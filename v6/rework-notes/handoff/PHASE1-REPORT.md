# PHASE1-REPORT.md — 插件 2.8.10 源码工程修复报告（第一阶段）

> 执行者：Lead（默认编程预设 / 普通工程会话）。
> 本阶段只做插件源码修复、隔离测试、版本打包与安装交接；**没有启动数学建模流程，也没有使用 Vibe Math Unify / Vibe Math Modeling 预设**。
> 第二阶段（实际项目回归与交付恢复）必须在新会话用 `Vibe Math Modeling` 预设执行，交接书见 `PHASE2-HANDOFF.md`。
> 原始项目当前仍为 `final=false`，本报告不宣称第二阶段通过。

## 1 定位与对应关系

| 项 | 值 |
|---|---|
| 插件源码仓库 | `/Users/baozhashizitou/Documents/MATHORCUP/work/modeling-quality-lifecycle-2.8.7`（git branch `main`） |
| 修复前 HEAD | `99d6dba`（2.8.9，`buildId=2.8.9+7384150`） |
| 已安装插件（修复前） | `~/.dsh/profiles/desktop/node_modules/dsh-vibe-math` = 2.8.9，与源码仓库 **逐字节一致**（仅仓库多出 `docs/audit`、`vmu` 两个仓内目录） |
| AGENTS.md | 已读；遵守“能力在内核/策略在 pack”“拒绝具名”“新增文件进 package.json#files 与 installer 托管清单”“提交只由 Lead” |
| 修复后版本 | **2.8.10**，`buildId=2.8.10+cefef8a`，提交 `cefef8a`（修复）+ `447b438`（包内 buildId） |
| 打包 | `dsh-vibe-math-2.8.10.tgz`，sha256 `6462db91483d6fc334c7fb184400ea06a728896f6397718ba5aaa73857d210c5`，854 文件 |
| 留档 | `/Users/baozhashizitou/Documents/MATHORCUP/outputs/质量问题修复工程交付-2.8.10/包/` |

> 注：本会话工作区被限制在建模项目目录，插件仓库与 `~/.dsh` 的写操作均以显式 `danger-full-access` + 中文理由执行；`node_modules` 未做任何临时手改（只通过公开安装机制更新）。

## 2 三处缺陷的修复

### 2.1 图版本冲突（FIG-0025/0030、FIG-0027/0031）

根因：同一作品的新旧两条图记录共用路径、sha256 不同；`delivery.check` 遍历全部记录逐条按字节核验，旧记录永远 STALE，且 2.8.9 没有删除/退役图记录的公开动作。

修复（公开、可审计、只追加）：

- 新动作 `modeling_deliver {action:"figure-retire", figureId, reason, supersededBy?}`：`reason` 必填；给 `supersededBy` 时旧记录 `status:"superseded"` + `supersededBy` + `supersededReason` + `statusHistory`，替代记录获 `supersedes[]`；不给则 `status:"retired"` + `retiredReason`；id/path/sha256/createdAt 不重写；重复退休/自指/同字节替代均具名拒绝；支持 `expectedRevision` CAS。
- 新动作 `modeling_deliver {action:"figure-archive", figureId, archivePath, reason?}`：仅退休记录；归档路径必须独立且文件字节必须等于登记 sha256（否则 `DATA_HASH_MISMATCH`，零写入）；旧路径进 `pathHistory`，登记 sha256 不变。
- `registerFigure`：同路径+同字节幂等；**同路径+不同字节以 `FIGURE_PATH_CONFLICT` 具名拒绝**（2.8.9 的缺陷无法再经 API 复现）。
- `delivery.check`：活跃图逐条严格核验 SHA；退休图给显式 `SUPERSEDED`/`RETIRED` 历史行（pass，注明未按字节核验并写出旧→新关系与原因）；历史遗留“同路径两条 ACTIVE”新增 `figures:paths` 具名失败行。
- `freeze` 只冻结活跃图；`render`/占位符解析/`renderBindingReasons` 拒绝引用退休图；`packageDelivery` 只为活跃图复制当前图，退休记录进 `figures.json#retiredFigures`，可核验旧字节复制到 `figures/history/<FIG-id>-<basename>` 并进 `SHA256SUMS`（不可核验时 `packagedAs:null` + warning，绝不伪造）。
- 统一谓词：`runtime/assertions.js` 新增 `RETIRED_FIGURE_STATUSES` / `isRetiredFigure` / `liveFigures`；`runtime/delivery.js`、`runtime/service.js`、`runtime/quality/ledger.js` 共用同一实现（消除两份镜像定义）。

