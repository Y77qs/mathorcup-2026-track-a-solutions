"""Q2-① 共表达图与模块发现（2.csv Spearman × 1.csv 特征 × 8.xlsx 类群）。

做什么
  1. 用 Lead 固化的 `corr2_map.csv` 把 2.csv 的化学全名节点换成 1.csv 列名；
  2. 用 1.csv 重算 Spearman 与 2.csv 对照（验证"2.csv=Spearman"并量化差异）；
  3. 边：|rho| >= TAU_PRIMARY（预注册 0.30）且 BH-FDR(q<0.05)（后者用逐对完整样本
     n_eff 的 Fisher-z 计算，作为统计下限报告）；另给 tau 网格敏感性；
  4. 模块：加权贪心模块度（CNM）在 TAU_PRIMARY 图上发现模块；用谱聚类（同一 k）
     做独立复核并给 ARI；
  5. 模块化学解释：与 8.xlsx `origin_paper` 类群做富集（Fisher 精确检验 + BH）、
     模块得分与 50 个感官维度的 Spearman 关联；
  6. 共线性诊断：2.csv 相关矩阵特征值谱、条件数、|rho|>0.9 高共线簇（供选择阶段
     说明"为什么单变量相关不足以定关键"）。

限制（如实写入 JSON）
  * 2.csv 是作者在**原始**数据上算的相关系数；本项目重算时对 1.csv 做了列中位数
    填补，因此二者会有小额差异（本脚本量化最大/平均差与相关）。
  * 1.csv 中 calibrated==0 对应 log10(最小正浓度/2) 的 LOD/2 删失替代码（755 格，
    Lead 已核实）：本脚本不把 1.csv 数值当浓度，不做 OAV（OAV 只在 q2_select 用
    `C.oav_long()`）。
  * 阈值只影响**模块叙事**，不参与 Top-3 选择（选择用全矩阵，见 q2_select.py）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import q2_common as Q  # noqa: E402

# ---- 预注册的图参数（在查看任何模块组成之前固定） ----
TAU_PRIMARY = 0.30
TAU_GRID = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
COLLINEAR_RHO = 0.90
N_TOP_EIG = 20


def build_graph(A_abs: np.ndarray, tau: float):
    """返回二元邻接（权重=|rho|）与上三角边集。"""
    iu, ju = np.triu_indices(A_abs.shape[0], k=1)
    rho = A_abs[iu, ju]
    keep = rho >= tau
    W = np.zeros_like(A_abs)
    W[iu[keep], ju[keep]] = rho[keep]
    W = W + W.T
    return W, iu[keep], ju[keep]


def connected_components(W: np.ndarray):
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components
    ncomp, lab = connected_components(csr_matrix(W > 0), directed=False)
    return ncomp, lab


def spectral_partition(W: np.ndarray, k: int, seed: int = Q.SEED):
    """独立复核：sklearn SpectralClustering(precomputed affinity)；k=1 时返回全 0。"""
    if k <= 1:
        return np.zeros(W.shape[0], dtype=int)
    from sklearn.cluster import SpectralClustering
    sc = SpectralClustering(n_clusters=k, affinity="precomputed", assign_labels="kmeans",
                            random_state=seed, n_init=20)
    return sc.fit_predict(W)


def origin_enrichment(modules: pd.Series, meta: pd.DataFrame, n_boot: int = 0):
    """模块 × origin_paper 富集（Fisher 精确检验 + BH）。"""
    from scipy.stats import fisher_exact
    df = pd.DataFrame({"compound": modules.index, "module": modules.values})
    df = df.join(meta, on="compound")
    df["origin"] = df["origin_paper"].fillna("Unknown")
    rows = []
    groups = sorted(df["origin"].unique())
    for m in sorted(df["module"].unique()):
        in_m = df["module"] == m
        n_m = int(in_m.sum())
        for g in groups:
            a = int((in_m & (df["origin"] == g)).sum())
            b = int((in_m & (df["origin"] != g)).sum())
            c = int((~in_m & (df["origin"] == g)).sum())
            d_ = int((~in_m & (df["origin"] != g)).sum())
            if a + c == 0:
                continue
            odds, p = fisher_exact([[a, b], [c, d_]], alternative="greater")
            rows.append({
                "module": int(m), "origin_paper": g, "n_in_module": a,
                "n_module": n_m, "n_origin_total": a + c,
                "fold_enrichment": (a / n_m) / ((a + c) / len(df)) if n_m else np.nan,
                "fisher_p": float(p), "n_edges_in_module": None,
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["q_bh"] = Q.bh_fdr(out["fisher_p"].to_numpy())
    return out


def module_sensory(modules: pd.Series, Xz: pd.DataFrame, Y: pd.DataFrame):
    """模块得分（成员 z 值均值）与 50 维感官的 Spearman；BH 校正。"""
    dims = list(Y.columns)
    rows = []
    for m in sorted(modules.unique()):
        mem = [c for c in modules.index if modules[c] == m]
        score = Xz[mem].mean(axis=1).to_numpy()
        rho = np.array([pd.Series(score).corr(pd.Series(Y[d].to_numpy()), method="spearman")
                        for d in dims])
        p = Q.fisher_p(rho, len(score))
        rows.append(pd.DataFrame({
            "module": int(m), "module_size": len(mem), "dim": dims,
            "spearman_rho": rho, "p": p,
        }))
    out = pd.concat(rows, ignore_index=True)
    out["q_bh"] = Q.bh_fdr(out["p"].to_numpy())
    return out


def main():
    d = Q.load_q2()
    feat = d["feat_cols"]
    S = d["R2"].to_numpy(dtype=float)
    A = np.abs(S)

    # ---------- 1) 2.csv vs 1.csv 重算 ----------
    X = d["X_imp"].to_numpy(dtype=float)
    S_re = Q.spearman_matrix(X)
    off = ~np.eye(len(feat), dtype=bool)
    diff = np.abs(S - S_re)[off]
    recon = {
        "max_abs_diff": float(diff.max()),
        "mean_abs_diff": float(diff.mean()),
        "median_abs_diff": float(np.median(diff)),
        "corr_2csv_vs_recomputed": float(np.corrcoef(S[off], S_re[off])[0, 1]),
        "n_pairs": int(off.sum()),
        "n_nan_in_2csv": int(np.isnan(S).sum()),
        "recompute_note": "1.csv 列中位数填补（73 缺失/57750 格）后重算 Spearman；2.csv 为作者原值",
    }

    # ---------- 2) 显著性边（Fisher-z，逐对 n_eff） ----------
    n_eff = (~d["X_raw"].isna()).astype(float).T @ (~d["X_raw"].isna()).astype(float)
    n_eff = np.asarray(n_eff, dtype=float)
    iu_all, ju_all = np.triu_indices(len(feat), k=1)
    rho_all = S[iu_all, ju_all]
    ne_all = n_eff[iu_all, ju_all]
    from scipy.stats import norm
    zstat = np.arctanh(np.clip(rho_all, -0.999999, 0.999999)) * np.sqrt(np.maximum(ne_all - 3, 1))
    p_all = 2.0 * norm.sf(np.abs(zstat))
    p_all[ne_all < 10] = 1.0
    q_all = Q.bh_fdr(p_all)
    sig = q_all < Q.FDR_Q
    tau_fdr = float(np.min(np.abs(rho_all[sig]))) if sig.any() else float("nan")

    # ---------- 3) 主图（tau=TAU_PRIMARY） ----------
    W, iu, ju = build_graph(A, TAU_PRIMARY)
    labels, Qmod = Q.greedy_modularity(W)
    ncomp, comp_lab = connected_components(W)
    k_mod = int(len(np.unique(labels)))
    sizes = np.bincount(labels)
    mod_ids = np.argsort(-sizes)

    # 模块内边权/强度
    strength = W.sum(axis=1)
    deg = (W > 0).sum(axis=1)
    # 每节点最强伙伴
    top_partner = []
    Wd = W.copy()
    np.fill_diagonal(Wd, 0)
    for i in range(len(feat)):
        j = int(np.nanargmax(Wd[i]))
        top_partner.append((feat[j], float(Wd[i, j])))

    meta_all = Q.compound_meta().reindex(feat)
    modules = pd.Series(labels, index=feat, name="module")

    # 模块标签：主导 origin 富集
    enrich = origin_enrichment(modules, meta_all)
    # 编号按模块大小重排（0=最大），便于画图/论文叙述
    remap = {int(old): int(new) for new, old in enumerate(mod_ids)}
    labels = np.array([remap[int(x)] for x in labels])
    modules = pd.Series(labels, index=feat, name="module")
    enrich["module"] = enrich["module"].map(remap)
    sizes_new = np.bincount(labels)
    mod_label = {}
    for m in range(len(sizes_new)):
        e = enrich[(enrich["module"] == m) & (enrich["q_bh"] < 0.10)].sort_values(
            "fold_enrichment", ascending=False)
        if int(sizes_new[m]) < 3:
            mod_label[int(m)] = f"module{m}:singleton"
        elif not e.empty:
            g = e.iloc[0]["origin_paper"]
            mod_label[int(m)] = f"module{m}:{str(g).lower().replace(' ', '_')}"
        else:
            mod_label[int(m)] = f"module{m}:mixed"

    mod_df = pd.DataFrame({
        "compound": feat,
        "module": labels,
        "degree": deg,
        "strength": strength,
        "top_partner": [t[0] for t in top_partner],
        "top_partner_rho": [t[1] for t in top_partner],
        "origin_paper": meta_all["origin_paper"].reindex(feat).to_numpy(),
        "off_flavors": meta_all["off_flavors"].reindex(feat).to_numpy(),
        "threshold_mean": meta_all["threshold_mean"].reindex(feat).to_numpy(),
    })
    mod_df["module_size"] = mod_df.groupby("module")["compound"].transform("size")
    mod_df["module_label"] = mod_df["module"].map(mod_label)

    # ---------- 4) 谱聚类复核（只比 size>=3 的核；k 分别取 模块总数 / 核模块数） ----------
    core_ids = [m for m in np.unique(labels) if (labels == m).sum() >= 3]
    core = np.isin(labels, core_ids)
    spec_all = spectral_partition(W, k=max(k_mod, 1))
    spec_core = spectral_partition(W[core][:, core], k=max(len(core_ids), 1))
    ari_core_all_k = Q.ari(labels[core], spec_all[core]) if core.sum() > 0 else float("nan")
    ari_core_kcore = Q.ari(labels[core], spec_core) if core.sum() > 0 else float("nan")

    # ---------- 5) tau 敏感性 ----------
    grid_rows = []
    for tau in TAU_GRID:
        Wt, iut, jut = build_graph(A, tau)
        lab_t, qt = Q.greedy_modularity(Wt)
        sz = np.bincount(lab_t)
        ncomp_t, _ = connected_components(Wt)
        # 与主划分（只用落在 tau 图上的节点）比较 ARI（不同 k 下仍可比）
        grid_rows.append({
            "tau": tau, "n_edges": int(len(iut)), "density": float(len(iut) / len(iu_all)),
            "n_components": int(ncomp_t), "n_modules": int(len(sz)),
            "n_modules_ge3": int((sz >= 3).sum()), "giant_component": int(sz.max()),
            "modularity": float(qt),
            "ari_vs_primary": float(Q.ari(lab_t, labels)),
        })
    sens = pd.DataFrame(grid_rows)

    # ---------- 6) 共线性诊断（2.csv 与重算各一份） ----------
    def collinear_diag(M, name):
        vals = np.linalg.eigvalsh((M + M.T) / 2)
        vals = np.sort(vals)[::-1]
        lmax, lmin = float(vals[0]), float(vals[-1])
        tol = lmax * len(vals) * np.finfo(float).eps
        rank = int((vals > tol).sum())
        n_neg = int((vals < 0).sum())
        # 条件数：只有当矩阵正定（含数值容差）时才有定义；否则如实记 None
        cond = float(lmax / lmin) if lmin > tol else None
        iu2, ju2 = np.triu_indices(M.shape[0], k=1)
        hi = np.abs(M[iu2, ju2]) > COLLINEAR_RHO
        # 高共线簇 = |rho|>0.9 图的连通分量
        H = np.zeros_like(M)
        H[iu2[hi], ju2[hi]] = 1.0
        H = ((H + H.T) > 0).astype(float)
        nc, lab = connected_components(H)
        clusters = []
        for c in range(nc):
            mem = [feat[i] for i in np.where(lab == c)[0]]
            if len(mem) >= 2:
                clusters.append({"size": len(mem), "members": mem})
        clusters.sort(key=lambda x: -x["size"])
        return {
            "source": name,
            "eigenvalues_top20": [float(v) for v in vals[:N_TOP_EIG]],
            "eigenvalues_bottom5": [float(v) for v in vals[-5:]],
            "lambda_max": lmax,
            "lambda_min": lmin,
            "rank_numerical": rank,
            "n_negative_eigenvalues": n_neg,
            "is_positive_semidefinite": bool(n_neg == 0),
            "condition_number": cond,
            "condition_number_note": (
                "None = 矩阵非正定（含负特征值），条件数无定义；这正说明不能直接对 2.csv 求逆"
                if cond is None else "lmax/lmin（正定矩阵）"),
            "condition_number_abs": float(lmax / abs(lmin)) if lmin != 0 else None,
            "n_eigen_lt_1e-3": int((vals < 1e-3).sum()),
            "n_pairs_abs_rho_gt_0.9": int(hi.sum()),
            "n_collinear_clusters_size_ge2": len(clusters),
            "collinear_clusters": clusters[:20],
        }

    collin = {
        "tau_primary": TAU_PRIMARY,
        "note": ("2.csv 是 231x231 Spearman 相关矩阵；其条件数/特征值谱说明设计矩阵在 "
                 "231 维上高度共线，单变量 |rho| 会把同一共线簇的多个成员同时排到前面，"
                 "这就是 M1/M2/M3 多变量方法必须存在的原因。"),
        "aggregate_features": Q.AGG_FEATURES,
        "aggregate_note": ("kcalperc/acids_sum/esters_sum/aroma_hops_sum/sulfur_sum 是题面所述"
                           "由多个化合物算出的派生列，本身就是特征列的线性组合，计入高共线簇。"),
        "diag_2csv": collinear_diag(S, "2.csv"),
        "diag_recomputed_from_1csv": collinear_diag(S_re, "1.csv recomputed (median-imputed)"),
        "psd_note": ("2.csv 用逐对完整样本计算（各对 n_eff 不同），因此不是 PSD：本数据实测 5 个负特征值、"
                     "λmin=-0.0424，rank≈226/231。任何需要精度矩阵/求逆的方法（M3）都必须用正则化估计"
                     "或改用 1.csv 重算的正定矩阵，不能直接对 2.csv 求逆。"),
    }

    # ---------- 7) 写盘 ----------
    outdir = C.ROOT / "outputs" / "q2"
    outdir.mkdir(parents=True, exist_ok=True)

    edges = pd.DataFrame({
        "node1": [feat[i] for i in iu], "node2": [feat[j] for j in ju],
        "rho": S[iu, ju], "abs_rho": np.abs(S[iu, ju]),
    })
    # 对齐 BH q：从全对索引里取
    key = pd.MultiIndex.from_arrays([iu_all, ju_all])
    q_map = pd.Series(q_all, index=key)
    edges["q_bh"] = q_map.loc[pd.MultiIndex.from_arrays([iu, ju])].to_numpy()
    edges["fdr_significant"] = (edges["q_bh"] < Q.FDR_Q).astype(int)
    edges["module1"] = labels[iu]
    edges["module2"] = labels[ju]
    edges.sort_values(["module1", "module2", "abs_rho"], ascending=[True, True, False], inplace=True)
    edges.to_csv(outdir / "coexpression_edges.csv", index=False, encoding="utf-8")
    mod_df.to_csv(outdir / "coexpression_modules.csv", index=False, encoding="utf-8")
    enrich.to_csv(outdir / "module_origin_enrichment.csv", index=False, encoding="utf-8")
    ms = module_sensory(modules, d["Xz"], d["Y"])
    ms.sort_values(["module", "q_bh"]).to_csv(outdir / "module_sensory_assoc.csv", index=False, encoding="utf-8")
    sens.to_csv(outdir / "graph_threshold_sensitivity.csv", index=False, encoding="utf-8")
    d["name_map"].to_csv(outdir / "corr2_name_map_used.csv", index=False, encoding="utf-8")
    (outdir / "collinearity.json").write_text(
        __import__("json").dumps(collin, ensure_ascii=False, indent=2), encoding="utf-8")

    graph_summary = {
        "source": "data/raw/2.csv (231x231 Spearman) + data/raw/1.csv (250x231)",
        "tau_primary": TAU_PRIMARY,
        "tau_grid": TAU_GRID,
        "tau_fdr_equivalent": tau_fdr,
        "fdr": {"method": "BH over 26565 pairs on Fisher-z with per-pair complete n_eff", "q": Q.FDR_Q,
                "n_significant": int(sig.sum())},
        "n_nodes": int(len(feat)),
        "n_edges_primary": int(len(iu)),
        "density_primary": float(len(iu) / len(iu_all)),
        "n_components": int(ncomp),
        "n_modules": int(k_mod),
        "n_modules_size_ge3": int((sizes_new >= 3).sum()),
        "modularity": float(Qmod),
        "module_sizes": [int((labels == m).sum()) for m in range(len(sizes_new))],
        "module_labels": {str(k): v for k, v in sorted(mod_label.items())},
        "spectral_crosscheck": {
            "k_all_modules": k_mod, "k_core_modules": len(core_ids),
            "ari_on_core_nodes_with_k_all": float(ari_core_all_k),
            "ari_on_core_nodes_with_k_core": float(ari_core_kcore)},
        "recompute_agreement": recon,
        "name_mapping": {"source": "outputs/protocol/corr2_map.csv",
                         "positional_equal": bool(d["positional_equal"])},
        "limitations": [
            "2.csv 由作者在原始（未填补）数据上计算；本图直接使用 2.csv，不重新估计相关。",
            "重算 Spearman 用列中位数填补 73 个缺失，与 2.csv 的差异已量化（max/mean abs diff）。",
            "1.csv 的 calibrated==0 是 LOD/2 删失替代码；本脚本不使用 1.csv 数值作为浓度。",
            "模块划分来自单一固定相关矩阵；未做样本 bootstrap 的模块稳定性（列入限制）。",
            "tau_primary=0.30 只影响模块叙事，不参与 Top-3 选择。",
        ],
    }
    (outdir / "coexpression_graph.json").write_text(
        __import__("json").dumps(graph_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(__import__("json").dumps(graph_summary, ensure_ascii=False, indent=2)[:4000])
    print("\nmodule sizes:", sizes_new.tolist())
    print(sens.to_string(index=False))

    # ---------- 8) 实验契约 ----------
    try:
        from modeling_contract import emit_metrics, emit_output
        have = True
    except Exception:
        have = False
    if have and os.environ.get("MODELING_EXPERIMENT_DIR"):
        emit_metrics({
            "n_nodes": float(len(feat)),
            "n_edges_primary": float(len(iu)),
            "edge_density": float(len(iu) / len(iu_all)),
            "tau_primary": float(TAU_PRIMARY),
            "tau_fdr_equivalent": float(tau_fdr),
            "n_modules": float(k_mod),
            "n_modules_ge3": float((sizes_new >= 3).sum()),
            "modularity": float(Qmod),
            "ari_spectral_core_kcore": float(ari_core_kcore),
            "condition_number_abs_2csv": float(collin["diag_2csv"]["condition_number_abs"]),
            "lambda_min_2csv": float(collin["diag_2csv"]["lambda_min"]),
            "n_negative_eigenvalues_2csv": float(collin["diag_2csv"]["n_negative_eigenvalues"]),
            "rank_numerical_2csv": float(collin["diag_2csv"]["rank_numerical"]),
            "condition_number_recomputed": float(collin["diag_recomputed_from_1csv"]["condition_number"]),
            "n_pairs_abs_rho_gt_0.9": float(collin["diag_2csv"]["n_pairs_abs_rho_gt_0.9"]),
            "max_abs_diff_vs_recomputed": float(recon["max_abs_diff"]),
            "corr_vs_recomputed": float(recon["corr_2csv_vs_recomputed"]),
        })
        emit_output("graph_summary", graph_summary)


if __name__ == "__main__":
    main()
