"""The shortlist must come from the workload's requirements, never from a guess."""

from harness.candidates import qualify, requirements, shortlist
from harness.models import Expected, Trajectory, Turn

TOOL = {"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}


def _trajectory(tools=None, input_chars=400, turns=3):
    return Trajectory(
        trajectory_id="t",
        turns=[Turn(input="x" * input_chars, expected=Expected(label="ok")) for _ in range(turns)],
        tools=tools,
    )


def _entry(model, prompt, completion, context=128_000, tools=True, **extra):
    return {
        "id": model,
        "name": model,
        "context_length": context,
        "pricing": {"prompt": str(prompt), "completion": str(completion)},
        "supported_parameters": ["tools", "max_tokens"] if tools else ["max_tokens"],
        **extra,
    }


CATALOG = [
    _entry("cheap/1b", 1e-8, 2e-8),
    _entry("cheap/1b:free", 0, 0),
    _entry("openrouter/auto", 1e-6, 2e-6),
    _entry("mid/35b", 1e-7, 4e-7),
    _entry("mid/120b", 1.5e-7, 6e-7),
    _entry("notools/70b", 5e-8, 1e-7, tools=False),
    _entry("short/ctx", 2e-8, 4e-8, context=2_000),
    _entry("ship/sonnet", 3e-6, 1.5e-5),
    _entry("pricey/pro", 1.5e-5, 6e-5),
    _entry(
        "vision/only", 1e-6, 2e-6,
        architecture={"input_modalities": ["image"], "output_modalities": ["text"]},
    ),
]


def test_requirements_read_tools_and_context_off_the_trajectories():
    req = requirements([_trajectory(tools=[TOOL], input_chars=4_000, turns=3)], max_tokens=500)
    assert req.needs_tools
    # 3 inputs of 1000 tokens, 2 earlier outputs of 500, the tool schema, the last output, plus headroom
    assert 5_000 < req.context_tokens < 6_000
    assert not requirements([_trajectory()], max_tokens=100).needs_tools


def test_qualify_drops_free_router_variant_short_context_and_no_tools_when_tools_are_needed():
    req = requirements([_trajectory(tools=[TOOL], input_chars=4_000)], max_tokens=500)
    ids = [c.model for c in qualify(CATALOG, req)]
    assert ids == ["cheap/1b", "mid/35b", "mid/120b", "ship/sonnet", "pricey/pro"]
    req_no_tools = requirements([_trajectory(input_chars=4_000)], max_tokens=500)
    assert "notools/70b" in [c.model for c in qualify(CATALOG, req_no_tools)]


def test_candidates_are_priced_on_this_workload_and_sorted_cheapest_first():
    req = requirements([_trajectory(input_chars=4_000)], max_tokens=500)
    candidates = qualify(CATALOG, req)
    assert [c.run_usd for c in candidates] == sorted(c.run_usd for c in candidates)
    cheap = candidates[0]
    assert cheap.run_usd == req.input_tokens * 1e-8 + req.output_tokens * 2e-8


def test_shortlist_uses_the_ceiling_you_ship_and_the_log_midpoint():
    req = requirements([_trajectory(tools=[TOOL])], max_tokens=200)
    picks = shortlist(qualify(CATALOG, req), ceiling="ship/sonnet")
    assert picks.floor.model == "cheap/1b"
    assert picks.ceiling.model == "ship/sonnet"
    assert picks.middle.model in ("mid/35b", "mid/120b")
    assert picks.reasons["ceiling"] == "the model you ship (--ceiling)"
    assert picks.models == ["cheap/1b", picks.middle.model, "ship/sonnet"]


def test_shortlist_explains_a_ceiling_that_does_not_qualify():
    req = requirements([_trajectory(tools=[TOOL])], max_tokens=200)
    picks = shortlist(qualify(CATALOG, req), ceiling="notools/70b")
    assert picks.ceiling.model == "pricey/pro"
    assert "not in the qualifying list" in picks.reasons["ceiling"]
