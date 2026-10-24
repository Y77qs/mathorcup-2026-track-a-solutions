"""Q3 简单基线：无条件全局高斯（不看风格）+ 原样不迁移。

对照：EXP-0008 的"风格条件高斯 + few-shot 原型迁移 + 缺陷约束投影"。
基线只回答一个问题：按风格条件化与迁移本身带来了多少改进？
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L  # noqa: E402
import emit as E  # noqa: E402

SEED = 20261024
HOLDOUT = ["Tripel", "Kriek", "Lambic"]
SOURCE = "Pils/Lager"


def energy_distance(A, B):
    if len(A) == 0 or len(B) == 0:
        return float("nan")
    v = 2 * cdist(A, B).mean() - cdist(A, A).mean() - cdist(B, B).mean()
    return float(np.sqrt(max(v, 0.0)))


def main() -> int:
    p = os.environ.get("MODELING_DATA_FILE")
    df = pd.read_csv(p) if p else pd.read_csv(L.CLEAN / "q3.csv")
    t50 = L.target_columns()
    feats = [c for c in df.columns if c not in L.KEEP and c not in t50
             and not c.startswith("threshold") and c not in ("style_holdout", "split_role")]
    styles = df["tasting_category_fine"].astype(str)
    seen = [s for s in sorted(styles.unique()) if s not in HOLDOUT]
    X = df[feats].to_numpy(float)
    med = np.nanmedian(X[styles.isin(seen)], axis=0)
    X = np.where(np.isfinite(X), X, med[None, :])
    mu, sd = X[styles.isin(seen)].mean(0), X[styles.isin(seen)].std(0)
    sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / sd
    rng = np.random.default_rng(SEED)

    # 无条件全局高斯（不看风格）
    C = np.diag(np.diag(np.cov(Z[styles.isin(seen)], rowvar=False))) + 1e-6 * np.eye(len(feats))
    G = rng.multivariate_normal(Z[styles.isin(seen)].mean(0), C, size=60, method="eigh")

    src = Z[np.where(styles.to_numpy() == SOURCE)[0]]
    rep = {}
    for s in HOLDOUT:
        rows = Z[np.where(styles.to_numpy() == s)[0]]
        rep[s] = {
            "energy_global_generated_vs_style": energy_distance(G, rows),
            "energy_source_identity_vs_style": energy_distance(src, rows),
            "n_style": int(len(rows)),
        }
    m = {
        "baseline_kind": "unconditional-global-gaussian + identity (no style conditioning, no transfer)",
        "constraint_satisfaction": 1.0,
        "energy_holdout_generated_mean": float(np.mean([v["energy_global_generated_vs_style"] for v in rep.values()])),
        "energy_holdout_source_baseline_mean": float(np.mean([v["energy_source_identity_vs_style"] for v in rep.values()])),
        "n_holdout_styles": len(HOLDOUT), "n_features": len(feats),
        "perStyle": rep,
        "note": "基线不含风格条件与迁移；缺陷列不动，因此不恶化率为 1.0（平凡满足）",
        "metricKey": "constraint-satisfaction",
        "targetContractId": "TGT-0003",
    }
    E.output("baseline_per_style", rep)
    E.metrics(m)
    print(json.dumps({k: m[k] for k in ["energy_holdout_generated_mean",
                                        "energy_holdout_source_baseline_mean", "n_holdout_styles"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
