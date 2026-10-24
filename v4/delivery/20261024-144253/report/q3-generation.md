# Q3 证据：风格条件生成、感官画像与跨风格迁移

> 本文件是 `modeling_project workbench` 为 Q3 登记的 `question-definition`、`method`、`results` 与 `recommendations`
> 证据义务的落点，同时供论文第五节引用。数值一律写成台账占位符；结论只写"生成合理性/约束满足"，
> **不写真实酿造验证、不写因果/未来预测**。阈值与量纲事实以 `report/data-quality.md` 第 10 节、
> `data/processed/q3_thresholds.json` 与 `report/validation-notes.md` §4.1 为依据；契约以 `quality.modelContracts[MCON-0001]` 为准。

## 1. 问题定义（question-definition）

- **要回答什么（可检验）**：给定风格条件，生成一个 231 维化合物谱，使它 (a) 落在该风格的训练分布附近，
  (b) 同时满足 7 项有真实阈值的缺陷约束；并回答"跨风格迁移后缺陷是否恶化"。
- **不是**：不是预测 style（style 是条件标签）；不是预测感官评分；不是真实酿造验证。
- **数据可得性**：`DATA-0003`（`q3_table.csv`，250 × 279 = 5 元数据 + 231 `chem__*` + 43 `thr__*`），
  风格 `tasting_category_fine` 共 22 个；`style_holdout` 把 Tripel(28)/Kriek(10)/Lambic(11) 共 **49 行**标为
  `heldout_style`，其余 **201 行**为 `train_style`。拟合只用 201 个 `train_style` 行。
- **为什么这样定义**：题面要"在给定风格下生成合理的化合物谱，并给出其感官画像；同时做跨风格迁移，保持缺陷化合物不恶化"。
  它没有给出"真实答案谱"，所以评价只能是分布一致性 + 约束满足 + 迁移前后相对比较，而不是精度指标。
- **主指标**：`constraint-satisfaction` = 生成谱中同时满足全部 7 项约束的行数 / 总行数（越大越好）。
  7 项约束在 `MCON-0001.constraints` 里是结构化数组 `{column, max:0}`，列名为 `excess__<化合物>`，
  `excess = 原始浓度 / 阈值 − 1`；约束列必须出现在 `generated_profiles.csv`。
- **辅助指标（只进论文表格，不进 claim 指标引用）**：`energy-distance`、`profile-consistency`、`defect-nonworsen-rate`。

## 2. 方法（method）

### 2.1 缺陷阈值集与量纲换算（先做，先于任何生成）

**可用阈值（7 个，唯一的缺陷判定依据）**——`threshold_mean` 口径，已换算到数据集尺度：

| 数据集列 | 化合物 | 阈值 mean | 单位 | 1.csv 尺度 | bound（约束上限） |
|---|---|---|---|---|---|
| `chem__DMS` | Dimethyl sulfide | 17.25 | µg/L | log10 | 1.236789099 |
| `chem__X2.3.butanedione` | Diacetyl | 0.29925 | mg/L | 原始浓度 | 0.29925 |
| `chem__X4VG` | 4-vinylguaiacol | 0.206333 | mg/L | 零值底限 log10（floor = −2.013157381） | −0.6854306064 |
| `chem__acetaldehyde` | Acetaldehyde | 50.0 | mg/L | log10 | 1.698970004 |
| `chem__DES` | Diethyl sulfide | 1.2 | µg/L | log10 | 0.07918124605 |
| `chem__H2S` | Hydrogen sulfide | 3.5 | µg/L | log10 | 0.5440680444 |
| `chem__SO2.mg.L.` | Sulfur dioxide | 15.333333 | mg/L | log10 | 1.185636577 |

**换算规则（逐列，不得统一）**：log10 列 `原始浓度 = 10^x`；原始浓度列直接取值；
零值底限列在存储值等于 floor code 时原始浓度按 0 处理（**不得**取 `10^floor` 当浓度），否则 `10^x`。
1.csv 不携带单位，阈值单位与 1.csv 浓度单位一致是**假设**（`q3_thresholds.json → exceedanceCheck.assumedConcentrationUnit` 逐列写明）。

