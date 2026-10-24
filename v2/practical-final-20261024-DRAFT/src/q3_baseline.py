"""Q3 基线生成器：**风格内均值 + 对角协方差高斯**（style-mean diagonal Gaussian）。

这是主模型（PCA 低秩 + 共享收缩协方差 + 条件均值锚定）的退化版本：不做低秩投影、不共享
协方差，只在 z 空间逐维用风格内均值与方差采样。作为"最简可跑基线"用于 baseline-ready 检查点。

口径与主模型完全一致：
* 生成空间 = 1.csv 231 列；预处理（中位数插补 + 逐列 log1p/identity + z 标准化）只在训练折拟合；
* 生成 -> 逆变换 -> 逐列训练支撑裁剪；物理浓度列非负；
* 风格分类器（5 折 CV 选型）与留出真值基线、能量距离、D_ref、缺陷 OAV 口径同主实验；
* 迁移：目标 = Tripel 风格均值，缺陷列取 min(目标, 原值)，再夹到支撑域（硬约束闭式可行解）；
* r2 / r2_overall = 1 - ED/D_ref(Tripel)（**包合同占位语义，不是 R²**，见 emit 的 metricNote）。
"""
from __future__ import annotations

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
import q3_eval as EV  # noqa: E402

try:
    import emit as E
except Exception:  # noqa: BLE001
    E = None

SEED = U.SEED
N_PER_STYLE = 200
TARGET = "Tripel"
SOURCE = "Pils/Lager"


def fit_baseline(Z, y):
    styles = list(np.unique(y))
    mu, var = {}, {}
    pooled_var = Z.var(axis=0, ddof=1) + 1e-8
    for s in styles:
        Zs = Z[y == s]
        mu[s] = Zs.mean(0)
        if len(Zs) >= 3:
            var[s] = Zs.var(axis=0, ddof=1) + 1e-8
        else:                       # 小样本退回合并方差，避免 n=1 时方差为 0
            var[s] = 0.5 * Zs.var(axis=0, ddof=1) + 0.5 * pooled_var + 1e-8
    return {"styles": styles, "mu": mu, "var": var}


def sample_baseline(model, style, n, rng):
    mu = model["mu"][style]
    sd = np.sqrt(model["var"][style])
    return mu[None, :] + rng.standard_normal((int(n), len(mu))) * sd[None, :]


