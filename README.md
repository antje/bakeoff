<img src="assets/logo.jpg" alt="bakeoff" width="120">

# bakeoff

**A bake-off for your agent.** Build an eval from your own workload, run it against any model on OpenRouter, decide by cost per correct call.

MLCommons just shipped agentic-inference benchmarks for MLPerf: recorded multi-turn trajectories replayed closed-loop, judge-free accuracy gates, TTFT and TPOT as percentiles, a Pareto of tokens per second per user against tokens per second per system. That is the right shape. It is also 613 trajectories, a submission process, and a membership. bakeoff keeps the shape and drops the ceremony: your agent's last 20 to 50 conversations, any model on OpenRouter, an afternoon.

Two things come out of it:

| | What it does | Where it runs |
|---|---|---|
| **The skills** | `/eval-build` turns your agent's logs into labelled trajectories and refuses to proceed without enough of them. `/bakeoff` runs the harness and refuses to report a number without its conditions. Both teach as they go: concept, why it matters, an example, then your turn. | Claude Code, in your own repo |
| **The harness** | Closed-loop replay against OpenAI-compatible endpoints, deterministic accuracy gates, TTFT/TPOT/cost percentiles, a routing verdict, a conditions block. | `uv run python -m harness.bench` |

Same model, different silicon is one flag away: OpenRouter serves the same open weights on Cerebras, Groq, SambaNova, and NVIDIA-backed providers, and `--providers` picks which. The numbers are endpoint-level and say so.

## Quick start (five minutes, about $0.05)

```bash
git clone https://github.com/antje/bakeoff && cd bakeoff
cp .env.example .env            # add OPENROUTER_API_KEY
uv sync
./setup                         # symlinks the skills into ~/.claude/skills/

# Run the worked example: 5 trajectories, one model
uv run python -m harness.bench \
  --trajectories examples/product-coach/trajectories.jsonl \
  --models openai/gpt-oss-120b --limit 5 --max-tokens 400
```

Then, in Claude Code inside your own repo: `/eval-build` (type `demo` at any prompt to load the worked example), then `/bakeoff`.

## What a result looks like

Three models on the worked example, 20 trajectories × 3 turns, replayed twice, concurrency 1 to 2 (full report with conditions: [`examples/product-coach/results-sample.md`](examples/product-coach/results-sample.md)):

| model | gate | TTFT p50 | TTFT p95 | $/task | $/correct | consistency |
|---|---|---|---|---|---|---|
| openai/gpt-oss-120b | 68% | 1.73s | 10.03s | $0.0006 | $0.0002 | 72% |
| qwen/qwen3.6-35b-a3b | 57% | 0.45s | 1.42s | $0.0014 | $0.0004 | 83% |
| anthropic/claude-sonnet-5 | 68% | 1.48s | 1.98s | $0.0353 | $0.0086 | 97% |

The verdict picks gpt-oss on cost per correct call. The table shows why you might argue: a 10-second p95 tail and 72% consistency against Sonnet's 2 seconds and 97%. That argument is the point of the table.

Same model, four silicon types ([`results-silicon-sample.md`](examples/product-coach/results-silicon-sample.md)):

| provider | silicon | quantization | gate | TTFT p50 | tok/s/user | $/correct |
|---|---|---|---|---|---|---|
| cerebras | wafer-scale | fp16 | 68% | 0.36s | 1428 | $0.0011 |
| sambanova | RDU | unknown | 67% | 0.43s | 1102 | $0.0005 |
| groq | LPU | unknown | 78% | 0.50s | 480 | $0.0003 |
| together | NVIDIA GPU | unknown | 77% | 0.67s | 251 | $0.0004 |

Endpoint-level numbers on one date at concurrency 2. A provider's result is its serving stack, its hardware, and the network in between. Nothing here is a chip-level measurement.

## Layout

```
skills/eval-build/   the eval coach          harness/models.py    data shapes, JSONL
skills/bakeoff/      the benchmark coach     harness/replay.py    closed-loop replay, streaming timings
examples/            the worked example      harness/gate.py      deterministic pass/fail
docs/                MLPerf mapping          harness/metrics.py   every formula, once
bench/               your evals and results  harness/report.py    conditions block, table, verdict
scripts/             skill linter, converter harness/estimate.py  price before you run
                                             harness/bench.py     the CLI
```

Every module opens with what it does, why it exists, and where it sits. `uv run pytest` covers the gate, the metrics, and the replay loop with a fake client. `node scripts/check-skills.mjs` enforces the skill contract.

## Things the harness learned the hard way

- Reasoning models spend output tokens thinking before they answer. Uncapped, they can hit `max_tokens` with no visible answer. `--reasoning low` caps most of them; some (Qwen3.6) need `--reasoning off`; some (gpt-oss-120b) refuse to disable it, so `off` falls back to `low` and the report says so.
- New OpenRouter accounts are limited to 20 requests per minute on some models. The harness backs off on 429 rather than failing the turn.
- TPOT is measured from the first token of any kind, reasoning included, because the provider bills those tokens. TTFT is measured from the first token a user can see.
- Cost comes from the provider's own `usage.cost` in the final streamed chunk, never from a price table.

## Status

Working end to end on the worked example. Not yet: the LLM-judge option, a chart, a second example scenario, a `--local` run against vLLM (the code path exists; untested).