**量纲陷阱**：直接把 `thr__*` 原始阈值当 bound 去比 `chem__*`，250 个真实样本里 138/250（55.2%）"满足"，
而 7 个 bound 有 5 个从不触发——这是空洞通过。换算后同一批真实样本只有 **6/250（2.4%）** 同时满足全部 7 项
（H2S 230/250、DMS 168/250、Diacetyl 112/250、4VG 16/250、DES 46/250 超阈值）。
**2.4% 是论文必须报告的基率，不是模型成绩。**

**不可评估（不得编造）**：`trans-2-nonenal`（1.csv 有 `X.E..2.nonenal`，但 8.xlsx 该行阈值两列皆空）；
`Stale hops`（阈值表无此化合物，它只是感官描述符）。两者只能做迁移前后相对比较，不能做阈值判定。

**其余 36 个 `thr__*` 只是参考水平**（bitterness 5 IBU、ethanol 1.757 %v/v 等），不得当缺陷限值。

**边界样例（来自 8.xlsx 阈值定义，不是生产代码）**：`ratio_to_threshold=1 → excess=0`；`0.5 → −0.5`；
`2 → +1`（违约）；`chem__X4VG` 存储值等于 floor code 时 `excess = 0/阈值 − 1 = −1`。

### 2.2 无条件/全局基线（必须先跑）

不使用 style 条件，从 201 个训练行的全局经验分布（逐列边际 + 相关结构）采样生成谱。
作用：证明"风格条件是否带来信息增量"，并为 `constraint-satisfaction` 提供无条件参照。

### 2.3 风格条件生成

在 201 个 `train_style` 行上估计每个风格的条件分布（风格内中心 + 协方差，按样本量做收缩），
在给定风格下采样生成谱；Tripel/Kriek/Lambic 三个风格**不参与拟合**，只用于测试。
每风格生成样本数、协方差收缩系数、生成器 seed 全部写入登记的 `params.generator`，先于结果固定。

### 2.4 跨风格迁移

对 `Pils/Lager` 的真实谱，按目标风格（如 Tripel）的条件分布做分位数/仿射迁移，逐样本记录迁移前后 7 项约束状态与
"是否恶化"，写入 `transfer_report.csv`（`before/after` 与 `worsened`）。“不恶化”用 `defect-nonworsen-rate` 单独报告，
**不是**主指标，也不能用常量阈值冒充"不恶化"。

### 2.5 感官画像

以目标风格条件下生成谱的期望/分位数为输入，给出该风格的感官画像（Aroma/Flavour/口感-缺陷-总体三类维度）。
若画像用 Q1 的代理模型推断，必须标注"代理近似、非实测评分"，且代理模型只能用 Q1 训练行拟合。

## 3. 结果（results）

### 3.1 主指标与参照

| 实验 | 条件 | `constraint-satisfaction` | 说明 |
|---|---|---|---|
| 无条件基线 `EXP-0006` | 无 style | {{metric:EXP-0006:constraint-satisfaction}} | 参照下界 |
| 风格条件生成 `EXP-0007` | style 条件 | {{metric:EXP-0007:constraint-satisfaction}} | 主结果 |
| **交付** `EXP-0007`（风格条件+约束投影） | 见 3.3 选择规则 | {{metric:EXP-0007:constraint-satisfaction}} | 交付结论引用 |
| 真实样本参照 | — | 6/250 = 2.4%（数据事实，见 2.1） | 不来自实验，不得写成模型指标 |

辅助：`energy-distance` {{metric:EXP-0007:energy-distance}}、`profile-consistency` {{metric:EXP-0007:profile-consistency}}、
`defect-nonworsen-rate` {{metric:EXP-0007:defect-nonworsen-rate}}。

### 3.2 图形证据（已登记，FIG id 可核）

- 约束满足率对照（含真实基率）：`{{figure:FIG-0012}}`。
- 风格感官画像（生成 vs 训练行真实分布）：`{{figure:FIG-0009}}`。
- 生成谱 vs 真实谱分布对比：`{{figure:FIG-0010}}`。
- 迁移前后缺陷项逐项对比（必须同时画阈值线与迁移前/后两组点）：`{{figure:FIG-0011}}`。

### 3.3 选择规则与结论边界（先于结果声明）

- 选择：以 `constraint-satisfaction` 为主，要求 `defect-nonworsen-rate` 不劣于无条件基线；若条件生成不如基线，
  如实报告"条件信息未带来改善"，不放宽阈值、不换 mean→median 口径来制造改善。
