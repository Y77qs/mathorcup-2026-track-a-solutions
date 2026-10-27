# Vibe Math Modeling 2.8.10 正确使用指南

适用环境：DeepSeek Harness（本机 0.2.1-rc.2）、**dsh-vibe-math 2.8.10**（`buildId=2.8.10+cefef8a`）、preset **Vibe Math Modeling**（`vibe-math-modeling`）。
本指南只描述 2.8.10 真实实现并**真实测试过**的公开接口；2.8.10 是 2.8.9 的**补丁版**（图版本迁移/退役、delivery review 版本绑定、退休对象审查语义），模型 API、默认值、数据格式与目录结构不变。

**最重要的一条（不变）：先把项目配置写完整，再 `init`。初始化之后要改配置，必须走公开的 `config diff` → `config accept` 事务，不能直接改文件当作协议已变更。**

> 2.8.9 指南仍然适用：`/Users/baozhashizitou/Documents/MATHORCUP/outputs/质量问题修复工程交付/02_Vibe-Math-Modeling-2.8.9-正确使用指南.md`。
> 本文件在它之上更新了 §0（安装/重启/版本确认）、§1（2.8.10 变化）、§9（审查绑定与退休对象）、§10（图版本，新增）、§14（本版验证范围）。
> 2.8.10 发布说明：`outputs/质量问题修复工程交付-2.8.10/包/RELEASE-NOTES-2.8.10.md`（英文 `.en.md`），插件包内 `docs/release-notes/` 同版。

## 0. 安装、升级与 identity（2.8.10 有变化）

- 安装包：`dsh-vibe-math-2.8.10.tgz`（SHA-256 见 `包/dsh-vibe-math-2.8.10.tgz.sha256`）。
- 安装前核对：`shasum -a 256 dsh-vibe-math-2.8.10.tgz` 与随包 SHA 一致；解包后至少确认
  `vibe-math-vmu/packs/modeling-contest/runtime/assertions.js`（含 `isRetiredFigure`/`liveFigures`）、
  `runtime/delivery.js`（含 `retireFigure`/`archiveFigure`）、`runtime/quality/ledger.js`（含 `deliveryScopeVersion`）存在。
- 本机 `desktop` profile 已安装 2.8.10：`~/.dsh/profiles/desktop/node_modules/dsh-vibe-math`，依赖指向
  `file:/Users/baozhashizitou/Documents/MATHORCUP/outputs/质量问题修复工程交付-2.8.10/包/dsh-vibe-math-2.8.10.tgz`。
- **升级后必须完全退出并重启 DSH**。同一运行进程内升级不会重载 ESM 模块：仍运行的宿主会继续用旧代码，
  激活诊断可能报
  `SyntaxError: The requested module '../assertions.js' does not provide an export named 'isRetiredFigure'`
  ——这是**旧模块缓存**，不是包损坏。判据以“新进程/重启后能否导入 + 会话内动作存在”为准。
- **三重 identity 核对**（做任何项目动作之前）：

  ```sh
  # ① 磁盘版本
  INST=~/.dsh/profiles/desktop/node_modules/dsh-vibe-math
  node -e "const p=require(process.env.HOME+'/.dsh/profiles/desktop/node_modules/dsh-vibe-math/package.json');console.log(p.version,p.buildId)"
  # 必须: 2.8.10 2.8.10+cefef8a

  # ② 新进程导入（不依赖运行中的宿主缓存）
  node -e "import(process.env.HOME+'/.dsh/profiles/desktop/node_modules/dsh-vibe-math/vibe-math-vmu/packs/modeling-contest/tools.js').then(m=>{const d=m.MODELING_TOOLS.find(t=>t.name==='modeling_deliver');const P=d.parameters.properties||d.parameters;console.log(P.action.enum)})"
  # 必须含 figure-retire 与 figure-archive
  ```

  ③ 会话内探针（只读、不写台账）：

  ```
  modeling_deliver {action:"figure-retire", figureId:"FIG-9999", reason:"version probe"}
  ```

  返回 `NOT_FOUND`（no figure FIG-9999）⇒ 新动作已加载；返回 `unknown deliver action` ⇒ 仍是旧代码，**停止并重启宿主**。
- 不要把“包名/版本号”当作行为证明；行为以 `status`/`check` 回执、动作枚举与本指南 §14 的测试为准。
- **不要**把 `Vibe Math Unify` 当作 `Vibe Math Modeling` 使用；覆盖式重装前先备份 profile 的 `package.json` 与旧 tgz，回滚就是显式装回旧版 tgz 并重启。

## 1. 2.8.10 相对 2.8.9 的变化速查

