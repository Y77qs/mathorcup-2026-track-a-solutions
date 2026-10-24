# 验证与审查笔记（reviewer / task-5）

> 本文件是 reviewer 的工作记录与**预注册草案**，不构成"已验证"。状态只有两种写法：
> `planned`（只有计划）与 `executed+result.passed`（台账里有真实 VAL/QC 记录且未过期）。
> 台账 `state/ledger.json` 是本项目唯一事实源；本文件与台账冲突时以台账为准。

生成时间：阶段 A + Lead 拍板后的调整；最后一次核对台账 revision=506、stage=data-ready：
`datasets=3`（DATA-0001 q1_mapped / DATA-0002 q2_raw / DATA-0003 q3_table）、
`splits=3`（SPLIT-0001/0002/0003，均 random-holdout 200/50、`rowIdMapping:"positional"`）、
`validationPlans=6`（VP-0001…VP-0006）、`quality.targetContracts=2`（TGT-0001/0002）、
`quality.modelContracts=1`（MCON-0001 revision 2）、`requirements=6`；
`models/experiments/validations/claims` 仍为空。
因此数据/划分/计划/契约相关的 id、文件名、列名、阈值与哈希在本文件里是**已核实的真实值**；
EXP/MODEL id 与 claim id 等仍是占位，GO 后按台账替换并逐项核对。

---

## 0.1 阶段 A 已完成的可核实动作

1. 读题面 Markdown（未读 PDF）、`contest.yaml`、START-PROMPT。
2. 读**部署版** pack 源码（见 §0），并用真实代码/合成夹具实测了 Q1/Q2/Q3 三种 native 复算
   （§1.1–§1.3），以及三种 Q1 失败形态。
3. 用真实文件核对了：3 个数据版本的表头/列数/目标列、3 个 split 的 positional 契约与哈希、
   Q1 leakage 阈值（清洗前后）、Q3 的 43 个阈值列与 7 个可用缺陷阈值及**量纲/变换错配风险**。
4. 写了 `src/validate_q2.py`、`src/validate_q3.py`（可运行；已用合成夹具跑通正/反例），
   本文件 §6 说明其输入输出与判定口径。
5. **未**调用任何 `modeling_validate` / `modeling_project` 写动作；未改台账/配置。

---

## 0.2 Lead 拍板的六条口径（2026-10-24，已按此调整脚本与本文件）

| # | 决定 | 本文件/脚本的落点 |
|---|---|---|
| 1 | **Q3 leakage 保留并跑**（VP-0003 已登记 required:true，无法删除）。报告分两段：<br>(a) 相关性部分：`targetColumn="style"` 非数值 ⇒ 0 个特征参与、**空洞通过**，明确写"对 Q3 只具形式意义"；<br>(b) forbiddenColumns 部分**不是空洞**：核对 style/style_holdout/gbm_importance_mdi/gbm_shap/beer_price 是否混入输入特征。真正的 Q3 泄漏证据用 `src/validate_q3.py` 补。 | §4.2 与 §6；脚本 `forbidden_input_audit`（MDI/SHAP/Price 正则 + 原始标签列 style/style_holdout/tasting_category_fine 精确匹配） |
| 2 | **Q3 bound 口径**：MCON-0001 的 7 条结构化约束是 `{column:"excess__<化合物>", max:0}`，`excess = 原始浓度/阈值 − 1`；阈值用数据集同名 `thr__*`（threshold_mean）；原始浓度按 `data_quality.json#perColumnCheck[col].transform` 逐列反变换（log10→10**v；raw→v；zeroFloor→等于 floor code 时原始浓度 0，X4VG floor=-2.013157381、CS2 floor=-2.146291652）。median 版本只作灵敏度。**不采用"把阈值换算成 chem 尺度再当 bound"**。 | §4.1 重写；脚本 (A) excess 列复算 + (B) 从 chem 列独立反算 excess 并逐列比对 |
| 3 | **MCON-0001 revision 2 已落库**（7 条 excess 约束，max:0；contract-revise 补齐，台账可见 revisionNote）。 | 脚本运行时读台账 `quality.modelContracts`，不写死 |
| 4 | **Q1 baseline-compare 顺序**：baseline succeeded 后、第一个候选之前，由 Lead 在 **VP-0007** 登记（improve/minimize、metric=mae、baselineExperimentId=真实 EXP）；我收到 VP-0007 后再跑。 | §2.2 / §8 执行顺序 |
| 5 | **robustness 由 Lead 预注册**：Q1 = param-perturbation + repeated-split（新 split/新 seed，不回用 SPLIT-0001），metricKey="mae"；Q2 = param-perturbation + multiple-seeds，metricKey="topk-jaccard"；Q3 = param-perturbation + multiple-seeds，metricKey="constraint-satisfaction"。同 seed 复跑不算稳健性。 | §1.8 的硬要求不变；我按预注册核对 |
| 6 | **task 描述已更正**：task-2（宽表 predictions.csv 供 native multi-output；long 仅补充）、task-3（sets.json 数组行格式）、task-5（VP↔EXP 对应）。 | 本文件 §2–§4 与部署版一致 |

**已登记的 VP 清单（读自台账，未改）**：

| plan | 小问 | required 检查 |
|---|---|---|
| VP-0001 | Q1 | split-integrity、leakage、**holdout-metrics(required:false)**、independent-rerun(mae, runs=1) |
| VP-0004 | Q1 | holdout-metrics(mae) — **VP-0001 的更正声明**（原生 multi-output 可复算，旧结论作废） |
| VP-0002 | Q2 | split-integrity、leakage、independent-rerun(topk-jaccard, runs=1) |
| VP-0005 | Q2 | holdout-metrics(topk-jaccard) — 补充 VP-0002 |
| VP-0003 | Q3 | split-integrity、leakage(target=style)、independent-rerun(constraint-satisfaction, runs=1) |
| VP-0006 | Q3 | holdout-metrics(constraint-satisfaction) — 补充 VP-0003 |

⇒ Q1 的 holdout-metrics 由 **VP-0004** 执行（VP-0001 里被标 required:false，run 时会被跳过）；
Q2 的 holdout-metrics 由 **VP-0005**；Q3 的 holdout-metrics 由 **VP-0006**。
Q1 的 baseline-compare 等 **VP-0007**。运行时用 `checkTypes` 过滤，避免在基线上跑无信息/不适用的检查。

## 0.3 已知的 provenance 瑕疵（data-engineer 报告，不影响数据字节）

- `DATA-0001/0002` 的 `cleaningScript.sha256` 登记为 `4f6b8e70…`，当前 `src/00_prepare_q1q2.py`
  实际哈希为 `6f0a1d12…`；`DATA-0003` 登记为 `9f2f2126…`，当前 `src/00_prepare_q3.py`
  实际哈希为 `9f3d5c6b…`。脚本在 SCRIPT-0001…0005 的运行中都有记录，且三张 CSV 的字节
  在所有运行中**未变**（数据集 sha256 与台账一致，已用真实文件核对）。
- 影响面（读部署版源码确认）：`runtime/validation.js#experimentEvidence` 只把
  `dataset.processedPath + dataset.sha256` 记为验证输入，**不读 cleaningScript**；
  quality 依赖指纹也只记录文件路径。因此 `check-stale` **不会**因为 cleaningScript 哈希变化
  把 dataset/validation 判 stale；它只会在"数据文件字节变了"时 stale。
- 处理：**不重注册数据集**（会打断 TGT-0001/TGT-0002/MCON-0001 的绑定）。在报告与论文复现说明里
  如实写"登记脚本哈希指向首版脚本、数据字节未变"，并在阶段 B 的 `check-stale` 结果中记录实际判定。

---

## 0. 依据的部署版本（重要）

本机 `work/vibe-mathematics-modeling/vibe-math-vmu/packs/modeling-contest/` 是**旧 checkout**，
与本次会话实际加载的部署 pack 不同。实际生效的是：

```
~/.dsh/profiles/desktop/node_modules/dsh-vibe-math/vibe-math-vmu/packs/modeling-contest/
```

差异核对结论（旧 → 新）：部署版多出 `runtime/quality/`（types/engine/checks/evaluation/metrics/
robustness/oracle/rules/ledger/runcontrol）、`runtime/workbench.js`、`python/tabular_workbench.py`、
`python/contest_analysis.py`、`monitor/`。**验证与质量门的行为以部署版为准**；下文行号引用均为部署版。

关键结论先说：**本项目的 `holdout-metrics` 不走旧 Python 路径**。部署版
`runtime/validation.js:940-947` 对 `checkType==='holdout-metrics'` 做了两路分派：

- 实验带 `params.evaluation` → **native**，直接调用 `runtime/quality/evaluation.js#evaluateEvidence`
  （支持 multi-output / set-stability / constraint-satisfaction / energy-distance / profile-consistency /
  selection-frequency / rank-consistency）；
- 不带 `params.evaluation` 但 schemaVersion≥2 且 quality 必需 → **canonical**，转 `quality/checks.js`
  的 `metric-recompute`（单列 `predictions.csv` 对注册 test 真值）。

旧 Python `validate.py` 的 `holdout-metrics` 路径（`predictionsPath/truthPath/keyColumn`）在
`quality.required=true` 的 schema-v2 项目里**不可达**。因此本项目的 `predictionsPath/truthPath`
参数不会被读取（传了也无效），也不需要伪造 truthPath。

---

## 1. 已用真实文件/真实代码核实的实现事实

### 1.1 Q1 多输出复算（native multi-output）

输入契约（`runtime/quality/evaluation.js:29-74`，行号为部署版）：

- 实验 `params.evaluation`：
  `{kind:"multi-output", targetContractId:"TGT-xxxx", metric:"mae", metricKey:"mae",
    predictionsFile:"predictions.csv", idColumn:"row", aggregation:"uniform-average", tolerance:1e-9}`
- `targetContract.dataset.targetColumns` 必须是**完整、去重**的 50 个目标列名；且
  `targetContract.dataset.datasetId === experiment.datasetId === split.datasetId`。
- 真值 = 注册 split 的 `testPath`（按 `split.testSha256` 校验），**不是**预测文件自带的 `y_true`。
- 预测文件 = 实验目录下的宽表：一行一个 test 样本，必须含 `idColumn`（默认 `row`）与
  每个目标的 `y_pred__<target>`（可用 `evaluation.outputColumns` 覆盖列名）。
- ID 对齐：预测 id 集合必须等于 test 真值 id 集合；否则只有在
  `split.rowIdMapping==="positional"` 且 `split.rowIdMappingTestHash===sha256(truthIds.join(','))`
  且预测 id 恰为 `0..n-1` 时才按 test 顺序映射。**没有"隐式按行序"这条路**。
  实测本项目的三个 split：`rowIdMapping="positional"`、
  `rowIdMappingTestHash=60490852…` 恰等于 `sha256(test.csv 的 row 列按 test 顺序 join(","))`，
  且 test 第一行 row=0/1/2/9/14… 与 assignment 的 test 行号一致。
  ⇒ 模型导出 `predictions.csv` 时，`row` 用 **test.csv 的真实 row 值**（直接匹配，最稳），
  或用 **0..49 位置值**（走 positional 契约，也可接受）；两者都可，但不要混用、不要重复。
- 逐目标重算 `metric`（mae），再对 50 个目标做**算术平均**（`uniform-average`；无权重猜测）。
- 与 `experiment.metrics[metricKey]` 比较，容差默认 `evaluation.tolerance ?? 1e-8`。

**已实测**（用部署版 `evaluation.js` + 合成 50 目标×50 test 行夹具，Node 直接调用
`evaluateEvidence`）：

```
RESULT passed= true observed= 0.30819495333608965 reported= 0.30819495333608954 delta= 1.11e-16
kind= multi-output nTargets= 50 n= 50
```

数学等价性也已实测：50 目标等行数（每目标 50 行）时，"逐目标 MAE 的均匀平均"≡"全部 2500 对
的 MAE"（差值 0.0）。但这只说明两种写法等价，**不改变**上表的取数路径：必须宽表
`y_pred__<target>` + 注册 test 真值，而不是 long-format 自证。

**已实测的拒绝形态**（同一夹具改写）：

| 变体 | 结果 |
|---|---|
| long-format（pair_id/row/target/y_true/y_pred） | 拒绝 `duplicate sample IDs in .../predictions.csv`（`row` 列重复） |
| 位置 id 0..49 但 test 真值 id 是 200..249 | 拒绝 `prediction IDs differ from registered test IDs; implicit positional mapping refused` |
| 目标列误命名 `pred_T00`（非 `y_pred__T00`） | 拒绝 `prediction misses target T00` |

