# PHASE2-HANDOFF.md — 第二阶段（Vibe Math Modeling 预设）交付恢复交接书

> 本文件由第一阶段（插件源码工程修复，默认编程预设）生成。
> **第二阶段必须在 Vibe Math Modeling 预设（`vibe-math-modeling`）的新会话中执行**；本会话未加载该预设，因此没有、也不得在本会话宣称第二阶段验证通过。
> 原始项目当前仍是 `final=false` 的 DRAFT 状态；台账只被宿主 usage 结算事件改变 revision/events，内容未改。

## 0 当前状态（一句话）

插件 2.8.10 已修复、已提交、已打包（SHA256 见 §2）、已安装进 `desktop` profile；**运行中的 DSH 宿主仍持有 2.8.9 的 ESM 模块缓存，必须完全退出并重启 DSH 才会加载 2.8.10**。第二阶段在重启后的新 `vibe-math-modeling` 会话里按 §5 执行即可。

---

## 1 第一阶段已完成（可复核）

### 1.1 插件源码修复

| 项 | 值 |
|---|---|
| 源码仓库 | `/Users/baozhashizitou/Documents/MATHORCUP/work/modeling-quality-lifecycle-2.8.7`（git，branch `main`） |
| 版本 | **2.8.10**（`buildId=2.8.10+cefef8a`） |
| 提交 | `cefef8a` = 2.8.10 代码/测试/发布说明；`447b438` = 包内 buildId |
| 变更规模 | 17 files, +1588/−55（13 modified, 4 new） |
| 关键文件 | `runtime/assertions.js`（统一退休谓词）、`runtime/delivery.js`、`runtime/service.js`、`runtime/quality/ledger.js`、`runtime/quality/checks.js`、`tools.js` |
| 新测试 | `tests/modeling-contest-figure-versioning.test.mjs`（73）、`tests/modeling-contest-review-binding.test.mjs`（161） |
| 包装 | `release-check`：**ALL CHECKS PASSED** |

三处缺陷的修复要点（与任务书 1/2/3 一一对应）：

1. **图版本迁移/退役**：`modeling_deliver` 新增公开动作 `figure-retire`（`reason` 必填；`supersededBy` 建立旧→新链接；保留 id/path/sha256/createdAt/statusHistory，替代记录得到 `supersedes[]`；支持 `expectedRevision` CAS）与 `figure-archive`（仅退休记录；归档字节必须等于登记 sha256，否则零写入；旧路径进 `pathHistory`）。`registerFigure` 对"同一路径不同字节"以 `FIGURE_PATH_CONFLICT` 具名拒绝；`delivery.check` 对活跃图严格核验 SHA、对退休图给显式 SUPERSEDED/RETIRED 历史行不再字节阻断、并对历史遗留"同路径两条 ACTIVE"新增 `figures:paths` 失败行；`freeze` 只冻结活跃图；render/占位符拒绝引用退休图；交付包把可核验旧字节复制到 `figures/history/` 并入 SHA256SUMS，`figures.json#retiredFigures` 保留状态与旧→新关系。
2. **delivery review 版本绑定**：`runtime/quality/ledger.js` 的 `deliveryScopeVersion()` 是唯一版本函数，写入（`addQualityRecord`）与刷新（`refreshQualityStaleness`）都调用它；范围 = `report/paper.md` sha256 + 活跃 claim 版本 + 活跃图版本 + 已接纳协议协议身份 + `src/build_paper.py` sha256；**有意排除** renders/rendered.md/tex/pdf/paperArtifacts/frozen/reviews，避免 render/freeze/review 循环失效。legacy `binds=null` 的 delivery review 不再被跳过，而是具名 stale（需要一次当前范围的 re-review）。
3. **退休对象审查**：`critical-findings` 用 `runtime/assertions.js` 的统一谓词；已 superseded/retracted 且不再被当前交付引用的对象，其 stale 最新 review 进 `retiredStale` 历史、不再阻塞；活跃对象未解决 critical 与 stale 最新 review 仍严格阻断；退休对象若仍被当前正文 `{{claim:…}}`/`{{figure:…}}`、requirement coverage 或活跃 claim 证据链引用，以 `DELIVERY_REF_MISSING` 具名失败；正文中的历史性文字提及不算引用。