| 领域 | 2.8.9 | 2.8.10 | 需要迁移吗 |
|---|---|---|---|
| 图的版本 | 同路径重新登记不同字节会被**静默接受**；同一路径可能对应两条记录 | 同路径不同字节以 `FIGURE_PATH_CONFLICT` 具名拒绝；新版本必须**独立路径**；新增 `figure-retire`/`figure-archive` | 旧台账无需迁移；若已有“同路径两条 ACTIVE”会用 `figures:paths` 具名阻断，按 §10.4 迁移 |
| `delivery.check` 的图 | 遍历全部记录逐条按字节核验，旧记录永远 STALE | 活跃图**严格**核验 SHA；退休图给显式 `SUPERSEDED`/`RETIRED` 历史行，不再字节阻断 | 无 |
| `freeze` | 冻结**全部**图 id | 只冻结**活跃**图 id | 重新 freeze 即可 |
| delivery review | 写入 `binds=null` 但指纹用另一结构，刷新必 stale | `binds` = 真实交付范围版本；写入/刷新同一函数；legacy `binds=null` 被具名 stale | 旧项目做一次当前范围的新 review |
| 退休对象审查 | 最新 review stale 一律阻断（包括已 superseded/retracted 对象） | 退休对象进 `retiredStale` 历史；活跃对象仍严格阻断；仍被当前正文/coverage/活跃证据链引用的退休对象**具名失败** | 无（历史 review 保留） |
| 交付包 | 只含活跃图 | 另含 `figures/history/`（可核验旧字节）+ `figures.json#retiredFigures` | 无 |
| 默认值/配置/台账 schema/目录 | — | **不变** | 无 |

## 2. 先选择正确入口

| 现在的情况 | 正确操作 |
|---|---|
| 全新项目，没有 config 和 ledger | 第 3 节准备**最终**配置 → `init` 一次 |
| 已初始化，`config status` 显示 `in_sync` | 不再 init；`status`/`probe` 核对后继续 |
| 已初始化，`config status` 显示 `changed` | 先 `config diff` 看影响面；合法变更就 `config accept`，否则恢复文件；**不要**在 drift 下登记新实验 |
| 旧项目（2.8.6 及以前）初始化后改过配置 | `status` 会显示 `needs_review`；`config accept` 建立**新的已知版本**，旧记录保持 unknown，需重做受影响证据 |
| 2.8.9 项目（含本仓库 v3 项目）升级到 2.8.10 | 无需重新 init；先重启宿主 + §0 三重核对；按 §10.4/§9.1 处理历史图与历史 delivery review |
| 已经有 final 包 | 核对正文/refs/render/包是否同版；不要为重复“收尾”继续训练 |

不要选择 **Vibe Math Unify** 来代替 **Vibe Math Modeling**。

## 3. init 之前：把配置一次写完整

### 3.1 准备目录与题面

```text
NEW_PROJECT/
  problem/statement.md
  data/raw/
  contest.yaml        # 或 contest.json（项目内只保留一份）
```

题面转成可逐字引用的 Markdown；原 PDF 保留为来源。附件保持原样。先读真实表头、主键、缺失、单位、尺度、标签来源与跨表关系；题面与附件冲突先记录，不能直接信附件说明或文件名。

此时确定：项目 ID、题面相对路径、Python 绝对路径、语言、任务类型、全局评价默认值、交付格式与质量策略。多小问的指标稍后通过 `plan` 与各问 evaluation 契约登记，不靠反复改全局 config。

### 3.2 配置安装与核对

2.8.10 **没有改 config schema**。可继续使用 2.8.9 交付目录里的 `验证脚本/准备与核对配置.mjs`（它读取真实 schema、拒绝覆盖已有 config、只写 config 与 `GUIDE-PREFLIGHT.json`，不初始化 ledger、不调用模型），也可以手写 `contest.yaml` 后用 `config status/diff` 核对。

至少核对：`projectId`、`problem.statement`、`runtime.python`（真实可用绝对路径）、`evaluation.taskType/primaryMetric/metricDirection`、`delivery.paperFormats`（需要 PDF 就同时声明 tex）、`quality.required=true`、`quality.robustness.maxHoldoutReuse`、预算字段。Python “存在”不等于依赖齐全，init 后仍必须看真实 probe 回执。

### 3.3 init 一次，接受版本 1

```json
{"action":"init","projectDir":"/绝对路径/本次新项目","python":"/绝对路径/本次Python"}
```

工具名是 `modeling_project`。回执里核对 `configVersion=1`、`configProtocolSha256`、projectId、revision 与 probe。init 会写入**已接纳版本 1**（完整配置快照 + 原始 SHA + 科学协议 SHA），这是后续所有证据的协议身份来源。

## 4. 配置生命周期：公开事务（与 2.8.9 相同）

### 4.1 读懂 status

```json
{"action":"status","projectDir":"/绝对路径/本次项目"}
```

