#!/usr/bin/env python
"""Independent delivery review: 19 tables, 15 inline blocks, 4 supportOnly sets."""
import hashlib
import json
import os
import re

PAPER = "report/paper.md"
RENDERED = ".rework/previews/preview-C/rendered.md"
TEX = ".rework/previews/preview-D/preview.tex"
OUT = ".rework/reviews/04_tables.json"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


idx = json.load(open("report/tables/INDEX.json"))
tables = idx["tables"]
paper = open(PAPER, encoding="utf-8").read()
rendered = open(RENDERED, encoding="utf-8").read()

inline = dict((m.group(1), m.group(2)) for m in re.finditer(r"table-begin:([\w.-]+) sha256=([0-9a-f]{64})", paper))
inline_r = dict((m.group(1), m.group(2)) for m in re.finditer(r"table-begin:([\w.-]+) sha256=([0-9a-f]{64})", rendered))

rows = []
for key, entry in tables.items():
    name = entry["id"]
    md_path = entry["outputs"]["md"]["path"]
    md_sha = entry["outputs"]["md"]["sha256"]
    csv_path = entry["outputs"]["csv"]["path"]
    csv_sha = entry["outputs"]["csv"]["sha256"]
    disk_md = sha(md_path) if os.path.exists(md_path) else None
    disk_csv = sha(csv_path) if os.path.exists(csv_path) else None
    r = {
        "key": key,
        "name": name,
        "paperIncluded": entry.get("paperIncluded"),
        "supportOnly": entry.get("supportOnly"),
        "status": entry.get("status"),
        "complete": entry.get("complete"),
        "inline_in_paper": name in inline,
        "inline_sha_paper": inline.get(name),
        "inline_sha_rendered": inline_r.get(name),
        "index_md_sha": md_sha,
        "disk_md_sha": disk_md,
        "md_file_ok": disk_md == md_sha,
        "inline_matches_index": inline.get(name) == md_sha,
        "rendered_matches_index": inline_r.get(name) == md_sha,
        "csv_file_ok": disk_csv == csv_sha,
        "md_path": md_path,
        "csv_path": csv_path,
        "bytes": entry["outputs"]["md"].get("bytes"),
    }
    rows.append(r)

# supportOnly full-data sets
sets = idx.get("supportOnlySets", {})
set_rows = []
for it in sets.get("items", []):
    for kind in ("md", "csv"):
        p = it.get(kind)
        if p:
            set_rows.append({"set": it.get("name"), "kind": kind, "path": p, "exists": os.path.exists(p),
                             "bytes": os.path.getsize(p) if os.path.exists(p) else None,
                             "sha256": sha(p) if os.path.exists(p) else None})
    for p in it.get("fullData", []) or []:
        set_rows.append({"set": it.get("name"), "kind": "fullData", "path": p, "exists": os.path.exists(p),
                         "bytes": os.path.getsize(p) if os.path.exists(p) else None,
                         "sha256": sha(p) if os.path.exists(p) else None})

# does paper.md mention supportOnly table names as inline blocks? (should be NO)
support_names = [e["id"] for e in tables.values() if e.get("supportOnly")]
support_inline_leak = [n for n in support_names if n in inline]

# tex-side: count table environments and captions
tex = open(TEX, encoding="utf-8").read()
tex_counts = {
    "longtable": tex.count(r"\begin{longtable}"),
    "tabular": tex.count(r"\begin{tabular}"),
    "table_env": tex.count(r"\begin{table}"),
    "captions": tex.count(r"\caption{"),
    "table_captions": len(re.findall(r"\\caption\{表", tex)),
    "table_begin_comments": tex.count("table-begin"),
    "includegraphics": tex.count(r"\includegraphics"),
    "figure_env": tex.count(r"\begin{figure}"),
    "figure_captions": len(re.findall(r"\\caption\{图", tex)),
}

result = {
    "index_tables": len(tables),
    "index_selfCheck": idx.get("selfCheck"),
    "index_generatedAt": idx.get("generatedAt"),
    "current_ledger_sha": sha("state/ledger.json"),
    "current_manifest_sha": sha("report/evidence_manifest.json"),
    "rows": rows,
    "support_sets": set_rows,
    "support_names": support_names,
    "support_inline_leak": support_inline_leak,
    "inline_names_paper": sorted(inline),
    "tex_counts": tex_counts,
}
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"tables in INDEX: {len(tables)}   inline blocks paper.md: {len(inline)}   rendered.md: {len(inline_r)}")
print(f"supportOnly names: {support_names}")
print(f"supportOnly leaked as inline: {support_inline_leak}")
print()
hdr = f"{'key':26s} {'incl':5s} {'sup':5s} {'status':9s} {'mdFile':6s} {'inline=IDX':10s} {'rendered':8s} {'csv':4s}"
print(hdr)
prob = []
for r in rows:
    print(f"{r['key']:26s} {str(r['paperIncluded']):5s} {str(r['supportOnly']):5s} {str(r['status']):9s} "
          f"{str(r['md_file_ok']):6s} {str(r['inline_matches_index']):10s} {str(r['rendered_matches_index']):8s} {str(r['csv_file_ok']):4s}")
    if r["paperIncluded"]:
        if not (r["md_file_ok"] and r["inline_matches_index"] and r["rendered_matches_index"]):
            prob.append(r["key"] + " inline/md mismatch")
    else:
        if not (r["md_file_ok"] and r["csv_file_ok"]):
            prob.append(r["key"] + " supportOnly file mismatch")
        if r["inline_in_paper"]:
            prob.append(r["key"] + " supportOnly but inlined")
print()
print("problems:", prob if prob else "none")
print()
print("supportOnly set files:")
for s in set_rows:
    print(f"  {s['set'][:28]:30s} {s['kind']:9s} exists={s['exists']} bytes={s['bytes']} sha={(s['sha256'] or '')[:12]} {s['path']}")
print()
print("tex counts:", json.dumps(tex_counts, ensure_ascii=False))
print()
print("INDEX selfCheck ledger:", idx["selfCheck"]["ledger"]["revision"], idx["selfCheck"]["ledger"]["sha256"][:12])
print("current ledger       :", sha("state/ledger.json")[:12])
print("INDEX selfCheck manifest:", idx["selfCheck"]["manifest"]["sha256"][:12])
print("current manifest        :", sha("report/evidence_manifest.json")[:12])
