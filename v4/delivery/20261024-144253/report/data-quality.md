# 数据质量与尺度核对报告（Q1/Q2/Q3 共用）

> 本文件由数据工程师（data-engineer）撰写，是论文"数据处理/数据质量"章节与 limitations 的唯一数据侧依据。
> 全部数字均由 `src/00_prepare_q1q2.py` 与 `src/00_prepare_q3.py` 实际计算并写入
> `data/processed/data_quality.json`、`data/processed/q3_thresholds.json`；论文引用时请附这两个文件的路径，
> 不要手工抄写或再计算。台账 id 见第 1 节。
>
> **三条红线（写作时请直接引用）**
> 1. Q1 只能叫 **mapped grade（映射分级，非原始 0–6）**；原始 0–6 不可还原。
> 2. 2/5/6/7 与 2.csv 都是**同一批 250 个样本的派生相关/派生评分**，不是独立外部数据，不能作外部验证。
> 3. `trans-2-nonenal` 与 `Stale hops` 在本附件中**没有数值阈值**，Q3 只能把它们写成 limitation，不得编阈值。

---

## 1. 台账绑定：导入的文件、三个数据版本、三个划分

原始附件（`modeling_data import`，`data/raw/` 原件未被修改，导入副本在 `data/raw/imported/`）：

| 文件 | 台账 id | role | 字节 | sha256（前 12 位） |
|---|---|---|---|---|
| 1.csv | RAW-41984922 | chemical_features | 700705 | 419849227a02 |
| 2.csv | RAW-415709ac | compound_correlation | 1000771 | 415709ac10f2 |
| 3.xlsx | RAW-fe4dcabd | sensory_scorecards | 163364 | fe4dcabd4843 |
| 4.csv | RAW-43a7b386 | sensory_targets | 162887 | 43a7b38682ed |
| 5.csv | RAW-c512eed1 | sensory_correlation | 48044 | c512eed108de |
| 6.csv | RAW-a55004fb | chemical_sensory_correlation | 42937 | a55004fb0390 |
| 7.csv | RAW-2083138d | sensory_descriptors | 588816 | 2083138df466 |
| 8.xlsx | RAW-f2316766 | reference_thresholds | 1740092 | f23167667921 |
| 数据说明.txt | RAW-40813e27 | data_notes | 614 | 40813e273e08 |

三个**互不混用**的数据版本（`register-clean`）：

| id | 文件 | 行列 | sha256 | 用途 |
|---|---|---|---|---|
| DATA-0001 | data/processed/q1_mapped.csv | 250 × 285 | `64651e40fbda83fc70d66fd3164bc0932562da143d0ec1946340ea27c5b5c8ab` | Q1（mapped grade 目标） |
| DATA-0002 | data/processed/q2_raw.csv | 250 × 285 | `cca702e9fb85d001218e1eebeb2c4c4d6bcbf990efd9dafede22217345c260d0` | Q2（4.csv 标准化目标） |
| DATA-0003 | data/processed/q3_table.csv | 250 × 279 | `a89872324f27ede6216242645894fbeee3a90c28d2f0ef5d50e08938242cfad3` | Q3（风格条件 + 阈值） |

三张表的共同部分完全相同：`row, beer, beer_id, tasting_category_fine` + 231 个 `chem__<1.csv 列名>`。
`q3_table.csv` 用 `style, style_holdout` 替代 `tasting_category_fine`，并追加 43 个 `thr__<化合物>` 常数列。
三个化学块逐位相同（脚本内已断言，见 `q3_thresholds.json → crossCheckAgainstQ1Q2Tables`）。

划分（`register-split`，method=`random-holdout`，testFraction=0.2，seed=20261024，`rowIdMapping="positional"`）：

| id | dataset | 行数 | train/test | assignment.csv sha256 |
|---|---|---|---|---|
| SPLIT-0001 | DATA-0001 | 250 | 200 / 50 | `e3addc6c6dde223279b835a44b9d5b1177636ca3aa06286a35a3c5b0054d473e` |
| SPLIT-0002 | DATA-0002 | 250 | 200 / 50 | 同上（同一 250 行，同一 seed） |
| SPLIT-0003 | DATA-0003 | 250 | 200 / 50 | 同上 |

- 训练/测试行与 `data/processed/q1_split_rows.json` **逐行完全相同**，也与 `split.py` 的实现
  `np.random.default_rng(20261024).permutation(250)` 取前 `int(round(250×0.2))=50` 个再排序完全一致
  （test 行：0,1,2,9,14,26,28,33,34,36,40,56,61,64,65,69,70,74,75,86,96,97,110,111,112,116,120,137,144,149,159,164,169,172,181,185,191,192,194,196,199,203,204,207,216,219,224,227,230,231）。
- **跨风格迁移不用这三个随机划分**：Q3 的风格 held-out 由数据列 `style_holdout` 表达（Tripel/Kriek/Lambic = 49 行 `heldout_style`，其余 201 行 `train_style`）。SPLIT-0003 只服务于"无条件/全局基线"。
- 复现说明：`data/processed/q1_mapped.csv`/`q2_raw.csv` 的当前字节由 `SCRIPT-0003` 生成，`q3_table.csv` 由 `SCRIPT-0001`/`SCRIPT-0004` 生成（两次运行字节相同）。登记时的 `cleaningScript.sha256` 指向首版脚本（`00_prepare_q1q2.py` 4f6b8e70…、`00_prepare_q3.py` 9f2f2126…）；此后脚本只增加了"缺陷阈值集裁决"的记录段落，**CSV 产物 sha256 未变**（SCRIPT-0003/SCRIPT-0004 在台账中可查）。见第 11 节。

---

## 2. 行对齐与主键：只能用行位置，不能用 beer_id

