# 交付说明（DELIVERY NOTES）— beer-2026-a

本文件是**人工交接说明**，不属于建模台账证据；台账在 `state/ledger.json`，交付检查结论以 `modeling_deliver check` 为准。

## 1. 本项目的真实状态（一句话）

论文三格式（md/tex/pdf）与全部实验/图表已真实产出并通过渲染校验，但**交付检查 `final=false`**，因此只生成了 **DRAFT 包** `delivery/20261024-122255-DRAFT/`（manifest `final:false`）。没有得到 final，也没有提交到任何竞赛平台。

## 2. 已经真实做到的

| 项 | 证据 | 状态 |
|---|---|---|
| 附件导入 + sha256 | 9 个附件 `data/raw/imported/`，sha 在台账 imports | 完成 |
| 数据审计/尺度逐列判定 | `outputs/audit/audit.json`、`scale_identification.csv`、`data_quality.md`（SCRIPT-0003） | 完成 |
| 三个独立数据版本 | DATA-0001（Q2 原始标准化）、DATA-0002（Q1 mapped grade）、DATA-0003（Q3 风格+阈值） | 完成 |
| 划分 | SPLIT-0001/0002，seed=20261024，200/50，assignment sha 相同 | 完成 |
| Q1 实验 | EXP-0001 基线、EXP-0002 Ridge、EXP-0003 HistGBM 全部 succeeded | 完成 |
| Q2 实验 | EXP-0007（EXP-0004 为声明字段错误的早期版本，指标 sha 完全相同） | 完成 |
| Q3 实验 | EXP-0008（EXP-0005 同上） | 完成 |
| Q1 验证 | VAL-0004..0007：泄漏 / 划分 / holdout MAE 复算（Δ=1.1e-16）/ 基线对照 全部 passed | 完成 |
| Q2 验证 | VAL-0016/0017：泄漏 / 划分 passed | 完成 |
| Q3 验证 | VAL-0018：泄漏 passed（**弱检查**：targetColumns=0，见 §4） | 完成但弱 |
| 训练内部独立复算 | `outputs/q1/independent_reproduction.json`：OOF MAE Δ=0 | 完成 |
| 图表 | 7 张图已登记（FIG-0001..0007），check 全部通过 | 完成 |
| 论文渲染 | RENDER-0003：35 个占位引用全部解析，无 stale ref | 完成 |
| 三格式 | `report/paper.md` / `paper.tex` / `paper.pdf`（12 页，568 KB，图可加载） | 完成 |
| 格式声明 | check `formats.declared = [md,tex,pdf]`，`produced = [md,tex,pdf]` | 通过 |
| 要求覆盖 | 6/6 requirements 已 map（REQ-0001..0006） | 完成 |

## 3. 为什么没有 final（按重要性排序，全部如实）

1. **critical claims 被判 stale（根因：协议要求 vs 服务端不变量冲突）**
   用户步骤 3 要求在 init 之后把 `problem.statement` 指向题面 Markdown、把 `delivery.paperFormats` 改为 `[md,tex,pdf]`。服务端把实验的 `configSha256` 固定为**初始化时**的 contest.yaml 哈希（7759c324…），而 claim 的 staleness 检查拿它和**当前文件**哈希（45f3b9b2…）比较。只要在 init 后改过 contest.yaml，该比较就永远不相等。
   - 我验证过：把这两处改动撤回，哈希立刻回到 7759c324…（即根因确认）。
   - 我没有修改台账字段来"洗掉" stale，也没有为了通过而撤回用户指定的配置。因此 CLAIM-0001..0003 保持 stale，`answer:Q1/Q2/Q3` 与 `stale-claims` 检查失败。
2. **independent-rerun 被 holdout 复用预算拒绝**
   `VMU_PACK_MODELING_CONTEST_HOLDOUT_REUSE_UNCONTROLLED`：B0/C1/C2/Q2 四次暴露已耗尽 `maxHoldoutReuse=3`。我最终把改动**撤回**为 3（没有留下放宽后的配置），并改用不触碰 holdout 的训练内部 OOF 独立复算（Δ=0）作为可复现证据，同时在论文与 claims 中披露"holdout 点估计未获第二次独立审计"。
