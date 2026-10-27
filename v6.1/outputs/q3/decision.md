# Q3 决策与稳健性（确认轮，自动生成）

> 本文件由 `src/r05_q3_docs.py` 从当前台账与 `outputs/q3/style_and_displacement_scope.json` 生成，数字不手抄。
> **只含确认轮**；先导轮 ROB-0001..0006 与 EXP-0076/0077 明确排除，不拼接。

## 1 生成侧（EXP-0079 / CLAIM-0054，active）

- 归一化经验 V 能量距离（21 个可估风格、177 个可估格、n_gen=729，n_gen 加权池化）= **0.884026**
- Tripel/Kriek/Lambic 三风格 27 格（n_gen=147）单独池化 = **1.830576**（不是上面的池化值）
- constraint-satisfaction = 1.000 是约束投影的**构造性质**，不作为分布质量证据；未约束原始生成 = 0.113333
- 限制：source-resample 控制 energy-distance = 0.813731 **优于**生成设计，故不宣称优于基线/真实参照；无原生 optimization VAL；Q3 选择仍为 **provisional**（生成/迁移双对象无法用单一 selectedModelId 表示）
- 稳健性 ROB-0009：0.877784 / 0.876453 / 0.898155，绝对极差 0.021702，**相对极差 0.024724 ≤ 0.05**（计划 message 的 0.021702 因 reference 为自由文本而按分母 1 计算，实为绝对极差；判定不变）（['multiple-seeds', 'param-perturbation']）

## 2 迁移侧（EXP-0080 / CLAIM-0055，active）

- 逐列不增率 = 1.000（qp-quantile-anchor / qp-source-anchor / source-fixed；target-mean-projection 参照控制 0.414141）
- 198 个 QP 证书全部 status=optimal，max primal = 9.9897e-9、max dual = 3.3938e-10、max_constraint_violation = 0、max KKT = 5.6167e-9
- 约束残差（transfer_constraints.csv 的 clamp(new−source,0)）最大：nonenal 3.5562e-17、butanedione 1.8041e-16
- qp-quantile-anchor 逐列 stored 位移 **max**：nonenal 0.001009（mean 1.02e-05）、butanedione 0.523886（mean 0.0939）、4VG 0.323279（mean 0.0127）
- 限制：nonincrease-rate=1.000 由硬上界构造保证且指标**饱和**，min 1≥1 不是改善量；source-fixed 是平凡对照；58 条 stale_hops 代理越界仅属 target-mean-projection 参照控制；z 位移可复现（SCRIPT-0011，396/396 delta=0）不证 QP 目标/最优性；**原生 optimization VAL 未通过、未声称**；不报告“迁移准确率”
- 稳健性 ROB-0010：[1, 1, 1]，min 1 satisfies min-value limit 1（['multiple-seeds', 'param-perturbation']）

## 3 本文件边界

- 生成与迁移分别评价，不合并为单一“Q3 成功率”。
- 两组件均只覆盖 2/3 冻结种子；固定种子独立复跑属确定性重现，不是独立实现。
- 本文件不构成交付审查，也不改变 selection 状态（Q3 = provisional）。
