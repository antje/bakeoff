# bakeoff results

## Conditions

- Date: 2026-09-21 02:10 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 20, turns per trajectory p50: 3
- Runs per trajectory: 2, concurrency: 2, max_tokens: 200
- Reasoning effort requested: low (applies to reasoning models only)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 712, output tokens p50: 58
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
| openai/gpt-oss-20b | auto | 84% | 2.05s | 7.42s | 15ms | 7.63s | 65 | $0.000078 | $0.000015 | 95% | 0 |
| openai/gpt-oss-120b | auto | 98% | 1.44s | 3.41s | 21ms | 4.95s | 48 | $0.000151 | $0.000026 | 100% | 0 |
| qwen/qwen3.6-35b-a3b | auto | 86% | 1.56s | 2.91s | 10ms | 3.29s | 96 | $0.0017 | $0.000325 | 78% | 0 |
| anthropic/claude-sonnet-5 | auto | 100% | 1.66s | 3.34s | 5ms | 3.38s | 210 | $0.0197 | $0.0033 | 100% | 0 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to openai/gpt-oss-120b @ auto: gate 98% (within 5% of the best, 100%) at $0.000026 per correct call, the cheapest of 2 contender(s).

## Notes

- qwen/qwen3.6-35b-a3b @ auto: 14 call(s) hit max_tokens with no visible answer (reasoning consumed the budget); raise --max-tokens or use --reasoning off before trusting this row
