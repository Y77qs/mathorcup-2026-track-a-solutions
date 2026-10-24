# 2.csv 相关矩阵类型取证报告（Pearson vs Spearman）

**结论（TL;DR）**：`2.csv` 是 **231×231 成对完整样本（pairwise complete）的 Spearman 秩相关矩阵**，不是 Pearson 相关矩阵。
用 `1.csv` 原始数据独立重算后，26565 个非对角元素与 `2.csv` 的 **最大绝对误差 = 7.77×10⁻¹⁶（机器精度）**、逐元素相关系数 = **1.000000**；
若改用 Pearson，最大绝对误差 = **1.1234**、中位误差 = **0.0622**，且 **4501/26565（16.94%）** 对元素的符号完全相反。
故：**题面 PDF 第 3 页“单元格为皮尔逊相关系数”的表述错误；`数据说明.txt` 第 2 条“Spearman”正确。**
`5.csv = Spearman(4.csv)`、`6.csv = Spearman(1.csv × 4.csv)` 同样在机器精度内成立。

> 本报告所有结论均由本脚本从 `data/raw/` 原始文件重算，未引用 `A/` 目录（往期 agent 结果）。
> 复现命令（唯一 Python 环境）：
> ```bash
> cd /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest
> /Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3 \
>     analysis/scripts/corr_forensics.py
> ```
> 运行约 7 秒，重写本目录下全部数值资产，并打印同样的数字。

---

## 1. 名称映射（先解决“行列名怎么对上”）

`2.csv` 用显示名（`Acetaldehyde`、`Carbon disulfide`…），`1.csv` 用代码名（`acetaldehyde`、`CS2`…）。
用 `8.xlsx / Sensory thresholds` 的 `field_name_R`（=1.csv 列名）与 `chemical_name`/`chemical_name_short`（≈2.csv 行名）建映射，并对 8.xlsx 中部分乱码（如 `E-Î²-damascenone` = UTF-8 被 latin-1 误解码）做修复、希腊字母归一：

| 校验项 | 结果 |
|---|---|
| 1.csv 特征列数 / 2.csv 行列名数 | 231 / 231 |
| 成功映射 | **231 / 231（100%）** |
| 未映射项 | **0** |
| 一对多歧义 | **0** |
| 映射是否双射 | **是**（231 个 2.csv 名 ↔ 231 个 1.csv 列，一一对应） |
| 1.csv 中未被使用的特征列 | 0 |

- 明细：`analysis/corr/name_mapping_2csv_to_1csv.csv`（每行给出 `csv2_name, csv1_column, field_name_R, field_name_python, chemical_name, calibrated, is_summary_col`）。
- **注意**：上下文原先假设“1.csv 有 5 个汇总列”，实测只有 **4 个**以 `_sum` 结尾的汇总列：
  `esters_sum, aroma_hops_sum, acids_sum, sulfur_sum`（分别对应 2.csv 行名 Esters/Total hop aroma compounds/Acids/Sulfur compounds 之类）；
  其余 227 列为单一化合物或理化指标（pH、Color、Bitterness、CO2、Ethanol、Caloric value 等）。4 个汇总列在 2.csv 中也作为独立行/列存在，故仍参与 231×231 矩阵。
- `1.csv` 特征列中存在 **73 个缺失值、分布在 9 列**（Diacetyl 9、Methylpyrazine 12、Amyl acetate 27、Total hop aroma compounds 13 等），
  这是必须用 **pairwise complete** 而不是 listwise 的原因（见 §3 的对照）。

---

## 2. 核心证据：2.csv = pairwise-complete Spearman

数据按 2.csv 行名顺序对齐为 250×231 矩阵，逐对取完整样本分别算 Pearson / Spearman，与 2.csv（231×231）逐元素比较：

