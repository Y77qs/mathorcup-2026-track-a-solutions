# Q3 三张实体答案表：生成报告（v6.2）

由 `src/q3_v62_answer_tables.py` 从已保存产物自动生成；本文件中的数字均由脚本从 CSV/JSON 单元格计算，不含手抄值。脚本只读 `experiments/EXP-0109`、`experiments/EXP-0110`、`data/clean`、`data/processed`，不调用 modeling_* 插件，不读 `state/ledger.json`，不重训模型、不重拟合边际。

## 1 交付清单

| 文件 | 内容 | 行数/大小 |
| --- | --- | --- |
| `tripel_kriek_lambic_profile_chem.csv` | 化学谱 CSV（表 1） | 37 行（含表头） |
| `tripel_kriek_lambic_profile_sensory.csv` | 感官代理 CSV（表 1） | 16 行（含表头） |
| `tripel_kriek_lambic_profile.csv` | 化学+感官合并 CSV（block 列） | 52 行（含表头） |
| `tripel_kriek_lambic_profile_chem.md` | 化学谱 markdown | 44 行 |
| `tripel_kriek_lambic_profile_sensory.md` | 感官代理 markdown | 23 行 |
| `pils_to_tripel_single_source.csv` | 单源迁移 CSV（表 2） | 25 行（含表头） |
| `pils_to_tripel_single_source.md` | 单源迁移 markdown | 46 行 |
| `defect_control_summary.csv` | 缺陷控制 CSV（表 3） | 6 行（含表头） |
| `defect_control_summary.md` | 缺陷控制 markdown | 28 行 |
| `ANSWER_TABLES_REPORT.md` | 生成报告（本文件） | — |

同时写入 `FINAL_SUBMISSION_v6.2/支撑材料/outputs/q3/v62_tables/`（同名文件）。

## 2 代表源选择规则（表 2）

固定规则：repeat=0, 外层 fold=0, 在 11 支 Pils/Lager 源啤酒中取最小 source_beer id。

- 协议来源：`experiments/EXP-0110/transfer_outputs.json` 的 `q3_transfer.protocol.sourceStyle=Pils/Lager`、`targetStyle=Tripel`、`sourceBeers=[28, 81, 90, 96, 119, 124, 139, 185, 209, 218, 230]`。
- 代表源：**beer=28**，记录 `transfer_id=R0-F0-B028-qp-quantile-anchor`，status=optimal、feasible=True、fallback=False、约束违反 0。
- 来源行：`experiments/EXP-0110/transfers.csv`，键 = (repeat=0, fold=0, source_beer=28, strategy=qp-quantile-anchor)。

## 3 表 1：profile 表的口径

- 化学块（12 化合物 × 3 风格）：生成侧 = `EXP-0109/samples.csv` 的 design 谱（copula-selected，3 个冻结重复池化，Tripel/Kriek/Lambic 分别 84/30/33 份）；实测侧 = `data/clean/q3.csv` 对应风格真实训练行（28/10/11 行）。生成侧给中位数 [P10,P90]，实测侧给中位数 [P10,P90]；CSV 同时保留 mean。
- 感官块（5 维度 × 3 风格）：生成侧 = `EXP-0109/sensory_profiles.csv` 的 `stage=design` 50 维岭回归标签代理预测；实测侧 = `q3.csv` 的 50 维真实标签。生成侧给均值 [P10,P90]，实测侧给均值 [P10,P90]；CSV 同时保留中位数。
- 尺度：`data/processed/v6_feature_dictionary.csv` 的 tier/storage_scale/unit_or_scale；37 个 log10 校准列按 c=10^x 还原，33 个线性校准列按 c=x；其余 161 列为“存储尺度（未校准）”（表 1 中仅 4-松油醇 terpinen.4.ol 属此类，用于展示该标注）。
- 百分位：numpy linear 插值 P10/P90；显示 4 位有效数字，CSV 数值列保留全精度。

## 4 表 2 / 表 3：逐项溯源与不可得项

| 输出块 | 数字 | 来源文件 | 列/键 | 变换 |
| --- | --- | --- | --- | --- |
| (a) 源值 | src | EXP-0110/transfers.csv | `src__chem__<col>` | 物理：log10→10^x，线性→x |
| (a) 目标参考值 | ref | EXP-0110/transfers.csv | `ref__chem__<col>` | 同上；ref=centre+scale·z̄，**不是分位数锚点** |
| (a) 迁移后 | opt | EXP-0110/transfers.csv | `opt__chem__<col>` | 同上 |
| (a) 分位数锚点 | — | 无 | `transfers.csv:anchor` 只有标签 `quantile` | 锚点向量未落盘，见下文 |
| (b) 缺陷源/后值 | — | EXP-0110/transfers.csv | `<缺陷>_stored_source/_new`、`<缺陷>_physical_source/_new`、`<缺陷>_nonincreasing` | 直接用落盘物理值 |
| (b) 源状态 | — | EXP-0110/transfer_sources.csv | `source_state`、`raw_source_value`、`is_na`、`is_floor`（键 repeat=0/fold=0/source_beer=28） | 直接读取 |
| (b) 老化酒花代理 | — | EXP-0110/transfers.csv | `stale_hops_source/new/nonincreasing`、`stale_a_dot_source`、`stale_halfspace_b` | b=a'z_source+1e-9 |
| (c) 两类已记录代理 | — | EXP-0110/transfers.csv | `stale_hops_source/new`、`t2n_source/new` | 直接读取 |
| (c) 核心 5 维感官 | — | 无 | EXP-0110 只预测 stale_hops 与 t2n | 不适用，不臆造 |
| 表 3 阈值/单位 | — | data/clean/q3_thresholds.json | `defects.<名>.thresholdMean/Median/unit/tier` | 直接读取 |
| 表 3 实际约束值 | — | EXP-0110/transfer_constraints.csv | `bound_type`、`bound_value_physical` | 直接读取 |
| 表 3 源状态计数 | — | EXP-0110/transfer_sources.csv | `source_state`（99 行/化学列） | 计数 |
| 表 3 四类核验 | — | EXP-0110/transfer_verdicts.csv | `n`、`denominator`、`verifiedDenominator` | 按 verdict 汇总 |
| 表 3 老化酒花 b 范围 | — | EXP-0110/transfers.csv | `stale_halfspace_b`（主策略 99 行） | min/max |
| 表 3 源值超阈值计数 | — | EXP-0110/transfers.csv + q3_thresholds.json | `<缺陷>_physical_source` 与 `thresholdMean` | 逐行比较 |

