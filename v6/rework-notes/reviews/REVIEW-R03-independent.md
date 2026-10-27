# REVIEW-R03 独立审查报告（MathorCup 2026 A / R00→R03 重跑）

- 审查者：`independent-reviewer`（与执行者不同上下文；只读项目，唯一写入 = 本文件）
- 审查对象目录：`P = /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`
- 审查时点：2026-10-26（台账 revision/时间以读取时刻为准）
- 方法：不采信执行者自述；所有数字要么从原始产物复算、要么在台账/验证记录里逐条对齐；无法复算的项列入 §5 `notChecked`。
- 我未调用任何 `modeling_*` 工具、未跑实验、未训练、未改任何项目文件。

---

## 0 结论速览

**verdict: `findings`**（存在 **2 条未解决的 critical**，因此不能记 passed；但 4 条核心结论的数字本身经我独立复算全部成立，故不记 rejected）

| 严重度 | 条数 | 一句话 |
|---|---|---|
| critical | 2 | ① 交付层（论文/渲染/图/冻结/打包/质量平面）整体停留在 R03 **之前**，渲染论文仍在用两个 v5.1 已判缺陷的数字；② `CLAIM-0026`(Q2) 把协议写成 3×3×3 嵌套 CV，实际是固定 200 行上的 bootstrap |
| major | 8 | Q2 零验证；Q3 "约束满足 1.000" 是投影+边界夹断；代理 R² 披露不实；验证计划晚于候选；"独立复跑"是同快照重放且目录缺失；质量/契约/评审平面未更新；题面口径与新工作冲突；Q3 不增率是构造保证 |
| minor | 10 | 数字小偏差、台账字段不一致、交付缺项、格式项无记录等 |

**模型层（数值证据）判定：可信。** 我把 4 条 claim 的 20 个 metric 引用全部解析到 `experiments/<ID>/metrics.json` 且数值逐字相等；把 Q1 的 A/F30 池化 MAE 从 `oof_long.csv` 重算、把 Q2 的 π 从 30 万行 bootstrap 明细重算、把 Q2 的名称对齐相关在 4 个维度上重算、把 Q3 生成与迁移的硬约束从 CSV 重算，全部与报告一致（见 §4）。

**交付层判定：不可交付。** 论文源 `report/paper.md` 的占位符仍绑定 `EXP-0001/0003/0004/0026/0029/0033`，最近一次 render 是 `RENDER-0009`（2026-10-24T14:37），31 张图 **0 张**来自 R03 实验，`delivery/` 最新包是 `20261024-223751`。

---

## 1 我实际做了什么复核（可复算清单）

在项目解释器下只读复算（不写任何文件）：

| # | 复核动作 | 结果 |
|---|---|---|
| R1 | 从 `experiments/EXP-0039/oof_long.csv`（150000 行 = 3×250×4 模型×50 目标）重算 A/F30 平铺 MAE | graph-lowrank 0.359291565882、graph-ridge 0.366411015783、ridge 0.366661758011、median 0.398177328373，与 `metrics.json` 在 12 位小数上完全一致 |
| R2 | 把 `oof_long.csv` 的 (beer,repeat,fold) 与 `data/splits/NESTED-CV-1/splits.csv` 的 `outer_test` 集合比对 | 750/750 全部命中，0 条多、0 条少 |
| R3 | `predictions.csv` 与 `oof_long.csv`(graph-lowrank) 比 | 750×50 最大绝对差 **0.0** |
| R4 | 拆分清单结构自检 | 2250 行；每 repeat 250 瓶各出现一次 outer_test；inner 折精确划分 outer-train；**任意两个 outer test 集合互不相同**（不是"旋转重复"）；22 个风格逐 repeat 分折计数一致 |
| R5 | 从 `experiments/EXP-0041/repeat0/bootstrap_pi.csv`（300000 行）重算 π | acetaldehyde 0.636、methylpyrazine 0.604、X2.acetylpyrrole 0.288，与交付表/输出一致 |
| R6 | 从 6.csv(44×50) + `candidate_scores.csv` 重算名称对齐后的 Spearman | A_malt_all 0.967865、body 0.987597、overall 0.950529、co2 0.980973，与 `outputs.external_6csv.perDimension` **6 位小数一致**（含旧版错位的尾部三列） |
| R7 | 从 `EXP-0042/samples.csv`、`samples_raw.csv` 重算 33 个"线性已校准列"负值与 3 个缺陷阈值 | 设计谱负值 **0**；DMS/双乙酰/4VG 超阈 **0/0/0**（最大值恰等于阈值）；原始谱负值 **0**，但超阈 **508/361/46**（DMS 最大 520.45 µg/L = 30× 阈值，双乙酰 121.73 vs 0.29925） |
| R8 | 统计 q3_metrics.csv 的 198 格 | 22 风格 × 9 折 = 198；`n_real==1` 恰 **21** 格，这些格 E_V_norm 为 NaN——与 claim "21/198 格不可估" 一致 |
| R9 | 从 `EXP-0043/transfers.csv`(396×738) 重算不增率与物理单调性 | qp-quantile-anchor 99 行：DMS/双乙酰/4VG/nonenal 不增率各 1.000，`max(new-source)` = 0/1.1e-16/0/0；target-mean-projection 99 行中 **58 行 feasible=False** |
| R10 | 解析 `solver_certificates.jsonl`(198) | status 全 optimal；primal ≤ 9.99e-9、dual ≤ 3.39e-10、constraint violation 全 0、KKT ≤ 5.62e-9、198 个 problem_hash 互不相同 |
| R11 | 4 条 claim 的 20 个 metric 引用逐条解析 | 文件存在、键存在、数值与 claim 相等、实验 status=succeeded（全部命中） |
| R12 | 代码/数据哈希一致性 | `src/q1_fix.py` 2fb4b4b0…、`src/q2_fix.py` fd010c4f…、`src/q3_fix.py` ae599242…、`src/q3_transfer_fix.py` 525d6494… 与各自 experiment.json `code.sha256` **完全一致**；`contest.yaml` sha256 = 728811fc… = config v2；`splits.csv` sha256 = 8ad8e75d… = manifest 记录 |

