# 基于稳健表示、共表达网络与风格条件生成的啤酒化合物—感官强度建模

> 关键词：图正则低秩回归；Rank-Gauss；风格内残差化；风格分层 bootstrap；分层收缩 Copula；约束迁移

## 摘要

本文针对附件给出的 250 款啤酒、231 个化学及理化变量与 50 个标准化感官标签，建立了“稳健化学表示—网络辅助预测—稳定因素识别—风格条件生成—约束风格迁移”的统一框架。三问共享同一套数据字典、共表达网络与感官预测器，但分别评价预测能力、关联稳定性与生成／迁移质量；任何复杂组件都必须通过消融证明价值，没有稳定增益时保留更可靠的简单模型。

**问题一**把“预测标准化感官标签”与“给出 0–6 相对分级”分开：先在训练折内完成中位数填补与缺失指示、z-score 或 Rank-Gauss 表示、图正则低秩多输出回归（$r\le 10$ 与 $\lambda,\gamma$ 由训练内 5 折 CV 选择），再把逐目标训练中位数、图正则低秩模型与 HGB 用训练内 OOF 单纯形权重融合（median {{metric:EXP-0004:w_median}}、graph {{metric:EXP-0004:w_graph}}、HGB {{metric:EXP-0004:w_hgb}}）。在唯一的 50 行留出集上，50 维等权平均 MAE 由基线的 {{metric:EXP-0001:mae}} 降到 {{metric:EXP-0004:mae}}，$R^2_{50}$ 为 {{metric:EXP-0004:r2_50dim}}，相对中位数基线的 Skill 为 {{metric:EXP-0004:skill_50dim}}；同 seed 独立复跑在 $10^{-9}$ 容差内逐项复现。三项训练内消融的增益都小于折间波动（见第 4.6 节），我们如实作为弱增益／负结果披露，稳定增益来自融合。

**问题二**用附件 2.csv 的 Spearman 关联矩阵构建附件描述网络、用 200 行训练集重算的图作正则化网络，对 {{metric:EXP-0029:n_candidates}} 个单体化合物候选计算总体 Spearman、风格残差化 Spearman 与图正则低秩系数，按列内百分位合成综合分 $S_{jt}$。主指标为 4 种方法 Top-3 集合的平均两两 Jaccard：候选 {{metric:EXP-0029:topk-jaccard}}、维度无关基线 {{metric:EXP-0002:topk-jaccard}}。最终 Top-3 按蓝图规定的“bootstrap 入选频率 $\pi$ 优先、平均综合分 $S$ 裁决并列”给出；$\pi$ 均值仅 {{metric:EXP-0029:mean_selected_pi}}、没有化合物达到 $\pi=1$，说明单维 Top-3 存在实质竞争。

**问题三**用风格内经验边际与池化边际的层次收缩（$\kappa=5$）与混合 floor 边际描述 $p(X\mid s)$，用向共享相关矩阵收缩的高斯 Copula（$\kappa_R=20$）描述依赖结构，采样后投影到五条硬缺陷约束。低缺陷生成的约束满足率为 {{metric:EXP-0033:constraint-satisfaction}}（无条件基线与未约束生成分别为 {{metric:EXP-0008:constraint-satisfaction}} 与 {{metric:EXP-0033:constraint-satisfaction-unconstrained}}）；归一化能量距离 {{metric:EXP-0033:energy-distance-normalized}}（同量真实—真实参照 {{metric:EXP-0033:energy-distance-real-reference}}）；缺陷超阈率由 {{metric:EXP-0033:defect-exceedance-rate-unconstrained}}（真实数据 {{metric:EXP-0033:defect-exceedance-rate-real}}）降到 {{metric:EXP-0033:defect-exceedance-rate}}。Pils/Lager→Tripel 迁移把目标马氏距离由 {{metric:EXP-0033:ablation-quantile-transfer-mahalanobis}} 降到 {{metric:EXP-0033:target-mahalanobis}}，但“策略相对不恶化率 {{metric:EXP-0033:transfer-nonworsen-rate}}”是投影构造保证的；在 cap-at-max 策略下，输出对“逐缺陷严格不增”这一更严标准的达标率只有 {{metric:EXP-0033:transfer-scenario-strict-nonworsen-min}}，两种口径必须分开读，不能把该策略相对率读成经验性的可行性结论。

台账现有 {{value:count:experiments}} 个实验、{{value:count:validations}} 条验证、{{value:count:claims}} 条结论（含被替代的历史记录）与 {{value:count:figures}} 张图；三项预注册稳健性判定全部通过（见第 7 节），九项必做消融逐项完成（见第 8 节）。全部数字由台账占位符渲染，失败实验与未通过的检查按原样保留并披露（第 7 节）。

## 1 问题重述与分析

### 1.1 题目要求

题目要求在附件 1–8 上完成三项任务：(i) 由 1.csv 化学谱给出 3.xlsx 定义的 Aroma 与 Flavour 两套感官维度的 0–6 分级；(ii) 用 2.csv 构建化合物共表达图并给出每个感官维度的 Top-3 关键化合物，量化稳定性与化学合理性；(iii) 以 `tasting_category_fine` 为条件学习风格生成模型，在给定风格下生成化合物谱并给出感官画像，同时完成 Pils/Lager→Tripel 迁移并保持 DMS、双乙酰、4VG、trans-2-nonenal、stale hops 等缺陷不恶化。

### 1.2 三问的评价对象

| 小问 | 目标 | 必须给出的结果 | 评价方式 |
|---|---|---|---|
| 问题一 | 估计 $Y=f(X)+E$ | 50 维连续预测、逐维 MAE／$R^2$／Skill、全部 {{metric:EXP-0026:n_rows}} 行的 0–6 分级 | 50 维等权平均留出 MAE（minimize） |
| 问题二 | 识别稳定同期关联 | 每个感官维度的 Top-3 单体化合物、$\pi$、方法间 Jaccard、化学合理性分层证据 | 4 方法 Top-3 平均两两 Jaccard（topk-jaccard） |
| 问题三 | 估计 $p(X\mid s)$ 与迁移算子 | 生成谱、约束满足、能量距离、感官画像、双阈值与 Pareto | 同时满足全部声明约束的样本比例（constraint-satisfaction） |

### 1.3 以数据为准的三处修正

