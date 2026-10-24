# 原工作区清单（2026-10-24 生成）

> 本文件是原工作区 `/Users/baozhashizitou/Documents/MATHORCUP` 的扫描清单，保留原始路径以便对照。
> 在本仓库中的对应位置：
>
> - `A/` → [`packages/01-A-mathorcup-2026-a/`](../packages/01-A-mathorcup-2026-a/)
> - `work/my-new-contest/` → [`packages/02-beer-2026-a/`](../packages/02-beer-2026-a/)
> - `work/beer-rerun-2.8.6/`、`work/my-new-contest-v2/`、`work/RERUN-GUIDE-2.8.6.md` → [`packages/03-rerun-2.8.6/`](../packages/03-rerun-2.8.6/)
>
> 清单中提到的部分大文件（`A/outputs/q1|q2|q3`、非最终交付压缩包、重跑项目 data 副本）未纳入本仓库，原因见根 README 第 5 节。

# 2026 年 MathorCup 大数据挑战赛 · 赛道 A 初赛 —— 论文与相关代码（按时间顺序）

> 扫描范围：`/Users/baozhashizitou/Documents/MATHORCUP`（工作区内全部同题产物）
> 排序依据：文件 mtime（Asia/Shanghai，即本机 `date` 时区）+ 各项目台账 `createdAt`
> 清单生成时间：2026-10-24 13:43 CST
> 题面文件：`A/problem/2026年MathorCup大数据挑战赛-赛道A初赛.pdf`（另有 md/txt 转写与 4 个项目的副本）

---

## 0. 一眼看全

工作区内共有 **4 个针对同一道题（2026 MathorCup 赛道 A 初赛：啤酒感官/化合物）的项目目录**，
其中 **2 个已经产出完整论文（md + tex + pdf）**，共 **7 个互不相同的 PDF 构型**（14 个 PDF 文件路径，含交付包内的构建副本）；
另外 2 个是依据《2.8.6 重跑指南》新开的重跑项目，**截至扫描时点还没有论文**。

| # | 项目目录 | projectId | 时间范围（CST） | 论文 | 代码 | 状态 |
|---|---|---|---|---|---|---|
| 1 | `A/` | `mathorcup-2026-a` | 10-23 21:04 → 22:27 | **有，47 页**（初版 44 页） | 39 个 py / 13,169 行 | 完整论文 + 3 个 DRAFT 包，`final=false` |
| 2 | `work/my-new-contest/` | `beer-2026-a` | 10-24 11:24 → 12:50 | **有，12 页**（5 个版本） | 20 个 py + 8 个取证脚本 | 完整论文 + 5 个 DRAFT 包，`final=false` |
| 3 | `work/beer-rerun-2.8.6/` | `beer-2026-a-r2` | 10-24 13:10 → 13:12 | **无** | 20 个 py（自项目 2 拷贝） | 只做到 Phase 0–2 准备审计（PASS） |
| 4 | `work/my-new-contest-v2/` | `beer-2026-a-v2` | 10-24 13:31 → 进行中 | **无** | 无（`src/` 为空） | 干净重跑，进行中（13:42 仍在写台账） |

> 说明：`work/vibe-mathematics-modeling/`（插件/框架仓库）、`work/competitions/mathorcup2026-c/`（赛道 C）、
> `work-quality/2021-mathorcup-e2e/`（2021 年题）、`work/trials/wordle/`（2023 MCM）均**不是**本赛题产物，未列入。

---

## 1. 总时间轴（按时间顺序）