### 1.2 测试结果（第一阶段）

| 测试 | 结果 |
|---|---|
| 新增 `modeling-contest-figure-versioning` | **73 passed / 0 failed**；未修复基线 35/38 failed |
| 新增 `modeling-contest-review-binding` | **161 passed / 0 failed**；未修复基线 111 ok/50 failed |
| `modeling-contest-quality` | 77/0 |
| `modeling-contest-quality-lifecycle` | 15/0 |
| `modeling-contest-quality-review2` | 26/0 |
| `modeling-contest-claim-supersede` | 65/0 |
| `modeling-contest-delivery` | 164/0 |
| `modeling-contest-delivery-consistency` | 27/0 |
| `modeling-contest-config-lifecycle` | 106/0 |
| `release-check.mjs` | ALL CHECKS PASSED |
| `preflight.mjs` / `check-docs.mjs` | 有**预先存在**的 D16 提示（未修复的 2.8.9 同样失败，与本轮无关）；`regen-all --check` 16/16 |
| T1 全量门禁 | 本机 macOS 上被 `D:\_tmp` 临时根（仓库内遗留的 Windows 路径目录）阻塞：`mkdtemp 'D:\_tmp/...' EPERM`。用 `--no-temp-hygiene` 可绕开；此属环境问题，已在 §5 记录 |
| modeling-contest 套件扫描（24 套件） | PASS 16 / FAIL 8；8 个失败全部是需要真实子进程的套件（`sandbox-exec: sandbox_apply: Operation not permitted`）。用**未修复的 2.8.9 原始安装包**跑同样 8 个套件，失败画像逐项相同（final 15/15、quality-tools 13/7、stale 6/5、scenarios 8/2 等），即**非本轮引入**；含本轮改动的 16 个套件全绿 |

### 1.3 插件包与安装

| 项 | 值 |
|---|---|
| tgz（留档） | `/Users/baozhashizitou/Documents/MATHORCUP/outputs/质量问题修复工程交付-2.8.10/包/dsh-vibe-math-2.8.10.tgz` |
| SHA-256 | `6462db91483d6fc334c7fb184400ea06a728896f6397718ba5aaa73857d210c5` |
| 大小 / 文件数 | 10,161,892 B / 854 |
| 安装 profile | `~/.dsh/profiles/desktop`（`dsh-vibe-math` 依赖已指向 2.8.10 tgz） |
| 已安装目录 | `~/.dsh/profiles/desktop/node_modules/dsh-vibe-math`，`package.json.version=2.8.10`、`buildId=2.8.10+cefef8a` |
| 字节核对 | `runtime/assertions.js`、`runtime/quality/ledger.js`、两个新测试与源码仓库**逐字节相同** |

**重要：安装后 `plugin_manager` 的激活诊断**为
`SyntaxError: The requested module '../assertions.js' does not provide an export named 'isRetiredFigure'`。
原因是**仍运行的 DSH 宿主缓存了 2.8.9 的 ESM 模块**（升级发生在同一进程内）；文件本身是正确的 2.8.10：
用**新进程** `node -e "import('<installed>/.../tools.js')"` 导入成功，且 `modeling_deliver` 动作枚举已含
`figure-retire`/`figure-archive`。**因此必须完全退出并重启 DSH**，新会话才会加载 2.8.10。

### 1.4 隔离副本上的端到端验证（第一阶段，非第二阶段）

在 `/tmp/rework-2.8.10/verify-2.8.10/project`（从快照重建的冻结 2.8.9 项目副本）上，用**已安装的 2.8.10**
经六个公开工具处理器跑完整生命周期，结果：

