#!/usr/bin/env python3
"""refresh_evidence_index.py — regenerate the evidence manifest and attach the figure index to
report/tables/INDEX.json, then re-verify the 19 table hashes.

Steps (all idempotent, no ledger writes):
  1. run src/r07_evidence_manifest.py  -> report/evidence_manifest.json (adds the ACTIVE figure index)
  2. read report/tables/INDEX.json, set INDEX["figures"] = manifest["figures"] + ledger snapshot,
     write it back (table entries untouched)
  3. run src/paper_tables.py --verify   -> must stay 19/19
  4. print the resulting sha256s
"""
import hashlib, json, subprocess, sys, pathlib

P = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable


def sha(p):
    return hashlib.sha256((P / p).read_bytes()).hexdigest()


def main():
    r = subprocess.run([PY, "src/r07_evidence_manifest.py"], cwd=str(P), capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip()[-2000:])
    if r.returncode != 0:
        return 1

    man = json.loads((P / "report/evidence_manifest.json").read_text(encoding="utf-8"))
    ledger = json.loads((P / "state/ledger.json").read_text(encoding="utf-8"))
    idx_path = P / "report/tables/INDEX.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    rc = ledger["quality"]["runControl"]
    idx["figures"] = {
        "source": "report/evidence_manifest.json#figures (ACTIVE only, current file bytes)",
        "paperCited": man["figures"]["paperCited"],
        "active": man["figures"]["active"],
    }
    idx["ledgerSnapshot"] = {
        "revision": ledger["revision"],
        "runtimeRevision": ledger.get("runtimeRevision"),
        "updatedAt": ledger["updatedAt"],
        "ledgerSha256": sha("state/ledger.json"),
        "semantics": ("revision/updatedAt are BUSINESS fields and only change on ledger record edits; "
                      "runtimeRevision is host/runtime bookkeeping written by the tool host on every call "
                      "and is not a business change. This snapshot is recorded once per batch, not chased."),
        "activeRunId": rc.get("activeRunId"),
    }
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")

    v = subprocess.run([PY, "src/paper_tables.py", "--verify"], cwd=str(P), capture_output=True, text=True)
    tail = [l for l in v.stdout.strip().splitlines() if l.startswith("verify:")]
    print("tables", tail[-1] if tail else "(no verify summary)")
    print(json.dumps({
        "paper": {"sha256": sha("report/paper.md")},
        "manifest": {"sha256": sha("report/evidence_manifest.json")},
        "tablesIndex": {"sha256": sha("report/tables/INDEX.json")},
        "activeFigures": len(man["figures"]["active"]),
        "paperCitedFigures": man["figures"]["paperCited"],
    }, ensure_ascii=False))
    return 0 if v.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
