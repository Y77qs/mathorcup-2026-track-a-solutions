#!/usr/bin/env python
"""Independent delivery review: captions, numbering continuity, footer centring, anonymity."""
import json
import re

from pypdf import PdfReader

PDF = ".rework/previews/preview-D/preview.pdf"
OUT = ".rework/reviews/02_pdf_captions.json"

reader = PdfReader(PDF)
pages = [p.extract_text() or "" for p in reader.pages]
full = "\n".join(pages)
W = float(reader.pages[0].mediabox.width)

fig_caps = []   # (pdfpage, number, text)
tab_caps = []
for i, t in enumerate(pages):
    for m in re.finditer(r"图\s*(\d{1,2})\s", t):
        n = int(m.group(1))
        if 1 <= n <= 40:
            fig_caps.append((i + 1, n, t[max(0, m.start()): m.start() + 60].replace("\n", " ")))
    for m in re.finditer(r"表\s*(\d{1,2})\s", t):
        n = int(m.group(1))
        if 1 <= n <= 40:
            tab_caps.append((i + 1, n, t[max(0, m.start()): m.start() + 60].replace("\n", " ")))

fig_nums = sorted({n for _, n, _ in fig_caps})
tab_nums = sorted({n for _, n, _ in tab_caps})

# footer page number x-position (centred?) using visitor on a body page
footer_detail = []
for idx in (3, 14, 29):  # pdf page 4, 15, 30
    page = reader.pages[idx]
    hits = []

    def visitor(text, cm, tm, font_dict, font_size, _hits=hits):
        t = text.strip()
        if not t:
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        if y < 60:
            _hits.append({"text": t, "x": round(x, 1), "y": round(y, 1), "w": None})

    page.extract_text(visitor_text=visitor)
    for h in hits:
        h["page_width"] = W
        h["centre_offset_pt"] = round(abs(h["x"] + 4 - W / 2), 1)  # approx half-digit width
    footer_detail.append({"pdf_page": idx + 1, "footer": hits})

# page-1 forensics
p1 = pages[0]
p2 = pages[1]
checks = {
    "page1_has_DRAFT": "DRAFT" in p1,
    "page1_DRAFT_occurrences": p1.count("DRAFT"),
    "page1_has_abstract": bool(re.search(r"摘\s*要|摘要", p1)),
    "page1_has_keywords": bool(re.search(r"关键词", p1)),
    "page1_has_toc": bool(re.search(r"目\s*录|目录", p1)),
    "page2_is_toc": bool(re.search(r"目\s*录|目录", p2)),
    "page3_is_toc_cont": bool(re.search(r"\. \. \.|\.\.\.", pages[2])),
    "full_has_DRAFT": full.count("DRAFT"),
    "full_has_author_marker": bool(re.search(r"作者|单位|团队|队伍|指导教师|参赛队号|学校|大学|学院", full)),
    "full_has_acknowledgement": bool(re.search(r"致\s*谢|Acknowledg", full)),
    "full_has_email": bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", full)),
}
author_lines = [ln for ln in full.split("\n")
                if re.search(r"作者|单位|团队|队伍|指导教师|参赛队号|学校|大学|学院|致\s*谢", ln)]
checks["author_lines"] = author_lines[:10]

result = {
    "figure_numbers_found": fig_nums,
    "figure_caption_hits": fig_caps,
    "table_numbers_found": tab_nums,
    "table_caption_hits_count": len(tab_caps),
    "table_first_hits": {},
    "footer_detail": footer_detail,
    "checks": checks,
}
for pg, n, txt in tab_caps:
    result["table_first_hits"].setdefault(n, {"pdf_page": pg, "text": txt})

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=1)

print("figure numbers found:", fig_nums)
print("expected 1..9 continuous:", fig_nums == list(range(1, 10)))
print()
print("figure caption hits (pdfpage, n, text):")
for h in fig_caps:
    print("  ", h[0], "图", h[1], "|", h[2][:55])
print()
print("table numbers found:", tab_nums)
print("table 1..19 continuous:", tab_nums == list(range(1, 20)))
print("table caption-ish hits:", len(tab_caps))
print()
for k, v in checks.items():
    print(f"{k}: {v}")
print()
for fd in footer_detail:
    print("footer", fd)
