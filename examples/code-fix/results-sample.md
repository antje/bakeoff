# bakeoff results

## Conditions

- Date: 2026-09-21 03:33 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 20, turns per trajectory p50: 3
- Runs per trajectory: 2, concurrency: 2, max_tokens: 600
- Reasoning effort requested: low (applies to reasoning models only)
- TTFT p95 budget: none given
- Gate tolerance: 5% (cells this far below the best gate rate still contend)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 536, output tokens p50: 44
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commit: 2961993

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
| *trivial baseline* | *constant answer* | *8%* | | | | | | | | | |
| | (turn 1: boundary, turn 2: none passes, turn 3: True) | | | | | | | | | | |
| openai/gpt-oss-20b | auto | 96% | 1.50s | 5.17s | 12ms | 6.49s | 82 | $0.000125 | $0.000022 | 92% | 0 |
| openai/gpt-oss-120b | auto | 98% | 0.93s | 7.73s | 13ms | 8.44s | 79 | $0.000268 | $0.000045 | 97% | 0 |
| qwen/qwen3.6-35b-a3b | auto | 74% | 2.63s | 9.95s | 6ms | 9.95s | 150 | $0.0023 | $0.000519 | 68% | 0 |
| anthropic/claude-sonnet-5 | auto | 97% | 1.29s | 2.93s | 69ms | 3.45s | 14 | $0.0088 | $0.0015 | 98% | 3 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to openai/gpt-oss-20b @ auto: gate 96% (within 5% of the best, 98%) at $0.000022 per correct call, the cheapest of 3 contender(s).

## Notes

- qwen/qwen3.6-35b-a3b @ auto: 29 call(s) hit max_tokens with no visible answer (reasoning consumed the budget); raise --max-tokens or use --reasoning off before trusting this row
- anthropic/claude-sonnet-5 @ auto: 3 call(s) errored and count as failed
