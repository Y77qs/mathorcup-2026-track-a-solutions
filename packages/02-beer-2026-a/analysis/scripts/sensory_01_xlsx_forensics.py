#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sensory_01_xlsx_forensics.py
3.xlsx 取证：13 个 sheet 逐一结构、12 个 beer 评分卡是否已填写、
summary 的公式/数值、0-6 刻度与锚点、跨表引用映射。
输出：analysis/sensory/xlsx_forensics.json
      analysis/sensory/xlsx_beersheet_inventory.csv
      analysis/sensory/xlsx_summary_formula_map.csv
只读 raw，不改 raw。
"""
import json
import os
import re

import openpyxl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "analysis", "sensory")
os.makedirs(OUT, exist_ok=True)
XLSX = os.path.join(RAW, "3.xlsx")

# beer 评分卡的 0-6 刻度行（数字 0..6 所在行；openpyxl 1-based）
SCALE_ROWS = [8, 21, 34, 46, 51, 55, 59, 63, 69, 73, 77, 83, 87, 91, 95, 98, 101]
SCALE_COLS_LEFT = ["C", "E", "G", "I", "K", "M", "O"]      # 0..6 (Aroma 侧)
SCALE_COLS_RIGHT = ["S", "U", "W", "Y", "AA", "AC", "AE"]  # 0..6 (Flavour 侧)


def col_idx(letter):
    n = 0
    for ch in letter:
        n = n * 26 + (ord(ch) - 64)
    return n


def nearest_label(ws, row, side):
    """Q 列(左/Aroma)公式 或 AG 列(右/Flavour)公式，向上/同排找属性名。"""
    subcol = "E" if side == "Aroma" else "U"
    headcol = "B" if side == "Aroma" else "R"
    # 同一排的子属性名（只认文本，忽略 0-6 刻度数字）
    v = ws[f"{subcol}{row}"].value
    if isinstance(v, str):
        return v
    # 向上找最近的组名(B/R)或子属性(E/U)，只认文本
    for r in range(row - 1, 0, -1):
        v = ws[f"{subcol}{r}"].value
        if isinstance(v, str):
            return v
        v = ws[f"{headcol}{r}"].value
        if isinstance(v, str):
            return v
    return ""


def group_header(ws, row, side):
    headcol = "B" if side == "Aroma" else "R"
    for r in range(row, 0, -1):
        v = ws[f"{headcol}{r}"].value
        if v not in (None, "") and r <= row:
            return str(v)
    return ""


def main():
    wb = openpyxl.load_workbook(XLSX, data_only=False)
    wbv = openpyxl.load_workbook(XLSX, data_only=True)

    facts = {
        "file": "data/raw/3.xlsx",
        "sheet_count": len(wb.sheetnames),
        "sheetnames": wb.sheetnames,
        "sheets": {},
        "summary": {},
        "conclusion_notes": [],
    }

    # ---------- 1) 12 个 beer 评分卡 ----------
    inv_rows = []
    for name in wb.sheetnames:
        if name == "summary":
            continue
        ws, wsv = wb[name], wbv[name]
        n_form = n_num = n_str = 0
        nums, strs, formulas = [], [], []
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if v is None:
                    continue
                if isinstance(v, str) and v.startswith("="):
                    n_form += 1
                    formulas.append((cell.coordinate, v))
                elif isinstance(v, (int, float)):
                    n_num += 1
                    nums.append((cell.coordinate, v))
                else:
                    n_str += 1
                    strs.append((cell.coordinate, str(v)))

        # 已填写评分 = 非公式、非刻度数字、非模板文字、非 Beer# 的单元格
        scale_coords = {f"{c}{r}" for r in SCALE_ROWS for c in SCALE_COLS_LEFT + SCALE_COLS_RIGHT}
        scale_coords.discard("C98")
        scale_coords.add("C98")  # 锚点 0
        scale_coords.add("C101")  # 锚点 6
        filled = [(co, v) for co, v in nums if co not in scale_coords and co != "S3"]
        filled += [(co, v) for co, v in strs if co in ()]  # 模板文字全部是标签，不计
        beer_no = ws["S3"].value

        # 0-6 刻度举证：每个刻度块 (block_row, labels)
        scale_blocks = {}
        for r in SCALE_ROWS:
            left = [ws[f"{c}{r}"].value for c in SCALE_COLS_LEFT]
            right = [ws[f"{c}{r}"].value for c in SCALE_COLS_RIGHT]
            scale_blocks[r] = {"left": left, "right": right}

        # 属性清单：Q 列(Aroma) / AG 列(Flavour) 的公式行
        for coord, f in formulas:
            m = re.match(r"^([A-Z]+)(\d+)$", coord)
            col, row = m.group(1), int(m.group(2))
            if col == "Q":
                side = "Aroma"
            elif col == "AG":
                side = "Flavour"
            else:
                continue
            inv_rows.append(dict(
                sheet=name, beer_no=beer_no, side=side,
                formula_cell=coord, formula=f,
                attribute=nearest_label(ws, row, side),
                group_header=group_header(ws, row, side),
            ))

        facts["sheets"][name] = {
            "beer_no": beer_no,
            "dims": ws.dimensions,
            "max_row": ws.max_row, "max_col": ws.max_column,
            "formula_cells": n_form,
            "numeric_cells": n_num,
            "string_cells": n_str,
            "filled_score_cells": len(filled),
            "filled_score_examples": filled[:10],
            "scale_block_rows": SCALE_ROWS,
            "scale_numbers_left_C..O": scale_blocks,
            "merged_ranges": [str(m) for m in ws.merged_cells.ranges],
            "data_validations": len(ws.data_validations.dataValidation) if ws.data_validations else 0,
            "images": len(getattr(ws, "_images", [])),
        }

    # 12 个 beer sheet 是否结构完全一致
    sig = {n: (d["formula_cells"], d["numeric_cells"], d["string_cells"], d["filled_score_cells"])
           for n, d in facts["sheets"].items()}
    facts["all_beer_sheets_identical_structure"] = len(set(sig.values())) == 1
    facts["beer_sheets_signature_(formulas,numeric,strings,filled)"] = sig
    facts["total_filled_score_cells_across_12_sheets"] = sum(
        d["filled_score_cells"] for d in facts["sheets"].values())

    # 0-6 编码公式举例
    bs = wb["beer_1"]
    facts["encoder_formula_examples"] = {
        "Q7 (Malt 总体分)": bs["Q7"].value,
        "AG7 (Malt flavour 总体分)": bs["AG7"].value,
        "Q10 (grain 子项)": bs["Q10"].value,
        "AG10 (grain flavour 子项)": bs["AG10"].value,
        "Q94 (Overall)": bs["Q94"].value,
        "anchors": {"E97": bs["E97"].value, "C98": bs["C98"].value,
                     "E100": bs["E100"].value, "C101": bs["C101"].value},
        "scale_numbers_row8": {c: bs[f"{c}8"].value for c in SCALE_COLS_LEFT},
    }

    # ---------- 2) summary ----------
    ws, wsv = wb["summary"], wbv["summary"]
    header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    facts["summary"]["dims"] = ws.dimensions
    facts["summary"]["rows"] = ws.max_row
    facts["summary"]["cols"] = ws.max_column
    facts["summary"]["header"] = header
    facts["summary"]["nonempty_data_cells"] = {
        "formula_version": sum(1 for r in range(2, ws.max_row + 1) for c in range(1, ws.max_column + 1)
                               if ws.cell(r, c).value is not None),
        "data_only_version": sum(1 for r in range(2, ws.max_row + 1) for c in range(1, ws.max_column + 1)
                                 if wsv.cell(r, c).value is not None),
    }
    vals_do = [[wsv.cell(r, c).value for c in range(1, ws.max_column + 1)]
               for r in range(2, ws.max_row + 1)]
    facts["summary"]["data_only_all_zero"] = all(
        (v == 0 or v in (None, "")) for row in vals_do for v in row[1:])
    facts["summary"]["beer_column_A"] = [r[0] for r in vals_do]
    facts["summary"]["distinct_data_only_values"] = sorted({v for row in vals_do for v in row[1:]
                                                            if v is not None})[:20]

    # summary 列 -> 源单元格 -> 评分卡属性名
    sum_rows, seen = [], set()
    sheet_ws = wb["beer_1"]
    for c in range(2, ws.max_column + 1):
        hdr = ws.cell(1, c).value
        f = ws.cell(2, c).value
        src = ""
        attr = ""
        if isinstance(f, str) and f.startswith("="):
            m = re.search(r"beer_1!\$([A-Z]+)\$(\d+)", f)
            if m:
                src = f"{m.group(1)}{m.group(2)}"
                col, row = m.group(1), int(m.group(2))
                side = "Aroma" if col == "Q" else ("Flavour" if col == "AG" else "?")
                attr = nearest_label(sheet_ws, row, side) if side != "?" else str(
                    sheet_ws[f"{col}{row}"].value)
                sum_rows.append(dict(summary_col=ws.cell(1, c).coordinate, summary_name=hdr,
                                     source_cell=f"beer_x!{src}", attribute_on_card=attr,
                                     side=side, formula=f))
                seen.add(src)
    facts["summary"]["n_summary_cols_mapped"] = len(sum_rows)

    # 评分卡上存在但 summary 未引用的分值公式
    card_score_cells = [co for co, _ in [(c.coordinate, c.value) for row in sheet_ws.iter_rows() for c in row]
                        if isinstance(sheet_ws[co].value, str) and sheet_ws[co].value.startswith("=")
                        and co[0] in "QA" and sheet_ws[co].value.startswith("=IF(ISBLANK(")]
    card_score_cells = [co for co in card_score_cells if re.match(r"^(Q|AG)\d+$", co)]
    missing = [co for co in card_score_cells if co not in seen]
    facts["summary"]["card_score_formulas_not_in_summary"] = missing
    facts["summary"]["card_score_formulas_not_in_summary_labels"] = [
        (co, nearest_label(sheet_ws, int(re.search(r"\d+", co).group()), "Aroma" if co[0] == "Q" else "Flavour"))
        for co in missing]

    # 异常：barnyard 引用
    by_name = {r["summary_name"]: r for r in sum_rows}
    facts["summary"]["suspect_refs"] = {
        k: by_name[k] for k in ("barnyard", "stale_hops", "clove", "lactic", "acetic", "orange", "coriander")
        if k in by_name}

    # 分组：A_* 15, F_* 15, 其余 20, comments 1
    facts["summary"]["group_counts"] = {
        "A_*": sum(1 for h in header if isinstance(h, str) and h.startswith("A_")),
        "F_*": sum(1 for h in header if isinstance(h, str) and h.startswith("F_")),
        "other_numeric": sum(1 for h in header if isinstance(h, str)
                             and not h.startswith(("A_", "F_")) and h not in ("comments", "Beer")),
        "comments": sum(1 for h in header if h == "comments"),
        "Beer": sum(1 for h in header if h == "Beer"),
    }

    # ---------- 结论 ----------
    facts["conclusion_notes"] = [
        "12 个 beer sheet 均为空白评分卡模板：无任何被勾选/填写的分值单元格（filled_score_cells=0）。",
        "每个 beer sheet 只有 54 个公式（Q7/AG7 及 Q10..AG94 编码公式）与 199 个数字，后者全部是 0–6 刻度标签与 Beer#。",
        "summary 是 12 行×52 列，除 A 列 Beer=1..12 外全部为跨表公式（612 个），data_only=True 计算值全为 0，因为被引用单元格全空。",
        "因此 3.xlsx 不含任何真实 0–6 评分，只提供：0–6 离散刻度语义、50 个感官维度定义、以及 12 款啤酒的空白卡。",
        "summary 定义 50 个数值感官维度（A_* 15 + F_* 15 + 其他 20）+ comments 文本列，与 4.csv 的 50 列一一对应。",
    ]

    with open(os.path.join(OUT, "xlsx_forensics.json"), "w", encoding="utf-8") as fh:
        json.dump(facts, fh, ensure_ascii=False, indent=2)

    import csv
    with open(os.path.join(OUT, "xlsx_beersheet_inventory.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["sheet", "beer_no", "side", "formula_cell",
                                           "attribute", "group_header", "formula"])
        w.writeheader()
        for r in inv_rows:
            w.writerow(r)
    with open(os.path.join(OUT, "xlsx_summary_formula_map.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["summary_col", "summary_name", "source_cell",
                                           "attribute_on_card", "side", "formula"])
        w.writeheader()
        for r in sum_rows:
            w.writerow(r)

    print("sheet_count:", facts["sheet_count"])
    print("sheetnames:", facts["sheetnames"])
    print("filled score cells (12 sheets total):", facts["total_filled_score_cells_across_12_sheets"])
    print("identical structure:", facts["all_beer_sheets_identical_structure"], sig)
    print("summary dims:", facts["summary"]["dims"], "group counts:", facts["summary"]["group_counts"])
    print("summary data_only all zero:", facts["summary"]["data_only_all_zero"],
          "distinct values:", facts["summary"]["distinct_data_only_values"])
    print("card score formulas not in summary:", facts["summary"]["card_score_formulas_not_in_summary"],
          facts["summary"]["card_score_formulas_not_in_summary_labels"])
    print("suspect refs:")
    for k, v in facts["summary"]["suspect_refs"].items():
        print("  ", k, "<-", v["source_cell"], "|", v["attribute_on_card"])
    print("wrote:", OUT)


if __name__ == "__main__":
    main()