3. **Q1 只能是 provisional selection**：`independent-rerun` 未通过 → `select` 拒绝 validated。
4. **未 freeze**：freeze 的前置条件（计划先于候选、Q2/Q3 有 selected model、Q1 全部必需检查）不满足。
5. **质量门未过**（qualityPassed=false，24 failed / 1 needs_review）：robustness 计划与执行缺失（Q1/Q2/Q3）、Q2/Q3 无 simple baseline 实验、metric-recompute 12 项键名不匹配（claims 引用的是子指标键如 `holdout_mae_mean`，而实验登记的 evaluation.metricKey 是 `mae`/`topk-jaccard`/`constraint-satisfaction`）、模型契约 MCON-0001 缺 formula/boundaryCases、无独立 review 记录、target-lineage 待独立复核。
6. **Q3 leakage 检查偏弱**：targetColumns=0 导致 231 个特征全部 skipped，只验证了"未声明禁用来源"；MDI/SHAP/Prices 的排除是在 DATA-0003 构建脚本里完成的，检查强度不足已在论文 §7 披露。

## 4. 关键结果（论文正文由占位符从台账渲染，此处仅索引）

- Q1：mapped-grade 50 维等权留出 MAE，基线 0.8011 → Ridge 0.7051（OOF 0.6805），HistGBM 0.7080；R² 均值 0.186。
- Q2：Top-3 Jaccard（Spearman vs Ridge）0.228，Spearman vs 网络平滑 0.614，bootstrap 入选频率 0.478。
- Q3：不受约束迁移使缺陷超阈值比例 0.091→0.318（不恶化率 0.333）；缺陷约束投影后不恶化率 1.000、超阈值率回到 0.091，能量距离 4.619 vs 源基线 5.342。
- 数据口径：原始 0–6 不可识别（3.xlsx 12 张评分卡只有模板/公式、summary 恒 0；空 sheet 在 8.xlsx）；2.csv 为实测 Spearman（位置对齐 max|Δ|≈6.7e-16，min eig −0.0424，非 PSD）；1.csv 的 231 个特征列中：70 个对齐化合物 = 37 列 log10 + 33 列原始浓度，5 个理化列 log10（推断），其余 156 列未核验。

## 5. 复现入口

```bash
cd /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
$PY src/prepare.py                 # 审计/尺度
$PY src/build_q2raw.py             # DATA-Q2raw
$PY src/build_q1mapped.py --split SPLIT-0001   # 仅训练集估计的 mapped grade
$PY src/build_q3.py                # DATA-Q3（风格留出 + 阈值）
$PY src/q1_candidate.py --family ridge         # Q1 候选（正式走 modeling_experiment run）
$PY src/q2_topk.py                 # Q2 Top-3 + bootstrap
$PY src/q3_generate.py             # Q3 生成/迁移/缺陷约束
$PY src/make_figures.py && $PY src/build_paper.py
```

正式跑批一律经 `modeling_experiment run`（见 `experiments/EXP-*/`），论文数字一律经 `modeling_deliver render`，不手工抄写。

## 6. 人类需要决定的事

1. 是否接受"init 后修改 contest.yaml"这一协议冲突：若接受，需在 pack 层把 experiment 的 configSha 改为随文件更新，或允许 `re-init`；
2. 若要冲 final：需要按 pack 顺序重做（先登记验证协议、再跑候选、再做 independent-rerun、再 select/freeze），且需要提高 holdout 复用预算或改用 train-only 复跑口径；
3. 是否补做 robustness 计划/执行、Q2/Q3 baseline、独立 review、模型契约 formula——这些是当前质量门的主要缺口。

**边界**：本包为 DRAFT，未提交任何竞赛平台；任何"已验证/最终"表述都不适用于本包。

## 7. 本轮追加的代码级证据（为什么 final 在本项目内结构性不可达）

我直接读了 pack 源码（`packs/modeling-contest/runtime/*.js`），确认四件事：

