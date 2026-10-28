# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""make_paper_figures.py — the paper's figure set, drawn ONLY from registered experiment artifacts.

WHY A SEPARATE SCRIPT. The figures that the experiments produce serve the experiments; the ones the
paper needs must (a) come from the FINAL selected experiments, (b) cover the delivered 250x50 grading
table, and (c) have a caption that matches what is actually drawn. Every panel below is computed from a
registered artifact (metrics.json / outputs.json / a registered CSV), the input paths are recorded by
`modeling_deliver {action:"figure", scriptFile:"src/make_paper_figures.py", experimentId:...}`, and in
figure text is English (the machine has no CJK font); the captions are Chinese and live in the ledger.

Run from the project root:
    python src/make_paper_figures.py

Outputs (figures/):
    q1_component_mae.png     Q1 OOF/test MAE of the three components and the fused model  (EXP-0004)
    q1_fusion_weights.png    Q1 simplex weights, global and by sensory group             (EXP-0004)
    q1_per_target.png        Q1 per-target Skill (fused vs training median)              (EXP-0004)
    q1_cv_grid.png           Q1 training-internal 5-fold CV grid, 54 cells               (EXP-0003)
    q1_grades_all.png        Q1 delivered 250x50 0-6 grading table                       (EXP-0026)
    q2_bootstrap_pi.png      Q2 bootstrap selection frequency pi, final sets             (EXP-0029)
    q2_method_jaccard.png    Q2 pairwise Top-3 Jaccard between the four methods          (EXP-0029)
    q2_modules.png           Q2 attachment-network modules at tau=0.4/0.5/0.6            (EXP-0029)
    q3_energy_by_style.png   Q3 per-style normalised energy distance                     (EXP-0033)
    q3_defect_exceedance.png Q3 defect-exceedance: real vs unconstrained vs constrained  (EXP-0033)
    q3_transfer_scenarios.png Q3 four transfer scenarios: non-worsening and strict rates (EXP-0033)
    q3_pareto.png            Q3 lambda/eta Pareto front                                  (EXP-0033)
    q3_profile.png           Q3 sensory-profile recovery per style                       (EXP-0033)