审计后我们对题面作了三处以数据为准的修正，并写进数据字典：样本数为 {{metric:EXP-0026:n_rows}}（题面 226 为笔误）；2.csv 实为 Spearman 相关（题面称 Pearson，但四个检验对与 Spearman 一致到 4 位小数）；感官维度为 {{metric:EXP-0026:n_targets}} 个（题面“约 40”是 Aroma+Flavour 的近似，实际为 Aroma 15 + Flavour 15 + 口感／缺陷／总体 20）。

## 2 数据审计与统一数据字典

### 2.1 对齐与主键

1.csv、4.csv、7.csv 以 `beer` 列（$1..250$ 的排列）逐行对齐；`beer_id` 在 4.csv/7.csv 中被截断（仅 96 个唯一值），**不作为连接键**。审计得到 1.csv 为 {{metric:EXP-0026:n_rows}} 行、{{metric:EXP-0026:n_features}} 个化学及理化变量、{{metric:EXP-0026:n_targets}} 个随行感官标签；缺失 {{metric:EXP-0004:audit_missing_cells}} 个单元格，集中在 9 列 63 行（`amyl.acetate` 27、`aroma_hops_sum` 13、`methylpyrazine` 12、`X2.3.butanedione` 9、`X3.methylbutanal` 7 等，逐列计数见 `outputs/audit/audit.json`）。

### 2.2 尺度—编码—单位—证据字典

以 8.xlsx 的 Calibrated chemical dataset（70 个化合物的原始浓度）对 1.csv 回算，逐列判定存储尺度：**37 列**与 $\log_{10}$(原始浓度) 数值一致，**33 列**与原始浓度线性一致，其余 **161 列**无校准表直接覆盖（逐列判定表见 `outputs/audit/scale_identification.csv`，由 `src/prepare_base.py` 生成并随包交付）。37 个 log10 列中有 {{metric:EXP-0004:audit_calibrated_zero_cells}} 个单元格对应校准表记录的 0，其存储值等于该列最小正浓度一半的 $\log_{10}$（编码点）；161 个未校准列中有 {{metric:EXP-0004:audit_floor_columns}} 列共享地板值（约 $-1.8178$），合计 {{metric:EXP-0004:audit_floor_cells}} 个单元格。字典逐变量记录名称、类型、存储尺度、反变换、单位、编码规则与证据等级；变量类型区分单体化合物（{{metric:EXP-0029:n_candidates}}）、派生汇总量（5：`kcalperc`、`acids_sum`、`esters_sum`、`aroma_hops_sum`、`sulfur_sum`）与理化指标（7）。

**必须区分三件事**：记录为零、真实浓度严格为零、已知低于检出限。主模型首先复现**观测分布**；在缺少可信检出限时，我们不把最小正观测值当作仪器检出限，因此不做左删失建模，而是在 Copula 生成中用 floor 混合边际显式表示编码点。

### 2.3 缺失与算法表示

Q1 的主预处理为：当前训练折中位数填补 + 这 9 列的缺失指示变量；线性模型比较原存储尺度 z-score 与 Rank-Gauss
$$
u_{ij}=\widehat F_{j,\mathrm{train}}(x_{ij}),\qquad z_{ij}=\Phi^{-1}\big[\operatorname{clip}(u_{ij},\varepsilon,1-\varepsilon)\big],\quad \varepsilon=\frac{1}{2n_{\mathrm{train}}},
$$
重复值用中秩。Q3 估计边际分布时只使用有效观测，避免把中位数填补的堆积当成真实质量点。

## 3 统一符号与总体框架

| 符号 | 含义 |
|---|---|
| $X\in\mathbb R^{n\times p}$ | 1.csv 存储尺度的化学／理化观测（$n=250,p=231$） |
| $C$ | 在尺度可确认时得到的物理浓度（37 列 $10^x$、33 列原值、其余按推断） |
| $Y\in\mathbb R^{n\times q}$ | 4.csv 的标准化感官标签（$q=50$） |
| $s_i$ | 细粒度风格标签（22 类） |
| $Z$ | 训练折拟合的稳健化学表示 |
| $G=(V,E,W)$ | 变量关联网络 |
| $f(X)$ | 化学谱到感官标签的预测器 |
| $F_{j,s}$ | 风格 $s$ 下变量 $j$ 的条件边际 |
| $\mathcal T_{a\to b}$ | 风格 $a\to b$ 的迁移算子 |

总体框架先建立可审计的数据字典与证据分级，再在 Q1 估计 $f$，在 Q2 用关联统计与 $f$ 的系数筛选稳定因素，在 Q3 用 $F_{j,s}$ 与 Copula 生成 $X^*$，并用 Q1 的 $f$ 作为感官画像与迁移筛查的前向代理。

## 4 问题一：图正则低秩多输出预测与有界相对分级

### 4.1 训练折内预处理

{{metric:EXP-0026:n_features}} 个 `chem__*` 特征与 9 个缺失指示列组成 $Z\in\mathbb R^{n\times 240}$。所有中位数、标准化／Rank-Gauss 参照分布、目标中心化尺度、Spearman 图与超参数都在**训练折内部**拟合；主模型对 $\widetilde y_{it}=(y_{it}-\mu_{t,\mathrm{train}})/s_{t,\mathrm{train}}$ 建模，$s_{t,\mathrm{train}}<10^{-8}$ 时置 1。

### 4.2 图正则低秩多输出回归

设 $\widetilde Y=ZB+\mathbf 1b^\top+E$，求解
$$
\min_{B,b}\ \frac1{n_{\mathrm{train}}}\big\|\widetilde Y-ZB-\mathbf 1b^\top\big\|_F^2+\lambda\|B\|_F^2+\gamma\operatorname{tr}(B^\top L_G B)\quad\text{s.t.}\ \operatorname{rank}(B)\le r .
$$
图由训练折 Spearman 相关重算：$w_{jk}=\hat\rho_{jk}\mathbf 1\{|\hat\rho_{jk}|\ge\tau\}$（$\tau=0.5$），$w_{jj}=0$，$L_G=D_{|W|}-W$；对 $L_G$ 作特征值截断到非负的 PSD 投影（带符号边权可能使 $L_G$ 不定，这是显式声明的数值稳定化），缺失指示列的图惩罚块置零。等价惩罚为 $\operatorname{tr}(B^\top L_GB)=\tfrac12\sum_{j,k}|w_{jk}|\|B_{j\cdot}-\operatorname{sign}(w_{jk})B_{k\cdot}\|_2^2$。优化用 $B=AC^\top$ 的交替最小二乘（25 轮），初值取图-ridge 解的 SVD 前 $r$ 个分量，截距每轮用残差均值更新。

### 4.3 候选与对照

