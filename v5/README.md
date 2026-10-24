# v5 · 第四套完整解（`beer-2026-a-v3`，2.8.10 插件）—— 第二套 final

**这是五篇论文中的第五篇，也是第二套由台账判定为 final 的完整解**：2026-10-24 19:20 建档、22:36:58 冻结，
论文 **18 页 / 14 图**，交付包 `delivery/20261024-223751`（**非 DRAFT**，`final=true`）。

- 论文题目：《基于稳健表示、共表达网络与风格条件生成的啤酒化合物—感官强度建模》
- 项目：`beer-2026-a-v3`（插件 `dsh-vibe-math` **2.8.10**，`buildId=2.8.10+cefef8a`；seed=20261024，主指标 mae）
- 时间：2026-10-24 19:20:58 → 22:40（最后一次台账写入）
- 台账：revision 2760，冻结于 **22:36:58**（rev 2731）
- 体量：1510 文件 / 约 128 MB（**不含** 2.8.10 插件相关材料，见 §5）

> 与 v4 的关系：v4（`beer-2026-a-v2`，45 页，14:45 结束）之后新开的一轮，同题同附件但方法学重写：
> 图正则低秩多输出 + 风格内残差化 + 风格分层 bootstrap + 分层收缩 Copula + 五条硬缺陷约束；插件版本从 2.8.6 升到 2.8.10。

---

## 0. 建模方案（蓝图）

[`MODELING-BLUEPRINT.md`](MODELING-BLUEPRINT.md) —— 本项目所依据的最终建模蓝图（作者提供，941 行，66 组公式）：
统一符号与三问目标；“尺度—编码—单位—证据”字典与地板编码/缺失处理；Q1 图正则低秩多输出与有界相对分级；
Q2 共表达网络、风格混杂分析与稳定 Top-3；Q3 风格收缩混合边际 Copula 与低缺陷生成；
跨风格分位数映射初始化 + 最小改动约束优化；验证设计与裁决规则；九项必做消融；最终结果要求。

---

## 1. 论文

| 文件 | 大小 | 说明 |
|---|---|---|
| `report/paper.pdf` | 1,278,067 B | **18 页**，14 图，最终 PDF（ART-0004，绑 RENDER-0009） |
| `report/paper.md` | 41,859 B | 正文源，185 个台账占位符 |
| `report/rendered.md` | 50,929 B | 渲染产物（185/185 解析，0 stale） |
| `report/rendered.pandoc.md` | 50,947 B | pandoc 输入（U+2208=0） |
| `report/rendered.refs.json` | 55,712 B | 占位符 ↔ 台账引用 |
| `report/paper.tex` | 67,131 B | LaTeX 源（ART-0003） |

**结构**：摘要 + 9 章（问题重述 / 数据审计与统一数据字典 / 符号框架 / Q1 图正则低秩多输出与有界相对分级 / Q2 共表达网络、风格混杂与稳定 Top-3 / Q3 风格条件生成与跨风格迁移 / 验证设计与稳健性 / 九项必做消融汇总 / 结论建议与局限）+ 附录 A 复现、附录 B 台账索引。

**核心结果**：Q1 50 维平均 MAE **0.4006 → 0.3466**（R²₅₀ = 0.2317）；Q2 Top-3 平均 Jaccard **0.2187**（维度无关基线 0.2000），入选频率 π 均值很低、无化合物 π=1；Q3 约束满足率 **1.0**、缺陷超阈率 **0.852 → 0**（真实数据 0.844），目标马氏距离显著下降但“策略相对不恶化率”是投影构造保证、须与严格不增口径分开读；三项预注册稳健性全部通过、九项必做消融逐项完成，失败与限制按原样披露。

## 2. 代码（`src/`，24 个 Python，约 420 KB）

| 模块 | 文件 |
|---|---|
| 数据/公共 | `prepare_base.py`、`prepare_q1mapped.py`、`prepare_q3.py`、`target_columns.py`、`q_common.py` |
| 问题一 | `q1_lib.py`、`q1_baseline.py`、`q1_candidate.py`、`q1_fusion.py`、`q1_grade_all.py`、`q1_robust.py` |
| 问题二 | `q2_lib.py`、`q2_baseline.py`、`q2_topk.py`、`q2_robust.py` |
| 问题三 | `q3_lib.py`、`q3_baseline.py`、`q3_generate.py`、`q3_robust.py` |
| 论文/审计 | `build_paper.py`、`make_paper_figures.py`、`ablation_summary.py`、`headline_audit.py` |

