# 包 02 · beer 项目（projectId: `beer-2026-a`）

**第二套完整解**：2026-10-24 11:24 → 12:50（CST），竞赛投稿式论文 **12 页**，共 **5 个论文版本**。
本包保留 5 个版本的 PDF、完整代码、建模前的数据取证报告、实验元数据、台账与最终交付包。

---

## 1. 论文

**题目**：《基于化合物谱的啤酒风味预测、归因与风格条件生成》

| 版本 | 时间 | 文件 | 说明 |
|---|---|---|---|
| v1 | 10-24 12:22 | `paper/versions/2026-10-24-1222-v1.pdf` | 第一版（第一个 DRAFT 包） |
| v1 重打包 | 10-24 12:23 | `paper/versions/2026-10-24-1223-v1-repack.pdf` | 内容几乎相同，仅换包名 |
| Round 1 | 10-24 12:36 | `paper/versions/2026-10-24-1236-round1.pdf` | 补 Q2/Q3 简单基线、独立审查记录 |
| Round 2 | 10-24 12:42 | `paper/versions/2026-10-24-1242-round2.pdf` | 独立复跑（train-only 隔离）通过后 |
| **终稿** | 10-24 12:43 | `paper/paper.pdf` | 含两轮复审修正，12 页；`build_report.json` 记录 pandoc + 两遍 xelatex、9 图全部可加载 |

源文件：`paper/paper.md`（20,646 B）、`paper/paper.tex`（26,497 B）、`paper/rendered.md`、
`paper/rendered_build.md`、`paper/rendered.refs.json`、`paper/paper-header.tex`、`paper/build_report.json`。

## 2. 目录

```text
paper/          终稿三格式 + 渲染物 + 5 个历史版本 PDF
src/            20 个 Python（2,895 行）：三个数据版本 + Q1/Q2/Q3 + 出图 + 论文生成
analysis/       建模前的 5 份数据取证报告（sensory / ref / corr）+ 脚本 + 原始证据 CSV
figures/        9 张 PNG（7 张登记为 FIG）
data/           raw（附件 + imported 副本）/ clean / processed / splits
problem/        题面 md + PDF + questions.yaml
experiments/    EXP-0001..0020 元数据（含 failed 记录）
validation/     18 个验证目录（台账 19 条记录）
outputs/        audit/ q1/ q2/ q3/ 汇总产物
ledger.json     台账（rev 494，1.5 MB）
docs/DELIVERY-NOTES.md  交付说明：为什么 final=false、两轮复审与修正、复现入口
delivery/round2-final-DRAFT.tar.gz  最终 DRAFT 包（sha256 dd74a243b552…）
contest.yaml / metrics.json
```

## 3. 代码地图

| 阶段 | 文件 |
|---|---|
| 数据取证（先于建模） | `analysis/scripts/`：`sensory_01_xlsx_forensics.py`、`sensory_02_scale_stats.py`、`sensory_03_align_targets.py`、`ref_8xlsx_audit.py`、`ref_crosscheck.py`、`ref_discrepancies.py`、`corr_forensics.py`、`verify_all.py` |
| 公共库 + 数据版本 | `src/lib.py`、`src/emit.py`、`src/build_q1mapped.py`、`src/build_q2raw.py`、`src/build_q3.py`、`src/q1_common.py`、`src/q1_baseline.py`、`src/q1_candidate.py` |
| 问题一/二/三 | `src/q1_analysis.py`、`src/q1_rerun_oof.py`、`src/q1_trainonly.py`、`src/q2_topk.py`、`src/q2_baseline.py`、`src/q3_generate.py`、`src/q3_baseline.py`、`src/q3_robust.py` |
| 出图与论文 | `src/make_figures.py`、`src/build_paper.py`、`src/prepare.py`、`src/evidence_docs.py` |

## 4. 复现

```bash
# 依赖同包 01；论文为 pandoc + xelatex（ctexart）
# 按 docs/DELIVERY-NOTES.md 第 5 节：
python src/prepare.py                      # 审计 / 尺度逐列判定
python src/build_q2raw.py                  # DATA-0001（Q2 原始标准化）
python src/build_q1mapped.py --split SPLIT-0001   # DATA-0002（Q1 mapped grade）
python src/build_q3.py                     # DATA-0003（Q3 风格 + 阈值）
python src/q1_candidate.py --family ridge  # Q1 候选
python src/q2_topk.py                      # Q2 Top-3 + bootstrap
python src/q3_generate.py                  # Q3 生成 / 迁移 / 缺陷约束
python src/make_figures.py && python src/build_paper.py
```

## 5. 主要结果（论文与 `docs/DELIVERY-NOTES.md` 第 4 节）

- **Q1**：50 维等权留出 MAE，常数基线 0.8011 → Ridge 0.7051（OOF 0.6805）、HistGBM 0.7080；R² 均值 0.186。
  交付的是 **mapped grade**（训练集端点映射 + 截断），**不是原始 0–6 评分**。
- **Q2**：Top-3 方法间 Jaccard 0.228，与网络平滑 Spearman 0.614，bootstrap 入选频率 0.478 → 结论具方法依赖性，只作探索性归因。
- **Q3**：不受约束迁移把缺陷超阈值比例 0.091 → 0.318（不恶化率 0.333）；加缺陷约束投影后不恶化率 1.000、超阈值率回到 0.091；
  能量距离 4.619 vs 源风格基线 5.342。另有一个阴性结果：无条件全局高斯基线能量距离 3.719 更低，故不宣称生成优于基线。

## 6. 为什么仍是 DRAFT（如实记录）

1. **critical claims 永久 stale**：用户步骤要求在 `init` 之后修改 `contest.yaml`，而实验记录的 `configSha256` 固定为 init 时的哈希，
   两者永不相等（详见 `docs/DELIVERY-NOTES.md` 第 7 节的源码级证据）。
2. **independent-rerun 被 holdout 复用预算拒绝**，只能改用不触 holdout 的训练内部 OOF 独立复算（Δ=0）作为可复现证据。
3. **quality 门未过**：robustness 计划/执行、Q2/Q3 简单基线（部分后补）、模型契约 formula/boundaryCases、独立 review 等缺口。
4. **未 freeze、未提交**；DRAFT 是唯一诚实产物。

## 7. 本包省略的内容

交付目录中只有最终包 `round2-final-DRAFT.tar.gz`；另外 4 个 DRAFT 压缩包（12:22/12:23/12:36/12:42）因体积与内容重复未纳入，
其论文 PDF 已作为历史版本保留在 `paper/versions/`。`data/raw/staged`（导入暂存，与 `imported/` 重复）未纳入。

## 8. 附：所有交付包清单（历史记录，压缩包未全部纳入）

| 时间（CST） | 包 | 大小 | sha256（前 16 位） |
|---|---|---|---|
| 12:22 | `20261024-122255-DRAFT.tar.gz` | 3,667,114 B | — |
| 12:23 | `DRAFT-final-DRAFT.tar.gz` | 3,666,397 B | — |
| 12:36 | `round1-DRAFT.tar.gz` | 3,682,734 B | — |
| 12:42 | `round2-DRAFT.tar.gz` | 3,691,899 B | — |
| 12:48 | `round2-final-DRAFT.tar.gz` | 3,694,512 B | `dd74a243b552484d…` |
