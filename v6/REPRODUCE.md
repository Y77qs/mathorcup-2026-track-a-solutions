# 复现说明（REPRODUCE.md）——v6 DRAFT 交付链

项目目录（本文件只描述本项目，`my-new-contest-v3` 仅为只读来源）：
`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`
项目 id：`beer-2026-a-v3`；语言 `zh-CN`；题型 `mixed`；主指标 `mae`（minimize）。
台账：`state/ledger.json`（业务 `revision` 与 `runtimeRevision` 分开；比较内容与 SHA，不比较 revision）。

> 原则：**正文不手抄任何指标**。`report/paper.md` 只写 `{{metric:EXP-xxxx:key}}`、
> `{{claim:CLAIM-xxxx}}`、`{{figure:FIG-xxxx}}` 以及由 `src/paper_tables.py` 生成的表格块；
> 数字全部由 `modeling_deliver render` 从台账解析。台账里没有的数不存在于可交付的论文里。

## 1 环境

```
Python 3.12.14  /Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
numpy 2.3.5 · pandas 2.2.3 · scipy 1.18.1 · scikit-learn 1.9.1
matplotlib 3.11.2 · openpyxl 3.1.5 · sympy 1.14.0 · pypdf 6.10.0
pandoc 3.11 · xelatex（TeX Live 2025）· sips（macOS，仅用于把 PDF 单页光栅化做目检）
```

配置：`contest.yaml`（`acceptedVersion=2`，raw sha256 `728811fc…c9e5c3733`，protocol sha256
`215d0941a803…`，`state=in_sync`）；`problem/statement.md`（题面，sha `c8fe921b…`）。

## 2 数据与划分（台账登记，含 SHA256）

| 数据 | 路径 | 说明 |
|---|---|---|
| DATA-0001 | `data/clean/q2_raw.csv` | 问题二基础表（231 化学列 + 感官/风格列） |
| DATA-0002 | `data/clean/q1_mapped.csv` | 问题一评估视图（50 感官目标 + 231 特征 + 训练折 0–6 参考等级） |
| DATA-0003 / DATA-0004 | `data/clean/q3.csv` | 问题三风格视图（同字节的两个登记视图；DATA-0004 `targetColumn=overall` 仅用于泄漏审计，不作为生成器输入） |
| SPLIT-0001 / SPLIT-0002 | `data/splits/<id>/{train,test,assignment}.csv` | `random-holdout`，seed 20261024，testFraction 0.2，positional 行 ID 契约。**注意**：SPLIT-0002 的 holdout 曝光已达 3/3（`contest.yaml` 的 `maxHoldoutReuse`），确认轮不再使用它；复现时不得再次曝光该 holdout。 |

原始附件保留在 `data/raw/imported/`（导入时逐一核对 SHA256）；清洗版本由 `register-clean` 登记，父版本可追溯。

**问题一的评价协议不是 holdout**：train-only 3×3×3 嵌套交叉验证（3 次重复 × 3 外层折 × 每折 3 内层折，
风格分层），因此 `split-integrity`/`holdout-metrics` 两项原生检查**结构性无法执行**——这是真实未通过项，
本文与交付说明均如实保留，不改写为通过。问题二只用注册的 200 行训练集（50 行留出不参与拟合/评价）。
问题三使用固定 3 折风格内留出。

## 3 实验与证据（确认轮白名单）

| 范围 | 主实验 | 稳健性实验 | 主 claim | 稳健性 claim | 验证 |
|---|---|---|---|---|---|
| Q1 预测 | EXP-0073（候选 MODEL-0048）、EXP-0074（中位数基线） | EXP-0100/0101/0102 | CLAIM-0056 | CLAIM-0059 | VAL-0063/0064/0065 |
| Q2 关联 | EXP-0075（MODEL-0050） | EXP-0089/0090/0091 | CLAIM-0041 | CLAIM-0052 | VAL-0056/0057 |
| Q3 生成 | EXP-0079（MODEL-0053） | EXP-0092/0093/0099 | CLAIM-0054 | CLAIM-0053 | VAL-0066/0068 |
| Q3 迁移 | EXP-0080（MODEL-0054） | EXP-0095/0096/0097 | CLAIM-0055 | CLAIM-0047 | VAL-0067/0069 |

当前 selection：Q1=MODEL-0048（`provisional`）、Q2=MODEL-0050（`validated`）、Q3=MODEL-0053（`provisional`；
Q3 是“生成 + 迁移”双对象，单一 `selectedModelId` 只覆盖生成侧，迁移侧为 MODEL-0054，见 `.rework/VALIDATION-SELECTION-HANDOFF.md`）。

独立复算（不属于原生 VAL）：`src/q3_cert_audit.py`（198 份 QP 证书全最优，`outputs/q3/qp_cert_audit.json`）、
`src/q3_zspace_recompute.py`（z 空间 396 行重算）。稳健性产物：`src/r05_robustness_products.py`。

## 4 从正文源到 PDF 的完整链路（本 DRAFT 交付实际执行）

