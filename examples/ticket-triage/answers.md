# Interview answers for the ticket-triage example

When you type `demo ticket-triage` at a prompt, the skill reads the matching answer here,
shows it with its "why this is a good answer" line, and asks whether to use it or take your
own. Each answer is keyed by the question id the skill uses.

---

## /eval-build

### step
**Answer:** The triage step of Loopwire's support copilot. It reads the routing policy and one
inbound ticket and returns the queue to route to, then the customer's plan tier.

**Why this is good:** One step, two closed answer sets, thousands of calls a day. It is
decided on its own terms: a short prompt and a one-word answer get a different model and a
different budget than the long-document step next door.

### logs
**Answer:** `examples/ticket-triage/logs.jsonl` (32 lines). Each line has the ticket as the
copilot saw it, the queue a human eventually resolved it to, and the plan tier from the CRM.

**Why this is good:** The outcome comes from outside the model: an agent's resolution and a
CRM field, both recorded without looking at what the model said. Prompts and responses alone
could not become an eval.

### correct
**Answer:** Turn 1 is correct when the first line of the reply names the resolved queue.
Turn 2 is correct when the first line names the CRM plan tier. Whole-word, case-insensitive.

**Why this is good:** Both are comparisons a script runs and a human can re-run. The eight
queue names were chosen so none is a substring of another, which is the one way a label check
can pass two answers at once.

### bad-correct
**Answer (a bad one, for contrast):** "Correct means the ticket ends up with the right team
eventually."

**Why this is bad:** "Eventually" hides the hand-off you are trying to measure. If a ticket
is misrouted and an agent forwards it, the customer still gets helped and the misroute is
invisible. The eval has to score the model's first answer against the final resolution.

## /bakeoff

### models
**Answer:** `openai/gpt-oss-20b,openai/gpt-oss-120b,qwen/qwen3.6-35b-a3b,anthropic/claude-sonnet-5`

**Why this is good:** The same four points as every other example, so the verdicts compare.
For this shape the interesting one is the smallest: if a 20B model clears the gate, every
larger model is paying for nothing.

### providers
**Answer:** `auto`

**Why this is good:** For a workload nobody waits on, the provider question is price, and
OpenRouter's own routing already picks on price. Pin providers when latency matters; here it
does not.

### concurrency
**Answer:** 2

**Why this is good:** There is no per-user latency to protect, so two streams halve the wall
clock without changing what is measured. The report records it.

### runs
**Answer:** 2

**Why this is good:** At the ceiling, consistency is the tie-breaker. Two cheap models at 97%
are not equal if one of them gets a different 3% wrong each time.

### limit
**Answer:** 6 for a live look; the full 32 for a result.

**Why this is good:** Two-turn trajectories are quick; six of them across four models is under
a minute. Say which one you are showing.

### reasoning
**Answer:** off

**Why this is good:** A one-word classification does not need a thinking budget, and a
reasoning model that thinks past 200 tokens returns nothing. `off` asks every model for its
minimum; the ones that refuse (gpt-oss) fall back to `low` and the report says so. The choice
is recorded in the conditions block.
