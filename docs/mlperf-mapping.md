# MLPerf agentic inference, and what bakeoff keeps

MLPerf Inference v6.1 (results September 2026) added two agentic benchmarks. Their design is the reference for bakeoff. Sources: [Agentic Inference for MLPerf Inference](https://mlcommons.org/2026/07/agentic-inference-for-mlperf-inference/), [Edge Agentic Inference](https://mlcommons.org/2026/07/mlperf-inference-v61-edge-agentic/), harness at [mlcommons/endpoints](https://github.com/mlcommons/endpoints).

## What MLPerf does

**Datacenter Agentic Inference.** 613 recorded multi-turn trajectories (113 coding, 500 workflow; about 30K turns), replayed closed-loop: one turn at a time, wait for the complete response, later turns carry the accumulated history. An `X-Session-ID` header per trajectory lets routers keep KV-cache locality. Two stress modes: coding (deep trajectories, growing context) and workflow (large shared prompt, prefix reuse). Accuracy gates are judge-free: tool-call action checks and intent-code checks against ground truth, plus a standalone slice of SWE-bench Verified. Performance is a Pareto curve of output tokens per second per system against output tokens per second per user. Models: Kimi K2.6 and Qwen3.6-35B-A3B. Runs against any OpenAI-compatible endpoint.

**Edge Agentic Inference.** Qwen3.6-27B at Q4_K_M. Accuracy gate is BFCL v4 (AST match, no LLM judge; pass at 0.97x the reference). Performance is a recorded agentic-coding replay, single-stream (one in-flight request), reporting TTFT, TPOT, end-to-end latency per turn, and input/output length distributions as p50/p90/p99.

## What bakeoff keeps

| Component | MLPerf | bakeoff |
|---|---|---|
| Trajectories | 613 recorded, curated | your agent's own, 20 to 50, in `bench/trajectories.jsonl` |
| Trajectory format | dataset schema | `{trajectory_id, system?, tools?, turns: [{input, expected: {tool_call \| label \| pattern}, tool_result?}]}` |
| Replay | closed-loop, history accumulates, session-sticky, recorded tool outputs fed back | same; `concurrency` knob, default 1 |
| Endpoint | OpenAI-compatible (vLLM, SGLang, TRT-LLM) | OpenRouter, or any OpenAI-compatible URL |
| Model axis | two fixed models | any models on OpenRouter |
| Silicon axis | whatever the submitter runs | same open model pinned to different providers (`provider.only`) |
| Accuracy gate | judge-free: action checks, intent codes, BFCL AST | judge-free: tool name + args match, label match; LLM judge optional and labeled |
| Performance | TTFT, TPOT, e2e per turn, p50/p90/p99; Pareto | TTFT, TPOT, e2e per turn, p50/p95; tokens/s per user |
| Cost | not measured | `usage.cost` per call, summed per task |
| Verdict | leaderboard | cost per correct call, per model and provider |
| Conditions | submission rules | a conditions block on every number: model + version, provider, date, n, concurrency, warm/cold, ISL/OSL p50 |

## What bakeoff does not claim

Endpoint-level numbers only. A provider's result is its serving stack plus its hardware plus the network in between, under whatever load the shared fleet is carrying. Quantization differs by provider and goes in the conditions block. Nothing here is a chip-level measurement, and the report says so.

## Same model, four silicon types (OpenRouter, September 2026)

`openai/gpt-oss-120b` is served on Cerebras (wafer-scale, fp16), Groq (LPU), SambaNova (RDU), and several NVIDIA-backed providers (Together, DeepInfra, Nebius, Baseten, CoreWeave; fp4 to bf16). One model, one flag, four architectures. Prices and quantizations change; the harness reads them from the endpoints API at run time rather than hardcoding them.
