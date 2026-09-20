"""Closed-loop replay, checked with a fake streaming client and no network.

The fake records every request it receives, so the tests can assert the one
thing that matters about closed-loop replay: turn N sees turns 1..N-1 and the
model's own earlier answers.
"""

from types import SimpleNamespace

from harness.client import Target
from harness.models import Expected, Trajectory, Turn
from harness.replay import replay_trajectory


class FakeStream:
    """Yields chunks the way the OpenAI SDK does: content deltas, then a usage-only chunk."""

    def __init__(self, text: str, cost: float = 0.001):
        self.text = text
        self.cost = cost

    def __iter__(self):
        for piece in self.text.split(" "):
            delta = SimpleNamespace(content=piece + " ", tool_calls=None)
            yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)
        usage = SimpleNamespace(prompt_tokens=50, completion_tokens=8, model_extra={"cost": self.cost})
        yield SimpleNamespace(choices=[], usage=usage)


class FakeClient:
    """Answers "billing" to everything and remembers each request's messages."""

    def __init__(self):
        self.requests: list[list[dict]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append([dict(m) for m in kwargs["messages"]])
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
