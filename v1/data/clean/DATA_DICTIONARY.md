# 数据字典（data/clean，生成脚本 src/03_clean.py）

> 本文件由 `src/03_clean.py` 生成；所有数字来自该脚本运行时对 `data/raw/` 的真实计算。
> 口径：只做类型/键/对齐/派生/标记，**不做任何插补**（插补留在建模折内）。

## 1. 文件清单与样本流

| 文件 | 行 × 列 | 说明 |
|---|---|---|
| `data/clean/features_log.csv` | 250 × 235 | 1.csv 原值复制 + 键 + `style`（= tasting_category_fine 别名）；231 个特征列数值一字未改 |
| `data/clean/targets_z.csv` | 250 × 53 | 4.csv 的 50 个感官目标（标准化连续值），按 `beer` 对齐 1.csv 的 beer_id |
| `data/clean/concentrations.csv` | 250 × 73 | 8.xlsx `Calibrated chemical dataset`（作者统一浓度表，70 化合物） |
| `data/clean/oav.csv` | 250 × 44 | 43 个有阈值化合物的 OAV = calibrated 浓度 / threshold_mean；1.csv 缺失处留空 |
| `data/clean/missing_flags.csv` | 250 × 10 | 9 个缺失列的 0/1 缺失指示（供插补/分层使用） |

样本流：`1.csv` 250 行 → `features_log` **250 行（删除 0 行）**；`4.csv` 250 行 → `targets_z` 250 行；
三张样本表（1/4/7.csv）的 `beer` 列顺序完全一致，连接**只用 `beer`**。

## 2. 键与连接规则

- `beer`：1..250 的样本序号，三表顺序一致，是唯一可靠连接键。
- `beer_id`：1.csv 与 8.xlsx Calibrated 未脱敏且完全相同；**4.csv / 7.csv 的 beer_id 被脱敏**
  （4.csv 仅 96 个唯一值，如 5410230000000.0），故 `targets_z.csv` 的 `beer_id` 已用 1.csv 的未脱敏值替换。
- `tasting_category_fine`：22 类风格标签；4.csv 与 1.csv 逐 beer 完全一致（已断言），因此 `style` 列与两表标签等价。

## 3. 缺失政策

- 1.csv 共 **73 个真实缺失**，分布在 **9 列**、**63 行**：
  - `amyl.acetate`：27 个
  - `aroma_hops_sum`：13 个
  - `methylpyrazine`：12 个
  - `X2.3.butanedione`：9 个
  - `X3.methylbutanal`：7 个
  - `ethyl.nicotinate`：2 个
  - `ethyl.isobutyrate`：1 个
  - `furfural`：1 个
  - `phenylacetaldehyde`：1 个
- **清洗阶段不插补**：所有缺失原样保留在 `features_log.csv`；插补/标准化/特征选择只在训练折内拟合。
- `missing_flags.csv` 提供逐行逐列 0/1 指示，可用于插补模型与分层误差报告。
- 缺失机制：缺失行与完整行的风格分布无显著关联（`outputs/audit/audit.json` C11b：χ² 检验 p≈0.34），但样本量小，只能作为弱证据；按 questions.yaml 要求分别报告缺失行/完整行的误差。
- 与 `calibrated == 0` 区分：`calibrated == 0` 是**非检出（低于检出限）**标记，不是缺失；1.csv 对这些行给出的是 `log10(该列最小正浓度/2)` 的 LOD/2 替换值（log10 列共 755 个单元格，见 `outputs/audit/scale_report.json` 的 `censoring`）。
- `oav.csv` 中 **25 个单元格因 1.csv 缺失而留空**（涉及的化合物：`furfural`(1)、`ethyl.isobutyrate`(1)、`ethyl.nicotinate`(2)、`X2.3.butanedione`(9)、`methylpyrazine`(12)）；其余为 calibrated/threshold。`calibrated == 0`（非检出）的 OAV 保留 0。

## 4. 尺度字典（1.csv 是混合尺度表）

