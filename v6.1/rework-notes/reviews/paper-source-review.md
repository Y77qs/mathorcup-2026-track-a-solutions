# 独立复审：report/paper.md 与台账证据一致性（DRAFT 批）

verdict: **findings**

- 审查者：paper-reviewer（独立上下文；只读；仅写本文件与同名 `.json`）
- 审查时间：2026-10-27T00:49Z（CST 2026-10-27 08:49）
- 被审文件 SHA256（本报告行号以此版本为准）：

| 文件 | SHA256 | 说明 |
|---|---|---|
| report/paper.md | `be1ac20d89e01a3ebb085ee2ee0ba79d54843caa165d0ec3cdf1bcdf00cffcdf` | 审查期间 08:44:31 被外部改写一次：`12482c38…` → `be1ac20d…`（q1-styles 表由正文移入附录 A、两处引用更新、+1 行；正文数值未变） |
| report/evidence_manifest.json | `0b65d24a4f86d4ea86b7b8ffe2587219303344e3e1bc94c5c4942a6da30cf69b` | `ledgerRevision: 4614` |
| report/tables/INDEX.json | `1615bc7c69914f73352544ff5497a27072afe77cb185c0ff95065175b1e3a764` | `selfCheck.ledger.revision: 4615` |
| state/ledger.json | 观察期内在变：`5432caa7…` → `c31665f9…` → `c3e4e8de…` → `48705104…` → `3063efe8…` → `44697738…` → `be4e926c…`（00:49Z）→ `8d59e056…`（00:52Z） | revision 恒 4615、`updatedAt` 恒 `2026-10-26T15:35:58.351Z`、字节数 9,123,313→9,126,500；见 F7 |

只读声明：未修改 `report/paper.md`、`report/tables/**`、`report/evidence_manifest.json`、`state/ledger.json`；未运行 render / check / package / quality-run / check-stale / 任何会写台账或产物的工具。

## 审查方法（实际执行的步骤）

1. **claim 比对**：读 `report/evidence_manifest.json` 8 组记录，与 `state/ledger.json` 的 claim 记录做字符串级比对（statement、limitations、status、stale、claimType、scope）；逐条 limitation 在 paper.md 的边界/限制段落中定位对应披露。
2. **表片段完整性**：从 paper.md 提取 19 个 `<!-- table-begin:… sha256=… --> … <!-- table-end -->` 块，对 `body + "\n"` 重算 sha256，与块头、`report/tables/<id>.md` 字节、INDEX `outputs.md.sha256` 三方比对；对 INDEX 记录的 59 个输入文件逐个重算 sha256。
3. **数值独立复算**：不读表值下结论，直接从 `experiments/**` 原始产物复算（`oof_long.csv`、`predictions*.csv`、`q3_metrics.csv`、`constraints.csv`、`samples`.csv、`transfers.csv`、`transfer_constraints.csv`、`solver_certificates.jsonl`、各 `metrics.json`、`outputs.json`），覆盖 Q1 / Q2 / Q3 生成 / Q3 迁移 / 稳健性五类（明细见下表，共 30 项，超出 ≥8 要求）。
4. **占位符解析**：解析 paper.md 全部 `{{metric:EXP-x:key}}`（77 处、59 个不同组合）与 `{{claim:CLAIM-x}}`（8 处），逐个回台账核对实验 `status=succeeded`、metric 键存在、claim `status=active` 且 `stale=false`。
5. **禁止对象扫描**：对 paper.md、19 个 `report/tables/*.md`、`INDEX.json`（含其 inputs 路径）全文扫描 6 条退休 claim、先导轮 EXP（0038–0072、0076/0077）、退休 FIG（0025/0027）；核对 INDEX `allowedExperiments` 与任务白名单是否逐项相同。
6. **过度声称扫描**：`全面稳定|显著|显著优于|恢复人工评分|迁移准确率|优于基线|准确率|FINAL|最终提交版|最终交付|已通过|独立验证|外部验证|证明|领先` 逐条人工判读正/否定语境。
7. **scope 诚实性**：按任务清单 6 个子项逐项取证（分对象、source-resample 方向、三风格/21 风格池化、Q1 0–6、nonincrease 饱和、58 条越界归属）。

## findings

### F1 [major] Q3 可估生成样本数占位符解析为 750，与同句"分母口径为 729"自相矛盾

