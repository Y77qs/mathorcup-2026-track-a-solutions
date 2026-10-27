# DELIVERY-NOTES.md — v6 DRAFT 交付说明（不是 FINAL）

- 项目：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`（项目 id `beer-2026-a-v3`）
- 只读来源：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3`（**本项目未向其写入任何文件**）
- 台账：`state/ledger.json`；配置：`contest.yaml`（`acceptedVersion=2`、`state=in_sync`）
- 写定时间：2026-10-27（UTC 约 03:2x）；`delivery.contest = null` → 官方平台提交动作记为 **skip**，由人工完成，本代理**未自动提交**。

> **一句话判定**：论文与产物链（源 → render → tex/pdf → ART）是闭合且可追溯的；但**交付身份未冻结**、
> **质量门禁未通过**、`QC-0033` 仍 failed，因此本交付是 **DRAFT**：`final=false`、`draft=true`。
> 本文档中任何“已完成”都只指**实际执行并留下回执**的动作，不指计划。

## 1 判定与门禁（如实）

| 项 | 实际状态 | 依据 |
|---|---|---|
| 交付类型 | **DRAFT** | `QC-0033` failed + 多项 required 检查 `needs_review`（无注册 split 的权威测试真值）/结构性不可满足；`final` 不可能为 true |
| freeze | **被工具拒绝** | `modeling_project {action:"freeze"}` → `VMU_PACK_MODELING_CONTEST_GATE_STAGE_SKIPPED`："cannot freeze before validation: question Q1: required check split-integrity/leakage/holdout-metrics/baseline-compare/independent-rerun has not passed; … Q2 leakage/holdout-metrics/independent-rerun; … Q3 leakage/simulation-seeds/independent-rerun/optimization-feasibility/optimization-objective …" |
| 是否绕过门禁 | **否** | 未 `advance`、未手改 `frozen`、未把 required 检查改成 optional/not_applicable、未用 `allowStale` |
| 台账 `frozen` | 仍是 **2026-10-24T14:36:58Z / revision 2731 / configVersion=1** | 含 6 条**已 retracted** claim（CLAIM-0012/0014/0018/0019/0021/0022）、29 张**已 retired/superseded** 图、MODEL-0004/0012/0013 —— **不是本轮身份** |
| RENDER-0016 的 `freeze` 字段 | **legacy 继承值** | render 在工具允许的 DRAFT 路径上执行，其记录里的 `freeze` 是上面那个旧身份；**不表示本轮已冻结**，不得读成“冻结后的正式 render” |
| 正式构建 | 已执行（非预览路径） | `build_paper.py --build --pdf --outdir report --allow-report-output`；`[PASS]` tex/pdf；`Output written on paper.pdf (30 pages)` |
| 产物绑定 | 已执行 | ART-0007（tex）/ ART-0008（pdf），均 `renderId=RENDER-0016`、sha 与磁盘逐字节一致 |
| 交付检查 `check` | 在本文写定后执行 | 实际回执见 §9（不预设结果） |
| 打包 | 仅 DRAFT | 见 §10；普通（FINAL）打包被禁止 |

## 2 产物与 SHA（全部实测）

