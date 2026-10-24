# 重跑前准备审计（PREP-AUDIT）

- 项目：`/Users/baozhashizitou/Documents/MATHORCUP/work/beer-rerun-2.8.6`
- 包版本：`dsh-vibe-math` **2.8.6**（desktop profile）
- 解释器：`reference-quality-env/bin/python` 3.12.14（numpy 2.3.5 / pandas 2.2.3 / scipy 1.18.1 / sklearn 1.9.1 / openpyxl 3.1.5）
- 审计时间：2026-10-24 13:11（Asia/Shanghai）
- 审计范围：**Phase 0–2（init / plan / data / contracts & requirements）**，不含 baseline、validation plan、experiments、claims、quality-run、reviews、freeze、package。
- 审计方式：读台账 + 独立重算 + 直接调用 2.8.6 `runCheck` 只读检查；未写 QC 记录。
- 执行方式说明：本次 prep 通过**已安装的 2.8.6 runtime 直接调用**（与 pack 服务层同一实现），未在宿主 GUI 里点击新建会话/选择 preset；GUI 可见性与监控属于人工验收项，见第 8 节。

## 1. 结论

**PASS（准备范围内）**。所有“重跑前必须成立”的门禁均通过；没有跨过任何不可逆门。
**NOT READY（重跑阶段）**：baseline-ready 还差 3 个真实基线，validation plan 尚未登记（设计上应在 baseline 之后、candidate 之前），claims/reviews/quality-run 均未开始。这是预期状态，不是缺陷。

## 2. 硬门禁

| 检查 | 结果 | 证据 |
|---|---|---|
| 2.8.6 包 | PASS | `package.json` version 2.8.6；probe ok |
| 配置在 init 前定稿 | PASS | `contest.yaml` 写入后 init；`configChanged=false` |
| config sha 一致 | PASS | 文件 `cae08b254ec1e03c215ffc9699957a7e47ca28a8962c36f9beb8c91cf92607f3` == ledger `configSha256` |
| 未跨不可逆门 | PASS | experiments=0、validationPlans=0、claims=0、QC=0、reviews=0、robustnessPlans=0 |
| 旧项目未被写入 | PASS | 旧 ledger mtime 12:50:38 < 本次 prep 开始 13:08；旧 `contest.yaml` 仍 45f3b9b2… |

## 3. 数据与划分

| 项 | 结果 |
|---|---|
| 原始附件 | 9 个，经 `import` 复制 + SHA；`data/raw/imported` 9 个，sh 与旧项目一致 |
| 数据脚本 | SCRIPT-0001 prepare、0002 build_q2raw、0003 build_q1mapped、0004 build_q3，全部 `succeeded` |
| DATA-0001 | `data/clean/q2_raw.csv`，250 行 × 284 列；fields=284 覆盖完整；sha 与台账一致 |
| DATA-0002 | `data/clean/q1_mapped.csv`，250 × 284；parent=DATA-0001；50 维 mapped grade |
| DATA-0003 | `data/clean/q3.csv`，250 × 250；targetColumn=`ethanol..v.v.`；风格/阈值视图 |
| SPLIT-0001 | DATA-0001，200/50，seed=20261024，assignment `e3addc6c…` |
| SPLIT-0002 | DATA-0002，200/50，seed=20261024，assignment `e3addc6c…`（与 SPLIT-0001 **相同**） |
| SPLIT 行 ID | 两个 assignment 的 250 行 ID 完全一致；train/test 集合一致 |
| Q1 映射 | `q1_map_params.json`：split_reference=SPLIT-0001，n_train=200；用 q2_raw 独立重算 q1_mapped 的 50 维映射，**max|Δ|=0** |
| Q3 风格留出 | `q3_style_holdout_assignment.csv`：style_holdout=1 共 **49** 行（Tripel 28 / Lambic 11 / Kriek 10） |
| fields | 三个数据集字段数与真实表头一致、无重复列、字段覆盖完整（2.8.6 逐列校验已通过） |

> 注意：SPLIT-0001 只用于估计 mapped-grade 的 zmin/zmax；**SPLIT-0002 才是 Q1 评估 split**。两个 split 不允许同时跑实验；Q2/Q3 不设随机 splitId。

## 4. 小问 / 要求 / 契约

| 项 | 结果 |
|---|---|
| questions | Q1/Q2/Q3，intake checkpoint = 0 blocker |
| requirements | 6 条 must_answer；`source.quote` 在题面文件中精确出现 1 次；`source.path` 存在 |
| target contracts | TGT-0001（Q1，transformed，DATA-0002，50 targets）、TGT-0002（Q2，observed，DATA-0001，50 targets）、TGT-0003（Q3，constraint，DATA-0003，231 targets）；targetColumns 全部真实存在 |
| model contracts | MCON-0001/0002/0003 均有 variables + objective + formula + boundaryCases；公式只用 2.8.6 声明式子集 |
| 契约公式重算 | 6 个 boundary case 全部通过（Q1: 0/6/3；Q2: 0/1.5；Q3: 1.2/1.0） |
| 记录过期 | 12 条 quality 记录（6 REQ + 3 TGT + 3 MCON）全部 `stale=false` |
| 只读检查 | `source-anchor` = passed；`model-condition` = passed；`target-lineage` = needs_review（等待 Q1 transformed 的独立 review）；`requirement-coverage` = failed（尚未映射/审查，预期）；`baseline-required` = failed（尚未跑基线，预期） |

