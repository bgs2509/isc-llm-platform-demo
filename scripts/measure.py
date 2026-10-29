#!/usr/bin/env python3
"""Measurements for the isc-2 site (plan Phase D), run on the GPU host; results in docs/measurements/.

Usage: scripts/measure.py kv|gateway|budget|alert|helm|eval [--base http://127.0.0.1:18500] [--yes]

Every step that puts load on the GPU prints what it starts and for how long and waits for Enter
(--yes skips the wait). The console API is the only way into the platform, except kubectl for the pod
drill, the cluster secrets (keys are never printed) and a port-forward to the gateway.
"""
import argparse
import base64
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "measurements"
KUBECTL = os.environ.get("KUBECTL", os.path.expanduser("~/bin/kubectl"))
HELM = os.environ.get("HELM", os.path.expanduser("~/bin/helm"))
NS = "llm-platform"
GATEWAY_PORT = 14000  # local end of the port-forward to the gateway
INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN = 0.15e-6, 0.60e-6  # chart values.yaml pricing
RUN_GRACE_S = 120  # how long past its duration a console run may take to be stored
KV_SWEEP =[(200, 4), (500, 8), (1000, 8), (1000, 16), (2000, 16)]  # (prompt words, parallel requests)


# ---- pure summaries (tested) -------------------------------------------------
def kv_row(params: dict, run: dict) -> dict:
    tl = run["timeline"]
    kv = [p["kv_cache_pct"] for p in tl if p.get("kv_cache_pct") is not None]
    wait = [p["vllm_waiting"] for p in tl if p.get("vllm_waiting") is not None]
    return {"prompt_words": params["prompt_words"], "concurrency": params["concurrency"],
            "kv_cache_peak_pct": max(kv, default=None), "waiting_peak": max(wait, default=None),
            "ttft_p95_s": run["summary"]["ttft_p95_s"], "tokens_per_s": run["summary"]["tokens_per_second"]}


def drill_summary(timeline: list[dict], summary: dict, delete_at_s: float, ready_after_s: float | None) -> dict:
    """The longest run of zero tokens/s after the delete (tokens/s is a 5 s window that swings on its own)."""
    best, start = (None, None), None
    for p in timeline:
        if p["t"] <= delete_at_s:
            continue
        if not p.get("tokens_per_s"):
            start = p["t"] if start is None else start
        elif start is not None:
            if best[0] is None or p["t"] - start > best[1] - best[0]:
                best = (start, p["t"])
            start = None
    last = timeline[-1]["t"] if timeline else None
    recovered = True
    if start is not None and last > start:  # zeros until the last point: the outage lasted to the end of the run
        best, recovered = (start, last), False
    silent, answer = best
    return {"requests": summary["requests"], "failed": summary["requests"] - summary["ok"],
            "no_answer_s": None if silent is None else answer - silent,
            "recovered_after_s": answer - delete_at_s if answer is not None and recovered else None,
            "recovered": recovered, "seconds_to_ready": ready_after_s}


def alert_times(samples: list[tuple[float, str]], load_end_s: float) -> dict:
    fired = next((t for t, s in samples if s == "firing"), None)
    resolved = None
    if fired is not None:
        resolved = next((t - load_end_s for t, s in samples if t > fired and t >= load_end_s and s != "firing"),
                        None)
    return {"fired_after_s": fired, "resolved_after_load_end_s": resolved}


def expected_spend(prompt_tokens: int, completion_tokens: int) -> float:
    return prompt_tokens * INPUT_USD_PER_TOKEN + completion_tokens * OUTPUT_USD_PER_TOKEN


# ---- I/O helpers --------------------------------------------------------------
def http(url: str, method: str = "GET", body: dict | None = None, key: str | None = None,
         timeout: float = 180) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, method=method, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def confirm(text: str, yes: bool) -> None:
    print(text, flush=True)
    if not yes:
        input("Enter to start, Ctrl-C to cancel ")