| 产物 | 路径 | sha256 / 说明 |
|---|---|---|
| 论文源 | `report/paper.md` | `95fd30f0f1908a2bb6575dbf47a2a260f5dec00e733c699b9369821503897416` |
| 正式 render 输出 | `report/rendered.md` | `c5cf631d327df4cedee02368fc480af5120e9dcd9937a6d4169197d6e2dd6245`（**RENDER-0016**） |
| render refs | `report/rendered.refs.json` | `41898f251f8ed70c3db473e2950460c83dd933f941d9b862fc15f63b12b8bade`（91 refs、0 stale、0 warning） |
| 正式 tex | `report/paper.tex` | `e874741b348e191c01bf19a3884cf59c412b528ced996059626d9cfeef842591`（**ART-0007**） |
| 正式 pdf | `report/paper.pdf` | `952b73e341d6411ae28bd658045af1a53edf22824763570801a8a0e01076e73e`（**ART-0008**，2,514,164 B，30 页） |
| 构建输入清单 | `report/BUILD-INPUTS.json` | `fd2804fa9d9a0590aa2c6ec7d776a430c1a3ef5041844bbead8570bfaf284edf` |
| 表格索引 | `report/tables/INDEX.json` | `6a78f7ce8d0da89451efbe2de925e453ceccf6412513f8ef313b0452e9309605`（`--verify` 19/19） |
| 证据清单 | `report/evidence_manifest.json` | `db5980ed5981189dd4d824371905dee56e66501b4df84adbb5e347e9ec13d561`（本批未重生成） |
| builder | `src/build_paper.py` | `40b0022f1fb964abd7bc525619415017098691b52ab75181cc50aef0572b8fe3`（本批修复 1 处 off-by-one） |
| header / template | `src/build/header.tex` / `src/build/template.tex` | `0d35a9640f355225d95df79ac4512c7b2eb670ed0c9bbda69bd9e5a634cd3926` / `b1140b188bdc5e1864c6a052a243f991d16fd0661db4078e5cfe69322ebfa042` |
| 表生成脚本 | `src/paper_tables.py` | `f8d881234db6a52e4d3929ab1bf7c25dd9a38d016c9421c83932e656f1fa6940` |
| 图生成脚本 | `src/make_confirmatory_figures.py` | `c44d706d7aeea3e03fce3bfe37d92b248c2def0cb3da43249d8be8e998e19a10` |
| 源一致性检查（只读） | `.rework/check_paper_consistency.py` | `538d8487fc03d45ea76b14ead8f3b6fd11a0fc38a505e3d2fbcd8899d081aa9e`（当前 0 violations） |
| PDF 结构审计（只读） | `.rework/pdf_audit.py` | `fb1eb50a9dc79c53ce579470c9c0b4745e1fda6d7ed93ffc3ed2bb33542fa977` |

9 张 active 图（台账 9/9 active，文件 sha 与登记逐字节一致）：

| FIG | 文件 | sha256 |
|---|---|---|
| FIG-0032 | `figures/confirmatory/Q1-per-target-skill.png` | `2557001da5d9510a8f8afbfd682d4149c2b276b294901892dbc45ee0c8cf5838` |
| FIG-0033 | `figures/confirmatory/Q1-model-comparison.png` | `a461da972ec8e999b9d643e945cf792f262d61c88aa85680fc67e7ba8119122e` |
| FIG-0034 | `figures/confirmatory/Q1-grade-distribution.png` | `e2cf95cdb0e4fa5d16a79db21f08f1abc8f8136346a2b02612285ea60daa27d4` |
| FIG-0035 | `figures/confirmatory/Q2-network.png` | `ad567a5eb75ba1b36012efc7d66b8d4e8e1667c348d2bf5cfa2f4f294410afc6` |
| FIG-0036 | `figures/confirmatory/Q2-stability.png` | `cec5621b88f02790868160137311c8375b26fef886c7738208d467faae976e99` |
| FIG-0037 | `figures/confirmatory/Q3-energy-comparison.png` | `0e5d64be11e8a391a61de27e52838e8134661332d114d83cb314b2445a523349` |
| FIG-0038 | `figures/confirmatory/Q3-per-style-energy.png` | `6ef2bac1b7b9b8867864f3fc8df85a3f24fdfc9f066e0488c4e2b57678959a6b` |
| FIG-0039 | `figures/confirmatory/Q3-transfer-shift.png` | `3c982d2394e3900ef7c91fd4f051d75ba8fd4e48123f9f548ae16efef9ba1e52` |
| FIG-0040 | `figures/confirmatory/ROB-summary.png` | `ab3461581ee902afde41bf6897316b67f8f9aedac12035919cdf6ec85f05be70` |

## 3 交付身份（当前值 vs 冻结值）

