# 实验/验证产物契约（reviewer 依据 pack 源码核对，供 modeler 对齐）

> 来源：`vibe-math-vmu/packs/modeling-contest/python/runner.py`、`python/modeling_contract.py`、`python/validate.py`、
> `runtime/validation.js`（本机 checkout：`/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/vibe-mathematics-monitor/…`）。
> 标注 `[未验证]` 的条目表示我未能从源码/实测确认，**不要按猜测写死**；其余条目均可在上述文件中复核。
> 协议台账：Q1=VP-0001、Q2=VP-0002、Q3=VP-0003。任何与本文件冲突的实现，会让 `modeling_validate {action:"run"}` 具名
> 拒绝（refuse）或判 failed——**具名拒绝不是通过，会被登记为缺陷**。

## 1. 脚本怎么被启动

- **cwd = 实验目录** `experiments/EXP-xxxx/`（不是项目根目录；不要用相对 cwd 找数据）。
- **解释器**：`contest.yaml` 绑定的 Python（当前 `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python`）。
- **环境变量（冻结名）**：`MODELING_PROJECT_DIR`、`MODELING_EXPERIMENT_ID`、`MODELING_EXPERIMENT_DIR`、
  `MODELING_METRICS_PATH`、`MODELING_PYTHON`、`MODELING_CONFIG_SHA256`、`MODELING_SEED`、
  `MODELING_DATA_FILE`、`MODELING_DATASET_ID`、`MODELING_SPLIT_ID`、`MODELING_TRAIN_FILE`、`MODELING_TEST_FILE`、
  `MODELING_ASSIGNMENT_FILE`；另有兼容别名 `PROJECT`/`EXPERIMENT_ID`/`EXPERIMENT_DIR`。
- **`import modeling_contract` 可用**：runner 把 pack 的 `python/` 目录放进 `PYTHONPATH`。接口：
  - `modeling_contract.emit_metrics(dict)` → 写 `metrics.json`；
  - `modeling_contract.emit_predictions(df, name="predictions.csv")` → 写预测 CSV；
  - `modeling_contract.save_figure(fig, name)` → 写 `figures/<name>.png` 并登记 `figures.json`；
  - `modeling_contract.emit_output(name, value)` → 写 `outputs.json`；
  - `modeling_contract.project_dir()` / `experiment_dir()` / `split_paths()` / `seed()`。
- **硬性**：脚本退出码 0 但**没有 metrics.json** = 失败（不是成功）。`metrics.json` 必须是 JSON 对象，数值键才会进台账。
- **`emit_metrics` 的精确规则（读现行 pack 源码 + EXP-0004/0005 实测）**：
  - 只接受**有限数值**（int/float/numpy 标量）；**str、bool、None、NaN、Inf 一律以具名 TypeError/ValueError 拒绝**；
  - 一次调用里只要有一个非法值，**整次调用不写**（不会部分落盘）→ 实验目录没有 metrics.json → runner 判 `NO_OUTPUT`（EXP-0004/0005 就是这样失败的）；
  - 结构化/字符串信息（逐维数组、folds、模型参数、note）必须走 `emit_output(name, value)`，不要塞进 metrics；
  - `emit_metrics` 是**合并写入**（对已存在 metrics.json 做 merge，原子替换），可多次调用分别写不同键；
  - 只有写进 `MODELING_METRICS_PATH`（= `experiments/<EXP>/metrics.json`）才算数；写到 `outputs/<area>/metrics.json` 的兜底路径**不算**（EXP-0004 的 fallback 产物即因此未被 runner 采纳）。
- **超时**：`runtime.experimentTimeoutSeconds`（当前 600s）；超时记为 `timed-out`，不得当成功重跑覆盖。
- **并发**：`maxComputeConcurrency: 1`（一次只跑一个计算任务）。

## 2. 文件与列约定（validator 实际读什么）

