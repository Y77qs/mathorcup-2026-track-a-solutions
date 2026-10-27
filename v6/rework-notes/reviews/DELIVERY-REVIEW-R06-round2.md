# 第二轮独立复审（REV-0083）：preview-E 实测记录

对象：`report/paper.md`(16cee72b…) + `.rework/previews/preview-E/` + 构建输入 + 台账 active 证据。
只读；未运行 render/artifact/check/package/freeze/quality-run/实验。

## 1. 绑定链（全部实测一致）

| 对象 | 实测 sha256 | 记录 |
|---|---|---|
| report/paper.md | 16cee72bb12e8b401006fb8a2bfb1ccc6a18cdc22ae6ee43fd9bfd9df5b94307 | = RENDER-0013.inputSha256 = BUILD-INPUTS.inputs.paper-source-draft |
| src/build_paper.py | 40b0022f1fb964abd7bc525619415017098691b52ab75181cc50aef0572b8fe3 | = BUILD-INPUTS.builder |
| preview-E/rendered.md | d0adc011dfb4d7fc7dfcf329f617c518634ce4489aa1d73038709e7364cb7688 | = RENDER-0013.sha256(outputPath) = tex 内嵌 source-sha256 |
| preview-E/preview.pandoc.md | 9bd0eea9c65d1b8a57cfd55c54704e1be838402201444aeb08ec57923e02083a | = tex 内嵌 pandoc-input-sha256 |
| preview-E/preview.tex | 142dbef47a625907b61ffd57ee920a76d288c5b74000744066764fb51743755f | = BUILD-INPUTS.outputs[0] |
| preview-E/preview.pdf | 8260415d62fbb1fa5bdbd88e09614c513c9dbfc58a250d1031874358f6a4971f | = BUILD-INPUTS.outputs[1] |
| src/build/header.tex | 0d35a964…（未变） | = BUILD-INPUTS.support[0] |
| src/build/template.tex | b1140b18…（未变） | = BUILD-INPUTS.support[1] |
| report/tables/INDEX.json | 6a78f7ce…（未变） | = BUILD-INPUTS.inputs[1] |

RENDER-0013 台账字段（第二轮更正：字段名是 outputPath/sha256，不是 output/outputSha256）：
input=report/paper.md、inputSha256=16cee72b…、outputPath=.rework/previews/preview-E/rendered.md、
sha256=d0adc011…、bytes=96227、refsPath=…/rendered.refs.json、refsSha256=1f676781…、
passes=1、staleRefs=[]、warnings=[]、allowStale=false、configVersion=2。

## 2. PDF 实测（pypdf；不采信 log）

- 页数 **30**，A4 595.28×841.9pt。
- 页码：PDF 1–3 无页码（1 标题+摘要+DRAFT；2–3 目录），正文 **1** 起于 PDF 第 4 页，至正文 **27**（PDF 30）连续。
- 页脚 y=36.9pt、x≈292.2–294.9（中心 297.6，偏差 ≤1.4pt）；**30/30 页页眉区无文字**。
- 首页 DRAFT 存在；无作者/单位/学校/邮箱。
- 图：内嵌图像 **9**（p8×2、p10、p12、p16、p20×2、p24、p26），图号 1–9 连续；9 条题注与台账 caption 归一化后 **9/9 逐字相同**；9 图文件 sha **9/9 匹配**。
- 表：编号题注 **1–15 连续**（12 `\captionof{table}` + 3 longtable `\caption{`）。
  - 「表 23」为跨行「表 / 231 个化学…」的假阳性，已排除。
- 附录 B：TOC 与正文均为 **B.1/B.2/B.3**；PDF 文本无「.1/.2/.3」式空号。
- `图件尚未登记`：paper.md / rendered.md / PDF **均 0**；`FIG-0001`：paper.md / rendered.md **均 0**。
- Overfull log 0 / Underfull 0 / Missing character 0；实测版心 L=62.36 / R=532.92，越左界仅 4 处全角「（」标点悬挂（x≈55.1–56.4），非越界；右侧无越界。

