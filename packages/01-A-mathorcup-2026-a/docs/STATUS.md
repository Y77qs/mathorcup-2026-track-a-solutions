# 交付状态（DRAFT） — 2026-MathorCup-A

> 本包是 **DRAFT**：`manifest.final=false`。以下逐条说明"已完成 / 未完成 / 为什么"。
> 台账 revision 444；实验 38 个（succeeded 19 / failed 8 / queued 9 / cancelled 1 / running 1）；
> claim 6 条、figure 15 张、validation 22 条。

## A. 已完成（可回读）

| 项 | 状态 | 证据 |
|---|---|---|
| 七检查点 intake / data-ready | ok | `state/ledger.json` |
| 数据核实（12 项题面-数据矛盾） | 完成 | `problem/statement.md` C1–C12、`outputs/audit/audit.json` |
| 混合尺度识别 | 完成（37 log10 / 33 linear / 161 unverified） | `outputs/audit/scale_identification.csv` |
| LOD/2 左删失识别 | 完成（755 格） | `outputs/audit/scale_report.json` |
| 2/5/6.csv 实为重算（非独立先验） | 完成（循环验证被识别并处置） | `CLAIM-0006`、REV-0011 |
| DATA-0002（250×284，284 条完整字段） + SPLIT-0002 | 已登记 | 台账 |
| Q1 最终候选 EXP-0025 五项验证 | 全 PASS | VAL-0013..0017、REV-0012 |
| Q1 0–6 分级表（四套口径） | 完成 | `outputs/q1/scores_0_6_{P1..P4}.csv` |
| Q1 model_bundle（供 Q3 推理） | 完成 | `outputs/q1/model_bundle.pkl(.gz)` |
| Q2 共表达图 | 完成（EXP-0003） | 231 节点 / 3918 边 / Q=0.318 |
| Q2 Q2 基线 | 完成（EXP-0035） | jaccard_mean=0.656（仅基线自洽） |
| Q3 基线 + 主模型 | 完成（EXP-0019 / EXP-0036） | 见 `CLAIM-0004` |
| 论文 md + tex + pdf | 产出 | `report/paper.md` / `.tex` / `.pdf` |
| 渲染（86 占位符全部可解析） | 通过 | `RENDER-0011` |
| 引用完整性 | 通过 | 6 条 claim 的证据全部可解析 |

## B. 未完成（必须如实披露）

1. **Q2 无候选 EXP、无法 `select`**：`outputs/q2/*` 来自 run-script（878s），未进 `modeling_experiment`。
   因此 Q2 只到"共表达图 + 基线"，Top-3 结论以**负结果**形式给出（`CLAIM-0005`）。
2. **Q3 `independent-rerun` FAILED（VAL-0012）**：`q3_eval.py` 固定 `SEED=42` 且读被重写的共享产物，
   `profile_spearman` 0.4073→0.8935。seed 稳定性证据**不成立**。
3. **稳健性计划 ROB-0001/0002/0003 均未执行**：`robustness-plan-execute` 要求"真正改变输入"的 ≥2 个实验；
   现有实验 seed/split/params 相同，被门禁具名拒绝（正确行为，未强推）。
4. **holdout 复用超限**：SPLIT-0002 被 19 个 succeeded 实验使用（阈值 3）→ 留出集已部分变成调参集，
   这是本次**最重要的方法学缺陷**，直接削弱 Q1/Q3 的留出指标解释力。
5. **`baseline-required` 未满足**：TGT-0001 声明了 labelRule，但缺"直接规则基线"实验。
6. **`target-lineage` 未被机械验证**：labelRule 语法不在可检查子集（`=` 处语法错误），
   一致性**未验证**。
7. **Q1 消融链不完整**：EXP-0031 FAILED（`q1_models.frozen_component_specs()` 不存在）；
   EXP-0038 为修后重跑（running）。故 ROB-0001 指名的 6 个扰动中只完成了部分。
8. **图 FIG-0001 过期未打包**：其文件字节在登记后被重绘；论文已改用 FIG-0013/0014/0015。
9. **`critical-findings` 状态 stale**：7 条 review（REV-0001..0005/0009/0011）在台账多次变更后过期，
   需 reviewer 在冻结后重新登记。
10. **`requirement-coverage` 为 needs_review**：16/16 机械链接完成，但**语义充分性仍需独立复核**。

## C. 交付边界

- `delivery.contest = null` → 未声明官方交付规范，按题面三项要求（论文/源码/图表与量化结论）执行，
  记为 `skip`，**不臆造竞赛平台要求**。
- 本包**未提交**任何竞赛平台；提交是人类的动作。
- 论文中的关键数字全部来自台账占位符（86 个，全部可解析）；未登记为 EXP 的数字（Q2 选择阶段）
  在正文中标注了来源文件与"未登记"状态。

