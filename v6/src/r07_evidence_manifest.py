#!/usr/bin/env python3
"""Freeze the paper evidence manifest from the CURRENT ledger (read-only on the ledger).

Writes report/evidence_manifest.json with exactly the objects this DRAFT may cite.
Fails loudly if an expected claim is not active.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
L = json.loads((P / "state" / "ledger.json").read_text(encoding="utf-8"))
C = {c["id"]: c for c in L["claims"]}
E = {e["id"]: e for e in L["experiments"]}
V = {v["id"]: v for v in L["validations"]}
R = {p["id"]: p for p in L["quality"]["robustnessPlans"]}
Q = {q["id"]: q for q in L["questions"]}

WANT = {
    "Q1": {"claim": "CLAIM-0056", "robustness": "CLAIM-0059", "rob": "ROB-0011", "exp": "EXP-0073"},
    "Q2": {"claim": "CLAIM-0041", "robustness": "CLAIM-0052", "rob": "ROB-0008", "exp": "EXP-0075"},
    "Q3gen": {"claim": "CLAIM-0054", "robustness": "CLAIM-0053", "rob": "ROB-0009", "exp": "EXP-0079"},
    "Q3mig": {"claim": "CLAIM-0055", "robustness": "CLAIM-0047", "rob": "ROB-0010", "exp": "EXP-0080"},
}


def sha(rel):
    p = P / rel
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def claim_block(cid):
    c = C[cid]
    if c["status"] != "active":
        raise SystemExit(f"{cid} is {c['status']}, not active: do not cite it in the paper")
    return {
        "claimId": cid, "status": c["status"], "critical": c["critical"],
        "claimType": c["quality"]["claimType"], "targetContractId": c["quality"].get("targetContractId"),
        "refs": c["refs"], "validationIds": c.get("validationIds") or [],
        "limitations": c["quality"].get("limitations") or [],
        "statement": c["statement"],
    }


def rob_block(rid):
    p = R[rid]
    r = p.get("result") or {}
    vals = r.get("values")
    if isinstance(vals, dict):
        vals = vals.get("values")
    return {
        "robId": rid, "preregisteredAt": p["preregisteredAt"], "executedAt": p.get("executedAt"),
        "experimentIds": p["experimentIds"], "metricKey": p["metricKey"],
        "decisionRule": p["decisionRule"], "values": vals,
        "spread": (r.get("spread") if isinstance(r.get("spread"), (int, float)) else None),
        "decisionPassed": p.get("decisionPassed"), "executionStatus": p.get("executionStatus"),
    }


out = {"kind": "paper-evidence-manifest", "generatedFrom": "state/ledger.json",
       "ledgerRevision": L["revision"], "draftOnly": True,
       "citationRule": "only objects listed here may appear in report/paper.md; ids are read from the ledger, never hand-typed",
       "questions": {}}
for key, w in WANT.items():
    qid = "Q3" if key.startswith("Q3") else key
    q = Q[qid]
    e = E[w["exp"]]
    out["questions"][key] = {
        "questionId": qid,
        "selectedModelId": q.get("selectedModelId"), "selectionStatus": q.get("selectionStatus"),
        "claim": claim_block(w["claim"]),
        "robustnessClaim": claim_block(w["robustness"]),
        "robustnessPlan": rob_block(w["rob"]),
        "experiment": {"id": e["id"], "status": e["status"], "metricsSha256": sha(f"experiments/{e['id']}/metrics.json"),
                       "resultSha256": e.get("resultSha256"), "dependencies": len(e.get("dependencies") or [])},
        "validations": {vid: {"checkType": V[vid]["checkType"], "passed": V[vid]["result"].get("passed"),
                              "stale": V[vid].get("stale")}
                        for vid in (C[w["claim"]].get("validationIds") or []) if vid in V},
    }
out["forbiddenInPaper"] = {
    "retiredClaims": ["CLAIM-0012", "CLAIM-0014", "CLAIM-0018", "CLAIM-0019", "CLAIM-0021", "CLAIM-0022"],
    "pilotExperiments": "EXP-0038..EXP-0072 and EXP-0076/0077 must not be cited as current evidence",
    "retiredFigures": [f["id"] for f in L["figures"] if f.get("status") in ("superseded", "retired")],
}
# ---- figure evidence index (added in the figure-build batch) -------------------------------------------------
# ACTIVE figures only; sha256 is computed from the CURRENT file bytes so the manifest binds the
# delivered figure version, not a caption string. `paperCited` is read from report/paper.md.
_paper = P / "report" / "paper.md"
_cited = []
if _paper.exists():
    import re as _re
    _cited = sorted(set(_re.findall(r"\{\{figure:(FIG-\d{4})\}\}", _paper.read_text(encoding="utf-8"))))
_retired_ids = {f["id"] for f in L["figures"] if f.get("status") in ("superseded", "retired")}
out["figures"] = {
    "note": ("ACTIVE figures only; sha256 is the CURRENT file bytes. retiredFigures above are history "
             "and must not be cited by the paper."),
    "paperCited": _cited,
    "active": [
        {"figureId": f["id"], "path": f["path"], "sha256": sha(f["path"]), "caption": f.get("caption"),
         "experimentIds": f.get("experimentIds") or [], "citedInPaper": f["id"] in _cited}
        for f in L["figures"] if f["id"] not in _retired_ids
    ],
}
out["qualitySnapshot"] = {
    "note": "run modeling_validate quality-report for the authoritative current values; this snapshot is informational",
    "questions": {q["id"]: q.get("selectionStatus") for q in L["questions"]},
}
outp = P / "report/evidence_manifest.json"
outp.parent.mkdir(parents=True, exist_ok=True)
outp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"path": str(outp.relative_to(P)),
                  "sha256": hashlib.sha256(outp.read_bytes()).hexdigest(),
                  "claims": {k: v["claim"]["claimId"] + "/" + v["robustnessClaim"]["claimId"] for k, v in out["questions"].items()},
                  "selection": out["qualitySnapshot"]["questions"]}, ensure_ascii=False))
