# Eval: ledger audit

Written by `/eval-build`. This is what a finished eval description looks like for a deep
multi-turn step where every answer depends on all the turns before it.

## What is being measured

One step: given the ledger spec, the opening balances, and every batch posted so far, answer
one exact question about the current position. Six turns per session. Turn six is only right
if the model carried the state correctly through turns one to five, which is why this eval
is replayed closed-loop and never as six independent prompts.

## Where the trajectories come from

`examples/ledger-audit/logs.jsonl`: 20 month-end sessions with each batch as posted and the
position the ledger system computed after it. The ledger system's figure is the ground
truth. The model never sees it; it sees only the batches.

## Ground truth, per turn

| Turn | Question | Correct when | Check kind |
|---|---|---|---|
| 1, 2, 4, 6 | balance of one named account | the first line contains the exact integer | pattern |
| 3 | how many non-REVERSE transactions so far had an amount above 500 | the first line contains the exact count | pattern |
| 5 | net change of one account since opening, negative if down | the first line contains the exact signed integer | pattern |

The pattern is anchored to the first line, tolerates a thousands separator, and rejects a
neighbouring number (`16533` does not pass for `16534`, `-250` does not pass for `250`).
No LLM judge.

## Sample

20 trajectories, 120 turns. Batches have 4 to 6 entries: transfers between three accounts,
fees, deposits, and (from turn two on) reversals of an earlier entry by id, each entry
reversible at most once. Every answer is a computed figure that varies per session, so no
constant passes and the trivial baseline is 0%.

## Known limits

- The arithmetic is small integers and the rules are stated in full in the system prompt.
  Real ledgers have currencies, dates, and rules nobody wrote down. The eval tests state
  carrying and exact arithmetic over a growing context, not accounting knowledge.
- One line of working is allowed after the answer. A model that puts the working first and
  the answer second fails the gate even when the answer is right; the prompt says first line,
  and a controller reading a column of answers needs it there.
- With reasoning on, the answer's TTFT includes thinking time. That is the honest number for
  this shape (the controller waits for the figure, not the first token of the working) and
  the conditions block records the effort level.

## Conditions to carry into every report

Reasoning effort requested: medium. This is the one example where a thinking budget is part
of the workload; the report records it, and a low-effort run is a different experiment.
Max tokens per turn: 400. Concurrency: 1; the history is long and the per-turn latency is
part of the story. Runs: 2; consistency is the column that separates a model that can do
this from one that sometimes does.
