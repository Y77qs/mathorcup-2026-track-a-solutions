#!/usr/bin/env python3
"""Read-only PDF audit for the DRAFT delivery chain.

Usage: pdf_audit.py <pdf> [--json out.json] [--textdir DIR]

Checks (all measured from the PDF bytes, never from the build log):
  * real page count
  * per-page embedded image count
  * text above the top margin (running header) and text below the body
  * footer page-number sequence (which page carries which number, centred?)
  * DRAFT banner on page 1, TOC on page 2, body numbering
  * figure / table label sequence (图 N, 表 N) and their first page
  * Chinese glyph presence, unresolved {{...}}, PENDING-FIGURE
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

W = 595.276  # A4 width pt
H = 841.89   # A4 height pt
TOP_MARGIN = 2.4 / 2.54 * 72.0      # 68.03 pt
BODY_TOP_Y = H - TOP_MARGIN         # ~773.86
BODY_BOT_Y = TOP_MARGIN             # ~68.03
HEADER_ZONE_Y = BODY_TOP_Y - 2.0    # anything at/above this is outside the text block


def page_items(page):
    """Return [(text, x0, y0, x1, y1)] for every text chunk."""
    items = []

    def visitor(text, cm, tm, font_dict, font_size):
        if not text or not text.strip():
            return
        # tm = text matrix; cm = current transformation matrix
        try:
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        except Exception:
            x, y = 0.0, 0.0
        items.append((text, x, y, font_size))

    page.extract_text(visitor_text=visitor)
    return items


def main(argv):
    pdf = Path(argv[1])
    out_json = None
    textdir = None
    args = argv[2:]
    while args:
        a = args.pop(0)
        if a == "--json":
            out_json = Path(args.pop(0))
        elif a == "--textdir":
            textdir = Path(args.pop(0))
        else:
            raise SystemExit(f"unknown arg {a}")

    reader = PdfReader(str(pdf))
    n = len(reader.pages)
    report = {"pdf": str(pdf), "bytes": pdf.stat().st_size, "pages": n,
              "pageWidth": W, "pageHeight": H,
              "bodyTopY": round(BODY_TOP_Y, 2), "bodyBottomY": round(BODY_BOT_Y, 2),
              "pages_detail": []}

    if textdir:
        textdir.mkdir(parents=True, exist_ok=True)

    all_text = []
    for i, page in enumerate(reader.pages, start=1):
        items = page_items(page)
        page_text = page.extract_text() or ""
        all_text.append(page_text)
        if textdir:
            (textdir / f"page-{i:02d}.txt").write_text(page_text, encoding="utf-8")

        xs = [it[1] for it in items]
        ys = [it[2] for it in items]
        header_hits = []
        footer_hits = []
        for text, x, y, size in items:
            s = text.strip()
            if not s:
                continue
            if y >= HEADER_ZONE_Y:
                header_hits.append({"text": s, "x": round(x, 2), "y": round(y, 2)})
            if y <= BODY_BOT_Y - 2.0:
                footer_hits.append({"text": s, "x": round(x, 2), "y": round(y, 2)})
        try:
            images = len(page.images)
        except Exception:
            images = None
        report["pages_detail"].append({
            "page": i,
            "chars": len(page_text),
            "items": len(items),
            "xmin": round(min(xs), 2) if xs else None,
            "xmax": round(max(xs), 2) if xs else None,
            "ymin": round(min(ys), 2) if ys else None,
            "ymax": round(max(ys), 2) if ys else None,
            "images": images,
            "header_hits": header_hits,
            "footer_hits": footer_hits,
        })

    joined = "\n".join(all_text)
    report["draft_page1"] = "DRAFT" in all_text[0] if n else False
    report["draft_pages"] = [i + 1 for i, t in enumerate(all_text) if "DRAFT" in t]
    report["toc_page2"] = ("目录" in all_text[1]) if n > 1 else False
    report["unresolved_placeholders"] = len(re.findall(r"\{\{|\}\}", joined))
    report["pending_figure"] = joined.count("PENDING-FIGURE")
    report["cjk_chars"] = len(re.findall(r"[\u4e00-\u9fff]", joined))

    # a label is "图 N"/"表 N" where N is a whole number that is NOT the head of a decimal
    # (prose such as "严格表单体表 0.908…" used to be misread as table 0) and not part of a
    # longer numeral; N == 0 is never a real label.
    UNITS = r"(?:列|行|个|维|项|格|张|类|种|款|条|次|水平|模型|组|层)"
    # label scan must skip the front matter: a TOC entry ends with a page number, so
    # "附录 A …两张概率表 32" would otherwise be misread as table 32.
    body_text = "\n".join(t for i, t in enumerate(all_text)
                          if i > 0 and "目录" not in t[:12])
    figs = [int(m) for m in re.findall(r"图\s*(\d+)(?![\d.．])(?!\s*" + UNITS + ")", body_text)
            if int(m) > 0]
    tabs = [int(m) for m in re.findall(r"表\s*(\d+)(?![\d.．])(?!\s*" + UNITS + ")", body_text)
            if int(m) > 0]
    report["figure_labels"] = sorted(set(figs))
    report["table_labels_max"] = max(tabs) if tabs else None
    report["table_labels"] = sorted(set(tabs))

    # page-number sequence: footer chunk that is only digits
    num_by_page = {}
    for d in report["pages_detail"]:
        digits = [h["text"] for h in d["footer_hits"] if re.fullmatch(r"\d{1,3}", h["text"].strip())]
        if digits:
            num_by_page[d["page"]] = {"value": digits, "x": [h["x"] for h in d["footer_hits"] if re.fullmatch(r"\d{1,3}", h["text"].strip())]}
    report["footer_numbers"] = num_by_page

    # centred check: expected centre x ~ W/2
    off = []
    for p, v in num_by_page.items():
        for x in v["x"]:
            if abs(x - W / 2.0) > 12.0:
                off.append({"page": p, "x": x})
    report["footer_offcentre"] = off

    # first body page = first page with footer number 1
    first_one = next((p for p, v in num_by_page.items() if "1" in v["value"]), None)
    report["first_numbered_page"] = first_one
    report["pages_without_number"] = [d["page"] for d in report["pages_detail"] if d["page"] not in num_by_page]

    # header zone violations
    report["header_violations"] = [{"page": d["page"], "hits": d["header_hits"]}
                                   for d in report["pages_detail"] if d["header_hits"]]
    # anything spilling outside the horizontal text block
    report["horizontal_overflow"] = [
        {"page": d["page"], "xmin": d["xmin"], "xmax": d["xmax"]}
        for d in report["pages_detail"]
        if d["xmax"] is not None and (d["xmax"] > W - 2.2 / 2.54 * 72.0 + 3.0 or d["xmin"] < 2.2 / 2.54 * 72.0 - 3.0)
    ]

    if out_json:
        out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "pages", "bytes", "draft_page1", "draft_pages", "toc_page2",
        "unresolved_placeholders", "pending_figure", "cjk_chars",
        "figure_labels", "table_labels", "first_numbered_page",
        "pages_without_number", "footer_offcentre")}, ensure_ascii=False, indent=1))
    print("header_violations:", json.dumps(report["header_violations"], ensure_ascii=False))
    print("horizontal_overflow:", json.dumps(report["horizontal_overflow"], ensure_ascii=False))
    print("pages:", [(d["page"], d["images"], d["chars"], d["ymin"]) for d in report["pages_detail"]])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
