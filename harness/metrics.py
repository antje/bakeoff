"""Every number in the report is computed here, once, with its formula written down.

Where this sits: `report.py` calls `summarise()` with the CallRecords for one
model on one provider and gets back a Summary. Nothing else does arithmetic
on records, so if a number in a report looks wrong, this file is the only
place to look.

The metrics, and who feels each one:

- **TTFT** (time to first token): how long a user stares at nothing. This is
  the number an interactive user feels. It is dominated by prefill, the phase
  where the model reads the whole prompt.
- **TPOT** (time per output token): how fast the model generates once it has
  started. TPOT = (total latency - time to first output) / output tokens,
  where "first output" includes hidden reasoning tokens because the provider
  bills them and they take decode time. It is dominated by decode, the phase
  where the model writes one token at a time.
- **End-to-end latency**: TTFT plus the whole decode. What an agent waiting on
  a tool result feels, because it cannot act on a partial answer.
- **Tokens per second per user**: output tokens / decode time for one stream.
  MLPerf's "interactivity" axis.
- **p50 / p95**: the median and the 95th percentile. Reporting only the median
  hides the slow tail, and the tail is what users complain about. Both are
  always reported together.
- **Cost per task**: the sum of every call's cost across a trajectory. Agents
  make many calls per task, so per-call cost understates the bill.
- **Cost per correct call**: total cost / number of calls that passed the
  gate. The headline. A cheap model that is wrong half the time is not cheap.
- **Consistency**: when the same trajectory is replayed twice, how often the
  gate result agrees. A model that flips between runs is not one you can route
  to on the strength of one run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from .models import CallRecord


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile: the value at position ceil(fraction * n).

    No interpolation, so the result is always a value that actually occurred.
    With five samples, p95 is the largest one; with twenty, the second largest.
    Returns 0.0 for an empty list so a report row can still render.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, int(round(fraction * len(ordered) + 0.5)))
    return ordered[min(rank, len(ordered)) - 1]


def time_per_output_token_s(record: CallRecord) -> float | None:
    """TPOT = (total latency - time to first output) / output tokens.

    None if nothing was generated. Uses first *output* (reasoning included),
    not first *visible* token, so a reasoning model's hidden tokens are not
    credited as instantaneous.
    """
    if record.output_tokens <= 0:
        return None
    decode_time = record.total_latency_s - record.time_to_first_output_s
    return max(decode_time, 0.0) / record.output_tokens


def tokens_per_second_per_user(record: CallRecord) -> float | None:
    """Output tokens / decode time for one stream. None if nothing was generated."""
    tpot = time_per_output_token_s(record)
    if tpot is None or tpot == 0:
        return None
    return 1.0 / tpot


@dataclass
class Summary:
    """The aggregate numbers for one (model, provider) cell of the bake-off."""

    model: str
    provider: str
    calls: int
    errors: int
    trajectories: int
    gate_pass_rate: float
    ttft_p50_s: float
    ttft_p95_s: float
    tpot_p50_s: float
    tpot_p95_s: float
    e2e_p50_s: float
    e2e_p95_s: float
    tokens_per_s_per_user_p50: float
    input_tokens_p50: float
    output_tokens_p50: float
    cost_total_usd: float | None
    cost_per_task_usd: float | None
    cost_per_correct_call_usd: float | None
    consistency: float | None
    notes: list[str] = field(default_factory=list)


def cost_per_correct_call(records: list[CallRecord]) -> float | None:
    """Total cost / passed calls. None when cost is unknown or nothing passed."""
    costs = [r.cost_usd for r in records if r.cost_usd is not None]
    if not costs:
        return None
    passed = sum(1 for r in records if r.passed)
    if passed == 0:
        return None
    return sum(costs) / passed


def consistency(records: list[CallRecord]) -> float | None:
    """Fraction of (trajectory, turn) pairs whose gate result agrees across runs.

    Only defined when at least two runs exist. A pair counts as consistent
    when every run gave the same pass/fail answer.
    """
    by_turn: dict[tuple[str, int], set[bool]] = {}
    runs_seen: set[int] = set()
    for record in records:
        if record.error:
            continue
        runs_seen.add(record.run)
        by_turn.setdefault((record.trajectory_id, record.turn_index), set()).add(record.passed)
    if len(runs_seen) < 2 or not by_turn:
        return None
    agreeing = sum(1 for outcomes in by_turn.values() if len(outcomes) == 1)
    return agreeing / len(by_turn)


def summarise(records: list[CallRecord]) -> Summary:
    """Reduce one cell's records to a Summary. Errored calls count as failed and
    are excluded from timing percentiles, because a timeout is not a latency."""
    if not records:
        raise ValueError("summarise() needs at least one record")
    ok = [r for r in records if not r.error]
    passed = sum(1 for r in ok if r.passed)
    tpots = [t for t in (time_per_output_token_s(r) for r in ok) if t is not None]
    rates = [t for t in (tokens_per_second_per_user(r) for r in ok) if t is not None]

    costs = [r.cost_usd for r in records if r.cost_usd is not None]
    cost_total = sum(costs) if costs else None
    trajectory_ids = {r.trajectory_id for r in records}

    notes: list[str] = []
    if cost_total is None:
        notes.append("endpoint reported no cost; cost columns are blank")
    if len(records) - len(ok):
        notes.append(f"{len(records) - len(ok)} call(s) errored and count as failed")
    # A reasoning model that thinks past max_tokens produces no visible answer.
    # That is a configuration problem (raise --max-tokens or set --reasoning off),
    # not a model verdict, so it is called out rather than silently scored as wrong.
    starved = sum(
        1
        for r in ok
        if r.extra.get("finish_reason") == "length" and not r.output_text.strip()
    )
    fell_back = sum(1 for r in ok if "refused" in str(r.extra.get("reasoning_used", "")))
    if fell_back:
        notes.append(
            f"{fell_back} call(s) ran at reasoning effort low because the endpoint refused "
            "to disable reasoning; this row's latency and cost include reasoning tokens"
        )
    if starved:
        notes.append(
            f"{starved} call(s) hit max_tokens with no visible answer (reasoning consumed the "
            "budget); raise --max-tokens or use --reasoning off before trusting this row"
        )

    return Summary(
        model=records[0].model,
        provider=records[0].provider,
        calls=len(records),
        errors=len(records) - len(ok),
        trajectories=len(trajectory_ids),
        gate_pass_rate=passed / len(records),
        ttft_p50_s=percentile([r.time_to_first_token_s for r in ok], 0.50),
        ttft_p95_s=percentile([r.time_to_first_token_s for r in ok], 0.95),
        tpot_p50_s=percentile(tpots, 0.50),
        tpot_p95_s=percentile(tpots, 0.95),
        e2e_p50_s=percentile([r.total_latency_s for r in ok], 0.50),
        e2e_p95_s=percentile([r.total_latency_s for r in ok], 0.95),
        tokens_per_s_per_user_p50=percentile(rates, 0.50),
        input_tokens_p50=median([r.input_tokens for r in ok]) if ok else 0.0,
        output_tokens_p50=median([r.output_tokens for r in ok]) if ok else 0.0,
        cost_total_usd=cost_total,
        cost_per_task_usd=(cost_total / len(trajectory_ids)) if cost_total is not None else None,
        cost_per_correct_call_usd=cost_per_correct_call(records),
        consistency=consistency(records),
        notes=notes,
    )
