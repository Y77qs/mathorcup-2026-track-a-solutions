# 8.xlsx 全 sheet 审计 + 题面/数据说明 vs 实际文件差异

> 任务：`task-3`（reference-audit）。数据源：`work/my-new-contest/data/raw/`（只读，未做任何修改）。
> 题面原文引用自 `A/problem/statement.txt`（由同一 PDF `problem/2026年MathorCup大数据挑战赛-赛道A初赛.pdf` 抽取，PDF SHA256=`494025cf76c5d47af576927fcf6cd3a073d61db5842d56aaf0ad4da5f4660a78`）；数据说明引用自 `data/raw/数据说明.txt`。
> **本报告所有数据事实均由下列脚本从 raw 文件重算**，不引用 `A/` 目录的任何数据结论。

---

## 0. 结论先行（TL;DR）

1. **8.xlsx 实际 7 个 sheet**：`Sensory thresholds`(261×11)、`Sensory names`(101×8)、`GBM importance MDI`(232×2，231 个特征)、`GBM SHAP Values`(500×236)、`Calibrated chemical dataset`(250×73)、`Beer Prices`(250×11)、`Sheet2`(**空表 0×0**)。即“6 个有内容 + 1 个空表”，远不止数据说明里一句“其他相关数据”。
2. **8.xlsx 的 `Calibrated chemical dataset` 可直接定标 1.csv 的对数底数 = 10**：70 个化合物、17,371 个可比值中，**37/70 列满足 `1.csv 值 = log10(原始浓度)`**（逐列中位差 <1e-6，总体中位差 **2.9e-10**；例：pH `0.6248 = log10(4.215)`、color `0.7745 = log10(5.95 EBC)`、bitterness `0.5434 = log10(3.495)`、ethanol `-1.1549 = log10(0.07 v/v)`、CO2 `0.4914 = log10(3.1 PSI)`）。**结论：底数 10（不是 ln），且题面称“ethanol/color/bitterness/pH/CO2 保留原始量纲”与文件不符——它们也被 log10 变换。** 另有 13 列相差恰好约 1 个数量级（校准/稀释口径不同），其余 20 列偏差更大，需按化合物单独核对。
3. **`Sensory names` 是 4.csv 50 个感官维度的权威映射**：101 行 = `Trained panel` 50 行 + `Ratebeer` 51 行；Trained panel 的 `R_name` 与 4.csv 的 50 列**逐列 100% 对应（50/50）**；`CleanName_Paper` 给出规范名（如 `A_malt_all`→“Malt - overall”），`CleanName_PanelFeedback` 是 5.csv/6.csv 的列名口径（49/50 直接映射，Overall 1 个需换行归一化）。**不要把 101 当目标数，也不要把 Ratebeer 51 行混进 4.csv 目标。**
4. **`Sensory thresholds` 能支撑部分“超阈值判定”，但覆盖有限**：261 条记录，**仅 43 条有 threshold_mean/median（NA 83.5%）**，off_flavors 文本仅 7 条。对上 1.csv 的缺陷化合物：**DMS 17.25 µg/L、Diacetyl(2,3-butanedione) 0.299 mg/L、4VG 0.206 mg/L 有阈值**；**(E)-2-nonenal 无阈值**；**“Stale hops”不是单一化合物**（是 4.csv 的感官维度 `stale_hops`，相近气味线索 3-methyl-2-butenal 也无阈值）。名称可与 1.csv 对应 47（精确）/172（归一化）/228（宽松归一化）/261。
5. **`GBM importance MDI` 是单列聚合重要性（sum=1.000000）**：首行 `[NaN, 0]` 为残缺表头，231 个特征与 1.csv 231 列**100% 一一对应**，无目标维度列 → 只能解释为“50 个感官目标 GBM 的聚合 MDI”，**不能反推某个单一感官维度**。Top-3：`ethyl_acetate 0.2222`、`ethanol..v.v. 0.0670`、`ethyl_octanoate 0.0541`。
6. **`GBM SHAP Values` = 500 行 = 250 行 SHAP + 250 行 concentration**（236 列 = 4 元数据 + **232 特征列（231 个与 1.csv 同名 + 1 个常数 `base_prediction`=-0.326338）**）；**concentration 块与 1.csv 的 231 列 × 250 行逐值相等（57,677/57,677，最大差 8.9e-16）**；行序/beer_id/tasting_category_fine 与 1.csv 完全一致。它是**单目标** GBM 的 SHAP（行内加和 = 单目标预测），该目标与 4.csv/7.csv 任一感官列最大 |r| 仅 0.651（aftertaste），**无法对应到 50 个感官目标之一**。
7. **4.csv / 7.csv 的 `beer_id` 精度严重损坏（数据预处理必写）**：原文以 6 位有效数字科学计数法写出（如 `5.41023E+12`），**250 行只有 96 个唯一值**，36 个 ID 被 190 行共享、单值最多 20 行；与 1.csv 精确 ID 仅 37/250 字面相等。但 4.csv/7.csv 的 `beer` 列与行序、`tasting_category_fine` 与 1.csv **逐行 250/250 完全一致** → **跨表合并必须按 `beer`/行位置，禁止按 `beer_id` 连接 4/7.csv**。8.xlsx 的 `cal`/`SHAP`/`Beer Prices` 的 beer_id 则是 250 个完整精确 ID，与 1.csv 逐行 250/250 相等。
8. **2.csv / 5.csv / 6.csv 的相关系数类型实测均为 Spearman**（题面 P3 称 2.csv 为 Pearson，与文件不符；数据说明的 Spearman 正确）：1.csv 重算 vs 2.csv 的 **780/780 对**在 1e-6 内一致（中位差 1.1e-16；若按 Pearson 中位差 0.0462、最大 0.6137）；5.csv 1128/1176 对一致（95.9%，余 48 对疑因 0–6 并列秩处理）；6.csv 抽检 200/200 对一致。
9. **3.xlsx 是“公式驱动的空白评分卡模板”，不含任何实测 0–6 评分（重大口径风险）**：13 个 sheet = `beer_1…beer_12` + `summary`（题面说 10 个、对应 Beer# 1–10，不符）。每个 beer sheet（101×33）有 **54 个公式**：`=IF(ISBLANK(O7),…,0,1),2)…6)` 把 0–6 刻度上的打钩位置换算成分数，`=IF(ISBLANK(C10),0,Q7)` 做占位；但**全表无任何打钩**，评分格计算值全 0（每 sheet 仅 25 个非图例数字：Beer# + 24 个 0）。`summary`（13×52）有 **612 个公式** `=beer_N!$Q$x / $AG$x`，即 12 行 beers × 50 维逐格引用 12 个 beer sheet，缓存值 **600 格全为 0（无 NA）**。因此 3.xlsx 只提供“评分卡/0–6 计算口径”，不能当监督标签，0–6 分只能理解为“按该口径输出预测/分级”。
10. **7.csv 语义**：250×189 = 3 元数据 + **186 感官列（aroma_ 62 + palate_ 62 + taste_ 62）**（题面写 187 个感官属性，不符）；3 列全 NA（`palate_acetaldehyde/palate_acetate/palate_dentist`，各 250 个，共 750）；列均值≈0（183/186 列 |mean|<0.1）、列标准差中位 **1.003**（186 列中 164 列 ∈[0.99,1.01]，另 19 列 0.82–0.99、2 列 0.22/0.37 为压缩列，3 列全 NA）、73.9% 单元格为负、范围 [-4.94, 15.81] → 与 4.csv 同为**标准化/中心化连续值**；且与 4.csv **同批 250 个样本的不同导出**（beer 顺序、类别逐行一致，beer_id 同样 6 位精度、二者完全相同），**不能当独立外部感官先验**。

