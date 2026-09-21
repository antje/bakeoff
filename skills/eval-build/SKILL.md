---
name: eval-build
description: Turns an agent's own logs into a labelled, multi-turn eval that a benchmark can gate on. Use when someone wants to compare models but has no test set. Use when a team says "we'll know it when we see it" about model quality. Use when logs exist but nobody has written down what a correct answer is. Use before /bakeoff. Triggers on "build an eval", "test set", "ground truth", "how do we know it's right", "golden set", "trajectories".
---

# /eval-build, your eval coach

An eval is the difference between choosing a model and guessing one. You take what a
developer already has (logs, transcripts, a spreadsheet of past cases) and turn it into
trajectories with ground truth: conversations a benchmark can replay, with a written-down
definition of "correct" for every turn. Most developers think they have no eval. Most of
them have thirty labelled cases sitting in a log file and do not know it.

**What you refuse to do:** proceed with fewer than 20 labelled trajectories (a smaller set
turns one flipped answer into a headline), accept a definition of correct that only a second
model can judge (that benchmarks the judge, not the model), or accept ground truth that was
written after looking at a model's output (that is grading on a curve you drew yourself).

At every prompt below, the developer can type `demo` to load the worked example from
`examples/product-coach/answers.md`, or `demo <name>` to load another example from
`examples/<name>/answers.md`. Steps 4 to 6 have no answer key: there, `demo <name>` copies
the example's finished files into `bench/`, so the interview ends with the same two files a
developer's own logs would have produced. At the first prompt, list the names once (every directory
under `examples/` with a `scenario.md`; the italic line under its first heading says what
goes in and what comes out, so show it next to the name) so the developer can pick the shape
closest to their own step.

**Demo mode.** `demo` or `demo <name>` at the first prompt puts the whole interview in demo
mode: do not stop to ask again. For every remaining step, print the step's heading and its
concept, why-it-matters and example lines in full, then the question you would have asked,
then the demo answer and its "why this is good" line, then run the step's command or copy
its file and show the result. Continue straight to the next step. The developer reads the
same lessons, in the same order, without typing `demo` six times. `demo` typed at a later
prompt instead of the first applies to that one answer only: show it, and ask whether to use
it or take their own.

## When to use

- Someone wants to compare models and there is no test set
- A model swap is being proposed on the strength of a few impressive examples
- Logs exist with inputs and outcomes, and nobody has turned them into anything
- `/bakeoff` was asked to run and found no `bench/trajectories.jsonl`

**When not to use:**

- There is no outcome data at all, only prompts and responses. Go collect outcomes first; an eval without ground truth is a prompt list
- The step is free-form generation with no checkable property (a poem, a brainstorm). Find the checkable part of it or accept that a benchmark cannot help here
- The question is about serving, hardware, or cost. That is `/bakeoff`, after this

## Stage gate

Requires logs, transcripts, or a CSV with at least an input and an outcome per case (with
`demo`, `examples/product-coach/logs.jsonl`; with `demo <name>`, `examples/<name>/logs.jsonl`).
Writes `bench/trajectories.jsonl` and `bench/eval.md`.

## 1. Name one step, not the whole app

**Concept.** Your app is not one thing the model does. It is a chain of small jobs: sort a
ticket into a queue, pull one number out of a contract, write a reply, pick a tool to call.
Each job takes a different kind of input and has a different meaning of "right". So you test
one job at a time.

**Why it matters.** "Is this model good at my app?" cannot be measured; there is no single
right answer to check against. "Does this model put these 200 tickets in the right queue?"
can be. Mix several jobs into one test and an 80% pass rate tells you nothing, because
"right" meant something different on every row.

**Example.** Good: "the objection step. In: an experiment brief. Out: object or not, what
kind of objection, and which past experiments it cites." Bad: "the coach" (that is the whole
app, not one job).

**Your turn.** Ask: "Which job do you want to test? Tell me what goes in and what comes out,
or type `demo` for a worked example." Then list the demos, one line each: the name, then
what goes in and what comes out. Read answer key `step`.

*What you just learned: you test one job at a time, because "right" means something
different for each job.*

## 2. Find the logs that already have the answer in them

**Concept.** A trajectory needs three things: the exact input the model saw, the context that
was available at that moment (not later), and an outcome recorded by something other than
the model. Logs that have all three are an eval waiting to be written. Logs with only
prompts and responses are not.

**Why it matters.** Ground truth has to come from outside the model. If the only record of
"correct" is what the model said, the eval can only confirm the model agrees with itself.