- **B0 基线**：逐目标训练中位数（无化学信息，`features: []`）。
- **C1 图正则低秩回归**：训练内 5 折 CV 在 $r\in\{3,6,10\}\times\lambda\in\{0.1,1,10\}\times\gamma\in\{0,0.1,1\}$（27 格）上选择，并在 Rank-Gauss 表示上复评；选中 $r$={{metric:EXP-0003:best_r}}、$\lambda$={{metric:EXP-0003:best_lambda}}、$\gamma$={{metric:EXP-0003:best_gamma}}。
- **C2 OOF 融合**：$\widehat Y=w_0\widehat Y_{\mathrm{median}}+w_1\widehat Y_{\mathrm{graph}}+w_2\widehat Y_{\mathrm{HGB}}$，$w_k\ge0,\sum w_k=1$，权重由训练内 OOF 最小二乘 + 单纯形投影得到；HGB 取 200 轮、学习率 0.06、15 叶、$L_2=0.1$，逐目标拟合。选择规则只看 OOF：融合 OOF MAE {{metric:EXP-0004:fused_oof_mae}} < 单纯图模型 {{metric:EXP-0004:graph_oof_mae}}，因此交付融合。

{{figure:FIG-0019}}

{{figure:FIG-0017}}

### 4.4 0–6 相对分级与 250×50 交付表

3.xlsx 是**空白评分卡模板**、4.csv 是标准化连续值，“原始 0–6 人工评分”不可识别。我们显式定义相对强度等级：以训练折中点经验 CDF
$$
a_{it}=\widehat F^{\mathrm{mid}}_{Y_t,\mathrm{train}}(\widehat y_{it}),\qquad g^{\mathrm{cont}}_{it}=6a_{it},\qquad g_{it}=\min\{6,\max[0,\lfloor 6a_{it}+1/2\rfloor]\},
$$
该主规则由模型契约 MCON-0001 的分段声明式公式与 7 个边界样例（覆盖 $a=0$、$1/12$、$1/6$、$1/2$、$3/4$、$11/12$、$1$）固定下来；敏感性分析另用训练折 5%/95% 分位到 0/6 的有界线性映射，仅用于检验分级对参考端点的敏感性。**等级 0 不自动表示该风味不存在，等级 6 不自动表示原人工评分满分，缺陷维度的相对高等级不等于已超过化学缺陷阈值**；标准化标签的 0 也不作为真实等级 3 的锚点。

交付层给出全部 {{metric:EXP-0026:n_rows}} 行 × {{metric:EXP-0026:n_targets}} 个维度的分级表（EXP-0026 的 `grades_all.csv`：每个维度一列 $g^{\mathrm{cont}}$、一列整数 $g$），其中 {{metric:EXP-0026:n_train_rows}} 行训练样本为 **in-sample**、{{metric:EXP-0026:n_holdout_rows}} 行留出样本为 out-of-sample。分级的二次加权 $\kappa$ 为 {{metric:EXP-0026:grade_qwk}}、分级 MAE 为 {{metric:EXP-0026:grade_mae}}、整级一致率为 {{metric:EXP-0026:grade_agreement}}；预测被收缩会使预测级分布更集中，而参考级近均匀，因此一致率有限，这一偏差如实报告而不修饰。

{{figure:FIG-0020}}

### 4.5 评价与结果

以留出 50 行的真实 $Y$ 计算逐维 $\mathrm{MAE}_t$、$R_t^2$、$\mathrm{Skill}_t=1-\mathrm{MAE}_{t,\mathrm{model}}/\mathrm{MAE}_{t,\mathrm{median}}$，再取 {{metric:EXP-0026:n_targets}} 维等权平均：

| 实验 | 50 维平均 MAE | $R^2_{50}$ | Skill |
|---|---:|---:|---:|
| B0 逐目标训练中位数 | {{metric:EXP-0001:mae}} | {{metric:EXP-0001:r2_50dim}} | 0（定义） |
| C1 图正则低秩回归 | {{metric:EXP-0003:mae}} | {{metric:EXP-0003:r2_50dim}} | {{metric:EXP-0003:skill_50dim}} |
| **C2 OOF 融合（选中）** | {{metric:EXP-0004:mae}} | {{metric:EXP-0004:r2_50dim}} | {{metric:EXP-0004:skill_50dim}} |

C1 的训练内 CV MAE 为 {{metric:EXP-0003:cv_mae}}（折间 sd {{metric:EXP-0003:cv_mae_sd}}），明显小于基线在测试行的 MAE，说明选择过程未系统性过拟合。逐目标看，{{metric:EXP-0026:n_improved_targets}} 个维度相对基线改善、{{metric:EXP-0026:n_degraded_targets}} 个维度恶化，恶化集中在训练样本极少的缺陷／风格维度；融合相对其自身分量的增益很小，多出来的那部分主要来自非线性残差而不是图结构。

{{figure:FIG-0016}}

{{figure:FIG-0018}}

### 4.6 训练内消融（第 1–3 项，负结果）

1. **原尺度标准化 vs Rank-Gauss**：CV MAE 分别为 {{metric:EXP-0035:ablation1-zscore-cv}} 与 {{metric:EXP-0035:ablation1-rankgauss-cv}}，差值 {{metric:EXP-0035:ablation1-rankgauss-minus-zscore-cv}}；
2. **普通 Ridge vs 低秩约束**：{{metric:EXP-0035:ablation2-ridge-cv}} 对 {{metric:EXP-0035:ablation2-lowrank-cv}}，差值 {{metric:EXP-0035:ablation2-ridge-minus-lowrank-cv}}；
3. **$\gamma=0$ vs 图正则**：{{metric:EXP-0035:ablation3-gamma0-cv}} 对 {{metric:EXP-0035:ablation3-gamma-best-cv}}，差值 {{metric:EXP-0035:ablation3-gamma0-minus-best-cv}}。

三项差值都小于折间 sd（{{metric:EXP-0035:ablation-q1-fold-sd}}），因此不能声称这些复杂组件带来稳定增益；真正稳定的增益来自 graph+HGB 融合（OOF {{metric:EXP-0036:q1-fused-oof}} 对 graph {{metric:EXP-0036:q1-graph-oof}}）。该负结果登记如下：

{{claim:CLAIM-0014}}

## 5 问题二：共表达网络、风格混杂与稳定 Top-3

### 5.1 两个用途不同的网络