---

## 1. 复现方式（全部脚本在 `analysis/scripts/`）

```bash
PY=/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
cd /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest
$PY analysis/scripts/ref_8xlsx_audit.py    # 8.xlsx 7 个 sheet 逐一审计 → 8xlsx_details.json / inventory / 列清单
$PY analysis/scripts/ref_crosscheck.py     # 行序/主键/类别一致性 + 2/5/6.csv 相关类型 + 7.csv 语义 → crosscheck.json
$PY analysis/scripts/ref_discrepancies.py  # 差异清单（数字运行时复核并 assert）→ discrepancies.csv|md
```
- 只依赖 pandas/numpy/openpyxl（唯一可用 Python 环境），无 scipy（Spearman 用 `rank().corr()` 自实现）。
- 只读 `data/raw/`；写盘范围严格限定 `analysis/ref/` 与 `analysis/scripts/ref_*.py`。

---

## 2. 8.xlsx 逐 sheet 规格（完整机器可读清单见 `analysis/ref/8xlsx_inventory.csv|md`）

### 2.1 `Sensory thresholds`（261×11，第 0 行表头）
- 列：`field_name_python, field_name_R, chemical_name, chemical_name_short, calibrated, origin_paper, unit, aging, off_flavors, threshold_mean, threshold_median`。
- **1 行 = 1 个化合物/风味物质的感官阈值记录**，共 261 条。
- 关键统计：`threshold_mean` 非空 **43/261**、`threshold_median` 非空 43（大量记录只有名称没有阈值）；`off_flavors` 非空 **7**；`aging` 非空 26（increase 18 / decrease 8）；`calibrated` 有值 68（`yes` 23、`yes_gcms` 33、`yes_gcms,yes` 8+4）。
- `unit` 分布：mg/L 52、A.U. 10、ug/L 5、g/L 4、IBU/v/v/kcal%/PSI/EBC/pH 各 1，其余 184 空。
- `origin_paper`：Hops 90、Yeast 82、Spices 28、Malt 24、Others 22、Wild flora 6、Internal standard solution 5、空 4。
- 阈值范围：mean [0.0245, 416.67]（中位 1.5；<1 的 16 条），median [0.0045, 400]。
- **缺陷化合物定位（用于问题 3 的“超阈值”口径）**：