| 项 | 当前（实际） | 台账 `frozen`（旧） |
|---|---|---|
| 配置 | v2，raw `728811fc…c9e5c3733`，protocol `215d0941a803…`，`in_sync` | v1，protocol `23fec133…` |
| selection | Q1=MODEL-0048 `provisional`；Q2=MODEL-0050 `validated`；Q3=MODEL-0053 `provisional`（Q3 双对象，迁移侧 MODEL-0054） | MODEL-0004/0012/0013 `validated` |
| active claims | 8 条（CLAIM-0041/0047/0052/0053/0054/0055/0056/0059） | 6 条（全部 retracted） |
| active figures | 9 张（FIG-0032–FIG-0040） | 29 张（全部 retired/superseded） |

**结论**：`frozen` 与本轮交付**不一致**；这是 freeze 被拒的直接后果，已在论文 §7.3 与附录 B.3/C 如实写出（“交付冻结被工具具名拒绝”），本文件不声称已冻结。

## 4 版式与视觉验收

- 总页数 **30**（A4 595.28×841.89 pt）。PDF 第 1 页 = 标题 + 摘要 + 关键词 + DRAFT 横幅；第 2–3 页 = 目录（跨两页）；正文页码 **1（PDF p4）→ 27（PDF p30）** 连续，页脚居中（x≈292–295，中心 297.6，偏差 ≤1.4 pt）。
- **30/30 页页眉区无任何文字**；无 `fancyhdr`；匿名（无作者/单位/邮箱/致谢）；首页 DRAFT 横幅在位；`{{…}}`=0、`PENDING-FIGURE`=0、Overfull=0、Underfull=0、Missing character=0。
- 图 **1–9 连续**（内嵌图像 9 张；本版重排后位于 p8×2、p10、p12、p16、p20、p21、p24、p26），题注全中文且与台账 caption 9/9 逐字相同；表 **1–15 连续**（12 `captionof` + 3 `longtable`）；附录 A/B/C 与 B.1/B.2/B.3 编号正确。
- **逐页视觉验收：30/30**。方法：`pypdf` 拆单页 → `sips` 光栅化（1050 px 宽）→ 逐页目检（中文、数学符号、图表题注、页码、DRAFT、旋转/裁切/空白）＋ 逐页墨迹包围盒（左 10.4% / 右 10.4% / 上 ≈8.1% / 下 4.2%，无页面触边、无空白页）。证据：`.rework/acceptance/final2/`（`p01..p30.pdf/png`）与 `report/pdf-audit.json`。
- **视觉验收的分辨率限制**：目检为 1050 px 宽的光栅图，小于 6 pt 的字形细节以 PDF 文本层抽取核对（`report/text/page-*.txt`）而不是靠光栅目视。

## 5 质量与验证状态（写定时）

写定时最近一次 `quality-run`（revision 4716）实际返回：**45 项 = 32 passed / 1 failed / 11 needs_review / 1 stale**。最终一次（含 REV-0084/0085/0086 刷新后）的回执见 §9。

| 项 | 状态 | 说明 |
|---|---|---|
| **QC-0020**（critical-findings） | 退休 claim 引用原因**已解除**；写定时仍 stale | 实测 `paper.md` 对 6 条退休 claim **0 命中**、只引 CLAIM-0059；该检查的失败原因已从“论文引用退休 claim”变为“`targetContract TGT-0003` 与 `requirements-coverage` 的最近 review 过期”；随后由 REV-0084（TGT-0003）与 REV-0085（coverage）刷新，最终状态见 §9 |
| **QC-0033**（analysis-evidence） | **failed，保持 failed** | EXP-0017/0018/0026/0035/0036 缺 input feature manifest，属历史/插件结构，**未 retrofit**、不改写为通过 |
| Q1 selection | `provisional` | `split-integrity`/`holdout-metrics` 结构性不可满足（train-only 3×3×3 嵌套 CV、无留出集、EXP-0073 未登记 splitId） |
| Q3 selection | `provisional` | 生成/迁移双对象无法用单一 `selectedModelId` 表示；原生 `optimization-feasibility`/`optimization-objective` 未通过、不声称 |
| Q2 selection | `validated` | VAL-0056 leakage + VAL-0057 independent-rerun 通过（同源对照，不是外部验证） |
| REQ-0004 | `insufficient_data` | 确认轮无 mean/median 双阈值情景、无 λ×η Pareto 前沿的当前证据 |
| REQ-0005 | `insufficient_data` | 论文门禁未通过（`final=false`）；“三格式同版”只到 DRAFT 级 |
| REQ-0007 | `insufficient_data` | 图注—结论“逐项一致性”仍属人工判断；refs 已由已 superseded 的 FIG-0001 改指 active **FIG-0033** |
| 无注册 split 的 `metric-recompute` | `needs_review`（不可满足） | 确认轮 EXP-0073/0074/0075/0079/0080/0089–0102 均无注册 split，故无权威测试真值；工具如实拒绝，不以预测文件自证 |
| `runControl` | RUN-0003 `running` | 未重复 `begin`、未 `stop`；预算软/硬上限为 `null` |

