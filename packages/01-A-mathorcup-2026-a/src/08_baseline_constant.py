"""B0 常数基线：每个目标维度取**训练集均值**，空特征。

用途（协议层，不是科学候选）：
  1. 验证 `modeling_experiment` 管线端到端可跑通（登记 → 运行 → 产物 → 指标）；
  2. 给出"什么都不学"的下界，供 Q1 后续候选做 `baseline-compare` 检查。

契约（与 reviewer 的 experiment_contract 对齐，若其最终版不同以它为准）：
  * `predictions.csv`（长表）：row, beer, dim, y_true, y_pred, is_oof, split
  * `metrics.json`：逐维 R²/MAE/Spearman + 50 维均值；训练 OOF 与 holdout 分开
  * 训练集用 5 折 OOF（常数基线在每折内仍是该折训练均值）
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import emit as E  # noqa: E402

from sklearn.model_selection import StratifiedKFold


def load_split():
    p = Path(C.SPLITS) / "SPLIT-0002" / "assignment.csv"
    if p.exists():
        a = pd.read_csv(p)
        order = pd.read_csv(C.RAW / "1.csv")["beer"].tolist()
        a["beer"] = [order[i] for i in a["row_index"].astype(int)]
        return a[["beer", "split"]], "SPLIT-0002"
    p2 = Path(C.SPLITS) / "assignment.csv"
    a = pd.read_csv(p2)[["beer", "split"]]
    return a, "stratified"


def main():
    mt = pd.read_csv(C.ROOT / "data/clean/model_table.csv", dtype={"beer_id": "int64"})
    sp, sp_name = load_split()
    df = mt.merge(sp, on="beer", how="left")
    assert df["split"].notna().all()
    tr = df[df["split"] == "train"].reset_index(drop=True)
    te = df[df["split"] == "test"].reset_index(drop=True)
    dims = C.TARGET_DIMS
    print(f"[B0] split={sp_name} train={len(tr)} test={len(te)} dims={len(dims)}")

    # ---- 训练集 5 折 OOF（常数基线 = 折内训练均值）
    oof = np.zeros((len(tr), len(dims)))
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for k, (ia, ib) in enumerate(skf.split(tr, tr["tasting_category_fine"])):
        mu = tr.iloc[ia][dims].mean()
        oof[ib, :] = mu.values[None, :]

    # ---- holdout：用全部训练均值
    mu_all = tr[dims].mean()
    pred_te = np.tile(mu_all.values[None, :], (len(te), 1))

    rows = []
    for i, r in tr.iterrows():
        for j, d in enumerate(dims):
            rows.append({"row": int(r["beer"]), "beer": int(r["beer"]), "dim": d,
                         "y_true": float(r[d]), "y_pred": float(oof[i, j]),
                         "split": "train", "is_oof": True})
    for i, r in te.iterrows():
        for j, d in enumerate(dims):
            rows.append({"row": int(r["beer"]), "beer": int(r["beer"]), "dim": d,
                         "y_true": float(r[d]), "y_pred": float(pred_te[i, j]),
                         "split": "test", "is_oof": False})
    pred = pd.DataFrame(rows)
    C.write_csv(pred, "outputs/q1/B0_constant_predictions.csv")

    def block(y, p, tag):
        r2v = C.r2(y, p)
        return {
            f"{tag}_r2_mean": float(np.nanmean(r2v)),
            f"{tag}_r2_median": float(np.nanmedian(r2v)),
            f"{tag}_mae_mean": float(np.nanmean(C.mae(y, p))),
            f"{tag}_spearman_mean": float(np.nanmean(C.spearman_per_col(y, p))),
            f"{tag}_per_dim_r2": {d: float(v) for d, v in zip(dims, r2v)},
        }

    m = {
        "experiment": "B0 constant train-mean baseline (empty features)",
        "split": sp_name,
        "n_train": int(len(tr)), "n_test": int(len(te)), "n_dims": len(dims),
        "targets": dims,
        "feature_mode": "none (constant per-dimension train mean)",
        **block(tr[dims].values, oof, "oof"),
        **block(te[dims].values, pred_te, "holdout"),
        "note": ("常数基线的 R² 均值在理论上 ≈ 0（OOF 下略为负）；"
                 "它只作下界与管线验证，不是候选模型。"),
    }
    C.write_json(m, "outputs/q1/B0_constant_metrics.json")

    # ---- 通过 emit 桥接层输出（runner 只接受有限数值）
    flat = {
        "oof_r2_mean": m["oof_r2_mean"], "oof_r2_median": m["oof_r2_median"],
        "oof_mae_mean": m["oof_mae_mean"],
        "holdout_r2_mean": m["holdout_r2_mean"], "holdout_r2_median": m["holdout_r2_median"],
        "holdout_mae_mean": m["holdout_mae_mean"],
        "n_train": m["n_train"], "n_test": m["n_test"], "n_dims": m["n_dims"],
    }
    for d, v in m["holdout_per_dim_r2"].items():
        flat[f"holdout_r2__{d}"] = v
    j_overall = dims.index("overall")
    pred_overall = pd.DataFrame({
        "row": list(range(len(te))),
        "beer": [int(b) for b in te["beer"].values],
        "y_true": te["overall"].values,
        "y_pred": pred_te[:, j_overall],
    })
    flat["holdout_r2_overall"] = float(C.r2(te[["overall"]].values,
                                            pred_te[:, [j_overall]])[0])
    # pack 合同（reviewer 实测）：
    #   * independent-rerun 读**裸键 r2**；
    #   * holdout-metrics 只复算**单列**，且在 whitelist 内（rmse/mae/mse/r2/...），
    #     因此 predictions.csv 是 overall 单列时，r2 必须**等于该列的 R²**，否则 pack 复算对不上。
    #   * 50 维科学主指标改名为 r2_50dim / holdout_r2_mean，由 reviewer 从 predictions_long.csv 独立重算。
    flat["r2"] = flat["holdout_r2_overall"]      # 与 predictions.csv(overall 单列) 自洽
    flat["r2_50dim"] = flat["holdout_r2_mean"]   # 科学主指标（pack 不复算）
    flat["mae"] = float(C.mae(te[["overall"]].values, pred_te[:, [j_overall]])[0])
    flat["holdout_mae_overall"] = float(C.mae(te[["overall"]].values,
                                              pred_te[:, [j_overall]])[0])
    E.emit_metrics(flat, area="q1")
    # 命名合同（reviewer 实测）：predictions.csv = 单列 overall 合同（与 test.csv 逐行对齐）；
    # 长表 50 维必须叫 predictions_long.csv，否则 holdout-metrics 会按 50 行去对齐 12500 长表而 refuse
    E.emit_predictions(pred_overall, "predictions.csv", area="q1")
    E.emit_predictions(pred, "predictions_long.csv", area="q1")
    E.emit_output("constant_values", {d: float(mu_all[d]) for d in dims}, area="q1")
    print("[B0] emitted; in_runner=", E.IN_RUNNER)
    print(json.dumps({k: round(float(flat[k]), 6) for k in
                      ["oof_r2_mean", "holdout_r2_mean", "holdout_mae_mean",
                       "holdout_r2_overall"]}, indent=2))
    print("[B0] predictions ->", "outputs/q1/B0_constant_predictions.csv",
          pred.shape)


if __name__ == "__main__":
    main()