## 5. 检查点状态（status）

| stage | 状态 | 说明 |
|---|---|---|
| intake | PASS | 3 个小问完整 |
| data-ready | PASS | 3 datasets + 2 splits，hash 未变，不相交 |
| baseline-ready | 预期未过 | 3 × NO_BASELINE（Phase 3 待做） |
| modeling | PASS（当前） | 尚无候选/计划，不触发 |
| validation | PASS（当前） | 尚无 selected model，不触发 |
| writing | 预期未过 | 3 × NO_CLAIM + NO_PAPER（Phase 7/9） |
| delivery | 预期未过 | NOT_FROZEN（Phase 8） |

> `stage.current` 仍是 `intake`：本次 prep 未调用 kernel `advance`；判断以 checkpoint 为准。若宿主提供 kernel 任务面，在 Phase 1 后可 `advance` 到 data-ready，但不得跳过 baseline-ready。

## 6. 审核发现与风险（进入 Phase 3 前必须知道）

1. **Q1 的 0–6 语义**：题面要求 0–6 分制，交付是 mapped grade。REQ-0002 已如实保留“0–6”原文；后续 coverage 只能走两条路之一：
   - 登记 `insufficient_data` + `blockedReason`（诚实，但 final 不会打开）；
   - 由独立 review 明确接受“mapped grade 是唯一可复核代理”，再登记 `covered`。
   **不要改题面/要求文本适配结果。** 这是进入 Phase 7 前必须由你拍板的语义决定。
2. **Q3 契约的 targetColumn 代表性**：TGT-0003 的 `targetColumn=acetaldehyde`，DATA-0003 的 `targetColumn=ethanol..v.v.`；两者都在 231 个 targetColumns 内，target-lineage 不依赖 targetColumn（无 labelRule）。若要在语义上完全一致，可在 Phase 7 前用 `contract-revise` 改 TGT-0003，并重绑 MCON-0003；不要等到 review 之后改。
3. **quality 聚合当前 23 项 pending**：这不是失败，是尚未 `quality-plan`。**不要现在跑 `quality-plan auto`**；等 claims/contracts/robustness 全部定稿后再 plan，避免把错误 metricKey 固化成永久 QC。
4. **Q2/Q3 不设 splitId**：Q2 的脚本必须只读 SPLIT-0001 的 train 行（作为 `params.dependencies`），Q3 必须用 style_holdout 视图；在 validation plan/claim 里如实写“关联分析/风格留出”，不要冒充随机 holdout。
5. **Q1 holdout 预算**：SPLIT-0002 最多 3 次成功曝光（baseline + Ridge + HistGBM）；Ridge 的 independent-rerun 走 verifiedRerun；稳健性用 train-only/OOF，不要再用 SPLIT-0002。
6. **validation plan 还没登记**：这是有意的。baseline 跑完后再登记（Phase 4），且每问只登记一次；用 2.8.6 的参数名（`baselineExperimentId`、`forbiddenColumns`+`correlationThreshold`、`simulation-seeds` 的 `expectedRange`/run JSON）。

## 7. 下一步（按顺序）

1. **Phase 3 基线**（3 个真实实验）：
   - Q1：`constant-train-mean`，`params.features:[]`，DATA-0002 + SPLIT-0002，metric=mae；
   - Q2：全局统一 Top-3，DATA-0001（train 行），metric=topk-jaccard；
   - Q3：无条件全局高斯，DATA-0003（style holdout），metric=constraint-satisfaction。
2. **Phase 4 validation plan**：Q1 五项；Q2 leakage + independent-rerun；Q3 leakage + simulation-seeds + independent-rerun；每问一次，且在 candidate 之前。
3. **Phase 5 candidates**：每问 ≤2；全部带 `freezeSources/dependenciesComplete/dependencies`。
4. 之后才进 robustness、claims、coverage/reviews、quality-plan/run、freeze、render/check/package。

## 8. 审计判定

- **准备阶段：PASS**（config sha、数据、划分、字段、契约、公式、无不可逆门均通过）。
- **可重跑性：READY**（可以从 Phase 3 开始）。
- **final：不可宣称**（claims/robustness/quality/reviews/freeze/package 均未开始；这是预期，不是失败）。

人工验收缺口（不阻塞 prep，但不要声称已完成）：
- 未在 GUI 新会话中选择 “Vibe Math Modeling” 并跑 probe（本次用已安装 2.8.6 runtime 直接执行）；
- 未点开“◈ 解题监控”核对角色/工具/实验/质量分列；
- 未做安装包逐字节验收（版本号已核对为 2.8.6，probe ok；正式交付前按 04 做 SHA/文件清单核对）。
