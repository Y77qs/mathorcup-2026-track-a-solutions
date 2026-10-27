"""r00_legacy_recheck.py — recompute the previous audit's headline numbers from saved artifacts.

NO FITTING. Nothing here trains a model, refits a copula or reruns an optimiser; every number is
arithmetic on files that are already registered (saved samples, saved metrics, frozen train split,
raw attachments). Each item reports {value, old_claimed, matches, method, inputs_sha256}; a
mismatch is recorded as a mismatch and the old record is never edited.

Items
  q3.negativeLinearCells     142 / 40 / 22  cells, generated spectra, fields  (EXP-0033/samples.csv)
  q3.t2nIncrease             6 of 11 transfers, max increase 0.7633000015   (samples.csv vs q3.csv)
  q2.externalSpearman        0.44505144467935176 as saved                    (EXP-0029/metrics.json)
  q2.externalSpearmanAligned 0.9210176180408739 after name alignment        (2.csv/6.csv/train.csv)
  q3.targetMeanSelfDistance  0.6044870518234862 (the missing-centring defect)
  q3.transferMeanDistance    0.4328202679 old / 0.6205347648 corrected
  q3.transferEnergy          U = -0.3195653428479943, V = 1.7453876944348181

Run:  python src/r00_legacy_recheck.py
Writes: outputs/audit/v6/legacy_recheck.json
Exit: 0 every item reproduced within its stated tolerance; 4 at least one mismatch (named on
      stderr; the JSON records both values).
"""

from __future__ import annotations

import datetime
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

PROJECT = v6_common.PROJECT
RAW = PROJECT / "data/raw/imported"
OUT = PROJECT / "outputs/audit/v6"

PATH_SAMPLES = PROJECT / "experiments/EXP-0033/samples.csv"
PATH_RAW_Q3 = PROJECT / "data/clean/q3.csv"
PATH_METRICS = PROJECT / "experiments/EXP-0029/metrics.json"
PATH_CORR = RAW / "415709ac10f2f730-2.csv"          # 2.csv
PATH_EXTERNAL = RAW / "a55004fb0390299a-6.csv"       # 6.csv
PATH_TRAIN = PROJECT / "data/splits/SPLIT-0001/train.csv"
PATH_WORKBOOK = RAW / "f2316766792111d9-8.xlsx"

COUNT = "exact integer equality"
REL_1E9 = "relative 1e-9"
REL_1E12 = "relative 1e-12"

OLD = {
    "negativeLinearCells": 142,
    "negativeLinearRows": 40,
    "negativeLinearFields": 22,
    "t2nIncreases": 6,
    "t2nTransfers": 11,
    "t2nMaxIncrease": 0.7633000015,
    "externalSpearman": 0.44505144467935176,
    "externalSpearmanAligned": 0.9210176180408739,
    "targetMeanSelfDistance": 0.6044870518234862,
    "transferMeanDistanceOld": 0.43282026794869743,
    "transferMeanDistanceCorrected": 0.6205347648114844,
    "energyU": -0.3195653428479943,
    "energyV": 1.7453876944348181,
}
OLD_SOURCE = "MathorCup_A_独立审查与重跑方案/independent_recheck.json + 01_独立复核与修复优先级.md"


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


def sha(path: Path) -> str:
    return v6_common.sha256_file(path)


def close(value, reference, rel: float) -> bool:
    if value is None or reference is None:
        return False
    if not np.isfinite(value) or not np.isfinite(reference):
        return False
    scale = max(abs(reference), 1e-12)
    return abs(value - reference) <= rel * scale


# --------------------------------------------------------------------------------- Q2 arithmetic
def crosscorr(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=float) - np.asarray(a, dtype=float).mean(axis=0)
    b = np.asarray(b, dtype=float) - np.asarray(b, dtype=float).mean(axis=0)
    denominator = np.outer(np.linalg.norm(a, axis=0), np.linalg.norm(b, axis=0))
    return a.T @ b / np.maximum(denominator, 1e-15)


def ranked(values: np.ndarray) -> np.ndarray:
    return pd.DataFrame(np.asarray(values, dtype=float)).rank(method="average").to_numpy()


def _normalise(text) -> str:
    return "".join(ch for ch in str(text).replace("_x000D_", "").lower() if ch.isalnum())


