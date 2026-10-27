# change_log.md — v6 复赛集中修正的逐项落实（2026-10-27）

基准：`MathorCup_A_v6_面向复赛修改说明.md`。本文件按该说明逐条写“已修 / 未修 / 剩余限制”，
并给涉及脚本与新实验 id。数字全部来自台账（`state/ledger.json`）与实验产物，不手抄。

## 1 第三问（Q3）

| # | 事项 | 状态 | 落点与证据 |
|---|---|---|---|
| 1 | stale 代理半空间扣除截距：`b = a'z_source + tol = f(z_source) − c + tol` | **已修** | `src/q3_transfer_fix.py`（proxy_linear_terms/build_problem/交付残差/投影/QP/证书同源）；`qp-max-stale-identity-error = 8.274037093680878e-17`、`qp-max-stale-halfspace-residual = 0`、`c ∈ [-0.1086, -0.0137]`（EXP-0110） |
| 2 | 原始 NA / 填补值 / floor 编码分离；四类 verdict | **已修** | `transfer_sources.csv`（396 行源状态）、`transfer_verdicts.csv`（760 行分层）；主策略 3762 条 = verified 3465（分母 3663）/ conditional 198 / not_identifiable 99 / failed 0；not_identifiable = 81 条 4VG 地板码 + 18 条 beer119/beer28 源双乙酰缺失（EXP-0110） |
| 3 | 经验边际改用未填补有效观测，统一四个入口 | **已修** | `src/q3_lib.py::StyleMarginals.fit(…, valid=…)`；`marginal_state.csv` 记录逐 (style,column) 的 n_valid/n_continuous/n_floor/omega；独立审查用 `data/clean/q3.csv` + splits 重建 5082 个单元，0 失配（REV-0088/独立复算） |
| 4 | 内层选参统一经验 V 口径 | **已修** | `src/q3_fix.py::select_hyperparameters_inner`；`tuning_table.csv`（243 行）记录每内折 V/D_train、有效格与样本数；U 只作带符号诊断 |
| 5 | 完整可行域均值投影基线 | **已修**（新增策略） | `target-mean-projection-full`：V=6.379240954520166、非增率=1.0；box-only 诊断 6.94148284204317 / 0.41414141414141414；QP 主策略 2.0798861351916886 / 1.0（EXP-0110） |
| 6 | 实体产物落盘 | **已修** | EXP-0109：`samples_raw.csv`、`samples.csv`、`samples_difference.csv`、`sensory_profiles.csv`、`tuning_table.csv`、`marginal_state.csv`、`verdict_layers.csv`、`energy_summary.csv`；EXP-0110：`transfers.csv`、`transfer_constraints.csv`、`solver_certificates.jsonl`、`transfer_sources.csv`、`transfer_verdicts.csv` |
| 7 | 198 个 QP 独立复算审计 | **已完成（audit，不是原生 VAL）** | `src/q3_cert_audit.py` → `SCRIPT-0023`；`outputs/q3/qp_cert_audit.json`（sha 32e1f9b5…，passed=true、hard_failures=[]） |

剩余限制：生成器仍未胜过同风格训练行重采样（0.8137313223527718）；Kriek 等小风格 V≈140；
感官 t2n 代理仍 366/750 增加（真实化学 trans-2-nonenal 0 条）；不增只在 1e-9 容差内成立（131/198 贴边）；
原生 optimization-feasibility/objective 仍不通过、不声明。

## 2 第二问（Q2）

| # | 事项 | 状态 | 证据 |
|---|---|---|---|
| 1 | `sign_stability` 改为与总体 Spearman 点估计同方向的一致率 | **已修** | `src/q2_fix.py`（`sign_buckets`/`point_direction_of`/`sign_fields`，零容差 `|ρ|≤1e-12`）；EXP-0107：`sign_stability_mean 0.9816877777777778`，旧口径 `sign_stability_legacy_mean 0.7225544444444444` |
| 2 | 旧值可复现 | **已验证** | 150/150 行 π 与旧 sign_stability 逐位相同（`legacyReproduction.passed=true`，EXP-0107 依赖 `EXP-0075/repeat{0,1,2}/strict_top3.csv`） |
| 3 | 正/负/零/无效计数与 95 条 π<0.5 逐项 | **已修** | `sign_counts.csv`（11550 行）、`strict_lowpi_sign_status.csv`（95 行）、`sign_stability_summary.json` |
| 4 | 附件 2 描述性网络实体产物 | **已完成** | `src/q2_att2_network.py` → `outputs/q2/attachment2_network/{nodes,edges,rules,component_summary,stats,network.png}`；231 节点/645 边/52 分量；`FIG-0045` |

## 3 第一问（Q1）

| # | 事项 | 状态 | 证据 |
|---|---|---|---|
| 1 | 保留 EXP-0073 / EXP-0074（不重训） | **已保留** | MAE 0.35929156588219174 / 0.39817732837288883 |
| 2 | 完整 250 酒评分矩阵、连续预测、0–6 相对等级、维度映射 | **已补** | `src/q1_export_scores.py` → `outputs/q1/{beer_scores_250,grades_250,oof_predictions_750,dimension_map,score_scale_note,export_manifest}` |
| 3 | 纠正“除以训练标准差”→ 中心化；低秩收缩归因；0–6 为训练分布内相对等级 | **已改** | `report/paper.md` 第 4 章；`outputs/q1/score_scale_note.json` |

## 4 论文与交付

- Q3 目标矩阵改为 `PᵀD⁻¹C⁻¹D⁻¹P`；V/U 对角项与分母写清；删除“以 U 正负判断偏移方向/过度分散”。
- 迁移拟合范围：目标参考与代理排除源风格，但源分位数边际使用训练源样本（已写明）。
- 校准附件与主输入 80 格线性值冲突已披露（16613 可比格 / 80 冲突 / 79 实质性 / 24 酒 / 32 字段；主输入规则）。
- 图件 10 张全部重出并登记 `FIG-0041…FIG-0050`；旧 `FIG-0032…0040` 分别 retired/superseded 并归档旧字节
  （Q1 三张因字节相同，工具拒绝 supersede，按纯退休处理）。
- 结论：`CLAIM-0060/0061/0067/0063/0064/0065` 新建；`CLAIM-0041/0054/0055` superseded、`CLAIM-0047/0052/0053` retracted
  （旧记录保留）。要求覆盖重映射到新 claim/实验/图（REQ-0001…0007）。
- 验证：Q2 `VAL-0070`（leakage）/`VAL-0073`（independent-rerun，rerun EXP-0108）；Q3 生成 `VAL-0076/0077`（rerun EXP-0112）；
  Q3 迁移 `VAL-0074/0075`（rerun EXP-0111）。
- 稳健性：ROB-0015/16/17 预登记并执行（各 n=2，判据通过）；补充种子块 EXP-0131/0132/0133 单列、未并入计划记录
  （工具拒绝覆盖已执行计划）。
- 干净目录复现：`src/r03_reproduce.py` → `ok=true`，四角色 `maxAbsDelta=0`（runId 20261027-212317）。
- 尚未解决：Q1 split-integrity/holdout-metrics（结构性）、Q3 原生优化检查（形状不兼容）、
  `QC-0033` analysis-evidence（历史实验缺输入清单，未 retrofit）、三问 selection 均 provisional、
  `outputs/q3/zspace_recompute.json` 过期未重跑 → 交付只能是 DRAFT（`final=false`）。