def main():
    print("== Q3 baseline: style-mean diagonal Gaussian ==")
    tab = U.load_style_table()
    split = U.load_split("primary")
    prep = U.fit_preprocessor(tab, split["train_beer"])
    Ztr = prep.transform(U.train_matrix(tab, split["train_beer"]))
    ytr = tab.set_index("beer").loc[split["train_beer"], "style"].values
    styles = sorted(set(tab["style"]))
    sid = M.style_id_map(styles)
    sel = U.load_json("outputs/q3/model_selection.json")
    clf_name = sel["classifier_selected"]
    clf = U.fit_style_classifier(Ztr, ytr, clf_name)
    base = fit_baseline(Ztr, ytr)

    # ---------------- 生成（主 seed + 5 seed 稳定性） ----------------
    SEEDS = [42, 7, 2024, 123, 9]
    gen = {}
    for seed in SEEDS:
        rng = np.random.default_rng(seed * 100_000 + 11)
        rows = []
        for s in styles:
            n = N_PER_STYLE if s in U.REQUIRED_STYLES else 100
            Zg = sample_baseline(base, s, n, rng)
            A = prep.clip(prep.inverse(Zg))
            df = pd.DataFrame(A, columns=U.FEATURES)
            df.insert(0, "style", s)
            df.insert(1, "sample_id", [f"BASE-{s.replace('/', '-')}-{seed}-{i:03d}"
                                       for i in range(n)])
            df.insert(2, "seed", seed)
            rows.append(df)
        gen[seed] = pd.concat(rows, ignore_index=True)
    U.write_csv(gen[SEED], "outputs/q3/baseline_generated_spectra.csv")

    # ---------------- 留出评估 ----------------
    tg = C.load_targets().set_index("beer")
    Zte = prep.transform(U.train_matrix(tab, split["test_beer"]))
    yte = tab.set_index("beer").loc[split["test_beer"], "style"].values
    hit, ed, ed_all, dref, hit_base, base_n = {}, {}, {}, {}, {}, {}
    for s in styles:
        Zg = prep.transform(gen[SEED][gen[SEED]["style"] == s][U.FEATURES])
        pred = clf.predict(Zg)
        hit[s] = float(np.mean(pred == s))
        ref_hold = [b for b in split["test_beer"]
                    if tab.set_index("beer").loc[b, "style"] == s]
        Zr_h = (prep.transform(U.train_matrix(tab, np.array(ref_hold)))
                if ref_hold else np.empty((0, U.N_FEATURES)))
        Zr_all = prep.transform(U.train_matrix(
            tab, tab.set_index("beer").loc[tab.set_index("beer")["style"] == s].index.values))
        Ztr_s = Ztr[ytr == s]
        dref[s] = M.d_ref_value(Ztr_s)
        e = U.energy_distance(Zg, Zr_h) if len(ref_hold) else {"ed": np.nan}
        ed[s] = e["ed"]
        ed_all[s] = U.energy_distance(Zg, Zr_all)["ed"]
        m = yte == s
        base_n[s] = int(m.sum())
        hit_base[s] = float((clf.predict(Zte[m]) == s).mean()) if m.sum() else np.nan

    macro_hit = float(np.mean([hit[s] for s in styles]))
    ed_ratio_tripel = float(ed[TARGET] / dref[TARGET]) if dref[TARGET] else np.nan

    # ---------------- 缺陷越阈率 ----------------
    dtbl = U.defect_compound_table()
    def_exceed = {}
    for comp in ["DMS", "X2.3.butanedione", "X4VG"]:
        g = pd.concat([gen[SEED][gen[SEED]["style"] == s] for s in styles])
        oav = U.oav_features(g[comp].values.astype(float), dtbl[comp])
        real = U.oav_features(tab.set_index("beer")[comp].values.astype(float), dtbl[comp])
        def_exceed[comp] = {"generated": float(np.nanmean(oav > 1)),
                            "real_all": float(np.nanmean(real > 1))}

    # ---------------- 迁移（目标 = 风格均值，缺陷夹紧；闭式可行） ----------------
    lo, hi = prep.tau_bounds()
    mu_T = base["mu"][TARGET]
    src = tab.set_index("beer")
    src = src[src["style"] == SOURCE]
    defect_idx = prep.defect_index(U.DEFECT_COMPOUNDS)
    trans_before, trans_after = [], []
    viol_cells, feas = 0, 0
    for beer, row in src.iterrows():
        x0 = row[U.FEATURES].values.astype(float)
        if np.isnan(x0).any():
            x0 = np.where(np.isnan(x0), prep.median, x0)
        u0 = prep.forward_raw(x0)[0]
        tau = mu_T.copy()
        tau[defect_idx] = np.minimum(tau[defect_idx], (u0 - prep.mean)[defect_idx] / prep.std[defect_idx])
        u = np.clip(tau * prep.std + prep.mean, lo, hi)
        x = prep.backward_raw(u)[0]
        dv = np.maximum(x[defect_idx] - x0[defect_idx], 0.0)
        viol_cells += int((dv > 1e-12).sum())
        feas += int(dv.max() <= 1e-9)
        trans_before.append(x0)
        trans_after.append(x)
    Zb = prep.transform(pd.DataFrame(np.vstack(trans_before), columns=U.FEATURES))
    Za = prep.transform(pd.DataFrame(np.vstack(trans_after), columns=U.FEATURES))
    transfer_hit_before = float(np.mean(clf.predict(Zb) == TARGET))
    transfer_hit_after = float(np.mean(clf.predict(Za) == TARGET))
    transfer_feasible_rate = float(feas / len(src))

    # ---------------- 感官画像（占位映射，只作一致性参考） ----------------
    prof = EV.placeholder_profile_predictor(prep, tab, split)
    prof_summary, prof_df, _ = EV.profile_consistency(
        prof, tab, split,
        {s: gen[SEED][gen[SEED]["style"] == s][U.FEATURES].values for s in styles}, prep)
    req = prof_summary["required_styles_mean"]
    _gen = {s: gen[SEED][gen[SEED]["style"] == s][U.FEATURES].values for s in styles}
    _P = prof["predict"](np.vstack([_gen[s] for s in styles]))
    _style_order = np.concatenate([[s] * len(_gen[s]) for s in styles])
    prof_matrix_df = pd.DataFrame(_P, columns=[f"z_{d}" for d in C.TARGET_DIMS])
    prof_matrix_df.insert(0, "style", _style_order)
    _pred_df, _r2_profile = EV.profile_prediction_frame(prof_matrix_df, tg, split,
                                                        U.REQUIRED_STYLES)
    _r2_50dim = req["spearman"]

    # ---------------- 落盘 + emit ----------------
    metrics = {
        "ed_over_dref_tripel": ed_ratio_tripel,
        "style_hit_macro": macro_hit,
        "style_hit_tripel": hit[TARGET],
        "style_hit_kriek": hit["Kriek"],
        "style_hit_lambic": hit["Lambic"],
        "defect_violation_rate": float(viol_cells) / max(len(src) * len(defect_idx), 1),
        "transfer_feasible_rate": transfer_feasible_rate,
        "transfer_tripel_hit_rate": transfer_hit_after,
        "transfer_tripel_hit_before": transfer_hit_before,
        "r2": _r2_profile,
        "r2_50dim": _r2_50dim,
        "baseline_holdout_accuracy": float((clf.predict(Zte) == yte).mean()),
        "n_features": int(U.N_FEATURES),
        "stochastic": True,
        "seed": SEED,
    }
    metrics = {k: float(v) for k, v in metrics.items() if v is not None}
    U.write_json({"metrics": metrics,
                  "per_style": {s: {"hit_rate": hit[s], "baseline_holdout_hit": hit_base[s],
                                    "n_test": base_n[s], "ed_holdout": ed[s],
                                    "ed_all_real": ed_all[s], "d_ref": dref[s]}
                                for s in styles},
                  "defect_exceedance": def_exceed,
                  "profile": {"source": prof_summary["profile_source"],
                              "required_styles_mean": req,
                              "r2_definition": "单列预测合同的 R²：required 三风格 × 50 维画像"
                                               "（y_true=留出同风格真值均值，y_pred=生成画像均值）",
                              "r2_50dim_definition": "required 三风格 50 维画像 Spearman 均值",
                              "note": "占位前向映射，不是 Q1 锁定模型"},
                  "transfer": {"feasible_rate": transfer_feasible_rate,
                               "violation_cells": viol_cells,
                               "hit_before": transfer_hit_before,
                               "hit_after": transfer_hit_after},
                  "emit_metricNote": "r2/r2_overall 为包合同占位：r2 = 1 - ED/D_ref(Tripel)，"
                                     "不是 R²；r2_overall = 1 - 平均画像 MAE（required 三风格）"},
                 "outputs/q3/baseline_metrics.json")

    pred_df = _pred_df

    if E is not None and E.IN_RUNNER:
        E.emit_metrics(metrics, area="q3")
        E.emit_predictions(pred_df, "predictions.csv", area="q3")
        E.emit_output("baseline_per_style", U.clean_json(
            {s: {"hit_rate": hit[s], "baseline_holdout_hit": hit_base[s],
                 "n_test": base_n[s], "ed_holdout": ed[s], "d_ref": dref[s]} for s in styles}),
            area="q3")
        E.emit_output("generated_spectra", U.clean_json(
            gen[SEED].head(50).to_dict(orient="records")), area="q3")
        E.emit_output("baseline_transfer", U.clean_json(
            {"feasible_rate": transfer_feasible_rate, "violation_cells": viol_cells,
             "hit_before": transfer_hit_before, "hit_after": transfer_hit_after}), area="q3")

    print(f"[done] baseline metrics: ED/Dref Tripel={ed_ratio_tripel:.4f} "
          f"hit macro={macro_hit:.3f} Tripel={hit[TARGET]:.3f} "
          f"transfer feasible={transfer_feasible_rate:.2f} hit={transfer_hit_after:.2f}")
    print("METRICS_JSON " + pd.Series(metrics).to_json())


if __name__ == "__main__":
    main()
