请使用 Vibe Math Modeling 插件（预设 `Vibe Math Modeling`，切勿使用 `Vibe Math Unify`），在项目目录 `/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3` 中完成 2026 年 MathorCup 大数据挑战赛赛道 A 初赛的全部建模、验证与论文交付（md/tex/pdf 三格式，目标是达成 `engineeringComplete=true, qualityPassed=true, checkpointsPassed=true, final=true`）。

你必须严格遵守以下两部分要求：**第一部分是 Vibe Math Modeling (2.8.6/2.8.9) 插件的 8 条操作铁律与 JSON 契约规范**；**第二部分是我指定的完整数学建模蓝图（必须 100% 严格按照该数学方案编写代码与论文，禁止擅自简化模型或跳过任何指定消融实验）**。

================================================================
第一部分：插件 8 条操作铁律与接口规范（违反任一条会导致 final=false）
================================================================

【铁律 1：配置先行与生命周期事务（init 前一次写死，init 后严禁私改文件）】
1.1 路径与环境：
    - 项目路径 `projectDir`：`/Users/baozhashizitou/Documents/MATHORCUP/work/beer-vmm-final`
    - Python 绝对路径：`/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python`
    - 原始附件与题面源路径：`/Users/baozhashizitou/Documents/MATHORCUP/A/data/raw/`（含 `1.csv`, `2.csv`, `3.xlsx`, `4.csv`, `5.csv`, `6.csv`, `7.csv`, `8.xlsx`, `数据说明.txt`）及题面 `/Users/baozhashizitou/Documents/MATHORCUP/A/problem/statement.md`、`/Users/baozhashizitou/Documents/MATHORCUP/A/problem/2026年MathorCup大数据挑战赛-赛道A初赛.pdf`。
1.2 初始化前定稿：
    - 若项目未初始化，先创建目录并将 `statement.md` 放入 `problem/statement.md`（作为唯一逐字引用源，PDF 仅存档不读取）；
    - 先写完整 `problem/questions.yaml`（Q1 `metric: mae`, Q2 `metric: topk-jaccard`, Q3 `metric: constraint-satisfaction`；三问均设 `needsData: true, needsBaseline: true`）和 `contest.yaml`（`schemaVersion: 2`, `taskType: mixed`, `primaryMetric: mae`, `metricDirection: minimize`, `split: {method: random-holdout, testFraction: 0.2, seed: 20261024}`, `delivery: {template: generic-zh, paperFormats: [md, tex, pdf], requireIndependentRerun: true, requireResolvedCriticalClaims: true}`, `quality: {required: true, coverageReviewRequired: true, review: {required: true, independence: independent_context, allowSameModelDifferentContext: true}, robustness: {required: true, maxHoldoutReuse: 3, methods: [multiple-seeds, param-perturbation]}}`, `runtime: {maxComputeConcurrency: 1, experimentTimeoutSeconds: 1800, maxImprovedModelsPerQuestion: 2}`）；
    - 随后调用一次 `modeling_project {action:"init"}`（生成版本 1 配置快照）和 `modeling_project {action:"plan", fromFile:"problem/questions.yaml", createTasks:true}`。
1.3 配置事务与预算监控：
    - 每次阶段切换前运行 `modeling_project {action:"status"}` 检查 `configState.state == "in_sync"`（且 `configChanged == false`）。
    - 初始化后严禁直接修改 `contest.yaml`；若确需变更配置，必须调用 `modeling_project {action:"config", subaction:"diff"}` 查看影响面，再用 `{action:"config", subaction:"accept", expectedRawSha256:"...", expectedRevision:..., reason:"..."}` 事务接纳。
    - 若启用 `run-control`（`preflight`/`begin`），一旦发现 `usage=unknown` 必须立即 `stop` 并报告，严禁忽略或继续重试。