def run_console(base: str, params: dict) -> dict:
    full = {"tenant": "research", "duration_s": 30, "max_tokens": 128, "shape": "unique", "prompt_words": 60,
            **params}
    status, started = http(base + "/api/runs", "POST", full)
    if status != 200:
        raise SystemExit(f"run not started: HTTP {status}")
    deadline = time.monotonic() + full["duration_s"] + RUN_GRACE_S
    while time.monotonic() < deadline:
        time.sleep(3)
        # 404 is normal until the run has finished: the runner stores it at the end
        _, run = http(base + f"/api/runs/{started['id']}")
        if run.get("summary"):
            return run
    raise SystemExit(f"run {started['id']} did not finish within {full['duration_s'] + RUN_GRACE_S} s")


def kubectl(*args: str) -> str:
    return subprocess.run([KUBECTL, "-n", NS, *args], check=True, capture_output=True, text=True).stdout


def secret(field: str) -> str:
    raw = kubectl("get", "secret", "llm-platform-secrets", "-o", f"jsonpath={{.data.{field}}}")
    return base64.b64decode(raw).decode()


@contextmanager
def gateway():
    pf = subprocess.Popen([KUBECTL, "-n", NS, "port-forward", "svc/litellm", f"{GATEWAY_PORT}:4000"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        yield f"http://127.0.0.1:{GATEWAY_PORT}"
    finally:
        pf.terminate()
        try:
            pf.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pf.kill()
            pf.wait()


def chat(gw: str, key: str, words: int, max_tokens: int) -> tuple[int, dict]:
    text = f"[{uuid.uuid4().hex}] " + "Summarize the following notes. " + "data platform " * (words // 2)
    body = {"model": "qwen38", "messages": [{"role": "user", "content": text}], "max_tokens": max_tokens,
            "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}, "cache": {"no-cache": True}}
    return http(gw + "/v1/chat/completions", "POST", body, key)


def save(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = {"measured_at": time.strftime("%Y-%m-%d %H:%M"), **data}
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf8")
    print("written", OUT / f"{name}.json")


# ---- measurements -------------------------------------------------------------
def measure_kv(base: str, yes: bool) -> None:
    confirm(f"KV sweep: {len(KV_SWEEP)} console runs of 30 s as research {KV_SWEEP}", yes)
    rows = []
    for words, c in KV_SWEEP:
        params = {"prompt_words": words, "concurrency": c}
        rows.append(kv_row(params, run_console(base, params)))
        print(rows[-1], flush=True)
    save("kv-sweep", {"runs_s": 30, "tenant": "research", "rows": rows})


def _pod_ready_after(t0: float, old: set[str]) -> float | None:
    while time.time() - t0 < 120:
        pods = json.loads(kubectl("get", "pods", "-l", "app=litellm", "-o", "json"))["items"]
        for p in pods:
            ready = any(c["type"] == "Ready" and c["status"] == "True" for c in p["status"].get("conditions", []))
            if p["metadata"]["name"] not in old and ready:
                return time.time() - t0
        time.sleep(1)
    return None


def measure_gateway(base: str, yes: bool) -> None:
    confirm("Gateway drill: console run 60 s at 8 parallel as research; the litellm pod is deleted at 20 s", yes)
    old = {p.split("/")[-1] for p in kubectl("get", "pods", "-l", "app=litellm", "-o", "name").split()}
    result: dict = {}
    t = threading.Thread(target=lambda: result.update(run=run_console(base, {"concurrency": 8, "duration_s": 60})))
    t.start()
    time.sleep(20)
    t0 = time.time()
    kubectl("delete", "pod", "-l", "app=litellm", "--wait=false")
    ready = _pod_ready_after(t0, old)
    t.join()
    run = result["run"]
    save("gateway-drill", {"concurrency": 8, "duration_s": 60, "delete_at_s": 20,
                           **drill_summary(run["timeline"], run["summary"], 20.0, ready)})


def _drill_key(gw: str, master: str, **limits) -> str:
    status, body = http(gw + "/key/generate", "POST", {"models": ["qwen38"], "key_alias": f"drill-{uuid.uuid4().hex[:6]}",
                                                       **limits}, master)
    if status != 200:
        raise SystemExit(f"key not created: HTTP {status}")
    return body["key"]


def measure_budget(base: str, yes: bool) -> None:
    confirm("Budget and rpm drill: two temporary keys, at most 60 short requests (64 output tokens), keys deleted",
            yes)
    master = secret("masterKey")
    with gateway() as gw:
        keys = []
        deleted = True
        try:
            rpm_key = _drill_key(gw, master, rpm_limit=5, max_budget=1.0)
            keys.append(rpm_key)
            rpm_status = [chat(gw, rpm_key, 10, 8)[0] for _ in range(10)]
            budget_key = _drill_key(gw, master, rpm_limit=600, max_budget=0.001)
            keys.append(budget_key)
            ok, prompt_t, completion_t, refused_at = 0, 0, 0, None
            for i in range(50):
                status, body = chat(gw, budget_key, 20, 64)
                if status != 200:
                    refused_at = i + 1
                    break
                ok += 1
                prompt_t += body["usage"]["prompt_tokens"]
                completion_t += body["usage"]["completion_tokens"]
            time.sleep(5)  # spend is written asynchronously
            _, info = http(gw + f"/key/info?key={budget_key}", key=master)
            recorded = info.get("info", {}).get("spend")
        finally:
            if keys:
                deleted = http(gw + "/key/delete", "POST", {"keys": keys}, master)[0] == 200
    save("budget-drill", {"keys_deleted": deleted,
                          "rpm": {"limit_per_min": 5, "sent": 10, "ok": rpm_status.count(200),
                                  "refused": len(rpm_status) - rpm_status.count(200)},
                          "budget": {"max_budget_usd": 0.001, "ok": ok, "refused_at_request": refused_at,
                                     "spend_recorded_usd": recorded,
                                     "spend_computed_usd": expected_spend(prompt_t, completion_t)}})
    if not deleted:
        print("WARNING: the temporary drill keys were NOT deleted; delete them by key_alias 'drill-*' in the "
              "gateway", flush=True)
        raise SystemExit(1)


def measure_alert(base: str, yes: bool) -> None:
    load_s = 150
    confirm(f"Alert drill: {load_s} s of research at 16 parallel (console) plus engineering at 8 (gateway): "
            "24 requests on 16 model slots; then wait for the alert to resolve (at most 5 min)", yes)
    eng = json.loads(secret("tenantKeysJson"))["engineering"]
    samples: list[tuple[float, str]] = []
    snapshot: dict = {}
    t0 = time.time()
    with gateway() as gw:
        stop = time.time() + load_s

        def engineering() -> None:
            while time.time() < stop:
                chat(gw, eng, 600, 256)

        workers = [threading.Thread(target=engineering) for _ in range(8)]
        console = threading.Thread(target=run_console,
                                   args=(base, {"concurrency": 16, "duration_s": load_s, "prompt_words": 600,
                                                "max_tokens": 256}))
        for w in [console, *workers]:
            w.start()
        while time.time() - t0 < load_s + 300:
            _, alerts = http(base + "/api/status?view=alerts")
            state = next((a["state"] for a in alerts if a["name"] == "ModelQueueBuildingUp"), "unknown") \
                if isinstance(alerts, list) else "unknown"
            samples.append((round(time.time() - t0, 1), state))
            if state == "firing" and not snapshot:
                _, teams = http(base + "/api/status?view=teams")
                snapshot = {"alerts": alerts, "teams": teams}
            if time.time() - t0 > load_s and state != "firing" and any(s == "firing" for _, s in samples):
                break
            time.sleep(5)
        for w in [console, *workers]:
            w.join()
    save("alert-drill", {"load_s": load_s, "parallel": {"research": 16, "engineering": 8},
                         **alert_times(samples, float(load_s)), "samples": samples, "snapshot_when_firing": snapshot})


def measure_helm(base: str, yes: bool) -> None:
    out = subprocess.run([HELM, "history", "llm-platform", "-n", NS, "-o", "json"], check=True,
                         capture_output=True, text=True).stdout
    save("helm-history", {"revisions": json.loads(out)})


def measure_eval(base: str, yes: bool) -> None:
    status, result = http(base + "/api/agent/eval")
    if status != 200:
        raise SystemExit(f"no evaluation result: HTTP {status}")
    save("eval", result)


def main() -> None:
    steps = {"kv": measure_kv, "gateway": measure_gateway, "budget": measure_budget, "alert": measure_alert,
             "helm": measure_helm, "eval": measure_eval}
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=steps)
    ap.add_argument("--base", default="http://127.0.0.1:18500")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    steps[args.step](args.base, args.yes)


if __name__ == "__main__":
    main()
