# 独立验证报告（reviewer）— 进行中，随实验台账滚动更新

> 本报告只登记**可核对**的结论：台账 id / 产物路径 / 数字来源。未完成的检查写 `PENDING`，失败的写 `FAIL`，
> 具名拒绝写 `REFUSED`，**不把计划/产物存在写成"通过"**。
> 更新日期：2026-10-23（本轮：协议登记、数据事实、标定核验、Q2 图/证据复核、Q3 产物与 rerun、Q1 候选全验）。
> 关键发现与 claim 互链：**CLAIM-0006**（Q2 辅助矩阵=同数据相关系数 → "独立先验"是循环验证）；
> **REV-0011**（同一结论的台账记录）；**REV-0012**（EXP-0025 passed）；**REV-0013**（Q3 MAJOR a–d + VAL-0012 FAILED）。

## 0. 台账与协议

| 问题 | 协议 | 覆盖的语义检查（Lead 要求） | 产物 |
|---|---|---|---|
| Q1 | VP-0001（原始）、**VP-0004**（可执行单列绑定） | leakage、split-integrity、metric-recompute、baseline-superiority、ordinal-calibration*、reproducibility | `outputs/review/calibration_verification.json`、`ordinal_calibration.json` |
| Q2 | VP-0002（原始）、**VP-0005**（可执行单列+split） | stability、multiplicity*、prior-consistency*、leakage | 待 `outputs/q2/top3_*` |
| Q3 | VP-0003（原始）、**VP-0006**（可执行单列） | constraint-satisfaction*、leakage、fidelity、small-n* | `outputs/review/q3_independent_checks.json` |

\* pack 无对应 checkType 的检查由 reviewer 独立脚本执行并登记 quality review（REV-0001..0005）。
VP-0004/0005/0006 的补登原因：pack 的 leakage/holdout-metrics 需要显式单一 `targetColumn`；语义与容差与原协议相同，**未放宽任何阈值**。

## 1. 数据事实（独立复算，`outputs/review/data_facts_recheck.json`）

| 事实 | 结论 |
|---|---|
| 250 样本 / 231 化合物 / 50 目标 | PASS（250×234 / 231×231 / 250×53） |
| 缺失 73 个 / 9 列 / 63 行 | PASS（逐列：amyl.acetate 27、aroma_hops_sum 13、methylpyrazine 12、X2.3.butanedione 9、X3.methylbutanal 7、ethyl.nicotinate 2、其余 3 列各 1） |
| 2.csv = Spearman | PASS（30/30 对与 Spearman 一致，差 ≤5e-4；Pearson 0/30；全矩阵 pairwise-complete Spearman 最大差 7.8e-16） |
| 4/7.csv beer_id 脱敏（唯一值 96） | PASS；三表 beer 顺序一致（1=4=7） |
| 4.csv 连续性 | **106–250 个不同取值**（不是 172–249）；仍判连续 |
| 1.csv 尺度 | 70 列可回算：37 log10（10^v 相对误差 ~5e-10）+ 33 linear；**161 列未验证** |
| LOD/2 删失码 | PASS：755 格逐格核过（37 个 log10 列，all_match） |
| dim_map 50/50 | PASS（需 `_x000D_`/CRLF 归一化；overall 在 5/6.csv 中为 "Overall appreciation (Trained panel)"） |
| 划分 | SPLIT-0002/stratified：200/50、overlap=0、union=250；主划分 test 缺 West Flanders ale（7 样本全在训练侧），stratified 22/22 进 test（两版 sha 已核） |

## 2. Q1 标定核验（`outputs/review/calibration_verification.json`）