关键字段：`configState.state`（`in_sync`/`changed`/`unreadable`/`needs_review`）、`configChanged`（每次都与已接纳版本比较）、`configState.accepted`（版本/raw SHA/protocol SHA）、`configState.current`、`configState.error`（不可解析时的具名错误，不会用缓存配置冒充正常）。

配置不可解析时，ledger-only 操作（如 `plan`）仍可读；但新证据写入、quality、render、freeze 会具名拒绝。

### 4.2 diff（只读）

```json
{"action":"config","subaction":"diff","projectDir":"/绝对路径/本次项目"}
```

返回 `changes[]`（path/class/before/after）、`class`（`protocol`/`policy`/`resource`/`presentation`）、`impact.scientificChanged`、`impact.willInvalidate`、`warnings`、`applyRequires.expectedRawSha256`/`expectedRevision`。diff **不写任何东西**。

### 4.3 accept（CAS 事务）

```json
{"action":"config","subaction":"accept","projectDir":"/绝对路径/本次项目",
 "expectedRawSha256":"<diff 显示的 64 位 sha>","expectedRevision":123,
 "reason":"为什么这个变更是合法的（例如：题面第 2 页抄写错误，容差未变）"}
```

三个参数缺一即拒；台账锁内重新读取并计算 sha；记录旧/新配置、版本、原始 SHA、四类身份与原因，**每次转换另记 `acceptanceEvents`**（含回退：kind/from-to 版本与 SHA/reason/diff/CAS 身份）。科学协议变化按名失效依赖证据（只写 stale 标记/原因，不改旧记录内容与哈希）；资源/展示变化不作废科学数字，也**不会**重置 run-control 停止、预算或 holdout 曝光历史。当前文件已等于已接纳版本时返回 `alreadyAccepted:true`。

### 4.4 旧项目（缺历史快照）

- 当前文件仍与初始化哈希一致 → 自动推导可信版本 1（`legacyDerived:true`，`in_sync`）；
- 已不一致 → `needs_review`；合法恢复：`config diff` → `config accept` 建立新版本往前走；旧记录保持 unknown，但不再以项目级标签永久阻断，只有当前仍被引用的旧记录按名阻断；
- 旧 render 会标记 `LEGACY_UNBOUND`（skip），不能当作“当前已绑定”。

## 5. 问题、数据与契约

### 5.1 题意登记

逐问登记：问题 ID、目标、输入、输出、约束、评价办法、指标方向与证据范围。每条原子要求从真实题面逐字引用，建立 source anchor。原始 0–6 标签不可恢复时 mapped grade 必须标为派生量；资料不足如实登记，不能改目标/题意凑覆盖。

### 5.2 原始附件、清洗版本与划分

- 项目外附件先用 `modeling_data action:"import"` 显式复制并核对 SHA；`inventory` 继续用项目内路径。
- 用 `profile` 读真实字段；清洗脚本真实运行后，`register-clean` 提供 sourceFile、cleanedFile、cleaningScript 与**完整** fields/fieldsFile。
- 不写“其余 216 列”等占位字段；下游用真实 DATA/SPLIT ID。
- 不同目标分别登记数据版本；多输出任务的 targetColumns 必须是全部真实且不重复的列名。
- 有真实样本 ID 就按 ID 对齐；只有确认用位置编号时才声明 `rowIdMapping:"positional"` 并保存顺序哈希。
- 预处理/缺失填补/标准化/目标变换参数只在训练侧拟合。

### 5.3 目标契约与模型契约

目标契约区分 observed/transformed/rule-derived/algorithm-output/constraint，绑定真实小问与数据/完整 targetColumns，说明可得时点、允许结论与限制。模型契约需要可执行 formula、变量、单位、条件、真实约束与来自题面的 boundaryCases。

漏填后可以公开修订：`modeling_project {action:"quality", subaction:"contract-revise", contract:"model"|"target", contractId, ...}`；2.8.9/2.8.10 会追加 `revisions[]`（字段前后值、时间、原因）。实际科学内容变化会让绑定验证/审查 stale（正常保护）；只改 `note` 不会；空修订被拒绝。修订后重跑 `model-condition` 及受影响审查。

## 6. 指标与验证计划必须在运行前配好

| 任务 | 口径示例 | 主要产物 |
|---|---|---|
| 多输出同期估计 | MAE/RMSE/逐目标 R² 与明确聚合 | 真实 ID、逐目标预测、全部逐维结果 |
| 关联/Top-k | topk-jaccard、selection-frequency、rank-spearman | 完整维度×方法/重采样集合或排序 |
| 生成 | constraint-satisfaction、energy-distance、profile-spearman | 实际生成样本、绑定约束、参考分布 |

