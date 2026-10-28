#!/usr/bin/env python3
"""Tiny GPU exporter for hosts without DCGM: reads `nvidia-smi --query-gpu`.

Serves Prometheus text on /metrics and JSON on /json. Values that nvidia-smi reports as
"[N/A]" (for example memory on unified-memory systems) are skipped.
Usage: gpu_exporter.py <listen host> <listen port>
"""
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIELDS = ["utilization.gpu", "temperature.gpu", "power.draw"]
NAMES = {
    "utilization.gpu": "gpu_utilization_percent",
    "temperature.gpu": "gpu_temperature_celsius",
    "power.draw": "gpu_power_watts",
}
_cache = {"t": 0.0, "v": {}}
_lock = threading.Lock()


def sample() -> dict:
    with _lock:
        if time.monotonic() - _cache["t"] < 0.5:
            return _cache["v"]
        values: dict = {}
        try:
            out = subprocess.run(
                ["nvidia-smi", f"--query-gpu={','.join(FIELDS)}", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=True)
            parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
            for field, part in zip(FIELDS, parts):
                try:
                    values[NAMES[field]] = float(part)
                except ValueError:
                    pass
        except (subprocess.SubprocessError, OSError, IndexError):
            pass
        _cache["t"], _cache["v"] = time.monotonic(), values
        return values


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        values = sample()
        if self.path.startswith("/json"):
            body, ctype = json.dumps(values), "application/json"
        elif self.path.startswith("/metrics"):
            lines = []
            for name, value in values.items():
                lines += [f"# TYPE {name} gauge", f"{name} {value}"]
            body, ctype = "\n".join(lines) + "\n", "text/plain; version=0.0.4"
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer((sys.argv[1], int(sys.argv[2])), Handler).serve_forever()