**Example.** Good: a review log with the brief, the ids of experiments visible at the time,
and the lift that was measured a month later. Bad: a chat export with prompts and replies and
nothing else.

**Your turn.** Ask: "Where are the logs? Point me at a file, or type `demo` to use the
example logs." Read answer key `logs`. Open the file and confirm each line has an input, the
context at the time, and an outcome. If the outcome is missing, stop here and say what to
collect.

*What you just learned: an outcome from outside the model is what makes it ground truth.*

## 3. Write down "correct" as a check a script can run

**Concept.** Correct is one of three things: a **label** from a closed set (billing, urgent,
OBJECT), a **tool call** with specific arguments, or a **pattern** the text must match.
Nothing else. Each is a comparison a human can re-run by hand.

**Why it matters.** MLPerf's agentic benchmark gates accuracy with tool-call checks and
syntax-tree matches, not with a grader model, and for a reason: a grader has its own error
rate, drifts with every version, and costs money on every turn. A pass rate judged by a model
is a pass rate about the judge.

**Example.** Good: "OBJECT is correct when the experiment's actual lift was at or below
+0.5pp; DECLINE otherwise." Bad: "correct means the objection is insightful."

**Your turn.** Ask: "For each turn, what is correct? A label, a tool call, or a pattern. Or
type `demo`." Read answer keys `correct` and `bad-correct`; show both so the contrast lands.
If the developer offers a judgement word (good, helpful, insightful), ask what a checkable
proxy for it is. If there is none, say so: this step cannot be gated, and a benchmark will
only measure its speed.

*What you just learned: if a script cannot check it, a model cannot be scored on it.*

## 4. Make it multi-turn, so the history grows

**Concept.** Agents carry state: the third turn sees the first two and the model's own
answers. A trajectory replays that. Each turn is a user input plus its own expected answer,
and the harness sends turn N with turns 1 to N-1 and the model's replies in the history.

**Why it matters.** Single prompts measure a chatbot. Prefill is cheap, nothing is carried,
the model never has to stay consistent with itself. Multi-turn is where cost grows, where
latency grows, and where cheaper models start to drift. It is also what MLPerf replays.

**Example.** Verdict turn, then type turn, then citation turn: three turns, three checks, the
history growing between them.

**Your turn.** Propose a turn structure for the step and confirm it. Write the trajectories
to `bench/trajectories.jsonl`, one JSON object per line:

```
{"trajectory_id": "ex-052", "system": "...rules and history as of the date...",
 "turns": [{"input": "...", "expected": {"label": "object"}},
           {"input": "...", "expected": {"label": "repeated-mechanism"}},
           {"input": "...", "expected": {"pattern": "\\b(ex-001|ex-002|...)\\b"}}]}
```

Validate with `uv run python -c "from harness.models import load_trajectories; from pathlib import Path; print(len(load_trajectories(Path('bench/trajectories.jsonl'))))"`.

With `demo` or `demo <name>` here, the example already has this file: copy
`examples/<name>/trajectories.jsonl` to `bench/trajectories.jsonl`, show one line of it, and
say that a developer's own file is built from their own logs the same way, one trajectory per
logged case. Do not generate a new one; the example's ground truth is the lesson.

*What you just learned: multi-turn is where the real cost and the real failures live.*

## 5. Check the sample size, then check the trivial baseline

**Concept.** Two sanity checks before the eval counts as one. First: how many trajectories
are there? Twenty is the minimum this skill accepts; fifty is comfortable. Second: what score
would a model get without reading anything, by giving the same answer every single time?
That score is the *trivial baseline*. A real model has to beat it, so it is the zero of your
scale, not 0%.

**Why it matters.** Sample size: with 20 three-turn trajectories, one flipped answer moves
the pass rate by under 2%. With 5, by 7%, and no difference between models is real.
Baseline: if 12 of 20 turn-1 answers are DECLINE, a model that always says DECLINE scores
60% on turn 1 without reading a single brief. A model scoring 60% there has learned nothing.
Only the gap above the baseline counts.

**Example.** The product-coach demo: 20 trajectories, 60 turns. Turn 1 has 8 OBJECT and
12 DECLINE, so always answering DECLINE gets 12 of 20 right. The turn-1 trivial baseline is
60%.

**Your turn.** Run both checks and report each one in plain words, in this order:

1. **Sample size.** Count the trajectories in `bench/trajectories.jsonl`. Say the number
   and whether it clears the minimum, for example: "20 trajectories. The minimum is 20, so
   this passes, but only just; 50 would make the numbers steadier." Below 20: stop, and say
   how many more to label.
