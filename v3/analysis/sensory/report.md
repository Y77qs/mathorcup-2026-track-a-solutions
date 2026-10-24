# 感官目标（targetColumns）与 0–6 分口径取证报告

- 任务：共享任务 `task-2`（Team 成员 `sensory-targets`）
- 数据（只读）：`work/my-new-contest/data/raw/` 下 `3.xlsx`、`4.csv`、`5.csv`、`8.xlsx`（行号/单元格坐标均为原始文件实测）
- 复现脚本：`analysis/scripts/sensory_01_xlsx_forensics.py`、`sensory_02_scale_stats.py`、`sensory_03_align_targets.py`
- 产出：`analysis/sensory/targetcolumns.csv`（50 行对齐清单）、`scale_stats.csv`（50 列逐列统计）、`mapping_analysis.csv`（映射量化）、`scale_hypothesis_tests.json`、`xlsx_forensics.json`、`xlsx_summary_formula_map.csv`、`xlsx_beersheet_inventory.csv`、`alignment_checks.json`
- 复现：`/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3 analysis/scripts/sensory_0{1,2,3}_*.py`

---

## 0. 结论速览（可直接进论文/汇报）

1. **最终 targetColumns = 50 列**，即 `4.csv` 的 50 个感官列：Aroma 侧 `A_*` 15 列 + Flavour 侧 `F_*` 15 列 + 口感/缺陷/辅料/总体 20 列。`3.xlsx` 的 `summary` 定义的数值感官列恰好也是 50 列（另有 1 个 `comments` 文本列，不建模），两者一一对应。题面"共约 40 个"既不等于 Aroma+Flavour 两套的 30，也不等于实际 50/51，是题面对附件的概括误差——论文应写 **50**，并说明"30（A+F 两套）+ 20（口感/缺陷/辅料/总体）"的口径。
2. **`3.xlsx` 是空白评分卡模板，不含任何真实 0–6 评分，不能作为 0–6 监督标签来源**：12 个 beer sheet 结构彼此完全相同（每个 sheet 54 个公式、199 个数字、63 个文本；数字 100% 是 0–6 刻度标签与 `S3` 的 Beer#），**被勾选/填写的分值单元格 = 0**；`summary` 为 12 行×52 列，除 A 列 Beer=1..12 外全部是跨表公式（共 612 个），`data_only=True` 的计算值**全为 0**。3.xlsx 只提供：0–6 离散刻度语义、50 个感官维度定义、评分卡公式逻辑。
3. **`4.csv` 既不是 0–6 原始分，也不是逐列 z-score**：50 列、每列 n=250、无缺失、全部非整数；逐列 `mean≈0` 但不精确为 0（\|mean\|≤0.0628，平均 0.0212）；逐列 `sd = 0.3697–0.8585`（均值 0.5679），**没有一列 sd 落在 [0.95,1.05]**；**60.94% 的单元格 <0**（7617/12500），最大 `clove = 6.1724 > 6`。合理解释：**列内中心化 + 一个共同的缩放系数**（列均值被抹掉，各列只保留相对离散度），来源样本与本 250 行并不完全一致（否则均值应为机器精度 0）。
4. **原始 0–6 分不能精确还原**（信息论上不可识别）：3.xlsx 无任何真实评分；`4.csv` 已把每列原始原点 `a_j` 完全消去，任何逐列仿射反演 `x = a_j + b·z_j` 中 `b` 的可行上界仅 0.9315（`clove` 极差决定），`a_j` 无任何文件可提供。两种都"保序且落入 [0,6]"的自然映射（列内 min-max vs 列内秩映射）逐单元格平均相差 **1.52 分**、最大 **4.94 分**——例：`clove` 的 beer 181 在 min-max 下为 0.059（"未检出"），在秩映射下为 3.012（"中等"），观测数据无法区分谁对。
5. **论文诚实口径**：主目标 = 标准化连续感官强度（报告为 standardized continuous score，不叫 0–6 分）；若题目强制要求"0–6 分制分级结果"，只能额外给出**映射分级分（mapped 0–6 grade）**，并显式声明：映射方式、端点假设、"非原始 0–6 分"、每列映射对 RMSE 的尺度系数（**0.9315–2.9498**，相差 3.17 倍），禁止与文献/评分卡绝对值直接比较。