- 迁移前 `deliver check`：`final=false`，blocking = `figure:FIG-0025`、`figure:FIG-0027`、`figures:paths`×2、`report:render-binding`、`report:freshness`、`quality:requirement-coverage`、`quality:critical-findings`；
- `figure-retire FIG-0025→FIG-0030`、`FIG-0027→FIG-0031` + `figure-archive`（归档字节 sha256 与登记值一致：`57e3e864…`/`299df07e…`）后：
  FIG-0025/27 = `superseded`，路径在 `figures/archive/`，`pathHistory` 保留旧路径，`supersededBy` 指向新记录；
  FIG-0030/31 仍 `active` 且严格核验；
- 三个 claim 只链接**实际适用**且已通过的验证（见 §5.3）；新 delivery review（`REV-0039`）`binds` 非空，
  连续两次 `quality-stale` 刷新后仍 `stale=false`（无内容改动）；旧 `REV-0010/0026/0038` 作为 legacy 具名 stale；
- `quality-run` 后 27 passed / 5 n/a / **0 stale**；9 条已退休 claim 的旧 review 进 `retiredStale` 历史；
- 重新 freeze → render（`RENDER-0007`，inputSha `687d097a…`）→ `python src/build_paper.py` → artifact `ART-0003/ART-0004` → `check`：
  **final=true、engineeringComplete=true、qualityPassed=true、checkpointsPassed=true、blocking=[]**；连续两次 check 结果一致；
- `package`：`delivery/20261024-221010`，`delivery-status.json` 四布尔全 true、`final=true`、`draft=false`，
  archive sha256 `44d35fb63604dd027107a737058f1f5a0545c1b7f359026cc0a8014a47d86776`；
  `figures/history/FIG-0025-…png`（sha `57e3e864…`）与 `FIG-0027-…png`（sha `299df07e…`）在包内且进 SHA256SUMS；
- 新 PDF（18 页）几何复测：全部页面墨迹 xmax ≤ 版心右界 +0.69pt（F1/F2 已消）；
  Figure 13 图注为 `\(\in\)` 数学模式（F3 已消）；tex 中 U+2208 = 0。

证据（项目内）：`.rework/verification/isolated-2.8.10/`（逐步 receipt JSON、`25-summary.json`、`24-ledger-facts.json`）。
镜像：插件仓库 `_work/rework-2.8.10/`（snapshot / repro / pdf-audit / verification / handoff）。

---

## 2 第二阶段启动（必须按此顺序）

### 2.1 重启 DSH（必需）

1. **完全退出 DeepSeek Harness**（不是关窗口；确认进程退出）。
2. 重新启动 DSH，打开 Web GUI。
3. 在项目目录 `/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3` 新建会话，
   **agent 预设选择 `Vibe Math Modeling`**（预设 id `vibe-math-modeling`）。

### 2.2 确认加载的是已修复插件（在做任何项目动作之前）

在项目外跑（终端）：

```sh
INST=~/.dsh/profiles/desktop/node_modules/dsh-vibe-math
node -e "const p=require('$INST/package.json'); console.log(p.version, p.buildId)"
# 必须输出: 2.8.10 2.8.10+cefef8a
shasum -a 256 "$INST/dsh-vibe-math-2.8.10.tgz" 2>/dev/null || shasum -a 256 ~/.dsh/profiles/desktop/node_modules/dsh-vibe-math/vibe-math-vmu/packs/modeling-contest/runtime/assertions.js
```

在新会话里做**只读探针**（不写台账）：

```
modeling_deliver {action:"figure-retire", figureId:"FIG-9999", reason:"version probe"}
```

- 返回 `NOT_FOUND` / "no figure FIG-9999" ⇒ **新代码已加载**（动作存在）；
- 返回 `INVALID_ARGUMENT unknown deliver action` ⇒ 仍是旧代码（预设/宿主未重启），**停止，不得继续，也不得宣称修复**。

### 2.3 第二阶段起始基线（应为）

- 项目：`/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3`
- 配置：`contest.yaml` sha256 `2ce0b2c3a72911328c4ed302840b63f3c50e5fcbd49a8744c348c176e2904271`（accepted，未改）
- frozen：`2026-10-24T13:34:30.261Z`（rev 1800）；**不得手改冻结记录**，只用公开 `freeze` 重做
- DRAFT：`delivery/20261024-DRAFT/`（final=false）**保留**，新 FINAL 包另建目录
- 台账内容基线：22 claims（6 active）/ 31 figures / 38 reviews / 3 validationPlans / 43 validations；
  台账 `revision` 会持续被宿主 usage 事件增加（`actor:"host-usage"`）——**revision 是噪声**，比较内容与 sha

