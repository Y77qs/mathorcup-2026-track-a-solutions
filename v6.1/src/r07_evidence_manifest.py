#!/usr/bin/env python3
"""Freeze the paper evidence manifest from the CURRENT ledger (read-only on the ledger).

Writes report/evidence_manifest.json with exactly the objects this DRAFT may cite.
Fails loudly if an expected claim is not active / a robustness claim is missing.

v6 binding (confirmatory rework):
  Q1    claim CLAIM-0056, robustness CLAIM-0059, plan ROB-0011, experiment EXP-0073
  Q2    claim CLAIM-0060, robustness <looked up by plan>, plan ROB-0012, experiment EXP-0107
  Q3gen claim CLAIM-0061, robustness <looked up by plan>, plan ROB-0013, experiment EXP-0109
  Q3mig claim CLAIM-0067, robustness <looked up by plan>, plan ROB-0014, experiment EXP-0110

The robustness claim id is NOT hard-typed: it is resolved from the ledger field
``quality.appliesTo.robustnessPlanId`` so the manifest cannot silently keep citing a
superseded plan's claim. A plan without an active claim is a named failure.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

P = Path(__file__).resolve().parents[1]
L = json.loads((P / "state" / "ledger.json").read_text(encoding="utf-8"))
C = {c["id"]: c for c in L["claims"]}
E = {e["id"]: e for e in L["experiments"]}
V = {v["id"]: v for v in L["validations"]}
R = {p["id"]: p for p in L["quality"]["robustnessPlans"]}
Q = {q["id"]: q for q in L["questions"]}

WANT = {
    # Q1 robustness claim is pinned explicitly: CLAIM-0056 (main Q1 claim) also carries
    # appliesTo.robustnessPlanId=ROB-0011, so a plan-id lookup would pick the main claim.
    "Q1": {"claim": "CLAIM-0056", "robustness": "CLAIM-0059", "rob": "ROB-0011", "exp": "EXP-0073"},
    "Q2": {"claim": "CLAIM-0060", "rob": "ROB-0015", "exp": "EXP-0107"},
    "Q3gen": {"claim": "CLAIM-0061", "rob": "ROB-0016", "exp": "EXP-0109"},
    "Q3mig": {"claim": "CLAIM-0067", "rob": "ROB-0017", "exp": "EXP-0110"},
}


class ManifestError(SystemExit):
    """Named refusal: the ledger does not carry the object the paper wants to cite."""


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
    c = C.get(cid)
    if c is None:
        raise ManifestError(f"r07_evidence_manifest: 台账中没有 claim {cid}，不能引用")
    if c["status"] != "active":
        raise ManifestError(f"{cid} is {c['status']}, not active: do not cite it in the paper")
    return {
        "claimId": cid, "status": c["status"], "critical": c["critical"],
        "claimType": c["quality"]["claimType"], "targetContractId": c["quality"].get("targetContractId"),
        "refs": c["refs"], "validationIds": c.get("validationIds") or [],
        "limitations": c["quality"].get("limitations") or [],
        "statement": c["statement"],
    }


def robustness_claim_for(rob_id):
    """Resolve the active robustness claim attached to this plan (never hand-typed)."""
    matches = [c for c in L["claims"]
               if c["status"] == "active"
               and ((c.get("quality") or {}).get("appliesTo") or {}).get("robustnessPlanId") == rob_id]
    if not matches:
        raise ManifestError(
            f"r07_evidence_manifest: 台账中没有绑定到 {rob_id} 的 active 稳健性结论"
            f"（quality.appliesTo.robustnessPlanId={rob_id}）。请由台账持有者创建该结论后再生成 manifest；"
            "本脚本不会回退到旧计划（ROB-0008/0009/0010）的结论。")
    if len(matches) > 1:
        raise ManifestError(
            f"r07_evidence_manifest: {rob_id} 绑定了多条 active 结论 {[c['id'] for c in matches]}，"
            "无法唯一确定引用对象")
    return matches[0]["id"]


def rob_block(rid):
    p = R.get(rid)
    if p is None:
        raise ManifestError(f"r07_evidence_manifest: 台账中没有稳健性计划 {rid}")
    if not p.get("executedAt"):
        raise ManifestError(f"r07_evidence_manifest: 稳健性计划 {rid} 尚未执行，不能作为当前证据")
    r = p.get("result") or {}
    vals = r.get("values")
    if isinstance(vals, dict):
        vals = vals.get("values")
    return {
        "robId": rid, "preregisteredAt": p["preregisteredAt"], "executedAt": p.get("executedAt"),
        "experimentIds": p.get("experimentIds") or [], "metricKey": p["metricKey"],
        "decisionRule": p["decisionRule"], "values": vals,
        "spread": (r.get("spread") if isinstance(r.get("spread"), (int, float)) else None),
        "decisionPassed": p.get("decisionPassed"), "executionStatus": p.get("executionStatus"),
    }


active_claim_ids = {c["id"] for c in L["claims"] if c["status"] == "active"}
out = {"kind": "paper-evidence-manifest", "generatedFrom": "state/ledger.json",
       "ledgerRevision": L["revision"], "draftOnly": True,
       "citationRule": "only objects listed here may appear in report/paper.md; ids are read from the ledger, never hand-typed",
       "questions": {}}
for key, w in WANT.items():
    qid = "Q3" if key.startswith("Q3") else key
    q = Q[qid]
    e = E.get(w["exp"])
    if e is None:
        raise ManifestError(f"r07_evidence_manifest: 台账中没有实验 {w['exp']}")
    if e.get("status") != "succeeded":
        raise ManifestError(f"r07_evidence_manifest: 实验 {w['exp']} 状态为 {e.get('status')!r}，不是 succeeded")
    rob_claim_id = w.get("robustness") or robustness_claim_for(w["rob"])
    if w.get("robustness") and w["robustness"] not in active_claim_ids:
        raise ManifestError(rf"r07_evidence_manifest: 指定的稳健性结论 {w['robustness']} 不是 active")
    out["questions"][key] = {
        "questionId": qid,
        "selectedModelId": q.get("selectedModelId"), "selectionStatus": q.get("selectionStatus"),
        "claim": claim_block(w["claim"]),
        "robustnessClaim": claim_block(rob_claim_id),
        "robustnessPlan": rob_block(w["rob"]),
        "experiment": {"id": e["id"], "status": e["status"], "metricsSha256": sha(f"experiments/{e['id']}/metrics.json"),
                       "resultSha256": e.get("resultSha256"), "dependencies": len(e.get("dependencies") or [])},
        "validations": {vid: {"checkType": V[vid]["checkType"], "passed": V[vid]["result"].get("passed"),
                              "stale": V[vid].get("stale")}
                        for vid in (C[w["claim"]].get("validationIds") or []) if vid in V},
    }
superseded_or_retired = sorted({c["id"] for c in L["claims"] if c["status"] != "active"})
out["forbiddenInPaper"] = {
    "retiredClaims": superseded_or_retired,
    "supersededRobustnessPlans": ["ROB-0008", "ROB-0009", "ROB-0010"],
    "pilotExperiments": ("EXP-0038..EXP-0072 and EXP-0076/0077 (pilot round) and "
                         "EXP-0075/0079/0080 + EXP-0089..0099 (previous confirmatory round) "
                         "must not be cited as current evidence"),
    "retiredFigures": [f["id"] for f in L["figures"] if f.get("status") in ("superseded", "retired")],
}
# ---- figure evidence index (added in the figure-build batch) -------------------------------------------------
# ACTIVE figures only; sha256 is computed from the CURRENT file bytes so the manifest binds the
# delivered figure version, not a caption string. `paperCited` is read from report/paper.md.
_paper = P / "report" / "paper.md"
_cited = []
if _paper.exists():
    _cited = sorted(set(re.findall(r"\{\{figure:(FIG-\d{4})\}\}", _paper.read_text(encoding="utf-8"))))
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
outp.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({"path": str(outp.relative_to(P)),
                  "sha256": hashlib.sha256(outp.read_bytes()).hexdigest(),
                  "claims": {k: v["claim"]["claimId"] + "/" + v["robustnessClaim"]["claimId"]
                             for k, v in out["questions"].items()},
                  "plans": {k: v["robustnessPlan"]["robId"] + ":" + str(v["robustnessPlan"]["values"])
                            for k, v in out["questions"].items()},
                  "selection": out["qualitySnapshot"]["questions"]}, ensure_ascii=False))
