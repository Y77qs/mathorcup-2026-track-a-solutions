#!/usr/bin/env python
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q2_v62_regen.py — deterministic rebuild of the Q2 v6.2 delivered tables from SAVED artefacts only.

WHY THIS SCRIPT EXISTS.  `src/q2_fix.py` delivered the Q2 Top-3 tables as experiment EXP-0107.  One defect
survived in the delivered tables: the same-module substitute candidate (`alternative_rank4`, and the
`module_rank4_to_10` pool of `strict_lowpi_sign_status.csv`) was taken as the 4th member of the module WITHOUT
excluding the Top-3 that had just been delivered, so the "substitute" repeated a compound that is already in
the table (34 of the 150 strict consensus rows, 11 of them at rank 3, for repeat 0).  The SOURCE fix is in
`src/q2_fix.py::module_alternatives()` / `module_alternative_report()`: build the candidate list after removing
the delivered set.

Re-running the 500-replicate bootstrap is forbidden here (deterministic post-processing only, and it would
retrain every model), so this script RE-DERIVES every delivered table from the artefacts EXP-0107 already
saved:

    experiments/EXP-0107/repeat{r}/candidate_scores.csv        point scores + consensus percentile + pi
    experiments/EXP-0107/repeat{r}/bootstrap_pi.csv           500 x 50 x 4 x 3 strict Top-3 records -> pi
    experiments/EXP-0107/repeat{r}/bootstrap_pi_extended.csv  the same for the extended board
    experiments/EXP-0107/repeat{r}/sign_counts.csv            per-cell sign counts + point-estimate rho
    experiments/EXP-0107/repeat{r}/outputs.json               q2.modules.perCompound (moduleId / size)
    data/splits/SPLIT-0001/train.csv                          only for the bootstrap stratification counts

THE PIPELINE IS REPRODUCED EXACTLY (`src/q_common.py::percentile_rank`, `board_ranked`, `order_by_pi`,
`delivered_table` and the evidence-status rule of `src/q2_fix.py`).  `candidate_scores.csv`'s `score` and `pi`
columns are used as an INDEPENDENT CROSS-CHECK, not as the primary source.  Only the substitute candidate
changes; every other cell of the five regenerated CSVs is compared cell-for-cell against the original
EXP-0107 file (floats within 1e-12, strings identical) — a difference is a hard failure, never "fixed" by
editing a number.

OUTPUTS (all under outputs/q2/v62_clean/)
    repeat{r}/strict_top3.csv                150 rows, delivered consensus Top-3
    repeat{r}/strict_top3_by_method.csv      600 rows, four methods
    repeat{r}/extended_top3.csv              150 rows
    repeat{r}/extended_top3_by_method.csv    600 rows
    repeat{r}/strict_lowpi_sign_status.csv   consensus rows with pi < 0.5 + non-delivered substitute pool
    repeat{r}/sign_stability_summary.json    the original summary fields + the three-denominator block
    sign_stability_summary.json              final top-level summary (three repeats + pooled values)
    v62_manifest.json                        source sha256s, output sha256s, every assertion
    REPORT.md                                short human-readable witness (Chinese)

Run:
    python src/q2_v62_regen.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
EXP = PROJECT / "experiments" / "EXP-0107"
OLD_REFERENCE_DIR = PROJECT / "experiments" / "EXP-0075"
TRAIN_CSV = PROJECT / "data/splits/SPLIT-0001/train.csv"
OUT = PROJECT / "outputs" / "q2" / "v62_clean"
SUBMISSION = PROJECT / "FINAL_SUBMISSION_v6.2" / "支撑材料" / "outputs" / "q2"

REPEATS = (0, 1, 2)
EXPECTED_SEEDS = (20261025, 20261026, 20261027)
METHODS = ("total_spearman", "within_style_spearman", "graph_lowrank", "consensus")
BASE_METHODS = METHODS[:3]
K = 3
N_DIMENSIONS = 50
N_FEATURES = 231
N_BOOTSTRAP = 500
PI_STABLE = 0.5
SIGN_STABLE = 0.9
ZERO_TOL = 1e-12
FLOAT_TOLERANCE = 1e-12
STYLE_COL = "tasting_category_fine"
NO_ALTERNATIVE = "none"
DIRECTION_UNDETERMINED = "direction-undetermined"
DIRECTION_POSITIVE = "positive"
DIRECTION_NEGATIVE = "negative"
BUCKET_POSITIVE, BUCKET_NEGATIVE, BUCKET_ZERO, BUCKET_INVALID = "positive", "negative", "zero", "invalid"
BUCKET_KEYS = (BUCKET_POSITIVE, BUCKET_NEGATIVE, BUCKET_ZERO, BUCKET_INVALID)

TOP3_HEADER = ["dimension", "rank", "compound", "kind", "score", "pi", "pi_mc_se", "sign_stability",
               "direction", "p_positive", "p_negative", "p_positive_legacy", "n_positive", "n_negative",
               "n_zero", "n_invalid", "point_direction", "direction_status", "module_id",
               "alternative_rank4", "alternative_first_valid", "evidence_status"]
TOP3_HEADER_METHOD = TOP3_HEADER + ["method"]
LOWPI_HEADER = ["dimension", "rank", "compound", "kind", "pi", "pi_mc_se", "point_direction",
                "p_positive", "p_negative", "p_positive_legacy", "n_positive", "n_negative", "n_zero",
                "n_invalid", "sign_stability", "direction_status", "evidence_status", "module_id",
                "module_size", "alternative_rank4", "alternative_first_valid", "module_rank4_to_10",
                "same_module_alternative_exists",
                "global_fallback"]
#: the columns whose VALUE is allowed to change (that is the bug being fixed); everything else is regression-checked
EXCLUDED_COLUMNS = ("alternative_rank4", "module_rank4_to_10", "same_module_alternative_exists")

ASSERTIONS: list = []


# =====================================================================================================
# small helpers
# =====================================================================================================
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> tuple:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return rows[0], rows[1:]


def write_csv(path: Path, header: list, rows: list) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
    return len(rows)


def fmt(value) -> str:
    """Shortest round-trip text for a float (same helper as src/q2_fix.py)."""
    return repr(float(value))


def jsonable(value):
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
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


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check(identifier: str, condition: bool, detail) -> None:
    """Record an assertion; a failing assertion aborts the run instead of being reported as a pass."""
    ok = bool(condition)
    ASSERTIONS.append({"id": identifier, "passed": ok, "detail": jsonable(detail)})
    if not ok:
        raise RuntimeError(f"ASSERTION FAILED [{identifier}]: {detail}")


# =====================================================================================================
# direction definition — ported verbatim from src/q2_fix.py (one definition, no drift)
# =====================================================================================================
def sign_buckets(replicate_signed, zero_tol: float = ZERO_TOL) -> dict:
    values = np.asarray(replicate_signed, dtype=float)
    finite = np.isfinite(values)
    return {
        BUCKET_POSITIVE: finite & (values > zero_tol),
        BUCKET_NEGATIVE: finite & (values < -zero_tol),
        BUCKET_ZERO: finite & (np.abs(values) <= zero_tol),
        BUCKET_INVALID: ~finite,
        "legacyPositive": values > 0,
    }


def point_direction_of(value: float, zero_tol: float = ZERO_TOL) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DIRECTION_UNDETERMINED
    if not math.isfinite(number) or abs(number) <= zero_tol:
        return DIRECTION_UNDETERMINED
    return DIRECTION_POSITIVE if number > 0.0 else DIRECTION_NEGATIVE


def sign_fields(n_positive: int, n_negative: int, n_zero: int, n_invalid: int, legacy_positive: int,
                reps: int, point_value: float, zero_tol: float = ZERO_TOL) -> dict:
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
    values = np.asarray(replicate_signed, dtype=float).ravel()
    buckets = sign_buckets(values, zero_tol)
    return sign_fields(int(buckets[BUCKET_POSITIVE].sum()), int(buckets[BUCKET_NEGATIVE].sum()),
                       int(buckets[BUCKET_ZERO].sum()), int(buckets[BUCKET_INVALID].sum()),
                       int(buckets["legacyPositive"].sum()), int(values.size), point_value, zero_tol)