| 缺陷项 | 阈值表对应记录 | threshold_mean | threshold_median | unit | off_flavors |
|---|---|---|---|---|---|
| DMS | `DMS` / Dimethyl sulfide | 17.25 | 19.0 | µg/L | cooked vegetables, onion, garlic, corn, black currant, sulfidic, cabbage… |
| Diacetyl | `2,3-butanedione` / Diacetyl | 0.29925 | 0.09 | mg/L | butterscotch, popcorn, oily, milky |
| 4VG | `X4VG` / 4-vinylguaiacol | 0.20633 | 0.20 | mg/L | （空） |
| trans-2-nonenal | `(E)-2-nonenal` / E-2-nonenal | **无** | **无** | mg/L | （空） |
| Stale hops | 无单一化合物记录（相近 `3-methyl-2-butenal` 无阈值）；4.csv 有感官维度 `stale_hops` | — | — | — | — |

- 名称与 1.csv 可对应：精确 47/261；归一化（去非字母数字）172/261；宽松归一化（再去前导 X）**228/261**。
- **用途**：可为 DMS/双乙酰/4VG 提供“浓度 vs 阈值”判定与化学合理性先验；trans-2-nonenal、stale hops 须改用 4.csv 感官值/文献阈值补齐；注意 DMS 单位 µg/L 与 Diacetyl/4VG 的 mg/L 不同，比较前必须统一单位（1.csv 是 log10 浓度，需先 `10^v` 还原）。

### 2.2 `Sensory names`（101×8，第 0 行表头）
- 列：`dataset, R_name, Category_Paper, Category, CleanName_Paper, CleanName_PaperLong, CleanName_PanelFeedback, DataType`。
- **1 行 = 1 个感官维度定义**；`dataset`：`Trained panel` **50** 行 + `Ratebeer` **51** 行。
- **Trained panel 50 行的 `R_name` 与 4.csv 的 50 个感官列 100% 逐列对应（50/50）** → 是 4.csv 目标的权威名称/归类表。
- `Category_Paper`：Aroma 30、Taste 56、Palate 7、Overall 4、texture 1、空 3；`Category`：Yeast 24、Others 23、Hops 20、Malt 20、Wild flora 4、空 10；`DataType`：numeric 26、categorical 24、空 51。
- 命名体系桥接：4.csv 用 `R_name`（如 `A_malt_all`）；5.csv/6.csv 用 `CleanName_PanelFeedback`（如 “Malt aroma - overall”）；`CleanName_Paper` 为“Malt - overall”。**Ratebeer 51 行是 7.csv 体系的命名（7.csv 186 列中 44 列与其同名）**，与 4.csv 的 50 目标无关。
- **用途**：问题 1/2 的 targetColumns 命名与中英对照、Aroma/Flavour/Palate/Faults 归类；5.csv/6.csv 列名对齐。

