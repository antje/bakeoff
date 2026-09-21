# bakeoff results

## Conditions

- Date: 2026-09-21 02:38 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 20, turns per trajectory p50: 3
- Runs per trajectory: 2, concurrency: 1, max_tokens: 200
- Reasoning effort requested: off (applies to reasoning models only)
- TTFT p95 budget: 2.0s (cells over it are not contenders)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 3788, output tokens p50: 21
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
| *trivial baseline* | *constant answer* | *0%* | | | | | | | | | |
| | (turn 1: none passes, turn 2: none passes, turn 3: none passes) | | | | | | | | | | |
| openai/gpt-oss-20b | auto | 99% | 1.26s | 4.53s | 13ms | 4.65s | 76 | $0.000658 | $0.000111 | 98% | 0 |
| openai/gpt-oss-120b | auto | 100% | 0.81s | 1.91s | 11ms | 2.03s | 88 | $0.0011 | $0.000185 | 100% | 0 |
| qwen/qwen3.6-35b-a3b | auto | 100% | 0.82s | 2.90s | 5ms | 3.53s | 208 | $0.0025 | $0.000419 | 100% | 0 |
| anthropic/claude-sonnet-5 | auto | 97% | 1.60s | 2.45s | 111ms | 2.66s | 9 | $0.0757 | $0.0131 | 100% | 0 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to openai/gpt-oss-120b @ auto: gate 100% (within 5% of the best, 100%) at $0.000185 per correct call, the cheapest of 1 contender(s). Over the 2.0s TTFT p95 budget and not considered: openai/gpt-oss-20b @ auto (4.53s), qwen/qwen3.6-35b-a3b @ auto (2.90s), anthropic/claude-sonnet-5 @ auto (2.45s).

## Notes

- openai/gpt-oss-20b @ auto: 120 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
- openai/gpt-oss-120b @ auto: 120 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
