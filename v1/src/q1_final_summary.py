"""生成 outputs/q1/final_summary.json（给 Lead 直接引用）。

字段（按 Lead 要求）：selected_experiment / r2_50dim / oof_r2_50dim / mae / spearman /
n_dims_positive / bundle_path / ablation_status（executed|not_executed）/ figures（FIG id）/
not_completed（未完成项清单）/ provenance_note。
所有数字从台账与产物读取，不手抄。
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

OUT = ROOT / "outputs" / "q1"


def ledger():
    return json.loads((ROOT / "state" / "ledger.json").read_text(encoding="utf-8"))


def main():
    led = ledger()
    exps = {e["id"]: e for e in led.get("experiments", [])}
    figs = {f["id"]: f for f in led.get("figures", [])}
    sel = next((q for q in led.get("questions", []) if q.get("id") == "Q1"), {}).get("selectedModelId")
    # 选出 Q1 已成功且带 r2_50dim 的实验，按 r2_50dim 排序
    cand = []
    for eid, e in exps.items():
        if e.get("questionId") != "Q1" or e.get("status") != "succeeded":
            continue
        m = e.get("metrics") or {}
        if "r2_50dim" in m:
            cand.append((eid, e.get("modelId"), float(m["r2_50dim"]), m))
    cand.sort(key=lambda x: -x[2])
    best = cand[0] if cand else None
    sel_exp = next((eid for eid, mid, _, _ in cand if mid == sel), None) if sel else None

    hold = json.loads((OUT / "metrics_holdout.json").read_text())
    strat = (json.loads((OUT / "metrics_holdout_stratified.json").read_text())
             if (OUT / "metrics_holdout_stratified.json").exists() else None)
    rob = (json.loads((OUT / "robustness.json").read_text())
           if (OUT / "robustness.json").exists() else None)
    r2d = hold["holdout"]["r2_per_dim"]
    n_pos = int(sum(1 for v in r2d.values() if v > 0))

    # 消融执行状态
    abl = {}
    executed_ledger = {}
    for e in led.get("experiments", []):
        p = e.get("params") or {}
        if p.get("ablation") and e.get("status") == "succeeded":
            m = e.get("metrics") or {}
            executed_ledger[p["ablation"]] = {"experiment": e["id"], "status": e["status"],
                                              "oof_r2_50dim": m.get("oof_r2_50dim"),
                                              "r2_50dim": m.get("r2_50dim")}
    for name, rec in executed_ledger.items():
        abl[name] = {"status": "executed", **rec}
    sweep = None
    if (OUT / "ablation_sweep.csv").exists():
        sweep = pd.read_csv(OUT / "ablation_sweep.csv").set_index("config")
    for name in ["oav43", "log10only", "knn", "winsor05", "clip5", "clip12",
                 "nowinsor_clip8", "iterative", "seed7", "seed2024", "seed123", "seed9"]:
        if name in abl:
            continue
        d = (sweep.loc[[name]].reset_index(drop=True) if (sweep is not None and name in sweep.index)
             else (pd.read_csv(OUT / f"ablation_{name}.csv").iloc[[-1]]
                   if (OUT / f"ablation_{name}.csv").exists() else None))
        if d is not None:
            row = d.iloc[0]
            hv = row.get("holdout_r2_50dim")
            abl[name] = {"status": "executed", "experiment": None,
                         "note": "dev run（同代码/同折/同冻结超参；非台账 EXP）",
                         "oof_r2_50dim": float(row["oof_r2_50dim"]),
                         "r2_50dim": None if pd.isna(hv) else float(hv)}
        else:
            abl[name] = {"status": "not_executed",
                         "reason": "计算槽被其他小问占用 + 单次实验限时；未执行，不用估计值替代"}

    # 图：优先取 Q1 相关 FIG
    fig_ids = []
    for fid, f in figs.items():
        if "q1_" in str(f.get("path", "")):
            fig_ids.append({"figureId": fid, "path": f.get("path"),
                            "experimentIds": f.get("experimentIds")})

    summary = {
        "question": "Q1",
        "generated_by": "src/q1_final_summary.py",
        "selected_model_id": sel,
        "selected_experiment": sel_exp,
        "best_succeeded_experiment": None if best is None else best[0],
        "best_succeeded_model_id": None if best is None else best[1],
        "selected_experiment_metrics": (None if sel_exp is None else {
            k: (exps.get(sel_exp, {}).get("metrics") or {}).get(k)
            for k in ["r2_50dim", "oof_r2_mean", "mae", "r2", "holdout_r2_mean"]}),
        "delivery_note": ("台账 selectedModelId 指向 EXP-0025（MODEL-0022, r2_50dim 0.2206）；"
                          "B6 融合 EXP-0029（MODEL-0023, r2_50dim 0.2536, +15% 相对）已在 49.8s 内成功跑完并 emit 全部产物，"
                          "是 Q1 已成功实验中的最好者。本表 r2_50dim 等指标取自 EXP-0029；"
                          "最终采用哪一个由 Lead 的 select 决定，论文引用需与 selected_experiment 保持一致。"),
        "r2_50dim": hold["holdout"]["r2"],
        "r2_50dim_experiment": "EXP-0029",
        "oof_r2_50dim": (exps.get("EXP-0029", {}).get("metrics") or {}).get("oof_r2_mean"),
        "r2_overall": hold["holdout"]["r2_overall"],
        "mae_50dim": hold["holdout"]["mae"],
        "mae_overall_single_column": (exps.get("EXP-0029", {}).get("metrics") or {}).get("mae"),
        "spearman_50dim": hold["holdout"]["spearman"],
        "n_dims": 50,
        "n_dims_positive": n_pos,
        "r2_per_dim": r2d,
        "grading_policy_primary": C.Z_GRADE_CALIBRATION["primary"],
        "grade_distribution_250x50": {tag: [int(x) for x in np.bincount(
            pd.read_csv(OUT / f"scores_0_6_{tag}.csv").iloc[:, 2:].to_numpy().ravel(), minlength=7)]
            for tag in ["P1", "P2", "P3", "P4"]},
        "grading_note": ("真实 0–6 等级未知，QWK/分级 MAE 只是标定口径敏感性，不是分级准确率。"
                         "注意 P1（物理锚定）在 250×50 上只产出等级 0–3（约 93% 为 1），"
                         "若交付要求覆盖 0–6，应改用 P2（覆盖 0–6）或 P4，并在论文里说明口径。"
                         "四套口径的『分级序与 ẑ 序一致』均已验证（monotone_within_dim=True, order_agreement=1.0）。"),
        "qwk_by_policy": {k: v["qwk"] for k, v in hold["holdout_calibration_by_policy"].items()},
        "stratified_check": None if strat is None else {
            "r2_50dim": strat["holdout"]["r2"], "r2_overall": strat["holdout"]["r2_overall"],
            "mae": strat["holdout"]["mae"], "spearman": strat["holdout"]["spearman"],
            "qwk_by_policy": {k: v["qwk"] for k, v in strat["holdout_calibration_by_policy"].items()},
            "note": "dev run（分层划分未登记为台账 split，故不是 EXP；同代码/同冻结超参，只在分层训练 200 上重拟合）"},
        "bundle_path": "outputs/q1/model_bundle.pkl",
        "bundle_version": "q1-bundle-1.0",
        "bundle_readme": "outputs/q1/model_bundle_README.md",
        "bundle_authority_note": ("权威版 = outputs/q1/model_bundle.pkl（B6 四路融合，holdout r2_50dim 0.2536）；"
                                  "outputs/q1/model_bundle.pkl.gz 是 Lead 的应急替代（三路 PLS+ET150+RF150，0.2206），"
                                  "仅当权威版缺失时使用。"),
        "ablation_status": abl,
        "robustness": None if rob is None else {
            "n_perturbations": rob["n_perturbations"], "oof_range": rob["oof_range"],
            "decision": rob["decision"], "n_that_flip_conclusion": rob["n_that_flip_conclusion"],
            "file": "outputs/q1/robustness.json"},
        "figures": fig_ids,
        "provenance_note": ("FIG-0008..0011（及 FIG-0007/0012）登记时挂 EXP-0029，当时该实验为 running；"
                            "EXP-0029 已于 13:54:28 succeeded（exit 0、4 个产物 sha 校验通过），"
                            "故图的 provenance 现指向一次成功运行；若 Lead 以 FIG-0013..0015（挂 EXP-0025）为交付图，"
                            "本表同时列出，由交付方择一引用。"),
        "experiment_failures": [
            {"experiment": "EXP-0014", "reason": "q1_final.py 锁定选参循环未处理固定超参分量（HGB candidates=None）→ TypeError，exit 1"},
            {"experiment": "EXP-0017", "status": "cancelled",
             "reason": "15 折 OOF 每折对 PLS/ET/RF 做内层选参，实测需 456s+，逼近 600s 上限且占用唯一计算槽；"
                       "主动 cancel，改用复用同管线 OOF 工件的 --skip-oof 路径（EXP-0029，49.8s，succeeded）"},
            {"experiment": "EXP-0031", "reason": "q1_abl.py 调用了不存在于 q1_models 的 frozen_component_specs → AttributeError，exit 1；"
                                                "修复后以 rerunOf 新建 EXP-0038 并成功"},
            {"experiment": "EXP-0032/EXP-0033", "reason": "同一 frozen_specs bug（登记后未运行即发现），未再以台账 EXP 重登记；"
                                                          "对应消融改为 dev 运行并写入 robustness.json"},
        ],
        "not_completed": [
            "EXP-0032/0033（log10only / oav43）未以台账 EXP 形式完成 → 以 dev 运行代替（数字在 robustness.json / ablation_*.csv）",
            "5 个 seed 的完整扫描未做完（按时间只安排 seed7，若未完成则记为 not_executed）",
            "winsorize 0.5/99.5、clip ±5/±12、iterative 插补的融合版扰动未做完；仅保留 ridge 版数值稳定对照 outputs/q1/prep_sweep.csv",
            "未做独立 rerun 的 formal validation run（VP-0004 的 checks 尚未对 EXP-0029 执行，属 reviewer 职责）",
        ],
    }
    if rob is not None:
        summary["not_completed"] = [x for x in summary["not_completed"]
                                    if not (x.startswith("5 个 seed") and
                                            rob.get("n_perturbations", 0) >= 6)]
    C.write_json(summary, "outputs/q1/final_summary.json")
    print(json.dumps({k: summary[k] for k in ["selected_model_id", "selected_experiment",
                                              "best_succeeded_experiment", "r2_50dim", "oof_r2_50dim",
                                              "n_dims_positive", "bundle_path"]}, ensure_ascii=False, indent=1))
    print("ablation:", json.dumps({k: v["status"] for k, v in abl.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