---

## 2 v5.1 必改项逐条核验

### 2.1 第一问（对照 / OOF / 口径）

| 必改项 | 判定 | 证据 |
|---|---|---|
| 真普通 Ridge（γ=0）对照 | **已修** | `src/q1_fix.py:296-410` 的 `inner_select` 里 `ridge_keys = [k for k in full_rank_keys if k[2]==0.0]`；外层再断言 `if float(gamma)!=0.0: raise`（`q1_fix.py:610`）。run.json/experiment.json 记录 `- -repeat all` 实跑 |
| 图 Ridge / 图低秩第三类对照 | **已修** | 三族各自独立调参：ridge 6 格、graph-ridge 12 格、graph-lowrank 54 格（`inner_grid.json` 的 `nCells`） |
| 逐行 OOF（预测该行的模型未见该行） | **已修** | 结构上：`q1_fix.py:296/333` 内层只用 `outer_train_beers`；`:511-700` 外层用 `v6.iter_outer`，预处理/图/中位数全部在 `train_frame` 上拟合；R1+R2 实测 750 行 OOF 与冻结折一致 |
| 旧 250 行"OOF"混入训练内预测 | **已修** | 旧路径 `src/q1_grade_all.py` 被明确弃用（`q1_fix.py` 文件头注释；outputs.json `fixes.trueOOF`） |
| 主报 A/F30 连续标签 MAE、同时 50 维/两组/逐风格 | **部分** | A/F30 与 all50、Aroma15/Flavour15、22 风格齐全（22 风格 ×(mae,n) 共 44 个 per_style 键）；**但"逐维 MAE/R²/Skill 表"与"改善/恶化维数"没有作为指标输出**（metrics 110 个键中没有 per-target 键；`outputs.models.*.pooled` 只有组级）。可从 `oof_long.csv` 重算，但交付表缺失 |
| 披露 z-score 截断 ±8 | **已修** | `src/q1_fix.py:101` `Z_CLIP = 8.0`，`Preprocessor.design` 中 `np.clip(..., -Z_CLIP, Z_CLIP)` |
| `Skill = 1 − MAE/MAE_baseline`、基线自身 0 | **已修** | `q1_fix.py:683-685`，`skill_af30` 输出 0.0976594 |
| 0–6 保留但声明为相对等级 | **已修** | 分级用外层训练经验 CDF（`q1_fix.py` grade 段）；`oof_long.csv` 有 `grade_pred/grade_true`；outputs `grade.note` 明示"not an accuracy claim about the panel's original 0-6 score" |
| 评分卡与可用标签对应表 | **未做/未见** | 未找到 3.xlsx 40 维 → 50 标签的对应表产物；`analysis/sensory/targetcolumns.csv` 是**化学列**字典，不是评分卡映射 |
| 融合成绩不冒充测试成绩 | **已修** | 融合/HGB 明确列在 `excluded`（"not_run"，理由写明旧融合是 in-sample 混用来源） |

**Q1 一处需要说明的技术点**：ridge 的内层最优 λ 在 9/9 折都落在网格上界 10.0（`inner_grid.json` 的 `lambdaAtGridEdge=true`）。按常理这会让"候选 vs 普通 Ridge"的对照偏向候选。但 `outputs.json:devNotes` 记录了一次**未登记为实验**的加宽探针（λ=1→0.3763、10→0.3701、30→0.3848、100→0.4000、300→0.4077），说明 10 是内部最优。该探针无法从台账复核（见 §5），属于"结论依赖不可核验的旁证"。

### 2.2 第二问（名称对齐 / 类别 / 严格vs扩展 / 稳定性）

| 必改项 | 判定 | 证据 |
|---|---|---|
| 按名称双向对齐（不再按位置） | **已修** | `src/q2_fix.py:487-530` 用显式字典 `sensory_name_alignment.csv` + 6.csv 表头集合双重校验；R6 我在 4 个维度上重算，含旧版错位的 aftertaste/body/co2/overall 三个尾部列，全部吻合 |
| 二次索引（219 行矩阵用 231 空间下标） | **已修** | `q2_fix.py:332 _guard_matrix` 强制 (231,50)；`:18` 注释写明只允许 `FEATURE_COLS.index(name)`；`:626/633/843` 每张分数矩阵都过 guard |
| 感官尾部三列错位 | **已修** | 对齐表 50 行一对一（`external_header→target`）；`outputs.mapping.chemistry` 44/44 matched、0 unmatched、0 ambiguous；旧错位 0.445051 由 R00 审计与 EXP-0041 两条记录分别复现 |
| 候选类别字典 | **已修** | `q2_fix.py:368-419` 断言四类恰好划分 231：single_compound 216 / element_or_index 3 / physical_parameter 7 / derived_sum 5 |
| 严格榜与扩展榜分表 | **已修** | `strict_top3.csv`(150 行, 12 列) + `strict_top3_by_method.csv`(600) + `extended_top3*.csv`；strict 只含 single_compound |
| 符号一致性与替代候选 | **已修** | 12 列含 `sign_stability / direction / module_id / alternative_rank4 / evidence_status`；`sets.json` 与 `module_alternatives` 给出模块内 4–10 名替代池 |
| 稳定性如实说明（91/150 旧数 → 新版 1263/1800） | **已修（记录）/未达验收** | `CLAIM-0026` limitations 明写"不能写成关键化合物已确定"；但 **没有"可核对的化学解释"列**（v5.1 §四验收要求），`strict_top3.csv` 12 列中无化学依据或"待证"标记 |
| 6.csv 不得称独立外部验证 | **claim 已改，题面记录未改** | `CLAIM-0026.limitations[1]` 与 `outputs.external_6csv.status` 均写明"同源、非独立"；但 **`state/ledger.json` 的 Q2 `evaluation` 仍写"与 6.csv 独立 \|r\| 的秩相关"**，且渲染论文仍在用 0.445051（见 C1） |