### 2.3 `GBM importance MDI`（原始 232×2 = 残缺表头 1 行 + 231 行）
- 首行 `[NaN, 0]` 无列名；其后柱 0=importance(float)、柱 1=feature(name)；**1 行 = 1 个化合物特征的重要性**，共 231 个。
- **231 个特征与 1.csv 231 列 100% 一一对应**（无缺、无多）。
- 值统计：**sum = 1.000000**（归一化重要性），min 5.39e-5、median 0.001279、max 0.222213；无 0 值。
- **无目标/感官维度列 → 是 50 个感官目标聚合后的单列 MDI**（不能当单目标归因）。
- Top-10（完整见 `analysis/ref/mdi_top10.csv`）：`ethyl_acetate 0.2222`、`ethanol..v.v. 0.0670`、`ethyl_octanoate 0.0541`、`ethyl.phenylacetate 0.0462`、`lactic_acid.mg.L. 0.0442`、`protein.g.L. 0.0240`、`MeSH 0.0236`、`styrene 0.0228`、`acids_sum 0.0219`、`isopentyl.hexanoate 0.0190`。
- **用途**：问题 2 的全局特征重要性交叉验证（与 2.csv 共表达图、Bootstrap Top-3 对照），须注明目标口径为聚合值。

### 2.4 `GBM SHAP Values`（500×236，第 0 行表头）
- 列：`data, beer, beer_id, tasting_category_fine` + **232 个特征列** = 1.csv 的 231 个特征（同名）+ `base_prediction`；完整列清单 `analysis/ref/shap_columns.csv`。
- **行由 `data` 列分块：`SHAP` 250 行（每个样本每个特征一个 SHAP 值）+ `concentration` 250 行（特征取值）**；两块行序完全相同（beer 10, 86, 2, …）。
- **concentration 块 = 1.csv**：231 列 × 250 行 **57,677/57,677 个单元格 |diff|<1e-9**（最大差 8.9e-16）→ SHAP 的输入特征就是 1.csv 的 log10 特征。
- `base_prediction` 为常数 **-0.3263382109**（250 行同值）；SHAP 值范围 [-0.6407, 0.1358]；行内加和 [-2.5866, 1.6983]（中位 0.1331）→ 单目标可加性成立。
- 样本覆盖：250 个唯一 beer_id，22 个 `tasting_category_fine` 风格（Blond 62、Tripel 56、Strong ale 36、Hoppy 34、Stout/Porter 26、Wheat/Amber/Brown 各 24、Pils/Lager/Lambic 各 22、Dubbel/Kriek/Saison 各 20…）。
- **目标识别**：`pred = base + ΣSHAP` 与 4.csv/7.csv 全部感官列求相关，最大 |r| = **0.651（4.csv aftertaste）**，远小于 1 → **该 SHAP 对应一个未在 4/7.csv 中单列的目标**，不能自称“50 个感官目标的 SHAP”。
- **用途**：问题 2 可作“化合物→单目标预测”的局部解释示例；不可与 4.csv 的 50 目标归因混称。

### 2.5 `Calibrated chemical dataset`（250×73，第 0 行表头）
- 列：`beer, beer_id, tasting_category_fine` + **70 个经校准的化合物列**（原始浓度量纲）；完整列清单 `analysis/ref/calibrated_columns.csv`。
- 行/主键：250 行、250 个唯一 beer_id，**与 1.csv 逐行 beer/beer_id/tasting_category_fine 完全一致（250/250）**。
- 与 1.csv 关系：70 个同名化合物；1.csv 另有 **161 列**不在该表 → **不能整体替代 1.csv**，只能作**补充**（原始浓度/校准证据）。
- **核心发现（对数底数）**：逐值比较 `1.csv v` vs `log10(该表原始浓度)`：
  - **37/70 列完全满足 `v = log10(c)`**（逐列中位差 <1e-6；总体中位差 2.9e-10）；
  - **13/70 列相差恰好约 1 个数量级**（`0.7 < |v-log10(c)| < 1.4`，即校准/稀释差 10 倍）；
  - 其余 20 列偏差更大（如 ethyl.nicotinate、furfural 等痕量物质），需逐化合物核对；
  - **理化参数同样被 log10**（题面称“保留原始量纲”与文件不符）：pH `0.6248 ↔ 4.215`、color `0.7745 ↔ 5.95 EBC`、bitterness `0.5434 ↔ 3.495`、ethanol `-1.1549 ↔ 0.07 v/v`、CO2 `0.4914 ↔ 3.1 PSI`（`10^1.csv值 = 原始值`）。
- NA：全表 69 个 NA（17 列有 NA；CO2.PSI. 39、benzyl.alcohol 4、geraniol 4、ethyl.isobutyrate 3、diethyl.succinate 3、benzaldehyde 3、linalool 3，其余 1）。
- **用途**：① 证明 1.csv 对数底数为 10（论文“自行核实变换底数”的硬证据）；② 还原 70 个核心化合物的原始浓度用于阈值比对与化学可解释性；③ 不可替代 1.csv。