| 检查 | 结论 |
|---|---|
| (a) `(a,s)` 是否只用训练 200 | **PASS**：train-200 重估与 stored 中位 \|Δs\|=1.1e-16；全 250 重估对照 0.075 |
| (b) 13 锚定维 ρ / 斜率符号可复算 | **PASS**：13/13 ρ 差 ~1e-16（≪±0.05）；Theil-Sen 与 Huber 斜率符号均 13/13 一致 |
| (c) 四套口径单调性 | 违反列数 0/0/0/0；**但这是重言式**（四套规则均为单调映射），不能当效度证据 |
| (d) 口径间 QWK | 独立复算 P1-P2=0.691、P1-P3=0.599、P1-P4=0.355（canonical 0.691/0.603/0.355）；**只反映标定敏感性，不是准确率** |
| 缺陷维弱锚定 | dms ρ=0.089 / diacetyl ρ=−0.111（主口径 SPLIT-0001）；stratified 0.072/−0.043；结论稳健：这两维无法由目标化合物解释 |
| 证据溯源 | **OPEN**：无 tag 的 `grade_calibration.json` 是 n=250 全量拟合版（14 维、QWK 0.674/0.538/0.320），与 canonical 不一致，须删除/重生成 |

Q1 台账进展：

| 实验 | 状态 | 内容 | pack 检查 |
|---|---|---|---|
| EXP-0007 | succeeded | B0 常数基线（features=[]） | VAL-0003 leakage PASS、VAL-0004 split-integrity PASS（旧版缺裸键，已被 EXP-0012 取代） |
| EXP-0012 | succeeded | B0 常数基线中间版（r2 语义不自洽：r2=50 维均值但 predictions.csv 是 overall 单列） | VAL-0005 independent-rerun PASS（旧口径）；已由 EXP-0015 取代 |
| EXP-0013 | succeeded | EXP-0012 的复跑 | — |
| EXP-0015 | succeeded | **当前台账基线**（`rerunOf: EXP-0012`；r2=overall 单列、r2_50dim=50 维均值） | VAL-0007 holdout-metrics **PASS**（复算 r2 差 2.2e-16）、VAL-0008 split PASS、VAL-0009 leakage PASS、VAL-0010 independent-rerun **PASS**（r2_50dim 差 0，复跑 EXP-0021） |
| EXP-0017 | cancelled | Q1 最终集成模型（pls/et/rf/hgb） | **CANCELLED**（约 13:47 被取消，非超时；无 metrics，不计入任何结论） |
| **EXP-0025** | succeeded | **Q1 可用候选**：三路等权 PLS5+ET150+RF150（`src/08c_q1_final.py`） | VAL-0013 holdout-metrics **PASS**（r2=0.048196，差 0）、VAL-0014 baseline-compare **PASS**（r2_50dim=0.220579>0）、VAL-0015 leakage PASS、VAL-0016 split PASS、VAL-0017 independent-rerun **PASS**（r2_50dim 差 0，复跑 EXP-0034） |
| EXP-0004 | failed（保留） | B1 ridge 首版 | NO_OUTPUT（未调 emit） |
| EXP-0005 | failed（保留） | 契约探针 | NO_OUTPUT（emit_metrics 拒收字符串） |

- **B0 与独立基线逐位一致**：EXP-0007 `holdout_r2_mean=-0.024635435726754987` = 我的独立均数基线（差 0）
  → 划分/目标对齐双确认。
- 独立基线（分折中位数插补 + 共表达族聚合 + RidgeCV），两套划分各算一遍（`outputs/review/independent_baseline.json`）：
  - SPLIT-0002：留出 **R²=0.0785**（中位 0.0591）、MAE=0.3846、Spearman=0.2494；
  - stratified：留出 **R²=0.1301**（中位 0.0925）、MAE=0.3932、Spearman=0.3618。
  **参考量级**：EXP-0004 首版（未加数值防护）打印的 holdout R²=0.0574 低于独立基线；B1 最终版须明显高于此才谈得上"候选更强"。
  候选在 SPLIT-0002 与 stratified 上的数字都要报（主/复核两栏）。
- **50 维全量独立重算（PASS，容差 1e-6）**：对 EXP-0012 的 `predictions_long.csv`（`split=test`，2500 行 × 50 维）独立重算：
  均值 R²=**-0.024635435726755**（上报 -0.024635435726755，差 3e-17）、MAE=0.409737038231132（相同）、
  overall R²=-0.014456198175550（上报 -0.014456198175550，差 2e-16）。metric-recompute 语义要求满足。