---

## 1. `3.xlsx` 逐 sheet 取证

### 1.1 结构总览（openpyxl data_only=False/True 双开）

| sheet | 维度 | 公式数 | 数字单元格 | 文本单元格 | 已填写分值单元格 |
|---|---|---|---|---|---|
| beer_1 … beer_12（12 个） | `A1:AG101` | 54 | 199 | 63 | **0** |
| summary | `A1:AZ13` | 612（12×51） | 12（A 列 Beer=1..12） | 52（表头） | 0（全部为公式计算结果） |

- 12 个 beer sheet 的结构签名 `(公式,数字,文本,已填分值)` 完全相同：`(54,199,63,0)`（脚本 `xlsx_forensics.json → beer_sheets_signature`）；差异只有 `S3`（"Beer#:" 后的 1..12）。
- `merged_cells` 为空、`data_validations` 为 0、`images` 为 0（`beer_1` 实测），即**没有表单控件/复选框**，勾选只能靠往单元格里打字。
- 依据：`analysis/scripts/sensory_01_xlsx_forensics.py`；证据字段见 `analysis/sensory/xlsx_forensics.json`。

### 1.2 12 个 beer sheet 是"空白评分卡"，不是"已填写的评分"

判定依据（每条可复核）：

1. **已填分值单元格 = 0**。剔除 54 个公式、17 行 0–6 刻度标签（`C8..O8`/`S8..AE8` 等，行号 8,21,34,46,51,55,59,63,69,73,77,83,87,91,95,98,101）、`S3` 的 Beer#、63 个属性/组名文本后，没有任何其它数字或标记；也没有 `x/✓/1` 之类的勾选字符。
2. `S3=1..12` 说明 12 个 sheet 分别对应 "Beer# 1..12"，与 `4.csv` 的 250 个样品相比，**覆盖率上限只有 12/250 = 4.8%**（且实际为 0，因为空白）。
3. 0–6 刻度的存在证明它是**评分卡设计**（这些是模板元素，不是数据）：
   - 每个属性块都有一行刻度数字：`beer_1!C8=0, E8=1, G8=2, I8=3, K8=4, M8=5, O8=6`（右半同理 `S8=0 … AE8=6`）；完整 0–6 刻度块共 **15 个**（行 8,21,34,46,51,55,59,63,69,73,77,83,87,91,95），另有 2 个锚点行（`C98=0`、`C101=6`）。
   - 0/6 锚点文字：`E97='Not present'` + `C98=0`；`E100='Predominant/overwhelming'` + `C101=6`。
   - 编码公式（把"刻度位置是否被标记"转成 0–6 整数）：
     - `Q7 = IF(ISBLANK(O7),IF(ISBLANK(M7),IF(ISBLANK(K7),IF(ISBLANK(I7),IF(ISBLANK(G7),IF(ISBLANK(E7),0,1),2),3),4),5),6)`（Aroma 侧组级分值，`AG7` 为 Flavour 侧镜像，检查 `AE7..U7`）
     - 子项公式：`Q10 = IF(ISBLANK(C10),0,Q7)`、`AG10 = IF(ISBLANK(S10),0,AG7)`：子属性未标记则记 0，标记则继承组级 0–6 分值。
   - 编码语义：全部刻度空白 → 0；在 E7/G7/I7/K7/M7/O7 中标记第 k 个位置 → 分别得 1/2/3/4/5/6。即 **0–6 为整数离散等级，0 = not present**。
4. `summary` 的 `data_only=True` 计算值全为 0：`summary!B2='=beer_1!$Q$7'` … `AY13='=beer_12!$Q$94'`，因为被引用单元格全空，`IF(ISBLANK(...))` 级联全部返回 0。`summary` 数据区 612 个单元格中非空（公式版）= 612，`data_only` 版唯一取值集合 = `{0}`。

**结论：3.xlsx 不提供任何可用于"还原 0–6"的观测值；它只是 0–6 量表与维度定义的说明书。**

### 1.3 `summary` 定义的感官维度（逐列）

`summary` 表头 52 列（A1:AZ1）：`Beer` + **50 个数值感官列** + `comments`。分组：