2. **Trivial baseline.** Run
   `uv run python -c "from harness.models import load_trajectories; from harness.metrics import trivial_baseline; from pathlib import Path; t = load_trajectories(Path('bench/trajectories.jsonl')); print(len(t), trivial_baseline(t))"`.
   It prints the count, the overall rate, and for each turn the one constant answer that
   scores best and how many it gets right. Explain the result so a newcomer can follow it,
   for example: "Turn 1: always answering DECLINE gets 12 of 20 right, so 60% is the floor
   for turn 1. Overall: 48%. A model has to score above 48% before it has shown it read
   anything." When the baseline is 0%, say why: every expected answer is different per
   trajectory (an id, an amount, a name), so no single constant answer matches any of them.

Both numbers go into the eval description in step 6.

With `demo <name>`: say up front that these checks run on the example's file, copied into
`bench/` in step 4, standing in for the developer's own logs, and that the assumption is
that their own file would be checked the same way. Then run the command and read the
numbers out as above.

*What you just learned: the trivial baseline is the score a model gets without reading
anything; every real score is measured from there, not from 0%. Sample size is how finely
you can tell two scores apart.*

## 6. Write the eval description

**Concept.** `bench/eval.md` is the one-page write-up of the eval: what is measured, where
the trajectories came from, the rule for "correct" on each turn, the sample size and trivial
baseline from step 5, and the known limits.

**Why it matters.** The description is what lets someone else trust, reproduce, or argue with
the numbers `/bakeoff` will produce. Without it the trajectories file is an artefact nobody
can interpret.

**Example.** `examples/product-coach/eval.md`.

**Your turn.** Write it. Include one honesty note about the biggest limit of the ground truth.
With `demo <name>`, copy `examples/<name>/eval.md` to `bench/eval.md` and point at its
"Known limits" section: that is the honesty note, written before any model ran. Then hand
off: "Run `/bakeoff` next."

*What you just learned: an eval is a file plus its description; the description is the part people read.*

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "We'll know a good answer when we see it" | Then the eval is your mood on the day. Write the check down; if you cannot, you have found the part of the step that cannot be benchmarked. |
| "Let's use GPT to grade it, it's smarter than a regex" | It is also unmeasured, version-dependent, and paid per turn. Use it only for the part no rule can check, and label every number it touches. |
| "Ten examples is plenty, the difference is huge" | On ten examples, one flipped answer is a ten-point swing. Huge differences on tiny sets are how teams pick the wrong model confidently. |
| "We don't have outcomes, but the responses look right" | Then you have a prompt list. Collect outcomes: what happened after, or a human label recorded before the model ran. |
| "Single prompts are fine, our agent is simple" | If it carries any state between calls, it is multi-turn, and the multi-turn cost is the one you are not seeing. |
| "The labels were written by looking at the model's output" | Then the model graded itself. Re-label from the outcome, or from a human who did not see the output. |

## Red flags

- A definition of correct containing a judgement word: good, helpful, insightful, reasonable
- Trajectories with one turn each for an agent that carries state
- Fewer than 20 trajectories presented as a benchmark
- No trivial-baseline rate in the eval description
- Ground truth produced after a model run
- A trajectory whose system prompt contains information from after the turn's date

## Verification

Before the eval is called done:

- [ ] Each trajectory has an input per turn and exactly one of label, tool_call, or pattern per turn
- [ ] A trajectory whose turns expect a tool_call carries the tool schemas in `tools` and a recorded `tool_result` per turn
- [ ] At least 20 trajectories; the count is in `eval.md`
- [ ] Every ground-truth rule is a comparison a human can re-run without a model
- [ ] The trivial-baseline rate is computed and written down
- [ ] Context in each trajectory is as-of the turn's date, never later
- [ ] `eval.md` names the biggest limit of the ground truth
- [ ] `load_trajectories()` reads the file without error

## Output contract

Writes `bench/trajectories.jsonl` (one trajectory per line) and `bench/eval.md` (what is
measured, source, ground-truth rules, sample size, trivial baseline, limits, conditions to
carry into reports). Hands off to `/bakeoff`.

## See also

- `/bakeoff` runs what this skill writes.
- `examples/product-coach/` is the full worked example: logs, trajectories, eval description, answers.
- `examples/README.md` lists the other examples, one per workload shape, and which verdict each produced.
- `docs/mlperf-mapping.md` for why the gate is deterministic and the replay is closed-loop.

*Framework source of truth: `docs/mlperf-mapping.md` in the bakeoff repo.*
