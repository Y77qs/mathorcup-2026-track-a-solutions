#!/usr/bin/env python3
"""Independent audit of the Q3 transfer QP batch (EXP-0080).

This is an AUDIT, not a native optimization-feasibility/optimization-objective
validation: the raw artifacts are re-read and re-computed and the per-certificate
maxima are compared with the aggregates the experiment recorded.

Sources (read-only):
  experiments/EXP-0080/solver_certificates.jsonl   198 QP certificates
  experiments/EXP-0080/transfer_constraints.csv    15048 per-field constraint records
  experiments/EXP-0080/transfers.csv               396 transfer rows (opt/src/ref x 231)
  experiments/EXP-0080/metrics.json                recorded aggregates

Outputs (written under outputs/q3/):
  qp_cert_audit.json
  qp_certificate_recompute.csv
  qp_constraint_recompute.csv

Two quantities are DELIBERATELY kept apart:
  * design movement  -- how far the delivered spectrum moved from its source;
  * constraint residual -- how much it violates a declared bound.
Stored-space movement is recomputable from the artifacts. The recorded
`l1_change_z`/`mean_abs_change_z` are in standardised z-space
(z = (x - centre)/scale, centre/scale are per-fold fit statistics NOT persisted in
the artifacts), so only their structural relation (==0 iff opt == src) is checked;
this limitation is reported, never silently treated as a pass.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "EXP-0080"
OUT = ROOT / "outputs" / "q3"

ADMM_TOL = 1e-8            # src/q3_transfer_fix.py ADMM_TOL
FEAS_TOL = 1e-8            # feasible = violation <= 1e-8
EXACT = 1e-12
CAP_REL, CAP_ABS = 1e-9, 1e-12   # declared nonincreasing tolerance in the production code
CAP_COLUMNS = ("DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def flag(row, name):
    return str(row.get(name)) == "True"


def main() -> int:
    hard, notes = [], []
    certs = read_jsonl(EXP / "solver_certificates.jsonl")
    metrics = json.loads((EXP / "metrics.json").read_text(encoding="utf-8"))
    with open(EXP / "transfer_constraints.csv", newline="", encoding="utf-8") as fh:
        constraints = list(csv.DictReader(fh))
    with open(EXP / "transfers.csv", newline="", encoding="utf-8") as fh:
        transfers = list(csv.DictReader(fh))

    # ---------------------------------------------------------------- A. certificates
    n_cert = len(certs)
    if n_cert != 198:
        hard.append(f"certificate count {n_cert} != 198")
    hashes = [str(c.get("problem_hash")) for c in certs]
    bad_hash_format = sum(1 for h in hashes if len(h) != 64 or any(ch not in "0123456789abcdef" for ch in h))
    if bad_hash_format:
        hard.append(f"{bad_hash_format} problem_hash values are not 64-hex")
    uniq_hash = len(set(hashes))
    if uniq_hash != n_cert:
        hard.append(f"problem_hash duplicates: {uniq_hash} unique of {n_cert}")
    keys = [(c.get("source_beer"), c.get("repeat"), c.get("fold"), c.get("strategy")) for c in certs]
    if len(set(keys)) != len(keys):
        hard.append("certificate (source_beer, repeat, fold, strategy) keys are not unique")

    strat_counts, status_counts, feasible_true = {}, {}, 0
    for c in certs:
        strat_counts[str(c.get("strategy"))] = strat_counts.get(str(c.get("strategy")), 0) + 1
        status_counts[str(c.get("status"))] = status_counts.get(str(c.get("status")), 0) + 1
        feasible_true += 1 if c.get("feasible") is True else 0

    def mx(col):
        return max((float(c[col]) for c in certs if c.get(col) is not None), default=None)

    max_viol, max_primal = mx("max_constraint_violation"), mx("primal_residual")
    max_dual, max_kkt = mx("dual_residual"), mx("kkt_stationarity_residual")

    inconsistent = []
    for c in certs:
        if c.get("status") == "optimal":
            ok = (c.get("feasible") is True and c.get("objective") is not None
                  and float(c["primal_residual"]) < ADMM_TOL and float(c["dual_residual"]) < ADMM_TOL
                  and float(c["max_constraint_violation"]) <= FEAS_TOL)
        elif c.get("status") == "infeasible":
            ok = c.get("feasible") is False and c.get("objective") is None
        else:
            ok = True
        if not ok:
            inconsistent.append({"problem_hash": c.get("problem_hash"), "status": c.get("status")})
    if inconsistent:
        hard.append(f"{len(inconsistent)} certificates are internally inconsistent with their status")

    aggregates = {}
    for rec_key, val in (
        ("qp-solves", n_cert),
        ("qp-status-optimal", status_counts.get("optimal", 0)),
        ("qp-status-infeasible", status_counts.get("infeasible", 0)),
        ("qp-status-not-converged", status_counts.get("not_converged", 0)),
        ("qp-max-constraint-violation", max_viol),
        ("qp-max-primal-residual", max_primal),
        ("qp-max-dual-residual", max_dual),
    ):
        want = metrics.get(rec_key)
        if want is None:
            continue
        same = (val is not None and math.isclose(float(val), float(want), rel_tol=1e-9, abs_tol=EXACT))
        aggregates[rec_key] = {"recomputed": val, "recorded": want, "match": same}
        if not same:
            hard.append(f"aggregate {rec_key}: recomputed {val} != recorded {want}")

    # ------------------------------------------------- B. transfers: flags and movement
    opt_cols = [c[5:] for c in transfers[0].keys() if c.startswith("opt__")]
    if len(opt_cols) != 231:
        hard.append(f"transfers.csv exposes {len(opt_cols)} opt__ columns, expected 231")
    cap_flag_mismatch = stale_flag_mismatch = all_flag_mismatch = 0
    stored_move_max = 0.0
    stored_move_zero_rows = 0
    l1_structural_mismatch = 0
    rate_buckets = {}
    for row in transfers:
        diffs = [abs(float(row["opt__" + c]) - float(row["src__" + c])) for c in opt_cols]
        stored_move_max = max(stored_move_max, sum(diffs))
        stored_move_zero_rows += 1 if sum(diffs) == 0.0 else 0
        l1_zero = abs(float(row["l1_change_z"])) < 1e-15
        opt_equals_src = all(d == 0.0 for d in diffs)
        if l1_zero != opt_equals_src:
            l1_structural_mismatch += 1
        cap_flags = []
        for c in CAP_COLUMNS:
            after, before = float(row[c + "_physical_new"]), float(row[c + "_physical_source"])
            expected = after <= before * (1.0 + CAP_REL) + CAP_ABS
            recorded = flag(row, c + "_nonincreasing")
            cap_flags.append(expected)
            if expected != recorded:
                cap_flag_mismatch += 1
        stale_expected = (float(row["stale_hops_new"])
                          <= float(row["stale_hops_source"]) + 1e-9)
        if stale_expected != flag(row, "stale_hops_nonincreasing"):
            stale_flag_mismatch += 1
        all_expected = all(cap_flags) and flag(row, "stale_hops_nonincreasing")
        if all_expected != flag(row, "nonincrease_all"):
            all_flag_mismatch += 1
        if not flag(row, "fallback_to_source"):
            b = rate_buckets.setdefault(str(row["strategy"]), {"rows": 0, "ok": 0})
            b["rows"] += 1
            b["ok"] += 1 if all_expected else 0
    if cap_flag_mismatch or stale_flag_mismatch or all_flag_mismatch:
        hard.append(f"non-increase flags do not reproduce (cap={cap_flag_mismatch}, "
                    f"stale={stale_flag_mismatch}, all={all_flag_mismatch})")
    if l1_structural_mismatch:
        hard.append(f"{l1_structural_mismatch} rows where l1_change_z==0 does not match opt==src")

    rates = {}
    for s, b in rate_buckets.items():
        rate = b["ok"] / b["rows"]
        rec = metrics.get("nonincrease-rate-" + s)
        rates[s] = {"recomputed": rate, "recorded": rec, "rows_non_fallback": b["rows"],
                    "match": None if rec is None else math.isclose(rate, float(rec), rel_tol=1e-12, abs_tol=EXACT)}
        if rec is not None and not rates[s]["match"]:
            hard.append(f"nonincrease-rate {s}: recomputed {rate} != recorded {rec}")

    notes.append("l1_change_z / mean_abs_change_z are z-space (centre/scale are per-fold fit statistics not saved "
                 "in transfers.csv); their magnitudes are therefore NOT independently recomputable from the "
                 "artifacts. Only the structural relation (l1==0 iff opt==src) is checked, plus the stored-space "
                 "movement sum|opt-src| which is reported separately below.")

    # ------------------------------------- C. constraint records (residual, not movement)
    groups, verdicts = {}, {}
    mismatch = {"upper_source_value": 0, "upper_source_value_proxy": 0, "lower_zero": 0}
    maxdiff = {k: 0.0 for k in mismatch}
    violations = 0
    residual_sum = 0.0
    for r in constraints:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
        a, b, res = float(r["stored_after"]), float(r["stored_before"]), float(r["residual"])
        bt = r["bound_type"]
        exp = max(0.0, a - b) if bt.startswith("upper") else max(0.0, -a)
        d = abs(exp - res)
        maxdiff[bt] = max(maxdiff[bt], d)
        tol = 1e-9 if bt == "upper_source_value_proxy" else EXACT
        if d > tol:
            mismatch[bt] += 1
        if res > 1e-9:
            violations += 1
        residual_sum += res
        g = (r["source_beer"], r["repeat"], r["fold"], r["strategy"])
        groups[g] = groups.get(g, 0) + 1
    if mismatch["upper_source_value"] or mismatch["lower_zero"]:
        hard.append(f"constraint residual does not reproduce: {mismatch}")
    if len(groups) != 396 or any(v != 38 for v in groups.values()):
        hard.append(f"constraint groups malformed: {len(groups)} groups, sizes {sorted(set(groups.values()))}")

    # ---------------------------------------------------------------- write artifacts
    OUT.mkdir(parents=True, exist_ok=True)
    cert_rows = [{
        "problem_hash": c.get("problem_hash"), "strategy": c.get("strategy"), "source_beer": c.get("source_beer"),
        "repeat": c.get("repeat"), "fold": c.get("fold"), "status": c.get("status"), "feasible": c.get("feasible"),
        "iterations": c.get("iterations"), "objective": c.get("objective"),
        "primal_residual": c.get("primal_residual"), "dual_residual": c.get("dual_residual"),
        "max_constraint_violation": c.get("max_constraint_violation"),
        "kkt_stationarity_residual": c.get("kkt_stationarity_residual"),
        "n_tight_constraints": c.get("n_tight_constraints"), "n_variables": c.get("n_variables"),
        "inequality_rows": c.get("inequality_rows"),
    } for c in certs]
    with open(OUT / "qp_certificate_recompute.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cert_rows[0].keys()))
        w.writeheader()
        w.writerows(cert_rows)

    con_rows = []
    for r in constraints:
        a, b, res = float(r["stored_after"]), float(r["stored_before"]), float(r["residual"])
        exp = max(0.0, a - b) if r["bound_type"].startswith("upper") else max(0.0, -a)
        con_rows.append({"source_beer": r["source_beer"], "repeat": r["repeat"], "fold": r["fold"],
                         "strategy": r["strategy"], "field": r["field"], "bound_type": r["bound_type"],
                         "verdict": r["verdict"], "stored_before": r["stored_before"],
                         "stored_after": r["stored_after"], "residual_recorded": r["residual"],
                         "residual_recomputed": exp, "delta": abs(exp - res),
                         "is_violation": res > 1e-9})
    with open(OUT / "qp_constraint_recompute.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(con_rows[0].keys()))
        w.writeheader()
        w.writerows(con_rows)

    summary = {
        "kind": "q3-transfer-qp-batch.audit",
        "note": ("Independent recomputation over the saved artifacts. NOT a native optimization-feasibility/"
                 "optimization-objective validation: the pack wants one declared optimization model + one "
                 "solution.csv, this experiment is 198 QPs with per-problem certificates."),
        "recordedAt": "2026-10-26T13:58Z",
        "inputs": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in
                   (EXP / "solver_certificates.jsonl", EXP / "transfer_constraints.csv",
                    EXP / "transfers.csv", EXP / "metrics.json")},
        "certificates": {
            "count": n_cert, "unique_problem_hash": uniq_hash, "hash_format_violations": bad_hash_format,
            "strategy_counts": strat_counts, "status_counts": status_counts, "feasible_true": feasible_true,
            "max_constraint_violation": max_viol, "max_primal_residual": max_primal,
            "max_dual_residual": max_dual, "max_kkt_stationarity_residual": max_kkt,
            "internal_inconsistencies": len(inconsistent), "aggregates_vs_recorded": aggregates,
        },
        "design_movement": {
            "rows": len(transfers), "columns": len(opt_cols),
            "stored_space_sum_abs_change_max": stored_move_max,
            "stored_space_rows_with_zero_change": stored_move_zero_rows,
            "l1_zero_iff_opt_equals_src_mismatches": l1_structural_mismatch,
            "z_space_l1_recomputable_from_artifacts": False,
        },
        "nonincrease": {
            "definition": "all four capped chemistry columns nonincreasing in PHYSICAL space "
                          "(after <= before*(1+1e-9)+1e-12) AND stale_hops nonincreasing",
            "cap_flag_mismatches": cap_flag_mismatch, "stale_flag_mismatches": stale_flag_mismatch,
            "nonincrease_all_mismatches": all_flag_mismatch,
            "rate_recomputed_vs_recorded": rates,
        },
        "constraint_residual": {
            "rows": len(constraints), "groups": len(groups), "verdicts": verdicts,
            "violating_records": violations, "residual_sum": residual_sum,
            "recompute_mismatch": mismatch, "recompute_max_abs_diff": maxdiff,
            "convention": ("residual = clamp(new - source, 0) in stored space for upper bounds; "
                           "residual = clamp(-new, 0) for lower_zero rows. A BOUND residual, not the movement."),
        },
        "separation_statement": ("Design movement and constraint residual are reported separately; the movement is "
                                 "not a violation and the violation is not a distance. The z-space movement declared "
                                 "by the experiment is not recomputable from the saved artifacts."),
        "limitations": notes,
        "hard_failures": hard,
        "passed": not hard,
    }
    (OUT / "qp_cert_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({k: summary[k] for k in ("certificates", "design_movement", "nonincrease",
                                              "constraint_residual", "hard_failures", "passed")},
                     ensure_ascii=False, indent=1)[:6000])
    if hard:
        print("\nHARD FAILURES:", hard, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