## 6 修改记录（本批实际改动）

| # | 对象 | 改动 | 触发 | 证据 |
|---|---|---|---|---|
| 1 | `src/build_paper.py` | 题注行下标 0-based→1-based（`consumed.add(cap_idx+1)`、`skip_lines` 同步 `+1`） | REV-0082 F1/F2：15/15 表题与编号题注重复、5 处标题与表体跨页分离 | preview-E：`\textbf{表 `=0（原 12）、15 个编号题注、p20 孤儿表题消失；30 页不变 |
| 2 | `report/paper.md` §2.4 | “附件相关矩阵…只在整体网络描述中使用”→“本轮只用于说明网络来源，未作为独立网络产物重算” | REV-0085 F1：2.csv 网络在确认轮无产物 | p5 实读 |
| 3 | `report/paper.md` §5.2 | 新增“本轮实际重算并上图的是训练网络…附件 2.csv 全样本矩阵未作为独立网络产物重算，因此不就该网络报告边数/分量数” | 同上 | p12 实读 |
| 4 | `report/paper.md` 附录 B.3(1) | 删“图件尚未登记…下一批替换”，改为“图 1–9 = FIG-0032–FIG-0040，9 个文件 SHA 与台账一致”，并披露图 1/2/9 图内文字偏小 | REV-0082 F3（自相矛盾） | p29 实读；`图件尚未登记` 全文 0 命中 |
| 5 | `report/paper.md` 附录 B.3(2) 与附录 C 尾注 | 改为“按 DRAFT 交付：正式渲染与产物绑定已执行，但交付检查未通过最终门禁…” | REV-0082 F11（时点性断言） | p29/p30 实读 |
| 6 | `report/paper.md` 附录 B 三个 H2 | 加 `B.1/B.2/B.3` + `{.unnumbered}` | REV-0082 F5：`.1/.2/.3` 空号 | p3 TOC 与 p29 正文均为 B.1–B.3 |
| 7 | `report/paper.md` §7.3 第 5 条 | 删“论文与交付审查本轮未执行（未渲染/未运行交付检查/未打包）”，改为“交付门禁未通过…交付冻结被工具具名拒绝” | REV-0086 同类时点性断言（本批自查） | p26 实读；旧句在 paper/rendered/tex/PDF 全 0 |
| 8 | 台账 REQ-0007 coverage | fig ref `FIG-0001`（superseded）→ active `FIG-0033`，coverage 仍 `insufficient_data` | 退休引用 | REV-0085 复核 7/7 refs 全活 |
| 9 | `delivery/` | 旧包 `20261024-223751(.tar.gz)`、`20261024-DRAFT(.tar.gz)` 移入 `delivery/archive/`（保留、未删除） | REV-0086 F2 | 见 §10 |
| 10 | 新增只读脚本 | `.rework/pdf_audit.py`、`.rework/acceptance/`（逐页光栅与墨迹统计） | 视觉验收 | 见 §4 |
| 11 | 文档 | 本文件全量重写；`REPRODUCE.md` 全量重写（v6 路径/链路/SHA） | REV-0086 F1/F3 | 见 §2 |

中间预览与历史（不冒充最终）：preview-D（30 页，RENDER-0012 构建）、preview-E（30 页，RENDER-0013）、preview-F（30 页，RENDER-0014）、RENDER-0015 + ART-0005/0006（§7.3 修改前）——均保留为历史，**最终交付以 §2 的 RENDER-0016 + ART-0007/0008 为准**。

