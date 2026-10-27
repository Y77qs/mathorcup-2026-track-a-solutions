# v6.1 · 复赛修正轮（`beer-2026-a-v3` 续）—— DRAFT

**这是 v6 之后的复赛修正轮**：项目在同一目录（`work/my-new-contest-v6`，项目 id `beer-2026-a-v3`）上
按“v6.1 显式恢复轮”（RUN-0004）继续重跑科学修正项并重排论文，2026-10-27 22:07 产出 **38 页**论文与 DRAFT 交付包。
交付判定仍为 **DRAFT**（`final=false`、`qualityPassed=false`）。

- 论文题目：《基于稳健表示、共表达网络与风格条件生成的啤酒化合物—感官强度建模》
- 论文：**38 页**（`paper/paper.pdf` 3,111,844 B，ART-0022，sha256 `31d5e72d…`，绑 RENDER-0022）
- 台账：revision 5220；实验 **133** 个（116 succeeded / 11 failed / 6 queued）；验证 77 条；图 50 张；claim 67 条
- 质量检查：45 项（**32 passed / 12 needs_review / 1 failed**）
- 体量：1889 文件 / 约 202 MB（裁剪自原项目约 3.0 GB，见 §7）

> 与 v6 的关系：v6 是 10-27 上午的确认轮（30 页）；v6.1 是同日傍晚的**复赛修正轮**，重跑了
> Q3 截距/NA/边际/V 选参、Q2 方向一致率、完整可行域基线等科学修正，并把论文扩到 38 页；
> 交付仍是 DRAFT，未冻结、未提交平台。

---

## 1. 状态判定（如实）

| 项 | 实际值 |
|---|---|
| `final` / `draft` | **false / true** |
| `qualityPassed` / `engineeringComplete` / `checkpointsPassed` | 均 **false** |
| 台账 `frozen` | 仍是 2026-10-24 的旧记录（rev 2731），**不代表本轮** |
| 质量检查 | 45 项：32 passed / 12 needs_review / 1 failed |
| 交付包 | 仅 DRAFT（`20261027-220714-DRAFT.tar.gz`）；FINAL 包装被禁止（`package-warnings.json` 可证） |
| 运行控制 | RUN-0004 显式恢复；RUN-0003 记为 stopped / unknown-usage；一笔请求未结算，预算检查 needs_review |

论文摘要是工作稿，正文数字以占位符引用本轮确认实验（三问各含主实验、对照与稳健性种子块），并明确“不得作为最终提交稿”。

## 2. 论文（`paper/`，38 页）

| 文件 | 大小 | 说明 |
|---|---|---|
| `paper.pdf` | 3,111,844 B | **38 页**（ART-0022），9 张确认图 |
| `paper.md` | 119,684 B | 正文源（占位符） |
| `rendered.md`（RENDER-0022） | 122,874 B | 渲染产物（0 stale） |
| `paper.tex`（ART-0021） | 158,705 B | LaTeX 源 |
| `paper.pandoc.md` / `rendered.pandoc.md` | 138,245 / 50,947 B | pandoc 中间件 |
| `rendered.refs.json` | 50,562 B | 占位符 ↔ 台账引用 |
| `paper.build.json` / `BUILD-INPUTS.json` / `evidence_manifest.json` / `pdf-audit.json` | — | 构建记录、输入清单、证据清单、PDF 结构审计 |
| `tables/`（39 文件） / `text/`（30 份逐页文本） | — | 表与排版核对材料 |
| `paper.log` / `xelatex-*.log` | — | 编译日志（记录 38 页） |

**主要结果**（渲染稿）：Q1 Aroma/Flavour 30 维等权 MAE **0.3593**（中位数基线 0.3982）、全 50 维 **0.3505**（基线 0.3919）；
Q2 四方法 Top-3 平均 Jaccard **0.2091**，方向一致率 **0.9817**；Q3 归一化经验 V 能量距离 **0.8727**（仍高于同量重采样参照），
迁移交付策略转移能量 **2.0799**，综合不增率 1（由硬上界构造保证）。

## 3. 目录