> 关于任务书里"predictions_long.csv + truthPath=long + keyColumn=pair_id"的方案：
> 部署版 native 路径根本不读 `truthPath`；若强行让旧 Python 路径读到自定 truth 文件，
> 部署版 `validation.js:496/505/533` 会拿 `split.testSha256` 校验该文件并拒绝。实测：
> `the truth file changed after it was registered: ... sha256 ... != recorded ...`。
> **结论：长期格式是给论文/自检用的补充产物，不能充当 holdout 复算入口。**

### 1.2 Q2 Top-3 集合稳定性复算（native set-stability）

输入契约（`runtime/quality/evaluation.js:75-89`）：

- 实验 `params.evaluation`：
  `{kind:"set-stability", metricKey:"topk-jaccard", topK:3, setsFile:"sets.json",
    dimensions:[50 个维度名], methods:[≥2 个互异方法名], tolerance:1e-9}`
- `sets.json` 是数组，行形如 `{dimension, method, items:[3]}`；行数必须**恰好**
  `len(dimensions)×len(methods)`，`(dimension,method)` 不重复，每行 `items` 恰为 topK 个**互异**元素。
- 复算定义：对每个维度，取所有方法两两组合，
  `Jaccard = |A∩B|/|A∪B| = 交集/(2k−交集)`；维度内取平均，再对维度取平均。
- `experiment.metrics["topk-jaccard"]` 必须存在且与复算在 `tolerance` 内一致。

**已实测**（4 维×3 方法合成夹具）：`Q2 passed= true observed= 0.15 reported= 0.15 delta= 0`。

### 1.3 Q3 约束满足复算（native constraint-satisfaction）

输入契约（`runtime/quality/evaluation.js:104-116`）：

- 实验 `params.evaluation`：
  `{kind:"constraint-satisfaction", metricKey:"constraint-satisfaction",
    samplesFile:"<生成谱 CSV>", modelContractId:"MCON-xxxx", tolerance:1e-9}`
- `modelContract.constraints` 必须是**结构化数组** `[{column,min?,max?}, ...]`（不是自由文本），
  且 `modelContract.questionId === experiment.questionId`。
- 复算 = 生成表中"同时满足全部 bound 的行数 / 总行数"；逐列违规计数写入 evidence。
- `experiment.metrics["constraint-satisfaction"]` 与复算比对。

**已实测**（40 行×3 缺陷列合成夹具）：`Q3 passed= true observed= 0.925 reported= 0.925
delta= 0 violations={"DMS":2,"Diacetyl":0,"X4VG":1}`。

> **风险点（必须 Lead 在登记时现场核实）**：当前 `modeling_project` 的公开参数表没有 `constraints`
> 字段，但 handler 确实读 `args.constraints`（部署版 `tools.js:199`，revise 在 `tools.js:224`）。
> 登记 Q3 model contract 后必须立即读回台账 `quality.modelContracts[].constraints`，确认是
> `[{column,min,max}]` 结构；若为空数组，`constraint-satisfaction` 复算会以
> `constraints must bind ... structured {column,min?,max?} bounds` 拒绝。

### 1.4 independent-rerun 的硬前置（交付门要求）

部署版 `runtime/validation.js:1045-1051`：

- 原实验必须已有 `sourceSnapshot.declaredComplete === true` **且** `dependencies` 非空，
  否则直接拒绝：`audited independent reproduction requires an immutable declared-complete
  source/input snapshot`。
  ⇒ Q1/Q2/Q3 的**最终被选实验**在 register 时必须带 `freezeSources:true` 与
  `dependenciesComplete:true`（两者都会进入 `params`，但被 `scientific()` 忽略，不影响重跑一致性）。
- 重跑 seed 固定为原 seed（`baseSeed`），比较容差取 plan 里 `independent-rerun` 检查的
  `tolerance`（缺省 `evaluation.reproductionTolerance`）。
- 重跑是**新 EXP id**，`rerunOf` 指向原实验；登记时会做 `sameRegistration && sameDependencies && sameData`
  校验，通过则 `verifiedRerun=true`，从而**不消耗** holdout 曝光预算（`experiments.js:950`、
  `quality/checks.js` 的 `holdout-reuse` 也排除它）。
- 重跑的 `metric` 取 plan 中 `independent-rerun` 检查声明的 metric；**不声明就会退回
  `evaluation.primaryMetric='mae'`**，Q2/Q3 会因找不到该指标而拒绝。因此三个 plan 都必须显式声明
  各自的 `independent-rerun` metric。

### 1.5 baseline-compare 的方向问题（Q2/Q3 不能用）

部署版 `validation.js:735` 的 `baseline-compare` 方向取 `cfg.config.evaluation.metricDirection`，
本项目 `contest.yaml` 是全局 `minimize`。对 Q1（MAE）正确；对 Q2（topk-jaccard）与
Q3（constraint-satisfaction）都是"越大越好"，该检查会把**更差**的候选判成通过。
⇒ Q2/Q3 的 plan **不登记** `baseline-compare`；baseline 的存在性由 quality 的
`baseline-required` 检查（需要 `modelKind:"baseline"` 且 `params.targetContractId` 匹配）保证，
数值对比写进论文表格与 src/validate_q2.py / validate_q3.py 的独立复算报告。

### 1.6 holdout 预算的真实计数口径

- `maxHoldoutReuse=3`，按 `splitId` 统计 **succeeded 且非 verifiedRerun** 的实验数
  （`quality/checks.js` 的 `holdout-reuse`）；`experiments.js:950-963` 还在每次 run 前按
  **test 行**预留曝光，第 4 次使用会直接 `HOLDOUT_REUSE_UNCONTROLLED` 拒绝。
- ⇒ Q1 严格 `baseline + 最多 2 个候选 = 3`；选模只允许 train-only OOF/CV。重跑必须走
  verifiedRerun（1.4）才不额外计数。
- **不要**为了给重跑腾预算而把最终模型改成 `evaluationUse:"train-only"`：那会改变被选实验的
  评估口径（不再是 holdout MAE），与 claim/论文口径冲突。

### 1.7 质量层（quality）会自动派生什么

`runtime/quality/engine.js:33-105` 的 `requiredCheckPlan` 会按台账自动派生（auto）：

- `source-anchor`、`requirement-coverage`、`target-lineage`、`metric-definition`、`claim-scope`；
- 每个 target contract：`baseline-required`（Q1/Q2 是 association/回归型，需要 succeeded baseline）；
- 每个带 `analysisPlan` 的小问：`analysis-evidence`（看 workbench 证据文件 + 实验族数 + selectedModelId）；
- 每条 claim 的 metric ref 与每个 selected model：`metric-recompute`（Q1 走 multi-output、Q2 走
  set-stability、Q3 走 constraint-satisfaction）；
- `review-provenance`、`review-independence`、`critical-findings`；
- 每个小问各一对 `robustness-plan` / `robustness-execution`；
- 实验数 ≥2 时 `holdout-reuse`；
- runcontrol 五项为 optional（本项目未用 run-control，记为 not_applicable 限制，不算通过）。

`metric-recompute` 在实验带 `params.evaluation` 时直接复用 1.1–1.3 的复算（`checks.js:266`）。
因此 **Q1/Q2/Q3 的主指标都会被独立重算两次**（一次 VAL 的 holdout-metrics，一次 QC 的
metric-recompute），二者都必须 passed 且未 stale。

### 1.8 robustness 预注册的硬要求

`runtime/quality/robustness.js#validateExecution`：

- 至少要 **2 个已 succeeded 的实验**，且它们的输入签名**真的不同**（split/dataset/seed/params/budget）；
  "同 seed 复跑"不算（要 `seed` 或 `params` 或 `budget` 或 `split` 实际变化）；
- `plan.preregisteredAt` 必须**早于**所有被链接实验的 `startedAt`（事后补登记会被拒）；
- `decisionRule` 必须是可执行对象（`sign-stable|relative-range|absolute-range|interval-width|min-value|max-value`），
  自由文本会 needs_review；
- 若方法含 `multiple-seeds`：每个实验必须 `params.requireSeedReceipt:true` 且脚本调用
  `modeling_contract.seed()`（老记录不能追认）；
- 若方法含 `repeated-split`：必须有两个**内容不同**的 assignment（换 split id/seed 不算）；
  `external-validation` 一律 needs_review（本项目没有独立外部数据，切勿声明）。

### 1.9 独立审查（review-add）的约束

- `review-add` 的 provenance 由调用上下文实测：只要 `isRoot !== true` 且
  `independence` 不低于 `contest.yaml` 的 `quality.review.independence`（`independent_context`，rank=2），
  我（teammate reviewer）的记录可以满足 `review-independence`。
- `requirements-coverage` 审查会自动绑定当前 requirements 版本；
  `requirement-coverage` 检查会比对 `binds.requirementsVersion`，要求最后一条 coverage 审查
  `verdict==="passed"` 且未 stale。因此**先 requirement-map，再让我审 coverage**；要求文本/覆盖一变，审查即过期。
- `target-lineage` 对 `labelOrigin==="transformed"` 的 target contract 要求一条
  `objectType:"targetContract"`、`verdict:"passed"`、未 stale 的独立审查（Q1、Q2 都是 transformed）。

---

## 2. Q1 检查清单与精确参数草案（planned）

假设台账 id：`DATA-Q1mapped`、`SPLIT-Q1`、基线 `EXP-00xx`、候选 `EXP-00yy`；GO 后替换。

### 2.1 实验侧必须先满足的声明（modeler 负责，reviewer 核对）

`params`（register 时写入，缺一不可）：

```json
{
  "features": ["chem__acetaldehyde", "...（与 analysisPlan.features 一致的 231 列）"],
  "family": "constant-per-target",              // 基线；候选写各自的 family（≥2 族，workbench 要求）
  "targetContractId": "TGT-xxxx",
  "freezeSources": true,                        // 仅最终被选实验必须
  "dependenciesComplete": true,                 // 仅最终被选实验必须
  "evaluation": {
    "kind": "multi-output",
    "targetContractId": "TGT-xxxx",
    "metric": "mae",
    "metricKey": "mae",
    "predictionsFile": "predictions.csv",
    "idColumn": "row",
    "aggregation": "uniform-average",
    "tolerance": 1e-9
  }
}
```

产物（experiment 目录内，runner 自动登记 sha256）：

- `predictions.csv`（宽表）：`row,y_pred__A_malt_all,...,y_pred__overall`（50 个预测列）；
  `row` 取注册 split `test.csv` 的 `row` 列值（不是 0..49 位置，除非 split 显式 positional）；
  **不要**放 `y_true`（放了则必须与注册真值逐行一致，任一处不符直接拒绝）；
- `predictions_long.csv`（补充产物，给论文/自检用）：`pair_id,row,target,y_true,y_pred`；
- `metrics.json`：至少 `mae`（数值）；`mae` = 50 目标逐目标 MAE 的算术平均
  （= 2500 对的 MAE，等行数下等价）。

### 2.2 validation plan（Lead 登记，reviewer 执行）

**实际登记拆分**（读台账）：
- **VP-0001**：split-integrity + leakage + independent-rerun(mae, runs=1)；
  其中 holdout-metrics 被标 `required:false`（基于旧 checkout 的错误结论）。
- **VP-0004**：holdout-metrics(mae) 的**更正声明**（部署版原生 multi-output 可复算），作为补充 plan 执行。
- **VP-0007**：baseline-compare（improve/minimize、metric=mae、baselineExperimentId=真实 EXP），
  Lead 在 baseline succeeded 后、第一个候选之前登记。

下面的合并 JSON 是"三张 plan 合起来的期望协议"，用于核对与实际登记是否一致（执行时按上面的 VP id 运行）。

**登记时机**：先跑完基线 → 再登记 VP-0007（`params.baselineExperimentId` 此时才存在）→ 再跑候选。
plan 早于任何候选即可，符合"先协议后比较"。

```json
{
  "questionId": "Q1",
  "protocolNote": "holdout 只做最终比较；选模用 train-only OOF；Q1 主指标 mae 由 multi-output native 复算；leakage 阈值 0.9 预声明（依据见 report/validation-notes.md §4）；Q2/Q3 不沿用本 split。",
  "checks": [
    {
      "checkType": "holdout-metrics", "required": true,
      "metric": "mae",
      "tolerance": {"absolute": 1e-9, "relative": 1e-6},
      "params": {}
    },
    {
      "checkType": "split-integrity", "required": true,
      "metric": "mae", "tolerance": {"absolute": 1e-9, "relative": 1e-6},
      "params": {}
    },
    {
      "checkType": "leakage", "required": true,
      "metric": "mae", "tolerance": {"absolute": 1e-9, "relative": 1e-6},
      "params": {
        "targetColumn": "A_malt_all",
        "forbiddenColumns": ["A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn",
          "A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody",
          "A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity",
          "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn",
          "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody",
          "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity",
          "acidity", "bitternes", "sweetness", "X4vg", "diacetyl", "dms", "metallic", "stale_hops",
          "t2n", "orange", "coriander", "clove", "lactic", "acetic", "barnyard", "alcohol",
          "aftertaste", "body", "co2", "overall"],
        "correlationThreshold": 0.9,
        "featureColumns": ["chem__acetaldehyde", "...（231 列，仅作 fallback）"]
      }
    },
    {
      "checkType": "baseline-compare", "required": true,
      "metric": "mae", "tolerance": {"absolute": 1e-9, "relative": 1e-6},
      "params": {"baselineExperimentId": "EXP-00xx", "mode": "improve"}
    },
    {
      "checkType": "independent-rerun", "required": true,
      "metric": "mae", "tolerance": {"absolute": 1e-9, "relative": 1e-6},
      "params": {}
    }
  ]
}
```