### 2.6 `Beer Prices`（250×11，第 0 行表头）
- 列：`beer, beer_id, tasting_category, ABV` + 7 个渠道价格：`Price_TotalWine_USA, Price_Colruyt_Belgium, Price_Delhaize_Belgium, Price_BeerHawk_UK, Price_TheBelgianBeerShop_global, Price_TheBelgianShop_global, Price_BeerOfBelgium_global`。
- 主键：`beer` = 1–250 升序索引；`beer_id` 与 1.csv **按 beer 合并后 250/250 完全相等**（该表是 1.csv 样本的 250 个完整 ID，无损）。
- 缺失：7 列价格 NA 分别为 164/170/159/204/156/43/109，**合计 1005**；有任一价格的样本 **229/250**，所有价格全缺 **21 行**；价格中位（美元/欧元口径见列名）：TotalWine 13.74、Colruyt 4.00、Delhaize 4.28、BeerHawk 11.59、TheBelgianBeerShop 8.40、TheBelgianShop 17.71、BeerOfBelgium 7.65。
- `ABV`：0–12（中位 6.75）；`tasting_category` 采用下划线命名（`low_no alcohol` vs 1.csv `Low/No alcohol`），需映射。
- **用途**：外部/商业协变量（价格—风格—ABV—风味关联、缺失机制分析）；不进化合物特征矩阵；按 beer 合并，注意高缺失率（部分列缺失 62%–82%）。

### 2.7 `Sheet2`
- **空表：0 行 × 0 列，无任何单元格**（`is_empty=True`，`n_cells=0`）→ 8.xlsx 名义 7 sheet、有效 6 sheet；读取时跳过。

---

## 3. 交叉一致性核验（脚本：`analysis/scripts/ref_crosscheck.py` → `analysis/ref/crosscheck.json|csv`）

| 对比 | beer 行序 | tasting_category_fine | beer_id（精确） | 备注 |
|---|---|---|---|---|
| 1.csv vs 4.csv | **250/250 一致** | **250/250 一致** | 仅 37/250 字面相等 | 4.csv beer_id 为 6 位有效数字（96 个唯一值，36 个 ID 被 190 行共享，单值最多 20 行）→ 用 beer/行序 |
| 1.csv vs 7.csv | **250/250 一致** | **250/250 一致** | 仅 37/250 字面相等 | 与 4.csv 完全相同的 beer_id 精度问题 |
| 4.csv vs 7.csv | **250/250 一致** | **250/250 一致** | 4/7 之间逐值全等 | 同一批样本；两表感官列名重合 **0**（4.csv=50 维品评面板，7.csv=186 维描述符） |
| 1.csv vs 8.xlsx `Calibrated` | 250/250 | 250/250 | **250/250** | 8.xlsx 主键无损 |
| 1.csv vs 8.xlsx `SHAP`（两个块） | 250/250 | 250/250 | **250/250** | concentration 块数值 = 1.csv（57677/57677） |
| 1.csv vs 8.xlsx `Beer Prices` | 按 beer 合并 250/250 | 命名体系不同 | 合并后 **250/250** | BP 按 beer 1–250 升序 |
| 4.csv vs 8.xlsx `Sensory names` | — | — | — | R_name 与 4.csv 50 列 **50/50** 对应 |
| 3.xlsx 结构 | — | — | — | 13 sheet；`summary` 12 行×50 维（612 个 `=beer_N!Q/AG` 公式）；12 个 beer sheet 各 101×33（各 54 个评分/占位公式）；共 1260 个公式，无打钩标记、缓存值全 0 |

相关系数类型（实测）：

| 矩阵 | 与 1.csv/4.csv 重算比较 | 判定 |
|---|---|---|
| 2.csv（231×231） | 780/780 对与 Spearman 在 1e-6 内一致（中位差 **1.1e-16**）；若按 Pearson 中位差 0.0462、最大 0.6137 | **Spearman**（题面写 Pearson 错） |
| 5.csv（50×50） | 1176 对中 1128 对（95.9%）与 Spearman 一致，48 对偏差最大 0.812（疑 0–6 并列秩处理） | **Spearman** |
| 6.csv（44×50） | 抽检 200/200 对与 Spearman 一致 | **Spearman**；列名与 5.csv 完全同序 |

### 3.1 3.xlsx 评分卡结构（与问题 1 的“0–6 分”口径直接相关）