| 检查类型 | 需要的产物 | 必须满足 |
|---|---|---|
| `holdout-metrics` | `predictions.csv`（文件名必须 exact，kind=predictions） | 列 `y_true`、`y_pred`（**单列**）；行顺序必须与 `split.test.csv` 一致（test.csv **没有** `row` 列，长度相等时 validator 按行序对齐） |
| 同上 | `split.testPath` 的留出真值 + 台账 `experiment.metrics[metric]` | 由 `modeling_data register-split` 生成；`params.truthColumn` 缺省 = `dataset.targetColumn`，所以**登记的数据集必须包含目标列**，且该列出现在 test.csv 中 |
| `leakage` | 登记数据集的特征表（dataset processed/source 文件）+ `experiment.params.features` | 特征表需含 `targetColumn`（数据集/contest 声明）；特征列名必须能在表中找到 |
| `split-integrity` | `split.assignmentPath`（列 `row_index`,`split`）+ `trainPath`+`testPath` | 行号覆盖 0..249 恰好一次、无重叠、文件行数与 assignment 一致 |
| `baseline-compare` | 数值 `metrics.r2` + 计划里 `params.baselineMetric` 或 `params.baselineExperimentId` | 方向按 `metricDirection: maximize` |
| `independent-rerun` | 同一 `codeFile`、`seed`、`metrics[metric]` | 用同 code 重新注册+运行；确定性=1 次，随机=3 次取均值 |
| `simulation-seeds`（未用于本计划） | 每次 seed 的 `run*.json`/`seed_*.json` | 需计划里预声明 `expectedRange` |

`split.py` 已核对的事实（`packs/modeling-contest/python/split.py`）：`assignment.csv` 表头固定
`row_index,split`（0-based 位置、恰好划分）；`train.csv`/`test.csv` 是**登记数据集行的子集，列与数据集完全相同**，
**没有** `row` 列，所以 `predictions.csv` 必须按 `test.csv` 的行序写出（不要按 beer_id 排序，4/7.csv 的 beer_id 已脱敏）。

### 2.1 多目标（Q1 的 50 维）的硬限制

`holdout-metrics` 是**单列**复算（`_pick_prediction_column` 只接受一个 `y_pred`）。所以 Q1 必须：
1. 额外产出 `predictions.csv`（`row,y_true,y_pred`），覆盖**一个显式声明的主维度**（建议 `overall`），用于 pack 复算；
2. 另外把 50 维全量预测存到 `outputs/q1/pred_z.csv`（250×50，含 `beer` 键或按行序），reviewer 用独立脚本重算
   逐维 R²/MAE/Spearman 的均值——**pack 的通过不能替代 50 维重算**，两者都要登记。

### 2.2 实验登记时必须写的 params

- `params.features`：**列名 JSON 数组**（不是字符串），否则 `leakage` 以 `feature-set-unknown` 具名失败。
  - Q1：1.csv 的 231 个特征列（实际使用的全部列）。
  - Q2：参与 Top-3 选择的 231 化合物列；另写 `params.selectionInputs` 说明 2.csv/1.csv/4.csv 的用法。
  - Q3：生成空间的化合物列；另写 `params.conditionColumn: "tasting_category_fine"`、`params.stochastic: true`。
- `params.stochastic: true`：随机生成/随机森林多 seed 时必须声明。**否则** `independent-rerun` 按确定性只跑 1 次同 seed；
  随机模型会被误当确定性（虽然同 seed 通常仍复现，但这是声明义务）。
- 重跑：`rerunOf` 指向原实验 id，**不得覆盖**旧实验目录。

## 3. 计划里各 check 的适用条件（与 VP 对应）

- **VP-0001（Q1）**：`leakage`（禁止列名集合 `5/6/7.csv` 目标代理 + `8.xlsx` GBM/SHAP/Calibrated；相关性阈值 0.999）→
  `split-integrity`（250 行、80/20）→ `holdout-metrics`（r2，容差 1e-6）→ `baseline-compare`（baselineMetric=0,
  mode=improve）→ `independent-rerun`（同 seed，容差 1e-6）。
- **VP-0002（Q2）**：`leakage`（6/7/SHAP 不得进入选择；6.csv 只作选择后外部核对）→ `independent-rerun`
  （bootstrap≥200、固定 seed，复跑 Top-3 频率/Jaccard 容差 1e-6）。multiplicity（BH-FDR）与 prior-consistency
  由 reviewer 脚本执行并登记 review（pack 无对应 checkType）。
