"""Every local link of the built site points to a file of the build.

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


def test_local_links_resolve():
    build.main()
    missing = []
    for page in build.OUT.rglob("*.html"):
        for ref in re.findall(r'(?:href|src)="([^"]+)"', page.read_text()):
            ref = ref.split("#", 1)[0]
            if not ref or re.match(r"^[a-z]+:", ref):
                continue
            target = (page.parent / ref).resolve()
            out = build.OUT.resolve()
            if target.is_relative_to(out) and target.relative_to(out).parts[:1] in {(p,) for p in PROXIED}:
                continue
            if not target.exists():
                missing.append(f"{page.relative_to(build.OUT)} -> {ref}")
    assert not missing, missing
