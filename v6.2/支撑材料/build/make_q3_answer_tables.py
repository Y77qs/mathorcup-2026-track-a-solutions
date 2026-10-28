#!/usr/bin/env python3
"""make_q3_answer_tables.py — compact paper fragments for the three Q3 answer tables.

Reads only the verified entity CSVs under ``outputs/q3/v62_tables/`` (produced by
src/q3_v62_answer_tables.py) plus, when available, the quantile-anchor export
``transfer_anchor_values.csv`` (produced by src/q3_v62_diagnostics.py).  The three
tables are deliberately reduced to the rows that answer the question so chapter 6
stays inside the page budget; the CSVs keep the full record.

Run:
    python FINAL_SUBMISSION_v6.2/build/make_q3_answer_tables.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BUILD_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BUILD_DIR.parent.parent
def _outputs_root() -> Path:
    for cand in (PROJECT_DIR, BUILD_DIR.parent):
        if (cand / "outputs").is_dir():
            return cand / "outputs"
    raise SystemExit("cannot locate outputs/")


OUT_ROOT = _outputs_root()
SRC = OUT_ROOT / "q3" / "v62_tables"
TABLES = BUILD_DIR / "tables"

STYLE_ORDER = ["Tripel", "Kriek", "Lambic"]
CHEM_ITEMS = ["乙醇", "二氧化硫", "苦度（α-酸）", "色度", "乙酸乙酯", "芳樟醇"]
SENSORY_ITEMS = ["麦芽香总体", "酒花总体", "酯香总体", "酸度", "总体"]
TRANSFER_CHEM = ["乙醇", "pH", "苦度（α-酸）", "色度", "甘油", "乙酸乙酯", "异戊醇", "芳樟醇"]


def md(header: list[str], rows: list[list[str]], aligns: list[str]) -> str:
    bar = "| " + " | ".join({"l": "---", "r": "---:", "c": ":---:"}[a] for a in aligns) + " |"
    lines = ["| " + " | ".join(header) + " |", bar]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def write(name: str, text: str) -> None:
    (TABLES / f"{name}.md").write_text(text, encoding="utf-8")
    print(f"[OK] tables/{name}.md")


def build_profile_chem() -> None:
    data = pd.read_csv(SRC / "tripel_kriek_lambic_profile_chem.csv")
    rows = []
    for style in STYLE_ORDER:
        part = data[data["style"] == style].set_index("item_cn")
        for item in CHEM_ITEMS:
            rec = part.loc[item]
            unit = str(rec["unit"]) if str(rec["unit_declared"]) == "yes" else "存储尺度"
            rows.append([f"{item}（{unit}）", style,
                         str(rec["generated_display"]), str(rec["real_display"])])
    note = ("注：生成侧为条件生成实验的设计谱按风格池化（Tripel/Kriek/Lambic 分别 84/30/33 份）的"
            "中位数与 P10–P90 区间；实测侧为 `data/clean/q3.csv` 同风格真实训练行（28/10/11 行）。"
            "已校准列按物理单位给出（对数校准 $c=10^x$，线性校准 $c=x$），未校准列标注“存储尺度”。"
            "生成谱是条件生成与约束投影后的设计值，不是测量值，也不能读作对某支真实啤酒的预测；"
            "三个冻结重复与九个训练上下文不是新增独立啤酒，表中区间不得读作窄置信区间。")
    write("q3-profile-chem", md(["化合物（单位）", "风格", "生成 中位数 [P10, P90]", "实测 中位数 [P10, P90]"],
                                rows, ["l", "l", "r", "r"]) + "\n\n" + note + "\n")


def build_profile_sensory() -> None:
    data = pd.read_csv(SRC / "tripel_kriek_lambic_profile_sensory.csv")
    rows = []
    for style in STYLE_ORDER:
        part = data[data["style"] == style].set_index("item_cn")
        for item in SENSORY_ITEMS:
            rec = part.loc[item]
            rows.append([item, style, str(rec["generated_display"]), str(rec["real_display"])])
    note = ("注：数值为 50 维岭回归标签代理对设计谱的预测均值与 P10–P90 区间（标准化 Z 分数，无物理单位），"
            "不是消费者感官测量；实测侧为同风格真实训练标签。两栏样本量不同，区间宽度不可直接比较；"
            "三个冻结重复与九个训练上下文不是新增独立啤酒，不得据此制造窄置信区间。")
    write("q3-profile-sensory", md(["感官代理", "风格", "生成 均值 [P10, P90]", "实测 均值 [P10, P90]"],
                                   rows, ["l", "l", "r", "r"]) + "\n\n" + note + "\n")


def numeric(x) -> str:
    """Readable 4-decimal presentation (tiny values in scientific notation)."""
    x = float(x)
    if x == 0.0:
        return "0.0000"
    if abs(x) < 1e-4:
        return f"{x:.2e}"
    return f"{x:.4f}"


def _lookup_anchor(anchors: pd.DataFrame | None, column: str) -> str:
    if anchors is None:
        return "—"
    hit = anchors[(anchors["repeat"] == 0) & (anchors["fold"] == 0)
                  & (anchors["source_beer"] == 28) & (anchors["column"] == column)]
    if hit.empty:
        return "—"
    rec = hit.iloc[0]
    if pd.isna(rec.get("anchor_physical")):
        return f"{numeric(rec['anchor_stored'])}（存储尺度）"
    return numeric(rec["anchor_physical"])


def build_transfer_example() -> None:
    data = pd.read_csv(SRC / "pils_to_tripel_single_source.csv")
    anchor_path = SRC / "transfer_anchor_values.csv"
    anchors = pd.read_csv(anchor_path) if anchor_path.exists() else None
    proxy_anchor = "—"
    diag = OUT_ROOT / "q3" / "v62_diagnostics" / "v62_diagnostics.json"
    if diag.exists():
        import json
        rep = json.loads(diag.read_text(encoding="utf-8"))["anchorDirectProjection"]["representativeAnchor"]
        proxy = rep.get("staleHopsProxy") or {}
        if "proxy_score_at_anchor" in proxy:
            proxy_anchor = numeric(proxy["proxy_score_at_anchor"])
    rows = []
    flavour = data[data["section"] == "flavour"].set_index("item_cn")
    for item in TRANSFER_CHEM:
        rec = flavour.loc[item]
        unit = str(rec["unit"]) if str(rec["unit_declared"]) == "yes" else "存储尺度"
        rows.append([f"{item}（{unit}）", str(rec["src_display"]),
                     _lookup_anchor(anchors, str(rec["column"])),
                     str(rec["ref_display"]), str(rec["post_display"]), str(rec["delta_display"])])
    defects = data[data["section"] == "defect"].set_index("item_cn")
    state_cn = {"measured": "实测", "imputed_training_median": "缺失·填补",
                "floor_coded": "地板码", "proxy": "代理"}
    for item, label in (("二甲基硫（DMS）", "二甲基硫（DMS）"), ("双乙酰（2,3-丁二酮）", "双乙酰"),
                        ("4-乙烯基愈创木酚（4VG）", "4VG"),
                        ("反-2-壬烯醛（trans-2-nonenal）", "反-2-壬烯醛"),
                        ("老化酒花代理（岭回归）", "老化酒花代理")):
        rec = defects.loc[item]
        unit = str(rec["unit"]).replace("物理：", "").replace("（log10校准）", "").replace("（线性校准）", "")
        unit = unit.replace("代理分数（标准化感官标签单位）", "代理分数")
        anchor_cell = (proxy_anchor if str(rec["column"]) == "stale_hops(ridge-proxy)"
                       else _lookup_anchor(anchors, str(rec["column"])))
        rows.append([f"{label}（{unit}；{state_cn.get(str(rec['source_state']), str(rec['source_state']))}）",
                     str(rec["src_display"]), anchor_cell,
                     str(rec["ref_display"]), str(rec["post_display"]), str(rec["delta_display"])])
    proxies = data[data["section"] == "sensory_proxy"].set_index("item_cn")
    for item, label, anchor_cell in (("反-2-壬烯醛感官代理", "感官代理·t2n", "—"),):
        rec = proxies.loc[item]
        rows.append([f"{label}（代理分数）", str(rec["src_display"]), anchor_cell,
                     "—", str(rec["post_display"]), str(rec["delta_display"])])
    note = ("注：代表源按固定规则选取——repeat=0（冻结种子 20261025）、外层 fold=0、"
            "在 11 支 Pils/Lager 源啤酒中取最小 id，即 beer 28（transfer_id R0-F0-B028-qp-quantile-anchor，"
            "status=optimal、feasible=True、约束违反 0）。源值为 `transfers.csv` 的 `src__chem__`（与 "
            "`data/clean/q3.csv` 对应训练行逐格一致），迁移后为 `opt__chem__`；分位数锚点为该折实际使用的"
            "分位数保序锚点；“目标参考值”是目标风格参考均值，**不是锚点**，单列以便区分。"
            "注意：原始分位数锚点本身并不是声明可行域内的点（99/99 个锚点都超出四条化学 cap 的盒界，"
            "需要在 QP 中被投影），表中给出的是锚点值，不是可行解；"
            "五项缺陷的“不增”是 QP 构造性质（上界取源值本身），不是感官合格证明；四条化学缺陷源状态为"
            "实测/缺失填补/地板码时已在标签中标明。老化酒花与 t2n 只有训练折内的岭回归代理，不能读作实测；"
            "核心 5 维感官代理在迁移产物中没有前后对照，故不列入。")
    write("q3-transfer-example", md(["化合物（单位；源状态）", "源值", "分位数锚点", "目标参考值",
                                     "迁移后设计值", "Δ（迁移后−源值）"],
                                    rows, ["l", "r", "r", "r", "r", "r"]) + "\n\n" + note + "\n")


def build_defect_control() -> None:
    data = pd.read_csv(SRC / "defect_control_summary.csv")
    rows = []
    for rec in data.itertuples():
        unit = str(rec.unit).replace("ug/L", "μg/L")
        def num(value):
            try:
                return f"{float(value):.4g}"
            except (TypeError, ValueError):
                return "—"
        rows.append([rec.item_cn, unit,
                     f"{num(rec.threshold_mean)} / {num(rec.threshold_median)}"
                     if str(rec.threshold_mean) != "nan" else "—",
                     f"{int(rec.n_measured)} / {int(rec.n_missing_imputed)} / {int(rec.n_floor)}",
                     f"{int(rec.n_records)}"])
    note1 = ("注：阈值取自 `data/clean/q3_thresholds.json`（Mean / Median），单位按该文件的声明；"
             "“实际约束”一律是**源值上限**（`transfer_constraints.csv` 的 bound_type=upper_source_value，"
             "老化酒花代理为半空间 $a'z\\le b$），因此 QP 只保证“不劣化源样本”，不保证低于感官阈值。"
             "源状态三列分别为实测 / 缺失（训练折中位数填补）/ 地板码（非检测），每类分母 99 = "
             "3 重复 × 3 折 × 11 支源啤酒。")
    header1 = ["缺陷项", "尺度/单位", "阈值 Mean / Median", "源状态 实测/缺失/地板", "约束记录数"]
    part1 = md(header1, rows, ["l", "l", "r", "r", "r"])

    rows2 = []
    for rec in data.itertuples():
        rows2.append([rec.item_cn, str(rec.constraint_type).replace("upper_source_value", "源值上限"),
                      int(rec.n_verified), int(rec.n_conditional),
                      int(rec.n_not_identifiable), int(rec.n_failed), int(rec.verified_denominator)])
    rows2.append(["四类合计", "—", 3465, 198, 99, 0, 3663])
    header2 = ["缺陷项（约束类型）", "约束类型", "已验证", "条件成立", "不可识别", "失败", "可核验分母"]
    part2 = md(header2, rows2, ["l", "l", "r", "r", "r", "r", "r"])
    note2 = ("注：五类上界记录合计 495 条（每类 99 条）；qc 表按全部约束统计的 3762 条"
             "（= 3267 条 33 列线性非负下界 + 396 条四项化学源值上限 + 99 条 stale 代理上界）复核结果见正文的求解证书汇总表。"
             "“不可识别”全部来自源格缺失或地板码，“条件成立”来自代理或存储尺度约定；两类都不计入可核验分母，"
             "也不计为失败。")
    write("q3-defect-control", part1 + "\n\n" + part2 + "\n\n" + note1 + " " + note2 + "\n")


def main() -> int:
    needed = ["tripel_kriek_lambic_profile_chem.csv", "tripel_kriek_lambic_profile_sensory.csv",
              "pils_to_tripel_single_source.csv", "defect_control_summary.csv"]
    missing = [n for n in needed if not (SRC / n).exists()]
    if missing:
        raise SystemExit(f"missing entity CSVs in {SRC}: {missing}")
    build_profile_chem()
    build_profile_sensory()
    build_transfer_example()
    build_defect_control()
    return 0


if __name__ == "__main__":
    sys.exit(main())
