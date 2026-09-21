# bakeoff results

## Conditions

- Date: 2026-09-21 02:45 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 20, turns per trajectory p50: 3
- Runs per trajectory: 1, concurrency: 2, max_tokens: 400
- Reasoning effort requested: low (applies to reasoning models only)
- TTFT p95 budget: none given
- Gate tolerance: 5% (cells this far below the best gate rate still contend)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 1930, output tokens p50: 84
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commit: 887df6c

Endpoint-level numbers. A provider's result is its serving stack, its hardware, and the network between here and there, under whatever load its fleet carries. Nothing here is a chip-level measurement.

## Per-cell endpoint facts

| model | provider | quantization | $/M in | $/M out |
|---|---|---|---|---|
| openai/gpt-oss-120b | cerebras | fp16 | 0.35 | 0.75 |
| openai/gpt-oss-120b | sambanova | unknown | 0.14 | 0.95 |
| openai/gpt-oss-120b | groq | unknown | 0.15 | 0.60 |
| openai/gpt-oss-120b | together | unknown | 0.15 | 0.60 |

## Results

| model | provider | gate | TTFT p50 | TTFT p95 | TPOT p50 | e2e p95 | tok/s/user | $/task | $/correct | consistency | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *trivial baseline* | *constant answer* | *48%* | | | | | | | | | |
| | (turn 1: decline, turn 2: none, turn 3: ex-004) | | | | | | | | | | |
| openai/gpt-oss-120b | cerebras | 63% | 0.33s | 0.63s | 1ms | 0.63s | 1612 | $0.0022 | $0.0012 | n/a | 0 |
| openai/gpt-oss-120b | sambanova | 52% | 0.43s | 0.72s | 1ms | 0.72s | 1230 | $0.0010 | $0.000661 | n/a | 0 |
| openai/gpt-oss-120b | groq | 45% | 0.40s | 0.93s | 2ms | 0.98s | 483 | $0.000689 | $0.000510 | n/a | 0 |
| openai/gpt-oss-120b | together | 52% | 0.85s | 1.66s | 6ms | 1.88s | 154 | $0.0010 | $0.000647 | n/a | 0 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to openai/gpt-oss-120b @ cerebras: gate 63% (within 5% of the best, 63%) at $0.0012 per correct call, the cheapest of 1 contender(s).
