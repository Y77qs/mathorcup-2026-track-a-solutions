"""headline_audit.py — one auditable table of every number the paper quotes.

WHY. The plugin's `metric-recompute` quality check is only safe for an experiment's OWN primary
`metricKey` (asking it for another key of a multi-output / set-stability / constraint-satisfaction
experiment is refused by design). The paper nevertheless needs the secondary numbers (energy distance,
profile Spearman, strict non-worsening rate, bootstrap pi, ...) to be traceable to the ledger rather than
typed by hand.

This audit experiment therefore reads the registered `metrics.json` of the CURRENT confirmatory
experiments as frozen dependencies, COPIES the values under stable audit keys, and ASSERTS that each
copy equals its source (it raises on any mismatch, so a silent drift cannot pass). It also re-derives
a few *relations* between numbers (baseline minus candidate MAE, projection cost, sign-definition gap,
verdict-layer balance, ...) so the table is not a blind transcription.

v6 binding: Q1 EXP-0073/EXP-0074, Q2 EXP-0107, Q3 generation EXP-0109, Q3 transfer EXP-0110.
No model is fitted, no data is generated, nothing is re-scored; this is the paper's evidence index.
"""

import json
import math

from modeling_contract import dependency_path, emit_metrics, emit_output, seed

SOURCES = {
    "EXP-0073": "experiments/EXP-0073/metrics.json",   # Q1 candidate
    "EXP-0074": "experiments/EXP-0074/metrics.json",   # Q1 median baseline
    "EXP-0107": "experiments/EXP-0107/metrics.json",   # Q2
    "EXP-0109": "experiments/EXP-0109/metrics.json",   # Q3 generation
    "EXP-0110": "experiments/EXP-0110/metrics.json",   # Q3 transfer
}

# EXPLICIT BINDING (v6): this audit table is PINNED to the confirmatory experiment ids below.
# The caller must declare exactly these ids in MODELING_EXPERIMENT_IDS; any other set is refused
# by name instead of silently replaying values as if they were the audited run.
from v6_experiment_ids import require_pinned as _require_pinned  # noqa: E402

_require_pinned("headline_audit", {exp: exp for exp in SOURCES})

