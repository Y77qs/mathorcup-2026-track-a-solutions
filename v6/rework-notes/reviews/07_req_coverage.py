#!/usr/bin/env python
"""Independent requirements-coverage review: resolve every ref of REQ-0001..0007 read-only."""
import hashlib
import json
import os

L = json.load(open("state/ledger.json"))
OUT = ".rework/reviews/07_req_coverage.json"

claims = {c["id"]: c for c in L["claims"]}
exps = {e["id"]: e for e in L["experiments"]}
figs = {f["id"]: f for f in L["figures"]}
reqs = L["quality"]["requirements"]

statement = open("problem/statement.md", encoding="utf-8").read()


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def resolve(ref):
    kind = ref.get("kind")
    rid = ref.get("id")
    path = ref.get("path")
    out = {"kind": kind, "id": rid, "path": path}
    if kind == "claim":
        c = claims.get(rid)
        out["exists"] = c is not None
        if c:
            out["status"] = c.get("status")
            out["stale"] = c.get("stale")
            out["supersededBy"] = c.get("supersededBy")
            out["ok"] = c.get("status") == "active" and not c.get("stale")
    elif kind == "experiment":
        e = exps.get(rid)
        out["exists"] = e is not None
        if e:
            out["status"] = e.get("status")
            out["ok"] = e.get("status") == "succeeded"
    elif kind == "figure":
        f = figs.get(rid)
        out["exists"] = f is not None
        if f:
            out["status"] = f.get("status")
            out["supersededBy"] = f.get("supersededBy")
            p = f.get("path")
            disk = sha(p) if os.path.exists(p) else None
            out["sha_match"] = disk == f.get("sha256")
            out["ok"] = f.get("status") == "active" and out["sha_match"]
    elif kind in ("script", "analysis", "report_section"):
        out["exists"] = bool(path) and os.path.exists(path)
        out["ok"] = out["exists"]
        if out["exists"] and kind != "report_section":
            out["sha256"] = sha(path)
    else:
        out["ok"] = False
        out["error"] = "unknown kind"
    return out


rows = []
for r in reqs:
    cov = r.get("coverage") or {}
    refs = [resolve(x) for x in (cov.get("refs") or [])]
    src = r.get("source") or {}
    quote = src.get("quote") or ""
    row = {
        "id": r["id"],
        "text": r.get("text"),
        "coverage_kind": cov.get("kind"),
        "blockedReason": cov.get("blockedReason"),
        "note": cov.get("note"),
        "refs": refs,
        "refs_all_ok": all(x.get("ok") for x in refs) if refs else None,
        "source_path": src.get("path"),
        "quote_exact_in_statement": (quote in statement) if quote else None,
        "quote": quote[:80],
    }
    rows.append(row)

json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for row in rows:
    print("=" * 78)
    print(f"{row['id']}  coverage={row['coverage_kind']}  refs_all_ok={row['refs_all_ok']}  "
          f"quote_in_statement={row['quote_exact_in_statement']}")
    print(f"  text: {(row['text'] or '')[:120]}")
    for x in row["refs"]:
        print("   -", json.dumps(x, ensure_ascii=False)[:170])
    if row["blockedReason"]:
        print("  blockedReason:", row["blockedReason"][:260])
