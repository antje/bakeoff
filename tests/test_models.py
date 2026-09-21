"""JSONL round trips: new optional keys survive, absent keys stay absent."""

import json

from harness.models import (
    Expected,
    Trajectory,
    Turn,
    load_trajectories,
    save_trajectories,
    trajectory_from_dict,
)

TOOL = {"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}


def test_tools_and_tool_result_round_trip(tmp_path):
    path = tmp_path / "t.jsonl"
    original = [
        Trajectory(
            trajectory_id="a",
            tools=[TOOL],
            turns=[
                Turn(
                    input="x",
                    expected=Expected(tool_call={"name": "lookup", "arguments": {}}),
                    tool_result={"lookup": "ok"},
                )
            ],
        ),
        Trajectory(trajectory_id="b", turns=[Turn(input="y", expected=Expected(label="l"))]),
    ]
    save_trajectories(path, original)
    assert load_trajectories(path) == original
    raw = [json.loads(line) for line in path.read_text().splitlines()]
    assert "tools" not in raw[1]
    assert "tool_result" not in raw[1]["turns"][0]


def test_bad_tools_and_tool_result_are_rejected():
    base = {"trajectory_id": "a", "turns": [{"input": "x", "expected": {"label": "l"}}]}
    try:
        trajectory_from_dict({**base, "tools": [{"type": "function"}]})
    except ValueError as err:
        assert "tools[0]" in str(err)
    else:
        raise AssertionError("expected ValueError")
    bad_turn = {"input": "x", "expected": {"label": "l"}, "tool_result": 42}
    try:
        trajectory_from_dict({**base, "turns": [bad_turn]})
    except ValueError as err:
        assert "tool_result" in str(err)
    else:
        raise AssertionError("expected ValueError")