- **附件描述网络**：把 2.csv 的 231×231 Spearman 矩阵作为登记依赖读入（EXP-0029），先做 PSD 投影再阈值化——原始矩阵最小特征值 {{metric:EXP-0029:attachment_network_min_eigenvalue_raw}}，投影后残差在 $10^{-16}$ 量级；$\tau=0.5$ 时 {{metric:EXP-0029:attachment_network_edges_tau05}} 条边、{{metric:EXP-0029:attachment_network_components_tau05}} 个连通块、最大块含 {{metric:EXP-0029:attachment_network_largest_component_tau05}} 个变量。它回应题目点名要用 2.csv 的要求，并给出附件水平的整体结构。
- **训练网络**：在 200 行训练集上重算 Spearman，用于 Q1 的图正则与任何需要评价泛化的分析。边权 $w_{jk}=\hat\rho_{jk}\mathbf 1\{|\hat\rho_{jk}|\ge\tau\}$，$\tau\in\{0.4,0.5,0.6\}$，并用 bootstrap 边出现频率作可靠性标注。

两者用途不同、都可在台账查证。**必须说明**：附件 2.csv 是同一批 250 款酒的关联矩阵，与 1.csv 不是独立数据源；若用全部 250 行重算图来正则化，测试信息会进入模型，因此模型侧的图只能来自训练 200 行。

### 5.2 网络模块

基于 $|W|$ 的阈值图用连通分量识别模块 $M_1,\dots,M_K$，模块得分 $m_{ik}=\mathrm{PC1}(Z_{i,M_k})$，先分析模块与感官维度的关系，再解释模块内候选。$\tau=0.5$ 时有 {{metric:EXP-0029:module_count_tau05}} 个连通块，但最大块几乎吞并了全部特征（传递连通），模块区分度弱；$\tau=0.6$ 时给出 {{metric:EXP-0029:module_count_tau06}} 块、{{metric:EXP-0029:network_edges_tau06}} 条边的更严划分，两者都报告。因此模块只作为解释线索，**不进入 Top-3 打分**。

{{figure:FIG-0023}}

### 5.3 总体关联与风格内关联

总体关联 $\rho^{\mathrm{total}}_{jt}=\operatorname{Spearman}(X_j,Y_t)$；风格内关联先对秩作风格虚拟变量与截距的残差化：
$$
r_j^X=\big[I-H(H^\top H)^\dagger H^\top\big]\operatorname{rank}(X_j),\quad r_t^Y=\big[I-H(H^\top H)^\dagger H^\top\big]\operatorname{rank}(Y_t),\quad \rho^{\mathrm{within}}_{jt}=\operatorname{Corr}(r_j^X,r_t^Y).
$$
据此区分四类：总体与风格内均稳定、主要体现风格差异、被风格差异遮蔽、不同风格方向不一致。第 4 项消融（总体 vs 风格内）见第 8 节。

### 5.4 固定的综合规则与“$\pi$ 优先”的最终 Top-3

对实际单体化合物候选（{{metric:EXP-0029:n_candidates}} 个），定义
$$
S_{jt}=\frac13\Big[R\big(|\rho^{\mathrm{total}}_{jt}|\big)+R\big(|\rho^{\mathrm{within}}_{jt}|\big)+R\big(|\widehat B_{jt}|\big)\Big],
$$
其中 $R$ 是列内“越大越高”的百分位，$\widehat B$ 来自与 Q1 同族的图正则低秩回归（$\tau=0.5,\lambda=1,\gamma=0.1,r=6$，不调参）。进行 $B=500$ 次风格分层 bootstrap（每个风格内有放回重采样到该风格样本数；每次重拟合秩变换、网络与模型），得到
$$
\pi_{jt}=\frac1B\sum_{b=1}^B\mathbf 1\{j\in\operatorname{Top3}^{(b)}_t\}.
$$

**交付的最终 Top-3 严格按蓝图 §4.4 的规则排序：先按 $\pi_{jt}$ 降序，$\pi$ 相同时用平均综合分 $S_{jt}$ 裁决并列**（`sets_pi_first.json` 与 `outputs.final_top3` 逐维给出 $\pi$、$S$ 分量、方向、模块与风格混杂标签）。主指标 `topk-jaccard` 仍按注册口径由三种单方法集合与“按 $S$ 取前 3”的综合集合的 `sets.json` 复算，这一口径下值为 {{metric:EXP-0029:topk-jaccard}}；若把综合集合换成 $\pi$ 优先集合，同一指标为 {{metric:EXP-0029:topk-jaccard-bootstrap-mean}}，两个数同时报告，不以后者替换已注册的主指标。点估计综合集与 $\pi$ 优先集在 {{metric:EXP-0035:ablation-q2-point-vs-pi-first-changed-dimensions}} 个维度上不同，Jaccard 为 {{metric:EXP-0035:ablation-q2-point-vs-pi-first-jaccard}}——这正是必须同时报告两者的原因。

### 5.5 结果与化学合理性

| 方法／基线 | topk-jaccard |
|---|---:|
| 维度无关的全局 Top-3 基线 | {{metric:EXP-0002:topk-jaccard}} |
| **四方法逐维 Top-3（选中）** | {{metric:EXP-0029:topk-jaccard}} |

500 次 bootstrap 下交付 Top-3 的 $\pi$ 均值为 {{metric:EXP-0029:mean_selected_pi}}，没有任何化合物达到 $\pi=1$，说明单维 Top-3 存在实质竞争；这是把 $\pi$ 作为稳定性主证据、并用 $S$ 裁决并列的原因。方法间 Jaccard 见本节末图：总体与风格内两种关联的 Jaccard 只有 {{metric:EXP-0035:ablation4-total-vs-within-jaccard}}，说明**风格混杂确实改变“哪些化合物最重要”的答案**；图正则系数与另两种排序的 Jaccard 最低（图中最矮的两条边）。

每个最终候选记录 $\{$方向、强度、$\pi$、模块、风格混杂、化学解释、证据等级$\}$。与 6.csv 的独立 $|r|$ 在 44/44 个化合物上对齐后，50 维秩相关均值为 {{metric:EXP-0029:external_6csv_mean_spearman}}；7.csv 的跨来源描述符与 8.xlsx 的 GBM importance/SHAP 只作非独立对照，不参与选择。主结论登记如下（只声明同期关联，不宣称因果或未来预测）：

{{claim:CLAIM-0019}}

{{figure:FIG-0021}}

{{figure:FIG-0022}}

## 6 问题三：风格条件生成与跨风格迁移

### 6.1 风格内留出协议