## D. 若要推进到 final，需按序完成

1. 修 `q3_eval.py` 的 seed 局部化 → 重跑 EXP-0036 的 `independent-rerun`；
2. 把 Q2 选择拆成 ≤500s 的两个 EXP 并登记 → `select` → VP-0005 验证；
3. 登记一个"直接规则基线"实验以满足 `baseline-required`；
4. 用"真正改变 seed/split/params"的 ≥2 个实验执行 ROB-0001/0002/0003；
5. reviewer 重新登记 review 以清除 stale；
6. 用**未参与调参的新留出集**（或外部数据）重做一次锁定评估，解决 holdout 复用超限；
7. 重新 `freeze` → `deliver.check` → `package`（非 draft）。

---

## E. 交付后更正（收到 modeler-q1 的事实修正）

**EXP-0029（B6 四路融合）确已 `succeeded`**（49.8s，exit 0，四产物 verified），`r2_50dim = 0.253574`，
比当前选中的 `EXP-0025`（0.220579）高 **+0.033**。此前"B6 未登记成功"的说法作废。

处置：
- 已对 EXP-0029 补跑 4 项检查并全部通过：`VAL-0024`(leakage)、`VAL-0025`(split-integrity)、
  `VAL-0026`(holdout-metrics，单列 r2 复算差 2.2e-16)、`VAL-0027`(baseline-compare，r2_50dim 高于 0)。
- **第 5 项 `independent-rerun` 因计算槽被 EXP-0039 占用而未能执行**（`COMPUTE_BUSY`）。
- 按"验证通过才可选"的纪律，**本次仍选 EXP-0025 / MODEL-0022**（5/5 全 PASS）。
- **若 EXP-0029 的 independent-rerun 通过，应改选 MODEL-0023，Q1 headline 由 0.2206 更新为 0.2536。**
  这是明确的待办项，已在 `select` 的 reason 字段与台账中记录。

补充事实（来自 modeler-q1 的消融）：
- `EXP-0038`（去掉 5 个聚合列，226 特征）`succeeded`，`oof_r2_50dim = 0.25639`（vs 全特征 0.254512）→
  5 个聚合列的边际信息贡献 ≈ 0，**不构成泄漏通道**，保留或移除均可。
- 分层复核（dev 运行）：`r2_50dim = 0.2313`、`r2_overall = 0.0756`、MAE 0.3594、ρ 0.4703；
  主分割下 `overall` 维仅 0.0092 → **不应写"能预测总体喜好"**。

---

## F. 交付后更新（Q2 补齐登记）

1. **Q2 已可选中**：`EXP-0035`（基线，univariate-spearman，succeeded）→ `EXP-0039`（phase M1M4）→
   **`EXP-0041`（phase M2M3，完整选择）**，三者也解开了 `baseline-ready` 的 Q2 blocker。
   已 `select` **Q2 = MODEL-0032（EXP-0041）**。
2. **Q2 负结果换成登记版数字（此前正文引的是 dev 运行）**：
   `jaccard_mean = 0.1867`（仅 **1/50** 维 ≥0.5，中位 0.15）、`prereg_hit_rate = 0.0972`、
   `prior_spearman_mean = 0.6282`、可信度分级 **4/4 = 11 席(7.3%) / 3/4 = 21 席(14%) / ≤2/4 = 118 席(78.7%)**、
   `top3_stability = 0.2364`（B=100 快速代理，完整 B=300 尚未落盘）。
   已新建 **`CLAIM-0007`**（登记版负结果）以取代 `CLAIM-0005`（dev 运行数字 0.1623/0.1389）。
3. **M3 口径修正已记录**：`GraphicalLassoCV` 下 99.94% 偏相关为 0、Top-3 退化为列索引并列（artifact），
   主口径改为 Ledoit-Wolf 收缩（shrinkage 0.2189）；glasso-CV 结果保留为敏感性列
   `importance_matrix.M3_glassoCV_abs`。**未改阈值、未换方法凑绿**，Jaccard 与命中率仍是负结果。

## G. `freeze` 无法通过的原因（工具层，非结果层）

`freeze` 持续报 `question Q1/Q2/Q3: required check "leakage"/... has not passed`，即使
`modeling_validate run` 已产出 **PASS** 记录（`VAL-0013..0017`、`VAL-0020..0027`、`VAL-0018/0019`）。
根因是台账里 `validation` 记录的 `status` 与 `questionId` 字段为 `null`（仅 `result.passed=true`），
而门禁按 `status`/`questionId` 取数。**这属于宿主/插件记账缺陷，不通过直接改 ledger 绕过**
（用户与项目纪律均禁止改 ledger）。因此本次交付只能停在 DRAFT，并在此如实登记该阻塞。

---

## H. 收尾轮更正的数字与 claim

