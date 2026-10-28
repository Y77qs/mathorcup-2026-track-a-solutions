# MathorCup 2026 A 题 · v6.2 支撑材料

本目录是参赛论文《基于稳健表示、共表达网络与风格条件生成的啤酒化合物—感官强度建模》
（`../论文正式版.pdf`）的完整支撑材料：可复现源码、清洗与划分数据、三问全部结果表，
以及论文生成脚本。所有路径均为**相对路径**，不依赖任何个人机器的绝对目录。

## 1. 目录结构

| 目录 | 内容 |
| --- | --- |
| `src/` | 三问全部可复现源码（数据准备、四模型嵌套交叉验证、Q2 共表达网络与 bootstrap、Q3 条件生成与迁移 QP、稳健性与复核脚本），另含 `build_paper.py`（Markdown→LaTeX 转换器） |
| `data/clean/` | 清洗后的三问输入表：`q1_mapped.csv`、`q2_raw.csv`、`q3.csv`、阈值与风格协议 |
| `data/splits/` | 冻结数据划分：`NESTED-CV-1`（问题一 3×3×3 嵌套交叉验证）、`SPLIT-0001`（问题二 200 行训练集）、`SPLIT-0002` |
| `data/processed/` | 特征字典与派生常量（单位/尺度校准、感官名称对齐、分级参数） |
| `outputs/q1/` | 问题一结果：250×50 连续评分与 0–6 相对等级、750 行折外预测、逐维/逐风格误差 |
| `outputs/q2/` | 问题二结果：`v62_clean/`（**去重后**的 Top-3、符号计数与稳定性摘要；Top-3 表同时含 `alternative_rank4` 与 `alternative_first_valid` 两列，取值相同、后者为规范名）、附件 2 描述性网络四件套、bootstrap 频率、点估计相关矩阵、旧哈希版本映射 |
| `outputs/q3/` | 问题三结果：生成谱 `samples*.csv`、感官画像 `sensory_profiles.csv`、迁移结果 `transfers.csv`、198 个 QP 证书、同锚点投影消融、`beer156` 敏感性诊断、分位数锚点全表、三张实体答案表 |
| `outputs/robustness/` | 四组稳健性检验的确认性汇总 |
| `build/` | 论文生成脚本、LaTeX 头/模板、最终论文 `.md`/`.tex` 源与源程序附录、PDF 版式核验结果、`build_all.sh` 一键重建 |
| `AI说明/` | 《AI 工具使用详情说明》的 `.tex`/`.md`/`.pdf` |

## 2. 环境

- Python 3.12，依赖见 `requirements.txt`（`numpy`、`pandas`、`scipy`、`scikit-learn`、`matplotlib`、`pypdf`）。
- 复现论文 PDF 另需 `pandoc` 3.x 与 `xelatex`（TeX Live 2025），以及系统字体
  `Times New Roman`、`Arial`、`Menlo`、`Songti SC`。

## 3. 直接复现（在本目录内，完全自包含）

```bash
python -m pip install -r requirements.txt
export PAPER_PROJECT_DIR="$PWD"
bash build/build_all.sh
```

`build_all.sh` 的四步含义：① 由 `outputs/q2/v62_clean/` 重建论文表 7 与附录长表；
② 由 `outputs/q3/v62_diagnostics/v62_diagnostics.json` 重建同锚点投影消融表；③ 由 `outputs/q3/v62_tables/`
重建三张实体答案表；④ 由 `build/paper_draft_base.md`（评审稿）+ 上述表片段生成
`build/paper_final.md`、`paper_final.tex`，经 `pandoc` + `xelatex` 编出 `论文正式版.pdf`，
最后运行 PDF 版式核验并输出 `build/out/pdf-audit.json`。

## 4. 归约到原始实验（可选）

两个**重导脚本**的输入是竞赛实验目录 `experiments/` 的已保存产物（该目录约 2.9 GB，未打包）；
在原始项目根目录下可运行：

```bash
python src/q2_v62_regen.py        # 问题二：重导去重后的交付表（不重跑 bootstrap）
python src/q3_v62_diagnostics.py  # 问题三：同锚点投影消融 + beer156 敏感性诊断
```

二者都已在本材料 `outputs/` 中留有**全部输出**；论文中的每个数字都可以直接从 `outputs/`
复核，无需重跑实验。三问主实验的运行命令见项目根目录 `REPRODUCE.md`。

## 5. 论文数字 → 文件对照

| 论文位置 | 数据文件 |
| --- | --- |
| 表 1–2（问题一四模型与分组误差） | `outputs/q1/model_comparison.csv`、`outputs/q1/error_analysis.csv` |
| 表 3（相对等级一致性） | `outputs/q1/grades_250.csv`、`outputs/q1/export_manifest.json` |
| 表 4–5（Beer#1–10 核心维度等级） | `outputs/q1/oof_predictions_750.csv`（评价侧，首轮重复） |
| 表 6（候选宇宙） | `outputs/q2/v62_clean/repeat0/strict_top3.csv`、`outputs/q2/v62_clean/v62_manifest.json` |
| 表 7、附录长表（Top-3 与同模块替代） | `outputs/q2/v62_clean/repeat0/strict_top3.csv`、`strict_top3_by_method.csv`、`extended_top3.csv` |
| 表 8–9（生成谱与分布质量） | `outputs/q3/samples.csv`、`energy_summary.csv`、`q3_metrics.csv` |
| 表 10（QP 证书） | `outputs/q3/solver_certificates.jsonl`、`transfer_metrics.json` |
| 表 11（迁移策略） | `outputs/q3/transfers.csv`、`transfer_metrics.json` |
| 表 12–17（迁移、缺陷、消融与三张实体表） | `outputs/q3/v62_tables/`（含 `anchor_direct_projection.csv`、`beer156_sensitivity.csv`、`transfer_anchor_values.csv`） |
| 表 18–20（稳健性与约束） | `outputs/robustness/`、`outputs/q2/v62_clean/sign_stability_summary.json` |
| 图 1–10 | `build/figures/confirmatory_v2/` |

## 5b. 源码 AI 辅助声明

`src/*.py` 每个文件头都带有统一的 AI 辅助声明（框架由 DeepSeek Harness 辅助生成；核心算法逻辑、约束修正与实验参数
由队员人工审阅、修改并独立核验）。声明只增加注释、不改变语义，因此副本的 sha256 与运行脚本不同；
原始哈希与副本哈希的对应关系见 `src/SOURCE_HASHES.json`，说明见 `src/AI-ASSISTANCE-NOTICE.md`。

## 6. 校验

`SHA256SUMS` 覆盖本目录除自身外的全部文件：

```bash
shasum -a 256 -c SHA256SUMS
```

## 7. 口径声明

- 问题一没有独立外部测试集：全部误差为 3×3×3 嵌套交叉验证的外折结果。
- 问题二的方向一致率按 150 / 600 / 1800 三个分母分列，引用时必须写明分母；同模块替代候选已剔除同维 Top-3。
- 问题三的生成未优于同量源样本重采样参照；迁移只是声明模型下的最优，没有迁移后真实标签。
- 缺陷约束是“不高于源样本”的数学筛查，不是感官阈值合格证明。
