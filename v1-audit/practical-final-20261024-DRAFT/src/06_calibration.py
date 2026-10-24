"""协议层：0–6 分级标定的登记与敏感性对照（Lead 所有）。

背景（reviewer MAJOR-3 的核实结论）：
  4.csv 逐列均值≈0（max|mean|=0.0628）但逐列标准差 0.3697–0.8585（中位 0.5536），
  **不是**逐列单位方差标准化。因此"z=0 ↔ 等级3""1 个 z 单位 ↔ 1 个等级"都无法从 4.csv 辨识。
本脚本把标定改成"外部物理锚定 + 三套替代口径"，并把全部参数落到台账可回读的文件里。

四套口径（预注册，先定后用）：
  P1_oav_anchor（主）: v ≈ a + s·log10(ΣOAV)；OAV=1（恰可察觉）↔ 等级 1；每数量级 ↔ +1 等级。
                       仅当 Spearman(v, log10ΣOAV) ≥ 0.30 且斜率>0 时接受；否则用已锚定维度的 (a,s) 中位迁移。
  P2_range           : 该维观测极差线性铺到 0..6（假设样本覆盖全量程）。
  P3_quantile        : 1/7 分位切 7 档（假设等级近似均匀）。
  P4_sigma           : g = clip(floor(v/S+3.5),0,6)，S=1（旧口径，保留对比）。
参数一律只在本划分的训练 200 样本上估计，再应用到全部 250。

输出：outputs/protocol/grade_calibration.csv / grade_calibration.json / corr2_map.csv
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def main():
    t = C.load_targets()
    beer_order = pd.read_csv(C.RAW / "1.csv")["beer"].tolist()
    # 两套划分都要给标定参数：主评估用台账 SPLIT-0001，稳健性复核用分层版
    split_specs = []
    p_off = C.SPLITS / "SPLIT-0001" / "assignment.csv"
    if p_off.exists():
        a = pd.read_csv(p_off)
        a["beer"] = [beer_order[i] for i in a["row_index"].astype(int)]
        split_specs.append(("SPLIT-0001", a[["beer", "split"]]))
    p_strat = C.SPLITS / "assignment.csv"
    if p_strat.exists():
        split_specs.append(("stratified", pd.read_csv(p_strat)[["beer", "split"]]))
    if not split_specs:
        raise SystemExit("no split file found")

    all_reports = {}
    for tag, adf in split_specs:
        tr = adf[adf["split"] == "train"]
        train_beers = set(tr["beer"].tolist())
        train_t = t[t["beer"].isin(train_beers)]
        print(f"[calib:{tag}] train n={len(train_t)} test n={int((adf['split']=='test').sum())}")
        _calibrate_one(t, train_t, tag)
        all_reports[tag] = tag
    print("[calib] done for splits:", list(all_reports))


def _calibrate_one(t, train_t, tag):
    global TAG
    TAG = tag

    anchor = C.fit_oav_anchor(train_t)
    rows = []
    for d in C.TARGET_DIMS:
        r = anchor[anchor["dim"] == d].iloc[0]
        v_tr = train_t.set_index("beer")[d].astype(float)
        rec = {
            "dim": d,
            "oav_status": r["status"],
            "oav_drivers": r["drivers"],
            "oav_rho": r["rho"],
            "P1_a": r["a"],
            "P1_s": r["s"],
            "P2_lo": float(v_tr.min()),
            "P2_hi": float(v_tr.max()),
            "P3_q": json.dumps([float(x) for x in np.nanquantile(v_tr.values, np.linspace(0, 1, 8)[1:-1])]),
            "P4_S": 1.0,
        }
        rows.append(rec)
    cal = pd.DataFrame(rows)
    C.write_csv(cal, f"outputs/protocol/grade_calibration_{TAG}.csv")

    # 四套口径在全部 250 样本上的分级分布与两两 QWK（只作口径对照，不是外部验证）
    t2 = t.set_index("beer")
    dist = {}
    grades = {}
    for pol in ["P1_oav_anchor", "P2_range", "P3_quantile", "P4_sigma"]:
        g = np.zeros((len(t2), len(C.TARGET_DIMS)), dtype=int)
        for j, d in enumerate(C.TARGET_DIMS):
            r = cal[cal["dim"] == d].iloc[0]
            pars = {"a": r["P1_a"], "s": r["P1_s"], "lo": r["P2_lo"], "hi": r["P2_hi"], "S": r["P4_S"]}
            g[:, j] = C.grade_policy(t2[d].values, pol, pars)
        grades[pol] = g
        dist[pol] = {d: [int(x) for x in np.bincount(g[:, j], minlength=7)]
                     for j, d in enumerate(C.TARGET_DIMS)}

    pair_qwk = {}
    pols = list(grades)
    for i in range(len(pols)):
        for j in range(i + 1, len(pols)):
            q = [C.qwk(grades[pols[i]][:, k], grades[pols[j]][:, k]) for k in range(len(C.TARGET_DIMS))]
            pair_qwk[f"{pols[i]} vs {pols[j]}"] = {
                "qwk_mean": float(np.nanmean(q)), "qwk_min": float(np.nanmin(q)),
                "qwk_max": float(np.nanmax(q)),
            }
    # 排序一致性：各口径下"样本排序"与连续 v 排序一致是否恒成立（应恒成立，作 sanity）
    order_consistent = {}
    for pol in pols:
        ok = 0
        for j, d in enumerate(C.TARGET_DIMS):
            v = t2[d].values
            g = grades[pol][:, j]
            from scipy.stats import spearmanr
            ok += 1 if abs(float(spearmanr(v, g).statistic)) > 0.999 else 0
        order_consistent[pol] = ok

    n_anchor = int((cal["oav_status"] == "anchored").sum())
    report = {
        "measured_facts": C.Z_GRADE_CALIBRATION["measured_facts"],
        "policies": C.Z_GRADE_CALIBRATION["policies"],
        "primary": "P1_oav_anchor",
        "n_dims_anchored": n_anchor,
        "n_dims_transfer": int(len(cal) - n_anchor),
        "anchored_dims": cal.loc[cal["oav_status"] == "anchored", "dim"].tolist(),
        "anchor_rho_mean": float(cal.loc[cal["oav_status"] == "anchored", "oav_rho"].mean()),
        "anchor_rho_min": float(cal.loc[cal["oav_status"] == "anchored", "oav_rho"].min()),
        "weak_anchor_dims": cal.loc[cal["oav_status"].str.startswith(("weak", "no_driver", "too_few")), "dim"].tolist(),
        "grade_distribution": dist,
        "pairwise_qwk_between_policies": pair_qwk,
        "order_preserved_dims": order_consistent,
        "caveat": ("四套口径之间的一致性只能说明'分级标定的口径敏感性'，**不是外部效度验证**："
                   "4.csv 的原始等级未知，任何 QWK 都不是真实等级上的准确率。"),
        "fit_scope": f"参数只在训练集(n={len(train_t)})估计，应用到全部 250",
    }
    C.write_json(report, f"outputs/protocol/grade_calibration_{TAG}.json")

    mp = C.corr2_mapping()
    C.write_csv(mp, "outputs/protocol/corr2_map.csv")
    C.write_json({
        "n_features": int(len(mp)),
        "n_named": int((mp["via"] != "positional(index)").sum()),
        "n_positional_only": int((mp["via"] == "positional(index)").sum()),
        "positional_agreement_among_named": float(mp.loc[mp["via"] != "positional(index)",
                                                        "positional_agrees_with_name"].mean()),
        "verdict": "2.csv 行列用化学全名，与 1.csv 列名按名字几乎对不上；"
                   "但 2.csv 第 i 行/列 ≡ 1.csv 第 i 个特征列（位置映射，209 个可命名的全部位置一致）",
    }, "outputs/protocol/corr2_map.json")

    print(f"[calib] anchored={n_anchor}/50  weak={len(report['weak_anchor_dims'])}")
    for k, v in pair_qwk.items():
        print(f"  {k}: QWK_mean={v['qwk_mean']:.3f}")
    print("[calib] corr2 map:", json.loads(open(C.ROOT / 'outputs/protocol/corr2_map.json').read())["verdict"][:60])
    print(json.dumps({k: report[k] for k in ["n_dims_anchored", "anchored_dims"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
