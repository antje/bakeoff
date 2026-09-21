# bakeoff results

## Conditions

- Date: 2026-09-21 03:05 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 12, turns per trajectory p50: 6
- Runs per trajectory: 2, concurrency: 6, max_tokens: 1200
- Reasoning effort requested: medium (applies to reasoning models only)
- TTFT p95 budget: none given
- Gate tolerance: 5% (cells this far below the best gate rate still contend)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 597, output tokens p50: 709
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commit: 887df6c

Endpoint-level numbers. A provider's result is its serving stack, its hardware, and the network between here and there, under whatever load its fleet carries. Nothing here is a chip-level measurement.

## Per-cell endpoint facts

| model | provider | quantization | $/M in | $/M out |
|---|---|---|---|---|
| openai/gpt-oss-20b | auto | unknown | n/a | n/a |
| openai/gpt-oss-120b | auto | unknown | n/a | n/a |
| qwen/qwen3.6-35b-a3b | auto | unknown | n/a | n/a |
| anthropic/claude-sonnet-5 | auto | unknown | n/a | n/a |

## Results

| model | provider | gate | TTFT p50 | TTFT p95 | TPOT p50 | e2e p95 | tok/s/user | $/task | $/correct | consistency | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *trivial baseline* | *constant answer* | *0%* | | | | | | | | | |
| | (turn 1: none passes, turn 2: none passes, turn 3: none passes, turn 4: none passes, turn 5: none passes, turn 6: none passes) | | | | | | | | | | |
| openai/gpt-oss-20b | auto | 72% | 10.46s | 20.13s | 12ms | 20.51s | 82 | $0.0016 | $0.000187 | 79% | 0 |
| openai/gpt-oss-120b | auto | 69% | 8.41s | 30.15s | 13ms | 30.15s | 80 | $0.0033 | $0.000399 | 81% | 0 |
| qwen/qwen3.6-35b-a3b | auto | 14% | 8.26s | 17.31s | 6ms | 18.12s | 166 | $0.0148 | $0.0089 | 75% | 0 |
| anthropic/claude-sonnet-5 | auto | 85% | 5.09s | 8.19s | 6ms | 8.19s | 158 | $0.0406 | $0.0040 | 82% | 1 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to anthropic/claude-sonnet-5 @ auto: gate 85% (within 5% of the best, 85%) at $0.0040 per correct call, the cheapest of 1 contender(s).

## Notes

- openai/gpt-oss-20b @ auto: 40 call(s) hit max_tokens with no visible answer (reasoning consumed the budget); raise --max-tokens or use --reasoning off before trusting this row
- openai/gpt-oss-120b @ auto: 42 call(s) hit max_tokens with no visible answer (reasoning consumed the budget); raise --max-tokens or use --reasoning off before trusting this row
- qwen/qwen3.6-35b-a3b @ auto: 115 call(s) hit max_tokens with no visible answer (reasoning consumed the budget); raise --max-tokens or use --reasoning off before trusting this row
- anthropic/claude-sonnet-5 @ auto: 1 call(s) errored and count as failed
