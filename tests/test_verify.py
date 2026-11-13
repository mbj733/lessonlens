"""B4 gate: the three verification gates, on hand-built positives and negatives.

Five cases must pass and five must fail. A verifier that only ever says SUPPORTED is worthless,
so the negatives matter more than the positives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lessonlens.ingest import Block, Document, Page
from lessonlens.verify import (
    SUPPORTED,
    UNGROUNDED,
    UNSUPPORTED,
    WRONG_PAGE,
    check_claim,
    check_scene,
    overlap,
    self_test,
)

ROOT = Path(__file__).resolve().parents[1]
PAGE_ONE = (
    "A comparison sort may only inspect keys through pairwise comparisons. "
    "Any comparison sort needs Ω(n log n) comparisons in the worst case."
)
PAGE_TWO = "Merge sort splits the array, sorts each half, then merges them."
PAGE_ZH = "高度为 h 的二叉树最多有 2^h − 1 个结点。"


def make_doc() -> Document:
    pages = [
        Page(index=1, title="Complexity", width=10, height=7.5, blocks=[Block("bullet", PAGE_ONE)]),
        Page(index=2, title="Merge sort", width=10, height=7.5, blocks=[Block("bullet", PAGE_TWO)]),
        Page(index=3, title="性质", width=10, height=7.5, blocks=[Block("bullet", PAGE_ZH)]),
    ]
    return Document(source="synthetic.pptx", kind="pptx", title="Synthetic", lang="en", pages=pages)


def claim(text: str, quote: str, page: int) -> dict:
    return {"text": text, "quote": quote, "page": page}


# ------------------------------------------------------------------ positives


def test_exact_quote_is_supported() -> None:
    doc = make_doc()
    result = check_claim("o01", 0, claim(PAGE_TWO, PAGE_TWO, 2), doc)
    assert result.verdict == SUPPORTED, result.reason
    assert result.similarity == pytest.approx(1.0)


def test_whitespace_and_linebreak_differences_are_supported() -> None:
    doc = make_doc()
    messy = "Merge sort splits the array,\n  sorts each half,   then merges them."
    result = check_claim("o01", 0, claim(messy, messy, 2), doc)
    assert result.verdict == SUPPORTED, result.reason


def test_chinese_quote_is_supported() -> None:
    doc = make_doc()
    result = check_claim("o01", 0, claim(PAGE_ZH, PAGE_ZH, 3), doc)
    assert result.verdict == SUPPORTED, result.reason
    assert result.similarity >= 0.9


def test_substring_of_page_is_supported() -> None:
    doc = make_doc()
    quote = "Any comparison sort needs Ω(n log n) comparisons in the worst case."
    result = check_claim("o01", 0, claim(quote, quote, 1), doc)
    assert result.verdict == SUPPORTED, result.reason


def test_claim_prefix_of_quote_is_supported() -> None:
    doc = make_doc()
    result = check_claim("o01", 0, claim("Merge sort splits the array", PAGE_TWO, 2), doc)
    assert result.verdict == SUPPORTED, result.reason
    # every token of the claim occurs in the quote, so containment is total
    assert result.similarity == pytest.approx(1.0)


# ------------------------------------------------------------------ negatives


def test_quote_from_another_page_is_wrong_page() -> None:
    doc = make_doc()
    result = check_claim("o01", 0, claim(PAGE_TWO, PAGE_TWO, 1), doc)
    assert result.verdict == WRONG_PAGE, result.reason
    assert result.quote_pages == [2]


def test_invented_quote_is_unsupported() -> None:
    doc = make_doc()
    result = check_claim("o01", 0, claim("Quick sort is always stable", "Quick sort is always stable", 1), doc)
    assert result.verdict == UNSUPPORTED, result.reason


def test_empty_quote_is_unsupported() -> None:
    doc = make_doc()
    result = check_claim("o01", 0, claim("anything", "   ", 1), doc)
    assert result.verdict == UNSUPPORTED
    assert "empty" in result.reason


def test_page_out_of_range_is_unsupported() -> None:
    doc = make_doc()
    result = check_claim("o01", 0, claim(PAGE_TWO, PAGE_TWO, 9), doc)
    assert result.verdict == UNSUPPORTED
    assert "range" in result.reason


def test_unrelated_claim_text_is_ungrounded() -> None:
    doc = make_doc()
    result = check_claim("o01", 0, claim("bananas and the weather", PAGE_TWO, 2), doc)
    assert result.verdict == UNGROUNDED, result.reason
    assert result.similarity < 0.5


# ------------------------------------------------------------------ helpers


def test_overlap_uses_words_for_latin_and_bigrams_for_cjk() -> None:
    assert overlap("merge sort", "merge sort splits the array") == pytest.approx(1.0)
    assert overlap("binary tree", "graphs are unrelated") == 0.0
    zh = overlap("二叉树", "高度为 h 的二叉树最多有 2^h − 1 个结点")
    assert zh >= 0.5


def test_scene_check_aggregates_verdicts() -> None:
    doc = make_doc()
    scene = {
        "objects": [
            {"id": "o01", "claims": [claim(PAGE_TWO, PAGE_TWO, 2)]},
            {"id": "o02", "claims": [claim(PAGE_TWO, PAGE_TWO, 1)]},
            {"id": "o03", "claims": [claim("bananas", PAGE_ONE, 1)]},
        ]
    }
    result = check_scene(scene, doc)
    assert result.verdicts() == {SUPPORTED: 1, WRONG_PAGE: 1, UNGROUNDED: 1}
    assert result.supported == 1
    assert result.objects_with_supported_claim == 1


# ------------------------------------------------------------------ self test


def test_self_test_detects_every_corruption() -> None:
    doc = make_doc()
    scene = {
        "deck": {"id": "synthetic", "pages": 3, "source": doc.source, "title": doc.title, "lang": "en"},
        "objects": [
            {"id": f"o0{i}", "page": 2, "claims": [claim(PAGE_TWO, PAGE_TWO, 2)]} for i in range(1, 4)
        ],
        "tasks": [],
    }
    report = self_test([(scene, doc)], rounds=3)
    assert report["total"]["trials"] == 9
    assert report["total"]["detected"] == 9
    for kind, item in report["corruptions"].items():
        assert item["rate"] == 1.0, kind


def test_self_test_is_deterministic() -> None:
    doc = make_doc()
    scene = {
        "deck": {"id": "synthetic", "pages": 3, "source": doc.source, "title": doc.title, "lang": "en"},
        "objects": [{"id": "o01", "page": 2, "claims": [claim(PAGE_TWO, PAGE_TWO, 2)]}],
        "tasks": [],
    }
    first = self_test([(scene, doc)], rounds=2)
    second = self_test([(scene, doc)], rounds=2)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
