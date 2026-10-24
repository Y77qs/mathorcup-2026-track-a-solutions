# 复现说明 — mathorcup-2026-a（交付目录 delivery/practical-final-20261024）

> 本文件由 `modeling_deliver {action:"package"}` 从项目台账生成：
> 台账 revision 781，contest.yaml sha256 a89e9e2f2caaaddd7498c20312f25e8ba783c9509515b3fcd942522ef7c339eb，生成时间 2026-10-24T02:48:24.748Z，
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
delivery/practical-final-20261024/
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
tar -xzf delivery/practical-final-20261024.tar.gz
cd delivery/practical-final-20261024
shasum -a 256 -c SHA256SUMS
```

数据集与它们的 hash：

| 数据集 | 文件 | sha256(前16) | 目标列 |
|---|---|---|---|
| DATA-0001 | data/clean/features_log.csv | 344740ebf6297ec8 | — |
| DATA-0002 | data/clean/model_table.csv | c5ef4195703f4aa3 | — |

划分方式与划分文件的 hash：

| 划分 | 数据集 | 方法 | train sha256 | test sha256 | assignment 文件 |
|---|---|---|---|---|---|
| SPLIT-0001 | DATA-0001 | random-holdout | b5d41512d66e | 32a3262ff63f | data/splits/SPLIT-0001/assignment.csv |
| SPLIT-0002 | DATA-0002 | random-holdout | dbe66088d43d | 56f3f16200f5 | data/splits/SPLIT-0002/assignment.csv |

> 原始附件不在包内；按下面的 sha256 从原始来源重新获取，再走同一清洗脚本：

| 原始文件 | 来源名 | 项目内路径 | sha256(前16) | 角色 |
|---|---|---|---|---|
| RAW-41984922 | 1.csv | data/raw/imported/1.csv | 419849227a02e0c7 | features-compounds |
| RAW-415709ac | 2.csv | data/raw/imported/2.csv | 415709ac10f2f730 | corr-compound-spearman |
| RAW-fe4dcabd | 3.xlsx | data/raw/imported/3.xlsx | fe4dcabd48431e6d | scorecard-schema-0to6 |
| RAW-43a7b386 | 4.csv | data/raw/imported/4.csv | 43a7b38682ed81ce | sensory-targets |
| RAW-c512eed1 | 5.csv | data/raw/imported/5.csv | c512eed108de6f98 | corr-sensory |
| RAW-a55004fb | 6.csv | data/raw/imported/6.csv | a55004fb0390299a | corr-chemical-sensory |
| RAW-2083138d | 7.csv | data/raw/imported/7.csv | 2083138df46640e2 | aux-ratebeer-external-only |
| RAW-f2316766 | 8.xlsx | data/raw/imported/8.xlsx | f2316766792111d9 | thresholds-names-calibrated-reference |
| RAW-40813e27 | 数据说明.txt | data/raw/imported/数据说明.txt | 40813e273e081ae0 | readme |
| RAW-494025cf | 2026年MathorCup大数据挑战赛-赛道A初赛.pdf | data/raw/imported/2026年MathorCup大数据挑战赛-赛道A初赛.pdf | 494025cf76c5d47a | statement |

## 四、复跑实验

在包根目录执行下表命令。若脚本依赖“实验目录内的相对路径”，先 `cd` 到该实验目录再执行同一行命令。

> **依赖 `modeling_contract` 的脚本**：该模块随整合包发布（`<已安装 preset>/packs/modeling-contest/python/`），
> 不在项目目录里。手动复跑时先把它加入 `PYTHONPATH`，例如：
> `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/path/to/preset/packs/modeling-contest/python python src/model.py`
> （`PYTHONDONTWRITEBYTECODE=1` 避免把 `__pycache__` 写进 preset 安装目录——那会让包名册/审计把构建产物当成未登记文件）。
> 通过 `modeling_experiment {action:"run"}` 复跑时 runner 会自动设置，无需手工处理。
> 若脚本只读取环境变量（`MODELING_TRAIN_FILE` 等），请按 `contest.yaml` 的划分文件自行导出。

| 实验 | 小题 | 模型 | 状态 | r2 | 复跑命令（在包根执行） |
|---|---|---|---|---|---|
| EXP-0003 | Q2 | MODEL-0003 | succeeded | （无 r2） | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0007 | Q1 | MODEL-0007 | succeeded | （无 r2） | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0012 | Q1 | MODEL-0012 | succeeded | -0.024635435726754987 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0013 | Q1 | MODEL-0012 | succeeded | -0.024635435726754987 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0015 | Q1 | MODEL-0014 | succeeded | -0.014456198175549995 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0019 | Q3 | MODEL-0017 | succeeded | 0.423009420982131 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0021 | Q1 | MODEL-0014 | succeeded | -0.014456198175549995 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0022 | Q3 | MODEL-0019 | succeeded | 0.857516 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0023 | Q3 | MODEL-0020 | succeeded | 0.805177 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0024 | Q3 | MODEL-0021 | succeeded | 0.4129395519057989 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0025 | Q1 | MODEL-0022 | succeeded | 0.04819587620111854 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0026 | Q3 | MODEL-0021 | succeeded | 0.4129395519057989 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0027 | Q3 | MODEL-0021 | succeeded | 0.3778958797264049 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0028 | Q3 | MODEL-0021 | succeeded | 0.3778958797264049 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0029 | Q1 | MODEL-0023 | succeeded | 0.009210149437171689 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0030 | Q3 | MODEL-0024 | succeeded | 0.3778958797264049 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0034 | Q1 | MODEL-0022 | succeeded | 0.04819587620111854 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0035 | Q2 | MODEL-0028 | succeeded | 0.6559999999999999 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0036 | Q3 | MODEL-0029 | succeeded | 0.41203475610256013 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0038 | Q1 | MODEL-0030 | succeeded | 0.02138714231702843 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0039 | Q2 | MODEL-0031 | succeeded | （无 r2） | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0041 | Q2 | MODEL-0032 | succeeded | 0.18666666666666668 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0047 | Q2 | MODEL-0035 | succeeded | （无 r2） | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0050 | Q1 | MODEL-0038 | succeeded | -0.000379042295657106 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |
| EXP-0051 | Q1 | MODEL-0039 | succeeded | 0.059925073556855835 | `不可精确复现：缺完整冻结依赖；以新实验重建，不能补写历史通过` |

> 复跑关系（哪个实验是谁的 `rerunOf`）见 `ledger-summary.json` 的 `experiments[]`。
> 新跑出来的数是**新实验**的数，不是旧实验的数；不要在包内覆盖旧结果。

## 五、复核结论与验证

| 校验 | 实验 | 类型 | 结果 | 新鲜度 |
|---|---|---|---|---|
| VAL-0001 | EXP-0003 | split-integrity | passed | fresh |
| VAL-0002 | EXP-0003 | leakage | passed | fresh |
| VAL-0003 | EXP-0007 | leakage | passed | fresh |
| VAL-0004 | EXP-0007 | split-integrity | passed | fresh |
| VAL-0005 | EXP-0012 | independent-rerun | passed | fresh |
| VAL-0007 | EXP-0015 | holdout-metrics | passed | fresh |
| VAL-0008 | EXP-0015 | split-integrity | passed | fresh |
| VAL-0009 | EXP-0015 | leakage | passed | fresh |
| VAL-0010 | EXP-0015 | independent-rerun | passed | fresh |
| VAL-0011 | EXP-0022 | leakage | passed | fresh |
| VAL-0012 | EXP-0024 | independent-rerun | FAILED | fresh |
| VAL-0013 | EXP-0025 | holdout-metrics | passed | fresh |
| VAL-0014 | EXP-0025 | baseline-compare | passed | fresh |
| VAL-0015 | EXP-0025 | leakage | passed | fresh |
| VAL-0016 | EXP-0025 | split-integrity | passed | fresh |
| VAL-0017 | EXP-0025 | independent-rerun | passed | fresh |
| VAL-0018 | EXP-0035 | leakage | passed | fresh |
| VAL-0019 | EXP-0035 | split-integrity | passed | fresh |
| VAL-0020 | EXP-0025 | leakage | passed | fresh |
| VAL-0021 | EXP-0025 | split-integrity | passed | fresh |
| VAL-0022 | EXP-0025 | holdout-metrics | passed | fresh |
| VAL-0023 | EXP-0025 | baseline-compare | passed | fresh |
| VAL-0024 | EXP-0029 | leakage | passed | fresh |
| VAL-0025 | EXP-0029 | split-integrity | passed | fresh |
| VAL-0026 | EXP-0029 | holdout-metrics | passed | fresh |
| VAL-0027 | EXP-0029 | baseline-compare | passed | fresh |
| VAL-0028 | EXP-0041 | leakage | passed | fresh |
| VAL-0029 | EXP-0041 | split-integrity | passed | fresh |

| 论断 | 小题 | 状态 | 陈述(截断) |
|---|---|---|---|
| CLAIM-0001 | Q1 | active | 三路等权融合（PLS-5 + ExtraTrees-150 + RandomForest-150，折内中位数插补+1%/ |
| CLAIM-0002 | Q1 | active | dms 与 diacetyl 两维的感官评分与其对应缺陷化合物的气味活度值几乎无单调关联（主分割物理锚定 Spearma |
| CLAIM-0003 | Q2 | active | 以 2.csv 的 Spearman 秩相关按 |ρ|≥0.30 阈值化（BH-FDR 等效阈值 0.1439）得到 2 |
| CLAIM-0004 | Q3 | active | 风格条件低秩高斯（PCA k=15 + 条件均值锚定 + 共享收缩协方差）生成的化合物谱满足非负与训练支撑约束，但其分布 |
| CLAIM-0005 | Q2 | active | 四种建模方法给出的每维 Top-3 高度不一致：跨方法 Jaccard 均值仅 0.1623（中位 0.1167），50 |
| CLAIM-0006 | Q2 | active | 附件 2.csv、5.csv、6.csv **不是独立的外部先验**，而是同 250 个样本的相关系数重算：2.csv  |
| CLAIM-0007 | Q1 | active | Q1 锁定的四路等权融合模型（PLS+ExtraTrees+RandomForest+逐维 HGB，折内预处理）在 SP |
| CLAIM-0008 | Q1 | active | 并非所有感官维度都能由 231 个化合物特征推断：holdout 上 A_hops_tropical（R²=−0.341 |
| CLAIM-0009 | Q1 | active | z→0–6 分级只能作为标定口径的产物报告，不能作为准确性指标：同一批 holdout 预测在四套口径下 QWK 分别为 |
| CLAIM-0010 | Q2 | active | 在已完成登记的选择实验（EXP-0041，四方法 + Borda 聚合）中，跨方法 Top-3 的 Jaccard 均值 |
| CLAIM-0011 | Q3 | active | 风格条件低秩高斯（PCA k=15 + 条件均值锚定 + 共享收缩协方差）的归一化能量距离 ED/D_ref = 0.1 |

| 图 | 标题 | 文件 | sha256(前16) |
|---|---|---|---|
| FIG-0001 | Q1 逐维留出集决定系数（上：EXP-0025 三路等权融合，50 维均值 0.2206，43/50 维为正；下：EXP-0015 常数基线，50 维均值 −0.0246）。横轴为 50 个感官维度（英文列名），纵轴为留出 50 样本上的 R²。样本量 n_test=50，一次性评估，未做分层（缺 West Flanders ale）。 | figures/q1_per_dim_r2.png | 6dee43f52ad0f6b2 |
| FIG-0002 | Q2 四种方法之间每维 Top-3 的 Jaccard 系数均值（M1 多变量岭/弹性网系数、M2 随机森林置换重要性、M3 图 lasso 偏相关、M4 单变量 Spearman+BH-FDR）。非对角均值约 0.20、最大 0.50，说明 Top-3 的跨方法一致性很低。注意：该图数据来自 Q2 选择阶段的开发运行（outputs/q2/method_jaccard.csv），对应 EXP 尚在登记中。 | figures/q2_method_agreement.png | 6f7c0c607f2077c7 |
| FIG-0003 | Q2 十个代表性感官维度的共识 Top-3 化合物（四方法归一化分数的均值排序，每维取前 3）。颜色条为共识强度（跨方法平均归一化重要度）。用于展示"共识候选"而非确定性关键因素；须与跨方法 Jaccard≈0.16 的不一致性一并阅读。 | figures/q2_top3_heatmap.png | ee9e9b73e140eac1 |
| FIG-0004 | Q3 生成谱与真实同风格谱在 PCA 前两主成分上的分布（Tripel/Kriek/Lambic 三风格，各 200 个生成样本）。用于直观检查生成分布是否落在同风格真值云内；定量判据为归一化能量距离 ED/D_ref（主模型 0.1264，基线 0.1262，两者几乎相同）。 | figures/q3_spectra_pca.png | 66c089090a8358e0 |
| FIG-0005 | Q3 逐风格保真度双栏图：左栏为"生成样本被判为目标风格"的命中率（标注 SATURATED——该指标在条件均值锚定后饱和，对生成质量无区分度）；右栏为逐风格能量距离（越低越接近真实分布）。小样本风格（Faro n=2、Scotch n=5）标为不可下结论。 | figures/q3_style_fidelity.png | 9db96713845e432b |
| FIG-0006 | Q3 五类缺陷化合物在生成侧与真实同风格侧的越阈率对比（OAV>1 的比例）。DMS/Diacetyl/4VG 用 8.xlsx 绝对阈值；trans-2-nonenal 与 Stale hops 无阈值，仅以浓度不增作单调约束（图中标注）。可见生成侧 DMS 与 Diacetyl 的越阈率系统性高于真实同风格，属必须披露的分布偏移。 | figures/q3_defect_oav.png | e03e43b3a2fb0f1b |
| FIG-0007 | 图 Q1-1 模型族比较：六个候选族 + 四路等权融合的训练内 OOF R²（50 维均值，5 折×3 重复=15 折，误差棒为 3 次重复间标准差）。常数基线 R²≈0 作下界；融合 15/15 折一致优于最好的单模 ExtraTrees（配对 t=7.1）。 | figures/q1_model_comparison.png | 5fb1628d4099dece |
| FIG-0008 | 图 Q1-2 逐维 holdout R²（50 维，SPLIT-0002 test n=50）：颜色区分 Aroma 15 维（蓝）/ Flavour 15 维（青）/ 口感-缺陷-总体 20 维（品红）。约 1/4 维为负，说明这些维度在 50 个留出样本上不可预测，不得宣称"全部感官维度可推断"。 | figures/q1_per_dim_r2.png | 17123fbcdb43e159 |
| FIG-0009 | 图 Q1-3 分级混淆（holdout 50 样本×50 维）：左 P1 物理锚定（QWK 0.313）、右 P2 极差（QWK 0.493）。参照等级 = 同一条标定规则作用于 4.csv 连续值；真实 0–6 等级未知，故此图只表示「标定口径下的一致性」，不是分级准确率。 | figures/q1_confusion.png | 4f579d79e45f1710 |
| FIG-0010 | 图 Q1-4 按风格分层的训练内 OOF R²（每风格内 50 维 R² 均值，n=200）。Faro/Brut/Scotch 等小类 n≤3，数值只作描述，不构成风格级结论。 | figures/q1_error_by_style.png | 1ed3506d9ce09dce |
| FIG-0011 | 图 Q1-5 标定敏感性：左为 holdout 上 P1（物理锚定）与 P2（极差）的预测等级分布，右为四套口径的 QWK。真实 0–6 等级未知，QWK 只作标定口径敏感性，不作准确性背书。 | figures/q1_calibration.png | a7ea8765cfec4674 |
| FIG-0012 | 图 Q1-6 全 250 样本×50 维 0–6 分级图（P1 物理锚定口径），样本按 tasting_category_fine 排序。训练 200 行为 OOF 预测、test 50 行为锁定模型预测，两段严格分开。 | figures/q1_grade_map.png | 759b1335f758072f |
| FIG-0013 | Q1 逐维留出集 R²（EXP-0025 三路等权融合），50 维均值 0.2206，43/50 维为正；约 1/4 维为负，说明这些维度在 50 个留出样本上不可预测，不得宣称"全部感官维度可推断"。对照常数基线（EXP-0015）50 维均值 −0.0246。n_test=50，一次性评估。 | figures/q1_per_dim_r2_final.png | 17123fbcdb43e159 |
| FIG-0014 | Q1 分级混淆（留出 50 样本 × 50 维）：左 P1 物理锚定（QWK 0.313）、右 P2 极差（QWK 0.493）。参照等级 = 同一条标定规则作用于 4.csv 连续值；真实 0–6 等级未知，故此图只表示"标定口径下的一致性"，不是分级准确率。 | figures/q1_confusion_final.png | 4f579d79e45f1710 |
| FIG-0015 | Q1 标定敏感性：左为留出集上 P1（物理锚定）与 P2（极差）的预测等级分布，右为四套口径的 QWK。真实 0–6 等级未知，QWK 仅作标定口径敏感性，不作准确性背书。 | figures/q1_calibration_final.png | a7ea8765cfec4674 |
| FIG-0016 | EXP-0029 all fifty dimensions: engineering post-hoc audit, not historical rerun | figures/practical-q1-audit.png | 51cab98d09c922b5 |

> 论文里的每个数字都由占位符从台账渲染而来，逐条解析记录在 `report/rendered.refs.json`；
> 每条结论的证据引用在 `ledger-summary.json` 的 `claims[]` 里。

## 六、交付检查读数

passed 41 / failed 26 / skipped 3

已知限制与警告：

- contest.yaml changed since the project ledger was created: the protocol in force may differ from the one the recorded results were produced under
- figure FIG-0001 was not packaged: figure FIG-0001 changed since it was registered: /Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/competitions/mathorcup2026-a-practical-repair/figures/q1_per_dim_r2.png sha256 17123fbcdb43e159dc62c24c9061edae3c3bd044cc6987481e5f53918f74400e != recorded 6dee43f52ad0f6b2698e89c5d1decf0e4d59cc3be016231b46b3d61e90d38cba
- experiment EXP-0001 is queued and is not in the package
- experiment EXP-0002 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0003: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0003/outputs.json
- experiment EXP-0004 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0005 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0006 is queued and is not in the package
- experiment EXP-0007: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0007/outputs.json, experiments/EXP-0007/predictions_overall.csv
- experiment EXP-0008 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0009 is queued and is not in the package
- experiment EXP-0010 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0011 is queued and is not in the package
- experiment EXP-0012: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0012/outputs.json, experiments/EXP-0012/predictions_long.csv
- experiment EXP-0013: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0013/outputs.json, experiments/EXP-0013/predictions_long.csv
- experiment EXP-0014 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0015: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0015/outputs.json, experiments/EXP-0015/predictions_long.csv
- experiment EXP-0016 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0017 is cancelled: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0018 is queued and is not in the package
- experiment EXP-0019: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0019/outputs.json
- experiment EXP-0020 is queued and is not in the package
- experiment EXP-0021: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0021/outputs.json, experiments/EXP-0021/predictions_long.csv
- experiment EXP-0022: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0022/outputs.json
- experiment EXP-0023: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0023/outputs.json
- experiment EXP-0024: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0024/outputs.json
- experiment EXP-0025: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0025/outputs.json, experiments/EXP-0025/predictions_long.csv
- experiment EXP-0026: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0026/outputs.json
- experiment EXP-0027: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0027/outputs.json
- experiment EXP-0028: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0028/outputs.json
- experiment EXP-0029: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0029/outputs.json, experiments/EXP-0029/predictions_long.csv
- experiment EXP-0030: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0030/outputs.json
- experiment EXP-0031 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0032 is queued and is not in the package
- experiment EXP-0033 is queued and is not in the package
- experiment EXP-0034: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0034/outputs.json, experiments/EXP-0034/predictions_long.csv
- experiment EXP-0035: 3 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0035/baseline_m4_frequency.csv, experiments/EXP-0035/baseline_m4_top3.csv, experiments/EXP-0035/outputs.json
- experiment EXP-0036: 1 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0036/outputs.json
- experiment EXP-0037 is queued and is not in the package
- experiment EXP-0038: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0038/outputs.json, experiments/EXP-0038/predictions_long.csv
- experiment EXP-0039: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0039/outputs.json, experiments/EXP-0039/univariate_fdr.csv
- experiment EXP-0040 is queued and is not in the package
- experiment EXP-0041: 5 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0041/confidence_grading.csv, experiments/EXP-0041/importance_matrix.csv, experiments/EXP-0041/method_jaccard.csv, experiments/EXP-0041/method_top3.csv, experiments/EXP-0041/outputs.json
- experiment EXP-0042 is timed-out: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0043 is queued and is not in the package
- experiment EXP-0044 is queued and is not in the package
- experiment EXP-0045 is queued and is not in the package
- experiment EXP-0046 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0047: 2 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0047/bootstrap_top3.csv, experiments/EXP-0047/outputs.json
- experiment EXP-0048 is interrupted: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0049 is failed: its numbers are not in the package (a failed run is not a result)
- experiment EXP-0050: 4 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0050/outputs.json, experiments/EXP-0050/predictions_oof.csv, experiments/EXP-0050/seed-receipt.json, experiments/EXP-0050/inputs/src/q1_trainonly.py
- experiment EXP-0051: 4 output file(s) are not packaged (only metrics/predictions/result + registered figure files are): experiments/EXP-0051/outputs.json, experiments/EXP-0051/predictions_oof.csv, experiments/EXP-0051/seed-receipt.json, experiments/EXP-0051/inputs/src/q1_trainonly.py

## 七、诚实边界（本包不能保证的部分）

1. **不生成 PDF/TeX**：本包保证 md 交付。`contest.yaml` 声明了 tex/pdf 而实际没有产出时，交付检查会**判失败**，
   不会把“应该能生成”写成“已就绪”。
2. **随机性**：随机过程按登记的 seed 复跑；未固定的差异以 `evaluation.reproductionTolerance` 比较，超出即视为不可复现。
3. **原始数据不随包分发**：原始附件只以 sha256 记录，需要从原始来源重新获取。
4. **环境随本地而定**：解释器、依赖版本、时间戳不随包分发；换环境后请重新探测解释器并重跑实验。
5. **比赛要求只核对声明的部分**：页数/匿名/命名/AI 说明只在 `contest.yaml` 的 `delivery.contest` 声明后才核对，
   且只有能机械核对的部分被核对（例如页数需要 PDF）；其余需人工确认。

## 八、包内文件清单

- report/REPAIR-SNAPSHOT.json
- report/analysis/practical-q1-audit/metrics.json
- report/analysis/practical-q1-audit/outputs.json
- report/analysis/practical-q1-audit/per_dim_recompute.csv
- report/build-sample.log
- report/build.log
- report/build.sh
- report/history/pre-practical-repair/paper.md
- report/history/pre-practical-repair/paper.pdf
- report/history/pre-practical-repair/paper.tex
- report/history/pre-practical-repair/rendered.md
- report/history/pre-practical-repair/rendered.refs.json
- report/paper.md
- report/paper.pdf
- report/paper.tex
- report/rendered.md
- report/rendered.refs.json
- report/tex/_build/minimal.aux
- report/tex/_build/minimal.log
- report/tex/_build/minimal.pass1.out
- report/tex/_build/minimal.pass2.out
- report/tex/_build/minimal.pdf
- report/tex/_build/minimal.toc
- report/tex/_build/page1.png
- report/tex/_build/pass1.out
- report/tex/_build/pass2.out
- report/tex/_build/texput.log
- report/tex/_t/sym.aux
- report/tex/_t/sym.log
- report/tex/_t/sym.out
- report/tex/_t/sym.pdf
- report/tex/_t/sym.tex
- report/tex/build/paper.aux
- report/tex/build/paper.log
- report/tex/build/paper.pdf
- report/tex/build/paper.toc
- report/tex/build/pass1.out
- report/tex/build/pass2.out
- report/tex/build/typeset.md
- report/tex/minimal.md
- report/tex/minimal.pdf
- report/tex/minimal.tex
- report/tex/pandoc-template.tex
- report/tex/typeset.py
- figures/FIG-0002-q2_method_agreement.png
- figures/q2_method_agreement.png
- figures/FIG-0003-q2_top3_heatmap.png
- figures/q2_top3_heatmap.png
- figures/FIG-0004-q3_spectra_pca.png
- figures/q3_spectra_pca.png
- figures/FIG-0005-q3_style_fidelity.png
- figures/q3_style_fidelity.png
- figures/FIG-0006-q3_defect_oav.png
- figures/q3_defect_oav.png
- figures/FIG-0007-q1_model_comparison.png
- figures/q1_model_comparison.png
- figures/FIG-0008-q1_per_dim_r2.png
- figures/q1_per_dim_r2.png
- figures/FIG-0009-q1_confusion.png
- figures/q1_confusion.png
- figures/FIG-0010-q1_error_by_style.png
- figures/q1_error_by_style.png
- figures/FIG-0011-q1_calibration.png
- figures/q1_calibration.png
- figures/FIG-0012-q1_grade_map.png
- figures/q1_grade_map.png
- figures/FIG-0013-q1_per_dim_r2_final.png
- figures/q1_per_dim_r2_final.png
- figures/FIG-0014-q1_confusion_final.png
- figures/q1_confusion_final.png
- figures/FIG-0015-q1_calibration_final.png
- figures/q1_calibration_final.png
- figures/FIG-0016-practical-q1-audit.png
- figures/practical-q1-audit.png
- figures/figures.json
- src/01_audit.py
- src/02_scale.py
- src/03_clean.py
- src/04_split.py
- src/05_dim_map.py
- src/06_calibration.py
- src/07_model_table.py
- src/08_baseline_constant.py
- src/08b_baseline_ridge.py
- src/08c_q1_final.py
- src/08d_figures.py
- src/09_independent_rerun.py
- src/common.py
- src/emit.py
- src/engineer_q1_audit.py
- src/probe_contract.py
- src/probe_env.py
- src/q1_abl.py
- src/q1_bundle.py
- src/q1_data.py
- src/q1_figs.py
- src/q1_final.py
- src/q1_final_summary.py
- src/q1_models.py
- src/q1_recompute_exp0029.py
- src/q1_robust_report.py
- src/q1_trainonly.py
- src/q2_baseline.py
- src/q2_common.py
- src/q2_figs.py
- src/q2_graph.py
- src/q2_prereg.py
- src/q2_select.py
- src/q2_stability.py
- src/q3_baseline.py
- src/q3_eval.py
- src/q3_exp_family.py
- src/q3_figs.py
- src/q3_generate.py
- src/q3_models.py
- src/q3_transfer.py
- src/q3_utils.py
- data/clean/features_log.csv
- data/raw/1.csv
- data/clean/model_table.csv
- data/raw/4.csv
- data/splits/SPLIT-0001/assignment.csv
- data/splits/SPLIT-0001/train.csv
- data/splits/SPLIT-0001/test.csv
- data/splits/SPLIT-0002/assignment.csv
- data/splits/SPLIT-0002/train.csv
- data/splits/SPLIT-0002/test.csv
- experiments/EXP-0003/metrics.json
- experiments/EXP-0003/result.json
- experiments/EXP-0007/metrics.json
- experiments/EXP-0007/predictions.csv
- experiments/EXP-0007/result.json
- experiments/EXP-0012/metrics.json
- experiments/EXP-0012/predictions.csv
- experiments/EXP-0012/result.json
- experiments/EXP-0013/metrics.json
- experiments/EXP-0013/predictions.csv
- experiments/EXP-0013/result.json
- experiments/EXP-0015/metrics.json
- experiments/EXP-0015/predictions.csv
- experiments/EXP-0015/result.json
- experiments/EXP-0019/metrics.json
- experiments/EXP-0019/predictions.csv
- experiments/EXP-0019/result.json
- experiments/EXP-0021/metrics.json
- experiments/EXP-0021/predictions.csv
- experiments/EXP-0021/result.json
- experiments/EXP-0022/metrics.json
- experiments/EXP-0022/result.json
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
- experiments/EXP-0027/predictions.csv
- experiments/EXP-0027/result.json
- experiments/EXP-0028/metrics.json
- experiments/EXP-0028/predictions.csv
- experiments/EXP-0028/result.json
- experiments/EXP-0029/metrics.json
- experiments/EXP-0029/predictions.csv
- experiments/EXP-0029/result.json
- experiments/EXP-0030/metrics.json
- experiments/EXP-0030/predictions.csv
- experiments/EXP-0030/result.json
- experiments/EXP-0034/metrics.json
- experiments/EXP-0034/predictions.csv
- experiments/EXP-0034/result.json
- experiments/EXP-0035/metrics.json
- experiments/EXP-0035/result.json
- experiments/EXP-0036/metrics.json
- experiments/EXP-0036/predictions.csv
- experiments/EXP-0036/result.json
- experiments/EXP-0038/metrics.json
- experiments/EXP-0038/predictions.csv
- experiments/EXP-0038/result.json
- experiments/EXP-0039/metrics.json
- experiments/EXP-0039/result.json
- experiments/EXP-0041/metrics.json
- experiments/EXP-0041/result.json
- experiments/EXP-0047/metrics.json
- experiments/EXP-0047/result.json
- experiments/EXP-0050/metrics.json
- experiments/EXP-0050/result.json
- experiments/EXP-0051/metrics.json
- experiments/EXP-0051/result.json
- contest.yaml
- quality-blockers.json
- ledger-summary.json