## 7 已披露的 minor 与已知限制（不返修，如实列出）

1. **图内文字偏小（F9）**：图 1、图 2、图 9 的英文标注在低分辨率/打印缩放下偏小；原始 PNG 可读，论文附录 B.3(1) 已自披露。
2. **全精度浮点（F10）**：摘要与正文按台账原值呈现（如 `0.35929156588219174`，17 位）。可逐位追溯，但可读性差；未做展示层格式化，避免与台账值产生舍入差异。
3. **附录 C 汇总表未编号**：该表为无题注的说明表（其余 15 张有编号），未进入 `INDEX.json`。
4. **正文用内部表 id 交叉指代**：如“表 q3-quality”实际是**表 10**。编号题注不含内部 id（构建参数 `--no-caption-ids`），映射关系记录在 `report/tables/INDEX.json`；若需逐处可点，应改为带 id 题注（会改变版式与页数，本批不做）。
5. **目录“摘要”条目无页码**：摘要位于不编页码的标题页（PDF p1），属版式设计结果。
6. **2.csv 网络偏离（REV-0085 F5）**：确认轮未把 2.csv 全样本矩阵重算为独立产物（645 边/52 分量仅由复审独立算出，无台账产物）；论文 §5.2 已披露，`REQ-0002` 仍为 `covered` 且其 coverage note **未**记录该偏离（为避免再改 requirementsVersion 使 coverage review 过期）。
7. **TGT-0003 三条 minor（REV-0084）**：`taskNature` 单值 `conditional_generation` 而对象含迁移；`claimScopes=[]` 且 CLAIM-0054/0055 的 `targetContractId=null`；契约记录 `stale=true`（config v1→v2，无 per-input snapshot，需一次 no-op revise 才能清）。
8. **REQ-0005/0007 的 blockedReason 含时点性表述**（“本批只做…”）：属 minor，未改。
9. **longtable 续表无“续表”标题**：表 7/8/12 跨页时第二页直接接表体（无重复题注），属当前版式。
10. **freeze legacy（F4）**：见 §1/§3；`frozen` 与 RENDER-0016 的 `freeze` 字段都是旧身份。

## 8 AI 使用说明

- 本交付的论文源、表格/图脚本、构建器、台账操作与检查脚本由 **AI 编码代理（DeepSeek Harness / vmu 建模工具链）** 生成与执行；人类提供赛题、项目目录与验收要求，并在每个检查点决定是否继续。
- **可追溯性**：论文中每个数字都来自 `{{metric:EXP-xxxx:key}}` 等占位符，由 `modeling_deliver render` 从 `state/ledger.json` 解析；实验记录含命令、退出码、stdout/stderr、输入/输出 SHA256；表格与图另有 `INDEX.json` / 台账登记的输入输出 SHA。
- **人类可复核的检查点**：`paper_tables.py --verify`（19/19）、`.rework/check_paper_consistency.py`（0 violations）、`build_paper.py --check`（30 PASS）、`.rework/pdf_audit.py`（页数/页码/页眉/图号/表号）、逐页光栅目检（30/30）、以及独立上下文复审（REV-0082…REV-0086，均由非根代理写入）。
- **未做/禁止**：未把 DRAFT 写成 FINAL；未绕过门禁；未手改台账 `frozen`；未删除历史（旧包归档、旧 render/ART/REVIEW 保留）；未向 SOURCE 写入；未输出任何凭据/密钥；未自动提交竞赛平台。
- 外部文献仅用于背景引用（[1]–[4]），数值与结论不依赖 LLM 记忆。

## 9 交付检查（`modeling_deliver check`）实际回执

在本文件写定后执行，实际结果（结构化：`engineeringComplete` / `qualityPassed` / `checkpointsPassed` / `final` / `draft` / `blocking`）见下方：

<!-- CHECK-RESULT -->
**执行**：`modeling_deliver {action:"check"}`（台账 revision 4782，`template=generic-zh`）。返回 `ok:false`（`final` 未通过，属预期）。

