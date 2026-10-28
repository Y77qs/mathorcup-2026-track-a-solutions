#!/usr/bin/env python3
"""make_q2_table.py — regenerate the Q2 table fragments from the v6.2 clean CSVs.

The Q2 deliverable tables (core 20-dimension, full 50-dimension, extended 15-metric)
are rebuilt from ``outputs/q2/v62_clean/repeat0/*.csv`` — the deterministic
post-processed copies in which ``alternative_rank4`` already excludes the delivered
Top-3 (see src/q2_v62_regen.py).  The style-confound class (内/风/混) is recomputed
from the point-estimate correlations in ``experiments/EXP-0107/candidate_scores.csv``
with the same rule as src/paper_tables.py::_style_type.

Run:
    python FINAL_SUBMISSION_v6.2/build/make_q2_table.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BUILD_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BUILD_DIR.parent.parent
TABLES = BUILD_DIR / "tables"
def _outputs_root() -> Path:
    for cand in (PROJECT_DIR, BUILD_DIR.parent):
        if (cand / "outputs").is_dir():
            return cand / "outputs"
    raise SystemExit("cannot locate outputs/")


OUT_ROOT = _outputs_root()
CLEAN = OUT_ROOT / "q2" / "v62_clean" / "repeat0"
def _point_scores() -> Path:
    original = PROJECT_DIR / "experiments" / "EXP-0107" / "candidate_scores.csv"
    if original.exists():
        return original
    derived = OUT_ROOT / "q2" / "candidate_scores_point.csv"
    if derived.exists():
        return derived
    raise SystemExit("candidate_scores.csv not found (original layout) and no derived extract")


SCORES = _point_scores()

DIM_LABELS = {
    "A_malt_all": "香气·麦芽总体", "A_malt_grain": "香气·谷物", "A_malt_bread": "香气·面包",
    "A_malt_cara": "香气·焦糖", "A_malt_burn": "香气·烘烤",
    "A_hops_all": "香气·酒花总体", "A_hops_citrus": "香气·柑橘", "A_hops_tropical": "香气·热带水果",
    "A_hops_noble": "香气·贵族酒花", "A_hops_woody": "香气·木质",
    "A_esters_all": "香气·酯香总体", "A_esters_ethac": "香气·乙酸乙酯", "A_esters_isoaa": "香气·乙酸异戊酯",
    "A_esters_flower": "香气·花香", "A_esters_fruity": "香气·果香",
    "F_malt_all": "风味·麦芽总体", "F_malt_grain": "风味·谷物", "F_malt_bread": "风味·面包",
    "F_malt_cara": "风味·焦糖", "F_malt_burn": "风味·烘烤",
    "F_hops_all": "风味·酒花总体", "F_hops_citrus": "风味·柑橘", "F_hops_tropical": "风味·热带水果",
    "F_hops_noble": "风味·贵族酒花", "F_hops_woody": "风味·木质",
    "F_esters_all": "风味·酯香总体", "F_esters_ethac": "风味·乙酸乙酯", "F_esters_isoaa": "风味·乙酸异戊酯",
    "F_esters_flower": "风味·花香", "F_esters_fruity": "风味·果香",
    "acidity": "酸感", "bitternes": "苦感", "sweetness": "甜感", "X4vg": "4-乙烯基愈创木酚",
    "diacetyl": "双乙酰", "dms": "二甲基硫", "metallic": "金属感", "stale_hops": "老化酒花",
    "t2n": "反-2-壬烯醛", "orange": "橙香", "coriander": "芫荽", "clove": "丁香",
    "lactic": "乳酸感", "acetic": "醋酸感", "barnyard": "马厩味", "alcohol": "酒精感",
    "aftertaste": "回味", "body": "酒体", "co2": "二氧化碳", "overall": "总体评价",
}
KIND_LABELS = {"single_compound": "单体化合物", "element_or_index": "元素/指数",
               "physical_parameter": "理化参数", "derived_sum": "派生和"}

TARGET_ORDER = ["A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn",
                "A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody",
                "A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity",
                "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn",
                "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody",
                "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity",
                "acidity", "bitternes", "sweetness", "X4vg", "diacetyl", "dms", "metallic",
                "stale_hops", "t2n", "orange", "coriander", "clove", "lactic", "acetic", "barnyard",
                "alcohol", "aftertaste", "body", "co2", "overall"]
CORE_A15 = TARGET_ORDER[:15]
CORE_F5 = ["F_malt_all", "F_hops_all", "F_hops_citrus", "F_esters_all", "F_esters_isoaa"]


def style_type(rho_total: float, rho_within: float) -> str:
    at, aw = abs(float(rho_total)), abs(float(rho_within))
    if aw >= 0.8 * at:
        return "内"
    if at >= 0.25 and aw < 0.5 * at:
        return "风"
    return "混"


def alt_text(value, compound) -> str:
    text = "" if value is None else str(value).strip()
    if text == "" or text.lower() in ("none", "null", "nan"):
        return "—（无）"
    if text == str(compound):
        return "—（无同模块替代）"
    return text


def fmt(value, digits: int) -> str:
    return f"{float(value):.{digits}f}"


def load(source: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(source)
    scores = pd.read_csv(SCORES, usecols=["dimension", "compound", "rho_total", "rho_within"])
    scores = scores.set_index(["dimension", "compound"])
    frame["type"] = [style_type(scores.loc[(d, c), "rho_total"], scores.loc[(d, c), "rho_within"])
                     for d, c in zip(frame["dimension"], frame["compound"])]
    frame["dir"] = ["+" if str(v).lower().startswith("pos") else "−" for v in frame["point_direction"]]
    return frame, scores


def write(name: str, text: str) -> None:
    (TABLES / f"{name}.md").write_text(text, encoding="utf-8")
    print(f"[OK] tables/{name}.md  ({len(text)} chars)")


def build_core() -> None:
    frame, _ = load(CLEAN / "strict_top3.csv")
    dims = CORE_A15 + CORE_F5
    rows = []
    for dim in dims:
        part = frame[frame["dimension"] == dim].sort_values("rank")
        if len(part) != 3:
            raise SystemExit(f"core table: dimension {dim} has {len(part)} rows, expected 3")
        cells = [f"{r.compound}｜{fmt(r.pi, 3)}/{fmt(r.score, 4)}｜{r.dir}·{r.type}"
                 for r in part.itertuples()]
        third = part.iloc[2]
        rows.append([DIM_LABELS[dim]] + cells + [alt_text(third["alternative_rank4"], third["compound"])])
    header = ["感官维度", "第 1 位", "第 2 位", "第 3 位", "第 3 位同模块替代候选"]
    note = (
        "注：单元格格式为“名称｜π/S｜方向·类型”。π 为 500 次风格内分层 bootstrap 的入选频率；"
        "S 为**三种基础方法（总体 Spearman、风格内残差 Spearman、图低秩系数）在维度内百分位排名的均值共识分**；"
        "方向为总体 Spearman 相关的符号；类型按原脚本口径判定——“内”表示 |风格内相关| ≥ 0.8|总体相关|，"
        "“风”表示未满足前者且 |总体相关| ≥ 0.25、|风格内相关| < 0.5|总体相关|，其余为“混”。"
        "维度取香气 15 维全部与风味 5 个核心维度；完整 50 维见附录 A 的长表。"
        "最后一列为第 3 位的**同模块替代候选**：先剔除该维度已进入 Top-3 的候选，再取同参考模块内点估计"
        "排序最靠前的第一个未入选候选，因此它不会与同维 Top-3 重复（150 条严格共识与 600 条四方法交付表的"
        "重合数均为 0）；“无”表示该参考模块内不存在这样的候选。"
    )
    md = "\n".join(["| " + " | ".join(header) + " |",
                    "| " + " | ".join("---" for _ in header) + " |"] +
                   ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])
    write("q2-core-top3", md + "\n\n" + note + "\n")


def build_full() -> None:
    frame, _ = load(CLEAN / "strict_top3.csv")
    header = ["感官维度", "位次", "化合物", "类别", "π", "S", "方向", "类型", "同模块替代候选"]
    rows = []
    for dim in TARGET_ORDER:
        part = frame[frame["dimension"] == dim].sort_values("rank")
        for r in part.itertuples():
            rows.append([DIM_LABELS[dim], int(r.rank), r.compound, KIND_LABELS[r.kind],
                         fmt(r.pi, 3), fmt(r.score, 4), r.dir, r.type,
                         alt_text(r.alternative_rank4, r.compound)])
    note = ("注：附录长表，覆盖全部 50 个感官维度、每维 3 个条目，共 150 条。列定义与核心维表一致；"
            "“同模块替代候选”已剔除同维 Top-3 已入选候选，不与之重复。严格榜只含单体化合物；"
            "元素/指数、理化参数与派生和见扩展榜。")
    md = "\n".join(["| " + " | ".join(header) + " |",
                    "| --- | ---: | --- | --- | ---: | ---: | --- | --- | --- |"] +
                   ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])
    write("q2-full-top3", md + "\n\n" + note + "\n")


def build_extended() -> None:
    frame, _ = load(CLEAN / "extended_top3.csv")
    header = ["感官维度", "位次", "化合物", "类别", "π", "S", "方向", "类型", "同模块替代候选"]
    rows = []
    for dim in TARGET_ORDER:
        part = frame[frame["dimension"] == dim].sort_values("rank")
        for r in part.itertuples():
            rows.append([DIM_LABELS[dim], int(r.rank), r.compound, KIND_LABELS[r.kind],
                         fmt(r.pi, 3), fmt(r.score, 4), r.dir, r.type,
                         alt_text(r.alternative_rank4, r.compound)])
    note = ("注：扩展榜，15 个非单体指标在全部 50 个感官维度上的 Top-3，与严格榜分表报告、不合并计数；"
            "π、S、方向与类型的口径同核心维表，“同模块替代候选”同样已剔除同维 Top-3。")
    md = "\n".join(["| " + " | ".join(header) + " |",
                    "| --- | ---: | --- | --- | ---: | ---: | --- | --- | --- |"] +
                   ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])
    write("q2-extended", md + "\n\n" + note + "\n")


def main() -> int:
    if not (CLEAN / "strict_top3.csv").exists():
        raise SystemExit(f"missing {CLEAN/'strict_top3.csv'}: run src/q2_v62_regen.py first")
    build_core()
    build_full()
    build_extended()
    return 0


if __name__ == "__main__":
    sys.exit(main())
