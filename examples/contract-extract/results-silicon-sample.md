# bakeoff results

## Conditions

- Date: 2026-09-21 02:43 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 20, turns per trajectory p50: 3
- Runs per trajectory: 2, concurrency: 1, max_tokens: 200
- Reasoning effort requested: off (applies to reasoning models only)
- TTFT p95 budget: 2.0s (cells over it are not contenders)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 3753, output tokens p50: 25
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commit: 887df6c

Endpoint-level numbers. A provider's result is its serving stack, its hardware, and the network between here and there, under whatever load its fleet carries. Nothing here is a chip-level measurement.

## Per-cell endpoint facts

| model | provider | quantization | $/M in | $/M out |
|---|---|---|---|---|
| openai/gpt-oss-120b | cerebras | fp16 | 0.35 | 0.75 |
| openai/gpt-oss-120b | groq | unknown | 0.15 | 0.60 |
| openai/gpt-oss-120b | together | unknown | 0.15 | 0.60 |

## Results

| model | provider | gate | TTFT p50 | TTFT p95 | TPOT p50 | e2e p95 | tok/s/user | $/task | $/correct | consistency | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *trivial baseline* | *constant answer* | *0%* | | | | | | | | | |
| | (turn 1: none passes, turn 2: none passes, turn 3: none passes) | | | | | | | | | | |
| openai/gpt-oss-120b | cerebras | 99% | 0.29s | 0.55s | 1ms | 0.55s | 1546 | $0.0080 | $0.0013 | 98% | 0 |
| openai/gpt-oss-120b | groq | 99% | 0.38s | 0.58s | 2ms | 0.58s | 517 | $0.0032 | $0.000536 | 98% | 0 |
| openai/gpt-oss-120b | together | 100% | 0.41s | 0.63s | 5ms | 0.71s | 204 | $0.0035 | $0.000578 | 100% | 0 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to openai/gpt-oss-120b @ groq: gate 99% (within 5% of the best, 100%) at $0.000536 per correct call, the cheapest of 3 contender(s).

## Notes

- openai/gpt-oss-120b @ cerebras: 120 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
- openai/gpt-oss-120b @ groq: 120 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
- openai/gpt-oss-120b @ together: 120 call(s) ran at reasoning effort low because the endpoint refused to disable reasoning; this row's latency and cost include reasoning tokens
