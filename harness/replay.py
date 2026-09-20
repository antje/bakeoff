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

Easy to get wrong: OpenRouter's cost and token counts arrive in the final
chunk's `usage`. Stop reading early and they are gone.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from openai import OpenAI

from .client import Target, request_extras
from .gate import check
from .models import CallRecord, Trajectory


@dataclass
class StreamResult:
    """Everything one streamed call produced, before it becomes a CallRecord."""

    text: str
    tool_calls: list[dict]
    time_to_first_token_s: float  # first token the user can see
    time_to_first_output_s: float  # first token of any kind, reasoning included
    total_latency_s: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    reasoning_chars: int
    finish_reason: str | None


def stream_one_call(
    client: OpenAI,
    target: Target,
    messages: list[dict],
    session_id: str,
    max_tokens: int,
    reasoning: str = "low",
) -> StreamResult:
    """Send one chat request with streaming on and measure it.

    Returns the assembled text, any tool calls, TTFT, total latency, and the
    provider-reported usage. Tool-call fragments are accumulated by index the
    way the OpenAI streaming protocol delivers them.

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

    stream = client.chat.completions.create(
        model=target.model,
        messages=messages,
        stream=True,
        max_tokens=max_tokens,
        stream_options={"include_usage": True},
        extra_body=extra_body,
        extra_headers=extra_headers,
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
            slot = tool_calls.setdefault(fragment.index, {"name": "", "arguments": ""})
            if fragment.function and fragment.function.name:
                slot["name"] += fragment.function.name
            if fragment.function and fragment.function.arguments:
                slot["arguments"] += fragment.function.arguments

    finished = time.perf_counter()
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
    turn the model's own answer is appended as the assistant message, so the
    next turn sees it. An exception on one turn is recorded as an errored,
    failed call and the replay continues with the history as it stands.
    """
    session_id = f"{trajectory.trajectory_id}-run{run}"
    history: list[dict] = []
    if trajectory.system:
        history.append({"role": "system", "content": trajectory.system})

    records: list[CallRecord] = []
    for turn_index, turn in enumerate(trajectory.turns):
        history.append({"role": "user", "content": turn.input})
        try:
            result = stream_one_call(client, target, history, session_id, max_tokens, reasoning)
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
                    },
                )
            )
            history.append({"role": "assistant", "content": result.text or ""})
        except Exception as err:  # noqa: BLE001 - any provider error is one failed call
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
                )
            )
            history.append({"role": "assistant", "content": ""})
    return records
