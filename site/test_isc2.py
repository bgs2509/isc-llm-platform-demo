"""Page rules of the isc-2 site: every key filled, ASCII only, six sections, new-tab links, no dead links,
tracked pages equal a fresh build.

Run: python -m pytest site
"""
import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _load(name: str, path: Path):
    # The package name "site" is taken by the standard library, so the builders are loaded by their paths.
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = _load("site_isc2_build", HERE / "isc2" / "build.py")

# Served by the origin proxy, not by the build.
PROXIED = {"console", "grafana"}
TOPIC_PAGES = ["inference.html", "infrastructure.html", "gateway.html", "rag.html", "observability.html",
               "delivery.html"]
SECTIONS = ["Challenge", "Solution", "Results", "Trade-offs", "What I'd change at scale", "Links"]


def _eval_result() -> dict:
    rows = []
    for i in range(1, 11):
        rows.append({"id": f"B{i}", "kind": "blog", "question": f"Blog question {i}?", "answer": "An answer.",
                     "steps": [{"tool": "search_docs", "args": {"query": "q"}, "result": []}],
                     "sources": [{"title": "Article", "url": "https://example.com/blog/a"}],
                     "latency_s": 2.5 + i / 10, "tokens": 900, "first_tool": "search_docs", "hit": i % 4 != 0,
                     "tool_ok": None, "claims_supported": 2, "claims_total": 3})
    for i in range(1, 7):
        rows.append({"id": f"P{i}", "kind": "platform", "question": f"Platform question {i}?", "answer": "OK.",
                     "steps": [{"tool": "platform_status", "args": {"view": "alerts"}, "result": []}],
                     "sources": [], "latency_s": 3.0, "tokens": 700, "first_tool": "platform_status", "hit": None,
                     "tool_ok": i != 5, "claims_supported": 1, "claims_total": 2, "judge_error": None,
                     "facts_stated": 1, "facts_total": 2})
    # The console stores unix seconds (evaluate.py); 1793350800 = 2026-10-30 09:00 UTC.
    return {"started": 1793350500.0, "finished": 1793350800.0, "team": "research", "rows": rows,
            "summary": {"hit_at_3": 0.8, "tool_accuracy": 5 / 6, "faithfulness": 0.7, "hits": 8, "blog_total": 10,
                        "tool_ok": 5, "platform_total": 6, "claims_supported": 28, "claims_total": 40,
                        "latency_p95_s": 4.2, "prompt_tokens": 9000, "completion_tokens": 2000,
                        "usd_per_1k_questions": 0.31},
            "chunking": {"kind": {"chunks": 90, "hits": 8}, "fixed": {"chunks": 120, "hits": 6}, "blog_total": 10},
            "measured_at": "2026-10-30 10:06"}


def fixture_inputs() -> dict:
    bench = json.loads((ROOT / "docs" / "benchmark-results.json").read_text(encoding="utf8"))
    kv = [(200, 4, 12.0, 0, 0.4, 90.0), (500, 8, 20.0, 0, 0.8, 120.0), (1000, 8, 31.0, 0, 1.0, 118.0),
          (1000, 16, 52.0, 4, 3.1, 170.0), (2000, 16, 78.0, 9, 5.6, 150.0)]
    measurements = {
        "kv-sweep": {"measured_at": "2026-10-30 09:00", "runs_s": 30, "tenant": "research", "rows": [
            {"prompt_words": w, "concurrency": c, "kv_cache_peak_pct": kvp, "waiting_peak": wt, "ttft_p95_s": tt,
             "tokens_per_s": tps} for w, c, kvp, wt, tt, tps in kv]},
        "gateway-drill": {"measured_at": "2026-10-30 09:10", "concurrency": 8, "duration_s": 60, "delete_at_s": 20,
                          "requests": 40, "failed": 6, "no_answer_s": 17.0, "recovered_after_s": 25.0,
                          "seconds_to_ready": 14.0},
        "budget-drill": {"measured_at": "2026-10-30 09:20",
                         "rpm": {"limit_per_min": 5, "sent": 10, "ok": 5, "refused": 5},
                         "budget": {"max_budget_usd": 0.001, "ok": 6, "refused_at_request": 7,
                                    "spend_recorded_usd": 0.00101, "spend_computed_usd": 0.00098}},
        "alert-drill": {"measured_at": "2026-10-30 09:30", "load_s": 150,
                        "parallel": {"research": 16, "engineering": 8}, "fired_after_s": 65.0,
                        "resolved_after_load_end_s": 40.0,
                        "samples": [[5.0, "inactive"], [65.0, "firing"], [200.0, "inactive"]],
                        "snapshot_when_firing": {"alerts": [{"name": "ModelQueueBuildingUp", "state": "firing",
                                                             "query": "x", "value": 7.0}], "teams": []}},
        "helm-history": {"measured_at": "2026-10-30 09:40", "revisions": [
            {"revision": 1, "updated": "2026-10-27T10:00:00.1Z", "status": "superseded", "chart": "llm-platform-0.1.0",
             "app_version": "1", "description": "Install complete"},
            {"revision": 2, "updated": "2026-10-27T11:00:00.1Z", "status": "failed", "chart": "llm-platform-0.1.0",
             "app_version": "1", "description": "Upgrade failed"},
            {"revision": 3, "updated": "2026-10-27T11:01:00.1Z", "status": "deployed", "chart": "llm-platform-0.1.0",
             "app_version": "1", "description": "Upgrade complete"}]},
        "eval": _eval_result(),
    }
    return {"commit": "abc1234", "tests": {"console": 120, "site": 9, "scripts": 12}, "benchmark": bench,
            "measurements": measurements}