def self_test(zero_tol: float = ZERO_TOL) -> dict:
    """The hand-built definition cases of src/q2_fix.py::sign_self_test — reproduced, not quoted."""
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

    def check_case(name, condition, detail):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    by_case = {record["case"]: record for record in cases}
    check_case("stable-positive.sign_stability==1", by_case["stable-positive"]["sign_stability"] == 1.0,
               by_case["stable-positive"]["sign_stability"])
    check_case("stable-negative.sign_stability==1", by_case["stable-negative"]["sign_stability"] == 1.0,
               by_case["stable-negative"]["sign_stability"])
    check_case("stable-negative.legacy==0 (the superseded bug)",
               by_case["stable-negative"]["p_positive_legacy"] == 0.0,
               by_case["stable-negative"]["p_positive_legacy"])
    check_case("alternating.sign_stability==0.5",
               abs(by_case["alternating-signs"]["sign_stability"] - 0.5) <= 1e-12,
               by_case["alternating-signs"]["sign_stability"])
    check_case("all-zero.status==direction-undetermined",
               by_case["all-zero"]["direction_status"] == DIRECTION_UNDETERMINED,
               by_case["all-zero"]["direction_status"])
    check_case("all-zero.n_zero==reps", by_case["all-zero"]["n_zero"] == reps, by_case["all-zero"]["n_zero"])
    check_case("all-zero.sign_stability==0", by_case["all-zero"]["sign_stability"] == 0.0,
               by_case["all-zero"]["sign_stability"])
    check_case("all-invalid.n_invalid==reps and valid==0",
               by_case["all-invalid"]["n_invalid"] == reps and by_case["all-invalid"]["valid"] == 0,
               [by_case["all-invalid"]["n_invalid"], by_case["all-invalid"]["valid"]])
    check_case("all-invalid.status==direction-undetermined",
               by_case["all-invalid"]["direction_status"] == DIRECTION_UNDETERMINED,
               by_case["all-invalid"]["direction_status"])
    check_case("near-zero.all_bucketed_as_zero", by_case["near-zero-tolerance"]["n_zero"] == reps,
               by_case["near-zero-tolerance"]["n_zero"])
    check_case("alternating.p_positive==p_negative==0.5",
               abs(by_case["alternating-signs"]["p_positive"] - 0.5) <= 1e-12
               and abs(by_case["alternating-signs"]["p_negative"] - 0.5) <= 1e-12,
               [by_case["alternating-signs"]["p_positive"], by_case["alternating-signs"]["p_negative"]])
    passed = all(record["passed"] for record in checks)
    return {"zeroTolerance": float(zero_tol), "reps": reps, "cases": cases, "checks": checks,
            "passed": passed,
            "note": "hand-built vectors only; the definition is fixed before any real replicate is looked at"}


# =====================================================================================================
# ranking primitives — byte-for-byte logic of src/q_common.py / src/q2_fix.py
# =====================================================================================================
def percentile_rank(values: np.ndarray) -> np.ndarray:
    """Exact replica of q_common.percentile_rank: column-wise stable order, ranks/(n-1), no tie averaging."""
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, axis=0, kind="mergesort")
    ranks = np.empty_like(values)
    for column in range(values.shape[1]):
        ranks[order[:, column], column] = np.arange(values.shape[0], dtype=float)
    return ranks / max(values.shape[0] - 1, 1)


def make_board(names: list, label: str, feature_index: dict) -> dict:
    rows = np.asarray([feature_index[name] for name in names], dtype=int)
    name_rank = {name: rank for rank, name in enumerate(sorted(names))}
    return {"label": label, "names": list(names), "rows": rows,
            "nameRank": np.asarray([name_rank[name] for name in names], dtype=int),
            "index": {name: local for local, name in enumerate(names)}, "size": len(names),
            "byModule": {}}


def board_ranked(abs_scores: dict, board: dict) -> dict:
    rows = board["rows"]
    ranked = {method: percentile_rank(abs_scores[method][rows, :]) for method in BASE_METHODS}
    ranked["consensus"] = (ranked["total_spearman"] + ranked["within_style_spearman"]
                           + ranked["graph_lowrank"]) / 3.0
    for method in METHODS:
        if ranked[method].shape != (board["size"], N_DIMENSIONS):
            raise RuntimeError(f"{board['label']}/{method}: percentile block has the wrong shape")
    return ranked


def order_by_pi(ranked: dict, pi: dict, board: dict) -> dict:
    out = {}
    rows = board["rows"]
    for method in METHODS:
        matrix = ranked[method]
        out[method] = [np.lexsort((board["nameRank"], -matrix[:, dimension],
                                   -pi[method][rows, dimension]))[:K].tolist()
                       for dimension in range(N_DIMENSIONS)]
    return out


# =====================================================================================================
# the FIXED substitute rule — same body as the repaired src/q2_fix.py::module_alternatives
# =====================================================================================================
def module_alternatives(method: str, dimension: int, module_id: int, board: dict, ranked: dict,
                        delivered: set) -> tuple:
    members = board["byModule"].get(module_id, [])
    if not members:
        return NO_ALTERNATIVE, []
    score = ranked[method]
    ordered = sorted(members, key=lambda name: (-float(score[board["index"][name], dimension]), name))
    candidates = [name for name in ordered if name not in delivered]
    alternative = candidates[0] if candidates else NO_ALTERNATIVE
    return alternative, [name for name in candidates[:10] if name not in delivered]


def module_alternative_report(table: list, board: dict, ranked: dict) -> list:
    delivered_by_cell = {}
    for row in table:
        delivered_by_cell.setdefault((row["method"], row["dimension"]), set()).add(row["compound"])
    out = []
    for row in table:
        method, dimension = row["method"], row["dimension_index"]
        members = board["byModule"].get(row["module_id"], [])
        score = ranked[method][:, dimension]
        ordered = sorted(members, key=lambda name: (-float(score[board["index"][name]]), name))
        delivered = delivered_by_cell[(method, row["dimension"])]
        candidates = [name for name in ordered if name not in delivered]
        global_order = sorted(board["names"], key=lambda name: (-float(score[board["index"][name]]), name))
        fallback = next((name for name in global_order if name not in delivered), NO_ALTERNATIVE)
        out.append({"dimension": row["dimension"], "method": method, "rank": row["rank"],
                    "compound": row["compound"], "pi": row["pi"], "moduleId": row["module_id"],
                    "moduleSize": len(members), "moduleOrder": ordered[:10],
                    "moduleRank4To10": candidates[:10],
                    "sameModuleAlternativeExists": bool(candidates),
                    "globalFallback": fallback})
    return out


def delivered_table(board: dict, ranked: dict, pi: dict, sign: dict, modules: dict, kind_of: dict,
                    reps: int, zero_tol: float = ZERO_TOL) -> tuple:
    """The delivered pi-first Top-3 table, per method in METHODS order (logic of q2_fix.delivered_table)."""
    chosen = order_by_pi(ranked, pi, board)
    rows, sets = [], {method: [] for method in METHODS}
    for method in METHODS:
        for dimension_index in range(N_DIMENSIONS):
            dimension = DIMENSION_NAMES[dimension_index]
            picked = [board["names"][int(local)] for local in chosen[method][dimension_index]]
            if len(set(picked)) != K:
                raise RuntimeError(f"{board['label']}/{method}/{dimension}: duplicate names in a Top-3 set")
            sets[method].append(picked)
            delivered = set(picked)
            for rank, local in enumerate(chosen[method][dimension_index]):
                name = board["names"][int(local)]
                grow = int(board["rows"][int(local)])
                value = float(pi[method][grow, dimension_index])
                legacy_positive = int(round(float(sign["p_positive_legacy"][grow, dimension_index]) * reps))
                fields = sign_fields(
                    int(sign["n_positive"][grow, dimension_index]),
                    int(sign["n_negative"][grow, dimension_index]),
                    int(sign["n_zero"][grow, dimension_index]),
                    int(sign["n_invalid"][grow, dimension_index]),
                    legacy_positive, int(reps),
                    float(sign["rho_point"][grow, dimension_index]), zero_tol)
                alternative, _pool = module_alternatives(
                    method, dimension_index, modules["perCompound"][name]["moduleId"], board, ranked,
                    delivered)
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
                    "dimension": dimension, "dimension_index": dimension_index, "rank": rank + 1,
                    "compound": name, "kind": kind_of[name], "method": method,
                    "score": float(ranked[method][int(local), dimension_index]),
                    "pi": value,
                    "pi_mc_se": math.sqrt(max(value * (1.0 - value), 0.0) / float(reps)),
                    "sign_stability": fields["sign_stability"],
                    "direction": fields["point_direction"],
                    "p_positive": fields["p_positive"], "p_negative": fields["p_negative"],
                    "p_positive_legacy": fields["p_positive_legacy"],
                    "n_positive": fields["n_positive"], "n_negative": fields["n_negative"],
                    "n_zero": fields["n_zero"], "n_invalid": fields["n_invalid"],
                    "point_direction": fields["point_direction"],
                    "direction_status": fields["direction_status"],
                    "module_id": int(modules["perCompound"][name]["moduleId"]),
                    "alternative_rank4": alternative, "alternative_first_valid": alternative,
                    "evidence_status": status,
                })
    return rows, sets


def low_pi_rows(table: list, module_report: list, pi_threshold: float = PI_STABLE) -> list:
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
            "alternative_first_valid": row["alternative_rank4"],
            "module_rank4_to_10": "; ".join(pool) if pool else NO_ALTERNATIVE,
            "same_module_alternative_exists": bool(record.get("sameModuleAlternativeExists", False)),
            "global_fallback": record.get("globalFallback", NO_ALTERNATIVE),
        })
    return out


# =====================================================================================================
# artefact loading + independent reconstruction cross-checks
# =====================================================================================================
DIMENSION_NAMES: list = []