"""

import csv
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"

# EXPLICIT BINDING (v5.1 / R00-R03): every figure below names the experiment it plots.
# The caller must pass MODELING_EXPERIMENT_IDS; the historical literals are NOT a
# fallback, so a rerun cannot silently draw old runs under new labels.
from v6_experiment_ids import resolve as _resolve_experiments  # noqa: E402

_IDS = _resolve_experiments(
    "make_paper_figures",
    ["q1_grades", "q1_candidate", "q1_graph", "q2_candidate", "q3_candidate"],
)
BLUE = "#2b6cb0"
GREY = "#a0aec0"
ORANGE = "#c05621"
GREEN = "#2f855a"
RED = "#c53030"

plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
                     "figure.dpi": 160, "savefig.bbox": "tight"})


def jload(rel):
    with open(ROOT / rel, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save(fig, name):
    path = FIG / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path.relative_to(ROOT), path.stat().st_size, "bytes")


# ------------------------------------------------------------------ Q1
def q1_component_mae(metrics):
    labels = ["training median\n(OOF)", "graph low-rank\n(OOF)", "HGB\n(OOF)", "fused\n(OOF)", "fused\n(test, 50 rows)"]
    values = [metrics["median_oof_mae"], metrics["graph_oof_mae"], metrics["hgb_oof_mae"],
              metrics["fused_oof_mae"], metrics["mae"]]
    colors = [GREY, BLUE, BLUE, GREEN, GREEN]
    fig, axis = plt.subplots(figsize=(6.6, 3.4))
    bars = axis.bar(range(5), values, color=colors, width=0.6)
    axis.axhline(metrics["mae_median_reference"], color=RED, lw=0.9, ls="--")
    axis.annotate("median baseline on the same 50 held-out rows = %.4f" % metrics["mae_median_reference"],
                  (0.02, metrics["mae_median_reference"]), xycoords=("axes fraction", "data"),
                  textcoords="offset points", xytext=(0, 3), color=RED, fontsize=7)
    for index, value in enumerate(values):
        axis.annotate("%.4f" % value, (index, value), textcoords="offset points", xytext=(0, 3),
                      ha="center", fontsize=7)
    axis.set_xticks(range(5))
    axis.set_xticklabels(labels, fontsize=7)
    axis.set_ylabel("MAE (50 sensory dimensions, uniform average)")
    axis.set_ylim(min(min(values), metrics["mae_median_reference"]) * 0.93,
                  max(max(values), metrics["mae_median_reference"]) * 1.06)
    axis.set_title("Q1: the fusion gains over its own components are small; the gain over the median baseline is the robust one")
    save(fig, "q1_component_mae.png")


def q1_fusion_weights(weights):
    groups = ["global", "Aroma", "Flavour", "other"]
    keys = ["global", "Aroma", "Flavour", "other"]
    components = weights["components"]
    table = []
    for key in keys:
        if key == "global":
            table.append(weights["global"]["weights"])
        else:
            table.append(weights["groups"][key]["weights"])
    table = np.asarray(table, dtype=float)
    fig, axis = plt.subplots(figsize=(6.2, 3.2))
    width = 0.26
    for index, component in enumerate(components):
        axis.bar(np.arange(len(groups)) + (index - 1) * width, table[:, index], width=width, label=component)
    for row_index, row in enumerate(table):
        for column_index in (1, 2):
            axis.annotate("%.3f" % row[column_index],
                          (row_index + (column_index - 1) * width, row[column_index]),
                          textcoords="offset points", xytext=(0, 2), ha="center", fontsize=6)
    axis.set_xticks(np.arange(len(groups)))
    axis.set_xticklabels(groups, fontsize=7)
    axis.set_ylabel("simplex weight")
    axis.set_ylim(0, 1.0)
    axis.legend(fontsize=7, frameon=False)
    axis.set_title("Q1: OOF-fitted simplex weights (each row sums to 1); the median component is dropped globally")
    save(fig, "q1_fusion_weights.png")


def q1_per_target(outputs):
    per_target = outputs["per_target"]
    improved = set(outputs["summary"]["improvedTargets"])
    names = sorted(per_target, key=lambda name: per_target[name]["skill"])
    skills = [per_target[name]["skill"] for name in names]
    colors = [GREEN if name in improved else RED for name in names]
    fig, axis = plt.subplots(figsize=(9.2, 3.3))
    axis.bar(range(len(names)), skills, color=colors, width=0.8)
    axis.axhline(0.0, color="#333333", lw=0.8)
    axis.set_xticks(range(len(names)))
    axis.set_xticklabels(names, rotation=90, fontsize=5.2)
    axis.set_ylabel("Skill = 1 - MAE_model / MAE_median")
    axis.set_title("Q1: per-target held-out Skill (%d improved, %d degraded vs the training-median baseline)"
                   % (len(improved), len(names) - len(improved)))
    save(fig, "q1_per_target.png")


def q1_cv_grid(outputs):
    cells = outputs["cv_grid"]["cells"]
    selected = outputs["cv_grid"]["selected"]
    fig, axis = plt.subplots(figsize=(6.8, 3.3))
    reps = ["zscore", "rankgauss"]
    colors = {"zscore": GREY, "rankgauss": BLUE}
    for index, rep in enumerate(reps):
        rows = [cell for cell in cells if cell["representation"] == rep]
        xs = np.full(len(rows), index, dtype=float)
        offsets = np.linspace(-0.16, 0.16, len(rows)) if len(rows) > 1 else np.array([0.0])
        xs = xs + offsets[:len(rows)]
        axis.scatter(xs, [cell["cv_mae"] for cell in rows], s=18, color=colors[rep], alpha=0.85, label=rep)
        for x, cell in zip(xs, rows):
            if rep == "rankgauss" and (cell["rank"], cell["lambda"], cell["gamma"]) == (selected["rank"], selected["lambda"], selected["gamma"]):
                axis.annotate("selected\nr=%d,lambda=%g,gamma=%g" % (cell["rank"], cell["lambda"], cell["gamma"]),
                              (x, cell["cv_mae"]), textcoords="offset points", xytext=(6, 8), fontsize=6.5,
                              arrowprops={"arrowstyle": "->", "lw": 0.6})
    axis.errorbar([1.0], [selected["cv_mae"]], yerr=[selected["cv_mae_sd"]], fmt="D", color=ORANGE, ms=5,
                  capsize=3, label="selected +/- fold sd")
    axis.set_xticks([0, 1])
    axis.set_xticklabels(["original-scale z-score", "Rank-Gauss"], fontsize=7)
    axis.set_xlim(-0.6, 1.6)
    axis.set_ylabel("training-internal 5-fold CV MAE")
    axis.legend(fontsize=7, frameon=False)
    axis.set_title("Q1: 54 training-internal CV cells (27 hyperparameter points x 2 representations); nothing here touches the holdout")
    save(fig, "q1_cv_grid.png")


def q1_grades_all():
    path = ROOT / ("experiments/%s/grades_all.csv" % _IDS["q1_grades"])
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    g6 = [column for column in header if column.startswith("g6__")]
    train_index = header.index("is_train")
    counts = {"train": np.zeros(7), "holdout": np.zeros(7)}
    mean_grade = {"train": np.zeros(len(g6)), "holdout": np.zeros(len(g6))}
    sizes = {"train": 0, "holdout": 0}
    per_dimension = {"train": [], "holdout": []}
    for row in rows:
        bucket = "train" if str(row[train_index]).strip() in ("1", "True", "true") else "holdout"
        sizes[bucket] += 1
        values = np.asarray([float(row[header.index(column)]) for column in g6])
        for grade in range(7):
            counts[bucket][grade] += int(np.sum(values == grade))
        per_dimension[bucket].append(values)
    for bucket in ("train", "holdout"):
        mean_grade[bucket] = np.mean(np.vstack(per_dimension[bucket]), axis=0)
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.3), gridspec_kw={"width_ratios": [1.0, 1.35]})
    width = 0.38
    for index, bucket in enumerate(("train", "holdout")):
        total = counts[bucket].sum() or 1.0
        axes[0].bar(np.arange(7) + (index - 0.5) * width, counts[bucket] / total, width=width,
                    color=GREY if bucket == "train" else BLUE,
                    label="%s (%d rows)" % (bucket, sizes[bucket]))
    axes[0].set_xticks(range(7))
    axes[0].set_xticklabels(["0", "1", "2", "3", "4", "5", "6"])
    axes[0].set_xlabel("delivered relative intensity grade g (0-6)")
    axes[0].set_ylabel("share of the 50x%d grade cells" % max(sizes.values()))
    axes[0].legend(fontsize=6.5, frameon=False)
    axes[0].set_title("Q1: grade distribution of the 250x50 table\n(train rows are in-sample; 50 holdout rows are out-of-sample)")
    order = np.argsort(mean_grade["holdout"])
    axes[1].plot(np.arange(len(g6)), mean_grade["train"][order], color=GREY, lw=1.0, label="train rows (in-sample)")
    axes[1].plot(np.arange(len(g6)), mean_grade["holdout"][order], color=BLUE, lw=1.0, label="50 holdout rows")
    axes[1].set_xticks(np.arange(0, len(g6), 5))
    axes[1].set_xticklabels([g6[index].replace("g6__", "") for index in order[::5]], rotation=60, fontsize=5.5)
    axes[1].set_ylabel("mean grade per sensory dimension")
    axes[1].set_ylim(0, 6)
    axes[1].legend(fontsize=6.5, frameon=False)
    axes[1].set_title("Q1: dimensions sorted by held-out mean grade")
    fig.tight_layout()
    save(fig, "q1_grades_all.png")


# ------------------------------------------------------------------ Q2
def q2_bootstrap_pi(outputs):
    final = outputs["final_top3"]
    delivered = [float(row["pi"]) for row in final]
    per_dim = {}
    for row in final:
        per_dim.setdefault(row["dimension"], []).append(float(row["pi"]))
    means = np.asarray([np.mean(values) for values in per_dim.values()])
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.2), gridspec_kw={"width_ratios": [1.0, 1.15]})
    axes[0].hist(delivered, bins=np.linspace(0.0, 1.0, 21), color=BLUE, alpha=0.9)
    axes[0].axvline(np.mean(delivered), color=RED, lw=0.9, ls="--")
    axes[0].annotate("mean pi = %.3f" % np.mean(delivered),
                     (np.mean(delivered), axes[0].get_ylim()[1] * 0.88),
                     textcoords="offset points", xytext=(4, 0), fontsize=7, color=RED)
    axes[0].set_xlabel("bootstrap selection frequency pi (500 style-stratified resamples)")
    axes[0].set_ylabel("number of delivered Top-3 entries")
    axes[0].set_title("Q2: pi of the %d delivered Top-3 entries\n(no compound reaches pi = 1)" % len(delivered))
    order = np.argsort(means)
    axes[1].bar(range(len(means)), means[order], color=GREEN, width=0.8)
    axes[1].axhline(np.mean(delivered), color=RED, lw=0.8, ls="--")
    axes[1].set_xticks(np.arange(0, len(means), 5))
    labels = list(per_dim.keys())
    axes[1].set_xticklabels([labels[index] for index in order[::5]], rotation=60, fontsize=5.5)
    axes[1].set_ylabel("mean pi of the delivered Top-3")
    axes[1].set_ylim(0, 1.0)
    axes[1].set_title("Q2: per-dimension mean pi of the pi-first Top-3")
    fig.tight_layout()
    save(fig, "q2_bootstrap_pi.png")


def q2_method_jaccard(outputs):
    pairs = outputs["method_jaccard"]["summary"]["pairMeans"]
    labels = list(pairs.keys())
    values = [pairs[key] for key in labels]
    fig, axis = plt.subplots(figsize=(7.0, 3.1))
    axis.bar(range(len(labels)), values, color=[GREEN if "consensus" in label else BLUE for label in labels],
             width=0.55)
    for index, value in enumerate(values):
        axis.annotate("%.3f" % value, (index, value), textcoords="offset points", xytext=(0, 3), ha="center",
                      fontsize=7)
    axis.set_xticks(range(len(labels)))
    axis.set_xticklabels([label.replace("_", " ").replace("|", " vs ") for label in labels], rotation=25,
                         ha="right", fontsize=6.5)
    axis.set_ylim(0, 1.0)
    axis.set_ylabel("mean Top-3 Jaccard over 50 dimensions")
    axis.axhline(float(outputs["method_jaccard"]["summary"]["overall"]), color=RED, lw=0.8, ls="--")
    axis.set_title("Q2: pairwise agreement of the four Top-3 sets; the delivered topk-jaccard is their mean (%.3f)"
                   % float(outputs["method_jaccard"]["summary"]["overall"]))
    save(fig, "q2_method_jaccard.png")


def q2_modules(outputs, metrics):
    sizes = outputs["modules"]["moduleSizes"]
    thresholds = ["0.4", "0.5", "0.6"]
    components = [metrics["module_count_tau04"], metrics["module_count_tau05"], metrics["module_count_tau06"]]
    largest = [int(np.max(sizes)) if sizes else 0]
    attachments = outputs["attachment_network"]["thresholds"]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.1))
    axes[0].hist(sizes, bins=range(1, max(sizes) + 2), color=BLUE)
    axes[0].set_yscale("log")
    axes[0].set_xlabel("module size (number of columns in one connected component)")
    axes[0].set_ylabel("number of modules (log scale)")
    axes[0].set_title("Q2: training-network module sizes at tau=0.5\n(%d modules, largest %d)" % (len(sizes), largest[0]))
    x = np.arange(len(thresholds))
    axes[1].bar(x - 0.2, components, width=0.4, color=BLUE, label="training network (200 rows)")
    axes[1].bar(x + 0.2, [attachments[t]["components"] for t in thresholds], width=0.4, color=ORANGE,
                label="attachment network (2.csv)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(["tau=0.4", "tau=0.5", "tau=0.6"])
    axes[1].set_ylabel("connected components")
    axes[1].legend(fontsize=6.5, frameon=False)
    axes[1].set_title("Q2: components of the two networks\n(both are one huge component plus singletons)")
    fig.tight_layout()
    save(fig, "q2_modules.png")


# ------------------------------------------------------------------ Q3
def q3_energy_by_style(outputs):
    cells = outputs["fold-cell-metrics"]
    agg = {}
    for cell in cells:
        entry = agg.setdefault(cell["style"], {"n": 0.0, "energy": 0.0, "ref": 0.0})
        weight = float(cell["n"])
        entry["n"] += weight
        entry["energy"] += weight * float(cell["e_norm"])
        entry["ref"] += weight * float(cell["real_ref"])
    styles = sorted(agg, key=lambda name: agg[name]["energy"])
    energies = [agg[name]["energy"] / max(agg[name]["n"], 1.0) for name in styles]
    refs = [agg[name]["ref"] / max(agg[name]["n"], 1.0) for name in styles]
    sizes = [agg[name]["n"] for name in styles]
    fig, axis = plt.subplots(figsize=(9.4, 3.3))
    axis.bar(range(len(styles)), energies, color=BLUE, width=0.7, label="generated (low-defect)")
    axis.scatter(range(len(styles)), refs, color=ORANGE, s=18, zorder=3, label="real-real reference")
    axis.set_xticks(range(len(styles)))
    axis.set_xticklabels(["%s\n(n=%d)" % (name, int(size)) for name, size in zip(styles, sizes)], rotation=70,
                         fontsize=5.6)
    axis.set_ylabel("normalised energy distance (lower is better)")
    axis.legend(fontsize=6.5, frameon=False)
    axis.set_title("Q3: per-style energy distance of the constrained generator; small styles (Kriek n=10, Lambic n=11, Faro n=3) are unstable")
    save(fig, "q3_energy_by_style.png")


def q3_defect_exceedance(metrics):
    labels = ["real data", "unconstrained\ngeneration", "low-defect\ngeneration"]
    values = [metrics["defect-exceedance-rate-real"], metrics["defect-exceedance-rate-unconstrained"],
              metrics["defect-exceedance-rate"]]
    fig, axis = plt.subplots(figsize=(6.2, 3.1))
    axis.bar(range(3), values, color=[GREY, ORANGE, GREEN], width=0.55)
    for index, value in enumerate(values):
        axis.annotate("%.3f" % value, (index, value), textcoords="offset points", xytext=(0, 3), ha="center",
                      fontsize=7)
    axis.set_xticks(range(3))
    axis.set_xticklabels(labels, fontsize=7)
    axis.set_ylim(0, 1.12)
    axis.set_ylabel("share above >= 1 mean threshold", fontsize=7.5)
    axis.set_title("Q3: defect exceedance rate\n(real vs unconstrained vs low-defect generation)", fontsize=8.5, pad=8)
    fig.tight_layout()
    save(fig, "q3_defect_exceedance.png")


def q3_transfer_scenarios(outputs):
    scenarios = outputs["transfer-scenarios"]
    labels = ["%s\n%s" % (s["policy"].replace("cap-at-max-source-threshold", "cap at max(source,T)")
                          .replace("non-increasing", "absolute non-increasing"), s["thresholdSet"]) for s in scenarios]
    nonworsen = [s["nonworsenRate"] for s in scenarios]
    strict = [s["strictNonworsenRate"] for s in scenarios]
    mahalanobis = [s["targetMahalanobis"] for s in scenarios]
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.2))
    x = np.arange(len(scenarios))
    axes[0].bar(x - 0.2, nonworsen, width=0.4, color=BLUE, label="policy-relative non-worsening")
    axes[0].bar(x + 0.2, strict, width=0.4, color=ORANGE, label="strict per-defect non-increase")
    for index in range(len(scenarios)):
        axes[0].annotate("%.3f" % strict[index], (index + 0.2, strict[index]), textcoords="offset points",
                         xytext=(0, 3), ha="center", fontsize=6.5)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, fontsize=5.4)
    axes[0].set_ylim(0, 1.12)
    axes[0].set_ylabel("non-worsening rate")
    axes[0].legend(fontsize=6.2, frameon=False, loc="lower left")
    axes[0].set_title("Q3: policy-relative vs strict non-worsening\n(the 1.000 is guaranteed by the projection; the strict rate is not)")
    axes[1].bar(x, mahalanobis, color=GREEN, width=0.5)
    for index, value in enumerate(mahalanobis):
        axes[1].annotate("%.3f" % value, (index, value), textcoords="offset points", xytext=(0, 3), ha="center",
                         fontsize=6.5)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=5.4)
    axes[1].set_ylabel("Mahalanobis distance to Tripel")
    axes[1].set_title("Q3: target-style distance is almost identical across the four scenarios")
    fig.tight_layout()
    save(fig, "q3_transfer_scenarios.png")


def q3_pareto(outputs):
    points = outputs["transfer-pareto"]
    fig, axis = plt.subplots(figsize=(6.8, 3.4))
    etas = sorted({point["eta"] for point in points})
    lambdas = sorted({point["lambda"] for point in points})
    colors = {etas[0]: GREY, etas[1]: BLUE, etas[-1]: ORANGE} if len(etas) > 1 else {etas[0]: BLUE}
    # connect the three eta variants of each lambda so the grid is legible without stacking 9 labels
    for lam in lambdas:
        subset = sorted([point for point in points if point["lambda"] == lam], key=lambda point: point["eta"])
        axis.plot([point["meanL1"] for point in subset], [point["targetMahalanobis"] for point in subset],
                  color="#bbbbbb", lw=0.7, zorder=1)
        for point in subset:
            axis.scatter([point["meanL1"]], [point["targetMahalanobis"]], s=26,
                         color=colors.get(point["eta"], BLUE), zorder=2)
        # one lambda label per grid line, placed above the eta=0 member
        head = subset[0]
        axis.annotate("lambda=%g" % lam, (head["meanL1"], head["targetMahalanobis"]),
                      textcoords="offset points", xytext=(-6, 10), ha="right", fontsize=6.5)
    for eta in etas:
        axis.scatter([], [], s=26, color=colors.get(eta, BLUE), label="eta=%g" % eta)
    axis.set_xlabel("mean L1 change of the spectrum (cost)")
    axis.set_ylabel("Mahalanobis distance to Tripel")
    axis.legend(fontsize=6.5, frameon=False, loc="upper right")
    axis.set_title("Q3: lambda/eta Pareto front (9 points); larger lambda buys a closer target style at a larger change",
                   fontsize=7.8, pad=6)
    fig.tight_layout()
    save(fig, "q3_pareto.png")


def q3_profile(outputs):
    per_style = outputs["profile-metrics"]["perStyle"]
    overall = float(outputs["profile-metrics"]["spearman"])
    names = sorted(per_style, key=lambda name: per_style[name]["spearman"])
    values = [per_style[name]["spearman"] for name in names]
    sizes = [per_style[name]["n"] for name in names]
    colors = [RED if value < 0 else GREEN for value in values]
    fig, axis = plt.subplots(figsize=(9.4, 3.2))
    axis.bar(range(len(names)), values, color=colors, width=0.75)
    axis.axhline(overall, color=BLUE, lw=0.9, ls="--")
    axis.annotate("pooled 50-dim profile Spearman = %.3f" % overall, (0.01, overall),
                  xycoords=("axes fraction", "data"), textcoords="offset points", xytext=(0, 3),
                  fontsize=6.8, color=BLUE)
    axis.axhline(0.0, color="#333333", lw=0.7)
    axis.set_xticks(range(len(names)))
    axis.set_xticklabels(["%s\n(n=%d)" % (name, size) for name, size in zip(names, sizes)], rotation=70, fontsize=5.4)
    axis.set_ylabel("Spearman of generated vs real style profile")
    axis.set_title("Q3: the pooled profile score hides per-style heterogeneity (Amber is negative)")
    save(fig, "q3_profile.png")


def main():
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "state/mplconfig"))
    FIG.mkdir(parents=True, exist_ok=True)
    # ids come from MODELING_EXPERIMENT_IDS (resolved at import): q1_candidate plays the
    # role of the old fused EXP-0004, q1_graph of EXP-0003, q2_candidate of EXP-0029,
    # q3_candidate of EXP-0033, q1_grades of EXP-0026.
    exp4_metrics = jload("experiments/%s/metrics.json" % _IDS["q1_candidate"])
    exp4_outputs = jload("experiments/%s/outputs.json" % _IDS["q1_candidate"])
    exp3_outputs = jload("experiments/%s/outputs.json" % _IDS["q1_graph"])
    exp29_metrics = jload("experiments/%s/metrics.json" % _IDS["q2_candidate"])
    exp29_outputs = jload("experiments/%s/outputs.json" % _IDS["q2_candidate"])
    exp33_metrics = jload("experiments/%s/metrics.json" % _IDS["q3_candidate"])
    exp33_outputs = jload("experiments/%s/outputs.json" % _IDS["q3_candidate"])

    q1_component_mae(exp4_metrics)
    q1_fusion_weights(exp4_outputs["fusion_weights"])
    q1_per_target(exp4_outputs)
    q1_cv_grid(exp3_outputs)
    q1_grades_all()
    q2_bootstrap_pi(exp29_outputs)
    q2_method_jaccard(exp29_outputs)
    q2_modules(exp29_outputs, exp29_metrics)
    q3_energy_by_style(exp33_outputs)
    q3_defect_exceedance(exp33_metrics)
    q3_transfer_scenarios(exp33_outputs)
    q3_pareto(exp33_outputs)
    q3_profile(exp33_outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
