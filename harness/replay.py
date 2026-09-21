"""Closed-loop replay: run one trajectory through one target, turn by turn.

Where this sits: `bench.py` calls `replay_trajectory()` for every
(trajectory, target, run) and collects the CallRecords.

Why closed-loop. An agent's fifth turn depends on the first four. If we sent
each turn as an independent prompt we would be measuring a chatbot, not an
agent: the prompt would be short, the prefill cheap, and the model would never
have to carry state. So this file does what MLPerf's agentic benchmark does:
send turn 1, wait for the *complete* answer, append it to the history, send
turn 2 with that history, and so on. Context grows every turn, the way it
does in production.

How the timings are taken. The request streams. TTFT is the clock reading at
the first chunk that carries content (a token or a tool-call fragment), not
the first bytes on the wire, because providers send keep-alive events before
any token. Total latency is the clock reading when the stream closes. Both are
wall-clock seconds measured on the client, which means they include network
time. That is deliberate: it is what a developer's users experience, and the
conditions block says so.

Tool calling. When the trajectory carries tool schemas they go on every
request, and after a turn where the model called a tool the history gets the
assistant's `tool_calls` message followed by one `tool` message per call
holding the *recorded* result from the trajectory. Nothing is executed; every
model is shown the same world, the way MLPerf replays recorded tool outputs.
Known gap: reasoning models that need `reasoning_details` echoed back to keep
tool-call coherence (some DeepSeek and Qwen endpoints) are not handled.

Easy to get wrong: OpenRouter's cost and token counts arrive in the final
chunk's `usage`. Stop reading early and they are gone.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from openai import BadRequestError, OpenAI, RateLimitError

from .client import Target, request_extras
from .gate import check
from .models import CallRecord, Trajectory, Turn

UNKNOWN_TOOL_RESULT = "error: unknown tool"


@dataclass
class StreamResult:
    """Everything one streamed call produced, before it becomes a CallRecord."""

    text: str
    tool_calls: list[dict]  # each {"id", "name", "arguments"}; arguments is the raw JSON string
    time_to_first_token_s: float  # first token the user can see
    time_to_first_output_s: float  # first token of any kind, reasoning included
    total_latency_s: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    reasoning_chars: int
    finish_reason: str | None
    reasoning_used: str = ""  # what was actually requested, after any fallback
    synthesised_ids: int = 0  # tool calls the provider streamed without an id


def stream_one_call(
    client: OpenAI,
    target: Target,
    messages: list[dict],
    session_id: str,
    max_tokens: int,
    reasoning: str = "low",
    tools: list[dict] | None = None,
) -> StreamResult:
    """Send one chat request with streaming on and measure it.

    Returns the assembled text, any tool calls, TTFT, total latency, and the
    provider-reported usage. Tool-call fragments are accumulated by index the
    way the OpenAI streaming protocol delivers them; the call id is assigned
    from whichever fragment carries it (some providers repeat it on every
    fragment, some send it once), never concatenated. A call that never gets
    an id is given `call_<index>` so the tool message can still reference it.
    `tools` is sent only when present, so a text-only run is byte-identical
    to one from before tool support existed.

    Reasoning models stream their thinking as a separate `reasoning` field
    before any content. That is not counted as the first *visible* token
    (TTFT), because the user cannot see it. It is counted as the first
    *output* (`time_to_first_output_s`), which is what TPOT is measured from,
    because the provider bills those tokens and they take real decode time.
    `reasoning_chars` makes a record that ends with no text explainable.
    """
    extra_body, extra_headers = request_extras(target, session_id, reasoning)
    started = time.perf_counter()
    first_token_at: float | None = None
    first_output_at: float | None = None
    text_parts: list[str] = []
    tool_calls: dict[int, dict] = {}
    reasoning_chars = 0
    finish_reason: str | None = None
    usage = None

    tool_kwargs: dict = {"tools": tools, "tool_choice": "auto"} if tools else {}
    stream = client.chat.completions.create(
        model=target.model,
        messages=messages,
        stream=True,
        max_tokens=max_tokens,
        stream_options={"include_usage": True},
        extra_body=extra_body,
        extra_headers=extra_headers,
        **tool_kwargs,
    )
    for chunk in stream:
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        if getattr(choice, "finish_reason", None):
            finish_reason = choice.finish_reason
        delta = choice.delta
        if delta is None:
            continue
        # OpenRouter puts a reasoning model's thinking in a non-standard field.
        thinking = (getattr(delta, "model_extra", None) or {}).get("reasoning")
        if thinking:
            reasoning_chars += len(thinking)
            if first_output_at is None:
                first_output_at = time.perf_counter()
        if delta.content:
            if first_token_at is None:
                first_token_at = time.perf_counter()
            if first_output_at is None:
                first_output_at = first_token_at
            text_parts.append(delta.content)
        for fragment in delta.tool_calls or []:
            if first_token_at is None:
                first_token_at = time.perf_counter()
            if first_output_at is None:
                first_output_at = first_token_at
            index = getattr(fragment, "index", None)
            if index is None:
                # A few servers omit the index; a fragment with a new id starts
                # a new call, anything else continues the latest one.
                fragment_id = getattr(fragment, "id", None)
                known = {slot["id"] for slot in tool_calls.values()}
                starts_new = not tool_calls or (fragment_id and fragment_id not in known)
                index = len(tool_calls) if starts_new else max(tool_calls)
            slot = tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
            if getattr(fragment, "id", None):
                slot["id"] = fragment.id
            if fragment.function and fragment.function.name:
                slot["name"] += fragment.function.name
            if fragment.function and fragment.function.arguments:
                slot["arguments"] += fragment.function.arguments

    finished = time.perf_counter()
    synthesised = 0
    for index, slot in tool_calls.items():
        if not slot["id"]:
            slot["id"] = f"call_{index}"
            synthesised += 1
    # A response with no content at all still "started" when it finished, so
    # TTFT never exceeds total latency.
    ttft = (first_token_at or finished) - started
    first_output = (first_output_at or first_token_at or finished) - started

    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    # OpenRouter puts the dollar cost on the usage object; the OpenAI SDK keeps
    # unknown fields in model_extra. Local servers have neither.
    cost = None
    if usage is not None:
        extra = getattr(usage, "model_extra", None) or {}
        cost = extra.get("cost")
        cost = float(cost) if cost is not None else None

    return StreamResult(
        text="".join(text_parts),
        tool_calls=[tool_calls[i] for i in sorted(tool_calls)],
        time_to_first_token_s=ttft,
        time_to_first_output_s=first_output,
        total_latency_s=finished - started,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        reasoning_chars=reasoning_chars,
        finish_reason=finish_reason,
        synthesised_ids=synthesised,
    )


def call_with_backoff(
    client: OpenAI,
    target: Target,
    messages: list[dict],
    session_id: str,
    max_tokens: int,
    reasoning: str,
    attempts: int = 5,
    tools: list[dict] | None = None,
) -> StreamResult:
    """Retry a call on HTTP 429, waiting longer each time.

    Providers and OpenRouter enforce per-minute limits (a new OpenRouter account
    gets 20 requests per minute on some models). A rate limit is not a property
    of the model, so it should slow the run down, not fail a turn. Waits 5, 10,
    20, 40 seconds between attempts; anything else raises immediately.

    One more model-specific case: some endpoints refuse `reasoning: off`
    ("Reasoning is mandatory for this endpoint"). Rather than fail every turn,
    the call is retried once at effort "low" and the record notes the fallback,
    because the developer chose "off" and should see that it did not apply.
    """
    for attempt in range(attempts):
        try:
            result = stream_one_call(
                client, target, messages, session_id, max_tokens, reasoning, tools
            )
            result.reasoning_used = reasoning
            return result
        except BadRequestError as err:
            if reasoning == "off" and "reasoning" in str(err).lower():
                result = stream_one_call(
                    client, target, messages, session_id, max_tokens, "low", tools
                )
                result.reasoning_used = "low (endpoint refused off)"
                return result
            raise
        except RateLimitError:
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (2**attempt))
    raise RuntimeError("unreachable")


def _tool_content(tool_result: str | dict[str, str] | None, name: str) -> str:
    """The recorded output to feed back for one call, or the sentinel when none was recorded."""
    if tool_result is None:
        return UNKNOWN_TOOL_RESULT
    if isinstance(tool_result, str):
        return tool_result
    return tool_result.get(name, UNKNOWN_TOOL_RESULT)


def extend_history(history: list[dict], result: StreamResult, turn: Turn) -> None:
    """Append what the model said, in the shape the next request needs.

    Text answer: one assistant message, as before. Tool calls: the assistant
    message carrying `tool_calls`, then exactly one `tool` message per call in
    call order, each with the recorded result. Every provider on the OpenAI
    protocol requires each call id to be answered before the next user turn;
    Anthropic via OpenRouter rejects the request otherwise. `content` is
    omitted rather than set to null on the tool-call message, because some
    providers reject null.
    """
    if not result.tool_calls:
        history.append({"role": "assistant", "content": result.text or ""})
        return
    assistant: dict = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": call["id"],
                "type": "function",
                "function": {"name": call["name"], "arguments": call["arguments"] or "{}"},
            }
            for call in result.tool_calls
        ],
    }
    if result.text:
        assistant["content"] = result.text
    history.append(assistant)
    for call in result.tool_calls:
        history.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": _tool_content(turn.tool_result, call["name"]),
            }
        )


def replay_trajectory(
    client: OpenAI,
    target: Target,
    trajectory: Trajectory,
    run: int,
    max_tokens: int = 1024,
    reasoning: str = "low",
) -> list[CallRecord]:
    """Replay one trajectory closed-loop and return one CallRecord per turn.

    The history starts with the trajectory's system prompt (if any). After each
    turn the model's own answer is appended (see `extend_history`), so the
    next turn sees it. An exception on one turn is recorded as an errored,
    failed call and the replay continues with the history as it stands. When
    the trajectory has tools and the endpoint refuses them, the record is
    tagged `tools_rejected` so the report can say why the row scored zero.
    """
    session_id = f"{trajectory.trajectory_id}-run{run}"
    history: list[dict] = []
    if trajectory.system:
        history.append({"role": "system", "content": trajectory.system})

    records: list[CallRecord] = []
    for turn_index, turn in enumerate(trajectory.turns):
        history.append({"role": "user", "content": turn.input})
        try:
            result = call_with_backoff(
                client, target, history, session_id, max_tokens, reasoning,
                tools=trajectory.tools or None,
            )
            passed = check(turn.expected, result.text, result.tool_calls)
            records.append(
                CallRecord(
                    trajectory_id=trajectory.trajectory_id,
                    turn_index=turn_index,
                    model=target.model,
                    provider=target.provider,
                    run=run,
                    passed=passed,
                    gate_kind=turn.expected.kind(),
                    time_to_first_token_s=result.time_to_first_token_s,
                    time_to_first_output_s=result.time_to_first_output_s,
                    total_latency_s=result.total_latency_s,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cost_usd=result.cost_usd,
                    output_text=result.text,
                    extra={
                        "tool_calls": result.tool_calls,
                        "reasoning_chars": result.reasoning_chars,
                        "finish_reason": result.finish_reason,
                        "reasoning_used": result.reasoning_used,
                        "synthesised_ids": result.synthesised_ids,
                    },
                )
            )
            extend_history(history, result, turn)
        except Exception as err:  # noqa: BLE001 - any provider error is one failed call
            # OpenRouter answers a pinned provider with no tool support with a
            # 404 "No endpoints found that support tool use", so match the text.
            tools_rejected = bool(trajectory.tools) and "tool" in str(err).lower()
            records.append(
                CallRecord(
                    trajectory_id=trajectory.trajectory_id,
                    turn_index=turn_index,
                    model=target.model,
                    provider=target.provider,
                    run=run,
                    passed=False,
                    gate_kind=turn.expected.kind(),
                    time_to_first_token_s=0.0,
                    time_to_first_output_s=0.0,
                    total_latency_s=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=None,
                    output_text="",
                    error=f"{type(err).__name__}: {err}"[:300],
                    extra={"tools_rejected": True} if tools_rejected else {},
                )
            )
            history.append({"role": "assistant", "content": ""})
    return records
