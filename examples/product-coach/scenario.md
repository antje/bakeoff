# Worked example: product-coach's objection step

*A product coach's objection step. In: an experiment brief plus the team's past experiments. Out: object or not, the kind of objection, and the past experiments it cites.*

This is the scenario the skills load when you type `demo` at any prompt. It is a real
step from a real project, so every answer in `answers.md` is one a developer actually
had to give.

## The product, in three sentences

product-coach is a review layer for product decisions: coaching skills that argue with a
brief using the team's own experiment history, and a scoreboard that later checks whether
the objection was right. Its one model-backed step is the **objection**: given a new
experiment brief and the 50 experiments this team has already run, decide whether to
object, say what kind of objection it is, and cite the past experiments that justify it.
Everything else in the product is deterministic code.

## The step, as an inference workload

| Question the skills ask | Answer for this step |
|---|---|
| What goes in | a ~1,700-token system prompt (the rules plus the team's history) and a ~120-token brief |
| What comes out | a verdict (OBJECT or DECLINE), an objection type, and cited experiment ids |
| How often | about 40 reviews a day at a small team; bursts when someone is planning a quarter |
| Who waits | a product manager, in the browser, watching a spinner |
| Latency budget | first token under 2 s at p95, whole answer under 15 s; the PM will not wait longer |
| What "correct" means | the verdict matches what actually happened: an objection was right if the experiment went on to fail |
| Cost of being wrong | a wrong objection wastes a PM's afternoon; a missed one ships a bad bet for a quarter |

## Why this makes a good eval

The corpus behind product-coach was generated from a rule the coach never sees
(feeling-led changes fail on the early funnel; friction-removal wins), and every experiment
carries the lift that really happened. So the eval is **blind** (the model sees only what
the team knew at the time), **labelled** (the outcome is known), and **multi-turn** (verdict,
then type, then citations, with the history growing between turns). That is the shape MLPerf's
agentic-inference benchmark uses, on twenty conversations instead of six hundred.

One honesty note the demo says out loud: the labels come from a synthetic rule, so the
numbers show whether a model can read a history, not whether it is a good product coach.
The eval design is the point; the model verdict is illustrative.

## Files here

- `logs.jsonl` — 25 raw reviews in the shape a developer would have before building an eval
- `trajectories.jsonl` — the 20 three-turn conversations `/eval-build` produces from them
- `eval.md` — the finished eval description, to compare yours against
- `answers.md` — every interview answer, each with one line on why it is a good answer
- `results-sample.md` — a finished report from a real run, so the output shape is visible before spending anything
