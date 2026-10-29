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


def test_drill_summary_measures_the_longest_silence_after_the_delete():
    # tokens/s is a 5 s window and swings (205 -> 26 -> 205) on its own; only a run of zeros is an outage.
    series = [(8, 179), (9, 205), (12, 0), (14, 51), (16, 205), (21, 26), (23, 205), (27, 179), (28, 0), (30, 0),
              (36, 0), (44, 0), (45, 26), (47, 205), (51, 26), (59, 0), (60, 77)]
    timeline = [{"t": t, "tokens_per_s": float(v)} for t, v in series]
    s = measure.drill_summary(timeline, {"requests": 122, "ok": 51}, delete_at_s=20.0, ready_after_s=18.0)
    assert s["failed"] == 71 and s["requests"] == 122
    assert s["no_answer_s"] == 17.0  # zeros from 28 s until the first answer at 45 s
    assert s["recovered_after_s"] == 25.0  # first answer after the silence, counted from the delete
    assert s["seconds_to_ready"] == 18.0


def test_drill_summary_zeros_until_the_last_point_are_an_unrecovered_outage():
    series = [(10, 100), (21, 0), (30, 0), (40, 0)]
    timeline = [{"t": t, "tokens_per_s": float(v)} for t, v in series]
    s = measure.drill_summary(timeline, {"requests": 10, "ok": 4}, delete_at_s=20.0, ready_after_s=None)
    assert (s["no_answer_s"], s["recovered_after_s"], s["recovered"]) == (19.0, None, False)


def test_drill_summary_marks_a_recovered_outage():
    timeline = [{"t": t, "tokens_per_s": float(v)} for t, v in [(21, 0), (30, 0), (35, 50)]]
    s = measure.drill_summary(timeline, {"requests": 10, "ok": 4}, delete_at_s=20.0, ready_after_s=None)
    assert s["recovered"] is True and s["no_answer_s"] == 14.0


def test_alert_times_from_state_samples():
    samples = [(0.0, "inactive"), (40.0, "pending"), (100.0, "firing"), (160.0, "firing"), (190.0, "inactive")]
    assert measure.alert_times(samples, load_end_s=150.0) == {"fired_after_s": 100.0,
                                                              "resolved_after_load_end_s": 40.0}


def test_alert_times_when_it_never_fires():
    assert measure.alert_times([(0.0, "inactive"), (60.0, "pending")], load_end_s=50.0) == {
        "fired_after_s": None, "resolved_after_load_end_s": None}


def test_expected_spend_uses_the_gateway_prices():
    assert abs(measure.expected_spend(1_000_000, 1_000_000) - 0.75) < 1e-12
