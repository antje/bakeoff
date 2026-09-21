# Five workload shapes, one roster, different verdicts

Every example here was run against the same four models (`openai/gpt-oss-20b`,
`openai/gpt-oss-120b`, `qwen/qwen3.6-35b-a3b`, `anthropic/claude-sonnet-5`), twice, on one
evening in September 2026, through OpenRouter. The verdict moved with the shape of the
workload, not with the size of the model. That is the whole argument for building the eval
from your own step instead of reading a leaderboard.

Load any of them in `/eval-build` or `/bakeoff` by typing `demo <name>` at a prompt; bare
`demo` loads `product-coach`.

| example | the use case, in one line | shape | gate | verdict | what decided it |
|---|---|---|---|---|---|
| [`ticket-triage`](ticket-triage/) | a help desk routes 2,000 tickets a day to eight queues; nobody waits, the bill does | ~300 tokens in, one word out, 2 turns | label | **gpt-oss-20b**, 98% | price: 70x cheaper per correct call than Sonnet at the same gate |
| [`contract-extract`](contract-extract/) | a buyer asks a 4,500-token contract one question while watching a spinner | long prefill, ten tokens out, 3 turns | pattern | **gpt-oss-120b**, 100% | the 2 s TTFT p95 budget: the cheaper 20b takes 4.5 s at p95 and is not a contender |
| [`tool-router`](tool-router/) | a support copilot turns "refund her, it arrived damaged" into exact API calls with ids from earlier tool results | schemas plus growing history, one call out, 3 turns | tool_call | **gpt-oss-120b**, 98%, 100% consistent | fidelity: 20b and Qwen3.6 drop to 84 to 86%, and a wrong argument is a wrong refund |
| [`ledger-audit`](ledger-audit/) | a finance assistant carries balances through six batches of postings and reversals | 6 dependent turns, context to ~2.5K, arithmetic, reasoning on | pattern | **claude-sonnet-5**, 85% | accuracy: gpt-oss lands at 69 to 72% and Qwen3.6 at 14%, so Sonnet is the only contender; its $0.0040 per correct call is the price of being right |
| [`product-coach`](product-coach/) | a product coach decides whether to object to an experiment brief from the team's history | ~2K-token history, three short answers | label, pattern | gpt-oss-120b, 60% | price, narrowly: the baseline row is 48%, Sonnet is 62%, and Qwen at 46% is under it; read the gap, not the rank |

Each directory has the same five files: `scenario.md` (the use case and the step as an
inference workload), `logs.jsonl` (what a developer has before `/eval-build`),
`trajectories.jsonl` (what `/eval-build` produces), `eval.md` (the finished eval
description), `answers.md` (the interview answers `demo <name>` loads), and
`results-sample.md` (a real report, conditions block included).

## What to notice

- **Four shapes, four different winners, on the same roster.** The 20B model wins triage
  on price; the 120B wins extraction on the latency budget and tool routing on fidelity; the
  frontier model wins the ledger because nothing cheaper is right often enough. Nothing about
  the models changed between rows.
- **Reasoning budgets are conditions too.** On `ledger-audit` at `--reasoning medium` and
  1,200 output tokens, a third of gpt-oss calls and nearly all Qwen3.6 calls hit the token
  cap while still thinking and returned nothing; the report's notes say so on each row. A
  bigger budget is a different experiment, and a fair one to run next.
- **The latency budget is a condition, not a footnote.** On `contract-extract` the verdict
  flips when the eval's 2 s TTFT budget is applied (`--ttft-budget 2`): the report names the
  cells that were dropped for it, and the same numbers without the budget pick the slower
  model. Both reports are honest; only one answers the buyer's question.
- **The baseline row is the zero of the gate column.** `product-coach` is kept here as the
  narrow case: a constant answer scores 48%, the best models 60 to 62%, and one model lands
  under the constant. Its verdict rests on a few points. The four new evals have baselines of
  19%, 0%, 0%, and 0%.
- **Reasoning settings are part of the shape.** At `--reasoning low`, Qwen3.6 spends its
  whole output budget thinking on short-answer tasks and returns nothing; `off` fixes it, and
  gpt-oss refuses `off` and falls back to `low` with a note. `ledger-audit` runs at `medium`
  on purpose. Every report records which.

## Regenerating

Each dataset comes from a deterministic generator under `scripts/examples/`; run it and the
files come back byte-identical. `tests/test_examples.py` checks that, and that the committed
files match. Ground truth is known by construction (planted facts, a reference ledger,
approved tool calls), so the honest caveat on every one of these is the same as on
`product-coach`: they test whether a model handles the shape, not whether it knows the
domain.
