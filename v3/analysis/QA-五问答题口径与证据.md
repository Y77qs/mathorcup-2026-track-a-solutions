# 2026 MathorCup 大数据挑战赛 · 赛道 A
# 五处数据口径问题：取证结论、答题口径与论文写法

> 适用对象：本队建模手/数据工程师/论文执笔。
> 结论全部由 `data/raw/` 原始文件重算，**不引用题面数字当事实**；题面只当"待核验的线索"。
> 复现：`analysis/scripts/verify_all.py`（Lead 独立复核）+ `analysis/scripts/{corr_*,sensory_*,ref_*}.py`（三组专项取证）。
> 生成日期：2026-10-24；数据/题面文件哈希见 §0。

---

## 0. 五问速答（先看这一页）

| # | 问题 | 一句话结论 | 论文里必须写的一句 |
|---|---|---|---|
| Q1 | 最终 `targetColumns` 到底几个？ | **50 个**：`Aroma A_*` 15 + `Flavour F_*` 15 + 口感/缺陷/辅料/总体 20。`3.xlsx summary` 也是 50 个数值列 + `comments`；`5.csv` 50×50；`8.xlsx Sensory names` 的 Trained panel 恰好 50 行且与 `4.csv` 列名 50/50 对应 | "题面'约 40 个'为概括误差；经与 3.xlsx summary、4.csv 实际列、8.xlsx Sensory names 三方对齐，实际为 **50 个感官维度**（30 个 Aroma/Flavour + 20 个口感/缺陷/总体）" |
| Q2 | `4.csv` 能不能还原成 0–6 分？ | **不能精确还原**。`3.xlsx` 是**空白评分卡模板**（12 张卡已填写分值=0；`summary` 612 个公式计算结果全 0），没有任何真实 0–6 标签；`4.csv` 是中心化/标准化后的连续值（列均值≈0 但非精确 0、列 sd=0.37–0.86≠1、60.94% 值为负、`clove` 最大 6.17>6）。列原点 `a_j` 与缩放系数从未记录，属**不可识别** | "4.csv 不是原始 0–6 分，而是标准化/中心化后的连续感官强度；本文以标准化连续值为建模目标。若需输出 0–6 分级，只能给出显式声明的**映射分级分（mapped grade，非原始评分）**，并报告映射规则与两套映射的敏感性" |
| Q3 | `2.csv` 是 Pearson 还是 Spearman？ | **实测是 Spearman（成对完整样本秩相关）**：与 `1.csv` 重算 Spearman 的 `max|Δ|=7.8×10⁻¹⁶`（逐元素相关=1.000000）；与 Pearson 的 `max|Δ|=1.1234`，且 16.94% 元素符号相反。题面 P3"皮尔逊"是笔误，`数据说明.txt` 的 Spearman 正确 | "题面正文标注 Pearson、附件说明标注 Spearman；经用 1.csv 重算核验，2.csv 实为 **Spearman 秩相关**（最大绝对误差≈8×10⁻¹⁶），本文按 Spearman 使用，并在此注明题面口径差异" |
| Q4 | `8.xlsx` 到底有哪些 sheet、怎么用？ | 实际 **7 个 sheet**（6 个有内容 + 1 个空 `Sheet2`）：Sensory thresholds（261 行，仅 43 行有阈值）、Sensory names（50 Trained + 51 Ratebeer）、GBM importance MDI（231 特征单列聚合）、GBM SHAP Values（250 SHAP + 250 concentration，单目标未标注）、Calibrated chemical dataset（250×73=3 元数据+70 化合物原始浓度）、Beer Prices（7 渠道价格，1005 个 NA）、Sheet2（空） | "8.xlsx 共 7 个 sheet，按用途分别用于：缺陷化合物阈值/OAV（thresholds）、50 维权威命名（names）、化学可解释性与原始浓度/变换底数核验（calibrated）、外部商业协变量（prices）；MDI/SHAP 为同一批 250 样本上的拟合产物，**只作外部对照、不作输入特征**" |
| Q5 | `3.xlsx` 到底几个 sheet？ | **13 个**：`beer_1`…`beer_12` 共 12 张评分卡 + `summary`。题面 P3 说"10 个 sheet / beer_1~beer_10"已过时；且 12 张卡除 `S3` 的 Beer# 外结构完全相同，都是**空白模板** | "3.xlsx 实际 13 个 sheet（12 张评分卡 beer_1~beer_12 + 1 个 summary），题面'10 个'与文件不符；本文按实际文件保留全部 13 个 sheet，不删不减" |

> **三条纪律**（回答任何"数据长什么样"的问题都适用）：
> 1. 题面/数据说明只是线索，**一切数字以实际文件重算为准**，并在论文"数据核查"小节逐条留痕；
> 2. **不把标准化值称作 0–6 分**；不把空白评分卡当标签；不把同源相关矩阵（5/6.csv）当独立外部先验；
> 3. 跨表合并**用 `beer` 列或行位置**，不要用 `beer_id`（`4.csv`/`7.csv` 的 `beer_id` 已被浮点截断，250 行只剩 96 个不同值）。

---

## 1. 证据基础（题面原文 + 文件事实）

### 1.1 题面 PDF 的逐字口径（3 页，SHA256 `494025cf76c5d47af576927fcf6cd3a073d61db5842d56aaf0ad4da5f4660a78`）

用 macOS PDFKit 独立抽取（`analysis/assets/pdf_text_pdfkit.txt`），关键原文：

