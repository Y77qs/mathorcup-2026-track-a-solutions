# 本轮证据性质记录（先导/探索性 → 锁定协议后的确认性复跑）

日期：2026-10-26（第二轮工作，确认性轮次）。项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`。
本文件**不修改**任何已登记的 VP/EXP/CLAIM 历史内容，只登记“应如何读这些记录”。

## 1 先导轮（探索性）的范围

- 以下实验属**先导/探索性证据**，不再作为确认性证据引用：`EXP-0038`…`EXP-0072`（含 Q1 0023–0035 系列、Q2 0041/0071/0072、Q3 0042/0043/0050/0051/0054/0055、稳健性 0062–0067，以及全部失败/未启动记录 0037/0040/0044/0045/0046/0047/0049/0052/0059/0061/0068/0069/0070）。
- 对应计划 `VP-0004`、`VP-0009`、`VP-0010`、`VP-0011` 与 `ROB-0004/0005/0006` 同属先导轮记录。

## 2 `config v2` 的准确含义（更正此前措辞）

- `config v2`（accepted 2026-10-26T07:44:30.383Z，protocol `215d0941…`）**只表示在较早时间冻结了 3×3×3 调参框架**（3 重复 × 3 外折、内 3 折、种子 20261025-27、按 `tasting_category_fine` 分层）。
- **不再**把 `config v2` 称为“唯一完整预注册”：它冻结的是框架，不含候选集合、选择规则、容差与输出契约。
- `VP-0004`（08:04:51Z）晚于 `EXP-0039` 启动（07:56:27Z），**不得**再声称“比较前登记”；其 `protocolNote` 的时序声明作废，仅检查项与容差可用。`VP-0009/0010/0011` 同理属事后协议文档。

## 3 复跑语义

- `VAL-0048/0049/0050/0054` 等 `mode=fixed-seed-reproduction` 的记录，统一称**确定性重现**；**不得**称“独立实现复跑”或“外部独立验证”。
- 本轮新增的 fixed-seed independent-rerun 同样只称确定性重现。
- 多种子结果只用于稳健性，不与固定种子确定性重放混称。

## 4 run-control 治理限制

- 先导轮全部实验（`EXP-0038`…`EXP-0072`）在**没有 controlled-run 覆盖**的情况下执行：`counters.RUN=0`、`runControl.runs=[]`。
- 这是**治理限制**，如实保留；**不为覆盖历史而补建形式化 controlled run**。本轮新建的受控 run 只覆盖其开始之后的工作，不得声称追溯覆盖既有实验。
- 补记：2.8.10 的 `run-control preflight` 模块检查比较 `probe.modules[name]===true`，而 probe 只写版本字符串，故 `requiredModules` 布尔检查无法启用；这不是“模块专项检查通过”。

## 5 F12 口径

- 台账顶层 `configSha256` 保持历史的 v1 值（`2ce0b2c3…`）不改；**当前协议身份读** `configLifecycle.acceptedProtocolSha256 = 215d0941…` 与 `acceptedRawSha256 = 728811fc…`。
- `forkOrigin.ledgerSha256` 不改；“SOURCE 字节级不可复验”保留为已披露限制；“宿主内存未刷盘”仍是**未证实假设**（见 `.rework/R00-fork-reconciliation.md`）。
- 历史 `queued`/`failed` 记录保留，不进入任何新 claim 的 refs。
- 以上均为**当前版本限制**，不称“已修复”，也不称“永久无法修复”。

## 6 复算说明修正与证据索引（2026-10-26T14:34Z，本批）

`src/r04_independent_recompute.py` 与 `.rework/R04-independent-recompute.json` 已**重写并真实重跑**（`SCRIPT-0014`；脚本 sha256 `55cf2689…`，输出 sha256 `65dda05d…`），修正以下被此前文本误用的口径：

| 项 | 修正后的定义 | 来源 |
|---|---|---|
| π | 候选在实际 bootstrap 重复中进入该维 Top-k 的**不同重复数** / 文件中实际重复数（本轮 = 500），不是“每行份额” | `experiments/EXP-0075/bootstrap_pi.csv` |
| 0.1199 | `edge-fraction` = 标准化矩阵中处于**声明边界**（floor code / 观测支撑 min-max / 0）的单元格比例；**不是约束贴边比例** | `experiments/EXP-0079/outputs.json::q3.comparisons.copula-selected.design.edge-fraction` |
| 3.556e-17 / 1.804e-16 | `transfer_constraints.csv` 的**约束残差** `clamp(new−source,0)`（nonenal / butanedione）；**不是** `transfers.csv` 的 new−source 位移（同策略实测 stored 位移 nonenal 0.001009、butanedione 0.523886、4VG 0.323279） | `experiments/EXP-0080/transfer_constraints.csv` vs `transfers.csv` |
| 经验 V / U | V 为无符号经验能量距离；U 为**带符号**诊断量，可负、不截零、不开根；两者分开报告 | `experiments/EXP-0079/outputs.json::constraint_definitions` |
| 复跑语义 | 固定种子 independent-rerun = **确定性重现**，不是独立实现、不是外部验证 | VAL-0057/0058…（本轮 VAL-0057/0065/0068/0069） |

证据索引（同时包含 QP 与 z 空间复现）：

- `.rework/QP-EVIDENCE-CLARIFICATION.md`：58 条越界全部是 `upper_source_value_proxy` / `stale_hops(ridge-proxy)`，且**只出现在 target-mean-projection 参照控制**（QP 策略 0 条）；与 `max_constraint_violation=0`（198 个 QP 的 box+半空间）不是同一对象。
- `SCRIPT-0011`（`src/q3_zspace_recompute.py`）：用 EXP-0080 冻结快照 + 确定性代码重建 9 组 `centre/scale`，396/396 行 `l1_change_z`/`mean_abs_change_z` 复算 delta = 0.0 → **z 位移可复现**；但该复现**不等于** QP 目标或最优性获得原生 optimization VAL。
- `SCRIPT-0010`（`src/q3_cert_audit.py`）：198 证书全 optimal、198 唯一 problem_hash、max violation 0、max primal 9.9897e-9、max dual 3.3938e-10；`upper_source_value_proxy` 有 4/396 行与记录残差相差 1.0000004e-9（保留，不抹平）。
- `SCRIPT-0009` **failed**（首版把存储空间位移误当 z 空间位移）保留为审计历史，不删除、不改写。
