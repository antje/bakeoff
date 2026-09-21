# Worked example: code fix

*A review copilot's fix step on a red CI run. In: the function, the failing test, and the CI output. Out: the kind of bug, the corrected function, and what it returns now.*

Load it with `demo code-fix` at any prompt in `/eval-build` or `/bakeoff`.

## The use case, in four sentences

Nightjar runs a review copilot on every pull request whose CI goes red. When a test fails,
the copilot reads the function, the test, and the CI output, names what kind of bug it is,
proposes the corrected function as a suggestion the author can accept in one click, and
answers the reviewer's "so what does it return now?" in the thread. The author is waiting
on the suggestion, but not by the second; what the team feels is how often the suggestion
is right, because a wrong suggestion accepted in one click is a second bug with a green
tick on it. Around 300 PRs a week go red.

## The step, as an inference workload

| Question the skills ask | Answer for this step |
|---|---|
| What goes in | a ~400-token system prompt, a 10-line function with its spec, a failing test, one line of CI output |
| What comes out | a category word, then a whole function (100 to 200 tokens), then a value |
| How often | ~300 a week, in bursts after each push |
| Who waits | the PR author, loosely; a suggestion that takes ten seconds is fine |
| Latency budget | 15 s end to end for the three turns |
| What "correct" means | the category the reviewer applied, the line the merged fix changed, the value the merged function returns |
| Cost of being wrong | a wrong suggestion merged in one click: a second bug, found later, by someone else |

## Why this shape is worth a bake-off

It is the first example here whose output is code. The tokens are on turn 2, so the bill
is output-heavy, and the shape separates three abilities that leaderboards blur: reading a
bug off a traceback (turn 1), writing the minimal fix without touching anything else (turn
2), and tracing the fixed code by hand (turn 3). Small models often get the first and miss
the third; the interesting rows are the ones where turn 2 passes and turn 3 fails, because
that is a copilot that emits fixes it does not understand.

## Files here

- `logs.jsonl`: 20 red PRs as CI and the reviewer leave them: source, failing test, CI output, the merged fix, the reviewer's label
- `trajectories.jsonl`: the 20 three-turn conversations `/eval-build` produces from them
- `eval.md`: the finished eval description
- `answers.md`: every interview answer, each with one line on why it is a good answer
- `results-sample.md`: a finished report from a real run, four models

Regenerate with `uv run python scripts/examples/code_fix.py`.
