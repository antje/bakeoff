# Eval: tool router

Written by `/eval-build`. This is what a finished eval description looks like for an agent
step whose output is a function call.

## What is being measured

One step: given the operator's message and the session so far, emit the one tool call the
situation needs, with exact arguments. Three turns per session, and the arguments for turns
two and three come from the tool results of the turns before, so the step is replayed
closed-loop with the recorded tool outputs fed back after each call.

## Where the trajectories come from

`examples/tool-router/logs.jsonl`: 20 operator sessions as the copilot logs them: each
operator message, the call the copilot made and the operator approved, and what the tool
returned. The approved call is the ground truth; the tool return is what the next turn sees.
Nothing is executed during replay. Every model sees the same recorded world.

## Ground truth, per turn

| Turn | Operator says | Correct call | Check kind |
|---|---|---|---|
| 1 | a customer with email X is asking about their latest order | `lookup_customer(email=X)` | tool_call |
| 2 | pull up that latest order | `get_order(order_id=<first id from the turn-1 result>)` | tool_call |
| 3 | one of four requests | `issue_refund(order_id, amount_cents=<total or total/2>, reason)`, `update_address(customer_id, address)`, or `escalate(ticket_id, severity="high")` | tool_call |

Tool name must match and the arguments must be equal after JSON normalisation (key order
does not matter; string vs parsed object does not matter). `reason` and `severity` are enums
in the schema, so the match is exact. No LLM judge.

## Sample

20 trajectories, 60 turns. Turn 3 rotates through five each of: full refund (damaged), half
refund (late; the model must halve the recorded total), address update (the new address is
given verbatim in the message; the customer id is not), and escalation (ticket id given;
severity must be "high"). No constant call passes any turn, so the trivial baseline is 0%.

## Known limits

- The sessions are generated, so the operator's phrasing is regular. Real operators are
  terser and make typos in email addresses.
- A model that answers in text instead of calling a tool fails the turn and the replay
  continues with its text in the history. That is scored as the failure it is; it is not
  retried with a nudge, the way a production copilot might.
- Some OpenRouter providers do not serve tool calling for a given open model. The harness
  records the refusal on every call for that cell and prints a note; the row's 0% is a
  serving fact, not a model fact.
- Anthropic models return a tool call in one burst, so their TPOT and tok/s/user on this
  eval describe a very short decode and are not comparable with text-generation rows.

## Conditions to carry into every report

Reasoning effort requested: off (at low, Qwen3.6 spends the budget thinking on this shape
and returns nothing; models that refuse off fall back to low and the report notes it). Max tokens per
turn: 200. Concurrency: 2. Runs: 2; a copilot that gets a refund right once and wrong the
second time is the worst case, and consistency is how you see it.
