"""The example generators are deterministic and produce evals the gate can use honestly.

Each generator under scripts/examples/ is imported and run twice; the output
must be identical, must load through `load_trajectories`, and must not hand
the gate a label set where one label is a substring of another (that is the
one way `check_label` can pass two answers at once).
"""

import importlib
import json
import sys
from pathlib import Path

import pytest

from harness.gate import check_pattern
from harness.metrics import trivial_baseline
from harness.models import trajectory_from_dict

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "examples"
sys.path.insert(0, str(SCRIPTS))

GENERATORS = ["ticket_triage", "contract_extract", "tool_router", "ledger_audit", "code_fix"]


@pytest.fixture(params=GENERATORS)
def generator(request):
    return importlib.import_module(request.param)


def test_generator_is_deterministic(generator):
    first = generator.build()
    second = generator.build()
    assert first == second


def test_generated_trajectories_load_and_round_trip(generator):
    _, trajectories = generator.build()
    assert len(trajectories) >= 20
    for trajectory in trajectories:
        raw = json.loads(json.dumps(trajectory, default=lambda o: o.__dict__))
        assert trajectory_from_dict(raw) == trajectory


def test_label_sets_have_no_substring_collisions(generator):
    _, trajectories = generator.build()
    per_turn: dict[int, set[str]] = {}
    for trajectory in trajectories:
        for index, turn in enumerate(trajectory.turns):
            if turn.expected.label:
                per_turn.setdefault(index, set()).add(turn.expected.label.lower())
    for labels in per_turn.values():
        for a in labels:
            for b in labels:
                assert a == b or a not in b, f"label {a!r} is inside {b!r}"


def test_trivial_baseline_is_low(generator):
    _, trajectories = generator.build()
    assert trivial_baseline(trajectories).rate <= 0.25


def test_committed_files_match_the_generator(generator):
    name = generator.__name__.replace("_", "-")
    path = Path(__file__).resolve().parents[1] / "examples" / name / "trajectories.jsonl"
    if not path.exists():
        pytest.skip(f"{path} not generated yet")
    _, trajectories = generator.build()
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    committed = [trajectory_from_dict(json.loads(line)) for line in lines]
    assert committed == trajectories


def test_ledger_patterns_reject_neighbouring_numbers():
    ledger = importlib.import_module("ledger_audit")
    for value in (7, 533, 16533, -250, -1200):
        pattern = ledger.number_pattern(value)
        assert check_pattern(pattern, f"{value}\nworking: {value + 1}")
        assert check_pattern(pattern, f"{value:,}")
        assert not check_pattern(pattern, str(value + 1))
        assert not check_pattern(pattern, str(value * 10))
        assert not check_pattern(pattern, f"-{abs(value)}" if value > 0 else str(abs(value)))
