import pytest

from app.stats import RequestResult, cost_per_million_tokens, parse_prometheus_text, percentile, summarize


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([5], 95) == 5
    assert percentile([], 50) is None
    assert percentile([1, 2, 3, 4, 5], 100) == 5


def test_cost_per_million_tokens():
    # 2 USD/hour, 1000 tokens/s -> 3.6M tokens/hour -> 0.5556 USD per 1M tokens
    assert cost_per_million_tokens(2.0, 1000.0) == pytest.approx(0.5555, rel=1e-3)
    assert cost_per_million_tokens(2.0, 0) is None
    assert cost_per_million_tokens(2.0, None) is None


def test_parse_prometheus_text_sums_labels_and_skips_noise():
    text = "\n".join([
        "# HELP vllm:num_requests_running x",
        'vllm:num_requests_running{engine="0",model_name="m"} 3.0',
        'vllm:num_requests_running{engine="1",model_name="m"} 2.0',
        "vllm:prompt_tokens_total 5.19e+06",
        "bad line",
        "vllm:nan_metric NaN",
    ])
    out = parse_prometheus_text(text)
    assert out["vllm:num_requests_running"] == 5.0
    assert out["vllm:prompt_tokens_total"] == pytest.approx(5.19e6)
    assert "vllm:nan_metric" not in out


def test_summarize_counts_errors_cache_and_throughput():
    results = [
        RequestResult(True, 200, 2.0, 0.5, 100),
        RequestResult(True, 200, 4.0, 1.5, 300, cached=True),
        RequestResult(False, 429, 0.1),
    ]
    s = summarize(results, duration_s=10.0, gpu_util=[10.0, 90.0], gpu_usd_per_hour=0.36)
    assert s["requests"] == 3 and s["ok"] == 2
    assert s["errors"] == {"429": 1}
    assert s["cache_hits"] == 1
    assert s["tokens_per_second"] == 40.0
    assert s["gpu_util_avg"] == 50.0 and s["gpu_util_max"] == 90.0
    # 0.36 USD/h at 40 tokens/s -> 0.36/(40*3600)*1e6 = 2.5 USD per 1M tokens
    assert s["usd_per_million_tokens"] == pytest.approx(2.5)
    assert s["ttft_p50_s"] == pytest.approx(1.0)
