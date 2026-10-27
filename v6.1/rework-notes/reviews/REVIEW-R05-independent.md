# REVIEW-R05 确认轮独立复审（14 个台账对象，MathorCup 2026 A）

- 审查者：`reviewer-1`（fresh context，team member；与 root 无共享推理）
- 项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`；复审时台账 revision **4421**（REV-0049..REV-0062 已写入，台账现 revision 仍为 4421，因为 14 条 review 是顺序追加）
- 唯一写入：14 条 `modeling_project{action:"quality",subaction:"review-add"}` + 本文件。未改 claim/contract/coverage/robustness 记录，未跑 quality-plan/run/stale，未 render/package，未碰论文与交付，未删历史。
- 方法：全部数字用绑定解释器 `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python`（3.12.14, numpy 2.3.5/pandas 2.2.3）从原始产物重算；不采信 statement、`.rework/R04-independent-recompute.json` 或 audit 自述。

---

## 0 14 条复审一览

| # | review | objectType | objectId | verdict | findings |
|---|---|---|---|---|---|
| 1 | REV-0049 | claim | CLAIM-0040 | findings | F1 minor |
| 2 | REV-0050 | claim | CLAIM-0041 | passed | — |
| 3 | REV-0051 | claim | CLAIM-0042 | findings | F1 **major** |
| 4 | REV-0052 | claim | CLAIM-0043 | findings | F1 minor, F2 minor |
| 5 | REV-0053 | claim | CLAIM-0044 | findings | F1 minor |
| 6 | REV-0054 | claim | CLAIM-0045 | findings | F1 minor |
| 7 | REV-0055 | claim | CLAIM-0046 | findings | F1 minor |
| 8 | REV-0056 | claim | CLAIM-0047 | passed | — |
| 9 | REV-0057 | requirements-coverage | project-requirements-set | findings | F1 **major**, F2 minor |
| 10 | REV-0058 | robustnessPlan | ROB-0007 | findings | F1 **major**, F2 minor, F3 minor |
| 11 | REV-0059 | robustnessPlan | ROB-0008 | findings | F1 **major** |
| 12 | REV-0060 | robustnessPlan | ROB-0009 | findings | F1 **major** |
| 13 | REV-0061 | robustnessPlan | ROB-0010 | passed | — |
| 14 | REV-0062 | experiment | EXP-0080 | passed | — |

major findings 共 5 条（CLAIM-0042、REQ-0004、ROB-0007/0008/0009 的 relative-range 口径），critical 0 条。没有 rejected。

---

## 1 CLAIM-0040（Q1）— findings，F1 minor

独立复算：

- `experiments/EXP-0073/oof_long.csv`（150000 行）按 `model=graph-lowrank`、`target` 前缀 `A_/F_` 取 22500 行：**A/F30 MAE=0.359291565882**、全 50 维 **0.350504156920**，与 `EXP-0073/metrics.json` 的 `mae` / `mae_all50` 逐位一致。
- 同文件 `model=median` 的 A/F30 MAE=**0.398177328373**，与 `EXP-0074/metrics.json` 的 `mae=0.398177328373`（`n_targets_af30=30`）一致；差 **0.038885762491**。
- `VAL-0064.result.details.checkParams={baselineExperimentId:"EXP-0074",mode:"improve",baselineMetric:"mae"}` —— baseline-compare **真用 EXP-0074**，不是 EXP-0073 内嵌基线。`VAL-0063` leakage 231 列 max|r|=0.576180；`VAL-0065` rerun=EXP-0083 delta=0（fixed-seed reproduction）。
- `questions[Q1].selectionStatus=provisional` + `selectionReason` 明写 split-integrity（EXP-0073 无 splitId、工具具名拒绝）与 holdout-metrics（train-only 嵌套 CV 无 holdout）两个结构性缺口；与 claim limitations 一致，未写成 validated。
- `claimType=contemporaneous_association` 对 TGT-0001（`taskNature=severity_estimation`、同期输入）与 Q1 `profile=prediction` 不构成未来预测/因果越界；A/F30 与全 50 指标分列、未混用；ROB-0007 只有 2/3 冻结种子（repeat 0/1），claim 已披露。
- **F1**：statement 的“相对极差 0.008210”实为 `result.spread`（绝对极差）。ROB-0007 的 `decisionRule.reference` 是文本，插件 `num()→null` 后按分母 1 执行；按该计划声明的 reference=首个实验 0.35422354618559243 重算，相对极差=**0.023178**（仍 ≤0.05，decisionPassed 不变）。建议改为“极差 0.008210 / 相对极差 0.023178”。

---

## 2 CLAIM-0041（Q2）— passed

独立重算：

- **Jaccard**：`experiments/EXP-0075/repeat{0,1,2}/sets.json`（各 50 维×4 方法），每维 6 个方法对算 `|A∩B|/|A∪B|` 再对 50 维平均 → **0.210333333333 / 0.207333333333 / 0.209666666667**，池化 **0.209111111111**；`topk-jaccard-point`=**0.197666666667**（`repeat0/outputs.json` 的 `q2.jaccard.pointEstimateSets` 6 对均值；三重复 point 相同）。与 `metrics.json` 逐位一致。
- **π**：`repeat{0,1,2}/bootstrap_pi.csv` 按 distinct `bootstrap_id` 出现次数/500 重算，对 delivered point Top-3 的 600 项/重复求均值 → 0.418603333 / 0.420806667 / 0.421960，池化 **0.420456667**；π<0.5 = 423+419+421 = **1263/1800**，与 `pi_mean`/`pi_below_0.5_*` 一致。
- **sign_stability**：每个 repeat 的 `outputs.json:q2.top3_strict` 600 条 `sign_stability` 均值 0.720313333/0.724656667/0.722693333，池化 **0.722554**，与 `metrics.json` 一致。
- **validated 背书**：VAL-0056/0057 的 `validationPlanId=VP-0013`；VP-0013 的 required 恰为 leakage + independent-rerun，二者均 passed（rerun=EXP-0081，delta=0）。因此 Q2 `validated` 是确认轮两项 required 检查背书，不是继承先导轮。
- **216/15 分表**：`n_strict_candidates=216`、`n_extended_candidates=15`；Q2 `analysisPlan.features=231` 与 EXP-0075 `params.features=231` 一致；`outputs.external_6csv.status` 明写“SAME-SOURCE corroboration, NOT independent external validation”，不参与选择。
- **Q2 `analysisPlan.source=null` 的影响判断**：按 `runtime/workbench.js`，`source` 只在 `scoring` 定义存在时才必需并持久化（`if (p.scoring) { ... p.source ... }`）；Q2 `profile=factor-analysis`、`scoring=null`，所以 source=null 是预期缺省。它不影响 CLAIM-0041 的任何数值/验证链；`selectionReason` 的“评分原文未被工具持久化”只是记录说明，不是证据缺口。**不立 finding。**
- 未发现 claim/coverage 引用 superseded/retracted 对象；limitations 已含 Jaccard≠准确率、6.csv 非外部验证、500→200 预算扰动、关联≠因果、确定性重现、ROB-0008 仅 2/3 种子。

---

## 3 CLAIM-0042（Q3 生成）— findings，F1 **major（scope）**

已核对并全部一致的数字（来自 `EXP-0079/metrics.json` / `outputs.json`）：

| 量 | claim | 实测 |
|---|---|---|
| energy-distance | 0.884026 | 0.8840256215 |
| energy-distance-raw | 0.884296 | 0.8842957424 |
| energy-V-raw | 16.182791 | 16.1827914328 |
| energy-U-signed | 1.113867 | 1.1138668333 |
| diversity | 19.735647 | 19.7356471944 |
| duplicate-share | 0.000 | 0.0 |
| nearest-neighbor | 17.632 | 17.6323085333 |
| edge-fraction | 0.119913 | 0.1199134199 |
| constraint-satisfaction / raw | 1.000 / 0.113333 | 1.0 / 0.1133333333 |
| source-resample energy-distance | 0.813731 | 0.8137313224 |

`outputs.q3.constraint_definitions` 的 V/U/duplicate/edge/density 定义与 claim 的“edge-fraction=声明边界单元格比例、非贴边比例”表述一致；constraint-satisfaction=1.000 的构造性质、source-resample 更优、无原生 optimization VAL、双对象 provisional、2/3 种子均已披露；VAL-0066/0068 passed。

**F1（major）**：从 `experiments/EXP-0079/q3_metrics.csv`（1980 行）取 `stage=design, model=copula-selected` 的 198 格，按 `n_gen` 加权：

- 177/198 格可估（21 个风格；Faro 9 格 `n_real=n_gen=1` 不可估），**全风格加权=0.8840256215**，与 metrics 一致；
- 只取 Tripel/Kriek/Lambic 的 27 格，加权 **E_V_norm=1.830576493**，约为池化值的 **2.07 倍**。

但 claim 的 `quality.scope` 与 `appliesTo.note` 把 0.884026 限定为 “generated design spectra vs real Tripel/Kriek/Lambic cells / for Tripel/Kriek/Lambic”。statement 的“风格整类留出”只描述生成协议，不是该数字的估计域；REQ-0003 还要求三个未见风格“单独报告”，当前 claim 没有区分池化值/三风格值。修法：改 scope/note 为“all 21 estimable styles pooled”，并用 `q3_metrics.csv` 的 27 格单列三个未见风格的能量距离。

---

## 4 CLAIM-0043（Q3 迁移）— findings，F1/F2 minor

独立核对：

- **证书**：`experiments/EXP-0080/solver_certificates.jsonl` 198 行 / **198 唯一 64hex problem_hash**；status `{optimal:198}`；策略 99+99；feasible 全 true；**max primal=9.989717497660422e-09、max dual=3.393784142602385e-10、max_constraint_violation=0.0、max KKT=5.616718630759355e-09**；status=optimal 且 violation>1e-8 的行 0；与 `outputs/q3/qp_cert_audit.json` 的 aggregates 全 match。
- **残差**：`transfer_constraints.csv` 15048 行=396×38；`upper_source_value` 复算 `clamp(after−before,0)` max|差|8.3e-17；nonenal max **3.556183e-17**；butanedione QP 口径 max **1.804112e-16**（含 target-mean-projection 全表 2.220446e-16，machine epsilon）；X4VG/DMS=0。
- **位移**：`transfers.csv` 396 行；qp-quantile-anchor（`outputs.json protocol.anchors` 的 delivered variant）逐列 max|stored_new−stored_source| = **0.001008854 / 0.523885882 / 0.323278758**（nonenal / butanedione / 4VG），与 claim 一致；同策略 mean 分别为 1.019e-5 / 0.093904 / 0.012708，故这些是 max。
- **非增率**：`nonincrease_all` 复算 QP 两策略与 source-fixed =99/99=1.0，target-mean-projection=41/99=**0.414141**；58 条 `infeasible` 全部是 target-mean-projection 的 `stale_hops(ridge-proxy)`（残差和 4.579550），QP 策略 0 条，claim 披露正确。
- **z 空间**：`outputs/q3/zspace_recompute.json` rows_checked=396、rows_mismatched=0、max_abs_delta_l1_change_z=0.0，`scope_note` 明写只证“位移可复现、不证 QP 目标/约束/最优性”；`SCRIPT-0009` failed（exit 1，旧 audit sha 6449df…）保留，SCRIPT-0010/0011 succeeded；audit 的 proxy 4/396 行 max diff 1.0000000003e-9 与 STALE_TOL=1e-9、判违 1e-12 的单位/容差见 `.rework/QP-EVIDENCE-CLARIFICATION.md §2.3` 与 audit `nonincrease.definition`。
- 文件 sha 与台账一致（solver_certificates 7a9fb090…、transfer_constraints d7ff5c95…、transfers 397a01a2…、metrics 8d3574f5…）。
- **原生 optimization**：VAL-0058/0059/0061 failed 保留；VP-0016/0017 未改写为通过；claim limitations 明写“无原生 optimization VAL、不声称”。

**F1（minor）**：位移 0.001009/0.523886/0.323279 是 qp-quantile-anchor 的逐列 **max**，claim 未点名策略、未标 max，审计者无法从文本直接复算。建议写“qp-quantile-anchor 逐列 max |new−source|”。

**F2（minor）**：`claimType=optimal_under_model` 的模型边界未进 claim 文本（z 空间 231 变量、box+1 半空间、feasible≤1e-8 只在 `EXP-0080/outputs.json protocol.qp` 与 `.rework` 文档；EXP-0080 记录无 `params.optimization/algorithm/equations`；原生 optimization VAL 仍 failed）。建议在 claim 内显式限定“solver status=optimal under the declared EXP-0080 z-space QP（非全局最优）”。

---

## 5 CLAIM-0044/0045/0046（ROB-0007/0008/0009）— 各 1 条 minor（同一根因）

| claim | 值（实测） | claim 写“相对极差” | 按首个实验重算真实相对极差 | 限值 | 判定 |
|---|---|---|---|---|---|
| CLAIM-0044 | 0.354223546 / 0.362433908 / 0.357634599；极差 0.008210361982 | 0.008210 | **0.023178** | 0.05 | 仍过 |
| CLAIM-0045 | 0.210333333 / 0.207333333 / 0.205333333；极差 0.005000 | 0.005000 | **0.023772** | 0.10 | 仍过 |
| CLAIM-0046 | 0.877784406 / 0.876453019 / 0.898155049；极差 0.021702030 | 0.021702 | **0.024724** | 0.05 | 仍过 |

根因：ROB-0007/0008/0009 的 `decisionRule.reference` 都是文本串（“first linked experiment = the post-plan reference”），`runtime/quality/robustness.js` 的 `evaluateDecisionRule` 执行 `num(spec.reference)→null`、`denominator=Math.abs(reference||1)=1`，因此 `observed=spread` 被记成“relative spread”。三者的值、预注册时序、seed receipts、satisfiedMethods、2/3 种子、边界披露均核对通过；F1 只要求把绝对/相对极差分列（或由 root 在 ROB 层披露），**decisionPassed 不变**。

- CLAIM-0044 另核对：ROB-0007 preregisteredAt=14:06:35.757Z 早于 EXP-0086/0087/0098 的 14:07:54/14:08:46/14:19:46Z；experimentIds 首位是参考 EXP-0086；EXP-0098 的实际 argv 是 `--set LAMBDAS=[0.05,0.5,5.0]`（params 只记 scalar lambdaMultiplier=0.5）。
- CLAIM-0045 另核对：EXP-0091 `--reps 200`，参考 500；satisfiedMethods=[multiple-seeds,budget-perturbation]。
- CLAIM-0046 另核对：EXP-0099 实际 argv `--set KAPPAS=[0.0,10.0,20.0]`（params 只记 scalar kappaShift=5）；EXP-0094 是同一数组命令版本，未进任何 ROB。

## 6 CLAIM-0047（ROB-0010）— passed

- EXP-0095/0096/0097 的 `nonincrease-rate` 均为 1.0；`decisionRule={type:"min-value",limit:1}` 在全部 10 个 robustnessPlans 中**首次**出现（ROB-0001..0009 均 relative-range），preregisteredAt=14:07:01.242Z 早于三条 startedAt（14:11:54/57/12:01Z），note 明写“首次登记并披露来源”。
- 值/seed receipts/deps hash/metadata 均核对通过；2/3 种子已披露；指标被硬上界约束饱和（1.000）的弱证据含义已写入 claim limitations（“构造结果、不构成改善或强稳健性、不能合并成全面稳定”）。未发现把 decisionPassed 读成模型有效/交付通过。

---

## 7 requirements-coverage — findings，F1 **major**

逐条核对（不采信旧 QC-0002 的 13:11Z 快照）：

- **引用解析**：REQ-0001→CLAIM-0040(active)+EXP-0073(succeeded)+`data/processed/q1_grade_summary.json`（50 维、每维 7 级 gradeCounts 和=250）+`src/q1_fix.py`；REQ-0002→CLAIM-0041+EXP-0075+`outputs/q2/top3_report.json`（piMean 0.42045666、piBelowHalf 1263，与 EXP-0075 一致）+`outputs/q2/factor_analysis.csv`（150 行与 `experiments/EXP-0075/strict_top3.csv` 的 compound/pi **150/150 相同**）；REQ-0003→CLAIM-0042+EXP-0079+`q3_metrics.csv`（1980 行，22 风格×3 reuse×3 fold 逐格）+`src/q3_fix.py`；REQ-0004→CLAIM-0043+EXP-0080+`transfer_constraints.csv`+`qp_cert_audit.json`+`src/q3_transfer_fix.py`；REQ-0006→EXP-0080+`src/q3_transfer_fix.py`+`REPRODUCE.md`+`solver_certificates.jsonl`。文件全部存在，sha 与台账一致（solver_certificates 7a9fb090…、transfer_constraints d7ff5c95…），无未知 kind，无 claim/experiment/figure 引用 superseded/retracted 对象。
- **REQ-0001**：q1_grade_summary 有 50 维 0–6 gradeCounts；MCON-0001 边界用例 QC-0017 passed；TGT-0001 revisions[0].before.labelSource 与 `report/paper.md:97` 披露 3.xlsx 空白评分卡、原始 0–6 不可识别。
- **REQ-0002**：Top-3/Jaccard/π/符号一致性均有 EXP-0075 与 CLAIM-0041 支撑；见 F2（化学合理性未单列证据）。
- **REQ-0003**：`q3_metrics.csv` 确有 27 格 Tripel/Kriek/Lambic 逐格行；但 CLAIM-0042 scope 把全风格池化值标成 3 风格（见 §3 F1），coverage 的 claim 引用不是干净的“三风格单独报告”证据。
- **REQ-0004（F1 major）**：coverage=covered，但 requirement 文本的“mean/median 双阈值情景 + 目标接近度—改动量 Pareto 前沿”没有当前 round 证据：`EXP-0080/transfer_outputs.protocol.constraints` 只有 box + `c_new<=c_source` + stale_hops proxy；`EXP-0079` 生成侧只用 mean 阈值；EXP-0080 无 Pareto 输出。台账唯一相关产物 FIG-0026/FIG-0031 是 `experimentId=null`、`scriptFile=null` 的先导轮图，caption 仍写已不在当前设计的 cap-at-max 0.182。建议用当前 `transfers.csv` 的 `target_mahalanobis`/`l1_change_z` 造当前 round 的 Pareto 与双阈值情景，或把 REQ-0004 降为 insufficient_data 并具名 blockedReason。
- **REQ-0005**：insufficient_data 仍成立——9 个 RENDER-0001..0009 / 4 个 ART 均为 10-24 先导轮产物，不含 CLAIM-0040..0047；本批未 render/artifact/check，不能用旧文件冒充。
- **REQ-0007**：insufficient_data 仍成立——无逐图英文标注/图注一致性检查；FIG-0001 为 active（status=null），29 active figure=31 总数−2 superseded，与 note 一致。
- 另记（不立 finding）：REQ-0001..0004 记录本身 `stale=true`（`deps.sourceSha256=null`，无法按 per-input snapshot 复核），但 coverage refs 均为当前可解析证据；交付前应刷新。

---

## 8 ROB-0007/0008/0009/0010

### ROB-0007 — findings（F1 major + F2/F3 minor）

- 时序：preregisteredAt=14:06:35.757Z < EXP-0086/0087/0098 startedAt（14:07:54/14:08:46/14:19:46Z）；experimentIds[0]=EXP-0086 是参考。
- 阈值来源：limit=0.05 与 ROB-0004（08:43:08Z 预注册，早于确认轮）一致；未按当前结果调整。
- 值：EXP-0086/0087/0098 `mae`=0.35422354618559243/0.36243390816790516/0.35763459908881995，与 result 逐位一致；spread=0.00821036198231273。
- **F1 major**：`decisionRule.reference` 是文本 → `denominator=1` → ledger 的 “relative spread 0.008210” 是绝对极差；按声明的 reference=首个实验 0.35422354618559243 重算=**0.023178**（≤0.05，decisionPassed 不变）。建议在 ROB/CLAIM 分列绝对/相对极差；不可事后改写已执行判定。
- **F2 minor**：EXP-0086/0087 冻结 `src/robustness_wrapper.py` sha=1e7cd0aeb0b7，EXP-0098 冻结 sha=7d7ab6aca6c2（当前 src）；EXP-0086/0087 的 dependencies 与当前文件不符，`check-stale` 会标其过期。我 diff 两个版本：唯一差异是 override 字符串→Path 的保持逻辑；EXP-0086/0087 无 `--set`、EXP-0098 的 LAMBDAS 是 list→tuple，故数值不受影响。需披露代码漂移或统一版本重跑参考。
- **F3 minor**：plan note 写“冻结重复 0/1/2”，但 `seeds` 只有 20261025/20261026、perturbations 描述 repeat 0/1、结果只有 repeat 0/1；note 与 perturbations/seeds 不一致，容易把 2/3 读成 3/3。建议改 note。

### ROB-0008 — findings（F1 major）

- 时序：preregisteredAt=14:06:44.685Z < EXP-0089/0090/0091 startedAt（14:09:27/14:10:00/14:10:26Z）；experimentIds[0]=EXP-0089。
- 阈值来源：limit=0.10 与 ROB-0005（08:37:52Z 预注册）一致；methods=[multiple-seeds,budget-perturbation]；seeds=2（repeat 0/1），执行 2/3，claim 已披露。
- 值：0.2103333333333333/0.20733333333333334/0.20533333333333334，与 result 逐位一致；pairs 满足 seed 与 budget（EXP-0091 `--reps 200`）。
- **F1 major**：reference 文本 → denominator=1 → “relative spread 0.005000” 是绝对极差；按首个实验 0.2103333333333333 重算=**0.023772**（≤0.10，decisionPassed 不变）。
- 实验目录有 seed-receipt.json、`requireSeedReceipt=true`；deps hash 与当前文件一致。

### ROB-0009 — findings（F1 major）

- 时序：preregisteredAt=14:06:52.880Z < EXP-0092/0093/0099 startedAt（14:10:50/14:11:12/14:19:57Z）；experimentIds[0]=EXP-0092。
- 阈值来源：limit=0.05 与 ROB-0006（08:37:43Z 预注册）一致；methods=[multiple-seeds,param-perturbation]；seeds=2（repeat 0/1），执行 2/3，claim 已披露。
- 值：0.8777844056665478/0.876453018856588/0.8981550487535501，与 result 逐位一致；EXP-0099 实际 argv `--set KAPPAS=[0.0,10.0,20.0]`（params 只记 scalar kappaShift=5）；EXP-0094 是同一数组命令版本且未进任何 ROB。
- **F1 major**：reference 文本 → denominator=1 → “relative spread 0.021702” 是绝对极差；按首个实验 0.8777844056665478 重算=**0.024724**（≤0.05，decisionPassed 不变）。
- 判定只用 energy-distance；constraint-satisfaction=1.000 不参与判定，claim/plan 已披露。

### ROB-0010 — passed

- 时序：preregisteredAt=14:07:01.242Z < EXP-0095/0096/0097 startedAt（14:11:54/57/12:01Z）；experimentIds[0]=EXP-0095。
- `decisionRule={type:"min-value",limit:1}` 在 10 个 plan 中**首次**出现，note 明写“此前无阈值、执行前首次登记并披露来源”；三值 1/1/1，min=1 满足 limit=1；spread=0。
- 值/seed receipts/deps/argv（EXP-0097 `--set LAMBDA=2.0`，params.lambdaWeight=2）均核对通过；EXP-0098/0099 未进本 plan，EXP-0094 未进任何 ROB。
- 饱和与弱判别力已在 CLAIM-0047 limitations 明写；claim 未把 decisionPassed 当模型有效/交付通过。

---

## 9 EXP-0080 — passed

- **证书**：198 行 / 198 唯一 problem_hash / 198 optimal / feasible 全 true / max primal 9.989717e-9 / max dual 3.393784e-10 / max violation 0.0 / max KKT 5.616719e-9；与 `outputs/q3/qp_cert_audit.json` aggregates 全 match；status=optimal 且 violation>1e-8 行 0。
- **残差**：upper_source_value 复算 `clamp(after−before,0)` max|差|8.3e-17；nonenal 3.556183e-17；butanedione QP 口径 1.804112e-16（全表 2.220446e-16）；proxy 4/396 行 max diff 1.0000000003e-9，单位（ridge-proxy score, sensory label units）与容差（STALE_TOL=1e-9、判违 1e-12）在 `.rework/QP-EVIDENCE-CLARIFICATION.md §2.3` 与 audit `nonincrease.definition` 有说明。
- **位移/策略**：396 行=11 源×9 折×4 策略；nonincrease_all=1.0/1.0/1.0/0.414141；58 条 infeasible 全在 target-mean-projection 的 stale_hops proxy；qp-quantile-anchor 逐列 max|Δstored| = 0.001008854/0.523885882/0.323278758。
- **z 空间**：`zspace_recompute.json` rows_checked=396、mismatched=0、delta=0、per_strategy 各 99 行 delta=0，scope_note 明写只证“位移可复现、不证 QP 目标/最优性”；audit 的 `z_space_l1_recomputable_from_artifacts=false` 保留。
- **失败/history**：SCRIPT-0009 failed（exit 1、旧 audit sha 6449df…、4150B）保留；SCRIPT-0010 succeeded（audit 713b0143…、4530B）；SCRIPT-0011 succeeded（zspace_recompute 2915a2ee…、zspace_centrescale c7aaa377…）。
- **原生 optimization**：VAL-0058/0059/0061 failed 保留；VP-0016/0017 未改写为通过；claim 未声称。
- 记录缺口（不构成本次 pass 的反证，已在 CLAIM-0043 F2 提出）：EXP-0080 自身无 `params.features/algorithm/equations/params.optimization`；leakage 用 VP-0016 的 featureColumns（231 列），QP 规格在 `EXP-0080/outputs.json protocol.qp`。

---

## 10 范围外观察（不写入 review-add，仅供 root 参考）

1. **`frozen` 记录仍是 2026-10-24 revision 2731 的旧身份**：`frozen.claimIds` 仍列 CLAIM-0012/0014/0018/0019/0021/0022（现均 retracted），`selectedModels` 仍是 MODEL-0004/0012/0013，experimentIds 不含 EXP-0073..0080。它不是“active claim/requirement coverage”，所以本轮没有写成 finding；但它是交付/冻结身份，交付前需重新 freeze。
2. **QC-0020 仍 failed**：`report/paper.md` 仍以占位符引用 CLAIM-0014/0019/0022/0012/0018/0021（均 retracted）；本批不碰论文。
3. **Q3 analysisPlan 声明的部分 evidence 是 16:36 先导轮文本**：`outputs/q3/decision.md` 仍写 “Not done: ... robustness execution”，`outputs/q3/robustness.json` 也是先导轮；虽然 `robustness_transfer/generation_confirmatory.json`（22:21）已更新，但 analysisPlan.evidence 指向的旧文件没有更新，`analysis-evidence` 结构检查不会发现语义过期。本批未改（不是我的 14 个对象）。
4. **REQ-0001..0004 stale=true**（`deps.sourceSha256=null`）；coverage refs 本身可解析，但交付前应刷新 requirement 快照。
5. **EXP-0088 / EXP-0094** 与 EXP-0098 / EXP-0099 的 argv 相同（数组 override），前者 params 仍记默认 `lambdaGrid`/`kappas`、后者只记 scalar 描述；它们未进任何 ROB，不影响本轮判定，但作为孤儿实验的记录一致性值得清理（不删除历史）。
6. **Q3 生成侧 energy-distance 的 style 池化口径** 也影响 `FIG-0024` 的 runtime 注释（其 caption 已写“22 个风格”，与我的重算一致）；但 FIG-0024 是 `experimentId=null` 的先导轮图，若交付引用需重新绑定 EXP-0079 的当前快照。
7. **requirements-coverage review 的 binds.requirementsVersion=1241ab4e…**：若 root 之后用 requirement-map 改任何 REQ 的 coverage，本轮 REV-0057 会按设计变为 stale，需要重新独立复审（这正是 `review-coverage` 的绑定机制，不是缺陷）。

---

## 11 边界声明

- 未改任何 claim / contract / requirement coverage / robustnessPlan / experiment 记录；未跑 `quality-plan` / `quality-run` / `quality-stale`；未 render / artifact / package；未删除任何历史。
- 未采信 `.rework/R04-independent-recompute.json` 的结论；所有数值独立重算。
- 14 条 review 的 provenance 均为 `team member 2492c073-...`、`isRoot=false`、`independent_context`，方法字段含实际文件路径与计算式。
- 本轮 finding 的严重度按“是否改变已记录的 decisionPassed / 是否影响 claim 主数字”判定：RELATED relative-range 口径错误均不影响 decisionPassed，但仍记为 major（记录量与该 plan 自声明口径不一致）；CLAIM-0042 的 scope 错误影响“数字的估计域”，记为 major；未把任何发现升级成 critical。