- `beer_1…beer_12`：每 sheet 101×33，是一个**双面板纸质评分表电子化**：左面板 Aroma（列 B–P）、右面板 Flavour（列 R–AF），每个维度一行，0–6 刻度画在奇数列（E/G/I/K/M/O 与 U/W/Y/AA/AC/AE），打分时在对应刻度单元格打钩。
- 每个 sheet 有 **54 个公式**：Q 列 `=IF(ISBLANK(O7),IF(ISBLANK(M7),…,IF(ISBLANK(E7),0,1),2),3),4),5),6)` 把左面板打钩位置换算成 0–6 分，AG 列对右面板同理；`=IF(ISBLANK(C{n}),0,Q{m})` 为无该维度时的占位。**当前文件无任何打钩，因此计算结果全 0。**
- `summary` 13×52：第 1 行表头，12 行 = Beer 1–12；B2:AZ13 每格为 `=beer_{k}!$Q${r}` 或 `$AG${r}`（共 **612 个公式**），即把 12 个 sheet 的 50 维分数汇总到 1 张表；缓存值全 0。最后两列为 `overall` 与 `comments`（文本列，当前为 0）。
- 结论：3.xlsx 给出的是**评分卡定义（维度名 + 0–6 刻度 + 汇总公式）**，不是实测标签；其中列名与 4.csv 的 50 维一一对应（个别拼写差异：`A_ester_fruity` vs `A_esters_fruity`、`4vg` vs `X4vg`），可作问题 1 的输出格式与 0–6 分级规则的依据。

---

## 4. 7.csv 语义核验（细节见 `crosscheck.json → csv7`）

| 项 | 数值 |
|---|---|
| 形状 | 250×189 = 3 元数据 + **186 感官列**（aroma_ 62 + palate_ 62 + taste_ 62） |
| 全 NA 列 | **3 列**：`palate_acetaldehyde`、`palate_acetate`、`palate_dentist`（各 250，合计 **750 个 NA**，无其他 NA） |
| 取值范围 | [-4.9359, 15.8115]；**73.93%** 单元格为负 |
| 是否标准化 | 列均值：183/186 列 \|mean\|<0.1（中位 0.0015）；列标准差：中位 **1.003**，164/186 列 ∈[0.99,1.01]、另 19 列 0.82–0.99、2 列 0.22/0.37、3 列全 NA → 与 4.csv 同为标准化/中心化连续值（非 0–6 原始分） |
| 与 4.csv 关系 | 同一批 250 样本、行序/类别逐行一致、beer_id 值与精度完全相同；**感官列名重合 0** |
| 与 Sensory names | 186 列中 44 列与 `Ratebeer` 51 个 R_name 同名；6 个 Ratebeer 名称（appearance_5、aroma_10、ave_score_5、overall_20、palate_5、taste_10）不在 7.csv |
| 能否当独立外部感官数据 | **不能**。数据说明称“论坛评论数据”，实际是数值化标准化感官矩阵，且与 4.csv 同源同批（不同描述符体系导出），当“独立先验”会造成同源泄漏；可作补充特征/多视图，但训练/验证必须按样本切分 |

---

## 5. 题面/数据说明 vs 实际文件：差异清单

完整 19 条（含原文、实际事实、证据、处理建议）见 **`analysis/ref/discrepancies.md`**（人工阅读版）与 **`analysis/ref/discrepancies.csv`**（机器版）。摘要：

