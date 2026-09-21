"""The pre-run estimate stays an upper bound when trajectories carry tools."""

from harness.estimate import estimate_tokens
from harness.models import Expected, Trajectory, Turn

TOOL = {"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}


def trajectory(with_tools: bool, turns: int) -> Trajectory:
    return Trajectory(
        trajectory_id="t",
        tools=[TOOL] if with_tools else None,
        turns=[
            Turn(
                input="look it up",
                expected=Expected(label="x"),
                tool_result="a recorded tool result" if with_tools else None,
            )
            for _ in range(turns)
        ],
    )


def test_tools_and_tool_results_add_input_tokens_every_turn():
    _, plain_2, _ = estimate_tokens([trajectory(False, 2)], max_tokens=10)
    _, tools_2, _ = estimate_tokens([trajectory(True, 2)], max_tokens=10)
    _, plain_4, _ = estimate_tokens([trajectory(False, 4)], max_tokens=10)
    _, tools_4, _ = estimate_tokens([trajectory(True, 4)], max_tokens=10)
    assert tools_2 > plain_2
    assert (tools_4 - plain_4) > (tools_2 - plain_2)
