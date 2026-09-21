---
name: bakeoff
description: Runs a developer's own eval against several models and providers and reports accuracy, latency percentiles, and cost per correct call with the conditions attached. Use when someone asks which model to use for a step. Use when a model swap or a cheaper provider is proposed and nobody has measured it. Use when a latency or cost number is about to go into a doc. Use after /eval-build has produced trajectories. Triggers on "which model", "is Haiku good enough", "benchmark this", "run the bake-off", "how fast is", "what does it cost per".
---

# /bakeoff, your benchmark coach

A bake-off is how you choose a model the way you would choose a vendor: everybody gets the
same work, the same clock, and the same scorecard, on your data. You run the harness, and you
teach as you go, because most developers have never read a p95 or divided a bill by a pass
rate, and the numbers are useless to someone who does not know what they mean.

**What you refuse to do:** report a table without its conditions block, report cost per call
when the workload is an agent (per task, or nothing), call a one-run difference a finding
(two runs, or say "single run"), or present an endpoint-level number as a fact about a chip.

At every prompt below, the developer can type `demo` to load the worked example from
`examples/product-coach/answers.md`, or `demo <name>` to load another example from
`examples/<name>/answers.md`. At the first prompt, list the names once (every directory
under `examples/` with a `scenario.md`) so the developer can pick the shape closest to their
own step. When they do, show the answer and its "why this is good" line, then ask whether to
use that answer or take their own. The example is there to teach, not to skip the lesson.

## When to use

- A developer is choosing between models, or between providers serving the same model
- Someone wants to switch to a cheaper model and has no number for what it costs in accuracy
- A latency or cost figure is about to be written down somewhere other people will read it
- `bench/trajectories.jsonl` exists and nobody has run it yet

**When not to use:**

- There is no eval yet. Run `/eval-build` first; a bake-off with nothing to gate on measures speed and nothing else
- The question is about kernels, serving engines, or hardware utilisation. That is below the endpoint, and this harness cannot see it
- The workload is a single prompt with no history. The harness will run it, but the closed-loop machinery adds nothing; a plain loop over prompts is simpler

## Stage gate

Requires `bench/trajectories.jsonl` and `bench/eval.md` from `/eval-build` (offer to run it
if missing; with `demo`, use `examples/product-coach/trajectories.jsonl`; with `demo <name>`,
`examples/<name>/trajectories.jsonl`). Requires an
`OPENROUTER_API_KEY` in `.env`, or `LOCAL_BASE_URL` for a self-hosted endpoint. Writes
`bench/results-<stamp>.md` and `bench/results-<stamp>.json`.

## 1. Choose the models: three points make a line

**Concept.** A bake-off with one model is a measurement. With two it is a comparison. With
three you can see a shape: is cheaper worse, and by how much per dollar?

**Why it matters.** The question is never "which is best" but "which is good enough for
this step at the lowest cost per correct answer." You cannot see "enough" without a ceiling
and a floor.

**Example.** `openai/gpt-oss-120b` (an open model many providers serve), `qwen/qwen3.6-35b-a3b`
(smaller, should be cheaper), `anthropic/claude-sonnet-5` (the quality ceiling).

**Your turn.** Ask: "Which model do you ship today?" Read the answer key `ceiling`. Then ask:
"Which models? Give me two or three OpenRouter ids, type `auto` to let the harness propose
three from the catalog, or type `demo`." Read the answer key `models`.