| 页 | 原文（节选） | 与数据事实的关系 |
|---|---|---|
| P1 | "附件 1-8 数据是测量了 **226 种不同啤酒**的化学特性……以及 **200 多种**风味化合物" | 实际 250 个样本；231 个特征列（226 个实测/化合物 + 5 个派生属性） |
| P2 | "问题 1……给出 3.xlsx 中定义的 **Aroma 与 Flavour 两套、共约 40 个**感官维度的 **0–6 分制**的分级评分结果" | 实际 50 个维度（A+F 仅 30）；4.csv 非 0–6 原始分 |
| P3 | "表格 2 是化合物相关性矩阵……单元格为**皮尔逊相关系数**" | 实测 Spearman（见 Q3） |
| P3 | "表格 3，4 是感官品评表（目标标签，**10 个 sheet**）……beer_1~beer_10" | 实际 13 个 sheet（12 卡 + summary），见 Q5 |
| P3 | "表格 4.csv 中的数值**不是原始 0–6 分**，而是经过标准化/中心化的连续值" | 与实测一致（但具体标准化参数缺失，见 Q2） |
| P3 | "表格 6……**46 个**化学/理化指标 × **50 个**感官属性的交叉相关矩阵（非方阵，行数 46、列数 50）" | 实测 **44×50** |
| P3 | "表格 7.csv……250 个啤酒样本 × **187 个**感官属性评分" | 实测 **186 个**感官列（250×189 = 3 元数据 + 186） |
| P3 | "表格 8 为一些综合参考数据" | 实际 7 个结构化 sheet，见 Q4 |

`数据说明.txt` 的官方口径：`2.csv` "所有化学参数之间的 **Spearman** 相关系数得分"；`5.csv` 感官参数 Spearman；`6.csv` 化学×感官 Spearman。**与文件实测一致**（Q3）。

### 1.2 文件事实清单

| 文件 | 实际维度（pandas 读入） | 备注 |
|---|---|---|
| `1.csv` | 250 × 234 = 3 元数据 + **231 特征** | 231 = 226 个单独测量/化合物 + 5 个派生属性（`kcalperc`、`esters_sum`、`aroma_hops_sum`、`acids_sum`、`sulfur_sum`）；缺失 73 个，分布 9 列；`beer` 唯一 =1..250 |
| `2.csv` | 231 × 231 | 化合物×化合物相关矩阵，行列名=显示名，与 1.csv 231 列**按位置一一对应** |
| `3.xlsx` | **13 sheets** | `beer_1`…`beer_12`（各 101×33）+ `summary`（13×52） |
| `4.csv` | 250 × 53 = 3 元数据 + **50 感官列** | 无缺失；`beer` 唯一 =1..250 |
| `5.csv` | 50 × 50 | 感官×感官相关矩阵 |
| `6.csv` | **44 × 50**（文件宽 51 = 行名 + 50） | 化学/理化 × 感官交叉相关矩阵 |
| `7.csv` | 250 × 189 = 3 元数据 + **186 感官列** | 其中 3 列全 NA；与 4.csv 同批样本、同 beer 顺序 |
| `8.xlsx` | **7 sheets** | 6 个有内容 + 空 `Sheet2` |

---

## 2. Q1：最终 `targetColumns`＝50 个（不是"约 40"，也不是"盲抄 50"）

### 2.1 三方对齐：为什么是 50 而不是 40

| 证据源 | 感官维度数 | 具体内容 |
|---|---|---|
| `4.csv` 实际列 | **50** | 3 元数据之外：`A_*` 15 + `F_*` 15 + 其余 20 |
| `3.xlsx summary` 表头 | **50 个数值列 + 1 个 `comments` 文本列** | `Beer` + 50 个感官列 + `comments`（A1:AZ1 共 52 列） |
| `5.csv` | **50×50** | 与 `4.csv` 的 50 维按 `8.xlsx` 的 `CleanName_PanelFeedback` 一一对应（含 `overall` 的换行清洗） |
| `8.xlsx 'Sensory names'` | Trained panel **50 行** | `R_name` 与 `4.csv` 50 列 **50/50 完全对应**（这是唯一权威短名映射表） |
| `3.xlsx` 12 张评分卡 | 印有 **51 个属性标签 + Comments** | 多出的 1 个是 `Acetaldehyde`，它**没有**被 summary 引用；summary 取其中 50 个 |

- 题面说 "Aroma 与 Flavour 两套、共约 40 个"：实测 Aroma=15、Flavour=15，两套只有 **30**；加上 20 个口感/缺陷/辅料/总体才是 **50**。
- 50 与 40 的差距不是"四舍五入"：要在 20 个"其他"维度里凭空删 10 个，才能凑出 40，且**没有任何文件依据**说明该删哪 10 个。故 `targetColumns` 取 **50 个全量**。
- 若论文想同时呼应题面，可写"主表 50 维、附注 30（A+F 两套）/20（其他）分层"，但**模型与交付物必须覆盖 50 维**，否则与 `4.csv` 目标集不一致。

### 2.2 50 个列的分组与命名差异（完整清单见附录 A / `analysis/sensory/targetcolumns.csv`）

| 组 | 列数 | 成员 |
|---|---|---|
| Aroma | 15 | `A_malt_all/grain/bread/cara/burn`（5）、`A_hops_all/citrus/tropical/noble/woody`（5）、`A_esters_all/ethac/isoaa/flower/fruity`（5） |
| Flavour | 15 | `F_malt_*`（5）、`F_hops_*`（5）、`F_esters_*`（5） |
| 口感/缺陷/辅料/总体 | 20 | 口感/基本味 7：`body, aftertaste, alcohol, co2, sweetness, acidity, bitternes`；缺陷/野生菌 9：`dms, diacetyl, metallic, stale_hops, t2n, X4vg, lactic, acetic, barnyard`；辅料/辛香 3：`orange, coriander, clove`；总体 1：`overall` |

**命名差异（写论文/合并表时必看）**：

| 4.csv | 3.xlsx summary | 5.csv 长名 | 说明 |
|---|---|---|---|
| `A_esters_fruity` / `F_esters_fruity` | `A_ester_fruity` / `F_ester_fruity` | `Esters aroma - fruity` / `Esters taste - fruity` | summary 少一个 `s` |
| `X4vg` | `4vg` | `4-vinyl guaiacol` | summary 无 `X` 前缀 |
| `bitternes` | `bitternes` | `Bitterness` | 拼写少一个 `s`，代码保留原列名、正文写 Bitterness |
| `overall` | `overall` | `Overall appreciation (Trained panel)` | 5.csv 原名含换行/`_x000D_` |
| `A_hops_noble` | `A_hops_noble` | `Hops aroma - grassy` | 语义是"贵族酒花/草本"，不是"noble"直译 |
| `orange` | `orange` | `Orange` | 8.xlsx `CleanName_PaperLong` 误作 "Hops taste - citrus"，以 `CleanName_Paper`/`PanelFeedback` 为准 |