- **pack 层 holdout-metrics 的具名限制**：metric 名只能在 `rmse/mae/mse/r2/accuracy/f1/mape/accuracy5/weighted-score`
  且只复算单列；`r2_overall` 被拒（"cannot recompute metric 'r2_overall'"）。因此 50 维均值 R² **无法由 pack 直接复算**，
  只能由 reviewer 独立重算（已做，见上）；如需 pack 单列证据，需另登记"单维验证实验"。这是工具限制，不是模型缺陷，也不是通过。
- **产物契约缺口已修复**：EXP-0015（`rerunOf: EXP-0012`）按定稿语义记录：`r2=-0.014456198175549995`（overall 单列，
  VAL-0007 复算差 2.2e-16）、`r2_50dim=holdout_r2_mean=-0.024635435726754987`（科学主指标）、`mae=0.42349438534479994`；
  单列 `predictions.csv` + 长表 `predictions_long.csv` 并存。EXP-0007/0012 保留为合同演进链。

**Q1 当前选定候选 = EXP-0025（"当前选定"而非"最终模型"；B6_fusion 若登记且验证更好，由 Lead 改选）**：

| 指标 | 值 | 验证 |
|---|---|---|
| r2_50dim（科学主指标，holdout） | **0.220579478860721** | VAL-0014 >0 PASS；我的 50 维全量重算差 2.8e-17 |
| r2（overall 单列） | 0.048195876201119 | VAL-0013 pack 复算差 0 |
| holdout_mae_mean / r2 median / spearman | 0.342228 / 0.177707 / 0.408539 | 我的重算差 ≤5.6e-17 |
| oof_r2_50dim | 0.228531 | 复跑差 0 |
| 对照 EXP-0015（台账基线） | r2_50dim 差值 **+0.24521** | baseline-compare PASS（VP-0007 阈值 0 更严） |
| 对照 reviewer 独立基线 | SPLIT-0002 0.0785 | 候选明显高于独立基线 |

- `params` 与脚本一致性已核：`nTrees=150`、`maxFeatures=0.2`、`clipQuantiles=[0.01,0.99]`、`imputation=in-fold median`；
  脚本 docstring 仍写 ET/RF 300 棵树（**注释过期，实际 150**，以 params/metrics 为准）。
- 复现：同 seed 复跑 EXP-0034，全部指标差 ≤3.3e-16。
- 未做：stratified 划分上的候选评估（ROB 稳健性口径）。
- **B6_fusion（EXP-0029）已登记并核验**：`src/q1_final.py`，PLS8+ET400+RF400+HGB 等权；`r2_50dim=0.253574`、
  `r2=0.009210`、`mae=0.423589`、`holdout_mae_mean=0.334085`、`spearman=0.441771`；台账已有 VAL-0024 leakage、
  VAL-0025 split、VAL-0026 holdout-metrics、VAL-0027 baseline-compare（均 PASS）；我的 50 维全量重算差 ≤2.2e-16。
  **EXP-0029 的 r2_50dim 0.2536 > EXP-0025 的 0.2206** → 若 Lead select B6，最终候选应改为 EXP-0029；
  independent-rerun 待计算槽空闲后补跑（VP-0007）。

## 3. Q2 图实验（EXP-0003）

- **VAL-0001 split-integrity：PASS**（SPLIT-0002：200 train / 50 test / overlap 0，assignment+train+test 哈希入账）。
- **VAL-0002 leakage：PASS**（231 个声明特征；无禁止列进入特征；max |r|=0.401 < 0.999；目标列 present-but-unused）。
- 独立复核 2.csv：**pairwise-complete Spearman 精确重建**（最大差 7.8e-16）。模型脚本用"中位数填补后重算"复核，
  最大差 0.0478——这是**填补引入的偏差**，不是 2.csv 的问题（minor）。
- EXP-0002 状态 `failed`（脚本非零退出），EXP-0003 为重跑后的成功版本——失败记录保留、未覆盖，符合纪律。
- Top-3 选择产物已于 21:50 落盘（`top3_per_dimension.csv` 150 行/50 维、`method_jaccard.csv`、`importance_matrix.csv`、
  `univariate_fdr.csv`、`prior_consistency.csv`、`metrics.json`）。**但 `selection_frequency.csv`/`bootstrap_top3.csv` 仍缺**
  → 单席位 bootstrap ≥0.80 的检查**证据未就绪**（不判通过）。