- 1.csv = 250 × 234，4.csv = 250 × 53，8.xlsx "Calibrated chemical dataset" = 250 × 73。三者 `beer` 列
  **逐行完全相同**（同一置换），1.csv/4.csv 的 `tasting_category_fine` **100% 相同**（22 个风格）。
- `beer` 是 1..250 的一个**置换**，不是行号（第 0 行 beer=10，第 1 行 beer=86）。所以"第 3 行"和"beer 3"不是同一款酒；
  本项目的划分与所有合并都用 **0 基行位置 `row`**。
- **beer_id 被数值截断**：1.csv 有 250 个不同 beer_id（13 位 EAN 类），4.csv **只剩 96 个不同值**
  （例：`5413970150111` → `5413970000000.0`），而且**一个 4.csv beer_id 最多对应 20 款不同的酒**。
  → `beer_id` 绝不能作为连接键；论文中若提到 250 个样本的合并，必须写明"按行位置合并"。
  7.csv 同样是 96 个不同 beer_id、且 beer 顺序与 1.csv 一致。
- 结论：**跨表合并唯一合法键 = 行位置**（等价合法键是 `beer`，但不能用 `beer_id`）。

---

## 3. 1.csv 的混合尺度：逐列判定，禁止统一取 log 或统一当原始浓度

231 个化学/理化列的最终判决（`data_quality.json → scaleAudit`，逐列证据在 `perColumnCheck`）：

| 类别 | 列数 | 判定依据 |
|---|---|---|
| log10 变换 | 196 | 负值不可能出现在原始浓度中；且 35 列与 8.xlsx Calibrated 原始浓度满足 `value ≡ log10(raw)`（中位误差 ≤5e-10） |
| 零值底限编码的 log10 | 2（`CS2`, `X4VG`） | 对应 Calibrated 原始值在 ≥50% 样本上恰为 0（CS2 209/250、X4VG 168/250），1.csv 用一个恒定底限代替（CS2 = −2.146292、X4VG = −2.013157），该值不代表浓度 |
| 原始浓度 | 33 | 与 Calibrated 原始浓度逐位相等（中位误差 <1e-6） |
| 合计 | 231 | 196 + 2 + 33 |

**判定方法（可复算）**：对同时出现在 8.xlsx "Calibrated chemical dataset" 的 70 列，分别按
"1.csv = 原始浓度" 与 "1.csv = log10(原始浓度)" 两个假设计算中位绝对误差，取误差更小者（最差列的中位误差 5e-10，
两假设间差距通常 3 个数量级以上）；对其余 161 列，用"负值 ⇒ 必然经过对数变换"以及同族列一致性判定，并在
`perColumnCheck[*].confidence` 标注 `high`/`medium`：其中 **145 列由负值直接证明（high）**，**16 列无负值、判定为
`medium`**（`n.pentanol`、`n.heptanol`、`n.octanol`、`X2.methyl.1.butanol`、`isopentyl.formate`、`X3.methyl.2.butenal`、
`X3.methyl.2.hexanol`、`X3.furanmethanol`、`terpinolene`、`nonan.2.ol`、`isoborneol`、`ethyl.benzoate`、
`X.E..beta.ionone`、`ethyl.hex..3E..enoate`、`trans.dihydro.alpha.terpinyl.acetate`、以及派生汇总列 `aroma_hops_sum`）——
它们与同族列同属 log10 空间（同族列带 −1.8178 底限），但本附件无法给出绝对证明，论文如引用请注明这一置信度。
70 列可对齐列的分布 = 35 log10 + 2 零值底限 + 33 原始浓度。

**题面与数据矛盾（必须在论文中如实报告）**：题面说部分理化参数"保留原始量纲"，
但实测证据显示它们**已经被取过 log10**：

| 列 | 1.csv 实测范围 | 等于 log10 的 Calibrated 原始值范围 | 单位（阈值表） |
|---|---|---|---|
| `pH` | 0.5705 – 0.6744 | 3.72 – 4.73 | — |
| `color.EBC.` | 0.6532 – 2.4762 | 4.50 – 299.35 | EBC |
| `bitterness` | −1.1442 – 1.7941 | 0 – 62.25 | IBU |
| `ethanol..v.v.` | −1.4559 – 1.0660 | 0 – 11.64 | %v/v |
| `CO2.PSI.` | −0.2310 – 0.7076 | 1.175 – 5.10 | PSI |

五列都满足 `1.csv 值 = log10(Calibrated 原始值)`（误差 <1e-9，pH 的 0.6139 = log10(4.11) 即为酒类 pH 的常识范围）。
**结论：以数据为准，题面这句话不成立；论文写"经实测，这些理化列同样是 log10 变换值"，并给出上表。**
附带说明：另有 4 个派生汇总列（`esters_sum`、`aroma_hops_sum`、`acids_sum`、`sulfur_sum`）取值落在对数空间
（`kcalperc` 已精确验证为 log10(千卡)），故按 log10 空间处理；它们是"由多个化合物计算得出"的派生量，不是独立测量。

---

## 4. 缺失值与填补规则（只用训练行统计量）

- 1.csv 仅有 **9 列 73 个缺失单元格**：

| 列 | 缺失数 | 列 | 缺失数 |
|---|---|---|---|
| `amyl.acetate` | 27 | `X2.3.butanedione` | 9 |
| `aroma_hops_sum` | 13 | `X3.methylbutanal` | 7 |
| `methylpyrazine` | 12 | `ethyl.nicotinate` | 2 |
| `ethyl.isobutyrate` | 1 | `furfural` | 1 |
| `phenylacetaldehyde` | 1 | | |

