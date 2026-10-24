"""prepare_base.py — Phase 1 data dictionary, scale audit and the base Q1/Q2 table.

Inputs (raw attachment copies imported by modeling_data import):
  data/raw/imported/419849227a02e0c7-1.csv   1.csv  chemistry (250 x 231 + 3 keys)
  data/raw/imported/415709ac10f2f730-2.csv   2.csv  231 x 231 Spearman co-expression matrix
  data/raw/imported/43a7b38682ed81ce-4.csv   4.csv  50 standardized sensory labels
  data/raw/imported/f2316766792111d9-8.xlsx  8.xlsx calibrated concentrations + sensory thresholds

Outputs (all registered, hashed by run-script):
  data/clean/q2_raw.csv            row, beer, beer_id, style, chem__<231>, <50 sensory labels>
  src/target_columns.py            pure constants: column lists, evidence tiers, floor codes, defect map
  data/clean/q2_chem_meta.json     per-variable type / scale tier / 2.csv label mapping
  data/clean/q3_thresholds.json    defect thresholds (mean/median) and storage-scale rules
  data/processed/fields_q2raw.json complete field list (each column exactly once)
  analysis/sensory/targetcolumns.csv  scale + evidence table
  outputs/audit/audit.json         every count claimed in the paper, recomputed here
  outputs/audit/scale_identification.csv
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / "data" / "raw" / "imported"
CLEAN = PROJECT / "data" / "clean"
PROCESSED = PROJECT / "data" / "processed"
AUDIT = PROJECT / "outputs" / "audit"
SENSORY = PROJECT / "analysis" / "sensory"
SRC = PROJECT / "src"

RAW_1 = RAW / "419849227a02e0c7-1.csv"
RAW_2 = RAW / "415709ac10f2f730-2.csv"
RAW_4 = RAW / "43a7b38682ed81ce-4.csv"
RAW_8 = RAW / "f2316766792111d9-8.xlsx"

META = ["row", "beer", "beer_id", "tasting_category_fine"]
CHEM_PREFIX = "chem__"
STYLE_COLUMN = "tasting_category_fine"
DERIVED_SUMS = ["kcalperc", "acids_sum", "esters_sum", "aroma_hops_sum", "sulfur_sum"]
PHYSICAL = ["pH", "color.EBC.", "bitterness", "ethanol..v.v.", "CO2.PSI.", "GFS", "unfermentables"]
DEFECT_FIELDS = {
    # R-style field name in 8.xlsx  ->  display name used in the paper
    "DMS": "DMS (dimethyl sulfide)",
    "X2.3.butanedione": "diacetyl (2,3-butanedione)",
    "X4VG": "4-vinylguaiacol (4VG)",
    "X.E..2.nonenal": "trans-2-nonenal",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identify_scale(stored: np.ndarray, raw: np.ndarray):
    """Decide whether a calibrated column is stored as log10(raw) or raw, using numeric identity."""
    stored = np.asarray(stored, dtype=float)
    raw = np.asarray(raw, dtype=float)
    both = np.isfinite(stored) & np.isfinite(raw)
    positive = both & (raw > 0)
    if positive.sum() >= 10:
        log_error = float(np.nanmedian(np.abs(stored[positive] - np.log10(raw[positive]))))
    else:
        log_error = None
    raw_error = float(np.nanmedian(np.abs(stored[both] - raw[both]))) if both.sum() else None
    zero_rows = both & (raw == 0)
    floor_error = None
    floor_value = None
    positives = raw[both & (raw > 0)]
    if positives.size:
        floor_value = float(np.log10(positives.min() / 2.0))
        if zero_rows.sum():
            floor_error = float(np.nanmedian(np.abs(stored[zero_rows] - floor_value)))
    chosen = None
    if log_error is not None and log_error < 1e-6:
        chosen = "log10"
    elif raw_error is not None and raw_error < 1e-6:
        chosen = "linear"
    elif log_error is not None and raw_error is not None:
        chosen = "log10" if log_error < raw_error else "linear"
    return {"chosen": chosen, "log10MedianAbsDiff": log_error, "linearMedianAbsDiff": raw_error,
            "nZeroCalibrated": int(zero_rows.sum()), "floorValueLog10": floor_value,
            "floorMedianAbsDiff": floor_error}


def normalise_name(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def main() -> int:
    for directory in (CLEAN, PROCESSED, AUDIT, SENSORY, SRC):
        directory.mkdir(parents=True, exist_ok=True)

    one = pd.read_csv(RAW_1)
    four = pd.read_csv(RAW_4)
    two = pd.read_csv(RAW_2, index_col=0)
    cal = pd.read_excel(RAW_8, sheet_name="Calibrated chemical dataset")
    thresholds = pd.read_excel(RAW_8, sheet_name="Sensory thresholds")

    feature_cols = [c for c in one.columns if c not in ("beer", "beer_id", STYLE_COLUMN)]
    target_cols = [c for c in four.columns if c not in ("beer", "beer_id", STYLE_COLUMN)]
    assert len(feature_cols) == 231, len(feature_cols)
    assert len(target_cols) == 50, len(target_cols)
    assert len(one) == 250 and len(four) == 250

    # ---- key alignment -------------------------------------------------------------------------------------
    assert one["beer"].is_unique and set(one["beer"]) == set(range(1, 251))
    assert (one["beer"].values == four["beer"].values).all()
    assert one["beer_id"].astype(str).is_unique
    beer_id_four_unique = int(four["beer_id"].astype(str).nunique())
    assert list(one[STYLE_COLUMN].values) == list(four[STYLE_COLUMN].values)
    style_counts = one[STYLE_COLUMN].value_counts().to_dict()

    # ---- scale identification against the calibrated table -------------------------------------------------
    calibrated = [c for c in cal.columns if c not in ("beer", "beer_id", STYLE_COLUMN)]
    assert len(calibrated) == 70, len(calibrated)
    assert all(c in feature_cols for c in calibrated)
    scale_rows = []
    for column in calibrated:
        info = identify_scale(one[column].to_numpy(), cal[column].to_numpy())
        info["column"] = column
        scale_rows.append(info)
    log10_cal = sorted([r["column"] for r in scale_rows if r["chosen"] == "log10"])
    linear_cal = sorted([r["column"] for r in scale_rows if r["chosen"] == "linear"])
    unverified = sorted([c for c in feature_cols if c not in calibrated])
    assert len(log10_cal) == 37, (len(log10_cal), log10_cal)
    assert len(linear_cal) == 33, (len(linear_cal), linear_cal)
    assert len(unverified) == 161, len(unverified)

    # calibrated zeros inside the 37 log10 columns, and their floor coding
    n_calibrated_zero_cells = 0
    floor_check = []
    for column in log10_cal:
        raw = cal[column].to_numpy(dtype=float)
        stored = one[column].to_numpy(dtype=float)
        zeros = np.isfinite(raw) & (raw == 0)
        n_calibrated_zero_cells += int(zeros.sum())
        info = next(r for r in scale_rows if r["column"] == column)
        floor_check.append({"column": column, "nZero": int(zeros.sum()),
                            "floorValueLog10": info["floorValueLog10"],
                            "medianAbsDiffAtZero": info["floorMedianAbsDiff"]})
    assert n_calibrated_zero_cells == 755, n_calibrated_zero_cells

    # common floor code among unverified columns
    minimum_by_column = {}
    for column in unverified:
        values = one[column].to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        minimum_by_column[column] = float(finite.min()) if finite.size else None
    candidate_floor = -1.81781854
    floor_columns = sorted([c for c, v in minimum_by_column.items()
                            if v is not None and abs(v - candidate_floor) <= 1e-6])
    floor_value = float(np.median([minimum_by_column[c] for c in floor_columns])) if floor_columns else None
    n_floor_cells = 0
    for column in floor_columns:
        values = one[column].to_numpy(dtype=float)
        n_floor_cells += int(np.sum(np.isfinite(values) & (np.abs(values - floor_value) <= 1e-6)))
    assert len(floor_columns) == 142, len(floor_columns)
    assert n_floor_cells == 6807, n_floor_cells

    # ---- missingness ----------------------------------------------------------------------------------------
    missing_by_column = {c: int(one[c].isna().sum()) for c in feature_cols if one[c].isna().any()}
    rows_with_missing = int(one[feature_cols].isna().any(axis=1).sum())
    assert sum(missing_by_column.values()) == 73, missing_by_column
    assert len(missing_by_column) == 9 and rows_with_missing == 63
    missing_order = sorted(missing_by_column, key=lambda c: -missing_by_column[c])

    # ---- 2.csv label mapping --------------------------------------------------------------------------------
    # 2.csv labels are display names ("Carbon disulfide", "2,3-butanedione") while 1.csv keeps R-munged field
    # names ("CS2", "X2.3.butanedione"). The bridge is a normalised match after stripping unit suffixes and the
    # leading R "X" of names that start with a digit, plus the four alias columns of the 8.xlsx threshold sheet.
    GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "κ": "kappa",
             "Î±": "alpha", "Î²": "beta", "Î³": "gamma", "Î´": "delta"}

    def normalise_label(text) -> str:
        value = str(text).lower()
        for glyph, word in GREEK.items():
            value = value.replace(glyph, word)
        value = re.sub(r"\.(mg|l|g|ug|psi|ebc|v|ml)\.?", "", value)
        value = re.sub(r"[^a-z0-9]", "", value)
        if value.startswith("x") and len(value) > 1 and value[1].isdigit():
            value = value[1:]
        return value

    alias_map = {}
    for _, row in thresholds.iterrows():
        field = row.get("field_name_R")
        if not isinstance(field, str) or not field.strip():
            continue
        key = normalise_label(field)
        for column in ("field_name_R", "field_name_python", "chemical_name", "chemical_name_short"):
            value = row.get(column)
            if isinstance(value, str) and value.strip():
                alias_map.setdefault(key, set()).add(normalise_label(value))
    label_index = {}
    for position, label in enumerate(two.columns):
        label_index.setdefault(normalise_label(label), position)
        label_index.setdefault(re.sub(r"[^a-z0-9]", "", str(label).lower()), position)

    def candidates_for(feature):
        keys = [normalise_label(feature), re.sub(r"[^a-z0-9]", "", str(feature).lower())]
        keys += sorted(alias_map.get(normalise_label(feature), set()))
        out = []
        for key in keys:
            index = label_index.get(key)
            if index is not None and index not in out:
                out.append(index)
        return out

    candidate_lists = {feature: candidates_for(feature) for feature in feature_cols}
    corr_map = {}
    used = set()
    # closest-constraint features first, then resolve one-to-one; a duplicate label is never counted twice.
    for feature in sorted(feature_cols, key=lambda f: len(candidate_lists[f])):
        for index in candidate_lists[feature]:
            if index not in used:
                corr_map[feature] = int(index)
                used.add(int(index))
                break
    matched_direct = sum(1 for f in feature_cols if normalise_label(f) in label_index and normalise_label(two.columns[corr_map.get(f, -1)]) == normalise_label(f)) if corr_map else 0
    matched_via_xlsx = len(corr_map) - matched_direct
    # last resort: a close-name match on the raw labels, for the few display names the aliases do not bridge
    if len(corr_map) < len(feature_cols):
        import difflib
        free = [i for i in range(len(two.columns)) if i not in used]
        for feature in feature_cols:
            if feature in corr_map:
                continue
            pool = {str(two.columns[i]): i for i in free}
            close = difflib.get_close_matches(feature, list(pool), n=1, cutoff=0.6)
            if close:
                index = pool[close[0]]
                corr_map[feature] = int(index)
                used.add(index)
                free.remove(index)
    if len(corr_map) != len(feature_cols):
        raise RuntimeError("2.csv alignment incomplete: %d/%d; missing=%s; freeLabels=%s" % (len(corr_map), len(feature_cols), [f for f in feature_cols if f not in corr_map], [two.columns[i] for i in range(len(two.columns)) if i not in used]))
    assert len(set(corr_map.values())) == len(feature_cols)
    assert abs(two.shape[0] - two.shape[1]) == 0

    # ---- variable types -------------------------------------------------------------------------------------
    compound_candidates = [c for c in feature_cols if c not in DERIVED_SUMS and c not in PHYSICAL]

    def variable_kind(column: str) -> str:
        if column in DERIVED_SUMS:
            return "derived_sum"
        if column in PHYSICAL:
            return "physical_parameter"
        return "single_compound"

    def evidence_tier(column: str) -> str:
        if column in log10_cal:
            return "calibrated_log10"
        if column in linear_cal:
            return "calibrated_linear"
        return "unverified_storage_scale"

    # ---- base table ---------------------------------------------------------------------------------------
    meta_block = pd.DataFrame({"row": np.arange(len(one), dtype=int), "beer": one["beer"].astype(int),
                               "beer_id": one["beer_id"].astype(str), STYLE_COLUMN: one[STYLE_COLUMN].astype(str)})
    chem_block = one[feature_cols].astype(float).copy()
    chem_block.columns = [CHEM_PREFIX + c for c in feature_cols]
    target_block = four[target_cols].astype(float).copy()
    base = pd.concat([meta_block, chem_block, target_block], axis=1)
    base_path = CLEAN / "q2_raw.csv"
    base.to_csv(base_path, index=False, lineterminator="\n")

    # ---- q2_chem_meta.json --------------------------------------------------------------------------------
    metadata = {
        "features": [{"name": c, "kind": variable_kind(c), "tier": evidence_tier(c),
                      "corrIndex": corr_map.get(c), "corrLabel": two.columns[corr_map[c]] if c in corr_map else None,
                      "floorCoded": c in floor_columns}
                     for c in feature_cols],
        "compounds": compound_candidates,
        "derivedSums": DERIVED_SUMS,
        "physicalParameters": PHYSICAL,
        "log10Calibrated": log10_cal,
        "linearCalibrated": linear_cal,
        "unverified": unverified,
        "corrMatches": {"total": len(feature_cols), "matched": len(corr_map),
                        "direct": matched_direct, "viaXlsxShortName": matched_via_xlsx},
    }
    (CLEAN / "q2_chem_meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ---- target_columns.py (pure constants) ---------------------------------------------------------------
    def block(name, values):
        lines = [name + " = ["]
        for value in values:
            lines.append("    %r," % value)
        lines.append("]")
        return "\n".join(lines)

    constants = ['"""target_columns.py — pure constants generated by src/prepare_base.py from the real headers.',
                 "",
                 "Do not edit by hand: every experiment declares this file as a dependency so the frozen snapshot",
                 'names exactly the columns the code was trained on."""',
                 "",
                 "N_SAMPLES = 250", "N_FEATURES = 231", "N_TARGETS = 50", "N_STYLES = %d" % len(style_counts),
                 "STYLE_COLUMN = %r" % STYLE_COLUMN, "CHEM_PREFIX = %r" % CHEM_PREFIX, "GRADE_PREFIX = 'g6__'",
                 "FLOOR_VALUE = %r" % float(floor_value),
                 "CALIBRATED_ZERO_CELLS = %d" % n_calibrated_zero_cells,
                 "FLOOR_CELLS = %d" % n_floor_cells,
                 "",
                 block("FEATURE_COLS", feature_cols), "",
                 block("FEATURE_COLUMNS", [CHEM_PREFIX + c for c in feature_cols]), "",
                 block("TARGET_COLS", target_cols), "",
                 block("LOG10_CALIBRATED", log10_cal), "",
                 block("LINEAR_CALIBRATED", linear_cal), "",
                 block("UNCALIBRATED", unverified), "",
                 block("FLOOR_COLUMNS", floor_columns), "",
                 block("DERIVED_SUMS", DERIVED_SUMS), "",
                 block("PHYSICAL_PARAMETERS", PHYSICAL), "",
                 block("COMPOUND_CANDIDATES", compound_candidates), "",
                 block("DEFECT_COLUMNS", sorted(DEFECT_FIELDS)), "",
                 "DEFECT_DISPLAY = %r" % DEFECT_FIELDS, "",
                 "STYLE_COUNTS = %r" % style_counts, "",
                 "MISSING_COLUMNS = %r" % missing_order, ""]
    (SRC / "target_columns.py").write_text("\n".join(constants), encoding="utf-8")

    # ---- q3_thresholds.json -------------------------------------------------------------------------------
    threshold_lookup = {}
    for _, row in thresholds.iterrows():
        field = row.get("field_name_R")
        if isinstance(field, str) and field.strip():
            mean = row.get("threshold_mean")
            median = row.get("threshold_median")
            threshold_lookup[field] = {
                "thresholdMean": None if pd.isna(mean) else float(mean),
                "thresholdMedian": None if pd.isna(median) else float(median),
                "unit": None if pd.isna(row.get("unit")) else str(row.get("unit")),
                "offFlavors": None if pd.isna(row.get("off_flavors")) else str(row.get("off_flavors")),
                "chemicalName": None if pd.isna(row.get("chemical_name")) else str(row.get("chemical_name")),
            }
    defect_rows = {}
    for field in DEFECT_FIELDS:
        info = threshold_lookup.get(field, {})
        tier = evidence_tier(field) if field in feature_cols else None
        defect_rows[field] = {"column": field, "tier": tier, "display": DEFECT_FIELDS[field],
                              "inFeatureTable": field in feature_cols, **info}
    defect_rows["stale_hops"] = {"column": "stale_hops", "tier": "sensory_label", "display": "stale hops (sensory dimension)",
                                 "inFeatureTable": False, "thresholdMean": None, "thresholdMedian": None,
                                 "unit": "standardized sensory label", "offFlavors": "stale hop character",
                                 "chemicalName": None}
    nonenal_values = one["X.E..2.nonenal"].to_numpy(dtype=float)
    t2n_negative = bool(np.nanmin(nonenal_values) < 0)
    q3_thresholds = {
        "defects": defect_rows,
        "storageRules": {c: ({"scale": "log10", "inverse": "10**x"} if c in log10_cal else
                             {"scale": "linear", "inverse": "x"} if c in linear_cal else
                             {"scale": "unverified", "negativeObserved": bool(np.nanmin(one[c].to_numpy(dtype=float)) < 0)})
                         for c in ["DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal"]},
        "floorValue": float(floor_value),
        "floorColumns": floor_columns,
        "trans2NonenalNegative": t2n_negative,
        "note": ("Thresholds come from 8.xlsx 'Sensory thresholds' joined on field_name_R (exact 1.csv column name). "
                 "Concentrations are compared after inverting the storage scale; a floor code is treated as a value at "
                 "or below the floor, i.e. not above any threshold."),
    }
    (CLEAN / "q3_thresholds.json").write_text(json.dumps(q3_thresholds, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ---- field list for register-clean ---------------------------------------------------------------------
    def field_records(frame: pd.DataFrame, dataset: str):
        records = []
        for column in frame.columns:
            if column == "row":
                records.append({"name": column, "type": "integer", "unit": None,
                                "description": "0-based position in 1.csv/4.csv (row-aligned); the holdout assignment uses this id."})
            elif column == "beer":
                records.append({"name": column, "type": "integer", "unit": None,
                                "description": "1.csv/4.csv beer label (permutation of 1..250); join key."})
            elif column == "beer_id":
                records.append({"name": column, "type": "string", "unit": None,
                                "description": "1.csv EAN-like code; 4.csv/7.csv copies are truncated, so it is not a join key."})
            elif column == STYLE_COLUMN:
                records.append({"name": column, "type": "string", "unit": None,
                                "description": "tasting_category_fine, 22 styles; conditioning label for Q3 and stratifier for Q2."})
            elif column.startswith(CHEM_PREFIX):
                raw = column[len(CHEM_PREFIX):]
                tier = evidence_tier(raw)
                unit = "stored value (log10 of concentration)" if tier == "calibrated_log10" else (
                    "stored concentration" if tier == "calibrated_linear" else "stored value, scale not directly calibrated")
                records.append({"name": column, "type": "number", "unit": unit,
                                "description": "1.csv column %r, value unchanged from the raw attachment (missing cells stay blank; Q1 imputes inside the training fold)." % raw})
            elif column.startswith("g6__"):
                records.append({"name": column, "type": "number", "unit": "grade 0-6",
                                "description": "Derived continuous 0-6 reference grade of the observed label %r under the SPLIT-0001 TRAIN midpoint CDF; used for reporting/sensitivity only, never as a feature." % column[4:]})
            elif column in target_cols:
                records.append({"name": column, "type": "number", "unit": "standardized sensory label",
                                "description": "4.csv standardized sensory target %r (continuous, mean 0; NOT an original 0-6 score)." % column})
            else:
                raise RuntimeError("unclassified column in %s: %s" % (dataset, column))
        return records

    fields_base = field_records(base, "q2_raw")
    assert len(fields_base) == len(base.columns)
    assert len({r["name"] for r in fields_base}) == len(base.columns)
    (PROCESSED / "fields_q2raw.json").write_text(json.dumps(fields_base, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ---- human-readable scale table ------------------------------------------------------------------------
    scale_table = pd.DataFrame({"column": feature_cols,
                                "kind": [variable_kind(c) for c in feature_cols],
                                "tier": [evidence_tier(c) for c in feature_cols],
                                "floorCoded": [c in floor_columns for c in feature_cols],
                                "corrMatched": [c in corr_map for c in feature_cols],
                                "missing": [int(one[c].isna().sum()) for c in feature_cols]})
    scale_table.to_csv(SENSORY / "targetcolumns.csv", index=False, lineterminator="\n")

    # ---- audit --------------------------------------------------------------------------------------------
    audit = {
        "shape": {"nSamples": int(len(one)), "nFeatures": len(feature_cols), "nTargets": len(target_cols),
                  "nStyles": len(style_counts), "styleCounts": style_counts},
        "alignment": {"beerUnique": True, "oneFourBeerEqual": True, "styleEqual": True,
                      "beerIdFourDistinct": beer_id_four_unique,
                      "note": "beer is a permutation of 1..250 and row-aligns 1.csv/4.csv; beer_id in 4.csv/7.csv is truncated."},
        "scale": {"calibratedColumns": len(calibrated), "log10Calibrated": len(log10_cal),
                  "linearCalibrated": len(linear_cal), "unverified": len(unverified),
                  "calibratedZeroCells": n_calibrated_zero_cells,
                  "floorValue": floor_value, "floorColumns": len(floor_columns), "floorCells": n_floor_cells},
        "missing": {"cells": int(base[[CHEM_PREFIX + c for c in feature_cols]].isna().sum().sum()), "columns": missing_by_column,
                    "rowsWithMissing": rows_with_missing},
        "corrMatrix": {"shape": [int(two.shape[0]), int(two.shape[1])], "matchedFeatures": len(corr_map),
                       "direct": matched_direct, "viaXlsxShortName": matched_via_xlsx},
        "variableTypes": {"singleCompound": len(compound_candidates), "derivedSum": len(DERIVED_SUMS),
                          "physical": len(PHYSICAL)},
        "thresholds": {"defects": {k: {"mean": v["thresholdMean"], "median": v["thresholdMedian"], "unit": v["unit"]}
                                   for k, v in defect_rows.items()}},
        "inputs": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in (RAW_1, RAW_2, RAW_4, RAW_8)},
        "outputs": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
                    for p in (base_path, SRC / "target_columns.py", CLEAN / "q2_chem_meta.json",
                              CLEAN / "q3_thresholds.json", PROCESSED / "fields_q2raw.json",
                              SENSORY / "targetcolumns.csv")},
    }
    (AUDIT / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pd.DataFrame(scale_rows).to_csv(AUDIT / "scale_identification.csv", index=False, lineterminator="\n")

    print(json.dumps({"ok": True, "baseRows": int(len(base)), "baseColumns": int(base.shape[1]),
                      "log10": len(log10_cal), "linear": len(linear_cal), "unverified": len(unverified),
                      "calibratedZeroCells": n_calibrated_zero_cells,
                      "floorColumns": len(floor_columns), "floorCells": n_floor_cells,
                      "missingCells": int(base[[CHEM_PREFIX + c for c in feature_cols]].isna().sum().sum()),
                      "corrMatched": len(corr_map), "compoundCandidates": len(compound_candidates)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