- 结论句由 {{claim:CLAIM-Q3}} 承载，`appliesTo` 写明"Tripel/Kriek/Lambic 风格留出、7 项缺陷约束、生成合理性"，
  `limitations` 写明"非真实酿造验证、单位一致是假设、2 项不可评估、真实基率 2.4%"。
- **禁止**：把约束满足率写成"通过率/合格率"；把生成谱写成"可酿造的配方"；把迁移写成"保持了风格真实性"。

## 4. 限制（必须与结论同时出现）

1. 生成合理性/约束满足 ≠ 真实酿造验证；没有发酵与品评，不能声称可酿出该风格。
2. 单位假设未被外部核实；若 1.csv 浓度单位与阈值单位不一致，所有满足率整体偏移。
3. `trans-2-nonenal` 与 `Stale hops` 不可评估；36 个参考阈值不得当缺陷限值。
4. 真实基率 2.4% 说明 7 项约束同时满足在真实啤酒中本就罕见；满足率接近该量级是合理的，显著偏高需检查退化解。
5. 风格留出是"风格级"留出，不等于外部批次验证；5/6/7.csv 不构成外部验证。

## 5. 建议（recommendations）

| 建议 | 支持证据 | 适用对象/时点 | 成本与约束 | 如何验证 |
|---|---|---|---|---|
| 把 7 项缺陷约束当配方筛选的硬门槛 | 2.1 阈值表与 2.4% 基率 | 配方设计、缺陷排查 | 单位一致是假设；2 项不可评估 | 实测浓度复核 |
| 用风格条件生成做候选谱扩增，再用代理画像排序 | 主指标 + 画像一致性 | 早期配方探索 | 生成谱非实测，需实验验证 | 小批量酿造 + 盲评 |
| 补充 `trans-2-nonenal` 阈值数据后再纳入缺陷约束 | 不可评估项声明 | 完整缺陷评估 | 需要文献/实验阈值 | 阈值确定后重跑约束检查 |
| 需要外部有效性时采集独立批次/工艺样本 | 同源派生事实 | 外推与上线 | 需要新数据 | 独立批次留出评估 |

## 6. 复现与状态

- 脚本：`src/q3_*.py`（无条件基线、条件生成、迁移；阶段 B 落地），共同模块 `src/q_common.py`；独立复算 `src/validate_q3.py`。
- 产物：`generated_profiles.csv`（含 7 个 `excess__*` 列）、`transfer_report.csv`、`metrics.json`（含 4 个指标）、图。
- 复跑：`modeling_experiment {action:"run"}`；原实验带 `freezeSources:true` + `dependenciesComplete:true` 才可独立复跑。
- 状态：以台账为准。**Q3 两个实验（EXP-0006 基线、EXP-0007 条件生成）均已 succeeded**，上表数值可渲染。

### 6.1 四个诚实点（与论文 5.5/5.6 一致，不得删）

1. **约束满足是投影构造的**：`constraint-satisfaction`={{metric:EXP-0007:constraint-satisfaction}} 由对 7 个缺陷化合物做阈值投影达成
   （`outputs.defectCounts.clippedPerCompound` 记录每列被裁剪行数）；同一生成器未投影时只有
   {{metric:EXP-0007:constraint-satisfaction-unconstrained}}，与真实基率 {{metric:EXP-0007:real_sample_constraint_satisfaction}} 同量级。
   真正的质量证据是同一实验内投影前后的对照（能量距离 {{metric:EXP-0007:energy-distance-unconstrained}} → {{metric:EXP-0007:energy-distance}}，几乎不变）。
2. **跨实验不可比**：基线 `EXP-0006` 的 `energy-distance`（{{metric:EXP-0006:energy-distance}}）与候选的
   {{metric:EXP-0007:energy-distance}} 参考集/生成目标不同（全局池 vs 3 个 held-out 风格），不能当"变好/变差"的因果结论。
3. **不恶化 ≠ 达标**：迁移后约束满足率 {{metric:EXP-0007:transfer-satisfaction-constrained}}、源谱 {{metric:EXP-0007:transfer-satisfaction-source}}，
   两者同为 0；Pils/Lager 源谱本身就不满足 7 条约束，迁移后仍不满足，只能说明"没有变得更差"。
4. **真实基率参照**：250 个真实样本 {{metric:EXP-0007:real_sample_constraint_satisfaction}}（6/250）、
   留出风格 49 个真实样本 {{metric:EXP-0007:heldout-real-base-rate}}（0/49）；7 项约束同时成立在真实啤酒中本就罕见。
