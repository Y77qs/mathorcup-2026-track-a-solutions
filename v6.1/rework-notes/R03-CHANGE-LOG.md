# R03 修改记录（v5.1 必改项 → 实际改动、证据与未解决项）

日期：2026-10-26。项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`。
协议：`configVersion 2`（`evaluation.tuning` 明确为 3 重复 × 3 外折、内 3 折、种子 20261025-27，按 `tasting_category_fine` 分层），protocol sha `215d0941a803…`。
本文件只列**真实执行**的改动与证据；未执行项单列。绝不把计划写成结果。

## 0 环境与预检

| 项 | 结果 |
|---|---|
| probe 重跑 | 2026-10-26T07:41:17Z，Python 3.12.14，numpy 2.3.5 / pandas 2.2.3 / scipy 1.18.1 / sklearn 1.9.1 / matplotlib 3.11.2 / openpyxl 3.1.5 / sympy 1.14.0 |
| 独立 import+计算核验 | 9/9 通过（`SCRIPT-0005`，`state/env-verify/v6-env-verification.json`） |
| run-control 限制 | 2.8.10 的 `requiredModules` 比较 `modules[name]===true`，而 probe 存版本字符串 → 该检查无法启用；本轮**未 begin**（`RUN=0`），如实记为限制 |
| requestAdmission（实测） | `inputUpperBound=1048576`、`maxOutputTokens=256000`（来源：本会话 `request/context`、`request/header`，provider `deepseek-official`、model `deepseek-flash`） |
| 对账说明 | `.rework/R00-fork-reconciliation.md`；`forkOrigin` 未改；字节级哈希不可复验（已披露限制） |

## 1 论文格式（v5.1 §二）

**未做**。本轮不动论文/tex/pdf；`report/revised-20261025/support/header.tex:20-22` 仍生成页眉与连续页码，A 链 `src/build_paper.py` 仍无 `\maketitle`/页码重置。已确认 v5.1 描述的“页眉 + 正文首页页码 3”属于 B 链 PDF，不是 A 链。验收需在后续重编 PDF 后做。

## 2 Q3 生成与迁移（v5.1 §三）

实现：`src/q3_fix.py`（73818 B，sha `ae599242db4b`）、`src/q3_transfer_fix.py`（61038 B，sha `525d64946313`）。

| v5.1 条目 | 改法 | 证据 |
|---|---|---|
| 非负实际浓度 | 33 个 linear 校准列为硬下界（投影），log10 列允许负 | `EXP-0042/0050` `n-linear-negative-design=0`（旧 142 格/40 行/22 列） |
| raw/design 分离 | 先写 `samples_raw.csv` 再写 `samples.csv`，两套都登记 | `EXP-0042` 输出含 6 个 CSV |
| t2n 化学列不增 | 约束改落在 `chem__X.E..2.nonenal`，不再用感官代理 | `EXP-0043` `nonincrease-rate-X.E..2.nonenal=1`；化学列逐行 max(new−source)≤1.1e-16 |
| PCA 中心化 | 拟合与评分共用同一 `z_mean`，并断言目标均值自距 | `EXP-0043` `target-mean-self-distance=4.75e-16`（旧 0.6655） |
| 目标/梯度一致 | 凸 QP + 解析梯度，有限差分交叉验证 | `EXP-0043` `objective-gradient-fd-max-abs=4.5e-9`；198/198 optimal，primal≤9.99e-9、dual≤3.39e-10 |
| 逐外折调参 | 每外折内独立选 (κ,κ_R)，禁止跨折平均回填 | `EXP-0042/outputs.json` `per_fold_tuning` 各折不同 |
| 经验 V/U | 主比较用经验 V，U 保留符号不截零 | `EXP-0042` `energy-distance=0.8840`、`energy-U-signed=+1.1139` |
| 多样性与复制 | 平均非对角距离、精确复制率、最近邻、贴边比例 | `diversity=19.736`、`duplicate-share=0`、`edge-fraction=0.1199` |

**必须同时读的负面/边界结论**：设计谱 constraint-satisfaction=1.000 是**投影构造不变量**，且伴随大比例边界夹断（508/750 DMS 恰=17.25、361/750 双乙酰恰=0.29925、46/750 4VG 恰=阈值）；能量 V 0.8840 **劣于**同风格重采样参照 0.8137；t2n 感官代理仍上升 360/750，另有 146/750 高于风格上界。全部写入 `CLAIM-0028/0029`。

## 3 Q2 名称对齐与稳定性（v5.1 §四）

实现：`src/q2_fix.py`（83579 B，sha `fd010c4fc691`）。

| v5.1 条目 | 改法 | 证据 |
|---|---|---|
| 名称双向对齐 | 化学行按 `corrLabel/name`、感官列按显式字典；断言一对一 | `EXP-0041/outputs.json` `mapping.assertions` M1–M6 pass |
| 二次索引 | 打分矩阵强制 (231,50)，禁止 219 行矩阵用 231 空间下标 | `_guard_matrix` |
| 感官尾三列错位 | 按名称取列（Carbonation/Aftertaste/Body 不再错位） | 对齐后同源对照 0.445051→**0.921018** |
| 类别字典 | single_compound 216 + element_or_index 3 + physical 7 + derived 5 | `n_strict_candidates=216`；严格榜无 iron/protein/理化/汇总 |
| 严格/扩展分表 | `strict_top3.csv`（150 行）与 `extended_top3.csv`（150 行） | 同名 `*_by_method.csv` 600 行 |
| 符号一致性/替代项 | bootstrap 内正号比例、模块替代、全局次优 | `sign_stability_mean=0.7226`；`pi_below_0.5_count=1263/1800` |
| 重新 bootstrap | 每重复 500 次、每次重做插补/图/回归 | `bootstrap_pi.csv` 每重复 300k 行 |

**协议诚实化**：独立审查 F1 指出原 claim 把 Q2 写成嵌套 CV —— 实际是**固定 200 行训练集 + 3 种子 × 500 次分层 bootstrap，无 outer/inner 折、无 OOF**；已由 `CLAIM-0027` 更正并保留 `CLAIM-0026` 为 superseded。

## 4 Q1 对照、成绩与口径（v5.1 §五）

实现：`src/q1_fix.py`（56723 B，sha `2fb4b4b09216`）、`src/q1_baseline_fix.py`。

| v5.1 条目 | 改法 | 证据 |
|---|---|---|
| 真普通 Ridge | γ=0、r=50 显式拟合 | `EXP-0038/0048` `mae_ridge0=0.366662` |
| 图 Ridge / 图低秩 | γ>0 独立拟合；低秩 r∈{3,6,10} 内层选参 | `mae_graph_ridge=0.366411`、`mae_graph_lowrank=0.359292`（9/9 折选 r=6） |
| 等价性 | r=50 且 γ=0 必须与 ridge 逐折一致 | `eq_ridge_rank50_max_abs_diff=4.0e-15` |
| 逐行 OOF | 750 行（3×250）OOF，每行只由未见它的模型预测 | `EXP-0048/predictions.csv`（750×106）+ `oof_long.csv`；独立复核 fold 归属 750/750 |
| A/F30 主指标 | `mae` = A/F30 等权池化；50 维作副指标 | `mae=0.359292`、`mae_all50=0.350504`、`skill_af30=0.097659` |
| 截距口径 | ridge/graph/lowrank 同一公式 `ȳ−z̄B` | `src/q1_fix.py` 统一路径 |
| clip ±8 披露 | 仍为 `q_common.py:165-167` 的历史处理；新代码不依赖该裁剪 | 未在论文披露（论文层本轮不做） |

**结论口径**：图惩罚本身几乎无增益（graph ridge − ridge = 0.00025），增益来自低秩约束（−0.007371，约 2.0%）；折间波动 0.34499–0.37313 大于模型间差距，故不作“稳定优势”断言。旧 0.346567 属旧 50 维单次留出口径，不可相减。

## 5 数据、复现与硬编码（v5.1 §六 + 工程缺口）

| 项 | 改法 | 证据 |
|---|---|---|
| 数据字典与尺度 | `src/r00_constants.py` 从真实表头与 8.xlsx 数值身份重算 37/33/161，写 `data/processed/v6_constants.json` + `v6_feature_dictionary.csv` | `SCRIPT` 回执；与 `prepare_base.identify_scale` 逐列一致 70/70 |
| 校准冲突双口径 | strict `isclose(atol=rtol=1e-7)`（存储尺度）**80 格/24 酒/32 列**；实质 rel>1% **79 格**；另记字面不换尺度会得 8532 格（仅尺度变换） | `outputs/audit/v6/{cell_provenance,conflicts_strict,conflicts_substantive}.csv` + `calibration_conflict_summary.json` |
| 状态字典 | 755 零编码 / 142 地板列 / 6807 地板格 / 73 缺失，与登记值一致 | `outputs/audit/v6/state_counts.json` |
| legacy recheck | 7/7 旧数字独立重现（142/40/22、6/11、0.445051、0.921018、0.604487、U/V） | `outputs/audit/v6/legacy_recheck.json` |
| 契约 oracle | 6/6：图低秩=解析下界、QP 与活跃集一致、能量玩具、梯度有限差分、切分不变量、Ridge 等价 | `outputs/contracts/v6/contract_tests.json` |
| 不可变切分 | `src/r00_build_splits.py` 生成 `data/splits/NESTED-CV-1/{splits.csv,manifest.json}`（2250 行） | `SCRIPT-0004` |
| target_columns 生成依赖 | 新增 `v6_constants.json` 生成器（表头驱动 + 输入 sha），新代码只读生成物，不在 runner 内覆写源码 | `src/r00_constants.py` |
| 硬编码旧 EXP ID | `src/ablation_summary.py`、`src/headline_audit.py`、`src/make_paper_figures.py` 改为必须显式提供 `MODELING_EXPERIMENT_IDS`，缺失/不符即具名失败（`src/v6_experiment_ids.py`） | 三文件均可编译；无 env 时具名报错 |
| 干净目录复现 | `src/r03_reproduce.py`：全新目录仅含冻结代码+输入，重跑 Q1 与 Q3 迁移，主指标 delta=0 | `SCRIPT-0007`、`state/repro-clean/repro_manifest.json` |

## 6 实验、验证与结论（真实 ID）

| 用途 | ID | 关键数字 |
|---|---|---|
| Q1 基线 | EXP-0038 | mae(A/F30)=0.398177 |
| Q1 候选 | EXP-0039 | mae=0.359292；ridge0 0.366662；graph_ridge 0.366411 |
| Q1 冻结源 / 复跑 | EXP-0048 / EXP-0053 | 同上，复跑 delta=0（VAL-0048） |
| Q2 候选 | EXP-0041 | topk-jaccard 0.20911；对齐后同源 0.921018；严格宇宙 216 |
| Q3 生成 / 冻结源 / 复跑 | EXP-0042 / EXP-0050 / EXP-0054 | constraint-satisfaction 1.000（构造）；V 0.8840；U +1.1139；负浓度 0 |
| Q3 迁移 / 冻结源 / 复跑 | EXP-0043 / EXP-0051 / EXP-0055 | 不增率 1.000（构造）；198/198 optimal；自距 4.75e-16 |
| 稳健性扰动 | EXP-0056 / EXP-0057 | energy-distance 0.877784 / 0.876453（相对极差 0.15%），但计划未执行（见下） |
| 验证 | VAL-0044/0045/0047/0048/0049/0050/0051/0052 | leakage / baseline-compare / simulation-seeds / independent-rerun |
| 结论 | CLAIM-0023（Q1）、CLAIM-0027（Q2）、CLAIM-0028（Q3 生成）、CLAIM-0029（Q3 迁移） | 全部 metric 引用可解析 |
| 独立审查 | REV-0040（independent_context，非 root） | verdict=findings；F1/F3/F4/F7 已修复并 resolve |

## 7 稳健性（后续轮次已执行，更新于本轮）

三项预注册计划**均已真实执行并通过**（扰动 = seed block，各 2 个独立实验，均带 runner 验证的 `seed-receipt.json`）：

| 计划 | 实验对 | 指标值 | 相对极差 | 判定 |
|---|---|---|---|---|
| ROB-0004（Q1） | EXP-0066 / EXP-0067 | mae 0.354224 / 0.362434 | 0.023178 | ≤0.05 passed |
| ROB-0005（Q2） | EXP-0064 / EXP-0065 | topk-jaccard 0.210333 / 0.207333 | 0.014263 | ≤0.10 passed |
| ROB-0006（Q3） | EXP-0062 / EXP-0063 | energy-distance 0.877784 / 0.876453 | 0.001517 | ≤0.05 passed |

实现方式：新增 `src/seed_receipt_wrapper.py`（不改冻结脚本），调用 `modeling_contract.seed()` 后执行冻结脚本 `main()`；seed-receipt 通道打通前有 4 次真实失败（EXP-0058/0059/0060/0061），全部保留。结论由 **CLAIM-0030** 承载，limitations 明确 n=2、非置信区间、未覆盖 λ/κ 参数扰动。

## 8 未完成 / 未解决（不得写成通过）

1. **稳健性执行**：已完成（见第 7 节，ROB-0004/0005/0006 均执行并通过）。未做的只有计划里的第二类扰动：Q1 的 λ×0.5/×2、Q2 的 bootstrap 次数 500→200、Q3 的 κ 网格（这些需要脚本提供对应参数入口，冻结脚本没有）。
2. **Q2 验证**：已完成。审计源 **EXP-0071**（带 231 列 features + `freezeSources` + 全部输入文件）→ **VAL-0053 leakage passed**、**VAL-0054 independent-rerun passed**（EXP-0072，21 指标 delta=0）；Q2 选择为 **validated**（MODEL-0047）。此前五次快照失败全部保留（EXP-0049 FileNotFound、EXP-0052/0068 非 ASCII 路径 EPERM、EXP-0069 快照缺被包装脚本、EXP-0070 包装器比较缺失原路径报错），解法是把对齐表复制为字节相同的 ASCII 副本并给包装器加 `--patch-align-to`。剩余不可消除项：holdout-metrics 结构性不适用；VAL-0054 的磁盘目录未落盘（包行为）。
3. **质量平面**：38 项中 23 passed / 5 failed / 5 needs_review / 5 n/a / 0 stale。失败项：QC-0020（论文仍引用 6 条已退休 claim）、QC-0022/0024/0026（稳健性未执行）、QC-0033（历史 EXP-0017/0018/0026/0035/0036 无 features 清单，不可 retrofit）。needs_review：QC-0002（两条 requirement 记 insufficient_data）、QC-0003（目标变换待独立推导复核）、QC-0036/0037/0038（嵌套 CV 无权威 test truth）。
4. **论文层**：paper/tex/pdf、FIG、frozen、render/artifact 全未更新；v5.1 格式必改项未做。
5. **run-control**：从未 begin（`RUN=0`），requestAdmission 未在受控 run 中登记。
6. **review 未决项**：REV-0040 仍有 F2/F5/F6/F8/F9（major）与 F10–F12（minor）未 resolve。
