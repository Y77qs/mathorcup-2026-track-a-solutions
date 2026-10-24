"""Q1 独立复算（训练内部 OOF，不触碰 holdout）。

背景：pack 的 independent-rerun 需要"新的冻结实验"，而 contest.yaml 的 holdout 复用预算已被
B0/C1/C2/Q2 四次使用占满；再次用 holdout 复跑会被
`VMU_PACK_MODELING_CONTEST_HOLDOUT_REUSE_UNCONTROLLED` 拒绝。
因此这里做**不暴露 holdout 的独立复算**：新进程、只读训练行、重跑 Ridge(alpha=1000) 的 5 折 OOF，
与 EXP-0002 记录的 oof_mae_mean 逐值比较。holdout 估计本身不因此获得第二次审计，如实披露。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L  # noqa: E402
import q1_common as Q  # noqa: E402
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold


def main() -> int:
    D = Q.load()
    tr, feats, targets = D["train"], D["features"], D["targets"]
    X = tr[feats].to_numpy(float)
    Y = tr[targets].to_numpy(float)
    kf = KFold(n_splits=5, shuffle=True, random_state=20261024)
    P = np.zeros_like(Y)
    for ia, ib in kf.split(X):
        pp = Q.fit_preprocess(X[ia])
        m = Ridge(alpha=1000.0)
        m.fit(Q.transform(X[ia], pp), Y[ia])
        P[ib, :] = m.predict(Q.transform(X[ib], pp))
    oof_mae = float(np.nanmean(Q.mae_per_target(Y, P)))

    ref = json.loads((L.ROOT / "experiments" / "EXP-0002" / "metrics.json").read_text(encoding="utf-8"))
    ref_mae = float(ref["oof_mae_mean"])
    delta = abs(oof_mae - ref_mae)
    rel = delta / max(abs(ref_mae), 1e-12)
    out = {
        "kind": "independent-reproduction-training-only",
        "experimentId": "EXP-0002",
        "metric": "oof_mae_mean",
        "recomputed": oof_mae,
        "recorded": ref_mae,
        "absoluteDelta": delta,
        "relativeDelta": rel,
        "tolerance": {"absolute": 1e-9, "relative": 1e-6},
        "passed": bool(delta <= 1e-9 or rel <= 1e-6),
        "holdoutTouched": False,
        "packIndependentRerun": {
            "attempted": True,
            "blockedBy": "VMU_PACK_MODELING_CONTEST_HOLDOUT_REUSE_UNCONTROLLED",
            "reason": "holdout 复用预算（contest.yaml quality.robustness.maxHoldoutReuse，初始 3）已被 "
                      "EXP-0001/0002/0003/0004 四次暴露占满；pack 拒绝再暴露。",
            "consequence": "holdout 点估计没有获得第二次独立审计；本文只用训练内部 OOF 验证可复现性，"
                           "并在限制中披露。",
        },
        "note": "同 seed、同数据、同代码哈希；训练行 200 条，5 折 seed=20261024",
    }
    p = L.OUT / "q1" / "independent_reproduction.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ["recomputed", "recorded", "absoluteDelta", "passed"]},
                     ensure_ascii=False, indent=2))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