### 2.3 第三问生成

| 必改项 | 判定 | 证据 |
|---|---|---|
| 非负实际浓度作为硬约束 | **已修** | 只对 33 个 LINEAR_CALIBRATED 列做非负（notes D1）；R7 从 `samples.csv` 重算 33 列负值 = **0** |
| raw / design 分离并报告调整幅度 | **已修** | `samples_raw.csv` 与 `samples.csv` 均在；`outputs.raw_design_change` 给 `mean_abs_change_std_all_columns=0.01418` 与 top 变化列（DMS 0.573 最大） |
| t2n 化学浓度不增（而非感官代理下降） | **已修（迁移）/生成侧不适用** | 迁移见 §2.4；生成侧 notes D4 明示"t2n 不再是约束，由化学 nonenal 承担"；`constraints.csv` 中 nonenal 750 条全为 conditional（有界不增），不是"已低于阈值" |
| 每列存储尺度/单位/有效范围/缺失状态 | **已修（并诚实标 not_declared）** | `outputs.column_state` 231 条，含 tier/storage/observed min-max/physical_range/n_missing/n_floor/floor_code/branch_state；单位"not_declared"照实写 |
| PCA 中心化修复 | **已修** | `EXP-0043/outputs.target_mean_assertion`：fixed 4.749e-16 / 2.5e-16 量级（逐折列出），legacy 0.6655，并**同时列出** `oldValueFromIndependentRecheck=0.6044870518234862`（两个旧值都已说明来源，不是互相矛盾） |
| 目标/梯度一致 | **已修** | `objective_gradient_check` 231 维有限差分 max_abs 8.8e-10 / 6.9e-10；另有 198 份 QP 证书 `kkt_stationarity_residual ≤ 5.62e-9` |
| 逐外折独立内层调参 | **已修** | `outputs.per_fold_tuning` 逐 (repeat,fold) 给 9 格网格与 3 个 inner 表，规则写明"no cross-fold pooling"；选中 (κ,κ_R) 随折变化（如 r0f0=5/50、r0f1=5/100） |
| 经验 V / 未截零 U | **已修** | V=0.8840256、U=+1.1138668（不截零）；`src/q3_fix.py:419` 的 `energy_statistics` 定义与 `outputs/contract_tests` 的二维玩具 V=0/U=−1 一致 |
| 重采样 / 独立边际 / Copula 三参照 | **已修** | `outputs.comparisons` 五路：copula-selected / shared-only / style-empirical / independent-marginals / source-resample |
| 多样性 / 最近邻 / 复制率 | **已修** | diversity 19.7356、nearest-neighbor 17.6323、duplicate-share 0.0（三次重复分别 19.688/19.610/19.910） |
| 导出后重读 CSV 再检查一次 | **已修** | `src/q3_fix.py:1064-1080` 从写出的 `samples.csv` 重建 row_ok，并与内存值比较，>1e-9 即抛错 |
| 报告不可核验项 | **已修** | constraints.csv 28500 条 = verified 19619 / conditional 8201 / not_identifiable 680 / infeasible 0，字段/样本级 |

### 2.4 第三问迁移

| 必改项 | 判定 | 证据 |
|---|---|---|
| 凸 QP 主策略 + 可行性/最优性残差/状态 | **已修** | 198/198 optimal，primal/dual/violation/KKT 全部记录（R10）；`qp-status-infeasible=0`、`qp-status-not-converged=0` |
| 不可行显式报告、回退记"未完成迁移" | **已修** | 主策略 fallback-share 全 0；对照 target-mean-projection 有 58/99 infeasible 且照实记录 |
| 四个化学列同单位不增（含 DMS/双乙酰/4VG/nonenal） | **已修** | R9：`max(new_source)=0`（双乙酰 1.1e-16 浮点级） |
| t2n 用化学列而非感官代理 | **已修** | `CLAIM-0025` 明写；`transfers.csv` 里 `X.E..2.nonenal_nonincreasing` 逐行可查 |
| 缺失/地板/报告零值不冒充实测 | **已修** | stale hops 与 nonenal 的源状态在 constraints/transfers 中区分；claim limitations 明写"记 conditional/not_identifiable，不记物理通过" |
| 至少比较"源点不变"与"目标均值投影" | **已修** | 四策略并列：qp-quantile / qp-source / source-fixed / target-mean-projection |
| 迁移前后逐行对照 | **已修** | `transfers.csv` 396×738，含 `src__*` / `opt__*` / `ref__*` 三套 231 列 + 每策略指标 |

### 2.5 数据口径、复现、文档

