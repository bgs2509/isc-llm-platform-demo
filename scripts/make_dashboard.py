#!/usr/bin/env python3
"""Generate the Grafana dashboard JSON for the chart (stdlib only).

Usage: scripts/make_dashboard.py > chart/llm-platform/files/dashboard.json
"""
import json

DS = {"type": "prometheus", "uid": "prometheus"}


def panel(pid, title, targets, x, y, w=12, h=8, unit="short", kind="timeseries", maxv=None):
    p = {
        "id": pid, "type": kind, "title": title, "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "targets": [{"refId": chr(65 + i), "datasource": DS, "expr": e, "legendFormat": lg}
                    for i, (e, lg) in enumerate(targets)],
    }
    if maxv is not None:
        p["fieldConfig"]["defaults"]["max"] = maxv
        p["fieldConfig"]["defaults"]["min"] = 0
    return p


panels = [
    panel(1, "Output tokens per second (model total)",
          [("sum(rate(vllm:generation_tokens_total[1m]))", "tokens/s")], 0, 0),
    panel(2, "Time to first token, seconds",
          [("histogram_quantile(0.5, sum(rate(vllm:time_to_first_token_seconds_bucket[1m])) by (le))", "p50"),
           ("histogram_quantile(0.95, sum(rate(vllm:time_to_first_token_seconds_bucket[1m])) by (le))", "p95")],
          12, 0, unit="s"),
    panel(3, "Requests on the model: running and waiting",
          [("sum(vllm:num_requests_running)", "running"), ("sum(vllm:num_requests_waiting)", "waiting")], 0, 8),
    panel(4, "KV cache used, %",
          [("max(vllm:kv_cache_usage_perc) * 100", "KV cache")], 12, 8, unit="percent", maxv=100),
    panel(5, "GPU utilization, % (whole GPU)",
          [("gpu_utilization_percent", "GPU")], 0, 16, unit="percent", maxv=100),
    panel(6, "GPU power, W and temperature, C",
          [("gpu_power_watts", "power W"), ("gpu_temperature_celsius", "temperature C")], 12, 16),
    panel(7, "Gateway requests per second by team",
          [("sum by (api_key_alias) (rate(litellm_proxy_total_requests_metric_total{api_key_alias!~\"None|\"}[1m]))", "{{api_key_alias}}")], 0, 24),
    panel(8, "Gateway failures per second by team and status",
          [("sum by (api_key_alias, exception_status) (rate(litellm_proxy_failed_requests_metric_total{api_key_alias!~\"None|\"}[1m]))",
            "{{api_key_alias}} {{exception_status}}")], 12, 24),
    panel(9, "Spend by team, USD (internal chargeback rates)",
          [("sum by (api_key_alias) (litellm_spend_metric_total{api_key_alias!~\"None|\"})", "{{api_key_alias}}")], 0, 32, unit="currencyUSD"),
    panel(10, "Tokens per second by team",
          [("sum by (api_key_alias) (rate(litellm_total_tokens_metric_total{api_key_alias!~\"None|\"}[1m]))", "{{api_key_alias}}")], 12, 32),
    panel(11, "Gateway request latency p95, seconds",
          [("histogram_quantile(0.95, sum(rate(litellm_request_total_latency_metric_bucket[5m])) by (le))", "p95")],
          0, 40, unit="s"),
    panel(12, "Firing alerts",
          [('ALERTS{alertstate="firing"}', "{{alertname}} ({{severity}})")], 12, 40, kind="table"),
]

dashboard = {
    "uid": "llm-platform", "title": "LLM platform", "tags": ["llm", "gpu"],
    "timezone": "browser", "schemaVersion": 39, "version": 1, "refresh": "5s",
    "time": {"from": "now-15m", "to": "now"}, "panels": panels,
}
print(json.dumps(dashboard, indent=2))
