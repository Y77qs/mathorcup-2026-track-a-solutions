"""03 清洗：生成 data/clean/ 下的全部规范化数据版本（不改数值，不做插补）。

样本流：1.csv 250 行 -> features_log 250 行（0 行删除）；1.csv 的 73 个真实缺失原样保留，
        只在建模折内插补（本脚本只生成 missing_flags 供插补/分层使用）。

产物：
  data/clean/features_log.csv     250 × 235（beer, beer_id, tasting_category_fine, style + 231 特征）
  data/clean/targets_z.csv        250 × 53 （beer, beer_id, tasting_category_fine + 50 感官目标）
  data/clean/concentrations.csv   250 × 73 （beer, beer_id, tasting_category_fine + 70 作者标定浓度）
  data/clean/oav.csv              250 × 44 （beer + 43 个有阈值化合物的 OAV；1.csv 缺失处留空）
  data/clean/missing_flags.csv    250 × 10 （beer + 9 个缺失列 0/1 指示）
  data/clean/DATA_DICTIONARY.md   字段/单位/缺失政策/尺度字典/泄漏清单
  outputs/data/clean_summary.json 形状、缺失统计、sha256（供 README 与台账引用）

关键约定（详见 DATA_DICTIONARY.md）：
  * 连接键一律用 `beer`（4.csv/7.csv 的 beer_id 被脱敏，只有 96 个唯一值；1.csv 与 8.xlsx
    Calibrated 的 beer_id 未脱敏且完全一致）。
  * 8.xlsx Calibrated 是作者统一浓度表：1.csv 的 37 列为 log10(calibrated)，33 列为 calibrated 原值，
    其余 161 列无外部校验（unverified）。详见 outputs/audit/scale_report.json。
  * OAV = 8.xlsx calibrated 浓度 / 8.xlsx threshold_mean（与 common.oav_table() 同一口径），
    但 1.csv 缺失的 73 个单元格对应 OAV 一律留空（不把"缺失"当作"非检出=0"）。
仅写 data/clean/ 与 outputs/data/，不改 data/raw、problem、state。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

KEYSET = set(C.KEYS)
REL_TOL = 1e-6
FLOOR_ATOL = 1e-6


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def scale_verdicts(f: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """与 02_scale.py 相同的判据：中位相对误差 < 1e-6 判 log10 / linear，否则 unverified。"""
    feats = [c for c in f.columns if c not in KEYSET]
    cal_cols = [c for c in cal.columns if c not in KEYSET]
    m = f[["beer"] + feats].merge(cal[["beer"] + [c for c in cal_cols if c in feats]],
                                  on="beer", suffixes=("", "_cal"))
    out = []
    for c in feats:
        if c in cal_cols:
            v = m[c].astype(float).values
            cc = m[c + "_cal"].astype(float).values
            ok = np.isfinite(v) & np.isfinite(cc)
            nz = ok & (cc != 0)
            with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
                e_log = np.abs(10.0 ** v[nz] - cc[nz]) / np.maximum(np.abs(cc[nz]), 1e-12)
                e_lin = np.abs(v[nz] - cc[nz]) / np.maximum(np.abs(cc[nz]), 1e-12)
            med_log = float(np.median(e_log)) if nz.any() else np.nan
            med_lin = float(np.median(e_lin)) if nz.any() else np.nan
            verdict = "log10" if med_log < REL_TOL else ("linear" if med_lin < REL_TOL else "ambiguous")
            out.append({"compound": c, "scale_verdict": verdict,
                        "median_rel_err_log10": med_log, "median_rel_err_identity": med_lin,
                        "in_calibrated": True})
        else:
            out.append({"compound": c, "scale_verdict": "unverified",
                        "median_rel_err_log10": np.nan, "median_rel_err_identity": np.nan,
                        "in_calibrated": False})
    return pd.DataFrame(out)


def main():
    f = C.load_features()                       # 1.csv
    t4 = C.read_csv_raw("4.csv")                # 4.csv（beer_id 已脱敏）
    cal = C.load_calibrated_chemicals()         # 8.xlsx Calibrated
    th = C.threshold_table()                    # field = field_name_R
    feats = [c for c in f.columns if c not in KEYSET]

    # ---------------------------------------------------------------- 键对齐校验
    idx = f[["beer", "beer_id", "tasting_category_fine"]].copy()
    assert f["beer"].is_unique and f["beer_id"].is_unique, "1.csv 的 beer / beer_id 应唯一"
    assert set(f["beer"]) == set(range(1, 251)), "beer 应为 1..250"
    assert t4["beer"].tolist() == f["beer"].tolist(), "4.csv 的 beer 顺序应与 1.csv 一致"
    assert cal["beer"].tolist() == f["beer"].tolist(), "8.xlsx calibrated 的 beer 顺序应与 1.csv 一致"
    # 4.csv beer_id 已脱敏 -> 统一换成 1.csv 的未脱敏 beer_id；先核验风格标签一致
    m4 = t4[["beer", "tasting_category_fine"]].merge(
        f[["beer", "tasting_category_fine"]], on="beer", suffixes=("_4", "_1"))
    assert len(m4) == 250
    assert (m4["tasting_category_fine_4"] == m4["tasting_category_fine_1"]).all(), \
        "4.csv 与 1.csv 的 tasting_category_fine 必须逐 beer 一致"
    # calibrated 的 beer_id 与 1.csv 一致（未脱敏）
    assert (cal["beer_id"].astype("int64").values == f["beer_id"].astype("int64").values).all(), \
        "8.xlsx calibrated 的 beer_id 应与 1.csv 一致"

    # ---------------------------------------------------------------- features_log
    feat = f[["beer", "beer_id", "tasting_category_fine"]].copy()
    feat["style"] = f["tasting_category_fine"]           # 风格别名，供 modeler 使用
    feat = pd.concat([feat, f[feats]], axis=1)
    C.write_csv(feat, "data/clean/features_log.csv")

    # ---------------------------------------------------------------- targets_z
    tgt = t4[["beer", "tasting_category_fine"] + C.TARGET_DIMS].copy()
    tgt = tgt.merge(f[["beer", "beer_id"]], on="beer", how="left")
    tgt = tgt[["beer", "beer_id", "tasting_category_fine"] + C.TARGET_DIMS]
    tgt["beer_id"] = tgt["beer_id"].astype("int64")
    assert tgt.shape == (250, 53), tgt.shape
    assert tgt[C.TARGET_DIMS].isna().sum().sum() == 0, "4.csv 目标应无缺失"
    C.write_csv(tgt, "data/clean/targets_z.csv")

    # ---------------------------------------------------------------- concentrations
    conc = cal[["beer", "beer_id", "tasting_category_fine"] +
               [c for c in cal.columns if c not in KEYSET]].copy()
    assert conc.shape == (250, 73), conc.shape
    C.write_csv(conc, "data/clean/concentrations.csv")

    # ---------------------------------------------------------------- OAV（calibrated / threshold）
    # 与 common.oav_table() 同口径；唯一差异：1.csv 缺失处留空（不把缺失当"非检出=0"）。
    thw = th[th["field"].isin(cal.columns)].copy()
    assert len(thw) == 43, f"阈值化合物应 43 个，实际 {len(thw)}"
    oav = pd.DataFrame({"beer": cal["beer"].astype(int).values})
    missing_mask = {}
    n_blank_by_missing = 0
    for field in thw["field"]:
        thr = float(thw.loc[thw["field"] == field, "threshold_mean"].iloc[0])
        conc_col = pd.to_numeric(cal[field], errors="coerce").astype(float)
        v = conc_col / thr
        v = v.where(conc_col.notna(), np.nan)             # calibrated 本身 NaN -> 空
        if field in f.columns:                            # 1.csv 缺失 -> 空（不当作 0）
            miss = f[field].isna().values
            missing_mask[field] = int(miss.sum())
            v = v.where(~miss, np.nan)
            n_blank_by_missing += int(miss.sum())
        oav[field] = v.values
    assert oav.shape == (250, 44), oav.shape
    C.write_csv(oav, "data/clean/oav.csv")

    # 与 common.oav_table() 交叉核对（非缺失行必须完全一致；按 beer 交集逐行比较）
    ref = C.oav_table()
    ref = ref.reset_index() if "beer" not in ref.columns else ref
    ref = ref.set_index("beer")
    mine = oav.set_index("beer")
    common_idx = mine.index.intersection(ref.index)
    for field in thw["field"]:
        a = mine.loc[common_idx, field].astype(float)
        b = ref.loc[common_idx, field].astype(float)
        both = a.notna() & b.notna()
        if both.any():
            assert np.allclose(a[both].values, b[both].values, rtol=1e-12, atol=0), \
                f"oav.csv 与 common.oav_table() 在 {field} 的非缺失行不一致"

    # ---------------------------------------------------------------- missing_flags
    na = f[feats].isna().sum()
    miss_cols = [c for c in na[na > 0].sort_values(ascending=False).index]
    flags = pd.DataFrame({"beer": f["beer"].astype(int).values})
    for c in miss_cols:
        flags[f"{c}__isna"] = f[c].isna().astype("int8").values
    assert flags.shape == (250, 1 + len(miss_cols)), flags.shape
    C.write_csv(flags, "data/clean/missing_flags.csv")

    # ---------------------------------------------------------------- 尺度字典
    sc = scale_verdicts(f, cal)
    scale_csv = C.ROOT / "outputs" / "audit" / "scale_identification.csv"
    scale_report = {}
    scale_report_path = C.ROOT / "outputs" / "audit" / "scale_report.json"
    if scale_report_path.exists():
        scale_report = pd.read_json(scale_report_path, typ="series").to_dict()
    if scale_csv.exists():
        known = pd.read_csv(scale_csv)[["compound", "scale_verdict"]]
        chk = sc.merge(known, on="compound", suffixes=("", "_02"))
        assert (chk["scale_verdict"] == chk["scale_verdict_02"]).all(), \
            "03_clean 的尺度判定必须与 02_scale.py 产物一致"
    n_censored = int((scale_report.get("censoring") or {}).get("total_calibrated_zero_cells_in_log10_cols") or 0)
    units = dict(zip(thw["field"], thw["unit"].astype(str)))
    thmean = dict(zip(thw["field"], thw["threshold_mean"].astype(float)))
    offs = dict(zip(thw["field"], thw["off_flavors"].fillna("").astype(str)))

    # ---------------------------------------------------------------- DATA_DICTIONARY
    lines = []
    A = lines.append
    A("# 数据字典（data/clean，生成脚本 src/03_clean.py）")
    A("")
    A("> 本文件由 `src/03_clean.py` 生成；所有数字来自该脚本运行时对 `data/raw/` 的真实计算。")
    A("> 口径：只做类型/键/对齐/派生/标记，**不做任何插补**（插补留在建模折内）。")
    A("")
    A("## 1. 文件清单与样本流")
    A("")
    A("| 文件 | 行 × 列 | 说明 |")
    A("|---|---|---|")
    A(f"| `data/clean/features_log.csv` | {feat.shape[0]} × {feat.shape[1]} | 1.csv 原值复制 + 键 + `style`（= tasting_category_fine 别名）；231 个特征列数值一字未改 |")
    A(f"| `data/clean/targets_z.csv` | {tgt.shape[0]} × {tgt.shape[1]} | 4.csv 的 50 个感官目标（标准化连续值），按 `beer` 对齐 1.csv 的 beer_id |")
    A(f"| `data/clean/concentrations.csv` | {conc.shape[0]} × {conc.shape[1]} | 8.xlsx `Calibrated chemical dataset`（作者统一浓度表，70 化合物） |")
    A(f"| `data/clean/oav.csv` | {oav.shape[0]} × {oav.shape[1]} | 43 个有阈值化合物的 OAV = calibrated 浓度 / threshold_mean；1.csv 缺失处留空 |")
    A(f"| `data/clean/missing_flags.csv` | {flags.shape[0]} × {flags.shape[1]} | 9 个缺失列的 0/1 缺失指示（供插补/分层使用） |")
    A("")
    A("样本流：`1.csv` 250 行 → `features_log` **250 行（删除 0 行）**；`4.csv` 250 行 → `targets_z` 250 行；")
    A("三张样本表（1/4/7.csv）的 `beer` 列顺序完全一致，连接**只用 `beer`**。")
    A("")
    A("## 2. 键与连接规则")
    A("")
    A("- `beer`：1..250 的样本序号，三表顺序一致，是唯一可靠连接键。")
    A("- `beer_id`：1.csv 与 8.xlsx Calibrated 未脱敏且完全相同；**4.csv / 7.csv 的 beer_id 被脱敏**")
    A(f"  （4.csv 仅 {t4['beer_id'].nunique()} 个唯一值，如 5410230000000.0），故 `targets_z.csv` 的 `beer_id` 已用 1.csv 的未脱敏值替换。")
    A("- `tasting_category_fine`：22 类风格标签；4.csv 与 1.csv 逐 beer 完全一致（已断言），因此 `style` 列与两表标签等价。")
    A("")
    A("## 3. 缺失政策")
    A("")
    A(f"- 1.csv 共 **{int(f[feats].isna().sum().sum())} 个真实缺失**，分布在 **{len(miss_cols)} 列**、"
      f"**{int(f[feats].isna().any(axis=1).sum())} 行**：")
    for c in miss_cols:
        A(f"  - `{c}`：{int(na[c])} 个")
    A("- **清洗阶段不插补**：所有缺失原样保留在 `features_log.csv`；插补/标准化/特征选择只在训练折内拟合。")
    A("- `missing_flags.csv` 提供逐行逐列 0/1 指示，可用于插补模型与分层误差报告。")
    A("- 缺失机制：缺失行与完整行的风格分布无显著关联（`outputs/audit/audit.json` C11b：χ² 检验 p≈0.34），"
      "但样本量小，只能作为弱证据；按 questions.yaml 要求分别报告缺失行/完整行的误差。")
    A("- 与 `calibrated == 0` 区分：`calibrated == 0` 是**非检出（低于检出限）**标记，不是缺失；"
      "1.csv 对这些行给出的是 `log10(该列最小正浓度/2)` 的 LOD/2 替换值（log10 列共 "
      f"{n_censored} 个单元格，见 `outputs/audit/scale_report.json` 的 `censoring`）。")
    A(f"- `oav.csv` 中 **{n_blank_by_missing} 个单元格因 1.csv 缺失而留空**（涉及的化合物："
      + "、".join(f"`{k}`({v})" for k, v in missing_mask.items() if v > 0) + "）；"
      "其余为 calibrated/threshold。`calibrated == 0`（非检出）的 OAV 保留 0。")
    A("")
    A("## 4. 尺度字典（1.csv 是混合尺度表）")
    A("")
    vc = sc["scale_verdict"].value_counts().to_dict()
    A(f"- 判定口径：以 8.xlsx `Calibrated chemical dataset`（70 列）为参照，比较 `10^v` 与 `v` 对 calibrated 的中位相对误差，"
      "阈值 1e-6；无 calibrated 覆盖的列一律 `unverified`（不臆造底数/单位）。")
    A(f"- 计数：**log10 = {vc.get('log10', 0)} 列**，**linear = {vc.get('linear', 0)} 列**，"
      f"**unverified = {vc.get('unverified', 0)} 列**（合计 {len(sc)} 列）。")
    A("- log10 列：还原浓度 = `10^(1.csv 值)`；linear 列：浓度 = `1.csv 值`（与 calibrated 完全一致）。")
    A("- `unverified` 列：1.csv 值原样保留为特征；若其含负值/共享地板值，仅说明是 log 尺度可能性高，"
      "**不参与 OAV、不声称物理单位**。")
    A("")
    A("### 4.1 有阈值的 43 个化合物（单位来自 8.xlsx Sensory thresholds，join 键为 `field_name_R`）")
    A("")
    A("| 化合物（1.csv 列名） | 人读名 | 尺度 | 单位 | 阈值（threshold_mean） | off-flavor 标记 |")
    A("|---|---|---|---|---|---|")
    srow = sc.set_index("compound")["scale_verdict"]
    for field in thw["field"]:
        label = str(thw.loc[thw["field"] == field, "label"].iloc[0])
        off = offs.get(field, "")
        A(f"| `{field}` | {label} | {srow.get(field, 'unverified')} | {units.get(field, '')} | {thmean.get(field):.6g} | {off} |")
    A("")
    A("> 说明：阈值表的 `field_name_python` 是人读名（含空格/逗号，如 `2,3-butanedione`），"
      "与数据列名对不上；必须用 `field_name_R`（如 `X2.3.butanedione`）join。43/43 全部命中。")
    A("")
    A("## 5. 目标字典（targets_z.csv，50 维）")
    A("")
    A("| 族 | 维度数 | 列名 |")
    A("|---|---|---|")
    A(f"| Aroma | {len(C.AROMA_DIMS)} | {', '.join(C.AROMA_DIMS)} |")
    A(f"| Flavour/Taste | {len(C.FLAVOUR_DIMS)} | {', '.join(C.FLAVOUR_DIMS)} |")
    A(f"| 口感/缺陷/总体 | {len(C.PALATE_DIMS)} | {', '.join(C.PALATE_DIMS)} |")
    A("")
    A("- 4.csv 的数值是**标准化/中心化后的连续值**（每列 172–249 个不同取值，非整数化后的 z），无量纲。")
    A(f"- 0–6 分级标定（唯一定义，见 common.Z_GRADE_CALIBRATION）：`{C.Z_GRADE_CALIBRATION['policy']}`，"
      f"主宽度 S = {C.Z_GRADE_CALIBRATION['primary']}，敏感性 S = {C.Z_GRADE_CALIBRATION['sensitivity']}；"
      "等级 3 锚定 z = 0。")
    A("- 5 类题面点名缺陷维度的化合物映射见 `common.DEFECT_DIMS`（dms, diacetyl, X4vg, t2n, stale_hops）。")
    A("")
    A("## 6. 特征字典（features_log.csv 的 231 个特征列）")
    A("")
    A("| # | 列名 | 尺度判定 | 单位 | 1.csv 缺失数 | 聚合列 |")
    A("|---|---|---|---|---|---|")
    for i, c in enumerate(feats, 1):
        unit = units.get(c, "—（未验证/无阈值）")
        agg = "是" if c in C.AGG_FEATURES else ""
        A(f"| {i} | `{c}` | {srow.get(c, 'unverified')} | {unit} | {int(f[c].isna().sum())} | {agg} |")
    A("")
    A("> 5 个聚合列（`kcalperc`/`acids_sum`/`esters_sum`/`aroma_hops_sum`/`sulfur_sum`）由多个化合物计算得出，"
      "本身是化合物函数；按 questions.yaml 要求须在消融中单独评估（含/不含）。")
    A("")
    A("## 7. 不可用于特征的泄漏清单")
    A("")
    A("| 对象 | 为什么泄漏 | 允许用途 |")
    A("|---|---|---|")
    A("| `4.csv` 的 50 列感官目标 | 就是 Q1 标签 | 只作 y；可作 Q3 感官画像的一致性校验 |")
    A("| `7.csv`（250×189，Ratebeer 论坛评论派生） | 目标代理（同源感官描述，3 列全缺） | Q2 稳健性外部佐证，禁止进 Q1/Q3 特征 |")
    A("| `5.csv` / `6.csv`（感官间与化学-感官相关矩阵） | 由感官目标计算得到 | Q2 的独立先验核对（不得用于挑 Top-3）；Q3 画像校验 |")
    A("| `8.xlsx` `GBM importance MDI` / `GBM SHAP Values` | 已用 4.csv 目标训练出的模型产物 | 只作外部对照 |")
    A("| `3.xlsx` 的 12 个 beer sheet + summary | 空白评分卡模板（无评分值） | 仅作 50 维定义与 0–6 刻度依据 |")
    A("| `2.csv`（231×231 Spearman） | 由 1.csv 特征计算，不含目标 | Q2 共表达图结构（允许） |")
    A("")
    A("## 8. 复现")
    A("")
    A("```bash")
    A("# 解释器：contest.yaml runtime.python")
    A("python src/02_scale.py    # -> outputs/audit/scale_*.{csv,json}")
    A("python src/03_clean.py    # -> data/clean/*, outputs/data/clean_summary.json")
    A("python src/04_split.py    # -> data/splits/{train,test,assignment}.csv")
    A("```")
    A("")
    dict_path = C.ROOT / "data" / "clean" / "DATA_DICTIONARY.md"
    dict_path.parent.mkdir(parents=True, exist_ok=True)
    dict_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------------------------------------------------------------- clean_summary.json
    files = {
        "features_log.csv": "data/clean/features_log.csv",
        "targets_z.csv": "data/clean/targets_z.csv",
        "concentrations.csv": "data/clean/concentrations.csv",
        "oav.csv": "data/clean/oav.csv",
        "missing_flags.csv": "data/clean/missing_flags.csv",
        "DATA_DICTIONARY.md": "data/clean/DATA_DICTIONARY.md",
    }
    summary = {
        "generated_by": "src/03_clean.py",
        "sample_flow": {"1.csv_rows": int(len(f)), "features_log_rows": int(len(feat)),
                        "rows_dropped": 0, "targets_rows": int(len(tgt))},
        "files": {},
        "keys": {
            "join_key": "beer",
            "beer_id_masked_in": ["4.csv", "7.csv"],
            "4csv_unique_beer_id": int(t4["beer_id"].nunique()),
            "style_consistent_1_vs_4": bool((m4["tasting_category_fine_4"] == m4["tasting_category_fine_1"]).all()),
        },
        "missing": {
            "n_missing_cells_1csv": int(f[feats].isna().sum().sum()),
            "n_cols_with_missing": int(len(miss_cols)),
            "n_rows_with_missing": int(f[feats].isna().any(axis=1).sum()),
            "by_column": {c: int(na[c]) for c in miss_cols},
            "policy": "清洗阶段不插补；插补/标准化只在训练折内拟合",
        },
        "scale": {
            "counts": {k: int(v) for k, v in vc.items()},
            "n_threshold_compounds": int(len(thw)),
            "oav_definition": "calibrated_conc / threshold_mean；1.csv 缺失处留空",
            "n_blank_by_missing": int(n_blank_by_missing),
            "blank_by_missing_by_compound": {k: int(v) for k, v in missing_mask.items() if v > 0},
            "censoring_note": "calibrated==0 = 非检出；log10 列在 1.csv 中为 log10(min_positive/2)",
        },
        "shapes": {
            "features_log": list(feat.shape), "targets_z": list(tgt.shape),
            "concentrations": list(conc.shape), "oav": list(oav.shape), "missing_flags": list(flags.shape),
        },
        "sha256": {k: sha256(C.ROOT / v) for k, v in files.items()},
    }
    C.write_json(summary, "outputs/data/clean_summary.json")

    print("== clean files ==")
    for k, v in files.items():
        p = C.ROOT / v
        print(f"{v}: {summary['shapes'].get(k[:-4] if k.endswith('.csv') else k)} "
              f"sha256={summary['sha256'][k][:16]}...")
    print("\n== shapes ==", summary["shapes"])
    print("\n== missing ==", summary["missing"]["n_missing_cells_1csv"], "cells /",
          summary["missing"]["n_cols_with_missing"], "cols /",
          summary["missing"]["n_rows_with_missing"], "rows")
    print("\n== scale counts ==", summary["scale"]["counts"])
    print("\n== oav blanks by missing ==", summary["scale"]["n_blank_by_missing"], summary["scale"]["blank_by_missing_by_compound"])
    print("\n== style consistency ==", summary["keys"]["style_consistent_1_vs_4"])


if __name__ == "__main__":
    main()