## 3. 副产物（全部纳入本目录）

| 类别 | 内容 |
|---|---|
| 题面 | `problem/`：原题 PDF、`statement.md`、`questions.yaml`、`数据说明.txt` |
| 数据 | `data/raw`（8 附件 + imported/staged）、`data/clean`（6 文件）、`data/processed`（字段契约 + 分级参数/摘要）、`data/splits`（SPLIT-0001/0002） |
| 实验 | `experiments/EXP-0001…0036`：**34 succeeded / 1 failed（EXP-0012）/ 1 queued（EXP-0027）** |
| 验证 | `validation/` 33 组目录、台账 43 条：leakage 11、holdout-metrics 11、independent-rerun 10、simulation-seeds 7、split-integrity 2、baseline-compare 2 |
| 图 | `figures/` 13 张 PNG + `figures/archive/` 2 张被替代旧图；台账登记 31 张（其余在 `experiments/*/figures/`） |
| 交付包 | `delivery/20261024-223751/`（**FINAL**，198 文件）+ `.tar.gz`（7,328,123 B，sha256 `21c9ec18…`）；`delivery/20261024-DRAFT/`（197 文件）+ `.tar.gz`（7,234,683 B） |
| 台账与运行痕迹 | `state/ledger.json`（4.1 MB，rev 2760）、`state/devrun/`（21 MB，42 个模型运行目录/日志）、`state/scripts/`、`state/build/` |
| 审计 | `outputs/audit/audit.json`、`scale_identification.csv`；`analysis/sensory/targetcolumns.csv` |
| Q2 中间数据 | `bootstrap_pi.csv`（782 KB）、`sets.json`、`sets_pi_first.json` |
| 文档 | `ORIGINAL_TASK.md`（完整任务书）、`DELIVERY-NOTES.md`（最终交付说明）、`REPRODUCE.md`、`CONTINUE.md`、`docs/AGENT-BRIEF.md` |

## 4. 最终判定（`delivery/20261024-223751/delivery-status.json`）

| 字段 | 值 |
|---|---|
| `final` / `draft` | **true / false** |
| `engineeringComplete` | true（51/51 工程检查） |
| `qualityPassed` | true（27 passed / 5 not_applicable / 0 failed / 0 stale） |
| `checkpointsPassed` / `blocking` | true / `[]` |
| 选中模型 | Q1 `MODEL-0004`（EXP-0004）、Q2 `MODEL-0012`（EXP-0029）、Q3 `MODEL-0013`（EXP-0033） |

## 5. 归档说明：已排除的 2.8.10 插件材料

按要求，本目录**不包含** 2.8.10 插件相关材料。原项目中这些内容位于 `.rework/`（约 151 MB / 3479 文件）：

| 已排除 | 原体积 | 内容 |
|---|---|---|
| `.rework/plugin/` | 69 MB | 2.8.10 插件完整源码（3129 文件） |
| `.rework/dist/` | 9.7 MB | `dsh-vibe-math-2.8.10.tgz` 构建包 |
| `.rework/evidence/` | 71 MB | 插件交付复验证据（phase2-audit / phase2-review / pdf-audit / repro / snapshot） |
| `.rework/verification/` | 460 KB | 隔离环境验证（isolated-2.8.10） |
| `.rework/plugin-review/` | 312 KB | 插件复审日志 |
| `.rework/handoff/` | 276 KB | 阶段报告、插件代码补丁、论文补丁 |

此外只去掉了 `.DS_Store`、`__pycache__`、`*.pyc` 与 matplotlib 缓存。**完整原文仍在原工作区**
`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3/`。

## 6. 复现

- 环境与命令：`delivery/20261024-223751/README_REPRODUCE.md`（台账生成，含解释器版本、依赖版本、数据集/划分 hash、逐条命令）
- 项目级说明：`REPRODUCE.md`
- 代码顺序：`prepare_base.py → prepare_q1mapped.py → prepare_q3.py → q1_* → q2_* → q3_* → make_paper_figures.py → build_paper.py`
- 完整性：包内 `SHA256SUMS` 可逐文件校验；PDF 字节受 xdvipdfmx 影响不可逐字节复现，但 18/18 页与独立复审预览在 2× 光栅与文本层一致
