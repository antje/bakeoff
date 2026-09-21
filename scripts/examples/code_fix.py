"""Build the code-fix example: a PR copilot turns a failing test into a corrected function.

What this produces, under examples/code-fix/:

- logs.jsonl: 20 pull requests as a CI system and a reviewer leave them: the
  function under review, the test that failed, the CI output, the fix that
  was merged, and the category the reviewer labelled the bug with. The
  "before /eval-build" state.
- trajectories.jsonl: each PR as a three-turn conversation. Turn 1 names the
  bug category, turn 2 writes the whole corrected function, turn 3 traces the
  corrected function on a fresh input.

Why this shape. This is the code-generation step of a review copilot, and
its output is a function, not a word: turn 2 is where the tokens go, so the
bill is output-heavy and a cheap model that gets the diagnosis right can
still fumble the code. Three turns, because a copilot that names the bug,
writes the fix, and cannot say what its own fix returns has not understood
it. The eight bug families are the ones that survive code review most often
(a boundary, an off-by-one range, a wrong initial value, integer division,
a mutable default, a flipped comparison, a missing case fold, a missing unit
conversion), each with one canonical fix and the equivalent spellings a
reviewer would also merge.

Ground truth. The generator executes its own buggy and fixed sources: the
failing test must fail on the buggy one and pass on the fixed one, and the
turn-3 answer is what the fixed function returns, so every expected value
is known by construction. The turn-2 gate is a pattern over the corrected
line and its accepted equivalents; a correct fix spelt some other way fails
the gate, which makes it conservative, never generous. Function names and
signatures are fixed per family so the patterns stay exact; identifiers
vary per PR so no constant answer passes turn 2 or turn 3.

Run:  uv run python scripts/examples/code_fix.py
"""

from __future__ import annotations

import re
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from _common import rng, write_example

from harness.models import Expected, Trajectory, Turn

CATEGORIES = {
    "boundary": "a comparison that excludes a value the spec includes, or the reverse (> for >=)",
    "range": "a loop that skips the first or last element",
    "init": "an accumulator or best-so-far that starts from the wrong value",
    "division": "integer division where the spec asks for a fraction, or the reverse",
    "default": "a mutable default argument shared between calls",
    "comparison": "a comparison pointing the wrong way (< for >)",
    "normalize": "input compared without the case folding or trimming the spec asks for",
    "units": "a result in the wrong unit or scale (a fraction where a percentage was asked for)",
}

SYSTEM = """You are the review copilot for Nightjar's Python services. A pull request has a failing test. You will be shown the function under review, its spec, the test, and the CI output, then asked three things in turn.

Bug categories, exactly one applies to each PR:
{categories}

Answer format:
- When asked for a category, put the category word alone on the first line.
- When asked for code, reply with one Python code block containing the complete corrected function, keeping its name and signature, changing as little as possible.
- When asked what a call returns, put the Python value alone on the first line, exactly as Python would print it, with no code."""


@dataclass
class Family:
    """One bug family: the sources with identifier placeholders, and how to test it."""

    category: str
    function: str
    path: str
    spec: str
    buggy: str
    fixed: str
    fix_pattern: str  # identifier placeholders are substituted after escaping
    names: list[dict[str, str]]  # per-PR identifier choices
    test: Callable[[Any, dict[str, str]], tuple[str, str, str]]  # (test name, test body, assert op)
    regression: Callable[[Any, dict[str, str]], str]  # a call expression on the fixed function


def _q(word: str) -> str:
    """Quote a Python string literal for a call expression."""
    return repr(word)


