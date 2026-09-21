# Interview answers for the worked example

When you type `demo` at a prompt, the skill reads the matching answer here, shows it to you
with its "why this is a good answer" line, and moves on. Read the *why* lines even if you
never use the example: they are the difference between an eval and a pile of prompts.

Each answer is keyed by the question id the skill uses.

---

## /eval-build

### step
**Answer:** The objection step of product-coach. It reads one new experiment brief plus the
team's completed-experiment history and returns a verdict (OBJECT or DECLINE), an objection
type, and the ids of past experiments that support the call.

**Why this is good:** It names one step, not the whole product. Inference is decided per step:
this step is a classification with citations, and it will not get the same model, budget, or
gate as, say, a free-text summary step elsewhere in the same app.

### logs
**Answer:** `examples/product-coach/logs.jsonl` (25 lines). Each line has the brief the coach
saw, the ids of the experiments it could see at the time, and what happened afterwards.

**Why this is good:** The logs carry three things an eval needs: the exact input, the context
that was available *at the time* (not later), and an outcome recorded after the fact by
something other than the model. Logs that only have prompts and responses cannot become an
eval; there is nothing to be right or wrong against.

### correct
**Answer:** A verdict is correct when it matches what really happened: OBJECT is correct if
the experiment's actual lift was flat or negative (at or below +0.5pp); DECLINE is correct if
it went on to work. The type turn is correct when it names `repeated-mechanism` for a
feeling-led change on the early funnel and `NONE` for a decline. The citation turn is correct
when every cited id exists in the history the model was shown.

**Why this is good:** Every definition is a comparison a script can run and a human can re-run
by hand. None of them asks a second model for an opinion. The threshold (+0.5pp) is written
down, so nobody can move it after seeing the results.

### bad-correct
**Answer (a bad one, for contrast):** "Correct means the objection is insightful and well
argued."

**Why this is bad:** "Insightful" is a judgement, not a measurement. To score it you would
need a grader model, whose own accuracy nobody has measured, and whose verdict would change
with its version. You would be benchmarking the grader. Rewrite it as something checkable:
a label, a tool call, or a pattern.

### volume
**Answer:** About 40 reviews per day; 200 to 300 in a planning week.

**Why this is good:** Volume decides whether cost matters at all. At 40 a day, a $0.03 call
is a rounding error; at 40,000 it is the biggest line on the bill. It also decides the
sample size: 20 trajectories is a fair sample of 40 a day, and would be thin at 40,000.

### who-waits
**Answer:** A product manager in the browser, watching a spinner after clicking Review.

**Why this is good:** "Who waits" picks the latency number that matters. A human waiting
feels time to first token. An agent waiting on a tool result feels end-to-end latency. A
batch job feels neither. Here it is a human, so TTFT is the headline and streaming is
non-negotiable.

### latency-budget
**Answer:** First token under 2 seconds at p95; complete answer under 15 seconds at p95.

**Why this is good:** Both numbers carry a percentile. "Under 2 seconds" without one is a
wish; "at p95" is a promise that one review in twenty may be slower and the rest will not be.
The tail is what the PM remembers.

### minimum-trajectories
**Answer:** 20 (the demo set). The rule of thumb is 20 minimum, 50 better.

**Why this is good:** With 20 trajectories of 3 turns, a single flipped answer moves the pass
rate by under 2%. With 5, it moves it by 7%, and any difference between models is noise.

---

## /bakeoff

### models
**Answer:** `openai/gpt-oss-120b,qwen/qwen3.6-35b-a3b,anthropic/claude-sonnet-5`

**Why this is good:** One open model that several silicon vendors serve (so it can also be
used for the provider comparison), one smaller open model that should be much cheaper, and one
frontier model as the quality ceiling. Three points are enough to see whether cheaper is
worse here, and by how much.

### providers
**Answer:** `cerebras,groq,sambanova,together` on `openai/gpt-oss-120b`

**Why this is good:** Same weights, four different architectures behind the endpoint:
wafer-scale, LPU, RDU, and NVIDIA GPU. It is the one comparison a developer cannot make any
other way from a laptop. The report labels it endpoint-level, because that is what it is.

### concurrency
**Answer:** 1

**Why this is good:** One trajectory in flight at a time gives clean per-user latency, the
way MLPerf's edge agentic benchmark measures. Raising it later shows how the endpoint behaves
under load; but the first run should answer "how fast is this for one user."

### runs
**Answer:** 2, when time allows; 1 for a quick look.

**Why this is good:** Replaying twice measures consistency. A model that gives a different
verdict on identical input is not one you can route to on the strength of one run, and you
only find out by asking twice.

### limit
**Answer:** 4 for a stage demo on one open model and two providers (about eleven seconds);
5 for a longer live look (about two minutes with three models); the full 20 for a real result.

**Why this is good:** A live audience will not wait ten minutes. Four or five trajectories
show the mechanics; the precomputed 20-trajectory table shows the numbers. Say which one
you are showing: four is a demo, twenty is a result.

### reasoning
**Answer:** low

**Why this is good:** Reasoning models can spend the whole output budget thinking and emit no
answer. A verdict-and-citation task does not need a thinking budget. The choice is recorded
in the conditions block because it changes both latency and cost.

### skip-conditions
**Answer (a bad one, for contrast):** "Just give me the table, I know the setup."

**Why this is bad:** You know it today. The person you paste the table to next week does not,
and neither will you in three months. The conditions block is how a number stays a fact
instead of becoming a rumour.