- 规则（显式、可复算）：对每一列，用 **seed 20261024 划分的 200 个训练行**的中位数填补；测试行从不参与计算填补值
  （测试行中位数仅作诊断记录在 `data_quality.json → missingHandling.perColumn`）。
  中位数先算、再填补，因此净化后的值不会进入 `zmin/zmax` 估计。
- **4.csv 完全无缺失**，所以 Q1/Q2 的 50 个目标列在任何情况下都不会被填补，也不存在用测试目标统计量的问题。
- 产物保真性（脚本内断言）：57677 个非缺失 `chem__` 单元格写出 CSV 再读回**逐位相同**；无单元格被写成 NaN；
  Q2 目标块与 4.csv **逐位相同**。Q1 目标块按 12 位有效数字写出（4.csv 本身约 10 位有效数字），写后四舍五入损失实测为 0.0。

---

## 5. Q1 目标：mapped grade，非原始 0–6

**公式**：`x = 6·(z − zmin)/(zmax − zmin)`，其中 `z` = 4.csv 原值（标准化/中心化的连续值），
`zmin/zmax` **只用 200 个训练行**估计（`fittedOn: "train-only"`，逐目标参数见
`data_quality.json → mappedGrade.perTarget`）。

- 端点：训练行按构造精确落在 [0,6]（zmin→0，zmax→6）。全表 96 个单元格恰为 0、52 个恰为 6。
- **越界 15 个单元格（7 个 <0，8 个 >6），不裁剪**（容差 1e-9；若按严格比较会多出 2 个 1e-16 级的浮点边界假阳性，已分开记录）：

| 目标 | row | 映射值 | 目标 | row | 映射值 |
|---|---|---|---|---|---|
| F_malt_grain | 231 | −0.4680（最小） | t2n | 36 | 7.2651 |
| bitternes | 0 | −0.2414 | stale_hops | 159 | 7.5677 |
| F_hops_noble | 0 | −0.1413 | barnyard | 159 | 7.5820 |
| A_hops_noble | 0, 2 | −0.0803 | acetic | 149 | 6.8198 |
| acidity | 2, 231 | −0.0348 | coriander | 227 | 9.7499（最大） |
| A_malt_grain | 1 | 6.3112 | orange | 0 | 6.4268 |
| F_hops_tropical | 14 | 6.3187 | | | |

  15 格全部落在**测试行**（训练行不可能越界）；原因是这些测试样本的 z 超出了训练集 z 的范围（4.csv 为标准化值，本身不受 0–6 约束）。
  保留原始线性映射、不裁剪，是为了让评估看到真实映射而不是被静默饱和的标签。
- 常数列策略：若某目标在训练行上 `zmax == zmin`，线性映射无定义，脚本对该目标全表写 3.0（0–6 中点）并在
  `perTarget.constantColumn` 标注。**本数据集中 0 个目标触发**。
- **原始 0–6 不可还原的三条证据**：(a) 3.xlsx 的 12 张评分卡是空白模板（见第 8 节），无法提供原始评级；
  (b) 4.csv 的标准化参数（均值/标准差或中心化方式）附件中没有任何记录，无法反解；
  (c) `clove` 的训练 zmax = 6.1724 > 6，`alcohol` 的 zmin = −2.1507，说明 z 不是 0–6 离散等级本身。
  → 论文只能写"mapped grade，0–6 名义区间、非原始评分"，且 50 个目标的训练 zmin 全为负、zmax 仅 clove 一个超过 6。

---

## 6. Q2 的目标与 4.csv 的关系

`DATA-0002` 的 50 个目标列 = 4.csv 原值，**不做任何变换**（逐位相同）。它们是"标准化/中心化后的感官结果"，
不是原始 0–6（同上证据）。Q2 的结论必须写成"同期关联"，不得写成因果；目标列是标准化连续值，故 Q2 的
Top-3 与贡献分析都是**标准化尺度上的关联强度**，不是"分数上升 1 分"的效应。

---

## 7. 派生相关矩阵：2/5/6/7 同源，不能当外部验证

| 文件 | 实际形状 | 内容 | 实测证据 |
|---|---|---|---|
| 2.csv | 231 × 232（含 1 个行标签列；矩阵 231×231，行列标签相同） | 化学-化学相关 | **是 Spearman，不是 Pearson**：用 1.csv 重算 Spearman，与 2.csv 的 26565 个对上 **max\|Δ\| = 6.66e-16**；与 Pearson 相比 **16.94%** 的单元格符号相反。**非 PSD**：最小特征值 **−0.0424**（最大 33.45），做矩阵运算前需说明或做 PSD 投影 |
| 5.csv | 50 × 50 | 感官-感官相关 | 对角元全为 1，标签是感官名（与 4.csv 列名不同写法，需经 8.xlsx "Sensory names" 映射） |
| 6.csv | **44 × 50**（原文件 44 行 × 51 列，首列为行标签） | 化学×感官交叉相关 | 44 行是化学物（英文名，可 44/44 解析回 1.csv 列）；50 列是感官属性（49/50 与 8.xlsx `CleanName_Paper` 精确匹配，剩 1 个是含换行的 `Overall appreciation\r\n(Trained panel)`，仍是同一感官维度）。**题面说 46×50，实际是 44×50（差 2 行）——以实测为准** |
| 7.csv | 250 × 189 | 250 个样本的感官描述符 | 62 个 `aroma_*` + 62 个 `palate_*` + 62 个 `taste_*` + 3 列元数据；其中 `palate_acetaldehyde`、`palate_acetate`、`palate_dentist` **三列 250 行全为 NA**（共 750 个空格）；beer 顺序与 1.csv 完全一致 |