【铁律 2：严格遵守 9 阶段不可逆顺序（前一阶段 blocker 清零才可进入下一阶段）】
必须严格按以下顺序执行，绝不可颠倒：
- Phase 0：`init` → `probe` → `plan`（只调一次）
- Phase 1：`modeling_data {action:"import"}`（导入 9 个数据文件，不导 PDF）→ `profile` → `run-script` 清洗与构建字典 → `register-clean`（附带完整 `fieldsFile`，每列恰好出现一次，严禁写“其余列”）→ `register-split`
- Phase 2：`requirement-add`（`source.path: "problem/statement.md"`, `source.quote` 必须为原文精确子串）→ `contract-add (contract:"target")` → `contract-add (contract:"model")` → 可选 `workbench configure`
- Phase 3：三问分别 `register` + `run` 真实 Baseline 实验（`modelKind:"baseline"`），确认 `succeeded`
- Phase 4：**在任何 Candidate 实验之前**，每问只调用一次 `modeling_validate {action:"plan"}`（绝不事后补 plan，也绝不一问建多个 plan）
- Phase 5：先在训练子集本地调通代码，再 `register` + `run` Candidate 实验 → `modeling_validate {action:"run"}` → `modeling_validate {action:"independent-rerun"}` → `modeling_project {action:"select", selectionPhase:"validated"}`（若 select 后提示 contract stale，用 `contract-revise` 刷新绑定）
- Phase 6：**在跑扰动实验之前**，先调用 `quality {subaction:"robustness-plan-add"}` 预注册 → 运行带 `requireSeedReceipt:true` 的扰动实验 → 调用 `robustness-plan-execute`
- Phase 7：创建 `modeling_claim` → `requirement-map` → 派生 `subagent` 独立上下文执行 `review-add`（若旧 critical claim 失效或冲突，使用公开的 `supersede` 或 `retract` 退休旧结论并重新映射 coverage）
- Phase 8：确保 `report/paper.md` 已存在 → `quality-plan {auto:true}` → `quality-run` → `quality-report`（确保 `stale=0` 且无 failed）→ `modeling_project {action:"freeze"}`
- Phase 9：`modeling_deliver {action:"figure"}` 登记全部图 → `render` → 编译 `tex`/`pdf` → `artifact (format:"tex")` & `artifact (format:"pdf")` → `check` → `package`

【铁律 3：严控 Holdout 曝光上限（maxHoldoutReuse: 3）与幂等重试（retry）】
3.1 数据集与划分拓扑：
    - `DATA-0001`（`data/clean/q2_raw.csv`：250 行，`beer` 键 + 231 特征 + 50 个 `4.csv` 原始标准化列）→ 注册 `SPLIT-0001`（`seed: 20261024, testFraction: 0.2, rowIdMapping: "positional"`）。**`SPLIT-0001` 仅用于提取训练行（200 行）拟合映射与 Q2 分析，绝不挂载任何实验！**
    - `DATA-0002`（`data/clean/q1_mapped.csv`：`parentId: "DATA-0001"`，基于 `SPLIT-0001` 训练行构造 Q1 评估表）→ 注册同 seed 的 `SPLIT-0002`（确认 `assignmentSha256` 与 `SPLIT-0001` 完全一致）。**全项目只有 Q1 的最终模型使用 `SPLIT-0002`！**
    - `DATA-0003`（`data/clean/q3.csv`：Q3 视图，`targetColumn` 指向真实数值列如 `ethanol..v.v.`，不挂载随机 `splitId`）。
3.2 曝光预算分配：
    - 插件按实际测试样本行累计曝光，且失败实验也可能占用预留曝光！因此所有脚本必须先在训练折内调通，确认无 bug 后再注册挂载 `SPLIT-0002` 的实验。
    - `SPLIT-0002` 上最多只跑 **3 个实验**：1 个 Baseline（逐目标训练中位数）+ Candidate 1（图正则低秩多输出回归）+ Candidate 2（HGB 非线性对照及 OOF 融合）。
    - **所有超参数搜索（$r,\lambda,\gamma,\kappa,\kappa_R$）、第 8 节的 9 项消融实验、以及 Phase 6 的稳健性扰动实验，一律在训练折内部完成（设 `evaluationUse: "train-only"` 或不挂载 `splitId`）**，绝不消耗 `SPLIT-0002` 预算！
3.3 失败重试与防并发堆积（2.8.9 语义）：
    - 注册实验时指定 `idempotencyKey`。若实验 `failed/timed-out`，相同调用只会返回旧失败（`retryRequired:true`）；修复代码或依赖后，必须显式传 `retry: true, retryReason: "..."` 发起重试，严禁换名字无限新建替身实验。遇到 `COMPUTE_BUSY` 时等待当前队列完成。

