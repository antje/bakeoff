"""Shared plumbing for the example generators: one seed, one writer, one layout.

Where this sits: each `scripts/examples/<name>.py` imports from here and
writes `examples/<name>/logs.jsonl` (the raw material a developer would have
before `/eval-build`) and `examples/<name>/trajectories.jsonl` (what
`/eval-build` produces from it). `tests/test_examples.py` calls `build()` on
every generator and checks determinism and gate hygiene.

Why one seed. The datasets are synthetic, and the honest way to be synthetic
is to be reproducible: anyone can regenerate the file and get the same bytes,
and a change to a generator shows up as a diff, not as a different eval.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from harness.models import Trajectory, save_trajectories  # noqa: E402

SEED = 20260920


def rng() -> random.Random:
    return random.Random(SEED)


def write_example(name: str, logs: list[dict], trajectories: list[Trajectory]) -> Path:
    """Write logs.jsonl and trajectories.jsonl under examples/<name>/ and return the dir."""
    out = ROOT / "examples" / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs.jsonl").write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in logs) + "\n"
    )
    save_trajectories(out / "trajectories.jsonl", trajectories)
    return out