- **稳定性（跨方法 Jaccard）FAIL（最终选择 EXP-0041）**：实验 metrics 报 `jaccard_mean=0.1867`（中位 0.15）；
  我用 `method_jaccard.csv` 独立复算 pair-level 均值 **0.217**（26.4% pair ≥0.5）——远低于预登记阈值 **0.50**
  → Q2 的"跨方法一致"判 FAIL，只能写"Top-3 对方法选择不稳定"。
- **bootstrap（关键：EXP-0042 超时但文件在盘）**：`EXP-0042`（`q2_stability.py`，B=300，M1/M4）**timed-out（600s）**，
  但 `outputs/q2/bootstrap_top3.csv` 完整落盘（90,000 行 = 300 rep × 50 维 × 3 席 × 2 方法）——写在项目 outputs 下，
  未进实验目录、`outputFiles` 为空 → **provenance 有缺口**。
  我独立重算逐席位频率：**M1 7/150 席 ≥0.80（4.7%，平均 modal freq 0.273）、M4 8/150（5.3%，0.296）**；
  与实验聚合 `freq_ge_080_share=0.0933`（14/150，约为两方法并集）方向一致 → **bootstrap 下 Top-3 极不稳定**。
  结论：Q2 稳定性两个口径（跨方法 Jaccard 0.1867/0.217、bootstrap 席位稳定 ~5%）**都远低于预登记阈值**。
- **最终选择指标**：`M4_n_q_global_lt_0.05=2721`（与我独立 2714 一致）、`prereg_hit_rate=0.0972`（14/144）、
  `prior_spearman_mean=0.6282`（循环，见下）。
- **多重比较（PASS）**：模型 `m4_n_q_global_lt_0.05=2721`；我独立复算 50×231 pairwise-complete Spearman + BH 得
  **2714**，显著集合 overlap 2712、Jaccard **0.996**、p-值秩相关 **0.99994** → 模型 BH 可复现。
- **prior-consistency：循环验证（本报告最重要的 Q2 发现，已固化为 CLAIM-0006）**：我独立重建三个辅助矩阵——
  **2.csv = Spearman(1.csv)（max|Δ|=6.1e-16）、5.csv = Spearman(4.csv)（6.1e-16）、6.csv = Spearman(1.csv,4.csv)（6.7e-16）**。
  即 6.csv 不是"独立外部先验"，而是同 250 样本的相关系数。用它做"独立 |r| 秩相关核对"是循环验证：
  模型报 `prior_spearman_mean=0.7341`、50/50 正显著，本质上是"方法与同数据单变量相关的一致性"；若直接用 M4（单变量）
  对照 6.csv，ρ 恒等于 1.0。**结论必须改写**：6.csv 只能作"数值一致性/管线检查"，不能作为独立先验证据。
- 静态泄漏扫描（只匹配真实 I/O）：当前 `q2_*.py` 无读取 6/7.csv 或 GBM/SHAP 的调用；`M4_abs_rho` 与我的独立
  单变量 |Spearman| 相关 0.99997（max|Δ|=0.020），确认 M4 来自 1.csv 而非 6.csv。
- 预注册命中率 `prereg_hit_rate=0.1389`（20/144 席位）——模型自己的预注册期望大部分未命中，论文应披露，
  不能只报"Top-3 与预注册一致"的维度。

## 4. Q3 产物预检（版本换代说明 + 当前哈希复核）

**版本换代（2026-10-23 21:36–21:46）**：Q3 modeler 把生成/评估 artifact 换代为 SCRIPT-0036（生成）+ SCRIPT-0034/0038（评估），
模型 = 低秩高斯 + 条件均值锚定 + 33 列 log1p（k=15）。**旧版 SCRIPT-0022/0031 的 per-style 命中率（Christmas 0.01、Scotch 0.02、
Faro 0.00、Saison 0.31、Brown 0.33、Dubbel 0.28，聚合 0.60）已作废、在新 artifact 下复现不出来**；旧记录保留在本报告
的 git 历史与本文件下方的"旧版记录"块中，用于解释"为什么加入锚定"。