**`3.xlsx` 内部还有两处不一致**（论文可说"以 4.csv 为准"）：
1. `summary!AX2 = '=beer_1!$AG$76'` 指向的 `AG76` 实为 **Stale hops** 的分值（`R75` 行），`Barnyard/horsey` 的分值公式在 `AG90`；即 summary 的 `barnyard` 列错引成 `stale_hops`。
2. `Acetaldehyde` 在评分卡上有属性（`B44/R44`）与分值公式（`Q45/AG45`），但 summary 没有引用它 → 卡上 51 个属性，summary 只取 50 个，恰好与 `4.csv` 的 50 列闭合。

### 2.3 论文写法（可直接粘贴）

> 题面称 Aroma 与 Flavour 两套"共约 40 个"感官维度。经与 `3.xlsx` 的 `summary`（52 列 = Beer + 50 个数值感官列 + comments）、12 张评分卡（beer_1~beer_12，每张 51 个属性标签）以及 `4.csv` 的实际列逐项对齐，附件实际定义 **50 个数值感官维度**：Aroma 15 维 + Flavour 15 维 + 口感/缺陷/辅料/总体 20 维；`5.csv` 与 `8.xlsx` 的 `Sensory names`（Trained panel 50 行）亦与之一一对应。因此本文的 `targetColumns` 取 `4.csv` 的 **50 个感官列**，题面"约 40"按概括误差处理，并在附录给出 50 维清单与跨表命名差异。

---

## 3. Q2：0–6 分口径——`4.csv` 不能精确还原成 0–6，论文必须区分"原始分/标准化值/映射分"

### 3.1 `3.xlsx` 是空白评分卡模板，不含任何真实 0–6 评分

对 `openpyxl` 同时用 `data_only=True/False` 双开取证（脚本 `sensory_01_xlsx_forensics.py`）：

| 对象 | 事实 | 证据 |
|---|---|---|
| 12 张 `beer_i` | 每张 101×33，结构完全相同：**54 个公式、199 个数字、63 个文本、已填写分值 = 0** | 数字 100% 是 0–6 刻度标签与 `S3` 的 Beer#；没有 `x/✓/1` 等勾选；无表单控件/图片 |
| 0–6 刻度 | `beer_1!C8=0, E8=1, G8=2, I8=3, K8=4, M8=5, O8=6`（右半 `S8…AE8` 同理），共 15 个刻度块 | 尺子本身是"评分卡定义"，不是数据 |
| 锚点文字 | `E97='Not present'` ↔ `C98=0`；`E100='Predominant/overwhelming'` ↔ `C101=6` | 0 = 未检出，6 = 主导/压倒性 |
| 编码公式 | `Q7 = IF(ISBLANK(O7),IF(ISBLANK(M7),…,0,1),2),3),4),5),6)`；`Q10 = IF(ISBLANK(C10),0,Q7)` | 把"是否在刻度位置打勾"编码成 0–6 整数；当前全空 → 全 0 |
| `summary` | 12 行 × 52 列，除 A 列 `Beer=1..12` 外共 **612 个跨表公式**（`=beer_1!$Q$7`…），`data_only=True` 计算结果**全部为 0** | 12 张卡空白 → `IF(ISBLANK(...))` 级联返回 0 |

**结论：`3.xlsx` 只提供 (i) 0–6 离散刻度的语义与锚点、(ii) 50 个感官维度的定义与评分卡公式逻辑；它不提供任何可用于校准/还原的观测评分。** 另外它只有 12 张卡（对应 Beer# 1–12，覆盖 250 个样本中的至多 12 个），即使有填写也远不足以做全量校准。

### 3.2 `4.csv` 不是 0–6 原始分，也不是逐列 z-score

| 检验 | 结果 | 判定 |
|---|---|---|
| 是否 0–6 原始分 | 50 列**全部非整数**；每列不同取值 106–250 个；**7617/12500（60.94%）单元格 <0**；`clove` 最大 **6.1724>6** | ❌ 不是原始 0–6 |
| 是否逐列 z-score | 50 列 **0 列**满足 `|sd−1|≤0.05`；`sd∈[0.3697, 0.8585]`（均值 0.5679，中位 0.5536） | ❌ 不是标准 z-score |
| 是否仅中心化 | 50 列均值都接近 0（`|mean|≤0.0628`，平均 0.0212），但**没有一列**精确为 0（最小 `|mean|=6.2e-4`） | △ 近似中心化，参考集不等于本 250 行 |
| 全局统计 | 全局均值 **0.00543**，全局 sd **0.57780**，范围 **[-2.1507, +6.1724]**，偏度 -0.53～+6.81 | 与"列内中心化 + 共同缩放"最一致（机制属于推断，文件未记录参数） |

**可直接写进论文的表述**："`4.csv` 的 50 个感官列是经中心化/标准化后的连续感官强度，不是原始 0–6 分；其列均值约为 0 但非精确 0、列标准差为 0.37–0.86 而非 1，且 60.94% 取值为负，说明其标准化参数（列原点与缩放系数）未随数据提供。"

### 3.3 能否还原 0–6？——不能精确还原（数学上不可识别）

设原始 0–6 值为 `x`，`4.csv` 值为 `z`。无论标准化是 `z=(x−a_j)/s_j` 还是 `z=(x−a_j)/s`（列原点 `a_j` + 列/共同缩放），只要 `a_j`、`s` 未记录，就有：