| 假设（矩阵级，非对角 26565 个元素） | max abs err | median abs err | q90 | q99 | 逐元素相关 | 判定 |
|---|---|---|---|---|---|---|
| **Spearman，pairwise complete** | **7.77×10⁻¹⁶** | **8.33×10⁻¹⁷** | 4.16×10⁻¹⁶ | 5.27×10⁻¹⁶ | **1.000000000** | **✅ 命中（机器精度）** |
| Spearman，listwise（整行删除，仅剩 187 行） | 0.1431 | 0.0264 | 0.0644 | 0.1015 | 0.9787 | ❌ 排除 |
| Pearson，pairwise complete | 1.1234 | 0.0622 | 0.1953 | 0.4048 | 0.7718 | ❌ 排除 |
| Pearson，log10 变换后（非正值平移后取对数） | 1.0167 | 0.0673 | 0.2033 | 0.3896 | 0.7562 | ❌ 排除 |
| Pearson，先秩变换（= Spearman，等价性自检） | 7.77×10⁻¹⁶ | 8.33×10⁻¹⁷ | — | — | 1.000000000 | ✅ 与 Spearman 完全一致 |

**决定性证据**：取 |Pearson − 2.csv| 最大的若干化合物对（完整数值见 `sample_pairs.csv`）：

| 化合物 A | 化合物 B | **2.csv 值** | **重算 Spearman** | 重算 Pearson | \|2.csv − Pearson\| |
|---|---|---|---|---|---|
| Ethyl pentanoate | 3-methylbutanal | **−0.447484** | **−0.447484** | **+0.675943** | 1.1234（**符号相反**） |
| Ethyl pentanoate | E,E-2,4-decadienal | **−0.591625** | **−0.591625** | **+0.474447** | 1.0661（**符号相反**） |
| Ethyl pentanoate | Diacetyl | **−0.663595** | **−0.663595** | **+0.304581** | 0.9682（**符号相反**） |
| Phenylacetaldehyde | Z-nerolidol | **−0.111587** | **−0.111587** | **+0.835820** | 0.9474（**符号相反**） |
| Ethyl pentanoate | Caryophyllene | **−0.129422** | **−0.129422** | **+0.785547** | 0.9150（**符号相反**） |

这些对的 Spearman 与 2.csv **逐位相同**（差值 ~1e-16），而 Pearson 不仅数值不同、**连符号都反了**——不可能是舍入或样本差异造成的，只能是秩相关。

**全矩阵一致性**：`|2.csv − 重算Spearman| < 1e-12` 的元素 = **53361 / 53361（含对角，100%）**；最大差值 7.77×10⁻¹⁶ 属于双精度浮点的求和次序误差。另用 pandas 独立实现 `DataFrame.corr(method='spearman')` 交叉核对，与 2.csv 最大差 **6.66×10⁻¹⁶**（第二实现交叉验证）。

**变换能否解释差异？**
- 秩变换后再 Pearson ≡ Spearman，**完全解释**了 2.csv（误差回到机器精度）。
- log10 变换后再 Pearson **不能解释**（中位误差 0.0673，甚至比原始 Pearson 的 0.0622 略差）；1.csv 中部分特征为对数后的丰度、且含负值/零值，log10 不是产生 2.csv 的机制。
- listwise Spearman 也**不能**（最大 0.1431），说明原矩阵用的是 pairwise complete（成对完整样本）口径。

---

## 3. 2.csv 矩阵属性审计

| 属性 | 实测值 | 说明 |
|---|---|---|
| 形状 | **231 × 231** | 与 1.csv 的 231 个特征列数量一致 |
| 行列名 | 231 个显示名，**行名 == 列名**（顺序也相同） | 与 1.csv 231 列经 8.xlsx 映射后一一对应 |
| 缺失值 NaN | **0** | 完整方阵 |
| 对称性 max\|M−Mᵀ\| | **0.0** | 严格对称（浮点意义上完全相等） |
| 对角元 | min = max = **1.0**，全为 1 | 相关矩阵标准形态 |
| 取值范围 | **min = −0.663595，max = 1.0** | 合法相关系数区间内；非对角负值 8627 个 |
| 最小特征值（PSD 检查） | **−0.04241270911948124**（5 个特征值 < −1e−10） | **不是 PSD**（见下方解释） |
| 重算 Spearman 的最小特征值 | **−0.04241270911948124** | 与 2.csv **逐位相同（差值 0.0）**，进一步证明二者同源 |
| 相关矩阵合法性 | min ≥ −1、max ≤ 1 | ✅ |

