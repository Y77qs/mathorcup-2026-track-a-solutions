# 2026 MathorCup 大数据挑战赛 · 赛道 A 初赛 —— 两套完整解与一次整改审计（v1 / v1-audit / v2）

本仓库把**同一道赛题**（2026 年 MathorCup 大数据挑战赛 赛道 A 初赛：商用啤酒化合物 / 感官数据建模）的
**两套完整解题论文与相关代码**、以及其后对第一套的**一次整改审计**，按时间先后整理为 `v1/`、`v1-audit/`、`v2/` 三个自包含目录。
每个目录都保留原始台账（ledger）、实验元数据与交付包，便于追溯论文中每个数字的来源。

- 归档时间：2026-10-24（源工作区快照）
- 题面：`2026年MathorCup大数据挑战赛-赛道A初赛.pdf`（各目录 `problem/` 或 `report/` 下均有）
- 赛题三问：Q1 用化合物数据预测 50 维感官评分；Q2 识别每个感官维度的 Top-3 关键化合物；Q3 风格条件生成与跨风格迁移

> **状态声明**：三份论文都是 **DRAFT**。项目台账 `final=false`，未冻结、未提交任何竞赛平台；
> 各自 `docs/`（或 `report/`）中保留了当时如实写下的未完成项与缺陷披露（`STATUS.md`、`DELIVERY-NOTES.md`、论文开头引文）。
> 本仓库是**归档**，不是官方提交物。

---

## 1. 目录（按时间顺序）

| 目录 | 项目 | 时间（CST） | 论文 | 规模 |
|---|---|---|---|---|
| [`v1/`](v1/) | `mathorcup-2026-a` · 第一套完整解 | 2026-10-23 21:04 → 22:27 | **47 页**（初版 44 页） | 662 文件 / 53 MB |
| [`v1-audit/`](v1-audit/) | 同一项目的**独立副本整改审计**（非新解） | 2026-10-24 10:48 | **5 页**审计草稿（内含 47 页 v1 原稿备份） | 200 文件 / 12 MB |
| [`v2/`](v2/) | `beer-2026-a` · 第二套完整解 | 2026-10-24 11:24 → 12:50 | **12 页**（5 个版本） | 384 文件 / 34 MB |

- **v1**：长报告式论文，数据核实作为建模前置，交付四套 0–6 分级口径；39 个 Python、48 个实验、15 张登记图、3 个 DRAFT 交付包（保留最终 1 个）。
- **v1-audit**：在 v1 的独立副本上做的复核与重打包——新增存量预测逐维复算（`src/q1_recompute_exp0029.py`、`src/engineer_q1_audit.py`），
  产出 5 页审计草稿；包内 `report/history/pre-practical-repair/paper.pdf` 是 v1 的 47 页原稿备份（与 `v1/paper/paper.pdf` 字节一致）。
- **v2**：竞赛投稿式论文，重新做了独立数据取证（`analysis/`），台账/复现协议更严格（配置冻结、plan 先于 candidate、holdout 曝光预算）；20 个 Python + 8 个取证脚本、20 个实验、7 张登记图、5 个 DRAFT 交付包（保留最终 1 个）。

每个目录内的 `README.md` 说明该目录结构、论文版本、复现入口与被省略的大文件。

---

## 2. 时间线

| 时间 | 事件 | 产物位置 |
|---|---|---|
| 10-23 21:04 | v1 建台账，开始数据核实 | `v1/` |
| 10-23 21:08–21:57 | 审计 → 尺度识别 → 清洗 → 划分；Q1/Q2/Q3 模型与基线 | `v1/src/` |
| 10-23 22:01 | v1 论文初版（44 页） | `v1/paper/versions/2026-10-23-2201-44pages.pdf` |
| 10-23 22:19 | v1 论文定稿重排（47 页） | `v1/paper/paper.pdf` |
| 10-23 22:20 | v1 最终交付快照（193 文件） | `v1/delivery/FINAL-DRAFT-2-DRAFT.tar.gz` |
| 10-24 10:48 | v1 独立副本整改审计 → 5 页草稿 + 重打包 | `v1-audit/report/paper.pdf`、`v1-audit/practical-final-20261024-DRAFT/` |
| 10-24 11:24–11:48 | v2 建立；5 份数据口径取证报告（先于建模） | `v2/analysis/` |
| 10-24 12:02–12:17 | v2 三个数据版本 + 建模脚本 + 出图 | `v2/src/`、`v2/figures/` |
| 10-24 12:22 | v2 论文 v1（12 页） | `v2/paper/versions/2026-10-24-1222-v1.pdf` |
| 10-24 12:36 | v2 Round 1（补基线/审查记录） | `v2/paper/versions/2026-10-24-1236-round1.pdf` |
| 10-24 12:42 | v2 Round 2（独立复跑通过） | `v2/paper/versions/2026-10-24-1242-round2.pdf` |
| 10-24 12:43 | v2 终稿（12 页） | `v2/paper/paper.pdf` |
| 10-24 12:48 | v2 最终 DRAFT 包 | `v2/delivery/round2-final-DRAFT.tar.gz` |