- 可恢复：列内相对大小（序）、列内相对间距（在未知比例意义下）、列间相对离散度（`sd_j` 之比）；
- **不可恢复**：每列的原点 `a_j`（=该感官维度的平均评审水平）与绝对 0–6 水平；列间绝对水平也无法比较。

可把"所有可能的还原"写成 `x = a_j + b·z`（`b>0` 为未知缩放；`a_j` 为自由原点）。要求 `x∈[0,6]` 时：

- `b ≤ 6 / max_j(range_j) = 6/6.4409 ≈ 0.9315`（由 `clove` 的极差决定）；
- 每个 `a_j` 只要落在 `[-b·z_min, 6−b·z_max]` 内即可，**是一段区间而非唯一点**。

这就是**不可识别性（non-identifiability）**，不是精度/算法问题。缺的信息（需向数据提供方索取）：
1. 每列的原始 0–6 值（或至少每列原始均值/标准差）；2. 标准化方式与参考样本（250 行上做的？品评员层级？更大样本？）；3. 品评员人数与聚合规则；4. 12 张卡对应哪 12 个 Beer# 的真实评分（当前空白）。

### 3.4 如果题目强制要 0–6：只能给"显式声明的映射分级分"

| 方案 | 做法 | 量化后果 | 建议 |
|---|---|---|---|
| **A（主方案）** | 不做 0–6 映射，直接把 `4.csv` 当标准化连续目标回归；指标在标准化尺度报告 | 信息零损失 | ✅ 建模主口径 |
| **B** | 列内 min-max 映射到 [0,6]：`x=6(z−z_min)/(z_max−z_min)`（端点假设：本样本极值=量程两端） | 保序（Spearman=1）；映射后列均值 0.221–3.364、sd 0.521–1.349；**RMSE 尺度系数 0.9315–2.9498（差 3.17 倍）** | ⚠️ 若必须交 0–6，用它，并声明端点假设 |
| **C** | 列内秩/分位数映射到 0..6（`6(rank−1)/(n−1)`） | 保序；但全列均值≈3、sd≈1.742，**抹平原始分布形状** | ⚠️ 只作敏感性对照 |
| **D** | 假定原始 0–6 分的列均值=3、列 sd=1；因 4.csv 的 sd≠1，须反推未知缩放 `s=1/sd_j`，即先按列 sd 归一再加 3：`x=3+(z−z̄_j)/sd_j` | **205/12500（1.64%）越界**，最大映射值 14.09（`clove`） | ❌ 不可用 |

**B 与 C 的差异必须写进论文**：两者都保序且都落 [0,6]，但逐单元格 **平均差 1.52 分、最大 4.94 分**。例：`clove` 的 beer 181（z=−0.3109）在 B 下映射为 **0.059（≈"未检出"）**、在 C 下为 **3.012（"中等"）**；观测数据无法区分谁对。**这正是"不能把映射分当原始分"的量化依据。**

### 3.5 论文写法（可直接粘贴）

> `4.csv` 的 50 个感官列是中心化/标准化后的连续强度（列均值≈0、列 sd=0.37–0.86、60.94% 值为负、`clove` 最大 6.17>6），不是原始 0–6 分；`3.xlsx` 的 12 张评分卡为空白模板（已填分值=0），`summary` 612 个跨表公式计算结果全 0，不含任何真实 0–6 观测，因此**无法精确还原原始 0–6 评分**。本文以标准化连续值为主建模目标（记为 `z`），所有指标在标准化尺度报告；为满足题面"0–6 分制分级"的呈现要求，另给出**映射分级分** `x_mapped = 6(z−z_min)/(z_max−z_min)`，并声明：(i) 它是保序映射分，**不是原始 0–6 评分**；(ii) 端点假设为样本极值对应量程两端；(iii) 各维映射对误差的尺度系数为 0.93–2.95，故分级分不用于跨维度绝对比较，也不与 3.xlsx 评分卡或文献 0–6 值直接比较；(iv) 另以秩映射做敏感性对照，两种映射逐单元格平均差 1.52 分、最大 4.94 分。

### 3.6 0–6 话题的常见错误（答辩时会被追问）

1. ❌ 直接把 `4.csv` 四舍五入/加 3 当 0–6 分（方案 D 会产生 1.64% 越界）。
2. ❌ 把 `4.csv` 当"z-score"（列 sd≠1），或声称"均值为 0 所以是中心化原始 0–6"（原点是未知的）。
3. ❌ 把 `3.xlsx` 当监督标签源（它是空白卡）；把 `summary` 的 0 当"评分全为 0"（其实是公式空引用）。
4. ❌ 用 `beer_id` 跨表 join（`4.csv`/`7.csv` 的 `beer_id` 被浮点截断，250 行只剩 96 个不同值）；应用 `beer` 列/行位置。
5. ❌ 把 `5.csv`/`6.csv` 当外部独立先验（它们就是同一批 250 样本从 `4.csv`/`1.csv` 重算的相关矩阵，见 Q3）。

---

## 4. Q3：`2.csv` 实测是 **Spearman**，题面"皮尔逊"是笔误

### 4.1 重算证据（用 `1.csv` 独立计算，不引用现成结论）

| 假设 | `max|Δ|`（对 2.csv，非对角 26565 个元素） | 中位 `|Δ|` | 逐元素相关 | 判定 |
|---|---|---|---|---|
| **Spearman，pairwise complete** | **7.77×10⁻¹⁶** | 8.33×10⁻¹⁷ | **1.000000**（53361/53361 元素 <1e-12） | ✅ 命中 |
| Pearson，pairwise complete | 1.1234 | 0.0622 | 0.7718；**4501/26565（16.94%）元素符号相反** | ❌ 排除 |
| listwise Spearman（整行删除） | 0.1431 | 0.0264 | 0.9787 | ❌ 排除 |
| log10 变换后 Pearson | 1.0167 | 0.0673 | 0.7562 | ❌ 排除 |

