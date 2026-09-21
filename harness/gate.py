"""The accuracy gate: did the model's answer match what we wrote down beforehand?

Where this sits: `replay.py` calls `check()` once per turn with the model's
output and the turn's Expected. The result becomes `CallRecord.passed`.

Why it is deterministic. MLPerf's agentic benchmark gates accuracy with
tool-call checks and AST matching, not with a second model grading the first.
A grader model has its own error rate, drifts between versions, and costs
money on every turn, so a "95% pass rate" judged by a model is really
"95% agreement with a grader nobody benchmarked". Here the check is a plain
comparison a human can re-run by hand: same tool and arguments, same label,
or a regex hit. The judge in `judge()` exists for cases where nothing else
works, and every number it produces is labelled "judged" in the report.

Three checks, one per kind of Expected:

- tool_call: the model called the same tool with matching arguments.
- label: the first non-empty line of the model's text, trimmed and
  lower-cased, equals the label or contains it as a whole word. "Billing."
  and "The category is billing" pass; "OBJECT. I would not decline" passes
  only OBJECT. Every prompt with a label gate asks for the answer on the
  first line, so the rest of the text is explanation, not decision.
- pattern: a regex search over the model's text.
"""

from __future__ import annotations

import json
import re

from .models import Expected


def _normalise_arguments(arguments: object) -> object:
    """Turn tool arguments into a comparable form.

    Providers return arguments either as a JSON string or as a parsed object,
    and key order varies. Parse strings, then sort keys by round-tripping
    through json.dumps(sort_keys=True), so {"a":1,"b":2} equals {"b":2,"a":1}.
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return arguments.strip()
    return json.loads(json.dumps(arguments, sort_keys=True))


def check_tool_call(expected: dict, actual_calls: list[dict]) -> bool:
    """Pass if any call the model made has the expected name and arguments.

    `actual_calls` is a list of {"name": ..., "arguments": ...} from the
    response. Any match passes, because a model may legitimately make an
    extra harmless call alongside the right one.
    """
    wanted_name = expected.get("name")
    wanted_arguments = _normalise_arguments(expected.get("arguments", {}))
    for call in actual_calls:
        if call.get("name") != wanted_name:
            continue
        if _normalise_arguments(call.get("arguments", {})) == wanted_arguments:
            return True
    return False


def check_label(expected: str, text: str) -> bool:
    """Pass if the first non-empty line is the label, or contains it as a whole word.

    Case-insensitive. Whole-word so that "billing" does not pass on
    "rebilling". First line only, so an answer that names the other label in
    its reasoning ("OBJECT. I would not decline this") passes one label, not
    two. Easy to get wrong: labels that are substrings of each other
    ("urgent" vs "not urgent"); put the negated one first in your label set
    or use a pattern check instead.
    """
    wanted = expected.strip().lower()
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    got = lines[0].lower() if lines else ""
    if got == wanted:
        return True
    return re.search(rf"\b{re.escape(wanted)}\b", got) is not None


def check_pattern(pattern: str, text: str) -> bool:
    """Pass if the regex matches anywhere in the text (case-insensitive)."""
    return re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is not None


def check(expected: Expected, text: str, tool_calls: list[dict]) -> bool:
    """Run the one check this Expected asks for. This is the gate."""
    kind = expected.kind()
    if kind == "tool_call":
        return check_tool_call(expected.tool_call or {}, tool_calls)
    if kind == "label":
        return check_label(expected.label or "", text)
    return check_pattern(expected.pattern or "", text)


def judge_prompt(question: str, reference: str, answer: str) -> str:
    """The prompt an optional LLM judge sees. Kept here so it is reviewable.

    Not used by default. When `--judge` is on, `replay.py` sends this to the
    judge model and treats a reply starting with "PASS" as a pass. The report
    labels every such result "judged" so nobody mistakes it for ground truth.
    """
    return (
        "You are grading one answer against a reference. Reply with exactly "
        "PASS or FAIL on the first line, then one sentence of reason.\n\n"
        f"Question:\n{question}\n\nReference answer:\n{reference}\n\n"
        f"Candidate answer:\n{answer}\n"
    )