| 结构化字段 | 实际值 |
|---|---|
| `engineeringComplete` | **false**（engineering 62 项：59 passed / 3 failed / 0 skipped） |
| `qualityPassed` | **false**（quality 45 项：32 passed / 1 failed / 11 needs_review / 1 stale / 0 not_applicable） |
| `checkpointsPassed` | **false**（34 个检查点阻断，全部在 validation 阶段） |
| `final` | **false** |
| `draft` | **true** |
| `submissionReady` | **false** |
| `blocking` | 16 项：`selection:Q1`、`selection:Q3`、`checkpoints`、`quality:requirement-coverage`、`quality:analysis-evidence`、11 × `quality:metric-recompute`、`quality:runcontrol-budget` |
| `summary` | total 75 / passed 91（含历史图行）/ failed 16 / skipped 0 |
| `reviewScope` | reviewed 32 类检查；notReviewed 含 requirement-coverage、analysis-evidence(Q1)、11×metric-recompute、runcontrol-budget |
| `warnings` | `[]` |

**三条 engineering 失败的具体原因**（不是新缺陷，就是本 DRAFT 的事实）：
1. `selection:Q1` = `PROVISIONAL_SELECTION`：Q1 的 `split-integrity`/`holdout-metrics` 结构性不可满足。
2. `selection:Q3` = `PROVISIONAL_SELECTION`：Q3 生成/迁移双对象 + 原生优化检查未通过。
3. `checkpoints` = `CHECKPOINTS_UNMET`：validation 阶段 34 个 required 检查未通过（Q1/Q2/Q3 的 leakage/holdout-metrics/baseline-compare/independent-rerun/simulation-seeds/optimization-*，其中 Q3 leakage 为具名失败“实验未声明 feature 列表”）。

**通过的关键工程项（真实回执，摘录）**：
- `config:accepted` → “the file equals accepted version 2 (protocol sha256 215d0941a803)”
- `report:source` / `report:rendered` → “report/rendered.md matches render **RENDER-0016**”
- `report:render-binding` → “render RENDER-0016 is bound to the current config/freeze/selection/source”
- `report:rendered-placeholders` → 无占位符；`placeholders` → **88 placeholder(s) all resolve against the ledger**
- `figure:FIG-0032…0040` → 9/9 sha 通过；旧图 FIG-0001…0031 以 `SUPERSEDED`/`RETIRED` 历史行通过（**不做字节核验、不阻断**）
- `paperFormat:md|tex|pdf` → tex/pdf “produced and bound to render RENDER-0016 (artifact **ART-0007** / **ART-0008**)”
- `independent-rerun` → Q1 VAL-0055 / Q2 VAL-0057 / Q3 VAL-0060 通过
- `QC-0020`（critical-findings）→ **passed**（退休 claim 引用原因已消除；TGT-0003 与 requirements-coverage 的最新 review 已由 REV-0084/REV-0085 刷新）
- `frozen` → 通过，但记录的是 **legacy 身份**“frozen at 2026-10-24T14:36:58.240Z (6 claim(s), 29 figure(s))”——与 §1/§3 一致，**不代表本轮已冻结**
- `contest:config` → `NO_CONTEST_CONFIG`：“delivery.contest is null … no official rule is invented”

**据此的最终判定**：`final=false`、`draft=true` → 只能出 DRAFT 包（§10），不得当作最终提交版。

## 10 打包与提交

- 旧包（v3 历史，**不代表本项目**）：`delivery/archive/20261024-223751/`、`delivery/archive/20261024-223751.tar.gz`、`delivery/archive/20261024-DRAFT/`、`delivery/archive/20261024-DRAFT.tar.gz`（保留，未删除）。

### 10.1 本项 DRAFT 包（`modeling_deliver package draft:true` 真实回执）

