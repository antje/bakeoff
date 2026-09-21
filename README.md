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

Then, in Claude Code inside your own repo: `/eval-build` (type `demo` at any prompt to load the worked example, or `demo ticket-triage`, `demo contract-extract`, `demo tool-router`, `demo ledger-audit`, `demo code-fix` for another shape), then `/bakeoff`.

Not sure which models to try? `--models auto --ceiling <the model you ship>` reads the requirements off your trajectories (tool calls, context), drops every catalog model that cannot meet them, prices the rest on your workload, and proposes three points on a log-price line: the cheapest that qualifies, the one you ship, and one in between. The gate decides; the price only picks the candidates.

## What a result looks like

Three models on the worked example, 20 trajectories × 3 turns, replayed twice, concurrency 1 to 2 (full report with conditions: [`examples/product-coach/results-sample.md`](examples/product-coach/results-sample.md)):

| model | gate | TTFT p50 | TTFT p95 | $/task | $/correct | consistency |
|---|---|---|---|---|---|---|
| *trivial baseline* | 48% | | | | | |
| openai/gpt-oss-120b | 60% | 1.25s | 4.65s | $0.0007 | $0.0002 | 70% |
| qwen/qwen3.6-35b-a3b | 46% | 0.78s | 1.63s | $0.0014 | $0.0005 | 85% |
| anthropic/claude-sonnet-5 | 62% | 1.57s | 2.24s | $0.0352 | $0.0095 | 90% |

The verdict picks gpt-oss on cost per correct call: two points behind Sonnet at a 48th of the price. Qwen lands below the trivial baseline (the best constant answer per turn), so it is not a contender at any price. The table shows why you might still argue: a 5-second p95 tail and 70% consistency against Sonnet's 2 seconds and 90%. That argument is the point of the table.

Same model, four silicon types ([`results-silicon-sample.md`](examples/product-coach/results-silicon-sample.md)):

| provider | silicon | quantization | gate | TTFT p50 | tok/s/user | $/correct |
|---|---|---|---|---|---|---|
| cerebras | wafer-scale | fp16 | 63% | 0.33s | 1612 | $0.0012 |
| sambanova | RDU | unknown | 52% | 0.43s | 1230 | $0.0007 |
| groq | LPU | unknown | 45% | 0.40s | 483 | $0.0005 |
| together | NVIDIA GPU | unknown | 52% | 0.85s | 154 | $0.0006 |

Endpoint-level numbers on one date at concurrency 2. A provider's result is its serving stack, its hardware, and the network in between. Nothing here is a chip-level measurement.

## Which shape, which winner

The same four models on six workloads, twice each ([`examples/README.md`](examples/README.md) has the table with the use cases; each directory has the full report):

| workload | shape | verdict | what decided it |
|---|---|---|---|
| `ticket-triage` | ~300 tokens in, one word out | gpt-oss-20b | price: 70x cheaper per correct call than Sonnet at the same 98 to 100% gate |
| `contract-extract` | 4,500-token prefill, ten tokens out | gpt-oss-120b | the 2 s TTFT budget (`--ttft-budget 2`): the cheaper 20b takes 4.5 s at p95 |
| `tool-router` | tool schemas, exact arguments carried from earlier tool results | gpt-oss-120b | fidelity: 98% and fully consistent, against 84 to 86% for the smaller models |
| `ledger-audit` | six dependent turns of postings, reversals, and balances | claude-sonnet-5 | accuracy: 85% against 69 to 72% for gpt-oss and 14% for Qwen3.6; the only cell within tolerance of the best, at 20x the price per correct call of the triage winner |
| `code-fix` | a function, its failing test, and the CI line in; the corrected function out, then a trace of it | gpt-oss-20b | price: 96% against 98% for the 120b and 97% for Sonnet, all within tolerance, at 68x below Sonnet per correct call |
| `product-coach` | ~2K-token history, three short answers | gpt-oss-120b | price, narrowly: the baseline row is 48% and the models land at 46 to 62%, so this eval separates them by a few points at most |

The verdict is computed the same way every time: the cheapest cell, by cost per correct call, among those within 5 points of the best gate rate, above the trivial baseline, and inside the latency budget if one was given. What changes between rows is the workload.

## Layout

```
skills/eval-build/   the eval coach          harness/models.py    data shapes, JSONL
skills/bakeoff/      the benchmark coach     harness/replay.py    closed-loop replay, streaming timings
examples/            six worked examples     harness/gate.py      deterministic pass/fail
docs/                MLPerf mapping          harness/metrics.py   every formula, once
bench/               your evals and results  harness/report.py    conditions block, table, verdict
scripts/             skill linter, example   harness/estimate.py  price before you run
                     generators              harness/candidates.py --models auto shortlist
tests/               pytest                  harness/bench.py     the CLI
DESIGN.md, assets/   the mark and the rules
```

Every module opens with what it does, why it exists, and where it sits. `uv run pytest` covers the gate, the metrics, the estimate, the candidate shortlist, the replay loop with a fake client, and every example generator against its committed files. `node scripts/check-skills.mjs` enforces the skill contract.

## Things the harness learned the hard way

- Reasoning models spend output tokens thinking before they answer. Uncapped, they can hit `max_tokens` with no visible answer. `--reasoning low` caps most of them; some (Qwen3.6) need `--reasoning off`; some (gpt-oss-120b) refuse to disable it, so `off` falls back to `low` and the report says so.
- New OpenRouter accounts are limited to 20 requests per minute on some models. The harness backs off on 429 rather than failing the turn.
- TPOT is measured from the first token of any kind, reasoning included, because the provider bills those tokens. TTFT is measured from the first token a user can see.
- Cost comes from the provider's own `usage.cost` in the final streamed chunk, never from a price table.
- A cheap model that is right can still be the wrong answer: on the long-document eval the cheapest cell had a 4.5 s p95 TTFT against a 2 s budget. `--ttft-budget` puts the budget into the verdict and the report names the cells it dropped.
- The trivial baseline (what a constant answer per turn scores) goes above the model rows. On the original example it is 48%, a few points under the best models and above one of them; the newer examples were built so it is 0 to 19%. It also found a broken gate: the original citation check accepted any id from the history, a constant `ex-001` scored 73%, and the gate was rewritten to demand a precedent that supports the call. A gate a constant can pass is not a gate.
- Five points of gate tolerance is a default, not a law. On the tool-router eval 98% and 100% are two wrong refunds in a hundred; `--tolerance 0` makes the verdict say so, and the report records whichever you chose.
- Tool calling is a serving-stack feature as much as a model feature. Trajectories carry the tool schemas and the recorded tool results; replay feeds them back so every model sees the same world, and a provider that refuses `tools` shows up as a note, not a silent zero.

## Status

Working end to end on six worked examples, tool calling included. Not yet: pruning candidates by eval (run the shortlist on five trajectories, drop what fails the gate, run survivors on everything), the LLM-judge option, confidence intervals on the gate rate, a chart, a `--local` run against vLLM (the code path exists; untested).
