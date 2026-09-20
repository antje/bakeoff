# bakeoff

A bake-off for your agent: build an eval from your own workload, run it against any model on OpenRouter, decide by cost per correct call. MLPerf's agentic-inference benchmark shape, at developer scale, delivered as Claude Code skills plus a small replay harness.

## Layout

- `skills/<name>/SKILL.md` — the coaches. Symlinked into `~/.claude/skills/` by `./setup`.
- `harness/` — Python: closed-loop replay against OpenAI-compatible endpoints, accuracy gates, metrics, report.
- `bench/` — `trajectories.jsonl` (committed) and `results-<date>.json` / `.md` (gitignored).
- `docs/mlperf-mapping.md` — what MLPerf's agentic benchmark does and what the light version keeps.
- `scripts/check-skills.mjs` — structural lint for skills; `node --test scripts/check-skills-test.mjs` tests the linter.

## Skill conventions (enforced by the linter)

Same contract as product-coach. Every `SKILL.md` has: frontmatter `name` matching the directory and a `description` with two or more "Use when…" sentences and no method summary; an H1 `# /name, your <role>`; a `**What you refuse to do:**` line; `## When to use` with `**When not to use:**`; `## Stage gate`; numbered method sections; `## Common rationalizations` as a table with at least three rows; `## Red flags`; `## Verification` as checkboxes; `## Output contract`. No em dashes anywhere. Artifacts are written under `bench/`.

A skill is a coach, not a report generator: it interviews, applies a method by name, refuses the soft answer, and leaves a file behind.

## Harness conventions

- Python 3.11+, `from __future__ import annotations`, `uv` for everything, ruff clean.
- The `openai` SDK against `OPENROUTER_BASE_URL` (or `LOCAL_BASE_URL`). Provider pinning through `extra_body={"provider": {...}}`.
- Replay is closed-loop: one turn at a time, wait for the full response, accumulate history. `concurrency` defaults to 1.
- Streaming always, so TTFT is measured at the first content chunk; TPOT = (total - TTFT) / output tokens.
- Accuracy gates are deterministic (tool name + args match, label match). An LLM judge is optional and always labeled as such in the report.
- Cost comes from `usage.cost` in the final chunk, never from a price table, and is reported per task, not per call, when the workload is an agent.
- Every reported number carries a conditions block: model + version, provider, date, n, concurrency, warm or cold, input/output length p50. A number without conditions is not reported.
- Respect `BAKEOFF_MAX_RUN_USD`: estimate before running, refuse above the ceiling.

## Rules

- Never commit `.env` or any results file containing a key.
- Never add `Co-Authored-By` trailers to commits.
- Say what is measured and what is not. Endpoint-level numbers are endpoint-level; nothing here claims chip-level facts.