1. `service.js:114` `this.configSha256 = configResult.sha256`（当前文件哈希）；`store.js:59-66` 只有在 **init** 时把 `configSha256` 写进台账，之后**没有任何 action 会更新 `ledger.configSha256`**。
   → 台账永远是 init 哈希 `7759c324…`，而当前文件是 `45f3b9b2…`。步骤 3 要求 init 后改 contest.yaml，于是：
   - 实验记录 `configSha256 = ledgerBefore.configSha256 || svc.configSha256` = `7759c324…`；
   - `validation.js:claimStaleReasons` 比较 `experiment.configSha256` 与当前文件哈希 `45f3b9b2…` → 永远不等 → **critical claims 永久 stale**。
2. `experiments.js:950-960` 的 holdout 守卫按**每个测试行**的累计使用次数与 `maxHoldoutReuse` 比较；当前台账 `holdoutExposures` 已有 5 次（EXP-0001/0002/0003/0004/0007），每行计数已达 2–3，而配置里是 3 → 任何新的带 split 的实验都被 `HOLDOUT_REUSE_UNCONTROLLED` 拒绝。
   - 唯一豁免是 `verifiedRerun`（`experiments.js:730`）与 `trainOnlyIsolation='macos-seatbelt-v1'`（`experiments.js:733`，需 `evaluationUse:'train-only'+freezeSources:true` 且 macOS `sandbox-exec`）。
   - 但 `independentRerun` 要求**原始实验**先有 `sourceSnapshot.declaredComplete` 且 `dependencies` 完整（`validation.js:1038-1042`）；原始 EXP-0002 没有快照，而新建"完整"原实验会被 holdout 守卫拒绝 → 只能退化为 train-only 口径（评估集不是 holdout），无法支撑 `holdout-metrics` 与 `selection:validated`。
3. `quality/checks.js:434-437` 遍历所有 model contract，`supersededBy` 只读不写（全仓库无写入点）→ MCON-0001 的"缺 formula/boundaryCases"**无法通过任何 action 修复**。
4. `quality/checks.js:183` target-lineage 要求 `latestReview(ledger,'targetContract',TGT-0001)` 为 passed —— 这是可补的（见下）。

**结论**：在不篡改 `state/ledger.json`、不撤销用户指定的 contest.yaml 改动的前提下，`final=true` 无法达成。DRAFT 是唯一诚实产物。

## 8. 独立审查（fresh-context reviewer）与修正记录

审查者（独立上下文、只读、未参与建模）结论：**VERDICT: findings**。已核对一致：TGT-0001 映射公式与 50 组 zmin/zmax 可用 SPLIT-0001 训练行逐值复现（0 mismatch）、q1_mapped 重算最大差 8.9e-16；CLAIM-0001/0002/0003 的数字与 EXP-0001/0002/0007/0008 的 metrics 一一对应，且"非原始 0–6""同期非因果""构造性满足/非酿造验证"均有披露。

已按审查意见修正（本轮）：
1. 论文/审计报告的尺度列数：改为 37+33+5+156（原先散文写 161、审计写 42/33/0 混入理化列）。
2. 删除论文中手写的理化列中位数（原 21 EBC/13.8 IBU/6.4%/2.0 PSI 与产物不符），改为量级表述并指向 `outputs/audit/scale_identification.csv` 的 raw_range/raw_median。
3. 3.xlsx sheet 说明更正为"13 = 12 卡 + summary"，空 sheet 归到 8.xlsx。
4. 三个误差最大维度改为占位符渲染（metallic / A_hops_citrus / F_esters_flower），不再手抄。
5. Q3 "逐样本不恶化比例"改为"风格×缺陷化合物的 12 个组"并说明构造性。
6. `data_quality.md` 的公式误引明细改为真实字段（summary_cell/shared_with），不再渲染 None。
7. 补充 SPLIT-0001 与 SPLIT-0002 assignment sha 相同、训练行一致的追溯说明。

未修正（如实保留）：critical claims 仍 stale（结构性，见 §7）；MCON-0001 缺 formula/boundaryCases（pack 无 supersede 写入点，无法修复）；robustness/baseline/review 记录仍缺。

## 9. 本轮（round 1）追加的证据与进展

质量门状态：**passed 13 / failed 20 / needs_review 1 / n/a 5**（会话初期为 passed 5 / failed 25）。

