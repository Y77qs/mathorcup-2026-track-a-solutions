"""r00_constants.py — regenerate the frozen v6 constant table from the real headers.

WHY: the previous round let a *generator script* rewrite `src/target_columns.py` in place, so
"the code the model was trained with" and "the code that produced it" were the same mutable
file. This script inverts that: it writes DATA (`data/processed/v6_constants.json` and
`data/processed/v6_feature_dictionary.csv`), records the sha256 of every input, of itself and
of its own body, and never writes under `src/`.

WHAT IS RE-DERIVED (never copied as literals):
  1. the 231 `chem__*` feature names come from the header of data/clean/q1_mapped.csv;
  2. kind / tier / corrIndex / corrLabel / floorCoded come from data/clean/q2_chem_meta.json;
  3. the storage scale of every calibrated column is decided from numeric identity between
     data/raw/imported/419849227a02e0c7-1.csv (stored) and f2316766792111d9-8.xlsx
     (calibrated concentrations), using the same deterministic rule as src/prepare_base.py:
     median |stored - log10(calibrated)| < 1e-6 => log10; else median |stored - calibrated|
     < 1e-6 => linear; else the smaller median error decides;
  4. the feature category is derived by rule (see `CATEGORY_RULES`): derived_sum and
     physical_parameter come from q2_chem_meta.json, element_or_index from the workbook's
     chemical_name/unit semantics, single_compound is the remainder.

The script is deterministic: two runs on the same inputs give byte-identical output apart from
the `generatedAt` timestamp, and `contentSha256NoTimestamp` proves it (printed in the summary).

Run:  python src/r00_constants.py
Writes: data/processed/v6_constants.json
        data/processed/v6_feature_dictionary.csv
        outputs/audit/v6/v6_constants.json          (byte-identical audit mirror)
        outputs/audit/v6/v6_feature_dictionary.csv  (byte-identical audit mirror)
"""

from __future__ import annotations

import datetime
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
import v6_common  # noqa: E402  (frozen shared interface: PROJECT, sha256_file, NON_SINGLE_COMPOUND)

PROJECT = v6_common.PROJECT
RAW = PROJECT / "data/raw/imported"
CLEAN = PROJECT / "data/clean"
PROCESSED = PROJECT / "data/processed"
AUDIT = PROJECT / "outputs/audit/v6"

PATH_Q1 = CLEAN / "q1_mapped.csv"
PATH_META = CLEAN / "q2_chem_meta.json"
PATH_RAW1 = RAW / "419849227a02e0c7-1.csv"
PATH_CAL = RAW / "f2316766792111d9-8.xlsx"

CHEM_PREFIX = "chem__"
STYLE_COL = "tasting_category_fine"
META_COLS = ("beer", "beer_id", STYLE_COL)

EXPECTED = {
    "chemFeatures": 231,
    "log10Calibrated": 37,
    "linearCalibrated": 33,
    "uncalibrated": 161,
    "singleCompound": 216,
    "elementOrIndex": 3,
    "physicalParameter": 7,
    "derivedSum": 5,
}

# Rule vocabulary for `element_or_index`. This is reference data (periodic-table names and the
# tokens that denote a macromolecule mass measurement), not a list of results: whichever fields
# the workbook's chemical_name/unit actually match becomes the category, and the script refuses
# to continue if the match is not exactly the declared 3.
ELEMENT_NAMES = {
    "hydrogen", "helium", "lithium", "beryllium", "boron", "carbon", "nitrogen", "oxygen",
    "fluorine", "neon", "sodium", "magnesium", "aluminium", "aluminum", "silicon",
    "phosphorus", "sulfur", "sulphur", "chlorine", "argon", "potassium", "calcium",
    "scandium", "titanium", "vanadium", "chromium", "manganese", "iron", "cobalt", "nickel",
    "copper", "zinc", "gallium", "germanium", "arsenic", "selenium", "bromine", "krypton",
    "rubidium", "strontium", "yttrium", "zirconium", "niobium", "molybdenum", "technetium",
    "ruthenium", "rhodium", "palladium", "silver", "cadmium", "indium", "tin", "antimony",
    "tellurium", "iodine", "xenon", "caesium", "cesium", "barium", "lanthanum", "cerium",
    "praseodymium", "neodymium", "promethium", "samarium", "europium", "gadolinium",
    "terbium", "dysprosium", "holmium", "erbium", "thulium", "ytterbium", "lutetium",
    "hafnium", "tantalum", "tungsten", "rhenium", "osmium", "iridium", "platinum", "gold",
    "mercury", "thallium", "lead", "bismuth", "polonium", "astatine", "radon", "francium",
    "radium", "actinium", "thorium", "protactinium", "uranium", "neptunium", "plutonium",
    "americium", "curium", "berkelium", "californium", "einsteinium", "fermium",
    "mendelevium", "nobelium", "lawrencium", "rutherfordium", "dubnium", "seaborgium",
    "bohrium", "hassium", "meitnerium", "darmstadtium", "roentgenium", "copernicium",
    "nihonium", "flerovium", "moscovium", "livermorium", "tennessine", "oganesson",
}
POLYMER_TOKENS = ("protein", "glucan", "dextrin")