说明：

- `holdout-metrics` 的 `params` 必须为空/无路径：它走 native 分派，只用实验的
  `params.evaluation`；写 `predictionsPath/truthPath` 不会生效（只会造成误解）。
- `leakage` 的 feature 列表**优先取 `experiment.params.features`**（部署版
  `validation.js:578-601` 的冻结优先级），plan 里 `featureColumns` 只是 fallback。因此
  "模型实际用了哪些列"由实验登记决定，不由此检查决定；我会在报告里写明 `featureColumnsSource`。
- `leakage.targetColumn` 用第一列目标 `A_malt_all`（其与 231 特征的最大 |r| 实测 0.576）；
  50 个目标的**全维**最大 |r| 由我的独立脚本另算（§4）。
- `baseline-compare` 的方向取全局 minimize，Q1 正确。容差 abs=1e-9/rel=1e-6 意味着
  候选只要比基线差超过约 1e-6 相对量就**判失败**——这是有意的：失败要如实报告，不改口径。
- `independent-rerun` 的 `params` 不需要 `runs`（确定性实验 1 次；脚本必须固定种子，
  不用 `np.random.default_rng()` 无参或时间种子，否则重跑不可复现）。

### 2.3 需要执行的命令（GO 后）

```
modeling_validate {action:"run", experimentId:"EXP-00xx(基线)", planId:"VP-Q1"}   // 只跑与基线兼容的检查
modeling_validate {action:"run", experimentId:"EXP-00yy(最终候选)", planId:"VP-Q1"}
modeling_validate {action:"independent-rerun", experimentId:"EXP-00yy", planId:"VP-Q1"}
modeling_validate {action:"check-stale"}
```

注意：`run` 会对 plan 里**所有 required 检查**逐个执行；`baseline-compare` 用在基线实验上会
`candidate==baseline` → improvement=0 → 通过（数学上成立但无信息）。为可控，建议对基线只跑
`split-integrity/leakage`，对最终候选跑全部（用 `checkTypes` 过滤）。最终结论以
**最终候选**上的 `holdout-metrics + split-integrity + leakage + baseline-compare` 全部 passed 为准。

- 我会逐项记录：checkType、passed、observed vs expected、delta、失败原因、is stale。
- 任何一项 failed/stale ⇒ 不得进入 writing/delivery；不重跑掩盖、不改阈值。

---

## 3. Q2 检查清单与精确参数草案（planned）

### 3.1 实验侧声明（modeler）

```json
{
  "features": ["chem__...（231 列，实际用于排序的输入）"],
  "family": "pearson-top3" / "spearman-top3" / ... ,
  "targetContractId": "TGT-yyyy",
  "freezeSources": true, "dependenciesComplete": true,      // 被选实验
  "evaluation": {
    "kind": "set-stability",
    "metricKey": "topk-jaccard",
    "topK": 3,
    "setsFile": "sets.json",
    "dimensions": ["A_malt_all", "... 共 50 个维度名（与 targetcolumns.csv 一致）"],
    "methods": ["pearson", "spearman"],                       // ≥2，互异
    "tolerance": 1e-9
  }
}
```

产物：`sets.json`（50×methods 行，`{dimension,method,items:[3]}`）、`metrics.json`
（`topk-jaccard`）、bootstrap 频率表（另存，例如 `bootstrap_frequency.csv`，作为第二稳定性证据，
不进入 evaluation 声明）。

### 3.2 validation plan

```json
{
  "questionId": "Q2",
  "protocolNote": "同期关联分析、非因果；sets 仅在训练行内产生；2.csv 仅作共表达结构参考（Spearman、非 PSD）；5/6/7 不作独立验证；topk-jaccard 由 set-stability native 复算；不登记 baseline-compare（全局 metricDirection=minimize 与 Jaccard 方向相反）。",
  "checks": [
    {"checkType": "holdout-metrics", "required": true, "metric": "topk-jaccard",
     "tolerance": {"absolute": 1e-9, "relative": 1e-6}, "params": {}},
    {"checkType": "split-integrity", "required": true, "metric": "topk-jaccard",
     "tolerance": {"absolute": 1e-9, "relative": 1e-6}, "params": {}},
    {"checkType": "leakage", "required": true, "metric": "topk-jaccard",
     "tolerance": {"absolute": 1e-9, "relative": 1e-6},
     "params": {
       "targetColumn": "A_malt_all",
       "forbiddenColumns": ["A_malt_all", "... 50 个原始标准化感官列"],
       "correlationThreshold": 0.9,
       "featureColumns": ["chem__...（231 列，fallback）"]
     }},
    {"checkType": "independent-rerun", "required": true, "metric": "topk-jaccard",
     "tolerance": {"absolute": 1e-9, "relative": 1e-6}, "params": {}}
  ]
}
```

说明：

- 不登记 `holdout-metrics` 以外的新奇检查；`topk-jaccard` 由 native 复算（§1.2）。
- 不登记 `baseline-compare`（§1.5）。baseline 是 quality 的 `baseline-required` 要求：
  必须有 `modelKind:"baseline"` 的 succeeded 实验（如"全局统一 Top-3"），且
  `params.targetContractId` 指向 Q2 的 target contract。
- 不登记 `holdout-metrics` 的路径参数；Q2 的 sets 在训练行内产生，不存在"test 真值"，
  其"复算"是方法间一致性，而不是对外部标签的预测精度——论文必须这样表述。
- **确定性要求**：bootstrap 的种子、tie-break 顺序必须固定；否则 independent-rerun 会
  以 `independent rerun did NOT reproduce the topk-jaccard` 失败（这会如实记录，不掩盖）。

---

## 4. Q3 检查清单与精确参数草案（planned）

### 4.1 实验侧声明（modeler）

```json
{
  "features": ["style_onehot__Tripel", "... 或 style 条件编码（不得含 MDI/SHAP/Prices）"],
  "family": "conditional-generator",
  "freezeSources": true, "dependenciesComplete": true,       // 被选实验
  "evaluation": {
    "kind": "constraint-satisfaction",
    "metricKey": "constraint-satisfaction",
    "samplesFile": "generated_profiles.csv",
    "modelContractId": "MCON-xxxx",
    "tolerance": 1e-9
  }
}
```

产物：`generated_profiles.csv` 必须同时含
（i）与 MCON-0001 同名的 7 个 `excess__<化合物>` 列（pack 复算用），
（ii）对应的 `chem__<化合物>` 列（reviewer 独立反算 excess 用；没有它我只能做 pack 等价复算，
等于相信模型自己写的 excess 列，脚本会判 `needs_review` 而不是 `passed`），
（iii）`style` 列；另有 `metrics.json`（`constraint-satisfaction`）、`transfer_report.csv`（迁移前后缺陷项对比）。

**model contract 的约束（已由 Lead 落库，MCON-0001 revision 2）**：7 条 `excess__*` 列、全部 `max:0`，
`excess = 原始浓度 / 阈值 − 1`。阈值取 q3_table 的同名 `thr__*` 列（装的是 8.xlsx `threshold_mean`）；
原始浓度按 `data_quality.json#perColumnCheck[col].transform` 逐列反变换：
log10→`10**v`；raw→`v`；zeroFloor→存储值等于 floor code 时原始浓度按 0、否则 `10**v`
（X4VG floor=-2.013157381、CS2 floor=-2.146291652）。**不使用"把阈值换算成 chem 尺度再当 bound"**——
单位假设不烤进契约常量；excess=0 恰在阈值上，≤0 判满足。

下面这张换算表仍然保留，用途变成"核对 modeler 的 excess 列算得对不对"的参照
（数据集尺度数值 = 原始阈值经逆变换的等价位置；每一行都可用脚本独立复算）：

| 约束列（数据集列名） | 8.xlsx 阈值(mean) | 单位 | 变换 | **数据集尺度等价位置(max)** |
|---|---|---|---|---|
| `chem__DMS` | 17.25 | µg/L | log10 | **1.236789099** |
| `chem__X2.3.butanedione` | 0.29925 | mg/L | raw | **0.29925** |
| `chem__X4VG` | 0.206333333 | mg/L | zeroFloor | **-0.6854306064** |
| `chem__acetaldehyde` | 50.0 | mg/L | log10 | **1.698970004** |
| `chem__DES` | 1.2 | µg/L | log10 | **0.07918124605** |
| `chem__H2S` | 3.5 | µg/L | log10 | **0.5440680444** |
| `chem__SO2.mg.L.` | 15.33333333 | mg/L | log10 | **1.185636577** |

若改用 threshold_median，则 DMS→1.278753601、diacetyl→0.09、X4VG→-0.6989700043、
acetaldehyde→1.698970004、DES→0.07918124605、H2S→0.5440680444、SO2→1.041392685。
**mean/median 只能预先选一个；另一个可用于稳健性扰动，不能事后换成更好看的。**

- **实测的量纲陷阱（已给 Lead；excess 口径正是为了绕开它）**：直接把 `thr__*` 原始阈值当 bound
  去比 `chem__*` 列，在 250 个真实样本上有 **138/250（55.2%）"满足"**，7 个 bound 里 5 个从不触发
  （DMS 17.25 ≫ max 2.716；X4VG 0.2063 > max -0.1644；acetaldehyde 50 ≫ 1.269；DES 1.2 ≫ 0.6716；
  H2S 3.5 ≫ 1.694；SO2 15.33 ≫ 1.074）——**空洞通过**。
  按 excess 口径（或等价的"数据集尺度换算"）算，同一批真实样本只有 **6/250（2.4%）** 同时满足
  全部 7 个阈值（H2S 230/250 超、DMS 168/250、diacetyl 112/250、X4VG 16/250、DES 46/250；
  acetaldehyde 与 SO2 在真实样本中 0 行超阈值）。
  ⇒ 这是 `constraint-satisfaction` 的真实基率参照：生成模型若接近真实啤酒分布，该指标天然约 0.02 量级，
  **这是数据事实，不是模型缺陷**；论文必须报告该基率（writer 的 limitation 用这句）。
- **不可评估项（不得编造）**：8.xlsx 没有 `trans-2-nonenal`（X.E..2.nonenal）的数值阈值；
  "Stale hops" 在 8.xlsx 里不是化合物行，在 4.csv 里是**感官维度** `stale_hops`，无浓度阈值可比。
  `q3_thresholds.json#defectThresholdSetUsed` 已列为 `notEvaluable`，另 36 个 `thr__*` 只是参考水平
  （bitterness 5 IBU 等），不得当缺陷限值。论文/契约必须照此披露；"缺陷不恶化"在这两项上只能做
  **相对比较**（迁移前后），不能做阈值判定。
- `boundaryCases` 至少写 1 个"excess=0 恰好等于阈值"的样例（expected 来自 8.xlsx 阈值换算，
  不是生产代码输出）。


### 4.2 validation plan（已登记：VP-0003 + VP-0006）

> 下面是"VP-0003 + VP-0006 合并后的期望协议"，用于核对登记内容；
> **实际拆分为**：VP-0003 = split-integrity + leakage + independent-rerun，
> VP-0006 = holdout-metrics（只此一条）。执行时按两个 plan 分别 run。

```json
{
  "questionId": "Q3",
  "protocolNote": "生成合理性/约束满足，不是真实酿造验证；style 是条件标签不是预测目标；跨风格用 style_holdout 列显式构造；不登记 baseline-compare（全局 metricDirection=minimize 与约束满足率方向相反）。leakage 按 VP-0003 照跑，但报告分两段：相关性部分因 targetColumn=style 非数值而空洞通过（只具形式意义）；forbiddenColumns 部分是真实断言。Q3 特有泄漏风险（MDI/SHAP/Prices、原始标签列、style 留出、记忆化）由 src/validate_q3.py 独立核对。",
  "checks": [
    {"checkType": "split-integrity", "required": true, "params": {"expectedRows": 250}},
    {"checkType": "leakage", "required": true, "params": {"targetColumn": "style",
      "forbiddenColumns": ["style", "style_holdout", "gbm_importance_mdi", "gbm_shap", "beer_price",
                           "Beer Prices", "GBM importance MDI", "GBM SHAP Values"],
      "correlationThreshold": 0.9}},
    {"checkType": "holdout-metrics", "required": true, "metric": "constraint-satisfaction",
     "tolerance": {"absolute": 1e-9, "relative": 1e-6}, "params": {}},
    {"checkType": "independent-rerun", "required": true, "metric": "constraint-satisfaction",
     "tolerance": {"absolute": 1e-9, "relative": 1e-6}, "params": {"runs": 1}}
  ]
}
```

