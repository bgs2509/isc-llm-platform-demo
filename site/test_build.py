"""Every local link of the built site points to a file of the build; the tracked pages equal a fresh build.

Run: python -m pytest site
"""
import importlib.util
import re
from pathlib import Path

# The package name "site" is taken by the standard library, so the builder is loaded by its path.
_spec = importlib.util.spec_from_file_location("site_build", Path(__file__).with_name("build.py"))
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

# Served by the origin proxy, not by the build.
PROXIED = {"console", "grafana"}


def test_an_interrupted_build_leaves_the_old_site_untouched(tmp_path):
    out = tmp_path / "site"
    out.mkdir()
    (out / "old.html").write_text("old")

    def broken(directory):
        (directory / "half.html").write_text("half")
        raise RuntimeError("interrupted")

    try:
        build.publish_dir(out, broken)
    except RuntimeError:
        pass
    assert [p.name for p in out.iterdir()] == ["old.html"]
    assert [p.name for p in tmp_path.iterdir()] == ["site"]  # no half-written sibling left


def test_a_finished_build_replaces_the_old_site(tmp_path):
    out = tmp_path / "site"
    out.mkdir()
    (out / "old.html").write_text("old")
    build.publish_dir(out, lambda d: (d / "new.html").write_text("new"))
    assert [p.name for p in out.iterdir()] == ["new.html"] and [p.name for p in tmp_path.iterdir()] == ["site"]


def test_local_links_resolve(tmp_path):
    build.main(tmp_path)
    missing = []
    for page in tmp_path.rglob("*.html"):
        for ref in re.findall(r'(?:href|src)="([^"]+)"', page.read_text()):
            ref = ref.split("#", 1)[0]
            if not ref or re.match(r"^[a-z]+:", ref):
                continue
            target = (page.parent / ref).resolve()
            out = tmp_path.resolve()
            if target.is_relative_to(out) and target.relative_to(out).parts[:1] in {(p,) for p in PROXIED}:
                continue
            if not target.exists():
                missing.append(f"{page.relative_to(tmp_path)} -> {ref}")
    assert not missing, missing


def test_tracked_pages_equal_fresh_build(tmp_path):
    build.main(tmp_path)
    fresh = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    tracked = {p.relative_to(build.OUT): p.read_bytes() for p in build.OUT.rglob("*") if p.is_file()}
    assert sorted(tracked) == sorted(fresh), "rebuild: python site/build.py"
    changed = [str(k) for k in fresh if fresh[k] != tracked[k]]
    assert not changed, f"rebuild: python site/build.py; changed {changed}"
