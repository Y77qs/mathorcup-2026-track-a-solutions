# 2026 MathorCup 大数据挑战赛 · 赛道 A 初赛 —— 八篇论文（v1 / v2 / v3 / v4 / v5 / v5.1 / v6 / v6.1，按时间顺序）

## 1. 八篇论文

| | 论文题目 | 时间（CST） | 页数 | 最终状态（是否可用） |
|---|---|---|---|---|
| [`v1/`](v1/) | 《数据缺失与尺度失配条件下啤酒感官评分、关键化合物识别与风格条件生成的建模研究》 | 2026-10-23 21:04–22:27 | 47（初版 44） | **不可用**：DRAFT（`final=false`），未冻结、未提交 |
| [`v2/`](v2/) | 《啤酒化学成分、感官映射与条件生成：实战整改审计草稿》 | 2026-10-24 10:48 | 5 | **不可用**：DRAFT，作者自述“不能作为通过质量验收的竞赛终稿” |
| [`v3/`](v3/) | 《基于化合物谱的啤酒风味预测、归因与风格条件生成》 | 2026-10-24 11:24–12:50 | 12（5 个版本） | **不可用**：DRAFT（`final=false`），未冻结、未提交 |
| [`v4/`](v4/) | 《混合尺度化合物谱下的啤酒感官分级预测、Top-3 关联解析与风格条件生成》 | 2026-10-24 13:31–14:45 | 45 | **可用（final）**：台账 14:38:50 冻结、产出 2 个非 DRAFT 交付包；但论文文本渲染于冻结前，仍写“DRAFT”，对外前需重渲染 |
| [`v5/`](v5/) | 《基于稳健表示、共表达网络与风格条件生成的啤酒化合物—感官强度建模》 | 2026-10-24 19:20–22:40 | 18 | **可用（final）**：台账 22:36:58 冻结，`final=true`，交付包 `20261024-223751`（非 DRAFT），论文与 final 状态一致 |
| [`v5.1/`](v5.1/) | 同上（修订版） | 2026-10-25 09:15 | 21（8 图） | **可用（论文修订稿）**：按修改建议重写摘要/图表/表格并复核，结果沿用 v5、未新跑实验；不改 v5 台账 |
| [`v6/`](v6/) | 同上（确认性重跑） | 2026-10-27 11:07 | 30（9 图） | **不可用（DRAFT）**：QC-0033 failed、freeze 被拒，`final=false`；交付为 DRAFT 包 |
| [`v6.1/`](v6.1/) | 同上（复赛修正轮） | 2026-10-27 22:07 | 38（9 图） | **不可用（DRAFT）**：`final=false`、`qualityPassed=false`；V6.1 显式恢复轮后仍 DRAFT |

> v1–v3 均为草稿，未提交任何竞赛平台；v4、v5 是两套由台账判定为 final 的完整解；v5.1 是 v5 论文的修订版；v6 是确认性重跑、v6.1 是同日的复赛修正轮，两者均因门禁未过而保持 DRAFT。

## 2. 八篇论文的关系

**v1 是第一套完整解**（10-23，47 页长报告）：数据核实作为建模前置，交付四套 0–6 分级口径，正文数字全部由台账占位符渲染。

**v2 是一篇独立论文**（10-24 10:48，5 页），不是新解：基于 v1 的独立副本（台账 rev 780/781），对存量预测逐维复算后重写的整改审计稿，共享 v1 证据链并备份其 47 页原稿。

**v3 是第二套完整解**（10-24 11:24–12:50，12 页）：另起炉灶，独立数据取证 + 更严格的台账/复现协议，最终仍为 DRAFT。

**v4 是第三套完整解**（10-24 13:31–14:45，45 页）：按 2.8.6 重跑指南新开 `beer-2026-a-v2`，同题重做数据契约与实验；Q1 独立复跑通过后冻结，首个达到 final 的一套（论文措辞滞后未重渲染）。

**v5 是第四套完整解**（10-24 19:20–22:40，18 页）：插件升级到 2.8.10 后新开 `beer-2026-a-v3`，方法学重写（图正则低秩多输出、风格分层 bootstrap、分层收缩 Copula、五条硬缺陷约束）；三项稳健性与九项消融全部完成，`final=true` 且论文与 final 状态一致。

**v5.1 是 v5 的论文修订版**（10-25 09:15，21 页 / 8 图）：同一套结果，按《论文修改建议》重写摘要与正文、补 Top-3 全表与迁移逐样本核验、重绘图表并做复核；未新跑实验、未改台账。

