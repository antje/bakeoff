# bakeoff results: one model, six providers

Two reports stitched into one table, because the first pass pinned a provider that does not
serve this model (Together: 400 on every call) and one that rate-limited upstream
(DeepInfra: 429 on 75 of 128 calls), and the second pass added three more. Both passes are
kept as run in `bench/triage-providers/` and `bench/triage-providers2/`. The rows are
comparable on gate and cost; latency rows from the second pass were measured one stream at a
time instead of two, which is recorded below because it favours them slightly.

## Conditions

- Date: 2026-09-21 03:06 and 03:20 (UTC)
- Endpoint: https://openrouter.ai/api/v1
- Trajectories: 32, turns per trajectory p50: 2
- Runs per trajectory: 2; concurrency: 2 (groq, together, deepinfra, coreweave), 1 (novita, siliconflow, deepinfra retry); max_tokens: 200
- Reasoning effort requested: off (every endpoint refused and ran at low; see notes)
- TTFT p95 budget: none given
- Gate tolerance: 5% (cells this far below the best gate rate still contend)
- Cache state: cold (the harness never pre-warms)
- Input tokens p50: 339, output tokens p50: 18
- Timings are client-side wall clock and include network time
- Accuracy gate: deterministic (no judge)
- Harness commits: 887df6c, 2961993

Endpoint-level numbers. A provider's result is its serving stack, its hardware, and the network between here and there, under whatever load its fleet carries. Nothing here is a chip-level measurement.

## Per-cell endpoint facts

| model | provider | quantization | $/M in | $/M out |
|---|---|---|---|---|
| openai/gpt-oss-20b | groq | unknown | 0.07 | 0.30 |
| openai/gpt-oss-20b | coreweave | fp4 | 0.03 | 0.13 |
| openai/gpt-oss-20b | novita | fp4 | 0.04 | 0.15 |
| openai/gpt-oss-20b | siliconflow | fp8 | 0.04 | 0.18 |
| openai/gpt-oss-20b | deepinfra | bf16 | 0.03 | 0.14 |
| openai/gpt-oss-20b | together | unknown | 0.05 | 0.20 |

## Results

| model | provider | gate | TTFT p50 | TTFT p95 | TPOT p50 | e2e p95 | tok/s/user | $/task | $/correct | consistency | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *trivial baseline* | *constant answer* | *19%* | | | | | | | | | |
| | (turn 1: refunds, turn 2: pro) | | | | | | | | | | |
| openai/gpt-oss-20b | groq | 98% | 0.28s | 0.52s | 1ms | 0.53s | 881 | $0.000127 | $0.000032 | 97% | 0 |
| openai/gpt-oss-20b | coreweave | 97% | 0.22s | 0.55s | 5ms | 0.57s | 185 | $0.000052 | $0.000013 | 94% | 0 |
| openai/gpt-oss-20b | novita | 99% | 0.73s | 1.33s | 12ms | 1.33s | 84 | $0.000067 | $0.000017 | 98% | 0 |
| openai/gpt-oss-20b | siliconflow | 98% | 2.90s | 6.60s | 33ms | 6.61s | 30 | $0.000103 | $0.000026 | 97% | 0 |
| openai/gpt-oss-20b | deepinfra | 39% | 0.59s | 2.43s | 6ms | 2.44s | 178 | $0.000021 | $0.000014 | 97% | 77 |
| openai/gpt-oss-20b | together | 0% | | | | | | n/a | n/a | n/a | 128 |

TTFT: time to first token. TPOT: time per output token. e2e: end-to-end latency per turn. tok/s/user: output tokens per second for one stream. $/task: cost summed over a trajectory. $/correct: total cost divided by calls that passed the gate. trivial baseline: what a constant answer per turn scores; the zero of the gate column.

## Verdict

Route to openai/gpt-oss-20b @ coreweave: gate 97% (within 5% of the best, 99%) at $0.000013 per correct call, the cheapest of 4 contender(s).

## Notes

- Every endpoint refused to disable reasoning and ran at effort low; each row's latency and cost include reasoning tokens.
- openai/gpt-oss-20b @ together: "Unable to access non-serverless model openai/gpt-oss-20b" (HTTP 400) on all 128 calls. This model is not on Together's serverless tier; pinning it there is a configuration error the harness surfaces as a failed cell instead of silently routing elsewhere.
- openai/gpt-oss-20b @ deepinfra: "temporarily rate-limited upstream" (HTTP 429) on 75 of 128 calls at concurrency 2 and 77 of 128 at concurrency 1, on two passes fourteen minutes apart. The calls that went through scored 100% on both passes. A rate limit is a serving fact on that date, not a model fact; it is reported as errors, not dropped.
- What moved and what did not, on the same weights: gate 97 to 99% on every endpoint that answered, including both fp4 endpoints. Tokens per second 30 to 881, a 30x spread. TTFT p50 0.22 s to 2.90 s. Cost per correct call 2.5x from cheapest to priciest.
