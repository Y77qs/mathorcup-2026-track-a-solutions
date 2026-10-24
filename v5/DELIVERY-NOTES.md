# DELIVERY-NOTES.md — 本轮交付的完成度与边界（2.8.10 第二阶段恢复后）

项目：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3`
插件：`dsh-vibe-math` **2.8.10**（`buildId=2.8.10+cefef8a`），预设 Vibe Math Modeling
台账：`state/ledger.json`（内容 revision 约 2748；`revision` 会持续被宿主 usage 事件增加，比较内容与 sha，不比较 revision）
最终交付：`delivery/20261024-223751/` + `delivery/20261024-223751.tar.gz`（FINAL，非 DRAFT）
历史保留：`delivery/20261024-DRAFT/` 与 `20261024-DRAFT.tar.gz`（final=false，未改写）

> 本文替代旧的 DRAFT 版说明。旧版描述的两个阻塞（`figure:FIG-0025`、`figure:FIG-0027`、`quality:critical-findings`）已由 2.8.10 的公开动作关闭，关闭方式与证据见 §3。

## 1 最终判定（来自最终 `modeling_deliver check`，连续 3 次一致）

| 判定 | 值 |
|---|---|
| `final` | **true** |
| `draft` | **false** |
| `engineeringComplete` | **true**（51/51 工程检查通过） |
| `qualityPassed` | **true**（27 passed / 5 not_applicable / 0 failed / 0 stale） |
| `checkpointsPassed` | **true** |
| `blocking` | **[]** |
| `submissionReady` | true（receipt 字段；交付仍由人类手动提交） |

工程检查合计 78 passed / 0 failed / 5 skipped（run-control 5 项不适用，记录为 limitation 而非 pass）。

## 2 关键产物与哈希

| 文件 | sha256 | 说明 |
|---|---|---|
| `report/paper.md` | `58d9a7786704d4153f832291776af2567f54331845cf33dedd23c681310c68f8` | 185 个占位符；F4 重写后正文不再复述数值 |
| `report/rendered.md` | `7a6c9a89b14050641909fbbded3694f7926ed9e2428c1d615fe2641cb678993f` | RENDER-0009，185/185 占位符解析，0 stale ref |
| `report/rendered.pandoc.md` | `8aa09abcd9066ee6088191e5ec4dfd1a596c24afa13f000d43926857edddfc68` | pandoc 输入（U+2208=0） |
| `report/paper.tex` | `8fa4849d6152fe86e060bd13c7ad98bcabaf547870c4403f8f809ac8d4580298` | ART-0003，绑 RENDER-0009 |
| `report/paper.pdf` | `3a8e6fe3f458ce5c0c868920b6b7670e424a7da23c0d4d8e7f0bca44275672d5` | ART-0004，绑 RENDER-0009，18 页 / 14 图 |
| `delivery/20261024-223751.tar.gz` | `21c9ec1826ce6dfc909de36eec015764c27d44321ce85155ef6c3664d11907b2` | 7,328,123 B；197 个交付文件 + SHA256SUMS |

- 冻结：`2026-10-24T14:36:58.240Z`（revision 2731），只含 6 条活跃 claim 与 **29 张活跃图**（FIG-0025/0027 不在冻结集合）。
- `rendered.md`/`paper.tex` 可在 `SOURCE_DATE_EPOCH=1700000000` 下逐字节复现；PDF 受 xdvipdfmx 影响字节不可复现，但最终 PDF 与独立复审的预览 PDF **18/18 页 2× 光栅像素一致、文本层一致**（见 `.rework/evidence/phase2-audit/final/compare_reviewed_vs_final.json`）。

## 3 旧阻塞如何关闭（2.8.10 公开接口，无手改台账）

1. **图版本迁移**：`modeling_deliver figure-retire` 把 FIG-0025→FIG-0030、FIG-0027→FIG-0031 标记 `superseded`（保留 id/path/sha256/createdAt/statusHistory，替代记录得到 `supersedes[]`）；`figure-archive` 把旧字节归档到 `figures/archive/FIG-0025-q3_defect_exceedance.png`（`57e3e864…`）与 `figures/archive/FIG-0027-q3_pareto.png`（`299df07e…`），归档字节与登记值逐字节相等，旧路径进 `pathHistory`。
2. **delivery review 版本绑定**：2.8.10 的 `deliveryScopeVersion()` 让 delivery review 绑定真实内容版本。独立复审 **REV-0039** 的 `binds={"kind":"delivery","version":"97e4982b…"}`，在 freeze/render/artifact/package 之后仍 `stale=false`。
3. **退休对象审查**：已 superseded 的 claim/figure 的旧 stale review 进入 `retiredStale` 历史，不再作为当前阻断；活跃对象未解决 critical 与 stale 最新 review 仍严格阻断（QC-0020 最终 passed）。
4. `deliver check` 中 FIG-0025/FIG-0027 以 **SUPERSEDED 历史行显式通过**（不再字节核验），FIG-0030/0031 作为 ACTIVE 图严格核验。

## 4 REV-0038 七条逐项复验（独立上下文 REV-0039，证据在 `.rework/evidence/phase2-review/`）

| 编号 | 结论 | 关键实测 |
|---|---|---|
| F1 §8 超宽表/裁切 | 已修复 | §8 为 1–9 条目列表；p15 全精度值 charbox x1=399.31/521.77/172.66 pt ≤ 555.31；无页面墨迹触页边 |
| F2 越界行 | 已修复 | 18 页最大墨迹 556.00 pt（p3，+0.69 pt < 3 pt 容忍）；§4.4 原 +32.19 pt 行现为 +0.18 pt；无裁切 |
| F3 Figure 13 ∈ 缺字形 | 已修复 | tex U+2208=0、pandoc 源=0、`$\in$`×2；p14 图注 2 个 ∈ 为正常数学字形（4×/8× 目检） |
| F4 §6.5 与 CLAIM-0022 重复数字 | 已修复（先独立确认残余，后返修） | 重写 §6.5 结果段后，6 个全精度值在 `paper.md` 正文计数为 0；数值只在 CLAIM-0022、摘要、§6.6、§8、§9 由占位符渲染 |
| F5 手写台账数字 | 已修复 | 88 个渲染值（48 个 ≥7 位小数）在剔除占位符后的 paper.md 中逐字命中 0；`1.0`/`18.18`/`delta = 0`/`也也` 计数 0；D 类常数已加登记来源指针 |
| F6 REPRODUCE 漂移 | 已修复 | §2.6 v2/v2/v3/v4 与台账一致；§2.11 六条 == 当前 active claim 集合 |
| F7 active claim 验证链接 | 已修复 | 见 §5 |

## 5 活跃 claim 与验证链接

| claim | 问题 | validationIds | 适用性 |
|---|---|---|---|
| CLAIM-0018 | Q1 | VAL-0032/0033/0034/0035/0036 | 划分完整性/泄漏/留出指标/基线比较/独立复跑 |
| CLAIM-0014 | Q1 负结果 | （空，证据为 EXP-0035/0036 metric＋FIG-0029） | 消融负结果，非独立复跑结论 |
| CLAIM-0019 | Q2 | VAL-0037/0038/0039 | leakage / topk-jaccard 原生复算 / 独立复跑 |
| CLAIM-0021 | Q3 生成 | VAL-0040/0041/0042/0043 | leakage / constraint-satisfaction 复算 / simulation-seeds / 独立复跑 |
| CLAIM-0022 | Q3 迁移 | VAL-0040/0041/0043 | **VAL-0043 的 52 项 comparisons 逐项含 transfer-* 全部数值且 delta=0**；VAL-0042 只测 seed 下的 constraint-satisfaction，不适用于迁移数值，故不链接 |
| CLAIM-0012 | 稳健性 | （空，证据为 EXP-0019/0022 + ROB-0001..0003 重算） | 稳健性判定，非独立复跑结论 |

全部 VAL-0032..0043 `result.passed=true`。`claims:evidence` 检查：6 条活跃结论的证据引用全部可解析。

## 6 PDF 交付验收（最终 PDF 实测，非打包后补测）

- 18 页、14 个内嵌图像、14 条 Figure 图注；14/14 图注在 PDF 文本层完整（规范化逐字命中），图文件 sha 与台账/渲染注释三方一致。
- 逐页 2× 光栅墨迹：最大 x = 556.00 pt（p3，版心右界 555.31 pt，+0.69 pt 属字形侧伸，小于 3 pt 容忍）；其余 555.00 pt；**无任何页面触页边/裁切**，垂直墨迹 56.5–765.0 pt（页高 792）。
- 图注缺字：14 条图注逐条 4× 条带目检 + 文本层规范化比对，中文/数学符号/标点完整；Figure 13 `∈` 为数学字形。
- 证据：`.rework/evidence/phase2-audit/`（audit JSON + 逐页几何 PNG + 对比 JSON）、`.rework/evidence/phase2-review/`（独立复审 313 行报告 + 35 张 PNG + JSON）。

## 7 已知限制与边界（如实披露）

1. **PDF 字节不可复现**：`xdvipdfmx` 生成的非确定性导致同一 `rendered.md` 两次构建 PDF 字节不同（本版最终 PDF `3a8e6fe3…`，复审预览 `2a1086af…`）。可复现的是：tex 逐字节（8fa4849d…）＋ PDF 18/18 页光栅像素与文本层一致。不要声称 PDF 字节级可复现。
2. **历史 stale review 保留**：39 条 review 中 20 条 stale，均为历史记录（REV-0010/0026/0038 等旧 delivery review 与已 supersede claim 的旧 review）。2.8.10 让它们作为历史/`historicalStale` 存在，不再阻断；未删除任何记录。
3. **同一对全精度值在 §6.6 与 §8 各出现一次**（同一组九项消融的两处汇总），均由占位符渲染；这是既有章节结构，不是手抄数字。若要求「每值只出现一次」需合并两节，属内容决策，本轮未改。
4. **交付包含 `src/__pycache__/*.pyc`**（构建缓存，非证据文件；不影响任何检查与哈希校验）。
5. `delivery.contest: null`：未声明竞赛平台要求，按规则记 skip，未编造官方规则；**未提交到任何竞赛平台**，提交是人类的动作。
6. 原始附件按 sha256 命名，9 个 raw 导入文件未随包（README_REPRODUCE 给出 sha，可重新导入）；实验目录只打包 metrics/predictions/result + 已登记图，其余输出留在项目内（见 `package-warnings.json`）。

## 8 未做（按红线）

- 未重新 init/plan；未重跑任何建模实验（experiments 36 条与基线快照逐条一致，status/exitCode 无变化）。
- 未新增 SPLIT-0002 曝光（holdoutExposures 仍 3 条，与快照一致）。
- 未降低任何门禁；未删除失败历史（EXP-0012、VAL-0011、VAL-0020、EXP-0027、EXP-0028/0032 保留）。
- 未手改 `state/ledger.json` 或冻结记录（全部经六个公开工具）。
- 未把 DRAFT 当 FINAL；DRAFT 保留为 `final=false`。
