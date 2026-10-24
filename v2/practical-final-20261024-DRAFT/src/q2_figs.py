"""Q2-④ 论文图（英文图内文字 + 中文图注单独落盘）。

读取 q2_graph / q2_select / q2_stability 的产物，生成：
  q2_coexpression_graph.png   共表达图（CNM 模块着色，tau=0.30）
  q2_module_adjacency.png     按模块排序的相关矩阵（模块边界）
  q2_module_origin.png        模块 × 8.xlsx origin_paper 组成
  q2_top3_heatmap.png         50 维 × 候选化合物 的 Borda 平均秩热图（Top-3 框出）
  q2_bootstrap_freq.png       bootstrap 席位频率分布 + 各方法 ≥0.80 席位比例
  q2_prior_consistency.png    与 6.csv 独立先验的逐维 Spearman
  q2_collinearity.png         相关矩阵特征值谱 + |rho|>0.9 高共线簇
  q2_jaccard.png              跨方法 Top-3 Jaccard
图注（中文）写入 outputs/q2/figure_captions.json，供 model_deliver figure 登记。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import q2_common as Q  # noqa: E402
import emit as E  # noqa: E402

OUT = C.ROOT / "outputs" / "q2"
FIG = C.ROOT / "figures"
plt = C.setup_matplotlib()

CAPTIONS = {}


def _save(fig, name, caption):
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / f"q2_{name}.png"
    fig.savefig(p, dpi=160, bbox_inches="tight")
    plt.close(fig)
    CAPTIONS[f"q2_{name}.png"] = caption
    try:
        E.save_figure(fig, f"q2_{name}", area="q2")
    except Exception:
        pass
    return p


def fig_graph():
    edges = pd.read_csv(OUT / "coexpression_edges.csv")
    mods = pd.read_csv(OUT / "coexpression_modules.csv")
    feat = mods["compound"].tolist()
    idx = {c: i for i, c in enumerate(feat)}
    n = len(feat)
    W = np.zeros((n, n))
    for _, r in edges.iterrows():
        i, j = idx[r["node1"]], idx[r["node2"]]
        W[i, j] = W[j, i] = r["abs_rho"]
    pos = Q.spring_layout(W, seed=Q.SEED, iterations=120)
    labels = mods.set_index("compound").loc[feat, "module"].to_numpy()
    deg = (W > 0).sum(axis=1)
    k = int(labels.max()) + 1
    cmap = plt.get_cmap("tab10")
    fig, ax = plt.subplots(figsize=(9, 8))
    from matplotlib.collections import LineCollection
    segs = []
    for i in range(n):
        for j in range(i + 1, n):
            if W[i, j] > 0:
                segs.append([pos[i], pos[j]])
    ax.add_collection(LineCollection(segs, colors="grey", linewidths=0.25, alpha=0.18))
    ax.scatter(pos[:, 0], pos[:, 1], c=[cmap(l % 10) for l in labels],
               s=10 + 3 * deg, zorder=3, edgecolor="white", linewidth=0.4)
    lab = mods.drop_duplicates("module").set_index("module")["module_label"]
    for m in range(k):
        mem = np.where(labels == m)[0]
        if mem.size >= 3:
            cx, cy = pos[mem, 0].mean(), pos[mem, 1].mean()
            name = lab.get(m, f"module{m}")
            ax.text(cx, cy, name.split(":", 1)[-1], fontsize=11, weight="bold",
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.75, ec="none"))
    ax.set_title(f"Co-expression graph (|rho| >= 0.30, n={n} nodes, {len(edges)} edges, {k} modules)")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_aspect("equal")
    fig.tight_layout()
    return _save(fig, "coexpression_graph",
                 "图 Q2-1 化合物共表达图。节点=231 个化合物/理化指标（2.csv Spearman 秩相关，"
                 "经 corr2_map 映射到 1.csv 列名）；边=|ρ|≥0.30（3918 条）；颜色=加权贪心模块度"
                 "（CNM）模块；节点大小=度数。模块标签来自 8.xlsx origin_paper 富集（Fisher+BH）。")


def fig_adjacency():
    d = Q.load_q2()
    S = d["R2"].to_numpy(float)
    feat = d["feat_cols"]
    mods = pd.read_csv(OUT / "coexpression_modules.csv").set_index("compound")
    order = [c for m in sorted(mods["module"].unique()) for c in mods.index[mods["module"] == m]]
    oi = [feat.index(c) for c in order if c in feat]
    M = S[np.ix_(oi, oi)]
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Spearman rho")
    bounds = np.cumsum(mods.loc[order, "module"].value_counts().sort_index().values)[:-1]
    for b in bounds:
        ax.axhline(b - 0.5, color="k", lw=0.8, ls="--")
        ax.axvline(b - 0.5, color="k", lw=0.8, ls="--")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Correlation matrix ordered by CNM module (tau=0.30)")
    fig.tight_layout()
    return _save(fig, "module_adjacency",
                 "图 Q2-2 按模块排序的 231×231 Spearman 相关矩阵。虚线=模块边界；块内正相关"
                 "（红）结构说明模块不是单一尺度的伪聚类；跨模块负相关（蓝）对应发酵/酒花等对立轴。")


def fig_module_origin():
    mods = pd.read_csv(OUT / "coexpression_modules.csv")
    tab = mods.groupby(["module_label", "origin_paper"]).size().unstack(fill_value=0)
    tab = tab.loc[sort_df_index_by_size(mods), :]
    frac = tab.div(tab.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    im = ax.imshow(frac.to_numpy(), cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(tab.shape[1])); ax.set_xticklabels(tab.columns, rotation=45, ha="right")
    ax.set_yticks(range(tab.shape[0])); ax.set_yticklabels(tab.index)
    for i in range(tab.shape[0]):
        for j in range(tab.shape[1]):
            v = frac.iloc[i, j]
            if v > 0:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        fontsize=7, color="white" if v > 0.5 else "black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="within-module fraction")
    ax.set_title("Module composition by 8.xlsx origin_paper group")
    fig.tight_layout()
    return _save(fig, "module_origin",
                 "图 Q2-3 各模块的 origin_paper 类群组成（行=模块，列=类群，值=模块内占比）。"
                 "用于说明共表达模块与化学来源（Hops/Yeast/Malt/Spices 等）的一致性，"
                 "不是把类群当成选择证据。")


def sort_df_index_by_size(mods):
    sizes = mods.groupby("module_label").size()
    return sizes.sort_values(ascending=False).index.tolist()


def fig_top3_heatmap():
    t3 = pd.read_csv(OUT / "top3_per_dimension.csv")
    imp = pd.read_csv(OUT / "importance_matrix.csv", usecols=["dim", "compound", "mean_rank"])
    dims = list(dict.fromkeys(t3["dim"].tolist()))
    comps = list(dict.fromkeys(t3["compound"].tolist()))
    M = imp.pivot(index="dim", columns="compound", values="mean_rank").reindex(index=dims, columns=comps)
    fig, ax = plt.subplots(figsize=(max(10, 0.18 * len(comps)), 0.28 * len(dims) + 2))
    V = M.to_numpy(float)
    im = ax.imshow(np.clip(V, 1, 80), cmap="viridis_r", aspect="auto", vmin=1, vmax=80)
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01, label="mean Borda rank (1=best, clipped at 80)")
    for _, r in t3.iterrows():
        yi, xi = dims.index(r["dim"]), comps.index(r["compound"])
        ax.add_patch(plt.Rectangle((xi - 0.5, yi - 0.5), 1, 1, fill=False, ec="red", lw=1.0))
    ax.set_xticks(range(len(comps)))
    ax.set_xticklabels(comps, rotation=90, fontsize=5)
    ax.set_yticks(range(len(dims)))
    ax.set_yticklabels(dims, fontsize=6)
    ax.set_title("Final Top-3 per sensory dimension (4-method Borda mean rank; red = selected)")
    fig.tight_layout()
    return _save(fig, "top3_heatmap",
                 "图 Q2-4 50 个感官维度 × 候选化合物的四方法 Borda 平均秩热图（1=最重要，>80 截断）。"
                 "红框=最终 Top-3。行按 4.csv 维度顺序（Aroma 15 / Flavour 15 / 口感缺陷 20），"
                 "列=所有维度 Top-3 出现过的化合物。")


def fig_bootstrap():
    freq = pd.read_csv(OUT / "selection_frequency.csv")
    seats = pd.read_csv(OUT / "stability_seats.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    bins = np.linspace(0, 1, 21)
    for m, color in [("M1", "#1f77b4"), ("M4", "#2ca02c"), ("AGG", "#d62728")]:
        sub = freq[freq.method == m]
        axes[0].hist(sub["freq"], bins=bins, alpha=0.5, label=f"{m} (B={int(sub.B.iloc[0])})",
                     color=color, density=True)
    axes[0].axvline(Q.FREQ_THRESHOLD, color="k", ls="--", lw=1)
    axes[0].set_xlabel("bootstrap Top-3 seat frequency")
    axes[0].set_ylabel("density")
    axes[0].legend(fontsize=8)
    axes[0].set_title("Seat frequency distributions")
    methods = ["M1", "M2", "M3", "M4", "AGG"]
    frac = [(seats[f"freq_{m}"] >= Q.FREQ_THRESHOLD).mean() for m in methods]
    axes[1].bar(methods, frac, color=["#1f77b4", "#ff7f0e", "#9467bd", "#2ca02c", "#d62728"])
    axes[1].axhline(0.5, color="k", ls=":")
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel("share of final Top-3 seats with freq >= 0.80")
    axes[1].set_title("Stable-seat share by method")
    for i, v in enumerate(frac):
        axes[1].text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    fig.suptitle("Bootstrap stability (M1/M4: B=300; M2/M3/AGG: B=20)")
    fig.tight_layout()
    return _save(fig, "bootstrap_freq",
                 "图 Q2-5 Bootstrap 稳定性。左：各方法 Top-3 席位入选频率分布（虚线=预注册阈值 0.80）；"
                 "右：最终 Top-3 的 150 个席位中频率≥0.80 的比例。M1/M4 为 B=300，M2/M3/AGG 为 B=20"
                 "（协议允许的限时设置，证据强度更低，论文已如实声明）。")


def fig_prior():
    pc = pd.read_csv(OUT / "prior_consistency.csv")
    imp = pd.read_csv(OUT / "importance_matrix.csv", usecols=["dim", "compound", "mean_rank"])
    x6, rows, dim_to_col = None, None, None
    try:
        from q2_select import load_prior
        x6, rows, dim_to_col = load_prior()
        r6 = x6.rename(index=rows)
        r6 = r6[~r6.index.duplicated()]
    except Exception:
        r6 = None
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    if r6 is not None:
        xs, ys = [], []
        for dim, col in dim_to_col.items():
            if dim not in imp["dim"].unique():
                continue
            sub = imp[imp["dim"] == dim]
            common = [c for c in r6.index if c in set(sub["compound"])]
            a = np.abs(r6.loc[common, col].to_numpy(float))
            b = -sub.set_index("compound").loc[common, "mean_rank"].to_numpy(float)
            xs.append(a); ys.append(b)
        if xs:
            axes[0].scatter(np.concatenate(xs), np.concatenate(ys), s=6, alpha=0.35)
            axes[0].set_xlabel("|r| from 6.csv (independent prior)")
            axes[0].set_ylabel("-mean Borda rank (higher = more important)")
            axes[0].set_title(f"Prior agreement (per-dim Spearman mean = {pc['spearman_rho'].mean():.3f})")
    axes[1].hist(pc["spearman_rho"].dropna(), bins=20, color="#4c72b0", alpha=0.85)
    axes[1].axvline(0, color="k", ls="--", lw=1)
    axes[1].set_xlabel("per-dim Spearman rho (|r_6| vs aggregate importance)")
    axes[1].set_ylabel("number of dims")
    axes[1].set_title("Per-dimension prior consistency")
    fig.tight_layout()
    return _save(fig, "prior_consistency",
                 "图 Q2-6 与 6.csv 独立先验的一致性（6.csv 在选择完成后才读入，不参与 Top-3）。"
                 "左：44 个共有化合物的 |r_6| 与四方法聚合重要性散点（按维度合并）；"
                 "右：50 个维度的逐维 Spearman 分布（虚线=0）。")


def fig_collinearity():
    col = json.loads((OUT / "collinearity.json").read_text(encoding="utf-8"))
    sens = pd.read_csv(OUT / "graph_threshold_sensitivity.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for key, lab, color in [("diag_2csv", "2.csv (author)", "#1f77b4"),
                            ("diag_recomputed_from_1csv", "recomputed from 1.csv", "#d62728")]:
        v = np.array(col[key]["eigenvalues_top20"], float) if "eigenvalues_top20" in col[key] else None
        pass
    d1 = col["diag_2csv"]
    d2 = col["diag_recomputed_from_1csv"]
    v1 = np.array(d1["eigenvalues_top20"]); v2 = np.array(d2["eigenvalues_top20"])
    axes[0].semilogy(np.arange(1, len(v1) + 1), v1, "o-", label="2.csv (not PSD)")
    axes[0].semilogy(np.arange(1, len(v2) + 1), v2, "s-", label="recomputed (cond=9.4e4)")
    axes[0].set_xlabel("eigenvalue index")
    axes[0].set_ylabel("eigenvalue")
    axes[0].legend(fontsize=8)
    axes[0].set_title("Top-20 eigenvalues of 231x231 Spearman matrix")
    clusters = d1.get("collinear_clusters", [])
    sizes = [c["size"] for c in clusters] or [0]
    axes[1].bar(range(len(sizes)), sizes, color="#8c564b")
    axes[1].set_xlabel("high-collinearity cluster (|rho| > 0.9)")
    axes[1].set_ylabel("cluster size")
    axes[1].set_title("Collinear clusters (2.csv)")
    fig.tight_layout()
    return _save(fig, "collinearity",
                 "图 Q2-7 共线性诊断。左：231 维 Spearman 相关矩阵的前 20 个特征值；2.csv 有 5 个负特征值"
                 "（非 PSD、数值秩 226/231，逐对删失导致），重算矩阵条件数 ≈9.4×10⁴。"
                 "右：|ρ|>0.9 的高共线簇大小。这是单变量相关不足以定"关键因素"的原因。")


def fig_jaccard():
    jac = pd.read_csv(OUT / "method_jaccard.csv")
    pairs = [f"{Q.METHODS[a]}_{Q.METHODS[b]}" for a in range(4) for b in range(a + 1, 4)]
    means = [jac[jac["pair"] == p]["jaccard"].mean() for p in pairs]
    dim_mean = jac[jac["pair"].isin(pairs)].groupby("dim")["jaccard"].mean()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].bar(pairs, means, color="#55a868")
    axes[0].axhline(Q.JACCARD_THRESHOLD, color="k", ls="--", lw=1)
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("mean Top-3 Jaccard")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].set_title("Pairwise method agreement")
    for i, v in enumerate(means):
        axes[0].text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    axes[1].hist(dim_mean, bins=15, color="#4c72b0", alpha=0.85)
    axes[1].axvline(dim_mean.mean(), color="r", ls="--", lw=1)
    axes[1].axvline(Q.JACCARD_THRESHOLD, color="k", ls=":", lw=1)
    axes[1].set_xlabel("per-dim mean Jaccard across 6 method pairs")
    axes[1].set_ylabel("number of dims")
    axes[1].set_title(f"Per-dimension agreement (mean = {dim_mean.mean():.3f})")
    fig.tight_layout()
    return _save(fig, "jaccard",
                 "图 Q2-8 跨方法 Top-3 一致性。左：4 种方法两两 Jaccard 均值（虚线=预注册阈值 0.50）；"
                 "右：逐维 6 对 Jaccard 均值的分布。Jaccard 来自 method_top3.csv 的原始 Top-3 名单，可独立重算。")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for fn in [fig_graph, fig_adjacency, fig_module_origin, fig_top3_heatmap,
               fig_bootstrap, fig_prior, fig_collinearity, fig_jaccard]:
        try:
            p = fn()
            made.append(str(p.relative_to(C.ROOT)))
            print("made", p.name)
        except Exception as exc:  # 单图失败不吞掉其它图，但如实打印
            print(f"[WARN] {fn.__name__} failed: {exc}")
    meta = {"figures": made, "captions": CAPTIONS,
            "note": "图内文字英文；图注中文，供 model_deliver figure 登记使用。"}
    (OUT / "figure_captions.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    E.emit_output("figure_captions", Q.sanitize(meta), area="q2")
    print(json.dumps({"n_figures": len(made), "figures": made}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
