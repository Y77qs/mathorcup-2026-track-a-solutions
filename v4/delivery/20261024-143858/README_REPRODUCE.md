# 复现说明 — beer-2026-a-v2（交付目录 delivery/20261024-143858）

> 本文件由 `modeling_deliver {action:"package"}` 从项目台账生成：
> 台账 revision 1885，contest.yaml sha256 466a882bcee6a3dc4cd956131d1aa82db168e284bf2296bd2fb5f2fd42b0e399，生成时间 2026-10-24T06:38:58.296Z，
> 交付模板 generic-zh。下面是**命令**，不是“应该能跑”的断言。

## 一、环境（唯一的外部前提）

- 解释器（绝对路径）：`/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python`
- Python 版本：3.12.14
- 平台：macOS-27.0-arm64-arm-64bit
- contest.yaml 声明的附加依赖：（contest.yaml 未声明 runtime.pythonPackages）

依赖版本（来自项目初始化时的真实能力探测）：

| 依赖 | 版本 |
|---|---|
| numpy | 2.3.5 |
| pandas | 2.2.3 |
| scipy | 1.18.1 |
| openpyxl | 3.1.5 |
| matplotlib | 3.11.2 |
| sympy | 1.14.0 |
| sklearn | 1.9.1 |

> 换解释器或依赖版本后，指标可能有微小差异。复现容差以 `contest.yaml` 的
> `evaluation.reproductionTolerance` 为准，比较时用它，而不是“看起来差不多”。

## 二、包内目录

```text
delivery/20261024-143858/
  report/              report/paper.md（源）、report/rendered.md（交付渲染产物）、report/rendered.refs.json（来源记录）
  figures/             已登记图形 + figures.json（图 id、原路径、sha256、图注、来源实验）
  src/                 建模代码
  data/processed/      已登记的数据集（清洗后）
  data/splits/         训练/测试/assignment 文件
  experiments/         每个成功实验的 metrics.json / predictions.csv / result.json（代码不在 src/ 时也放这里）
  contest.yaml         交付时生效的配置（协议与容差的唯一来源）
  ledger-summary.json  台账摘要：结论、验证、图形、复跑关系、解释器与依赖版本
  README_REPRODUCE.md  本文件
  SHA256SUMS           包内每个文件的 sha256
```

## 三、解压与完整性核对

```bash
tar -xzf delivery/20261024-143858.tar.gz
cd delivery/20261024-143858
shasum -a 256 -c SHA256SUMS
```

数据集与它们的 hash：

| 数据集 | 文件 | sha256(前16) | 目标列 |
|---|---|---|---|
| DATA-0001 | data/processed/q1_mapped.csv | 64651e40fbda83fc | A_malt_all |
| DATA-0002 | data/processed/q2_raw.csv | cca702e9fb85d001 | A_malt_all |
| DATA-0003 | data/processed/q3_table.csv | a89872324f27ede6 | style |
| DATA-0004 | data/processed/q1_pool.csv | 52129428f0348591 | A_malt_all |
| DATA-0005 | data/processed/q2_pool.csv | d00925b8264d5a36 | A_malt_all |
| DATA-0006 | data/processed/q3_pool.csv | 06d8ee5f4c4a22e8 | style |

划分方式与划分文件的 hash：

| 划分 | 数据集 | 方法 | train sha256 | test sha256 | assignment 文件 |
|---|---|---|---|---|---|
| SPLIT-0001 | DATA-0001 | random-holdout | 52129428f034 | 3ec46c406df7 | data/splits/SPLIT-0001/assignment.csv |
| SPLIT-0002 | DATA-0002 | random-holdout | d00925b8264d | 998cb973d907 | data/splits/SPLIT-0002/assignment.csv |
| SPLIT-0003 | DATA-0003 | random-holdout | 06d8ee5f4c4a | 9588112f41cc | data/splits/SPLIT-0003/assignment.csv |
| SPLIT-0004 | DATA-0001 | random-holdout | ba5592cf19ff | 9cd2c1d4d3c1 | data/splits/SPLIT-0004/assignment.csv |
| SPLIT-0005 | DATA-0001 | random-holdout | f94fb32ed556 | db07c148d6b5 | data/splits/SPLIT-0005/assignment.csv |
| SPLIT-0006 | DATA-0002 | random-holdout | b98b1e29488d | c4836b6da5c2 | data/splits/SPLIT-0006/assignment.csv |
| SPLIT-0007 | DATA-0003 | random-holdout | 37e9dfc8fa4f | c3122c07e756 | data/splits/SPLIT-0007/assignment.csv |
| SPLIT-0008 | DATA-0004 | random-holdout | 50025d425f24 | bb1392f171d1 | data/splits/SPLIT-0008/assignment.csv |
| SPLIT-0009 | DATA-0004 | random-holdout | 3719c8e7907e | d83b49ba03ef | data/splits/SPLIT-0009/assignment.csv |
| SPLIT-0010 | DATA-0005 | random-holdout | 97ad06185685 | f95b295c971e | data/splits/SPLIT-0010/assignment.csv |
| SPLIT-0011 | DATA-0005 | random-holdout | f33f9a789777 | 0b9f558985fe | data/splits/SPLIT-0011/assignment.csv |
| SPLIT-0012 | DATA-0006 | random-holdout | dbe765baf0e0 | 86b6f3c46f87 | data/splits/SPLIT-0012/assignment.csv |
| SPLIT-0013 | DATA-0006 | random-holdout | 88fd10c43d50 | dca550264977 | data/splits/SPLIT-0013/assignment.csv |
| SPLIT-0014 | DATA-0004 | random-holdout | c1b14a2ddc83 | 526f2f598d85 | data/splits/SPLIT-0014/assignment.csv |
| SPLIT-0015 | DATA-0004 | random-holdout | 19770d46b5c8 | 47a7c9303624 | data/splits/SPLIT-0015/assignment.csv |
| SPLIT-0016 | DATA-0004 | random-holdout | 3e2194f9c4e9 | 51c2994de02b | data/splits/SPLIT-0016/assignment.csv |
| SPLIT-0017 | DATA-0006 | random-holdout | ac9a7a0fa08c | f6da1e3b4e4d | data/splits/SPLIT-0017/assignment.csv |