登记时对齐：小问 metric、evaluation.metricKey、emit_metrics 输出键、验证计划、claim refs、论文主结论。**没有自动 alias**：`holdout_mae_mean` ≠ `mae`，额外统计量需要自己的定义、可执行复算与审查。

多输出例：`evaluation.kind:"multi-output"`、`metric:"mae"`、`metricKey:"mae"`、`aggregation:"uniform-average"`；predictions 含 `y_pred__<真实目标列>`，targetColumns 覆盖全部目标。

候选运行前登记验证计划；按实际任务声明必检项（划分一致性、泄漏、主指标复算、基线对照、精确复跑）。优先修复最上游的具名 blocker：配置/字段/目标/metricKey 错时，停止下游 select/claim/freeze。

## 7. 基线、训练内部选模与精确复跑

1. 先注册真实基线；常数训练均值/中位数用 `constant-train-mean`/`constant-train-median`（可零特征），不照抄未验证的 family 别名。
2. 在训练内部 OOF/CV 比较候选；每个实验带真实 features、family、DATA/SPLIT、目标/模型契约与评价声明。
3. 实验登记时冻结：`freezeSources:true`、`dependenciesComplete:true`，**列全**实际辅助模块/bundle/标定依赖；声明不能替代 inputs 中确有文件及 SHA。
4. 每个实验使用自己的输出目录；不在执行中修改该实验的冻结代码。
5. 首次受保护评估之前锁定选择办法、阈值与报告范围；validated 选择必须通过所需验证，provisional 继续是草稿。
6. 精确复跑指定真实原始 EXP ID，固定种子与协议；忙碌时等待同一排队作业，不反复注册替身。

### 7.1 失败、重试与幂等（沿用 2.8.9）

- 同一 `idempotencyKey` 且输入相同：`queued/running/succeeded` 直接复用同一 EXP；
- 上一次 `failed/timed-out/cancelled/interrupted`：相同调用只返回旧失败并带 `retryRequired:true`，不新建实验；
- 修复依赖后显式重试：`{"action":"register",...,"retry":true,"retryReason":"…"}`；新 EXP 记录 `attempt`/`retryOf`，旧失败保留；
- 真实输入变化（code sha/seed/params）不能借用同一 key 复用旧成功。

### 7.2 冻结依赖与 runner 沙箱（沿用 2.8.9）

- 真实 macOS Seatbelt 下：冻结快照目录允许“目录枚举 + 已登记文件读取”，原始项目 src、原始 holdout、未登记文件不可读；冻结 inputs 不可写。
- train-only 视图不携带任意项目文件；列名常量事前从真实表头程序生成 `src/target_columns.py` 并记来源 SHA，进入冻结依赖。
- 脚本真实接口：`from modeling_contract import seed, emit_metrics, emit_predictions, emit_output, emit_diagnostics`；没有 `emit`。主 metrics 只发有限数值；说明放 emit_output。
- OOF 复跑只证明 OOF 重复性，不能替代另一个 holdout 实验的精确复跑。

## 8. holdout 预算与稳健性

- 曝光按**实际样本**记录，不按 split 名字清零；同批数据换 seed/换 split ID/拆 dataset 都不恢复“未见”。
- baseline+候选都可能消耗曝光；确定性精确复跑与真正 OS 隔离的训练内部评估按各自协议处理，不自行假定豁免。
- 已耗尽时：合规训练内分析、真正未见数据，或保留探索性/资料不足与 DRAFT；不得加上限、删记录、反复重分直到绿。
- 预注册顺序：`robustness-plan-add` → 参考/扰动实验 → `robustness-plan-execute` → 质量复算与独立审查。执行过的计划不能改阈值。
- 负结果按预登记 ROB 范围判定：执行有效与假设成立分开报告；同范围正面稳定性断言必须 supersede/retract 或修正证据，不能靠加一条 negative_result 洗掉失败判据。
- 退休即历史：`supersede`/`retract` 后的旧 claim 保留 id/refs/状态历史，不再作为当前断言阻塞；旧 coverage 不自动转移，必须显式重映射并复审。

## 9. claim、要求覆盖与独立审查（2.8.10 语义有变化）

- claim 等证据稳定后再创建；用 `evaluation.metricKey` 引用主指标；写清 claimType、适用范围、targetContractId、limitations；负结果用 `claimType:"negative_result"` 并用 `appliesToPlanId:"ROB-0001"` 精确绑定。
- requirement-map 按原题逐条映射；负结果与 insufficient_data 分别登记。
- 分别取得必要独立审查（目标血缘、要求覆盖、关键 claim、稳健性/模型条件、delivery）。审查必须来自真实不同上下文/成员；根代理不能自宣独立或代填 passed。findings 修正后由审查者复审。
- **未解决的 critical finding 必须显式 resolve**：后续 passed review 不会自动清除早期非 stale review 上的未解决 critical；用 `quality review-resolve`（reviewId+findingId+resolution）记录后才恢复。
- 质量计划在需要新增检查对象时更新；之后按 checkIds/类型重跑受影响项并读 report。