| 组 | 列数 | 列名（`summary` 表头原文） |
|---|---|---|
| Aroma（`A_*`） | 15 | `A_malt_all, A_malt_grain, A_malt_bread, A_malt_cara, A_malt_burn, A_hops_all, A_hops_citrus, A_hops_tropical, A_hops_noble, A_hops_woody, A_esters_all, A_esters_ethac, A_esters_isoaa, A_esters_flower, A_ester_fruity` |
| Flavour（`F_*`） | 15 | `F_malt_all, F_malt_grain, F_malt_bread, F_malt_cara, F_malt_burn, F_hops_all, F_hops_citrus, F_hops_tropical, F_hops_noble, F_hops_woody, F_esters_all, F_esters_ethac, F_esters_isoaa, F_esters_flower, F_ester_fruity` |
| 口感/缺陷/辅料/总体 | 20 | `body, bitternes, co2, aftertaste, alcohol, sweetness, acidity, dms, metallic, 4vg, t2n, diacetyl, stale_hops, orange, coriander, clove, lactic, acetic, barnyard, overall` |
| 文本 | 1 | `comments`（无数值，不进目标集） |

`summary` 每一列在第 2 行都指向评分卡的某个分值单元格（`xlsx_summary_formula_map.csv` 给出 50 列完整映射，例如 `B2=beer_1!$Q$7`、`AF2=beer_1!$Q$50(body)`、`AM2=beer_1!$Q$68(dms)`）。

**取 evidence 时发现的两处 3.xlsx 内部不一致（论文数据处理可提，说明以 4.csv 为准）：**

1. **barnyard 引用错误**：`summary!AX2 = '=beer_1!$AG$76'`，而 `AG76` 在评分卡上是 `Stale hops (cheesy, roquefort)`（`R75` 行对应 `AG76` 公式）；`Barnyard/horsey` 的公式在 `AG90`。即 3.xlsx 的 `barnyard` 列错引成 `stale_hops`（`AR2` 也引 `AG76`）。而 `4.csv` 的 `barnyard`（mean=-0.0493、sd=0.4492）与 `stale_hops`（mean=-0.0488、sd=0.4415）是两列不同数据，故以 4.csv 为准。
2. **Acetaldehyde 只存在于评分卡、未进 summary**：评分卡 `B44/R44='Acetaldehyde (green apples, peel)'`、分值公式 `Q45/AG45` 存在，但 summary 无对应列（`Q45/AG45` 未被任何 summary 公式引用）。评分卡共印 51 个感官属性标签 + Comments，summary 取其中 50 个（去掉 Acetaldehyde），`4.csv` 也恰为 50 列——三者的"50"由此闭合。
3. 另有两个**无标签镜像公式** `AG62`、`AG94`（Flavour 侧无对应属性名/对应 `Comments:`），属模板冗余公式，不构成维度。

---

## 2. `4.csv` 尺度取证：是 0–6 吗？是 z-score 吗？是中心化吗？

文件：250 行 × 53 列 = `beer, beer_id, tasting_category_fine` + **50 个感官列**；每列 n=250、**无缺失**；`beer` 唯一且 =1..250。

### 2.1 全局数字

| 指标 | 数值 |
|---|---|
| 全局均值（50×250 个值） | **0.00543** |
| 全局标准差（ddof=1） | **0.57780** |
| 全局最小 / 最大 | **-2.15073**（`alcohol`）/ **+6.17238**（`clove`） |
| 50 列 sd：min / median / max / 均值 | **0.36966**（`A_hops_woody`）/ 0.55362 / **0.85846**（`acidity`）/ **0.56794** |
| 50 列 \|mean\|：min / max / 均值 | 0.00062 / **0.06283**（`F_esters_isoaa`）/ **0.02118** |
| 非整数列数 | **50/50** |
| 每列不同取值数 | 106（`coriander`）– 250（`A_esters_all`） |
| 小于 0 的单元格 / 大于 6 的单元格 | **7617 / 12500（60.94%）** / **1**（`clove` 最大 6.1724） |
| 偏度范围 | -0.534（`overall`）～ **+6.805**（`clove`） |

代表列（完整 50 列见 `scale_stats.csv`）：