> 原始附件不在包内；按下面的 sha256 从原始来源重新获取，再走同一清洗脚本：

| 原始文件 | 来源名 | 项目内路径 | sha256(前16) | 角色 |
|---|---|---|---|---|
| RAW-41984922 | 419849227a02e0c7-1.csv | data/raw/imported/419849227a02e0c7-1.csv | 419849227a02e0c7 | chemical_features |
| RAW-415709ac | 415709ac10f2f730-2.csv | data/raw/imported/415709ac10f2f730-2.csv | 415709ac10f2f730 | compound_correlation |
| RAW-fe4dcabd | fe4dcabd48431e6d-3.xlsx | data/raw/imported/fe4dcabd48431e6d-3.xlsx | fe4dcabd48431e6d | sensory_scorecards |
| RAW-43a7b386 | 43a7b38682ed81ce-4.csv | data/raw/imported/43a7b38682ed81ce-4.csv | 43a7b38682ed81ce | sensory_targets |
| RAW-c512eed1 | c512eed108de6f98-5.csv | data/raw/imported/c512eed108de6f98-5.csv | c512eed108de6f98 | sensory_correlation |
| RAW-a55004fb | a55004fb0390299a-6.csv | data/raw/imported/a55004fb0390299a-6.csv | a55004fb0390299a | chemical_sensory_correlation |
| RAW-2083138d | 2083138df46640e2-7.csv | data/raw/imported/2083138df46640e2-7.csv | 2083138df46640e2 | sensory_descriptors |
| RAW-f2316766 | f2316766792111d9-8.xlsx | data/raw/imported/f2316766792111d9-8.xlsx | f2316766792111d9 | reference_thresholds |
| RAW-40813e27 | 40813e273e081ae0-数据说明.txt | data/raw/imported/40813e273e081ae0-数据说明.txt | 40813e273e081ae0 | data_notes |

## 四、复跑实验

在包根目录执行下表命令。若脚本依赖“实验目录内的相对路径”，先 `cd` 到该实验目录再执行同一行命令。

> **依赖 `modeling_contract` 的脚本**：该模块随整合包发布（`<已安装 preset>/packs/modeling-contest/python/`），
> 不在项目目录里。手动复跑时先把它加入 `PYTHONPATH`，例如：
> `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/path/to/preset/packs/modeling-contest/python python src/model.py`
> （`PYTHONDONTWRITEBYTECODE=1` 避免把 `__pycache__` 写进 preset 安装目录——那会让包名册/审计把构建产物当成未登记文件）。
> 通过 `modeling_experiment {action:"run"}` 复跑时 runner 会自动设置，无需手工处理。
> 若脚本只读取环境变量（`MODELING_TRAIN_FILE` 等），请按 `contest.yaml` 的划分文件自行导出。