| 项 | 值 |
|---|---|
| 调用 | `modeling_deliver {action:"package", projectDir:P, draft:true}` |
| 目录 | `delivery/20261027-111607-DRAFT/` |
| 归档 | `delivery/20261027-111607-DRAFT.tar.gz`（28,174,344 B）sha256 **`d84dcbe663c1ef880e2353b24851c387f612b1de7484698fb5451c98b9e59ba3`** |
| manifest（`delivery-status.json`） | `final=false`、`draft=true`、`engineeringComplete=false`、`qualityPassed=false`、`checkpointsPassed=false`、`submissionReady=null` |
| 文件数 | 504 个文件；`SHA256SUMS` 503 行，**独立复算 503/503 全部一致** |
| 论文产物 | 包内 `report/paper.md`=`95fd30f0…`、`report/rendered.md`=`c5cf631d…`、`report/paper.tex`=`e874741b…`、`report/paper.pdf`=`952b73e3…`（与 **ART-0007/ART-0008**、**RENDER-0016** 逐字节一致） |
| 附带的诊断文件 | `quality-blockers.json`（13 条 quality 阻断）、`ledger-summary.json`、`delivery-status.json`、`README_REPRODUCE.md`、`SHA256SUMS` |
| supportOnly 表 | 4 张表（q1-styles / q1-targets / q2-full-top3 / q2-extended）的 md+csv **已在包内** `report/tables/` |

**包内警告（工具原文，未手改）**：
1. 每个历史实验只打包 `metrics.json`/`predictions.csv`/`result.json` 与**已登记图**，其余输出（`outputs.json`、`samples*.csv`、`inputs/src/*` 等）未打包——它们仍在项目目录内，可复算；
2. 9 个原始导入附件未打包（`README_REPRODUCE.md` 按 sha256 列名，可据此重新导入）；
3. 包内包含历史修订目录 `report/revised-20261025/`（旧版论文与其 PDF）以及 `.DS_Store`、`src/__pycache__/*`——**这些是历史/缓存，不是本次 DRAFT 交付物**；插件包与其 `SHA256SUMS` **未被手工修改**。

### 10.2 DRAFT 支撑材料包（本项目另建，明确标识 DRAFT）

插件包只包含 supportOnly 表的汇总版，**不含** QP 证书全量与迁移逐行数据（见 10.1 警告 1）。因此另建：

| 项 | 值 |
|---|---|
| 目录 | `delivery/20261027-111607-DRAFT-SUPPORT/` |
| 归档 | `delivery/20261027-111607-DRAFT-SUPPORT.tar.gz`（3,314,980 B）sha256 **`b812eb1ab9a5f3512f5ad0d272f37cb45df2eb97b61f2e07a78dd57505e46fc8`** |
| 清单 | `SUPPORT-MANIFEST.json`（21 条：每条 set / path / bytes / sha256 + 来源与边界说明）＋ `SHA256SUMS`（22 文件，**独立复算 22/22 一致，合计 10,465,827 B**） |
| 内容 | 4 张 supportOnly 表的 md+csv；`experiments/EXP-0080/solver_certificates.jsonl`（198 份 QP 证书）；`outputs/q3/qp_cert_audit.json`；`experiments/EXP-0080/transfers.csv`（396 行）；`experiments/EXP-0080/transfer_constraints.csv`（15,048 行）；`outputs/q3/zspace_centrescale.csv`；以及**与本次 DRAFT 同版**的 `report/paper.md|rendered.md|paper.tex|paper.pdf`、`INDEX.json`、`evidence_manifest.json`、`REPRODUCE.md`、`AI-USAGE.md` |
| 为什么不放 `DELIVERY-NOTES.md` | 该文件描述本包自身，放入会形成“包内说明落后于包”的自指；权威版本在项目根目录，清单里已记其说明 |
| 同版校验 | 包内 `report/paper.tex` = `e874741b…`（ART-0007）、`report/paper.pdf` = `952b73e3…`（ART-0008）——与插件 DRAFT 包逐字节一致 |
| 边界 | 所有文件均为**逐字节复制**（未修改）；不替代插件 DRAFT 包；不表示 FINAL；不改插件包或其 `SHA256SUMS` |

### 10.3 提交

`delivery.contest = null`，未声明官方提交要求 → 记为 **skip**；本代理**未自动提交**，也未声称已提交。提交动作由人类完成。
