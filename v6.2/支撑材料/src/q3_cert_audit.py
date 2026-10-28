#!/usr/bin/env python3
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""Independent audit of a Q3 transfer QP batch (EXP-0080 by default, or a local re-run directory).

This is an AUDIT, not a native optimization-feasibility/optimization-objective
validation: the raw artifacts are re-read and re-computed and the per-certificate
maxima are compared with the aggregates the experiment recorded.

Sources (read-only), `<run>` = argv[1] / $Q3_TRANSFER_RUN_DIR / experiments/EXP-0080:
  <run>/solver_certificates.jsonl   198 QP certificates
  <run>/transfer_constraints.csv    per-field constraint records (n_transfer_rows * 38)
  <run>/transfers.csv               transfer rows (opt/src/ref x 231)
  <run>/metrics.json                recorded aggregates
  <run>/transfer_sources.csv        (v6 runs only) raw/missing/floor/imputed source state per capped column

Outputs (default outputs/q3/, override with argv[2] / $Q3_AUDIT_OUT):
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

TWO GENERATIONS OF ARTIFACTS ARE HANDLED, AND THE OLD ONE IS NEVER REWRITTEN:
  * pre-v6 (EXP-0080): 4 strategies, 396 transfer rows, verdict labels
    verified/conditional/not_identifiable/infeasible, certificates WITHOUT the
    half-space intercept fields. The intercept defect cannot be re-derived here
    (c, centre and scale are not persisted) and is reported as a limitation.
  * v6: 5 strategies, 495 transfer rows, four verdict classes
    (verified/conditional/not_identifiable/failed), certificates carrying
    stale_intercept_c / stale_a_dot_source / stale_halfspace_b /
    stale_halfspace_residual / stale_prediction_delta, and a
    transfer_sources.csv inventory of the source's missing/floor state.
    For those, the half-space identity and the "an imputed or floor-coded source is
    never verified" rule are checked directly.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "experiments" / "EXP-0080"
DEFAULT_OUT = ROOT / "outputs" / "q3"

ADMM_TOL = 1e-8            # src/q3_transfer_fix.py ADMM_TOL
FEAS_TOL = 1e-8            # feasible = violation <= 1e-8
EXACT = 1e-12
CAP_REL, CAP_ABS = 1e-9, 1e-12   # declared nonincreasing tolerance in the production code
STALE_TOL = 1e-9                 # declared stale_hops tolerance
IDENTITY_TOL = 1e-7              # f(z_new)-f(z_source) == (a'z_new - b) + STALE_TOL
CAP_COLUMNS = ("DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal")
PROXY_FIELD = "stale_hops(ridge-proxy)"
VERDICT_CLASSES = ("verified", "conditional", "not_identifiable", "failed")
LEGACY_VERDICT_ALIAS = {"infeasible": "failed"}   # pre-v6 label for the same class


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


