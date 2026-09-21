"""Turn call records into the two things a developer keeps: a table and its conditions.

Where this sits: `bench.py` hands `write_report()` every CallRecord from the
run plus what it knows about the run itself. Out come
`bench/results-<stamp>.json` (every call, re-readable) and
`bench/results-<stamp>.md` (the table, the conditions block, the verdict).

Why the conditions block is not optional. A latency number without the model
version, provider, quantization, date, sample size, and concurrency is a
number about nothing: it cannot be reproduced, compared, or argued with. So
the block is written first, above the table, and `/bakeoff` refuses to show
a table without it. This is the same discipline MLPerf enforces through its
submission rules, applied to a developer's afternoon.

The verdict is computed, not chosen: the cheapest cell (by cost per correct
call) whose gate pass rate is within `tolerance` of the best cell's and whose
TTFT p95 is inside the latency budget, when the developer gave one. A cheap
cell that makes the user wait past the budget is not a candidate, however
accurate; the eval description names the budget and the report applies it.
If no cell has a cost, the verdict falls back to the fastest p95 TTFT among
the most accurate cells.

The table's first row is the trivial baseline: what a constant answer per
turn would score on this eval, computed from the trajectories before any
model ran. It is the zero of the gate column. A model row at or below it has
not read the input, whatever its price, and the verdict says so.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .client import EndpointInfo, Target
from .metrics import Baseline, Summary, summarise, trivial_baseline
from .models import CallRecord, Trajectory, save_records


@dataclass
class RunConditions:
    """The facts that make the numbers reproducible. All go in the report header."""

    date_utc: str
    trajectories: int
    turns_per_trajectory_p50: float
    concurrency: int
    runs: int
    max_tokens: int
    warm_or_cold: str  # "cold" unless the developer pre-warmed; the harness never warms
    input_tokens_p50: float
    output_tokens_p50: float
    harness_commit: str
    endpoint: str
    judged: bool
    reasoning: str = "low"  # thinking budget requested from reasoning models
    ttft_budget_s: float | None = None  # p95 TTFT a cell must meet to be a contender


def harness_commit() -> str:
    """Short git hash of the harness, so a report can be tied to the code that made it."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def group_by_target(records: list[CallRecord]) -> dict[tuple[str, str], list[CallRecord]]:
    """Split records into cells keyed by (model, provider)."""
    cells: dict[tuple[str, str], list[CallRecord]] = {}
    for record in records:
        cells.setdefault((record.model, record.provider), []).append(record)
    return cells


def verdict(
    summaries: list[Summary],
    tolerance: float = 0.05,
    baseline: float = 0.0,
    ttft_budget_s: float | None = None,
) -> str:
    """Name the cell to route to, and say why in one sentence.

    Cells at or below the trivial baseline are not contenders: routing to a
    model that a constant answer would beat is not a routing decision. Cells
    whose TTFT p95 is over the latency budget are not contenders either, and
    the sentence names the ones that were dropped for it.
    """
    scored = [s for s in summaries if s.calls - s.errors > 0]
    if not scored:
        return "No verdict: every call errored."
    above = [s for s in scored if s.gate_pass_rate > baseline]
    if not above:
        return (
            f"No verdict: no cell beat the trivial baseline of {baseline:.0%}. "
            "The eval is not separating models; tighten the gate or the prompts before routing."
        )
    scored = above
    too_slow: list[Summary] = []
    if ttft_budget_s is not None:
        too_slow = [s for s in scored if s.ttft_p95_s > ttft_budget_s]
        scored = [s for s in scored if s.ttft_p95_s <= ttft_budget_s]
        if not scored:
            return (
                f"No verdict: every cell's TTFT p95 is over the {ttft_budget_s:.1f}s budget. "
                "Relax the budget on purpose or pin a faster provider."
            )
    dropped = ""
    if too_slow:
        names = ", ".join(f"{s.model} @ {s.provider} ({s.ttft_p95_s:.2f}s)" for s in too_slow)
        dropped = f" Over the {ttft_budget_s:.1f}s TTFT p95 budget and not considered: {names}."
    best_rate = max(s.gate_pass_rate for s in scored)
    contenders = [s for s in scored if s.gate_pass_rate >= best_rate - tolerance]
    priced = [s for s in contenders if s.cost_per_correct_call_usd is not None]
    if priced:
        pick = min(priced, key=lambda s: s.cost_per_correct_call_usd or 0)
        return (
            f"Route to {pick.model} @ {pick.provider}: gate {pick.gate_pass_rate:.0%} "
            f"(within {tolerance:.0%} of the best, {best_rate:.0%}) at "
            f"{_fmt_usd(pick.cost_per_correct_call_usd)} per correct call, the cheapest of "
            f"{len(contenders)} contender(s)." + dropped
        )
    pick = min(contenders, key=lambda s: s.ttft_p95_s)
    return (
        f"Route to {pick.model} @ {pick.provider}: gate {pick.gate_pass_rate:.0%} and the "
        f"lowest p95 TTFT ({pick.ttft_p95_s:.2f}s) among {len(contenders)} contender(s). "
        "No cost reported by these endpoints, so cost did not decide." + dropped
    )