| 实验 | 小题 | 模型 | 状态 | mae | 复跑命令（在包根执行） |
|---|---|---|---|---|---|
| EXP-0001 | Q1 | MODEL-0001 | succeeded | 0.7509114931486188 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0001/inputs/src/q1_baseline.py` |
| EXP-0002 | Q1 | MODEL-0002 | succeeded | 0.6685467308887166 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0002/inputs/src/q1_candidate_ridge.py` |
| EXP-0003 | Q1 | MODEL-0003 | succeeded | 0.6571399342026767 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0003/inputs/src/q1_candidate_hgb.py` |
| EXP-0004 | Q2 | MODEL-0004 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0004/inputs/src/q2_baseline.py` |
| EXP-0005 | Q2 | MODEL-0005 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0005/inputs/src/q2_topk.py` |
| EXP-0006 | Q3 | MODEL-0006 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0006/inputs/src/q3_baseline.py` |
| EXP-0007 | Q3 | MODEL-0007 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0007/inputs/src/q3_generate.py` |
| EXP-0010 | Q2 | MODEL-0010 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0010/inputs/src/q2_topk.py` |
| EXP-0013 | Q3 | MODEL-0012 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0013/inputs/src/q3_generate.py` |
| EXP-0014 | Q3 | MODEL-0013 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0014/inputs/src/q3_generate.py` |
| EXP-0015 | Q1 | MODEL-0014 | succeeded | 0.8446668450194856 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0015/inputs/src/q1_candidate_ridge.py` |
| EXP-0016 | Q1 | MODEL-0015 | succeeded | 0.6055966442672139 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0016/inputs/src/q1_candidate_ridge.py` |
| EXP-0017 | Q2 | MODEL-0016 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0017/inputs/src/q2_topk.py` |
| EXP-0018 | Q1 | MODEL-0017 | succeeded | 0.7713941642358138 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0018/inputs/src/q1_candidate_ridge.py` |
| EXP-0019 | Q2 | MODEL-0005 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0005/inputs/src/q2_topk.py` |
| EXP-0021 | Q3 | MODEL-0007 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0007/inputs/src/q3_generate.py` |
| EXP-0023 | Q2 | MODEL-0020 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0023/inputs/src/q2_baseline.py` |
| EXP-0024 | Q1 | MODEL-0021 | succeeded | 0.7566911281178076 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0024/inputs/src/q1_baseline.py` |
| EXP-0025 | Q1 | MODEL-0022 | succeeded | 0.758591595965814 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0025/inputs/src/q1_candidate_ridge.py` |
| EXP-0026 | Q1 | MODEL-0023 | succeeded | 1.962372612515533 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0026/inputs/src/q1_candidate_ridge.py` |
| EXP-0027 | Q3 | MODEL-0024 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0027/inputs/src/q3_generate.py` |
| EXP-0029 | Q3 | MODEL-0026 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0029/inputs/src/q3_generate.py` |
| EXP-0031 | Q1 | MODEL-0002 | succeeded | 0.6685467308887166 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0002/inputs/src/q1_candidate_ridge.py` |
| EXP-0032 | Q1 | MODEL-0002 | succeeded | 0.6685467308887166 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0002/inputs/src/q1_candidate_ridge.py` |
| EXP-0033 | Q2 | MODEL-0005 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0005/inputs/src/q2_topk.py` |
| EXP-0034 | Q3 | MODEL-0007 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0007/inputs/src/q3_generate.py` |
| EXP-0035 | Q1 | MODEL-0002 | succeeded | 0.6685467308887166 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0002/inputs/src/q1_candidate_ridge.py` |

> 复跑关系（哪个实验是谁的 `rerunOf`）见 `ledger-summary.json` 的 `experiments[]`。
> 新跑出来的数是**新实验**的数，不是旧实验的数；不要在包内覆盖旧结果。

## 五、复核结论与验证

| 校验 | 实验 | 类型 | 结果 | 新鲜度 |
|---|---|---|---|---|
| VAL-0001 | EXP-0002 | split-integrity | passed | fresh |
| VAL-0002 | EXP-0002 | leakage | passed | fresh |
| VAL-0003 | EXP-0002 | holdout-metrics | passed | fresh |
| VAL-0004 | EXP-0002 | baseline-compare | passed | fresh |
| VAL-0005 | EXP-0005 | split-integrity | passed | fresh |
| VAL-0006 | EXP-0005 | leakage | passed | fresh |
| VAL-0007 | EXP-0005 | holdout-metrics | passed | fresh |
| VAL-0008 | EXP-0007 | split-integrity | passed | STALE |
| VAL-0009 | EXP-0007 | leakage | passed | STALE |
| VAL-0010 | EXP-0007 | holdout-metrics | passed | STALE |
| VAL-0011 | EXP-0005 | independent-rerun | passed | fresh |
| VAL-0012 | EXP-0007 | independent-rerun | passed | fresh |
| VAL-0013 | EXP-0007 | split-integrity | passed | fresh |
| VAL-0014 | EXP-0007 | leakage | passed | fresh |
| VAL-0015 | EXP-0007 | holdout-metrics | passed | fresh |
| VAL-0016 | EXP-0002 | split-integrity | passed | fresh |
| VAL-0017 | EXP-0002 | leakage | passed | fresh |
| VAL-0018 | EXP-0002 | split-integrity | passed | fresh |
| VAL-0019 | EXP-0002 | leakage | passed | fresh |
| VAL-0020 | EXP-0002 | independent-rerun | passed | fresh |
| VAL-0021 | EXP-0002 | baseline-compare | passed | fresh |
| VAL-0022 | EXP-0002 | split-integrity | passed | fresh |
| VAL-0023 | EXP-0002 | leakage | passed | fresh |
| VAL-0024 | EXP-0002 | holdout-metrics | passed | fresh |
| VAL-0025 | EXP-0002 | independent-rerun | passed | fresh |
| VAL-0026 | EXP-0002 | baseline-compare | passed | fresh |
| VAL-0027 | EXP-0005 | split-integrity | passed | fresh |
| VAL-0028 | EXP-0005 | leakage | passed | fresh |
| VAL-0029 | EXP-0005 | independent-rerun | passed | fresh |
| VAL-0030 | EXP-0005 | holdout-metrics | passed | fresh |
| VAL-0031 | EXP-0007 | split-integrity | passed | fresh |
| VAL-0032 | EXP-0007 | leakage | passed | fresh |
| VAL-0033 | EXP-0007 | independent-rerun | passed | fresh |
| VAL-0034 | EXP-0007 | holdout-metrics | passed | fresh |
| VAL-0035 | EXP-0002 | split-integrity | passed | fresh |
| VAL-0036 | EXP-0002 | leakage | passed | fresh |
| VAL-0037 | EXP-0002 | independent-rerun | passed | fresh |
| VAL-0038 | EXP-0002 | split-integrity | passed | fresh |
| VAL-0039 | EXP-0002 | leakage | passed | fresh |
| VAL-0040 | EXP-0002 | independent-rerun | passed | fresh |
| VAL-0041 | EXP-0002 | baseline-compare | passed | fresh |

| 论断 | 小题 | 状态 | 陈述(截断) |
|---|---|---|---|
| CLAIM-0001 | Q1 | active | 在 DATA-0001（250 款啤酒 × 50 个感官维度的 mapped grade）上，按预注册的 seed=20 |
| CLAIM-0002 | Q2 | active | 对 4.csv 的 50 个感官维度，三种相互独立的逐维排序方法（训练行上的 |Spearman|、岭回归系数、随机森林 |
| CLAIM-0003 | Q3 | active | 在 DATA-0003 上，风格条件高斯生成器（仅用 style_holdout=train_style 的 201 行 |
| CLAIM-0004 | Q1 | active | Q1 的稳健性去混杂检验（ROB-0004：正则强度倍数固定 1.0、只变池划分）**未通过**预注册判据：EXP-00 |

| 图 | 标题 | 文件 | sha256(前16) |
|---|---|---|---|
| FIG-0001 | 问题一：选中模型（多输出岭回归，alpha 由训练行内 5 折 CV 选）在 50 个 mapped grade 目标上的留出 MAE，按误差排序；纵轴为 mapped grade 单位（非原始 0–6），标题给出 50 目标均匀平均。 | experiments/EXP-0002/figures/q1_ridge_per_target_mae.png | dfe3afee3a10b44e |
| FIG-0002 | 问题一：选中模型（岭回归）的预测值与真值散点（50 个目标 × 50 个留出行），黑线为 y = x；两轴均为 mapped grade 单位。 | experiments/EXP-0002/figures/q1_ridge_scatter.png | 70a023f868b1d0eb |
| FIG-0003 | 问题一：选中模型（岭回归）的残差分布（50 个目标池化），残差 = 预测 − 真值，单位 mapped grade；用于检查误差是否对称、是否被少数越界测试单元格拉偏。 | experiments/EXP-0002/figures/q1_ridge_residuals.png | 6d8e1bfde7f691c6 |
| FIG-0004 | 问题一：常数基线（逐目标训练中位数，不使用任何化合物特征）的逐目标留出 MAE，与选中模型同数据、同划分、同指标口径对照；纵轴为 mapped grade 单位。 | experiments/EXP-0001/figures/q1_baseline_per_target_mae.png | 3616c81c974256a7 |
| FIG-0005 | 问题二：每个感官维度 × 被选关键化合物的关联强度热图；颜色为 |Spearman ρ|（训练行），空白表示三种排序方法都未把该化合物选入该维度的 Top-3。 | experiments/EXP-0005/figures/q2_top3_selection_heatmap.png | 30d68db3765ab8a7 |
| FIG-0006 | 问题二：500 次训练行内 bootstrap 重采样下 Top-3 入选频率（spearman-abs 与 ridge-coef 两种估计器平均）；频率越接近 1 表示该名次越不依赖样本偶然性。 | experiments/EXP-0005/figures/q2_bootstrap_inclusion.png | cbbd115a0819948c |
| FIG-0007 | 问题二：三种排序方法两两的逐维 Top-3 Jaccard 矩阵（每个格子是 50 个维度的平均 Jaccard）；用于判断不同方法是否指向同一批关键化合物。 | experiments/EXP-0005/figures/q2_method_jaccard.png | c3f6be1f05d38627 |
| FIG-0008 | 问题二：2.csv 共表达结构。左：2.csv 块在 PSD 投影前后的特征值谱（红=附件原样，蓝=投影后），标题给出全矩阵与块的最小特征值；右：PSD 投影后的相关块热图，仅含进入任一 Top-3 集合的化合物。2.csv 只作结构参考，不是独立外部先验。 | experiments/EXP-0005/figures/q2_coexpression.png | cfcd448c3085652b |
| FIG-0009 | 问题三：各风格感官画像（风格条件生成 vs 训练行真实分布）。画像由 Q1 训练行拟合的代理模型近似，不是实测评分，只用于相对比较。 | experiments/EXP-0007/figures/q3_sensory_profiles.png | fb2fa0c0242bd1b5 |
| FIG-0010 | 问题三：生成谱与真实留出谱的逐化合物均值对比（标准化空间），标题给出画像 Spearman；用于判断生成是否只学到中心、没学到离散度。 | experiments/EXP-0007/figures/q3_generated_vs_real.png | 82879de445a73795 |
| FIG-0011 | 问题三：跨风格迁移（Pils/Lager → Tripel）前后 7 项缺陷化合物的超阈比例逐项对比（蓝=Pils/Lager 迁移前，红=全化合物平移，绿=缺陷化合物不平移）；迁移前后均未整体达标这一负结果如实呈现。 | experiments/EXP-0007/figures/q3_transfer_defects.png | 0c698b18b9b8ce4e |
| FIG-0012 | 问题三：约束满足率对照。四根柱依次为风格条件生成（未投影）、风格条件生成（约束投影）、250 个真实样本、49 个留出风格真实样本；约束满足是用后处理投影达成的，不构成独立质量证据，因此必须同时报告未投影版本与真实基率。 | experiments/EXP-0007/figures/q3_constraint_satisfaction.png | 75a51634098f07c2 |

> 论文里的每个数字都由占位符从台账渲染而来，逐条解析记录在 `report/rendered.refs.json`；
> 每条结论的证据引用在 `ledger-summary.json` 的 `claims[]` 里。

## 六、交付检查读数

passed 63 / failed 0 / skipped 5

已知限制与警告：

- experiment EXP-0001: 8 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0001/figures.json, experiments/EXP-0001/outputs.json, experiments/EXP-0001/predictions_long.csv, experiments/EXP-0001/seed-receipt.json, experiments/EXP-0001/figures/q1_baseline_residuals.png, experiments/EXP-0001/figures/q1_baseline_scatter.png, experiments/EXP-0001/inputs/src/q1_baseline.py, experiments/EXP-0001/inputs/src/q_common.py
- experiment EXP-0002: 6 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0002/figures.json, experiments/EXP-0002/outputs.json, experiments/EXP-0002/predictions_long.csv, experiments/EXP-0002/seed-receipt.json, experiments/EXP-0002/inputs/src/q1_candidate_ridge.py, experiments/EXP-0002/inputs/src/q_common.py
- experiment EXP-0003: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0003/figures.json, experiments/EXP-0003/outputs.json, experiments/EXP-0003/predictions_long.csv, experiments/EXP-0003/seed-receipt.json, experiments/EXP-0003/figures/q1_hgb_per_target_mae.png, experiments/EXP-0003/figures/q1_hgb_residuals.png, experiments/EXP-0003/figures/q1_hgb_scatter.png, experiments/EXP-0003/inputs/src/q1_candidate_hgb.py, experiments/EXP-0003/inputs/src/q_common.py
- experiment EXP-0004: 10 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0004/figures.json, experiments/EXP-0004/outputs.json, experiments/EXP-0004/seed-receipt.json, experiments/EXP-0004/sets.json, experiments/EXP-0004/sets_nested.json, experiments/EXP-0004/figures/q2_baseline_global_importance.png, experiments/EXP-0004/figures/q2_baseline_jaccard.png, experiments/EXP-0004/inputs/src/q2_baseline.py, experiments/EXP-0004/inputs/src/q2_lib.py, experiments/EXP-0004/inputs/src/q_common.py
- experiment EXP-0005: 10 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0005/figures.json, experiments/EXP-0005/outputs.json, experiments/EXP-0005/seed-receipt.json, experiments/EXP-0005/sets.json, experiments/EXP-0005/sets_nested.json, experiments/EXP-0005/inputs/data/raw/2.csv, experiments/EXP-0005/inputs/data/raw/8.xlsx, experiments/EXP-0005/inputs/src/q2_lib.py, experiments/EXP-0005/inputs/src/q2_topk.py, experiments/EXP-0005/inputs/src/q_common.py
- experiment EXP-0006: 11 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0006/figures.json, experiments/EXP-0006/generated_profiles.csv, experiments/EXP-0006/outputs.json, experiments/EXP-0006/seed-receipt.json, experiments/EXP-0006/figures/q3_baseline_constraint_satisfaction.png, experiments/EXP-0006/figures/q3_baseline_defect_rates.png, experiments/EXP-0006/figures/q3_baseline_profile_scatter.png, experiments/EXP-0006/inputs/data/processed/data_quality.json, experiments/EXP-0006/inputs/src/q3_baseline.py, experiments/EXP-0006/inputs/src/q3_lib.py, experiments/EXP-0006/inputs/src/q_common.py
- experiment EXP-0007: 12 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0007/figures.json, experiments/EXP-0007/generated_profiles.csv, experiments/EXP-0007/generated_profiles_unconstrained.csv, experiments/EXP-0007/outputs.json, experiments/EXP-0007/seed-receipt.json, experiments/EXP-0007/transfer_profiles.csv, experiments/EXP-0007/inputs/data/processed/data_quality.json, experiments/EXP-0007/inputs/data/processed/q1_mapped.csv, experiments/EXP-0007/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0007/inputs/src/q3_generate.py, experiments/EXP-0007/inputs/src/q3_lib.py, experiments/EXP-0007/inputs/src/q_common.py
- experiment EXP-0008 is queued and is not in the package
- experiment EXP-0009 is queued and is not in the package
- experiment EXP-0010: 14 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0010/figures.json, experiments/EXP-0010/outputs.json, experiments/EXP-0010/seed-receipt.json, experiments/EXP-0010/sets.json, experiments/EXP-0010/sets_nested.json, experiments/EXP-0010/figures/q2_bootstrap_inclusion.png, experiments/EXP-0010/figures/q2_coexpression.png, experiments/EXP-0010/figures/q2_method_jaccard.png, experiments/EXP-0010/figures/q2_top3_selection_heatmap.png, experiments/EXP-0010/inputs/data/raw/2.csv, experiments/EXP-0010/inputs/data/raw/8.xlsx, experiments/EXP-0010/inputs/src/q2_lib.py, experiments/EXP-0010/inputs/src/q2_topk.py, experiments/EXP-0010/inputs/src/q_common.py
- experiment EXP-0011 is queued and is not in the package
- experiment EXP-0012 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0013: 16 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0013/figures.json, experiments/EXP-0013/generated_profiles.csv, experiments/EXP-0013/generated_profiles_unconstrained.csv, experiments/EXP-0013/outputs.json, experiments/EXP-0013/seed-receipt.json, experiments/EXP-0013/transfer_profiles.csv, experiments/EXP-0013/figures/q3_constraint_satisfaction.png, experiments/EXP-0013/figures/q3_generated_vs_real.png, experiments/EXP-0013/figures/q3_sensory_profiles.png, experiments/EXP-0013/figures/q3_transfer_defects.png, experiments/EXP-0013/inputs/data/processed/data_quality.json, experiments/EXP-0013/inputs/data/processed/q1_mapped.csv, experiments/EXP-0013/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0013/inputs/src/q3_generate.py, experiments/EXP-0013/inputs/src/q3_lib.py, experiments/EXP-0013/inputs/src/q_common.py
- experiment EXP-0014: 16 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0014/figures.json, experiments/EXP-0014/generated_profiles.csv, experiments/EXP-0014/generated_profiles_unconstrained.csv, experiments/EXP-0014/outputs.json, experiments/EXP-0014/seed-receipt.json, experiments/EXP-0014/transfer_profiles.csv, experiments/EXP-0014/figures/q3_constraint_satisfaction.png, experiments/EXP-0014/figures/q3_generated_vs_real.png, experiments/EXP-0014/figures/q3_sensory_profiles.png, experiments/EXP-0014/figures/q3_transfer_defects.png, experiments/EXP-0014/inputs/data/processed/data_quality.json, experiments/EXP-0014/inputs/data/processed/q1_mapped.csv, experiments/EXP-0014/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0014/inputs/src/q3_generate.py, experiments/EXP-0014/inputs/src/q3_lib.py, experiments/EXP-0014/inputs/src/q_common.py
- experiment EXP-0015: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0015/figures.json, experiments/EXP-0015/outputs.json, experiments/EXP-0015/predictions_long.csv, experiments/EXP-0015/seed-receipt.json, experiments/EXP-0015/figures/q1_ridge_per_target_mae.png, experiments/EXP-0015/figures/q1_ridge_residuals.png, experiments/EXP-0015/figures/q1_ridge_scatter.png, experiments/EXP-0015/inputs/src/q1_candidate_ridge.py, experiments/EXP-0015/inputs/src/q_common.py
- experiment EXP-0016: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0016/figures.json, experiments/EXP-0016/outputs.json, experiments/EXP-0016/predictions_long.csv, experiments/EXP-0016/seed-receipt.json, experiments/EXP-0016/figures/q1_ridge_per_target_mae.png, experiments/EXP-0016/figures/q1_ridge_residuals.png, experiments/EXP-0016/figures/q1_ridge_scatter.png, experiments/EXP-0016/inputs/src/q1_candidate_ridge.py, experiments/EXP-0016/inputs/src/q_common.py
- experiment EXP-0017: 14 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0017/figures.json, experiments/EXP-0017/outputs.json, experiments/EXP-0017/seed-receipt.json, experiments/EXP-0017/sets.json, experiments/EXP-0017/sets_nested.json, experiments/EXP-0017/figures/q2_bootstrap_inclusion.png, experiments/EXP-0017/figures/q2_coexpression.png, experiments/EXP-0017/figures/q2_method_jaccard.png, experiments/EXP-0017/figures/q2_top3_selection_heatmap.png, experiments/EXP-0017/inputs/data/raw/2.csv, experiments/EXP-0017/inputs/data/raw/8.xlsx, experiments/EXP-0017/inputs/src/q2_lib.py, experiments/EXP-0017/inputs/src/q2_topk.py, experiments/EXP-0017/inputs/src/q_common.py
- experiment EXP-0018: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0018/figures.json, experiments/EXP-0018/outputs.json, experiments/EXP-0018/predictions_long.csv, experiments/EXP-0018/seed-receipt.json, experiments/EXP-0018/figures/q1_ridge_per_target_mae.png, experiments/EXP-0018/figures/q1_ridge_residuals.png, experiments/EXP-0018/figures/q1_ridge_scatter.png, experiments/EXP-0018/inputs/src/q1_candidate_ridge.py, experiments/EXP-0018/inputs/src/q_common.py
- experiment EXP-0019: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0019/figures.json, experiments/EXP-0019/outputs.json, experiments/EXP-0019/seed-receipt.json, experiments/EXP-0019/sets.json, experiments/EXP-0019/sets_nested.json, experiments/EXP-0019/figures/q2_bootstrap_inclusion.png, experiments/EXP-0019/figures/q2_coexpression.png, experiments/EXP-0019/figures/q2_method_jaccard.png, experiments/EXP-0019/figures/q2_top3_selection_heatmap.png
- experiment EXP-0020 is queued and is not in the package
- experiment EXP-0021: 10 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0021/figures.json, experiments/EXP-0021/generated_profiles.csv, experiments/EXP-0021/generated_profiles_unconstrained.csv, experiments/EXP-0021/outputs.json, experiments/EXP-0021/seed-receipt.json, experiments/EXP-0021/transfer_profiles.csv, experiments/EXP-0021/figures/q3_constraint_satisfaction.png, experiments/EXP-0021/figures/q3_generated_vs_real.png, experiments/EXP-0021/figures/q3_sensory_profiles.png, experiments/EXP-0021/figures/q3_transfer_defects.png
- experiment EXP-0022 is queued and is not in the package
- experiment EXP-0023: 10 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0023/figures.json, experiments/EXP-0023/outputs.json, experiments/EXP-0023/seed-receipt.json, experiments/EXP-0023/sets.json, experiments/EXP-0023/sets_nested.json, experiments/EXP-0023/figures/q2_baseline_global_importance.png, experiments/EXP-0023/figures/q2_baseline_jaccard.png, experiments/EXP-0023/inputs/src/q2_baseline.py, experiments/EXP-0023/inputs/src/q2_lib.py, experiments/EXP-0023/inputs/src/q_common.py
- experiment EXP-0024: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0024/figures.json, experiments/EXP-0024/outputs.json, experiments/EXP-0024/predictions_long.csv, experiments/EXP-0024/seed-receipt.json, experiments/EXP-0024/figures/q1_baseline_per_target_mae.png, experiments/EXP-0024/figures/q1_baseline_residuals.png, experiments/EXP-0024/figures/q1_baseline_scatter.png, experiments/EXP-0024/inputs/src/q1_baseline.py, experiments/EXP-0024/inputs/src/q_common.py
- experiment EXP-0025: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0025/figures.json, experiments/EXP-0025/outputs.json, experiments/EXP-0025/predictions_long.csv, experiments/EXP-0025/seed-receipt.json, experiments/EXP-0025/figures/q1_ridge_per_target_mae.png, experiments/EXP-0025/figures/q1_ridge_residuals.png, experiments/EXP-0025/figures/q1_ridge_scatter.png, experiments/EXP-0025/inputs/src/q1_candidate_ridge.py, experiments/EXP-0025/inputs/src/q_common.py
- experiment EXP-0026: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0026/figures.json, experiments/EXP-0026/outputs.json, experiments/EXP-0026/predictions_long.csv, experiments/EXP-0026/seed-receipt.json, experiments/EXP-0026/figures/q1_ridge_per_target_mae.png, experiments/EXP-0026/figures/q1_ridge_residuals.png, experiments/EXP-0026/figures/q1_ridge_scatter.png, experiments/EXP-0026/inputs/src/q1_candidate_ridge.py, experiments/EXP-0026/inputs/src/q_common.py
- experiment EXP-0027: 16 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0027/figures.json, experiments/EXP-0027/generated_profiles.csv, experiments/EXP-0027/generated_profiles_unconstrained.csv, experiments/EXP-0027/outputs.json, experiments/EXP-0027/seed-receipt.json, experiments/EXP-0027/transfer_profiles.csv, experiments/EXP-0027/figures/q3_constraint_satisfaction.png, experiments/EXP-0027/figures/q3_generated_vs_real.png, experiments/EXP-0027/figures/q3_sensory_profiles.png, experiments/EXP-0027/figures/q3_transfer_defects.png, experiments/EXP-0027/inputs/data/processed/data_quality.json, experiments/EXP-0027/inputs/data/processed/q1_mapped.csv, experiments/EXP-0027/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0027/inputs/src/q3_generate.py, experiments/EXP-0027/inputs/src/q3_lib.py, experiments/EXP-0027/inputs/src/q_common.py
- experiment EXP-0028 is queued and is not in the package
- experiment EXP-0029: 16 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0029/figures.json, experiments/EXP-0029/generated_profiles.csv, experiments/EXP-0029/generated_profiles_unconstrained.csv, experiments/EXP-0029/outputs.json, experiments/EXP-0029/seed-receipt.json, experiments/EXP-0029/transfer_profiles.csv, experiments/EXP-0029/figures/q3_constraint_satisfaction.png, experiments/EXP-0029/figures/q3_generated_vs_real.png, experiments/EXP-0029/figures/q3_sensory_profiles.png, experiments/EXP-0029/figures/q3_transfer_defects.png, experiments/EXP-0029/inputs/data/processed/data_quality.json, experiments/EXP-0029/inputs/data/processed/q1_mapped.csv, experiments/EXP-0029/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0029/inputs/src/q3_generate.py, experiments/EXP-0029/inputs/src/q3_lib.py, experiments/EXP-0029/inputs/src/q_common.py
- experiment EXP-0030 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0031: 7 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0031/figures.json, experiments/EXP-0031/outputs.json, experiments/EXP-0031/predictions_long.csv, experiments/EXP-0031/seed-receipt.json, experiments/EXP-0031/figures/q1_ridge_per_target_mae.png, experiments/EXP-0031/figures/q1_ridge_residuals.png, experiments/EXP-0031/figures/q1_ridge_scatter.png
- experiment EXP-0032: 7 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0032/figures.json, experiments/EXP-0032/outputs.json, experiments/EXP-0032/predictions_long.csv, experiments/EXP-0032/seed-receipt.json, experiments/EXP-0032/figures/q1_ridge_per_target_mae.png, experiments/EXP-0032/figures/q1_ridge_residuals.png, experiments/EXP-0032/figures/q1_ridge_scatter.png
- experiment EXP-0033: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0033/figures.json, experiments/EXP-0033/outputs.json, experiments/EXP-0033/seed-receipt.json, experiments/EXP-0033/sets.json, experiments/EXP-0033/sets_nested.json, experiments/EXP-0033/figures/q2_bootstrap_inclusion.png, experiments/EXP-0033/figures/q2_coexpression.png, experiments/EXP-0033/figures/q2_method_jaccard.png, experiments/EXP-0033/figures/q2_top3_selection_heatmap.png
- experiment EXP-0034: 10 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0034/figures.json, experiments/EXP-0034/generated_profiles.csv, experiments/EXP-0034/generated_profiles_unconstrained.csv, experiments/EXP-0034/outputs.json, experiments/EXP-0034/seed-receipt.json, experiments/EXP-0034/transfer_profiles.csv, experiments/EXP-0034/figures/q3_constraint_satisfaction.png, experiments/EXP-0034/figures/q3_generated_vs_real.png, experiments/EXP-0034/figures/q3_sensory_profiles.png, experiments/EXP-0034/figures/q3_transfer_defects.png
- experiment EXP-0035: 7 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0035/figures.json, experiments/EXP-0035/outputs.json, experiments/EXP-0035/predictions_long.csv, experiments/EXP-0035/seed-receipt.json, experiments/EXP-0035/figures/q1_ridge_per_target_mae.png, experiments/EXP-0035/figures/q1_ridge_residuals.png, experiments/EXP-0035/figures/q1_ridge_scatter.png

## 七、诚实边界（本包不能保证的部分）

1. **不生成 PDF/TeX**：本包保证 md 交付。`contest.yaml` 声明了 tex/pdf 而实际没有产出时，交付检查会**判失败**，
   不会把“应该能生成”写成“已就绪”。
2. **随机性**：随机过程按登记的 seed 复跑；未固定的差异以 `evaluation.reproductionTolerance` 比较，超出即视为不可复现。
3. **原始数据不随包分发**：原始附件只以 sha256 记录，需要从原始来源重新获取。
4. **环境随本地而定**：解释器、依赖版本、时间戳不随包分发；换环境后请重新探测解释器并重跑实验。
5. **比赛要求只核对声明的部分**：页数/匿名/命名/AI 说明只在 `contest.yaml` 的 `delivery.contest` 声明后才核对，
   且只有能机械核对的部分被核对（例如页数需要 PDF）；其余需人工确认。

## 八、包内文件清单

- report/data-quality.md
- report/paper.aux
- report/paper.log
- report/paper.md
- report/paper.pdf
- report/paper.tex
- report/q1-modeling.md
- report/q2-factor-analysis.md
- report/q3-generation.md
- report/rendered.md
- report/rendered.refs.json
- report/robustness.md
- report/validation-notes.md
- figures/FIG-0001-q1_ridge_per_target_mae.png
- experiments/EXP-0002/figures/q1_ridge_per_target_mae.png
- figures/FIG-0002-q1_ridge_scatter.png
- experiments/EXP-0002/figures/q1_ridge_scatter.png
- figures/FIG-0003-q1_ridge_residuals.png
- experiments/EXP-0002/figures/q1_ridge_residuals.png
- figures/FIG-0004-q1_baseline_per_target_mae.png
- experiments/EXP-0001/figures/q1_baseline_per_target_mae.png
- figures/FIG-0005-q2_top3_selection_heatmap.png
- experiments/EXP-0005/figures/q2_top3_selection_heatmap.png
- figures/FIG-0006-q2_bootstrap_inclusion.png
- experiments/EXP-0005/figures/q2_bootstrap_inclusion.png
- figures/FIG-0007-q2_method_jaccard.png
- experiments/EXP-0005/figures/q2_method_jaccard.png
- figures/FIG-0008-q2_coexpression.png
- experiments/EXP-0005/figures/q2_coexpression.png
- figures/FIG-0009-q3_sensory_profiles.png
- experiments/EXP-0007/figures/q3_sensory_profiles.png
- figures/FIG-0010-q3_generated_vs_real.png
- experiments/EXP-0007/figures/q3_generated_vs_real.png
- figures/FIG-0011-q3_transfer_defects.png
- experiments/EXP-0007/figures/q3_transfer_defects.png
- figures/FIG-0012-q3_constraint_satisfaction.png
- experiments/EXP-0007/figures/q3_constraint_satisfaction.png
- figures/figures.json
- src/00_prepare_outlier_audit.py
- src/00_prepare_pools.py
- src/00_prepare_q1q2.py
- src/00_prepare_q3.py
- src/__pycache__/q2_lib.cpython-312.pyc
- src/__pycache__/q3_lib.cpython-312.pyc
- src/__pycache__/q_common.cpython-312.pyc
- src/q1_baseline.py
- src/q1_candidate_hgb.py
- src/q1_candidate_ridge.py
- src/q1_outlier_diagnostic.py
- src/q2_baseline.py
- src/q2_lib.py
- src/q2_topk.py
- src/q3_baseline.py
- src/q3_generate.py
- src/q3_lib.py
- src/q_common.py
- src/validate_q2.py
- src/validate_q3.py
- data/processed/q1_mapped.csv
- data/raw/4.csv
- data/processed/q2_raw.csv
- data/processed/q3_table.csv
- data/raw/1.csv
- data/processed/q1_pool.csv
- data/processed/q2_pool.csv
- data/processed/q3_pool.csv
- data/splits/SPLIT-0001/assignment.csv
- data/splits/SPLIT-0001/train.csv
- data/splits/SPLIT-0001/test.csv
- data/splits/SPLIT-0002/assignment.csv
- data/splits/SPLIT-0002/train.csv
- data/splits/SPLIT-0002/test.csv
- data/splits/SPLIT-0003/assignment.csv
- data/splits/SPLIT-0003/train.csv
- data/splits/SPLIT-0003/test.csv
- data/splits/SPLIT-0004/assignment.csv
- data/splits/SPLIT-0004/train.csv
- data/splits/SPLIT-0004/test.csv
- data/splits/SPLIT-0005/assignment.csv
- data/splits/SPLIT-0005/train.csv
- data/splits/SPLIT-0005/test.csv
- data/splits/SPLIT-0006/assignment.csv
- data/splits/SPLIT-0006/train.csv
- data/splits/SPLIT-0006/test.csv
- data/splits/SPLIT-0007/assignment.csv
- data/splits/SPLIT-0007/train.csv
- data/splits/SPLIT-0007/test.csv
- data/splits/SPLIT-0008/assignment.csv
- data/splits/SPLIT-0008/train.csv
- data/splits/SPLIT-0008/test.csv
- data/splits/SPLIT-0009/assignment.csv
- data/splits/SPLIT-0009/train.csv
- data/splits/SPLIT-0009/test.csv
- data/splits/SPLIT-0010/assignment.csv
- data/splits/SPLIT-0010/train.csv
- data/splits/SPLIT-0010/test.csv
- data/splits/SPLIT-0011/assignment.csv
- data/splits/SPLIT-0011/train.csv
- data/splits/SPLIT-0011/test.csv
- data/splits/SPLIT-0012/assignment.csv
- data/splits/SPLIT-0012/train.csv
- data/splits/SPLIT-0012/test.csv
- data/splits/SPLIT-0013/assignment.csv
- data/splits/SPLIT-0013/train.csv
- data/splits/SPLIT-0013/test.csv
- data/splits/SPLIT-0014/assignment.csv
- data/splits/SPLIT-0014/train.csv
- data/splits/SPLIT-0014/test.csv
- data/splits/SPLIT-0015/assignment.csv
- data/splits/SPLIT-0015/train.csv
- data/splits/SPLIT-0015/test.csv
- data/splits/SPLIT-0016/assignment.csv
- data/splits/SPLIT-0016/train.csv
- data/splits/SPLIT-0016/test.csv
- data/splits/SPLIT-0017/assignment.csv
- data/splits/SPLIT-0017/train.csv
- data/splits/SPLIT-0017/test.csv
- experiments/EXP-0001/metrics.json
- experiments/EXP-0001/predictions.csv
- experiments/EXP-0001/result.json
- experiments/EXP-0002/metrics.json
- experiments/EXP-0002/predictions.csv
- experiments/EXP-0002/result.json
- experiments/EXP-0003/metrics.json
- experiments/EXP-0003/predictions.csv
- experiments/EXP-0003/result.json
- experiments/EXP-0004/metrics.json
- experiments/EXP-0004/result.json
- experiments/EXP-0005/metrics.json
- experiments/EXP-0005/result.json
- experiments/EXP-0006/metrics.json
- experiments/EXP-0006/result.json
- experiments/EXP-0007/metrics.json
- experiments/EXP-0007/result.json
- experiments/EXP-0010/metrics.json
- experiments/EXP-0010/result.json
- experiments/EXP-0013/metrics.json
- experiments/EXP-0013/result.json
- experiments/EXP-0014/metrics.json
- experiments/EXP-0014/result.json
- experiments/EXP-0015/metrics.json
- experiments/EXP-0015/predictions.csv
- experiments/EXP-0015/result.json
- experiments/EXP-0016/metrics.json
- experiments/EXP-0016/predictions.csv
- experiments/EXP-0016/result.json
- experiments/EXP-0017/metrics.json
- experiments/EXP-0017/result.json
- experiments/EXP-0018/metrics.json
- experiments/EXP-0018/predictions.csv
- experiments/EXP-0018/result.json
- experiments/EXP-0019/metrics.json
- experiments/EXP-0019/result.json
- experiments/EXP-0019/q2_topk.py
- experiments/EXP-0021/metrics.json
- experiments/EXP-0021/result.json
- experiments/EXP-0021/q3_generate.py
- experiments/EXP-0023/metrics.json
- experiments/EXP-0023/result.json
- experiments/EXP-0024/metrics.json
- experiments/EXP-0024/predictions.csv
- experiments/EXP-0024/result.json
- experiments/EXP-0025/metrics.json
- experiments/EXP-0025/predictions.csv
- experiments/EXP-0025/result.json
- experiments/EXP-0026/metrics.json
- experiments/EXP-0026/predictions.csv
- experiments/EXP-0026/result.json
- experiments/EXP-0027/metrics.json
- experiments/EXP-0027/result.json
- experiments/EXP-0029/metrics.json
- experiments/EXP-0029/result.json
- experiments/EXP-0031/metrics.json
- experiments/EXP-0031/predictions.csv
- experiments/EXP-0031/result.json
- experiments/EXP-0031/q1_candidate_ridge.py
- experiments/EXP-0032/metrics.json
- experiments/EXP-0032/predictions.csv
- experiments/EXP-0032/result.json
- experiments/EXP-0032/q1_candidate_ridge.py
- experiments/EXP-0033/metrics.json
- experiments/EXP-0033/result.json
- experiments/EXP-0033/q2_topk.py
- experiments/EXP-0034/metrics.json
- experiments/EXP-0034/result.json
- experiments/EXP-0034/q3_generate.py
- experiments/EXP-0035/metrics.json
- experiments/EXP-0035/predictions.csv
- experiments/EXP-0035/result.json
- experiments/EXP-0035/q1_candidate_ridge.py
- contest.yaml
- ledger-summary.json