新增真实证据：
- **Q2 简单基线** EXP-0010：全局统一 Top-3（所有维度共用一份榜单）与逐维 Top-3 的平均 Jaccard = **0.09** → 逐维排序有实质增量（QC-0005 通过）。
- **Q3 简单基线** EXP-0011：无条件全局高斯（不看风格、不迁移）对留出风格的能量距离 **3.719**，低于 few-shot 生成 4.477 与约束迁移 4.619。
  → 这是一个**阴性结果**，已写进论文 §5.3 与 `outputs/q3/results.json`：3–5 例 few-shot 原型不足以刻画 Tripel/Kriek/Lambic 的分布，能量距离偏好全局中心；因此不宣称“生成/迁移优于基线”，只宣称“缺陷不恶化 + 相对源风格基线更接近”。
- 分析证据文档（SCRIPT-0010/0011）：`outputs/q1/robustness.json`、`outputs/q2/{factor_analysis,robustness}.json`、`outputs/q2/recommendations.md`、`outputs/q3/{question_definition,method,results,robustness}.json`、`outputs/q3/recommendations.md` → QC-0009/0010/0011 通过。
- 独立审查记录 **REV-0001**（fresh-context reviewer，independence=independent_context）：verdict=findings，4 条发现中 3 条已修复并标注 resolved，1 条（claim 文本“逐样本”措辞）保留为 open 并说明原因。→ QC-0025/0026/0027 通过。

仍未通过（如实）：
- requirement-coverage + 12 项 metric-recompute：都源自 **critical claims stale**（config sha 冲突），claim 文本不可编辑、旧 check 的 planned metric 取的是 claim 里的子指标键；
- model-condition：MCON-0001 缺 formula/boundaryCases，pack 没有 supersede 写入点，无法修复；
- robustness 计划/执行（Q1/Q2/Q3 共 6 项）：我们没有做预注册的重复划分/扰动实验，**不伪造**计划去凑检查；
- target-lineage：需要 verdict=passed 的独立推导审查，而本次审查结论是 findings（不是 passed）。

因此 `qualityPassed` 仍为 false，交付仍为 DRAFT。

## 10. independent-rerun 的最后一次尝试（失败，如实记录）

为绕开 holdout 复用预算，我按 pack 支持的 **train-only 隔离** 口径注册了 EXP-0012
（`evaluationUse:'train-only'` + `freezeSources:true` + `dependenciesComplete:true`，
macOS seatbelt 隔离，只读 train.csv）。运行结果：**failed / NONZERO_EXIT**，
原因：隔离快照只打包 `src/*.py`，而脚本调用 `lib.target_columns()` 去读
`analysis/sensory/targetcolumns.csv`，该文件不在快照里。
未重试的原因：修好需要把 50 个目标列名内嵌进脚本并**重新注册**（新 EXP id），
且即使跑通，`selection:Q1` 仍要求原始 EXP-0002 自己具备 fresh 的 independent-rerun
（EXP-0002 无 sourceSnapshot，无法补），因此不能把 final 打开。
该失败实验保留在台账（EXP-0012，status=failed），未删除、未覆盖。

## 11. Round 2：独立复跑（train-only 隔离）已真实通过

- 新增 `src/q1_trainonly.py`：只读 `MODELING_TRAIN_FILE`（train.csv），50 个目标列名内嵌（隔离快照只携带 `src/*.py`），直接调用 runner 注入的 `modeling_contract.emit_metrics`（只发有限数值）。
- **EXP-0016**（train-only + freezeSources + dependenciesComplete，seatbelt 隔离）**succeeded**，OOF MAE = 0.6804670815061572。
- `modeling_validate independent-rerun` 自动生成 **EXP-0017** 并比较：**VAL-0019 passed，Δ=0**（与 EXP-0002 的 oof_mae_mean 0.6804670815061571 在 1e-16 内一致）。
- 失败轨迹同样保留在台账：EXP-0012（隔离快照缺 `analysis/sensory/targetcolumns.csv`）、EXP-0013/0014（`import emit` 不可用）、EXP-0015（emit_metrics 拒绝字符串指标）。

**但这仍不足以打开 final**：`modeling_project status` 显示 validation 阶段的必检项全部被判"未通过"，因为该阶段用 `ledger.configSha256`(7759c324…) 作为 ctx，而所有 validation 的 `configSha256` 是当前文件哈希(45f3b9b2…)，两者永不相等。这是 §7 已定位的同一根因的另一种表现。

