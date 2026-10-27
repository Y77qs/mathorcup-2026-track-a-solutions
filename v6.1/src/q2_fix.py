#!/usr/bin/env python
"""q2_fix.py — MathorCup 2026 A / Q2 repair run (F06/F09): name-only two-way alignment, category split,
strict + extended boards, full-flow stratified bootstrap stability, repeat-pooled metrics.

WHY (v5.1 §4).  The superseded Q2 pipeline scored a 219-row candidate matrix with indices taken from the
231-feature space, and aligned the 50 sensory columns of the attachment table 6.csv BY POSITION.  The tail of
that table is ordered Carbonation / Aftertaste / Body / Overall while the target order is
aftertaste / body / co2 / overall, so three sensory columns were swapped; together with the 219-vs-231 index
mix every chemistry row was shifted as well.  This script removes every positional lookup:

  * chemistry rows of 6.csv -> feature names through data/clean/q2_chem_meta.json (corrLabel first, then name),
    normalised, asserted one-to-one; duplicates / ambiguities / unmatched rows are reported BY NAME and abort
    the run instead of being silently dropped or guessed;
  * sensory columns of 6.csv -> TARGET names through a literal 50-entry dictionary, cross-checked against
    MathorCup_A_独立审查与重跑方案/sensory_name_alignment.csv (sha256 recorded) and against the header set of
    6.csv itself (50/50); the positional order is measured and reported as wrong (3 columns);
  * every score matrix is 231x50 (all chemistry columns x all 50 targets) and candidate rows are ALWAYS derived
    from a feature NAME via FEATURE_COLS.index(name).  _guard_matrix() refuses a matrix whose row count is not
    231, so the old 219-row candidate space cannot be indexed with 231-space positions again.

CATEGORIES.  single_compound (the strict universe) / element_or_index (iron, protein.g.L., betaglucan.mg.L. —
v6_common.NON_SINGLE_COMPOUND reclassifies three features that q2_chem_meta.json still tags single_compound) /
physical_parameter (7) / derived_sum (5).  The strict Top-3 board contains single_compound only; elements,
physical parameters and derived sums go to the extended board.  Expected strict size is 216; if the measured
size differs the run reports the size AND the reason instead of forcing 216.

METHODS (unchanged, no T/W dual track): total_spearman, within_style_spearman, graph_lowrank, consensus
(mean of the three within-dimension percentile ranks over the board's own candidate universe).

STABILITY.  Per repeat, 500 style-stratified (tasting_category_fine) resamples of the 200 registered train rows,
each style resampled with replacement to its own size; every replicate REDOES median imputation, the Spearman
graph at tau=0.5, the graph low-rank regression (rank 6, lambda 1, gamma 0.1, 25 ALS sweeps), the within-style
rank residualisation and all three ingredient scores.  pi = selection frequency,
pi_mc_se = sqrt(pi(1-pi)/reps).

DIRECTION STABILITY (v6 §3, replaces the superseded rule).  The reference is the DIRECTION of the point-estimate
total Spearman on the full 200-row training set (`point_direction`).  For every (compound, dimension) cell the
replicates are counted as positive (rho > ZERO_TOL), negative (rho < -ZERO_TOL), zero (|rho| <= ZERO_TOL) or
invalid (non-finite), with ZERO_TOL = 1e-12 PRE-DECLARED below and echoed into every artefact:

    p_positive    = n_positive / valid      p_negative = n_negative / valid
    sign_stability= (replicates agreeing with point_direction) / valid
    valid         = reps - n_invalid

A point estimate that is exactly zero or not computable is `direction-undetermined`: it is NEVER folded into the
negative direction, and 1 - p_positive is never reported as a negative frequency.  `p_positive_legacy` keeps the
superseded rule ((rho > 0) / reps) as a control column so the old values can be reproduced and compared; it does
not enter the ranking, which stays pi first, then the point-estimate score, then the fixed feature name.

RANKING.  pi first, then the point-estimate score, then the fixed feature name (Unicode order); the module
alternative (rank 4..10 inside the same reference module) is always reported next to the pick, so an unstable
third place is never hidden.

WHAT THIS IS NOT.  6.csv is a table shipped with the same attachment: the aligned rank correlation is
SAME-SOURCE corroboration, not independent external validation.  Stability/consistency is not accuracy.  No
causal claim is made.  6.csv never enters the Top-3 selection (it is read only after the boards are fixed).

Run:
    python src/q2_fix.py --repeat all            # repeats 0,1,2 in one process (default)
    python src/q2_fix.py --repeat 1 --reps 200   # one repeat, reduced bootstrap (recorded truthfully)

Outputs land in $MODELING_EXPERIMENT_DIR when the runner sets it, otherwise in
state/devrun/v6/q2/repeat{0,1,2}/ with a copy of the primary repeat at state/devrun/v6/q2/.
Per repeat directory:
    sets.json                        50 dimensions x 4 methods x 3 compounds (200 rows)
    strict_top3.csv                  delivered consensus Top-3 with the sign-count columns (150 rows)
    strict_top3_by_method.csv        the same columns + `method` (600 rows)
    extended_top3.csv                same, extended board (elements / physical parameters / derived sums)
    extended_top3_by_method.csv      same, all four methods
    candidate_scores.csv             231 candidates x 50 dimensions, point estimates + pi
    bootstrap_pi.csv                 every replicate's Top-3 (strict): 500 x 50 x 4 x 3 = 300000 rows
    bootstrap_pi_extended.csv        the same for the extended board
    sign_counts.csv                  all 231 x 50 cells: point rho/direction + pos/neg/zero/invalid counts
    strict_lowpi_sign_status.csv     the strict consensus rows with pi < 0.5, with status and substitutes
    sign_stability_summary.json      definition, tolerance, seeds, reps, denominators, legacy reproduction
    metrics.json, outputs.json
Every bootstrap replicate is streamed to bootstrap_pi.csv (strict) and bootstrap_pi_extended.csv (extended),
so each pi in the tables is reconstructible from files alone.  The SIGN counts are NOT in those files (the
superseded run never stored per-replicate signs), which is why this script recomputes them from the fixed
inputs; sign_counts.csv then makes every new ratio reconstructible from files as well.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
PROJECT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import v6_common as C  # frozen shared interfaces (safe to import before the contract shim)


# =====================================================================================================
# contract channel
# =====================================================================================================
def install_contract_shim(project: Path) -> dict:
    """Exercise v6_common.emit_metrics / emit_output through the real contract when it exists.

    Outside the runner modeling_contract is absent, so q_common/q1_lib/q2_lib would not even import.  The shim
    registers a stand-in module that writes the same two artefacts (metrics.json, outputs.json) that the runner
    writes, into the directory held in ``state['directory']``.  Nothing is faked: the payloads are the real ones
    handed to the frozen channel, and the shim mode is recorded in outputs.json.
    """
    try:
        import modeling_contract  # noqa: F401
        return {"mode": "runner-contract", "state": None}
    except ImportError:
        pass

    module = types.ModuleType("modeling_contract")
    state = {"directory": project, "outputs": {}}

    def _target_dir() -> Path:
        directory = Path(state["directory"])
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def seed():
        return None  # this script takes its seeds from v6_common.SEEDS, not from the runner

    def emit_metrics(metrics: dict) -> None:
        C.write_json(_target_dir() / "metrics.json", metrics)

    def emit_output(name: str, value) -> None:
        state["outputs"][str(name)] = value
        C.write_json(_target_dir() / "outputs.json", state["outputs"])

    def emit_predictions(frame) -> None:
        raise RuntimeError("Q2 delivers a candidate ranking, not row predictions")

    def save_figure(figure, name: str):
        target = _target_dir() / "figures" / (str(name) + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(target, dpi=150, bbox_inches="tight")
        return {"path": str(target), "name": str(name)}

    def experiment_dir() -> Path:
        return _target_dir()

    def project_dir() -> Path:
        return project

    def dataset_path():
        return None

    def split_paths() -> dict:
        return {}

    def dependency_path(rel):
        path = Path(rel)
        full = path if path.is_absolute() else project / path
        if not full.exists():
            raise FileNotFoundError(f"dependency not found: {full}")
        return full

    module.seed = seed
    module.emit_metrics = emit_metrics
    module.emit_output = emit_output
    module.emit_predictions = emit_predictions
    module.save_figure = save_figure
    module.experiment_dir = experiment_dir
    module.project_dir = project_dir
    module.dataset_path = dataset_path
    module.split_paths = split_paths
    module.dependency_path = dependency_path
    sys.modules["modeling_contract"] = module
    return {"mode": "local-shim", "state": state}


CONTRACT = install_contract_shim(PROJECT)

# the modules below import modeling_contract (through q_common), so they must come after the shim
import q_common as QC  # noqa: E402
import q1_lib as L  # noqa: E402
import q2_lib as QL  # noqa: E402  (only its verified helpers: midranks, style basis, residualise, column
#                                correlation, jaccard, module components, label normalisation)
from target_columns import FEATURE_COLS, TARGET_COLS  # noqa: E402

# NOTE: q2_lib.ingredient_scores / percentile_block / topk_* / external_corroboration are deliberately NOT
# used: they live in the 219-row COMPOUND_CANDIDATES space while their lookups use 231-space positions
# (the double-index bug), and the external alignment is positional on the sensory columns.

# =====================================================================================================
# constants
# =====================================================================================================
TRAIN_CSV = PROJECT / "data/splits/SPLIT-0001/train.csv"          # 200 registered train rows (Q2's only rows)
CLEAN_CSV = PROJECT / "data/clean/q1_mapped.csv"
CHEM_META = PROJECT / "data/clean/q2_chem_meta.json"
EXTERNAL_CSV = PROJECT / "data/raw/imported/a55004fb0390299a-6.csv"
ALIGN_CSV = PROJECT / "MathorCup_A_独立审查与重跑方案/sensory_name_alignment.csv"

METHODS = ("total_spearman", "within_style_spearman", "graph_lowrank", "consensus")
BASE_METHODS = METHODS[:3]
K = 3
TAU = 0.5
GRAPH_SETTINGS = {"rank": 6, "lambda": 1.0, "gamma": 0.1, "nIter": 25}
N_BOOTSTRAP = 500
N_DIMENSIONS = len(C.TARGETS_50)
N_FEATURES = len(FEATURE_COLS)
STYLE_COL = C.STYLE_COL

# pi / sign thresholds only LABEL stability in the delivered tables; they are never correctness thresholds
PI_STABLE = 0.5
SIGN_STABLE = 0.9
#: PRE-DECLARED numerical tolerance, in correlation units, for the sign decision of a replicate or of the
#: point estimate.  Fixed here, BEFORE any replicate is drawn, and echoed into sign_stability_summary.json,
#: sign_counts.csv, outputs.json and the tables; it is not tuned to the observed values.  |rho| <= ZERO_TOL
#: is recorded as `zero` and never folded into positive or negative.
ZERO_TOL = 1e-12
#: bucket / status labels shared by the counters, the tables and the self-test
BUCKET_POSITIVE = "positive"
BUCKET_NEGATIVE = "negative"
BUCKET_ZERO = "zero"
BUCKET_INVALID = "invalid"
BUCKET_KEYS = (BUCKET_POSITIVE, BUCKET_NEGATIVE, BUCKET_ZERO, BUCKET_INVALID)
DIRECTION_POSITIVE = "positive"
DIRECTION_NEGATIVE = "negative"
DIRECTION_UNDETERMINED = "direction-undetermined"
#: written in alternative_rank4 when the reference module has fewer than 4 members (no same-module 4th pick)
NO_ALTERNATIVE = "none"

FILE_SETS = "sets.json"
FILE_STRICT = "strict_top3.csv"
FILE_STRICT_METHODS = "strict_top3_by_method.csv"
FILE_EXTENDED = "extended_top3.csv"
FILE_EXTENDED_METHODS = "extended_top3_by_method.csv"
FILE_CANDIDATES = "candidate_scores.csv"
FILE_BOOT = "bootstrap_pi.csv"
FILE_BOOT_EXT = "bootstrap_pi_extended.csv"
FILE_SIGN_COUNTS = "sign_counts.csv"
FILE_LOWPI = "strict_lowpi_sign_status.csv"
FILE_SIGN_SUMMARY = "sign_stability_summary.json"
FILE_METRICS = "metrics.json"
FILE_OUTPUTS = "outputs.json"

# The requested table schema carries no method field, so the exact columns are the DELIVERED consensus
# Top-3 (150 rows = 50 dimensions x 3 ranks).  The four-method evidence goes to the *_by_method.csv twins,
# which keep the same columns in the same order and append `method` as the last column.
# `direction` (the superseded binary label, which silently pushed zeros into "negative") is replaced by the
# tri-state `point_direction` + `direction_status`; the counts make (p_positive, p_negative, sign_stability)
# reconstructible from the table itself.
TOP3_HEADER = ["dimension", "rank", "compound", "kind", "score", "pi", "pi_mc_se", "sign_stability",
               "direction", "p_positive", "p_negative", "p_positive_legacy", "n_positive", "n_negative",
               "n_zero", "n_invalid", "point_direction", "direction_status", "module_id",
               "alternative_rank4", "evidence_status"]
TOP3_HEADER_METHOD = TOP3_HEADER + ["method"]
BOOT_HEADER = ["bootstrap_id", "seed", "dimension", "method", "rank", "compound"]
CANDIDATE_HEADER = ["dimension", "compound", "kind", "rho_total", "rho_within", "beta_graphlowrank",
                    "score", "pi"]
SIGN_COUNTS_HEADER = ["dimension", "compound", "kind", "rho_point_signed", "point_direction",
                      "n_positive", "n_negative", "n_zero", "n_invalid", "valid", "p_positive",
                      "p_negative", "p_positive_legacy", "sign_stability", "direction_status"]
LOWPI_HEADER = ["dimension", "rank", "compound", "kind", "pi", "pi_mc_se", "point_direction",
                "p_positive", "p_negative", "p_positive_legacy", "n_positive", "n_negative", "n_zero",
                "n_invalid", "sign_stability", "direction_status", "evidence_status", "module_id",
                "module_size", "alternative_rank4", "module_rank4_to_10", "same_module_alternative_exists",
                "global_fallback"]

# ----------------------------------------------------------------------------------------------------
# explicit sensory-header dictionary: normalised 6.csv header -> frozen target name.
# Keys are produced by q2_lib.normalise_label (lower case, alphanumerics only), which also removes the
# embedded CRLF of the last header ("Overall appreciation\r\n(Trained panel)") without inventing an order.
# The comments quote the header exactly as it appears in 6.csv.
# ----------------------------------------------------------------------------------------------------
SENSORY_HEADER_TO_TARGET = {
    'maltaromaoverall': 'A_malt_all',            # Malt aroma - overall
    'maltaromagrain': 'A_malt_grain',            # Malt aroma - grain
    'maltaromabread': 'A_malt_bread',            # Malt aroma - bread
    'maltaromacaramel': 'A_malt_cara',           # Malt aroma - caramel
    'maltaromasmoked': 'A_malt_burn',            # Malt aroma - smoked
    'hopsaromaoverall': 'A_hops_all',            # Hops aroma - overall
    'hopsaromacitrus': 'A_hops_citrus',          # Hops aroma - citrus
    'hopsaromatropicalfruit': 'A_hops_tropical',  # Hops aroma - tropical fruit
    'hopsaromagrassy': 'A_hops_noble',           # Hops aroma - grassy
    'hopsaromawoody': 'A_hops_woody',            # Hops aroma - woody
    'estersaromaoverall': 'A_esters_all',        # Esters aroma - overall
    'estersaromanailpolish': 'A_esters_ethac',   # Esters aroma - nail polish
    'estersaromabanana': 'A_esters_isoaa',       # Esters aroma - banana
    'estersaromafloral': 'A_esters_flower',      # Esters aroma - floral
    'estersaromafruity': 'A_esters_fruity',      # Esters aroma - fruity
    'malttasteoverall': 'F_malt_all',            # Malt taste - overall
    'malttastegrain': 'F_malt_grain',            # Malt taste - grain
    'malttastebread': 'F_malt_bread',            # Malt taste - bread
    'malttastecaramel': 'F_malt_cara',           # Malt taste - caramel
    'malttastesmoked': 'F_malt_burn',            # Malt taste - smoked
    'hopstasteoverall': 'F_hops_all',            # Hops taste - overall
    'hopstastecitrus': 'F_hops_citrus',          # Hops taste - citrus
    'hopstastetropicalfruit': 'F_hops_tropical',  # Hops taste - tropical fruit
    'hopstastegrassy': 'F_hops_noble',           # Hops taste - grassy
    'hopstastewoody': 'F_hops_woody',            # Hops taste - woody
    'esterstasteoverall': 'F_esters_all',        # Esters taste - overall
    'esterstastenailpolish': 'F_esters_ethac',   # Esters taste - nail polish
    'esterstastebanana': 'F_esters_isoaa',       # Esters taste - banana
    'esterstastefloral': 'F_esters_flower',      # Esters taste - floral
    'esterstastefruity': 'F_esters_fruity',      # Esters taste - fruity
    'acidity': 'acidity',                        # Acidity
    'bitterness': 'bitternes',                   # Bitterness
    'sweetness': 'sweetness',                    # Sweetness
    '4vinylguaiacol': 'X4vg',                    # 4-vinyl guaiacol
    'diacetyl': 'diacetyl',                      # Diacetyl
    'dimethylsulfide': 'dms',                    # Dimethyl sulfide
    'metallic': 'metallic',                      # Metallic
    'stalehops': 'stale_hops',                   # Stale hops
    'trans2nonenal': 't2n',                      # Trans-2-nonenal
    'orange': 'orange',                          # Orange
    'coriander': 'coriander',                    # Coriander
    'clove': 'clove',                            # Clove
    'lacticacid': 'lactic',                      # Lactic acid
    'aceticacid': 'acetic',                      # Acetic acid
    'barnyard': 'barnyard',                      # Barnyard
    'alcohol': 'alcohol',                        # Alcohol
    'carbonation': 'co2',                        # Carbonation
    'aftertaste': 'aftertaste',                  # Aftertaste
    'body': 'body',                              # Body
    'overallappreciationtrainedpanel': 'overall',  # Overall appreciation\r\n(Trained panel)
}
if any(QL.normalise_label(key) != key for key in SENSORY_HEADER_TO_TARGET):
    raise RuntimeError("SENSORY_HEADER_TO_TARGET keys must already be normalised")


# =====================================================================================================
# small helpers
# =====================================================================================================
def fmt(value) -> str:
    """Shortest round-trip text for a float, so a CSV cell reconstructs the exact number."""
    return repr(float(value))


def write_csv(path: Path, header: list, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def jsonable(value):
    """Convert numpy scalars/arrays and refuse non-finite floats (a NaN must never reach metrics/outputs)."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError(f"non-finite float in an output payload: {value!r}")
        return value
    return value


