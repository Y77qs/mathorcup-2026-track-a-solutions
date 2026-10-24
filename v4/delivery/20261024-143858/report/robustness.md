# 稳健性检验：预注册设计、执行结果与 Q1 失败分析

> 本文件是 `modeling_project workbench` 为 Q1/Q2/Q3 登记的 `robustness` 证据义务的落点，供论文第六节引用。
> 纪律：**先预注册、后扰动**。计划在下表登记后才运行；执行结果只能由 `robustness-plan-execute` 链接**真实 succeeded**
> 的实验后填入；不得事后补计划，也不得用"同 seed 复跑"冒充稳健性。数值用与论文相同的台账占位符语法，便于核对。

## 1. 预注册计划（台账 `quality.robustnessPlans`）

| 计划 | 小问 | 方法 | 扰动设计 | 评估面 | 指标键 | 判定规则（可执行对象） | 状态 |
|---|---|---|---|---|---|---|---|
| ROB-0001 | Q1 | `repeated-split` + `param-perturbation` | 新 seed 划分 + α×0.5 / ×2.0（参数写在**嵌套 params**） | DATA-0004（160/40） | `mae` | `{"type":"relative-range","limit":0.30,"reference":0.6685467308887166}` | **未执行**（见下） |
| ROB-0002 | Q2 | `param-perturbation` | bootstrap 500→1000/seed 20261031；Ridge→Kendall tau-b | DATA-0005（160/40） | `topk-jaccard` | `{"type":"min-value","limit":0.15}` | 已执行 |
| ROB-0003 | Q3 | `param-perturbation` | 每风格 200 样本；收缩 ×0.5/×2.0；生成器 seed 20261027/28（**嵌套 params**） | DATA-0006（160/40） | `energy-distance` | `{"type":"relative-range","limit":0.30,"reference":3.501495913841147}` | **未执行**（见下） |
| ROB-0004 | Q1 | `repeated-split` | 去混杂：α 乘子作为**顶层标量**；两个新 seed 各跑一次 | DATA-0004（160/40） | `mae` | 与 ROB-0001 **逐字相同**：relative-range ≤0.30、reference=0.6685467308887166 | 已执行 |
| ROB-0005 | Q3 | `repeated-split` | 去混杂：`n_samples_per_style`/`shrinkage` 作为**顶层标量** | DATA-0006（160/40） | `energy-distance` | 与 ROB-0003 **逐字相同**：relative-range ≤0.30、reference=3.501495913841147 | 已执行 |

**ROB-0001 / ROB-0003 未执行的原因（如实记录）**：它们声明的 `param-perturbation` 写在嵌套 `params` 里，台账的输入签名只看顶层
params，无法证实"扰动确实不同"；按稳健性校验规则，这种实验即使运行也会被记为"输入签名不可证实"。因此改用
ROB-0004/ROB-0005：**判定规则与 reference 逐字不变**，只是把设计改为可证实的 `repeated-split` 并把乘子提到顶层标量以去混杂。
这是对实验设计的修正，不是放宽标准；ROB-0001/ROB-0003 的 `executedAt` 仍为空，本文不写成"已通过"。

## 2. 评估面：未曝光评估池

- 部署版 pack 的 holdout 曝光门按行内容 hash 计数、上限 3；Q1 主 holdout 用满 3 次后，`EXP-0008`/`EXP-0011` 以及
  **`EXP-0020`/`EXP-0022`/`EXP-0028` 三条 queued 实验**（零曝光、从未 run）均为 `HOLDOUT_REUSE_UNCONTROLLED` 的拒绝留档。
- 评估行因此改放在三个未曝光池：`DATA-0004`（DATA-0001 去掉 SPLIT-0001 的 50 个 test 行，200 行）、`DATA-0005`（同理）、
  `DATA-0006`（同理），池内 160/40，对应 `SPLIT-0008…SPLIT-0017`。
- **池上指标与主 holdout（50 行）不可混比**；池 baseline 另跑：`EXP-0024`（Q1 常数基线，{{metric:EXP-0024:mae}}）、
  `EXP-0023`（Q2 全局基线，{{metric:EXP-0023:topk-jaccard}}）。

## 3. 判定口径

- `relative-range` = (max − min)/|reference| ≤ limit；`min-value` = min ≥ limit。
- reference 一律取**主实验**指标（`EXP-0002` 的 holdout MAE / `EXP-0007` 的 energy-distance），不是扰动结果的函数。
- ROB-0003/0005 的判据不用 `constraint-satisfaction`：交付版本的该指标恒为 1（约束投影的构造性结果，见
  `report/q3-generation.md` §6.1），对扰动无分辨力，用它做判据是空洞通过。

## 4. 执行结果（已链接的主判据实验）

