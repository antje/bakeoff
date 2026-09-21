"""The command line: `uv run python -m harness.bench ...`

Where this sits: the entry point. It loads trajectories, builds the list of
targets (model × provider), estimates the cost and checks the budget, replays
everything, and writes the report. Every other module does one job; this one
strings them together in the order a developer would do it by hand.

Typical runs:

    # Three models, unpinned provider, one pass, single stream:
    uv run python -m harness.bench --trajectories bench/trajectories.jsonl \\
        --models openai/gpt-oss-120b,qwen/qwen3.6-35b-a3b,anthropic/claude-sonnet-5

    # Let the harness propose the three from the catalog: cheapest that can run
    # your workload, the model you ship, and one in between on a log-price line:
    uv run python -m harness.bench --trajectories bench/trajectories.jsonl \\
        --models auto --ceiling anthropic/claude-sonnet-5

    # Same model, four silicon types:
    uv run python -m harness.bench --trajectories bench/trajectories.jsonl \\
        --models openai/gpt-oss-120b --providers cerebras,groq,sambanova,together

    # Quick live demo on five trajectories, twice, to see consistency:
    uv run python -m harness.bench --trajectories examples/product-coach/trajectories.jsonl \\
        --models openai/gpt-oss-120b --limit 5 --runs 2

    # A tool-calling agent: schemas and recorded tool results travel in the JSONL:
    uv run python -m harness.bench --trajectories examples/tool-router/trajectories.jsonl \\
        --models openai/gpt-oss-120b,anthropic/claude-sonnet-5 --max-tokens 200

    # The eval has a latency budget and every miss costs money: only cells under
    # 2 s TTFT p95 and at the best gate rate can win, and the report says why:
    uv run python -m harness.bench --trajectories bench/trajectories.jsonl \\
        --models auto --ceiling anthropic/claude-sonnet-5 --ttft-budget 2 --tolerance 0

    # Your own vLLM server:
    LOCAL_BASE_URL=http://localhost:8000/v1 uv run python -m harness.bench \\
        --trajectories bench/trajectories.jsonl --models my-model --local

Concurrency defaults to 1, meaning one trajectory in flight at a time. That
is the single-stream setup MLPerf's edge agentic benchmark uses and the one
that gives clean per-user latency numbers. Raise it to see how an endpoint
behaves under load; the report records whichever you chose.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from .candidates import describe, fetch_catalog, qualify, requirements, shortlist
from .client import OPENROUTER_BASE_URL, Target, endpoint_info, find_endpoint, make_client
from .estimate import estimate_run, over_budget
from .models import CallRecord, Trajectory, load_trajectories
from .replay import replay_trajectory
from .report import RunConditions, harness_commit, write_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bakeoff",
        description="Replay your agent's trajectories against models and providers; "
        "report accuracy, latency percentiles, and cost per correct call.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Typical runs:")[1],
    )
    parser.add_argument("--trajectories", type=Path, required=True, help="JSONL from /eval-build")
    parser.add_argument(
        "--models",
        required=True,
        help="comma-separated model ids, or 'auto' to shortlist three from the OpenRouter catalog "
        "(cheapest that can run the workload, the model you ship, one in between)",
    )
    parser.add_argument(
        "--ceiling",
        default=None,
        help="with --models auto: the model you ship today, used as the top of the price line",
    )
    parser.add_argument(
        "--providers",
        default="auto",
        help="comma-separated OpenRouter provider slugs to pin, or 'auto' (default). "
        "Each model is run once per provider.",
    )
    parser.add_argument("--concurrency", type=int, default=1, help="trajectories in flight (default 1)")
    parser.add_argument("--runs", type=int, default=1, help="replay each trajectory this many times")
    parser.add_argument("--limit", type=int, default=None, help="only the first N trajectories")
    parser.add_argument("--max-tokens", type=int, default=1024, help="output cap per turn")
    parser.add_argument(
        "--reasoning",
        choices=["off", "none", "low", "medium", "high"],
        default="low",
        help="thinking budget for reasoning models (default low; recorded in the conditions block). "
        "Use off for models that ignore effort and think past max_tokens.",
    )
    parser.add_argument(
        "--ttft-budget",
        type=float,
        default=None,
        help="p95 time to first token, in seconds, a cell must meet to be a contender in the verdict "
        "(from your eval description's latency budget; recorded in the conditions block)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="how far below the best gate rate a cell can be and still be a contender in the verdict "
        "(default 0.05; use 0 when every miss is expensive, e.g. a wrong refund; "
        "recorded in the conditions block)",
    )
    parser.add_argument("--local", action="store_true", help="use LOCAL_BASE_URL instead of OpenRouter")
    parser.add_argument("--out", type=Path, default=Path("bench"), help="where results-* go")
    parser.add_argument("--yes", action="store_true", help="skip the cost confirmation prompt")
    return parser.parse_args(argv)


def build_targets(models: str, providers: str, local: bool) -> list[Target]:
    """Every model crossed with every provider; local runs ignore providers."""
    model_ids = [m.strip() for m in models.split(",") if m.strip()]
    if local:
        import os

        base = os.environ.get("LOCAL_BASE_URL", "").rstrip("/")
        if not base:
            raise SystemExit("--local needs LOCAL_BASE_URL in the environment")
        return [Target(model=m, provider="local", base_url=base) for m in model_ids]
    provider_ids = [p.strip() for p in providers.split(",") if p.strip()] or ["auto"]
    return [Target(model=m, provider=p) for m in model_ids for p in provider_ids]


def run_all(
    targets: list[Target],
    trajectories: list[Trajectory],
    runs: int,
    concurrency: int,
    max_tokens: int,
    reasoning: str,
) -> list[CallRecord]:
    """Replay every (target, trajectory, run), at most `concurrency` trajectories at once.

    One client per distinct base_url. Progress prints one line per finished
    trajectory so a live audience can see it moving.
    """
    clients = {t.base_url: make_client(t.base_url) for t in targets}
    jobs = [(t, tr, r) for t in targets for r in range(1, runs + 1) for tr in trajectories]
    records: list[CallRecord] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {
            pool.submit(replay_trajectory, clients[t.base_url], t, tr, r, max_tokens, reasoning): (t, tr, r)
            for t, tr, r in jobs
        }
        done = 0
        for future in as_completed(futures):
            target, trajectory, run = futures[future]
            batch = future.result()
            records.extend(batch)
            done += 1
            passed = sum(1 for rec in batch if rec.passed)
            errors = sum(1 for rec in batch if rec.error)
            print(
                f"[{done}/{len(jobs)}] {target.label} run{run} {trajectory.trajectory_id}: "
                f"{passed}/{len(batch)} passed"
                + (f", {errors} error(s)" if errors else ""),
                flush=True,
            )
    return records


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    all_trajectories = load_trajectories(args.trajectories)
    trajectories = all_trajectories[: args.limit] if args.limit else all_trajectories
    if not trajectories:
        print("no trajectories to run", file=sys.stderr)
        return 2
    models = args.models
    if models.strip() == "auto":
        if args.local:
            print("--models auto needs the OpenRouter catalog; name the model with --local", file=sys.stderr)
            return 2
        # Shortlist on the whole file, so --limit changes the run, not the candidates.
        req = requirements(all_trajectories, args.max_tokens)
        catalog = fetch_catalog()
        if not catalog:
            print("could not fetch the OpenRouter catalog; pass --models <ids>", file=sys.stderr)
            return 2
        try:
            picks = shortlist(qualify(catalog, req), args.ceiling)
        except ValueError as err:
            print(f"{err}; pass --models <ids>", file=sys.stderr)
            return 2
        print(describe(req, picks))
        print()
        models = ",".join(picks.models)
    targets = build_targets(models, args.providers, args.local)

    # Price it first. A bake-off should never surprise anyone on the invoice.
    estimates = estimate_run(trajectories, targets, args.runs, args.max_tokens)
    print("Estimated (upper bound):")
    for e in estimates:
        cost = "no public price" if e.usd is None else f"~${e.usd:.4f}"
        print(f"  {e.target_label}: {e.calls} calls, {cost}")
    too_much, total = over_budget(estimates)
    if too_much:
        print(f"Refusing: estimated ${total:.2f} exceeds BAKEOFF_MAX_RUN_USD. Lower --limit, "
              f"--runs, or --max-tokens, or raise the ceiling on purpose.", file=sys.stderr)
        return 3
    if not args.yes and sys.stdin.isatty():
        answer = input(f"Proceed with ~${total:.4f}? [y/N] ").strip().lower()
        if answer != "y":
            return 1

    records = run_all(
        targets, trajectories, args.runs, args.concurrency, args.max_tokens, args.reasoning
    )

    # Endpoint facts for the conditions block, looked up once per model.
    endpoints: dict[tuple[str, str], object] = {}
    for target in targets:
        infos = endpoint_info(target.model) if not args.local else []
        endpoints[(target.model, target.provider)] = (
            find_endpoint(infos, target.provider) if target.provider not in ("auto", "local") else None
        )

    ok = [r for r in records if not r.error]
    conditions = RunConditions(
        date_utc=datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
        trajectories=len(trajectories),
        turns_per_trajectory_p50=statistics.median(t.turn_count for t in trajectories),
        concurrency=args.concurrency,
        runs=args.runs,
        max_tokens=args.max_tokens,
        warm_or_cold="cold",
        input_tokens_p50=statistics.median(r.input_tokens for r in ok) if ok else 0,
        output_tokens_p50=statistics.median(r.output_tokens for r in ok) if ok else 0,
        harness_commit=harness_commit(),
        endpoint="local" if args.local else OPENROUTER_BASE_URL,
        judged=False,
        reasoning=args.reasoning,
        ttft_budget_s=args.ttft_budget,
        tolerance=args.tolerance,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    json_path, md_path, summaries = write_report(
        args.out, records, conditions, targets, endpoints, trajectories
    )

    print()
    print(md_path.read_text())
    print(f"Wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