def assert_finite(metrics: dict) -> None:
    for key, value in metrics.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise RuntimeError(f"metric {key!r} is not finite")


def _guard_matrix(matrix: np.ndarray, name: str) -> np.ndarray:
    """Refuse any score matrix that is not 231 x 50: the old bug was a 219-row matrix indexed in 231 space."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != (N_FEATURES, N_DIMENSIONS):
        raise RuntimeError(
            f"{name}: shape {matrix.shape} != ({N_FEATURES}, {N_DIMENSIONS}); a candidate-space matrix must "
            f"never be indexed with feature-space positions")
    if not np.isfinite(matrix).all():
        raise RuntimeError(f"{name}: non-finite score")
    return matrix


# =====================================================================================================
# direction stability (v6 §3) — ONE definition, used by the bootstrap, by the tables and by the self-test
# =====================================================================================================
def sign_buckets(replicate_signed, zero_tol: float = ZERO_TOL) -> dict:
    """Classify signed correlations into positive / negative / zero(near-zero) / invalid (+ legacy rule).

    This is the only place the sign rules live, so the counters, the delivered ratios and the self-test
    cannot drift apart.  Every returned value is a boolean mask with the input's shape.
    """
    values = np.asarray(replicate_signed, dtype=float)
    finite = np.isfinite(values)
    return {
        BUCKET_POSITIVE: finite & (values > zero_tol),
        BUCKET_NEGATIVE: finite & (values < -zero_tol),
        BUCKET_ZERO: finite & (np.abs(values) <= zero_tol),
        BUCKET_INVALID: ~finite,
        # superseded rule: (rho > 0); NaN and exact zeros were both counted as "not positive"
        "legacyPositive": values > 0,
    }


def point_direction_of(value: float, zero_tol: float = ZERO_TOL) -> str:
    """Direction of the point estimate; zero / non-finite -> direction-undetermined (never negative)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DIRECTION_UNDETERMINED
    if not math.isfinite(number) or abs(number) <= zero_tol:
        return DIRECTION_UNDETERMINED
    return DIRECTION_POSITIVE if number > 0.0 else DIRECTION_NEGATIVE


def sign_fields(n_positive: int, n_negative: int, n_zero: int, n_invalid: int, legacy_positive: int,
                reps: int, point_value: float, zero_tol: float = ZERO_TOL) -> dict:
    """The delivered ratios and labels from integer counts.  THE ONE PLACE the ratios are computed."""
    counts = {BUCKET_POSITIVE: int(n_positive), BUCKET_NEGATIVE: int(n_negative),
              BUCKET_ZERO: int(n_zero), BUCKET_INVALID: int(n_invalid)}
    reps = int(reps)
    valid = reps - counts[BUCKET_INVALID]
    if valid < 0 or sum(counts.values()) != reps:
        raise RuntimeError(f"sign counts do not partition the {reps} replicates: {counts}")
    direction = point_direction_of(point_value, zero_tol)
    if direction == DIRECTION_POSITIVE:
        aligned = counts[BUCKET_POSITIVE]
    elif direction == DIRECTION_NEGATIVE:
        aligned = counts[BUCKET_NEGATIVE]
    else:
        aligned = 0
    def ratio(value: int, denominator: int) -> float:
        return float(value) / float(denominator) if denominator > 0 else 0.0
    return {
        "n_positive": counts[BUCKET_POSITIVE], "n_negative": counts[BUCKET_NEGATIVE],
        "n_zero": counts[BUCKET_ZERO], "n_invalid": counts[BUCKET_INVALID],
        "valid": int(valid), "reps": reps, "aligned": int(aligned),
        "p_positive": ratio(counts[BUCKET_POSITIVE], valid),
        "p_negative": ratio(counts[BUCKET_NEGATIVE], valid),
        "p_positive_legacy": ratio(int(legacy_positive), reps),
        "sign_stability": ratio(aligned, valid),
        "point_direction": direction,
        "direction_status": direction,
        "direction_undetermined": direction == DIRECTION_UNDETERMINED,
    }


def sign_summary(point_value: float, replicate_signed, zero_tol: float = ZERO_TOL) -> dict:
    """`sign_fields` on an explicit replicate vector (used by the self-test and by any row-level recompute)."""
    values = np.asarray(replicate_signed, dtype=float).ravel()
    buckets = sign_buckets(values, zero_tol)
    return sign_fields(int(buckets[BUCKET_POSITIVE].sum()), int(buckets[BUCKET_NEGATIVE].sum()),
                      int(buckets[BUCKET_ZERO].sum()), int(buckets[BUCKET_INVALID].sum()),
                      int(buckets["legacyPositive"].sum()), int(values.size), point_value, zero_tol)