FAMILIES: list[Family] = [
    Family(
        category="boundary",
        function="is_over_budget",
        path="billing/limits.py",
        spec="Return True when {a} has reached or exceeded {b}, False otherwise.",
        buggy="def is_over_budget({a}, {b}):\n    return {a} > {b}\n",
        fixed="def is_over_budget({a}, {b}):\n    return {a} >= {b}\n",
        fix_pattern=r"{a}\s*>=\s*{b}|{b}\s*<=\s*{a}|not\s+{a}\s*<\s*{b}",
        names=[{"a": "spent", "b": "budget"}, {"a": "used", "b": "limit"}, {"a": "total", "b": "cap"}],
        test=lambda r, n: (
            "test_is_over_budget_at_limit",
            f"    assert is_over_budget({(v := r.randint(2, 40) * 25)}, {v}) is True",
            "is",
        ),
        regression=lambda r, n: f"is_over_budget({(v := r.randint(2, 40) * 25)}, {v})"
        if r.random() < 0.5
        else f"is_over_budget({(v := r.randint(2, 40) * 25)}, {v + r.randint(1, 8) * 25})",
    ),
    Family(
        category="range",
        function="running_total",
        path="reports/series.py",
        spec="Return the list of prefix sums of {xs}: element i is the sum of {xs}[0] through {xs}[i].",
        buggy=(
            "def running_total({xs}):\n    out = []\n    total = 0\n"
            "    for i in range(1, len({xs})):\n        total += {xs}[i]\n        out.append(total)\n    return out\n"
        ),
        fixed=(
            "def running_total({xs}):\n    out = []\n    total = 0\n"
            "    for i in range(len({xs})):\n        total += {xs}[i]\n        out.append(total)\n    return out\n"
        ),
        fix_pattern=r"range\(\s*len\(\s*{xs}\s*\)\s*\)|range\(\s*0\s*,\s*len\(\s*{xs}\s*\)\s*\)|for\s+\w+\s+in\s+{xs}\s*:|accumulate\(",
        names=[{"xs": "xs"}, {"xs": "values"}, {"xs": "amounts"}],
        test=lambda r, n: (
            "test_running_total_three",
            f"    assert running_total({(v := [r.randint(1, 9) for _ in range(3)])!r}) == {[sum(v[: i + 1]) for i in range(3)]!r}",
            "==",
        ),
        regression=lambda r, n: f"running_total({[r.randint(1, 12) for _ in range(4)]!r})",
    ),
    Family(
        category="init",
        function="largest",
        path="metrics/extrema.py",
        spec="Return the largest element of {xs}, which is never empty and may be all negative.",
        buggy="def largest({xs}):\n    best = 0\n    for x in {xs}:\n        if x > best:\n            best = x\n    return best\n",
        fixed="def largest({xs}):\n    best = {xs}[0]\n    for x in {xs}:\n        if x > best:\n            best = x\n    return best\n",
        fix_pattern=r"best\s*=\s*{xs}\[\s*0\s*\]|-\s*inf|-\s*math\.inf|best\s*=\s*None|return\s+max\(\s*{xs}\s*\)|{xs}\[\s*1\s*:\s*\]",
        names=[{"xs": "xs"}, {"xs": "readings"}, {"xs": "deltas"}],
        test=lambda r, n: (
            "test_largest_all_negative",
            f"    assert largest({(v := sorted(r.sample(range(-40, -1), 3), reverse=True))!r}) == {max(v)}",
            "==",
        ),
        regression=lambda r, n: f"largest({r.sample(range(-60, -1), 4)!r})",
    ),
    Family(
        category="division",
        function="average",
        path="metrics/stats.py",
        spec="Return the arithmetic mean of {xs} as a float; {xs} is never empty.",
        buggy="def average({xs}):\n    return sum({xs}) // len({xs})\n",
        fixed="def average({xs}):\n    return sum({xs}) / len({xs})\n",
        fix_pattern=r"sum\(\s*{xs}\s*\)\s*/\s*len\(\s*{xs}\s*\)|mean\(|/\s*float\(",
        names=[{"xs": "xs"}, {"xs": "samples"}, {"xs": "latencies"}],
        test=lambda r, n: (
            "test_average_is_a_fraction",
            f"    assert average({(v := [r.randint(1, 4) * 2, r.randint(1, 9) * 2 + 1])!r}) == {sum(v) / 2}",
            "==",
        ),
        regression=lambda r, n: f"average({_quarter_list(r)!r})",
    ),
    Family(
        category="default",
        function="add_tag",
        path="tickets/tags.py",
        spec="Append {t} to {ts} and return {ts}. When {ts} is not given, start from a new empty list on every call.",
        buggy="def add_tag({t}, {ts}=[]):\n    {ts}.append({t})\n    return {ts}\n",
        fixed="def add_tag({t}, {ts}=None):\n    if {ts} is None:\n        {ts} = []\n    {ts}.append({t})\n    return {ts}\n",
        fix_pattern=r"{ts}\s*(?::[^=\n]*)?=\s*None|{ts}\s*(?::[^=\n]*)?=\s*\(\s*\)",
        names=[{"t": "tag", "ts": "tags"}, {"t": "label", "ts": "labels"}, {"t": "flag", "ts": "flags"}],
        test=lambda r, n: (
            "test_add_tag_fresh_list",
            f"    add_tag({_q(r.choice(WORDS))})\n    assert add_tag({_q(w := r.choice(WORDS))}) == [{_q(w)}]",
            "==",
        ),
        regression=lambda r, n: f"add_tag({_q(r.choice(WORDS))}); add_tag({_q(r.choice(WORDS))})",
    ),
    Family(
        category="comparison",
        function="longest",
        path="search/rank.py",
        spec="Return the longest string in {ws}, which is never empty and has a unique longest element.",
        buggy="def longest({ws}):\n    best = {ws}[0]\n    for w in {ws}:\n        if len(w) < len(best):\n            best = w\n    return best\n",
        fixed="def longest({ws}):\n    best = {ws}[0]\n    for w in {ws}:\n        if len(w) > len(best):\n            best = w\n    return best\n",
        fix_pattern=r"len\(\s*w\s*\)\s*>\s*len\(\s*best\s*\)|len\(\s*best\s*\)\s*<\s*len\(\s*w\s*\)|max\(\s*{ws}\s*,\s*key\s*=\s*len\s*\)",
        names=[{"ws": "words"}, {"ws": "names"}, {"ws": "tokens"}],
        test=lambda r, n: (
            "test_longest_not_first",
            f"    assert longest({(v := _distinct_lengths(r, 3))!r}) == {max(v, key=len)!r}",
            "==",
        ),
        regression=lambda r, n: f"longest({_distinct_lengths(r, 4)!r})",
    ),
    Family(
        category="normalize",
        function="count_tag",
        path="tickets/counts.py",
        spec="Return how many entries of {ts} equal {w}, comparing case-insensitively.",
        buggy="def count_tag({ts}, {w}):\n    n = 0\n    for t in {ts}:\n        if t == {w}:\n            n += 1\n    return n\n",
        fixed="def count_tag({ts}, {w}):\n    n = 0\n    for t in {ts}:\n        if t.lower() == {w}.lower():\n            n += 1\n    return n\n",
        fix_pattern=r"\.lower\(\)|\.casefold\(\)|\.upper\(\)",
        names=[{"ts": "tags", "w": "wanted"}, {"ts": "labels", "w": "needle"}, {"ts": "entries", "w": "target"}],
        test=lambda r, n: (
            "test_count_tag_ignores_case",
            f"    assert count_tag({(m := _mixed_case(r))[0]!r}, {_q(m[1])}) == {m[2]}",
            "==",
        ),
        regression=lambda r, n: f"count_tag({(m := _mixed_case(r))[0]!r}, {_q(m[1])})",
    ),
    Family(
        category="units",
        function="percent_used",
        path="billing/usage.py",
        spec="Return the share of {b} that {a} represents, as a percentage between 0 and 100.",
        buggy="def percent_used({a}, {b}):\n    return {a} / {b}\n",
        fixed="def percent_used({a}, {b}):\n    return {a} / {b} * 100\n",
        fix_pattern=r"\*\s*100(?:\.0)?\b|\b100(?:\.0)?\s*\*",
        names=[{"a": "used", "b": "quota"}, {"a": "spent", "b": "budget"}, {"a": "sent", "b": "allowance"}],
        test=lambda r, n: (
            "test_percent_used_is_a_percentage",
            f"    assert percent_used({(v := r.choice([1, 3]))}, {(d := r.choice([4, 8]))}) == {v / d * 100}",
            "==",
        ),
        regression=lambda r, n: f"percent_used({r.choice([1, 3, 5, 7])}, {r.choice([4, 8, 16, 32])})",
    ),
]