| 必改项 | 判定 | 证据 |
|---|---|---|
| 80 个线性数值冲突清单、不静默覆盖 | **已修** | `outputs/audit/v6/conflicts_strict.csv`(80 格/24 瓶/32 列，全部在 linear 层) + `calibration_conflict_summary.json` + `conflicts_substantive.csv` |
| 状态字典（零/地板/缺失）可复算 | **已修** | `state_counts.json`：calibratedZero 755、floorColumns 142、floorCells 6807、missing 73/9 列/63 行，逐项 `matches: true` 对比登记值 |
| 旧缺陷数字独立复算 | **已修** | `legacy_recheck.json` 复算 142 格/40 行/22 列、t2n 6/11、0.445051/0.921018、自距 0.6045、U=−0.3196，全部带输入 sha256 |
| 冻结切分清单可追溯 | **部分** | `data/splits/NESTED-CV-1/{splits.csv,manifest.json}` 自洽、sha 与 manifest 一致；但该切分**未登记进台账 `splits`**（台账只有 SPLIT-0001/0002），且 R03 实验 `splitId` 全为 null——"冻结清单"只在实验依赖哈希里体现 |
| 干净目录可运行 | **部分** | EXP-0053/54/55 确实从 `experiments/EXP-00xx/inputs/` 快照（code+data+splits+originalPath）跑通并有 `sourceSnapshot`；但 **Q2 两次快照尝试都失败**（EXP-0049 FileNotFound、EXP-0052 非 ASCII 路径 PermissionError），整包"从零重建"未验证 |
| 论文格式（无页眉、正文页码从 1） | **未做且未声明** | 全项目无完成记录、也无"明确未做"的说明；`report/revised-20261025/修改说明.md` 未提及页眉/页码；`.rework/evidence/pdf-audit/` 只审"墨迹越界/字形"，不审页眉页码 |

---

## 3 协议诚实性（3×3×3 是否真按冻结清单执行）

**结论：Q1 与 Q3 真按冻结清单执行；Q2 没有执行嵌套 CV，而 claim 写成了嵌套 CV。**

| 检查点 | 判定 | 证据 |
|---|---|---|
| 3 repeat × 3 outer × 3 inner、seed 20261025-27 | **真** | `src/r00_build_splits.py:55-80`：`rng_outer = default_rng(SEEDS[repeat])`、`rng_inner = default_rng([seed,fold])`；`contest.yaml:19` 与 `manifest.json` 一致；config v2 于 **2026-10-26T07:44:30** 接受（早于首个 R03 实验 07:55:57） |
| 训练/测试不交 | **真** | `r00_build_splits.py:100-120` 的四条不变量（外层交、并、内层划分、非空）+ 我 R4 的独立重算 |
| 内层只在外层训练集内 | **真** | `v6_common.py:182` 的 `iter_inner(repeat, outer_fold, outer_train_beers)`；`q1_fix.py:303` 只用传入的 outer-train 瓶 |
| 分层按 tasting_category_fine、小风格不复制 | **真** | 22 风格逐折计数；Faro n=3 在 outer-train 只有 2 行，manifest 明写"some inner folds hold 0 rows of that style; this is recorded, not padded" |
| 种子来源可追溯 | **真** | seeds 来自 config；每实验 `experiment.json.seed`、`run-seed-<seed>.json`（Q3）可对 |
| 有无用 outer_test 拟合/调参/校准的痕迹 | **未发现** | `q1_fix.py` 的 `Preprocessor`/`graph_laplacian`/`inner_select`/中位数全部只吃训练行；`q3_fix.py` 的 style 统计在 outer-train 上重算；泄漏检查 VAL-0044/0051 只对单目标做 |r| 过滤，属窄检查，但 `EXP-0039.params.features` 实测 231 个全为 `chem__*`（无目标列/无 g6 列），结构上无标签泄漏 |
| `mae` 是否真是 A/F30 池化（非 50 维、非训练内混用） | **真** | `q1_fix.py:897` 定义 + R1 的独立重算（0.359291565882 恰好等于 750×30 平铺） |
| OOF 是否"该样本拟合时未见" | **真（Q1）** | R2：750 行 OOF 的 fold 归属与冻结 outer_test 完全一致；每瓶每 repeat 只被预测一次（`duplicated((model,repeat,beer,target))=0`） |
| Q2 的"3×3×3 嵌套 CV" | **假** | `src/q2_fix.py:180` `TRAIN_CSV = .../SPLIT-0001/train.csv  # 200 registered train rows (Q2's only rows)`；`:353` 断言 len==200；`:681` 的 loop 是 `for replicate in range(reps)` 的分层 bootstrap；`repeats` 只是 `SEEDS[repeat]` 作为 bootstrap 种子。**没有 outer/inner 折，没有 OOF，50 行留出瓶从未进入 Q2 任何计算** |

---

## 4 结论—证据一致性抽查

### 4.1 数字对账（我复算 vs claim/metrics）