| 时间（CST） | 阶段/事件 | 关键产物 |
|---|---|---|
| 10-23 21:04:49 | **阶段 I 开始**：`A/` 项目建台账 | `A/state/ledger.json` |
| 21:05–21:08 | 题面入库、环境探针、数据审计启动 | `A/problem/`、`src/probe_env.py`、`src/01_audit.py` |
| 21:08–21:37 | 数据核实 → 尺度识别 → 清洗 → 划分 → 建模表 → 问题一/二/三模型族 | `A/src/` 数据与模型族模块、`A/state/scripts/SCRIPT-0001..0037` |
| 21:38–21:57 | 基线、Q1 定稿、Q2 选择、Q3 评估、独立复算 | `A/src/08*`、`q1_final.py`、`q2_select.py`、`q3_eval.py`、`09_independent_rerun.py` |
| 21:59–22:01 | A 论文首次成稿并打第一个 DRAFT 包（**44 页**） | `A/delivery/2026-MathorCup-A-DRAFT-DRAFT.tar.gz`、`paper.pdf` |
| 22:07–22:11 | 排版脚本、图重绘、Q1 汇总 | `A/report/tex/typeset.py`、`src/q3_figs.py`、`src/q1_final_summary.py` |
| 22:19 | A 论文**重排/扩写为 47 页**（新增“结论边界”等节） | `A/report/paper.pdf`（47 页）、`A/delivery/final-draft-DRAFT/` |
| 22:20 | 最终交付快照（193 文件）+ STATUS 状态书 | `A/delivery/FINAL-DRAFT-2-DRAFT.tar.gz`、`A/delivery/STATUS.md` |
| 22:21–22:27 | 交付后复核：Q2 稳定性补跑、独立审查报告 | `A/src/q2_stability.py`、`A/outputs/review/validation_report.md` |
| 10-24 11:24–11:48 | **阶段 II 开始**：`work/my-new-contest/` 建目录、题面 md 转写、5 份取证报告 | `analysis/{sensory,ref,corr}/report.md`、`analysis/QA-五问答题口径与证据.md` |
| 11:56:26 | 项目 2 建台账（新项目 id，配置随后再改——这是后面 final 不可达的根因） | `work/my-new-contest/state/ledger.json` |
| 12:02–12:17 | 数据构建（Q1 mapped / Q2 raw / Q3）+ 建模脚本 + 出图 | `src/build_*.py`、`src/q*`、`figures/*.png`（9 张 PNG，7 张登记） |
| 12:22:55 | 项目 2 论文第一版（**12 页**）并打 DRAFT 包 | `delivery/20261024-122255-DRAFT.tar.gz` |
| 12:23:25 | 同名重打包（内容几乎相同） | `delivery/DRAFT-final-DRAFT.tar.gz` |
| 12:36:26 | **Round 1**：补 Q2/Q3 基线、审查记录后重排 | `delivery/round1-DRAFT.tar.gz` |
| 12:42:33 | **Round 2**：独立复跑（train-only 隔离）通过后重排 | `delivery/round2-DRAFT.tar.gz` |
| 12:43:43 | 项目 2 终稿（12 页，含两轮复审修正） | `work/my-new-contest/report/paper.pdf` |
| 12:48:55 | 项目 2 最终 DRAFT 包 + 交付说明 | `delivery/round2-final-DRAFT.tar.gz`、`DELIVERY-NOTES.md` |
| 13:01 | 失败复盘成文：2.8.6 重跑指南 | `work/RERUN-GUIDE-2.8.6.md`（47 KB） |
| 13:10:18 | **阶段 III**：2.8.6 重跑项目建台账（`beer-2026-a-r2`） | `work/beer-rerun-2.8.6/state/ledger.json` |
| 13:10–13:12 | 只做 prep 审计（init/plan/data/contracts），0 实验、0 论文 | `PREP-AUDIT.md`、`prep-audit.json`、`src/`（20 py 拷贝） |
| 13:31:37 | **阶段 IV**：干净重跑项目 v2 建台账并预检（目录 13:31:29 创建） | `work/my-new-contest-v2/PREFLIGHT.json`、`START-PROMPT.md` |
| 13:32–13:42 | v2 录入题面/数据，正在建计划（扫描时仍在写） | `work/my-new-contest-v2/state/ledger.json`（13:42 仍在更新） |

---

## 2. 论文清单（按时间顺序）