- file:line：`report/paper.md:478`
- 问题：句子为"21 个可估风格共 177 个可估格、可估生成样本 `{{metric:EXP-0079:n-samples}}` 的分母口径为 729（三次重复的合计）"。占位符在台账中解析为 `n-samples = 750`（198 个设计格合计，含被排除的 21 格/21 份），渲染后成为"可估生成样本 750 的分母口径为 729"，与"可估格 177 / 可估样本 729"的口径直接冲突，也与 CLAIM-0054 statement 的 `n_gen=729` 冲突。
- 证据：`experiments/EXP-0079/metrics.json`：`n-samples=750`、`n-cells=198`、`n-cells-excluded-from-energy=21`、`energy-distance=0.8840256`；我按 `q3_metrics.csv` 对 177 个可估格按 n_gen 加权复算：729 份、`E_V_norm=0.8840256215416037`；`report/evidence_manifest.json:323`（CLAIM-0054 limitation 1）写明"177 个可估格（n_gen=729）"。
- 建议处理：**本批可修**（仅改正文，不重跑实验、不动台账）：改为"177 个可估格共 729 份可估生成样本（另有 21 格/21 份因对照侧不足被排除）"；若要用占位符，下一批为 EXP-0079 增补 `n-gen-estimable=729` 指标键后改用。

### F2 [major] Q1 稳健性的"预注册"叙述与台账 CLAIM-0057 记录不一致（披露缺口）

- file:line：`report/paper.md:20`、`:727`、`:749`
- 问题：正文把四组稳健性检验统一表述为"在任何比较之前预注册"（727）、"每行是一次预注册的稳健性检验……判定规则与上限在比较之前登记"（749）、"相对极差均在各自预注册限内"（20）。但 CLAIM-0057 的 statement 明确写 ROB-0011 "属来源一致性修复、**非首次预注册**"，且其三个值与已被替代的旧 ROB-0007 逐位相同（0.354224 / 0.362434 / 0.357635）；CLAIM-0056 limitation 4 也要求保留"旧 ROB-0007 历史"。正文未披露这一点。
- 证据：`report/evidence_manifest.json:96`（CLAIM-0057 statement）、`:59`（CLAIM-0056 limitation 4）；ledger `claims[CLAIM-0057].statement`；正文 grep `ROB-0007|非首次预注册|来源一致性` 为 0 命中。
- 建议处理：**本批可修**（正文加注，不动台账）：在 §7.1 或 rob-confirmatory 表注后补一句"Q1 的 ROB-0011 属来源一致性修复性重登记，不是首次预注册；判定规则沿用既有上限，三值与旧 ROB-0007 逐位相同，仅证当前协议下一致"。若要与 claim 措辞完全统一，需下一批由 claim 维护者确认（本批不改台账）。

### F3 [major] q3-transfer-stages 的"逐列不增率"0.4141 与该表自己的定义不符：0.4141 是含代理的综合不增率

- file:line：`report/paper.md:674`（目标均值投影行）、`:676`（表注定义）、`:679`（正文断言）、`:784`（据此推断）
- 问题：表注（676）定义"逐列不增率是四个缺陷化学列在物理空间中'不变差'的比例"；但该格取自 metric `nonincrease-rate-target-mean-projection = 0.414141`，而该指标定义是"四个 cap 列全部不增 **AND** stale_hops 代理不增"的综合值。目标均值投影的四条 cap 列逐列不增率实际为 **1.0000**（`outputs.json` perField 四列均 1.0），0.4141 完全由 stale_hops 代理越界 58/99 驱动；同一行"老化酒花代理不增率"也显示 0.4141，等于把同一数字展示两次。784 行据此得出"约束确实有约束力"，实际有约束力的只是代理上限，不是四条化学 cap。
- 证据：`experiments/EXP-0080/outputs.json` → `nonincrease_by_strategy['target-mean-projection']`：`perField` 四项均 1.0、`staleProxyRate=0.4141414`、`nonincreaseRate=0.4141414`；`transfers.csv`：target-mean 行 `nonincrease_all` False=58/True=41，但四条 cap 的 `*_nonincreasing` 全为 True；`transfer_constraints.csv`：58 条 `infeasible` 全为 `target-mean-projection` + `upper_source_value_proxy` + `stale_hops`；我的独立复算：四条 cap 逐列不增率 99/99=1.0000，代理不增率 41/99=0.414141。
- 建议处理：**下一批修**（改 `src/paper_tables.py` 列名/取值后重生成表，且需同步 CLAIM-0055 措辞）：把该列改为"综合不增率（含 stale_hops 代理）"并另列"四条 cap 逐列不增率（均为 1.0000）"；或直接把 target-mean 行的"逐列不增率"改为 1.0000、0.4141 只留在代理列。784 行推断改为"该参照控制违反的是 stale_hops 代理上限（58/99），不是四条化学 cap"。

### F4 [major] 数据类别表数量相加为 236，与"化学表 231 列"矛盾（派生汇总量 5 被重复计数）

