# v2 · 实战整改审计稿（独立论文；`mathorcup-2026-a` 独立副本）

**三篇论文中的第二篇**（按时间：v1 10-23 → 本目录 10-24 10:48 → v3 10-24 11:24）。
它是一份**独立成篇的审计论文**，性质是对 v1 项目的独立副本做一次“整改审计”，不是第三套同题解：

- 由工程整理程序根据竞赛独立副本的真实台账与复算文件重新生成，2026-10-24 10:48 产出；
- 论文只有 **5 页**（审计草稿），作者自述“不能作为通过质量验收的竞赛终稿”。

- 论文题目：《啤酒化学成分、感官映射与条件生成：实战整改审计草稿》
- 来源：`/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/outputs/建模实战整改最终交付/竞赛副本产物/`
- 状态：**DRAFT**（见论文开头引文）

---

## 1. 与 v1 / v3 的关系

| | v1 | v2（本目录） | v3 |
|---|---|---|---|
| 项目 id | `mathorcup-2026-a` | `mathorcup-2026-a` 的**独立副本**（台账 rev 780/781） | `beer-2026-a` |
| 时间 | 10-23 21:04–22:27 | 10-24 10:48 | 10-24 11:24–12:50 |
| 论文 | 47 页完整解 | 5 页审计草稿（独立论文） | 12 页完整解 |
| 性质 | 第一套完整解 | **对 v1 的复核与重打包，不是新解** | 第二套完整解 |

关键关系：本目录 `practical-final-20261024-DRAFT/report/history/pre-practical-repair/paper.pdf` 是 **v1 的 47 页原稿备份**
（sha256 `d46d838cec…`，与 `../v1/paper/paper.pdf` 完全一致）。本目录在 v1 的基础上增加了两件事：
① 对存量预测做逐维复算（`src/q1_recompute_exp0029.py`、`src/engineer_q1_audit.py`）；
② 按审计结论重写了 5 页草稿并重新打包。

## 2. 论文要点（节选）

- **Q1**：已选模型 `MODEL-0022 / EXP-0025` 的 50 维平均留出 R² 为 0.220579；更强存量预测 `EXP-0029` 经 2500 个 beer×dim 单元格复算后，
  逐维 R² 算术平均 **0.253574**、中位数 0.244622，但 `overall` 单维仅 **0.009210**。审计只证明存量文件指标一致，**不构成独立复跑证明**，因此未改选模型。
- **Q2**：实际候选为 `MODEL-0032 / EXP-0041`，平均 Jaccard 0.186667、预登记命中率 0.097222，仅 1/50 个维度 Jaccard ≥ 0.5；旧产物中以 `r2` 命名的同值字段实为集合重合度，不解释为预测 R²。
- **Q3**：`MODEL-0029 / EXP-0036` 仍存在映射器依赖不完整、历史复跑失败、分布拟合证据弱等问题。
- **边界**：留出集历史被反复用于模型判断，不能通过重新划分或更换 split ID 恢复为“未见数据”，因此保持草稿。

## 3. 目录

```text
REPAIR-SNAPSHOT.json                       台账快照（rev 780、final=false、三个 sha256）
practical-final-20261024-DRAFT/            原交付包解包内容（包名保持原样，可用 SHA256SUMS 校验）
├── README_REPRODUCE.md                    台账生成的复现说明（含环境、数据集/划分 hash、命令）
├── SHA256SUMS                             包内逐文件 sha256
├── contest.yaml                           生效配置（sha a89e9e2f…）
├── ledger-summary.json                    台账摘要（结论、验证、图形、复跑关系）
├── quality-blockers.json                  质量门阻塞项
├── report/
│   ├── paper.md / paper.tex / paper.pdf    5 页审计草稿
│   ├── rendered.md / rendered.refs.json
│   ├── analysis/practical-q1-audit/       Q1 逐维复算证据（metrics/outputs/per_dim_recompute.csv）
│   ├── history/pre-practical-repair/      v1 原稿备份（47 页）
│   └── tex/ build.sh 等构建工程
├── src/                                   42 个 Python（v1 的 39 个 + 复算/审计/训练隔离 3 个）
├── figures/                               31 张登记图（FIG-0002…）
├── experiments/                           25 个实验的打包产物
└── data/                                  clean / raw / splits
```

## 4. 完整性

原交付压缩包 `practical-final-20261024-DRAFT.tar.gz`（7,154,835 B，sha256 `e7edb09a24efd87239c847c390e390998ec6dd7b6449ae9eceaebab889349ca5`）的内容
已**原样解包**在本目录下，因此未重复存放压缩包。校验方式：

```bash
cd practical-final-20261024-DRAFT
shasum -a 256 -c SHA256SUMS
```

## 5. 复现

见 `practical-final-20261024-DRAFT/README_REPRODUCE.md`（台账生成，含解释器版本、依赖版本、数据集与划分 hash、逐条命令）。
注意原机器解释器路径为 `/Users/baozhashizitou/Documents/Codex/…`，在其他机器上需替换。