主任务学习**已有目标风格**：用目标风格已有训练样本学习 $p(X\mid s)$，在风格内部留出真实样本（固定 3 折，`data/clean/q3_style_protocol.json`），共 {{metric:EXP-0033:n-generation}} 行 out-of-fold 生成；Tripel、Kriek、Lambic 整类排除训练（{{metric:EXP-0033:n-style-holdout}} 行）仅作为**未见风格泛化扩展**，单独报告，绝不与主分数合并。4.csv 的 50 个标签只用于评估，不进入生成模型似然。

### 6.2 风格收缩边际与 floor 混合

$$
\widehat F_{j,s}=\omega_s\widehat F^{\mathrm{emp}}_{j,s}+(1-\omega_s)\widehat F^{\mathrm{pool}}_j,\qquad \omega_s=\frac{n_s}{n_s+\kappa},\quad \kappa\in\{0,5,15\}.
$$
有地板编码的变量使用观测混合分布
$$
F^{\mathrm{obs}}_{j,s}(v)=\pi^{\mathrm{floor}}_{j,s}\mathbf 1\{v\ge v_j^{\mathrm{floor}}\}+(1-\pi^{\mathrm{floor}}_{j,s})F^{\mathrm{nonfloor}}_{j,s}(v),
$$
采样时以 $\pi^{\mathrm{floor}}$ 概率取 floor 原子、否则从非 floor 子样本经验 CDF 采样。最终 $\kappa$ 由训练内风格半折 CV 的 9 个格点跨折均值 argmin 选出（并列取更强收缩），得 $\kappa=$ {{metric:EXP-0033:kappa}}。

### 6.3 Copula 依赖结构

$$
z_{ij}=\Phi^{-1}\big[\widehat F_{j,s_i}(x_{ij})\big],\qquad \widehat R_s=\eta_s\widehat R_s^{\mathrm{emp}}+(1-\eta_s)\widehat R_{\mathrm{shared}},\quad \eta_s=\frac{n_s}{n_s+\kappa_R}.
$$
相关矩阵特征值截断到 $\ge10^{-6}$、归一化后再向单位阵收缩 5%，采样 $z^*\sim N(0,\widehat R_s)\Rightarrow u_j^*=\Phi(z_j^*)\Rightarrow x_j^*=\widehat F_{j,s}^{-1}(u_j^*)$；对已确认尺度的变量再转成 $c_j^*$ 检查阈值。最终 $\kappa_R=$ {{metric:EXP-0033:kappa_R}}。

### 6.4 三层检查与低缺陷生成

**观测分布合理性**用固定训练集标准化表示上的归一化能量距离
$$
\mathcal E^2=2\mathbb E\|X-Y\|-\mathbb E\|X-X'\|-\mathbb E\|Y-Y'\|,\qquad \mathcal E_{\mathrm{norm}}=\sqrt{\max(\mathcal E^2,0)/D_{\mathrm{ref}}},
$$
$D_{\mathrm{ref}}$ 为同量真实训练样本的典型两两距离，并提供同量真实—真实参照。**物理有效性**检查非负、训练支撑与派生量一致性；**缺陷风险**检查 3 个有阈值缺陷（DMS 17.25 μg/L、双乙酰 0.29925 mg/L、4VG 0.206333 mg/L，取 8.xlsx 均值，阈值登记在 `data/clean/q3_thresholds.json`）与 t2n 的风格上界。普通条件生成与低缺陷生成（对有阈值缺陷施加 $e_j(c)=\max(c_j/T_j-1,0)=0$，t2n 用风格训练 q90 上界）分别评价。

结果为：低缺陷生成的约束满足率 {{metric:EXP-0033:constraint-satisfaction}}（{{metric:EXP-0036:q3-n-generation}} 行 OOF 生成 + {{metric:EXP-0036:q3-n-style-holdout}} 行未见风格 + {{metric:EXP-0036:q3-n-transfer}} 行迁移，全部满足 MCON-0003 的五条约束），未约束生成仅 {{metric:EXP-0033:constraint-satisfaction-unconstrained}}，无条件全局高斯基线 {{metric:EXP-0008:constraint-satisfaction}}；缺陷超阈率方面，未约束生成 {{metric:EXP-0033:defect-exceedance-rate-unconstrained}}、真实数据 {{metric:EXP-0033:defect-exceedance-rate-real}}、低缺陷生成 {{metric:EXP-0033:defect-exceedance-rate}}。约束投影的代价很小：$\mathcal E_{\mathrm{norm}}$ 由 {{metric:EXP-0033:energy-distance-normalized-unconstrained}} 变为 {{metric:EXP-0033:energy-distance-normalized}}（真实—真实参照 {{metric:EXP-0033:energy-distance-real-reference}}；无条件基线 {{metric:EXP-0008:energy-distance-normalized}}）。逐风格的能量距离见本节末图：未见风格扩展的 $\mathcal E_{\mathrm{norm}}$ 为 {{metric:EXP-0033:style-holdout-energy-distance-normalized}}，Tripel 较好而 Kriek/Lambic 区间很宽，小样本如实披露。

经 Q1 代理的 50 维合并感官画像 Spearman 为 {{metric:EXP-0033:profile-spearman}}、MAE 为 {{metric:EXP-0033:profile-mae}}；但逐风格图（第 6.4 节末）显示这一合并分数掩盖了逐风格异质（Amber 为负、Brut 与 Brett/cofermented 接近 0、Kriek 与 Strong ale 较高），因此**合并分数不能读成逐风格可靠**，t2n/stale hops 的代理 CV $R^2$ 仅 {{metric:EXP-0033:proxy-cv-r2-t2n}}/{{metric:EXP-0033:proxy-cv-r2-stale}}，相关结论只作弱证据。

{{figure:FIG-0030}}

{{figure:FIG-0024}}

{{figure:FIG-0028}}

### 6.5 跨风格迁移：分位数初始化 + 最小改动约束优化

分位数映射给出初始化
$$
x_j^{(0)}=\widehat F_{j,\mathrm{Tripel}}^{-1}\big[\widehat F_{j,\mathrm{Pils/Lager}}(x_j^{\mathrm{source}})\big].
$$
在单调规范化坐标 $v_j=h_j(x_j)\in[0,1]$ 与低维表示 $a=A(v-\mu_T)$（Tripel 训练集 PCA 前 10 主成分）下求解
$$
\min_v\ (v-v^{(0)})^\top Q(v-v^{(0)})+\lambda D_{\mathrm{target}}(v)+\eta\|D(v-v^{\mathrm{source}})\|_1
$$
满足物理边界、缺陷不恶化、派生量关系与可信变动范围，其中 $D_{\mathrm{target}}(v)=(Av-\mu_T)^\top\Sigma_T^{-1}(Av-\mu_T)$、$\Sigma_T=0.9\Sigma_T^{\mathrm{emp}}+0.1I$。优化变量为 $v\in[0,1]^{231}$，用 L-BFGS-B，缺陷硬约束用可行域投影（每步把 DMS/双乙酰/4VG 的存储值投影到约束上界，t2n 与 stale hops 用 Q1 感官代理平移）。

