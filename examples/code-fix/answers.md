# Interview answers for the code-fix example

When you type `demo code-fix` at a prompt, the skill reads the matching answer here, shows
it with its "why this is a good answer" line, and asks whether to use it or take your own.
Each answer is keyed by the question id the skill uses.

---

## /eval-build

### step
**Answer:** The fix step of Nightjar's review copilot. When CI goes red it reads the function,
its spec, the failing test, and the CI line, then names the bug category, writes the corrected
function as a one-click suggestion, and says what the corrected function returns.

**Why this is good:** One step, three checkable outputs, and the expensive one is code. It is
decided on its own terms: a whole function out per call is a different bill and a different
failure mode than a one-word label, even from the same model.

### logs
**Answer:** `examples/code-fix/logs.jsonl` (20 lines). Each line has the function as the
copilot saw it, the failing test, the CI output, the fix that was merged, and the category the
reviewer put on the PR.

**Why this is good:** The merged fix is an outcome from outside the model: a person accepted
it and CI went green. The reviewer's label is a second one. Neither was written by looking at
what a model proposed.

### correct
**Answer:** Turn 1 is correct when the first line names the reviewer's category. Turn 2 is
correct when the reply contains the line the merged fix changed, or one of its listed
equivalents. Turn 3 is correct when the first line is the value the merged function returns.

**Why this is good:** All three are comparisons a script runs and a human can re-run. Turn 2
is the loosest, and the eval says so: it checks the fix is there, not that nothing else broke.
Execution would be stricter, and it is the first thing to add.

### bad-correct
**Answer (a bad one, for contrast):** "Correct means the suggested code looks reasonable and a
senior engineer would accept it."

**Why this is bad:** That is a judge, and a judge with a taste. Two senior engineers will
disagree about the same suggestion, and a judge model will agree with whichever way the prompt
leans. The merged fix already exists; score against it.

## /bakeoff

### models
**Answer:** `openai/gpt-oss-20b,openai/gpt-oss-120b,qwen/qwen3.6-35b-a3b,anthropic/claude-sonnet-5`

**Why this is good:** The same four points as every other example, so the verdicts compare.
On this shape the question is which turn breaks first as the model gets smaller: the label,
the code, or the trace.

### providers
**Answer:** `auto`

**Why this is good:** The author is waiting loosely, not by the second, so the provider
question is price and OpenRouter's routing already picks on price. Pin a provider when a
TTFT budget matters; here the budget is 15 s for three turns.

### concurrency
**Answer:** 2

**Why this is good:** Nobody's latency is being protected within a PR, so two streams halve
the wall clock and change nothing that is measured. The report records it.

### runs
**Answer:** 2

**Why this is good:** A copilot that misses a different PR each run cannot be trusted on any
of them. Two runs show whether the turn-2 misses are the same bug families both times.

### limit
**Answer:** 3 for a live look; the full 20 for a result.

**Why this is good:** Three PRs cover three bug families and take under a minute across two
models; the whole function on turn 2 is the slow part. Say which one you are showing.

### reasoning
**Answer:** low

**Why this is good:** Turn 3 is a trace and a little thinking helps, but 600 output tokens
is the budget for a whole function and a model that thinks past it returns nothing. `low`
keeps the trace inside the budget; `off` is a fair second experiment and the conditions block
says which one the table shows.