| 列 | mean | sd | min | max | 不同取值 | 偏度 |
|---|---|---|---|---|---|---|
| `A_malt_all` | 0.0365 | 0.7169 | -1.5521 | 2.8765 | 249 | 0.990 |
| `A_hops_woody` | -0.0199 | **0.3697** | -0.5229 | 1.5111 | 189 | 1.597 |
| `bitternes` | -0.0226 | 0.7310 | -1.6965 | 2.3280 | 247 | 0.214 |
| `clove` | -0.0310 | 0.5594 | -0.2685 | **6.1724** | 119 | **6.805** |
| `orange` | 0.0177 | 0.6835 | -0.2976 | 4.7745 | 131 | 4.531 |
| `overall` | -0.0080 | 0.5479 | -1.7360 | 1.3457 | 250 | -0.535 |

### 2.2 三个假设的严格判定（`scale_hypothesis_tests.json`）

| 假设 | 判定 | 量化证据 |
|---|---|---|
| **H1：逐列 z-score（sd≈1）** | **否定** | 50 列中 **0 列** 满足 \|sd-1\|≤0.05；`sd ∈ [0.3697, 0.8585]`，均值 0.5679；sd 的 5%/95% 分位 = 0.419/0.742 |
| **H2：仅中心化（mean=0）** | **近似成立、非精确** | 50 列 **0 列** 精确 mean=0（\|mean\| 最小 6.2e-4）；但 **50/50 列** \|mean\|≤0.1，平均 0.0212 → 已中心化，参考样本与本 250 行不完全一致 |
| **H3：原始 0–6 分** | **否定** | 非整数列 50/50；60.94% 单元格 <0；`clove` 最大 6.1724>6；每列不同取值 106–250（0–6 至多 7 种） |

补充：逐列 sd 全部 <1 且差别很大，与"**列内中心化后乘同一个缩放系数**"最一致（若每列做了单位方差 z-score，则 sd 应恒为 1；若保留原始 0–6，则不应出现负值）。但"均值非机器精度 0"说明中心化用的参考集不严格等于本表 250 行（可能是标准化在更大样本/品评员层级完成后再平均）。**该机制只能作为假设标注，无法从现有文件证实**（见 §6 存疑点）。

> 注意：题面自己也写明"表格 4.csv 中的数值不是原始 0–6 分，而是经过标准化/中心化的连续值"（problem PDF 第 3 页）。本报告的贡献是把这个定性说法量化：**"标准化"不是逐列 z-score（sd≠1），而是中心化 + 共同缩放**。

---

## 3. 0–6 能否还原？缺什么？如何在显式假设下近似？

### 3.1 结论：不能精确还原（且不存在唯一近似）

- **3.xlsx 没有任何真实评分**（§1.2：12 张空白卡、summary 全 0），因此**数据集内不存在一列真实的 0–6 作为校准锚点**；250 个样品中最多只有 12 个 Beer# 有卡（且空白），不存在逐样品对照。
- 3.xlsx 评分卡是原始 0–6 的记录载体，而 `4.csv` 是其变换产物：设原始 0–6 值为 `x`，变换为 `z = (x - a_j)/s_g`（`a_j` 为列原点、`s_g` 为缩放；也可以是每列各自的 `s_j`，两者在本数据上不可区分）。**`a_j` 已被消去且无任何文件记录**，`s_g` 也未记录。因此：
  - **可恢复**：列内相对大小（序）、列内相对间距（在未知比例意义下）、列间相对离散度（`sd_j` 之比）；
  - **不可恢复**：每列的原点（=该感官维度的平均评审水平），以及绝对 0–6 水平；列间绝对水平也无法比较。
- 数学上：对任意 `b∈(0, b_max]`、`a_j∈[-b·z_min, 6-b·z_max]`，`x = a_j + b·z` 都给出同样保序、同样落在 [0,6] 的合法"反演"。`b_max = 6/max_j(range_j) = 6/6.4409 = **0.9315**`（由 `clove` 决定），`a_j` 是自由参数。**这是不可识别性（non-identifiability），不是精度问题。**

### 3.2 缺的信息（若真要做 0–6 必须向数据提供方索取）

