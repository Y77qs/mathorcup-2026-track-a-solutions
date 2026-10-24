# 数据划分说明（data/splits/）

> 本目录只有 **两条允许使用的划分**，不得自造第三版：
> ① 台账主划分 `SPLIT-0002`（= `SPLIT-0001`，同一划分，分别建在 DATA-0002 / DATA-0001 上）；
> ② 分层稳健性划分 `data/splits/stratified/`。
> 生成与比对脚本：`src/04_split.py`（台账 `SCRIPT-0019`）；比对明细：`outputs/data/split_summary.json`。

## 1. 主评估划分（台账登记版）

`SPLIT-0002` 建在 **DATA-0002**（250×284，含 50 目标）上；`SPLIT-0001` 建在 DATA-0001（纯特征版）上。
两者数据行序相同、参数相同（random-holdout, 0.2, seed 42, positional），因此 **逐 beer 完全相同**
（assignment sha256 相同，0 个 beer 差异）——实验引用哪个都等价，**新实验优先引用 `SPLIT-0002`**。

| 项 | SPLIT-0002（主，新实验用） | SPLIT-0001（同一划分，历史版） |
|---|---|---|
| 台账 id | **SPLIT-0002**（datasetId = **DATA-0002**） | SPLIT-0001（datasetId = DATA-0001） |
| 路径 | `data/splits/SPLIT-0002/{train.csv,test.csv,assignment.csv,meta.json,split.log}` | `data/splits/SPLIT-0001/...` |
| 方法 | random-holdout，testFraction 0.2，seed **42**，rowIdMapping `positional` | 同上 |
| 规模 | 250 → **train 200 / test 50**，互斥，并集 250 | 同上 |
| assignment sha256 | `4a032d281d3b85f860e0322868afde68503abf13260cdf52496a276ed5a0855e` | 同左（逐 beer 相同） |
| train / test sha256 | `dbe66088…` / `56f3f162…`（284 列表） | `b5d41512…` / `32a3262f…`（235 列表） |
| **已知偏差** | **未分层**：test 只覆盖 **21/22** 风格，**`West Flanders ale`（7 样本）整类缺席 holdout** | 同左 |

主划分的 test 各风格样本数（合计 50，21 类）：
Blond 9、Tripel 5、Strong ale 5、Stout/Porter 3、Pils/Lager 3、Brown 3、Lambic 3、Dubbel 2、Scotch 2、
Saison 2、Amber 2、Christmas 2、Brett/cofermented 1、Hoppy 1、Wheat 1、Low/No alcohol 1、Fruitbeer 1、
Flanders old brown 1、Kriek 1、Faro 1、Brut 1；**West Flanders ale 0**。

**主评估口径**：所有 Q1/Q2/Q3 主实验传 `splitId = "SPLIT-0002"`。论文中必须把
"West Flanders ale 在 holdout 不可评"作为限制登记，不得用全样本或训练集冒充对该风格的评估。

## 2. 分层稳健性划分：`data/splits/stratified/`

| 项 | 值 |
|---|---|
| 路径 | `data/splits/stratified/{train.csv,test.csv,assignment.csv,meta.json}` |
| 方法 | `StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)`，分层变量 `tasting_category_fine` |
| 规模 | 250 → **train 200 / test 50**，互斥，并集 250 |
| 列数 | **284**（= DATA-0002 的 3 键 + 231 特征 + **50 目标**；与 SPLIT-0002 同 schema） |
| 覆盖 | **22/22 类进 test**（最小类 Faro = 3 → test 1） |
| assignment sha256 | `a468240288c06a31f500fe25933772c90453507a234e352c27d1a1583c8893d6` |
| train sha256 | `e640871c57a08732ffeeebbdc2811ec6f5dd2f1841f7fc9333c02b593e3fbd4c` |
| test sha256 | `71331d72cb3c1b8e6c1aef66cc678e352edc58fc4f6fd7752b3415e044e81b4a` |
| 生成运行 | SCRIPT-0025（`src/04_split.py`；assignment 与早期 235 列版本完全相同） |
| 性质 | **稳健性复核（robustness），不是主评估口径**；与 Lead 的 provisional 逐 beer 完全一致（0 差异） |

`stratified` 的 test 各风格样本数（合计 50，22 类）：
Blond 6、Tripel 6、Strong ale 4、Hoppy 3、Stout/Porter 3、Amber 2、Brown 2、Wheat 2、Lambic 2、Pils/Lager 2、
Dubbel 2、Kriek 2、Saison 2、Christmas 2、Fruitbeer 2、Low/No alcohol 2、West Flanders ale 1、
Brett/cofermented 1、Flanders old brown 1、Scotch 1、Brut 1、Faro 1。

**用途**：Q1/Q3 必须额外在这个划分上跑一次 holdout，并在报告里与主分割分列两栏数字
（"主分割 / 分层复核"），使 22 个风格在至少一处得到 holdout 覆盖。

## 3. 主划分 vs 分层版差异（真实数字）

| 项 | 值 |
|---|---|
| 两版 test 集是否相同 | 否 |
| 划分不同的 beer 数 | **92** |
| 差异 beer 清单 | 1,2,3,4,5,9,10,12,16,19,22,23,28,31,34,36,41,42,46,47,49,50,51,56,58,59,60,64,65,66,67,68,70,71,74,83,84,88,89,93,94,95,100,101,104,106,108,112,116,119,120,124,126,127,128,129,132,134,136,138,146,147,148,152,162,163,164,165,171,173,175,180,184,192,196,203,204,208,209,210,216,226,230,232,233,235,236,239,242,246,249,250 |
| 检查 | `outputs/data/split_summary.json` → `vs_official_SPLIT-0001` / `vs_SPLIT-0002`（含逐项字段） |

## 4. 使用规则（硬约束）

1. **modelers 只准用两条路径**：`data/splits/SPLIT-0002/assignment.csv`（主口径；`SPLIT-0001` 为同一划分的历史登记，等价）
   与 `data/splits/stratified/assignment.csv`（稳健性）；不得自造第三版、不得按结果换划分。
2. 主实验必须引用台账 `splitId = "SPLIT-0002"`；分层稳健性结果必须显式标注 "split = stratified"。
3. `data/splits/assignment_lead_provisional.csv` / `train_lead_provisional.csv` / `test_lead_provisional.csv`
   是 Lead 早期核对用文件，**不是权威口径**，仅为溯源保留。
4. 两版划分都只按 `beer` 生效（**不得**用 `beer_id` 连接，4/7.csv 的 beer_id 已脱敏）。
5. 任何重跑/复核必须使用同一划分；若数据或划分变化，相关验证与结论按台账协议标记过期。

## 5. 标定对划分的敏感性（Lead 的 06_calibration.py 实测）

同一套 z→0–6 标定规则在不同训练集上锚定到的维度数不同：

| 划分 | 标定产物 | 锚定维度数 |
|---|---|---|
| SPLIT-0001（= SPLIT-0002 同一划分） | `outputs/protocol/grade_calibration_SPLIT-0001.csv/.json` | **13/50** |
| stratified | `outputs/protocol/grade_calibration_stratified.csv/.json` | **15/50** |

该差异是真实的训练集敏感性，**不是 bug**；论文需说明标定只在训练集拟合，并报告两套划分下的分级指标。