- 2.csv 的 231 个标签可用 8.xlsx "Sensory thresholds" 的 `chemical_name → field_name_R` 映射**全部 231/231** 解析回 1.csv 列名（希腊字母 α/β 需先归一化，另有 2 个 mojibake 字符需修复）。
- 5/6/7 都是**同一批 250 个样本**的派生结果；它们可以提供"结构一致性"的描述性证据，但**不能作为独立外部验证集**，
  也不能当作与 1.csv/4.csv 相互独立的先验。数据说明.txt 把 7.csv 说成"论坛评论数据"，实际它是同批 250 样本的
  标准化感官描述符（与 4.csv 同一批样本、beer 顺序一致），**说明文字与内容不符，以实测为准**。

---

## 8. 3.xlsx：12 张空白评分卡 + summary 全 0 + 公式共用单元格

- 13 个 sheet：`beer_1 … beer_12`（12 张人工评分卡）+ `summary`。
- **12 张评分卡都是空白模板**：卡片里唯一的非零数字是 0–6 评分刻度的**列标题**（芳香列 E/G/I/K/M/O = 1/2/3/4/5/6，
  风味列 U/W/Y/AA/AC/AE = 1/2/3/4/5/6）和少量 0/1 勾选标记；真正的评分列 **Q 列与 AG 列在所有 12 张卡上全为 0**
  （评分格子为空，公式 `=IF(ISBLANK(...),0,...)` 求值为 0）。
- `summary`：52 列（`Beer` + 50 个目标列 + `comments`）、13 行（表头 + Beer# 1..12）。
  每格都是 `=beer_1!$Q$7` 这类**跨表引用**：**612 个公式单元格 = 51 列（B..AZ，即 50 个目标列 + `comments`）× 12 行**，
  `data_only` 求值后 **612 个全部为 0**（数值单元格也是 612 个、也全为 0）。
  口径说明：若只统计 B..AX（49 列）会得到 588，那是漏掉 `overall`(AY) 与 `comments`(AZ) 两列的结果；
  正确计数是 51 列 × 12 行 = 612（`AZ` 列的 `comments` 也不是文本而是 `=beer_1!$S$93` 这样的引用公式）。
  且 summary 只覆盖 **12 款酒**（beer_1..beer_12），而 4.csv 有 250 个样本。
- **公式误引（已实测确认）**：50 个目标引用 50 个卡片单元格，其中 **`stale_hops` 与 `barnyard` 共用同一个单元格
  `beer_x!AG76`**，而该单元格在卡片上的标签是 "Stale hops (cheesy, roquefort)"，即 **`barnyard` 被错误地指向了
  stale hops 的评分位**（其余 48 个引用与卡片标签一一对应）。
- 结论：3.xlsx 既不能作为 Q1 的标签来源（空白），也不能作为校验集（全 0，且只覆盖 12 款酒）。
  **以 4.csv 为权威标签**；3.xlsx 仅用于说明"50 个目标列的语义/量表定义"（`problem/targetcolumns.csv` 已把
  目标列 ↔ 卡片属性 ↔ summary 单元格的对应关系固化）。原始 3.xlsx 未被修改，上述差异只记录在此。

---

## 9. 8.xlsx：可用的只有"阈值"和"名称"，其余三张表要么禁用要么只作核对

| sheet | 实际形状 | 本项目如何使用 |
|---|---|---|
| Sensory thresholds | 261 行 × 11 列 | **唯一阈值来源**：43 行有数值阈值（`threshold_mean`/`threshold_median` 各 43 个非空）、7 行有 `off_flavors` 标记（6 行与阈值重叠）。详见第 10 节 |
| Sensory names | 101 行 × 8 列（50 Trained + 51 Ratebeer） | 仅用于把 5/6.csv 的感官列名映射到 4.csv 目标列（`CleanName_*` ↔ `R_name`） |
| GBM importance MDI | 231 行 × 2 列 | **禁止作输入特征**：它是在这同一批 250 个样本上拟合出的模型输出（MDI 重要性），当作特征即目标泄漏 |
| GBM SHAP Values | 500 行 × 235 列 | **禁止作输入特征**：同上，是同一批样本的 SHAP 分解结果 |
| Calibrated chemical dataset | 250 行 × 73 列（3 元数据 + 70 化合物原始浓度） | **只用于核对尺度**（第 3 节的 70 列判定）。不作特征、不作填补来源、不作划分来源 |
| Beer Prices | 250 行 × 11 列 | **不作核心输入**：7 个价格列缺失严重（`Price_BeerHawk_UK` 204/250 缺失、`Price_Colruyt_Belgium` 170、`Price_TotalWine_USA` 164、`Price_Delhaize_Belgium` 159、`Price_TheBelgianBeerShop_global` 156、`Price_BeerOfBelgium_global` 109、`Price_TheBelgianShop_global` 43），21 款酒 7 个价格全缺；价格不能解释化合物谱 |
| Sheet2 | 空表 | 忽略 |

**Calibrated 与 1.csv 的一致性核对（只作核对记录，不影响任何尺度判决）**：70 个可对齐列中，每列都可用**单一**
变换假设与 1.csv 精确对齐（最差列的中位误差 5e-10）；但存在 **73 个单元格差 >1e-3**、分布在 **30 个列**上，
其中最集中的一行是 **row 105 / beer 177**：`n.hexanol`（1.csv 0.2427 vs Calibrated 8.9124）、`Z.nerolidol`
（0.00787 vs 10.0088）、`X3Z.hexenol`（0.0563 vs 2.3226）三个化合物不一致，另有若干单元格在两侧互为 NaN。
这些是 Calibrated 表自身的录入瑕疵，`n.hexanol`/`Z.nerolidol` 的其它 249 行与 1.csv 逐位一致，因此**列的尺度判决不受影响**。
另外 Calibrated 自身有两列出现负的"原始浓度"（`betaglucan.mg.L.` min −2.0、`unfermentables` min −16.755），
进一步说明它不能当原始浓度真值使用。

