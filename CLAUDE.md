# bakeoff

A bake-off for your agent: build an eval from your own workload, run it against any model on OpenRouter, decide by cost per correct call. MLPerf's agentic-inference benchmark shape, at developer scale, delivered as Claude Code skills plus a small replay harness.

## Layout

- `skills/<name>/SKILL.md` — the coaches. Symlinked into `~/.claude/skills/` by `./setup`.
- `harness/` — Python: closed-loop replay against OpenAI-compatible endpoints, accuracy gates, metrics, candidate shortlist, cost estimate, report. `bench.py` is the CLI.
- `examples/<name>/` — six worked examples, one per workload shape (`product-coach`, `ticket-triage`, `contract-extract`, `tool-router`, `ledger-audit`, `code-fix`). Each has `scenario.md`, `logs.jsonl`, `trajectories.jsonl`, `eval.md`, `answers.md` (what `demo <name>` loads in the skills), and `results-*-sample.md` (real reports, kept). `examples/README.md` is the cross-example table.
- `scripts/examples/<name>.py` — deterministic generators for every example except `product-coach` (that one is `scripts/convert_product_coach.py`, from the product-coach corpus). `tests/test_examples.py` checks the committed files match the generator output.
- `bench/` — where the skills write `trajectories.jsonl` and `eval.md` and where `results-<stamp>.json` / `.md` land (`--out bench/<name>` for a named run). Everything under it except `.gitkeep` is gitignored; a report worth keeping is copied to `examples/<name>/results-*-sample.md`.
- `docs/mlperf-mapping.md` — what MLPerf's agentic benchmark does and what the light version keeps.
- `assets/`, `DESIGN.md` — the mark, icons, and the design rules for any surface that prints a number.
- `scripts/check-skills.mjs` — structural lint for skills; `node --test scripts/check-skills-test.mjs` tests the linter. `scripts/render-assets.sh` re-renders the icon PNGs.
- `tests/` — `uv run pytest`; gate, metrics, replay (fake client), estimate, candidates, models, examples.

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
- Every reported number carries a conditions block: model + version, provider, date, n, concurrency, runs, max_tokens, reasoning effort, TTFT budget, gate tolerance, warm or cold, input/output length p50, harness commit. A number without conditions is not reported.
- The verdict is computed, never chosen: cheapest cell by cost per correct call among those within `--tolerance` (default 0.05) of the best gate rate, above the trivial baseline, and inside `--ttft-budget` if one was given. The report names the cells it dropped and why. When a condition would leave no cell (a four-trajectory demo under the baseline, a budget nothing meets), the verdict is still computed and opens with `Provisional (...)` naming the failed condition; it is never withheld.
- The trivial baseline (best constant answer per turn) is the first row of every table. A gate a constant can pass is not a gate; fix the gate in the generator, never loosen it after a run.
- Respect `BAKEOFF_MAX_RUN_USD`: estimate before running, refuse above the ceiling. Without a TTY (a skill running the CLI) the confirmation prompt is skipped; the ceiling still applies.
- New example generators go in `scripts/examples/`, use `_common.py` (`rng`, `write_example`), build ground truth by construction, and get a row in `tests/test_examples.py::GENERATORS`. Identifiers vary per trajectory so no constant answer passes.

## Rules

- Never commit `.env` or any results file containing a key.
- Never add `Co-Authored-By` trailers to commits.
- Say what is measured and what is not. Endpoint-level numbers are endpoint-level; nothing here claims chip-level facts.