### 2.1 阶段 I：`A/`（第一套完整解，47 页长报告式）

论文题目：《**数据缺失与尺度失配条件下啤酒感官评分、关键化合物识别与风格条件生成的建模研究**》

| # | 时间 | 论文 PDF（含所在包） | 页数 | 大小 | 说明 |
|---|---|---|---|---|---|
| 1 | 10-23 22:01:51 | `A/delivery/2026-MathorCup-A-DRAFT-DRAFT/report/paper.pdf` | 44 | 1,309,618 B | 初版；同一文件夹内有 `paper.md`(97 KB) / `paper.tex`(142 KB) / `rendered.md` |
| 2 | 10-23 22:19:32 | `A/report/paper.pdf`（项目报告主文件） | 47 | 1,341,927 B | 定稿重排（`report/build.log` 记录 47 页、overfull hbox 0） |
| 3 | 10-23 22:19:51 | `A/delivery/final-draft-DRAFT/report/paper.pdf` | 47 | 1,341,927 B | 与 #2 **字节相同**（sha `d46d838cec…`），只是打进了交付包 |
| 4 | 10-23 22:20:05 | `A/delivery/FINAL-DRAFT-2-DRAFT/report/paper.pdf` | 47 | 1,341,927 B | **最终交付快照**（193 文件；压缩包 sha256 `2317a21b…`），论文字节与 #2/#3 相同 |

对应压缩包（可直接解压交付）：

| 时间 | 压缩包 | 大小 |
|---|---|---|
| 10-23 22:01 | `A/delivery/2026-MathorCup-A-DRAFT-DRAFT.tar.gz` | 7,826,459 B |
| 10-23 22:19 | `A/delivery/final-draft-DRAFT.tar.gz` | 7,925,282 B |
| 10-23 22:20 | `A/delivery/FINAL-DRAFT-2-DRAFT.tar.gz` | 7,924,895 B（sha256 `2317a21bf4321778ca7e97997914387e9bd170b4c02418bdfb3b2a5c60496dfb`） |

> 另有 3 个**未通过的 final 打包尝试**（只剩 `package-warnings.json`，说明当时 `final=false` 被打包器拒绝）：
> `A/delivery/2026-MathorCup-A-DRAFT/`(22:01)、`A/delivery/final-draft/`(22:19)、`A/delivery/FINAL-DRAFT-2/`(22:20)。

### 2.2 阶段 II：`work/my-new-contest/`（第二套完整解，12 页竞赛投稿式）

论文题目：《**基于化合物谱的啤酒风味预测、归因与风格条件生成**》

| # | 时间 | 论文 PDF（含所在包） | 页数 | 大小 | 说明 |
|---|---|---|---|---|---|
| 5 | 10-24 12:22:55 | `work/my-new-contest/delivery/20261024-122255-DRAFT/report/paper.pdf` | 12 | 567,382 B | 第一版（`paper.md` 18.2 KB） |
| 6 | 10-24 12:23:25 | `work/my-new-contest/delivery/DRAFT-final-DRAFT/report/paper.pdf` | 12 | 566,677 B | 第一版改名重打包 |
| 7 | 10-24 12:36:26 | `work/my-new-contest/delivery/round1-DRAFT/report/paper.pdf` | 12 | 571,852 B | Round 1：补 Q2/Q3 简单基线、审查记录 |
| 8 | 10-24 12:42:33 | `work/my-new-contest/delivery/round2-DRAFT/report/paper.pdf` | 12 | 572,700 B | Round 2：独立复跑（train-only 隔离）通过后 |
| 9 | 10-24 12:43:43 | `work/my-new-contest/report/paper.pdf`（项目报告主文件） | 12 | 574,481 B | **终稿**（`build_report.json`：pandoc + 两遍 xelatex，9 图全可加载） |
| 10 | 10-24 12:48:55 | `work/my-new-contest/delivery/round2-final-DRAFT/report/paper.pdf` | 12 | 574,481 B | 与 #9 **字节相同**（sha `c154d55945…`），最终 DRAFT 包 |

