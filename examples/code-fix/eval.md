# Eval: code fix

Written by `/eval-build`. This is what a finished eval description looks like for a
code-generation step whose ground truth is a merged fix.

## What is being measured

One step: given a function, its spec, a failing test, and the CI output, name the bug
category, write the corrected function, and say what the corrected function returns on a
fresh input. Three turns, because a copilot that writes a fix it cannot trace has not
understood the bug, and that shows up as a second bug later.

## Where the trajectories come from

`examples/code-fix/logs.jsonl`: 20 pull requests in the shape CI and a reviewer leave
them: the function under review, the test that failed, the CI output, the fix that was
merged, and the category the reviewer labelled the bug with. The merged fix and the label
were decided by people, before any model ran, which is what makes them ground truth.

## Ground truth, per turn

| Turn | Question | Correct when | Check kind |
|---|---|---|---|
| 1 | Which bug category? | the first line names the reviewer's label (8 categories) | label |
| 2 | Write the corrected function | the reply contains the line the merged fix changed, or one of the equivalent spellings a reviewer would also merge | pattern |
| 3 | What does the corrected function return for this call? | the first line is the value the merged function returns | pattern |

No LLM judge. Turn 2 is a regular expression over the corrected line with whitespace
freedom and the accepted equivalents listed (for example `range(len(xs))`, `for x in xs:`,
or `accumulate(` for the off-by-one range). Turn 3 is the Python value on the first line,
with a tolerated `.0` on whole numbers and a quote style of the model's choosing on strings.

## Sample

20 trajectories, 60 turns. Eight bug families, two or three PRs each, with the identifiers
varied per PR so the same corrected line does not recur. Trivial baseline: 15% on turn 1
(the most common category), 0% on turn 2, 10% on turn 3 (the boolean answers), 8% overall.

## Known limits

- Turn 2 is checked by pattern, not by execution. A correct fix spelt some way the pattern
  does not list fails the gate; a wrong function that happens to contain the corrected line
  passes it. The first is the more likely error, so the gate is conservative. Executing the
  model's code against the test is the honest next step, and the harness does not do it.
- The eight families are the textbook ones. A real review queue has bugs that need the
  whole module to understand; this eval tests whether a model handles the shape (read a
  traceback, make a minimal edit, trace it), not whether it can debug a codebase.
- Turn 3 asks the model to trace its own fix, but the gate scores it against the merged
  fix. A model that wrote a different, wrong function and traced it faithfully fails turn 3
  for the right reason; a model that wrote the right function and traced it wrong also
  fails, and the report cannot tell the two apart.

## Conditions to carry into every report

Reasoning effort requested: low. Max tokens per turn: 600 (a whole function with room for
a sentence around it). Concurrency: 2; the author is not watching a spinner. Runs: 2, to
see whether a model's turn-2 misses are the same PRs each time.
