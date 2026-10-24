# 两类判定必须分开：reproduction（复现） vs stochastic-stability（随机稳定）

> 依据：VP-0001/0002/0003 预登记容差 + `outputs/review/calibration_verification.json` + pack `runtime/validation.js` 的
> `independentRerun`（确定性模型 1 次同 seed；随机模型 3 次不同 seed 取均值后与原始比）。
> 目的：防止把"跨 seed 波动大"说成"复现失败"，也防止把"同 seed 能复现"说成"模型稳定"。

## 1. 定义与判定口径

| 判定 | 问题 | 做法 | 通过口径 | 适用 |
|---|---|---|---|---|
| **reproduction（复现）** | 同一份代码、同一 seed、同一数据，结果是否一致？ | 用同 `codeFile`、同 `seed` 重跑（新 EXP id，`rerunOf`） | 逐维 R²/指标差 ≤ **1e-6**（确定性路径应精确一致） | Q1/Q2（固定 seed 的确定性流程） |
| **stochastic-stability（随机稳定）** | 换 seed（或换 bootstrap 重采样）后结论是否稳定？ | 3 个不同 seed 各跑一次，比较均值/区间 | 均值与原始差 ≤ **0.05**（Q3 风格命中率，预登记）；或 Top-3 入选频率/Jaccard 在多个 seed 下保持阈值 | Q3 生成模型；Q2 bootstrap |

## 2. 为什么不能混用

- **复现失败 ≠ 随机性大**：同 seed 重跑出现 1e-6 以上的差异，说明存在未固定的随机源（线程、哈希序、未设 seed 的插补/聚类），
  这是**工程确定性缺陷**，不能解释为"模型本身随机"。
- **随机性大 ≠ 复现失败**：Q3 换 seed 后风格命中率从 0.62 掉到 0.50，是 seed 敏感性（下游结论不稳），
  但同 seed 仍可完全复现；两者要分别报告。
- **两者都通过也不等于有效**：复现只证明"可重跑"，随机稳定只证明"对 seed 不敏感"，都不证明模型正确或分级有效。

## 3. 本项目当前的具体应用

### Q1（确定性）
- `independent-rerun`：seed=42 同码重跑，**逐维 R² 差 ≤1e-6**（VP-0001）。若失败 → reproduction failed。
- 另：**标定参数 (a,s) 的 fit_scope 已独立核过**（train-200 重估与 stored 差 ~1e-16），属 reproduction 证据，不是 stability。
- 4.csv 的 QWK 跨口径（P1 vs P2/P3/P4）**不是** reproduction，也不是 stability；它是"标定口径敏感性"（见 method_findings §3d）。

### Q2（bootstrap 确定性）
- bootstrap 固定 seed 后是确定性计算：**reproduction** 用 1e-6 核入选频率/Jaccard 能否逐位复现（VP-0002）。
- **stochastic-stability**：另跑 3 个 bootstrap seed，看 Top-3 集合与 Jaccard 是否仍满足预登记阈值
  （单席位 ≥0.80、跨方法 Jaccard ≥0.50）。这是"结论对重采样是否稳"，与复现分开报告。

### Q3（随机生成）
- **stochastic-stability**：3 个 seed 的风格判别命中率均值与原始差 ≤ **0.05**（VP-0003）。这是预登记的 seed 敏感性上限，
  **不是复现精度**。
- **reproduction** 的 1e-6 不适用于跨 seed 的生成结果；只有当同 seed 重跑（确定性实现）时才能用 1e-6 核
  "同一 seed 是否可复现"。
- 结论写法：分别写 "reproduction: PASS/FAIL（同 seed）" 与 "stochastic-stability: 命中率 0.62→0.50（Δ=0.12 > 0.05，FAIL）"，
  不得合并成一句"复现通过/不通过"。

## 4. 报告模板（validation_report.md 将按此填写）

```
[Qx] reproduction: <metric> 原值=A，重跑=B，|Δ|=C，容差=1e-6 → PASS/FAIL（原因）
[Qx] stochastic-stability: k=3 seeds，均值=M，区间=[L,U]，与原始差=D，上限=0.05 → PASS/FAIL
[Qx] 结论：以上两项独立；任何一项 FAIL 不得写成"已验证通过"。
```