- **两种不恶化策略**：超阈不恶化 $c_j^{\mathrm{new}}\le\max(c_j^{\mathrm{source}},T_j)$ 与绝对不增 $c_j^{\mathrm{new}}\le c_j^{\mathrm{source}}$；
- **双阈值情景**：$T_j$ 分别取 8.xlsx 的 mean 与 median；
- **题目指定缺陷**：DMS、双乙酰、4VG 用阈值；t2n 无阈值，施加 $c_{\mathrm{t2n}}^{\mathrm{new}}\le c_{\mathrm{t2n}}^{\mathrm{source}}$；stale hops 是感官维度，用 Q1 代理筛查并报告不确定性。

结果：**必须分清两个口径**。策略相对非恶化率由可行域投影构造保证、不是经验发现；严格逐缺陷不增率在「绝对不增」策略下由 $c^{\mathrm{new}}\le c^{\mathrm{source}}$ 同一约束直接保证，在「超阈不恶化」（cap-at-max）策略下则明显更低，逐缺陷拆分见 EXP-0033 的 `outputs.transfer-scenarios`；对 t2n/stale 两个代理约束的标签代理重抽样只给出代理口径的分位，不是五类缺陷严格率的下界。Pareto 前沿（$\lambda\in\{0.1,1,10\}\times\eta\in\{0,0.01,0.1\}$）见本节末图：$\lambda$ 越大目标越近、改动越大，$\eta$ 只带来很小额外代价，9 个格点的非恶化率全部与可行域允许的最大值一致。**两种策略的差别是约束保证的强度**（严格不增 vs 不超过 $\max(c^{\mathrm{source}},T)$），而不是可行性或代价；具体数值与逐缺陷拆分见紧随其后的登记结论。迁移结论登记如下：

{{claim:CLAIM-0022}}

{{figure:FIG-0026}}

{{figure:FIG-0031}}

### 6.6 生成模型消融（第 5–9 项）

5. **独立边际 vs Copula**：独立边际的 $\mathcal E_{\mathrm{norm}}$ 反而低 {{metric:EXP-0033:ablation-independent-marginals-delta}}，但依赖结构谱 MAE 由 {{metric:EXP-0033:dependence-spectrum-mae}} 升至 {{metric:EXP-0033:ablation-independent-marginals-dependence-spectrum-mae}}——能量距离对 Copula 不敏感，Copula 的收益体现在依赖结构，不能只报 $\mathcal E_{\mathrm{norm}}$；
6. **无收缩（$\kappa=0,\kappa_R=0$）vs 收缩**：无收缩 $\mathcal E_{\mathrm{norm}}$ 高 {{metric:EXP-0033:ablation-no-shrinkage-delta}}，收缩有效；
7. **不考虑编码质量点 vs 混合边际**：去掉 floor 原子最伤，$\mathcal E_{\mathrm{norm}}$ 高 {{metric:EXP-0033:ablation-no-floor-delta}}；
8. **普通生成 vs 低缺陷生成**：约束后 $\mathcal E_{\mathrm{norm}}$ 只差 {{metric:EXP-0033:ablation-normal-generation-delta}}（代价小），缺陷超阈率由 {{metric:EXP-0033:defect-exceedance-rate-unconstrained}} 降到 {{metric:EXP-0033:defect-exceedance-rate}}；
9. **分位数迁移 vs 约束优化**：目标马氏距离由 {{metric:EXP-0033:ablation-quantile-transfer-mahalanobis}} 降到 {{metric:EXP-0033:target-mahalanobis}}。

## 7 验证设计与稳健性（含失败与限制披露）

**协议先于比较**：在登记任何候选之前，三问各登记且仅登记一个验证计划（Q1：split-integrity、leakage、holdout-metrics、baseline-compare、independent-rerun；Q2：leakage、holdout-metrics、independent-rerun；Q3：leakage、holdout-metrics、simulation-seeds、independent-rerun）。检查由插件原生重算：Q1 的 50 维 MAE 由注册预测文件与测试真值复算（VAL-0034）、Q2 的 topk-jaccard 由 `sets.json` 复算（VAL-0038）、Q3 的 constraint-satisfaction 由 `samples.csv` 与 MCON-0003 的五条数值约束复算（VAL-0041），三者的复算值与实验记录值之差都在机器精度量级；三问的独立复跑都用**新实验 id** 在固定 seed 下逐项比较全部数值指标（VAL-0036 / VAL-0039 / VAL-0043，全部在声明的容差内复现，逐项比较见各 VAL 的 `result.json`）。

**Holdout 预算**：SPLIT-0002 共 5 条实验记录 = **3 次模型曝光**（EXP-0001 基线、EXP-0003 C1、EXP-0004 C2）＋ **2 次 verified rerun**（EXP-0010、EXP-0025，按 `verifiedRerun` 不计曝光；其中只有 EXP-0010 有独立复跑验证记录，见 VAL-0005/VAL-0031/VAL-0036，EXP-0025 是台账中第二条未单独验证的 verified rerun）。每行曝光 3 次，达到 `maxHoldoutReuse: 3` 上限，之后不再在该划分上注册任何非复跑实验；Q1 的稳健性扰动（EXP-0016–0018）与 Q2 的（EXP-0019–0021）只用 `SPLIT-0001/train.csv` 作依赖、不挂 split，因此不消耗曝光。SPLIT-0001 不挂载任何正式评估实验，其训练行被 Q1/Q2 的稳健性与 Q2 的关联分析使用。

**失败与回退（按原样保留，不删除、不改写）**：

