"""B1 gate: every generated deck ingests into ten titled pages with quotable blocks."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from lessonlens.ingest import (
    Document,
    extract_document,
    extract_paths,
    normalize,
    write_extract,
)

ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "eval" / "slides"
MANIFEST_PATH = ROOT / "eval" / "expected" / "manifest.json"


def _load_corpus():
    spec = importlib.util.spec_from_file_location(
        "lessonlens_sample_corpus", ROOT / "tools" / "sample_corpus.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


CORPUS = _load_corpus()
MANIFEST = json.loads(MANIFEST_PATH.read_text("utf-8"))
DECK_BY_ID = {deck["id"]: deck for deck in CORPUS.DECKS}


@pytest.fixture(scope="session")
def corpus_files() -> list[Path]:
    files = sorted(p for p in SLIDES.iterdir() if p.suffix.lower() in {".pptx", ".pdf"})
    assert files, "corpus is missing; run `python tools/gen_samples.py`"
    return files


@pytest.fixture(scope="session")
def docs(corpus_files: list[Path]) -> dict[str, Document]:
    return {p.name: extract_document(p, root=ROOT) for p in corpus_files}


def _deck_id_from_name(name: str) -> str:
    return name.rsplit(".", 1)[0]


def test_manifest_covers_corpus() -> None:
    assert len(MANIFEST["decks"]) == 10
    declared = {f["path"]: f["sha256"] for deck in MANIFEST["decks"] for f in deck["files"]}
    on_disk = {p.name for p in SLIDES.iterdir() if p.suffix.lower() in {".pptx", ".pdf"}}
    assert set(declared) == on_disk, "regenerate the manifest after changing eval/slides"


def test_every_deck_has_ten_titled_pages(docs: dict[str, Document]) -> None:
    for name, doc in docs.items():
        assert len(doc.pages) == 10, name
        expected = DECK_BY_ID[_deck_id_from_name(name)]["slides"]
        assert [page.title for page in doc.pages] == [
            slide["title"] for slide in expected
        ], name
        for page in doc.pages:
            assert page.title.strip(), name
            assert page.text.strip(), f"{name} page {page.index} has no text"


def test_document_title_comes_from_metadata(docs: dict[str, Document]) -> None:
    for name, doc in docs.items():
        deck = DECK_BY_ID[_deck_id_from_name(name)]
        assert doc.title == deck["title"], name
        assert doc.lang == deck["lang"], name


def test_blocks_are_well_formed(docs: dict[str, Document]) -> None:
    for name, doc in docs.items():
        for page in doc.pages:
            for block in page.blocks:
                assert block.type in {"title", "bullet", "body", "table", "image"}, name
                if block.type == "image":
                    assert block.text == ""
                else:
                    assert block.text.strip(), f"{name} page {page.index} empty block"
                if block.bbox is not None:
                    x, y, w, h = block.bbox
                    assert w > 0 and h > 0, f"{name} page {page.index} degenerate bbox"
                    assert x >= -0.01 and y >= -0.01, f"{name} page {page.index} negative origin"
                    assert x + w <= page.width + 0.05, f"{name} page {page.index} bbox overflows"
                    assert y + h <= page.height + 0.05, f"{name} page {page.index} bbox overflows"


def test_block_types_present(docs: dict[str, Document]) -> None:
    types = {name: set(doc.stats()["types"]) for name, doc in docs.items()}
    for name, seen in types.items():
        assert "title" in seen, name
        assert "bullet" in seen, f"{name} lost its bullets"
    assert "table" in types["en-01-sorting.pptx"]
    assert "table" in types["en-01-sorting.pdf"] or "body" in types["en-01-sorting.pdf"]


def test_table_rows_are_structured(docs: dict[str, Document]) -> None:
    deck = docs["en-01-sorting.pptx"]
    tables = [b for page in deck.pages for b in page.blocks if b.type == "table"]
    assert len(tables) == 1
    rows = tables[0].rows or []
    assert rows[0][0] == "Algorithm"
    assert len(rows) == 5  # header + four algorithms
    assert all(len(row) == 5 for row in rows)


def test_every_corpus_bullet_survives_ingest(docs: dict[str, Document]) -> None:
    """Grounding needs verbatim quotes, so no bullet may be mangled or dropped."""
    for name, doc in docs.items():
        deck = DECK_BY_ID[_deck_id_from_name(name)]
        for page, slide in zip(doc.pages, deck["slides"], strict=True):
            page_text = normalize(page.text)
            for bullet in slide.get("bullets", []):
                assert normalize(bullet) in page_text, f"{name} page {page.index}: {bullet!r}"


def test_ppt_bbox_matches_slide_size(docs: dict[str, Document]) -> None:
    deck = docs["zh-06-binary-tree.pptx"]
    assert deck.pages[0].width == pytest.approx(13.333, abs=0.01)
    assert deck.pages[0].height == pytest.approx(7.5, abs=0.01)
    assert deck.pages[0].blocks[0].type == "title"


def test_extract_json_roundtrip(tmp_path: Path, docs: dict[str, Document]) -> None:
    doc = docs["en-02-bst.pptx"]
    written = write_extract(doc, tmp_path)
    assert written.name == "en-02-bst.pptx.json"
    payload = json.loads(written.read_text("utf-8"))
    assert payload["schema"] == "lessonlens/extract@1"
    assert payload["kind"] == "pptx"
    assert payload["stats"]["pages"] == 10
    assert len(payload["pages"][0]["blocks"]) >= 2
    assert written.read_text("utf-8").count("\n") > 50


def test_extract_paths_keeps_input_order(tmp_path: Path) -> None:
    docs = extract_paths([SLIDES], root=ROOT)
    assert len(docs) == 14
    names = [Path(d.source).name for d in docs]
    assert names == sorted(names)
    assert names[0] == "en-01-sorting.pdf"


def test_unsupported_input_raises(tmp_path: Path) -> None:
    bogus = tmp_path / "notes.txt"
    bogus.write_text("hello", "utf-8")
    with pytest.raises(ValueError):
        extract_document(bogus)
    with pytest.raises(FileNotFoundError):
        extract_document(tmp_path / "missing.pptx")


def test_cli_ingest_smoke(tmp_path: Path) -> None:
    from lessonlens.cli import main

    out = tmp_path / "extract"
    code = main(["ingest", str(SLIDES / "en-03-hashing.pptx"), "--out", str(out), "--root", str(ROOT)])
    assert code == 0
    assert (out / "en-03-hashing.pptx.json").exists()


def test_no_ocr_claim_for_text_layers(docs: dict[str, Document]) -> None:
    for name, doc in docs.items():
        for page in doc.pages:
            assert page.flags.get("text_layer") is True, name


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
