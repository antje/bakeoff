# bakeoff results

## Conditions

- Date: 2026-09-20 22:37 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 20, turns per trajectory p50: 3
- Runs per trajectory: 1, concurrency: 2, max_tokens: 400
- Reasoning effort requested: low (applies to reasoning models only)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 1920, output tokens p50: 84
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commit: a90b5d0

Endpoint-level numbers. A provider's result is its serving stack, its hardware, and the network between here and there, under whatever load its fleet carries. Nothing here is a chip-level measurement.

## Per-cell endpoint facts

| model | provider | quantization | $/M in | $/M out |
|---|---|---|---|---|
| openai/gpt-oss-120b | cerebras | fp16 | 0.35 | 0.75 |
| openai/gpt-oss-120b | groq | unknown | 0.15 | 0.60 |
| openai/gpt-oss-120b | sambanova | unknown | 0.14 | 0.95 |
| openai/gpt-oss-120b | together | unknown | 0.15 | 0.60 |

## Results

| model | provider | gate | TTFT p50 | TTFT p95 | TPOT p50 | e2e p95 | tok/s/user | $/task | $/correct | consistency | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-oss-120b | cerebras | 68% | 0.36s | 0.56s | 1ms | 0.57s | 1428 | $0.0022 | $0.0011 | n/a | 0 |
| openai/gpt-oss-120b | groq | 78% | 0.50s | 0.86s | 2ms | 0.87s | 480 | $0.0008 | $0.0003 | n/a | 0 |
| openai/gpt-oss-120b | sambanova | 67% | 0.43s | 0.86s | 1ms | 0.88s | 1102 | $0.0010 | $0.0005 | n/a | 0 |
| openai/gpt-oss-120b | together | 77% | 0.67s | 1.08s | 4ms | 1.18s | 251 | $0.0010 | $0.0004 | n/a | 0 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate.

## Verdict

Route to openai/gpt-oss-120b @ groq: gate 78% (within 5% of the best, 78%) at $0.0003 per correct call, the cheapest of 2 contender(s).
