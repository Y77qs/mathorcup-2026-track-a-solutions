"""Q2 共享层（只读 `common.py`）：数据加载/名称对齐/预处理/统计与图工具。

设计约束：
  * 本文件只做**机械工具**，不替任何方法做选择判断；
  * 名称对齐全部走 8.xlsx 的 `Sensory names`（感官）与 `Sensory thresholds` 的
    `chemical_name / field_name_R`（化合物），不做模糊猜测；映射表落盘可审计；
  * 6.csv / 5.csv / 8.xlsx 的 GBM 产物**不进入**任何选择方法的输入：选择只读
    2.csv（图结构）、1.csv（特征）、4.csv（目标）。独立先验核对在 q2_select.py 里
    以只读方式加载 6.csv，并用代码路径声明"选择发生时 6.csv 尚未读入"。

关键常量（预注册，不得事后调整）：
  BOOTSTRAP_B=300, BOOTSTRAP_B_SECONDARY=20, FREQ_THRESHOLD=0.80, JACCARD_THRESHOLD=0.50
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

# ---------------------------------------------------------------- 预注册常量
SEED = 42


def effective_seed(default: int = SEED) -> int:
    """实验运行器通过 MODELING_SEED 传种子（稳健性计划会用 42/7/2024/123/9 复跑）；
    runner 外（run-script/直接执行）用默认 42。"""
    v = os.environ.get("MODELING_SEED")
    try:
        return int(v) if v not in (None, "") else int(default)
    except (TypeError, ValueError):
        return int(default)
BOOTSTRAP_B = 300            # M1/M4 的 bootstrap 重复次数（协议：B=300）
BOOTSTRAP_B_SECONDARY = 20   # M2/M3/AGG 的 bootstrap 重复次数（协议：30 以内）
FREQ_THRESHOLD = 0.80        # Top-3 席位入选频率 >= 0.80 视为稳定（协议）
JACCARD_THRESHOLD = 0.50     # 跨方法 Top-3 Jaccard 均值 >= 0.50 视为一致（协议）
FDR_Q = 0.05                 # BH-FDR 的 q 阈值（边/单变量）
METHODS = ["M1", "M2", "M3", "M4"]
METHOD_LABEL = {
    "M1": "M1 ridge(inner-CV alpha) standardized coef |b|",
    "M2": "M2 RandomForest 5-fold mean permutation importance",
    "M3": "M3 GraphicalLassoCV joint precision partial correlation |r|",
    "M4": "M4 univariate Spearman |rho| with BH-FDR",
}
AGG_FEATURES = list(C.AGG_FEATURES)


# ---------------------------------------------------------------- 名称归一化
_GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta",
          "ε": "epsilon", "ζ": "zeta", "μ": "mu"}


def norm_name(s) -> str:
    """把任意人名/表头归一化为可比较键（小写、去希腊字母/标点/空白）。"""
    s = str(s)
    for k, v in _GREEK.items():
        s = s.replace(k, v)
    s = s.lower().replace("\r", " ").replace("\n", " ")
    return re.sub(r"[^a-z0-9]+", "", s)


# ---------------------------------------------------------------- 名称映射
def _human_to_r_map() -> dict[str, str]:
    """8.xlsx Sensory thresholds：chemical_name / short / field_name_python -> field_name_R。"""
    th = C.load_sensory_thresholds()
    m: dict[str, str] = {}
    for _, r in th.iterrows():
        field = str(r["field_name_R"]).strip()
        for col in ("chemical_name", "chemical_name_short", "field_name_python", "field_name_R"):
            key = norm_name(r[col]) if pd.notna(r[col]) else ""
            if key and key not in m:
                m[key] = field
    return m


def corr2_map() -> pd.DataFrame:
    """Lead 固化的 1.csv->2.csv 名称映射（outputs/protocol/corr2_map.csv）。

    2.csv 行列是化学全名，231 列中 209 列按名字映射、22 列只能按位置；
    209 个可命名列的名字映射与位置映射 100% 一致（corr2_map.json 记录）。
    Q2 必须用这张表，使图节点名与 1.csv/6.csv/DRIVER_REGISTRY 对齐。
    """
    p = C.ROOT / "outputs" / "protocol" / "corr2_map.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} 不存在：先跑 Lead 的 corr2_map 生成脚本")
    d = pd.read_csv(p)
    need = {"col_1csv", "name_2csv", "via"}
    if not need <= set(d.columns):
        raise ValueError(f"corr2_map.csv 缺列: {need - set(d.columns)}")
    return d


def human_to_r_map() -> dict[str, str]:
    """公开别名：8.xlsx 化学全名 -> 1.csv(field_name_R) 的归一化映射。"""
    return _human_to_r_map()


def load_q2():
    """Q2 的全部输入；返回 dict（所有矩阵按 beer 顺序对齐）。

    keys:
      X_raw  250x231 DataFrame（1.csv 特征，混合尺度，含 73 缺失）
      X_imp  median-imputed（列中位数只在全表算一次；仅用于描述性关联，见报告限制）
      Xz     median-imputed + z-score（M1/M2/M3 输入）
      Y      250x50 DataFrame（4.csv 目标，标准化连续值）
      Yz     z-scored targets（数值上等于 Y，只做统一）
      R2    231x231 DataFrame（2.csv，按 corr2_map 换成 1.csv 列名）
      name_map  DataFrame（col_1csv / name_2csv / via）
      feat_cols list

    尺度限制（Lead 已核实）：1.csv 的 calibrated==0 在混合尺度表里对应
    log10(最小正浓度/2) 的 LOD/2 删失替代码（755 格）。因此**不要**把 1.csv 数值
    当真实浓度解释；浓度/OAV 一律用 C.oav_long()（作者标定浓度）。
    """
    feats = C.load_features().reset_index(drop=True)
    targ = C.load_targets().reset_index(drop=True)
    feat_cols = C.feature_columns()

    X_raw = feats[feat_cols].astype(float)

    # 2.csv 人名 -> 1.csv 列名：用 Lead 固化的映射表（名字优先，缺失按位置）
    cmap = corr2_map().set_index("col_1csv")
    r2_human = C.load_corr_compound()
    name_to_col = {}
    for col in feat_cols:
        nm = cmap.loc[col, "name_2csv"]
        name_to_col[str(nm).strip()] = col
    if len(name_to_col) != len(feat_cols):
        raise ValueError("corr2_map 的 name_2csv 有重复，映射不唯一")
    cols2 = [name_to_col[str(h).strip()] for h in r2_human.index]
    R2 = pd.DataFrame(r2_human.to_numpy(dtype=float), index=cols2, columns=cols2)
    R2 = R2.loc[feat_cols, feat_cols]
    name_map = cmap.reset_index()[["col_1csv", "name_2csv", "via"]].copy()

    # 名字映射与位置映射一致性抽查（Lead 记录为 100%）
    positional_equal = all(
        norm_name(cmap.loc[c, "name_2csv"]) == norm_name(cmap.loc[c, "positional_name"])
        for c in feat_cols)

    X_imp = X_raw.copy()
    med = X_raw.median(axis=0)
    for c in feat_cols:
        X_imp[c] = X_imp[c].fillna(med[c])
    mu = X_imp.mean(axis=0)
    sd = X_imp.std(axis=0, ddof=0).replace(0, 1.0)
    Xz = (X_imp - mu) / sd

    Y = targ[C.TARGET_DIMS].astype(float)
    Yz = (Y - Y.mean(axis=0)) / Y.std(axis=0, ddof=0).replace(0, 1.0)

    return {
        "X_raw": X_raw, "X_imp": X_imp, "Xz": Xz,
        "Y": Y, "Yz": Yz, "R2": R2, "name_map": name_map,
        "feat_cols": feat_cols, "beer": feats["beer"].to_numpy(),
        "targets": targ, "positional_equal": bool(positional_equal),
    }


def dim_map() -> pd.DataFrame:
    """Lead 的 50 维对齐表（outputs/protocol/dim_map.csv）；缺失则明确报错。"""
    p = C.ROOT / "outputs" / "protocol" / "dim_map.csv"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} 不存在：先跑 src/05_dim_map.py（Lead 所有），Q2 不自行猜 6.csv 列名")
    return pd.read_csv(p)


# ---------------------------------------------------------------- 统计工具
def sanitize(obj):
    """递归 JSON 安全化：numpy 标量->python，NaN/Inf->None（strict JSON）。"""
    import math
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, (bool,)):
        return bool(obj)
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return sanitize(obj.item())
        except Exception:
            pass
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, int):
        return int(obj)
    return obj


def bh_fdr(p: np.ndarray, q: float = None) -> np.ndarray:
    """Benjamini-Hochberg FDR；返回与输入同形状的 q 值。"""
    p = np.asarray(p, dtype=float)
    shape = p.shape
    flat = p.ravel()
    ok = np.isfinite(flat)
    out = np.full(flat.shape, np.nan)
    pv = flat[ok]
    n = pv.size
    if n == 0:
        return out.reshape(shape)
    order = np.argsort(pv)
    ranked = pv[order]
    qv = ranked * n / (np.arange(1, n + 1))
    qv = np.minimum.accumulate(qv[::-1])[::-1]
    qv = np.clip(qv, 0.0, 1.0)
    res = np.empty(n, dtype=float)
    res[order] = qv
    out[ok] = res
    return out.reshape(shape)


def spearman_matrix(A: np.ndarray) -> np.ndarray:
    """两两 Spearman（无缺失输入）；A: n x p -> p x p。"""
    from scipy.stats import rankdata
    R = np.apply_along_axis(rankdata, 0, np.asarray(A, dtype=float))
    R = (R - R.mean(axis=0)) / R.std(axis=0, ddof=0)
    return (R.T @ R) / R.shape[0]


def fisher_p(rho: np.ndarray, n: int) -> np.ndarray:
    """相关系数的 Fisher-z 双侧 p 值。"""
    from scipy.stats import norm
    r = np.clip(np.asarray(rho, dtype=float), -0.999999, 0.999999)
    z = np.arctanh(r) * np.sqrt(max(n - 3, 1))
    return 2.0 * norm.sf(np.abs(z))


def spearman_pair(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """逐列 Spearman：A n x p, B n x q -> p x q（无缺失）。"""
    from scipy.stats import rankdata
    Ra = np.apply_along_axis(rankdata, 0, np.asarray(A, float))
    Rb = np.apply_along_axis(rankdata, 0, np.asarray(B, float))
    Ra = (Ra - Ra.mean(axis=0)) / Ra.std(axis=0, ddof=0)
    Rb = (Rb - Rb.mean(axis=0)) / Rb.std(axis=0, ddof=0)
    return (Ra.T @ Rb) / Ra.shape[0]


# ---------------------------------------------------------------- 排名/Borda
def rank_high(scores: np.ndarray) -> np.ndarray:
    """score 越大越重要 -> rank 1 为最大（ties 取平均秩）。"""
    from scipy.stats import rankdata
    return rankdata(-np.asarray(scores, dtype=float), method="average")


def top_k_set(scores: np.ndarray, k: int = 3) -> list[int]:
    """返回 score 最高的 k 个索引；同分按索引升序（确定性）。"""
    s = np.asarray(scores, dtype=float)
    order = np.lexsort((np.arange(s.size), -s))
    return list(order[:k])


def jaccard(a, b) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else float("nan")


# ---------------------------------------------------------------- 图工具
def threshold_edges(R: np.ndarray, n_obs: int, q: float = FDR_Q):
    """对 2.csv 相关矩阵做 Fisher-z + BH(FDR)；返回上三角显著边与阈值统计。"""
    p = R.shape[0]
    iu, ju = np.triu_indices(p, k=1)
    rho = R[iu, ju]
    pvals = fisher_p(rho, n_obs)
    qvals = bh_fdr(pvals)
    sig = qvals < q
    # 等效 |rho| 阈值（显著边里最弱的 |rho|）
    tau = float(np.min(np.abs(rho[sig]))) if sig.any() else float("nan")
    return {"iu": iu, "ju": ju, "rho": rho, "p": pvals, "q": qvals,
            "sig": sig, "tau": tau, "n_sig": int(sig.sum()),
            "n_pairs": int(pvals.size)}


def greedy_modularity(W: np.ndarray, max_iter: int = 2000):
    """Clauset-Newman-Moore 贪心模块度合并（加权无向，W>=0）。

    返回 labels (n,), modularity Q。确定性：每次取最大正增益，同分取 (i,j) 字典序最小。
    """
    W = np.asarray(W, dtype=float)
    n = W.shape[0]
    m = W.sum() / 2.0
    if m <= 0:
        return np.arange(n), 0.0
    deg = W.sum(axis=1)
    labels = np.arange(n)
    K = deg.copy()
    members = [np.array([i]) for i in range(n)]
    Wc = W.copy()
    for _ in range(max_iter):
        c = Wc.shape[0]
        if np.allclose(K, 0):
            break
        with np.errstate(divide="ignore", invalid="ignore"):
            delta = Wc / m - np.outer(K, K) / (2.0 * m * m)
        np.fill_diagonal(delta, -np.inf)
        if c <= 1 or np.nanmax(delta) <= 1e-12:
            break
        i, j = np.unravel_index(np.nanargmax(delta), delta.shape)
        if i > j:
            i, j = j, i
        # merge j into i
        members[i] = np.concatenate([members[i], members[j]])
        K[i] = K[i] + K[j]
        Wc[i, :] += Wc[j, :]
        Wc[:, i] += Wc[:, j]
        Wc[i, i] = Wc[i, i]  # 自环保留
        # 删除 j
        keep = [k for k in range(c) if k != j]
        Wc = Wc[np.ix_(keep, keep)]
        K = K[keep]
        members = [members[k] for k in keep]
    labels = np.zeros(n, dtype=int)
    for cid, mem in enumerate(members):
        labels[mem] = cid
    return labels, modularity(W, labels)


def modularity(W: np.ndarray, labels) -> float:
    W = np.asarray(W, float)
    labels = np.asarray(labels)
    m = W.sum() / 2.0
    if m <= 0:
        return 0.0
    deg = W.sum(axis=1)
    q = 0.0
    for c in np.unique(labels):
        idx = labels == c
        q += W[np.ix_(idx, idx)].sum() / (2.0 * m) - (deg[idx].sum() / (2.0 * m)) ** 2
    return float(q)


def ari(a, b) -> float:
    """Adjusted Rand Index（模块划分一致性交叉核对，无需 sklearn）。"""
    from math import comb
    a = np.asarray(a)
    b = np.asarray(b)
    n = a.size
    ua, ub = np.unique(a), np.unique(b)
    cont = np.zeros((ua.size, ub.size), dtype=int)
    for i, va in enumerate(ua):
        for j, vb in enumerate(ub):
            cont[i, j] = int(((a == va) & (b == vb)).sum())
    sum_ij = sum(comb(int(x), 2) for x in cont.ravel())
    sum_i = sum(comb(int(x), 2) for x in cont.sum(axis=1))
    sum_j = sum(comb(int(x), 2) for x in cont.sum(axis=0))
    exp = sum_i * sum_j / comb(n, 2)
    mx = (sum_i + sum_j) / 2.0
    return float((sum_ij - exp) / (mx - exp)) if mx != exp else 1.0


def spring_layout(W: np.ndarray, seed: int = SEED, iterations: int = 150):
    """Fruchterman-Reingold 力导向布局（无需 networkx）；返回 n x 2。"""
    W = np.asarray(W, float)
    n = W.shape[0]
    rng = np.random.default_rng(seed)
    pos = rng.normal(size=(n, 2))
    pos -= pos.mean(axis=0)
    pos /= np.abs(pos).max() + 1e-12
    k = 1.0 / np.sqrt(max(n, 1))
    mask = W > 0
    for it in range(iterations):
        disp = np.zeros_like(pos)
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((delta ** 2).sum(axis=2)) + 1e-9
        rep = (k * k) / dist ** 2
        np.fill_diagonal(rep, 0.0)
        disp += (delta * rep[:, :, None]).sum(axis=1)
        att = (dist / k) * W
        np.fill_diagonal(att, 0.0)
        disp -= (delta * att[:, :, None]).sum(axis=1)
        temp = 0.1 * (1.0 - it / iterations) + 1e-3
        length = np.sqrt((disp ** 2).sum(axis=1)) + 1e-12
        pos += disp * (temp / length)[:, None]
        pos -= pos.mean(axis=0)
        scale = np.sqrt((pos ** 2).sum(axis=1)).mean() + 1e-12
        pos /= scale
    return pos


def spectral_layout(W: np.ndarray):
    """归一化 Laplacian 的 2 个最小非零特征向量作为初始/校验布局。"""
    W = np.asarray(W, float)
    d = W.sum(axis=1)
    dinv = 1.0 / np.sqrt(np.maximum(d, 1e-12))
    L = np.eye(W.shape[0]) - (W * np.outer(dinv, dinv))
    vals, vecs = np.linalg.eigh(L)
    return vecs[:, 1:3], vals


# ---------------------------------------------------------------- 阈值表/OAV
def compound_meta() -> pd.DataFrame:
    """所有 231 列（+其余）化合物的 origin_paper/unit/off_flavors/threshold_mean。"""
    th = C.load_sensory_thresholds()
    d = th[["field_name_R", "chemical_name", "origin_paper", "unit", "off_flavors",
            "threshold_mean", "threshold_median", "aging", "calibrated"]].copy()
    d["field"] = d["field_name_R"].astype(str).str.strip()
    d = d.drop_duplicates("field").set_index("field")
    return d


def oav_stats() -> pd.DataFrame:
    """每个化合物的 OAV 汇总（仅 43 个有阈值者）；由 C.oav_long() 计算。"""
    long = C.oav_long()
    if long.empty:
        return pd.DataFrame(columns=["compound", "mean_oav", "median_oav", "frac_oav_gt1", "n"])
    g = long.groupby("compound")["oav"]
    out = pd.DataFrame({
        "mean_oav": g.mean(),
        "median_oav": g.median(),
        "frac_oav_gt1": g.apply(lambda s: float((s > 1).mean())),
        "n": g.size(),
    }).reset_index().rename(columns={"compound": "compound"})
    return out