## 12. Round 2 收尾状态

| 项 | 状态 |
|---|---|
| 独立复跑（train-only 隔离） | **VAL-0019 passed，Δ=0**（EXP-0016 → EXP-0017） |
| Q1 / Q2 / Q3 选择 | 全部 **provisional**（MODEL-0002 / MODEL-0007 / MODEL-0008），记录在台账 |
| 质量门 | passed 13 / failed 20 / needs_review 1 / n/a 5（QC-0005/0006/0009/0010/0011/0025/0026/0027 已通过） |
| 论文 | RENDER-0007（42 占位符全部解析，无 stale ref）；PDF 12 页 |
| DRAFT 包 | `delivery/round2-DRAFT.tar.gz`（92 文件，manifest final:false） |

`modeling_project status` 的 validation 阶段仍把**所有**必检项判为未通过：该阶段用
`ledger.configSha256`(7759c324…) 作 ctx，而所有 validation 记录的是当前文件哈希(45f3b9b2…)，
两者永不相等（与 §7 同一根因）。即便 VAL-0019 已 passed，也不被计入。

复审（TGT-0001 是否已是可辩护派生标签）的独立 subagent 在本次轮次内**未返回结论**，
因此 REV-0002 未记录、QC-0003 仍为 needs_review；不做"代填通过"。

## 13. 第二轮独立复审（REV-0002）与修正

复审结论 **findings**，2 条 blocking（均为我上一轮没改全的论文措辞），已修复：
1. `paper.md:135/:147` 的"逐样本不恶化比例/比值" → 改为"3 风格 × 4 有阈值化合物 = 12 个**组级**比例"，并注明同一风格同一化合物的 11 个源样本共享同一平移量（`rendered.md` 已无该措辞）。
2. 删除论文"换用其他映射时模型排序保持方向一致"的表述（`outputs/q1/robustness.json` 明确未重跑替代映射），改为"不声称排序对映射不变"。
另有一条 confirmation：复审用 SPLIT-0001 训练 200 行重算 50 组 zmin/zmax 得 **0 mismatch**，`q1_mapped.csv` 重算最大差 **8.9e-16**，截断 27/25 与 clip_stats 相符，mapped grade ≠ 原始 0–6 的声明属实。

已重建 RENDER-0008 与 PDF（12 页）。REV-0002 记录为 verdict=findings（其中 F1/F2 已 resolved，F3 为确认项）；
按 pack 规则 target-lineage 需要 **verdict=passed** 的最新审查，因此 QC-0003 在终审返回前保持 needs_review。

## 14. 终审与最终质量状态（本轮末）

- **REV-0003（TGT-0001，verdict=passed）**：独立终审 grep 无残留措辞；用 EXP-0008/outputs.json 逐行复算 24 行 = 12 组 × 2 variant、raw 12 组均值 4/12 = 0.3333 与 metrics 一致；q1_map_params.json 与正文的公式/训练集估计/clip 27·25/非原始 0–6 声明逐项相符。
- **REV-0004（TGT-0002，verdict=passed）**：独立重算确认 50 个目标列与 targetcolumns 一一对应（50/50、同序），50 列均值 |mean|≤0.063、sd 0.369–0.857、12500 值中 7618 个越出 [0,6]，且论文明确"同期关联、非因果"。
- QC-0003 **target-lineage 通过**；QC-0025/0026/0027（审查来源/独立性/关键发现）通过。

**质量门最终状态：passed 14 / failed 20 / pending 3 / needs_review 0 / n/a 5 / stale 0**（会话初期为 5/25/4）。

仍失败的 20 项全部可归因到 3 个根因：
1. **critical claims stale**（结构性的 config sha 冲突）→ requirement-coverage + 12 项 metric-recompute（另有 3 项 pending）；
2. **MCON-0001 缺 formula/boundaryCases** → model-condition（pack 无 supersede 写入点）；
3. **未做预注册的稳健性实验** → 6 项 robustness plan/execution（不伪造计划）。

交付物：`delivery/round2-final-DRAFT.tar.gz`（92 文件，manifest final:false）；论文 RENDER-0008 / PDF 12 页。