---

## 10. 阈值解析与 Q3 缺陷集裁决（数据层的决定，已写入 `data_quality.json → defectThresholdPolicy`）

**解析结果（真实、可复算）**：8.xlsx "Sensory thresholds" 261 行 → **43 行有数值阈值**、**7 行有异味标记**
（`acetaldehyde`、`X2.3.butanedione`=Diacetyl、`DES`、`DMS`、`H2S`、`MeSH`、`SO2.mg.L.`）。其余 218 行只有化合物名、没有阈值，
**没有编造任何阈值**。

**列名匹配**：用 `field_name_R`（R 风格名，如 `X2.3.butanedione`、`acetic_acid.g.L.`）与 1.csv 列名匹配，
**43/43 精确命中**；`field_name_python`（人读名，如 `2,3-butanedione`）只 18/43 精确、归一化后 39/43；
`chemical_name`（如 `Diacetyl`）归一化后只 24/43。匹配前修复了 2 个 mojibake 字符（`Î±`/`Î²` = alpha/beta）。
→ 论文说明"阈值表用 R 风格列名可 1:1 对齐 1.csv，共 43 个化合物有真实阈值"。

**缺陷集裁决（7 个，这是 Q3 唯一的缺陷判定依据）**：

| Q3 列 | 化合物 | 阈值（threshold_mean） | 单位 | 阈值中位数 | 异味标记 |
|---|---|---|---|---|---|
| `thr__DMS` | Dimethyl sulfide | 17.25 | ug/L | 19.0 | cooked vegetables, onion, garlic, corn… |
| `thr__X2.3.butanedione` | Diacetyl | 0.29925 | mg/L | 0.09 | butterscotch, popcorn, oily, milky |
| `thr__X4VG` | 4-vinylguaiacol | 0.206333 | mg/L | 0.2 | — |
| `thr__acetaldehyde` | Acetaldehyde | 50.0 | mg/L | 50.0 | pungent, rotten-apples, green apple |
| `thr__DES` | Diethyl sulfide | 1.2 | ug/L | 1.2 | rotting vegetables |
| `thr__H2S` | Hydrogen sulfide | 3.5 | ug/L | 3.5 | sulfidic, rotten eggs |
| `thr__SO2.mg.L.` | Sulfur dioxide | 15.333333 | mg/L | 11.0 | Burnt matches |

**不可评估（2 个，必须写成 limitation，不得编阈值）**：

| 题面点名 | 实际情况 |
|---|---|
| `trans-2-nonenal` | 化合物存在（1.csv `X.E..2.nonenal`，阈值表 `(E)-2-nonenal`，单位 mg/L），但**阈值表该行的 `threshold_mean` 与 `threshold_median` 都是空**，因此无法给出缺陷阈值 |
| `Stale hops` | **阈值表里根本没有这个化合物**（它是感官描述符：4.csv 目标 `stale_hops`、7.csv `stale_*` 列），没有对应浓度，无法定义阈值 |

**其余 36 个阈值列 = "典型/检出水平"参考，不得当缺陷阈值**。这条必须遵守：例如 `bitterness` 阈值 5 IBU
（86.4% 样本超过）、`ethanol..v.v.` 阈值 1.757 %v/v（97.6% 超过）、`protein.g.L.` 阈值 1.024 g/L（99.6% 超过）、
`linalool` 阈值 0.027 mg/L（98.4% 超过）——这些是"正常范围/检出水平"，不是缺陷。它们仍保留在
`q3_table.csv` 的 43 个 `thr__` 列中，论文可把它们作为"典型浓度参考"引用，但**不得**说成"超阈值=缺陷"。

**单位与尺度的使用前提**：1.csv 不携带任何单位；上表的单位是**阈值表自己的单位**。要算 OAV，必须
(a) 按第 3 节的尺度把 `chem__` 值还原成原始浓度（log10/零值底限列取 `10^x`），(b) 假定该化合物在 1.csv 中的浓度
单位与阈值单位一致（这是**假设**，不是已验证事实，`q3_thresholds.json → exceedanceCheck.assumedConcentrationUnit`
逐列写明）。该假设的合理性证据：按此假设，题面点名的缺陷化合物超阈值比例是 DMS 0.672、Diacetyl 0.448、4VG 0.064，
而 `acetaldehyde` 0.000、`CS2` 0.000（阈值远高于实测范围）——数量级自洽；反之若单位错位，这些比例会整体偏移数个量级。

---

## 11. 复现说明与产物清单

| 产物 | 生成者 | 台账证据 | sha256 |
|---|---|---|---|
| data/processed/q1_mapped.csv | `src/00_prepare_q1q2.py` | SCRIPT-0001（首版）/ SCRIPT-0003（当前） | `64651e40…` |
| data/processed/q2_raw.csv | 同上 | 同上 | `cca702e9…` |
| data/processed/q1_split_rows.json | 同上 | 同上 | `a2f2c5b7…` |
| data/processed/data_quality.json | 同上 | SCRIPT-0005（当前版本，含缺陷集裁决） | `249dc17c…` |
| data/fieldlists/q1_mapped_fields.json | 同上（285 字段） | 同上 | `4c86baff…` |
| data/fieldlists/q2_raw_fields.json | 同上（285 字段） | 同上 | `7c92da7d…` |
| data/processed/q3_table.csv | `src/00_prepare_q3.py` | SCRIPT-0002 / SCRIPT-0004（当前） | `a8987232…` |
| data/processed/q3_thresholds.json | 同上 | SCRIPT-0004（当前，含缺陷集消费校验） | `cce0f452…` |
| data/fieldlists/q3_table_fields.json | 同上（279 字段） | 同上 | `6298a718…` |

