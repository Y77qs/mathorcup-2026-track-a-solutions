#!/usr/bin/env python3
"""make_confirmatory_figures.py - the 9 confirmatory figures of report/paper.md.

Every figure is generated from the CURRENT confirmatory evidence only:

    experiments/EXP-0073 EXP-0074 EXP-0075 EXP-0079 EXP-0080
    experiments/EXP-0089 EXP-0090 EXP-0091
    experiments/EXP-0092 EXP-0093 EXP-0099
    experiments/EXP-0095 EXP-0096 EXP-0097
    experiments/EXP-0100 EXP-0101 EXP-0102
    outputs/q3/style_and_displacement_scope.json
    outputs/q3/zspace_recompute.json
    outputs/q3/zspace_centrescale.csv
    data/clean/q2_chem_meta.json
    report/evidence_manifest.json

Hard rules enforced by this script:

* a missing input file, a missing metric key or an inconsistent value raises
  ``NamedFailure`` (non-zero exit, message names the figure and the missing key);
  nothing falls back to an older experiment and no number is replaced by 0;
* numbers that the experiment itself also recorded (pooled MAE, pi_mean,
  per-style pooled energy distance, edgeCount, plan spread) are recomputed here
  and compared bit-for-bit (1e-9) with the recorded value; a mismatch fails;
* old PNG bytes are never reused: every figure is drawn from the artifacts;
* in-figure text is ENGLISH only (no CJK font dependency); the Chinese caption
  is returned as metadata and registered through ``modeling_deliver``.

Usage::

    python src/make_confirmatory_figures.py --list
    python src/make_confirmatory_figures.py --all
    python src/make_confirmatory_figures.py --one Q1-per-target-skill
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("MPLCONFIGDIR", os.path.join(ROOT, "state", "mplconfig"))

import matplotlib  # noqa: E402  (backend must be fixed before pyplot)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

FIGDIR = os.path.join(ROOT, "figures", "confirmatory")

E73 = "experiments/EXP-0073"
E74 = "experiments/EXP-0074"
E75 = "experiments/EXP-0075"
E79 = "experiments/EXP-0079"
E80 = "experiments/EXP-0080"

# robustness plan experiments (ROB-0011 / ROB-0008 / ROB-0009 / ROB-0010)
ROB_EXPS = {
    "ROB-0011": ["EXP-0100", "EXP-0101", "EXP-0102"],
    "ROB-0008": ["EXP-0089", "EXP-0090", "EXP-0091"],
    "ROB-0009": ["EXP-0092", "EXP-0093", "EXP-0099"],
    "ROB-0010": ["EXP-0095", "EXP-0096", "EXP-0097"],
}

CAPTION_LIMIT = 80  # characters, per the paper's figure-caption budget

# palette -------------------------------------------------------------------
C_MAIN = "#1f4e79"      # the delivered strategy / model
C_ALT = "#5b9bd5"
C_BAD = "#c0392b"
C_GOOD = "#2e7d32"
C_GREY = "#8c8c8c"
C_REF = "#7b3294"       # reference lines
C_HL = "#e67e22"        # highlighted / reference-as-baseline
CAT_COLORS = {
    "single_compound": "#2f6fb0",
    "element_or_index": "#d1495b",
    "physical_parameter": "#edae49",
    "derived_sum": "#00798c",
}
CAT_LABELS = {
    "single_compound": "strict single compound (216)",
    "element_or_index": "element / index (3)",
    "physical_parameter": "physical parameter (7)",
    "derived_sum": "derived sum (5)",
}


class NamedFailure(RuntimeError):
    """A figure cannot be produced from the current evidence."""


# helpers -------------------------------------------------------------------
def P(relative: str) -> str:
    return os.path.join(ROOT, relative)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def need(condition, figure: str, message: str) -> None:
    if not condition:
        raise NamedFailure("[%s] %s" % (figure, message))


def load_json(relative: str, figure: str):
    path = P(relative)
    need(os.path.exists(path), figure, "missing input file %r" % relative)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_csv(relative: str, figure: str, **kwargs) -> pd.DataFrame:
    path = P(relative)
    need(os.path.exists(path), figure, "missing input file %r" % relative)
    return pd.read_csv(path, **kwargs)


def metric(data: dict, key: str, where: str, figure: str):
    need(key in data, figure, "missing metric key %r in %s" % (key, where))
    value = data[key]
    need(value is not None, figure, "metric key %r in %s is null" % (key, where))
    return value


def close(left, right, tol=1e-9) -> bool:
    return abs(float(left) - float(right)) <= tol * max(1.0, abs(float(right)))


def check_value(figure: str, what: str, recomputed, recorded, tol=1e-9) -> None:
    need(
        close(recomputed, recorded, tol),
        figure,
        "evidence inconsistency: recomputed %s = %.12g but the artifact records %.12g"
        % (what, float(recomputed), float(recorded)),
    )


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelsize": 8.5,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#444444",
            "axes.linewidth": 0.8,
            "legend.frameon": False,
            "legend.fontsize": 7.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "figure.dpi": 200,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
        }
    )


def save(fig, name: str) -> tuple[str, str]:
    os.makedirs(FIGDIR, exist_ok=True)
    path = os.path.join(FIGDIR, name + ".png")
    fig.savefig(path)
    plt.close(fig)
    return os.path.relpath(path, ROOT), sha256_file(path)


def note(fig, text: str, xy=(0.005, -0.02), size=7.0, color="#333333") -> None:
    fig.text(xy[0], xy[1], text, ha="left", va="top", fontsize=size, color=color)


def scan_text(fig, figure: str, banned=("accuracy", "全面稳定", "fully stable")) -> None:
    """Refuse wording that would overclaim (the figure text is English only)."""
    for artist in fig.findobj(matplotlib.text.Text):
        text = (artist.get_text() or "").lower()
        for word in banned:
            need(word.lower() not in text, figure, "banned wording %r in figure text: %r" % (word, artist.get_text()))


def caption(figure: str, text: str) -> str:
    need(len(text) <= CAPTION_LIMIT, figure, "caption is %d chars (> %d): %r" % (len(text), CAPTION_LIMIT, text))
    return text


def metadata(name, experiment_id, caption_text, inputs, **extra):
    return {
        "name": name,
        "experimentId": experiment_id,
        "caption": caption_text,
        "inputs": [{"path": p, "sha256": sha256_file(P(p))} for p in inputs],
        **extra,
    }


# ===========================================================================
# 1. Q1-per-target-skill - EXP-0073
# ===========================================================================
def fig_q1_per_target_skill():
    name = "Q1-per-target-skill"
    metrics = load_json(f"{E73}/metrics.json", name)
    df = load_csv(f"{E73}/oof_long.csv", name, usecols=["target", "model", "y_true", "y_pred"])
    need({"graph-lowrank", "median"} <= set(df["model"].unique()), name, "oof_long.csv lacks model 'graph-lowrank' or 'median'")

    df["abs_err"] = (df["y_pred"] - df["y_true"]).abs()
    mae = df.groupby(["target", "model"])["abs_err"].mean().unstack("model")
    targets = list(mae.index)
    af30 = [t for t in targets if t.startswith(("A_", "F_"))]
    need(len(af30) == 30, name, "expected 30 A/F30 targets in oof_long.csv, found %d" % len(af30))
    need(len(targets) == 50, name, "expected 50 targets in oof_long.csv, found %d" % len(targets))

    m_af30 = float(mae.loc[af30, "graph-lowrank"].mean())
    b_af30 = float(mae.loc[af30, "median"].mean())
    m_all = float(mae["graph-lowrank"].mean())
    b_all = float(mae["median"].mean())
    skill_af30 = 1.0 - m_af30 / b_af30
    skill_all = 1.0 - m_all / b_all

    check_value(name, "A/F30 OOF MAE (graph-lowrank)", m_af30, metric(metrics, "mae_graph_lowrank", f"{E73}/metrics.json", name))
    check_value(name, "A/F30 OOF MAE (median)", b_af30, metric(metrics, "mae_median", f"{E73}/metrics.json", name))
    check_value(name, "A/F30 skill", skill_af30, metric(metrics, "skill_af30", f"{E73}/metrics.json", name))
    check_value(name, "all-50 OOF MAE (graph-lowrank)", m_all, metric(metrics, "mae_all50", f"{E73}/metrics.json", name))
    check_value(name, "all-50 OOF MAE (median)", b_all, metric(metrics, "mae_all50_median", f"{E73}/metrics.json", name))

    skill = (1.0 - mae["graph-lowrank"] / mae["median"]).sort_values()
    order = list(skill.index)
    values = skill.to_numpy()
    is_af30 = np.array([t.startswith(("A_", "F_")) for t in order])
    colors = [C_GOOD if v >= 0 else C_BAD for v in values]
    negative = int((values < 0).sum())

    fig, ax = plt.subplots(figsize=(10.6, 5.8))
    positions = np.arange(len(order))
    bars = ax.bar(positions, values, color=colors, edgecolor="white", linewidth=0.4, width=0.82, zorder=2)
    # A/F30 targets carry a black outline, the other 20 targets are hatched
    for bar, flag in zip(bars, is_af30):
        if not flag:
            bar.set_hatch("///")
            bar.set_edgecolor("#4d4d4d")
            bar.set_linewidth(0.5)
    ax.axhline(0.0, color="#222222", linewidth=0.9, zorder=3)
    ax.set_xticks(positions)
    ax.set_xticklabels(order, rotation=90, fontsize=6.6)
    ax.set_xlim(-0.7, len(order) - 0.3)
    ax.set_ylabel("skill = 1 - MAE(model) / MAE(per-target median baseline)")
    ax.set_xlabel("sensory target, sorted by skill (lowest left)")
    span = max(abs(values.min()), abs(values.max()))
    ax.set_ylim(values.min() - 0.14 * span, values.max() + 0.16 * span)

    ax.set_title(
        "Q1 per-target skill - graph low-rank (MODEL-0048) vs per-target median baseline\n"
        "pooled out-of-fold rows, internal nested 3x3x3 re-validation (3 repeats x 3 outer folds), not a holdout"
    )
    for i, v in enumerate(values):
        ax.text(i, v + (0.012 * span if v >= 0 else -0.028 * span), ("%.2f" % v),
                ha="center", va="bottom" if v >= 0 else "top", fontsize=5.6, rotation=90,
                color="#333333")

    handles = [
        Patch(facecolor=C_GOOD, label="positive skill (better than the median baseline)"),
        Patch(facecolor=C_BAD, label="negative skill (worse than the median baseline: %d/50)" % negative),
        Patch(facecolor="#bbbbbb", edgecolor="#4d4d4d", hatch="///", label="other 20 targets (all-50 caliber)"),
        Patch(facecolor="#bbbbbb", label="A/F30 targets (30: 15 aroma + 15 flavour)"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=7.2, ncol=2)

    summary = (
        "Aggregate pooled out-of-fold skill (from metrics.json, recomputed here)\n"
        "A/F30 (30 targets): MAE %.6f vs median %.6f  ->  skill %.6f\n"
        "all 50 targets:     MAE %.6f vs median %.6f  ->  skill %.6f"
        % (m_af30, b_af30, skill_af30, m_all, b_all, skill_all)
    )
    ax.text(0.985, 0.035, summary, transform=ax.transAxes, ha="right", va="bottom", fontsize=7.0,
            family="DejaVu Sans Mono",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#f7f7f7", edgecolor="#b0b0b0", linewidth=0.6))

    note(fig, "Skill is a RELATIVE mean-absolute-error improvement over the per-target median baseline (ratio of errors, not a score-match rate). "
              "Source: experiments/EXP-0073/oof_long.csv (graph-lowrank, median; 3 repeats x 3 folds, 750 rows x 50 targets).",
         xy=(0.005, -0.13))
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题一：逐目标相对误差改善 1−MAE模型/MAE中位数（图低秩，内部嵌套CV折外池化）；A/F30 %.4f、全50维 %.4f，%d 个目标为负。"
                   % (skill_af30, skill_all, negative))
    return metadata(name, "EXP-0073", text, [f"{E73}/metrics.json", f"{E73}/oof_long.csv"],
                    path=path, sha256=digest,
                    key_values={"skill_af30": skill_af30, "skill_all50": skill_all,
                                "mae_af30": m_af30, "baseline_af30": b_af30, "negative_targets": negative})


# ===========================================================================
# 2. Q1-model-comparison - EXP-0073 (+ EXP-0074 median baseline)
# ===========================================================================
def fig_q1_model_comparison():
    name = "Q1-model-comparison"
    metrics = load_json(f"{E73}/metrics.json", name)
    base = load_json(f"{E74}/metrics.json", name)

    models = [
        ("median", "median baseline", "mae_median", "mae_all50_median"),
        ("ridge0", "ridge (gamma=0, r=50)", "mae_ridge0", "mae_all50_ridge0"),
        ("graph-ridge", "graph ridge", "mae_graph_ridge", "mae_all50_graph_ridge"),
        ("graph-lowrank", "graph low-rank", "mae_graph_lowrank", "mae_all50_graph_lowrank"),
    ]
    af30 = [metric(metrics, af_key, f"{E73}/metrics.json", name) for _, _, af_key, _ in models]
    all50 = [metric(metrics, all_key, f"{E73}/metrics.json", name) for _, _, _, all_key in models]
    median_ref = metric(base, "mae", f"{E74}/metrics.json", name)
    median_ref_all = metric(base, "mae_all50", f"{E74}/metrics.json", name)
    check_value(name, "EXP-0074 A/F30 median MAE vs EXP-0073 mae_median", median_ref, af30[0])
    check_value(name, "EXP-0074 all-50 median MAE vs EXP-0073 mae_all50_median", median_ref_all, all50[0])

    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    positions = np.arange(len(models))
    width = 0.36
    bars_a = ax.bar(positions - width / 2, af30, width, color=C_MAIN, edgecolor="white", linewidth=0.4,
                    label="A/F30 (30 targets)", zorder=2)
    bars_b = ax.bar(positions + width / 2, all50, width, color=C_ALT, edgecolor="white", linewidth=0.4,
                    label="all 50 targets", zorder=2)
    for x, v in zip(positions - width / 2, af30):
        ax.text(x, v + 0.0035, "%.4f" % v, ha="center", va="bottom", fontsize=7.6, fontweight="bold")
    for x, v in zip(positions + width / 2, all50):
        ax.text(x, v + 0.0035, "%.4f" % v, ha="center", va="bottom", fontsize=7.6, color="#1f4e79")
    for x, v in zip(positions, af30):
        skill = 1.0 - v / af30[0]
        ax.text(x, v + 0.019, "skill %.4f" % skill, ha="center", va="bottom", fontsize=6.8, color="#444444")
    # the median bar IS the EXP-0074 reference value; the equality is stated in the note rather than drawn,
    # because a reference line through the top of that bar would collide with the bar labels.
    ax.set_xticks(positions)
    ax.set_xticklabels([label for _, label, _, _ in models], fontsize=8)
    ax.set_ylabel("out-of-fold MAE (mean absolute error)")
    ax.set_ylim(0.0, af30[0] * 1.34)
    ax.set_title(
        "Q1 four-model comparison on the SAME protocol - A/F30 OOF MAE\n"
        "internal nested re-validation (3 repeats x 3 outer folds x 3 inner folds), NOT a holdout"
    )
    ax.legend(loc="upper right", fontsize=7.6)
    note(fig, "All four models are refitted inside the same 3x3x3 nested out-of-fold loop of EXP-0073. "
              "The independent EXP-0074 run reproduces the median baseline exactly: A/F30 %.6f and all-50 %.6f, "
              "identical to EXP-0073 to < 1e-15. No external (holdout) test set exists for Q1." % (median_ref, median_ref_all))
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题一：四模型同协议折外MAE（内部3×3×3嵌套重验证，非holdout）：中位数%.3f、岭%.3f、图岭%.3f、图低秩%.3f；全50维另列。"
                   % tuple(af30))
    return metadata(name, "EXP-0073", text, [f"{E73}/metrics.json", f"{E74}/metrics.json"],
                    path=path, sha256=digest,
                    key_values={"af30": af30, "all50": all50, "exp0074_median": median_ref})


# ===========================================================================
# 3. Q1-grade-distribution - EXP-0073
# ===========================================================================
def fig_q1_grade_distribution():
    name = "Q1-grade-distribution"
    outputs = load_json(f"{E73}/outputs.json", name)
    need("q1" in outputs and "grade" in outputs["q1"], name, "missing key 'q1.grade' in %s/outputs.json" % E73)
    grade = outputs["q1"]["grade"]
    need("perModel" in grade, name, "missing key 'q1.grade.perModel' in %s/outputs.json" % E73)

    models = ["median", "ridge", "graph-ridge", "graph-lowrank"]
    for model in models:
        need(model in grade["perModel"], name, "missing grade block for model %r" % model)
    oof = load_csv(f"{E73}/oof_long.csv", name, usecols=["model", "grade_true", "grade_pred"])

    # cross-check the recorded counts against the raw out-of-fold grade columns
    reference = None
    for model in models:
        block = grade["perModel"][model]
        for key in ("grade_counts_reference", "grade_counts_predicted", "n_grade_cells", "qwk",
                    "exact_agreement", "within_one_agreement", "grade_mae"):
            need(key in block, name, "missing key 'q1.grade.perModel.%s.%s'" % (model, key))
        rows = oof[oof["model"] == model]
        need(len(rows) == int(block["n_grade_cells"]), name,
             "model %r: %d oof rows but n_grade_cells = %r" % (model, len(rows), block["n_grade_cells"]))
        true_counts = rows["grade_true"].value_counts().reindex(range(7), fill_value=0).to_numpy(int)
        pred_counts = rows["grade_pred"].value_counts().reindex(range(7), fill_value=0).to_numpy(int)
        need(list(true_counts) == list(block["grade_counts_reference"]), name,
             "model %r: oof grade_true counts %r != recorded reference counts %r"
             % (model, list(true_counts), block["grade_counts_reference"]))
        need(list(pred_counts) == list(block["grade_counts_predicted"]), name,
             "model %r: oof grade_pred counts %r != recorded predicted counts %r"
             % (model, list(pred_counts), block["grade_counts_predicted"]))
        if reference is None:
            reference = true_counts
        else:
            need(list(reference) == list(true_counts), name, "reference grade counts differ between models")

    fig, ax = plt.subplots(figsize=(8.4, 4.5))
    grades = np.arange(7)
    colors = {"median": C_GREY, "ridge": "#9ecae1", "graph-ridge": C_ALT, "graph-lowrank": C_MAIN}
    labels = {"median": "median baseline", "ridge": "ridge", "graph-ridge": "graph ridge", "graph-lowrank": "graph low-rank"}
    width = 0.15
    offsets = np.arange(len(models) + 1) - (len(models)) / 2.0
    ax.bar(grades + offsets[0] * width, reference, width, color="#d9d9d9", edgecolor="#7f7f7f",
           linewidth=0.4, label="reference (observed outer-test label grade)", zorder=2)
    for offset_position, model in zip(offsets[1:], models):
        ax.bar(grades + offset_position * width, grade["perModel"][model]["grade_counts_predicted"], width,
               color=colors[model], edgecolor="white", linewidth=0.3, label="predicted - " + labels[model], zorder=2)
    median_counts = grade["perModel"]["median"]["grade_counts_predicted"]
    spike = int(np.argmax(median_counts))
    ax.annotate("%d cells\n(all predicted at grade %d)" % (int(median_counts[spike]), spike),
                xy=(spike + offsets[1] * width, median_counts[spike]), xytext=(-40, -62),
                textcoords="offset points", ha="right", va="top", fontsize=6.6, color="#333333",
                arrowprops=dict(arrowstyle="->", color="#555555", lw=0.7))
    ax.set_xticks(grades)
    ax.set_xlabel("relative grade (0-6, from the outer-training empirical CDF; not the panel's original score)")
    ax.set_ylabel("grade cells (pooled out-of-fold, 37,500 per model)")
    ax.set_ylim(0.0, 41000.0)
    ax.set_title(
        "Q1 relative-grade distribution - predicted out-of-fold vs reference\n"
        "grade rule: g = clip(floor(6F(y) + 0.5), 0, 6), F = mid-rank empirical CDF of the outer-training labels"
    )
    ax.legend(ncol=3, loc="upper left", fontsize=7.0)
    hub = grade["perModel"]["graph-lowrank"]
    ax.text(0.985, 0.62,
            "graph low-rank\nQWK %.4f\nexact %.4f\nwithin-one %.4f\ngrade MAE %.4f"
            % (hub["qwk"], hub["exact_agreement"], hub["within_one_agreement"], hub["grade_mae"]),
            transform=ax.transAxes, ha="right", va="top", fontsize=6.9, family="DejaVu Sans Mono",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f7f7f7", edgecolor="#b0b0b0", linewidth=0.6))
    note(fig, "The reference distribution is near-uniform BY CONSTRUCTION (the mid-rank CDF maps the outer-training labels onto 0-6): "
              "this figure compares relative grade placement, it does NOT recover the panel's original 0-6 human score.")
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题一：相对等级 0–6 的折外预测分布与参照分布对照（内部嵌套CV、中秩经验CDF；属相对等级，未恢复人工评分）。")
    return metadata(name, "EXP-0073", text, [f"{E73}/outputs.json", f"{E73}/oof_long.csv"],
                    path=path, sha256=digest,
                    key_values={"qwk": hub["qwk"], "exact": hub["exact_agreement"],
                                "within_one": hub["within_one_agreement"], "reference_counts": list(reference)})


# ===========================================================================
# 4. Q2-network - EXP-0075 (recomputed from the registered inputs, tau = 0.5)
# ===========================================================================
def _spearman_matrix(matrix: np.ndarray) -> np.ndarray:
    """Rank -> Pearson, mid-ranks for ties (same rule as the frozen q_common.spearman_matrix)."""
    ranks = np.empty_like(matrix, dtype=float)
    for column in range(matrix.shape[1]):
        values = matrix[:, column]
        order = np.argsort(values, kind="mergesort")
        ordered = values[order]
        unique, inverse, counts = np.unique(ordered, return_inverse=True, return_counts=True)
        mid = np.cumsum(counts) - (counts - 1) / 2.0
        ranks[order, column] = mid[inverse]
    ranks = ranks - ranks.mean(axis=0, keepdims=True)
    scaled = ranks / np.maximum(np.linalg.norm(ranks, axis=0, keepdims=True), 1e-12)
    return scaled.T @ scaled


def _force_layout(edge_index: np.ndarray, seed: int = 20261025, iterations: int = 700,
                  gravity: float = 0.06) -> np.ndarray:
    """Deterministic Fruchterman-Reingold layout with a gravity term for the largest component."""
    n = int(edge_index.max()) + 1
    rng = np.random.default_rng(seed)
    positions = rng.uniform(-1.0, 1.0, size=(n, 2))
    k = 1.6 / np.sqrt(n)
    temperature = 0.18
    for _ in range(iterations):
        delta = positions[:, None, :] - positions[None, :, :]
        distance = np.sqrt((delta ** 2).sum(axis=-1))
        np.fill_diagonal(distance, np.inf)
        displacement = ((k * k / (distance ** 2))[:, :, None] * delta).sum(axis=1)
        for i, j in edge_index:
            vec = positions[i] - positions[j]
            dist = float(np.hypot(*vec)) + 1e-9
            force = dist * dist / k
            unit = vec / dist
            displacement[i] -= unit * force
            displacement[j] += unit * force
        displacement -= gravity * (positions - positions.mean(axis=0, keepdims=True))
        norm = np.linalg.norm(displacement, axis=1, keepdims=True) + 1e-12
        positions += displacement * np.minimum(1.0, temperature / norm)
        temperature *= 0.992
    positions -= positions.mean(axis=0, keepdims=True)
    scale = np.abs(positions).max()
    return positions / (scale + 1e-12)


def fig_q2_network():
    name = "Q2-network"
    outputs = load_json(f"{E75}/outputs.json", name)
    need("q2" in outputs, name, "missing top-level key 'q2' in %s/outputs.json" % E75)
    q2 = outputs["q2"]
    modules = q2.get("modules")
    need(isinstance(modules, dict), name, "missing key 'q2.modules' in %s/outputs.json" % E75)
    for key in ("edgeCount", "count", "largestModuleSize", "moduleSizes"):
        need(key in modules, name, "missing key 'q2.modules.%s'" % key)
    members = q2.get("categoryMembers")
    need(isinstance(members, dict), name, "missing key 'q2.categoryMembers'")
    counts = q2.get("category_counts")
    need(isinstance(counts, dict), name, "missing key 'q2.category_counts'")

    meta = load_json("data/clean/q2_chem_meta.json", name)
    need(isinstance(meta.get("features"), list) and len(meta["features"]) == 231, name,
         "data/clean/q2_chem_meta.json must list 231 features")
    feature_names = [item["name"] for item in meta["features"]]
    meta_kind = {item["name"]: item["kind"] for item in meta["features"]}

    # authoritative node category = the experiment's own declared partition, reconciled with the metadata
    category = {}
    for kind, names in members.items():
        for feature in names:
            need(feature not in category, name, "feature %r appears in two categoryMembers blocks" % feature)
            category[feature] = kind
    need(set(category) == set(feature_names), name, "categoryMembers does not partition the 231 feature names")
    for kind in ("single_compound", "element_or_index", "physical_parameter", "derived_sum"):
        expected = int(counts.get(kind, -1))
        observed = sum(1 for value in category.values() if value == kind)
        need(observed == expected, name,
             "category %r has %d members but category_counts records %d" % (kind, observed, expected))
    reclassified = [f for f in feature_names if meta_kind[f] != category[f]]
    for feature in reclassified:
        need(meta_kind[feature] == "single_compound" and category[feature] == "element_or_index", name,
             "unexpected metadata/experiment category mismatch for %r (%s vs %s)"
             % (feature, meta_kind[feature], category[feature]))
    need(len(reclassified) == 3, name, "expected exactly 3 reclassified element_or_index features, found %d" % len(reclassified))

    # recompute the tau = 0.5 graph from the registered training table
    split_rel = f"{E75}/inputs/data/splits/SPLIT-0001/train.csv"
    frame = load_csv(split_rel, name, low_memory=False)
    need(len(frame) == 200, name, "%s must hold the 200 registered training rows, found %d" % (split_rel, len(frame)))
    columns = ["chem__" + feature for feature in feature_names]
    missing = [c for c in columns if c not in frame.columns]
    need(not missing, name, "registered training table is missing %d chemistry columns (first: %r)" % (len(missing), missing[:1]))
    matrix = np.empty((len(frame), len(columns)), dtype=float)
    for index, column in enumerate(columns):
        raw = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        finite = raw[np.isfinite(raw)]
        need(finite.size > 0, name, "column %r has no finite value to impute from" % column)
        matrix[:, index] = np.where(np.isfinite(raw), raw, float(np.median(finite)))
    rho = _spearman_matrix(matrix)
    weight = np.where(np.abs(rho) >= 0.5, rho, 0.0)
    weight = 0.5 * (weight + weight.T)
    np.fill_diagonal(weight, 0.0)
    edges = int(np.count_nonzero(np.triu(weight, 1)))
    adjacency = np.abs(weight) > 0
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    n_components, labels = connected_components(csr_matrix(adjacency.astype(np.int8)))
    sizes = np.bincount(labels)
    largest = int(sizes.max())

    # the recompute must reproduce the experiment's own recorded topology
    check_value(name, "edge count at tau=0.5", edges, modules["edgeCount"], tol=0)
    check_value(name, "component count at tau=0.5", n_components, modules["count"], tol=0)
    check_value(name, "largest component size at tau=0.5", largest, modules["largestModuleSize"], tol=0)
    need(list(np.sort(sizes)[::-1]) == sorted([int(s) for s in modules["moduleSizes"]], reverse=True), name,
         "recomputed component-size spectrum differs from q2.modules.moduleSizes")

    big = int(np.argmax(sizes))
    subset = np.where(labels == big)[0]
    degree = adjacency.sum(axis=0)
    local = {int(node): index for index, node in enumerate(subset)}
    pairs = []
    for i in range(len(subset)):
        for j in range(i + 1, len(subset)):
            if adjacency[subset[i], subset[j]]:
                pairs.append((local[int(subset[i])], local[int(subset[j])]))
    positions = _force_layout(np.asarray(pairs, dtype=int))

    fig = plt.figure(figsize=(12.4, 5.8))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.95, 1.0], wspace=0.16)
    ax = fig.add_subplot(grid[0, 0])

    for i, j in pairs:
        sign = weight[subset[i], subset[j]]
        color = "#c0392b" if sign < 0 else "#9e9e9e"
        alpha = 0.60 if sign < 0 else 0.16
        width = 1.2 if sign < 0 else 0.40
        ax.plot([positions[i, 0], positions[j, 0]], [positions[i, 1], positions[j, 1]],
                color=color, alpha=alpha, linewidth=width, zorder=1, solid_capstyle="round")

    node_colors = [CAT_COLORS[category[feature_names[int(node)]]] for node in subset]
    node_sizes = 5.0 + 2.4 * degree[subset]
    ax.scatter(positions[:, 0], positions[:, 1], s=node_sizes, c=node_colors, edgecolors="white",
               linewidths=0.4, zorder=3)

    hubs = np.argsort(-degree[subset])[:6]
    hub_text = ", ".join("%s (%d)" % (feature_names[int(subset[i])], int(degree[subset[i]])) for i in hubs)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("(a) largest connected component (%d of 231 nodes, %d internal edges)"
                 % (largest, len(pairs)), loc="left")

    handles = [Patch(facecolor=CAT_COLORS[kind], label=CAT_LABELS[kind]) for kind in CAT_COLORS]
    handles += [Line2D([0], [0], color="#c0392b", linewidth=1.4, label="negative edge (rho <= -0.5): %d" % int((weight < 0).sum() // 2)),
                Line2D([0], [0], color="#9e9e9e", linewidth=0.8, label="positive edge (rho >= 0.5): %d" % int((weight > 0).sum() // 2))]
    ax.legend(handles=handles, loc="lower left", fontsize=6.6, ncol=1)

    ax2 = fig.add_subplot(grid[0, 1])
    ordered = np.sort(sizes)[::-1]
    ax2.bar(np.arange(len(ordered)), ordered, color=C_MAIN, width=0.8, zorder=2)
    ax2.set_yscale("log")
    ax2.set_xlabel("component index (sorted by size)")
    ax2.set_ylabel("component size (nodes, log scale)")
    ax2.set_title("(b) component-size spectrum (%d components)" % n_components, loc="left")
    ax2.set_ylim(0.7, max(ordered) * 1.9)
    singles = int((sizes == 1).sum())
    ax2.annotate("172-node component\n(density 723/14706)", xy=(0, ordered[0]), xytext=(8, ordered[0] * 0.55),
                 fontsize=6.7, arrowprops=dict(arrowstyle="->", color="#555555", lw=0.7))
    ax2.text(len(ordered) * 0.52, 1.25,
             "%d isolated nodes\n%d x size-3, 1 x size-5, 1 x size-2" % (singles, int((sizes == 3).sum())),
             fontsize=6.9, ha="center", va="bottom")
    ax2.grid(axis="y", color="#e6e6e6", linewidth=0.5, zorder=0)
    ax2.set_axisbelow(True)

    note(fig, "Tau = 0.5 Spearman threshold graph (|rho| >= 0.5) on the 231 registered chemistry columns, 200 SPLIT-0001 training rows.\n"
              "Highest-degree nodes (degree): %s.\n" % hub_text +
              "RECOMPUTED from the EXP-0075 registered inputs and it reproduces the experiment's recorded topology exactly "
              "(732 edges / 51 components / 172 largest).\n"
              "Red edges are negative associations, grey are positive. An edge is a same-sample association, NOT a causal or mechanistic link.\n"
              "Candidate universes: 216 strict single compounds + 15 extended indicators (3 element/index + 7 physical + 5 derived sums).")
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题二：τ=0.5 Spearman 阈值网络（由 EXP-0075 注册输入重算，复现 %d 边/%d 分量）；严格单体216与扩展15分色，边非因果。"
                   % (edges, n_components))
    return metadata(name, "EXP-0075", text,
                    [f"{E75}/outputs.json", split_rel, "data/clean/q2_chem_meta.json"],
                    path=path, sha256=digest,
                    key_values={"edges": edges, "components": n_components, "largest": largest,
                                "negative_edges": int((weight < 0).sum() // 2),
                                "reclassified": reclassified})


# ===========================================================================
# 5. Q2-stability - EXP-0075 (+ ROB-0008 budget perturbation)
# ===========================================================================
def fig_q2_stability():
    name = "Q2-stability"
    metrics = load_json(f"{E75}/metrics.json", name)
    outputs = load_json(f"{E75}/outputs.json", name)
    q2 = outputs["q2"]
    for key in ("per_repeat", "stability", "jaccard"):
        need(key in q2, name, "missing key 'q2.%s' in %s/outputs.json" % (key, E75))

    frames = []
    for repeat in range(3):
        frame = load_csv(f"{E75}/repeat{repeat}/strict_top3_by_method.csv", name)
        for column in ("dimension", "method", "rank", "compound", "pi", "sign_stability", "direction",
                       "alternative_rank4", "evidence_status"):
            need(column in frame.columns, name, "repeat%d/strict_top3_by_method.csv lacks column %r" % (repeat, column))
        frame["repeat"] = repeat
        frames.append(frame)
    board = pd.concat(frames, ignore_index=True)
    need(len(board) == 1800, name, "expected 1800 delivered strict entries (600 x 3 repeats), found %d" % len(board))

    pi_mean = float(board["pi"].mean())
    below = int((board["pi"] < 0.5).sum())
    sign_mean = float(board["sign_stability"].mean())
    check_value(name, "pi_mean", pi_mean, metric(metrics, "pi_mean", f"{E75}/metrics.json", name))
    check_value(name, "pi_below_0.5_count", below, metric(metrics, "pi_below_0.5_count", f"{E75}/metrics.json", name))
    check_value(name, "sign_stability_mean", sign_mean, metric(metrics, "sign_stability_mean", f"{E75}/metrics.json", name))
    denominator = int(metric(metrics, "pi_below_0.5_denominator", f"{E75}/metrics.json", name))
    need(denominator == len(board), name, "pi denominator %d != %d delivered entries" % (denominator, len(board)))

    third_counts = []
    for repeat in range(3):
        block = q2["per_repeat"].get("rep%d" % repeat)
        need(isinstance(block, dict), name, "missing 'q2.per_repeat.rep%d'" % repeat)
        third_counts.append(int(block.get("thirdPlaceUnstableCount", -1)))
    need(all(value >= 0 for value in third_counts), name, "per_repeat is missing thirdPlaceUnstableCount")

    # ROB-0008: reference 500 reps / seed block 500 reps / budget 200 reps
    rob = load_json("report/evidence_manifest.json", name)["questions"]["Q2"]["robustnessPlan"]
    need(rob.get("robId") == "ROB-0008", name, "manifest Q2 robustnessPlan is not ROB-0008")
    jaccard = {}
    for experiment in ROB_EXPS["ROB-0008"]:
        record = load_json(f"experiments/{experiment}/metrics.json", name)
        jaccard[experiment] = float(metric(record, "topk-jaccard", f"experiments/{experiment}/metrics.json", name))
    check_value(name, "ROB-0008 reference Jaccard", jaccard["EXP-0089"], rob["values"][0])
    check_value(name, "ROB-0008 seed Jaccard", jaccard["EXP-0090"], rob["values"][1])
    check_value(name, "ROB-0008 budget Jaccard", jaccard["EXP-0091"], rob["values"][2])
    note_0091 = load_json("experiments/EXP-0091/experiment.json", name)
    purpose = json.dumps(note_0091.get("params", {}).get("note", ""))
    need("500 -> 200" in purpose or "500 ->200" in purpose or "500->200" in purpose, name,
         "EXP-0091 is not the bootstrap 500 -> 200 budget perturbation: %r" % purpose)

    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.6))
    fig.subplots_adjust(hspace=0.62, wspace=0.28)

    ax = axes[0, 0]
    bins = np.linspace(0.0, 1.0, 21)
    ax.hist(board["pi"], bins=bins, color=C_MAIN, edgecolor="white", linewidth=0.4, zorder=2)
    ax.axvline(pi_mean, color=C_HL, linewidth=1.4, label="mean pi = %.4f" % pi_mean, zorder=3)
    ax.axvline(0.5, color=C_REF, linestyle="--", linewidth=1.0, zorder=3,
               label="0.5 = reference only, NOT a pass line")
    ax.set_xlabel("selection frequency pi of the delivered Top-3 entry (bootstrap, 500 replicates)")
    ax.set_ylabel("delivered entries (n = 1800)")
    ax.set_xlim(0.0, 1.05)
    ax.set_title("(a) pi distribution of the delivered strict Top-3 entries", loc="left")
    ax.legend(loc="upper right", fontsize=6.8)
    ax.text(0.985, 0.60, "%d of %d entries below 0.5 (%.1f%%)\nno entry reaches pi = 1.0"
            % (below, len(board), 100.0 * below / len(board)),
            transform=ax.transAxes, ha="right", va="top", fontsize=7.0,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#f7f7f7", edgecolor="#b0b0b0", linewidth=0.6))

    ax = axes[0, 1]
    methods = ["total_spearman", "within_style_spearman", "graph_lowrank", "consensus"]
    labels = {"total_spearman": "total Spearman", "within_style_spearman": "within-style",
              "graph_lowrank": "graph low-rank", "consensus": "consensus"}
    colors = {"total_spearman": "#9ecae1", "within_style_spearman": "#f4a582",
              "graph_lowrank": "#a6d96a", "consensus": C_MAIN}
    group = board.groupby(["method", "rank"])["pi"].mean()
    width = 0.2
    for offset, method in enumerate(methods):
        heights = [float(group.loc[(method, rank)]) for rank in (1, 2, 3)]
        ax.bar(np.arange(3) + (offset - 1.5) * width, heights, width, color=colors[method],
               edgecolor="white", linewidth=0.3, label=labels[method], zorder=2)
    for index, rank in enumerate((1, 2, 3)):
        mean_rank = float(group.loc[(slice(None), rank)].mean())
        ax.text(index, 0.012, "mean %.3f" % mean_rank, ha="center", va="bottom", fontsize=6.6, color="#333333")
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(["rank 1", "rank 2", "rank 3"])
    ax.set_ylabel("mean selection frequency pi")
    ax.set_ylim(0.0, 0.86)
    ax.set_title("(b) pi erodes from rank 1 to rank 3 (all four methods)\n"
                 "3rd place unstable in %d-%d of 200 (dimension, method) cells"
                 % (min(third_counts), max(third_counts)), loc="left")
    ax.legend(fontsize=6.8, ncol=2, loc="upper right", columnspacing=0.9)

    ax = axes[1, 0]
    box = [board.loc[board["method"] == method, "sign_stability"].to_numpy() for method in methods]
    parts = ax.boxplot(box, widths=0.55, patch_artist=True, showfliers=False,
                       medianprops=dict(color="#222222", linewidth=1.0))
    for patch, method in zip(parts["boxes"], methods):
        patch.set_facecolor(colors[method])
        patch.set_alpha(0.85)
        patch.set_edgecolor("#444444")
        patch.set_linewidth(0.6)
    status = board["evidence_status"].value_counts()
    ax.axhline(sign_mean, color=C_HL, linewidth=1.3, zorder=3)
    ax.axhline(0.5, color=C_REF, linestyle="--", linewidth=0.9, zorder=3)
    ax.set_xlim(0.4, 4.9)
    ax.text(0.46, sign_mean + 0.02, "mean %.4f" % sign_mean, ha="left", va="bottom", fontsize=6.6, color=C_HL)
    ax.text(0.46, 0.52, "0.5 = reference only", ha="left", va="bottom", fontsize=6.4, color=C_REF)
    ax.set_xticks(np.arange(1, len(methods) + 1))
    ax.set_xticklabels([labels[m] for m in methods], fontsize=6.8)
    ax.set_ylabel("sign consistency (share of replicates with positive signed rho)")
    ax.set_ylim(-0.03, 1.10)
    ax.set_title("(c) sign consistency by method\nstable entries %d/1800; negative-direction entries %d"
                 % (int(status.get("stable", 0)), int((board["direction"] == "negative").sum())), loc="left")

    ax = axes[1, 1]
    positions = np.arange(3)
    values = [jaccard["EXP-0089"], jaccard["EXP-0090"], jaccard["EXP-0091"]]
    tick = ["reference\n500 reps, seed 20261025", "seed perturbation\n500 reps, seed 20261026",
            "budget perturbation\n200 reps, seed 20261025"]
    ax.bar(positions, values, 0.58, color=[C_MAIN, C_ALT, C_HL], edgecolor="white", linewidth=0.4, zorder=2)
    for x, v in zip(positions, values):
        ax.text(x, v + 0.0015, "%.6f" % v, ha="center", va="bottom", fontsize=7.4)
    ax.set_xticks(positions)
    ax.set_xticklabels(tick, fontsize=6.8)
    ax.set_ylim(0.0, max(values) * 1.50)
    ax.set_ylabel("Q2 Top-3 pooled Jaccard (ROB-0008 metric)")
    ax.set_title("(d) budget perturbation 500 -> 200 bootstrap replicates", loc="left")
    delta = values[2] - values[0]
    ax.text(1.0, max(values) * 1.30,
            "500 -> 200 changes Jaccard by %+.6f:\nlower Monte-Carlo precision,\nNOT a drop in selection stability"
            % delta, ha="center", va="center", fontsize=6.9,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#fdf3e7", edgecolor="#e67e22", linewidth=0.6))
    fig.suptitle("Q2 Top-3 selection stability - 3 frozen seeds x 500 style-stratified bootstrap replicates (ROB-0008 adds the budget arm)",
                 fontsize=9.6, fontweight="bold", y=0.99)
    note(fig, "pi is the share of bootstrap replicates in which an entry survives in the delivered Top-3; it is a stability statistic, not a p-value.\n"
              "pi = 0.5 is drawn as a reference line only - no threshold of 0.5 was pre-registered and it is NOT a pass/fail line.\n"
              "The 500 -> 200 arm lowers Monte-Carlo precision (pi Monte-Carlo SE = sqrt(pi(1-pi)/reps)); it is not evidence that selection became less stable.")
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题二：Top-3 入选频率 π 与符号一致性（500 次风格内 bootstrap、3 重复）；0.5 仅参考非判定，500→200 为蒙特卡洛精度变化。")
    return metadata(name, "EXP-0075", text,
                    [f"{E75}/metrics.json", f"{E75}/outputs.json"]
                    + [f"{E75}/repeat{repeat}/strict_top3_by_method.csv" for repeat in range(3)]
                    + [f"experiments/{e}/metrics.json" for e in ROB_EXPS["ROB-0008"]]
                    + ["report/evidence_manifest.json"],
                    path=path, sha256=digest,
                    key_values={"pi_mean": pi_mean, "pi_below_0.5": below, "n": len(board),
                                "sign_stability_mean": sign_mean, "third_place_unstable": third_counts,
                                "rob0008_values": values})


# ===========================================================================
# 6. Q3-energy-comparison - EXP-0079
# ===========================================================================
def fig_q3_energy_comparison():
    name = "Q3-energy-comparison"
    outputs = load_json(f"{E79}/outputs.json", name)
    need("q3" in outputs and "comparisons" in outputs["q3"], name, "missing key 'q3.comparisons' in %s/outputs.json" % E79)
    comparisons = outputs["q3"]["comparisons"]
    designs = ["copula-selected", "copula-shared-only", "copula-style-empirical", "independent-marginals", "source-resample"]
    labels = {
        "copula-selected": "generated design\n(copula-selected)",
        "copula-shared-only": "shared-correlation\ncopula",
        "copula-style-empirical": "within-style\nempirical copula",
        "independent-marginals": "independent\nmarginals",
        "source-resample": "source resample\n(no generation)",
    }
    values = {}
    for design in designs:
        need(design in comparisons, name, "missing key 'q3.comparisons.%s'" % design)
        block = comparisons[design].get("design")
        need(isinstance(block, dict), name, "missing key 'q3.comparisons.%s.design'" % design)
        for key in ("energy-distance", "energy-V", "energy-U"):
            need(key in block, name, "missing key 'q3.comparisons.%s.design.%s'" % (design, key))
        values[design] = block

    raw_design = comparisons["copula-selected"].get("raw", {}).get("energy-distance")
    need(raw_design is not None, name, "missing key 'q3.comparisons.copula-selected.raw.energy-distance'")

    norm = [values[d]["energy-distance"] for d in designs]
    v_raw = [values[d]["energy-V"] for d in designs]
    u_raw = [values[d]["energy-U"] for d in designs]
    generated = values["copula-selected"]["energy-distance"]
    resample = values["source-resample"]["energy-distance"]
    need(resample < generated, name,
         "source-resample (%.6f) is expected to be BETTER (lower) than the generated design (%.6f); "
         "the artifact now says otherwise - do not silently redraw the claim" % (resample, generated))

    short = {
        "copula-selected": "generated design\n(copula-selected)",
        "copula-shared-only": "shared-correlation copula",
        "copula-style-empirical": "within-style empirical copula",
        "independent-marginals": "independent marginals",
        "source-resample": "source resample\n(no generation)",
    }
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.3), sharey=False)
    fig.subplots_adjust(wspace=0.52)
    y = np.arange(len(designs))[::-1]  # first design on top
    colors = [C_MAIN if d == "copula-selected" else (C_HL if d == "source-resample" else C_GREY) for d in designs]

    ax = axes[0]
    ax.barh(y, norm, 0.62, color=colors, edgecolor="white", linewidth=0.4, zorder=2)
    for position, value in zip(y, norm):
        ax.text(value + 0.008, position, "%.6f" % value, va="center", ha="left", fontsize=7.0)
    ax.axvline(resample, color=C_HL, linestyle="--", linewidth=1.0, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([short[d] for d in designs], fontsize=7.0)
    ax.set_xlim(0.0, max(norm) * 1.62)
    ax.set_xlabel("normalized empirical V energy distance\n(E_V_norm = V / D_train; lower is better)")
    ax.set_title("(a) normalized V - the reported metric", loc="left")
    ax.set_ylim(-0.65, 5.10)
    ax.text(max(norm) * 1.60, 5.02,
            "source resample %.6f\n< generated %.6f -> not better" % (resample, generated),
            ha="right", va="top", fontsize=6.6, color="#a05a10",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#fdf3e7", edgecolor="#e67e22", linewidth=0.6))

    ax = axes[1]
    ax.barh(y, v_raw, 0.62, color=colors, edgecolor="white", linewidth=0.4, zorder=2)
    for position, value in zip(y, v_raw):
        ax.text(value + 0.18, position, "%.4f" % value, va="center", ha="left", fontsize=7.0)
    ax.set_yticks(y)
    ax.set_yticklabels([])
    ax.set_xlim(0.0, max(v_raw) * 1.18)
    ax.set_xlabel("unsigned V energy distance\n(raw scale, un-normalized)")
    ax.set_title("(b) unsigned V (separate scale)", loc="left")

    ax = axes[2]
    ax.barh(y, u_raw, 0.62, color=colors, edgecolor="white", linewidth=0.4, zorder=2)
    for position, value in zip(y, u_raw):
        ax.text(value + 0.022, position, "%.4f" % value, va="center", ha="left", fontsize=7.0)
    ax.axvline(0.0, color="#222222", linewidth=0.8, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([])
    ax.set_xlim(0.0, max(u_raw) * 1.22)
    ax.set_xlabel("signed U diagnostic\n(never clipped, never sqrt-ed)")
    ax.set_title("(c) signed U (can be negative)", loc="left")

    fig.suptitle("Q3 generation quality - empirical energy distances by design (n_gen-weighted over 177 estimable cells, n_gen = 729)",
                 fontsize=9.6, fontweight="bold", y=1.03)
    note(fig, "V, U and the normalized V are three different quantities and are never mixed: (a) is the reported metric, "
              "(b) is the same V before dividing by D_train, (c) is the signed diagnostic U (values may be negative).\n"
              "The generated design spectrum is NOT better than the source-resampling reference: %.6f > %.6f. "
              "No truncated-U or sqrt(max(U,0)) variant is reported anywhere in this figure."
              % (generated, resample))
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题三：归一化经验 V 能量距离（V/D_train）对照；生成设计谱 %.4f 未优于源样本重采样 %.4f，带符号 U 单列不截零。"
                   % (generated, resample))
    return metadata(name, "EXP-0079", text, [f"{E79}/outputs.json"],
                    path=path, sha256=digest,
                    key_values={"design_norm": generated, "resample_norm": resample, "raw_design": raw_design,
                                "norm": dict(zip(designs, norm)), "V_raw": dict(zip(designs, v_raw)),
                                "U_signed": dict(zip(designs, u_raw))})


# ===========================================================================
# 7. Q3-per-style-energy - EXP-0079
# ===========================================================================
def fig_q3_per_style_energy():
    name = "Q3-per-style-energy"
    scope = load_json("outputs/q3/style_and_displacement_scope.json", name)
    need("energy_distance_pooling" in scope, name, "missing key 'energy_distance_pooling'")
    pooling = scope["energy_distance_pooling"]
    for key in ("definition", "all_estimable_styles", "tripel_kriek_lambic", "per_style"):
        need(key in pooling, name, "missing key 'energy_distance_pooling.%s'" % key)
    per_style = pooling["per_style"]
    all_styles = pooling["all_estimable_styles"]
    three = pooling["tripel_kriek_lambic"]

    # recompute every pooled number from the experiment's own per-cell metric table
    metrics_csv = load_csv(f"{E79}/q3_metrics.csv", name, low_memory=False)
    for column in ("stage", "model", "style", "n_gen", "E_V_norm", "n_excluded_from_energy"):
        need(column in metrics_csv.columns, name, "q3_metrics.csv lacks column %r" % column)
    cells = metrics_csv[(metrics_csv["stage"] == "design")
                        & (metrics_csv["model"] == "copula-selected")
                        & (metrics_csv["n_excluded_from_energy"] == 0)]
    need(len(cells) == int(all_styles["cells"]),
         name, "recomputed %d estimable cells but the scope file records %r" % (len(cells), all_styles["cells"]))
    weighted = float((cells["E_V_norm"] * cells["n_gen"]).sum() / cells["n_gen"].sum())
    check_value(name, "21-style pooled normalized V", weighted, all_styles["value"])
    need(abs(float(cells["n_gen"].sum()) - float(all_styles["n_gen"])) < 1e-9, name,
         "recomputed n_gen differs from the scope file")

    recomputed = {}
    for style, frame in cells.groupby("style"):
        recomputed[str(style)] = {
            "value": float((frame["E_V_norm"] * frame["n_gen"]).sum() / frame["n_gen"].sum()),
            "cells": int(len(frame)),
            "n_gen": float(frame["n_gen"].sum()),
        }
    need(set(recomputed) == set(per_style), name,
         "style sets differ: recompute %r vs scope file %r" % (sorted(recomputed), sorted(per_style)))
    for style in per_style:
        check_value(name, "pooled normalized V for %r" % style, recomputed[style]["value"],
                    per_style[style]["energy_distance_pooled"])
        need(recomputed[style]["cells"] == int(per_style[style]["cells"]), name,
             "cell count for %r differs from the scope file" % style)
        need(abs(recomputed[style]["n_gen"] - float(per_style[style]["n_gen"])) < 1e-9, name,
             "n_gen for %r differs from the scope file" % style)

    three_names = ["Tripel", "Kriek", "Lambic"]
    three_cells = cells[cells["style"].isin(three_names)]
    three_value = float((three_cells["E_V_norm"] * three_cells["n_gen"]).sum() / three_cells["n_gen"].sum())
    check_value(name, "three-style pooled normalized V", three_value, three["value"])
    need(len(three_cells) == int(three["cells"]), name, "three-style cell count differs from the scope file")
    need(abs(float(three_cells["n_gen"].sum()) - float(three["n_gen"])) < 1e-9, name, "three-style n_gen differs")

    styles = sorted(per_style, key=lambda s: recomputed[s]["value"])  # largest on top
    values = [recomputed[s]["value"] for s in styles]
    ns = [recomputed[s]["n_gen"] for s in styles]
    colors = [C_HL if s in three_names else C_MAIN for s in styles]

    fig, ax = plt.subplots(figsize=(9.4, 6.8))
    y = np.arange(len(styles))
    ax.barh(y, values, height=0.72, color=colors, edgecolor="white", linewidth=0.4, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(["%s (n_gen=%d)" % (s, int(n)) for s, n in zip(styles, ns)], fontsize=7.0)
    ax.set_xscale("log")
    ax.set_xlabel("n_gen-weighted mean normalized V energy distance (log scale, lower is better)")
    ax.set_xlim(min(values) * 0.72, max(values) * 4.6)
    ax.set_ylim(-0.7, len(styles) - 0.3)
    for index, value in enumerate(values):
        ax.text(value * 1.05, index, "%.4f" % value, va="center", fontsize=6.8)
    ax.axvline(float(all_styles["value"]), color=C_MAIN, linestyle="--", linewidth=1.1, zorder=3)
    ax.axvline(three_value, color=C_HL, linestyle="--", linewidth=1.1, zorder=3)
    ax.set_title("Q3 normalized energy distance per style (21 estimable styles), generated design spectrum\n"
                 "Tripel / Kriek / Lambic highlighted; the two pooled values are reported separately, never substituted")
    handles = [
        Patch(facecolor=C_MAIN, label="other 18 estimable styles"),
        Patch(facecolor=C_HL, label="Tripel / Kriek / Lambic (27 cells, n_gen=147)"),
        Line2D([0], [0], color=C_MAIN, linestyle="--", linewidth=1.1,
               label="21-style pooled %.6f (%d cells, n_gen=%d)"
                     % (float(all_styles["value"]), all_styles["cells"], int(all_styles["n_gen"]))),
        Line2D([0], [0], color=C_HL, linestyle="--", linewidth=1.1,
               label="three-style pooled %.6f (%d cells, n_gen=%d)"
                     % (three_value, three["cells"], int(three["n_gen"]))),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=6.9)
    note(fig, "Every bar is the n_gen-weighted mean of E_V_norm over that style's estimable (stage=design) cells; all 21 bars, the 21-style pool "
              "and the three-style pool are recomputed from experiments/EXP-0079/q3_metrics.csv and match the recorded scope file bit-for-bit.\n"
              "21 of 198 cells are excluded from the energy estimate (n_real or n_gen too small); the 21-style pool is NOT the three-style pool.")
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题三：逐风格 n_gen 加权能量距离（21 可估风格）；三风格池化 %.4f 与 21 风格池化 %.4f 分列标注、不得互替。"
                   % (three_value, float(all_styles["value"])))
    return metadata(name, "EXP-0079", text, ["outputs/q3/style_and_displacement_scope.json", f"{E79}/q3_metrics.csv"],
                    path=path, sha256=digest,
                    key_values={"pooled_21": float(all_styles["value"]), "pooled_three": three_value,
                                "n_styles": len(styles), "cells": int(all_styles["cells"])})


# ===========================================================================
# 8. Q3-transfer-shift - EXP-0080 (three separate quantity groups)
# ===========================================================================
def fig_q3_transfer_shift():
    name = "Q3-transfer-shift"
    transfers = load_csv(f"{E80}/transfers.csv", name, low_memory=False)
    constraints = load_csv(f"{E80}/transfer_constraints.csv", name, low_memory=False)
    scope = load_json("outputs/q3/style_and_displacement_scope.json", name)
    zrecompute = load_json("outputs/q3/zspace_recompute.json", name)
    zcentrescale = load_csv("outputs/q3/zspace_centrescale.csv", name)

    opt_cols = [c for c in transfers.columns if c.startswith("opt__chem__")]
    src_cols = [c for c in transfers.columns if c.startswith("src__chem__")]
    need(len(opt_cols) == 231 and len(src_cols) == 231, name,
         "expected 231 opt__chem__/src__chem__ columns, found %d/%d" % (len(opt_cols), len(src_cols)))
    column_names = [c[len("opt__chem__"):] for c in opt_cols]
    need([c[len("src__chem__"):] for c in src_cols] == column_names, name,
         "opt__chem__ and src__chem__ column order differs")
    for column in ("strategy", "l1_change_z", "mean_abs_change_z"):
        need(column in transfers.columns, name, "transfers.csv lacks column %r" % column)

    strategies = ["qp-quantile-anchor", "qp-source-anchor", "target-mean-projection", "source-fixed"]
    present = set(transfers["strategy"].unique())
    for strategy in strategies:
        need(strategy in present, name, "transfers.csv lacks strategy %r" % strategy)

    storage_arrays = {}
    z_arrays = {}
    for strategy in strategies:
        frame = transfers[transfers["strategy"] == strategy]
        need(len(frame) == 99, name, "strategy %r has %d rows, expected 99" % (strategy, len(frame)))
        delta = np.abs(frame[opt_cols].to_numpy(dtype=float) - frame[src_cols].to_numpy(dtype=float))
        storage_arrays[strategy] = {"max": delta.max(axis=0), "mean": delta.mean(axis=0)}
        z_arrays[strategy] = {
            "l1": frame["l1_change_z"].to_numpy(dtype=float),
            "mean_abs": frame["mean_abs_change_z"].to_numpy(dtype=float),
        }

    # the scope file publishes the stored |new - src| for the 4 bounded columns; it must match this recompute
    published = scope.get("transfer_displacement")
    need(isinstance(published, dict) and "per_column" in published, name,
         "missing key 'transfer_displacement.per_column' in the scope file")
    need(published.get("strategy") == "qp-quantile-anchor", name,
         "scope-file transfer_displacement is not for qp-quantile-anchor")
    for column, record in published["per_column"].items():
        need(column in column_names, name, "scope-file column %r is not a chemistry column" % column)
        index = column_names.index(column)
        check_value(name, "stored max |new-src| for %r" % column,
                    storage_arrays["qp-quantile-anchor"]["max"][index], record["max_abs_stored"], tol=1e-6)
        check_value(name, "stored mean |new-src| for %r" % column,
                    storage_arrays["qp-quantile-anchor"]["mean"][index], record["mean_abs_stored"], tol=1e-9)

    # z-space movement: row-level readings, with the independent replay as the audit
    need(zrecompute.get("passed") is True, name, "zspace_recompute.json is not passed=true")
    check_value(name, "z-space rows replayed", zrecompute.get("rows_checked"), 396, tol=0)
    check_value(name, "z-space rows mismatched", zrecompute.get("rows_mismatched"), 0, tol=0)
    need(len(zcentrescale) == 9, name, "zspace_centrescale.csv must hold 9 (repeat, fold) contexts, found %d" % len(zcentrescale))
    context_rows = zcentrescale["n_context_rows"].to_numpy(int)

    # constraint residual: clamp(after - bound, 0) for upper bounds, clamp(0 - after, 0) for lower_zero
    upper = constraints["bound_type"].str.startswith("upper")
    need(set(constraints["bound_type"].unique()) <= {"lower_zero", "upper_source_value", "upper_source_value_proxy"},
         name, "unexpected bound_type values: %r" % sorted(constraints["bound_type"].unique()))
    violation = np.where(upper,
                         np.clip(constraints["stored_after"] - constraints["bound_value"], 0.0, None),
                         np.clip(0.0 - constraints["stored_after"], 0.0, None))
    residual_gap = float(np.abs(violation - constraints["residual"].to_numpy(float)).max())
    need(residual_gap <= 1e-8, name,
         "transfer_constraints.csv residual is not clamp(new - src, 0) as declared (max gap %.3g)" % residual_gap)
    residual_by_strategy = {}
    for strategy in strategies:
        mask = constraints["strategy"] == strategy
        values = violation[mask.to_numpy()]
        residual_by_strategy[strategy] = {
            "rows": int(mask.sum()),
            "violations": int((values > 1e-12).sum()),
            "max": float(values.max()) if values.size else 0.0,
        }
        need(residual_by_strategy[strategy]["rows"] == 3762, name,
             "strategy %r has %d constraint records, expected 3762" % (strategy, residual_by_strategy[strategy]["rows"]))

    colors = {"qp-quantile-anchor": C_MAIN, "qp-source-anchor": C_ALT,
              "target-mean-projection": C_HL, "source-fixed": C_GREY}
    tick_labels = ["QP quantile anchor\n(delivered)", "QP source anchor", "target-mean projection\n(reference)", "source fixed\n(trivial control)"]

    def boxes(ax, data, log_floor_text=None):
        parts = ax.boxplot(data, widths=0.55, patch_artist=True, showfliers=True,
                           flierprops=dict(marker="o", markersize=1.6, markerfacecolor="#555555",
                                           markeredgecolor="none", alpha=0.5),
                           medianprops=dict(color="#111111", linewidth=1.1))
        for patch, strategy in zip(parts["boxes"], strategies):
            patch.set_facecolor(colors[strategy])
            patch.set_alpha(0.85)
            patch.set_edgecolor("#333333")
            patch.set_linewidth(0.6)
        ax.set_xticks(np.arange(1, len(strategies) + 1))
        ax.set_xticklabels(tick_labels, fontsize=6.3, rotation=18, ha="right")

    def symlog_axis(ax, linthresh, top):
        ax.set_yscale("symlog", linthresh=linthresh)
        ax.set_ylim(-0.35 * linthresh, top)
        ticks = [0.0] + [linthresh * 10 ** power for power in range(0, 8) if linthresh * 10 ** power < top]
        ax.set_yticks(ticks)

        def formatter(value, _position=None):
            if value == 0:
                return "0"
            if value >= 0.01:
                return ("%g" % value)
            return ("%.0e" % value)

        ax.yaxis.set_major_formatter(FuncFormatter(formatter))
        ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.grid(axis="y", color="#ececec", linewidth=0.5, zorder=0)
        ax.set_axisbelow(True)

    fig = plt.figure(figsize=(13.2, 7.6))
    grid = fig.add_gridspec(2, 3, hspace=0.50, wspace=0.30)

    storage_max_top = float(storage_arrays["qp-quantile-anchor"]["max"].max())
    storage_mean_top = float(storage_arrays["qp-quantile-anchor"]["mean"].max())
    z_l1_top = float(max(np.percentile(z_arrays[strategy]["l1"], 99.5) for strategy in strategies))
    z_mean_top = float(max(np.percentile(z_arrays[strategy]["mean_abs"], 99.5) for strategy in strategies))

    ax = fig.add_subplot(grid[0, 0])
    boxes(ax, [storage_arrays[s]["max"] for s in strategies])
    symlog_axis(ax, 0.01, storage_max_top * 1.6)
    ax.set_ylabel("|opt - src| per column\nMAX over 99 rows (stored units)")
    ax.set_title("(a1) storage displacement - per-column MAX", loc="left")

    ax = fig.add_subplot(grid[1, 0])
    boxes(ax, [storage_arrays[s]["mean"] for s in strategies])
    symlog_axis(ax, 0.01, storage_mean_top * 1.6)
    ax.set_ylabel("|opt - src| per column\nMEAN over 99 rows (stored units)")
    ax.set_title("(a2) storage displacement - per-column MEAN", loc="left")

    ax = fig.add_subplot(grid[0, 1])
    boxes(ax, [z_arrays[s]["mean_abs"] for s in strategies])
    symlog_axis(ax, 0.01, z_mean_top * 1.6)
    ax.set_ylabel("mean_abs_change_z per row\n(z units, dimensionless)")
    ax.set_title("(b1) z-space displacement - per-row MEAN", loc="left")

    ax = fig.add_subplot(grid[1, 1])
    boxes(ax, [z_arrays[s]["l1"] for s in strategies])
    symlog_axis(ax, 0.1, z_l1_top * 1.6)
    ax.set_ylabel("l1_change_z per row (sum over 231 dims)\n(z units, dimensionless)")
    ax.set_title("(b2) z-space displacement - per-row L1", loc="left")

    ax = fig.add_subplot(grid[0, 2])
    counts = [residual_by_strategy[s]["violations"] for s in strategies]
    ax.bar(np.arange(len(strategies)), counts, 0.6,
           color=[colors[s] for s in strategies], edgecolor="white", linewidth=0.4, zorder=2)
    for index, (strategy, count) in enumerate(zip(strategies, counts)):
        ax.text(index, max(counts) * 0.04 + count, "%d / %d" % (count, residual_by_strategy[strategy]["rows"]),
                ha="center", va="bottom", fontsize=6.9)
    ax.set_xticks(np.arange(len(strategies)))
    ax.set_xticklabels(tick_labels, fontsize=6.3, rotation=18, ha="right")
    ax.set_ylabel("records with residual > 1e-12")
    ax.set_ylim(0.0, max(counts) * 1.35 if max(counts) else 5.0)
    ax.set_title("(c1) constraint residual - violating records", loc="left")

    ax = fig.add_subplot(grid[1, 2])
    values = violation[violation > 1e-12]
    if values.size:
        ax.hist(values, bins=min(24, max(6, values.size // 3)), color=C_HL, edgecolor="white", linewidth=0.4, zorder=2)
    else:
        ax.text(0.5, 0.5, "no violating record", ha="center", va="center", transform=ax.transAxes)
    ax.set_xlabel("constraint residual clamp(new - src, 0)\n(stored-value units)")
    ax.set_ylabel("records")
    ax.set_title("(c2) residual magnitude (violating records only)", loc="left")
    ax.text(0.97, 0.95, "max %.6f\n%d violating records\n(QP arms: max %.1e)"
            % (float(violation.max()), int(values.size),
               max(residual_by_strategy[s]["max"] for s in strategies[:2])),
            transform=ax.transAxes, ha="right", va="top", fontsize=6.4,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#fdf3e7", edgecolor="#e67e22", linewidth=0.6))

    for x, title, subtitle in (
        (0.185, "(1) STORAGE-SPACE DISPLACEMENT", "|opt - src| in stored units: design movement, not a residual"),
        (0.505, "(2) Z-SPACE DISPLACEMENT", "dimensionless, fold-fitted centre / scale"),
        (0.83, "(3) CONSTRAINT RESIDUAL", "clamp(new - src, 0): bound violation, NOT a displacement"),
    ):
        fig.text(x, 1.005, title, ha="center", va="bottom", fontsize=8.6, fontweight="bold", color="#1a1a1a")
        fig.text(x, 0.968, subtitle, ha="center", va="bottom", fontsize=6.8, color="#444444")

    fig.suptitle("Q3 transfer (Pils/Lager -> Tripel, 11 sources x 9 folds = 396 rows): three quantities in three separate panels",
                 fontsize=9.8, fontweight="bold", y=1.06)
    top_columns = np.argsort(-storage_arrays["qp-quantile-anchor"]["max"])[:3]
    top_text = ", ".join("%s %.3f" % (column_names[i], storage_arrays["qp-quantile-anchor"]["max"][i])
                         for i in top_columns)
    note(fig, "The three groups are DIFFERENT quantities with different units and must not be merged into one curve: "
              "(1) stored-space displacement of the delivered vector, (2) z-space movement of the same vector, "
              "(3) violation of the declared bounds. A residual is not a new-minus-source displacement.\n"
              "Largest stored movements of the delivered arm: %s (trace compounds; the declared bounds are still satisfied).\n"
              "z-space: 9 (repeat, fold) contexts of %d-%d rows; %d/396 rows replay bit-for-bit (0 mismatch). "
              "Residual: %d of %d records per strategy; violations occur only in target-mean projection (stale_hops ridge proxy).\n"
              "Storage and residual panels share stored-value units (37 log10-calibrated + 194 linear columns, some floored)."
              % (top_text, int(context_rows.min()), int(context_rows.max()), int(zrecompute["rows_checked"]),
                 residual_by_strategy["target-mean-projection"]["violations"],
                 residual_by_strategy["target-mean-projection"]["rows"]),
         xy=(0.005, -0.055), size=6.5)
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题三：迁移三组量分面板——存储位移 |opt−src|、z 空间位移、约束残差 clamp(new−src,0)；残差非位移，按策略区分。")
    return metadata(name, "EXP-0080", text,
                    [f"{E80}/transfers.csv", f"{E80}/transfer_constraints.csv",
                     "outputs/q3/style_and_displacement_scope.json", "outputs/q3/zspace_recompute.json",
                     "outputs/q3/zspace_centrescale.csv"],
                    path=path, sha256=digest,
                    key_values={
                        "storage_max": {s: float(storage_arrays[s]["max"].max()) for s in strategies},
                        "storage_mean_of_means": {s: float(storage_arrays[s]["mean"].mean()) for s in strategies},
                        "z_mean_median": {s: float(np.median(z_arrays[s]["mean_abs"])) for s in strategies},
                        "residual": residual_by_strategy,
                        "z_rows_checked": int(zrecompute["rows_checked"]),
                    })


# ===========================================================================
# 9. ROB-summary - ROB-0011 / ROB-0008 / ROB-0009 / ROB-0010
# ===========================================================================
def fig_rob_summary():
    name = "ROB-summary"
    manifest = load_json("report/evidence_manifest.json", name)
    need("questions" in manifest, name, "evidence_manifest.json has no 'questions' block")
    order = [("Q1", "ROB-0011"), ("Q2", "ROB-0008"), ("Q3gen", "ROB-0009"), ("Q3mig", "ROB-0010")]
    labels = {
        "ROB-0011": "ROB-0011  Q1\nA/F30 MAE",
        "ROB-0008": "ROB-0008  Q2\nTop-3 Jaccard",
        "ROB-0009": "ROB-0009  Q3 generation\nnormalized V",
        "ROB-0010": "ROB-0010  Q3 transfer\nnon-increase rate",
    }
    roles = ["reference", "seed block\n(repeat 1)", "param / budget\nperturbation"]

    groups = []
    for question_key, rob_id in order:
        need(question_key in manifest["questions"], name, "manifest lacks question %r" % question_key)
        plan = manifest["questions"][question_key].get("robustnessPlan")
        need(isinstance(plan, dict), name, "manifest %s has no robustnessPlan" % question_key)
        need(plan.get("robId") == rob_id, name, "manifest %s robustnessPlan is %r, expected %r"
             % (question_key, plan.get("robId"), rob_id))
        need(list(plan.get("experimentIds", [])) == ROB_EXPS[rob_id], name,
             "%s experimentIds %r differ from the expectation %r"
             % (rob_id, plan.get("experimentIds"), ROB_EXPS[rob_id]))
        metric_key = plan.get("metricKey")
        need(bool(metric_key), name, "%s has no metricKey" % rob_id)
        rule = plan.get("decisionRule")
        need(isinstance(rule, dict) and "type" in rule, name, "%s has no decisionRule.type" % rob_id)
        recorded = [float(value) for value in plan["values"]]
        need(len(recorded) == 3, name, "%s lists %d values, expected 3" % (rob_id, len(recorded)))
        recomputed = []
        for experiment in ROB_EXPS[rob_id]:
            record = load_json(f"experiments/{experiment}/metrics.json", name)
            recomputed.append(float(metric(record, metric_key, f"experiments/{experiment}/metrics.json", name)))
        for experiment, value, record in zip(ROB_EXPS[rob_id], recomputed, recorded):
            check_value(name, "%s %s.%s" % (rob_id, experiment, metric_key), value, record)
        absolute = max(recomputed) - min(recomputed)
        check_value(name, "%s recorded spread (equal to the absolute spread)" % rob_id, absolute, float(plan["spread"]))
        rule_type = str(rule["type"])
        if rule_type == "relative-range":
            reference = abs(recomputed[0])
            need(reference > 0.0, name, "%s reference value is 0, cannot form a relative spread" % rob_id)
            relative = absolute / reference
            limit = float(rule["limit"])
        elif rule_type == "min-value":
            relative = None
            limit = float(rule["limit"])
        else:
            raise NamedFailure("[%s] unsupported decision rule type %r for %s" % (name, rule_type, rob_id))
        groups.append({
            "robId": rob_id,
            "question": question_key,
            "metricKey": metric_key,
            "ruleType": rule_type,
            "limit": limit,
            "values": recomputed,
            "absolute": absolute,
            "relative": relative,
        })

    # the transfer-side spread is 0 because the metric is saturated at its ceiling, not because of an improvement
    transfer = next(group for group in groups if group["robId"] == "ROB-0010")
    need(transfer["ruleType"] == "min-value", name, "ROB-0010 rule changed away from min-value; the saturation note would be wrong")
    need(all(abs(value - transfer["limit"]) < 1e-12 for value in transfer["values"]), name,
         "ROB-0010 values are no longer all at the min-value limit %r" % transfer["limit"])

    fig, ax = plt.subplots(figsize=(11.6, 5.6))
    width = 0.34
    x = np.arange(len(groups))
    absolute = [group["absolute"] for group in groups]
    relative = [group["relative"] if group["relative"] is not None else 0.0 for group in groups]
    ax.bar(x - width / 2, absolute, width, color=C_MAIN, edgecolor="white", linewidth=0.4,
           label="absolute range (max - min, metric units)", zorder=2)
    ax.bar(x + width / 2, relative, width, color=C_HL, edgecolor="white", linewidth=0.4,
           label="TRUE relative range (absolute / reference value)", zorder=2)
    for position, value in zip(x - width / 2, absolute):
        if value > 0:
            ax.text(position, value + 0.0018, "%.6f" % value, ha="center", va="bottom", fontsize=6.9)
    for position, value in zip(x + width / 2, relative):
        if value > 0:
            ax.text(position, value + 0.0018, "%.6f" % value, ha="center", va="bottom", fontsize=6.9, color="#a05a10")
    for position, group in zip(x, groups):
        if group["ruleType"] == "relative-range":
            ax.plot([position + width / 2 - width * 0.62, position + width / 2 + width * 0.62],
                    [group["limit"], group["limit"]], color="#c0392b", linewidth=1.8, zorder=4,
                    solid_capstyle="butt")
            ax.text(position + width / 2 + width * 0.70, group["limit"],
                    "pre-registered limit %.2f" % group["limit"], va="center", ha="left",
                    fontsize=6.6, color="#c0392b")
        else:
            ax.text(position, 0.004, "all three = %.3f\nabsolute = relative = 0.000000\nrange 0 = ceiling saturation\n(min-value rule, limit %.1f)"
                    % (group["values"][0], group["limit"]), ha="center", va="bottom", fontsize=6.6, color="#c0392b")
    ax.set_xticks(x)
    ax.set_xticklabels(["%s\n%s" % (labels[group["robId"]], " / ".join("%.6f" % value for value in group["values"]))
                        for group in groups], fontsize=6.9)
    ax.set_ylabel("range of the three pre-registered runs")
    ax.set_ylim(0.0, max(max(absolute), max(relative), 0.11) * 1.26)
    ax.set_xlim(-0.55, len(groups) - 0.25)
    ax.grid(axis="y", color="#ececec", linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title("Robustness summary - absolute range vs the TRUE relative range, next to each plan's pre-registered limit\n"
                 "NOTE: the ledger's 'relative spread' field equals the ABSOLUTE range (plugin denominator = 1); the orange bars are the real ratio")
    ax.legend(loc="upper left", fontsize=7.2)
    notes = (
        "Seeds: every plan uses only 2 of the 3 frozen seeds (repeat 0 reference + repeat 1 seed block).\n"
        "ROB-0008 third arm is a BUDGET perturbation (bootstrap 500 -> 200): it changes Monte-Carlo precision, not the selection rule.\n"
        "ROB-0010 is saturated: non-increase rate = 1.000 in all three runs, so range 0 is a ceiling artefact and is NOT an improvement.\n"
        "Each range describes its own perturbation set only; the four plans are not pooled into one stability verdict."
    )
    note(fig, notes, xy=(0.005, -0.055), size=6.7)
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "四组稳健性：绝对极差与真实相对极差并排、各自预注册上限；仅2/3冻结种子，含预算扰动与迁移侧饱和（极差0非改善）。")
    return metadata(name, None, text,
                    ["report/evidence_manifest.json"]
                    + [f"experiments/{e}/metrics.json" for rob in ROB_EXPS.values() for e in rob],
                    path=path, sha256=digest,
                    key_values=groups)


# ===========================================================================
FIGURES = {
    "Q1-per-target-skill": fig_q1_per_target_skill,
    "Q1-model-comparison": fig_q1_model_comparison,
    "Q1-grade-distribution": fig_q1_grade_distribution,
    "Q2-network": fig_q2_network,
    "Q2-stability": fig_q2_stability,
    "Q3-energy-comparison": fig_q3_energy_comparison,
    "Q3-per-style-energy": fig_q3_per_style_energy,
    "Q3-transfer-shift": fig_q3_transfer_shift,
    "ROB-summary": fig_rob_summary,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="build all nine confirmatory figures")
    group.add_argument("--one", metavar="NAME", help="build a single figure by PENDING-FIGURE name")
    group.add_argument("--list", action="store_true", help="list the figure names")
    args = parser.parse_args(argv)

    if args.list:
        for name in FIGURES:
            print(name)
        return 0

    style()
    names = list(FIGURES) if args.all else [args.one]
    if args.one and args.one not in FIGURES:
        print("NAMED FAILURE: unknown figure %r (known: %s)" % (args.one, ", ".join(FIGURES)), file=sys.stderr)
        return 2

    results = []
    status = 0
    for name in names:
        try:
            record = FIGURES[name]()
        except NamedFailure as failure:
            print("NAMED FAILURE: %s" % failure, file=sys.stderr)
            status = 2
            continue
        results.append(record)
        print(json.dumps({key: record[key] for key in ("name", "experimentId", "path", "sha256", "caption")},
                         ensure_ascii=False))
    if results:
        print(json.dumps({"built": len(results), "figures": [
            {"name": r["name"], "path": r["path"], "sha256": r["sha256"],
             "experimentId": r["experimentId"], "captionLength": len(r["caption"]),
             "caption": r["caption"], "inputs": r["inputs"], "keyValues": r.get("key_values")}
            for r in results]}, ensure_ascii=False, indent=1,
            default=lambda obj: obj.item() if hasattr(obj, "item") else str(obj)))
    return status


if __name__ == "__main__":
    sys.exit(main())