| claim | 陈述数字 | 我的实测 | 一致 |
|---|---|---|---|
| CLAIM-0023 | 0.359292 / 0.366662 / 0.366411 / 0.398177 / Skill 0.097659 | 0.359291565882 / 0.366661758011 / 0.366411015783 / 0.398177328373 / 0.0976594（从 OOF 重算） | ✅ |
| CLAIM-0023 | 等价性 4.0e-15 | `eq_ridge_rank50_max_abs_diff=3.9968e-15`，逐折 1.998e-15… | ✅ |
| CLAIM-0023 | 增益来自低秩 −0.007371（≈2.0%） | 0.359292−0.366662=−0.007370；2.01% | ✅ |
| CLAIM-0023 | "选中 r=6" | 9/9 折 r=6 | ✅ |
| CLAIM-0023 | 内层 margin 1e-4~6e-4 | lowrank 9.3e-5~6.02e-4；graph-ridge 最大 1.09e-3 | ✅（低秩范围内） |
| CLAIM-0024 | 1.000 / 0.1133 / 0 负格 / V 0.8840 / U +1.1139 / 多样性 19.736 / 复制 0 | metrics 逐字相等；R7 独立确认 0 负格与 0 超阈；R8 确认 21/198 | ✅ |
| CLAIM-0024 | 重采样参照 0.8137 | `comparisons["source-resample"].design.energy-distance=0.8137313` | ✅ |
| CLAIM-0024 | verified 19619 / conditional 8201 / not_identifiable 680 / infeasible 0，最大残差 0.0 | constraints.csv 分组计数完全一致；`max residual = 0.0` | ✅ |
| CLAIM-0024 | t2n 代理上升 360/750（48%） | `t2n-increases=360` | ✅ |
| CLAIM-0025 | 不增率 1.000、四列各 1.000 | R9 逐列重算 99/99 | ✅ |
| CLAIM-0025 | 目标均值自距 4.75e-16（旧 0.6655） | metrics 一致；`outputs.target_mean_assertion` 同时登记 0.6655 与独立复核 0.6045（两个旧值都有出处） | ✅ |
| CLAIM-0025 | 198/198 optimal、9.99e-9、3.39e-10、违反 0、KKT 5.6e-9 | R10 全部一致 | ✅ |
| CLAIM-0025 | V 0.1236 / 2.261、源点不变 7.196、均值投影 6.941、U −0.148 | metrics 一致 | ✅ |
| CLAIM-0025 | 均值投影 0.414（58 条不可行） | R9：99 行中 58 行 feasible=False，nonincrease 0.414141 | ✅ |
| CLAIM-0026 | 0.20911（0.21033/0.20733/0.20967）、跨重复 0.87483 | metrics 一致；三 rep 均值 = 0.209111 | ✅ |
| CLAIM-0026 | 0.445051→0.921018（44 行；严格 0.90802） | metrics 一致；R6 四维重算吻合 | ✅ |
| CLAIM-0026 | 216 项 / 15 项扩展 | `categories` 断言 216+3+7+5=231 | ✅ |
| CLAIM-0026 | 1263/1800 个 π<0.5、平均 π 0.4205、符号一致性 0.7226 | 逐 rep 423+419+421=1263 / 600×3；均值 0.420457 | ✅ |

### 4.2 limitations 是否覆盖真实弱点

| 弱点 | 是否在 limitations | 备注 |
|---|---|---|
| Q1 折间波动 > 模型间差距 | ✅ 有 | 但区间写成 "0.345–0.379"，实测逐折 0.34499–0.37313（minor） |
| Q1 旧 0.346567 不可与新版相减 | ✅ 有 | — |
| Q2 1263/1800 π<0.5、第三名不稳 | ✅ 有 | 明确写"不能写成关键化合物已确定" |
| Q2 6.csv 同源非独立 | ✅ 有 | 但题面 evaluation 与渲染论文仍写"独立"（major） |
| Q3 能量 V 0.8840 劣于重采样 0.8137 | ✅ 有 | 明写"本轮不宣称 Copula 优于简单参照" |
| Q3 21/198 格不可估 | ✅ 有 | — |
| Q3 t2n 代理 48% 上升 | ✅ 有 | — |
| Q3 约束满足是投影构造 + **夹断质量** | ❌ 无 | 67.7% 行恰压在 DMS 阈值、48.1% 恰压在双乙酰阈值（我重算）；claim 未披露 |
| Q3 感官代理对 t2n/stale_hops 的实际 R² | ❌ 不实 | claim 写"CV R²≈0.18"（那是 A/F30 全局），实际 `proxyCvR2: t2n=0.0099, stale_hops=0.0350` |
| Q3 迁移不增率是 QP 约束保证 | 部分 | 只写"设计诊断，不是迁移准确率"，未写"由约束构造保证"；且未披露 t2n 感官代理在 QP 主策略仍有 7/99 上升 |
| Q2 协议不是嵌套 CV | ❌ 无（反而写错） | 见 critical C2 |

---

## 5 未完成 / 不可核验清单（真实缺口 vs 记账口径）