对应压缩包：

| 时间 | 压缩包 | 大小 |
|---|---|---|
| 10-24 12:22 | `work/my-new-contest/delivery/20261024-122255-DRAFT.tar.gz` | 3,667,114 B |
| 10-24 12:23 | `work/my-new-contest/delivery/DRAFT-final-DRAFT.tar.gz` | 3,666,397 B |
| 10-24 12:36 | `work/my-new-contest/delivery/round1-DRAFT.tar.gz` | 3,682,734 B |
| 10-24 12:42 | `work/my-new-contest/delivery/round2-DRAFT.tar.gz` | 3,691,899 B |
| 10-24 12:48 | `work/my-new-contest/delivery/round2-final-DRAFT.tar.gz` | 3,694,512 B（sha256 `dd74a243b552484d9808ba6e420176064b04548bfa519695f76730cb9e7460d4`） |

> 项目 2 的 `20261024-122255/`、`DRAFT-final/` 两个同级目录也只有 `package-warnings.json`，是未通过的 final 打包尝试。

### 2.3 阶段 III / IV：**尚无论文**

| 项目 | 时间 | 现状 |
|---|---|---|
| `work/beer-rerun-2.8.6/` | 13:10–13:12 | `report/`、`delivery/`、`experiments/`、`figures/` 全空；只有数据/审计/字段契约；`PREP-AUDIT.md` 结论“准备范围内 PASS，重跑阶段 NOT READY” |
| `work/my-new-contest-v2/` | 13:31–进行中 | `report/` 只有空 `figures/`；`src/`、`delivery/`、`validation/` 空；台账 0 实验 0 问题 0 数据 |

### 2.4 论文源文件与构建工程

| 项目 | md（正文源） | tex | 其他构建物 | 构建入口 |
|---|---|---|---|---|
| `A/` | `A/report/paper.md`（106,764 B，含 `{{…}}` 占位符） | `A/report/paper.tex`（152,989 B） | `rendered.md`、`rendered.refs.json`、`tex/build/typeset.md`、`tex/pandoc-template.tex`、`tex/typeset.py` | `A/report/build.sh` + `report/build.log` |
| `work/my-new-contest/` | `report/paper.md`（20,646 B） | `report/paper.tex`（26,497 B） | `rendered.md`、`rendered_build.md`、`rendered.refs.json`、`paper-header.tex`、`report/build_report.json` | `src/build_paper.py` |
| `beer-rerun` / `v2` | — | — | — | — |

论文随包复现说明：`A/delivery/FINAL-DRAFT-2-DRAFT/README_REPRODUCE.md`（31,544 B）、
`work/my-new-contest/delivery/round2-final-DRAFT/README_REPRODUCE.md`（16,903 B）。

---

## 3. 相关代码清单（按时间顺序）

### 3.1 阶段 I：`A/src/` —— 39 个 Python 文件，13,169 行（21:08 → 22:21）

| 时间起→止 | 模块组 | 文件 |
|---|---|---|
| 21:11 → 21:33 | 环境/契约探针 | `probe_env.py`、`probe_contract.py` |
| 21:08 → 21:33 | 审计 → 尺度 → 清洗 → 划分 → 建模表 | `01_audit.py`、`02_scale.py`、`03_clean.py`、`04_split.py`、`05_dim_map.py`、`06_calibration.py`、`07_model_table.py`、`common.py`、`emit.py` |
| 21:35 → 22:11 | 问题一（50 维感官分级） | `q1_models.py`、`q1_bundle.py`、`q1_data.py`、`q1_final.py`、`q1_figs.py`、`q1_abl.py`、`q1_robust_report.py`、`q1_final_summary.py`、`08_baseline_constant.py`、`08b_baseline_ridge.py`、`08c_q1_final.py`、`08d_figures.py` |
| 21:23 → 22:21 | 问题二（共表达图 + Top-3） | `q2_prereg.py`、`q2_common.py`、`q2_graph.py`、`q2_baseline.py`、`q2_figs.py`、`q2_select.py`、`q2_stability.py` |
| 21:36 → 22:10 | 问题三（风格条件生成 + 迁移） | `q3_utils.py`、`q3_models.py`、`q3_generate.py`、`q3_transfer.py`、`q3_exp_family.py`、`q3_baseline.py`、`q3_eval.py`、`q3_figs.py` |
| 21:54 | 独立复算 | `09_independent_rerun.py` |