@pytest.fixture(scope="module")
def pages() -> dict:
    return build.render(fixture_inputs())


def _write(pages: dict, out: Path) -> None:
    for rel, text in pages.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf8")


def test_every_key_is_filled_and_an_unknown_key_fails_with_its_name(pages, tmp_path):
    for rel, text in pages.items():
        assert "{{" not in text, f"{rel} has an unfilled key"
    templates = tmp_path / "templates"
    shutil.copytree(HERE / "isc2" / "templates", templates)
    index = templates / "index.html"
    index.write_text(index.read_text(encoding="utf8").replace("</main>", "{{no_such_key}}</main>"), encoding="utf8")
    with pytest.raises(Exception, match="no_such_key"):
        build.render(fixture_inputs(), templates=templates)


def test_no_character_outside_ascii(pages):
    bad = {rel: sorted({c for c in text if ord(c) > 127}) for rel, text in pages.items()}
    assert not {k: v for k, v in bad.items() if v}
    # a site built before the measurements exist is still ASCII and says so
    empty = build.render({"commit": "abc1234", "tests": {"console": 1, "site": 1, "scripts": 1},
                          "benchmark": fixture_inputs()["benchmark"], "measurements": {}})
    assert all(ord(c) < 128 for text in empty.values() for c in text)
    assert "not measured yet" in empty["inference.html"]


@pytest.mark.parametrize("name", TOPIC_PAGES)
def test_topic_page_has_the_six_sections_in_order(pages, name):
    heads = [h.replace("&#x27;", "'").replace("&#39;", "'") for h in re.findall(r"<h2><small>([^<]+)</small>", pages[name])]
    position = -1
    for section in SECTIONS:
        assert section in heads[position + 1:], f"{name}: {section} missing or out of order in {heads}"
        position = heads.index(section, position + 1)
    if name == "rag.html":
        assert "Ask the agent" in heads and "API" in heads


def test_every_link_opens_in_a_new_tab(pages):
    bad = []
    for rel, text in pages.items():
        for tag in re.findall(r"<a\b[^>]*>", text):
            if 'target="_blank"' not in tag or 'rel="noopener"' not in tag:
                bad.append((rel, tag))
    assert not bad, bad[:5]


def test_local_links_and_assets_resolve(pages, tmp_path):
    _write(pages, tmp_path)
    out = tmp_path.resolve()
    missing = []
    for page in tmp_path.rglob("*.html"):
        for ref in re.findall(r'(?:href|src)="([^"]+)"', page.read_text(encoding="utf8")):
            ref = ref.split("#", 1)[0]
            if not ref or re.match(r"^[a-z]+:", ref):
                continue
            target = (page.parent / ref).resolve()
            if target.is_relative_to(out) and target.relative_to(out).parts[:1] in {(p,) for p in PROXIED}:
                continue
            if not target.is_relative_to(out) or not target.exists():
                missing.append(f"{page.relative_to(tmp_path)} -> {ref}")
    assert not missing, missing
    # the anchors the pages link to exist
    assert 'id="eval"' in pages["rag.html"] and 'id="alerts"' in pages["observability.html"]


def test_platform_eval_rows_show_expected_facts_and_blog_rows_do_not(pages):
    html = pages["rag.html"]
    assert html.count("Expected facts stated: 1 of 2") == 6
    assert "Expected facts stated: 0 of 0" not in html
    assert "evalRow" in (HERE / "isc2" / "static" / "site.js").read_text(encoding="utf8")
    assert "Expected facts stated" in (HERE / "isc2" / "static" / "site.js").read_text(encoding="utf8")


def test_tracked_pages_equal_a_fresh_build_from_the_saved_inputs():
    inputs_file = HERE / "isc2" / "inputs.json"
    if not inputs_file.exists():
        pytest.skip("site/isc2/inputs.json does not exist yet: it is written by the first real build, "
                    "after the measurements")
    fresh = build.render(json.loads(inputs_file.read_text(encoding="utf8")))
    tracked = {p.relative_to(build.OUT).as_posix(): p.read_text(encoding="utf8")
               for p in build.OUT.rglob("*") if p.is_file()}
    assert sorted(tracked) == sorted(fresh), "rebuild: python site/isc2/build.py"
    changed = [k for k in fresh if fresh[k] != tracked[k]]
    assert not changed, f"rebuild: python site/isc2/build.py; changed {changed}"
