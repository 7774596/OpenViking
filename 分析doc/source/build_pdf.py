#!/usr/bin/env python3
"""Build the source-grounded OpenViking design report (Python + ReportLab).

Usage: python3 source/build_pdf.py [--output PATH]
Fonts: OV_CJK_FONT and OV_LATIN_FONT may override the default system fonts.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Flowable, Frame, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "source/report.json").read_text(encoding="utf-8"))
for source in DATA["sources"].values():
    source["url"] = DATA["repository"] + "/blob/" + DATA["commit"] + "/" + source["path"]
INK = colors.HexColor("#172B41")
MUTED = colors.HexColor("#526479")
TEAL = colors.HexColor("#087E83")
LIGHT = colors.HexColor("#ECF5F5")
LINE = colors.HexColor("#DCE5EC")
GOLD = colors.HexColor("#B46A1F")
PAGE_W, PAGE_H = A4
MARGIN = 48
WIDTH = PAGE_W - 2 * MARGIN


def setup_fonts():
    cjk = os.environ.get("OV_CJK_FONT", "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf")
    latin = os.environ.get("OV_LATIN_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    for name, path in (("CJK", cjk), ("Latin", latin)):
        if not Path(path).is_file():
            raise SystemExit(f"Missing font: {path}; set OV_CJK_FONT / OV_LATIN_FONT")
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily("CJK", normal="CJK", bold="CJK", italic="CJK", boldItalic="CJK")


STYLES = {
    "body": ParagraphStyle("body", fontName="CJK", fontSize=10.4, leading=17.4,
                           textColor=INK, wordWrap="CJK", spaceAfter=9),
    "lead": ParagraphStyle("lead", fontName="CJK", fontSize=12, leading=20,
                           textColor=INK, wordWrap="CJK", spaceAfter=14),
    "h": ParagraphStyle("h", fontName="CJK", fontSize=12.2, leading=19,
                        textColor=TEAL, spaceBefore=7, spaceAfter=7, wordWrap="CJK"),
    "small": ParagraphStyle("small", fontName="CJK", fontSize=8.5, leading=13,
                            textColor=MUTED, wordWrap="CJK", spaceAfter=6),
    "cell": ParagraphStyle("cell", fontName="CJK", fontSize=9.2, leading=14.2,
                           textColor=INK, wordWrap="CJK"),
    "th": ParagraphStyle("th", fontName="CJK", fontSize=9.2, leading=14,
                         textColor=colors.white, wordWrap="CJK"),
    "box": ParagraphStyle("box", fontName="CJK", fontSize=10.1, leading=15.2,
                          textColor=INK, alignment=TA_CENTER, wordWrap="CJK"),
}


def markup(text):
    def font_for(char):
        if ord(char) in pdfmetrics.getFont("Latin").face.charToGlyph and ord(char) < 0x3000:
            return "Latin"
        if ord(char) in pdfmetrics.getFont("CJK").face.charToGlyph:
            return "CJK"
        if ord(char) in pdfmetrics.getFont("Latin").face.charToGlyph:
            return "Latin"
        raise ValueError(f"No glyph for {char!r} (U+{ord(char):04X})")

    def fontify(value):
        lines = []
        for line in value.split("\n"):
            lines.append("".join(
                f'<font name="{font}">{html.escape("".join(chars))}</font>'
                for font, chars in groupby(line, font_for)
            ))
        return "<br/>".join(lines)

    chunks = []
    for chunk in re.split(r"(\[S\d+\])", text):
        if re.fullmatch(r"\[S\d+\]", chunk):
            sid = chunk[1:-1]
            chunks.append('<link href="' + DATA["sources"][sid]["url"] +
                          '" color="#087E83">' + fontify(chunk) + '</link>')
        else:
            chunks.append(fontify(chunk))
    return "".join(chunks)


def para(text, style="body"):
    return Paragraph(markup(text), STYLES[style])


class Diagram(Flowable):
    """Small vector flow diagram; each row may contain parallel branches."""
    def __init__(self, rows, caption, row_height=47):
        super().__init__()
        self.rows = rows
        self.caption = caption
        self.row_height = row_height
        self.width = WIDTH
        self.height = len(rows) * row_height + (len(rows) - 1) * 20 + 27

    def draw(self):
        c = self.canv
        y = self.height
        previous = None
        for i, row in enumerate(self.rows):
            gap = 12
            w = (self.width - gap * (len(row) - 1)) / len(row)
            centers = [j * (w + gap) + w / 2 for j in range(len(row))]
            if previous is not None:
                top = y + 20
                # Fan-in and fan-out meet on a single horizontal bus.
                c.setStrokeColor(TEAL)
                c.setLineWidth(0.9)
                all_x = previous + centers
                middle = y + 10
                c.line(min(all_x), middle, max(all_x), middle)
                for x in previous:
                    c.line(x, top, x, middle)
                for x in centers:
                    c.line(x, middle, x, y + 3)
                    c.line(x, y + 3, x - 2.4, y + 6.5)
                    c.line(x, y + 3, x + 2.4, y + 6.5)
            for j, text in enumerate(row):
                x = j * (w + gap)
                c.setFillColor(LIGHT if i % 2 == 0 else colors.HexColor("#F3F6FA"))
                c.setStrokeColor(LINE)
                c.roundRect(x, y - self.row_height, w, self.row_height, 5, stroke=1, fill=1)
                p = para(text, "box")
                pw, ph = p.wrap(w - 16, self.row_height - 8)
                if ph > self.row_height - 8:
                    raise ValueError(f"Diagram label overflow: {text}")
                p.drawOn(c, x + 8, y - self.row_height + (self.row_height - ph) / 2)
            previous = centers
            y -= self.row_height + 20
        p = para(self.caption, "small")
        _, ph = p.wrap(self.width, 30)
        p.drawOn(c, 0, 0)


def blocks(items):
    result = []
    for b in items:
        kind = b["type"]
        if kind in ("p", "lead", "h", "small"):
            result.append(para(b["text"], "body" if kind == "p" else kind))
        elif kind == "diagram":
            result.extend([Diagram(b["rows"], b["caption"], b.get("row_height", 47)), Spacer(1, 10)])
        elif kind == "table":
            ratios = b.get("widths", [1] * len(b["rows"][0]))
            widths = [WIDTH * x / sum(ratios) for x in ratios]
            rows = [[para(x, "th" if i == 0 else "cell") for x in row] for i, row in enumerate(b["rows"])]
            t = Table(rows, colWidths=widths, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F1F5F8"), colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, LINE),
            ]))
            result.extend([t, Spacer(1, 12)])
        elif kind == "note":
            p = para(b["text"])
            t = Table([[p]], colWidths=[WIDTH])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF5E6")),
                ("LINEBEFORE", (0, 0), (0, 0), 3, GOLD),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            result.extend([t, Spacer(1, 12)])
        elif kind == "refs":
            ref_title = ParagraphStyle("ref-title", parent=STYLES["h"], fontSize=10.5,
                                       leading=16, spaceBefore=2, spaceAfter=3)
            ref_path = ParagraphStyle("ref-path", parent=STYLES["small"], fontSize=8,
                                      leading=11, spaceAfter=7)
            for sid in b["ids"]:
                s = DATA["sources"][sid]
                result.append(Paragraph(markup(f'[{sid}] {s["title"]}'), ref_title))
                result.append(Paragraph(markup(s["path"]), ref_path))
        else:
            raise ValueError(kind)
    return result


def chrome(c, number, total, section):
    c.setFillColor(TEAL)
    c.rect(0, PAGE_H - 8, PAGE_W, 8, fill=1, stroke=0)
    c.setFont("Latin", 8)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, PAGE_H - 34, "OPENVIKING / SYSTEM DESIGN")
    c.setFont("Latin", 8)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 34, DATA["date"])
    c.setStrokeColor(LINE)
    c.line(MARGIN, 44, PAGE_W - MARGIN, 44)
    c.setFont("Latin", 7.5)
    c.drawString(MARGIN, 29, "CODE BASELINE  " + DATA["commit"][:9])
    c.drawRightString(PAGE_W - MARGIN, 29, f"{number:02d} / {total:02d}")


def render(output):
    setup_fonts()
    os.environ.setdefault("SOURCE_DATE_EPOCH", str(int(
        datetime.fromisoformat(DATA["date"]).replace(tzinfo=timezone.utc).timestamp()
    )))
    c = canvas.Canvas(str(output), pagesize=A4, pageCompression=1, invariant=1)
    c.setTitle(DATA["title"])
    c.setAuthor("OpenViking 系统设计分析")
    c.setSubject("基于源码的系统边界、核心抽象与端到端流程分析")
    total = len(DATA["pages"])
    for i, page in enumerate(DATA["pages"], 1):
        chrome(c, i, total, page["title"])
        key = f"page-{i}"
        c.bookmarkPage(key)
        c.addOutlineEntry(page["title"], key, 0, False)
        c.setFillColor(TEAL)
        c.setFont("Latin", 9)
        c.drawString(MARGIN, PAGE_H - 66, page["kicker"])
        title_style = ParagraphStyle("title", fontName="CJK", fontSize=24 if i == 1 else 20,
                                     leading=32, textColor=INK, wordWrap="CJK")
        title = Paragraph(markup(page["title"]), title_style)
        _, h = title.wrap(WIDTH, 80)
        title.drawOn(c, MARGIN, PAGE_H - 84 - h)
        top = PAGE_H - 84 - h - 19
        story = blocks(page["blocks"])
        frame = Frame(MARGIN, 62, WIDTH, top - 62, leftPadding=0,
                      rightPadding=0, topPadding=0, bottomPadding=0)
        frame.addFromList(story, c)
        if story:
            raise SystemExit(f"Page {i} overflow ({page['title']}): {len(story)} blocks left")
        c.showPage()
    c.save()
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    print(json.dumps({"file": str(output), "pages": total, "bytes": output.stat().st_size,
                      "sha256": sha}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=ROOT / "OpenViking系统设计与整体流程分析.pdf")
    render(p.parse_args().output)
