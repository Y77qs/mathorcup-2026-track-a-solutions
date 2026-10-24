# 独立验证发现（Q1 数据/标定 + Q2/Q3 方法风险）

> 角色：reviewer（独立上下文 + 独立实现）。产物：`src/09_independent_rerun.py`、`outputs/review/*.json`。
> 状态标记：**已修复**（问题已消除，有可回读证据）/ **已接受**（Lead 裁决保留，作为限制披露）/ **仍开放**（阻塞或未处置）。
> 所有数字均为本 reviewer 对 `data/raw/` 原始文件的独立复算，不是转抄台账。

## 0. 复算基准（供判断建模者 R² 是否离谱）

`outputs/review/independent_baseline.json`：分折中位数插补 + train-only 共表达族聚合（Spearman 距离 + SpectralClustering）+ RidgeCV，
按 SPLIT-0001 留出 50 样本：

| 指标 | 独立基线 |
|---|---|
| holdout 逐维均值 R² | **0.0785** |
| R² 中位 | 0.0591 |
| MAE 均值 | 0.3846 |
| 逐维 Spearman 均值 | 0.2494 |
| 常数基线（训练均值）R² | −0.0246 |

**判据**：任何模型报告 R² 显著高于 ~0.08 时，必须先排除泄漏（6/7/SHAP、目标代理、插补/标定跨折拟合）再解释为"建模更强"。
该基线不追求超越建模者；它只提供独立量级。

## 1. CRITICAL（历史）统一 10^v 的 OAV —— 已修复，已复核

- 旧版 `C.oav_table()` 对所有阈值列做 `10^v`；43 个有阈值列中 **13 个是线性浓度**（v 即浓度），
  含 diacetyl(X2.3.butanedione) 与 furfural。10^v/真浓度：中位 **11.3×**、p95 **9.3e4×**。
- **已修复**：现行 `oav_table()`/`oav_long()` 直接用 8.xlsx `Calibrated chemical dataset` 的作者标定浓度。
- 我的独立复算（只用 8.xlsx，不 import common）：43 个化合物可算 OAV；DMS 中位 1.405 / max 30.17（µg/L）、
  diacetyl 中位 0.851 / max 406.79（mg/L）、4VG 0~3.319（mg/L）、linalool 中位 13.55、ethyl_acetate 中位 1.152
  —— 与 Lead 给的物理量级一致。
- **仍开放（残余）**：Calibrated 表**没有单位列**，OAV 成立依赖"cal 数值单位 = threshold 的 unit"，该前提不可由数据内部验证，
  必须写进数据限制。另有 **755 格 LOD/2 删失替代码**（见 §5），低浓度端 OAV 不是实测物理量。

## 2. CRITICAL 五类缺陷的可计算性 —— 已接受，按"三类绝对 + 两类单调代理"披露

独立复算（8.xlsx `Sensory thresholds` 按 `field_name_R` join）：

| 题面缺陷 | 1.csv 列 | 有阈值 | 尺度 | 结论 |
|---|---|---|---|---|
| DMS | DMS | 17.25 µg/L | log10 | 可算绝对 OAV |
| Diacetyl | X2.3.butanedione | 0.29925 mg/L | **linear** | 可算绝对 OAV（须用 cal 浓度，不能 10^v） |
| 4VG | X4VG | 0.2063 mg/L | log10 | 可算绝对 OAV |
| trans-2-nonenal | X.E..2.nonenal | **NaN**（chemical_name 为 E-2-nonenal） | linear | **不可算绝对 OAV** |
| Stale hops | X.E..2.nonenal / X3.methyl.2.butenal / X5.methylfurfural / furfural | 仅 furfural 60 mg/L | 混合 | 仅 furfural 可算；其余无阈值 |

裁决已接受：DMS/Diacetyl/4VG 用绝对 OAV；t2n 与 stale hops 用"浓度不增"单调代理并标 `is_absolute_threshold=false`；
论文数据限制明写"五类中仅三类可算绝对阈值"。**不得**写成"五类全部通过"。
**仍开放**：Q3 实现是否真的按此标注，需在实验产物出来后逐样本核（reviewer 的 Q3 检查项之一）。

