"""Ingest: slide deck (PPTX) or PDF -> a page/block structure with bounding boxes.

The output of this stage is deliberately dumb: it keeps text *and* geometry, because every
later claim must be traceable to a page and (when the format allows) a box on the page.

Block types
-----------
``title``   the slide title placeholder, or the largest font run on a PDF page
``bullet``  a bulleted paragraph
``body``    a paragraph that is not bulleted
``table``   a table, flattened row-major into ``text`` and kept structured in ``rows``
``image``   a picture; carries geometry only, no text

No OCR: a scanned PDF page yields zero blocks and gets ``flags.text_layer = False``.
"""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.oxml.ns import qn

EMU_PER_INCH = 914400
SCHEMA = "lessonlens/extract@1"

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# U+0000 is accepted because some PDF writers map an unmapped bullet glyph to NUL.
_BULLET = re.compile(r"^\s*[\x00\u2022\u00b7\u25cf\u25aa\-\u2013\u2014*]\s*")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SPACE = re.compile(r"\s+")

TITLE_PLACEHOLDERS = {
    PP_PLACEHOLDER.TITLE,
    PP_PLACEHOLDER.CENTER_TITLE,
    PP_PLACEHOLDER.VERTICAL_TITLE,
}


def normalize(text: str) -> str:
    """Collapse whitespace and drop control characters, so quote matching is stable."""
    return _SPACE.sub(" ", _CONTROL.sub("", text)).strip()


def guess_lang(text: str) -> str:
    cjk = len(_CJK.findall(text))
    return "zh" if cjk >= max(12, len(text) * 0.15) else "en"


@dataclass
class Block:
    type: str
    text: str
    bbox: list[float] | None = None
    level: int = 0
    rows: list[list[str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type, "text": self.text, "level": self.level}
        if self.bbox is not None:
            data["bbox"] = [round(v, 3) for v in self.bbox]
        if self.rows is not None:
            data["rows"] = self.rows
        return data


@dataclass
class Page:
    index: int
    title: str
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks if b.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "size": [round(self.width, 3), round(self.height, 3)],
            "blocks": [b.to_dict() for b in self.blocks],
            "flags": self.flags,
        }


@dataclass
class Document:
    source: str
    kind: str
    title: str
    lang: str
    pages: list[Page] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    def stats(self) -> dict[str, Any]:
        types: dict[str, int] = {}
        for page in self.pages:
            for block in page.blocks:
                types[block.type] = types.get(block.type, 0) + 1
        return {
            "pages": len(self.pages),
            "blocks": sum(types.values()),
            "chars": len(self.text),
            "types": dict(sorted(types.items())),
            "empty_pages": sum(1 for p in self.pages if not p.text.strip()),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "source": self.source,
            "kind": self.kind,
            "title": self.title,
            "lang": self.lang,
            "pages": [p.to_dict() for p in self.pages],
            "stats": self.stats(),
            **({"meta": self.meta} if self.meta else {}),
        }


# --------------------------------------------------------------------------- pptx


def _walk(shapes) -> Iterator[Any]:
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(shape.shapes)
        else:
            yield shape


def _bbox(shape) -> list[float] | None:
    try:
        left, top = shape.left, shape.top
        width, height = shape.width, shape.height
    except (AttributeError, TypeError):
        return None
    if None in (left, top, width, height):
        return None
    return [left / EMU_PER_INCH, top / EMU_PER_INCH, width / EMU_PER_INCH, height / EMU_PER_INCH]


def _has_bullet(paragraph) -> bool:
    """True when the paragraph carries an explicit bullet glyph or auto-numbering."""
    p_pr = paragraph._p.pPr
    if p_pr is None:
        return False
    return p_pr.find(qn("a:buChar")) is not None or p_pr.find(qn("a:buAutoNum")) is not None


def _pptx_page(slide, index: int, width: float, height: float) -> Page:
    blocks: list[Block] = []
    title = ""
    shapes = sorted(
        _walk(slide.shapes),
        key=lambda s: ((s.top or 0), (s.left or 0)),
    )
    for shape in shapes:
        box = _bbox(shape)
        is_title = bool(
            getattr(shape, "is_placeholder", False)
            and shape.placeholder_format.type in TITLE_PLACEHOLDERS
        )
        if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
            paragraphs = [p.text.strip() for p in shape.text_frame.paragraphs]
            if is_title:
                text = normalize("\n".join(p for p in paragraphs if p))
                if text:
                    title = text
                    blocks.append(Block("title", text, box))
                continue
            for paragraph in shape.text_frame.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue
                kind = "bullet" if (paragraph.level > 0 or _has_bullet(paragraph)) else "body"
                blocks.append(Block(kind, text, box, level=paragraph.level))
        elif getattr(shape, "has_table", False) and shape.has_table:
            rows = [[cell.text.strip() for cell in row.cells] for row in shape.table.rows]
            text = "\n".join(" | ".join(row) for row in rows)
            if text.strip():
                blocks.append(Block("table", text, box, rows=rows))
        elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            blocks.append(Block("image", "", box))

    if not title:
        title = next((b.text for b in blocks if b.text), "")
    flags = {"text_layer": bool(title or any(b.text for b in blocks))}
    return Page(index=index, title=title, width=width, height=height, blocks=blocks, flags=flags)


