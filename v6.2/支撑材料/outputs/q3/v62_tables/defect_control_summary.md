**表 q3-defect-control　五类受控缺陷：尺度/单位、阈值与源值上限来源、源状态与核验记录构成**

说明：本表按交付策略 qp-quantile-anchor 统计。`transfer_verdicts.csv` 的 n / denominator / verifiedDenominator 按（strategy, field, bound_type, verdict）落盘；这里每个缺陷项取**实际约束行**（四个化学缺陷取 upper_source_value，代理取 upper_source_value_proxy），不把同名列的 lower_zero 下界行混入。分母 99 = 3 重复 × 3 折 × 11 支源啤酒；可核验分母 = 分母 − 不可识别。源状态计数来自 `transfer_sources.csv`（每个化学列 99 行），代理不在该文件中，单独标 99 个代理分数。 尺度/单位与阈值来自 `data/clean/q3_thresholds.json` 的 defects.<名>.unit / tier / thresholdMean / thresholdMedian；实际约束值来自 `transfer_constraints.csv` 的 bound_value_physical 与 `transfers.csv` 的 stale_halfspace_b。✳ 注意：transfer_constraints.csv 的 unit 列把反-2-壬烯醛写成 “unit NOT declared in q3_thresholds.json”，但阈值文件实际声明 mg/L；本表采用阈值文件的声明，并保留这一审计字符串矛盾。

（一）尺度、单位、阈值与实际约束来源

| 缺陷项（源列名） | 尺度/单位 | 阈值（q3_thresholds.json） | 本次实际约束与来源 | 源状态 实测/缺失/地板 | 源值超阈值 Mean（条/99） |
| --- | --- | --- | --- | ---: | ---: |
| 二甲基硫（DMS）（chem__DMS） | ug/L（log10，c=10**x） | Mean 17.25 / Median 19.00 | 源值上限 upper_source_value（transfer_constraints.csv，99 条） | 99 / 0 / 0 | 27（实测 27） |
| 双乙酰（2,3-丁二酮）（chem__X2.3.butanedione） | mg/L（linear，c=x） | Mean 0.2993 / Median 0.09000 | 源值上限 upper_source_value（transfer_constraints.csv，99 条） | 81 / 18 / 0 | 13（实测 9） |
| 4-乙烯基愈创木酚（4VG）（chem__X4VG） | mg/L（log10，c=10**x） | Mean 0.2063 / Median 0.2000 | 源值上限 upper_source_value（transfer_constraints.csv，99 条） | 18 / 0 / 81 | 0（实测 0） |
| 反-2-壬烯醛（trans-2-nonenal）（chem__X.E..2.nonenal） | mg/L（linear，c=x） | Mean — / Median — | 源值上限 upper_source_value（transfer_constraints.csv，99 条） | 99 / 0 / 0 | — |
| 老化酒花代理（stale_hops(ridge-proxy)） | ridge-proxy 分数（标准化感官标签单位） | 无（null） | 半空间 a'z≤b（b=-0.211239…0.134958，主策略 99 条） | 0 / 0 / 0；代理 99 | —（代理非浓度） |

（二）核验记录构成（主交付策略 qp-quantile-anchor）

| 缺陷项（约束类型） | 已验证 verified | 条件成立 conditional | 不可识别 not_identifiable | 失败 failed | 分母 | 可核验分母 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 二甲基硫（DMS）（upper_source_value） | 99 | 0 | 0 | 0 | 99 | 99 |
| 双乙酰（2,3-丁二酮）（upper_source_value） | 81 | 0 | 18 | 0 | 99 | 81 |
| 4-乙烯基愈创木酚（4VG）（upper_source_value） | 18 | 0 | 81 | 0 | 99 | 18 |
| 反-2-壬烯醛（trans-2-nonenal）（upper_source_value） | 0 | 99 | 0 | 0 | 99 | 99 |
| 老化酒花代理（岭回归）（upper_source_value_proxy（半空间 a'z<=b）） | 0 | 99 | 0 | 0 | 99 | 99 |
| 合计（五类上界记录） | 198 | 198 | 99 | 0 | 495 | 396 |

**3762 条约束记录的分解核验**（`transfer_constraints.csv`，主策略 qp-quantile-anchor）：记录总量 3762 = lower_zero 3267（33 个线性校准列 × 99）+ upper_source_value 396（4 个化学缺陷 × 99）+ upper_source_value_proxy 99（老化酒花代理 × 99）；与论文表述 3267+396+99=3762 **完全一致**。全文件共 18810 行 = 5 个策略 × 3762 条，3762 是**每个策略**的记录集，不是全部策略的总和。四类核验合计：verified 3465 / conditional 198 / not_identifiable 99 / failed 0，可核验分母 3663，其中 verified 3465 = 3267 条下界 + 198 条上界，与论文 qp-certs 表的 3465/198/99/0（分母 3663）一致。仅箱约束参照 target-mean-projection 在老化酒花代理上出现 conditional 41 / failed 58 条，其余四个策略在该代理上 conditional 99 / failed 0，说明半空间行是有效约束。

注：不增/上界是模型构造性质，不是感官合格证明；四个化学缺陷的 QP 上界是**源值本身**，不是感官阈值，源值已超阈值时 QP 只保证不恶化（例如本批 99 个源中 DMS 有 27 条源值已高于阈值 Mean 17.25 ug/L）。老化酒花只有训练折内岭回归代理，不能读作实测老化指标；B 表中的 conditional 一律来自代理或存储尺度约定（反-2-壬烯醛线性校准、单位按阈值文件声明），not_identifiable 一律来自源格缺失或地板码。双乙酰源值超阈值 Mean 的 13 条中，4 条来自训练折中位数填补的缺失源格，只有 9 条是实测源值。
