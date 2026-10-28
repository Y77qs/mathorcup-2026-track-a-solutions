#!/usr/bin/env python
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
# -*- coding: utf-8 -*-
"""q3_v62_answer_tables.py — Q3 章三张"实体答案表"（CSV + 可直接嵌入论文的 markdown 片段）。

本脚本只读以下已保存的产物，不调用 modeling_* 插件、不读 state/ledger.json、不重训/重拟合任何模型或边际：

  表 1  tripel_kriek_lambic_profile_{chem,sensory}
        experiments/EXP-0109/samples.csv              （design 设计谱，copula-selected）
        experiments/EXP-0109/sensory_profiles.csv     （stage=design 的 50 维岭回归标签代理）
        data/clean/q3.csv                             （250 行真实训练化学 + 50 维感官标签）
        data/processed/v6_feature_dictionary.csv      （每列的 storage_scale / tier / unit_or_scale）
        src/target_columns.py                         （LOG10_CALIBRATED / LINEAR_CALIBRATED / FLOOR_COLUMNS）

  表 2  pils_to_tripel_single_source
        experiments/EXP-0110/transfers.csv            （src__ / ref__ / opt__ / 缺陷物理值与不增标记）
        experiments/EXP-0110/transfer_sources.csv     （源状态 measured / missing / floor）
        experiments/EXP-0110/transfer_outputs.json    （protocol.sourceStyle/sourceBeers，用于核对规则）
        data/clean/q3.csv                             （核对应源值就是训练表中的存储值）
        data/clean/q3_thresholds.json                 （缺陷阈值与单位）

  表 3  defect_control_summary
        experiments/EXP-0110/transfer_constraints.csv （逐条上界记录：lower_zero / upper_source_value / proxy）
        experiments/EXP-0110/transfer_verdicts.csv    （四类核验状态与分母）
        experiments/EXP-0110/transfer_sources.csv     （源状态计数；99 = 3 重复 × 3 折 × 11 支源啤酒）
        experiments/EXP-0110/transfers.csv            （stale 半空间 b、a'z_source）
        data/clean/q3_thresholds.json
        data/processed/v6_feature_dictionary.csv

数值约定（与 src/q3_lib.py 一致，未在脚本内重新拟合）：
  · log10 校准列：物理值 = 10 ** 存储值；线性校准列：物理值 = 存储值；其余列保留存储尺度并标注"未校准"。
  · 声明的非检测码（FLOOR_VALUE，或 q3_lib 的重复最小值地板码）在物理换算时计为 0；本表所选列在
    三风格真实行中均无缺失、无地板码（terpinen-4-ol 声明为地板码列，但本表样本中未出现地板码）。
  · 百分位为 numpy 线性插值 P10 / P90，中位数 P50；CSV 数值列保留全精度，`*_display` 列按 4 位有效数字显示。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import target_columns as T  # noqa: E402  (纯常量快照；不导入 q3_lib/q_common，避免触发 modeling_contract)

EXP109 = ROOT / "experiments" / "EXP-0109"
EXP110 = ROOT / "experiments" / "EXP-0110"
DATA_CLEAN = ROOT / "data" / "clean"
DATA_PROCESSED = ROOT / "data" / "processed"
OUT_DIR = ROOT / "outputs" / "q3" / "v62_tables"
SUB_DIR = ROOT / "FINAL_SUBMISSION_v6.2" / "支撑材料" / "outputs" / "q3" / "v62_tables"

STYLE_COLUMN = T.STYLE_COLUMN                      # 'tasting_category_fine'
CHEM_PREFIX = T.CHEM_PREFIX                        # 'chem__'
STYLES = ("Tripel", "Kriek", "Lambic")

LOG10_SET = set(T.LOG10_CALIBRATED)                # 37 列：物理值 = 10 ** 存储值
LINEAR_SET = set(T.LINEAR_CALIBRATED)              # 33 列：物理值 = 存储值
FLOOR_SET = set(T.FLOOR_COLUMNS)                   # 142 个声明地板码列
FLOOR_VALUE = float(T.FLOOR_VALUE)

PRIMARY_STRATEGY = "qp-quantile-anchor"            # EXP-0110 的交付策略
TRANSFER_RULE = "repeat=0, 外层 fold=0, 在 11 支 Pils/Lager 源啤酒中取最小 source_beer id"
TRANSFER_TRUNC = 1e-12                             # Δ 小于该值按数值噪声显示为 0

# --------------------------------------------------------------------------------------------- 表 1 指标清单
# (源列名, 中文名, 备注)；全部为"已校准"列，另加 1 个未校准列用于展示"存储尺度（未校准）"标注
CHEM_ITEMS = (
    ("ethanol..v.v.", "乙醇", ""),
    ("SO2.mg.L.", "二氧化硫", ""),
    ("pH", "pH", ""),
    ("bitterness", "苦度（α-酸）", ""),
    ("color.EBC.", "色度", ""),
    ("glycerol", "甘油", ""),
    ("acetic_acid.g.L.", "乙酸", ""),
    ("lactic_acid.mg.L.", "乳酸", ""),
    ("ethyl_acetate", "乙酸乙酯", ""),
    ("isoamyl_alcohol", "异戊醇", ""),
    ("linalool", "芳樟醇", ""),
    ("terpinen.4.ol", "4-松油醇", "未校准列，仅存储尺度"),
)

# 核心感官代理：malt / hops / ester / sour-acid / overall（全部来自 50 维标签的第 j 列）
SENSORY_ITEMS = (
    ("A_malt_all", "麦芽香总体", "香气维度：麦芽总体强度"),
    ("A_hops_all", "酒花总体", "香气维度：酒花总体强度"),
    ("A_esters_all", "酯香总体", "香气维度：酯类总体强度"),
    ("acidity", "酸度", "酸度维度（sour/acid）"),
    ("overall", "总体", "总体维度"),
)

# 表 2/表 3 的缺陷清单（顺序固定：DMS、双乙酰、4VG、真实反-2-壬烯醛、老化酒花代理）
DEFECT_ITEMS = (
    ("DMS", "二甲基硫（DMS）", "upper_source_value"),
    ("X2.3.butanedione", "双乙酰（2,3-丁二酮）", "upper_source_value"),
    ("X4VG", "4-乙烯基愈创木酚（4VG）", "upper_source_value"),
    ("X.E..2.nonenal", "反-2-壬烯醛（trans-2-nonenal）", "upper_source_value"),
)
PROXY_FIELD = "stale_hops(ridge-proxy)"


# --------------------------------------------------------------------------------------------- 通用工具
def fail(message: str) -> None:
    raise SystemExit("[q3_v62_answer_tables] " + message)


def load_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        fail("缺少输入文件：%s" % path)
    return pd.read_csv(path, **kwargs)


def load_json(path: Path) -> dict:
    if not path.exists():
        fail("缺少输入文件：%s" % path)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def fmt4(value, tiny_zero: float | None = None) -> str:
    """4 位有效数字的显示串；NaN → '—'。tiny_zero：绝对值小于该值的数按 0 显示。"""
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(number):
        return "—"
    if tiny_zero is not None and abs(number) < float(tiny_zero):
        number = 0.0
    if number == 0.0:
        return "0.000"
    scale = abs(number)
    if scale >= 1e5 or scale < 1e-3:
        return "%.3e" % number
    decimals = max(0, 3 - int(np.floor(np.log10(scale))))
    return ("%." + str(decimals) + "f") % number


def md_table(header, rows, aligns) -> str:
    if len(header) != len(aligns):
        fail("markdown 表头与对齐长度不一致")
    lines = ["| " + " | ".join(str(cell) for cell in header) + " |",
             "| " + " | ".join("---:" if a == "r" else "---" for a in aligns) + " |"]
    for row in rows:
        if len(row) != len(header):
            fail("markdown 行长度不一致：%r" % (row,))
        cells = []
        for cell in row:
            text = str(cell)
            if "|" in text:
                fail("markdown 单元格不允许包含竖线：%r" % (text,))
            cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def summarize(values) -> dict:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {"n": 0, "mean": None, "median": None, "p10": None, "p90": None}
    return {
        "n": int(array.size),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p10": float(np.percentile(array, 10)),
        "p90": float(np.percentile(array, 90)),
    }


def to_physical(column: str, stored) -> np.ndarray:
    """存储值 → 物理值（q3_lib.physical_conc 的读法）；未校准列原样返回。"""
    values = np.asarray(stored, dtype=float)
    if column in FLOOR_SET:
        values = np.where(np.isclose(values, FLOOR_VALUE, rtol=1e-6, atol=0.0), 0.0, values)
    if column in LOG10_SET:
        return np.power(10.0, values)
    return values


def feature_meta(fd: pd.DataFrame) -> dict:
    meta = {}
    for record in fd.to_dict("records"):
        meta[str(record["name"])] = record
    return meta


def unit_scale_text(column: str, meta: dict) -> str:
    """markdown 的"尺度/单位"列：物理尺度 + 单位，或存储尺度（未校准）。"""
    record = meta.get(column)
    if record is None:
        fail("特征字典缺少列：%s" % column)
    tier = str(record["tier"])
    unit = str(record["unit_or_scale"])
    declared = unit not in ("not declared in 8.xlsx", "A.U.")
    if tier == "calibrated_log10":
        return "物理尺度，%s（log10 校准，c=10^x）" % unit
    if tier == "calibrated_linear":
        return "物理尺度，%s（线性校准，c=x）" % unit
    if declared:
        return "存储尺度（未校准），单位 %s" % unit
    return "存储尺度（未校准），单位未声明"


def write_frames(name: str, frame: pd.DataFrame) -> Path:
    path = OUT_DIR / name
    frame.to_csv(path, index=False, lineterminator="\n", encoding="utf-8")
    frame.to_csv(SUB_DIR / name, index=False, lineterminator="\n", encoding="utf-8")
    return path


def write_text(name: str, text: str) -> Path:
    path = OUT_DIR / name
    path.write_text(text, encoding="utf-8")
    (SUB_DIR / name).write_text(text, encoding="utf-8")
    return path


def write_note(name: str, note: str, source: str) -> Path:
    path = OUT_DIR / name
    body = source + "\n\n" + note
    path.write_text(body, encoding="utf-8")
    (SUB_DIR / name).write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------------- 读入
def load_inputs() -> dict:
    q3 = load_csv(DATA_CLEAN / "q3.csv")
    samples = load_csv(EXP109 / "samples.csv")
    sensory = load_csv(EXP109 / "sensory_profiles.csv")
    transfers = load_csv(EXP110 / "transfers.csv")
    sources = load_csv(EXP110 / "transfer_sources.csv")
    verdicts = load_csv(EXP110 / "transfer_verdicts.csv")
    constraints = load_csv(EXP110 / "transfer_constraints.csv")
    thresholds = load_json(DATA_CLEAN / "q3_thresholds.json")
    fd = load_csv(DATA_PROCESSED / "v6_feature_dictionary.csv")
    outputs = load_json(EXP110 / "transfer_outputs.json")["q3_transfer"]

    # ---- 输入自检 -------------------------------------------------------------------------
    for frame, label, columns in (
        (q3, "data/clean/q3.csv", [STYLE_COLUMN] + [CHEM_PREFIX + c for c in T.FEATURE_COLS] + list(T.TARGET_COLS)),
        (samples, "EXP-0109/samples.csv", ["style", "repeat", "fold", "model_id"]),
        (sensory, "EXP-0109/sensory_profiles.csv", ["style", "stage", "repeat", "fold"]),
        (transfers, "EXP-0110/transfers.csv", ["transfer_id", "repeat", "fold", "source_beer", "strategy",
                                              "anchor", "src__chem__DMS", "opt__chem__DMS", "ref__chem__DMS"]),
        (sources, "EXP-0110/transfer_sources.csv", ["repeat", "fold", "source_beer", "column", "source_state"]),
        (verdicts, "EXP-0110/transfer_verdicts.csv",
         ["strategy", "field", "bound_type", "verdict", "n", "denominator", "verifiedDenominator"]),
        (constraints, "EXP-0110/transfer_constraints.csv",
         ["strategy", "field", "bound_type", "bound_value_physical", "unit"]),
    ):
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            fail("%s 缺少列：%s" % (label, missing))

    if set(STYLES) - set(q3[STYLE_COLUMN].unique()):
        fail("q3.csv 缺少目标风格行")
    if set(samples["model_id"].unique()) != {"copula-selected"}:
        fail("EXP-0109 samples.csv 不是单一 copula-selected 方案：%s" % samples["model_id"].unique())
    if set(transfers["strategy"].unique()) != {
            "source-fixed", "target-mean-projection", "target-mean-projection-full",
            "qp-source-anchor", PRIMARY_STRATEGY}:
        fail("transfers.csv 的策略集合与预期不符")

    return {
        "q3": q3, "samples": samples, "sensory": sensory, "transfers": transfers,
        "sources": sources, "verdicts": verdicts, "constraints": constraints,
        "thresholds": thresholds, "meta": feature_meta(fd), "outputs": outputs,
    }


# --------------------------------------------------------------------------------------------- 表 1
def build_profile(data: dict) -> tuple:
    q3 = data["q3"]
    samples = data["samples"]
    sensory = data["sensory"]
    meta = data["meta"]

    gen = samples[samples["style"].isin(STYLES)].copy()
    real = q3[q3[STYLE_COLUMN].isin(STYLES)].copy()
    gen_sense = sensory[(sensory["stage"] == "design") & (sensory["style"].isin(STYLES))].copy()

    # 生成谱在 12 个所选化合物上不应出现缺失/地板码（否则"物理值"含 0 质量点，需要另行说明）
    for column, _, _ in CHEM_ITEMS:
        gen_values = gen[CHEM_PREFIX + column].to_numpy(dtype=float)
        real_values = real[CHEM_PREFIX + column].to_numpy(dtype=float)
        if not np.isfinite(gen_values).all() or not np.isfinite(real_values).all():
            fail("表 1 列 %s 存在缺失值：不能按本表口径汇总" % column)
        if np.isclose(gen_values, FLOOR_VALUE, rtol=1e-6, atol=0.0).any():
            fail("表 1 列 %s 的生成谱出现地板码：需要改口径" % column)
        if np.isclose(real_values, FLOOR_VALUE, rtol=1e-6, atol=0.0).any():
            fail("表 1 列 %s 的真实行出现地板码：需要改口径" % column)

    chem_rows = []
    for style in STYLES:
        style_gen = gen[gen["style"] == style]
        style_real = real[real[STYLE_COLUMN] == style]
        for column, item_cn, note in CHEM_ITEMS:
            generated = to_physical(column, style_gen[CHEM_PREFIX + column])
            observed = to_physical(column, style_real[CHEM_PREFIX + column])
            gen_stat = summarize(generated)
            real_stat = summarize(observed)
            record = meta[column]
            chem_rows.append({
                "block": "chem",
                "style": style,
                "item_cn": item_cn,
                "column": column,
                "tier": str(record["tier"]),
                "storage_scale": str(record["storage_scale"]),
                "physical_inverse": ("10**x" if record["tier"] == "calibrated_log10"
                                     else ("x" if record["tier"] == "calibrated_linear" else "x (未校准)")),
                "unit": str(record["unit_or_scale"]),
                "unit_declared": "yes" if str(record["unit_or_scale"]) not in
                                        ("not declared in 8.xlsx", "A.U.") else "no",
                "generated_n": gen_stat["n"],
                "generated_mean": gen_stat["mean"],
                "generated_median": gen_stat["median"],
                "generated_p10": gen_stat["p10"],
                "generated_p90": gen_stat["p90"],
                "real_n": real_stat["n"],
                "real_mean": real_stat["mean"],
                "real_median": real_stat["median"],
                "real_p10": real_stat["p10"],
                "real_p90": real_stat["p90"],
                "generated_display": "%s [%s, %s]" % (
                    fmt4(gen_stat["median"]), fmt4(gen_stat["p10"]), fmt4(gen_stat["p90"])),
                "real_display": "%s [%s, %s]" % (
                    fmt4(real_stat["median"]), fmt4(real_stat["p10"]), fmt4(real_stat["p90"])),
                "source_generated": "experiments/EXP-0109/samples.csv: chem__%s (repeat=0/1/2, design)"
                                    % column,
                "source_real": "data/clean/q3.csv: %s%s=%s" % (CHEM_PREFIX, column, style),
                "note": note,
            })

    sensory_rows = []
    for style in STYLES:
        style_gen = gen_sense[gen_sense["style"] == style]
        style_real = real[real[STYLE_COLUMN] == style]
        for column, item_cn, meaning in SENSORY_ITEMS:
            gen_stat = summarize(style_gen[column].to_numpy(dtype=float))
            real_stat = summarize(style_real[column].to_numpy(dtype=float))
            sensory_rows.append({
                "block": "sensory",
                "style": style,
                "item_cn": item_cn,
                "column": column,
                "tier": "sensory_proxy_label",
                "storage_scale": "standardized_label",
                "physical_inverse": "identity",
                "unit": "标准化感官标签单位（Z 分数，无物理单位）",
                "unit_declared": "yes",
                "generated_n": gen_stat["n"],
                "generated_mean": gen_stat["mean"],
                "generated_median": gen_stat["median"],
                "generated_p10": gen_stat["p10"],
                "generated_p90": gen_stat["p90"],
                "real_n": real_stat["n"],
                "real_mean": real_stat["mean"],
                "real_median": real_stat["median"],
                "real_p10": real_stat["p10"],
                "real_p90": real_stat["p90"],
                "generated_display": "%s [%s, %s]" % (
                    fmt4(gen_stat["mean"]), fmt4(gen_stat["p10"]), fmt4(gen_stat["p90"])),
                "real_display": "%s [%s, %s]" % (
                    fmt4(real_stat["mean"]), fmt4(real_stat["p10"]), fmt4(real_stat["p90"])),
                "source_generated": "experiments/EXP-0109/sensory_profiles.csv: %s (stage=design, repeat=0/1/2)"
                                    % column,
                "source_real": "data/clean/q3.csv: %s=%s" % (column, style),
                "note": meaning,
            })

    chem = pd.DataFrame(chem_rows)
    sense = pd.DataFrame(sensory_rows)
    combined = pd.concat([chem, sense], ignore_index=True)
    return chem, sense, combined


def markdown_profile(chem: pd.DataFrame, sensory: pd.DataFrame, meta: dict) -> tuple:
    # ---- 化学片段 -------------------------------------------------------------------------
    rows = []
    for style in STYLES:
        block = chem[chem["style"] == style]
        for _, row in block.iterrows():
            rows.append([
                "%s（%s）" % (row["item_cn"], row["column"]),
                unit_scale_text(row["column"], meta),
                style,
                str(row["generated_n"]),
                row["generated_display"],
                str(row["real_n"]),
                row["real_display"],
            ])
    header = ["化合物（源列名）", "尺度/单位", "风格", "生成 n", "生成中位数 [P10, P90]",
              "实测 n", "实测中位数 [P10, P90]"]
    note = ("说明：生成侧 = EXP-0109 `samples.csv` 的 design 设计谱（copula-selected，3 个冻结重复池化，"
            "n=84/30/33 份），不是测量；实测侧 = `data/clean/q3.csv` 同风格真实训练行（n=28/10/11）。"
            "log10 校准列的物理值按 c=10^x 还原、线性校准列按 c=x 使用，单位取自 "
            "`data/processed/v6_feature_dictionary.csv` 的 unit_or_scale；未校准列保留存储尺度并在"
            "\u201c尺度/单位\u201d列标注\u201c存储尺度（未校准）\u201d。P10/P90 为线性插值。")
    tail = ("注：显示为 4 位有效数字，CSV 数值列保留全精度；所选 12 列在三风格真实行与生成谱中均无缺失、"
            "无地板码，故未触发非检测码按 0 计的换算。生成谱只表示条件生成与约束投影后的设计值，"
            "不能读作对某支真实啤酒的测量或预测。")
    chem_md = ("**表 q3-profile-chem　Tripel / Kriek / Lambic：关键化合物生成谱与真实训练分布对照**\n\n"
               + note + "\n\n" + md_table(header, rows, ["l", "l", "l", "r", "r", "r", "r"])
               + "\n\n" + tail + "\n")

    # ---- 感官片段 -------------------------------------------------------------------------
    rows = []
    for style in STYLES:
        block = sensory[sensory["style"] == style]
        for _, row in block.iterrows():
            rows.append([
                "%s（%s：%s）" % (row["item_cn"], row["column"], row["note"]),
                style,
                str(row["generated_n"]),
                row["generated_display"],
                str(row["real_n"]),
                row["real_display"],
            ])
    header = ["感官维度（代理列名：含义）", "风格", "生成 n", "生成均值 [P10, P90]",
              "实测 n", "实测均值 [P10, P90]"]
    note = ("说明：生成侧 = EXP-0109 `sensory_profiles.csv` stage=design 的 50 维岭回归标签代理对设计谱的"
            "预测（3 个冻结重复池化，n=84/30/33），不是感官测量；实测侧 = `data/clean/q3.csv` 同风格真实"
            "训练标签（n=28/10/11）。代理维度按列名取：A_malt_all=香气·麦芽总体强度、A_hops_all=香气·"
            "酒花总体强度、A_esters_all=香气·酯类总体强度、acidity=酸度、overall=总体。标签为标准化 Z 分数，"
            "无物理单位；P10/P90 为线性插值。")
    tail = ("注：生成侧仅说明代理模型对生成谱的读法，不表示消费者感官实测；两栏样本量不同（生成 3 重复 × "
            "真实行数），区间宽度不可直接比较。显示 4 位有效数字，CSV 保留全精度。")
    sensory_md = ("**表 q3-profile-sensory　Tripel / Kriek / Lambic：核心感官代理生成值与真实训练分布对照**\n\n"
                  + note + "\n\n" + md_table(header, rows, ["l", "l", "r", "r", "r", "r"])
                  + "\n\n" + tail + "\n")

    return chem_md, sensory_md


# --------------------------------------------------------------------------------------------- 表 2
def pick_representative(transfers: pd.DataFrame, outputs: dict) -> pd.Series:
    protocol = outputs.get("protocol", {})
    if protocol.get("sourceStyle") != "Pils/Lager" or protocol.get("targetStyle") != "Tripel":
        fail("EXP-0110 协议不是 Pils/Lager→Tripel")
    eligible = sorted(int(beer) for beer in protocol.get("sourceBeers", []))
    if not eligible:
        fail("transfer_outputs.json 未记录 sourceBeers")
    chosen_beer = eligible[0]
    block = transfers[(transfers["repeat"] == 0) & (transfers["fold"] == 0)
                      & (transfers["source_beer"] == chosen_beer)]
    primary = block[block["strategy"] == PRIMARY_STRATEGY]
    if len(primary) != 1:
        fail("代表源记录不唯一：repeat=0/fold=0/source_beer=%d/%s 命中 %d 行"
             % (chosen_beer, PRIMARY_STRATEGY, len(primary)))
    row = primary.iloc[0]
    if row["status"] != "optimal" or not bool(row["feasible"]) or bool(row["fallback_to_source"]):
        fail("代表源 QP 不是 optimal/feasible/非回退：status=%r feasible=%r fallback=%r"
             % (row["status"], row["feasible"], row["fallback_to_source"]))
    expected_id = "R0-F0-B%03d-%s" % (chosen_beer, PRIMARY_STRATEGY)
    if str(row["transfer_id"]) != expected_id:
        fail("代表源 transfer_id 不符：%r != %r" % (row["transfer_id"], expected_id))
    return row, eligible


def build_transfer_example(data: dict) -> tuple:
    transfers = data["transfers"]
    rows_in = data["q3"]
    sources = data["sources"]
    thresholds = data["thresholds"]
    meta = data["meta"]
    row, eligible = pick_representative(transfers, data["outputs"])
    chosen_beer = int(row["source_beer"])

    # 源值 = q3 训练表中该啤酒的存储值（本表 12 列均为实测，src__ 与训练表逐格一致）
    beer_row = rows_in[rows_in["beer"] == chosen_beer]
    if len(beer_row) != 1:
        fail("q3.csv 中 beer=%d 行数不为 1" % chosen_beer)
    beer_row = beer_row.iloc[0]

    records = []
    # ---- (a) 关键化合物 -------------------------------------------------------------------
    for column, item_cn, note in CHEM_ITEMS:
        stored_key = CHEM_PREFIX + column
        source_stored = float(row["src__" + stored_key])
        ref_stored = float(row["ref__" + stored_key])
        post_stored = float(row["opt__" + stored_key])
        training_stored = float(beer_row[stored_key])
        if not np.isclose(source_stored, training_stored, rtol=1e-9, atol=1e-12):
            fail("源值 src__%s 与 q3.csv 训练值不一致：%r vs %r"
                 % (stored_key, source_stored, training_stored))
        calibrated = column in LOG10_SET or column in LINEAR_SET
        source_value = float(to_physical(column, [source_stored])[0])
        ref_value = float(to_physical(column, [ref_stored])[0])
        post_value = float(to_physical(column, [post_stored])[0])
        delta = post_value - source_value
        scale = ("physical" if calibrated else "storage_uncalibrated")
        records.append({
            "section": "flavour",
            "item_cn": item_cn,
            "column": stored_key,
            "tier": str(meta[column]["tier"]),
            "storage_scale": str(meta[column]["storage_scale"]),
            "unit": str(meta[column]["unit_or_scale"]) if calibrated else "未声明",
            "unit_declared": "yes" if calibrated else "no",
            "src_stored": source_stored,
            "src_physical": source_value,
            "anchor_status": "not_persisted",
            "anchor_stored": np.nan,
            "anchor_physical": np.nan,
            "ref_stored": ref_stored,
            "ref_physical": ref_value,
            "cap_physical": np.nan,
            "post_stored": post_stored,
            "post_physical": post_value,
            "delta_physical": delta,
            "value_scale": "physical" if calibrated else "storage_uncalibrated",
            "delta_scale": "physical" if calibrated else "storage_uncalibrated",
            "nonincrease": "",
            "source_state": "measured",
            "source_state_detail": "q3.csv 实测存储值",
            "threshold_mean": np.nan,
            "threshold_median": np.nan,
            "source_record": "experiments/EXP-0110/transfers.csv: %s/src__%s/ref__%s/opt__%s @ %s"
                             % (PRIMARY_STRATEGY, stored_key, stored_key, stored_key, row["transfer_id"]),
            "note": note if note else ("Δ=opt−src；非不增约束列，允许增大" if calibrated else ""),
            "src_display": fmt4(source_value),
            "ref_display": fmt4(ref_value),
            "post_display": fmt4(post_value),
            "delta_display": fmt4(delta, tiny_zero=TRANSFER_TRUNC),
        })

    # ---- (b) 五类缺陷 ---------------------------------------------------------------------
    cap_con = data["constraints"]
    cap_con = cap_con[(cap_con["strategy"] == PRIMARY_STRATEGY) & (cap_con["bound_type"] == "upper_source_value")]
    tsrc = sources[(sources["repeat"] == 0) & (sources["fold"] == 0)
                   & (sources["source_beer"] == chosen_beer)]
    if len(tsrc) != len(DEFECT_ITEMS):
        fail("transfer_sources.csv 中代表源行数不是 4")
    state_map = dict(zip(tsrc["column"], tsrc["source_state"]))
    state_text = {"measured": "实测", "imputed_training_median": "缺失（训练折中位数填补）",
                  "floor_coded": "地板码（非检测）"}
    for name, item_cn, bound_type in DEFECT_ITEMS:
        column = CHEM_PREFIX + name
        state = str(state_map[column])
        physical_source = float(row[name + "_physical_source"])
        physical_new = float(row[name + "_physical_new"])
        ref_physical = float(to_physical(name, [float(row["ref__" + column])])[0])
        nonincrease = bool(row[name + "_nonincreasing"])
        threshold = thresholds["defects"][name]
        unit = str(threshold["unit"])
        records.append({
            "section": "defect",
            "item_cn": item_cn,
            "column": column,
            "tier": str(threshold["tier"]),
            "storage_scale": ("log10" if threshold["tier"] == "calibrated_log10" else "linear"),
            "unit": "物理：%s（%s校准）" % (unit, "log10" if threshold["tier"] == "calibrated_log10" else "线性"),
            "unit_declared": "yes",
            "src_stored": float(row[name + "_stored_source"]),
            "src_physical": physical_source,
            "anchor_status": "not_persisted",
            "anchor_stored": np.nan,
            "anchor_physical": np.nan,
            "ref_stored": float(row["ref__" + column]),
            "ref_physical": ref_physical,
            "cap_physical": physical_source,
            "post_stored": float(row[name + "_stored_new"]),
            "post_physical": physical_new,
            "delta_physical": physical_new - physical_source,
            "value_scale": "physical",
            "delta_scale": "physical",
            "nonincrease": "true" if nonincrease else "false",
            "source_state": state,
            "source_state_detail": state_text.get(state, state),
            "threshold_mean": float(threshold["thresholdMean"]) if threshold["thresholdMean"] is not None else np.nan,
            "threshold_median": float(threshold["thresholdMedian"])
            if threshold["thresholdMedian"] is not None else np.nan,
            "source_record": "experiments/EXP-0110/transfer_sources.csv: %s @ repeat=0/fold=0/source_beer=%d; "
                             "transfers.csv: %s_physical_source/_new/_nonincreasing"
                             % (column, chosen_beer, name),
            "note": "源值上限=源值本身；QP 只保证不增，不保证低于感官阈值",
            "src_display": fmt4(physical_source),
            "ref_display": fmt4(ref_physical),
            "post_display": fmt4(physical_new),
            "delta_display": fmt4(physical_new - physical_source, tiny_zero=TRANSFER_TRUNC),
        })

    # 老化酒花代理（stale_hops 岭回归分数，不是化学测量）
    stale_source = float(row["stale_hops_source"])
    stale_new = float(row["stale_hops_new"])
    stale_b = float(row["stale_halfspace_b"])
    stale_azs = float(row["stale_a_dot_source"])
    records.append({
        "section": "defect",
        "item_cn": "老化酒花代理（岭回归）",
        "column": PROXY_FIELD,
        "tier": "sensory_label_proxy",
        "storage_scale": "standardized_label_proxy",
        "unit": "代理分数（标准化感官标签单位）",
        "unit_declared": "no",
        "src_stored": np.nan,
        "src_physical": stale_source,
        "anchor_status": "not_applicable_proxy",
        "anchor_stored": np.nan,
        "anchor_physical": np.nan,
        "ref_stored": np.nan,
        "ref_physical": np.nan,
        "cap_physical": stale_b,
        "post_stored": np.nan,
        "post_physical": stale_new,
        "delta_physical": stale_new - stale_source,
        "value_scale": "proxy_score",
        "delta_scale": "proxy_score",
        "nonincrease": "true" if bool(row["stale_hops_nonincreasing"]) else "false",
        "source_state": "proxy",
        "source_state_detail": "训练折内岭回归代理分数（PROXY，不是测量）",
        "threshold_mean": np.nan,
        "threshold_median": np.nan,
        "source_record": "experiments/EXP-0110/transfers.csv: stale_hops_source/new/nonincreasing, "
                         "stale_a_dot_source, stale_halfspace_b @ %s" % row["transfer_id"],
        "note": "约束为半空间 a'z<=b，b=%.12g=a'z_source+1e-9；b 不是浓度" % stale_b,
        "src_display": fmt4(stale_source),
        "ref_display": "—",
        "post_display": fmt4(stale_new),
        "delta_display": fmt4(stale_new - stale_source, tiny_zero=TRANSFER_TRUNC),
    })

    # ---- (c) 感官代理：迁移管线只记录 2 个缺陷代理分数 -----------------------------------
    t2n_source = float(row["t2n_source"])
    t2n_new = float(row["t2n_new"])
    records.append({
        "section": "sensory_proxy",
        "item_cn": "老化酒花代理",
        "column": "stale_hops(ridge-proxy)",
        "tier": "sensory_label_proxy",
        "storage_scale": "standardized_label_proxy",
        "unit": "代理分数（标准化感官标签单位）",
        "unit_declared": "no",
        "src_stored": np.nan,
        "src_physical": stale_source,
        "anchor_status": "not_applicable_proxy",
        "anchor_stored": np.nan,
        "anchor_physical": np.nan,
        "ref_stored": np.nan,
        "ref_physical": np.nan,
        "cap_physical": stale_b,
        "post_stored": np.nan,
        "post_physical": stale_new,
        "delta_physical": stale_new - stale_source,
        "value_scale": "proxy_score",
        "delta_scale": "proxy_score",
        "nonincrease": "true" if bool(row["stale_hops_nonincreasing"]) else "false",
        "source_state": "recorded_proxy",
        "source_state_detail": "迁移管线记录的岭回归代理分数",
        "threshold_mean": np.nan,
        "threshold_median": np.nan,
        "source_record": "experiments/EXP-0110/transfers.csv: stale_hops_source/new/nonincreasing",
        "note": "QP 半空间约束行；不增在 1e-9 容差内成立",
        "src_display": fmt4(stale_source),
        "ref_display": "—",
        "post_display": fmt4(stale_new),
        "delta_display": fmt4(stale_new - stale_source, tiny_zero=TRANSFER_TRUNC),
    })
    records.append({
        "section": "sensory_proxy",
        "item_cn": "反-2-壬烯醛感官代理",
        "column": "t2n(ridge-proxy)",
        "tier": "sensory_label_proxy",
        "storage_scale": "standardized_label_proxy",
        "unit": "代理分数（标准化感官标签单位）",
        "unit_declared": "no",
        "src_stored": np.nan,
        "src_physical": t2n_source,
        "anchor_status": "not_applicable_proxy",
        "anchor_stored": np.nan,
        "anchor_physical": np.nan,
        "ref_stored": np.nan,
        "ref_physical": np.nan,
        "cap_physical": np.nan,
        "post_stored": np.nan,
        "post_physical": t2n_new,
        "delta_physical": t2n_new - t2n_source,
        "value_scale": "proxy_score",
        "delta_scale": "proxy_score",
        "nonincrease": "",
        "source_state": "recorded_proxy",
        "source_state_detail": "迁移管线记录的岭回归代理分数（仅诊断，不是约束）",
        "threshold_mean": np.nan,
        "threshold_median": np.nan,
        "source_record": "experiments/EXP-0110/transfers.csv: t2n_source/new/increasing",
        "note": "仅诊断；t2n 不是 QP 约束，不能替代真实化学反-2-壬烯醛不增",
        "src_display": fmt4(t2n_source),
        "ref_display": "—",
        "post_display": fmt4(t2n_new),
        "delta_display": fmt4(t2n_new - t2n_source, tiny_zero=TRANSFER_TRUNC),
    })
    for column, item_cn, meaning in SENSORY_ITEMS:
        records.append({
            "section": "core_sensory_unavailable",
            "item_cn": item_cn,
            "column": column,
            "tier": "sensory_label_proxy",
            "storage_scale": "standardized_label",
            "unit": "标准化感官标签单位",
            "unit_declared": "yes",
            "src_stored": np.nan,
            "src_physical": np.nan,
            "anchor_status": "not_applicable",
            "anchor_stored": np.nan,
            "anchor_physical": np.nan,
            "ref_stored": np.nan,
            "ref_physical": np.nan,
            "cap_physical": np.nan,
            "post_stored": np.nan,
            "post_physical": np.nan,
            "delta_physical": np.nan,
            "value_scale": "not_recorded",
            "delta_scale": "not_recorded",
            "nonincrease": "",
            "source_state": "not_recorded",
            "source_state_detail": "EXP-0110 迁移管线只落盘 stale_hops 与 t2n 两个代理分数，未记录核心 50 维",
            "threshold_mean": np.nan,
            "threshold_median": np.nan,
            "source_record": "—（EXP-0110 产物中无该列）",
            "note": "—：迁移管线未记录该核心感官代理，不臆造",
            "src_display": "—",
            "ref_display": "—",
            "post_display": "—",
            "delta_display": "—",
        })

    frame = pd.DataFrame(records)
    return frame, row, chosen_beer, eligible


def markdown_transfer(frame: pd.DataFrame, row: pd.Series, chosen_beer: int, eligible: list,
                      meta: dict) -> str:
    flavour = frame[frame["section"] == "flavour"]
    defects = frame[frame["section"] == "defect"]
    proxies = frame[frame["section"] == "sensory_proxy"]
    core = frame[frame["section"] == "core_sensory_unavailable"]

    rows_a = []
    for _, item in flavour.iterrows():
        plain_column = item["column"][len(CHEM_PREFIX):]
        if item["unit_declared"] == "yes":
            scale_unit = unit_scale_text(plain_column, meta)
        else:
            scale_unit = "存储尺度（未校准），单位未声明"
        rows_a.append([item["item_cn"] + "（" + item["column"] + "）", scale_unit,
                       item["src_display"], "—", item["ref_display"],
                       item["post_display"], item["delta_display"]])
    header_a = ["化合物（源列名）", "尺度/单位", "源值 src", "分位数锚点", "目标参考值 ref（非锚点）",
                "迁移后 opt", "Δ（opt−src）"]

    rows_b = []
    for _, item in defects.iterrows():
        if item["column"] == PROXY_FIELD:
            rows_b.append([item["item_cn"], item["source_state_detail"], item["unit"],
                           item["src_display"], "a'z≤b，b=%s" % fmt4(item["cap_physical"]),
                           item["ref_display"], item["post_display"], item["delta_display"], "✓"])
        else:
            threshold = ("—" if item["threshold_mean"] is None or not np.isfinite(item["threshold_mean"])
                         else fmt4(item["threshold_mean"]))
            rows_b.append([item["item_cn"] + "（" + item["column"] + "）",
                           item["source_state_detail"], item["unit"], item["src_display"],
                           "%s（源值上限）" % item["src_display"],
                           item["ref_display"], item["post_display"], item["delta_display"],
                           "✓" if item["nonincrease"] == "true" else "✗"])
    header_b = ["缺陷项（源列名）", "源状态（transfer_sources.csv）", "单位", "源值", "源值上限",
                "目标参考值 ref（非锚点）", "迁移后", "Δ", "不增"]

    rows_c = []
    for _, item in proxies.iterrows():
        rows_c.append([item["item_cn"], item["column"], item["src_display"], item["post_display"],
                       item["delta_display"], "已记录（代理分数，非测量）"])
    for _, item in core.iterrows():
        rows_c.append([item["item_cn"], item["column"], "—", "—", "—", "未记录（不臆造）"])
    header_c = ["感官代理", "代理列名", "源值", "迁移后", "Δ", "记录状态"]

    note = ("说明：代表源按固定规则选取 —— repeat=0（冻结种子 20261025）、外层 fold=0、在 %d 支 Pils/Lager "
            "源啤酒（id=%s）中取最小 id = %d；交付策略为 %s，transfer_id=%s（status=optimal、feasible=True、"
            "fallback=False、约束违反 0）。源值取 `transfers.csv` 的 src__chem__（对 12 个化合物与 `data/clean/"
            "q3.csv` 训练表逐格一致），迁移后取 opt__chem__，目标参考值取 ref__chem__（=centre+scale·z̄，"
            "是目标风格参考均值，**不是分位数锚点**）。log10 校准列按 c=10^x、线性校准列按 c=x 显示物理值；"
            "4-松油醇未校准，按存储尺度显示。"
            % (len(eligible), ",".join(str(b) for b in eligible), chosen_beer,
               PRIMARY_STRATEGY, row["transfer_id"]))

    anchor_note = ("**分位数锚点列为什么是 \u201c—\u201d**：EXP-0110 只在 `transfers.csv` 落盘锚点标签"
                   " anchor=quantile，没有落盘锚点向量；`marginal_state.csv` 只有每（风格，列）的计数、"
                   "omega 与地板质量点（n_valid/n_continuous/n_floor/omega/kappa/pi），没有 `Marginal.inverse` "
                   "所需的支撑点 grid_x/grid_u；`solver_certificates.jsonl` 只存 problem_hash。因此锚点向量"
                   "**无法**从已保存产物重建；该结论对 (a) 的 12 个化合物与 (b) 的 4 个化学缺陷列同样成立；"
                   "表中给出最近的可持久化参照 ref__chem__ 并明确标注它不是锚点。"
                   "要得到精确锚点必须重拟合边际（属于重跑管线，本次按只读产物口径不做）。")

    dms_row = defects[defects["column"] == CHEM_PREFIX + "DMS"].iloc[0]
    linalool_row = flavour[flavour["column"] == CHEM_PREFIX + "linalool"].iloc[0]
    tail = ("注：Δ 为 opt−src；|Δ|<1e-12 显示为 0（数值噪声）。缺陷项不增=QP 构造性质"
            "（upper_source_value / stale 半空间），不代表低于感官阈值：该源 DMS 源值 %s %s 已高于"
            "阈值 Mean %s %s。未被源值上限约束的化合物允许移动，例如芳樟醇 %s→%s mg/L（目标参考 %s），"
            "其设计值由 QP 目标与箱约束共同决定，不能读作目标风格的典型浓度。核心 5 维感官代理"
            "（麦芽/酒花/酯/酸度/总体）在 EXP-0110 产物中不存在前后对照，不能用其它代理替代。"
            % (dms_row["src_display"], dms_row["unit"].replace("物理：", "").split("（")[0],
               fmt4(dms_row["threshold_mean"]),
               dms_row["unit"].replace("物理：", "").split("（")[0],
               linalool_row["src_display"], linalool_row["post_display"], linalool_row["ref_display"]))

    body = ("**表 q3-transfer-example　Pils/Lager→Tripel 单源迁移示例（B%03d / repeat 0 / fold 0 / %s）**\n\n"
            % (chosen_beer, PRIMARY_STRATEGY) + note + "\n\n（a）关键化合物：源值、目标参考值与迁移后设计值\n\n"
            + md_table(header_a, rows_a, ["l", "l", "r", "r", "r", "r", "r"])
            + "\n\n（b）五类缺陷：源状态、源值上限、不增标记\n\n"
            + md_table(header_b, rows_b, ["l", "l", "l", "r", "r", "r", "r", "r", "l"])
            + "\n\n（c）感官代理：迁移管线记录的两类代理与未记录的核心维度\n\n"
            + md_table(header_c, rows_c, ["l", "l", "r", "r", "r", "l"])
            + "\n\n" + anchor_note + "\n\n" + tail + "\n")
    return body


# --------------------------------------------------------------------------------------------- 表 3
def build_defect_control(data: dict) -> tuple:
    transfers = data["transfers"]
    sources = data["sources"]
    verdicts = data["verdicts"]
    constraints = data["constraints"]
    thresholds = data["thresholds"]
    meta = data["meta"]

    primary = transfers[transfers["strategy"] == PRIMARY_STRATEGY]
    if len(primary) != 99:
        fail("主策略记录数不是 99：%d" % len(primary))
    primary_con = constraints[constraints["strategy"] == PRIMARY_STRATEGY]
    if len(primary_con) != 3762:
        fail("主策略约束记录数不是 3762：%d" % len(primary_con))

    # ---- 3762 分解 ----------------------------------------------------------------
    decomposition = {str(k): int(v) for k, v in primary_con["bound_type"].value_counts().items()}
    expected = {"lower_zero": 3267, "upper_source_value": 396, "upper_source_value_proxy": 99}
    for key, value in expected.items():
        if decomposition.get(key) != value:
            fail("3762 分解不符：%s=%r，期望 %d" % (key, decomposition.get(key), value))
    if sum(decomposition.values()) != 3762:
        fail("3762 分解总和不为 3762：%r" % decomposition)

    # ---- 四类核验的总体口径 --------------------------------------------------------
    prim_verdict = verdicts[verdicts["strategy"] == PRIMARY_STRATEGY]
    if int(prim_verdict["n"].sum()) != 3762:
        fail("transfer_verdicts.csv 主策略 n 合计不是 3762：%d" % int(prim_verdict["n"].sum()))
    verdict_totals = {str(k): int(v) for k, v in
                      prim_verdict.groupby("verdict")["n"].sum().items()}
    overall = {
        "verified": verdict_totals.get("verified", 0),
        "conditional": verdict_totals.get("conditional", 0),
        "not_identifiable": verdict_totals.get("not_identifiable", 0),
        "failed": verdict_totals.get("failed", 0),
    }
    if overall != {"verified": 3465, "conditional": 198, "not_identifiable": 99, "failed": 0}:
        fail("主策略四类核验总数与论文 qp-certs 表不一致：%r" % overall)

    # 每个上界字段的四类计数（bound_type 取实际约束行，避免 diacetyl/nonenal 的 lower_zero 行混入）
    def verdict_counts(field: str, bound_type: str) -> dict:
        block = prim_verdict[(prim_verdict["field"] == field) & (prim_verdict["bound_type"] == bound_type)]
        if len(block) != 4:
            fail("verdict 组不是 4 类：%s/%s 命中 %d 行" % (field, bound_type, len(block)))
        counts = {str(v): int(n) for v, n in zip(block["verdict"], block["n"])}
        denominator = int(block["denominator"].max())
        verified_denominator = int(block["verifiedDenominator"].max())
        return {
            "verified": counts.get("verified", 0),
            "conditional": counts.get("conditional", 0),
            "not_identifiable": counts.get("not_identifiable", 0),
            "failed": counts.get("failed", 0),
            "denominator": denominator,
            "verified_denominator": verified_denominator,
        }

    records = []
    for name, item_cn, bound_type in DEFECT_ITEMS:
        column = CHEM_PREFIX + name
        threshold = thresholds["defects"][name]
        unit = str(threshold["unit"])
        tier = str(threshold["tier"])
        source_block = sources[sources["column"] == column]
        if len(source_block) != 99:
            fail("transfer_sources.csv 中 %s 记录数不是 99" % column)
        state_counts = {str(k): int(v) for k, v in source_block["source_state"].value_counts().items()}
        counts = verdict_counts(column, bound_type)
        cap_block = primary_con[(primary_con["field"] == column)
                                & (primary_con["bound_type"] == "upper_source_value")]
        above = int((primary[name + "_physical_source"].to_numpy(dtype=float)
                     > float(threshold["thresholdMean"])).sum()) if threshold["thresholdMean"] is not None else None
        above_measured = None
        if threshold["thresholdMean"] is not None:
            measured_mask = np.ones(len(primary), dtype=bool)
            state_lookup = dict(zip(zip(source_block["repeat"], source_block["fold"], source_block["source_beer"]),
                                    source_block["source_state"]))
            for index, source_row in primary.reset_index(drop=True).iterrows():
                key = (int(source_row["repeat"]), int(source_row["fold"]), int(source_row["source_beer"]))
                measured_mask[index] = state_lookup.get(key, "missing") == "measured"
            above_measured = int(((primary[name + "_physical_source"].to_numpy(dtype=float)
                                   > float(threshold["thresholdMean"])) & measured_mask).sum())
        records.append({
            "item_cn": item_cn,
            "column": column,
            "tier": tier,
            "storage_scale": ("log10" if tier == "calibrated_log10" else "linear"),
            "physical_inverse": ("10**x" if tier == "calibrated_log10" else "x"),
            "unit": unit,
            "unit_declared": "yes",
            "unit_source": "data/clean/q3_thresholds.json: defects.%s.unit" % name,
            "threshold_mean": threshold["thresholdMean"],
            "threshold_median": threshold["thresholdMedian"],
            "threshold_source": "data/clean/q3_thresholds.json: defects.%s.thresholdMean / thresholdMedian" % name,
            "constraint_type": bound_type,
            "constraint_source": "experiments/EXP-0110/transfer_constraints.csv: bound_type=upper_source_value, "
                                 "bound_value_physical（n=%d）" % len(cap_block),
            "constraint_value_min": float(cap_block["bound_value_physical"].min()) if len(cap_block) else np.nan,
            "constraint_value_max": float(cap_block["bound_value_physical"].max()) if len(cap_block) else np.nan,
            "n_source_records": int(len(source_block)),
            "n_measured": state_counts.get("measured", 0),
            "n_missing_imputed": state_counts.get("imputed_training_median", 0),
            "n_floor": state_counts.get("floor_coded", 0),
            "n_proxy": 0,
            "source_state_note": "transfer_sources.csv 的 source_state（99 = 3 重复 × 3 折 × 11 支源啤酒）",
            "n_records": int(sum(counts[k] for k in
                                 ("verified", "conditional", "not_identifiable", "failed"))),
            "n_verified": counts["verified"],
            "n_conditional": counts["conditional"],
            "n_not_identifiable": counts["not_identifiable"],
            "n_failed": counts["failed"],
            "denominator": counts["denominator"],
            "verified_denominator": counts["verified_denominator"],
            "n_source_above_threshold_mean": above,
            "n_measured_source_above_threshold_mean": above_measured,
            "note": ("源值上限即源值；QP 不保证低于阈值" if bound_type == "upper_source_value" else ""),
            "unit_consistency_note": "",
        })

    # 老化酒花代理 ---------------------------------------------------------------
    stale_block = primary_con[primary_con["bound_type"] == "upper_source_value_proxy"]
    if len(stale_block) != 99:
        fail("stale 代理记录数不是 99：%d" % len(stale_block))
    stale_counts = verdict_counts(PROXY_FIELD, "upper_source_value_proxy")
    stale_b = primary["stale_halfspace_b"].to_numpy(dtype=float)
    records.append({
        "item_cn": "老化酒花代理（岭回归）",
        "column": PROXY_FIELD,
        "tier": "sensory_label_proxy",
        "storage_scale": "standardized_label_proxy",
        "physical_inverse": "identity（代理分数）",
        "unit": "ridge-proxy score（标准化感官标签单位）",
        "unit_declared": "no",
        "unit_source": "data/clean/q3_thresholds.json: defects.stale_hops.unit（仅声明为感官标签单位）",
        "threshold_mean": np.nan,
        "threshold_median": np.nan,
        "threshold_source": "无阈值：q3_thresholds.json defects.stale_hops.thresholdMean/thresholdMedian 均为 null",
        "constraint_type": "upper_source_value_proxy（半空间 a'z<=b）",
        "constraint_source": "experiments/EXP-0110/transfers.csv: stale_halfspace_b / stale_a_dot_source "
                             "（主策略 99 行）；solver_certificates.jsonl 同样记录 b",
        "constraint_value_min": float(stale_b.min()),
        "constraint_value_max": float(stale_b.max()),
        "n_source_records": 99,
        "n_measured": 0,
        "n_missing_imputed": 0,
        "n_floor": 0,
        "n_proxy": 99,
        "source_state_note": "代理分数，非测量；transfer_sources.csv 只覆盖 4 个化学列",
        "n_records": int(sum(stale_counts[k] for k in
                             ("verified", "conditional", "not_identifiable", "failed"))),
        "n_verified": stale_counts["verified"],
        "n_conditional": stale_counts["conditional"],
        "n_not_identifiable": stale_counts["not_identifiable"],
        "n_failed": stale_counts["failed"],
        "denominator": stale_counts["denominator"],
        "verified_denominator": stale_counts["verified_denominator"],
        "n_source_above_threshold_mean": None,
        "n_measured_source_above_threshold_mean": None,
        "note": "b=a'z_source+1e-9；半空间约束是训练折内代理，不是化学/感官测量",
        "unit_consistency_note": "",
    })

    # 已知文本矛盾：transfer_constraints.csv 的 unit 列把 nonenal 写成 "unit NOT declared"，
    # 但 q3_thresholds.json 实际声明 mg/L。这里如实记录，表 3 采用阈值文件的声明。
    nonenal_string = constraints[(constraints["field"] == CHEM_PREFIX + "X.E..2.nonenal")
                                 & (constraints["bound_type"] == "upper_source_value")]["unit"].unique().tolist()
    if not any("NOT declared" in str(value) for value in nonenal_string):
        fail("未复现 transfer_constraints.csv 的 nonenal unit 审计字符串")
    nonenal_record = next(r for r in records if r["column"] == CHEM_PREFIX + "X.E..2.nonenal")
    nonenal_record["unit_consistency_note"] = (
        "transfer_constraints.csv 的 unit 列写作 %r，与 q3_thresholds.json 声明的 %s 不一致；"
        "本表采用阈值文件的声明。" % (nonenal_string[0], nonenal_record["unit"]))

    frame = pd.DataFrame(records)

    # 五个策略的 stale 代理核验差异（仅箱约束参照会在代理上失败）
    strategy_stale = {}
    for strategy, block in verdicts.groupby("strategy"):
        stale_rows = block[(block["field"] == PROXY_FIELD) & (block["bound_type"] == "upper_source_value_proxy")]
        strategy_stale[strategy] = {
            "conditional": int(stale_rows[stale_rows["verdict"] == "conditional"]["n"].sum()),
            "failed": int(stale_rows[stale_rows["verdict"] == "failed"]["n"].sum()),
        }

    lower_verified = int(prim_verdict[(prim_verdict["bound_type"] == "lower_zero")
                                      & (prim_verdict["verdict"] == "verified")]["n"].sum())
    upper_verified = int(prim_verdict[(prim_verdict["bound_type"] == "upper_source_value")
                                      & (prim_verdict["verdict"] == "verified")]["n"].sum())
    context = {
        "decomposition": decomposition,
        "overall": overall,
        "lower_zero_verified": lower_verified,
        "upper_bound_verified": upper_verified,
        "strategy_stale": strategy_stale,
        "constraint_rows_total": int(len(constraints)),
        "n_strategies": int(constraints["strategy"].nunique()),
        "n_lower_fields": int(primary_con[primary_con["bound_type"] == "lower_zero"]["field"].nunique()),
        "n_defect_caps": int(primary_con[primary_con["bound_type"] == "upper_source_value"]["field"].nunique()),
    }
    return frame, context


def markdown_defect_control(frame: pd.DataFrame, context: dict) -> str:
    chemical = frame[frame["column"] != PROXY_FIELD]

    rows_a = []
    for _, item in chemical.iterrows():
        threshold_mean = "—" if not np.isfinite(item["threshold_mean"]) else fmt4(item["threshold_mean"])
        threshold_median = "—" if not np.isfinite(item["threshold_median"]) else fmt4(item["threshold_median"])
        above_value = item["n_source_above_threshold_mean"]
        above = ("—" if (above_value is None or not np.isfinite(above_value))
                 else "%d（实测 %d）" % (int(above_value),
                                        int(item["n_measured_source_above_threshold_mean"])))
        rows_a.append([
            "%s（%s）" % (item["item_cn"], item["column"]),
            "%s（%s，c=%s）" % (item["unit"], item["storage_scale"], item["physical_inverse"]),
            "Mean %s / Median %s" % (threshold_mean, threshold_median),
            "源值上限 upper_source_value（transfer_constraints.csv，%d 条）" % int(item["n_records"]),
            "%d / %d / %d" % (item["n_measured"], item["n_missing_imputed"], item["n_floor"]),
            above,
        ])
    proxy = frame[frame["column"] == PROXY_FIELD].iloc[0]
    rows_a.append([
        "老化酒花代理（%s）" % PROXY_FIELD,
        "ridge-proxy 分数（标准化感官标签单位）",
        "无（null）",
        "半空间 a'z≤b（b=%.6g…%.6g，主策略 99 条）" % (proxy["constraint_value_min"],
                                                    proxy["constraint_value_max"]),
        "0 / 0 / 0；代理 99",
        "—（代理非浓度）",
    ])
    header_a = ["缺陷项（源列名）", "尺度/单位", "阈值（q3_thresholds.json）", "本次实际约束与来源",
                "源状态 实测/缺失/地板", "源值超阈值 Mean（条/99）"]

    rows_b = []
    for _, item in frame.iterrows():
        bound_type = item["constraint_type"]
        short_type = ("upper_source_value_proxy" if bound_type == "upper_source_value_proxy"
                      else bound_type)
        rows_b.append([
            "%s（%s）" % (item["item_cn"], short_type),
            str(item["n_verified"]), str(item["n_conditional"]), str(item["n_not_identifiable"]),
            str(item["n_failed"]), str(item["denominator"]), str(item["verified_denominator"]),
        ])
    upper_records = int(frame["n_records"].sum())
    upper_ver = int(frame["n_verified"].sum())
    upper_cond = int(frame["n_conditional"].sum())
    upper_not = int(frame["n_not_identifiable"].sum())
    upper_fail = int(frame["n_failed"].sum())
    upper_den = int(frame["denominator"].sum())
    upper_vden = int(frame["verified_denominator"].sum())
    rows_b.append(["合计（五类上界记录）", str(upper_ver), str(upper_cond), str(upper_not),
                   str(upper_fail), str(upper_den), str(upper_vden)])
    header_b = ["缺陷项（约束类型）", "已验证 verified", "条件成立 conditional", "不可识别 not_identifiable",
                "失败 failed", "分母", "可核验分母"]

    decomposition = context["decomposition"]
    overall = context["overall"]
    total_rows = context["constraint_rows_total"]
    n_strategies = context["n_strategies"]
    stale = context["strategy_stale"]
    other_stale = {k: v for k, v in stale.items() if k != "target-mean-projection"}

    note = ("说明：本表按交付策略 %s 统计。`transfer_verdicts.csv` 的 n / denominator / verifiedDenominator "
            "按（strategy, field, bound_type, verdict）落盘；这里每个缺陷项取**实际约束行**"
            "（四个化学缺陷取 upper_source_value，代理取 upper_source_value_proxy），不把同名列的 lower_zero "
            "下界行混入。分母 99 = 3 重复 × 3 折 × 11 支源啤酒；可核验分母 = 分母 − 不可识别。"
            "源状态计数来自 `transfer_sources.csv`（每个化学列 99 行），代理不在该文件中，单独标 99 个代理分数。"
            % PRIMARY_STRATEGY)
    note += (" 尺度/单位与阈值来自 `data/clean/q3_thresholds.json` 的 defects.<名>.unit / tier / thresholdMean / "
             "thresholdMedian；实际约束值来自 `transfer_constraints.csv` 的 bound_value_physical 与 "
             "`transfers.csv` 的 stale_halfspace_b。"
             "✳ 注意：transfer_constraints.csv 的 unit 列把反-2-壬烯醛写成 \u201cunit NOT declared in "
             "q3_thresholds.json\u201d，但阈值文件实际声明 mg/L；本表采用阈值文件的声明，并保留这一审计字符串矛盾。")
    lower_zero_verified = context["lower_zero_verified"]
    check = ("**3762 条约束记录的分解核验**（`transfer_constraints.csv`，主策略 %s）："
             "记录总量 %d = lower_zero %d（%d 个线性校准列 × 99）+ upper_source_value %d（4 个化学缺陷 × 99）"
             "+ upper_source_value_proxy %d（老化酒花代理 × 99）；与论文表述 3267+396+99=3762 **完全一致**。"
             "全文件共 %d 行 = %d 个策略 × 3762 条，3762 是**每个策略**的记录集，不是全部策略的总和。"
             "四类核验合计：verified %d / conditional %d / not_identifiable %d / failed %d，可核验分母 %d，"
             "其中 verified %d = %d 条下界 + %d 条上界，与论文 qp-certs 表的 3465/198/99/0（分母 3663）"
             "一致。仅箱约束参照 target-mean-projection 在老化酒花代理上出现 conditional %d / failed %d 条，"
             "其余四个策略在该代理上 conditional 99 / failed 0，说明半空间行是有效约束。"
             % (PRIMARY_STRATEGY, sum(decomposition.values()), decomposition["lower_zero"],
                context["n_lower_fields"], decomposition["upper_source_value"],
                decomposition["upper_source_value_proxy"], total_rows, n_strategies,
                overall["verified"], overall["conditional"], overall["not_identifiable"], overall["failed"],
                overall["verified"] + overall["conditional"] + overall["not_identifiable"] + overall["failed"]
                - overall["not_identifiable"],
                overall["verified"],
                lower_zero_verified,
                overall["verified"] - lower_zero_verified,
                stale.get("target-mean-projection", {}).get("conditional", 0),
                stale.get("target-mean-projection", {}).get("failed", 0)))
    diacetyl = chemical[chemical["column"] == CHEM_PREFIX + "X2.3.butanedione"].iloc[0]
    diacetyl_imputed_above = (int(diacetyl["n_source_above_threshold_mean"])
                              - int(diacetyl["n_measured_source_above_threshold_mean"]))
    dms = chemical[chemical["column"] == CHEM_PREFIX + "DMS"].iloc[0]
    tail = ("注：不增/上界是模型构造性质，不是感官合格证明；四个化学缺陷的 QP 上界是**源值本身**，不是感官阈值，"
            "源值已超阈值时 QP 只保证不恶化（例如本批 99 个源中 DMS 有 %d 条源值已高于阈值 Mean %s ug/L）。"
            "老化酒花只有训练折内岭回归代理，不能读作实测老化指标；B 表中的 conditional 一律来自代理或"
            "存储尺度约定（反-2-壬烯醛线性校准、单位按阈值文件声明），not_identifiable 一律来自源格缺失或地板码。"
            "双乙酰源值超阈值 Mean 的 %d 条中，%d 条来自训练折中位数填补的缺失源格，只有 %d 条是实测源值。"
            % (int(dms["n_source_above_threshold_mean"]), fmt4(dms["threshold_mean"]),
               int(diacetyl["n_source_above_threshold_mean"]), diacetyl_imputed_above,
               int(diacetyl["n_measured_source_above_threshold_mean"])))

    body = ("**表 q3-defect-control　五类受控缺陷：尺度/单位、阈值与源值上限来源、源状态与核验记录构成**\n\n"
            + note + "\n\n（一）尺度、单位、阈值与实际约束来源\n\n"
            + md_table(header_a, rows_a, ["l", "l", "l", "l", "r", "r"])
            + "\n\n（二）核验记录构成（主交付策略 %s）\n\n" % PRIMARY_STRATEGY
            + md_table(header_b, rows_b, ["l", "r", "r", "r", "r", "r", "r"])
            + "\n\n" + check + "\n\n" + tail + "\n")
    return body


# --------------------------------------------------------------------------------------------- 报告
def build_report(paths: dict, transfer_frame: pd.DataFrame, chosen_beer: int, eligible: list,
                 profile_chem: pd.DataFrame, profile_sensory: pd.DataFrame,
                 defect_context: dict) -> str:
    n_chem = len(CHEM_ITEMS)
    n_sense = len(SENSORY_ITEMS)
    decomposition = defect_context["decomposition"]
    overall = defect_context["overall"]

    lines = []
    add = lines.append
    add("# Q3 三张实体答案表：生成报告（v6.2）")
    add("")
    add("由 `src/q3_v62_answer_tables.py` 从已保存产物自动生成；本文件中的数字均由脚本从 CSV/JSON 单元格计算，"
        "不含手抄值。脚本只读 `experiments/EXP-0109`、`experiments/EXP-0110`、`data/clean`、`data/processed`，"
        "不调用 modeling_* 插件，不读 `state/ledger.json`，不重训模型、不重拟合边际。")
    add("")
    add("## 1 交付清单")
    add("")
    add("| 文件 | 内容 | 行数/大小 |")
    add("| --- | --- | --- |")
    for key, path in paths.items():
        rows = ""
        if path.suffix == ".csv":
            rows = "%d 行（含表头）" % (sum(1 for _ in path.open(encoding="utf-8")))
        elif path.suffix == ".md":
            rows = "%d 行" % (sum(1 for _ in path.open(encoding="utf-8")))
        add("| `%s` | %s | %s |" % (path.name, key, rows))
    add("| `ANSWER_TABLES_REPORT.md` | 生成报告（本文件） | — |")
    add("")
    add("同时写入 `FINAL_SUBMISSION_v6.2/支撑材料/outputs/q3/v62_tables/`（同名文件）。")
    add("")
    add("## 2 代表源选择规则（表 2）")
    add("")
    add("固定规则：%s。" % TRANSFER_RULE)
    add("")
    add("- 协议来源：`experiments/EXP-0110/transfer_outputs.json` 的 `q3_transfer.protocol.sourceStyle=Pils/Lager`、"
        "`targetStyle=Tripel`、`sourceBeers=%s`。" % eligible)
    add("- 代表源：**beer=%d**，记录 `transfer_id=R0-F0-B%03d-%s`，status=optimal、feasible=True、"
        "fallback=False、约束违反 0。" % (chosen_beer, chosen_beer, PRIMARY_STRATEGY))
    add("- 来源行：`experiments/EXP-0110/transfers.csv`，键 = (repeat=0, fold=0, source_beer=%d, strategy=%s)。"
        % (chosen_beer, PRIMARY_STRATEGY))
    add("")
    add("## 3 表 1：profile 表的口径")
    add("")
    add("- 化学块（%d 化合物 × 3 风格）：生成侧 = `EXP-0109/samples.csv` 的 design 谱（copula-selected，3 个冻结"
        "重复池化，Tripel/Kriek/Lambic 分别 84/30/33 份）；实测侧 = `data/clean/q3.csv` 对应风格真实训练行"
        "（28/10/11 行）。生成侧给中位数 [P10,P90]，实测侧给中位数 [P10,P90]；CSV 同时保留 mean。" % n_chem)
    add("- 感官块（%d 维度 × 3 风格）：生成侧 = `EXP-0109/sensory_profiles.csv` 的 `stage=design` 50 维岭回归标签"
        "代理预测；实测侧 = `q3.csv` 的 50 维真实标签。生成侧给均值 [P10,P90]，实测侧给均值 [P10,P90]；"
        "CSV 同时保留中位数。" % n_sense)
    add("- 尺度：`data/processed/v6_feature_dictionary.csv` 的 tier/storage_scale/unit_or_scale；37 个 log10 校准列"
        "按 c=10^x 还原，33 个线性校准列按 c=x；其余 161 列为\u201c存储尺度（未校准）\u201d（表 1 中仅 4-松油醇"
        " terpinen.4.ol 属此类，用于展示该标注）。")
    add("- 百分位：numpy linear 插值 P10/P90；显示 4 位有效数字，CSV 数值列保留全精度。")
    add("")
    add("## 4 表 2 / 表 3：逐项溯源与不可得项")
    add("")
    add("| 输出块 | 数字 | 来源文件 | 列/键 | 变换 |")
    add("| --- | --- | --- | --- | --- |")
    add("| (a) 源值 | src | EXP-0110/transfers.csv | `src__chem__<col>` | 物理：log10→10^x，线性→x |")
    add("| (a) 目标参考值 | ref | EXP-0110/transfers.csv | `ref__chem__<col>` | 同上；ref=centre+scale·z̄，"
        "**不是分位数锚点** |")
    add("| (a) 迁移后 | opt | EXP-0110/transfers.csv | `opt__chem__<col>` | 同上 |")
    add("| (a) 分位数锚点 | — | 无 | `transfers.csv:anchor` 只有标签 `quantile` | 锚点向量未落盘，见下文 |")
    add("| (b) 缺陷源/后值 | — | EXP-0110/transfers.csv | `<缺陷>_stored_source/_new`、"
        "`<缺陷>_physical_source/_new`、`<缺陷>_nonincreasing` | 直接用落盘物理值 |")
    add("| (b) 源状态 | — | EXP-0110/transfer_sources.csv | `source_state`、`raw_source_value`、`is_na`、`is_floor`"
        "（键 repeat=0/fold=0/source_beer=%d） | 直接读取 |" % chosen_beer)
    add("| (b) 老化酒花代理 | — | EXP-0110/transfers.csv | `stale_hops_source/new/nonincreasing`、"
        "`stale_a_dot_source`、`stale_halfspace_b` | b=a'z_source+1e-9 |")
    add("| (c) 两类已记录代理 | — | EXP-0110/transfers.csv | `stale_hops_source/new`、`t2n_source/new` | 直接读取 |")
    add("| (c) 核心 5 维感官 | — | 无 | EXP-0110 只预测 stale_hops 与 t2n | 不适用，不臆造 |")
    add("| 表 3 阈值/单位 | — | data/clean/q3_thresholds.json | `defects.<名>.thresholdMean/Median/unit/tier` | 直接读取 |")
    add("| 表 3 实际约束值 | — | EXP-0110/transfer_constraints.csv | `bound_type`、`bound_value_physical` | 直接读取 |")
    add("| 表 3 源状态计数 | — | EXP-0110/transfer_sources.csv | `source_state`（99 行/化学列） | 计数 |")
    add("| 表 3 四类核验 | — | EXP-0110/transfer_verdicts.csv | `n`、`denominator`、`verifiedDenominator` | 按 verdict 汇总 |")
    add("| 表 3 老化酒花 b 范围 | — | EXP-0110/transfers.csv | `stale_halfspace_b`（主策略 99 行） | min/max |")
    add("| 表 3 源值超阈值计数 | — | EXP-0110/transfers.csv + q3_thresholds.json | `<缺陷>_physical_source` 与 `thresholdMean` | 逐行比较 |")
    add("")
    add("**分位数锚点为何是 \u201c—\u201d（已验证不可得）**：`transfers.csv` 的 `anchor` 列只是标签（`quantile`）；"
        "`transfer_outputs.json` 的 `anchors` 只有文字定义；`marginal_state.csv` 只保存每（风格，列）的 "
        "n_valid/n_continuous/n_floor/omega/kappa/pi（状态表 `StyleMarginals.state_table()`），"
        "不含 `Marginal.inverse` 需要的支撑点 `grid_x/grid_u`；`solver_certificates.jsonl` 只保存 "
        "`problem_hash`。因此锚点向量**不能**从已保存产物单元格重建；本表给出 `ref__chem__`（目标参考均值）"
        "并在表头标注\u201c非锚点\u201d。精确锚点需要重拟合源/目标边际（重跑管线），超出本次只读产物口径。")
    add("")
    add("## 5 表 3：3762 条约束记录的真实分解")
    add("")
    add("| 约束类 | 记录数 | 计算 | 来源 |")
    add("| --- | ---: | --- | --- |")
    add("| 线性非负下界 lower_zero | %d | %d 个线性校准列 × 99 | transfer_constraints.csv |"
        % (decomposition["lower_zero"], defect_context["n_lower_fields"]))
    add("| 四化学缺陷源值上限 upper_source_value | %d | %d 缺陷 × 99 | transfer_constraints.csv |"
        % (decomposition["upper_source_value"], defect_context["n_defect_caps"]))
    add("| 老化酒花代理上界 upper_source_value_proxy | %d | 1 代理 × 99 | transfer_constraints.csv |"
        % decomposition["upper_source_value_proxy"])
    add("| 合计（每个策略） | %d | 3267+396+99 | 与论文表述一致 |" % sum(decomposition.values()))
    add("")
    lower_verified = defect_context["lower_zero_verified"]
    upper_verified = overall["verified"] - lower_verified
    add("核验状态（主策略 qp-quantile-anchor）：verified %d、conditional %d、not_identifiable %d、failed %d；"
        "可核验分母 = %d − %d = %d。论文 qp-certs 表\u201c3465 / 198 / 99 / 0，分母 3663\u201d与此一致"
        "（%d = %d 条 lower_zero + %d 条上界）。"
        % (overall["verified"], overall["conditional"], overall["not_identifiable"], overall["failed"],
           overall["verified"] + overall["conditional"] + overall["not_identifiable"] + overall["failed"],
           overall["not_identifiable"],
           overall["verified"] + overall["conditional"],
           overall["verified"], lower_verified, upper_verified))
    add("")
    add("范围说明：`transfer_constraints.csv` 共 %d 行 = %d 个策略 × 3762；3762 是**每个策略**的记录集，"
        "不是 5 个策略的总和（18810 才是全文件行数）。"
        % (defect_context["constraint_rows_total"], defect_context["n_strategies"]))
    add("")
    add("已知文本矛盾：`transfer_constraints.csv` 的 `unit` 列把 `chem__X.E..2.nonenal` 写成 "
        "\u201cmg/L (unit NOT declared in q3_thresholds.json)\u201d，但 `q3_thresholds.json` 的 "
        "`defects.X.E..2.nonenal.unit` 实际声明为 `mg/L`。表 3 采用阈值文件的声明并保留该矛盾说明；"
        "该字符串是审计代码的标签，不影响数值。")
    add("")
    add("## 6 所有 \u201c—\u201d 及原因")
    add("")
    add("| 位置 | 列 | 原因 |")
    add("| --- | --- | --- |")
    add("| 表 2 (a)(b) | 分位数锚点 | 锚点向量未落盘（见 §4）；ref__chem__ 只是最近可持久化参照，不冒充锚点 |")
    add("| 表 2 (c) | 核心 5 维感官代理的前后值 | EXP-0110 迁移管线只落盘 stale_hops 与 t2n 两个代理分数，"
        "没有 A_malt_all/A_hops_all/A_esters_all/acidity/overall 的迁移前后预测 |")
    add("| 表 3 非壬烯醛阈值 | thresholdMean/Median | `q3_thresholds.json` 对该缺陷为 null（无感官阈值），"
        "其约束仅为源值不增 |")
    add("| 表 3 老化酒花 | 阈值 | 无阈值；只有训练折内岭回归代理的半空间上界 |")
    add("| 表 1 未校准列 | 物理单位 | 4-松油醇的 `unit_or_scale` 为 \u201cnot declared in 8.xlsx\u201d，"
        "只按存储尺度报告 |")
    add("")
    add("## 7 单位与尺度来源")
    add("")
    add("- 校准分级：`src/target_columns.py`（LOG10_CALIBRATED 37 列 / LINEAR_CALIBRATED 33 列 / FLOOR_COLUMNS 142 列）"
        "与 `data/clean/q2_chem_meta.json` 的 `log10Calibrated`/`linearCalibrated` 一致（脚本按前者取集合）。")
    add("- 每列单位/尺度：`data/processed/v6_feature_dictionary.csv` 的 `unit_or_scale`、`storage_scale`、`tier`。")
    add("- 缺陷单位/阈值：`data/clean/q3_thresholds.json` 的 `defects.<名>.unit`、`storageRules`、"
        "`thresholdMean`、`thresholdMedian`。")
    add("- 非检测码：`q3_thresholds.json` 的 `floorValue=-1.81781854`；表 1 所选 12 列在三风格真实行与生成谱中"
        "均未出现该码，故未触发\u201c非检测按 0 计\u201d。")
    add("")
    add("## 8 复核")
    add("")
    add("```bash")
    add("python \\")
    add("  src/q3_v62_answer_tables.py")
    add("```")
    add("")
    add("脚本自带输入列检查、代表源唯一性检查、3762 分解检查与四类核验总数检查，任一不符即具名失败，不填零。")
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------- 主流程
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUB_DIR.mkdir(parents=True, exist_ok=True)

    data = load_inputs()
    print("[q3_v62_answer_tables] 输入就绪：q3.csv %d 行、samples %d 行、transfers %d 行、constraints %d 行"
          % (len(data["q3"]), len(data["samples"]), len(data["transfers"]), len(data["constraints"])))

    # ---------------- 表 1 ----------------
    chem, sensory, combined = build_profile(data)
    chem_md, sensory_md = markdown_profile(chem, sensory, data["meta"])
    paths = {}
    paths["化学谱 CSV（表 1）"] = write_frames("tripel_kriek_lambic_profile_chem.csv", chem)
    paths["感官代理 CSV（表 1）"] = write_frames("tripel_kriek_lambic_profile_sensory.csv", sensory)
    paths["化学+感官合并 CSV（block 列）"] = write_frames("tripel_kriek_lambic_profile.csv", combined)
    paths["化学谱 markdown"] = write_text("tripel_kriek_lambic_profile_chem.md", chem_md)
    paths["感官代理 markdown"] = write_text("tripel_kriek_lambic_profile_sensory.md", sensory_md)

    # ---------------- 表 2 ----------------
    transfer_frame, rep_row, chosen_beer, eligible = build_transfer_example(data)
    transfer_md = markdown_transfer(transfer_frame, rep_row, chosen_beer, eligible, data["meta"])
    paths["单源迁移 CSV（表 2）"] = write_frames("pils_to_tripel_single_source.csv", transfer_frame)
    paths["单源迁移 markdown"] = write_text("pils_to_tripel_single_source.md", transfer_md)

    # ---------------- 表 3 ----------------
    defect_frame, defect_context = build_defect_control(data)
    defect_md = markdown_defect_control(defect_frame, defect_context)
    paths["缺陷控制 CSV（表 3）"] = write_frames("defect_control_summary.csv", defect_frame)
    paths["缺陷控制 markdown"] = write_text("defect_control_summary.md", defect_md)

    # ---------------- 报告 ----------------
    report = build_report(paths, transfer_frame, chosen_beer, eligible,
                          chem, sensory, defect_context)
    report_path = write_text("ANSWER_TABLES_REPORT.md", report)
    paths["生成报告"] = report_path

    print("[q3_v62_answer_tables] 完成")
    for key, path in paths.items():
        print("  %-28s %s" % (key, path.relative_to(ROOT)))
    print("[q3_v62_answer_tables] 代表源 beer=%d；3762 分解 %s；四类核验 %s"
          % (chosen_beer, defect_context["decomposition"], defect_context["overall"]))


if __name__ == "__main__":
    main()
