# 验证契约修复说明（Q1/Q3）

项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`
性质：**验证契约修复**，不是新的预注册，也不是科学失败或科学通过。本文件不修改任何旧 VP/EXP/VAL，旧拒绝回执全部保留。
时间顺序（如实保留）：先导轮（EXP-0038…0072 / VP-0004、0009–0011）→ 确认轮（VP-0012/0013/0014，EXP-0073…0080）→ **本轮契约修复（2026-10-26T13:5xZ，登记于相关实验之后）**。

## 1 VP-0014 independent-rerun 指标错配（Q3 迁移）

- VP-0014 把 `independent-rerun.metric` 冻结为 `constraint-satisfaction`。
- EXP-0080（迁移侧）实测主指标是 `nonincrease-rate`（逐列不增率 + QP 状态/残差），**该实验不存在 constraint-satisfaction**。
- 旧拒绝回执 `VMU_PACK_MODELING_CONTEST_VALIDATION_MISSING: experiment EXP-0080 records no numeric primary metric "constraint-satisfaction", so a rerun cannot be compared` 保留，不改写。
- 本轮只修正 **metricKey 与组件范围**，不改变候选、切分、约束、容差、指标定义或选择规则。

## 2 VP-0014 把 optimization 检查同时套到生成与迁移

- 生成侧（EXP-0079）**没有**对应的单一优化模型声明；它是 Copula + 约束投影生成器。
- 迁移侧（EXP-0080）实际是 **198 个 QP**（11 源 × 9 折 × 2 策略）+ `solver_certificates.jsonl`，不是原生检查要求的「单个模型 + 单个 solution.csv」形状。
- 旧拒绝回执 `VMU_PACK_MODELING_CONTEST_VALIDATION_MISSING: experiment EXP-0079/EXP-0080 records no optimization model (params.optimization), so feasibility/objective cannot be re-checked` 保留。
- 结论：原生 `optimization-feasibility` / `optimization-objective` 与当前批量产物形状**不兼容**；**本轮不声称它们已通过**，也不把单个 `params.optimization` 或单个 `solution.csv` 当作 198 个 QP 的完整证明。

## 3 VP-0012 baseline-compare 缺 baselineExperimentId

- VP-0012 的 `baseline-compare.params` 为空，工具硬拒绝 `baseline-compare needs params.baselineMetric or params.baselineExperimentId`。
- 修复计划显式写入 `baselineExperimentId = EXP-0074`（Q1 训练折中位数基线，已登记实验，真实 `mae=0.39817732837288883`）。
- 该拒绝回执保留。

## 4 EXP-0079/0080 未登记 params.features

- 插件公开接口同时接受 `checks[i].params.featureColumns`，因此可在**验证计划**里声明输入列，而不必改实验记录（实验记录不可改）。
- 本轮 `featureColumns` 为 **231 列**，来自四个独立来源逐项核对同序同集合（见 `.rework/contract-repair/feature_columns_231.json`）：
  1. 真实表头 `data/clean/q3.csv` 的 `chem__*` 列（285 列 = 4 标识 + 231 化学 + 50 目标）；
  2. 代码常量 `src/target_columns.py::FEATURE_COLS`（运行期由 `q3_fix.py` / `q3_transfer_fix.py` 的 `chem = [c for c in frame.columns if c.startswith(CHEM_PREFIX)]` 断言一致）；
  3. EXP-0079 自己冻结的输出 `experiments/EXP-0079/outputs.json::q3.column_state`（231 条，声明 `designColumns=231`）；
  4. EXP-0080 的 `experiments/EXP-0080/transfers.csv` 的 `opt__*` 列（231 条）。
- 四者**顺序与集合完全相同**，`features sha256 = 3bf8e6ee4096d628043c5b114deb0c57ef01d8f279fefac10487505cd7a6c5c5`。
- 只要发现 featureColumns 与实际输入不一致，就停止对应验证并修上游；不得用重跑无关实验掩盖。

## 5 旧拒绝回执的处理

- 全部保留：VAL-0058/0059（EXP-0079 leakage failed，feature-set-unknown）、VAL-0061（EXP-0080 leakage failed）、以及三次 `VALIDATION_MISSING` 拒绝（Q1 baseline-compare、Q1 holdout-metrics、Q3 optimization ×2、Q3 EXP-0080 rerun）。
- 本轮新增 VAL 只追加，不覆盖；旧记录不删除、不改写为 passed。

## 6 本轮登记的三个修复计划（公开 `modeling_validate plan`）

| 计划 | 组件 | 适用实验 | checks（全部 required，容差沿用 abs 1e-9 / rel 1e-6） |
|---|---|---|---|
| 新 Q1 计划 | Q1 全问 | EXP-0073（基线 EXP-0074） | split-integrity（params.splitId=NESTED-CV-1）、leakage、baseline-compare（baselineExperimentId=EXP-0074）、independent-rerun、holdout-metrics |
| 新 Q3 生成计划 | 生成 | EXP-0079 | leakage（metric=constraint-satisfaction，featureColumns=231）、independent-rerun（metric=constraint-satisfaction） |
| 新 Q3 迁移计划 | 迁移 | EXP-0080 | leakage（metric=nonincrease-rate，featureColumns=231）、independent-rerun（metric=nonincrease-rate） |

- 三个 `protocolNote` 均声明：登记于相关实验之后，是**验证契约修复**，不是首次预注册；不改变候选/切分/科学指标定义/约束/容差/选择规则；只修正组件范围、验证输入、实际 metricKey。
- Q1 的 split-integrity / holdout-metrics **保留为 required**，不降级、不删除；其 train-only 3×3×3 结构缺口继续如实披露，不用旧 SPLIT-0002 顶替。
- Q3 不再套用不存在的 optimization 检查；原生 optimization 通过与否**不声明**。

## 7 批量 QP（198 个）的科学核验口径

- 科学核验使用**全部** `solver_certificates.jsonl`（198 条）、`transfer_constraints.csv`（15048 条）、逐问题 `problem_hash`、primal/dual residual、KKT 残差、可行性/求解状态，以及本批的独立复算。
- **不**把独立复算写成原生 `optimization-feasibility/objective` VAL；它是一份审计（audit）证据，不是原生检查通过。
- 若以后需要原生 optimization 检查，应另建带**已知最优解的小例 oracle**；小例通过不能代替 198 个实际 QP 的验证。
- `new−source` 的位移（设计改动）与约束残差（越界量）在复算中**分开统计**，不混为一个数。

## 8 执行结果（真实 ID，2026-10-26T13:54Z–13:59Z）

| 组件 | 计划 | 检查 | 结果 | rerun |
|---|---|---|---|---|
| Q1 / EXP-0073 | VP-0015 | leakage | `VAL-0063` **passed**（231 列，max\|r\|=0.576180<0.999） | — |
| Q1 / EXP-0073 | VP-0015 | baseline-compare | `VAL-0064` **passed**（0.359291565882 vs EXP-0074 真实 0.398177328373，delta=0.0388857624907，minimize） | — |
| Q1 / EXP-0073 | VP-0015 | independent-rerun | `VAL-0065` **passed**（delta=0，确定性重现） | `EXP-0083` |
| Q1 / EXP-0073 | VP-0015 | split-integrity | 未执行：结构性不可满足（EXP-0073 无 splitId，先会话具名拒绝，不重复调用） | — |
| Q1 / EXP-0073 | VP-0015 | holdout-metrics | 未执行：结构性不可满足（train-only 嵌套 CV 无 holdout，先会话具名拒绝） | — |
| Q3 生成 / EXP-0079 | VP-0017 | leakage | `VAL-0066` **passed**（featureColumns 231 列，max\|r\|=0.401311） | — |
| Q3 生成 / EXP-0079 | VP-0017 | independent-rerun（constraint-satisfaction） | `VAL-0068` **passed**（delta=0） | `EXP-0084` |
| Q3 迁移 / EXP-0080 | VP-0016 | leakage | `VAL-0067` **passed**（featureColumns 231 列，max\|r\|=0.401311） | — |
| Q3 迁移 / EXP-0080 | VP-0016 | independent-rerun（nonincrease-rate） | `VAL-0069` **passed**（delta=0）——旧拒绝「no numeric primary metric constraint-satisfaction」被真实指标修复取代，未使用别名 | `EXP-0085` |

- Q3 原生 optimization-feasibility / optimization-objective **仍不通过、也不声明通过**；两侧 `params.optimization` 依旧缺失，旧拒绝保留。
- 选择：Q1 `MODEL-0048` = `provisional`（readiness blockers 恰为 missing fresh split-integrity + holdout-metrics）；Q3 `MODEL-0053` = `provisional`（生成组件 readiness eligible=true，但单一 selectedModelId 无法覆盖迁移组件，故不宣称 validated）；Q2 `MODEL-0050` 保持既有 `validated`，本批未动。

## 9 工具层缺陷（影响本批执行方式，如实记录）

- `modeling_validate {action:"independent-rerun", planId:...}` **不转发 planId**（`.rework/plugin/.../tools.js:630` 只传 experimentId/runs），因此该动作永远按「该问最新计划」的 metric 比较。第一次对 EXP-0080 执行即因此仍报 `no numeric primary metric "constraint-satisfaction"`（最新计划当时是 VP-0017 生成侧）。
- 可用路径：`modeling_validate {action:"run", planId:"VP-0016", checkTypes:["independent-rerun"]}`，该路径在 `validation.js:933` 转发了 `planRecord.id`，于是按 VP-0016 的 `nonincrease-rate` 执行并产生 `VAL-0069`。
- 这不是放宽标准：metric 由修复计划声明，未新增别名、未改实验记录、未改容差。

## 10 198 个 QP 的独立复算（audit，不是原生 VAL）

- 脚本：`src/q3_cert_audit.py`（sha256 `5a9f743b2810f2b451f53296897cb6a8ed770d0eb4b76d4aab498deec009cb04`），两次运行：`SCRIPT-0009` **failed**（第一版把存储空间位移当成 z 空间 `l1_change_z`，真实报错并保留）、`SCRIPT-0010` **succeeded**。
- 产物：`outputs/q3/qp_cert_audit.json`（sha256 `713b0143b0e085c8d699d1de3636d811e0ab8b25df187391578ccc6fcb5f0733`）、`qp_certificate_recompute.csv`、`qp_constraint_recompute.csv`。
- 结论：198 证书 / 198 唯一 `problem_hash` / 状态全 `optimal` / 策略各 99；最大约束违反 0、max primal `9.9897e-9`（< ADMM_TOL 1e-8）、max dual `3.3938e-10`、max KKT `5.617e-9`；记录聚合值逐项复算一致。
- 非增率：按生产代码声明的**物理空间**公式（`after <= before*(1+1e-9)+1e-12`，四列化学 + stale_hops）复算，逐列/逐行 flag 0 失配，逐策略率与记录逐位一致（source-fixed 1.0、qp-source-anchor 1.0、qp-quantile-anchor 1.0、target-mean-projection 0.41414141414141414）。
- 约束残差：15048 行、396 组 × 38 字段，`residual = clamp(new−source, 0)`（存储空间）复算，upper_source_value 与 lower_zero **0 失配**；`upper_source_value_proxy` 有 **4/396** 行相差 `1.0000004e-9`（边界舍入），如实报告未抹平。
- **分工**：位移（`stored_space_sum_abs_change_max=487.17`，99 行零位移）与约束残差（58 条违规记录、残差和 4.58）分开统计；记录的 `l1_change_z/mean_abs_change_z` 属 z 空间（centre/scale 未落盘），**无法由产物独立复算**，只核对了 `l1==0 ⇔ opt==src`（0 失配）——该限制写入 `qp_cert_audit.json.limitations`。
- 若以后要原生 optimization 检查：另建带**已知最优解**的小例 oracle，小例通过不代替这 198 个实际 QP。
