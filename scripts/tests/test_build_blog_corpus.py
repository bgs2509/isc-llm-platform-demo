"""Pure parts of scripts/build_blog_corpus.py: argument parsing, failure counting, exit order (no network)."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("corpus_build", Path(__file__).parent.parent / "build_blog_corpus.py")
cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cb)


def test_command_defaults_to_all_and_rejects_unknown():
    assert cb.parse_args([]) == "all"
    assert cb.parse_args(["fetch"]) == "fetch"
    with pytest.raises(SystemExit):
        cb.parse_args(["fetsh"])


def test_fetch_counts_failed_downloads(tmp_path, monkeypatch):
    (tmp_path / "_index.html").write_text('<a href="/blog/a">a</a> <a href="/blog/b">b</a>', encoding="utf8")

    def get(url):
        if url.endswith("/blog/b"):
            raise OSError("boom")
        return b"<html>ok</html>"

    monkeypatch.setattr(cb, "HTML_DIR", tmp_path)
    monkeypatch.setattr(cb, "get", get)
    monkeypatch.setattr(cb.time, "sleep", lambda s: None)
    assert cb.fetch() == 1


def test_all_stops_before_extract_when_a_download_failed(monkeypatch):
    calls = []
    monkeypatch.setattr(cb, "fetch", lambda: 2)
    monkeypatch.setattr(cb, "extract", lambda: calls.append("extract"))
    assert cb.main(["all"]) == 1 and calls == []


def test_all_extracts_when_nothing_failed(monkeypatch):
    calls = []
    monkeypatch.setattr(cb, "fetch", lambda: 0)
    monkeypatch.setattr(cb, "extract", lambda: calls.append("extract"))
    assert cb.main(["all"]) == 0 and calls == ["extract"]
