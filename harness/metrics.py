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
- **Trivial baseline**: the gate rate a constant answer per turn would get,
  computed from the trajectories alone before any model runs. It is the zero
  of the scale. A model at or under it has not read the input.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import median

from .gate import check_pattern
from .models import CallRecord, Trajectory


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
    rejected = sum(1 for r in records if r.extra.get("tools_rejected"))
    synthesised = sum(int(r.extra.get("synthesised_ids", 0) or 0) for r in ok)
    if rejected:
        notes.append(
            f"{rejected} call(s) were refused because this endpoint does not accept tool "
            "schemas for this model; tool_call gates cannot pass on this row"
        )
    if synthesised:
        notes.append(
            f"{synthesised} tool call(s) arrived without an id; ids were synthesised so the "
            "replay could continue"
        )
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


@dataclass
class Baseline:
    """What a constant answer per turn scores. `per_turn` maps turn index to
    (best constant answer, passes, turns at that index)."""

    rate: float
    per_turn: dict[int, tuple[str, int, int]]


_ALTERNATIVES = re.compile(r"\\b\(([^()]*)\)\\b")


def _pattern_candidates(pattern: str) -> list[str]:
    """Literal strings a constant answer could be, read off a `\\b(a|b|c)\\b` pattern.

    Anything more elaborate yields no candidates, and the turn counts as one
    a constant cannot pass. That understates the baseline for exotic patterns,
    never overstates it.
    """
    match = _ALTERNATIVES.search(pattern)
    if not match:
        return []
    return [re.sub(r"\\(.)", r"\1", alt) for alt in match.group(1).split("|") if alt]


def trivial_baseline(trajectories: list[Trajectory]) -> Baseline:
    """Per turn index, the single answer that passes the most trajectories.

    Label turns: the majority label. Pattern turns: the literal alternative
    that matches the most patterns (patterns with no literal alternatives
    count as unpassable). Tool-call turns: unpassable, since a constant call
    with constant arguments matches at most the trajectories that happen to
    share those arguments, and the harness does not credit that. The overall
    rate is the sum of per-turn best passes over the total number of turns,
    which is exactly how the model rows are scored.
    """
    per_turn: dict[int, tuple[str, int, int]] = {}
    total_turns = 0
    total_passes = 0
    max_turns = max((t.turn_count for t in trajectories), default=0)
    for index in range(max_turns):
        turns = [t.turns[index] for t in trajectories if index < t.turn_count]
        total_turns += len(turns)
        labels = Counter(t.expected.label.strip().lower() for t in turns if t.expected.label)
        best_answer, best_passes = "", 0
        if labels:
            best_answer, best_passes = labels.most_common(1)[0]
        candidates: set[str] = set()
        for turn in turns:
            if turn.expected.pattern:
                candidates.update(_pattern_candidates(turn.expected.pattern))
        for candidate in sorted(candidates):
            passes = sum(
                1 for t in turns if t.expected.pattern and check_pattern(t.expected.pattern, candidate)
            )
            if passes > best_passes:
                best_answer, best_passes = candidate, passes
        per_turn[index] = (best_answer, best_passes, len(turns))
        total_passes += best_passes
    rate = total_passes / total_turns if total_turns else 0.0
    return Baseline(rate=rate, per_turn=per_turn)
