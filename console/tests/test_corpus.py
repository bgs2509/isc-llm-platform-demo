from pathlib import Path

import pytest

from app.corpus import Article, Index, chunk, chunk_fixed, load_articles


def words(prefix: str, n: int) -> str:
    """n unique words, so coverage can be checked word by word."""
    return " ".join(f"{prefix}{i}" for i in range(n))


def article(kind: str, body: str, slug: str = "a", title: str = "Title", url: str = "https://x.test/a") -> Article:
    return Article(slug=slug, title=title, url=url, author="Ann", date="2020-01-02", kind=kind, body=body)


def test_load_articles_reads_front_matter_and_names_file_without_url(tmp_path):
    (tmp_path / "ok.md").write_text(
        '---\ntitle: "T \\"q\\""\nurl: "https://x.test/ok"\nauthor: "Ann"\ndate: "2020-01-02"\nkind: "case"\n---\n\n'
        "# T\n\nBody text.\n",
        encoding="utf8",
    )
    [a] = load_articles(tmp_path)
    assert (a.slug, a.title, a.url, a.author, a.date, a.kind) == (
        "ok", 'T "q"', "https://x.test/ok", "Ann", "2020-01-02", "case")
    assert a.body.strip() == "Body text."
    (tmp_path / "bad.md").write_text('---\ntitle: "T"\nkind: "case"\n---\n\nBody\n', encoding="utf8")
    with pytest.raises(ValueError, match="bad.md"):
        load_articles(tmp_path)


def test_case_article_is_one_chunk_starting_with_title_and_url():
    [c] = chunk(article("case", "## Challenge\n\n" + words("w", 700)))
    assert c.text.startswith("Title (https://x.test/a)")
    assert (c.title, c.url) == ("Title", "https://x.test/a")


def test_sections_merge_short_and_split_long():
    short = "## Short\n\n" + words("s", 50) + "\n\n## Next\n\n" + words("n", 200)
    [c] = chunk(article("sections", short))
    assert "s0" in c.text and "n199" in c.text
    long = "## Long\n\n" + "\n\n".join(words(f"p{i}_", 100) for i in range(9))
    assert len(chunk(article("sections", long))) >= 2


def test_plain_packs_paragraphs_with_one_paragraph_overlap():
    paras = [words(f"p{i}_", 100) for i in range(6)]
    cs = chunk(article("plain", "\n\n".join(paras)))
    assert len(cs) == 3
    assert all(len(c.text.split()) <= 310 for c in cs)
    for left, right in zip(cs, cs[1:]):
        shared = [p for p in paras if p in left.text and p in right.text]
        assert len(shared) == 1


@pytest.mark.parametrize("kind", ["case", "sections", "plain"])
def test_chunkers_cover_every_word(kind):
    body = "## A\n\n" + "\n\n".join(words(f"p{i}_", 90) for i in range(6))
    a = article(kind, body)
    body_words = set(body.split()) - {"##"}
    for chunker in (chunk, chunk_fixed):
        covered = {w for c in chunker(a) for w in c.text.split()}
        assert body_words <= covered
    assert len(chunk_fixed(article("plain", words("w", 600)))) == 3


def test_bm25_ranks_matching_article_first_and_unknown_words_give_nothing():
    arts = [
        article("case", "Modernizing manufacturing through cloud migration of plant data.", slug="cloud",
                title="Cloud migration case", url="https://x.test/cloud"),
        article("case", "A hedge fund rebuilt its data infrastructure.", slug="fund",
                title="Hedge fund case", url="https://x.test/fund"),
        article("case", "Quantum annealing cut costs.", slug="quantum",
                title="Quantum case", url="https://x.test/quantum"),
    ]
    index = Index([c for a in arts for c in chunk(a)])
    hits = index.search("cloud migration manufacturing")
    assert hits[0].chunk.url == "https://x.test/cloud"
    assert hits[0].score > 0
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert index.search("zzzz qqqq") == []


def test_real_corpus_loads_and_chunks():
    arts = load_articles(Path(__file__).resolve().parent.parent / "corpus" / "blog")
    chunks = [c for a in arts for c in chunk(a)]
    assert len(arts) == 36
    assert 60 <= len(chunks) <= 120
    assert all(c.url.startswith("https://") for c in chunks)