**决定性样例**（完整见 `analysis/corr/sample_pairs.csv`）：
- `Ethyl pentanoate` × `3-methylbutanal`：`2.csv = −0.447484`，重算 Spearman = **−0.447484**，重算 Pearson = **+0.675943（符号相反）**；
- `Ethyl pentanoate` × `E,E-2,4-decadienal`：`2.csv = −0.591625`，Spearman = −0.591625，Pearson = +0.474447（符号相反）。

**结论：`2.csv` 是 231×231 成对完整样本（pairwise complete）的 Spearman 秩相关矩阵；题面 P3"皮尔逊"错误，`数据说明.txt` 的 Spearman 正确。**

### 4.2 矩阵属性与使用注意

| 属性 | 实测 | 含义 |
|---|---|---|
| 形状 / 命名 | 231×231；行名=列名（顺序同 `1.csv` 231 特征经映射后的顺序） | 用 `8.xlsx Sensory thresholds` 的 `field_name_R↔chemical_name` 可做 **231/231 双射** |
| 对称性 / 对角 / 缺失 | `max|M−Mᵀ|=0`；对角全 1；无 NaN | 标准相关矩阵形态 |
| 取值范围 | `[−0.6636, 1]`；非对角负值 8627 个 | 合法 |
| **最小特征值** | **−0.04241270911948124**（5 个特征值 <−1e−10）→ **非 PSD** | 成对完整样本相关矩阵在缺失值下不保证半正定；重算矩阵 min eig 逐位相同，佐证同源。若做 Cholesky/PCA/高斯图模型，需先做最近 PSD 投影或收缩估计，并在论文声明 |
| 缺失处理 | `1.csv` 有 73 个缺失（9 列），必须 **pairwise complete**；listwise 会偏离 2.csv（max 0.1431） | 2.csv 生成口径即 pairwise complete |

### 4.3 `5.csv` / `6.csv` 是同一批数据的重算，不是"外部先验"

- `5.csv = Spearman(4.csv)`：50×50，`max|Δ| = 6.66×10⁻¹⁶`；min eig = +0.02343（PSD）。
- `6.csv = Spearman(1.csv, 4.csv)`：实际 **44×50**（题面称 46×50），`max|Δ| = 6.66×10⁻¹⁶`；行 = 44 个化学/理化特征，列 = 50 个感官属性。
- 二者都可由 `1.csv`/`4.csv` 在机器精度内复现 ⇒ **不能当独立外部证据**（会构成循环验证）；可用于一致性检查、共表达图权重、或作为"多视图"但不参与独立验证。

### 4.4 论文写法（可直接粘贴）

> 题面正文称 `2.csv` 的单元格为"皮尔逊相关系数"，而附件 `数据说明.txt` 称其为 Spearman 相关系数。本文用 `1.csv` 的 231 个特征以成对完整样本重算两种相关系数并与 `2.csv` 逐元素比对：与 Spearman 的最大绝对误差为 **7.8×10⁻¹⁶**（逐元素相关 1.000000），与 Pearson 的最大绝对误差为 **1.1234** 且 16.94% 的元素符号相反（例：Ethyl pentanoate × 3-methylbutanal，`2.csv` 与重算 Spearman 均为 −0.447484，而 Pearson 为 +0.675943）。因此 `2.csv` **实为 Spearman 秩相关矩阵**，题面"皮尔逊"为笔误；本文按 Spearman 秩相关语义构建化合物共表达图（以 `|ρ|` 为边权并做 BH-FDR 校正）。此外，`5.csv = Spearman(4.csv)`、`6.csv = Spearman(1.csv,4.csv)` 均可在机器精度内重算，说明三者是同批 250 个样本的相关矩阵，不构成独立外部数据。

---

## 5. Q4：`8.xlsx` 实际 7 个 sheet，按实际用途使用

### 5.1 全 sheet 清单（`8xlsx_inventory.md` / `8xlsx_details.json`）

| # | sheet | 实际维度 | 内容与语义 | 建模用途 | 坑 |
|---|---|---|---|---|---|
| 1 | `Sensory thresholds` | 261×11 | 261 条化合物/风味物质；`threshold_mean/median` **仅 43 行有数值**（NA 83.5%）；`off_flavors` 仅 **7 行**；`calibrated` 有值 68 行；`origin_paper`（Hops 90/Yeast 82/Spices 28/Malt 24/Others 22/Wild flora 6） | Q3 缺陷化合物 OAV/超阈值判定；化学合理性 | 只有 DMS(17.25 µg/L)、Diacetyl(2,3-butanedione, 0.299 mg/L)、4VG(0.206 mg/L) 等少数有阈值；`(E)-2-nonenal` 有记录**无阈值**；`3-methyl-2-butenal` 无阈值；"Stale hops"本身是 4.csv 感官维度而非单一化合物 |
| 2 | `Sensory names` | 101×8 | `dataset`：**Trained panel 50 行 + Ratebeer 51 行**；`R_name`（=4.csv 列名）↔ `CleanName_Paper`/`CleanName_PanelFeedback`（=5/6.csv 列名） | 50 维权威命名与 Aroma/Flavour/口感分组 | **不要把 101 行当 101 个目标**；Ratebeer 51 行属于 7.csv 体系；`CleanName_PaperLong` 有 2 处与 `CleanName_Paper` 不一致（`t2n`、`orange`），以 `CleanName_Paper`/`PanelFeedback` 为准 |
| 3 | `GBM importance MDI` | 232×2（首行残缺表头 `['', 0]`） | 231 个特征 + **单列 importance**（sum=1，范围 5.39e−5～0.2222；Top：`ethyl_acetate` 0.2222、`ethanol..v.v.` 0.0670、`ethyl_octanoate` 0.0541） | Q2 "全局重要性"外部对照/排序一致性 | **不是 50 目标逐目标归因**（无目标列，疑为多输出聚合）；且是同一批 250 样本上的拟合产物，**不能当输入特征**（泄漏） |
| 4 | `GBM SHAP Values` | 501×236（含表头 → 500 数据行） | `data` 列：**250 行 SHAP + 250 行 concentration**；列 = 4 元数据 + 231 特征 + `base_prediction`（常数 −0.326338）。concentration 块与 `1.csv` 231 列 250 行**逐值相等**（max diff 8.9e−16）；行内 SHAP 加 + base = 单目标预测 | Q2 归因示例/与 2.csv 图对照 | **单目标、目标未标注**（与 50 维任一列最大 |r| 仅 0.651，对应 aftertaste，不能唯一对应）；同批样本拟合，**不可作特征** |
| 5 | `Calibrated chemical dataset` | 250×73 | 3 元数据 + **70 个化合物的原始浓度**（单位量纲经校准）；缺 69 个单元格 | 核验 `1.csv` 的对数变换底数（**log10**，不是 ln）；还原原始浓度供 OAV/阈值比较；化学可解释性 | 只有 70/231 列，**不能整体替代 1.csv**；且 `1.csv` 并非全部 log10（见下） |
| 6 | `Beer Prices` | 250×11 | `beer/beer_id/tasting_category/ABV` + 7 个渠道价格；NA 合计 **1005**；有任一价格 229/250；ABV 0–12（中位 6.75） | 外部商业协变量（价格-风格-ABV-风味关联、缺失机制分析） | 7 列价格缺失 40%–82%，不能进 Q1 特征；`tasting_category` 命名与 1.csv 不同 |
| 7 | `Sheet2` | 0×0 | **空表** | 无 | 读取时跳过；论文可写"名义 7 个，有效 6 个" |

