# bakeoff results

## Conditions

- Date: 2026-09-20 22:36 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 20, turns per trajectory p50: 3
- Runs per trajectory: 2, concurrency: 2, max_tokens: 400
- Reasoning effort requested: off (applies to reasoning models only)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 2200, output tokens p50: 18
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commit: a90b5d0

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
| openai/gpt-oss-120b | auto | 68% | 1.73s | 10.03s | 16ms | 11.00s | 62 | $0.0006 | $0.0002 | 72% | 0 |
| qwen/qwen3.6-35b-a3b | auto | 57% | 0.45s | 1.42s | 4ms | 1.65s | 271 | $0.0014 | $0.0004 | 83% | 0 |
| anthropic/claude-sonnet-5 | auto | 68% | 1.48s | 1.98s | 29ms | 3.04s | 34 | $0.0353 | $0.0086 | 97% | 0 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate.

## Verdict

Route to openai/gpt-oss-120b @ auto: gate 68% (within 5% of the best, 68%) at $0.0002 per correct call, the cheapest of 2 contender(s).

## Notes

- openai/gpt-oss-120b @ auto: 120 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
- openai/gpt-oss-120b @ auto: 1 call(s) hit max_tokens with no visible answer (reasoning consumed the budget); raise --max-tokens or use --reasoning off before trusting this row
