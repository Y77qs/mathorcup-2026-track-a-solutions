"""r00_data_audit.py — cell-by-cell calibration provenance, conflict lists and state dictionary.

WHAT IT ANSWERS
  1. For every beer x calibrated field, how do the two sources compare?  The main input
     data/raw/imported/419849227a02e0c7-1.csv stores either log10(concentration) or the
     concentration; the calibration workbook f2316766792111d9-8.xlsx always stores the
     concentration.  A like-for-like comparison therefore needs the scale of each field:
         log10 fields : expected_storage = log10(calibrated)
         linear fields: expected_storage = calibrated
     The raw comparison `stored vs calibrated` is computed too, only to show why it cannot be
     used (it would flag every log-scaled cell).
  2. Two conflict definitions (two "口径", both frozen here):
         strict      : NOT numpy.isclose(stored, expected_storage, atol=1e-7, rtol=1e-7)
         substantive : rel_diff = |stored - expected_storage| / |expected_storage| > 0.01
  3. The state dictionary: calibrated zero codes (755), floor-coded columns (142), floor-coded
     cells (6807), missing cells, and their per-column breakdown.  Every number claimed in the
     previous audit is recomputed and compared; a difference is reported, never re-baselined.
  4. Row identity: `beer` must be unique and exactly 1..250; `beer_id` is recorded but never used
     as a join key (the 4.csv/7.csv copies are truncated).

No fitting, no model, no write outside outputs/audit/v6/.

Run:  python src/r00_data_audit.py
Writes: outputs/audit/v6/cell_provenance.csv
        outputs/audit/v6/conflicts_strict.csv
        outputs/audit/v6/conflicts_substantive.csv
        outputs/audit/v6/calibration_conflict_summary.json
        outputs/audit/v6/state_counts.json
Exit: 0 all registered counts reproduce; 3 a registered state count drifted (outputs are still
      written and the difference is named on stderr).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True  # never leave new build artefacts under src/
sys.path.insert(0, str(Path(__file__).resolve().parent))
import v6_common  # noqa: E402
from r00_constants import identify_scale  # noqa: E402  (single source of the scale rule)

PROJECT = v6_common.PROJECT
RAW = PROJECT / "data/raw/imported"
AUDIT = PROJECT / "outputs/audit/v6"
PATH_RAW1 = RAW / "419849227a02e0c7-1.csv"
PATH_CAL = RAW / "f2316766792111d9-8.xlsx"
PATH_V6_CONSTANTS = PROJECT / "data/processed/v6_constants.json"
OUT = AUDIT

ATOL = 1e-7
RTOL = 1e-7
SUBSTANTIVE_REL = 0.01
FLOOR_TOL = 1e-6
FLOOR_CANDIDATE = -1.81781854
STYLE_COL = "tasting_category_fine"
META_COLS = ("beer", "beer_id", STYLE_COL)

# Values registered by the previous audit / src/target_columns.py. Recomputed below; a
# difference is a finding to report, not a licence to change the definition.
REGISTERED = {
    "calibratedZeroCells": 755,
    "floorColumns": 142,
    "floorCells": 6807,
    "missingCells": 73,
    "missingColumns": 9,
    "rowsWithMissing": 63,
}
PREVIOUS_CONFLICT = {"cells": 80, "beers": 24, "fields": 32, "atol": 1e-7, "rtol": 1e-7,
                     "source": "MathorCup_A_独立审查与重跑方案/01_独立复核与修复优先级.md F09"}


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n", na_rep="").encode("utf-8")


def _json_text(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def load_scales(one: pd.DataFrame, cal: pd.DataFrame, features: list) -> dict:
    """Load the registered tier split and verify it by recomputing the scale rule."""
    calibrated = [c for c in cal.columns if c in set(features)]
    if PATH_V6_CONSTANTS.exists():
        registered = json.loads(PATH_V6_CONSTANTS.read_text(encoding="utf-8"))
        tiers = registered["tiers"]
        log10 = list(tiers["log10Calibrated"])
        linear = list(tiers["linearCalibrated"])
        unverified = list(tiers["uncalibrated"])
        source = "data/processed/v6_constants.json"
    else:
        chosen = {c: identify_scale(one[c].to_numpy(), cal[c].to_numpy())["chosen"]
                  for c in calibrated}
        log10 = [c for c in calibrated if chosen[c] == "log10"]
        linear = [c for c in calibrated if chosen[c] == "linear"]
        unverified = [c for c in features if c not in set(calibrated)]
        source = "recomputed (v6_constants.json absent)"
    recomputed_log = []
    recomputed_linear = []
    for column in calibrated:
        decision = identify_scale(one[column].to_numpy(), cal[column].to_numpy())["chosen"]
        (recomputed_log if decision == "log10" else recomputed_linear).append(column)
    if sorted(recomputed_log) != sorted(log10) or sorted(recomputed_linear) != sorted(linear):
        raise RuntimeError("registered tier list disagrees with the recomputed scale rule: "
                           f"log10 registered {len(log10)} vs recomputed {len(recomputed_log)}, "
                           f"linear registered {len(linear)} vs recomputed {len(recomputed_linear)}")
    if sorted(log10 + linear + unverified) != sorted(features):
        raise RuntimeError("tier lists do not partition the feature list")
    return {"log10": log10, "linear": linear, "unverified": unverified, "source": source,
            "recomputedAgreement": {"log10": len(recomputed_log), "linear": len(recomputed_linear)}}


def build_cells(one: pd.DataFrame, cal: pd.DataFrame, scales: dict) -> pd.DataFrame:
    frames = []
    for tier, columns in (("log10", scales["log10"]), ("linear", scales["linear"])):
        for column in columns:
            stored = one[column].to_numpy(dtype=float)
            calibrated = cal[column].to_numpy(dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                expected = np.log10(calibrated) if tier == "log10" else calibrated.copy()
            frames.append(pd.DataFrame({
                "beer": one["beer"].to_numpy(dtype=int),
                "field": column,
                "tier": tier,
                "stored_value": stored,
                "calibrated_value": calibrated,
                "expected_storage": expected,
            }))
    table = pd.concat(frames, ignore_index=True)

    stored_finite = np.isfinite(table["stored_value"].to_numpy(dtype=float))
    cal_finite = np.isfinite(table["calibrated_value"].to_numpy(dtype=float))
    cal = table["calibrated_value"].to_numpy(dtype=float)
    expected = table["expected_storage"].to_numpy(dtype=float)
    comparable = stored_finite & cal_finite & (cal > 0) & np.isfinite(expected)

    state = np.full(len(table), "comparable_positive", dtype=object)
    state[~cal_finite] = "calibrated_missing"
    state[cal_finite & (cal < 0)] = "calibrated_negative"
    state[cal_finite & (cal == 0)] = "calibrated_zero"
    state[cal_finite & (cal > 0) & ~stored_finite] = "stored_missing"
    table["source_state"] = state

    diff = table["stored_value"].to_numpy(dtype=float) - expected
    abs_diff = np.abs(diff)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel_diff = abs_diff / np.abs(expected)
    strict_equal = np.isclose(table["stored_value"].to_numpy(dtype=float), expected,
                              atol=ATOL, rtol=RTOL)
    substantive = rel_diff > SUBSTANTIVE_REL

    table["abs_diff"] = np.where(comparable, abs_diff, np.nan)
    table["rel_diff"] = np.where(comparable, rel_diff, np.nan)
    table["strict_equal"] = pd.Series(np.where(comparable, strict_equal, None), dtype=object)
    table["substantive_rel_gt_1pct"] = pd.Series(np.where(comparable, substantive, None),
                                                 dtype=object)
    columns = ["beer", "field", "stored_value", "calibrated_value", "abs_diff", "rel_diff",
               "strict_equal", "substantive_rel_gt_1pct", "source_state", "tier",
               "expected_storage"]
    return table[columns]


def summarise(table: pd.DataFrame, mask: np.ndarray) -> dict:
    part = table[mask]
    return {"cells": int(mask.sum()), "beers": int(part["beer"].nunique()),
            "fields": int(part["field"].nunique()),
            "tierBreakdown": {tier: int((part["tier"] == tier).sum())
                              for tier in ("log10", "linear")},
            "fieldsAffected": sorted(part["field"].unique().tolist()),
            "beersAffected": sorted(int(b) for b in part["beer"].unique())}


def state_dictionary(one: pd.DataFrame, cal: pd.DataFrame, features: list, scales: dict) -> dict:
    log10 = scales["log10"]
    linear = scales["linear"]
    unverified = scales["unverified"]

    # ---- calibrated zero codes: the registered definition is the 37 log10 columns ------------
    zeros_log10 = {c: int((np.isfinite(cal[c].to_numpy(dtype=float))
                           & (cal[c].to_numpy(dtype=float) == 0)).sum()) for c in log10}
    zeros_linear = {c: int((np.isfinite(cal[c].to_numpy(dtype=float))
                            & (cal[c].to_numpy(dtype=float) == 0)).sum()) for c in linear}
    zero_code_check = {}
    for column in log10:
        raw = cal[column].to_numpy(dtype=float)
        stored = one[column].to_numpy(dtype=float)
        finite = np.isfinite(raw)
        positive = raw[finite & (raw > 0)]
        code = float(np.log10(positive.min() / 2.0)) if positive.size else None
        zero_mask = finite & (raw == 0)
        zero_code_check[column] = {
            "zeroCells": int(zero_mask.sum()),
            "floorCodeLog10": code,
            "medianAbsDiffAtZero": (None if not zero_mask.sum() or code is None else
                                    float(np.nanmedian(np.abs(stored[zero_mask] - code)))),
        }

    # ---- floor coding among the unverified columns --------------------------------------------
    minimum = {c: float(np.nanmin(one[c].to_numpy(dtype=float))) for c in features}
    floor_columns = sorted(c for c in unverified
                           if abs(minimum[c] - FLOOR_CANDIDATE) <= FLOOR_TOL)
    floor_value = float(np.median([minimum[c] for c in floor_columns])) if floor_columns else None
    floor_cells_by_column = {}
    for column in floor_columns:
        values = one[column].to_numpy(dtype=float)
        floor_cells_by_column[column] = int(
            np.sum(np.isfinite(values) & (np.abs(values - floor_value) <= FLOOR_TOL)))
    floor_cells = sum(floor_cells_by_column.values())

    # ---- calibrated negatives (reported, never silently clipped) ------------------------------
    negative_cells = []
    for column in list(log10) + list(linear):
        raw = cal[column].to_numpy(dtype=float)
        hits = np.nonzero(np.isfinite(raw) & (raw < 0))[0]
        for index in hits:
            negative_cells.append({"beer": int(one["beer"].to_numpy()[index]), "field": column,
                                   "calibrated": float(raw[index])})

    # ---- missingness --------------------------------------------------------------------------
    missing = {c: int(one[c].isna().sum()) for c in features if one[c].isna().any()}
    rows_with_missing = int(one[features].isna().any(axis=1).sum())

    per_column = {}
    for column in features:
        values = one[column].to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        per_column[column] = {
            "tier": ("log10" if column in set(log10) else
                     "linear" if column in set(linear) else "unverified"),
            "missing": int(np.isnan(values).sum()),
            "storedMin": float(finite.min()) if finite.size else None,
            "storedMax": float(finite.max()) if finite.size else None,
            "calibratedZeros": (zeros_log10.get(column) if column in set(log10) else
                                zeros_linear.get(column) if column in set(linear) else None),
            "floorCoded": column in set(floor_columns),
            "floorCells": int(floor_cells_by_column.get(column, 0)),
        }

    observed = {
        "calibratedZeroCells": int(sum(zeros_log10.values())),
        "floorColumns": len(floor_columns),
        "floorCells": int(floor_cells),
        "missingCells": int(sum(missing.values())),
        "missingColumns": len(missing),
        "rowsWithMissing": rows_with_missing,
    }
    assertions = []
    for name, expected in REGISTERED.items():
        got = observed[name]
        assertions.append({"name": name, "registered": expected, "recomputed": got,
                           "matches": got == expected})
    drifted = [a for a in assertions if not a["matches"]]
    return {
        "scope": ("state dictionary recomputed from the two raw sources; the registered definition "
                  "of every count is stated with the number"),
        "inputs": {"data/raw/imported/419849227a02e0c7-1.csv":
                   {"sha256": v6_common.sha256_file(PATH_RAW1)},
                   "data/raw/imported/f2316766792111d9-8.xlsx":
                   {"sha256": v6_common.sha256_file(PATH_CAL)}},
        "definitions": {
            "calibratedZeroCells": ("cells in the 37 log10-calibrated columns where the "
                                    "calibration workbook records concentration exactly 0; the "
                                    "stored value of such a cell is the log10 floor code "
                                    "log10(min(positive)/2), not 0"),
            "linearCalibratedZeros": ("the 33 linear-calibrated columns also contain calibrated "
                                      "zeros; they are reported separately and are NOT counted as "
                                      "floor codes, because 0 is a plausible measured "
                                      "concentration there"),
            "floorColumns": (f"uncalibrated columns whose minimum stored value equals "
                             f"{FLOOR_CANDIDATE} within {FLOOR_TOL}"),
            "floorCells": ("cells equal to the estimated floor value "
                           "(median of the per-column minima) within "
                           f"{FLOOR_TOL}, summed over the floor columns"),
            "floorTolerance": FLOOR_TOL,
        },
        "estimatedFloorValue": floor_value,
        "floorCandidateValue": FLOOR_CANDIDATE,
        "recomputed": observed,
        "registered": REGISTERED,
        "assertions": assertions,
        "drifted": [a["name"] for a in drifted],
        "calibratedZerosByColumn": {
            "log10": zeros_log10,
            "linear": zeros_linear,
            "log10Total": int(sum(zeros_log10.values())),
            "linearTotal": int(sum(zeros_linear.values())),
        },
        "floorColumns": floor_columns,
        "floorColumnsCount": len(floor_columns),
        "floorCellsByColumn": floor_cells_by_column,
        "unverifiedMinima": {c: minimum[c] for c in unverified},
        "missing": missing,
        "zeroCodeVerification": zero_code_check,
        "calibratedNegativeCells": {"count": len(negative_cells), "cells": negative_cells},
        "perColumn": per_column,
        "notResolved": [
            "a repeated floor code is a convention, not proof of a measured zero or of a "
            "detection limit; no LOD is declared in the attachments",
            "calibrated negative concentrations are reported in calibratedNegativeCells; their "
            "origin is not established here and no value was clipped",
        ],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    one = pd.read_csv(PATH_RAW1)
    cal = pd.read_excel(PATH_CAL, sheet_name="Calibrated chemical dataset")

    # ---- key checks ---------------------------------------------------------------------------
    beer_unique = bool(one["beer"].is_unique)
    beer_range = sorted(int(b) for b in one["beer"].tolist())
    beer_is_1_to_250 = beer_range == list(range(1, 251))
    cal_beer = cal["beer"].to_numpy(dtype=int)
    cal_aligned = bool(np.array_equal(cal_beer, one["beer"].to_numpy(dtype=int)))
    beer_id_unique = bool(one["beer_id"].astype(str).is_unique)
    if not beer_unique or not beer_is_1_to_250:
        raise RuntimeError("beer key check failed: 1.csv 'beer' is not a unique 1..250 permutation")
    if not cal_aligned:
        raise RuntimeError("calibration table rows are not beer-aligned with 1.csv")

    features = [c for c in one.columns if c not in META_COLS]
    scales = load_scales(one, cal, features)
    table = build_cells(one, cal, scales)

    comparable = (table["source_state"] == "comparable_positive").to_numpy()
    strict_flag = np.asarray([bool(v) if v is not None else False
                              for v in table["strict_equal"]], dtype=bool)
    substantive_flag = np.asarray([bool(v) if v is not None else False
                                   for v in table["substantive_rel_gt_1pct"]], dtype=bool)
    strict_conflict = comparable & ~strict_flag
    substantive_conflict = comparable & substantive_flag

    strict_rows = table.loc[strict_conflict]
    substantive_rows = table.loc[substantive_conflict]
    required = ["beer", "field", "stored_value", "calibrated_value", "abs_diff", "rel_diff",
                "strict_equal", "substantive_rel_gt_1pct", "source_state", "tier",
                "expected_storage"]
    _atomic_write(OUT / "cell_provenance.csv", _csv_bytes(table[required]))
    _atomic_write(OUT / "conflicts_strict.csv", _csv_bytes(strict_rows[required]))
    _atomic_write(OUT / "conflicts_substantive.csv", _csv_bytes(substantive_rows[required]))

    strict = summarise(table, strict_conflict)
    substantive = summarise(table, substantive_conflict)

    # The literal "stored vs calibrated" comparison, recorded only to explain why it is invalid.
    stored = table["stored_value"].to_numpy(dtype=float)
    calibrated = table["calibrated_value"].to_numpy(dtype=float)
    naive_mask = np.isfinite(stored) & np.isfinite(calibrated) & (calibrated > 0)
    naive_strict = naive_mask & ~np.isclose(stored, calibrated, atol=ATOL, rtol=RTOL)
    with np.errstate(divide="ignore", invalid="ignore"):
        naive_rel = np.abs(stored - calibrated) / np.abs(calibrated)
    naive_substantive = naive_mask & (naive_rel > SUBSTANTIVE_REL)

    max_log10_error = 0.0
    for column in scales["log10"]:
        raw = cal[column].to_numpy(dtype=float)
        positive = np.isfinite(raw) & (raw > 0)
        if positive.any():
            max_log10_error = max(max_log10_error, float(np.max(
                np.abs(one[column].to_numpy(dtype=float)[positive] - np.log10(raw[positive])))))

    previous_matches = (strict["cells"] == PREVIOUS_CONFLICT["cells"]
                        and strict["beers"] == PREVIOUS_CONFLICT["beers"]
                        and strict["fields"] == PREVIOUS_CONFLICT["fields"])
    summary = {
        "scope": ("cell-by-cell comparison of 1.csv against the 8.xlsx calibration sheet on the "
                  "storage scale; no fitting, no substitution of either source"),
        "inputs": {
            "data/raw/imported/419849227a02e0c7-1.csv": {
                "sha256": v6_common.sha256_file(PATH_RAW1), "role": "main input (stored values)"},
            "data/raw/imported/f2316766792111d9-8.xlsx": {
                "sha256": v6_common.sha256_file(PATH_CAL),
                "role": "calibration table (concentrations)"},
        },
        "tierSource": scales["source"],
        "tierCounts": {"log10": len(scales["log10"]), "linear": len(scales["linear"]),
                       "unverified": len(scales["unverified"])},
        "tolerance": {"atol": ATOL, "rtol": RTOL, "substantiveRelThreshold": SUBSTANTIVE_REL},
        "comparisonBasis": {
            "formula": {"log10": "expected_storage = log10(calibrated)",
                        "linear": "expected_storage = calibrated"},
            "rationale": ("1.csv stores log10(c) for the 37 log10-calibrated fields and c for the "
                          "33 linear-calibrated fields; comparing a stored log10 value with a raw "
                          "concentration is a unit mismatch, not a data conflict"),
            "maxAbsStorageErrorLog10Columns": max_log10_error,
        },
        "comparableCells": int(comparable.sum()),
        "totalCellsCompared": int(len(table)),
        "cellStateCounts": table["source_state"].value_counts().to_dict(),
        "strict": {"definition": f"not isclose(stored, expected_storage, atol={ATOL}, rtol={RTOL})",
                   **strict},
        "substantive": {"definition": "rel_diff = |stored-expected_storage|/|expected_storage| > 0.01",
                        **substantive},
        "previousAudit": {
            "claimed": PREVIOUS_CONFLICT,
            "matchesStrict": previous_matches,
            "beerCountMatches": strict["beers"] == PREVIOUS_CONFLICT["beers"],
            "fieldCountMatches": strict["fields"] == PREVIOUS_CONFLICT["fields"],
            "differenceReason": (None if previous_matches else
                                 "recomputed strict conflict set differs from the previous audit; "
                                 "the definition here is stated verbatim so the difference can be "
                                 "attributed to the definition rather than to the data"),
            "comparedAt_24_beers": prev_beers_note(strict),
        },
        "directStoredVsCalibrated": {
            "definition": (f"not isclose(stored, calibrated, atol={ATOL}, rtol={RTOL}) with NO "
                           "scale conversion"),
            "strictCells": int(naive_strict.sum()),
            "strictBeers": int(table.loc[naive_strict, "beer"].nunique()),
            "strictFields": int(table.loc[naive_strict, "field"].nunique()),
            "substantiveCells": int(naive_substantive.sum()),
            "whyNotUsed": ("expected by construction for the 37 log10 columns: stored=log10(c) and "
                           "calibrated=c, so almost every positive cell differs; it measures the "
                           "scale transform, not a data conflict"),
        },
        "keyChecks": {
            "joinKey": "beer",
            "beerUnique": beer_unique,
            "beerIs1To250": beer_is_1_to_250,
            "calibrationTableBeerAligned": cal_aligned,
            "beerIdUnique": beer_id_unique,
            "beerIdUsedForJoin": False,
            "beerIdNote": ("beer_id is recorded but never used to join: the 4.csv/7.csv copies are "
                           "truncated, so an EAN-like key would silently drop or mis-merge rows"),
        },
        "notResolved": [
            "the cause of the substantive conflicts is not established; neither source is "
            "declared authoritative, so 1.csv stays the main input and no value is replaced",
            "a conflict is a disagreement between two files, not proof that either is wrong",
        ],
    }
    _atomic_write(OUT / "calibration_conflict_summary.json", _json_text(summary))

    states = state_dictionary(one, cal, features, scales)
    _atomic_write(OUT / "state_counts.json", _json_text(states))

    drifted = states["drifted"]
    print(json.dumps({
        "ok": not drifted,
        "script": "src/r00_data_audit.py",
        "outputs": ["outputs/audit/v6/cell_provenance.csv",
                    "outputs/audit/v6/conflicts_strict.csv",
                    "outputs/audit/v6/conflicts_substantive.csv",
                    "outputs/audit/v6/calibration_conflict_summary.json",
                    "outputs/audit/v6/state_counts.json"],
        "rowsInCellProvenance": int(len(table)),
        "comparableCells": int(comparable.sum()),
        "strictConflicts": {"cells": strict["cells"], "beers": strict["beers"],
                            "fields": strict["fields"]},
        "substantiveConflicts": {"cells": substantive["cells"], "beers": substantive["beers"],
                                 "fields": substantive["fields"]},
        "previousAuditMatches": previous_matches,
        "stateCounts": states["recomputed"],
        "stateCountsMatchRegistered": not drifted,
        "drifted": drifted,
        "keyChecks": {"beerUnique": beer_unique, "beerIs1To250": beer_is_1_to_250,
                      "beerIdUsedForJoin": False},
    }, ensure_ascii=False))

    if drifted:
        print("STATE COUNT DRIFT: " + ", ".join(
            f"{a['name']} registered={a['registered']} recomputed={a['recomputed']}"
            for a in states["assertions"] if not a["matches"]), file=sys.stderr)
        print("the registered definition was NOT changed to match; see state_counts.json",
              file=sys.stderr)
        return 3
    return 0


def prev_beers_note(strict: dict) -> dict:
    """The previous audit reported 80 conflicts over 24 beers and 32 fields; expose that ratio."""
    return {"previousBeers": PREVIOUS_CONFLICT["beers"], "recomputedBeers": strict["beers"],
            "sameBeerCount": strict["beers"] == PREVIOUS_CONFLICT["beers"],
            "previousCells": PREVIOUS_CONFLICT["cells"], "recomputedCells": strict["cells"]}


if __name__ == "__main__":
    sys.exit(main())
