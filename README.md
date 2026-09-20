# bakeoff

**A bake-off for your agent.** Build an eval from your own workload, run it against any model on OpenRouter, decide by cost per correct call.

MLCommons just shipped agentic-inference benchmarks for MLPerf: recorded multi-turn trajectories replayed closed-loop, judge-free accuracy gates, TTFT and TPOT as percentiles, a Pareto of tokens per second per user against tokens per second per system. That is the right shape. It is also 613 trajectories, a submission process, and a membership. bakeoff keeps the shape and drops the ceremony: your agent's last 20 to 50 conversations, any model on OpenRouter, an afternoon.

Two things come out of it:

| | What it does | Where it runs |
|---|---|---|
| **The skills** | `/eval-build` turns your agent's logs into labeled trajectories and refuses to proceed without enough of them. `/bakeoff` runs the harness and refuses to report a number without its conditions. | Claude Code, in your own repo |
| **The harness** | Closed-loop replay against OpenAI-compatible endpoints, deterministic accuracy gates, TTFT/TPOT/cost percentiles, a routing verdict, a conditions block. | `uv run` |

Same model, different silicon is one flag away: OpenRouter serves the same open weights on Cerebras, Groq, SambaNova, and NVIDIA-backed providers, and `provider.only` picks which. The numbers are endpoint-level and say so.

## Install

```bash
git clone https://github.com/antje/bakeoff && cd bakeoff
cp .env.example .env        # add OPENROUTER_API_KEY
uv sync
./setup                     # symlinks skills/* into ~/.claude/skills/
```

## Status

Scaffold. No skills or harness code yet. See `docs/mlperf-mapping.md` for the design.