- **VP-0003（Q3）**：`leakage`（4/5/6/7/SHAP 不得进生成训练）→ `independent-rerun`（随机生成 3 seed，
  风格命中率均值差 ≤ **0.05**，这是**seed 敏感性**口径，不是复现精度；Q1/Q2 的 1e-6 不适用）。
  constraint-satisfaction / fidelity 分布距离 / small-n 由 reviewer 脚本执行并登记 review。

## 4. 缺陷 OAV 的计算口径（Q3 硬约束的前提）

**已修并复核（reviewer 独立复算，2026-10-23）**：现行 `C.oav_table()`/`C.oav_long()` 直接用 8.xlsx
`Calibrated chemical dataset` 的作者标定浓度（不再统一 `10^v`），按 `field_name_R` 与阈值 join，43 个化合物可算。
独立复算量级：DMS 中位 OAV 1.405 / max 30.17（µg/L）、diacetyl 中位 0.851 / max 406.79（mg/L）、4VG 0~3.32（mg/L）、
linalool 中位 13.55、ethyl_acetate 中位 1.152 —— 与 Lead 的物理量级一致。旧版"统一 10^v"会把线性列（13/43，
含 diacetyl、furfural）的 OAV 抬高：diacetyl 中位 11.3×、p95 9.3e4×（仅作历史记录，勿再使用）。

**仍存在的数据限制（必须披露，不得当作已解决）**：
- `trans-2-nonenal`(X.E..2.nonenal)、`3-methyl-2-butenal`(X3.methyl.2.butenal)、`5-methylfurfural`(X5.methylfurfural)
  在阈值表 `threshold_mean` 为 NaN → **无绝对 OAV**。可算绝对 OAV 的只有 DMS、diacetyl、4VG、furfural。
  裁决：t2n 与 stale hops 用"浓度不增"单调代理并标 `is_absolute_threshold=false`；论文数据限制明写"五类中仅三类可算绝对阈值"，
  **不得**写成"五类全部通过"。
- Calibrated 表**没有单位列**；OAV 依赖"cal 数值单位 = threshold 的 unit"。该前提不可由数据内部验证 `[未验证]`。
- **755 格 LOD/2 删失替代码**：37 个 log10 列中 calibrated==0 的格子，1.csv 值 = `log10(最小正浓度/2)`；
  低浓度端不是实测值，绝对量/低端 OAV 解释必须标注。

## 5. 已解决：数据集/划分目标列与单列合同（2026-10-23）

- 历史问题：DATA-0001(`features_log.csv`, 250×235, targetColumn=None) 与 SPLIT-0001 的 train/test **不含 4.csv 的 50 目标列**，
  导致 `leakage`（no targetColumn）与 `holdout-metrics`（no declared truth column）会 refuse。
- 现状（已解除）：**DATA-0002** `data/clean/model_table.csv` 250×284（3 键 + 231 特征 + 50 目标，目标值逐列与 4.csv 一致，
  reviewer 实测 max|diff|=0），配套 **SPLIT-0002**（与 SPLIT-0001 逐 beer 相同，200/50，test.csv 含 50 目标列，哈希入账）。
- 因此 Q1 实验必须 `datasetId=DATA-0002, splitId=SPLIT-0002`；`params.features` 只列 231 特征（50 目标列不得出现）；
  `holdout-metrics` 用 `truthColumn=overall`、`metric=r2_overall`（VP-0004）；50 维全量由 reviewer 独立重算。
- `stratified/` 划分已补齐为 284 列（50 目标齐全，assignment 语义不变），可作为分层稳健性复核的 holdout 真值来源。
- 参考基线：**EXP-0007**（B0 常数基线）holdout R²=-0.024635435726754987，与 reviewer 独立均数基线逐位相同。

## 6. 已由 EXP-0005 探针实测确认的事实（原 `[未验证]` 已关闭）