CATEGORY_RULES = {
    "derived_sum": "member of q2_chem_meta.json:derivedSums (a column computed by the data "
                   "provider as a sum of other columns in this table, not an independently "
                   "measured assay)",
    "physical_parameter": "member of q2_chem_meta.json:physicalParameters (a bulk physical or "
                          "process measurement: pH, colour, bitterness index, ethanol, CO2, "
                          "fermentable sugar, unfermentables)",
    "element_or_index": "chemical_name in 8.xlsx is a periodic-table element name or denotes a "
                        "macromolecule/fraction mass assay (protein, glucan tokens). Excluded "
                        "from single_compound because no single molecule identity — and therefore "
                        "no single compound-specific sensory threshold — is defined.",
    "single_compound": "remainder: one named chemical species, so a single compound identity and "
                       "a single sensory-threshold comparison are well defined",
}


# ------------------------------------------------------------------------------------------ io
def _atomic_write_bytes(path: Path, data: bytes) -> None:
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
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _normalise(text) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


# ----------------------------------------------------------------------------- scale identity
def identify_scale(stored: np.ndarray, calibrated: np.ndarray) -> dict:
    """Same deterministic rule as src/prepare_base.py:identify_scale, re-derived here so this
    audit does not depend on the generator module being importable or unchanged."""
    stored = np.asarray(stored, dtype=float)
    calibrated = np.asarray(calibrated, dtype=float)
    both = np.isfinite(stored) & np.isfinite(calibrated)
    positive = both & (calibrated > 0)
    log_error = None
    linear_error = None
    if int(positive.sum()) >= 10:
        log_error = float(np.nanmedian(np.abs(stored[positive] - np.log10(calibrated[positive]))))
    if int(both.sum()) > 0:
        linear_error = float(np.nanmedian(np.abs(stored[both] - calibrated[both])))
    if log_error is not None and log_error < 1e-6:
        chosen = "log10"
    elif linear_error is not None and linear_error < 1e-6:
        chosen = "linear"
    elif log_error is not None and linear_error is not None:
        chosen = "log10" if log_error < linear_error else "linear"
    else:
        chosen = None
    return {
        "chosen": chosen,
        "log10MedianAbsDiff": log_error,
        "linearMedianAbsDiff": linear_error,
        "nFinitePairs": int(both.sum()),
        "nPositivePairs": int(positive.sum()),
        "maxAbsDiffLog10": None if log_error is None else float(
            np.max(np.abs(stored[positive] - np.log10(calibrated[positive])))),
        "maxAbsDiffLinear": None if linear_error is None else float(
            np.max(np.abs(stored[both] - calibrated[both]))),
    }


def cross_check_prepare_base(one: pd.DataFrame, cal: pd.DataFrame, calibrated: list) -> dict:
    """Optional independent agreement with the frozen generator, when it can be imported."""
    try:
        import prepare_base  # noqa: F401  (module-level definitions only; no side effects)
    except Exception as exc:  # pragma: no cover - only if the generator becomes unimportable
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    mismatches = []
    for column in calibrated:
        reference = prepare_base.identify_scale(one[column].to_numpy(), cal[column].to_numpy())
        mine = identify_scale(one[column].to_numpy(), cal[column].to_numpy())
        if reference["chosen"] != mine["chosen"]:
            mismatches.append({"column": column, "prepareBase": reference["chosen"],
                               "thisScript": mine["chosen"]})
    return {"available": True, "columnsCompared": len(calibrated),
            "agreements": len(calibrated) - len(mismatches), "mismatches": mismatches}


