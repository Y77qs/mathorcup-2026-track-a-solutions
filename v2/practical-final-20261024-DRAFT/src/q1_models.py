"""Q1 候选模型比较：重复分层 5 折 × 3 次（15 折）训练内 OOF。

纪律（与 Lead 冻结协议、reviewer 的 VP-0001 对齐）：
  * 只在 200 个训练样本内做模型选择；test 50 个样本在本脚本中**完全不被读取**；
  * 每个 family 独立运行、独立登记（--families 只跑一个 family 时用于正式 EXP）；
  * 插补/截尾/标准化/特征变换一律在训练折内 fit（见 q1_data.Prep）；
  * 超参数只在内层 K 折上选；固定先验超参的 family 在输出里注明 "fixed"。

用法：
  python src/q1_models.py --families all                 # 开发：全家族比较
  python src/q1_models.py --families B1_ridge --emit      # 正式实验：单 family + 契约产物
  python src/q1_models.py --prep-sweep                    # 预处理对照（协议字面版 vs 尺度协调+截尾）
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common as C  # noqa: E402
import q1_data as D  # noqa: E402

SEED = 42
PREP_PROTOCOL = dict(harmonize="none", winsor_q=None, indicator=True)   # 协议 B1 字面版
PREP_MAIN = dict(harmonize="log10_linear", winsor_q=0.01, indicator=True)  # 经预处理对照选出


# ------------------------------------------------------------------ 模型装配
class ConstModel:
    """B0：每维训练均值（空特征）。"""

    def fit(self, X, Y):
        self.mu_ = np.asarray(Y, float).mean(axis=0)
        return self

    def predict(self, X):
        return np.tile(self.mu_, (len(X), 1))


def _make_estimator(kind: str, p: dict, seed: int):
    from sklearn.linear_model import Ridge
    from sklearn.decomposition import PCA
    from sklearn.cross_decomposition import PLSRegression
    from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
    from sklearn.multioutput import MultiOutputRegressor

    if kind == "const":
        return ConstModel()
    if kind == "ridge":
        return Ridge(alpha=p["alpha"])
    if kind == "pca_ridge":
        return _PCARidge(p["k"], p["alpha"])
    if kind == "pls":
        return PLSRegression(n_components=p["n_components"], scale=False)
    if kind == "et":
        return ExtraTreesRegressor(n_estimators=p.get("n_estimators", 400),
                                   max_features=p["max_features"],
                                   min_samples_leaf=p["min_samples_leaf"],
                                   random_state=seed, n_jobs=-1)
    if kind == "rf":
        return RandomForestRegressor(n_estimators=p.get("n_estimators", 400),
                                     max_features=p["max_features"],
                                     min_samples_leaf=p["min_samples_leaf"],
                                     random_state=seed, n_jobs=-1)
    if kind == "hgb":
        return MultiOutputRegressor(HistGradientBoostingRegressor(
            max_iter=p.get("max_iter", 150), learning_rate=p.get("learning_rate", 0.06),
            max_leaf_nodes=p.get("max_leaf_nodes", 8), min_samples_leaf=p.get("min_samples_leaf", 10),
            l2_regularization=p.get("l2_regularization", 1.0), early_stopping=False,
            random_state=seed), n_jobs=-1)
    raise ValueError(kind)


class _PCARidge:
    def __init__(self, k, alpha):
        self.k, self.alpha = k, alpha

    def fit(self, X, Y):
        from sklearn.linear_model import Ridge
        from sklearn.decomposition import PCA
        self.pca_ = PCA(n_components=self.k, random_state=0).fit(X)
        self.reg_ = Ridge(alpha=self.alpha).fit(self.pca_.transform(X), Y)
        return self

    def predict(self, X):
        return self.reg_.predict(self.pca_.transform(X))


class Predictor:
    """折内预处理 + (可选)化学族聚合 + 估计器。fit 只用训练折。"""

    def __init__(self, spec: dict, seed: int = SEED, family_map: dict = None):
        self.spec = spec
        self.seed = seed
        self.family_map = family_map

    def _design(self, X, fit=False):
        if self.spec.get("feature_mode") == "group":
            # 化学族聚合：先标准化再按 origin_paper 组聚合
            Z = self.prep_.transform(X)
            cols = self.prep_.columns_
            if fit:
                self.ga_ = D.GroupAgg(self.family_map)
            G = self.ga_.transform(Z, cols)
            # 追加 5 个化合物聚合列的标准化值（它们在 1.csv 内，是化合物函数，单独成块）
            agg_cols = [c for c in D.AGG_FEATURES if c in cols]
            Gagg = Z[:, [cols.index(c) for c in agg_cols]]
            return np.hstack([G, Gagg])
        Z = self.prep_.transform(X)
        return Z

    def fit(self, X, Y):
        comps = self.spec.get("components")
        if comps:
            self.models_ = [Predictor(cs, self.seed, self.family_map).fit(X, Y) for cs in comps]
            return self
        self.models_ = None
        self.prep_ = D.Prep(**self.spec["prep"]).fit(X)
        Z = self._design(X, fit=True)
        self.model_ = _make_estimator(self.spec["kind"], self.spec["params"], self.seed).fit(Z, np.asarray(Y, float))
        return self

    def predict(self, X):
        if getattr(self, "models_", None):
            return np.mean([m.predict(X) for m in self.models_], axis=0)
        return np.asarray(self.model_.predict(self._design(X)), dtype=float)


# ------------------------------------------------------------------ 家族定义
def family_specs(prep: dict = None, family_map: dict = None):
    """返回 {family: {spec, candidates, note}}；candidates=None 表示超参固定先验。"""
    prep = dict(prep or PREP_MAIN)
    alphas = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0]
    fam = {
        "B0_const": dict(
            spec=dict(kind="const", params={}, prep=prep, feature_mode="none"),
            candidates=None, note="每维训练均值，空特征（常数基线）"),
        "B1_ridge": dict(
            spec=dict(kind="ridge", params={"alpha": 30.0}, prep=prep, feature_mode="raw"),
            candidates=[{"params": {"alpha": a}} for a in alphas],
            note="岭回归多输出；alpha 内层 3 折选"),
        "B2_pca_ridge": dict(
            spec=dict(kind="pca_ridge", params={"k": 20, "alpha": 10.0}, prep=prep, feature_mode="raw"),
            candidates=[{"params": {"k": k, "alpha": a}} for k in (5, 10, 20, 30) for a in (1.0, 10.0, 100.0)],
            note="PCA(k)+岭；k/alpha 内层 3 折选"),
        "B2b_pls": dict(
            spec=dict(kind="pls", params={"n_components": 5}, prep=prep, feature_mode="raw"),
            candidates=[{"params": {"n_components": k}} for k in (2, 3, 5, 8, 12, 20)],
            note="PLS 多输出；成分数内层 3 折选"),
        "B3_extratrees": dict(
            spec=dict(kind="et", params={"max_features": 0.1, "min_samples_leaf": 1}, prep=prep, feature_mode="raw"),
            candidates=[{"params": {"max_features": mf, "min_samples_leaf": leaf}}
                        for mf in (0.05, 0.1, 0.3) for leaf in (1, 3)],
            note="ExtraTrees 多输出；max_features/leaf 内层 3 折选；seed=42"),
        "B3b_randomforest": dict(
            spec=dict(kind="rf", params={"max_features": 0.1, "min_samples_leaf": 1}, prep=prep, feature_mode="raw"),
            candidates=[{"params": {"max_features": mf, "min_samples_leaf": leaf}}
                        for mf in (0.05, 0.1, 0.3) for leaf in (1, 3)],
            note="RandomForest 多输出；同上；seed=42"),
        "B4_hgb": dict(
            spec=dict(kind="hgb", params={"max_iter": 150, "learning_rate": 0.06, "max_leaf_nodes": 8,
                                          "min_samples_leaf": 10, "l2_regularization": 1.0},
                      prep=prep, feature_mode="raw"),
            candidates=None, note="逐维 HistGradientBoosting(MultiOutputRegressor)；超参固定先验（未在 OOF 上调）"),
        "B5_chemgroup_ridge": dict(
            spec=dict(kind="ridge", params={"alpha": 30.0}, prep=prep, feature_mode="group"),
            candidates=[{"params": {"alpha": a}} for a in alphas],
            note="化学族（origin_paper 7 组）聚合 mean/max/检出率 + 5 聚合列 + 岭；alpha 内层 3 折选"),
    }
    fam["B6_fusion"] = dict(
        components={"pls": fam["B2b_pls"], "et": fam["B3_extratrees"],
                    "rf": fam["B3b_randomforest"], "hgb": fam["B4_hgb"]},
        spec=None, candidates=None,
        note="四路简单平均融合（PLS+ET+RF+HGB）；各分量在折内各自用内层 3 折选参，"
             "只用训练折数据；选定依据 = 41 种 2/3/4 路平均中 OOF R² 最优，且 15/15 折一致优于单模 ET")
    if family_map:
        for v in fam.values():
            v["family_map"] = family_map
            if v.get("components"):
                for c in v["components"].values():
                    c["family_map"] = family_map
    return fam


# ------------------------------------------------------------------ 内层选参与 CV
def _score(cand_spec, Xa, Ya, n_splits, seed, family_map):
    from sklearn.model_selection import KFold
    kf = KFold(n_splits=min(n_splits, len(Xa)), shuffle=True, random_state=seed)
    pred = np.zeros(np.asarray(Ya).shape, float)
    for a, b in kf.split(Xa):
        m = Predictor(cand_spec, seed, family_map).fit(Xa.iloc[a], np.asarray(Ya)[a])
        pred[b] = m.predict(Xa.iloc[b])
    r2v = C.r2(np.asarray(Ya, float), pred)
    return float(np.nanmean(r2v)), pred


def inner_select(spec, candidates, Xa, Ya, family_map, n_splits=3, seed=0):
    """内层 K 折选超参：以逐维 R² 均值（nan 安全）为准则。"""
    best, best_s, best_p = None, -np.inf, None
    for cand in candidates:
        s = copy.deepcopy(spec)
        s.update(copy.deepcopy(cand))
        sc, _ = _score(s, Xa, Ya, n_splits, seed, family_map)
        if sc > best_s:
            best_s, best, best_p = sc, s, cand
    return best, best_p, best_s


def run_family(name, fam_def, X, Y, cats, folds, family_map, verbose=True):
    n, m = len(X), D.N_DIMS
    n_repeats = max(f[0] for f in folds) + 1
    oof = np.full((n_repeats, n, m), np.nan)
    chosen = []
    t0 = time.time()
    for rep, fold, a, b in folds:
        Xa, Xb, Ya = X.iloc[a], X.iloc[b], Y.iloc[a]
        spec = fam_def["spec"]
        pick = None
        if fam_def.get("components"):
            comp_specs = []
            for cname, cfam in fam_def["components"].items():
                if cfam["candidates"]:
                    cs, cpick, isc = inner_select(cfam["spec"], cfam["candidates"], Xa, Ya, family_map,
                                                  n_splits=3, seed=1000 + rep * 10 + fold)
                    chosen.append({"repeat": rep, "fold": fold, "component": cname,
                                   **cpick.get("params", {}), "inner_r2": round(isc, 4)})
                else:  # 固定先验超参的分量（HGB）
                    cs, cpick, isc = cfam["spec"], {"params": {}}, float("nan")
                    chosen.append({"repeat": rep, "fold": fold, "component": cname,
                                   "inner_r2": None, "hyper": "fixed"})
                comp_specs.append(cs)
            spec = {"kind": "fusion", "components": comp_specs, "feature_mode": "raw"}
        elif fam_def["candidates"]:
            spec, pick, isc = inner_select(spec, fam_def["candidates"], Xa, Ya, family_map,
                                           n_splits=3, seed=1000 + rep * 10 + fold)
            chosen.append({"repeat": rep, "fold": fold, **pick.get("params", {}), "inner_r2": round(isc, 4)})
        pred = Predictor(spec, SEED, family_map).fit(Xa, np.asarray(Ya)).predict(Xb)
        oof[rep, b] = pred
        if verbose:
            print(f"  [{name}] rep{rep} fold{fold} done in {time.time()-t0:.1f}s", flush=True)
    return oof, chosen, time.time() - t0


def summarize_oof(oof, Y):
    """逐 repeat 指标 + repeat 平均 OOF 指标 + 三档 S 的分级指标。"""
    Yv = np.asarray(Y, float)
    per_rep = [D.z_metrics(Yv, oof[r]) for r in range(oof.shape[0])]
    avg = np.nanmean(oof, axis=0)
    m_avg = D.z_metrics(Yv, avg)
    out = {
        "oof_r2_mean": float(np.mean([p["r2_mean"] for p in per_rep])),
        "oof_r2_sd_over_repeats": float(np.std([p["r2_mean"] for p in per_rep], ddof=1)) if len(per_rep) > 1 else 0.0,
        "oof_r2_mean_repeat_averaged": m_avg["r2_mean"],
        "oof_mae_mean": float(np.mean([p["mae_mean"] for p in per_rep])),
        "oof_spearman_mean": float(np.mean([p["spearman_mean"] for p in per_rep])),
        "oof_r2_median": m_avg["r2_median"],
        "oof_n_dims_r2_negative": m_avg["n_dims_r2_negative"],
        "r2_per_dim": m_avg["r2_per_dim"],
        "mae_per_dim": m_avg["mae_per_dim"],
    }
    for pol in D.POLICIES:
        out[f"calib_{pol}"] = D.calibration_report(Yv, avg, policy=pol)
    return out, per_rep, avg


# ------------------------------------------------------------------ 输出契约
def emit_contract(metrics: dict, pred_df: pd.DataFrame, outputs: dict = None, pred_name="predictions.csv"):
    """统一经由 src/emit.py 桥接层输出（runner 内落台账，runner 外写 outputs/q1/）。"""
    try:
        import emit as E
    except Exception:
        return "no-emit-bridge"
    E.emit_metrics(metrics, area="q1")
    if pred_df is not None:
        E.emit_predictions(pred_df, pred_name, area="q1")
    for k, v in (outputs or {}).items():
        E.emit_output(k, v, area="q1")
    return "emitted"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", default="all")
    ap.add_argument("--block", default="raw231", choices=["raw231", "noagg", "log10only", "oav43"])
    ap.add_argument("--prep-sweep", action="store_true")
    ap.add_argument("--prep", default="main", choices=["main", "protocol"])
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n-repeats", type=int, default=3)
    ap.add_argument("--out", default="outputs/q1/model_comparison.csv")
    ap.add_argument("--emit", action="store_true", help="写 runner 契约产物（metrics.json/predictions.csv）")
    ap.add_argument("--note", default="")
    ap.add_argument("--split", default="primary", choices=["primary", "stratified"])
    a = ap.parse_args()

    D.ensure_dirs()
    data = D.load_all()
    X_all, Y_all, cats_all, family_map = data["X"], data["Y"], data["cats"], data["feature_family"]
    tr, te = D.load_split(a.split)
    X, Y, cats = X_all.loc[tr], Y_all.loc[tr], cats_all.loc[tr]
    prep = PREP_MAIN if a.prep == "main" else PREP_PROTOCOL
    folds = D.cv_folds(cats, n_splits=5, n_repeats=a.n_repeats, seed=a.seed)

    print(f"[Q1] train n={len(tr)} dims={D.N_DIMS} folds={len(folds)} block={a.block} "
          f"prep={prep} seed={a.seed}", flush=True)

    if a.prep_sweep:
        rows = []
        variants = {
            "P1_med+std(协议字面)": dict(harmonize="none", winsor_q=None, indicator=True),
            "P2_med+winsor1+std": dict(harmonize="none", winsor_q=0.01, indicator=True),
            "P3_log10lin+std": dict(harmonize="log10_linear", winsor_q=None, indicator=True),
            "P4_log10lin+winsor1+std": dict(harmonize="log10_linear", winsor_q=0.01, indicator=True),
            "P5_log10lin+winsor1+std,noind": dict(harmonize="log10_linear", winsor_q=0.01, indicator=False),
            "P6_log10lin+winsor5+std": dict(harmonize="log10_linear", winsor_q=0.05, indicator=True),
            "P8_log10lin+std+clip8(无winsor)": dict(harmonize="log10_linear", winsor_q=None, indicator=True, clip_z=8.0),
            "P9_log10lin+winsor1+std+clip8": dict(harmonize="log10_linear", winsor_q=0.01, indicator=True, clip_z=8.0),
        }
        for name, pv in variants.items():
            fs = family_specs(pv, family_map)["B1_ridge"]
            oof, chosen, secs = run_family("B1_ridge", fs, X, Y, cats, folds, family_map, verbose=False)
            s, _, _ = summarize_oof(oof, np.asarray(Y))
            rows.append({"variant": name, "prep": json.dumps(pv), "oof_r2_mean": s["oof_r2_mean"],
                         "oof_r2_sd": s["oof_r2_sd_over_repeats"], "oof_mae_mean": s["oof_mae_mean"],
                         "oof_spearman_mean": s["oof_spearman_mean"],
                         "qwk_P1": s["calib_P1_oav_anchor"]["qwk"], "n_dims_r2_negative": s["oof_n_dims_r2_negative"],
                         "median_alpha": float(np.median([c.get("alpha", np.nan) for c in chosen])),
                         "seconds": round(secs, 1)})
            print(f"  {name:34s} r2={s['oof_r2_mean']:+.4f} ±{s['oof_r2_sd_over_repeats']:.4f} "
                  f"mae={s['oof_mae_mean']:.4f} nneg={s['oof_n_dims_r2_negative']} t={secs:.0f}s", flush=True)
        df = pd.DataFrame(rows)
        p = C.write_csv(df, "outputs/q1/prep_sweep.csv")
        print("wrote", p)
        return

    specs = family_specs(prep, family_map)
    names = list(specs) if a.families == "all" else [f.strip() for f in a.families.split(",") if f.strip()]
    rows = []
    for name in names:
        if name not in specs:
            raise SystemExit(f"unknown family {name}; known: {list(specs)}")
        print(f"[Q1] === {name} ===", flush=True)
        fam = specs[name]
        if a.block != "raw231":
            Xb, extra = D.feature_block(a.block)
            X_use = X[Xb].copy()
            if extra is not None:
                ex = extra.reindex(X_use.index)
                X_use = pd.concat([X_use, ex], axis=1)
        else:
            X_use = X
        oof, chosen, secs = run_family(name, fam, X_use, Y, cats, folds, family_map)
        s, per_rep, avg = summarize_oof(oof, np.asarray(Y))
        np.savez_compressed(ROOT / "outputs" / "q1" / "oof" / f"{name}__{a.block}.npz",
                            oof=oof, avg=avg, beer=tr, dims=np.array(D.TARGET_DIMS))
        rows.append({
            "family": name, "block": a.block, "prep": json.dumps(prep), "n_repeats": a.n_repeats,
            "oof_r2_mean": s["oof_r2_mean"], "oof_r2_sd_over_repeats": s["oof_r2_sd_over_repeats"],
            "oof_r2_mean_repeat_averaged": s["oof_r2_mean_repeat_averaged"],
            "oof_mae_mean": s["oof_mae_mean"], "oof_spearman_mean": s["oof_spearman_mean"],
            "oof_r2_median": s["oof_r2_median"], "n_dims_r2_negative": s["oof_n_dims_r2_negative"],
            "qwk_P1": s["calib_P1_oav_anchor"]["qwk"],
            "qwk_P2": s["calib_P2_range"]["qwk"],
            "qwk_P3": s["calib_P3_quantile"]["qwk"],
            "qwk_P4": s["calib_P4_sigma"]["qwk"],
            "grade_mae_P1": s["calib_P1_oav_anchor"]["grade_mae"],
            "grade_mae_P4": s["calib_P4_sigma"]["grade_mae"],
            "hyper_fixed": json.dumps(fam["spec"]["params"] if fam.get("spec") else {}),
            "hyper_chosen": json.dumps(chosen[:5]),
            "seconds": round(secs, 1), "note": fam["note"] + (" | " + a.note if a.note else ""),
        })
        print(f"  -> {name}: OOF R2={s['oof_r2_mean']:+.4f} (sd {s['oof_r2_sd_over_repeats']:.4f}) "
              f"MAE={s['oof_mae_mean']:.4f} rho={s['oof_spearman_mean']:.4f} "
              f"QWK_P1={s['calib_P1_oav_anchor']['qwk']:.4f} nneg={s['oof_n_dims_r2_negative']}", flush=True)

        if a.emit:
            # 契约产物（reviewer VP-0004）：predictions.csv 长表(row,dim,y_true,y_pred) +
            # predictions_overall.csv 单列(overall) + 逐维 R² 走 emit_output。
            # 注意：候选 EXP 的是**训练 OOF** 预测（row = beer），不是 holdout；holdout 只在锁定后的 q1_final 出现。
            oi = D.TARGET_DIMS.index("overall")
            pred_df = pd.DataFrame({
                "row": np.repeat(tr, D.N_DIMS),
                "dim": np.tile(D.TARGET_DIMS, len(tr)),
                "y_true": np.asarray(Y, float).ravel(order="F"),
                "y_pred": avg.ravel(order="F"),
            })
            pred_overall = pd.DataFrame({"row": tr, "y_true": np.asarray(Y, float)[:, oi],
                                         "y_pred": avg[:, oi]})
            met = {
                "r2": s["oof_r2_mean"], "r2_repeat_averaged": s["oof_r2_mean_repeat_averaged"],
                "mae": s["oof_mae_mean"], "spearman": s["oof_spearman_mean"],
                "qwk_p1": s["calib_P1_oav_anchor"]["qwk"], "qwk_p2": s["calib_P2_range"]["qwk"],
                "qwk_p3": s["calib_P3_quantile"]["qwk"], "qwk_p4": s["calib_P4_sigma"]["qwk"],
                "r2_sd_over_repeats": s["oof_r2_sd_over_repeats"],
                "n_dims": float(D.N_DIMS), "n_repeats": float(a.n_repeats),
            }
            print(emit_contract(met, pred_df,
                                outputs={"family": name, "block": a.block,
                                         "features": list(X_use.columns),
                                         "predictionSchema": "long(row=beer,dim,y_true,y_pred) OOF on train 200",
                                         "per_dim_r2": dict(zip(D.TARGET_DIMS, np.asarray(s["r2_per_dim"]).astype(float).tolist())),
                                         "per_dim_mae": dict(zip(D.TARGET_DIMS, np.asarray(s["mae_per_dim"]).astype(float).tolist())),
                                         "calib_by_policy": {k: s[k] for k in s if k.startswith("calib_")},
                                         "hyper_chosen_folds": chosen[:15]},
                                pred_name="predictions.csv"))
            import emit as E
            E.emit_predictions(pred_overall, "predictions_overall.csv", area="q1")
        df = pd.DataFrame(rows)
        p = C.write_csv(df, "outputs/q1/prep_sweep.csv")
        print("wrote", p)
        return

    specs = family_specs(prep, family_map)
    names = list(specs) if a.families == "all" else [f.strip() for f in a.families.split(",") if f.strip()]
    rows = []
    for name in names:
        if name not in specs:
            raise SystemExit(f"unknown family {name}; known: {list(specs)}")
        print(f"[Q1] === {name} ===", flush=True)
        fam = specs[name]
        if a.block != "raw231":
            Xb, extra = D.feature_block(a.block)
            X_use = X[Xb].copy()
            if extra is not None:
                ex = extra.reindex(X_use.index)
                X_use = pd.concat([X_use, ex], axis=1)
        else:
            X_use = X
        oof, chosen, secs = run_family(name, fam, X_use, Y, cats, folds, family_map)
        s, per_rep, avg = summarize_oof(oof, np.asarray(Y))
        np.savez_compressed(ROOT / "outputs" / "q1" / "oof" / f"{name}__{a.block}.npz",
                            oof=oof, avg=avg, beer=tr, dims=np.array(D.TARGET_DIMS))
        rows.append({
            "family": name, "block": a.block, "prep": json.dumps(prep), "n_repeats": a.n_repeats,
            "oof_r2_mean": s["oof_r2_mean"], "oof_r2_sd_over_repeats": s["oof_r2_sd_over_repeats"],
            "oof_r2_mean_repeat_averaged": s["oof_r2_mean_repeat_averaged"],
            "oof_mae_mean": s["oof_mae_mean"], "oof_spearman_mean": s["oof_spearman_mean"],
            "oof_r2_median": s["oof_r2_median"], "n_dims_r2_negative": s["oof_n_dims_r2_negative"],
            "qwk_P1": s["calib_P1_oav_anchor"]["qwk"],
            "qwk_P2": s["calib_P2_range"]["qwk"],
            "qwk_P3": s["calib_P3_quantile"]["qwk"],
            "qwk_P4": s["calib_P4_sigma"]["qwk"],
            "grade_mae_P1": s["calib_P1_oav_anchor"]["grade_mae"],
            "grade_mae_P4": s["calib_P4_sigma"]["grade_mae"],
            "hyper_fixed": json.dumps(fam["spec"]["params"] if fam.get("spec") else {}),
            "hyper_chosen": json.dumps(chosen[:5]),
            "seconds": round(secs, 1), "note": fam["note"] + (" | " + a.note if a.note else ""),
        })
        print(f"  -> {name}: OOF R2={s['oof_r2_mean']:+.4f} (sd {s['oof_r2_sd_over_repeats']:.4f}) "
              f"MAE={s['oof_mae_mean']:.4f} rho={s['oof_spearman_mean']:.4f} "
              f"QWK_P1={s['calib_P1_oav_anchor']['qwk']:.4f} nneg={s['oof_n_dims_r2_negative']}", flush=True)

        if a.emit:
            # 契约产物：OOF 预测长表 row,dim,y_true,y_pred（test 不参与选型，故这里只发布训练 OOF）
            pred_df = pd.DataFrame({
                "row": np.repeat(tr, D.N_DIMS),
                "dim": np.tile(D.TARGET_DIMS, len(tr)),
                "y_true": np.asarray(Y, float).ravel(order="F"),
                "y_pred": avg.ravel(order="F"),
            })
            met = {
                "r2": s["oof_r2_mean"], "r2_repeat_averaged": s["oof_r2_mean_repeat_averaged"],
                "mae": s["oof_mae_mean"], "spearman": s["oof_spearman_mean"],
                "qwk_P1": s["calib_P1_oav_anchor"]["qwk"], "r2_sd_over_repeats": s["oof_r2_sd_over_repeats"],
                "n_dims": float(D.N_DIMS), "n_repeats": float(a.n_repeats),
            }
            print(emit_contract(met, pred_df,
                                outputs={"family": name, "block": a.block,
                                         "features": list(X_use.columns),
                                         "predictionSchema": "long(row,dim,y_true,y_pred)",
                                         "calibration": {"policy": C.Z_GRADE_CALIBRATION["policy"],
                                                         "S_primary": C.Z_GRADE_CALIBRATION["primary"],
                                                         "S_sensitivity": C.Z_GRADE_CALIBRATION["sensitivity"]},
                                         "calib_by_policy": {k: s[k] for k in s if k.startswith("calib_")}},
                                pred_name="oof_predictions.csv"))
        df = pd.DataFrame(rows)
        C.write_csv(df, a.out)
    p = C.write_csv(pd.DataFrame(rows), a.out)
    print("wrote", p)
    if len(rows) > 1:
        cols = ["family", "oof_r2_mean", "oof_mae_mean", "oof_spearman_mean", "qwk_P1", "qwk_P2"]
        print(pd.DataFrame(rows)[cols].sort_values("oof_r2_mean", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
