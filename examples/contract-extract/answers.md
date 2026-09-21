# Interview answers for the contract-extract example

When you type `demo contract-extract` at a prompt, the skill reads the matching answer here,
shows it with its "why this is a good answer" line, and asks whether to use it or take your
own. Each answer is keyed by the question id the skill uses.

---

## /eval-build

### step
**Answer:** The question-answering step of Meridian's procurement tool. It reads one signed
agreement and one question and returns the single value asked for: a fee, a number of days,
a jurisdiction, a clause number.

**Why this is good:** One step with a long input and a tiny output. That shape decides the
model and the provider on its own: prefill cost and time to first token, not fluency.

### logs
**Answer:** `examples/contract-extract/logs.jsonl` (20 lines). Each line has the full
agreement text and the six fields a paralegal keyed in from it afterwards.

**Why this is good:** The keyed fields are the outcome, recorded by a person from the same
document without seeing the model. That is ground truth. The document is the exact input the
model sees, not a summary of it.

### correct
**Answer:** The first line of the reply contains the keyed value: the amount (with or without
a thousands separator), the number of days or months, the jurisdiction name, or the clause
number. Nothing else on the first line is scored.

**Why this is good:** A pattern anchored to the first line is a comparison a script can run
and a human can check by eye. It also refuses the cheap trick: a model that lists every number
in the contract does not pass.

### bad-correct
**Answer (a bad one, for contrast):** "Correct means the answer is supported by the contract."

**Why this is bad:** Supported by whom? A second model would have to read the contract and
judge, at the same cost as the first call and with its own error rate. The paralegal already
wrote down the answer; compare against that.

## /bakeoff

### models
**Answer:** `openai/gpt-oss-20b,openai/gpt-oss-120b,qwen/qwen3.6-35b-a3b,anthropic/claude-sonnet-5`

**Why this is good:** The same four points as every other example. Here the question is
whether the small models still find the needle among the distractors, and whether the large
one's input price is justified by a gate difference or is just a bigger bill for reading.

### providers
**Answer:** `cerebras,groq,together` on `openai/gpt-oss-120b`

**Why this is good:** Same weights, three serving stacks, on a 4,500-token prompt. Prefill is
where they differ, and this is the shape that makes the difference visible. The report says
endpoint-level, because that is what it is.

### concurrency
**Answer:** 1

**Why this is good:** A buyer is waiting on one stream. Per-user TTFT is the number this step
lives on, and it is only clean at concurrency 1.

### runs
**Answer:** 2

**Why this is good:** A model that finds the notice period once and the cure period the next
time is not one to route to. Consistency shows it.

### limit
**Answer:** 4 for a live look; the full 20 for a result.

**Why this is good:** Each turn sends 4,500 tokens; four trajectories across four models is a
minute or two. Say which one you are showing.

### reasoning
**Answer:** off

**Why this is good:** Extraction does not need a thinking budget, and the answer is short
enough that hidden reasoning would dominate both latency and cost. `off` asks every model for
its minimum; the ones that refuse fall back to `low` and the report says so. Recorded in the
conditions block.
