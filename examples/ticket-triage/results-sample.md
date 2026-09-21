# bakeoff results

## Conditions

- Date: 2026-09-21 02:23 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 32, turns per trajectory p50: 2
- Runs per trajectory: 2, concurrency: 2, max_tokens: 200
- Reasoning effort requested: off (applies to reasoning models only)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 342, output tokens p50: 8
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commit: 9511afe

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
| *trivial baseline* | *constant answer* | *19%* | | | | | | | | | |
| | (turn 1: refunds, turn 2: pro) | | | | | | | | | | |
| openai/gpt-oss-20b | auto | 98% | 1.01s | 2.92s | 11ms | 2.94s | 86 | $0.000048 | $0.000012 | 97% | 0 |
| openai/gpt-oss-120b | auto | 98% | 0.68s | 2.09s | 12ms | 2.09s | 83 | $0.000092 | $0.000023 | 97% | 0 |
| qwen/qwen3.6-35b-a3b | auto | 100% | 0.59s | 1.17s | 6ms | 1.18s | 151 | $0.000123 | $0.000031 | 100% | 0 |
| anthropic/claude-sonnet-5 | auto | 100% | 1.47s | 1.86s | 113ms | 2.27s | 9 | $0.0034 | $0.000840 | 100% | 0 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to openai/gpt-oss-20b @ auto: gate 98% (within 5% of the best, 100%) at $0.000012 per correct call, the cheapest of 4 contender(s).

## Notes

- openai/gpt-oss-20b @ auto: 128 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
- openai/gpt-oss-120b @ auto: 128 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
