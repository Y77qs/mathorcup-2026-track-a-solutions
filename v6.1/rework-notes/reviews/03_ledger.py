#!/usr/bin/env python
"""Independent delivery review: read-only ledger extraction for the DRAFT delivery scope."""
import json
import sys

L = json.load(open("state/ledger.json"))
OUT = ".rework/reviews/03_ledger.json"

res = {}

# ---------- config lifecycle ----------
cl = L.get("configLifecycle", {})
res["config"] = {
    "ledgerConfigSha256": L.get("configSha256"),
    "initRawSha256": cl.get("initRawSha256"),
    "acceptedVersion": cl.get("acceptedVersion"),
    "needsReview": cl.get("needsReview"),
    "versions": [
        {
            "version": v.get("version"),
            "rawSha256": v.get("rawSha256"),
            "protocolSha256": v.get("protocolSha256"),
            "at": v.get("at"),
            "reason": (v.get("reason") or "")[:120],
        }
        for v in (cl.get("versions") or [])
    ],
    "acceptanceEvents": [
        {
            "version": e.get("version"),
            "rawSha256": e.get("rawSha256"),
            "protocolSha256": e.get("protocolSha256"),
            "at": e.get("at"),
        }
        for e in (cl.get("acceptanceEvents") or [])
    ],
}

# ---------- stage / freeze ----------
res["stage"] = L.get("stage")
res["frozen"] = L.get("frozen")

# ---------- questions / selection ----------
res["questions"] = [
    {
        "id": q.get("id"),
        "title": q.get("title"),
        "selectedModelId": q.get("selectedModelId"),
        "selectionPhase": q.get("selectionPhase"),
        "selectionReason": (q.get("selectionReason") or "")[:400],
        "metric": q.get("metric"),
    }
    for q in (L.get("questions") or [])
]

# ---------- claims ----------
claims = []
for c in L.get("claims") or []:
    claims.append(
        {
            "id": c.get("id"),
            "status": c.get("status"),
            "critical": c.get("critical"),
            "questionId": c.get("questionId"),
            "claimType": c.get("claimType"),
            "stale": c.get("stale"),
            "supersededBy": c.get("supersededBy"),
            "refs": [
                r.get("kind") + ":" + str(r.get("experimentId") or r.get("figureId") or r.get("citation"))
                for r in (c.get("refs") or [])
            ],
            "validationIds": c.get("validationIds"),
            "statement": (c.get("statement") or "")[:200],
        }
    )
res["claims"] = claims

# ---------- figures ----------
figs = []
for f in L.get("figures") or []:
    figs.append(
        {
            "id": f.get("id"),
            "status": f.get("status"),
            "supersededBy": f.get("supersededBy"),
            "path": f.get("path"),
            "sha256": f.get("sha256"),
            "experimentId": f.get("experimentId"),
            "caption": (f.get("caption") or "")[:160],
            "scriptFile": f.get("scriptFile"),
        }
    )
res["figures"] = figs

# ---------- renders ----------
res["renders"] = [
    {
        "id": r.get("id"),
        "at": r.get("at"),
        "input": r.get("input"),
        "inputSha256": r.get("inputSha256"),
        "output": r.get("output"),
        "outputSha256": r.get("outputSha256"),
        "configVersion": r.get("configVersion"),
        "configRawSha256": r.get("configRawSha256"),
        "frozenAt": r.get("frozenAt"),
        "selectedModels": r.get("selectedModels"),
        "stale": r.get("stale"),
        "warnings": r.get("warnings"),
    }
    for r in (L.get("renders") or [])
]

# ---------- paper artifacts ----------
res["paperArtifacts"] = L.get("paperArtifacts")