```bash
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6
cd "$P"

# 4.1 表格（19 张：正文内联 15 + 支撑材料 4）——输入是台账实验产物，输出 md/csv + INDEX.json
$PY src/paper_tables.py --verify          # 期望：19/19 complete, 0 problem(s)

# 4.2 图（9 张 active，来源实验见台账与 src/make_confirmatory_figures.py）
$PY src/make_confirmatory_figures.py --all

# 4.3 源一致性（只读）：裸编号 / 退休对象 / 占位符可解析 / 表块四方 sha
$PY .rework/check_paper_consistency.py    # 期望：OK: 0 violations

# 4.4 正式 render（台账 → 正文；本批为 RENDER-0016）
#     输入 report/paper.md，输出 report/rendered.md，refs report/rendered.refs.json
modeling_deliver {action:"render", input:"report/paper.md", output:"report/rendered.md", allowStale:false}

# 4.5 正式构建（与预览同一 builder/header/template/显示参数）
$PY src/build_paper.py --build --pdf --source report/rendered.md --outdir report \
    --allow-report-output --number-sections --wide-tables wrap --no-caption-ids
# 期望日志：Output written on paper.pdf (30 pages).  tex 内嵌 source/pandoc/header/template/builder 五个 sha

# 4.6 产物绑定（ART 记录绑定 render id 与产物 sha）
modeling_deliver {action:"artifact", format:"tex", renderId:"RENDER-0016"}   # report/paper.tex
modeling_deliver {action:"artifact", format:"pdf", renderId:"RENDER-0016"}   # report/paper.pdf

# 4.7 PDF 结构与逐页检查（本批自带只读脚本）
$PY .rework/pdf_audit.py report/paper.pdf --json report/pdf-audit.json --textdir report/text
# 期望：pages=30、9 图、表 1–15、PDF 1–3 无页码、正文页码 1 起于 PDF 第 4 页、页眉区无文字
```

`report/BUILD-INPUTS.json` 记录 builder / header / template / 4 个输入与 2 个输出的 sha256 与字节数；
`report/paper.tex` 首行 `% build=...` 同时内嵌 source-sha256、pandoc-input-sha256、header/template/builder sha。

## 5 本 DRAFT 交付的关键 SHA（2026-10-27）

| 对象 | 值 |
|---|---|
| `report/paper.md` | `95fd30f0f1908a2bb6575dbf47a2a260f5dec00e733c699b9369821503897416` |
| `report/rendered.md` | `c5cf631d327df4cedee02368fc480af5120e9dcd9937a6d4169197d6e2dd6245`（RENDER-0016） |
| `report/paper.tex` | `e874741b348e191c01bf19a3884cf59c412b528ced996059626d9cfeef842591`（ART-0007） |
| `report/paper.pdf` | `952b73e341d6411ae28bd658045af1a53edf22824763570801a8a0e01076e73e`（ART-0008，30 页） |
| `report/tables/INDEX.json` | `6a78f7ce8d0da89451efbe2de925e453ceccf6412513f8ef313b0452e9309605` |
| `report/evidence_manifest.json` | `db5980ed5981189dd4d824371905dee56e66501b4df84adbb5e347e9ec13d561` |
| `src/build_paper.py` | `40b0022f1fb964abd7bc525619415017098691b52ab75181cc50aef0572b8fe3` |
| `src/build/header.tex` | `0d35a9640f355225d95df79ac4512c7b2eb670ed0c9bbda69bd9e5a634cd3926` |
| `src/build/template.tex` | `b1140b188bdc5e1864c6a052a243f991d16fd0661db4078e5cfe69322ebfa042` |

## 6 已知限制（与论文附录 B.3 / 附录 C 一致，不得当作已通过）

1. **freeze 被工具拒绝**（`VMU_PACK_MODELING_CONTEST_GATE_STAGE_SKIPPED`：Q1/Q2/Q3 多项 required 验证检查未通过），
   台账 `frozen` 仍是 2026-10-24 的旧身份（configVersion=1、6 条已退休 claim、29 张旧图、MODEL-0004/0012/0013）。
   本 DRAFT 的 RENDER-0016 因此携带的是该 legacy 冻结身份，**不是**“冻结后的正式 render”。
2. Q1 `split-integrity`/`holdout-metrics`、Q3 原生 `optimization-feasibility`/`optimization-objective` 结构性不可满足；
   Q3 `leakage` 因实验未声明 feature list 被具名拒绝。因此 **Q1/Q3 selection 只能是 `provisional`**。
3. `QC-0033` failed（EXP-0017/0018/0026/0035/0036 缺 input feature manifest）——历史结构，禁止 retrofit。
4. 无注册 split 的实验（含全部确认轮 EXP-0073..0102）其 `metric-recompute` 原生检查**没有权威测试真值**，
   保持 `needs_review`；论文不声称这些指标经过原生复算。
5. `REQ-0004/0005/0007` 保持 `insufficient_data`（多阈值迁移情景/Pareto 前沿缺当前证据；论文门禁未通过；图注—结论逐项一致性仍属人工判断）。
6. 图 1/2/9 图内英文标注在低分辨率下偏小；摘要与正文按台账全精度呈现 17 位浮点（可追溯、可读性差）。
7. 附录 C 的说明表未编号、正文用内部表 id（如“表 q3-quality”）交叉指代、目录“摘要”条目无页码——三项为已披露的 minor。

## 7 复现注意

- 每次重跑实验都会产生新的 `EXP-xxxx`，旧记录不覆盖；重跑用新 id + `rerunOf`。
- 重新 render 会产生新的 `RENDER-xxxx`；旧 render 不得冒充新 render。`artifact` 必须显式指定 `renderId`。
- 本批未向 `my-new-contest-v3`（SOURCE）写入任何文件；所有新增/修改都在本项目内。
- **不自动提交到任何竞赛平台**：`contest.yaml` 的 `delivery.contest` 为 `null`，未声明官方提交要求，故提交动作记为 skip，由人工完成。
