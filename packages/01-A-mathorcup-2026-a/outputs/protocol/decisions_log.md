# 决策与协议变更日志（Lead 维护，可回读）

> 记账纪律：本文件只记录**已经发生**的处置与理由；每一条都指向台账 id 或文件。论文的"失败与修正"一节直接取材于此。

## 0. 台账状态快照（写作时点）
- 项目：`mathorcup-2026-a`，目录 `/Users/baozhashizitou/Documents/MATHORCUP/A`。
- `data-ready`：ok。`baseline-ready`：Q2/Q3 缺基线（已派单，见 §4）。`modeling`：三问均未 select。`writing`：无 claim、无 paper。`delivery`：未 freeze。

## 1. `contest.yaml` 变更（必须记录，因为台账会报 `configChanged`）
- **变更时点**：项目 init 之后、**任何实验之前**（init 13:04，首次实验 EXP-0002 于 13:26 登记；EXP-0012 于 13:36 跑通）。
- **改了什么**：
  1. `delivery.paperFormats: [md]` → `[md, tex, pdf]`（用户明确要求三种格式）。
  2. `evaluation.primaryMetric: rmse / minimize` → `r2 / maximize`（题面要求"结论量化"，Q1 的 50 维主指标在项目内统一用逐维 R² 均值；per-question 指标已在 `problem/questions.yaml` 与 workbench analysisPlan 中分别声明）。
  3. `evaluation.baseline` 注释说明为"每维训练均值的常数基线（空特征）"。
- **影响评估**：三项变更**均早于**本项目登记的每一个实验（最早实验 EXP-0002 登记于变更之后），因此不存在"旧协议下跑出的结果被新协议解释"的情况。台账的 `configChanged` 警告属**时序无关的机械比对**，此处如实记录、不作辩解。
- **不改回的**理由：`r2/maximize` 是实际执行的协议；改回会造成"记录与执行不一致"，比保留变更加危险。