---

## 3 第二阶段执行顺序（全部走公开工具；不得手改台账）

> 下面的 `modeling_*` 都是 Vibe Math Modeling 预设的公开工具。任何一步失败都**保留 final=false**，不要用
> `allowStale`、不要降低 `quality.required`、不要删失败记录、不要重跑建模实验。

### 3.0 预备：保存工作副本与基线

- 保留现在的 `delivery/20261024-DRAFT/` 与 `state/ledger.json` 不动；记下 `deliver check` 当前输出（应为
  3 项阻断：`figure:FIG-0025`、`figure:FIG-0027`、`quality:critical-findings`，外加新插件的 `figures:paths`×2）。
- 旧图字节已留在 `.rework/handoff/old-figure-bytes/`（sha 已核验）。

### 3.1 应用论文残余修复（REV-0038 F2/F4/F5 + 重复用字 + 图历史说明）

```sh
cd /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3
python3 .rework/handoff/apply-paper-fixes.py .
```

- 脚本幂等，逐条断言旧文本存在；成功应为 `report/paper.md` sha256 = `687d097afd26c91564e64b19db358a34c243918a647fc14de4399b9dbcf6ed89`
  （若你另行调整措辞，以实际为准，并把新 sha 记入交付说明）。
- 该脚本包含 F2（p4 过满行）、F4（§6.5 与 CLAIM-0022 段重复数字）、F5（§6.5/§9 手写 1.0、`delta = 0`、阈值/审计常数来源指针）、
  “也也”错字，以及 FIG-0025/0027 历史说明（归档路径按 §3.2 的规范名）。
- **注意**：改完 `paper.md` 后旧的 `RENDER-0006`/`ART-0001/0002` 自然失效，必须走 3.5 的重建，不能沿用旧产物绑定。

### 3.2 图版本迁移（公开动作；保留旧记录/旧字节/旧→新）

先把旧字节放到独立归档路径（**字节必须与登记 sha256 相同**，否则 archive 会拒绝）：

```sh
mkdir -p figures/archive
cp .rework/handoff/old-figure-bytes/FIG-0025-q3_defect_exceedance.png figures/archive/FIG-0025-q3_defect_exceedance.png
cp .rework/handoff/old-figure-bytes/FIG-0027-q3_pareto.png             figures/archive/FIG-0027-q3_pareto.png
shasum -a 256 figures/archive/FIG-0025-q3_defect_exceedance.png   # 必须 57e3e864e41517f8600b70b069c87d0d37eda7b5c52c055b32591e2d8dbd1306
shasum -a 256 figures/archive/FIG-0027-q3_pareto.png              # 必须 299df07e5a54e3727f3d86d752ff3672ecb4e1227944a70eaab8808698a6b14e
```

然后（顺序：先 retire 建旧→新关系，再 archive 把旧记录指向归档副本）：

```
modeling_deliver {action:"figure-retire", figureId:"FIG-0025", supersededBy:"FIG-0030", reason:"图面重叠修订后重绘：FIG-0030 是同一作品的新版本（独立登记），旧记录保留为历史"}
modeling_deliver {action:"figure-retire", figureId:"FIG-0027", supersededBy:"FIG-0031", reason:"图面重叠修订后重绘：FIG-0031 是同一作品的新版本（独立登记），旧记录保留为历史"}
modeling_deliver {action:"figure-archive", figureId:"FIG-0025", archivePath:"figures/archive/FIG-0025-q3_defect_exceedance.png", reason:"保留修订前旧字节，归档副本 sha256 必须等于登记值"}
modeling_deliver {action:"figure-archive", figureId:"FIG-0027", archivePath:"figures/archive/FIG-0027-q3_pareto.png", reason:"保留修订前旧字节，归档副本 sha256 必须等于登记值"}
```

