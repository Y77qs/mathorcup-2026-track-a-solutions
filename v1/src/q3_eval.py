"""Q3 评估：风格保真度、分布吻合、缺陷越阈率、感官画像一致性、小样本不确定度、跨 seed 稳定性。

评价口径（预先登记于 VP-0003，不在看到结果后改动）
--------------------------------------------------
(i)   风格保真度：在 200 个训练样本上做 5 折 CV 训练的风格分类器（LogisticRegression 或
      HistGradientBoosting，按 CV 准确率选），判别生成样本是否被判为目标风格；基线 = 同一分类器对
      留出真值样本的逐风格命中率（Wilson 95% CI）。
(ii)  分布吻合：z 空间能量距离（ed2 = 2E||x-y|| - E||x-x'|| - E||y-y'||）与 RBF-MMD^2，
      参考集 = 留出真值同风格样本（逐 beer 列明）；另报"全部真值样本"作为较软的参考。
(iii) 缺陷：DMS / Diacetyl(X2.3.butanedione) / 4VG 用 8.xlsx 作者阈值算 OAV（>1 视为超阈）；
      trans-2-nonenal 与 Stale hops 无阈值，只报浓度分布，不报越阈率（不得臆造阈值）。
(iv)  感官画像：生成谱经前向映射（Q1 model_bundle；未就绪时用 4.csv 训练折上的 Ridge 占位，
      明确标注 profile_source）得到 50 维 ẑ 与 0–6 分级；与同风格真值画像做 Spearman/MAE。
(v)   小样本：Kriek/Lambic/Faro 的均值/协方差 bootstrap CI。
(vi)  跨 seed：5 个 seed 的指标波动（相对极差）与同 seed 逐值复现。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import q3_utils as U  # noqa: E402
import q3_models as M  # noqa: E402

try:
    import emit as E
except Exception:  # noqa: BLE001
    E = None

SEEDS = [42, 7, 2024, 123, 9]
PRIMARY = 42
N_REQUIRED = 200
N_OTHER = 100


# ---------------------------------------------------------------- 小工具
def wilson_ci(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(max(0.0, centre - half)), float(min(1.0, centre + half))]


def style_vec(tab, beer):
    return tab.set_index("beer").loc[beer, "style"].values


def n_by_style(styles):
    return {s: (N_REQUIRED if s in U.REQUIRED_STYLES else N_OTHER) for s in styles}


# ---------------------------------------------------------------- 前向映射（感官画像）
def placeholder_profile_predictor(prep, tab, split):
    """占位前向映射：只用训练折的 (231 特征 -> 4.csv 50 维) 岭回归，alpha 在训练内 5 折选。

    明确标注 profile_source = placeholder_ridge_4csv_train：
    它不是 Q1 的锁定模型，只用于在 Q1 model_bundle 到位前跑通链路；4.csv 不参与生成模型训练。
    """
    from sklearn.linear_model import Ridge

    tg = C.load_targets().set_index("beer")
    Y = tg.loc[split["train_beer"], C.TARGET_DIMS].values.astype(float)
    Z = prep.transform(U.train_matrix(tab, split["train_beer"]))
    folds = U.stratified_folds(style_vec(tab, split["train_beer"]), k=5, seed=U.SEED)
    grid = [10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0]
    cv = {}
    for a in grid:
        scores = []
        for f in folds:
            mask = np.ones(len(Z), bool)
            mask[f] = False
            m = Ridge(alpha=a).fit(Z[mask], Y[mask])
            scores.append(float(np.nanmean(C.r2(Y[f], m.predict(Z[f])))))
        cv[a] = float(np.mean(scores))
    alpha = max(cv, key=cv.get)
    mdl = Ridge(alpha=alpha).fit(Z, Y)

    def predict(spectra_raw: np.ndarray) -> np.ndarray:
        Zg = prep.transform(pd.DataFrame(spectra_raw, columns=U.FEATURES))
        return mdl.predict(Zg)

    hold_r2 = None
    try:
        Yte = tg.loc[split["test_beer"], C.TARGET_DIMS].values.astype(float)
        Zte = prep.transform(U.train_matrix(tab, split["test_beer"]))
        hold_r2 = float(np.nanmean(C.r2(Yte, mdl.predict(Zte))))
    except Exception:
        pass
    return {
        "source": "placeholder_ridge_4csv_train",
        "predict": predict,
        "meta": {
            "description": "岭回归占位映射（训练折 200 样本；alpha 在训练内 5 折按 50 维平均 R² 选），"
                           "非 Q1 锁定模型",
            "alpha_selected": alpha,
            "alpha_cv_r2": {str(k): v for k, v in cv.items()},
            "train_internal_cv_r2_mean_50dims": cv[alpha],
            "holdout_r2_mean_50dims": hold_r2,
            "style_mean_baseline_holdout_r2_mean": _style_mean_r2(tg, split),
            "train_rows": int(split["n_train"]),
            "uses_4csv": "只用于此占位映射的拟合与评估，不进入风格条件生成模型",
        },
    }


def _style_mean_r2(tg, split) -> float:
    """风格均值画像基线在留出集上的 50 维平均 R²（对照占位映射是否有增益）。"""
    cols = C.TARGET_DIMS
    tr = tg.loc[split["train_beer"]]
    te = tg.loc[split["test_beer"]]
    Ytr, Yte = tr[cols].values.astype(float), te[cols].values.astype(float)
    mus = {s: Ytr[tr["tasting_category_fine"].values == s].mean(0)
           for s in set(tr["tasting_category_fine"])}
    g = Ytr.mean(0)
    pred = np.array([mus.get(s, g) for s in te["tasting_category_fine"].values])
    return float(np.nanmean(C.r2(Yte, pred)))




def profile_consistency_mapper(profile, tab, split, gen_by_style):
    """同一个前向映射器下比较生成谱与真值谱的 50 维画像。

    关键纪律：生成侧与真值侧**必须过同一个映射器**，否则比较无意义。
    baseline（同一映射器） = 把"训练折同风格均值谱"过同一映射器得到的画像，
    用来回答"生成谱是否比'只吐风格均值'携带更多画像信息"。
    """
    rows = []
    t = tab.set_index("beer")
    styles_all = list(gen_by_style)
    for style in styles_all:
        A = np.asarray(gen_by_style[style], float)
        P_gen = profile["predict"](A)
        ref_hold = [b for b in split["test_beer"] if t.loc[b, "style"] == style]
        tr_beer = [b for b in split["train_beer"] if t.loc[b, "style"] == style]
        if not ref_hold:
            continue
        P_ref = profile["predict"](U.train_matrix(tab, np.array(ref_hold)))
        p_ref = P_ref.mean(0)
        rho = float(spearmanr(P_gen.mean(0), p_ref).statistic)
        mae = float(np.mean(np.abs(P_gen.mean(0) - p_ref)))
        per_sample = [spearmanr(P_gen[i], p_ref).statistic for i in range(len(P_gen))]
        # 同一映射器下的"风格均值谱"基线
        if tr_beer:
            Xtr_s = U.train_matrix(tab, np.array(tr_beer))
            mu_spec = Xtr_s.mean(0).values
            P_base = profile["predict"](mu_spec[None, :])[0]
            rho_base = float(spearmanr(P_base, p_ref).statistic)
            mae_base = float(np.mean(np.abs(P_base - p_ref)))
        else:
            rho_base, mae_base = np.nan, np.nan
        rows.append({
            "style": style, "profile_source": profile["source"],
            "n_ref": int(len(ref_hold)), "ref_beers": [int(b) for b in ref_hold],
            "n_gen": int(len(P_gen)),
            "spearman_mean_profile_vs_ref": rho,
            "mae_mean_profile_vs_ref": mae,
            "spearman_per_generated_sample_mean": float(np.nanmean(per_sample)),
            "baseline_same_mapper_spearman": rho_base,
            "baseline_same_mapper_mae": mae_base,
        })
    df = pd.DataFrame(rows)
    req = df[df["style"].isin(U.REQUIRED_STYLES)] if len(df) else df
    summary = {
        "profile_source": profile["source"],
        "profile_meta": profile.get("meta", {}),
        "reference": "留出真值谱，经同一映射器",
        "per_style": df.round(6).to_dict(orient="records") if len(df) else [],
        "required_styles_mean": {
            "spearman": float(np.nanmean(req["spearman_mean_profile_vs_ref"])) if len(req) else None,
            "mae": float(np.nanmean(req["mae_mean_profile_vs_ref"])) if len(req) else None,
            "baseline_same_mapper_spearman": float(
                np.nanmean(req["baseline_same_mapper_spearman"])) if len(req) else None,
            "baseline_same_mapper_mae": float(
                np.nanmean(req["baseline_same_mapper_mae"])) if len(req) else None,
        },
    }
    return summary, df


def load_q1_bundle(tab, split, prep):
    """权威 Q1 bundle（outputs/q1/model_bundle.pkl，经 src/q1_data.py 推理，只做推理）。"""
    p = U.PROJECT / "outputs" / "q1" / "model_bundle.pkl"
    if not p.exists():
        return {"status": "not_available",
                "note": "outputs/q1/model_bundle.pkl 尚未生成；本版用 placeholder"}
    try:
        import q1_data  # noqa: E402
        B = q1_data.load_bundle(p)
    except Exception as e:  # noqa: BLE001
        return {"status": "load_failed", "note": f"{type(e).__name__}: {e}"}
    feats = list(B["features"])

    def predict(spectra_raw):
        X = pd.DataFrame(np.asarray(spectra_raw, float), columns=U.FEATURES)
        return np.asarray(q1_data.bundle_predict(B, X), float)

    meta = {
        "description": "Q1 权威 bundle（modeler-q1 交付；joblib）",
        "bundle_path": "outputs/q1/model_bundle.pkl",
        "bundle_version": B.get("bundle_version"),
        "holdout_r2_50dim": B.get("holdout_r2_50dim"),
        "n_features": len(feats),
        "features_match_q3": feats == list(U.FEATURES),
        "use_rule": "只做推理；不得用 Q3 生成数据或 4.csv 再训练/微调 bundle 参数",
        "readme": "outputs/q1/model_bundle_README.md",
    }
    return {"status": "loaded", "source": "q1_model_bundle", "predict": predict, "meta": meta}


def load_emergency_bundle():
    """Lead 应急 bundle（outputs/q1/model_bundle.pkl.gz；只作对照块 lead_emergency_bundle）。"""
    p = U.PROJECT / "outputs" / "q1" / "model_bundle.pkl.gz"
    if not p.exists():
        return {"status": "not_available", "note": "应急 bundle 不存在"}
    try:
        import q1_bundle  # noqa: E402
        B = q1_bundle.load_bundle()

        def predict(spectra_raw):
            X = pd.DataFrame(np.asarray(spectra_raw, float), columns=U.FEATURES)
            Z, _G = q1_bundle.predict_spectra(B, X)
            return np.asarray(Z, float)

        return {"status": "loaded", "source": "lead_emergency_bundle", "predict": predict,
                "meta": {"description": "Lead 应急 bundle（pls5+ET+RF 均值）",
                         "bundle_path": "outputs/q1/model_bundle.pkl.gz",
                         "holdout_r2_50dim": B.get("holdout_r2_50dim")}}
    except Exception as e:  # noqa: BLE001
        return {"status": "load_failed", "note": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- 画像一致性
def profile_consistency(profile, tab, split, gen_by_style, prep, ref_mode="holdout"):
    """生成画像 vs 同风格真值画像：Spearman（跨 50 维）与 MAE（4.csv z 单位）。"""
    tg = C.load_targets().set_index("beer")
    Y_all = tg[C.TARGET_DIMS]
    rows = []
    for style in sorted(gen_by_style):
        A = gen_by_style[style]
        P = profile["predict"](A)                     # (n_gen, 50)
        p_gen_mean = P.mean(0)
        if ref_mode == "holdout":
            ref_beer = [b for b in split["test_beer"] if tg.loc[b, "tasting_category_fine"] == style]
        else:
            ref_beer = [b for b in split["train_beer"] if tg.loc[b, "tasting_category_fine"] == style]
        if not ref_beer:
            continue
        P_ref = Y_all.loc[ref_beer].values
        p_ref_mean = P_ref.mean(0)
        rho = spearmanr(p_gen_mean, p_ref_mean).statistic
        mae = float(np.mean(np.abs(p_gen_mean - p_ref_mean)))
        # 每个生成样本单独与参考均值的秩相关
        per_sample = [spearmanr(P[i], p_ref_mean).statistic for i in range(len(P))]
        # 基线：训练真值画像的均值（不使用生成谱）
        tr_beer = [b for b in split["train_beer"]
                   if tg.loc[b, "tasting_category_fine"] == style]
        base = Y_all.loc[tr_beer].values.mean(0) if tr_beer else np.full(50, np.nan)
        rho_base = spearmanr(base, p_ref_mean).statistic if tr_beer else np.nan
        mae_base = float(np.mean(np.abs(base - p_ref_mean))) if tr_beer else np.nan
        rows.append({
            "style": style, "profile_source": profile["source"],
            "n_ref": int(len(ref_beer)), "ref_beers": [int(b) for b in ref_beer],
            "spearman_mean_profile_vs_ref": float(rho),
            "mae_mean_profile_vs_ref": mae,
            "spearman_per_generated_sample_mean": float(np.nanmean(per_sample)),
            "baseline_spearman_style_mean_profile": float(rho_base),
            "baseline_mae_style_mean_profile": float(mae_base),
            "n_gen": int(len(P)),
            "grade_range_check": "ẑ 与 0–6 分级同时落盘 sensory_profiles.csv",
        })
    df = pd.DataFrame(rows)
    req = df[df["style"].isin(U.REQUIRED_STYLES)] if len(df) else df
    summary = {
        "profile_source": profile["source"],
        "profile_meta": profile["meta"],
        "reference": ("留出真值样本（holdout）" if ref_mode == "holdout" else "训练真值样本"),
        "per_style": df.round(6).to_dict(orient="records") if len(df) else [],
        "required_styles_mean": {
            "spearman": float(np.nanmean(req["spearman_mean_profile_vs_ref"])) if len(req) else None,
            "mae": float(np.nanmean(req["mae_mean_profile_vs_ref"])) if len(req) else None,
            "baseline_spearman": float(np.nanmean(req["baseline_spearman_style_mean_profile"]))
            if len(req) else None,
            "baseline_mae": float(np.nanmean(req["baseline_mae_style_mean_profile"]))
            if len(req) else None,
        },
    }
    return summary, df, profile["predict"]




def profile_prediction_frame(prof_df, tg, split, styles_required):
    """单列预测合同（row, y_true, y_pred）：required 三风格 × 50 维的画像一致性。

    y_true = 留出真值同风格 50 维画像均值（4.csv z 口径）；
    y_pred = 生成样本画像（同一前向映射）的 50 维均值。
    pack 可以从该单列复算 r2 = 1 - SSE/SST，与 metrics 里的 r2 相同。
    """
    rows = []
    for st in styles_required:
        sub = prof_df[prof_df["style"] == st]
        y_pred = sub[[f"z_{d}" for d in C.TARGET_DIMS]].values.mean(0)
        ref = [b for b in split["test_beer"]
               if tg.loc[b, "tasting_category_fine"] == st]
        if not ref:
            continue
        y_true = tg.loc[ref, C.TARGET_DIMS].values.mean(0)
        for j, _d in enumerate(C.TARGET_DIMS):
            rows.append({"row": len(rows), "y_true": float(y_true[j]),
                         "y_pred": float(y_pred[j])})
    df = pd.DataFrame(rows)
    if len(df) < 2:
        return df, None
    sse = float(((df["y_true"] - df["y_pred"]) ** 2).sum())
    sst = float(((df["y_true"] - df["y_true"].mean()) ** 2).sum())
    return df, (1.0 - sse / sst if sst > 0 else None)


def write_summary_md(metrics, tr):
    """把关键结果写成工作小结（**不是论文正文**；论文数字必须走台账占位符）。"""
    sf = metrics["style_fidelity"]
    dist = metrics["distribution_match"]
    dg = metrics["defect_check_generation"]
    _ps = metrics["sensory_profile"]
    _q1 = _ps.get("q1_model_bundle", {})
    _q1_ok2 = ("profile_source" in _q1 and _q1.get("status") == "loaded")
    prof = (_q1["required_styles_mean"] if _q1_ok2
            else _ps["placeholder"]["required_styles_mean"])
    prof_src = (_q1.get("profile_source", "q1_model_bundle")
                if _q1_ok2 else _ps["placeholder"]["profile_source"])
    fr = (tr or {}).get("feasibility", {})
    sp = (tr or {}).get("style_progress", {})
    req = "Tripel/Kriek/Lambic"
    lines = [
        "# Q3 工作小结（非论文正文；数字以 state/ledger.json 与 outputs/q3/*.json 为准）",
        "",
        f"- 生成模型：A 风格条件低秩高斯（PCA k=15、共享收缩协方差、条件均值锚定；"
        f"log1p 变换 33 列）；CV 选中分数 {metrics['model']['selection_score'] if 'selection_score' in metrics['model'] else sf['classifier']['cv_accuracy']:.3f}",
        "",
        "> **两条禁写（reviewer 登记的 MAJOR）**",
        "> 1. 生成侧的缺陷越阈率高于真实同风格（Tripel DMS 0.975 vs 0.893、diacetyl 0.620 vs 0.464），"
        "**不得声称缺陷水平与真实一致**。",
        "> 2. 迁移只实现部分迁移（Tripel 命中 6/11 = 0.5455），**不得声称已把 Pils/Lager 转成 Tripel**。",
        "",
        f"- 风格分类器 5 折 CV 准确率：{sf['classifier']['cv_accuracy']:.3f}"
        f"（宏 F1 {sf['classifier']['cv_macro_f1']:.3f}，22 类，随机 {sf['classifier']['chance_uniform']:.3f}）",
        "",
        "## 1. 风格保真度（注意饱和）",
        "",
        "| 风格 | 生成命中率（5 seed 均值） | 留出真值基线 | 留出 n |",
        "|---|---|---|---|",
    ]
    for s, v in sf["required_styles"].items():
        lines.append(f"| {s} | {v['hit_rate_mean_over_seeds']:.3f} | "
                     f"{v['baseline_holdout_hit_rate']:.3f} | {v['baseline_holdout_n']} |")
    lines += [
        "",
        f"全风格宏平均命中率 {sf['aggregate_generated_hit_rate']:.3f}，"
        f"留出真值整体准确率 {sf['aggregate_holdout_accuracy']:.3f}。",
        "**警告**：条件均值锚定后命中率饱和（逐风格 0.98–1.00），"
        "该指标对生成质量已无区分度，不能作为“全风格保真”的证据；"
        "有信息量的是能量距离与缺陷/画像一致性。",
        "",
        "## 2. 分布吻合（z 空间能量距离，留出真值参考）",
        "",
        "| 风格 | ED | n_ref | D_ref（训练同风格两两距离中位数） | ED/D_ref |",
        "|---|---|---|---|---|",
    ]
    for s, v in dist["required_styles"].items():
        lines.append(f"| {s} | {v['ed_holdout_seed42']:.3f} | {v['n_ref_holdout']} | "
                     f"{v['d_ref']:.3f} | "
                     f"{v['ed_holdout_seed42'] / v['d_ref']:.3f} |")
    lines += [
        "",
        "Kriek/Lambic 的留出参考只有 1–3 个样本，ED 的参考侧不确定度很大；"
        "分层分割复算一栏见 metrics.json 的 stratified_split_recheck。",
        "",
        "## 3. 缺陷（生成 vs 真实同风格；只有三类有绝对阈值）",
        "",
        "| 风格 | 项 | 生成 OAV>1 比例 | 真实同风格 OAV>1 比例 | Δ |",
        "|---|---|---|---|---|",
    ]
    for s, d in dg["required_style_delta_vs_real"].items():
        for c, v in d.items():
            lines.append(f"| {s} | {c} | {v['generated_exceed_rate']:.3f} | "
                         f"{v['real_exceed_rate']:.3f} | {v['delta']:+.3f} |")
    lines += [
        "",
        "**口径**：DMS/Diacetyl/4VG 用 8.xlsx 绝对阈值；trans-2-nonenal 与 Stale hops 无阈值，"
        "只做“浓度不增”单调代理（is_absolute_threshold=false），不编造阈值。",
        "**禁止**写成“缺陷水平与真实一致”：上表显示生成侧存在缺陷分布偏移"
        "（低秩条件高斯复制了风格内的缺陷共现，未显式建模缺陷稀疏性）。",
        "",
        "## 4. 迁移（Pils/Lager → Tripel）",
        "",
        f"- 硬约束可行性：{fr.get('n_hard_feasible')}/{fr.get('n_samples')} 全满足，"
        f"最大浓度上升 {fr.get('max_defect_violation_raw'):.2e}，"
        f"最大支撑越界 {fr.get('max_box_violation_raw'):.2e}。",
        f"- 迁移后仍被判为 Tripel 的比例：**{sp.get('classifier_hit_as_tripel_after'):.3f}**"
        f"（迁移前 {sp.get('classifier_hit_as_tripel_before'):.3f}），"
        f"到 Tripel 质心的 z 距离 {sp.get('mean_dist_to_tripel_centroid_before_z'):.2f} → "
        f"{sp.get('mean_dist_to_tripel_centroid_after_z'):.2f}；"
        f"个体差异保留率 {sp.get('identity_preservation_ratio_nondef_columns'):.2f}。",
        "- **只能写“部分向 Tripel 质心迁移 / 更接近 Tripel”**，不能写“把 Pils/Lager 转成了 Tripel”。"
        "原因是缺陷硬约束禁止 DMS/双乙酰上升，而这两项恰是区分 Tripel 与 Pils/Lager 的强判别维度。",
        "- 反事实边界：迁移是构造方案，不代表保证的干预收益。",
        "",
        "## 5. 感官画像（同一映射器比较；placeholder 与 Q1 bundle 两版并列）",
        "",
        f"- 交付版 profile_source = **{prof_src}**。",
        f"- required 三风格画像一致性（生成画像 vs 同风格留出真值画像，均过同一映射器）："
        f"Spearman {prof['spearman']:.3f}，MAE {prof['mae']:.3f}；"
        f"同一映射器下“只吐训练风格均值谱”的基线：Spearman "
        f"{prof.get('baseline_same_mapper_spearman', float('nan')):.3f}，MAE "
        f"{prof.get('baseline_same_mapper_mae', float('nan')):.3f}。",
        f"- placeholder 版（对照，同一比较口径）：Spearman "
        f"{_ps['placeholder']['required_styles_mean']['spearman']:.3f}，MAE "
        f"{_ps['placeholder']['required_styles_mean']['mae']:.3f}。",
        "",
        "| profile_source | Spearman | MAE | 同映射器风格均值谱基线 Spearman | 基线 MAE |",
        "|---|---|---|---|---|",
        f"| q1_model_bundle（权威，{(_q1.get('profile_meta', {}) or {}).get('bundle_version')}） | "
        f"{_ps['q1_model_bundle']['required_styles_mean']['spearman']:.3f} | "
        f"{_ps['q1_model_bundle']['required_styles_mean']['mae']:.3f} | "
        f"{_ps['q1_model_bundle']['required_styles_mean']['baseline_same_mapper_spearman']:.3f} | "
        f"{_ps['q1_model_bundle']['required_styles_mean']['baseline_same_mapper_mae']:.3f} |",
        f"| placeholder_ridge_4csv_train（旧） | "
        f"{_ps['placeholder']['required_styles_mean']['spearman']:.3f} | "
        f"{_ps['placeholder']['required_styles_mean']['mae']:.3f} | "
        f"{_ps['placeholder']['required_styles_mean']['baseline_same_mapper_spearman']:.3f} | "
        f"{_ps['placeholder']['required_styles_mean']['baseline_same_mapper_mae']:.3f} |",
        (f"| lead_emergency_bundle（对照，{(_ps['lead_emergency_bundle'].get('profile_meta', {}) or {}).get('holdout_r2_50dim')}） | "
         f"{_ps['lead_emergency_bundle']['required_styles_mean']['spearman']:.3f} | "
         f"{_ps['lead_emergency_bundle']['required_styles_mean']['mae']:.3f} | "
         f"{_ps['lead_emergency_bundle']['required_styles_mean']['baseline_same_mapper_spearman']:.3f} | "
         f"{_ps['lead_emergency_bundle']['required_styles_mean']['baseline_same_mapper_mae']:.3f} |")
        if _ps.get("lead_emergency_bundle", {}).get("status") == "loaded" else "",
        "- **诚实结论**：三种映射器下，生成谱画像与“只吐训练风格均值谱”的基线在同一口径下几乎并列"
        "（权威 bundle：Spearman 0.893 vs 0.892、MAE 0.068 vs 0.082；应急 bundle：0.934 vs 0.928）——"
        "生成谱并未带来超出风格均值谱的画像信息；该指标只能说明“生成谱落在正确的风格画像区域”，"
        "不能说明它比一个退化生成器更好。",
        "- 版本说明：早期版本用占位岭回归（profile_source=placeholder_ridge_4csv_train，"
        "与 4.csv 真值比较）；Q1 bundle 交付后切换为 bundle 推理，并改为“同一映射器”比较。"
        "旧占位块保留在 metrics.json 的 sensory_profile.placeholder，两版不覆盖。",
        "",
        "## 6. 小样本与稳定性",
        "",
        f"- 小样本：Kriek(n=10)/Lambic(n=11)/Faro(n=3) 的均值/协方差 bootstrap CI 见 "
        f"smalln_uncertainty.json；生成均值与真值均值的中位 z 距离 "
        + ", ".join(f"{s}={metrics['small_n_uncertainty']['styles'][s].get('abs_mean_gap_median_z', float('nan')):.3f}"
                    for s in U.SMALL_N_STYLES) + "。",
        f"- 跨 seed（42/7/2024/123/9）稳定性：见 seed_stability.csv；"
        f"ROB-0003 的 ed_over_dref_tripel 绝对极差 "
        f"{(max(r['ed_Tripel'] for r in metrics['seed_stability']['per_seed']) - min(r['ed_Tripel'] for r in metrics['seed_stability']['per_seed'])) / metrics['distribution_match']['required_styles']['Tripel']['d_ref']:.4f}"
        "（判据 absolute-range ≤ 0.05）。",
        "",
        "## 7. 适用边界",
        "",
        "- 结论只适用于这 250 款商用啤酒的经验分布内；不外推到其他酒厂/工艺。",
        "- Kriek(n=10)/Lambic(n=11)/Faro(n=3) 只能给区间估计，不声称精确刻画。",
        "- 命中率饱和、缺陷分布偏移、迁移只是部分迁移，三条都要在论文里如实披露。",
    ]
    # 产物哈希（供 reviewer 按哈希核对）
    hash_targets = [
        "outputs/q3/generated_spectra.csv",
        "outputs/q3/seed_stability.csv",
        "outputs/q3/metrics.json",
        "outputs/q3/energy_distance.csv",
        "outputs/q3/defect_check.csv",
        "outputs/q3/transfer_report.json",
        "outputs/q3/seeds/generated_spectra_seed42.csv",
        "outputs/q3/seeds/generated_spectra_seed7.csv",
        "outputs/q3/seeds/generated_spectra_seed2024.csv",
        "outputs/q3/seeds/generated_spectra_seed123.csv",
        "outputs/q3/seeds/generated_spectra_seed9.csv",
    ]
    lines += ["", "## 8. 产物哈希（SHA256，供 reviewer 按哈希核对）", ""]
    for rel in hash_targets:
        f = U.PROJECT / rel
        if f.exists():
            lines.append(f"- `{rel}`  `{U.sha256(f)}`")
    p = U.PROJECT / "outputs" / "q3" / "results_summary.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_readme(metrics, tr):
    """产物清单 + 复现说明 + 两条禁写（reviewer MAJOR）+ 画像版本说明。"""
    files = [
        "generated_spectra.csv", "generation_diagnostics.json", "metrics.json",
        "robustness.json", "results_summary.md", "style_classifier_report.json",
        "generated_style_probs.csv", "sensory_profiles.csv",
        "sensory_profiles_placeholder.csv", "energy_distance.csv",
        "energy_distance_stratified.csv", "seed_stability.csv",
        "smalln_uncertainty.json", "defect_check.csv",
        "transfer_pils_to_tripel.csv", "transfer_report.json",
        "column_transforms.csv", "leakage_manifest.json", "figure_captions.json",
        "baseline_metrics.json", "baseline_generated_spectra.csv",
    ]
    lines = [
        "# Q3 交付说明（风格条件生成 / 风味指纹 / 跨风格迁移）",
        "",
        "## 1. 两条禁写（reviewer 登记的 MAJOR，论文与 claim limitations 各出现一次）",
        "",
        "1. **生成侧的缺陷越阈率高于真实同风格（Tripel DMS 0.975 vs 0.893、diacetyl 0.620 vs 0.464），"
        "因此不得声称缺陷水平与真实一致。**",
        "2. **迁移只实现部分迁移（Tripel 命中 6/11 = 0.5455），不得声称已把 Pils/Lager 转成 Tripel。**",
        "",
        "## 2. 管线与脚本",
        "",
        "| 步骤 | 脚本 | 说明 |",
        "|---|---|---|",
        "| 预处理/选型 | `src/q3_utils.py`, `src/q3_models.py` | 训练折内中位数插补 + 逐列 log1p/identity + z 标准化；A/B/C 三族训练内 5 折 CV |",
        "| 生成 | `src/q3_generate.py` | 锁定的 A 族（k=15）生成 5 个 seed；逆变换 + 支撑裁剪 |",
        "| 迁移 | `src/q3_transfer.py` | Pils/Lager→Tripel，五类缺陷浓度不增的硬约束（SLSQP + 解析投影兜底） |",
        "| 评估 | `src/q3_eval.py` | 风格命中/ED/MMD/缺陷/画像/小样本/bootstrap/跨 seed |",
        "| 基线 | `src/q3_baseline.py` | 风格均值 + 对角协方差高斯（modelKind=baseline） |",
        "| 图 | `src/q3_figs.py` | 9 张图；中文图注与图元数据见 `figure_captions.json` |",
        "",
        "## 3. 复现",
        "",
        "```",
        "python src/q3_models.py     # 选型（写 model_selection.json 等）",
        "python src/q3_generate.py   # 5 个 seed 的生成谱",
        "python src/q3_transfer.py   # 迁移 + defect_check.csv",
        "python src/q3_eval.py       # metrics/robustness/smalln/seed_stability/画像",
        "python src/q3_figs.py       # 9 张图",
        "```",
        "所有随机性走 `np.random.default_rng(seed)`；同 seed 重新生成逐值一致（见 generation_diagnostics.json）。",
        "",
        "## 4. 感官画像版本说明",
        "",
        "| profile_source | 说明 | 状态 |",
        "|---|---|---|",
        "| `q1_model_bundle`（权威） | `outputs/q1/model_bundle.pkl`（joblib，q1-bundle-1.0），经 `src/q1_data.py` 推理 | 交付版 |",
        "| `placeholder_ridge_4csv_train` | 训练折岭回归占位映射（alpha 训练内 CV） | 旧版保留对照 |",
        "| `lead_emergency_bundle` | `outputs/q1/model_bundle.pkl.gz`（Lead 应急） | 对照块 |",
        "",
        "三块互不覆盖；比较口径统一为“生成谱与同风格留出真值谱过同一映射器”。",
        "",
        "## 5. 产物哈希（SHA256）",
        "",
    ]
    for f in files:
        fp = U.PROJECT / "outputs" / "q3" / f
        if fp.exists():
            lines.append(f"- `outputs/q3/{f}`  `{U.sha256(fp)}`")
    for f in sorted((U.PROJECT / "outputs" / "q3" / "seeds").glob("*.csv")):
        lines.append(f"- `outputs/q3/seeds/{f.name}`  `{U.sha256(f)}`")
    lines += ["", "## 6. 适用边界", "",
              "- 结论只适用于这 250 款商用啤酒的经验分布内。",
              "- Kriek(n=10)/Lambic(n=11)/Faro(n=3) 只给区间估计，不声称精确刻画。",
              "- 迁移是反事实方案，不代表保证的干预收益。"]
    p = U.PROJECT / "outputs" / "q3" / "README.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------- 主流程
def main():
    print("== Q3 eval ==")
    tab = U.load_style_table()
    split = U.load_split("primary")
    prep = U.fit_preprocessor(tab, split["train_beer"])
    Ztr = prep.transform(U.train_matrix(tab, split["train_beer"]))
    ytr = style_vec(tab, split["train_beer"])
    styles = sorted(set(tab["style"]))
    sid = M.style_id_map(styles)
    sel = U.load_json("outputs/q3/model_selection.json")
    clf_name = sel["classifier_selected"]
    clf = U.fit_style_classifier(Ztr, ytr, clf_name)
    classes = list(clf.classes_)

    gen = {}
    for seed in SEEDS:
        df = pd.read_csv(U.PROJECT / f"outputs/q3/seeds/generated_spectra_seed{seed}.csv")
        gen[seed] = df

    # ---------- 1) 生成样本的风格概率（供 reviewer 独立重算命中率） ----------
    prob_rows = []
    for seed in SEEDS:
        df = gen[seed]
        Zg = prep.transform(df[U.FEATURES])
        proba = clf.predict_proba(Zg)
        pred = clf.predict(Zg)
        pr = pd.DataFrame(proba, columns=[f"p_{c}" for c in classes])
        pr.insert(0, "style", df["style"].values)
        pr.insert(1, "sample_id", df["sample_id"].values)
        pr.insert(2, "seed", df["seed"].values)
        pr.insert(3, "pred_style", pred)
        pr.insert(4, "hit", (pred == df["style"].values).astype(int))
        prob_rows.append(pr)
    probs = pd.concat(prob_rows, ignore_index=True)
    U.write_csv(probs, "outputs/q3/generated_style_probs.csv")
    print(f"[1] generated_style_probs.csv rows={len(probs)}")

    # ---------- 2) 风格命中率（vs 留出真值基线） ----------
    hit = {}
    for seed in SEEDS:
        sub = probs[probs.seed == seed]
        hit[seed] = sub.groupby("style")["hit"].mean()
    style_stats = {}
    for s in styles:
        vals = [hit[seed].get(s, np.nan) for seed in SEEDS]
        style_stats[s] = {
            "n_gen_per_seed": int((gen[PRIMARY]["style"] == s).sum()),
            "hit_rate_seed42": float(hit[PRIMARY].get(s, np.nan)),
            "hit_rate_mean_over_seeds": float(np.nanmean(vals)),
            "hit_rate_sd_over_seeds": float(np.nanstd(vals, ddof=1)),
        }
    # 基线：分类器对留出真值样本的逐风格命中率
    Zte = prep.transform(U.train_matrix(tab, split["test_beer"]))
    yte = style_vec(tab, split["test_beer"])
    pred_te = clf.predict(Zte)
    base_rows = []
    for s in styles:
        m = yte == s
        n = int(m.sum())
        k = int((pred_te[m] == s).sum())
        base_rows.append({"style": s, "n_test": n, "n_hit": k,
                          "hit_rate": (k / n if n else float("nan")),
                          "wilson_ci": wilson_ci(k, n)})
    base = pd.DataFrame(base_rows).set_index("style")
    # 训练内（in-sample）参考
    pred_tr = clf.predict(Ztr)
    base_tr = {}
    for s in styles:
        m = ytr == s
        base_tr[s] = float((pred_tr[m] == s).mean()) if m.sum() else float("nan")
    for s in styles:
        style_stats[s].update({
            "baseline_holdout_hit_rate": float(base.loc[s, "hit_rate"]),
            "baseline_holdout_n": int(base.loc[s, "n_test"]),
            "baseline_holdout_wilson_ci": base.loc[s, "wilson_ci"],
            "baseline_train_in_sample_hit_rate": base_tr[s],
        })
    req_hits = [style_stats[s]["hit_rate_mean_over_seeds"] for s in U.REQUIRED_STYLES]
    req_base = [style_stats[s]["baseline_holdout_hit_rate"] for s in U.REQUIRED_STYLES]
    style_fidelity = {
        "classifier": {"selected": clf_name,
                       "cv_accuracy": sel["classifier_cv"][clf_name]["cv_accuracy_mean"],
                       "cv_macro_f1": sel["classifier_cv"][clf_name]["cv_macro_f1_mean"],
                       "chance_uniform": 1.0 / len(styles)},
        "aggregate_generated_hit_rate": float(probs[probs.seed == PRIMARY]["hit"].mean()),
        "aggregate_holdout_accuracy": float((pred_te == yte).mean()),
        "required_styles": {s: style_stats[s] for s in U.REQUIRED_STYLES},
        "required_mean_generated_hit": float(np.nanmean(req_hits)),
        "required_mean_baseline_hit": float(np.nanmean(req_base)),
        "per_style": style_stats,
        "note": "命中率 = 生成样本被判为目标风格的比例；基线 = 同一分类器对留出真值同风格样本的命中率（n 很小，Kriek/Lambic 见 n_test）。",
    }
    print(f"[2] generated hit (seed42): {style_fidelity['aggregate_generated_hit_rate']:.3f} "
          f"vs holdout acc {style_fidelity['aggregate_holdout_accuracy']:.3f}; "
          f"required mean {style_fidelity['required_mean_generated_hit']:.3f} "
          f"vs baseline {style_fidelity['required_mean_baseline_hit']:.3f}")

    # ---------- 3) 分布吻合：能量距离 / MMD（逐风格、逐 seed、两种参考） ----------
    ed_rows = []
    mmd_rows = []
    bw = {}
    for s in styles:
        Zr = Ztr[ytr == s]
        bw[s] = U.median_bandwidth(tab, prep, np.array([b for b in split["train_beer"]
                                                        if tab.set_index("beer").loc[b, "style"] == s]))
    for seed in SEEDS:
        df = gen[seed]
        for s in styles:
            Zg = prep.transform(df[df["style"] == s][U.FEATURES])
            ref_hold = np.array([b for b in split["test_beer"]
                                 if tab.set_index("beer").loc[b, "style"] == s])
            ref_all = tab.set_index("beer").loc[
                tab.set_index("beer")["style"] == s].index.values
            Zr_hold = prep.transform(U.train_matrix(tab, ref_hold)) if len(ref_hold) else np.empty((0, U.N_FEATURES))
            Zr_all = prep.transform(U.train_matrix(tab, ref_all))
            e_hold = U.energy_distance(Zg, Zr_hold) if len(ref_hold) else {"ed": np.nan, "ed2": np.nan,
                                                                         "n_gen": len(Zg), "n_ref": 0}
            e_all = U.energy_distance(Zg, Zr_all)
            ed_rows.append({
                "style": s, "seed": seed, "n_gen": len(Zg),
                "n_ref_holdout": int(len(ref_hold)),
                "ref_holdout_beers": ";".join(str(int(b)) for b in ref_hold),
                "energy_distance_holdout": e_hold["ed"],
                "energy_distance_sq_holdout": e_hold["ed2"],
                "energy_distance_all_real": e_all["ed"],
                "n_ref_all": int(len(ref_all)),
            })
            m_hold = U.mmd_rbf(Zg, Zr_hold, bandwidth_sq=bw[s]) if len(ref_hold) else {"mmd2": np.nan}
            m_all = U.mmd_rbf(Zg, Zr_all, bandwidth_sq=bw[s])
            mmd_rows.append({"style": s, "seed": seed,
                             "mmd2_holdout": m_hold["mmd2"],
                             "mmd2_all_real": m_all["mmd2"],
                             "bandwidth_sq": bw[s]})
    ed_df = pd.DataFrame(ed_rows)
    mmd_df = pd.DataFrame(mmd_rows)
    ed_df["mmd2_holdout"] = mmd_df["mmd2_holdout"].values
    ed_df["mmd2_all_real"] = mmd_df["mmd2_all_real"].values
    ed_df["rbf_bandwidth_sq"] = mmd_df["bandwidth_sq"].values
    U.write_csv(ed_df, "outputs/q3/energy_distance.csv")
    # 参考集离散度的尺度：D_ref（训练同风格两两距离中位数）便于解释 ED 大小
    dref_rows = []
    for s in styles:
        Zr = Ztr[ytr == s]
        dref_rows.append({"style": s, "d_ref_train_median_pairwise": M.d_ref_value(Zr),
                          "n_train": int(len(Zr))})
    dref = pd.DataFrame(dref_rows).set_index("style")
    dist = {
        "space": "训练集 z 空间（231 维，训练均值/标准差）",
        "definitions": {
            "energy_distance_sq": "2E||x-y|| - E||x-x'|| - E||y-y'||（V 统计量，取平方根为 ed）",
            "mmd": "有偏 RBF-MMD^2，带宽 = 训练同风格两两平方距离中位数（逐风格固定）",
            "d_ref": "训练同风格两两距离中位数，用于把 ED 相对化",
        },
        "primary_seed": PRIMARY,
        "seed42_holdout": {s: float(ed_df[(ed_df.seed == PRIMARY) & (ed_df["style"] == s)]
                                    ["energy_distance_holdout"].iloc[0]) for s in styles},
        "seed42_ratio_to_d_ref": {s: float(ed_df[(ed_df.seed == PRIMARY) & (ed_df["style"] == s)]
                                           ["energy_distance_holdout"].iloc[0] / dref.loc[s, "d_ref_train_median_pairwise"])
                                  for s in styles},
        "seed42_mmd2_holdout": {s: float(mmd_df[(mmd_df.seed == PRIMARY) & (mmd_df["style"] == s)]
                                         ["mmd2_holdout"].iloc[0]) for s in styles},
        "required_styles": {
            s: {"ed_holdout_seed42": float(ed_df[(ed_df.seed == PRIMARY) & (ed_df["style"] == s)]
                                           ["energy_distance_holdout"].iloc[0]),
                "ed_all_real_seed42": float(ed_df[(ed_df.seed == PRIMARY) & (ed_df["style"] == s)]
                                            ["energy_distance_all_real"].iloc[0]),
                "n_ref_holdout": int(ed_df[(ed_df.seed == PRIMARY) & (ed_df["style"] == s)]
                                     ["n_ref_holdout"].iloc[0]),
                "ref_beers": str(ed_df[(ed_df.seed == PRIMARY) & (ed_df["style"] == s)]
                                 ["ref_holdout_beers"].iloc[0]),
                "d_ref": float(dref.loc[s, "d_ref_train_median_pairwise"])}
            for s in U.REQUIRED_STYLES},
        "small_reference_warning": "留出真值集很小（Kriek/Lambic 在 primary split 仅 1–3 个），ED/MMD 参考侧不确定度大；另给 all_real 参考一栏。",
        "per_style_ed": ed_df.round(6).to_dict(orient="records"),
    }
    print(f"[3] ED (seed42, required): " +
          ", ".join(f"{s}={dist['required_styles'][s]['ed_holdout_seed42']:.3f}"
                    for s in U.REQUIRED_STYLES))

    # ---------- 4) 缺陷：生成谱的 OAV 越阈率（三类有阈值） ----------
    dtbl = U.defect_compound_table()
    thr3 = [c for c in dtbl if dtbl[c]["has_author_threshold"] and c != "furfural"]
    def_rows = []
    for seed in SEEDS:
        df = gen[seed]
        for s in styles:
            sub = df[df["style"] == s]
            row = {"seed": seed, "style": s, "n_gen": int(len(sub))}
            for comp in thr3:
                v = sub[comp].values.astype(float)
                oav = U.oav_features(v, dtbl[comp])
                row[f"{comp}_oav_median"] = float(np.nanmedian(oav))
                row[f"{comp}_exceed_rate"] = float(np.nanmean(oav > 1.0))
            for comp in ["X.E..2.nonenal", "X3.methyl.2.butenal",
                         "X5.methylfurfural", "furfural"]:
                v = sub[comp].values.astype(float)
                conc = U.conc_with_censoring(v, dtbl[comp])
                row[f"{comp}_conc_median"] = float(np.nanmedian(conc))
                row[f"{comp}_conc_p95"] = float(np.nanpercentile(conc, 95))
            def_rows.append(row)
    def_df = pd.DataFrame(def_rows)
    # 真值基线（训练 / 留出）
    def_base = {}
    for tag, beer in (("train", split["train_beer"]), ("holdout", split["test_beer"])):
        sub = U.train_matrix(tab, beer)
        d = {}
        for comp in thr3:
            oav = U.oav_features(sub[comp].values.astype(float), dtbl[comp])
            d[comp] = {"oav_median": float(np.nanmedian(oav)),
                       "exceed_rate": float(np.nanmean(oav > 1.0))}
        def_base[tag] = d
    # 逐风格真值缺陷基线（全部真值样本，n 大一些；留出/训练分别也保留）
    per_style_base = {}
    for s in styles:
        beer_s = tab.set_index("beer").loc[tab.set_index("beer")["style"] == s].index.values
        sub = U.train_matrix(tab, beer_s)
        rec = {"n_real": int(len(beer_s))}
        for comp in thr3:
            oav = U.oav_features(sub[comp].values.astype(float), dtbl[comp])
            rec[comp] = {"oav_median": float(np.nanmedian(oav)),
                         "exceed_rate": float(np.nanmean(oav > 1.0))}
        per_style_base[s] = rec
    defect_gen = {
        "real_baseline_per_style": per_style_base,
        "absolute_threshold_compounds": {
            c: {"threshold": dtbl[c]["threshold"], "unit": dtbl[c]["unit"],
                "scale": dtbl[c]["scale"], "censoring": dtbl[c]["censoring"]}
            for c in thr3},
        "no_threshold_compounds": ["X.E..2.nonenal", "X3.methyl.2.butenal",
                                   "X5.methylfurfural"],
        "no_threshold_note": "trans-2-nonenal 与 Stale hops 在 8.xlsx 无阈值：只报浓度分布，"
                             "不报越阈率，不采用任何外部/自造阈值",
        "real_baseline": def_base,
        "generated_seed42": {
            s: {c: {"oav_median": float(def_df[(def_df.seed == PRIMARY) & (def_df["style"] == s)]
                                        [f"{c}_oav_median"].iloc[0]),
                    "exceed_rate": float(def_df[(def_df.seed == PRIMARY) & (def_df["style"] == s)]
                                         [f"{c}_exceed_rate"].iloc[0])}
                for c in thr3}
            for s in U.REQUIRED_STYLES},
        "required_style_delta_vs_real": {
            s: {c: {"generated_exceed_rate": float(def_df[(def_df.seed == PRIMARY) & (def_df["style"] == s)]
                                                  [f"{c}_exceed_rate"].iloc[0]),
                    "real_exceed_rate": per_style_base[s][c]["exceed_rate"],
                    "delta": float(def_df[(def_df.seed == PRIMARY) & (def_df["style"] == s)]
                                   [f"{c}_exceed_rate"].iloc[0]) - per_style_base[s][c]["exceed_rate"]}
                for c in thr3}
            for s in U.REQUIRED_STYLES},
        "per_style_per_seed": def_df.round(6).to_dict(orient="records"),
    }
    print("[4] defect exceedance (seed42 required styles): " + "; ".join(
        f"{s}: " + ", ".join(f"{c.split('.')[-1]}={defect_gen['generated_seed42'][s][c]['exceed_rate']:.2f}"
                             for c in thr3)
        for s in U.REQUIRED_STYLES))

    # ---------- 5) 跨 seed 稳定性 ----------
    stab = []
    for seed in SEEDS:
        sub = probs[probs.seed == seed]
        ed_s = ed_df[ed_df.seed == seed]
        d_s = def_df[def_df.seed == seed]
        row = {"seed": seed,
               "aggregate_hit_rate": float(sub["hit"].mean())}
        for s in U.REQUIRED_STYLES:
            row[f"hit_{s}"] = float(sub[sub["style"] == s]["hit"].mean())
            row[f"ed_{s}"] = float(ed_s[ed_s["style"] == s]["energy_distance_holdout"].iloc[0])
        # 相关性/距离类指标：用全部风格均值
        row["mean_ed_all_styles"] = float(ed_s["energy_distance_holdout"].mean())
        for c in thr3:
            row[f"{c}_exceed_rate_all_styles"] = float(d_s[f"{c}_exceed_rate"].mean())
        stab.append(row)
    stab_df = pd.DataFrame(stab)
    # 修正 div 列（用生成诊断里的多样性比）
    gdiag = U.load_json("outputs/q3/generation_diagnostics.json")
    for i, seed in enumerate(SEEDS):
        for s in U.REQUIRED_STYLES:
            stab_df.loc[i, f"div_{s}"] = gdiag["per_seed"][str(seed)]["per_style"][s]["diversity_ratio_z"]
    U.write_csv(stab_df, "outputs/q3/seed_stability.csv")
    metric_cols = [c for c in stab_df.columns if c != "seed"]
    stab_summary = {}
    for c in metric_cols:
        v = stab_df[c].dropna().values.astype(float)
        if len(v) < 2:
            continue
        mean = float(np.mean(v))
        rng = float(np.max(v) - np.min(v))
        rel = rng / abs(mean) if mean != 0 else float("inf")
        stab_summary[c] = {"mean": mean, "min": float(np.min(v)), "max": float(np.max(v)),
                           "range": rng, "relative_range": rel,
                           "pass_0.05": bool(rel <= 0.05), "n_seeds": int(len(v)),
                           "tolerance": 0.05, "criterion": "relative range across seeds <= 0.05"}
    n_pass = int(sum(1 for v in stab_summary.values() if v["pass_0.05"]))
    failed = [k for k, v in stab_summary.items() if not v["pass_0.05"]]
    stab_summary["_summary"] = {
        "n_metrics": int(len(stab_summary)),
        "n_pass_relative_range_0.05": n_pass,
        "failed_metrics": failed,
        "note": "相对极差在均值接近 0 的指标上不稳定（如全风格 4VG 超阈率≈0）；"
                "同时给出绝对极差 range 供判断。命中率类指标的波动来自 200 个生成样本的二项抽样。",
        "absolute_range_key": "range",
        "relative_range_key": "relative_range",
    }
    print(f"[5] seed stability: {n_pass}/{len(stab_summary) - 1} metrics pass rel-range<=0.05; "
          f"failed={failed}")

    # ---------- 6) 小样本 bootstrap 不确定度 ----------
    tg = C.load_targets().set_index("beer")
    smalln = {"description": "Kriek(n=10)/Lambic(n=11)/Faro(n=3)：均值与协方差的 bootstrap 95% CI；"
                             "n 太小，不能声称精确刻画分布",
              "n_boot": 2000, "seed": U.SEED, "styles": {}}
    for s in U.SMALL_N_STYLES:
        beer_s = tab.set_index("beer").loc[tab.set_index("beer")["style"] == s].index.values
        Zr = prep.transform(U.train_matrix(tab, beer_s))
        Zg = prep.transform(gen[PRIMARY][gen[PRIMARY]["style"] == s][U.FEATURES])
        rec = {
            "n_real_all": int(len(beer_s)),
            "n_real_train": int(len([b for b in beer_s if b in set(split["train_beer"])])),
            "n_generated": int(len(Zg)),
            "real": {"mean_ci": None, "cov_ci": None},
            "generated": {"mean_ci": None, "cov_ci": None},
            "ed_holdout_seed42": float(ed_df[(ed_df.seed == PRIMARY) & (ed_df["style"] == s)]
                                       ["energy_distance_holdout"].iloc[0]),
            "n_ref_holdout": int(ed_df[(ed_df.seed == PRIMARY) & (ed_df["style"] == s)]
                                 ["n_ref_holdout"].iloc[0]),
        }
        for tag, Zm in (("real", Zr), ("generated", Zg)):
            if len(Zm) < 2:
                continue
            bm = U.bootstrap_mean_ci(Zm, n_boot=2000, seed=U.SEED)
            bc = U.bootstrap_cov_fro(Zm, n_boot=2000, seed=U.SEED)
            sd_real = float(np.nanmedian(np.nanstd(Zr, axis=0)))
            rec[tag] = {
                "mean_ci_width_median_z_units": bm["median_ci_width"],
                "mean_ci_width_median_over_real_sd": bm["median_ci_width"] / (sd_real + 1e-12),
                "cov_fro_ci": [bc["fro_lo"], bc["fro_hi"]],
                "cov_fro_point": bc["fro_point"],
            }
        # 生成侧均值相对真值均值的偏差（z 单位）与 CI 是否覆盖
        if len(Zr) >= 2 and len(Zg) >= 2:
            diff = np.abs(np.nanmean(Zg, axis=0) - np.nanmean(Zr, axis=0))
            rec["abs_mean_gap_median_z"] = float(np.median(diff))
            rec["abs_mean_gap_p90_z"] = float(np.percentile(diff, 90))
        smalln["styles"][s] = rec
    U.write_json(smalln, "outputs/q3/smalln_uncertainty.json")
    print(f"[6] small-n: " + ", ".join(
        f"{s} n={smalln['styles'][s]['n_real_all']} gap={smalln['styles'][s].get('abs_mean_gap_median_z', float('nan')):.3f}"
        for s in U.SMALL_N_STYLES))

    # ---------- 7) OAV 映射校验（对真值样本复算 vs data/clean/oav.csv） ----------
    oav_ref = pd.read_csv(U.PROJECT / "data" / "clean" / "oav.csv", index_col=0)
    oav_check = {}
    for comp in thr3:
        me = U.oav_features(tab.set_index("beer")[comp].values.astype(float), dtbl[comp])
        ref = oav_ref[comp].reindex(tab["beer"].values).values
        ok = np.isfinite(ref)
        d = np.abs(me[ok] - ref[ok])
        oav_check[comp] = {
            "n_compared": int(ok.sum()),
            "max_abs_diff": float(np.nanmax(d)),
            "n_rows_diff_gt_1e-6": int((d > 1e-6).sum()),
            "row_level_data_caveat": ("1.csv 与 8.xlsx Calibrated 在少数行不一致"
                                      if comp == "X2.3.butanedione" else None),
        }
    oav_check["note"] = ("映射口径 = 作者标定浓度规则（log10 列 10^v、linear 列原值）+ LOD/2 删失码还原为 0；"
                         "与 data/clean/oav.csv 对齐可验证。X2.3.butanedione 有 3 行 1.csv 与 8.xlsx 标定表"
                         "本身不一致（非本项目改动），已在绝对 OAV 上留痕。")

    # ---------- 8) 感官画像 ----------
    profiles = {}
    prof_placeholder = placeholder_profile_predictor(prep, tab, split)
    gen_primary = {s: gen[PRIMARY][gen[PRIMARY]["style"] == s][U.FEATURES].values for s in styles}
    summ_ph, _df_ph = profile_consistency_mapper(prof_placeholder, tab, split, gen_primary)
    profiles["placeholder"] = summ_ph
    # 落盘感官画像（50 ẑ + 0-6 分级）
    P_ph = prof_placeholder["predict"](np.vstack([gen_primary[s] for s in styles]))
    style_order = np.concatenate([[s] * len(gen_primary[s]) for s in styles])
    sid_order = np.concatenate([gen[PRIMARY][gen[PRIMARY]["style"] == s]["sample_id"].values
                                for s in styles])
    prof_df = pd.DataFrame(P_ph, columns=[f"z_{d}" for d in C.TARGET_DIMS])
    prof_df.insert(0, "style", style_order)
    prof_df.insert(1, "sample_id", sid_order)
    prof_df.insert(2, "seed", PRIMARY)
    prof_df.insert(3, "profile_source", prof_placeholder["source"])
    grades = np.column_stack([C.z_to_grade(P_ph[:, j]) for j in range(P_ph.shape[1])])
    gdf = pd.DataFrame(grades, columns=[f"g_{d}" for d in C.TARGET_DIMS])
    prof_df = pd.concat([prof_df.reset_index(drop=True), gdf], axis=1)
    U.write_csv(prof_df, "outputs/q3/sensory_profiles.csv")
    print(f"[8] sensory_profiles.csv rows={len(prof_df)} (profile_source=placeholder)")

    q1 = load_q1_bundle(tab, split, prep)
    if q1.get("status") == "loaded" and "predict" in q1:
        try:
            summ_q1, _df_q1 = profile_consistency_mapper(q1, tab, split, gen_primary)
            profiles["q1_model_bundle"] = {**summ_q1, "status": "loaded"}
            prof_df.to_csv(U.PROJECT / "outputs/q3/sensory_profiles_placeholder.csv", index=False)
            P1 = q1["predict"](np.vstack([gen_primary[s] for s in styles]))
            d1 = pd.DataFrame(P1, columns=[f"z_{d}" for d in C.TARGET_DIMS])
            d1.insert(0, "style", style_order)
            d1.insert(1, "sample_id", sid_order)
            d1.insert(2, "seed", PRIMARY)
            d1.insert(3, "profile_source", "q1_model_bundle")
            g1 = pd.DataFrame(np.column_stack([C.z_to_grade(P1[:, j]) for j in range(P1.shape[1])]),
                              columns=[f"g_{d}" for d in C.TARGET_DIMS])
            d1 = pd.concat([d1.reset_index(drop=True), g1], axis=1)
            U.write_csv(d1, "outputs/q3/sensory_profiles.csv")
            prof_df = d1          # 交付版画像 = Q1 bundle（同一映射器比较）
            print("[8b] sensory_profiles.csv 已切换为 profile_source=q1_model_bundle")
        except Exception as e:  # noqa: BLE001
            profiles["q1_model_bundle"] = {"status": "predict_failed", "note": f"{type(e).__name__}: {e}"}
    else:
        profiles["q1_model_bundle"] = q1

    # Q1 应急 bundle 对照块（不覆盖权威块）
    emg = load_emergency_bundle()
    if emg.get("status") == "loaded" and "predict" in emg:
        try:
            summ_e, _ = profile_consistency_mapper(emg, tab, split, gen_primary)
            profiles["lead_emergency_bundle"] = {**summ_e, "status": "loaded"}
        except Exception as e:  # noqa: BLE001
            profiles["lead_emergency_bundle"] = {"status": "predict_failed",
                                                 "note": f"{type(e).__name__}: {e}"}
    else:
        profiles["lead_emergency_bundle"] = emg

    # ---------- 9) 分层分割复算（Lead 要求两栏报告） ----------
    split_s = U.load_split("stratified")
    prep_s = U.fit_preprocessor(tab, split_s["train_beer"])
    Zs = prep_s.transform(U.train_matrix(tab, split_s["train_beer"]))
    ys = style_vec(tab, split_s["train_beer"])
    clf_s = U.fit_style_classifier(Zs, ys, clf_name)
    family = sel["selected"]["family"].split("_")[0]
    sampler_s = M.make_sampler(family, sel["selected"]["config"], Zs, ys,
                               np.array([sid[s] for s in ys]), len(styles), U.SEED)
    strat = {"split": split_s, "styles": {}}
    ed_rows_s = []
    yte_s = style_vec(tab, split_s["test_beer"])
    pred_te_s = clf_s.predict(prep_s.transform(U.train_matrix(tab, split_s["test_beer"])))
    nbs = n_by_style(styles)
    for s in styles:
        rng = np.random.default_rng(U.SEED * 100_000 + sid[s] * 17 + 3)
        Zg = M.draw(sampler_s, family, s, nbs[s], rng, sid[s])
        A = prep_s.clip(prep_s.inverse(Zg))
        Zga = prep_s.transform(pd.DataFrame(A, columns=U.FEATURES))
        pred = clf_s.predict(Zga)
        ref_hold = [b for b in split_s["test_beer"]
                    if tab.set_index("beer").loc[b, "style"] == s]
        Zr_h = prep_s.transform(U.train_matrix(tab, np.array(ref_hold))) if ref_hold else np.empty((0, U.N_FEATURES))
        e = U.energy_distance(Zga, Zr_h) if len(ref_hold) else {"ed": np.nan, "ed2": np.nan}
        ref_all = tab.set_index("beer").loc[tab.set_index("beer")["style"] == s].index.values
        Zr_all = prep_s.transform(U.train_matrix(tab, ref_all))
        e_all = U.energy_distance(Zga, Zr_all)
        # 基线命中率
        m = yte_s == s
        base_hit = float((pred_te_s[m] == s).mean()) if m.sum() else float("nan")
        strat["styles"][s] = {
            "n_train": int((ys == s).sum()), "n_test": int(m.sum()),
            "hit_rate_generated": float(np.mean(pred == s)),
            "hit_rate_baseline_holdout": base_hit,
            "ed_holdout": e["ed"], "n_ref_holdout": int(len(ref_hold)),
            "ref_holdout_beers": [int(b) for b in ref_hold],
            "ed_all_real": e_all["ed"],
        }
        ed_rows_s.append({"style": s, "seed": U.SEED,
                          "energy_distance_holdout": e["ed"],
                          "n_ref_holdout": int(len(ref_hold)),
                          "ref_holdout_beers": ";".join(str(int(b)) for b in ref_hold),
                          "energy_distance_all_real": e_all["ed"]})
    U.write_csv(pd.DataFrame(ed_rows_s), "outputs/q3/energy_distance_stratified.csv")
    strat["required_mean_hit"] = float(np.nanmean(
        [strat["styles"][s]["hit_rate_generated"] for s in U.REQUIRED_STYLES]))
    strat["required_mean_baseline_hit"] = float(np.nanmean(
        [strat["styles"][s]["hit_rate_baseline_holdout"] for s in U.REQUIRED_STYLES]))
    strat["required_mean_ed"] = float(np.nanmean(
        [strat["styles"][s]["ed_holdout"] for s in U.REQUIRED_STYLES]))
    print(f"[9] stratified recheck: hit {strat['required_mean_hit']:.3f} vs base "
          f"{strat['required_mean_baseline_hit']:.3f}")

    # ---------- 9b) 锚定消融（robustness） ----------
    print("[9b] anchoring ablation ...")
    abl = {}
    for tag, anchor in (("with_anchoring", True), ("without_anchoring", False)):
        r = M.inner_cv_family("A", {"k": int(sel["selected"]["config"]["k"]), "anchor": anchor},
                              Ztr, ytr, np.array([sid[s] for s in ytr]), len(styles),
                              clf_name, seed=U.SEED, style_ids=sid, verbose=False)
        abl[tag] = {"score": r["score"], "mean_hit_rate": r["mean_hit_rate"],
                    "mean_ed_ratio": r["mean_ed_ratio"],
                    "mean_diversity_ratio": r["mean_diversity_ratio"]}
        print(f"     {tag}: score={r['score']:.3f} hit={r['mean_hit_rate']:.3f} "
              f"ed_ratio={r['mean_ed_ratio']:.3f} div={r['mean_diversity_ratio']:.3f}")

    # ---------- 10) 迁移结果（若已跑） ----------
    tr_report = U.load_json("outputs/q3/transfer_report.json")
    defect_transfer = tr_report.get("defect_summary") if tr_report else {
        "status": "pending", "note": "q3_transfer.py 尚未运行"}

    # ---------- 11) metrics.json ----------
    metrics = {
        "question": "Q3",
        "generated_by": "src/q3_eval.py",
        "seeds": {"primary": PRIMARY, "stability": SEEDS},
        "splits": {"primary": U.split_meta(split), "stratified": U.split_meta(split_s),
                   "primary_role": "SPLIT-0001（未分层；holdout 缺 West Flanders ale）"},
        "model": {"family": sel["selected"]["family"], "config": sel["selected"]["config"],
                  "selection_criterion": sel["protocol"]["criterion"],
                  "admissibility": sel["protocol"]["admissibility"],
                  "unconstrained_best": sel["unconstrained_best"],
                  "vaes_overfitting": sel["vae_overfitting"]},
        "style_fidelity": style_fidelity,
        "distribution_match": dist,
        "defect_check_generation": defect_gen,
        "defect_check_transfer": defect_transfer,
        "sensory_profile": profiles,
        "small_n_uncertainty": smalln,
        "seed_stability": {"per_seed": stab_df.round(6).to_dict(orient="records"),
                           "summary": stab_summary},
        "stratified_split_recheck": {**strat, "split": U.split_meta(split_s)},
        "anchoring_ablation": abl,
        "oav_mapping_validation": oav_check,
        "support_and_nonnegativity": {
            "support_violation_after_clip_max":
                gdiag["per_seed"][str(PRIMARY)]["support_violation_after_clip_max"],
            "n_cells_clipped": gdiag["per_seed"][str(PRIMARY)]["n_cells_clipped"],
            "clipped_fraction": gdiag["per_seed"][str(PRIMARY)]["clipped_fraction"],
            "neg_linear_concentration_cells":
                gdiag["per_seed"][str(PRIMARY)]["neg_linear_concentration_cells"],
            "aggregates_within_train_support":
                gdiag["per_seed"][str(PRIMARY)]["aggregates_within_train_support"],
            "note": "k=15 低秩高斯的采样落在训练支撑内，裁剪未触发（非负与支撑约束不 binding，但机制在位）",
        },
        "reproduction": gdiag.get("reproduction_check"),
        "applicability": {
            "scope": "这 250 款商用啤酒的经验分布内（22 类风格）；不外推到其他酒厂/工艺/时间",
            "small_n": "Kriek(n=10)/Lambic(n=11)/Faro(n=3) 只能给区间估计，不声称精确刻画",
            "transfer": "迁移结果是反事实方案，不代表保证的干预收益",
        },
    }
    U.write_json(metrics, "outputs/q3/metrics.json")
    print("[done] metrics.json / energy_distance.csv / smalln_uncertainty.json / seed_stability.csv")

    # 把分类器评估段落追加进 style_classifier_report.json（不覆盖 CV 段）
    rep = U.load_json("outputs/q3/style_classifier_report.json")
    rep["generation_evaluation"] = {
        "generated_hit_rate_seed42": style_fidelity["aggregate_generated_hit_rate"],
        "holdout_accuracy": style_fidelity["aggregate_holdout_accuracy"],
        "required_styles": {s: {"generated_hit": style_stats[s]["hit_rate_mean_over_seeds"],
                                "baseline_holdout_hit": style_stats[s]["baseline_holdout_hit_rate"],
                                "n_test": style_stats[s]["baseline_holdout_n"]}
                            for s in U.REQUIRED_STYLES},
        "per_style": style_stats,
        "probabilities_file": "outputs/q3/generated_style_probs.csv",
        "note": "命中率可由 generated_style_probs.csv 的 pred_style 与 style 列直接重算",
    }
    U.write_json(rep, "outputs/q3/style_classifier_report.json")

    write_summary_md(metrics, tr_report)
    write_readme(metrics, tr_report)

    # ---------- 12) robustness.json ----------
    tr = tr_report or {}
    robustness = {
        "purpose": "Q3 稳健性汇总：选型、锚定消融、跨 seed、小样本、迁移目标变体、数据质量",
        "model_selection": {
            "selected": sel["selected"],
            "unconstrained_best": sel["unconstrained_best"],
            "tie_break": sel.get("tie_break"),
            "diversity_floor": sel.get("diversity_floor"),
            "candidates": [{"family": r["family"], "config": r["config"],
                            "score": r["score"], "mean_hit_rate": r["mean_hit_rate"],
                            "mean_ed_ratio": r["mean_ed_ratio"],
                            "mean_diversity_ratio": r["mean_diversity_ratio"],
                            "admissible": r.get("admissible")}
                           for r in sel["candidates"]],
            "criterion_revisions": sel["protocol"].get("criterion_revision_note"),
            "objective_revision_note": sel["protocol"].get("anchoring_note"),
        },
        "anchoring_ablation": abl,
        "seed_stability": {"summary": stab_summary,
                           "per_seed": stab_df.round(6).to_dict(orient="records")},
        "small_n": smalln["styles"],
        "transfer": {
            "feasibility": tr.get("feasibility"),
            "objective_variants": tr.get("objective_variants"),
            "style_progress": tr.get("style_progress"),
            "defect_summary": tr.get("defect_summary"),
        } if tr else {"status": "pending"},
        "data_quality_flags": {
            "oav_mapping_validation": oav_check,
            "diacetyl_row_inconsistency": "1.csv 与 8.xlsx Calibrated 在 X2.3.butanedione 上"
                                          "有 3 行实质性不一致（OAV 差 >1e-6，最大约 1.04），"
                                          "属原始数据不一致，非本项目改动。",
            "holdout_note": "primary split 未分层，test 缺 West Flanders ale；"
                            "Kriek/Lambic 留出真值仅 1–3 个样本",
        },
        "applicability": metrics["applicability"],
    }
    U.write_json(robustness, "outputs/q3/robustness.json")

    # 泄漏清单补充：占位画像用了 4.csv（只做前向映射，不进生成模型）
    man = U.load_json("outputs/q3/leakage_manifest.json")
    man["sensory_profile_mapping"] = {
        "placeholder": prof_placeholder["meta"],
        "q1_bundle": {k: v for k, v in profiles["q1_model_bundle"].items()
                      if k in ("status", "note")},
        "rule": "4.csv 只在占位前向映射里作为回归目标出现；生成模型训练集仍是 1.csv 的 231 列 + 风格列",
    }
    U.write_json(man, "outputs/q3/leakage_manifest.json")

    # ---------- 13) 机读指标行（供台账/独立复算抓取） ----------
    import json as _json
    _dref_tripel = dist["required_styles"]["Tripel"].get("d_ref")
    _pred_df, _r2_profile = profile_prediction_frame(prof_df, tg, split,
                                                     U.REQUIRED_STYLES)
    _q1_ok = ("profile_source" in profiles.get("q1_model_bundle", {})
              and profiles["q1_model_bundle"].get("status") == "loaded")
    _prof_for_metric = (profiles["q1_model_bundle"] if _q1_ok
                        else profiles["placeholder"])
    _r2_50dim = _prof_for_metric["required_styles_mean"]["spearman"]
    flat = {
        "r2": _r2_profile,
        "r2_50dim": _r2_50dim,
        "ed_over_dref_tripel": (dist["required_styles"]["Tripel"]["ed_holdout_seed42"] /
                                _dref_tripel) if _dref_tripel else None,
        "style_hit_macro": style_fidelity["aggregate_generated_hit_rate"],
        "style_hit_tripel": style_fidelity["required_styles"]["Tripel"]["hit_rate_mean_over_seeds"],
        "defect_violation_rate": ((tr_report or {}).get("feasibility", {})
                                  .get("total_defect_violation_cells")),
        "transfer_feasible_rate": (tr_report or {}).get("feasibility", {})
        .get("fraction_hard_feasible"),
        "transfer_tripel_hit_rate": (tr_report or {}).get("style_progress", {})
        .get("classifier_hit_as_tripel_after"),
        "gen_style_fidelity": style_fidelity["aggregate_generated_hit_rate"],
        "gen_style_fidelity_required_mean": style_fidelity["required_mean_generated_hit"],
        "holdout_style_accuracy": style_fidelity["aggregate_holdout_accuracy"],
        "energy_distance_tripel": dist["required_styles"]["Tripel"]["ed_holdout_seed42"],
        "energy_distance_kriek": dist["required_styles"]["Kriek"]["ed_holdout_seed42"],
        "energy_distance_lambic": dist["required_styles"]["Lambic"]["ed_holdout_seed42"],
        "energy_distance_ratio_mean": sel["selected"]["mean_ed_ratio"],
        "diversity_ratio_mean": sel["selected"]["mean_diversity_ratio"],
        "profile_spearman_delivered": _prof_for_metric["required_styles_mean"]["spearman"],
        "profile_spearman_placeholder": profiles["placeholder"]["required_styles_mean"]["spearman"],
        "defect_transfer_feasible_fraction": (tr_report or {}).get("feasibility", {})
        .get("fraction_hard_feasible"),
        "defect_transfer_all_satisfied": (tr_report or {}).get("feasibility", {})
        .get("all_samples_satisfy_hard_constraints"),
        "n_features": int(U.N_FEATURES),
        "stochastic": True,
        "seed": int(PRIMARY),
    }
    flat = {k: v for k, v in flat.items() if v is not None}
    print("METRICS_JSON " + _json.dumps(flat, ensure_ascii=False))
    if E is not None and E.IN_RUNNER:
        E.emit_metrics(flat, area="q3")
        E.emit_output("style_fidelity_per_style",
                      U.clean_json(style_fidelity["per_style"]), area="q3")
        E.emit_output("defect_generation", U.clean_json({
            "required_style_delta_vs_real": defect_gen["required_style_delta_vs_real"],
            "real_baseline_per_style": defect_gen["real_baseline_per_style"],
        }), area="q3")
        E.emit_output("energy_distance_table",
                      U.clean_json(dist["per_style_ed"]), area="q3")
        E.emit_output("sensory_profile_placeholder",
                      U.clean_json(profiles["placeholder"]["required_styles_mean"]), area="q3")
        E.emit_output("stratified_split_recheck", {
            "required_mean_hit": strat["required_mean_hit"],
            "required_mean_baseline_hit": strat["required_mean_baseline_hit"],
            "required_mean_ed": strat["required_mean_ed"],
        }, area="q3")
        E.emit_predictions(_pred_df[["row", "y_true", "y_pred"]], "predictions.csv", area="q3")
        E.emit_output("generated_spectra",
                      U.clean_json(gen[PRIMARY].head(50).to_dict(orient="records")), area="q3")


if __name__ == "__main__":
    main()