def _pptx(path: Path, source: str) -> Document:
    prs = Presentation(str(path))
    width = prs.slide_width / EMU_PER_INCH
    height = prs.slide_height / EMU_PER_INCH
    pages = [
        _pptx_page(slide, index, width, height)
        for index, slide in enumerate(prs.slides, start=1)
    ]
    props = prs.core_properties
    title = (props.title or "").strip() or (pages[0].title if pages else path.stem)
    meta = {
        "author": props.author or "",
        "subject": props.subject or "",
        "slide_count": len(pages),
    }
    doc = Document(source=source, kind="pptx", title=title, lang=guess_lang(doc_text(pages)), pages=pages, meta=meta)
    return doc


# --------------------------------------------------------------------------- pdf


def _line_size(chars: list[dict]) -> float:
    sizes = [round(float(char["size"]), 1) for char in chars if char.get("size")]
    return statistics.median(sizes) if sizes else 0.0


def _needs_space(left: str, right: str) -> bool:
    """True unless the two fragments are CJK, where a space would be wrong."""
    if not left or not right:
        return False
    return not (_CJK.match(left[-1]) or _CJK.match(right[0]))


def _pdf_page(page, index: int) -> Page:
    width, height = float(page.width), float(page.height)
    lines = page.extract_text_lines(return_chars=True) or []
    blocks: list[Block] = []
    sizes: list[float] = []
    previous_bottom = None
    previous_height = 0.0

    for line in lines:
        raw = (line.get("text") or "").strip()
        if not raw:
            continue
        chars = line.get("chars") or []
        size = _line_size(chars) or round(float(line["bottom"]) - float(line["top"]), 1)
        height_line = float(line["bottom"]) - float(line["top"])
        box = [
            float(line["x0"]),
            float(line["top"]),
            float(line["x1"]) - float(line["x0"]),
            height_line,
        ]
        gap = (float(line["top"]) - previous_bottom) if previous_bottom is not None else 1e9
        bullet = bool(_BULLET.match(raw))
        text = _BULLET.sub("", raw).strip()

        same_para = (
            blocks
            and not bullet
            and abs(size - sizes[-1]) <= 0.6
            and gap <= 0.55 * max(height_line, previous_height, 1.0)
        )
        if same_para:
            glue = " " if _needs_space(blocks[-1].text, text) else ""
            blocks[-1].text = normalize(blocks[-1].text + glue + text)
            pref = blocks[-1].bbox or box
            blocks[-1].bbox = [
                min(pref[0], box[0]),
                min(pref[1], box[1]),
                max(pref[0] + pref[2], box[0] + box[2]) - min(pref[0], box[0]),
                max(pref[1] + pref[3], box[1] + box[3]) - min(pref[1], box[1]),
            ]
        else:
            blocks.append(Block("bullet" if bullet else "body", text, box))
            sizes.append(size)
        previous_bottom = float(line["bottom"])
        previous_height = height_line

    if not blocks:
        return Page(
            index=index,
            title="",
            width=width,
            height=height,
            blocks=[],
            flags={"text_layer": False},
        )

    # The title is the block drawn in the largest type on the page.
    max_size = max(sizes)
    title_blocks = [b for b, s in zip(blocks, sizes, strict=True) if s >= max_size - 0.3]
    title = normalize(title_blocks[0].text) if title_blocks else ""
    for block, size in zip(blocks, sizes, strict=True):
        if size >= max_size - 0.3 and normalize(block.text) == title and block.type != "title":
            block.type = "title"
            break
    return Page(
        index=index,
        title=title,
        width=width,
        height=height,
        blocks=blocks,
        flags={"text_layer": True},
    )


def _pdf(path: Path, source: str) -> Document:
    import pdfplumber

    pages: list[Page] = []
    metadata: dict[str, Any] = {}
    with pdfplumber.open(str(path)) as pdf:
        metadata = dict(pdf.metadata or {})
        for index, page in enumerate(pdf.pages, start=1):
            pages.append(_pdf_page(page, index))
    title = str(metadata.get("Title") or "").strip() or (pages[0].title if pages else path.stem)
    meta = {
        "producer": str(metadata.get("Producer") or ""),
        "creator": str(metadata.get("Creator") or ""),
        "page_count": len(pages),
    }
    return Document(source=source, kind="pdf", title=title, lang=guess_lang(doc_text(pages)), pages=pages, meta=meta)


def doc_text(pages: list[Page]) -> str:
    return "\n".join(p.text for p in pages)


# --------------------------------------------------------------------------- api


def extract_document(path: str | Path, *, root: str | Path | None = None) -> Document:
    """Extract one deck. ``root`` only controls how ``source`` is rendered in the JSON."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if root is not None:
        try:
            source = path.resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            source = path.as_posix()
    else:
        source = path.as_posix()

    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return _pptx(path, source)
    if suffix == ".pdf":
        return _pdf(path, source)
    raise ValueError(f"unsupported input: {path.name} (expected .pptx or .pdf)")


def extract_paths(paths, *, root: str | Path | None = None) -> list[Document]:
    """Expand directories into decks, sorted by file name for deterministic output."""
    files: list[Path] = []
    for item in paths:
        item = Path(item)
        if item.is_dir():
            files.extend(sorted(p for p in item.iterdir() if p.suffix.lower() in {".pptx", ".pdf"}))
        else:
            files.append(item)
    return [extract_document(path, root=root) for path in files]


def write_extract(doc: Document, out_dir: str | Path) -> Path:
    """One JSON per input file; the full file name keeps .pptx and .pdf apart."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{Path(doc.source).name}.json"
    target.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2) + "\n", "utf-8")
    return target