## 3. 修复点实测

| 项 | 上一轮 | 本轮 |
|---|---|---|
| tex `\textbf{表 ` | 12 | **0** |
| pandoc.md `**表 ` 行 | 15 | **0** |
| 编号表题注 | 15 | 15（唯一题注） |
| 孤儿表题（跨页） | 5 | **0**（p20 底=图 7；表 11/表 12 与表体同页页首） |
| 附录 B 编号 | .1/.2/.3 | **B.1/B.2/B.3** |
| B.3(1) 图件陈述 | 「图件尚未登记」 | 已登记并列出 FIG-0032–0040 |
| B.3(2)/附录C 尾注 | 「渲染/绑定/打包均未执行」 | 已改写为 DRAFT 交付 + 门禁未过 |

目检（pypdf 抽单页 + sips 110dpi）：p7 单条「表 1」题注；p8 图 1/2 正常、段末无粘连表题；p20 页底仅图 7 题注；p21 页首「表 11+表体」；p22 页首「表 12+表体」；p29 B.1–B.3 + 新 B.3 文案；p30 附录 C 尾注已改写。

## 4. 其余一致性

- `paper_tables.py --verify` = 19/19 complete, 0 problem。
- 15 张内联块 table-begin sha = INDEX = 片段字节 = rendered.md **15/15 四向一致**；4 张 supportOnly 未内联、md/csv 与 fullData 齐全。
- `build_paper.py --check --source preview-E/rendered.md --number-sections --wide-tables wrap --no-caption-ids` = 30 PASS / 0 FAIL / 0 warn。
- claim：active 8（0041/0047/0052/0053/0054/0055/0056/0059）；paper.md 仅 CLAIM-0059（1 处）；6 条 retired claim 0 命中。
- config：728811fc… = versions[1].rawSha256；acceptedVersion=2；protocol 215d0941…；needsReview=false。
- REQ-0007：coverage=insufficient_data，refs 已改指 active **FIG-0033**。
- 选择状态：Q1 provisional / Q2 validated / Q3 provisional。

## 5. 本轮新发现的 minor（REV-0083 F1–F8）

1. B.3(2)/附录C「正式渲染与产物绑定已执行」不准确：artifact 绑定仍是 ART-0003/0004→RENDER-0009/cfgV1；RENDER-0013 产物尚未绑定。
2. 附录 C 汇总表无编号/题注、未入 INDEX。
3. 正文/摘要以内部表 id 交叉引用（「表 q3-quality」实际是表 10），题注只有编号。
4. 目录「摘要」条目仍无页码（上一轮 F5 残留）。
5. report/paper.pdf|tex|rendered.md 仍是旧轮（绑 RENDER-0009/RENDER-0008，18 页）——更正上轮「未绑定」措辞。
6. F10（17 位浮点）未披露 → 建议写入 DELIVERY-NOTES。
7. F9（图内文字偏小）已在 B.3(1) 披露 → 确认披露到位，不返修。
8. 下游项：frozen 仍旧（cfgV1/retired claimIds）；QC-0020 文本仍旧（实为 quality-run 未刷新）；QC-0033/QC-0002 属结构限制。

## 6. 更正上一轮（REV-0082）

- **F8 撤回**：renders 记录字段是 `outputPath`/`sha256`（我上轮误查 `output`/`outputSha256`）。RENDER-0012 与 RENDER-0013 的输出自始绑定且与磁盘一致。
- REV-0082 **F4** 中「paperArtifacts=[]/未绑定」措辞错误：实有 ART-0001..0004，旧文件是绑到 RENDER-0009（cfgV1）。F4 的实质（规范路径是旧轮产物、默认 `--check` 74 FAKE_FIGURE）不变，仍未解决。

## 7. 证据文件

- `.rework/reviews/05_previewE_layout.py` / `05_previewE.json`
- `.rework/reviews/pagesE/p{07,08,20,21,29,30}.{pdf,png}`
- 本文件 `.rework/reviews/DELIVERY-REVIEW-R06-round2.md`
