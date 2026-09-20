# Eval: product-coach objection step

Written by `/eval-build`. This is what a finished eval description looks like; compare yours
against it.

## What is being measured

One step: given a new experiment brief and the team's history of completed experiments,
decide whether to object, name the objection type, and cite supporting experiments. The
step is replayed as a three-turn conversation so that the type and citation turns see the
verdict turn's answer, the way they do in the product.

## Where the trajectories come from

`examples/product-coach/logs.jsonl`: 25 real reviews from product-coach's corpus. The 20
most recent were kept, because each of those could see at least 30 earlier experiments, which
is enough history for the objection to have something to stand on. Earlier reviews would
mostly decline for lack of evidence and would measure nothing.

Each trajectory's system prompt contains only experiments that had **read out before the
brief was written**. The model never sees the future. That is the as-of guard, and it is
what makes the eval blind.

## Ground truth, per turn

| Turn | Question | Correct when | Check kind |
|---|---|---|---|
| 1 | OBJECT or DECLINE? | OBJECT if the experiment's actual lift was at or below +0.5pp, otherwise DECLINE | label |
| 2 | Which objection type, or NONE? | `repeated-mechanism` for a feeling-led change on the early funnel that failed; `assumed-causation` for other failures; `none` for a decline | label |
| 3 | Cite up to three supporting ids | at least one cited id exists in the history the model was shown | pattern |

No LLM judge. Every check is a string or regex comparison a human can re-run.

## Sample

20 trajectories, 60 turns. Expected verdicts: 8 OBJECT, 12 DECLINE. Turn-1 pass rate for a
model that always says DECLINE would be 60%, so anything near 60% on turn 1 means the model
is not reading the history.

## Known limits

- The outcomes were generated from a synthetic rule (feeling-led changes fail on the early
  funnel; friction-removal wins). The eval tests whether a model reads a history, not whether
  it is a good product coach.
- The citation check is lenient: it confirms the ids are real, not that they are the *best*
  ids. A stricter version would require the cited experiments to share the brief's mechanism
  or audience.
- Turn 1 has a short answer; TTFT dominates its latency. Turn 3 has the longest history.

## Conditions to carry into every report

Reasoning effort requested: low. Max tokens per turn: 300 is enough (the longest correct
answer is a three-id list plus one sentence). Concurrency: 1 for per-user latency.
