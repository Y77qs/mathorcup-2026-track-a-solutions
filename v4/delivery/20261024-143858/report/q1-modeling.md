# Q1 证据：50 维 mapped grade 的模型设定、比较口径与误差分析

> 本文件是 `modeling_project workbench` 为 Q1 登记的 `model-comparison` 与 `error-analysis` 证据义务的落点，
> 同时供论文第三节引用。数值一律写成台账占位符；状态只有两种写法：**台账里 `status=succeeded` 的实验**与
> **未执行/失败**。数据事实以 `report/data-quality.md` 为唯一依据，契约以台账 `quality.targetContracts[TGT-0001]` 为准。

## 1. 任务与目标契约（不可改动的边界）

- 决策时点：化合物/理化检测完成、感官评分尚未获得；输入只有 `DATA-0001` 的 231 个 `chem__*` 列。
- 目标：`problem/targetcolumns.csv` 的 50 个真实目标列（15 Aroma + 15 Flavour + 20 口感/缺陷/总体），
  目标契约 `TGT-0001`：`taskNature=association_analysis`、`labelOrigin=transformed`、`labelSource="4.csv 标准化结果 + mapped-grade 映射"`。
- 标签口径：`mapped grade`，`x = 6·(z − zmin)/(zmax − zmin)`，`zmin/zmax` 只用 200 个训练行估计；
  训练行按构造落在 [0,6]，全表 96 格恰为 0、52 格恰为 6、15 格越界且不裁剪（逐格见 `data_quality.json → mappedGrade.outOfRangeCounts`）。
- **原始 0–6 不可还原**：3.xlsx 的 12 张评分卡是空白模板、`summary` 求值全 0 且只覆盖 12 款酒、
  4.csv 标准化参数缺失、`clove` 的训练 zmax=6.1724>6。本文件与论文都不写"还原 0–6 分"。
- 禁止：4.csv 的 50 个感官列、7.csv 任何列进入特征；用测试目标重估 `zmin/zmax`；跨表按 `beer_id` 合并（该列 250→96 截断）。

## 2. 三个模型族与形式（同数据、同划分、同指标）

数据版本 `DATA-0001`、划分 `SPLIT-0001`（random-holdout，testFraction=0.2，seed=20261024，200/50，`rowIdMapping="positional"`）。

| 族 | family | 形式 | 预处理（只用训练行拟合） | 选择项 |
|---|---|---|---|---|
| 基线 | `constant-train-median` | `ŷ_{i,t} = median_{j∈train} y_{j,t}`，无特征 | 无 | 无 |
| 候选一 | 多输出岭回归（L2） | `min_W ||XW−Y||_F² + α||W||_F²` | 中位数填补 + z 标准化 | `α` 取固定网格，由 train-only 5 折 CV 选 |
| 候选二 | 逐目标直方图梯度提升 | `HistGradientBoostingRegressor`（50 个独立模型） | 中位数填补（树模型不需缩放） | 超参数先验固定：`max_iter=120, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=10, l2_regularization=1.0, early_stopping=False` |

共同点：`metrics["mae"]` = 留出集上 50 个目标各自 MAE 的算术平均（uniform-average），
与部署版 native multi-output 复算器（从注册 split 的 test 真值 + `predictions.csv` 宽表逐目标重算、容差 1e-9）一致。

## 3. 选择协议（先于任何候选比较声明）

1. **选择指标 = `train_only_oof_mae_mean`**：同族 5 折训练内 OOF（seed 固定），三次实验用同一套折与同一套预处理口径。
2. **holdout 只做最终比较**：每个实验在 50 个留出行上只预测一次；预算 = 基线 1 + 候选 2 = 3，命中 `contest.yaml` 的 `maxHoldoutReuse=3`。
3. **选择规则**：取 OOF 最小者为最终候选；若候选相对基线的 OOF 改善不可分辨，则选基线并报告负结果。
   不允许用留出指标反向选模，也不允许换 seed/换划分把结果"做正"。
4. **产物流水线**：`predictions.csv` 宽表（`row` + 50 个 `y_pred__<target>`）；`predictions_long.csv` 只作论文/自检；
   `metrics.json` 至少含 `mae`、`holdout_mae_mean`、`train_only_oof_mae_mean`、`train_mae_mean`。

## 4. 同口径比较表（数值来自台账，未运行/未成功的不许填数）

| 模型/实验 | 族 | train-only OOF MAE（选择指标） | 留出 MAE（mapped grade） | 台账状态 |
|---|---|---|---|---|
| `EXP-0001` | 常数（逐目标训练中位数） | {{metric:EXP-0001:train_only_oof_mae_mean}} | {{metric:EXP-0001:mae}} | succeeded（下界对照） |
| `EXP-0003` | 逐目标直方图梯度提升 | {{metric:EXP-0003:train_only_oof_mae_mean}} | {{metric:EXP-0003:mae}} | succeeded（对照候选） |
| **选中** `EXP-0002` | 多输出岭回归 | {{metric:EXP-0002:train_only_oof_mae_mean}} | {{metric:EXP-0002:mae}} | succeeded（按预注册 OOF 规则选中） |