1. **预处理崩溃幅度更正**：协议字面预处理（无防护）在 **15 折**下的 ridge OOF R² = **−0.9301 ± 1.1423**
   （**39/50** 维为负），**不是 −2.66**（后者是 5 折单次试点的单折爆炸值）。
   机制更正：主因是 **1.csv 混合尺度**（33 个线性列 1e-9~1e3 与 37 个 log10 列混做折内标准化），
   不是"winsorize 本身"；三条防护几乎等价（尺度协调 0.1987 / winsorize 0.2002 / 裁剪 ±8 0.1997）。
   已同步修正 `outputs/protocol/decisions_log.md`（§2 第 18 行 + §7）与 `REPRODUCE.md`（§4b）。
2. **交付主表改 P2**：P1 在 250×50 上只产出等级 0–3（`[300,11663,494,43,0,0,0]`，93% 在 1 级），
   不满足题面"0–6 分级"要求；P2 覆盖 0–6（`[822,2802,2894,2679,2004,1113,186]`）。
   四套表全部保留，P1 作为物理锚定变体并列交付；变更理由见 `decisions_log.md §6`。
3. **Q3 迁移违反量以 `outputs/q3/transfer_report.json` 为准**：`max_defect_violation_raw = 0.0`、
   `max_box_violation_raw = 0.0`、`n_hard_feasible = 11/11`、判定阈值 ≤1e-9（解析投影兜底，不依赖 SLSQP 标志）。
   早期运行报告的 **7.9e-10 不是当前权威值**，只在 EXP-0030 的 `params.metricNote` 里留痕。
4. **新增 `CLAIM-0011`**（Q3，refs 严格同源 EXP-0024/EXP-0019），取代 refs 与陈述不一致的 `CLAIM-0004`。
5. **`CLAIM-0010` 含一处无关 ref**（EXP-0022 的 gen_style_fidelity，属 Q3 指标）——不导致解析失败，
   但属语义瑕疵，登记在此；claim 文本不可就地编辑，故不改。
6. **FIG-0001 永久性瑕疵**：登记（sha 6dee43f5）后我重跑绘图脚本覆盖了文件（现 sha 17123fbc，= FIG-0008/0013），
   **旧字节不可恢复**。`delivery.check` 会逐张校验所有已登记图，因此该条会长期 FAIL；
   正文不使用 FIG-0001，交付图用 FIG-0013/0014/0015。台账不允许直接修改，故此瑕疵保留披露。
7. **VAL-0013..0017 全 PASS 确认**：EXP-0025 五项检查（含 independent-rerun）全部通过，
   正文"EXP-0025 = 5/5 通过"准确；EXP-0029 = 4/5（仅缺 independent-rerun，队列 `EXP-0043` 待计算槽）。

---

## I. 最终交付快照（本轮定稿）

| 项 | 值 |
|---|---|
| 台账 revision | 518 |
| 实验 | 45 个登记（succeeded 25 / failed 9 / queued 6 / cancelled 1 / running 1） |
| claim | 11 条（关键 7 条：CLAIM-0001/0002/0004/0006/0010/0011 + 0003 描述性） |
| figure | 15 张登记（正文引用 8 张：FIG-0002/0003/0004/0005/0006/0013/0014/0015） |
| validation | 30 条（Q1 EXP-0025 五项全 PASS；Q3 VAL-0012 FAILED） |
| 论文 | `report/paper.md` / `.tex` / `.pdf`，**47 页**，overfull hbox 0、missing glyph 0 |
| render | **RENDER-0023**：113 个占位符全部解析，**0 stale / 0 warnings** |
| 工程检查 | **29/33 通过** |
| 质量门 | **13 通过 / 8 失败 / 2 待语义复核 / 5 不适用 / 1 过期** |
| 包 | `delivery/FINAL-DRAFT-2-DRAFT.tar.gz`，sha256 `2317a21bf4321778ca7e97997914387e9bd170b4c02418bdfb3b2a5c60496dfb`，193 文件 |
| 最终状态 | **DRAFT**（`final=false`、`submissionReady=false`）——**不冒充 final，不提交平台** |

**8 项质量失败（全部已具名，无一被掩盖）**：
`baseline-required`×3（缺直接规则基线）、`analysis-evidence`×1（Q2 缺 robustness）、
`robustness-execution`×3（ROB-0001/0002/0003 均未执行）、`holdout-reuse`（SPLIT-0002 被 **22** 个成功实验使用，阈值 3）。
**2 项待语义复核**：`requirement-coverage`（16/16 机械链接完成，语义充分性需独立复核定稿）、
`target-lineage`（labelRule 语法不在可机械检查子集，一致性未验证）。
**1 项过期**：`critical-findings`（7 条 review 在台账多次变更后 stale，需冻结后重登）。
**1 项永久瑕疵**：`figure:FIG-0001`（登记后重绘，旧字节不可恢复；正文不用该图）。
