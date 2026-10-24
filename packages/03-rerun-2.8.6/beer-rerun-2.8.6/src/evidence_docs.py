"""生成分析证据文档（Q1/Q2/Q3 的 factor-analysis/robustness/recommendations 等）。

纪律：所有数字都从**已成功的实验产物**读取（metrics.json / outputs.json），不手写、不新造数字；
文件只做"把已有证据整理成 obligations 要求的形状"，语义充分性仍由独立审查判断。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L  # noqa: E402

EXP = L.ROOT / "experiments"
OUT = L.OUT


def metrics(eid):
    return json.loads((EXP / eid / "metrics.json").read_text(encoding="utf-8"))


def outputs(eid):
    p = EXP / eid / "outputs.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def write_json(obj, rel):
    p = L.ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def q1():
    m1, m2, m3 = metrics("EXP-0001"), metrics("EXP-0002"), metrics("EXP-0003")
    t50 = L.target_columns()
    per = {t: {"ridge": m2.get(f"holdout_mae__{t}"), "gbm": m3.get(f"holdout_mae__{t}"),
               "baseline": m1.get(f"holdout_mae__{t}")} for t in t50}
    df = pd.read_csv(L.CLEAN / "q1_mapped.csv")
    tr_beers = set(pd.read_csv(L.SPLITS / "SPLIT-0002" / "train.csv", usecols=["beer"])["beer"].astype(int))
    te = df[~df["beer"].isin(tr_beers)]
    style = te.set_index("beer")["tasting_category_fine"].astype(str)
    # 用 EXP-0002 的留出预测按风格重算 MAE（真实产物，不重新拟合）
    pred = pd.read_csv(EXP / "EXP-0002" / "predictions_long.csv")
    pred["style"] = pred["beer"].map(style)
    by_style = pred.groupby("style").apply(
        lambda g: float(np.mean(np.abs(g["y_true"] - g["y_pred"]))), include_groups=False).sort_values()
    robust = {
        "question": "Q1",
        "kind": "post-hoc sensitivity of the reported holdout MAE (no refit, no new holdout use)",
        "modelFamilySensitivity": {
            "EXP-0001_constant": m1["holdout_mae_mean"],
            "EXP-0002_ridge": m2["holdout_mae_mean"],
            "EXP-0003_gbm": m3["holdout_mae_mean"],
            "spread": float(max(m2["holdout_mae_mean"], m3["holdout_mae_mean"])
                            - min(m2["holdout_mae_mean"], m3["holdout_mae_mean"])),
        },
        "oofVsHoldoutGap": float(m2["holdout_mae_mean"] - m2["oof_mae_mean"]),
        "perTargetMae": {t: per[t]["ridge"] for t in t50},
        "perTargetSpread": {"min": float(np.nanmin([per[t]["ridge"] for t in t50])),
                            "max": float(np.nanmax([per[t]["ridge"] for t in t50])),
                            "p90": float(np.nanpercentile([per[t]["ridge"] for t in t50], 90))},
        "perStyleMae": {k: float(v) for k, v in by_style.items()},
        "styleSpread": {"best": float(by_style.iloc[0]), "worst": float(by_style.iloc[-1]),
                        "worstStyle": str(by_style.index[-1]), "nStyles": int(len(by_style))},
        "limitations": ["这是对既有产物的分层/敏感性汇总，不是新模型族的稳健性实验",
                        "未做重复划分/多种子重估：受 holdout 复用预算限制",
                        "映射端点替换（分位数等）未重跑，故不可据此宣称映射无关"],
    }
    write_json(robust, "outputs/q1/robustness.json")

    md = ["# Q1 建议（全部绑定真实指标）\n",
          f"- 以多输出 Ridge 作为交付模型：留出 MAE {m2['holdout_mae_mean']:.4f}，优于常数基线 "
          f"{m1['holdout_mae_mean']:.4f}；HistGBM {m3['holdout_mae_mean']:.4f} 未见优势。",
          f"- 误差按维度差异大（{robust['perTargetSpread']['min']:.3f}–{robust['perTargetSpread']['max']:.3f}），"
          f"建议按维度给出可用性标签，而不是只报 50 维均值。",
          f"- 按风格分层后最差风格为 {robust['styleSpread']['worstStyle']}"
          f"（MAE {robust['styleSpread']['worst']:.3f}），小样本风格应单独标注不确定性。",
          "- 若追求更高精度，优先补真实 0–6 评分卡与重复感官评价，而不是继续加模型复杂度。",
          "- 任何对外表述都必须写 mapped grade，不得写“还原原始 0–6”。"]
    (OUT / "q1" / "recommendations.md").write_text("\n".join(md), encoding="utf-8")


def q2():
    m = metrics("EXP-0007")
    m2b = metrics("EXP-0010")
    o = outputs("EXP-0007")
    sets = o.get("sets", {})
    t50 = L.target_columns()
    rows = []
    for t in t50:
        rows.append({"dimension": t,
                     "methodA": sets.get(t, {}).get("methodA", []),
                     "methodB": sets.get(t, {}).get("methodB", []),
                     "methodC": sets.get(t, {}).get("methodC", []),
                     "jaccard_A_B": m.get(f"jaccard_A_B__{t}"),
                     "stability_A": m.get(f"stability_A__{t}"),
                     "top1_abs_rho": m.get(f"rho_top1_abs__{t}")})
    df = pd.DataFrame(rows)
    by_stab = df.sort_values("stability_A", ascending=False)
    fa = {
        "question": "Q2",
        "kind": "factor analysis (contemporaneous association, not causal)",
        "nFeatures": m["n_features"], "nDims": m["n_dims"], "topK": m["topK"],
        "methodJaccard": {"A_B": m["jaccard_A_B"], "A_C": m["jaccard_A_C"], "B_C": m["jaccard_B_C"]},
        "bootstrapStability": m["bootstrap_stability_A"],
        "psdMinEigRaw2csv": m["psd_min_eig_raw_2csv"],
        "perDimension": rows,
        "mostStable": by_stab.head(5)[["dimension", "stability_A"]].to_dict("records"),
        "leastStable": by_stab.tail(5)[["dimension", "stability_A"]].to_dict("records"),
        "interpretation": "A(Spearman) 与 C(网络平滑) 一致性高；B(Ridge 系数) 与 A 差异大 → Top-3 方法依赖，"
                          "只能交付候选簇 + 入选频率；2.csv 为实测 Spearman 且非 PSD（已投影）。",
    }
    write_json(fa, "outputs/q2/factor_analysis.json")
    robust = {
        "question": "Q2",
        "kind": "stability analysis of the Top-3 ranking",
        "bootstrap": m["n_bootstrap"], "stabilityA": m["bootstrap_stability_A"],
        "jaccard": {"A_B": m["jaccard_A_B"], "A_C": m["jaccard_A_C"], "B_C": m["jaccard_B_C"]},
        "sensitivity": {
            "methodChange": "换成 Ridge 系数排序时 Top-3 平均只有约 "
                            f"{m['jaccard_A_B']:.3f} 的 Jaccard",
            "networkSmoothing": "加入 2.csv 网络平滑后与 A 保持约 "
                                f"{m['jaccard_A_C']:.3f} 的 Jaccard",
            "psd": f"2.csv 非 PSD（min eig {m['psd_min_eig_raw_2csv']:.4f}），已做特征值截断投影",
        },
        "baseline": {"globalTop3JaccardVsPerDim": m2b["topk_jaccard"],
                     "globalTop3": (outputs("EXP-0010").get("baseline_sets", {}) or {}).get("globalTop3"),
                     "interpretation": "若所有维度共用同一 Top-3，与逐维 Top-3 的平均 Jaccard 仅 %.3f；"
                                       "说明逐维排序有实质增量" % m2b["topk_jaccard"]},
        "limitations": ["未做重复划分的 Top-3 重估（holdout 预算受限）", "无独立外部数据验证", "同期关联，非因果"],
    }
    write_json(robust, "outputs/q2/robustness.json")
    md = ["# Q2 建议（全部绑定真实指标）\n",
          f"- 交付形式应为“每个维度的候选簇（A/B/C 三法）+ bootstrap 入选频率”，而不是单一 Top-3："
          f"A–B Jaccard 仅 {m['jaccard_A_B']:.3f}，bootstrap 平均入选频率 {m['bootstrap_stability_A']:.3f}。",
          f"- 推荐把 Spearman 排序（A）作为主排序、网络平滑（C）作为稳健性复核：二者 Jaccard {m['jaccard_A_C']:.3f}。",
          "- 对稳定性低的维度（见 factor_analysis.json 的 leastStable），应补样本或改用分层/分风格分析。",
          "- 任何因果表述都不允许；2.csv 非 PSD，矩阵运算前必须投影并披露。"]
    (OUT / "q2" / "recommendations.md").write_text("\n".join(md), encoding="utf-8")


def q3():
    m = metrics("EXP-0008")
    mb = metrics("EXP-0011")
    m2b = metrics("EXP-0010")
    o = outputs("EXP-0008")
    adapt = o.get("adapt_report", {})
    proto = o.get("protocol", {})
    write_json({"question": "Q3",
                "task": "风格条件化合物谱生成 + 跨风格迁移（生成合理性/约束满足，非酿造验证）",
                "given": ["tasting_category_fine（22 类）", "1.csv 231 个化合物/理化特征", "8.xlsx 缺陷阈值"],
                "unknown": ["目标风格化合物谱", "跨风格迁移后的谱", "感官画像（由 Q1 Ridge 派生预测）"],
                "decisionTime": "生成时已知风格标签与缺陷阈值",
                "styleHoldout": proto.get("holdout_styles"),
                "fewShot": proto.get("adapt_n"),
                "sourceStyle": proto.get("source_style")},
               "outputs/q3/question_definition.json")
    write_json({"question": "Q3",
                "generator": proto.get("generator"),
                "transfer": proto.get("transfer"),
                "constraint": "缺陷列（DMS/Diacetyl/4VG/furfural 等）位移为 0，缺陷 OAV 不变",
                "evaluation": ["energy distance（生成/迁移 vs 留出样本）", "缺陷 OAV 不恶化比例", "超阈值比例"],
                "sensoryImage": "用 EXP-0002 同配置的 Ridge（DATA-0002 训练行）把生成谱映射为 50 维 mapped grade（派生预测）"},
               "outputs/q3/method.json")
    results = {
        "question": "Q3",
        "constraintSatisfaction": m["constraint_satisfaction"],
        "defectNonworsen": {"raw": m["defect_nonworsen_rate_raw"],
                            "constrained": m["defect_nonworsen_rate_constrained"]},
        "exceedRate": {"before": m["exceed_rate_before"], "afterRaw": m["exceed_rate_after_raw"],
                       "afterConstrained": m["exceed_rate_after_constrained"]},
        "energy": {"seenStyles": m["energy_seen_styles_mean"],
                   "holdoutGenerated": m["energy_holdout_generated_mean"],
                   "holdoutSourceBaseline": m["energy_holdout_source_baseline_mean"],
                   "holdoutTransferredRaw": m["energy_holdout_transferred_raw_mean"],
                   "holdoutTransferredConstrained": m["energy_holdout_transferred_constrained_mean"]},
        "transferGain": {"raw": m["transfer_gain_raw_mean"], "constrained": m["transfer_gain_constrained_mean"]},
        "nDefectChecks": m["n_defect_checks"],
        "nDefectChecksWithThreshold": m["n_defect_checks_with_threshold"],
        "perStyleAdapt": adapt,
        "baselineComparison": {
            "unconditionalGlobalEnergy": mb["energy_holdout_generated_mean"],
            "sourceIdentityEnergy": mb["energy_holdout_source_baseline_mean"],
            "fewShotGeneratedEnergy": m["energy_holdout_generated_mean"],
            "constrainedTransferEnergy": m["energy_holdout_transferred_constrained_mean"],
            "finding": "无条件全局高斯的能量距离（%.3f）低于 few-shot 生成（%.3f）与约束迁移（%.3f）："
                       "在 Tripel/Kriek/Lambic 上，3–5 例 few-shot 原型不足以刻画风格分布，能量距离指标偏好全局中心"
                       % (mb["energy_holdout_generated_mean"], m["energy_holdout_generated_mean"],
                          m["energy_holdout_transferred_constrained_mean"]),
        },
    }
    write_json(results, "outputs/q3/results.json")
    robust = {
        "question": "Q3",
        "kind": "constraint & style-consistency check",
        "perStyleEnergy": {s: v for s, v in adapt.items()},
        "defectChecksWithThreshold": m["n_defect_checks_with_threshold"],
        "defectChecksNoThreshold": m["n_defect_checks_no_threshold"],
        "unitRisk": proto.get("unit_risk"),
        "fewShotDisclosure": proto.get("few_shot_disclosure"),
        "limitations": ["绝对 OAV 受阈值单位不确定性影响（可能差 10^3）",
                        "trans-2-nonenal / 3-methyl-2-butenal / 5-methylfurfural 无阈值，无法判定",
                        "few-shot 使用了 3–5 个留出样本，不是 zero-shot",
                        "未做多种子重复生成（未预注册的稳健性实验），仅有单 seed 结果"],
    }
    write_json(robust, "outputs/q3/robustness.json")
    md = ["# Q3 建议（全部绑定真实指标）\n",
          f"- 跨风格迁移必须带缺陷约束：不受约束时缺陷超阈值比例 {m['exceed_rate_before']:.3f}→"
          f"{m['exceed_rate_after_raw']:.3f}；约束后回到 {m['exceed_rate_after_constrained']:.3f}。",
          f"- 约束的代价很小：能量距离 {m['energy_holdout_transferred_constrained_mean']:.3f} vs "
          f"{m['energy_holdout_transferred_raw_mean']:.3f}，且均优于源风格基线 "
          f"{m['energy_holdout_source_baseline_mean']:.3f}。",
          "- 生成结果只能作为“候选配方假设”，需湿实验验证；不得写成真实酿造结论。",
          f"- 阴性结果必须保留：无条件全局基线的能量距离 {metrics('EXP-0011')['energy_holdout_generated_mean']:.3f} "
          f"低于 few-shot 生成 {m['energy_holdout_generated_mean']:.3f} 与约束迁移 "
          f"{m['energy_holdout_transferred_constrained_mean']:.3f}，说明 3–5 例 few-shot 不足以刻画留出风格分布。",
          f"- 有阈值可判定的缺陷组合为 {m['n_defect_checks_with_threshold']} 个，"
          f"其余 {m['n_defect_checks_no_threshold']} 个因缺阈值只能报告“无法判定”。"]
    (OUT / "q3" / "recommendations.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    q1(); q2(); q3()
    files = ["outputs/q1/robustness.json", "outputs/q1/recommendations.md",
             "outputs/q2/factor_analysis.json", "outputs/q2/robustness.json", "outputs/q2/recommendations.md",
             "outputs/q3/question_definition.json", "outputs/q3/method.json", "outputs/q3/results.json",
             "outputs/q3/robustness.json", "outputs/q3/recommendations.md"]
    print(json.dumps({"wrote": files, "allExist": all((L.ROOT / f).exists() for f in files)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
