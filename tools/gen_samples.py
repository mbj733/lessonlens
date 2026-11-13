"""Generate the evaluation corpus as .pptx (all decks) and .pdf (a subset).

The decks come from :mod:`sample_corpus`, so the repository contains no third-party slide
content. Output layout::

    eval/slides/<deck-id>.pptx        all ten decks
    eval/slides/<deck-id>.pdf         the four decks listed in PDF_DECK_IDS
    eval/expected/manifest.json       page titles + sha256 of every generated file

Run from the repository root::

    python tools/gen_samples.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sample_corpus import DECKS, PDF_DECK_IDS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SLIDE_DIR = ROOT / "eval" / "slides"
EXPECTED_DIR = ROOT / "eval" / "expected"

FONT_EN = "Segoe UI"
FONT_ZH = "Microsoft YaHei"
SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _set_run(run, size: int, font: str, bold: bool = False) -> None:
    run.font.size = Pt(size)
    run.font.name = font
    run.font.bold = bold


def _set_bullet(paragraph, char: str = "\u2022") -> None:
    """python-pptx has no bullet API, so write the two pPr children in schema order."""
    p_pr = paragraph._p.get_or_add_pPr()
    if p_pr.find(qn("a:buChar")) is not None:
        return
    bullet_font = p_pr.makeelement(qn("a:buFont"), {"typeface": "Arial"})
    p_pr.insert_element_before(bullet_font, "a:buChar", "a:tabLst", "a:defRPr", "a:extLst")
    bullet = p_pr.makeelement(qn("a:buChar"), {"char": char})
    p_pr.insert_element_before(bullet, "a:tabLst", "a:defRPr", "a:extLst")


def _pptx_deck(deck: dict, out: Path) -> None:
    font = FONT_ZH if deck["lang"] == "zh" else FONT_EN
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    prs.core_properties.title = deck["title"]
    prs.core_properties.subject = deck["subtitle"]
    prs.core_properties.author = "LessonLens corpus generator"
    prs.core_properties.language = "zh-CN" if deck["lang"] == "zh" else "en-US"

    for spec in deck["slides"]:
        slide = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only
        title = slide.shapes.title
        title.left, title.top = Inches(0.6), Inches(0.45)
        title.width, title.height = Inches(12.1), Inches(1.05)
        title.text = spec["title"]
        for para in title.text_frame.paragraphs:
            para.alignment = PP_ALIGN.LEFT
            for run in para.runs:
                _set_run(run, 30, font, bold=True)

        if "table" in spec:
            table_spec = spec["table"]
            rows = [table_spec["header"], *table_spec["rows"]]
            shape = slide.shapes.add_table(
                len(rows),
                len(rows[0]),
                Inches(0.9),
                Inches(1.9),
                Inches(11.5),
                Inches(0.55) * len(rows),
            )
            table = shape.table
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    cell = table.cell(r, c)
                    cell.text = value
                    for para in cell.text_frame.paragraphs:
                        for run in para.runs:
                            _set_run(run, 14, font, bold=(r == 0))
        else:
            box = slide.shapes.add_textbox(
                Inches(0.85), Inches(1.85), Inches(11.6), Inches(5.0)
            )
            frame = box.text_frame
            frame.word_wrap = True
            for i, bullet in enumerate(spec["bullets"]):
                para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
                para.text = bullet
                para.space_after = Pt(10)
                _set_bullet(para)
                for run in para.runs:
                    _set_run(run, 18, font)

    prs.save(str(out))


def _register_fonts() -> dict:
    """Register body / bullet / math TrueType fonts and report their glyph coverage.

    SimHei renders Chinese but has no glyph for U+2212, U+2202, U+2207, U+0177 or the floor
    brackets; Cambria covers exactly those. Mixing them per character keeps the PDF lossless,
    which matters because every quote in the corpus has to survive extraction verbatim.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    def pick(name: str, candidates: list[Path]) -> str:
        if name in pdfmetrics.getRegisteredFontNames():
            return name
        for candidate in candidates:
            if candidate.exists():
                pdfmetrics.registerFont(TTFont(name, str(candidate), subfontIndex=0))
                return name
        return ""

    body = pick(
        "corpus-cjk",
        [
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/simsun.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        ],
    )
    if not body:
        raise SystemExit("no CJK TrueType font found; cannot render the PDF corpus")
    math_font = pick(
        "corpus-math",
        [
            Path("C:/Windows/Fonts/cambria.ttc"),
            Path("C:/Windows/Fonts/seguisym.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ],
    )
    bullet = pick(
        "corpus-latin",
        [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")],
    ) or "Helvetica"

    def coverage(name: str) -> set[int]:
        if name not in pdfmetrics.getRegisteredFontNames():
            return set()
        return set(pdfmetrics.getFont(name).face.charToGlyph)

    return {
        "body": body,
        "math": math_font,
        "bullet": bullet,
        "body_chars": coverage(body),
        "math_chars": coverage(math_font),
    }


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _markup(text: str, fonts: dict) -> str:
    """Wrap the characters the body font lacks in an inline math-font run."""
    pieces: list[str] = []
    buffer: list[str] = []
    in_math = False

    def flush() -> None:
        if not buffer:
            return
        chunk = _escape("".join(buffer))
        pieces.append(f'<font name="{fonts["math"]}">{chunk}</font>' if in_math else chunk)
        buffer.clear()

    for char in text:
        codepoint = ord(char)
        use_math = (
            fonts["math"]
            and codepoint not in fonts["body_chars"]
            and codepoint in fonts["math_chars"]
        )
        if use_math != in_math:
            flush()
            in_math = bool(use_math)
        buffer.append(char)
    flush()
    return "".join(pieces)


def _deck_chars(deck: dict) -> set[str]:
    chars: set[str] = set()
    for spec in deck["slides"]:
        chars.update(spec["title"])
        for bullet in spec.get("bullets", []):
            chars.update(bullet)
        table = spec.get("table")
        if table:
            for cell in table["header"]:
                chars.update(cell)
            for row in table["rows"]:
                for cell in row:
                    chars.update(cell)
    return chars


def _assert_glyph_coverage(deck: dict, fonts: dict) -> None:
    missing = sorted(
        char
        for char in _deck_chars(deck)
        if not char.isspace()
        and ord(char) not in fonts["body_chars"]
        and ord(char) not in fonts["math_chars"]
    )
    if missing:
        shown = "".join(f"{char}(U+{ord(char):04X}) " for char in missing)
        raise SystemExit(f"{deck['id']}: no glyph for {shown}— fix the text or add a font")


def _pdf_deck(deck: dict, out: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    fonts = _register_fonts()
    _assert_glyph_coverage(deck, fonts)

    title_style = ParagraphStyle(
        "t", fontName=fonts["body"], fontSize=21, leading=27, spaceAfter=14
    )
    body_style = ParagraphStyle(
        "b",
        fontName=fonts["body"],
        fontSize=12.5,
        leading=18,
        spaceAfter=9,
        leftIndent=16,
        bulletIndent=2,
        bulletFontName=fonts["bullet"],
        bulletFontSize=12.5,
    )
    cell_style = ParagraphStyle("c", fontName=fonts["body"], fontSize=10.5, leading=14)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=deck["title"],
        subject=deck["subtitle"],
        author="LessonLens corpus generator",
        creator="tools/gen_samples.py",
    )

    story: list = []
    for index, spec in enumerate(deck["slides"]):
        if index:
            story.append(PageBreak())
        story.append(Paragraph(_markup(spec["title"], fonts), title_style))
        if "table" in spec:
            table_spec = spec["table"]
            data = [
                [Paragraph(_markup(cell, fonts), cell_style) for cell in table_spec["header"]]
            ]
            for row in table_spec["rows"]:
                data.append([Paragraph(_markup(cell, fonts), cell_style) for cell in row])
            col_width = (A4[0] - 36 * mm) / len(table_spec["header"])
            table = Table(data, colWidths=[col_width] * len(table_spec["header"]))
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, (0.4, 0.4, 0.4)),
                        ("BACKGROUND", (0, 0), (-1, 0), (0.92, 0.93, 0.95)),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(Spacer(1, 4))
            story.append(table)
        else:
            for bullet in spec["bullets"]:
                story.append(
                    Paragraph(_markup(bullet, fonts), body_style, bulletText="\u2022")
                )
    doc.build(story)


def main() -> int:
    SLIDE_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {"generator": "tools/gen_samples.py", "decks": []}
    for deck in DECKS:
        pptx_path = SLIDE_DIR / f"{deck['id']}.pptx"
        _pptx_deck(deck, pptx_path)
        files = [{"path": pptx_path.name, "sha256": _sha256(pptx_path)}]
        print(f"pptx  {pptx_path.name}  {pptx_path.stat().st_size:>7,} B")

        if deck["id"] in PDF_DECK_IDS:
            pdf_path = SLIDE_DIR / f"{deck['id']}.pdf"
            _pdf_deck(deck, pdf_path)
            files.append({"path": pdf_path.name, "sha256": _sha256(pdf_path)})
            print(f"pdf   {pdf_path.name}  {pdf_path.stat().st_size:>7,} B")

        manifest["decks"].append(
            {
                "id": deck["id"],
                "lang": deck["lang"],
                "title": deck["title"],
                "subtitle": deck["subtitle"],
                "page_titles": [spec["title"] for spec in deck["slides"]],
                "files": files,
            }
        )

    manifest_path = EXPECTED_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    total = len(DECKS)
    pdfs = len(PDF_DECK_IDS)
    print(f"\n{total} decks, {total + pdfs} files, manifest -> {manifest_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
