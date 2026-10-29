#!/usr/bin/env python3
"""Build the static site from README.md, docs/ and docs/benchmark-results.json.

The output is tracked in git (deploy/origin/site) and reaches the web server by git pull; the build is
deterministic so a test can compare the tracked pages with a fresh build.
Usage: python site/build.py
"""
import html
import json
import os
import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy" / "origin" / "site"
EXT = ["tables", "fenced_code", "sane_lists"]

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2430;--muted:#667085;--line:#e4e7ec;--accent:#2563eb;--code:#eef1f5}
@media (prefers-color-scheme: dark){:root{--bg:#0f1318;--card:#171c23;--text:#e6e9ef;--muted:#98a2b3;--line:#2a313b;--accent:#5b8def;--code:#222932}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,sans-serif}
a{color:var(--accent)}
.top{border-bottom:1px solid var(--line);background:var(--card)}
.top div{max-width:960px;margin:0 auto;padding:12px 16px;display:flex;gap:18px;flex-wrap:wrap;align-items:center}
.top b{margin-right:auto}.top a{text-decoration:none;color:var(--muted);font-size:14px}.top a:hover{color:var(--text)}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:30px;line-height:1.25;margin:0 0 8px}h2{margin-top:36px}
p.lead{font-size:18px;color:var(--muted);margin:0 0 24px}
pre,code{background:var(--code);border-radius:6px;font:14px/1.5 ui-monospace,monospace}
code{padding:1px 5px}pre{padding:12px 14px;overflow-x:auto}pre code{padding:0;background:none}
table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}th{color:var(--muted);font-weight:500}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:20px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat b{display:block;font-size:28px;line-height:1.2}.stat span{color:var(--muted);font-size:14px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:20px 0}
.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;text-decoration:none;color:var(--text)}
.card:hover{border-color:var(--accent)}.card b{display:block;margin-bottom:4px}.card span{color:var(--muted);font-size:14px}
.tag{font-size:12px;border:1px solid var(--line);border-radius:99px;padding:1px 8px;color:var(--muted);margin-left:6px}
footer{color:var(--muted);font-size:13px;margin-top:48px}
"""

# The provisioned dashboard; Grafana's own root page is an empty home for anonymous viewers.
GRAFANA = "grafana/d/llm-platform/llm-platform"
NAV = [("Overview", "index.html"), ("Architecture", "docs/architecture.html"),
       ("Benchmark report", "docs/benchmark-report.html"), ("Handover", "docs/handover.html"),
       ("Console", "console/"), ("Grafana: LLM platform", GRAFANA)]


def page(title: str, body: str, depth: int) -> str:
    up = "../" * depth
    nav = "".join(f'<a href="{up}{href}">{label}</a>' for label, href in NAV)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(title)}</title><link rel="icon" href="data:,">'
            f'<link rel="stylesheet" href="{up}style.css"></head><body>'
            f'<div class="top"><div><b>Private LLM platform</b>{nav}</div></div>'
            f'<main>{body}</main></body></html>')


def md_to_html(path: Path) -> str:
    body = markdown.markdown(path.read_text(encoding="utf8"), extensions=EXT)
    return re.sub(r'href="([^"#:]+)\.md(#[^"]*)?"', lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"', body)


def write(out: Path, rel: str, content: str) -> None:
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf8")


def landing() -> str:
    data = json.loads((ROOT / "docs" / "benchmark-results.json").read_text(encoding="utf8"))
    runs = {r["name"]: r["summary"] for r in data["runs"]}
    s1, s16 = runs["baseline c=1"], runs["baseline c=16"]
    gpu = [runs[f"baseline c={c}"]["gpu_util_avg"] for c in (1, 2, 4, 8, 16)]
    speedup = s16["tokens_per_second"] / s1["tokens_per_second"]
    drop = (1 - s16["usd_per_million_tokens"] / s1["usd_per_million_tokens"]) * 100
    return f"""