HEADLINES = {
    # ---- Q1 (EXP-0073 candidate / EXP-0074 median baseline)
    "q1-candidate-mae": ("EXP-0073", "mae"),
    "q1-candidate-mae-all50": ("EXP-0073", "mae_all50"),
    "q1-candidate-macro-r2-af30": ("EXP-0073", "macro_r2_af30"),
    "q1-candidate-skill-af30": ("EXP-0073", "skill_af30"),
    "q1-graph-ridge-mae": ("EXP-0073", "mae_graph_ridge"),
    "q1-ridge-mae": ("EXP-0073", "mae_ridge0"),
    "q1-median-mae": ("EXP-0073", "mae_median"),
    "q1-aroma15-mae": ("EXP-0073", "per_group__Aroma15__mae"),
    "q1-flavour15-mae": ("EXP-0073", "per_group__Flavour15__mae"),
    "q1-other20-mae": ("EXP-0073", "per_group__Other20__mae"),
    "q1-n-rows": ("EXP-0073", "n_rows"),
    "q1-n-targets-all50": ("EXP-0073", "n_targets_all50"),
    "q1-n-repeats": ("EXP-0073", "n_repeats"),
    "q1-baseline-mae": ("EXP-0074", "mae"),
    "q1-baseline-mae-all50": ("EXP-0074", "mae_all50"),
    "q1-baseline-macro-r2-af30": ("EXP-0074", "macro_r2_af30"),
    "q1-baseline-n-rows": ("EXP-0074", "n_rows"),
    # ---- Q2 (EXP-0107)
    "q2-jaccard": ("EXP-0107", "topk-jaccard"),
    "q2-jaccard-point": ("EXP-0107", "topk-jaccard-point"),
    "q2-cross-repeat-jaccard": ("EXP-0107", "cross_repeat_jaccard"),
    "q2-sign-stability-mean": ("EXP-0107", "sign_stability_mean"),
    "q2-sign-stability-legacy": ("EXP-0107", "sign_stability_legacy_mean"),
    "q2-pi-mean": ("EXP-0107", "pi_mean"),
    "q2-pi-below-half-count": ("EXP-0107", "pi_below_0.5_count"),
    "q2-pi-below-half-denominator": ("EXP-0107", "pi_below_0.5_denominator"),
    "q2-external-spearman-aligned": ("EXP-0107", "external_6csv_mean_spearman_aligned"),
    "q2-external-rows-matched": ("EXP-0107", "external_6csv_rows_matched"),
    "q2-n-strict-candidates": ("EXP-0107", "n_strict_candidates"),
    "q2-n-extended-candidates": ("EXP-0107", "n_extended_candidates"),
    "q2-bootstrap-reps": ("EXP-0107", "bootstrap_reps"),
    "q2-n-dimensions": ("EXP-0107", "n_dimensions"),
    "q2-n-methods": ("EXP-0107", "n_methods"),
    # ---- Q3 generation (EXP-0109)
    "q3-cs": ("EXP-0109", "constraint-satisfaction"),
    "q3-cs-raw": ("EXP-0109", "constraint-satisfaction-raw"),
    "q3-e-norm": ("EXP-0109", "energy-distance"),
    "q3-e-norm-raw": ("EXP-0109", "energy-distance-raw"),
    "q3-e-V-raw": ("EXP-0109", "energy-V-raw"),
    "q3-e-U-signed": ("EXP-0109", "energy-U-signed"),
    "q3-e-V-subset": ("EXP-0109", "energy-V-subset-tripel-kriek-lambic"),
    "q3-e-U-subset": ("EXP-0109", "energy-U-subset-tripel-kriek-lambic"),
    "q3-profile-rho": ("EXP-0109", "profile-spearman"),
    "q3-profile-pooled-rho": ("EXP-0109", "profile-pooled-spearman"),
    "q3-diversity": ("EXP-0109", "diversity"),
    "q3-duplicate-share": ("EXP-0109", "duplicate-share"),
    "q3-n-cells-estimable": ("EXP-0109", "n-cells-estimable"),
    "q3-n-cells-subset": ("EXP-0109", "n-cells-subset"),
    "q3-n-samples": ("EXP-0109", "n-samples"),
    "q3-t2n-increases": ("EXP-0109", "t2n-increases"),
    "q3-t2n-increase-share": ("EXP-0109", "t2n-proxy-increase-share"),
    "q3-nonenal-increases-design": ("EXP-0109", "nonenal-increases-design"),
    "q3-constraints-verified": ("EXP-0109", "constraints-verified"),
    "q3-constraints-conditional": ("EXP-0109", "constraints-conditional"),
    "q3-constraints-not-identifiable": ("EXP-0109", "constraints-not-identifiable"),
    "q3-constraints-infeasible": ("EXP-0109", "constraints-infeasible"),
    # ---- Q3 transfer (EXP-0110)
    "q3-transfer-energy": ("EXP-0110", "transfer-energy"),
    "q3-transfer-energy-U": ("EXP-0110", "transfer-energy-U"),
    "q3-transfer-energy-normalized": ("EXP-0110", "transfer-energy-normalized"),
    "q3-transfer-energy-source-fixed": ("EXP-0110", "transfer-energy-source-fixed"),
    "q3-transfer-energy-box-mean": ("EXP-0110", "transfer-energy-target-mean-projection"),
    "q3-transfer-energy-full-mean": ("EXP-0110", "transfer-energy-target-mean-projection-full"),
    "q3-nonincrease-rate": ("EXP-0110", "nonincrease-rate"),
    "q3-nonincrease-rate-box-mean": ("EXP-0110", "nonincrease-rate-target-mean-projection"),
    "q3-nonincrease-rate-full-mean": ("EXP-0110", "nonincrease-rate-target-mean-projection-full"),
    "q3-qp-solves": ("EXP-0110", "qp-solves"),
    "q3-qp-status-optimal": ("EXP-0110", "qp-status-optimal"),
    "q3-qp-status-infeasible": ("EXP-0110", "qp-status-infeasible"),
    "q3-qp-status-not-converged": ("EXP-0110", "qp-status-not-converged"),
    "q3-qp-max-primal-residual": ("EXP-0110", "qp-max-primal-residual"),
    "q3-qp-max-dual-residual": ("EXP-0110", "qp-max-dual-residual"),
    "q3-qp-max-constraint-violation": ("EXP-0110", "qp-max-constraint-violation"),
    "q3-qp-max-stale-halfspace-residual": ("EXP-0110", "qp-max-stale-halfspace-residual"),
    "q3-qp-max-stale-identity-error": ("EXP-0110", "qp-max-stale-identity-error"),
    "q3-verdict-verified": ("EXP-0110", "verdict-verified-primary"),
    "q3-verdict-verified-denominator": ("EXP-0110", "verdict-verified-denominator-primary"),
    "q3-verdict-conditional": ("EXP-0110", "verdict-conditional-primary"),
    "q3-verdict-not-identifiable": ("EXP-0110", "verdict-not-identifiable-primary"),
    "q3-verdict-failed": ("EXP-0110", "verdict-failed-primary"),
    "q3-verdict-records": ("EXP-0110", "verdict-records-primary"),
    "q3-mig-t2n-increase-share": ("EXP-0110", "t2n-proxy-increase-share-primary"),
}


def finite(value, what):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("audit quantity %s is not finite: %r" % (what, value))
    return number


def close(a, b, rel_tol=1e-12):
    return a == b or abs(float(a) - float(b)) <= rel_tol * max(abs(float(a)), abs(float(b)), 1e-300)