配套：`A/state/scripts/SCRIPT-0001..0038`（脚本登记副本）、`A/experiments/EXP-0001..0048`（48 个实验目录）、
`A/figures/`（20 张 PNG，其中 15 张登记为 FIG）、`A/data/{raw,clean,processed,splits}`、`A/outputs/{q1,q2,q3,protocol,audit,review,probe,data}`。

### 3.2 阶段 II：`work/my-new-contest/` —— 20 个 py + 8 个取证脚本（11:47 → 12:49）

| 时间 | 模块组 | 文件 |
|---|---|---|
| 11:47–11:48 | 独立数据取证（先于建项，产物即 `analysis/` 三份报告） | `analysis/scripts/`：`sensory_01_xlsx_forensics.py`、`sensory_02_scale_stats.py`、`sensory_03_align_targets.py`、`ref_8xlsx_audit.py`、`ref_crosscheck.py`、`ref_discrepancies.py`、`corr_forensics.py`、`verify_all.py` |
| 12:02–12:04 | 公共库 + 三个数据版本（Q1 mapped / Q2 raw / Q3） | `src/lib.py`、`src/emit.py`、`src/build_q1mapped.py`、`src/build_q2raw.py`、`src/build_q3.py`、`src/q1_common.py`、`src/q1_baseline.py`、`src/q1_candidate.py` |
| 12:08–12:11 | 问题二 + 问题三生成 + 出图 | `src/q2_topk.py`、`src/q1_analysis.py`、`src/q3_generate.py`、`src/make_figures.py` |
| 12:18–12:22 | 独立复跑入口 + 论文生成 | `src/q1_rerun_oof.py`、`src/build_paper.py` |
| 12:33–12:49 | 审计收尾 + 基线/稳健/证据文档 | `src/prepare.py`、`src/q2_baseline.py`、`src/q3_baseline.py`、`src/evidence_docs.py`、`src/q1_trainonly.py`、`src/q3_robust.py` |

配套：`experiments/EXP-0001..0020`（20 个）、`validation/`（18 个目录 / 台账 19 条）、
`figures/`（9 张 PNG，7 张登记）、`data/{raw,clean,processed,splits}`、`outputs/{audit,q1,q2,q3}`。

### 3.3 阶段 III：`work/beer-rerun-2.8.6/src/` —— 20 个 py（13:10，全部拷贝自 3.2）

代码与 3.2 的 `src/` 一一对应（`lib/prepare/build_q1mapped/build_q2raw/build_q3/q1_*/q2_*/q3_*/make_figures/build_paper/emit/evidence_docs`），
目前 0 实验；审计产物在 `outputs/audit/`、`analysis/{sensory,fields}/`。

### 3.4 阶段 IV：`work/my-new-contest-v2/` —— 无代码

只有 `contest.yaml`、`problem/`（题面 pdf+md、targetcolumns.csv）、`data/raw/`（9 个附件）、`state/ledger.json`、
`PREFLIGHT.json`、`START-PROMPT.md`；`src/`、`report/`、`delivery/` 为空。

---

## 4. 同题但非论文的关键文档（按时间顺序）

