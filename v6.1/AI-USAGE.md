# AI 使用说明（AI-USAGE.md）

项目：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`（`beer-2026-a-v3`）
适用交付：**DRAFT**（`final=false`；见 `DELIVERY-NOTES.md` §1）

## 1 AI 参与范围

| 环节 | 参与方式 | 人类角色 |
|---|---|---|
| 数据导入 / 清洗 / 划分 | AI 通过 `modeling_data` 执行，输入输出 SHA256 入台账 | 人类提供附件与项目目录 |
| 实验代码与运行 | AI 编写 `src/*.py` 并通过 `modeling_experiment` 真实运行（命令、退出码、日志、产物入台账） | 人类决定是否采纳、是否继续 |
| 验证与稳健性 | AI 登记验证计划/稳健性计划并执行；独立复跑由工具记录 | 人类决定是否冻结/提交 |
| 论文源与图表 | AI 写 `report/paper.md`（只写占位符与表块）、`src/paper_tables.py`、`src/make_confirmatory_figures.py`、`src/build_paper.py` | 人类审阅交付说明 |
| 独立复审 | 由**独立上下文（非根）代理**写入 REV 记录；根代理不代签 | 人类可要求重审 |
| 交付检查与打包 | 由 `modeling_*` 工具执行并留回执 | 人类决定是否提交；**本代理未提交** |

## 2 数字与证据的可追溯性

- 论文正文不含手抄指标：只写 `{{metric:EXP-xxxx:key}}`、`{{claim:CLAIM-xxxx}}`、`{{figure:FIG-xxxx}}`
  与由 `src/paper_tables.py` 生成的表格块；数字由 `modeling_deliver render` 从 `state/ledger.json` 解析
  （本交付 RENDER-0016 解析 88 个占位符、0 stale、0 warning）。
- 每个实验记录含：脚本、参数、seed、输入/输出 SHA256、stdout/stderr、退出码与产物。
- 每张表在 `report/tables/INDEX.json` 有输入路径+SHA、输出 SHA、表→实验映射；每张图在台账登记
  文件 SHA、来源实验、生成脚本 SHA。
- 一致性由只读脚本复核：`src/paper_tables.py --verify`（19/19）、`.rework/check_paper_consistency.py`
  （0 violations）、`src/build_paper.py --check`（30 PASS）、`.rework/pdf_audit.py`（页数/页码/页眉/图号/表号）。

## 3 已披露的 AI 相关限制

1. **全精度浮点**：正文按台账原值呈现（如 17 位小数），可逐位追溯但可读性差；未做展示层舍入，避免与台账产生差异。
2. **图内英文标注偏小**：图 1/2/9 在低分辨率下偏小（原始 PNG 可读）。
3. **内部表 id 交叉指代**：正文出现“表 q3-quality”这类内部 id（编号题注不含 id），映射见 `INDEX.json`。
4. **审查非形式化证明**：独立复审覆盖结构、SHA、页数、题注、覆盖与限制披露；它不等于数学证明，也不等于同行评审。
5. **未使用外部数据或外部模型输出作为证据**：参考文献 [1]–[4] 仅作背景引用。

## 4 明确的边界

- 本代理**不把 DRAFT 写成 FINAL**，不绕过交付门禁，不手改台账 `frozen`，不删除历史记录。
- 本代理**不自动提交竞赛平台**：`contest.yaml` 的 `delivery.contest` 为 `null`，提交由人工完成。
- 不输出任何凭据、密钥或 token。
- 仅向本项目目录写入；只读来源目录 `my-new-contest-v3` 未写入任何文件。

## 2026-10-27 v6.1 恢复轮（补充记录，不覆盖上文）

- 恢复：宿主在 `DeepSeek Messages stream idle timeout` 后按公开 `quality/run-control control:recover` 建立 **RUN-0004**；
  RUN-0003 保持 stopped/unknown-usage，失败请求 `ab5ac473-…:1:67` 仍未结算，1,304,576 token 上界由新 run 继承并在
  `runcontrol-budget` 中如实记为 unknown/needs_review。没有把未知用量当成 0，也没有自动重试。
- 已回收而非重训：EXP-0125…0130 用公开 `modeling_experiment status` 从磁盘结果入账（EXPs 前后均为 130）。
  之后按预登记顺序补跑的是参考/补充种子块 EXP-0131/0132/0133（同一协议，新增证据，不覆盖旧结果）。
- 图件：`src/make_confirmatory_figures.py` 由子代理改到本轮实验并输出 `figures/confirmatory_v2/`，
  10 张 PNG 两次运行字节一致；主控用 `modeling_deliver figure` 登记 FIG-0041…FIG-0050，旧图退休/归档。
- 论文：`report/paper.md` 由子代理按 v6 说明重写并两轮压缩（正文 30 页、整份 38 页），主控修 2 处事实错误
  （Q2 分母、131/198 贴边）与 1 处交叉引用笔误（图 9）；所有数字仍由 `{{metric:…}}`/`{{claim:…}}`/`{{figure:…}}`
  占位符经 `modeling_deliver render` 从台账解析，没有手抄进正文。
- 独立审查：由非根子代理（独立上下文）写入 REV-0087…REV-0097 并执行 historical findings 的 resolve；
  根代理不自宣独立、不代填 passed。
- 代码/产物：Q2/Q3 的修正脚本、明细产物与下游表/图脚本均由子代理在约定写域内完成，主控复核
  `paper_tables --verify 19/19`、`check_paper_consistency 0 violations`、`pdf_audit`、`r03_reproduce ok=true`。
- 未做：没有把任何 DRAFT 说成 FINAL；没有手改 `frozen`/`qualityPassed`；没有删除任何历史失败/queued/stale；
  没有向 v3 项目写入；没有自动提交竞赛平台（`delivery.contest = null` → 提交记为 skip，由人完成）。
