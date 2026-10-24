"""04 划分：按 beer 做 80/20 分层留出（stratify = tasting_category_fine, seed = 42）。

背景与口径：
  * 台账登记的官方划分是 `modeling_data register-split` 生成的 **SPLIT-0001**
    （data/splits/SPLIT-0001/{train,test,assignment}.csv，200/50，seed 42, rowIdMapping=positional）。
    该工具**没有 stratify 参数**，其随机抽样在 test 中恰好漏掉了 1 个风格类（West Flanders ale，7 样本）。
  * 本脚本生成**分层复核版**：StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)，
    保证 22 类在 test 中每类至少 1 个；写到 data/splits/{train,test,assignment}.csv，
    并逐 beer 与 SPLIT-0001 及 Lead 的 provisional 版比对，结果写 outputs/data/split_summary.json。
  * 两版都 200/50、互斥、并集 250；差异只在"哪些 beer 进 test"。

输出：
  data/splits/train.csv       200 × 235（features_log 的行子集，按 beer 排序）
  data/splits/test.csv        50 × 235
  data/splits/assignment.csv  250 × 3（beer, tasting_category_fine, split）
  data/splits/meta.json       划分参数与校验结果
  outputs/data/split_summary.json  与 SPLIT-0001 / provisional 的差异、各风格计数
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


TEST_FRACTION = 0.2
SEED = 42
CANONICAL = C.ROOT / "data" / "splits"
STRAT = CANONICAL / "stratified"
KEEP = ["beer", "beer_id", "tasting_category_fine", "style"]


def main():
    # 用 DATA-0002 主表（250×284 = 3 键 + 231 特征 + 50 目标）生成分层版 train/test，
    # 使分层稳健性文件与 SPLIT-0002 的 schema 一致（含 50 个目标列，可直接算 50 维指标）。
    # 注意：assignment（beer, tasting_category_fine, split）语义与内容不变。
    f = pd.read_csv(C.ROOT / "data" / "clean" / "model_table.csv")
    assert f["beer"].is_unique and f.shape == (250, 284), f.shape
    style = f["tasting_category_fine"].astype(str)

    # ---------------- 分层划分（确定性：sklearn StratifiedShuffleSplit + seed 42）
    sss = StratifiedShuffleSplit(n_splits=1, test_size=TEST_FRACTION, random_state=SEED)
    tr_idx, te_idx = next(sss.split(f, style))
    train = f.iloc[tr_idx].sort_values("beer").reset_index(drop=True)
    test = f.iloc[te_idx].sort_values("beer").reset_index(drop=True)
    assignment = pd.DataFrame({
        "beer": f["beer"].astype(int).values,
        "tasting_category_fine": style.values,
        "split": np.where(np.isin(np.arange(len(f)), te_idx), "test", "train"),
    }).sort_values("beer").reset_index(drop=True)

    # ---------------- 基本校验
    assert len(train) == 200 and len(test) == 50, (len(train), len(test))
    assert set(train["beer"]).isdisjoint(set(test["beer"])), "train/test 必须不相交"
    assert set(train["beer"]) | set(test["beer"]) == set(f["beer"]), "并集必须覆盖 250"
    assert len(assignment) == 250
    assert assignment["split"].value_counts().to_dict() == {"train": 200, "test": 50}

    # 每类至少 1 个进 test
    cnt_all = style.value_counts()
    cnt_test = test["tasting_category_fine"].value_counts()
    cnt_train = train["tasting_category_fine"].value_counts()
    missing_test = sorted(set(cnt_all.index) - set(cnt_test.index))
    assert not missing_test, f"test 缺类: {missing_test}"

    # ---------------- 与 Lead provisional 比对
    prov_path = CANONICAL / "assignment_lead_provisional.csv"
    prov = pd.read_csv(prov_path) if prov_path.exists() else None
    prov_cmp = {}
    if prov is not None:
        p = prov.set_index("beer")["split"].reindex(assignment["beer"].values)
        mine = assignment.set_index("beer")["split"]
        diff_beers = sorted(mine.index[(mine.values != p.values)].tolist())
        prov_cmp = {
            "path": "data/splits/assignment_lead_provisional.csv",
            "n_test_lead": int((p == "test").sum()),
            "test_sets_equal": set(p[p == "test"].index) == set(mine[mine == "test"].index),
            "n_differing_beers": len(diff_beers),
            "differing_beers": diff_beers,
        }

    # ---------------- 与台账官方 SPLIT-0001 比对
    off_path = CANONICAL / "SPLIT-0001" / "assignment.csv"
    off_cmp = {"path": "data/splits/SPLIT-0001/assignment.csv", "exists": off_path.exists()}
    if off_path.exists():
        off = pd.read_csv(off_path)
        assert "row_index" in off.columns, "官方 assignment 预期含 row_index 列"
        off_beer = f["beer"].astype(int).values[off["row_index"].astype(int).values]
        off_split = pd.Series(off["split"].values, index=off_beer)
        mine = assignment.set_index("beer")["split"]
        common = mine.index.intersection(off_split.index)
        a = mine.loc[common]
        b = off_split.reindex(common)
        diff_beers = sorted(a.index[(a.values != b.values)].tolist())
        off_split_style = f.set_index("beer")["tasting_category_fine"]
        off_test_styles = set(off_split_style.loc[off_split[off_split == "test"].index])
        all_styles = set(cnt_all.index)
        off_cmp.update({
            "n_test_official": int((off_split == "test").sum()),
            "test_sets_equal": set(mine[mine == "test"].index) == set(off_split[off_split == "test"].index),
            "n_differing_beers": len(diff_beers),
            "differing_beers": diff_beers,
            "n_test_styles_official": len(off_test_styles),
            "test_styles_missing_official": sorted(all_styles - off_test_styles),
            "official_is_stratified": len(off_test_styles) == len(all_styles),
        })

    # ---------------- 与 DATA-0002 上的 SPLIT-0002 比对（应 = SPLIT-0001，逐 beer 相同）
    def load_rowidx(p: Path) -> pd.Series:
        a = pd.read_csv(p)
        a["beer"] = f["beer"].astype(int).values[a["row_index"].astype(int).values]
        return a.set_index("beer")["split"]

    sp2_path = CANONICAL / "SPLIT-0002" / "assignment.csv"
    sp2_cmp = {"path": "data/splits/SPLIT-0002/assignment.csv", "exists": sp2_path.exists()}
    if sp2_path.exists():
        s2 = load_rowidx(sp2_path)
        mine2 = assignment.set_index("beer")["split"].reindex(s2.index)
        s1 = load_rowidx(off_path) if off_path.exists() else None
        sp2_cmp.update({
            "n_test": int((s2 == "test").sum()),
            "assignment_sha256": sha256(sp2_path),
            "identical_to_SPLIT-0001": bool(s1 is not None and
                                            (s1.reindex(s2.index).values == s2.values).all()),
            "n_differing_beers_vs_SPLIT-0001": (int((s1.reindex(s2.index).values != s2.values).sum())
                                                if s1 is not None else None),
            "n_differing_beers_vs_stratified": int((s2.values != mine2.values).sum()),
            "note": "SPLIT-0002 建在 DATA-0002（250×284 含 50 目标）上；因数据行序不变且同为 seed42 位置划分，"
                    "其 assignment 与 SPLIT-0001 逐 beer 完全相同（sha 亦相同）。",
        })

    # ---------------- 落盘（分层稳健性版固定落在 data/splits/stratified/，不占用裸名）
    STRAT.mkdir(parents=True, exist_ok=True)
    train.to_csv(STRAT / "train.csv", index=False, encoding="utf-8")
    test.to_csv(STRAT / "test.csv", index=False, encoding="utf-8")
    assignment.to_csv(STRAT / "assignment.csv", index=False, encoding="utf-8")

    class_counts = pd.DataFrame({
        "style": cnt_all.index,
        "n_total": cnt_all.values,
        "n_train": [int(cnt_train.get(s, 0)) for s in cnt_all.index],
        "n_test": [int(cnt_test.get(s, 0)) for s in cnt_all.index],
    }).sort_values(["n_total", "style"], ascending=[False, True]).reset_index(drop=True)

    meta = {
        "method": "stratified-random-holdout",
        "stratify": "tasting_category_fine",
        "testFraction": TEST_FRACTION,
        "seed": SEED,
        "rows": 250, "train": len(train), "test": len(test),
        "columns": int(f.shape[1]),
        "schema": "DATA-0002 model_table 全列（3 键 + 231 特征 + 50 目标）；train/test 与 SPLIT-0002 同 schema",
        "disjoint": True, "coverage": 250,
        "n_styles": int(len(cnt_all)),
        "min_class": {"style": str(cnt_all.idxmin()), "n": int(cnt_all.min())},
        "every_class_in_test": bool(len(missing_test) == 0),
        "role": "稳健性复核（robustness），非主评估口径",
        "files": {"train": "data/splits/stratified/train.csv", "test": "data/splits/stratified/test.csv",
                  "assignment": "data/splits/stratified/assignment.csv"},
        "authoritative_ledger_split": "SPLIT-0001（data/splits/SPLIT-0001/assignment.csv，由 modeling_data register-split 生成；主评估口径）",
    }
    (STRAT / "meta.json").write_text(
        pd.Series(meta).to_json(force_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "generated_by": "src/04_split.py",
        "canonical": meta,
        "class_counts": class_counts.to_dict(orient="records"),
        "vs_lead_provisional": prov_cmp,
        "vs_official_SPLIT-0001": off_cmp,
        "vs_SPLIT-0002": sp2_cmp,
        "conclusion": (
            "主评估口径 = 台账 SPLIT-0001 / SPLIT-0002（同一划分，建在 DATA-0001 与 DATA-0002 上，"
            "assignment sha256 相同 = 4a032d28…；未分层，test 缺 West Flanders ale）；"
            "分层稳健性版（22/22 类进 test，与 Lead provisional 逐 beer 一致）落在 data/splits/stratified/，"
            + f"与主划分 test 集差异 {off_cmp.get('n_differing_beers', 'NA')} 个 beer。"
            + "modelers 只准用这两条路径，不得自造第三版。"
        ),
    }
    C.write_json(summary, "outputs/data/split_summary.json")

    print("== stratified split (seed 42) ==")
    print(f"train={len(train)} test={len(test)} styles={len(cnt_all)} "
          f"every_class_in_test={meta['every_class_in_test']} min_class={meta['min_class']}")
    print("\n== class counts (total / train / test) ==")
    print(class_counts.to_string(index=False))
    print("\n== vs lead provisional ==", {k: v for k, v in prov_cmp.items() if k != "differing_beers"})
    print("\n== vs official SPLIT-0001 ==", {k: v for k, v in off_cmp.items() if k != "differing_beers"})
    print("\nconclusion:", summary["conclusion"])


if __name__ == "__main__":
    main()