**v6 是确认性重跑**（10-27 11:07，30 页 / 9 图）：在 v5 的同一项目上继续做确认轮实验（Q1 四模型共用嵌套交叉验证、Q2 候选宇宙拆 216 单体 + 15 扩展、Q3 凸二次规划证书），重写论文并产出 DRAFT 交付包；因 QC-0033 failed 与 required 检查未过，freeze 被拒，`final=false`。

**v6.1 是复赛修正轮**（10-27 22:07，38 页 / 9 图）：在 v6 上按“v6.1 显式恢复轮”重跑 Q3 截距/NA/边际/V 选参、Q2 方向一致率与完整可行域基线等科学修正，论文扩至 38 页；交付仍为 DRAFT（`final=false`、`qualityPassed=false`）。

按时间：**v1 → v2 → v3 → v4 → v5 → v5.1 → v6 → v6.1**。

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

### v4 · 第三套完整解（45 页，final）

- **概括**：2.8.6 干净重跑。Q1 常数基线 MAE 0.7509 → Ridge 0.6685（OOF 0.6744，选模只用 train-only OOF）；Q2 逐维 Top-3 Jaccard 0.2247（全局基线 0.200）、bootstrap 频率 0.4616；Q3 约束满足率 1.0 但为投影构造（未投影 0.04），能量距离 3.50 vs 3.49；稳健性 Q2/Q3 通过、Q1 未通过（相对极差约 180%，作为负结果保留）。
- **材料**：`v4/report/`（45 页论文三格式 + 6 份证据文档）、`v4/src/`（18 个 Python）、`v4/data/`（6 数据集 + 17 套划分）、`v4/experiments/`（35 个）、`v4/validation/`（41 条）、`v4/state/ledger.json`、`v4/delivery/`（3 个交付包：1 个 DRAFT + 2 个 final，含 tar.gz）
- **复现**：见 `v4/delivery/20261024-144253/README_REPRODUCE.md`；代码顺序 `src/00_prepare_q1q2.py → 00_prepare_q3.py → 00_prepare_pools.py → q1/q2/q3 各脚本 → validate_q2/q3.py`；论文用 `delivery/build_paper.py` 重建

### v5 · 第四套完整解（18 页，final）

- **概括**：2.8.10 重做。Q1 图正则低秩多输出 + OOF 融合：50 维平均 MAE **0.4006 → 0.3466**（R²₅₀ 0.2317）；Q2 四方法 Top-3（总体/风格残差化 Spearman + 图低秩 + 共识）平均 Jaccard **0.2187**（维度无关基线 0.2000），bootstrap 入选频率 π 普遍偏低；Q3 分层收缩 Copula + 五条硬缺陷约束：满足率 **1.0**、缺陷超阈率 **0.852 → 0**（真实数据 0.844）；三项预注册稳健性与九项消融全部完成，失败与限制原样披露。
- **材料**：`v5/report/`（18 页论文 6 个文件）、`v5/src/`（24 个 Python）、`v5/data/`（raw/clean/processed/splits）、`v5/experiments/`（36 个）、`v5/validation/`（43 条）、`v5/figures/`（13 张 + 2 张归档）、`v5/state/ledger.json`、`v5/delivery/`（final `20261024-223751` + DRAFT `20261024-DRAFT`，含 tar.gz）、`MODELING-BLUEPRINT.md`（建模方案）、`ORIGINAL_TASK.md` / `DELIVERY-NOTES.md` / `REPRODUCE.md` / `CONTINUE.md`
- **说明**：按需求**不含** 2.8.10 插件相关材料（原 `.rework/` 的插件源码、构建包、复验证据等约 151 MB），详见 `v5/README.md` §5
- **复现**：见 `v5/delivery/20261024-223751/README_REPRODUCE.md`；代码顺序 `prepare_base.py → prepare_q1mapped.py → prepare_q3.py → q1_* → q2_* → q3_* → make_paper_figures.py → build_paper.py`

### v5.1 · v5 论文修订版（21 页）

- **概括**：沿用 v5 结果，重写为投稿体：摘要去工程化、Beer#1–Beer#10 的 0–6 评分、核心 Top-3 大表（20 维）与附录完整 50 维（150 条）、按酯类/萜烯/高级醇/有机酸/硫化物讨论化学合理性、实际网络连接图、三风格生成画像、迁移前后浓度与逐样本缺陷核验、稳健性与九项消融汇总；并纠正 9 处实质表述（如 S 为原样本点估计、219 候选含非单体指标、感官代理为 Ridge、稳定性扰动未含 stale hops）。
- **材料**：`v5.1/paper/`（pdf 21 页 / md / tex / 修改说明）、`v5.1/figures/`（8 张）、`v5.1/data/`（8 份支撑表：250×50 评分、Beer#1–10、150 条 Top-3、数据字典、网络节点、310 行生成谱、风格画像、迁移对照）、`v5.1/support/`（重建/复核脚本、manifest、哈希、逐页核对图）、`v5.1/论文修订版_含图表与支撑数据.zip`
- **复现**：`support/prepare_revision.py → build_revision.py → latexmk -xelatex → verify_revision.py`（详见 `v5.1/README.md` §4）

