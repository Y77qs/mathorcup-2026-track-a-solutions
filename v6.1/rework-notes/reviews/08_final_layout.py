#!/usr/bin/env python
"""Round-2 independent review: preview-E PDF layout + captions + numbering + anonymity.

Measured with pypdf (never from the xelatex log).
"""
import json
import re

from pypdf import PdfReader

PDF = "report/paper.pdf"
OUT = ".rework/reviews/08_final.json"

reader = PdfReader(PDF)
npages = len(reader.pages)
W = float(reader.pages[0].mediabox.width)
H = float(reader.pages[0].mediabox.height)
L = 2.2 / 2.54 * 72
R = W - L


def count_images(page):
    res = page.get("/Resources")
    if res is None:
        return 0
    xo = res.get_object().get("/XObject")
    if xo is None:
        return 0
    n = 0
    for key in xo.get_object():
        try:
            if xo.get_object()[key].get_object().get("/Subtype") == "/Image":
                n += 1
        except Exception:  # noqa: BLE001
            pass
    return n


def items(page):
    got = []

    def visitor(text, cm, tm, font_dict, font_size):
        t = text.strip()
        if not t:
            return
        got.append({"t": t, "x": tm[4] * cm[0] + tm[5] * cm[2] + cm[4],
                    "y": tm[4] * cm[1] + tm[5] * cm[3] + cm[5]})

    page.extract_text(visitor_text=visitor)
    return got


pages = []
for i, page in enumerate(reader.pages):
    txt = page.extract_text() or ""
    it = items(page)
    hdr = [x for x in it if x["y"] > H - 60]
    ftr = [x for x in it if x["y"] < 60]
    nums = [x for x in ftr if re.fullmatch(r"\d{1,3}", x["t"])]
    pages.append({
        "page": i + 1,
        "chars": len(txt),
        "images": count_images(page),
        "header_count": len(hdr),
        "footer_items": [(x["t"][:20], round(x["x"], 1), round(x["y"], 1)) for x in ftr][:4],
        "page_number": int(nums[0]["t"]) if nums else None,
        "pageno_x": round(nums[0]["x"], 1) if nums else None,
        "outside_margin": [(round(x["x"], 2), round(x["y"], 1), x["t"][:24])
                           for x in it if x["x"] < L - 0.5 or x["x"] > R + 0.5],
        "first_line": (txt.strip().split("\n")[0][:55] if txt.strip() else ""),
    })

full = "\n".join((p.extract_text() or "") for p in reader.pages)
flat = re.sub(r"\s+", "", full)
fig_nums = sorted({int(m) for m in re.findall(r"图\s*(\d{1,2})", full) if 1 <= int(m) <= 40})
tab_nums = sorted({int(m) for m in re.findall(r"表\s*(\d{1,2})", full) if 1 <= int(m) <= 40})
bold_titles = re.findall(r"表\s*(?:q1|q2|q3|rob)-[\w\-]+", full)

checks = {
    "page1_has_DRAFT": "DRAFT" in (reader.pages[0].extract_text() or ""),
    "DRAFT_total": full.count("DRAFT"),
    "page1_has_abstract": bool(re.search(r"摘\s*要", reader.pages[0].extract_text() or "")),
    "page1_has_keywords": "关键词" in (reader.pages[0].extract_text() or ""),
    "identity_leak": [ln for ln in full.split("\n")
                      if re.search(r"作者|指导教师|参赛队号|学校|大学|学院|致\s*谢|@[\w-]+\.[a-z]", ln)][:6],
    "stale_图件尚未登记": "图件尚未登记" in flat,
    "fig_numbers": fig_nums,
    "tab_numbers": tab_nums,
    "bold_table_title_hits": bold_titles,
    "appendix_B_numbering": re.findall(r"B\.[1-3]", flat),
    "orphan_dot_numbering": bool(re.search(r"(?<![\w.])\.1(?=[\u4e00-\u9fff])", flat)),
}

result = {"pdf": PDF, "pages": npages, "page_size": [round(W, 2), round(H, 2)],
          "margin_L": round(L, 2), "margin_R": round(R, 2),
          "per_page": pages, "checks": checks}
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"pages={npages}  size={W:.1f}x{H:.1f}  margins=[{L:.2f},{R:.2f}]")
print("page | chars | imgs | hdr | pageno | x | first line")
for p in pages:
    print(f"{p['page']:4d} | {p['chars']:5d} | {p['images']:4d} | {p['header_count']:3d} |"
          f" {str(p['page_number']):>6} | {str(p['pageno_x']):>6} | {p['first_line'][:44]}")
print()
print("page numbers:", [(p["page"], p["page_number"]) for p in pages])
print("pages with header text:", [p["page"] for p in pages if p["header_count"]])
print("images per page:", [(p["page"], p["images"]) for p in pages if p["images"]], "total", sum(p["images"] for p in pages))
print("fig numbers:", fig_nums, "continuous 1-9:", fig_nums == list(range(1, 10)))
print("table numbers:", tab_nums, "continuous 1-15:", tab_nums == list(range(1, 16)))
print("bold table title hits (should be []):", bold_titles)
print("appendix B headings found:", checks["appendix_B_numbering"])
print("orphan '.1' numbering pattern:", checks["orphan_dot_numbering"])
print("outside-margin items per page:", [(p["page"], p["outside_margin"]) for p in pages if p["outside_margin"]])
print()
for k, v in checks.items():
    if k not in ("fig_numbers", "tab_numbers", "bold_table_title_hits", "appendix_B_numbering"):
        print(f"{k}: {v}")