1. `4.csv` 每列的原始 0–6 值（或每列的原始均值/标准差）；2. 标准化方式与参考样本（`scale()` 是在 250 行上、还是品评员层级/更大样本上做的）；3. 品评员人数与聚合规则（均值/共识、0–6 是否先归一化）；4. 3.xlsx 中 12 张卡对应哪 12 个 Beer#、以及真实填写的评分（当前为空白）。

### 3.3 显式假设下的近似映射（三种，量化差异）

**方案 A（推荐主方案）：保留标准化连续值，不做 0–6 映射。**
- 变换：无。信息零损失，模型可直接回归 50 个标准化目标。
- 论文表述："目标为标准化/中心化后的感官强度连续值（`4.csv`），不是原始 0–6 分"；报告 RMSE/MAE 时注明"标准化尺度"。
- 若必须给"分级"，可在**结果展示层**才加方案 B/C，并明确标注为映射分。

**方案 B：列内 min-max 映射到 [0,6]（端点假设：本样本最小值=0、最大值=6）。**
- 公式：`x^mm = 6·(z - z_min)/(z_max - z_min)`。
- 逐列结果（`mapping_analysis.csv`）：映射后 `mean ∈ [0.221, 3.364]`（不等于 3），`sd ∈ [0.521, 1.349]`；**RMSE 尺度系数 = 6/range ∈ [0.9315, 2.9498]**（`clove` 0.93 vs `A_hops_woody` 2.95，差 **3.17 倍**）→ 若在映射分上报误差，必须逐列报告，不能跨列汇总。
- 保序性：严格单调，与 z 的秩完全相同（Spearman=1）。

**方案 C：列内秩/分位数映射到 0..6（例如 `x^rk = 6·(rank-1)/(n-1)` 或"分位→0–6 均匀分布"）。**
- 映射后 `mean≈3`、`sd≈1.742`（所有列几乎相同），分布被强行改成近均匀，**丢失原始分布形状**（如缺陷类维度的严重右偏会被抹平）。
- 与方案 B 的差异：逐单元格 **平均 |Δ| = 1.52 分**、**最大 |Δ| = 4.94 分**；两方案 Spearman 相关 =1（都"保序"），但同一观测值可差到近 5 分。典型例子：
  - `clove`，beer 181（z=-0.3109）：方案 B → **0.059**（近似"未检出"）；方案 C → **3.012**（"中等"）。
  - `overall`，beer 104（z=0.1295）：方案 B → 3.503；方案 C → 3.012。
  - `bitternes`，beer 197（z=0.0548）：方案 B → 2.555；方案 C → 2.988。
- 说明：观测数据**无法**在 B、C 之间做选择——这正是"不能把映射分当原始分"的量化依据。

**方案 D（不推荐）：假定原始分列均值=3、原始 sd=1，即 `x = 3 + z`。**
- 后果：**205/12500（1.64%）单元格越界**（<0 或 >6），最大映射值 **14.09**（`clove`，原始 `clove` 极度右偏），说明"0–6 里均值 3、sd 1"这一常见直觉与数据结构矛盾，**不可用**。

### 3.4 论文可用的口径模板（建议写入"数据处理"与"评价指标"）

> `4.csv` 为经**中心化+缩放**后的连续感官强度（50 维，非原始 0–6 分；证据：逐列均值≈0 而 sd=0.37–0.86、60.94% 值为负、最大 6.17>6）。本文以该标准化连续值为建模目标，指标均在标准化尺度上报告。为满足题面"0–6 分制分级"的呈现要求，另给出**映射分级分**：`x_mapped = 6·(z-z_min)/(z_max-z_min)`，并声明：(i) 它是保序映射分，**不是原始 0–6 评分**；(ii) 端点假设为样本极值对应量程两端；(iii) 各维映射对误差的尺度系数为 0.93–2.95，故分级分不作为跨维度绝对比较依据，也不与 3.xlsx 评分卡或文献 0–6 值比较。

实现（可直接复用）：
```python
import pandas as pd
df = pd.read_csv("data/raw/4.csv")
meta = ["beer", "beer_id", "tasting_category_fine"]
cols = [c for c in df.columns if c not in meta]

# 方案 B：映射分级分（展示/提交用，声明为 mapped grade）
mm = pd.DataFrame({
    c: 6.0 * (df[c] - df[c].min()) / (df[c].max() - df[c].min()) for c in cols
}, index=df.index)
# 方案 A：主目标（标准化连续值）
y = df[cols].copy()
```