- file:line：`report/paper.md:72–78`（`37 / 33 / 161 / 5 / 50` 五行）
- 问题：`37 + 33 + 161 = 231` 已覆盖全部化学列；"派生汇总量 5"是这 231 列中的子集（`kcalperc` 属 37 个 log10 校准列，`acids_sum / esters_sum / aroma_hops_sum / sulfur_sum` 属 161 个未校准列）。把 5 另起一行相加得 236，与正文"化学表规模为 250 行、231 列"（`paper.md:64`）及 240 维输入口径（`paper.md:125`）不一致。
- 证据：`outputs/audit/v6/v6_constants.json` → `counts`：`{chemFeatures:231, log10Calibrated:37, linearCalibrated:33, uncalibrated:161, derived:5}`；`features[*]` 中 `kcalperc.tier=calibrated_log10`，其余 4 个 derived 为 `unverified_storage_scale`；`experiments/EXP-0079/outputs.json` `protocol.storageScale={log10_calibrated:37, linear_calibrated:33, uncalibrated:161}`。
- 建议处理：**本批可修**（手写表，不重跑）：把该行改为"其中：派生汇总量 5（含于上两行，不另计）"，或在表下补"合计 231（37+33+161）"并注明派生 5 为子集。

### F5 [minor] "显著高于"属未检验的显著性表述

- file:line：`report/paper.md:584`
- 问题：三风格池化 1.8306 与 21 风格池化 0.8840 是描述性池化值之差，Q3 协议没有为这两个池化值登记任何显著性检验；用"显著"会被读作统计显著。
- 证据：`outputs/q3/style_and_displacement_scope.json` 与 `EXP-0079` 只给点值（1.8305765 / 0.8840256），无检验量或不确定性；表行 569 只声明"不同范围，不可互换"。
- 建议处理：**本批可修**：改为"明显高于（描述性差异，未作显著性检验）"；同义句 `paper.md:796` 已用"明显高于"。

### F6 [minor] "加密检查"术语错误（应为"泄漏检查"）

- file:line：`report/paper.md:50`
- 问题：生成侧通过的验证是 leakage（VAL-0066）与 independent-rerun（VAL-0068）；不存在"加密检查"。该词会误导读者以为做过加密/加密数据处理检查。
- 证据：ledger `validations[VAL-0066]={checkType:"leakage", result.passed:true}`、`VAL-0068={checkType:"independent-rerun", result.passed:true}`；`report/evidence_manifest.json:398-407`。
- 建议处理：**本批可修**：改为"泄漏检查与复跑已通过"。

### F7 [minor] INDEX 的台账溯源哈希已与当前台账不符；审查窗口内台账被并发改写

- file:line：`report/tables/INDEX.json` → `selfCheck.ledger`（`sha256=85f2729…`、`revision=4615`）；`report/evidence_manifest.json:4`（`ledgerRevision: 4614`）
- 问题：审查期间 `state/ledger.json` 至少 8 个不同字节版本（见顶部哈希序列；大小 9,123,313→9,126,500 字节），而 `revision` 恒为 4615、`updatedAt` 恒为 `2026-10-26T15:35:58.351Z`。INDEX 记录的 ledger sha256 `85f2729…` 不对应任何观察到的版本，因此"表格索引—台账"这条溯源链当前不可复现。数值不受影响：19/19 表输出 sha256、59/59 表输入 sha256 仍全部匹配（见下节）。
- 证据：审查期 shasum 序列；`INDEX.selfCheck`；`manifest.ledgerRevision`；`state/ledger.json` 的 `revision/updatedAt`。
- 建议处理：**下一批修**（重生成 INDEX/manifest 时自然修复）：冻结/打包前重跑 `paper_tables.py` 与 manifest 生成，使 `selfCheck.ledger.sha256` 与 revision 指向同一版本；同时在交付说明中记录"台账在审查窗口内被并发写入"。不据此改任何数值结论。

### F8 [minor] Q1 claim 的"仅适用于当前候选"限制未进入正文边界文字

- file:line：`report/evidence_manifest.json:61`（CLAIM-0056 limitation 6）与 `report/paper.md:806–818`（§适用边界）
- 问题：8 条 active claim 的 limitations 逐条映射，仅此一条在正文"边界/限制"文字中没有对应披露。正文只写"在冻结协议下的内部折外重验证"（`paper.md:312`），没有"结论只适用于当前候选 MODEL-0048、当前数据与当前协议"的候选范围句；全文不含 `MODEL-`（附录 C 的 claim 占位符渲染后会带出 MODEL-0048，但那是核对材料，不是正文边界）。
- 证据：`report/evidence_manifest.json:61`；ledger `claims[CLAIM-0056].quality.limitations[5]`；grep `MODEL-|只适用于` 为 0 命中。
- 建议处理：**本批可修**（正文加一句）：在 §问题一的作用边界 或 §适用边界 增写"结论只对当前冻结候选（图正则低秩）与当前数据/协议成立"。

