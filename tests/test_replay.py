"""Closed-loop replay, checked with a fake streaming client and no network.

The fake records every request it receives, so the tests can assert the one
thing that matters about closed-loop replay: turn N sees turns 1..N-1 and the
model's own earlier answers.
"""

from types import SimpleNamespace

from harness.client import Target
from harness.models import Expected, Trajectory, Turn
from harness.replay import UNKNOWN_TOOL_RESULT, replay_trajectory


class FakeStream:
    """Yields chunks the way the OpenAI SDK does: content deltas, then a usage-only chunk.

    `tool_fragments` is a list of chunks, each a list of fragment dicts with
    any of index / id / name / arguments, so a test can stream one tool call
    in as many pieces as a real provider does.
    """

    def __init__(self, text: str = "", cost: float = 0.001, tool_fragments: list[list[dict]] | None = None):
        self.text = text
        self.cost = cost
        self.tool_fragments = tool_fragments or []

    def __iter__(self):
        for piece in self.text.split(" ") if self.text else []:
            delta = SimpleNamespace(content=piece + " ", tool_calls=None)
            yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)
        for chunk in self.tool_fragments:
            fragments = [
                SimpleNamespace(
                    index=f.get("index", 0),
                    id=f.get("id"),
                    type="function",
                    function=SimpleNamespace(name=f.get("name"), arguments=f.get("arguments")),
                )
                for f in chunk
            ]
            delta = SimpleNamespace(content=None, tool_calls=fragments)
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=delta, finish_reason="tool_calls")], usage=None
            )
        usage = SimpleNamespace(prompt_tokens=50, completion_tokens=8, model_extra={"cost": self.cost})
        yield SimpleNamespace(choices=[], usage=usage)


class FakeClient:
    """Answers "billing" to everything (or the queued responses) and remembers each request."""

    def __init__(self, responses: list[FakeStream] | None = None):
        self.requests: list[list[dict]] = []
        self.kwargs: list[dict] = []
        self.responses = list(responses or [])
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append([dict(m) for m in kwargs["messages"]])
        self.kwargs.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        return FakeStream("the category is billing")


def make_trajectory() -> Trajectory:
    return Trajectory(
        trajectory_id="t-1",
        system="You classify support tickets.",
        turns=[
            Turn(input="I was charged twice.", expected=Expected(label="billing")),
            Turn(input="And the app crashes.", expected=Expected(label="technical")),
        ],
    )


def test_history_accumulates_across_turns():
    client = FakeClient()
    records = replay_trajectory(client, Target(model="m"), make_trajectory(), run=1)

    assert len(records) == 2
    first, second = client.requests
    assert [m["role"] for m in first] == ["system", "user"]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert "billing" in second[2]["content"]


def test_gate_and_usage_land_on_the_record():
    client = FakeClient()
    records = replay_trajectory(client, Target(model="m"), make_trajectory(), run=1)

    assert records[0].passed is True  # "billing" matched
    assert records[1].passed is False  # answered billing, expected technical
    assert records[0].input_tokens == 50
    assert records[0].output_tokens == 8
    assert records[0].cost_usd == 0.001
    assert 0 < records[0].time_to_first_token_s <= records[0].total_latency_s


def test_an_exception_becomes_an_errored_failed_call_and_replay_continues():
    class Exploding(FakeClient):
        def _create(self, **kwargs):
            if len(self.requests) == 0:
                self.requests.append([])
                raise RuntimeError("provider 503")
            return super()._create(**kwargs)

    client = Exploding()
    records = replay_trajectory(client, Target(model="m"), make_trajectory(), run=1)
    assert records[0].error and records[0].error.startswith("RuntimeError")
    assert records[0].passed is False
    assert records[1].error is None


# --- tool calling ------------------------------------------------------------

LOOKUP_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup",
        "description": "Look up an order.",
        "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}},
    },
}


def make_tool_trajectory(tool_result="found: order 1") -> Trajectory:
    return Trajectory(
        trajectory_id="t-tools",
        system="You are an order assistant.",
        tools=[LOOKUP_TOOL],
        turns=[
            Turn(
                input="Look up order 1.",
                expected=Expected(tool_call={"name": "lookup", "arguments": {"id": 1}}),
                tool_result=tool_result,
            ),
            Turn(input="Is it a billing issue?", expected=Expected(label="billing")),
        ],
    )


