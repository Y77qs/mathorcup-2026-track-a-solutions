"""Q3 共享工具：数据/划分装载、标准化与支撑域、缺陷口径、分布距离、bootstrap。

只读依赖 `src/common.py`（共享契约），不修改任何共享文件。
所有随机性一律走 `np.random.default_rng(seed)`，以便同 seed 逐值复现。
"""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import common as C  # noqa: E402

PROJECT = C.ROOT
OUT_Q3 = PROJECT / "outputs" / "q3"
FIG_Q3 = PROJECT / "figures"
OUT_Q3.mkdir(parents=True, exist_ok=True)

SEED = 42
REQUIRED_STYLES = ["Tripel", "Kriek", "Lambic"]
SMALL_N_STYLES = ["Kriek", "Lambic", "Faro"]

FEATURES = C.feature_columns()          # 1.csv 的 231 个化合物/理化列（唯一生成空间）
N_FEATURES = len(FEATURES)

# 五类缺陷（题面点名）。每类 -> 化合物列；has_threshold 表示 8.xlsx 是否有绝对阈值。
DEFECT_SPECS = [
    {"category": "DMS", "compounds": ["DMS"], "has_threshold": True},
    {"category": "Diacetyl", "compounds": ["X2.3.butanedione"], "has_threshold": True},
    {"category": "4VG", "compounds": ["X4VG"], "has_threshold": True},
    {"category": "trans-2-nonenal", "compounds": ["X.E..2.nonenal"], "has_threshold": False},
    {"category": "Stale hops",
     "compounds": ["X.E..2.nonenal", "X3.methyl.2.butenal", "X5.methylfurfural", "furfural"],
     "has_threshold": False},
]
# 迁移硬约束实际作用的列集合（去重）
DEFECT_COMPOUNDS = sorted({c for d in DEFECT_SPECS for c in d["compounds"]})

# 补充：这些缺陷化合物在 8.xlsx 中确实带阈值（只作补充信息，不改变类别判定口径）
SUPPLEMENTARY_THRESHOLDS = {"furfural"}


# ---------------------------------------------------------------- 数据装载
def load_style_table() -> pd.DataFrame:
    """beer / style / 231 列（1.csv 原样）。"""
    f = C.load_features()
    f = f.rename(columns={"tasting_category_fine": "style"})
    return f[["beer", "style"] + FEATURES].copy()


def load_scale_verdicts() -> dict[str, str]:
    """每列的尺度判定（来自 01/02 审计产物 scale_identification.csv）。"""
    p = PROJECT / "outputs" / "audit" / "scale_identification.csv"
    si = pd.read_csv(p).set_index("compound")
    return {c: str(si.loc[c, "scale_verdict"]) if c in si.index else "unverified"
            for c in FEATURES}


def load_split(name: str = "primary") -> dict:
    """读取训练/留出划分。

    主分割 = `SPLIT-0001`（data/splits/SPLIT-0001/assignment.csv，列 row_index,split；
    row_index 是 1.csv 的 0-based 行号，beer = 1.csv['beer'][row_index]）。
    分层复算分割 = `stratified`（data/splits/stratified/assignment.csv，列 beer,...,split）。
    两者都要求 train/test 不交、并集覆盖 250 个 beer。
    """
    tab = load_style_table()
    beer_all = tab["beer"].astype(int).values
    if name == "primary":
        cand = [PROJECT / "data" / "splits" / "SPLIT-0002" / "assignment.csv",
                PROJECT / "data" / "splits" / "SPLIT-0001" / "assignment.csv"]
        path = next((p for p in cand if p.exists()), cand[-1])
        a = pd.read_csv(path)
        if "row_index" in a.columns:
            beer = beer_all[a["row_index"].astype(int).values]
        else:
            beer = a["beer"].astype(int).values
        role = a["split"].astype(str).str.strip().str.lower().values
    elif name == "stratified":
        path = PROJECT / "data" / "splits" / "stratified" / "assignment.csv"
        a = pd.read_csv(path)
        beer = a["beer"].astype(int).values
        role = a["split"].astype(str).str.strip().str.lower().values
    else:
        raise ValueError(f"unknown split name: {name}")
    train_beer = np.sort(beer[role == "train"])
    test_beer = np.sort(beer[role == "test"])
    if len(train_beer) == 0 or len(test_beer) == 0:
        raise ValueError(f"split {name} has empty train or test side")
    inter = np.intersect1d(train_beer, test_beer)
    if len(inter):
        raise ValueError(f"split {name} train/test overlap: {inter[:5]}")
    if len(np.union1d(train_beer, test_beer)) != len(beer_all):
        raise ValueError(f"split {name} does not cover all 250 beers")
    return {
        "name": name,
        "path": str(path.relative_to(PROJECT)),
        "sha256": sha256(path),
        "train_beer": train_beer,
        "test_beer": test_beer,
        "n_train": int(len(train_beer)),
        "n_test": int(len(test_beer)),
    }