---

## 4. targetColumns 最终决策与三方对齐

### 4.1 最终清单（50 列，按 `4.csv` 列序）

`analysis/sensory/targetcolumns.csv`（50 行，含每列的四套名字与命名差异注释）。分组计数：

| group | 列数 | subgroup 细分 |
|---|---|---|
| Aroma | 15 | Malt/麦芽 5、Hops/酒花 5、Esters/酯类 5 |
| Flavour | 15 | Malt/麦芽 5、Hops/酒花 5、Esters/酯类 5 |
| 口感/缺陷/总体 | 20 | 缺陷/野生菌 9（`dms, diacetyl, metallic, stale_hops, t2n, X4vg, lactic, acetic, barnyard`）、口感/基本味 7（`body, aftertaste, alcohol, co2, sweetness, acidity, bitternes`）、辅料/辛香 3（`orange, coriander, clove`）、总体 1（`overall`） |

> 若采用"只交 Aroma+Flavour 两套"的窄口径：15+15 = **30 列**（`group ∈ {Aroma, Flavour}`）；其余 20 列作为附加维度。建议**主表 50 列**、附注 30/20 分层，二者都在 `targetcolumns.csv` 的 `group`/`subgroup` 字段可筛出。

### 4.2 四方对齐结果（脚本 `sensory_03_align_targets.py`）

- `4.csv` 50 列 ↔ `8.xlsx 'Sensory names'` 的 Trained panel 50 行：**R_name 集合完全相等（50/50）**——`8.xlsx` 是唯一权威的短名映射表。
- `4.csv` 50 列 ↔ `5.csv` 50 个长名：通过 `8.xlsx` 的 `CleanName_PanelFeedback` 匹配 **50/50**（含 `overall` 的换行/`_x000D_` 清洗）。
- `4.csv` 50 列 ↔ `3.xlsx summary` 50 列：**50/50 命中**，其中 3 处命名差异（见下表）。
- **注意**：`5.csv` 的行列名与 `4.csv` 的列顺序**并非完全同序**（末尾 5 个块不同：5.csv 为 `Alcohol, Carbonation, Aftertaste, Body, Overall`，4.csv 为 `alcohol, aftertaste, body, co2, overall`），对齐必须按**名字**而不是位置。

命名差异与证据：

| 维度 | 4.csv | 3.xlsx summary | 5.csv 长名 | 8.xlsx R_name | 说明 |
|---|---|---|---|---|---|
| 果香（A） | `A_esters_fruity` | `A_ester_fruity` | `Esters aroma - fruity` | `A_esters_fruity` | 3.xlsx 少一个 `s` |
| 果香（F） | `F_esters_fruity` | `F_ester_fruity` | `Esters taste - fruity` | `F_esters_fruity` | 同上 |
| 4-乙烯基愈创木酚 | `X4vg` | `4vg` | `4-vinyl guaiacol` | `X4vg` | 3.xlsx 无前缀 `X` |
| 苦味 | `bitternes` | `bitternes` | `Bitterness` | `bitternes` | 拼写少一个 `s`，三套文件一致保留；写论文时建议正文用 Bitterness、代码保留原列名 |
| 总体 | `overall` | `overall` | `Overall appreciation (Trained panel)` | `overall` | 5.csv 原名含换行 |
| 酒花"noble" | `A_hops_noble` | `A_hops_noble` | `Hops aroma - grassy` | `A_hops_noble` | 8.xlsx `CleanName_PaperLong` 为 "Hops - grassy" |
| 橘味 | `orange` | `orange` | `Orange` | `orange` | 8.xlsx `CleanName_PaperLong` 误作 "Hops taste - citrus"（`8.xlsx!F48`），但 `CleanName_Paper`/`PanelFeedback` 均为 Orange——以 `CleanName_PanelFeedback` 为准 |

### 4.3 为什么题面"约 40"不成立

题面原文（problem PDF 第 2 页）："给出 3.xlsx 中定义的 **Aroma 与 Flavour 两套、共约 40 个**感官维度的 0–6 分制的分级评分结果。"