## 3. MAJOR 4.csv 标定前提与 P1 物理锚定 —— 已接受，我独立复核 4 项

事实（独立复算）：4.csv 列均值 ≈0（max|col mean|=0.0628），列 sd **0.3697–0.8585**（中位 0.5536），
逐列不同取值 **106–250**；不是单位方差标准化。因此"z=0↔等级3""1 z 单位=1 等级"**不可由 4.csv 单独辨识**。
Lead 已改为 P1 物理锚定（OAV=1↔等级1，每数量级 +1 级），P2/P3/P4 为敏感性口径。我独立核的四项：

**(a) fit_scope：通过（精确）**。对 25 个有驱动集合的维度，用 train-200 重估 Theil-Sen 的 (a,s) 与 stored 的差：
中位 |Δs| = **1.1e-16**（机器精度）；用全部 250 重估的中位 |Δs| = 0.075。→ 参数确实只用训练 200 估计。

**(b) 13 个锚定维的 ρ 与斜率符号：通过（精确可复算）**。13/13 的 ρ 与我独立复算一致（差 ~1e-16，远小于 ±0.05）；
13/13 斜率符号一致；换 **Huber** 稳健回归后 13/13 符号仍一致（量级同阶，例：A_hops_all TS 0.447 / Huber 0.365；
A_hops_citrus TS 0.246 / Huber 0.295）。锚定维：A_hops_all/A_hops_citrus/A_esters_ethac/F_hops_all/F_esters_all/
F_esters_ethac/acidity/bitternes/sweetness/X4vg/lactic/acetic/alcohol。

**(c) 四套口径的单调性：成立，但它是重言式**。"分级序 = 连续值序"对 P1–P4 恒成立（违反列数 0/0/0/0），
因为四套规则都是 v 的单调非降函数。它是必要条件，不是效度证据；**不能当通过依据**。

**(d) 口径间 QWK：只反映标定敏感性，不是效度**。我独立复算（stored 参数、全 250 分级）：
P1 vs P2 = **0.691**（canonical 0.691）、P1 vs P3 = **0.599**（canonical 0.603）、P1 vs P4 = **0.355**（canonical 0.355）。
QWK 高只说明两套口径排序相近；4.csv 真实 0–6 等级未知，任何 QWK 都不是"分级正确率"，更不是外部效度。
**报告必须写明这一点，且不得用 QWK 给 Q1 的分级准确性背书。**

## 4. MAJOR 缺陷维弱锚定：dms / diacetyl 无法由目标化合物解释 —— 已接受，登记为真结论

| 维度 | SPLIT-0001 ρ（主） | stratified ρ（复核） | Lead 引用值 |
|---|---|---|---|
| dms | **0.0889** | 0.0720 | 0.072（来自 stratified） |
| diacetyl | **−0.1113** | −0.0432 | −0.043（来自 stratified） |
| metallic | 0.2435 | 0.2457 | 0.246 |
| F_hops_citrus | 0.2443 | 0.1961 | 0.196（stratified） |
| orange | 0.2045 | 0.1285 | 0.129（stratified） |

结论稳健（两种划分下 dms ρ≈0.07–0.09、diacetyl ρ≤0 或近 0）：**这两个缺陷维几乎不能由目标化合物解释**。
后果：Q1 在这两维上即使 R² 高，也只是拟合了风格/批次/共线信息，**不是"测出了缺陷"**；论文不得把该 R² 解读为缺陷识别能力。
（Lead 引用的数值来自 stratified 文件；主口径应用 SPLIT-0001 的 0.089 / −0.111，引用时需注明来源，属 minor 溯源问题。）

## 5. MINOR/MAJOR 数据事实与泄漏边界（已核，供论文与检查使用）