def split_meta(split: dict) -> dict:
    """可 JSON 化的划分摘要（不落 beer 数组，数组另存 assignment.csv）。"""
    out = {k: split[k] for k in ("name", "path", "sha256", "n_train", "n_test") if k in split}
    out["n_styles_train"] = None
    if "train_beer" in split:
        tab = load_style_table().set_index("beer")
        out["n_styles_train"] = int(tab.loc[split["train_beer"], "style"].nunique())
        out["n_styles_test"] = int(tab.loc[split["test_beer"], "style"].nunique())
        out["test_missing_styles"] = sorted(set(tab["style"]) -
                                           set(tab.loc[split["test_beer"], "style"]))
    return out


def style_counts(beer_all, style_all, beer_sub) -> dict:
    s = pd.Series(style_all, index=beer_all)
    return {k: int(v) for k, v in s.loc[beer_sub].value_counts().sort_index().items()}


# ---------------------------------------------------------------- 预处理
class Preprocessor:
    """训练集内拟合：逐列中位数插补 + 逐列单调变换 + z 标准化 + 训练观测支撑域。

    逐列变换（只用训练行统计，规则固定、可复现）：
      * 审计判定为 log10 的列：identity（已是对数尺度）；
      * 其余列若训练值全部 >= 0 且 **偏度 > 2.0**：log1p（重尾浓度列在乘法尺度上建模）；
      * 其它：identity。
    这条规则来自一个实测缺陷：若对重尾线性浓度列（如 X2.3.butanedione 偏度 6.5、max/median=420）
    直接 z 标准化，条件高斯的对称采样会让"生成中位数"远高于真值中位数（z 空间的 0 对应原始均值
    而不是原始中位数），生成谱在缺陷项上系统性偏高。log1p 只改尺度不改信息，反变换精确可逆。

    - `scale_verdicts` 决定非负约束施加在哪一列（物理浓度列 clamp >= 0；log10 列的原始值
      可负，对应浓度 < 1，其非负性由 10^v > 0 自动满足；log1p 列的原始值恒 >= 0）。
    """

    SKEW_CUT = 2.0

    def __init__(self, feature_names: list[str], scale_verdicts: dict[str, str]):
        self.features = list(feature_names)
        self.verdicts = dict(scale_verdicts)
        self.median = None
        self.mean = None
        self.std = None
        self.lower = None
        self.upper = None
        self.linear_cols = None
        self.kinds = None          # 'identity' | 'log1p'
        self.skew = None

    def fit(self, X_train: pd.DataFrame):
        from scipy.stats import skew as _skew

        X = X_train[self.features].astype(float)
        A = X.values
        kinds, sk = [], []
        for j, c in enumerate(self.features):
            v = A[:, j]
            v = v[np.isfinite(v)]
            s = float(_skew(v)) if len(v) > 3 and np.std(v) > 0 else 0.0
            sk.append(s)
            if self.verdicts.get(c) == "log10":
                kinds.append("identity")
            elif len(v) and np.min(v) >= 0 and np.max(v) > 0 and s > self.SKEW_CUT:
                kinds.append("log1p")
            else:
                kinds.append("identity")
        self.kinds = np.array(kinds)
        self.skew = np.array(sk)
        self.median = X.median(axis=0).fillna(0.0).values
        Xi = X.fillna(pd.Series(self.median, index=self.features)).values
        T = self._fwd(Xi)
        self.mean = np.nanmean(T, axis=0)
        sd = np.nanstd(T, axis=0, ddof=1)
        self.std = np.where(sd > 1e-8, sd, 1.0)
        self.lower = np.nanmin(A, axis=0)
        self.upper = np.nanmax(A, axis=0)
        # 物理浓度列（linear verified）必须非负；审计确认这些列观测 min >= 0
        self.linear_cols = np.array([self.verdicts.get(c) == "linear" for c in self.features])
        self.lower = np.where(self.linear_cols, np.maximum(self.lower, 0.0), self.lower)
        self.lower = np.minimum(self.lower, self.upper)
        return self

    # -- 单调变换（逐列）
    def _fwd(self, A: np.ndarray) -> np.ndarray:
        out = np.array(A, dtype=float, copy=True)
        lg = self.kinds == "log1p"
        if lg.any():
            out[:, lg] = np.log1p(np.maximum(out[:, lg], 0.0))
        return out

    def _bwd(self, T: np.ndarray) -> np.ndarray:
        out = np.array(T, dtype=float, copy=True)
        lg = self.kinds == "log1p"
        if lg.any():
            out[:, lg] = np.expm1(out[:, lg])
        return out

    # -- 变换
    def impute(self, X: pd.DataFrame) -> np.ndarray:
        A = X[self.features].astype(float).values
        miss = np.isnan(A)
        if miss.any():
            A = np.where(miss, self.median[None, :], A)
        return A

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        T = self._fwd(self.impute(X))
        return (T - self.mean[None, :]) / self.std[None, :]

    def inverse(self, Z: np.ndarray) -> np.ndarray:
        return self._bwd(Z * self.std[None, :] + self.mean[None, :])

    # -- 变换空间的公开接口（迁移优化用）
    def forward_raw(self, A: np.ndarray) -> np.ndarray:
        return self._fwd(np.atleast_2d(np.asarray(A, float)))

    def backward_raw(self, T: np.ndarray) -> np.ndarray:
        return self._bwd(np.atleast_2d(np.asarray(T, float)))

    def defect_index(self, compounds: list[str]) -> np.ndarray:
        return np.array([self.features.index(c) for c in compounds], dtype=int)

    # -- 标准化空间 <-> 变换空间（迁移优化用）
    def tau_to_z(self, tau: np.ndarray) -> np.ndarray:
        return (np.asarray(tau, float) - self.mean[None, :]) / self.std[None, :]

    def tau_bounds(self, lower: np.ndarray = None, upper: np.ndarray = None):
        lo = self.lower if lower is None else lower
        up = self.upper if upper is None else upper
        return self._fwd(lo[None, :])[0], self._fwd(up[None, :])[0]

    # -- 支撑域（原始尺度）
    def clip(self, A: np.ndarray) -> np.ndarray:
        return np.clip(A, self.lower[None, :], self.upper[None, :])

    def support_violation(self, A: np.ndarray) -> np.ndarray:
        lo = np.minimum(A - self.lower[None, :], 0.0)
        hi = np.maximum(A - self.upper[None, :], 0.0)
        return np.abs(lo) + np.abs(hi)

    def to_frame(self, A: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(A, columns=self.features)

    def transform_table(self) -> pd.DataFrame:
        return pd.DataFrame({"compound": self.features, "scale_verdict": [
            self.verdicts.get(c) for c in self.features],
            "train_skew": self.skew, "transform": self.kinds,
            "train_min": self.lower, "train_max": self.upper})


def fit_preprocessor(style_tab: pd.DataFrame, train_beer: np.ndarray) -> Preprocessor:
    prep = Preprocessor(FEATURES, load_scale_verdicts())
    prep.fit(style_tab.set_index("beer").loc[train_beer])
    return prep


def train_matrix(style_tab: pd.DataFrame, beer: np.ndarray) -> pd.DataFrame:
    return style_tab.set_index("beer").loc[beer, FEATURES]


# ---------------------------------------------------------------- 浓度 / OAV
def concentration(x_raw: np.ndarray, compound: str, verdict: str) -> np.ndarray:
    """1.csv 特征尺度 -> 浓度（连续映射，不含删失语义）。

    log10 列：10^v；linear 列：v（原样）；unverified 列：v（单调代理，无阈值时仅用于不增判定）。
    """
    v = np.asarray(x_raw, dtype=float)
    if verdict == "log10":
        return np.power(10.0, v)
    return v.copy()


def threshold_map() -> dict:
    th = C.threshold_table().set_index("field")
    return {f: float(th.loc[f, "threshold_mean"]) for f in th.index if f in FEATURES}


def defect_compound_table() -> dict:
    """缺陷化合物的口径表：尺度、作者阈值、删失（calibrated==0 ⇔ 1.csv 取 LOD/2 代码）。

    口径依据（Lead 最终版 + 02_scale 审计）：
      * DMS    : log10 列，阈值 17.25 ug/L；calibrated 有 1 个 0（=LOD/2 代码）
      * X2.3.butanedione : **linear 列**（1.csv 值即 mg/L），阈值 0.29925 mg/L；calibrated 的 0 对应
                            1.csv 的真实缺失（不用 10^v）
      * X4VG   : log10 列，阈值 0.206333 mg/L；calibrated 的 0（168 行）= LOD/2 代码
      * X.E..2.nonenal / X3.methyl.2.butenal / X5.methylfurfural / furfural：无"Stale hops"类阈值
    删失规则：log10 列中 10^v <= (最小正浓度/2) 的格子，按作者标定表记为 0（非检出），
    生成值同样套用该规则（保留 LOD/2 删失语义）。
    """
    th = C.threshold_table().set_index("field")
    cal = C.load_calibrated_chemicals().set_index("beer")
    verdicts = load_scale_verdicts()
    out = {}
    for comp in DEFECT_COMPOUNDS:
        scale = verdicts.get(comp, "unverified")
        thr = float(th.loc[comp, "threshold_mean"]) if comp in th.index else None
        unit = str(th.loc[comp, "unit"]) if comp in th.index else None
        cens = None
        if scale == "log10" and comp in cal.columns:
            vals = pd.to_numeric(cal[comp], errors="coerce").astype(float)
            nz = int(np.nansum(vals == 0))
            pos = vals[vals > 0]
            if nz > 0 and len(pos) > 0:
                pos_min = float(np.nanmin(pos))
                cens = {
                    "kind": "LOD/2 -> 0 (author calibrated == 0)",
                    "cutoff_conc": pos_min / 2.0,
                    "floor_code_log10": float(np.log10(pos_min / 2.0)),
                    "n_censored_rows_in_calibrated": nz,
                }
        out[comp] = {"compound": comp, "scale": scale, "threshold": thr,
                     "unit": unit, "censoring": cens,
                     "has_author_threshold": thr is not None}
    return out


def conc_with_censoring(x_raw: np.ndarray, comp_info: dict) -> np.ndarray:
    """按作者标定口径把特征尺度映射为浓度，并保留 LOD/2 删失语义（<=cutoff 记 0）。"""
    v = np.asarray(x_raw, dtype=float)
    if comp_info["scale"] == "log10":
        conc = np.power(10.0, v)
        cens = comp_info.get("censoring")
        if cens:
            conc = np.where(conc <= cens["cutoff_conc"] * (1 + 1e-9), 0.0, conc)
        return conc
    return v.copy()


def oav_features(x_raw: np.ndarray, comp_info: dict) -> np.ndarray:
    if not comp_info.get("threshold"):
        return np.full(np.shape(x_raw), np.nan)
    return conc_with_censoring(x_raw, comp_info) / comp_info["threshold"]


# ---------------------------------------------------------------- 分布距离
def pairwise_sq_dists(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    d2 = (A * A).sum(1)[:, None] + (B * B).sum(1)[None, :] - 2.0 * A @ B.T
    return np.maximum(d2, 0.0)


def energy_distance(X: np.ndarray, Y: np.ndarray) -> dict:
    """能量距离（z 空间）。返回平方统计量 ed2 = 2E||x-y|| - E||x-x'|| - E||y-y'||。"""
    X = np.asarray(X, float)
    Y = np.asarray(Y, float)
    n, m = len(X), len(Y)
    if n < 2 or m < 1:
        return {"ed2": float("nan"), "ed": float("nan"), "n_gen": n, "n_ref": m}
    dxy = np.sqrt(pairwise_sq_dists(X, Y)).mean()
    dxx = np.sqrt(pairwise_sq_dists(X, X)).mean()
    dyy = np.sqrt(pairwise_sq_dists(Y, Y)).mean() if m > 1 else 0.0
    ed2 = 2.0 * dxy - dxx - dyy
    return {"ed2": float(ed2), "ed": float(np.sqrt(max(ed2, 0.0))),
            "n_gen": int(n), "n_ref": int(m)}


def mmd_rbf(X: np.ndarray, Y: np.ndarray, bandwidth_sq: float = None) -> dict:
    """有偏 RBF-MMD^2（z 空间）；带宽取合并集平方距离中位数（可外部固定以保证可比）。"""
    X = np.asarray(X, float)
    Y = np.asarray(Y, float)
    Z = np.vstack([X, Y])
    if bandwidth_sq is None:
        d2 = pairwise_sq_dists(Z, Z)
        iu = np.triu_indices(len(Z), k=1)
        bandwidth_sq = float(np.median(d2[iu])) if len(iu[0]) else 1.0
    bandwidth_sq = max(bandwidth_sq, 1e-12)
    kxx = np.exp(-pairwise_sq_dists(X, X) / (2 * bandwidth_sq)).mean()
    kyy = np.exp(-pairwise_sq_dists(Y, Y) / (2 * bandwidth_sq)).mean()
    kxy = np.exp(-pairwise_sq_dists(X, Y) / (2 * bandwidth_sq)).mean()
    return {"mmd2": float(max(kxx + kyy - 2 * kxy, 0.0)),
            "bandwidth_sq": bandwidth_sq, "n_gen": len(X), "n_ref": len(Y)}


def median_bandwidth(style_tab: pd.DataFrame, prep: Preprocessor,
                     beer: np.ndarray, floor: float = 1e-6) -> float:
    """某风格（或合并训练样本）在 z 空间的经验带宽：平方距离中位数。"""
    Z = prep.transform(train_matrix(style_tab, beer))
    d2 = pairwise_sq_dists(Z, Z)
    iu = np.triu_indices(len(Z), k=1)
    if len(iu[0]) == 0:
        return floor
    return float(max(np.median(d2[iu]), floor))


# ---------------------------------------------------------------- bootstrap
def bootstrap_ci(x: np.ndarray, stat_fn, n_boot: int = 2000, seed: int = SEED,
                 alpha: float = 0.05) -> dict:
    rng = np.random.default_rng(seed)
    n = len(x)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        vals.append(stat_fn(x[idx]))
    vals = np.asarray(vals, float)
    lo, hi = np.nanquantile(vals, [alpha / 2, 1 - alpha / 2])
    return {"lo": float(lo), "hi": float(hi),
            "point": float(stat_fn(x)), "n_boot": int(n_boot)}


def bootstrap_mean_ci(X: np.ndarray, n_boot: int = 2000, seed: int = SEED) -> dict:
    """逐维均值的 95% bootstrap CI：返回区间宽度中位数与若干代表列（避免巨大 JSON）。"""
    def stat(A):
        return np.nanmean(A, axis=0)

    Bm = np.empty((n_boot, X.shape[1]))
    rng = np.random.default_rng(seed)
    for b in range(n_boot):
        Bm[b] = np.nanmean(X[rng.integers(0, len(X), len(X))], axis=0)
    lo = np.nanquantile(Bm, 0.025, axis=0)
    hi = np.nanquantile(Bm, 0.975, axis=0)
    full = (hi - lo) / (np.nanstd(X, axis=0) + 1e-12)
    return {
        "mean_ci_lo": lo, "mean_ci_hi": hi,
        "median_ci_width": float(np.median(hi - lo)),
        "median_ci_width_over_sd": float(np.median(full)),
        "point_mean": np.nanmean(X, axis=0),
    }


def bootstrap_cov_fro(X: np.ndarray, n_boot: int = 2000, seed: int = SEED) -> dict:
    """协方差矩阵 Frobenius 范数的 bootstrap CI（衡量协方差估计不确定性）。"""
    def stat(A):
        return float(np.linalg.norm(np.cov(A, rowvar=False), "fro"))

    vals = []
    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        vals.append(stat(X[rng.integers(0, len(X), len(X))]))
    vals = np.asarray(vals)
    return {"fro_lo": float(np.quantile(vals, 0.025)),
            "fro_hi": float(np.quantile(vals, 0.975)),
            "fro_point": float(stat(X)), "n_boot": int(n_boot)}


# ---------------------------------------------------------------- 风格 CV 折
def stratified_folds(y: np.ndarray, k: int = 5, seed: int = SEED) -> list[np.ndarray]:
    """按风格分层的手写 K 折（允许某类样本数 < k：round-robin 分配到不同折）。"""
    rng = np.random.default_rng(seed)
    fold_id = np.full(len(y), -1, dtype=int)
    for cls in np.unique(y):
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        for j, i in enumerate(idx):
            fold_id[i] = j % k
    folds = [np.where(fold_id == f)[0] for f in range(k)]
    return [f for f in folds if len(f) > 0]


# ---------------------------------------------------------------- IO / 台账
def write_json(obj, rel: str):
    return C.write_json(obj, rel)


def write_csv(df: pd.DataFrame, rel: str, index: bool = False):
    return C.write_csv(df, rel, index=index)


def rel(p: Path) -> str:
    return str(Path(p).resolve().relative_to(PROJECT))


def sha256(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dump_pickle(obj, rel_path: str):
    p = PROJECT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as fh:
        pickle.dump(obj, fh, protocol=4)
    return p


def load_pickle(rel_path: str):
    with open(PROJECT / rel_path, "rb") as fh:
        return pickle.load(fh)


# ---------------------------------------------------------------- 风格分类器
def classifier_candidates():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.decomposition import PCA

    def logreg_raw():
        return Pipeline([("clf", LogisticRegression(C=1.0, max_iter=3000))])

    def logreg_pca20():
        return Pipeline([("pca", PCA(n_components=20, random_state=SEED)),
                         ("clf", LogisticRegression(C=0.5, max_iter=3000))])

    def hgb():
        return HistGradientBoostingClassifier(max_iter=150, learning_rate=0.06,
                                              max_leaf_nodes=8, min_samples_leaf=3,
                                              l2_regularization=1.0,
                                              random_state=SEED)

    return {"logreg_raw": logreg_raw, "logreg_pca20": logreg_pca20, "hgb": hgb}


def style_classifier_cv(Z: np.ndarray, y: np.ndarray, k: int = 5,
                        seed: int = SEED) -> dict:
    """在训练集上 5 折 CV 比较 3 个分类器候选，返回每个候选的准确率/宏 F1/混淆矩阵。"""
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

    folds = stratified_folds(y, k=k, seed=seed)
    classes = np.unique(y)
    out = {}
    for name, factory in classifier_candidates().items():
        accs, f1s = [], []
        cm = np.zeros((len(classes), len(classes)), dtype=int)
        for f_test in folds:
            mask = np.ones(len(y), bool)
            mask[f_test] = False
            clf = factory()
            with np.errstate(all="ignore"):
                clf.fit(Z[mask], y[mask])
                pred = clf.predict(Z[f_test])
            accs.append(accuracy_score(y[f_test], pred))
            f1s.append(f1_score(y[f_test], pred, average="macro", zero_division=0))
            for t, p in zip(y[f_test], pred):
                cm[list(classes).index(t), list(classes).index(p)] += 1
        out[name] = {
            "cv_accuracy_mean": float(np.mean(accs)),
            "cv_accuracy_folds": [float(a) for a in accs],
            "cv_macro_f1_mean": float(np.mean(f1s)),
            "confusion_matrix": cm.tolist(),
            "classes": classes.tolist(),
        }
    best = max(out, key=lambda n: out[n]["cv_accuracy_mean"])
    return {"candidates": out, "selected": best, "n_train": int(len(y)), "folds": int(k),
            "fold_seed": seed}


def fit_style_classifier(Z: np.ndarray, y: np.ndarray, name: str):
    clf = classifier_candidates()[name]()
    with np.errstate(all="ignore"):
        clf.fit(Z, y)
    return clf


def clean_json(obj):
    """把 NaN/Inf/numpy 标量递归转成 JSON 安全值（runner 的 emit_output 拒绝非有限数）。"""
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [clean_json(v) for v in obj.tolist()]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    return obj


def load_json(rel_path: str, default=None):
    p = PROJECT / rel_path
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))