def _matrix_from_frame(frame: pd.DataFrame, column: str, name_index: dict, dim_index: dict) -> np.ndarray:
    matrix = np.full((N_FEATURES, N_DIMENSIONS), np.nan, dtype=float)
    rows = np.asarray([name_index[name] for name in frame["compound"]], dtype=int)
    cols = np.asarray([dim_index[dimension] for dimension in frame["dimension"]], dtype=int)
    # Python's float() is correctly rounded; the pandas fast parser can be 1 ulp off, which is enough to
    # turn the independent candidate_scores.csv cross-check into a spurious "difference".
    matrix[rows, cols] = np.asarray([float(item) for item in frame[column].tolist()], dtype=float)
    if not np.isfinite(matrix).all():
        raise RuntimeError(f"column {column!r} does not cover all {N_FEATURES} x {N_DIMENSIONS} cells")
    return matrix


def load_repeat(repeat: int) -> dict:
    root = EXP / f"repeat{repeat}"
    candidate = pd.read_csv(root / "candidate_scores.csv", dtype=str)
    if candidate.shape != (N_FEATURES * N_DIMENSIONS, 8):
        raise RuntimeError(f"repeat{repeat}: candidate_scores.csv shape {candidate.shape} is not 231x50")
    names = list(dict.fromkeys(candidate["compound"].tolist()))
    dimensions = list(dict.fromkeys(candidate["dimension"].tolist()))
    global DIMENSION_NAMES
    DIMENSION_NAMES = dimensions
    if len(names) != N_FEATURES or len(dimensions) != N_DIMENSIONS:
        raise RuntimeError(f"repeat{repeat}: {len(names)} compounds / {len(dimensions)} dimensions")
    if not candidate.groupby("compound", sort=False).size().eq(N_DIMENSIONS).all():
        raise RuntimeError(f"repeat{repeat}: candidate file is not name-major with all 50 dimensions")
    if not candidate.groupby("dimension", sort=False).size().eq(N_FEATURES).all():
        raise RuntimeError(f"repeat{repeat}: candidate file does not cover all 231 compounds per dimension")
    name_index = {name: position for position, name in enumerate(names)}
    dim_index = {dimension: position for position, dimension in enumerate(dimensions)}

    kinds = candidate.drop_duplicates("compound").set_index("compound")["kind"].to_dict()
    kind_values = set(kinds.values())
    if kind_values != {"single_compound", "element_or_index", "physical_parameter", "derived_sum"}:
        raise RuntimeError(f"repeat{repeat}: unexpected kind values {sorted(kind_values)}")
    strict_names = [name for name in names if kinds[name] == "single_compound"]
    extended_names = [name for name in names if kinds[name] != "single_compound"]
    if (len(strict_names), len(extended_names)) != (216, 15):
        raise RuntimeError(f"repeat{repeat}: strict/extended split is "
                           f"{len(strict_names)}/{len(extended_names)}, expected 216/15")

    signed_total = _matrix_from_frame(candidate, "rho_total", name_index, dim_index)
    within_signed = _matrix_from_frame(candidate, "rho_within", name_index, dim_index)
    graph_signed = _matrix_from_frame(candidate, "beta_graphlowrank", name_index, dim_index)
    stored_score = _matrix_from_frame(candidate, "score", name_index, dim_index)
    stored_pi = _matrix_from_frame(candidate, "pi", name_index, dim_index)

    # ---- pi from the saved per-replicate Top-3 records (never re-drawn) ----
    # a cell that is never selected in any of the 500 replicates has pi = 0, so start from zeros
    pi = {method: np.zeros((N_FEATURES, N_DIMENSIONS), dtype=float) for method in METHODS}
    seeds = set()
    partition = {method: np.zeros(N_DIMENSIONS, dtype=int) for method in METHODS}
    for filename, board_names in (("bootstrap_pi.csv", strict_names),
                                  ("bootstrap_pi_extended.csv", extended_names)):
        boot = pd.read_csv(root / filename)
        if len(boot) != N_BOOTSTRAP * N_DIMENSIONS * len(METHODS) * K:
            raise RuntimeError(f"repeat{repeat}/{filename}: {len(boot)} rows, expected "
                               f"{N_BOOTSTRAP * N_DIMENSIONS * len(METHODS) * K}")
        seeds.update(int(value) for value in boot["seed"].unique())
        grouped = boot.groupby(["dimension", "method", "compound"], sort=False).size().reset_index(name="count")
        board_set = set(board_names)
        if not set(grouped["compound"]) <= board_set:
            raise RuntimeError(f"repeat{repeat}/{filename}: a compound outside its board")
        rows = np.asarray([name_index[name] for name in grouped["compound"]], dtype=int)
        cols = np.asarray([dim_index[dimension] for dimension in grouped["dimension"]], dtype=int)
        methods = np.asarray([METHODS.index(method) for method in grouped["method"]], dtype=int)
        counts = grouped["count"].to_numpy(dtype=float)
        if counts.max() > N_BOOTSTRAP:
            raise RuntimeError(f"repeat{repeat}/{filename}: a selection count exceeds {N_BOOTSTRAP}")
        for position, method in enumerate(METHODS):
            mask = methods == position
            pi[method][rows[mask], cols[mask]] = counts[mask] / float(N_BOOTSTRAP)
            np.add.at(partition[method], cols[mask], counts[mask].astype(int))
    for method in METHODS:
        # two boards x K picks x N_BOOTSTRAP replicates per (method, dimension)
        expected_partition = 2 * K * N_BOOTSTRAP
        if not np.array_equal(partition[method], np.full(N_DIMENSIONS, expected_partition, dtype=int)):
            raise RuntimeError(f"repeat{repeat}/{method}: per-dimension selection counts do not sum to "
                               f"{expected_partition}")
    if seeds != {EXPECTED_SEEDS[repeat]}:
        raise RuntimeError(f"repeat{repeat}: bootstrap seeds {sorted(seeds)} != {EXPECTED_SEEDS[repeat]}")

    # ---- sign counts from sign_counts.csv ----
    sign_frame = pd.read_csv(root / "sign_counts.csv", dtype=str)
    if len(sign_frame) != N_FEATURES * N_DIMENSIONS:
        raise RuntimeError(f"repeat{repeat}: sign_counts.csv has {len(sign_frame)} rows")
    sign = {}
    for column in ("n_positive", "n_negative", "n_zero", "n_invalid"):
        sign[column] = _matrix_from_frame(sign_frame, column, name_index, dim_index).astype(int)
    sign["rho_point"] = _matrix_from_frame(sign_frame, "rho_point_signed", name_index, dim_index)
    sign["p_positive_legacy"] = _matrix_from_frame(sign_frame, "p_positive_legacy", name_index, dim_index)
    if not np.array_equal(sign["n_positive"] + sign["n_negative"] + sign["n_zero"] + sign["n_invalid"],
                          np.full((N_FEATURES, N_DIMENSIONS), N_BOOTSTRAP, dtype=int)):
        raise RuntimeError(f"repeat{repeat}: sign counts do not partition {N_BOOTSTRAP} replicates")
    if not np.array_equal(sign["rho_point"], signed_total):
        raise RuntimeError(f"repeat{repeat}: sign_counts rho_point_signed != candidate rho_total")

    # ---- modules from the saved outputs.json ----
    outputs = json.loads((root / "outputs.json").read_text(encoding="utf-8"))
    modules = outputs["q2"]["modules"]
    per_compound = modules["perCompound"]
    if set(per_compound) != set(names):
        raise RuntimeError(f"repeat{repeat}: outputs.json module map does not cover the 231 compounds")

    # ---- boards (strict / extended) ----
    boards = {"strict": make_board(strict_names, "strict", name_index),
              "extended": make_board(extended_names, "extended", name_index)}
    for board in boards.values():
        groups = {}
        for name in board["names"]:
            groups.setdefault(per_compound[name]["moduleId"], []).append(name)
        board["byModule"] = groups

    abs_scores = {"total_spearman": np.abs(signed_total),
                  "within_style_spearman": np.abs(within_signed),
                  "graph_lowrank": np.abs(graph_signed)}

    # ---- INDEPENDENT cross-check: candidate_scores.csv score / pi columns must be reproduced ----
    score_diffs, pi_diffs = [], []
    for label, board in boards.items():
        ranked = board_ranked(abs_scores, board)
        rows = board["rows"]
        score_diffs.append(np.abs(ranked["consensus"] - stored_score[rows, :]))
        pi_diffs.append(np.abs(pi["consensus"][rows, :] - stored_pi[rows, :]))
    max_score_diff = float(max(diff.max() for diff in score_diffs))
    max_pi_diff = float(max(diff.max() for diff in pi_diffs))
    check(f"reconstruct.repeat{repeat}.candidate_score",
          max_score_diff <= FLOAT_TOLERANCE,
          {"maxAbsDiff": max_score_diff, "tolerance": FLOAT_TOLERANCE,
           "detail": "重建的 consensus 百分位分与 candidate_scores.csv 的 score 列一致（仅允许浮点末位误差）"})
    check(f"reconstruct.repeat{repeat}.candidate_pi",
          max_pi_diff == 0.0,
          {"maxAbsDiff": max_pi_diff,
           "detail": "由 bootstrap_pi*.csv 重建的 pi 与 candidate_scores.csv 的 pi 列逐位一致"})

    return {
        "repeat": repeat, "seed": EXPECTED_SEEDS[repeat], "root": root,
        "names": names, "dimensions": dimensions, "name_index": name_index, "dim_index": dim_index,
        "kind": kinds, "boards": boards, "abs_scores": abs_scores,
        "signed_total": signed_total, "pi": pi, "sign": sign,
        "modules": {"perCompound": per_compound},
        "stored_score": stored_score, "stored_pi": stored_pi,
    }


