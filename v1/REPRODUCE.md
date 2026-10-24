# REPRODUCE — 2026 MathorCup 赛道 A 复现说明

> 本文件描述**如何在本机从头复现**本文的全部可回读结果。所有数字都来自台账（`state/ledger.json`）
> 与 `experiments/`、`outputs/`、`figures/` 下的哈希化产物；论文正文用占位符渲染，不允许手抄。

## 1. 环境

| 项 | 值 |
|---|---|
| Python | `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python`（3.12.14） |
| 必需依赖 | numpy 2.3.5, pandas 2.2.3, scipy 1.18.1, scikit-learn 1.9.1, matplotlib 3.11.2, openpyxl 3.1.5 |
| 未安装 | 无 torch；条件 VAE 用 numpy/sklearn 手写（见 `src/q3_models.py`） |
| 中文字体 | 图内文字一律英文（环境无 CJK 字体），图注为中文 |
| LaTeX | `/usr/local/bin/xelatex`，CJK 字体 `Songti SC` / `Heiti SC`（`report/build.sh`） |

依赖安装（若需在新机复现）：
```bash
python -m pip install "numpy==2.3.5" "pandas==2.2.3" "scipy==1.18.1" "scikit-learn==1.9.1" \
  "matplotlib==3.11.2" "openpyxl==3.1.5"
```

## 2. 数据

原始附件已在 `data/raw/`（sha256 见 `data/raw/README` 与 `outputs/audit/audit.json` 的 `files` 段），
并在 `data/raw/imported/` 留有 inventory 登记的副本（10 个附件，台账 `RAW-*`）。

**不要用 Downloads 下的路径**：所有路径必须在项目目录内，否则 `modeling_data` 会以
`VMU_PACK_MODELING_CONTEST_PATH_ESCAPE` 拒绝（这是一条被验证过的门禁，不绕过）。

## 3. 一键复现顺序

```bash
cd /Users/baozhashizitou/Documents/MATHORCUP/A
P=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python

# 3.1 数据审计（题面-数据 12 项矛盾、缺失、log10 底数、2.csv 属性）
$P src/01_audit.py

# 3.2 尺度识别与 OAV（37 log10 / 33 linear / 161 unverified；LOD/2 755 格）
$P src/02_scale.py

# 3.3 清洗与建模表（250×284 = 3 键 + 231 特征 + 50 目标）
$P src/07_model_table.py
#   登记：modeling_data register-clean → DATA-0002（parentId=DATA-0001）

# 3.4 划分（台账主分割 SPLIT-0002 / 分层复核 data/splits/stratified）
$P src/04_split.py

# 3.5 维度对齐 + 标定（两份 canonical：SPLIT-0001 / stratified）
$P src/05_dim_map.py
$P src/06_calibration.py

# 3.6 Q1：基线 → 最终候选（含 model_bundle）
$P src/08_baseline_constant.py        # B0 常数基线（空特征, family=mean）→ EXP-0015
$P src/08c_q1_final.py                # 三路融合 + bundle → EXP-0025

# 3.7 Q2：共表达图 → 四方法 Top-3 与稳定性
$P src/q2_graph.py                    # → EXP-0003
$P src/q2_baseline.py                 # → EXP-0035（若存在）
$P src/q2_select.py                   # 注意：该步在本次交付中未登记为成功 EXP（见 §6）

# 3.8 Q3：风格条件生成 → 评估 → 迁移
$P src/q3_baseline.py                 # → EXP-0019
$P src/q3_models.py                   # 族选择（A/B/C）
$P src/q3_generate.py                 # → EXP-0022
$P src/q3_eval.py                     # → EXP-0024（含画像/缺陷/迁移）
$P src/q3_transfer.py
$P src/q3_figs.py                     # 9 张图

# 3.9 Q1/Q2 交付图
$P src/08d_figures.py

# 3.10 论文渲染与格式
$P - <<'PY'   # 或用 modeling_deliver render
PY
bash report/build.sh                  # md → tex → pdf
```

## 4. 台账操作（凡"登记"都必须在项目中执行，不能只跑脚本）

```text
modeling_project init / plan / select / freeze
modeling_data    inventory / profile / register-clean / register-split / run-script
modeling_experiment register → run（单次 ≤600s，本机 maxComputeConcurrency=1，需串行）
modeling_validate plan / run / independent-rerun / report
modeling_claim   create / link / check-stale
modeling_deliver figure / render / check / package
```

