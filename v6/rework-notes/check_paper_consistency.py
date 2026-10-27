#!/usr/bin/env python3
"""check_paper_consistency.py — read-only consistency scan for report/paper.md (DRAFT batch).

Checks
  1. no bare internal ledger ids in prose (ids may only live inside {{...}} placeholders or HTML comments)
  2. no retired claim ids anywhere
  3. no forbidden pilot experiment ids / retired figure ids / fake figure refs
  4. every {{metric:EXP-x:key}} resolves to a real, non-stale ledger metric
  5. every {{claim:C}} exists, is active and not stale, and is in the allowed set
  6. every <!-- TABLE:id --> marker is unique and every PENDING-FIGURE registered in .rework/PAPER-DRAFT-HANDOFF.md
  7. no FINAL / 最终提交版 claim (this batch is DRAFT only)
Exit code 0 only if there are zero violations.
"""
import json, re, sys, pathlib

P = pathlib.Path(__file__).resolve().parents[1]
paper = (P / "report/paper.md").read_text(encoding="utf-8")
ledger = json.loads((P / "state/ledger.json").read_text(encoding="utf-8"))
manifest = json.loads((P / "report/evidence_manifest.json").read_text(encoding="utf-8"))
handoff = (P / ".rework/PAPER-DRAFT-HANDOFF.md").read_text(encoding="utf-8")

EXPS = {e["id"]: e for e in ledger["experiments"]}
CLAIMS = {c["id"]: c for c in ledger["claims"]}
viol, notes = [], []

RETIRED_CLAIMS = set(manifest["forbiddenInPaper"]["retiredClaims"])
FORBIDDEN_EXP = {f"EXP-{n:04d}" for n in list(range(38, 73)) + [76, 77]}
RETIRED_FIGS = set(manifest["forbiddenInPaper"]["retiredFigures"])
ALLOWED_CLAIMS = {"CLAIM-0056", "CLAIM-0059", "CLAIM-0041", "CLAIM-0052",
                  "CLAIM-0054", "CLAIM-0053", "CLAIM-0055", "CLAIM-0047"}
ALLOWED_EXP = {"EXP-0073", "EXP-0074", "EXP-0075", "EXP-0079", "EXP-0080",
               "EXP-0089", "EXP-0090", "EXP-0091", "EXP-0092", "EXP-0093", "EXP-0099",
               "EXP-0095", "EXP-0096", "EXP-0097", "EXP-0100", "EXP-0101", "EXP-0102"}

# ---- 1/2/3: ids outside placeholders and comments
stripped = re.sub(r"\{\{[^}]*\}\}", "", paper)
stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.S)
stripped = re.sub(r"`[^`]*`", "", stripped)
for pat, why in [(r"\bCLAIM-\d{4}\b", "claim id in prose"),
                 (r"\bEXP-\d{4}\b", "experiment id in prose"),
                 (r"\bVAL-\d{4}\b", "validation id in prose"),
                 (r"\bROB-\d{4}\b", "robustness id in prose"),
                 (r"\bMCON-\d{4}\b", "model-contract id in prose"),
                 (r"\bFIG-\d{4}\b", "figure id in prose"),
                 (r"\bSPLIT-\d{4}\b", "split id in prose"),
                 (r"\bSCRIPT-\d{4}\b", "script id in prose"),
                 (r"\bREQ-\d{4}\b", "requirement id in prose"),
                 (r"\bTGT-\d{4}\b", "target-contract id in prose")]:
    for m in re.finditer(pat, stripped):
        viol.append(f"§1 {why}: {m.group(0)}")

for rid in RETIRED_CLAIMS:
    if rid in paper:
        viol.append(f"§2 retired claim present: {rid}")
for eid in FORBIDDEN_EXP:
    if eid in paper:
        viol.append(f"§3 forbidden pilot experiment present: {eid}")
for fid in RETIRED_FIGS:
    if fid in paper:
        viol.append(f"§3 retired figure present: {fid}")
# ---- 3b: figure placeholders must point at ACTIVE registered figures with matching bytes
FIG_S = {f["id"]: f for f in ledger["figures"]}
fig_refs = re.findall(r"\{\{figure:(FIG-\d{4})\}\}", paper)
for fid in sorted(set(fig_refs)):
    f = FIG_S.get(fid)
    if f is None:
        viol.append(f"§3b unknown figure id: {fid}")
        continue
    if f.get("status") not in (None, "active"):
        viol.append(f"§3b figure is not ACTIVE: {fid} ({f.get('status')})")
    fp = P / f["path"]
    if not fp.is_file():
        viol.append(f"§3b figure file missing: {fid} {f['path']}")
    else:
        import hashlib as _h
        if _h.sha256(fp.read_bytes()).hexdigest() != f.get("sha256"):
            viol.append(f"§3b figure bytes != registered sha256: {fid}")
    if fid in RETIRED_FIGS:
        viol.append(f"§3b retired figure cited: {fid}")
for fid in RETIRED_FIGS:
    if fid in fig_refs:
        viol.append(f"§3b retired figure cited: {fid}")
notes.append(f"figure placeholders: {len(fig_refs)} refs of {sorted(set(fig_refs))}")
if "PENDING-FIGURE" in paper:
    viol.append("§3b PENDING-FIGURE still present after the figure batch")

for m in re.finditer(r"\bFIG-(\d{4})\b", paper):
    if m.group(0) not in {f["id"] for f in ledger["figures"]}:
        viol.append(f"§3 fake figure id: {m.group(0)}")