### 9.1 delivery review 的版本绑定（2.8.10 修复）

`objectType:"delivery"` 的 review 现在绑定一个**交付范围版本** `deliveryScopeVersion()`，写入与刷新调用同一函数。范围（命名分项）：

1. `report/paper.md` 的 sha256；
2. 活跃 claim 的对象版本；
3. 活跃 figure 的对象版本 + 记录 sha256；
4. 已接纳协议身份（`configProtocolSha256`）；
5. `src/build_paper.py` 的 sha256（PDF 构建脚本）。

**有意排除**：renders、`report/rendered.md`、`report/paper.tex`、`report/paper.pdf`、`paperArtifacts`、`ledger.frozen`、review 记录本身。它们是评审与交付的**输出/事件**，已由 render→freeze→artifact 绑定；纳入会造成 render/freeze/review 循环失效。

使用要点：

- 先让内容**终态**（论文源、claim 证据链、图版本、构建脚本不再变），再记录 delivery review；
- 之后只做 `quality-run` → `freeze` → `render` → 构建 tex/pdf → `artifact` → `check` → `package` 不会使该 review stale；
- 改了 `report/paper.md`、活跃 claim/图、或 `src/build_paper.py`，该 review 会 stale 并**具名**说明变了哪个输入（`describeDeliveryScopeChanges`），需要重新 review；
- 2.8.9 遗留的 `binds=null` delivery review 不会被跳过，而是具名 stale（"predates delivery-scope binding…"）：做一次当前范围的新 review 即可；
- 旧 delivery review 的历史与 findings 全部保留（`historicalStale`），只有“每个对象的最新 review”参与 stale 判定。

### 9.2 退休对象与 critical-findings（2.8.10 修复）

统一谓词在 `runtime/assertions.js`：claim 用 `isRetiredClaim`（`superseded`/`retracted`），figure 用 `isRetiredFigure`（`superseded`/`retired`/`archived`/`historical`，或带 `supersededBy`/`retiredAt`/`retiredBy`），契约用 `supersededBy`。

- 最新 review 为 stale 的**已退休**对象 → 进 `retiredStale` 历史，**不阻塞**当前交付；
- 最新 review 为 stale 的**活跃**对象 → 仍阻断（"re-review the current version"）；
- **活跃**对象上未解决的 critical finding → 仍严格阻断（`open`）；
- 退休对象上的未解决 critical finding → `historicalFindings`（历史可见，不阻塞）；
- 退休对象**仍被当前交付引用**时失败：当前 `report/paper.md` 的 `{{claim:…}}`/`{{figure:…}}` 占位符、requirement coverage 的 refs、活跃 claim 的证据 refs/target contract → `DELIVERY_REF_MISSING`，消息点名 kind/id/来源；
- 正文里对历史的**文字提及**（例如“被取代的 FIG-0025 保留为历史”）不算引用，不会失败；
- `critical-findings` 的依赖是“派生的退休引用签名”，无关台账事件（包括宿主 usage 事件）不会使其误失效。

### 9.3 supersede / retract（公开恢复路径，沿用 2.8.9）

```json
{"action":"supersede","claimId":"CLAIM-0003","statement":"用重新验证后的证据表述的替代结论",
 "refs":[{"kind":"metric","experimentId":"EXP-0012","metricKey":"accuracy"}],
 "claimType":"rule_reproduction","reason":"旧实验证据已变化，重新登记并复算后建立新结论"}
```

```json
{"action":"retract","claimId":"CLAIM-0004","reason":"holdout 标签被证明是规则派生，撤回该复现结论"}
```

新 claim 是新 id；旧记录保留 `status`/`supersededBy`/`statusHistory`；critical 不能降级；coverage 不自动重映射；旧 claim 不能再 link 证据或被 render 引用。retract 后该题无 active claim 时需要补新结论或登记 `unansweredReason`。

## 10. 图版本管理（2.8.10 新增，重点）

### 10.1 铁律

**一个路径 = 一个版本。** 同一作品不同版本必须落在独立路径；同一路径登记不同字节会被 `FIGURE_PATH_CONFLICT` 具名拒绝（2.8.9 会静默接受，从而制造“旧记录永远 STALE”的死局）。

### 10.2 新增图（没有旧版本）

```
modeling_deliver {action:"figure", path:"experiments/EXP-0001/figures/x.png",
                  caption:"…", experimentId:"EXP-0001", scriptFile:"src/make_fig.py"}
```

记录 sha256+bytes+script hash；同路径同字节重复登记幂等返回既有记录。