**分位数锚点为何是 “—”（已验证不可得）**：`transfers.csv` 的 `anchor` 列只是标签（`quantile`）；`transfer_outputs.json` 的 `anchors` 只有文字定义；`marginal_state.csv` 只保存每（风格，列）的 n_valid/n_continuous/n_floor/omega/kappa/pi（状态表 `StyleMarginals.state_table()`），不含 `Marginal.inverse` 需要的支撑点 `grid_x/grid_u`；`solver_certificates.jsonl` 只保存 `problem_hash`。因此锚点向量**不能**从已保存产物单元格重建；本表给出 `ref__chem__`（目标参考均值）并在表头标注“非锚点”。精确锚点需要重拟合源/目标边际（重跑管线），超出本次只读产物口径。

## 5 表 3：3762 条约束记录的真实分解

| 约束类 | 记录数 | 计算 | 来源 |
| --- | ---: | --- | --- |
| 线性非负下界 lower_zero | 3267 | 33 个线性校准列 × 99 | transfer_constraints.csv |
| 四化学缺陷源值上限 upper_source_value | 396 | 4 缺陷 × 99 | transfer_constraints.csv |
| 老化酒花代理上界 upper_source_value_proxy | 99 | 1 代理 × 99 | transfer_constraints.csv |
| 合计（每个策略） | 3762 | 3267+396+99 | 与论文表述一致 |

核验状态（主策略 qp-quantile-anchor）：verified 3465、conditional 198、not_identifiable 99、failed 0；可核验分母 = 3762 − 99 = 3663。论文 qp-certs 表“3465 / 198 / 99 / 0，分母 3663”与此一致（3465 = 3267 条 lower_zero + 198 条上界）。

范围说明：`transfer_constraints.csv` 共 18810 行 = 5 个策略 × 3762；3762 是**每个策略**的记录集，不是 5 个策略的总和（18810 才是全文件行数）。

已知文本矛盾：`transfer_constraints.csv` 的 `unit` 列把 `chem__X.E..2.nonenal` 写成 “mg/L (unit NOT declared in q3_thresholds.json)”，但 `q3_thresholds.json` 的 `defects.X.E..2.nonenal.unit` 实际声明为 `mg/L`。表 3 采用阈值文件的声明并保留该矛盾说明；该字符串是审计代码的标签，不影响数值。

## 6 所有 “—” 及原因

| 位置 | 列 | 原因 |
| --- | --- | --- |
| 表 2 (a)(b) | 分位数锚点 | 锚点向量未落盘（见 §4）；ref__chem__ 只是最近可持久化参照，不冒充锚点 |
| 表 2 (c) | 核心 5 维感官代理的前后值 | EXP-0110 迁移管线只落盘 stale_hops 与 t2n 两个代理分数，没有 A_malt_all/A_hops_all/A_esters_all/acidity/overall 的迁移前后预测 |
| 表 3 非壬烯醛阈值 | thresholdMean/Median | `q3_thresholds.json` 对该缺陷为 null（无感官阈值），其约束仅为源值不增 |
| 表 3 老化酒花 | 阈值 | 无阈值；只有训练折内岭回归代理的半空间上界 |
| 表 1 未校准列 | 物理单位 | 4-松油醇的 `unit_or_scale` 为 “not declared in 8.xlsx”，只按存储尺度报告 |

## 7 单位与尺度来源

- 校准分级：`src/target_columns.py`（LOG10_CALIBRATED 37 列 / LINEAR_CALIBRATED 33 列 / FLOOR_COLUMNS 142 列）与 `data/clean/q2_chem_meta.json` 的 `log10Calibrated`/`linearCalibrated` 一致（脚本按前者取集合）。
- 每列单位/尺度：`data/processed/v6_feature_dictionary.csv` 的 `unit_or_scale`、`storage_scale`、`tier`。
- 缺陷单位/阈值：`data/clean/q3_thresholds.json` 的 `defects.<名>.unit`、`storageRules`、`thresholdMean`、`thresholdMedian`。
- 非检测码：`q3_thresholds.json` 的 `floorValue=-1.81781854`；表 1 所选 12 列在三风格真实行与生成谱中均未出现该码，故未触发“非检测按 0 计”。

## 8 复核

```bash
python \
  src/q3_v62_answer_tables.py
```

脚本自带输入列检查、代表源唯一性检查、3762 分解检查与四类核验总数检查，任一不符即具名失败，不填零。
