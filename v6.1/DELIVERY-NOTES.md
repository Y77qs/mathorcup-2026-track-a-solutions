# DELIVERY-NOTES.md — v6 复赛修正后的交付说明（**DRAFT，不是 FINAL**）

- 项目：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`（项目 id `beer-2026-a-v3`）
- 台账：`state/ledger.json`；配置：`contest.yaml`（`acceptedVersion=2`、`configState.state=in_sync`）
- 协议身份：`configRawSha256=728811fc…`、`configProtocolSha256=215d0941…`（与 acceptedVersion 2 一致）
- 交付判定：**DRAFT**（`final=false`、`qualityPassed=false`）。`delivery.contest = null` → 官方平台提交记为 **skip**，
  由人完成；本代理**未自动提交**，也未声称已提交。
- 本轮时间：2026-10-27（v6.1 显式恢复轮）。

## 1 一句话判定

论文与产物链（`paper.md` → `rendered.md`（RENDER-0022）→ `paper.tex`/`paper.pdf`（ART-0021/ART-0022））
是闭合且逐字节可核对的；科学修正（Q3 截距/NA/边际/V 选参、Q2 方向一致率、完整可行域基线）已重跑并留下真实回执；
但**交付身份未冻结、质量门禁未通过**，因此本交付是 **DRAFT**。

## 2 运行控制与恢复（如实）

| 项 | 实际状态 |
|---|---|
| activeRunId | **RUN-0004**（`control:recover` 显式恢复建立；未再 begin/stop/recover） |
| RUN-0003 | **stopped / unknown-usage**，未改写为成功 |
| 失败请求 `ab5ac473-…:1:67` | `settled:false`、`usageUnknown:true`、`reserved=1304576`；**未结算** |
| 预算继承 | 新 run 继承 1,304,576 token 未结算上界与历史已知用量；`runcontrol-budget` 如实为 **needs_review**；soft/hard 均 null |
| 恢复方式证据 | `.rework/recovery-20261027/`（recovery-proof.json、recovery-receipt.json、ledger-before.json、collected-experiments.json） |
| 已回收不重训 | EXP-0125…0130 用公开 `experiment status` 从磁盘结果入账（EXPs 前后均 130） |

## 3 产物与 SHA（全部实测，逐字节与磁盘一致）

| 产物 | bytes | sha256 |
|---|---|---|
| `report/paper.md` | 119684 | `b319ccd9a8c31749cad3db8828c4cca055afd449a5b47397996185df93a8b0df` |
| `report/rendered.md`（RENDER-0022） | 122874 | `59c731bcae1087cded39b135c3684a55f9b2e2858f5737a34075489a8289649c` |
| `report/paper.tex`（ART-0021） | 158705 | `3286dde052752682369d8e579489994bf418302013644eba62db3868798b3597` |
| `report/paper.pdf`（ART-0022） | 3111844 | `31d5e72dfc03a65a63fff23d281542026378c9475d38206545537b5bd78c6a1b` |
| `report/tables/INDEX.json` | 36156 | `3fd9756f1f90efc71a978ad94e6600dda8b983cd0aa26f780b7c4444abf3ab33` |
| `report/evidence_manifest.json` | 28891 | `7dbd3a6375beff8db2c3204cace12aa9d6af9a69916cef0098058f2ebcc8f263` |
| `report/BUILD-INPUTS.json` | 4793 | `1434f8ee88296c302cdb2cde1b403ae4e7d91f737b1ae0029beb35d825b99a82` |
| `report/pdf-audit.json` | 14101 | `48e3e14d8783b561e5e987392a05ea5b8dc64cd492df2c654c9f8011ce508a43` |
| `outputs/q3/qp_cert_audit.json` | 7132 | `32e1f9b575a268befda7b12f49575c2e0b4dedcb39d186d4dc5d418588852127` |
| `REPRODUCE.md` | 7798 | `a2b8c8c4b00eb7815af86804b5b7a0d94becff557e7887665a6c01fcdee0eca5` |
| `change_log.md` | 6131 | `94ce79446fe883434ff5a1a96fa067c407611a1afd2c7980a8c9b92a4cd9dbb9` |
| `AI-USAGE.md` | 5209 | `8ed0646ffd1b6b2a0b0c1edc19679140b2bc719267489bbed0e71b23a61d6e3d` |

构建脚本：`src/build_paper.py 0a9e2b15…`（本轮加了 --no-caption-ids 与图注内部编号过滤）、`src/paper_tables.py 232ba066…`、`src/make_confirmatory_figures.py ffd9daf3…`、
`src/r05_scope_numbers.py b954f80d…`、`src/r05_robustness_products.py 0bdc404c…`、`src/r07_evidence_manifest.py 7318daed…`、
`src/r03_reproduce.py 1dc177f4…`。构建命令：`build_paper.py --build --pdf --no-caption-ids --outdir report --allow-report-output`
（`--no-caption-ids` 保证题注只显示中文编号，不出现内部表/图 id）。

## 4 本轮确认轮证据（台账实际 id）

| 问 | 主实验 | 关键指标 | 验证 | 稳健性 |
|---|---|---|---|---|
| Q1 | EXP-0073 / 基线 EXP-0074 | A/F30 OOF MAE 0.35929156588219174 / 0.39817732837288883 | VAL-0063/0064/0065（历史轮，仍有效） | ROB-0011 = EXP-0100/0101/0102；CLAIM-0059 |
| Q2 | EXP-0107 | topk-jaccard 0.2091111111111111；sign_stability 0.9816877777777778（旧口径 0.7225544444444444）；π<0.5 1263/1800；150 条共识 95 条 π<0.5 | VAL-0070 leakage、VAL-0073 independent-rerun（rerun EXP-0108） | ROB-0015 = EXP-0125/0126 + 补充 EXP-0131；CLAIM-0063 |
| Q3 生成 | EXP-0109 | constraint-satisfaction 1；energy-distance 0.8726874826148657；V 15.99994601104919；U 1.6153896894821214；subset V 33.78288729066554；真实 nonenal 增加 0 / 感官 t2n 366 | VAL-0076/0077（rerun EXP-0112） | ROB-0016 = EXP-0127/0128 + 补充 EXP-0132；CLAIM-0064 |
| Q3 迁移 | EXP-0110 | nonincrease-rate 1；transfer-energy 2.0798861351916886；198 QP 全 optimal；131/198 贴 1e-9 边界；四类 verdict 3465/3663、198、99、0 | VAL-0074/0075（rerun EXP-0111） | ROB-0017 = EXP-0129/0130 + 补充 EXP-0133；CLAIM-0065 |

结论：活跃 claim 8 条 = CLAIM-0056/0059/0060/0061/0067/0063/0064/0065。
`CLAIM-0041/0054/0055` 已 superseded、`CLAIM-0047/0052/0053` 已 retracted（旧记录保留，不删除）。
`CLAIM-0062→0066→0067` 是同一结论的两轮更正：贴边 189/198→**131/198**（189 是 495 行全策略合计）、
conditional 198 更正为 **99 条 nonenal 源值上界（非训练 q90）+ 99 条 stale_hops 代理**；
`CLAIM-0060` 的 supersedesReason 里把 VAL-0070 写成 EXP-0107 的检查是错误表述（VAL-0070 实挂 EXP-0104，
EXP-0107 名下是 VAL-0073），历史文本不可改，在此披露。
`CLAIM-0061` 的 limitations 里“458 行”为笔误：实际每个 fit 的有效观测总数是 463/5082 或 231/5082（视折而定）。

## 5 图件版本链（2.8.10 §10）

- 活跃图 **FIG-0041…FIG-0050**（10 张，`figures/confirmatory_v2/`），全部由 `src/make_confirmatory_figures.py`
  从台账实验重算，两次运行字节一致；新增 **FIG-0045** = 附件 2 描述性网络（不对应实验，来源产物 sha 已记录）。
- 旧图 **FIG-0032…FIG-0034**（Q1 三张，内容未变、字节相同）：工具拒绝 supersede（"not a different version"），
  按**纯退休**处理并归档；**FIG-0035…FIG-0040**（内容变化）按 **superseded** 指向对应新图并归档。
  归档路径 `figures/archive/FIG-00xx-<原文件名>.png`，sha256 与登记值逐字节一致。

## 6 论文结构审计（实测，非构建日志）

`python .rework/pdf_audit.py report/paper.pdf --json report/pdf-audit.json`：
38 页；封面/目录（目录在**第 2 页**且为单页）无页码；正文从 PDF 第 3 页起编 **1**，到 PDF 第 32 页为 **30**（正文 30 页）；
参考文献 p33；附录 p34–38；38/38 页**无页眉**；页脚页码**居中**且连续；图 **1–10**、表 **1–15** 连续；
未解析 `{{…}}` = 0、`PENDING-FIGURE` = 0、CJK 字符 26k+；完全匿名（无作者/单位/致谢）。
`python .rework/check_paper_consistency.py` → **0 violations**；`paper_tables.py --verify` → **19/19 complete**。
论文正文与图表题注只出现中文编号；内部实验/验证编号只出现在附录 B.4 的证据登记块（渲染器生成，可整块删除而不影响阅读）。

## 7 复现

见 `REPRODUCE.md`。`python src/r03_reproduce.py` 本轮实测 `ok=true`（runId `20261027-212317`），
四个角色（Q1 / Q2 / Q3 生成 / Q3 迁移）全部通过且 `maxAbsDelta = 0`。
干净目录复现的是**四个实验角色的数值指标**（`src/r03_reproduce.py` 只复现实验，不复现 `rendered.md`/`paper.tex`；上一句提到的“rendered/tex”不属该脚本能力范围，已在此更正）。`rendered.md`/`paper.tex` 由同一脚本链确定性生成但不受该复现脚本约束；**PDF 字节不可复现**（xdvipdfmx 非确定性）。

## 8 如实保留的缺口（阻断 FINAL 的原因）

1. **质量门禁未过**：`QC-0033` analysis-evidence 仍 failed（历史实验缺输入特征清单，本轮不 retrofit）；
   多项 required 检查因无注册 split 的权威测试真值而 `needs_review`；`runcontrol-budget` 因继承未知用量而 needs_review。
2. **三问 selection 均 provisional**：Q1/Q3 结构性（无 holdout / 单 selectedModelId 无法覆盖生成+迁移双组件）；
   Q2 因工具 readiness 绑到最新稳健性实验 EXP-0131（其 params 与模型不同、无法 fixed-seed 精确复跑）。
3. **验证检查点**：Q1 split-integrity / holdout-metrics 结构性不可满足；Q3 原生 optimization 检查形状不兼容、不声明通过。
4. **ROB 计划执行面 n=2**：ROB-0015/0016/0017 声明 3 个种子块，但工具拒绝覆盖已执行计划，故计划记录只含 2 块；
   第 3 块 EXP-0131/0132/0133 另有 succeeded 记录并在论文/表中以“补充种子块、未并入计划记录”单列。
5. **过期证据**：`outputs/q3/zspace_recompute.json` 仍是旧 EXP-0080 代码产物，本轮**不引用**；`TGT-0003` 记录带 legacy
   `stale=true`（无 per-input snapshot，无法在公开接口内清除）。
6. **数据边界**：无外部 holdout/外部验证；6.csv 仅同源对照；校准附件与主输入有 80 格线性值冲突（主输入规则已披露）。
7. **旧轮审查**：REV-0026/0082/0083/0093/0094/0095 的未决 findings 已由最终独立审查者逐条 resolve；REV-0106/0107 等更早一版 review 因对象更新而 stale，当前最新为 REV-0112（delivery）/REV-0113（coverage）；其中余下的 minor 项见下第 8 条。
8. **版式 minor（如实保留）**：PDF p9 有一条 60.5pt 的 Overfull hbox（长 `\texttt{}` 不折行）；正文数值按 17 位浮点原样呈现（可追溯但不宜读）；图 4/6/10 的台账 caption 文本含实验/计划编号，构建用 `--no-caption-ids` 把它们**语义替换**为中文角色词（如“对应主实验”“预登记的种子块计划”）；PDF 正文与题注已无任何内部编号，编号只出现在附录 B.4 的证据登记块。

## 9 交付检查与打包

### 9.1 实际回执（已执行，2026-10-27）

- `modeling_deliver {action:"check"}`：`ok=false`、`final=false`、`draft=true`、`engineeringComplete=false`、`checkpointsPassed=false`、`qualityPassed=false`、`submissionReady=false`。
  质量：45 项 = **32 passed / 1 failed（QC-0033） / 11 needs_review / 1 stale（QC-0031 未知用量）**，`criticalOpen=0`，`QC-0020 critical-findings = passed`、`stale=0`（15 passed/82 stale 的 review 计数只对交付范围口径生效）。
  结构检查 86 项：101 passed / 17 failed；engineering 73 项 69 passed / 4 failed；blocking = 三问 selection（均 provisional）、checkpoints（36 条 required 检查未过）、quality（requirement-coverage / analysis-evidence / metric-recompute×10 / runcontrol-budget）。
  三种格式 md/tex/pdf 均 produced 且 tex/pdf 绑定 RENDER-0022（ART-0021/ART-0022）；`contest:config = NO_CONTEST_CONFIG`（`delivery.contest=null`，不虚构官方规则）。
- `modeling_deliver {action:"package", draft:true}`：`ok=true`，目录 `delivery/20261027-220714-DRAFT`（588 文件），归档 `delivery/20261027-220714-DRAFT.tar.gz` sha256 `cbfbd05c3f978e89d08916ee8b58868980a21fa49f1fbca39a72208efcde3ff7`，manifest `final=false`。包内仅收录 metrics/predictions/result 与已登记图，**不包含** `samples*.csv`/`solver_certificates.jsonl`/`transfers.csv` 等实体文件（工具行为，已在 warnings 如实列出）。
- 支撑材料包（人工同步，逐字节复制）：`delivery/support-20261027-220714/`（190 文件；含 10 张图、19 张表、Q1 评分矩阵/750 行 OOF、Q2 符号与 Top-3 表、附件2 网络四件、Q3 的 `samples.csv`/`samples_raw.csv`/`samples_difference.csv`/`sensory_profiles.csv`/`tuning_table.csv`/`marginal_state.csv`/`verdict_layers.csv`/`transfers.csv`/`transfer_constraints.csv`/`transfer_verdicts.csv`/`transfer_sources.csv`/`solver_certificates.jsonl`/`qp_cert_audit.json`，以及 12 个确认轮/稳健性实验的 metrics/outputs），`SUPPORT-MANIFEST.json` + `SHA256SUMS` 190/190 独立复算一致；归档 `delivery/support-20261027-220714.tar.gz` sha256 `e8bdd38c5dc6d43e4d5863136141af8dc55d6ea7e47ce4bcb4511ba91d763a79`。**这不是 FINAL 包，也不替代插件 DRAFT 包。**
`delivery.contest = null` → 官方平台提交 = **skip**，由人完成。
