"""q2_lib.py — Q2 shared machinery: three ingredient scores, the consensus ranking, style-stratified
bootstrap Top-3 stability, Jaccard scoring against the plugin definition, chemistry modules and the
6.csv external-corroboration alignment.

Scope.  Q2 ranks SINGLE-COMPOUND chemistry columns (``COMPOUND_CANDIDATES``, 219 of them; the 5 derived sums
and the 7 physical parameters are excluded by construction) against each of the 50 sensory dimensions, using
the 200 SPLIT-0001 train rows only (read through ``dependency_path`` because the Q2 experiment hangs no split).

Ingredients (all refitted inside every bootstrap resample):
  1. ``total_spearman``          |Spearman(chem_j, sensory_t)| over the 200 rows;
  2. ``within_style_spearman``   rank both sides, residualise the ranks on style dummies + intercept
                                 (r = (I - H (H^T H)^+ H^T) rank), then |Pearson(r_X, r_Y)|;
  3. ``graph_lowrank``           the Q1 graph-regularised low-rank multi-output regression on the train graph
                                 (tau = 0.5, lambda = 1, gamma = 0.1, r = 6, un-tuned), score = |B_jt|.
The consensus score is the mean of the three within-dimension percentile ranks (larger = stronger).

Delivered Top-3 per (dimension, method): candidates ordered by bootstrap selection frequency pi, ties broken
by the point-estimate score, then by the frozen candidate order.
"""

import itertools
import re

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from q_common import spearman_matrix, percentile_rank, dependency_path, read_dependency_json
from target_columns import FEATURE_COLS, TARGET_COLS, COMPOUND_CANDIDATES, STYLE_COLUMN

import q1_lib as L

METHODS = ("total_spearman", "within_style_spearman", "graph_lowrank", "consensus")
BASE_METHODS = METHODS[:3]
K = 3
TAU = 0.5
GRAPH_SETTINGS = {"rank": 6, "lambda": 1.0, "gamma": 0.1}
N_BOOTSTRAP = 500
SPLIT_TRAIN_DEPENDENCY = "data/splits/SPLIT-0001/train.csv"
CHEM_META_DEPENDENCY = "data/clean/q2_chem_meta.json"
EXTERNAL_DEPENDENCY = "data/raw/imported/a55004fb0390299a-6.csv"

CANDIDATE_POSITIONS = [FEATURE_COLS.index(name) for name in COMPOUND_CANDIDATES]
CANDIDATE_NAMES = list(COMPOUND_CANDIDATES)


# --------------------------------------------------------------------------------------------- loading
def load_train_frame() -> pd.DataFrame:
    frame = pd.read_csv(dependency_path(SPLIT_TRAIN_DEPENDENCY))
    if len(frame) != 200:
        raise RuntimeError("expected 200 train rows, got %d" % len(frame))
    missing = [c for c in TARGET_COLS if c not in frame.columns]
    if missing:
        raise RuntimeError("sensory targets missing from the train table: %s" % missing[:3])
    if STYLE_COLUMN not in frame.columns:
        raise RuntimeError("style column %r missing" % STYLE_COLUMN)
    return frame.reset_index(drop=True)


# --------------------------------------------------------------------------------------------- ranks / style projection
def midranks(matrix: np.ndarray) -> np.ndarray:
    """Mid-ranks per column (ties share their mean rank); deterministic."""
    values = np.asarray(matrix, dtype=float)
    out = np.empty_like(values)
    for column in range(values.shape[1]):
        order = np.argsort(values[:, column], kind="mergesort")
        ordered = values[order, column]
        unique, inverse, counts = np.unique(ordered, return_inverse=True, return_counts=True)
        mid = np.cumsum(counts) - (counts - 1) / 2.0
        out[order, column] = mid[inverse]
    return out


