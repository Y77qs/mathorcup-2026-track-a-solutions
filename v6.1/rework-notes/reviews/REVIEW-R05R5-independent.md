# REVIEW-R05R5 Q1 来源一致性修复复审（4 个对象 + Q3 文档只读核对）

- 审查者：`reviewer-1`（independent_context；只写本文件 + 4 条 review-add）
- 台账 revision 4556；新增 REV-0075..REV-0078。未改被审对象，未跑 quality-plan/run/stale，未碰论文/交付。

| review | objectType | objectId | verdict | findings |
|---|---|---|---|---|
| REV-0075 | robustnessPlan | ROB-0011 | passed | — |
| REV-0076 | claim | CLAIM-0056 | findings | F1 minor（缺 EXP-0074/mae_all50 refs） |
| REV-0077 | claim | CLAIM-0057 | passed | — |
| REV-0078 | requirements-coverage | project-requirements-set | passed | — |

## ROB-0011 — passed
- preregisteredAt=15:16:37.780Z < EXP-0100/0101/0102 startedAt（15:17:26/30/33Z）；experimentIds[0]=EXP-0100 参考。
- 三条实验 code.sha256 + dependencies 的 src/robustness_wrapper.py 全部 7d7ab6aca6c24df154bd096fda15bd0717a3e9ec6217778ed8475424b43cfdec（当前文件）；9 个依赖逐 hash 无 drift，sourceSnapshot=true，seed-receipt.json 存在。
- EXP-0102 params.lambdaMultiplier=0.5（number）进入 inputSignature；pairs=seed + params:lambdaMultiplier；methods 满足。
- decisionRule={relative-range,limit:0.05} 无自由文本 reference；分母=首个实验 0.35422354618559243 → 0.023178476；message="relative spread 0.023178 <= 0.05"。旧 ROB-0007 的 0.008210（分母=1）未复现。
- result.values 与 EXP-0100/0101/0102 metrics.mae 逐位一致；executedAt 晚于实验。
- 旧 ROB-0007 未改：version=2、updatedAt=14:20:32.231Z、experimentIds=[0086,0087,0098]、message 仍 0.008210；符合“保留历史”。

## CLAIM-0056 — findings（minor）
- 状态/绑定正确：0048 superseded→0056；active/critical；appliesTo=ROB-0011；VAL-0063/64/65 passed。
- refs 四 keys 存在：EXP-0073/0100/0101/0102:mae；值 0.359291565882 / 0.35422354618559243 / 0.36243390816790516 / 0.35763459908881995，与 statement、ROB-0011 一致。
- 独立重算：A/F30=0.359291565882、all50=0.350504156920、EXP-0074=0.398177328373、差=0.038885762491；相对极差=0.023178476。
- F1：statement 报基线 0.398177 与 all50 0.350504，但 refs 缺 EXP-0074:mae 与 EXP-0073:mae_all50（旧 0048 有）；VAL-0064 覆盖 baseline-compare，但 metric refs 不完整。
- 限制保留：provisional、split/holdout、确定性重现、2/3 种子、绝对/相对极差分列、旧 ROB-0007 历史。

## CLAIM-0057 — passed
- refs=EXP-0100/0101/0102:mae，值一致；statement 的 unified wrapper 7d7ab6aca6c2 经三条实验 code/deps 核对；绝对 0.008210/相对 0.023178；decisionPassed=true；限制完整；旧 ROB-0007 历史披露。

## requirements-coverage — passed
- REQ-0001→CLAIM-0056、REQ-0002→0041、REQ-0003→0054、REQ-0004→0055、REQ-0007→0056/0055；全部 active，脚本逐条校验 0 problems（无 missing/superseded/stale claim、failed exp、retired figure、missing file）。
- REQ-0004 仍 insufficient_data 且 blockedReason 具名；REQ-0005/0007 same；REQ-0001/0002/0003/0006 covered 有证据。
- artifact sha b7881974…、recordedAt 2026-10-26T15:00:00Z；177格/729=0.8840256217、27格/147=1.8305764927 复算一致。
- REQ-0001..0004 stale=true（sourceSha256=null）为 freshness 标记，交付前刷新。

## Q3 文档只读核对（不在正式审查范围，不写 review-add）
- `outputs/q3/decision.md` 存在（23:19 本地）。两处与当前 claims 不一致：
  1. §2“约束残差（clamp(new−source,0)）最大：nonenal 1.009e-03、butanedione 5.239e-01”把**位移 max**当成了残差；EXP-0080/CLAIM-0055 的残差 max 是 3.556e-17/1.804e-16，位移 max 才是 0.001009/0.523886。
  2. §1“ROB-0009 … relative spread 0.021702 <= 0.05”复现旧 ROB-0009 的分母=1 标签；active CLAIM-0053/0054 说绝对 0.021702 / 相对 0.024724。文档与 raw ROB-0009 记录一致，但与更正后的 claim 不一致。
- `outputs/q3/robustness_confirmatory.json` 不存在；现存 `outputs/q3/robustness.json`（23:19，同样复现 ROB-0009 旧标签）与 robustness_generation/transfer_confirmatory.json（22:21）。若按 raw 记录生成，会继承上述旧标签。
- 其余 Q3 数字（0.884026/1.830576/0.813731/198 certificates/1.0 vs 0.414141/saturation/provisional）与当前台账一致。
