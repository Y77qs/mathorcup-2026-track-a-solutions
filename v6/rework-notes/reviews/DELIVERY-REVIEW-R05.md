# DRAFT 交付独立审查（R05 / delivery reviewer, fresh independent context）

项目：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`
审查对象：当前 DRAFT 交付范围（report/paper.md + .rework/previews/preview-D/ + 台账 active 证据 + accepted 配置）
审查方式：只读 + 独立脚本重算 + pypdf 逐页/逐坐标读数 + sips 光栅化目检。未运行 render/artifact/check/package/quality-run/实验。

## 0. 绑定核对（sha256）

| 对象 | 实测 sha256 | 期望/记录 | 结论 |
|---|---|---|---|
| report/paper.md | e61b2410b9aee9fe9a5753096535a76e55c3b9a95743db2604e687c26a6f4b81 | = RENDER-0012.inputSha256 | 一致 |
| .rework/previews/preview-C/rendered.md | deda7968116520f33edc35acaf3217b0242a9dca9a9fea68c458abf7663e16d5 | = BUILD-INPUTS.sourceSha256 / preview.tex source-sha256 | 一致 |
| preview.pandoc.md | 96b54bae7e3423624ee8e4df65421df78ffeeb5ecf8ca0068c4df2d56401d8c9 | = BUILD-INPUTS.preprocessedSha256 / tex pandoc-input-sha256 | 一致 |
| preview.tex | 17f91379709f903dfea6344d66f05721a93a8957ec57b5482234ab60b6cbe64b | = BUILD-INPUTS.outputs[].sha256 | 一致 |
| preview.pdf | dffb83fb2eada3bfe3b53c5869afc12b2123713ccd53247e96b05aba85deee35 | = BUILD-INPUTS.outputs[].sha256 | 一致 |
| src/build_paper.py | 6f62c823d880a7a3aa45698bd2aace6aad010856d29b7a7381b7999445487d58 | = BUILD-INPUTS.builder.sha256 | 一致 |
| src/build/header.tex | 0d35a9640f355225d95df79ac4512c7b2eb670ed0c9bbda69bd9e5a634cd3926 | = BUILD-INPUTS.support[0] | 一致 |
| src/build/template.tex | b1140b188bdc5e1864c6a052a243f991d16fd0661db4078e5cfe69322ebfa042 | = BUILD-INPUTS.support[1] | 一致 |
| report/tables/INDEX.json | 6a78f7ce8d0da89451efbe2de925e453ceccf6412513f8ef313b0452e9309605 | = BUILD-INPUTS.inputs[1] | 一致 |
| report/evidence_manifest.json | db5980ed5981189dd4d824371905dee56e66501b4df84adbb5e347e9ec13d561 | = BUILD-INPUTS.inputs[4] | 一致 |
| contest.yaml | 728811fc888fef0b4d16b0513be5bac87ab5c420f5809861c14052cc9e5c3733 | = configLifecycle.versions[1].rawSha256（v2 accepted） | 一致 |

台账：`modeling_project status` 返回 `configState.state = in_sync`、`acceptedVersion = 2`、`configRawSha256 = 728811fc…`、`configProtocolSha256 = 215d0941…`、`needsReview = false`、revision 4658。
台账 sha 在审查期间不稳定（同一 revision 4658 上两次 hash 不同，疑似并发写），故此表只按 revision 4658 记录内容事实。

## 1. PDF 实测（不采信 log）

- 真实页数（pypdf）：**30**，A4 595.28×841.9pt。
- 页码序列：PDF 1–3 **无页码**（1 标题/摘要/DRAFT、2–3 目录跨两页），正文页码 **1** 出现在 PDF 第 4 页，至 PDF 第 30 页 = 正文 **27**，连续无缺。
- 页脚：页码 y=36.9pt，x≈292.2–294.9（版心中心 297.6，偏差 ≤1.4pt）→ 居中页脚。
- 页眉：30/30 页在 y>H−60 区域**无任何文字**（visitor 坐标实测），即无页眉；tex 无 fancyhdr。
- 目录：59 条目；58 条带页码逐条与正文实际页核对 **58/58 一致**；「摘要」条目**无页码**（\addcontentsline 无页码）。
- 首页 DRAFT：`DRAFT——科学证据与交付限制见文末，非最终提交版` 以 draftbanner 出现在第 1 页（DRAFT 全文 4 次）。
- 匿名性：无作者/单位/学校/学院/致谢/邮箱；`\author{}` 为空（"单位"命中均为计量单位，非机构）。
- 图：内嵌图像 **9**，图号 1–9 连续，9 条题注全中文且与台账 caption **逐字相同**（归一化后 9/9 EXACT）；9 张图文件字节 sha 与台账 **9/9 匹配**。
- 表：编号题注 **表 1–15 连续**；15 张 paperIncluded 全部内联；4 张 supportOnly 未内联。
- tex 静态检查：未解析 `{{...}}` = 0、`PENDING-FIGURE` = 0、`fancyhdr` = 0、`LTcaptype` 包装 = 0。
- 缺字：xelatex log `Missing character` = 0；中文/数学符号（ρ、⊤、Σ、‖、∈、0–6、τ）目检正常。
- Overfull：log Overfull = 0 / Underfull = 1。实测版心 L=62.36pt、R=532.92pt；越左界者仅 4 处，全部是以全角左括号「（」开头的中文标点悬挂（x≈55.1–56.4pt，悬挂 6–7pt），属 xeCJK 正常排版，**非越界缺陷**；右侧无越界项。

## 2. 表/支撑材料（`src/paper_tables.py --verify`）

`verify: 19/19 complete, 0 problem(s)`；INDEX 自检记录 per-table md/csv sha 与磁盘一致；15 张内联表的 `<!-- table-begin:<id> sha256=… -->` 与 INDEX `outputs.md.sha256`、片段文件字节、rendered.md 内联块**四向一致 15/15**；4 张 supportOnly（q1-styles、q1-targets、q2-full-top3、q2-extended）未出现在正文内联块，其 md/csv 与 supportOnlySets 的 fullData（EXP-0080/solver_certificates.jsonl、transfers.csv、transfer_constraints.csv、qp_cert_audit.json、zspace_centrescale.csv）全部存在且可读。
注：INDEX.selfCheck 内嵌的 ledger sha（rev 4615）与 manifest sha（0b65d24a）是生成时快照，现已前进（rev 4658 / db5980ed），属正常快照漂移，verify 仍 19/19。

## 3. 证据面（台账）

- claims：active **8** = CLAIM-0041/0047/0052/0053/0054/0055/0056/0059；retracted 11（含 0012/0014/0018/0019/0021/0022）。
- paper.md 只引 claim **CLAIM-0059**（1 处）；全篇 CLAIM id 仅此 1 个；6 条退休 claim **0 命中**。
- figures：FIG-0032..0040 active，9/9 sha 匹配；paper.md 有 `{{figure:FIG-0032..0040}}` 各 1 处，无其他 FIG。
- 数字可追溯抽查：rendered.md 的 0.35929156588219174 / 0.39817732837288883 / 0.350504156920024 / 0.3918800487369867 / 0.2091111111111111 / 0.8840256215416039 与台账 `EXP-0073:mae` / `EXP-0074:mae` / `EXP-0073:mae_all50` / `EXP-0073:mae_all50_median` / `EXP-0075:topk-jaccard` / `EXP-0079:energy-distance` 逐位相同。
- selection：Q1 provisional、Q3 provisional、Q2 validated（selectionStatus 实测）。
- 结构限制（已披露，不可修）：Q1 split-integrity / holdout-metrics 结构性无法执行；Q3 生成+迁移双对象、原生 optimization-feasibility/objective 未通过；QC-0033（EXP-0017/0018/0026/0035/0036 无 feature manifest，历史结构）；REQ-0004/0005/0007 = insufficient_data；无 registered split 的原生检查不可满足。上述在 paper.md §9.3 / 附录 B.3 / 附录 C 与首页 DRAFT banner 均有对应表述（grep：草稿选择 8、划分完整性 7、原生优化 8、数据不足 3、未冻结 1）。
- 交付边界事实：`paperArtifacts = []`；`frozen` = 2026-10-24 / revision 2731 / configVersion 1 / claimIds 为 6 条现已 retracted 的 claim / selectedModels 为 MODEL-0004/0012/0013（现已 0048/0050/0053）；`stage.current = intake`；`delivery.contest = null`（无官方页数/格式硬性要求，故 30 页不构成"页数不达标"）。

## 4. 版式缺陷根因（已定位到上游对象）

`src/build_paper.py` `transform()` 以 **0-based** `cap_idx` 写入 `consumed`，而 `transform_inline_lines()` 用 **1-based** `idx` 判断 `idx in consumed`，差一：
- 该删的「`**表 <id>　<title>**`」题注行没删 → 15/15 表在 PDF 中同时出现粗体散文标题与编号题注（重复题注）；
- 被误删的是题注行**上方**那一行（多数为分隔空行）→ 13/15 的粗体标题与上一段正文粘连（pandoc.md 实测 13/15 `prev_blank=False`）；
- 粗体标题是普通段落可断页、真表在 minipage/longtable 内不可断 → 5/15 表的标题与表体被分页切开（PDF 8→9、10→11、11→12、20→21、21→22）。

## 5. 证据文件

- `.rework/reviews/01_pdf_layout.py` / `01_pdf_layout.json`：页数、逐页坐标、页眉页脚、页码序列、内嵌图像数
- `.rework/reviews/02_pdf_captions.py` / `02_pdf_captions.json`：图/表编号、页脚居中、首页 DRAFT、匿名性
- `.rework/reviews/03_ledger.py` / `03_ledger.json`：台账只读抽取（config/claims/figures/renders/quality/REQ）
- `.rework/reviews/04_tables.py` / `04_tables.json`：19 表 / 15 内联 / 4 supportOnly 四向 sha
- `.rework/reviews/pages/p*.pdf|png`：抽单页 + sips 光栅化目检（p01/02/04/07/08/10/20/21/24/26/29/30）