**Q3 leakage 的两段式报告（Lead 拍板，VP-0003 已 required:true，无法删除）**：

- **(a) 相关性部分：空洞通过。** `targetColumn="style"` 是非数值列，`pd.to_numeric` 后全为 NaN，
  pack 的 leakage 对每个特征都因"少于 3 个有限数值对"而跳过，`correlations` 为空、
  `maxAbsCorrelation=None`，最终 `passed=true`。这条**不构成任何证据**，
  报告里必须写"该检查对 Q3 只具形式意义，0 个特征参与相关性计算"。
- **(b) forbiddenColumns 部分不是空洞。** pack 会取实验声明的 `params.features` 与 forbidden 列表求交，
  非空即 `forbidden-column-used` 失败。这是真实断言：核对 style/style_holdout/
  gbm_importance_mdi/gbm_shap/beer_price 是否混入输入特征。
  （若实验声明 `features: []`，pack 会以"declares NO input features"判 pass——那仍是形式通过；
  所以 Q3 必须声明真实的 style 条件编码列，否则 (b) 也失去意义。）

真正的 Q3 泄漏证据由 `src/validate_q3.py` 补（与 pack 检查分工写进报告）：

1. 输入清单/数据集表头不含 `MDI|SHAP|Price`（正则断言）；
2. 声明的 features 不含原始标签列 `style`/`style_holdout`/`tasting_category_fine`
   （条件可编码为 `style_cond__*`，但不能以原始列名直接当特征）；
3. `style_holdout` 的数据事实：留出风格 = Tripel/Kriek/Lambic（49 行），
   生成谱风格覆盖；训练是否真的排除留出行由代码静态审查补证；
4. 生成谱相对训练行的记忆化率（按 chem 列整行哈希，统计完全重复比例）。

`split-integrity` 只验证注册的 SPLIT-0003（random-holdout 200/50，供基线用）是合法划分；
**它不证明**风格留出，不得让 `split-integrity: passed` 冒充"跨风格迁移已验证"。

---

## 5. leakage correlationThreshold=0.9 的预声明理由（比较之前已定）

用**原始附件**（未清洗）实测 231 个化学/理化列（1.csv，含 4 个 sum 列）× 50 个感官目标（4.csv），
行按 `beer` 逐行对齐（250/250 行一致；`beer_id` 在 4.csv 被截断，不用）：

- 全局最大 |Pearson r| = **0.7805**（`acidity` vs `lactic_acid.mg.L.`，n=250 对全非缺失）；
- 50 个目标各自的"最强单特征 |r|"：min 0.2085 / median 0.4024 / max 0.7805；
- |r| ≥ 0.8 的配对：**0**；|r| ≥ 0.7 的配对：4（acidity、lactic、acetic、alcohol）。

取 **0.9** 的理由（写死在比较之前，不看结果再调）：

1. 与实测最大合法相关 0.7805 之间有 0.12 的余量，且无任何合法特征达到 0.8；
2. |r|=0.9 ⇔ R²=0.81：该特征单独可解释目标 81% 的方差，现实中只可能来自
   "目标本身/目标的确定性变换/标签泄漏"，而不是化学量之间的真实关联；
3. 清洗后的 mapped grade 是逐目标仿射变换 `6*(z-zmin)/(zmax-zmin)`（train-only zmin/zmax），
   |r| 对仿射变换不变，所以原始数据的 0.7805 上界对清洗后的数据同样成立；
4. Q1/Q2 的 leakage 只对 `targetColumn="A_malt_all"` 做 pack 检查（实测最大 |r|=0.576），
   0.9 不会误伤；全 50 维的 max |r| 由 src/validate_q2.py 复核并报告。

**GO 后已用清洗后的真实文件复核（不只是原始附件）**：`data/processed/q1_mapped.csv`
（285 列 = 4 元数据 + 231 个 `chem__` + 50 个目标，目标列名与 targetcolumns.csv 完全一致），
`data/processed/q2_raw.csv`（同构，231 chem + 50 个原始标准化感官列）：

- Q1 mapped grade（train-only 映射后）× 231 特征：全局 max |r| = **0.780542**
  （`acidity` ~ `chem__lactic_acid.mg.L.`，与原始附件同一值，验证了仿射映射不改变 |r|）；
  50 个目标各自的最大 |r|：min 0.2085 / median 0.4024 / max 0.7805；
  |r| ≥ 0.8 的配对 **0** 个，|r| ≥ 0.9 的配对 **0** 个；
- `A_malt_all` 的最强特征为 `chem__color.EBC.`，|r| = **0.576180**（pack leakage 检查将看到的值）。

> 若 GO 后清洗数据的实际 max |r| 超过 0.9（例如某 sum 列与某目标高度共线），那是**真实发现**：
> 应排除该特征或如实写明限制，**不允许**事后把阈值调高来让检查通过。

---

## 6. 独立复算脚本（我的写域：src/validate_q2.py / src/validate_q3.py）

原则：只调用 pandas/numpy/json/hashlib，**不 import modeler 的 src 代码**；
所有路径从 `state/ledger.json`（只读）与 `contest.yaml` 读，不手抄数字；
输出 JSON 到 `report/`，把"复算值 / 台账值 / delta / 容差 / 结论"写清楚；
缺文件/缺字段时输出 `status:"refused"` 并 exit 2，绝不伪造通过。

### src/validate_q2.py（已按部署版与 Lead 口径更新并自测）

输入：`--project-dir`、`--experiment-id`、可选 `--baseline-experiment-id`、`--out`。

1. 结构化校验：`sets.json` 行数 = len(dimensions)×len(methods)；(dimension,method) 唯一；
   每行 `items` 恰为 topK 个互异项；`dimensions`/`methods` 与实验登记一致；
   任何不符 → `status:"refused"`（exit 2）。
2. 独立复算 `topk-jaccard`：维度内所有方法两两 Jaccard 平均 → 维度平均；与
   `experiments[].metrics["topk-jaccard"]` 按 contest.yaml 容差比对（abs 1e-9 / rel 1e-6），
   不符 → `status:"recomputed", passed:false`（exit 1）。
3. 泄漏审计：用注册 split 的 **train** 文件与实验声明的 features，逐维度算最大 |r|，
   报告全局 max 与 ≥0.9 的配对（应 0 个，真实值见 §5）。
4. **独立 Top-3 交叉核对**（新增，描述性）：用 |Pearson r| 在 train 行上自己取 Top-3，
   与各方法的 sets 比 Jaccard，报告 `meanBestJaccard` / 完全一致维度数。
   这不是 pass/fail 判据（方法不同），但高重叠支持 sets 来自数据而非手填。
5. 可选基线对比：`--baseline-experiment-id` 报告候选与基线的 topk-jaccard 差值
   （Q2 不在 pack 里登记 baseline-compare，数值对比放这里）。

### src/validate_q3.py（已按 excess 口径重写并自测）

1. 从台账读 MCON-0001 的 7 条 `{column:"excess__<化合物>", max:0}`；结构不符 →
   `refused`。
2. **(A) pack 等价复算**：只用 `generated_profiles.csv` 的 excess__* 列，算"一行 7 个 excess
   全 ≤0"的比例，与 `metrics["constraint-satisfaction"]` 按容差比对。
3. **(B) 独立复算**：从生成谱 `chem__<化合物>` 列 + 数据集 `thr__*`（要求常量）+ 
   `data_quality.json#perColumnCheck` 的 transform 反变换（log10/raw/zeroFloor，floor code 取
   `recurringValues`），重算 excess 与满足率；与 (A) 的满足率比对、并逐列比对模型自己写的
   excess__* 列（差异 > 1e-9 即"excess 列与自身 chem 值矛盾"的发现）。同时用同一公式算
   250 个真实样本的基率（应为 6/250=0.024）。
   **若生成谱缺 chem__* 列**：只能做 (A)，脚本判 `status:"needs_review"`、passed=false，
   不把"相信模型自己写的 excess 列"当成独立验证。
4. 输入断言：features/数据集表头不含 `MDI|SHAP|Price`；features 不含原始标签列
   `style`/`style_holdout`/`tasting_category_fine`。
