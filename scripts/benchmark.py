#!/usr/bin/env python3
"""Run the benchmark sweep through the console API and write docs/benchmark-results.json.

The same API the web page uses: POST /api/runs, then poll GET /api/runs until the run ends.
Usage: scripts/benchmark.py [--base http://127.0.0.1:18500] [--out docs/benchmark-results.json]
"""
import argparse
import json
import time
import urllib.request

SWEEP = [
    # name, params
    ("baseline c=1", {"tenant": "research", "concurrency": 1, "shape": "unique"}),
    ("baseline c=2", {"tenant": "research", "concurrency": 2, "shape": "unique"}),
    ("baseline c=4", {"tenant": "research", "concurrency": 4, "shape": "unique"}),
    ("baseline c=8", {"tenant": "research", "concurrency": 8, "shape": "unique"}),
    ("baseline c=16", {"tenant": "research", "concurrency": 16, "shape": "unique"}),
    ("gateway cache, repeated prompts, c=8", {"tenant": "research", "concurrency": 8, "shape": "repeated"}),
    ("team limit, operations, c=8", {"tenant": "operations", "concurrency": 8, "shape": "unique", "duration_s": 20}),
]
DEFAULTS = {"duration_s": 30, "max_tokens": 128, "prompt_words": 60, "gpu_usd_per_hour": 0.2}


def call(base, path, method="GET", body=None):
    req = urllib.request.Request(base + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18500")
    ap.add_argument("--out", default="docs/benchmark-results.json")
    args = ap.parse_args()
    results = []
    for name, extra in SWEEP:
        params = {**DEFAULTS, **extra}
        before = {r["id"] for r in call(args.base, "/api/runs")}
        run_id = call(args.base, "/api/runs", "POST", params)["id"]
        print(f"started {name} ({run_id})", flush=True)
        while True:
            time.sleep(2)
            ids = {r["id"] for r in call(args.base, "/api/runs")}
            if run_id in ids - before:
                break
        run = call(args.base, f"/api/runs/{run_id}")
        results.append({"name": name, **run})
        s = run["summary"]
        print(f"  ok={s["ok"]} errors={s["errors"]} tok/s={s["tokens_per_second"]:.1f} "
              f"ttft_p95={s["ttft_p95_s"]} gpu_avg={s["gpu_util_avg"]}", flush=True)
        time.sleep(3)
    call(args.base, f"/api/runs/{results[0]["id"]}", "PATCH", {"label": "before"})
    call(args.base, f"/api/runs/{results[3]["id"]}", "PATCH", {"label": "after"})
    with open(args.out, "w", encoding="utf8") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": results}, f, indent=1)
    print("written", args.out)


if __name__ == "__main__":
    main()
