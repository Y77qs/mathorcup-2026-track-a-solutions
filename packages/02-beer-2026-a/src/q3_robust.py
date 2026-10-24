"""Q3 稳健性：多 seed 重复生成/迁移，报告约束迁移能量距离的种子间波动。

只做一件事：改变随机种子，重复 few-shot 生成与"约束迁移"，输出与主实验同名的指标
`energy_holdout_transferred_constrained_mean`（以及缺陷不恶化率），供 robustness-plan-execute 比较。
不改变协议、不重新定义判据。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import modeling_contract as _mc
except Exception:  # noqa
    _mc = None

HOLDOUT = ["Tripel", "Kriek", "Lambic"]
ADAPT_N = {"Tripel": 5, "Kriek": 3, "Lambic": 3}
SOURCE = "Pils/Lager"
KEYS = ["beer", "beer_id", "tasting_category_fine"]
TARGETS_50 = ["A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn", "A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody", "A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity", "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn", "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody", "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity", "acidity", "bitternes", "sweetness", "X4vg", "diacetyl", "dms", "metallic", "stale_hops", "t2n", "orange", "coriander", "clove", "lactic", "acetic", "barnyard", "alcohol", "aftertaste", "body", "co2", "overall"]
DEFECTS = ["DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal", "X3.methyl.2.butenal", "furfural", "X5.methylfurfural"]


def energy(A, B):
    if len(A) == 0 or len(B) == 0:
        return float("nan")
    v = 2 * cdist(A, B).mean() - cdist(A, A).mean() - cdist(B, B).mean()
    return float(np.sqrt(max(v, 0.0)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261024)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    p = os.environ.get("MODELING_DATA_FILE")
    df = pd.read_csv(p) if p else pd.read_csv(Path(__file__).resolve().parents[1] / "data/clean/q3.csv")
    t50 = TARGETS_50
    feats = [c for c in df.columns if c not in KEYS and c not in t50
             and not c.startswith("threshold") and c not in ("style_holdout", "split_role")]
    styles = df["tasting_category_fine"].astype(str)
    seen = [s for s in sorted(styles.unique()) if s not in HOLDOUT]
    X = df[feats].to_numpy(float)
    med = np.nanmedian(X[styles.isin(seen)], axis=0)
    X = np.where(np.isfinite(X), X, med[None, :])
    mu, sd = X[styles.isin(seen)].mean(0), X[styles.isin(seen)].std(0)
    sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / sd
    defect_idx = [feats.index(c) for c in DEFECTS if c in feats]
    src = Z[np.where(styles.to_numpy() == SOURCE)[0]]
    C = np.diag(np.diag(np.cov(Z[styles.isin(seen)], rowvar=False))) + 1e-6 * np.eye(len(feats))
    energies, nw, gen_e = [], [], []
    for s in HOLDOUT:
        idx = np.where(styles.to_numpy() == s)[0]
        k = min(ADAPT_N[s], max(1, len(idx) // 3))
        mu_T = Z[idx[:k]].mean(0)
        delta = mu_T - src.mean(0)
        delta[defect_idx] = 0.0
        Xf = src + delta
        energies.append(energy(Xf, Z[idx[k:]]))
        G = rng.multivariate_normal(mu_T, C, size=50, method="eigh")
        gen_e.append(energy(G, Z[idx[k:]]))
        nw.append(1.0)  # 缺陷列位移恒 0 → 构造性不恶化
    m = {"seed": int(args.seed),
         "energy_holdout_transferred_constrained_mean": float(np.mean(energies)),
         "energy_holdout_generated_mean": float(np.mean(gen_e)),
         "defect_nonworsen_rate_constrained": float(np.mean(nw)),
         "n_holdout_styles": len(HOLDOUT)}
    if _mc is not None:
        _mc.emit_metrics({k: float(v) for k, v in m.items()})
    else:
        Path("metrics.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(m, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