### F9 [minor] q3-quality 同一行混用 729 / 750 两种分母，与"全部可估格"标注不完全一致

- file:line：`report/paper.md:563–566`（前四行"范围说明"列）、`:571`（表注）、`:574`（正文占位符段）
- 问题：主方案行的 energy-distance / U / diversity / nearest-neighbor 是 177 个可估格、729 份生成的 n_gen 加权值（我按 `q3_metrics.csv` 复算逐位一致）；而 edge-fraction 0.1199 的分母是 `231×750=173250` 个单元格（`20775/173250=0.1199134`，含未进入能量距离的 21 格/21 份生成），duplicate-share 同理按全 750。行标注"该方案的全部可估格"与 edge/duplicate 的实际分母不一致（数字本身与产物一致，问题在标注）。
- 证据：`EXP-0079 outputs.comparisons[*].design` 的 `edge-fraction` 值（0.1199134199 / 0.1209062049 / 0.1122481962 / 0.1222164502 / 0.1196825397）与 `20775/173250` 精确相等；同一行的 diversity=19.7356472 与 729 份加权值精确相等。
- 建议处理：**下一批修**（表注/表生成脚本）：注明"edge-fraction 与 duplicate-share 以 231×750 个单元格为分母；其余四项按 177 格/729 份加权"，或统一口径重算。

## 逐条清单结果（一页）

| # | 检查项 | 结论 | 关键证据（行号均为 `be1ac20d`） | 关联 |
|---|---|---|---|---|
| 1 | claim↔正文一致性（8 active） | **基本通过**：8/8 statement+limitations 与台账逐字节相同、数值不矛盾；limitation 逐条映射仅 1 条未入正文（F8），另 1 条预注册限制未披露（F2） | `paper.md:14/199/478/569/584/679/747`；manifest 8 组；台账 claims 8 条 | F2, F8 |
| 2 | 过度声称 | **通过**（1 处 minor）：DRAFT banner 在 `paper.md:10`；`FINAL` 0 命中；"全面稳定/恢复人工评分/迁移准确率/优于基线/准确率"均为否定或定义句；唯一正面"显著"在 584 | `paper.md:10/54/259/576/657/713/812` | F5 |
| 3 | 数字抽查（≥8） | **通过**：19/19 表片段三方哈希一致；59/59 输入哈希一致；30 项原始产物复算逐位一致（明细下节） | `report/tables/INDEX.json`；`experiments/**` | — |
| 4 | 退休/禁止对象 | **通过**：paper.md、19 个 table .md、INDEX.json（含 inputs）中 0 命中：CLAIM-0012/14/18/19/21/22、EXP-0038..0072、EXP-0076/0077、FIG-0025/0027；INDEX.allowedExperiments 与白名单逐项相同 | `INDEX.allowedExperiments`；全量 grep | — |
| 5 | 占位符可解析 | **基本通过**：77 个 metric（59 distinct）全部指向 succeeded 实验且键存在；8 个 claim 全部 active、stale=false；但 478 处把 `n-samples=750` 当成 729 使用（F1） | ledger experiments/claims；`paper.md:478` | F1 |
| 6 | scope 诚实性 | **基本通过**（1 处标签错配 F3 + 1 处分母标注 F9）：①生成/迁移分开 `474` ②source-resample 0.8137 在表内且方向正确（"生成未超过参照"）`576/717` ③三风格 1.8306/27/147 与 21 风格 0.8840/177/729 分列 `568/569/584/586` ④Q1 0–6 为训练分布内相对等级、不恢复人工评分 `14/246/259/812` ⑤nonincrease=1.000 为构造上界/饱和 `681/747/758` ⑥58 条越界仅 target-mean-projection 参照控制 `683`（我复算 58 行全为该策略 stale 代理） | 见左 | F3, F9 |
| 7 | 证据层级 | **通过**：Q1 无留出集、split-integrity 与 holdout-metrics 结构性不可满足、选择为草稿选择 `312-316, 810`；Q3 无原生 optimization VAL、无迁移准确率 `657/713/715`；Q1/Q3 `selectionStatus=provisional`、Q2 `validated`（ledger questions） | 见左 | — |

## 数字抽查明细（全部从原始产物独立复算；30 项）

