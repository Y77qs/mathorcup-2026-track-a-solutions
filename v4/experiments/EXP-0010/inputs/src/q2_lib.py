"""q2_lib.py — Q2 ranking / set-stability / co-expression helpers.

The PRIMARY metric is defined exactly as the pack's native set-stability recompute
(`runtime/quality/evaluation.js`, kind:"set-stability"):
    per dimension: mean pairwise Jaccard over all method pairs, J(a,b)=|A∩B|/(2k-|A∩B|) with k=3
    value        : mean of the per-dimension values
so `metrics["topk-jaccard"]` recomputes to within 1e-8 from sets.json alone.

Everything is deterministic: fixed seed, single-threaded BLAS, ties broken by feature order
(`np.lexsort((arange, -score))`), and the bootstrap uses one `np.random.default_rng(seed)` stream.
"""

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

import q_common as C

TOP_K = 3
ALPHA_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)


def standardise(X_train: np.ndarray, X_test: np.ndarray):
    mean = X_train.mean(axis=0)
    scale = X_train.std(axis=0)
    scale = np.where(scale > 0, scale, 1.0)
    return (X_train - mean) / scale, (X_test - mean) / scale


def spearman_abs(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """|Spearman rho| between every feature column of X and every column of Y (no NaN; ranks averaged for ties)."""
    n = X.shape[0]
    rank_x = rankdata(X, axis=0)
    rank_y = rankdata(Y, axis=0)
    centred_x = rank_x - rank_x.mean(axis=0)
    centred_y = rank_y - rank_y.mean(axis=0)
    norm_x = np.sqrt((centred_x ** 2).sum(axis=0))
    norm_y = np.sqrt((centred_y ** 2).sum(axis=0))
    norm_x = np.where(norm_x > 0, norm_x, np.inf)
    norm_y = np.where(norm_y > 0, norm_y, np.inf)
    corr = (centred_x.T @ centred_y) / np.outer(norm_x, norm_y)
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    return np.abs(np.clip(corr, -1.0, 1.0))


def kendall_abs(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """|Kendall tau-b| between every feature column of X and every column of Y (rank-based robustness variant)."""
    from scipy.stats import kendalltau
    n_features, n_targets = X.shape[1], Y.shape[1]
    out = np.zeros((n_features, n_targets))
    for target in range(n_targets):
        y = Y[:, target]
        for feature in range(n_features):
            tau = kendalltau(X[:, feature], y).statistic
            out[feature, target] = 0.0 if not np.isfinite(tau) else abs(float(tau))
    return out


def pearson_abs(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """|Pearson r| (linear association) as an alternative univariate ranking."""
    a = X - X.mean(axis=0)
    b = Y - Y.mean(axis=0)
    na = np.sqrt((a ** 2).sum(axis=0))
    nb = np.sqrt((b ** 2).sum(axis=0))
    na = np.where(na > 0, na, np.inf)
    nb = np.where(nb > 0, nb, np.inf)
    corr = (a.T @ b) / np.outer(na, nb)
    return np.abs(np.nan_to_num(np.clip(corr, -1.0, 1.0)))


def ridge_coefficients(X: np.ndarray, Y: np.ndarray, alpha: float) -> np.ndarray:
    """Multi-output ridge on already-standardised X: (X'X + alpha I)^-1 X'Y  ->  (p x q) coefficients."""
    p = X.shape[1]
    gram = X.T @ X + alpha * np.eye(p)
    return np.linalg.solve(gram, X.T @ Y)


def select_alpha(X: np.ndarray, Y: np.ndarray, seed: int) -> tuple:
    folds = KFold(n_splits=5, shuffle=True, random_state=seed)
    table = {}
    for alpha in ALPHA_GRID:
        errors = []
        for fit_index, score_index in folds.split(X):
            beta = ridge_coefficients(X[fit_index], Y[fit_index], alpha)
            errors.append(np.abs(Y[score_index] - X[score_index] @ beta).reshape(-1))
        table[alpha] = float(np.mean(np.concatenate(errors)))
    best = min(ALPHA_GRID, key=lambda a: (table[a], a))
    return float(best), table


def forest_importance(X: np.ndarray, Y: np.ndarray, seed: int, trees: int = 120) -> np.ndarray:
    """Random-forest impurity importance per sensory dimension (non-linear, multivariate)."""
    importance = np.zeros((X.shape[1], Y.shape[1]))
    for column in range(Y.shape[1]):
        model = RandomForestRegressor(
            n_estimators=trees, max_features="sqrt", min_samples_leaf=5,
            random_state=int(seed) + column, n_jobs=1,
        )
        model.fit(X, Y[:, column])
        importance[:, column] = model.feature_importances_
    return importance


def score_estimators(methods, X: np.ndarray, Y: np.ndarray, alpha: float) -> dict:
    """Compute the requested ranking scores; unsupported method names raise (never silently skipped)."""
    out = {}
    for method in methods:
        if method == "spearman_absrho":
            out[method] = spearman_abs(X, Y)
        elif method == "kendall_absrho":
            out[method] = kendall_abs(X, Y)
        elif method == "pearson_absrho":
            out[method] = pearson_abs(X, Y)
        elif method == "ridge_coef":
            out[method] = np.abs(ridge_coefficients(X, Y, alpha))
        elif method == "random_forest_importance":
            raise ValueError("random_forest_importance is fitted separately (forest_importance), not as a score matrix")
        else:
            raise ValueError("unknown ranking method %r" % method)
    return out


def top_k_indices(scores: np.ndarray, k: int = TOP_K) -> np.ndarray:
    """Deterministic top-k per column: descending score, ties broken by ascending feature index."""
    order = np.arange(scores.shape[0])
    out = np.empty((k, scores.shape[1]), dtype=int)
    for column in range(scores.shape[1]):
        out[:, column] = np.lexsort((order, -scores[:, column]))[:k]
    return out


def build_sets(rankings: dict, features: list, dimensions: list, k: int = TOP_K) -> dict:
    """{'selected': {method: {dim: [names]}}, 'rows': the pack's expected JSON array of rows}."""
    selected = {}
    rows = []
    for method, scores in rankings.items():
        indices = top_k_indices(scores, k)
        selected[method] = {}
        for column, dimension in enumerate(dimensions):
            items = [features[i] for i in indices[:, column]]
            selected[method][dimension] = items
            rows.append({"dimension": dimension, "method": method, "items": items})
    return {"selected": selected, "rows": rows}


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    union = len(a | b)
    return 0.0 if union == 0 else len(a & b) / union


def topk_jaccard(selected: dict, dimensions: list, methods: list, k: int = TOP_K) -> tuple:
    """The native definition, reimplemented independently so the emitted value can be audited."""
    per_dimension = {}
    for dimension in dimensions:
        values = []
        for index_a in range(len(methods)):
            for index_b in range(index_a + 1, len(methods)):
                a = selected[methods[index_a]][dimension]
                b = selected[methods[index_b]][dimension]
                intersection = len(set(a) & set(b))
                values.append(intersection / (2 * k - intersection))
        per_dimension[dimension] = float(np.mean(values))
    value = float(np.mean(list(per_dimension.values())))
    return value, per_dimension


def method_overlap(selected: dict, dimensions: list, methods: list) -> dict:
    matrix = {}
    for index_a, method_a in enumerate(methods):
        for index_b, method_b in enumerate(methods):
            if index_b <= index_a:
                continue
            values = [jaccard(selected[method_a][d], selected[method_b][d]) for d in dimensions]
            matrix[method_a + "|" + method_b] = float(np.mean(values))
    return matrix


def bootstrap_inclusion(X: np.ndarray, Y: np.ndarray, dimensions: list, features: list,
                        rankings: dict, methods: list, alpha: float, seed: int,
                        replicates: int = 500) -> dict:
    """Empirical Top-3 inclusion frequency under train-row bootstrap resampling.

    The bootstrapped estimators are the ones that can be refitted cheaply on a resample (`spearman_absrho`,
    `kendall_absrho`, `pearson_absrho`, `ridge_coef`); a forest refit per resample is not feasible and is excluded.
    The alpha used is the one selected on the full training rows (re-selecting alpha inside every replicate is a
    different, much more expensive protocol and is NOT claimed here). Paired resampling: the same rows feed every
    bootstrapped estimator in a replicate.
    """
    estimators = [method for method in methods
                  if method in ("spearman_absrho", "kendall_absrho", "pearson_absrho", "ridge_coef")]
    if not estimators:
        raise ValueError("no bootstrappable ranking method was requested")
    rng = np.random.default_rng(int(seed))
    n = X.shape[0]
    counts = {method: {dimension: {} for dimension in dimensions} for method in estimators}
    for _ in range(replicates):
        index = rng.integers(0, n, n)
        scores = score_estimators(estimators, X[index], Y[index], alpha)
        for method in estimators:
            indices = top_k_indices(scores[method], TOP_K)
            for column, dimension in enumerate(dimensions):
                bucket = counts[method][dimension]
                for feature_index in indices[:, column]:
                    name = features[feature_index]
                    bucket[name] = bucket.get(name, 0) + 1
    frequencies = {method: {dimension: {name: count / replicates for name, count in bucket.items()}
                            for dimension, bucket in counts[method].items()}
                   for method in estimators}
    summary = {}
    for method in estimators:
        values = []
        for dimension in dimensions:
            chosen = rankings_selected_names(rankings, method, dimensions, features, dimension)
            values.append(float(np.mean([frequencies[method][dimension].get(name, 0.0) for name in chosen])))
        summary[method] = float(np.mean(values))
    mean_value = float(np.mean(list(summary.values())))
    return {"replicates": replicates, "seed": int(seed), "estimators": estimators,
            "perMethodMeanInclusion": summary, "value": mean_value, "frequencies": frequencies}


def rankings_selected_names(rankings: dict, method: str, dimensions: list, features: list, dimension: str) -> list:
    column = dimensions.index(dimension)
    indices = top_k_indices(rankings[method], TOP_K)[:, column]
    return [features[i] for i in indices]


def frequency_table(frequencies: dict, selected: dict, dimensions: list, features: list) -> dict:
    """Compact, paper-ready frequency table: selected compounds plus the 10 most frequent alternatives per cell."""
    table = {}
    for method, per_dimension in frequencies.items():
        table[method] = {}
        for dimension in dimensions:
            bucket = per_dimension[dimension]
            chosen = {name: bucket.get(name, 0.0) for name in selected[method][dimension]}
            alternatives = sorted(((name, value) for name, value in bucket.items() if name not in chosen),
                                  key=lambda item: (-item[1], item[0]))[:10]
            table[method][dimension] = {"selected": chosen,
                                        "topAlternatives": [{"compound": n, "frequency": v} for n, v in alternatives]}
    return table


# ----------------------------------------------------------------------------------------------------------------
# co-expression structure from 2.csv (declared Spearman matrix; non-PSD -> documented projection)
# ----------------------------------------------------------------------------------------------------------------
def psd_project(matrix: np.ndarray) -> tuple:
    """Nearest correlation matrix by eigenvalue clipping + diagonal renormalisation (documented, deterministic)."""
    symmetric = (matrix + matrix.T) / 2.0
    values, vectors = np.linalg.eigh(symmetric)
    clipped = np.clip(values, 0.0, None)
    projected = vectors @ np.diag(clipped) @ vectors.T
    diagonal = np.sqrt(np.clip(np.diag(projected), 1e-12, None))
    projected = projected / np.outer(diagonal, diagonal)
    np.fill_diagonal(projected, 1.0)
    return projected, float(np.min(values)), float(np.min(np.linalg.eigvalsh((projected + projected.T) / 2.0)))


def _normalise_name(text) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def load_correlation_matrix(chem_features: list) -> dict:
    """Load 2.csv, map its chemical-name labels onto the chem__* features, and project to PSD.

    Label mapping: 2.csv rows/columns are chemical names ("Dimethyl sulfide", "Carbon disulfide"), while the
    dataset uses 1.csv field names ("DMS", "CS2"). The bridge is 8.xlsx sheet "Sensory thresholds"
    (field_name_python -> chemical_name_short), matched after removing all non-alphanumeric characters and
    lower-casing; a direct normalised match against the 2.csv label is tried first.
    If fewer than 50 compounds can be matched, an empirical Spearman matrix from the registered data is used
    instead and that substitution is recorded (it is never silently presented as 2.csv).
    """
    matrix_frame, basis = C.read_dependency_indexed("data/raw/2.csv", index_col=0)
    if matrix_frame.shape[0] != matrix_frame.shape[1] or matrix_frame.shape[0] < 2:
        raise RuntimeError("2.csv is not a square compound x compound matrix (shape %s)" % (matrix_frame.shape,))
    labels = [str(c) for c in matrix_frame.columns]
    label_index = {}
    for position, label in enumerate(labels):
        label_index.setdefault(_normalise_name(label), position)
    field_names = [f[len(C.CHEM_PREFIX):] for f in chem_features]

    field_to_short = {}
    threshold_basis = "unavailable"
    try:
        thresholds, threshold_basis = C.read_dependency_xlsx("data/raw/8.xlsx", "Sensory thresholds")
        for _, row in thresholds.iterrows():
            field = _normalise_name(row.get("field_name_python"))
            short = row.get("chemical_name_short")
            if field and short is not None and str(short).strip():
                field_to_short.setdefault(field, str(short).strip())
    except Exception:  # a missing/renamed xlsx must not kill the experiment; the substitution is recorded
        threshold_basis = "unavailable"

    mapping, matched_direct, matched_via_xlsx = {}, 0, 0
    for field in field_names:
        index = label_index.get(_normalise_name(field))
        if index is not None:
            matched_direct += 1
        else:
            short = field_to_short.get(_normalise_name(field))
            if short is not None:
                index = label_index.get(_normalise_name(short))
                if index is not None:
                    matched_via_xlsx += 1
        if index is not None and index not in mapping.values():
            mapping[field] = index

    if len(mapping) >= 50:
        order = sorted(mapping.items(), key=lambda item: item[1])
        index = [item[1] for item in order]
        names = [item[0] for item in order]
        block = matrix_frame.iloc[index, index].to_numpy(dtype=float)
        projected, minimum_before, minimum_after = psd_project(block)
        full = matrix_frame.to_numpy(dtype=float)
        full_eigen = np.sort(np.linalg.eigvalsh((full + full.T) / 2.0))
        block_eigen = np.sort(np.linalg.eigvalsh((block + block.T) / 2.0))
        return {"source": "data/raw/2.csv", "basis": basis, "thresholdNameBasis": threshold_basis,
                "compounds": names, "projected": projected,
                "minEigenBefore": minimum_before, "minEigenAfter": minimum_after,
                "minEigenFullMatrix": float(full_eigen[0]),
                "minEigenDeliveredFullMatrix": float(full_eigen[0]),
                "rawBlockEigen": block_eigen,
                "projectedBlockEigen": np.sort(np.linalg.eigvalsh((projected + projected.T) / 2.0)),
                "nCompounds": len(names), "nUnmatched": len(field_names) - len(names),
                "nMatchedDirect": matched_direct, "nMatchedViaXlsx": matched_via_xlsx,
                "role": "documented Spearman co-expression structure; NOT an independent external prior; "
                        "5.csv/6.csv/7.csv are not used as validation"}

    # fallback: empirical Spearman from the registered feature table (recorded as a substitution)
    data = C.load_dataset()
    features = [f for f in chem_features if f in data.columns]
    values = C.matrix(data, features)
    empirical = spearman_abs(values, values)
    projected, minimum_before, minimum_after = psd_project(empirical)
    return {"source": "empirical Spearman recomputed from the registered feature table (2.csv label mapping failed)",
            "basis": "fallback", "thresholdNameBasis": threshold_basis,
            "compounds": [f[len(C.CHEM_PREFIX):] for f in features], "projected": projected,
            "minEigenBefore": minimum_before, "minEigenAfter": minimum_after,
            "minEigenFullMatrix": minimum_before,
            "rawBlockEigen": np.sort(np.linalg.eigvalsh((empirical + empirical.T) / 2.0)),
            "projectedBlockEigen": np.sort(np.linalg.eigvalsh((projected + projected.T) / 2.0)),
            "nCompounds": len(features), "nUnmatched": 0,
            "nMatchedDirect": 0, "nMatchedViaXlsx": 0,
            "role": "empirical co-expression structure; NOT an independent external prior"}
