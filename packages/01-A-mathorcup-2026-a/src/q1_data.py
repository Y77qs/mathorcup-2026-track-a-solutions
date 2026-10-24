"""Q1 共享层：数据装载、折内（fold-fitted）预处理、特征块、重复分层折、分级标定。

边界（与 problem/questions.yaml Q1 constraints 一致）：
  * 特征只来自 1.csv 的 231 列（+ 5 个聚合列本身就在 1.csv 中，做包含/排除消融）；
  * 目标只来自 4.csv 的 50 维；5/6/7.csv 与 8.xlsx 的 GBM importance/SHAP 一律不进入特征；
  * 任何插补/截尾(winsorize)/标准化/特征筛选都只在传入的训练折上 fit，验证折只 transform。

坐标系：1.csv 为**混合尺度**表 —— 37 列经 8.xlsx 标定验证为 log10(浓度)，33 列为线性浓度，
161 列无标定可核（取值跨 4~10 个数量级）。因此本模块提供两种尺度协调：
  harmonize='none'        : 直接用原值（协议字面版）
  harmonize='log10_linear': 仅对 33 个已验证线性列取 log10（零/负值按 LOD/2 下限替换），
                            与其余已是 log10 尺度的列对齐。
截尾 winsorize(1%/99%) 是混合尺度 + 重尾下的关键一步（见 q1_models.py 的预处理对照）。
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
import common as C  # noqa: E402

OUT_Q1 = ROOT / "outputs" / "q1"
FIG = ROOT / "figures"

TARGET_DIMS = C.TARGET_DIMS
FEATURES = C.feature_columns()          # 231 个，顺序即 1.csv 列序
AGG_FEATURES = C.AGG_FEATURES            # 5 个化合物聚合列
N_DIMS = len(TARGET_DIMS)

SPLIT_DIR = ROOT / "data" / "splits"

# ---------------------------------------------------------------- 尺度判定（来自 01_audit/02_scale 的实测产物）
def _scale_lists():
    p = ROOT / "outputs" / "audit" / "scale_identification.csv"
    d = pd.read_csv(p)
    log10 = [c for c in d.loc[d.scale_verdict == "log10", "compound"] if c in FEATURES]
    linear = [c for c in d.loc[d.scale_verdict == "linear", "compound"] if c in FEATURES]
    unver = [c for c in d.loc[d.scale_verdict == "unverified", "compound"] if c in FEATURES]
    return log10, linear, unver


LOG10_COLS, LINEAR_COLS, UNVERIFIED_COLS = _scale_lists()

# 缺失：73 格 / 9 列（实测，见 problem/statement.md C11）
MISSING_COLS = ["amyl.acetate", "aroma_hops_sum", "methylpyrazine", "X2.3.butanedione",
                "X3.methylbutanal", "ethyl.nicotinate", "ethyl.isobutyrate", "furfural",
                "phenylacetaldehyde"]

# 化学族（8.xlsx "Sensory thresholds" 的 origin_paper，逐列映射；仅用其分组语义，不用任何浓度）
FAMILY_ORDER = ["Hops", "Yeast", "Malt", "Wild flora", "Spices", "Others", "Internal standard solution"]


def dataset_table() -> pd.DataFrame | None:
    """runner 上下文里的登记数据集（DATA-0002 = data/clean/model_table.csv，250×284）；否则 None。"""
    import os
    p = os.environ.get("MODELING_DATA_FILE")
    if p and Path(p).exists():
        d = pd.read_csv(p)
        if set(TARGET_DIMS) <= set(d.columns) and set(FEATURES) <= set(d.columns):
            return d.set_index("beer")
    return None


def load_all() -> dict:
    """返回 Q1 的全部输入（按 beer 对齐，beer 1..250）。

    runner 内优先用登记数据集（DATA-0002 model_table）的特征与目标，保证与台账 sha256 同源；
    进程外回退到 data/raw/1.csv + 4.csv。
    """
    ds = dataset_table()
    if ds is not None:
        X = ds[FEATURES].astype(float)
        Y = ds[TARGET_DIMS].astype(float)
        cats = ds["tasting_category_fine"].astype(str)
        return {"X": X, "Y": Y, "cats": cats, "beer": X.index.to_numpy(),
                "feature_family": feature_family_map(), "source": "dataset"}
    feats = C.load_features().set_index("beer")
    tg = C.load_targets().set_index("beer")
    tg = tg.loc[feats.index]
    X = feats[FEATURES].astype(float)
    Y = tg[TARGET_DIMS].astype(float)
    cats = tg["tasting_category_fine"].astype(str)
    return {
        "X": X, "Y": Y, "cats": cats,
        "beer": feats.index.to_numpy(),
        "feature_family": feature_family_map(),
    }


def feature_family_map() -> dict:
    """1.csv 列名 -> origin_paper 化学族（缺失则 'Others'）。"""
    th = C.load_sensory_thresholds()
    m = {}
    for _, r in th.iterrows():
        f = str(r["field_name_R"]).strip()
        if f in FEATURES and f not in m:
            op = r["origin_paper"]
            m[f] = op if isinstance(op, str) and op.strip() else "Others"
    for f in FEATURES:
        m.setdefault(f, "Others")
    return m


# ---------------------------------------------------------------- 训练/测试划分
# 主评估 = 台账 SPLIT-0001（assignment.csv 的 row_index 是 1.csv 的 **0-based 行号**
#          -> beer = 1.csv['beer'][row_index]；注意 1.csv 的 beer 列本身不是 1..250 顺序排列）
# 稳健性复核 = 分层划分 data/splits/stratified/assignment.csv（列 beer,split）
SPLIT_PRIMARY_DIR = ROOT / "data" / "splits" / "SPLIT-0001"
SPLIT_STRAT_DIR = ROOT / "data" / "splits" / "stratified"


def _beer_from_row_index(row_index) -> np.ndarray:
    f = pd.read_csv(ROOT / "data" / "raw" / "1.csv", usecols=["beer"])
    return f["beer"].to_numpy()[np.asarray(row_index, dtype=int)]


def load_split(kind: str = "primary", train_beers=None, test_beers=None):
    """返回 (train_beers, test_beers)（beer 值，已排序）。

    kind='primary'    : 台账 SPLIT-0001（未分层；test 覆盖 21/22 风格）
    kind='stratified' : 分层复核划分（22/22 类进 test）
    runner 环境变量 MODELING_TRAIN_FILE/MODELING_TEST_FILE 存在时优先使用（正式实验路径）。
    """
    import os
    env_tr, env_te = os.environ.get("MODELING_TRAIN_FILE"), os.environ.get("MODELING_TEST_FILE")
    if train_beers is not None and test_beers is not None:
        tr, te = np.asarray(train_beers), np.asarray(test_beers)
    elif env_tr and env_te and Path(env_tr).exists() and Path(env_te).exists():
        tr = pd.read_csv(env_tr, usecols=["beer"])["beer"].to_numpy()
        te = pd.read_csv(env_te, usecols=["beer"])["beer"].to_numpy()
    elif kind == "primary":
        a = pd.read_csv(SPLIT_PRIMARY_DIR / "assignment.csv")
        tr = _beer_from_row_index(a.loc[a["split"] == "train", "row_index"])
        te = _beer_from_row_index(a.loc[a["split"] == "test", "row_index"])
    else:
        a = pd.read_csv(SPLIT_STRAT_DIR / "assignment.csv")
        tr = a.loc[a["split"] == "train", "beer"].to_numpy()
        te = a.loc[a["split"] == "test", "beer"].to_numpy()
    tr = np.sort(np.asarray(tr, dtype=int))
    te = np.sort(np.asarray(te, dtype=int))
    assert len(set(tr) & set(te)) == 0, "train/test overlap"
    assert len(tr) + len(te) == 250, "split does not cover 250 beers"
    return tr, te


def feature_block(block: str, oav: pd.DataFrame = None):
    """特征块定义（消融用）。返回 (列名列表, 额外特征 DataFrame 或 None)。"""
    if block == "raw231":
        return list(FEATURES), None
    if block == "noagg":
        return [c for c in FEATURES if c not in AGG_FEATURES], None
    if block == "log10only":
        return list(LOG10_COLS), None
    if block == "oav43":
        # 43 个 OAV = 标定浓度 / 8.xlsx 物理阈值；等价于对 1.csv 对应列的单调变换。
        # 只在训练折上 log1p（OAV 重尾），验证折同样用训练折的变换（log1p 无参数，安全）。
        o = oav if oav is not None else C.oav_table()
        o = o.copy()
        o.columns = ["oav_" + c for c in o.columns]
        o = o.reindex(range(1, 251))
        o.index.name = "beer"
        return list(FEATURES), o
    raise ValueError(f"unknown block {block!r}")


# ---------------------------------------------------------------- 折内预处理
class Prep:
    """折内预处理：可选尺度协调 -> 中位数插补 -> winsorize -> 标准化 -> 缺失指示。

    所有统计量在 fit() 时只用训练折；transform() 只套用。内部用 numpy 运算以支撑
    15 折 × 内层选参的高频调用（每折约 27 次 pipeline 拟合）。
    """

    def __init__(self, harmonize="log10_linear", winsor_q=0.01, indicator=True, clip_z=None,
                 impute="median", eps=1e-12):
        """clip_z: 标准化后 |z|<=clip_z 裁剪（近零方差列的数值稳定防护，与 winsorize 互补）。
        impute: median | knn(k=5) | iterative（后者在训练折上 fit，验证折只 transform）。"""
        self.harmonize = harmonize
        self.winsor_q = winsor_q
        self.indicator = indicator
        self.clip_z = clip_z
        self.impute = impute
        self.eps = eps

    # -- 尺度协调（无监督、逐列）--
    def _harmonize_np(self, A, fit=False):
        """仅对 33 个已验证线性列取 log10（LOD/2 下限），与已是 log10 尺度的列对齐。"""
        if self.harmonize != "log10_linear":
            return A
        A = A.copy()
        if fit:
            self.floor_ = np.empty(len(self.lin_idx_))
            for k, j in enumerate(self.lin_idx_):
                col = A[:, j][np.isfinite(A[:, j])]
                pos = col[col > 0]
                self.floor_[k] = float(pos.min()) * 0.5 if len(pos) else 1e-9
        A[:, self.lin_idx_] = np.log10(np.maximum(A[:, self.lin_idx_], self.floor_[None, :]))
        return A

    def _as_matrix(self, X: pd.DataFrame) -> np.ndarray:
        if not hasattr(self, "columns_"):
            self.columns_ = list(X.columns)
            self.lin_idx_ = np.array([self.columns_.index(c) for c in LINEAR_COLS if c in self.columns_],
                                     dtype=int)
            self.lin_idx_ = self.lin_idx_ if len(self.lin_idx_) else np.array([], dtype=int)
        return X[self.columns_].to_numpy(dtype=float)

    def _impute_fill(self, A, fit=False):
        if self.impute == "median":
            return np.where(np.isnan(A), self.median_[None, :], A)
        if fit:
            if self.impute == "knn":
                from sklearn.impute import KNNImputer
                self.imputer_ = KNNImputer(n_neighbors=5).fit(A)
            elif self.impute == "iterative":
                from sklearn.experimental import enable_iterative_imputer  # noqa: F401
                from sklearn.impute import IterativeImputer
                self.imputer_ = IterativeImputer(max_iter=10, random_state=0).fit(A)
            else:
                raise ValueError(self.impute)
        return self.imputer_.transform(A)

    def fit(self, X: pd.DataFrame, y=None):
        A = self._harmonize_np(self._as_matrix(X), fit=True)
        with np.errstate(all="ignore"):
            self.na_mask_cols_ = np.where(np.isnan(A).any(axis=0))[0]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.median_ = np.nanmedian(A, axis=0)
            self.median_ = np.where(np.isnan(self.median_), 0.0, self.median_)
        A = self._impute_fill(A, fit=True)
        if self.winsor_q:
            lo = np.quantile(A, self.winsor_q, axis=0)
            hi = np.quantile(A, 1 - self.winsor_q, axis=0)
        else:
            lo, hi = np.full(A.shape[1], -np.inf), np.full(A.shape[1], np.inf)
        A = np.clip(A, lo[None, :], hi[None, :])
        self.lo_, self.hi_ = lo, hi
        self.mean_ = A.mean(axis=0)
        sd = A.std(axis=0, ddof=0)
        self.sd_ = np.where(sd > 0, sd, 1.0)
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        import warnings as _w
        A = self._harmonize_np(self._as_matrix(X), fit=False)
        ind = A[:, self.na_mask_cols_].copy()
        ind = np.isnan(ind).astype(float)
        A = self._impute_fill(A)
        A = np.clip(A, self.lo_[None, :], self.hi_[None, :])
        Z = (A - self.mean_[None, :]) / self.sd_[None, :]
        if self.clip_z:
            Z = np.clip(Z, -float(self.clip_z), float(self.clip_z))
        if self.indicator and ind.shape[1]:
            Z = np.hstack([Z, ind])
        return Z

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)


class GroupAgg:
    """化学族聚合：对标准化后的矩阵按 origin_paper 组做 (mean, max, 检出比例)。"""

    def __init__(self, family_map, families=FAMILY_ORDER):
        self.family_map = family_map
        self.families = families

    def fit(self, X=None, y=None):
        return self

    def transform(self, Z, columns):
        idx = {c: i for i, c in enumerate(columns)}
        blocks = []
        for fam in self.families:
            cols = [c for c in columns if self.family_map.get(c, "Others") == fam]
            if not cols:
                blocks.append(np.zeros((Z.shape[0], 3)))
                continue
            A = Z[:, [idx[c] for c in cols]]
            blocks.append(np.column_stack([
                A.mean(1),
                A.max(1),
                (np.abs(A) > 1.0).mean(1),
            ]))
        return np.hstack(blocks)


def make_prep(prep_spec: dict):
    return Prep(**prep_spec)


# ---------------------------------------------------------------- 重复分层折
def cv_folds(cats: pd.Series, n_splits=5, n_repeats=3, seed=42):
    """重复分层 K 折：返回 [(repeat, fold, train_pos, val_pos), ...]（位置索引，针对 200 训练行）。"""
    from sklearn.model_selection import RepeatedStratifiedKFold
    rskf = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    out = []
    y = np.asarray(cats)
    for k, (a, b) in enumerate(rskf.split(np.zeros(len(y)), y)):
        out.append((k // n_splits, k % n_splits, a, b))
    return out


# ---------------------------------------------------------------- 0–6 分级标定（四套口径）
# 参数表由 supervisor 侧 SCRIPT-0005 用**训练 200** 估得并落盘；Q1 直接读表，不自行重估，
# 以保证论文数字、台账与 reviewer 独立复核使用同一组 (a, s)。
GRADE_CAL_CSV = ROOT / "outputs" / "protocol" / "grade_calibration_SPLIT-0001.csv"
GRADE_CAL_CSV_STRAT = ROOT / "outputs" / "protocol" / "grade_calibration_stratified.csv"
POLICIES = ["P1_oav_anchor", "P2_range", "P3_quantile", "P4_sigma"]
POLICY_PRIMARY = C.Z_GRADE_CALIBRATION["primary"]


def load_grade_params(kind: str = "primary") -> dict:
    """读 supervisor 侧登记的标定参数表 -> {dim: {policy: params}}。

    主分割（SPLIT-0001）与分层复核各有一张表，**不自行重估**，保证论文/台账/复核同参。
    """
    path = GRADE_CAL_CSV if kind == "primary" else GRADE_CAL_CSV_STRAT
    df = pd.read_csv(path)
    out = {}
    for _, r in df.iterrows():
        out[str(r["dim"])] = {
            "P1_oav_anchor": {"a": float(r["P1_a"]), "s": float(r["P1_s"])},
            "P2_range": {"lo": float(r["P2_lo"]), "hi": float(r["P2_hi"])},
            "P3_quantile": {},
            "P4_sigma": {"S": float(r["P4_S"])},
        }
    return out


def grade_matrix(V, policy: str, params: dict, dims=None) -> np.ndarray:
    """逐维套用 C.grade_policy（同一维的真值与预测用同一组参数）。"""
    V = np.asarray(V, float)
    dims = list(dims or TARGET_DIMS)
    G = np.zeros(V.shape, dtype=int)
    for j, d in enumerate(dims):
        G[:, j] = C.grade_policy(V[:, j], policy, params.get(d, {}))
    return G


def calibration_report(y_true_v, y_pred_v, policy=POLICY_PRIMARY, params=None) -> dict:
    """连续性预测 -> 分级后的一致性报告（QWK、分级 MAE、分布、单调性检验）。

    注意：真实等级**未知**（4.csv 只是连续标准化值）。这里的 y_true_v 是被同一标定规则
    映射后的"参照等级"，因此 QWK/分级 MAE 只能读作**标定敏感性**，不是"真实 0–6 分上的准确率"。
    """
    params = params if params is not None else load_grade_params()
    yt = np.asarray(y_true_v, float)
    yp = np.asarray(y_pred_v, float)
    gt = grade_matrix(yt, policy, params)
    gp = grade_matrix(yp, policy, params)
    mono_ok, order_agree = True, []
    for j in range(yt.shape[1]):
        o = np.argsort(yp[:, j], kind="stable")
        d = np.diff(gp[o, j])
        if (d < 0).any():
            mono_ok = False
        order_agree.append(float((d >= 0).mean()) if len(d) else 1.0)
    per_dim_qwk = []
    for j in range(yt.shape[1]):
        per_dim_qwk.append(C.qwk(gt[:, j], gp[:, j]))
    return {
        "policy": policy,
        "qwk": float(C.qwk(gt.ravel(), gp.ravel())),
        "qwk_per_dim_mean": float(np.nanmean(per_dim_qwk)),
        "grade_mae": float(np.abs(gt - gp).mean()),
        "grade_exact": float((gt == gp).mean()),
        "grade_within1": float((np.abs(gt - gp) <= 1).mean()),
        "monotone_within_dim": bool(mono_ok),
        "grade_order_agreement": float(np.mean(order_agree)),
        "dist_true": np.bincount(gt.ravel(), minlength=7).tolist(),
        "dist_pred": np.bincount(gp.ravel(), minlength=7).tolist(),
        "n_dims_anchored_used": int(sum(1 for d, p in params.items()
                                        if policy == "P1_oav_anchor" and d in TARGET_DIMS)),
    }


def confusion(y_true_v, y_pred_v, policy=POLICY_PRIMARY, params=None):
    params = params if params is not None else load_grade_params()
    gt = grade_matrix(np.asarray(y_true_v, float), policy, params).ravel()
    gp = grade_matrix(np.asarray(y_pred_v, float), policy, params).ravel()
    M = np.zeros((7, 7), int)
    for a, b in zip(gt, gp):
        M[a, b] += 1
    return pd.DataFrame(M, index=[f"true_{i}" for i in range(7)],
                        columns=[f"pred_{i}" for i in range(7)])


# ---------------------------------------------------------------- 指标
def z_metrics(y_true, y_pred) -> dict:
    yt = np.asarray(y_true, float)
    yp = np.asarray(y_pred, float)
    r2v = C.r2(yt, yp)
    mav = C.mae(yt, yp)
    return {
        "r2_mean": float(np.nanmean(r2v)),
        "r2_median": float(np.nanmedian(r2v)),
        "n_dims_r2_negative": int(np.sum(np.asarray(r2v) < 0)),
        "mae_mean": float(np.nanmean(mav)),
        "spearman_mean": float(np.nanmean(C.spearman_per_col(yt, yp))),
        "r2_per_dim": np.asarray(r2v),
        "mae_per_dim": np.asarray(mav),
    }


def ensure_dirs():
    (OUT_Q1 / "oof").mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- 模型 bundle（Q1 -> Q3 前向映射）
def load_bundle(path):
    """载入 Q1 锁定模型 bundle（joblib 压缩或 pickle 均可）。"""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    try:
        import joblib
        return joblib.load(p)
    except Exception:
        import pickle
        with open(p, "rb") as f:
            return pickle.load(f)


def bundle_predict(bundle, X_df: pd.DataFrame) -> np.ndarray:
    """用 Q1 锁定模型把化合物谱映射为 50 维连续强度 ẑ。

    X_df 必须含 bundle['features'] 的 231 列（顺序任意，按名字取）；缺失值允许（折内插补参数已固化在 bundle 里）。
    返回 (n, 50) 数组，列序 = bundle['target_dims']。
    """
    import q1_models as M  # noqa: F401  （bundle 里的 Predictor 类在此模块）
    pred = bundle["predictor"]
    missing = [c for c in bundle["features"] if c not in X_df.columns]
    if missing:
        raise ValueError("bundle_predict 缺少特征列: %s" % missing[:5])
    return pred.predict(X_df[bundle["features"]])