### 2.2 delivery review 无改动也 stale

根因：写入时 `binds=null`、fingerprint 用 `stableHash({objectType,objectId,boundVersion:null})`；刷新时退回 `fingerprint(svc,deps)` 的另一套结构 ⇒ 每次 refresh 必 stale。

修复：`objectType:"delivery"` 有了真实的**交付范围版本** `deliveryScopeVersion(svc,ledger)`，写入（`addQualityRecord`）与刷新（`refreshQualityStaleness`）调用同一函数。范围 = `report/paper.md` sha256 + 活跃 claim 版本 + 活跃图版本 + 已接纳协议身份 + `src/build_paper.py` sha256；**有意排除** renders / rendered.md / tex / pdf / paperArtifacts / frozen / reviews（它们是评审与交付的输出/事件，已由 render→freeze→artifact 绑定，纳入会造成 render/freeze/review 循环失效）。刷新用 `describeDeliveryScopeChanges` 具名说明变了哪个输入。legacy `binds=null` delivery review 不被跳过，而是具名 stale（"predates delivery-scope binding…"）。

### 2.3 已退休对象的旧 review 被当作永久阻塞

根因：`critical-findings` 对每个对象都要求“最新 review 必须 fresh”，包括早已 superseded/retracted、且已不在活跃交付中的旧 claim。

修复：用 `runtime/assertions.js` 的统一退休谓词（claim: `isRetiredClaim`；figure/contract: supersede 词汇）。最新 review 为 stale 的**已退休**对象进 `retiredStale` 历史，不阻塞；**活跃**对象的 stale 最新 review 与未解决 critical finding 仍严格阻断；退休对象若仍被当前正文 `{{claim:…}}`/`{{figure:…}}`、requirement coverage 引用、活跃 claim 证据链（含 target contract）引用，则 `DELIVERY_REF_MISSING` 具名失败（正文中的历史性文字提及不算引用）；检查依赖改为“派生的退休引用签名”，无关台账事件不使其失效。历史 review/finding 全部保留可见（`historicalStale`/`historicalFindings`）。

## 3 测试结果

### 3.1 新增回归套件（先失败后通过）

| 套件 | 未修复 2.8.9 基线 | 修复后 |
|---|---|---|
| `tests/modeling-contest-figure-versioning.test.mjs` | **35 passed / 38 failed**（缺 FIGURE_PATH_CONFLICT、`figure-retire`/`figure-archive` 不存在、freeze 冻结全部图、同路径异字节被静默接受…） | **73 passed / 0 failed** |
| `tests/modeling-contest-review-binding.test.mjs` | **111 ok / 50 failed**（无改动也 stale、退休 claim 假阻塞…） | **161 passed / 0 failed** |

### 3.2 受影响既有套件

quality 77/0、quality-lifecycle 15/0、quality-review2 26/0、claim-supersede 65/0、delivery 164/0、delivery-consistency 27/0、config-lifecycle 106/0、entry 19/0、gate 23/0。

### 3.3 modeling-contest 全类扫描与基线对照

`node tests/run-tests.mjs --no-temp-hygiene --only modeling-contest`：**24 套件，PASS 16 / FAIL 8**。
8 个失败全部是需要真实子进程的套件（`sandbox-exec: sandbox_apply: Operation not permitted`）。用**未修复的 2.8.9 原始安装包**跑同样 8 个套件，失败画像逐项相同（final 15/15、quality-tools 13/7、stale 6/5、scenarios 8/2、其余 Node 崩溃/SKIP 相同）——**非本轮引入**。日志：`.rework/verification/t1-modeling-contest.log`。

### 3.4 其它门禁