### 10.3 修订图（保留旧记录/旧字节/旧→新关系）

1. 把新图写到**新路径**并登记成新 FIG id：

```
modeling_deliver {action:"figure", path:"figures/q3_pareto_v2.png", caption:"…", scriptFile:"src/make_paper_figures.py"}
```

2. 旧记录标记 superseded 并建立旧→新链接（`reason` 必填）：

```
modeling_deliver {action:"figure-retire", figureId:"FIG-0027", supersededBy:"FIG-0032",
                  reason:"图面重叠修订后重绘；新版本登记在独立路径"}
```

3. （可选但推荐）把旧字节保留到归档副本；**归档字节必须与旧记录登记 sha256 逐字节相等**，否则零写入拒绝：

```
modeling_deliver {action:"figure-archive", figureId:"FIG-0027",
                  archivePath:"figures/archive/FIG-0027-q3_pareto.png",
                  reason:"保留修订前旧字节"}
```

纯退役（没有替代版本）：只做第 2 步且省略 `supersededBy`（`status:"retired"` + `retiredReason`）。
两种记录都保留 id/path/sha256/createdAt；retire 追加 `statusHistory`，替代记录得到 `supersedes[]`；archive 把旧路径写入 `pathHistory` 且**不改登记 sha256**。重复退休、自指、用已退休记录当替代、同字节替代都会被具名拒绝；三个动作都支持 `expectedRevision` CAS。

### 10.4 旧台账已有“同路径两条 ACTIVE”的迁移

`delivery.check` 会给 `figures:paths` 失败行（点名两条记录与各自 sha256）。恢复步骤：

1. 把旧字节复制到独立归档路径（字节必须等于旧记录登记值）；
2. `figure-retire` 旧 id → `supersededBy` 指向当前活跃记录（若活跃记录已在新路径）；
3. `figure-archive` 旧 id → 归档路径；
4. 重新 `quality-run`（图集合变化）→ freeze → render → artifact → check。

### 10.5 交付层如何对待不同状态的图

- `delivery.check`：活跃图 `figure:<id>` 严格核验 SHA（文件被改即 STALE，必须重新登记/重新生成）；退休图给 `SUPERSEDED`/`RETIRED` 历史行（pass，注明未按字节核验并写出旧→新与原因）；`NO_FIGURES` 合法。
- `freeze`：只把**活跃**图写入 `frozen.figureIds`。
- `render`/占位符：引用退休图会被拒绝（`allowStale:true` **不能**绕过退休判定）；应改引替代 id。
- `package`：活跃图按当前字节打包；退休记录进 `figures.json#retiredFigures`（含 status/pathHistory/supersededBy/packagedAs）；若归档字节可核验，复制到 `figures/history/<FIG-id>-<basename>` 并进 `SHA256SUMS`；不可核验时 `packagedAs:null` + warning，绝不伪造。

## 11. 论文、render 与交付必须做最后一次同步

写论文用真实引用：`{{metric:EXP-0002:mae}}`、`{{claim:CLAIM-0001}}`、`{{figure:FIG-0001}}`。ID 以真实回执为准。收尾顺序：

1. 确认选择、证据、coverage 与独立审查；登记全部图并在正文实际引用；运行 quality 检查。
2. 记录 delivery review（内容终态之后；见 §9.1），必要时对旧 review 的 findings 用 `review-resolve` 记录证据。
3. 若上一步改变了 review 集合 → `quality-stale` 刷新后 `quality-run`，确认 `states.stale=0`。
4. 按实际状态 `freeze`（记录 config/协议/选择身份；图只冻结活跃集合）；最终判断看 `checkpointsPassed`，不看 stage 字符串。
5. `modeling_deliver {action:"render"}`：render 记录绑定配置/协议、冻结身份、选择身份与被引用证据版本；写 `report/rendered.refs.json`。`contest.yaml` 与 accepted 版本不一致时连草稿 render 都会具名拒绝：先 `config accept` 或恢复文件。
6. 生成 tex/PDF 后**必须绑定到当前 render**：`{action:"artifact", format:"tex"}`、`{action:"artifact", format:"pdf"}`；记录 renderId/renderSha/产物 SHA/生产者；`compile:true` 只在检测到真实引擎时编译，无引擎具名拒绝、不伪造。
7. 目检 PDF 全部页面或至少每类版式；核对图、表、单位、页数、空白页与溢出（长数字/数学符号/图注缺字）。
8. `modeling_deliver {action:"check"}`：读 `engineeringComplete`、`qualityPassed`、`checkpointsPassed`、`final`、`draft` 与失败明细；`final = 三者都 true`。
9. 同版核对：正文终态、选中 EXP、headline、摘要、图、refs、render、tex/PDF 与本次 check 同版；状态变化后必须重新 render（必要时重新编译并重新 artifact 绑定）→ check → 再打包。
10. 打包：`{action:"package"}` 生成 FINAL；`{action:"package", draft:true}` 仅在未通过时显式生成 `-DRAFT`（目录名带 `-DRAFT`，`final:false`，不能冒充最终交付）。默认不自动提交任何竞赛平台。