当前 artifact（`outputs/q3/metrics.json` 21:46）独立复核：

| 检查 | 结论 |
|---|---|
| 生成谱支撑/非负 | PASS：2500×231 格，below-min 0、above-max 0、线性列负值 0（与模型自报一致） |
| 小样本 | PASS：Kriek n=10（train 9）、Lambic n=11（train 8）、Faro n=3；bootstrap CI 已报 |
| **风格命中率（MAJOR-b 改写）** | **PASS 但指标饱和、失去区分度**：我的独立 LogisticRegression 得 aggregate 0.9936（模型 0.994），per-style 0.96–1.00（Tripel 0.995、Kriek 1.000、Lambic 1.000）。**基线模型 `style_hit_macro`=0.9973 与主模型 0.994 无差异** → 不能用 style_hit 证明全风格保真；必须用逐风格能量距离 + 缺陷合理性 + 画像一致性。 |
| **分布吻合（新增 negative result）** | **主模型未优于基线**：主模型 Tripel `ed_over_dref`=**0.12643**，基线=**0.12618**（几乎相同，主模型不更好）。说明"锚定 + 低秩"的贡献主要在**可解释性/约束可行性**，不在分布拟合精度；论文模型评价一节必须写明。 |
| 能量距离（绝对量） | 独立复算 Tripel 2.058 / Kriek 4.571 / Lambic 2.601（模型 2.078/4.573/2.595，同定义下一致） |
| 缺陷生成（MAJOR-a，仍有效） | 逐风格逐位一致（Tripel DMS 0.975/diacetyl 0.620/4VG 0.0；Kriek DMS 0.135；Lambic diacetyl 0.500）。相对真实同风格：Tripel DMS 0.975 vs 0.893、diacetyl 0.620 vs 0.464；Kriek diacetyl 0.595 vs 0.800（更好）；Lambic diacetyl 0.500 vs 0.364（更差）、DMS 0.620 vs 0.818（更好）→ **生成缺陷分布偏移**，须披露，不得写"缺陷水平一致" |
| 迁移（MAJOR-c，数字更新、口径不变） | 11/11 硬约束满足（max 违反 7.9e-10 ≤1e-6，我的逐样本复核一致）；独立分类器 Tripel 命中 **6/11=0.5455**（迁移前 0.0），质心距离 14.21→9.36（z）。只能写"**部分向 Tripel 质心迁移**"，不得写"转为 Tripel" |
| 五类缺陷 | 绝对 OAV 仅 DMS/Diacetyl/4VG；t2n 与 stale hops 用浓度不增代理（逐样本绝对增量 ≤1e-6）。**不得写"五类全部通过"** |

**旧版记录（已作废，保留追溯）**：SCRIPT-0022/0031 的聚合命中率 0.6016、per-style Christmas 0.01/Scotch 0.02/Faro 0.00/
Saison 0.31/Brown 0.33/Dubbel 0.28、迁移 4/11=0.364、ED Tripel 2.076。这些数字**不能**在论文里引用；仅用于说明
"未锚定 → 锚定"的迭代原因。

**Q3 正式 VALIDATION（部分完成）**：
- EXP-0022（conditional-lowrank-gaussian）：VAL-0011 **leakage PASS**（231 特征、无禁止列、max|r|=0.401）。
- EXP-0024（Q3 最终候选，同族 rerun）：VAL-0012 **independent-rerun FAILED（passed=false）**。
  - 主指标 `gen_style_fidelity` 三次复跑均 0.994（差 1e-16，稳）；
  - 但 `profile_spearman_placeholder`（=`r2_50dim`）在复跑间 **0.4073 → 0.8935**（seed 43/44 一档、45 一档；
    均值 0.7315 vs 原值 0.4073，\|Δ\|=0.324 ≫ 0.05）；
  - 复跑间 `ed_over_dref_tripel`、`energy_distance_*`、`gen_style_fidelity` **完全相同**（差 0）→ 说明
    `q3_eval.py` 读的是项目级共享产物 `outputs/q3/seeds/generated_spectra_seed*.csv` 且 `U.SEED=42` 固定，
    **没有读取 runner 注入的 `MODELING_SEED`**；复跑期间共享产物被重写/替换，导致输入不一致。
  - 结论：Q3 的 independent-rerun **不构成有效的 seed 稳定性检验**；且 sensory-profile 指标本身在 0.407/0.894
    两档跳变（不可复现）。需：q3_eval 改为读实验目录内产物或按 `MODELING_SEED` 现场生成，然后重跑。