更细的工作区级扫描清单见 [`docs/workspace-inventory.md`](docs/workspace-inventory.md)（保留原工作区路径，用于对照）。

---

## 3. 三者的关系

- **v1（10-23）**：先完成的完整解，论文 47 页、113 个占位符全部由台账渲染、11 条 claim；方法学主线是区分“已计划 / 真实执行 / 验证通过 / 被选中”。
- **v1-audit（10-24 10:48）**：不是新解。它读取 v1 独立副本的台账（rev 780/781）与存量预测，做逐维复算后重写了一份 5 页审计草稿，
  并重新打包（包名 `practical-final-20261024-DRAFT`）。作者自述“DRAFT，不能作为通过质量验收的竞赛终稿”。
- **v2（10-24 11:24 起）**：另起炉灶的完整解，12 页投稿体；数据取证单独成章，协议更严格，但仍因 `contest.yaml` 在 init 后修改导致的 sha 冲突而无法 `final=true`。

三套的局限与未完成项都在各自文档中逐条列出，未作修饰。

---

## 4. 复现

三个目录都是自包含的：论文（md/tex/pdf + 构建脚本）、`src/`（建模代码）、`data/`、`experiments/`、`figures/`、
`ledger`（台账或台账摘要）、`contest.yaml`（协议配置）。

- v1：见 [`v1/REPRODUCE.md`](v1/REPRODUCE.md)
- v1-audit：见 [`v1-audit/README.md`](v1-audit/README.md) 与包内 `practical-final-20261024-DRAFT/README_REPRODUCE.md`
- v2：见 [`v2/docs/DELIVERY-NOTES.md`](v2/docs/DELIVERY-NOTES.md) 第 5 节「复现入口」
- 依赖：Python 3.12 + numpy / pandas / scipy / scikit-learn / matplotlib / openpyxl；论文另需 pandoc + XeLaTeX（ctexart）

> 原机器的绝对路径（`/Users/...`）仍出现在部分复现文档中，请按本仓库布局替换为相对路径。

---

## 5. 被省略的大文件

为控制仓库体积，以下内容未纳入（均可由 `src/` 重新生成，或按需从原位置取回）：

| 省略项 | 原体积 | 说明 |
|---|---|---|
| v1 `outputs/q1`、`q3`、`q2` 的大体量中间产物 | ≈ 400 MB | 论文引用的汇总 JSON 已保留在 `v1/outputs/`；逐维度/逐样本大表可由 `src/` 重跑 |
| 历史交付压缩包（仅保留各自最终一个） | v1 少 2 个 / v2 少 4 个 | 保留 `v1/delivery/FINAL-DRAFT-2-DRAFT.tar.gz` 与 `v2/delivery/round2-final-DRAFT.tar.gz` |
| v1-audit 的原始压缩包 | 7,154,835 B | 内容已原样解包在 `v1-audit/practical-final-20261024-DRAFT/`，可用其 `SHA256SUMS` 校验 |
| 后续重跑材料（指南、重跑准备审计、v2 重跑进行中快照） | ≈ 1 MB | 已按需求从仓库移除（原工作区仍在） |
| `__pycache__`、`.DS_Store`、`mplconfig` 等缓存 | — | 已清理 |

---

## 6. 变更记录

- 2026-10-24 首版归档：三个包 `packages/01-A-…`、`packages/02-beer-…`、`packages/03-rerun-2.8.6`。
- 2026-10-24 按需求调整：移除 `03` 重跑材料包；两套完整解按时间顺序重命名为 `v1`（A 项目）与 `v2`（beer 项目）。
- 2026-10-24 追加：从 `…/建模实战整改最终交付/竞赛副本产物/` 收入 `v1-audit/`（5 页审计草稿 + 完整解包内容）。

---

## 7. 权利与用途

论文、代码、图表由仓库所有者（Y77qs）完成，用于竞赛归档与复现；赛题与附件数据版权归 MathorCup 组委会所有，
仅在竞赛与学习范围内使用。若需引用，请注明本仓库与原始时间。
