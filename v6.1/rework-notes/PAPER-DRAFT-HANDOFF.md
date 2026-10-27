# 论文源批次：断点续跑文件（PAPER-DRAFT-HANDOFF）

项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`；SOURCE（`my-new-contest-v3`）**只读**。
本文件只记录**真实 ID、状态、下一动作、blocker**。不复制台账，不粘贴大回执。
新会话恢复顺序：`modeling_project {action:"status", projectDir:P}` → `config status` → 读本文件 → 读
`report/evidence_manifest.json` → 读对应 EXP/VAL/ROB 原始记录。

## 0 本批范围（明确不做）

**做**：`report/paper.md` 全篇证据重写；证据驱动的业务表格（脚本生成，含 SHA/来源映射）；本批一致性扫描。
**不做**：新图、FIG 登记、`src/build_paper.py` 版式、`modeling_deliver render/check/artifact/package`、
`quality-run`、delivery review、freeze、任何 `modeling_*` 写调用、任何竞赛平台提交。

## 1 恢复现场（2026-10-27 本批开始时）

- 业务 revision=4615，runtimeRevision=1910→1914；`stage=intake`（七检查点仅 validation 未过，其余 ok）。
- `config`：`in_sync`，acceptedVersion=2，raw sha256 `728811fc…c9e5c3733`，未变更；**不改配置**。
- `quality.runControl.activeRunId=RUN-0003`，status=`running`，budget `{soft:null,hard:null}`；RUN-0001=`stopped/budget`、
  RUN-0002=`stopped/no-progress`。**本批不 `begin`、不 `stop`**；RUN-0003 保持 running（本批无 quality-run）。
- 实验：102 条；`reconcile.running` 报 6 条（EXP-0027/0045/0046/0047/0059/0061）实为 `queued: never started`（pid=null），
  **无真实运行中进程**；本批不重用这些排队项、不 cancel。
- `frozen` 仍是 2026-10-24 旧身份（claimIds 为 6 条退休 claim），**本批不改 frozen**。
- selection：Q1=MODEL-0048 `provisional`；Q2=MODEL-0050 `validated`；Q3=MODEL-0053 `provisional`（生成/迁移双对象）。
- `report/evidence_manifest.json` 已存在（ledgerRevision=4614，`draftOnly=true`），**本批不重新生成**。

## 2 当前证据映射（以 evidence_manifest 为准，本批核对一致）

| 范围 | 主 claim | 稳健性 claim | 主实验 | 验证 | ROB |
|---|---|---|---|---|---|
| Q1 | CLAIM-0056 | CLAIM-0057 | EXP-0073（候选）/ EXP-0074（中位数基线） | VAL-0063/0064/0065 | ROB-0011 |
| Q2 | CLAIM-0041 | CLAIM-0052 | EXP-0075 | VAL-0056/0057 | ROB-0008 |
| Q3 生成 | CLAIM-0054 | CLAIM-0053 | EXP-0079 | VAL-0066/0068 | ROB-0009 |
| Q3 迁移 | CLAIM-0055 | CLAIM-0047 | EXP-0080 | VAL-0067/0069 | ROB-0010 |

- 允许引用的实验（本批白名单）：EXP-0073/0074/0075/0079/0080、EXP-0089/0090/0091、EXP-0092/0093/0099、
  EXP-0095/0096/0097、EXP-0100/0101/0102。
- 禁止：退休 claim CLAIM-0012/0014/0018/0019/0021/0022；EXP-0038..EXP-0072、EXP-0076/0077；退休图 FIG-0025/0027；
  任何新 FIG id（本批无图）。
- 旧论文 `report/paper.md`（原文）建立在先导轮 EXP-0001..0036 与 6 条退休 claim 上，**已被本批整体替换**；
  这正是 quality QC-0020 的失败原因，本批即该项的修复动作。

## 3 表格产物约定（本批落地）

- 生成脚本：`src/paper_tables.py`（一次性、幂等、只读输入、`--splice` 才写 paper.md）。
- 片段：`report/tables/<id>.md`（markdown 管道表）；数值：`report/tables/<id>.csv`；索引：`report/tables/INDEX.json`
  （含每张表的输入路径 + 输入 sha256 + 输出 sha256 + 表→实验映射 + 生成脚本自身 sha256 + 生成时间）。
- 正文占位：`<!-- TABLE:<id> -->`；`--splice` 把该行替换为
  `<!-- table-begin:<id> sha256=... -->` + 片段 + `<!-- table-end:<id> -->`，可重复执行（幂等）。
- 表 id 清单：T1 q1-models、T2 q1-groups、T3 q1-styles、T4 q1-targets、T5 q1-grades、T6 q1-scores-aroma、
  T7 q1-scores-flavour、T8 q2-universe、T9 q2-core-top3、T10 q2-full-top3、T11 q2-extended、T12 q2-stability、
  T13 q3-raw-design、T14 q3-quality、T15 q3-constraints、T16 q3-transfer-stages、T17 q3-transfer-columns、
  T18 q3-qp-certs、T19 rob-confirmatory。
- 缺输入必须**具名失败**（非零退出 + 打印缺失的 metric key / 文件路径），不得回退到旧 EXP、不得填 0。

## 4 进度台账（每完成一节更新）

| 项 | 状态 | 证据 |
|---|---|---|
| 现场恢复（status/config/runControl/queued） | DONE | 本文件 §1 |
| 读 evidence_manifest / decision.md / INDEX-confirmatory / HANDOFF | DONE | §2 |
| 表生成脚本 + 19 表 + INDEX.json | IN_PROGRESS | teammate `table-builder`（写域 `src/paper_tables.py`、`report/tables/**`） |
| paper.md 全篇重写（DRAFT） | **DONE**（本批 §3 口径；677 行） | 写域 `report/paper.md`（Lead 独占）；旧稿备份 `.rework/paper.superseded-20261024.md` |
| 一致性扫描脚本 | **DONE** | `.rework/check_paper_consistency.py`（只读；当前 0 violations） |
| 表生成脚本 + 19 表 + INDEX.json | **DONE** | `src/paper_tables.py`（`--build/--verify/--splice`）；19/19 COMPLETE；`--verify` 19/19 通过 |
| splice 表格进 paper.md | **DONE** | 19 个 `<!-- TABLE:... -->` 全部替换为 `table-begin/end` 块；块内 sha256 与 INDEX 记录一致（由检查脚本逐块核对） |
| 一致性扫描 | **DONE，0 violations** | `.rework/check_paper_consistency.py`（含：裸编号、退休对象、占位符解析、表块 sha 绑定、记录输入 sha 未漂移） |
| 独立复审（paper-reviewer） | IN_PROGRESS | 写域 `.rework/reviews/`；结论以复审报告为准，Lead 不代填 |
| 记录 SHA + 断点收口 | **DONE** | 见 §8 |
| 本批收口 | TODO | 输出 A/B |

## 5 PENDING-FIGURE 清单（下一批换真实 FIG）

（随 paper.md 写作填充；本批**不得**出现任何 `{{figure:...}}` 或假 FIG id。）

每处图位在 `report/paper.md` 中以 `<!-- PENDING-FIGURE:<name> -->` 占据，**本批无任何 `{{figure:...}}`、无 FIG id**；下一批生成图文件、经 `modeling_deliver figure` 登记后再替换。

| # | 占位注释 | 论文位置 | 需要的图 | 来源实验 | 数据出处 |
|---|---|---|---|---|---|
| 1 | `<!-- PENDING-FIGURE:Q1-per-target-skill -->` | §4.4 预测结果（Skill 口径段后） | 逐维 Skill 升序条形图（正/负分色） | EXP-0073 | `oof_long.csv` / 表 q1-targets |
| 2 | `<!-- PENDING-FIGURE:Q1-model-comparison -->` | §4.4 四模型对照（表 q1-models 后） | 四模型 MAE 对照条形图（A/F30 与全 50 双口径） | EXP-0073 / EXP-0074 | 表 q1-models |
| 3 | `<!-- PENDING-FIGURE:Q1-grade-distribution -->` | §4.5 相对等级（表 q1-grades 后） | 预测等级与参照等级的 0–6 分布对照 | EXP-0073 | `outputs.json` grade 块 / 表 q1-grades |
| 4 | `<!-- PENDING-FIGURE:Q2-network -->` | §5.2 两个网络 | 附件描述网络拓扑（最大连通分量 + 分量规模统计） | 附件相关矩阵（非实验） | `data/` 相关矩阵 |
| 5 | `<!-- PENDING-FIGURE:Q2-stability -->` | §5.5 稳定性 | 入选频率分布 + 四方法集合一致性 | EXP-0075 | 表 q2-stability |
| 6 | `<!-- PENDING-FIGURE:Q3-energy-comparison -->` | §6.5 生成质量 | 五种对照（含 source-resample）的归一化能量距离 | EXP-0079 | 表 q3-quality |
| 7 | `<!-- PENDING-FIGURE:Q3-per-style-energy -->` | §6.6 三风格分开 | 逐风格能量距离（21 风格，三风格高亮） | EXP-0079 | `style_and_displacement_scope.json` |
| 8 | `<!-- PENDING-FIGURE:Q3-transfer-shift -->` | §6.10 三组量分开 | 约束残差 / stored 位移 / z 位移三组分离图 | EXP-0080 | 表 q3-transfer-columns |
| 9 | `<!-- PENDING-FIGURE:ROB-summary -->` | §7.2 四组检验 | 四组绝对/相对极差与各自上限对照 | EXP-0100–0102/0089–0091/0092–0099/0095–0097 | 表 rob-confirmatory |

**下一批注意**：`Q1-per-target-skill` 与 `Q1-model-comparison` 是两张不同的图，不要合并；`Q3-transfer-shift` 必须画成三组而不只是一条位移曲线（本批正文已明确三组量不可混写）。

## 6 已知遗留（不属本批，禁止在本批顺手做）

1. QC-0020（paper 引 6 条退休 claim）——本批重写即修复，但 `quality-run` 不在本批。
2. QC-0033（EXP-0017/0018/0026/0035/0036 缺 feature manifest）——历史/插件结构，禁止 retrofit。
3. REQ-0001..0004 记录 `stale=true`（sourceSha256=null）；REQ-0004/0005/0007 为 `insufficient_data`。
4. `frozen` 旧身份；`render/check/freeze/package` 均未做，DRAFT 不得写成 FINAL。
5. Q3 选择双对象（生成/迁移无法用单一 selectedModelId 表示）；原生 optimization VAL 未通过、不声称。
6. 新图、FIG 登记、`src/build_paper.py` 版式：下一批。

## 7 本批执行日志

- 恢复：modeling_project status（rev 4615）、config status（in_sync, v2）、runControl（RUN-0003 running，不 begin/不 stop）、
  queued 6 条实为 never-started；未与旧会话并行写（无活动进程）。
- 读入：`report/evidence_manifest.json`、`outputs/q3/decision.md`、`outputs/robustness/INDEX-confirmatory.json`、
  `.rework/VALIDATION-SELECTION-HANDOFF.md`、`report/revised-20261025/support/manuscript.template.md`。
- 旧 `report/paper.md`（先导轮 EXP-0001..0036 + 6 条退休 claim）**整体替换**，原件备份 `.rework/paper.superseded-20261024.md`（未删除）。
- 新稿：正文只引白名单实验；关键数字一律 `{{metric:...}}`；8 条 active claim 绑定在附录 C；9 处图位为 `PENDING-FIGURE`；
  19 处表位为 `<!-- TABLE:<id> -->`；原文中的 `{{figure:FIG-xxxx}}` 全部移除（本批不登记 FIG）。
- 一致性扫描：裸台账编号 0、退休 claim 0、禁止 EXP 0、假 FIG 0、metric 占位符 76 处/59 唯一全部可解析、claim 占位符 8 处全 active。
- 未做：`quality-run`、`render`、`check`、`freeze`、`artifact`、`package`、新图、FIG 登记、`src/build_paper.py`。

## 8 本批产物与 SHA（最终，2026-10-27T01:0xZ）

| 产物 | 路径 | sha256 |
|---|---|---|
| **论文源（DRAFT，19 表已内联）** | `report/paper.md` | `1bf7a65a72e2f045baae9755e2374f2614e2837f0e326a9be46157b7ee4ba414` |
| 表格索引 | `report/tables/INDEX.json` | `1c27309b9ac8da5e0221ab0749b68b983a848e70d68f18a125e8ed9be11d4dbf` |
| 表格生成脚本 | `src/paper_tables.py` | `f8d881234db6a52e4d3929ab1bf7c25dd9a38d016c9421c83932e656f1fa6940` |
| 一致性检查脚本 | `.rework/check_paper_consistency.py` | `d3473b23f37283667b6aa379fba1dea0d70812b7fc30c2c873e2fb993f5c86b2` |
| 表块刷新脚本 | `.rework/refresh_table_block.py` | `2121a702726602d2f7d473288384af4bf9fe5266f9b9a61676d2127e5eb0cfed` |
| 独立复审报告（REV-1 + REV-2） | `.rework/reviews/paper-source-review.md` | `eb40294d9e5dc23c5d96fadaeb895a5ad7b19a48096a8fdd5aed0092b86110cf` |
| 旧论文备份（未删除） | `.rework/paper.superseded-20261024.md` | — |

19 张表的 md sha256（与 `INDEX.json` 的 `tables.*.outputs.md.sha256`、以及 `paper.md` 内联块的 `table-begin` 头三方一致，
由 `check_paper_consistency.py` 每次运行逐块核对）：

| 表 id | md sha256 |
|---|---|
| q1-models | `89369169d05f5d7d0901a347096f00fd3edacfeacbc822adf1eb72965d39ace9` |
| q1-groups | `346c55460e3fde077cdaf481cd0930060902cd08f0cf121bed75678c70c8228a` |
| q1-styles | `9d4b327caa7784267b363bf7815d71c25814487470f33e37510068f5c722be82` |
| q1-targets | `8f60d76335c4be459b2fd43efb88e30f93f78b7f01ef547bd773564c905ad99a` |
| q1-grades | `003871a907665e16bf0094c63cb04e80637c3fb52cff89ac95e07d60eb05f214` |
| q1-scores-aroma | `0040ad38b0b93fa8a8f0ee6935edc3ad3d1da2916f6b9db8d38f360b526ba4d1` |
| q1-scores-flavour | `a1ab3464521df13d9e0f039f6bdaf35522034adc6015fb6022fbdd8830359165` |
| q2-universe | `83af9df245dda67a83065e9a76f2423297dfaf46130b6480ca401951ef8b69bd` |
| q2-core-top3 | `b0b98a71dc2c4db096f7dbe7b88d35dfff710b2827a9da9869200ca293c03369` |
| q2-full-top3 | `d9c9827376edc9ea679a76448af2731c70815cb80dd32e32310f2e07c7380f92` |
| q2-extended | `b4f6724f313fc0ab0bcd9b343a7e4a7489b938b617903c7bf11832ff26aabb09` |
| q2-stability | `a9096a00b75e626afb3d1ad44de4fec8da69bc93bcf3f2eb12d34000b1b2057b` |
| q3-raw-design | `b8e173bd751dd37412c631d52a05e58c592446805750db49ebfa18790a0b9bc1` |
| q3-quality | `577eb42b7cbd5046d99de288c79061d5bcac7d7b53709e8d3387a1c29a1c4c1d` |
| q3-constraints | `69b722d61b523aa767a6d1f81499afca2129210a7e2b41fd2c2a9291f9826a8d` |
| q3-transfer-stages | `361b6f06bf5e18b3e97516b09cdba08fd74fcaf1955fdbab9a6e269c817fa369` |
| q3-transfer-columns | `97874c0dfba5c3aa03f638aa78c6082f87f9dafaa40773e13fe4f50b783f77c1` |
| q3-qp-certs | `457b2cda6ae36354c3f99974b9a8a900a33a648fc2d337134551e6096671b451` |
| rob-confirmatory | `30a93c3f2a1d383a2af6303d74f3e76da0e5b92788b18b4637a90a0b14331ed2` |

- 论文规模：1274 行 / 126 294 字节；正文（`\appendix` 之前）约 44 千字符，其中表格约 15 千字符、散文约 29 千字符；
  按 1 300–1 500 字/页估算正文约 24–30 页，**实际页数以下一批 `src/build_paper.py` 构建后为准**。
- 结构：14 个一级标题（摘要、7 个正文章、结论、参考文献、附录 A/B/C）；正文内联 15 张表，附录 A 4 张，附录 C 8 条 claim 占位符。
- 78 个 `{{metric:...}}`（60 个不同组合）与 8 个 `{{claim:...}}` 全部可解析到 active/succeeded 证据。

### 8.1 独立复审结论（paper-source-review.md）

- REV-1：verdict=findings，30 项原始产物独立复算逐位一致；findings F1–F9（4 major / 5 minor，无 critical）。
- REV-2：9 项指定修复 **9/9 resolved、0 regressed**；仅 N2/N3 两条 minor 文字项 + F7 台账溯源项。
  本批已修 N2（“四个综合 1.000”→“三个”）与 N3（T19 行标签 + 摘要/§6.10/§7.2/结论统一为“综合不增率（旧称逐列不增率）”）。
- 表块哈希链：19/19 满足「`table-begin` 头 sha == INDEX == 片段文件字节 == 块内 body」。
- **F7 处置（书面记录，不改台账）**：复审观察窗内 `state/ledger.json` 至少出现 14 个不同字节版本，
  而 `revision` 恒为 4615、`updatedAt` 恒为 `2026-10-26T15:35:58.351Z`，即写入未伴随 revision 变更。
  这不影响论文数值的追溯（数值来自不可变实验产物；19/19 表输出与 59/59 表输入 sha256 均匹配、30 项复算逐位一致），
  只影响「表格索引 → 台账快照」这一层：`INDEX.selfCheck.ledger.sha256` 已不等于当前台账字节，
  `evidence_manifest.ledgerRevision=4614` 也落后于台账 `revision=4615`。**下一批须在台账静默后重生成 INDEX/manifest
  再冻结**，或在交付说明中保留本段记录。本批未写台账（仅只读的 status/config 调用）。

## 9 本批发现的证据不一致（未改台账，交下一批处理）

1. `outputs/q1/robustness_confirmatory.json` 仍是旧身份：`robId=ROB-0007`、`experimentIds=EXP-0086/0087/0098`，而 manifest 的 Q1 稳健性为 **ROB-0011 / EXP-0100/0101/0102**（三值逐位相同）。表 `rob-confirmatory` 不读该文件（值取自 EXP-0100/0101/0102 台账 metrics + manifest），因此**先导轮实验未进入任何溯源**。建议下一批重生成该文件或显式标 superseded。
2. Q1 逐风格指标实为 **22** 个风格（非 21；Faro 3 款、Brut 4、Flanders old brown 5、Scotch 5 为小样本风格）。表 `q1-styles` 已按 22 行输出并与项目风格计数常量对齐；与 Q3 的“21 个可估风格”不是同一口径（22 风格中去掉 1 个不可估）。
3. `extended_top3.csv` 是 **50 个感官维度 × 3 = 150 条**（候选宇宙才是那 15 个扩展指标），非 15 行；表 `q2-extended` 与论文表注均按此口径写明。
4. T17 的 z 空间**逐列**分解未随产物保存（`centre/scale` 只存 sha256），故第三组只给行级读数（231 维逐行 max/mean 与 L1），表注已写明；z 位移另有 396 行 0 失配的独立重算支撑。

## 10 下一批事项（本批明确未做）

1. 9 处 `PENDING-FIGURE` → 生成图文件 → `modeling_deliver figure` 登记真实 `FIG-xxxx` → 用 `{{figure:...}}` 替换注释（**不得**先写假 id）。
2. `src/build_paper.py` 版式：表块 → LaTeX 表环境、`table-begin/end` 注释在渲染管线中的处理、页数核定（目标正文 ≤ 30 页）。
3. `modeling_deliver render` → 解析 77 个 metric 占位符 + 8 个 claim 占位符；**注意**附录 C 的 claim 块会展开为带台账编号的结论原文，是否保留由该批决定。
4. `check` / `quality-run`（QC-0020 应由本批重写而转绿，但需实跑确认）/ `freeze` / `artifact` / `package`。
5. 遗留：`frozen` 旧身份；REQ-0001..0004 `stale=true`；REQ-0004/0005/0007 仍 `insufficient_data`；Q1 `split-integrity`/`holdout-metrics` 与 Q3 原生 optimization 检查结构性未通过（不得在本批或下批改写为通过）。

---

## 11 第二批：9 张图 + FIG 生命周期 + 构建准备（2026-10-27）

**本批做**：9 处 `PENDING-FIGURE` → 真实图 + 真实 FIG 登记；旧 ACTIVE 图生命周期处置；`src/build_paper.py` 重写与静态/小例测试；evidence_manifest 与 `report/tables/INDEX.json` 元数据刷新；paper.md 中 9 处占位替换。
**本批不做**：正式 render、delivery review、quality-run、freeze、artifact、package、正式 `paper.pdf` 绑定。

- 现场：revision 4615（业务字段未变）、`RUN-0003` running（不 begin/不 stop）；`revision` 恒定而 `runtimeRevision` 递增（host 运行时记账，非业务变更）。
- 分工（写域不重叠）：`figurer` = `figures/confirmatory/**` + `src/make_confirmatory_figures.py` + **唯一图登记写权限**；`builder` = `src/build_paper.py` + `src/build/**` + `.rework/build-test/**`；Lead = `report/paper.md`、`src/r07_evidence_manifest.py`、`.rework/*`、旧图退休。
- 本批新增/修改辅助脚本：`src/r07_evidence_manifest.py`（加 ACTIVE figure 索引块）、`.rework/refresh_evidence_index.py`（重生成 manifest + INDEX 元数据 + 复验 19 表）、`.rework/figure-retirement-plan.json`（29 条逐图决策，执行前校验）。

### 11.1 claim 块重构（本批已做）

`paper.md` 的 8 个 `{{claim:...}}` 已从附录 C **移入各自科学章节**（§4 末 2 条、§5 末 2 条、§6 生成末 2 条、§6 迁移末 2 条），标签为「证据登记（…）」。附录 C 改为**人类可读**的「证据类型/证据范围/验证状态/关键限制」表 + 未完成事项说明，不再重复展开带工程编号的结论原文。
（`report/paper.md` 改动前后备份：`.rework/paper.before-claim-restructure.md`。）

### 11.2 旧 ACTIVE 图的生命周期决策（逐图，不盲退）

校验结果：**29 张 ACTIVE 旧图全部没有 active claim 或 coverage 引用**（历史引用仅来自 superseded/retracted claim，不计当前交付）；`paper.md` 当前引用旧图 0 张。决策表见 `.rework/figure-retirement-plan.json`：

- **14 张按“被新图替代”退休**（先确认新 FIG ACTIVE，再 `figure-retire` + `supersededBy`）：
  FIG-0001/0016→`Q1-model-comparison`，FIG-0004/0018→`Q1-per-target-skill`，FIG-0005→`Q1-grade-distribution`，
  FIG-0006/0007/0021/0022→`Q2-stability`，FIG-0008/0023→`Q2-network`，
  FIG-0009/0024→`Q3-per-style-energy`，FIG-0015→`Q3-energy-comparison`。
- **15 张“纯退休”**（无替代、无当前引用，理由统一为“v6 论文证据链替换：旧图不在当前论文/active claim/coverage 的证据链中，保留历史”）：
  FIG-0002（融合权重）、FIG-0003（CV 网格）、FIG-0010（缺陷超阈）、FIG-0011（迁移情景）、FIG-0012（Pareto）、
  FIG-0013（消融）、FIG-0014（画像回收）、FIG-0017（融合权重）、FIG-0019（CV 网格）、FIG-0020（250×50 分级图，改为数据文件+正文表）、
  FIG-0026（迁移情景）、FIG-0028（画像）、FIG-0029（旧消融汇总）、FIG-0030（缺陷超阈）、FIG-0031（Pareto）。
- FIG-0025/0027 早已 superseded，本次不动。

### 11.3 台账快照语义（一次性记录，不追 revision）

`revision` 与 `updatedAt` 是业务字段，只在记录被编辑时变化；`runtimeRevision` 由 host 在每次工具调用时递增（本批观察 2602→…），**不是**业务变更。本批只在 `report/tables/INDEX.json` 的 `ledgerSnapshot` 里记录一次当前快照与上述语义，不通过反复重生成去追运行时 revision。

## 12 本批进度

| 项 | 状态 | 备注 |
|---|---|---|
| claim 块重构（§11.1） | DONE | 8 条入章节，附录 C 重写，检查脚本 0 violations |
| 旧图退休计划（§11.2） | DONE（计划） | 29 条已校验 0 active 引用；**待新 FIG ACTIVE 后执行** |
| 9 张图生成 + FIG 登记 | IN_PROGRESS | `figurer` |
| `src/build_paper.py` 重写 + 静态/小例测试 | IN_PROGRESS | `builder` |
| paper.md 9 处 PENDING → `{{figure:FIG-xxxx}}` | TODO | 仅在取得真实 FIG id 后 |
| 旧图执行退休 | TODO | 依赖新 FIG ACTIVE |
| manifest + INDEX 刷新 | TODO | `.rework/refresh_evidence_index.py` |
| 本批收口（19 表复验、PENDING=0、假 FIG=0） | TODO | — |

## 13 本批结果（图 + 生命周期 + 构建准备，2026-10-27T01:3xZ）

### 13.1 九张新图与真实 FIG（全部 active、字节 sha 与登记一致、正文各引用一次）

| 占位名 | FIG | path | sha256 | experimentId |
|---|---|---|---|---|
| Q1-per-target-skill | FIG-0032 | figures/confirmatory/Q1-per-target-skill.png | 2557001da5d9510a8f8afbfd682d4149c2b276b294901892dbc45ee0c8cf5838 | EXP-0073 |
| Q1-model-comparison | FIG-0033 | figures/confirmatory/Q1-model-comparison.png | a461da972ec8e999b9d643e945cf792f262d61c88aa85680fc67e7ba8119122e | EXP-0073 |
| Q1-grade-distribution | FIG-0034 | figures/confirmatory/Q1-grade-distribution.png | e2cf95cdb0e4fa5d16a79db21f08f1abc8f8136346a2b02612285ea60daa27d4 | EXP-0073 |
| Q2-network | FIG-0035 | figures/confirmatory/Q2-network.png | ad567a5eb75ba1b36012efc7d66b8d4e8e1667c348d2bf5cfa2f4f294410afc6 | EXP-0075 |
| Q2-stability | FIG-0036 | figures/confirmatory/Q2-stability.png | cec5621b88f02790868160137311c8375b26fef886c7738208d467faae976e99 | EXP-0075 |
| Q3-energy-comparison | FIG-0037 | figures/confirmatory/Q3-energy-comparison.png | 0e5d64be11e8a391a61de27e52838e8134661332d114d83cb314b2445a523349 | EXP-0079 |
| Q3-per-style-energy | FIG-0038 | figures/confirmatory/Q3-per-style-energy.png | 6ef2bac1b7b9b8867864f3fc8df85a3f24fdfc9f066e0488c4e2b57678959a6b | EXP-0079 |
| Q3-transfer-shift | FIG-0039 | figures/confirmatory/Q3-transfer-shift.png | 3c982d2394e3900ef7c91fd4f051d75ba8fd4e48123f9f548ae16efef9ba1e52 | EXP-0080 |
| ROB-summary | FIG-0040 | figures/confirmatory/ROB-summary.png | ab3461581ee902afde41bf6897316b67f8f9aedac12035919cdf6ec85f05be70 | （空） |

生成脚本 `src/make_confirmatory_figures.py` sha256 `c44d706d7aeea3e03fce3bfe37d92b248c2def0cb3da43249d8be8e998e19a10`（`--all/--one/--list`，缺输入具名失败 exit=2，两次 `--all` 逐字节一致，内建复算比对：Q1 逐目标池化 MAE、Q2 732 边/51 分量/π/符号一致性、Q3 逐风格池化与迁移位移/残差、ROB plan.values 与 spread）。

### 13.2 旧图处置（29 张，逐图授权，0 张命中 active claim/coverage 引用）

- 台账最终状态：**active 9 / superseded 16 / retired 15 = 40**。
- 14 张按“被新图替代”`superseded`（REV 记录含 supersededBy）：
  FIG-0001、0016→FIG-0033；FIG-0004、0018→FIG-0032；FIG-0005→FIG-0034；FIG-0006、0007、0021、0022→FIG-0036；
  FIG-0008、0023→FIG-0035；FIG-0009、0024→FIG-0038；FIG-0015→FIG-0037。
- 15 张纯 `retired`（理由均写明“v6 论文证据链替换…保留历史”）：FIG-0002、0003、0010、0011、0012、0013、0014、0017、0019、0020、0026、0028、0029、0030、0031。
- FIG-0025/0027 早已 superseded，本批未动；未做 archive（路径与登记字节未改，无归档需求）。
- 决策依据与逐图校验见 `.rework/figure-retirement-plan.json`（sha256 `3604c19d4516d349ebd947b3cf48c0eef6a33a5bc5382573f6b1735bb45d4bea`）。

### 13.3 paper.md 现状（sha256 `d9cc08eeeb7e7af9ead0f146642258fe93178914bcfe59406141bc37aee8d417`）

- 14 个 H1；**PENDING-FIGURE=0**，9 个 `{{figure:FIG-0032..0040}}` 各引用一次；8 个 `{{claim:...}}` 在科学章节末；19 个表块 `table-begin/end`。
- 新增范围说明（§6.10 第二组）：表只发布 3 个受约束列，231 列整体位移由痕量化合物主导、不代表整体设计位移。
- 三个附录 H1 已加 `{.unnumbered}`（避免 `\appendix` 字母编号与手写“附录 A”双编号）。

### 13.4 构建器（builder，静态/小例测试通过；未写 report 正式产物）

- `src/build_paper.py` `f658127d355486184ec5ad114157d667c8f31d38bf411802503c72cdd326c383`（`--check/--selftest/--build`；表块校验→booktabs/长表/宽表；claim 证据登记块；`{{figure}}`→includegraphics；PENDING/退休 claim/先导 EXP/假 FIG/`@@`/sha 不符逐条具名拒绝；tex 内嵌 source+builder sha；默认拒绝写 report/）。
- `src/build/header.tex` `2ba3c6339911ae6e3139cffb4ca07a780159c69e2a20ee32c36d77bccc06649c`、`src/build/template.tex` `b1140b188bdc5e1864c6a052a243f991d16fd0661db4078e5cfe69322ebfa042`。
- 我的复核（`--check --source report/paper.md --number-sections`）：**pass=33 fail=1**，唯一具名拒绝是 78 处未解析 `{{metric:...}}`（须下一批 render）；表块 19/19 四方一致、claim 8/8 active、图位 9/9 active 且 sha 匹配。
- `--selftest`：36/36 断言通过，小例 PDF 4 页（页1 标题+DRAFT+摘要、页2 目录、前两页无页码、正文页脚居中从 1 起、中文表/图题注）。
- 负测试 6/6 命中（退休 claim、先导 EXP、假 FIG、`@@`、表块 sha 篡改、PENDING）。产物只在 `.rework/build-test/`（`BUILD-INPUTS.json` 等）。
- `report/paper.tex|pdf|rendered.md` **仍是 2026-10-24 旧文件**（mtime 22:37，未覆盖）。

### 13.5 本批决定（下一批按其执行）

1. **编号**：用 `--number-sections`，`secnumdepth=1`（只编 H1）；摘要/参考文献/附录已 `{.unnumbered}` ⇒ §4/§5/§6/§7 引用全部可解析，无双编号。
2. **宽表**：`--wide-tables wrap`（留在原位、比 rotate 少约 2 页）。
3. **页数**：本批**未核定**（被 78 个未解析指标挡住）。builder 静态探针：仅动态内容（19 表+8 claim+9 图、无正文）rotate 36 页 / wrap 34 页，其中两张 150 行附录表各占 6 页；加散文估算整篇约 45–55 页。**下一批需按“正文 ≤30 页”做内容决策**：优先把 q2-full-top3 / q2-extended 两张 150 行长表移支撑材料、缩图高、去重复版面，**不删负结果与限制**。

### 13.6 证据索引刷新

- `report/evidence_manifest.json` `58a8a9fac8115eebbc754ee5ddaab4a1acf77e689cac775ee3ca62c3c4fd05e3`：新增 `figures` 块（9 张 active + `paperCited`），`forbiddenInPaper.retiredFigures` 现为 31 条（历史保留），8 条 active claim 映射不变。
- `report/tables/INDEX.json` `10ff2bbfd36f0f6daa1321f84f869d21e47479c2f98a0e0f9c74b56bf96c3cfb`：新增 `figures` 与一次性 `ledgerSnapshot`（含 revision/updatedAt 语义说明）；19 张表 `--verify` 仍 **19/19**。

### 13.7 下一批（render + 独立复审 + 质量 + PDF 绑定 + DRAFT 包）

1. `modeling_deliver render`（解析 78 个 metric + 8 个 claim + 9 个 figure）→ 得到当前 `rendered.md`。**未决**：render 是否把 `{{claim:...}}` 展开成纯文本；若展开，builder 的证据登记框样式失效，需决定“保留占位符由 builder 从台账渲染”或“接受纯文本”。
2. `--build` 到 report（需 `--allow-report-output`）→ 实测整篇页数/overfull；按 13.5(3) 做页数内容决策。
3. 独立 delivery review；`quality-run`（QC-0020 应因退休 claim 清空而转绿，需实跑确认）；`freeze`；`artifact`（tex/pdf 绑定 render）；`package`。
4. 未决：FIG-0040 无 experimentId（工具允许；如需台账层实验绑定，下一批登记审计实验并把 ROB-summary 以新图 supersede）。
5. 结构性未通过项不得改写为通过：Q1 split-integrity/holdout-metrics、Q3 原生 optimization；Q1/Q3 选择仍为草稿选择；REQ-0004/0005/0007 仍 insufficient_data。

## 14 第三批：渲染预览与页数收口（2026-10-27T02:0xZ）

**范围**：内容减重 + 当前 render 预览 + 版式实测。**未做**：delivery review、quality-run、freeze、正式 artifact、package。

### 14.1 表格移支撑材料（页数驱动，不删证据）

- `q2-full-top3`、`q2-extended`（各 152 行）已从正文/附录移出，正文改为一段指针（指向 `report/tables/<id>.md` + 同名 csv + INDEX 溯源）。
- `report/tables/INDEX.json` 新增每表 `paperIncluded` / `supportOnly`，并新增 `supportOnlySets`（4 项：两张完整 Top-3 表 + QP 198 份证书全量 + 迁移逐行全量；后者指向 `solver_certificates.jsonl`、`transfers.csv`、`transfer_constraints.csv`、`zspace_centrescale.csv`）。移出理由字段写明“页数限制，非证据缺失”。
- **偏离并已核实**：`q3-qp-certs`（16 行）与 `q3-transfer-columns`（7 行）**已是汇总表**（求解数量/optimal/primal/dual/KKT/violation；关键列三组量），正合任务书 §一.4 要求的“只展示汇总”。故保留在正文，其**完整数据**按 supportOnly 登记。若下一批仍要求移出，只需把这两条 `paperIncluded` 置 false 并补一段指针。
- 表格验证：`src/paper_tables.py --verify` 仍 **19/19**；我的检查脚本已升级为“内联表查四方 sha、supportOnly 表查完整文件+INDEX sha、不允许 supportOnly 仍在正文”，当前 0 violations。

### 14.2 claim 渲染语义（实测）

- `{{claim:...}}` 由 render 展开为 **statement 纯文本**（不保留占位符、不展开 refs/limitations）。实测 RENDER-0010：8 条 statement 全部展开，且**含工程编号/时间戳/封装哈希**（如 "MODEL-0048 / EXP-0073 … VAL-0063/0064/0065 … ROB-0011 … wrapper 7d7ab6aca6c2 … 2026-10-26T15:16:37Z"），不适合进入论文正文。
- 已做**一条**合法替代（示范 + 保留证据）：`CLAIM-0057` → `CLAIM-0058`（字段不全，limitations 丢失）→ **`CLAIM-0059`**（补齐 limitations 5 条 / targetContractId / evidenceScope / refs 3 条），正文改引 `CLAIM-0059`；`src/r07_evidence_manifest.py` 的 WANT 与检查脚本白名单已同步。旧 0057/0058 保留为 superseded。
- **未做**：其余 7 条（CLAIM-0056/0041/0052/0054/0053/0055/0047）的 statement 仍含工程编号。本批为控制范围只保留其结论段（正文散文已完整覆盖，附录 C 已给出证据类型与限制），并**移除这 7 个 `{{claim:...}}` 占位符**——因此 RENDER-0011 的正文不再出现工程编号。若要恢复“每章一条 claim 原文”的形态，下一批需按 0059 的字段完整模板批量 supersede 7 条，并同步 r07 WANT / paper 占位符 / 检查脚本白名单（这是独立的一次证据操作，须整体验证）。
- 工具提示：supersede 后需 `requirement-map` 重指 coverage 并复跑相关 quality 检查（本批未做）。

### 14.3 预览 render

| 项 | 值 |
|---|---|
| RENDER（最终预览用） | **RENDER-0011** |
| 输入 | `report/paper.md`（sha256 `899c34bd5b4478e86a2f8dc3676ec7cc5522df3a8db937eabf840cc8cc13351c`） |
| 输出 | `.rework/previews/preview-B/rendered.md`（sha256 `a570ee55b8f4d463f572d7a0386b4afde14598f6fca13d64bd2dc25b52b17c08`） |
| refs | `.rework/previews/preview-B/rendered.refs.json`（`87ab44ba…`），88 个占位符、0 stale、0 warning |
| 结构校验 | `build_paper.py --check` **pass=32 / fail=0 / warn=0**；内联表 17/17、supportOnly 2/2、图 9/9、`claimsExpanded=true` |

（RENDER-0010 为减重前的一次预览尝试，保留在 `.rework/previews/preview-A/`，不作为预览基准。）

### 14.4 预览构建：**PDF 未通过（阻塞）**

- 命令：`--build --pdf --source .rework/previews/preview-B/rendered.md --outdir .rework/previews/preview-B --number-sections --wide-tables wrap --no-caption-ids`
- 首次结果：`preview.tex` 生成成功，**`preview.pdf` 仅 2 页即中止**：`! LaTeX Error: No counter 'none' defined.`
- 根因已定位：builder 的 longtable 题注抑制写作 `{\def\LTcaptype{none} …}`（tex 第 221/309/374/476/1786 行等），longtable 对未定义计数器执行 `\refstepcounter{none}`。**属 builder 缺陷，不是内容缺陷**；已按“不改 tex、改 builder”的要求回报给 builder 修复。
- **因此本批没有实测页数**，不宣称任何页数结论。上一批的 45–55 页只是静态探针估算，已被移出两张 152 行表（约 −12 页）后的真实页数待修复后实测。

### 14.5 下一批（在 14.4 修复后）

1. 重跑 14.4 命令 → 实测页数；若 >30，按任务书 §五 顺序：缩图高/表距（不改 FIG 字节）→ 再移 `q1-targets`(32 行)、`q1-styles`(24 行) 到支撑材料 → 合并重复说明；**不删负结果与限制**。
2. 版式逐项验收：首页（标题+DRAFT+摘要+关键词）、目录第 2 页、无页眉、前两页无页码、正文页脚居中从 1 起、匿名、无重复编号、中文图表题注、9 图全部出现且可读、无溢出/空白页/异常旋转页。
3. 视情况批量 supersede 剩余 7 条 claim（见 14.2）。
4. 之后才做：内容终态确认 → 独立 delivery review → quality-run（含 requirement-map 重指）→ freeze → 正式 render/artifact → DRAFT package。

### 14.6 builder 修复与**实测页数（本批结论）**

builder 已修 `\LTcaptype{none}`（改为不触发 `\refstepcounter` 的写法），同一命令重建成功：
`[PASS] pdf … bytes=2519696`，**`Output written on preview.pdf (36 pages)`**。
产物：`.rework/previews/preview-B/preview.pdf`（36 页）、`preview.tex` `e5e79579…`、`BUILD-INPUTS.json`。

**判定：36 页 > 正文 ≤30 页目标 → 本批不通过（LAYOUT_PREVIEW_BLOCKED），不宣称通过。**
- 已知构成（builder 静态探针 + 本次实测）：front matter 2 页（标题+DRAFT、目录）+ 散文约 19 页 + 17 张内联表与 9 张图较上一版减少约 12 页（两张 152 行长表已移出）。
- **未能核实正文/附录分界**：本机无 `pdftotext`/`qpdf`/pypdf（项目 env 无），无法逐页取文本定位“附录 A”起始页，故连“正文部分是否已 ≤30”也不能认证。
- 下一批最小改动顺序（不改 FIG 字节、不删负结果）：
  1) 把 `q1-targets`(32 行) 与 `q1-styles`(24 行) 移入 supportOnly（与 14.1 同一机制），预计 −4~5 页；
  2) 图高/表距显示级收紧（builder 需要新增 display 参数，纯显示不改 FIG），预计 −1~2 页；
  3) 若仍 >30，再合并重复的稳健性/证据说明段落，不删限制。
- 需要 builder 补一个 `--page-report`（用其 pypdf 逐页输出章节标题→页码），以便下一批认证“正文 ≤30、附录单独计”。

## 15 第四批：继续减重 + claim 引用一致性（2026-10-27T02:3xZ，**未完成页数验收**）

### 15.1 claim 引用一致性（已核对，无退休引用）

- 状态：`CLAIM-0056` active、`CLAIM-0057` superseded、`CLAIM-0058` superseded、**`CLAIM-0059` active**。
- 扫全台账：**没有任何 requirement coverage 或 claim 引用 superseded/retracted claim**（`bad refs: []`）；paper.md 不引 0057/0058，只引 0059。
- 其余 7 条 claim **未**批量 supersede（按本批 §一.3）；正文已保留其科学结论与限制，附录 C 给出证据类型/限制汇总。

### 15.2 再移两张长表（已完成，数据行未删）

- `q1-targets`（30 维逐维，含 Skill 为负的恶化维度）、`q1-styles`（22 风格，含 Faro/Brut/Flanders old brown/Scotch 小样本行）→ `paperIncluded=false / supportOnly=true`，正文改为指针段并明示“负结果与小样本行逐条保留在支撑材料”。
- 现 `supportOnly` 共 4 张：q1-styles、q1-targets、q2-full-top3、q2-extended；正文内联表 **15** 张。
- 校验：`paper_tables.py --verify` **19/19**；检查脚本 **0 violations**（内联四方 sha / supportOnly 文件+INDEX sha / 不得同时内联）。

### 15.3 当前 SHA

| 产物 | sha256 |
|---|---|
| `report/paper.md` | `e61b2410b9aee9fe9a5753096535a76e55c3b9a95743db2604e687c26a6f4b81` |
| `report/tables/INDEX.json` | `6a78f7ce8d0da89451efbe2de925e453ceccf6412513f8ef313b0452e9309605` |
| builder / header | `6f62c823…` / `cf1fe462…`（本批未改） |
| 上一轮预览（减重前） | RENDER-0011 / preview.pdf `318b3b9c…` / **36 页** |

### 15.4 未完成（阻断本批 A 结论）

- **本批未重新 render/构建**：paper.md 已变（15 内联表），按纪律必须重新 `render`（旧 rendered.md 已过期，**不得**用旧 RENDER 冒充）。
- 因此**没有新的实测页数**；上一轮 36 页不能用来宣称通过。预计本轮两张表移出可回落约 4–5 页（→ ~31–32），仍可能 >30，需继续执行 §五 的顺序（显示级收紧 → 再评估）。
- 下一步命令序列（下一批首件事）：
  1. `python src/build_paper.py --check --source report/paper.md --number-sections`（应仅剩 78 个 metric 未解析这一项预期拒绝）
  2. `modeling_deliver render`（input `report/paper.md`，output `.rework/previews/preview-C/rendered.md`）→ 记录新 RENDER ID
  3. `--build --pdf --source …/rendered.md --outdir .rework/previews/preview-C --number-sections --wide-tables wrap --no-caption-ids`
  4. 读 log 的 `Output written on … (N pages)`；若 >30，按 §五 继续（显示级参数/合并重复说明），每轮记录页数与 SHA。

## 16 第五批：preview-C 实建（2026-10-27T02:5xZ）

- RENDER-0012：input `report/paper.md`（`e61b2410…`）→ `.rework/previews/preview-C/rendered.md`（`deda7968…`），88 占位符全解析、0 stale、0 warning。
- check（渲染源）：**30 pass / 0 fail / 0 warn**；inline 15/15、supportOnly 4/4、图 9/9、claimsExpanded。
- build：`preview.tex` `8676ff4c…`、`preview.pdf` `1a428380…`（**33 页**，0 error）。
- 判定：**33 > 30 → 仍 BLOCKED**。需再减约 3 页；下一轮按 §五 顺序只做一种可审计调整（显示级收紧或合并附录 C 重复说明），改后必须重新 render（当前 RENDER-0012 即失效）。
- 旧正式产物 `report/paper.tex|pdf|rendered.md` 未覆盖；预览未绑定 artifact。

## 17 第六批（续跑会话）：DRAFT 交付链收口（2026-10-27T03:2xZ）

**范围**：只完成当前 DRAFT 交付链；不重做实验/ROB/claim/图/表/预览减重。

### 17.1 恢复与核对
- `status`：revision 4658；`config` in_sync（acceptedVersion=2，raw `728811fc…`、protocol `215d0941…`）；`runControl` RUN-0003 `running`（未重复 begin、未 stop）。
- `report/paper.md` sha = `e61b2410…`（与任务书一致）；preview-D **30 页**（pypdf 实测）；`src/build/header.tex` = `0d35a964…`（含 display-only tightening 17 行）；`paper_tables.py --verify` **19/19**；一致性脚本 **0 violations**；FIG-0032–0040 全 active 且字节 sha 9/9 匹配；无 PENDING、无退休引用。

### 17.2 独立 delivery review（三轮，均由非根 reviewer 写台账）
- **REV-0082**（findings：4 major + 8 minor）→ 修 `src/build_paper.py` 题注下标 off-by-one（0-based `cap_idx` vs 1-based `idx`）、paper.md 附录 B.3(1)/(2)/附录 C/附录 B H2 编号。
- **preview-E**（RENDER-0013，30 页）→ **REV-0083**（8 minor，0 major/critical）。
- **REV-0084**（TGT-0003 复审，3 minor）、**REV-0085**（requirements-coverage，1 major + 2 minor）。F1 major：REQ-0002 高估 → 在 paper §2.4/§5.2 披露 2.csv 网络偏离（并在 REQ-0007 把已 superseded 的 FIG-0001 改指 active FIG-0033）。
- **REV-0086**（最终确认，1 critical + 2 major + 2 minor，全在文档层）→ 重写 `DELIVERY-NOTES.md`（v6 DRAFT）、重写 `REPRODUCE.md`（v6）、旧包移入 `delivery/archive/`、新增 `AI-USAGE.md`；F1–F5 **全部 resolved**，REV-0086 open findings = 0。

### 17.3 质量刷新（实跑）
- `quality-plan auto:true` → `quality-stale` → `quality-run` → `quality-report`：**45 项 = 33 passed / 1 failed (QC-0033) / 11 needs_review / 0 stale**（report 快照另含 1 个 optional stale：QC-0031 runcontrol-budget）。
- **QC-0020 已 passed**：论文不再引用 6 条退休 claim（0 命中），其后“latest review stale”的原因由 REV-0084/REV-0085 刷新而消失。
- QC-0033 保持 failed（EXP-0017/0018/0026/0035/0036 缺 feature manifest，禁止 retrofit）；Q1/Q3 selection 保持 provisional；REQ-0004/0005/0007 保持 insufficient_data；无注册 split 的 11 项 metric-recompute 保持 needs_review。

### 17.4 freeze 被拒（真实阻断）
- `modeling_project {action:"freeze"}` → **拒绝**：`VMU_PACK_MODELING_CONTEST_GATE_STAGE_SKIPPED`“cannot freeze before validation: …required check … has not passed”。
- 未 advance、未手改 frozen、未降门禁；台账 `frozen` 仍 2026-10-24T14:36:58Z / revision 2731 / cfgV1 / 6 条 retracted claim / 29 张旧图 / MODEL-0004·0012·0013。
- 因此 RENDER-0016 的 `freeze` 字段是 **legacy 继承值**，不是“冻结后的正式 render”。

### 17.5 正式产物（工具允许的 DRAFT 路径）
| 项 | 值 |
|---|---|
| paper.md | `95fd30f0f1908a2bb6575dbf47a2a260f5dec00e733c699b9369821503897416` |
| RENDER-0016 | `report/rendered.md` = `c5cf631d327df4cedee02368fc480af5120e9dcd9937a6d4169197d6e2dd6245` |
| ART-0007（tex） | `report/paper.tex` = `e874741b348e191c01bf19a3884cf59c412b528ced996059626d9cfeef842591` |
| ART-0008（pdf） | `report/paper.pdf` = `952b73e341d6411ae28bd658045af1a53edf22824763570801a8a0e01076e73e`（30 页） |
| 中间记录 | RENDER-0014（preview-F）、RENDER-0015 + ART-0005/0006（§7.3 修改前）——历史保留 |

### 17.6 版式与视觉
- 30 页；PDF 1–3 无页码（1 标题+摘要+DRAFT、2–3 目录），正文页码 1（p4）→27（p30）；页眉 0/30；图 1–9、表 1–15 连续；附录 B=B.1/B.2/B.3。
- 逐页视觉验收 **30/30**（pypdf 拆页 + sips 1050px + 墨迹包围盒 L/R 10.4%、T≈8.1%、B=4.2%，无触边/空白/旋转）；证据 `.rework/acceptance/final2/`。

### 17.7 交付检查与打包
- `modeling_deliver check`：`final=false`、`draft=true`、`engineeringComplete=false`（59/62，失败为 selection:Q1、selection:Q3、checkpoints 34 阻断）、`qualityPassed=false`、`checkpointsPassed=false`、`submissionReady=false`，blocking 16 项。
- DRAFT 包：`delivery/20261027-111607-DRAFT/` + `.tar.gz`（`d84dcbe6…`），504 文件、SHA256SUMS 503/503 复算一致、manifest `final=false`/`draft=true`；tex/pdf 与 ART-0007/0008 逐字节一致。
- 支撑材料包：`delivery/20261027-111607-DRAFT-SUPPORT/` + `.tar.gz`（`bb8c42aa…`），19 文件、19/19 sha 一致；含 198 份 QP 证书、transfers(396 行)、transfer_constraints(15,048 行)、zspace 与 4 张 supportOnly 表。
- 旧包移入 `delivery/archive/`；`delivery.contest=null` → 提交 skip，未自动提交。

### 17.8 下一批（若要转 FINAL）
必须先在**验证侧**真实补齐 Q1/Q2/Q3 的 required 检查（含注册 split 或明确适用的替代协议），使 freeze 不再被 `GATE_STAGE_SKIPPED` 拒绝；`QC-0033` 需在**实验侧**补 feature manifest（不得 retrofit）；Q1/Q3 selection 需凭新证据改 `validated`。在此之前，任何“FINAL”都属伪造。
