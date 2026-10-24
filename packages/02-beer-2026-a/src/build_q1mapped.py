"""02 构建 DATA-Q1mapped：把 4.csv 的 50 个标准化目标映射为 **mapped grade ∈ [0,6]**。

口径（必须与论文一致）：
  * x = 6 * (z - zmin) / (zmax - zmin)，zmin/zmax **只用训练集估计**（不得用测试目标拟合）；
  * 端点假设：训练集最小值 => 0 分、最大值 => 6 分；超出训练范围的测试值按 [0,6] 截断并计数披露；
  * 这是 **mapped grade（transformed）**，不是原始 0–6 人工评分：
    原始 0–6 不可识别（3.xlsx 12 张评分卡是空白模板、summary 公式恒 0；4.csv 是未知缩放参数的标准值，
    clove 列 max=6.17>6）。论文必须写 "mapped grade, non-original 0–6"。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L

PHYSICO_DESC = {
    "pH": "1.csv pH 列；量程核对显示为 log10(pH)（推断；非 8.xlsx 标定实测）",
    "color.EBC.": "1.csv 色度列；量程核对显示为 log10(EBC)（推断）",
    "bitterness": "1.csv 苦度列；量程核对显示为 log10(IBU)（推断）",
    "ethanol..v.v.": "1.csv 酒精度列；量程核对显示为 log10(% v/v)（推断）",
    "CO2.PSI.": "1.csv 二氧化碳列；量程核对显示为 log10(PSI)（推断）",
}


DESC4 = {
    "beer": "样本主键（1..250）",
    "beer_id": "1.csv 的整数 beer_id（仅引用，不作连接键）",
    "tasting_category_fine": "风格标签，22 类",
}


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="SPLIT-0001",
                    help="用哪个 split 估计映射参数（默认 SPLIT-0001，seed=20261024，与 Q1 同 seed 同划分）")
    ap.add_argument("--split-file", default=None)
    args = ap.parse_args()

    src = L.CLEAN / "q2_raw.csv"
    df = pd.read_csv(src)
    t50 = L.target_columns()
    assert set(t50) <= set(df.columns), "q2_raw 必须已含 50 个原始目标列"

    if args.split_file:
        sp = pd.read_csv(args.split_file)
        if "row_index" in sp.columns:
            sp["beer"] = L.load_1()["beer"].to_numpy()[sp["row_index"].astype(int).to_numpy()]
        tr_beers = np.sort(sp.loc[sp["split"] == "train", "beer"].astype(int).to_numpy())
        split_ref = {"split_file": args.split_file, "sha256": sha(Path(args.split_file))}
    else:
        sp, tr_beers, te_beers = L.load_assignment(args.split)
        split_ref = {"split": args.split,
                     "assignment": str(L.assignment_path(args.split).relative_to(L.ROOT)),
                     "sha256": sha(L.assignment_path(args.split))}
    assert len(tr_beers) == 200, len(tr_beers)

    train = df[df["beer"].isin(tr_beers)].reset_index(drop=True)
    assert len(train) == 200, len(train)
    test = df[~df["beer"].isin(tr_beers)].reset_index(drop=True)
    params, mapped_rows, clip_stats = {}, {}, {}
    out = df.copy()
    for c in t50:
        zmin, zmax = float(train[c].min()), float(train[c].max())
        span = zmax - zmin
        params[c] = {"zmin_train": zmin, "zmax_train": zmax, "span": span}
        raw = 6.0 * (out[c].to_numpy() - zmin) / span
        clipped = np.clip(raw, 0.0, 6.0)
        out[c] = clipped
        n_clip = int(np.sum((raw < 0) | (raw > 6)))
        n_clip_test = int(np.sum(((raw < 0) | (raw > 6)) & (~out["beer"].isin(tr_beers).to_numpy())))
        clip_stats[c] = {"n_clipped": n_clip, "n_clipped_test": n_clip_test,
                         "test_below_0": int(np.sum((raw < 0) & (~out["beer"].isin(tr_beers).to_numpy()))),
                         "test_above_6": int(np.sum((raw > 6) & (~out["beer"].isin(tr_beers).to_numpy())))}
        mapped_rows[c] = {"mapped_min": float(clipped.min()), "mapped_max": float(clipped.max()),
                          "mapped_mean": float(clipped.mean())}

    o = "data/clean/q1_mapped.csv"
    L.write_csv(out, o)
    meta = {
        "formula": "x = 6 * (z - zmin) / (zmax - zmin)",
        "label_origin": "transformed",
        "label_nature": "mapped grade, non-original 0-6",
        "endpoint_assumption": "训练集 min=>0、max=>6；测试超出训练范围按 [0,6] 截断",
        "params_estimated_on": "train split only",
        "split_reference": split_ref,
        "n_train": int(len(train)), "n_test": int(len(test)),
        "targets": params,
        "clip_stats": clip_stats,
        "mapped_summary": mapped_rows,
        "raw_source": "4.csv（标准化/中心化连续值，缩放参数未知）",
    }
    L.write_json(meta, "data/processed/q1_map_params.json")

    smap = L.scale_map()
    feats = [c for c in out.columns if c not in L.KEEP and c not in t50]
    desc, units = {}, {}
    desc.update(DESC4)
    units.update({"beer": "id", "beer_id": "id", "tasting_category_fine": "label"})
    for c in feats:
        v = smap.get(c, {})
        sc = v.get("verdict", "unverified")
        desc[c] = ("1.csv 特征列；尺度=" + ("log10(浓度)" if sc == "log10" else
                                           "原始浓度" if sc == "linear" else "未核验"))
        units[c] = "log10(concentration)" if sc == "log10" else ("concentration" if sc == "linear" else "unknown")
    for c in t50:
        desc[c] = ("mapped grade ∈[0,6]（transformed，非原始 0–6）："
                   "x=6(z-zmin)/(zmax-zmin)，zmin/zmax 仅由训练集估计，越界截断；"
                   "原文 4.csv 为标准化连续值，缩放参数未知")
        units[c] = "mapped grade (0-6 scale, non-original)"
    prof_paths = [str(p.relative_to(L.ROOT)) for p in sorted(L.PROC.glob("profile-*.json"))]
    fields = L.build_fields(list(out.columns), prof_paths, desc, units)
    L.write_json(fields, "data/processed/fields_q1mapped.json")

    tot_clip = sum(v["n_clipped"] for v in clip_stats.values())
    tot_clip_test = sum(v["n_clipped_test"] for v in clip_stats.values())
    print(json.dumps({"shape": list(out.shape), "n_targets": len(t50),
                      "n_train": int(len(train)), "n_test": int(len(test)),
                      "total_clipped": tot_clip, "total_clipped_test": tot_clip_test,
                      "clipped_targets": [c for c, v in clip_stats.items() if v["n_clipped"] > 0],
                      "csv": o}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