def _fmt_usd(value: float | None) -> str:
    """Four decimals, or six when the value would otherwise round to nothing."""
    if value is None:
        return "n/a"
    return f"${value:.6f}" if 0 < value < 0.001 else f"${value:.4f}"


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def markdown_report(
    summaries: list[Summary],
    conditions: RunConditions,
    endpoints: dict[tuple[str, str], EndpointInfo | None],
    baseline: Baseline | None = None,
) -> str:
    """Render conditions, per-cell endpoint facts, the results table, and the verdict."""
    lines = ["# bakeoff results", ""]
    lines += ["## Conditions", ""]
    c = conditions
    lines += [
        f"- Date: {c.date_utc} (UTC)",
        f"- Endpoint: {c.endpoint}",
        f"- Trajectories: {c.trajectories}, turns per trajectory p50: {c.turns_per_trajectory_p50:.0f}",
        f"- Runs per trajectory: {c.runs}, concurrency: {c.concurrency}, max_tokens: {c.max_tokens}",
        f"- Reasoning effort requested: {c.reasoning} (applies to reasoning models only)",
        "- TTFT p95 budget: "
        + (f"{c.ttft_budget_s:.1f}s (cells over it are not contenders)" if c.ttft_budget_s else "none given"),
        f"- Cache state: {c.warm_or_cold} (the harness never pre-warms)",
        f"- Input tokens p50: {c.input_tokens_p50:.0f}, output tokens p50: {c.output_tokens_p50:.0f}",
        "- Timings are client-side wall clock and include network time",
        f"- Accuracy gate: {'LLM-judged (labelled)' if c.judged else 'deterministic (no judge)'}",
        f"- Harness commit: {c.harness_commit}",
        "",
        "Endpoint-level numbers. A provider's result is its serving stack, its hardware, "
        "and the network between here and there, under whatever load its fleet carries. "
        "Nothing here is a chip-level measurement.",
        "",
    ]
    lines += [
        "## Per-cell endpoint facts",
        "",
        "| model | provider | quantization | $/M in | $/M out |",
        "|---|---|---|---|---|",
    ]
    for s in summaries:
        info = endpoints.get((s.model, s.provider))
        if info is None:
            lines.append(f"| {s.model} | {s.provider} | unknown | n/a | n/a |")
        else:
            lines.append(
                f"| {s.model} | {s.provider} | {info.quantization} | "
                f"{info.prompt_price_per_token * 1e6:.2f} | {info.completion_price_per_token * 1e6:.2f} |"
            )
    lines += ["", "## Results", ""]
    header = (
        "| model | provider | gate | TTFT p50 | TTFT p95 | TPOT p50 | e2e p95 | "
        "tok/s/user | $/task | $/correct | consistency | errors |"
    )
    lines += [header, "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    if baseline is not None:
        answers = ", ".join(
            f"turn {i + 1}: {answer if answer else 'none passes'}"
            for i, (answer, _, _) in sorted(baseline.per_turn.items())
        )
        lines.append(
            f"| *trivial baseline* | *constant answer* | *{baseline.rate:.0%}* | | | | | | | | | |"
        )
        lines.append(f"| | ({answers}) | | | | | | | | | | |")
    for s in summaries:
        lines.append(
            f"| {s.model} | {s.provider} | {s.gate_pass_rate:.0%} | {s.ttft_p50_s:.2f}s | "
            f"{s.ttft_p95_s:.2f}s | {s.tpot_p50_s * 1000:.0f}ms | {s.e2e_p95_s:.2f}s | "
            f"{s.tokens_per_s_per_user_p50:.0f} | {_fmt_usd(s.cost_per_task_usd)} | "
            f"{_fmt_usd(s.cost_per_correct_call_usd)} | {_fmt_pct(s.consistency)} | {s.errors} |"
        )
    lines += [
        "",
        "TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. "
        "tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. "
        "$/correct: total cost divided by calls that passed the gate. "
        "trivial baseline: what a constant answer per turn scores; the zero of the gate column.",
        "",
        "## Verdict",
        "",
        verdict(
            summaries,
            baseline=baseline.rate if baseline else 0.0,
            ttft_budget_s=conditions.ttft_budget_s,
        ),
        "",
    ]
    notes = [f"- {s.model} @ {s.provider}: {n}" for s in summaries for n in s.notes]
    if notes:
        lines += ["## Notes", ""] + notes + [""]
    return "\n".join(lines)


def write_report(
    out_dir: Path,
    records: list[CallRecord],
    conditions: RunConditions,
    targets: list[Target],
    endpoints: dict[tuple[str, str], EndpointInfo | None],
    trajectories: list[Trajectory] | None = None,
) -> tuple[Path, Path, list[Summary]]:
    """Write results-<stamp>.json and results-<stamp>.md; return their paths and the summaries.

    `trajectories` are the ones that were replayed; they give the trivial
    baseline row. Without them the row is omitted."""
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"results-{stamp}.json"
    md_path = out_dir / f"results-{stamp}.md"
    save_records(json_path, records)

    cells = group_by_target(records)
    # Keep the developer's target order so the table reads the way the run was asked for.
    ordered_keys = [(t.model, t.provider) for t in targets if (t.model, t.provider) in cells]
    summaries = [summarise(cells[key]) for key in ordered_keys]

    baseline = trivial_baseline(trajectories) if trajectories else None
    md_path.write_text(markdown_report(summaries, conditions, endpoints, baseline))
    meta_path = out_dir / f"results-{stamp}.conditions.json"
    meta_path.write_text(json.dumps(asdict(conditions), indent=2))
    return json_path, md_path, summaries
