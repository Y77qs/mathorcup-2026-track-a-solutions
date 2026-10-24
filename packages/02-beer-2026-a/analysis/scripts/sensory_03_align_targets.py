#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sensory_03_align_targets.py
targetColumns 决策 + 四方对齐：
  4.csv 列名 <-> 3.xlsx summary 列名/评分卡属性 <-> 5.csv 长名 <-> 8.xlsx 'Sensory names' 的 R_name / CleanName_PanelFeedback
输出：analysis/sensory/targetcolumns.csv
      analysis/sensory/alignment_checks.json
只读 raw，不改 raw。
"""
import json
import os
import re

import numpy as np
import openpyxl
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "analysis", "sensory")
os.makedirs(OUT, exist_ok=True)
META = ["beer", "beer_id", "tasting_category_fine"]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def nearest_label(ws, row, side):
    subcol = "E" if side == "Aroma" else "U"
    headcol = "B" if side == "Aroma" else "R"
    v = ws[f"{subcol}{row}"].value
    if isinstance(v, str):
        return v
    for r in range(row - 1, 0, -1):
        v = ws[f"{subcol}{r}"].value
        if isinstance(v, str):
            return v
        v = ws[f"{headcol}{r}"].value
        if isinstance(v, str):
            return v
    return ""


SUBGROUP = {}
for c in ["A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn",
          "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn"]:
    SUBGROUP[c] = "Malt/麦芽"
for c in ["A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody",
          "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody"]:
    SUBGROUP[c] = "Hops/酒花"
for c in ["A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity",
          "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity"]:
    SUBGROUP[c] = "Esters/酯类"
for c in ["body", "aftertaste", "alcohol", "co2", "sweetness", "acidity", "bitternes"]:
    SUBGROUP[c] = "口感/基本味"
for c in ["dms", "diacetyl", "metallic", "stale_hops", "t2n", "X4vg", "lactic", "acetic", "barnyard"]:
    SUBGROUP[c] = "缺陷/野生菌"
for c in ["orange", "coriander", "clove"]:
    SUBGROUP[c] = "辅料/辛香"
SUBGROUP["overall"] = "总体"


def main():
    d4 = pd.read_csv(os.path.join(RAW, "4.csv"))
    cols4 = [c for c in d4.columns if c not in META]
    assert len(cols4) == 50

    # 3.xlsx summary
    wb = openpyxl.load_workbook(os.path.join(RAW, "3.xlsx"), data_only=False)
    ws = wb["summary"]
    beer1 = wb["beer_1"]
    summary = {}
    for c in range(2, ws.max_column + 1):
        name = ws.cell(1, c).value
        f = ws.cell(2, c).value
        src, attr, side = "", "", ""
        if isinstance(f, str):
            m = re.search(r"beer_1!\$([A-Z]+)\$(\d+)", f)
            if m:
                col, row = m.group(1), int(m.group(2))
                src = f"beer_x!{col}{row}"
                side = "Aroma" if col == "Q" else ("Flavour" if col == "AG" else "?")
                attr = nearest_label(beer1, row, side) if side != "?" else ""
        summary[name] = dict(summary_cell=ws.cell(1, c).coordinate, source=src,
                             card_attribute=attr, side=side)
    by_norm = {norm(k): k for k in summary}

    # 5.csv 长名
    d5 = pd.read_csv(os.path.join(RAW, "5.csv"), index_col=0)
    f5 = [str(x).replace("\r\n", " ").replace("\n", " ").strip() for x in d5.index]
    f5_norm = {norm(x): x for x in f5}

    # 8.xlsx Sensory names -> 只取 Trained panel 50 行
    wb8 = openpyxl.load_workbook(os.path.join(RAW, "8.xlsx"), data_only=True)
    w8 = wb8["Sensory names"]
    names = {}
    for r in range(2, w8.max_row + 1):
        if w8.cell(r, 1).value == "Trained panel":
            names[w8.cell(r, 2).value] = dict(
                category=w8.cell(r, 4).value,
                clean_paper=w8.cell(r, 5).value,
                clean_paper_long=w8.cell(r, 6).value,
                panel_feedback=w8.cell(r, 7).value,
                datatype=w8.cell(r, 8).value,
            )

    # 对齐
    rows = []
    diffs = []
    for i, c in enumerate(cols4, start=1):
        group = "Aroma" if c.startswith("A_") else ("Flavour" if c.startswith("F_") else "口感/缺陷/总体")
        s = summary.get(c, {})
        ALIAS = {"X4vg": "4vg"}
        s_norm = by_norm.get(norm(c), None)
        if s_norm is None and c in ALIAS:
            s_norm = by_norm.get(norm(ALIAS[c]), None)
        if s_norm is None:
            # 容忍命名差异：模糊匹配（去 s / 去前缀）
            cand = [k for k in summary if norm(k).replace("s", "") == norm(c).replace("s", "")]
            if cand:
                s_norm = cand[0]
        s = summary.get(s_norm, {}) if s_norm else {}
        n8 = names.get(c, {})
        f5_name = n8.get("panel_feedback") or ""
        f5_name = str(f5_name).replace("_x000D_\n", " ").replace("\r\n", " ").replace("\n", " ").strip()
        if norm(f5_name) not in f5_norm:
            f5_name_matched = ""
        else:
            f5_name_matched = f5_norm[norm(f5_name)]

        note = []
        if s_norm and s_norm != c:
            note.append(f"3.xlsx summary 作 '{s_norm}'（与 4.csv '{c}' 命名不一致）")
        if not s_norm:
            note.append("3.xlsx summary 中无对应列")
        if c == "X4vg":
            note.append("3.xlsx 作 '4vg'；8.xlsx R_name 作 'X4vg'")
        if c in ("A_esters_fruity", "F_esters_fruity"):
            note.append("3.xlsx 作 'A_ester_fruity'/'F_ester_fruity'（缺一个 s）；8.xlsx R_name 与 4.csv 一致")
        if c == "bitternes":
            note.append("'bitternes' 拼写少一个 s，三套文件一致保留该拼写")
        if c == "barnyard" and s.get("source") == "beer_x!AG76":
            note.append("3.xlsx summary 的 barnyard 公式误引 beer_x!AG76（=Stale hops），正确应为 AG90")
        if c == "overall":
            note.append("5.csv 长名含换行 'Overall appreciation (Trained panel)'")
        rows.append(dict(
            order_4csv=i, group=group, subgroup=SUBGROUP.get(c, ""), col_4csv=c,
            xlsx_summary_name=s_norm or "",
            xlsx_summary_cell=s.get("summary_cell", ""),
            xlsx_source_cell=s.get("source", ""),
            xlsx_card_attribute=s.get("card_attribute", ""),
            f5_name=f5_name_matched or f5_name,
            f5_name_matched=bool(f5_name_matched),
            xlsx_sensory_name_R=c if c in names else "",
            xlsx_category=n8.get("category", ""),
            xlsx_datatype=n8.get("datatype", ""),
            xlsx_clean_paper=n8.get("clean_paper", ""),
            notes="；".join(note),
        ))
        if s_norm != c:
            diffs.append((c, s_norm))

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "targetcolumns.csv"), index=False, encoding="utf-8-sig")

    checks = {
        "n_target_columns": len(cols4),
        "groups": out.group.value_counts().to_dict(),
        "subgroups": out.subgroup.value_counts().to_dict(),
        "4csv_cols_all_in_8xlsx_trained_panel": bool(set(cols4) == set(names)),
        "n_3xlsx_summary_matched": int((out.xlsx_summary_name != "").sum()),
        "n_3xlsx_summary_unmatched": int((out.xlsx_summary_name == "").sum()),
        "n_f5_names": int(len(f5)),
        "n_f5_names_matched": int(out.f5_name_matched.sum()),
        "naming_diffs_4csv_vs_3xlsx": diffs,
        "3xlsx_summary_numeric_cols": int(sum(1 for k in summary if k != "comments")),
        "statement_says_about_40": "题面：'3.xlsx 中定义的 Aroma 与 Flavour 两套、共约 40 个感官维度'",
        "actual": "3.xlsx summary 定义 50 个数值感官维度（A_*15 + F_*15 + 其他20）+ comments；4.csv 亦为 50 列",
        "why_not_40": [
            "仅 Aroma+Flavour 两套 = 30，不等于约 40；",
            "summary 另有 20 个口感/缺陷/辅料/总体维度，合计 50；",
            "12 个 beer 评分卡上共 51 个属性标签（比 summary 多 Acetaldehyde），也不等于 40；",
            "因此 '约40' 既不对应 30 也不对应 50，是题面对附件的概括误差，论文应以 50 为准并声明口径。",
        ],
    }
    with open(os.path.join(OUT, "alignment_checks.json"), "w", encoding="utf-8") as fh:
        json.dump(checks, fh, ensure_ascii=False, indent=2)

    print(json.dumps(checks, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
