"""Gate semantics: the exact rules a pass/fail decision follows.

Each test is one rule from harness/gate.py, so a change in behaviour shows up
as a named failure rather than a drifting pass rate.
"""

from harness.gate import check, check_label, check_pattern, check_tool_call
from harness.models import Expected


def test_tool_call_matches_regardless_of_argument_order_and_encoding():
    expected = {"name": "lookup_order", "arguments": {"order_id": "NW-1", "verbose": True}}
    as_string = [{"name": "lookup_order", "arguments": '{"verbose": true, "order_id": "NW-1"}'}]
    as_object = [{"name": "lookup_order", "arguments": {"verbose": True, "order_id": "NW-1"}}]
    assert check_tool_call(expected, as_string)
    assert check_tool_call(expected, as_object)


def test_tool_call_fails_on_wrong_name_or_arguments():
    expected = {"name": "lookup_order", "arguments": {"order_id": "NW-1"}}
    wrong_name = [{"name": "cancel_order", "arguments": {"order_id": "NW-1"}}]
    wrong_args = [{"name": "lookup_order", "arguments": {"order_id": "NW-2"}}]
    assert not check_tool_call(expected, wrong_name)
    assert not check_tool_call(expected, wrong_args)
    assert not check_tool_call(expected, [])


def test_tool_call_passes_when_the_right_call_is_among_several():
    expected = {"name": "lookup_order", "arguments": {"order_id": "NW-1"}}
    calls = [
        {"name": "get_time", "arguments": {}},
        {"name": "lookup_order", "arguments": {"order_id": "NW-1"}},
    ]
    assert check_tool_call(expected, calls)


def test_label_is_case_insensitive_and_accepts_whole_word_mentions():
    assert check_label("billing", "Billing")
    assert check_label("billing", "The category is billing.")
    assert not check_label("billing", "rebilling")
    assert not check_label("billing", "technical")


def test_pattern_is_a_case_insensitive_search():
    assert check_pattern(r"object|decline", "Verdict: OBJECT because ...")
    assert not check_pattern(r"^decline$", "object")


def test_check_dispatches_on_expected_kind():
    assert check(Expected(label="urgent"), "urgent", [])
    assert check(Expected(pattern=r"\d{3}"), "code 123", [])
    assert check(
        Expected(tool_call={"name": "t", "arguments": {}}),
        "",
        [{"name": "t", "arguments": {}}],
    )