| 计划 | 实验 | 值 | 判据 | 结论 |
|---|---|---|---|---|
| ROB-0002 | `EXP-0010`（DATA-0005/SPLIT-0010，bootstrap 1000/seed 20261031） | `topk-jaccard` = {{metric:EXP-0010:topk-jaccard}} | — | — |
| ROB-0002 | `EXP-0017`（DATA-0005/SPLIT-0010，Ridge→Kendall tau-b） | `topk-jaccard` = {{metric:EXP-0017:topk-jaccard}} | min = 0.218 ≥ 0.15 | **通过** |
| ROB-0004 | `EXP-0025`（DATA-0004/SPLIT-0014，seed 20261027，α×0.5） | `mae` = {{metric:EXP-0025:mae}} | — | — |
| ROB-0004 | `EXP-0026`（DATA-0004/SPLIT-0015，seed 20261046，α×2.0） | `mae` = {{metric:EXP-0026:mae}} | (max−min)/0.6685467308887166 ≈ 180.06% > 30% | **未通过（负结果）** |
| ROB-0005 | `EXP-0027`（DATA-0006/SPLIT-0012，n=200，shrinkage×0.5） | `energy-distance` = {{metric:EXP-0027:energy-distance}}；`constraint-satisfaction` = {{metric:EXP-0027:constraint-satisfaction}} | — | — |
| ROB-0005 | `EXP-0029`（DATA-0006/SPLIT-0017，n=200，shrinkage×2.0） | `energy-distance` = {{metric:EXP-0029:energy-distance}}；`constraint-satisfaction` = {{metric:EXP-0029:constraint-satisfaction}} | (max−min)/3.501495913841147 ≈ 0.2175% ≤ 30% | **通过** |

> ROB-0005 的 `constraint-satisfaction` 两次都为 1，是投影的构造性结果，只说明"投影在扰动下仍达成约束"，不作分布质量证据；
> 判据是 `energy-distance` 的相对范围。

## 5. 未链接 / 探索性实验（真实数值照列，不作判据）

| 实验 | 设计 | 值 | 处理 |
|---|---|---|---|
| `EXP-0013` | Q3 池 DATA-0006、shrinkage×0.5（旧 ROB-0003 口径） | `energy-distance` = {{metric:EXP-0013:energy-distance}} | 未链接计划，仅对照 |
| `EXP-0014` | Q3 池 DATA-0006、shrinkage×2.0 | `energy-distance` = {{metric:EXP-0014:energy-distance}} | 同上 |
| `EXP-0015` | Q1 池 DATA-0004、seed 20261025、α×0.5（旧 ROB-0001 口径） | `mae` = {{metric:EXP-0015:mae}} | 未链接计划，仅对照 |
| `EXP-0016` | Q1 池 DATA-0004、seed 20261026、α×2.0 | `mae` = {{metric:EXP-0016:mae}} | 同上 |
| `EXP-0018` | Q1 池 DATA-0004 第一个划分上的**探索性**结果 | `mae` = {{metric:EXP-0018:mae}} | **显式标注：探索性、不链接任何计划** |
| `EXP-0024` | Q1 池 baseline（常数逐目标） | `mae` = {{metric:EXP-0024:mae}} | 池对照基线 |
| `EXP-0023` | Q2 池 baseline（全局统一 Top-3） | `topk-jaccard` = {{metric:EXP-0023:topk-jaccard}} | 池对照基线 |

## 6. Q1 稳健性失败：单点离群值被线性模型外推（负结果）

- 数据事实：`1.csv` 的 `X2.methyltetrahydrofuran.3.one` 在 **row 73 / beer 156** 为 **12596.43287**；该列中位数 0.05286，
  除它外最大值 76.83，全列 **>100 的只有这 1 个点**（原始 `1.csv` 独立复核，pipeline 未造数）。
- 机制：训练集标准化后该点 |z| ≈ **4897**，其余点最大 |z| ≈ **12.6**；Ridge(α=300) 线性外推到约 **[−123.2, 349.0]**，
  该行行内平均绝对误差约 **51.54**；40 行平均把池上 MAE 从约 0.69 抬到 {{metric:EXP-0026:mae}}。
- 两个数同时报告：含该行 = {{metric:EXP-0026:mae}}；剔除该行后 40 行平均 MAE = **0.6911**（诊断值，由
  `src/q1_outlier_diagnostic.py` 只读 `experiments/EXP-0026/predictions.csv` 复现；**非台账指标、不用占位符**）。
- 模型含义与处置：线性模型对训练分布外的单点没有防护；树模型不会有该外推，但 HGB 未被选中（按 train-only OOF 选模）。
  **我们没有为让它通过而剔除离群行，也没有搜出避开该行的划分**；判据保持预注册 seed 与限值，结论按失败记录。
- 该负结果由 {{claim:CLAIM-0004}}（`claimType=negative_result`、critical）承载；适用范围仅限 `DATA-0004` 的重复划分族
  （`SPLIT-0014`/`SPLIT-0015`，各 40 行 test），不外推到主 holdout 与外部样品。

## 7. 失败与不稳定的报告原则

1. 扰动实验 `failed/timed-out/interrupted`：写明状态与原因、对结论的影响；不重跑成"成功"掩盖。
2. 判定规则不满足：如实写"该结论对扰动不稳定"，论文第七节把对应结论降级为"条件下成立"；不改限值、不换 seed、不删扰动项。
3. 稳健性只覆盖已预注册的扰动维度；未预注册的扰动不能事后追认为稳健性证据。

## 8. 与论文第六节的对应

- 论文 6.1 表 = 本文件 §1；论文表 6-1 = 本文件 §4；论文表 6-2 = 本文件 §5；论文 6.3 = 本文件 §6。
- 论文不写"通过了稳健性检验"：Q2/Q3 各写"通过某条预注册判据"，Q1 写"未通过 + 成因 + 负结果处置"，均与台账
  `robustnessPlans[].result` 一致。
- 补数字时必须继续用 `{{metric:EXP-xxxx:...}}` 占位符，不许手抄。