- `scripts/release-check.mjs`：**ALL CHECKS PASSED**（版本三处一致、zh/en 发布说明 8 节顺序、清单登记、无 CRLF、真实 `npm pack`）。
- `scripts/regen-all.mjs --check`：**16/16 in sync**（新增测试改变派生计数，已 `--write` 同步 6 份文档）。
- `scripts/preflight.mjs` / `scripts/check-docs.mjs`：仍有 **预先存在** 的 D16/D6/D11 提示与 `DOC LINT: FAIL`；已实测**未修复的 2.8.9 上完全相同**，与本轮无关（本版未改 kernel 文档契约）。
- T1 全量门禁在本机被仓库内遗留的 `D:\_tmp` 临时根阻塞（`mkdtemp 'D:\_tmp/...' EPERM`）；`--no-temp-hygiene` 可绕开，属环境问题。

## 4 打包、安装与“已修复版本已加载”的边界

- 包：`dsh-vibe-math-2.8.10.tgz`（sha256 见 §1），解包核对 `version=2.8.10`、`buildId=2.8.10+cefef8a`、
  `modeling_deliver` 动作枚举含 `figure-retire`/`figure-archive`、运行文件与源码仓库逐字节相同。
- 安装：通过公开 `plugin_manager install_bundle` 安装到 `desktop` profile；`~/.dsh/profiles/desktop/package.json`
  的 `dsh-vibe-math` 已指向 2.8.10 tgz；已安装目录 `package.json.version=2.8.10`。
- **重要边界**：同一运行进程内升级触发激活诊断
  `SyntaxError: … '../assertions.js' does not provide an export named 'isRetiredFigure'`
  ——这是运行中宿主缓存的 2.8.9 ESM 模块（旧 `assertions.js` 已先被加载，升级后新 `ledger.js` 从缓存取旧模块）；
  文件本身正确：**新进程**导入已安装包成功，动作枚举包含新动作。
  ⇒ **必须完全退出并重启 DSH**，新会话才会加载 2.8.10。第二阶段会话内用
  `modeling_deliver {action:"figure-retire", figureId:"FIG-9999", reason:"version probe"}` 应返回 `NOT_FOUND`
  （旧代码会返回 `unknown deliver action`）；不满足即停止，不得宣称修复验证通过。

## 5 隔离副本端到端验证（用已安装 2.8.10 的公开工具）

环境：`/tmp/rework-2.8.10/verify-2.8.10/project`，由基线快照（ledger rev 1985、frozen 13:34:30Z）重建的**副本**；
原始项目从未被本阶段的工具调用写入。逐步 receipt 证据：`.rework/verification/isolated-2.8.10/`。

| 步骤 | 结果 |
|---|---|
| 迁移前 check | `final=false`，blocking 含 `figure:FIG-0025`、`figure:FIG-0027`、`figures:paths`×2、`report:render-binding`、`report:freshness`、`quality:requirement-coverage`、`quality:critical-findings` |
| figure-retire ×2 + figure-archive ×2 | 全部 ok；FIG-0025/27 = `superseded`、`supersededBy`=FIG-0030/31、旧 sha256 保留、`pathHistory` 保留旧路径；FIG-0030/31 仍 `active` 且严格核验 |
| claim link | CLAIM-0019→VAL-0037/0038/0039；CLAIM-0021→VAL-0040/0041/0042/0043；CLAIM-0022→VAL-0040/0041/0043 |
| 新 delivery review | `REV-0039`，`binds={kind:"delivery",version:…}` 非空；连续两次 `quality-stale` 后仍 `stale=false`（无内容改动）；旧 REV-0010/0026/0038 具名 stale |
| quality-run | **27 passed / 5 n/a / 0 stale / 0 failed**；9 条退休 claim 旧 review 进 `retiredStale` 历史 |
| freeze → render → build → artifact | 新 frozen；`RENDER-0007`（inputSha `687d097a…`）；`ART-0003`(tex)/`ART-0004`(pdf) 绑定 RENDER-0007 |
| deliver check（两次） | **final=true；engineeringComplete/qualityPassed/checkpointsPassed 全 true；blocking=[]** |
| package | `delivery/20261024-221010`，四布尔全 true、`draft=false`；archive sha256 `44d35fb6…`；`figures/history/` 两份旧图（sha 57e3e864…/299df07e…）在包内且进 SHA256SUMS；`figures.json#retiredFigures` 含状态/旧→新/`packagedAs` |
| 新 PDF 几何复测 | 18 页；全部页面墨迹 xmax ≤ 版心右界 +0.69pt（F1/F2 消），Figure 13 图注为数学模式 `\(\in\)`（F3 消） |