【铁律 4：Python 沙箱契约（modeling_contract）与 Seatbelt 冻结依赖】
4.1 预先生成纯常量模块：
    - 实验在 macOS Seatbelt 沙箱中运行，无法读取未登记的原项目文件。在 Phase 1 必须从真实表头程序生成 `src/target_columns.py`（内含 `FEATURE_COLS` 231 列名数组、`TARGET_COLS` 50 列名数组、以及 37 log10 / 33 linear / 161 unverified 分类常量），并将其加入所有实验的 `dependencies` 列表。
4.2 实验注册必填参数：
    - 所有实验必须声明 `params.freezeSources: true`、`params.dependenciesComplete: true`、`params.dependencies: ["src/target_columns.py", ...]`（列全所有 import 的辅助脚本、校准字典与数据文件）以及 `params.features: [...]`（长度为 231 的列名数组，Baseline 常数模型设为 `[]`）。
4.3 脚本内部接口（严禁猜接口）：
    - 只能使用 `from modeling_contract import seed, emit_metrics, emit_predictions, emit_output, save_figure`（**注意：没有 `emit` 函数！**）。
    - 脚本开头必须调用 `s = seed()` 并将其作为所有随机数生成器的种子（满足 `requireSeedReceipt: true`）。
    - `emit_metrics({...})` **只能包含有限数值（int/float）**，任何字符串、`None`、`NaN`、`Inf` 或列表都会导致整次写入被拒并判 `NO_OUTPUT`！逐维数组、消融表、Top-3 名单、文字说明一律通过 `emit_output(name, value)` 写入 `outputs.json`。

【铁律 5：指标键名与预测文件格式严格对齐（无自动 alias）】
5.1 Q1（多输出回归）：
    - 注册参数：`evaluation: {kind: "multi-output", targetContractId: "TGT-0001", metric: "mae", metricKey: "mae", predictionsFile: "predictions.csv", idColumn: "row", aggregation: "uniform-average"}`。
    - `predictions.csv` 格式：第一列为 `row`（`0..n_test-1`，严格对应 `test.csv` 行序），后接 50 个预测列 `y_pred__<真实目标列名>`（与 50 个目标列一一对应）。
    - `emit_metrics` 必须包含 `"mae"`（50 维均值的留出 MAE），同时写入 `"r2_50dim"`、`"skill_50dim"` 等数值；逐维 $\mathrm{MAE}_t, R_t^2, \mathrm{Skill}_t$ 与 0–6 分级结果通过 `emit_output` 及独立 CSV 保存。
5.2 Q2（稳定因素识别）：
    - 注册参数：`evaluation: {kind: "set-stability", metricKey: "topk-jaccard", topK: 3, setsFile: "sets.json", dimensions: [...50个感官列名...], methods: ["total_spearman", "within_style_spearman", "graph_lowrank", "consensus"]}`。
    - `emit_metrics` 必须包含 `"topk-jaccard"`。
5.3 Q3（风格条件生成与迁移）：
    - 注册参数：`evaluation.metricKey: "constraint-satisfaction"`，`params.stochastic: true`。
    - 为通过 `simulation-seeds` 验证，脚本对每个随机种子（如 3 个 seed）必须写出 `run-seed-<seed>.json` 文件并登记在产物中，`emit_metrics` 必须包含 `"constraint-satisfaction"`，同时报告归一化能量距离 $\mathcal E_{\mathrm{norm}}$ 等指标。
5.4 Claim 与 ROB 引用对齐：
    - `modeling_claim` 的 `refs` 只允许引用主 `metricKey`（Q1 `"mae"`、Q2 `"topk-jaccard"`、Q3 `"constraint-satisfaction"`）。
    - 若某项消融或稳健性检验为负结果，使用 `claimType: "negative_result"` 并通过 `appliesToPlanId: "ROB-000x"` 绑定对应稳健性计划（若同一范围内有正面的稳定性结论冲突，需先 `supersede`/`retract` 矛盾结论）。