**实验产物契约（实测，见 `outputs/protocol/experiment_contract.md`）**：
- `modeling_contract` 只在 `modeling_experiment run` 的进程里经 `sys.path` 注入；
  统一桥接层为 `src/emit.py`（runner 外自动降级为写文件）。
- `emit_metrics` **只接受有限数值**（字符串/NaN/inf 会被具名拒绝）。
- `predictions.csv` = 单列合同（`row,beer,y_true,y_pred`，与 `test.csv` 行序对齐）；
  50 维长表必须叫 `predictions_long.csv`。
- 键名语义：`r2` = 单列 R²（pack 可复算）；`r2_50dim` = 50 维均值（科学主指标）。

## 4b. 预处理与数值稳定性（重要，易被复现时踩到）

协议字面的"折内中位数插补 + 标准化"在 1.csv 上会让 **ridge OOF R² = −0.9301 ± 1.1423**（15 折，39/50 维为负）：
根因是 **1.csv 混合尺度**（33 个线性浓度列跨 1e-9~1e3，与 37 个 log10 列混做折内标准化），
留出样本的标准化值会爆到几十。三条防护几乎等价：
winsorize 1%/99% → 0.2002；33 个线性列 log10 协调 → 0.1987；标准化后裁剪 ±8 → 0.1997。
本项目的最终管线 = 中位数插补 + 1%/99% winsorize + 标准化（融合模型另加 log10 协调）。
复现时**务必使用带防护的预处理**，否则会得到大负 R² 并误判为"模型无效"。

## 5. 关键随机性

| 位置 | 种子 |
|---|---|
| 划分 | 42（`StratifiedShuffleSplit` / 台账 register-split） |
| Q1 交叉验证 / 树模型 | 42 |
| Q2 bootstrap | 42（B=300；M2/M3 部分为 B=20，证据强度较低） |
| Q3 生成 / 评估 | 42（跨 seed 敏感性 42/7/2024/123/9） |

确定性路径复跑容差 **1e-6**；随机路径（Q3）以 `stochastic-stability` 单独判定（绝对极差 ≤0.05）。

## 6. 已知未完成与不可复现项（必须如实阅读）

1. **Q2 的 Top-3 选择未登记为成功 EXP**：`outputs/q2/metrics.json` 等产物来自 run-script（878s），
   未进入 `modeling_experiment`，因此 Q2 无 candidate、无法 `select`，稳定性结论只基于跨方法 Jaccard（FAIL）。
2. **Q3 的 `independent-rerun` FAILED（VAL-0012）**：`q3_eval.py` 固定 `SEED=42` 且读取被重写的共享产物
   `outputs/q3/seeds/*`，复跑输入不一致（`profile_spearman` 0.4073→0.8935）。
3. **稳健性计划 ROB-0001/0002/0003 均未执行**：`robustness-plan-execute` 需要"真正改变了输入"的
   ≥2 个实验；现有实验 seed/split/params 相同，被门禁具名拒绝（这是正确行为，未强推）。
4. **holdout 复用超限**：SPLIT-0002 被 17 个 succeeded 实验使用（阈值 3）→ 留出集已部分变成调参集，
   这是本次交付最重要的方法学缺陷。
5. **Q1 的 `baseline-required` 未满足**：TGT-0001 声明了 labelRule，但缺"直接规则基线"实验。
6. **数据边界**：161 列尺度未验证、755 格 LOD/2 删失、4.csv 非单位方差（真实 0–6 等级不可辨识）、
   holdout 缺 West Flanders ale（7 样本）、Kriek/Lambic/Faro 小样本。

## 7. 产物地图

```text
problem/        题面逐字稿、questions.yaml、12 项核对
data/raw/       原始附件 + imported 副本
data/clean/     model_table.csv(250×284), features_log, targets_z, concentrations, oav,
                missing_flags, fields_model.json, DATA_DICTIONARY.md
data/splits/    SPLIT-0001, SPLIT-0002, stratified/
src/            00–08d（Lead 协议层）+ q1_* q2_* q3_*（建模者）+ 09_independent_rerun（reviewer）
experiments/    EXP-0001..0040（含 failed/cancelled 记录，不覆盖）
outputs/        audit/ protocol/ data/ q1/ q2/ q3/ review/ probe/
figures/        Q1 6 张、Q2 2 张、Q3 9 张
report/         paper.md（源）、rendered.md（渲染）、paper.tex, paper.pdf, build.sh
state/          ledger.json（唯一真相）+ 各次脚本/实验日志
```