5. `style_holdout` 数据事实（留出风格 Tripel/Kriek/Lambic，49 行）与生成谱风格覆盖。
6. 记忆化率：生成行与训练行按 chem 列整行哈希，统计完全重复比例（描述性）。
7. `transfer_report.csv`：独立复算缺陷迁移前后变化，报告恶化项（支持"一行一缺陷
   defect/before/after"与"宽表 *_before/*_after"两种形态）。
8. 可选 `--baseline-experiment-id`：报告候选与基线 constraint-satisfaction 差值。

> 自测（合成夹具，已跑）：正例 `reported=0 → recomputed=0 → passed=true, exit 0`，
> 且 `baseRate=0.024`；把模型 excess 列改成与 chem 值矛盾 → `passed=false, exit 1`
> （`excessColumnDisagreements` 报出 `excess__DMS maxAbsDiff=3.84`）；删掉 chem 列 →
> `status=needs_review, exit 1`。缺失/字段不符均 `refused`。

---

## 7. 未决问题（Lead 已拍板 1/2/3/4/6/7，剩余为我执行时需注意的事项）

1. ~~Q3 leakage 是否登记~~ → **已拍板：保留**（VP-0003 无法删除），按 §4.2 两段式报告：
   相关性部分空洞通过（只具形式意义）；forbiddenColumns 部分是真实断言；实质证据用脚本补。
2. ~~Q2/Q3 baseline-compare~~ → **已拍板：不登记**；Q2/Q3 的数值对比放脚本的
   `--baseline-experiment-id`（描述性，不作方向性宣称）。
3. ~~Q1 plan 登记时机~~ → **已拍板**：baseline succeeded 后、第一个候选之前在 VP-0007 登记
   baseline-compare；我收到 VP-0007 后再跑。
4. ~~Q3 constraints 参数~~ → **已拍板并落库**：MCON-0001 revision 2 含 7 条 excess 约束
   （台账已读回确认）。
5. **Q1/Q2/Q3 被选实验的 `freezeSources:true` + `dependenciesComplete:true`**：不做这一步，
   `independent-rerun` 会以"requires an immutable declared-complete source/input snapshot"拒绝，
   而 `delivery.requireIndependentRerun=true` 又要求每个被选模型都有 passed 的独立重跑 ⇒ 交付被阻断。
   请在候选/最终实验 register 时就把这两个参数带上（不必事后重跑）。
6. ~~robustness 方法~~ → **已拍板**：Q1 = param-perturbation + repeated-split（新 split/新 seed，
   不回用 SPLIT-0001）；Q2 = param-perturbation + multiple-seeds；Q3 = param-perturbation +
   multiple-seeds。multiple-seeds 的实验要 `requireSeedReceipt:true` 且脚本用
   `modeling_contract.seed()`；同 seed 复跑不算稳健性。
7. ~~Q3 bound 口径~~ → **已拍板**：excess 比值列 + thr__*（threshold_mean）+ 逐列反变换；
   median 仅作灵敏度；2.4% 真实基率写进 limitations。
8. **Q3 "缺陷不恶化"的判定方式**：pack 的 constraint-satisfaction 只支持常量 bound，无法表达
   "迁移后不比源样本差"；`transfer_report.csv` + `src/validate_q3.py` 独立复算恶化项数，
   作为**第二个报告数字**（不放进 claim 的 metric ref）。

---

## 8. 阶段 B 执行顺序（GO 后）

1. 核对台账：数据/划分已就绪（§0.1：DATA-0001/0002/0003、SPLIT-0001/0002/0003 均已登记且哈希可验）；
   核对 target/model contract（TGT-0001/0002、MCON-0001 rev2）与 experiments 是否按 §2–§4 登记；
   `configSha256` 仍为 `466a882b…`；stage 已进入 modeling/validation。
2. 等 Lead 发 EXP id（含 Q1 baseline/candidate、Q2 baseline/topk、Q3 baseline/generate）+ 选中 modelId，
   以及 **VP-0007**。按 VP↔EXP 对应关系逐项 `modeling_validate {action:"run"}`：
   - Q1 候选：VP-0001（split-integrity/leakage/independent-rerun）+ VP-0004（holdout-metrics）
     + VP-0007（baseline-compare；只在最终候选上跑）；Q1 基线只跑 split-integrity/leakage。
   - Q2 候选：VP-0002（split-integrity/leakage/independent-rerun）+ VP-0005（holdout-metrics）。
   - Q3 候选：VP-0003（split-integrity/leakage/independent-rerun）+ VP-0006（holdout-metrics）；
     leakage 按 §4.2 两段式记录。
   每次 run 用 `checkTypes` 过滤，避免对基线跑 holdout-metrics/baseline-compare 之类无信息的检查。
3. 每问 `independent-rerun`（新 EXP id、rerunOf；核对 ledger 里 `verifiedRerun=true`、
   未被计为额外 holdout 曝光）。
4. `check-stale`：确认没有 VAL/CLAIM 被标 stale；特别记录 cleaningScript 哈希瑕疵
   **没有**导致 dataset/validation stale（§0.3）；若有其它 stale，如实记录原因，修复后重跑（不手改台账）。
5. 等 Lead 创建 claims 后：`quality-plan auto → quality-run → quality-report`，只补 blocker；
   逐条列 passed/failed/needs_review/stale 与证据 id。Q1 的 `metric-recompute` 会走 multi-output、
   Q2 走 set-stability、Q3 走 constraint-satisfaction（§1.7）。
6. 独立上下文审查：`review-add` 审 `targetContract`（TGT-0001、TGT-0002 的 target-lineage；
   两者 labelOrigin=transformed，必须先有 passed 审查）与 `requirements-coverage`
   （Lead 先 requirement-map）；`independence="independent_context"`、`method` 必填。
7. 给 Lead 的交接消息按 `{角色, 任务, 输入, 期望输出, 证据引用, 未决问题, 下一步}` 逐项列
   checkType / passed / observed vs expected / delta / 失败原因 / is stale。
8. 把 Q3 的 2.4% 真实基率与"trans-2-nonenal / Stale hops 不可评估"作为 limitation 转给 writer
   （Lead 已同意转达）。

**红线（自我约束）**：不改台账、不改 contest.yaml、不放宽 maxHoldoutReuse、不伪造 robustness/validation、
不把 failed/timed-out/stale 写成成功、不手抄数字进论文、不提交竞赛作品。


---

## 9. 阶段 B 实证记录：Q1 第一批验证（EXP-0002 / MODEL-0002，2026-10-24T06:00Z）

台账 revision 720 前后写入；四条 VAL 均 `passed=true`、`pending`/`stale` 均未标记（stale 待批次 2 后
跑 `check-stale` 再确认）。

| validationId | checkType | plan | passed | observed | expected | delta | tolerance | stale |
|---|---|---|---|---|---|---|---|---|
| VAL-0001 | split-integrity | VP-0001 | true | assignmentRows=250, train=200, test=50, overlap=0, fileRows{200,50} | disjoint, coverage "each row exactly once" | — | — | 未标记 |
| VAL-0002 | leakage | VP-0001 | true | maxAbsCorrelation=0.5761801113866015, forbiddenUsed=[], checkedColumns=231, skippedColumns=0 | forbiddenUsed=[], maxAbsCorrelation<0.9 | — | — | 未标记 |
| VAL-0003 | holdout-metrics | VP-0004 | true | mae=0.6685467308887165 | mae=0.6685467308887166（台账） | -1.11e-16 | abs=1e-9 | 未标记 |
| VAL-0004 | baseline-compare | VP-0007 | true | candidate mae=0.6685467308887166 | baseline EXP-0001 mae=0.7509114931486188；improvement=+0.0823647622599（minimize） | +0.0823647622599 | allowedShortfall=7.52e-7 | 未标记 |

补充事实（从 VAL-0003 details 与我的独立复算）：

- `leakage` 的 basis 是 `experiment.params.features`（231 个 chem__ 列），
  `forbiddenPresentButUnused` = 全部 50 个感官列（说明它们不在输入里）；
  最强相关是 `chem__color.EBC.` 与 `A_malt_all` 的 |r|=0.57618，远低于预声明的 0.9。
- `holdout-metrics` 是 native multi-output：50 个目标、n=50 test 行、`aggregation=uniform-average`；
  predictions.csv 的 sha256=a390f278…、test.csv 的 sha256=3ec46c40…、assignment sha256=e3addc6c…。
- **我的独立复算**（自己读 test.csv + predictions.csv，不调用 pack/模型代码）：
  50 目标逐目标 MAE 的均匀平均 = **0.6685467308887166**，与台账 `mae` 差值 **0.0**；
  逐目标 MAE 的 min / median / max = **0.259709 / 0.684846 / 1.056053**；
  50 个目标里 >1.0 的 1 个（t2n=1.056）、>0.9 的 2 个、<0.5 的 7 个。
- 选模纪律：Q1 → MODEL-0002(Ridge/EXP-0002)，selectionStatus=provisional，按 train-only OOF 选
  （baseline 0.734104 / Ridge 0.674371 / HGB 0.684230）。**HGB 的 holdout(0.657140) 低于 Ridge(0.668547)，
  但选模未使用 holdout；这一不一致已在台账/报告中如实记录，不据此改选**。
- 批次 2（independent-rerun）待 Lead 通知计算槽空闲：EXP-0002 已带 `freezeSources:true` +
  `dependenciesComplete:true`、sourceSnapshot.declaredComplete=true、dependencies=2 个文件，
  重跑前置满足。SPLIT-0001 现有 3 个非 rerun 成功实验（baseline+2 候选，已达 maxHoldoutReuse=3），
  重跑必须且应当成为 `verifiedRerun=true`（不计入 holdout-reuse）；跑完我会在 check-stale/quality
  报告里把实际 `verifiedRerun`、holdout 计数（应为 3 个非 rerun + 1 个 rerun）写清楚。

---

## 10. 独立审查准备：target-lineage（TGT-0001 / TGT-0002）

> 还没提交 `review-add`（按 Lead 顺序，审查在 claims 之后）；这里先做独立复算与发现记录，
> 提交时 `objectType="targetContract"`、`independence="independent_context"`、`method` 用下面的方法描述。

### 10.1 方法（我会写进 review.method）

"独立重算 + 原始文件对照，不调用 modeler 代码：用 data/processed/q2_raw.csv（4.csv 的逐位副本）
与 SPLIT-0001 的 200 个训练行，按 6*(z-zmin)/(zmax-zmin) 逐目标重算 zmin/zmax 与 mapped grade；
用 data/raw/4.csv 对照 q2_raw 的目标列；用 SPLIT-0001/0002 的 assignment 校验训练行同一性；
逐项核对 target contract 的 dataset 绑定、50 个 targetColumns、labelOrigin/labelSource/labelRule/
inputsAvailableAt，并检查是否存在未来信息（future_prediction 证据）。"

### 10.2 独立复算结果（全部与台账/数据说明一致）

| 检查 | 结果 |
|---|---|
| SPLIT-0001/0002/0003 是否同一划分 | **是**（assignment 完全相同；同 seed/fraction 的预期结果） |
| q2_raw 的 50 个目标列 vs data/raw/4.csv | 逐位相同，max abs diff = **0.0**；行序按 beer 对齐 250/250 |
| 逐目标 zmin/zmax（200 训练行）vs data_quality.json mappedGrade | **50/50 一致**（|diff|<1e-9） |
| 用训练行参数重算的 mapped grade vs q1_mapped.csv | max abs diff = **5.0e-12**（12 位有效数字写出所致，roundTrip 已说明） |
| 训练行是否被测试目标污染 | 否：zmin/zmax 仅用 200 训练行；测试行有 15 个外推格子（−0.468~9.750）**未裁剪**，与 VP-0001 protocolNote 的 15 个一致 |
| 越界格子细分 | 全部 250 行共 17 个 <0 或 >6：其中 **15 个在测试行**（真实外推），另 2 个在训练行但值为 6+1e-15（浮点端点舍入，不是外推） |
| targetColumns 完整性 | TGT-0001/0002 各 50 个、互异 50 个，与 targetcolumns.csv 顺序一致；dataset 分别绑定 DATA-0001/DATA-0002 |
| labelOrigin | 两者 `transformed`；TGT-0001 的 labelRule 是 mapped-grade 线性映射（已声明仅用训练行参数），未触发 rule-dependency 复算（labelOrigin≠rule-derived） |
| 未来信息 | 无 `future_prediction` 声明；`inputsAvailableAt` = "化合物/理化检测完成时"，与 1.csv 同时可得一致 |

### 10.3 发现（拟提交为 review findings，均为 minor，不阻断）

1. **F1（minor）**：mapped grade 在测试行有 15 个格子超出 [0,6]（−0.468~9.750），契约已声明不裁剪；
   论文/claim 必须写"mapped grade（非原始 0–6）"并披露该外推，不能把 9.75 说成评分。
2. **F2（minor）**：TGT-0001 的 `dataset.targetColumn="A_malt_all"` 只是单列默认值；Q1 是多输出，
   口径必须引用 `dataset.targetColumns`（50 列）与 uniform-average MAE，claim 不得只写 A_malt_all。
3. **F3（minor）**：训练行端点出现 6+1e-15（2 个格子），属浮点舍入；若论文写"训练行严格落在 [0,6]"
   需要注明是"至浮点误差"。

拟裁决：**TGT-0001 / TGT-0002 均 verdict=passed（3 条 minor findings 记录在案，不影响 lineage）**；
若 Lead 要求"passed 必须零 findings"，可改为 findings 并把 F1/F2 写进论文限制后再复审。

---

## 11. 阶段 B 实证记录：Q2/Q3 第一批验证（EXP-0005 / EXP-0007，2026-10-24T06:02Z）

台账 revision≈923；六条 VAL 均 `passed=true`、`pending`/`stale` 未标记。

| validationId | exp | checkType | plan | passed | observed | expected | delta | tolerance |
|---|---|---|---|---|---|---|---|---|
| VAL-0005 | EXP-0005 | split-integrity | VP-0002 | true | 250 行, train=200, test=50, overlap=0 | disjoint + 每行恰一次 | — | — |
| VAL-0006 | EXP-0005 | leakage | VP-0002 | true | maxAbsCorrelation=0.5761801113864866, forbiddenUsed=[], 231 列全查 | <0.9 且无 forbidden | — | — |
| VAL-0007 | EXP-0005 | holdout-metrics（set-stability） | VP-0005 | true | topk-jaccard=0.22466666666666663, n=50 | 台账 0.22466666666666665 | -2.78e-17 | abs=1e-9 |
| VAL-0008 | EXP-0007 | split-integrity | VP-0003 | true | 250 行, train=200, test=50, overlap=0 | disjoint + 每行恰一次 | — | — |
| VAL-0009 | EXP-0007 | leakage | VP-0003 | true | **maxAbsCorrelation=null, checkedColumns=0, skippedColumns=231**, forbiddenUsed=[] | 无 forbidden 使用 | — | — |
| VAL-0010 | EXP-0007 | holdout-metrics（constraint-satisfaction） | VP-0006 | true | 1.0, n=300, 7 个 excess 违规全 0 | 台账 1.0 | 0 | abs=1e-9 |

### 11.1 Q2 独立复算（我的脚本，不调用 modeler 代码）

- sets.json：**150 行 = 50 维 × 3 方法**（`spearman_absrho` / `ridge_coef` / `random_forest_importance`），
  每行 3 个互异化合物；我的复算 Jaccard = **0.22466666666666665**，与台账 **delta=0.0**。
- 逐维 Jaccard：min/median/max = **0.0 / 0.1667 / 0.6667**（50 维）。
- leakage 独立审计（train 行）：max |r| = **0.777055**，≥0.9 的配对 **0 个**（与 pack 的 0.576 不同是因为
  pack 只查 targetColumn=A_malt_all 单列，我查了 50 个目标的全维最大值；都低于 0.9）。
- **独立 Top-3 交叉核对**：我用 |Pearson r| 在 TRAIN 行上自取 Top-3，与三种方法的 sets 比 Jaccard：
  **mean best Jaccard = 0.516，11/50 维存在某一方法与我的 Top-3 完全一致**。
  这支持"sets 来自数据、不是手填"；但方法不同，完全一致不是必要条件。
- **不可比声明**：EXP-0004 baseline 的 0.200 是 2 方法（1 个方法对/维），EXP-0005 的 0.2247 是
  3 方法（3 个方法对/维）的均值，方法对数不同 ⇒ **不得写"候选优于基线"**。

### 11.2 Q3 独立复算 + 构造性 100% 的诚实性判断

- **双路复算**：(A) 用 generated_profiles.csv 的 7 个 excess 列 = **1.0**；(B) 用 chem__ 列 + 数据集
  thr__*（threshold_mean）+ scaleAudit 反变换重算 excess = **1.0**；两路逐列一致
  （`excessColumnsAgree=true`），threshold 与 q3_thresholds.json 7/7 一致。
- **真实基率**：250 个真实样本同时满足 7 条 = **6/250 = 0.024**，与台账
  `real_sample_constraint_satisfaction=0.024` 一致；held-out 49 行为 **0**。
- **投影来源（关键）**：`generated_profiles_unconstrained.csv` 的违规数逐列等于
  `outputs.defectCounts.clippedPerCompound`：**DMS 200/300、Diacetyl 182、H2S 166、DES 55、
  4VG 5、acetaldehyde 1、SO2 0**；未投影满足率 = **0.04**（≈真实基率）。
  ⇒ `constraint-satisfaction=1.0` 是"把 7 个缺陷列超阈部分裁剪到阈值（1e-9 margin）"的直接结果，
  **不是生成器学会避缺陷**。modeler 的脚本 docstring 也明确写了这一点（诚实披露）。
- **投影前后同实验对照（有价值的证据）**：
  perStyle energy constrained/unconstrained：Tripel **1.3468/1.2993**、Kriek **7.0541/7.0648**、
  Lambic **2.1036/2.0950**（变化很小）；overall energy 3.5015/3.4864（Δ+0.015，+0.43%）；
  profile Spearman constrained：Tripel 0.3938、Kriek 0.5377、Lambic 0.5500。
  ⇒ 投影是"小改动"，但同时也说明**需要改的行很多**（DMS 2/3 的行都被改）。
- **跨实验 energy 不可比**：baseline EXP-0006 energy=1.7428 是**无条件全局池**（300 样本）对全体真实分布；
  候选 3.5015 是**3 个 held-out 风格的条件生成**对各自真实行（nReal 10/11/28）。参考集与生成目标不同，
  **不能写"变差/变好"的因果结论**。可用的是同实验内 constrained vs unconstrained 的对照。
- **transfer 独立复算**（我按 modeler 代码里的 cell-wise 定义重算，over 7 化合物 × 11 源行 = 77 格）：
  - 源行 = 数据集中全部 11 个 Pils/Lager 行（counts 与我重算完全一致：DMS 3、diacetyl 1、H2S 11、
    其余 0；satisfyingAll7=0）。
  - constrained：**77/77 = 1.0 不恶化**（按构造：迁移时 7 个缺陷列不位移，逐格与源值相同）；
  - rawshift：**11/77 = 0.142857**（只有 SO2 未恶化，其余 6 个化合物的位移使 excess 变大），
    与台账 `defect-nonworsen-rate-rawshift=0.142857` **完全一致**；
  - transfer satisfaction：source/constrained/rawshift **全为 0**（源谱本身就不达标）
    ⇒ 结论只能是"**不恶化**"，**绝不能写"达标/合规"**。
- **不可评估缺陷**：`trans-2-nonenal (X.E..2.nonenal)` 与 `3-methyl-2-butenal (X3.methyl.2.butenal)`
  在 8.xlsx 无数值阈值（modeler 已在 outputs 声明）；Stale hops 是感官维度、非化合物。

### 11.3 对 Lead 问题的直接回答

**"投影后 100% 是否等于用约束后处理把自己的评价指标做到满分？"——是，至少是部分地是。
我判断：`constraint-satisfaction=1.0` 不应作为关键结论的支撑；它只能作为"构造性事实"披露。**
理由：该指标与投影作用于同一组 7 个列，投影把超阈行直接改到阈值以下（DMS 200/300 等），
所以 1.0 度量的是"投影是否执行正确"，不是"生成模型的缺陷规避能力"；且真实啤酒 itself 只有 2.4%
同时满足 7 条、held-out 49 行为 0，1.0 这个数字比任何真实啤酒都"好"，把它当质量证据会误导。

建议的 claim 设计（供 Lead）：
1. **真实基率**（descriptive）：250 真实样本 6/250=2.4%，held-out 49 行为 0；生成模型未投影时 0.04
   （≈基率）。证据：EXP-0007 / EXP-0006 的 `real_sample_constraint_satisfaction` 与
   `constraint-satisfaction-unconstrained`（论文表格用子指标，claim refs 仍按规则只写
   `constraint-satisfaction` 或按 pack 允许的 metricKey）。
2. **投影前后对照**（descriptive）：同实验 constrained vs unconstrained 的 energy/profile 差很小，
   但**必须同时披露被裁剪的行数**；不能只报 1.0。
3. **迁移不恶化**（descriptive）：constrained 77/77 格不恶化（构造性）、rawshift 11/77；源谱 satisfaction=0
   ⇒ 只能称"不恶化"，不称"达标"。
4. `constraint-satisfaction=1.0` 只作为**构造性事实**出现在结果表/限制里，不作为任何关键 claim 的
   唯一支撑；论文必须写"constraint projection, not independent quality evidence"。

---

## 12. 阶段 B 实证记录：independent-rerun 第一批（失败，已停手）

### 12.1 事实（EXP-0012 / Q1 / rerunOf=EXP-0002）

- 调用：`modeling_validate {action:"run", experimentId:"EXP-0002", planId:"VP-0001", checkTypes:["independent-rerun"]}`
- 结果：**失败**。工具返回 `VMU_PACK_MODELING_CONTEST_RUNNER_FAILED`：
  `independent rerun EXP-0012 did not succeed (status failed), so the original metric cannot be reproduced`。
- 台账事实（读回）：
  - EXP-0012 `status="failed"`、`exitCode=1`、`verifiedRerun=true`、`rerunOf=EXP-0002`、
    `outputFiles=[]`、`startedAt=2026-10-24T06:06:15.318Z`、`endedAt=06:06:16.575Z`；
  - `failure.code="NONZERO_EXIT"`，stderr 末行：`ModuleNotFoundError: No module named 'q_common'`
    （脚本 `experiments/EXP-0002/inputs/src/q1_candidate_ridge.py` 第 19 行 `import q_common as C`）；
  - **没有产生 VAL**（validations 仍为 10），也没有 `holdoutExposures` 条目
    （EXP-0012 不在曝光列表里；verifiedRerun 豁免成立）。
- **没有重试**。按 Lead 指令，失败即停并上报。

### 12.2 根因（读部署版源码 + 路径对照，不是猜测）

- 部署版 `python/runner.py:510`：runner 优先用 `sourceSnapshot.codePath` 作为脚本路径；
  重跑复用原实验的 snapshot，因此 `script_path = experiments/EXP-0002/inputs/src/q1_candidate_ridge.py`
  ——**在原实验目录内，不在重跑实验目录 EXP-0012 内**。
- `python/runner.py:587-615`：因为 `outputIsolation="macos-seatbelt-v1"`（darwin 默认），
  子进程被 `sandbox-exec` 包住；策略先 `deny file-read* (subpath "/Users")`，
  再允许 `file-read* (subpath <experiment_dir>)`（对 EXP-0012 是 `experiments/EXP-0012`）
  以及 snapshot 文件的**逐文件**可读（`literal`）与父目录的 `file-read-metadata`。
- 原实验 EXP-0002 能 import `q_common`，是因为它的 experiment_dir = `experiments/EXP-0002`，
  `(allow file-read* (subpath experiments/EXP-0002))` 覆盖了 `inputs/src/` 目录（可 listdir）。
  重跑时 experiment_dir 变成 `experiments/EXP-0012`，而 snapshot 目录在 EXP-0002 下：
  **文件本身可读，但目录不可 listdir** → Python import 找不到 `q_common` → ModuleNotFoundError。
- 结论：这是 **pack/runner 的重跑 sandbox 缺陷**（snapshot 复用 + seatbelt 目录白名单不一致），
  不是模型代码 bug，也不是指标不可复现。`verifiedRerun` 机制本身按预期工作（未消耗曝光）。

### 12.3 预测（未执行，明确标注为代码推断）

EXP-0005（`q2_topk.py` import `q2_lib`、`q_common`）与 EXP-0007（`q3_generate.py` import
`q3_lib`、`q_common`）的重跑会走同一机制，**预计同样以 ModuleNotFoundError 失败**。
按 Lead "失败即停、不要重试掩盖"的指令，我**没有**运行这两个 rerun 去验证这个预测。

### 12.4 对交付的影响

`contest.yaml delivery.requireIndependentRerun=true`，而 `delivery.check` 要求每个被选模型都有
一条 **passed 且未 stale** 的 independent-rerun；当前 Q1/Q2/Q3 都是 0 条 ⇒ **final delivery 被阻断**
（draft 包可以出，但不能声称 final）。在 pack 修复或 Lead 给出替代协议之前，这不是我能自行绕过的。

### 12.5 新事实记录（Lead 2026-10-24 告知，已核对台账）

- **未曝光评估池**：DATA-0004/0005/0006（`q1_pool.csv`/`q2_pool.csv`/`q3_pool.csv`，各 200 行，
  = 主数据集去掉主 split test 行）已登记；SPLIT-0008…0013 为 200 行 160/40 划分
  （SPLIT-0008/0009→DATA-0004、0010/0011→DATA-0005、0012/0013→DATA-0006）。
  稳健性评估面是 40 行池 test，**与主 holdout 的 50 行不可混比**；池数据是行子集且不重估映射
  （q1_pool 目标列与 q1_mapped 逐位相同）。
- **ROB-0001**（Q1，version 2）：显式 `reference=0.6685467308887166`，`relative-range ≤ 0.30`；
  **ROB-0003**（Q3）：`metricKey=energy-distance`、`reference=3.501495913841147`、`relative-range ≤ 0.30`。
- **曝光门生效证据**：EXP-0008（Q1，SPLIT-0004）与 EXP-0011（Q2，SPLIT-0006）都是
  `register` 成功但 `run` 在 compute 启动前被 `HOLDOUT_REUSE_UNCONTROLLED` 具名拒绝，
  台账里保持 `queued`、无 failure、无输出、**零曝光**。按 Lead 要求：记为"门生效的证据"，
  **不算失败实验、不算 holdout 使用次数**。
- 当前 SPLIT-0001/0002/0003 的 exposure 条目：0001 有 EXP-0001/0002/0003 各 50 行（3 次，达上限）；
  0002 有 EXP-0004/0005；0003 有 EXP-0006/0007；EXP-0012（失败 rerun）**无**曝光条目。

---

## 13. 阶段 B 实证记录：independent-rerun 重跑（pack 修复后）+ check-stale + 契约修订

### 13.1 pack 修复已生效（runner.py）

`~/.dsh/.../packs/modeling-contest/python/runner.py:591-600` 已把 **snapshot 代码目录**加入
seatbelt 可读 subpath（`allowed_dirs += {snapshot 文件所在目录}`），原 ModuleNotFoundError
根因消除。runner.py 每次 run 由 experiments.js 新起子进程，改动立即生效。

### 13.2 Q2 / Q3 重跑成功（Q1 被 idempotency 挡住）

| 原实验 | plan | 新 rerun EXP | status | verifiedRerun | 指标 delta | VAL | passed | stale |
|---|---|---|---|---|---|---|---|---|
| EXP-0005 (Q2) | VP-0002 | **EXP-0019** | succeeded, exit 0 | **true** | topk-jaccard 0.22466666666666665 → 0.22466666666666665，**delta=0** | VAL-0011 | true | false |
| EXP-0007 (Q3) | VP-0003 | **EXP-0021** | succeeded, exit 0 | **true** | constraint-satisfaction 1 → 1，**delta=0**；其余 15 个子指标也全 delta=0 | VAL-0012 | true | false |

- 两次 rerun 的 **exposure 条目均为空**（EXP-0019/EXP-0021 不在 `holdoutExposures`）⇒ verifiedRerun 豁免成立。
- 非 rerun 成功实验计数：**SPLIT-0001=3、SPLIT-0002=2、SPLIT-0003=2**（与 Lead 预期一致，未被 rerun 推高）。
- Q1 重跑**没有执行**：`modeling_validate run` 返回同一失败记录 **EXP-0012**（status=failed），
  根因是 **idempotency key 冲突**：
  - `runtime/validation.js:1085` 的 key = `rerun:<原EXP>:hash(registration,metrics,plan.checks,seed,index)`，
    与"这是第几次尝试"无关；
  - `runtime/experiments.js:736-738` 命中已存在 key 就直接返回旧记录（即使旧记录 failed），
    于是 runner 修好了也不会重新跑。
  - 这不是指标复现失败，也不是 sandbox 失败；是"失败后重试"路径的 pack 缺陷（与 pack hint
    "fix the rerun failure and retry" 自相矛盾）。
  - 待 Lead 决策：A) 再修一行 experiments.js（failed 记录不再占用 key / 把旧记录 key 清空后再建新实验）；
    B) 用一张**判定规则完全相同**的新 plan（checks hash 不同即可，如 params 里加一条 retry 说明）绕过 key 碰撞；
    C) 接受 Q1 无 rerun（交付只能 draft）。我未做任何重试或绕过。

### 13.3 check-stale 结果

- 第一次：`validationsMarked=3, newlyMarked=3` —— **VAL-0008/0009/0010（Q3 三条）因 MCON-0001 修订而 stale**
  （reason: "model contract changed since this validation ran"）。这是正确行为：它们验证的是旧契约。
- 已用同一批 plan 重跑 Q3 三条（对当前 MCON-0001，sha=68334051…）：
  **VAL-0013 split-integrity / VAL-0014 leakage / VAL-0015 holdout-metrics，全部 passed、fresh**。
- 第二次 check-stale：`validationsMarked=3, newlyMarked=0, claimsMarked=0` —— 旧的 VAL-0008/9/10
  按设计永久 stale（历史证据，不冒充现行验证）；12 条现行 VAL 中仅这 3 条旧记录 stale。
- **claims 未被标记 stale**（claims=3；claimStaleReasons 只检查其 linked validationIds，未链接旧 VAL）。

### 13.4 MCON-0001 修订后预检（model-condition）

MCON-0001 现为 **version 4**、objectiveUnit=unitless；我用部署版 `evalFormula` 预跑 4 个 boundaryCases：

| case | inputs | expected | actual | pass |
|---|---|---|---|---|
| bc-at-threshold | ratio=1 | 0 | 0 | ✅ |
| bc-below-threshold | ratio=0.5 | -0.5 | -0.5 | ✅ |
| bc-above-threshold | ratio=2 | 1 | 1 | ✅ |
| bc-zero-floor-compound | (0/阈值换算) | -1 | -1 | ✅ |

formula = `{sum:[{linear:[{var:"ratio_to_threshold",coef:1}]},{constant:-1}]}`，顶层只有 sum，
不再被顶层 constant 短路。**model-condition 预检 4/4 通过**（quality-run 时仍以实际结果为准）。

### 13.5 稳健性计划与池数据（Lead 告知，已核对）

- **ROB-0001（Q1, v2）预计失败**：EXP-0015（α=150, mae=0.8446668450194856）与
  EXP-0016（α=600, mae=0.6055966442672139）的 range=0.2390702，relative=35.76% > 30% ⇒ 判失败。
  **真实原因**：两次扰动**同时**改 split（SPLIT-0008/0009）与正则强度（α×0.5 / α×2.0），
  极差无法归因（设计混杂）；且 α 在 160 行池上高度敏感。**不改判据、不放宽、不掩盖**；
  EXP-0015/0016 保留为真实负结果。
- **ROB-0004（Q1, v1，06:11:11.495Z 预注册）**：去混杂设计，正则强度倍数固定 1.0、只变划分；
  判定规则与 reference **逐字相同**（relative-range ≤0.30, reference=0.6685467308887166）。
  ⇒ 这是"修正实验设计"，不是"事后调阈值"；ROB-0001 的失败仍是它自己的结论。
- **ROB-0003（Q3, v2）**：metricKey 改为 energy-distance、reference=3.501495913841147、relative-range ≤0.30；
  理由（plan note 已写）：constraint-satisfaction 在投影后恒为 1，用它做稳健性判据是空洞的。
  已链接/将链接 EXP-0013（energy 4.0204）/EXP-0014（energy 4.0381）→ range 0.0216，relative≈0.62% ≤30%。
- **ROB-0002（Q2）**：param-perturbation、metricKey=topk-jaccard、min-value 0.15（无 reference）。
- 池数据：DATA-0004/0005/0006（q1/q2/q3_pool.csv，各 200 行 = 主数据集去掉主 split test 行），
  SPLIT-0008…0013 为 160/40；评估面 40 行池 test，**与主 holdout 50 行不可混比**；
  池数据行子集且不重估映射（q1_pool 目标列与 q1_mapped 逐位相同）。
- 新 target contract：**TGT-0003（Q1↔DATA-0004）、TGT-0004（Q2↔DATA-0005）**，labelOrigin=transformed、
  50 个 targetColumns ⇒ 我的 target-lineage 审查对象扩展为 **TGT-0001…0004** 四个。

---

## 14. target-lineage 审查扩展：TGT-0003 / TGT-0004（独立复算，已核实）

用真实文件复算（不调用 modeler 代码）：

| 检查 | TGT-0003（Q1↔DATA-0004/q1_pool） | TGT-0004（Q2↔DATA-0005/q2_pool） |
|---|---|---|
| 绑定数据集 | DATA-0004（`data/processed/q1_pool.csv`，200×285） | DATA-0005（`data/processed/q2_pool.csv`，200×285） |
| targetColumns | 50 个、互异、**与 targetcolumns.csv 同序** | 同左 |
| labelOrigin / labelRule | transformed；labelRule 明写"DATA-0004 是 DATA-0001 行子集，目标列逐位相同、未重估映射" | transformed；labelRule=null |
| 目标列是否被重算 | q1_pool 与 q1_mapped 在共享 row 上 **pandas equals=True**（逐位相同；data-engineer 报 10000 格 max\|diff\|=0.0） | q2_pool 与 q2_raw 在共享 row 上 **equals=True** |
| 行范围 | q1_pool 行 ⊂ q1_mapped 行；与 SPLIT-0001 test 交集 **0** | q2_pool 行 ⊂ q2_raw 行；与 SPLIT-0002 test 交集 **0** |
| inputsAvailableAt | 有（化合物/理化检测完成时，231 chem，不含感官评分） | 有 |
| taskNature | association_analysis（非 future_prediction） | association_analysis |

结论：两个池契约的 target lineage 与主契约一致（行子集 + 目标值逐位不变 + 未重估映射），
不存在"池数据重新拟合/泄漏"；拟裁决 **TGT-0003 / TGT-0004 均 verdict=passed**（无新 findings；
与 TGT-0001/0002 相同的 minor 披露——mapped grade 非原始 0–6、不得把外推当评分——继续适用）。

---

## 15. Q1 independent-rerun 的最终处置（Lead 决定：方案 C）

- **结论**：Q1 **无** independent-rerun。`delivery.requireIndependentRerun=true` ⇒ 交付只能 **DRAFT**，
  不能称 final。原因不是指标不可复现，而是 pack 的两处环境缺陷叠加：
  1. 修复前：runner 的 seatbelt 白名单只给 snapshot 文件逐文件 `literal` 读、不给目录 `file-read*`，
     CPython 无法 listdir，`import q_common` 失败（EXP-0012，exit 1，**零曝光**）；
  2. 修复后：重跑仍返回 EXP-0012，因为 `experiments.js` 的 idempotency 分支被"失败记录永久占用 key"
     卡住；释放 key 的补丁已在磁盘（`experiments.js:745-746`），但 **DSH 宿主缓存了旧 ESM 模块**，
     本次会话不生效（EXP-0012 的 `idempotencyKey` 仍为原值、`idempotencyKeyReleasedAt=None`）。
  3. 同批的 **Q2/Q3 独立复跑成功**：EXP-0019（topk-jaccard delta=0，VAL-0011）、
     EXP-0021（constraint-satisfaction delta=0，VAL-0012），均 `verifiedRerun=true`、零曝光。
- **替代证据（必须这样标注）**：reviewer 的独立复算——自读 `SPLIT-0001/test.csv` +
  `EXP-0002/predictions.csv`，50 目标逐目标 MAE 再均匀平均 = **0.6685467308887166**，
  与台账 `mae` **delta=0.0**。这**是替代证据，不等于 pack 的 independent-rerun 通过**；
  论文/报告必须写"Q1 独立复跑未完成（pack 环境缺陷），由独立复算替代，已明确标注"。
- 交付后果：工程完整性可以成立，但 `requireIndependentRerun` 使 final 检查必红；如实出 DRAFT，
  `quality-report` 里保留 Q1 validation checkpoint 红、ROB-0001 真实失败记录，**不补通过、不改 plan**。

### 15.1 Q1 稳健性补池（Lead 已安排，待登记）

- 已登记/待登记：**DATA-0007** = q1_pool 再减去 SPLIT-0008 的 40 个 test 行后的 160 行
  （配两个新 split，种子 20261027/20261028）；**TGT-0005** 绑定 DATA-0007；
  **ROB-0005** 与 ROB-0001/ROB-0004 **判定规则逐字相同**（relative-range ≤0.30，
  reference=0.6685467308887166，只做 repeated-split、α 倍数固定 1.0）。
  原因：SPLIT-0008/0009 的 test 有 3 行重叠且已到 3 次曝光，S2 被门拒绝；含这 3 行的 split 不可再用。
- **EXP-0018 不链接进任何计划**（它跑在 ROB-0004 旧设计下、且新计划必须晚于自有实验），
  作为"池第一划分上的探索性结果"在报告里如实登记。
- 截至本笔记 revision=1291，DATA-0007/TGT-0005/ROB-0005 **尚未出现在台账**；出现后我按 §14
  同样方法补做 TGT-0005 的 lineage 核对，并把 ROB-0005 的规则逐字与 ROB-0001/0004 对比。

---

## 16. 审查材料（已备好，等 Lead 通知再提交 review-add）

### 16.1 target-lineage（objectType="targetContract"，对象 TGT-0001…0004）

**method（提交时用这段）**："独立重算 + 原始文件对照，不调用 modeler 代码：用 q2_raw/q1_pool/q2_pool
与 SPLIT-0001/0002/0008/0010 的训练行，按 6*(z−zmin)/(zmax−zmin) 重算 zmin/zmax 与 mapped grade；
用 data/raw/4.csv 对照目标列；用 assignment 校验训练行与池行；逐项核对 target contract 的
dataset 绑定、50 个 targetColumns、labelOrigin/labelSource/labelRule/inputsAvailableAt 与未来信息。"

| 契约 | 绑定 | 独立核对结果 | 发现 |
|---|---|---|---|
| TGT-0001 | DATA-0001 / 50 列同序 | zmin/zmax 50/50 与 data_quality 一致；mapped grade 重算 max\|diff\|=5e-12；q2_raw 目标与 4.csv 逐位相同；测试行 15 格越界（−0.468~9.750）未裁剪；训练行仅 2 个 6+1e-15 浮点端点 | F1 mapped grade 非原始 0–6 且含外推；F2 单列 targetColumn 只是默认、口径须用 50 列；F3 端点须注明"至浮点误差" |
| TGT-0002 | DATA-0002 / 50 列同序 | 目标列 = 4.csv 标准化原值（未反变换）；无 labelRule；不涉及未来信息 | 同 F1 的披露要求（非原始 0–6） |
| TGT-0003 | DATA-0004 / 50 列同序 | q1_pool 是 q1_mapped 行子集（200 行），目标列共享行 **逐位相同**；与 SPLIT-0001 test 交集 0；未重估映射 | note：**池契约只服务稳健性扰动，不是交付目标**；F1/F2 披露继续适用 |
| TGT-0004 | DATA-0005 / 50 列同序 | q2_pool 与 q2_raw 共享行逐位相同；与 SPLIT-0002 test 交集 0；labelRule=null | 同上 |

拟裁决：**四个契约 verdict=passed**；F1/F2/F3 为 minor，已由论文"mapped grade, non-original 0–6 /
15 格越界逐格登记"与 target contract 披露覆盖。**没有 critical finding**。

### 16.2 requirements-coverage（objectType="requirements-coverage"）

**method**："逐条把 REQ 的题面原文与 coverage refs 对齐：核对每个 ref 可验证（claim/experiment/figure/
report_section 均存在且未 stale），再读论文与证据报告确认该句被实质回答（不是只挂了一个文件）；
对无法用附件回答的部分检查是否明确写为 limitation，而不是编造。"

当前 `requirement-coverage` 机械检查通过（6/6 refs 全部 `ok:true`），只差本审查；
当前 coverageHash=948507b4…（提交时以工具绑定的版本为准，若 Lead 改 coverage 我会重审）。

| REQ | 我的语义核对（读到的事实） | 结论 |
|---|---|---|
| REQ-0001 | EXP-0002 只用 231 个 chem__ 特征（VAL-0002 leakage 231 列、forbiddenUsed=[]）；holdout-metrics details targets=50；paper §2.1 明写"Aroma 15 + Flavour 15 + 口感/缺陷/总体 20 = 50，题面'约 40'的差异与来源"；附录 C 给出 50 维完整名单 | covered |
| REQ-0002 | mapped grade 公式与"train-only zmin/zmax"在 data_quality + 论文 §2.1；"mapped grade, non-original 0–6"明写；**15 个越界单元格（7<0、8>6）逐格登记**且不裁剪；另 2 个 6+1e-15 浮点端点分开说明 | covered |
| REQ-0003 | sets.json = **150 行 = 50 维×3 方法**，每行 3 个互异项；**论文附录 C 解析出 50/50 维度，150/150 条名单与 sets.json 逐项完全相同**；FIG-0005 可视化 | covered（强证据） |
| REQ-0004 | 主指标 topk-jaccard=0.22466666666666663（VAL-0007 复算 delta=−2.78e-17）；bootstrap 500 次、两个估计器、逐维频率在 outputs.stability；FIG-0006/FIG-0007；基线（2 方法）与候选（3 方法）不可比已先声明 | covered |
| REQ-0005 | EXP-0007 生成 300 条 = 3 个 held-out 风格×100；拟合只用 style_holdout=train_style 的 201 行；感官画像由 Q1 训练行 Ridge 代理生成并明确标注 surrogate、非实测；FIG-0009 | covered |
| REQ-0006 | 迁移源 = 全部 11 行 Pils/Lager；constrained 77/77 格不恶化（构造性）、rawshift 11/77；transfer satisfaction source/constrained/rawshift=0 ⇒ 只能"不恶化"；FIG-0011 前后对比 | covered，附 minor 限制（见 F4） |

**拟 findings**：
- F4（minor，已披露可标 resolved）：REQ-0006 点名 `trans-2-nonenal` 与 `Stale hops`，但附件里前者无
  数值阈值、后者是感官维度而非化合物；证据只覆盖 7 个可评估化合物并明确写"不可评估、不编造阈值"。
  resolution："论文 §Q3 限制与 q3-generation.md §2.x 已披露；相对比较（不恶化）已给出，阈值判定不声称。"
- F5（minor）：REQ-0001 的"约 40 vs 50"解释依赖论文 §2.1 与附录 C；目前一致，若后续改稿删表会破坏
  覆盖——resolution："附录 C 与 sets.json 150/150 已核对；改稿需保留该表或重新登记报告段 sha。"
- 没有 critical finding；拟裁决 **requirements-coverage verdict=passed**。

> 提交时机：等 Lead 通知"robustness 执行完"且 requirement/coverage 定稿后再 review-add，
> 避免审查绑定到会变化的 requirements/coverage hash。届时我按 tool 返回的实际 binds 版本核对一次。

---

## 17. 阶段 B 实证记录：quality plan/run/report + review-add（2026-10-24T06:20–06:23Z）

### 17.1 quality 计划与首轮结果

- `quality-plan auto`：33 项（28 required + 5 optional runcontrol）。
- 首轮 `quality-run`：**22 passed / 6 needs_review / 5 not_applicable / 0 failed / 0 stale**。
  6 项 needs_review = requirement-coverage（待 coverage 审查）、target-lineage（待 4 契约审查）、
  review-provenance/independence/critical-findings（当时无 review 记录）、
  robustness-execution(Q1)（ROB-0004 真实失败，需 negative-result claim + 计划审查）。
- **baseline-required ×4 全部 passed**（EXP-0001/EXP-0004 主契约 baseline；EXP-0024/EXP-0023 池 baseline）；
  robustness-plan/execution(Q2/Q3) passed；model-condition passed；
  metric-recompute ×5（EXP-0002/0005/0007/0019/0021）passed；analysis-evidence ×3 passed；holdout-reuse passed。
- 首轮 `quality-report`：qualityPassed=false，blockers 即上述 6 项。

### 17.2 review-add 记录（6 条，全部 independence=independent_context、isRoot=false、method 必填）

| review | objectType / objectId | binds | verdict |
|---|---|---|---|
| REV-0001 | targetContract / TGT-0001 | TGT-0001 v=e4cb84b9… | passed（3 minor resolved） |
| REV-0002 | targetContract / TGT-0002 | TGT-0002 v=301c6012… | passed（2 minor resolved） |
| REV-0003 | targetContract / TGT-0003 | TGT-0003 v=cf8b8f69… | passed（3 minor resolved；含"池契约只服务稳健性"） |
| REV-0004 | targetContract / TGT-0004 | TGT-0004 v=407e6255… | passed（3 minor resolved；含"池契约只服务稳健性"） |
| REV-0005 | requirements-coverage / project-requirements-set | requirementsVersion=948507b4… | passed（3 minor resolved；含附录 C 50/50×150/150 核对） |
| REV-0006 | robustnessPlan / ROB-0004 | ROB-0004 v=c42075f1… | passed（2 minor resolved；负结果真实、不救） |

- `review-provenance` / `review-independence` / `critical-findings` 复查后 passed；
  `requirement-coverage`、`target-lineage` 复查后 passed。
- 一次**依赖漂移**：补 REV-0006 与外部一次 `modeling_deliver render` 后，report 曾把 14 项标 stale
  （review 集合/报告文件/plan 依赖版本变化）。**全量重跑 quality-run 后 0 stale**；
  这是正常的依赖刷新，不是失败。

### 17.3 当前唯一剩余 blocker：QC-0023 robustness-execution(Q1)

- 状态 `needs_review`，code `VMU_PACK_MODELING_CONTEST_ROBUSTNESS_METHOD_INVALID`；
  原因：ROB-0004 执行有效但**稳定性假设失败**（decisionPassed=false），pack 要求
  ① 一条 precisely bound 的 negative-result claim（含 ROB-0004 与两个实验引用）+
  ② 对 ROB-0004 的独立审查（**REV-0006 已满足**）+ ③ 对 claim 的独立审查。
- 需要的 claim（由 Lead 创建）：questionId=Q1、critical=true、claimType=`negative_result`、
  refs=[{kind:"metric",experimentId:"EXP-0025",metricKey:"mae"},{kind:"metric",experimentId:"EXP-0026",metricKey:"mae"}]、
  limitations 非空、**quality.appliesTo.robustnessPlanId="ROB-0004"**。
  ⚠ 工具 schema 把 `appliesTo` 声明为 string，而 check 读的是对象字段 `appliesTo.robustnessPlanId`；
  若宿主拒绝对象，需要以工具实际错误为准并报告（这是 schema/实现形状不一致）。
- claim 建好后：我 review-add（objectType="claim"）+ 重跑 QC-0023 及 claim 依赖项
  （claim-scope / metric-definition / critical-findings），再出最终 quality-report。

### 17.4 selection 状态（pack readiness 口径，非验证缺失）

三个小问 `selectedModelId` 已登记（MODEL-0002/0005/0007），但 `selectionStatus=provisional`。
原因（Lead 查证 + 我核对）：`service.js#selectionReadiness` 只用**该小问最新的那个 validation plan**
算资格，且要求每条校验记录的 `validationPlanId` 都等于它；Q1 的检查分散在 VP-0001/VP-0004/VP-0007，
Q2 在 VP-0002/VP-0005，Q3 在 VP-0003/VP-0006 ⇒ readiness 永远不满足。
**不为此合并计划或重复跑验证**；报告里如实写"全部 required 检查均已 passed 且 fresh，provisional 是
pack readiness 口径所限"。Q1 的 validation checkpoint 因**无 independent-rerun**（方案 C）而红，
属既定事实；Q2/Q3 有 passed 的 rerun（VAL-0011/VAL-0012）。

### 17.5 当前 fresh 验证清单

- Q1：VAL-0001 split-integrity、VAL-0002 leakage、VAL-0003 holdout-metrics、VAL-0004 baseline-compare
  ——4/4 passed、fresh；**independent-rerun 缺失（EXP-0012 failed，零曝光）**。
- Q2：VAL-0005/0006/0007 + VAL-0011（independent-rerun，EXP-0019，delta=0）——4/4 passed、fresh。
- Q3：VAL-0012（independent-rerun，EXP-0021，delta=0）+ VAL-0013/0014/0015（MCON v4 下重跑）
  ——4/4 passed、fresh；VAL-0008/0009/0010 为旧契约的历史 stale（不冒充现行验证）。

---

## 18. 最终 quality 结果（writer 定稿后，2026-10-24T06:26Z）

### 18.1 计数与 qualityPassed

- writer 最终产物：RENDER-0010（paper.md sha 94b999cf…，rendered.md sha 0c98210e…，tex sha 340a16f9…，
  pdf sha aea38161…，**45 页**、0 Missing character、12 张图；占位符 120/120）。
- 最终全量 `quality-run`（35 项，含 CLAIM-0004 派生的 QC-0034/0035）：
  **passed 29 / needs_review 1（QC-0023）/ not_applicable 5 / failed 0 / stale 0**。
- 最终 `quality-report`：**qualityPassed=false**；`engineeringComplete=null`、`final=null`
  （由 Lead 的 deliver check 计算）；`criticalOpen=0`；requirements 6/6 covered；
  reviews 7/7 passed、independence 全为 independent_context。
- （Lead 预估 30 passed 是按 36 项算的；实际计划 35 项 = 29 passed + 1 needs_review + 5 n/a，以实跑为准。）

### 18.2 QC-0023 的最终原文（如实保留）

- status=`needs_review`
- code=`VMU_PACK_MODELING_CONTEST_ROBUSTNESS_METHOD_INVALID`
- message=`perturbations executed correctly, but the stability hypothesis failed; a precisely bound negative-result claim and fresh independent plan/claim reviews are required`
- hint=`retain the failed decision, limitations and raw evidence; do not change the threshold to force stability`
- evidence（摘要）：`{planId:"ROB-0004", metricKey:"mae", experiments:["EXP-0025","EXP-0026"],
  values:[0.758591595965814, 1.962372612515533], perturbation:{satisfiedMethods:["repeated-split"]},
  executionValid:true, decisionPassed:false}`

**为什么它结构上无法转 green（Lead 逐行读 + 我独立复现判定）**：

> `robustness-execution(Q1)` 的 `needs_review` 不是"未执行"或"未审查"，而是 pack 的判定要求
> "该小问所有 critical claim 均为 negative_result 且绑定该 robustness plan"；Q1 同时存在正向主结果
> claim（CLAIM-0001）与负结果 claim（CLAIM-0004），该 `every` 条件在结构上无法同时满足。
> 我们拒绝把 CLAIM-0001 降级为非关键来换取一项绿色，故按 needs_review 如实交付。

- 我独立复现了 `checks.js:559-568` 的判定：`claims.filter(qid=Q1, active, critical)` =
  [CLAIM-0001, CLAIM-0004]；CLAIM-0004 的 negative 条件全部满足（claimType=negative_result、
  appliesTo.robustnessPlanId=ROB-0004、limitations=5、refs 覆盖 EXP-0025/0026 的 mae、REV-0007 passed），
  但 CLAIM-0001 是 `contemporaneous_association` 且不绑定 ROB-0004 ⇒ `every` 必假。
  `reviewed('robustnessPlan','ROB-0004')` 本身为 true（REV-0006），缺的只是机械前提。

### 18.3 最终 fresh 验证与审查清单

- fresh VAL（12 条）：
  - Q1：VAL-0001 split-integrity、VAL-0002 leakage、VAL-0003 holdout-metrics、VAL-0004 baseline-compare；
    **无 independent-rerun**（EXP-0012 failed，零曝光；方案 C）。
  - Q2：VAL-0005、VAL-0006、VAL-0007、VAL-0011（independent-rerun，EXP-0019，delta=0）。
  - Q3：VAL-0012（independent-rerun，EXP-0021，delta=0）、VAL-0013、VAL-0014、VAL-0015（MCON v4 下）。
- 历史 stale（3 条，保留为证据、不冒充现行）：VAL-0008/0009/0010（旧 MCON 契约）。
- reviews（7 条）：REV-0001…0004（TGT-0001…0004）、REV-0005（requirements-coverage，
  binds requirementsVersion=948507b4…）、REV-0006（robustnessPlan ROB-0004）、
  REV-0007（claim CLAIM-0004，binds claim v=8e1ef639…）。
- 交付边界（与 Lead 口径一致）：
  1. engineering：数据/实验/验证/论文/三格式全部真实完成；
  2. quality：29 项真实 passed，QC-0023 为"真实负结果 + pack 机械前提不可能满足"的 needs_review，
     5 项 runcontrol 为 not_applicable；
  3. 交付：**Q1 缺 independent-rerun（环境缺陷，补丁需重启宿主）⇒ 只能 DRAFT**；
     `selectionStatus=provisional` 是 pack readiness 只看最新 plan 的口径所致，全部 required 检查均 passed 且 fresh。
- "schema/实现形状不一致"记录：`modeling_claim` 的工具 schema 把 `appliesTo` 声明为 string，
  而 pack 的 `robustness-execution` 读 `appliesTo.robustnessPlanId`（对象）；Lead 以对象形式传参
  **未被宿主阻断**、成功落库（CLAIM-0004）。这类不一致应在报告/复现说明里记一笔，但不影响本结论。