def lookup_stream(*fragment_chunks: list[dict]) -> FakeStream:
    return FakeStream(tool_fragments=list(fragment_chunks))


def test_tools_are_not_sent_when_the_trajectory_has_none():
    client = FakeClient()
    replay_trajectory(client, Target(model="m"), make_trajectory(), run=1)
    assert "tools" not in client.kwargs[0]
    assert "tool_choice" not in client.kwargs[0]


def test_tools_and_tool_choice_are_sent_when_present():
    client = FakeClient([lookup_stream([{"id": "call_1", "name": "lookup", "arguments": '{"id": 1}'}])])
    replay_trajectory(client, Target(model="m"), make_tool_trajectory(), run=1)
    assert client.kwargs[0]["tools"] == [LOOKUP_TOOL]
    assert client.kwargs[0]["tool_choice"] == "auto"


def test_fragmented_tool_call_is_assembled_and_fed_back():
    client = FakeClient(
        [
            lookup_stream(
                [{"id": "call_1", "name": "lookup", "arguments": ""}],
                [{"arguments": '{"id"'}],
                [{"arguments": ": 1}"}],
            )
        ]
    )
    trajectory = make_tool_trajectory({"lookup": "found: order 1"})
    records = replay_trajectory(client, Target(model="m"), trajectory, run=1)

    assert records[0].passed is True
    assert records[0].extra["tool_calls"][0]["id"] == "call_1"
    second = client.requests[1]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "tool", "user"]
    assert second[2]["tool_calls"][0]["function"]["arguments"] == '{"id": 1}'
    assert "content" not in second[2]
    assert second[3]["tool_call_id"] == "call_1"
    assert second[3]["content"] == "found: order 1"
    assert records[1].passed is True


def test_id_repeated_on_every_fragment_is_not_concatenated():
    client = FakeClient(
        [
            lookup_stream(
                [{"id": "call_1", "name": "lookup", "arguments": '{"id":'}],
                [{"id": "call_1", "arguments": " 1}"}],
            )
        ]
    )
    records = replay_trajectory(client, Target(model="m"), make_tool_trajectory(), run=1)
    assert records[0].extra["tool_calls"][0]["id"] == "call_1"
    assert records[0].passed is True


def test_string_tool_result_applies_to_the_call():
    client = FakeClient([lookup_stream([{"id": "c", "name": "lookup", "arguments": '{"id": 1}'}])])
    replay_trajectory(client, Target(model="m"), make_tool_trajectory("ok"), run=1)
    assert client.requests[1][3]["content"] == "ok"


def test_unknown_tool_gets_the_error_sentinel_and_replay_continues():
    client = FakeClient([lookup_stream([{"id": "c", "name": "other", "arguments": "{}"}])])
    records = replay_trajectory(client, Target(model="m"), make_tool_trajectory({"lookup": "x"}), run=1)
    assert records[0].passed is False
    assert client.requests[1][3]["content"] == UNKNOWN_TOOL_RESULT
    assert records[1].error is None


def test_missing_id_is_synthesised_and_counted():
    client = FakeClient([lookup_stream([{"name": "lookup", "arguments": '{"id": 1}'}])])
    records = replay_trajectory(client, Target(model="m"), make_tool_trajectory(), run=1)
    assert client.requests[1][3]["tool_call_id"] == "call_0"
    assert records[0].extra["synthesised_ids"] == 1


def test_text_on_a_tool_turn_appends_a_plain_assistant_message():
    client = FakeClient()  # answers in text
    records = replay_trajectory(client, Target(model="m"), make_tool_trajectory(), run=1)
    assert records[0].passed is False
    assert [m["role"] for m in client.requests[1]] == ["system", "user", "assistant", "user"]


def test_tools_rejection_is_flagged_on_the_record():
    class Refusing(FakeClient):
        def _create(self, **kwargs):
            self.requests.append([])
            raise RuntimeError("No endpoints found that support tool use")

    records = replay_trajectory(Refusing(), Target(model="m"), make_tool_trajectory(), run=1)
    assert records[0].extra.get("tools_rejected") is True
    assert records[0].passed is False
