# 共享上下文（Lead 维护，teammates 只读）

## 环境
- 工作目录：`/Users/baozhashizitou/Documents/MATHORCUP`
- 原始数据（只读，禁止修改）：`work/my-new-contest/data/raw/`
  - `1.csv` 250×234（beer, beer_id, tasting_category_fine + 231 化合物/理化特征）
  - `2.csv` 231×231（化合物×化合物相关矩阵，首列 Unnamed:0）
  - `3.xlsx` 13 sheets（beer_1..beer_12 + summary）
  - `4.csv` 250×53（3 元数据 + 50 感官列）
  - `5.csv` 50×51（感官×感官相关矩阵）
  - `6.csv` 44×51（化学/理化×感官交叉相关矩阵，实际 44×50）
  - `7.csv` 250×189（3 元数据 + 186 感官描述符）
  - `8.xlsx` 7 sheets（Sensory thresholds / Sensory names / GBM importance MDI / GBM SHAP Values / Calibrated chemical dataset / Beer Prices / Sheet2 空）
  - `数据说明.txt`（官方口径：2/5/6.csv 均称 Spearman）
- Python（唯一可用环境，pandas/openpyxl/numpy 已装）：
  `/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3`
- 题面 PDF：`work/my-new-contest/problem/2026年MathorCup大数据挑战赛-赛道A初赛.pdf`
  - SHA256 = `494025cf76c5d47af576927fcf6cd3a073d61db5842d56aaf0ad4da5f4660a78`
  - 逐字抽取文本见 `A/problem/statement.txt`（同一 PDF，已核验 SHA；3 页，无公式/表/图）
- 往期运行目录 `A/` 存在（另一个 agent 的完整跑分），**只能当线索，不可当证据**；所有结论必须自己从 raw 数据重算并给数字。

## 交付物约定（写盘范围，互相不越界）
- Lead：`analysis/` 根目录的汇总报告与 `analysis/scripts/verify_all.py`
- 相关性取证：`analysis/corr/` + `analysis/scripts/corr_*.py`
- 感官目标/0–6：`analysis/sensory/` + `analysis/scripts/sensory_*.py`
- 8.xlsx/交叉审计：`analysis/ref/` + `analysis/scripts/ref_*.py`
- 每个结论必须带：源文件、sheet/列、脚本路径、可复现命令、精确数字（保留足够小数）。
- 报告用中文 Markdown；数值表另存 csv/json 供 Lead 汇总。禁止修改 raw 数据。

## 用户要回答的五个问题（按分配各管一段）
1. 最终 targetColumns：题面“约 40”，4.csv 实际 50 个感官列；按 3.xlsx summary/12 beer sheet 与 4.csv 实际列对齐后决定，不能照抄 40 或 50。
2. 0–6 分口径：4.csv 是标准化/中心化连续值；3.xlsx 是 0–6 评分卡。必须先说明能否还原、如何还原；不能把标准化值直接叫 0–6 分。
3. 2.csv 相关类型：题面正文写 Pearson，数据说明写 Spearman；核验矩阵属性与说明，论文中如实标注。
4. 8.xlsx 的 sheet：按实际 sheet 使用（Sensory thresholds、Sensory names、GBM importance MDI、GBM SHAP Values、Calibrated chemical dataset、Beer Prices 等）。
5. 3.xlsx sheet 数：题面说 10 个（beer_1~10），实际 12 beer sheet + summary；以实际文件为准，不删不减。

## 汇报要求
- 完成后用 send_message 给 lead：≤300 字结论摘要 + 产出文件绝对路径 + 任何不确定/存疑点。
- 若与他人结论冲突，先查自己的复现脚本，再在消息里指出分歧与证据。
