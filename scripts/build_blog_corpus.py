"""Build the blog corpus: fetch the client's public blog into corpus/blog/html/ (raw HTML, ignored by version
control), then extract console/corpus/blog/*.md (front matter title, url, author, date, kind; body with
headings and lists) and print per-article structure statistics used to choose the chunking method.

Usage: python3 scripts/build_blog_corpus.py [fetch|extract|all]   (default: all)
Needs beautifulsoup4 for the extract step (host-side tool, not a console dependency).
"""
import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_DIR = ROOT / "corpus" / "blog" / "html"
OUT_DIR = ROOT / "console" / "corpus" / "blog"
SITE = "https://insightsoftmax.com"

DATE = re.compile(r"[A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}")
BLOCKS = {"h2", "h3", "h4", "p", "li", "ul", "ol", "div", "blockquote", "section", "table", "tr", "td"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch() -> None:
    """Download the blog index and every article linked from it (existing non-empty files are kept)."""
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    index = HTML_DIR / "_index.html"
    if not index.exists() or index.stat().st_size == 0:
        index.write_bytes(get(SITE + "/blog"))
    paths = sorted(set(re.findall(r"/blog/[a-z0-9$.%-]+", index.read_text(encoding="utf8"))))
    for p in paths:
        out = HTML_DIR / (p.removeprefix("/blog/").replace("$", "S") + ".html")
        if out.exists() and out.stat().st_size > 0:
            continue
        try:
            out.write_bytes(get(SITE + p))
            print("ok", p)
        except OSError as exc:
            print("FAILED", p, exc)
        time.sleep(1)
    print(len(list(HTML_DIR.glob("*.html"))), "files in", HTML_DIR)


def walk(el, out: list[str]) -> None:
    """Emit markdown lines; text directly inside an element is emitted once, nested blocks recurse."""
    from bs4 import NavigableString, Tag

    buf: list[str] = []

    def flush() -> None:
        text = re.sub(r"\s+", " ", " ".join(buf)).strip()
        buf.clear()
        if not text:
            return
        if el.name in ("h2", "h3", "h4"):
            out.append("#" * int(el.name[1]) + " " + text)
        elif el.name == "li":
            out.append("- " + text)
        elif el.name == "div" and len(text.split()) <= 4 and not text.endswith("."):
            out.append("## " + text)  # labels such as Challenge / Solution / Results
        else:
            out.append(text)

    for ch in el.children:
        if isinstance(ch, NavigableString):
            buf.append(str(ch))
        elif isinstance(ch, Tag) and ch.name in BLOCKS:
            flush()
            walk(ch, out)
        elif isinstance(ch, Tag):
            buf.append(ch.get_text(" "))
    flush()


def byline(el) -> tuple[str, str]:
    """(author, ISO date) from a 'Title | by | Author | ... | Mon. DD, YYYY' block."""
    parts = el.get_text(" | ", strip=True).split(" | ")[:12]
    author = parts[parts.index("by") + 1] if "by" in parts else ""
    raw = next((p for p in parts if DATE.fullmatch(p)), "")
    return author, datetime.strptime(raw.replace(".", ""), "%b %d, %Y").date().isoformat() if raw else ""


def extract() -> None:
    """HTML files -> markdown files with front matter; prints structure statistics."""
    from bs4 import BeautifulSoup

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = BeautifulSoup((HTML_DIR / "_index.html").read_text(encoding="utf8"), "html.parser")
    cards = {}
    for card in index.select("article.list-blog-post"):
        link = card.find("a", href=re.compile(r"/blog/"))
        cards[link["href"].rstrip("/").rsplit("/", 1)[-1].replace("$", "S")] = byline(card)
    rows = []
    for f in sorted(HTML_DIR.glob("*.html")):
        if f.name.startswith("_"):
            continue
        s = BeautifulSoup(f.read_text(encoding="utf8"), "html.parser")
        h1 = s.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else s.title.string.split(" - ")[0].strip()
        canon = s.find("link", rel="canonical")
        lines: list[str] = []
        for sel in ("div.blog-content", "div.blog-case-study"):  # intro text, then the case card
            part = s.select_one(sel)
            if part is None or not part.get_text(strip=True):
                continue
            sub: list[str] = []
            walk(part, sub)
            if sub and sub[0].lstrip("# ").startswith(("Case Study:", title[:30])):
                sub = sub[1:]  # the card repeats the title
            lines += sub
        body = "\n\n".join(lines) + "\n"
        body = re.sub(r"\n\n(?=- )", "\n", body)  # keep list items together
        blocks = [b for b in body.split("\n\n") if b]
        heads = sum(1 for b in blocks if b.startswith("#"))
        items = body.count("\n- ")
        paras = [len(b.split()) for b in blocks if not b.startswith(("#", "- "))]
        kind = "case" if "## Challenge" in body else ("sections" if heads >= 2 else "plain")
        author, date = byline(s.select_one("div.blogPost"))
        if not (author and date):  # case cards show no byline; the blog list does
            author, date = cards.get(f.stem, ("", ""))
        meta = {"title": title, "url": canon["href"] if canon else "", "author": author, "date": date, "kind": kind}
        front = "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in meta.items()) + "---\n\n"
        md = front + f"# {title}\n\n" + body
        (OUT_DIR / (f.stem + ".md")).write_text(md, encoding="utf8")
        missing = [k for k, v in meta.items() if not v]
        if missing:
            print("MISSING", missing, f.name)
        rows.append((len(md.split()), heads, len(paras), items, max(paras or [0]), kind, f.stem[:66]))
    for r in sorted(rows, reverse=True):
        print("%5d w  %2d h  %3d p  %3d li  maxp %3d  %-4s %s" % r)
    w = sorted(r[0] for r in rows)
    print("articles", len(rows), "| words total", sum(w), "median", w[len(w) // 2], "min", w[0], "max", w[-1])
    print({k: sum(r[5] == k for r in rows) for k in ("case", "sections", "plain")})


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("fetch", "all"):
        fetch()
    if step in ("extract", "all"):
        extract()
