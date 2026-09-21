"""Propose which models to bake off, from the workload and the OpenRouter catalog.

Where this sits: `bench.py` calls `shortlist()` when `--models auto` is given,
before estimating cost. `/bakeoff` step 1 offers `auto` as an answer to
"which models?". Nothing here runs a model; that is the bake-off's job.

What it does. A bake-off decides between candidates; it cannot find them,
because a model has to run before its pass rate exists. What can be known
before any run is the hard requirements the trajectories impose, and what the
catalog says each model supports and charges. So:

1. Read the requirements off the trajectories: does the agent call tools (the
   model must accept a `tools` parameter), and how much context will the
   longest trajectory reach by its last turn.
2. Drop every catalog entry that cannot meet them, plus the free tiers (rate
   limited, unstable, and not what anyone ships), the `openrouter/` router
   pseudo-models, and the `:variant` aliases of a base model.
3. Price each survivor on this workload's own token mix, not on a blended
   list price, because an agent with long histories is input-heavy and a
   summariser is output-heavy.
4. Pick three points on a log-price line: the **floor** (cheapest qualifying),
   the **ceiling** (the model you ship, passed in; otherwise the priciest
   qualifying), and the **middle** (closest to the geometric mean of the two).
   Three points make a line; the skill explains why.

Easy to get wrong: treating the floor as a recommendation. It is the cheapest
model that *could* work; the gate decides whether it does. A tiny model that
fails the gate is the bake-off working as intended, not the shortlist failing.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import httpx

from .client import OPENROUTER_BASE_URL
from .estimate import CHARS_PER_TOKEN, estimate_tokens
from .models import Trajectory

CONTEXT_HEADROOM = 1.2  # the token estimate is rough; ask for 20% more than it says


@dataclass
class Requirements:
    """What any candidate must support, read off the trajectories."""

    needs_tools: bool
    context_tokens: int  # the longest history any trajectory reaches, with headroom
    input_tokens: int  # one pass over the workload, for pricing candidates on it
    output_tokens: int


@dataclass
class Candidate:
    """One catalog model that meets the requirements, priced on this workload."""

    model: str
    name: str
    context_length: int
    prompt_price_per_token: float
    completion_price_per_token: float
    supports_tools: bool
    run_usd: float  # estimated cost of one pass over the workload, upper bound

    @property
    def prompt_price_per_million(self) -> float:
        return self.prompt_price_per_token * 1_000_000

    @property
    def completion_price_per_million(self) -> float:
        return self.completion_price_per_token * 1_000_000


@dataclass
class Shortlist:
    """The three points, with why each was picked, and how many models qualified."""

    floor: Candidate
    middle: Candidate
    ceiling: Candidate
    qualifying: int
    reasons: dict[str, str]

    @property
    def models(self) -> list[str]:
        ids = [self.floor.model, self.middle.model, self.ceiling.model]
        return list(dict.fromkeys(ids))  # de-duplicate, keep order


def requirements(trajectories: list[Trajectory], max_tokens: int) -> Requirements:
    """Read the hard requirements off the trajectories.

    Context is the largest history any single trajectory reaches at its last
    turn, plus that turn's output cap, using the same growing-history model
    as the cost estimate.
    """
    needs_tools = any(t.has_tools for t in trajectories)
    longest = 0
    for trajectory in trajectories:
        history = len(trajectory.system or "") // CHARS_PER_TOKEN
        if trajectory.tools:
            history += len(json.dumps(trajectory.tools)) // CHARS_PER_TOKEN
        for turn in trajectory.turns:
            history += len(turn.input) // CHARS_PER_TOKEN
            longest = max(longest, history + max_tokens)
            history += max_tokens
            if isinstance(turn.tool_result, str):
                history += len(turn.tool_result) // CHARS_PER_TOKEN
            elif isinstance(turn.tool_result, dict):
                history += sum(len(v) for v in turn.tool_result.values()) // CHARS_PER_TOKEN
    _, input_tokens, output_tokens = estimate_tokens(trajectories, max_tokens)
    return Requirements(
        needs_tools=needs_tools,
        context_tokens=math.ceil(longest * CONTEXT_HEADROOM),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def fetch_catalog() -> list[dict]:
    """Fetch OpenRouter's public model catalog. No key needed. Empty list when offline."""
    try:
        response = httpx.get(f"{OPENROUTER_BASE_URL}/models", timeout=20.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return []
    return list(response.json().get("data", []))


def qualify(catalog: list[dict], req: Requirements) -> list[Candidate]:
    """Keep the catalog entries that can run this workload, priced on it, cheapest first."""
    out: list[Candidate] = []
    for entry in catalog:
        model = str(entry.get("id", ""))
        if not model or model.startswith("openrouter/") or ":" in model:
            continue
        architecture = entry.get("architecture") or {}
        if "text" not in (architecture.get("input_modalities") or ["text"]):
            continue
        if "text" not in (architecture.get("output_modalities") or ["text"]):
            continue
        pricing = entry.get("pricing") or {}
        try:
            prompt = float(pricing.get("prompt") or 0)
            completion = float(pricing.get("completion") or 0)
        except (TypeError, ValueError):
            continue
        if prompt <= 0 or completion <= 0:
            continue  # free tiers and unpriced entries
        context_length = entry.get("context_length")
        if not isinstance(context_length, int) or context_length < req.context_tokens:
            continue
        supports_tools = "tools" in (entry.get("supported_parameters") or [])
        if req.needs_tools and not supports_tools:
            continue
        out.append(
            Candidate(
                model=model,
                name=str(entry.get("name") or model),
                context_length=context_length,
                prompt_price_per_token=prompt,
                completion_price_per_token=completion,
                supports_tools=supports_tools,
                run_usd=req.input_tokens * prompt + req.output_tokens * completion,
            )
        )
    out.sort(key=lambda c: (c.run_usd, c.model))
    return out


def shortlist(candidates: list[Candidate], ceiling: str | None = None) -> Shortlist:
    """Pick floor, middle and ceiling from the qualifying candidates.

    `ceiling` is the model id you ship today, if you have one; the whole point
    of the bake-off is to see how far below it you can go. When it is not in
    the qualifying list (wrong id, or it cannot run the workload), that is
    reported as a reason and the priciest qualifying model stands in.
    """
    if not candidates:
        raise ValueError("no model in the catalog meets the workload's requirements")
    reasons: dict[str, str] = {}
    floor = candidates[0]
    reasons["floor"] = "cheapest model that meets the requirements"

    top = next((c for c in candidates if c.model == ceiling), None) if ceiling else None
    if top is None:
        top = candidates[-1]
        reasons["ceiling"] = (
            f"{ceiling} is not in the qualifying list; priciest qualifying model instead"
            if ceiling
            else "priciest qualifying model; pass --ceiling <the model you ship> for a better one"
        )
    else:
        reasons["ceiling"] = "the model you ship (--ceiling)"

    target = math.sqrt(max(floor.run_usd, 1e-12) * max(top.run_usd, 1e-12))
    between = [c for c in candidates if floor.run_usd < c.run_usd < top.run_usd and c.model != top.model]
    middle = min(between, key=lambda c: abs(math.log(c.run_usd) - math.log(target))) if between else top
    reasons["middle"] = (
        "closest to the geometric mean of floor and ceiling price"
        if between
        else "nothing priced between floor and ceiling; ceiling stands in"
    )
    return Shortlist(floor=floor, middle=middle, ceiling=top, qualifying=len(candidates), reasons=reasons)


def describe(req: Requirements, picks: Shortlist) -> str:
    """The shortlist as text for the terminal, with the requirements it came from."""
    lines = [
        "Requirements read from the trajectories:",
        f"  tools: {'required' if req.needs_tools else 'not used'}",
        f"  context: at least {req.context_tokens:,} tokens at the longest trajectory's last turn",
        f"  one pass: ~{req.input_tokens:,} input tokens, ~{req.output_tokens:,} output tokens (upper bound)",
        f"{picks.qualifying} models in the OpenRouter catalog qualify. Three points on the price line:",
    ]
    for role in ("floor", "middle", "ceiling"):
        c: Candidate = getattr(picks, role)
        lines.append(
            f"  {role:<8} {c.model:<40} ${c.prompt_price_per_million:.2f}/M in, "
            f"${c.completion_price_per_million:.2f}/M out, ~${c.run_usd:.4f} per pass"
        )
        lines.append(f"           {picks.reasons[role]}")
    lines.append("Edit with --models <ids> if you know better; the gate decides, not the price.")
    return "\n".join(lines)