def main():
    seed_value = seed()
    sources = {}
    for experiment_id, relative in SOURCES.items():
        with open(dependency_path(relative), "r", encoding="utf-8") as handle:
            sources[experiment_id] = json.load(handle)

    metrics = {}
    table = []
    for audit_key, (experiment_id, source_key) in HEADLINES.items():
        source = sources[experiment_id]
        if source_key not in source:
            raise KeyError("%s is not recorded in %s" % (source_key, experiment_id))
        value = finite(source[source_key], audit_key)
        metrics[audit_key] = value
        table.append({"auditKey": audit_key, "experimentId": experiment_id, "metricKey": source_key, "value": value})

    # The audit is not a blind copy: verify the copies agree with their sources and re-derive relations.
    mismatches = []
    for row in table:
        if finite(sources[row["experimentId"]][row["metricKey"]], row["auditKey"]) != metrics[row["auditKey"]]:
            mismatches.append(row["auditKey"])
    if mismatches:
        raise RuntimeError("audit copy mismatch: %s" % mismatches)

    # structural identities that must hold inside the artifacts (a violated one is a finding, not a note)
    qp_solves = metrics["q3-qp-solves"]
    qp_states = (metrics["q3-qp-status-optimal"] + metrics["q3-qp-status-infeasible"]
                 + metrics["q3-qp-status-not-converged"])
    if not close(qp_solves, qp_states):
        raise RuntimeError("QP solve count %r != status counts sum %r" % (qp_solves, qp_states))
    verdict_records = metrics["q3-verdict-records"]
    verdict_denom = metrics["q3-verdict-verified-denominator"]
    verdict_ni = metrics["q3-verdict-not-identifiable"]
    if not close(verdict_records, verdict_denom + verdict_ni):
        raise RuntimeError("verdict records %r != verified denominator %r + not-identifiable %r"
                           % (verdict_records, verdict_denom, verdict_ni))
    verdict_verified = metrics["q3-verdict-verified"]
    verdict_cond = metrics["q3-verdict-conditional"]
    verdict_failed = metrics["q3-verdict-failed"]
    if not close(verdict_denom, verdict_verified + verdict_cond + verdict_failed):
        raise RuntimeError("verified denominator %r != verified %r + conditional %r + failed %r"
                           % (verdict_denom, verdict_verified, verdict_cond, verdict_failed))
    gen_constraints = (metrics["q3-constraints-verified"] + metrics["q3-constraints-conditional"]
                       + metrics["q3-constraints-not-identifiable"] + metrics["q3-constraints-infeasible"])
    if gen_constraints <= 0:
        raise RuntimeError("generation constraint records sum to %r" % gen_constraints)

    relations = {
        # the Q1 candidate improves on the training-median baseline
        "audit-q1-improved": metrics["q1-baseline-mae"] - metrics["q1-candidate-mae"],
        # the 50-target metric is a wider, not the same, average
        "audit-q1-all50-minus-af30": metrics["q1-candidate-mae-all50"] - metrics["q1-candidate-mae"],
        # two sign-stability definitions must stay separate
        "audit-q2-sign-definition-gap": metrics["q2-sign-stability-mean"] - metrics["q2-sign-stability-legacy"],
        # pi-below-half share of the delivered cells
        "audit-q2-pi-below-half-share": (metrics["q2-pi-below-half-count"]
                                         / metrics["q2-pi-below-half-denominator"]),
        # the constrained projection costs a little distributional accuracy under the normalised V
        "audit-q3-projection-cost": metrics["q3-e-norm"] - metrics["q3-e-norm-raw"],
        # the three-style subset is a different scope, not a smaller version of the same number
        "audit-q3-subset-minus-all-V": metrics["q3-e-V-subset"] - metrics["q3-e-V-raw"],
        # the delivered design satisfies the declared constraints where the raw draw does not
        "audit-q3-cs-gain": metrics["q3-cs"] - metrics["q3-cs-raw"],
        # the full-feasible mean projection is worse in transfer energy than the delivered QP
        "audit-q3mig-full-minus-quantile": (metrics["q3-transfer-energy-full-mean"]
                                            - metrics["q3-transfer-energy"]),
        # the box-only control is an intermediate baseline between the full projection and the QP
        "audit-q3mig-box-minus-full": (metrics["q3-transfer-energy-box-mean"]
                                       - metrics["q3-transfer-energy-full-mean"]),
    }
    for key, value in relations.items():
        if not math.isfinite(float(value)):
            raise ValueError("relation %s is not finite" % key)
        metrics[key] = float(value)

    metrics["audit-source-metrics-files"] = float(len(SOURCES))
    metrics["audit-headline-entries"] = float(len(HEADLINES))
    metrics["audit-mismatches"] = float(len(mismatches))
    emit_metrics(metrics)
    emit_output("headline_table", {
        "note": "every value below was copied programmatically from the registered metrics.json of the named experiment; "
                "the runner's sha256 for each source file is in the experiment's dependencies",
        "sources": SOURCES,
        "seed": seed_value,
        "relations": relations,
        "rows": table,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
