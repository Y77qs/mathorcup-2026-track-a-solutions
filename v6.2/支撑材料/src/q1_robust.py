# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q1_robust.py — Q1 robustness probe: train-only 5-fold CV MAE of the graph low-rank model.

Reads ONLY the 200 rows of the registered dependency data/splits/SPLIT-0001/train.csv (one and the same
assignment as SPLIT-0002, so this is the Q1 train fold) and fits nothing on any test rows.  It exists for the
Phase-6 perturbation runs: the declared seed changes the fold assignment and --alpha-multiplier multiplies the
ridge penalty lambda, while the remaining hyper-parameters stay at the Q1 candidate's selected configuration
(defaults below can be overridden from the command line as well).

Contract: emit_metrics({"mae": CV MAE, "cv_mae_sd": fold sd, "seed_used": seed, ...}); the seed receipt is
written by seed() at the very top.
"""

import pandas as pd

from modeling_contract import emit_metrics
from q_common import run_seed, report, option, option_float, option_int, dependency_path

import q1_lib as L

TRAIN_DEPENDENCY = "data/splits/SPLIT-0001/train.csv"
N_FOLDS = 5


def main() -> int:
    receipt_seed = run_seed()  # seed() -> seed-receipt.json (requireSeedReceipt)
    seed = int(option_int("seed", receipt_seed))
    alpha_multiplier = float(option_float("alpha-multiplier", 1.0))
    base_lambda = float(option_float("lambda", 1.0))
    representation = str(option("representation", "rankgauss"))
    rank = int(option_int("rank", 10))
    gamma = float(option_float("gamma", 1.0))
    lam = base_lambda * alpha_multiplier
    if lam <= 0.0:
        raise SystemExit("the perturbed lambda must stay positive (got %r)" % (lam,))

    frame = pd.read_csv(dependency_path(TRAIN_DEPENDENCY)).reset_index(drop=True)
    if len(frame) != 200:
        raise SystemExit("expected 200 train rows, got %d" % (len(frame),))
    targets = L.check_targets(frame)
    if len(targets) != L.N_TARGETS:
        raise SystemExit("the dependency does not carry the 50 Q1 targets")

    folds = L.fold_indices(len(frame), N_FOLDS, seed, salt=13)
    blocks = L.build_blocks(frame, folds, representation)
    scoring = L.cv_mae_for(blocks, rank, lam, gamma, "lowrank")

    report("settings", {
        "model": "graph-regularised low-rank multi-output regression (train-only 5-fold CV)",
        "dataSource": TRAIN_DEPENDENCY,
        "nRows": int(len(frame)),
        "seedUsed": int(seed), "receiptSeed": int(receipt_seed),
        "representation": representation, "rank": int(rank),
        "baseLambda": base_lambda, "alphaMultiplier": alpha_multiplier, "lambda": float(lam),
        "gamma": float(gamma), "nFolds": N_FOLDS, "nIter": L.N_ITER, "tau": float(L.TAU),
        "foldSizes": [int(len(fold)) for fold in folds],
    })
    report("fold_mae", [float(value) for value in scoring["fold_maes"]])
    emit_metrics({
        "mae": float(scoring["mean"]),
        "cv_mae_sd": float(scoring["sd"]),
        "seed_used": int(seed),
        "alpha_multiplier": float(alpha_multiplier),
        "lambda": float(lam),
        "rank": int(rank),
        "gamma": float(gamma),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