# =====================================================================================================
# writing the five regenerated CSVs
# =====================================================================================================
def table_rows(rows: list, with_method: bool = False) -> list:
    out = []
    for row in rows:
        line = [row[key] for key in TOP3_HEADER]
        if with_method:
            line.append(row["method"])
        out.append([fmt(value) if isinstance(value, float) else value for value in line])
    return out


def low_pi_payload(rows: list) -> list:
    return [[row[key] for key in LOWPI_HEADER] for row in rows]


def write_repeat_tables(data: dict) -> dict:
    repeat = data["repeat"]
    out_dir = OUT / f"repeat{repeat}"
    tables, ranked = {}, {}
    for label, board in data["boards"].items():
        ranked[label] = board_ranked(data["abs_scores"], board)
        tables[label], _sets = delivered_table(board, ranked[label], data["pi"], data["sign"],
                                               data["modules"], data["kind"], N_BOOTSTRAP)
    consensus = {label: [row for row in tables[label] if row["method"] == "consensus"]
                 for label in data["boards"]}
    module_report = module_alternative_report(tables["strict"], data["boards"]["strict"], ranked["strict"])
    module_report_extended = module_alternative_report(tables["extended"], data["boards"]["extended"],
                                                       ranked["extended"])
    lowpi = low_pi_rows(tables["strict"], module_report)
    written = {
        "strict_top3.csv": (TOP3_HEADER, table_rows(consensus["strict"])),
        "strict_top3_by_method.csv": (TOP3_HEADER_METHOD, table_rows(tables["strict"], True)),
        "extended_top3.csv": (TOP3_HEADER, table_rows(consensus["extended"])),
        "extended_top3_by_method.csv": (TOP3_HEADER_METHOD, table_rows(tables["extended"], True)),
        "strict_lowpi_sign_status.csv": (LOWPI_HEADER, low_pi_payload(lowpi)),
    }
    for name, (header, rows) in written.items():
        write_csv(out_dir / name, header, rows)
    return {"repeat": repeat, "tables": tables, "consensus": consensus, "ranked": ranked,
            "module_report": module_report, "module_report_extended": module_report_extended,
            "lowpi": lowpi, "lowpi_summary": {
                "count": len(lowpi), "file": "strict_lowpi_sign_status.csv",
                "statusCounts": {status: int(sum(1 for row in lowpi if row["evidence_status"] == status))
                                 for status in sorted({row["evidence_status"] for row in lowpi})},
                "directionCounts": {direction: int(sum(1 for row in lowpi
                                                       if row["direction_status"] == direction))
                                    for direction in sorted({row["direction_status"] for row in lowpi})}},
            "written": written}


# =====================================================================================================
# regression check: every non-excluded cell against the original EXP-0107 file
# =====================================================================================================
def read_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str)


def compare_regression(original_path: Path, regenerated_path: Path) -> dict:
    header_original, rows_original = read_rows(original_path)
    header_new, rows_new = read_rows(regenerated_path)
    expected_new_header = list(header_original)
    if "alternative_rank4" in expected_new_header:
        expected_new_header.insert(expected_new_header.index("alternative_rank4") + 1,
                                   "alternative_first_valid")
    if header_new != expected_new_header:
        raise RuntimeError(f"regression: header changed for {regenerated_path.name}: "
                           f"{header_original} -> {header_new}")
    if len(rows_original) != len(rows_new):
        raise RuntimeError(f"regression: row count changed for {regenerated_path.name}: "
                           f"{len(rows_original)} -> {len(rows_new)}")
    columns = {name: {"compared": 0, "exactStringMatches": 0, "floatWithinTolerance": 0,
                      "failed": 0, "maxAbsDiff": 0.0}
               for name in header_original}
    excluded = {name: {"compared": 0, "changed": 0} for name in EXCLUDED_COLUMNS if name in header_original}
    failures = []
    index_new = {name: position for position, name in enumerate(header_new)}
    for row_index, (old_row, new_row) in enumerate(zip(rows_original, rows_new)):
        for column_index, name in enumerate(header_original):
            old_value, new_value = old_row[column_index], new_row[index_new[name]]
            if name in EXCLUDED_COLUMNS:
                excluded[name]["compared"] += 1
                if old_value != new_value:
                    excluded[name]["changed"] += 1
                continue
            record = columns[name]
            record["compared"] += 1
            if old_value == new_value:
                record["exactStringMatches"] += 1
                continue
            try:
                old_number, new_number = float(old_value), float(new_value)
            except ValueError:
                failures.append({"row": row_index, "column": name, "original": old_value,
                                 "regenerated": new_value, "reason": "string mismatch"})
                record["failed"] += 1
                continue
            difference = abs(old_number - new_number)
            record["maxAbsDiff"] = max(record["maxAbsDiff"], difference)
            if difference <= FLOAT_TOLERANCE:
                record["floatWithinTolerance"] += 1
            else:
                record["failed"] += 1
                failures.append({"row": row_index, "column": name, "original": old_value,
                                 "regenerated": new_value, "absDiff": difference})
    passed = not failures
    cells_compared = sum(record["compared"] for record in columns.values())
    totals = {
        "cellsCompared": int(cells_compared),
        "exactStringMatches": int(sum(record["exactStringMatches"] for record in columns.values())),
        "floatWithinTolerance": int(sum(record["floatWithinTolerance"] for record in columns.values())),
        "maxAbsDiff": float(max(record["maxAbsDiff"] for record in columns.values())),
    }
    check(f"regression.{regenerated_path.parent.name}.{regenerated_path.name}", passed,
          {"file": str(regenerated_path.relative_to(OUT)), "rows": len(rows_new),
           "columnsCompared": len(header_original), "excludedColumns": list(EXCLUDED_COLUMNS),
           "failures": failures[:5], "failureCount": len(failures),
           "detail": "除 alternative_rank4 / module_rank4_to_10 / same_module_alternative_exists 外，"
                     "所有单元格与原 EXP-0107 文件逐格一致（浮点容差 1e-12）"})
    return {"file": regenerated_path.name, "rows": len(rows_new), "passed": passed,
            "failures": len(failures), **totals, "columns": columns, "excludedColumns": excluded}


# =====================================================================================================
# pre/post dedup statistics and replacement validation
# =====================================================================================================
def consensus_top3_sets(table_frame: pd.DataFrame) -> dict:
    return {dimension: set(group["compound"]) for dimension, group in table_frame.groupby("dimension")}


def by_method_top3_sets(table_frame: pd.DataFrame) -> dict:
    return {(dimension, method): set(group["compound"])
            for (dimension, method), group in table_frame.groupby(["dimension", "method"])}


def overlap_rows(table_frame: pd.DataFrame, delivered_sets: dict, by_method: bool) -> list:
    hits = []
    for _, row in table_frame.iterrows():
        key = (row["dimension"], row["method"]) if by_method else row["dimension"]
        if row["alternative_rank4"] in delivered_sets.get(key, set()):
            hits.append({"dimension": row["dimension"], "method": row.get("method"),
                         "rank": int(row["rank"]), "alternative_rank4": row["alternative_rank4"]})
    return hits


def describe_overlap(hits: list) -> dict:
    ranks = {str(rank): int(sum(1 for hit in hits if hit["rank"] == rank)) for rank in (1, 2, 3)}
    return {"rowsWithDeliveredAlternative": len(hits), "rank1Rows": ranks["1"], "rank2Rows": ranks["2"],
            "rank3Rows": ranks["3"]}


def validate_replacements(original_frame: pd.DataFrame, regenerated_frame: pd.DataFrame, board: dict,
                          modules: dict, delivered_sets: dict, by_method: bool) -> dict:
    changed, invalid = 0, []
    for row_index, (old_row, new_row) in enumerate(zip(original_frame.itertuples(index=False),
                                                       regenerated_frame.itertuples(index=False))):
        old_value, new_value = old_row.alternative_rank4, new_row.alternative_rank4
        if old_value == new_value:
            continue
        changed += 1
        key = (new_row.dimension, new_row.method) if by_method else new_row.dimension
        delivered = delivered_sets.get(key, set())
        members = board["byModule"].get(int(new_row.module_id), [])
        candidates = [name for name in members if name not in delivered]
        if new_value == NO_ALTERNATIVE:
            if candidates:
                invalid.append({"row": row_index, "reason": "none but a same-module candidate exists",
                                "candidates": candidates})
        elif new_value not in members:
            invalid.append({"row": row_index, "reason": "not a member of the row's module",
                            "value": new_value, "moduleId": int(new_row.module_id)})
        elif new_value in delivered:
            invalid.append({"row": row_index, "reason": "still a delivered Top-3 pick", "value": new_value})
    return {"changed": changed, "invalid": invalid}


