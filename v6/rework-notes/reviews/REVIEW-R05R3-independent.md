# REVIEW-R05R3 第三轮修复后独立复审（3 个对象）

- 审查者：`reviewer-1`（independent_context；只读 P，唯一写入 = 3 条 review-add + 本文件）
- 台账 revision **4481**；新增 review：REV-0071..REV-0073；未改被审对象，未跑 quality-plan/run/stale，未碰论文/交付。

| review | objectType | objectId | verdict | findings |
|---|---|---|---|---|
| REV-0071 | claim | CLAIM-0054 | passed | — |
| REV-0072 | claim | CLAIM-0055 | passed | — |
| REV-0073 | requirements-coverage | project-requirements-set | findings | F1 **major**：REQ-0004 仍引 CLAIM-0050（superseded→0055） |

## 核对要点

### CLAIM-0054（supersedes 0049）— passed
- scope：177 estimable cells / 21 styles / n_gen 729 + Tripel/Kriek/Lambic 27 cells / n_gen 147。
- 独立复算 `experiments/EXP-0079/q3_metrics.csv`（sha c7e8a495…）：design/copula-selected 按 n_gen 加权 → **0.8840256215416037**；三风格 27 格/147 → **1.8305764926829646**；逐风格 Tripel 0.2776752014 / Kriek 7.4607239855 / Lambic 0.6651002405。
- refs 8 个 metric key 全存在（含补回的 energy-V-raw、nearest-neighbor、edge-fraction），数值与 claim 一致；VAL-0066/0068 passed。
- SCRIPT-0018 重生成的 `outputs/q3/style_and_displacement_scope.json` sha=b7881974…、recordedAt=2026-10-26T15:00:00Z；inputs 的 q3_metrics/transfers hash 与当前文件匹配。F1/F2 已修。

### CLAIM-0055（supersedes 0050）— passed
- 模型：z 空间 231 维；目标 = `(z−zref)'Q_t(z−zref) + λ||z−z_anchor||² + ηΣt`（rank-10 二次 + λ anchor + L1）；约束 = box + 1 条 stale_cap 半空间；feasible≤1e-8。与 `experiments/EXP-0080/outputs.json` protocol.qp 一致。
- 198 证书/198 unique hash/198 optimal；max primal 9.989717e-9、dual 3.393784e-10、violation 0、KKT 5.616719e-9；nonenal 残差 3.556183e-17、butanedione QP 口径 1.804112e-16；qp-quantile-anchor 逐列 max/mean 位移与 claim 一致；nonincrease_all QP 两策略+source-fixed 1.0、target-mean-projection 0.414141；58 条仅参照控制。
- refs 6 个 metric key 全存在；VAL-0067/0069 passed。F1 已修。

### requirements-coverage — findings
- 已修复并核对：REQ-0001→CLAIM-0048、REQ-0003→CLAIM-0054、REQ-0007→CLAIM-0048/0055（均 active）；REQ-0002 note 改为“共表达图连通分量（非化学类别分组；不平衡 172/231）”；REQ-0007 blockedReason 已补回；artifact sha b7881974…/recordedAt 合法/数值可复算。
- **F1 major**：REQ-0004 的 claim ref 仍是 **CLAIM-0050**，而 CLAIM-0050 已 status=superseded、supersededBy=CLAIM-0055。按 checks.js `verifyEvidenceRef`，superseded claim 直接判 bad，requirement-coverage 检查会失败；REQ-0004 的 blockedReason/note 也仍写“CLAIM-0050 已绑…”。改指 CLAIM-0055 并同步 note/blockedReason 后需重新独立复审（本轮 REV-0073 绑定 requirementsVersion=ffdca764…）。
- REQ-0004 其余 refs（EXP-0080、transfer_constraints.csv、qp_cert_audit.json、style_and_displacement_scope.json）均存在；insufficient_data 语义仍正确（double threshold/Pareto 无当前证据）。REQ-0005 仍 insufficient_data、REQ-0006 covered 证据存在；REQ-0001..0004 记录 stale=true（sourceSha256=null）是 freshness 标记，交付前应刷新。

## 边界
- 3 条新 review 均 `independent_context`、`isRoot=false`；未修改任何被审对象。
- 本轮唯一 blocking 项是 REQ-0004→CLAIM-0050 的 retired ref；改指 0055 即可，不影响数值/insufficient_data 语义。
