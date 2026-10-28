# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q2_robust.py — Q2 robustness probe: the Q2 candidate main flow with a perturbed seed / tau.

Reads ONLY the 200 rows of the registered dependency data/splits/SPLIT-0001/train.csv (no split).  It runs the
same four-method / Top-3-Jaccard flow as ``q2_topk.py`` (three ingredient scores, consensus percentile ranking,
style-stratified bootstrap with pi-first delivery) but with:

  * ``--seed``              the registered seed by default; changes the bootstrap resamples;
  * ``--tau``               the graph threshold (default 0.5);
  * ``--bootstrap-reps``    the bootstrap size, default 50 for the Phase-6 perturbation runs (only the stability
                            output and the pi ordering depend on it, never the ``topk-jaccard`` definition).

The delivered sets (and therefore ``topk-jaccard``) are the point-estimate four-method Top-3 - exactly the
definitions used by ``q2_topk.py`` and by the baseline - so the perturbation runs are directly comparable with
the candidate and do not depend on the bootstrap size.  The bootstrap still runs (50 resamples by default) and
its aggregated pi-first Jaccard is stored separately as ``topk-jaccard-bootstrap-mean``.
"""

import json

import numpy as np
import pandas as pd

from modeling_contract import emit_metrics
from q_common import run_seed, report, option_int, option_float, dependency_path

import q2_lib as Q
from target_columns import TARGET_COLS


def main() -> int:
    receipt_seed = run_seed()  # seed() -> seed-receipt.json (requireSeedReceipt)
    seed = int(option_int("seed", receipt_seed))
    tau = float(option_float("tau", Q.TAU))
    reps = int(option_int("bootstrap-reps", 50))
    if reps < 1:
        raise SystemExit("bootstrap reps must be >= 1")

    frame = pd.read_csv(dependency_path(Q.SPLIT_TRAIN_DEPENDENCY)).reset_index(drop=True)
    if len(frame) != 200:
        raise SystemExit("expected 200 train rows, got %d" % (len(frame),))
    missing = [c for c in TARGET_COLS if c not in frame.columns]
    if missing:
        raise SystemExit("sensory targets missing from the dependency: %s" % missing[:3])

    scores = Q.ingredient_scores(frame, tau=tau)
    ranked = Q.percentile_block(scores)
    counts = Q.bootstrap_counts(frame, seed, reps, tau=tau)
    pi = Q.frequencies(counts, reps)
    sets_point = Q.topk_from_scores(ranked)
    sets_pi = Q.topk_from_pi(pi, ranked)

    pairs = Q.pairwise_jaccard(sets_point)
    summary = Q.jaccard_summary(pairs)
    pi_pairs = Q.pairwise_jaccard(sets_pi)
    pi_summary = Q.jaccard_summary(pi_pairs)
    point_vs_bootstrap = {method: {
        "meanJaccard": float(np.mean([Q.jaccard(sets_point[method][d], sets_pi[method][d])
                                      for d in range(len(TARGET_COLS))])),
        "changedDimensions": int(sum(1 for d in range(len(TARGET_COLS))
                                     if set(sets_point[method][d]) != set(sets_pi[method][d])))}
        for method in Q.METHODS}
    selected_pi = [pi["consensus"][position, dimension]
                   for dimension in range(len(TARGET_COLS))
                   for position in sets_point["consensus"][dimension]]

    with open("sets.json", "w", encoding="utf-8") as handle:
        json.dump(Q.sets_payload(sets_point), handle, ensure_ascii=False, indent=1)

    report("settings", {
        "model": "Q2 candidate main flow (consensus of total / within-style / graph low-rank)",
        "dataSource": Q.SPLIT_TRAIN_DEPENDENCY, "nRows": int(len(frame)),
        "seedUsed": int(seed), "receiptSeed": int(receipt_seed),
        "tau": float(tau), "bootstrapReps": int(reps), "k": Q.K,
        "graph": {"representation": "zscore", "rank": Q.GRAPH_SETTINGS["rank"],
                  "lambda": Q.GRAPH_SETTINGS["lambda"], "gamma": Q.GRAPH_SETTINGS["gamma"],
                  "nIter": 25, "tau": float(tau)},
        "delivery": "sets.json uses the point-estimate Top-3 per method (consensus = Top-3 by S); the pi-first ordering is reported in q2_topk.py and is not part of the delivered sets",
        "graphEdges": int(scores["graph"]["edges"]),
        "graphComponents": int(scores["graph"]["components"]["count"]),
    })
    report("method_jaccard", {"pairs": pairs, "summary": summary,
                              "bootstrapPiFirst": {"pairs": pi_pairs, "summary": pi_summary},
                              "deliveredSets": "point estimates (sets.json)",
                              "definition": "J = |A n B| / (2k - |A n B|), k = 3; mean over 50 dimensions and the 6 method pairs"})
    report("point_vs_bootstrap", point_vs_bootstrap)
    report("sets_path", "sets.json")
    emit_metrics({
        "topk-jaccard": float(summary["overall"]),
        "topk-jaccard-bootstrap-mean": float(pi_summary["overall"]),
        "tau": float(tau),
        "seed_used": int(seed),
        "bootstrap_reps": int(reps),
        "mean_selected_pi": float(np.mean(selected_pi)),
        "n_dimensions": int(len(TARGET_COLS)),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
