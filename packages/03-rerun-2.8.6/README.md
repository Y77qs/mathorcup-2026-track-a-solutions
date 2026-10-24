# 包 03 · 2.8.6 重跑材料（rerun-2.8.6）

本包不是论文，而是**第二套论文失败复盘后的重跑材料**：重跑指南、重跑准备审计、以及第三次尝试（v2）在
2026-10-24 13:46 的进行中快照。共 54 个文件。

题目仍是同一道：2026 MathorCup 大数据挑战赛 赛道 A 初赛。

---

## 1. 内容

```text
RERUN-GUIDE-2.8.6.md        47 KB 重跑指南（2026-10-24 13:01）
beer-rerun-2.8.6/          2.8.6 重跑准备项目（projectId: beer-2026-a-r2）
├── PREP-AUDIT.md          重跑前准备审计（2026-10-24 13:11，Phase 0–2）
├── prep-audit.json        审计结构化结论
├── contest.yaml           预冻结的竞赛配置
├── analysis/              sensory / fields 审计证据
├── outputs/audit/         审计产物（audit.json、data_quality.md、scale_identification.csv）
├── src/                   20 个 py（与包 02 的 src 一一对应）
├── state/ledger.json      台账（rev 31，0 实验 0 论文）
└── problem/               题面 md + questions.yaml
my-new-contest-v2/         干净重跑项目（projectId: beer-2026-a-v2）快照
├── PREFLIGHT.json         预检：配置冻结、configStable=true、stage=intake
├── START-PROMPT.md        v2 的执行指令（数据事实清单 + 十条铁律）
├── contest.yaml           已冻结配置
├── src/                   进行中新增的脚本（q_common、00_prepare_q1q2、00_prepare_q3、q1_baseline、q1_candidate_ridge）
├── state/ledger.json      台账快照
└── problem/               题面 md + targetcolumns.csv
```

## 2. 重跑指南要点

`RERUN-GUIDE-2.8.6.md` 是包 02 失败复盘后的操作手册，目标为“新项目一次跑到 `final=true`”，核心是十条铁律：

1. `init` 之后不再改 `contest.yaml`（配置是协议指纹）；
2. `plan` 只调一次；
3. 每个小问只登记一个 validation plan，且必须在 candidate 之前；
4. 不在 candidate 之后补 plan、不在 quality-plan 后改 claim 的 metricKey；
5. candidate 必须带 `freezeSources` / `dependenciesComplete` / `dependencies`；
6. claim 的 `metricKey` 用实验注册键（`mae` / `topk-jaccard` / `constraint-satisfaction`）；
7. requirement refs 用 `{kind,id}`；
8. 一个 holdout 行最多 3 次成功曝光，不把 holdout 当调试集；
9. review 必须来自独立上下文；
10. 任何 unknown usage 立即停止。

并附带“旧坑对照表”（init 后改配置导致 sha 永久不一致、plan 晚于 candidate、子指标键、MCON 缺 formula 等）。

## 3. 两个重跑项目的状态

| 项目 | 时间 | 结论 |
|---|---|---|
| `beer-rerun-2.8.6` | 13:10 → 13:12 | **准备范围 PASS**：配置在 init 前定稿、`configChanged=false`、未跨不可逆门（0 实验 / 0 plan / 0 claim / 0 QC / 0 review / 0 robustness plan）；重跑阶段 **NOT READY**（缺 3 个真实基线、validation plan 未登记） |
| `my-new-contest-v2` | 13:31 → 13:46（快照） | 干净重跑已开始：配置 `466a882b…` 冻结、`configStable=true`、stage=intake；正在写数据准备脚本。**截至快照无论文、无实验** |

## 4. 说明

- `beer-rerun-2.8.6/src/` 的 20 个脚本与 `packages/02-beer-2026-a/src/` 内容对应，保留在此仅为让本包自包含；
- 两个项目的 `data/` 目录未纳入（与包 01/02 的数据重复，约 20 MB），需要时指向 `../01-A-mathorcup-2026-a/data` 或 `../02-beer-2026-a/data`；
- v2 是**进行中的活项目快照**，其台账在快照之后仍会变化。