### 5.2 关键发现：`8.xlsx` 的 Calibrated 数据反过来证明 `1.csv` 是"混合尺度"

用 70 个可对齐列逐一比较 `1.csv` 与 Calibrated 原始浓度（脚本 `ref_8xlsx_audit.py` + 本报告复核）：

- **35 列**：`1.csv = log10(原始浓度)`（例：`ethyl_acetate` 的 −0.5993 ↔ 0.2516；`DMS` 0.0462 ↔ 0.0，1.3844 ↔ 24.2352；`pH` 0.6248 ↔ 4.215；`color` 0.653/1.261 ↔ 18.225；`bitterness` ↔ 18.162；`ethanol` ↔ 7.19；`CO2` ↔ 2.5）；
- **33 列**：`1.csv = 原始浓度本身`（无负值；例：`linalool` 22.0557、`X2.3.butanedione` 0.0021）；
- **2 列**（`CS2`、`X4VG`）：`1.csv = log10(原始浓度)`，但原始浓度为 0 时用底限值（−2.1463/−2.0132）编码。

> 合计 **37 列**（35 + 2）为 log10 口径、**33 列**为原始浓度口径，与 ref 组"37/70 列 1.csv=log10(原始浓度)"的结论一致；划分判据为逐列中位差 `|1.csv − log10(cal)| < 1e−3`（或零底限码）。

**这意味着**：
1. 题面说"少量理化参数列（如 ethanol、color、bitterness、pH、CO2）保留原始量纲"与文件**不符**——这 5 列实测也是 log10（10^值 = 原始量纲）；
2. 题面要求"自行核实变换底数（log10 或 ln）"——答案是 **log10**，且**并非所有列都做了对数变换**（33 列保留原始浓度）；
3. 建模前必须逐列判断尺度，不能对全部 231 列统一再取 log 或统一 z-score；如需原始量纲，用 Calibrated 表还原（仅 70 列）或按 `10^v` 反演（仅 log10 列）。

### 5.3 论文写法（可直接粘贴）

> 附件 8.xlsx 共 7 个 sheet（6 个有内容 + 1 个空 Sheet2），本文按实际内容分别使用：`Sensory thresholds` 提供 43 个化合物的感官阈值与 7 个异味标记，用于问题 3 的缺陷化合物 OAV/超阈值判定（其中 trans-2-nonenal、stale hops 无直接阈值，需以 4.csv 感官值或文献补齐）；`Sensory names` 提供 50 个训练面板感官维度的权威命名映射（另 51 行为 Ratebeer 体系）；`Calibrated chemical dataset` 提供 70 个化合物的原始浓度，用于核验 1.csv 的对数变换底数为 **log10**，并发现 1.csv 为混合尺度（35 列 log10、33 列原始浓度、2 列零值底限编码），其中 pH/color/bitterness/ethanol/CO2 亦为 log10，与题面"保留原始量纲"的表述不符；`GBM importance MDI` 与 `GBM SHAP Values` 是同一批 250 个样本、231 个化合物特征上的拟合产物（单目标未标注/SHAP 含 concentration 块），仅作外部对照与可解释性示例，**不作为模型输入特征**（避免目标泄漏）；`Beer Prices` 提供 7 个渠道价格（缺失 40%–82%），仅作外部商业协变量。

---

## 6. Q5：`3.xlsx` 以实际 13 个 sheet 为准（题面"10 个"过时）

| 项 | 题面 | 实际 | 证据 |
|---|---|---|---|
| sheet 数 | "10 个 sheet"，"beer_1~beer_10" | **13 个**：`beer_1`…`beer_12` + `summary` | `openpyxl.load_workbook(...).sheetnames`；`xlsx_forensics.json` |
| 每张 beer 卡 | "每个 sheet 对应一款啤酒（Beer# 1~10）" | 12 张，`S3` 分别为 1…12；结构完全相同（54 公式/199 数字/63 文本） | `xlsx_beersheet_inventory.csv` |
| 是否含评分 | "是人工感官评分卡，评分采用 0–6 离散等级" | **空白模板**：已填写分值=0；summary 计算结果全 0 | §3.1 |

**处理原则：不删不减。** 保留 `beer_1`…`beer_12` 与 `summary`；论文写"3.xlsx 共 13 个 sheet：12 张评分卡 + 1 个 summary"，并说明 12 张卡为**空白模板**（只用于定义 0–6 刻度与 50 维属性）。若审稿要求解释"题面 10 个"，按题面笔误/版本差异处理，不修改原始文件。