1. **EXP-0012 → failed**（`SEED_NOT_ACKNOWLEDGED`）：Q3 候选为绕开 simulation-seeds 把 `seed-receipt.json` 误读成逐 seed 运行文件的问题，把 receipt 改名为 `env-seed.json`，但该次注册仍声明 `requireSeedReceipt:true`，runner 找不到 receipt 即失败。修复：Q3 候选不再声明该参数（EXP-0013 起成功），稳健性实验保留 receipt 并声明 `true`。
2. **VAL-0011 → passed=false**（EXP-0009 的 simulation-seeds）：`run.json`/`seed-receipt.json` 被正则当成第 4 个 run 且无指标。修复后 VAL-0012 与 VAL-0015/VAL-0029/VAL-0042 通过。
3. **VAL-0020 → passed=false**（EXP-0028 的 leakage，`feature-set-unknown`）：EXP-0028 注册时只写了 `featuresRef` 而没有逐列 `features`，审计拒绝在“特征集未知”时判通过。修复：以同一代码哈希、同一 seed、同一数据重建登记（EXP-0033，`samples.csv` 与 EXP-0028 逐字节相同），并把 231 个 `chem__` 输入列入注册参数；VP-0003 随后全部通过（VAL-0040–0043）。EXP-0028 与 VAL-0020 的失败记录保留在台账中。
4. **EXP-0027 → queued 但从未运行**：注册时特征表有一个错误列名，已被 EXP-0029 取代；台账保留其 `queued` 状态而不伪造运行。
5. **Q3 稳健性判定阈值**：ROB-0003 预注册的相对极差上限是较宽的 0.25，实际极差与判定见本节末的稳健性结论；我们如实报告“判定通过但阈值较宽”，不写成“很稳定”。

**稳健性（先登记后执行）**：三问各预注册一个稳健性计划并使用 `multiple-seeds` + `param-perturbation`，判定规则是预注册的可执行规则（relative-range）：

- ROB-0001（Q1）：训练内 5 折 CV MAE 在 seed 与 $\lambda\times2$ 两个扰动下的相对极差；
- ROB-0002（Q2）：topk-jaccard 在 seed 与 $\tau$ 两个扰动下的相对极差；
- ROB-0003（Q3）：$\mathcal E_{\mathrm{norm}}$ 在 seed 与 $\kappa$ 两个扰动下的相对极差，同时报告 constraint-satisfaction 的稳定性。

三个判定的具体极差、预注册上限与判定结果都由结论记录原样渲染，不在正文重抄：

{{claim:CLAIM-0012}}

**必须说明**：Q2 的 topk-jaccard 对这两个扰动不敏感，不代表 Top-3 集合完全相同；Q3 的 25% 阈值较宽，实际极差已如实报告。

**模型级证据的边界**：Q1 的交付数字以 EXP-0004 为准（VAL-0032–0036），同模型的 EXP-0016–0018 是训练内扰动、不参与交付数字；Q2 的交付数字以 EXP-0029 为准（VAL-0037–0039），EXP-0030 是它的 verified rerun；Q3 的交付数字以 EXP-0033 为准（VAL-0040–0043），EXP-0034 是它的 verified rerun；EXP-0035 与 EXP-0036 是纯审计实验（九项消融汇总与论文数字的 headline 表），不拟合任何模型。

## 8 九项必做消融汇总

九项消融逐项完成（审计实验 EXP-0035 断言的完成数为 {{metric:EXP-0035:ablation-items-complete}} / {{metric:EXP-0035:ablation-n-required}}，任一缺失即拒绝出表）。为免表格挤成一列长数字，下面按条目列出：

1. **原尺度标准化 vs Rank-Gauss**（训练内 CV MAE）：{{metric:EXP-0035:ablation1-zscore-cv}} 对 {{metric:EXP-0035:ablation1-rankgauss-cv}}，差值 {{metric:EXP-0035:ablation1-rankgauss-minus-zscore-cv}}，小于折间标准差 {{metric:EXP-0035:ablation-q1-fold-sd}}，弱正。
2. **普通 Ridge vs 低秩回归**（训练内 CV MAE）：{{metric:EXP-0035:ablation2-ridge-cv}} 对 {{metric:EXP-0035:ablation2-lowrank-cv}}，差值 {{metric:EXP-0035:ablation2-ridge-minus-lowrank-cv}}，弱正但不称稳定。
3. **$\gamma=0$ vs 图正则**（训练内 CV MAE）：{{metric:EXP-0035:ablation3-gamma0-cv}} 对 {{metric:EXP-0035:ablation3-gamma-best-cv}}，差值 {{metric:EXP-0035:ablation3-gamma0-minus-best-cv}}，弱正，作为负结果披露。
4. **总体关联 vs 风格内关联**（Top-3 集合 Jaccard）：{{metric:EXP-0035:ablation4-total-vs-within-jaccard}}；{{metric:EXP-0035:ablation4-differing-dimensions}}/{{metric:EXP-0035:ablation4-n-dimensions}} 个维度上两种关联给出不同的 Top-3，说明风格混杂显著改变答案。
5. **独立边际 vs Copula**（$\mathcal E_{\mathrm{norm}}$ 与依赖结构谱）：独立边际的 $\mathcal E_{\mathrm{norm}}$ 反而低 {{metric:EXP-0035:ablation5-independent-marginals-delta}}；但依赖结构谱 MAE 由 {{metric:EXP-0035:ablation5-copula-dependence-spectrum-mae}} 升到 {{metric:EXP-0035:ablation5-dependence-spectrum-mae}}。这是负结果，必须两个指标一起读，Copula 的收益体现在依赖结构而不是能量距离。
6. **独立风格估计 vs 收缩**（$\mathcal E_{\mathrm{norm}}$）：无收缩时高 {{metric:EXP-0035:ablation6-no-shrinkage-delta}}，收缩有效。
7. **不考虑编码质量点 vs 混合边际**（$\mathcal E_{\mathrm{norm}}$）：去掉 floor 混合时高 {{metric:EXP-0035:ablation7-no-floor-delta}}，是生成质量最关键的组件。
8. **普通生成 vs 低缺陷生成**（约束满足率与 $\mathcal E_{\mathrm{norm}}$）：约束把缺陷超阈率由 {{metric:EXP-0035:ablation8-exceedance-normal}} 降到 {{metric:EXP-0035:ablation8-exceedance-lowdefect}}，$\mathcal E_{\mathrm{norm}}$ 的代价只有 {{metric:EXP-0035:ablation8-normal-generation-delta}}。
9. **分位数迁移 vs 约束优化**（目标马氏距离）：由 {{metric:EXP-0035:ablation9-quantile-mahalanobis}} 降到 {{metric:EXP-0035:ablation9-constrained-mahalanobis}}，减少 {{metric:EXP-0035:ablation9-mahalanobis-reduction}}。

