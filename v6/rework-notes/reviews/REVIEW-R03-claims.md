# REVIEW-R03-claims 独立审查报告（CLAIM-0027 / 0028 / 0029 / 0030）

- 审查者：`claims-reviewer`（新上下文；与被审执行者不同上下文）
- 审查对象：`state/ledger.json` 的 `CLAIM-0027`（Q2）、`CLAIM-0028`（Q3 生成）、`CLAIM-0029`（Q3 迁移）、`CLAIM-0030`（Q1/Q2/Q3 稳健性）
- 项目目录：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`
- 权限：只读项目；唯一写入 = 本文件。**未调用任何 `modeling_*` 工具、未跑实验、未训练、未改任何项目文件、未写 SOURCE。**
- 工具：系统 `python3` + 标准库 `csv/json`（环境无 pandas）；全部数字由我本人从磁盘产物复算或逐键解析，不采信 claim 文字。
- 时点：2026-10-26（台账以读取时刻为准；本报告写作期间台账 revision 未再变化）

---

## 0 结论速览

| claim | 问 | verdict | critical | 数字可复算 | 主要问题 |
|---|---|---|---|---|---|
| CLAIM-0027 | Q2 | **findings** | 是 | 全部成立 | limitations 自称"未被验证"与 validationIds/选择状态直接矛盾；唯一 ref 实验 EXP-0041 自己写着"3x3x3 nested CV"并挂错依赖；VAL-0054 磁盘无目录 |
| CLAIM-0028 | Q3 生成 | **findings** | 是 | 全部成立 | 1.000 的约束集合含 ridge 代理上界未披露；0.1199 是单元格级却与行级数字并排；31.2% 约束记录未 verified 未给占比；2/3 行 4VG 在 censor 地板码 |
| CLAIM-0029 | Q3 迁移 | **findings** | 是 | 全部成立 | 唯一验证 VAL-0050 磁盘无目录且是确定性重放；"396 行/198 求解/独立 KKT/1.1e-16"四处措辞或数字不严谨 |
| CLAIM-0030 | Q1/Q2/Q3 | **findings** | 否 | 全部成立 | 三个 ROB 计划台账 status 仍为 `pending` 且注记"不记为通过"，claim 写"已…通过"；三个"相对极差"分母互不一致；ROB-0004 把登记参数差异记成 param-perturbation 已满足 |

没有一条因"数字造假/对不上产物"被 rejected；四条 claim 的**核心数值全部逐位复算成立**。问题集中在**自我限定与台账证据对象不自洽、验证产物未落盘、判据口径不一致**。

---

## 1 我实际做了什么复核（可复算清单）

| # | 复核动作 | 结果 |
|---|---|---|
| R1 | 从 `experiments/EXP-0041/repeat{0,1,2}/strict_top3_by_method.csv`（各 600 行）重算 π<0.5 与均值 | 423+419+421=**1263/1800**；平均 π **0.42045667**；平均 sign_stability **0.72255444**，与 `metrics.json` 完全一致 |
| R2 | 从 `EXP-0041/repeat0/bootstrap_pi.csv`（300000 行 = 500×50×4×3）按 (dim,method,compound) 重算 π，抽 12 条与交付表比对 | 12/12 完全相等（π 可由原始 replicate 明细重建） |
| R3 | 从 `EXP-0041/repeat*/sets.json`（各 200 条）重算四方法两两 Top-3 Jaccard | rep0 **0.2103333**、rep1 **0.2073333**、rep2 **0.2096667**；池化 **0.2091111**；跨重复（4 方法×50 维池化）**0.8748333**（仅 consensus 榜为 0.856） |
| R4 | 复核 6.csv 对照口径 | `outputs.q2.external_6csv`：`nMatched=44`、`meanSpearman=0.9210176`（= 50 个 perDimension 的均值，我重算 0.921017618）、严格 0.9080153、旧管线 0.4450514、仅列错位 0.8968626 |
| R5 | 复核 Q2 宇宙划分 | `candidate_scores.csv` 231×50：single_compound **216**、element_or_index **3**、physical_parameter **7**、derived_sum **5**（扩展 15） |
| R6 | 代码级核对 Q2 协议 | `src/q2_fix.py:180` 只读 `SPLIT-0001/train.csv`；`:353` 断言 200 行；`:681-720` 是 500 次风格分层重抽样；`:1174` 池化=三次重复均值。**确无 outer/inner 折、无 OOF、无 test 读取** |
| R7 | 从 `EXP-0042/samples.csv`（750×237）重算三个夹断计数 | DMS 存储上界 1.2367890994（=log10(17.25)）恰命中 **508/750**；双乙酰 **0.29925 恰命中 361/750**；X4VG 存储上界 −0.6854306（=log10(0.206333333)）恰命中 **46/750** |
| R8 | 从 `EXP-0042/samples.csv` 33 个 calibrated_linear 列重算负值 | 设计谱负值格 **0**（750 行）；旧版 EXP-0033/samples.csv 同法复算 **142 格/40 行/22 列**（与 `outputs/audit/v6/legacy_recheck.json` 的 `matches:true` 一致） |
| R9 | 从 `EXP-0042/q3_metrics.csv`（198 格×5 模型×2 阶段）按代码口径（`n_gen` 加权，`q3_fix.py:1009-1010`）重算池化量 | copula-selected design：E_V_norm **0.8840256**、diversity **19.735647**、U **+1.1138668**、edge **0.11991342**（=20775/173250 单元格）；source-resample design E_V_norm **0.8137313**。加权口径下逐位等于 metrics（注意：**算术平均是 1.1368，不是 0.8840**，池化是 n_gen 加权） |
| R10 | 复核 21 个不可估格 | `q3_metrics.csv` 中 n_real==1 的格恰 21 个，其 E_V_norm 全为空；`n-cells=198`、`n-cells-excluded-from-energy=21` |
| R11 | 从 `EXP-0042/constraints.csv`（28500 条）重数核验分布 | verified **19619** / conditional **8201** / not_identifiable **680** / infeasible **0**；max residual **0.0**；verified 占比 **68.84%**，未 verified **31.16%** |
| R12 | 从 `EXP-0043/transfers.csv`（396×738）重算四列不增与 Δ | qp-quantile-anchor 99 行：DMS 99/99、nonenal 99/99（max Δ **3.556e-17**）、双乙酰 99/99（max Δ **1.804e-16**）、X4VG 99/99；**source-fixed（不做任何迁移）同样 99/99**；target-mean-projection 四列也 99/99，其 0.414 全部来自 stale 代理行 |
| R13 | 复核 `EXP-0043/transfer_constraints.csv` verdict | target-mean-projection 有 **58 条 infeasible**，全部是 `stale_hops(ridge-proxy)`；其余策略 infeasible=0 |
| R14 | 解析 `EXP-0043/solver_certificates.jsonl` | **198 份**（= 2 个 QP 策略 × 99 行；qp-quantile-anchor 99 + qp-source-anchor 99）；status 全 optimal；max primal **9.9897e-9**、max dual **3.3938e-10**、violation **0**、KKT **5.6167e-9**；198 个 problem_hash 互不相同 |
| R15 | 从 `EXP-0066/oof_long.csv`（50000 行 = 250×30×4 模型）重算 Q1 A/F30 池化 MAE | graph-lowrank **0.3542235462**（7500 个绝对误差），与 metrics/claim 0.354224 一致；median 0.397808、ridge0 0.364678、graph-ridge 0.364856 |
| R16 | 复核稳健性实验与主实验的关系 | EXP-0066 = EXP-0039 repeat0（0.354224，逐折 mae 0.3549259163784175 完全相同）、EXP-0067 = EXP-0039 repeat1（0.362434）；EXP-0064/0065 = EXP-0041 rep0/rep1；EXP-0062/0063 = EXP-0042 rep0/rep1。**"扰动实验"是主实验已报告的 repeat 0/1 腿的逐位重放** |
| R17 | 复核哈希一致性 | `src/q2_fix.py` fd010c4f…、`src/q3_fix.py` ae599242…、`src/q1_fix.py` 2fb4b4b0…、`data/clean/q3.csv` 4948a908…、`data/splits/NESTED-CV-1/splits.csv` 8ad8e75d…、`data/splits/SPLIT-0001/train.csv` bf6bad1d… 均与登记值一致；四条 claim `configVersion=2` 与全部被引实验的 configSha 728811fc… 一致（`stale=false` 在数据/代码层站得住） |

---

## 2 CLAIM-0027（Q2）

### 2.1 数字逐条对账（全部成立）

| claim 陈述 | 实测 | 判定 |
|---|---|---|
| topk-jaccard 0.20911 | 0.2091111111111111 | ✅ |
| 三次重复 0.21033 / 0.20733 / 0.20967 | 0.2103333 / 0.2073333 / 0.2096667 | ✅ |
| 跨重复一致性 0.87483 | 0.8748333（4 方法×50 维池化） | ✅（口径见 F4） |
| 旧错位 0.445051 | `external_6csv_mean_spearman_superseded_positional=0.4450514`；代码 `q2_fix.py:845-856,1199` 以"列按位置 + 219 行用 231 空间下标"的旧管线复现 | ✅ |
| 对齐后 0.921018（44 行；严格 0.90802） | 0.9210176 / 44 / 0.9080153 | ✅ |
| 严格 216（219 减 3）+ 扩展 15 | 216 / 15 | ✅ |
| π<0.5 1263/1800，平均 π 0.4205，符号一致 0.7226 | 1263/1800，0.42045667，0.72255444 | ✅ |
| "不是嵌套 CV、无 outer/inner、无 OOF、50 行留出未参与" | `q2_fix.py` 仅读 200 行 train；无折/OOF/test 读取 | ✅（执行层为真，见 F2） |

### 2.2 findings

**F1（major）limitations[1] 说"本轮 Q2 没有任何 verification…故该结论未被验证"，与 claim 自己的 validationIds 直接矛盾。**
证据：`CLAIM-0027.quality.limitations[1]` 原文"本轮 Q2 没有任何 verification（无 leakage、无独立复跑）：EXP-0049/EXP-0052 两次冻结快照尝试失败，故该结论未被验证"；但同一记录 `validationIds=["VAL-0053","VAL-0054"]`，两者 `result.passed=true`（VAL-0053 leakage max|r|=0.576<0.999；VAL-0054 independent-rerun delta=0），且 `questions[Q2].selectionStatus="validated"`、`selectionReason` 明写"VAL-0053 leakage 与 VAL-0054 independent-rerun 均通过"。时间线：claim 创建 08:34，validation 于 08:48/08:49 通过并 `linkedAt 08:49:40`，limitation 未回写。
影响：审查者若只读 limitations 会得出"关键结论未验证"的反向错误结论；若只读 validationIds 会得出"已独立复跑"，两者不能同时成立。必须二选一并改写（见 §8）。

**F2（major）claim 唯一的 metric ref 实验 EXP-0041 自身的登记文本写着"3x3x3 nested CV"，并挂了一个代码从不读取的依赖、漏掉唯一真正读取的数据文件。**
证据：`experiments/EXP-0041/experiment.json` 的 `params.protocol="3x3x3 nested CV, seeds 20261025-27, style-stratified; stratified bootstrap inside each style"`；`params.dependencies` 含 `data/splits/NESTED-CV-1/splits.csv`（`src/q2_fix.py` 全文未打开该文件），却**不含** `data/splits/SPLIT-0001/train.csv`（`q2_fix.py:180/353` 唯一读取的数据）。同一误标也在 `MODEL-0020.params.protocol`（EXP-0041 的 model）与 MODEL-0019/0024/0028/0031；只有 MODEL-0044..0047（含 Q2 选中的 MODEL-0047）被改成正确文本。
与配置的关系：`contest.yaml` 的 `evaluation.tuning="train-only-nested-cv; repeats=3; outer_folds=3; inner_folds=3; …"`，`data/splits/NESTED-CV-1/manifest.json` 的 `purpose="frozen internal re-validation protocol for the R00-R03 rerun"`。Q2 **既不消费 NESTED-CV-1，也不消费 SPLIT-0002**，且其超参数（`TAU=0.5`、rank 6、λ=1、γ=0.1、25 sweep）是代码常量而非调参产物（`q2_fix.py:189/191` 等）——所以"不是嵌套 CV"在执行层为真，但台账/配置层**没有任何"Q2 豁免"的登记**，导致 ref 链上出现自相矛盾的协议标签。
建议表述（可直接替换 appliesTo/limitation）："Q2 不消费 `NESTED-CV-1` 与 `SPLIT-0002`；其超参数是预先声明常量而非调参结果，因此 contest.yaml 的 `train-only-nested-cv` 调参要求对 Q2 为空转（vacuous），**不能**据此声称 Q2 通过嵌套 CV；这是需在 question/experiment 层显式登记的豁免，而非嵌套 CV；Q2 因此不提供任何样本外估计。" 同时把 MODEL-0020/EXP-0041 的 protocol 与依赖清单改正（或让 claim 的 refs 指向 EXP-0071）。

**F3（major）claim 的 independent-rerun 证据 VAL-0054 在磁盘上不存在，且它与 VAL-0053 都不是独立实现，而是同快照同种子的确定性重放。**
证据：`validation/` 下有 `VAL-0047/`、`VAL-0053/`（各含 `spec.json`+`result.json`），**没有** `VAL-0049/`、`VAL-0050/`、`VAL-0054/`；VAL-0054 只有 `state/ledger.json` 内联记录（`specPath` 缺失、无 `startedAt`）。且 VAL-0054 的 `details.mode="fixed-seed-reproduction"`、`seeds=[20261025]`、`rerunExperimentIds=["EXP-0072"]`，而 EXP-0072 的 `rerunOf=EXP-0071`、同代码同数据同种子，`delta=0`——只能证明确定性，不能证明独立性。claim 未披露这一语义。

**F4（minor）"跨重复一致性 0.87483"的口径未说明。**
它是"4 方法 × 50 维池化"的跨重复 Jaccard（`q2_fix.py:1197-1212`；我复算 0.88/0.8595/0.885→0.8748333）；若只看交付的 consensus 榜，跨重复一致性是 **0.856**（0.88/0.828/0.86）。建议写成"跨重复（4 方法×50 维池化）一致性 0.87483；仅交付榜 0.856"。

**F5（minor）statement 里多个数字未绑定为 ref，台账渲染无法从 refs 取值。**
refs 只覆盖 `topk-jaccard`、`-rep0`、`external_6csv_mean_spearman_aligned`、`n_strict_candidates`、`pi_below_0.5_count`、`sign_stability_mean`；而 statement 还引用了 0.445051、44、0.90802、15（扩展）、0.20733/0.20967、0.87483、π 均值 0.4205、分母 1800、reps 500。它们能在 `EXP-0041/metrics.json` 找到，但未绑定 → 论文若要引用只能手工抄写。

---

## 3 CLAIM-0028（Q3 生成）

### 3.1 数字逐条对账（全部成立）

| claim 陈述 | 实测 | 判定 |
|---|---|---|
| constraint-satisfaction 1.000 | 1.0（且 `q3_fix.py:1064-1080` 从写出的 samples.csv 逐行重算，与内存值一致） | ✅（构造不变量，claim 已正确自我限定） |
| raw 0.1133 | 0.11333333（=85/750 行零违反） | ✅ |
| 线性实际浓度负值 0（旧版 142 格/40 行/22 列） | 设计谱 0；旧版我从 EXP-0033/samples.csv 复算 142/40/22 | ✅ |
| 750 行中 508/361/46 行贴阈值 | 508/750=67.7%、361/750=48.1%、46/750=6.1%（存储空间恰等于 cap，物理即 17.25/0.29925/0.206333333） | ✅ |
| 归一化 V 0.8840 vs 重采样 0.8137 | 0.8840256 vs 0.8137313（n_gen 加权池化） | ✅ |
| 有符号 U +1.1139 | +1.1138668（不截零） | ✅ |
| 多样性 19.736、复制率 0.000 | 19.735647 / 0.0 | ✅ |
| verified 19619/conditional 8201/not_identifiable 680/infeasible 0、max residual 0.0 | 逐条相同（28500 条） | ✅ |
| 21/198 格不可估 | n_real==1 恰 21 格，E_V_norm 全空 | ✅ |

### 3.2 findings

**F1（major）"1.000"的约束集合包含一条 ridge 代理约束，claim 未披露。**
证据：`q3_fix.py:399-410` 的 `violated_rows` 除四阈值、nonenal、非负之外，还包含 `ctx["proxy"].predict_storage(X, L.STALE) > style_stale_bound(...)`；`outputs.q3.constraint_definitions.staleHops.state="PROXY constraint, not a chemical measurement"`。claim 只说明"t2n 已改由化学 nonenal 承担约束"（limitations[4]），没有说 `stale_hops` 代理仍在满足集合内。读者会把 1.000 理解为"化学/物理约束全部满足"。

**F2（minor）"贴边比例 0.1199"是单元格级，却与行级数字并排。**
证据：`q3_fix.py:480-490` 的 `edge_fraction` 对 `n_gen×231` 个单元格取均值（floor code / 训练支撑 min-max / 0 都算贴边）；`outputs.q3.constraint_definitions.edgeFraction` 同义。0.1199 = **20,775/173,250 个单元格**。而同一句前文是"508 行/361 行/46 行"，按行计至少一格被夹断的是 508/750=67.7%。建议写成"按单元格计的贴边比例 0.1199（20,775/173,250）"。

**F3（minor）31.2% 的约束记录未 verified，claim 只给原始计数不给占比。**
8201 conditional + 680 not_identifiable = 8881/28500 = 31.16%，verified 仅 68.84%；而"1.000"是行级、把 censored/条件记录所在行也计入满足。建议直接写"verified 19619/28500=68.8%，其余 31.2% 为 conditional 或不可识别"。

**F4（minor）2/3 的生成 4VG 值落在 censor 地板码上，claim 未披露。**
`samples.csv` 中 `chem__X4VG` 恰等于 floor code −2.013157381 的有 **494/750=65.9%**（真实 `data/clean/q3.csv` 为 168/250=67.2%，属忠实抽样而非 bug）；claim 只披露 46 行贴上限阈值。其后果是"4VG 不超过阈值"对 2/3 的行近乎空转，且地板码不是可解释浓度。建议在 limitations 增加一句。

**F5（minor）VAL-0047 对"1.000"没有信息量，claim 引用时未限定。**
`VAL-0047` 是 `simulation-seeds`：3 个 seed 的 constraint-satisfaction 都是 1.0、范围 [0,1] 内。由于 1.0 由投影循环保证，这个"通过"只是复述不变量，不能作为质量/正确性证据。claim 已说 1.000 是构造不变量，但把 VAL-0047 列进 validationIds 会让读者以为它验证了什么。

**F6（minor）VAL-0049 无磁盘目录，且 mode=fixed-seed-reproduction（单 seed 20261025，EXP-0054 rerunOf EXP-0050），是确定性重放而非独立实现；claim 未披露。**

**F7（minor）claimType 选择不当。**
`CLAIM-0028.quality.claimType="contemporaneous_association"`，但该结论是"生成谱与真实分布的距离/夹断诊断"，不是变量间同期关联；`descriptive` 更贴切（对比 `CLAIM-0029` 用 `optimal_under_model` 是正确的）。critical claim 的 claimType 会被门禁读取。

---

## 4 CLAIM-0029（Q3 迁移）

### 4.1 数字逐条对账（全部成立）

| claim 陈述 | 实测 | 判定 |
|---|---|---|
| 不增率 1.000（约束构造结果） | 1.0；`q3_transfer_fix.py:454-470` 的 cap 就是 `c_new ≤ c_source`（输入侧构造），QP 目标含该约束 | ✅（claim 已正确自我限定） |
| 四化学列各 1.000（nonenal max(new−source)≤1.1e-16） | 99/99×4；nonenal max Δ=3.556e-17，双乙酰 max Δ=1.804e-16 | ✅（"≤1.1e-16"数字本身见 F5） |
| 198/198 QP optimal；primal 9.99e-9；dual 3.39e-10；violation 0；KKT 5.6e-9 | 198 份证书全 optimal；9.9897e-9 / 3.3938e-10 / 0 / 5.6167e-9 | ✅ |
| 目标均值自距 4.75e-16（旧实现 0.6655） | 4.7490841e-16；legacy 0.6654909915 | ✅ |
| 迁移 V 归一化 0.1236；主策略 V=2.261；源点不变 7.196；均值投影 6.941；U −0.148 | 0.12363579 / 2.26108049 / 7.19632629 / 6.94148284 / −0.14768123 | ✅ |
| 目标均值投影 0.414（58/99 stale 代理不可行） | 0.41414141；`transfer_constraints.csv` 58 条 infeasible 且全为 stale 代理 | ✅ |
| 主策略下 t2n 代理仍 7/99 上升 | `outputs.nonincrease_by_strategy.qp-quantile-anchor.t2nDiagnosticIncreaseShare=0.070707`（=7/99） | ✅ |
| 11 源 × 3 重复 × 3 折、99 行/策略 | n-sources=11、n-folds=9、每策略 99 行 | ✅ |

### 4.2 findings

**F1（major）唯一 validation VAL-0050 在磁盘上没有目录（无 spec.json/result.json），且是确定性重放而非独立实现。**
证据：`validation/VAL-0050/` 不存在（只有台账内联记录，无 `specPath`）；`VAL-0050.result.details.mode="fixed-seed-reproduction"`、`seeds=[20261025]`、`rerunExperimentIds=["EXP-0055"]`，EXP-0055 `rerunOf=EXP-0051`（同代码同数据同种子），`delta=0`。critical claim 仅此一条验证，且无法从磁盘复核。

**F2（minor）"（396 行）"与"198/198 次 QP 求解"的口径容易被读反。**
396 = 4 个策略 × 99 行（`n-transfer-rows=396`）；主策略 qp-quantile-anchor 只有 99 行。198 份证书 = 2 个 QP 策略 × 99（`qp-source-anchor` 99 + `qp-quantile-anchor` 99）。建议写"4 策略合计 396 行，其中主策略 99 行；两个 QP 策略共 198 次求解"。

**F3（minor）"独立 KKT 复核 5.6e-9"的"独立"过强。**
5.6167e-9 来自本次运行 `outputs.certificates_summary.maxKktStationarityResidual`（同脚本内用 NNLS 重建 lambda 后算平稳性残差），是对迭代解的**独立重算**，但不是独立实现/独立工具复核。建议改"求解后 KKT 平稳性重算 5.6e-9"。

**F4（minor）"不增率 1.000"缺少最有说服力的对照：什么都不做的 source-fixed 也是 1.000。**
我从 `transfers.csv` 复算：source-fixed 四列同为 99/99=1.000。也就是说该指标对"是否真的发生迁移"零区分度。claim 已声明 1.000 由约束保证，但未指出平凡对照同样满分——建议补一句，否则读者仍可能把它当"迁移后化学仍安全"的经验证据。

**F5（minor）"nonenal 列逐行 max(new−source)≤1.1e-16"这个界不是实测值。**
我在 `EXP-0043` 全部产物（metrics/outputs/transfer_constraints/transfers）中检索不到 1.1e-16；实测 nonenal 列 max Δ=3.556e-17，四列 max Δ=1.804e-16（双乙酰）。不等式仍成立，但引用的数字无出处，且 1.1e-16 恰好会把双乙酰的实测最大值排除在外，容易被误读成"四列都 ≤1.1e-16"。

**F6（minor）归一化与原始能量值混写。**
"迁移后与目标参照的归一化能量 V 为 0.1236（主策略 V=2.261），源点不变对照 7.196、目标均值投影 6.941"中，0.1236 是 E_V_norm，2.261/7.196/6.941 是原始 V；未标注会让读者以为 2.261 也是归一化值。建议写成"归一化 V=0.1236（主策略原始 V=2.261；对照原始 V：源点不变 7.196、目标均值投影 6.941）"。

---

## 5 CLAIM-0030（稳健性）

### 5.1 数字逐条对账（全部成立）

| claim 陈述 | 实测 | 判定 |
|---|---|---|
| Q1 0.354224 / 0.362434 | EXP-0066 mae=0.3542235462（我从 oof_long.csv 重算同值）；EXP-0067=0.3624339082 | ✅ |
| Q2 0.210333 / 0.207333 | EXP-0064/0065 topk-jaccard | ✅ |
| Q3 0.877784 / 0.876453 | EXP-0062/0063 energy-distance（= EXP-0042 repeat0/1） | ✅ |
| 阈值 5%/10%/5% | ROB-0004 limit 0.05、ROB-0005 0.1、ROB-0006 0.05 | ✅ |
| decisionPassed=true、executionStatus=completed | 三条记录均如此 | ✅ |
| 每计划 2 个实验、均带 seed-receipt.json | 六个实验目录均有 `seed-receipt.json`，experiment.json `requireSeedReceipt=true` | ✅（"runner 验证"语义见 F5） |

### 5.2 findings

**F1（major）三个 ROB 计划在台账里仍全部是 `status="pending"`，且注记明写"不记为通过"，与 claim 的"已真实执行并通过"相反。**
证据：`ROB-0004/0005/0006` 的 `status` 都是 `pending`；ROB-0005.note"本轮不 retrofit，计划保持 pending，不记为通过"；ROB-0006.note"计划保持 pending，不记为通过"；ROB-0004.note 同样写"计划保持 pending，不记为通过"。同时 `quality.checks` 的 QC-0022/0024/0026（robustness-execution）却是 `passed`、`stale=false`（08:44）——台账内部也不自洽。
建议表述：**"三个计划的执行记录为 executionStatus=completed、result.decisionPassed=true，对应 QC 通过；但计划自身 status 仍为 pending 且注记明写『不记为通过』，因此只能表述为『执行已完成且判据在已执行的扰动内满足』，不能写成『计划已通过』。"**

**F2（major）ROB-0004 把"登记参数字段差异"记成 param-perturbation 已满足，与 claim 的 limitation 互相矛盾。**
证据：`ROB-0004.result.evidence.perturbation.satisfiedMethods=["multiple-seeds","param-perturbation"]`，其 `pairs[0].changedParams=["metricDefinition","protocol"]`——即仅因两次登记的 params 文本不同；计划里真正的 λ×0.5/×2 扰动从未执行。而 `CLAIM-0030.limitations[1]` 写"计划里的 param-perturbation 分支未单独执行"。claim 诚实、ROB-0004 的证据字段不诚实，而 `decisionPassed` 读的是后者。

**F3（major）三个"相对极差"分母不一致，至少一个数字与其判据公式不符。**
| 计划 | claim 值 | spread/min | spread/max | spread/mean |
|---|---|---|---|---|
| Q1 | 0.023178 | **0.0231785** | 0.0226534 | 0.0229129 |
| Q2 | 0.014263 | 0.0144695 | **0.0142631** | 0.0143655 |
| Q3 | 0.001517 | 0.0015191 | **0.0015168** | 0.0015179 |

Q1 用的是 `spread/min`，Q2/Q3 用的是 `spread/max`；三个数在任何单一公式下不能同时成立。三个阈值下通过/不通过不变，但 claim 把它们并列成同一判据"相对极差"，其中至少一个不是该判据的值（若统一 /max，Q1 应为 0.022653）。`quality/robustness.js` 在 app.asar 内不可读，无法确认哪个是工具的官方公式——这也正是必须修正记录、而不是只在 claim 里抄数的理由。

**F4（minor）"2 个独立实验"实为主实验已报告 repeat 0/1 腿的逐位重放。**
EXP-0066=EXP-0039 repeat0（0.354224，逐折 mae 逐位相同）、EXP-0067=EXP-0039 repeat1；EXP-0064/0065=EXP-0041 rep0/rep1（0.210333/0.207333 原样）；EXP-0062/0063=EXP-0042 rep0/rep1（0.877784/0.876453 原样）。它们不提供新的扰动信息（同代码/同数据/同协议/同种子），"独立"容易被读成独立证据。claim 的 limitation 已说明"只用 2 个 seed block（重复 0 与 1）"，但未说明数值与主实验 repeat 腿逐位相同。

**F5（minor）`seed-receipt.json` 内容只有 `{"seed":…,"source":"MODELING_SEED"}`，无签名、无代码/数据哈希、无实验绑定；"runner 验证"在项目文件里没有可审计痕迹（run.json/result.json 无验证字段）。**
claim 的"均带 runner 验证的 seed-receipt.json"只能依赖 runner 实现（app.asar），项目侧不可复核。

**F6（minor）ROB-0004.note 未更新，仍写"Q1 仍未执行…计划保持 pending"，与该记录已挂 EXP-0066/0067、executedAt=08:44:08 矛盾。**

**F7（minor）ROB-0004 声明 `seeds=[20261025,26,27]`、`repeats=3`，实际只执行 2 个 block，`executionStatus` 仍记 `completed`（未标 partial）。**

---

## 6 跨条目问题

- **X1 证据链两段不相连**：三条 critical claim 的 metric refs 指向主实验（EXP-0041/0042/0043），而 validationIds 指向 audit/rerun 实验（EXP-0071→EXP-0072、EXP-0050→EXP-0054、EXP-0051→EXP-0055）。数值逐位相同，但"claim→ref 实验"与"claim→被验证实验"不是同一条链。建议 Q2 的 refs 改指 EXP-0071（带 features 清单与 immutable 声明完整快照）。
- **X2 "independent-rerun" 的语义**：VAL-0049/0050/0054 全部 `mode=fixed-seed-reproduction`、单 seed、`rerunOf` 同一实验快照。这是确定性重放，不是独立实现。三条 claim 均未披露。
- **X3 验证产物未落盘**：`validation/` 下只有 VAL-0047/0053；VAL-0049/0050/0054 无目录、无 spec/result，仅台账内联。审计无法从磁盘复核这三条。
- **X4 无台账 review 记录**：`quality.reviews` 40 条中没有任何一条覆盖 CLAIM-0027..0030（REV-0040 只覆盖已 superseded 的 CLAIM-0026）。`contest.yaml` 的 `quality.review.required=true`、`coverageReviewRequired=true`；本文件不替代台账中的 review 记录，交付前仍需登记。
- **X5 未绑定 ref 的数字**：四条 claim 的 statement 都有可直接取自 `metrics.json`/`outputs.json` 但未绑定为 ref 的数字（见各条 F5）。按"论文正文只写台账占位符"的纪律，这些数字一旦进正文就是手工抄写。
- **X6 登记层缺口**：EXP-0041/0042/0043 的 `splitId` 全为 `null`；Q2 更是把从不读取的 `NESTED-CV-1/splits.csv` 写成依赖，同时漏掉唯一读取的 `SPLIT-0001/train.csv`（EXP-0071 已修正）。

---

## 7 notChecked（无法核验项与原因）

1. `quality/robustness.js` 的"relative range"官方公式：实现位于 app.asar，不可读；只能指出三个数在数学上互不一致（F3）。
2. "runner 验证 seed receipt" 的实现语义：runner 在 app.asar 内；项目侧只有 `requireSeedReceipt:true` 与两行 receipt，无验证记录。
3. Q3 池化能量/多样性的"逐样本"重算：我按代码口径用 `q3_metrics.csv` 的 per-cell 行 × `n_gen` 权重复算并与 metrics 逐位相等（R9），但未从 750 行原始 `samples.csv` 重新拟合标准化/边际（等于重跑，被禁止）。
4. 旧错位值 0.445051 的独立重建：我确认代码内 legacy 诊断路径（列按位置 + 219/231 下标）产出该值、`outputs` 有两条独立记录，但未用已 superseded 的 219 行矩阵独立重建。
5. `D_ref`/`d_train` 的独立重算：需要核函数尺度定义，未复算；只核对了 `E_V_raw/d_train == E_V_norm` 逐行成立。
6. Q2 6.csv 的 50×44 原始矩阵对齐：我核对了 `nMatched=44`、50 维 perDimension 均值=0.9210176，未逐列重解 6.csv（上一份独立审查已做过 4 维抽验）。
7. 四条 claim 的门禁效果（是否会被 render/check/package 拒绝）：未调用 modeling_* 工具（禁止），只能描述台账事实。
8. 四条 claim 在本台账中无 REV 记录（X4），因此"review 覆盖"无法从台账核验；本文件是文件系统证据，不是台账 review 对象。

---

## 8 修复建议（按优先级）

1. **CLAIM-0027 limitations 重写**：删掉"该结论未被验证"，改为"VAL-0053 leakage 与 VAL-0054 independent-rerun 已通过；但 VAL-0054 是同快照同种子重放（mode=fixed-seed-reproduction），只证明确定性，不证明独立实现"。
2. **修 EXP-0041 / MODEL-0020**：把 `params.protocol` 改为"固定 200 行训练集 + 3 seed block × 500 次风格分层 bootstrap（非嵌套 CV、无 OOF）"；依赖清单删 `NESTED-CV-1/splits.csv`、补 `data/splits/SPLIT-0001/train.csv`；或直接把 CLAIM-0027 的 refs 指向 EXP-0071。
3. **落地盘**：补 `validation/VAL-0049|0050|0054/{spec.json,result.json}`（与台账内联记录同源），否则这三条"验证通过"无法审计。
4. **CLAIM-0028**：补披露（a）1.000 满足集合含 stale_hops ridge 代理；（b）0.1199 为单元格级（20,775/173,250），按行至少一格被夹断 508/750；（c）verified 68.8%，31.2% 为 conditional/not_identifiable；（d）494/750 行 4VG 是 censor 地板码；把 claimType 改为 `descriptive`。
5. **CLAIM-0029**：补披露 VAL-0050 是确定性重放且无磁盘产物；改写"396 行/198 求解/独立 KKT/1.1e-16/归一化与原始 V"五处措辞；补"平凡对照 source-fixed 不增率同为 1.000"。
6. **CLAIM-0030 / ROB 记录**：统一"计划已执行但 status=pending、不记为通过"的表述；把 ROB-0004 的 `satisfiedMethods` 去掉 param-perturbation（或真正执行 λ 扰动）；把三个"相对极差"统一分母并回写结果；更新 ROB-0004 的过期 note；`executionStatus` 标 partial（2/3 block）。
7. **登记层**：为四条 claim 各建一条独立 review 记录（或至少记录"已由独立审查文件覆盖，结论见 REVIEW-R03-claims.md"），否则 `quality.review.required=true` 下交付门禁无法合法通过。
8. **数字绑定**：把 statement 中引用的关键数字补成 metric refs（尤其是 0.445051、0.921018 严格版、0.8137、1.1139、legacy 0.6655、19619/8201/680、7/99、0.414 与 58/99、三个极差值）。

---

## 附录 A：本报告的关键证据位置

- 台账：`state/ledger.json`（claims[27..30]；`quality.robustnessPlans[ROB-0004..0006]`；`quality.checks[QC-0022/0024/0026]`；`validations[VAL-0047/0049/0050/0053/0054]`；`validationPlans[VP-0008..0011]`；`models[MODEL-0020/0047]`；`questions[Q2].selectionStatus`）
- Q2：`experiments/EXP-0041/{metrics.json,outputs.json,repeat*/sets.json,repeat*/bootstrap_pi.csv,repeat*/strict_top3_by_method.csv,candidate_scores.csv,experiment.json}`；`experiments/EXP-0071/`（快照）、`EXP-0072/`（rerun）；`src/q2_fix.py:180,189,191,353,681-720,845-856,1174,1197-1212`；`src/q2_lib.py:195-206`
- Q3 生成：`experiments/EXP-0042/{metrics.json,outputs.json,q3_metrics.csv,constraints.csv,samples.csv,samples_raw.csv}`；`EXP-0050/0054`；`src/q3_fix.py:399-410,480-490,1009-1010,1064-1080`；`outputs/audit/v6/legacy_recheck.json`
- Q3 迁移：`experiments/EXP-0043/{metrics.json,outputs.json,transfers.csv,transfer_constraints.csv,solver_certificates.jsonl}`；`EXP-0051/0055`；`src/q3_transfer_fix.py:454-470`
- 稳健性：`experiments/EXP-0062..0067/{metrics.json,result.json,experiment.json,seed-receipt.json}`；`EXP-0039/stdout.log`（repeat 0/1 腿）；`src/seed_receipt_wrapper.py`
- 协议/配置：`contest.yaml`（`evaluation.tuning`、`evaluation.split`、`quality.review/robustness`）；`data/splits/NESTED-CV-1/manifest.json`；`data/splits/SPLIT-0001/{meta.json,train.csv,test.csv}`；`data/clean/q3.csv`→`q3_thresholds.json`
- 磁盘验证：`validation/VAL-0047/{spec.json,result.json}`、`validation/VAL-0053/{spec.json,result.json}`；**VAL-0049/0050/0054 目录不存在**

## 附录 B：明确的 notChecked 摘要

见 §7。核心是：`robustness.js` 公式不可读（故只报互不一致，不判定哪个数是工具官方值）；runner 侧 seed-receipt 验证不可审计；从零重算 Q3 能量/旧错位/6.csv 全量对齐需要重跑（被禁止）。