**论文写法**：

> 3.xlsx 实际包含 13 个 sheet：`beer_1`～`beer_12` 共 12 张感官评分卡与 1 个 `summary` 汇总表，题面所述"10 个 sheet（beer_1~beer_10）"与文件不符。12 张评分卡结构一致（每张 54 个公式、0–6 刻度与属性标签），但均为空白模板，`summary` 的 612 个跨表公式计算结果全为 0，不含真实评分；本文保留全部 13 个 sheet 不删不减，仅将其作为 0–6 量表语义与 50 维属性定义的依据，另发现 summary 的 `barnyard` 列误引 `stale_hops` 单元格（`AG76`，应为 `AG90`）、`Acetaldehyde` 有评分卡公式但未进入 summary，建模目标以 `4.csv` 的 50 列为准。

---

## 7. 题面/数据说明 vs 实际文件：差异总表（建议放论文"数据核查"小节）

| ID | 题面/说明原文 | 实际事实 | 证据（脚本/位置） | 论文处理 |
|---|---|---|---|---|
| D01 | 226 种不同啤酒 | **250** 个样本（1/4/7.csv 均 250；8.xlsx 各表 250） | `verify_all.py`；`ref_crosscheck.py` | 按 250 陈述，注明题面笔误 |
| D02 | 2.csv 为**皮尔逊**相关 | **Spearman**（max err 7.8e−16；Pearson max 1.1234） | `corr_forensics.py` | 按 Spearman，注明题面笔误 |
| D03 | 3.xlsx **10 个 sheet** | **13 个**（12 卡 + summary） | `ref_crosscheck.py` | 按 13，不删不减 |
| D04 | Aroma+Flavour **约 40 个**感官维度 | **50 个**（A15+F15+其他20） | `sensory_03_align_targets.py` | 按 50，附注 30/20 口径 |
| D05 | 6.csv **46×50** | **44×50** | `corr_forensics.py` | 按 44×50 |
| D06 | 7.csv **187 个**感官属性 | **186 个**感官列（250×189 = 3+186；3 列全 NA） | `ref_crosscheck.py` | 按 186（可用 183） |
| D07 | 1.csv "200 多种"化合物 | **231 特征** = 226 实测/化合物 + 5 派生（kcalperc、4 个 _sum） | `ref_crosscheck.py` | 按 231，区分派生列 |
| D08 | 3.xlsx 是"评分卡" | 是**空白评分卡模板**，无任何真实 0–6 评分 | `sensory_01_xlsx_forensics.py` | 只作量表/维度定义，不作标签 |
| D09 | 4.csv 为"标准化/中心化连续值" | 成立，但**参数未给**：非 z-score（sd 0.37–0.86）、非精确中心化、60.94% 负值、`clove`>6 | `sensory_02_scale_stats.py` | 主目标用标准化值；0–6 只能映射并声明 |
| D10 | "少量理化参数保留原始量纲（ethanol/color/bitterness/pH/CO2）" | 这 5 列实测也是 **log10**；1.csv 混合尺度（35 列 log10、33 列原始浓度、2 列零底限） | `ref_8xlsx_audit.py` | 逐列判断尺度；log10 反演 `10^v` |
| D11 | 8.xlsx 为"其他相关数据" | **7 个 sheet**（6 有内容 + 空 Sheet2），各自可支撑不同环节 | `8xlsx_inventory.md` | 逐 sheet 说明用途 |
| D12 | 数据说明：7.csv 是"论坛评论数据" | 实际是 186 维**标准化数值**矩阵（列均值≈0、列 sd 中位 1.003），与 4.csv 同批 250 样本、同 beer 顺序 | `ref_crosscheck.py` | 不能当独立外部先验；可作多视图补充 |
| D13 | （未提及数据质量） | 4/7.csv 的 `beer_id` 被浮点截断：250 行仅 **96 个不同值**，与 1.csv 精确 ID 仅 37/250 字面相等 | `ref_crosscheck.py` | 跨表 join 用 `beer`/行位置，不用 `beer_id` |

**统一处理原则**（写进论文即可）：
1. **以实际文件为准**：题面数字（226/40/10/46/187）全部按实测修正，并在"数据核查"表逐条列原文、实测、证据；
2. 每个"修正"都给可复现脚本与精确数字，避免"我觉得/大概"；
3. 不修改、不删减原始附件；题面差异只在论文中说明；
4. 同源文件（1/2/4/5/6/7.csv、8.xlsx 的 MDI/SHAP/Calibrated）要标明同源关系，避免把重算矩阵当独立证据；
5. 对不可识别的问题（4.csv→0–6）明确声明假设，不伪造"原始分"。

---

## 8. 复现与证据索引

### 8.1 一键复核

```bash
cd /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest
PY=/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3

$PY analysis/scripts/verify_all.py            # Lead 总复核：全部关键数字（约 2 s）
$PY analysis/scripts/corr_forensics.py        # 2.csv/5.csv/6.csv 相关类型（约 7 s）
$PY analysis/scripts/sensory_01_xlsx_forensics.py   # 3.xlsx 空白卡取证
$PY analysis/scripts/sensory_02_scale_stats.py      # 4.csv 尺度检验与映射量化
$PY analysis/scripts/sensory_03_align_targets.py    # 50 维对齐
$PY analysis/scripts/ref_8xlsx_audit.py       # 8.xlsx 全 sheet 审计
$PY analysis/scripts/ref_crosscheck.py        # 跨表一致性与差异清单
```

### 8.2 证据文件

