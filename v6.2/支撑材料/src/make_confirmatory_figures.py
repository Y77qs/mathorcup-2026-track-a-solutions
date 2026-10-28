#!/usr/bin/env python3
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""make_confirmatory_figures.py - the 10 confirmatory figures of report/paper.md.

Every figure is generated from the CURRENT v6 rerun evidence only:

    experiments/EXP-0073 EXP-0074           (Q1 model + median baseline)
    experiments/EXP-0107                    (Q2 main: 200 frozen rows, 3 seeds x 500 bootstrap)
    experiments/EXP-0109                    (Q3 generation main)
    experiments/EXP-0110                    (Q3 transfer main)
    experiments/EXP-0100 EXP-0101 EXP-0102  (ROB-0011 Q1: repeat 0/1 + lambda x0.5)
    experiments/EXP-0125 EXP-0126           (ROB-0015 Q2: frozen-seed-block param-perturbation)
    experiments/EXP-0127 EXP-0128           (ROB-0016 Q3 generation, same plan kind)
    experiments/EXP-0129 EXP-0130           (ROB-0017 Q3 transfer, same plan kind)
    experiments/EXP-0131 EXP-0132 EXP-0133  (SUPPLEMENTARY repeat-2 blocks, NOT in the plan records)
    outputs/q2/attachment2_network/nodes.csv
    outputs/q2/attachment2_network/edges.csv
    outputs/q2/attachment2_network/component_summary.json
    outputs/q2/attachment2_network/stats.md
    data/clean/q2_chem_meta.json
    state/ledger.json                       (pre-registered robustness plans)

Historical evidence is NOT used any more: EXP-0075, EXP-0079, EXP-0080 and the
EXP-0089..EXP-0118 robustness blocks are superseded (that includes the never-run
ROB-0012 / ROB-0013 / ROB-0014 plans), as are the derived files
outputs/q3/style_and_displacement_scope.json and outputs/q3/zspace_recompute.json
(they were built from the old EXP-0079 / EXP-0080 runs).  The per-style and
transfer figures are rebuilt from the new experiments' own artifacts.

Hard rules enforced by this script:

* a missing input file, a missing metric key or an inconsistent value raises
  ``NamedFailure`` (non-zero exit, message names the figure and the missing key);
  nothing falls back to an older experiment and no number is replaced by 0;
* every experiment a figure is drawn from must have result.status == 'succeeded';
* every robustness plan the figures draw must be really executed (executedAt set,
  result.decisionRule.passed == true) and must link exactly the drawn experiments;
* numbers that the experiment itself also recorded (pooled MAE, pi_mean,
  per-style pooled energy distance, edgeCount, plan values/spread) are
  recomputed here and compared bit-for-bit (1e-9) with the recorded value;
* old PNG bytes are never reused: every figure is drawn from the artifacts into
  figures/confirmatory_v2/ (the old figures/confirmatory/ is left untouched);
* ROB-0015 / ROB-0016 / ROB-0017 are PARAM-PERTURBATION plans on the declared
  frozen-seed-block constant (SEEDS/repeat); their records hold n = 2 runs and
  the repeat-2 blocks are drawn only as clearly labelled supplementary evidence;
* in-figure text is ENGLISH only (no CJK font dependency); the Chinese caption
  is returned as metadata for the Lead to register through ``modeling_deliver``.

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
import re
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

FIGDIR = os.path.join(ROOT, "figures", "confirmatory_v2")

E73 = "experiments/EXP-0073"    # Q1 graph low-rank main model
E74 = "experiments/EXP-0074"    # Q1 per-target median baseline
E107 = "experiments/EXP-0107"   # Q2 main (frozen 200 rows, 3 seeds x 500 bootstrap)
E109 = "experiments/EXP-0109"   # Q3 generation main
E110 = "experiments/EXP-0110"   # Q3 transfer main

