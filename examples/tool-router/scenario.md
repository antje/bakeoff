# Worked example: tool router

Load it with `demo tool-router` at any prompt in `/eval-build` or `/bakeoff`.

## The use case, in four sentences

An online store's support copilot sits next to the operator and turns "refund her, it
arrived damaged" into the exact API calls the store's systems need. It has five tools:
look up a customer, fetch an order, issue a refund, update an address, escalate a ticket.
The right arguments are almost never in the operator's message: the customer id comes back
from the first lookup, the order id and total from the second, and a half refund means
dividing that total. A wrong argument is a wrong refund to a real card, so a near miss is
worse than a refusal, and the operator is waiting with the customer on the line.

## The step, as an inference workload

| Question the skills ask | Answer for this step |
|---|---|
| What goes in | a short system prompt, five tool schemas (~600 tokens), the conversation so far including tool results |
| What comes out | one tool call with exact arguments; no prose |
| How often | every operator message, a few thousand a day |
| Who waits | the operator, with the customer on chat or phone |
| Latency budget | whole call under 3 s at p95; the operator reads the proposed action before it runs |
| What "correct" means | the tool and arguments the operator approved in the session log |
| Cost of being wrong | a refund of the wrong amount, an address changed on the wrong account, an escalation that never happened |

## Why this shape is worth a bake-off

This is the agent case proper. Text fluency buys nothing; what is measured is whether the
model emits a syntactically exact call with arguments carried from earlier tool results,
turn after turn. Models differ sharply on that, and so do serving stacks: not every provider
serves tool calling for an open model, and the report says so as a note rather than a silent
zero. The verdict should land on tool-call fidelity first and price second, and the argument
is whether a cheap model that is right 90% of the time is acceptable when the other 10% are
refunds.

## Files here

- `logs.jsonl`: 20 operator sessions with the calls the copilot made and what each tool returned
- `trajectories.jsonl`: the 20 three-turn conversations `/eval-build` produces, tool schemas attached
- `eval.md`: the finished eval description
- `answers.md`: every interview answer, each with one line on why it is a good answer
- `results-sample.md`: a finished report from a real run

Regenerate with `uv run python scripts/examples/tool_router.py`.
