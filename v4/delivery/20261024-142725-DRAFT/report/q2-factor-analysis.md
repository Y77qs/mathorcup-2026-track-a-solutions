# Q2 证据：化合物–风味同期关联、Top-3 选择与稳定性

> 本文件是 `modeling_project workbench` 为 Q2 登记的 `factor-analysis` 与 `recommendations` 证据义务的落点，
> 同时供论文第四节引用。数值一律写成台账占位符；结论只写"同期关联"，不写因果、不写未来预测。
> 数据事实以 `report/data-quality.md` 第 6/7/12 节为依据；契约以 `quality.targetContracts[TGT-0002]` 为准。

## 1. 任务与口径

- 任务：对每个感官维度给出 Top-3 关键化合物，并量化稳定性（bootstrap 入选频率 + 方法间 Jaccard）。
- 输入：`DATA-0002`（`q2_raw.csv`）的 231 个 `chem__*` 特征 + 50 个标准化感官列；**只用训练行**（`SPLIT-0002` 的 200 行）。
- 输出：`sets.json`（`{dimension, method, items:[3]}` 数组，行数 = 50 × 方法数）、`sets_nested.json`、
  `metrics.json`（含 `topk-jaccard`）、bootstrap 频率表、共表达结构图。
- 指标定义：`topk-jaccard` = 逐维度对方法两两求 Top-3 集合 `J(A,B)=|A∩B|/(|A∪B|)`（k=3 即 `交集/(6−交集)`），
  维度内取平均，再对 50 个维度取平均；由部署版 native set-stability 复算器从 `sets.json` 重算，容差 1e-9。
- 禁止：因果表述、未来预测；把 5/6/7.csv 当独立外部验证；把 2.csv 当独立先验；用 test 行做排序或选参。

## 2. 共表达图的构建（2.csv）

2.csv 是 1.csv 的 **Spearman** 相关矩阵（重算 `max|Δ| = 6.66e-16`，与 Pearson 相比 16.94% 的单元格符号相反），
且**非半正定**：全矩阵最小特征值约 −0.0424、最大约 33.45。构建流程：

1. 对称化后特征分解，负特征值截断为 0（eigenvalue clipping）；
2. 对角线重新归一化为 1；
3. 记录投影前后最小特征值（实验指标 `coexpression_min_eigen_raw` / `coexpression_min_eigen_projected`）；
4. 以"出现在任一 Top-3 集合中的化合物"为节点，画 PSD 投影后的相关块热图 + 特征值谱对比图。

**为什么不做阈值化边图**：在非 PSD、且由同一批 250 样本派生的矩阵上，阈值化会放大负特征值方向上的伪结构；
先投影再呈现，既保留结构信息，又不产生不可解释的负方差。2.csv 的角色是**结构参考**，不是独立证据。

## 3. 三种排序方法与选择规则

| 方法 | 定义 | 选择规则 |
|---|---|---|
| `spearman_absrho` | 每个（化合物，感官维度）对的 \|Spearman ρ\| | 每维取分数最高的 3 个 |
| `ridge_coef` | 多输出岭回归在标准化特征上的系数绝对值；`α` 由 train-only 5 折 CV 选 | 每维取 \|coef\| 最高的 3 个 |
| `random_forest_importance` | 随机森林不纯度重要度（120 棵树，固定 seed） | 每维取重要度最高的 3 个 |

并列时按特征列顺序决定（`np.lexsort((arange, -score))`），保证同 seed 复跑完全一致。

## 4. 稳定性量化（两类证据，缺一不可）

### 4.1 方法间 Jaccard（主指标）

对每个维度取三种方法两两组合，`J = |A∩B|/(2k−|A∩B|)`，维度内平均，再对 50 维平均。
基线是"全局统一 Top-3"（两个全局排序共用一组三个化合物给所有维度），其 Jaccard 只反映两个全局集合的一致度。
**基线与候选不可直接比较**：基线是 2 个方法→1 个方法对，候选是 3 个方法→3 个方法对的均值；方法对数不同，
两者不是同一统计量，因此**不得写"候选优于基线"**，只能作一致性水平的描述。题面要求的每维 Top-3 由候选交付。

| 实验 | 方法集合 | `topk-jaccard` |
|---|---|---|
| 基线 `EXP-0004` | 两个全局排序（逐维集合相同） | {{metric:EXP-0004:topk-jaccard}} |
| 逐维方法 `EXP-0005` | `spearman_absrho` / `ridge_coef` / `random_forest_importance` | {{metric:EXP-0005:topk-jaccard}} |
| **交付** `EXP-0005`（逐维三方法） | 与基线方法对数不同，数值不可直接比较 | {{metric:EXP-0005:topk-jaccard}} |

### 4.2 bootstrap 入选频率（第二稳定性证据）

训练行内有放回重采样 500 次（seed 固定），每次对两个计算可承受的估计器（`spearman_absrho`、`ridge_coef`）重算 Top-3，
统计每个化合物在每个维度上入选 Top-3 的频率。频率越接近 1，说明名次由数据结构支撑而非样本偶然。

- 平均入选频率（50 维 × 2 估计器）：`{{metric:EXP-0005:bootstrap_mean_top3_inclusion}}`
- `spearman_absrho` 分项：`{{metric:EXP-0005:bootstrap_mean_top3_inclusion_univariate}}`
- `ridge_coef` 分项：`{{metric:EXP-0005:bootstrap_mean_top3_inclusion_ridge}}`
- 共表达块匹配化合物数：`{{metric:EXP-0005:coexpression_compounds_matched}}`（共 231 列；实现用更严格的
  `field_name_python → chemical_name_short` 路径，故不等于 231，披露于论文 4.2）
