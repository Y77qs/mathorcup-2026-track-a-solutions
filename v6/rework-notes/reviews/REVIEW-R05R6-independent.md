# REVIEW-R05R6 CLAIM-0056 复审 + TGT-0001 派生审查

- 审查者：reviewer-1（independent_context；只写本文件 + REV-0079/REV-0080）
- 台账 revision 4562；未改被审对象，未跑 quality-plan/run/stale，未碰论文/交付。

| review | objectType | objectId | verdict | findings |
|---|---|---|---|---|
| REV-0079 | claim | CLAIM-0056 | passed | — |
| REV-0080 | targetContract | TGT-0001 | findings | F1 minor（3.xlsx 空白披露不在 active 字段） |

## CLAIM-0056 — passed
- 6 refs：EXP-0073:mae、EXP-0100/0101/0102:mae、EXP-0074:mae、EXP-0073:mae_all50，全部存在；值 0.35929156588219174 / 0.35422354618559243 / 0.36243390816790516 / 0.35763459908881995 / 0.39817732837288883 / 0.350504156920024，与 statement 一致。
- 独立复算：EXP-0073 oof A/F30=0.359291565882、all50=0.350504156920；EXP-0074=0.398177328373；ROB-0011 三值一致，spread=0.00821036198231273，相对=0.023178476。
- statement/scope/limitations 未被 link 改动；ROB-0011 绑定、2/3 种子、绝对/相对极差分列、旧 ROB-0007 历史均保留；REV-0076 F1 已解决。

## TGT-0001 — findings（F1 minor）
- 50 targetColumns 全在 DATA-0002（335 字段）；A/F30=前 30 列（15 A + 15 F），其余 20 列；EXP-0073 n_targets=30/50、features=231。
- labelOrigin=transformed 正确：4.csv 是 250×53 的 z 标准化连续感官值，不是 raw 0–6；0–6 是下游规则（MCON-0001/MCON 边界样例），labelRule=null 对连续 Y 绑定是刻意的。
- MCON-0001 6 分支 = clip(floor(6a+0.5),0,6)，200001 点扫描 0 不一致；7 个边界样例正确。
- EXP-0026/grades_all.csv 250×50 g6/g_cont；g6 vs clip(floor(g_cont+0.5),0,6) 0/12500 不一致；is_train=200/50；q1_grade_summary 每维 gradeCounts 和=250。
- 3.xlsx 实读：summary 12×50 全 0；12 个 beer_* 仅模板/描述词/0–5 刻度，无人工评分；4.csv 仅标准化值 → “空白评分卡/原始 0–6 不可恢复”事实成立。
- 当前 EXP-0073/VAL-0063/64/65/CLAIM-0056 绑定成立；EXP-0026 的 50 行留出是分级表交付，不是 current Q1 MAE 的 holdout（current Q1 train-only、无 holdout）。
- **F1**：当前 labelSource/note 不再显式写“3.xlsx 为空白评分卡、原始 0–6 不可识别/不可恢复”；仅 revisions[0].before 和 report/paper.md:97。REQ-0001 要求披露，建议 contract-revise 补回 active 字段（不改 targetColumns/规则）。