**关于“不 PSD”**：成对完整样本（pairwise complete）相关矩阵在存在缺失值时**数学上不保证半正定**，出现 5 个小的负特征值是正常现象，并不是文件损坏或算错；重算矩阵的最小特征值与之**完全一致（差值 0.0）**，恰好是“2.csv 就是这套 pairwise-complete Spearman”的强证据。论文中若需 PSD（如直接做 Cholesky、高斯图模型、PCA 白化），应注明并采用最近 PSD 投影或收缩估计。

---

## 4. 5.csv / 6.csv 核验

`8.xlsx / Sensory names` 的 `R_name`（=4.csv 感官列名）↔ `CleanName_PanelFeedback`（=5.csv/6.csv 感官显示名）建映射；注意 5.csv 最后一个名字含 `\r\n(Trained panel)`（对应 4.csv 的 `overall`），归一空白后 **50/50 全部映射**。

| 校验项 | 5.csv | 6.csv |
|---|---|---|
| 实际维度（读入后） | **50 × 50**（文件 51 列 = 1 个行名索引 + 50 列） | **44 × 50**（文件 51 列 = 1 个行名索引 + 50 列） |
| 题面/说明口径 | 题面未写方法，只说“风味感官分析数据的相关性矩阵” | 题面称 **46×50** → **实测 44×50**（44 个化学/理化行 × 50 个感官列） |
| 行/列语义 | 感官 × 感官（方阵） | 行 = 化学/理化特征（44），列 = 感官属性（50） |
| 名称映射 | 4.csv 50 列 ↔ 5.csv 50 名，**50/50** | 44 行全部映射到 1.csv 列；50 列全部映射到 4.csv 列 |
| **= Spearman(4.csv)?** | **✅ 最大绝对误差 6.66×10⁻¹⁶** | **✅ 最大绝对误差 6.66×10⁻¹⁶** |
| 若误按 Pearson | 最大绝对误差 0.5406（肯定错） | 最大绝对误差 0.4618（肯定错） |
| 对称性 max\|M−Mᵀ\| | 0.0 | 非方阵，不适用 |
| 对角元 | 全 1.0 | 不适用 |
| NaN | 0 | 0 |
| 取值范围 | [−0.5021, 1.0] | [−0.5012, 0.8171] |
| 最小特征值 | +0.02343 → **PSD** ✅ | 非方阵，不适用 |

6.csv 的 44 个化学/理化行清单见 `6csv_vs_recomputed.csv`（含 Ethyl acetate、Ethanol、Isoamyl alcohol、Linalool、Diacetyl、4-vinylguaiacol、DMS、pH、Color、Sugars、Caloric value 等 44 项），均为 1.csv 231 特征中的子集。

---

## 5. 三方口径对照：题面 vs 数据说明 vs 实测

| 口径 | 原文（证据） | 实测结论 |
|---|---|---|
| 题面 PDF 第 3 页 | “表格 2 是化合物相关性矩阵。行、列都是化合物名，**单元格为皮尔逊相关系数**。” | ❌ **错**。2.csv 是 Spearman（误差 7.8×10⁻¹⁶） |
| `数据说明.txt` 第 2 条 | “文件名2 说明：所有化学参数之间的 **Spearman 相关系数**得分。” | ✅ **对** |
| `数据说明.txt` 第 4、5 条 | 5、6.csv 也都是 Spearman | ✅ **对**（5/6.csv 均在机器精度内复现 Spearman） |
| 题面：5.csv | “表格 5 是风味感官分析数据的相关性矩阵” | 实测 50×50，= Spearman(4.csv) |
| 题面：6.csv | “**46 个**化学/理化指标 × 50 个感官属性” | ❌ 实测 **44×50**（44 行） |
| 题面：样本数 | “226 种不同啤酒” | 实测 1.csv/4.csv 均 **250 行**（本报告只做相关取证，供其他任务汇总） |

**PDF 原文的独立取证**：本报告未引用 `A/` 目录，而是用系统 PDFKit 从 PDF 直接抽取文字：

```bash
# PDF SHA256 = 494025cf76c5d47af576927fcf6cd3a073d61db5842d56aaf0ad4da5f4660a78
cd /tmp && TMPDIR=/tmp swift -module-cache-path /tmp/swiftmod analysis/corr/pdftext.swift
```
抽取结果保存在 `analysis/corr/pdf_statement_extract.txt`（73 行，含第 3 页原文），哈希见 `pdf_sha256.txt`。

---

## 6. 可直接写进论文的表述（建议原文）