- 运行方式：`modeling_data {action:"run-script", script:"src/00_prepare_q1q2.py"}` 与 `…"src/00_prepare_q3.py"`，
  退出码均为 0（SCRIPT-0001/0002/0003/0004/0005，stdout 存于 `state/scripts/<id>/stdout.log`）。
- 确定性：脚本只依赖附件与 `problem/targetcolumns.csv`（4 个输入文件 sha256 记录在 `data_quality.json → inputs`），
  无随机数（唯一的随机性是划分本身，seed 固定），报告 JSON 不含时间戳。同一脚本重跑产物 sha256 不变
  （唯一例外是报告 JSON 内嵌的输出路径，用 `--out-*` 改路径时该字段随之变化，属预期）。
- **脚本版本与登记版本的说明**：`DATA-0001/0002` 登记的 `cleaningScript.sha256` 是首版脚本（4f6b8e70…），
  当前脚本为 `6f0a1d12…`；`DATA-0003` 登记的是 9f2f2126…，当前为 `9f3d5c6b…`。两次改动都只涉及 QA 报告的内容
  （把第 10 节的缺陷集裁决写进 `data_quality.json` / `q3_thresholds.json`、以及修正一处字符串里的 `%%`），
  **三张 CSV 的 sha256 在所有运行中完全相同**，可由 SCRIPT-0001/0002/0003/0004/0005 的 outputs 记录交叉验证。
  因此数据本身可复现，差异只在 QA 报告的登记版本。
- 原始附件未被覆盖：`data/raw/*` 与导入副本 `data/raw/imported/*` 的 sha256 与第 1 节一致。

---

## 12. 给论文的限制句（可直接引用，勿改写数值）

1. **Q1**：4.csv 的 50 个感官列是标准化/中心化后的连续值，原始 0–6 评分不可还原（3.xlsx 评分为空白模板、
   summary 全 0 且只覆盖 12 款酒、标准化参数缺失、`clove` 的 z 达 6.17）；本文交付的是**映射分级（mapped grade）**，
   `x = 6(z−zmin)/(zmax−zmin)`，映射参数仅用 200 个训练样本估计，训练样本精确落在 [0,6]，全表 15 个测试单元格越界且未裁剪。
2. **尺度**：1.csv 的 231 个化学/理化列不是同一尺度——196 列为 log10 变换、2 列（CS2/4VG）为零值底限编码、
   33 列为原始浓度；`pH/color/bitterness/ethanol/CO2` 实测也是 log10（与题面"保留原始量纲"的说法不符，以数据为准）。
3. **主键**：250 个样本只能按行位置（或 beer）合并；4.csv/7.csv 的 `beer_id` 被数值截断为 96 个不同值，一个 id 最多对应 20 款酒。
4. **同源**：2.csv 是 1.csv 的 Spearman 矩阵（重算 max\|Δ\|=6.66e-16，非 PSD，min eig=−0.0424），5/6/7 是同一批
   250 样本的派生结果，均**不是独立外部数据**，不构成外部验证。
5. **3.xlsx / 8.xlsx**：3.xlsx 的 12 张评分卡为空白模板、summary 全 0 且 `barnyard` 与 `stale_hops` 共用单元格 AG76
   （公式误引）；8.xlsx 的 GBM MDI/SHAP 是同一批样本的模型输出，禁止作输入特征；Prices 缺失严重不作核心输入；
   Calibrated 仅用于尺度核对。
6. **Q3 缺陷约束**：只对 7 个有真实阈值的化合物（DMS、Diacetyl、4VG、acetaldehyde、DES、H2S、SO2）成立；
   `trans-2-nonenal` 与 `Stale hops` 在本附件中无数值阈值，其缺陷约束**不可评估**；其余 36 个阈值只是典型浓度参考，
   不能用来判定缺陷。Q3 的生成结果属于"约束满足/生成合理性"，不是真实酿造验证。

---

## 13. 稳健性评估池（unexposed evaluation pools）

**为什么需要**：主划分 SPLIT-0001/0002/0003 的测试行已经用满了 holdout 曝光上限（每个实际样本最多被 3 次实验当作
测试行），而任何与它们重叠的新划分都会被拒绝（"holdout exposure limit reached"）。因此稳健性实验不能再用主划分，
也不能用与主划分共享测试行的新 seed 划分；它的**测试行必须来自从未进入过任何主划分测试集的样本**。
为此构建三个"评估池"：主数据集去掉主划分测试行后剩下的 200 行。

**构造规则（只做行子集，不做任何重算）**：
池 = 父数据集 250 行 − 主划分 test 的 50 行（按 `assignment.csv` 的 `row_index`）；
保留父文件行序；**`row` 列保存原始 0 基编号，不重新编号**（所以缺口就是主划分测试行，任一池行都能按 `row` 回到同一款酒）；
列集合与父数据集完全一致；**所有数值逐位不变**，特别地 q1_pool 的 50 个 mapped grade 目标列与 q1_mapped 完全相同
（未用池重新估计 zmin/zmax —— 若重估就等于改标签）。

| 数据集 | 池文件 | 行×列 | sha256 | 父数据集 | 主划分 | 划分 |
|---|---|---|---|---|---|---|
| DATA-0004 | data/processed/q1_pool.csv | 200×285 | `52129428f0348591a46036b1da01894097bc2c616f8eb9907b175f6b46288487` | DATA-0001 | SPLIT-0001 | SPLIT-0008(seed 20261025)、SPLIT-0009(seed 20261026) |
| DATA-0005 | data/processed/q2_pool.csv | 200×285 | `d00925b8264d5a36d8ffa042277dafc75874647b6764fb7e9e9050ef3355d7ee` | DATA-0002 | SPLIT-0002 | SPLIT-0010(20261025)、SPLIT-0011(20261026) |
| DATA-0006 | data/processed/q3_pool.csv | 200×279 | `06d8ee5f4c4a22e8c2861a3e06eb39b1135684231615fb02930e16a9b007bc2d` | DATA-0003 | SPLIT-0003 | SPLIT-0012(20261025)、SPLIT-0013(20261026) |

