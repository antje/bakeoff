# Interview answers for the tool-router example

When you type `demo tool-router` at a prompt, the skill reads the matching answer here, shows
it with its "why this is a good answer" line, and asks whether to use it or take your own.
Each answer is keyed by the question id the skill uses.

---

## /eval-build

### step
**Answer:** The action step of the store's support copilot. It reads the operator's message
and the session so far and emits one tool call: look up a customer, fetch an order, issue a
refund, update an address, or escalate a ticket.

**Why this is good:** One step whose output is structured, not prose. That changes everything
downstream: the gate is exact, the failure is expensive, and fluency is worth nothing.

### logs
**Answer:** `examples/tool-router/logs.jsonl` (20 lines). Each session has the operator's
messages, the call the copilot made and the operator approved, and the tool's return value.

**Why this is good:** The approved call is an outcome from outside the model: a human said
"yes, run that." And the tool returns are recorded, so the eval can replay turn two with the
same order id every model saw, instead of letting each model's mistakes change the world.

### correct
**Answer:** The model called the expected tool with arguments equal to the approved ones
after JSON normalisation. Enum fields (`reason`, `severity`) must match exactly.

**Why this is good:** Tool name plus arguments is the most exact gate there is, and it is what
MLPerf uses for its agentic benchmark. Key order and string-versus-object encoding are
normalised away so the check measures the decision, not the serialiser.

### bad-correct
**Answer (a bad one, for contrast):** "Correct means the copilot understood what the operator
wanted."

**Why this is bad:** Understanding is unobservable; the call is not. A model that "understood"
and then refunded 22,924 cents instead of 11,462 did the wrong thing, and no grader's opinion
about its understanding changes the card statement.

## /bakeoff

### models
**Answer:** `openai/gpt-oss-20b,openai/gpt-oss-120b,qwen/qwen3.6-35b-a3b,anthropic/claude-sonnet-5`

**Why this is good:** The same four points as every other example. On this shape the question
is fidelity: which of the cheap models emits an exact call turn after turn, and whether the
gap to the frontier model is a few percent or a cliff.

### providers
**Answer:** `cerebras,groq,together` on `openai/gpt-oss-120b`

**Why this is good:** Tool calling is a serving-stack feature as much as a model feature. Some
providers do not serve it for an open model; the report says so as a note. The ones that do
differ on latency, and the operator is waiting.

### concurrency
**Answer:** 2

**Why this is good:** The operator waits on one call, so per-user latency matters, but the
calls are short and two streams keep the run under a few minutes. Record it either way.

### runs
**Answer:** 2

**Why this is good:** A copilot that gets the refund right the first time and wrong the second
is the worst case. Two runs is the minimum that can see it.

### limit
**Answer:** 3 for a live look; the full 20 for a result.

**Why this is good:** Three sessions across two models takes about a minute and shows a tool
call being assembled from an earlier result. Twenty is where the gate rate means something.

### reasoning
**Answer:** off

**Why this is good:** Emitting a call does not need a thinking budget, and hidden reasoning
adds to the wait the operator feels. At `low`, Qwen3.6 thinks anyway and starves the answer;
`off` is the setting that gives every model its minimum, and the ones that refuse it (gpt-oss)
fall back to `low` with a note in the report.