WORDS = ["alpha", "beta", "gamma", "delta", "kappa", "sigma", "omega", "theta"]
TAGS = ["bug", "feature", "urgent", "billing", "docs", "infra"]


def _quarter_list(r) -> list[int]:
    """Four integers whose mean is not an integer, so integer division visibly fails."""
    while True:
        xs = [r.randint(1, 20) for _ in range(4)]
        if sum(xs) % 4:
            return xs


def _distinct_lengths(r, count: int) -> list[str]:
    """Words of distinct lengths, the longest not first, so a wrong comparison shows."""
    pool = ["ox", "ant", "wren", "heron", "falcon", "sparrow", "kingfisher"]
    while True:
        words = r.sample(pool, count)
        if max(words, key=len) != words[0]:
            return words


def _mixed_case(r) -> tuple[list[str], str, int]:
    """A tag list with the wanted tag in several cases, the tag, and how many times it appears."""
    word = r.choice(TAGS)
    others = [t for t in TAGS if t != word]
    variants = [word, word.upper(), word.capitalize(), word.title()]
    hits = r.randint(2, 4)
    entries = r.sample(variants, hits) + r.sample(others, r.randint(1, 3))
    r.shuffle(entries)
    return entries, word, hits


def value_pattern(value: Any) -> str:
    """The value alone on the first line, as Python prints it, with harmless variation allowed."""
    if isinstance(value, bool):
        return rf"^\s*[^\n]*\b({value})\b"
    if isinstance(value, int):
        return rf"^\s*[^\n]*(?<![\d.,-]){'-' if value < 0 else ''}{abs(value)}(?:\.0+)?(?![\d.])"
    if isinstance(value, float):
        text = repr(value)
        if text.endswith(".0"):
            return rf"^\s*[^\n]*(?<![\d.,-]){text[:-2]}(?:\.0+)?(?![\d.])"
        return rf"^\s*[^\n]*(?<![\d.,-]){re.escape(text)}0*(?![\d])"
    if isinstance(value, str):
        return rf"^\s*[^\n]*\b({re.escape(value)})\b"
    if isinstance(value, list):
        inner = r"\s*,\s*".join(
            rf"['\"]{re.escape(v)}['\"]" if isinstance(v, str) else rf"{'-' if v < 0 else ''}{abs(v)}"
            for v in value
        )
        return rf"^\s*[^\n]*\[\s*{inner}\s*\]"
    raise TypeError(f"no pattern for {value!r}")