- 判定口径：以 8.xlsx `Calibrated chemical dataset`（70 列）为参照，比较 `10^v` 与 `v` 对 calibrated 的中位相对误差，阈值 1e-6；无 calibrated 覆盖的列一律 `unverified`（不臆造底数/单位）。
- 计数：**log10 = 37 列**，**linear = 33 列**，**unverified = 161 列**（合计 231 列）。
- log10 列：还原浓度 = `10^(1.csv 值)`；linear 列：浓度 = `1.csv 值`（与 calibrated 完全一致）。
- `unverified` 列：1.csv 值原样保留为特征；若其含负值/共享地板值，仅说明是 log 尺度可能性高，**不参与 OAV、不声称物理单位**。

### 4.1 有阈值的 43 个化合物（单位来自 8.xlsx Sensory thresholds，join 键为 `field_name_R`）

| 化合物（1.csv 列名） | 人读名 | 尺度 | 单位 | 阈值（threshold_mean） | off-flavor 标记 |
|---|---|---|---|---|---|
| `acetic_acid.g.L.` | acetic acid.g.L. | log10 | g/L | 0.14025 |  |
| `bitterness` | bitterness | log10 | IBU | 5 |  |
| `lactic_acid.mg.L.` | lactic acid | log10 | mg/L | 416.667 |  |
| `ethanol..v.v.` | ethanol..v.v. | log10 | v/v | 1.75726 |  |
| `isoamyl_alcohol` | isoamyl alcohol | log10 | mg/L | 40.015 |  |
| `isobutanol` | isobutanol | log10 | mg/L | 80 |  |
| `phenethyl_alcohol` | phenethyl alcohol | log10 | mg/L | 35.01 |  |
| `acetaldehyde` | acetaldehyde | log10 | mg/L | 50 | pungent, rotten-apples, green apple |
| `furfural` | furfural | linear | mg/L | 60 |  |
| `glycerol` | glycerol | log10 | g/L | 4.43333 |  |
| `GFS` | GFS | log10 | g/L | 2.9 |  |
| `ethyl_2.methyl_butyrate` | ethyl 2-methyl butyrate | log10 | mg/L | 0.027 |  |
| `ethyl_isovalerate` | ethyl isovalerate | log10 | mg/L | 0.1 |  |
| `ethyl_acetate` | ethyl acetate | log10 | mg/L | 24 |  |
| `ethyl.butyrate` | ethyl butyrate | linear | mg/L | 0.45 |  |
| `ethyl_decanoate` | ethyl decanoate | log10 | mg/L | 1.035 |  |
| `ethyl_hexanoate` | ethyl hexanoate | log10 | mg/L | 0.23 |  |
| `ethyl.isobutyrate` | ethyl isobutyrate | linear | mg/L | 2.6 |  |
| `ethyl.nicotinate` | ethyl nicotinate | linear | mg/L | 6 |  |
| `ethyl_octanoate` | ethyl octanoate | log10 | mg/L | 0.7 |  |
| `ethyl_propionate` | ethyl propionate | log10 | mg/L | 10 |  |
| `isopentyl_acetate` | isopentyl acetate | log10 | mg/L | 0.603333 |  |
| `isobutyl_acetate` | isobutyl acetate | log10 | mg/L | 1 |  |
| `octyl_acetate` | octyl acetate | log10 | mg/L | 0.5 |  |
| `phenethyl_acetate` | phenethyl acetate | log10 | mg/L | 1.76333 |  |
| `X2.3.butanedione` | 2,3-butanedione | linear | mg/L | 0.29925 | butterscotch, popcorn, oily, milky |
| `ammonia.mg.L.` | ammonia | log10 | mg/L | 2.6 |  |
| `iron` | iron | log10 | mg/L | 0.1 |  |
| `protein.g.L.` | protein.g.L. | log10 | g/L | 1.02393 |  |
| `X4VG` | X4VG | log10 | mg/L | 0.206333 |  |
| `methylpyrazine` | methylpyrazine | linear | mg/L | 1 |  |
| `CS2` | CS2 | log10 | ug/L | 50 |  |
| `DES` | DES | log10 | ug/L | 1.2 | rotting vegetables |
| `DMS` | DMS | log10 | ug/L | 17.25 | cooked vegetables, onion, garlic, corn, black currant, sulfidic, cabbage, tinned tomato, baked beans |
| `H2S` | H2S | log10 | ug/L | 3.5 | sulfidic, rotten eggs |
| `SO2.mg.L.` | SO2-mg.L. | log10 | mg/L | 15.3333 | Burnt matches |
| `alpha.humulene` | alpha-humulene | linear | mg/L | 0.625 |  |
| `X1.alpha.terpineol` | 1-alpha-terpineol | linear | mg/L | 1.5 |  |
| `E.caryophyllene` | E-caryophyllene | linear | mg/L | 0.28 |  |
| `citronellol` | citronellol | linear | mg/L | 0.0245 |  |
| `geraniol` | geraniol | linear | mg/L | 0.0315 |  |
| `linalool` | linalool | linear | mg/L | 0.027285 |  |
| `Z.nerolidol` | Z-nerolidol | linear | mg/L | 25 |  |