生成脚本 `src/00_prepare_pools.py`（SCRIPT-0006，exit 0），全部断言记录在 `data/processed/pools_quality.json`。

**核验结果（实测，非声明）**
1. 三个池都是 200 行，且 `row` 集合**恰好等于**父数据集 250 行减去对应主划分的 50 个测试行（集合相等）；`row` 取值 3–249，行序保持父文件顺序。
2. 六个新划分都是 200 行 → **160 train / 40 test**，且 test 行集合等于 `default_rng(seed).permutation(200)` 前 40 个（逐一复核通过）；`rowIdMapping="positional"`。
3. 六个新划分的 test 行（按原始 `row` 值）与对应主划分 test 行的**交集均为 0**（这是评估池的全部意义）。
4. q1_pool 的 50 个目标列与 q1_mapped 对应行**逐位相同**（10000 个单元格 max|diff| = 0.0）。
5. q3_pool 的 `style_holdout`：160 train_style + 40 heldout_style；held-out 三风格 Tripel 23 / Kriek 8 / Lambic 9
   （主划分测试集带走了 5 个 Tripel、2 个 Kriek、2 个 Lambic），22 个风格一个都没被清空，Q3 扰动仍可按 `style_holdout` 拟合。
6. holdout 曝光审计（用与 pack 相同的行内容哈希复核）：q1_pool / q3_pool 的 40 个测试行当前曝光均为 0；
   q2_pool 两个划分的测试行中分别有 8 / 10 行当前曝光 = 1（来自 Q2 第一次扰动 EXP-0010），再跑一次只会到 2，
   仍低于上限 3，因此**六次稳健性运行都不会被 holdout 门拒绝**（各自只跑一次的前提下）。

**必须写进限制的三点**
- **仿射重标度弱泄漏**：q1_pool 的 200 行正是估计主划分 zmin/zmax 的那 200 行，因此池内每一行都参与过标度估计；
  泄漏只经"每目标 2 个标量"传递，不涉及单样本信息，但结论只能表述为"同一组仿射参数下的重标度标签"，
  池上算出的误差与主划分的误差不可直接混比（另见第 5 节的映射公式与端点说明）。
- **同一池的两个 seed 划分并不独立**：SPLIT-0008 与 SPLIT-0009 的测试集互有 3 行重叠（200 行抽两个 40 行子集），
  两个 seed 的稳健性结果是同一池上的重复划分，不是两次独立重采样。
- **三个池共用同一批 200 行**（同一父行序），因此同一 seed 下 Q1/Q2/Q3 的稳健性划分是**同一组行划分**
  （只是挂在三个列集不同的数据集上），不能声称三问各自独立重采样。

> 论文表述建议："Q1/Q2/Q3 各保留 1 个主划分用于最终评估；稳健性检验使用预注册的新 seed 划分
> （20261025 / 20261026），并把测试行限制在从未进入主划分测试集的评估池内，防止同一 holdout 被反复使用。"

### 13.1 Q1 追加划分（SPLIT-0014 / 0015 / 0016，DATA-0004）与 seed 选择口径

主划分与评估池用了几轮之后，Q1 还需要 3 个"测试行不含已耗尽曝光样本"的划分（1 个给池上 baseline，
2 个给去混杂稳健性）。**曝光门按样本行内容累计、上限 3**，而 SPLIT-0008 与 SPLIT-0009 的测试集交集那 3 行
（原始 `row` = **62 / 158 / 236**）已经被用到 3 次——SPLIT-0008 的两条实验（EXP-0015、EXP-0018）各记 1 次、
SPLIT-0009 的一条（EXP-0016）再加 1 次，之后任何包含这 3 行的划分都会被拒。因此：

| splitId | dataset | seed | train/test | assignment sha256 | test ∩ {62,158,236} |
|---|---|---|---|---|---|
| SPLIT-0014 | DATA-0004 | 20261027 | 160 / 40 | `804219e7ac801974caedbe98070eca2f7ff8289d51f348e658f03f7c4629c7ca` | **0** |
| SPLIT-0015 | DATA-0004 | 20261046 | 160 / 40 | `2e0939b613b7501747dfe22d5ab5900beeea0682f2640abc73c121f9847faf68` | **0** |
| SPLIT-0016 | DATA-0004 | 20261096 | 160 / 40 | `cb00d58ef61ea2b902628a83c732a25f52f5b27d94815681936faf553ec36dc1` | **0** |

- **seed 选择口径（必须如实引用）**：`register-split` 只能给 seed，不能指定具体行，所以 seed 是从 20261027 起逐个 +1
  试出来的（共试 70 个，落在 20261027 / 20261046 / 20261096）。筛选条件**只看曝光簿记**：
  ① 该 seed 的 40 个测试行不含曝光已达 3 的样本；② 三个新划分合起来，任何一行的累计曝光不超过 3（保证各跑一次都不会被门拒绝）。
  **选择过程没有使用任何实验指标、模型结果或标签信息**——它只用到"哪些行已被当作测试行用过几次"这一元数据。
