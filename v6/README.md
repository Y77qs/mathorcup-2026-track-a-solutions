# v6 · 确认性重跑（`beer-2026-a-v3` 续）—— DRAFT

**这是第五套完整解**：在 v5 / v5.1 的同一项目（`beer-2026-a-v3`）上继续做的**确认轮重跑**，
2026-10-27 11:07 生成 30 页论文与 DRAFT 交付包。项目**未冻结、质量门禁未通过**，因此是 **DRAFT**（`final=false, draft=true`）。

- 论文题目：《基于稳健表示、共表达网络与风格条件生成的啤酒化合物—感官强度建模》
- 目录时间：2026-10-24 起（沿用项目台账）→ 2026-10-27 11:17 交付说明
- 论文：**30 页**（ART-0008，`report/paper.pdf` 2,514,164 B），9 张确认性图（FIG-0032…0040）
- 台账：revision 4782；实验 **102** 个（86 succeeded / 10 failed / 6 queued）；验证 69 条；检查 45 项（33 passed / 11 needs_review / **1 failed**：QC-0033）
- 体量：1498 文件 / 约 116 MB（已按需裁剪大体量中间产物，见 §6）

> 与 v5 / v5.1 的关系：v5 是 2.8.10 首次跑到 final 的 18 页版本；v5.1 是其论文修订版（21 页）。
> v6 在同一项目上继续做**确认性实验与论文重写**（30 页、9 张确认图、Q1 嵌套交叉验证、Q2 候选宇宙拆分 216+15、Q3 凸二次规划证书），
> 但交付身份未冻结，仍为 DRAFT。

---

## 1. 状态判定（如实）

| 项 | 实际值 |
|---|---|
| `final` / `draft` | **false / true** |
| `engineeringComplete` / `qualityPassed` / `checkpointsPassed` | 均 **false** |
| freeze | **被工具拒绝**（`GATE_STAGE_SKIPPED`：多项 required 检查未通过） |
| 台账 `frozen` 字段 | 仍是 2026-10-24 的旧冻结记录（rev 2731），**不代表本轮** |
| 质量检查 | 45 项：33 passed / 11 needs_review / 1 failed（QC-0033） |
| 打包 | 仅 DRAFT（FINAL 打包被禁止）；`delivery/20261027-111607/` 只有 `package-warnings.json` 可证 |

论文摘要本身也标注：“DRAFT——科学证据与交付限制见文末，非最终提交版”；正文数字来自确认轮实验，但结论尚未过门禁。

## 2. 论文（`report/`，30 页）

| 文件 | 大小 | 说明 |
|---|---|---|
| `paper.pdf` | 2,514,164 B | **30 页**，9 图，ART-0008（绑 RENDER-0016） |
| `paper.md` | 95,405 B | 正文源（91 refs） |
| `rendered.md` / `rendered.refs.json` | 96,658 / 24,630 B | 渲染产物与引用映射（0 stale / 0 warning） |
| `paper.tex` / `paper.pandoc.md` | 130,625 / 112,466 B | LaTeX 源与 pandoc 中间件（ART-0007 / ART-0006） |
| `BUILD-INPUTS.json` / `paper.build.json` / `evidence_manifest.json` | — | 构建输入、构建记录、证据清单 |
| `pdf-audit.json` / `xelatex-1.log` / `xelatex-2.log` | — | PDF 结构审计与编译日志 |
| `tables/` | 39 文件（15 张表） | 表生成索引与 CSV/MD 表（`--verify` 19/19） |
| `text/` | 30 文件 | 逐页文本提取（核对排版用） |

**主要结果**（由渲染稿读出）：
Q1 Aroma/Flavour 30 维等权 MAE **0.3593**（中位数基线 0.3982）、50 维 **0.3505**（基线 0.3919）；
Q2 四方法 Top-3 平均两两 Jaccard **0.2091**（同源对照 0.1977）；Q3 归一化经验 V 能量距离 **0.8840**，
迁移综合不增率 **1.0**（由硬上界构造保证，不作为稳健性证据）。

## 3. 代码（`src/`，49 个 Python，1.3 MB）

| 模块 | 文件（节选） |
|---|---|
| 数据准备 | `prepare_base.py`、`prepare_q1mapped.py`、`prepare_q3.py`、`target_columns.py`、`q_common.py` |
| Q1 | `q1_baseline.py`、`q1_candidate.py`、`q1_fusion.py`、`q1_grade_all.py`、`q1_lib.py`、`q1_robust.py`、`q1_fix.py` |
| Q2 | `q2_baseline.py`、`q2_topk.py`、`q2_lib.py`、`q2_robust.py`、`q2_fix.py` |
| Q3 | `q3_baseline.py`、`q3_generate.py`、`q3_lib.py`、`q3_robust.py`、`q3_cert_audit.py`、`q3_zspace_recompute.py` 等 |
| 确认轮/审计 | `r00_build_splits.py`、`r00_constants.py`、`r00_contract_tests.py`、`r00_data_audit.py`、`r00_legacy_recheck.py`、`r03_evidence_rollup.py` |
| 论文/图表 | `build_paper.py`、`paper_tables.py`、`make_confirmatory_figures.py`、`make_paper_figures.py`、`ablation_summary.py`、`headline_audit.py` |
| 环境 | `env_verify.py`、`build/`（header.tex、template.tex） |

