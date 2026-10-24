"""Q1 旧 EXP-0029 的 test 部分：50 维逐目标独立复算（事后审计，不是独立复跑）。

事实边界（必须随结果一起读）：
  * EXP-0029 的代码/依赖没有完整冻结（OOF 来自项目外工件），因此**不能**把本脚本算出的
    一致性写成 "independent-rerun passed"；它只复核"已落盘 predictions_long.csv 的 test 行
    与 SPLIT-0002 test 真值按 beer×dim 连接后的指标"。
  * 本脚本不训练模型，不改旧实验，不读 full/assignment 用于训练；只读：
      experiments/EXP-0029/predictions_long.csv
      data/splits/SPLIT-0002/test.csv（仅 beer + 50 目标列）
  * 结果写 MODELING_EXPERIMENT_DIR，并由 modeling_contract 输出 metrics/outputs。

聚合口径（一次性全部登记，避免"挑一个数"）：
  recomputed_r2_50dim       逐维 R² 的算术平均（旧 r2_50dim 的同义口径）
  recomputed_r2_median      逐维 R² 中位数
  recomputed_r2_overall     仅 overall 维的 R²（旧 r2/r2_overall 口径）
  recomputed_mae_mean       逐维 MAE 的算术平均
  recomputed_rmse_mean      逐维 RMSE 的算术平均
  recomputed_pooled_r2      2500 个 (sample,dim) 值 pooled 的 R²
  recomputed_n_dims_r2_positive  逐维 R²>0 的维度数
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(os.environ.get("MODELING_PROJECT_DIR") or Path(__file__).resolve().parents[1])
PRED = PROJECT / "experiments" / "EXP-0029" / "predictions_long.csv"
TEST = PROJECT / "data" / "splits" / "SPLIT-0002" / "test.csv"

TARGET_DIMS = [
    "A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn",
    "A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody",
    "A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity",
    "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn",
    "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody",
    "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity",
    "acidity", "bitternes", "sweetness", "X4vg", "diacetyl", "dms", "metallic",
    "stale_hops", "t2n", "orange", "coriander", "clove", "lactic", "acetic",
    "barnyard", "alcohol", "aftertaste", "body", "co2", "overall",
]


def col_metrics(y, p):
    ss_res = float(np.sum((y - p) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rmse = float(np.sqrt(np.mean((y - p) ** 2)))
    mae = float(np.mean(np.abs(y - p)))
    return r2, rmse, mae


def main():
    old_dir = PROJECT / "experiments" / "EXP-0029"
    old = json.loads((old_dir / "metrics.json").read_text(encoding="utf-8"))
    pred = pd.read_csv(PRED)
    test = pd.read_csv(TEST, usecols=["beer"] + TARGET_DIMS)
    print(f"[recompute] pred={pred.shape} test={test.shape} split counts={pred['split'].value_counts().to_dict()}", flush=True)

    pte = pred[pred["split"] == "test"].copy()
    if set(pte["beer"]) != set(test["beer"]):
        raise SystemExit("beer ID sets differ between predictions and test.csv")
    truth = test.melt(id_vars=["beer"], value_vars=TARGET_DIMS, var_name="dim", value_name="y_true_test")
    j = pte.merge(truth, on=["beer", "dim"], how="inner", validate="one_to_one")
    if len(j) != 50 * 50:
        raise SystemExit(f"join produced {len(j)} rows, expected 2500")
    d = np.abs(j["y_true"].to_numpy(float) - j["y_true_test"].to_numpy(float))
    print(f"[recompute] join rows={len(j)} max|y_true - test.csv|={d.max():.3e}", flush=True)
    if d.max() > 1e-9:
        raise SystemExit("stored y_true does not match test.csv targets")

    rows, r2s, maes, rmses = [], [], [], []
    for dim in TARGET_DIMS:
        g = j[j["dim"] == dim]
        if len(g) != 50:
            raise SystemExit(f"dim {dim} has {len(g)} test rows, expected 50")
        r2, rmse, mae = col_metrics(g["y_true"].to_numpy(float), g["y_pred"].to_numpy(float))
        r2s.append(r2); rmses.append(rmse); maes.append(mae)
        rows.append({"dim": dim, "r2": r2, "rmse": rmse, "mae": mae,
                     "n": int(len(g)), "r2_positive": bool(r2 > 0)})
    yall = j["y_true"].to_numpy(float)
    pall = j["y_pred"].to_numpy(float)
    pooled_r2, pooled_rmse, pooled_mae = col_metrics(yall, pall)
    r2s = np.asarray(r2s); maes = np.asarray(maes); rmses = np.asarray(rmses)
    j_overall = TARGET_DIMS.index("overall")

    metrics = {
        "recomputed_r2_50dim": float(np.mean(r2s)),
        "recomputed_r2_median": float(np.median(r2s)),
        "recomputed_r2_overall": float(r2s[j_overall]),
        "recomputed_r2_min": float(np.min(r2s)),
        "recomputed_r2_max": float(np.max(r2s)),
        "recomputed_mae_mean": float(np.mean(maes)),
        "recomputed_rmse_mean": float(np.mean(rmses)),
        "recomputed_pooled_r2": float(pooled_r2),
        "recomputed_pooled_rmse": float(pooled_rmse),
        "recomputed_pooled_mae": float(pooled_mae),
        "recomputed_n_dims_r2_positive": int(np.sum(r2s > 0)),
        "n_test": int(len(test)),
        "n_dims": int(len(TARGET_DIMS)),
        "n_joined_rows": int(len(j)),
        "old_EXP0029_r2_50dim": float(old["r2_50dim"]),
        "old_EXP0029_r2_overall": float(old.get("holdout_r2__overall", old.get("r2_overall"))),
        "old_EXP0029_mae_mean": float(old["holdout_mae_mean"]),
        "delta_r2_50dim_vs_old": float(np.mean(r2s) - float(old["r2_50dim"])),
        "max_abs_ytrue_diff_vs_testcsv": float(d.max()),
    }
    print(json.dumps(metrics, indent=2), flush=True)

    try:
        import modeling_contract as mc  # type: ignore

        mc.emit_metrics(metrics)
        mc.emit_output("per_dim", rows)
        mc.emit_output("provenance", {
            "sourceExperiment": "EXP-0029",
            "sourceFile": "experiments/EXP-0029/predictions_long.csv",
            "truthFile": "data/splits/SPLIT-0002/test.csv",
            "joinKey": ["beer", "dim"],
            "joinRows": int(len(j)),
            "note": "post-hoc recomputation of stored test predictions; NOT an independent rerun because EXP-0029 has no frozen dependency set",
        })
        pd.DataFrame(rows).to_csv(Path(os.environ["MODELING_EXPERIMENT_DIR"]) / "per_dim_recompute.csv", index=False)
    except Exception as exc:
        print(f"[recompute] modeling_contract unavailable: {exc}", flush=True)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