| 表/单元格 | 论文值 | 复算值 | 复算来源与方法 |
|---|---|---|---|
| q1-models 图正则低秩 A/F30 MAE | 0.3593 | 0.359291565882 | `EXP-0073/oof_long.csv`，37500 行 mean\|pred−true\| |
| q1-models 最小中位数基线 全50 | 0.3919 | 0.391880048737 | 同上（median 模型 37500 行） |
| q1-models 普通 Ridge A/F30 | 0.3667 | 0.366661758011 | 同上（ridge 模型） |
| q1-groups 第2次重复·第1折 MAE/样本/基线 | 0.3643 / 76 / 0.4039 | 0.364282838 / 76 / 0.403867792 | `EXP-0073/oof_long.csv` 按 repeat/fold 重算（A/F30） |
| q1-groups 风味 15 维组 | 0.3540 | 0.353957 | 同上，F_ 前缀 15 维池化 |
| q1-styles Tripel MAE/啤酒数 | 0.3786 / 28 | 0.3786 / 28 | 同上 + `predictions_all_models.csv` 的 beer→style |
| q1-grades 图正则低秩 等级MAE/整级一致率/二次κ | 1.4111 / 0.2289 / 0.3321 | 1.4111 / 0.2289 / 0.3321 | `oof_long.csv` 37500 个 grade 格重算（7×7 加权 κ） |
| q1-grades 参照等级 0 档 / 6 档计数 | 3190 / 3195 | 3190 / 3195 | 同上 `grade_true` 计数 |
| q2-stability 主 Jaccard（π 优先集合） | 0.2091 | 0.2091111111 | `repeat{0,1,2}/strict_top3_by_method.csv`：50 维×6 方法对×3 次重复=300 对/次 |
| q2-stability 点估计 Jaccard | 0.1977 | 0.1976666667 | `candidate_scores.csv` 严格 216 宇宙按四种方法点估计 Top-3 重算 |
| q2-stability π 均值 / π<0.5 | 0.4205 / 1263/1800 | 0.4204566667 / 1263/1800 | 3 次重复 × 4 方法 × 150 条 = 1800 条 π |
| q2-stability 跨重复 Jaccard | 0.8748 | 0.8748333333 | 三次重复交付集合两两 Jaccard（600 对） |
| q2-core-top3 香气·麦芽总体 furfural | 0.490/0.9767/+·内 | π=0.49、S=0.9767442、ρ_total=+0.263407、\|ρ_within\|=0.266383≥0.8\|ρ_total\| | `EXP-0075/candidate_scores.csv` |
| q2-universe 216/3/7/5/231 | 216/3/7/5/231 | 216/3/7/5/231 | `candidate_scores.csv` kind 计数（10800/150/350/250 行 ÷50） |
| q3-quality 主方案 V/U/多样性/最近邻 | 0.8840 / 1.1139 / 19.7356 / 17.6323 | 0.8840256215 / 1.1138668333 / 19.7356471944 / 17.6323085333 | `EXP-0079/q3_metrics.csv` 177 可估格、729 份 n_gen 加权 |
| q3-quality 源样本重采样参照 | 0.8137 | 0.8137313224 | 同上（model=source-resample，177 格/729 份） |
| q3-quality 三风格单独池化/格数/n_gen | 1.8306 / 27 / 147 | 1.8305764927 / 27 / 147 | 同上，Tripel+Kriek+Lambic |
| q3-raw-design 原始 V/V_raw/U | 0.8843 / 16.1872 / 1.0881 | 0.8842957424 / 16.1872010126 / 1.0880562226 | 同上 stage=raw 加权 |
| q3-raw-design 投影轮数 均值/最大/最大残差 | 1.4798 / 5 / 0.0000 | 1.4797979798 / 5 / 0.0 | `EXP-0079/outputs.json` projection_rounds、design_projection |
| q3-constraints 19619/8201/680/0/28500 与占比 | 见表 | 19619/8201/680/0/28500；0.688386/0.287754/0.023860 | `EXP-0079/constraints.csv` verdict 计数（28500 行） |
| q3-constraints 线性非负 18613/5951/186/0 | 见表 | 18613/5951/186/0（24750 行） | 同上 bound_type=lower_zero |
| q3-qp-certs 198/optimal/最大原残差/对偶/违反/KKT/最大迭代 | 198/198/9.99e-09/3.394e-10/0.0000/5.617e-09/49 | 198/198/9.9897175e-09/3.3937841e-10/0.0/5.6167186e-09/49；198 唯一 problem_hash、99/99 锚定 | `EXP-0080/solver_certificates.jsonl` |
| q3-transfer-stages QP·分位 V/归一化/不增率/代理/fallback | 2.2611 / 0.1236 / 1.0000 / 1.0000 / 0.0000 | 2.2610805 / 0.1236358 / 1.0 / 1.0 / 0.0 | `EXP-0080/outputs.json` energy_by_strategy、nonincrease_by_strategy |
| q3-transfer-stages 目标均值投影 V/归一化/自距 | 6.9415 / 0.3794 / 4.749e-16 | 6.9414828 / 0.3794023 / 4.7490841e-16 | 同上 |
| q3-transfer-columns 反-2-壬烯醛 残差/位移max/mean | 3.556e-17 / 0.0010 / 1.019e-05 | 3.55618e-17 / 0.00100885 / 1.01904e-05 | `transfer_constraints.csv` residual + `transfers.csv` \|opt−src\| |
| q3-transfer-columns 双乙酰 残差/位移max/mean | 1.804e-16 / 0.5239 / 0.0939 | 1.80411e-16 / 0.523886 / 0.0939044 | 同上 |
| q3-transfer-columns 4VG 残差/位移max/mean | 0.0000 / 0.3233 / 0.0127 | 0.0 / 0.323279 / 0.0127085 | 同上 |
| rob Q1 三值 / 绝对极差 / 相对极差 | 0.3542/0.3624/0.3576；0.0082；0.0232 | 0.3542235462/0.3624339082/0.3576345991；0.0082103620；0.023178476 | `EXP-0100/0101/0102/metrics.json`；EXP-0100 另用 `oof_long.csv` 独立复算=0.354223546186 |
| rob Q2 三值 / 绝对 / 相对 | 0.2103/0.2073/0.2053；0.0050；0.0238 | 0.2103333/0.2073333/0.2053333；0.005；0.023772 | `EXP-0089/0090/0091/metrics.json` |
| rob Q3gen 三值 / 绝对 / 相对 | 0.8778/0.8765/0.8982；0.0217；0.0247 | 0.8777844/0.8764530/0.8981550；0.0217020；0.0247236 | `EXP-0092/0093/0099/metrics.json` |
| rob Q3mig 三值 / 极差 | 1.0000/1.0000/1.0000；0.0000 | 1.0/1.0/1.0；0.0 | `EXP-0095/0096/0097/metrics.json`（饱和，见 F3） |