- 非 PSD 证据：全矩阵最小特征值 `{{metric:EXP-0005:coexpression_min_eigen_full_matrix}}`、块投影前
  `{{metric:EXP-0005:coexpression_min_eigen_raw}}`、投影后 `{{metric:EXP-0005:coexpression_min_eigen_projected}}`

## 5. 结果与解读（写作时按此顺序组织）

1. **每个维度的 Top-3 名单**：完整 50 维 × 3 方法名单以实验产物 `sets.json` 为准（论文表在阶段 B 由 `sets.json` 逐行转录，
   并注明"转录自 EXP 的 sets.json，若与台账不一致以台账为准"）。不得凭印象写化合物名。
2. **名次强度**：图 `{{figure:FIG-0005}}` 同时给出名次与 |ρ| 强度，避免"只报名不报强度"。
3. **稳定性**：图 `{{figure:FIG-0006}}` 与 `{{figure:FIG-0007}}` 分别给出 bootstrap 频率与方法间 Jaccard；
   低频率格子必须在论文里如实标注为"不稳定名次"。
4. **选择规则与不可比口径（先于结果声明）**：以 `topk-jaccard` 为主指标，结合 bootstrap 平均入选频率；基线（2 方法→1 个方法对）与候选（3 方法→3 个方法对）的 Jaccard 不是同一统计量，**不得写"候选优于基线"**；
   本文只把基线当作一致性水平参照，题面要求的逐维 Top-3 由候选交付。
   候选总数与 holdout 预算遵守 `contest.yaml`；Q2 不登记 `baseline-compare`（全局 metricDirection=minimize 与 Jaccard 方向相反）。

## 6. 化学合理性讨论（框架，不预写名次）

按 1.csv 的化合物族核对（族信息来自列名与 8.xlsx `chemical_name` / `origin_paper`）：

- **萜类（酒花来源）**：与 `A_hops_*` / `F_hops_*` 对应时应出现萜烯/萜醇；若出现酵母代谢产物，说明方法捕捉的是风格层共变。
- **酯类（酵母代谢）**：与 `A_esters_*` / `F_esters_*` 对应时应出现乙酸酯/乙酯；`esters_sum` 是派生汇总列，进入 Top-3 必须注明"派生量"。
- **醇类**：与 `alcohol`、`body` 对应时应出现高级醇；`ethanol..v.v.` 是 log10 值（data-quality 2.4 节），系数符号按 log 空间解释。
- **硫化物/缺陷**：与 `dms`、`diacetyl`、`stale_hops`、`t2n` 对应时应出现对应缺陷化合物；后两者在附件中**无阈值**，只能做关联排名。
- **派生汇总列**：`esters_sum`、`aroma_hops_sum`、`acids_sum`、`sulfur_sum` 由多个化合物计算得出，不能当独立化学证据。

合理性的判据是"名次方向与已知化学族一致 + 在 bootstrap 下稳定"，不是"看起来合理"。

## 7. 边界与限制（必须与结论同时出现）

1. **同期关联，非因果**：排名是同一时点的关联强度；2.csv 与 5/6/7 同源，无法提供时间先后或干预证据。
2. **标准化尺度**：目标列是 4.csv 标准化值，\|ρ\| 与系数都是标准化尺度上的关联强度，不是"评分上升 1 分"的效应。
3. **同源派生**：5/6/7 与 2.csv 都由同一批 250 样本派生，不构成外部验证，也不是独立先验。
4. **非 PSD 后处理**：PSD 投影改变特征值谱（负特征值被截断），投影后结构只用于可视化与稳健性参考。
5. **方法一致 ≠ 化学正确**：三种方法一致只说明"在给定数据与尺度下稳定"，化学机理需外部实验验证，超出本附件范围。

## 8. 建议（workbench `recommendations` 义务）

| 建议 | 支持证据 | 适用对象/时点 | 成本与约束 | 如何验证 |
|---|---|---|---|---|
| 用 Top-3 关联筛查指导感官品评预算 | Q2 的 Jaccard 与 bootstrap 频率 | 新品开发早期 | 只覆盖附件中的 50 维；不能替代品评 | 独立批次重复检测 + 盲评 |
| 对低 bootstrap 频率的名次不做工艺决策 | 频率表 | 任何基于 Top-3 的结论 | 需要保留重采样记录 | 换批次复核入选频率 |
| 需要因果结论时补做干预/时间序列实验 | 本文件边界声明 | 工艺调整 | 需要新数据采集 | 干预实验或纵向数据 |
| 需要外部验证时采集独立批次 | 同源派生事实 | 模型外推 | 需要新批次样本与完整 beer_id | 独立批次留出评估 |

## 9. 复现

- 脚本：`src/q2_lib.py`、`src/q2_baseline.py`、`src/q2_topk.py`；独立复算：`src/validate_q2.py`（不 import 建模代码）。
- 产物：`sets.json`、`sets_nested.json`、`metrics.json`、bootstrap 频率 CSV、4 张图。
- 复跑：`modeling_experiment {action:"run", experimentId}`；独立复跑要求原实验 `freezeSources:true` 且 `dependenciesComplete:true`。
- 确定性要求：bootstrap seed、重采样次数、tie-break 顺序必须固定，否则独立复跑会以"未复现 topk-jaccard"失败（如实记录，不掩盖）。