| ID | 主题 | 题面/数据说明 | 实际文件事实 |
|---|---|---|---|
| D01 | 样本量 | 题面“226 种不同啤酒” | 1/4/7.csv 均 **250 行/250 唯一 beer_id**；8.xlsx 各表 250；3.xlsx summary 仅 12 |
| D02 | 2.csv 相关类型 | 题面“皮尔逊”；数据说明“Spearman” | **Spearman**（780/780 对 1e-6 内一致） |
| D03 | 5.csv | 数据说明 Spearman | **Spearman**（1128/1176 对一致，95.9%） |
| D04 | 6.csv 形状 | 题面 46 行×50 列 | **44 行×50 感官列**（44×51 含索引；列名与 5.csv 完全同序） |
| D05 | 3.xlsx sheet 数 | 题面 10 个（beer_1~beer_10） | **13 个：beer_1…beer_12 + summary** |
| D06 | 3.xlsx 内容（重大） | 题面称 0–6 人工评分卡/目标标签 | **公式驱动的空白评分卡**（beer_*=54、summary=612 公式，共 1260 个）：无打钩，12 个 beer sheet 评分格全 0；summary 12×50 **600 格缓存值全 0**，无任何实测评分 |
| D07 | 目标维度数 | 题面“约 40 个感官维度” | 4.csv **50** 个感官列（A_*15 + F_*15 + 其余 20）；3.xlsx summary 也 50；“Aroma+Flavour 两套”本身 30 |
| D08 | 4/7.csv beer_id 精度 | 题面未提 | **6 位有效数字**（`5.41023E+12`）：250 行仅 96 唯一值，单值最多 20 行；必须按 beer/行序合并 |
| D09 | 7.csv 形状 | 题面“250×187 个感官属性” | **250×189 = 3 元数据 + 186 感官列**；3 列全 NA（750 个 NA） |
| D10 | 7.csv 语义 | 数据说明“论坛评论数据” | 数值化标准化感官矩阵（列均值≈0、标准差≈1、73.9% 负值）；与 4.csv 同批样本的不同导出 |
| D11 | 1.csv 化合物数 | 题面“200 多种风味化合物” | **231 特征列 = 226 个个体测量/化合物 + 5 个派生属性**（kcalperc、esters_sum、aroma_hops_sum、acids_sum、sulfur_sum） |
| D12 | 1.csv 对数底数 | 题面“自行核实 log10 或 ln；ethanol/color/bitterness/pH/CO2 保留原始量纲” | **底数 = 10**；且 5 个理化参数也做了 log10（pH 0.6248=log10 4.215 等），**并非原始量纲** |
| D13 | 8.xlsx 定位 | 数据说明“其他相关数据”；题面“一些综合参考数据” | **7 个结构化 sheet**（6 有效 + 1 空）：阈值/名称/MDI/SHAP/校准浓度/啤酒价格 |
| D14 | MDI 口径 | 无说明 | 231 特征单列重要性、sum=1，无目标列 → **50 目标聚合值**，不能单目标归因 |
| D15 | SHAP 口径 | 无说明 | 500 行 = 250 SHAP + 250 concentration；**单目标 SHAP**（base=-0.3263 常数），目标无法对应 4/7.csv 任一列 |
| D16 | 缺陷阈值覆盖 | 题面以 DMS/Diacetyl/4VG/trans-2-nonenal/Stale hops 超阈值为准 | 阈值表仅 **43/261** 有阈值、7 条 off_flavors；DMS/Diacetyl/4VG 有阈值，**trans-2-nonenal 无阈值**，**Stale hops 非单一化合物** |
| D17 | Sensory names | 无说明 | 101 行 = 50 Trained panel（与 4.csv **50/50** 对应）+ 51 Ratebeer（7.csv 体系）；不是 101 个目标 |
| D18 | Beer Prices | 无说明 | 250×11，7 渠道价格、**1005 个 NA**、21 行全缺、229 行有任一价格；ABV 0–12 |
| D19 | Sheet2 | 无说明 | **空表 0×0** |

---

## 6. 对论文“数据预处理”章节可直接引用的结论

1. **样本与主键**：以 1.csv 的 250 个样本为主表；`beer_id` 为唯一权威 ID；4.csv/7.csv 的 `beer_id` 已被写成 6 位有效数字（96 个唯一值），**只能用 `beer`/行位置对齐**；8.xlsx 的 cal/SHAP/Beer Prices 的 beer_id 完整可用。
2. **变换底数**：`1.csv = log10(原始浓度)`（log base 10，不是 ln），依据是 8.xlsx `Calibrated chemical dataset` 70 个化合物的原始浓度（37/70 列精确一致，中位差 2.9e-10）；原始量纲还原用 `10^v`。**且 pH/color/bitterness/ethanol/CO2 也被 log10**，题面“保留原始量纲”的说法需在论文中纠正并说明。
3. **特征口径**：231 列 = 226 个体化合物 + 5 个派生属性（kcalperc、esters_sum、aroma_hops_sum、acids_sum、sulfur_sum）；相关性/共表达分析应把派生列与个体列分层讨论，避免用派生列当“化合物证据”。
4. **目标口径**：4.csv 的 50 个感官列是标准化连续值，**不是 0–6 原始分**；3.xlsx 是公式驱动的空白评分卡（1260 个公式、无打钩、缓存值全 0），**不能当标签**，但它给出 0–6 的评分维度/刻度/汇总口径；0–6 分只能作为输出口径/分级规则，需另给还原映射假设（4.csv 无法逐值反推 0–6，只能按分布/分位映射，或按 3.xlsx 评分卡的维度定义对齐）。
5. **相关矩阵**：2.csv/5.csv/6.csv 全部为 **Spearman**（实测）；题面 Pearson 为笔误；论文在数据说明处写“Spearman（数据说明与实测一致，题面 Pearson 与文件不符）”。
6. **8.xlsx 的使用**：`Sensory names`（4.csv 50 维权威映射）、`Sensory thresholds`（DMS/Diacetyl/4VG 缺陷阈值判定，其余需补）、`GBM importance MDI`（全局重要性交叉验证，聚合口径）、`GBM SHAP Values`（单目标局部解释，非 50 目标）、`Calibrated chemical dataset`（对数底数与原始浓度核验，不替代 1.csv）、`Beer Prices`（外部协变量，21 行全缺）；`Sheet2` 空表跳过。
7. **7.csv 的使用**：与 4.csv **同源同批**（不能当独立外部感官先验）；可作 186 维补充特征/多视图对比，注意 3 个全 NA 列与 183 个可用列；与 4.csv 感官列名零重合，须经 Sensory names 或人工映射后再融合。

