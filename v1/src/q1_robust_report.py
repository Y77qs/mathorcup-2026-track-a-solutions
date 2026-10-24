"""汇总 Q1 稳健性：把消融 EXP（台账）+ 扰动/种子 dev 扫描（ablation_sweep.csv）合并成 robustness.json。

判定规则（Lead 已在执行扫描前把 ROB-0001 的 metricKey 改为 `oof_r2_50dim`）：
  * 主配置 OOF R²(50 维均值) 为参考点 r0；
  * 所有扰动/种子的 OOF R² 极差 range = max - min；
  * decisionRule = absolute-range ≤ 0.05 → passed；
  * 逐个扰动报告 Δ = r - r0 与是否改变"融合优于单条 ET（OOF 0.2319）"这一结论方向。

不读 holdout 判稳健性（holdout 只用于主分割 + 分层复核两次），holdout 数字仅作补充列。
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
LIMIT = 0.05
ET_SINGLE_OOF = 0.2319  # src/q1_models.py 的 B3_extratrees 15 折 OOF（同一折法）


def ledger_metrics() -> dict:
    led = json.loads((ROOT / "state" / "ledger.json").read_text(encoding="utf-8"))
    out = {}
    for e in led.get("experiments", []):
        out[e["id"]] = {"status": e.get("status"), "family": (e.get("params") or {}).get("family"),
                        "ablation": (e.get("params") or {}).get("ablation"),
                        "metrics": e.get("metrics") or {}}
    return out


def main():
    rows = []
    led = ledger_metrics()
    # 1) 消融 EXP（台账真跑的）
    for eid, rec in led.items():
        if rec["ablation"] in ("noagg", "oav43", "log10only") and rec["status"] == "succeeded":
            m = rec["metrics"]
            rows.append({
                "perturbation": rec["ablation"],
                "kind": "feature-block",
                "source": f"{eid} (ledger)",
                "oof_r2_50dim": m.get("oof_r2_50dim", m.get("oof_r2_mean")),
                "holdout_r2_50dim": m.get("r2_50dim"),
                "holdout_r2_overall": m.get("r2"),
                "n_features": m.get("n_features"),
            })
    # 2) 扰动 / 种子 dev 扫描
    sweep = OUT / "ablation_sweep.csv"
    if sweep.exists():
        d = pd.read_csv(sweep)
        for _, r in d.iterrows():
            if r["config"] in ("main",):
                continue
            rows.append({
                "perturbation": r["config"], "kind": ("fold-seed" if str(r["config"]).startswith("seed")
                                                      else "param-perturbation"),
                "source": "ablation_sweep.csv (dev run, same code path)",
                "oof_r2_50dim": r["oof_r2_50dim"], "holdout_r2_50dim": r.get("holdout_r2_50dim"),
                "holdout_r2_overall": r.get("holdout_r2_overall"), "n_features": r["n_features"],
                "desc": r.get("desc"),
            })
    # 3) 主配置参考点（EXP-0029 真实 holdout + 复用 OOF 工件）
    ref = led.get("EXP-0029", {}).get("metrics", {})
    r0 = ref.get("oof_r2_mean")
    if r0 is None and sweep.exists():
        d = pd.read_csv(sweep)
        r0 = float(d.loc[d.config == "main", "oof_r2_50dim"].iloc[0])
    if not rows:
        print("no robustness rows; run ablations first")
        return
    df = pd.DataFrame(rows).sort_values("oof_r2_50dim")
    vals = df["oof_r2_50dim"].dropna().to_numpy(float)
    rng = float(vals.max() - vals.min())
    df["delta_vs_main"] = df["oof_r2_50dim"] - r0
    df["changes_conclusion_vs_et"] = df["oof_r2_50dim"] < ET_SINGLE_OOF
    report = {
        "generated_by": "src/q1_robust_report.py",
        "plan": "ROB-0001 (metricKey=oof_r2_50dim, absolute-range ≤ 0.05)",
        "main_config": {"family": "B6_fusion", "oof_r2_50dim": r0,
                        "holdout_r2_50dim": ref.get("r2_50dim"),
                        "holdout_r2_overall": ref.get("r2"),
                        "source": "EXP-0029"},
        "n_perturbations": int(len(df)),
        "oof_range": rng,
        "decision": "passed" if rng <= LIMIT else "failed",
        "decision_rule": {"type": "absolute-range", "limit": LIMIT, "actual": rng},
        "reference_for_conclusion": {"single_model_et_oof_r2_50dim": ET_SINGLE_OOF,
                                     "note": "融合优于单模 ET 的结论在多少个扰动下仍成立"},
        "n_that_flip_conclusion": int(df["changes_conclusion_vs_et"].sum()),
        "table": df.to_dict(orient="records"),
        "holdout_note": ("holdout 只使用 2 次（主分割 SPLIT-0002 + 分层复核），"
                         "holdout_r2_50dim 列仅作补充，不参与稳健性判定（dataUse.maxHoldoutReuse=3）"),
        "missing_perturbations": [],
    }
    C.write_csv(df, "outputs/q1/robustness.csv")
    C.write_json(report, "outputs/q1/robustness.json")
    print(json.dumps({k: report[k] for k in ["n_perturbations", "oof_range", "decision",
                                             "n_that_flip_conclusion"]}, ensure_ascii=False, indent=1))
    print(df[["perturbation", "kind", "oof_r2_50dim", "delta_vs_main"]].to_string(index=False))


if __name__ == "__main__":
    main()
