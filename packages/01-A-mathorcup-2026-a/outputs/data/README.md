# 数据交付索引（outputs/data/README.md）

> 项目：mathorcup-2026-a（赛道A 啤酒酿造化合物分析与啤酒风味预测）。
> 本文件索引 **data/clean/ 与 data/splits/ 的全部权威产物**，所有数字均来自真实运行输出文件。
> 数据版本：**DATA-0002**（250×284，3 键 + 231 特征 + 50 目标，主版本）；历史特征版 DATA-0001；
> 主划分：**SPLIT-0002**（与 SPLIT-0001 同一划分）；分层稳健性划分：`data/splits/stratified/`。
> 详细字段字典见 `data/clean/DATA_DICTIONARY.md`；划分规则见 `data/splits/README.md`；尺度证据见 `outputs/audit/scale_report.json`。

## 1. 台账 id 索引

| 类型 | id | 说明 |
|---|---|---|
| 数据集版本（主） | **DATA-0002** | register-clean 版本升级（parentId DATA-0001）：source `data/raw/4.csv`（双源，特征来自 1.csv）→ processed `data/clean/model_table.csv`（250×284，sha256 `c5ef4195…`），**284 条完整字段**，含 50 个目标 |
| 数据集版本（历史） | **DATA-0001** | 纯特征版：`data/clean/features_log.csv`（250×235，sha256 `344740eb…`），保留为历史版本 |
| 划分（主口径） | **SPLIT-0002** | register-split on DATA-0002：random-holdout，0.2，seed 42，rowIdMapping positional，200/50；assignment sha256 `4a032d28…` |
| 划分（同一划分的历史版） | **SPLIT-0001** | register-split on DATA-0001；与 SPLIT-0002 **逐 beer 完全相同（0 差异）** |
| 清洗脚本运行 | **SCRIPT-0004** | `src/03_clean.py`，exit 0，产出 5 个 csv + DATA_DICTIONARY + clean_summary.json |
| 尺度识别运行 | **SCRIPT-0008** | `src/02_scale.py`，exit 0，产出 scale_identification/oav_summary/scale_report |
| 模型表构建运行 | `src/07_model_table.py`（Lead） | 产出 `data/clean/model_table.csv` + `fields_model.json` + `outputs/protocol/model_table_checks.json`（cleaningscript sha `001bcf42…`） |
| 划分整理运行 | **SCRIPT-0019** | `src/04_split.py`，exit 0，产出 `data/splits/stratified/*` + split_summary.json（含 SPLIT-0001/0002 比对） |
| 画像（features） | **PROFILE-344740eb-38727341** | `data/processed/profile-344740eb-38727341.json`，features_log 250×235，**无 targetColumn**（原因见 §7） |
| 画像（targets） | **PROFILE-13ba7c41-e1ddcb76** | `data/processed/profile-13ba7c41-e1ddcb76.json`，targets_z 250×53，无 targetColumn |
| 画像（targets×A_hops_all） | **PROFILE-13ba7c41-6b2ee9fe** | `data/processed/profile-13ba7c41-6b2ee9fe.json`，targets_z，targetColumn=`A_hops_all`（**仅占位画像目标**，见 §7） |

## 2. 产物清单（路径、形状、sha256、生成来源）

### 2.1 清洗产物（data/clean/）