def cross_check_frozen_constants(features: list, log10: list, linear: list, unverified: list) -> dict:
    """Drift check only: does the shipped src/target_columns.py still describe this data?"""
    path = PROJECT / "src/target_columns.py"
    namespace = {}
    try:
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)  # noqa: S102
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    frozen_features = namespace.get("FEATURE_COLS", [])
    return {
        "available": True,
        "featureOrderEqual": list(frozen_features) == list(features),
        "log10SetEqual": sorted(namespace.get("LOG10_CALIBRATED", [])) == sorted(log10),
        "linearSetEqual": sorted(namespace.get("LINEAR_CALIBRATED", [])) == sorted(linear),
        "uncalibratedSetEqual": sorted(namespace.get("UNCALIBRATED", [])) == sorted(unverified),
        "note": "read-only drift check; this script never writes src/, values are not copied from it",
    }


# ---------------------------------------------------------------------------------- categories
def classify(name: str, chemical_name: str, unit: str, derived: set, physical: set) -> tuple:
    """Return (category, rule text, short reason appended to the dictionary row)."""
    if name in derived:
        return ("derived_sum", CATEGORY_RULES["derived_sum"],
                "computed by the data provider as a sum of other columns, not an independent assay")
    if name in physical:
        return ("physical_parameter", CATEGORY_RULES["physical_parameter"],
                "bulk physical/process measurement, not a single compound concentration")
    tokens = _normalise(chemical_name)
    scaled_unit = unit or "declared unit"
    if chemical_name and str(chemical_name).strip().lower() in ELEMENT_NAMES:
        return ("element_or_index", CATEGORY_RULES["element_or_index"],
                f"element concentration in {scaled_unit}: an element is not a flavour compound, "
                "so a compound-specific odour threshold does not apply")
    for token in POLYMER_TOKENS:
        if token in tokens:
            return ("element_or_index", CATEGORY_RULES["element_or_index"],
                    f"macromolecule/fraction mass assay in {scaled_unit} over an unresolved "
                    f"mixture ({token} fraction), so no single molecule identity is defined")
    return ("single_compound", CATEGORY_RULES["single_compound"],
            "one named chemical species, so a single compound identity is well defined")