验收：FIG-0025/0027 `status="superseded"`、`supersededBy` 分别 FIG-0030/0031、`pathHistory` 保留
`figures/q3_defect_exceedance.png`/`figures/q3_pareto.png`、登记 sha256 不变；FIG-0030/0031 仍 `active`。
`deliver check` 的 `figure:FIG-0025`/`figure:FIG-0027`/`figures:paths` 行应消失（退休行以 SUPERSEDED 显式通过）。

### 3.3 只链接实际适用且已通过的验证（不得机械照抄）

```
modeling_claim {action:"link", claimId:"CLAIM-0019", addValidationIds:["VAL-0037","VAL-0038","VAL-0039"]}
modeling_claim {action:"link", claimId:"CLAIM-0021", addValidationIds:["VAL-0040","VAL-0041","VAL-0042","VAL-0043"]}
modeling_claim {action:"link", claimId:"CLAIM-0022", addValidationIds:["VAL-0040","VAL-0041","VAL-0043"]}
```

理由（可在交付说明中写明）：0019 的证据就是 `topk-jaccard`，对应 VAL-0037 leakage + VAL-0038 原生复算 +
VAL-0039 独立复跑；0021 的证据是 `constraint-satisfaction`，对应 VAL-0040/0041/0042/0043 四项；
0022 的证据是 EXP-0033 的转移数值，**VAL-0043 的 independent-rerun 逐项比较了全部 52 个指标（含 transfer-*）**、
VAL-0041 复算它所引用的 constraint-satisfaction、VAL-0040 确认其输入无泄漏；**VAL-0042（simulation-seeds）不链接**，
因为该结论不涉及 seed 变异性（那是 0021 的范围）。不要复制别的结论的验证列表。

### 3.4 独立复审 + 用 review-resolve 记录 REV-0038 的实际解决证据

必须由**独立上下文**（不同 agent/member，`isRoot=false`）执行，`method` 写清实际审阅了什么。最低要求：

```
modeling_project {action:"quality", subaction:"review-add",
  objectType:"delivery", objectId:"paper", verdict:"passed",
  method:"独立通读 report/paper.md、rendered.md、tex/pdf、REPRODUCE.md 与台账：核对 RENDER-0007 绑定、14 图注与图 SHA、活跃 claim 证据链、已退休图/claim 的历史与旧→新关系、版本关系",
  independence:"independent_context"}
```

（可选更严格：对 6 条 active claim（CLAIM-0018/0014/0019/0021/0022/0012）逐条 `review-add`，`objectType:"claim"`。）
REV-0038 的 7 条 finding 用公开 `review-resolve` 记录证据（先自己按 §3.7 复验再写）：

```
modeling_project {action:"quality", subaction:"review-resolve", reviewId:"REV-0038", findingId:"F1", resolution:"当前 RENDER-0007 构建的 PDF 复测：§8 已为条目列表，第 9 项长数字完整可见，全部页面墨迹未越版心（xmax≤555.31pt+0.69pt），无裁切；证据 .rework/evidence/pdf-audit/… 与本轮复测"}
... F2（p4 过满行已由 paper.md §4.4 数学拆分修复，新构建全页无越界）
... F3（build_paper.py 把 U+2208 → $\in$，tex 中 U+2208=0，Figure 13 图注为数学模式 ∈）
... F4（§6.5 重复数字段已删，改为指向登记结论；§9 保留一次）
... F5（手写 1.0 改占位符/名称，delta=0 改为“容差内复现”，审计/阈值常数加注册来源指针）
... F6（REPRODUCE.md §2.6 已是 v3/v4，§2.11 已是 6 条 active claim）
... F7（CLAIM-0019/0021/0022 已按实际适用链接 VAL-0037–0039 / 0040–0043 / 0040+0041+0043）
```

### 3.5 质量检查 → freeze → render → 构建 tex/pdf → artifact → check → package

