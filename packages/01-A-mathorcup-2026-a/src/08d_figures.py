"""生成 Q1/Q2 的交付图（从已登记实验指标与已有产物直接作图，不重算模型）。

图内文字用英文（环境无 CJK 字体），图注在注册 figure 时用中文。

产物：
  figures/q1_per_dim_r2.png      : EXP-0025 逐维留出 R²（与 EXP-0015 基线对比）
  figures/q1_model_comparison.png: Q1 各族 OOF R²（来自 model_comparison.csv，若存在）
  figures/q2_method_agreement.png: 四方法两两 Top-3 Jaccard（来自 method_jaccard.csv）
  figures/q2_top3_heatmap.png    : 若干代表性维度的 Borda Top-3 重要性
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

plt = C.setup_matplotlib()


def exp_metrics(eid):
    p = C.ROOT / "experiments" / eid / "metrics.json"
    return json.loads(p.read_text())


def fig_q1_per_dim():
    cand = exp_metrics("EXP-0025")
    base = exp_metrics("EXP-0015")
    dims = C.TARGET_DIMS
    y = np.array([cand.get(f"holdout_r2__{d}", np.nan) for d in dims])
    b = np.array([base.get(f"holdout_r2__{d}", np.nan) for d in dims])
    order = np.argsort(y)[::-1]
    fig, ax = plt.subplots(2, 1, figsize=(11, 7.2), gridspec_kw={"height_ratios": [2.2, 1]})
    x = np.arange(len(dims))
    ax[0].bar(x, y[order], color="#2b6cb0", label="Q1 ensemble (EXP-0025)")
    ax[0].axhline(0, color="k", lw=0.8)
    ax[0].set_xticks(x)
    ax[0].set_xticklabels([dims[i] for i in order], rotation=90, fontsize=7)
    ax[0].set_ylabel("Holdout $R^2$ (per dimension)")
    ax[0].set_title(f"Q1 per-dimension holdout $R^2$ (50 dims, mean={np.nanmean(y):.4f})")
    ax[0].legend(loc="upper right", fontsize=8)
    ax[1].bar(x, b[order], color="#a0aec0")
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set_xticks(x)
    ax[1].set_xticklabels([dims[i] for i in order], rotation=90, fontsize=7)
    ax[1].set_ylabel("Holdout $R^2$")
    ax[1].set_title(f"Constant baseline EXP-0015 (mean={np.nanmean(b):.4f})")
    fig.tight_layout()
    p = C.FIG / "q1_per_dim_r2.png"
    fig.savefig(p, bbox_inches="tight", dpi=160)
    plt.close(fig)
    return p, {"n_dims": len(dims), "mean_candidate": float(np.nanmean(y)),
               "mean_baseline": float(np.nanmean(b)),
               "n_positive": int(np.sum(y > 0))}


def fig_q1_compare():
    p = C.ROOT / "outputs/q1/model_comparison.csv"
    if not p.exists():
        return None, None
    d = pd.read_csv(p)
    col = "oof_r2_mean" if "oof_r2_mean" in d.columns else d.columns[1]
    fam = d.columns[0]
    d = d.sort_values(col)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.barh(d[fam].astype(str), d[col], color="#2f855a")
    ax.set_xlabel("Training-internal OOF $R^2$ (mean over 50 dims)")
    ax.set_title("Q1 candidate families (OOF, selection set only)")
    for i, v in enumerate(d[col]):
        ax.text(v + (0.002 if v >= 0 else -0.002), i, f"{v:.3f}",
                va="center", ha="left" if v >= 0 else "right", fontsize=8)
    fig.tight_layout()
    q = C.FIG / "q1_model_comparison.png"
    fig.savefig(q, bbox_inches="tight", dpi=160)
    plt.close(fig)
    return q, {"n_families": int(len(d)), "best": str(d.iloc[-1][fam]),
               "best_oof_r2": float(d.iloc[-1][col])}


def fig_q2_jaccard():
    p = C.ROOT / "outputs/q2/method_jaccard.csv"
    if not p.exists():
        return None, None
    d = pd.read_csv(p)
    meth = ["M1", "M2", "M3", "M4"]
    M = np.full((4, 4), np.nan)
    for _, r in d.iterrows():
        a, b = str(r["setA"]), str(r["setB"])
        if a in meth and b in meth:
            M[meth.index(a), meth.index(b)] = float(r["jaccard"])
            M[meth.index(b), meth.index(a)] = float(r["jaccard"])
    np.fill_diagonal(M, 1.0)
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    im = ax.imshow(M, cmap="YlOrRd", vmin=0, vmax=0.6)
    ax.set_xticks(range(4)); ax.set_xticklabels(meth)
    ax.set_yticks(range(4)); ax.set_yticklabels(meth)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{M[i, j]:.3f}", ha="center", va="center", fontsize=9)
    ax.set_title("Q2 Top-3 Jaccard between methods (mean per dim)")
    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()
    q = C.FIG / "q2_method_agreement.png"
    fig.savefig(q, bbox_inches="tight", dpi=160)
    plt.close(fig)
    return q, {"mean_offdiag": float(np.nanmean(M[~np.eye(4, dtype=bool)])),
               "max_offdiag": float(np.nanmax(M[~np.eye(4, dtype=bool)]))}


def fig_q2_top3():
    imp = C.ROOT / "outputs/q2/importance_matrix.csv"
    top = C.ROOT / "outputs/q2/method_top3.csv"
    if not imp.exists() or not top.exists():
        return None, None
    I = pd.read_csv(imp)
    t3 = pd.read_csv(top)
    dim_sel = ["A_hops_all", "A_hops_citrus", "F_esters_all", "A_esters_ethac",
               "bitternes", "alcohol", "acidity", "lactic", "dms", "diacetyl"]
    fig, axes = plt.subplots(2, 5, figsize=(16, 6.2))
    used = 0
    for ax, dim in zip(axes.ravel(), dim_sel):
        sub = t3[(t3["dim"] == dim)]
        if sub.empty:
            ax.axis("off"); continue
        # 用 4 方法的平均归一化分数作为共识强度
        g = sub.groupby("compound")["score"].mean().sort_values(ascending=False).head(3)
        comps = g.index.astype(str).tolist()
        vals = g.values.tolist()
        ax.barh(range(len(comps))[::-1], vals, color="#805ad5")
        ax.set_yticks(range(len(comps))[::-1])
        ax.set_yticklabels(comps, fontsize=7)
        ax.set_title(dim, fontsize=8)
        ax.tick_params(axis="x", labelsize=6)
        used += 1
    fig.suptitle("Q2 Borda-aggregated Top-3 compounds (consensus; cross-method Jaccard is low)", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    q = C.FIG / "q2_top3_heatmap.png"
    fig.savefig(q, bbox_inches="tight", dpi=160)
    plt.close(fig)
    return q, {"dims_plotted": used}


def main():
    out = {}
    for name, fn in [("q1_per_dim", fig_q1_per_dim), ("q1_compare", fig_q1_compare),
                     ("q2_jaccard", fig_q2_jaccard), ("q2_top3", fig_q2_top3)]:
        try:
            p, meta = fn()
            out[name] = {"path": str(p) if p else None, "meta": meta}
            print(f"[fig] {name}: {p} {meta}")
        except Exception as e:  # noqa
            out[name] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[fig] {name} FAILED: {e}")
    C.write_json(out, "outputs/protocol/figures_built.json")


if __name__ == "__main__":
    main()
