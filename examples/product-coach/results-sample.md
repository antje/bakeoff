# bakeoff results

## Conditions

- Date: 2026-09-21 02:53 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 20, turns per trajectory p50: 3
- Runs per trajectory: 2, concurrency: 2, max_tokens: 400
- Reasoning effort requested: off (applies to reasoning models only)
- TTFT p95 budget: none given
- Gate tolerance: 5% (cells this far below the best gate rate still contend)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 2193, output tokens p50: 18
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commit: 887df6c

Endpoint-level numbers. A provider's result is its serving stack, its hardware, and the network between here and there, under whatever load its fleet carries. Nothing here is a chip-level measurement.

## Per-cell endpoint facts

| model | provider | quantization | $/M in | $/M out |
|---|---|---|---|---|
| openai/gpt-oss-120b | auto | unknown | n/a | n/a |
| qwen/qwen3.6-35b-a3b | auto | unknown | n/a | n/a |
| anthropic/claude-sonnet-5 | auto | unknown | n/a | n/a |

## Results

| model | provider | gate | TTFT p50 | TTFT p95 | TPOT p50 | e2e p95 | tok/s/user | $/task | $/correct | consistency | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *trivial baseline* | *constant answer* | *48%* | | | | | | | | | |
| | (turn 1: decline, turn 2: none, turn 3: ex-004) | | | | | | | | | | |
| openai/gpt-oss-120b | auto | 60% | 1.25s | 4.65s | 13ms | 4.76s | 77 | $0.000714 | $0.000198 | 70% | 0 |
| qwen/qwen3.6-35b-a3b | auto | 46% | 0.78s | 1.63s | 8ms | 2.29s | 130 | $0.0014 | $0.000511 | 85% | 0 |
| anthropic/claude-sonnet-5 | auto | 62% | 1.57s | 2.24s | 33ms | 3.13s | 30 | $0.0352 | $0.0095 | 90% | 0 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to openai/gpt-oss-120b @ auto: gate 60% (within 5% of the best, 62%) at $0.000198 per correct call, the cheapest of 2 contender(s).

## Notes

- openai/gpt-oss-120b @ auto: 120 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
- openai/gpt-oss-120b @ auto: 1 call(s) hit max_tokens with no visible answer (reasoning consumed the budget); raise --max-tokens or use --reasoning off before trusting this row