- 新发现（minor）：Q3 把 `r2_50dim` 用作 **profile Spearman**（不是 R²），键名与 Q1 的 `r2_50dim`（R²）语义不同，
  跨问题比较/ROB-0003 会被误导，建议改名 `profile_spearman_required` 或在报告里显式声明。
- EXP-0019（Q3 基线）已 succeeded：ed_over_dref_tripel=0.12618、style_hit_macro=0.9973。

## 4.5 不可复现/无效验证的处置（本次最重要的负面发现，单列）

| 项 | 判定 | 原因与处置 |
|---|---|---|
| **EXP-0024 / VAL-0012（Q3 independent-rerun）** | **FAILED（passed=false）** | 主指标 gen_style_fidelity 三复跑均 0.994（稳），但 `profile_spearman_placeholder`（=Q3 `r2_50dim`）复跑间 **0.4073→0.8935**（\|Δ\|=0.324 ≫ 0.05）。同批 ED/gen_fidelity 三复跑**完全相同（差 0）**→ `q3_eval.py` 用 `U.SEED=42` 固定、不读 `MODELING_SEED`，且读项目级共享产物 `outputs/q3/seeds/*.csv`（13:50–13:51 被重写）→ 复跑输入不一致。**该 rerun 不能作为 seed 稳定性证据**；需改为实验目录内产物或按 MODELING_SEED 现场生成，artifact 冻结后重跑。 |
| **Q2 prior-consistency（6.csv）** | **无效（循环验证）** | 独立重建：2.csv=Spearman(1.csv)（6.1e-16）、5.csv=Spearman(4.csv)（6.1e-16）、6.csv=Spearman(1.csv,4.csv)（6.7e-16）→ 6.csv 不是独立先验。`prior_spearman_mean=0.7341` 只能当"与同数据单变量相关的一致性"检查，不能当独立证据；M4 对照 6.csv 时 ρ≡1.0。 |
| **EXP-0017（Q1 最终集成首版）** | **CANCELLED（无 metrics）** | 约 8 分钟后被取消（非超时），不计入任何结论；EXP-0025 为可用候选。 |
| **EXP-0007 / EXP-0012** | 历史（合同演进链） | 分别因缺裸键 `r2`、`r2` 与单列 predictions 不自洽被 EXP-0015 取代；失败记录保留。 |
| **EXP-0004 / EXP-0005 / EXP-0008** | FAILED（保留） | NO_OUTPUT：未调 emit / emit_metrics 拒收字符串；作为"为什么必须有 emit 契约"的证据链。 |

**处置原则**：以上任何一项都**不得**在论文/claim 中写成"已验证"；Q3 的 stochastic-stability 在修好前记"未完成"；
Q2 的"独立先验"表述必须改为"同数据一致性"。

## 4.6 负面发现汇总（三项，按 Lead 要求单独成节）

### 4.6.1 holdout 复用超限（major）

- `contest.yaml.quality.robustness.maxHoldoutReuse = 3`，但台账里 **SPLIT-0002 已被 21 个 `succeeded` 实验使用**
  （另有 11 queued、8 failed、2 running、1 cancelled 也登记在同一 split）。
- 后果：holdout 不再只是"锁定后的一次评估"，而是被用于基线/候选/消融的反复比较 → **Q1 的 holdout 数字（含 0.2206/0.2536）
  是选择后的开发集数字，存在选择偏差**；论文不得把 holdout 当作无偏泛化估计。
- 缓解/要求：① 论文明确写"holdout 复用 21 次 > 预登记上限 3，数字为开发集估计"；② 用 `stratified/` 划分做一次
  不参与选择的独立复核（目前台账里**没有**任何实验绑定 stratified 划分，这是缺口）；③ 若进入 delivery，robustness
  计划需如实记录超限。