def read_csv(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def flag(row, name):
    return str(row.get(name)) == "True"


def as_bool(value):
    """CSV booleans: 'True'/'False' from pandas, and empty for a missing source value."""
    text = str(value).strip().lower()
    return text == "true"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    run = Path(argv[0]).resolve() if len(argv) > 0 else Path(
        os.environ.get("Q3_TRANSFER_RUN_DIR", str(DEFAULT_RUN))).resolve()
    out = Path(argv[1]).resolve() if len(argv) > 1 else Path(
        os.environ.get("Q3_AUDIT_OUT", str(DEFAULT_OUT))).resolve()
    hard, notes = [], []
    certs = read_jsonl(run / "solver_certificates.jsonl")
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    constraints = read_csv(run / "transfer_constraints.csv")
    transfers = read_csv(run / "transfers.csv")
    sources_path = run / "transfer_sources.csv"
    sources = read_csv(sources_path) if sources_path.exists() else []

    # ---------------------------------------------------------------- A. certificates
    n_cert = len(certs)
    transfer_keys = {(r["source_beer"], r["repeat"], r["fold"]) for r in transfers}
    strategies = sorted({str(c.get("strategy")) for c in certs})
    qp_strategies = [s for s in strategies if s.startswith("qp-")]
    expected_cert = len(transfer_keys) * len(qp_strategies)
    if n_cert != expected_cert:
        hard.append(f"certificate count {n_cert} != {expected_cert} "
                    f"({len(transfer_keys)} source x fold contexts x {len(qp_strategies)} QP strategies)")
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

    # ------------------------------------------- A2. the half-space intercept (v6 certificates only)
    intercept_certified = all(c.get("stale_intercept_c") is not None
                              and c.get("stale_halfspace_b") is not None for c in certs)
    halfspace = {"certificatesCarryIntercept": bool(intercept_certified),
                 "nCertificates": n_cert}
    if intercept_certified:
        def close(a, b, tol):
            return abs(float(a) - float(b)) <= tol

        bad_b, bad_source, bad_identity, bad_residual, missing = [], [], [], [], 0
        for c in certs:
            if c.get("stale_intercept_c") is None:
                missing += 1
                continue
            a_dot = float(c["stale_a_dot_source"])
            c_val = float(c["stale_intercept_c"])
            b_val = float(c["stale_halfspace_b"])
            if not close(b_val, a_dot + STALE_TOL, 1e-12):
                bad_b.append(str(c.get("problem_hash")))
            if c.get("stale_prediction_source") is not None and not close(
                    float(c["stale_prediction_source"]), a_dot + c_val, 1e-8):
                bad_source.append(str(c.get("problem_hash")))
            if c.get("stale_prediction_delta") is not None and c.get("stale_halfspace_residual") is not None:
                if not close(float(c["stale_prediction_delta"]),
                             float(c["stale_halfspace_residual"]) + STALE_TOL, IDENTITY_TOL):
                    bad_identity.append(str(c.get("problem_hash")))
                if float(c["stale_halfspace_residual"]) > FEAS_TOL:
                    bad_residual.append(str(c.get("problem_hash")))
        halfspace.update({
            "definition": "a'z_new <= b, b = a'z_source + STALE_TOL = f(z_source) - c + STALE_TOL",
            "missingInterceptFields": int(missing),
            "b_equals_a_dot_source_plus_tol_violations": len(bad_b),
            "f_source_equals_a_dot_source_plus_c_violations": len(bad_source),
            "prediction_delta_identity_violations": len(bad_identity),
            "halfspace_residual_positive": len(bad_residual),
            "maxAbsHalfspaceResidual": max((abs(float(c["stale_halfspace_residual"])) for c in certs
                                            if c.get("stale_halfspace_residual") is not None), default=None),
            "interceptRange": [min(float(c["stale_intercept_c"]) for c in certs),
                               max(float(c["stale_intercept_c"]) for c in certs)],
            "maxRecordedIdentityError": max((float(c["stale_identity_error"]) for c in certs
                                             if c.get("stale_identity_error") is not None), default=None),
        })
        if bad_b:
            hard.append(f"{len(bad_b)} certificates have b != a'z_source + tol")
        if bad_source:
            hard.append(f"{len(bad_source)} certificates have f_source != a'z_source + c")
        if bad_identity:
            hard.append(f"{len(bad_identity)} certificates violate f(z_new)-f(z_source) == (a'z_new-b)+tol")
        if bad_residual:
            hard.append(f"{len(bad_residual)} certificates have a positive half-space residual")
    else:
        halfspace["limitation"] = (
            "pre-v6 artifacts: the certificates record only the right-hand side as it was computed, without c, "
            "a'z_source or the z-space residual; centre/scale are not persisted either, so the intercept error "
            "cannot be re-derived from these files. The old b used f(z_source)+tol instead of a'z_source+tol; "
            "since every fitted c is negative the old box was strictly smaller, so these solutions cannot be "
            "claimed to be the solutions of the declared problem. This audit does NOT re-sign the old batch as "
            "the corrected problem and does not treat the missing fields as a pass.")
        notes.append("the pre-v6 certificate generation is not replaced by this audit; a v6 run directory must be "
                     "pointed at explicitly to audit the corrected half-space.")

    # ------------------------------------------------- B. transfers: flags and movement
    opt_cols = [c[5:] for c in transfers[0].keys() if c.startswith("opt__")]
    if len(opt_cols) != 231:
        hard.append(f"transfers.csv exposes {len(opt_cols)} opt__ columns, expected 231")
    cap_flag_mismatch = stale_flag_mismatch = all_flag_mismatch = 0
    stale_identity_mismatch = 0
    rows_on_stale_boundary = 0
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
        # production rule (src/q3_transfer_fix.py delivered_metrics):
        #   delta = f_new - f_source ; nonincreasing  <=>  delta <= STALE_TOL + 1e-9
        # the extra 1e-9 is the declared CSV round-trip guard, NOT a new tolerance invented here.
        stale_delta = float(row["stale_hops_new"]) - float(row["stale_hops_source"])
        stale_expected = stale_delta <= STALE_TOL + 1e-9
        if abs(stale_delta - STALE_TOL) <= 1e-12:
            rows_on_stale_boundary += 1
        if stale_expected != flag(row, "stale_hops_nonincreasing"):
            stale_flag_mismatch += 1
        if "stale_halfspace_residual" in row and row.get("stale_prediction_delta") not in (None, ""):
            delta = float(row["stale_prediction_delta"])
            residual = float(row["stale_halfspace_residual"])
            if abs(delta - (residual + STALE_TOL)) > IDENTITY_TOL:
                stale_identity_mismatch += 1
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
    if stale_identity_mismatch:
        hard.append(f"{stale_identity_mismatch} transfer rows violate the half-space identity in their own columns")
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
    carries_source_state = bool(constraints) and "is_na_source" in constraints[0]
    unverified_source_state = {"rows_with_source_state": 0, "imputed_but_verified": 0,
                               "floor_coded_but_verified": 0, "recomputed_verdict_mismatch": 0}
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
        if carries_source_state:
            unverified_source_state["rows_with_source_state"] += 1
            is_na = as_bool(r.get("is_na_source"))
            is_floor = as_bool(r.get("is_floor_source"))
            verdict = r["verdict"]
            if (is_na or is_floor) and verdict == "verified":
                unverified_source_state["imputed_but_verified" if is_na else "floor_coded_but_verified"] += 1
            # recompute the declared class from the record's own numbers and flags
            # the proxy row's declared residual is measured ABOVE its numerical tolerance: the production
            # residual is max(0, delta - STALE_TOL), so the class is decided on delta beyond that tolerance.
            class_residual = (max(0.0, exp - STALE_TOL) if bt == "upper_source_value_proxy" else exp)
            recomputed = classify_record(class_residual, is_na, is_floor, r["field"], bt,
                                         stored_after=float(r["stored_after"]))
            if recomputed != verdict:
                unverified_source_state["recomputed_verdict_mismatch"] += 1
    if mismatch["upper_source_value"] or mismatch["lower_zero"]:
        hard.append(f"constraint residual does not reproduce: {mismatch}")
    n_transfer_rows = len(transfers)
    if len(groups) != n_transfer_rows or any(v != 38 for v in groups.values()):
        hard.append(f"constraint groups malformed: {len(groups)} groups (expected {n_transfer_rows}), "
                    f"sizes {sorted(set(groups.values()))}")
    if unverified_source_state["imputed_but_verified"] or unverified_source_state["floor_coded_but_verified"]:
        hard.append("an imputed or floor-coded SOURCE cell is recorded as verified: "
                    f"{unverified_source_state}")
    if unverified_source_state["recomputed_verdict_mismatch"]:
        hard.append(f"{unverified_source_state['recomputed_verdict_mismatch']} constraint records do not match the "
                    "declared verdict rule for their own residual and source flags")

    # ------------------------------------- D. source missing-state inventory (v6 runs only)
    source_state = {"inventoryFile": str(sources_path.name) if sources else None,
                    "nRows": len(sources), "available": bool(sources)}
    if sources:
        missing = [r for r in sources if as_bool(r.get("is_na"))]
        floor = [r for r in sources if as_bool(r.get("is_floor"))]
        source_state.update({
            "nMissingCells": len(missing), "nFloorCodedCells": len(floor),
            "missingDetail": sorted({(int(r["source_beer"]), r["column"]) for r in missing}),
            "floorCodedColumns": sorted({r["column"] for r in floor}),
            "imputedValuesLookFinite": all(
                str(r.get("imputed_value")) not in ("", "nan", "None") for r in missing),
        })
        # every upper-bound record for a missing/floor-coded source cell must NOT be verified
        offenders = []
        key_state = {(int(r["source_beer"]), r["column"]): (as_bool(r.get("is_na")), as_bool(r.get("is_floor")))
                     for r in sources}
        for row in constraints:
            if not str(row["bound_type"]).startswith("upper_source_value"):
                continue
            if row["field"] == PROXY_FIELD:
                continue
            state = key_state.get((int(row["source_beer"]), row["field"]))
            if state is None:
                continue
            if (state[0] or state[1]) and row["verdict"] == "verified":
                offenders.append((row["source_beer"], row["field"], row["strategy"], row["verdict"]))
        source_state["upperBoundVerifiedForUnidentifiedSource"] = {"n": len(offenders),
                                                                   "examples": offenders[:10]}
        if offenders:
            hard.append(f"{len(offenders)} upper-bound records mark an unidentified source concentration as verified")
        known = {(28, "chem__X2.3.butanedione"), (119, "chem__X2.3.butanedione")}
        found = {(beer, column) for beer, column in
                 (pair for pair in source_state["missingDetail"])}
        if known - found:
            hard.append(f"the declared missing source cells are not in the inventory: {sorted(known - found)}")
        source_state["declaredMissingCellsPresent"] = sorted(known & found)
    else:
        source_state["limitation"] = ("pre-v6 artifacts carry no source inventory and no per-record NA/floor flags; "
                                      "the imputed-source defect cannot be re-derived from these files (the src__ "
                                      "columns are already imputed). Reported, never treated as a pass.")

    # ---------------------------------------------------------------- write artifacts
    out.mkdir(parents=True, exist_ok=True)
    cert_rows = [{
        "problem_hash": c.get("problem_hash"), "strategy": c.get("strategy"), "source_beer": c.get("source_beer"),
        "repeat": c.get("repeat"), "fold": c.get("fold"), "status": c.get("status"), "feasible": c.get("feasible"),
        "iterations": c.get("iterations"), "objective": c.get("objective"),
        "primal_residual": c.get("primal_residual"), "dual_residual": c.get("dual_residual"),
        "max_constraint_violation": c.get("max_constraint_violation"),
        "kkt_stationarity_residual": c.get("kkt_stationarity_residual"),
        "n_tight_constraints": c.get("n_tight_constraints"), "n_variables": c.get("n_variables"),
        "inequality_rows": c.get("inequality_rows"),
        "stale_intercept_c": c.get("stale_intercept_c"),
        "stale_a_dot_source": c.get("stale_a_dot_source"),
        "stale_halfspace_b": c.get("stale_halfspace_b"),
        "stale_halfspace_residual": c.get("stale_halfspace_residual"),
        "stale_prediction_delta": c.get("stale_prediction_delta"),
    } for c in certs]
    with open(out / "qp_certificate_recompute.csv", "w", newline="", encoding="utf-8") as fh:
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
                         "is_na_source": r.get("is_na_source"), "is_floor_source": r.get("is_floor_source"),
                         "bound_check_verdict": r.get("bound_check_verdict"),
                         "is_violation": res > 1e-9})
    with open(out / "qp_constraint_recompute.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(con_rows[0].keys()))
        w.writeheader()
        w.writerows(con_rows)

    verdict_classes = {name: 0 for name in VERDICT_CLASSES}
    for label, count in verdicts.items():
        verdict_classes[LEGACY_VERDICT_ALIAS.get(label, label)] += int(count)

    summary = {
        "kind": "q3-transfer-qp-batch.audit",
        "auditTarget": str(run),
        "auditOutput": str(out),
        "note": ("Independent recomputation over the saved artifacts. NOT a native optimization-feasibility/"
                 "optimization-objective validation: the pack wants one declared optimization model + one "
                 "solution.csv, this experiment is a batch of QPs with per-problem certificates."),
        "doesNotReplaceOtherEvidence": ("This audit covers exactly the run directory named in auditTarget. It does "
                                        "not rewrite, re-sign or retire any other experiment's record; a pre-v6 "
                                        "batch keeps its own (uncorrected) evidence and the limitations below."),
        "artifactGeneration": "v6" if intercept_certified or carries_source_state else "pre-v6 (EXP-0080)",
        "inputs": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in
                   (run / "solver_certificates.jsonl", run / "transfer_constraints.csv",
                    run / "transfers.csv", run / "metrics.json")
                   if p.exists()},
        "certificates": {
            "count": n_cert, "expected_count": expected_cert,
            "unique_problem_hash": uniq_hash, "hash_format_violations": bad_hash_format,
            "strategy_counts": strat_counts, "status_counts": status_counts, "feasible_true": feasible_true,
            "max_constraint_violation": max_viol, "max_primal_residual": max_primal,
            "max_dual_residual": max_dual, "max_kkt_stationarity_residual": max_kkt,
            "internal_inconsistencies": len(inconsistent), "aggregates_vs_recorded": aggregates,
        },
        "halfspace_row": halfspace,
        "design_movement": {
            "rows": len(transfers), "columns": len(opt_cols), "strategies": sorted(rate_buckets),
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
            "stale_halfspace_identity_mismatches": stale_identity_mismatch,
            "rows_at_stale_tolerance_boundary": rows_on_stale_boundary,
            "staleRule": ("delta = f_new - f_source must satisfy delta <= STALE_TOL + 1e-9, the production rule "
                          "(declared numerical tolerance plus the CSV round-trip guard); rows landing exactly on the "
                          "boundary are counted, not hidden"),
            "rate_recomputed_vs_recorded": rates,
        },
        "constraint_residual": {
            "rows": len(constraints), "groups": len(groups), "verdicts": verdicts,
            "verdictClasses": verdict_classes,
            "verdictClassNote": "an 'infeasible' label in a pre-v6 artifact is the same class as 'failed'",
            "violating_records": violations, "residual_sum": residual_sum,
            "recompute_mismatch": mismatch, "recompute_max_abs_diff": maxdiff,
            "sourceStateRecheck": unverified_source_state if carries_source_state else "not available (pre-v6)",
            "convention": ("residual = clamp(new - source, 0) in stored space for upper bounds; "
                           "residual = clamp(-new, 0) for lower_zero rows. A BOUND residual, not the movement."),
        },
        "source_missing_state": source_state,
        "separation_statement": ("Design movement and constraint residual are reported separately; the movement is "
                                 "not a violation and the violation is not a distance. The z-space movement declared "
                                 "by the experiment is not recomputable from the saved artifacts."),
        "limitations": notes,
        "hard_failures": hard,
        "passed": not hard,
    }
    (out / "qp_cert_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({k: summary[k] for k in ("auditTarget", "artifactGeneration", "certificates", "halfspace_row",
                                              "nonincrease", "constraint_residual", "source_missing_state",
                                              "hard_failures", "passed")},
                     ensure_ascii=False, indent=1)[:8000])
    if hard:
        print("\nHARD FAILURES:", hard, file=sys.stderr)
        return 1
    return 0


def classify_record(residual, is_na, is_floor, field, bound_type, stored_after=None):
    """The declared four-class rule, re-derived from a constraint record's own numbers and flags.

    It mirrors `q3_transfer_fix.source_nonincreasing_verdict` / `bound_check_verdict` for the fields that are
    non-increase statements about the source; lower-bound (lower_zero) records are classified on their residual only.
    """
    if residual > 1e-12:
        return "failed"
    if str(field) == PROXY_FIELD:
        return "conditional"                      # the stale row is a proxy, never a measurement
    if not str(bound_type).startswith("upper_source_value"):
        # lower_zero: a stored value sitting at 0 is a reported zero, i.e. a censored value, not a measured pass
        if stored_after is not None and abs(float(stored_after)) <= 1e-12:
            return "not_identifiable"
        return "verified"
    if is_na or is_floor:
        return "not_identifiable"                 # the source concentration is not identified
    if field in ("chem__DMS", "chem__X2.3.butanedione", "chem__X4VG"):
        return "verified"
    return "conditional"                          # trans-2-nonenal: declared storage -> concentration convention


if __name__ == "__main__":
    sys.exit(main())