# v6 rerun robustness plans.  ROB-0015 / ROB-0016 / ROB-0017 are
# param-perturbation plans: the perturbed input is the declared protocol
# constant SEEDS/repeat (the frozen seed block), NOT a new seed draw and NOT a
# "multiple-seeds" plan.  Each plan record holds EXACTLY two post-plan runs
# (repeat-0 reference + repeat-1 block).  The repeat-2 blocks EXP-0131 /
# EXP-0132 / EXP-0133 were run afterwards as SUPPLEMENTARY evidence and are NOT
# part of the plan records, so figures must label them as such.
ROB_EXPS = {
    "ROB-0011": ["EXP-0100", "EXP-0101", "EXP-0102"],
    "ROB-0015": ["EXP-0125", "EXP-0126"],
    "ROB-0016": ["EXP-0127", "EXP-0128"],
    "ROB-0017": ["EXP-0129", "EXP-0130"],
}
ROB_SUPPLEMENT = {
    "ROB-0015": ["EXP-0131"],   # repeat-2 seed block, NOT in the ROB-0015 record
    "ROB-0016": ["EXP-0132"],   # repeat-2 seed block, NOT in the ROB-0016 record
    "ROB-0017": ["EXP-0133"],   # repeat-2 seed block, NOT in the ROB-0017 record
}
ROB_METRICS = {
    "ROB-0011": ("mae", "relative-range", 0.05),
    "ROB-0015": ("topk-jaccard", "relative-range", 0.10),
    "ROB-0016": ("energy-distance", "relative-range", 0.05),
    "ROB-0017": ("nonincrease-rate", "min-value", 1.0),
}
ROB_METHODS = {
    "ROB-0011": ("multiple-seeds", "param-perturbation"),
    "ROB-0015": ("param-perturbation",),
    "ROB-0016": ("param-perturbation",),
    "ROB-0017": ("param-perturbation",),
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


def require_succeeded(experiment: str, name: str) -> None:
    """A figure may only be drawn from an experiment the ledger recorded as succeeded."""
    result = load_json("experiments/%s/result.json" % experiment, name)
    need(
        result.get("status") == "succeeded",
        name,
        "%s result.status is %r, not 'succeeded'; refusing to draw it"
        % (experiment, result.get("status")),
    )


def robustness_plan(rob_id: str, name: str) -> dict:
    """Read the pre-registered robustness plan from the kernel ledger."""
    ledger = load_json("state/ledger.json", name)
    plans = (ledger.get("quality") or {}).get("robustnessPlans") or []
    need(isinstance(plans, list), name, "state/ledger.json quality.robustnessPlans is not a list")
    plan = None
    for item in plans:
        if isinstance(item, dict) and item.get("id") == rob_id:
            plan = item
            break
    need(plan is not None, name, "state/ledger.json has no robustness plan %r" % rob_id)
    need(bool(plan.get("metricKey")), name, "%s has no metricKey" % rob_id)
    rule = plan.get("decisionRule")
    need(
        isinstance(rule, dict) and rule.get("type") in ("relative-range", "min-value"),
        name,
        "%s has no supported decisionRule (%r)" % (rob_id, rule),
    )
    return plan


def manifest_plan(question_key: str, rob_id: str, name: str):
    """Cross-check against report/evidence_manifest.json only when it lists THIS plan."""
    path = P("report/evidence_manifest.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    plan = ((manifest.get("questions") or {}).get(question_key) or {}).get("robustnessPlan")
    if isinstance(plan, dict) and plan.get("robId") == rob_id:
        return plan
    return None


def robustness_readings(rob_id: str, question_key: str, name: str) -> dict:
    """Recompute the linked values; the plan must be really executed and decided."""
    plan = robustness_plan(rob_id, name)
    metric_key, rule_type, limit = ROB_METRICS[rob_id]
    need(plan["metricKey"] == metric_key, name, "%s metricKey is %r, expected %r"
         % (rob_id, plan["metricKey"], metric_key))
    need(tuple(sorted(plan.get("methods") or [])) == tuple(sorted(ROB_METHODS[rob_id])), name,
         "%s methods are %r, expected %r" % (rob_id, plan.get("methods"), list(ROB_METHODS[rob_id])))
    rule = plan["decisionRule"]
    need(rule.get("type") == rule_type, name, "%s decisionRule.type is %r, expected %r"
         % (rob_id, rule.get("type"), rule_type))
    need(close(rule.get("limit"), limit), name, "%s decisionRule.limit is %r, expected %r"
         % (rob_id, rule.get("limit"), limit))

    # a plan that was not really executed must never be drawn as evidence
    need(bool(plan.get("executedAt")), name,
         "%s has no executedAt (plan not executed); refusing to draw it" % rob_id)
    result = plan.get("result") or None
    need(isinstance(result, dict), name, "%s has no result block; refusing to draw it" % rob_id)
    decision = result.get("decisionRule") or {}
    need(decision.get("passed") is True, name,
         "%s result.decisionRule.passed is not true; refusing to draw it" % rob_id)

    experiments = ROB_EXPS[rob_id]
    values = []
    for experiment in experiments:
        require_succeeded(experiment, name)
        record = load_json("experiments/%s/metrics.json" % experiment, name)
        values.append(float(metric(record, metric_key, "experiments/%s/metrics.json" % experiment, name)))

    # executed plans must link exactly the experiments the figure draws
    registered = [str(item) for item in (plan.get("experimentIds") or [])]
    need(registered == experiments, name,
         "%s registered experimentIds %r differ from the expected %r" % (rob_id, registered, experiments))

    absolute = max(values) - min(values)
    relative = absolute / abs(values[0]) if (rule_type == "relative-range" and values[0] != 0.0) else None

    recorded_values = [float(item) for item in (result.get("values") or [])]
    need(len(recorded_values) == len(values), name,
         "%s result records %d values but %d experiments are linked"
         % (rob_id, len(recorded_values), len(values)))
    for experiment, value, recorded in zip(experiments, values, recorded_values):
        check_value(name, "%s %s %s" % (rob_id, experiment, metric_key), value, recorded)
    recorded_spread = result.get("spread")
    need(recorded_spread is not None, name, "%s result records no spread" % rob_id)
    recorded_spread = float(recorded_spread)
    if close(recorded_spread, absolute):
        convention = "absolute"
    elif relative is not None and close(recorded_spread, relative):
        convention = "relative"
    else:
        raise NamedFailure(
            "[%s] %s recorded spread %.12g is neither the absolute range %.12g nor the ratio %.12g"
            % (name, rob_id, recorded_spread, absolute, relative)
        )

    cross = manifest_plan(question_key, rob_id, name)
    if isinstance(cross, dict):
        cross_values = [float(item) for item in (cross.get("values") or [])]
        if len(cross_values) == len(values):
            for experiment, value, recorded in zip(experiments, values, cross_values):
                check_value(name, "%s manifest %s %s" % (rob_id, experiment, metric_key), value, recorded)

    return {
        "robId": rob_id,
        "question": question_key,
        "metricKey": metric_key,
        "ruleType": rule_type,
        "limit": limit,
        "values": values,
        "absolute": absolute,
        "relative": relative,
        "executed": True,
        "executedAt": plan.get("executedAt"),
        "decisionPassed": bool(decision.get("passed")),
        "plan": plan,
        "spreadConvention": convention,
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
# 4. Q2-network - EXP-0107 (recomputed from the registered inputs, tau = 0.5)
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
    require_succeeded("EXP-0107", name)
    outputs = load_json(f"{E107}/outputs.json", name)
    need("q2" in outputs, name, "missing top-level key 'q2' in %s/outputs.json" % E107)
    q2 = outputs["q2"]
    modules = q2.get("modules")
    need(isinstance(modules, dict), name, "missing key 'q2.modules' in %s/outputs.json" % E107)
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
    split_rel = f"{E107}/inputs/data/splits/SPLIT-0001/train.csv"
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
    ax2.annotate("%d-node component\n(density %d/%d)" % (largest, len(pairs), largest * (largest - 1) // 2),
                 xy=(0, ordered[0]), xytext=(8, ordered[0] * 0.55),
                 fontsize=6.7, arrowprops=dict(arrowstyle="->", color="#555555", lw=0.7))
    small = ", ".join("%d x size-%d" % (int((sizes == size).sum()), size)
                      for size in sorted(set(sizes.tolist()) - {1, largest}, reverse=True))
    ax2.text(len(ordered) * 0.52, 1.25,
             "%d isolated nodes\n%s" % (singles, small),
             fontsize=6.9, ha="center", va="bottom")
    ax2.grid(axis="y", color="#e6e6e6", linewidth=0.5, zorder=0)
    ax2.set_axisbelow(True)

    note(fig, "Tau = 0.5 Spearman threshold graph (|rho| >= 0.5) on the 231 registered chemistry columns, 200 SPLIT-0001 training rows.\n"
              "Highest-degree nodes (degree): %s.\n" % hub_text +
              "RECOMPUTED from the EXP-0107 registered inputs and it reproduces the experiment's recorded topology exactly "
              "(%d edges / %d components / %d largest).\n" % (edges, n_components, largest) +
              "Red edges are negative associations, grey are positive. An edge is a same-sample association, NOT a causal or mechanistic link.\n"
              "Candidate universes: 216 strict single compounds + 15 extended indicators (3 element/index + 7 physical + 5 derived sums).")
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题二：τ=0.5 Spearman 阈值网络（由 EXP-0107 注册输入重算，复现 %d 边/%d 分量）；严格单体216与扩展15分色，边非因果。"
                   % (edges, n_components))
    return metadata(name, "EXP-0107", text,
                    [f"{E107}/outputs.json", split_rel, "data/clean/q2_chem_meta.json"],
                    path=path, sha256=digest,
                    key_values={"edges": edges, "components": n_components, "largest": largest,
                                "negative_edges": int((weight < 0).sum() // 2),
                                "reclassified": reclassified})


# ===========================================================================
# 4b. Q2-attachment2-network - descriptive 231-node attachment-2 network
# ===========================================================================
ATT2_KIND_LABELS = {
    "single_compound": "single compound",
    "element_or_index": "element / index",
    "physical_parameter": "physical parameter",
    "derived_sum": "derived sum",
}


def fig_q2_attachment2_network():
    name = "Q2-attachment2-network"
    nodes = load_csv("outputs/q2/attachment2_network/nodes.csv", name)
    edges = load_csv("outputs/q2/attachment2_network/edges.csv", name)
    summary = load_json("outputs/q2/attachment2_network/component_summary.json", name)
    stats_rel = "outputs/q2/attachment2_network/stats.md"
    stats_path = P(stats_rel)
    need(os.path.exists(stats_path), name, "missing input file %r" % stats_rel)
    with open(stats_path, "r", encoding="utf-8") as handle:
        stats_text = handle.read()

    for column in ("nodeId", "feature", "kind", "moduleId", "moduleSize", "degree", "placement", "x", "y"):
        need(column in nodes.columns, name, "nodes.csv lacks column %r" % column)
    for column in ("sourceIndex", "targetIndex", "rho", "sign"):
        need(column in edges.columns, name, "edges.csv lacks column %r" % column)
    need(set(nodes["kind"].unique()) <= set(CAT_COLORS), name,
         "nodes.csv kinds %r are not all in the declared palette" % sorted(nodes["kind"].unique()))

    nodes = nodes.sort_values("nodeId").reset_index(drop=True)
    node_count = len(nodes)
    edge_count = len(edges)
    check_value(name, "node count", node_count, int(summary["nodeCount"]), tol=0)
    check_value(name, "edge count", edge_count, int(summary["edgeCount"]), tol=0)
    need(summary.get("matchesExpected") is True, name, "component_summary.json does not record matchesExpected=true")
    for key in ("nodes", "edges", "components", "largestComponent"):
        need(int(summary["expected"][key]) == int(summary["actual"][key]), name,
             "component_summary.json expected/actual differ on %r" % key)
    need(list(nodes["nodeId"].to_numpy(int)) == list(range(node_count)), name,
         "nodes.csv nodeId is not 0..n-1")
    need(edges["sourceIndex"].between(0, node_count - 1).all()
         and edges["targetIndex"].between(0, node_count - 1).all(), name,
         "edges.csv references a nodeId outside 0..%d" % (node_count - 1))
    need(bool((edges["sourceIndex"] < edges["targetIndex"]).all()), name,
         "edges.csv is not stored with i < j (a self-loop or a duplicated direction would break the count)")

    positive = int((edges["sign"] == "positive").sum())
    negative = int((edges["sign"] == "negative").sum())
    check_value(name, "positive edges", positive, int(summary["positiveEdges"]), tol=0)
    check_value(name, "negative edges", negative, int(summary["negativeEdges"]), tol=0)
    sign_matches = int((np.sign(edges["rho"].to_numpy(float)) == np.where(edges["sign"] == "negative", -1.0, 1.0)).sum())
    need(sign_matches == edge_count, name, "edges.csv sign does not match the sign of rho")
    need(float(edges["absRho"].min()) >= 0.5, name,
         "edges.csv holds an edge below the declared |rho| >= 0.5 threshold")

    # connected components recomputed from the stored edge list
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    adjacency = np.zeros((node_count, node_count), dtype=np.int8)
    adjacency[edges["sourceIndex"].to_numpy(int), edges["targetIndex"].to_numpy(int)] = 1
    adjacency = ((adjacency + adjacency.T) > 0).astype(np.int8)
    n_components, labels = connected_components(csr_matrix(adjacency))
    sizes = np.bincount(labels)
    check_value(name, "component count", n_components, int(summary["nComponents"]), tol=0)
    check_value(name, "largest component size", int(sizes.max()), int(summary["largestComponentSize"]), tol=0)
    need(list(np.sort(sizes)[::-1]) == [int(item) for item in summary["componentSizesDescending"]], name,
         "recomputed component-size spectrum differs from component_summary.json")

    degree = adjacency.sum(axis=0).astype(int)
    need(list(degree) == list(nodes["degree"].to_numpy(int)), name,
         "recomputed node degree differs from nodes.csv degree")
    need(np.isfinite(nodes[["x", "y"]].to_numpy(float)).all(), name, "nodes.csv x/y holds non-finite values")
    placement = nodes["placement"].value_counts().to_dict()
    check_value(name, "largest-component nodes", int(placement.get("largest", 0)),
                int(summary["largestComponentSize"]), tol=0)
    check_value(name, "isolated nodes", int(placement.get("isolated", 0)),
                int(summary["isolatedNodes"]), tol=0)
    need(sum(value for key, value in placement.items() if key != "largest")
         == node_count - int(summary["largestComponentSize"]), name,
         "placement counts do not add up to the component sizes")

    def stats_measured(label):
        match = re.search(r"^\|\s*%s\s*\|\s*(\d+)\s*\|" % label, stats_text, re.MULTILINE)
        need(match is not None, name, "stats.md lacks the %r row" % label)
        return int(match.group(1))

    check_value(name, "stats.md node count", stats_measured("节点数"), node_count, tol=0)
    check_value(name, "stats.md edge count", stats_measured("边数"), edge_count, tol=0)
    check_value(name, "stats.md component count", stats_measured("连通分量数"), n_components, tol=0)
    check_value(name, "stats.md largest component", stats_measured("最大分量规模"), int(sizes.max()), tol=0)

    kinds_present = [kind for kind in ("single_compound", "element_or_index", "physical_parameter", "derived_sum")
                     if (nodes["kind"] == kind).any()]
    kind_counts = {kind: int((nodes["kind"] == kind).sum()) for kind in kinds_present}
    node_colors = [CAT_COLORS[kind] for kind in nodes["kind"]]

    fig = plt.figure(figsize=(12.6, 6.0))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.95, 1.0], wspace=0.14)
    ax = fig.add_subplot(grid[0, 0])
    x = nodes["x"].to_numpy(float)
    y = nodes["y"].to_numpy(float)
    for _, edge in edges.iterrows():
        i, j = int(edge["sourceIndex"]), int(edge["targetIndex"])
        negative_edge = edge["sign"] == "negative"
        ax.plot([x[i], x[j]], [y[i], y[j]],
                color="#c0392b" if negative_edge else "#9e9e9e",
                alpha=0.62 if negative_edge else 0.18,
                linewidth=1.3 if negative_edge else 0.45,
                zorder=1, solid_capstyle="round")
    ax.scatter(x, y, s=5.0 + 2.3 * degree, c=node_colors, edgecolors="white", linewidths=0.4, zorder=3)
    hubs = np.argsort(-degree)[:6]
    hub_text = ", ".join("%s (%d)" % (nodes["feature"].iloc[int(index)], int(degree[int(index)])) for index in hubs)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("(a) descriptive attachment-2 network (%d nodes, %d edges, %d components)"
                 % (node_count, edge_count, n_components), loc="left")
    handles = [Patch(facecolor=CAT_COLORS[kind], label="%s (%d)" % (ATT2_KIND_LABELS[kind], kind_counts[kind]))
               for kind in kinds_present]
    handles += [Line2D([0], [0], color="#c0392b", linewidth=1.4, label="negative edge (rho <= -0.5): %d" % negative),
                Line2D([0], [0], color="#9e9e9e", linewidth=0.8, label="positive edge (rho >= 0.5): %d" % positive)]
    ax.legend(handles=handles, loc="lower left", fontsize=6.4, ncol=1)

    ax2 = fig.add_subplot(grid[0, 1])
    ordered = np.sort(sizes)[::-1]
    ax2.bar(np.arange(len(ordered)), ordered, color=C_MAIN, width=0.8, zorder=2)
    ax2.set_yscale("log")
    ax2.set_xlabel("component index (sorted by size)")
    ax2.set_ylabel("component size (nodes, log scale)")
    ax2.set_title("(b) component-size spectrum (%d components)" % n_components, loc="left")
    ax2.set_ylim(0.7, max(ordered) * 1.9)
    ax2.annotate("%d-node component" % int(ordered[0]), xy=(0, ordered[0]), xytext=(8, ordered[0] * 0.55),
                 fontsize=6.7, arrowprops=dict(arrowstyle="->", color="#555555", lw=0.7))
    small = ", ".join("%d x size-%d" % (int((sizes == size).sum()), size)
                      for size in sorted(set(sizes.tolist()) - {1, int(ordered[0])}, reverse=True))
    ax2.text(len(ordered) * 0.52, 1.25, "%d isolated nodes\n%s" % (int(placement.get("isolated", 0)), small),
             fontsize=6.9, ha="center", va="bottom")
    ax2.grid(axis="y", color="#e6e6e6", linewidth=0.5, zorder=0)
    ax2.set_axisbelow(True)

    note(fig, "Descriptive |rho| >= 0.5 network from the attachment-2 231x231 correlation matrix (signs kept); the layout is read from nodes.csv x/y, so it is deterministic.\n"
              "Highest-degree features (degree): %s.\n" % hub_text +
              "NOT used for any Top-3 selection and NOT an independent external validation: the predictive graph is rebuilt inside every training fold / bootstrap resample in q2_fix.py, "
              "so the full-sample matrix never enters validation.\n"
              "Node colour = candidate category, node size = degree; red edges = negative association, grey = positive. "
              "Counts are cross-checked against component_summary.json and stats.md (%d nodes / %d edges / %d components / %d largest)."
              % (node_count, edge_count, n_components, int(ordered[0])))
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题二附件2：描述性化学相关网络（231 节点/645 边/52 分量，x/y 取自 nodes.csv）；仅解释网络结构，预测训练图仍在训练折内构建。")
    return metadata(name, None, text,
                    ["outputs/q2/attachment2_network/nodes.csv",
                     "outputs/q2/attachment2_network/edges.csv",
                     "outputs/q2/attachment2_network/component_summary.json",
                     stats_rel],
                    path=path, sha256=digest,
                    key_values={"nodes": node_count, "edges": edge_count, "components": n_components,
                                "largest": int(ordered[0]), "positive_edges": positive,
                                "negative_edges": negative, "isolated_nodes": int(placement.get("isolated", 0)),
                                "kinds": kind_counts, "hubs": [nodes["feature"].iloc[int(i)] for i in hubs]})


# ===========================================================================
# 5. Q2-stability - EXP-0107 (+ ROB-0015 frozen-seed-block perturbation)
# ===========================================================================
def fig_q2_stability():
    name = "Q2-stability"
    require_succeeded("EXP-0107", name)
    metrics = load_json(f"{E107}/metrics.json", name)
    outputs = load_json(f"{E107}/outputs.json", name)
    q2 = outputs["q2"]
    for key in ("per_repeat", "stability", "jaccard"):
        need(key in q2, name, "missing key 'q2.%s' in %s/outputs.json" % (key, E107))

    frames = []
    for repeat in range(3):
        frame = load_csv(f"{E107}/repeat{repeat}/strict_top3_by_method.csv", name)
        for column in ("dimension", "method", "rank", "compound", "pi", "sign_stability",
                       "p_positive", "p_positive_legacy", "direction",
                       "alternative_rank4", "evidence_status"):
            need(column in frame.columns, name, "repeat%d/strict_top3_by_method.csv lacks column %r" % (repeat, column))
        frame["repeat"] = repeat
        frames.append(frame)
    board = pd.concat(frames, ignore_index=True)
    need(len(board) == 1800, name, "expected 1800 delivered strict entries (600 x 3 repeats), found %d" % len(board))

    pi_mean = float(board["pi"].mean())
    below = int((board["pi"] < 0.5).sum())
    sign_mean = float(board["sign_stability"].mean())
    legacy_mean = float(board["p_positive_legacy"].mean())
    check_value(name, "pi_mean", pi_mean, metric(metrics, "pi_mean", f"{E107}/metrics.json", name))
    check_value(name, "pi_below_0.5_count", below, metric(metrics, "pi_below_0.5_count", f"{E107}/metrics.json", name))
    check_value(name, "sign_stability_mean (point-direction agreement)", sign_mean,
                metric(metrics, "sign_stability_mean", f"{E107}/metrics.json", name))
    check_value(name, "sign_stability_legacy_mean (legacy p_positive rule)", legacy_mean,
                metric(metrics, "sign_stability_legacy_mean", f"{E107}/metrics.json", name))
    denominator = int(metric(metrics, "pi_below_0.5_denominator", f"{E107}/metrics.json", name))
    need(denominator == len(board), name, "pi denominator %d != %d delivered entries" % (denominator, len(board)))
    need(int((board["pi"] >= 1.0).sum()) == 0, name,
         "at least one delivered entry reaches pi = 1.0; the panel text would be false")

    third_counts = []
    per_repeat_jaccard = []
    per_repeat_seed = {}
    for repeat in range(3):
        block = q2["per_repeat"].get("rep%d" % repeat)
        need(isinstance(block, dict), name, "missing 'q2.per_repeat.rep%d'" % repeat)
        third_counts.append(int(block.get("thirdPlaceUnstableCount", -1)))
        per_repeat_jaccard.append(float(metric(block, "topk-jaccard", "q2.per_repeat.rep%d" % repeat, name)))
        per_repeat_seed[int(metric(block, "seed", "q2.per_repeat.rep%d" % repeat, name))] = repeat
    need(all(value >= 0 for value in third_counts), name, "per_repeat is missing thirdPlaceUnstableCount")
    check_value(name, "pooled topk-jaccard vs the mean of the three repeats",
                float(np.mean(per_repeat_jaccard)), metric(metrics, "topk-jaccard", f"{E107}/metrics.json", name))

    # ROB-0015: param-perturbation on the declared frozen-seed-block constant
    # (SEEDS/repeat).  The plan record holds exactly TWO post-plan runs
    # (repeat 0 reference + repeat 1 block).  The repeat-2 block EXP-0131 is a
    # supplementary run that is NOT in the plan record, so it is drawn apart.
    rob = robustness_readings("ROB-0015", "Q2", name)
    need(rob["ruleType"] == "relative-range", name, "ROB-0015 is no longer a relative-range plan")
    seeds = []
    for experiment in ROB_EXPS["ROB-0015"]:
        record = load_json(f"experiments/{experiment}/metrics.json", name)
        seeds.append(int(metric(record, "seed", f"experiments/{experiment}/metrics.json", name)))
    need(len(set(seeds)) == len(ROB_EXPS["ROB-0015"]), name,
         "ROB-0015 must span %d distinct frozen seeds, found %r" % (len(ROB_EXPS["ROB-0015"]), seeds))
    for experiment, seed in zip(ROB_EXPS["ROB-0015"], seeds):
        need(seed in per_repeat_seed, name, "%s seed %d is not one of EXP-0107's frozen seeds" % (experiment, seed))
        repeat = per_repeat_seed[seed]
        record = load_json(f"experiments/{experiment}/metrics.json", name)
        check_value(name, "%s topk-jaccard vs EXP-0107 repeat %d" % (experiment, repeat),
                    float(metric(record, "topk-jaccard", f"experiments/{experiment}/metrics.json", name)),
                    per_repeat_jaccard[repeat])

    supplement_experiment = ROB_SUPPLEMENT["ROB-0015"][0]
    require_succeeded(supplement_experiment, name)
    supplement_metrics = load_json(f"experiments/{supplement_experiment}/metrics.json", name)
    supplement_jaccard = float(metric(supplement_metrics, "topk-jaccard",
                                      f"experiments/{supplement_experiment}/metrics.json", name))
    supplement_seed = int(metric(supplement_metrics, "seed",
                                 f"experiments/{supplement_experiment}/metrics.json", name))
    need(supplement_seed in per_repeat_seed, name,
         "%s seed %d is not one of EXP-0107's frozen seeds" % (supplement_experiment, supplement_seed))
    supplement_repeat = per_repeat_seed[supplement_seed]
    need(supplement_repeat not in [per_repeat_seed[seed] for seed in seeds], name,
         "the supplementary block repeats a seed that is already in the ROB-0015 record")
    check_value(name, "%s topk-jaccard vs EXP-0107 repeat %d" % (supplement_experiment, supplement_repeat),
                supplement_jaccard, per_repeat_jaccard[supplement_repeat])

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 7.9))
    fig.subplots_adjust(hspace=0.72, wspace=0.30)

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
    span = 1.30
    box_width = 0.40
    for offset, method in enumerate(methods):
        center = offset * span
        for j, (column, face, hatch) in enumerate(
                (("sign_stability", colors[method], None),
                 ("p_positive_legacy", "#d9d9d9", "///"))):
            data = board.loc[board["method"] == method, column].to_numpy()
            parts = ax.boxplot([data], positions=[center + (-box_width / 2 if j == 0 else box_width / 2)],
                               widths=box_width * 0.92, patch_artist=True, showfliers=False,
                               medianprops=dict(color="#222222", linewidth=1.0))
            patch = parts["boxes"][0]
            patch.set_facecolor(face)
            patch.set_alpha(0.90)
            patch.set_edgecolor("#444444")
            patch.set_linewidth(0.6)
            if hatch is not None:
                patch.set_hatch(hatch)
    ax.axhline(sign_mean, color=C_HL, linewidth=1.3, zorder=3)
    ax.axhline(legacy_mean, color=C_REF, linestyle="--", linewidth=1.0, zorder=3)
    ax.set_xticks([offset * span for offset in range(len(methods))])
    ax.set_xticklabels([labels[m] for m in methods], fontsize=6.8)
    ax.set_xlim(-0.7, (len(methods) - 1) * span + 0.7)
    ax.set_ylabel("share of the 500 bootstrap replicates")
    ax.set_ylim(-0.03, 1.10)
    handles = [
        Patch(facecolor="#777777", label="sign_stability: agrees with the point direction (mean %.4f)" % sign_mean),
        Patch(facecolor="#d9d9d9", hatch="///", label="p_positive: legacy rho > 0 rule (mean %.4f)" % legacy_mean),
    ]
    ax.legend(handles=handles, loc="lower center", fontsize=6.3, ncol=1, frameon=True,
              facecolor="white", framealpha=0.93, edgecolor="#dddddd")
    ax.set_title("(c) sign consistency: point direction vs legacy p_positive", loc="left")

    ax = axes[1, 1]
    plan_values = list(rob["values"])
    positions = np.arange(len(plan_values) + 1)
    bar_values = plan_values + [supplement_jaccard]
    ax.bar(positions[:len(plan_values)], plan_values, 0.58, color=[C_MAIN, C_ALT][:len(plan_values)],
           edgecolor="white", linewidth=0.4, zorder=2)
    ax.bar([positions[-1]], [supplement_jaccard], 0.58, color="#d9d9d9", edgecolor="#7f7f7f",
           linewidth=0.7, hatch="///", zorder=2)
    for x, v in zip(positions, bar_values):
        ax.text(x, v + 0.0012, "%.6f" % v, ha="center", va="bottom", fontsize=7.4)
    tick = ["repeat-0 reference\nseed %d (EXP-0125)" % seeds[0],
            "plan block\nseed %d (EXP-0126)" % seeds[1],
            "supplementary\nseed %d (EXP-0131)\nNOT in the plan" % supplement_seed]
    ax.set_xticks(positions)
    ax.set_xticklabels(tick, fontsize=6.6)
    ax.set_ylim(0.0, max(bar_values) * 1.52)
    ax.set_ylabel("Q2 Top-3 pooled Jaccard (ROB-0015 metric)")
    ax.set_title("(d) frozen-seed-block perturbation (ROB-0015, param-perturbation)", loc="left")
    ax.text(1.0, max(bar_values) * 1.34,
            "ROB-0015 plan: n = %d\nabsolute range %.6f\nratio to reference %.6f\npre-registered limit %.2f"
            % (len(plan_values), rob["absolute"], rob["relative"], rob["limit"]),
            ha="center", va="center", fontsize=6.8,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f7f7f7", edgecolor="#b0b0b0", linewidth=0.6))

    fig.suptitle("Q2 Top-3 selection stability - 500 style-stratified bootstrap replicates (ROB-0015: frozen-seed-block perturbation, plan n = %d + 1 supplementary block)"
                 % len(plan_values), fontsize=9.6, fontweight="bold", y=0.99)
    note(fig, "pi is the share of bootstrap replicates in which an entry survives in the delivered Top-3; it is a stability statistic, not a p-value.\n"
              "sign_stability = share of replicates whose signed rho agrees with the POINT-ESTIMATE direction; p_positive (legacy) = share of replicates with rho > 0.\n"
              "The two readouts differ because %d of the 1800 delivered entries have a negative point direction: for those, p_positive is near 0 while sign_stability can be near 1.\n"
              % int((board["direction"] == "negative").sum()) +
              "pi = 0.5 is drawn as a reference line only - no threshold of 0.5 was pre-registered and it is NOT a pass/fail line.\n"
              "ROB-0015 is a PARAM-PERTURBATION plan (the declared protocol constant SEEDS/repeat is changed from 0 to 1), NOT multiple-seeds; its record links EXP-0125 (repeat 0) and EXP-0126 (repeat 1) only.\n"
              "EXP-0131 (repeat 2) was run afterwards and is drawn as a SUPPLEMENTARY block: it is NOT in the ROB-0015 record and is not a third planned arm.\n"
              "The ledger 'spread' field for ROB-0015 is the ABSOLUTE range (%.6f); the ratio to the reference run computed here is %.6f (limit %.2f)."
              % (rob["absolute"], rob["relative"], rob["limit"]))
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题二：Top-3 入选频率 π、符号一致率与旧口径 p_positive；ROB-0015 为冻结种子块参数扰动（计划 n=2，补充块单列）。")
    return metadata(name, "EXP-0107", text,
                    [f"{E107}/metrics.json", f"{E107}/outputs.json"]
                    + [f"{E107}/repeat{repeat}/strict_top3_by_method.csv" for repeat in range(3)]
                    + [f"experiments/{e}/metrics.json" for e in ROB_EXPS["ROB-0015"]]
                    + [f"experiments/{e}/metrics.json" for e in ROB_SUPPLEMENT["ROB-0015"]]
                    + ["state/ledger.json"],
                    path=path, sha256=digest,
                    key_values={"pi_mean": pi_mean, "pi_below_0.5": below, "n": len(board),
                                "sign_stability_mean": sign_mean, "sign_stability_legacy_mean": legacy_mean,
                                "third_place_unstable": third_counts,
                                "rob0015_values": plan_values,
                                "rob0015_absolute_range": rob["absolute"],
                                "rob0015_relative_range": rob["relative"],
                                "rob0015_spread_convention": rob["spreadConvention"],
                                "rob0015_seeds": seeds,
                                "supplementary_experiment": supplement_experiment,
                                "supplementary_seed": supplement_seed,
                                "supplementary_jaccard": supplement_jaccard})


# ===========================================================================
# 6. Q3-energy-comparison - EXP-0109
# ===========================================================================
def fig_q3_energy_comparison():
    name = "Q3-energy-comparison"
    require_succeeded("EXP-0109", name)
    outputs = load_json(f"{E109}/outputs.json", name)
    need("q3" in outputs and "comparisons" in outputs["q3"], name, "missing key 'q3.comparisons' in %s/outputs.json" % E109)
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

    summary = outputs["q3"].get("energy_summary")
    need(isinstance(summary, dict) and isinstance(summary.get("allStyles"), dict), name,
         "missing key 'q3.energy_summary.allStyles' in %s/outputs.json" % E109)
    all_styles = summary["allStyles"]
    for key in ("nCells", "nEstimableCells", "nExcludedCells", "nSamples", "V_normalized", "V", "U_signed"):
        need(key in all_styles, name, "missing key 'q3.energy_summary.allStyles.%s'" % key)
    check_value(name, "generated design normalized V vs energy_summary", generated, all_styles["V_normalized"])
    check_value(name, "generated design unsigned V vs energy_summary", values["copula-selected"]["energy-V"], all_styles["V"])
    check_value(name, "generated design signed U vs energy_summary", values["copula-selected"]["energy-U"], all_styles["U_signed"])
    check_value(name, "estimable cells", int(all_styles["nEstimableCells"]), 177, tol=0)
    check_value(name, "excluded cells", int(all_styles["nExcludedCells"]), 21, tol=0)
    check_value(name, "generated samples", int(all_styles["nSamples"]), 729, tol=0)

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

    fig.suptitle("Q3 generation quality - empirical energy distances by design (n_gen-weighted over %d estimable cells, n_gen = %d)"
                 % (int(all_styles["nEstimableCells"]), int(all_styles["nSamples"])),
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
    return metadata(name, "EXP-0109", text, [f"{E109}/outputs.json"],
                    path=path, sha256=digest,
                    key_values={"design_norm": generated, "resample_norm": resample, "raw_design": raw_design,
                                "norm": dict(zip(designs, norm)), "V_raw": dict(zip(designs, v_raw)),
                                "U_signed": dict(zip(designs, u_raw))})


# ===========================================================================
# 7. Q3-per-style-energy - EXP-0109 (recomputed from the experiment's own table)
# ===========================================================================
def fig_q3_per_style_energy():
    name = "Q3-per-style-energy"
    require_succeeded("EXP-0109", name)
    outputs = load_json(f"{E109}/outputs.json", name)
    need("q3" in outputs, name, "missing top-level key 'q3' in %s/outputs.json" % E109)
    summary = outputs["q3"].get("energy_summary")
    need(isinstance(summary, dict), name, "missing key 'q3.energy_summary' in %s/outputs.json" % E109)
    for key in ("allStyles", "excludedStylesSubset", "perStyle"):
        need(isinstance(summary.get(key), dict), name, "missing key 'q3.energy_summary.%s'" % key)
    all_styles = summary["allStyles"]
    three = summary["excludedStylesSubset"]
    per_style = summary["perStyle"]
    for key in ("nCells", "nEstimableCells", "nExcludedCells", "nSamples", "V_normalized"):
        need(key in all_styles, name, "missing key 'q3.energy_summary.allStyles.%s'" % key)
        need(key in three, name, "missing key 'q3.energy_summary.excludedStylesSubset.%s'" % key)
    for style, block in per_style.items():
        for key in ("nCells", "nEstimableCells", "nExcludedCells", "nSamples", "V_normalized"):
            need(key in block, name, "missing key 'q3.energy_summary.perStyle.%s.%s'" % (style, key))

    # recompute every pooled number from the experiment's own per-cell metric table
    metrics_csv = load_csv(f"{E109}/q3_metrics.csv", name, low_memory=False)
    for column in ("stage", "model", "style", "n_gen", "E_V_norm", "n_excluded_from_energy"):
        need(column in metrics_csv.columns, name, "q3_metrics.csv lacks column %r" % column)
    design = metrics_csv[(metrics_csv["stage"] == "design") & (metrics_csv["model"] == "copula-selected")]
    cells = design[design["n_excluded_from_energy"] == 0]
    check_value(name, "total design cells", len(design), int(all_styles["nCells"]), tol=0)
    check_value(name, "estimable design cells", len(cells), int(all_styles["nEstimableCells"]), tol=0)
    check_value(name, "excluded design cells", len(design) - len(cells), int(all_styles["nExcludedCells"]), tol=0)
    weighted = float((cells["E_V_norm"] * cells["n_gen"]).sum() / cells["n_gen"].sum())
    check_value(name, "21-style pooled normalized V", weighted, all_styles["V_normalized"])
    check_value(name, "21-style pooled generated samples", float(cells["n_gen"].sum()), float(all_styles["nSamples"]))

    recomputed = {}
    for style, frame in cells.groupby("style"):
        recomputed[str(style)] = {
            "value": float((frame["E_V_norm"] * frame["n_gen"]).sum() / frame["n_gen"].sum()),
            "cells": int(len(frame)),
            "n_gen": float(frame["n_gen"].sum()),
        }
    for style in sorted(set(per_style) - set(recomputed)):
        need(int(per_style[style]["nEstimableCells"]) == 0, name,
             "style %r has no estimable cell here but the summary records estimable cells" % style)
    for style, block in recomputed.items():
        need(style in per_style, name, "style %r is missing from energy_summary.perStyle" % style)
        check_value(name, "pooled normalized V for %r" % style, block["value"], per_style[style]["V_normalized"])
        check_value(name, "estimable cells for %r" % style, block["cells"],
                    int(per_style[style]["nEstimableCells"]), tol=0)
        check_value(name, "generated samples for %r" % style, block["n_gen"],
                    float(per_style[style]["nSamples"]))

    three_names = ["Tripel", "Kriek", "Lambic"]
    three_cells = cells[cells["style"].isin(three_names)]
    three_value = float((three_cells["E_V_norm"] * three_cells["n_gen"]).sum() / three_cells["n_gen"].sum())
    check_value(name, "three-style pooled normalized V", three_value, three["V_normalized"])
    check_value(name, "three-style estimable cells", len(three_cells), int(three["nEstimableCells"]), tol=0)
    check_value(name, "three-style generated samples", float(three_cells["n_gen"].sum()), float(three["nSamples"]))

    styles = sorted(recomputed, key=lambda item: recomputed[item]["value"])  # largest on top
    values = [recomputed[style]["value"] for style in styles]
    ns = [recomputed[style]["n_gen"] for style in styles]
    colors = [C_HL if style in three_names else C_MAIN for style in styles]

    fig, ax = plt.subplots(figsize=(9.4, 6.8))
    y = np.arange(len(styles))
    ax.barh(y, values, height=0.72, color=colors, edgecolor="white", linewidth=0.4, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(["%s (n_gen=%d)" % (style, int(n)) for style, n in zip(styles, ns)], fontsize=7.0)
    ax.set_xscale("log")
    ax.set_xlabel("n_gen-weighted mean normalized V energy distance (log scale, lower is better)")
    ax.set_xlim(min(values) * 0.72, max(values) * 4.6)
    ax.set_ylim(-0.7, len(styles) - 0.3)
    for index, value in enumerate(values):
        ax.text(value * 1.05, index, "%.4f" % value, va="center", fontsize=6.8)
    ax.axvline(float(all_styles["V_normalized"]), color=C_MAIN, linestyle="--", linewidth=1.1, zorder=3)
    ax.axvline(three_value, color=C_HL, linestyle="--", linewidth=1.1, zorder=3)
    ax.set_title("Q3 normalized energy distance per style (%d estimable styles), generated design spectrum\n"
                 "Tripel / Kriek / Lambic highlighted; the two pooled values are reported separately, never substituted"
                 % len(styles))
    handles = [
        Patch(facecolor=C_MAIN, label="other %d estimable styles" % (len(styles) - len(three_names))),
        Patch(facecolor=C_HL, label="Tripel / Kriek / Lambic (%d cells, n_gen=%d)"
              % (int(three["nEstimableCells"]), int(three["nSamples"]))),
        Line2D([0], [0], color=C_MAIN, linestyle="--", linewidth=1.1,
               label="%d-style pooled %.6f (%d cells, n_gen=%d)"
                     % (len(styles), float(all_styles["V_normalized"]),
                        int(all_styles["nEstimableCells"]), int(all_styles["nSamples"]))),
        Line2D([0], [0], color=C_HL, linestyle="--", linewidth=1.1,
               label="three-style pooled %.6f (%d cells, n_gen=%d)"
                     % (three_value, int(three["nEstimableCells"]), int(three["nSamples"]))),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=6.9)
    note(fig, "Every bar is the n_gen-weighted mean of E_V_norm over that style's estimable (stage=design, copula-selected) cells; all %d bars, the %d-style pool "
              "and the three-style pool are recomputed from experiments/EXP-0109/q3_metrics.csv and match EXP-0109 outputs.json energy_summary bit-for-bit.\n"
              "Faro has 0 estimable cells (all 9 excluded), so it has no bar; %d of %d cells are excluded in total (n_real or n_gen too small). "
              "The %d-style pool is NOT the three-style pool.\n"
              "The older outputs/q3/style_and_displacement_scope.json was built from the superseded EXP-0079 run and is NOT used here."
              % (len(styles), len(styles), len(design) - len(cells), len(design), len(styles)))
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题三：逐风格 n_gen 加权能量距离（21 可估风格）；三风格池化 %.4f 与 21 风格池化 %.4f 不得互替。"
                   % (three_value, float(all_styles["V_normalized"])))
    return metadata(name, "EXP-0109", text,
                    [f"{E109}/q3_metrics.csv", f"{E109}/outputs.json"],
                    path=path, sha256=digest,
                    key_values={"pooled_21": float(all_styles["V_normalized"]), "pooled_three": three_value,
                                "n_styles": len(styles), "cells": int(all_styles["nEstimableCells"]),
                                "estimable_styles": styles})


# ===========================================================================
# 8. Q3-transfer-shift - EXP-0110 (three separate quantity groups, five arms)
# ===========================================================================
def fig_q3_transfer_shift():
    name = "Q3-transfer-shift"
    require_succeeded("EXP-0110", name)
    transfers = load_csv(f"{E110}/transfers.csv", name, low_memory=False)
    constraints = load_csv(f"{E110}/transfer_constraints.csv", name, low_memory=False)
    metrics = load_json(f"{E110}/metrics.json", name)
    outputs = load_json(f"{E110}/outputs.json", name)

    opt_cols = [c for c in transfers.columns if c.startswith("opt__chem__")]
    src_cols = [c for c in transfers.columns if c.startswith("src__chem__")]
    ref_cols = [c for c in transfers.columns if c.startswith("ref__chem__")]
    need(len(opt_cols) == 231 and len(src_cols) == 231, name,
         "expected 231 opt__chem__/src__chem__ columns, found %d/%d" % (len(opt_cols), len(src_cols)))
    need(len(ref_cols) == 231, name, "expected 231 ref__chem__ columns, found %d" % len(ref_cols))
    column_names = [c[len("opt__chem__"):] for c in opt_cols]
    need([c[len("src__chem__"):] for c in src_cols] == column_names, name,
         "opt__chem__ and src__chem__ column order differs")
    need([c[len("ref__chem__"):] for c in ref_cols] == column_names, name,
         "ref__chem__ column order differs from opt__chem__")
    for column in ("strategy", "l1_change_z", "mean_abs_change_z", "nonincrease_all", "repeat"):
        need(column in transfers.columns, name, "transfers.csv lacks column %r" % column)

    strategies = ["qp-quantile-anchor", "qp-source-anchor", "target-mean-projection-full",
                  "target-mean-projection", "source-fixed"]
    need(set(transfers["strategy"].unique()) == set(strategies), name,
         "transfers.csv strategies %r differ from the expected %r"
         % (sorted(transfers["strategy"].unique()), strategies))
    bounded = ["DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal"]
    for column in bounded:
        for prefix in ("_stored_source", "_stored_new", "_nonincreasing"):
            need(column + prefix in transfers.columns, name, "transfers.csv lacks column %r" % (column + prefix))

    storage_arrays = {}
    z_arrays = {}
    bounded_gap = 0.0
    for strategy in strategies:
        frame = transfers[transfers["strategy"] == strategy]
        need(len(frame) == 99, name, "strategy %r has %d rows, expected 99" % (strategy, len(frame)))
        delta = np.abs(frame[opt_cols].to_numpy(dtype=float) - frame[src_cols].to_numpy(dtype=float))
        storage_arrays[strategy] = {"max": delta.max(axis=0), "mean": delta.mean(axis=0)}
        z_arrays[strategy] = {
            "l1": frame["l1_change_z"].to_numpy(dtype=float),
            "mean_abs": frame["mean_abs_change_z"].to_numpy(dtype=float),
        }
        # the four bounded columns are recorded twice: opt/src chemistry columns and stored_* readings
        for column in bounded:
            index = column_names.index(column)
            recorded = np.abs(frame[column + "_stored_new"].to_numpy(float)
                              - frame[column + "_stored_source"].to_numpy(float))
            bounded_gap = max(bounded_gap, float(np.abs(storage_arrays[strategy]["max"][index] - recorded.max())))
    need(bounded_gap <= 1e-9, name,
         "recomputed |opt - src| disagrees with the recorded stored_new - stored_source readings (max gap %.3g)"
         % bounded_gap)

    # z-space movement: l1_change_z must equal 231 x mean_abs_change_z on every row
    z_gap = max(float(np.abs(z_arrays[strategy]["l1"] - 231.0 * z_arrays[strategy]["mean_abs"]).max())
                for strategy in strategies)
    need(z_gap <= 1e-9, name,
         "l1_change_z != 231 x mean_abs_change_z (max gap %.3g); the two z-space readings are inconsistent" % z_gap)

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
    # stored values carry ~1e-9 rounding: count a violation only above the same 1e-8 tolerance
    violation_tolerance = 1e-8
    residual_by_strategy = {}
    for strategy in strategies:
        mask = constraints["strategy"] == strategy
        values = violation[mask.to_numpy()]
        residual_by_strategy[strategy] = {
            "rows": int(mask.sum()),
            "violations": int((values > violation_tolerance).sum()),
            "max": float(values.max()) if values.size else 0.0,
        }
        need(residual_by_strategy[strategy]["rows"] == 3762, name,
             "strategy %r has %d constraint records, expected 3762" % (strategy, residual_by_strategy[strategy]["rows"]))

    # non-increase rates: recomputed from the row-level flag, checked against outputs.json
    nonincrease = outputs.get("nonincrease_by_strategy")
    need(isinstance(nonincrease, dict), name, "outputs.json has no nonincrease_by_strategy")
    for strategy in strategies:
        need(strategy in nonincrease, name, "outputs.json lacks nonincrease_by_strategy.%s" % strategy)
        recomputed_rate = float(transfers.loc[transfers["strategy"] == strategy, "nonincrease_all"].astype(float).mean())
        check_value(name, "non-increase rate for %r" % strategy, recomputed_rate, nonincrease[strategy]["nonincreaseRate"])
        for column in bounded:
            recorded = float(transfers.loc[transfers["strategy"] == strategy, column + "_nonincreasing"].astype(float).mean())
            check_value(name, "%s non-increase for %r" % (column, strategy), recorded,
                        nonincrease[strategy]["perField"][column])

    # delivered-arm and reference-arm metrics, cross-checked between metrics.json and outputs.json
    energy = outputs.get("energy_by_strategy")
    certificates = outputs.get("certificates_summary")
    need(isinstance(energy, dict), name, "outputs.json has no energy_by_strategy")
    need(isinstance(certificates, dict), name, "outputs.json has no certificates_summary")
    delivered = "qp-quantile-anchor"
    check_value(name, "delivered transfer energy", float(metric(metrics, "transfer-energy", f"{E110}/metrics.json", name)),
                float(energy[delivered]["V"]))
    check_value(name, "delivered signed U", float(metric(metrics, "transfer-energy-U", f"{E110}/metrics.json", name)),
                float(energy[delivered]["U"]))
    check_value(name, "delivered normalized energy",
                float(metric(metrics, "transfer-energy-normalized", f"{E110}/metrics.json", name)),
                float(energy[delivered]["V_normalized"]))
    check_value(name, "delivered non-increase rate",
                float(metric(metrics, "nonincrease-rate", f"{E110}/metrics.json", name)),
                float(nonincrease[delivered]["nonincreaseRate"]))
    check_value(name, "QP solves", int(metric(metrics, "qp-solves", f"{E110}/metrics.json", name)),
                int(certificates["solves"]), tol=0)
    check_value(name, "QP max constraint violation",
                float(metric(metrics, "qp-max-constraint-violation", f"{E110}/metrics.json", name)),
                float(certificates["maxConstraintViolation"]))
    check_value(name, "box-only projection energy",
                float(metric(metrics, "transfer-energy-target-mean-projection", f"{E110}/metrics.json", name)),
                float(energy["target-mean-projection"]["V"]))
    check_value(name, "box-only projection non-increase rate",
                float(metric(metrics, "nonincrease-rate-target-mean-projection", f"{E110}/metrics.json", name)),
                float(nonincrease["target-mean-projection"]["nonincreaseRate"]))
    check_value(name, "full projection energy",
                float(metric(metrics, "transfer-energy-target-mean-projection-full", f"{E110}/metrics.json", name)),
                float(energy["target-mean-projection-full"]["V"]))
    check_value(name, "full projection non-increase rate",
                float(metric(metrics, "nonincrease-rate-target-mean-projection-full", f"{E110}/metrics.json", name)),
                float(nonincrease["target-mean-projection-full"]["nonincreaseRate"]))

    colors = {"qp-quantile-anchor": C_MAIN, "qp-source-anchor": C_ALT, "target-mean-projection-full": "#a6d96a",
              "target-mean-projection": C_HL, "source-fixed": C_GREY}
    tick_labels = ["QP quantile anchor\n(delivered)", "QP source anchor", "target-mean projection\nFULL (half-space)",
                   "target-mean projection\nBOX only (diagnostic)", "source fixed\n(trivial control)"]

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
        ax.set_xticklabels(tick_labels, fontsize=6.1, rotation=18, ha="right")

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

    fig = plt.figure(figsize=(13.2, 7.8))
    grid = fig.add_gridspec(2, 3, hspace=0.56, wspace=0.30)

    storage_max_top = float(storage_arrays[delivered]["max"].max())
    storage_mean_top = float(storage_arrays[delivered]["mean"].max())
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
    ax.set_xticklabels(tick_labels, fontsize=6.1, rotation=18, ha="right")
    ax.set_ylabel("records with residual > 1e-8\n(stored precision)")
    ax.set_ylim(0.0, max(counts) * 1.35 if max(counts) else 5.0)
    ax.set_title("(c1) constraint residual - violating records", loc="left")

    ax = fig.add_subplot(grid[1, 2])
    values = violation[violation > violation_tolerance]
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

    fig.suptitle("Q3 transfer (Pils/Lager -> Tripel, 11 sources x 3 repeats x 3 folds = 99 rows per arm): three quantities in three separate panels",
                 fontsize=9.6, fontweight="bold", y=1.06)
    top_columns = np.argsort(-storage_arrays[delivered]["max"])[:3]
    top_text = ", ".join("%s %.3f" % (column_names[i], storage_arrays[delivered]["max"][i])
                         for i in top_columns)
    note(fig, "The three groups are DIFFERENT quantities with different units and must not be merged into one curve: "
              "(1) stored-space displacement of the delivered vector, (2) z-space movement of the same vector, "
              "(3) violation of the declared bounds. A residual is not a new-minus-source displacement.\n"
              "Delivered arm (qp-quantile-anchor): transfer energy %.6f, signed U %.6f, normalized %.6f, non-increase rate %.4f, %d QP solves (all optimal).\n"
              % (float(metrics["transfer-energy"]), float(metrics["transfer-energy-U"]),
                 float(metrics["transfer-energy-normalized"]), float(metrics["nonincrease-rate"]),
                 int(metrics["qp-solves"])) +
              "Largest stored movements of the delivered arm: %s; the four bounded columns agree with the recorded stored_new - stored_source readings to <= 1e-9.\n"
              % top_text +
              "z-space: 99 rows per arm; l1_change_z = 231 x mean_abs_change_z on every row (max gap %.1e). No independent z-space replay of this round exists in outputs/q3: "
              "the older zspace_recompute.json covers 396 rows of the superseded EXP-0080 and is NOT reused here.\n"
              % z_gap +
              "Residual: 3762 records per arm; clamp(new - bound, 0) reproduces the recorded residual (max gap %.1e). The BOX-only projection violates the stale half-space in %d records; "
              "the FULL projection and both QP arms violate none (bound violations are NOT displacements)."
              % (residual_gap, residual_by_strategy["target-mean-projection"]["violations"]),
         xy=(0.005, -0.075), size=6.3)
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "问题三：迁移三组量分面板——存储位移 |opt−src|、z 空间位移、约束残差 clamp(new−src,0)；残差非位移，按策略区分。")
    return metadata(name, "EXP-0110", text,
                    [f"{E110}/transfers.csv", f"{E110}/transfer_constraints.csv",
                     f"{E110}/metrics.json", f"{E110}/outputs.json"],
                    path=path, sha256=digest,
                    key_values={
                        "storage_max": {s: float(storage_arrays[s]["max"].max()) for s in strategies},
                        "storage_mean_of_means": {s: float(storage_arrays[s]["mean"].mean()) for s in strategies},
                        "z_mean_median": {s: float(np.median(z_arrays[s]["mean_abs"])) for s in strategies},
                        "z_identity_max_gap": z_gap,
                        "bounded_gap": bounded_gap,
                        "residual": residual_by_strategy,
                        "transfer_energy": float(metrics["transfer-energy"]),
                        "transfer_energy_U": float(metrics["transfer-energy-U"]),
                        "transfer_energy_normalized": float(metrics["transfer-energy-normalized"]),
                        "nonincrease_rate": float(metrics["nonincrease-rate"]),
                        "target_mean_projection_energy": float(metrics["transfer-energy-target-mean-projection"]),
                        "target_mean_projection_rate": float(metrics["nonincrease-rate-target-mean-projection"]),
                        "target_mean_projection_full_energy": float(metrics["transfer-energy-target-mean-projection-full"]),
                        "target_mean_projection_full_rate": float(metrics["nonincrease-rate-target-mean-projection-full"]),
                        "qp_solves": int(metrics["qp-solves"]),
                    })


# ===========================================================================
# 9. ROB-summary - ROB-0011 / ROB-0015 / ROB-0016 / ROB-0017
# ===========================================================================
def fig_rob_summary():
    name = "ROB-summary"
    order = [("Q1", "ROB-0011"), ("Q2", "ROB-0015"), ("Q3gen", "ROB-0016"), ("Q3mig", "ROB-0017")]
    labels = {
        "ROB-0011": "ROB-0011  Q1\nA/F30 MAE",
        "ROB-0015": "ROB-0015  Q2\nTop-3 Jaccard",
        "ROB-0016": "ROB-0016  Q3 generation\nnormalized V",
        "ROB-0017": "ROB-0017  Q3 transfer\nnon-increase rate",
    }
    groups = [robustness_readings(rob_id, question_key, name) for question_key, rob_id in order]
    for group in groups:
        if group["ruleType"] == "relative-range":
            need(group["values"][0] != 0.0, name,
                 "%s reference value is 0, cannot form a ratio" % group["robId"])

    # the transfer-side spread is 0 because the metric is saturated at its ceiling, not because of an improvement
    transfer = next(group for group in groups if group["robId"] == "ROB-0017")
    need(transfer["ruleType"] == "min-value", name, "ROB-0017 rule changed away from min-value; the saturation note would be wrong")
    need(all(abs(value - transfer["limit"]) < 1e-12 for value in transfer["values"]), name,
         "ROB-0017 values are no longer all at the min-value limit %r" % transfer["limit"])

    fig, ax = plt.subplots(figsize=(11.8, 5.8))
    width = 0.34
    x = np.arange(len(groups))
    absolute = [group["absolute"] for group in groups]
    relative = [group["relative"] if group["relative"] is not None else 0.0 for group in groups]
    ax.bar(x - width / 2, absolute, width, color=C_MAIN, edgecolor="white", linewidth=0.4,
           label="absolute range (max - min, metric units)", zorder=2)
    ax.bar(x + width / 2, relative, width, color=C_HL, edgecolor="white", linewidth=0.4,
           label="ratio to the reference run (absolute / reference value)", zorder=2)
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
            ax.text(position, 0.004, "all %d = %.3f\nabsolute = relative = 0.000000\nrange 0 = ceiling saturation\n(min-value rule, limit %.1f)"
                    % (len(group["values"]), group["values"][0], group["limit"]),
                    ha="center", va="bottom", fontsize=6.6, color="#c0392b")
    ax.set_xticks(x)
    ax.set_xticklabels(["%s\n%s" % (labels[group["robId"]], " / ".join("%.6f" % value for value in group["values"]))
                        for group in groups], fontsize=6.9)
    ax.set_ylabel("range of the pre-registered runs")
    ax.set_ylim(0.0, max(max(absolute), max(relative), 0.11) * 1.26)
    ax.set_xlim(-0.55, len(groups) - 0.25)
    ax.grid(axis="y", color="#ececec", linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title("Robustness summary - absolute range vs the ratio to the reference run, next to each plan's pre-registered limit\n"
                 "(ROB-0017 is a bounded rate: a 0 range is ceiling saturation, not an improvement)")
    ax.legend(loc="upper left", fontsize=7.0)

    conventions = []
    for group in groups:
        rob_id = group["robId"]
        if group["spreadConvention"] == "absolute":
            conventions.append(
                "%s: ledger 'spread' field equals the ABSOLUTE range (plugin denominator = 1); the orange bar is the true ratio"
                % rob_id)
        else:
            conventions.append("%s: ledger 'spread' field equals the ratio to the reference run" % rob_id)
    notes = (
        "Plans (all executed, decisionPassed = true): ROB-0011 Q1 = repeat 0/1 seed block + lambda x0.5 (reference EXP-0100).\n"
        "ROB-0015 Q2 / ROB-0016 Q3 generation / ROB-0017 Q3 transfer are PARAM-PERTURBATION plans: the perturbed input is the declared frozen-seed-block constant SEEDS/repeat (0 -> 1), "
        "references EXP-0125 / EXP-0127 / EXP-0129; each plan record holds n = 2 runs.\n"
        "The repeat-2 blocks EXP-0131 / EXP-0132 / EXP-0133 are SUPPLEMENTARY and are NOT part of the plan records, so they are not pooled into these ranges.\n"
        + "\n".join(conventions) + "\n"
        "ROB-0017 is saturated: non-increase rate = 1.000 in both runs by construction of the hard bound; range 0 is a ceiling artefact, NOT an improvement.\n"
        "Each range describes its own perturbation set only; the four plans are not pooled into one stability verdict."
    )
    note(fig, notes, xy=(0.005, -0.062), size=6.5)
    scan_text(fig, name)
    path, digest = save(fig, name)
    text = caption(name,
                   "四组稳健性：绝对极差与参照比值并排、各自预注册上限；ROB-0015/16/17 为冻结种子块参数扰动（计划 n=2），ROB-0017 饱和极差非改善。")
    inputs = ["state/ledger.json"] + [f"experiments/{e}/metrics.json" for rob in ROB_EXPS.values() for e in rob]
    if os.path.exists(P("report/evidence_manifest.json")):
        inputs.append("report/evidence_manifest.json")
    return metadata(name, None, text, inputs,
                    path=path, sha256=digest,
                    key_values=[{key: value for key, value in group.items() if key != "plan"} for group in groups])


# ===========================================================================
FIGURES = {
    "Q1-per-target-skill": fig_q1_per_target_skill,
    "Q1-model-comparison": fig_q1_model_comparison,
    "Q1-grade-distribution": fig_q1_grade_distribution,
    "Q2-network": fig_q2_network,
    "Q2-attachment2-network": fig_q2_attachment2_network,
    "Q2-stability": fig_q2_stability,
    "Q3-energy-comparison": fig_q3_energy_comparison,
    "Q3-per-style-energy": fig_q3_per_style_energy,
    "Q3-transfer-shift": fig_q3_transfer_shift,
    "ROB-summary": fig_rob_summary,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="build all ten confirmatory figures")
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
