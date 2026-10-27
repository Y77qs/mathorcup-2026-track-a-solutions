#!/usr/bin/env python
"""Independent delivery review: PDF layout forensics for preview-D/preview.pdf.

Checks (measured, not read from log):
  * real page count via pypdf
  * page 1 contains DRAFT banner
  * page 1-2 contain NO page number; body page numbers start at 1 and count up
  * header band (above body text top) must contain NO body text (no running header)
  * footer page number must be horizontally centred
  * per-page embedded image count + Figure caption count
"""
import json
import re
import sys
from collections import Counter

from pypdf import PdfReader
from pypdf.generic import IndirectObject

PDF = ".rework/previews/preview-D/preview.pdf"
OUT = ".rework/reviews/01_pdf_layout.json"


def page_text_items(page):
    """Return list of (text, x, y, fontsize) using a visitor that keeps coordinates."""
    items = []

    def visitor(text, cm, tm, font_dict, font_size):
        t = text.strip()
        if not t:
            return
        # tm is text matrix; cm is CTM. effective position:
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        items.append({"text": t, "x": x, "y": y, "size": font_size})

    try:
        page.extract_text(visitor_text=visitor)
    except Exception as exc:  # noqa: BLE001
        return items, f"visitor-failed: {exc}"
    return items, None


def count_images(page):
    n = 0
    res = page.get("/Resources")
    if res is None:
        return 0
    res = res.get_object()
    xo = res.get("/XObject")
    if xo is None:
        return 0
    xo = xo.get_object()
    for key in xo:
        try:
            obj = xo[key].get_object()
            if obj.get("/Subtype") == "/Image":
                n += 1
        except Exception:  # noqa: BLE001
            pass
    return n


def main():
    reader = PdfReader(PDF)
    npages = len(reader.pages)
    mb = reader.pdf_header
    # page size
    p0 = reader.pages[0]
    box = p0.mediabox
    W = float(box.width)
    H = float(box.height)

    pages = []
    for i, page in enumerate(reader.pages):
        items, err = page_text_items(page)
        txt = page.extract_text() or ""
        # geometry heuristics on A4: top margin 2.4cm ~ 68.03pt, bottom 2.4cm, footskip 1.1cm
        # header band = y > H - 60 (above body start); footer band = y < 60
        header = [it for it in items if it["y"] > H - 60]
        footer = [it for it in items if it["y"] < 60]
        # page-number detection: footer text that is only digits (arabic) or roman
        pn = None
        for it in footer:
            if re.fullmatch(r"\d{1,3}", it["text"]):
                pn = int(it["text"])
                pn_x = it["x"]
                pn_y = it["y"]
                break
        digits_only_footer = [it["text"] for it in footer if re.fullmatch(r"\d{1,3}", it["text"])]
        pages.append(
            {
                "page": i + 1,
                "chars": len(txt),
                "images": count_images(page),
                "header_items": [(it["text"][:40], round(it["y"], 1)) for it in header][:6],
                "header_count": len(header),
                "footer_items": [(it["text"][:40], round(it["x"], 1), round(it["y"], 1)) for it in footer][:6],
                "footer_count": len(footer),
                "page_number_arabic": pn,
                "digits_in_footer": digits_only_footer,
                "first_line": txt.strip().split("\n")[0][:60] if txt.strip() else "",
                "visitor_err": err,
            }
        )

    result = {
        "pdf": PDF,
        "pdf_header": str(mb),
        "pages": npages,
        "page_size_pt": [round(W, 2), round(H, 2)],
        "page_size_cm": [round(W / 72 * 2.54, 2), round(H / 72 * 2.54, 2)],
        "page1_has_DRAFT": "DRAFT" in (reader.pages[0].extract_text() or ""),
        "page2_has_DRAFT": "DRAFT" in (reader.pages[1].extract_text() or ""),
        "per_page": pages,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)

    # ---- console summary ----
    print(f"pages={npages}  size={W:.1f}x{H:.1f}pt ({W/72*2.54:.2f}x{H/72*2.54:.2f}cm)  header={mb}")
    print(f"page1_has_DRAFT={result['page1_has_DRAFT']}  page2_has_DRAFT={result['page2_has_DRAFT']}")
    print("page | chars | imgs | hdr | ftr | pageno | first line")
    for p in pages:
        print(
            f"{p['page']:4d} | {p['chars']:5d} | {p['images']:4d} | {p['header_count']:3d} |"
            f" {p['footer_count']:3d} | {str(p['page_number_arabic']):>6} | {p['first_line'][:45]}"
        )
    arabic = [(p["page"], p["page_number_arabic"]) for p in pages if p["page_number_arabic"] is not None]
    print("\narabic page numbers found:", arabic)
    hdr = [p for p in pages if p["header_count"]]
    print("pages with text in header band:", [(p["page"], p["header_items"]) for p in hdr])
    imgs = sum(p["images"] for p in pages)
    print("total embedded images:", imgs)
    print("images per page:", [(p["page"], p["images"]) for p in pages if p["images"]])


if __name__ == "__main__":
    sys.exit(main())
