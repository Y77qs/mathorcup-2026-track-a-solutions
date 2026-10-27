# 验证与选择批次：断点续跑文件

项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`（本批只写 P；SOURCE 只读）
本文件只记录**真实 ID、状态、下一动作、blocker**。不复制台账，不粘贴大回执。
新会话恢复顺序：`modeling_project {action:"status", projectDir:P}` → 读本文件 → 读对应 VAL/EXP 原始记录。

## 0 批次范围（本批不做）

只做：Q2 analysisPlan 重配 → Q2 确认轮验证与选择 → Q3 生成/迁移分别验证与双对象选择 → Q1 剩余可执行验证。
**不做**：ROB、claim/coverage、论文、交付包。后续事项未开始**不构成本批失败**。

## 1 恢复时的现场（2026-10-26T13:40Z 快照）

- 业务 revision=4175，runtimeRevision=412；`stage=intake`（七检查点里只有 validation 未过，其余 ok）。
- `quality.runControl.activeRunId=RUN-0003`，status=`running`，budget `{soft:null,hard:null}`；RUN-0001=`stopped/budget`、RUN-0002=`stopped/no-progress`（历史保留，不改）。
- 实验：80 条 = 64 succeeded + 10 failed + 6 queued（EXP-0027/0045/0046/0047/0059/0061，均 `queued: never started`）。**无 running 实验**。
- 验证：55 条；验证计划 14 条。Q1 最新计划 VP-0012，Q2 最新 VP-0013，Q3 最新 VP-0014。
- 选择现状：
  - Q1 `selectedModelId=MODEL-0048`，`selectionStatus=provisional`，evidence 仅 `VAL-0055`（selectedAt 2026-10-26T13:33:34.781Z）。
  - Q2 `selectedModelId=MODEL-0047`，`selectionStatus=validated` —— **仍绑先导轮 VAL-0053/0054，本批必须改为确认轮实际模型**。
  - Q3 `selectedModelId=MODEL-0029`，`selectionStatus=provisional`（先导轮），本批处理双对象。
- 已确认可用证据：`VAL-0055`（EXP-0073 independent-rerun，rerun=`EXP-0078`，delta=0，passed，stale=false）。
- `EXP-0073` 的 split-integrity：工具硬拒绝 `VALIDATION_MISSING: experiment EXP-0073 records no split to check`（已发生，**不重复调用**，也不挂旧 SPLIT-0002）。

## 2 本批任务清单（按依赖顺序）

| # | 动作 | 状态 |
|---|---|---|---|
| A | Q2 analysisPlan 重配 | **DONE** 13:41:08.934Z，rev 4176，features=231 unique=231，excluded=54 unique=54，metricDirection=maximize，sha256=`80cc1044f6415593c99086fae2c83f5fe2934a7ec692e5cb0ad267f227b647df`。**限制**：工具未持久化 `source`（回执 source=null） |
| B | EXP-0075 VP-0013 leakage + independent-rerun | **DONE** `VAL-0056` leakage passed（231 列，max\|r\|=0.576180）；`VAL-0057` rerun passed（rerun=`EXP-0081`，delta=0，fixed-seed-reproduction） |
| C | Q2 选择 | **DONE** `MODEL-0050` / `validated`，readiness eligible=true blockers=[]，evidence=VAL-0056,VAL-0057，13:42:51.243Z |
| D | EXP-0079 生成侧 VP-0014 | **部分**：`VAL-0060` rerun passed（rerun=`EXP-0082`，constraint-satisfaction=1，delta=0）；`VAL-0058`+`VAL-0059` leakage **failed**（feature-set-unknown）；optimization-feasibility/objective **硬拒绝**（无 params.optimization） |
| E | EXP-0080 迁移侧 VP-0014 | **部分**：`VAL-0061` leakage **failed**（feature-set-unknown）；optimization 两项硬拒绝；independent-rerun **硬拒绝**（VP-0014 冻结指标 constraint-satisfaction 在 EXP-0080 不存在） |
| F | Q3 双对象选择 | **DONE（provisional）** `MODEL-0053` / `provisional`，readiness eligible=false，blockers=[missing fresh leakage / optimization-feasibility / optimization-objective for EXP-0079]，13:45:20.415Z；迁移侧只能由 reason + 本文件表示 |
| G | EXP-0073 leakage | **DONE** `VAL-0062` passed（231 列，max\|r\|=0.576180） |
| H | EXP-0073 vs EXP-0074 baseline-compare | **硬拒绝** `baseline-compare needs params.baselineMetric or params.baselineExperimentId`（VP-0012 params 为空）；台账派生差值另存回执，非验证通过 |
| I | Q1 holdout-metrics 一次回执 | **DONE** 硬拒绝 `experiment EXP-0073 records no split, so there is no holdout ground truth` |
| J | 最终矩阵 + 定稿 | **DONE** |

## 3 本批结果矩阵（真实 ID）

| experiment/model | required checks / VAL | rerun EXP / VAL | readiness | selectionPhase / reason | 剩余 blocker |
|---|---|---|---|---|---|
| EXP-0075 / MODEL-0050（Q2） | leakage `VAL-0056` **pass**；independent-rerun `VAL-0057` **pass** | `EXP-0081` / `VAL-0057` | eligible=true，blockers=[] | `validated`，evidence VAL-0056/0057 | 无（限制：rerun=确定性重现；6.csv 非外部独立验证；analysisPlan.source 未持久化） |
| EXP-0079 / MODEL-0053（Q3 生成） | leakage `VAL-0058`/`VAL-0059` **fail**（feature-set-unknown）；optimization-feasibility **refused**；optimization-objective **refused**；independent-rerun `VAL-0060` **pass** | `EXP-0082` / `VAL-0060` | eligible=false，blockers=[fresh leakage, opt-feasibility, opt-objective] | `provisional`（双对象只能表示生成侧） | 实验未登记 params.features 与 params.optimization |
| EXP-0080 / MODEL-0054（Q3 迁移） | leakage `VAL-0061` **fail**（feature-set-unknown）；optimization-feasibility **refused**；optimization-objective **refused**；independent-rerun **refused** | 无（拒绝：无 constraint-satisfaction 指标） | 不可达（单字段无法表示） | 仅由 Q3 reason + 本文件登记，**不**单列选择 | 无 params.optimization；VP-0014 用一个指标覆盖两个组件 |
| EXP-0073 / MODEL-0048（Q1） | leakage `VAL-0062` **pass**；baseline-compare **refused**；holdout-metrics **refused**；split-integrity 先会话已 refused；independent-rerun `VAL-0055` **pass** | `EXP-0078` / `VAL-0055` | 结构性不可满足 | 保持 `provisional`，**本批不重复写选择** | 无 holdout；EXP-0073 未登记 splitId；baseline-compare 缺 baselineExperimentId；VALID-0062 未回写 selectionEvidence（因禁止重复 select） |
| EXP-0074 / MODEL-0049（Q1 基线） | 仅作为 baseline-compare 目标；比较被拒 | — | — | 未选择 | 同上 |

## 4 已知结构性缺口（真实具名，不假装通过）

- Q1 `holdout-metrics`：train-only 3×3×3 嵌套 CV 无 holdout，工具具名拒绝；不挂旧 SPLIT-0002（曝光 3/3）。
- Q1 `split-integrity`：EXP-0073 无 splitId，工具具名拒绝（先会话已发生，本批不重复调用）。
- Q1 `baseline-compare`：VP-0012 检查 params 为空，工具要求 baselineExperimentId/baselineMetric；计划不可编辑。
- Q3 `leakage`：EXP-0079/EXP-0080 均未登记 feature 列表，工具判 **failed（feature-set-unknown）**，明确「不是 pass」。
- Q3 `optimization-feasibility/objective`：两侧实验均无 `params.optimization`，工具硬拒绝；求解状态/证书不等同模型声明。
- Q3 `independent-rerun`（迁移侧）：VP-0014 把 independent-rerun 指标冻结为 constraint-satisfaction，迁移侧主指标是 nonincrease-rate，故无法比较。
- Q3 双对象：`questions[Q3].selectedModelId` 只能有一个值，迁移侧缺公认可寻址表示。
- `VAL-0058` 与 `VAL-0059` 同为 EXP-0079 leakage 失败记录（首次合并调用先落了 leakage 再因 optimization 声明中止）；保留两条，不删除历史。

## 5 更新日志

- 2026-10-26T13:40Z 建立本文件，记录恢复现场与任务清单。
- 2026-10-26T13:41Z A 完成（Q2 features 231 重配）。
- 2026-10-26T13:43Z B/C 完成（EXP-0075 两项 pass；MODEL-0050 validated）。
- 2026-10-26T13:45Z D/E/F 完成（Q3 两侧可跑项跑完，优化两项硬拒绝；双对象 provisional）。
- 2026-10-26T13:46Z G/H/I 完成（Q1 leakage pass；baseline-compare、holdout-metrics 具名拒绝）。
- 2026-10-26T13:47Z J 完成，本批收口。大回执存于 `.rework/validation-selection/`。

## 6 本批边界（不构成失败）

本批**未开始**：ROB、claim/coverage、论文、交付包。这些是后续批次事项。
本批**未做**：修改任何历史 EXP/VAL/VP/selection 记录、重跑先导实验、新建验证计划来绕过具名拒绝。

---

## 7 第二批：验证契约修复（2026-10-26T13:54Z–14:00Z，同一 RUN-0003）

说明文件：`.rework/VALIDATION-CONTRACT-REPAIR.md`；231 列清单：`.rework/contract-repair/feature_columns_231.json`。

| experiment | 新 VP | featureColumns 来源 | required checks / VAL | rerun EXP / VAL | readiness | 当前选择 | 剩余 blocker |
|---|---|---|---|---|---|---|---|
| EXP-0073（Q1） | VP-0015（契约修复，2026-10-26T13:54Z 登记） | 实验自身 `params.features`（231 列，逐项与 q1_mapped 表头/代码一致） | leakage `VAL-0063` pass；baseline-compare `VAL-0064` pass（对 EXP-0074 真实 mae 0.398177）；independent-rerun `VAL-0065` pass；split-integrity 不可满足；holdout-metrics 不可满足 | `EXP-0083` / `VAL-0065`（确定性重现） | eligible=false，blockers=[missing fresh split-integrity, missing fresh holdout-metrics] | `MODEL-0048` **provisional**（readiness 由 select 写入 2026-10-26T13:59:24.376Z） | 无 splitId；train-only 无 holdout |
| EXP-0079（Q3 生成） | VP-0017（契约修复） | 四源逐项核对 231 列（q3.csv 表头 / target_columns.FEATURE_COLS / EXP-0079 column_state / EXP-0080 opt__ 列），sha256=`3bf8e6ee…c6c5c5` | leakage `VAL-0066` pass（max\|r\|=0.401311）；independent-rerun(constraint-satisfaction) `VAL-0068` pass | `EXP-0084` / `VAL-0068` | eligible=true，required=[leakage, independent-rerun] | `MODEL-0053` **provisional**（生成组件 eligible，但双对象不能表示，2026-10-26T13:59:33.420Z） | 原生 optimization 不通过、不声称；迁移组件无独立选择字段 |
| EXP-0080（Q3 迁移） | VP-0016（契约修复） | 同上 231 列 | leakage `VAL-0067` pass；independent-rerun(**nonincrease-rate**) `VAL-0069` pass | `EXP-0085` / `VAL-0069` | 工具按「问最新计划」计算，无法单独读（见下） | 由 Q3 reason + 本文件登记，不单列选择 | 原生 optimization 不通过、不声称；readiness 无独立可寻址字段 |
| Q2 / EXP-0075 | VP-0013（上一批） | 231 列 analysisPlan | `VAL-0056`/`VAL-0057` pass | `EXP-0081` / `VAL-0057` | eligible=true | `MODEL-0050` **validated**（本批未动） | — |

- 198 QP 独立复算：`SCRIPT-0010` succeeded，`outputs/q3/qp_cert_audit.json` sha256=`713b0143…0733`；198 证书全 optimal、198 唯一 hash、max violation 0、max primal 9.99e-9、max dual 3.39e-10；非增率逐策略与记录一致；残差复算 upper/lower 0 失配、proxy 4/396 差 1e-9（已披露）。**不是**原生 optimization VAL。
- `SCRIPT-0009` failed 保留（第一版把存储空间位移误当 z 空间位移，真实报错）。
- 工具缺陷：`action:"independent-rerun"` 不转发 planId；改用 `action:"run"` + `checkTypes:["independent-rerun"]`。详见修复说明 §9。
- 状态收口：revision 4225，RUN-0003 running，无遗留 queued/running 验证作业（仅 6 个历史 `never started` EXP）。

---

## 8 第三批：QP 口径澄清 + 确认轮稳健性（2026-10-26T14:00Z–14:22Z，同一 RUN-0003）

### 8.1 两项 QP 口径（详见 `.rework/QP-EVIDENCE-CLARIFICATION.md`）

- z 空间位移：`SCRIPT-0011` 用**冻结快照 + 确定性代码**重建 9 组 `centre/scale`，396 行 `l1_change_z/mean_abs_change_z` 全部 delta=0 → 可复现；仍**不**证明 QP 目标/最优性。
- 58 条违规：全部是 `stale_hops(ridge-proxy)`、`bound_type=upper_source_value_proxy`、且**只出现在 target-mean-projection 参照控制**（QP 策略 0 条）；残差和 4.58 全来自这 58 条；与 `max_constraint_violation=0`（198 个 QP 的 box+半空间）**不是同一对象**。
- `upper_source_value_proxy` 的 4/396 行 1e-9 差异保留（记录用 `max(0,Δ−1e-9)`、审计用 `max(0,Δ)`）；`SCRIPT-0009/0010` 失败与差异原样保留。

### 8.2 确认轮 ROB（先导 ROB-0001..0006 不转移）

| ROB | 对象 | 计划登记 | 参考 / 扰动 EXP | 指标与极差 | decisionPassed | 限制 |
|---|---|---|---|---|---|---|
| ROB-0007 | Q1 MODEL-0048 / EXP-0073 | 2026-10-26T14:06:35.757Z | ref `EXP-0086`；seed `EXP-0087`(repeat1/seed26)；lambda `EXP-0098`(λ网格×0.5) | mae 0.354224 / 0.362434 / 0.357635，spread 0.008210 ≤ 0.05 | **true** | 无 holdout/splitId 不改；只跑 2/3 冻结种子；rerun≠稳健性 |
| ROB-0008 | Q2 MODEL-0050 / EXP-0075 | 14:06:44.685Z | ref `EXP-0089`；seed `EXP-0090`；budget `EXP-0091`(500→200) | topk-jaccard 0.210333/0.207333/0.205333，spread 0.005000 ≤ 0.10 | **true** | Jaccard≠准确率；6.csv 非同源外部验证；seed 对同时改变 bootstrapSeed |
| ROB-0009 | Q3 生成 EXP-0079 | 14:06:52.880Z | ref `EXP-0092`；seed `EXP-0093`；kappa `EXP-0099`(KAPPAS 0/10/20) | energy-distance 0.877784/0.876453/0.898155，spread 0.021702 ≤ 0.05 | **true** | constraint-satisfaction=1.0 是构造性质，不作稳定性证据；生成≠迁移 |
| ROB-0010 | Q3 迁移 EXP-0080 | 14:07:01.242Z | ref `EXP-0095`；seed `EXP-0096`；lambda `EXP-0097`(LAMBDA 2.0) | nonincrease-rate 1/1/1，min 1 ≥ 1（新登记阈值，执行前披露） | **true** | 指标饱和；58 条只属参照控制；原生 optimization 仍未通过 |

- 产物：`outputs/q1/robustness_confirmatory.json`、`outputs/q2/robustness_confirmatory.json`、`outputs/q3/robustness_generation_confirmatory.json`、`outputs/q3/robustness_transfer_confirmatory.json`、`outputs/robustness/INDEX-confirmatory.json`（`SCRIPT-0013` 生成，全部数值取自台账）。
- 保留历史：`EXP-0088`/`EXP-0094` 是执行过的真实实验，但其参数改动写在数组型参数里，pack 的 input-signature 忽略数组 → 不能作为 param-perturbation 证据；改用标量 `lambdaMultiplier`/`kappaShift` 重新登记 `EXP-0098`/`EXP-0099` 并执行。两者均保留，不删除。
- 工具/契约事实：`modeling_experiment register` 会拒绝未声明的特征（两次笔误被具名拒绝，未落任何实验记录）；`robustness-plan-execute` 只认可标量参数变化。
- 状态：revision 4385；RUN-0003 running；无遗留 queued/running 稳健性作业（仅 6 个历史 `never started` EXP）。

---

## 9 第四批：claim / coverage 重建（2026-10-26T14:34Z–14:36Z，同一 RUN-0003）

### 9.1 复算说明修正

`SCRIPT-0014` 重跑修正版 `src/r04_independent_recompute.py`（脚本 sha256 `55cf2689…`），输出 `.rework/R04-independent-recompute.json` sha256 `65dda05d009cc8da07ee4e043b4f8eae15855a8bcd6172ba20757d6693c86eff`；π 定义、edge-fraction、约束残差 vs new−source、V/U 分离、确定性重现语义均已改正，并把 `QP-EVIDENCE-CLARIFICATION` + `SCRIPT-0010/0011` 纳入 `evidence_index`。旧 `SCRIPT-0009` failed 与 4/396 的 1e-9 差异保留。

### 9.2 claim 映射（新 CLAIM 与旧 CLAIM 处理）

| 范围 | 新 CLAIM | EXP / VAL / ROB | 旧 CLAIM 处理 |
|---|---|---|---|
| Q1 主结论 | `CLAIM-0040` | EXP-0073 + EXP-0074；VAL-0063/0064/0065；ROB-0007 | CLAIM-0036 → superseded |
| Q2 主结论 | `CLAIM-0041` | EXP-0075；VAL-0056/0057；ROB-0008 | CLAIM-0037 → superseded |
| Q3 生成 | `CLAIM-0042` | EXP-0079；VAL-0066/0068；ROB-0009 | CLAIM-0038 → superseded |
| Q3 迁移 | `CLAIM-0043` | EXP-0080；VAL-0067/0069；ROB-0010 + SCRIPT-0010/0011 | CLAIM-0039 → superseded |
| Q1 稳健性 | `CLAIM-0044` | EXP-0086/0087/0098；ROB-0007 | —（旧稳健性 CLAIM-0030/0032 早已 superseded/retracted） |
| Q2 稳健性 | `CLAIM-0045` | EXP-0089/0090/0091；ROB-0008 | — |
| Q3 生成稳健性 | `CLAIM-0046` | EXP-0092/0093/0099；ROB-0009 | — |
| Q3 迁移稳健性 | `CLAIM-0047` | EXP-0095/0096/0097；ROB-0010 | — |

### 9.3 requirement coverage（真实映射）

| REQ | coverage | refs | 可见限制 |
|---|---|---|---|
| REQ-0001 | covered | CLAIM-0040, EXP-0073, q1_grade_summary.json, src/q1_fix.py | split-integrity/holdout-metrics 不可满足、provisional；见 CLAIM-0040 limitations |
| REQ-0002 | covered | CLAIM-0041, EXP-0075, top3_report.json, factor_analysis.csv, src/q2_fix.py | 集合一致性≠准确率、6.csv 非外部、216/15 分表 |
| REQ-0003 | covered | CLAIM-0042, EXP-0079, q3_metrics.csv, src/q3_fix.py | 1.000 为构造性质、source-resample 更优、无原生 optimization VAL、双对象限制 |
| REQ-0004 | covered | CLAIM-0043, EXP-0080, transfer_constraints.csv, qp_cert_audit.json, src/q3_transfer_fix.py | 指标饱和、58 条仅属参照控制、残差≠位移、不报告迁移准确率 |
| REQ-0005 | **insufficient_data** | report/paper.md（仅指针） | 本批不做论文/交付，未 render/check，不以文件存在冒充覆盖 |
| REQ-0006 | covered | EXP-0080, src/q3_transfer_fix.py, REPRODUCE.md, solver_certificates.jsonl | 只覆盖可追溯，不覆盖独立复现审查 |
| REQ-0007 | **insufficient_data** | CLAIM-0040/0043, FIG-0001 | 结论-指标绑定已建立；图表标注一致性未核验 |

- 一致性核对：`modeling_claim check-stale` → claimsNewlyMarked = 0（新 claim 均非 stale）；`list(stale:true)` 返回 7 条全部是**已 retracted 的历史 claim**，8 条新 claim 不在其中。
- 无 claim/coverage 引用退休对象（新 claim 只引用 EXP-0073/0074/0075/0079/0080/0086–0099 与 active FIG-0001）。
- 状态：revision 4406；RUN-0003 running；本批未创建 review、未运行 quality-run、未进入论文或 delivery。

---

## 10 第五批：独立复审与 findings 处理（2026-10-26T14:54Z–15:11Z，同一 RUN-0003）

独立复审员：`reviewer-1`（fresh context，memberId 2492c073…；全部 review 的 provenance.isRoot=false、independence=independent_context）。root 未代填任何 method/findings/verdict。

### 10.1 复审对象与结果（26 条 REV）

| objectType / objectId | REV | verdict | findings → resolution |
|---|---|---|---|
| claim CLAIM-0040 | REV-0049 | findings | F1(minor) 相对/绝对极差混写 → CLAIM-0048 supersede 修复 |
| claim CLAIM-0041 | REV-0050 | **passed** | — |
| claim CLAIM-0042 | REV-0051 | findings | F1(major) 0.884026 被写成三风格 scope → CLAIM-0049 → 再修 0054（177 格/729 n_gen） |
| claim CLAIM-0043 | REV-0052 | findings | F1/F2(minor) 位移未点名策略/max、QP 边界 → CLAIM-0050 → 再修 0055 |
| claim CLAIM-0044/0045/0046 | REV-0053/0054/0055 | findings | 相对/绝对极差 → CLAIM-0051/0052/0053 |
| claim CLAIM-0047 | REV-0056 | **passed** | — |
| requirements-coverage | REV-0057 → REV-0069 → REV-0073 → **REV-0074** | findings→**passed** | REQ-0004 双阈值/Pareto 无证据 → 降 insufficient_data；REQ-0002 化学证据补 modules；superseded ref 逐条改指 active claims |
| ROB-0007 | REV-0058 | findings | F1(major) 分母=1 口径 → claims 分列绝对/相对；F2 wrapper 版本漂移（已披露+下批重跑）；F3 note repeats 笔误（claims 更正） |
| ROB-0008/0009 | REV-0059/0060 | findings | 同上相对极差口径 → CLAIM-0052/0053 |
| ROB-0010 | REV-0061 | **passed** | — |
| experiment EXP-0080 | REV-0062 | **passed** | 198 唯一 hash/198 optimal/残差/KKT/58 条归属均独立复算一致 |
| claim CLAIM-0048/0051/0052/0053 | REV-0063/0066/0067/0068 | **passed** | — |
| claim CLAIM-0049/0050 | REV-0064/0065 | findings | 885→177 格、补 V/NN/edge ref → CLAIM-0054；目标补 rank-10 二次+anchor → CLAIM-0055 |
| targetContract TGT-0002 | REV-0070 | **passed** | 216+15 分表、6.csv 同源 |
| claim CLAIM-0054/0055 | REV-0071/0072 | **passed** | — |

### 10.2 契约与产物
- `TGT-0002` 经公开 `contract-revise` 修订到 revision 2（219→216 严格 + 15 扩展；6.csv 非外部）。
- 新增 `outputs/q3/style_and_displacement_scope.json`（SCRIPT-0018，sha256 `b7881974…`，recordedAt 合法）：21 风格 177 可估格 n_gen=729 → 0.8840256215；Tripel/Kriek/Lambic 27 格 n_gen=147 → 1.8305764927；qp-quantile-anchor 逐列 max/mean 位移；Pareto 输入。
- 开放 findings = **0**（26 条 review 中所有 findings 均经 review-resolve 且 resolved=true）。

### 10.3 当前状态与遗留
- active claims：`CLAIM-0041/0047/0048/0051/0052/0053/0054/0055`；旧 0036–0039、0040/0042–0046、0049/0050 均 superseded（历史保留）。
- coverage：REQ-0001/0002/0003/0006 covered；REQ-0004/0005/0007 insufficient_data（具名 blockedReason）。
- 遗留（不影响本批结论，交付前处理）：①REQ-0001..0004 记录 stale=true（sourceSha256=null，freshness 标记）；②`frozen` 仍是 10-24 旧身份、QC-0020 会因 paper 引用旧 claim 失败，需下次 freeze/render；③ROB-0007 的 EXP-0086/87 与 EXP-0098 wrapper 版本漂移（数值已证不变，若质量平面要求同一代码身份需重跑）；④Q3 `outputs/q3/decision.md`、`robustness.json` 仍是先导轮文本。
- 本批未运行 quality-plan/stale/run，未改论文/交付，未做整体 READY 判定；revision 4484，无遗留 queued/running 作业（仅 6 个历史 never-started EXP）。

---

## 11 第六批：ROB-0007 来源一致性修复 + quality 刷新（15:16Z–15:2xZ，RUN-0003）

- **ROB-0011**（15:16:37.780Z 登记，provenance-repair，非首次预注册）：EXP-0100(ref repeat0)/EXP-0101(seed repeat1)/EXP-0102(λ×0.5 标量 lambdaMultiplier)，三条统一 wrapper `7d7ab6aca6c2`；decisionRule 无自由文本 reference → 插件原生 **relative spread 0.023178 ≤ 0.05**，decisionPassed=true，values 0.354224/0.362434/0.357635 与旧 ROB-0007 逐位相同。旧 ROB-0007 及其分母=1 口径限制原样保留。
- claim：**CLAIM-0056**(supersede 0048，绑 ROB-0011+VAL-0063/64/65)、**CLAIM-0057**(supersede 0051，绑 ROB-0011)；REQ-0001→CLAIM-0056，REQ-0007→CLAIM-0056/0055（仍 insufficient_data）。
- Q3 文档由 **SCRIPT-0021** 从台账重生成：`outputs/q3/decision.md`（sha256 5a72e311…）、`outputs/q3/robustness.json`（sha256 b9ee2647…）；修正「残差 vs 位移」与相对极差标签，先导轮不拼接。
- 独立复审（reviewer-1，isRoot=false/independent_context）：REV-0075 ROB-0011 **passed**；REV-0077 CLAIM-0057 **passed**；REV-0078 coverage **passed**；REV-0076 CLAIM-0056 **findings（minor，F1 未解决）**：refs 缺 EXP-0074:mae 与 EXP-0073:mae_all50（数值已复算一致）→ 下一批补 refs 并复审（本批不擅自改动已审版本）。
- quality 刷新（plan auto → stale → run → report）：**qualityPassed=false**；45 项 = passed 30 / failed 2 / needs_review 12 / stale 1 / not_applicable 0；criticalOpen 0；requirements covered 4/7。
  - failed：QC-0020（paper 仍引 6 条 retired claim：CLAIM-0012/0014/0018/0019/0021/0022，交付阶段修）、QC-0033（EXP-0017/0018/0026/0035/0036 缺 feature manifest，历史/插件结构，禁止 retrofit）。
  - needs_review：QC-0002（REQ 有具名 insufficient_data）、QC-0003（TGT-0001 需独立 derivation review）、QC-0041/0043/0044/0045 + QC-0036–0040/0042（无 registered split 的 metric-recompute，结构性不可满足）。
  - stale：QC-0031（runcontrol-budget，可选检查）。
  - selection：Q1 provisional（MODEL-0048）、Q2 validated（MODEL-0050）、Q3 provisional（MODEL-0053）。
- 判定：**READY_FOR_DRAFT_PAPER_ONLY**。下一批唯一优先项：补 CLAIM-0056 的 2 个 refs 并复审，然后进入论文阶段；QC-0020/QC-0033 与 REQ insufficient_data 属 DRAFT 可披露范围。
