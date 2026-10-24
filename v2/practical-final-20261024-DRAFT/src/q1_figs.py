"""Q1 图形：模型比较 / 逐维 R² / 分级混淆 / 误差-风格 / 标定敏感性。

图内文字一律英文（无 CJK 字体），图注（caption）用中文，见 figures/q1_figures.json 与论文。
数据来源只读 outputs/q1/ 的真实产物，不手抄数字。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import common as C  # noqa: E402
import q1_data as D  # noqa: E402

plt = C.setup_matplotlib()
FIG = ROOT / "figures"
OUT = ROOT / "outputs" / "q1"
CAPS = {}


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / name
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}"


def fig_model_comparison():
    comp = pd.read_csv(OUT / "model_comparison.csv")
    comp = comp[comp.family != "B0_const"].copy()
    # 融合结果（若已跑）
    fus = OUT / "model_comparison_fusion.csv"
    if fus.exists():
        f = pd.read_csv(fus)
        comp = pd.concat([comp, f], ignore_index=True)
    comp = comp.sort_values("oof_r2_mean")
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    y = np.arange(len(comp))
    ax.barh(y, comp["oof_r2_mean"], xerr=comp["oof_r2_sd_over_repeats"], color="#4477AA",
            error_kw={"elinewidth": 1, "capsize": 2})
    ax.set_yticks(y)
    ax.set_yticklabels(comp["family"])
    ax.set_xlabel("OOF $R^2$ (mean of 50 dims), 15 folds")
    ax.set_title("Q1 model comparison (train-internal OOF, SPLIT-0002 train n=200)")
    for yi, v in zip(y, comp["oof_r2_mean"]):
        ax.text(v + 0.004, yi, f"{v:.3f}", va="center", fontsize=8)
    CAPS["fig_q1_model_comparison.png"] = (
        "图 Q1-1 六个模型族与四路等权融合的训练内 OOF 比较（5 折×3 重复=15 折，误差棒为 3 次重复间的标准差）。"
        "常数基线 R²≈0 作为下界；融合在 15/15 折一致优于最好的单模 ExtraTrees。")
    return _save(fig, "q1_model_comparison.png")


def fig_per_dim_r2():
    m = json.loads((OUT / "metrics_holdout.json").read_text())
    hd = m["holdout"]["r2_per_dim"]
    s = pd.Series(hd).sort_values()
    groups = [("A_", "#4477AA"), ("F_", "#66CCEE"), ("", "#AA3377")]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    cols = []
    for d in s.index:
        cols.append("#4477AA" if d.startswith("A_") else ("#66CCEE" if d.startswith("F_") else "#AA3377"))
    ax.bar(np.arange(len(s)), s.values, color=cols)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(np.arange(len(s)))
    ax.set_xticklabels(s.index, rotation=90, fontsize=6.5)
    ax.set_ylabel("Holdout $R^2$ per dimension")
    ax.set_title("Q1 per-dimension holdout $R^2$ (blue=Aroma, cyan=Flavour, magenta=Palate/Overall)")
    CAPS["fig_q1_per_dim_r2.png"] = (
        "图 Q1-2 锁定的四路融合模型在 50 个感官维度上的 holdout R²（SPLIT-0002 test n=50）。"
        "颜色区分 Aroma 15 维 / Flavour 15 维 / 口感-缺陷-总体 20 维；负值说明该维在 50 个留出样本上不可预测。")
    return _save(fig, "q1_per_dim_r2.png")


def fig_confusion():
    m = json.loads((OUT / "metrics_holdout.json").read_text())
    pred = pd.read_csv(OUT / "pred_z.csv")
    Y = C.load_targets().set_index("beer")[D.TARGET_DIMS]
    te_rows = pred[pred.is_oof == 0]
    te = te_rows.beer.to_numpy()
    gparams = D.load_grade_params("primary")
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6))
    for ax, pol, tag in zip(axes, ["P1_oav_anchor", "P2_range"], ["P1 physical anchor", "P2 range"]):
        M_ = D.confusion(Y.loc[te].values, te_rows[D.TARGET_DIMS].values, pol, gparams)
        im = ax.imshow(M_.values, cmap="Blues")
        ax.set_title(f"{tag}: QWK={m['holdout_calibration_by_policy'][pol]['qwk']:.3f}")
        ax.set_xlabel("predicted grade")
        ax.set_ylabel("reference grade (same rule on 4.csv)")
        ax.set_xticks(range(7)); ax.set_yticks(range(7))
        for i in range(7):
            for j in range(7):
                v = M_.values[i, j]
                if v:
                    ax.text(j, i, str(v), ha="center", va="center", fontsize=6,
                            color="white" if v > M_.values.max() * 0.5 else "black")
        fig.colorbar(im, ax=ax, fraction=0.046)
    CAPS["fig_q1_confusion.png"] = (
        "图 Q1-3 分级混淆（holdout 50 样本×50 维）。参照等级 = 用同一条标定规则作用于 4.csv 连续值得到的等级；"
        "真实 0–6 等级未知，故这张图只表示「标定口径下的一致性」，不是分级准确率。"
        "P1 为物理锚定主口径，P2 为极差敏感性口径。")
    return _save(fig, "q1_confusion.png")


def fig_error_by_style():
    p = OUT / "error_analysis.csv"
    ea = pd.read_csv(p)
    st = ea[ea.level == "style"].sort_values("r2")
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ax.barh(np.arange(len(st)), st["r2"], color="#228833")
    ax.set_yticks(np.arange(len(st)))
    ax.set_yticklabels([f"{g} (n={n})" for g, n in zip(st["group"], st["n"])], fontsize=7)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("OOF $R^2$ (mean over 50 dims)")
    ax.set_title("Q1 error by beer style (train OOF, n=200)")
    CAPS["fig_q1_error_by_style.png"] = (
        "图 Q1-4 按风格分层的训练内 OOF R²（每风格内 50 维 R² 的均值）。Faro/Brut/Scotch 等小类样本极少（n≤3），"
        "其数值只作描述，不构成风格级结论。")
    return _save(fig, "q1_error_by_style.png")


def fig_calibration():
    m = json.loads((OUT / "metrics_holdout.json").read_text())
    pols = ["P1_oav_anchor", "P2_range", "P3_quantile", "P4_sigma"]
    labels = ["P1 anchor", "P2 range", "P3 quantile", "P4 sigma"]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.4))
    w = 0.38
    x = np.arange(7)
    ax = axes[0]
    for k, (pol, lab) in enumerate(zip(pols[:2], labels[:2])):
        d = np.array(m["holdout_calibration_by_policy"][pol]["dist_pred"], float)
        d = d / d.sum()
        ax.bar(x + (k - 0.5) * w, d, width=w, label=lab)
    ax.set_xlabel("grade"); ax.set_ylabel("relative frequency")
    ax.set_title("Predicted grade distribution (holdout)")
    ax.legend(fontsize=7)
    ax = axes[1]
    q = [m["holdout_calibration_by_policy"][p]["qwk"] for p in pols]
    ax.bar(np.arange(4), q, color="#CC6677")
    ax.set_xticks(np.arange(4)); ax.set_xticklabels(labels, rotation=20, fontsize=7)
    ax.set_ylabel("QWK vs reference grades")
    ax.set_title("Calibration-policy sensitivity (not accuracy)")
    CAPS["fig_q1_calibration.png"] = (
        "图 Q1-5 左：holdout 上两套标定口径的预测等级分布；右：四套口径（P1 物理锚定 / P2 极差 / P3 分位 / P4 σ）"
        " 的 QWK。真实 0–6 等级未知，QWK 只作标定敏感性，不作准确性背书。")
    return _save(fig, "q1_calibration.png")


def fig_grade_map():
    pred = pd.read_csv(OUT / "pred_z.csv")
    g = pd.read_csv(OUT / "scores_0_6_P1.csv")
    cats = C.load_targets().set_index("beer")["tasting_category_fine"]
    order = pred.assign(cat=cats.loc[pred.beer].values).sort_values("cat").beer.to_numpy()
    G = g.set_index("beer").loc[order, D.TARGET_DIMS].to_numpy()
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    im = ax.imshow(G, aspect="auto", cmap="viridis", vmin=0, vmax=6)
    ax.set_xlabel("sensory dimension (50)")
    ax.set_ylabel("beer (sorted by style)")
    ax.set_title("Q1 0-6 grades (P1 physical anchor), 250 samples x 50 dimensions")
    fig.colorbar(im, ax=ax, fraction=0.03, label="grade")
    CAPS["fig_q1_grade_map.png"] = (
        "图 Q1-6 全 250 样本×50 维的 0–6 分级图（P1 物理锚定口径），样本按 tasting_category_fine 排序。"
        "训练 200 行来自 OOF 预测，test 50 行来自锁定模型；两段严格分开、不混用。")
    return _save(fig, "q1_grade_map.png")


def main():
    made = {}
    for fn in [fig_model_comparison, fig_per_dim_r2, fig_confusion,
               fig_error_by_style, fig_calibration, fig_grade_map]:
        try:
            made[fn.__name__] = fn()
            print("ok", fn.__name__, made[fn.__name__], flush=True)
        except Exception as exc:  # 缺产物时不静默跳过
            print(f"FAILED {fn.__name__}: {type(exc).__name__}: {exc}", flush=True)
    C.write_json({"figures": made, "captions_zh": CAPS}, "figures/q1_figures.json")
    print(json.dumps(made, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