> 说明：阈值表的 `field_name_python` 是人读名（含空格/逗号，如 `2,3-butanedione`），与数据列名对不上；必须用 `field_name_R`（如 `X2.3.butanedione`）join。43/43 全部命中。

## 5. 目标字典（targets_z.csv，50 维）

| 族 | 维度数 | 列名 |
|---|---|---|
| Aroma | 15 | A_malt_all, A_malt_grain, A_malt_bread, A_malt_cara, A_malt_burn, A_hops_all, A_hops_citrus, A_hops_tropical, A_hops_noble, A_hops_woody, A_esters_all, A_esters_ethac, A_esters_isoaa, A_esters_flower, A_esters_fruity |
| Flavour/Taste | 15 | F_malt_all, F_malt_grain, F_malt_bread, F_malt_cara, F_malt_burn, F_hops_all, F_hops_citrus, F_hops_tropical, F_hops_noble, F_hops_woody, F_esters_all, F_esters_ethac, F_esters_isoaa, F_esters_flower, F_esters_fruity |
| 口感/缺陷/总体 | 20 | acidity, bitternes, sweetness, X4vg, diacetyl, dms, metallic, stale_hops, t2n, orange, coriander, clove, lactic, acetic, barnyard, alcohol, aftertaste, body, co2, overall |

- 4.csv 的数值是**标准化/中心化后的连续值**（每列 172–249 个不同取值，非整数化后的 z），无量纲。
- 0–6 分级标定（唯一定义，见 common.Z_GRADE_CALIBRATION）：`g = clip(floor(z / S + 3.5), 0, 6)`，主宽度 S = 1.0，敏感性 S = [0.75, 1.25]；等级 3 锚定 z = 0。
- 5 类题面点名缺陷维度的化合物映射见 `common.DEFECT_DIMS`（dms, diacetyl, X4vg, t2n, stale_hops）。

## 6. 特征字典（features_log.csv 的 231 个特征列）