旧 tex/PDF 不能冒充新 render：改稿后未重新 render/绑定，check 会报 `ARTIFACT_FROM_OLD_RENDER`/`ARTIFACT_CHANGED`/`RENDER_STALE`，恢复路径就是重新 render + 重新 artifact。

## 12. 预算与恢复

- 每次使用重新明确模型预算、回合、时长；不继承旧授权。严格请求预算需在发模型前由工程入口建立受控 run 并确认请求上界/全会话计量。
- 查看真实 run ID、用量来源、已知小计、未结算上界；`usage=unknown` 不能按 0 或“预算内”处理；未知用量/无法确认在途上界即停付费，不自动重试或扩容。
- 提高预算/曝光上限的配置变更不会自动授权扩容、清空曝光或恢复保护停止；保护停止仍在，必须显式走 run-control 恢复/新 run。
- 停止前保留：revision、acceptedVersion 与协议 SHA、DATA/SPLIT/EXP/VAL/CLAIM/ROB/REV、选择、曝光、待审项与下一条具体工具操作。恢复先核对 config/文件/run，不重新 init、不删除失败、不只凭聊天记忆。

## 13. 错误处理速查

| 具名问题 | 下一步 |
|---|---|
| `CONFIG` / `CONFIG_DRIFT` / `needs_review` | `config diff` 看影响面；合法就 `config accept`（sha+revision+reason），否则恢复；旧项目按 §4.4 重建证据 |
| `CONFIG_UNREADABLE` | 修 `contest.yaml` 语法/schema；不可解析期间不用缓存配置继续写证据 |
| `PATH_ESCAPE` | 显式 import 后用项目内相对路径 |
| fields 缺失/别名 | 从真实表头生成完整 fieldsFile |
| DATA/SPLIT/target 不一致 | 复用成功回执；核对真实数据版本 |
| `model-condition` 缺公式/边界 | `contract-revise` → 重跑 `model-condition` → 受影响审查复审 |
| `metric-recompute` 键名错 | 回到 evaluation.metricKey 与产物协议；子指标不自动 alias |
| `COMPUTE_BUSY` / queued | 等待同一作业；不要反复新建 rerun |
| 失败后想重试 | 相同调用只返回旧失败；显式 `retry:true`+`retryReason` 才新开一个 attempt |
| snapshot 缺依赖 | 事前重建新原实验和完整冻结；旧证据不能补写历史依赖 |
| holdout 超限 | 不换 ID 洗历史；训练内部范围 / 真正未见数据 / 披露限制 |
| 负结果与正结论冲突 | 只在预登记 ROB 范围内允许共存；同范围正面断言必须 supersede/retract 或修正 |
| review findings/stale（活跃对象） | 实际修正后由独立审查者复审正确对象 |
| 旧 delivery review 报 stale（predates delivery-scope binding） | 对当前交付范围做一次新 `review-add {objectType:"delivery"}`；旧 review 保留 |
| delivery review 改了论文/claim/图/构建脚本后 stale | 原因已具名；重新 review 当前范围（§9.1） |
| `FIGURE_PATH_CONFLICT` | 新版本写真新路径再登记；旧记录用 `figure-retire` 退休/替代（§10） |
| `figures:paths`（同路径两条 ACTIVE） | 按 §10.4 迁移：归档旧字节 → retire → archive |
| `figure-retire` 报已退休 / 替代记录 retired / 同字节 | 历史只追加；替代必须是活跃且字节不同；纯退役省略 `supersededBy` |
| `figure-archive` 报 `DATA_HASH_MISMATCH` | 归档文件不是登记字节：复制正确的旧字节；archive 不伪造 |
| render 拒绝引用退休图 | 改引 `supersededBy` 指向的替代 id；`allowStale` 不能绕过 |
| `DELIVERY_REF_MISSING`（退休对象仍被引用） | 当前正文/coverage/活跃证据链仍在引用已退休对象：改引替代或撤销该引用 |
| `ARTIFACT_NOT_BOUND` / `ARTIFACT_FROM_OLD_RENDER` / `RENDER_STALE` | 重新 `render` 再 `artifact` 绑定当前 render；旧产物不冒充 |
| 包 final 但正文仍 DRAFT | 以结构化状态为准，修正正文状态文字 → 重新 render/编译/绑定 → check → 重打包 |
| `compile:true` 报无引擎 | 安装 LaTeX 或自行编译后用 `artifact` 绑定；不生成假 PDF |

