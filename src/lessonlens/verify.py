"""Verification gates: does every claim actually come from the slide it names?

Three gates per claim, cheapest first:

1. **quote gate** — the quote, after whitespace normalisation, occurs on the page it claims.
2. **page gate** — if it does not occur there, where does it occur? A quote found on another page is
   a factual error, not a typo, and gets its own verdict.
3. **grounding gate** — the claim sentence must be covered by the quote (lexical overlap). This is a
   *lexical* check, not a semantic one: no embedding model is required or installed, and the report
   says so instead of pretending otherwise.

``self_test`` deliberately corrupts scenes to prove the gates can fail — a verifier that only ever
returns SUPPORTED proves nothing.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from .ingest import Document, normalize

SUPPORTED = "SUPPORTED"
WRONG_PAGE = "WRONG_PAGE"
UNSUPPORTED = "UNSUPPORTED"
UNGROUNDED = "UNGROUNDED"

MIN_OVERLAP = 0.5

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    """Word tokens plus CJK character bigrams — a mixed script keeps both signals."""
    text = normalize(text).casefold()
    tokens = set(_WORD.findall(text))
    chars = [char for char in text if _CJK.match(char)]
    tokens.update(first + second for first, second in zip(chars, chars[1:], strict=False))
    if len(chars) == 1:
        tokens.add(chars[0])
    return tokens


def overlap(text: str, quote: str) -> float:
    """Fraction of the claim's tokens that the quote also contains."""
    claim_tokens = _tokens(text)
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & _tokens(quote)) / len(claim_tokens)


@dataclass
class ClaimCheck:
    object_id: str
    claim_index: int
    page: int
    quote: str
    verdict: str
    quote_pages: list[int] = field(default_factory=list)
    similarity: float = 0.0
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.verdict == SUPPORTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "claim_index": self.claim_index,
            "page": self.page,
            "verdict": self.verdict,
            "quote_pages": self.quote_pages,
            "similarity": round(self.similarity, 3),
            "reason": self.reason,
        }


@dataclass
class SceneCheck:
    source: str
    claims: list[ClaimCheck] = field(default_factory=list)
    schema_ok: bool = True
    schema_errors: list[str] = field(default_factory=list)
    objects: int = 0
    tasks: int = 0

    def verdicts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for claim in self.claims:
            counts[claim.verdict] = counts.get(claim.verdict, 0) + 1
        return dict(sorted(counts.items()))

    @property
    def supported(self) -> int:
        return sum(1 for claim in self.claims if claim.ok)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "verdicts": self.verdicts(),
            "objects": self.objects,
            "claims": len(self.claims),
            "objects_with_supported_claim": self.objects_with_supported_claim,
            "tasks": self.tasks,
            "schema_ok": self.schema_ok,
            "schema_errors": self.schema_errors,
            "claims_detail": [claim.to_dict() for claim in self.claims],
        }

    @property
    def objects_with_supported_claim(self) -> int:
        ids = {claim.object_id for claim in self.claims if claim.ok}
        return len(ids)


def check_claim(
    object_id: str,
    claim_index: int,
    claim: dict[str, Any],
    doc: Document,
    *,
    min_overlap: float = MIN_OVERLAP,
) -> ClaimCheck:
    page = int(claim.get("page", 0))
    quote = normalize(claim.get("quote", ""))
    text = claim.get("text", "")
    pages = [normalize(page_obj.text) for page_obj in doc.pages]

    if not quote:
        return ClaimCheck(object_id, claim_index, page, quote, UNSUPPORTED, reason="empty quote")
    if not 1 <= page <= len(doc.pages):
        return ClaimCheck(object_id, claim_index, page, quote, UNSUPPORTED, reason="page out of range")

    quote_pages = [index for index, page_text in enumerate(pages, start=1) if quote in page_text]
    if page not in quote_pages:
        if quote_pages:
            return ClaimCheck(
                object_id,
                claim_index,
                page,
                quote,
                WRONG_PAGE,
                quote_pages,
                reason=f"quote occurs on page(s) {quote_pages}, not {page}",
            )
        return ClaimCheck(
            object_id,
            claim_index,
            page,
            quote,
            UNSUPPORTED,
            quote_pages,
            reason="quote does not occur anywhere in the deck",
        )

    similarity = overlap(text, quote)
    if similarity < min_overlap:
        return ClaimCheck(
            object_id,
            claim_index,
            page,
            quote,
            UNGROUNDED,
            quote_pages,
            similarity,
            reason=f"claim text only {similarity:.0%} covered by its quote",
        )
    return ClaimCheck(object_id, claim_index, page, quote, SUPPORTED, quote_pages, similarity)


def check_scene(scene: dict[str, Any], doc: Document, *, min_overlap: float = MIN_OVERLAP) -> SceneCheck:
    result = SceneCheck(
        source=doc.source,
        objects=len(scene.get("objects", [])),
        tasks=len(scene.get("tasks", [])),
    )
    for obj in scene.get("objects", []):
        for index, claim in enumerate(obj.get("claims", [])):
            result.claims.append(
                check_claim(obj["id"], index, claim, doc, min_overlap=min_overlap)
            )
    return result


# --------------------------------------------------------------------------- self test


CORRUPTIONS = ("quote_scrambled", "page_shifted", "claim_replaced")


def _corrupt(scene: dict[str, Any], kind: str, rng: random.Random, pages: int) -> dict[str, Any]:
    mutated = {
        "objects": [dict(obj, claims=[dict(claim) for claim in obj["claims"]]) for obj in scene["objects"]],
        "tasks": scene.get("tasks", []),
        "deck": scene["deck"],
    }
    target = rng.choice(mutated["objects"])
    claim = target["claims"][0]
    if kind == "quote_scrambled":
        words = claim["quote"].split()
        if len(words) > 3:
            words[len(words) // 2] = "zzzq"
            claim["quote"] = " ".join(words)
        else:
            claim["quote"] = claim["quote"][: len(claim["quote"]) // 2] + "zzzq"
    elif kind == "page_shifted":
        claim["page"] = claim["page"] % pages + 1
        target["page"] = claim["page"]
    elif kind == "claim_replaced":
        claim["text"] = "unrelated statement about bananas and the weather"
    return mutated


def self_test(
    pairs: list[tuple[dict[str, Any], Document]],
    *,
    rounds: int = 3,
    seed: int = 20261113,
) -> dict[str, Any]:
    """Corrupt known-good scenes; every corruption must be detected."""
    rng = random.Random(seed)
    report: dict[str, Any] = {"rounds": rounds, "corruptions": {}}
    for kind in CORRUPTIONS:
        trials = 0
        detected = 0
        for scene, doc in pairs:
            for _ in range(rounds):
                mutated = _corrupt(scene, kind, rng, len(doc.pages))
                check = check_scene(mutated, doc)
                trials += 1
                if any(not claim.ok for claim in check.claims):
                    detected += 1
        report["corruptions"][kind] = {
            "trials": trials,
            "detected": detected,
            "rate": detected / trials if trials else 0.0,
        }
    total = sum(item["trials"] for item in report["corruptions"].values())
    hits = sum(item["detected"] for item in report["corruptions"].values())
    report["total"] = {"trials": total, "detected": hits, "rate": hits / total if total else 0.0}
    return report