| 时间 | 文档 | 作用 |
|---|---|---|
| 10-23 21:06 | `A/problem/statement.md`、`questions.yaml` | 题面转写 + 三问定义 |
| 10-23 21:15 | `A/data/clean/DATA_DICTIONARY.md` | 清洗数据字典 |
| 10-23 22:13 | `A/REPRODUCE.md` | A 项目一键复现说明 |
| 10-23 22:20 | `A/delivery/STATUS.md` | **A 交付状态书**：已完成/未完成/为什么、快照（文档自述 rev 518 / 45 实验 / 47 页；台账此后更新至 rev 527），`final=false` |
| 10-23 22:25 | `A/outputs/review/validation_report.md` | A 论文独立审查报告（交付后复核） |
| 10-24 11:42–11:48 | `work/my-new-contest/analysis/{sensory,ref,corr}/report.md`、`QA-五问答题口径与证据.md`、`CONTEXT.md` | 项目 2 的五处数据口径取证（先于建项完成） |
| 10-24 12:48 | `work/my-new-contest/DELIVERY-NOTES.md` | **项目 2 交付说明**：为什么 `final=false`、两轮复审与修正、复现入口 |
| 10-24 12:48 | `work/my-new-contest/delivery/*/README_REPRODUCE.md` | 每个包内的复现说明（14–17 KB） |
| 10-24 13:01 | `work/RERUN-GUIDE-2.8.6.md` | 2.8.6 重跑指南（失败复盘 → 十条铁律） |
| 10-24 13:11 | `work/beer-rerun-2.8.6/PREP-AUDIT.md` + `prep-audit.json` | 重跑前准备审计（Phase 0–2 PASS） |
| 10-24 13:32 | `work/my-new-contest-v2/START-PROMPT.md` + `PREFLIGHT.json` | v2 的执行指令与预检（配置冻结、configStable=true） |

---

## 5. 去重说明（哪些其实是同一份文件）

| 完全相同的 PDF | sha256 前缀 |
|---|---|
| `A/report/paper.pdf` = `A/report/tex/build/paper.pdf` = `A/delivery/final-draft-DRAFT/report/paper.pdf` = `A/delivery/FINAL-DRAFT-2-DRAFT/report/paper.pdf` | `d46d838cec` |
| `A/delivery/2026-MathorCup-A-DRAFT-DRAFT/report/paper.pdf` = 同包 `report/tex/build/paper.pdf` | `cba15455ef` |
| `work/my-new-contest/report/paper.pdf` = `delivery/round2-final-DRAFT/report/paper.pdf` | `c154d55945` |

**真正不同的论文构型只有 7 个**：A 的 44 页版与 47 页版，项目 2 的 5 个 12 页版（12:22 / 12:23 / 12:36 / 12:42 / 12:43）。
每个包内还有一份 `report/tex/build/paper.pdf`（构建残留），与同包主 PDF 字节相同。

---

## 6. 如果只看一份

| 需求 | 打开这个 |
|---|---|
| 要**最新、最完整的代码与最终论文**（项目 2 终稿） | `work/my-new-contest/delivery/round2-final-DRAFT/`（整包）或 `work/my-new-contest/report/paper.pdf` |
| 要**长报告式、证据最全**（47 页、113 个占位符、11 条 claim） | `A/delivery/FINAL-DRAFT-2-DRAFT/`（整包）或 `A/report/paper.pdf` |
| 要**最终交付压缩包** | `A/delivery/FINAL-DRAFT-2-DRAFT.tar.gz`、`work/my-new-contest/delivery/round2-final-DRAFT.tar.gz` |
| 要看**为什么两套都只到 DRAFT** | `A/delivery/STATUS.md`、`work/my-new-contest/DELIVERY-NOTES.md`、`work/RERUN-GUIDE-2.8.6.md` |
| 要找**正在进行的第三次尝试** | `work/my-new-contest-v2/`（无论文，13:42 仍在写台账）、`work/beer-rerun-2.8.6/`（仅准备审计） |

> 注意：两套论文均为 **DRAFT**（`manifest.final=false`，未冻结、未提交任何竞赛平台）；
> 论文页数/大小取自 `mdls`、`report/build.log`、`build_report.json`；时间均为文件 mtime（Asia/Shanghai）。
