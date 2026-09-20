"""The data shapes bakeoff moves around, and how they get on and off disk.

Where this sits: everything else imports from here. `/eval-build` writes
Trajectory objects to `bench/trajectories.jsonl`; `replay.py` turns each one
into a list of CallRecord objects; `metrics.py` and `report.py` summarise them.

The vocabulary, once:

- A **trajectory** is one conversation with an agent: several turns in order.
  It is the unit MLPerf's agentic benchmark replays, because later turns depend
  on earlier ones and a single prompt in isolation would not exercise that.
- A **turn** is one user input plus what a correct answer looks like.
- An **expected** answer is ground truth written down before the model runs:
  a tool call (name plus arguments), a label from a closed set, or a text
  pattern. Never an opinion formed after seeing the output.
- A **call record** is what one model call actually did: the tokens, the
  timings, the cost, and whether it passed the gate.

Everything is a plain dataclass so it prints, diffs, and serialises without
surprises.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Expected:
    """What a correct answer to one turn looks like. Exactly one field is set.

    tool_call: {"name": "...", "arguments": {...}}; passes when the model calls
        the same tool with arguments that match after JSON normalisation.
    label: one value from a closed set, compared case-insensitively.
    pattern: a regular expression searched in the model's text.

    Easy to get wrong: setting none of them. That turn can never pass and will
    quietly drag the pass rate down, so `load_trajectories` rejects it.
    """

    tool_call: dict | None = None
    label: str | None = None
    pattern: str | None = None

    def kind(self) -> str:
        """Return which kind of check this is: "tool_call", "label" or "pattern"."""
        if self.tool_call is not None:
            return "tool_call"
        if self.label is not None:
            return "label"
        if self.pattern is not None:
            return "pattern"
        raise ValueError("Expected has no tool_call, label or pattern set")


@dataclass
class Turn:
    """One user input and its expected answer."""

    input: str
    expected: Expected


@dataclass
class Trajectory:
    """One conversation to replay: an id, an optional system prompt, ordered turns."""

    trajectory_id: str
    turns: list[Turn]
    system: str | None = None

    @property
    def turn_count(self) -> int:
        return len(self.turns)


@dataclass
class CallRecord:
    """What one model call did. One per turn per model per provider per run.

    Timings are in seconds. Tokens come from the provider's usage object, not
    from a local tokenizer, because the provider's count is what gets billed.
    `cost_usd` is the provider-reported cost for this call, or None when the
    endpoint does not report one (a local vLLM server, for example).
    """

    trajectory_id: str
    turn_index: int
    model: str
    provider: str
    run: int
    passed: bool
    gate_kind: str
    time_to_first_token_s: float  # first visible token (TTFT)
    time_to_first_output_s: float  # first token of any kind, reasoning included; TPOT starts here
    total_latency_s: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    output_text: str
    error: str | None = None
    extra: dict = field(default_factory=dict)


# --- JSONL on and off disk ---------------------------------------------------


def trajectory_from_dict(raw: dict) -> Trajectory:
    """Build a Trajectory from one parsed JSONL line, validating the shape.

    Raises ValueError with the trajectory id in the message, so a bad line in a
    50-line file is findable.
    """
    trajectory_id = str(raw.get("trajectory_id", "")).strip()
    if not trajectory_id:
        raise ValueError("trajectory is missing trajectory_id")
    turns_raw = raw.get("turns") or []
    if not turns_raw:
        raise ValueError(f"{trajectory_id}: has no turns")

    turns: list[Turn] = []
    for index, turn_raw in enumerate(turns_raw):
        expected_raw = turn_raw.get("expected") or {}
        expected = Expected(
            tool_call=expected_raw.get("tool_call"),
            label=expected_raw.get("label"),
            pattern=expected_raw.get("pattern"),
        )
        try:
            expected.kind()
        except ValueError as err:
            raise ValueError(f"{trajectory_id} turn {index}: {err}") from err
        turns.append(Turn(input=str(turn_raw["input"]), expected=expected))

    return Trajectory(trajectory_id=trajectory_id, turns=turns, system=raw.get("system"))


def load_trajectories(path: Path) -> list[Trajectory]:
    """Read a JSONL file of trajectories. Blank lines are skipped; bad lines raise."""
    trajectories: list[Trajectory] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            trajectories.append(trajectory_from_dict(json.loads(line)))
        except (json.JSONDecodeError, ValueError, KeyError) as err:
            raise ValueError(f"{path}:{line_number}: {err}") from err
    return trajectories


def save_trajectories(path: Path, trajectories: list[Trajectory]) -> None:
    """Write trajectories as JSONL, one per line, with None fields dropped."""
    lines = []
    for trajectory in trajectories:
        raw = asdict(trajectory)
        for turn in raw["turns"]:
            turn["expected"] = {k: v for k, v in turn["expected"].items() if v is not None}
        if raw["system"] is None:
            del raw["system"]
        lines.append(json.dumps(raw, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n")


def save_records(path: Path, records: list[CallRecord]) -> None:
    """Write call records as JSON so a run can be re-read exactly as it happened."""
    path.write_text(json.dumps([asdict(r) for r in records], indent=2, ensure_ascii=False))
