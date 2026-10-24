# v1 · A 项目（projectId: `mathorcup-2026-a`）—— 第一套完整解（2026-10-23）

**第一套完整解**：2026-10-23 21:04 → 22:27（CST），长报告式论文 **47 页**（初版 44 页）。本目录即归档中的 `v1/`。
本包是自包含的：论文、代码、数据、实验元数据、台账、交付包齐全，可离线复现论文中的数字。

---

## 1. 论文

**题目**：《数据缺失与尺度失配条件下啤酒感官评分、关键化合物识别与风格条件生成的建模研究》

| 文件 | 说明 |
|---|---|
| `paper/paper.pdf` | **47 页**定稿（2026-10-23 22:19；`report/build.log` 记录 pages=47、overfull hbox 0） |
| `paper/paper.md` | 正文源（106,764 B，含 113 个台账占位符） |
| `paper/paper.tex` | pandoc 生成（152,989 B） |
| `paper/rendered.md` | 占位符渲染后的正文 |
| `paper/rendered.refs.json` | 占位符 ↔ 台账引用映射 |
| `paper/build.sh`、`paper/tex/` | XeLaTeX 构建脚本、pandoc 模板、`typeset.py` |
| `paper/versions/2026-10-23-2201-44pages.pdf` | 首版（44 页，22:01 打进第一个 DRAFT 包） |

论文结构：摘要 → 问题重述 → 问题分析 → 数据核实与预处理 → 假设与符号 → 问题一模型 → 问题二模型 → 问题三模型 → 结果与边界 → 附录。

## 2. 目录

```text
paper/          论文三格式 + 渲染物 + 构建工程 + 历史版本 PDF
src/            39 个 Python（13,169 行）：数据 -> Q1 -> Q2 -> Q3 -> 独立复算
figures/        20 张 PNG（其中 15 张登记为 FIG）
data/           raw（附件 + imported 副本）/ clean / processed / splits
problem/        题面 PDF + statement.md/txt + questions.yaml + pages
experiments/    EXP-0001..0048 元数据（experiment/metrics/result/outputs/run + predictions + 日志）
validation/     VAL-0001.. 验证记录（spec/result/log）
outputs/        protocol/ audit/ data/ probe/ review/（汇总 JSON 与审查报告）
ledger.json     台账（唯一真相，rev 527，2.9 MB）
scripts/        SCRIPT-0001..0038（脚本登记副本，用于溯源）
docs/STATUS.md  交付状态书：已完成 / 未完成 / 为什么、最终快照
delivery/FINAL-DRAFT-2-DRAFT.tar.gz  最终交付快照（193 文件，sha256 2317a21b…）
REPRODUCE.md    一键复现说明
contest.yaml    竞赛协议配置
```

## 3. 代码地图（按问题）

| 阶段 | 文件 |
|---|---|
| 审计/尺度/清洗/划分/建模表 | `01_audit.py`、`02_scale.py`、`03_clean.py`、`04_split.py`、`05_dim_map.py`、`06_calibration.py`、`07_model_table.py`、`common.py`、`emit.py` |
| 问题一（50 维感官分级） | `q1_models.py`、`q1_data.py`、`q1_final.py`、`q1_bundle.py`、`q1_figs.py`、`q1_abl.py`、`q1_robust_report.py`、`q1_final_summary.py`、`08_baseline_constant.py`、`08b_baseline_ridge.py`、`08c_q1_final.py`、`08d_figures.py` |
| 问题二（共表达图 + Top-3） | `q2_prereg.py`、`q2_graph.py`、`q2_common.py`、`q2_baseline.py`、`q2_select.py`、`q2_figs.py`、`q2_stability.py` |
| 问题三（风格条件生成 + 迁移） | `q3_utils.py`、`q3_models.py`、`q3_generate.py`、`q3_transfer.py`、`q3_exp_family.py`、`q3_baseline.py`、`q3_eval.py`、`q3_figs.py` |
| 独立复算 | `09_independent_rerun.py` |
| 环境/契约探针 | `probe_env.py`、`probe_contract.py` |

## 4. 复现

```bash
# 依赖：Python 3.12 + numpy 2.3.5 / pandas 2.2.3 / scipy 1.18.1 / scikit-learn 1.9.1 / matplotlib 3.11.2 / openpyxl 3.1.5
# 论文：pandoc + XeLaTeX（ctexart，CJK 字体 Songti SC / Heiti SC）
python src/01_audit.py
python src/02_scale.py
python src/03_clean.py
python src/04_split.py
python src/05_dim_map.py
python src/06_calibration.py
python src/07_model_table.py
python src/08_baseline_constant.py
python src/08c_q1_final.py
python src/q2_graph.py
python src/q2_baseline.py
python src/q3_baseline.py
python src/q3_models.py
python src/q3_generate.py
python src/q3_eval.py
python src/q3_transfer.py
python src/q3_figs.py
python src/08d_figures.py
bash paper/build.sh        # md -> tex -> pdf
```

> **务必阅读 `REPRODUCE.md` 第 4b 节**：协议字面的"折内中位数插补 + 标准化"会在混合尺度数据上产生大负 R²；
> 必须使用 1%/99% winsorize（或线性列 log10 协调）才有论文中的结果。
> 正式登记实验需走 `modeling_experiment run`，`src/emit.py` 是 runner 内外统一的指标桥接层。

## 5. 论文的核心结论与边界（摘要）

- 数据：题面 12 处与附件不符；`1.csv` 为混合尺度（37 列 log10 / 33 列线性 / 161 列未验证）；
  755 格为 LOD/2 左删失；`4.csv` 是标准化值、**原始 0–6 不可辨识**，故交付四套显式“映射分级”口径（P1–P4）。
- Q1：折内拟合的带防护预处理 + 8 个候选族选型；分级表覆盖 0–6 全档，但**不是真实人工评分**。
- Q2：Spearman 共表达图 + 四方法 Borda 聚合 Top-3，稳定性以 bootstrap / 跨方法 Jaccard 判定；
  `6.csv` 只作同数据一致性检查，不作独立先验。
- Q3：三族条件生成模型 + 缺陷化合物硬约束迁移；结论仅表示生成合理性与约束满足，**不是酿造验证**。

**未完成项（如实披露，详见 `docs/STATUS.md`）**：Q2 未登记为候选 EXP；Q3 independent-rerun FAILED；
稳健性计划未执行；holdout 复用超限。因此项目状态为 `DRAFT`（`final=false`），未提交平台。

## 6. 本包省略的内容

`outputs/q1`（271 MB）、`outputs/q3`（122 MB）、`outputs/q2`（8 MB）中大体积的逐维度/逐样本中间产物未纳入；
论文引用的汇总 JSON 已保留在 `outputs/`。其余交付压缩包只保留最终一个（`FINAL-DRAFT-2-DRAFT.tar.gz`）。
