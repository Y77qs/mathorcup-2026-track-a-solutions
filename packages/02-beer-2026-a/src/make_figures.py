"""从已完成的实验产物生成论文图（只读 experiments/，不重新拟合）。

输出：
  figures/q1_feature_importance.png
  figures/q2_topk_stability.png
  figures/q2_method_jaccard.png
  figures/q3_energy_distance.png
  figures/q3_defect_oav.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L  # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIGD = L.FIG
EXP = L.ROOT / "experiments"


def load_outputs(eid):
    p = EXP / eid / "outputs.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_metrics(eid):
    p = EXP / eid / "metrics.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main() -> int:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    t50 = L.target_columns()
    made = []

    # ---------------- Q1 特征重要性（Ridge mean|beta|）
    o2 = load_outputs("EXP-0002")
    imp = o2.get("feature_importance", {})
    if imp and "note" not in imp:
        s = pd.Series(imp).sort_values(ascending=False).head(20)[::-1]
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.barh(range(len(s)), s.values, color="#4C72B0")
        ax.set_yticks(range(len(s))); ax.set_yticklabels(s.index, fontsize=8)
        ax.set_xlabel("mean |beta| across 50 targets（标准化特征）")
        ax.set_title("Q1 多输出 Ridge：Top-20 化合物系数幅值")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout(); fig.savefig(FIGD / "q1_feature_importance.png", dpi=160); plt.close(fig)
        made.append("q1_feature_importance.png")

    # ---------------- Q2 Top-3 稳定性
    o4 = load_outputs("EXP-0004")
    freq = o4.get("bootstrap_frequency", {})
    sets = o4.get("sets", {})
    if freq and sets:
        rows = []
        for t in t50:
            for c in sets[t]["methodA"]:
                rows.append({"target": t, "compound": c, "freq": freq.get(t, {}).get(c, 0.0)})
        df = pd.DataFrame(rows)
        fig, ax = plt.subplots(figsize=(11, 3.6))
        for k, t in enumerate(t50):
            sub = df[df.target == t]
            for r, (_, row) in enumerate(sub.iterrows()):
                ax.scatter(k, row["freq"], s=18, c=[plt.cm.viridis(r / 3.0)])
        ax.set_xticks(range(len(t50)))
        ax.set_xticklabels(t50, rotation=90, fontsize=6)
        ax.set_ylabel("bootstrap Top-3 入选频率（B=500）")
        ax.set_title("Q2 每个感官维度 Top-3 化合物的 bootstrap 稳定性")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout(); fig.savefig(FIGD / "q2_topk_stability.png", dpi=160); plt.close(fig)
        made.append("q2_topk_stability.png")

        m4 = load_metrics("EXP-0004")
        j_ab = [m4.get(f"jaccard_A_B__{t}") for t in t50]
        fig, ax = plt.subplots(figsize=(9, 3.2))
        ax.hist([x for x in j_ab if x is not None], bins=np.linspace(0, 1, 11), color="#DD8452")
        ax.axvline(float(np.nanmean(j_ab)), color="k", ls="--",
                   label=f"均值 {np.nanmean(j_ab):.2f}")
        ax.set_xlabel("逐维度 Top-3 Jaccard（Spearman vs Ridge）")
        ax.set_ylabel("维度数")
        ax.set_title("Q2 方法间 Top-3 一致性（Jaccard）分布")
        ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
        fig.tight_layout(); fig.savefig(FIGD / "q2_method_jaccard.png", dpi=160); plt.close(fig)
        made.append("q2_method_jaccard.png")

    # ---------------- Q3 能量距离
    o5 = load_outputs("EXP-0005")
    adapt = o5.get("adapt_report", {})
    if adapt:
        styles = list(adapt.keys())
        x = np.arange(len(styles)); w = 0.2
        base = [adapt[s]["energy_source_baseline_vs_eval"] for s in styles]
        raw = [adapt[s]["energy_transferred_raw_vs_eval"] for s in styles]
        con = [adapt[s]["energy_transferred_constrained_vs_eval"] for s in styles]
        gen = [adapt[s]["energy_generated_vs_eval"] for s in styles]
        fig, ax = plt.subplots(figsize=(7, 3.6))
        ax.bar(x - 1.5 * w, base, w, label="源风格未迁移（基线）")
        ax.bar(x - 0.5 * w, raw, w, label="迁移（不受约束）")
        ax.bar(x + 0.5 * w, con, w, label="迁移（缺陷约束）")
        ax.bar(x + 1.5 * w, gen, w, label="few-shot 生成")
        ax.set_xticks(x); ax.set_xticklabels(styles)
        ax.set_ylabel("energy distance（越小越接近留出样本）")
        ax.set_title("Q3 留出风格的生成/迁移与源风格基线")
        ax.legend(fontsize=7); ax.grid(axis="y", alpha=0.3)
        fig.tight_layout(); fig.savefig(FIGD / "q3_energy_distance.png", dpi=160); plt.close(fig)
        made.append("q3_energy_distance.png")

    # ---------------- Q3 缺陷 OAV
    checks = o5.get("defect_checks", [])
    if checks:
        df = pd.DataFrame(checks)
        df = df[df["median_oav_before"].notna()]
        if len(df):
            df["label_key"] = df["label"] + "|" + df["compound"]
            pivot_b = df[df.variant == "raw"].groupby("label_key")["median_oav_before"].median()
            pivot_r = df[df.variant == "raw"].groupby("label_key")["median_oav_after"].median()
            pivot_c = df[df.variant == "constrained"].groupby("label_key")["median_oav_after"].median()
            keys = list(pivot_b.index)
            x = np.arange(len(keys)); w = 0.26
            fig, ax = plt.subplots(figsize=(8, 3.6))
            ax.bar(x - w, pivot_b.values, w, label="迁移前")
            ax.bar(x, pivot_r.reindex(keys).values, w, label="迁移后（不受约束）")
            ax.bar(x + w, pivot_c.reindex(keys).values, w, label="迁移后（缺陷约束）")
            ax.set_yscale("log")
            ax.axhline(1.0, color="k", ls="--", lw=0.8, label="OAV=1 阈值")
            ax.set_xticks(x); ax.set_xticklabels(keys, rotation=30, ha="right", fontsize=7)
            ax.set_ylabel("median OAV（log 轴）")
            ax.set_title("Q3 缺陷化合物 OAV：迁移前后（含单位不确定性）")
            ax.legend(fontsize=7); ax.grid(axis="y", alpha=0.3)
            fig.tight_layout(); fig.savefig(FIGD / "q3_defect_oav.png", dpi=160); plt.close(fig)
            made.append("q3_defect_oav.png")

    print(json.dumps({"figures": made, "dir": str(FIGD)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
