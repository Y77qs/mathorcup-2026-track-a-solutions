"""r03_reproduce.py — clean-directory reproduction of the selected Q1 / Q3-transfer configuration.

WHY: "it ran once" is not reproducibility. This script builds a FRESH directory that
contains only the frozen code and the frozen inputs (no experiments/, no state/, no
prior outputs), runs the selected scripts there with the frozen interpreter, and
compares the produced metrics against the registered experiments number by number
inside the pre-declared tolerance (absolute 1e-9, relative 1e-6).

What is copied (and hashed): src/*.py (code), data/clean/{q1_mapped,q3}.csv,
data/clean/q3_{style_protocol,thresholds}.json, data/splits/NESTED-CV-1/splits.csv.
Nothing else from the project is readable from the clean root: the scripts derive
PROJECT from their own __file__, so an accidental absolute-path dependency fails here.

Output: state/repro-clean/<run_id>/repro_manifest.json (plus each run's own outputs).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT_ROOT = PROJECT / "state/repro-clean"
ABS_TOL, REL_TOL = 1e-9, 1e-6

COPY = [
    ("src", "src"),
    ("data/clean/q1_mapped.csv", "data/clean/q1_mapped.csv"),
    ("data/clean/q3.csv", "data/clean/q3.csv"),
    ("data/clean/q3_style_protocol.json", "data/clean/q3_style_protocol.json"),
    ("data/clean/q3_thresholds.json", "data/clean/q3_thresholds.json"),
    ("data/splits/NESTED-CV-1/splits.csv", "data/splits/NESTED-CV-1/splits.csv"),
]
TARGETS = [
    # (role, script, args, registered experiment, metric keys to compare)
    ("q1_generation_lowrank", "src/q1_fix.py", ["--repeat", "all"], "EXP-0048",
     ["mae", "mae_ridge0", "mae_graph_ridge", "mae_median", "mae_all50", "skill_af30"]),
    ("q3_transfer_qp", "src/q3_transfer_fix.py", ["--repeat", "all"], "EXP-0051",
     ["nonincrease-rate", "target-mean-self-distance", "qp-status-optimal",
      "qp-max-primal-residual", "transfer-energy"]),
]


def sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_tree(rel_src: str, rel_dst: str, root: Path) -> list:
    src = PROJECT / rel_src
    dst = root / rel_dst
    written = []
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in sorted(src.iterdir()):
            if item.suffix in (".py",) and item.is_file():
                shutil.copy2(item, dst / item.name)
                written.append({"path": str((dst / item.name).relative_to(root)), "sha256": sha256(item)})
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        written.append({"path": str(dst.relative_to(root)), "sha256": sha256(src)})
    return written


def load_metrics(path: Path) -> dict:
    """Read the run's metrics; the Q3 transfer script writes transfer_metrics.json (also copied to metrics.json
    by the runner), so a clean local run must fall back to that name."""
    candidates = [path]
    if path.name == "metrics.json":
        candidates.append(path.with_name("transfer_metrics.json"))
    for candidate in candidates:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}


def main() -> int:
    run_id = time.strftime("%Y%m%d-%H%M%S")
    root = OUT_ROOT / run_id
    if root.exists():
        raise SystemExit(f"refusing to reuse an existing clean root: {root}")
    root.mkdir(parents=True)
    copied = []
    for rel_src, rel_dst in COPY:
        copied += copy_tree(rel_src, rel_dst, root)

    env = dict(os.environ)
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    env["MPLCONFIGDIR"] = str(root / "state/mplconfig")
    env["PYTHONPATH"] = str(root / "src")
    env.pop("MODELING_PROJECT_DIR", None)

    manifest = {
        "kind": "clean-directory-reproduction",
        "runId": run_id,
        "cleanRoot": str(root.relative_to(PROJECT)),
        "interpreter": sys.executable,
        "pythonVersion": sys.version.split()[0],
        "threadEnv": {k: env[k] for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        "tolerance": {"absolute": ABS_TOL, "relative": REL_TOL},
        "copied": copied,
        "runs": [],
        "ok": False,
        "notes": [
            "the clean root contains ONLY frozen code and frozen inputs; experiments/, state/ and prior outputs are absent",
            "each script derives PROJECT from its own __file__, so an absolute-path dependency would fail here",
            "comparison is against the registered experiment metrics inside the pre-declared tolerance",
        ],
    }

    all_ok = True
    for role, script, args, exp_id, keys in TARGETS:
        out_dir = root / "state/repro-out" / role
        out_dir.mkdir(parents=True, exist_ok=True)
        run_env = dict(env)
        run_env["MODELING_EXPERIMENT_DIR"] = str(out_dir)
        cmd = [sys.executable, script, *args]
        started = time.time()
        proc = subprocess.run(cmd, cwd=str(root), env=run_env, capture_output=True, text=True, timeout=1800)
        elapsed = round(time.time() - started, 2)
        produced = load_metrics(out_dir / "metrics.json")
        registered = load_metrics(PROJECT / "experiments" / exp_id / "metrics.json")
        comparisons = {}
        ok = proc.returncode == 0
        for key in keys:
            got = produced.get(key)
            want = registered.get(key)
            if got is None or want is None:
                comparisons[key] = {"produced": got, "registered": want, "passed": False,
                                    "reason": "missing on one side"}
                ok = False
                continue
            delta = abs(float(got) - float(want))
            rel = delta / max(abs(float(want)), 1e-12)
            passed = delta <= ABS_TOL or rel <= REL_TOL
            comparisons[key] = {"produced": float(got), "registered": float(want),
                                "absDelta": delta, "relDelta": rel, "passed": bool(passed)}
            ok = ok and passed
        manifest["runs"].append({
            "role": role, "script": script, "args": args, "registeredExperiment": exp_id,
            "command": " ".join(cmd), "cwd": str(root), "exitCode": proc.returncode,
            "elapsedSeconds": elapsed,
            "stdoutTail": proc.stdout.strip().splitlines()[-3:],
            "stderrTail": proc.stderr.strip().splitlines()[-3:],
            "outputs": sorted(str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file())[:40],
            "comparisons": comparisons, "passed": bool(ok),
        })
        all_ok = all_ok and ok

    manifest["ok"] = bool(all_ok)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    target = OUT_ROOT / f"repro_manifest_{run_id}.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # stable alias for the declared run-script output
    alias = OUT_ROOT / "repro_manifest.json"
    alias.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps({"ok": manifest["ok"], "runId": run_id,
                      "runs": [{"role": r["role"], "passed": r["passed"], "exit": r["exitCode"],
                                "seconds": r["elapsedSeconds"]} for r in manifest["runs"]]}, ensure_ascii=False))
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