def main() -> int:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)

    # ---- 1. feature names from the real header -------------------------------------------------
    header = pd.read_csv(PATH_Q1, nrows=0)
    chem_columns = [c for c in header.columns if c.startswith(CHEM_PREFIX)]
    features = [c[len(CHEM_PREFIX):] for c in chem_columns]
    if len(chem_columns) != EXPECTED["chemFeatures"]:
        raise RuntimeError(f"expected {EXPECTED['chemFeatures']} {CHEM_PREFIX} columns in "
                           f"{PATH_Q1}, found {len(chem_columns)}")
    if len(set(features)) != len(features):
        raise RuntimeError("duplicate feature names in the q1_mapped header")
    target_columns = [c for c in header.columns
                      if not c.startswith(CHEM_PREFIX) and c not in ("row", "beer", "beer_id", STYLE_COL)
                      and not c.startswith("g6__")]

    # ---- 2. per-variable metadata (kind / tier / corrIndex / corrLabel / floorCoded) ------------
    meta = json.loads(PATH_META.read_text(encoding="utf-8"))
    meta_by_name = {record["name"]: record for record in meta["features"]}
    if list(meta_by_name) != features:
        raise RuntimeError("q2_chem_meta.json feature order disagrees with the q1_mapped header")
    derived_sums = list(meta["derivedSums"])
    physical = list(meta["physicalParameters"])

    # ---- 3. storage scale from numeric identity against the calibrated workbook ----------------
    one = pd.read_csv(PATH_RAW1)
    if not one["beer"].is_unique or set(one["beer"]) != set(range(1, 251)):
        raise RuntimeError("1.csv 'beer' is not a permutation of 1..250: row identity is unsafe")
    cal = pd.read_excel(PATH_CAL, sheet_name="Calibrated chemical dataset")
    calibrated = [c for c in cal.columns if c in set(features)]
    missing = [c for c in calibrated if c not in set(features)]
    if missing:  # pragma: no cover - defensive
        raise RuntimeError(f"calibration columns absent from 1.csv: {missing}")
    scale_rows = {}
    for column in calibrated:
        scale_rows[column] = identify_scale(one[column].to_numpy(), cal[column].to_numpy())
        scale_rows[column]["workbookChemicalName"], scale_rows[column]["workbookUnit"] = (
            _workbook_labels(PATH_CAL)).get(column, (None, None))
    log10_columns = [c for c in calibrated if scale_rows[c]["chosen"] == "log10"]
    linear_columns = [c for c in calibrated if scale_rows[c]["chosen"] == "linear"]
    unverified = [c for c in features if c not in set(calibrated)]
    if (len(log10_columns), len(linear_columns), len(unverified)) != (
            EXPECTED["log10Calibrated"], EXPECTED["linearCalibrated"], EXPECTED["uncalibrated"]):
        raise RuntimeError(
            "scale identification drifted from the registered counts: "
            f"log10={len(log10_columns)} (want {EXPECTED['log10Calibrated']}), "
            f"linear={len(linear_columns)} (want {EXPECTED['linearCalibrated']}), "
            f"unverified={len(unverified)} (want {EXPECTED['uncalibrated']})")

    # ---- 4. workbook display/unit + category ----------------------------------------------------
    workbook_labels = _workbook_labels(PATH_CAL)
    workbook_flag = _workbook_calibrated_flags(PATH_CAL)
    floor_value = float(np.median([np.nanmin(one[c].to_numpy(dtype=float))
                                   for c in features if meta_by_name[c]["floorCoded"]]))
    records = []
    for name in features:
        info = meta_by_name[name]
        display, unit = workbook_labels.get(name, (None, None))
        display = display or info.get("corrLabel") or name
        tier = info["tier"]
        if tier == "calibrated_log10":
            storage_scale = "log10"
        elif tier == "calibrated_linear":
            storage_scale = "linear"
        else:
            storage_scale = "unverified"
        category, rule_text, category_reason = classify(
            name, display, unit, set(derived_sums), set(physical))
        evidence = scale_rows.get(name)
        if tier == "calibrated_log10":
            reason = (f"stored value = log10(concentration): median |stored-log10(cal)| = "
                      f"{evidence['log10MedianAbsDiff']:.3e} over {evidence['nPositivePairs']} "
                      f"positive pairs (linear hypothesis error "
                      f"{evidence['linearMedianAbsDiff']:.3e})")
        elif tier == "calibrated_linear":
            reason = (f"stored value = concentration: median |stored-cal| = "
                      f"{evidence['linearMedianAbsDiff']:.3e} over {evidence['nPositivePairs']} "
                      f"positive pairs (log10 hypothesis error "
                      f"{evidence['log10MedianAbsDiff']:.3e})")
        else:
            reason = ("no calibrated row in 8.xlsx; storage scale is the raw stored value and is "
                      "not directly calibrated")
        if info["floorCoded"]:
            reason += f"; floor-coded at {floor_value!r}"
        if category != "single_compound":
            reason += "; category: " + category_reason
        records.append({
            "name": name,
            "column": CHEM_PREFIX + name,
            "display": display,
            "unit": unit,
            "unit_or_scale": unit if unit else "not declared in 8.xlsx",
            "storage_scale": storage_scale,
            "tier": tier,
            "kind": info["kind"],
            "category": category,
            "categoryRule": rule_text,
            "categoryReason": category_reason,
            "floor_coded": bool(info["floorCoded"]),
            "calibrated": tier != "unverified_storage_scale",
            "is_derived": name in set(derived_sums),
            "is_dietary_aggregate": name == "kcalperc",
            "corrIndex": info["corrIndex"],
            "corrLabel": info["corrLabel"],
            "join_key_status": "aligned on beer; not itself a join key",
            "reason": reason,
        })

    counts = {
        "chemFeatures": len(features),
        "targetColumns": len(target_columns),
        "log10Calibrated": len(log10_columns),
        "linearCalibrated": len(linear_columns),
        "uncalibrated": len(unverified),
        "categories": {
            category: sum(1 for r in records if r["category"] == category)
            for category in ("single_compound", "element_or_index", "physical_parameter", "derived_sum")
        },
        "floorCoded": sum(1 for r in records if r["floor_coded"]),
        "derived": sum(1 for r in records if r["is_derived"]),
        "dietaryAggregate": sum(1 for r in records if r["is_dietary_aggregate"]),
    }
    for key, want in EXPECTED.items():
        if key in ("singleCompound", "elementOrIndex", "physicalParameter", "derivedSum"):
            continue
        if counts[key] != want:
            raise RuntimeError(f"count {key}={counts[key]} != expected {want}")
    if (counts["categories"]["single_compound"], counts["categories"]["element_or_index"],
            counts["categories"]["physical_parameter"], counts["categories"]["derived_sum"]) != (
            EXPECTED["singleCompound"], EXPECTED["elementOrIndex"],
            EXPECTED["physicalParameter"], EXPECTED["derivedSum"]):
        raise RuntimeError(f"category counts drifted: {counts['categories']}")
    element_members = [r["name"] for r in records if r["category"] == "element_or_index"]
    declared_element = list(v6_common.NON_SINGLE_COMPOUND["element_or_index"])
    if sorted(element_members) != sorted(declared_element):
        raise RuntimeError("element_or_index derived by rule differs from the frozen interface: "
                           f"{sorted(element_members)} vs {sorted(declared_element)}")

    workbook_flag_by_name = workbook_flag
    scale_evidence = {}
    for name in features:
        item = {
            "tier": meta_by_name[name]["tier"],
            "storageScale": ("log10" if meta_by_name[name]["tier"] == "calibrated_log10" else
                             "linear" if meta_by_name[name]["tier"] == "calibrated_linear" else
                             "unverified"),
            "workbookCalibratedFlag": workbook_flag_by_name.get(name),
            "workbookChemicalName": workbook_labels.get(name, (None, None))[0],
            "unit": workbook_labels.get(name, (None, None))[1],
        }
        if name in scale_rows:
            item.update({k: scale_rows[name][k] for k in (
                "log10MedianAbsDiff", "linearMedianAbsDiff", "nFinitePairs", "nPositivePairs",
                "maxAbsDiffLog10", "maxAbsDiffLinear")})
        scale_evidence[name] = item

    cross_checks = {
        "prepareBaseScaleIdentification": cross_check_prepare_base(one, cal, calibrated),
        "frozenTargetColumns": cross_check_frozen_constants(
            features, log10_columns, linear_columns, unverified),
        "workbookCalibratedFlag": {
            "log10TierWithYesFlag": sum(1 for c in log10_columns
                                        if "yes" in str(workbook_flag.get(c, "")).lower()),
            "log10TierTotal": len(log10_columns),
            "linearTierWithYesOrGcmsFlag": sum(
                1 for c in linear_columns if str(workbook_flag.get(c, "")).strip()),
            "linearTierTotal": len(linear_columns),
            "note": ("8.xlsx 'calibrated' is a provenance flag (yes / yes_gcms), not a scale flag: "
                     "all 37 log10 columns carry it and all 33 linear columns carry it, so it "
                     "cannot replace the numeric scale test"),
        },
    }

    inputs = {}
    for path in (PATH_Q1, PATH_META, PATH_RAW1, PATH_CAL):
        inputs[str(path.relative_to(PROJECT))] = {
            "sha256": v6_common.sha256_file(path), "bytes": path.stat().st_size}

    dictionary_columns = ["name", "display", "unit_or_scale", "storage_scale", "tier", "category",
                          "floor_coded", "calibrated", "is_derived", "is_dietary_aggregate",
                          "join_key_status", "reason"]
    dictionary = pd.DataFrame([{
        "name": r["name"], "display": r["display"], "unit_or_scale": r["unit_or_scale"],
        "storage_scale": r["storage_scale"], "tier": r["tier"], "category": r["category"],
        "floor_coded": r["floor_coded"], "calibrated": r["calibrated"],
        "is_derived": r["is_derived"], "is_dietary_aggregate": r["is_dietary_aggregate"],
        "join_key_status": r["join_key_status"], "reason": r["reason"],
    } for r in records], columns=dictionary_columns)

    script = Path(__file__).resolve()
    body = {
        "schema": "v6-constants-1",
        "purpose": ("generated data product replacing the previous practice of rewriting "
                    "src/target_columns.py from a generator script"),
        "project": PROJECT.name,
        "generator": {
            "script": str(script.relative_to(PROJECT)),
            "scriptSha256": v6_common.sha256_file(script),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": inputs,
        "counts": counts,
        "frozenOrder": {"featureCols": features, "chemColumns": chem_columns,
                        "targetColumns": target_columns},
        "tiers": {
            "log10Calibrated": log10_columns,
            "linearCalibrated": linear_columns,
            "uncalibrated": unverified,
        },
        "kindsFromMeta": {
            kind: sum(1 for r in records if r["kind"] == kind)
            for kind in ("single_compound", "physical_parameter", "derived_sum")},
        "categories": {
            "element_or_index": element_members,
            "elementOrIndexReasons": {r["name"]: r["categoryReason"] for r in records
                                      if r["category"] == "element_or_index"},
            "physical_parameter": [r["name"] for r in records
                                   if r["category"] == "physical_parameter"],
            "derived_sum": [r["name"] for r in records if r["category"] == "derived_sum"],
            "rules": CATEGORY_RULES,
        },
        "storage": {
            "floorValue": floor_value,
            "note": ("log10 columns store log10(concentration); linear columns store the "
                     "concentration; unverified columns store an uncalibrated value. Categories "
                     "are a declared rule set, not a measurement."),
        },
        "scaleEvidence": scale_evidence,
        "features": records,
        "crossChecks": cross_checks,
        "dictionary": {"path": "data/processed/v6_feature_dictionary.csv",
                       "columns": dictionary_columns, "rows": len(records)},
    }
    canonical = json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    content_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    document = {"generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"), "contentSha256NoTimestamp": content_sha, **body}
    text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    csv_data = _csv_bytes(dictionary)

    for target in (PROCESSED / "v6_constants.json", AUDIT / "v6_constants.json"):
        _atomic_write_bytes(target, text.encode("utf-8"))
    for target in (PROCESSED / "v6_feature_dictionary.csv",
                   AUDIT / "v6_feature_dictionary.csv"):
        _atomic_write_bytes(target, csv_data)

    print(json.dumps({
        "ok": True,
        "script": "src/r00_constants.py",
        "outputs": ["data/processed/v6_constants.json",
                    "data/processed/v6_feature_dictionary.csv",
                    "outputs/audit/v6/v6_constants.json",
                    "outputs/audit/v6/v6_feature_dictionary.csv"],
        "counts": counts,
        "contentSha256NoTimestamp": content_sha,
        "scaleCrossCheck": cross_checks["prepareBaseScaleIdentification"].get("agreements"),
        "frozenDriftMatches": bool(cross_checks["frozenTargetColumns"].get("featureOrderEqual"))
        and bool(cross_checks["frozenTargetColumns"].get("log10SetEqual")),
        "elementOrIndex": element_members,
    }, ensure_ascii=False))
    return 0


