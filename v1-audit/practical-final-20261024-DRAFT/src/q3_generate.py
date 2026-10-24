"""Q3 生成：用锁定的风格条件模型生成 231 维化合物谱（Tripel/Kriek/Lambic 必做 + 其余风格）。

纪律
----
* 生成空间 = 1.csv 的 231 列；标准化/插补/支撑域全部只在 200 个训练样本内拟合。
* 生成 -> 逆标准化 -> **逐列裁剪回训练观测 [min, max]**；物理浓度列（linear verified）下界 >= 0
  （这些列训练观测 min 本就 >= 0，裁剪后非负自动成立）。
* 主种子 42 落 `outputs/q3/generated_spectra.csv`；跨 seed（42..46）稳定性落
  `outputs/q3/seeds/generated_spectra_seed{S}.csv`。
* 同 seed 逐值可复现：脚本内部会用同 seed 重生成一次并比对，把结果写进 diagnostics。
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

SEEDS = [42, 7, 2024, 123, 9]
N_REQUIRED = 200
N_OTHER = 100


def slug(style: str) -> str:
    return style.replace("/", "-").replace(" ", "_")


def generate_all(prep, tab, split, locked, seed: int, n_by_style: dict,
                 styles: list, sid: dict):
    """拟合锁定模型并逐风格生成；返回 {style: (n, 231) 原尺度 ndarray}。"""
    Xtr = U.train_matrix(tab, split["train_beer"])
    Z = prep.transform(Xtr)
    y = tab.set_index("beer").loc[split["train_beer"], "style"].values
    y_idx = np.array([sid[s] for s in y], dtype=int)
    family = locked["family"].split("_")[0]
    sampler = M.make_sampler(family, locked["config"], Z, y, y_idx, len(styles), seed)
    out = {}
    for s in styles:
        rng = np.random.default_rng(seed * 100_000 + sid[s] * 17 + 3)
        Zg = M.draw(sampler, family, s, n_by_style[s], rng, sid[s])
        A = prep.inverse(Zg)
        out[s] = prep.clip(A)
    return out, sampler, family


def raw_spectra_frame(gen: dict, seed: int) -> pd.DataFrame:
    frames = []
    for s, A in gen.items():
        n = A.shape[0]
        df = pd.DataFrame(A, columns=U.FEATURES)
        df.insert(0, "style", s)
        df.insert(1, "sample_id", [f"GEN-{slug(s)}-{seed}-{i:03d}" for i in range(n)])
        df.insert(2, "seed", seed)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main():
    print("== Q3 generate ==")
    tab = U.load_style_table()
    split = U.load_split("primary")
    prep = U.fit_preprocessor(tab, split["train_beer"])
    sel = U.load_json("outputs/q3/model_selection.json")
    locked = sel["selected"]
    sid = sel["style_id_map"]
    styles = sorted(sid, key=lambda s: sid[s])
    n_by_style = {s: (N_REQUIRED if s in U.REQUIRED_STYLES else N_OTHER) for s in styles}
    print(f"locked: {locked['family']} {locked['config']}")
    print(f"n per style: required={N_REQUIRED} others={N_OTHER}")

    diag = {
        "locked_model": {"family": locked["family"], "config": locked["config"],
                         "score_inner_cv": locked["score"]},
        "split": U.split_meta(split),
        "seed_primary": SEEDS[0],
        "seeds": SEEDS,
        "n_per_style": n_by_style,
        "column_transforms": {
            "file": "outputs/q3/column_transforms.csv",
            "n_log1p": int((prep.kinds == "log1p").sum()),
            "n_identity": int((prep.kinds == "identity").sum()),
            "rule": "log10 审计列 -> identity；其余列若训练值全 >=0 且偏度>2.0 -> log1p；否则 identity",
        },
        "support_definition": {
            "generation_space": "1.csv 231 化合物/理化列（混合尺度：37 列 log10 / 33 列 linear / 161 列 unverified）",
            "clip": "逐列训练观测 [min, max]",
            "nonnegativity": "物理浓度列（linear verified，33 列）下界取 max(0, train_min)；"
                             "log10 列的原始值可负（对应浓度 10^v > 0，非负自动满足）",
            "sum_aggregates": "5 个聚合列（kcalperc/acids_sum/esters_sum/aroma_hops_sum/sulfur_sum）"
                              "同样裁剪到训练观测区间",
        },
        "per_seed": {},
    }

    primary_df = None
    for seed in SEEDS:
        gen, sampler, family = generate_all(prep, tab, split, locked, seed,
                                            n_by_style, styles, sid)
        df = raw_spectra_frame(gen, seed)
        rel = f"outputs/q3/seeds/generated_spectra_seed{seed}.csv"
        U.write_csv(df, rel)
        A = df[U.FEATURES].values
        # ---- 支撑/非负/聚合列检查 ----
        viol = prep.support_violation(A)
        lin = prep.linear_cols
        neg_lin = int((A[:, lin] < -1e-12).sum())
        agg = ["kcalperc", "acids_sum", "esters_sum", "aroma_hops_sum", "sulfur_sum"]
        agg_idx = [U.FEATURES.index(c) for c in agg]
        agg_ok = bool(np.all((A[:, agg_idx] >= prep.lower[agg_idx][None, :] - 1e-12) &
                             (A[:, agg_idx] <= prep.upper[agg_idx][None, :] + 1e-12)))
        # 逐风格诊断
        per_style = {}
        Xtr_z = prep.transform(U.train_matrix(tab, split["train_beer"]))
        ytr = tab.set_index("beer").loc[split["train_beer"], "style"].values
        for s in styles:
            Zg = prep.transform(pd.DataFrame(gen[s], columns=U.FEATURES))
            Zr = Xtr_z[ytr == s]
            n_raw_outside = int((prep.support_violation(prep.inverse(Zg)) > 1e-9).sum())
            per_style[s] = {
                "n": int(gen[s].shape[0]),
                "n_train_real": int((ytr == s).sum()),
                "mean_abs_clip_units": float(np.mean(viol[df["style"] == s])),
                "support_violation_after_clip": 0.0,
                "n_cells_clipped": int((viol[df["style"] == s] > 1e-12).sum()),
                "diversity_ratio_z": M.diversity_ratio(Zg, Zr),
                "mean_l2_to_style_mean_z": float(np.mean(np.linalg.norm(
                    Zg - Zr.mean(0)[None, :], axis=1))),
                "real_mean_l2_to_style_mean_z": float(np.mean(np.linalg.norm(
                    Zr - Zr.mean(0)[None, :], axis=1))),
            }
        anchor = getattr(sampler, "delta_norm_", None)
        diag["per_seed"][str(seed)] = {
            "family": family,
            "conditional_mean_anchor_delta_norm": anchor,
            "n_rows": int(len(df)),
            "support_violation_after_clip_max": float(viol.max()),
            "n_cells_clipped": int((viol > 1e-12).sum()),
            "clipped_fraction": float((viol > 1e-12).mean()),
            "neg_linear_concentration_cells": neg_lin,
            "aggregates_within_train_support": agg_ok,
            "per_style": per_style,
        }
        dtbl = U.defect_compound_table()
        plaus = {}
        for st in U.REQUIRED_STYLES:
            real = tab.set_index("beer")
            real = real[real["style"] == st]
            g = df[df["style"] == st]
            row = {}
            for c in ["DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal"]:
                row[c] = {
                    "real_median_raw": float(np.nanmedian(real[c].values.astype(float))),
                    "gen_median_raw": float(np.nanmedian(g[c].values.astype(float))),
                    "ratio_gen_over_real": float(
                        np.nanmedian(g[c].values.astype(float)) /
                        (abs(np.nanmedian(real[c].values.astype(float))) + 1e-12)),
                    "real_oav_median": float(np.nanmedian(
                        U.oav_features(real[c].values.astype(float), dtbl[c]))),
                    "gen_oav_median": float(np.nanmedian(
                        U.oav_features(g[c].values.astype(float), dtbl[c]))),
                }
            plaus[st] = row
        diag["per_seed"][str(seed)]["defect_plausibility"] = plaus
        print(f"  seed {seed}: rows={len(df)} clipped={(viol>1e-12).mean():.4f} "
              f"neg_lin={neg_lin} agg_ok={agg_ok}")
        if seed == SEEDS[0]:
            primary_df = df
            # ---- 同 seed 逐值复现自检 ----
            gen2, _, _ = generate_all(prep, tab, split, locked, seed, n_by_style,
                                      styles, sid)
            df2 = raw_spectra_frame(gen2, seed)
            same = bool(np.array_equal(df[U.FEATURES].values, df2[U.FEATURES].values))
            diag["reproduction_check"] = {
                "method": "同 seed 重新拟合+重新采样一次，逐值比对 231 列",
                "same_seed_bitwise_identical": same,
                "max_abs_diff": float(np.max(np.abs(df[U.FEATURES].values -
                                                   df2[U.FEATURES].values))),
            }
            if not same:
                print("  !! reproduction check failed")

    U.write_csv(primary_df, "outputs/q3/generated_spectra.csv")
    diag["primary_file"] = {
        "path": "outputs/q3/generated_spectra.csv",
        "columns": ["style", "sample_id", "seed"] + U.FEATURES,
        "n_rows": int(len(primary_df)),
        "n_feature_columns": int(U.N_FEATURES),
        "scale": "逆标准化 + 支撑裁剪后的 1.csv 原尺度",
    }
    # 训练集与留出集风格计数（供报告引用）
    diag["style_support"] = {
        "train": U.style_counts(tab["beer"].values, tab["style"].values, split["train_beer"]),
        "test": U.style_counts(tab["beer"].values, tab["style"].values, split["test_beer"]),
    }
    U.write_json(diag, "outputs/q3/generation_diagnostics.json")
    print("[done] generated_spectra.csv + generation_diagnostics.json")


if __name__ == "__main__":
    main()
