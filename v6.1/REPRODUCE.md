# REPRODUCE.md — v6 复赛修正后的复现说明（现状，2026-10-27）

项目：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`（项目 id `beer-2026-a-v3`）
协议身份：`contest.yaml` acceptedVersion **2**，`configState.state = in_sync`，
`configRawSha256 = 728811fc888fef0b4d16b0513be5bac87ab5c420f5809861c14052cc9e5c3733`，
`configProtocolSha256 = 215d0941a803e1fc4420fa9c580834b41c5cf6a87f1e1b0a1d6a64fd45947abc`。

> 本文件只写**本轮实际跑过并留在台账里的命令、输入与读数**。历史轮次（先导轮、v5、v5.1）的
> 脚本与数值保留在 `experiments/` 与台账历史中，不作为当前证据。

## 1 解释器与环境

```sh
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python   # Python 3.12.14
PACK=~/.dsh/profiles/desktop/node_modules/dsh-vibe-math/vibe-math-vmu/packs/modeling-contest/python
export MPLCONFIGDIR=$PWD/state/mplconfig
export PYTHONPATH=$PACK:$PWD/src        # modeling_contract / q_common 的导入路径
```
已实测模块版本：numpy 2.3.5、pandas 2.2.3、scipy 1.18.1、sklearn 1.9.1、matplotlib 3.11.2、openpyxl 3.1.5。
pdf 构建需要 xelatex（本机已装；`src/build_paper.py --build --pdf` 会真实编译并报告 `[PASS] pdf`）。

## 2 冻结输入（sha256 与台账登记值一致）

| 文件 | sha256 |
|---|---|
| `data/clean/q3.csv`（DATA-0004） | `4948a908ab943d02591e791533fe70c8c962d7c506bef77e6ad0f1bf8e732a86` |
| `data/clean/q2_raw.csv`（DATA-0001，与上同字节视图） | `4948a908ab943d02591e791533fe70c8c962d7c506bef77e6ad0f1bf8e732a86` |
| `data/clean/q1_mapped.csv`（DATA-0002） | `2e317968fa68b7c2b43978d79222eb332a43d1d691c12b36622f22654fbfb30b` |
| `data/splits/SPLIT-0001/train.csv` | `bf6bad1d336c3e635d5f15f5bf145718551755663219a3ee148d5c9763f7c954` |
| `data/splits/NESTED-CV-1/splits.csv` | `8ad8e75dcedcb2c1336cf4db5caa9542f6827c557e6588344d36fbf2ae41ad81` |
| `data/splits/NESTED-CV-1/manifest.json` | `0353e7da54e9dbed5a6f1864d336202c7416a2e65607f5f4e220a4a1eb24b4a4` |
| `data/clean/q3_style_protocol.json` | `bac88751b98512a96cc6cd6e5e6d07f53dfd8c077f097ab3ee1e0ebb5026daf8` |
| `data/clean/q3_thresholds.json` | `4e593b48855f29176478b5f46abdc5823bd24809134670f266139947d86d8f61` |
| `data/raw/imported/415709ac10f2f730-2.csv`（附件 2 相关矩阵） | `415709ac10f2f730d31f249bd6ac108250bdfbfd62e0055f4d8db9b41ec9cc4c` |
| `data/raw/imported/a55004fb0390299a-6.csv`（同源参照表） | `a55004fb0390299a5c8089f0c37d3bfc006e7049963c84d7d9652affabe614ae` |
| `data/processed/sensory_name_alignment.csv` | `971a0e47e1b3651e27b95d49a35bd24098f0f0975b78cafca2e414640d642912` |

## 3 确认轮实验（台账真实 id）

| 问 | 实验 | 脚本 / 参数 | 种子 | 实测耗时 | 主指标（台账 metrics.json） |
|---|---|---|---|---|---|
| Q1 | EXP-0073 | `src/q1_fix.py --repeat all` | 20261025 | 2.5s | A/F30 OOF MAE `0.35929156588219174` |
| Q1 | EXP-0074 | `src/q1_or_baseline`（训练折中位数基线） | 20261025 | 0.3s | `0.39817732837288883` |
| Q2 | EXP-0107 | `src/seed_receipt_wrapper.py --target src/q2_fix.py --patch-align-to data/processed/sensory_name_alignment.csv --repeat all` | 20261025 | 80.8s | `topk-jaccard 0.2091111111111111`、`sign_stability_mean 0.9816877777777778`、`sign_stability_legacy_mean 0.7225544444444444` |
| Q3 生成 | EXP-0109 | `src/q3_fix.py --repeat all` | 20261025 | 70.8s | `constraint-satisfaction 1`、`energy-distance 0.8726874826148657`、`energy-V-raw 15.99994601104919` |
| Q3 迁移 | EXP-0110 | `src/q3_transfer_fix.py --repeat all` | 20261025 | 7.4s | `nonincrease-rate 1`、`transfer-energy 2.0798861351916886`、`qp-solves 198` |
| Q2 ROB（ROB-0015） | EXP-0125 / EXP-0126 / 补充 EXP-0131 | `src/robustness_wrapper.py --target src/q2_fix.py --set ALIGN_CSV="data/processed/sensory_name_alignment.csv" --repeat {0,1,2} --reps 500` | 20261025 / 20261026 / 20261027 | 29–38s | jaccard `0.2103333333333333` / `0.20733333333333334` / `0.20966666666666664` |
| Q3 生成 ROB（ROB-0016） | EXP-0127 / EXP-0128 / 补充 EXP-0132 | `src/robustness_wrapper.py --target src/q3_fix.py --repeat {0,1,2}` | 同上 | 20–27s | energy-distance `0.8639056831482218` / `0.8702681221486325` / `0.8838886425477438` |
| Q3 迁移 ROB（ROB-0017） | EXP-0129 / EXP-0130 / 补充 EXP-0133 | `src/robustness_wrapper.py --target src/q3_transfer_fix.py --repeat {0,1,2}` | 同上 | 3–4s | nonincrease-rate `1` / `1` / `1` |
| Q1 ROB（ROB-0011，未变） | EXP-0100 / 0101 / 0102 | `src/robustness_wrapper.py --target src/q1_fix.py ...` | — | 1–2s | mae `0.35422354618559243` / `0.36243390816790516` / `0.35763459908881995` |

实验由 runner 启动（`cwd=experiments/EXP-xxxx/`，只导出 `MODELING_*` 与登记依赖）；本地等价环境见
`docs/AGENT-BRIEF.md` §4。各实验的 `inputs/` 下是冻结快照，`metrics.json`/`outputs.json`/`result.json`
是产物；`solver_certificates.jsonl`、`transfers.csv`、`samples*.csv` 等实体文件留在实验目录。

## 4 干净目录复现（delta = 0）

```sh
MPLCONFIGDIR=$PWD/state/mplconfig $PY src/r03_reproduce.py
```
本轮实测：`ok: true`，runId `20261027-212317`（只复现四个实验角色的数值指标；不复现 rendered.md/paper.tex），四个角色全部通过且 `maxAbsDelta = 0`：
`q1_generation_lowrank`（EXP-0073）、`q2_consensus_top3`（EXP-0107）、`q3_generation`（EXP-0109）、
`q3_transfer_qp`（EXP-0110）。清单：`state/repro-clean/repro_manifest.json`。
脚本会把 `src/*.py`、`data/clean/{q1_mapped,q3}.csv`、`q3_{style_protocol,thresholds}.json`、
`NESTED-CV-1/splits.csv`、`SPLIT-0001/train.csv`、`q2_chem_meta.json`、两份导入附件与对齐表复制到
干净目录，再从干净目录运行；任何绝对路径依赖都会在那里失败。

## 5 下游产物 → 论文 → 交付的回执链

```sh
$PY src/r05_scope_numbers.py            # outputs/q3/style_and_displacement_scope.json
$PY src/r05_robustness_products.py      # outputs/{q1,q2,q3}/robustness_*_confirmatory.json + outputs/robustness/INDEX-confirmatory.json
$PY src/r07_evidence_manifest.py        # report/evidence_manifest.json
$PY src/paper_tables.py --build         # report/tables/*.md|csv + INDEX.json（19 张）
$PY src/paper_tables.py --verify        # 19/19 complete, 0 problem(s)
# 台账动作（由主控执行）：modeling_deliver render → build_paper → artifact(tex/pdf) → check → package
$PY src/build_paper.py --build --pdf --outdir report --allow-report-output
$PY .rework/check_paper_consistency.py  # 0 violations
$PY .rework/pdf_audit.py report/paper.pdf --json report/pdf-audit.json
```

本轮关键产物 sha256（逐字节与磁盘一致）：
`report/paper.md b319ccd9…`、`report/rendered.md 59c731bc…`（RENDER-0022）、
`report/paper.tex 3286dde0…`（ART-0021）、`report/paper.pdf 31d5e72d…`（ART-0022，3,111,844 B，38 页，正文 30 页）、
`report/tables/INDEX.json 3fd9756f…`、`report/evidence_manifest.json 7dbd3a63…`。

## 6 已知边界（不得当成可复现/已通过的部分）

- PDF **字节**不可复现（xdvipdfmx 非确定性）；可复现的是 `rendered.md`、`paper.tex` 与 PDF 的文本/页面结构。
- `outputs/q3/zspace_recompute.json` 仍是旧 EXP-0080 代码的产物（代码/数据 sha 已变），本轮**未引用**；
  如需该证据须重跑 `src/q3_zspace_recompute.py` 指向 EXP-0110。
- 三问选择状态均为 **provisional**（Q1/Q3 结构性缺口；Q2 因工具 readiness 绑到最新稳健性实验而无法精确复跑）。
- 无外部 holdout / 外部验证集；独立复跑是确定性重现，不是独立实现。
- 交付检查未过最终门禁 → `final=false`，只能出 DRAFT 包（见 `DELIVERY-NOTES.md`）。