---

## 7. 存疑点与交接（需 Lead/其他同学确认）

1. **D06 是全局口径风险**：3.xlsx 全 0 意味着“0–6 分标签”在数据中不存在。问题 1 的合理读法只能是“按 3.xlsx 评分卡定义输出预测分数”；若队内有人把 3.xlsx 当监督目标训练会直接错。建议 Lead 在论文问题分析中明确写“3.xlsx 为评分卡模板（无实测值），0–6 标签不可得；本文按 4.csv 标准化值建模并给出 0–6 映射口径”。（已同步 Lead）
2. **GBM SHAP 的目标未知**：concentration 块 = 1.csv 已确证，但 `base_prediction=-0.3263`、单目标预测与 4/7.csv 任一列最大 |r| 仅 0.651，无法唯一命名该目标。使用其归因结论时必须注明“未标注单目标”，不能写成“某感官维度”。
3. **MDI 是聚合值**：sum=1、无目标列，无法拆到 50 个感官维度；若问题 2 需要逐目标重要性，须自己训练多输出/逐目标模型。
4. **阈值表 13 列相差 10 倍**：37/70 列精确 log10、13 列相差约 1 个数量级——若用 Calibrated 还原原始浓度做阈值比对，这 13 列（及另 20 列偏差更大的痕量物质）需逐列核对校准口径，否则超阈值判定会差一个数量级。
5. **5.csv 48 对不一致**：疑 0–6 原始序数的并列秩处理差异；若论文强依赖个别 5.csv 相关系数，建议用 4.csv 重算该对。
6. **题面 PDF 文本引用**：本报告题面原文按 `A/problem/statement.txt`（Lead 提供，PDF SHA 已核验）引用；本机无 pdftotext/PyPDF，未二次从 PDF 抽文本，但该 txt 与 PDF 同源且 SHA 已核验，数据事实全部来自 raw。

---

## 8. 交付物清单（均在 `work/my-new-contest/analysis/` 下）

| 路径 | 内容 |
|---|---|
| `ref/report.md` | 本报告（结论先行 + 逐 sheet + 交叉核验 + 7.csv + 差异摘要 + 预处理结论） |
| `ref/8xlsx_inventory.csv` / `ref/8xlsx_inventory.md` | 7 个 sheet 的 shape/表头/行语义/关键统计/建模用途 |
| `ref/8xlsx_details.json` | 全部审计的机器可读明细（NA、分布、缺陷化合物、MDI top10、SHAP 分块、校准对比等） |
| `ref/discrepancies.csv` / `ref/discrepancies.md` | 19 条题面/数据说明 vs 实际事实差异（含证据与处理建议） |
| `ref/crosscheck.json` / `ref/crosscheck.csv` | 行序/主键/类别一致性、2/5/6.csv 相关类型、7.csv 语义 |
| `ref/mdi_top10.csv`、`ref/shap_columns.csv`、`ref/calibrated_columns.csv`、`ref/sensory_thresholds_clean.csv`、`ref/sensory_names_clean.csv`、`ref/beer_prices_na.csv` | 各表列清单/整理版（供其他章节直接引用） |
| `scripts/ref_8xlsx_audit.py`、`scripts/ref_crosscheck.py`、`scripts/ref_discrepancies.py` | 复现脚本（只读 raw，输出上述文件） |
