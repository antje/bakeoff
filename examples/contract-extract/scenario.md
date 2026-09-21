# Worked example: contract extraction

Load it with `demo contract-extract` at any prompt in `/eval-build` or `/bakeoff`.

## The use case, in four sentences

Meridian's procurement tool holds every signed services agreement, and a buyer preparing a
renewal asks it questions like "what is our notice period?" while looking at the contract on
screen. The model reads the whole agreement, about 4,500 tokens, and answers with one number
or one name. The buyer is watching a spinner, so time to first token is the entire experience,
and prefill is the entire cost. A wrong number goes straight into a renewal decision: miss a
90-day notice window and the contract renews for another year.

## The step, as an inference workload

| Question the skills ask | Answer for this step |
|---|---|
| What goes in | the full agreement (~18,500 characters, ~4,500 tokens) and a one-line question |
| What comes out | one number or one jurisdiction name, on the first line |
| How often | a few hundred a day, clustered around renewal season |
| Who waits | a buyer, in the browser, watching a spinner |
| Latency budget | first token under 2 s at p95; the answer is short so TTFT is nearly everything |
| What "correct" means | matches the field a paralegal keyed in from the same contract |
| Cost of being wrong | a missed notice window, a renewal nobody wanted, or a cap misquoted to legal |

## Why this shape is worth a bake-off

Prefill dominates, and prefill is where serving stacks differ most. The same open model on
four providers will show four different TTFTs on a 4,500-token prompt, and the price per
million *input* tokens, not output, sets the bill. It is also where small models start to
miss: the annual fee sits next to a setup fee, the notice period next to a cure period, the
liability cap next to an insurance minimum. The verdict should turn on TTFT p95 and input
price, and the argument is whether the fast, cheap cell is also the one that reads carefully.

## Files here

- `logs.jsonl`: 20 agreements with the fields a paralegal keyed in afterwards
- `trajectories.jsonl`: the 20 three-turn conversations `/eval-build` produces from them
- `eval.md`: the finished eval description
- `answers.md`: every interview answer, each with one line on why it is a good answer
- `results-sample.md`: a finished report from a real run

Regenerate with `uv run python scripts/examples/contract_extract.py`.