> 经独立重算核验，附件 `2.csv` 为 231×231 的**成对完整样本 Spearman 秩相关系数矩阵**（pairwise complete Spearman）：按 `8.xlsx` 的 `field_name_R` 将 `1.csv` 231 个特征与 `2.csv` 行列名一一映射后重算，26565 个非对角元素与文件值的最大绝对误差为 7.8×10⁻¹⁶（机器精度），逐元素相关系数为 1.000000；若按 Pearson 计算，最大绝对误差 1.12、中位误差 0.062，且有 4501/26565（16.9%）对元素符号相反。因此题面“单元格为皮尔逊相关系数”的表述有误，本文按数据说明采用 **Spearman** 口径解读该矩阵。

> 需说明该矩阵为成对完整样本估计：`1.csv` 存在 73 个缺失值（9 列），且 `2.csv` 并非半正定（最小特征值 −0.0424，5 个负特征值）。该现象在 pairwise-complete 相关矩阵中属正常，但若模型要求正定（如 Cholesky 分解、PCA 白化、高斯图模型），应先做最近半正定投影或收缩估计。

若论文需要更短的一句：**“2.csv 经复算为 Spearman 秩相关（最大误差 8×10⁻¹⁶），题面 Pearson 表述有误，按数据说明以 Spearman 使用。”**

---

## 7. 不确定性与使用建议

1. **无法从数据反推软件来源**（R `cor(method="spearman", use="pairwise.complete.obs")` 或 pandas `.corr("spearman")` 均可产生同结果）；但“成对完整 + 平均秩处理并列”这两个语义已被证明（listwise 误差 0.143 排除）。
2. 2.csv 中的数值精度为双精度输出；残余 7.8×10⁻¹⁶ 属浮点求和次序差异，不影响“完全相同”的判定。
3. **2.csv 非 PSD** 是数据事实而非缺陷：如需 PSD，做投影后再用，并在论文中声明。
4. 以下事项属于其他任务取证范围，本报告仅顺带记录、不展开：226 vs 250 样本、3.xlsx sheet 数、4.csv 的 0–6 还原、7.csv 维度。
5. 1.csv 的 4 个 `_sum` 汇总列（非 5 个）也计入 231×231 矩阵；若后续建模要去掉汇总列避免信息泄漏，需自行从 231 维中剔除并重算，本报告的 231 维结论不变。

---

## 8. 产出文件与复现

| 文件（均位于 `analysis/corr/`） | 内容 |
|---|---|
| `report.md` | 本报告 |
| `summary.json` | 结论 + 所有关键数字（机器可读） |
| `error_stats.json` | 5 种假设的矩阵级误差统计（max/median/q90/q99/逐元素相关/占比） |
| `matrix_properties.json` | 2.csv / 5.csv / 6.csv 的形状、对称性、对角、NaN、范围、最小特征值、PSD、映射覆盖 |
| `name_mapping_2csv_to_1csv.csv` | 231 行名称映射明细（含 `field_name_python`、`chemical_name`、是否汇总列） |
| `2csv_vs_recomputed.csv` | 26565 行逐元素对照：`value_2csv, spearman_recomputed, pearson_recomputed, pearson_log10, diff_*` |
| `2csv_spearman_recomputed.csv` / `2csv_pearson_recomputed.csv` | 重算出的 231×231 矩阵（可直接替代/对照） |
| `sample_pairs.csv` | 6 个决定性化合物对的数值 |
| `5csv_vs_recomputed.csv` / `6csv_vs_recomputed.csv` | 5/6.csv 逐元素对照（Spearman vs Pearson vs 文件值） |
| `pdf_statement_extract.txt`、`pdf_sha256.txt`、`pdftext.swift` | 题面 PDF 原文独立抽取证据与哈希 |
| `../scripts/corr_forensics.py` | **唯一复现脚本**（自包含，约 7 秒跑完，重写上述全部数值文件） |

复现（工作目录 `work/my-new-contest`，Python 为唯一可用运行时）：

```bash
/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3 \
    analysis/scripts/corr_forensics.py
```

脚本末尾会打印：映射覆盖率、5 种假设的 max/median 误差、2.csv 属性、5/6.csv 核验结果、决定性样例对。除 numpy/pandas/openpyxl 外无其他依赖。
