"""Corpus and retrieval for the RAG agent (pure).

PURPOSE: load the blog articles, cut them into chunks by kind, rank chunks for a query.
INPUTS: a directory of `*.md` files with front matter `title, url, author, date, kind`; a query string.
OUTPUTS: `load_articles(dir) -> list[Article]`; `chunk(article) -> list[Chunk]` where
    `Chunk(id, title, url, text)` and `text` starts with "<title> (<url>)"; `Index(chunks).search(query, k=3)
    -> list[Hit(chunk, score)]`, best first, empty for a query with no known words.
DEPENDS: standard library only.
Errors: an article without `title`, `url` or `kind` raises `ValueError` naming the file (fail fast at load).
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus" / "blog"
MIN_SECTION_WORDS = 80
MAX_SECTION_WORDS = 400
PLAIN_WORDS = 250
FIXED_WORDS = 250
K1, B = 1.5, 0.75
_REQUIRED = ("title", "url", "kind")
_TOKEN = re.compile(r"\w+")


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    url: str
    author: str
    date: str
    kind: str
    body: str


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    url: str
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def _parse(path: Path) -> Article:
    head, sep, body = path.read_text(encoding="utf8").partition("\n---\n")
    if not head.startswith("---") or not sep:
        raise ValueError(f"{path.name}: no front matter")
    meta: dict[str, str] = {}
    for line in head.splitlines()[1:]:
        key, _, raw = line.partition(": ")
        meta[key] = json.loads(raw)
    missing = [k for k in _REQUIRED if not meta.get(k)]
    if missing:
        raise ValueError(f"{path.name}: front matter lacks {', '.join(missing)}")
    body = re.sub(r"^\s*# .*\n", "", body, count=1)  # the title is already in front matter
    return Article(path.stem, meta["title"], meta["url"], meta.get("author", ""), meta.get("date", ""),
                   meta["kind"], body.strip())


def load_articles(directory: Path = CORPUS_DIR) -> list[Article]:
    return [_parse(p) for p in sorted(Path(directory).glob("*.md"))]


def _words(text: str) -> int:
    return len(text.split())


def _make(a: Article, n: int, blocks: list[str]) -> Chunk:
    return Chunk(f"{a.slug}#{n}", a.title, a.url, f"{a.title} ({a.url})\n\n" + "\n\n".join(blocks))


def _blocks(body: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]


def _pack(blocks: list[str], limit: int) -> list[list[str]]:
    """Consecutive blocks, a group closes before it would exceed `limit` words."""
    groups: list[list[str]] = []
    size = 0
    for b in blocks:
        if groups and size + _words(b) > limit:
            groups.append([])
            size = 0
        if not groups:
            groups.append([])
        groups[-1].append(b)
        size += _words(b)
    return groups


def _sections(blocks: list[str]) -> list[list[str]]:
    """Split at `##`/`###` headings, merging sections under MIN_SECTION_WORDS into the next one."""
    groups: list[list[str]] = []
    pending: list[str] = []
    for b in blocks:
        if re.match(r"###? ", b) and pending and _words(" ".join(pending)) >= MIN_SECTION_WORDS:
            groups.append(pending)
            pending = []
        pending.append(b)
    if pending:
        if groups and _words(" ".join(pending)) < MIN_SECTION_WORDS:
            groups[-1] += pending  # a short last section joins the previous one
        else:
            groups.append(pending)
    return groups


def _plain(blocks: list[str]) -> list[list[str]]:
    """Paragraphs packed to about PLAIN_WORDS; each chunk repeats the last paragraph of the previous one."""
    groups: list[list[str]] = []
    i = 0
    while i < len(blocks):
        j, size = i, 0
        while j < len(blocks) and size < PLAIN_WORDS:
            size += _words(blocks[j])
            j += 1
        groups.append(blocks[i:j])
        i = j - 1 if j < len(blocks) and j - 1 > i else j
    return groups


def chunk(a: Article) -> list[Chunk]:
    blocks = _blocks(a.body)
    if a.kind == "case":
        groups = [blocks]
    elif a.kind == "sections":
        groups = [g for s in _sections(blocks) for g in _pack(s, MAX_SECTION_WORDS)]
    elif a.kind == "plain":
        groups = _plain(blocks)
    else:
        raise ValueError(f"{a.slug}: unknown kind {a.kind!r}")
    return [_make(a, n, g) for n, g in enumerate(groups)]


def chunk_fixed(a: Article) -> list[Chunk]:
    """Fixed windows of FIXED_WORDS words; the baseline for the chunking comparison only."""
    ws = a.body.split()
    return [_make(a, n, [" ".join(ws[i:i + FIXED_WORDS])]) for n, i in enumerate(range(0, len(ws), FIXED_WORDS))]


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class Index:
    """BM25 (k1 = 1.5, b = 0.75) over chunk texts."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self._tf = [Counter(_tokens(c.text)) for c in chunks]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = sum(self._len) / len(chunks) if chunks else 0.0
        df = Counter(t for tf in self._tf for t in tf)
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int = 3) -> list[Hit]:
        terms = [t for t in dict.fromkeys(_tokens(query)) if t in self._idf]
        hits = []
        for chunk_, tf, size in zip(self._chunks, self._tf, self._len):
            score = sum(
                self._idf[t] * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * size / self._avg))
                for t in terms if t in tf
            )
            if score > 0:
                hits.append(Hit(chunk_, score))
        return sorted(hits, key=lambda h: h.score, reverse=True)[:k]
