# R03 未关闭项：需人类裁决或无法在本阶段修复的已登记记录

日期：2026-10-26。项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`。
本文件只记录**不能靠项目内写入解决的开放项**，并给出当前应采用的运行口径。它**不修改**任何已登记的台账记录、计划、验证或实验（红线）。

## 1 `REV-0040 F5`（major）— VP-0004 的预注册时序

- 事实：`VP-0004` 登记于 2026-10-26T08:04:51Z，而 `EXP-0039` 启动于 07:56:27Z；VP-0004 的 `protocolNote` 自称「在比较候选之前登记」，与自身时间戳矛盾。
- 唯一成立的预注册是 **config v2（07:44:30.383Z accepted）**：它把 `evaluation.tuning` 固定为 3 重复 × 3 外折、内 3 折、种子 20261025-27。
- 当前应读口径：**协议以 config v2 为准**；`VP-0004`/`VP-0011`/`VP-0009`/`VP-0010` 应视为“事后协议文档”，其 `protocolNote` 的时序声明不可信，只有检查项与容差本身可用。
- 为什么不能修：验证计划记录不可编辑；改 `protocolNote` 需要新建计划，但会让「计划与其后运行的验证」的绑定关系更混乱。
- 需要的裁决：接受“config v2 为唯一预注册、VP 记录为事后文档”这一口径，或要求重登记全部 VP 并重跑对应验证（成本：Q1/Q2/Q3 各一次独立复跑）。

## 2 `REV-0040 F6`（major）— 独立复跑的语义与磁盘证据

- 事实：`VAL-0048/0049/0050/0054` 的 `mode=fixed-seed-reproduction`、单 seed 20261025、`rerunOf` 指向同代码同数据同种子的源实验，delta=0 → **只证确定性，不证独立实现**；且 `validation/VAL-0048|0049|0050|0054` 在磁盘上**无目录**（仅台账内联记录，包行为）。
- 当前应读口径：本轮所有 “independent-rerun” 一律表述为**确定性重放**；真正的独立复跑需要（a）不同实现或（b）不同种子/数据的再训练，本轮未做。CLAIM-0031/0034 的 limitations 已按此披露。
- 需要的裁决：是否要求“独立实现型复跑”（新协议 + 新证据，工作量约 1 次全流程）；若不要求，请在最终交付说明中沿用“确定性重放”措辞。

## 3 `REV-0040 F9`（major）— 题面 questions 的文本口径

- 事实：`state/ledger.json` 的 `questions[Q1].evaluation` 仍写「候选必须在同一 SPLIT-0002 上与基线可比、50 维留出 MAE 为主」，`questions[Q2].evaluation` 仍写「与 6.csv 的独立 |r|」。
- 与新协议冲突：本轮 Q1 是 3×3×3 嵌套 CV（无 holdout）、主指标为 A/F30 OOF；Q2 是固定 200 行 + bootstrap、且 6.csv 只是同源对照。
- 为什么不能修：questions 由 `plan` 写入，编辑它等于改计划记录（需 re-plan，被红线禁止）；`problem/questions.yaml` 也不能单方面改（会与台账不一致）。
- 当前应读口径：**以 CLAIM-0035 / CLAIM-0031 的 statement + limitations 为准**；questions 文本只作历史计划文本。
- 需要的裁决：接受“claim 文本优先于 questions 历史文本”，或在后续允许 `plan` 修订时重登记 questions（届时旧证据需按名失效）。

## 4 `REV-0040 F12`（minor）— 记账类

| 子项 | 事实 | 当前处理 |
|---|---|---|
| `ledger.configSha256` 顶层字段 | 仍是 v1 的 `2ce0b2c3…`；`configLifecycle.acceptedRawSha256` 是 v2 的 `728811fc…` | 顶层字段是包遗留字段，不作协议身份；协议身份读 `configProtocolSha256=215d0941…`。不改台账。 |
| `EXP-0045/0046/0047` | 登记后从未运行（queued） | 保留为未启动历史，不删除；它们不进入任何 claim 的 refs。 |
| v5.1 论文格式必改项 | 未做 | 已在 `.rework/R03-CHANGE-LOG.md` §1 明确写“未做”，本轮阶段边界不做论文。 |
| `forkOrigin.ledgerSha256` | 与 SOURCE 当前字节不符 | 已在 `.rework/R00-fork-reconciliation.md` 记为不可复验的已披露限制。 |

## 5 一句话状态

四项开放项都不影响本轮**数值证据**（两轮独立复算均成立），影响的是**证据性质与历史文本的口径**。在人类裁决前，任何交付文本必须采用本文件第 1–4 节的“当前应读口径”，不得声称“独立实现复跑已通过”或“题面要求已按新协议修订”。
