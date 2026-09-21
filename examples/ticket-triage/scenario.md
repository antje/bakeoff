# Worked example: ticket triage

*A help desk's routing step. In: one support ticket. Out: which of eight queues it goes to, and the customer's plan tier.*

Load it with `demo ticket-triage` at any prompt in `/eval-build` or `/bakeoff`.

## The use case, in four sentences

Loopwire is a team analytics product with a help desk that receives about 2,000 tickets
a day. Before a human sees a ticket, a model routes it to one of eight queues and reads
the customer's plan tier off the signature so enterprise accounts jump the line. Nobody
waits on a single call; the ticket sits in a queue either way, so what the team feels is
the monthly bill and the misroute rate. A misroute costs one agent hand-off, about four
minutes, and at 2,000 tickets a day a 5% misroute rate is a full-time person.

## The step, as an inference workload

| Question the skills ask | Answer for this step |
|---|---|
| What goes in | a ~200-token routing policy and a 100 to 150-token ticket |
| What comes out | a queue name, then a plan tier: one word each |
| How often | ~2,000 a day, steady, bursts on Monday morning |
| Who waits | nobody; the ticket lands in a queue either way |
| Latency budget | none that matters; under 5 s end to end so the queue view stays live |
| What "correct" means | the queue a human agent eventually resolved it to; the plan tier the CRM has on file |
| Cost of being wrong | one hand-off between queues, about four agent-minutes |

## Why this shape is worth a bake-off

It is the most common inference workload there is and the easiest to overspend on. Every
capable model should be near the ceiling, so the interesting column is not the gate, it is
price per correct call: a frontier model buys nothing here that a small open model does
not already deliver. The verdict should land on the cheapest cell that clears the gate,
and the argument to have is whether the cheapest model's gate rate is *really* the same
or just within noise.

## Files here

- `logs.jsonl`: 32 tickets as a help desk exports them, with the resolved queue and the CRM plan
- `trajectories.jsonl`: the 32 two-turn conversations `/eval-build` produces from them
- `eval.md`: the finished eval description
- `answers.md`: every interview answer, each with one line on why it is a good answer
- `results-sample.md`: a finished report from a real run, four models
- `results-providers-sample.md`: the star baker on six providers, two of them as error rows

Regenerate with `uv run python scripts/examples/ticket_triage.py`.
