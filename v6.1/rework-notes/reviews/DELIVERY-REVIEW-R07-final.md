# 第三轮最终确认复审（REV-0086）：正式 DRAFT 交付实测

对象：`report/paper.md` 95fd30f0… → RENDER-0016 → `report/rendered.md` c5cf631d… → `report/paper.tex` e874741b… (ART-0007) / `report/paper.pdf` 952b73e3… (ART-0008)。
只读；未调用 freeze/render/artifact/check/package/quality-run；未改任何文件。

## 0. 冻结状态（如实）
- `modeling_project freeze` 未成功（Lead 报告 `VMU_PACK_MODELING_CONTEST_GATE_STAGE_SKIPPED`；我未自行调用 freeze）。
- 台账 `frozen` 仍为 **2026-10-24T14:36:58Z / revision 2731 / configVersion=1**，claimIds = CLAIM-0012/0014/0018/0019/0021/0022（**全部 retracted**），figureIds 29 张（**全部 retired**），selectedModels = MODEL-0004/0012/0013；`stage.current = intake`。
- RENDER-0016 的 `freeze` 字段 = 上述 legacy 身份 → **不是"冻结后的正式 render"**。
- 结论：交付身份**未冻结**；论文 B.3(2) 未声称已冻结（把状态指向 DELIVERY-NOTES）。

## 1. sha 链（全部实测一致）
| 对象 | sha256 | 绑定 |
|---|---|---|
| paper.md | 95fd30f0…3897416 | RENDER-0016.inputSha256 |
| rendered.md | c5cf631d…d6e2dd6245 | RENDER-0016.outputPath.sha256（=磁盘） |
| paper.tex | e874741b…fef842591 | ART-0007 / RENDER-0016 |
| paper.pdf | 952b73e3…1076e73e（2,514,164 B） | ART-0008 / RENDER-0016 |
| builder | 40b0022f… | BUILD-INPUTS.builder |
| header / template | 0d35a964… / b1140b18… | BUILD-INPUTS.support |
| INDEX / manifest | 6a78f7ce… / db5980ed… | BUILD-INPUTS.inputs |

`report/BUILD-INPUTS.json`：source=c5cf631d…、preprocessed=1b9c23a6…、tex=e874741b…、pdf=952b73e3…，与磁盘逐项一致；`paper.tex` 内嵌 source-sha256=c5cf631d…、pandoc-input-sha256=1b9c23a6…、builder-sha256=40b0022f…。

## 2. PDF 实测（pypdf；不采信 log）
- **30 页** A4；PDF 1–3 无页码（1 标题+摘要+DRAFT、2–3 目录）；正文页码 **1（p4）→ 27（p30）** 连续。
- 页脚 y=36.9pt、x≈292–295（中心 297.6，偏差≤1.4pt）；**30/30 页页眉区 0 文字**；首页 DRAFT（5 次）；匿名。
- 图：9 张（p8×2、p10、p12、p16、**p20**、**p21**、p24、p26；与 Lead 报的 "p20×2" 不同，属 §7.3 改动后的重排，总数与图号不变），图号 1–9 连续；题注与台账 caption 9/9 逐字相同；文件 sha 9/9。
- 表：编号题注 1–15 连续（12 captionof + 3 longtable caption）；"表 23" 为跨行假阳性（"表/231 个化学…"）。
- 附录 B = B.1/B.2/B.3；tex `\textbf{表 `=0、`{{…}}`=0、PENDING=0、fancyhdr=0；log Overfull=0 / Underfull=0 / Missing character=0；越左界仅 4 处全角「（」悬挂。
- 旧句 grep（paper.md / rendered.md / tex / PDF）："论文与交付审查本轮未执行" 0、"图件尚未登记" 0、"未执行渲染" 0、"未运行交付检查" 0、"未打包" 0；新句"交付冻结被工具具名拒绝" 1（p26）。

## 3. 新披露实读
- p12 §5.2：新增「本轮实际重算并上图的是训练网络…；附件全样本相关矩阵（2.csv）已导入并登记 SHA，但其半正定投影阈值网络在本确认轮没有独立产物，因此本文不就该网络报告边数或分量数，也不得把它的统计量与训练网络混用。」→ 与我的独立测算一致（2.csv=645 边/52 分量=全 250 行 Spearman；训练网络=732/51）。
- p26 §7.3(5)：改为「交付门禁未通过…交付冻结被工具具名拒绝」。

## 4. 构建/表/证据
- `build_paper.py --check --source report/rendered.md …` = **30 PASS / 0 FAIL / 0 warn**（上轮默认源 74 FAKE_FIGURE 已消失）。
- `paper_tables.py --verify` = 19/19；内联块四向 sha 15/15；supportOnly 4 张未内联。
- active claims 8；paper 只引 CLAIM-0059；retired claims 0 命中；FIG 仅 0032–0040；REQ-0007=insufficient_data + FIG-0033；config v2 / in_sync。
- 目检：p12/p26/p27/p28/p29/p30（p29/p30 与 preview-E 像素逐字节相同）。

