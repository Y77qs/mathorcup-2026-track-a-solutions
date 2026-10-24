# 2026 MathorCup 大数据挑战赛 · 赛道 A 初赛 —— 三篇论文（v1 / v2 / v3，按时间顺序）

## 1. 三篇论文

| | 论文题目 | 时间（CST） | 页数 | 最终状态（是否可用） |
|---|---|---|---|---|
| [`v1/`](v1/) | 《数据缺失与尺度失配条件下啤酒感官评分、关键化合物识别与风格条件生成的建模研究》 | 2026-10-23 21:04–22:27 | 47（初版 44） | **不可用**：DRAFT（`final=false`），未冻结、未提交 |
| [`v2/`](v2/) | 《啤酒化学成分、感官映射与条件生成：实战整改审计草稿》 | 2026-10-24 10:48 | 5 | **不可用**：DRAFT，作者自述“不能作为通过质量验收的竞赛终稿” |
| [`v3/`](v3/) | 《基于化合物谱的啤酒风味预测、归因与风格条件生成》 | 2026-10-24 11:24–12:50 | 12（5 个版本） | **不可用**：DRAFT（`final=false`），未冻结、未提交 |

> 三篇都还是草稿，均未提交任何竞赛平台；“不可用”指不能直接作为正式提交物。

## 2. 三篇论文的关系

**v1 是第一套完整解**（10-23，47 页长报告）：把数据核实作为建模前置，交付四套 0–6 分级口径，正文数字全部由台账占位符渲染。

**v2 是一篇独立论文**（10-24 10:48，5 页），不是第三套解：它基于 v1 的**独立副本**（台账 rev 780/781），对存量预测做逐维复算后重写的“整改审计稿”。它与 v1 共享同一条证据链，并备份了 v1 的 47 页原稿。

**v3 是第二套完整解**（10-24 11:24–12:50，12 页）：另起炉灶，独立数据取证 + 更严格的台账/复现协议（配置冻结、plan 先于 candidate、holdout 曝光预算）。

按时间：**v1 → v2 → v3**。

## 3. 论文概括与复现

### v1 · 第一套完整解（47 页）

- **概括**：混合尺度、LOD/2 删失、原始 0–6 不可辨识等数据事实先行；Q1 做 50 维感官分级（四套显式映射口径），Q2 用共表达图 + 四方法 Borda 聚合给出 Top-3，Q3 做风格条件生成与缺陷约束迁移；结论按“已计划 / 真实执行 / 验证通过 / 被选中”区分。
- **材料**：`v1/paper/`（md/tex/pdf + 历史版本）、`v1/src/`（39 个 Python）、`v1/data/`、`v1/experiments/`（48 个）、`v1/figures/`（20 张）、`v1/ledger.json`、`v1/delivery/FINAL-DRAFT-2-DRAFT.tar.gz`
- **复现**：见 `v1/REPRODUCE.md`；Python 3.12 + numpy/pandas/scipy/sklearn/matplotlib/openpyxl，`bash paper/build.sh` 重建 PDF（需 pandoc + XeLaTeX）

### v2 · 独立审计论文（5 页）

- **概括**：复算 v1 存量预测（EXP-0029 的 2500 个 beer×dim 单元格：逐维 R² 平均 0.253574，`overall` 仅 0.009210），核查 Q2 候选与 Q3 依赖问题，结论是“指标一致但不构成独立复跑证明”，故保持草稿。
- **材料**：`v2/practical-final-20261024-DRAFT/`（`report/` 论文与审计证据、`src/` 42 个 Python、`figures/` 31 张、`data/`、`experiments/`、`SHA256SUMS`）、`v2/REPAIR-SNAPSHOT.json`
- **复现**：见 `v2/practical-final-20261024-DRAFT/README_REPRODUCE.md`；完整性核对 `cd practical-final-20261024-DRAFT && shasum -a 256 -c SHA256SUMS`

### v3 · 第二套完整解（12 页）

- **概括**：重新做数据口径取证后，Q1 交付 50 维 mapped grade 多输出回归（基线 MAE 0.8011 → Ridge 0.7051），Q2 用三方法交叉核对给出 Top-3 并量化稳定性，Q3 做风格条件生成 + 缺陷约束迁移（不恶化率 1.000）。
- **材料**：`v3/paper/`（5 个版本 PDF）、`v3/src/`（20 个 Python + 8 个取证脚本）、`v3/analysis/`、`v3/data/`、`v3/experiments/`（20 个）、`v3/figures/`（9 张）、`v3/ledger.json`、`v3/delivery/round2-final-DRAFT.tar.gz`
- **复现**：见 `v3/docs/DELIVERY-NOTES.md` 第 5 节；按 `src/prepare.py → build_*.py → q1/q2/q3 → make_figures.py → build_paper.py` 顺序执行

> 更细的目录说明、未完成项与缺陷披露见各论文目录的 `README.md`、`docs/` 与原始台账。