【铁律 6：模型契约（MCON）必须使用声明式 AST 与 boundaryCases】
创建 `contract:"model"`（`MCON-0001..0003`）时，禁止使用自由文本公式或 `eval`，必须一次性填齐 `variables`（含 `unit`）、`objective`、声明式 AST `formula` 和 `boundaryCases`。例如缺陷超阈程度 $e_j(c)=\max(c_j/T_j-1,0)$ 的 AST 写法为：
```json
{
  "formula": {"max": [{"sum": [{"linear": [{"coef": 1, "var": "ratio"}]}, {"constant": -1}]}, {"constant": 0}]},
  "variables": [{"name": "ratio", "unit": "unitless"}],
  "boundaryCases": [
    {"id": "below-threshold", "inputs": {"ratio": 0.5}, "expected": 0, "unit": "unitless", "reason": "未超阈时超阈程度为0"},
    {"id": "at-threshold", "inputs": {"ratio": 1.0}, "expected": 0, "unit": "unitless", "reason": "恰好阈值处超阈程度为0"},
    {"id": "above-threshold", "inputs": {"ratio": 2.0}, "expected": 1, "unit": "unitless", "reason": "两倍阈值处超阈程度为1"}
  ]
}
若后续 model-condition 检查报缺失，使用 quality {subaction:"contract-revise", contract:"model", contractId:"MCON-…"} 修订并重跑检查。
【铁律 7：独立审查必须派生 subagent 子会话 + review-resolve 闭环】
主代理绝不能自己调用 review-add 并自称 independent_context（会被 review-independence 门禁直接拒绝）。
必须调用 subagent 工具启动独立子代理，对 targetContract（TGT-0001..0003）、modelContract、requirements-coverage、所有关键 claim 及 delivery 执行独立审查并调用 review-add。
若任何早期非 stale 审查存在未解决的 critical finding，修复后必须先调用公开的 modeling_project {action:"quality", subaction:"review-resolve"} 记录解决方案，再由 subagent 重新出具 verdict:"passed" 的最新审查。
【铁律 8：论文占位符渲染、artifact 绑定与同版同步】
report/paper.md 中引用的所有核心实验指标、结论与图表，必须使用 {{metric:EXP-xxxx:mae}}、{{claim:CLAIM-xxxx}}、{{figure:FIG-xxxx}} 占位符，严禁手抄数字。
图中文字一律使用英文（防止本机 matplotlib 缺中文字体乱码），图注（caption）与论文正文使用中文。
收尾顺序不可颠倒：freeze → modeling_deliver {action:"render"}（生成 report/rendered.md 并确认无 {{ 残留）→ 从 rendered.md 编译生成 report/paper.tex 和 report/paper.pdf → 调用 modeling_deliver {action:"artifact", format:"tex"} 和 {action:"artifact", format:"pdf"} 将 tex/pdf 哈希绑定到当前 render → 调用 modeling_deliver {action:"check"} 确认 engineeringComplete=true, qualityPassed=true, checkpointsPassed=true, final=true → 最后调用 modeling_deliver {action:"package"}。
同版铁律：一旦修改了 report/paper.md 的任何一字，旧的 render 和 tex/pdf 立即变为 RENDER_STALE / ARTIFACT_FROM_OLD_RENDER，必须重新执行 render → 编译 → artifact 绑定 → check → package。
================================================================
第二部分：必须严格实现的数学建模蓝图（Vibe Math Modeling 最终建模方案）
================================================================

【总体采用“稳健化学表示—网络辅助预测—稳定因素识别—风格条件生成—约束风格迁移”的统一框架。】
三问共享数据字典、化合物网络和感官预测器，但分别评价预测能力、关联稳定性和生成／迁移质量。任何复杂组件都必须通过消融证明价值，不预设其一定优于简单模型。

---

一、研究对象与统一符号

按目前核对的附件，设：
$$n=250,\qquad p=231,\qquad q=50,$$
分别表示啤酒样本数、化学及理化变量数、感官维度数。细粒度风格共 22 类。

| 符号 | 定义 |
|---|---|
| $X=(x_{ij})$ | 1.csv 中实际存储的化学及理化观测 |
| $C=(c_{ij})$ | 在尺度、编码和单位可以确认时得到的物理浓度 |
| $Y=(y_{it})$ | 4.csv 中的标准化感官标签 |
| $s_i$ | 样本 $i$ 的风格标签 |
| $Z$ | 从训练数据拟合的稳健化学表示 |
| $G=(V,E,W)$ | 化学及理化变量的关联网络 |
| $f(X)$ | 化学谱到感官标签的预测器 |
| $F_{j,s}$ | 风格 $s$ 下变量 $j$ 的条件边际分布 |
| $\mathcal T_{a\rightarrow b}$ | 从风格 $a$ 向风格 $b$ 的迁移算子 |

三问的数学目标为：
- Q1：估计 $Y=f(X)+E$，并形成有明确定义的 0–6 分级
- Q2：识别对各感官维度具有稳定关联和解释价值的 Top-3 化合物
- Q3：估计 $p(X\mid s)$，并求解物理与缺陷约束下的风格迁移

Q1 主模型只使用化学及理化检测量。风格标签用于分层验证、Q2 的混杂分析和 Q3 的条件生成。加入风格的感官预测模型仅作为辅助对照。

---

二、共同数据模型：建立“尺度—编码—单位—证据”字典

2.1 以 `beer` 为主键，保留原始附件。
1.csv、4.csv、7.csv 使用唯一的 `beer` 对齐，并检查唯一性、样本集合和逐行对应关系。`beer_id` 在部分表中发生截断，不能作为连接键。所有修正、填补及变换都产生派生表示，原始观测不覆盖。

2.2 将 231 个变量按直接证据分为三组。
| 分组 | 数量 | 使用原则 |
|---|---:|---|
| 可与校准表核对 log10 关系 | 37 | 正浓度部分可按 $10^x$ 反变换，编码点单独处理 |
| 可与校准表核对线性数值关系 | 33 | 保留线性数值，另行核验单位及异常观测 |
| 无校准表直接覆盖 | 161 | 保留观测尺度；进一步的变换解释标为推断 |

每个变量建立：
$$\mathcal D_j=\{\text{名称、类型、存储尺度、反变换、单位、编码规则、证据等级}\}.$$
变量类型至少区分：单体化合物；理化指标；派生汇总量（`kcalperc`, `acids_sum`, `esters_sum`, `aroma_hops_sum`, `sulfur_sum`）。校准表用于判断尺度关系，不视为逐单元格无误的浓度真值。没有直接证据的变量不能仅凭负值就确定为某一种对数底数。

2.3 明确记录零、地板编码与真实零的区别。
已核实的编码现象包括：
- 37 个可校准 log10 变量中，有 **755 个单元格对应校准表记录的 0**，其存储值符合“该列最小正浓度的一半取 log10”的关系。
- 161 个未直接校准变量中，有 **142 列**出现约 $-1.81781854$ 的共同地板值，合计 **6,807 个单元格**。
这些点应设置编码指示：
$$d_{ij}^{\mathrm{floor}}=\mathbf 1\{x_{ij}\text{ 命中已识别地板编码}\}.$$
必须区分：记录为零 $\neq$ 真实浓度严格为零 $\neq$ 已知低于确定检出限。主模型首先复现**观测分布**。若有可信检出限，再增加潜在浓度的左删失分析；没有检出信息时，不把最小正观测值直接认定为仪器检出限。

2.4 缺失值与算法表示按任务处理。
1.csv 有 73 个缺失单元格，集中在 9 列、63 行（`amyl.acetate` 27, `aroma_hops_sum` 13, `methylpyrazine` 12, `X2.3.butanedione` 9, `X3.methylbutanal` 7, `ethyl.nicotinate` 2, `ethyl.isobutyrate` 1, `furfural` 1, `phenylacetaldehyde` 1）。
Q1 的主预处理为：当前训练折中位数填补＋这 9 列的缺失指示变量。
线性模型比较两种化学表示：
1. 原存储尺度上的训练集标准化（配合必要的数值稳定性边界控制）；
2. 训练集经验分布的 Rank-Gauss 变换：
$$u_{ij}=\widehat F_{j,\mathrm{train}}(x_{ij}),\qquad z_{ij}=\Phi^{-1}\left[\operatorname{clip}\left(u_{ij},\varepsilon,1-\varepsilon\right)\right],\qquad \varepsilon=\frac{1}{2n_{\mathrm{train}}}.$$
重复值使用中秩；超出训练范围的输入采用预先固定的边界规则。Rank-Gauss 用于抑制极端点的线性外推，但可能损失幅度信息，必须通过消融评价。树模型可以直接使用原存储尺度。
Q3 估计边际分布时只使用有效观测，不能把中位数填补产生的堆积误认为真实分布质量点。

---

三、问题一：图正则低秩多输出预测与有界相对分级

3.1 将感官预测与评分标度分开。
首先预测附件真实可观测的标准化标签 $Y$，再定义分级。不得先构造人为分数，再将其误称为原始人工评分。
训练时按当前训练集合对各目标中心化、缩放：
$$\widetilde y_{it}=\frac{y_{it}-\mu_{t,\mathrm{train}}}{s_{t,\mathrm{train}}}.$$
近常数目标单独处理，避免除以接近零的尺度。

3.2 主要结构模型：图正则低秩多输出回归。
设 $\widetilde Y=ZB+\mathbf 1b^\top+E$，求解：
$$\min_{B,b}\frac{1}{n_{\mathrm{train}}}\left\|\widetilde Y-ZB-\mathbf 1b^\top\right\|_F^2+\lambda\|B\|_F^2+\gamma\operatorname{tr}(B^\top L_GB),\qquad \text{s.t. }\operatorname{rank}(B)\le r.$$
对带符号的边权：
$$L_G=D_{|W|}-W,\qquad D_{|W|,jj}=\sum_k|w_{jk}|,\qquad \operatorname{tr}(B^\top L_GB)=\frac12\sum_{j,k}|w_{jk}|\left\|B_{j\cdot}-\operatorname{sign}(w_{jk})B_{k\cdot}\right\|_2^2.$$
缺失指示变量等辅助变量不强行连接到化合物图，其图惩罚块设为零。
在尺度规范化后，初始搜索：$r\in\{3,6,10\},\ \lambda\in\{0.1,1,10\},\ \gamma\in\{0,0.1,1\}$（在训练内部交叉验证中进行，并通过 $\gamma=0$ 消融检验图正则收益）。

3.3 控制候选数量，设置明确对照。
- 逐目标训练中位数（无化学信息基线，作为 Q1 Baseline 实验登记）
- 普通 Ridge（检验稳健表示与基础线性信号）
- 图正则低秩回归（检验共享结构及网络信息，作为 Candidate 1 登记）
- HGB（检验非线性关系）及训练内 OOF 简单融合：
$$\widehat Y=w_0\widehat Y_{\mathrm{median}}+w_1\widehat Y_{\mathrm{graph}}+w_2\widehat Y_{\mathrm{HGB}},\qquad w_k\ge0,\ \sum_kw_k=1$$
权重仅设置为全局一组，或 Aroma、Flavour、其他感官三组各一组（作为 Candidate 2 登记）。没有稳定融合收益时，保留最可靠的单模型。

3.4 0–6 分级的主规则。
定义参考啤酒群体中的相对感官强度等级：
$$a_{it}=\widehat F^{\mathrm{mid}}_{Y_t,\mathrm{train}}(\widehat y_{it}),\qquad \widehat F^{\mathrm{mid}}_t(v)=\frac1{n_{\mathrm{train}}}\sum_{\ell\in\mathrm{train}}\left[\mathbf 1(y_{\ell t}<v)+\frac12\mathbf 1(y_{\ell t}=v)\right].$$
交付连续分数 $g^{\mathrm{continuous}}_{it}=6a_{it}$ 以及离散等级：
$$g_{it}=\min\left\{6,\max\left[0,\left\lfloor6a_{it}+\frac12\right\rfloor\right]\right\}.$$
明确说明：等级 0 不自动表示该风味不存在；等级 6 不自动表示原人工评分满分；缺陷维度的相对高等级不等于已超过化学缺陷阈值；标准化标签的 0 不作为真实等级 3 的锚点。同时增加一套预先定义参考端点的有界线性映射作为分级敏感性分析。

3.5 Q1 的评价指标。
以真实 $Y$（及基于训练折严格构造的验证口径）报告 $\mathrm{MAE}_t$、$R_t^2$、$\mathrm{Skill}_t=1-\mathrm{MAE}_{t,\mathrm{model}}/\mathrm{MAE}_{t,\mathrm{median}}$，同时报告宏平均、Aroma/Flavour/其他感官分组结果、改善和恶化的维度数、极端样本误差及配对模型差异。

---

四、问题二：共表达网络、风格混杂分析与稳定 Top-3

4.1 建立两个用途不同的网络。
- 附件描述网络：基于 2.csv，回应题目、展示附件提供的整体结构；
- 训练网络：当前训练样本重算 Spearman，用于 Q1 正则化及需要评价泛化的分析。
完整对齐 231 个变量，并对单体化合物、理化指标和派生量作类型标记。最终 Top-3 化合物名单不把 `pH`、颜色或 5 个汇总量冒称为单体化合物；这些因素另列为辅助解释。
主网络采用 $w_{jk}=\widehat\rho_{jk}\mathbf 1\{|\widehat\rho_{jk}|\ge\tau\},\ w_{jj}=0$，$\tau\in\{0.4,0.5,0.6\}$，通过 bootstrap 计算边的出现频率作为可靠性标注。

4.2 网络模块用于识别共同变化的化学因素。
基于 $|W|$ 识别模块 $M_1,\ldots,M_K$，模块得分定义为 $m_{ik}=\operatorname{PC1}(Z_{i,M_k})$，先分析模块与感官维度的关系，再解释模块内候选化合物。

4.3 同时计算总体关联与风格内关联。
- 总体关联：$\rho^{\mathrm{total}}_{jt}=\operatorname{Spearman}(X_j,Y_t)$。
- 风格内关联：令 $H$ 为风格虚拟变量和截距构成的设计矩阵，对秩进行风格残差化：
$$r_j^X=\left[I-H(H^\top H)^\dagger H^\top\right]\operatorname{rank}(X_j),\qquad r_t^Y=\left[I-H(H^\top H)^\dagger H^\top\right]\operatorname{rank}(Y_t),\qquad \rho^{\mathrm{within}}_{jt}=\operatorname{Corr}(r_j^X,r_t^Y).$$
据此区分：总体与风格内均稳定的关联、主要体现风格差异的标记物、被风格差异遮蔽的关联、不同风格方向不一致的异质关联。

4.4 最终 Top-3 采用固定综合规则。
对实际单体化合物候选，定义：
$$S_{jt}=\frac13\left[R(|\rho^{\mathrm{total}}_{jt}|)+R(|\rho^{\mathrm{within}}_{jt}|)+R(|\widehat B_{jt}|)\right],$$
其中 $R$ 为“数值越大、排名百分位越高”的统一转换。
进行 $B=500$ 次风格分层 bootstrap（固定已选超参数，在每次重采样中重拟合预处理、训练网络和模型），计算入选频率：
$$\pi_{jt}=\frac1B\sum_{b=1}^{B}\mathbf 1\{j\in\operatorname{Top3}^{(b)}_t\}.$$
最终优先按 $\pi_{jt}$ 排序，以平均综合分数裁决并列。同时保存三类单方法的 Top-3、最终综合 Top-3、bootstrap 入选频率及方法两两 Jaccard 系数 $J(A,B)=|A\cap B|/|A\cup B|$（作为 Q2 实验的主指标 `topk-jaccard`）。

4.5 化学合理性与补充证据分层。
每个最终候选记录 $\{\text{方向、强度、频率、模块、风格混杂、化学解释、证据等级}\}$，并使用 6.csv（方向与数值复核）、7.csv（183 个非全缺描述符跨来源比较）、8.xlsx MDI/SHAP（已有模型对照）作为非独立外部验证的补充证据表。

---

五、问题三的生成模型：风格收缩边际与混合边际 Copula

5.1 主任务学习已有目标风格。
使用目标风格已有训练样本学习 $p(X\mid s)$，在风格内部留出真实样本（重复风格内 3 折）评价；Tripel、Kriek、Lambic 全部排除训练的实验仅作为未见风格泛化扩展。

5.2 风格边际采用层次收缩。
$$\widehat F_{j,s}=\omega_s\widehat F^{\mathrm{emp}}_{j,s}+(1-\omega_s)\widehat F^{\mathrm{pool}}_j,\qquad \omega_s=\frac{n_s}{n_s+\kappa},\qquad \kappa\in\{0,5,15\}.$$
有地板编码的变量使用观测混合分布：
$$F^{\mathrm{obs}}_{j,s}(v)=\pi^{\mathrm{floor}}_{j,s}\mathbf 1\{v\ge v_j^{\mathrm{floor}}\}+(1-\pi^{\mathrm{floor}}_{j,s})F^{\mathrm{nonfloor}}_{j,s}(v).$$

5.3 Copula 负责依赖结构。
在条件边际下构造潜变量 $z_{ij}=\Phi^{-1}[\widehat F_{j,s_i}(x_{ij})]$（质量点采用中点处理，并以随机化处理作敏感性对照）。相关矩阵采用风格间收缩：
$$\widehat R_s=\eta_s\widehat R_s^{\mathrm{emp}}+(1-\eta_s)\widehat R_{\mathrm{shared}},\qquad \eta_s=\frac{n_s}{n_s+\kappa_R},\qquad \kappa_R\in\{20,50,100\},$$
投影为正定相关矩阵并向单位阵收缩。采样 $z^*\sim N(0,\widehat R_s)\Rightarrow u_j^*=\Phi(z_j^*)\Rightarrow x_j^*=\widehat F_{j,s}^{-1}(u_j^*)$，对已确认尺度的变量再转为 $c_j^*$，派生汇总量由单体重新计算或检验一致性。

5.4–5.6 三层检查、普通生成 vs 低缺陷生成、感官画像比较。
普通条件生成与低缺陷生成（对有阈值的缺陷施加 $e_j(c)=\max(c_j/T_j-1,0)=0$）分别评价，报告观测分布合理性、物理有效性、缺陷风险，以及经 Q1 预测器得到的感官画像 $\widehat Y^*=f(X^*)$ 与真实留出样本 $Y$ 的比较。

---

六、跨风格迁移：分布映射初始化与最小改动约束优化

6.1 分位数映射给出初始化（Pils/Lager $\to$ Tripel）：
$$x_j^{(0)}=\widehat F_{j,\mathrm{Tripel}}^{-1}\left[\widehat F_{j,\mathrm{Pils}}(x_j^{\mathrm{source}})\right].$$

6.2 在可行域中进行最小改动优化。
在单调规范化坐标 $v_j=h_j(x_j)$ 及低维表示 $a=Av$ 下，定义目标风格马氏距离（带协方差收缩）$D_{\mathrm{target}}(v)=(Av-\mu_{\mathrm{target}})^\top\Sigma_{\mathrm{target}}^{-1}(Av-\mu_{\mathrm{target}})$，求解：
$$\min_v (v-v^{(0)})^\top Q(v-v^{(0)})+\lambda D_{\mathrm{target}}(v)+\eta\|D(v-v^{\mathrm{source}})\|_1$$
满足物理边界、缺陷不恶化约束、派生量关系与可信变动范围。

6.3–6.4 题目指定缺陷的映射、双阈值情景与 Pareto 分析。
- `DMS`（mean 阈值 17.25 μg/L，median 19 μg/L）、`X2.3.butanedione`（mean 0.29925 mg/L，median 0.09 mg/L）、`X4VG`（mean 0.206333 mg/L，median 0.20 mg/L）：分别检验“超阈不恶化” $c_j^{\mathrm{new}}\le\max(c_j^{\mathrm{source}},T_j)$ 与“绝对浓度不增” $c_j^{\mathrm{new}}\le c_j^{\mathrm{source}}$ 两种策略，并对比 mean 与 median 两种阈值情景；
- `X.E..2.nonenal`（无阈值）：施加 $c_{\mathrm{t2n}}^{\mathrm{new}}\le c_{\mathrm{t2n}}^{\mathrm{source}}$；
- `stale_hops`（感官维度）：使用 Q1 感官预测代理筛查并检查不确定性。
改变 $\lambda,\eta$ 绘出“目标风格接近程度 $\leftrightarrow$ 谱改动规模”的 Pareto 前沿，如实披露缺陷约束与迁往 Tripel 之间的可行性张力。

---

七 & 八、验证设计、能量距离归一化与 9 项必做消融实验

- Q3 能量距离使用固定训练集标准化表示，报告归一化能量距离 $\mathcal E_{\mathrm{norm}}=\sqrt{\max(\mathcal E^2,0)/D_{\mathrm{ref}}}$（$D_{\mathrm{ref}}$ 为训练真实样本典型两两距离），并提供相同样本量的真实—真实参照。
- 必须在训练内 CV / 风格留出上完成并输出以下 **9 项消融实验表**：
  1. 原尺度标准化 vs Rank-Gauss
  2. 普通 Ridge vs 低秩回归
  3. $\gamma=0$ vs 图正则
  4. 总体关联 vs 风格内关联
  5. 独立边际 vs Copula
  6. 独立风格估计 vs 收缩估计
  7. 不考虑编码质量点 vs 混合边际
  8. 普通生成 vs 低缺陷生成
  9. 分位数迁移 vs 约束优化
  若某个复杂组件没有稳定增益，如实报告该负结果并按验证规则裁决。