## 2. 关键处置（按发生顺序）
| # | 事件 | 处置 | 证据 |
|---|---|---|---|
| 1 | 首次 `modeling_data inventory` 用 Downloads 绝对路径 → `VMU_PACK_MODELING_CONTEST_PATH_ESCAPE` | 不绕过检查；把附件 `cp` 进 `data/raw/` 后用**项目内相对路径**重跑 inventory，成功 | 台账 revision 28；10 个附件 sha256 全列 |
| 2 | 题面"226 种啤酒"vs 数据 250 | 以数据为准，判题面笔误 | `outputs/audit/audit.json` C1 |
| 3 | 题面"2.csv 皮尔逊"vs 数据说明"Spearman" | 重算 30 对，2.csv 与 Spearman 完全一致、与 Pearson 不一致 → 认定 Spearman，题面笔误 | `outputs/audit/corr_type_check.csv` |
| 4 | 3.xlsx 是否为已标注评分卡 | 逐 sheet 检查评分单元格，全为空模板 → 只作**维度与 0–6 刻度定义** | `audit.json` C3 |
| 5 | 1.csv 尺度 | 用 8.xlsx Calibrated 回算：**37 列 log10 / 33 列 linear / 161 列 unverified（其中 145 含负值必非原始浓度、16 两可）**；负值 ⇔ 原始浓度 <1 | `outputs/audit/scale_identification.csv`、`scale_report.json`（SCRIPT-0008） |
| 6 | `calibrated==0` 的含义 | 实测 = `log10(最小正浓度/2)` 的 **LOD/2 左删失替代码，755 格** → 零不是真零，低浓度端不可作物理浓度解释 | `scale_report.json` |
| 7 | 4/7.csv 的 `beer_id` 脱敏 | 仅 96 个唯一值；三表 `beer` 列顺序一致 → **按 `beer` 连接**，禁止按 beer_id | `audit.json` C9 |
| 8 | 2.csv 行列名与 1.csv 列名对不上 | 209 列经 `chemical_name_short→field_name_R` 命名映射、22 列位置映射；**209 个可命名列的位置映射与名字映射 100% 一致** → 位置映射成立 | `outputs/protocol/corr2_map.json`（SCRIPT-0010） |
| 9 | threshold 表 `field_name_python` 是人读名（`2,3-butanedione`），join 不上 | 改用 `field_name_R`（`X2.3.butanedione`）；修进 `C.threshold_table()` | reviewer REV 系列 |
| 10 | 曾把 4.csv 当作"单位方差 z" | reviewer 实测逐列 sd 0.37–0.86、mean≈0 → **改为主口径"物理锚定"P1（OAV=1↔等级1，每数量级 +1 等级）+ 三套敏感性** | `outputs/protocol/grade_calibration_SPLIT-0001.json`（13/50 锚定） |
| 11 | 早期 `grade_calibration.json`（n=250 全量拟合、14 维） | **移入 `outputs/protocol/superseded/` 并写 README**，不删除（保审计痕迹）；论文只引两份 tagged canonical | `superseded/README.md` |
| 12 | `DATA-0001` 只有 16 条占位字段、且无 50 个目标列 | 升级为 **DATA-0002**（250×284，284 条完整字段逐列来自真实表头，parentId=DATA-0001），并登记 SPLIT-0002（与 SPLIT-0001 逐 beer 相同） | SCRIPT-0011/0019；`outputs/protocol/model_table_checks.json` |
| 13 | `register-split` 无 stratify 参数 → SPLIT-0001/0002 未分层，holdout 缺 `West Flanders ale` | 主口径仍用**台账登记版**（可对账），另建**分层复核版**（22/22 类）用于稳健性；两版 92 beer 不同，均如实披露 | `data/splits/README.md` |
| 14 | **空特征基线被 pack 拒**（`needs params.features`） | 不造假特征；查明 `params.family` 必须在 `mean/median/constant` 三族内 → 用 `family="mean"`、`features=[]` 登记并跑通 | **EXP-0012 succeeded**（rerunOf EXP-0007） |
| 15 | 实验 failed（保留，不覆盖） | EXP-0002 `inf` 指标被拒；EXP-0004/EXP-0005 `NO_OUTPUT`（未调 emit / emit 拒字符串）；EXP-0008 `NO_OUTPUT` | `experiments/*/result.json` |
| 16 | `modeling_contract` 注入方式未知 | 用**受控探针实验 EXP-0005**查清：sys.path 注入、cwd=experiments/<EXP>/、env 变量清单、`emit_metrics` **只收有限数值**；据此写 `src/emit.py` 统一桥接层 | `outputs/probe/experiment_env.json` |
| 17 | pack 合同缺口：裸键 `r2`、`predictions.csv` 必须单列 | 修正基线并入 EXP-0012：metrics 补 `r2/r2_overall/mae`；`predictions.csv`=单列 overall 合同、`predictions_long.csv`=50 维长表 | EXP-0012（`verified:true`） |
| 18 | 数值不稳定：协议字面预处理（折内中位数+标准化，无防护）下 ridge OOF R² = **−0.9301 ± 1.1423**（15 折口径；39/50 维为负）。**【更正】先前引用的 −2.66 是 5 折单次试点、单折数值爆炸的数字，不是正式口径** | **根因=1.csv 的混合尺度**：33 个线性浓度列跨 1e-9~1e3，与 37 个 log10 列混做折内标准化 → 留出样本 z 值爆到几十（实测 fold2 `pred_sd` 0.57→4.2）。三条防护路径**几乎等价**：winsorize 1/99% +0.2002、尺度协调 +0.1987、标准化后裁剪 ±8 +0.1997（叠加无额外增益），Lead 独立管线复现 +0.2026 → 互相印证 | `outputs/q1/prep_sweep.csv`；`outputs/q1/B1_*` |

## 3. 已登记但**尚未**构成结论的东西（防止混谈）
- `EXP-0003`（Q2 共表达图）`succeeded`，只说明**运行成功**，其 Top-3 选择尚未登记、稳定性/多重比较尚未独立复算 → **不是 Q2 结论**。
- Q1 的候选族数字（ET +0.2319、融合 +0.2473 等）目前来自 modeler 的开发运行，**尚未全部成为正式 EXP** → 论文引用前必须替换为 EXP 指标占位符。
- Q3 的风格命中率 0.99 是**饱和指标**（锚定到风格质心后分类器必然判对），不可作质量证据；真正的证据是 per-style 保真度、能量距离、缺陷越阈率与 small-n 不确定度。

