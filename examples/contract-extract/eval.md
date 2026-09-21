# Eval: contract extraction

Written by `/eval-build`. This is what a finished eval description looks like for a
long-context, short-answer step.

## What is being measured

One step: given a signed master services agreement and one question, return the one value
the question asks for. Three questions per agreement, asked in sequence, so turns two and
three see the earlier answers the way a buyer's session does.

## Where the trajectories come from

`examples/contract-extract/logs.jsonl`: 20 agreements as the procurement tool stores them,
each with six fields a paralegal keyed in afterwards: annual fee, notice period, governing
law, renewal term, retention clause number, liability cap. The keyed fields are the ground
truth; each trajectory asks for three of the six, rotating so every field is asked ten times
across the set.

## Ground truth, per turn

| Turn | Question (one of six) | Correct when | Check kind |
|---|---|---|---|
| any | annual fee, liability cap | the first line contains the amount, with or without a thousands separator | pattern |
| any | notice days, renewal months | the first line contains the number as a whole word | pattern |
| any | governing law | the first line contains the jurisdiction name | pattern |
| any | retention clause | the first line contains the clause number, e.g. 7.3 | pattern |

No LLM judge. Every pattern is anchored to the first line (`^\s*[^\n]*\b...\b`), so a reply
that recites every number in the contract does not pass by accident.

## Sample

20 trajectories, 60 turns. Every planted value is drawn per agreement, so no constant answer
passes and the trivial baseline is 0%. Distractors sit next to every planted fact: a setup
fee beside the annual fee, a cure period and an audit notice beside the termination notice,
an insurance minimum beside the liability cap, an initial term beside the renewal term. The
data protection section moves between positions 5 and 10, so the clause number has to be
read, not remembered.

## Known limits

- The agreements are assembled from one set of clause templates. Real contracts vary in
  structure, and a model that learns the template between turns has an advantage a real
  buyer's tool would not give it. Three questions per contract limits that.
- Small-number answers (a 30-day notice period) are more forgiving than large ones: a reply
  that says "30 days, though the cure period is 15" passes. The first-line anchor and the
  "number only" instruction keep that rare, not impossible.
- The retention clause question depends on the model numbering clauses the way the document
  does. A reply of "the Retention clause under Data Protection" is right and fails the gate.

## Conditions to carry into every report

Reasoning effort requested: off (models that refuse fall back to low; the report notes it). Max tokens per turn: 200. Concurrency: 1 for per-user
TTFT, which is the number this step lives on. Runs: 2. Pin providers on the open model:
this is the shape where they differ.