## 4. 数据、图、验证、输出

| 类别 | 内容 |
|---|---|
| 数据（14 MB） | `data/raw`（8 附件 + imported/staged）、`clean`、`processed`、`splits`（SPLIT-0001/0002） |
| 图（2.7 MB） | `figures/confirmatory/` **9 张确认图**（Q1 三张、Q2 两张、Q3 三张、ROB 一张）+ 13 张主图 + `archive/` |
| 验证（948 KB） | `validation/` 49 组目录；台账 69 条验证、17 个 validation plan |
| 输出（5.2 MB） | `outputs/audit/`（v6 审计：常量、口径冲突、契约测试、特征字典等）、`q1`、`q2`、`q3`、`contracts`、`robustness` |
| 题面/分析/参考 | `problem/`（题面 + questions）、`analysis/sensory/targetcolumns.csv`、`reference/Vibe-Math 2.8.10 使用指南` |

## 5. 实验（102 个，裁剪后 46 MB）

- 每个实验保留：`experiment.json`、`run.json`、`metrics.json`、`result.json`、`heartbeat.json`、`seed-receipt.json`、`stdout/stderr.log`、`outputs.json`、`predictions.csv`、`sets.json`、`figures/`（如有）。
- **未纳入**（体积原因）：`inputs/`（63 个目录，含每实验数据/代码副本，约 68 MB）、`repeat0/1/2` 稳健性重复（23 组，约 300 MB）、大批逐实验 CSV（bootstrap 采样、候选评分、分组表等，约 680 MB）。均可由 `src/` + `state/ledger.json` 重建。

## 6. 交付包（`delivery/`，30 MB）

| 文件 | 大小 | 说明 |
|---|---|---|
| `20261027-111607-DRAFT.tar.gz` | 28,174,344 B | **本轮唯一交付包**（DRAFT），197 个文件 + SHA256SUMS |
| `20261027-111607-DRAFT-SUPPORT.tar.gz` | 3,314,980 B | 支撑材料包 |
| `20261027-111607/package-warnings.json` | 70,994 B | FINAL 打包被拒的警告回执（证明只能 DRAFT） |

> 解包后的 DRAFT 目录（55 MB）与旧归档 `delivery/archive/`（v5 的 2 个包，39 MB）未重复纳入。

## 7. 其他材料

| 文件/目录 | 说明 |
|---|---|
| `DELIVERY-NOTES.md` | 本轮 DRAFT 交付说明（判定、产物 SHA、证据链、复核记录） |
| `REPRODUCE.md`、`ORIGINAL_TASK.md`、`CONTINUE.md`、`AI-USAGE.md` | 复现说明、原始任务、交接、AI 使用披露 |
| `论文修改建议.md`、`MathorCup_A_v5.1_面向复赛修改说明.md` | 论文修改建议与 v5.1 修改说明 |
| `MathorCup_A_独立审查与重跑方案/` | 独立复核、物理审查、统计协议、重跑清单与提示词、校验 CSV/JSON |
| `state/` | `ledger.json`（9.4 MB，rev 4782）、`scripts/`、`build/`、`env-verify/`（`devrun` 229 MB 与 `repro-clean` 51 MB 未纳入） |
| `rework-notes/` | 整理自 `.rework/` 的**文本类**材料：R00–R06 变更/决策/证据说明、PAPER-DRAFT-HANDOFF、VALIDATION-*、13 份独立审查 md/json、handoff 阶段报告与补丁、validation-selection |
| `bootstrap_pi.csv`、`sets.json`、`sets_pi_first.json` | Q2 Top-3 与 bootstrap 的中间结果 |

## 8. 本目录未纳入的材料（原项目 2.3 GB → 本目录 116 MB）

| 未纳入 | 原体积 | 说明 |
|---|---|---|
| `.rework/plugin`、`.rework/dist`、`.rework/plugin-review` | ≈ 79 MB | 2.8.10 插件源码、构建包、复审日志（插件材料） |
| `.rework/evidence`、`acceptance`、`previews`、`build-test` | ≈ 209 MB | 重跑证据、验收、预览、构建测试的原始二进制/页面 |
| `.rework/reviews/pages*` | ≈ 15 MB | 审查页面图片（文本类审查记录已收入 `rework-notes/reviews/`） |
| `state/devrun`、`state/repro-clean` | 280 MB | 运行日志与两次干净复现产物 |
| `report/revised-20261025/` | 13 MB | v5.1 修订目录，已作为仓库 `v5.1/` 单独归档 |
| 实验 `inputs/`、`repeat*/`、大批 CSV | ≈ 1.5 GB | 见 §5 |
| `__pycache__`、`.DS_Store`、`mplconfig` | — | 缓存 |

## 9. 复现

- 项目级：`REPRODUCE.md`
- 交付包内：`delivery/20261027-111607-DRAFT.tar.gz` 解压后的 `README_REPRODUCE.md`（台账生成，含解释器/依赖版本、数据与划分 hash、逐条命令）
- 论文重建：`src/build_paper.py --build --pdf --outdir report --allow-report-output`（pandoc + XeLaTeX）；表格 `src/paper_tables.py`；确认图 `src/make_confirmatory_figures.py`
- 说明：本轮 `freeze` 未成功，`frozen` 字段是 v5 的旧身份；任何“已冻结/已验证”表述都不适用于本目录。