## 4. 当前阻塞与派单
- `baseline-ready`：Q2/Q3 缺 `modelKind=baseline` 的已跑通实验 → 已派 modeler-q2（单变量 Spearman 基线）、modeler-q3（风格均值对角高斯基线）。
- `modeling`：三问均待 `select`（需先有候选 EXP + 验证）。
- `writing`：待 claim 与 `report/paper.md`（writer 已在建骨架与 tex/pdf 管道）。
- `delivery`：待 `freeze`。

## 5. 后续关键发现（追加，按发生顺序）
| # | 事件 | 处置 | 证据 |
|---|---|---|---|
| 19 | **2/5/6.csv 都是同批数据的相关矩阵重算，不是独立外部先验** | 撤销"6.csv 为独立先验"的表述；新增 CLAIM-0006 记录循环验证；论文把 prior_spearman 0.7341 改称"同数据一致性" | reviewer REV-0011；`CLAIM-0006` |
| 20 | Q2 跨方法稳定性 **FAIL**：Jaccard 均值 0.1623（模型）/0.2196（reviewer 独立复算），远低于预登记的 0.50 | 作为核心负结果保留，不改阈值；Top-3 降级为"共识候选 + 不确定性" | `CLAIM-0005` |
| 21 | Q3 `independent-rerun` **VAL-0012 FAILED**：评估脚本固定 seed 且读被重写的共享产物 | 记 failed；要求改为读实验目录产物或按 MODELING_SEED 现场生成；在论文单列"不可复现/无效验证的处置" | `VAL-0012` |
| 22 | Q1 EXP-0025 全套验证 PASS（holdout-metrics/baseline-compare/leakage/split/independent-rerun） | 记录为 Q1 当前可用的已验证候选；B6_fusion 若登记将再比较 | VAL-0013..0017 |
| 23 | 计算槽 `maxComputeConcurrency=1` 导致 Q3 基线被 Q1 长实验阻塞（EXP-0017 8 分钟） | 不擅自 cancel 他人实验；改为排队 + 要求单次实验 <120s；最终 cancel 由实验所有者自决 | EXP-0017 result.json |

## 6. 交付口径变更（P1 → P2 作为交付主表）

**问题**：题面要求给出"0–6 分制的分级评分结果"。但 P1（物理锚定）在 250×50 的交付表上只产出
**等级 0–3**，分布为 `[300, 11663, 494, 43, 0, 0, 0]`（93% 落在等级 1），**实际不满足 0–6 分级的要求**；
P2（极差锚定）分布为 `[822, 2802, 2894, 2679, 2004, 1113, 186]`，覆盖 0–6 全档，QWK(P1 vs P2)=0.209–0.493。

**决定**：**交付主表改用 P2**，P1 作为"物理锚定变体"保留并同时交付（`scores_0_6_P1.csv`）。
四套口径表全部保留（P1/P2/P3/P4），不删任何一套。

**理由与边界（防止被误读为挑分数）**：
1. 变更的驱动是**题面的 0–6 要求**，不是 QWK 更高；P2 的 QWK 仅作口径敏感性，**不是准确率**。
2. 真实 0–6 等级未知（4.csv 非单位方差、location/scale 不可辨识），所以任何口径都不能宣称"正确"，
   只能宣称"满足量程要求且可追溯"。
3. 该决定在**看到任何新模型结果之前**提出（由 modeler-q1 报告 P1 分布后立即处置），并同时保留
   P1 供复核；若下游认为应坚持物理锚定，改回只需切换引用文件，不涉及模型重跑。

## 7. 数字更正登记（modeler-q1 → Lead）

- **−2.66 → −0.9301 ± 1.1423（15 折）**：前者为 5 折单次试点、单折爆炸值，已从所有交付文档中撤换。
  逐维为负 **39/50**（15 折口径），不是"50/50 全负"。
- **崩溃机制更正**：主因是**混合尺度**（33 个线性列 1e-9~1e3 与 37 个 log10 列混做折内标准化），
  而不是"winsorize 本身"；尺度协调 / winsorize / 裁剪 ±8 三条路径几乎等价（0.1987 / 0.2002 / 0.1997）。
- 该更正已同步到 `REPRODUCE.md`、`delivery/STATUS.md` 与论文写作素材。