```
modeling_validate {action:"quality-plan", auto:true}
modeling_validate {action:"quality-run"}
modeling_project  {action:"quality", subaction:"status"}     # 期望 qualityPassed=true，states.stale=0
modeling_project  {action:"freeze", reason:"2.8.10 交付复验：图版本迁移完成、活跃 claim 链接验证、delivery 独立复审完成"}
modeling_deliver  {action:"render"}                          # 期望 RENDER-0007，inputSha=新 paper.md sha
# 终端：python src/build_paper.py                             # 生成 paper.tex / paper.pdf（同一 rendered.md）
modeling_deliver  {action:"artifact", format:"tex"}          # 期望 ART-0003 绑定 RENDER-0007
modeling_deliver  {action:"artifact", format:"pdf"}          # 期望 ART-0004 绑定 RENDER-0007
modeling_deliver  {action:"check"}                           # 期望 final=true 且四布尔全 true
modeling_deliver  {action:"check"}                           # 再跑一次，结果应一致
modeling_deliver  {action:"package"}                         # 生成 FINAL 包（非 draft）
```

**关键顺序约束**：`quality-run` 必须在所有内容改动（paper/claim 链接/退休动作/review）之后；`freeze` 必须在
render 之前；tex/pdf 必须在 render 之后构建并**绑定到最新 render**；旧 `RENDER-0006`/`ART-0001/0002` 不可复用。
若 `quality-run` 后又有 review/claim 改动，必须再 `quality-stale` + `quality-run`（review 集合变化会使其 stale）。

### 3.6 交付包验收

- 新 FINAL 目录（`delivery/<timestamp>/`）的 `delivery-status.json`：`final=true`、`draft=false`、
  `engineeringComplete=true`、`qualityPassed=true`、`checkpointsPassed=true`；
- `figures/figures.json#retiredFigures` 含 FIG-0025/0027（status、supersededBy、pathHistory、`packagedAs`）；
- `figures/history/` 含两条旧图且 sha 为 `57e3e864…`/`299df07e…`，且出现在 `SHA256SUMS`；
- 14 张活跃图 sha 与台账一致；`report/paper.tex`/`paper.pdf` sha 与 `ART-0003/0004` 一致，`ART-*.renderId=RENDER-0007`；
- 记录新包的绝对路径、`.tar.gz` sha256（第二阶段最终报告必须给出）。

### 3.7 复验 REV-0038 的 PDF 三项（用当前 PDF 实测，不要口头声称）

用 `.rework/evidence/pdf-audit/scripts/final_audit.py`（把 `PROJ` 指向当前项目）或等价 pypdfium2 脚本：
渲染 18 页 2×，测每页墨迹 xmax，**任何页面 > 版心右界 +3pt 即失败**；§8 第 9 项两个长数字完整可见；
Figure 13 图注 ∈ 为数学字形；报告中保存 PNG/JSON 证据。当前隔离副本上复测：18 页、最大越界 +0.69pt（字形侧伸）、无裁切。

---

## 4 红线（违反即视为做错）

1. 不重跑任何建模实验（除非发现具体科学证据缺口）；不新增 SPLIT-0002 曝光（3/3 已用尽）。
2. 不降低任何配置门禁（`quality.required`、`delivery.requireIndependentRerun`、`review.independence` 等）。
3. 不删除/改写失败历史（EXP-0012、VAL-0011、VAL-0020、EXP-0027、EXP-0028/0032 保留）。
4. 不手改 `state/ledger.json`、不重建项目、不 reset 曝光预算、不手改 `frozen`。
5. 不把 DRAFT 当 FINAL；`final=false` 时只能出 DRAFT 包。
6. 若任何必需检查失败/无法解释，**保留 final=false**，如实记录，不得声称通过。

---

## 5 已知环境问题（不是本轮缺陷）

- `preflight.mjs` / `check-docs.mjs` 的 D16 提示（`vmu.library`/`vmu.members`/`vmu.store` 未列入契约）与
  `DOC LINT: FAIL` 在**未修复的 2.8.9 上同样存在**（已实测），本轮未改 kernel 文档契约。