> 方法说明：点估计 Jaccard 首次用"全部 231 候选"复算得 0.1967，与论文 0.1977 不符；改为按论文口径的严格 216 单体候选宇宙重算后精确等于 0.1976666667，差异来源是扩展指标不应进入严格榜（与 `paper.md:320-338` 一致）。edge-fraction 的 0.1204（729 份加权）与表中 0.1199 的差异已定位为分母 231×750（F9），不是数值错误。

## 未决 / 本批不可核验

1. **"已通过且未过期"中的"未过期"**：VAL-0063/64/65/56/57/66/67/68/69 的 `result.passed` 均为 true（已核）。但台账中这些 validation 记录本身**没有 `stale` 字段**，只有 manifest 写 `stale: null`；本批按指令未运行 check-stale，因此"未被标记过期"只能引用 manifest 快照，不能独立核验过期状态。
2. **"工具具名拒绝"的回执位置**：split-integrity（EXP-0073 未登记 splitId）、holdout-metrics（无 holdout）、optimization-feasibility/objective（EXP-0080 无 `params.optimization`）在 ledger `validations` 中没有对应记录；其"具名拒绝/结构性不可满足"只见于 `validationPlans` 的 protocolNote（VP-0015、VP-0014）与 Q3 selection reason 文本。因此论文 `paper.md:314/662/713/810` 的措辞有台账文字依据，但无法从 validation 记录侧复核"拒绝回执"本身。
3. **被审文件的并发改写**：`paper.md` 在审查窗口内被改过一次（见顶部）；`state/ledger.json` 被多次改写。本报告所有行号、哈希均以 `be1ac20d` / 00:49Z 快照为准；若之后再有编辑，需重新定位行号。
4. **9 处 `<!-- PENDING-FIGURE:… -->` 与"未 render/check/package"**：属本批预期状态（任务背景已声明），不计缺陷；但交付前必须补齐，且 `paper.md:772/1246` 已如实声明未执行。

## 覆盖统计

- active claim：8/8 核对（statement、limitations、status、stale、claimType、scope）。
- 表：19/19 片段三方哈希一致；59/59 输入哈希一致；19/19 INDEX `status=COMPLETE`。
- 占位符：77 处 metric（59 distinct）全部可解析；8 处 claim 全部 active。
- 数值：30 个单元格独立复算，逐位一致（1 处点估计口径差异已定位并排除）。
- 禁止对象：0 命中。
- findings：critical 0 / major 4 / minor 5。

## 第二轮复审（REV-2）