复杂组件并非一律有增益：图正则与低秩约束只有弱正；Copula 的能量距离增益不显著但依赖结构谱明显更好（第 5 项本身是负结果，必须两个指标一起读）；收缩与 floor 混合是生成质量的关键。这些判断都可在台账输出中复核，汇总图为第 8 节末图。

{{figure:FIG-0029}}

## 9 结论、建议与局限

**结论**。(1) 在 50 维标准化感官标签上，训练内 OOF 融合相对逐目标中位数基线把留出 MAE 从 {{metric:EXP-0001:mae}} 降到 {{metric:EXP-0004:mae}}（Skill {{metric:EXP-0004:skill_50dim}}），而图正则与低秩约束本身只有弱增益；分级以训练折中点经验 CDF 定义并交付全部 {{metric:EXP-0026:n_rows}} 行。(2) 每个感官维度的 Top-3 在风格分层 bootstrap 下并不唯一（$\pi$ 均值 {{metric:EXP-0029:mean_selected_pi}}，无化合物 $\pi=1$），总体关联与风格内关联给出的答案显著不同（Jaccard {{metric:EXP-0035:ablation4-total-vs-within-jaccard}}），把风格混杂显式建模是必要的。(3) 风格条件 Copula 生成器在几乎不损失分布合理性的前提下把缺陷超阈率从与真实数据相当的 {{metric:EXP-0033:defect-exceedance-rate-unconstrained}} 降到 {{metric:EXP-0033:defect-exceedance-rate}}；跨风格迁移的「策略相对不恶化率」在四种情景下都等于可行域投影保证的上界，在「绝对不增」策略下「严格逐缺陷不增率」同样由约束构造保证，而在「超阈不恶化（cap-at-max）」策略下输出对严格不增的达标率只有 {{metric:EXP-0033:transfer-scenario-strict-nonworsen-min}}；两种策略的可行率与代价几乎相同，所以差别是**保证强度**而不是可行性，不能把该策略相对率读成经验性的可行性结论，也不能把该达标率读成“只有少数源样本可行”。

**建议**。对酿造实践，我们只提供**关联与生成合理性**层面的证据：不能把 Top-3 读成因果靶点；不能把 0–6 相对等级读成人工评分；生成的谱需要真实酿造与品评复核。若用于工艺优化，应先在小规模实验中检验“超阈不恶化”与“绝对不增”两种策略的实际代价。

**局限**（如实披露）。(i) 标签是 4.csv 标准化连续值，0–6 分级只是训练折参考分布下的相对量，且训练行的分级是 in-sample；(ii) 留出只有 50 行，单维估计的抽样波动不可忽略；(iii) 2.csv 与 6/7/8.xlsx 之间不是独立数据源，不能当作外部验证；(iv) Q3 的 t2n/stale hops 依赖 Q1 线性代理，代理 CV $R^2$ 仅约 {{metric:EXP-0033:proxy-cv-r2-t2n}}；(v) 小风格（Kriek、Lambic、Faro）区间很宽，不声称精确刻画；(vi) 缺陷阈值来自 8.xlsx 的汇总值，原文献的检出限与基质效应未逐条核对；(vii) Q3 稳健性判定阈值（25%）较宽，已预注册并如实报告实际极差；(viii) 合并画像 Spearman 掩盖逐风格异质。

## 附录 A 复现说明

- 环境：Python 3.12.14（numpy 2.3.5、pandas 2.2.3、scipy 1.18.1、scikit-learn 1.9.1、matplotlib 3.11.2、openpyxl 3.1.5）；所有实验由插件 runner 在 macOS Seatbelt 沙箱中执行，脚本只读 `MODELING_*` 指向的注册数据／划分与已登记依赖。
- 数据：`modeling_data import` 导入 9 个附件并核对 SHA256；`src/prepare_base.py` 生成审计、尺度字典与 `src/target_columns.py`；`src/prepare_q1mapped.py` 用 SPLIT-0001 训练行生成 0–6 参考分级；`src/prepare_q3.py` 生成 Q3 视图与风格折协议。
- 顺序：init → probe → plan → 数据 → 契约 → 三问基线 → 逐问验证计划 → 候选 → 验证（含独立复跑）→ 选定 → 稳健性（先登记后执行）→ 结论／覆盖 → 审计（九项消融与 headline）→ 质量检查 → freeze → render → tex/pdf → artifact → check → package。
- 复现命令、种子与三处工程说明见 `REPRODUCE.md`；台账 `state/ledger.json` 记录每个实验的代码／数据／划分哈希与全部验证证据。

## 附录 B 台账与证据索引

- 数据：DATA-0001（基准表）、DATA-0002（Q1 评估视图）、DATA-0003（Q3 视图）、DATA-0004（Q3 leakage 审计视图）；SPLIT-0001（训练行／映射／Q2）、SPLIT-0002（唯一 Q1 评估划分）。
- 契约：TGT-0001（v2，labelSource 明确主分级规则）、TGT-0002（v2，50 个目标列 + 219 单体分析宇宙 + 2.csv 输入）、TGT-0003；MCON-0001（v3，主分级分段 AST + 7 个边界样例）、MCON-0002、MCON-0003（v4，5 条数值约束 + 8 个边界样例）。
- 关键实验：EXP-0001（Q1 基线）、EXP-0003/0004（Q1 候选）、EXP-0002/0029（Q2）、EXP-0008/0033（Q3）、EXP-0016–0024（稳健性）、EXP-0026（250×50 分级）、EXP-0035（九项消融审计）、EXP-0036（headline 审计）。
- 结论（每条一行，原文来自台账）：
  - {{claim:CLAIM-0018}}
  - {{claim:CLAIM-0014}}
  - {{claim:CLAIM-0019}}
  - {{claim:CLAIM-0021}}
  - {{claim:CLAIM-0022}}
  - {{claim:CLAIM-0012}}
- 图：论文实际引用的 14 张为 FIG-0016–FIG-0024、FIG-0026、FIG-0028、FIG-0029、FIG-0030、FIG-0031（Q1 五张、Q2 三张、Q3 五张、九项消融汇总一张；FIG-0030/0031 是图面修订后重新登记的缺陷超阈率图与 Pareto 图）。逐图 sha256 入台账；被取代的 FIG-0025/0027 已用 figure-retire 标记为 superseded（分别指向 FIG-0030/FIG-0031），旧字节归档到 `figures/archive/FIG-0025-q3_defect_exceedance.png` 与 `figures/archive/FIG-0027-q3_pareto.png`（归档字节与登记 sha256 逐字节核验一致），旧记录、路径历史与旧→新关系保留在台账。