| # | 项目 | 真实缺口？ | 依据 |
|---|---|---|---|
| 1 | 独立复跑 | **部分真实缺口** | Q1(EXP-0053)、Q3 生成(EXP-0054)、Q3 迁移(EXP-0055) 只有"同快照+同种子"的逐字节重放（`VAL-0048/49/50` delta=0，`mode=fixed-seed-reproduction`）——只能证明确定性，不能发现系统性 bug，也不能称为独立实现；**Q2 完全没有**（EXP-0049 FileNotFound、EXP-0052 非 ASCII 路径 PermissionError） |
| 2 | 稳健性（multiple-seeds/param-perturbation） | **真实缺口** | `ROB-0001/2/3` 全部 status=pending，绑定的仍是旧实验 EXP-0016..0024（seed 20261024/20261025、旧指标键）；新 claim 无 `appliesToPlanId`；`CLAIM-0012` 因此被撤回（撤回理由自述"这是当前明确缺口"）。config `robustness.required=true` |
| 3 | 干净目录复现 | **部分真实缺口** | Q1/Q3 有 `inputs/` 快照（含 data+splits+code+originalPath，`sourceSnapshot` 记录齐）；Q2 无；没有一份"空目录 + 安装依赖 + 一条命令"的端到端记录 |
| 4 | run-control begin | **记账口径（但门禁会读）** | `quality.runControl = {activeRunId:null, runs:[], events:[]}`，`counters.RUN=0`，QC-0028..0032 全 not_applicable。本次重跑未纳入 run 预算/审批治理——不是科学缺陷，但 `quality.required=true` 下不能当作"已通过治理" |
| 5 | quality plan/run | **真实缺口** | 32 条 QC **全部 stale=true**，时间 2026-10-24T14:36（早于 R03 全部实验）；27 passed/5 n/a 是 v1 的读数，不能给 R03 背书 |
| 6 | 门禁 holdout-metrics 与 train-only 嵌套 CV 的冲突 | **真实冲突，已被诚实记录** | 3 次 SPLIT-0002 曝光是**真实使用**（EXP-0001 metrics 记 `n_holdout_rows=50`；EXP-0003/0004 的 `splitId=SPLIT-0002` 且 `mae` 即留出值，EXP-0004=0.346567），`quality.robustness.maxHoldoutReuse=3` 已满；VP-0004 因此删掉 holdout-metrics，选择只能记 provisional。工具侧是否仍硬性要求 holdout-metrics 我**无法核验**（实现位于 app.asar，不可读，见 notChecked）。这条不是造假，但意味着"final"不可能达成 |
| 7 | forkOrigin 哈希不可复验 | **真实不可核验（影响很小）** | 台账记 `ledgerSha256=3dd298cc…`@rev 2790；当前 v3 台账实际 sha256 = `07e15fcd…`（源在 fork 之后继续演化），P 内没有 rev 2790 的快照，故 fork 点无法复验 |
| 8 | 验证计划先于比较 | **真实缺口（Q1/Q3）** | `VP-0004.registeredAt = 2026-10-26T08:04:51`，而 EXP-0039 于 07:56:27 开跑；`VP-0008` 等更晚。可辩护的一层是 **config v2 于 07:44:30 已冻结协议文本**，所以"协议先于比较"在 config 层成立，在**台账计划层不成立**；但 VP-0004 的 protocolNote 自称"本计划在比较候选之前登记"，与自身时间戳矛盾 |
| 9 | 验证记录落盘 | **记账口径/可读性问题** | `VAL-0048/0049/0050` 在 `validation/` 下**没有目录**（无 spec.json/result.json），只有台账内联记录；而它们是 CLAIM-0023/24/25 的 validationIds。读者无法从磁盘复核这三条 |
| 10 | 实验残留 | **记账口径** | EXP-0045/0046/0047 长期 status=queued、无 result；EXP-0040(DEPENDENCY_CHANGED)/0044(FileNotFound)/0049/0052 失败均如实保留、未静默重跑 ✅ |

---

## 6 风险与反对意见（分级）

### critical

**C1｜交付物整体停留在 R03 之前，渲染论文仍在用两个已被 v5.1 判为缺陷的数字。**
- `report/paper.md:9,11,13,15` 的占位符绑定 `EXP-0001/0003/0004/0026/0029/0033`（全是 v1 实验）；`report/paper.md:88` 仍写"训练内 5 折 CV"。
- `report/rendered.md:9` 与 `:118`、`report/paper.tex:137/427/989` 仍写 **0.3465674099243312**（旧 SPLIT-0002 留出、50 维口径）；`report/rendered.md:184` 仍写"与 6.csv 的**独立** |r| … 50 维秩相关均值为 **0.44505144467935176**"——这正是 v5.1 §四.2 明令改正的两处（错位口径 + 把同源当独立）。
- 最近渲染 `RENDER-0009` = 2026-10-24T14:37；31 张图 **0 张**来自 R03（全部 EXP-0003..EXP-0035）；`delivery/20261024-223751` 为旧包；`frozen` 仍是 `configVersion:1, revision:2731`，其 `claimIds` 列的是已 retracted 的 CLAIM-0012/0014/0018/0019/0021/0022（`state/ledger.json:407-490`）。
- 后果：若现在打包，交付物与台账互相矛盾——论文报告的是被撤回结论的数字，且含已确认的错位值。这是**阻断级**问题，不是文字瑕疵。

**C2｜`CLAIM-0026`(Q2, critical) 把协议写成"3×3×3 嵌套内部交叉验证"，实际是固定 200 行上的 bootstrap。**
- 实际：`src/q2_fix.py:180` 只读 `SPLIT-0001/train.csv` 的 200 行（`:353` 断言），`repeats` 只是 `SEEDS[repeat]` 当作 `np.random.default_rng(seed+1000003*21)` 的 bootstrap 种子（`q2_fix.py:688`），500 次分层重采样（`:681-720`）。**没有 outer/inner 折、没有 OOF、没有"每折训练"**；250 瓶中 50 瓶从未进入 Q2 任何计算。
- 但 claim 的 statement（`state/ledger.json:78696` 起）与 `appliesTo`（"50 个感官维度 × 216 个严格单一化合物候选（内部嵌套 CV，三次重复）"）都写嵌套 CV。
- 后果：这是把**较弱的重采样稳定性分析**表述成**更强的嵌套重验证**，方向上属于"高估验证强度"。数字本身没错（§4 已核），错的是协议标签；但该标签会原样进论文方法节与摘要。

### major

**M1｜Q2 完全没有验证，却是 critical/active claim。** `CLAIM-0026.validationIds=[]`；EXP-0041 无 leakage、无 baseline-compare、无 independent-rerun；Q2 选择理由自述"本轮缺 leakage 与独立复跑"——诚实，但意味着这条 critical 结论没有任何机器/独立检查背书。

**M2｜Q3 "constraint-satisfaction = 1.000" 是投影构造不变量 + 大比例边界夹断。** 我从 `samples.csv` 重算：设计谱 750 行中 **508 行（67.7%）DMS 恰好等于 17.25 阈值、361 行（48.1%）双乙酰恰好等于 0.29925、46 行（6.1%）4VG 恰好等于阈值**；原始谱超阈 508/361/46（DMS 最大 520.45 µg/L）。也就是说"满足率 1.000"等价于"把 2/3 的样本压到阈值上"，而 claim 既未披露夹断质量、也未声明该 1.000 由 `q3_fix.py:350-370` 的投影循环保证（`max residual ≤ 1e-9` 才停）。可辩护的部分是它确实从写出的 CSV 复核（`:1064-1080`），raw 0.1133 的对照也真实；不可辩护的是把它当作"质量指标"呈现。