| # | 列名 | 尺度判定 | 单位 | 1.csv 缺失数 | 聚合列 |
|---|---|---|---|---|---|
| 1 | `acetaldehyde` | log10 | mg/L | 0 |  |
| 2 | `CS2` | log10 | ug/L | 0 |  |
| 3 | `DES` | log10 | ug/L | 0 |  |
| 4 | `DMS` | log10 | ug/L | 0 |  |
| 5 | `ethyl_2.methyl_butyrate` | log10 | mg/L | 0 |  |
| 6 | `ethyl_acetate` | log10 | mg/L | 0 |  |
| 7 | `ethyl_decanoate` | log10 | mg/L | 0 |  |
| 8 | `ethyl_hexanoate` | log10 | mg/L | 0 |  |
| 9 | `ethyl_isovalerate` | log10 | mg/L | 0 |  |
| 10 | `ethyl_octanoate` | log10 | mg/L | 0 |  |
| 11 | `ethyl_propionate` | log10 | mg/L | 0 |  |
| 12 | `H2S` | log10 | ug/L | 0 |  |
| 13 | `isoamyl_alcohol` | log10 | mg/L | 0 |  |
| 14 | `isobutanol` | log10 | mg/L | 0 |  |
| 15 | `isobutyl_acetate` | log10 | mg/L | 0 |  |
| 16 | `isopentyl_acetate` | log10 | mg/L | 0 |  |
| 17 | `MeSH` | log10 | —（未验证/无阈值） | 0 |  |
| 18 | `octyl_acetate` | log10 | mg/L | 0 |  |
| 19 | `phenethyl_acetate` | log10 | mg/L | 0 |  |
| 20 | `phenethyl_alcohol` | log10 | mg/L | 0 |  |
| 21 | `X4VG` | log10 | mg/L | 0 |  |
| 22 | `SO2.mg.L.` | log10 | mg/L | 0 |  |
| 23 | `acetic_acid.g.L.` | log10 | g/L | 0 |  |
| 24 | `ammonia.mg.L.` | log10 | mg/L | 0 |  |
| 25 | `color.EBC.` | log10 | —（未验证/无阈值） | 0 |  |
| 26 | `betaglucan.mg.L.` | log10 | —（未验证/无阈值） | 0 |  |
| 27 | `lactic_acid.mg.L.` | log10 | mg/L | 0 |  |
| 28 | `glycerol` | log10 | g/L | 0 |  |
| 29 | `iron` | log10 | mg/L | 0 |  |
| 30 | `pH` | log10 | —（未验证/无阈值） | 0 |  |
| 31 | `protein.g.L.` | log10 | g/L | 0 |  |
| 32 | `bitterness` | log10 | IBU | 0 |  |
| 33 | `GFS` | log10 | g/L | 0 |  |
| 34 | `ethanol..v.v.` | log10 | v/v | 0 |  |
| 35 | `CO2.PSI.` | log10 | —（未验证/无阈值） | 0 |  |
| 36 | `unfermentables` | log10 | —（未验证/无阈值） | 0 |  |
| 37 | `kcalperc` | log10 | —（未验证/无阈值） | 0 | 是 |
| 38 | `X1.propanol` | unverified | —（未验证/无阈值） | 0 |  |
| 39 | `X2.3.butanedione` | linear | mg/L | 9 |  |
| 40 | `X3.methylbutanal` | linear | —（未验证/无阈值） | 7 |  |
| 41 | `propylene.glycol` | unverified | —（未验证/无阈值） | 0 |  |
| 42 | `propyl.acetate` | unverified | —（未验证/无阈值） | 0 |  |
| 43 | `n.pentanol` | unverified | —（未验证/无阈值） | 0 |  |
| 44 | `X2.methyl.1.butanol` | unverified | —（未验证/无阈值） | 0 |  |
| 45 | `isopentyl.formate` | unverified | —（未验证/无阈值） | 0 |  |
| 46 | `ethyl.isobutyrate` | linear | mg/L | 1 |  |
| 47 | `X3.methyl.2.butenal` | unverified | —（未验证/无阈值） | 0 |  |
| 48 | `X2.methyltetrahydrofuran.3.one` | linear | —（未验证/无阈值） | 0 |  |
| 49 | `ethyl.butyrate` | linear | mg/L | 0 |  |
| 50 | `butyl.acetate` | unverified | —（未验证/无阈值） | 0 |  |
| 51 | `methylpyrazine` | linear | mg/L | 12 |  |
| 52 | `furfural` | linear | mg/L | 1 |  |
| 53 | `ethyl.lactate` | unverified | —（未验证/无阈值） | 0 |  |
| 54 | `X3Z.hexenol` | linear | —（未验证/无阈值） | 0 |  |
| 55 | `n.hexanol` | linear | —（未验证/无阈值） | 0 |  |
| 56 | `styrene` | linear | —（未验证/无阈值） | 0 |  |
| 57 | `X2.furanmethanol` | unverified | —（未验证/无阈值） | 0 |  |
| 58 | `X3.methyl.2.hexanol` | unverified | —（未验证/无阈值） | 0 |  |
| 59 | `X3.furanmethanol` | unverified | —（未验证/无阈值） | 0 |  |
| 60 | `X2.acetylfuran` | unverified | —（未验证/无阈值） | 0 |  |
| 61 | `X2.6.dimethyl.pyrazine` | unverified | —（未验证/无阈值） | 0 |  |
| 62 | `amyl.acetate` | linear | —（未验证/无阈值） | 27 |  |
| 63 | `ethyl.tiglate` | unverified | —（未验证/无阈值） | 0 |  |
| 64 | `benzaldehyde` | linear | —（未验证/无阈值） | 0 |  |
| 65 | `X5.methylfurfural` | linear | —（未验证/无阈值） | 0 |  |
| 66 | `n.heptanol` | unverified | —（未验证/无阈值） | 0 |  |
| 67 | `X1.octen.3.ol` | unverified | —（未验证/无阈值） | 0 |  |
| 68 | `X3.methylthio.propanol` | unverified | —（未验证/无阈值） | 0 |  |
| 69 | `isomaltol` | unverified | —（未验证/无阈值） | 0 |  |
| 70 | `X6.methyl.5.hepten.2.one` | unverified | —（未验证/无阈值） | 0 |  |
| 71 | `X2.pentyl.furan` | unverified | —（未验证/无阈值） | 0 |  |
| 72 | `ethyl.hex..3E..enoate` | unverified | —（未验证/无阈值） | 0 |  |
| 73 | `alpha.phellandrene` | unverified | —（未验证/无阈值） | 0 |  |
| 74 | `dehydroxy.cis.linalool.oxide` | unverified | —（未验证/无阈值） | 0 |  |
| 75 | `hexyl.acetate` | linear | —（未验证/无阈值） | 0 |  |
| 76 | `isopentyl.butanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 77 | `X2.ethyl.1.hexanol` | unverified | —（未验证/无阈值） | 0 |  |
| 78 | `beta.phellandrene` | unverified | —（未验证/无阈值） | 0 |  |
| 79 | `limonene` | unverified | —（未验证/无阈值） | 0 |  |
| 80 | `eucalyptol` | unverified | —（未验证/无阈值） | 0 |  |
| 81 | `benzyl.alcohol` | linear | —（未验证/无阈值） | 0 |  |
| 82 | `ethyl.hex..2E..enoate` | unverified | —（未验证/无阈值） | 0 |  |
| 83 | `phenylacetaldehyde` | linear | —（未验证/无阈值） | 1 |  |
| 84 | `X.E..beta.ocimene` | linear | —（未验证/无阈值） | 0 |  |
| 85 | `prenyl.isobutyrate` | unverified | —（未验证/无阈值） | 0 |  |
| 86 | `ethyl.furoate` | unverified | —（未验证/无阈值） | 0 |  |
| 87 | `ortho.cresol` | unverified | —（未验证/无阈值） | 0 |  |
| 88 | `ethyl.5.methylhexanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 89 | `X2.acetylpyrrole` | unverified | —（未验证/无阈值） | 0 |  |
| 90 | `isoamyl.lactate` | unverified | —（未验证/无阈值） | 0 |  |
| 91 | `n.octanol` | unverified | —（未验证/无阈值） | 0 |  |
| 92 | `cis.linalool.oxide` | unverified | —（未验证/无阈值） | 0 |  |
| 93 | `meta.cymenene` | unverified | —（未验证/无阈值） | 0 |  |
| 94 | `terpinolene` | unverified | —（未验证/无阈值） | 0 |  |
| 95 | `linalool` | linear | mg/L | 0 |  |
| 96 | `nonan.2.ol` | unverified | —（未验证/无阈值） | 0 |  |
| 97 | `n.nonanal` | unverified | —（未验证/无阈值） | 0 |  |
| 98 | `X2.methyl.benzofuran` | unverified | —（未验证/无阈值） | 0 |  |
| 99 | `heptyl.acetate` | unverified | —（未验证/无阈值） | 0 |  |
| 100 | `X4.methyl.1.pentanol` | unverified | —（未验证/无阈值） | 0 |  |
| 101 | `neo.allo.ocimene` | unverified | —（未验证/无阈值） | 0 |  |
| 102 | `x.methyl.1.octanol` | unverified | —（未验证/无阈值） | 0 |  |
| 103 | `trans.dihydro.beta.terpineol` | unverified | —（未验证/无阈值） | 0 |  |
| 104 | `cis.beta.terpineol` | unverified | —（未验证/无阈值） | 0 |  |
| 105 | `y.methyl.1.octanol` | unverified | —（未验证/无阈值） | 0 |  |
| 106 | `camphor` | unverified | —（未验证/无阈值） | 0 |  |
| 107 | `isobutyl.hexanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 108 | `nerol.oxide` | unverified | —（未验证/无阈值） | 0 |  |
| 109 | `X.E..2.nonenal` | linear | —（未验证/无阈值） | 0 |  |
| 110 | `cis.dihydro.beta.terpineol` | unverified | —（未验证/无阈值） | 0 |  |
| 111 | `X4.ethyl.phenol` | unverified | —（未验证/无阈值） | 0 |  |
| 112 | `isoborneol` | unverified | —（未验证/无阈值） | 0 |  |
| 113 | `ethyl.benzoate` | unverified | —（未验证/无阈值） | 0 |  |
| 114 | `n.nonanol` | unverified | —（未验证/无阈值） | 0 |  |
| 115 | `terpinen.4.ol` | unverified | —（未验证/无阈值） | 0 |  |
| 116 | `diethyl.succinate` | linear | —（未验证/无阈值） | 0 |  |
| 117 | `vinyl.caprylate` | unverified | —（未验证/无阈值） | 0 |  |
| 118 | `X1.alpha.terpineol` | linear | mg/L | 0 |  |
| 119 | `ethyl..E..linalool` | unverified | —（未验证/无阈值） | 0 |  |
| 120 | `ethyl.nicotinate` | linear | mg/L | 2 |  |
| 121 | `citronellol` | linear | mg/L | 0 |  |
| 122 | `nerol` | unverified | —（未验证/无阈值） | 0 |  |
| 123 | `hydroxy.methyl.furfural` | unverified | —（未验证/无阈值） | 0 |  |
| 124 | `E.ocimenone` | unverified | —（未验证/无阈值） | 0 |  |
| 125 | `cumin.aldehyde` | unverified | —（未验证/无阈值） | 0 |  |
| 126 | `ethyl.phenylacetate` | unverified | —（未验证/无阈值） | 0 |  |
| 127 | `isopentyl.hexanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 128 | `geraniol` | linear | mg/L | 0 |  |
| 129 | `beta.cyclohomocitral` | unverified | —（未验证/无阈值） | 0 |  |
| 130 | `E.cinnamaldehyde` | unverified | —（未验证/无阈值） | 0 |  |
| 131 | `n.decanol` | unverified | —（未验证/无阈值） | 0 |  |
| 132 | `neryl.formate` | unverified | —（未验证/无阈值） | 0 |  |
| 133 | `X4.ethyl.guaiacol` | unverified | —（未验证/无阈值） | 0 |  |
| 134 | `X2.undecanone` | unverified | —（未验证/无阈值） | 0 |  |
| 135 | `trans.dihydro.alpha.terpinyl.acetate` | unverified | —（未验证/无阈值） | 0 |  |
| 136 | `terpinen.4.ol.acetate` | unverified | —（未验证/无阈值） | 0 |  |
| 137 | `X2.undecanol` | unverified | —（未验证/无阈值） | 0 |  |
| 138 | `delta.terpinyl.acetate` | unverified | —（未验证/无阈值） | 0 |  |
| 139 | `X.E.E..2.4.decadienal` | linear | —（未验证/无阈值） | 0 |  |
| 140 | `methyl.geranate` | unverified | —（未验证/无阈值） | 0 |  |
| 141 | `car.3.en.2.one` | unverified | —（未验证/无阈值） | 0 |  |
| 142 | `dimethoxy..E..citral` | unverified | —（未验证/无阈值） | 0 |  |
| 143 | `X2.butyloctanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 144 | `X4.methoxysalicylaldehyde` | unverified | —（未验证/无阈值） | 0 |  |
| 145 | `ethyl.hydrocinnamate` | unverified | —（未验证/无阈值） | 0 |  |
| 146 | `eugenol` | linear | —（未验证/无阈值） | 0 |  |
| 147 | `gamma.nonalactone` | linear | —（未验证/无阈值） | 0 |  |
| 148 | `methyl.para.anisate` | unverified | —（未验证/无阈值） | 0 |  |
| 149 | `X.E..beta.damascenone` | linear | —（未验证/无阈值） | 0 |  |
| 150 | `ethyl..9..decenoate` | unverified | —（未验证/无阈值） | 0 |  |
| 151 | `vanillin` | unverified | —（未验证/无阈值） | 0 |  |
| 152 | `geosmin` | unverified | —（未验证/无阈值） | 0 |  |
| 153 | `dodecanal` | unverified | —（未验证/无阈值） | 0 |  |
| 154 | `X4.8.alpha.epoxy.caryophyllane` | unverified | —（未验证/无阈值） | 0 |  |
| 155 | `E.caryophyllene` | linear | mg/L | 0 |  |
| 156 | `X.E..alpha.ionone` | unverified | —（未验证/无阈值） | 0 |  |
| 157 | `perillyl.acetate` | unverified | —（未验证/无阈值） | 0 |  |
| 158 | `beta.humulene` | unverified | —（未验证/无阈值） | 0 |  |
| 159 | `X2.phenyl.ethyl.butyrate` | unverified | —（未验证/无阈值） | 0 |  |
| 160 | `X.Z..beta.farnesene` | unverified | —（未验证/无阈值） | 0 |  |
| 161 | `pentyl.octanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 162 | `X.E..beta.farnesene` | unverified | —（未验证/无阈值） | 0 |  |
| 163 | `X2.methylbutyl.octanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 164 | `alpha.humulene` | linear | mg/L | 0 |  |
| 165 | `neryl.propanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 166 | `X9.epi..E..caryophyllene` | unverified | —（未验证/无阈值） | 0 |  |
| 167 | `ethyl..E..cinnamate` | unverified | —（未验证/无阈值） | 0 |  |
| 168 | `linalool.isovalerate` | unverified | —（未验证/无阈值） | 0 |  |
| 169 | `alpha.terpinyl.isobutanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 170 | `n.dodecanol` | unverified | —（未验证/无阈值） | 0 |  |
| 171 | `germacrene.D` | unverified | —（未验证/无阈值） | 0 |  |
| 172 | `X.E..beta.ionone` | unverified | —（未验证/无阈值） | 0 |  |
| 173 | `valencene` | unverified | —（未验证/无阈值） | 0 |  |
| 174 | `neryl.isobutanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 175 | `E.methyl.isoeugenol` | unverified | —（未验证/无阈值） | 0 |  |
| 176 | `X.Z..dihydro.apofarnesal` | unverified | —（未验证/无阈值） | 0 |  |
| 177 | `butylated.hydroxytoluene` | unverified | —（未验证/无阈值） | 0 |  |
| 178 | `X.E..dihydro.apofarnesal` | unverified | —（未验证/无阈值） | 0 |  |
| 179 | `Z.nerolidol` | linear | mg/L | 0 |  |
| 180 | `X.E..ortho.methoxy.cinnamaldehyde` | unverified | —（未验证/无阈值） | 0 |  |
| 181 | `alpha.calacorene` | unverified | —（未验证/无阈值） | 0 |  |
| 182 | `E.nerolidol` | unverified | —（未验证/无阈值） | 0 |  |
| 183 | `dihydroisocaryophyllene.epoxide` | unverified | —（未验证/无阈值） | 0 |  |
| 184 | `caryophyllene.alcohol` | unverified | —（未验证/无阈值） | 0 |  |
| 185 | `neryl.isovalerate` | unverified | —（未验证/无阈值） | 0 |  |
| 186 | `spathulenol` | unverified | —（未验证/无阈值） | 0 |  |
| 187 | `caryophyllene.oxide` | unverified | —（未验证/无阈值） | 0 |  |
| 188 | `humulene.epoxide.II` | unverified | —（未验证/无阈值） | 0 |  |
| 189 | `alloaromadendrene.epoxide` | unverified | —（未验证/无阈值） | 0 |  |
| 190 | `X1.10.di.epi.cubenol` | unverified | —（未验证/无阈值） | 0 |  |
| 191 | `isopropyl.laurate` | unverified | —（未验证/无阈值） | 0 |  |
| 192 | `caryophylla.4.12..8.13..dien.5.alpha.ol` | unverified | —（未验证/无阈值） | 0 |  |
| 193 | `gamma.eudesmol` | unverified | —（未验证/无阈值） | 0 |  |
| 194 | `alpha.muurolol` | unverified | —（未验证/无阈值） | 0 |  |
| 195 | `X1.2.dihydro.8.hydroxy..2E..linalool` | unverified | —（未验证/无阈值） | 0 |  |
| 196 | `tau.cadinol` | unverified | —（未验证/无阈值） | 0 |  |
| 197 | `selin.11.en.4.alpha.ol` | unverified | —（未验证/无阈值） | 0 |  |
| 198 | `alpha.eudesmol` | unverified | —（未验证/无阈值） | 0 |  |
| 199 | `X14.hydroxy.9.epi..E..caryophyllene` | unverified | —（未验证/无阈值） | 0 |  |
| 200 | `tau.muurolol` | unverified | —（未验证/无阈值） | 0 |  |
| 201 | `n.tetradecanol` | unverified | —（未验证/无阈值） | 0 |  |
| 202 | `foeniculin` | unverified | —（未验证/无阈值） | 0 |  |
| 203 | `cadalene` | unverified | —（未验证/无阈值） | 0 |  |
| 204 | `X2.3.dihydro.farnesol` | unverified | —（未验证/无阈值） | 0 |  |
| 205 | `X2E.6Z.farnesal` | unverified | —（未验证/无阈值） | 0 |  |
| 206 | `caryophyllene.acetate` | unverified | —（未验证/无阈值） | 0 |  |
| 207 | `X14.hydroxy.alpha.humulene` | unverified | —（未验证/无阈值） | 0 |  |
| 208 | `X2Z.6E.farnesal` | unverified | —（未验证/无阈值） | 0 |  |
| 209 | `X2Z.6Z.farnesol` | unverified | —（未验证/无阈值） | 0 |  |
| 210 | `X2Z.6E.farnesol` | unverified | —（未验证/无阈值） | 0 |  |
| 211 | `ambroxide` | unverified | —（未验证/无阈值） | 0 |  |
| 212 | `benzyl.benzoate` | unverified | —（未验证/无阈值） | 0 |  |
| 213 | `X2E.6E.methyl.farnesoate` | unverified | —（未验证/无阈值） | 0 |  |
| 214 | `ethyl.tetradecanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 215 | `X2.ethylhexylsalicylate` | unverified | —（未验证/无阈值） | 0 |  |
| 216 | `isopropyl.tetradecanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 217 | `ethyl.pentadecanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 218 | `methyl.hexadecanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 219 | `Z.Z.geranyl.linalool` | unverified | —（未验证/无阈值） | 0 |  |
| 220 | `ethyl.hexadecanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 221 | `manool.oxide` | unverified | —（未验证/无阈值） | 0 |  |
| 222 | `X13.epi.manool.oxide` | unverified | —（未验证/无阈值） | 0 |  |
| 223 | `isopropyl.hexadecanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 224 | `manool` | unverified | —（未验证/无阈值） | 0 |  |
| 225 | `ethyl.octadecanoate` | unverified | —（未验证/无阈值） | 0 |  |
| 226 | `ethyl.pentanoate` | linear | —（未验证/无阈值） | 0 |  |
| 227 | `X2.ethyl.3.methylpyrazine` | linear | —（未验证/无阈值） | 0 |  |
| 228 | `esters_sum` | unverified | —（未验证/无阈值） | 0 | 是 |
| 229 | `aroma_hops_sum` | unverified | —（未验证/无阈值） | 13 | 是 |
| 230 | `acids_sum` | unverified | —（未验证/无阈值） | 0 | 是 |
| 231 | `sulfur_sum` | unverified | —（未验证/无阈值） | 0 | 是 |

