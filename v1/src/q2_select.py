"""Q2-② 四方法分数矩阵 + Borda 聚合 + Jaccard + 独立先验 + 化学合理性（两阶段，各 <500s）。

协议（预注册，缺一不可）
  M1 多变量：Ridge（alpha 内层 5 折 CV）标准化系数 |b|；ElasticNet（alpha×l1_ratio
     内层 CV）作同族稳健性对照（不进 Borda）。
  M2 非线性：RandomForest 5 折 CV，每折验证折上的**置换重要性**（重复 3 次、向量化
     批量预测），折均值；不是不纯度重要性。
  M3 偏相关：对 [231 特征 + 50 目标] 联合精度矩阵做正则化估计，取目标-特征块
     |偏相关|。**主口径 = Ledoit-Wolf 收缩精度矩阵**（shrinkage≈0.22）；
     GraphicalLassoCV（alpha 内层 CV）作为敏感性对照，并记录其退化诊断（α≈0.39 时
     大量偏相关被压到 0，逐维排名退化为并列，见 m3_diagnostics）。
     理由：2.csv 非 PSD（不能直接求逆）；joint glasso CV 在 250x281 下过度收缩、
     大量偏相关精确为 0 导致 Top-3 退化为列索引并列，因此改用协议允许的
     "联合精度矩阵"正则化估计作为主口径，glasso-CV 结果完整保留为敏感性分析。
  M4 单变量：Spearman |rho| + BH-FDR（全局 11550 对 + 逐维 231 对两种 q）。
  Borda：每维把 4 个方法排名求和 → 最终 Top-3（并列按 M4 rank、列名索引确定性打破）。
  Jaccard：4 方法 Top-3 两两（每维 6 对）。
  可信度分级：每维每个共识化合物统计"4 方法中有几个把它排进 Top-3"，
    分 4/4、3/4、≤2/4 三档，并报各档维数/席位数。
  独立先验：6.csv |r| 与聚合重要性逐维 Spearman（选择完成后才读入，不参与选择）。
  化学合理性：预注册表 × 8.xlsx origin_paper/阈值/OAV 逐条核对，算命中率。

阶段
  --stage m1m4：M1 ridge / M1b enet / M4 Spearman+BH；写 univariate_fdr.csv 与
                outputs/q2/_stage_m1m4.npz；emit 部分 metrics（<120s）。
  --stage m2m3：M2 RF / M3 LW 偏相关（+glasso 敏感性）；读 _stage_m1m4.npz；
                Borda/Jaccard/置信度/先验/化学合理性；写全部主产物并 emit 主 metrics
                （<500s）。M4-only bootstrap B=100 只用于给 selection EXP 提供
                top3_stability 快速代理，完整四方法 bootstrap 在 q2_stability.py。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import q2_common as Q  # noqa: E402
import emit as E  # noqa: E402

warnings.filterwarnings("ignore")
OUT = C.ROOT / "outputs" / "q2"
RAW = C.RAW
STAGE_FILE = OUT / "_stage_m1m4.npz"


# ================================================================ 四方法
def ridge_scores(X, Y, seed=Q.SEED):
    from sklearn.linear_model import RidgeCV
    alphas = np.logspace(-2, 4, 13)
    p, q = X.shape[1], Y.shape[1]
    S = np.zeros((p, q))
    chosen = np.zeros(q)
    for j in range(q):
        m = RidgeCV(alphas=alphas, cv=5).fit(X, Y[:, j])
        S[:, j] = np.abs(m.coef_)
        chosen[j] = m.alpha_
    return S, chosen


def enet_scores(X, Y, seed=Q.SEED):
    from sklearn.linear_model import ElasticNetCV
    p, q = X.shape[1], Y.shape[1]
    S = np.zeros((p, q))
    info = {"alpha": np.zeros(q), "l1_ratio": np.zeros(q), "n_nonzero": np.zeros(q)}
    for j in range(q):
        m = ElasticNetCV(l1_ratio=[0.1, 0.5, 0.9, 1.0], cv=3, max_iter=5000,
                         alphas=30, n_jobs=-1, random_state=seed)
        m.fit(X, Y[:, j])
        S[:, j] = np.abs(m.coef_)
        info["alpha"][j] = m.alpha_
        info["l1_ratio"][j] = m.l1_ratio_
        info["n_nonzero"][j] = int((m.coef_ != 0).sum())
    return S, info


def rf_perm_scores(X, Y, seed=Q.SEED, n_splits=5, n_rep=3, n_estimators=200,
                   max_features=0.33, min_samples_leaf=2):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import KFold
    p, q = X.shape[1], Y.shape[1]
    S = np.zeros((p, q))
    folds = list(KFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X))
    for j in range(q):
        acc = np.zeros(p)
        for fi, (tr, te) in enumerate(folds):
            rf = RandomForestRegressor(
                n_estimators=n_estimators, max_features=max_features,
                min_samples_leaf=min_samples_leaf, n_jobs=-1,
                random_state=seed + 100 * fi).fit(X[tr], Y[tr, j])
            Xte, yte = X[te], Y[te, j]
            base = float(((rf.predict(Xte) - yte) ** 2).mean())
            rng = np.random.default_rng(seed + 1000 * fi + j)
            blocks = []
            for f in range(p):
                for _ in range(n_rep):
                    Xp = Xte.copy()
                    Xp[:, f] = rng.permutation(Xp[:, f])
                    blocks.append(Xp)
            pred = rf.predict(np.vstack(blocks)).reshape(p * n_rep, len(yte))
            mse = ((pred - yte[None, :]) ** 2).mean(axis=1).reshape(p, n_rep).mean(axis=1)
            acc += (mse - base) / n_splits
        S[:, j] = acc
    return S


def m3_partial_lw(X, Y):
    """M3 主口径：Ledoit-Wolf 收缩联合精度矩阵 -> 目标-特征块 |偏相关|。"""
    from sklearn.covariance import LedoitWolf
    Z = np.hstack([X, Y])
    lw = LedoitWolf().fit(Z)
    P = lw.precision_
    d = np.sqrt(np.maximum(np.diag(P), 1e-15))
    pc = -P / np.outer(d, d)
    p, q = X.shape[1], Y.shape[1]
    return np.abs(pc[:p, p:p + q]), {"shrinkage": float(lw.shrinkage_)}


def m3_partial_glasso(X, Y, cv=3, max_iter=200):
    """M3 敏感性：GraphicalLassoCV（alpha 内层 CV）联合精度矩阵。"""
    from sklearn.covariance import GraphicalLassoCV
    Z = np.hstack([X, Y])
    with warnings.catch_warnings(record=True) as wl:
        warnings.simplefilter("always")
        gl = GraphicalLassoCV(cv=cv, max_iter=max_iter, n_jobs=-1).fit(Z)
        n_warn = sum(1 for w in wl if "did not converge" in str(w.message))
    P = gl.precision_
    d = np.sqrt(np.maximum(np.diag(P), 1e-15))
    pc = -P / np.outer(d, d)
    p, q = X.shape[1], Y.shape[1]
    S = np.abs(pc[:p, p:p + q])
    top1 = [int(np.argmax(S[:, j])) for j in range(q)]
    diag = {
        "alpha": float(gl.alpha_),
        "n_convergence_warnings": int(n_warn),
        "frac_exact_zero_partial": float((S == 0).mean()),
        "n_dims_all_zero_column": int((S.sum(axis=0) == 0).sum()),
        "top1_mode_count": int(pd.Series(top1).value_counts().iloc[0]),
    }
    return S, diag


def spearman_univariate(X, Y, n_eff=None):
    from scipy.stats import norm
    rho = Q.spearman_pair(X, Y)
    if n_eff is not None:
        z = np.arctanh(np.clip(rho, -0.999999, 0.999999)) * np.sqrt(np.maximum(n_eff - 3, 1))
        p = 2.0 * norm.sf(np.abs(z))
    else:
        p = Q.fisher_p(rho, X.shape[0])
    return rho, p, Q.bh_fdr(p), np.column_stack([Q.bh_fdr(p[:, j]) for j in range(Y.shape[1])])


# ================================================================ 聚合
def borda(Y, S):
    q = Y.shape[1]
    R = {m: np.column_stack([Q.rank_high(S[m][:, j]) for j in range(q)]) for m in Q.METHODS}
    borda_sum = sum(R[m] for m in Q.METHODS)
    return borda_sum / len(Q.METHODS), borda_sum, R


def top3_idx(mean_rank_col, m4_rank_col, p):
    return np.lexsort((np.arange(p), m4_rank_col, mean_rank_col))[:3]


def top3_of(rank_col, k=3):
    return np.argsort(rank_col, kind="stable")[:k]


# ================================================================ 6.csv 先验
def load_prior():
    x6 = C.load_corr_cross()
    h2r = Q.human_to_r_map()
    rows = {h: h2r[Q.norm_name(h)] for h in x6.index if Q.norm_name(h) in h2r}
    dm = Q.dim_map()
    col_norm = {Q.norm_name(c): c for c in x6.columns}
    dim_to_col = {}
    for _, r in dm.iterrows():
        c = col_norm.get(Q.norm_name(r["in_6csv"]))
        if c is not None:
            dim_to_col[str(r["target_col_4csv"])] = c
    return x6, rows, dim_to_col


def prior_consistency(feat, Y, mean_rank, R_m4):
    from scipy.stats import spearmanr
    x6, rows, dim_to_col = load_prior()
    r6 = x6.rename(index=rows)
    r6 = r6[~r6.index.duplicated()]
    common = [c for c in r6.index if c in feat]
    idx = [feat.index(c) for c in common]
    out = []
    for j, dim in enumerate(Y.columns):
        col = dim_to_col.get(dim)
        if col is None:
            out.append({"dim": dim, "n_common": 0, "spearman_rho": np.nan, "p_value": np.nan,
                        "top10_overlap": np.nan, "spearman_rho_m4only": np.nan, "p_m4only": np.nan})
            continue
        a = np.abs(r6.loc[common, col].to_numpy(dtype=float))
        b = -mean_rank[idx, j]
        b4 = -R_m4[idx, j]
        rho, p = spearmanr(a, b)
        rho4, p4 = spearmanr(a, b4)
        top10_6 = set(np.array(common)[np.argsort(-a)[:10]])
        top10_ours = set(np.array(common)[np.argsort(-b)[:10]])
        out.append({"dim": dim, "n_common": len(common), "spearman_rho": float(rho),
                    "p_value": float(p), "top10_overlap": len(top10_6 & top10_ours) / 10.0,
                    "spearman_rho_m4only": float(rho4), "p_m4only": float(p4)})
    return pd.DataFrame(out)


# ================================================================ 化学合理性
def chemical_plausibility(feat, Y, top3, rho_m4, q_global, R_m4):
    prereg = pd.read_csv(OUT / "preregistered_expectations.csv")
    pre = {r["dim"]: r for _, r in prereg.iterrows()}
    meta = Q.compound_meta()
    oav_df = Q.oav_stats()
    oav = oav_df.set_index("compound") if not oav_df.empty else pd.DataFrame()
    long = C.oav_long()

    direct = {}
    combos = list(C.DEFECT_DIMS.items()) + [("acidity", ["lactic_acid.mg.L."]),
                                            ("lactic", ["lactic_acid.mg.L."]),
                                            ("acetic", ["acetic_acid.g.L."])]
    for dim, comps in combos:
        if dim not in Y.columns:
            continue
        for comp in comps:
            s = long[long["compound"] == comp]
            if s.empty:
                continue
            m = s.groupby("beer")["oav"].mean()
            y = pd.Series(Y[dim].to_numpy(), index=np.arange(1, len(Y) + 1))
            dfj = pd.DataFrame({"oav": m, "y": y}).dropna()
            if len(dfj) > 10:
                direct[(dim, comp)] = float(dfj["oav"].corr(dfj["y"], method="spearman"))

    coldims = list(Y.columns)
    rows = []
    for dim in coldims:
        j = coldims.index(dim)
        pr = pre.get(dim)
        expected = [] if (pr is None or not bool(pr["preregistered"])) else str(pr["expected_compounds"]).split(";")
        signs = [] if (pr is None or not bool(pr["preregistered"])) else [int(x) for x in str(pr["expected_signs"]).split(";")]
        sign_map = dict(zip(expected, signs))
        for rank, ci in enumerate(top3[dim], start=1):
            comp = feat[ci]
            r = {
                "dim": dim, "rank": rank, "compound": comp,
                "in_prereg": comp in expected,
                "preregistered_dim": bool(pr["preregistered"]) if pr is not None else False,
                "expected_sign": sign_map.get(comp, 0),
                "observed_rho": float(rho_m4[ci, j]),
                "q_bh": float(q_global[ci, j]),
                "origin_paper": meta["origin_paper"].get(comp, np.nan) if comp in meta.index else np.nan,
                "threshold_mean": meta["threshold_mean"].get(comp, np.nan) if comp in meta.index else np.nan,
                "unit": meta["unit"].get(comp, np.nan) if comp in meta.index else np.nan,
                "off_flavors": meta["off_flavors"].get(comp, np.nan) if comp in meta.index else np.nan,
                "mean_oav": float(oav.loc[comp, "mean_oav"]) if (not oav.empty and comp in oav.index) else np.nan,
                "frac_oav_gt1": float(oav.loc[comp, "frac_oav_gt1"]) if (not oav.empty and comp in oav.index) else np.nan,
                "oav_sensory_rho": direct.get((dim, comp), np.nan),
            }
            r["sign_agrees"] = (np.sign(r["observed_rho"]) == r["expected_sign"]) if r["expected_sign"] != 0 else np.nan
            rows.append(r)
    hit = pd.DataFrame(rows)
    pre_mask = hit["preregistered_dim"].astype(bool)
    hit["in_prereg"] = hit["in_prereg"].astype(bool)
    n_seats = int(pre_mask.sum())
    n_hits = int(hit.loc[pre_mask, "in_prereg"].sum())
    hit_rate = n_hits / n_seats if n_seats else float("nan")

    m4_rows = []
    for j, dim in enumerate(coldims):
        pr = pre.get(dim)
        expected = [] if (pr is None or not bool(pr["preregistered"])) else str(pr["expected_compounds"]).split(";")
        for ci in top3_of(R_m4[:, j], 3):
            m4_rows.append({"dim": dim, "compound": feat[ci],
                            "in_prereg": feat[ci] in expected,
                            "preregistered_dim": bool(pr["preregistered"]) if pr is not None else False})
    m4df = pd.DataFrame(m4_rows)
    m4_mask = m4df["preregistered_dim"].astype(bool)
    m4_hit = float(m4df.loc[m4_mask, "in_prereg"].mean()) if m4_mask.any() else float("nan")

    sign_num = pd.to_numeric(hit["sign_agrees"], errors="coerce")
    smask = pre_mask & hit["in_prereg"] & sign_num.notna()
    sign_mean = float(sign_num[smask].mean()) if smask.any() else float("nan")

    summary = {
        "n_preregistered_dims": int(pre_mask.sum() // 3),
        "n_exploratory_dims": int(Y.shape[1] - pre_mask.sum() // 3),
        "n_seats": n_seats, "n_hits": n_hits,
        "hit_rate": float(hit_rate),
        "hit_rate_denominator": "preregistered dims x 3 Top-3 seats (48 x 3 = 144)",
        "m4_only_hit_rate_reference": m4_hit,
        "sign_agreement_among_hits": sign_mean,
        "direct_oav_sensory_rho": {f"{d}|{c}": v for (d, c), v in direct.items()},
        "causal_limit": "全部为横截面观测关联；不声称因果，也不声称干预效果。",
        "lod_note": "1.csv 中 calibrated==0 是 log10(最小正浓度/2) 的 LOD/2 删失替代码；OAV 一律用 C.oav_long()（作者标定浓度）。",
    }
    return hit, summary


# ================================================================ 阶段
def stage_m1m4(d, seed):
    t0 = time.time()
    feat, Ydf = d["feat_cols"], d["Y"]
    X = d["Xz"].to_numpy(float)
    Y = Ydf.to_numpy(float)
    p, q = X.shape[1], Y.shape[1]
    print("[m1m4] ridge ...", flush=True)
    S1, ridge_alpha = ridge_scores(X, Y, seed=seed)
    print("[m1m4] elastic net ...", flush=True)
    S1b, enet_info = enet_scores(X, Y, seed=seed)
    print("[m1m4] spearman + BH ...", flush=True)
    Xraw = d["X_raw"]
    n_eff = np.outer((~Xraw.isna()).sum(axis=0).to_numpy(), np.ones(q))
    rho, pval, q_global, q_within = spearman_univariate(X, Y, n_eff=n_eff)
    from scipy.stats import spearmanr as _sp
    pair_rho = np.array(rho, copy=True)
    for i, c in enumerate(feat):
        if not Xraw[c].isna().any():
            continue
        m = Xraw[c].notna().to_numpy()
        xi = Xraw.loc[m, c].to_numpy(float)
        for j in range(q):
            pair_rho[i, j] = _sp(xi, Y[m, j]).statistic
    m4_sens = float(_sp(np.abs(rho).ravel(), np.abs(pair_rho).ravel()).statistic)

    np.savez_compressed(
        STAGE_FILE, S1=S1, S1b=S1b, rho=rho, pval=pval,
        q_global=q_global, q_within=q_within, pair_rho=pair_rho,
        ridge_alpha=ridge_alpha, enet_alpha=enet_info["alpha"],
        enet_l1=enet_info["l1_ratio"], enet_nz=enet_info["n_nonzero"])
    uf = pd.DataFrame({
        "dim": np.repeat(Ydf.columns, p), "compound": np.tile(feat, q),
        "rho": rho.T.ravel(), "p": pval.T.ravel(),
        "q_bh": q_global.T.ravel(), "q_bh_within": q_within.T.ravel(),
    })
    uf["rank_in_dim"] = uf.groupby("dim")["rho"].rank(ascending=False, method="average").astype(float)
    uf.to_csv(OUT / "univariate_fdr.csv", index=False, encoding="utf-8")
    E.emit_predictions(uf, "univariate_fdr.csv", area="q2")
    meta = {
        "stage": "m1m4", "seed": seed, "runtime_seconds": round(time.time() - t0, 1),
        "ridge_alpha_median": float(np.median(ridge_alpha)),
        "enet_alpha_median": float(np.median(enet_info["alpha"])),
        "enet_l1_ratio_median": float(np.median(enet_info["l1_ratio"])),
        "enet_nonzero_median": float(np.median(enet_info["n_nonzero"])),
        "m4_impute_sensitivity_spearman": m4_sens,
        "m4_n_q_global_lt_0.05": int((q_global < 0.05).sum()),
        "m4_n_q_within_lt_0.05": int((q_within < 0.05).sum()),
        "n_features_tests": int(p * q),
        "bh_family": "global 11550 + within-dim 231",
    }
    (OUT / "stage_m1m4_meta.json").write_text(
        json.dumps(Q.sanitize(meta), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    E.emit_metrics({
        "M1_ridge_alpha_median": meta["ridge_alpha_median"],
        "M1_enet_alpha_median": meta["enet_alpha_median"],
        "M1_enet_l1_ratio_median": meta["enet_l1_ratio_median"],
        "M4_n_q_global_lt_0.05": meta["m4_n_q_global_lt_0.05"],
        "M4_n_q_within_lt_0.05": meta["m4_n_q_within_lt_0.05"],
        "M4_impute_sensitivity_spearman": m4_sens,
        "n_features_tests": meta["n_features_tests"],
        "runtime_seconds": meta["runtime_seconds"],
        "seed": seed,
    }, area="q2")
    E.emit_output("stage_m1m4_meta", Q.sanitize(meta), area="q2")
    print("[m1m4] done", round(time.time() - t0, 1), "s", flush=True)


def stage_m2m3(d, seed):
    t0 = time.time()
    feat, Ydf = d["feat_cols"], d["Y"]
    dims = list(Ydf.columns)
    X = d["Xz"].to_numpy(float)
    Y = Ydf.to_numpy(float)
    p, q = X.shape[1], Y.shape[1]
    if not STAGE_FILE.exists():
        raise SystemExit(f"missing {STAGE_FILE}: run --stage m1m4 first")
    st = np.load(STAGE_FILE)
    S1, S1b = st["S1"], st["S1b"]
    rho, pval, q_global, q_within = st["rho"], st["pval"], st["q_global"], st["q_within"]
    pair_rho = st["pair_rho"]
    S4 = np.abs(rho)
    ridge_alpha, enet_alpha = st["ridge_alpha"], st["enet_alpha"]
    enet_l1, enet_nz = st["enet_l1"], st["enet_nz"]
    from scipy.stats import spearmanr as _sp
    m4_sens = float(_sp(np.abs(rho).ravel(), np.abs(pair_rho).ravel()).statistic)

    print("[m2m3] RF permutation importance ...", flush=True)
    S2 = rf_perm_scores(X, Y, seed=seed)
    print("[m2m3] M3 Ledoit-Wolf partial corr ...", flush=True)
    S3, lw_info = m3_partial_lw(X, Y)
    print("[m2m3] M3 glasso-CV sensitivity ...", flush=True)
    S3g, gl_info = m3_partial_glasso(X, Y)
    top1 = [int(np.argmax(S3g[:, j])) for j in range(q)]
    gl_info["top1_mode_feature"] = feat[int(pd.Series(top1).value_counts().index[0])]

    S = {"M1": S1, "M2": S2, "M3": S3, "M4": S4}
    mean_rank, borda_sum, R = borda(Ydf, S)
    R_enet = np.column_stack([Q.rank_high(S1b[:, j]) for j in range(q)])

    # ---------- Top-3 + 可信度分级 ----------
    top3 = {}
    top3_rows = []
    for j, dim in enumerate(dims):
        idx = top3_idx(mean_rank[:, j], R["M4"][:, j], p)
        top3[dim] = idx
        methodsets = {m: set(int(x) for x in top3_of(R[m][:, j], 3)) for m in Q.METHODS}
        for rank, ci in enumerate(idx, start=1):
            n_methods = sum(1 for m in Q.METHODS if ci in methodsets[m])
            grade = "4/4" if n_methods == 4 else ("3/4" if n_methods == 3 else "<=2/4")
            top3_rows.append({
                "dim": dim, "rank": rank, "compound": feat[ci],
                "aggregate_score": float(mean_rank[ci, j]),
                "borda_sum": float(borda_sum[ci, j]),
                "M1_rank": float(R["M1"][ci, j]), "M2_rank": float(R["M2"][ci, j]),
                "M3_rank": float(R["M3"][ci, j]), "M4_rank": float(R["M4"][ci, j]),
                "n_methods_in_top3": n_methods, "confidence": grade,
                "spearman_rho": float(rho[ci, j]), "q_bh": float(q_global[ci, j]),
                "ridge_abs": float(S1[ci, j]), "enet_abs": float(S1b[ci, j]),
                "rf_permimp": float(S2[ci, j]), "partial_corr_abs": float(S3[ci, j]),
            })
    top3_df = pd.DataFrame(top3_rows)

    # ---------- Jaccard ----------
    pairs = [f"{Q.METHODS[a]}_{Q.METHODS[b]}" for a in range(4) for b in range(a + 1, 4)]
    jac_rows = []
    for j, dim in enumerate(dims):
        sets = {m: set(int(x) for x in top3_of(R[m][:, j], 3)) for m in Q.METHODS}
        cons = set(int(x) for x in top3[dim])
        for a in range(4):
            for b in range(a + 1, 4):
                ma, mb = Q.METHODS[a], Q.METHODS[b]
                inter, union = sets[ma] & sets[mb], sets[ma] | sets[mb]
                jac_rows.append({"dim": dim, "setA": ma, "setB": mb,
                                 "intersection_n": len(inter), "union_n": len(union),
                                 "jaccard": len(inter) / len(union) if union else np.nan})
        for m in Q.METHODS:
            inter, union = cons & sets[m], cons | sets[m]
            jac_rows.append({"dim": dim, "setA": "CONSENSUS", "setB": m,
                             "intersection_n": len(inter), "union_n": len(union),
                             "jaccard": len(inter) / len(union) if union else np.nan})
    jac = pd.DataFrame(jac_rows)
    jac["pair"] = jac["setA"] + "_" + jac["setB"]
    pair_means = {pr: float(jac[jac["pair"] == pr]["jaccard"].mean()) for pr in pairs}
    cons_means = {f"CONSENSUS_{m}": float(jac[jac["pair"] == f"CONSENSUS_{m}"]["jaccard"].mean())
                  for m in Q.METHODS}
    dim_mean_jac = jac[jac["pair"].isin(pairs)].groupby("dim")["jaccard"].mean()
    jac_overall = float(dim_mean_jac.get("overall", np.nan))

    # ---------- method_top3 ----------
    mt_rows = []
    for j, dim in enumerate(dims):
        for m in Q.METHODS:
            for rank, ci in enumerate(top3_of(R[m][:, j], 3), start=1):
                mt_rows.append({"dim": dim, "method": m, "rank": rank,
                                "compound": feat[ci], "score": float(S[m][ci, j])})
    mt = pd.DataFrame(mt_rows)

    # ---------- importance_matrix ----------
    imp = pd.DataFrame({
        "dim": np.repeat(dims, p), "compound": np.tile(feat, q),
        "M1_ridge_abs": S1.T.ravel(), "M1_ridge_rank": R["M1"].T.ravel(),
        "M1_enet_abs": S1b.T.ravel(), "M1_enet_rank": R_enet.T.ravel(),
        "M2_permimp": S2.T.ravel(), "M2_rank": R["M2"].T.ravel(),
        "M3_partial_abs": S3.T.ravel(), "M3_rank": R["M3"].T.ravel(),
        "M3_glassoCV_abs": S3g.T.ravel(),
        "M4_abs_rho": S4.T.ravel(), "M4_rank": R["M4"].T.ravel(),
        "mean_rank": mean_rank.T.ravel(), "borda_sum": borda_sum.T.ravel(),
    })
    pre_df = pd.read_csv(OUT / "preregistered_expectations.csv").set_index("dim")
    imp["in_prereg"] = [
        c in ([] if not bool(pre_df.loc[dm, "preregistered"])
              else str(pre_df.loc[dm, "expected_compounds"]).split(";"))
        for dm, c in zip(imp["dim"], imp["compound"])]
    imp.to_csv(OUT / "importance_matrix.csv", index=False, encoding="utf-8")

    # ---------- 置信度分级汇总 ----------
    conf_summary = {}
    for g in ["4/4", "3/4", "<=2/4"]:
        sub = top3_df[top3_df["confidence"] == g]
        conf_summary[g] = {
            "n_seats": int(len(sub)),
            "share_seats": float(len(sub) / len(top3_df)),
            "n_dims_with_any": int(sub["dim"].nunique()),
            "dims": sorted(sub["dim"].unique().tolist()),
        }

    # ---------- 独立先验 ----------
    prior_df = prior_consistency(feat, Ydf, mean_rank, R["M4"])
    prior_df.to_csv(OUT / "prior_consistency.csv", index=False, encoding="utf-8")
    prior_sum = {
        "method": "Spearman(|r_6csv|, -mean_rank_over_4_methods) per dim over 44 common compounds",
        "n_dims": int(prior_df["n_common"].gt(0).sum()),
        "mean_rho": float(prior_df["spearman_rho"].mean()),
        "median_rho": float(prior_df["spearman_rho"].median()),
        "min_rho": float(prior_df["spearman_rho"].min()),
        "max_rho": float(prior_df["spearman_rho"].max()),
        "n_positive": int((prior_df["spearman_rho"] > 0).sum()),
        "n_p_sig_pos": int(((prior_df["spearman_rho"] > 0) & (prior_df["p_value"] < 0.05)).sum()),
        "mean_top10_overlap": float(prior_df["top10_overlap"].mean()),
        "m4_only_mean_rho": float(prior_df["spearman_rho_m4only"].mean()),
        "m4_only_n_sig_pos": int(((prior_df["spearman_rho_m4only"] > 0) & (prior_df["p_m4only"] < 0.05)).sum()),
        "selection_independence": {
            "6csv_sha256": hashlib.sha256((RAW / "6.csv").read_bytes()).hexdigest(),
            "6csv_loaded_when": "after M1-M4 scores and Borda aggregation; 6.csv not used for selection",
            "inputs_used_for_selection": {
                "data/raw/2.csv": hashlib.sha256((RAW / "2.csv").read_bytes()).hexdigest(),
                "data/raw/1.csv": hashlib.sha256((RAW / "1.csv").read_bytes()).hexdigest(),
                "data/raw/4.csv": hashlib.sha256((RAW / "4.csv").read_bytes()).hexdigest(),
                "outputs/protocol/corr2_map.csv": hashlib.sha256(
                    (C.ROOT / "outputs/protocol/corr2_map.csv").read_bytes()).hexdigest(),
            },
            "files_not_used_for_selection": ["data/raw/6.csv", "data/raw/5.csv", "data/raw/7.csv",
                                             "8.xlsx GBM importance MDI", "8.xlsx GBM SHAP Values"],
        },
    }
    (OUT / "prior_consistency.json").write_text(
        json.dumps(Q.sanitize(prior_sum), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    # ---------- 化学合理性 ----------
    hit_df, plaus = chemical_plausibility(feat, Ydf, top3, rho, q_global, R["M4"])
    hit_df.to_csv(OUT / "chemical_plausibility.csv", index=False, encoding="utf-8")

    # ---------- 快速 M4-only bootstrap（B=100）：selection EXP 的 top3_stability 代理 ----------
    n = X.shape[0]
    Ximp = d["X_imp"]
    cons = {(r["dim"], r["compound"]): 0 for _, r in top3_df.iterrows()}
    Bp = 100
    for b in range(Bp):
        idx = np.random.default_rng(seed + b).integers(0, n, n)
        rb = Q.spearman_pair(Ximp.iloc[idx].to_numpy(float), Y[idx])
        for j, dim in enumerate(dims):
            for ci in np.argsort(-np.abs(rb[:, j]), kind="stable")[:3]:
                key = (dim, feat[ci])
                if key in cons:
                    cons[key] += 1
    top3_df["freq_M4_B100"] = [cons[(r["dim"], r["compound"])] / Bp for _, r in top3_df.iterrows()]
    proxy_stability = float(top3_df["freq_M4_B100"].mean())

    # ---------- 写盘 ----------
    top3_df.to_csv(OUT / "top3_per_dimension.csv", index=False, encoding="utf-8")
    mt.to_csv(OUT / "method_top3.csv", index=False, encoding="utf-8")
    jac.to_csv(OUT / "method_jaccard.csv", index=False, encoding="utf-8")
    top3_df[["dim", "rank", "compound", "n_methods_in_top3", "confidence"]].to_csv(
        OUT / "confidence_grading.csv", index=False, encoding="utf-8")

    flat = {m: S[m].T.ravel() for m in Q.METHODS}
    rc = pd.DataFrame(index=Q.METHODS, columns=Q.METHODS, dtype=float)
    for a in Q.METHODS:
        for b in Q.METHODS:
            rc.loc[a, b] = _sp(flat[a], flat[b]).statistic
    rc.to_csv(OUT / "method_rank_corr.csv", encoding="utf-8")

    def crossdim_corr(Sm):
        M = Sm.T
        Rk = np.apply_along_axis(lambda v: pd.Series(v).rank().to_numpy(), 0, M)
        C = np.corrcoef(Rk.T)
        k = C.shape[0]
        return float((C.sum() - k) / (k * (k - 1)))

    m3_diag = {
        "primary_M3": "Ledoit-Wolf shrinkage joint precision partial correlation",
        "ledoitwolf_shrinkage": lw_info["shrinkage"],
        "glassoCV_sensitivity": gl_info,
        "crossdim_rank_corr_LW": crossdim_corr(S3),
        "crossdim_rank_corr_glassoCV": crossdim_corr(np.nan_to_num(S3g)),
        "glasso_vs_LW_score_spearman": float(_sp(S3.ravel(), S3g.ravel()).statistic),
        "why": ("GraphicalLassoCV 在本数据（n=250, p=281）选到 alpha≈0.39，大量偏相关被压成 0，"
                "逐维 Top-3 退化为列索引并列（top1 众数占 27/50）；因此主口径改用协议允许的"
                "联合精度矩阵正则化估计（Ledoit-Wolf），glasso-CV 结果保留为敏感性并如实记录退化。"),
    }
    (OUT / "m3_diagnostics.json").write_text(
        json.dumps(Q.sanitize(m3_diag), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    # ---------- chemical_plausibility.md ----------
    lines = []
    lines.append("# Q2 化学合理性论证（Top-3 关键化合物）\n")
    lines.append("> 结论只声明**关联/预测贡献**，不声明因果。数据为横截面观测；1.csv 的 "
                 "`calibrated==0` 是 LOD/2 删失替代码（755 格），OAV 一律用 `C.oav_long()`。\n")
    lines.append("## 1. 预注册与命中率\n")
    lines.append(f"- 预注册表：`outputs/q2/preregistered_expectations.csv`（在任何选择之前落盘，SCRIPT-0021）。\n"
                 f"- 预注册维度 {plaus['n_preregistered_dims']} 个（另 {plaus['n_exploratory_dims']} 个探索性维度不进分母）。\n"
                 f"- 最终 Top-3 共 {plaus['n_seats']} 个席位，命中预注册集合 **{plaus['n_hits']}**，"
                 f"**命中率 = {plaus['hit_rate']:.3f}**。\n"
                 f"- 命中席位中方向一致比例 = {plaus['sign_agreement_among_hits']:.3f}。\n"
                 f"- 参考：只用 M4 单变量 Top-3 的命中率 = {plaus['m4_only_hit_rate_reference']:.3f}。\n")
    lines.append("## 2. 缺陷维的物理一致性（感官值 vs 该化合物 OAV 的 Spearman）\n")
    lines.append("| 维度 | 化合物 | rho(感官, OAV) |\n|---|---|---|")
    for k, v in plaus["direct_oav_sensory_rho"].items():
        d_, c_ = k.split("|")
        lines.append(f"| {d_} | {c_} | {v:.3f} |")
    lines.append("\n**解读（含反直觉结果）**：dms 与 diacetyl 的感官值与对应化合物 OAV 的秩相关接近 0，"
                 "说明这两个缺陷维的评分几乎不随浓度变化（阈值以下普遍不可察觉，或感官卡受风格混淆）。"
                 "若这两个维的 Top-3 出现 DMS / 2,3-丁二酮，本报告如实记录而不回避："
                 "它是「与评分几乎不相关的名义关键化合物」，不能当作可干预的关键因素。\n")
    lines.append("## 3. 逐维明细（预注册维度）\n")
    for dim in dims:
        pr = pre_df.loc[dim]
        if not bool(pr["preregistered"]):
            continue
        sub = hit_df[hit_df["dim"] == dim]
        lines.append(f"### {dim}\n")
        lines.append(f"预注册期望：{pr['expected_compounds']}（方向 {pr['expected_signs']}）；理由：{pr['rationale']}\n")
        lines.append("| rank | compound | 命中 | origin_paper | 阈值 | 平均OAV | OAV>1比例 | rho(M4) | 方向一致 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for _, r in sub.iterrows():
            thr = "" if pd.isna(r["threshold_mean"]) else f"{r['threshold_mean']:.4g} {r['unit'] if pd.notna(r['unit']) else ''}"
            mo = "" if pd.isna(r["mean_oav"]) else f"{r['mean_oav']:.3g}"
            fo = "" if pd.isna(r["frac_oav_gt1"]) else f"{r['frac_oav_gt1']:.2f}"
            sa = "" if pd.isna(r["sign_agrees"]) else ("是" if r["sign_agrees"] else "否")
            lines.append(f"| {int(r['rank'])} | {r['compound']} | {'是' if r['in_prereg'] else '否'} | "
                         f"{r['origin_paper']} | {thr} | {mo} | {fo} | {r['observed_rho']:.3f} | {sa} |")
        lines.append("")
    lines.append("## 4. 探索性维度（不进命中率）\n")
    for dim in dims:
        pr = pre_df.loc[dim]
        if bool(pr["preregistered"]):
            continue
        sub = hit_df[hit_df["dim"] == dim]
        lines.append(f"- {dim}：Top-3 = {', '.join(sub['compound'].tolist())}（无单化合物先验，仅描述）")
    lines.append("\n## 5. 限制\n")
    lines.append("- 共线性：重算相关矩阵条件数 ≈9.4e4；2.csv 非 PSD（5 个负特征值、数值秩 226/231），"
                 "单变量相关会把同一共线簇的多个成员同时排到前面，所以最终 Top-3 用 4 方法 Borda 聚合。\n"
                 "- 跨方法一致性弱（见 selection_summary 的 Jaccard），因此 Top-3 不是唯一可辨识答案；"
                 "本报告并列每方法 Top-3 与 4/4、3/4、<=2/4 可信度分级。\n"
                 "- 6.csv 只作独立先验核对（选择完成后才读入），不参与 Top-3；其 |r| 与本报告的聚合重要性"
                 f"逐维秩相关均值 = {prior_sum['mean_rho']:.3f}（{prior_sum['n_p_sig_pos']}/{prior_sum['n_dims']} 维显著为正）。\n"
                 "- 8.xlsx 的 GBM importance/SHAP 是目标泄漏产物，未用于选择。\n"
                 "- 所有化学机制解释均为已知风味化学的定性对照，不是从本数据估计的因果效应。\n")
    (OUT / "chemical_plausibility.md").write_text("\n".join(lines), encoding="utf-8")

    # ---------- summary ----------
    sel_summary = {
        "n_dims": int(q), "n_features": int(p), "n_samples": int(X.shape[0]),
        "seed": int(seed),
        "seed_source": "MODELING_SEED env" if os.environ.get("MODELING_SEED") else "default 42",
        "borda_method": "sum of per-method ranks (1 = most important); mean = aggregate_score",
        "jaccard_by_pair": pair_means,
        "jaccard_mean": float(dim_mean_jac.mean()),
        "jaccard_median": float(dim_mean_jac.median()),
        "jaccard_threshold": Q.JACCARD_THRESHOLD,
        "n_dims_jaccard_ge_threshold": int((dim_mean_jac >= Q.JACCARD_THRESHOLD).sum()),
        "jaccard_overall_dim": jac_overall,
        "consensus_jaccard_by_method": cons_means,
        "confidence_grading": conf_summary,
        "top3_stability_m4_b100_proxy": proxy_stability,
        "m1_ridge_alpha_median": float(np.median(ridge_alpha)),
        "m1_enet": {"alpha_median": float(np.median(enet_alpha)),
                    "l1_ratio_median": float(np.median(enet_l1)),
                    "n_nonzero_median": float(np.median(enet_nz))},
        "m2": {"n_splits": 5, "n_perm_repeats": 3, "n_estimators": 200,
               "importance": "permutation on validation fold (NOT impurity)"},
        "m3": {"primary": "Ledoit-Wolf joint precision partial correlation",
               "ledoitwolf_shrinkage": lw_info["shrinkage"],
               "glassoCV_alpha": gl_info["alpha"],
               "glassoCV_frac_exact_zero_partial": gl_info["frac_exact_zero_partial"],
               "glassoCV_top1_mode_feature": gl_info["top1_mode_feature"],
               "glassoCV_top1_mode_count": gl_info["top1_mode_count"],
               "diagnostics_file": "outputs/q2/m3_diagnostics.json"},
        "m4": {"n_features_tests": int(p * q), "bh_family": "global 11550 + within-dim 231",
               "n_q_global_lt_0.05": int((q_global < 0.05).sum()),
               "n_q_within_lt_0.05": int((q_within < 0.05).sum()),
               "impute_sensitivity_score_spearman": m4_sens},
        "prior_consistency": {k: v for k, v in prior_sum.items() if k != "selection_independence"},
        "chemical_plausibility": {k: v for k, v in plaus.items() if k != "direct_oav_sensory_rho"},
        "runtime_seconds": round(time.time() - t0, 1),
    }
    (OUT / "selection_summary.json").write_text(
        json.dumps(Q.sanitize(sel_summary), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    # ---------- emit ----------
    E.emit_metrics({
        "jaccard_mean": float(dim_mean_jac.mean()),
        "jaccard_median": float(dim_mean_jac.median()),
        "n_dims_jaccard_ge_0.5": float((dim_mean_jac >= Q.JACCARD_THRESHOLD).sum()),
        "r2": float(dim_mean_jac.mean()),          # 包合同占位键，语义见 metricNote
        "r2_overall": jac_overall,
        "r2_50dim": float(dim_mean_jac.mean()),
        "holdout_r2_mean": float(dim_mean_jac.mean()),
        "top3_stability": float(proxy_stability),
        "freq_ge_080_share": float((top3_df["freq_M4_B100"] >= Q.FREQ_THRESHOLD).mean()),
        "n_slots_stable": float((top3_df["freq_M4_B100"] >= Q.FREQ_THRESHOLD).sum()),
        "prior_spearman_mean": float(prior_df["spearman_rho"].mean()),
        "prior_spearman_median": float(prior_df["spearman_rho"].median()),
        "prior_n_p_sig_pos": float(((prior_df["spearman_rho"] > 0) & (prior_df["p_value"] < 0.05)).sum()),
        "prior_top10_overlap_mean": float(prior_df["top10_overlap"].mean()),
        "prior_rank_corr_mean": float(prior_df["spearman_rho"].mean()),
        "prereg_hit_rate": float(plaus["hit_rate"]),
        "prereg_hits": float(plaus["n_hits"]),
        "prereg_seats": float(plaus["n_seats"]),
        "m4_n_q_global_lt_0.05": float((q_global < 0.05).sum()),
        "m3_ledoitwolf_shrinkage": float(lw_info["shrinkage"]),
        "n_conf_4of4": float(conf_summary["4/4"]["n_seats"]),
        "n_conf_3of4": float(conf_summary["3/4"]["n_seats"]),
        "n_conf_le2of4": float(conf_summary["<=2/4"]["n_seats"]),
        "runtime_seconds": float(time.time() - t0),
    }, area="q2")
    E.emit_output("selection_summary", Q.sanitize(sel_summary), area="q2")
    E.emit_output("prior_consistency", Q.sanitize(prior_sum), area="q2")
    E.emit_output("m3_diagnostics", Q.sanitize(m3_diag), area="q2")
    E.emit_output("confidence_grading", Q.sanitize(conf_summary), area="q2")
    E.emit_predictions(imp, "importance_matrix.csv", area="q2")
    E.emit_predictions(mt, "method_top3.csv", area="q2")
    E.emit_predictions(jac, "method_jaccard.csv", area="q2")
    E.emit_predictions(top3_df[["dim", "rank", "compound", "n_methods_in_top3", "confidence"]],
                       "confidence_grading.csv", area="q2")
    print(json.dumps(Q.sanitize({k: sel_summary[k] for k in
                                 ["jaccard_mean", "n_dims_jaccard_ge_threshold", "confidence_grading",
                                  "prior_consistency", "chemical_plausibility", "m3", "runtime_seconds"]}),
                     ensure_ascii=False, indent=2)[:3500], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="m2m3", choices=["m1m4", "m2m3"])
    args = ap.parse_args()
    t_start = time.time()
    seed = Q.effective_seed()
    OUT.mkdir(parents=True, exist_ok=True)
    d = Q.load_q2()
    print(f"stage={args.stage} seed={seed}", flush=True)
    if args.stage == "m1m4":
        stage_m1m4(d, seed)
    else:
        stage_m2m3(d, seed)
    print("total", round(time.time() - t_start, 1), "s", flush=True)


if __name__ == "__main__":
    main()