基线已达到的对照值（已真实运行、`succeeded`）：holdout `mae` = {{metric:EXP-0001:mae}}，
train-only OOF = {{metric:EXP-0001:train_only_oof_mae_mean}}；两者是同一族的两个口径，**不是**两个模型。
**选模与 holdout 方向不一致（必须与主结论同时报告）**：OOF 最小的是岭回归（{{metric:EXP-0002:train_only_oof_mae_mean}}），
但 50 行 holdout 上 HGB 的 MAE（{{metric:EXP-0003:mae}}）反而低于岭回归（{{metric:EXP-0002:mae}}）。
按预注册规则（选模只看 OOF、holdout 只作最终比较），最终模型是岭回归；本文不改选、也不把 holdout 方向包装成"HGB 更好"。
0.01 级差异在 50 行 holdout 上不足以稳定区分两个模型，这一不一致已列入稳健性风险。

## 5. 误差分析（回答"误差在哪里、为什么"）

### 5.1 需要逐项检查的误差来源

1. **越界标签（15 格，全部在测试行）**：这些单元格的 mapped grade 落在 [0,6] 之外（最小 −0.4680、最大 9.7499），
   是训练集 z 范围之外的真实取值，不裁剪。它们会**机械放大**对应目标的留出 MAE；解释误差时必须先扣除这 15 格的影响，
   再判断模型好坏。涉及目标：`A_malt_grain`、`A_hops_noble`、`F_malt_grain`、`F_hops_tropical`、`F_hops_noble`、
   `acidity`、`bitternes`、`stale_hops`、`t2n`、`orange`、`coriander`、`acetic`、`barnyard`。
2. **分布外推**：`coriander` 的最大越界达 +3.75（映射值 9.7499），`stale_hops`/`barnyard` 的 +1.57 左右；
   这些目标是"重尾"目标，常数预测与线性预测都会系统性低估峰值。
3. **缺失填补**：1.csv 9 列 73 格缺失，最大一列 `amyl.acetate` 缺 27/250；填补用训练行中位数，
   会削弱该化合物与酯类维度的关联，属"数据侧不可约"的误差来源。
4. **标签噪声**：4.csv 是人工感官评分的标准化结果，标准化方式未知；同一化合物谱在不同品评批次下的分数差异无法从附件估计，
   这是本问题的**不可约误差下界**，不能用更复杂的模型消除。
5. **分组误差**：按 Aroma / Flavour / 口感-缺陷-总体 三组分别汇总 MAE，检查是否某组整体更难；
   若某组误差显著高于其余组，应优先解释该组的标签分布（是否重尾/是否多缺失化合物）而不是换模型。
6. **稳健性负结果（ROB-0004，必须与误差讨论一起出现）**：未曝光池上的两个新划分给出 `mae` =
   {{metric:EXP-0025:mae}}（EXP-0025）与 {{metric:EXP-0026:mae}}（EXP-0026），相对极差约 180.06% > 预注册 30%，
   判定**未通过**。成因是单点离群：`1.csv` 的 `X2.methyltetrahydrofuran.3.one` 在 row 73 / beer 156 取 12596.43287
   （该列中位数 0.05286、其余最大 76.83），训练标准化后 |z|≈4897 而其余点最大 |z|≈12.6，Ridge(α=300) 把它外推到
   约 [−123.2, 349.0]，该行行内平均绝对误差约 51.54；剔除该行后 40 行平均 MAE = 0.6911（诊断值，
   `src/q1_outlier_diagnostic.py`，非台账指标）。含该行与剔除该行两个数必须同时报告；**不得为了通过而删点或换划分**。

### 5.2 图形证据（经 `modeling_deliver figure` 登记后引用）

- 基线逐目标留出 MAE（对照）：`{{figure:FIG-0004}}`。
- 选中模型逐目标留出 MAE（按误差排序）：`{{figure:FIG-0001}}`。
- 预测-真值散点（50 目标 × 50 留出行，`y=x` 参考线）：`{{figure:FIG-0002}}`。
- 残差分布（50 目标池化）：`{{figure:FIG-0003}}`。

### 5.3 结论与限制（写作时必须与结论同时出现）

- 结论句由 {{claim:CLAIM-Q1}} 承载，适用范围写"mapped grade、给定 231 个检测量、附件 250 款啤酒"。
- 不得写"还原了原始 0–6 评分"；不得把越界 15 格造成的误差算作模型缺陷；不得把 OOF 与留出混用比较。
- 若候选族不优于基线，按负结果报告：化合物谱对部分感官维度可能只有弱信号，这本身是有信息量的结论。

## 6. 复现与产物

- 脚本：`src/q1_baseline.py`、`src/q1_candidate_ridge.py`、`src/q1_candidate_hgb.py`；共同模块 `src/q_common.py`。
- 产物（每个实验目录内）：`predictions.csv`（宽表）、`predictions_long.csv`、`metrics.json`、`outputs.json`、
  `result.json`、`figures/`；runner 记录每个输出的 sha256。
- 复跑：`modeling_experiment {action:"run", experimentId}`（自动注入 `MODELING_*` 与 `PYTHONPATH`）；
  独立复跑用新实验 id + `rerunOf`，要求原实验 `freezeSources:true` 且 `dependenciesComplete:true`。
- 状态：以台账为准；未成功的实验不得在上表填任何数字（渲染器具名拒绝）。
