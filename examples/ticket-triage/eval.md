# Eval: ticket triage

Written by `/eval-build`. This is what a finished eval description looks like for a short,
high-volume classification step.

## What is being measured

One step: given the routing policy and one inbound ticket, name the queue it belongs to,
then name the plan tier the customer is on. Two turns, so the second answer is read from a
ticket the model has already processed once, the way the copilot does it in production.

## Where the trajectories come from

`examples/ticket-triage/logs.jsonl`: 32 tickets in the shape a help desk exports them:
subject, body, the queue a human agent eventually resolved the ticket to, and the plan tier
from the CRM. Both outcomes were recorded by something other than the model, which is what
makes them ground truth.

## Ground truth, per turn

| Turn | Question | Correct when | Check kind |
|---|---|---|---|
| 1 | Which queue? | the first line names the queue the ticket was resolved to (8 queues) | label |
| 2 | Which plan? | the first line names the CRM plan tier (free, pro, team, enterprise) | label |

No LLM judge. Both checks are a whole-word comparison on the first line of the reply.

## Sample

32 trajectories, 64 turns. Four tickets per queue, eight per plan, and every queue has one
ticket per plan, so the two answers are independent. Trivial baseline: 12.5% on turn 1,
25% on turn 2, 19% overall. Anything near that means the model is not reading the ticket.

## Known limits

- The tickets are generated from templates: one queue-specific cue, one detail, one neutral
  distractor, one plan mention. Real tickets are messier and longer. The eval tests whether a
  model applies a written policy to a short text, not whether it survives real-world noise.
- Two of the queues (billing, refunds) are separated by one fact: whether the customer asks
  for money back. That is deliberate; it is where real triage goes wrong too.
- The plan tier is always stated in the ticket. A production version would also have to
  handle its absence.

## Conditions to carry into every report

Reasoning effort requested: off (models that refuse fall back to low; the report notes it). Max tokens per turn: 200 (a one-word answer plus a short
sentence). Concurrency: 2 is fine; nobody is waiting on one stream. Runs: 2, to see whether
the cheapest model is stable at the ceiling or flickering around it.
