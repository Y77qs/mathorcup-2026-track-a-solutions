# QP 证据口径澄清（两项）

项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`
性质：**独立证据审计**，不冒充原生 `optimization-feasibility/optimization-objective` VAL，也不进入 claim/robustness 的“已验证指标”清单。旧记录（`SCRIPT-0009` failed、`SCRIPT-0010` 的 4/396 与 1e-9）全部保留、不改写。
日期：2026-10-26。

## 1 z 空间调整量（`l1_change_z` / `mean_abs_change_z`）

问题：`centre/scale` 能否从 EXP-0080 的**冻结输入 + 确定性代码**无歧义重建？若能，独立重算。

**结论：能，且已重算通过。** 依据 `SCRIPT-0011`（script `src/q3_zspace_recompute.py`，sha256 `5030ccb183a584a55a6064947b1b53055f7a491dd3f7a530f695a8a415b1bd08`）：

- 重建方式：导入冻结快照模块 `experiments/EXP-0080/inputs/src/q3_transfer_fix.py`（其数据路径全部解析到 `experiments/EXP-0080/inputs/…` 快照），按生产折循环重建 `context_idx = 该 (repeat,fold) 训练行中剔除 Pils/Lager 源风格`，调用同一个 `fit_transfer_context`，得到 `centre = L.fit_standardizer(apply_median(X[context_idx]))` 与 `scale`。
- 覆盖：3 repeats × 3 outer folds = **9 个上下文**（与 EXP-0080 `n-folds=9` 一致），每个上下文的 `centre/scale` 以 sha256 落盘（`outputs/q3/zspace_centrescale.csv`，sha256 `c7aaa37779c5292746a4eefd7b2ce8baa3210bc5132731289663236eeee8b58c`）。
- 重算公式：`z = (x − centre)/scale`；`l1_change_z = Σ|z_new − z_source|`；`mean_abs_change_z = l1/231`。
- 结果：`outputs/q3/zspace_recompute.json`（sha256 `2915a2ee5f254554b66a1e15374df3b7529cd19027410dbd04cdb0ac1141f85d`）：
  - `rows_checked = 396`（99 × 4 策略），`rows_mismatched = 0`；
  - `max_abs_delta_l1_change_z = 0.0`，`max_abs_delta_mean_abs_change_z = 0.0`（float64 逐位重现，容差声明 1e-12）；
  - 分策略 `max_abs_delta_l1` 均为 `0.0`（source-fixed / target-mean-projection / qp-source-anchor / qp-quantile-anchor 各 99 行）。
- 冻结输入 sha256（同文件记录）：`data/clean/q3.csv`、`data/splits/NESTED-CV-1/splits.csv`、`src/q3_lib.py`、`src/v6_common.py`、`src/target_columns.py`、`src/q3_transfer_fix.py`。

可写入口径：`l1_change_z` / `mean_abs_change_z` 现在是**可由冻结输入与确定性代码复现**的量，可在 robustness 产物中作为“源改动量（z 空间）”引用。
**边界（必须同时写）**：这只证明该**位移量**可重现，不证明 QP 的目标函数、约束模型或最优性；z-space 复现不等于原生 optimization 检查通过。`SCRIPT-0009` 的失败（首版误用存储空间位移替代 z 空间位移）保留。

## 2 “58 条违规、残差和 4.58” 与 `max_constraint_violation = 0`

两项不是同一对象，逐项归类如下（数据源：`experiments/EXP-0080/transfer_constraints.csv` 15048 行 = 396 转移行 × 38 字段；`solver_certificates.jsonl` 198 条）。

### 2.1 58 条违规

| 项目 | 内容 |
|---|---|
| 字段 | `field = stale_hops(ridge-proxy)`，唯一字段 |
| 单位 | `ridge-proxy score (sensory label units)`——**感官标签单位的岭回归代理分**，不是化合物浓度 |
| 约束类型 | `bound_type = upper_source_value_proxy`（**代理上界**，非化学硬上界） |
| 上界值 | `bound_value = problem.source_prediction.stale_hops`（源谱的代理预测） |
| 样本阶段 | **最终交付谱**（`stored_after` 为最终值）；`target-mean-projection` 行不经过 QP，是参照控制，不是“优化前”状态 |
| 残差定义 | `residual = max(0, new − source − STALE_TOL)`，`STALE_TOL = 1e-9`（仅数值容差） |
| 判违 | `residual > 1e-12` → `verdict = infeasible` |
| 归属策略 | **58 条全部属于 `target-mean-projection`**（99 行中 41 行 `conditional`）；`qp-source-anchor` 99/99 conditional、`qp-quantile-anchor` 99/99 conditional、`source-fixed` 99/99 conditional，**QP 策略 0 条** |
| 残差和 4.5795501989305745 | 全部来自这 58 条（分策略残差和：target-mean-projection 4.57955；其余三策略 0.0） |
| 与 nonincrease-rate 的关系 | 该控制的 `nonincrease-rate = 41/99 = 0.41414141414141414`，与 58 条完全对应（41 行全不增） |

**判定：不是最终交付 QP 的硬约束失败。** 它是**参照控制策略**在 `stale_hops` 代理上的越界；该策略无 QP、无证书，仅作对照，且其不增率 0.4141 已在指标中原样披露（不是被隐藏的失败）。

### 2.2 `max_constraint_violation = 0`

| 项目 | 内容 |
|---|---|
| 对象 | 198 条 `solver_certificates.jsonl`（11 源 × 9 单元 × 2 个 QP 策略 = 198） |
| 含义 | QP 在 z 空间（231 变量）上对 **box 界 + 1 条半空间**（`arow·w ≤ stale_cap`）的最大违反量 |
| 容差 | `feasible = violation ≤ 1e-8`；`ADMM_TOL = 1e-8` |
| 实测 | 最大约束违反 `0.0`；max primal `9.989717497660422e-09`、max dual `3.393784142602385e-10`、max KKT `5.616718630759355e-09`；198/198 `status=optimal`、`qp-status-infeasible=0` |
| 与 58 条的关系 | **不同对象、不同空间、不同容差**：`max_constraint_violation` 只描述 QP 的 box+半空间；58 条是交付后的 `stale_hops` 代理残差，且只在参照控制上出现 |

**不得混写**：`max_constraint_violation=0` 不是“58 条违规已被消除”，58 条也不是“QP 不可行”。两者在 robustness/claim 文本中必须分开表述。

### 2.3 `upper_source_value_proxy` 的 4/396 行 1e-9 差异（保留）

- `SCRIPT-0010` 复算用 `residual = max(0, Δ)`，记录用 `max(0, Δ − 1e-9)`；两者在 4 行相差 `1.0000004e-9`，**已在 `outputs/q3/qp_cert_audit.json` 的 `constraint_residual.recompute_mismatch` 与 `recompute_max_abs_diff` 中原样保留**，本次不重跑去“抹平”。
- 4 行原始值（`source_beer, repeat, fold, recorded_residual, Δ=new−source`）：
  - `230, 0, 0, 0.00449065412820522, 0.00449065512820522`
  - `119, 0, 1, 0.004550029369448343, 0.0045500303694483435`
  - `90,  0, 1, 0.007071358377972361, 0.007071359377972361`
  - `119, 0, 2, 0.004419746313466997, 0.004419747313466997`
- 单位：`ridge-proxy score (sensory label units)`；容差：`STALE_TOL=1e-9`、判违阈值 `1e-12`；单位与容差均来自生产代码常量，未按结果调整。

## 3 与上一轮审计的关系

- `SCRIPT-0009`（failed）：保留。失败原因是审计脚本把存储空间位移当成 z 空间位移。
- `SCRIPT-0010`（succeeded）：保留，含 4/396 的 1e-9 差异与 `z_space_l1_recomputable_from_artifacts=false` 的限制表述。
- `SCRIPT-0011`（succeeded）：在**冻结快照 + 确定性代码**下重建 centre/scale，把 z 空间位移从“不可复算”升级为“可复现”，并保留“不证明目标函数/最优性”的边界。