- `modeling_contract` 由 runner 通过 `PYTHONPATH`（pack 的 `python/` 目录）注入，`sys.path` 可直接 `import modeling_contract`；
- cwd = `experiments/<EXP>/`；环境变量实测存在：`EXPERIMENT_ID`、`EXPERIMENT_DIR`、`MODELING_EXPERIMENT_DIR`、
  `MODELING_METRICS_PATH`、`MODELING_DATA_FILE`、`MODELING_ASSIGNMENT_FILE`、`MODELING_DATASET_ID`、
  `MODELING_CONFIG_SHA256`、`MODELING_SEED`、`MODELING_TRAIN_FILE`/`MODELING_TEST_FILE`；
- `emit_metrics` 只接受有限数值，`str` 与 `inf/NaN` 均被具名拒绝；另有 `emit_predictions`、`emit_output`、
  `save_figure`、`experiment_dir`、`dataset_path`、`split_paths`、`seed`；
- 探针 EXP-0005 因为给 `emit_metrics` 传了字符串 `note` 而被拒 → 实验目录无 metrics.json → runner 判 `NO_OUTPUT`；
  这是"字符串不能当测量"的实证（该失败保留在台账，作为契约证据）。

## 6.1 指标键名契约（EXP-0007 实测发现的缺口）

pack 的 `primaryMetric = r2`，`holdout-metrics` 的 `reported` 读 `experiment.metrics[<metric>]`；
本项目的单列合同还要求 `r2_overall`（VP-0004）。**实验必须同时记录以下"裸键"**（可再带前缀的详细指标）：

| 键 | 含义 | 必需 |
|---|---|---|
| `r2` | holdout 50 维均值 R²（主指标） | 是（`baseline-compare`/`independent-rerun` 读它） |
| `r2_overall` | holdout `overall` 维 R² | 是（VP-0004 `holdout-metrics` 读它） |
| `mae` / `spearman` / `qwk` | holdout 均值（可选但建议） | 否 |

**反例（EXP-0007）**：只记录了 `holdout_r2_mean`/`holdout_r2_overall`，没有裸键 `r2`/`r2_overall`，
于是 `independent-rerun` 具名拒绝（"records no numeric primary metric r2"）。这不是通过，也不是失败——是**未完成**。
EXP-0012（`rerunOf: EXP-0007`）已修正并验证：`independent-rerun` PASS（VAL-0005，r2 差 0；EXP-0013 为复跑）。

**候选实验必须记录的指标键（按 ROB 计划）**：

| 问题 | 必需裸键 | 语义（定稿） | 用途 |
|---|---|---|---|
| Q1 | `r2` | **predictions.csv（overall 单列）的 R²**，必须与 pack 单列复算逐位一致 | VAL-0007 holdout-metrics |
| Q1 | `r2_50dim` | 50 维逐维 R² 的算术平均 = **科学主指标**（pack 不复算，reviewer 从 predictions_long.csv 重算） | 候选比较 / baseline-compare / independent-rerun |
| Q1 | `holdout_r2_mean` | 与 `r2_50dim` 同值（ROB-0001 已注册此 metricKey） | 稳健性计划 |
| Q1 | `mae` | predictions.csv 单列 MAE（== holdout_mae_overall） | 报告 |
| Q2 | `top3_stability`、`jaccard_mean` | pack rerun / ROB-0002 | |
| Q3 | `gen_style_fidelity`、`ed_over_dref_tripel` | pack rerun / ROB-0003 | |

**当前台账基线是 EXP-0015**：`r2=-0.014456198175549995`（overall 单列，VAL-0007 复算差 2.2e-16）、
`r2_50dim=holdout_r2_mean=-0.024635435726754987`、`mae=0.42349438534479994`。
EXP-0007/EXP-0012 保留为历史（分别代表"未合规"与"r2 语义不自洽"的中间版本）。

