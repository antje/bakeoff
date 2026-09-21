"""Build the worked example from product-coach's experiment corpus.

What this produces, under examples/product-coach/:

- logs.jsonl: the raw material a developer would actually have. One line per
  past review: the brief the coach saw, the history it could see at the time
  (only experiments that had read out before that date), and what really
  happened afterwards. This is the "before /eval-build" state.
- trajectories.jsonl: the "after /eval-build" state. Each review becomes a
  three-turn conversation with ground truth per turn, so the harness has
  something to gate on and the history grows the way an agent's does.

Why product-coach. Its corpus was generated from a rule the coach never sees
(feeling-led changes fail on the early funnel, friction-removal wins), and
every experiment carries the lift that actually happened. That gives a
labelled, blind, multi-turn eval for free, which is exactly what MLPerf's
agentic benchmark needs and what most developers think they do not have.

The ground truth, in one sentence: an objection was *right* if the experiment
went on to fail. So the expected verdict for a brief is OBJECT when its actual
lift was flat or negative, and DECLINE when it went on to work. The objection
type is the corpus rule stated as a category. The citation turn checks that
the model cites a precedent that actually supports the call: a past experiment
with the same mechanism whose outcome matches the verdict (failed for OBJECT,
worked for DECLINE); when the history has none, the same audience with that
outcome; when it has none of those either, any past experiment with that
outcome. "Any id in the history" was the first version of this gate, and a
constant answer of ex-001 passed it every time, which the harness's trivial
baseline row made visible. A gate a constant can pass is not a gate.

Run:  uv run python scripts/convert_product_coach.py [path/to/corpus.ts]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_CORPUS = Path.home() / "product-school/product-coach/lib/data/corpus.ts"
OUT_DIR = Path(__file__).resolve().parent.parent / "examples" / "product-coach"

FEELING_LED = {"personalization", "social-proof", "urgency", "incentive"}
EARLY_FUNNEL_AUDIENCES = {"new-workspaces", "trial-day-7"}
EARLY_FUNNEL_METRICS = {"activation rate", "trial conversion"}
FLAT_LIFT_PP = 0.5  # at or below this the experiment "did not work"

SYSTEM_RULES = (
    "You are a product coach reviewing an experiment brief against this team's own "
    "history of completed experiments. Object only when the history gives you a reason. "
    "Answer each question exactly in the format asked, with no preamble."
)

# A field is `key: 'string'`, `key: "string"` (used when the value has an
# apostrophe), or `key: number`. Group 2 or 3 holds the string, group 4 the number.
FIELD = re.compile(r"(\w+):\s*(?:'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"|(-?\d+(?:\.\d+)?))")


def parse_corpus(text: str) -> list[dict]:
    """Pull every experiment object literal out of corpus.ts.

    The file is TypeScript, not JSON, but each entry is a flat object of
    quoted strings and numbers, so a field regex is enough and avoids a
    TypeScript dependency. Multi-line hypotheses are joined first.
    """
    body = text.split("export const EXPERIMENTS", 1)[1]
    body = re.sub(r"\n\s+", " ", body)
    experiments = []
    for block in re.findall(r"\{\s*id: '(?:[^}]*)\}", body):
        fields: dict = {}
        for key, single_quoted, double_quoted, number_value in FIELD.findall(block):
            if number_value != "":
                fields[key] = float(number_value)
            else:
                fields[key] = single_quoted or double_quoted
        if "id" in fields:
            experiments.append(fields)
    experiments.sort(key=lambda e: e["readDate"])
    return experiments


def expected_verdict(experiment: dict) -> str:
    """OBJECT if the experiment went on to fail, else DECLINE."""
    return "object" if experiment["actualLiftPp"] <= FLAT_LIFT_PP else "decline"


def expected_type(experiment: dict) -> str:
    """The objection category the corpus rule implies, or NONE when declining."""
    if expected_verdict(experiment) == "decline":
        return "none"
    early = (
        experiment["audience"] in EARLY_FUNNEL_AUDIENCES
        and experiment["primaryMetric"].lower() in EARLY_FUNNEL_METRICS
    )
    if early and experiment["mechanism"] in FEELING_LED:
        return "repeated-mechanism"
    return "assumed-causation"


def render_history(history: list[dict]) -> str:
    """One compact line per past experiment, the same fields a real export would carry."""
    rows = [
        f"{e['id']} | {e['readDate']} | {e['name']} | {e['mechanism']} | {e['audience']} | "
        f"{e['primaryMetric']} | expected +{e['expectedLiftPp']:.1f}pp | actual {e['actualLiftPp']:+.1f}pp"
        for e in history
    ]
    return "Completed experiments (oldest first):\n" + "\n".join(rows)


def render_brief(e: dict) -> str:
    return (
        f"Brief: {e['name']}\nHypothesis: {e['hypothesis']}\nMechanism: {e['mechanism']}\n"
        f"Audience: {e['audience']}\nPrimary metric: {e['primaryMetric']} "
        f"(baseline {e['baselinePp']:.1f}pp, expected lift +{e['expectedLiftPp']:.1f}pp)"
    )


def make_log(experiment: dict, history: list[dict]) -> dict:
    return {
        "id": experiment["id"],
        "reviewed_on": experiment["startDate"],
        "brief": {
            k: experiment[k]
            for k in (
                "name", "hypothesis", "mechanism", "audience",
                "primaryMetric", "baselinePp", "expectedLiftPp",
            )
        },
        "history_ids": [h["id"] for h in history],
        "outcome": {"actualLiftPp": experiment["actualLiftPp"], "shipped": experiment["outcome"]},
    }


def supporting_ids(experiment: dict, history: list[dict]) -> list[str]:
    """The past experiments that support the expected call, strongest class available.

    Same mechanism and same outcome first (the coach's own rule is about
    mechanisms); then the same audience and outcome (a precedent on the same
    funnel stage); then any experiment with the same outcome. Returns at least
    one id whenever the history has any experiment with the right outcome.
    """
    verdict = expected_verdict(experiment)
    same_outcome = [h for h in history if expected_verdict(h) == verdict]
    for tier in (
        [h for h in same_outcome if h["mechanism"] == experiment["mechanism"]],
        [h for h in same_outcome if h["audience"] == experiment["audience"]],
        same_outcome,
    ):
        if tier:
            return [h["id"] for h in tier]
    return []


def make_trajectory(experiment: dict, history: list[dict]) -> dict:
    ids = "|".join(re.escape(i) for i in supporting_ids(experiment, history)) or "ex-000"
    return {
        "trajectory_id": experiment["id"],
        "system": SYSTEM_RULES + "\n\n" + render_history(history),
        "turns": [
            {
                "input": render_brief(experiment)
                + "\n\nShould the coach object to this brief? Reply with exactly OBJECT or DECLINE "
                "on the first line, then one sentence of reason.",
                "expected": {"label": expected_verdict(experiment)},
            },
            {
                "input": "If you objected: which type, exactly one of assumed-causation, "
                "repeated-mechanism, unpowered-metric, audience-mismatch, undevised-target, "
                "guardrail-gap. If you declined: reply NONE. One word only.",
                "expected": {"label": expected_type(experiment)},
            },
            {
                "input": "List the ids of up to three past experiments from the history above that "
                "most support your call, comma-separated, ids only.",
                "expected": {"pattern": rf"\b({ids})\b"},
            },
        ],
    }


def main(argv: list[str]) -> int:
    corpus_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_CORPUS
    experiments = parse_corpus(corpus_path.read_text())
    if len(experiments) < 30:
        raise SystemExit(f"parsed only {len(experiments)} experiments from {corpus_path}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logs, trajectories = [], []
    for index, experiment in enumerate(experiments):
        history = [h for h in experiments[:index] if h["readDate"] < experiment["startDate"]]
        if index >= len(experiments) - 25:
            logs.append(make_log(experiment, history))
        if index >= len(experiments) - 20:
            trajectories.append(make_trajectory(experiment, history))

    (OUT_DIR / "logs.jsonl").write_text("\n".join(json.dumps(x) for x in logs) + "\n")
    (OUT_DIR / "trajectories.jsonl").write_text("\n".join(json.dumps(x) for x in trajectories) + "\n")
    verdicts = [t["turns"][0]["expected"]["label"] for t in trajectories]
    print(f"{len(logs)} logs, {len(trajectories)} trajectories "
          f"({verdicts.count('object')} object / {verdicts.count('decline')} decline) -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