- T1 全量门禁在本机 macOS 上被仓库内遗留的 `D:\_tmp` 临时根阻塞（`mkdtemp 'D:\_tmp/...' EPERM`）；
  可加 `--no-temp-hygiene` 绕开（会改用系统 tmp）。Windows 风格 fixture 与 Lean/Seatbelt 相关套件在该环境本就失败。

## 6 证据与产物索引

| 内容 | 路径 |
|---|---|
| 第一阶段完整报告 | `.rework/handoff/PHASE1-REPORT.md` |
| 论文修复脚本（幂等） | `.rework/handoff/apply-paper-fixes.py` |
| 论文修复 diff | `.rework/handoff/report-paper.md.patch` |
| 插件 2.8.10 代码 patch | `.rework/handoff/plugin-2.8.10-code.patch` |
| 旧图字节（sha 已核验） | `.rework/handoff/old-figure-bytes/` |
| 基线快照 + MANIFEST + SHA256SUMS | `.rework/evidence/snapshot/` |
| 三项缺陷复现报告/运行手册 | `.rework/evidence/repro/{REPRO-2.8.9.md,RUNBOOK-2.8.10.md}` |
| REV-0038 独立复验（F1–F7） | `.rework/evidence/pdf-audit/REV-0038-REVERIFY.md` |
| 隔离副本 2.8.10 端到端证据 | `.rework/verification/isolated-2.8.10/` |
| 公开工具 harness | `.rework/evidence/repro/tools/invoke.mjs`（用法见 RUNBOOK §2） |
| 插件仓库镜像 | `/Users/baozhashizitou/Documents/MATHORCUP/work/modeling-quality-lifecycle-2.8.7/_work/rework-2.8.10/` |
| 插件包（留档） | `/Users/baozhashizitou/Documents/MATHORCUP/outputs/质量问题修复工程交付-2.8.10/包/dsh-vibe-math-2.8.10.tgz` |

## 7 第二阶段提示词（可直接粘贴到新建的 Vibe Math Modeling 会话）

```text
这是 Vibe Math Modeling 2.8.10 项目的第二阶段：交付回归验证与交付恢复，不是重新建模。

项目：/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3
先读：.rework/handoff/PHASE2-HANDOFF.md（权威交接书，含全部顺序/命令/验收标准），
以及 .rework/evidence/pdf-audit/REV-0038-REVERIFY.md、.rework/evidence/repro/REPRO-2.8.9.md、RUNBOOK-2.8.10.md。
先确认当前加载的插件是 2.8.10（交接书 §2.2：node 读 version/buildId=2.8.10+cefef8a；会话内 figure-retire 探针应返回 NOT_FOUND 而不是 unknown action）。若仍是旧版，停止并报告，不得继续。

然后严格按 PHASE2-HANDOFF.md §3 执行：
1) 运行 python3 .rework/handoff/apply-paper-fixes.py . 应用 REV-0038 残余 F2/F4/F5 修复；
2) 用公开 figure-retire/figure-archive 迁移 FIG-0025→FIG-0030、FIG-0027→FIG-0031（旧字节从 .rework/handoff/old-figure-bytes/ 归档，sha 必须等于登记值）；
3) 按实际适用性给 CLAIM-0019/0021/0022 链接 VAL（见 §3.3，不得机械照抄）；
4) 独立复审当前论文/claim/图/复现说明/版本关系，用 review-resolve 记录 REV-0038 七条 finding 的实际证据；
5) 依次 quality-plan/quality-run → freeze → render → python src/build_paper.py → artifact tex/pdf → check（期望 final=true）→ package（FINAL）；
6) 用 pypdfium2 复测新 PDF 的 F1/F2/F3 并保存证据；核对交付包四个布尔、figures/history 与 SHA256SUMS；
7) 更新交付说明并给出新交付包绝对路径。

红线：不重跑建模实验、不新增 SPLIT-0002 曝光、不降配置门禁、不删失败历史、不手改台账/frozen；未全部通过时保留 final=false 并如实报告。
最终报告需包含：新质量报告结果、最终 check 实际结果、图与 review 迁移记录、REV-0038 逐项复验、活跃 claim 验证链接、新交付包绝对路径。
```
