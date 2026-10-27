# 实验脚本接口约定（所有 modeler 必读）

项目目录：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3`
解释器：`/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python`

**只写文件、只在本地测试；不要调用任何 `modeling_*` 工具**（台账写入由 Lead 负责，写错不可逆）。

## 1. 运行环境（Seatbelt 沙箱）

实验由 runner 启动，`cwd = experiments/EXP-xxxx/`，只导出以下内容：

| 变量 | 含义 |
|---|---|
| `MODELING_PROJECT_DIR` | 项目根 |
| `MODELING_EXPERIMENT_DIR` | 本次实验目录（唯一可写目录） |
| `MODELING_DATA_FILE` | 注册数据集 CSV 绝对路径 |
| `MODELING_TRAIN_FILE` / `MODELING_TEST_FILE` / `MODELING_ASSIGNMENT_FILE` | 仅当实验挂载 splitId 时存在 |
| `MODELING_SEED` | 注册的随机种子 |
| `MODELING_DEPENDENCIES` | JSON：`{项目相对路径: 沙箱内绝对路径}`，只能读这里登记的文件 |
| `PYTHONPATH` | 含沙箱内 `src/` 快照目录，所以 `import q_common` 可用 |

**只能**通过 `modeling_contract`（`seed / emit_metrics / emit_predictions / emit_output / save_figure`）与
`q_common`（已提供，**不得修改**）读取数据/写结果。除 `MODELING_*` 指向的文件与 `dependency_path()` 返回的文件外，任何读取都会被沙箱拒绝。
不得写 `MODELING_EXPERIMENT_DIR` 之外的任何路径。

## 2. 强制契约

```python
from modeling_contract import seed, emit_metrics, emit_predictions, emit_output, save_figure
s = seed()                                  # 必须第一行调用；所有随机数都用它派生
```

* `emit_metrics({...})` 只允许**有限数值**（int/float）。字符串/None/NaN/Inf/list/bool 会被拒绝 → 整次实验 `NO_OUTPUT`。
  主指标键必须精确等于注册的 `metricKey`。
* 逐维数组、Top-3 名单、消融表、阈值、文字结论 → `emit_output(name, value)`（写 `outputs.json`，值可为嵌套结构）。
* 预测文件 → `emit_predictions(df, "predictions.csv")`；集合证据 → `df.to_json(...)`/`json.dump` 写到实验目录再在 outputs 里登记。
* 图 → `save_figure(fig, "name")`；**图内文字全英文**（本机无中文字体）。
* **独立复跑（independent-rerun）会用同一 seed 重跑并逐位比较所有数值指标**：脚本必须完全确定性。
  禁止 `time`、`uuid`、未播种的 `np.random`、按字典/集合迭代顺序影响数值的写法。
* 不得读取未登记文件；不得联网；不得起子进程。

## 3. 数据（已注册）

| 文件 | 形状 | 说明 |
|---|---|---|
| `data/clean/q2_raw.csv` (DATA-0001) | 250×285 | `row,beer,beer_id,tasting_category_fine` + `chem__<231>` + 50 个感官标签（4.csv 原值，标准化连续量） |
| `data/clean/q1_mapped.csv` (DATA-0002) | 250×335 | DATA-0001 + 50 个 `g6__<label>`（训练折中点 CDF 派生的 0–6 参考分级；**只用于报告/敏感性，绝不作特征**） |
| `data/clean/q3.csv` (DATA-0003) | 250×285 | 与 DATA-0001 同列；`targetColumn = chem__ethanol..v.v.` |
| `data/splits/SPLIT-0001/{train,test,assignment}.csv` | 200/50 | `row` 为 0-based 原始行号；**Q2 只读 train.csv（作为依赖）**，绝不挂 split |
| `data/splits/SPLIT-0002/*` | 200/50 | 与 SPLIT-0001 同 assignment；**仅 Q1 实验挂载** |
| `src/target_columns.py` | 常量 | `FEATURE_COLS`(231), `TARGET_COLS`(50), `LOG10_CALIBRATED`(37), `LINEAR_CALIBRATED`(33), `UNCALIBRATED`(161), `FLOOR_COLUMNS`(142), `FLOOR_VALUE`, `DERIVED_SUMS`, `PHYSICAL_PARAMETERS`, `COMPOUND_CANDIDATES`(219), `DEFECT_COLUMNS`, `MISSING_COLUMNS`, `STYLE_COLUMN` |
| `data/clean/q2_chem_meta.json` | JSON | 每特征 `{name,kind,tier,corrIndex,corrLabel,floorCoded}`；`corrIndex` 指向 2.csv 的行列下标（231/231 已对齐） |
| `data/clean/q3_thresholds.json` | JSON | 缺陷阈值 mean/median、单位、存储尺度规则、floor 值 |
| `data/processed/q1_grade_params.json` | JSON | 每个目标：`trainValues`(200 个已排序标签)、`linearReferenceLow/High`、`linearSlope/Intercept` |
| `data/clean/q3_style_protocol.json` | JSON | 风格内 3 折 `foldByRow`、`excludedStyles=[Tripel,Kriek,Lambic]` |

缺失值：`chem__*` 有 73 个 NaN（9 列）。**只在训练折内**用中位数填，并对这 9 列加缺失指示（Q1）。

## 4. 本地测试 harness（复制即用）

```bash
cd /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
PACK=~/.dsh/profiles/desktop/node_modules/dsh-vibe-math/vibe-math-vmu/packs/modeling-contest/python
export MPLCONFIGDIR=$PWD/state/mplconfig
export MODELING_PROJECT_DIR=$PWD
export MODELING_EXPERIMENT_DIR=$PWD/state/devrun/q1
export MODELING_DATA_FILE=$PWD/data/clean/q1_mapped.csv
export MODELING_TRAIN_FILE=$PWD/data/splits/SPLIT-0002/train.csv
export MODELING_TEST_FILE=$PWD/data/splits/SPLIT-0002/test.csv
export MODELING_ASSIGNMENT_FILE=$PWD/data/splits/SPLIT-0002/assignment.csv
export MODELING_SEED=20261024
export MODELING_DEPENDENCIES="$(python3 - <<'JSON'
import json,os
p=os.getcwd()
print(json.dumps({k:os.path.join(p,k) for k in [
 "src/target_columns.py","src/q_common.py","src/q3_lib.py","src/q2_lib.py",
 "data/processed/q1_grade_params.json","data/clean/q2_chem_meta.json",
 "data/clean/q3_thresholds.json","data/clean/q3_style_protocol.json",
 "data/splits/SPLIT-0001/train.csv"]}))
JSON
)"
export PYTHONPATH=$PACK:$PWD/src
mkdir -p "$MODELING_EXPERIMENT_DIR"
$PY src/q1_candidate.py            # 换成你的脚本
ls "$MODELING_EXPERIMENT_DIR"
```

无 split 的脚本（Q2/Q3）去掉 `MODELING_TRAIN_FILE/TEST/ASSIGNMENT`，并把 `MODELING_DATA_FILE`
指向 `q2_raw.csv`/`q3.csv`；Q2 用 `dependency_path("data/splits/SPLIT-0001/train.csv")` 读训练行。

测试通过后把脚本路径、依赖清单、参数与预期 `emit_metrics` 键名报告给 Lead。

## 5. 交付给 Lead 的报告格式

```
脚本: src/qX_xxx.py
依赖(必须全部登记): [...]
注册参数: modelKind, datasetId, splitId(或 null), seed, args, params.evaluation, params.features
emit_metrics 键: [...]
输出文件: [...]
本地测试: 运行秒数 / 主指标值 / 是否两次运行完全一致
```
