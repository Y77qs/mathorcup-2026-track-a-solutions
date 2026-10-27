# REVIEW-R05R2 修复后独立复审（8 个对象，MathorCup 2026 A）

- 审查者：`reviewer-1`（fresh context；只读 P，唯一写入 = 14 条 review-add + 本文件）
- 台账复审时 revision **4461**；新增 review：REV-0063..REV-0070
- 未改 claim/coverage/contract 记录；未跑 quality-plan/run/stale；未 render/package；未碰论文/交付。

## 8 条复审

| review | objectType | objectId | verdict | findings |
|---|---|---|---|---|
| REV-0063 | claim | CLAIM-0048 | passed | — |
| REV-0064 | claim | CLAIM-0049 | findings | F1 minor（scope 885 cells）、F2 minor（V/NN/edge 无 metric ref） |
| REV-0065 | claim | CLAIM-0050 | findings | F1 minor（“L1 目标”不完整） |
| REV-0066 | claim | CLAIM-0051 | passed | — |
| REV-0067 | claim | CLAIM-0052 | passed | — |
| REV-0068 | claim | CLAIM-0053 | passed | — |
| REV-0069 | requirements-coverage | project-requirements-set | findings | F1 **major**（旧 claim refs 未重映射）、F2/F3 minor |
| REV-0070 | targetContract | TGT-0002 | passed | — |

## 关键核对

### CLAIM-0048（Q1）— passed
- EXP-0073/oof_long.csv 重算：graph-lowrank A/F30 MAE=0.359291565882、all50=0.350504156920；median=0.398177328373=EXP-0074；差 0.038885762491。
- ROB-0007：0.35422354618559243/0.36243390816790516/0.35763459908881995；绝对极差 0.00821036198231273；spread/|首个值| = **0.023178476**；claim 分列 0.008210/0.023178 并披露分母=1，正确。
- VAL-0063/64/65 passed；2/3 种子、split-integrity/holdout-metrics 缺口保留。

### CLAIM-0049（Q3 生成）— findings
- 独立重算：design/copula-selected，按 n_gen 加权：全 **177** 可估格（21 风格，n_gen=729）= **0.8840256215416037**；Tripel/Kriek/Lambic **27** 格（n_gen=147）= **1.8305764926829646**；逐风格 Tripel 0.2776752014 / Kriek 7.4607239855 / Lambic 0.6651002405。与 artifact（sha 4dc72fff…）逐项一致。
- **F1**：scope 写 “(885 cells)”，实际 177（885=177×5）；0.884026/1.830576 不受影响。
- **F2**：supersede 时删掉了 EXP-0079:energy-V-raw ref，V/nearest-neighbor/edge-fraction 三个数字无 metric ref；建议补回。
- source-resample 0.813731 更优、constraint-satisfaction 构造性质、无原生 optimization VAL、双对象、2/3 种子均保留；VAL-0066/68 passed。

### CLAIM-0050（Q3 迁移）— findings
- 独立复算：198 证书/198 唯一 hash/198 optimal；max primal 9.989717e-9、dual 3.393784e-10、violation 0、KKT 5.616719e-9；nonenal 残差 3.556183e-17、butanedione QP 口径 1.804112e-16；qp-quantile-anchor 逐列 max/mean 位移与 claim 一致（nonenal 0.001008854/1.019044e-5、butanedione 0.523885882/0.093904405、4VG 0.323278758/0.012708453）；nonincrease_all：QP 两策略+source-fixed 1.0、target-mean-projection 0.414141；58 条 infeasible 全属参照控制的 stale_hops proxy。
- **F1**：claim 写 “box+1 条 stale_cap 半空间与 **L1 目标**”，但 EXP-0080/outputs.json protocol.qp 的实际目标为 `(z−zref)'Q_t(z−zref) + λ||z−z_anchor||² + ηΣt`（Q_t rank-10 二次项），L1 只是第三项；建议补全或引用 protocol.qp。solver status/残差结论不受影响。

### CLAIM-0051/0052/0053（ROB-0007/8/9）— passed
- 0.008210/0.023178（≤0.05）、0.005000/0.023772（≤0.10）、0.021702/0.024724（≤0.05）均独立重算一致；decisionPassed=true 不变；2/3 种子、500→200、饱和/构造性质、不与 Q1/Q3 合并均已披露；refs 与实验值逐位一致。

### requirements-coverage — findings
- **F1 major**：REQ-0001 仍引 CLAIM-0040（superseded→0048）、REQ-0003 仍引 CLAIM-0042（→0049）、REQ-0007 仍引 CLAIM-0040+CLAIM-0043（→0048/0050）；`verifyEvidenceRef` 对 claim 的 superseded 直接判 bad，requirement-coverage 检查会 fail；note 里的旧 id 也需同步。
- REQ-0004 的 insufficient_data 正确：refs 为 CLAIM-0050(active)+EXP-0080+transfer_constraints+qp_cert_audit+style_and_displacement_scope，blockedReason 与 EXP-0080/EXP-0079 的当前约束口径一致；降级不是把 insufficient_data 当 covered。
- **F2 minor**：REQ-0002 note 称 modules 为“化学类别分组”，实际 modules.definition 是 |W|>0.5 共表达图连通分量（200 行训练集），readingNote 明说不平衡（172/231）。
- **F3 minor**：新 artifact 的 `recordedAt="2026-10-26T15:0xZ"` 非法；SCRIPT-0017 真实 startedAt=14:59:21.041Z。
- REQ-0005/REQ-0007 仍 insufficient_data 成立；REQ-0006 covered 证据存在。REQ-0001..0004 记录 stale=true（sourceSha256=null）是 freshness 问题，交付前应刷新。

### TGT-0002（revision 2）— passed
- revisions 最后一条 revision=2（14:40:52Z）；record version=3（不是“revision 3”）。
- 216 严格 + 15 扩展（7 理化+5 派生+3 元素/指数）与 EXP-0075 category_counts 完全一致；219−3=216；strict_top3 只含 single_compound、extended 只含扩展类别；dataset 50 列全部是 DATA-0001 字段；6.csv 明写同源非外部验证；taskNature=association_analysis、labelSource 不预测/不因果。
- 记录 stale=true（deps 无 per-input snapshot）是历史 freshness 标记，REV-0028 也在 stale=true 下 passed；内容本轮对齐。

## 边界
- 14 条旧 findings（REV-0049..REV-0060）经 review-resolve 全部 `resolved=true`（lead 消息写 15 条，实际计数 14 条；无遗漏未解决项）。
- 本文件与 8 条新 review 均为 `independent_context`、`isRoot=false`；未修改任何被审对象。