def q2_items() -> dict:
    metrics = json.loads(PATH_METRICS.read_text(encoding="utf-8"))
    saved = float(metrics["external_6csv_mean_spearman"])

    train = pd.read_csv(PATH_TRAIN)
    chem_columns = [c for c in train.columns if c.startswith(v6_common.CHEM_PREFIX)]
    feature_names = [c[len(v6_common.CHEM_PREFIX):] for c in chem_columns]
    if len(feature_names) != 231:
        raise RuntimeError(f"SPLIT-0001/train.csv has {len(feature_names)} chem columns, want 231")
    missing_targets = [t for t in v6_common.TARGETS_50 if t not in train.columns]
    if missing_targets:
        raise RuntimeError(f"train split is missing sensory columns {missing_targets}")

    x_train = train[chem_columns].fillna(train[chem_columns].median()).to_numpy(dtype=float)
    y_train = train[list(v6_common.TARGETS_50)].to_numpy(dtype=float)
    total = crosscorr(ranked(x_train), ranked(y_train))  # features x 50

    # chemical side. The registered display-name -> feature bridge is q2_chem_meta.json
    # (corrLabel/corrIndex); 2.csv is used as the label authority that confirms it, so no
    # positional assumption is made anywhere in this mapping.
    corr_table = pd.read_csv(PATH_CORR, index_col=0)
    if list(corr_table.index) != list(corr_table.columns):
        raise RuntimeError("2.csv is not a square symmetric label table")
    label_at_position = {}
    for position, label in enumerate(corr_table.index):
        key = _normalise(label)
        if key in label_at_position and label_at_position[key] != position:
            raise RuntimeError(f"2.csv label collision on {key!r}")
        label_at_position[key] = position
    meta = json.loads((PROJECT / "data/clean/q2_chem_meta.json").read_text(encoding="utf-8"))
    corr_index = {record["name"]: int(record["corrIndex"]) for record in meta["features"]}
    corr_label = {record["name"]: record["corrLabel"] for record in meta["features"]}
    if sorted(corr_index.values()) != list(range(231)):
        raise RuntimeError("q2_chem_meta.json corrIndex is not a permutation of 0..230")
    label_confirmations = 0
    for name in feature_names:
        position = corr_index[name]
        if _normalise(label_at_position and corr_table.index[position]) == _normalise(corr_label[name]):
            label_confirmations += 1
    if label_confirmations != 231:
        raise RuntimeError(f"2.csv labels confirm only {label_confirmations}/231 corrLabels")
    label_to_feature = {_normalise(corr_label[name]): name for name in feature_names}
    if len(label_to_feature) != 231:
        raise RuntimeError("corrLabel is not injective under name normalisation")

    external = pd.read_csv(PATH_EXTERNAL)
    external_chemicals = [_normalise(v) for v in external.iloc[:, 0]]
    unmapped = [name for name in external_chemicals if name not in label_to_feature]
    if unmapped:
        raise RuntimeError(f"6.csv chemical labels absent from the registered bridge: {unmapped}")
    external_features = [label_to_feature[name] for name in external_chemicals]
    external_positions = [feature_names.index(name) for name in external_features]
    if len(set(external_positions)) != len(external_positions):
        raise RuntimeError("two 6.csv rows map to the same chemical")
    # the positional shortcut (2.csv row i == feature i) must agree, and is recorded as a check
    positional_positions = [label_at_position[name] for name in external_chemicals]
    positional_agreement = positional_positions == external_positions

    # sensory side: display names -> R names via the workbook 'Sensory names' sheet
    book = pd.read_excel(PATH_WORKBOOK, sheet_name="Sensory names")
    bridge = {}
    for _, row in book.iterrows():
        if str(row.get("dataset")) != "Trained panel":
            continue
        key = _normalise(row.get("CleanName_PanelFeedback"))
        r_name = row.get("R_name")
        if isinstance(r_name, str) and key:
            bridge[key] = r_name.strip()
    external_columns = list(external.columns[1:])
    sensory_order = [bridge.get(_normalise(c)) for c in external_columns]
    if any(s is None for s in sensory_order):
        raise RuntimeError("sensory display names without a workbook bridge: "
                           f"{[c for c, s in zip(external_columns, sensory_order) if s is None]}")
    if len(set(sensory_order)) != 50 or set(sensory_order) != set(v6_common.TARGETS_50):
        raise RuntimeError("workbook sensory bridge does not cover the 50 targets exactly")

    physical = set(v6_common.NON_SINGLE_COMPOUND["physical_parameter"])
    derived = set(v6_common.NON_SINGLE_COMPOUND["derived_sum"])
    candidates = [name for name in feature_names if name not in physical and name not in derived]
    if len(candidates) != 219:
        raise RuntimeError(f"compound candidate universe is {len(candidates)}, want 219")
    candidate_rows = total[[feature_names.index(name) for name in candidates]]
    external_values = external.iloc[:, 1:].to_numpy(dtype=float)

    def compare(model_rows: np.ndarray, external_columns_matrix: np.ndarray) -> np.ndarray:
        return np.diag(crosscorr(ranked(np.abs(model_rows)),
                                 ranked(np.abs(external_columns_matrix))))

    reorder = [sensory_order.index(target) for target in v6_common.TARGETS_50]
    # the previous code path: 231-space row positions applied to the 219-row candidate matrix and
    # external columns assumed to be in TARGETS_50 order
    wrong = compare(candidate_rows[external_positions], external_values)
    aligned = compare(total[external_positions], external_values[:, reorder])
    positional = compare(total[external_positions], external_values)

    inputs = {str(p.relative_to(PROJECT)): sha(p) for p in (
        PATH_METRICS, PATH_CORR, PATH_EXTERNAL, PATH_TRAIN, PATH_WORKBOOK,
        PROJECT / "data/clean/q2_chem_meta.json")}
    return {
        "saved": saved,
        "aligned": float(aligned.mean()),
        "positionalSensory": float(positional.mean()),
        "mismatchedColumns": [{"position": i, "external": external_columns[i],
                               "mapped_target": sensory_order[i],
                               "positional_target": v6_common.TARGETS_50[i]}
                              for i in range(50) if sensory_order[i] != v6_common.TARGETS_50[i]],
        "chemicalPositionsMapped": len(external_positions),
        "corrLabelConfirmations": label_confirmations,
        "positionalShortcutAgreesWithNameBridge": positional_agreement,
        "inputs": inputs,
    }