# ---- 4: metric placeholders
metric_refs = re.findall(r"\{\{metric:([A-Za-z0-9_\-]+):([^}]+)\}\}", paper)
for eid, key in metric_refs:
    if eid in FORBIDDEN_EXP or eid not in ALLOWED_EXP:
        viol.append(f"§4 metric placeholder on non-whitelisted experiment: {eid}")
        continue
    e = EXPS.get(eid)
    if e is None:
        viol.append(f"§4 metric placeholder on unknown experiment: {eid}")
        continue
    if e.get("status") != "succeeded":
        viol.append(f"§4 metric placeholder on non-succeeded experiment: {eid} ({e.get('status')})")
    if key not in (e.get("metrics") or {}):
        viol.append(f"§4 metric key missing: {eid}:{key}")
notes.append(f"metric placeholders: {len(metric_refs)} refs, {len(set(metric_refs))} unique")

# ---- 5: claim placeholders
claim_refs = re.findall(r"\{\{claim:(CLAIM-\d{4})\}\}", paper)
for cid in set(claim_refs):
    c = CLAIMS.get(cid)
    if c is None:
        viol.append(f"§5 unknown claim: {cid}")
        continue
    if cid not in ALLOWED_CLAIMS:
        viol.append(f"§5 claim outside evidence_manifest active set: {cid}")
    if c.get("status") != "active":
        viol.append(f"§5 claim not active: {cid} ({c.get('status')})")
    if c.get("stale"):
        viol.append(f"§5 claim marked stale: {cid}")
manifest_claims = {q["claim"]["claimId"] for q in manifest["questions"].values()}
manifest_claims |= {q["robustnessClaim"]["claimId"] for q in manifest["questions"].values()}
for cid in ALLOWED_CLAIMS - manifest_claims:
    viol.append(f"§5 allowed claim absent from evidence_manifest: {cid}")
notes.append(f"claim placeholders: {len(claim_refs)} refs of {sorted(set(claim_refs))}")

# ---- 6: tables (markers and/or spliced blocks) and figures
index_path = P / "report/tables/INDEX.json"
table_marks = re.findall(r"<!-- TABLE:([a-z0-9\-]+) -->", paper)
dupes = {t for t in table_marks if table_marks.count(t) > 1}
for d in dupes:
    viol.append(f"§6 duplicate TABLE marker: {d}")
blocks = re.findall(r"<!-- table-begin:([a-z0-9\-]+) sha256=([0-9a-f]{64}) -->\n(.*?)\n<!-- table-end:\1 -->", paper, flags=re.S)
notes.append(f"table markers: {len(table_marks)} unique={len(set(table_marks))}; spliced blocks: {len(blocks)}")

if not index_path.is_file():
    viol.append("§6 report/tables/INDEX.json missing")
else:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    by_tid = {}
    for key, rec in index["tables"].items():
        tid = key.split(" ", 1)[-1]
        by_tid[tid] = rec
        if rec.get("status") != "COMPLETE" or not rec.get("complete"):
            viol.append(f"§6 table not COMPLETE: {key} ({rec.get('reason')})")
        for inp in rec.get("inputs", []):
            f = P / inp["path"]
            if not f.is_file():
                viol.append(f"§6 recorded input missing: {inp['path']}")
                continue
            import hashlib
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            if h != inp["sha256"]:
                viol.append(f"§6 recorded input sha drifted: {inp['path']}")
    seen = set(table_marks) | {b[0] for b in blocks}
    for tid, rec in by_tid.items():
        so = bool(rec.get("supportOnly"))
        if so:
            if tid in seen:
                viol.append(f"§6 supportOnly table still inlined: {tid}")
            for kind in ("md", "csv"):
                out = (rec.get("outputs") or {}).get(kind)
                if not out:
                    viol.append(f"§6 supportOnly table missing {kind} record: {tid}")
                    continue
                f = P / out["path"]
                if not f.is_file():
                    viol.append(f"§6 supportOnly file missing: {out['path']}")
                else:
                    import hashlib as _h2
                    if _h2.sha256(f.read_bytes()).hexdigest() != out["sha256"]:
                        viol.append(f"§6 supportOnly file sha drifted: {out['path']}")
        elif tid not in seen:
            viol.append(f"§6 table generated but absent from paper: {tid}")
    for tid in seen:
        if tid not in by_tid:
            viol.append(f"§6 paper cites ungenerated table: {tid}")
    import hashlib
    for tid, sha, body in blocks:
        rec = by_tid.get(tid)
        if rec is None:
            continue
        want = rec["outputs"]["md"]["sha256"]
        if sha != want:
            viol.append(f"§6 block header sha != INDEX for {tid}")
        frag = (P / rec["outputs"]["md"]["path"]).read_text(encoding="utf-8")
        if hashlib.sha256(frag.encode("utf-8")).hexdigest() != want:
            viol.append(f"§6 fragment file sha != INDEX for {tid}")
        if body.rstrip("\n") != frag.rstrip("\n"):
            viol.append(f"§6 embedded block differs from fragment for {tid}")
figs = re.findall(r"<!-- PENDING-FIGURE:([A-Za-z0-9\-]+) -->", paper)
for f in figs:
    if f not in handoff:
        viol.append(f"§6 PENDING-FIGURE not registered in handoff: {f}")
notes.append(f"pending figures: {len(figs)}")

# ---- 7: DRAFT integrity
if "DRAFT" not in paper:
    viol.append("§7 missing DRAFT marker")
if re.search(r"(?<!非)最终提交版(?!.*不得)", paper) and "不得作为最终提交稿" not in paper:
    viol.append("§7 possible FINAL claim without limitation")

print("== notes ==")
for n in notes:
    print(" ", n)
if viol:
    print("== VIOLATIONS ==")
    for v in viol:
        print(" ", v)
    sys.exit(1)
print("== OK: 0 violations ==")
