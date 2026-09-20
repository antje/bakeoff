"""Price a run before it starts, and refuse if it would blow the budget.

Where this sits: `bench.py` calls `estimate_run()` after loading trajectories
and targets, prints the estimate, and stops if it exceeds BAKEOFF_MAX_RUN_USD.

Why estimate at all. A bake-off is a loop over trajectories × turns × models ×
providers × runs. Each factor is small; the product is not. Twenty trajectories
of five turns across four providers, twice, is 800 calls. With growing history
the later turns are the expensive ones. A developer should see "about $2.40"
before the first request, not "$41" on next month's invoice.

How it is estimated. Input tokens for turn k are roughly the sum of all
earlier inputs plus earlier outputs (that is what closed-loop replay sends).
We approximate tokens as characters / 4, assume `max_tokens` per output as
the ceiling, and multiply by the provider's per-token prices from the
endpoints API. It is an upper bound, and the report says "estimated".
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .client import Target, endpoint_info, find_endpoint
from .models import Trajectory

CHARS_PER_TOKEN = 4  # a coarse English average; good enough for an upper bound


@dataclass
class Estimate:
    """One target's estimated calls, tokens, and dollars for a run."""

    target_label: str
    calls: int
    input_tokens: int
    output_tokens: int
    usd: float | None  # None when the endpoint has no public price (local servers)


def estimate_tokens(trajectories: list[Trajectory], max_tokens: int) -> tuple[int, int, int]:
    """Return (calls, input_tokens, output_tokens) for one pass over the trajectories.

    Models the growing history: turn k's input includes every earlier input and
    every earlier (assumed max-length) output.
    """
    calls = 0
    input_tokens = 0
    output_tokens = 0
    for trajectory in trajectories:
        history_tokens = len(trajectory.system or "") // CHARS_PER_TOKEN
        for turn in trajectory.turns:
            history_tokens += len(turn.input) // CHARS_PER_TOKEN
            input_tokens += history_tokens
            output_tokens += max_tokens
            history_tokens += max_tokens  # the answer joins the history for the next turn
            calls += 1
    return calls, input_tokens, output_tokens


def estimate_run(
    trajectories: list[Trajectory], targets: list[Target], runs: int, max_tokens: int
) -> list[Estimate]:
    """Estimate cost per target, looking up live prices from OpenRouter."""
    calls, input_tokens, output_tokens = estimate_tokens(trajectories, max_tokens)
    estimates: list[Estimate] = []
    price_cache: dict[str, list] = {}
    for target in targets:
        usd: float | None = None
        if target.provider != "local":
            if target.model not in price_cache:
                price_cache[target.model] = endpoint_info(target.model)
            infos = price_cache[target.model]
            chosen = find_endpoint(infos, target.provider) if target.provider != "auto" else None
            if chosen is None and infos:
                # Unpinned: assume the most expensive listed endpoint, to stay an upper bound.
                chosen = max(infos, key=lambda i: i.prompt_price_per_token + i.completion_price_per_token)
            if chosen is not None:
                usd = runs * (
                    input_tokens * chosen.prompt_price_per_token
                    + output_tokens * chosen.completion_price_per_token
                )
        estimates.append(
            Estimate(
                target_label=target.label,
                calls=calls * runs,
                input_tokens=input_tokens * runs,
                output_tokens=output_tokens * runs,
                usd=usd,
            )
        )
    return estimates


def budget_usd() -> float:
    """The spend ceiling from BAKEOFF_MAX_RUN_USD, defaulting to $5."""
    try:
        return float(os.environ.get("BAKEOFF_MAX_RUN_USD", "5"))
    except ValueError:
        return 5.0


def over_budget(estimates: list[Estimate]) -> tuple[bool, float]:
    """Return (True, total) if the priced estimates exceed the ceiling."""
    total = sum(e.usd for e in estimates if e.usd is not None)
    return total > budget_usd(), total