# ---------- quality ----------
q = L.get("quality", {})
res["quality_meta"] = {k: q.get(k) for k in ("schemaVersion", "createdAt", "updatedAt")}
res["requirements"] = [
    {
        "id": r.get("id"),
        "text": (r.get("text") or "")[:180],
        "coverage": r.get("coverage"),
        "coverageType": r.get("coverageType"),
        "blockedReason": (r.get("blockedReason") or "")[:200],
        "refs": r.get("refs"),
    }
    for r in (q.get("requirements") or [])
]
res["checks"] = [
    {
        "id": c.get("id"),
        "checkType": c.get("checkType"),
        "scope": c.get("scope"),
        "status": c.get("status"),
        "passed": c.get("passed"),
        "at": c.get("at"),
        "detail": (json.dumps(c.get("detail"), ensure_ascii=False)[:400] if c.get("detail") is not None else None),
        "message": (c.get("message") or "")[:400],
        "stale": c.get("stale"),
    }
    for c in (q.get("checks") or [])
]
res["reviews"] = [
    {
        "id": r.get("id"),
        "objectType": r.get("objectType"),
        "objectId": r.get("objectId"),
        "verdict": r.get("verdict"),
        "independence": r.get("independence"),
        "at": r.get("at"),
        "method": (r.get("method") or "")[:300],
        "findings": [
            {"severity": f.get("severity"), "text": (f.get("text") or "")[:220], "resolved": f.get("resolved")}
            for f in (r.get("findings") or [])
        ],
    }
    for r in (q.get("reviews") or [])
]
res["robustnessPlans"] = [
    {
        "id": p.get("id"),
        "questionId": p.get("questionId"),
        "status": p.get("status"),
        "metricKey": p.get("metricKey"),
        "decisionRule": p.get("decisionRule"),
        "experimentIds": p.get("experimentIds"),
        "seeds": p.get("seeds"),
        "methods": p.get("methods"),
    }
    for p in (q.get("robustnessPlans") or [])
]

# ---------- validations summary ----------
vals = L.get("validations") or []
res["validations_summary"] = {
    "total": len(vals),
    "passed": sum(1 for v in vals if (v.get("result") or {}).get("passed") is True),
    "failed": sum(1 for v in vals if (v.get("result") or {}).get("passed") is False),
    "stale": sum(1 for v in vals if v.get("stale")),
}

# ---------- splits / datasets ----------
res["splits"] = [
    {"id": s.get("id"), "datasetId": s.get("datasetId"), "method": s.get("method"), "at": s.get("at")}
    for s in (L.get("splits") or [])
]
res["datasets"] = [
    {"id": d.get("id"), "kind": d.get("kind"), "path": d.get("path"), "sha256": d.get("sha256"), "rows": d.get("rows")}
    for d in (L.get("datasets") or [])
]

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1)

# ---------- console ----------
print("### config lifecycle")
print(json.dumps(res["config"], ensure_ascii=False, indent=1)[:2500])
print("\n### stage", L.get("stage"))
print("\n### frozen", json.dumps(res["frozen"], ensure_ascii=False)[:1200])
print("\n### questions / selection")
for qq in res["questions"]:
    print(json.dumps(qq, ensure_ascii=False)[:600])
print("\n### claims summary")
from collections import Counter
print(Counter(c["status"] for c in claims))
for c in claims:
    if c["status"] != "superseded":
        print(f"  {c['id']} status={c['status']} critical={c['critical']} q={c['questionId']} stale={c['stale']} refs={c['refs']}")
print("\n### figures")
for f in figs:
    print(f"  {f['id']} {f['status']} sha={str(f['sha256'])[:12]} exp={f['experimentId']} path={f['path']}")
print("\n### renders")
for r in res["renders"]:
    print(json.dumps(r, ensure_ascii=False)[:700])
print("\n### paperArtifacts")
print(json.dumps(res["paperArtifacts"], ensure_ascii=False)[:900])
print("\n### checks")
for c in res["checks"]:
    print(f"  {c['id']} {c['checkType']} scope={c['scope']} status={c['status']} passed={c['passed']} stale={c['stale']}")
print("\n### reviews")
for r in res["reviews"]:
    print(json.dumps(r, ensure_ascii=False)[:800])
print("\n### requirements")
for r in res["requirements"]:
    print(f"  {r['id']} coverage={r['coverage']} type={r['coverageType']} blocked={(r['blockedReason'] or '')[:120]}")
print("\n### robustness plans")
for p in res["robustnessPlans"]:
    print(json.dumps(p, ensure_ascii=False)[:400])
print("\n### validations", res["validations_summary"])
print("\n### splits", res["splits"])
print("\n### datasets")
for d in res["datasets"]:
    print(json.dumps(d, ensure_ascii=False)[:220])