1. **LOD/2 删失代码 755 格**（已核）：37 个 log10 列中 calibrated==0 的 755 格，1.csv 值精确等于 `log10(最小正浓度/2)`；
   线性列没有 0→0 的替代码。含义：低浓度端不是实测值，OAV 低端与"缺陷不恶化"的绝对量解释必须标注删失。
2. **4.csv 连续值区间**：Lead 早期"172–249"有误，实测 **106–250**（coriander/acetic 106、lactic 110、clove 119、orange 131；
   A_esters_all/aftertaste/F_esters_all/overall 为 250）。仍判为连续，但区间陈述须按 106–250。
3. **尺度**：70 列可回算 = 37 log10（10^v 相对误差中位 ~5e-10）+ 33 线性（v 与 calibrated 精确相等）；
   其余 **161 列无校准参照**。论文只写"70 列已核验"，不得写"其余线性"。
4. **2.csv 映射**：行/列是化学全名，与 1.csv 列名按名字仅 1/231 对得上；实测第 i 行/列 ≡ 1.csv 第 i 个特征列
   （212 个可命名对照全部单调、offset=0）。已固化为 `C.corr2_mapping()`（209 命名 + 22 位置）。凡按名字 join 2.csv 的代码都是错的。
5. **泄漏边界**：4.csv=目标；5.csv=感官维间 Spearman（由目标算）；6.csv=化学×感官交叉相关（含目标）；7.csv=Ratebeer 侧目标代理；
   8.xlsx 的 GBM importance/SHAP 是用 4.csv 训练的产物。这五类不得进入 Q1/Q3 特征；Q2 的 6.csv 只能作"选择后"独立先验。
6. **划分**：SPLIT-0001 未分层，**test 缺 West Flanders ale（7 样本全在训练侧）**；stratified 版 22/22 类进 test。
   两者均 disjoint=0、union=250。**SPLIT-0001 的 holdout 数字不能外推到 West Flanders ale**；两套都要报。

## 6. Q2 方法风险（重要性 ≠ 因果）

- 231 化合物高度共线（2.csv 高相关）；单变量相关或 Ridge 系数排序都会把"同一化学族的替代变量"排进 Top-3。
  Top-3 只能是**关联/预测贡献排序**，论文不得写"关键因素决定风味"或任何因果措辞。
- 必须做 **BH-FDR**（50×231 检验），并报告 q<0.05 的集合；未校正的 p<0.05 不能作为证据。
- 稳定性阈值预先固定：bootstrap≥200、单席位入选频率 ≥0.80、跨方法 Jaccard 均值 ≥0.50。**低于阈值就如实写"不稳定"**，
  不得只报入选频率高的维度。
- 6.csv 只能做选择后核对（|r| 秩相关 >0），不得回流选择；7.csv 与 SHAP 只能外部对照。
- 化学合理性用 8.xlsx 阈值/OAV 与 origin 类群，但**OAV 只对 43 个有阈值化合物可算**；对无阈值化合物只能写"文献/类群先验"，
  不得编造阈值。

## 7. Q3 方法风险（小样本生成的下游不可辨识）

- Kriek=10、Lambic=11：风格条件生成只能描述"这 10/11 个样本的经验分布"，不能声称刻画该风格总体；
  必须报 n 与 bootstrap 区间；Tripel 等小类同理。
- 五类缺陷中仅 3 类可算绝对 OAV（§2）；"缺陷不恶化"对 t2n/stale hops 只能做浓度单调代理；
  且 755 格 LOD/2 会让低浓度端的"不增"判断失真（删失后数值是替代码，不是测量）。
- Pils/Lager→Tripel 的迁移是**观察性风格差异**，不是"保证的干预收益"；生成谱必须在训练观测支撑内
  （逐化合物 min/max、非负、总和约束），越界即不可信。
- 感官画像依赖 Q1 预测器（冻结参数），Q1 的 dms/diacetyl 弱锚定会直接传播到 Q3 的缺陷维画像——必须披露。