| 内容 | 文件 |
|---|---|
| Lead 总复核（JSON，含全部关键数字） | `analysis/assets/verification.json` |
| PDF 独立抽取文本 | `analysis/assets/pdf_text_pdfkit.txt` |
| 50 维清单与四方对齐 | `analysis/sensory/targetcolumns.csv`、`analysis/assets/target_columns_lead.csv` |
| 4.csv 逐列尺度统计 | `analysis/sensory/scale_stats.csv` |
| 3.xlsx 取证 | `analysis/sensory/xlsx_forensics.json`、`xlsx_summary_formula_map.csv`、`xlsx_beersheet_inventory.csv` |
| 2.csv 相关类型证据 | `analysis/corr/report.md`、`summary.json`、`matrix_properties.json`、`sample_pairs.csv`、`name_mapping_2csv_to_1csv.csv` |
| 8.xlsx 全 sheet 审计 | `analysis/ref/8xlsx_inventory.md|csv`、`8xlsx_details.json` |
| 差异总表 | `analysis/ref/discrepancies.md|csv` |
| 三组专项报告 | `analysis/corr/report.md`、`analysis/sensory/report.md`、`analysis/ref/report.md`（另 `8xlsx_inventory.md`、`discrepancies.md`） |

---

## 附录 A：50 个 `targetColumns` 完整清单（按 4.csv 列序）

见 `analysis/sensory/targetcolumns.csv`（含 4.csv 列名、Aroma/Flavour 组、子类、3.xlsx summary 名与单元格、5.csv 长名、8.xlsx R_name、命名差异注释）。分组计数：**Aroma 15 + Flavour 15 + 口感/缺陷/辅料/总体 20 = 50**。

| # | 4.csv 列 | 组 | 子类 | 中文/显示名 | 备注 |
|---|---|---|---|---|---|
| 1–5 | `A_malt_all/grain/bread/cara/burn` | Aroma | Malt | 麦芽香（总体/谷物/面包/焦糖/烟熏） | |
| 6–10 | `A_hops_all/citrus/tropical/noble/woody` | Aroma | Hops | 酒花香（总体/柑橘/热带水果/草本/木质） | `noble` 实为 grassy/草本 |
| 11–15 | `A_esters_all/ethac/isoaa/flower/fruity` | Aroma | Yeast | 酯香（总体/指甲油/香蕉/花香/果香） | `ethac`=ethyl acetate 类 |
| 16–20 | `F_malt_all/grain/bread/cara/burn` | Flavour | Malt | 麦芽风味 5 维 | |
| 21–25 | `F_hops_all/citrus/tropical/noble/woody` | Flavour | Hops | 酒花风味 5 维 | |
| 26–30 | `F_esters_all/ethac/isoaa/flower/fruity` | Flavour | Yeast | 酯风味 5 维 | |
| 31 | `acidity` | 其他 | 基本味 | 酸度 | |
| 32 | `bitternes` | 其他 | 基本味 | 苦味 | 原文拼写少 s |
| 33 | `sweetness` | 其他 | 基本味 | 甜味 | |
| 34 | `X4vg` | 其他 | 缺陷 | 4-乙烯基愈创木酚 | summary 名 `4vg` |
| 35 | `diacetyl` | 其他 | 缺陷 | 双乙酰（黄油味） | |
| 36 | `dms` | 其他 | 缺陷 | 二甲基硫（煮玉米/蔬菜） | |
| 37 | `metallic` | 其他 | 缺陷 | 金属味 | |
| 38 | `stale_hops` | 其他 | 缺陷 | 陈酒花（奶酪/臭） | |
| 39 | `t2n` | 其他 | 缺陷 | 反-2-壬烯醛（纸板味） | |
| 40 | `orange` | 其他 | 辅料/辛香 | 橙味 | |
| 41 | `coriander` | 其他 | 辅料/辛香 | 芫荽 | |
| 42 | `clove` | 其他 | 辅料/辛香 | 丁香 | |
| 43 | `lactic` | 其他 | 野生菌 | 乳酸 | |
| 44 | `acetic` | 其他 | 野生菌 | 乙酸 | |
| 45 | `barnyard` | 其他 | 野生菌 | 谷仓/马厩味 | summary 误引 stale_hops |
| 46 | `alcohol` | 其他 | 口感 | 酒精感 | |
| 47 | `aftertaste` | 其他 | 口感 | 余味 | |
| 48 | `body` | 其他 | 口感 | 酒体 | |
| 49 | `co2` | 其他 | 口感 | 碳酸感 | |
| 50 | `overall` | 其他 | 总体 | 总体喜好 | 5.csv 名含换行 |

---

## 附录 B：关键数字速查

| 主题 | 数字 |
|---|---|
| 样本数 | 250（题面 226） |
| 1.csv 特征 | 231（226 实测/化合物 + 5 派生）；缺失 73 个/9 列 |
| 4.csv 感官列 | 50（A15+F15+其他20）；无缺失 |
| 3.xlsx | 13 sheets（12 卡 + summary）；每卡 54 公式/199 数字/已填分值 0；summary 612 公式、结果全 0 |
| 4.csv 全局 | mean 0.00543、sd 0.57780；列 sd 0.3697–0.8585；60.94% 值为负；`clove` max 6.1724 |
| 0–6 不可识别 | `x=a_j+b·z`，`b≤0.9315`；B 与 C 映射平均差 1.52 分、最大 4.94 分 |
| 2.csv | 231×231；vs Spearman max 7.8e−16；vs Pearson max 1.1234、16.94% 符号相反；min eig −0.0424（非 PSD） |
| 5.csv / 6.csv | 50×50 / **44×50**；均 = 同批数据 Spearman，max err 6.7e−16 |
| 8.xlsx | 7 sheets；thresholds 261 行仅 43 阈值、7 异味；Sensory names 50+51；MDI 231 特征；SHAP 250+250；Calibrated 70 列；Prices 1005 NA；Sheet2 空 |
| 1.csv 尺度 | 35 列 log10、33 列原始浓度、2 列零底限；pH/color/bitterness/ethanol/CO2 也是 log10 |
| 跨表 join | 用 `beer`（1..250）；`4/7.csv` 的 `beer_id` 250 行仅 96 个不同值 |

---

*本报告为 Lead 汇总；三组独立取证报告见 `analysis/corr/report.md`、`analysis/sensory/report.md`、`analysis/ref/`。所有数字均可用 §8.1 命令重跑。*