## 5. 本轮 findings（REV-0086）
| # | Sev | 内容 | 修哪个对象 |
|---|---|---|---|
| F1 | **critical** | DELIVERY-NOTES.md 仍是 v3 FINAL 说明（final=true、v3 路径、18 页/14 图旧 sha、冻结含 6 条 retracted claim/29 张 retired 图），而论文 B.3(2) 指向它 | DELIVERY-NOTES.md（文档级） |
| F2 | major | `delivery/` 仍有旧 FINAL 包 20261024-223751(+tar.gz) 与 20261024-DRAFT | 归档/标注 |
| F3 | major | REPRODUCE.md 项目路径写 my-new-contest-v3（2 处） | REPRODUCE.md |
| F4 | minor | RENDER-0016.freeze 携带 legacy 身份且无"未冻结"标记 | DELIVERY-NOTES 说明 |
| F5 | minor | REQ-0002 coverage note 未记录 2.csv 偏离（论文已披露） | DELIVERY-NOTES 说明 |

## 6. resolve 清单（本轮）
- REV-0083 **F1 resolved**（B.3(2) 现为真：RENDER-0016+ART-0007/0008；未声称已冻结）
- REV-0083 **F5 resolved**（规范路径已被 RENDER-0016/ART-0007/0008 覆盖，`--check` 30 PASS）
- REV-0085 **F1 resolved**（§5.2 已披露 2.csv 偏离，残余记为 REV-0086 F5）
- 保持开放：REV-0083 F2/F3/F4/F6/F7/F8（含已接受的披露型 minor 与下游项）、REV-0085 F2/F3、REV-0084 F1–F3（TGT-0003 已知限制）——均按 Lead 的 DELIVERY-NOTES 披露路线处理。

## 7. 建议顺序
1. 修 DELIVERY-NOTES（v6 DRAFT、final=false、RENDER-0016/ART-0007/0008、freeze 被拒、legacy frozen 仅历史、QC 状态、已披露 minor 清单含 F9/F10/TGT-0003/2.csv 偏离）。
2. 改 REPRODUCE.md 两行路径；归档 `delivery/` 旧包。
3. 我复核文档后 resolve REV-0086 F1–F5（不涉及论文 sha，不影响 RENDER-0016/ART-0007/0008 绑定）。
4. 再 quality-run（QC-0020 应转 passed）→ `deliver check` → DRAFT 包。

## 8. 证据
- `.rework/reviews/08_final_layout.py` / `08_final.json`
- `.rework/reviews/pagesF/p{12,26,27,28,29,30}.{pdf,png}`

## 9 文档层复核（F1–F5 resolve 依据，2026-10-27 追加）

| 文档 | 实测 | 结论 |
|---|---|---|
| DELIVERY-NOTES.md | 17,258 B，sha `b2e3d62a…4df508ffd89`；§1 final=false/draft=true + freeze 拒绝码原文；§1/§3/§7.10 legacy frozen；§2 sha 表；§7 披露 10 条；§9 CHECK-RESULT 空占位 | F1/F4/F5 通过 |
| REPRODUCE.md | 9,013 B，sha `bd08431f…ba1f7d2e3a`；v6 路径 2 处，v3 仅 2 处“只读来源”声明、0 条命令使用 v3 | F3 通过 |
| AI-USAGE.md | 3,179 B，sha `dde02d54…2dbb7edfe`；自称 FINAL/已冻结/已提交 = 0 | 一致 |
| delivery/archive/ | 20261024-223751.tar.gz = **7,328,123 B**；20261024-DRAFT.tar.gz = **7,234,683 B**，两目录均在；`delivery/` 顶层仅 archive/ | F2 通过 |

sha 表比对：`.rework/reviews/09_doc_sha_check.py` → 文档声明的 **23/23** (path, sha256) 与磁盘一致；BUILD-INPUTS 声明 `fd2804fa…` 一致；`rendered.refs.json` 条目 91 = 文中“91 refs”。

grep 结果：三份文档中 FINAL / 已冻结 / 已提交 / submissionReady 仅出现在**否定句**（“不是 FINAL”“FINAL 打包被禁止”“未把 DRAFT 写成 FINAL”“不声称已冻结”“不声称已提交”），自称项 = 0。

resolve：REV-0086 F1/F2/F3/F4/F5 全部 resolved（台账 revision 4734，REV-0086 open findings = 0）。
残余建议（不阻断）：REPRODUCE.md §2 建议注明 SPLIT-0002 holdout 曝光已 3/3（=maxHoldoutReuse），确认轮不再使用。