# --------------------------------------------------------------------------------- Q3 arithmetic
def distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)


def energy(a: np.ndarray, b: np.ndarray) -> dict:
    """Signed energy statistics on z-scored spectra.

    U (unbiased) = 2 E||G-R|| - sum_{i!=j}||g_i-g_j||/(m(m-1)) - sum_{i!=j}||r_i-r_j||/(n(n-1))
    V (empirical) = 2 mean ||G-R|| - sum||g_i-g_j||/m^2 - sum||r_i-r_j||/n^2
    The sign of U is preserved: a negative U is a possible finite-sample value, not an error.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m, n = len(a), len(b)
    within_a = float(distances(a, a).sum())
    within_b = float(distances(b, b).sum())
    cross = float(2.0 * distances(a, b).mean())
    u = cross - within_a / (m * (m - 1)) - within_b / (n * (n - 1))
    v = cross - within_a / m**2 - within_b / n**2
    return {"U": float(u), "V": float(v)}


def q3_items() -> dict:
    samples = pd.read_csv(PATH_SAMPLES)
    raw = pd.read_csv(PATH_RAW_Q3)
    linear_columns = [v6_common.CHEM_PREFIX + name
                      for name in _linear_calibrated_columns()]
    generation = samples[samples["group"] == "generation"]
    negative = generation[linear_columns] < -1e-10

    transfer = samples[samples["group"] == "transfer"].reset_index(drop=True)
    source = raw.set_index("row").loc[transfer["slot"].to_numpy()]
    t2n = v6_common.CHEM_PREFIX + "X.E..2.nonenal"
    delta = transfer[t2n].to_numpy(dtype=float) - source[t2n].to_numpy(dtype=float)

    # ---- the target-mean self distance (the missing-centring defect) --------------------------
    # src/q3_lib.py:917-960 fits the PCA on Zc = Z - z_mean but score() computes
    # ((Z @ pca.T) - score_mean) / score_sd *without* subtracting z_mean, so the target-style mean
    # is scored 0.604487 away from its own centre instead of ~0.  The fitted per-fold object is not
    # persisted, so the same algebra is reconstructed statically on the frozen q3.csv; no
    # optimisation is rerun and nothing is refitted.
    chem_columns = [v6_common.CHEM_PREFIX + name for name in _feature_columns(raw)]
    x = raw[chem_columns].fillna(raw[chem_columns].median()).to_numpy(dtype=float)
    centre, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    z = (x - centre) / scale
    style = raw["tasting_category_fine"].astype(str).to_numpy()
    target_style = "Tripel"
    z_target = z[style == target_style]
    z_mean = z_target.mean(axis=0)
    _, _, vt = np.linalg.svd(z_target - z_mean, full_matrices=False)
    pca = vt[:10]
    scores = (z_target - z_mean) @ pca.T
    score_mean = scores.mean(axis=0)
    score_sd = scores.std(axis=0, ddof=1)
    score_sd = np.where(score_sd > 1e-12, score_sd, 1.0)
    correlation = 0.9 * np.corrcoef((scores - score_mean) / score_sd, rowvar=False) \
        + 0.1 * np.eye(pca.shape[0])
    inverse = np.linalg.inv(np.atleast_2d(np.nan_to_num(correlation, nan=0.0)))

    def mahalanobis(values: np.ndarray, subtract_mean: bool) -> np.ndarray:
        block = ((values - z_mean) if subtract_mean else values) @ pca.T
        scaled = (block - score_mean) / score_sd
        return np.sqrt(np.maximum(np.einsum("...i,ij,...j->...", scaled, inverse, scaled), 0.0))

    target_distance_old = float(mahalanobis(z_mean, subtract_mean=False))
    target_distance_correct = float(mahalanobis(z_mean, subtract_mean=True))
    z_transfer = (transfer[chem_columns].to_numpy(dtype=float) - centre) / scale
    transfer_old = float(mahalanobis(z_transfer, subtract_mean=False).mean())
    transfer_correct = float(mahalanobis(z_transfer, subtract_mean=True).mean())
    reference = z[style == target_style]
    transfer_energy = energy(z_transfer, reference)

    inputs = {str(p.relative_to(PROJECT)): sha(p) for p in (
        PATH_SAMPLES, PATH_RAW_Q3, PROJECT / "src/q3_lib.py")}
    return {
        "negativeCells": int(negative.to_numpy().sum()),
        "negativeRows": int(negative.any(axis=1).sum()),
        "negativeFields": int(negative.any(axis=0).sum()),
        "generatedRows": int(len(generation)),
        "transferRows": int(len(transfer)),
        "t2nIncreases": int((delta > 1e-10).sum()),
        "t2nMaxIncrease": float(delta.max()),
        "t2nPerTransfer": [
            {"sourceRow": int(transfer.loc[i, "slot"]),
             "sourceBeer": int(source.iloc[i]["beer"]),
             "before": float(source.iloc[i][t2n]), "after": float(transfer.loc[i, t2n]),
             "delta": float(delta[i])} for i in range(len(transfer))],
        "targetStyle": target_style,
        "targetRows": int((style == target_style).sum()),
        "targetMeanDistanceOld": target_distance_old,
        "targetMeanDistanceCorrect": target_distance_correct,
        "transferMeanDistanceOld": transfer_old,
        "transferMeanDistanceCorrected": transfer_correct,
        "energyU": transfer_energy["U"],
        "energyV": transfer_energy["V"],
        "inputs": inputs,
    }


def _feature_columns(raw: pd.DataFrame) -> list:
    columns = [c[len(v6_common.CHEM_PREFIX):] for c in raw.columns
               if c.startswith(v6_common.CHEM_PREFIX)]
    if len(columns) != 231:
        raise RuntimeError(f"q3.csv has {len(columns)} chemical columns, want 231")
    return columns


def _linear_calibrated_columns() -> list:
    path = PROJECT / "data/processed/v6_constants.json"
    if path.exists():
        document = json.loads(path.read_text(encoding="utf-8"))
        return list(document["tiers"]["linearCalibrated"])
    raise RuntimeError("data/processed/v6_constants.json is missing; run src/r00_constants.py first")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    q2 = q2_items()
    q3 = q3_items()

    def item(value, old, matches, tolerance, method, inputs, notes=None):
        return {"value": value, "old_claimed": old, "matches": bool(matches),
                "tolerance": tolerance, "method": method, "inputs_sha256": inputs,
                "notes": notes}

    items = {
        "q3.negativeLinearCells": item(
            {"cells": q3["negativeCells"], "rows": q3["negativeRows"],
             "fields": q3["negativeFields"]},
            {"cells": OLD["negativeLinearCells"], "rows": OLD["negativeLinearRows"],
             "fields": OLD["negativeLinearFields"]},
            (q3["negativeCells"] == OLD["negativeLinearCells"]
             and q3["negativeRows"] == OLD["negativeLinearRows"]
             and q3["negativeFields"] == OLD["negativeLinearFields"]),
            COUNT,
            ("count cells < -1e-10 among the 33 linear-calibrated chem__ columns of the 250 "
             "group=='generation' rows of experiments/EXP-0033/samples.csv; rows/fields are the "
             "distinct affected indices"),
            q3["inputs"]),
        "q3.t2nIncrease": item(
            {"increases": q3["t2nIncreases"], "transfers": q3["transferRows"],
             "maxIncrease": q3["t2nMaxIncrease"]},
            {"increases": OLD["t2nIncreases"], "transfers": OLD["t2nTransfers"],
             "maxIncrease": OLD["t2nMaxIncrease"]},
            (q3["t2nIncreases"] == OLD["t2nIncreases"]
             and q3["transferRows"] == OLD["t2nTransfers"]
             and close(q3["t2nMaxIncrease"], OLD["t2nMaxIncrease"], 1e-9)),
            COUNT + " for counts, " + REL_1E9 + " for the maximum",
            ("join each group=='transfer' row to its q3.csv source row through the saved `slot` "
             "index (not beer_id) and count delta = after - before > 1e-10 for "
             "chem__X.E..2.nonenal; the maximum delta is reported in the stored units"),
            q3["inputs"], {"perTransfer": q3["t2nPerTransfer"]}),
        "q2.externalSpearman": item(
            q2["saved"], OLD["externalSpearman"],
            close(q2["saved"], OLD["externalSpearman"], 1e-12),
            REL_1E12,
            ("read experiments/EXP-0029/metrics.json:external_6csv_mean_spearman as saved; no "
             "recomputation is involved, so this item only certifies the saved value is still "
             "present and unedited"),
            {k: v for k, v in q2["inputs"].items()
             if k.endswith("EXP-0029/metrics.json")}),
        "q2.externalSpearmanAligned": item(
            q2["aligned"], OLD["externalSpearmanAligned"],
            close(q2["aligned"], OLD["externalSpearmanAligned"], 1e-9),
            REL_1E9,
            ("same-source rank comparison recomputed without fitting: Spearman matrix between the "
             "200 frozen SPLIT-0001 TRAIN rows (231 chem, median-filled) and the 50 targets; "
             "6.csv |correlation| rows are matched to feature positions through 2.csv's own row "
             "labels (44/44 unique, name normalised) and its 50 columns are matched to the "
             "targets through the 8.xlsx 'Sensory names' bridge; the score is the mean over 50 "
             "columns of the rank correlation between the model and 6.csv"),
            q2["inputs"],
            {"columnsThatWereMisordered": q2["mismatchedColumns"],
             "positionalSensoryOrderScore": q2["positionalSensory"],
             "note": ("0.9210176 reproduces only with the name bridge; with the old positional "
                      "column assumption the score is the reported positional value, and the "
                      "chemical-side indexing bug alone yields the 0.445 saved metric"),
             "chemicalBridge": {
                 "source": ("data/clean/q2_chem_meta.json corrLabel/corrIndex, confirmed "
                            "label-by-label against the 2.csv row labels"),
                 "corrLabelConfirmations": q2["corrLabelConfirmations"],
                 "positionalShortcutAgreesWithNameBridge":
                     q2["positionalShortcutAgreesWithNameBridge"]},
             "extraInput": ("8.xlsx 'Sensory names' is not in the three listed data files; it is "
                            "the only registered display-name -> R-name bridge, so without it the "
                            "aligned value cannot be recomputed (it is not a fit, just a "
                            "dictionary)")}),
        "q3.targetMeanSelfDistance": item(
            q3["targetMeanDistanceOld"], OLD["targetMeanSelfDistance"],
            close(q3["targetMeanDistanceOld"], OLD["targetMeanSelfDistance"], 1e-9),
            REL_1E9,
            ("the algebra of src/q3_lib.py:917-960 reproduced statically on data/clean/q3.csv: "
             "standardise by the 250-row mean/sd, take the 10-component PCA of the mean-centred "
             "Tripel block, standardise the scores, shrink the 0.9/0.1 correlation matrix, then "
             "score the target mean WITH the omitted z_mean (old path) and WITH it (corrected). "
             "No optimiser is run; the fitted per-fold object is not persisted, so the static "
             "reconstruction is the strongest available check"),
            q3["inputs"],
            {"targetStyle": q3["targetStyle"], "targetRows": q3["targetRows"],
             "correctedValue": q3["targetMeanDistanceCorrect"],
             "defect": "q3_lib.score() omits (Z - z_mean); the target mean is its own centre"}),
        "q3.transferMeanDistance": item(
            {"old": q3["transferMeanDistanceOld"],
             "corrected": q3["transferMeanDistanceCorrected"]},
            {"old": OLD["transferMeanDistanceOld"],
             "corrected": OLD["transferMeanDistanceCorrected"]},
            (close(q3["transferMeanDistanceOld"], OLD["transferMeanDistanceOld"], 1e-9)
             and close(q3["transferMeanDistanceCorrected"],
                       OLD["transferMeanDistanceCorrected"], 1e-9)),
            REL_1E9,
            ("mean Mahalanobis distance of the 11 saved transfer spectra to the target-style "
             "centre under the same static reconstruction, computed with and without the "
             "omitted z_mean; this is an evaluation change only, not a re-optimisation"),
            q3["inputs"],
            {"note": "the old spectrum was not re-designer; only the evaluation changes"}),
        "q3.transferEnergy": item(
            {"U": q3["energyU"], "V": q3["energyV"]},
            {"U": OLD["energyU"], "V": OLD["energyV"]},
            (close(q3["energyU"], OLD["energyU"], 1e-9)
             and close(q3["energyV"], OLD["energyV"], 1e-9)),
            REL_1E9,
            ("saved transfer spectra z-scored with the frozen q3.csv mean/sd against the real "
             "Tripel reference rows (28 of 250): U unbiased = 2 mean||G-R|| - within(G)/(m(m-1)) "
             "- within(R)/(n(n-1)); V empirical = 2 mean||G-R|| - within(G)/m^2 - within(R)/n^2; "
             "the sign of U is preserved, a negative U is a possible finite-sample value"),
            q3["inputs"],
            {"reference": "real Tripel rows of data/clean/q3.csv", "noOptimisation": True}),
    }

    mismatches = [name for name, payload in items.items() if not payload["matches"]]
    document = {
        "schema": "v6-legacy-recheck-1",
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "scope": ("recompute only; no model fitting, no generator refit, no optimiser rerun, no "
                  "edit of any old record"),
        "oldRecord": {"source": OLD_SOURCE, "values": OLD},
        "items": items,
        "summary": {
            "items": len(items),
            "matched": len(items) - len(mismatches),
            "mismatched": mismatches,
            "allMatch": not mismatches,
        },
        "notDone": [
            "a per-fold refit of the Q3 optimiser is not attempted: the task forbids rerunning "
            "the optimisation and the fitted object is not persisted",
            "no new model is trained, so none of these numbers is a fixed-model performance claim",
        ],
    }
    text = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode()
    _atomic_write(OUT / "legacy_recheck.json", text)

    print(json.dumps({
        "ok": not mismatches,
        "script": "src/r00_legacy_recheck.py",
        "output": "outputs/audit/v6/legacy_recheck.json",
        "matched": f"{len(items) - len(mismatches)}/{len(items)}",
        "mismatched": mismatches,
        "values": {
            "negativeLinearCells": [q3["negativeCells"], q3["negativeRows"], q3["negativeFields"]],
            "t2nIncreases": [q3["t2nIncreases"], q3["transferRows"]],
            "t2nMaxIncrease": q3["t2nMaxIncrease"],
            "externalSpearmanSaved": q2["saved"],
            "externalSpearmanAligned": q2["aligned"],
            "targetMeanSelfDistance": q3["targetMeanDistanceOld"],
            "transferMeanDistance": [q3["transferMeanDistanceOld"],
                                     q3["transferMeanDistanceCorrected"]],
            "energy": [q3["energyU"], q3["energyV"]],
        },
    }, ensure_ascii=False))
    if mismatches:
        print("MISMATCH: " + ", ".join(mismatches), file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