- 三个划分两两测试集重叠：SPLIT-0014∩0015 = 4 行，SPLIT-0014∩0016 = 7 行，SPLIT-0015∩0016 = 9 行（同一 200 行池上抽三个 40 行子集，重叠是预期内的）。
- 曝光上界核算（与部署版同一复现）：三者各自单跑一次后，池内每行的最大曝光均为 3（不会出现 >3 的行）；
  三个各跑一次合并后最大曝光仍为 3；按 0014→0015→0016 的顺序逐个跑，每次都通过门。
- 因此这 3 个划分**不能**再被重复使用第二次（重叠行会到 4），"每划分每实验只跑一次"必须写进稳健性计划。

### 13.2 Q3 追加划分（SPLIT-0017，DATA-0006）与同一 seed 选择口径

Q3 的第二个去混杂 run 也遇到同型问题：**SPLIT-0012 test ∩ SPLIT-0013 test = {row 62, 158, 236}**，这 3 行在
q3_pool 的行内容上已被 **EXP-0013 + EXP-0014 + EXP-0027** 各记 1 次、累计到 3，因此用 SPLIT-0013 再跑会被
`HOLDOUT_REUSE_UNCONTROLLED` 拒绝（EXP-0028 就是被拒的那条，未 run、零曝光）。为此在 DATA-0006 上追加一个划分：

| splitId | dataset | seed | train/test | assignment sha256 | test ∩ {62,158,236} |
|---|---|---|---|---|---|
| SPLIT-0017 | DATA-0006 | 20261030 | 160 / 40 | `811f9d7876581ee33174ce988ce915483db95e6368c8a68bdd69f5540ecf555b` | **0** |

- 复核：q3_pool 200 行的曝光分布 = 0:123 / 1:37 / 2:37 / 3:3（3 行即上述 hot 集）；SPLIT-0017 的 40 个 test 行
  当前曝光分布 = {0:27, 1:9, 2:4}，跑一次后最大曝光 = **3**，不会被门拒绝。
- 与既有划分的测试集重叠：与 SPLIT-0012 test 重叠 **4 行**、与 SPLIT-0013 test 重叠 **9 行**（同一 200 行池上抽 40 行子集，重叠属预期）。
- **seed=20261030 由曝光簿记确定**：候选 seed 由 modeler 提出，本侧用同一套行内容哈希复现后确认其 test 集合不含
  hot 集；筛选条件只有"不含曝光已达 3 的样本 + 单跑一次后任一行 ≤3"，**未使用任何指标、模型结果或标签信息**。
- 与 §13.1 同理：该划分**只能用一次**（重叠行跑第二次会到 4）。

---

## 14. 已登记的数据缺陷：row id 73 的单点极端离群（不修正，只登记）

这条是 modeler 在 Q1 敏感性实验中发现、本侧在**原始附件上复核确认**的数据事实（脚本 `src/00_prepare_outlier_audit.py`，
台账 SCRIPT-0007，机器可读记录 `data/processed/outlier_audit.json`，sha256 `fbefdad96ec865c6eca5df49514b79c380db1780f67db1b517886f087ee8bdfe`）：

| 项 | 实测值 |
|---|---|
| 列 | `1.csv` 的 `X2.methyltetrahydrofuran.3.one`（已换算入 q1_mapped / q2_raw / q3_table 的 `chem__` 同名列） |
| 行 | **row id 73**（4.csv / 1.csv 第 74 行数据行），`beer = 156` |
| 原始值 | **12596.43287** |
| 该列 median（250 行） | 0.052860078（去掉该点后 0.052685651） |
| 该列次大值 | **76.832805**（row id 105） |
| 离群倍数 | 相对中位数 **约 2.39×10⁵ 倍**（log10 高 5.38 个数量级）；相对次大值 **163.9 倍** |
| 折算到训练集标准化 | 用 SPLIT-0015 的 160 个训练行统计（mean 0.449253、std 2.572235）标准化后 **\|z\| ≈ 4897**；而同一组训练行上 231 个化学列任意一格的最大 \|z\| 只有 **12.6** |

- **不是 pipeline 造成的**：该值在 `data/raw/1.csv` 原件里就是 12596.43287，并且在三个派生数据集里**逐位不变**
  （q1_mapped / q2_raw / q3_table 的 `chem__X2.methyltetrahydrofuran.3.one` 在 row 73 都是 12596.43287）。
  该行在 q1_pool 中仍保留，且它恰是 **SPLIT-0005 与 SPLIT-0015 的 test 行**（`outlier_audit.json → rowId73InTestOfSplits`）。
- **对指标的实际影响（从 EXP-0026 的 predictions.csv 复算，不是估计）**：
  - 该行把线性 Ridge 的预测外推到 **[-123.196, 349.041]** 的 mapped-grade 区间（而该行的真值只有 0.041–6.0）；
    整个 40 行测试集的预测极值区间完全由这一行贡献；
  - 该行的逐行 MAE = **51.54**；其余 39 行的逐行平均 MAE = **0.6911**；于是 40 行平均 MAE 从 **0.691 抬到 1.9624**；
  - 对照：同一模型在 row 73 **不在**测试集的划分上，holdout MAE 是 EXP-0016 = **0.6056**、EXP-0025 = **0.7586**。
- **处置：只登记，不修正**。我们**没有**对本数据做 winsorize、没有删行、没有重新插补、没有改动任何 CSV 数值——
  这是附件的真实性质，掩盖它会让数据质量报告失真。因此 Q1 的任何"稳健性/敏感性"表述都必须二选一：
  (a) 同时报告"含该行"与"剔除该行（仅作敏感性口径）"的指标，或 (b) 改用对离群不敏感的模型（如树模型、秩相关）；
  不得在正文只报剔除后的数字而不说明。论文中该点应作为数据类型缺陷（单点录入级离群）披露，并说明它只在
  row 73 落入测试集时才影响指标（如 SPLIT-0015）。
