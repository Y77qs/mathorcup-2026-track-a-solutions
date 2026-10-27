"""q1_baseline_fix.py — Q1 training-median baseline under the frozen 3x3x3 nested CV.

WHY: `baseline-compare` needs a real succeeded BASELINE experiment whose metric is
recorded in the ledger, not a number copied into a table. This is the simplest
possible predictor (per-target training median, fitted inside each outer training
set only) evaluated on exactly the same OOF rows as the candidates.

Outputs (experiment dir): predictions.csv, metrics.json, outputs.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v6_common as C  # noqa: E402

MODEL = "median"


def main() -> int:
    frame = C.load_frame(C.DATA_Q1)
    frame = frame.set_index("beer", drop=False)
    targets = C.all_targets(frame)
    af = C.af_targets(frame)
    styles = dict(zip(frame["beer"], frame[C.STYLE_COL].astype(str)))

    rows, pred_frames = [], []
    per_repeat = {}
    for repeat, outer, train_beers, test_beers in C.iter_outer():
        train = frame.loc[train_beers]
        test = frame.loc[test_beers]
        med = train[targets].median(axis=0)
        pred = pd.DataFrame(np.tile(med.to_numpy(dtype=float), (len(test), 1)),
                            index=test.index, columns=targets)
        block = C.regression_block(test[targets].to_numpy(float), pred.to_numpy(float), targets,
                                   styles=[styles[b] for b in test_beers])
        per_repeat.setdefault(str(repeat), []).append(block["mae"])
        out = pd.DataFrame({"beer": test.index.astype(int), "repeat": repeat, "outer_fold": outer})
        for t in targets:
            out[f"y_pred__{t}"] = pred[t].to_numpy(float)
            out[f"y_true__{t}"] = test[t].to_numpy(float)
        pred_frames.append(out)

    predictions = pd.concat(pred_frames, ignore_index=True)
    y_true = predictions[[f"y_true__{t}" for t in targets]].to_numpy(float)
    y_pred = predictions[[f"y_pred__{t}" for t in targets]].to_numpy(float)
    style_values = [styles[b] for b in predictions["beer"]]
    pooled = C.regression_block(y_true, y_pred, targets, styles=style_values)
    # PRIMARY metric must be the SAME definition as the candidate: uniform-average MAE over
    # the 30 Aroma/Flavour targets. The 50-dim value is a secondary number (mae_all50).
    af_index = [targets.index(t) for t in af]
    pooled_af = C.regression_block(y_true[:, af_index], y_pred[:, af_index], af, styles=style_values)
    metrics = {
        "mae": pooled_af["mae"],
        "mae_all50": pooled["mae"],
        "macro_r2_50": pooled.get("macro_r2", float("nan")),
        "macro_r2_af30": pooled_af.get("macro_r2", float("nan")),
        "n_rows": int(len(predictions)),
        "n_targets": len(targets),
        "n_targets_af30": len(af),
        "n_repeats": C.N_REPEATS,
    }
    # per-repeat pooled AF30 MAE (3 values), never averaged into a single claim
    for repeat in per_repeat:
        mask = predictions["repeat"] == int(repeat)
        metrics[f"mae_rep{repeat}"] = float(
            np.abs(y_true[mask.to_numpy()][:, af_index] - y_pred[mask.to_numpy()][:, af_index]).mean())

    metrics = {k: float(v) for k, v in metrics.items() if np.isfinite(v)}
    directory = C.out_dir(__file__)
    C.save_csv(predictions, "predictions.csv", directory)
    C.emit_metrics(metrics)
    C.emit_output("q1_baseline", {
        "model": MODEL,
        "protocol": {
            "splits": C.SPLITS_CSV.relative_to(C.PROJECT).as_posix(),
            "splits_sha256": C.sha256_file(C.SPLITS_CSV),
            "seeds": list(C.SEEDS),
            "repeats": C.N_REPEATS,
            "definition": "per-target training median fitted inside each outer training set; OOF pooled over 3 repeats",
        },
        "per_repeat_mae_af30": {k: [float(x) for x in v] for k, v in per_repeat.items()},
        "note": "this baseline never sees the outer test rows; it is the reference for Skill = 1 - MAE/MAE_baseline",
    })
    print({"ok": True, "malformed": False, "mae": metrics["mae"], "mae_all50": metrics["mae_all50"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