**M3｜代理 R² 披露不实（Q3）。** `CLAIM-0024.limitations[2]` 写"感官画像由弱 Ridge 代理给出（CV R²≈0.18）"；`EXP-0042/outputs.profile_predictor_validation[*].proxyCvR2` 实测 **t2n = 0.0099、stale_hops = 0.0350**。0.18 是 A/F30 全局宏 R²，不是承载缺陷结论的那两列的 R²。按该代理说话（如"t2n 代理下降"）时，其可用信息近乎为零。

**M4｜Q1 验证计划晚于候选实验，且 protocolNote 自述与时间戳矛盾。** `VP-0004.registeredAt=2026-10-26T08:04:51`（`state/ledger.json:55777`）vs `EXP-0039.startedAt=2026-10-26T07:56:27`。计划文本写"本计划在比较候选之前登记"。唯一成立的预注册是 config v2（07:44:30）。若审查者只读 VP-0004，会得到相反印象。

**M5｜三条"独立复跑"是同快照逐字节重放，且磁盘上没有验证目录。** `VAL-0048/49/50` 的 `result.details.mode="fixed-seed-reproduction"`、`seeds=[20261025]`（与原实验同种子）、`delta=0`；EXP-0053 的 run.json 显示它跑的是 `experiments/EXP-0048/inputs/src/q1_fix.py`（与原实验同一文件）。这只能证明"确定性"，不能证明"独立"。同时 `validation/VAL-0048|0049|0050` 目录不存在，只有台账内联记录——而它们被用作 CLAIM-0023/24/25 的证据 id。

**M6｜质量/契约/评审/稳健性平面整体未随 R03 更新。** 32/32 QC 全 stale（2026-10-24T14:36）；`REQ-0001/0002/0003/0004/0007` 的 `coverage.kind="covered"` 所引 claim 全部是**已 retracted** 的 CLAIM-0018/0019/0021/0022（其余 refs 也是 EXP-0004/0026、FIG-0020 等旧证据）；没有任何 review 覆盖 CLAIM-0023..0026（最新 REV-0039 审的是旧 delivery/paper）；`MCON-0001..0003` 的 `modelId=null`、与新模型未绑定；`TGT-0001.labelSource` 仍在描述 EXP-0026 的 in-sample/留出分级。在 `quality.required=true, review.required=true` 下，这些门禁无法合法通过。

**M7｜题面/口径记录与新工作冲突。** Q1 `evaluation` 仍要求"候选必须在同一 SPLIT-0002 上可比"且"50 维等权平均**留出** MAE 为主"，而 R03 实验 `splitId=null`、主指标是 A/F30 OOF；Q2 `evaluation` 仍写"与 6.csv **独立** |r|"。题面记录是验收口径的来源，不更新就会让"覆盖/验收"永远对不上。

**M8｜Q3 迁移的 1.000 是求解器保证，措辞容易被读成经验可行率。** QP 的约束里就含 `c_new ≤ c_source`，198/198 optimal 自然给出 1.000；真正有信息量的是"对照 target-mean-projection 58/99 不可行"。claim 的 limitations 只说"不增率是设计诊断"，未说"由约束构造保证"。旧 CLAIM-0022 恰恰因"策略相对非恶化率 1.0 是构造产物"被撤回，同型表达又在 CLAIM-0025 出现。另外主策略下 t2n **感官代理仍上升 7/99**，未披露。

### minor

- **m1** CLAIM-0023 limitations "候选逐折 0.345–0.379"：实测 0.34499–0.37313（上界不对）。
- **m2** `state/ledger.json:7` 的 `configSha256 = 2ce0b2c3…`（config v1）≠ 当前 `contest.yaml` = `728811fc…`；claims/configLifecycle 用的是 728811。字段语义未在台账里说明，属易误读的不一致。
- **m3** Q1 交付缺"逐维 MAE/R²/Skill"表与"改善/恶化维数"；`metrics.json` 110 键里没有 per-target 键（只能从 `oof_long.csv` 重算）。
- **m4** Q1 缺"3.xlsx 评分卡 → 50 标签"对应表（v5.1 §五验收项）。
- **m5** Q2 交付的 12 列里没有"化学解释/待证"字段（v5.1 §四验收要求"可核对的化学解释"）。
- **m6** `EXP-0039/outputs.json` 的 `definition.predictionsCsv` 写"250 rows per repeat"，实际 `predictions.csv` 为 750 行（含 repeat 列）。
- **m7** `EXP-0045/0046/0047` 长期 queued、无结果，属残留排队记录（未清理也未标失败）。
- **m8** v5.1 §二 论文格式必改（去页眉/正文页码从 1）在本项目**既无完成记录也无"明确未做"声明**；`report/revised-20261025/修改说明.md` 未提；`pdf-audit` 只查墨迹/字形。
- **m9** `forkOrigin.ledgerSha256` 与当前 v3 台账不符（07e15fcd…），且无 rev 2790 快照。
- **m10** Q3 生成只披露 t2n 代理上升 360/750，未披露 `t2n-above-style-bound=146/750`（另一条同族弱信号）。

### 需要明确否定的读法（这些说法在现有证据下**不成立**）

