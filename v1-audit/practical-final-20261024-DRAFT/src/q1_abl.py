"""Q1 消融 / 数值稳定性 / 种子敏感性：锁定融合模型（超参冻结）逐配置评估。

每个配置 = 一次真实运行：15 折 OOF（超参冻结，不再内层选参）+ 在 200 上重拟合后的一次 holdout。
单个配置可单独登记为 EXP（--config <name> --emit）。

配置清单（与 ROB-0001 预登记的扰动一一对应）：
  blocks : noagg（去掉 5 个聚合列）/ oav43（231+43 OAV）/ log10only（仅 37 个已验证 log10 列）
  prep   : winsor05（0.5/99.5）/ clip5 / clip12 / nowinsor_clip8 / knn / iterative
  seeds  : seed7 / seed2024 / seed123 / seed9（只改 15 折的折划分；最终重拟合不变）

指标键语义与 EXP-0015 一致：
  r2 / mae        = predictions.csv 单列(overall) 的 R² / MAE（pack 复算这一列）
  r2_50dim        = 50 维逐维 R² 算术平均（科学主指标）
  holdout_r2_mean = r2_50dim（ROB-0001 metricKey）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common as C  # noqa: E402
import emit as E  # noqa: E402
import q1_data as D  # noqa: E402
import q1_models as M  # noqa: E402

LOCKED_JSON = ROOT / "outputs" / "q1" / "locked_models.json"
SEED = 42


def configs():
    """返回 {name: dict(feature_block, prep_patch, fold_seed, desc)}。"""
    base = dict(feature_block="raw231", prep_patch={}, fold_seed=42,
                desc="主配置（参考点）")
    out = {"main": base}
    out["noagg"] = dict(feature_block="noagg", prep_patch={}, fold_seed=42,
                        desc="去掉 5 个化合物聚合列（kcalperc/acids_sum/esters_sum/aroma_hops_sum/sulfur_sum）")
    out["oav43"] = dict(feature_block="oav43", prep_patch={}, fold_seed=42,
                        desc="231 特征 + 43 个 OAV 特征（C.oav_table 的单调物理变换，log1p）")
    out["log10only"] = dict(feature_block="log10only", prep_patch={}, fold_seed=42,
                            desc="只用 37 个经 8.xlsx 标定验证的 log10 列")
    out["winsor05"] = dict(feature_block="raw231", prep_patch={"winsor_q": 0.005}, fold_seed=42,
                           desc="winsorize 1%/99% -> 0.5%/99.5%")
    out["clip5"] = dict(feature_block="raw231", prep_patch={"clip_z": 5.0}, fold_seed=42,
                        desc="标准化后裁剪 ±8 -> ±5")
    out["clip12"] = dict(feature_block="raw231", prep_patch={"clip_z": 12.0}, fold_seed=42,
                         desc="标准化后裁剪 ±8 -> ±12")
    out["nowinsor_clip8"] = dict(feature_block="raw231",
                                 prep_patch={"winsor_q": None, "clip_z": 8.0}, fold_seed=42,
                                 desc="去掉 winsorize，仅用标准化后 ±8 裁剪（Lead 的数值稳定防护）")
    out["knn"] = dict(feature_block="raw231", prep_patch={"impute": "knn"}, fold_seed=42,
                      desc="插补：折内中位数 -> KNN(k=5)")
    out["iterative"] = dict(feature_block="raw231", prep_patch={"impute": "iterative"}, fold_seed=42,
                            desc="插补：折内中位数 -> 迭代插补(IterativeImputer)")
    for s in (7, 2024, 123, 9):
        out[f"seed{s}"] = dict(feature_block="raw231", prep_patch={}, fold_seed=s,
                               desc=f"折划分种子 42 -> {s}")
    return out


def build_matrix(data, cfg):
    """按配置构造 (X, feature_names, extra_output)。"""
    X_all = data["X"]
    block = cfg["feature_block"]
    if block == "raw231":
        return X_all, list(X_all.columns), None
    cols, extra = D.feature_block(block)
    X = X_all[cols].copy()
    if extra is not None:
        ex = extra.reindex(X.index)
        ex = np.log1p(np.clip(ex, 0, None))  # OAV 重尾；log1p 为逐元素无参数变换
        ex.columns = ["oav__" + c.replace("oav_", "") for c in ex.columns]
        X = pd.concat([X, ex], axis=1)
        return X, list(X.columns), ex.columns.tolist()
    return X, list(X.columns), None


def frozen_specs(locked, family_map):
    """按 locked_models.json 的冻结超参构造 4 个分量的 spec（不再内层选参）。"""
    specs = M.family_specs(family_map=family_map)["B6_fusion"]["components"]
    out = []
    for cname, fam in specs.items():
        s = dict(fam["spec"])
        s["params"] = dict(locked["components"][cname]["params"])
        out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="配置名或逗号分隔列表（dev 用）")
    ap.add_argument("--split", default="primary", choices=["primary", "stratified"])
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--skip-holdout", action="store_true")
    a = ap.parse_args()
    D.ensure_dirs()

    locked = json.loads(LOCKED_JSON.read_text(encoding="utf-8"))
    data = D.load_all()
    X_all, Y_all, cats_all, family_map = data["X"], data["Y"], data["cats"], data["feature_family"]
    tr, te = D.load_split(a.split)
    gparams = D.load_grade_params(a.split)
    comp_specs = frozen_specs(locked, family_map)
    specs = configs()
    names = [n.strip() for n in a.config.split(",")]
    rows = []
    for name in names:
        if name not in specs:
            raise SystemExit(f"unknown config {name}; known: {list(specs)}")
        cfg = specs[name]
        t0 = time.time()
        X, fnames, added = build_matrix(data, cfg)
        Xtr, Xte = X.loc[tr], X.loc[te]
        Y = Y_all.loc[tr]
        prep = dict(M.PREP_MAIN)
        prep.update(cfg["prep_patch"])
        cs = [dict(s, prep=prep) for s in comp_specs]
        fusion = {"kind": "fusion", "components": cs, "feature_mode": "raw"}
        # 15 折 OOF（超参冻结）
        folds = D.cv_folds(cats_all.loc[tr], 5, 3, cfg["fold_seed"])
        oof = np.full((3, len(tr), D.N_DIMS), np.nan)
        for rep, fold, ia, ib in folds:
            p = M.Predictor(fusion, SEED, family_map).fit(Xtr.iloc[ia], np.asarray(Y.iloc[ia]))
            oof[rep, ib] = p.predict(Xtr.iloc[ib])
        oof_avg = np.nanmean(oof, axis=0)
        so = D.z_metrics(Y.values, oof_avg)
        # holdout：在训练 200 上重拟合后预测 test（每次运行一次）
        if a.skip_holdout:
            sh, z_test = None, None
        else:
            pred = M.Predictor(fusion, SEED, family_map).fit(Xtr, np.asarray(Y))
            z_test = pred.predict(Xte)
            sh = D.z_metrics(Y_all.loc[te].values, z_test)
        oi = D.TARGET_DIMS.index("overall")
        r2_overall = None if sh is None else float(C.r2(Y_all.loc[te, ["overall"]].values,
                                                        z_test[:, [oi]])[0])
        row = {"config": name, "desc": cfg["desc"], "n_features": len(fnames),
               "feature_block": cfg["feature_block"], "prep": json.dumps(prep),
               "fold_seed": cfg["fold_seed"],
               "oof_r2_50dim": so["r2_mean"], "oof_mae": so["mae_mean"], "oof_spearman": so["spearman_mean"],
               "holdout_r2_50dim": None if sh is None else sh["r2_mean"],
               "holdout_mae": None if sh is None else sh["mae_mean"],
               "holdout_spearman": None if sh is None else sh["spearman_mean"],
               "holdout_r2_overall": r2_overall,
               "qwk_p1_holdout": None if sh is None else D.calibration_report(
                   Y_all.loc[te].values, z_test, "P1_oav_anchor", gparams)["qwk"],
               "seconds": round(time.time() - t0, 1)}
        rows.append(row)
        print(f"[abl] {name:16s} feats={len(fnames):3d} oof_r2={row['oof_r2_50dim']:+.4f} "
              f"holdout_r2={0 if row['holdout_r2_50dim'] is None else row['holdout_r2_50dim']:+.4f} "
              f"({row['seconds']}s)", flush=True)

        if a.emit:
            pred_overall = pd.DataFrame({
                "row": np.arange(len(te)),
                "beer": [int(b) for b in te],
                "y_true": Y_all.loc[te, "overall"].values,
                "y_pred": z_test[:, oi],
            })
            flat = {
                "r2": float(r2_overall), "r2_overall": float(r2_overall),
                "mae": float(np.mean(np.abs(Y_all.loc[te, "overall"].values - z_test[:, oi]))),
                "r2_50dim": float(sh["r2_mean"]), "holdout_r2_mean": float(sh["r2_mean"]),
                "holdout_mae_mean": float(sh["mae_mean"]),
                "holdout_spearman_mean": float(sh["spearman_mean"]),
                # ROB-0001 的 metricKey（Lead 已改为训练内 OOF 口径）
                "oof_r2_50dim": float(so["r2_mean"]),
                "oof_r2_mean": float(so["r2_mean"]),
                "oof_mae_mean": float(so["mae_mean"]),
                "oof_spearman_mean": float(so["spearman_mean"]),
                "n_features": float(len(fnames)), "n_train": float(len(tr)), "n_test": float(len(te)),
                "n_dims": float(D.N_DIMS),
            }
            for d, v in zip(D.TARGET_DIMS, sh["r2_per_dim"]):
                flat[f"holdout_r2__{d}"] = float(v)
            for pol, tag in zip(D.POLICIES, ["p1", "p2", "p3", "p4"]):
                rep = D.calibration_report(Y_all.loc[te].values, z_test, pol, gparams)
                flat[f"qwk_{tag}"] = float(rep["qwk"])
            E.emit_metrics(flat, area="q1")
            E.emit_predictions(pred_overall, "predictions.csv", area="q1")
            rows_long = []
            for i, b in enumerate(X_all.index):
                src = "test" if b in set(te) else "train"
                yp = z_test[list(te).index(b)] if src == "test" else oof_avg[list(tr).index(b)]
                for j, d in enumerate(D.TARGET_DIMS):
                    rows_long.append({"row": int(b), "beer": int(b), "dim": d,
                                      "y_true": float(Y_all.loc[b, d]), "y_pred": float(yp[j]),
                                      "split": src, "is_oof": bool(src == "train")})
            E.emit_predictions(pd.DataFrame(rows_long), "predictions_long.csv", area="q1")
            E.emit_output("config", {"name": name, "desc": cfg["desc"],
                                     "feature_block": cfg["feature_block"],
                                     "features_added": added,
                                     "prep": prep, "fold_seed": cfg["fold_seed"]}, area="q1")
            E.emit_output("features_declared", fnames, area="q1")
        cur = pd.DataFrame(rows)
        cur[cur["config"] == name].to_csv(ROOT / "outputs" / "q1" / f"ablation_{name}.csv", index=False)

    if len(rows) > 1:
        C.write_csv(pd.DataFrame(rows), "outputs/q1/ablation_sweep.csv")
        cols = ["config", "n_features", "oof_r2_50dim", "holdout_r2_50dim", "oof_spearman"]
        print(pd.DataFrame(rows)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
