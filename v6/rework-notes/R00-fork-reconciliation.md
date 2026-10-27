# R00 对账说明：adopt-copy 的字节级与内容级核对

日期：2026-10-26。对象：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`（下称 P），
来源：`SOURCE=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3`（只读，未写入、未运行任何实验）。

本说明只记录**已核实的事实**与**未证实的假设**，不修改 `forkOrigin`，不声称字节级复验通过。

## 1 fork 记录（P 台账，未改动）

| 字段 | 值 |
|---|---|
| `forkOrigin.source` | `/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3` |
| `forkOrigin.revision` | 2790 |
| `forkOrigin.ledgerSha256` | `3dd298cc7990cb541861177fb414e41612f389a12f5ae06c4bcd04a16e3e377a` |
| `forkOrigin.at` | 2026-10-26T07:15:06.864Z |
| 接收事件 | revision 2791，`actor: modeling_project`，`reason: "adopt an independent immutable project snapshot"`（全台账只出现 1 次） |
| 快照说明文件 | `.rework/v6-source-snapshot.json`，同一 source 与同一 ledgerSha256 |

## 2 SOURCE 现状（只读，2026-10-26 实测）

| 字段 | 值 |
|---|---|
| `revision` | 2769 |
| `state/ledger.json` sha256 | `07e15fcd237dc63f2e0539b650f6ea8b292957c059bbfb4659981efa23553738` |
| 最后一条事件 | 2026-10-26T06:20:47.484Z，`actor: host-usage`，`reason: "settle native host request usage"` |
| 事件窗口 | 保留最近 500 条（首条 2026-10-24T13:52:49Z / revision 2270） |

## 3 字节级结论（未通过，如实记录）

`forkOrigin.ledgerSha256 = 3dd298cc…377a` **无法**由 SOURCE 当前可读台账复现（当前为 `07e15fcd…353738`）。
该哈希字符串在本机只出现在两处：P 的 `state/ledger.json`（`forkOrigin` 字段本身）与
`.rework/v6-source-snapshot.json`。全盘检索 `/private/tmp` 与 `~/Documents/MATHORCUP` 未找到第三份可核验副本。
`.rework/evidence/snapshot/state/ledger.json` 是更早的快照（revision 1985，sha `f4186a12…`），不是本次 fork 基准。

**未证实假设（不得写成结论）**：adopt-copy 可能哈希的是宿主内存中的台账（revision 2790，含尚未落盘的
host-usage 结算事件），而 SOURCE 磁盘文件滞后在 revision 2769。revision/updatedAt/events 任一差异都会改变
字节哈希，因此该假设能解释差异，但没有证据能证明它。

**该缺口作为已披露限制保留**：本项目的字节级 fork 复验不成立；任何后续报告不得写“fork 哈希已复验通过”。

## 4 内容级对账（已通过）

对 P 与 SOURCE 两份台账逐对象比较（JSON 规范化后逐字段比对）：

| 集合 | 对象数 | 差异 |
|---|---|---|
| `splits` | 2 | 0 |
| `claims` | 22 | 0 |
| `figures` | 31 | 0 |
| `validations` | 43 | 0 |
| `datasets` | 4 | 0 |
| `models` | 15 | 0 |
| `validationPlans` | 3 | 0 |
| `experiments` | 36 | 36 条均有差异，但**仅限 adopt-copy 归一化字段**：`forkedFromStatus`（新增）、`pid`/`token`/`queueRequestedAt`（清空） |

结论：除 adopt-copy 自身的运行状态归一化外，P 与 SOURCE 在全部语义集合上**内容全等**。
`holdoutExposures` 的历史（SPLIT-0002 三次曝光）被 `exposureHistoryImported=true` 标记并保留原样。

## 5 处理

1. 不修改 `forkOrigin`（红线）。
2. 后续所有证据以 P 自己的台账与文件为准，不以 SOURCE 复核作为通过条件。
3. 若将来需要字节级复验，只能在**不写入 SOURCE**的前提下另行取证（例如由宿主提供当时内存台账的副本），
   并同样以“已披露限制”记录，而不是事后重写 `forkOrigin`。