1. **不能**把 Q1/Q2/Q3 的模型选择说成 validated：三问 `selectionStatus` 都是 `provisional`；`frozen.selectedModels` 里的 `validated` 属于 config v1 的旧模型（MODEL-0004/0012/0013），不是本轮。
2. **不能**把 `constraint-satisfaction=1.0` 说成"物理正确/真实可行"：它是投影不变量，且 67.7%/48.1% 样本被夹在阈值边界；约束来源是"声明的均值感官阈值"和经验 q90，不是物理定律。
3. **不能**把 Q2 的低 π 说成"关键化合物已定"：1263/1800 项 π<0.5、平均 π 0.4205，第三名普遍不稳。
4. **不能**把 6.csv 说成独立外部验证：它同源、未参与选择；当前正确值 0.921018（严格 0.90802），论文里的 0.445051 是错位产物。
5. **不能**把生成谱的感官画像说成感官验证：代理对 t2n/stale_hops 的 CV R² 仅 0.0099/0.0350，`notes` 自己也说"never an independent sensory validation"。
6. **不能**把 VAL-0048/49/50 的"independent-rerun passed"当作独立实现复核：那是同快照同种子重放。

---

## 7 复审建议（阻断项优先）

1. **阻断**：在改完 C1 之前不要 freeze/advance/package。论文必须重新 render 到 `EXP-0038/0039`（Q1）、`EXP-0041`（Q2）、`EXP-0042/0043`（Q3），删除 0.346567 与 0.445051 两处"独立"表述，重做图。
2. **阻断**：改写 `CLAIM-0026` 的 statement/appliesTo（或在 `EXP-0041` 上补真正的嵌套 CV）——两者选一，但不能继续用"3×3×3 嵌套 CV"描述 bootstrap。
3. 给 Q2 补 leakage + 至少一次快照复跑（先修非 ASCII 快照路径），并把 `validation/VAL-0048/49/50` 的 spec/result 落盘。
4. 在 `CLAIM-0024` 增加披露：约束满足由投影保证、DMS 67.7%/双乙酰 48.1% 样本位于阈值边界；把代理 R² 改为按列（t2n 0.0099 / stale_hops 0.0350）报告。
5. 在 `CLAIM-0025` 增加"不增率由 QP 约束保证"和"t2n 感官代理 7/99 上升"两句。
6. 重跑 quality plan/run（自动派生 32 项），把 REQ 覆盖改指 CLAIM-0023..0026，撤销/更新 `frozen`（当前仍指向 retracted claims），并更新 Q1/Q2 的 `evaluation` 口径。
7. 交付前补：Q1 逐维表 + 改善/恶化维数 + 评分卡映射；Q2 化学解释列；论文格式项（页眉/页码）的完成证据或"明确未做"声明。

---

## 附录 A：本报告的关键证据位置

- 切分：`data/splits/NESTED-CV-1/splits.csv`、`manifest.json`（`splits_sha256=8ad8e75d…`、`n_rows=2250`）；生成器 `src/r00_build_splits.py`。
- Q1：`experiments/EXP-0039/{metrics.json,oof_long.csv,predictions.csv,inner_grid.json,outputs.json}`；`experiments/EXP-0038/metrics.json`；代码 `src/q1_fix.py`。
- Q2：`experiments/EXP-0041/{metrics.json,outputs.json,repeat0/bootstrap_pi.csv,strict_top3.csv,candidate_scores.csv}`；代码 `src/q2_fix.py`。
- Q3 生成：`experiments/EXP-0042/{metrics.json,outputs.json,q3_metrics.csv,constraints.csv,samples.csv,samples_raw.csv,run-seed-*.json}`；代码 `src/q3_fix.py`。
- Q3 迁移：`experiments/EXP-0043/{metrics.json,transfers.csv,solver_certificates.jsonl,outputs.json}`；代码 `src/q3_transfer_fix.py`。
- R00 审计：`outputs/audit/v6/{feature_dictionary,cell_provenance,conflicts_strict,conflicts_substantive,state_counts,legacy_recheck,calibration_conflict_summary}.json/csv`、`outputs/contracts/v6/contract_tests.json`、`data/processed/v6_constants.json`。
- 台账：`state/ledger.json`（claims 78499/78566/78632/78696；frozen 407；stage 396；VP-0004 55777；VAL-0048 72437、VAL-0049 74310、VAL-0050 75279）。
- 论文层：`report/paper.md:9-15,88`、`report/rendered.md:9,118,184,322`、`report/paper.tex:137,427,989`、`report/revised-20261025/修改说明.md`。
- 上游要求：`MathorCup_A_v5.1_面向复赛修改说明.md`、`MathorCup_A_独立审查与重跑方案/{03_插件重跑清单与提示词.md,independent_recheck.json,sensory_name_alignment.csv}`。

## 附录 B：明确的 notChecked（无法核验，不作为结论）

1. `modeling_*` 工具内部的门禁语义（是否硬性要求 holdout-metrics 才能 `validated`）：实现在 app.asar 内，不可读，只能依据 `selectionReason`/VP 记录推断。
2. `EXP-0039/outputs.json:devNotes` 的"λ 加宽探针"（λ=10 为内部最优）：无实验记录，复核需重训，被禁止。
3. 旧错位口径 0.445051 的**独立**复现：需要已 superseded 的 219 行代码路径，我未重建；仅确认两条记录（R00 审计、EXP-0041）互相一致。
4. `transfer-energy` 归一化分母 `D_ref` 的独立重算：需要核函数尺度定义，未复算。
5. t2n / stale_hops 的 Ridge 代理内部参数与预测：重算等于重新训练，被禁止；只核对了其 CV R² 输出。
6. PDF 页眉/页码的实际状态：R03 没有对应 PDF，`paper.pdf` 为 10-24 旧产物，我未在本次做页面几何实测。
7. forkOrigin 的源 rev 2790 台账快照：项目内不存在，无法复验哈希。
