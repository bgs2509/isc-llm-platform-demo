"""Arithmetic of the measurement summaries (scripts/measure.py); the network parts are checked by the runs."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("measure", Path(__file__).parent.parent / "measure.py")
measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure)


def test_kv_row_takes_peaks_from_the_timeline():
    run = {"summary": {"ttft_p95_s": 1.5, "tokens_per_second": 120.0},
           "timeline": [{"kv_cache_pct": 10.0, "vllm_waiting": 0.0}, {"kv_cache_pct": 42.5, "vllm_waiting": 3.0},
                        {"kv_cache_pct": None, "vllm_waiting": None}]}
    row = measure.kv_row({"prompt_words": 1000, "concurrency": 16}, run)
    assert row == {"prompt_words": 1000, "concurrency": 16, "kv_cache_peak_pct": 42.5, "waiting_peak": 3.0,
                   "ttft_p95_s": 1.5, "tokens_per_s": 120.0}


def test_drill_summary_counts_failures_and_recovery():
    timeline = [{"t": t, "tokens_per_s": v} for t, v in
                [(5, 100.0), (10, 100.0), (15, 100.0), (21, 20.0), (25, 0.0), (30, 50.0), (35, 95.0), (40, 100.0)]]
    summary = {"requests": 200, "ok": 190}
    s = measure.drill_summary(timeline, summary, delete_at_s=20.0, ready_after_s=9.5)
    assert s["failed"] == 10 and s["requests"] == 200
    assert s["baseline_tokens_per_s"] == 100.0
    assert s["recovered_after_s"] == 15.0  # first point at or above 90 % of the baseline after the delete
    assert s["seconds_to_ready"] == 9.5


def test_alert_times_from_state_samples():
    samples = [(0.0, "inactive"), (40.0, "pending"), (100.0, "firing"), (160.0, "firing"), (190.0, "inactive")]
    assert measure.alert_times(samples, load_end_s=150.0) == {"fired_after_s": 100.0,
                                                              "resolved_after_load_end_s": 40.0}


def test_alert_times_when_it_never_fires():
    assert measure.alert_times([(0.0, "inactive"), (60.0, "pending")], load_end_s=50.0) == {
        "fired_after_s": None, "resolved_after_load_end_s": None}


def test_expected_spend_uses_the_gateway_prices():
    assert abs(measure.expected_spend(1_000_000, 1_000_000) - 0.75) < 1e-12