def _run(source: str, statements: str) -> Any:
    """Execute a function source, then the statements; return the value of the last expression."""
    namespace: dict[str, Any] = {}
    exec(source, namespace)  # our own generated code, by construction
    *setup, last = [s.strip() for s in statements.split(";")]
    for statement in setup:
        exec(statement, namespace)
    return eval(last, namespace)


def _fill(template: str, names: dict[str, str], escape: bool = False) -> str:
    return template.format(**({k: re.escape(v) for k, v in names.items()} if escape else names))


def build() -> tuple[list[dict], list[Trajectory]]:
    random = rng()
    logs: list[dict] = []
    trajectories: list[Trajectory] = []
    categories = "\n".join(f"- {name}: {meaning}" for name, meaning in CATEGORIES.items())
    for i in range(20):
        family = FAMILIES[i % len(FAMILIES)]
        names = random.choice(family.names)
        buggy = _fill(family.buggy, names)
        fixed = _fill(family.fixed, names)
        spec = _fill(family.spec, names)
        test_name, test_body, op = family.test(random, names)
        test_source = f"def {test_name}():\n{test_body}\n"
        regression = family.regression(random, names)

        # Ground truth by construction: the test fails on the buggy source and passes on the fixed one.
        assert_line = test_body.strip().splitlines()[-1].strip().removeprefix("assert ")
        lhs, rhs = [part.strip() for part in assert_line.split(f" {op} ")]
        setup = "; ".join(line.strip() for line in test_body.strip().splitlines()[:-1])
        call = f"{setup}; {lhs}" if setup else lhs
        buggy_value = _run(buggy, call)
        fixed_value = _run(fixed, call)
        expected = eval(rhs)  # a literal we wrote
        assert fixed_value == expected and buggy_value != expected, (family.function, call)
        assert re.search(_fill(family.fix_pattern, names, escape=True), fixed, re.IGNORECASE)
        assert not re.search(_fill(family.fix_pattern, names, escape=True), buggy, re.IGNORECASE)
        answer = _run(fixed, regression)
        ci_output = (
            f"FAILED tests/{family.path.replace('/', '_').replace('.py', '')}_test.py::{test_name} "
            f"- AssertionError: assert {buggy_value!r} {op} {expected!r}"
        )

        pr_id = f"PR-{3100 + i * 7}"
        logs.append(
            {
                "pr": pr_id,
                "path": family.path,
                "function": family.function,
                "spec": spec,
                "source": buggy,
                "failing_test": test_source,
                "ci_output": ci_output,
                "merged_fix": fixed,
                "review_label": family.category,
                "regression": {"call": regression, "returns": repr(answer)},
            }
        )
        turn1 = textwrap.dedent(
            f"""\
            {pr_id} touches `{family.path}`.

            Spec for `{family.function}`: {spec}

            ```python
            {{buggy}}```

            Failing test:
            ```python
            {{test}}```

            CI output:
            {ci_output}

            Which bug category is this? Reply with the category word alone on the first line."""
        ).replace("{buggy}", buggy).replace("{test}", test_source)
        trajectories.append(
            Trajectory(
                trajectory_id=pr_id,
                system=SYSTEM.format(categories=categories),
                turns=[
                    Turn(input=turn1, expected=Expected(label=family.category)),
                    Turn(
                        input=(
                            "Write the complete corrected function in one Python code block. "
                            "Keep the name and signature; change as little as possible."
                        ),
                        expected=Expected(pattern=_fill(family.fix_pattern, names, escape=True)),
                    ),
                    Turn(
                        input=(
                            f"Using the corrected function, what does `{regression}` return? "
                            "Put the value alone on the first line, exactly as Python would print it, no code."
                            if ";" not in regression
                            else f"In a fresh interpreter with the corrected function, run `{regression}`. "
                            "What does the second call return? Put the value alone on the first line, "
                            "exactly as Python would print it, no code."
                        ),
                        expected=Expected(pattern=value_pattern(answer)),
                    ),
                ],
            )
        )
    return logs, trajectories


if __name__ == "__main__":
    logs, trajectories = build()
    out = write_example("code-fix", logs, trajectories)
    print(f"wrote {len(trajectories)} trajectories to {out}")
