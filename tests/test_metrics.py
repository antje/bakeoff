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


def test_trivial_baseline_takes_the_best_constant_per_turn():
    from harness.metrics import trivial_baseline
    from harness.models import Expected, Trajectory, Turn

    def t(tid, label, pattern):
        return Trajectory(
            trajectory_id=tid,
            turns=[
                Turn(input="q1", expected=Expected(label=label)),
                Turn(input="q2", expected=Expected(pattern=pattern)),
                Turn(input="q3", expected=Expected(tool_call={"name": "f", "arguments": {}})),
            ],
        )

    trajectories = [
        t("a", "yes", r"\b(id\-1|id\-2)\b"),
        t("b", "yes", r"\b(id\-1)\b"),
        t("c", "no", r"\b(id\-3)\b"),
    ]
    baseline = trivial_baseline(trajectories)
    assert baseline.per_turn[0] == ("yes", 2, 3)
    assert baseline.per_turn[1] == ("id-1", 2, 3)
    assert baseline.per_turn[2] == ("", 0, 3)
    assert abs(baseline.rate - 4 / 9) < 1e-9


def test_verdict_drops_cells_over_the_ttft_budget():
    from dataclasses import replace

    from harness.metrics import Summary
    from harness.report import verdict

    def cell(model, rate, ttft, cost):
        return Summary(
            model=model, provider="auto", calls=10, errors=0, trajectories=5, gate_pass_rate=rate,
            ttft_p50_s=ttft / 2, ttft_p95_s=ttft, tpot_p50_s=0.01, tpot_p95_s=0.02, e2e_p50_s=1, e2e_p95_s=2,
            tokens_per_s_per_user_p50=50, input_tokens_p50=100, output_tokens_p50=10, cost_total_usd=cost,
            cost_per_task_usd=cost / 5, cost_per_correct_call_usd=cost / 10, consistency=None,
        )

    cheap_slow = cell("small", 0.99, 4.5, 0.01)
    fast = cell("mid", 1.0, 1.9, 0.02)
    assert "small" in verdict([cheap_slow, fast])
    with_budget = verdict([cheap_slow, fast], ttft_budget_s=2.0)
    assert with_budget.startswith("Route to mid")
    assert "small @ auto (4.50s)" in with_budget
    over_budget = verdict([replace(fast, ttft_p95_s=3.0), cheap_slow], ttft_budget_s=2.0)
    assert over_budget.startswith("Provisional (every cell's TTFT p95 is over the 2.0s budget")
    assert "Route to small" in over_budget


def test_verdict_is_provisional_not_withheld_under_the_baseline():
    from harness.metrics import Summary
    from harness.report import verdict

    def cell(model, rate, cost):
        return Summary(
            model=model, provider="auto", calls=12, errors=0, trajectories=4, gate_pass_rate=rate,
            ttft_p50_s=0.5, ttft_p95_s=1.0, tpot_p50_s=0.01, tpot_p95_s=0.02, e2e_p50_s=1, e2e_p95_s=2,
            tokens_per_s_per_user_p50=50, input_tokens_p50=100, output_tokens_p50=10, cost_total_usd=cost,
            cost_per_task_usd=cost / 4, cost_per_correct_call_usd=cost / max(1, int(rate * 12)),
            consistency=None,
        )

    out = verdict([cell("a", 0.33, 0.01), cell("b", 0.42, 0.02)], baseline=0.58)
    assert out.startswith("Provisional (no cell beat the trivial baseline of 58%")
    assert "Route to b @ auto" in out
    assert verdict([cell("a", 0.9, 0.01)], baseline=0.58).startswith("Route to a")


def test_at_a_glance_stars_the_verdict_cell_and_picks_the_shape_by_what_was_compared():
    from dataclasses import replace

    from harness.metrics import Summary
    from harness.report import RunConditions, at_a_glance, verdict

    def cell(model, provider, rate, cost):
        return Summary(
            model=model, provider=provider, calls=10, errors=0, trajectories=5, gate_pass_rate=rate,
            ttft_p50_s=0.5, ttft_p95_s=1.0, tpot_p50_s=0.01, tpot_p95_s=0.02, e2e_p50_s=1, e2e_p95_s=2,
            tokens_per_s_per_user_p50=50, input_tokens_p50=100, output_tokens_p50=10, cost_total_usd=cost,
            cost_per_task_usd=cost / 5, cost_per_correct_call_usd=cost / 10, consistency=None,
        )

    conditions = RunConditions(
        date_utc="2026-09-21 00:00", trajectories=5, turns_per_trajectory_p50=2, concurrency=1, runs=1,
        max_tokens=100, warm_or_cold="cold", input_tokens_p50=100, output_tokens_p50=10, harness_commit="x",
        endpoint="e", judged=False, reasoning="off",
    )
    # several models: model shape, costs per thousand, the verdict's cell starred
    models = [cell("small", "auto", 0.98, 0.01), cell("big", "auto", 1.0, 0.10)]
    text = "\n".join(at_a_glance(models, conditions, {}))
    assert "| model | gate |" in text and "$ / 1k correct" in text
    assert "| small ★ | 98% |" in text and "| big | 100% |" in text
    assert "$1.00 |" in text  # 0.01 / 10 per correct call, times a thousand
    assert verdict(models, as_cell=True) is models[0]
    # one model on several providers: provider shape, quantization column, star follows the verdict
    providers = [cell("m", "groq", 0.98, 0.05), replace(cell("m", "cerebras", 0.99, 0.10), ttft_p95_s=0.4)]
    text = "\n".join(at_a_glance(providers, conditions, {}))
    assert "one model on 2 endpoints" in text and "| provider | quantization |" in text
    assert "| groq ★ | unknown | 98% |" in text and "| cerebras | unknown | 99% |" in text
