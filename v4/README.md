# v4 · 第三次完整解（2.8.6 干净重跑，`beer-2026-a-v2`）—— 唯一跑到 final 的一次

**这是四篇论文中的第四篇，也是唯一由台账判定为 final 的一套**：2026-10-24 13:31 建档、14:38:50 冻结（final closure），
论文 **45 页**，交付包均不带 `-DRAFT` 后缀。

- 论文题目：《混合尺度化合物谱下的啤酒感官分级预测、Top-3 关联解析与风格条件生成》
- 项目：`beer-2026-a-v2`（配置 sha `466a882b…`，seed=20261024，主指标 mae）
- 时间：2026-10-24 13:31:37 → 14:45（最后一次台账写入为 usage 结算）
- 台账：revision 1906，`stage=validation`，`frozen` 于 14:38:50；质量 38 项检查 **33 passed / 5 not_applicable / 0 failed**
- 体量：1379 文件 / 约 210 MB

> 与 v3 的关系：v3 是 beer 线的完整解（12 页，DRAFT）；v4 是其后按《2.8.6 重跑指南》**另起的新项目**，
> 同一道题、同一批附件，但数据契约、实验与验证全部重做，最终跑到 final。

---

## 1. 论文

**《混合尺度化合物谱下的啤酒感官分级预测、Top-3 关联解析与风格条件生成》**（45 页，1.7 MB PDF）

- 结构：摘要 + 八章（问题分析 / 数据质量与尺度核对 / Q1 / Q2 / Q3 / 稳健性与复现 / 结论与建议 / 复现说明）+ 3 个附录（AI 使用说明、台账引用与图形清单、逐维 Top-3）
- 文件：`report/paper.md`(101 KB) / `paper.tex` / `paper.pdf`(45 页) / `rendered.md` / `rendered.refs.json`
- 配套证据文档：`report/data-quality.md`(38 KB)、`q1-modeling.md`、`q2-factor-analysis.md`、`q3-generation.md`、`robustness.md`、`validation-notes.md`(90 KB)
- 12 张登记图（FIG-0001…0012，存放在 `experiments/*/figures/`）

一个必须知道的时间差：**论文渲染于 14:24，早于 14:38 的冻结**。因此正文 §6.4/§7.2 与摘要仍写着
“Q1 缺 independent-rerun ⇒ 交付只能是 DRAFT”；而实际上 14:38:32 的 VAL-0040 已通过（EXP-0031 复跑，delta=0），
项目随即冻结并打 final 包。**论文文本未重渲染**，对外使用前应先重新渲染，使措辞与 final 状态一致。

## 2. 关键结果

| 问题 | 结果（本套 45 页论文口径） |
|---|---|
| 数据 | 231 列混合尺度（196 log10 + 2 零值底限 + 33 原始浓度）；4.csv 为标准化值、原始 0–6 不可辨识；2.csv 为 Spearman 且非 PSD（min eig −0.0424）；2/5/6/7 同源派生 |
| Q1 | 常数基线留出 MAE **0.7509**（OOF 0.7341）→ 选中多输出 Ridge **0.6685**（OOF 0.6744）；选模只用 train-only OOF |
| Q2 | 逐维三方法 Top-3 Jaccard **0.2247**（全局基线 0.200）、bootstrap 平均入选频率 **0.4616**；限定为同期关联 |
| Q3 | 约束投影后满足率 **1.0**，未投影仅 **0.04**；能量距离 3.50 vs 3.49（几乎不变）→ 高满足率来自投影；真实样本全约束基率 0.024（6/250），三个留出风格 0.0 |
| 稳健性 | Q2 通过（ROB-0002，0.218 ≥ 0.15）、Q3 通过（ROB-0005，相对极差 0.2175%）、**Q1 未通过**（ROB-0004，相对极差约 180%，线性模型被极端离群点外推）——负结果如实保留 |

## 3. 目录

```text
problem/          题面 md + PDF + targetcolumns.csv
data/             raw（8 个附件 + imported/staged）；processed（6 个数据集 + profiles + 阈值 + 质量/离群审计）；splits/（SPLIT-0001…0017）；fieldlists/（6 份字段契约）
src/              18 个 Python：数据准备（00_prepare_*）、Q1/Q2/Q3 建模、validate_q2/q3、离群诊断
experiments/      EXP-0001…0035（27 succeeded / 6 queued / 2 failed），含 inputs/predictions/metrics/result/figures
validation/       35 个目录 / 41 条验证记录（split-integrity、leakage、holdout-metrics、baseline-compare、independent-rerun…）
report/           45 页论文三格式 + 6 份证据文档
delivery/         3 个交付包（2 个 final + 1 个 DRAFT）及对应 tar.gz、build_paper.py、header.tex
state/            ledger.json（rev 1906）、scripts/（7 个登记脚本）
contest.yaml / PREFLIGHT.json / START-PROMPT.md
```

三个交付包：

| 时间 | 包 | 类型 | 台账 rev |
|---|---|---|---|
| 14:27 | `delivery/20261024-142725-DRAFT/` + `.tar.gz` | DRAFT（含 quality-blockers） | 1691 |
| 14:38 | `delivery/20261024-143858/` + `.tar.gz` | **final** | 1885 |
| 14:42 | `delivery/20261024-144253/` + `.tar.gz` | **final（最新）** | 1896 |

## 4. 复现

- 环境与命令：见最新包的 `delivery/20261024-144253/README_REPRODUCE.md`（台账生成，含解释器版本、依赖版本、数据集/划分 hash、逐条命令）
- 代码顺序：`src/00_prepare_q1q2.py` → `00_prepare_q3.py` → `00_prepare_pools.py` → `q1_baseline.py` → `q1_candidate_ridge.py` → `q2_baseline.py` → `q2_topk.py` → `q3_baseline.py` → `q3_generate.py` → `validate_q2.py` / `validate_q3.py`
- 论文重建：`delivery/build_paper.py` + `delivery/header.tex`（pandoc + XeLaTeX）
- 完整性：包内 `SHA256SUMS` 可逐文件校验

## 5. 归档说明

- 本目录是 `work/my-new-contest-v2` 的**完整拷贝**（仅去掉 `.DS_Store`、`__pycache__`、`*.pyc` 与 matplotlib 缓存 `state/mplconfig`）
- 三个交付包的解包目录与 tar.gz 全部保留；`package-warnings.json` 中 36 条“中间产物未打包”属正常提示
- 遗留记录：6 个 queued 稳健性变体（已被后续 EXP-0015/16/17/24/29 等替代）、2 个早期 failed rerun（后由 EXP-0031/32/35 补跑成功）