```text
paper/            38 页论文与构建/审计材料（来自最新 DRAFT 包）
src/              52 个 Python（数据、Q1/Q2/Q3、r00/r03/r05/r07 审计与复现、论文构建）
data/             raw/clean/processed/splits
experiments/      133 个实验（保留元数据、metrics/result/outputs、predictions、sets、seed-receipt、图）
validation/       54 组目录（台账 77 条验证）
figures/          43 张 PNG：confirmatory/（9 张）、confirmatory_v2/、主图、archive/
outputs/          audit/ q1/ q2/ q3/ contracts/ robustness/（含 qp_cert_audit.json）
state/            ledger.json（13 MB，rev 5220）、scripts/、build/、env-verify/
delivery/         20261027-220714-DRAFT.tar.gz（32.2 MB）+ support-20261027-220714.tar.gz（21.7 MB）
                  + 20261027-220714-package-warnings.json（FINAL 被拒回执）
rework-notes/     R00–R07 变更/决策/证据说明、13 份独立审查记录、handoff、validation-selection、contract-repair、
                  recovery/（recovery-proof/receipt、baseline、collected-experiments）
docs/             AGENT-BRIEF
problem/          题面 + questions；reference/ 插件使用指南；analysis/ 感官列对齐
根目录文件         DELIVERY-NOTES.md、REPRODUCE.md、change_log.md、AI-USAGE.md、ORIGINAL_TASK.md、CONTINUE.md、
                  论文修改建议.md、MathorCup_A_v5.1/v6_面向复赛修改说明.md、MathorCup_A_独立审查与重跑方案/、
                  contest.yaml、sets.json、sets_pi_first.json、bootstrap_pi.csv
```

## 4. 本轮科学修正（摘要）

- **Q3**：截距/NA/边际与 V 选参重跑；化学反-2-壬烯醛与感官 t2n 代理两个命题分列（代理仍在部分样本上升）；
  迁移侧 198 个 QP 证书均最优，源状态分层核验通过，交付策略能量优于同可行域均值投影基线，两者综合不增率均为 1。
- **Q2**：新增“与总体 Spearman 点估计同方向的一致率”（0.9817），旧口径 P(ρ>0) 仅作历史对照；
  附件 2 描述性网络与训练折内网络明确区分，前者只作结构解释。
- **Q1**：四模型共用嵌套交叉验证；图 Ridge 与普通 Ridge 几乎相同，低秩改善归因于**低秩收缩**，不读作“加图收益”。
- **稳健性**：按问题分列的种子/参数/预算扰动相对极差均在预注册限内，但每组只覆盖 3 个冻结种子中的 2 个；
  固定种子复跑只证确定性重现。Q1 划分完整性/留出评价、Q3 原生优化检查结构性未通过。

## 5. 交付包

| 文件 | 大小 | 说明 |
|---|---|---|
| `delivery/20261027-220714-DRAFT.tar.gz` | 32,210,589 B | 本轮 DRAFT 包（含 README_REPRODUCE 209 KB、SHA256SUMS、report/、src/、figures/、experiments/、data/、ledger-summary 3.1 MB、quality-blockers） |
| `delivery/support-20261027-220714.tar.gz` | 21,705,984 B | 支撑材料包（exp/、q1/、q2/、q3/、report/ 支撑数据与清单） |
| `delivery/20261027-220714-package-warnings.json` | 125,663 B | FINAL 打包被拒的警告回执 |

## 6. 复现

- 项目级：`REPRODUCE.md`；交付包内：`README_REPRODUCE.md`（台账生成，含版本、哈希与逐条命令）
- 论文重建：`src/build_paper.py --build --pdf --no-caption-ids --outdir report --allow-report-output`
  （`--no-caption-ids` 保证题注只显示中文编号，不出现内部表/图 id）；表格 `src/paper_tables.py`；
  确认图 `src/make_confirmatory_figures.py`
- 说明：本轮未成功冻结，`frozen` 字段是 v5 的旧身份；任何“已冻结/已验证”表述不适用于本目录。

## 7. 本目录未纳入的材料（原项目约 3.0 GB → 本目录 202 MB）

| 未纳入 | 原体积 | 说明 |
|---|---|---|
| `state/devrun` | 1.2 GB | 各模型运行目录与日志 |
| `state/repro-clean` | 365 MB | 两次干净复现的完整产物 |
| `.rework/plugin`、`dist`、`plugin-review` | ≈ 79 MB | 2.8.10 插件源码/构建/复审（插件材料） |
| `.rework/evidence`、`acceptance`、`previews`、`build-test`、`reviews/pages*` | ≈ 200 MB | 重跑证据、验收、预览、构建测试的原始页面与二进制（文本类审查已收入 `rework-notes/reviews/`） |
| 实验 `inputs/`、`repeat*/`、大批逐实验 CSV | ≈ 2.7 GB | 每实验数据副本、稳健性重复、bootstrap/候选评分等大表 |
| `report/revised-20261025`（DRAFT 包内） | 15 MB | v5.1 修订目录，已单列为仓库 `v5.1/` |
| `__pycache__`、`.DS_Store`、`mplconfig` | — | 缓存 |