### 4.6.2 循环验证（major，已固化 CLAIM-0006）

- 独立重建：**2.csv = Spearman(1.csv)（max\|Δ\|=6.1e-16）、5.csv = Spearman(4.csv)（6.1e-16）、
  6.csv = Spearman(1.csv,4.csv)（6.7e-16，2200 对）**。
- 因此 6.csv 不是独立外部先验；Q2 的 `prior_spearman_mean=0.6282`（最终选择）/0.7341（早期）只能解释为
  "方法与同数据单变量相关的一致性"，直接拿 M4 对照 6.csv 时 ρ≡1.0。论文不得写"独立先验验证通过"。

### 4.6.3 无效验证的处置（VAL-0012 FAILED）

- EXP-0024 的 `independent-rerun` 判 FAIL：主指标 gen_style_fidelity 三复跑 0.994（稳），但 `profile_spearman_placeholder`
  （=Q3 r2_50dim）复跑间 0.4073→0.8935（\|Δ\|=0.324≫0.05）。
- 根因：`q3_eval.py` 用 `U.SEED=42` 固定、不读 `MODELING_SEED`，且读项目级共享产物 `outputs/q3/seeds/*`（13:50–13:51 被重写）
  → 复跑输入不一致。
- 处置：**维持 FAILED，不得写成通过**；修法=读实验目录内产物或按 MODELING_SEED 现场生成，artifact 冻结后重跑。
  `q3_eval.py` 至本轮仍未修，故最终报告口径为"Q3 seed 稳定性未成立"。

### 4.6.4 工具侧记账缺陷（非结果问题）

- `freeze` 被宿主记账缺陷挡住：部分 validation 记录在台账里 `status`/`questionId` 为 null，门禁取不到
  （Lead 已在 `delivery/STATUS.md §G` 留证）。这是**工具问题**，不是验证结果问题；reviewer 未通过改 ledger 绕过，
  本报告保留原始 VAL 记录与证据链。

## 5. 失败/未完成清单（截至本轮）

| 项 | 状态 | 说明 |
|---|---|---|
| Q1 实验 | PENDING | 等 `modeling_experiment` 登记后跑 run + independent-rerun |
| Q2 Top-3 选择 | PENDING | `q2_select.py` 未登记/未产出；`importance_matrix.csv`/`bootstrap_top3.csv`/`univariate_fdr.csv`/`method_top3.csv` 未落盘 → 证据未就绪（不判通过） |
| Q3 实验 EXP-0006/0009/0011/0019 | queued | **登记但未运行**（never started），不计入任何结论 |
| EXP-0004 / EXP-0005 | FAILED（已保留） | NO_OUTPUT；前者未调 emit，后者 emit_metrics 拒收字符串 |
| EXP-0007 independent-rerun | REFUSED（已被 EXP-0012/0015 取代） | 缺裸键 `r2`；predictions.csv 为长表 |
| EXP-0017 | CANCELLED（不计入结论） | Q1 最终集成运行约 8 分钟后被取消；无 metrics；需重跑更快配置 |
| Q1 pack holdout-metrics | REFUSED（工具限制） | 只支持单列 whitelist 指标，50 维均值无法直接复算；reviewer 独立重算替代 |
| Q3 正式实验 | PENDING | 产物在生成中，哈希未锁定 |
| `grade_calibration.json` 溯源 | OPEN | 旧 n=250 文件仍存在，Lead 引用过其中的数字（14/50、0.674/0.538/0.320） |
| EXP-0002 | FAILED（已保留） | 非零退出；EXP-0003 为重跑，未覆盖失败记录 |

## 6. 判定口径（不得混用）

- reproduction（同 seed 复跑 1e-6）与 stochastic-stability（跨 seed ≤0.05）分开报，详见
  `outputs/review/reproduction_vs_stochastic_stability.md`。
- 口径间 QWK 不是效度；分级序单调不是效度；pack 的 holdout-metrics 单列通过不等于 50 维通过。
- 任何 `PENDING/REFUSED/FAIL` 不得在论文中写成"已验证"。
