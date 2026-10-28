# Q3 结果文件索引（主键与形状）

本文件给出支撑材料 `outputs/q3/` 下各结果文件的**主键与用途**，便于逐格复核论文第 6 章。
全部文件均为 UTF-8 CSV/JSON；`chem__<name>` 列为 231 维化学/理化变量，`<dimension>` 列为 50 个感官标签。

| 文件 | 行数 × 列数 | 主键 / 结构 | 用途 |
| --- | --- | --- | --- |
| `samples.csv` | 750 × 237 | `sample_id`；键 `(repeat, fold, style, seed)`；`chem__*` 231 列 | 交付的约束后**设计谱**（题目要求的生成化合物谱全表） |
| `sensory_profiles.csv` | 1500 × 55 | `sample_id`；键 `(stage, repeat, fold, style)`；50 个 `<dimension>` 列 | 生成谱的感官代理画像（`stage=design` 与 `stage=raw` 各 750 行，题目要求的感官画像全表） |
| `samples_raw.csv` | 750 × 237 | 同上（`stage=raw`） | 未约束原始抽样，对照投影代价 |
| `q3_metrics.csv` / `energy_summary.csv` | 汇总 | 按格/按方案 | 归一化能量距离与质量指标 |
| `verdict_layers.csv` / `constraints.csv` | 逐条 | `(sample_id, constraint)` | 约束核验分层与逐条状态 |
| `transfers.csv` | 495 × 756 | 键 `(repeat, fold, source_beer, strategy)`；`src__/opt__/ref__ + chem__*` | 迁移前后设计值、缺陷状态与证书字段 |
| `transfer_verdicts.csv` | 逐 (策略, 字段, 边界类型, 判定) | 同左 | 约束核验计数 |
| `transfer_sources.csv` | 396 × 14 | 键 `(repeat, fold, source_beer, column)` | 源状态（实测/缺失/地板）与源值 |
| `transfer_constraints.csv` | 18810 = 5 策略 × 3762 | 键 `(strategy, …)` | 每条约束记录（3267 下界 + 396 源值上限 + 99 代理上界） |
| `solver_certificates.jsonl` | 198 行 | `problem_hash` | 每个 QP 的求解证书（状态/残差/KKT/半空间字段） |
| `v62_tables/tripel_kriek_lambic_profile_chem.csv` | 36 × 24 | 键 `(style, item_cn, column)` | 论文表 10 的三风格化学画像（含 P10/P90） |
| `v62_tables/tripel_kriek_lambic_profile_sensory.csv` | 15 × 24 | 键 `(style, item_cn, column)` | 论文表 11 的三风格感官画像 |
| `v62_tables/pils_to_tripel_single_source.csv` | 24 × 31 | 键 `(section, item_cn, column)` | 论文表 12 的单源迁移实例（源/锚点/参考/迁移后） |
| `v62_tables/defect_control_summary.csv` | 5 × 32 | 键 `column` | 论文表 15 的五类缺陷口径与核验计数 |
| `v62_tables/anchor_direct_projection.csv` | 159 × 17 | 键 `(level, strategy, repeat, fold)` | 论文表 17 的同锚点投影消融（pooled 与逐折） |
| `v62_tables/beer156_sensitivity.csv` | — | 键 `(scope, fold)` | beer156 极端坐标敏感性诊断 |
| `v62_tables/transfer_anchor_values.csv` | 22869 = 99 × 231 | 键 `(repeat, fold, source_beer, column)` | 99 个迁移点的分位数锚点全表（存储尺度 + 物理值） |
| `v62_diagnostics/v62_diagnostics.json` | — | 段：anchorDirectProjection / beer156Sensitivity / crossSetDiagnostic / assertions | 消融、敏感性与跨集邻近性的完整记录（54 条断言） |
| `v62_tables/q3_crossset_diagnostic.csv` | 10 行（9 折 + pooled） | 键 `(repeat, fold)` | 生成设计谱相对同折训练集的整行精确重合率与最近训练行标准化距离 |

**命名说明。** `outputs/q2/v62_clean/` 中的替代候选列历史名为 `alternative_rank4`；修复后该列语义已变为
“**首个合格同模块替代项**”（在模块点分序中剔除本维 Top-3 后取第一个），因此不再必然是模块点分第 4 名。
为保持与既有表格生成代码的兼容性未改列名，引用时请按正文口径读作“首个合格替代项”。

`outputs/q2/v62_clean/` 的四个 Top-3 CSV 与 `strict_lowpi_sign_status.csv` 同时带有
`alternative_rank4` 与 `alternative_first_valid` 两列，**两列取值逐格相同**：
`alternative_rank4` 为历史列名（下游脚本兼容用），`alternative_first_valid` 为本次修复后的规范列名
（“首个合格同模块替代项”）。两者同义，任取其一即可。
