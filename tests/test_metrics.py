"""Metric formulas, checked against hand-computed values.

If a number in a report is questioned, these tests are the receipt for how it
was computed.
"""

from harness.metrics import (
    consistency,
    cost_per_correct_call,
    percentile,
    summarise,
    time_per_output_token_s,
    tokens_per_second_per_user,
)
from harness.models import CallRecord


def make_record(**overrides) -> CallRecord:
    base = dict(
        trajectory_id="t1",
        turn_index=0,
        model="m",
        provider="p",
        run=1,
        passed=True,
        gate_kind="label",
        time_to_first_token_s=0.5,
        time_to_first_output_s=0.5,
        total_latency_s=2.5,
        input_tokens=100,
        output_tokens=40,
        cost_usd=0.01,
        output_text="ok",
    )
    base.update(overrides)
    return CallRecord(**base)


def test_percentile_is_nearest_rank_and_never_interpolates():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(values, 0.50) == 30.0
    assert percentile(values, 0.95) == 50.0
    assert percentile([7.0], 0.95) == 7.0
    assert percentile([], 0.5) == 0.0


def test_tpot_is_decode_time_over_output_tokens():
    record = make_record(time_to_first_output_s=0.5, total_latency_s=2.5, output_tokens=40)
    assert time_per_output_token_s(record) == 2.0 / 40
    assert tokens_per_second_per_user(record) == 20.0
    assert time_per_output_token_s(make_record(output_tokens=0)) is None


def test_cost_per_correct_call_divides_total_cost_by_passes():
    records = [
        make_record(passed=True, cost_usd=0.02),
        make_record(turn_index=1, passed=False, cost_usd=0.02),
    ]
    assert cost_per_correct_call(records) == 0.04 / 1
    assert cost_per_correct_call([make_record(passed=False)]) is None
    assert cost_per_correct_call([make_record(cost_usd=None)]) is None


def test_consistency_needs_two_runs_and_counts_agreeing_turns():
    one_run = [make_record(run=1)]
    assert consistency(one_run) is None
    two_runs = [
        make_record(run=1, turn_index=0, passed=True),
        make_record(run=2, turn_index=0, passed=True),
        make_record(run=1, turn_index=1, passed=True),
        make_record(run=2, turn_index=1, passed=False),
    ]
    assert consistency(two_runs) == 0.5


def test_summarise_excludes_errors_from_timings_but_counts_them_as_failed():
    records = [
        make_record(turn_index=0, passed=True, time_to_first_token_s=1.0, total_latency_s=3.0),
        make_record(turn_index=1, passed=False, error="timeout", time_to_first_token_s=99.0),
    ]
    summary = summarise(records)
    assert summary.calls == 2
    assert summary.errors == 1
    assert summary.gate_pass_rate == 0.5
    assert summary.ttft_p95_s == 1.0
    assert summary.cost_per_task_usd == 0.02
    assert any("errored" in note for note in summary.notes)