- 复审对象：`report/paper.md`，本轮基准 **SHA256 = `1822930befc84ef3b4f7b25d6e28ae7ead1c7d61ff032196ea42cf5e512a11c5`**（mtime 2026-10-27T08:54:07 CST / 00:54Z；1274 行、126,003 字节）
- 对照快照：`report/tables/INDEX.json` = `a06c594853cf1b9626f3f1ac000a5ee90da43ac1a3e997d1f9d679716f7b5ec6`（generatedAt 2026-10-27T00:53:15Z）；`.rework/refresh_table_block.py` = `2121a702726602d2f7d473288384af4bf9fe5266f9b9a61676d2127e5eb0cfed`
- 复审时间：2026-10-27T00:56Z
- 只读纪律：未修改 paper/tables/ledger/manifest；未运行 render/check/package/quality-run/check-stale/refresh 脚本；未重做 30 项全量复算（按 Lead 指定只核对 9 项 + 2 项事实，另抽查了表块哈希链与关键术语）。
- 版本时间线（审计窗口内 paper.md 被外部改写）：`12482c38…`（REV-1 起始）→ `be1ac20d…`（08:44:31）→ `c319ac53…`（08:52:27）→ `71c08c83…`（08:53:43）→ `1822930b…`（08:54:07，本轮基准）。REV-1 的 F1/F2/F3/F4/F5/F6/F8/F9 已在本轮基准上复核为 resolved，REV-1 记录按原样保留。
- **REV-2 总体 verdict：findings（指定 9 项 9/9 resolved，无 regressed；仅剩 N2/N3 两项 minor 文字项与 F7 台账溯源项，均 minor）**

### 9 项指定核对（行号以 `1822930b` 为准）

| # | 项 | verdict | 新文本证据 |
|---|---|---|---|
| 1 | F1（§6.1） | **resolved** | `paper.md:480`："21 个可估风格共 177 个可估格、729 份可估生成样本（三次重复合计）"；"设计格总数为 `{{metric:EXP-0079:n-cells}}`、生成样本总数为 `{{metric:EXP-0079:n-samples}}`；729 与 750 的差额即被排除部分，两者不可互换"。台账 `n-cells=198`、`n-samples=750`，渲染后自洽；`n-samples=750` 不再被当作 729 使用 |
| 2 | F2（§7.2 问题一段） | **resolved** | `paper.md:758`："该检验属**来源一致性修复后的重登记**，不是首次预注册……三组扰动值与旧记录逐位相同……因此本组只证'当前协议下一致'，不能读作一次新的独立稳健性证据"；与 `CLAIM-0057` statement 及 limitation 一致 |
| 3 | F3（正文） | **resolved** | `paper.md:681` 明确分开两个量："四条化学列（DMS、双乙酰、4VG、反-2-壬烯醛）的不增率在四种策略下都是 1……综合不增率另要求 stale_hops 代理不增……这一低值完全由代理上限的越界驱动，不是化学 cap 失败"；§8 `paper.md:790` 已同步改为"该低值完全由 stale_hops 代理上限越界造成、四条化学 cap 仍全为 1；真正有约束力的是代理上限，而不是三条物理缺陷阈值"（不再暗示化学 cap 有约束力） |
| 4 | F3（表） | **resolved** | `paper.md:671-676` 表块列为：转移能量 V / 归一化 V / **四条化学列不增率 / 老化酒花代理不增率 / 综合不增率（含代理）** / fallback 份额 / 目标均值自距。行值：qp-quantile 1.0000·1.0000·1.0000；qp-source 1.0000·1.0000·1.0000；source-fixed 1.0000·1.0000·1.0000；target-mean **1.0000·0.4141·0.4141**。表注 `paper.md:678` 含"综合不增率 0.4141 不等于四条 cap 有 58% 不满足"。与 `experiments/EXP-0080/outputs.json` 的 `perField`（全 1.0）与 `staleProxyRate`（0.4141）逐位一致 |
| 5 | F4 | **resolved** | `paper.md:77`："其中派生汇总量 \| 5（含于上两行，不另计）\| …属子集，合计仍为 231"；37+33+161=231 可读出，不再出现 236 相加矛盾 |
| 6 | F5 | **resolved** | 全文"显著"仅 2 处且均为否定/限定：`paper.md:196`"不构成对任一分量的显著性结论"；`paper.md:586`"值明显高于……这是描述性差异，本文未对两个池化值作任何显著性检验"；无未加限定的正面"显著"表述 |
| 7 | F6 | **resolved** | `paper.md:50` 已为"生成侧的**泄漏检查**与复跑已通过"；全文"加密"0 命中。第 48–50 行三段验证名（泄漏检查 / 基线比较检查 / 独立复跑）与 ledger `checkType`（leakage / baseline-compare / independent-rerun）一致，未见同类术语错误 |
| 8 | F8 | **resolved** | `paper.md:318`："第四，结论只适用于当前冻结候选（图正则低秩）、当前数据版本与当前协议。更换候选、更换数据或改变划分/协议后，本节的误差与等级数字都不可沿用……"；同节 `paper.md:310` 已同步改为"四条硬边界"（旧"三条硬边界"已修，与四项一致） |
| 9 | F9（表） | **resolved** | `paper.md:565-569` 每行"范围说明"列已写明"能量/U/多样性/最近邻按 177 格 · 729 份加权；复制率与边饱和按 231×750 格"；表注 `paper.md:573` 写明"精确复制率与边饱和比例的分母是 231×750 = 173250 个存储单元格（750 行），其中包含未进入能量距离的 21 个不可估格 / 21 份生成，因此两类指标的分母不是同一批格" |

