"""mathorcup-2026-a 共享契约层。

所有脚本只通过本模块读取数据、构造特征/目标、计算指标，以保证：
  * 特征与目标的边界唯一（防止 4/5/6/7.csv 泄漏进 Q1/Q3 特征）；
  * 分级标定规则唯一且可审计（problem 中登记的分级标定策略）；
  * 指标定义唯一（R²/MAE/Spearman/QWK）。
不在此处做任何"按分数挑模型"的动作。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
SPLITS = ROOT / "data" / "splits"
OUT = ROOT / "outputs"
FIG = ROOT / "figures"

for _d in (CLEAN, SPLITS, OUT, FIG):
    _d.mkdir(parents=True, exist_ok=True)

RNG_SEED = 42

# ---------------------------------------------------------------- 键与分组
KEYS = ["beer", "beer_id", "tasting_category_fine"]
BEER_ID_MASKED = ["4.csv", "7.csv"]  # 这两张表的 beer_id 被脱敏，只能按 beer 连接

AROMA_DIMS = [
    "A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn",
    "A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody",
    "A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity",
]
FLAVOUR_DIMS = [
    "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn",
    "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody",
    "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity",
]
PALATE_DIMS = [
    "acidity", "bitternes", "sweetness", "X4vg", "diacetyl", "dms", "metallic",
    "stale_hops", "t2n", "orange", "coriander", "clove", "lactic", "acetic",
    "barnyard", "alcohol", "aftertaste", "body", "co2", "overall",
]
TARGET_DIMS = AROMA_DIMS + FLAVOUR_DIMS + PALATE_DIMS

# 5 类缺陷（题面点名）：感官维度名 -> 对应 1.csv 化合物列（可多列）
DEFECT_DIMS = {
    "dms": ["DMS"],
    "diacetyl": ["X2.3.butanedione"],
    "X4vg": ["X4VG"],
    "t2n": ["X.E..2.nonenal"],
    "stale_hops": ["X.E..2.nonenal", "X3.methyl.2.butenal", "X5.methylfurfural", "furfural"],
}
DEFECT_LABELS = ["DMS", "Diacetyl", "4VG", "trans-2-nonenal", "Stale hops"]

# 5 个由化合物聚合而成的派生列
AGG_FEATURES = ["kcalperc", "acids_sum", "esters_sum", "aroma_hops_sum", "sulfur_sum"]

Z_GRADE_CALIBRATION = {
    "name": "oav-anchored(primary) + range/quantile/sigma(sensitivity)",
    "measured_facts": {
        "centered": True,
        "max_abs_col_mean": 0.0628,
        "unit_variance": False,
        "col_sd_min": 0.3697,
        "col_sd_max": 0.8585,
        "col_sd_median": 0.5536,
        "n_unique_per_col": [106, 250],
        "conclusion": (
            "4.csv 只做了中心化 + 一个未知的（全局或逐列）缩放，不是逐列单位方差标准化；"
            "因此'grade 3 锚定 z=0'与'1 个 z 单位 = 1 个等级'都不能由 4.csv 单独辨识。"
            "本项目改用外部物理锚点（8.xlsx 气味阈值 ⇒ OAV=1 为恰可察觉，对应等级 1）来定 location，"
            "并用 range/quantile/sigma 三套替代标定做敏感性。"
        ),
    },
    "policies": {
        "P1_oav_anchor": "g = clip(floor((v - a_d)/s_d + 0.5), 0, 6)，(a_d, s_d) 由 v_d ~ log10(OAV_driver) 稳健回归估得；"
                          "a_d 锚定 OAV=1（恰可察觉=等级 1），s_d 为每个数量级 OAV 的等级宽度",
        "P2_range": "g = clip(floor(6*(v - min_d)/(max_d - min_d) + 0.5), 0, 6)（假设 250 款样覆盖该维全量程）",
        "P3_quantile": "g = clip(7 等分位数分箱, 0, 6)（假设该维等级分布近似均匀）",
        "P4_sigma": "g = clip(floor(v/S + 3.5), 0, 6)，S=1.0（旧口径，保留以便对比）",
    },
    "primary": "P1_oav_anchor",
    "sensitivity": ["P2_range", "P3_quantile", "P4_sigma"],
}

# 预注册的"维度 -> 主驱化合物"表（用于 OAV 物理锚定；写在看结果之前）。
# 依据：8.xlsx Sensory thresholds 的 origin_paper/类群 + 风味化学常识 + 6.csv 的独立先验。
DRIVER_REGISTRY = {
    "dms": ["DMS"],
    "diacetyl": ["X2.3.butanedione"],
    "X4vg": ["X4VG"],
    "t2n": ["X.E..2.nonenal"],          # 8.xlsx 无阈值 → 无法锚定，仅保留供参考
    "metallic": ["iron"],
    "alcohol": ["ethanol..v.v."],
    "bitternes": ["bitterness"],
    "sweetness": ["GFS"],
    "lactic": ["lactic_acid.mg.L."],
    "acetic": ["acetic_acid.g.L."],
    "acidity": ["lactic_acid.mg.L.", "acetic_acid.g.L."],
    "ester_all_aroma": ["ethyl_acetate", "ethyl_hexanoate", "ethyl_octanoate", "isopentyl_acetate",
                        "ethyl_decanoate", "ethyl_butyrate", "isobutyl_acetate", "phenethyl_acetate"],
    "A_esters_all": ["ethyl_acetate", "ethyl_hexanoate", "ethyl_octanoate", "isopentyl_acetate",
                     "ethyl_decanoate", "ethyl_butyrate", "isobutyl_acetate", "phenethyl_acetate"],
    "F_esters_all": ["ethyl_acetate", "ethyl_hexanoate", "ethyl_octanoate", "isopentyl_acetate",
                     "ethyl_decanoate", "ethyl_butyrate", "isobutyl_acetate", "phenethyl_acetate"],
    "A_esters_ethac": ["ethyl_acetate"],
    "F_esters_ethac": ["ethyl_acetate"],
    "A_esters_isoaa": ["isopentyl_acetate"],
    "F_esters_isoaa": ["isopentyl_acetate"],
    "A_hops_citrus": ["linalool", "geraniol", "citronellol", "X1.alpha.terpineol"],
    "F_hops_citrus": ["linalool", "geraniol", "citronellol", "X1.alpha.terpineol"],
    "orange": ["linalool", "geraniol", "citronellol"],
    "A_hops_noble": ["alpha.humulene", "E.caryophyllene"],
    "F_hops_noble": ["alpha.humulene", "E.caryophyllene"],
    "A_hops_woody": ["alpha.humulene", "E.caryophyllene"],
    "F_hops_woody": ["alpha.humulene", "E.caryophyllene"],
    "A_hops_all": ["linalool", "geraniol", "citronellol", "alpha.humulene", "E.caryophyllene",
                   "X1.alpha.terpineol"],
    "F_hops_all": ["linalool", "geraniol", "citronellol", "alpha.humulene", "E.caryophyllene",
                   "X1.alpha.terpineol"],
    "sulphury": ["DMS", "DES", "H2S", "SO2.mg.L."],
}


def corr2_mapping() -> pd.DataFrame:
    """1.csv 特征列 -> 2.csv 行列名 的映射（reviewer 实测：2.csv 用的是化学全名，
    与 1.csv 列名按名字几乎对不上；但 2.csv 第 i 行/列与 1.csv 第 i 个特征列**位置一一对应**）。

    这里用 8.xlsx thresholds 的 chemical_name_short -> field_name_R 做名字映射，
    并用"位置一致性"交叉验证；返回 col_1csv / name_2csv / via / positional_agree。
    """
    th = load_sensory_thresholds()
    short2field = {}
    for _, r in th.iterrows():
        f = str(r["field_name_R"]).strip()
        c = str(r["chemical_name_short"]).strip()
        if f and c and c.lower() != "nan":
            short2field.setdefault(c.lower(), []).append(f)
    corr = load_corr_compound()
    feats = feature_columns()
    names = list(corr.index)
    rows = []
    for i, col in enumerate(feats):
        cand = None
        via = None
        for short, fields in short2field.items():
            if col in fields:
                # 用 short 去 2.csv 名字里找（大小写/去空格）
                for nm in names:
                    if str(nm).strip().lower() == short:
                        cand, via = nm, "threshold:chemical_name_short"
                        break
            if cand:
                break
        pos = names[i] if i < len(names) else None
        rows.append({
            "col_1csv": col, "name_2csv": cand or pos,
            "via": via or "positional(index)",
            "positional_name": pos,
            "positional_agrees_with_name": (cand is not None and pos is not None
                                            and str(cand).strip().lower() == str(pos).strip().lower()),
        })
    return pd.DataFrame(rows)


def oav_driver_matrix(driver: list) -> pd.DataFrame:
    """按 DRIVER_REGISTRY 的一个驱动集合，返回 beer × 1 的"感知强度代理" = Σ OAV（可比量纲由阈值归一化）。"""
    oav = oav_table()
    cols = [c for c in driver if c in oav.columns]
    if not cols:
        return pd.DataFrame()
    s = oav[cols].fillna(0.0).sum(axis=1)
    return pd.DataFrame({"beer": s.index.astype(int), "sum_oav": s.values})



# ---------------------------------------------------------------- 读数据
def read_csv_raw(name: str) -> pd.DataFrame:
    """严格读取原表：beer_id 用 int64，避免 4/7.csv 的 float 化。"""
    p = RAW / name
    if name in ("4.csv", "7.csv"):
        # beer_id 已被脱敏（尾数归零），仍按 int64 读，但连接一律用 beer
        return pd.read_csv(p, dtype={"beer_id": "int64"})
    return pd.read_csv(p)


def load_features() -> pd.DataFrame:
    """1.csv：250 x (3 键 + 231 化合物/理化)。"""
    return read_csv_raw("1.csv")


def feature_columns() -> list[str]:
    d = read_csv_raw("1.csv")
    return [c for c in d.columns if c not in KEYS]


def load_targets() -> pd.DataFrame:
    """4.csv：250 x (3 键 + 50 感官维度)，按 beer 对齐到 1.csv。"""
    t = read_csv_raw("4.csv")
    f = read_csv_raw("1.csv")[["beer", "beer_id"]]
    m = t.merge(f, on="beer", how="left", suffixes=("", "_f"))
    m["beer_id"] = m["beer_id_f"].astype("int64")
    m = m.drop(columns=["beer_id_f"])
    return m[["beer", "beer_id", "tasting_category_fine"] + TARGET_DIMS]


def load_sensory_thresholds() -> pd.DataFrame:
    return pd.read_excel(RAW / "8.xlsx", sheet_name="Sensory thresholds")


def load_calibrated_chemicals() -> pd.DataFrame:
    return pd.read_excel(RAW / "8.xlsx", sheet_name="Calibrated chemical dataset")


def load_sensory_names() -> pd.DataFrame:
    return pd.read_excel(RAW / "8.xlsx", sheet_name="Sensory names")


def load_corr_compound() -> pd.DataFrame:
    return pd.read_csv(RAW / "2.csv", index_col=0)


def load_corr_cross() -> pd.DataFrame:
    return pd.read_csv(RAW / "6.csv", index_col=0)


def load_ratebeer() -> pd.DataFrame:
    return read_csv_raw("7.csv")


# ---------------------------------------------------------------- 浓度/阈值
def log10_to_conc(v: np.ndarray) -> np.ndarray:
    """1.csv 的丰度列为 log10(原始浓度)，已用 8.xlsx 标定表验证。"""
    return np.power(10.0, np.asarray(v, dtype=float))


def threshold_table() -> pd.DataFrame:
    """有阈值的化合物表，键 `field` = threshold 表的 field_name_R（R 规范化名），
    这正是 1.csv / 8.xlsx Calibrated chemical dataset 的列名风格。

    注意：threshold 表的 `field_name_python` 列实际是人读名（含空格与括号，如
    "2,3-butanedione"），与数据列名不匹配；必须用 `field_name_R`
    （如 "X2.3.butanedione"）才能 join 上。该错位由 01_audit 与 02_scale 记录。
    """
    t = load_sensory_thresholds()
    t = t[t["threshold_mean"].notna()].copy()
    t["field"] = t["field_name_R"].astype(str).str.strip()
    t["label"] = t["field_name_python"].astype(str).str.strip()
    return t.drop_duplicates("field")


def oav_table(features: pd.DataFrame = None) -> pd.DataFrame:
    """OAV = 浓度 / 阈值，只用 8.xlsx 的物理阈值与作者标定浓度。

    1.csv 是**混合尺度**表（37 列 log10、其余线性，详见 outputs/audit/scale_identification.csv），
    因此这里不自行猜测底数：浓度一律取自 8.xlsx "Calibrated chemical dataset"（作者提供的统一浓度表，
    250×70）。只用物理阈值，不引入任何感官目标信息，对 Q1/Q3 均可安全使用。

    返回 250 行（以 beer 为索引）的 OAV 表；未同时具备"标定浓度 + 阈值"的化合物不出现。
    """
    cal = load_calibrated_chemicals()
    th = threshold_table().set_index("field")
    rows = []
    for field in th.index:
        if field not in cal.columns:
            continue
        thr = float(th.loc[field, "threshold_mean"])
        if not np.isfinite(thr) or thr <= 0:
            continue
        conc = pd.to_numeric(cal[field], errors="coerce").astype(float)
        rows.append(pd.DataFrame({
            "beer": cal["beer"].astype(int).values,
            "compound": [field] * len(cal),
            "unit": str(th.loc[field, "unit"]),
            "threshold_mean": thr,
            "conc": conc.values,
            "oav": (conc / thr).values,
        }))
    if not rows:
        return pd.DataFrame()
    long = pd.concat(rows, ignore_index=True)
    wide = long.pivot(index="beer", columns="compound", values="oav")
    return wide


def oav_long() -> pd.DataFrame:
    """OAV 长表：beer / compound / unit / threshold_mean / conc / oav。"""
    cal = load_calibrated_chemicals()
    th = threshold_table().set_index("field")
    out = []
    for field in th.index:
        if field not in cal.columns:
            continue
        thr = float(th.loc[field, "threshold_mean"])
        if not np.isfinite(thr) or thr <= 0:
            continue
        out.append(pd.DataFrame({
            "beer": cal["beer"].astype(int).values,
            "compound": field,
            "unit": str(th.loc[field, "unit"]),
            "origin_paper": str(th.loc[field, "origin_paper"]),
            "off_flavors": str(th.loc[field, "off_flavors"]),
            "threshold_mean": thr,
            "conc": pd.to_numeric(cal[field], errors="coerce").astype(float).values,
        }))
    if not out:
        return pd.DataFrame()
    d = pd.concat(out, ignore_index=True)
    d["oav"] = d["conc"] / d["threshold_mean"]
    return d


# ---------------------------------------------------------------- 分级标定
def z_to_grade(z, width: float = None) -> np.ndarray:
    """标准化感官值 -> 0..6 整数等级（P4_sigma 旧口径，保留以便对比）。"""
    s = 1.0 if width is None else float(width)
    g = np.floor(np.asarray(z, dtype=float) / s + 3.5)
    return np.clip(g, 0, 6).astype(int)


# ------------------------------------------------- 0-6 分级标定（四套策略）
def grade_range(v, lo=None, hi=None) -> np.ndarray:
    """P2：按该维观测极差线性铺到 0..6（假设样本覆盖全量程）。"""
    v = np.asarray(v, dtype=float)
    lo = np.nanmin(v) if lo is None else float(lo)
    hi = np.nanmax(v) if hi is None else float(hi)
    if not np.isfinite(hi - lo) or hi <= lo:
        return np.full(v.shape, 3, dtype=int)
    g = np.floor(6.0 * (v - lo) / (hi - lo) + 0.5)
    return np.clip(g, 0, 6).astype(int)


def grade_quantile(v) -> np.ndarray:
    """P3：按 1/7 分位切分成 7 档（假设该维等级近似均匀分布）。"""
    v = np.asarray(v, dtype=float)
    ok = np.isfinite(v)
    out = np.full(v.shape, 3, dtype=int)
    if ok.sum() < 14:
        return out
    qs = np.nanquantile(v, np.linspace(0, 1, 8)[1:-1])
    out[ok] = np.searchsorted(qs, v[ok], side="right")
    return np.clip(out, 0, 6).astype(int)


def grade_anchored(v, a: float, s: float) -> np.ndarray:
    """P1：物理锚定。OAV=1（恰可察觉）对应等级 1；每 1 个数量级 OAV 增加 1 个等级。

    参数 (a, s) 由 `fit_oav_anchor` 在训练集上估得：v ≈ a + s·log10(ΣOAV)。
    a 是 location（v 在 OAV=1 处的取值），s 是 scale（v 每数量级的宽度）。
    """
    v = np.asarray(v, dtype=float)
    if not np.isfinite(s) or s == 0:
        return np.full(v.shape, 3, dtype=int)
    g = np.floor(1.0 + (v - a) / s + 0.5)
    return np.clip(g, 0, 6).astype(int)


def fit_oav_anchor(targets: pd.DataFrame, dims=None, min_rho: float = 0.30) -> pd.DataFrame:
    """在**训练集**上为每个维度估计 OAV 锚定参数 (a, s)。

    约定（预注册，写进论文）：
      * ΣOAV = 该维主驱化合物（DRIVER_REGISTRY）的 OAV 之和（阈值归一化后的可比强度）；
      * 感知强度按 Fechner/Stevens 用 log10(ΣOAV) 线性化；
      * OAV = 1（恰可察觉）↔ 等级 1；每 1 个数量级 ↔ +1 个等级；
      * 仅当 Spearman(v, log10 ΣOAV) ≥ min_rho 且斜率 > 0 时接受该维锚定，否则标记 unanchored，
        用已锚定维度的 (a, s) 中位数迁移（transfer）。
    """
    from scipy.stats import spearmanr, theilslopes

    dims = list(dims or TARGET_DIMS)
    oav = oav_table()
    rows = []
    for d in dims:
        drivers = DRIVER_REGISTRY.get(d, [])
        cols = [c for c in drivers if c in oav.columns]
        rec = {"dim": d, "drivers": ",".join(drivers) if drivers else "",
               "n_drivers_available": len(cols)}
        if not cols:
            rec.update({"status": "no_driver", "a": np.nan, "s": np.nan, "rho": np.nan})
            rows.append(rec)
            continue
        so = oav[cols].fillna(0.0).sum(axis=1)
        L = np.log10(np.maximum(so.values, 1e-6))
        tv = targets.set_index("beer")[d].astype(float)
        common = [b for b in oav.index if b in tv.index]
        if len(common) < 30:
            rec.update({"status": "too_few", "a": np.nan, "s": np.nan, "rho": np.nan})
            rows.append(rec)
            continue
        pos = {b: i for i, b in enumerate(oav.index)}
        v = tv.loc[common].values
        Lc = L[[pos[b] for b in common]]
        ok = np.isfinite(v) & np.isfinite(Lc)
        if ok.sum() < 30:
            rec.update({"status": "too_few", "a": np.nan, "s": np.nan, "rho": np.nan})
            rows.append(rec)
            continue
        rho = float(spearmanr(v[ok], Lc[ok]).statistic)
        slope, intercept, _, _ = theilslopes(v[ok], Lc[ok])
        accepted = bool(rho >= min_rho and slope > 0)
        rec.update({"status": "anchored" if accepted else "weak",
                    "a": float(intercept), "s": float(slope), "rho": rho,
                    "n": int(ok.sum())})
        rows.append(rec)
    out = pd.DataFrame(rows)
    good = out[out["status"] == "anchored"]
    if len(good):
        a_med, s_med = float(good["a"].median()), float(good["s"].median())
        m = out["status"].isin(["weak", "no_driver", "too_few"])
        out.loc[m, "a"] = a_med
        out.loc[m, "s"] = s_med
        out.loc[m, "status"] = out.loc[m, "status"] + "+transfer"
    return out


def grade_policy(v, policy: str, params: dict) -> np.ndarray:
    """统一入口：按策略名把连续值映射为 0..6 等级。"""
    if policy == "P1_oav_anchor":
        return grade_anchored(v, params.get("a", 0.0), params.get("s", 1.0))
    if policy == "P2_range":
        return grade_range(v, params.get("lo"), params.get("hi"))
    if policy == "P3_quantile":
        return grade_quantile(v)
    if policy == "P4_sigma":
        return z_to_grade(v, params.get("S", 1.0))
    raise ValueError(f"unknown policy: {policy}")



# ---------------------------------------------------------------- 指标
def r2(y_true, y_pred) -> np.ndarray:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = ((y_true - y_pred) ** 2).sum(axis=0)
    ss_tot = ((y_true - y_true.mean(axis=0)) ** 2).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 1.0 - ss_res / ss_tot
    return out


def mae(y_true, y_pred) -> np.ndarray:
    return np.abs(np.asarray(y_true, float) - np.asarray(y_pred, float)).mean(axis=0)


def spearman_per_col(y_true, y_pred) -> np.ndarray:
    from scipy.stats import spearmanr
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    out = np.full(y_true.shape[1], np.nan)
    for j in range(y_true.shape[1]):
        r = spearmanr(y_true[:, j], y_pred[:, j]).statistic
        out[j] = r
    return out


def qwk(y_true_g, y_pred_g) -> float:
    """二次加权 kappa（分级一致性），9 级混淆实现不依赖 sklearn 版本细节。"""
    yt = np.asarray(y_true_g, int).ravel()
    yp = np.asarray(y_pred_g, int).ravel()
    k = 7
    obs = np.zeros((k, k), float)
    for a, b in zip(yt, yp):
        obs[a, b] += 1
    hist_t = np.bincount(yt, minlength=k).astype(float)
    hist_p = np.bincount(yp, minlength=k).astype(float)
    exp = np.outer(hist_t, hist_p) / max(len(yt), 1)
    w = (np.arange(k)[:, None] - np.arange(k)[None, :]) ** 2 / (k - 1) ** 2
    num = (w * obs).sum()
    den = (w * exp).sum()
    return float(1.0 - num / den) if den > 0 else float("nan")


def summarize(y_true, y_pred, prefix: str = "") -> dict:
    r2v = r2(y_true, y_pred)
    return {
        f"{prefix}r2_mean": float(np.nanmean(r2v)),
        f"{prefix}r2_median": float(np.nanmedian(r2v)),
        f"{prefix}mae_mean": float(np.nanmean(mae(y_true, y_pred))),
        f"{prefix}spearman_mean": float(np.nanmean(spearman_per_col(y_true, y_pred))),
        f"{prefix}n_dims": int(np.asarray(y_true).shape[1]),
    }


# ---------------------------------------------------------------- IO
def write_json(obj, rel: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return p


def write_csv(df: pd.DataFrame, rel: str, index: bool = False):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=index, encoding="utf-8")
    return p


def setup_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplcache"))
    plt.rcParams.update({
        "figure.dpi": 130,
        "savefig.dpi": 160,
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.unicode_minus": False,
        "font.family": ["DejaVu Sans"],
    })
    return plt