**多输出限制（已验证）**：`holdout-metrics` 只能复算**单列**指标，且 metric 名必须属于
`rmse/mae/mse/r2/accuracy/f1/mape/accuracy5/weighted-score`；因此 **50 维均值 R² 无法由 pack 直接复算**
（`r2_overall` 会被拒："cannot recompute metric 'r2_overall'"）。本项目的 50 维复算由 reviewer 对
`predictions_long.csv` 的 `split=test` 行独立完成（EXP-0012 实测：均值 R²=-0.024635435726755、MAE=0.409737038231132、
overall R²=-0.014456198175550，与上报差 ≤3e-17）。若需要 pack 层单列证据，只能另登记"单维验证实验"。

## 6.2 预测文件命名契约（必须按此，否则 holdout-metrics 取错文件）

- `predictions.csv`：**冻结单列格式** `row,y_true,y_pred`（VP-0004：overall 维，按 `split.test.csv` 行序），
  runner 会自动识别为 kind=predictions 并被 `holdout-metrics` 读取；
- 50 维宽/长表另存 `predictions_long.csv`（或 `pred_z.csv`），**不要**占用 `predictions.csv` 这个名字；
- `predictions_overall.csv` 可以保留（审计用），但 pack 读的是 `predictions.csv`。

**反例（EXP-0007）**：`predictions.csv` 是 12500×7 长表、单列合同写在 `predictions_overall.csv`，
于是 holdout-metrics 会因行数/列不对齐而 refuse；须调换命名后重跑。

## 6.3 数值稳定性防护是模型的一部分（必须在 `params` 声明并可复现）

- B1 岭回归的经验：只做"中位数插补 + 折内标准化"时，近零方差列被放大（fold 2 的 `pred_sd` 0.57→4.2），
  OOF R² 可跌到 -2.66（50/50 维为负）；加 winsorize（或标准化后 clip ±8）后回到 +0.20。
- 因此 `prep` 必须作为模型参数登记（如 `{"harmonize":"log10_linear","winsor_q":0.01,"indicator":true,"clip_z":8}`），
  reviewer 复跑时按 `params` 原样重建；**没有在 params 里声明的预处理步骤，复跑对不上时不计入复现失败，而计入"参数未声明"缺陷**。
- Q1 的插补/标准化/winsorize 必须**只在训练折内拟合**；`clip ±8` 是固定常数可在全数据应用，但要在 params 里写明。
- 两条等价路径都接受（Lead 已裁决）：(a) `median impute → StandardScaler → clip(±8) → Ridge(alpha)`，alpha 用内层 5 折
  **均方误差**选；(b) `median impute → winsorize 1/99% → StandardScaler → Ridge(alpha)`。两者结论一致（0.2026 vs 0.2029）
  视为互相印证的稳健性证据，**不是实现不一致的缺陷**；但 params 必须逐项声明（winsor_q / clip_z / alpha 选择准则 / 是否指示列），
  reviewer 按声明复跑，1e-6 内必须一致。

## 7. 最小可复现骨架（示例，不含任何目标信息）

```python
import json, os
from pathlib import Path
import numpy as np, pandas as pd
import modeling_contract as mc

project = Path(os.environ["MODELING_PROJECT_DIR"])
seed = int(os.environ.get("MODELING_SEED") or 42)
train = pd.read_csv(os.environ["MODELING_TRAIN_FILE"])
test = pd.read_csv(os.environ["MODELING_TEST_FILE"])   # 示例：test.csv 无 "row" 列，按行序写出
# … 只在 train 上拟合插补/标准化/模型，test 只做 transform …
pred = ...
mc.emit_predictions(pd.DataFrame({
    "row": np.arange(len(test)),          # 位置行号；必须与 test.csv 行序一致（不是 beer 序号）
    "y_true": y_true,                      # 例如 overall 维
    "y_pred": pred,
}))
mc.emit_metrics({"r2": float(r2), "mae": float(mae), "r2_overall": float(r2_overall)})
mc.emit_output("features", features)       # 列名数组/结构化信息走 emit_output，不要塞进 metrics
```

> 注意：上面的 `features` 必须以**列名数组**的形式出现在 `experiment.params.features`（leakage 检查优先读它），
> 不能只在 `emit_output` 里；`predictions.csv` 用 `params.predictionsPath` 或默认 `predictions.csv` 被 holdout-metrics 读取。