## 6 REV-0038 的独立复验结论（由独立子代理 pdf-audit 对当前 RENDER-0006 实测）

| # | 复验结论（当前 PDF/tex/paper） | 第二阶段处置 |
|---|---|---|
| F1 major | **ALREADY FIXED**：§8 已为条目列表，p15 第 9 项长数字 x1=399.31/521.77pt < 版心 555.31pt，无裁切 | review-resolve 记录实测证据 |
| F2 minor | **PARTIAL**：§4.4 仍 overfull（p4 xmax 587.50pt，+32.19pt，未丢字） | 已备好 paper.md 数学拆分（`apply-paper-fixes.py`），重渲染后复测 |
| F3 minor | **ALREADY FIXED**：`build_paper.py` U+2208→`$\in$`，tex 中 U+2208=0，p14 图注正常 ∈ | review-resolve 记录证据 |
| F4 minor | **STILL PRESENT**：§6.5 正文段与 CLAIM-0022 段重复同一组数字，§9 再重复 | 脚本已删重复段并改为指向登记结论 |
| F5 minor | **PARTIAL**：点名 4 处已修；仍有手写 1.0（§摘要/§9）、`delta = 0`、审计/阈值常数无来源 | 脚本改占位符/名称/来源指针（数据常数标注注册来源） |
| F6 minor | **ALREADY FIXED**：REPRODUCE §2.6=v3/v4、§2.11=当前 6 条 active claim | review-resolve 记录证据 |
| F7 minor | **PARTIAL**：CLAIM-0018 已链 VAL-0032–0036；0019/0021/0022 为空 | 按实际适用性链接（见 §5 与交接书 §3.3，不机械照抄） |

PDF 绑定核对：paper.md `c7d9cd2c…`=RENDER-0006.inputSha256；rendered.md `42fa002b…`=RENDER-0006.sha256；
paper.tex `f102ef84…`=ART-0001；paper.pdf `31b72aed…`=ART-0002；14 图注/图 sha 与台账逐字一致。

## 7 原始项目完整性（第一阶段未污染）

- `report/paper.md` = `c7d9cd2c…`（快照值；第一阶段为准备交接做过编辑，已**逐字节还原**）；
- `contest.yaml` = `2ce0b2c3…`；`figures/q3_defect_exceedance.png`=`4d6c13f8…`、`q3_pareto.png`=`a404a27f…`（与台账活跃记录一致）；
- `delivery/20261024-DRAFT.tar.gz` = `74a63e9d…` 未变；DRAFT `delivery-status.json` 仍 `final=false`；
- 台账内容（除 `revision`/`updatedAt`/`events`/`quality.runControl` 的宿主 usage 噪声外）与快照**哈希相同**；
  当前 frozen 仍为 `2026-10-24T13:34:30.261Z`（未被重写）；
- 项目根目录未新增非隐藏文件（只新增隐藏 `.rework/`：快照、复现证据、pdf 复验、隔离验证证据、交接材料）。

## 8 残留风险（如实）

1. 运行中 DSH 必须重启才能加载 2.8.10（§4）；重启前的任何“通过”都不算数。
2. delivery review 范围把 `report/paper.md` 与 `src/build_paper.py` 作为交付约定；其它构建路径不纳入范围。
3. 退休图 id 在交付层之外的少数消费者（`runtime/claims.js` 图引用、`runtime/validation.js` 图身份复核、`runtime/workbench.js`）未改动；本项目的 render/check/freeze/package 已全部覆盖。
4. `quality/engine.js` 的通用 review 状态投影仍会统计退休对象 stale review 数量（历史展示），最终判定由 `critical-findings` 负责。
5. 本机 macOS 上部分依赖真实嵌套 Seatbelt/Windows 路径的既有套件失败（已证明与修复前基线逐项相同）。

## 9 第二阶段交接

见 `.rework/handoff/PHASE2-HANDOFF.md`（含启动步骤、版本确认探针、逐条公开命令、验收标准、红线与可直接粘贴的第二阶段提示词）。
本会话**未执行**第二阶段，**不宣称**实际项目的最终交付已通过；原始项目保持 `final=false` DRAFT。