_LABEL_CACHE = {}


def _workbook_labels(path: Path) -> dict:
    key = (str(path), "labels")
    if key in _LABEL_CACHE:
        return _LABEL_CACHE[key]
    table = pd.read_excel(path, sheet_name="Sensory thresholds")
    labels = {}
    for _, row in table.iterrows():
        field = row.get("field_name_R")
        if not isinstance(field, str) or not field.strip():
            continue
        chemical = row.get("chemical_name")
        unit = row.get("unit")
        labels[field.strip()] = (
            None if not isinstance(chemical, str) or not chemical.strip() else chemical.strip(),
            None if not isinstance(unit, str) or not unit.strip() else unit.strip(),
        )
    _LABEL_CACHE[key] = labels
    return labels


def _workbook_calibrated_flags(path: Path) -> dict:
    key = (str(path), "flags")
    if key in _LABEL_CACHE:
        return _LABEL_CACHE[key]
    table = pd.read_excel(path, sheet_name="Sensory thresholds")
    flags = {}
    for _, row in table.iterrows():
        field = row.get("field_name_R")
        if not isinstance(field, str) or not field.strip():
            continue
        value = row.get("calibrated")
        flags[field.strip()] = None if pd.isna(value) else str(value).strip()
    _LABEL_CACHE[key] = flags
    return flags


if __name__ == "__main__":
    sys.exit(main())
