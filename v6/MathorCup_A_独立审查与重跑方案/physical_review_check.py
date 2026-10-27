"""Independent, read-only checks for the physical-domain review; no fitting or optimisation.

Run with a Python environment containing pandas, numpy, and openpyxl.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import json

import numpy as np
import openpyxl
import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', required=True, type=Path)
parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
HERE = args.out.resolve()
HERE.mkdir(parents=True, exist_ok=True)
ROOT = args.repo.resolve()
V5 = ROOT / "v5"
constants_path = V5 / "src" / "target_columns.py"
constants = {}
for node in ast.parse(constants_path.read_text()).body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        try:
            constants[node.targets[0].id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            pass
raw_path = next((V5 / "data/raw/imported").glob("*-1.csv"))
book_path = next((V5 / "data/raw/imported").glob("*-8.xlsx"))
generated_path = ROOT / "v5.1/data/generated_spectra_310.csv"
raw = pd.read_csv(raw_path)
book = openpyxl.load_workbook(book_path, read_only=True, data_only=True)
cal_rows = list(book["Calibrated chemical dataset"].values)
cal = pd.DataFrame(cal_rows[1:], columns=cal_rows[0])
cal["beer"] = pd.to_numeric(cal["beer"])
cal = cal.set_index("beer").reindex(raw["beer"]).reset_index()
assert np.array_equal(cal["beer"].to_numpy(), raw["beer"].to_numpy())
threshold_rows = list(book["Sensory thresholds"].values)
thresholds = pd.DataFrame(threshold_rows[1:], columns=threshold_rows[0])
names = constants["DERIVED_SUMS"] + ["DMS", "X4VG", "X.E..2.nonenal", "X2.3.butanedione"]
dictionary = thresholds[thresholds["field_name_R"].isin(names)].replace({np.nan: None}).to_dict("records")
generated = pd.read_csv(generated_path)
generated_linear = generated[["chem__" + n for n in constants["LINEAR_CALIBRATED"]]]
negative = generated_linear.lt(0)
source_rows = []
for idx in raw.index[raw["tasting_category_fine"] == "Pils/Lager"]:
    item = {"beer": int(raw.loc[idx, "beer"])}
    for name in ["DMS", "X4VG", "X.E..2.nonenal", "X2.3.butanedione"]:
        def value(v):
            v = pd.to_numeric(v, errors="coerce")
            return None if pd.isna(v) else float(v)
        item[name] = {"stored": value(raw.loc[idx, name]), "calibrated": value(cal.loc[idx, name])}
    source_rows.append(item)
defect_original = {}
for name in ["DMS", "X4VG", "X.E..2.nonenal", "X2.3.butanedione"]:
    vals = pd.to_numeric(cal[name], errors="coerce")
    defect_original[name] = {
        "calibrated_zero_count": int(vals.eq(0).sum()),
        "calibrated_missing_count": int(vals.isna().sum()),
        "stored_missing_count": int(raw[name].isna().sum()),
    }
transform_checks = []
calibration_conflicts = []
for tier in ["LOG10_CALIBRATED", "LINEAR_CALIBRATED"]:
    for name in constants[tier]:
        physical = pd.to_numeric(cal[name], errors="coerce")
        stored = pd.to_numeric(raw[name], errors="coerce")
        valid = physical.notna() & stored.notna() & physical.gt(0)
        expected = np.log10(physical[valid]) if tier == "LOG10_CALIBRATED" else physical[valid]
        errors = np.abs(stored[valid] - expected)
        # Both absolute and relative tolerances protect against source rounding.
        conflicts = ~np.isclose(stored[valid], expected, atol=1e-7, rtol=1e-7)
        for idx in expected.index[conflicts]:
            calibration_conflicts.append({"beer": int(raw.loc[idx, "beer"]), "feature": name,
                                          "tier": tier, "stored_value": float(stored.loc[idx]),
                                          "calibrated_value": float(physical.loc[idx]),
                                          "expected_storage": float(expected.loc[idx]),
                                          "difference": float(stored.loc[idx]-expected.loc[idx])})
        transform_checks.append({"name": name, "tier": tier, "positive_observed_pairs": int(valid.sum()),
                                 "conflicts_over_rounding_tolerance": int(conflicts.sum()),
                                 "max_absolute_storage_error": float(np.max(errors))})
pd.DataFrame(calibration_conflicts).to_csv(HERE / "calibrated_positive_value_conflicts.csv", index=False)
facts = {
    "scope": "Direct source/dictionary/output checks only; no fitting, no optimisation, no fabricated LOD",
    "tier_counts": {n: len(constants[n]) for n in ["LOG10_CALIBRATED", "LINEAR_CALIBRATED", "UNCALIBRATED"]},
    "raw_linear_negative_cells": int(raw[constants["LINEAR_CALIBRATED"]].lt(0).to_numpy().sum()),
    "generated_linear_negative_cells": int(negative.to_numpy().sum()),
    "generated_linear_negative_rows": int(negative.any(axis=1).sum()),
    "generated_linear_negative_columns": int(negative.any(axis=0).sum()),
    "negative_groups": generated.loc[negative.any(axis=1), "group"].value_counts().to_dict(),
    "style_counts": raw["tasting_category_fine"].value_counts().to_dict(),
    "dictionary_rows": dictionary,
    "defect_original": defect_original,
    "positive_observation_transform_checks": transform_checks,
    "positive_observation_conflicts": {"count": len(calibration_conflicts),
                                       "beer_count": len({r["beer"] for r in calibration_conflicts}),
                                       "feature_count": len({r["feature"] for r in calibration_conflicts}),
                                       "comparison_atol": 1e-7, "comparison_rtol": 1e-7},
    "source_11_pils_lager": source_rows,
    "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in [constants_path, raw_path, book_path, generated_path]},
}
(HERE / "physical_review_evidence.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: facts[k] for k in ["tier_counts", "raw_linear_negative_cells", "generated_linear_negative_cells", "generated_linear_negative_rows", "generated_linear_negative_columns", "negative_groups"]}, ensure_ascii=False))
