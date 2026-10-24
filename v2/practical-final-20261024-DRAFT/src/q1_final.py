"""Q1 最终锁定模型：一次性 holdout 评估 + 全部交付产物。

锁定模型（见 outputs/q1/locked_models.json）：
  B6_fusion = PLS + ExtraTrees + RandomForest + 逐维 HGB 的**简单平均**（等权，不打权重）。
  各分量超参在主分割训练 200 上由内层 3 折 CV 选定后**冻结**；分层复核复用同一组超参、
  只在分层训练 200 上重拟合（不重新选参），因此两栏差异只来自划分，不来自选型。

用法：
  python src/q1_final.py --split primary --emit        # 主分割 SPLIT-0002（正式 EXP）
  python src/q1_final.py --split stratified           # 分层复核（稳健性，不重复选参）

产物：
  outputs/q1/pred_z.csv            250×50（train 200 = OOF，test 50 = 锁定模型）
  outputs/q1/scores_0_6_P{1..4}.csv 四套标定口径的 0–6 分级（+ 一份 scores_0_6.csv = P1）
  outputs/q1/metrics_holdout.json  逐维 R²/MAE/ρ、r2_overall、分级敏感性、两栏对比
  outputs/q1/error_analysis.csv    逐维误差 + 按风格/按缺失行分层
  outputs/q1/model_bundle.pkl      Q1 锁定模型（Q3 前向映射用）
  outputs/q1/predictions_overall_holdout.csv  overall 维 holdout 预测（单列契约）
  outputs/q1/locked_models.json    冻结的超参与内层 CV 分数
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common as C  # noqa: E402
import q1_data as D  # noqa: E402
import q1_models as M  # noqa: E402

SEED = 42
LOCKED_JSON = ROOT / "outputs" / "q1" / "locked_models.json"


# ------------------------------------------------------------------ 工具
def test_beers_in_file_order(kind: str) -> np.ndarray:
    """test 文件原始行序（positional 契约要求 row 与该顺序一致）。"""
    p = os.environ.get("MODELING_TEST_FILE")
    if not (p and Path(p).exists()):
        p = (ROOT / "data" / "splits" / ("SPLIT-0002" if kind == "primary" else "stratified")
             / "test.csv")
    return pd.read_csv(p, usecols=["beer"])["beer"].to_numpy()


def select_and_freeze(X, Y, family_map):
    """在主分割训练 200 上用内层 3 折选定各分量超参，写 locked_models.json。"""
    specs = M.family_specs(family_map=family_map)
    locked = {}
    for cname, fam in specs["B6_fusion"]["components"].items():
        if fam["candidates"]:
            spec, pick, score = M.inner_select(fam["spec"], fam["candidates"], X, Y, family_map,
                                               n_splits=3, seed=7)
            locked[cname] = {"params": pick.get("params", {}), "inner_r2": round(float(score), 6),
                             "kind": fam["spec"]["kind"], "selection": "inner 3-fold CV on train 200"}
        else:
            locked[cname] = {"params": dict(fam["spec"]["params"]), "inner_r2": None,
                             "kind": fam["spec"]["kind"], "selection": "fixed a priori"}
        print(f"[lock] {cname}: {locked[cname]}", flush=True)
    out = {
        "family": "B6_fusion",
        "description": "PLS + ExtraTrees + RandomForest + HGB(逐维) 的等权简单平均",
        "selected_on": "SPLIT-0002 train 200, inner 3-fold CV, seed_inner=7",
        "prep": M.PREP_MAIN,
        "components": locked,
        "hgb_fixed": True,
        "n_folds_outer": 15,
        "outer_seed": SEED,
    }
    LOCKED_JSON.parent.mkdir(parents=True, exist_ok=True)
    LOCKED_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def frozen_component_specs(locked, family_map):
    """按冻结的超参构造 4 个分量的 spec（不再调用 inner_select）。"""
    specs = M.family_specs(family_map=family_map)["B6_fusion"]["components"]
    out = []
    for cname, fam in specs.items():
        s = dict(fam["spec"])
        s["params"] = dict(locked["components"][cname]["params"])
        out.append(s)
    return out


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="primary", choices=["primary", "stratified"])
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--skip-oof", action="store_true")
    a = ap.parse_args()
    D.ensure_dirs()

    data = D.load_all()
    X_all, Y_all, cats_all, family_map = data["X"], data["Y"], data["cats"], data["feature_family"]
    tr, te = D.load_split(a.split)
    X, Y, cats = X_all.loc[tr], Y_all.loc[tr], cats_all.loc[tr]
    Xte = X_all.loc[te]
    te_order = test_beers_in_file_order(a.split)
    gparams = D.load_grade_params(a.split)

    print(f"[final:{a.split}] train={len(tr)} test={len(te)} source={data.get('source')}", flush=True)
    t0 = time.time()

    # 1) 锁定超参（主分割选一次并冻结；分层复核复用）
    if a.split == "primary" or not LOCKED_JSON.exists():
        locked = select_and_freeze(X, Y, family_map)
    else:
        locked = json.loads(LOCKED_JSON.read_text(encoding="utf-8"))
        print(f"[final] reusing frozen hyperparams from {LOCKED_JSON.name}", flush=True)

    comp_specs = frozen_component_specs(locked, family_map)
    fusion_spec = {"kind": "fusion", "components": comp_specs, "feature_mode": "raw"}

    # 2) 训练 200 的 15 折 OOF（诚实报告用：每折内重新用内层 CV 选参，不用全 200 选出的冻结超参）
    oof_avg = None
    oof_metrics = None
    if a.skip_oof:
        # 允许复用同一确定性管线已产出的 OOF 工件（显式记录来源），避免重复 8 分钟计算
        # 复用同一确定性管线（同 folds/同 prep/同内层选参）已产出的 OOF 工件，避免重复约 8 分钟计算。
        # 候选来源优先级：本脚本上一次的 final 工件 > q1_models 的 B6_fusion 15 折工件。
        for cand in ["B6_fusion__final.npz", "B6_fusion__raw231.npz"]:
            npz = ROOT / "outputs" / "q1" / "oof" / cand
            if npz.exists():
                z = np.load(npz, allow_pickle=True)
                oof_avg = z["avg"]
                Yv = np.asarray(Y, float)
                oof_metrics = {"source": f"reused OOF artifact outputs/q1/oof/{cand}",
                               "oof_r2_mean": float(np.nanmean(C.r2(Yv, oof_avg))),
                               "oof_mae_mean": float(np.nanmean(C.mae(Yv, oof_avg))),
                               "oof_spearman_mean": float(np.nanmean(C.spearman_per_col(Yv, oof_avg))),
                               "r2_per_dim": C.r2(Yv, oof_avg).astype(float).tolist()}
                print(f"[final] OOF reused from {npz} (r2={oof_metrics['oof_r2_mean']:.4f})", flush=True)
                break
    if not a.skip_oof:
        fam_def = M.family_specs(family_map=family_map)["B6_fusion"]
        folds = D.cv_folds(cats, n_splits=5, n_repeats=3, seed=SEED)
        oof, chosen, secs = M.run_family("B6_fusion", fam_def, X, Y, cats, folds, family_map, verbose=False)
        oof_avg = np.nanmean(oof, axis=0)
        print(f"[final] OOF folds done in {secs:.0f}s", flush=True)
        s, per_rep, _ = M.summarize_oof(oof, np.asarray(Y))
        oof_metrics = {k: v for k, v in s.items() if not isinstance(v, np.ndarray)}
        oof_metrics["r2_per_dim"] = np.asarray(s["r2_per_dim"]).tolist()
        oof_metrics["r2_per_repeat"] = [float(x["r2_mean"]) for x in per_rep]
        np.savez_compressed(ROOT / "outputs" / "q1" / "oof" / "B6_fusion__final.npz",
                            oof=oof, avg=oof_avg, beer=tr)
        print(f"[final] OOF r2={s['oof_r2_mean']:.4f} (sd {s['oof_r2_sd_over_repeats']:.4f}) "
              f"in {time.time()-t0:.0f}s", flush=True)

    # 3) 在全部训练 200 上重拟合锁定模型 -> 预测 test（唯一一次留出评估）
    t1 = time.time()
    predictor = M.Predictor(fusion_spec, SEED, family_map).fit(X, np.asarray(Y))
    z_test = predictor.predict(Xte)
    print(f"[final] refit on 200 + predict test in {time.time()-t1:.0f}s", flush=True)

    Yte = Y_all.loc[te]
    m_test = D.z_metrics(Yte.values, z_test)
    holdout = {
        "split": a.split,
        "n_train": int(len(tr)), "n_test": int(len(te)),
        "r2": m_test["r2_mean"],
        "r2_repeat_averaged": None,
        "r2_overall": float(C.r2(Yte.values[:, [D.TARGET_DIMS.index("overall")]],
                                 z_test[:, [D.TARGET_DIMS.index("overall")]])[0]),
        "mae": m_test["mae_mean"],
        "spearman": m_test["spearman_mean"],
        "r2_median": m_test["r2_median"],
        "n_dims_r2_negative": m_test["n_dims_r2_negative"],
        "r2_per_dim": dict(zip(D.TARGET_DIMS, m_test["r2_per_dim"].tolist())),
        "mae_per_dim": dict(zip(D.TARGET_DIMS, m_test["mae_per_dim"].tolist())),
        "model": "B6_fusion (PLS+ET+RF+HGB equal-weight mean), refit on train 200",
        "calibration": {},
    }
    for pol in D.POLICIES:
        holdout["calibration"][pol] = D.calibration_report(Yte.values, z_test, policy=pol, params=gparams)
    print(f"[final] HOLDOUT r2={holdout['r2']:+.4f} r2_overall={holdout['r2_overall']:+.4f} "
          f"mae={holdout['mae']:.4f} rho={holdout['spearman']:.4f}", flush=True)

    # 4) 250×50 连续强度 + 四套分级的落盘
    pred_df_all = pd.DataFrame(np.nan, index=X_all.index, columns=D.TARGET_DIMS)
    is_oof_s = pd.Series(0, index=X_all.index, dtype=int)
    if oof_avg is not None:
        pred_df_all.loc[tr] = oof_avg
        is_oof_s.loc[tr] = 1
    pred_df_all.loc[te] = z_test
    pred = pred_df_all.to_numpy()
    is_oof = is_oof_s.to_numpy()
    suf = "" if a.split == "primary" else "_stratified"
    pred_df = pd.DataFrame(pred, columns=D.TARGET_DIMS)
    pred_df.insert(0, "beer", X_all.index.to_numpy())
    pred_df.insert(1, "is_oof", is_oof)
    if oof_avg is None:
        pred_df = pred_df[pred_df["is_oof"] == 0].reset_index(drop=True)
    C.write_csv(pred_df, f"outputs/q1/pred_z{suf}.csv")
    for pol, tag in zip(D.POLICIES, ["P1", "P2", "P3", "P4"]):
        G = D.grade_matrix(pred, pol, gparams)
        gdf = pd.DataFrame(G, columns=D.TARGET_DIMS)
        gdf.insert(0, "beer", X_all.index.to_numpy())
        gdf.insert(1, "is_oof", is_oof)
        if oof_avg is None:
            G = G[is_oof == 0]
            gdf = gdf[gdf["is_oof"] == 0].reset_index(drop=True)
        C.write_csv(gdf, f"outputs/q1/scores_0_6_{tag}{suf}.csv")
        if tag == "P1":
            C.write_csv(gdf, f"outputs/q1/scores_0_6{suf}.csv")
    # 分级不确定性：等级宽度（同一 ẑ 在四套口径下取到的等级跨度）
    Gs = np.stack([D.grade_matrix(pred, pol, gparams) for pol in D.POLICIES])
    width = (Gs.max(axis=0) - Gs.min(axis=0)).astype(int)
    wdf = pd.DataFrame(width, columns=D.TARGET_DIMS)
    wdf.insert(0, "beer", X_all.index.to_numpy())
    wdf.insert(1, "is_oof", is_oof)
    C.write_csv(wdf, f"outputs/q1/grade_width_across_policies{suf}.csv")

    # 5) 误差分析：逐维 + 按风格 + 按缺失行（用训练 OOF，test 太小不按风格切）
    err_rows = []
    ref = oof_avg if oof_avg is not None else z_test
    ref_y = Y_all.loc[tr] if oof_avg is not None else Yte
    tag = "oof_train" if oof_avg is not None else "holdout_test"
    from scipy.stats import spearmanr
    for j, d in enumerate(D.TARGET_DIMS):
        r2v = C.r2(ref_y.values[:, [j]], ref[:, [j]])[0]
        mav = C.mae(ref_y.values[:, [j]], ref[:, [j]])[0]
        rho = float(spearmanr(ref_y.values[:, j], ref[:, j]).statistic)
        err_rows.append({"level": "dim", "group": d, "n": int(len(ref_y)), "r2": float(r2v),
                         "mae": float(mav), "spearman": float(rho), "source": tag})
    # 按风格
    for sty, idx in cats.groupby(cats).groups.items():
        ii = np.array([list(tr).index(x) for x in idx])
        rr = float(np.nanmean(C.r2(ref_y.values[ii], ref[ii]))) if len(ii) > 1 else np.nan
        err_rows.append({"level": "style", "group": sty, "n": len(ii), "r2": rr,
                         "mae": float(np.nanmean(C.mae(ref_y.values[ii], ref[ii]))),
                         "spearman": float(np.nanmean(C.spearman_per_col(ref_y.values[ii], ref[ii]))),
                         "source": tag})
    # 按缺失行 / 完整行
    miss_rows = X.isna().any(axis=1).to_numpy()
    for name, mask in [("missing_any", miss_rows), ("complete", ~miss_rows)]:
        if mask.sum() > 1:
            err_rows.append({"level": "missing", "group": name, "n": int(mask.sum()),
                             "r2": float(np.nanmean(C.r2(ref_y.values[mask], ref[mask]))),
                             "mae": float(np.nanmean(C.mae(ref_y.values[mask], ref[mask]))),
                             "spearman": float(np.nanmean(C.spearman_per_col(ref_y.values[mask], ref[mask]))),
                             "source": tag})
    C.write_csv(pd.DataFrame(err_rows), f"outputs/q1/error_analysis{suf}.csv")

    # 6) 指标落盘
    full = {
        "split": a.split,
        "generated_by": "src/q1_final.py",
        "model": holdout["model"],
        "dataset": data.get("source"),
        "oof": oof_metrics,
        "holdout": holdout,
        "holdout_calibration_by_policy": holdout["calibration"],
        "grading_notes": ("真实 0–6 等级未知：4.csv 只是中心化+未知缩放的连续值。"
                          "因此 QWK / 分级 MAE 是**标定口径敏感性**，不是分级准确率。"
                          "P1 为物理锚定主口径；P2/P3/P4 为敏感性口径。"),
        "missing_handling": "折内中位数插补（+训练折缺失指示列），插补/截尾/标准化全部只在训练折拟合",
        "preprocessing": dict(M.PREP_MAIN),
        "locked_components": locked["components"],
        "locked_hyperparams_frozen_on": locked["selected_on"],
    }
    name = "metrics_holdout.json" if a.split == "primary" else "metrics_holdout_stratified.json"
    C.write_json(full, f"outputs/q1/{name}")

    # 7) overall 维 holdout 单列预测（VP-0004 / pack 契约），row 按 test 文件行序
    oi = D.TARGET_DIMS.index("overall")
    zmap = pd.Series(z_test[:, oi], index=te)
    tmap = Y_all.loc[te, "overall"]
    pred_overall = pd.DataFrame({
        "row": np.arange(len(te_order)),
        "beer": te_order,
        "y_true": [float(tmap.loc[b]) for b in te_order],
        "y_pred": [float(zmap.loc[b]) for b in te_order],
    })
    C.write_csv(pred_overall, f"outputs/q1/predictions_overall_holdout{suf}.csv")

    # 8) 模型 bundle（Q3 前向映射）
    bundle = {
        "predictor": predictor, "component_specs": comp_specs, "fusion": "equal-weight mean",
        "features": list(X_all.columns), "target_dims": list(D.TARGET_DIMS),
        "prep": dict(M.PREP_MAIN), "locked": locked,
        "grade_params": gparams, "policies": D.POLICIES, "policy_primary": D.POLICY_PRIMARY,
        "train_beers": tr.tolist(), "test_beers": te.tolist(),
        "oof_r2": None if oof_metrics is None else oof_metrics.get("oof_r2_mean"),
        "holdout_r2": holdout["r2"], "holdout_r2_overall": holdout["r2_overall"],
        "notes": "Q1 锁定模型：fit 全训练 200；predict(X_df 以 feature 名为列) -> (n,50) 连续 ẑ",
    }
    bundle["bundle_version"] = "q1-bundle-1.0"
    bundle["load_hint"] = ("load: import sys; sys.path.insert(0,'src'); import q1_data; "
                           "b=q1_data.load_bundle('outputs/q1/model_bundle.pkl'); "
                           "z=q1_data.bundle_predict(b, X_df)  # X_df: 以 231 特征名为列的 DataFrame")
    bpath = ROOT / "outputs" / "q1" / f"model_bundle{suf}.pkl"
    try:
        import joblib  # sklearn 依赖，压缩后 ~1/4 体积
        joblib.dump(bundle, bpath, compress=3)
    except Exception:
        with open(bpath, "wb") as f:
            pickle.dump(bundle, f)
    if a.split == "primary":
        C.write_json({"ok": True, "holdout_r2": holdout["r2"], "r2_overall": holdout["r2_overall"],
                      "oof_r2": None if oof_metrics is None else oof_metrics["oof_r2_mean"]},
                     "outputs/q1/final_summary.json")

    # 9) runner 契约（照 src/08_baseline_constant.py 的 EMP-0012 实测口径）
    if a.emit:
        import emit as E
        flat = {
            # 键名语义（Lead EXP-0015 实测口径）：
            #   r2 / mae        = predictions.csv 单列(overall) 的 R² / MAE，pack 会复算这一列
            #   r2_50dim        = 50 维逐维 R² 的算术平均 = 科学主指标
            #   holdout_r2_mean = 与 r2_50dim 同值（ROB-0001 的 metricKey）
            "r2": holdout["r2_overall"],
            "r2_overall": holdout["r2_overall"],
            "mae": float(np.mean(np.abs(Yte["overall"].values -
                                       z_test[:, D.TARGET_DIMS.index("overall")]))),
            "r2_50dim": holdout["r2"],
            "spearman": holdout["spearman"],
            "holdout_r2_mean": holdout["r2"],
            "holdout_r2_median": holdout["r2_median"],
            "holdout_mae_mean": holdout["mae"],
            "holdout_spearman_mean": holdout["spearman"],
            "holdout_mae_overall": float(np.mean(np.abs(Yte["overall"].values -
                                                      z_test[:, D.TARGET_DIMS.index("overall")]))),
            "n_train": float(len(tr)), "n_test": float(len(te)), "n_dims": float(D.N_DIMS),
        }
        for d, v in holdout["r2_per_dim"].items():
            flat[f"holdout_r2__{d}"] = float(v)
        if oof_metrics is not None:
            flat["oof_r2_mean"] = oof_metrics["oof_r2_mean"]
            flat["oof_mae_mean"] = oof_metrics["oof_mae_mean"]
            flat["oof_spearman_mean"] = oof_metrics["oof_spearman_mean"]
        for pol, tagp in zip(D.POLICIES, ["p1", "p2", "p3", "p4"]):
            flat[f"qwk_{tagp}"] = float(holdout["calibration"][pol]["qwk"])
            flat[f"grade_mae_{tagp}"] = float(holdout["calibration"][pol]["grade_mae"])
        # 单列 overall 合同（50 行，test.csv 行序）
        E.emit_metrics(flat, area="q1")
        E.emit_predictions(pred_overall[["row", "beer", "y_true", "y_pred"]], "predictions.csv", area="q1")
        # 50 维长表 12500 行（train OOF + test holdout）
        rows = []
        for i, b in enumerate(X_all.index):
            src_split = "test" if b in set(te) else "train"
            for j, d in enumerate(D.TARGET_DIMS):
                rows.append({"row": int(b), "beer": int(b), "dim": d,
                             "y_true": float(Y_all.loc[b, d]), "y_pred": float(pred[i, j]),
                             "split": src_split, "is_oof": bool(is_oof[i])})
        E.emit_predictions(pd.DataFrame(rows), "predictions_long.csv", area="q1")
        E.emit_output("per_dim_r2", {"holdout": holdout["r2_per_dim"],
                                     "oof": None if oof_metrics is None else
                                     dict(zip(D.TARGET_DIMS, oof_metrics["r2_per_dim"]))}, area="q1")
        E.emit_output("calibration_by_policy", holdout["calibration"], area="q1")
        E.emit_output("locked_components", locked["components"], area="q1")
        E.emit_output("grade_params", gparams, area="q1")
        E.emit_output("artifacts", {"pred_z": f"outputs/q1/pred_z{suf}.csv",
                                    "scores_P1": f"outputs/q1/scores_0_6_P1{suf}.csv",
                                    "model_bundle": f"outputs/q1/model_bundle{suf}.pkl",
                                    "metrics": f"outputs/q1/{name}"}, area="q1")
    print(f"[final:{a.split}] done in {time.time()-t0:.0f}s; outputs/q1/pred_z{suf}.csv etc.")


if __name__ == "__main__":
    main()
