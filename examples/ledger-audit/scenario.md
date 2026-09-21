# Worked example: ledger audit

*A finance assistant's running-balance step. In: batches of postings and reversals, one per turn, six turns. Out: one exact figure about the current position after each batch.*

Load it with `demo ledger-audit` at any prompt in `/eval-build` or `/bakeoff`.

## The use case, in four sentences

A small company's finance assistant sits in the month-end review: the controller posts a
batch of transactions, asks for a position, posts the next batch, asks again, six times in
a session. Batches include reversals of earlier entries by id, so turn four reaches back to
turn two, and every answer depends on every batch before it. Nothing on any single turn is
hard; what is hard is being right on turn six, which only happens if turns one to five were
carried exactly. A wrong balance is an audit finding, and the controller will not notice
until the books do not close.

## The step, as an inference workload

| Question the skills ask | Answer for this step |
|---|---|
| What goes in | a short ledger spec with opening balances, then six batches of 4 to 6 transactions, history growing to ~2,500 tokens |
| What comes out | one integer on the first line: a balance, a count, or a net change |
| How often | a few sessions a day at month end; low volume, high stakes |
| Who waits | the controller, but with a spreadsheet open; ten seconds is fine |
| Latency budget | end to end under 15 s per turn; there is no spinner anxiety here |
| What "correct" means | the exact figure the ledger system computes for the same batches |
| Cost of being wrong | an audit finding, or a reserve transfer that was never made |

## Why this shape is worth a bake-off

This is the workload where "cheap is not cheap when wrong" stops being a slogan. Small
models are fast and nearly free per call, and their accuracy collapses somewhere between
turn three and turn six as the state they have to carry grows. Cost per *correct* call is
what the harness ranks, and it is the number that flips here: the expensive model wins on
price because the cheap ones are not producing correct calls. It is also where a reasoning
budget earns its tokens and where consistency across runs matters most. The verdict should
land on the model that is right; the argument is what that costs per month and whether a
mid-size model with more reasoning closes the gap.

## Files here

- `logs.jsonl`: 20 review sessions with every batch and the ledger's position after each
- `trajectories.jsonl`: the 20 six-turn conversations `/eval-build` produces from them
- `eval.md`: the finished eval description
- `answers.md`: every interview answer, each with one line on why it is a good answer
- `results-sample.md`: a finished report from a real run

Regenerate with `uv run python scripts/examples/ledger_audit.py`.
