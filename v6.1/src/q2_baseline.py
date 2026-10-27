"""q2_baseline.py — Q2 baseline: one GLOBAL Top-3 per scoring method, shared by all 50 dimensions.

The baseline deliberately ignores the dimension: for each of the four methods it ranks the 219 single-compound
candidates by a score averaged over the 50 sensory dimensions and keeps the same three compounds for every
dimension (total Spearman, within-style Spearman, graph low-rank |B|, and their percentile-rank consensus).
This makes the reference point for the Q2 question explicit: a dimension-blind Top-3.

The metric is nevertheless the registered ``topk-jaccard``: mean over the 50 dimensions and the 6 method pairs of
the plugin Jaccard J = |A n B| / (2k - |A n B|), k = 3.  Because the sets are dimension-independent, every
dimension contributes the same value; sets.json still carries all 200 (dimension, method) rows.
"""

import json

import numpy as np
import pandas as pd

from modeling_contract import emit_metrics
from q_common import run_seed, report, dataset_path

import q2_lib as Q
from target_columns import TARGET_COLS


def main() -> int:
    seed = run_seed()
    frame = Q.load_train_frame()
    dataset = pd.read_csv(dataset_path())
    coverage = {"nDatasetRows": int(len(dataset)), "nTrainRows": int(len(frame)),
                "trainRowsFoundInDataset": int(frame["row"].isin(dataset["row"]).sum())}

    scores = Q.ingredient_scores(frame)
    ranked = Q.percentile_block(scores)
    n_candidates = len(Q.CANDIDATE_NAMES)
    index = np.arange(n_candidates)

    # ------------------------------------------------------------------ dimension-blind global scores
    global_scores = {}
    for method in Q.BASE_METHODS:
        global_scores[method] = scores[method].mean(axis=1)
    global_scores["consensus"] = np.mean([ranked[method].mean(axis=1) for method in Q.BASE_METHODS], axis=0)

    global_top = {}
    sets_by_method = {}
    for method in Q.METHODS:
        order = np.lexsort((index, -global_scores[method]))[:Q.K]
        global_top[method] = [int(position) for position in order]
        sets_by_method[method] = [list(global_top[method]) for _ in TARGET_COLS]

    pairs = Q.pairwise_jaccard(sets_by_method)
    summary = Q.jaccard_summary(pairs)

    # ------------------------------------------------------------------ evidence that one global set is dimension-blind
    dimension_percentile = {}
    for method in Q.METHODS:
        rows = []
        for d, target in enumerate(TARGET_COLS):
            positions = global_top[method]
            rows.append({"dimension": target,
                         "meanPercentile": float(np.mean([ranked[method][position, d] for position in positions]))})
        dimension_percentile[method] = rows

    global_table = []
    for method in Q.METHODS:
        for rank, position in enumerate(global_top[method]):
            name = Q.CANDIDATE_NAMES[position]
            global_table.append({
                "method": method, "rank": rank + 1, "compound": name,
                "globalScore": float(global_scores[method][position]),
                "meanAbsRhoTotal": float(scores["total_spearman"][position].mean()),
                "meanAbsRhoWithin": float(scores["within_style_spearman"][position].mean()),
                "meanAbsBetaGraph": float(scores["graph_lowrank"][position].mean()),
                "meanConsensusPercentile": float(ranked["consensus"][position].mean()),
            })

    with open("sets.json", "w", encoding="utf-8") as handle:
        json.dump(Q.sets_payload(sets_by_method), handle, ensure_ascii=False, indent=1)

    report("settings", {
        "modelKind": "baseline",
        "method": "dimension-blind global Top-3 (one shared set per scoring method)",
        "seed": int(seed), "k": Q.K, "tau": Q.TAU,
        "graph": {"representation": "zscore", "rank": Q.GRAPH_SETTINGS["rank"],
                  "lambda": Q.GRAPH_SETTINGS["lambda"], "gamma": Q.GRAPH_SETTINGS["gamma"],
                  "nIter": 25, "tau": Q.TAU},
        "candidates": "%d single-compound columns (COMPOUND_CANDIDATES)" % n_candidates,
        "trainingRows": "200 rows of data/splits/SPLIT-0001/train.csv (registered dependency; no split)",
        "scoring": "each method's score averaged over the 50 dimensions; consensus = mean within-dimension percentile rank, averaged over methods and dimensions",
        "coverage": coverage,
    })
    report("global_top3", global_table)
    report("method_jaccard", {"pairs": pairs, "summary": summary,
                              "definition": "J = |A n B| / (2k - |A n B|), k = 3; mean over 50 dimensions and the 6 method pairs"})
    report("dimension_blind_evidence", {
        "note": "mean within-dimension percentile rank of the shared global set; a dimension-specific Top-3 would sit near the top of this column",
        "perMethod": dimension_percentile,
        "meanPercentile": {method: float(np.mean([row["meanPercentile"] for row in rows]))
                           for method, rows in dimension_percentile.items()},
    })
    report("sets_path", "sets.json")

    emit_metrics({
        "topk-jaccard": float(summary["overall"]),
        "n_dimensions": int(len(TARGET_COLS)),
        "n_methods": int(len(Q.METHODS)),
        "n_candidates": int(n_candidates),
        "tau": float(Q.TAU),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