def style_basis(styles) -> dict:
    """H = [1 | style dummies] and the pseudo-inverse of H^T H (styles in sorted order)."""
    labels = pd.factorize(pd.Series(styles), sort=True)
    codes = np.asarray(labels[0], dtype=int)
    n_styles = int(codes.max()) + 1 if codes.size else 0
    n = len(codes)
    design = np.zeros((n, n_styles + 1), dtype=float)
    design[:, 0] = 1.0
    design[np.arange(n), codes + 1] = 1.0
    gram = design.T @ design
    return {"design": design, "gramInverse": np.linalg.pinv(gram), "nStyles": n_styles}


def residualise(matrix: np.ndarray, basis: dict) -> np.ndarray:
    design, gram_inverse = basis["design"], basis["gramInverse"]
    return matrix - design @ (gram_inverse @ (design.T @ matrix))


def column_correlation(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    left_norm = np.linalg.norm(left, axis=0)
    right_norm = np.linalg.norm(right, axis=0)
    numerator = left.T @ right
    denominator = np.outer(np.maximum(left_norm, 1e-12), np.maximum(right_norm, 1e-12))
    return numerator / denominator


# --------------------------------------------------------------------------------------------- scores
def ingredient_scores(frame: pd.DataFrame, tau: float = TAU) -> dict:
    """The three ingredient score matrices plus the signed total correlation, all on the 219 candidates."""
    imputed = L.imputed_blocks(frame, {"train": frame})["train"]
    features = imputed[:, :L.N_FEATURES]
    targets = L.raw_target_matrix(frame)
    signed_total = spearman_matrix(features, targets)  # 231 x 50
    total = np.abs(signed_total)
    basis = style_basis(frame[STYLE_COLUMN].to_numpy())
    within = np.abs(column_correlation(residualise(midranks(features), basis),
                                       residualise(midranks(targets), basis)))
    fitted = L.FittedModel(frame, "zscore", GRAPH_SETTINGS["rank"], GRAPH_SETTINGS["lambda"],
                           GRAPH_SETTINGS["gamma"], tau=tau)
    beta = np.abs(fitted.model["beta"][:L.N_FEATURES, :])
    return {"candidates": CANDIDATE_POSITIONS,
            "signedTotal": signed_total[CANDIDATE_POSITIONS],
            "total_spearman": total[CANDIDATE_POSITIONS],
            "within_style_spearman": within[CANDIDATE_POSITIONS],
            "graph_lowrank": beta[CANDIDATE_POSITIONS],
            "graph": fitted.graph}


def percentile_block(scores: dict) -> dict:
    """Within-dimension percentile ranks over the 219 candidates, plus the mean-based consensus score."""
    ranked = {method: percentile_rank(scores[method]) for method in BASE_METHODS}
    ranked["consensus"] = (ranked["total_spearman"] + ranked["within_style_spearman"]
                           + ranked["graph_lowrank"]) / 3.0
    return ranked


def topk_from_scores(ranked: dict, k: int = K) -> dict:
    """Top-k candidate positions per dimension, ordered by score (desc), ties by frozen candidate order."""
    out = {}
    n_candidates, n_dimensions = ranked[BASE_METHODS[0]].shape
    index = np.arange(n_candidates)
    for method in METHODS:
        matrix = ranked[method]
        chosen = []
        for dimension in range(n_dimensions):
            order = np.lexsort((index, -matrix[:, dimension]))[:k]
            chosen.append([int(v) for v in order])
        out[method] = chosen
    return out


def topk_from_pi(pi: dict, ranked: dict, k: int = K) -> dict:
    """Top-k by bootstrap selection frequency pi, ties broken by the point-estimate score."""
    out = {}
    n_candidates, n_dimensions = ranked[BASE_METHODS[0]].shape
    index = np.arange(n_candidates)
    for method in METHODS:
        chosen = []
        for dimension in range(n_dimensions):
            order = np.lexsort((index, -ranked[method][:, dimension], -pi[method][:, dimension]))[:k]
            chosen.append([int(v) for v in order])
        out[method] = chosen
    return out


# --------------------------------------------------------------------------------------------- bootstrap
def bootstrap_counts(frame: pd.DataFrame, seed: int, n_reps: int = N_BOOTSTRAP, tau: float = TAU) -> dict:
    """Style-stratified bootstrap: resample each style with replacement to its own size, refit everything."""
    styles = frame[STYLE_COLUMN].to_numpy()
    style_order = sorted(set(styles.tolist()))
    groups = [np.nonzero(styles == style)[0] for style in style_order]
    rng = L.rng_for(seed, 21)
    n_candidates = len(CANDIDATE_POSITIONS)
    counts = {method: np.zeros((n_candidates, len(TARGET_COLS)), dtype=np.int32) for method in METHODS}
    for _ in range(int(n_reps)):
        indices = np.concatenate([group[rng.integers(0, group.size, size=group.size)] for group in groups])
        sample = frame.iloc[indices].reset_index(drop=True)
        scores = ingredient_scores(sample, tau=tau)
        ranked = percentile_block(scores)
        chosen = topk_from_scores(ranked, K)
        for method in METHODS:
            for dimension, positions in enumerate(chosen[method]):
                counts[method][positions, dimension] += 1
    return counts


def frequencies(counts: dict, n_reps: int) -> dict:
    return {method: counts[method].astype(float) / float(n_reps) for method in METHODS}


# --------------------------------------------------------------------------------------------- jaccard
def jaccard(left, right) -> float:
    """|A n B| / (2k - |A n B|) with the plugin definition (k = 3 -> denominator 6 - |A n B|)."""
    intersection = len(set(left) & set(right))
    union = len(set(left)) + len(set(right)) - intersection
    return float(intersection) / float(union) if union else 0.0


def pairwise_jaccard(sets_by_method: dict, methods=METHODS) -> dict:
    pairs = {}
    n_dimensions = len(sets_by_method[methods[0]])
    for left, right in itertools.combinations(methods, 2):
        values = [jaccard(sets_by_method[left][d], sets_by_method[right][d]) for d in range(n_dimensions)]
        pairs[left + "|" + right] = {"mean": float(np.mean(values)), "perDimension": [float(v) for v in values]}
    return pairs


def jaccard_summary(pairs: dict) -> dict:
    means = [value["mean"] for value in pairs.values()]
    return {"overall": float(np.mean(means)), "pairMeans": {key: value["mean"] for key, value in pairs.items()}}


# --------------------------------------------------------------------------------------------- modules
def module_table(graph: dict) -> dict:
    """Chemistry modules = connected components of the thresholded |W| graph (tau = 0.5)."""
    weight = graph["weight"]
    adjacency = (np.abs(weight) > 0).astype(np.int8)
    count, labels = connected_components(csr_matrix(adjacency), directed=False)
    labels = np.asarray(labels, dtype=int)
    sizes = np.bincount(labels)
    per_compound = {}
    for name in COMPOUND_CANDIDATES:
        position = FEATURE_COLS.index(name)
        per_compound[name] = {"moduleId": int(labels[position]), "moduleSize": int(sizes[labels[position]])}
    members = {}
    for module in range(int(count)):
        names = [FEATURE_COLS[j] for j in np.nonzero(labels == module)[0]]
        members[str(module)] = {"size": int(len(names)), "features": names}
    return {"count": int(count), "perCompound": per_compound, "members": members,
            "edgeCount": int(adjacency.sum() // 2), "moduleSizes": sizes.tolist(),
            "labels": labels.tolist()}


# --------------------------------------------------------------------------------------------- external 6.csv
def normalise_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def spearman_between(left: np.ndarray, right: np.ndarray) -> float:
    if left.size < 3 or right.size != left.size:
        return 0.0
    a = midranks(left.reshape(-1, 1))[:, 0]
    b = midranks(right.reshape(-1, 1))[:, 0]
    a = a - a.mean()
    b = b - b.mean()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 0.0 if denominator <= 1e-12 else float(a @ b / denominator)


def external_corroboration(signed_total: np.ndarray) -> dict:
    """Rank correlation of our |Spearman| with the literature table in 6.csv (external corroboration only).

    Alignment note: 6.csv has 44 compound rows keyed by English compound names; the ``corrIndex`` field of
    q2_chem_meta.json indexes the 231x231 chemistry correlation matrix in 2.csv (not registered as a
    dependency), so the rows here are aligned through the meta ``corrLabel`` (normalised, 44/44 matched).
    The 50 sensory columns of 6.csv are taken in the same order as TARGET_COLS.
    """
    table = pd.read_csv(dependency_path(EXTERNAL_DEPENDENCY))
    meta = read_dependency_json(CHEM_META_DEPENDENCY)
    label_to_feature = {normalise_label(record["corrLabel"]): record["name"] for record in meta["features"]}
    rows = []
    for row in range(len(table)):
        name = label_to_feature.get(normalise_label(table.iloc[row, 0]))
        rows.append({"row": int(row), "label": str(table.iloc[row, 0]), "feature": name,
                     "position": None if name is None else FEATURE_COLS.index(name)})
    matched = [record for record in rows if record["position"] is not None]
    values = table.iloc[:, 1:].to_numpy(dtype=float)
    if values.shape[1] != len(TARGET_COLS):
        raise RuntimeError("6.csv does not carry %d sensory columns" % len(TARGET_COLS))
    ours_positions = [record["position"] for record in matched]
    theirs_rows = [record["row"] for record in matched]
    per_dimension = []
    for dimension, target in enumerate(TARGET_COLS):
        ours = np.abs(signed_total[ours_positions, dimension])
        theirs = np.abs(values[theirs_rows, dimension])
        per_dimension.append({"dimension": target, "spearman": spearman_between(ours, theirs),
                              "nCompounds": int(len(matched))})
    finite = np.asarray([record["spearman"] for record in per_dimension], dtype=float)
    return {"alignment": "6.csv row labels matched to q2_chem_meta corrLabel (normalised); 44/44 matched; "
                         "columns taken in TARGET_COLS order; corrIndex indexes 2.csv (231x231, not registered)",
            "nMatched": len(matched), "nUnmatched": len(rows) - len(matched),
            "unmatchedLabels": [record["label"] for record in rows if record.get("feature") is None],
            "meanSpearman": float(np.mean(finite)), "medianSpearman": float(np.median(finite)),
            "perDimension": per_dimension}


# --------------------------------------------------------------------------------------------- tables
def final_table(sets_by_method: dict, scores: dict, pi: dict, modules: dict) -> list:
    """The delivered (consensus) Top-3 table with direction, |rho|, pi, module id and style-confound class."""
    table = []
    for dimension, target in enumerate(TARGET_COLS):
        for rank, position in enumerate(sets_by_method["consensus"][dimension]):
            name = CANDIDATE_NAMES[position]
            absolute_total = float(scores["total_spearman"][position, dimension])
            absolute_within = float(scores["within_style_spearman"][position, dimension])
            signed = float(scores["signedTotal"][position, dimension])
            if absolute_within >= 0.8 * absolute_total:
                confound = "within-consistent"
            elif absolute_total >= 0.25 and absolute_within < 0.5 * absolute_total:
                confound = "style-driven"
            else:
                confound = "mixed"
            table.append({
                "dimension": target,
                "rank": rank + 1,
                "compound": name,
                "direction": "positive" if signed >= 0 else "negative",
                "absRhoTotal": absolute_total,
                "absRhoWithin": absolute_within,
                "absBetaGraph": float(scores["graph_lowrank"][position, dimension]),
                "pi": float(pi["consensus"][position, dimension]),
                "moduleId": modules["perCompound"][name]["moduleId"],
                "moduleSize": modules["perCompound"][name]["moduleSize"],
                "styleConfound": confound,
            })
    return table


def sets_payload(sets_by_method: dict) -> list:
    rows = []
    for dimension, target in enumerate(TARGET_COLS):
        for method in METHODS:
            rows.append({"dimension": target, "method": method,
                         "items": [CANDIDATE_NAMES[position] for position in sets_by_method[method][dimension]]})
    return rows