### 两项事实确认

**（1）19 个表块四等一致：全部满足。** 逐个重算 `body+"\n"` 的 sha256，并与块头 sha、INDEX `outputs.md.sha256`、`report/tables/<id>.md` 字节比对：

- 全部 19 块：`块头 sha256 == INDEX == 片段文件字节 == 块内 body(+末尾换行)`，0 例外；begin/end 成对、无重复 id、无残留 `<!-- TABLE:` 占位。
- 本轮 Lead 重刷的两块：`q3-quality` = `577eb42b7cbd5046…`、`q3-transfer-stages` = `361b6f06bf5e18b3…`，均与 INDEX/文件/块内 body 四方一致；其余 17 块亦一致。
- 另：9 处 `<!-- PENDING-FIGURE:… -->` 保留、78 处 metric 占位符（60 distinct）全部可解析、8 处 claim 占位符全部 active 且 stale=false、禁止对象 0 命中（本轮快速复扫）。

**（2）`state/ledger.json` 仍在被并发改写（F7 仍开放）。** 观察窗（00:38Z–00:56Z）内至少出现 14 个不同 sha256（`5432caa7… / c31665f9… / c3e4e8de… / 48705104… / 3063efe8… / 44697738… / be4e926c… / 8d59e056… / e19970e5… / f5f0431a… / 2db5121… / 1882bb08… / f8657d2b… / 6d38231d…`），字节数 9,123,313→9,177,294；`revision` 始终为 4615、`updatedAt` 始终为 `2026-10-26T15:35:58.351Z`（即写入未伴随 revision 变更）；单次 4 秒观察窗内稳定，但不能据此认定已停止。
**对"论文数值可追溯性"的结论影响**：不影响数值本身的追溯——论文/表里的数来自不可变实验产物（19/19 表输出的 sha256 与文件、INDEX 一致；59/59 表输入 sha256 仍匹配；关键指标仍逐位等于 `experiments/*/metrics.json`，REV-1 已复算 30 项）。受影响的只是"表格索引 → 台账快照"这一层：INDEX `selfCheck.ledger.sha256 = 0b875be1…`（00:53:15Z 生成）已不等于当前台账字节，manifest `ledgerRevision=4614` 也落后于台账 `revision=4615`。建议在台账静默后重新生成 INDEX/manifest 再冻结，或在交付说明中记录"台账在审查窗口内被并发写入、revision 未随字节变化"。

### REV-2 新增/遗留项（均 minor，无 critical/major）

- **N1（已消除，不计 open）**：`paper.md:310` 已由"三条硬边界"改为"四条硬边界"，与 `paper.md:318` 新增的"第四"一致——REV-1 修复过程中引入的计数错误已修。
- **N2 [minor] still-open**：`paper.md:683`"四个综合 1.000 也必须一起读"与事实不符。四个策略的综合不增率是 1.0 / 1.0 / 1.0 / 0.4141，只有**三个** 1.000（target-mean-projection 为 0.4141，见 `paper.md:671-676`）。建议改为"三个综合 1.000"（或"三个策略的综合值为 1.000"）。
- **N3 [minor] still-open**：§6.10 已把复合指标命名为"综合不增率（含代理）"，但摘要 `paper.md:18`、rob 表 `paper.md:751`、稳健性正文 `paper.md:764`、结论 `paper.md:802` 仍以"逐列不增率"指代复合 metric `nonincrease-rate`（EXP-0080/EXP-0095/0096/0097）。建议统一为"综合不增率"，或在首次出现处注明"旧称逐列不增率"。
- **F7 [minor] still-open**：同"两项事实确认（2）"。

### REV-2 结论

- Lead 指定 9 项：**9/9 resolved，0 regressed**。
- 仍开放：N2、N3（文字，一行可修）、F7（重生成 INDEX/manifest 或在交付说明中记录）。无 critical / major。
- 若 N2/N3 修完且 F7 以"记录台账并发写入"方式处置，本复审可给出 passed；在此之前总体仍为 findings（minor only）。
