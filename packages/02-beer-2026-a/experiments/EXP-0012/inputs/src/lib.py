"""beer-2026-a 共享数据层。

纪律（写进本文件，所有脚本共用）：
  * 唯一题面 = problem/2026年MathorCup大数据挑战赛-赛道A初赛.md；PDF 只作存档，不被任何脚本读取。
  * 附件一律经 data/raw/imported/ 的**登记副本**读取（sha256 已入台账）。
  * 主键：跨表只按 beer（1..250）连接；4.csv/7.csv 的 beer_id 被浮点截断（250 行仅 96 个不同值），
    禁止用作键。
  * 目标维度：50 列，固定来自 analysis/sensory/targetcolumns.csv（只作字段口径参考，不抄结论）。
  * 2.csv 是**实测 Spearman**；5/6/7 是 4/1/7 的派生，不是独立外部数据。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "imported"
CLEAN = ROOT / "data" / "clean"
PROC = ROOT / "data" / "processed"
SPLITS = ROOT / "data" / "splits"
OUT = ROOT / "outputs"
FIG = ROOT / "figures"
REPORT = ROOT / "report"

for _d in (CLEAN, PROC, SPLITS, OUT, FIG, REPORT):
    _d.mkdir(parents=True, exist_ok=True)

# 登记副本（sha256 见 state/ledger.json 的 imports 段）
FILES = {
    "1.csv": RAW / "419849227a02e0c7-1.csv",
    "2.csv": RAW / "415709ac10f2f730-2.csv",
    "3.xlsx": RAW / "fe4dcabd48431e6d-3.xlsx",
    "4.csv": RAW / "43a7b38682ed81ce-4.csv",
    "5.csv": RAW / "c512eed108de6f98-5.csv",
    "6.csv": RAW / "a55004fb0390299a-6.csv",
    "7.csv": RAW / "2083138df46640e2-7.csv",
    "8.xlsx": RAW / "f2316766792111d9-8.xlsx",
    "数据说明.txt": RAW / "40813e273e081ae0-数据说明.txt",
}

TARGETCOL_CSV = ROOT / "analysis" / "sensory" / "targetcolumns.csv"

SEED = 20261024
TEST_FRACTION = 0.2


def load_targets_table() -> pd.DataFrame:
    t = pd.read_csv(TARGETCOL_CSV)
    assert t["col_4csv"].is_unique and len(t) == 50, t.shape
    return t


def load_4() -> pd.DataFrame:
    return pd.read_csv(FILES["4.csv"])


def load_1() -> pd.DataFrame:
    return pd.read_csv(FILES["1.csv"])


def load_7() -> pd.DataFrame:
    return pd.read_csv(FILES["7.csv"])


def load_corr(path_key: str) -> pd.DataFrame:
    return pd.read_csv(FILES[path_key], index_col=0)


def xlsx_sheet(key: str, sheet: str) -> pd.DataFrame:
    return pd.read_excel(FILES[key], sheet_name=sheet)


KEEP = ["beer", "beer_id", "tasting_category_fine"]


def feature_columns() -> list[str]:
    """1.csv 的 231 个化合物/理化特征列（按 1.csv 列序，去掉 3 个键列）。"""
    cols = list(load_1().columns)
    return [c for c in cols if c not in KEEP]


def target_columns() -> list[str]:
    """4.csv 的 50 个目标列，顺按 targetcolumns.csv 的 order_4csv。"""
    t = load_targets_table().sort_values("order_4csv")
    return t["col_4csv"].tolist()


def write_json(obj, rel: str | Path) -> Path:
    p = ROOT / rel if not str(rel).startswith("/") else Path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return p


def write_csv(df: pd.DataFrame, rel: str | Path) -> Path:
    p = ROOT / rel if not str(rel).startswith("/") else Path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, encoding="utf-8")
    return p


def assignment_path(split_id: str) -> Path:
    """台账 register-split 的落盘约定：data/splits/<SPLITID>/assignment.csv。"""
    return SPLITS / split_id / "assignment.csv"


def load_assignment(split_id: str):
    """返回 (assignment DataFrame, train_beers, test_beers)。

    优先用 split 工具落盘的 train.csv/test.csv（它们含真实 beer 列，最可靠）；
    assignment.csv 的 row_index 是**数据集文件行序**，不等于 1.csv 的 beer 序。
    """
    d = SPLITS / split_id
    trp, tep, ap = d / "train.csv", d / "test.csv", d / "assignment.csv"
    assert ap.exists(), f"missing split assignment: {ap}"
    a = pd.read_csv(ap)
    if trp.exists() and tep.exists() and "beer" in pd.read_csv(trp, nrows=1).columns:
        tr = np.sort(pd.read_csv(trp, usecols=["beer"])["beer"].astype(int).to_numpy())
        te = np.sort(pd.read_csv(tep, usecols=["beer"])["beer"].astype(int).to_numpy())
    else:
        order = load_1()["beer"].to_numpy()
        a["beer"] = order[a["row_index"].astype(int).to_numpy()]
        tr = np.sort(a.loc[a["split"] == "train", "beer"].to_numpy())
        te = np.sort(a.loc[a["split"] == "test", "beer"].to_numpy())
    assert len(set(tr) & set(te)) == 0
    return a, tr, te


# ---------------------------------------------------------------- 字段清单（来自 profile）
def profile_columns(profile_json: str | Path) -> list[dict]:
    p = Path(profile_json)
    if not p.is_absolute():
        p = ROOT / p
    d = json.loads(p.read_text(encoding="utf-8"))
    cols = d.get("columnStats") or d.get("columns")
    if not isinstance(cols, list):
        return []
    return cols


def scale_map() -> dict[str, dict]:
    p = ROOT / "outputs" / "audit" / "scale_identification.csv"
    if not p.exists():
        return {}
    d = pd.read_csv(p)
    out = {}
    for _, r in d.iterrows():
        basis = r.get("basis")
        out[str(r["compound"])] = {
            "verdict": str(r["verdict"]),
            "basis": basis if isinstance(basis, str) else "",
            "zero_floor": bool(r.get("zero_floor_encoded", False)),
        }
    return out


def build_fields(columns: list[str], profile_paths: list[str], descriptions: dict[str, str],
                 units: dict[str, str] | None = None) -> list[dict]:
    """按 profile 的真实列类型生成字段清单；description/unit 由调用方按列给出。"""
    meta: dict[str, dict] = {}
    for pp in profile_paths:
        for c in profile_columns(pp):
            meta.setdefault(c["name"], c)
    units = units or {}
    out = []
    for name in columns:
        m = meta.get(name, {})
        dt = m.get("dtype") or "numeric"
        typ = "categorical" if dt == "categorical" else "number"
        out.append({
            "name": name,
            "type": typ,
            "unit": units.get(name) or ("n/a" if typ == "categorical" else "dimensionless"),
            "description": descriptions.get(name) or f"{name}（{typ}；来源见清理脚本）",
            "missingRatio": m.get("missingRatio"),
        })
    return out