## 14. 本版真实验证范围与边界

### 14.1 已验证（无需模型 API）

| 项 | 结果 |
|---|---|
| 新增 `tests/modeling-contest-figure-versioning.test.mjs` | **73 passed / 0 failed**；未修复 2.8.9 基线 **35 passed / 38 failed** |
| 新增 `tests/modeling-contest-review-binding.test.mjs` | **161 passed / 0 failed**；未修复基线 **111 ok / 50 failed** |
| 受影响既有套件 | quality 77/0、quality-lifecycle 15/0、quality-review2 26/0、claim-supersede 65/0、delivery 164/0、delivery-consistency 27/0、config-lifecycle 106/0、entry 19/0、gate 23/0 |
| `release-check.mjs` | ALL CHECKS PASSED（版本三处一致、zh/en 发布说明 8 节、清单登记、无 CRLF、真实 `npm pack`） |
| `regen-all --check` | 16/16 in sync（新增测试改变派生计数，已同步文档） |
| 建模类套件扫描 | 24 套件 PASS 16 / FAIL 8；8 个失败均为需要真实子进程的套件（`sandbox-exec: sandbox_apply: Operation not permitted`），用未修复 2.8.9 原始安装包跑同样套件失败画像逐项相同 → **非本轮引入** |
| 真实项目副本（隔离，公开动作） | 图迁移 + claim 链接 + 新 delivery review + quality-run → 27 passed/5 n/a/0 stale；freeze→render→build→artifact→check 两次均 **final=true、四布尔全 true、blocking=[]**；package FINAL |
| 本仓库 v3 项目（第二阶段） | FINAL 包 `delivery/20261024-223751/`（`final=true`，197 文件，archive sha256 `21c9ec18…`）；REV-0038 七条逐项复验完成（见项目 `DELIVERY-NOTES.md` §4） |

### 14.2 已知限制（不得冒充）

- **运行中宿主不会热重载**：升级 2.8.10 后必须完全重启；重启前的“通过”不算数（§0）。
- delivery review 的交付范围把 `report/paper.md` 与 `src/build_paper.py` 作为交付约定；使用其它 PDF 构建路径的项目，其 builder 变化不会纳入该 review。
- 退休图 id 在交付层之外仍有少数消费者未改（`runtime/claims.js` 的图引用、`runtime/validation.js` 的图身份复核、`runtime/workbench.js`）；render/check/freeze/package/交付范围已覆盖。
- `quality/engine.js` 的通用 review 状态投影仍会统计退休对象 stale review 数量（历史展示），最终判定由 `critical-findings` 负责。
- PDF **字节**不可复现（`xdvipdfmx` 非确定性）；可复现的是 `rendered.md`/`paper.tex` 与 PDF 的光栅/文本层一致性。不要声称 PDF 字节级可复现。
- `preflight.mjs`/`check-docs.mjs` 的 D6/D11/D16 提示与 `DOC LINT: FAIL` 在未修复 2.8.9 上同样存在（kernel 文档契约的历史问题，与本轮无关）。
- T1 全量门禁在 macOS 上会被仓库内遗留的 `D:\_tmp` 临时根阻塞（`mkdtemp 'D:\_tmp/...' EPERM`）；可加 `--no-temp-hygiene` 绕开。Windows 风格 fixture 与 Lean/Seatbelt 相关套件在本机本就失败。
- 本指南不包含任何“自动发布/自动提交竞赛平台”的能力；提交是人的动作。没有新的付费模型调用、没有模型自主解题 E2E。

### 14.3 相关文档

| 内容 | 路径 |
|---|---|
| 2.8.9 完整使用指南 | `outputs/质量问题修复工程交付/02_Vibe-Math-Modeling-2.8.9-正确使用指南.md` |
| 2.8.10 发布说明（zh/en） | `outputs/质量问题修复工程交付-2.8.10/包/RELEASE-NOTES-2.8.10.md` / `.en.md` |
| 2.8.10 插件包与 SHA | `outputs/质量问题修复工程交付-2.8.10/包/` |
| 2.8.10 版本/buildId 提交记录 | `outputs/质量问题修复工程交付-2.8.10/验证材料/git-log-2.8.10.txt` |
| 本仓库 v3 项目交付说明 | 项目根 `DELIVERY-NOTES.md`（2.8.10 第二阶段恢复后） |
| 本仓库 v3 项目复现说明 | 项目根 `REPRODUCE.md` |
| 第二阶段交接/操作序列 | 项目 `.rework/handoff/PHASE2-HANDOFF.md`；第一阶段报告 `.rework/handoff/PHASE1-REPORT.md` |
| 2.8.9→2.8.10 图迁移/审查复现证据 | 项目 `.rework/evidence/`、`.rework/verification/` |