### v6 · 确认性重跑（30 页，DRAFT）

- **概括**：沿用 v5 项目做确认轮：Q1 在图 Ridge/低秩/中位数/HGB 上统一嵌套交叉验证（30 维 MAE 0.3593 vs 基线 0.3982；50 维 0.3505 vs 0.3919）；Q2 把候选拆为 216 个严格单体 + 15 个扩展指标，四方法 Top-3 平均 Jaccard 0.2091；Q3 用含编码质量点的收缩 Copula 生成（归一化能量距离 0.8840）并以凸二次规划迁移（综合不增率 1.0，由硬上界构造保证）；稳健性按种子/参数/预算扰动分列，失败与结构性不可满足项如实披露。
- **材料**：`v6/report/`（30 页论文 6 件 + BUILD-INPUTS/evidence_manifest/pdf-audit + 15 张表 + 30 份逐页文本）、`v6/src/`（49 个 Python）、`v6/data/`、`v6/experiments/`（102 个，保留元数据/输出/predictions）、`v6/validation/`（69 条）、`v6/figures/`（9 张确认图 + 13 张主图）、`v6/outputs/`、`v6/state/ledger.json`（rev 4782）、`v6/delivery/`（DRAFT 包 28.2 MB + 支撑包 3.3 MB）、`v6/rework-notes/`（审查与变更记录文本）、`v6/DELIVERY-NOTES.md`
- **说明**：本目录为 2.3 GB 原项目的裁剪归档（116 MB）：未含插件 `.rework/plugin|dist|plugin-review`、`state/devrun`、`state/repro-clean`、实验 `inputs/`、`repeat*/` 与大批逐实验 CSV，清单见 `v6/README.md` §8
- **复现**：`REPRODUCE.md` 与 DRAFT 包内 `README_REPRODUCE.md`；论文重建 `src/build_paper.py --build --pdf ...`，表格 `src/paper_tables.py`，确认图 `src/make_confirmatory_figures.py`

### v6.1 · 复赛修正轮（38 页，DRAFT）

- **概括**：在 v6 上做复赛修正：Q1 四模型共用嵌套交叉验证（30 维 MAE 0.3593 vs 基线 0.3982；50 维 0.3505 vs 0.3919）；Q2 新增“与总体 Spearman 同方向的一致率”0.9817（旧 P(ρ>0) 仅作历史对照），四方法 Top-3 平均 Jaccard 0.2091；Q3 修正截距/NA/边际与 V 选参，化学 t2n 与感官代理分列，199 个 QP 证书均最优、交付策略转移能量 2.0799；稳健性按问题分列并披露结构性未通过项。
- **材料**：`v6.1/paper/`（38 页 pdf 3.11 MB + md/tex/rendered/refs + BUILD-INPUTS/evidence_manifest/pdf-audit + 15 张表 + 30 份逐页文本）、`v6.1/src/`（52 个 Python）、`v6.1/data/`、`v6.1/experiments/`（133 个，保留元数据/输出/predictions）、`v6.1/validation/`（77 条）、`v6.1/figures/`（9 张确认图 + confirmatory_v2 + 主图，共 43 PNG）、`v6.1/outputs/`、`v6.1/state/ledger.json`（rev 5220）、`v6.1/delivery/`（DRAFT 32.2 MB + support 21.7 MB + FINAL 被拒回执）、`v6.1/rework-notes/`、`v6.1/DELIVERY-NOTES.md`
- **说明**：原项目约 3.0 GB → 本目录 202 MB；未含 `state/devrun`（1.2 GB）、`state/repro-clean`（365 MB）、插件 `.rework` 材料、实验 `inputs/`/`repeat*/`/大批 CSV、DRAFT 包内 `revised-20261025`（已单列为 `v5.1/`），清单见 `v6.1/README.md` §7
- **复现**：`REPRODUCE.md` 与 DRAFT 包内 `README_REPRODUCE.md`；论文重建 `src/build_paper.py --build --pdf --no-caption-ids --outdir report --allow-report-output`，表格 `src/paper_tables.py`，确认图 `src/make_confirmatory_figures.py`

> 更细的目录说明、未完成项与缺陷披露见各论文目录的 `README.md`、`docs/` 与原始台账。