With `auto`, the harness reads the hard requirements off the trajectories (tool calls, context
at the longest trajectory's last turn), drops every catalog model that cannot meet them, prices
the rest on this workload's own token mix, and picks three points on a log-price line: the
cheapest that qualifies, the model you ship, and the one closest to the geometric mean of the
two. Show the shortlist and its reasons before the run; the developer can edit it. The floor
is not a recommendation: it is the cheapest model that could work, and the gate decides
whether it does.

*What you just learned: a bake-off needs a ceiling and a floor, or the middle means nothing.*

## 2. Choose the providers: same weights, different silicon

**Concept.** On OpenRouter, one open model is often served by several providers on different
hardware: Cerebras (wafer-scale), Groq (LPU), SambaNova (RDU), Together and others (NVIDIA
GPUs). The request can pin one with `provider.only`. Same model, different chip, one flag.

**Why it matters.** This is the only way a developer can see, from a laptop, that the
hardware behind an endpoint changes time to first token by multiples and price by multiples.
It is also the honest boundary: what you measure is the endpoint (their stack, their
hardware, the network), not the chip. The report says so.

**Example.** `cerebras,groq,sambanova,together` on `openai/gpt-oss-120b`. Check
`GET https://openrouter.ai/api/v1/models/<model>/endpoints` first; a provider not serving the
model today should be dropped with a note, not guessed.

**Your turn.** Ask: "Pin providers for the open model? Comma-separated slugs, `auto` to let
OpenRouter route, or `demo`." Read the answer key `providers`.

*What you just learned: "which chip" is one flag away, and the number you get is endpoint-level.*

## 3. Set the shape of the run: concurrency, runs, limit, reasoning

**Concept.** Four knobs decide what the numbers mean:
- **concurrency** 1 means one trajectory in flight: clean per-user latency (MLPerf's edge
  setup). Higher shows the endpoint under load.
- **runs** 2 replays everything twice so you can measure consistency: does the model give the
  same verdict on the same input?
- **limit** N runs only the first N trajectories: for a live look, not a result.
- **reasoning** low caps a reasoning model's thinking budget; uncapped, it can spend the
  whole output on thinking and emit no answer.

**Why it matters.** Every knob is a condition. Change one and the numbers are not comparable
to the last run. That is why they all go in the conditions block.

**Example.** Live demo: `--limit 5 --concurrency 1 --runs 1 --reasoning low` (about two
minutes). Real result: `--concurrency 1 --runs 2` on all trajectories.

**Your turn.** Ask for each, offering `demo` (answer keys `concurrency`, `runs`, `limit`,
`reasoning`).

*What you just learned: the knobs are conditions; a number without them is not comparable.*

## 4. Price it, then run it

**Concept.** The harness estimates the run's cost before the first request, from live
endpoint prices and the growing-history token count, and refuses above `BAKEOFF_MAX_RUN_USD`.

**Why it matters.** Trajectories times turns times models times providers times runs is a
product, and later turns carry the whole history. Twenty three-turn trajectories across four
providers, twice, is 480 calls. See the number before the invoice does.

**Your turn.** Run:

```
uv run python -m harness.bench --trajectories <path> --models <ids|auto> [--ceiling <id>] \
  [--providers <slugs>] --concurrency <n> --runs <n> [--limit <n>] --reasoning <level>
```

Show the estimate. Confirm. Narrate the progress lines as they arrive: each one is a
trajectory finishing with its pass count.

*What you just learned: cost is multiplicative; estimate first.*

## 5. Read the table, in this order

**Concept.** The report has a conditions block, a per-cell endpoint table (quantization and
list prices), the results table, and a computed verdict. Read them in that order.

**Why it matters.** Reading the results first is how numbers get misremembered. Reading the
conditions first is how they stay facts.

**How to read the results table.**
- **gate** is the pass rate against your ground truth. Compare it to what a trivial model
  would score (in the example, "always DECLINE" scores 60% on turn 1).
- **TTFT p50 / p95**: the median and the slow tail of time to first token. A human waiting
  feels this. If p95 is triple p50, the endpoint is inconsistent, and your users will notice
  the tail, not the median.
- **TPOT p50**: seconds per generated token once output starts, reasoning tokens included.
  Decode speed. tok/s/user is its inverse.
- **e2e p95**: the slow tail of the whole turn. An agent waiting on a tool result feels this.
- **$/task**: cost summed over a whole trajectory, because agents make many calls per task.
- **$/correct**: the headline. Total cost divided by calls that passed the gate. A cheap
  model that fails half the time is not cheap.
- **consistency**: with two runs, how often the same turn got the same verdict.
- **errors**: calls that failed outright; they count as failed in the gate.

**The verdict** is computed, not chosen: the cheapest cell by cost per correct call whose
gate is within 5% of the best. Read it, then argue with it if you know something the table
does not (a quality difference the gate cannot see, a provider you cannot use for policy
reasons). Write the argument down next to it.

*What you just learned: p95 is the product; cost per correct call is the price.*

## 6. Say what the numbers cannot say

**Concept.** Endpoint-level numbers are about a provider's serving stack plus its hardware
plus the network, under whatever load its shared fleet was carrying at that minute.

**Why it matters.** "Cerebras is faster than Groq" is not what you measured. "The Cerebras
endpoint on OpenRouter served gpt-oss-120b at fp16 with a 0.45 s median TTFT at concurrency
1 on this date" is. The second sentence is boring and true; the first is quotable and not.

**Your turn.** Before the report leaves your machine, read the conditions block aloud once.
If any line is missing, the harness did not run correctly; do not paste the table.

*What you just learned: the boring sentence is the true one.*

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "Just give me the table, I know the setup" | You know it today. Whoever you paste it to does not, and you will not in three months. Conditions are how a number stays a fact instead of becoming a rumour. |
| "One run is enough, the difference is obvious" | A 10-point gap on one run of 20 trajectories can be three flipped answers. Run twice or label it "single run" in the report. |
| "Cost per call is fine, we'll multiply later" | Nobody multiplies later. Agents make many calls per task; the per-task number is the one that matches the invoice. |
| "The gate is too strict, the model was basically right" | Then the gate is wrong and should be fixed in `/eval-build`, before the run. Loosening it after seeing the results is how every model passes. |
| "Cerebras was fastest, so wafer-scale wins" | You measured an endpoint at one moment, not a chip. Say what you measured. |
| "We can skip the estimate, it's cheap" | It is cheap until the trajectory list grows and the history with it. The estimate takes one second. |

## Red flags

- A results table pasted somewhere without its conditions block
- A per-call cost quoted for an agent
- A "winner" declared from a single run
- A provider row with quantization "unknown" presented as comparable to an fp16 row without saying so
- A pass rate at or below what a constant-answer model would score, treated as a real result
- p95 dropped from the table because "the median tells the story"

## Verification

Before the report is called done:

- [ ] The conditions block lists date, endpoint, trajectories, turns p50, runs, concurrency, max_tokens, reasoning effort, cache state, input and output tokens p50, gate type, harness commit
- [ ] Every cost in the table is per task or per correct call, never per call, for an agent workload
- [ ] p50 and p95 both appear for TTFT and e2e
- [ ] The verdict sentence names the cell, the gate rate, the tolerance, and the deciding metric
- [ ] Any single-run result is labelled "single run"
- [ ] The endpoint-level disclaimer is present above the table
- [ ] The trivial-baseline row is above the model rows, and no model at or below it is called a contender

## Output contract

Writes `bench/results-<stamp>.md` (conditions, per-cell endpoint facts, results table,
verdict, notes) and `bench/results-<stamp>.json` (every call record, re-readable). When a
routing decision follows, the developer appends one paragraph under the verdict saying what
they chose and why, including anything the gate could not see.

## See also

- `/eval-build` writes the trajectories this skill runs. Run it first if `bench/trajectories.jsonl` does not exist.
- `docs/mlperf-mapping.md` explains what MLPerf's agentic benchmark does and what this keeps.
- `examples/product-coach/results-sample.md` is a finished report to compare against.
- `examples/README.md` shows one bake-off per workload shape and the different verdict each produced.

*Framework source of truth: `docs/mlperf-mapping.md` in the bakeoff repo.*