> 5 个聚合列（`kcalperc`/`acids_sum`/`esters_sum`/`aroma_hops_sum`/`sulfur_sum`）由多个化合物计算得出，本身是化合物函数；按 questions.yaml 要求须在消融中单独评估（含/不含）。

## 7. 不可用于特征的泄漏清单

| 对象 | 为什么泄漏 | 允许用途 |
|---|---|---|
| `4.csv` 的 50 列感官目标 | 就是 Q1 标签 | 只作 y；可作 Q3 感官画像的一致性校验 |
| `7.csv`（250×189，Ratebeer 论坛评论派生） | 目标代理（同源感官描述，3 列全缺） | Q2 稳健性外部佐证，禁止进 Q1/Q3 特征 |
| `5.csv` / `6.csv`（感官间与化学-感官相关矩阵） | 由感官目标计算得到 | Q2 的独立先验核对（不得用于挑 Top-3）；Q3 画像校验 |
| `8.xlsx` `GBM importance MDI` / `GBM SHAP Values` | 已用 4.csv 目标训练出的模型产物 | 只作外部对照 |
| `3.xlsx` 的 12 个 beer sheet + summary | 空白评分卡模板（无评分值） | 仅作 50 维定义与 0–6 刻度依据 |
| `2.csv`（231×231 Spearman） | 由 1.csv 特征计算，不含目标 | Q2 共表达图结构（允许） |

## 8. 复现

```bash
# 解释器：contest.yaml runtime.python
python src/02_scale.py    # -> outputs/audit/scale_*.{csv,json}
python src/03_clean.py    # -> data/clean/*, outputs/data/clean_summary.json
python src/04_split.py    # -> data/splits/{train,test,assignment}.csv
```