<h1>One gateway, one large model, several teams</h1>
<p class="lead">A small private LLM platform running on a single NVIDIA GB10 machine: per-team keys and limits,
dashboards, alerts and a console that proves the numbers. Everything below was measured on the real model.</p>
<div class="grid">
  <div class="stat"><b>{speedup:.1f}×</b><span>output tokens/s going from 1 to 16 parallel requests ({s1['tokens_per_second']:.1f} → {s16['tokens_per_second']:.1f})</span></div>
  <div class="stat"><b>−{drop:.0f} %</b><span>cost per 1M output tokens at the same time (base: 1 request; assumed GPU price 0.20 USD/hour)</span></div>
  <div class="stat"><b>{s1['ttft_p95_s']:.2f} → {s16['ttft_p95_s']:.2f} s</b><span>time to first token p95: the price of the speed-up</span></div>
  <div class="stat"><b>{min(gpu):.0f}–{max(gpu):.0f} %</b><span>GPU utilization in every run: it cannot show this difference</span></div>
</div>
<h2>Explore</h2>
<div class="cards">
  <a class="card" href="console/"><b>Live console <span class="tag">password</span></b><span>Start a load test as a team, watch tokens per second, latency, GPU and queue move, compare before and after.</span></a>
  <a class="card" href="{GRAFANA}"><b>Grafana dashboard LLM platform <span class="tag">password</span></b><span>12 panels from Prometheus: model, GPU and gateway, with 6 alert rules behind it.</span></a>
  <a class="card" href="docs/benchmark-report.html"><b>Benchmark report</b><span>Throughput, latency and cost per million tokens from 1 to 16 parallel requests; what the gateway adds.</span></a>
  <a class="card" href="docs/architecture.html"><b>Architecture</b><span>Components, decisions and trade-offs, and what changes at customer scale.</span></a>
  <a class="card" href="docs/handover.html"><b>Handover</b><span>What a customer team receives and how to operate it.</span></a>
  <a class="card" href="readme.html"><b>README</b><span>What it is, how to run it, honest limits.</span></a>
</div>
<h2>Runbooks</h2>
<ul>
  <li><a href="docs/runbooks/01-model-endpoint-down.html">Model endpoint down</a></li>
  <li><a href="docs/runbooks/02-slow-answers-or-queue.html">Slow answers or a growing queue</a></li>
  <li><a href="docs/runbooks/03-kv-cache-full.html">KV cache nearly full</a></li>
  <li><a href="docs/runbooks/04-gateway-errors-and-limits.html">Gateway errors and team limits</a></li>
  <li><a href="docs/runbooks/05-release-upgrade-rollback.html">Upgrade and roll back a release</a></li>
</ul>
<h2>Built with</h2>
<p>vLLM (model server), LiteLLM (gateway), Kubernetes in Docker (<code>kind</code>) and Helm, PostgreSQL,
Prometheus, Grafana, FastAPI and plain JavaScript (console), <code>nvidia-smi</code> exporter.</p>
<h2>Access</h2>
<p>The live console and Grafana start real load on a GPU, so they are protected by a password. The documents
and the report are open.</p>
<footer>Measured {data["generated_at"][:10]}, built from the project repository. Benchmark numbers: one 30-second run per setting on a shared GPU; see the report for limits.</footer>
"""


def publish_dir(out: Path, fill) -> None:
    """Run `fill(directory)` on a sibling directory, then swap it for `out`; an error leaves `out` as it was."""
    tmp = out.with_name(out.name + ".new")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        fill(tmp)
        if out.exists():
            shutil.rmtree(out)
        os.replace(tmp, out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def main(out: Path = OUT) -> None:
    pages = [("readme.html", ROOT / "README.md", "README"), ("deploy/README.html", ROOT / "deploy" / "README.md", "publishing")]
    for name in ("architecture", "benchmark-report", "handover"):
        pages.append((f"docs/{name}.html", ROOT / "docs" / f"{name}.md", name))
    for p in sorted((ROOT / "docs" / "runbooks").glob("*.md")):
        pages.append((f"docs/runbooks/{p.stem}.html", p, p.stem))

    def fill(directory: Path) -> None:
        write(directory, "style.css", CSS)
        write(directory, "index.html", page("Private LLM platform", landing(), 0))
        for rel, src, title in pages:
            write(directory, rel, page(title, md_to_html(src), rel.count("/")))

    publish_dir(out, fill)
    print("built", len(pages) + 1, "pages into", out)


if __name__ == "__main__":
    main()