# =====================================================================================================
# legacy reproduction check (read-only against the superseded EXP-0075 record)
# =====================================================================================================
def legacy_reproduction(table: list, reference_path: Path, claim_reference: bool) -> dict:
    out = {"available": False, "reference": str(reference_path.relative_to(PROJECT)), "passed": None,
           "reason": "not read"}
    if not reference_path.exists():
        out["reason"] = "reference table does not exist"
        return out
    reference = pd.read_csv(reference_path)
    out["referenceSha256"] = sha256_file(reference_path)
    needed = {"dimension", "rank", "compound", "pi", "sign_stability"}
    if not needed.issubset(reference.columns):
        out["reason"] = f"reference table lacks columns {sorted(needed - set(reference.columns))}"
        return out
    mine = {(row["dimension"], int(row["rank"])): row for row in table if row["method"] == "consensus"}
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


# =====================================================================================================
# summary blocks
# =====================================================================================================
DEFINITION = {
    "pointDirection": "sign of the point-estimate total Spearman (200 SPLIT-0001 train rows) for the same "
                      "(compound, dimension) cell",
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
    "undetermined": "a zero or non-computable point estimate is labelled `direction-undetermined`; it is "
                    "never folded into the negative direction and 1 - p_positive is never reported as a "
                    "negative frequency",
    "notClaimed": "this is the stability of the total-correlation DIRECTION; it is not the stability of the "
                  "low-rank coefficients, not a causal direction and not an accuracy measure",
}

QUESTION = "Q2 compound -> sensory-dimension Top-3 direction stability"


def sign_status_counts(table: list) -> dict:
    consensus = [row for row in table if row["method"] == "consensus"]
    directions = {DIRECTION_POSITIVE: 0, DIRECTION_NEGATIVE: 0, DIRECTION_UNDETERMINED: 0}
    statuses = {"stable": 0, "sign-mixed": 0, "low-pi": 0, "low-pi+sign-mixed": 0,
                DIRECTION_UNDETERMINED: 0}
    for row in consensus:
        directions[row["direction_status"]] = directions.get(row["direction_status"], 0) + 1
        statuses[row["evidence_status"]] = statuses.get(row["evidence_status"], 0) + 1
    return {"directionCounts": directions, "evidenceStatusCounts": statuses, "rows": len(consensus),
            "replicateCounts": {"n_positive": int(sum(row["n_positive"] for row in consensus)),
                                "n_negative": int(sum(row["n_negative"] for row in consensus)),
                                "n_zero": int(sum(row["n_zero"] for row in consensus)),
                                "n_invalid": int(sum(row["n_invalid"] for row in consensus))}}


def bootstrap_strata() -> dict:
    frame = pd.read_csv(TRAIN_CSV)
    counts = frame[STYLE_COL].astype(str).value_counts().to_dict()
    return {style: int(counts[style]) for style in sorted(counts)}


def source_hashes() -> dict:
    paths = [
        ("data/splits/SPLIT-0001/train.csv", PROJECT / "data/splits/SPLIT-0001/train.csv"),
        ("data/clean/q1_mapped.csv", PROJECT / "data/clean/q1_mapped.csv"),
        ("data/clean/q2_raw.csv", PROJECT / "data/clean/q2_raw.csv"),
        ("data/clean/q2_chem_meta.json", PROJECT / "data/clean/q2_chem_meta.json"),
        ("data/raw/imported/a55004fb0390299a-6.csv",
         PROJECT / "data/raw/imported/a55004fb0390299a-6.csv"),
        ("data/processed/sensory_name_alignment.csv",
         PROJECT / "data/processed/sensory_name_alignment.csv"),
        ("src/q2_fix.py", PROJECT / "src/q2_fix.py"),
        ("src/q2_v62_regen.py", PROJECT / "src/q2_v62_regen.py"),
    ]
    hashes = {}
    for label, path in paths:
        hashes[label] = sha256_file(path) if path.exists() else "unreadable"
    return hashes


def artifact_hashes(repeat: int) -> dict:
    root = EXP / f"repeat{repeat}"
    out = {}
    for name in ("candidate_scores.csv", "bootstrap_pi.csv", "bootstrap_pi_extended.csv",
                 "sign_counts.csv", "outputs.json"):
        out[f"experiments/EXP-0107/repeat{repeat}/{name}"] = sha256_file(root / name)
    return out


def repeat_denominators(mean150: float, mean600: float, pooled600: float,
                        pooled_legacy: float) -> dict:
    return {
        "strictConsensus150": {
            "rows": 150, "board": "strict", "method": "consensus",
            "meanSignStability": float(mean150),
            "note": "150 行 strict consensus 交付表（50 维 x 3 名）的 sign_stability 均值",
            "source": "repeat{r}/strict_top3.csv",
        },
        "singleRepeat600": {
            "rows": 600, "board": "strict", "methods": list(METHODS),
            "meanSignStability": float(mean600),
            "note": "单次重复 4 方法 x 50 维 x 3 名 = 600 行的 sign_stability 均值",
            "source": "repeat{r}/strict_top3_by_method.csv",
        },
        "pooled3x600": {
            "rows": 1800, "board": "strict", "methods": list(METHODS), "repeats": list(REPEATS),
            "meanSignStability": float(pooled600),
            "meanSignStability_legacy": float(pooled_legacy),
            "note": "三次重复的 600 行按方法表合并（1800 行）的 sign_stability 均值",
            "source": "repeat{0,1,2}/strict_top3_by_method.csv",
        },
    }


def build_repeat_summary(data: dict, built: dict, comparison: dict, dedup: dict,
                         means: dict, pooled: dict, source_hash: dict, strata: dict) -> dict:
    repeat = data["repeat"]
    tables = built["tables"]["strict"]
    consensus = built["consensus"]["strict"]
    sign_counts = sign_status_counts(tables)
    summary = {
        "schemaVersion": "q2-sign-stability/2",
        "repeat": int(repeat),
        "seed": int(data["seed"]),
        "question": QUESTION,
        "definition": DEFINITION,
        "denominators": {
            "bootstrapReps": int(N_BOOTSTRAP),
            "validDenominator": "reps - n_invalid",
            "legacyDenominator": "reps (the superseded denominator)",
            "legacyComparableReps": int(N_BOOTSTRAP),
            "cells": int(N_FEATURES * N_DIMENSIONS),
            "deliveredRowsStrictAllMethods": int(len(tables)),
            "deliveredRowsStrictConsensus": int(len(consensus)),
            **repeat_denominators(means["strictConsensus150"], means["singleRepeat600"],
                                  pooled["sign_stability"], pooled["sign_stability_legacy"]),
        },
        "bootstrap": {"seeds": [int(data["seed"])], "reps": int(N_BOOTSTRAP), "stratifiedBy": STYLE_COL,
                      "strata": strata, "redrawnPerReplicate": True, "zeroTolerance": float(ZERO_TOL)},
        "population": {"board": "strict single_compound", "method": "consensus",
                       "rows": int(len(consensus)), "dimensions": int(N_DIMENSIONS), "ranks": int(K)},
        "directionCounts": sign_counts["directionCounts"],
        "replicateCounts": sign_counts["replicateCounts"],
        "evidenceStatusCounts": sign_counts["evidenceStatusCounts"],
        "means": {"sign_stability": float(means["singleRepeat600"]),
                  "sign_stability_legacy": float(means["legacy600"])},
        "lowPi": {**built["lowpi_summary"], "threshold": PI_STABLE},
        "legacyReproduction": legacy_reproduction(tables, OLD_REFERENCE_DIR / f"repeat{repeat}"
                                                  / "strict_top3.csv", claim_reference=(repeat == 0)),
        "selfTest": self_test(),
        "inputs": source_hash,
        "supersededSchemaVersion": "q2-sign-stability/1",
        "alternativeDedup": dedup,
        "regressionCheck": comparison,
    }
    # the fields of the original summary every repeat carried must all survive
    original = json.loads((data["root"] / "sign_stability_summary.json").read_text(encoding="utf-8"))
    missing = sorted(set(original) - set(summary))
    check(f"summary.repeat{repeat}.fields", not missing,
          {"missing": missing, "detail": "原 sign_stability_summary.json 的全部顶层字段均保留"})
    return summary