实测：
- Aroma 侧 `A_*` = **15**，Flavour 侧 `F_*` = **15**，两套合计 **30** ≠ 约 40；
- `summary` 另有 **20** 个数值维度（口感/缺陷/辅料/总体），合计 **50**；
- 12 张评分卡上共印 **51** 个感官属性标签（多一个 Acetaldehyde）+ Comments，也不等于 40；
- 因此"约 40"不对应任何一个可由附件严格定义的子集（30/50/51 都不是 40；若强行取 40 需要从 20 个"其他"维度里任选 10 个，缺乏依据）。
- **处理建议**：论文主目标取 **50 列**（与 `4.csv`/`3.xlsx summary` 对齐），并在问题 1 处用一句话解释"题面'约40'为概括，附件实际定义 50 个数值感官维度（A+F 30 + 其他 20）+ comments"，同时说明未把文本 `comments` 纳入目标。

### 4.4 `4.csv` / `5.csv` 数据完整性检查

- `4.csv`：250 行，`beer` 唯一且 = {1..250}；**无缺失值**；50 个感官列名**无重复**；无两列数值完全相同（精确重复列 = 0 对）。
- **跨表 join 必须用 `beer`，不要用 `beer_id`**：`4.csv` 的 `beer_id` 是 float64 且只有 **96** 个不同值（被浮点/精度截断，如 1.csv 的 `5410228202929` 在 4.csv 变为 `5.410230e12`）；`1.csv` 的 `beer_id` 为 int64、250 个不同值。但 `beer` 列的顺序在 `1.csv` 与 `4.csv` 完全一致（逐行相同），`tasting_category_fine` 也一致。
- `5.csv`：50×50 方阵，行名=列名（50 个长名）。

---

## 5. 复现命令

```bash
cd /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest
PY=/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
$PY analysis/scripts/sensory_01_xlsx_forensics.py   # 3.xlsx 取证
$PY analysis/scripts/sensory_02_scale_stats.py      # 4.csv 尺度检验 + 映射量化
$PY analysis/scripts/sensory_03_align_targets.py    # targetColumns 对齐
```
输出均在 `analysis/sensory/`；脚本只读 `data/raw/`。

---

## 6. 存疑点 / 需 Lead 与其他组统一点

1. **4.csv 的标准化机制只是推断**：证据支持"列内中心化 + 共同缩放"（mean≈0、sd<1 且逐列不同），但"为什么 mean 不是精确 0""共同缩放因子是多少"无法从现有文件确定；本报告不把机制写死，只把它作为"不可精确还原"的佐证。**若论文需要一句话解释**，建议："4.csv 为经中心化/标准化处理的连续感官强度，标准化具体参数未随数据提供。"
2. **3.xlsx 的 12 vs 题面 10**（beer_1..beer_12，题面写 10 个 sheet），属另一条差异；本任务只涉及感官目标，sheet 数差异建议由 Lead 在总差异表中引用（`3.xlsx` 实测 13 sheets = 12 beer + summary）。
3. **3.xlsx summary 的 `barnyard` 引用 bug** 与 **Acetaldehyde 未入 summary** 是文件内部不一致；本任务以 `4.csv`（50 列、与 8.xlsx R_name 完全一致）为最终目标集，3.xlsx 只作维度定义/量表语义来源。
4. **"约 40" 的取舍**：本报告建议 50 列；若 Lead/用户决定按"两套 30 列"窄口径提交，需在论文中显式声明未覆盖的 20 个维度（口感/缺陷/辅料/总体），否则问题 1 的评分维度会与 4.csv 目标集不一致。
5. **0–6 分级输出**：若评阅要求问题 1 必须交付 0–6 整数分级，建议采用方案 B（min-max 映射）并另加"分级依据说明"；**不要**把 4.csv 值四舍五入/直接加 3 当 0–6（方案 D 会产生 1.64% 越界、最大值 14.09，见 §3.3）。
6. 本次未引用任何 `A/` 目录内容作为数据证据；题面原文引用自官方 problem PDF（SHA256 见 `CONTEXT.md`），数据事实全部由 `analysis/scripts/sensory_0*.py` 从 `data/raw/` 重新计算。
