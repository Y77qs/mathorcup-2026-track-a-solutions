"""Q1 证据汇总：模型对比（train-internal 选型）、误差分层、离群敏感性与图。

只读 experiments/ 的既有产物，不重新拟合模型；holdout 只用于报告选定模型。
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

OUT = L.OUT / "q1"
FIGD = L.FIG
OUT.mkdir(parents=True, exist_ok=True)
FIGD.mkdir(parents=True, exist_ok=True)

EXPS = ["EXP-0001", "EXP-0002", "EXP-0003"]
LABEL = {"EXP-0001": "B0 常数基线", "EXP-0002": "C1 多输出 Ridge", "EXP-0003": "C2 多输出 HistGBM"}


def load_metrics(eid):
    p = L.ROOT / "experiments" / eid / "metrics.json"
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    t50 = L.target_columns()
    rows, per_target = [], {}
    for eid in EXPS:
        m = load_metrics(eid)
        rows.append({
            "experimentId": eid, "model": LABEL[eid],
            "modelFamily": m.get("model_family"),
            "nFeatures": m.get("n_features", m.get("features_used", 0)),
            "oofMaeMean": m.get("oof_mae_mean"),
            "holdoutMaeMean": m.get("holdout_mae_mean"),
            "holdoutR2Mean": m.get("holdout_r2_mean"),
        })
        per_target[eid] = {t: {"oof": m.get(f"oof_mae__{t}"), "holdout": m.get(f"holdout_mae__{t}")}
                           for t in t50}

    # 选型只看训练内部 OOF（不看 holdout）
    ranked = sorted([r for r in rows if r["experimentId"] != "EXP-0001"],
                    key=lambda r: (r["oofMaeMean"] is None, r["oofMaeMean"]))
    selected = ranked[0]["experimentId"] if ranked else None
    base = next(r for r in rows if r["experimentId"] == "EXP-0001")
    cmp = {"table": rows, "selectionRule": "训练集 5 折 OOF MAE 最小（holdout 不参与选型）",
           "selected": selected, "baseline": "EXP-0001",
           "holdoutImprovementVsBaseline": {
               r["experimentId"]: (None if r["holdoutMaeMean"] is None else
                                   base["holdoutMaeMean"] - r["holdoutMaeMean"]) for r in rows},
           "labelNature": "mapped grade (transformed, non-original 0-6)"}
    (OUT / "model_comparison.json").write_text(json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 误差分析（用选定模型的 holdout 预测） ----------
    sel = selected or "EXP-0002"
    pred = pd.read_csv(L.ROOT / "experiments" / sel / "predictions_long.csv")
    df = pd.read_csv(L.CLEAN / "q1_mapped.csv")
    style = df.set_index("beer")["tasting_category_fine"].astype(str)
    pred["style"] = pred["beer"].map(style)
    per_dim = pred.groupby("target").apply(lambda g: float(np.mean(np.abs(g["y_true"] - g["y_pred"]))),
                                           include_groups=False).sort_values()
    by_style = pred.groupby("style").apply(lambda g: float(np.mean(np.abs(g["y_true"] - g["y_pred"]))),
                                           include_groups=False).sort_values()
    err = (pred["y_pred"] - pred["y_true"]).abs()
    obs = pred.groupby(["beer", "target"]).size()
    ea = {
        "experimentId": sel,
        "holdoutMaeMean": float(err.mean()),
        "perTargetMae": {k: float(v) for k, v in per_dim.items()},
        "perStyleMae": {k: float(v) for k, v in by_style.items()},
        "bestTargets": per_dim.head(5).to_dict(),
        "worstTargets": per_dim.tail(5).to_dict(),
        "errorQuantiles": {"p50": float(np.quantile(err, 0.5)), "p90": float(np.quantile(err, 0.9)),
                           "p99": float(np.quantile(err, 0.99)), "max": float(err.max())},
        "nPredRows": int(len(pred)), "nTargets": int(len(t50)),
        "labelNature": "mapped grade (transformed, non-original 0-6)",
    }
    (OUT / "error_analysis.json").write_text(json.dumps(ea, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 图 ----------
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(7, 3.6))
    names = [r["model"] for r in rows]
    x = np.arange(len(names))
    ax.bar(x - 0.18, [r["oofMaeMean"] for r in rows], 0.36, label="训练集 OOF MAE")
    ax.bar(x + 0.18, [r["holdoutMaeMean"] for r in rows], 0.36, label="留出 MAE")
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel("MAE (mapped grade)")
    ax.set_title("Q1 三模型：训练内部 OOF 与留出 MAE")
    ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(FIGD / "q1_model_comparison.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 3.4))
    order = per_dim.sort_values(ascending=False)
    ax.bar(range(len(order)), order.values, color="#4C72B0")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order.index, rotation=90, fontsize=6)
    ax.set_ylabel("MAE")
    ax.set_title(f"Q1 {LABEL[sel]}：50 维留出 MAE（降序）")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(FIGD / "q1_per_target_mae.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    g = pred[pred["target"] == "overall"]
    ax.scatter(g["y_true"], g["y_pred"], s=14, alpha=0.75)
    lim = [min(g["y_true"].min(), g["y_pred"].min()), max(g["y_true"].max(), g["y_pred"].max())]
    ax.plot(lim, lim, "k--", lw=1)
    ax.set_xlabel("真实 mapped grade"); ax.set_ylabel("预测 mapped grade")
    ax.set_title(f"Q1 overall 维度（{LABEL[sel]}）")
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(FIGD / "q1_overall_scatter.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 3.6))
    bs = by_style.sort_values(ascending=False).head(15)
    ax.bar(range(len(bs)), bs.values, color="#DD8452")
    ax.set_xticks(range(len(bs))); ax.set_xticklabels(bs.index, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("MAE"); ax.set_title("Q1 按风格的留出误差（Top 15 风格，误差最高）")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(FIGD / "q1_error_by_style.png", dpi=160); plt.close(fig)

    print(json.dumps({"selected": selected,
                      "holdoutMae": {r["experimentId"]: r["holdoutMaeMean"] for r in rows},
                      "oofMae": {r["experimentId"]: r["oofMaeMean"] for r in rows},
                      "figures": ["q1_model_comparison.png", "q1_per_target_mae.png",
                                  "q1_overall_scatter.png", "q1_error_by_style.png"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
