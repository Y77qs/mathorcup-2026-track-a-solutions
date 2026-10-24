# 复现说明 — beer-2026-a-v3（交付目录 delivery/20261024-223751）

> 本文件由 `modeling_deliver {action:"package"}` 从项目台账生成：
> 台账 revision 2743，contest.yaml sha256 2ce0b2c3a72911328c4ed302840b63f3c50e5fcbd49a8744c348c176e2904271，生成时间 2026-10-24T14:37:51.334Z，
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
delivery/20261024-223751/
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
tar -xzf delivery/20261024-223751.tar.gz
cd delivery/20261024-223751
shasum -a 256 -c SHA256SUMS
```

数据集与它们的 hash：

| 数据集 | 文件 | sha256(前16) | 目标列 |
|---|---|---|---|
| DATA-0001 | data/clean/q2_raw.csv | 4948a908ab943d02 | A_malt_all |
| DATA-0002 | data/clean/q1_mapped.csv | 2e317968fa68b7c2 | A_malt_all |
| DATA-0003 | data/clean/q3.csv | 4948a908ab943d02 | chem__ethanol..v.v. |
| DATA-0004 | data/clean/q3.csv | 4948a908ab943d02 | overall |

划分方式与划分文件的 hash：

| 划分 | 数据集 | 方法 | train sha256 | test sha256 | assignment 文件 |
|---|---|---|---|---|---|
| SPLIT-0001 | DATA-0001 | random-holdout | bf6bad1d336c | 9dff5dd80e7d | data/splits/SPLIT-0001/assignment.csv |
| SPLIT-0002 | DATA-0002 | random-holdout | 353f1814d947 | b729d617d4fd | data/splits/SPLIT-0002/assignment.csv |

> 原始附件不在包内；按下面的 sha256 从原始来源重新获取，再走同一清洗脚本：

| 原始文件 | 来源名 | 项目内路径 | sha256(前16) | 角色 |
|---|---|---|---|---|
| RAW-41984922 | 419849227a02e0c7-1.csv | data/raw/imported/419849227a02e0c7-1.csv | 419849227a02e0c7 | chem |
| RAW-415709ac | 415709ac10f2f730-2.csv | data/raw/imported/415709ac10f2f730-2.csv | 415709ac10f2f730 | corr |
| RAW-fe4dcabd | fe4dcabd48431e6d-3.xlsx | data/raw/imported/fe4dcabd48431e6d-3.xlsx | fe4dcabd48431e6d | scorecards |
| RAW-43a7b386 | 43a7b38682ed81ce-4.csv | data/raw/imported/43a7b38682ed81ce-4.csv | 43a7b38682ed81ce | sensory |
| RAW-c512eed1 | c512eed108de6f98-5.csv | data/raw/imported/c512eed108de6f98-5.csv | c512eed108de6f98 | derived |
| RAW-a55004fb | a55004fb0390299a-6.csv | data/raw/imported/a55004fb0390299a-6.csv | a55004fb0390299a | derived |
| RAW-2083138d | 2083138df46640e2-7.csv | data/raw/imported/2083138df46640e2-7.csv | 2083138df46640e2 | sensory7 |
| RAW-f2316766 | f2316766792111d9-8.xlsx | data/raw/imported/f2316766792111d9-8.xlsx | f2316766792111d9 | calibrated |
| RAW-40813e27 | 40813e273e081ae0-数据说明.txt | data/raw/imported/40813e273e081ae0-数据说明.txt | 40813e273e081ae0 | readme |

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
| EXP-0001 | Q1 | MODEL-0001 | succeeded | 0.4005615400064 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0001/inputs/src/q1_baseline.py` |
| EXP-0002 | Q2 | MODEL-0002 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0002/inputs/src/q2_baseline.py` |
| EXP-0003 | Q1 | MODEL-0003 | succeeded | 0.35455830244427766 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0003/inputs/src/q1_candidate.py` |
| EXP-0004 | Q1 | MODEL-0004 | succeeded | 0.3465674099243312 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0004/inputs/src/q1_fusion.py` |
| EXP-0005 | Q3 | MODEL-0005 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0005/inputs/src/q3_baseline.py` |
| EXP-0006 | Q2 | MODEL-0006 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0006/inputs/src/q2_topk.py` |
| EXP-0007 | Q3 | MODEL-0007 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0007/inputs/src/q3_generate.py` |
| EXP-0008 | Q3 | MODEL-0005 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0008/inputs/src/q3_baseline.py` |
| EXP-0009 | Q3 | MODEL-0007 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0009/inputs/src/q3_generate.py` |
| EXP-0010 | Q1 | MODEL-0004 | succeeded | 0.3465674099243312 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0004/inputs/src/q1_fusion.py` |
| EXP-0011 | Q2 | MODEL-0006 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0006/inputs/src/q2_topk.py` |
| EXP-0013 | Q3 | MODEL-0007 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0013/inputs/src/q3_generate.py` |
| EXP-0014 | Q3 | MODEL-0008 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0014/inputs/src/q3_generate.py` |
| EXP-0015 | Q3 | MODEL-0008 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0014/inputs/src/q3_generate.py` |
| EXP-0016 | Q1 | MODEL-0004 | succeeded | 0.35039761171092537 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0016/inputs/src/q1_robust.py --seed 20261024 --alpha-multiplier 1.0` |
| EXP-0017 | Q1 | MODEL-0004 | succeeded | 0.3504945149881529 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0017/inputs/src/q1_robust.py --seed 20261025 --alpha-multiplier 1.0` |
| EXP-0018 | Q1 | MODEL-0004 | succeeded | 0.3489273952475994 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0018/inputs/src/q1_robust.py --seed 20261024 --alpha-multiplier 2.0` |
| EXP-0019 | Q2 | MODEL-0006 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0019/inputs/src/q2_robust.py --seed 20261024 --tau 0.5` |
| EXP-0020 | Q2 | MODEL-0006 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0020/inputs/src/q2_robust.py --seed 20261025 --tau 0.5` |
| EXP-0021 | Q2 | MODEL-0006 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0021/inputs/src/q2_robust.py --seed 20261024 --tau 0.6` |
| EXP-0022 | Q3 | MODEL-0008 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0022/inputs/src/q3_robust.py --seed 20261024 --kappa 5 --kappa-r 20` |
| EXP-0023 | Q3 | MODEL-0008 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0023/inputs/src/q3_robust.py --seed 20261025 --kappa 5 --kappa-r 20` |
| EXP-0024 | Q3 | MODEL-0008 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0024/inputs/src/q3_robust.py --seed 20261024 --kappa 15 --kappa-r 20` |
| EXP-0025 | Q1 | MODEL-0004 | succeeded | 0.3465674099243312 | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0025/inputs/src/q1_fusion.py` |
| EXP-0026 | Q1 | MODEL-0009 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0026/inputs/src/q1_grade_all.py` |
| EXP-0028 | Q3 | MODEL-0011 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0028/inputs/src/q3_generate.py` |
| EXP-0029 | Q2 | MODEL-0012 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0029/inputs/src/q2_topk.py` |
| EXP-0030 | Q2 | MODEL-0012 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0029/inputs/src/q2_topk.py` |
| EXP-0031 | Q3 | MODEL-0011 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0028/inputs/src/q3_generate.py` |
| EXP-0032 | Q3 | MODEL-0011 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0032/inputs/src/q3_generate.py` |
| EXP-0033 | Q3 | MODEL-0013 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0033/inputs/src/q3_generate.py` |
| EXP-0034 | Q3 | MODEL-0013 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0033/inputs/src/q3_generate.py` |
| EXP-0035 | Q1 | MODEL-0014 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0035/inputs/src/ablation_summary.py` |
| EXP-0036 | Q1 | MODEL-0015 | succeeded | （无 mae） | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python experiments/EXP-0036/inputs/src/headline_audit.py` |

> 复跑关系（哪个实验是谁的 `rerunOf`）见 `ledger-summary.json` 的 `experiments[]`。
> 新跑出来的数是**新实验**的数，不是旧实验的数；不要在包内覆盖旧结果。

## 五、复核结论与验证

| 校验 | 实验 | 类型 | 结果 | 新鲜度 |
|---|---|---|---|---|
| VAL-0001 | EXP-0004 | split-integrity | passed | fresh |
| VAL-0002 | EXP-0004 | leakage | passed | fresh |
| VAL-0003 | EXP-0004 | holdout-metrics | passed | fresh |
| VAL-0004 | EXP-0004 | baseline-compare | passed | fresh |
| VAL-0005 | EXP-0004 | independent-rerun | passed | fresh |
| VAL-0006 | EXP-0006 | leakage | passed | fresh |
| VAL-0007 | EXP-0006 | holdout-metrics | passed | fresh |
| VAL-0008 | EXP-0006 | independent-rerun | passed | fresh |
| VAL-0009 | EXP-0009 | leakage | passed | fresh |
| VAL-0010 | EXP-0009 | holdout-metrics | passed | fresh |
| VAL-0011 | EXP-0009 | simulation-seeds | FAILED | fresh |
| VAL-0012 | EXP-0013 | simulation-seeds | passed | fresh |
| VAL-0013 | EXP-0014 | leakage | passed | fresh |
| VAL-0014 | EXP-0014 | holdout-metrics | passed | fresh |
| VAL-0015 | EXP-0014 | simulation-seeds | passed | fresh |
| VAL-0016 | EXP-0014 | independent-rerun | passed | fresh |
| VAL-0017 | EXP-0029 | leakage | passed | fresh |
| VAL-0018 | EXP-0029 | holdout-metrics | passed | fresh |
| VAL-0019 | EXP-0029 | independent-rerun | passed | fresh |
| VAL-0020 | EXP-0028 | leakage | FAILED | fresh |
| VAL-0021 | EXP-0028 | holdout-metrics | passed | fresh |
| VAL-0022 | EXP-0028 | simulation-seeds | passed | fresh |
| VAL-0023 | EXP-0028 | independent-rerun | passed | fresh |
| VAL-0024 | EXP-0032 | leakage | passed | fresh |
| VAL-0025 | EXP-0032 | holdout-metrics | passed | fresh |
| VAL-0026 | EXP-0032 | simulation-seeds | passed | fresh |
| VAL-0027 | EXP-0033 | leakage | passed | fresh |
| VAL-0028 | EXP-0033 | holdout-metrics | passed | fresh |
| VAL-0029 | EXP-0033 | simulation-seeds | passed | fresh |
| VAL-0030 | EXP-0033 | independent-rerun | passed | fresh |
| VAL-0031 | EXP-0004 | independent-rerun | passed | fresh |
| VAL-0032 | EXP-0004 | split-integrity | passed | fresh |
| VAL-0033 | EXP-0004 | leakage | passed | fresh |
| VAL-0034 | EXP-0004 | holdout-metrics | passed | fresh |
| VAL-0035 | EXP-0004 | baseline-compare | passed | fresh |
| VAL-0036 | EXP-0004 | independent-rerun | passed | fresh |
| VAL-0037 | EXP-0029 | leakage | passed | fresh |
| VAL-0038 | EXP-0029 | holdout-metrics | passed | fresh |
| VAL-0039 | EXP-0029 | independent-rerun | passed | fresh |
| VAL-0040 | EXP-0033 | leakage | passed | fresh |
| VAL-0041 | EXP-0033 | holdout-metrics | passed | fresh |
| VAL-0042 | EXP-0033 | simulation-seeds | passed | fresh |
| VAL-0043 | EXP-0033 | independent-rerun | passed | fresh |

| 论断 | 小题 | 状态 | 陈述(截断) |
|---|---|---|---|
| CLAIM-0001 | Q1 | SUPERSEDED | 在 SPLIT-0002 的 50 行留出上，训练内 OOF 融合（median 权重 0、graph 0.649、HG |
| CLAIM-0002 | Q1 | SUPERSEDED | Q1 的三项训练内消融只显示很小的增益：Rank-Gauss 相对标准化 CV MAE 改善 0.00399，普通 Ri |
| CLAIM-0003 | Q2 | SUPERSEDED | 在 200 行训练集上，50 维 × 4 方法的 Top-3 平均两两 Jaccard 为 0.21867（点估计集合、 |
| CLAIM-0004 | Q3 | SUPERSEDED | 风格条件 copula 生成器（κ=5、κ_R=20）在 310 个输出（250 个 OOF 生成 + 49 个未见风格 |
| CLAIM-0005 | Q3 | SUPERSEDED | Pils/Lager→Tripel 迁移在 c_new≤max(c_source,T)（超阈不恶化）与 c_new≤c_ |
| CLAIM-0006 | Q1 | SUPERSEDED | 三项预注册稳健性判定全部通过：Q1 训练内 CV MAE 在 seed 与 λ 扰动下的相对极差 0.00447（≤0. |
| CLAIM-0007 | Q1 | SUPERSEDED | 在 SPLIT-0002 的 50 行留出上，训练内 OOF 融合（median 权重 0、graph 0.649、HG |
| CLAIM-0008 | Q1 | SUPERSEDED | Q1 的三项训练内消融只显示很小的增益：Rank-Gauss 相对标准化 CV MAE 改善 0.00399，普通 Ri |
| CLAIM-0009 | Q2 | SUPERSEDED | 在 200 行训练集上，50 维 × 4 方法的 Top-3 平均两两 Jaccard 为 0.21867（点估计集合、 |
| CLAIM-0010 | Q3 | SUPERSEDED | 风格条件 copula 生成器（κ=5、κ_R=20）在 310 个输出（250 个 OOF 生成 + 49 个未见风格 |
| CLAIM-0011 | Q3 | SUPERSEDED | Pils/Lager→Tripel 迁移在 c_new≤max(c_source,T)（超阈不恶化）与 c_new≤c_ |
| CLAIM-0012 | Q1 | active | 三项预注册稳健性判定全部通过：Q1 训练内 CV MAE 在 seed 与 λ 扰动下的相对极差 0.00447（≤0. |
| CLAIM-0013 | Q1 | SUPERSEDED | 在 SPLIT-0002 的 50 行留出上，训练内 OOF 融合（median 权重 0、graph 0.649、HG |
| CLAIM-0014 | Q1 | active | Q1 的三项训练内消融都只有很小的增益：Rank-Gauss 相对原尺度标准化的训练内 CV MAE 低 0.00399 |
| CLAIM-0015 | Q2 | SUPERSEDED | 在 200 行训练集上，以附件 2.csv 的 231×231 Spearman 矩阵（PSD 投影：原始最小特征值 − |
| CLAIM-0016 | Q3 | SUPERSEDED | 风格条件 copula 生成器（κ=5、κ_R=20，训练内跨折选择）在 310 个输出（250 个 3 折 out-o |
| CLAIM-0017 | Q3 | SUPERSEDED | Pils/Lager→Tripel 迁移在两种非恶化策略下的策略相对非恶化率都是 1.0，但这是可行域投影构造保证的、不 |
| CLAIM-0018 | Q1 | active | 在 SPLIT-0002 的 50 行留出上，训练内 OOF 融合（median 权重 0、graph 0.649、HG |
| CLAIM-0019 | Q2 | active | 在 200 行训练集上，以附件 2.csv 的 231×231 Spearman 矩阵（PSD 投影：原始最小特征值 − |
| CLAIM-0020 | Q3 | SUPERSEDED | Pils/Lager→Tripel 迁移中，「绝对不增」策略（c_new≤c_source）的严格逐缺陷不增率为 1.0 |
| CLAIM-0021 | Q3 | active | 风格条件 copula 生成器（κ=5、κ_R=20，训练内跨折选择）在 310 个输出（250 个 3 折 out-o |
| CLAIM-0022 | Q3 | active | Pils/Lager→Tripel 迁移中，两种策略的**策略相对**非恶化率都是 1.0，两种策略在「绝对不增」与 c |

| 图 | 标题 | 文件 | sha256(前16) | 状态 |
|---|---|---|---|---|
| FIG-0001 | Q1 融合模型的三个分量（训练内 OOF）与融合结果的逐目标 MAE 对比：纵轴为 50 个感官维度，横轴为 MAE。 | experiments/EXP-0004/figures/q1_fusion_component_mae.png | dc7d0e88336672d8 | active |
| FIG-0002 | Q1 融合权重（训练内 OOF 最小二乘 + 单纯形投影）：全局与 Aroma/Flavour/其他三组的 median、graph、HGB 权重。 | experiments/EXP-0004/figures/q1_fusion_weights.png | 24e9efbd7113526a | active |
| FIG-0003 | Q1 图正则低秩回归的训练内 5 折 CV MAE 网格（27 个 (r, λ, γ) 格点），用于说明超参数选择只发生在训练折内部。 | experiments/EXP-0003/figures/q1_cv_mae_grid.png | ed6506d846da6f98 | active |
| FIG-0004 | Q1 逐目标 MAE 改善（候选相对逐目标训练中位数基线）：正值表示改善，负值表示恶化，标注了 40 个改善维与 10 个恶化维。 | experiments/EXP-0003/figures/q1_per_target_improvement.png | 234c3d58343f6d0c | active |
| FIG-0005 | Q1 留出集上 0–6 相对分级的混淆矩阵（行=参考级，列=预测级）：分级由训练折中点经验 CDF 派生，仅作相对强度参考。 | experiments/EXP-0003/figures/q1_grade_confusion.png | 864362a8836bd943 | active |
| FIG-0006 | Q2 500 次风格分层 bootstrap 下每个感官维度 Top-3 的入选频率（π）：颜色越深表示该化合物越稳定入选。 | experiments/EXP-0006/figures/q2_bootstrap_stability.png | d192737752ae3e60 | active |
| FIG-0007 | Q2 四种方法（总体 Spearman、风格内 Spearman、图正则低秩系数、综合分）两两 Top-3 Jaccard 系数的 50 维平均。 | experiments/EXP-0006/figures/q2_method_jaccard.png | 3f6d8bfc57d10715 | active |
| FIG-0008 | Q2 训练样本 Spearman 网络（τ=0.5）的连通模块结构：节点为 219 个单体化合物候选，边为阈值化相关。 | experiments/EXP-0006/figures/q2_module_graph.png | 227cea51df32c1f5 | active |
| FIG-0009 | Q3 逐风格归一化能量距离（越小越好）：低缺陷生成 vs 未约束生成 vs 真实—真实参照，按 22 个风格分组。 | experiments/EXP-0014/figures/energy-distance-by-style.png | 1bec850a71a6efd7 | active |
| FIG-0010 | Q3 缺陷超阈率对比：低缺陷生成（0）、未约束生成（约 0.85）与真实数据（0.844），阈值取 8.xlsx Sensory thresholds 的均值。 | experiments/EXP-0014/figures/defect-exceedance.png | de50a1d57a9e7738 | active |
| FIG-0011 | Q3 Pils/Lager→Tripel 迁移的 2 策略 × 2 阈值情景：非恶化率、平均 L1 改动量与目标风格马氏距离。 | experiments/EXP-0014/figures/transfer-scenarios.png | b020b99397afeb74 | active |
| FIG-0012 | Q3 迁移的“目标风格接近程度 ↔ 谱改动规模”Pareto 前沿（λ∈{0.1,1,10} × η∈{0,0.01,0.1}，9 个格点）。 | experiments/EXP-0014/figures/transfer-pareto.png | ea25faf2342e3b4a | active |
| FIG-0013 | Q3 九项消融中的 5–9 项：独立边际 vs Copula、无收缩、无 floor 混合、普通 vs 低缺陷生成、分位数迁移 vs 约束优化。 | experiments/EXP-0014/figures/ablation-comparison.png | 63153604c807eac5 | active |
| FIG-0014 | Q3 生成谱经 Q1 感官预测代理映射后的 50 维感官画像与同风格真实留出样本画像的对比。 | experiments/EXP-0014/figures/profile-recovery.png | f68b0e77d832326b | active |
| FIG-0015 | Q3 无条件全局高斯基线 vs 真实数据的逐风格能量距离：基线忽略风格，误差显著大于风格条件模型。 | experiments/EXP-0008/figures/baseline-energy-distance.png | 523af105ce88651a | active |
| FIG-0016 | 问题一：三个分量与融合模型的 MAE 对比。横轴依次为逐目标训练中位数（OOF）、图正则低秩回归（OOF）、HGB（OOF）、融合（OOF）、融合（50 行留出测试）；红色虚线为同一批 50 行留出上的中位数基线 MAE。融合相对自身分量的增益很小，相对中位数基线的增益才是稳健的那个。 | figures/q1_component_mae.png | 7dd974449e1dfd4a | active |
| FIG-0017 | 问题一：训练内 OOF 拟合的单纯形权重（每行三个权重之和为 1），分为全局与 Aroma/Flavour/其他三组；全局与三组都把 median 分量的权重压到接近 0，graph 约 0.64、HGB 约 0.33–0.35。 | figures/q1_fusion_weights.png | 019d4e0bcb30882a | active |
| FIG-0018 | 问题一：50 个感官维度的留出 Skill = 1 − MAE_model/MAE_median，按 Skill 升序排列；绿色为相对中位数基线改善的 38 维，红色为恶化的 12 维（EXP-0004 的 improvedTargets/degradedTargets）。恶化集中在训练样本极少的缺陷/风格维度。 | figures/q1_per_target.png | a3f6b0f969746540 | active |
| FIG-0019 | 问题一：训练折内 5 折 CV 的 54 个格点（27 个 (r,λ,γ) 组合 × 2 种表示），纵轴为 CV MAE，灰色为原尺度 z-score、蓝色为 Rank-Gauss；橙色菱形为选中格点 r=10,λ=1,γ=1 及其折间标准差。全部超参数选择只发生在训练折内部，未接触留出集。 | figures/q1_cv_grid.png | a44a3b2b94655a71 | active |
| FIG-0020 | 问题一：交付的 250×50 相对强度分级表（EXP-0026 的 grades_all.csv）。左图为等级 0–6 的分布，200 行训练行（in-sample）与 50 行留出分别归一化；右图为按留出均值等级排序的 50 个维度在两个子集上的均值等级。等级是相对强度，0 不代表风味不存在、6 不代表人工评分满分。 | figures/q1_grades_all.png | ef678ce51f91c9a1 | active |
| FIG-0021 | 问题二：500 次风格分层 bootstrap 下交付 Top-3 的入选频率 π。左图为 150 个交付条目的 π 分布（均值 0.465，没有任何化合物达到 π=1），右图为 50 个维度各自的平均 π（按 π 排序）；这是把 π 作为稳定性主证据、并用平均综合分 S 裁决并列的依据。 | figures/q2_bootstrap_pi.png | 64dded4f4d27a381 | active |
| FIG-0022 | 问题二：四种方法（总体 Spearman、风格内 Spearman、图正则低秩 |B|、综合分 S）Top-3 集合两两 Jaccard 系数的 50 维平均；红色虚线为四种方法两两平均的主指标 topk-jaccard=0.219。总体与风格内两种关联的 Jaccard 仅 0.302（6 条边中最接近的两条），图正则系数与另两种排序的 Jaccard 只有 0.080。 | figures/q2_method_jaccard.png | ed7b64d556d07135 | active |
| FIG-0023 | 问题二：左图为训练网络（τ=0.5）的模块规模分布（纵轴对数），51 个连通块、最大块含 172 列；右图为训练网络（200 行重算）与附件 2.csv 网络（PSD 投影后阈值化）在 τ=0.4/0.5/0.6 下的连通分量数对比——两者都是“一个巨大连通块 + 大量单点”，模块区分度弱，因此模块只作解释线索而不进入 Top-3 打分。 | figures/q2_modules.png | 5734a42d9c5ff4bd | active |
| FIG-0024 | 问题三：约束生成在 22 个风格上的归一化能量距离（蓝柱，按风格留出样本量加权）与同样本量的真实—真实参照（橙点）；Kriek (n=10)、Lambic (n=11)、Faro (n=3) 等小风格波动很大，不声称精确刻画。 | figures/q3_energy_by_style.png | d58b540a9b70c537 | active |
| FIG-0025 | 问题三：至少一种均值阈值缺陷超阈的样本比例——真实数据 0.844、未约束条件生成 0.852、低缺陷生成 0.000。约束把缺陷超阈率降到 0，而生成模型在加约束前的缺陷水平与真实数据相当。 | figures/archive/FIG-0025-q3_defect_exceedance.png | 57e3e864e41517f8 | SUPERSEDED→FIG-0030 |
| FIG-0026 | 问题三：Pils/Lager→Tripel 的 4 个迁移情景（2 种非恶化策略 × mean/median 两套阈值）。左图为策略相对非恶化率（四种情景恒为 1.000，由投影构造保证）与严格逐缺陷不增率（绝对不增策略为 1.000，cap-at-max 策略仅 0.182）；右图为目标风格马氏距离，四种情景几乎相同（0.434–0.435），说明阈值情景的选择对目标接近度影响很小。 | figures/q3_transfer_scenarios.png | 7e4be79a9c929fb1 | active |
| FIG-0027 | 问题三：λ∈{0.1,1,10} × η∈{0,0.01,0.1} 共 9 个格点的 Pareto 前沿（横轴为平均 L1 改动量，纵轴为到 Tripel 的马氏距离，越小越接近目标风格）；λ 越大目标风格越近、谱改动越大，η 只带来很小的额外代价，且 9 个格点的非恶化率均为 1.0。 | figures/archive/FIG-0027-q3_pareto.png | 299df07e5a54e372 | SUPERSEDED→FIG-0031 |
| FIG-0028 | 问题三：生成谱经 Q1 感官代理映射后的 50 维感官画像与同风格真实留出样本画像的 Spearman 相关，按风格排列（横轴标注样本量）；蓝色虚线为合并口径的 0.796。逐风格异质性明显：Amber (n=12) 为负、Brut (n=4) 与 Brett/cofermented (n=6) 接近 0，Kriek (n=10) 与 Strong ale (n=18) 较高，因此合并分数不能读成逐风格可靠。 | figures/q3_profile.png | 7bf61b6f235470c4 | active |
| FIG-0029 | 九项必做消融汇总（EXP-0035 从三个实验的产物重新汇总，本图即该审计实验的产物）。上：Q1 第 1–3 项消融两侧的训练内 CV MAE 与折间标准差，三个差值都小于折间波动；中：Q2 第 4 项消融的总关联/风格内关联/综合分的 Top-3 Jaccard；下左：Q3 第 5–8 项的能量距离差（第 5 项“无 Copula”能量距离反而低 0.0080，但依赖结构谱 MAE 0.0151 明显差于 0.0063）；下右：Q3 第 9 项分位数初始化与约束优化的目标马氏距离（1.481 → 0.433）。 | experiments/EXP-0035/figures/ablation-summary.png | 7fca986b270e5dd5 | active |
| FIG-0030 | 问题三：至少一种均值阈值缺陷超阈的样本比例——真实数据 0.844、未约束条件生成 0.852、低缺陷生成 0.000。约束把缺陷超阈率降到 0，而生成模型在加约束前的缺陷水平与真实数据相当。 | figures/q3_defect_exceedance.png | 4d6c13f894c65ca0 | active |
| FIG-0031 | 问题三：λ∈{0.1,1,10} × η∈{0,0.01,0.1} 共 9 个格点的 Pareto 前沿（横轴为平均 L1 改动量，纵轴为到 Tripel 的马氏距离，越小越接近目标风格）；灰线连接同一 λ 的三个 η 变体，颜色区分 η，每个 λ 只标注一次。λ 越大目标风格越近、谱改动越大，η 只带来很小的额外代价，9 个格点的非恶化率全部与可行域允许的最大值一致。 | figures/q3_pareto.png | a404a27fa6adba2b | active |

> 论文里的每个数字都由占位符从台账渲染而来，逐条解析记录在 `report/rendered.refs.json`；
> 每条结论的证据引用在 `ledger-summary.json` 的 `claims[]` 里。

## 六、交付检查读数

passed 78 / failed 0 / skipped 5

已知限制与警告：

- experiment EXP-0001: 6 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0001/outputs.json, experiments/EXP-0001/predictions_long.csv, experiments/EXP-0001/seed-receipt.json, experiments/EXP-0001/inputs/src/q1_baseline.py, experiments/EXP-0001/inputs/src/q_common.py, experiments/EXP-0001/inputs/src/target_columns.py
- experiment EXP-0002: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0002/outputs.json, experiments/EXP-0002/seed-receipt.json, experiments/EXP-0002/sets.json, experiments/EXP-0002/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0002/inputs/src/q1_lib.py, experiments/EXP-0002/inputs/src/q2_baseline.py, experiments/EXP-0002/inputs/src/q2_lib.py, experiments/EXP-0002/inputs/src/q_common.py, experiments/EXP-0002/inputs/src/target_columns.py
- experiment EXP-0003: 8 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0003/figures.json, experiments/EXP-0003/outputs.json, experiments/EXP-0003/seed-receipt.json, experiments/EXP-0003/inputs/data/processed/q1_grade_params.json, experiments/EXP-0003/inputs/src/q1_candidate.py, experiments/EXP-0003/inputs/src/q1_lib.py, experiments/EXP-0003/inputs/src/q_common.py, experiments/EXP-0003/inputs/src/target_columns.py
- experiment EXP-0004: 8 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0004/figures.json, experiments/EXP-0004/outputs.json, experiments/EXP-0004/seed-receipt.json, experiments/EXP-0004/inputs/data/processed/q1_grade_params.json, experiments/EXP-0004/inputs/src/q1_fusion.py, experiments/EXP-0004/inputs/src/q1_lib.py, experiments/EXP-0004/inputs/src/q_common.py, experiments/EXP-0004/inputs/src/target_columns.py
- experiment EXP-0005: 13 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0005/figures.json, experiments/EXP-0005/outputs.json, experiments/EXP-0005/samples.csv, experiments/EXP-0005/seed-receipt.json, experiments/EXP-0005/figures/baseline-defect-exceedance.png, experiments/EXP-0005/figures/baseline-energy-distance.png, experiments/EXP-0005/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0005/inputs/data/clean/q3_thresholds.json, experiments/EXP-0005/inputs/data/processed/q1_grade_params.json, experiments/EXP-0005/inputs/src/q3_baseline.py, experiments/EXP-0005/inputs/src/q3_lib.py, experiments/EXP-0005/inputs/src/q_common.py, experiments/EXP-0005/inputs/src/target_columns.py
- experiment EXP-0006: 14 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0006/bootstrap_pi.csv, experiments/EXP-0006/figures.json, experiments/EXP-0006/outputs.json, experiments/EXP-0006/seed-receipt.json, experiments/EXP-0006/sets.json, experiments/EXP-0006/sets_pi_first.json, experiments/EXP-0006/inputs/data/clean/q2_chem_meta.json, experiments/EXP-0006/inputs/data/raw/imported/a55004fb0390299a-6.csv, experiments/EXP-0006/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0006/inputs/src/q1_lib.py, experiments/EXP-0006/inputs/src/q2_lib.py, experiments/EXP-0006/inputs/src/q2_topk.py, experiments/EXP-0006/inputs/src/q_common.py, experiments/EXP-0006/inputs/src/target_columns.py
- experiment EXP-0007: 20 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0007/figures.json, experiments/EXP-0007/outputs.json, experiments/EXP-0007/run-seed-20261024.json, experiments/EXP-0007/run-seed-20261025.json, experiments/EXP-0007/run-seed-20261026.json, experiments/EXP-0007/samples.csv, experiments/EXP-0007/seed-receipt.json, experiments/EXP-0007/figures/ablation-comparison.png, experiments/EXP-0007/figures/defect-exceedance.png, experiments/EXP-0007/figures/energy-distance-by-style.png, experiments/EXP-0007/figures/profile-recovery.png, experiments/EXP-0007/figures/transfer-pareto.png, experiments/EXP-0007/figures/transfer-scenarios.png, experiments/EXP-0007/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0007/inputs/data/clean/q3_thresholds.json, experiments/EXP-0007/inputs/data/processed/q1_grade_params.json, experiments/EXP-0007/inputs/src/q3_generate.py, experiments/EXP-0007/inputs/src/q3_lib.py, experiments/EXP-0007/inputs/src/q_common.py, experiments/EXP-0007/inputs/src/target_columns.py
- experiment EXP-0008: 12 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0008/figures.json, experiments/EXP-0008/outputs.json, experiments/EXP-0008/samples.csv, experiments/EXP-0008/seed-receipt.json, experiments/EXP-0008/figures/baseline-defect-exceedance.png, experiments/EXP-0008/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0008/inputs/data/clean/q3_thresholds.json, experiments/EXP-0008/inputs/data/processed/q1_grade_params.json, experiments/EXP-0008/inputs/src/q3_baseline.py, experiments/EXP-0008/inputs/src/q3_lib.py, experiments/EXP-0008/inputs/src/q_common.py, experiments/EXP-0008/inputs/src/target_columns.py
- experiment EXP-0009: 20 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0009/figures.json, experiments/EXP-0009/outputs.json, experiments/EXP-0009/run-seed-20261024.json, experiments/EXP-0009/run-seed-20261025.json, experiments/EXP-0009/run-seed-20261026.json, experiments/EXP-0009/samples.csv, experiments/EXP-0009/seed-receipt.json, experiments/EXP-0009/figures/ablation-comparison.png, experiments/EXP-0009/figures/defect-exceedance.png, experiments/EXP-0009/figures/energy-distance-by-style.png, experiments/EXP-0009/figures/profile-recovery.png, experiments/EXP-0009/figures/transfer-pareto.png, experiments/EXP-0009/figures/transfer-scenarios.png, experiments/EXP-0009/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0009/inputs/data/clean/q3_thresholds.json, experiments/EXP-0009/inputs/data/processed/q1_grade_params.json, experiments/EXP-0009/inputs/src/q3_generate.py, experiments/EXP-0009/inputs/src/q3_lib.py, experiments/EXP-0009/inputs/src/q_common.py, experiments/EXP-0009/inputs/src/target_columns.py
- experiment EXP-0010: 5 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0010/figures.json, experiments/EXP-0010/outputs.json, experiments/EXP-0010/seed-receipt.json, experiments/EXP-0010/figures/q1_fusion_component_mae.png, experiments/EXP-0010/figures/q1_fusion_weights.png
- experiment EXP-0011: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0011/bootstrap_pi.csv, experiments/EXP-0011/figures.json, experiments/EXP-0011/outputs.json, experiments/EXP-0011/seed-receipt.json, experiments/EXP-0011/sets.json, experiments/EXP-0011/sets_pi_first.json, experiments/EXP-0011/figures/q2_bootstrap_stability.png, experiments/EXP-0011/figures/q2_method_jaccard.png, experiments/EXP-0011/figures/q2_module_graph.png
- experiment EXP-0012 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0013: 20 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0013/env-seed.json, experiments/EXP-0013/figures.json, experiments/EXP-0013/outputs.json, experiments/EXP-0013/run-seed-20261024.json, experiments/EXP-0013/run-seed-20261025.json, experiments/EXP-0013/run-seed-20261026.json, experiments/EXP-0013/samples.csv, experiments/EXP-0013/figures/ablation-comparison.png, experiments/EXP-0013/figures/defect-exceedance.png, experiments/EXP-0013/figures/energy-distance-by-style.png, experiments/EXP-0013/figures/profile-recovery.png, experiments/EXP-0013/figures/transfer-pareto.png, experiments/EXP-0013/figures/transfer-scenarios.png, experiments/EXP-0013/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0013/inputs/data/clean/q3_thresholds.json, experiments/EXP-0013/inputs/data/processed/q1_grade_params.json, experiments/EXP-0013/inputs/src/q3_generate.py, experiments/EXP-0013/inputs/src/q3_lib.py, experiments/EXP-0013/inputs/src/q_common.py, experiments/EXP-0013/inputs/src/target_columns.py
- experiment EXP-0014: 14 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0014/env-seed.json, experiments/EXP-0014/figures.json, experiments/EXP-0014/outputs.json, experiments/EXP-0014/run-seed-20261024.json, experiments/EXP-0014/run-seed-20261025.json, experiments/EXP-0014/run-seed-20261026.json, experiments/EXP-0014/samples.csv, experiments/EXP-0014/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0014/inputs/data/clean/q3_thresholds.json, experiments/EXP-0014/inputs/data/processed/q1_grade_params.json, experiments/EXP-0014/inputs/src/q3_generate.py, experiments/EXP-0014/inputs/src/q3_lib.py, experiments/EXP-0014/inputs/src/q_common.py, experiments/EXP-0014/inputs/src/target_columns.py
- experiment EXP-0015: 13 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0015/env-seed.json, experiments/EXP-0015/figures.json, experiments/EXP-0015/outputs.json, experiments/EXP-0015/run-seed-20261024.json, experiments/EXP-0015/run-seed-20261025.json, experiments/EXP-0015/run-seed-20261026.json, experiments/EXP-0015/samples.csv, experiments/EXP-0015/figures/ablation-comparison.png, experiments/EXP-0015/figures/defect-exceedance.png, experiments/EXP-0015/figures/energy-distance-by-style.png, experiments/EXP-0015/figures/profile-recovery.png, experiments/EXP-0015/figures/transfer-pareto.png, experiments/EXP-0015/figures/transfer-scenarios.png
- experiment EXP-0016: 7 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0016/outputs.json, experiments/EXP-0016/seed-receipt.json, experiments/EXP-0016/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0016/inputs/src/q1_lib.py, experiments/EXP-0016/inputs/src/q1_robust.py, experiments/EXP-0016/inputs/src/q_common.py, experiments/EXP-0016/inputs/src/target_columns.py
- experiment EXP-0017: 7 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0017/outputs.json, experiments/EXP-0017/seed-receipt.json, experiments/EXP-0017/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0017/inputs/src/q1_lib.py, experiments/EXP-0017/inputs/src/q1_robust.py, experiments/EXP-0017/inputs/src/q_common.py, experiments/EXP-0017/inputs/src/target_columns.py
- experiment EXP-0018: 7 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0018/outputs.json, experiments/EXP-0018/seed-receipt.json, experiments/EXP-0018/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0018/inputs/src/q1_lib.py, experiments/EXP-0018/inputs/src/q1_robust.py, experiments/EXP-0018/inputs/src/q_common.py, experiments/EXP-0018/inputs/src/target_columns.py
- experiment EXP-0019: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0019/outputs.json, experiments/EXP-0019/seed-receipt.json, experiments/EXP-0019/sets.json, experiments/EXP-0019/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0019/inputs/src/q1_lib.py, experiments/EXP-0019/inputs/src/q2_lib.py, experiments/EXP-0019/inputs/src/q2_robust.py, experiments/EXP-0019/inputs/src/q_common.py, experiments/EXP-0019/inputs/src/target_columns.py
- experiment EXP-0020: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0020/outputs.json, experiments/EXP-0020/seed-receipt.json, experiments/EXP-0020/sets.json, experiments/EXP-0020/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0020/inputs/src/q1_lib.py, experiments/EXP-0020/inputs/src/q2_lib.py, experiments/EXP-0020/inputs/src/q2_robust.py, experiments/EXP-0020/inputs/src/q_common.py, experiments/EXP-0020/inputs/src/target_columns.py
- experiment EXP-0021: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0021/outputs.json, experiments/EXP-0021/seed-receipt.json, experiments/EXP-0021/sets.json, experiments/EXP-0021/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0021/inputs/src/q1_lib.py, experiments/EXP-0021/inputs/src/q2_lib.py, experiments/EXP-0021/inputs/src/q2_robust.py, experiments/EXP-0021/inputs/src/q_common.py, experiments/EXP-0021/inputs/src/target_columns.py
- experiment EXP-0022: 11 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0022/outputs.json, experiments/EXP-0022/samples.csv, experiments/EXP-0022/seed-receipt.json, experiments/EXP-0022/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0022/inputs/data/clean/q3_thresholds.json, experiments/EXP-0022/inputs/data/processed/q1_grade_params.json, experiments/EXP-0022/inputs/src/q3_generate.py, experiments/EXP-0022/inputs/src/q3_lib.py, experiments/EXP-0022/inputs/src/q3_robust.py, experiments/EXP-0022/inputs/src/q_common.py, experiments/EXP-0022/inputs/src/target_columns.py
- experiment EXP-0023: 11 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0023/outputs.json, experiments/EXP-0023/samples.csv, experiments/EXP-0023/seed-receipt.json, experiments/EXP-0023/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0023/inputs/data/clean/q3_thresholds.json, experiments/EXP-0023/inputs/data/processed/q1_grade_params.json, experiments/EXP-0023/inputs/src/q3_generate.py, experiments/EXP-0023/inputs/src/q3_lib.py, experiments/EXP-0023/inputs/src/q3_robust.py, experiments/EXP-0023/inputs/src/q_common.py, experiments/EXP-0023/inputs/src/target_columns.py
- experiment EXP-0024: 11 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0024/outputs.json, experiments/EXP-0024/samples.csv, experiments/EXP-0024/seed-receipt.json, experiments/EXP-0024/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0024/inputs/data/clean/q3_thresholds.json, experiments/EXP-0024/inputs/data/processed/q1_grade_params.json, experiments/EXP-0024/inputs/src/q3_generate.py, experiments/EXP-0024/inputs/src/q3_lib.py, experiments/EXP-0024/inputs/src/q3_robust.py, experiments/EXP-0024/inputs/src/q_common.py, experiments/EXP-0024/inputs/src/target_columns.py
- experiment EXP-0025: 10 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0025/figures.json, experiments/EXP-0025/outputs.json, experiments/EXP-0025/seed-receipt.json, experiments/EXP-0025/figures/q1_fusion_component_mae.png, experiments/EXP-0025/figures/q1_fusion_weights.png, experiments/EXP-0025/inputs/data/processed/q1_grade_params.json, experiments/EXP-0025/inputs/src/q1_fusion.py, experiments/EXP-0025/inputs/src/q1_lib.py, experiments/EXP-0025/inputs/src/q_common.py, experiments/EXP-0025/inputs/src/target_columns.py
- experiment EXP-0026: 11 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0026/grades_all.csv, experiments/EXP-0026/outputs.json, experiments/EXP-0026/predictions_all.csv, experiments/EXP-0026/seed-receipt.json, experiments/EXP-0026/inputs/data/processed/q1_grade_params.json, experiments/EXP-0026/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0026/inputs/src/q1_fusion.py, experiments/EXP-0026/inputs/src/q1_grade_all.py, experiments/EXP-0026/inputs/src/q1_lib.py, experiments/EXP-0026/inputs/src/q_common.py, experiments/EXP-0026/inputs/src/target_columns.py
- experiment EXP-0027 is queued and is not in the package
- experiment EXP-0028: 20 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0028/env-seed.json, experiments/EXP-0028/figures.json, experiments/EXP-0028/outputs.json, experiments/EXP-0028/run-seed-20261024.json, experiments/EXP-0028/run-seed-20261025.json, experiments/EXP-0028/run-seed-20261026.json, experiments/EXP-0028/samples.csv, experiments/EXP-0028/figures/ablation-comparison.png, experiments/EXP-0028/figures/defect-exceedance.png, experiments/EXP-0028/figures/energy-distance-by-style.png, experiments/EXP-0028/figures/profile-recovery.png, experiments/EXP-0028/figures/transfer-pareto.png, experiments/EXP-0028/figures/transfer-scenarios.png, experiments/EXP-0028/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0028/inputs/data/clean/q3_thresholds.json, experiments/EXP-0028/inputs/data/processed/q1_grade_params.json, experiments/EXP-0028/inputs/src/q3_generate.py, experiments/EXP-0028/inputs/src/q3_lib.py, experiments/EXP-0028/inputs/src/q_common.py, experiments/EXP-0028/inputs/src/target_columns.py
- experiment EXP-0029: 18 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0029/bootstrap_pi.csv, experiments/EXP-0029/figures.json, experiments/EXP-0029/outputs.json, experiments/EXP-0029/seed-receipt.json, experiments/EXP-0029/sets.json, experiments/EXP-0029/sets_pi_first.json, experiments/EXP-0029/figures/q2_bootstrap_stability.png, experiments/EXP-0029/figures/q2_method_jaccard.png, experiments/EXP-0029/figures/q2_module_graph.png, experiments/EXP-0029/inputs/data/clean/q2_chem_meta.json, experiments/EXP-0029/inputs/data/raw/imported/415709ac10f2f730-2.csv, experiments/EXP-0029/inputs/data/raw/imported/a55004fb0390299a-6.csv, experiments/EXP-0029/inputs/data/splits/SPLIT-0001/train.csv, experiments/EXP-0029/inputs/src/q1_lib.py, experiments/EXP-0029/inputs/src/q2_lib.py, experiments/EXP-0029/inputs/src/q2_topk.py, experiments/EXP-0029/inputs/src/q_common.py, experiments/EXP-0029/inputs/src/target_columns.py
- experiment EXP-0030: 9 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0030/bootstrap_pi.csv, experiments/EXP-0030/figures.json, experiments/EXP-0030/outputs.json, experiments/EXP-0030/seed-receipt.json, experiments/EXP-0030/sets.json, experiments/EXP-0030/sets_pi_first.json, experiments/EXP-0030/figures/q2_bootstrap_stability.png, experiments/EXP-0030/figures/q2_method_jaccard.png, experiments/EXP-0030/figures/q2_module_graph.png
- experiment EXP-0031: 13 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0031/env-seed.json, experiments/EXP-0031/figures.json, experiments/EXP-0031/outputs.json, experiments/EXP-0031/run-seed-20261024.json, experiments/EXP-0031/run-seed-20261025.json, experiments/EXP-0031/run-seed-20261026.json, experiments/EXP-0031/samples.csv, experiments/EXP-0031/figures/ablation-comparison.png, experiments/EXP-0031/figures/defect-exceedance.png, experiments/EXP-0031/figures/energy-distance-by-style.png, experiments/EXP-0031/figures/profile-recovery.png, experiments/EXP-0031/figures/transfer-pareto.png, experiments/EXP-0031/figures/transfer-scenarios.png
- experiment EXP-0032: 20 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0032/env-seed.json, experiments/EXP-0032/figures.json, experiments/EXP-0032/outputs.json, experiments/EXP-0032/run-seed-20261024.json, experiments/EXP-0032/run-seed-20261025.json, experiments/EXP-0032/run-seed-20261026.json, experiments/EXP-0032/samples.csv, experiments/EXP-0032/figures/ablation-comparison.png, experiments/EXP-0032/figures/defect-exceedance.png, experiments/EXP-0032/figures/energy-distance-by-style.png, experiments/EXP-0032/figures/profile-recovery.png, experiments/EXP-0032/figures/transfer-pareto.png, experiments/EXP-0032/figures/transfer-scenarios.png, experiments/EXP-0032/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0032/inputs/data/clean/q3_thresholds.json, experiments/EXP-0032/inputs/data/processed/q1_grade_params.json, experiments/EXP-0032/inputs/src/q3_generate.py, experiments/EXP-0032/inputs/src/q3_lib.py, experiments/EXP-0032/inputs/src/q_common.py, experiments/EXP-0032/inputs/src/target_columns.py
- experiment EXP-0033: 20 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0033/env-seed.json, experiments/EXP-0033/figures.json, experiments/EXP-0033/outputs.json, experiments/EXP-0033/run-seed-20261024.json, experiments/EXP-0033/run-seed-20261025.json, experiments/EXP-0033/run-seed-20261026.json, experiments/EXP-0033/samples.csv, experiments/EXP-0033/figures/ablation-comparison.png, experiments/EXP-0033/figures/defect-exceedance.png, experiments/EXP-0033/figures/energy-distance-by-style.png, experiments/EXP-0033/figures/profile-recovery.png, experiments/EXP-0033/figures/transfer-pareto.png, experiments/EXP-0033/figures/transfer-scenarios.png, experiments/EXP-0033/inputs/data/clean/q3_style_protocol.json, experiments/EXP-0033/inputs/data/clean/q3_thresholds.json, experiments/EXP-0033/inputs/data/processed/q1_grade_params.json, experiments/EXP-0033/inputs/src/q3_generate.py, experiments/EXP-0033/inputs/src/q3_lib.py, experiments/EXP-0033/inputs/src/q_common.py, experiments/EXP-0033/inputs/src/target_columns.py
- experiment EXP-0034: 13 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0034/env-seed.json, experiments/EXP-0034/figures.json, experiments/EXP-0034/outputs.json, experiments/EXP-0034/run-seed-20261024.json, experiments/EXP-0034/run-seed-20261025.json, experiments/EXP-0034/run-seed-20261026.json, experiments/EXP-0034/samples.csv, experiments/EXP-0034/figures/ablation-comparison.png, experiments/EXP-0034/figures/defect-exceedance.png, experiments/EXP-0034/figures/energy-distance-by-style.png, experiments/EXP-0034/figures/profile-recovery.png, experiments/EXP-0034/figures/transfer-pareto.png, experiments/EXP-0034/figures/transfer-scenarios.png
- experiment EXP-0035: 6 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0035/figures.json, experiments/EXP-0035/outputs.json, experiments/EXP-0035/seed-receipt.json, experiments/EXP-0035/inputs/experiments/EXP-0003/outputs.json, experiments/EXP-0035/inputs/experiments/EXP-0029/outputs.json, experiments/EXP-0035/inputs/src/ablation_summary.py
- experiment EXP-0036: 3 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0036/outputs.json, experiments/EXP-0036/seed-receipt.json, experiments/EXP-0036/inputs/src/headline_audit.py

## 七、诚实边界（本包不能保证的部分）

1. **不生成 PDF/TeX**：本包保证 md 交付。`contest.yaml` 声明了 tex/pdf 而实际没有产出时，交付检查会**判失败**，
   不会把“应该能生成”写成“已就绪”。
2. **随机性**：随机过程按登记的 seed 复跑；未固定的差异以 `evaluation.reproductionTolerance` 比较，超出即视为不可复现。
3. **原始数据不随包分发**：原始附件只以 sha256 记录，需要从原始来源重新获取。
4. **环境随本地而定**：解释器、依赖版本、时间戳不随包分发；换环境后请重新探测解释器并重跑实验。
5. **比赛要求只核对声明的部分**：页数/匿名/命名/AI 说明只在 `contest.yaml` 的 `delivery.contest` 声明后才核对，
   且只有能机械核对的部分被核对（例如页数需要 PDF）；其余需人工确认。

## 八、包内文件清单

- report/paper.md
- report/paper.pdf
- report/paper.tex
- report/rendered.md
- report/rendered.pandoc.md
- report/rendered.refs.json
- figures/FIG-0001-q1_fusion_component_mae.png
- experiments/EXP-0004/figures/q1_fusion_component_mae.png
- figures/FIG-0002-q1_fusion_weights.png
- experiments/EXP-0004/figures/q1_fusion_weights.png
- figures/FIG-0003-q1_cv_mae_grid.png
- experiments/EXP-0003/figures/q1_cv_mae_grid.png
- figures/FIG-0004-q1_per_target_improvement.png
- experiments/EXP-0003/figures/q1_per_target_improvement.png
- figures/FIG-0005-q1_grade_confusion.png
- experiments/EXP-0003/figures/q1_grade_confusion.png
- figures/FIG-0006-q2_bootstrap_stability.png
- experiments/EXP-0006/figures/q2_bootstrap_stability.png
- figures/FIG-0007-q2_method_jaccard.png
- experiments/EXP-0006/figures/q2_method_jaccard.png
- figures/FIG-0008-q2_module_graph.png
- experiments/EXP-0006/figures/q2_module_graph.png
- figures/FIG-0009-energy-distance-by-style.png
- experiments/EXP-0014/figures/energy-distance-by-style.png
- figures/FIG-0010-defect-exceedance.png
- experiments/EXP-0014/figures/defect-exceedance.png
- figures/FIG-0011-transfer-scenarios.png
- experiments/EXP-0014/figures/transfer-scenarios.png
- figures/FIG-0012-transfer-pareto.png
- experiments/EXP-0014/figures/transfer-pareto.png
- figures/FIG-0013-ablation-comparison.png
- experiments/EXP-0014/figures/ablation-comparison.png
- figures/FIG-0014-profile-recovery.png
- experiments/EXP-0014/figures/profile-recovery.png
- figures/FIG-0015-baseline-energy-distance.png
- experiments/EXP-0008/figures/baseline-energy-distance.png
- figures/FIG-0016-q1_component_mae.png
- figures/q1_component_mae.png
- figures/FIG-0017-q1_fusion_weights.png
- figures/q1_fusion_weights.png
- figures/FIG-0018-q1_per_target.png
- figures/q1_per_target.png
- figures/FIG-0019-q1_cv_grid.png
- figures/q1_cv_grid.png
- figures/FIG-0020-q1_grades_all.png
- figures/q1_grades_all.png
- figures/FIG-0021-q2_bootstrap_pi.png
- figures/q2_bootstrap_pi.png
- figures/FIG-0022-q2_method_jaccard.png
- figures/q2_method_jaccard.png
- figures/FIG-0023-q2_modules.png
- figures/q2_modules.png
- figures/FIG-0024-q3_energy_by_style.png
- figures/q3_energy_by_style.png
- figures/history/FIG-0025-FIG-0025-q3_defect_exceedance.png
- figures/FIG-0026-q3_transfer_scenarios.png
- figures/q3_transfer_scenarios.png
- figures/history/FIG-0027-FIG-0027-q3_pareto.png
- figures/FIG-0028-q3_profile.png
- figures/q3_profile.png
- figures/FIG-0029-ablation-summary.png
- experiments/EXP-0035/figures/ablation-summary.png
- figures/FIG-0030-q3_defect_exceedance.png
- figures/q3_defect_exceedance.png
- figures/FIG-0031-q3_pareto.png
- figures/q3_pareto.png
- figures/figures.json
- src/__pycache__/q1_candidate.cpython-312.pyc
- src/__pycache__/q1_fusion.cpython-312.pyc
- src/__pycache__/q1_lib.cpython-312.pyc
- src/__pycache__/q1_robust.cpython-312.pyc
- src/__pycache__/q2_baseline.cpython-312.pyc
- src/__pycache__/q2_lib.cpython-312.pyc
- src/__pycache__/q2_robust.cpython-312.pyc
- src/__pycache__/q2_topk.cpython-312.pyc
- src/__pycache__/q3_generate.cpython-312.pyc
- src/__pycache__/q3_lib.cpython-312.pyc
- src/__pycache__/q_common.cpython-312.pyc
- src/__pycache__/target_columns.cpython-312.pyc
- src/__pycache__/target_columns.cpython-314.pyc
- src/ablation_summary.py
- src/build_paper.py
- src/headline_audit.py
- src/make_paper_figures.py
- src/prepare_base.py
- src/prepare_q1mapped.py
- src/prepare_q3.py
- src/q1_baseline.py
- src/q1_candidate.py
- src/q1_fusion.py
- src/q1_grade_all.py
- src/q1_lib.py
- src/q1_robust.py
- src/q2_baseline.py
- src/q2_lib.py
- src/q2_robust.py
- src/q2_topk.py
- src/q3_baseline.py
- src/q3_generate.py
- src/q3_lib.py
- src/q3_robust.py
- src/q_common.py
- src/target_columns.py
- data/clean/q2_raw.csv
- data/raw/imported/419849227a02e0c7-1.csv
- data/clean/q1_mapped.csv
- data/clean/q3.csv
- data/splits/SPLIT-0001/assignment.csv
- data/splits/SPLIT-0001/train.csv
- data/splits/SPLIT-0001/test.csv
- data/splits/SPLIT-0002/assignment.csv
- data/splits/SPLIT-0002/train.csv
- data/splits/SPLIT-0002/test.csv
- experiments/EXP-0001/metrics.json
- experiments/EXP-0001/predictions.csv
- experiments/EXP-0001/result.json
- experiments/EXP-0002/metrics.json
- experiments/EXP-0002/result.json
- experiments/EXP-0003/metrics.json
- experiments/EXP-0003/predictions.csv
- experiments/EXP-0003/result.json
- experiments/EXP-0004/metrics.json
- experiments/EXP-0004/predictions.csv
- experiments/EXP-0004/result.json
- experiments/EXP-0005/metrics.json
- experiments/EXP-0005/result.json
- experiments/EXP-0006/metrics.json
- experiments/EXP-0006/result.json
- experiments/EXP-0007/metrics.json
- experiments/EXP-0007/result.json
- experiments/EXP-0008/metrics.json
- experiments/EXP-0008/result.json
- experiments/EXP-0009/metrics.json
- experiments/EXP-0009/result.json
- experiments/EXP-0010/metrics.json
- experiments/EXP-0010/predictions.csv
- experiments/EXP-0010/result.json
- experiments/EXP-0010/q1_fusion.py
- experiments/EXP-0011/metrics.json
- experiments/EXP-0011/result.json
- experiments/EXP-0011/q2_topk.py
- experiments/EXP-0013/metrics.json
- experiments/EXP-0013/result.json
- experiments/EXP-0014/metrics.json
- experiments/EXP-0014/result.json
- experiments/EXP-0015/metrics.json
- experiments/EXP-0015/result.json
- experiments/EXP-0015/q3_generate.py
- experiments/EXP-0016/metrics.json
- experiments/EXP-0016/result.json
- experiments/EXP-0017/metrics.json
- experiments/EXP-0017/result.json
- experiments/EXP-0018/metrics.json
- experiments/EXP-0018/result.json
- experiments/EXP-0019/metrics.json
- experiments/EXP-0019/result.json
- experiments/EXP-0020/metrics.json
- experiments/EXP-0020/result.json
- experiments/EXP-0021/metrics.json
- experiments/EXP-0021/result.json
- experiments/EXP-0022/metrics.json
- experiments/EXP-0022/result.json
- experiments/EXP-0023/metrics.json
- experiments/EXP-0023/result.json
- experiments/EXP-0024/metrics.json
- experiments/EXP-0024/result.json
- experiments/EXP-0025/metrics.json
- experiments/EXP-0025/predictions.csv
- experiments/EXP-0025/result.json
- experiments/EXP-0026/metrics.json
- experiments/EXP-0026/result.json
- experiments/EXP-0028/metrics.json
- experiments/EXP-0028/result.json
- experiments/EXP-0029/metrics.json
- experiments/EXP-0029/result.json
- experiments/EXP-0030/metrics.json
- experiments/EXP-0030/result.json
- experiments/EXP-0030/q2_topk.py
- experiments/EXP-0031/metrics.json
- experiments/EXP-0031/result.json
- experiments/EXP-0031/q3_generate.py
- experiments/EXP-0032/metrics.json
- experiments/EXP-0032/result.json
- experiments/EXP-0033/metrics.json
- experiments/EXP-0033/result.json
- experiments/EXP-0034/metrics.json
- experiments/EXP-0034/result.json
- experiments/EXP-0034/q3_generate.py
- experiments/EXP-0035/metrics.json
- experiments/EXP-0035/result.json
- experiments/EXP-0036/metrics.json
- experiments/EXP-0036/result.json
- contest.yaml
- ledger-summary.json
- delivery-status.json