# =====================================================================================================
# main
# =====================================================================================================
def main() -> int:
    if not TRAIN_CSV.exists():
        raise RuntimeError(f"missing {TRAIN_CSV}")
    strata = bootstrap_strata()
    self_test_payload = self_test()
    check("definition.selfTest", self_test_payload["passed"],
          {"passed": self_test_payload["passed"], "detail": "方向稳定性定义自检（手工向量）全部通过"})

    # a clean output tree makes the run byte-for-byte reproducible regardless of any earlier leftover file
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    source_hash = source_hashes()

    pre_fix, post_fix, replaced, regression, repeat_results = {}, {}, {}, {}, {}
    repeat_summaries = {}
    means_per_repeat = {}

    # ---------------------------------------------------------------- phase 1: reconstruct + regression
    for repeat in REPEATS:
        data = load_repeat(repeat)
        built = write_repeat_tables(data)
        repeat_results[repeat] = {"data": data, "built": built}

        # compare the five regenerated CSVs with the original EXP-0107 records, cell by cell
        comparison = {}
        for name in ("strict_top3.csv", "strict_top3_by_method.csv", "extended_top3.csv",
                     "extended_top3_by_method.csv", "strict_lowpi_sign_status.csv"):
            comparison[name] = compare_regression(data["root"] / name, OUT / f"repeat{repeat}" / name)
        regression[str(repeat)] = comparison

        # pre-fix overlap (original delivered files) and post-fix overlap (regenerated files)
        root = data["root"]
        original_strict = read_table(root / "strict_top3.csv")
        original_by_method = read_table(root / "strict_top3_by_method.csv")
        original_extended = read_table(root / "extended_top3.csv")
        original_extended_by_method = read_table(root / "extended_top3_by_method.csv")
        regenerated = {name: read_table(OUT / f"repeat{repeat}" / name) for name in
                       ("strict_top3.csv", "strict_top3_by_method.csv", "extended_top3.csv",
                        "extended_top3_by_method.csv")}

        consensus_sets_original = consensus_top3_sets(original_strict)
        method_sets_original = by_method_top3_sets(original_by_method)
        consensus_sets_new = consensus_top3_sets(regenerated["strict_top3.csv"])
        method_sets_new = by_method_top3_sets(regenerated["strict_top3_by_method.csv"])
        extended_sets_original = consensus_top3_sets(original_extended)
        extended_method_sets_original = by_method_top3_sets(original_extended_by_method)
        extended_sets_new = consensus_top3_sets(regenerated["extended_top3.csv"])
        extended_method_sets_new = by_method_top3_sets(regenerated["extended_top3_by_method.csv"])

        pre_hits = {
            "strictConsensus150": overlap_rows(original_strict, consensus_sets_original, False),
            "strictByMethod600": overlap_rows(original_by_method, method_sets_original, True),
            "extendedConsensus150": overlap_rows(original_extended, extended_sets_original, False),
            "extendedByMethod600": overlap_rows(original_extended_by_method,
                                                extended_method_sets_original, True),
        }
        pre_hits["strictByMethod600_vsConsensusTop3"] = overlap_rows(
            original_by_method, consensus_sets_original, False)
        post_hits = {
            "strictConsensus150": overlap_rows(regenerated["strict_top3.csv"], consensus_sets_new, False),
            "strictByMethod600": overlap_rows(regenerated["strict_top3_by_method.csv"], method_sets_new, True),
            "extendedConsensus150": overlap_rows(regenerated["extended_top3.csv"], extended_sets_new, False),
            "extendedByMethod600": overlap_rows(regenerated["extended_top3_by_method.csv"],
                                                extended_method_sets_new, True),
        }
        lowpi_frame = read_table(OUT / f"repeat{repeat}" / "strict_lowpi_sign_status.csv")
        original_lowpi_frame = read_table(root / "strict_lowpi_sign_status.csv")
        lowpi_pre = overlap_rows(original_lowpi_frame, consensus_sets_original, False)
        lowpi_post = overlap_rows(lowpi_frame, consensus_sets_new, False)

        pre_fix[str(repeat)] = {
            "strictConsensus150": describe_overlap(pre_hits["strictConsensus150"]),
            "strictByMethod600": describe_overlap(pre_hits["strictByMethod600"]),
            "strictByMethod600_vsConsensusTop3": {
                "rowsWithDeliveredAlternative": len(pre_hits["strictByMethod600_vsConsensusTop3"])},
            "extendedConsensus150": describe_overlap(pre_hits["extendedConsensus150"]),
            "extendedByMethod600": describe_overlap(pre_hits["extendedByMethod600"]),
            "lowPiRows": {"rowsWithDeliveredAlternative": len(lowpi_pre)},
        }
        post_fix[str(repeat)] = {
            "strictConsensus150": describe_overlap(post_hits["strictConsensus150"]),
            "strictByMethod600": describe_overlap(post_hits["strictByMethod600"]),
            "extendedConsensus150": describe_overlap(post_hits["extendedConsensus150"]),
            "extendedByMethod600": describe_overlap(post_hits["extendedByMethod600"]),
            "lowPiRows": {"rowsWithDeliveredAlternative": len(lowpi_post)},
        }
        for label, statistics in post_fix[str(repeat)].items():
            check(f"dedup.repeat{repeat}.{label}.postFixOverlap", statistics[
                "rowsWithDeliveredAlternative"] == 0,
                  {**statistics, "detail": "修复后同模块替代候选不再重复任何已交付 Top-3 成员"})
        if repeat == 0:
            # the pre-fix state of the original EXP-0107 files, quoted by the task: 34 / 11 / 86 / 95 / 2 / 12
            recorded = {
                "strictConsensus150": (34, 11),
                "strictByMethod600": 86,
                "strictByMethod600_vsConsensusTop3": 95,
                "extendedConsensus150": 2,
                "extendedByMethod600": 12,
            }
            observed = {
                "strictConsensus150": (pre_fix[str(repeat)]["strictConsensus150"]
                                       ["rowsWithDeliveredAlternative"],
                                       pre_fix[str(repeat)]["strictConsensus150"]["rank3Rows"]),
                "strictByMethod600": pre_fix[str(repeat)]["strictByMethod600"]
                ["rowsWithDeliveredAlternative"],
                "strictByMethod600_vsConsensusTop3": pre_fix[str(repeat)]
                ["strictByMethod600_vsConsensusTop3"]["rowsWithDeliveredAlternative"],
                "extendedConsensus150": pre_fix[str(repeat)]["extendedConsensus150"]
                ["rowsWithDeliveredAlternative"],
                "extendedByMethod600": pre_fix[str(repeat)]["extendedByMethod600"]
                ["rowsWithDeliveredAlternative"],
            }
            check("dedup.repeat0.preFixRecorded", observed == recorded,
                  {"observed": observed, "recorded": recorded,
                   "detail": "复现记录在案的修复前重叠：consensus 150 行 34 个（其中 rank 3 为 11 个），"
                             "by-method 对自身方法 Top-3 86 个、对 consensus Top-3 95 个，"
                             "extended 为 2 / 12"})

        # replacement validation: every changed alternative_rank4 is a same-module non-delivered pick or 'none'
        replacement = {
            "strictConsensus150": validate_replacements(
                original_strict, regenerated["strict_top3.csv"], data["boards"]["strict"],
                data["modules"], consensus_sets_new, False),
            "strictByMethod600": validate_replacements(
                original_by_method, regenerated["strict_top3_by_method.csv"], data["boards"]["strict"],
                data["modules"], method_sets_new, True),
            "extendedConsensus150": validate_replacements(
                original_extended, regenerated["extended_top3.csv"], data["boards"]["extended"],
                data["modules"], extended_sets_new, False),
            "extendedByMethod600": validate_replacements(
                original_extended_by_method, regenerated["extended_top3_by_method.csv"],
                data["boards"]["extended"], data["modules"], extended_method_sets_new, True),
            "lowPiRows": validate_replacements(
                read_table(root / "strict_lowpi_sign_status.csv"), lowpi_frame,
                data["boards"]["strict"], data["modules"], consensus_sets_new, False),
        }
        invalid = {label: record["invalid"] for label, record in replacement.items() if record["invalid"]}
        check(f"dedup.repeat{repeat}.replaced.valid", not invalid,
              {"changed": {label: record["changed"] for label, record in replacement.items()},
               "invalid": invalid,
               "detail": "每个被替换的替代候选都是同模块内未交付的候选或 'none'"})
        replaced[str(repeat)] = {label: record["changed"] for label, record in replacement.items()}

        # per-repeat means used by the three denominators
        consensus_rows = built["consensus"]["strict"]
        strict_rows = built["tables"]["strict"]
        means = {
            "strictConsensus150": float(np.mean([row["sign_stability"] for row in consensus_rows])),
            "singleRepeat600": float(np.mean([row["sign_stability"] for row in strict_rows])),
            "legacy600": float(np.mean([row["p_positive_legacy"] for row in strict_rows])),
        }
        means_per_repeat[repeat] = means
        repeat_results[repeat]["dedup"] = {"preFix": pre_fix[str(repeat)], "postFix": post_fix[str(repeat)],
                                           "replaced": replaced[str(repeat)]}

    # ---------------------------------------------------------------- phase 2: pooled denominators
    pooled150 = means_per_repeat[0]["strictConsensus150"]
    pooled600 = float(np.mean([means_per_repeat[repeat]["singleRepeat600"] for repeat in REPEATS]))
    pooled_legacy = float(np.mean([means_per_repeat[repeat]["legacy600"] for repeat in REPEATS]))
    # the pooled mean is the row-level mean over the 1800 by-method rows (identical to the mean of repeat means)
    all_strict_rows = [row for repeat in REPEATS for row in repeat_results[repeat]["built"]["tables"]["strict"]]
    pooled600_rows = float(np.mean([row["sign_stability"] for row in all_strict_rows]))
    pooled_legacy_rows = float(np.mean([row["p_positive_legacy"] for row in all_strict_rows]))
    means = {"strictConsensus150": pooled150, "singleRepeat600": means_per_repeat[0]["singleRepeat600"],
             "pooled3x600": pooled600_rows, "legacy600": means_per_repeat[0]["legacy600"],
             "strictConsensus150_repeat0": pooled150,
             "singleRepeat600_repeat0": means_per_repeat[0]["singleRepeat600"],
             "pooled3x600_legacy": pooled_legacy_rows}
    check("denominators.pooled.rowLevelConsistency", abs(pooled600_rows - pooled600) <= 1e-12,
          {"meanOfRepeatMeans": pooled600, "rowLevelMean": pooled600_rows})
    expected = {"strictConsensus150": 0.9994667, "singleRepeat600": 0.9819800, "pooled3x600": 0.9816878}
    for label, target in expected.items():
        value = means[label]
        check(f"denominators.{label}.mean", abs(value - target) <= 5e-8,
              {"rows": {"strictConsensus150": 150, "singleRepeat600": 600, "pooled3x600": 1800}[label],
               "meanSignStability": value, "roundedTo7": round(float(value), 7),
               "expected": target,
               "detail": f"{label} 的 sign_stability 均值四舍五入到 7 位小数应为 {target}"})

    pooled = {
        "sign_stability": pooled600_rows, "sign_stability_legacy": pooled_legacy_rows,
    }
    denominator_assertions = {
        label: {"expectedRoundedTo7": target, "observedRoundedTo7": round(float(means[label]), 7),
                "observed": float(means[label]),
                "passed": abs(float(means[label]) - target) <= 5e-8}
        for label, target in expected.items()}

    # ---------------------------------------------------------------- phase 3: per-repeat summaries
    for repeat in REPEATS:
        result = repeat_results[repeat]
        summary = build_repeat_summary(
            result["data"], result["built"], regression[str(repeat)], result["dedup"],
            means_per_repeat[repeat], pooled, {**source_hash, **artifact_hashes(repeat)}, strata)
        save_json(OUT / f"repeat{repeat}" / "sign_stability_summary.json", summary)
        repeat_summaries[repeat] = summary

    # ---------------------------------------------------------------- phase 4: final top-level summary
    all_consensus_rows = [row for repeat in REPEATS for row in
                          repeat_results[repeat]["built"]["consensus"]["strict"]]
    pooled_directions = {DIRECTION_POSITIVE: 0, DIRECTION_NEGATIVE: 0, DIRECTION_UNDETERMINED: 0}
    pooled_statuses = {"stable": 0, "sign-mixed": 0, "low-pi": 0, "low-pi+sign-mixed": 0,
                       DIRECTION_UNDETERMINED: 0}
    for row in all_consensus_rows:
        pooled_directions[row["direction_status"]] += 1
        pooled_statuses[row["evidence_status"]] += 1
    pooled_replicates = {"n_positive": int(sum(row["n_positive"] for row in all_consensus_rows)),
                         "n_negative": int(sum(row["n_negative"] for row in all_consensus_rows)),
                         "n_zero": int(sum(row["n_zero"] for row in all_consensus_rows)),
                         "n_invalid": int(sum(row["n_invalid"] for row in all_consensus_rows))}
    pooled_lowpi_count = int(sum(repeat_results[repeat]["built"]["lowpi_summary"]["count"]
                                 for repeat in REPEATS))
    lowpi_status_pooled, lowpi_direction_pooled = {}, {}
    for repeat in REPEATS:
        for status, count in repeat_results[repeat]["built"]["lowpi_summary"]["statusCounts"].items():
            lowpi_status_pooled[status] = lowpi_status_pooled.get(status, 0) + count
        for direction, count in repeat_results[repeat]["built"]["lowpi_summary"]["directionCounts"].items():
            lowpi_direction_pooled[direction] = lowpi_direction_pooled.get(direction, 0) + count

    final = {
        "schemaVersion": "q2-sign-stability-v62/1",
        "extends": "q2-sign-stability/2 (per-repeat files)",
        "generatedBy": {"script": "src/q2_v62_regen.py", "command": "python src/q2_v62_regen.py",
                        "pythonVersion": sys.version.split()[0],
                        "q2FixSha256": sha256_file(PROJECT / "src/q2_fix.py")},
        "question": QUESTION,
        "definition": DEFINITION,
        "denominators": {
            "bootstrapReps": int(N_BOOTSTRAP),
            "validDenominator": "reps - n_invalid",
            "legacyDenominator": "reps (the superseded denominator)",
            "legacyComparableReps": int(N_BOOTSTRAP),
            "cells": int(N_FEATURES * N_DIMENSIONS),
            "repeatCount": int(len(REPEATS)),
            "deliveredRowsStrictAllMethods": int(len(repeat_results[0]["built"]["tables"]["strict"])),
            "deliveredRowsStrictConsensus": int(len(repeat_results[0]["built"]["consensus"]["strict"])),
            **repeat_denominators(pooled150, means_per_repeat[0]["singleRepeat600"],
                                  pooled600_rows, pooled_legacy_rows),
        },
        "bootstrap": {"reps": int(N_BOOTSTRAP), "seeds": list(EXPECTED_SEEDS), "stratifiedBy": STYLE_COL,
                      "strata": strata, "redrawnPerRepeat": True, "zeroTolerance": float(ZERO_TOL)},
        "population": {"board": "strict single_compound", "method": "consensus", "rows": 150,
                       "dimensions": int(N_DIMENSIONS), "ranks": int(K), "repeats": list(REPEATS)},
        "directionCounts": pooled_directions,
        "replicateCounts": pooled_replicates,
        "evidenceStatusCounts": pooled_statuses,
        "means": {
            "sign_stability": float(pooled600_rows),
            "sign_stability_denominator": "pooled3x600（1800 行 = 3 重复 × 600）；不是 150 条共识的分母",
            "sign_stability_legacy": float(pooled_legacy_rows),
            "sign_stability_legacy_denominator": "pooled3x600（1800 行，旧口径）",
            "perRepeat": {str(repeat): {
                "strictConsensus150_sign_stability": float(means_per_repeat[repeat]["strictConsensus150"]),
                "singleRepeat600_sign_stability": float(means_per_repeat[repeat]["singleRepeat600"]),
                "singleRepeat600_sign_stability_legacy": float(means_per_repeat[repeat]["legacy600"]),
            } for repeat in REPEATS},
        },
        "lowPi": {
            "count": pooled_lowpi_count,
            "file": "repeat{0,1,2}/strict_lowpi_sign_status.csv",
            "statusCounts": {status: lowpi_status_pooled[status] for status in sorted(lowpi_status_pooled)},
            "directionCounts": {direction: lowpi_direction_pooled[direction]
                                for direction in sorted(lowpi_direction_pooled)},
            "threshold": PI_STABLE,
            "perRepeatCounts": {str(repeat): repeat_results[repeat]["built"]["lowpi_summary"]["count"]
                                for repeat in REPEATS},
        },
        "legacyReproduction": {str(repeat): repeat_summaries[repeat]["legacyReproduction"]
                               for repeat in REPEATS},
        "selfTest": self_test_payload,
        "inputs": source_hash,
        "denominatorAssertions": denominator_assertions,
        "alternativeDedup": {
            "rule": "同模块替代候选 = 该 (方法, 维度) 内按该方法点估计得分降序（同分按特征名）排序后，"
                    "第一个不在该 (方法, 维度) 已交付 Top-3 中的同模块成员；没有这样的成员时写 'none'。"
                    "module_rank4_to_10 为剔除已交付 Top-3 后的同模块替代池。",
            "preFix": pre_fix,
            "postFix": post_fix,
            "replaced": replaced,
            "assertionsPassed": all(
                statistics["rowsWithDeliveredAlternative"] == 0
                for repeat in REPEATS for statistics in post_fix[str(repeat)].values()),
        },
        "regressionCheck": regression,
        "repeats": {str(repeat): repeat_summaries[repeat] for repeat in REPEATS},
    }
    save_json(OUT / "sign_stability_summary.json", final)

    # ---------------------------------------------------------------- phase 5: manifest + report
    written_files = sorted(path for path in OUT.rglob("*") if path.is_file()
                           and path.name not in ("v62_manifest.json", "REPORT.md"))
    output_hashes = {
        str(path.relative_to(OUT)): {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in written_files
    }
    report = build_report(data=repeat_results, pre_fix=pre_fix, post_fix=post_fix, replaced=replaced,
                          regression=regression, means=means, final=final, output_hashes=output_hashes)
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    output_hashes["REPORT.md"] = {"bytes": (OUT / "REPORT.md").stat().st_size,
                                  "sha256": sha256_file(OUT / "REPORT.md")}
    # ---------------------------------------------------------------- phase 6: mirror to the submission tree
    # the tree is mirrored BEFORE the manifest is written, so the manifest can also assert the mirror
    if SUBMISSION.exists():
        shutil.rmtree(SUBMISSION)
    SUBMISSION.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(OUT, SUBMISSION)
    expected = {str(path.relative_to(OUT)): sha256_file(path) for path in OUT.rglob("*") if path.is_file()}
    actual = {str(path.relative_to(SUBMISSION)): sha256_file(path)
              for path in SUBMISSION.rglob("*") if path.is_file()}
    check("sync.submissionTree", expected == actual,
          {"files": len(actual), "target": str(SUBMISSION),
           "detail": "交付材料目录与 v62_clean 逐字节一致（manifest 在镜像校验后写入并同步）"})

    manifest = {
        "schemaVersion": "q2-v62-regen/1",
        "purpose": "从 EXP-0107 已保存产物确定性地重建 Q2 v6.2 交付表，并修复同模块替代候选重复已交付 Top-3 的缺陷；"
                   "不重跑 bootstrap、不重训练任何模型。",
        "script": {"path": "src/q2_v62_regen.py", "sha256": sha256_file(PROJECT / "src/q2_v62_regen.py"),
                   "command": "python src/q2_v62_regen.py"},
        "sourceFix": {"path": "src/q2_fix.py", "sha256": sha256_file(PROJECT / "src/q2_fix.py"),
                      "change": "module_alternatives()/module_alternative_report() 先剔除 delivered Top-3 再取替代候选"},
        "inputs": {**source_hash, **{key: value for repeat in REPEATS
                                     for key, value in artifact_hashes(repeat).items()}},
        "assertions": ASSERTIONS,
        "denominators": final["denominators"],
        "preFixOverlap": pre_fix,
        "postFixOverlap": post_fix,
        "replaced": replaced,
        "regressionCheck": {
            repeat: {name: {"passed": record["passed"], "rows": record["rows"],
                            "failures": record["failures"],
                            "cellsCompared": record["cellsCompared"],
                            "exactStringMatches": record["exactStringMatches"],
                            "floatWithinTolerance": record["floatWithinTolerance"],
                            "maxAbsDiff": record["maxAbsDiff"],
                            "excludedColumnChanges": {column: statistics["changed"]
                                                      for column, statistics in record["excludedColumns"].items()}}
                     for name, record in comparison.items()}
            for repeat, comparison in regression.items()},
        "outputs": output_hashes,
        "sync": {"target": "FINAL_SUBMISSION_v6.2/支撑材料/outputs/q2",
                 "mirrors": "outputs/q2/v62_clean/"},
        "determinism": "同一输入重复运行应产生逐字节相同的全部输出（脚本不含时间戳/随机数）。",
    }
    save_json(OUT / "v62_manifest.json", manifest)
    shutil.copyfile(OUT / "v62_manifest.json", SUBMISSION / "v62_manifest.json")
    if sha256_file(OUT / "v62_manifest.json") != sha256_file(SUBMISSION / "v62_manifest.json"):
        raise RuntimeError("sync: the manifest copy in the submission tree differs")

    print(json.dumps({
        "status": "ok",
        "repeats": list(REPEATS),
        "preFixOverlap": pre_fix,
        "postFixOverlap": post_fix,
        "replaced": replaced,
        "denominators": {key: final["denominators"][key]["meanSignStability"]
                         for key in ("strictConsensus150", "singleRepeat600", "pooled3x600")},
        "regressionAllPassed": all(record["passed"] for repeat in REPEATS
                                   for record in regression[str(repeat)].values()),
        "assertions": len(ASSERTIONS),
        "outputs": len(output_hashes),
        "outDir": str(OUT),
        "submission": str(SUBMISSION),
    }, ensure_ascii=False, indent=2))
    return 0


# =====================================================================================================
# REPORT.md (Chinese prose; numbers come from the run)
# =====================================================================================================
def build_report(data: dict, pre_fix: dict, post_fix: dict, replaced: dict, regression: dict,
                 means: dict, final: dict, output_hashes: dict) -> str:
    lines = ["# Q2 v6.2 交付表重建与同模块替代候选去重报告", ""]
    lines.append("本报告由 `src/q2_v62_regen.py` 从 `experiments/EXP-0107/repeat{0,1,2}/` 已保存产物确定性生成："
                 "不重跑 500 次 bootstrap、不重训练任何模型，仅重新组装交付表并修复替代候选规则。")
    lines.append("")
    lines.append("## 1. 缺陷与修复")
    lines.append("")
    lines.append("- 缺陷：`module_alternatives()` 直接取同模块点估计排序第 4 名，未剔除刚交付的 Top-3，"
                 "导致替代候选重复已交付化合物；`module_alternative_report()` 的 `moduleRank4To10` 池同样未剔除。")
    lines.append("- 修复：先剔除该 (方法, 维度) 已交付 Top-3，再取第一个同模块候选；无候选时写 `none`。"
                 "`sameModuleAlternativeExists` 改为“是否存在未交付的同模块候选”。")
    lines.append("- 修复源码：`src/q2_fix.py::module_alternatives()` / `module_alternative_report()`。")
    lines.append("")
    lines.append("## 2. 修复前后重叠计数（alternative_rank4 是否落在对应 Top-3 中）")
    lines.append("")
    lines.append("| 重复 | consensus 150 行（修复前/后） | 其中 rank 3（修复前） | by-method 600 行对自身方法 Top-3（前/后） | "
                 "by-method 对 consensus Top-3（修复前） | extended 150 行（前/后） | extended by-method（前/后） |")
    lines.append("|---|---|---|---|---|---|---|")
    for repeat in REPEATS:
        pre, post = pre_fix[str(repeat)], post_fix[str(repeat)]
        lines.append(
            f"| {repeat} | {pre['strictConsensus150']['rowsWithDeliveredAlternative']} / "
            f"{post['strictConsensus150']['rowsWithDeliveredAlternative']} | "
            f"{pre['strictConsensus150']['rank3Rows']} | "
            f"{pre['strictByMethod600']['rowsWithDeliveredAlternative']} / "
            f"{post['strictByMethod600']['rowsWithDeliveredAlternative']} | "
            f"{pre['strictByMethod600_vsConsensusTop3']['rowsWithDeliveredAlternative']} | "
            f"{pre['extendedConsensus150']['rowsWithDeliveredAlternative']} / "
            f"{post['extendedConsensus150']['rowsWithDeliveredAlternative']} | "
            f"{pre['extendedByMethod600']['rowsWithDeliveredAlternative']} / "
            f"{post['extendedByMethod600']['rowsWithDeliveredAlternative']} |")
    lines.append("")
    lines.append("替换（alternative_rank4 取值发生变化的单元格）计数：" +
                 "；".join(f"重复 {repeat}：" + "，".join(f"{label} {count} 个"
                                                          for label, count in replaced[str(repeat)].items())
                          for repeat in REPEATS) +
                 "。每个替换项均校验为“同模块内未交付候选”或 `none`，无非法替换。")
    lines.append("")
    lines.append("## 3. 三个分母（sign_stability 均值）")
    lines.append("")
    denominators = final["denominators"]
    lines.append("| 分母 | 行数 | sign_stability 均值 |")
    lines.append("|---|---|---|")
    for key, label in (("strictConsensus150", "repeat 0 交付 consensus 150 行"),
                       ("singleRepeat600", "单次重复 4 方法 600 行"),
                       ("pooled3x600", "三次重复合并 1800 行")):
        block = denominators[key]
        lines.append(f"| {label} | {block['rows']} | {block['meanSignStability']!r} |")
    lines.append("")
    lines.append(f"断言通过：0.9994667 / 0.9819800 / 0.9816878（7 位小数）。"
                 f"repeat 0 的 150 行均值 {means['strictConsensus150']!r}，600 行均值 "
                 f"{means['singleRepeat600']!r}，合并 1800 行均值 {means['pooled3x600']!r}。")
    lines.append("")
    lines.append("## 4. 回归校验（除三个允许变化的列外逐格比对原 EXP-0107 文件）")
    lines.append("")
    lines.append("| 重复 | 文件 | 行数 | 结果 | 失败单元格 |")
    lines.append("|---|---|---|---|---|")
    regression_passed = True
    for repeat in REPEATS:
        for name, record in regression[str(repeat)].items():
            regression_passed = regression_passed and record["passed"]
            lines.append(f"| {repeat} | {name} | {record['rows']} | "
                         f"{'通过' if record['passed'] else '失败'} | {record['failures']} |")
    lines.append("")
    lines.append(f"总结果：{'全部通过' if regression_passed else '存在失败'}（浮点容差 1e-12；"
                 "允许变化列：alternative_rank4 / module_rank4_to_10 / same_module_alternative_exists）。")
    lines.append("")
    lines.append("## 5. 文件清单")
    lines.append("")
    lines.append("| 文件 | 字节数 | sha256 |")
    lines.append("|---|---|---|")
    for name, record in output_hashes.items():
        lines.append(f"| {name} | {record['bytes']} | `{record['sha256']}` |")
    lines.append("")
    lines.append("## 6. 复现")
    lines.append("")
    lines.append("```")
    lines.append("python src/q2_v62_regen.py")
    lines.append("```")
    lines.append("")
    lines.append("脚本不读取 `state/ledger.json`，不重跑 bootstrap，不写入 `experiments/`；"
                 "输出同时镜像到 `FINAL_SUBMISSION_v6.2/支撑材料/outputs/q2/`。")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
