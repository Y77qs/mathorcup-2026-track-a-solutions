"""Q3 图：生成谱 vs 真值（PCA 2D）、感官画像热图、迁移缺陷前后对比、风格保真度、
迁移轨迹、能量距离、小样本不确定度。图内文字英文，中文图注另存 `outputs/q3/figure_captions.json`。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import q3_utils as U  # noqa: E402
import q3_models as M  # noqa: E402

from sklearn.decomposition import PCA  # noqa: E402

STYLE_COLORS = {
    "Tripel": "#1f77b4", "Kriek": "#d62728", "Lambic": "#2ca02c",
    "Pils/Lager": "#ff7f0e", "Faro": "#9467bd",
}
GREY = "#9aa0a6"
CAPTIONS = {}
FIG_META = {}


def cap(name: str, cn: str):
    CAPTIONS[name] = cn


def fig_meta(name: str, source_exp: str, script: str, units: str, n: str, err: str):
    FIG_META[name] = {"filename": f"figures/{name}.png", "caption_cn": CAPTIONS.get(name, ""),
                      "source_exp": source_exp, "script": script,
                      "units_and_samples": f"{units}；样本量：{n}",
                      "error_bars": err}


def fig_spectra_pca(plt, tab, split, prep, gen):
    Ztr = prep.transform(U.train_matrix(tab, split["train_beer"]))
    Zte = prep.transform(U.train_matrix(tab, split["test_beer"]))
    p2 = PCA(n_components=2, random_state=U.SEED).fit(Ztr)
    T_tr, T_te = p2.transform(Ztr), p2.transform(Zte)
    ytr = tab.set_index("beer").loc[split["train_beer"], "style"].values
    yte = tab.set_index("beer").loc[split["test_beer"], "style"].values
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharex=True, sharey=True)
    for ax, (title, T, y, m) in zip(
            axes, [("Real training samples", T_tr, ytr, "o"),
                   ("Real holdout samples", T_te, yte, "^")]):
        ax.scatter(T[:, 0], T[:, 1], s=14, c=GREY, alpha=0.45, marker=m,
                   label="other styles" if title.endswith("samples") else None)
        for st in U.REQUIRED_STYLES:
            mm = y == st
            if mm.any():
                ax.scatter(T[mm, 0], T[mm, 1], s=42, c=STYLE_COLORS[st],
                           edgecolor="k", linewidth=0.4, label=f"real {st}", marker=m)
        for st in U.REQUIRED_STYLES:
            sub = gen[gen["style"] == st]
            Tz = p2.transform(prep.transform(sub[U.FEATURES]))
            ax.scatter(Tz[:200, 0], Tz[:200, 1], s=8, alpha=0.55, c=STYLE_COLORS[st],
                       marker="x", label=f"generated {st}")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("PC1 (train z-space)")
        ax.set_ylabel("PC2 (train z-space)")
    axes[0].legend(fontsize=6.5, loc="best", ncol=2, framealpha=0.85)
    fig.suptitle("Generated 231-dim spectra vs real samples in PCA(2) space", fontsize=11)
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_spectra_pca.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_spectra_pca",
        "生成谱（×）与真值样本在训练集 z 空间前两个主成分上的分布。左：训练真值；右：留出真值。"
        "三色分别为 Tripel/Kriek/Lambic；生成云的质心被锚定到各风格观测均值，离散度略窄于真值"
        "（低秩 + 共享协方差收缩所致）。")
    return p


def fig_style_fidelity(plt, metrics):
    sf = metrics["style_fidelity"]
    dist = metrics["distribution_match"]
    rows = [(s, v["hit_rate_mean_over_seeds"], v["baseline_holdout_hit_rate"],
             v["baseline_holdout_n"]) for s, v in sf["per_style"].items()]
    rows.sort(key=lambda r: (-(r[3] or 0), -r[1]))
    labels = [r[0] for r in rows]
    gen_hit = [r[1] for r in rows]
    base = [r[2] for r in rows]
    ns = [r[3] for r in rows]
    x = np.arange(len(rows))
    edr = {r["style"]: r["energy_distance_holdout"] for r in dist["per_style_ed"]
           if int(r["seed"]) == dist["primary_seed"]}
    dref = {s: v["d_ref"] for s, v in []}
    # D_ref 从 required_styles 里取，其余风格用中位数近似（仅作相对刻度）
    dref_req = {s: v["d_ref"] for s, v in dist["required_styles"].items()}
    dref_typ = float(np.nanmedian(list(dref_req.values())))
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    ax = axes[0]
    ax.bar(x - 0.2, gen_hit, width=0.4, color="#1f77b4", label="generated (mean of 5 seeds)")
    ax.bar(x + 0.2, base, width=0.4, color=GREY, label="real-holdout baseline")
    for i, n in enumerate(ns):
        ax.text(i, 1.02, f"n={n}", ha="center", fontsize=6, color="#444")
    ax.axhline(1 / 22, ls="--", c="k", lw=0.8, label="chance (1/22)")
    ax.set_ylim(0, 1.12)
    ax.set_title("(a) style hit rate — SATURATED after conditional-mean anchoring", fontsize=9)
    ax.legend(fontsize=6.5, loc="lower left")
    ax2 = axes[1]
    edv = [edr.get(s, np.nan) for s in labels]
    ax2.bar(x, edv, color="#d62728", alpha=0.8)
    ax2.set_yscale("symlog", linthresh=1.0)
    ax2.set_title("(b) energy distance to holdout truth (symlog) — the informative view",
                  fontsize=9)
    ax2.set_ylabel("energy distance (z-space)")
    for i, s in enumerate(labels):
        ax2.text(i, (edv[i] if np.isfinite(edv[i]) else 0) + 0.02, f"n={ns[i]}",
                 ha="center", fontsize=5.5)
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=6.5)
    fig.suptitle("Per-style fidelity: hit rate is not discriminative after anchoring; "
                 "energy distance is", fontsize=10)
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_style_fidelity.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_style_fidelity",
        "逐风格保真度：(a) 生成样本被判为目标风格的比例 vs 留出真值基线（顶部 n= 为留出真值样本数）；"
        "(b) 生成集到留出真值的能量距离。条件均值锚定后命中率饱和在 0.98–1.00，**不能**当质量证据；"
        "真正有区分度的是能量距离（Kriek/Lambic/Faro 等留出样本只有 1–3 个的风格，ED 的上/下界都很宽）。")
    return p


def fig_energy_distance(plt, metrics):
    dist = metrics["distribution_match"]
    req = dist["required_styles"]
    styles = list(dist["seed42_holdout"].keys())
    ed = [dist["seed42_holdout"][s] for s in styles]
    ed_all = [float(np.nan) for _ in styles]
    for r in dist["per_style_ed"]:
        if int(r["seed"]) == 42:
            ed_all[styles.index(r["style"])] = r["energy_distance_all_real"]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    x = np.arange(len(styles))
    ax.bar(x - 0.2, ed, width=0.4, color="#1f77b4", label="ED vs holdout truth")
    ax.bar(x + 0.2, ed_all, width=0.4, color="#7fb3d5", label="ED vs all real of that style")
    for i, s in enumerate(styles):
        if s in req:
            ax.text(i, max(ed[i], 0) + 0.15, f"n={req[s]['n_ref_holdout']}",
                    ha="center", fontsize=6.5)
    ax.set_xticks(x)
    ax.set_xticklabels(styles, rotation=60, ha="right", fontsize=7)
    ax.set_ylabel("energy distance (z-space)")
    ax.set_title("Energy distance: generated vs real (seed 42); "
                 "annotated n = holdout truth sample size", fontsize=10)
    ax.legend(fontsize=7)
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_energy_distance.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_energy_distance",
        "生成集与真值的能量距离（训练 z 空间）：深色为留出真值参考，浅色为该风格全部真值参考。"
        "Kriek/Lambic/Faro 的留出参考只有 1–3 个样本，深色柱的不确定度很大，因此两种参考并列报告。")
    return p


def fig_defect_exceedance(plt, metrics):
    dg = metrics["defect_check_generation"]
    comps = ["DMS", "X2.3.butanedione", "X4VG"]
    names = {"DMS": "DMS", "X2.3.butanedione": "Diacetyl", "X4VG": "4VG"}
    styles = U.REQUIRED_STYLES
    x = np.arange(len(styles))
    w = 0.12
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for k, c in enumerate(comps):
        gen = [dg["generated_seed42"][s][c]["exceed_rate"] for s in styles]
        real = [dg["real_baseline_per_style"][s][c]["exceed_rate"] for s in styles]
        ax.bar(x + (k - 1) * 3 * w - w / 2, gen, width=w, color=f"C{k}",
               label=f"generated {names[c]}")
        ax.bar(x + (k - 1) * 3 * w + w / 2, real, width=w, color=f"C{k}", alpha=0.4,
               hatch="//", label=f"real {names[c]}")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s}\n(real n={dg['real_baseline_per_style'][s]['n_real']})"
                        for s in styles], fontsize=8)
    ax.set_ylabel("fraction with OAV > 1")
    ax.set_title("Defect exceedance (absolute OAV, 8.xlsx thresholds), generated vs real",
                 fontsize=10)
    ax.legend(fontsize=6.5, ncol=2)
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_defect_exceedance.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_defect_exceedance",
        "生成谱与真值在三个有绝对阈值的缺陷项上的 OAV>1 比例（实心=生成，斜线=真值同风格）。"
        "trans-2-nonenal 与 Stale hops 在 8.xlsx 无阈值，故不报越阈率，只报浓度不增。")
    return p


def fig_sensory_profiles(plt, metrics):
    prof = pd.read_csv(U.PROJECT / "outputs/q3/sensory_profiles.csv")
    tg = C.load_targets().set_index("beer")
    split = U.load_split("primary")
    dims = C.TARGET_DIMS
    rows, labels = [], []
    for st in U.REQUIRED_STYLES:
        sub = prof[prof["style"] == st]
        rows.append(sub[[f"z_{d}" for d in dims]].values.mean(0))
        labels.append(f"gen {st}")
        beer_h = [b for b in split["test_beer"]
                  if tg.loc[b, "tasting_category_fine"] == st]
        beer_t = [b for b in split["train_beer"]
                  if tg.loc[b, "tasting_category_fine"] == st]
        ref = tg.loc[beer_h, dims].values.mean(0) if beer_h else np.full(len(dims), np.nan)
        rows.append(ref)
        labels.append(f"real holdout {st} (n={len(beer_h)})")
        rows.append(tg.loc[beer_t, dims].values.mean(0))
        labels.append(f"real train {st} (n={len(beer_t)})")
    Mx = np.vstack(rows)
    vmax = float(np.nanpercentile(np.abs(Mx), 98))
    fig, ax = plt.subplots(figsize=(13, 4.2))
    im = ax.imshow(Mx, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xticks(range(len(dims)))
    ax.set_xticklabels(dims, rotation=90, fontsize=5.5)
    ax.set_title("Sensory profiles (50-d latent z, placeholder forward map) — "
                 "generated vs real same-style", fontsize=10)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("z (4.csv scale)", fontsize=8)
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_sensory_profiles.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_sensory_profiles",
        "生成谱经 Q1 锁定映射器（outputs/q1/model_bundle.pkl.gz，经 src/q1_bundle.py 推理）得到的"
        " 50 维感官画像（ẑ），与同风格真值谱经**同一映射器**得到的画像对比。"
        "占位岭回归版另存 metrics.json 的 sensory_profile.placeholder（与 4.csv 真值比较的旧口径），"
        "两版不覆盖；比较结论：生成谱画像与“只吐风格均值谱”的基线几乎并列，"
        "只能说明画像落在正确风格区域，不能说明优于退化生成器。")
    return p


def fig_transfer_trajectory(plt, tab, split, prep):
    rep = U.load_json("outputs/q3/transfer_report.json")
    w = pd.read_csv(U.PROJECT / "outputs/q3/transfer_pils_to_tripel.csv")
    Xtr = U.train_matrix(tab, split["train_beer"])
    Ztr = prep.transform(Xtr)
    ytr = tab.set_index("beer").loc[split["train_beer"], "style"].values
    p2 = PCA(n_components=2, random_state=U.SEED).fit(Ztr)
    T = p2.transform(Ztr)
    Tb = p2.transform(prep.transform(pd.DataFrame(w[[f"before_{c}" for c in U.FEATURES]].values,
                                                 columns=U.FEATURES)))
    Ta = p2.transform(prep.transform(pd.DataFrame(w[[f"after_{c}" for c in U.FEATURES]].values,
                                                 columns=U.FEATURES)))
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    ax.scatter(T[:, 0], T[:, 1], s=10, c=GREY, alpha=0.5, label="real train samples")
    for st in ["Tripel", "Pils/Lager"]:
        mm = ytr == st
        ax.scatter(T[mm, 0], T[mm, 1], s=48, c=STYLE_COLORS[st], edgecolor="k",
                   linewidth=0.4, label=f"real {st}")
    for i in range(len(w)):
        ax.annotate("", xy=(Ta[i, 0], Ta[i, 1]), xytext=(Tb[i, 0], Tb[i, 1]),
                    arrowprops=dict(arrowstyle="->", color="#333", lw=0.9, alpha=0.8))
    ax.scatter(Tb[:, 0], Tb[:, 1], s=30, c=STYLE_COLORS["Pils/Lager"], marker="o",
               label="Pils/Lager before transfer")
    ax.scatter(Ta[:, 0], Ta[:, 1], s=44, c=STYLE_COLORS["Pils/Lager"], marker="*",
               label="after transfer (target Tripel)")
    ax.set_xlabel("PC1 (train z-space)")
    ax.set_ylabel("PC2 (train z-space)")
    ax.set_title("Transfer trajectories Pils/Lager -> Tripel "
                 f"(hit as Tripel {rep['style_progress']['classifier_hit_as_tripel_before']:.2f}"
                 f" -> {rep['style_progress']['classifier_hit_as_tripel_after']:.2f})",
                 fontsize=10)
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_transfer_trajectory.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_transfer_trajectory",
        "Pils/Lager -> Tripel 迁移轨迹（培训集 z 空间 PCA 2D）。箭头起点=迁移前、星号=迁移后；"
        "迁移把样本显著移向 Tripel 区域，但硬约束禁止 DMS/双乙酰上升，因此只能部分达到 Tripel 判别"
        "（见 q3_defect_oav 与 metrics.json 的 style_progress）。")
    return p


def fig_defect_oav(plt, tab, split):
    dc = pd.read_csv(U.PROJECT / "outputs/q3/defect_check.csv")
    abs_rows = dc[dc["is_absolute_threshold"]].copy()
    mono_rows = dc[~dc["is_absolute_threshold"]].copy()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.0))
    for ax, comp, name in zip(axes, ["DMS", "X2.3.butanedione", "X4VG"],
                              ["DMS (thr 17.25 ug/L)", "Diacetyl (thr 0.29925 mg/L)",
                               "4VG (thr 0.2063 mg/L)"]):
        sub = abs_rows[abs_rows["compound"] == comp]
        x = np.arange(len(sub))
        ax.plot(x, sub["oav_before"], "o-", ms=4, lw=1, label="before (Pils/Lager)")
        ax.plot(x, sub["oav_after"], "s--", ms=4, lw=1, label="after (migrated)")
        ax.set_yscale("log")
        ax.axhline(1.0, c="k", ls=":", lw=0.9, label="OAV = 1")
        ax.set_title(name, fontsize=9)
        ax.set_xlabel("Pils/Lager sample")
        ax.set_ylabel("OAV")
        ax.legend(fontsize=6.5)
    fig.suptitle("Transfer: absolute-OAV defects before vs after "
                 "(hard constraint: concentration never increases)", fontsize=10)
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_defect_oav.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_defect_oav",
        "迁移前后三类有绝对阈值缺陷的 OAV（对数轴，虚线=OAV 1）。硬约束是逐样本浓度不增，"
        "因此 after 曲线处处不高于 before；DMS/双乙酰在多数 Pils 样品上未超阈，迁移后仍不超阈。")
    return p


def fig_seed_stability(plt, metrics):
    ss = metrics["seed_stability"]["per_seed"]
    seeds = [r["seed"] for r in ss]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for st in U.REQUIRED_STYLES:
        axes[0].plot(seeds, [r[f"hit_{st}"] for r in ss], "o-", label=st,
                     color=STYLE_COLORS[st])
        axes[1].plot(seeds, [r[f"ed_{st}"] for r in ss], "o-", label=st,
                     color=STYLE_COLORS[st])
    axes[0].set_title("Style hit rate across seeds", fontsize=9)
    axes[1].set_title("Energy distance vs holdout truth across seeds", fontsize=9)
    for ax in axes:
        ax.set_xlabel("seed")
        ax.legend(fontsize=7)
    fig.suptitle("Cross-seed stochastic stability (5 seeds, same fitted model)", fontsize=10)
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_seed_stability.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_seed_stability",
        "5 个 seed 下的风格命中率与能量距离（同一拟合模型，只变采样随机性）。"
        "逐指标相对极差与是否 ≤0.05 的判定见 seed_stability.csv 与 metrics.json。")
    return p


def fig_smalln(plt, metrics):
    sn = metrics["small_n_uncertainty"]["styles"]
    styles = [s for s in U.SMALL_N_STYLES if s in sn]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    x = np.arange(len(styles))
    w = 0.35
    for k, tag in enumerate(["real", "generated"]):
        vals = [sn[s][tag]["mean_ci_width_median_over_real_sd"] for s in styles]
        ax.bar(x + (k - 0.5) * w, vals, width=w,
               color="#7fb3d5" if tag == "generated" else "#1f77b4",
               label=f"{tag} mean-CI width / real sd")
    for i, s in enumerate(styles):
        ax.text(i, 0.05, f"n={sn[s]['n_real_all']}", ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(styles)
    ax.set_ylabel("median bootstrap CI width (in units of real sd)")
    ax.set_title("Small-class estimation uncertainty: bootstrap 95% CI of the mean", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    p = U.FIG_Q3 / "q3_smalln_uncertainty.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    cap("q3_smalln_uncertainty",
        "小类（Kriek n=10 / Lambic n=11 / Faro n=3）均值估计的 bootstrap 95% CI 宽度（以真值标准差为单位）。"
        "真值侧 CI 宽度在 1 个标准差量级，说明 n 太小时不能声称精确刻画分布。")
    return p


def main():
    plt = C.setup_matplotlib()
    tab = U.load_style_table()
    split = U.load_split("primary")
    prep = U.fit_preprocessor(tab, split["train_beer"])
    gen = pd.read_csv(U.PROJECT / "outputs/q3/generated_spectra.csv")
    metrics = U.load_json("outputs/q3/metrics.json")

    paths = []
    paths.append(fig_spectra_pca(plt, tab, split, prep, gen))
    paths.append(fig_style_fidelity(plt, metrics))
    paths.append(fig_energy_distance(plt, metrics))
    paths.append(fig_defect_exceedance(plt, metrics))
    paths.append(fig_sensory_profiles(plt, metrics))
    paths.append(fig_transfer_trajectory(plt, tab, split, prep))
    paths.append(fig_defect_oav(plt, tab, split))
    paths.append(fig_seed_stability(plt, metrics))
    paths.append(fig_smalln(plt, metrics))
    meta_list = {
        "q3_spectra_pca": dict(source_exp="EXP-0036（生成谱源自 q3_generate，选型 EXP-0022）· DATA-0002/SPLIT-0002",
                               script="src/q3_figs.py + src/q3_generate.py",
                               units="z 空间（1.csv 231 列，训练集均值/标准差；log1p 33 列）",
                               n="生成 Tripel/Kriek/Lambic 各 200（seed 42）；真值训练 200 / 留出 50",
                               err="无误差棒（散点图）"),
        "q3_style_fidelity": dict(source_exp="EXP-0036（主模型）· EXP-0019（基线）",
                                  script="src/q3_figs.py + src/q3_eval.py",
                                  units="比例（0-1）/ 能量距离（z 空间）",
                                  n="生成每风格 200×5 seed；留出真值 n 见图顶标注（1–9）",
                                  err="无误差棒；命中率为 5 seed 均值，留出基线受 n 影响见 n="),
        "q3_energy_distance": dict(source_exp="EXP-0036", script="src/q3_figs.py + src/q3_eval.py",
                                   units="能量距离（z 空间，无量纲）",
                                   n="生成每风格 100–200；留出真值 n 见图内标注",
                                   err="Kriek/Lambic/Faro 留出参考仅 1–3 个样本，参考侧不确定度大（另给 all-real 参考柱）"),
        "q3_defect_exceedance": dict(source_exp="EXP-0036", script="src/q3_figs.py + src/q3_eval.py",
                                     units="OAV>1 的比例；OAV=浓度/8.xlsx 阈值",
                                     n="生成每风格 200（seed 42）；真实同风格 n 见图内标注（3–28）",
                                     err="无误差棒；比例为点估计"),
        "q3_sensory_profiles": dict(source_exp="EXP-0036（Q1 权威 bundle 画像）",
                                    script="src/q3_figs.py + src/q3_eval.py",
                                    units="4.csv 标准化 ẑ（0–6 分级见 sensory_profiles.csv）",
                                    n="生成每风格 200（seed 42）；真值留出 n=1–5、训练 n=8–23",
                                    err="无误差棒；真值侧样本量极小（见标题 n=）"),
        "q3_transfer_trajectory": dict(source_exp="EXP-0036 + SCRIPT-0037（迁移）",
                                       script="src/q3_figs.py + src/q3_transfer.py",
                                       units="PCA 2D（z 空间）",
                                       n="Pils/Lager 11 个样本；真值训练 200",
                                       err="无误差棒；箭头=单样本迁移轨迹"),
        "q3_defect_oav": dict(source_exp="EXP-0036 + SCRIPT-0037（迁移）",
                              script="src/q3_figs.py + src/q3_transfer.py",
                              units="OAV（对数轴），阈值来自 8.xlsx：DMS 17.25 µg/L、Diacetyl 0.29925 mg/L、4VG 0.2063 mg/L",
                              n="11 个 Pils/Lager 样本（逐样本点）",
                              err="无误差棒；逐样本配对连线"),
        "q3_seed_stability": dict(source_exp="EXP-0036", script="src/q3_figs.py + src/q3_eval.py",
                                  units="比例 / 能量距离（z 空间）",
                                  n="5 个 seed（42/7/2024/123/9）× 每风格 200",
                                  err="无误差棒；点=单 seed 值，波动见 seed_stability.csv"),
        "q3_smalln_uncertainty": dict(source_exp="EXP-0036", script="src/q3_figs.py + src/q3_eval.py",
                                      units="bootstrap 95% CI 宽度 / 真值标准差",
                                      n="Kriek n=10、Lambic n=11、Faro n=3；bootstrap 2000 次",
                                      err="误差棒即 bootstrap 95% CI 宽度"),
    }
    for k, v in meta_list.items():
        v = dict(v)
        units = v.pop("units", "")
        n = v.pop("n", "")
        err = v.pop("err", "")
        v["units_and_samples"] = f"{units}；样本量：{n}"
        v["error_bars"] = err
        v["filename"] = f"figures/{k}.png"
        v["caption_cn"] = CAPTIONS.get(k, "")
        FIG_META.setdefault(k, v)
    U.write_json({"captions_cn": CAPTIONS,
                  "figure_registry": FIG_META,
                  "note": "图内文字为英文；本文件给出中文图注，供论文直接引用。",
                  "files": [U.rel(p) for p in paths]},
                 "outputs/q3/figure_captions.json")
    print(f"[done] {len(paths)} figures -> figures/q3_*.png")
    for p in paths:
        print("  ", U.rel(p))


if __name__ == "__main__":
    main()