def sign_self_test(zero_tol: float = ZERO_TOL) -> dict:
    """Four hand-built cases (plus two edge cases) that pin the definition before any data is touched.

    stable positive -> sign_stability 1; stable negative -> 1 (the superseded rule said 0 here);
    alternating signs -> 0.5; all zero and all invalid -> direction-undetermined with an explicit status.
    """
    reps = 20
    cases = []

    def add(name, point, values, expect):
        summary = sign_summary(point, values, zero_tol)
        cases.append({"case": name, "pointEstimate": float(point) if math.isfinite(float(point)) else "nan",
                      "requests": expect, **{key: summary[key] for key in
                                             ("n_positive", "n_negative", "n_zero", "n_invalid", "valid",
                                              "p_positive", "p_negative", "p_positive_legacy",
                                              "sign_stability", "point_direction", "direction_status")}})

    ascending = np.linspace(0.30, 0.52, reps)
    add("stable-positive", 0.42, ascending, {"sign_stability": 1.0, "direction_status": DIRECTION_POSITIVE})
    add("stable-negative", -0.42, -ascending, {"sign_stability": 1.0, "direction_status": DIRECTION_NEGATIVE})
    add("alternating-signs", 0.05, np.array([0.25, -0.25] * (reps // 2)),
        {"sign_stability": 0.5, "direction_status": DIRECTION_POSITIVE})
    add("all-zero", 0.0, np.zeros(reps),
        {"sign_stability": 0.0, "n_zero": reps, "direction_status": DIRECTION_UNDETERMINED})
    add("all-invalid", float("nan"), np.full(reps, np.nan),
        {"sign_stability": 0.0, "n_invalid": reps, "valid": 0, "direction_status": DIRECTION_UNDETERMINED})
    add("near-zero-tolerance", 1e-15, np.array([1e-13, -1e-13] * (reps // 2)),
        {"sign_stability": 0.0, "n_zero": reps, "direction_status": DIRECTION_UNDETERMINED})

    checks = []
    def check(name, condition, detail):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    by_case = {case["case"]: case for case in cases}
    check("stable-positive.sign_stability==1", by_case["stable-positive"]["sign_stability"] == 1.0,
          by_case["stable-positive"]["sign_stability"])
    check("stable-negative.sign_stability==1", by_case["stable-negative"]["sign_stability"] == 1.0,
          by_case["stable-negative"]["sign_stability"])
    check("stable-negative.legacy==0 (the superseded bug)",
          by_case["stable-negative"]["p_positive_legacy"] == 0.0,
          by_case["stable-negative"]["p_positive_legacy"])
    check("alternating.sign_stability==0.5", abs(by_case["alternating-signs"]["sign_stability"] - 0.5) <= 1e-12,
          by_case["alternating-signs"]["sign_stability"])
    check("all-zero.status==direction-undetermined",
          by_case["all-zero"]["direction_status"] == DIRECTION_UNDETERMINED,
          by_case["all-zero"]["direction_status"])
    check("all-zero.n_zero==reps", by_case["all-zero"]["n_zero"] == reps, by_case["all-zero"]["n_zero"])
    check("all-zero.sign_stability==0", by_case["all-zero"]["sign_stability"] == 0.0,
          by_case["all-zero"]["sign_stability"])
    check("all-invalid.n_invalid==reps and valid==0",
          by_case["all-invalid"]["n_invalid"] == reps and by_case["all-invalid"]["valid"] == 0,
          [by_case["all-invalid"]["n_invalid"], by_case["all-invalid"]["valid"]])
    check("all-invalid.status==direction-undetermined",
          by_case["all-invalid"]["direction_status"] == DIRECTION_UNDETERMINED,
          by_case["all-invalid"]["direction_status"])
    check("near-zero.all_bucketed_as_zero", by_case["near-zero-tolerance"]["n_zero"] == reps,
          by_case["near-zero-tolerance"]["n_zero"])
    check("alternating.p_positive==p_negative==0.5",
          abs(by_case["alternating-signs"]["p_positive"] - 0.5) <= 1e-12
          and abs(by_case["alternating-signs"]["p_negative"] - 0.5) <= 1e-12,
          [by_case["alternating-signs"]["p_positive"], by_case["alternating-signs"]["p_negative"]])
    passed = all(record["passed"] for record in checks)
    return {"zeroTolerance": float(zero_tol), "reps": reps, "cases": cases, "checks": checks,
            "passed": passed,
            "note": "hand-built vectors only; the run aborts if any check fails, so the definition is fixed "
                    "before any real replicate is drawn"}


# =====================================================================================================
# data
# =====================================================================================================
def load_train() -> pd.DataFrame:
    """The 200 registered SPLIT-0001 train rows, validated through the frozen v6_common interfaces."""
    frame = C.load_frame(TRAIN_CSV)
    columns = C.chem_columns(frame)                      # asserts 231 chemical features
    targets = C.all_targets(frame)                       # asserts the 50 frozen targets
    C.style_of(frame)                                    # asserts the style column exists
    if len(frame) != 200:
        raise RuntimeError(f"expected the 200 SPLIT-0001 train rows, got {len(frame)}")
    if list(targets) != list(C.TARGETS_50):
        raise RuntimeError("v6_common.TARGETS_50 order disagrees with the table")
    if list(TARGET_COLS) != list(C.TARGETS_50):
        raise RuntimeError("src/target_columns.py TARGET_COLS order differs from v6_common.TARGETS_50; "
                           "the two frozen orders must be identical before any matrix is built")
    if [column[len(C.CHEM_PREFIX):] for column in columns] != list(FEATURE_COLS):
        raise RuntimeError("table chem columns disagree with target_columns.FEATURE_COLS order")
    return frame.reset_index(drop=True)


# =====================================================================================================
# categories
# =====================================================================================================
def build_categories(meta: dict) -> dict:
    """single_compound / element_or_index / physical_parameter / derived_sum, asserted to partition 231."""
    names = [record["name"] for record in meta["features"]]
    if names != list(FEATURE_COLS):
        raise RuntimeError("q2_chem_meta.json feature order differs from target_columns.FEATURE_COLS")
    kind = {record["name"]: record["kind"] for record in meta["features"]}
    unknown = sorted(set(kind.values()) - {"single_compound", "physical_parameter", "derived_sum"})
    if unknown:
        raise RuntimeError(f"unexpected meta kinds: {unknown}")

    element = list(C.NON_SINGLE_COMPOUND["element_or_index"])
    physical = list(C.NON_SINGLE_COMPOUND["physical_parameter"])
    derived = list(C.NON_SINGLE_COMPOUND["derived_sum"])
    for group, expected in (("element_or_index", element), ("physical_parameter", physical),
                            ("derived_sum", derived)):
        if len(expected) != len(set(expected)):
            raise RuntimeError(f"{group} list has duplicates")
        for name in expected:
            if name not in kind:
                raise RuntimeError(f"{group} member {name!r} is not a chemistry feature")
            if group == "physical_parameter" and kind[name] != "physical_parameter":
                raise RuntimeError(f"{name!r} is listed as a physical parameter but meta says {kind[name]!r}")
            if group == "derived_sum" and kind[name] != "derived_sum":
                raise RuntimeError(f"{name!r} is listed as a derived sum but meta says {kind[name]!r}")
            if group == "element_or_index" and kind[name] != "single_compound":
                raise RuntimeError(f"{name!r} is an element/index feature but meta says {kind[name]!r}")
    reclassified = [name for name in element if kind[name] == "single_compound"]

    single = [name for name in FEATURE_COLS if kind[name] == "single_compound" and name not in element]
    expected_single = 216
    meta_single = sum(1 for name in FEATURE_COLS if kind[name] == "single_compound")
    if len(single) != expected_single:
        reason = (f"meta tags {meta_single} single_compound features; removing the {len(element)} "
                  f"element_or_index members leaves {len(single)} (expected {expected_single})")
    else:
        reason = (f"meta tags {meta_single} single_compound features; the {len(element)} element_or_index "
                  f"members (iron, protein.g.L., betaglucan.mg.L.) are reclassified out of the strict "
                  f"universe, {meta_single} - {len(element)} = {len(single)}")
    categories = {"single_compound": single, "element_or_index": element,
                  "physical_parameter": physical, "derived_sum": derived}
    universe = [name for group in categories.values() for name in group]
    if sorted(universe) != sorted(FEATURE_COLS) or len(universe) != N_FEATURES:
        raise RuntimeError("the category lists do not partition the 231 chemistry features exactly once")
    return {
        "groups": categories,
        "strictNames": single,
        "extendedNames": [name for name in FEATURE_COLS if name not in set(single)],
        "kindOf": {name: group for group, members in categories.items() for name in members},
        "counts": {group: len(members) for group, members in categories.items()},
        "strictSize": len(single),
        "strictSizeExpected": expected_single,
        "strictSizeMatchesExpected": bool(len(single) == expected_single),
        "metaSingleCompoundCount": meta_single,
        "metaReclassified": reclassified,
        "reason": reason,
    }


# =====================================================================================================
# mapping (both sides) — name only
# =====================================================================================================
def build_chemistry_mapping(meta: dict, external: pd.DataFrame) -> dict:
    """6.csv first column -> feature name through corrLabel (then name); one-to-one, no omissions."""
    features = meta["features"]
    names = [record["name"] for record in features]
    label_map: dict = {}
    for record in features:
        label_map.setdefault(QL.normalise_label(record["corrLabel"]), []).append(record["name"])
    name_map = {QL.normalise_label(name): [name] for name in names}
    ambiguous_labels = {key: value for key, value in label_map.items() if len(value) > 1}

    labels = [str(value) for value in external.iloc[:, 0].tolist()]
    normalised = [QL.normalise_label(label) for label in labels]
    if len(set(normalised)) != len(normalised):
        raise RuntimeError("6.csv has duplicate compound rows after normalisation")

    table, unmatched, ambiguous = [], [], []
    for label, key in zip(labels, normalised):
        candidates = sorted(set(label_map.get(key, [])) | set(name_map.get(key, [])))
        if len(candidates) == 1:
            position = len(table)
            name = candidates[0]
            table.append({"row": position, "label": label, "feature": name,
                          "kind": None, "corrIndex": None, "position": FEATURE_COLS.index(name)})
        elif len(candidates) > 1:
            ambiguous.append({"label": label, "candidates": candidates})
        else:
            unmatched.append({"label": label, "reason": "no corrLabel and no feature name matches"})
    if unmatched or ambiguous:
        raise RuntimeError(
            f"6.csv chemistry rows are not one-to-one: unmatched={unmatched} ambiguous={ambiguous}; "
            f"a partial row set would silently change the comparison denominator")
    matched_names = [record["feature"] for record in table]
    if len(set(matched_names)) != len(matched_names):
        raise RuntimeError("two 6.csv rows map to the same chemistry feature")

    kind = {record["name"]: record["kind"] for record in features}
    corr = {record["name"]: record["corrIndex"] for record in features}
    for record in table:
        record["corrIndex"] = int(corr[record["feature"]])
        record["kind"] = kind[record["feature"]]
    if any(record["corrIndex"] != record["position"] for record in table):
        raise RuntimeError("meta corrIndex disagrees with the FEATURE_COLS position; name and index disagree")

    return {
        "source": "6.csv column 1 (display name) matched to data/clean/q2_chem_meta.json corrLabel, then "
                  "name, after q2_lib.normalise_label (lower case, alphanumerics only)",
        "n": len(labels), "matched": len(table), "nUnmatched": len(unmatched), "nAmbiguous": len(ambiguous),
        "unmatched": unmatched, "ambiguous": ambiguous, "oneToOne": True,
        "duplicateNormalisedLabels": [{"label": key, "features": value}
                                      for key, value in sorted(ambiguous_labels.items())],
        "duplicateNormalisedLabelNote":
            "E-alpha-ionone and E-beta-ionone both normalise to 'eionone' (Greek letters are stripped). "
            "No 6.csv row uses that label, so 44/44 rows resolve; if one ever did, the run aborts instead of "
            "picking a feature by position.",
        "table": table,
    }


def build_sensory_mapping(external: pd.DataFrame, alignment_path: Path) -> dict:
    """6.csv headers -> frozen target names through the explicit dictionary, three-way cross-checked."""
    alignment = pd.read_csv(alignment_path)
    if list(alignment.columns) != ["external_header", "target"]:
        raise RuntimeError(f"{alignment_path} must have columns ['external_header', 'target']")
    if len(alignment) != N_DIMENSIONS:
        raise RuntimeError(f"alignment table has {len(alignment)} rows, expected {N_DIMENSIONS}")
    align_map = {QL.normalise_label(header): str(target)
                 for header, target in zip(alignment["external_header"], alignment["target"])}
    if len(align_map) != len(alignment):
        raise RuntimeError("alignment table has duplicate headers after normalisation")
    if len(set(align_map.values())) != len(align_map):
        raise RuntimeError("alignment table maps two headers to one target")
    if set(align_map.values()) != set(C.TARGETS_50):
        raise RuntimeError("alignment table targets differ from v6_common.TARGETS_50")
    if align_map != SENSORY_HEADER_TO_TARGET:
        differing = {key: (align_map.get(key), SENSORY_HEADER_TO_TARGET.get(key))
                     for key in set(align_map) | set(SENSORY_HEADER_TO_TARGET)
                     if align_map.get(key) != SENSORY_HEADER_TO_TARGET.get(key)}
        raise RuntimeError(f"the literal dictionary and {alignment_path} disagree: {differing}")

    headers = [str(value) for value in external.columns[1:]]
    if len(headers) != N_DIMENSIONS:
        raise RuntimeError(f"6.csv carries {len(headers)} sensory columns, expected {N_DIMENSIONS}")
    norms = [QL.normalise_label(header) for header in headers]
    if len(set(norms)) != len(norms):
        raise RuntimeError("6.csv has duplicate sensory headers after normalisation")
    missing = [header for header, key in zip(headers, norms) if key not in SENSORY_HEADER_TO_TARGET]
    unused = sorted(set(SENSORY_HEADER_TO_TARGET) - set(norms))
    if missing or unused:
        raise RuntimeError(f"6.csv headers do not cover the dictionary: missing={missing} unused={unused}")
    targets = [SENSORY_HEADER_TO_TARGET[key] for key in norms]
    if len(set(targets)) != len(targets) or set(targets) != set(C.TARGETS_50):
        raise RuntimeError("6.csv sensory columns are not one-to-one onto the 50 targets")

    column_for_target = {target: index for index, target in enumerate(targets)}
    positional_mismatch = [{"column": index + 1, "header": headers[index],
                            "targetIfPositional": C.TARGETS_50[index],
                            "targetIfNamed": targets[index]}
                           for index in range(len(targets)) if targets[index] != C.TARGETS_50[index]]
    return {
        "source": "explicit literal 50-entry dictionary, cross-checked against "
                  "MathorCup_A_独立审查与重跑方案/sensory_name_alignment.csv and the 6.csv header set",
        "n": len(headers), "matched": len(headers), "oneToOne": True, "unmatched": [], "ambiguous": [],
        "positionalMismatch": positional_mismatch,
        "positionalMismatchCount": len(positional_mismatch),
        "columnsForTargets": [column_for_target[target] for target in C.TARGETS_50],
        "table": [{"externalHeader": header, "normalised": key, "target": target,
                   "externalColumnIndex": index + 1, "targetPosition": C.TARGETS_50.index(target)}
                  for index, (header, key, target) in enumerate(zip(headers, norms, targets))],
    }


def build_mapping(meta: dict) -> dict:
    external = pd.read_csv(EXTERNAL_CSV)
    chemistry = build_chemistry_mapping(meta, external)
    sensory = build_sensory_mapping(external, ALIGN_CSV)
    assertions = [
        {"id": "M1", "description": "every 6.csv chemistry row maps to exactly one feature by name",
         "passed": chemistry["oneToOne"] and chemistry["nUnmatched"] == 0 and chemistry["nAmbiguous"] == 0,
         "detail": f"{chemistry['matched']}/{chemistry['n']} matched"},
        {"id": "M2", "description": "no two 6.csv rows map to the same feature",
         "passed": True, "detail": f"{chemistry['matched']} distinct features"},
        {"id": "M3", "description": "meta corrIndex equals the FEATURE_COLS position for every matched row",
         "passed": True, "detail": "name and index spaces agree"},
        {"id": "M4", "description": "every 6.csv sensory column maps to exactly one of the 50 targets",
         "passed": sensory["oneToOne"], "detail": f"{sensory['matched']}/{sensory['n']} matched"},
        {"id": "M5", "description": "literal dictionary == alignment table == 6.csv header set",
         "passed": True, "detail": "three independent sources agree on 50/50"},
        {"id": "M6", "description": "positional reading of the sensory columns is wrong (evidence, not a guess)",
         "passed": sensory["positionalMismatchCount"] > 0,
         "detail": f"{sensory['positionalMismatchCount']} columns differ: " +
                   ", ".join(row["header"] for row in sensory["positionalMismatch"])},
    ]
    failed = [record for record in assertions if not record["passed"]]
    if failed:
        raise RuntimeError(f"mapping assertions failed: {failed}")
    return {"chemistry": chemistry, "sensory": sensory, "assertions": assertions,
            "files": {str(EXTERNAL_CSV.relative_to(PROJECT)): C.sha256_file(EXTERNAL_CSV),
                      str(ALIGN_CSV.relative_to(PROJECT)): C.sha256_file(ALIGN_CSV),
                      str(CHEM_META.relative_to(PROJECT)): C.sha256_file(CHEM_META),
                      str(TRAIN_CSV.relative_to(PROJECT)): C.sha256_file(TRAIN_CSV),
                      str(CLEAN_CSV.relative_to(PROJECT)): C.sha256_file(CLEAN_CSV)}}


# =====================================================================================================
# boards
# =====================================================================================================
def make_board(names: list, label: str) -> dict:
    rows = np.asarray([FEATURE_COLS.index(name) for name in names], dtype=int)
    if rows.size != len(names) or len(set(rows.tolist())) != len(names):
        raise RuntimeError(f"{label} board: name->position mapping is not injective")
    if rows.size == 0 or int(rows.max()) >= N_FEATURES:
        raise RuntimeError(f"{label} board: position outside the 231-feature space")
    name_rank = {name: rank for rank, name in enumerate(sorted(names))}
    return {"label": label, "names": list(names), "rows": rows,
            "nameRank": np.asarray([name_rank[name] for name in names], dtype=int),
            "index": {name: local for local, name in enumerate(names)}, "size": len(names)}


def module_lookup(graph: dict) -> dict:
    """Reference modules = connected components of the point-estimate |W|>0 graph (tau = 0.5)."""
    table = QL.module_table(graph)
    labels = np.asarray(table["labels"], dtype=int)
    if labels.size != N_FEATURES:
        raise RuntimeError(f"module labels cover {labels.size} features, expected {N_FEATURES}")
    sizes = np.bincount(labels)
    per = {}
    for name in FEATURE_COLS:
        position = FEATURE_COLS.index(name)
        per[name] = {"moduleId": int(labels[position]), "moduleSize": int(sizes[labels[position]])}
    return {"count": int(table["count"]), "edgeCount": int(table["edgeCount"]),
            "moduleSizes": [int(value) for value in table["moduleSizes"]], "perCompound": per,
            "largestModuleSize": int(max(int(value) for value in table["moduleSizes"])),
            "largestModuleShare": float(max(int(value) for value in table["moduleSizes"]) / N_FEATURES),
            "partitionBalanced": bool(max(int(value) for value in table["moduleSizes"]) <= N_FEATURES // 3),
            "definition": "connected components of the point-estimate training graph |W| > 0 at tau = 0.5 over "
                          "the 231 chemistry features (200 SPLIT-0001 train rows)", 
            "readingNote": "the partition is UNBALANCED: one component absorbs most features, so the 'rank 4..10 "
                           "inside the same module' substitute pool is nearly the global next-best list for most "
                           "picks. moduleSize is reported next to every alternative so this is visible, not "
                           "hidden."}


def attach_modules(board: dict, modules: dict) -> None:
    groups: dict = {}
    for name in board["names"]:
        groups.setdefault(modules["perCompound"][name]["moduleId"], []).append(name)
    board["byModule"] = groups


# =====================================================================================================
# scores
# =====================================================================================================
def pointscores(frame: pd.DataFrame, tau: float = TAU) -> dict:
    """The three ingredients on the full 231 x 50 matrix (every preprocessing step refit on `frame`)."""
    imputed = L.imputed_blocks(frame, {"train": frame})["train"]
    features = imputed[:, :L.N_FEATURES]
    targets = L.raw_target_matrix(frame)
    signed_total = _guard_matrix(QC.spearman_matrix(features, targets), "signed_total")
    basis = QL.style_basis(frame[STYLE_COL].to_numpy())
    within_signed = _guard_matrix(
        QL.column_correlation(QL.residualise(QL.midranks(features), basis),
                              QL.residualise(QL.midranks(targets), basis)), "within_signed")
    fitted = L.FittedModel(frame, "zscore", GRAPH_SETTINGS["rank"], GRAPH_SETTINGS["lambda"],
                           GRAPH_SETTINGS["gamma"], tau=tau)
    beta = _guard_matrix(np.asarray(fitted.model["beta"])[:L.N_FEATURES, :], "graph_beta")
    return {"signedTotal": signed_total, "total_spearman": np.abs(signed_total),
            "within_signed": within_signed, "within_style_spearman": np.abs(within_signed),
            "graph_lowrank": np.abs(beta), "graph_beta_signed": beta, "graph": fitted.graph}


def board_ranked(scores: dict, board: dict) -> dict:
    """Within-board percentile ranks (the board's own candidate universe) and the consensus mean."""
    rows = board["rows"]
    ranked = {method: QC.percentile_rank(scores[method][rows, :]) for method in BASE_METHODS}
    ranked["consensus"] = (ranked["total_spearman"] + ranked["within_style_spearman"]
                           + ranked["graph_lowrank"]) / 3.0
    for method in METHODS:
        if ranked[method].shape != (board["size"], N_DIMENSIONS):
            raise RuntimeError(f"{board['label']}/{method}: percentile block has the wrong shape")
    return ranked


def order_by_score(ranked: dict, board: dict) -> dict:
    """Top-3 per (method, dimension) by the point-estimate score; ties by the fixed feature name."""
    out = {}
    for method in METHODS:
        matrix = ranked[method]
        out[method] = [np.lexsort((board["nameRank"], -matrix[:, dimension]))[:K].tolist()
                       for dimension in range(N_DIMENSIONS)]
    return out


def order_by_pi(ranked: dict, pi: dict, board: dict) -> dict:
    """Top-3 per (method, dimension): pi first, then the point-estimate score, then the fixed feature name."""
    out = {}
    rows = board["rows"]
    for method in METHODS:
        matrix = ranked[method]
        out[method] = [np.lexsort((board["nameRank"], -matrix[:, dimension],
                                   -pi[method][rows, dimension]))[:K].tolist()
                       for dimension in range(N_DIMENSIONS)]
    return out


def sets_as_names(chosen: dict, board: dict) -> dict:
    return {method: [[board["names"][int(local)] for local in chosen[method][dimension]]
                     for dimension in range(N_DIMENSIONS)] for method in METHODS}


# =====================================================================================================
# bootstrap
# =====================================================================================================
def bootstrap(frame: pd.DataFrame, seed: int, reps: int, boards: dict, paths: dict) -> dict:
    """Style-stratified bootstrap that REDOES every refit; streams the full per-replicate Top-3 to CSV.

    The RNG stream is UNCHANGED from the superseded run (one default_rng(seed + 1000003*21), one resample
    per replicate, the styles in sorted order), so the sign counters added here cannot move the selection
    frequencies pi or any other delivered number.
    """
    styles = frame[STYLE_COL].to_numpy()
    style_order = sorted(set(styles.tolist()))
    groups = [np.nonzero(styles == style)[0] for style in style_order]
    if sum(group.size for group in groups) != len(frame):
        raise RuntimeError("style strata do not cover the training rows")
    rng = np.random.default_rng(int(seed) + 1000003 * 21)

    counts = {method: np.zeros((N_FEATURES, N_DIMENSIONS), dtype=np.int32) for method in METHODS}
    sign = {key: np.zeros((N_FEATURES, N_DIMENSIONS), dtype=np.int32)
            for key in BUCKET_KEYS + ("legacyPositive",)}
    handles = {label: open(path, "w", encoding="utf-8", newline="") for label, path in paths.items()}
    writers = {label: csv.writer(handle, lineterminator="\n") for label, handle in handles.items()}
    for writer in writers.values():
        writer.writerow(BOOT_HEADER)
    rows_written = {label: 0 for label in paths}
    try:
        for replicate in range(int(reps)):
            indices = np.concatenate([group[rng.integers(0, group.size, size=group.size)]
                                      for group in groups])
            sample = frame.iloc[indices].reset_index(drop=True)
            scores = pointscores(sample)
            for key, mask in sign_buckets(scores["signedTotal"], ZERO_TOL).items():
                sign[key] += mask.astype(np.int32)
            for label, board in boards.items():
                chosen = order_by_score(board_ranked(scores, board), board)
                writer = writers[label]
                for method in METHODS:
                    for dimension in range(N_DIMENSIONS):
                        for rank, local in enumerate(chosen[method][dimension]):
                            counts[method][board["rows"][int(local)], dimension] += 1
                            writer.writerow([replicate, int(seed), C.TARGETS_50[dimension], method,
                                             rank + 1, board["names"][int(local)]])
                            rows_written[label] += 1
    finally:
        for handle in handles.values():
            handle.close()
    expected = int(reps) * N_DIMENSIONS * len(METHODS) * K
    for label, written in rows_written.items():
        if written != expected:
            raise RuntimeError(f"{label}: wrote {written} bootstrap rows, expected {expected}")
    # every cell must be partitioned exactly once per replicate; a miss would silently move a denominator
    totals = sum(sign[key] for key in BUCKET_KEYS)
    if not np.array_equal(totals, np.full((N_FEATURES, N_DIMENSIONS), int(reps), dtype=np.int32)):
        raise RuntimeError("sign buckets do not cover every replicate for every (compound, dimension) cell")
    return {"counts": counts, "sign": sign, "zeroTol": float(ZERO_TOL), "reps": int(reps),
            "rowsWritten": rows_written,
            "strata": {style: int(group.size) for style, group in zip(style_order, groups)}}


def frequencies(counts: dict, reps: int) -> dict:
    return {method: counts[method].astype(float) / float(reps) for method in METHODS}


# =====================================================================================================
# delivered tables
# =====================================================================================================
def module_alternatives(method: str, dimension: int, module_id: int, board: dict, ranked: dict,
                        delivered: set) -> tuple:
    """In-module ordering by the method's own point score; ranks 4..10 are the substitute pool.

    Returns ("none", []) when the module has no fourth member: an empty CSV cell would read back as NaN and
    would hide the fact that the module is simply too small for a same-module substitute.
    """
    members = board["byModule"].get(module_id, [])
    if not members:
        return NO_ALTERNATIVE, []
    score = ranked[method]
    ordered = sorted(members, key=lambda name: (-float(score[board["index"][name], dimension]), name))
    alternative = ordered[3] if len(ordered) > 3 else NO_ALTERNATIVE
    return alternative, [name for name in ordered[3:10] if name not in delivered]


def delivered_table(board: dict, ranked: dict, pi: dict, sign: dict, scores: dict,
                    modules: dict, kind_of: dict, reps: int, zero_tol: float = ZERO_TOL) -> tuple:
    """The delivered (pi-first) Top-3 table and the corresponding sets, per method in METHODS order.

    `sign` holds the per-cell replicate counters (positive / negative / zero / invalid / legacyPositive).
    The evidence label is decided on the DIRECTION-ALIGNED sign_stability, and an undetermined point
    direction keeps its own label instead of being read as a mixed/negative result.
    """
    chosen = order_by_pi(ranked, pi, board)
    rows, sets = [], {method: [] for method in METHODS}
    for method in METHODS:
        for dimension, target in enumerate(C.TARGETS_50):
            picked = [board["names"][int(local)] for local in chosen[method][dimension]]
            if len(set(picked)) != K:
                raise RuntimeError(f"{board['label']}/{method}/{target}: duplicate names in a Top-3 set")
            sets[method].append(picked)
            delivered = set(picked)
            for rank, local in enumerate(chosen[method][dimension]):
                name = board["names"][int(local)]
                grow = int(board["rows"][int(local)])
                value = float(pi[method][grow, dimension])
                fields = sign_fields(
                    int(sign[BUCKET_POSITIVE][grow, dimension]), int(sign[BUCKET_NEGATIVE][grow, dimension]),
                    int(sign[BUCKET_ZERO][grow, dimension]), int(sign[BUCKET_INVALID][grow, dimension]),
                    int(sign["legacyPositive"][grow, dimension]), int(reps),
                    float(scores["signedTotal"][grow, dimension]), zero_tol)
                alternative, _pool = module_alternatives(
                    method, dimension, modules["perCompound"][name]["moduleId"], board, ranked, delivered)
                if fields["direction_undetermined"]:
                    status = DIRECTION_UNDETERMINED
                elif value >= PI_STABLE and fields["sign_stability"] >= SIGN_STABLE:
                    status = "stable"
                elif value >= PI_STABLE:
                    status = "sign-mixed"
                elif fields["sign_stability"] >= SIGN_STABLE:
                    status = "low-pi"
                else:
                    status = "low-pi+sign-mixed"
                rows.append({
                    "dimension": target, "rank": rank + 1, "compound": name, "kind": kind_of[name],
                    "method": method,
                    "score": float(ranked[method][int(local), dimension]),
                    "pi": value, "pi_mc_se": math.sqrt(max(value * (1.0 - value), 0.0) / float(reps)),
                    "sign_stability": fields["sign_stability"],
                    # `direction` is kept as a TRI-STATE alias of point_direction so the existing paper /
                    # figure scripts that read this column keep working; the superseded binary rule that
                    # wrote "negative" for a zero or missing value is gone.
                    "direction": fields["point_direction"],
                    "p_positive": fields["p_positive"], "p_negative": fields["p_negative"],
                    "p_positive_legacy": fields["p_positive_legacy"],
                    "n_positive": fields["n_positive"], "n_negative": fields["n_negative"],
                    "n_zero": fields["n_zero"], "n_invalid": fields["n_invalid"],
                    "point_direction": fields["point_direction"],
                    "direction_status": fields["direction_status"],
                    "module_id": int(modules["perCompound"][name]["moduleId"]),
                    "alternative_rank4": alternative, "evidence_status": status,
                })
    return rows, sets


def module_alternative_report(table: list, board: dict, ranked: dict) -> list:
    """The full rank 4..10 substitute pool per delivered row, so an unstable third place is never hidden."""
    delivered_by_cell = {}
    for row in table:
        delivered_by_cell.setdefault((row["method"], row["dimension"]), set()).add(row["compound"])
    out = []
    for row in table:
        method, dimension = row["method"], C.TARGETS_50.index(row["dimension"])
        members = board["byModule"].get(row["module_id"], [])
        score = ranked[method][:, dimension]
        ordered = sorted(members, key=lambda name: (-float(score[board["index"][name]]), name))
        delivered = delivered_by_cell[(method, row["dimension"])]
        # board-wide fallback: the best candidate that is NOT delivered, so a pick whose module is too small
        # for a same-module substitute still exposes a substitute (clearly labelled board-wide, not same-module)
        global_order = sorted(board["names"], key=lambda name: (-float(score[board["index"][name]]), name))
        fallback = next((name for name in global_order if name not in delivered), NO_ALTERNATIVE)
        out.append({"dimension": row["dimension"], "method": method, "rank": row["rank"],
                    "compound": row["compound"], "pi": row["pi"], "moduleId": row["module_id"],
                    "moduleSize": len(members), "moduleOrder": ordered[:10],
                    "moduleRank4To10": ordered[3:10],
                    "sameModuleAlternativeExists": bool(len(ordered) > 3),
                    "globalFallback": fallback})
    return out


# =====================================================================================================
# sign evidence products (v6 §3)
# =====================================================================================================
def sign_counts_rows(sign: dict, scores: dict, kind_of: dict, reps: int,
                     zero_tol: float = ZERO_TOL) -> list:
    """One row per (compound, dimension): point rho, direction, replicate buckets and the three ratios."""
    rows = []
    signed_total = _guard_matrix(scores["signedTotal"], "signed_total")
    for name in FEATURE_COLS:
        grow = FEATURE_COLS.index(name)
        for dimension, target in enumerate(C.TARGETS_50):
            fields = sign_fields(
                int(sign[BUCKET_POSITIVE][grow, dimension]), int(sign[BUCKET_NEGATIVE][grow, dimension]),
                int(sign[BUCKET_ZERO][grow, dimension]), int(sign[BUCKET_INVALID][grow, dimension]),
                int(sign["legacyPositive"][grow, dimension]), int(reps),
                float(signed_total[grow, dimension]), zero_tol)
            rows.append([target, name, kind_of[name], fmt(signed_total[grow, dimension]),
                         fields["point_direction"], fields["n_positive"], fields["n_negative"],
                         fields["n_zero"], fields["n_invalid"], fields["valid"],
                         fmt(fields["p_positive"]), fmt(fields["p_negative"]),
                         fmt(fields["p_positive_legacy"]), fmt(fields["sign_stability"]),
                         fields["direction_status"]])
    return rows


def low_pi_rows(table: list, module_report: list, pi_threshold: float = PI_STABLE) -> list:
    """The delivered strict consensus rows with pi < the declared stability threshold.

    Each row carries its own status, its replicate counts and the same-module substitute pool
    (module_alternatives already publishes rank 4..10), so an unstable entry is never a bare number.
    """
    alternatives = {(record["dimension"], record["method"], record["rank"]): record
                    for record in module_report}
    out = []
    for row in table:
        if row["method"] != "consensus" or row["pi"] >= pi_threshold:
            continue
        record = alternatives.get((row["dimension"], row["method"], row["rank"]), {})
        pool = record.get("moduleRank4To10", [])
        out.append({
            "dimension": row["dimension"], "rank": row["rank"], "compound": row["compound"],
            "kind": row["kind"], "pi": row["pi"], "pi_mc_se": row["pi_mc_se"],
            "point_direction": row["point_direction"], "p_positive": row["p_positive"],
            "p_negative": row["p_negative"], "p_positive_legacy": row["p_positive_legacy"],
            "n_positive": row["n_positive"], "n_negative": row["n_negative"],
            "n_zero": row["n_zero"], "n_invalid": row["n_invalid"],
            "sign_stability": row["sign_stability"], "direction_status": row["direction_status"],
            "evidence_status": row["evidence_status"], "module_id": row["module_id"],
            "module_size": int(record.get("moduleSize", 0)),
            "alternative_rank4": row["alternative_rank4"],
            "module_rank4_to_10": "; ".join(pool) if pool else NO_ALTERNATIVE,
            "same_module_alternative_exists": bool(record.get("sameModuleAlternativeExists", False)),
            "global_fallback": record.get("globalFallback", NO_ALTERNATIVE),
        })
    return out


def _md_cell(value, digits: int) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def write_markdown(path: Path, title: str, note: list, header: list, rows: list,
                   digits: int = 3) -> int:
    """A readable witness table: fixed 3-decimal floats, integers as integers (full precision stays in CSV)."""
    lines = [f"# {title}", ""]
    lines.extend([f"- {text}" for text in note])
    lines.append("")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join("---" for _ in header) + "|")
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(value, digits) for value in row) + " |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


def legacy_reproduction(table: list, reference_path: Path, claim_reference: bool = True) -> dict:
    """Compare the recomputed legacy p_positive with the recorded superseded sign_stability.

    `claim_reference` marks the repeat the v6 note quotes (the primary repeat 0).  The note's 36 / 27
    counts describe THAT repeat only, so a different seed block records them as out of scope instead of
    reporting a spurious reproduction failure.

    READ-ONLY cross-check against an existing experiment record; it never feeds a delivered number.
    The runner's sandbox does not register that path, so an unreadable reference is reported as
    unavailable instead of being faked.
    """
    out = {"available": False, "reference": str(reference_path), "passed": None,
           "reason": "not read"}
    try:
        if not reference_path.exists():
            out["reason"] = "reference table does not exist"
            return out
        reference = pd.read_csv(reference_path)
        out["referenceSha256"] = C.sha256_file(reference_path)
    except OSError as error:  # sandbox denial / unreadable snapshot
        out["reason"] = f"reference table not readable: {error}"
        return out
    needed = {"dimension", "rank", "compound", "pi", "sign_stability"}
    if not needed.issubset(reference.columns):
        out["reason"] = f"reference table lacks columns {sorted(needed - set(reference.columns))}"
        return out
    mine = {(row["dimension"], int(row["rank"])): row for row in table
            if row["method"] == "consensus"}
    theirs = {(str(row["dimension"]), int(row["rank"])): row for _, row in reference.iterrows()}
    common = sorted(set(mine) & set(theirs))
    compound_mismatch = [key for key in common
                         if str(mine[key]["compound"]) != str(theirs[key]["compound"])]
    pi_diff = [abs(float(mine[key]["pi"]) - float(theirs[key]["pi"])) for key in common]
    legacy_diff = [abs(float(mine[key]["p_positive_legacy"]) - float(theirs[key]["sign_stability"]))
                   for key in common]
    negative_rows = [row for row in table
                     if row["method"] == "consensus" and row["point_direction"] == DIRECTION_NEGATIVE]
    legacy_values = [row["p_positive_legacy"] for row in negative_rows]
    out.update({
        "available": True, "rowsCompared": len(common),
        "rowsInReference": len(reference), "rowsRecomputed": len(mine),
        "keySetsEqual": set(mine) == set(theirs),
        "compoundMismatches": len(compound_mismatch),
        "piExactMatches": int(sum(1 for value in pi_diff if value == 0.0)),
        "piMaxAbsDiff": float(max(pi_diff)) if pi_diff else None,
        "legacyExactMatches": int(sum(1 for value in legacy_diff if value == 0.0)),
        "legacyMaxAbsDiff": float(max(legacy_diff)) if legacy_diff else None,
        # the v6 §3 claim, re-derived from THIS run instead of quoted from the note
        "recomputedNegativePointRows": len(negative_rows),
        "recomputedNegativeLegacyMin": float(min(legacy_values)) if legacy_values else None,
        "recomputedNegativeLegacyMax": float(max(legacy_values)) if legacy_values else None,
        "recomputedNegativeLegacyWithin0To0.022": int(sum(1 for value in legacy_values
                                                          if 0.0 <= value <= 0.022)),
        "recomputedNegativeLegacyExactZero": int(sum(1 for value in legacy_values if value == 0.0)),
        "v6Claim": {"negativePointRows": 36, "legacyRange": [0.0, 0.022], "legacyExactZero": 27},
    })
    if claim_reference:
        out["v6ClaimReproduced"] = bool(len(negative_rows) == 36
                                        and out["recomputedNegativeLegacyWithin0To0.022"] == 36
                                        and out["recomputedNegativeLegacyExactZero"] == 27)
        out["v6ClaimScope"] = "the v6 note quotes the primary repeat (seed 20261025); this repeat is it"
    else:
        out["v6ClaimReproduced"] = None
        out["v6ClaimScope"] = ("not applicable: the v6 note's 36 / 27 counts quote the primary repeat only; "
                               "this repeat is a different seed block, reported here for completeness")
    out["passed"] = bool(set(mine) == set(theirs) and not compound_mismatch
                         and out["piMaxAbsDiff"] == 0.0 and out["legacyMaxAbsDiff"] == 0.0)
    out["reason"] = "recomputed legacy p_positive compared with the recorded sign_stability"
    return out


def sign_status_counts(table: list) -> dict:
    """Distribution of direction_status / evidence_status over the delivered consensus strict rows."""
    consensus = [row for row in table if row["method"] == "consensus"]
    directions = {DIRECTION_POSITIVE: 0, DIRECTION_NEGATIVE: 0, DIRECTION_UNDETERMINED: 0}
    statuses = {"stable": 0, "sign-mixed": 0, "low-pi": 0, "low-pi+sign-mixed": 0,
                DIRECTION_UNDETERMINED: 0}
    for row in consensus:
        directions[row["direction_status"]] = directions.get(row["direction_status"], 0) + 1
        statuses[row["evidence_status"]] = statuses.get(row["evidence_status"], 0) + 1
    return {"directionCounts": directions, "evidenceStatusCounts": statuses,
            "rows": len(consensus),
            "replicateCounts": {"n_positive": int(sum(row["n_positive"] for row in consensus)),
                                "n_negative": int(sum(row["n_negative"] for row in consensus)),
                                "n_zero": int(sum(row["n_zero"] for row in consensus)),
                                "n_invalid": int(sum(row["n_invalid"] for row in consensus))}}


def sign_tables(table: list, module_report: list, out_dir: Path) -> dict:
    """Write the per-repeat low-pi witness table (CSV full precision + readable markdown)."""
    rows = low_pi_rows(table, module_report)
    payload = [[row[key] for key in LOWPI_HEADER] for row in rows]
    write_csv(out_dir / FILE_LOWPI, LOWPI_HEADER, payload)
    write_markdown(out_dir / (Path(FILE_LOWPI).stem + ".md"),
                   f"Q2 strict consensus rows with pi < {PI_STABLE} (sign status and substitutes)",
                   [f"rows: {len(rows)} of {sum(1 for row in table if row['method'] == 'consensus')} "
                    f"delivered strict consensus rows",
                    f"sign_stability counts a replicate only when it agrees with the point-estimate "
                    f"direction; |rho| <= {ZERO_TOL:g} is 'zero', non-finite is 'invalid'",
                    "module_rank4_to_10 is the same-module substitute pool (module_alternatives); "
                    "'none' means the module has fewer than 4 members",
                    "this is a stability label, not an accuracy or causal claim"],
                   LOWPI_HEADER, payload, digits=3)
    return {"count": len(rows), "file": FILE_LOWPI,
            "statusCounts": {status: int(sum(1 for row in rows if row["evidence_status"] == status))
                             for status in sorted({row["evidence_status"] for row in rows})},
            "directionCounts": {direction: int(sum(1 for row in rows
                                                  if row["direction_status"] == direction))
                                for direction in sorted({row["direction_status"] for row in rows})}}


# =====================================================================================================
# external corroboration (same-source, never used for selection)
# =====================================================================================================
def spearman_between(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if left.size < 3 or right.size != left.size:
        raise RuntimeError("spearman_between needs two equal vectors of at least 3 entries")
    ranked_left = QL.midranks(left.reshape(-1, 1))[:, 0]
    ranked_right = QL.midranks(right.reshape(-1, 1))[:, 0]
    ranked_left = ranked_left - ranked_left.mean()
    ranked_right = ranked_right - ranked_right.mean()
    denominator = float(np.linalg.norm(ranked_left) * np.linalg.norm(ranked_right))
    if denominator <= 1e-12:
        raise RuntimeError("constant vector: rank correlation is undefined")
    return float(ranked_left @ ranked_right / denominator)


def external_corroboration(signed_total: np.ndarray, mapping: dict, categories: dict) -> dict:
    """Rank correlation of our |Spearman| with 6.csv after name alignment on BOTH sides."""
    table = pd.read_csv(EXTERNAL_CSV)
    values = table.iloc[:, 1:].to_numpy(dtype=float)
    if values.shape != (len(table), N_DIMENSIONS):
        raise RuntimeError(f"6.csv value block has shape {values.shape}")
    records = mapping["chemistry"]["table"]
    our_rows = [record["position"] for record in records]
    their_rows = [record["row"] for record in records]
    our_columns = mapping["sensory"]["columnsForTargets"]
    strict = set(categories["strictNames"])
    strict_rows = [index for index, record in enumerate(records) if record["feature"] in strict]
    signed_total = _guard_matrix(signed_total, "signed_total")

    per_dimension, per_dimension_strict, per_dimension_positional = [], [], []
    for dimension, target in enumerate(C.TARGETS_50):
        ours = np.abs(signed_total[our_rows, dimension])
        theirs = np.abs(values[their_rows, our_columns[dimension]])
        per_dimension.append({"dimension": target, "spearman": spearman_between(ours, theirs),
                              "nCompounds": len(records), "nStrictCompounds": len(strict_rows)})
        per_dimension_strict.append(spearman_between(ours[strict_rows], theirs[strict_rows]))
        # diagnostic: rows aligned, columns still read positionally (the superseded column convention)
        per_dimension_positional.append(spearman_between(ours, np.abs(values[their_rows, dimension])))

    # diagnostic reproduction of the superseded pipeline: 219-row candidate space indexed with 231-space
    # positions, plus positional sensory columns.  It never feeds a delivered number.
    legacy_names = [name for name in FEATURE_COLS
                    if categories["kindOf"][name] in ("single_compound", "element_or_index")]
    legacy_matrix = signed_total[[FEATURE_COLS.index(name) for name in legacy_names], :]
    if legacy_matrix.shape != (len(legacy_names), N_DIMENSIONS):
        raise RuntimeError("legacy reproduction: candidate space has the wrong shape")
    legacy = []
    if max(our_rows) < legacy_matrix.shape[0]:
        for dimension in range(N_DIMENSIONS):
            ours = np.abs(legacy_matrix[our_rows, dimension])
            theirs = np.abs(values[their_rows, dimension])
            legacy.append(spearman_between(ours, theirs))

    finite = np.asarray([record["spearman"] for record in per_dimension], dtype=float)
    if not np.isfinite(finite).all():
        raise RuntimeError("non-finite external corroboration")
    return {
        "status": "SAME-SOURCE corroboration, NOT independent external validation: 6.csv ships with the same "
                  "attachment and never enters the Top-3 selection. It only says our |Spearman| matrix agrees "
                  "in rank with the table the attachment itself provides.",
        "alignment": "rows by chemistry display name -> corrLabel/name; columns by explicit name dictionary",
        "nMatched": len(records), "nUnmatched": mapping["chemistry"]["nUnmatched"],
        "nStrictCompounds": len(strict_rows),
        "meanSpearman": float(finite.mean()), "medianSpearman": float(np.median(finite)),
        "minSpearman": float(finite.min()), "maxSpearman": float(finite.max()),
        "meanSpearmanStrictOnly": float(np.mean(per_dimension_strict)),
        "meanSpearmanPositionalColumnsOnly": float(np.mean(per_dimension_positional)),
        "meanSpearmanSupersededPipeline": float(np.mean(legacy)) if legacy else None,
        "supersededNote": "the previous 0.445051 value is reproduced by the positional-column + 219/231 index "
                          "mix; it is a misalignment artefact, not a chemistry finding",
        "perDimension": per_dimension,
    }


# =====================================================================================================
# one repeat
# =====================================================================================================
def _registered_reference(legacy_root, repeat: int):
    """Locate the recorded per-repeat strict table, honouring the runner's dependency remapping.

    Under the experiment runner every registered dependency is copied into a snapshot and its absolute location is
    published in ``MODELING_DEPENDENCIES`` (``{project-relative path: snapshot path}``). A plain
    ``Path(legacy_root)`` therefore does not exist inside the sandbox even when the file IS registered. The lookup
    order is: remapped dependency -> legacy_root/repeatN -> legacy_root (repeat 0 only). Returning ``None`` means
    "no reference table supplied"; it is never treated as a successful reproduction.
    """
    keys = [f"repeat{repeat}/strict_top3.csv", f"experiments/EXP-0075/repeat{repeat}/strict_top3.csv"]
    if repeat == 0:
        keys += ["strict_top3.csv", "experiments/EXP-0075/strict_top3.csv"]
    raw = os.environ.get("MODELING_DEPENDENCIES")
    if raw:
        try:
            mapping = json.loads(raw)
        except ValueError:
            mapping = {}
        for project_key, snapshot in mapping.items():
            normalised = str(project_key).replace(os.sep, "/")
            if any(normalised.endswith("EXP-0075/" + key) or normalised == key for key in keys):
                candidate = Path(snapshot)
                if candidate.exists():
                    return candidate
    base = Path(legacy_root)
    candidate = base / f"repeat{repeat}" / "strict_top3.csv"
    if candidate.exists():
        return candidate
    if repeat == 0:
        root_table = base / "strict_top3.csv"
        if root_table.exists():
            return root_table
    return None


def run_repeat(repeat: int, frame: pd.DataFrame, categories: dict, base_scores: dict, modules: dict,
               boards: dict, out_dir: Path, reps: int, legacy_root: Path = None,
               self_test: dict = None, source_hashes: dict = None) -> dict:
    seed = int(C.SEEDS[repeat])
    started = time.time()
    strict_set = set(categories["strictNames"])
    boot = bootstrap(frame, seed, reps, boards,
                     {"strict": out_dir / FILE_BOOT, "extended": out_dir / FILE_BOOT_EXT})
    pi = frequencies(boot["counts"], reps)

    tables, sets, ranked = {}, {}, {}
    for label, board in boards.items():
        ranked[label] = board_ranked(base_scores, board)
        tables[label], sets[label] = delivered_table(board, ranked[label], pi, boot["sign"],
                                                    base_scores, modules, categories["kindOf"], reps)

    # ---------------------------------------------------------------- sets.json (50 dimensions x 4 methods)
    sets_payload = []
    for dimension, target in enumerate(C.TARGETS_50):
        for method in METHODS:
            items = sets["strict"][method][dimension]
            sets_payload.append({"dimension": target, "method": method, "items": items})
    if len(sets_payload) != N_DIMENSIONS * len(METHODS):
        raise RuntimeError(f"sets.json has {len(sets_payload)} rows, expected {N_DIMENSIONS * len(METHODS)}")
    for record in sets_payload:
        if len(record["items"]) != K or len(set(record["items"])) != K:
            raise RuntimeError(f"sets.json row is not 3 distinct compounds: {record}")
        if not set(record["items"]) <= strict_set:
            raise RuntimeError(f"sets.json leaked a non-single_compound candidate: {record['items']}")
    C.save_json(FILE_SETS, sets_payload, out_dir)

    # ---------------------------------------------------------------- top-3 tables
    def table_rows(table, with_method=False):
        rows = []
        for row in table:
            line = [row["dimension"], row["rank"], row["compound"], row["kind"], row["score"],
                    row["pi"], row["pi_mc_se"], row["sign_stability"], row["direction"], row["p_positive"],
                    row["p_negative"], row["p_positive_legacy"], row["n_positive"], row["n_negative"],
                    row["n_zero"], row["n_invalid"], row["point_direction"], row["direction_status"],
                    row["module_id"], row["alternative_rank4"], row["evidence_status"]]
            if with_method:
                line.append(row["method"])
            rows.append(line)
        return rows

    def csv_rows(rows):
        """Floats leave the CSV at full round-trip precision; integers stay integers."""
        return [[fmt(value) if isinstance(value, float) else value for value in row] for row in rows]

    consensus = {label: [row for row in tables[label] if row["method"] == "consensus"]
                 for label in boards}
    write_csv(out_dir / FILE_STRICT, TOP3_HEADER, csv_rows(table_rows(consensus["strict"])))
    write_csv(out_dir / FILE_STRICT_METHODS, TOP3_HEADER_METHOD,
              csv_rows(table_rows(tables["strict"], True)))
    write_csv(out_dir / FILE_EXTENDED, TOP3_HEADER, csv_rows(table_rows(consensus["extended"])))
    write_csv(out_dir / FILE_EXTENDED_METHODS, TOP3_HEADER_METHOD,
              csv_rows(table_rows(tables["extended"], True)))

    # ---------------------------------------------------------------- sign evidence products
    write_csv(out_dir / FILE_SIGN_COUNTS, SIGN_COUNTS_HEADER,
              sign_counts_rows(boot["sign"], base_scores, categories["kindOf"], reps))
    module_report = module_alternative_report(tables["strict"], boards["strict"], ranked["strict"])
    module_report_extended = module_alternative_report(tables["extended"], boards["extended"],
                                                       ranked["extended"])
    lowpi = sign_tables(tables["strict"], module_report, out_dir)
    reference = None
    probe_error = None
    if legacy_root is not None:
        # the runner's sandbox remaps every registered dependency to a snapshot path, so the recorded reference
        # tables are resolved through MODELING_DEPENDENCIES first; a denied stat is reported as "no reference
        # available" instead of crashing the registered run (and never as a pass)
        try:
            reference = _registered_reference(legacy_root, repeat)
        except OSError as error:
            reference = None
            probe_error = f"reference path not readable under the run sandbox: {error}"
    if reference is not None and int(reps) == int(N_BOOTSTRAP):
        legacy = legacy_reproduction(tables["strict"], reference, claim_reference=(int(repeat) == 0))
    elif reference is not None:
        legacy = {"available": False, "reference": str(reference), "passed": None,
                  "reason": f"bootstrapReps={int(reps)} differs from the recorded {int(N_BOOTSTRAP)}: the "
                            f"legacy ratio uses its own denominator, so the comparison is not meaningful"}
    else:
        legacy = {"available": False, "reference": None, "passed": None,
                  "reason": probe_error or "no recorded reference table was supplied for this repeat"}

    # ---------------------------------------------------------------- candidate scores (231 x 50)
    candidate_rows = []
    for name in FEATURE_COLS:
        label = "strict" if name in strict_set else "extended"
        local = boards[label]["index"][name]
        grow = FEATURE_COLS.index(name)
        for dimension, target in enumerate(C.TARGETS_50):
            candidate_rows.append([
                target, name, categories["kindOf"][name],
                fmt(base_scores["signedTotal"][grow, dimension]),
                fmt(base_scores["within_signed"][grow, dimension]),
                fmt(base_scores["graph_beta_signed"][grow, dimension]),
                fmt(ranked[label]["consensus"][local, dimension]),
                fmt(pi["consensus"][grow, dimension]),
            ])
    write_csv(out_dir / FILE_CANDIDATES, CANDIDATE_HEADER, candidate_rows)

    # ---------------------------------------------------------------- jaccard between methods
    pairs = QL.pairwise_jaccard(sets["strict"], METHODS)
    summary = QL.jaccard_summary(pairs)
    point_sets = sets_as_names(order_by_score(ranked["strict"], boards["strict"]), boards["strict"])
    point_pairs = QL.pairwise_jaccard(point_sets, METHODS)
    point_summary = QL.jaccard_summary(point_pairs)

    # ---------------------------------------------------------------- stability numbers of this repeat
    selected_pi = [row["pi"] for row in tables["strict"]]
    selected_sign = [row["sign_stability"] for row in tables["strict"]]
    selected_legacy = [row["p_positive_legacy"] for row in tables["strict"]]
    below = int(sum(1 for value in selected_pi if value < PI_STABLE))
    third_place = [{"dimension": row["dimension"], "method": row["method"], "compound": row["compound"],
                    "pi": row["pi"], "alternative_rank4": row["alternative_rank4"]}
                   for row in tables["strict"] if row["rank"] == K and row["pi"] < PI_STABLE]
    sign_counts = sign_status_counts(tables["strict"])
    sign_counts_consensus = sign_status_counts(consensus["strict"])

    repeat_metrics = {
        "topk-jaccard": float(summary["overall"]),
        "topk-jaccard-point": float(point_summary["overall"]),
        "pi_mean": float(np.mean(selected_pi)),
        "pi_below_0.5_count": below,
        "pi_below_0.5_denominator": len(selected_pi),
        "sign_stability_mean": float(np.mean(selected_sign)),
        "sign_stability_legacy_mean": float(np.mean(selected_legacy)),
        "sign_negative_point_count": int(sign_counts["directionCounts"][DIRECTION_NEGATIVE]),
        "sign_direction_undetermined_count": int(
            sign_counts["directionCounts"][DIRECTION_UNDETERMINED]),
        "sign_zero_count": int(sign_counts["replicateCounts"]["n_zero"]),
        "sign_invalid_count": int(sign_counts["replicateCounts"]["n_invalid"]),
        "bootstrap_reps": int(reps),
        "n_dimensions": int(N_DIMENSIONS),
        "n_strict_candidates": int(len(categories["strictNames"])),
        "seed": seed,
    }

    stability = {
        "selectedPiMean": float(np.mean(selected_pi)),
        "selectedPiMin": float(np.min(selected_pi)),
        "selectedPiMedian": float(np.median(selected_pi)),
        "shareSelectedAtPiOne": float(np.mean([value == 1.0 for value in selected_pi])),
        "perMethodMeanSelectedPi": {
            method: float(np.mean([row["pi"] for row in tables["strict"] if row["method"] == method]))
            for method in METHODS},
        "selectedSignStabilityMean": float(np.mean(selected_sign)),
        "selectedSignStabilityLegacyMean": float(np.mean(selected_legacy)),
        "directionStatusCounts": sign_counts_consensus["directionCounts"],
        "evidenceStatusCounts": sign_counts_consensus["evidenceStatusCounts"],
        "signReplicateCounts": sign_counts_consensus["replicateCounts"],
        "thirdPlaceUnstable": third_place,
        "thirdPlaceUnstableCount": len(third_place),
        "sameModuleAlternativeMissingCount": int(sum(1 for row in tables["strict"]
                                                     if row["alternative_rank4"] == NO_ALTERNATIVE)),
        "threshold": {"piStable": PI_STABLE, "signStable": SIGN_STABLE,
                      "zeroTolerance": ZERO_TOL,
                      "note": "labels only: stability is not accuracy; |rho| <= zeroTolerance is 'zero' and "
                              "a zero / non-finite point estimate is 'direction-undetermined'"},
    }
    stability_extended = {
        "selectedPiMean": float(np.mean([row["pi"] for row in tables["extended"]])),
        "piBelow0.5Count": int(sum(1 for row in tables["extended"] if row["pi"] < PI_STABLE)),
        "n": len(tables["extended"]),
    }

    # ---------------------------------------------------------------- sign_stability_summary.json
    summary_payload = {
        "schemaVersion": "q2-sign-stability/1",
        "repeat": int(repeat), "seed": seed,
        "question": "Q2 compound -> sensory-dimension Top-3 direction stability",
        "definition": {
            "pointDirection": "sign of the point-estimate total Spearman (200 SPLIT-0001 train rows) for the "
                              "same (compound, dimension) cell",
            "zeroTolerance": float(ZERO_TOL),
            "zeroToleranceRule": f"a replicate with |rho| <= {ZERO_TOL:g} is counted as `zero` (near-zero), "
                                 f"never as positive and never as negative",
            "positive": f"rho > {ZERO_TOL:g}", "negative": f"rho < {-ZERO_TOL:g}",
            "invalid": "rho is not finite (NaN/inf) and therefore has no direction",
            "p_positive": "n_positive / valid",
            "p_negative": "n_negative / valid",
            "sign_stability": "(replicates agreeing with point_direction) / valid",
            "valid": "bootstrapReps - n_invalid",
            "p_positive_legacy": "superseded rule (rho > 0) / bootstrapReps, kept as a control column",
            "undetermined": "a zero or non-computable point estimate is labelled `direction-undetermined`; it "
                            "is never folded into the negative direction and 1 - p_positive is never reported "
                            "as a negative frequency",
            "notClaimed": "this is the stability of the total-correlation DIRECTION; it is not the stability "
                          "of the low-rank coefficients, not a causal direction and not an accuracy measure",
        },
        "denominators": {
            "bootstrapReps": int(reps),
            "validDenominator": "reps - n_invalid",
            "legacyDenominator": "reps (the superseded denominator)",
            "legacyComparableReps": int(N_BOOTSTRAP),
            "cells": int(N_FEATURES * N_DIMENSIONS),
            "deliveredRowsStrictAllMethods": int(len(tables["strict"])),
            "deliveredRowsStrictConsensus": int(len(consensus["strict"])),
        },
        "bootstrap": {"seeds": [seed], "reps": int(reps), "stratifiedBy": STYLE_COL,
                      "strata": boot["strata"], "redrawnPerReplicate": True,
                      "zeroTolerance": float(ZERO_TOL)},
        "population": {"board": "strict single_compound", "method": "consensus",
                       "rows": int(len(consensus["strict"])), "dimensions": int(N_DIMENSIONS),
                       "ranks": int(K)},
        "directionCounts": sign_counts_consensus["directionCounts"],
        "replicateCounts": sign_counts_consensus["replicateCounts"],
        "evidenceStatusCounts": sign_counts_consensus["evidenceStatusCounts"],
        "means": {"sign_stability": float(np.mean(selected_sign)),
                  "sign_stability_legacy": float(np.mean(selected_legacy))},
        "lowPi": {**lowpi, "threshold": PI_STABLE},
        "legacyReproduction": legacy,
        "selfTest": self_test if self_test is not None else {"passed": None,
                                                             "reason": "not supplied by the caller"},
        "inputs": source_hashes or {},
    }
    C.write_json(out_dir / FILE_SIGN_SUMMARY, jsonable(summary_payload))

    files = {name: C.sha256_file(out_dir / name)
             for name in (FILE_SETS, FILE_STRICT, FILE_STRICT_METHODS, FILE_EXTENDED,
                          FILE_EXTENDED_METHODS, FILE_CANDIDATES, FILE_BOOT, FILE_BOOT_EXT,
                          FILE_SIGN_COUNTS, FILE_LOWPI, FILE_SIGN_SUMMARY)}

    elapsed = time.time() - started
    return {
        "repeat": int(repeat), "seed": seed, "metrics": repeat_metrics, "elapsed": elapsed,
        "sets": sets["strict"], "setsPayload": sets_payload, "pairs": pairs, "summary": summary,
        "pointSummary": point_summary, "outDir": out_dir, "signSummary": summary_payload,
        "repeatPayload": {
            "repeat": int(repeat), "seed": seed, "metrics": repeat_metrics,
            "jaccard": {"deliveredPiFirst": {"pairs": pairs, "summary": summary},
                        "pointEstimateSets": {"pairs": point_pairs, "summary": point_summary},
                        "definition": "J = |A n B| / (2k - |A n B|) with k = 3; mean over 50 dimensions and the "
                                      "6 method pairs; delivered sets are pi-first, point sets are the "
                                      "point-estimate Top-3"},
            "stability": stability, "stability_extended": stability_extended,
            "top3_strict": tables["strict"], "top3_extended": tables["extended"],
            "module_alternatives": module_report,
            "module_alternatives_extended": module_report_extended,
            "signStability": {"definition": summary_payload["definition"],
                              "zeroTolerance": float(ZERO_TOL),
                              "directionCounts": sign_counts_consensus["directionCounts"],
                              "replicateCounts": sign_counts_consensus["replicateCounts"],
                              "lowPi": summary_payload["lowPi"],
                              "legacyReproduction": legacy,
                              "summaryFile": FILE_SIGN_SUMMARY,
                              "countsFile": FILE_SIGN_COUNTS,
                              "lowPiFile": FILE_LOWPI},
            "bootstrap": {"reps": int(reps), "seeds": [seed], "stratifiedBy": STYLE_COL,
                          "strata": boot["strata"], "redrawnPerReplicate": True,
                          "refitPerReplicate": ["median imputation",
                                                "Spearman graph at tau=0.5",
                                                "graph low-rank regression (rank 6, lambda 1, gamma 0.1, "
                                                "25 ALS sweeps)",
                                                "within-style rank residualisation",
                                                "all three ingredient scores", "within-board percentile ranks"],
                          "piMonteCarloSE": "sqrt(pi*(1-pi)/reps)",
                          "signStability": "share of replicates whose signed total Spearman agrees with the "
                                           "point-estimate direction (v6 §3); positive / negative / "
                                           "zero / invalid counts are stored separately and "
                                           "p_positive_legacy keeps the superseded (rho > 0) rule",
                          "zeroTolerance": float(ZERO_TOL),
                          "rowsWritten": boot["rowsWritten"],
                          "files": [{"path": FILE_BOOT, "board": "strict",
                                     "rows": boot["rowsWritten"]["strict"]},
                                    {"path": FILE_BOOT_EXT, "board": "extended",
                                     "rows": boot["rowsWritten"]["extended"]}]},
            "files": files,
            "repeatTiming": {"seconds": elapsed},
        },
    }


# =====================================================================================================
# self checks
# =====================================================================================================
def self_check(out_dir: Path, sets_payload: list, categories: dict, reps: int) -> dict:
    strict = set(categories["strictNames"])
    forbidden = {name for name in FEATURE_COLS if name not in strict}
    report = {}

    with open(out_dir / FILE_SETS, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    report["sets_entries"] = len(raw)
    report["sets_dimensions"] = len({record["dimension"] for record in raw})
    report["sets_methods"] = sorted({record["method"] for record in raw})
    report["sets_each_k3_unique"] = all(len(record["items"]) == K and len(set(record["items"])) == K
                                        for record in raw)
    report["sets_strict_only"] = all(set(record["items"]) <= strict for record in raw)
    report["sets_matches_memory"] = raw == jsonable(sets_payload)

    report["bootstrap_rows"] = sum(1 for _ in open(out_dir / FILE_BOOT, encoding="utf-8")) - 1
    report["bootstrap_rows_expected"] = int(reps) * N_DIMENSIONS * len(METHODS) * K
    report["bootstrap_extended_rows"] = sum(1 for _ in open(out_dir / FILE_BOOT_EXT, encoding="utf-8")) - 1

    table = pd.read_csv(out_dir / FILE_STRICT)
    report["strict_header_ok"] = list(table.columns) == TOP3_HEADER
    report["strict_rows"] = len(table)
    report["strict_kinds"] = sorted(table["kind"].unique().tolist())
    report["strict_forbidden"] = sorted(set(table["compound"]) & forbidden)
    report["strict_compounds"] = int(table["compound"].nunique())
    by_method = pd.read_csv(out_dir / FILE_STRICT_METHODS)
    report["strict_by_method_header_ok"] = list(by_method.columns) == TOP3_HEADER_METHOD
    report["strict_by_method_rows"] = len(by_method)
    report["strict_by_method_counts"] = {method: int((by_method["method"] == method).sum())
                                        for method in METHODS}
    report["strict_by_method_forbidden"] = sorted(set(by_method["compound"]) & forbidden)
    report["top3_nan"] = int(table.isna().sum().sum()) + int(by_method.isna().sum().sum())
    report["alternative_rank4_empty"] = int((table["alternative_rank4"].astype(str) == "").sum()) + \
        int((by_method["alternative_rank4"].astype(str) == "").sum())
    extended = pd.read_csv(out_dir / FILE_EXTENDED)
    report["extended_header_ok"] = list(extended.columns) == TOP3_HEADER
    report["extended_rows"] = len(extended)
    report["extended_kinds"] = sorted(extended["kind"].unique().tolist())
    extended_methods = pd.read_csv(out_dir / FILE_EXTENDED_METHODS)
    report["extended_by_method_header_ok"] = list(extended_methods.columns) == TOP3_HEADER_METHOD
    report["extended_by_method_rows"] = len(extended_methods)
    candidates = pd.read_csv(out_dir / FILE_CANDIDATES)
    report["candidate_rows"] = len(candidates)
    report["candidate_nan"] = int(candidates[["rho_total", "rho_within", "beta_graphlowrank", "score",
                                              "pi"]].isna().sum().sum())
    # ---------------------------------------------------------------- v6 §3 direction evidence
    counts_table = pd.read_csv(out_dir / FILE_SIGN_COUNTS)
    report["sign_counts_header_ok"] = list(counts_table.columns) == SIGN_COUNTS_HEADER
    report["sign_counts_rows"] = len(counts_table)
    bucket_sum = counts_table[["n_positive", "n_negative", "n_zero", "n_invalid"]].sum(axis=1)
    report["sign_counts_partition_reps"] = bool((bucket_sum == int(reps)).all())
    report["sign_counts_invalid_cells"] = int((counts_table["n_invalid"] != 0).sum())
    report["sign_counts_zero_cells"] = int((counts_table["n_zero"] != 0).sum())
    allowed_status = {DIRECTION_POSITIVE, DIRECTION_NEGATIVE, DIRECTION_UNDETERMINED}
    report["sign_counts_status_values"] = sorted(set(counts_table["direction_status"]) - allowed_status)
    valid = int(reps) - counts_table["n_invalid"].to_numpy(dtype=float)
    aligned = np.where(counts_table["direction_status"].to_numpy() == DIRECTION_POSITIVE,
                       counts_table["n_positive"].to_numpy(dtype=float),
                       np.where(counts_table["direction_status"].to_numpy() == DIRECTION_NEGATIVE,
                                counts_table["n_negative"].to_numpy(dtype=float), 0.0))
    denominators = np.where(valid > 0, valid, 1.0)
    diffs = [
        float(np.max(np.abs(counts_table["p_positive"].to_numpy(dtype=float)
                           - counts_table["n_positive"].to_numpy(dtype=float) / denominators))),
        float(np.max(np.abs(counts_table["p_negative"].to_numpy(dtype=float)
                           - counts_table["n_negative"].to_numpy(dtype=float) / denominators))),
        float(np.max(np.abs(counts_table["sign_stability"].to_numpy(dtype=float) - aligned / denominators))),
        float(np.max(np.abs(counts_table["p_positive_legacy"].to_numpy(dtype=float) * int(reps)
                           - np.round(counts_table["p_positive_legacy"].to_numpy(dtype=float) * int(reps))))),
    ]
    report["sign_ratio_max_abs_diff"] = float(max(diffs))
    report["sign_undetermined_cells"] = int((counts_table["direction_status"] == DIRECTION_UNDETERMINED).sum())

    lowpi_table = pd.read_csv(out_dir / FILE_LOWPI)
    report["lowpi_header_ok"] = list(lowpi_table.columns) == LOWPI_HEADER
    report["lowpi_rows"] = len(lowpi_table)
    report["lowpi_expected_rows"] = int((table["pi"] < PI_STABLE).sum())
    report["lowpi_status_values"] = sorted(set(lowpi_table["evidence_status"]) - set(
        ["stable", "sign-mixed", "low-pi", "low-pi+sign-mixed", DIRECTION_UNDETERMINED]))

    summary_file = out_dir / FILE_SIGN_SUMMARY
    report["sign_summary_exists"] = summary_file.exists()
    if report["sign_summary_exists"]:
        summary_payload = C.read_json(summary_file)
        report["sign_summary_zero_tolerance"] = float(summary_payload["definition"]["zeroTolerance"])
        report["sign_summary_zero_tolerance_ok"] = report["sign_summary_zero_tolerance"] == float(ZERO_TOL)
        report["sign_summary_reps"] = int(summary_payload["denominators"]["bootstrapReps"])
        report["sign_summary_self_test_passed"] = bool(
            (summary_payload.get("selfTest") or {}).get("passed") is True)
    else:
        report["sign_summary_zero_tolerance_ok"] = False
        report["sign_summary_self_test_passed"] = False

    expected_single_method = N_DIMENSIONS * K
    expected_all_methods = N_DIMENSIONS * len(METHODS) * K
    passed = (report["sets_entries"] == N_DIMENSIONS * len(METHODS)
              and report["sets_dimensions"] == N_DIMENSIONS
              and report["sets_each_k3_unique"] and report["sets_strict_only"]
              and report["bootstrap_rows"] == report["bootstrap_rows_expected"]
              and report["strict_header_ok"] and report["strict_by_method_header_ok"]
              and report["extended_header_ok"] and report["extended_by_method_header_ok"]
              and report["strict_forbidden"] == []
              and report["strict_by_method_forbidden"] == []
              and report["strict_rows"] == expected_single_method
              and report["strict_by_method_rows"] == expected_all_methods
              and all(value == expected_single_method for value in report["strict_by_method_counts"].values())
              and report["extended_rows"] == expected_single_method
              and report["extended_by_method_rows"] == expected_all_methods
              and report["candidate_rows"] == N_FEATURES * N_DIMENSIONS
              and report["candidate_nan"] == 0
              and report["top3_nan"] == 0
              and report["alternative_rank4_empty"] == 0
              and report["sets_matches_memory"]
              and report["sign_counts_header_ok"]
              and report["sign_counts_rows"] == N_FEATURES * N_DIMENSIONS
              and report["sign_counts_partition_reps"]
              and report["sign_counts_status_values"] == []
              and report["sign_ratio_max_abs_diff"] == 0.0
              and report["lowpi_header_ok"]
              and report["lowpi_rows"] == report["lowpi_expected_rows"]
              and report["lowpi_status_values"] == []
              and report["sign_summary_exists"]
              and report["sign_summary_zero_tolerance_ok"]
              and report["sign_summary_reps"] == int(reps)
              and report["sign_summary_self_test_passed"])
    report["allPassed"] = bool(passed)
    if not passed:
        raise RuntimeError(f"self check failed: {report}")
    return report


# =====================================================================================================
# local deliverable export (never used by the registered runner: the sandbox forbids writes outside
# $MODELING_EXPERIMENT_DIR, so --export-dir is a LOCAL-ONLY convenience for the delivery tree)
# =====================================================================================================
EXPORT_FILES = (FILE_STRICT, FILE_STRICT_METHODS, FILE_EXTENDED, FILE_EXTENDED_METHODS,
                FILE_SIGN_COUNTS, FILE_LOWPI, FILE_SIGN_SUMMARY)
REPORT_HEADER = ["dimension", "rank", "compound", "pi", "pi_mc_se", "sign_stability", "p_positive",
                 "p_negative", "p_positive_legacy", "n_positive", "n_negative", "n_zero", "n_invalid",
                 "point_direction", "evidence_status"]


def _read_csv_rows(path: Path, columns: list) -> list:
    frame = pd.read_csv(path)
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise RuntimeError(f"{path} lacks columns {missing}")
    return [[record[column] for column in columns] for _, record in frame.iterrows()]


def export_deliverables(base_out: Path, export_dir: Path, results: list, metrics: dict) -> dict:
    """Copy the primary repeat's delivered files into a delivery directory and add readable witnesses."""
    export_dir.mkdir(parents=True, exist_ok=True)
    primary = results[0]
    source_dir = primary["outDir"]
    written = []
    for name in EXPORT_FILES:
        source = source_dir / name if (source_dir / name).exists() else base_out / name
        if not source.exists():
            raise RuntimeError(f"export: {name} is missing at {source}")
        target = export_dir / name
        shutil.copyfile(source, target)
        written.append(target)
    lowpi_md = source_dir / (Path(FILE_LOWPI).stem + ".md")
    if lowpi_md.exists():
        shutil.copyfile(lowpi_md, export_dir / lowpi_md.name)
        written.append(export_dir / lowpi_md.name)
    # readable 3-decimal witness of the delivered consensus table (the CSV keeps full precision)
    rows = _read_csv_rows(export_dir / FILE_STRICT, REPORT_HEADER)
    write_markdown(export_dir / (Path(FILE_STRICT).stem + ".md"),
                   "Q2 delivered strict consensus Top-3 with direction evidence (3 decimals)",
                   ["CSV keeps full round-trip precision; this table is rounded to 3 decimals for reading",
                    f"sign_stability = replicates agreeing with the point direction / valid; "
                    f"|rho| <= {ZERO_TOL:g} is 'zero'; a zero or non-computable point estimate is "
                    f"'direction-undetermined'",
                    "p_positive_legacy is the superseded (rho > 0)/reps column, kept only as a control",
                    "stability labels are not accuracy or causal claims"],
                   REPORT_HEADER, rows, digits=3)
    written.append(export_dir / (Path(FILE_STRICT).stem + ".md"))

    summary_payload = C.read_json(export_dir / FILE_SIGN_SUMMARY)
    report = ["# Q2 direction stability (v6 §3)", ""]
    report.append(f"- zero tolerance: **{ZERO_TOL:g}** (pre-declared; |rho| <= tolerance is `zero`)")
    report.append("- reference direction: point-estimate total Spearman on the 200 SPLIT-0001 train rows")
    report.append("- sign_stability: replicates agreeing with the reference direction / valid "
                  "(valid = reps - n_invalid); p_positive = n_positive/valid; p_negative = n_negative/valid")
    report.append("- a zero or non-computable point estimate is `direction-undetermined`, never negative")
    report.append("- p_positive_legacy keeps the superseded (rho > 0)/reps rule; it does not enter the ranking")
    report.append("")
    for result in results:
        payload = C.read_json(result["outDir"] / FILE_SIGN_SUMMARY)
        report.append(f"## repeat {result['repeat']} (seed {result['seed']}, reps {payload['denominators']['bootstrapReps']})")
        report.append("")
        report.append(f"- direction counts (150 delivered consensus rows): {payload['directionCounts']}")
        report.append(f"- evidence status counts: {payload['evidenceStatusCounts']}")
        report.append(f"- replicate counts over those rows: {payload['replicateCounts']}")
        report.append(f"- mean sign_stability (new): {payload['means']['sign_stability']:.6f}; "
                      f"mean p_positive_legacy (old): {payload['means']['sign_stability_legacy']:.6f}")
        report.append(f"- rows with pi < {payload['lowPi']['threshold']}: {payload['lowPi']['count']}; "
                      f"status {payload['lowPi']['statusCounts']}; direction {payload['lowPi']['directionCounts']}")
        legacy = payload["legacyReproduction"]
        if legacy.get("available"):
            report.append(f"- legacy reproduction: rows compared {legacy['rowsCompared']}, "
                          f"compound mismatches {legacy['compoundMismatches']}, "
                          f"pi exact {legacy['piExactMatches']} (max |diff| {legacy['piMaxAbsDiff']}), "
                          f"old sign_stability exact {legacy['legacyExactMatches']} "
                          f"(max |diff| {legacy['legacyMaxAbsDiff']}), passed={legacy['passed']}")
            report.append(f"- negative-direction rows re-derived: {legacy['recomputedNegativePointRows']}, "
                          f"legacy in [0, 0.022] = "
                          f"{legacy['recomputedNegativeLegacyWithin0To0.022']}, exactly zero = "
                          f"{legacy['recomputedNegativeLegacyExactZero']}")
            if legacy.get("v6ClaimReproduced") is None:
                report.append(f"- v6 reference claim (36 rows / 27 zeros): {legacy.get('v6ClaimScope')}")
            else:
                report.append(f"- v6 reference claim (36 rows / 27 zeros) reproduced = "
                              f"{legacy['v6ClaimReproduced']} ({legacy.get('v6ClaimScope')})")
        else:
            report.append(f"- legacy reproduction unavailable: {legacy.get('reason')}")
        report.append("")
    selftest = summary_payload.get("selfTest") or {}
    if selftest.get("cases"):
        report.append("## definition self-test (hand-built vectors, run before any replicate)")
        report.append("")
        report.append(f"- zero tolerance {selftest['zeroTolerance']:g}, checks passed = {selftest['passed']}")
        report.append("")
        header = ["case", "point", "n_pos", "n_neg", "n_zero", "n_invalid", "valid", "p_positive",
                  "p_negative", "p_positive_legacy", "sign_stability", "direction_status"]
        table = []
        for case in selftest["cases"]:
            table.append([case["case"], case["pointEstimate"], case["n_positive"], case["n_negative"],
                          case["n_zero"], case["n_invalid"], case["valid"], case["p_positive"],
                          case["p_negative"], case["p_positive_legacy"], case["sign_stability"],
                          case["direction_status"]])
        report.extend(["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"])
        for row in table:
            report.append("| " + " | ".join(_md_cell(value, 3) for value in row) + " |")
        report.append("")
        report.append("checks: " + "; ".join(f"{c['check']}={'ok' if c['passed'] else 'FAIL'}"
                                             for c in selftest["checks"]))
        report.append("")
    report.append("## delivered files")
    report.append("")
    report.append("- strict_top3.csv / strict_top3.md, strict_top3_by_method.csv")
    report.append("- extended_top3.csv, extended_top3_by_method.csv")
    report.append("- sign_counts.csv (231 x 50 cells with counts and ratios)")
    report.append("- strict_lowpi_sign_status.csv / .md (every pi < 0.5 row with status and substitutes)")
    report.append("- sign_stability_summary.json (definition, tolerance, seeds, denominators, legacy check)")
    report.append("")
    (export_dir / "sign_stability_report.md").write_text("\n".join(report), encoding="utf-8")
    written.append(export_dir / "sign_stability_report.md")

    manifest = {"generatedBy": "src/q2_fix.py --export-dir (local only)", "primaryRepeat": primary["repeat"],
                "zeroTolerance": float(ZERO_TOL), "bootstrapReps": int(metrics["bootstrap_reps"]),
                "codeSha256": C.sha256_file(Path(__file__)), "files": []}
    for path in written:
        rows_count = None
        if path.suffix == ".csv":
            with open(path, "r", encoding="utf-8") as handle:
                rows_count = sum(1 for _ in handle) - 1
        manifest["files"].append({"path": path.name, "sha256": C.sha256_file(path), "rows": rows_count})
    C.write_json(export_dir / "sign_stability_manifest.json", jsonable(manifest))
    return {"dir": str(export_dir), "files": [record["path"] for record in manifest["files"]],
            "manifest": str(export_dir / "sign_stability_manifest.json")}


# =====================================================================================================
# main
# =====================================================================================================
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Q2 repair run: name alignment, categories, stability")
    parser.add_argument("--repeat", default="all", choices=("all", "0", "1", "2"),
                        help="which protocol repeat(s) to run; 'all' = 0,1,2 in one process (default)")
    parser.add_argument("--reps", type=int, default=N_BOOTSTRAP,
                        help=f"bootstrap replicates per repeat (default {N_BOOTSTRAP}); recorded truthfully")
    parser.add_argument("--self-test", action="store_true",
                        help="run ONLY the direction-stability unit cases and exit (no data, no output files)")
    parser.add_argument("--legacy-root", default=str(PROJECT / "experiments/EXP-0075"),
                        help="directory holding the superseded per-repeat strict_top3.csv records that the "
                             "legacy p_positive column is checked against; unreadable -> reported, not faked")
    parser.add_argument("--export-dir", default=None,
                        help="LOCAL-ONLY: also copy the delivered tables/summaries into this directory. The "
                             "runner sandbox forbids writes outside MODELING_EXPERIMENT_DIR, so the registered "
                             "experiment never passes this flag")
    args = parser.parse_args(argv)
    if args.self_test:
        payload = sign_self_test()
        print(json.dumps(jsonable(payload), ensure_ascii=False, indent=2))
        return 0 if payload["passed"] else 1
    repeats = list(range(C.N_REPEATS)) if args.repeat == "all" else [int(args.repeat)]
    reps = int(args.reps)
    if reps < 10:
        raise RuntimeError("--reps must be at least 10")
    started = time.time()

    if len(C.SEEDS) != C.N_REPEATS:
        raise RuntimeError("v6_common.SEEDS length disagrees with N_REPEATS")
    frame = load_train()
    meta = C.read_json(CHEM_META)
    categories = build_categories(meta)
    mapping = build_mapping(meta)
    boards = {"strict": make_board(categories["strictNames"], "strict"),
              "extended": make_board(categories["extendedNames"], "extended")}
    if set(boards["strict"]["names"]) & set(boards["extended"]["names"]):
        raise RuntimeError("strict and extended boards overlap")
    if boards["strict"]["size"] + boards["extended"]["size"] != N_FEATURES:
        raise RuntimeError("the two boards do not cover the 231 chemistry features")

    # the direction definition is pinned BEFORE any replicate is drawn; a failing case aborts the run
    self_test = sign_self_test()
    if not self_test["passed"]:
        raise RuntimeError(f"direction-stability self-test failed: {self_test}")
    print("[q2_fix] direction self-test passed: " + ", ".join(
        record["check"] for record in self_test["checks"]), flush=True)

    base_out = C.out_dir("q2")   # honours $MODELING_EXPERIMENT_DIR, else state/devrun/v6/q2
    # fixed KEYS (project-relative names) so the payload cannot depend on a sandbox path; a file the runner
    # does not register is recorded as unreadable instead of aborting the run
    source_hashes = {}
    for label, path in (("data/splits/SPLIT-0001/train.csv", TRAIN_CSV),
                        ("data/clean/q1_mapped.csv", CLEAN_CSV),
                        ("data/clean/q2_raw.csv", PROJECT / "data/clean/q2_raw.csv"),
                        ("data/clean/q2_chem_meta.json", CHEM_META),
                        ("data/raw/imported/a55004fb0390299a-6.csv", EXTERNAL_CSV),
                        ("data/processed/sensory_name_alignment.csv", ALIGN_CSV),
                        ("src/q2_fix.py", Path(__file__))):
        try:
            source_hashes[label] = C.sha256_file(path)
        except OSError:
            source_hashes[label] = "unreadable"
    base_scores = pointscores(frame)
    modules = module_lookup(base_scores["graph"])
    for board in boards.values():
        attach_modules(board, modules)
    external = external_corroboration(base_scores["signedTotal"], mapping, categories)

    results = []
    for repeat in repeats:
        out_dir = base_out / f"repeat{repeat}"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[q2_fix] repeat={repeat} seed={C.SEEDS[repeat]} reps={reps} -> {out_dir}", flush=True)
        result = run_repeat(repeat, frame, categories, base_scores, modules, boards, out_dir, reps,
                            legacy_root=Path(args.legacy_root) if args.legacy_root else None,
                            self_test=self_test, source_hashes=source_hashes)
        result["check"] = self_check(out_dir, result["setsPayload"], categories, reps)
        results.append(result)
        print(f"[q2_fix] repeat={repeat} done in {result['elapsed']:.1f}s "
              f"topk-jaccard={result['metrics']['topk-jaccard']:.6f}", flush=True)

    # ---------------------------------------------------------------- pooled metrics
    pooled_jaccard = float(np.mean([result["metrics"]["topk-jaccard"] for result in results]))
    pooled_pi = [row["pi"] for result in results for row in result["repeatPayload"]["top3_strict"]]
    pooled_sign = [row["sign_stability"] for result in results
                   for row in result["repeatPayload"]["top3_strict"]]
    pooled_legacy = [row["p_positive_legacy"] for result in results
                     for row in result["repeatPayload"]["top3_strict"]]
    pooled_rows = [row for result in results for row in result["repeatPayload"]["top3_strict"]]
    metrics = {
        "topk-jaccard": pooled_jaccard,
        **{f"topk-jaccard-rep{result['repeat']}": float(result["metrics"]["topk-jaccard"])
           for result in results},
        "topk-jaccard-point": float(np.mean([result["pointSummary"]["overall"] for result in results])),
        "external_6csv_mean_spearman_aligned": float(external["meanSpearman"]),
        "external_6csv_rows_matched": int(external["nMatched"]),
        "external_6csv_mean_spearman_aligned_strict": float(external["meanSpearmanStrictOnly"]),
        "n_strict_candidates": int(len(categories["strictNames"])),
        "n_extended_candidates": int(len(categories["extendedNames"])),
        "pi_mean": float(np.mean(pooled_pi)),
        "pi_below_0.5_count": int(sum(1 for value in pooled_pi if value < PI_STABLE)),
        "pi_below_0.5_denominator": int(len(pooled_pi)),
        "sign_stability_mean": float(np.mean(pooled_sign)),
        "sign_stability_legacy_mean": float(np.mean(pooled_legacy)),
        "sign_negative_point_count": int(sum(1 for row in pooled_rows
                                            if row["point_direction"] == DIRECTION_NEGATIVE)),
        "sign_direction_undetermined_count": int(sum(1 for row in pooled_rows
                                                    if row["direction_status"] == DIRECTION_UNDETERMINED)),
        "sign_zero_count": int(sum(row["n_zero"] for row in pooled_rows)),
        "sign_invalid_count": int(sum(row["n_invalid"] for row in pooled_rows)),
        "n_dimensions": int(N_DIMENSIONS),
        "n_methods": int(len(METHODS)),
        "n_repeats": int(len(results)),
        "bootstrap_reps": int(reps),
        "seed": int(C.SEEDS[repeats[0]]),
    }
    if external["meanSpearmanSupersededPipeline"] is not None:
        metrics["external_6csv_mean_spearman_superseded_positional"] = float(
            external["meanSpearmanSupersededPipeline"])

    # ---------------------------------------------------------------- cross-repeat agreement
    cross = []
    for left in range(len(results)):
        for right in range(left + 1, len(results)):
            values = [QL.jaccard(results[left]["sets"][method][dimension],
                                 results[right]["sets"][method][dimension])
                      for method in METHODS for dimension in range(N_DIMENSIONS)]
            cross.append({"repeats": [results[left]["repeat"], results[right]["repeat"]],
                          "meanJaccard": float(np.mean(values))})
    if cross:
        metrics["cross_repeat_jaccard"] = float(np.mean([record["meanJaccard"] for record in cross]))
    assert_finite(metrics)

    per_repeat = {f"rep{result['repeat']}": {
        "seed": result["seed"],
        "topk-jaccard": float(result["metrics"]["topk-jaccard"]),
        "topk-jaccard-point": float(result["metrics"]["topk-jaccard-point"]),
        "cross_repeat_vs_first": next((record["meanJaccard"] for record in cross
                                       if record["repeats"][0] == results[0]["repeat"]
                                       and record["repeats"][1] == result["repeat"]), None),
        "n_strict_candidates": int(len(categories["strictNames"])),
        "n_extended_candidates": int(len(categories["extendedNames"])),
        "n_dimensions": int(N_DIMENSIONS),
        "pi_mean": float(result["metrics"]["pi_mean"]),
        "pi_below_0.5_count": int(result["metrics"]["pi_below_0.5_count"]),
        "pi_below_0.5_denominator": int(result["metrics"]["pi_below_0.5_denominator"]),
        "sign_stability_mean": float(result["metrics"]["sign_stability_mean"]),
        "sign_stability_legacy_mean": float(result["metrics"]["sign_stability_legacy_mean"]),
        "sign_negative_point_count": int(result["metrics"]["sign_negative_point_count"]),
        "sign_direction_undetermined_count": int(result["metrics"]["sign_direction_undetermined_count"]),
        "sign_zero_count": int(result["metrics"]["sign_zero_count"]),
        "sign_invalid_count": int(result["metrics"]["sign_invalid_count"]),
        "directionStatusCounts": result["repeatPayload"]["stability"]["directionStatusCounts"],
        "evidenceStatusCounts": result["repeatPayload"]["stability"]["evidenceStatusCounts"],
        "thirdPlaceUnstableCount": int(result["repeatPayload"]["stability"]["thirdPlaceUnstableCount"]),
        "bootstrap_reps": int(reps),
        "seconds": round(result["elapsed"], 1),
        "outDir": str(result["outDir"]),
    } for result in results}

    shared = {
        "mapping": mapping,
        "category_counts": {**{group: len(members) for group, members in categories["groups"].items()},
                            "strictSize": categories["strictSize"],
                            "strictSizeExpected": categories["strictSizeExpected"],
                            "strictSizeMatchesExpected": categories["strictSizeMatchesExpected"],
                            "metaSingleCompoundCount": categories["metaSingleCompoundCount"],
                            "metaReclassified": categories["metaReclassified"],
                            "reason": categories["reason"]},
        "categoryMembers": categories["groups"],
        "modules": modules,
        "external_6csv": external,
        "directionStability": {
            "reference": "point-estimate total Spearman on the 200 SPLIT-0001 train rows",
            "zeroTolerance": float(ZERO_TOL),
            "positive": f"rho > {ZERO_TOL:g}", "negative": f"rho < {-ZERO_TOL:g}",
            "zero": f"|rho| <= {ZERO_TOL:g}", "invalid": "non-finite rho",
            "p_positive": "n_positive / valid", "p_negative": "n_negative / valid",
            "sign_stability": "same-direction-as-point_direction / valid", "valid": "reps - n_invalid",
            "p_positive_legacy": "(rho > 0) / reps (superseded definition, control column)",
            "undetermined": "zero or non-computable point estimate -> 'direction-undetermined', never negative",
            "scope": "direction of the total correlation only; not the low-rank coefficient direction, not "
                     "causal, not accuracy",
            "rankingUnchanged": "the sign fields do not enter the pi-first ranking",
        },
        "method": {"names": list(METHODS), "baseIngredients": list(BASE_METHODS),
                   "consensus": "mean of the three within-dimension percentile ranks over the board's own "
                                "candidate universe",
                   "graph": {"representation": "zscore", **GRAPH_SETTINGS, "tau": TAU},
                   "k": K,
                   "rankingRule": "pi first, then the point-estimate score, then the fixed feature name "
                                  "(Unicode order)"},
        "metricDefinitions": {
            "topk-jaccard": "mean over repeats, the 50 dimensions and the 6 method pairs of "
                            "J = |A n B|/(2k-|A n B|) with k = 3, on the delivered pi-first sets (main metric)",
            "topk-jaccard-point": "same statistic on the point-estimate Top-3 sets",
            "cross_repeat_jaccard": "same statistic between the delivered sets of two repeats",
            "external_6csv_mean_spearman_aligned": "mean over 50 dimensions of Spearman(|our rho|, "
                                                   "|6.csv value|) after name alignment on BOTH sides",
            "pi_mean": "mean selection frequency of the delivered strict entries, pooled over the four methods "
                       "and the repeats run (600 delivered strict entries per repeat)",
            "pi_below_0.5_count": "delivered strict entries with pi < 0.5, pooled over the four methods and the "
                                  "repeats run (denominator = pi_below_0.5_denominator)",
            "sign_stability_mean": "mean share of replicates whose signed total Spearman AGREES with the "
                                   "point-estimate direction (v6 §3) for the delivered strict entries, pooled "
                                   "over the four methods and the repeats run; the superseded (rho > 0) "
                                   "statistic is reported separately as sign_stability_legacy_mean",
            "sign_stability_legacy_mean": "the superseded definition: mean share of replicates with signed "
                                          "total Spearman > 0, same population (control column only)",
            "sign_negative_point_count": "delivered strict entries whose point-estimate total Spearman is "
                                         "negative, pooled over methods and repeats",
            "sign_direction_undetermined_count": "delivered strict entries whose point estimate is exactly "
                                                 "zero (|rho| <= 1e-12) or not computable; these are never "
                                                 "counted as negative",
            "sign_zero_count": "replicates (over the delivered strict entries) whose |signed rho| <= 1e-12, "
                               "pooled; denominator = sign_stability_denominator (see outputs)",
            "sign_invalid_count": "replicates (over the delivered strict entries) whose signed rho is not "
                                  "finite, pooled",
            "n_strict_candidates": "size of the strict single_compound universe",
        },
        "tableSchema": {
            "strict_top3.csv / extended_top3.csv": "the DELIVERED consensus Top-3 (50 dimensions x 3 ranks = "
                                                  "150 rows): the identity columns plus pi/pi_mc_se, the "
                                                  "direction columns (sign_stability, p_positive, p_negative, "
                                                  "p_positive_legacy, n_positive, n_negative, n_zero, "
                                                  "n_invalid, point_direction, direction_status) and "
                                                  "module_id/alternative_rank4/evidence_status",
            "strict_top3_by_method.csv / extended_top3_by_method.csv": "same columns in the same order plus "
                                                                       "`method` as the last column: all four "
                                                                       "methods x 50 dimensions x 3 ranks = 600 "
                                                                       "rows, the full per-method evidence",
            "note": "the requested schema has no method field, so a 600-row file with only those columns would "
                    "let four different sets share one (dimension, rank) key. Splitting the delivered consensus "
                    "table from the by-method evidence avoids that ambiguity.",
            "direction": "kept for backward compatibility with the existing paper/figure scripts, but it is now "
                         "the TRI-STATE point direction (positive / negative / direction-undetermined). The "
                         "superseded rule wrote 'negative' whenever the point estimate was not > 0, so exact "
                         "zeros were silently called negative; that rule is gone. `point_direction` carries the "
                         "same value and `direction_status` the same label set.",
            "point_direction": "the reference direction of the direction-aligned sign_stability: positive / "
                               "negative / direction-undetermined (exactly zero within ZERO_TOL or not "
                               "computable). It never folds a zero or a non-computable value into negative.",
            "evidence_status": "stable / sign-mixed / low-pi / low-pi+sign-mixed as before, plus "
                               "'direction-undetermined' for a zero or non-computable point estimate; the "
                               "sign half of the label now uses the direction-aligned sign_stability.",
            "sign_counts.csv": "all 231 x 50 cells with rho_point_signed, point_direction, n_positive, "
                               "n_negative, n_zero, n_invalid, valid and the three ratios, so every legacy "
                               "and new ratio is reconstructible from files",
            "sign_stability_summary.json": "definition, ZERO_TOL, seeds, reps, denominators, per-repeat "
                                           "counters, the low-pi block, the legacy reproduction check and "
                                           "the self-test cases",
            "alternative_rank4": "the 4th-ranked candidate of the SAME reference module; the literal string "
                                 "'none' means that module has fewer than 4 members (an empty cell would read "
                                 "back as NaN). outputs.module_alternatives then still gives the board-wide "
                                 "next-best candidate in globalFallback, labelled as not same-module.",
        },
        "notes": [
            "6.csv 只做同源对照（与附件同源），不是独立外部验证；它不参与任何 Top-3 选择，读取发生在榜单固定之后。",
            "一致性/稳定性不是准确率：evidence_status 只是稳定性标签（pi 与符号一致性），不是正确性判断。",
            f"方向稳定性（v6 §3）以总体 Spearman 点估计方向为参照：sign_stability = 与 point_direction 同方向的"
            f"重复次数 / 有效次数；|rho| <= {ZERO_TOL:g} 记 zero，非有限值记 invalid，点估计为零或不可计算记 "
            f"direction-undetermined，绝不自动归负。p_positive_legacy 保留旧口径 (rho > 0)/reps 作对照列，"
            f"符号字段不参与排序（仍是 pi 优先）。",
            "不对任何化合物-感官相关做因果解释；这里只有同一批 200 行训练数据上的相关与回归系数。",
            f"严格榜只含 single_compound（{len(categories['strictNames'])} 项）；iron / protein.g.L. / "
            f"betaglucan.mg.L. 归 element_or_index，7 项理化参数与 5 项汇总指标进扩展榜，均不进严格榜。",
            "本轮不加 T/W 双轨，方法仍是 total_spearman / within_style_spearman / graph_lowrank / consensus。",
            f"bootstrap 每个重复 {reps} 次（--reps 可改；实际次数写在 outputs.bootstrap.reps 与 "
            f"metrics.bootstrap_reps，不写死 500）。",
            "交付集（sets.json / strict_top3.csv）用 pi 优先排序；同分先看点估计强度，再按固定特征名。",
            "第 3 名不稳（pi < 0.5）时，同参考模块内排名 4–10 的替代项同时给出（alternative_rank4 与 "
            "outputs.module_alternatives），不隐藏；模块成员不足 4 个时 alternative_rank4 写 'none'，"
            "outputs 里另给 globalFallback（全局次优，标注为非同模块）。",
            "参考模块划分在 tau=0.5 下很不均衡（一个连通分量吸收绝大多数特征），所以“同模块 4–10 名”在多数"
            "维度上接近全局次优候选；每条替代项都同时报 moduleSize，让这一点可见而不是被隐藏。",
            "strict_top3.csv / extended_top3.csv 是 consensus 方法的交付表（150 行，12 列）；四方法完整证据在 "
            "strict_top3_by_method.csv / extended_top3_by_method.csv（600 行，12 列 + method）。",
            "sensory_name_alignment.csv、6.csv、q2_chem_meta.json、train.csv、q1_mapped.csv 的 sha256 记在 "
            "mapping.files。",
            "candidate_scores.csv 的 score 是候选所在榜（严格/扩展）内的 consensus 百分位；pi 是 consensus "
            "方法的选择频率。",
            "bootstrap_pi.csv 记录每次重采样的 Top-3（50 维 × 4 方法 × 3 = 300 行/次），"
            "所以每个 pi 都能从文件无损重建；扩展榜的次数表在同目录 bootstrap_pi_extended.csv。",
            "repeat>0 目录里的 metrics.json 与主目录内容相同（三次重复池化口径）；该次重复自身的指标在 "
            "outputs.json 的 metrics 字段与 per_repeat 里。",
            "strict_lowpi_sign_status.csv 逐项列出交付严格 consensus 表中 pi < 0.5 的条目（状态、四次计数、"
            "同模块排名 4–10 的替代项与全局次优），不把低稳定项包装成稳定关键化合物。",
            "sign_counts.csv 的单位是 (compound, dimension)，与榜单/方法无关；sign_stability_summary.json "
            "每次重复各写一份，repeat 0 那份用 EXP-0075 的记录核对旧口径能否逐位复现。",
        ],
    }

    # ---------------------------------------------------------------- emit: primary through the frozen channel
    primary = results[0]
    primary_dir = primary["outDir"]
    total_seconds = round(time.time() - started, 1)
    run_level = {
        "per_repeat": per_repeat,
        "primary_repeat": primary["repeat"],
        **shared,
        **primary["repeatPayload"],
        "bootstrap": {**primary["repeatPayload"]["bootstrap"],
                      "reps": int(reps), "seeds": [int(C.SEEDS[repeat]) for repeat in repeats],
                      "perRepeat": {str(result["repeat"]): result["repeatPayload"]["bootstrap"]
                                    for result in results}},
        "contract": {"mode": CONTRACT["mode"],
                     "metricsChannel": "v6_common.emit_metrics",
                     "outputsChannel": "v6_common.emit_output('q2', ...)",
                     "note": "repeat 0 goes through the frozen channel; repeats > 0 are written directly by "
                             "this script and are marked as such in their own outputs.json"},
        "code": {"file": "src/q2_fix.py", "sha256": C.sha256_file(Path(__file__)),
                 "repeats": [int(value) for value in repeats], "bootstrapReps": int(reps),
                 "python": sys.version.split()[0]},
        "timing": {"totalSeconds": total_seconds,
                   "perRepeatSeconds": {str(result["repeat"]): round(result["elapsed"], 1)
                                        for result in results}},
    }

    if CONTRACT["mode"] == "local-shim":
        CONTRACT["state"]["directory"] = primary_dir
    C.emit_metrics(jsonable(metrics))
    C.emit_output("q2", jsonable(run_level))
    for name in (FILE_METRICS, FILE_OUTPUTS):
        if not (primary_dir / name).exists():
            print(f"[q2_fix] contract channel wrote no {name}; writing it directly", flush=True)
            if name == FILE_METRICS:
                C.write_json(primary_dir / name, jsonable(metrics))
            else:
                C.write_json(primary_dir / name, {"q2": jsonable(run_level)})

    # non-primary repeats: same schema written directly (documented inside their outputs.json)
    for result in results[1:]:
        directory = result["outDir"]
        payload = {"per_repeat": per_repeat, "primary_repeat": primary["repeat"], **shared,
                   **result["repeatPayload"],
                   "bootstrap": {**result["repeatPayload"]["bootstrap"], "reps": int(reps),
                                 "seeds": [int(C.SEEDS[repeat]) for repeat in repeats],
                                 "perRepeat": {str(item["repeat"]): item["repeatPayload"]["bootstrap"]
                                               for item in results}},
                   "contract": {"mode": CONTRACT["mode"],
                                "note": "repeat > 0 written directly by this script; the frozen contract "
                                        "channel is exercised once for the primary repeat"},
                   "timing": {"totalSeconds": total_seconds,
                              "perRepeatSeconds": {str(item["repeat"]): round(item["elapsed"], 1)
                                                   for item in results}}}
        C.write_json(directory / FILE_METRICS, jsonable(metrics))
        C.write_json(directory / FILE_OUTPUTS, {"q2": jsonable(payload)})

    # ---------------------------------------------------------------- copy the primary artefacts to the root
    for name in (FILE_SETS, FILE_STRICT, FILE_STRICT_METHODS, FILE_EXTENDED, FILE_EXTENDED_METHODS,
                 FILE_CANDIDATES, FILE_BOOT, FILE_BOOT_EXT, FILE_SIGN_COUNTS, FILE_LOWPI,
                 FILE_SIGN_SUMMARY, FILE_METRICS, FILE_OUTPUTS):
        source = primary_dir / name
        target = base_out / name
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)

    exported = export_deliverables(base_out, Path(args.export_dir), results, metrics) \
        if args.export_dir else None

    summary = {
        "repeats": repeats,
        "seedPerRepeat": {str(result["repeat"]): result["seed"] for result in results},
        "topk-jaccard": pooled_jaccard,
        "topk-jaccard-per-repeat": {f"rep{result['repeat']}": float(result["metrics"]["topk-jaccard"])
                                    for result in results},
        "external_6csv_mean_spearman_aligned": metrics["external_6csv_mean_spearman_aligned"],
        "external_6csv_rows_matched": metrics["external_6csv_rows_matched"],
        "n_strict_candidates": metrics["n_strict_candidates"],
        "pi_mean": metrics["pi_mean"],
        "pi_below_0.5_count": metrics["pi_below_0.5_count"],
        "pi_below_0.5_denominator": metrics["pi_below_0.5_denominator"],
        "sign_stability_mean": metrics["sign_stability_mean"],
        "sign_stability_legacy_mean": metrics["sign_stability_legacy_mean"],
        "sign_negative_point_count": metrics["sign_negative_point_count"],
        "sign_direction_undetermined_count": metrics["sign_direction_undetermined_count"],
        "sign_zero_count": metrics["sign_zero_count"],
        "sign_invalid_count": metrics["sign_invalid_count"],
        "zeroTolerance": float(ZERO_TOL),
        "selfTestPassed": bool(self_test["passed"]),
        "bootstrap_reps": metrics["bootstrap_reps"],
        "totalSeconds": total_seconds,
        "setsEntries": N_DIMENSIONS * len(METHODS),
        "selfChecks": {str(result["repeat"]): result["check"] for result in results},
        "legacyReproduction": {str(result["repeat"]): result["signSummary"]["legacyReproduction"]
                               for result in results},
        "exported": exported,
        "outDir": str(base_out),
        "primaryDir": str(primary_dir),
    }
    print(json.dumps(jsonable(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