| 文件 | 行 × 列 | sha256 | 说明 |
|---|---|---|---|
| `data/clean/model_table.csv` | 250 × 284 | `c5ef4195703f4aa32a155236e867b41f99519d71b01d464e28c1d7f03e5bb3dc` | **DATA-0002 主表**：3 键 + 231 特征（1.csv 原值）+ 50 目标（4.csv 标准化连续值），数值一字未改；目标与 4.csv 逐 beer 全等 |
| `data/clean/fields_model.json` | 284 条 | `data/clean/fields_model.json` | 284 条完整字段（name/type/unit/role/scale/scale_status/odor_threshold/chemical_group/missing；目标含 sensory_set 与 defect） |
| `outputs/protocol/model_table_checks.json` | — | — | 一致性自检：`workbench_features_equal_231=true`、`workbench_extra_declared=[]`、`workbench_missing_declared=[]`、`targets_match_4csv_on_beer=true` |
| `data/clean/features_log.csv` | 250 × 235 | `344740ebf6297ec8bfe30887737370ad9b228372f4773259be8ef1a2ae6b8aee` | DATA-0001（历史特征版）：1.csv 原值复制 + beer/beer_id/tasting_category_fine/**style** + 231 特征；数值一字未改 |
| `data/clean/targets_z.csv` | 250 × 53 | `13ba7c4140af583f28d4fd9be2bdc9c0070e050e0e5a7378dcd4b26bf932519d` | 4.csv 的 50 个标准化感官目标，按 `beer` 对齐并用 1.csv 的未脱敏 beer_id |
| `data/clean/concentrations.csv` | 250 × 73 | `c101b8d55ea1b5d421cfb95cb54854455aba9600cc15b5d1b0b29e730a159c6d` | 8.xlsx `Calibrated chemical dataset`（作者统一浓度表，70 化合物） |
| `data/clean/oav.csv` | 250 × 44 | `b31ba08ed800e1af649d584557469e5cd8d7c1038e8d53797c78310e32fd2a90` | beer + 43 个阈值化合物 OAV = calibrated 浓度 / threshold_mean；1.csv 缺失处留空 |
| `data/clean/missing_flags.csv` | 250 × 10 | `dd7be762072e85e7c3b3f83ab5b97cc1748964bf334b0479bcdcf2a3f43b1d19` | beer + 9 个缺失列的 0/1 指示 |
| `data/clean/DATA_DICTIONARY.md` | — | `a64cb5287b7a717e79ba2d47b97b19184e49fa737a8981cefdf4a9d3f2a5440d` | 字段/单位/缺失政策/231 列尺度字典/泄漏清单 |
| `outputs/data/clean_summary.json` | — | `b436a031e2904a4abce7b8e4ef276d93a30b616743794b3fe63698c67f077211` | 清洗流水账（形状、缺失、sha256、oav 留空计数） |
| `outputs/data/fields_compact.json` | 284 条 | （构建中间件） | 由 `data/clean/fields_model.json` 压缩出的 `{name,type,unit,description}` 四键字段，用于 DATA-0002 的 `register-clean`（逐条与 model_table 表头同序；`fields_compact_lines.txt` 为逐行版本） |

### 2.2 尺度与 OAV 产物（outputs/audit/，SCRIPT-0008）

| 文件 | 行 × 列 | sha256 | 说明 |
|---|---|---|---|
| `outputs/audit/scale_identification.csv` | 231 × 27 | `63a05561d682e25cd5f566a2a74809b658c766262a68eda1e211ff056e07a34e` | 逐列尺度判定 + 证据（中位相对误差、负值/零值、共享地板、阈值可用性） |
| `outputs/audit/oav_summary.csv` | 43 × 24 | `1be04c54f2dbbff276e71e4c5b8e6c5f09806b4bfc5e007da79269d245963bf9` | 43 个阈值化合物 OAV 分位数、>1/>10 比例、量级合理性 |
| `outputs/audit/scale_report.json` | — | `5866ff8dbb22bf61f39c6c96dafb990cf705e67fb08c5bea5456f984789d16dc` | 完整尺度报告（opening question 结论、删失证据、单位对齐论证、论文可用数字） |

### 2.3 划分产物

| 文件 | 行 × 列 | sha256 | 角色 |
|---|---|---|---|
| `data/splits/SPLIT-0002/train.csv` | 200 × 284 | `dbe66088d43d5af6cb686499369e1bf7bdde31fb5ed3de69e787507f4abc0208` | **主口径** train（DATA-0002 全列） |
| `data/splits/SPLIT-0002/test.csv` | 50 × 284 | `56f3f16200f521a263ed6e046d9ef8b99bcd73b200208e7c14f555200d4dda6a` | **主口径** test（DATA-0002 全列） |
| `data/splits/SPLIT-0002/assignment.csv` | 250 × 2 | `4a032d281d3b85f860e0322868afde68503abf13260cdf52496a276ed5a0855e` | 台账 SPLIT-0002 assignment；与 SPLIT-0001 **逐 beer 相同（0 差异）** |
| `data/splits/SPLIT-0001/train.csv` | 200 × 235 | `b5d41512d66e85fd5cc240d31504f80c14f758b2fdd8928a99e67026b68253ff` | 历史（同一划分，DATA-0001 特征版）train |
| `data/splits/SPLIT-0001/test.csv` | 50 × 235 | `32a3262ff63fa6f38900036a33c097f95022416d664002adf7ad51e6174d9da4` | 历史（同一划分）test |
| `data/splits/SPLIT-0001/assignment.csv` | 250 × 2 | `4a032d281d3b85f860e0322868afde68503abf13260cdf52496a276ed5a0855e` | 台账 SPLIT-0001 assignment（row_index, split） |
| `data/splits/stratified/train.csv` | 200 × 284 | `e640871c57a08732ffeeebbdc2811ec6f5dd2f1841f7fc9333c02b593e3fbd4c` | 分层稳健性 train（含 50 目标，与 SPLIT-0002 同 schema） |
| `data/splits/stratified/test.csv` | 50 × 284 | `71331d72cb3c1b8e6c1aef66cc678e352edc58fc4f6fd7752b3415e044e81b4a` | 分层稳健性 test（含 50 目标） |
| `data/splits/stratified/assignment.csv` | 250 × 3 | `a468240288c06a31f500fe25933772c90453507a234e352c27d1a1583c8893d6` | 分层稳健性 assignment（beer, style, split；与 235 列旧版完全相同） |
| `data/splits/stratified/meta.json` | — | `e474d5b54bd48ba77465681a8aa8d62a4c0549f1f0e304ee9f2cf796b24642c3` | 分层划分参数与校验（含 `columns=284`、schema 说明） |
| `outputs/data/split_summary.json` | — | `cb5ec9f6fcbd96fc15d3ec3f3b7e81f720783f44c3cfcbbae68e80fc5706d5c7` | 三版划分逐 beer 差异（主 vs 分层 92 个；SPLIT-0002 vs SPLIT-0001 0 个）、各风格计数 |

## 3. 样本流与键规则

- 样本流：`1.csv` **250 行 → model_table 250 行（删除 0 行）**；`4.csv` 250 → `targets_z` 250。
  `model_table.csv` = 3 键 + 231 特征 + 50 目标（按 `beer` 合并，双源：特征 1.csv、目标 4.csv）；三张样本表（1/4/7.csv）的 `beer` 列顺序完全一致。
- **连接键只用 `beer`**（1..250）。1.csv 与 8.xlsx Calibrated 的 `beer_id` 未脱敏且完全一致；
  **4.csv / 7.csv 的 beer_id 被脱敏**（4.csv 仅 96 个唯一值，如 `5410230000000.0`），
  因此 `targets_z.csv` 的 beer_id 已用 1.csv 的未脱敏值替换。
- `tasting_category_fine`（22 类）在 1.csv 与 4.csv 中逐 beer 完全一致（250/250 已断言）；
  `style` 是其别名列。

## 4. 缺失政策（73 / 9 / 63）

- 1.csv 共 **73 个真实缺失**，分布 **9 列 / 63 行**：`amyl.acetate` 27、`aroma_hops_sum` 13、
  `methylpyrazine` 12、`X2.3.butanedione` 9、`X3.methylbutanal` 7、`ethyl.nicotinate` 2、
  `ethyl.isobutyrate` 1、`furfural` 1、`phenylacetaldehyde` 1。
- **清洗阶段不插补**：缺失原样保留在 `features_log.csv`；插补/标准化/特征选择**只在训练折内拟合**。
  `missing_flags.csv` 提供逐列 0/1 指示，供插补与"缺失行/完整行"分层误差报告使用。
- 缺失机制：缺失行 vs 完整行的风格分布无显著关联（audit.json C11b，χ² p≈0.34），但样本量小，仅作弱证据。
- **`calibrated == 0` 不是缺失，是"非检出（低于检出限）"**：1.csv 对这些行给出的是
  `log10(该列最小正浓度 / 2)` 的 **LOD/2 左删失替代码**（37 个 log10 列共 **755 个单元格 / 25 列**，
  最大比例偏差 5.5e-10）。1.csv 自身的 73 个 NaN 才是真缺失。
- `oav.csv`：43 个阈值化合物中，**25 个单元格因 1.csv 缺失而留空**（furfural 1、ethyl.isobutyrate 1、
  ethyl.nicotinate 2、X2.3.butanedione 9、methylpyrazine 12）；`calibrated==0`（非检出）的 OAV 保留 0。

## 5. 尺度口径（1.csv 是混合尺度表，论文必须这么写）

- 判定口径：以 8.xlsx `Calibrated chemical dataset`（70 列，列名与 1.csv 完全一致）为参照，
  比较 `10^v` 与 `v` 对 calibrated 的中位相对误差，阈值 1e-6；无 calibrated 覆盖的列一律 **unverified**。
- 计数：**log10 = 37 列**（10^v 中位相对误差 **5.93e-10**）、**linear = 33 列**（v 与 calibrated 完全一致，
  中位相对误差 **0.00e+00**）、**unverified = 161 列**。
  > **161 个 unverified 列不得写成"其余线性"**：它们没有外部浓度表可校验，不判定尺度、不声称物理单位。
- **1.csv 与 8.xlsx Calibrated 的关系（opening question）**：1.csv 是**混合尺度**表；8.xlsx calibrated
  是作者"去对数 + 非检出置 0"的统一浓度表。二者不是同一张表的冗余副本，也不能整表二选一。
- unverified 列的形态证据：**145/161 列含负值**（原始浓度不可能为负）、**142/161 列共享同一地板值
  `-1.81781854`（共 6807 格，≈ log10(0.01521)）**，与"低于检出限替换"的形态一致；据此只能说明
  "log 尺度可能性高"，底数与单位未验证，**不臆造**。
- 43 个有阈值化合物（8.xlsx `Sensory thresholds` 的 `field_name_R`，43/43 命中）：OAV = 还原浓度 / threshold_mean，
  单位即阈值表 unit（log10 列的 10^v 与 linear 列的 v 都等于 calibrated 浓度，故无需换算）。
  **39/43 化合物的中位 OAV 落在 1e-3~1e2**；4 个低于 1e-3 的是 `Z.nerolidol`(3.97e-4)、`methylpyrazine`(2.93e-4)、
  `CS2`(1.43e-4)、`furfural`(1.38e-4)——这是"该化合物实测浓度整体远低于收录阈值"的化学事实（如 furfural 实测
  ≤1.82 mg/L vs 阈值 60 mg/L），不是尺度错误。
- 题面点名的缺陷项锚点：DMS（log10，10^v = 1.11–520.45 ug/L，阈值 17.25 ug/L，OAV 中位 1.40）、
  diacetyl（linear，5.9e-8–121.7 mg/L，阈值 0.29925 mg/L，OAV 中位 0.95）、4VG（log10，阈值 0.206333 mg/L）、
  trans-2-nonenal（linear，无阈值行）、stale hops（`X.E..2.nonenal`/`X3.methyl.2.butenal`/`X5.methylfurfural`/`furfural`）。

## 6. 划分口径（主 + 稳健性两栏）

| | 主评估 | 分层稳健性 |
|---|---|---|
| 台账/路径 | **SPLIT-0002**（= SPLIT-0001，同一划分）：`data/splits/SPLIT-0002/`（历史版 `SPLIT-0001/`） | `data/splits/stratified/` |
| 方法 | random-holdout，0.2，seed 42 | StratifiedShuffleSplit，0.2，seed 42，stratify=`tasting_category_fine` |
| 规模 | train 200 / test 50 | train 200 / test 50 |
| 风格覆盖 | test 覆盖 **21/22**，**`West Flanders ale` 整类缺席** | test 覆盖 **22/22**（最小类 Faro=3 → test 1） |
| 与对方差异 | 两版 test 集有 **92 个 beer** 不同（逐项清单见 `outputs/data/split_summary.json`） | 与 Lead provisional 逐 beer **完全一致（0 差异）** |
| 用途 | 所有主实验必须 `splitId="SPLIT-0002"`（SPLIT-0001 为同一划分的历史登记，等价） | Q1/Q3 必须额外跑一次，报告分列"主分割 / 分层复核"两栏 |

- 分层版**不是**主口径；它的存在是为了让 22 个风格在至少一处得到 holdout 覆盖。
- 标定对训练集敏感（Lead 的 `06_calibration.py` 实测）：`outputs/protocol/grade_calibration_SPLIT-0001.csv/.json`
  锚定 **13/50** 维（SPLIT-0002 与 SPLIT-0001 的训练集完全相同，故沿用同一份标定）；
  `outputs/protocol/grade_calibration_stratified.csv/.json` 锚定 **15/50** 维。
  这是真实差异，论文需说明"标定只在训练集拟合"并报告两套划分下的分级指标。
- **行序提示**：`model_table.csv` 的行序沿用 1.csv 原序（beer = 10, 86, 2, …），**不是 beer 1..250 递增**
  （`model_table_checks.json` 的 `row_identity_beer_1_to_250=false` 即指此）。连接/划分一律按 `beer` 或 `row_index`，
  **不得**假设"第 i 行 = beer i"。

## 7. 画像（profile）口径说明，避免 reviewer 误读

- `PROFILE-344740eb-38727341`（features_log，250×235）：**没有 targetColumn**。原因：50 个感官目标在
  `targets_z.csv`，不在 `features_log.csv` 的列里；`profile` 要求 targetColumn 必须是同一文件的列，
  传 `A_hops_all` 会被工具拒绝（已实测）。该画像只用于字段类型/缺失/取值范围的**结构核对**。
- `PROFILE-13ba7c41-6b2ee9fe`（targets_z，targetColumn=`A_hops_all`）：`A_hops_all` 只是 50 个目标维度中的
  一个"占位画像目标"，用于描述目标间结构（如 `F_hops_all` r=0.82、`A_hops_noble` r=0.75）；
  **它不是 Q1 的单一主目标**，其 `corrWithTarget` **不得**用于特征筛选或任何跨文件特征-目标关联结论
  （跨文件相关只能建模折内计算，否则泄漏）。

## 8. 不可用于特征的泄漏清单

| 对象 | 为什么泄漏 | 允许用途 |
|---|---|---|
| `4.csv` 的 50 列感官目标（= `targets_z.csv`） | 就是 Q1 标签 | 只作 y；Q3 只作感官画像一致性校验 |
| `7.csv`（250×189，Ratebeer 评论派生，3 列全缺） | 目标代理（同源感官描述） | Q2 稳健性外部佐证；**禁止**进 Q1/Q3 特征 |
| `5.csv` / `6.csv`（感官间、化学-感官相关矩阵） | 由感官目标计算得到 | Q2 独立先验核对（不得用于挑 Top-3）；Q3 校验 |
| `8.xlsx` `GBM importance MDI` / `GBM SHAP Values` | 已用 4.csv 目标训练出的模型产物 | 只作外部对照 |
| `3.xlsx` 的 12 个 beer sheet + summary | 空白评分卡模板（无评分值） | 仅作 50 维定义与 0–6 刻度依据 |
| `2.csv`（231×231 Spearman） | 由 1.csv 特征计算，不含目标 | Q2 共表达图结构（允许） |

## 9. 复现命令

```bash
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
$PY src/02_scale.py        # -> outputs/audit/scale_identification.csv, oav_summary.csv, scale_report.json（SCRIPT-0008）
$PY src/03_clean.py        # -> data/clean/*, DATA_DICTIONARY.md, outputs/data/clean_summary.json（SCRIPT-0004）
$PY src/07_model_table.py  # -> data/clean/model_table.csv（250×284）, fields_model.json（Lead；cleaningscript sha 001bcf42…）
$PY src/04_split.py        # -> data/splits/stratified/*, outputs/data/split_summary.json（SCRIPT-0019）
# 台账登记（只能通过 modeling_* 工具）：DATA-0002 / SPLIT-0002 见 §1
```

## 10. 已知限制与未决项

1. **主划分未分层**：`SPLIT-0001` 的 holdout 无 `West Flanders ale`；该风格的任何结论都不得声称 holdout 评估。
2. **161 个 unverified 列**：不判定尺度、不声称单位；建模只用其 1.csv 原值，不做 10^v 还原。
3. **OAV 的删失约定**：`oav.csv` 与 `common.oav_table()` 同口径（calibrated/threshold），差异仅在 1.csv 缺失的
   25 格留空；`calibrated==0` 记 OAV=0。Q3 缺陷约束若改用 1.csv 的 LOD/2 代代码，需显式声明并做敏感性。
4. **73 个真实缺失未插补**：插补在建模折内进行；缺失行/完整行误差必须分列报告。
5. **标定对训练集敏感**（13/50 vs 15/50 锚定维度）：分级指标必须两套划分都报。
6. **oav.csv 只覆盖 43 个阈值化合物**；其余 188 列无阈值，OAV 不可计算（不是 0，也不是缺失）。
