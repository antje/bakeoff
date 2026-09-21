# Interview answers for the ledger-audit example

When you type `demo ledger-audit` at a prompt, the skill reads the matching answer here, shows
it with its "why this is a good answer" line, and asks whether to use it or take your own.
Each answer is keyed by the question id the skill uses.

---

## /eval-build

### step
**Answer:** The position step of the finance assistant. Given every batch posted so far in a
month-end session, it answers one exact question about the current state: a balance, a count,
or a net change.

**Why this is good:** One step, but six turns deep, and that depth is the workload. A model
that answers turn one well and turn six badly is not a model for this step, and only a
closed-loop eval can tell you.

### logs
**Answer:** `examples/ledger-audit/logs.jsonl` (20 lines). Each session has the batches as
posted and the ledger system's position after each one.

**Why this is good:** The ledger system computed the answer without a model in the loop. That
is the cleanest ground truth there is: exact, recorded at the time, and not an opinion.

### correct
**Answer:** The first line of the reply contains the exact integer the ledger system computed,
thousands separator optional, sign required when negative. Neighbouring numbers do not pass.

**Why this is good:** Exact arithmetic gets an exact gate. There is nothing to interpret, and
a controller can check any row against the ledger by hand.

### bad-correct
**Answer (a bad one, for contrast):** "Correct means the answer is close enough; a few units
off is fine for a review."

**Why this is bad:** A ledger that is a few units off does not close. And "close enough" hides
the failure mode this eval exists to catch: a model that dropped one reversal on turn two and
is now confidently wrong by exactly that amount on every turn after.

## /bakeoff

### models
**Answer:** `openai/gpt-oss-20b,openai/gpt-oss-120b,qwen/qwen3.6-35b-a3b,anthropic/claude-sonnet-5`

**Why this is good:** The same four points as every other example. Here the question is where
the small models fall off, and whether the frontier model's price per call is still the
cheapest price per *correct* call once the others start failing.

### providers
**Answer:** `auto`

**Why this is good:** The controller is not watching a spinner, so this is a model question,
not a silicon question. Pin providers when TTFT is the product; here correctness is.

### concurrency
**Answer:** 4

**Why this is good:** Nobody is watching a spinner, and with reasoning on the TTFT is mostly
thinking time either way, so several streams in flight cost nothing that matters here and
turn an hour into fifteen minutes. The report records whichever you chose.

### runs
**Answer:** 2

**Why this is good:** On this shape consistency is the whole story. A model at 70% that gets
a different 30% wrong each run cannot be routed to; one that gets the same hard sessions wrong
can at least be fenced.

### limit
**Answer:** 2 for a live look; the full 20 for a result.

**Why this is good:** Six turns with reasoning on is slow. Two sessions across two models show
a balance being carried across a reversal; twenty is where the collapse curve appears.

### reasoning
**Answer:** medium

**Why this is good:** This is the one example where thinking is part of the workload. Running
it at `low` is a different experiment, and a fair one to run second; the conditions block
records which one the table shows.
