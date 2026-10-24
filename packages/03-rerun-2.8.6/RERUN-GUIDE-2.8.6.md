# Vibe Math Modeling 2.8.6 重跑指南（MathorCup 2026 A）

> 依据：`04_安装_使用_禁用_回滚.md` + 2026-10-24 本项目失败复盘。
> 目标：**新项目、一次跑到 `final=true`**；旧项目 `work/my-new-contest` 只读，不写入、不删除、不复用为“未见测试”。
> 原则：**配置先定稿、协议先于候选、记录一次写对、不可删的记录不试错、不伪造。**
> 说明：没有绝对的“无漏洞”，但有“不可逆清单”。本指南把所有已知漏洞前移成门禁；**一旦跨过不可逆门，唯一正确动作是重开项目，不是修补。**

---

## 0. 十条铁律（违反任何一条，直接重开项目）

1. **`init` 之后不再改 `contest.yaml`**。配置是协议指纹，不是运行参数。
2. **`problem/questions.yaml` 定稿后 `plan` 只调一次**；不要反复 plan 改小问。
3. **每个小问只登记一个 validation plan，且必须在任何 candidate 之前**。plan 不可删除。
4. **不要在 candidate 之后补 plan；不要在 `quality-plan` 之后改 claim 的 metricKey**。QC 记录不可删除/改参。
5. **每个 candidate 必须带 `params.freezeSources:true` + `params.dependenciesComplete:true` + `params.dependencies`**；否则不能 `independent-rerun`。
6. **claim 的 `metricKey` 用实验注册的 `params.evaluation.metricKey`**（`mae` / `topk-jaccard` / `constraint-satisfaction`），不用 `holdout_mae_mean` 之类的子指标。
7. **requirement 的 refs 用 `{kind:"experiment", id:"EXP-…"}`**，不要用 `experimentId/claimId/figureId` 作为 id 字段。
8. **一个 holdout 行最多 3 次成功曝光**；不要用新 splitId 重置；只有 `verifiedRerun` 和 `train-only` 隔离实验豁免。**不要把 holdout 当调试集**：脚本先在 train-only/子样本上跑通，再注册正式 holdout 实验；2.8.6 在评估前预留曝光，失败也可能占预算。
9. **review 必须来自独立上下文**（子会话/成员）；root agent 不能自称 `independent_context`。
10. **任何 unknown usage 立即停止**；不继续付费调用；不删停止标记。

### 0.1 这次重跑要修掉的旧坑（对照上一轮）

| 旧坑 | 本指南的做法 |
|---|---|
| init 后改 `contest.yaml`，sha 永久不一致 | 配置在 init 前定稿；init 后只读 |
| Q1 的 validation plan 晚于 candidate | Phase 4 先 plan，Phase 5 才跑 candidate |
| 同一问登记 3 个 plan，stage 要求全部通过 | 一问一 plan；错就重开，不补第二个 |
| claim 用 `holdout_mae_mean` 等子指标键 | claim 的 `metricKey` 用 `mae/topk-jaccard/constraint-satisfaction` |
| requirement refs 用 `experimentId` 而不是 `id` | refs 统一 `{kind,id}` |
| MCON 缺 formula/boundaryCases | Phase 2 一次给全；可 `contract-revise` |
| TGT review 是 findings，target-lineage 卡住 | 独立上下文重审，verdict=passed |
| EXP-0002 无 snapshot，不能 independent-rerun | 所有 candidate 从第一天带 `freezeSources/dependenciesComplete` |
| robustness 只登记不复跑 | Phase 6 先 plan、再跑扰动、再 execute |
| root agent 自称独立 review | 用子会话/成员执行 `review-add` |
| DRAFT 包与论文不一致 | 任何改动后重新 render + 重新 package；DRAFT 不改名 |
| holdout 复用超 3 次 | 4.2 曝光表；Q2/Q3 不设随机 splitId；稳健性用 train-only |

---

## 1. 安装 / 升级 / 回滚（按 04 执行）

| 步骤 | 动作 | 通过判据 |
|---|---|---|
| 1.1 | 备份**当前** profile（无论 2.8.5/2.8.6）：`~/.dsh/profiles/desktop/package.json`、`pnpm-lock.yaml`、`cordis.patch.yml`；若当前已是 2.8.6，先核对版本/文件清单，再决定是否重装 | 三个文件有备份 |
| 1.2 | 核对 `/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/outputs/建模实战整改最终交付/安装包/dsh-vibe-math-2.8.6.tgz` 的 SHA256 = `f28909b23a7e4850381c834b1f6d2a72d6b2718e6f3eebd4c29ac65c56708de4`，并核对同目录 `安装包/SHA256SUMS` | 一致；833 文件 |
| 1.3 | **在宿主官方插件管理器里从本地安装** `…/建模实战整改最终交付/安装包/dsh-vibe-math-2.8.6.tgz`；不要用 PATH 旧版 `dsh` 强改 desktop profile | 插件页显示 2.8.6 |
| 1.4 | 正常重启宿主；新建会话选择 **Vibe Math Modeling**；先跑 **probe** | probe ok，解释器版本入台账 |
| 1.5 | 打开“◈ 解题监控”；确认角色/工具/实验/质量分列显示 | 不把“质量红色”直接当成整题失败 |
| 1.6 | 禁用/移除：宿主插件页操作并正常重启。回滚：官方插件管理器安装 `…/建模实战整改最终交付/安装包/回滚/dsh-vibe-math-2.8.5.tgz`；必要时退出宿主后恢复 1.1 备份 | 不删 `~/.dsh`、不删会话、不删原竞赛目录 |
| 1.7 | 隔离 CLI 复现只用于测试 profile（`DSH_HOME=/private/tmp/...`），不用于 desktop | 不冒充 GUI 点击验收 |
| 1.8 | 若同 profile 试装过 2.8.6 候选：先用官方管理器移除，再装最终 SHA 包，核对关键文件 | 版本号不等于字节正确 |

**失败即停**：probe 失败、preset 不可见、插件版本不是 2.8.6、安装包 SHA 不符——任一条件不满足，不要开始建模。

---

## 2. 配置定稿（`init` 之前，一次到位）

> 这一步在旧项目里是致命伤：先 init 后改配置，导致 ledger 的 `configSha256` 冻结在 init 版本，experiments/claims/selection 三处比较永久不一致。**新项目必须先把配置写死。**

### 2.1 新项目路径

```bash
PROJ=/Users/baozhashizitou/Documents/MATHORCUP/work/beer-rerun-2.8.6
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
```

### 2.2 `contest.yaml`（写到 `$PROJ/contest.yaml`，然后才 init）

```yaml
schemaVersion: 2
projectId: beer-2026-a-r2
language: zh-CN
deadline: null
problem:
  statement: problem/2026年MathorCup大数据挑战赛-赛道A初赛.md
  questions: problem/questions.yaml
runtime:
  python: /Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
  maxComputeConcurrency: 1
  experimentTimeoutSeconds: 1800
  maxImprovedModelsPerQuestion: 2
evaluation:
  taskType: mixed
  split:
    method: random-holdout
    testFraction: 0.2
    seed: 20261024
  tuning: train-only-cross-validation
  primaryMetric: mae
  metricDirection: minimize
  baseline: null
  leakage:
    correlationThreshold: 0.999
    forbiddenColumns: []
  reproductionTolerance:
    absolute: 1.0e-9
    relative: 1.0e-6
    stochasticReruns: 3
delivery:
  template: generic-zh
  paperFormats: [md, tex, pdf]
  requireIndependentRerun: true
  requireResolvedCriticalClaims: true
  submission: manual
  contest:
    name: 2026年MathorCup大数据挑战赛-赛道A
    pageLimit: null
    anonymous: null
    fileNaming: null
    aiDisclosure: null
    extraRequirements: []
quality:
  required: true
  coverageReviewRequired: true
  ruleDependencyAgreement: 0.999
  review:
    required: true
    independence: independent_context
    allowSameModelDifferentContext: true
  robustness:
    required: true
    maxHoldoutReuse: 3
    methods: [multiple-seeds, param-perturbation]
  runControl:
    maxRetries: 2
    noProgressLimit: 3
    approvalTimeoutSeconds: 120
    softTokenLimit: null
    hardTokenLimit: null
```

**与旧配置的差异（全部是有意的）**

| 项 | 旧值 | 新值 | 原因 |
|---|---|---|---|
| `evaluation.primaryMetric` | `rmse` | `mae` | 旧项目主指标实际是 MAE（`mae`），用 rmse 会让 fallback 检查对不上 |
| `evaluation.split.seed` | `42` | `20261024` | 与论文、旧 SPLIT 的 assignment 一致 |
| `problem.questions` | 指向不存在的文件 | 必须先创建 `problem/questions.yaml` | schema 要求且 `plan fromFile` 需要 |
| `quality.robustness.methods` | `[]` | 真会执行的两种 | 空列表等于没配置稳健性方法 |
| `delivery.contest` | `null` | 声明比赛名 | `submissionReady` 需要 contest declared；不影响 `final` |
| `runtime.maxImprovedModelsPerQuestion` | 默认 2 | 显式 2 | 旧项目 Q1 堆到 7 个候选，触发预算警告 |

**硬规则**：`init` 成功后，`shasum -a 256 contest.yaml` 必须与 `state/ledger.json` 的 `configSha256` **始终相等**。任何后续编辑都视为“换协议”，必须重开项目。

---

## 3. 目录与资产准备

```bash
# 只读来源（旧项目）
OLD=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest

mkdir -p "$PROJ"/{problem,src,analysis/sensory,analysis/fields,data/raw,data/clean,data/processed,report,figures,state}

# 1) 题面
cp "$OLD/problem/2026年MathorCup大数据挑战赛-赛道A初赛.md" "$PROJ/problem/"
cp "$OLD/problem/2026年MathorCup大数据挑战赛-赛道A初赛.pdf" "$PROJ/problem/"   # 存档，脚本不读

# 2) 现有脚本与字段口径（脚本会按原路径查找附件；导入后哈希名一致）
cp "$OLD"/src/*.py "$PROJ/src/"
cp "$OLD/analysis/sensory/targetcolumns.csv" "$PROJ/analysis/sensory/"

# 3) 字段清单：由数据脚本生成到 data/processed/fields_*.json；
#    如需人工审查可复制到 analysis/fields/ 作参考，但 register-clean 用脚本生成的那份
cp "$OLD"/data/processed/fields_*.json "$PROJ/analysis/fields/" 2>/dev/null || true

# 4) questions.yaml（见附录 A），必须在 init 前创建
$EDITOR "$PROJ/problem/questions.yaml"
```

### 3.1 `questions.yaml` 的设计要点

- `metric` 必须逐问写：Q1=`mae`，Q2=`topk-jaccard`，Q3=`constraint-satisfaction`；不要依赖 `primaryMetric`。
- `needsBaseline: true` 对三问都设：2.8.6 的 `baseline-required` 按目标契约要求基线；旧项目 Q2/Q3 的 `false` 是后来的坑。
- `needsData: true` 对三问都设。
- 输出里写清楚“predictions.csv / sets.json / metrics.json”等，便于后面 claim/coverage 对齐。

---

## 4. 数据与评估拓扑（先定 holdout 预算，再跑任何实验）

### 4.1 推荐：base 数据集 → mapped 版本 → 同 assignment 的两个 split

旧项目把同一批 250 行拆成 `DATA-0001/0002/0003`，又注册 `SPLIT-0001/0002`（assignment 相同）——风险是“换 splitId 冒充新测试”。但 Q1 的 mapped grade **必须只用训练行估计**，而 split 必须在 dataset 之后才能注册，这里有一个真实循环：映射需要 split，split 需要 dataset，dataset 又需要映射后的目标。2.8.6 不支持自定义 assignment 文件，所以用“两个版本 + 两个同 assignment 的 split”解开循环，但**只允许一个 split 被实验使用**：

1. `src/build_q2raw.py` → `data/clean/q2_raw.csv`（250 行：231 特征 + 50 原始目标 + 键）→ 注册 **DATA-0001**。
2. 在 DATA-0001 上注册 **SPLIT-0001**（200/50，seed=20261024，positional）。它**只用于估计 mapped-grade 的 zmin/zmax**，不跑任何实验。
3. `src/build_q1mapped.py --split SPLIT-0001` → `data/clean/q1_mapped.csv`（50 维 mapped 目标）→ 注册 **DATA-0002**（`parentId:"DATA-0001"`）。
4. 在 DATA-0002 上注册 **SPLIT-0002**（同一 seed、同一批行，assignment 与 SPLIT-0001 相同）。Q1 实验只用 **DATA-0002 + SPLIT-0002**。
5. Q2 用 **DATA-0001 的 train 行**（脚本读 `data/splits/SPLIT-0001/train.csv` 作为依赖），实验**不设 splitId**；验证只做 leakage + independent-rerun。
6. Q3 用 `src/build_q3.py` → **DATA-0003**（风格/阈值视图），实验**不设随机 splitId**；验证用 leakage + simulation-seeds + independent-rerun。

关键点：
- SPLIT-0001 与 SPLIT-0002 是**同一个 assignment**；SPLIT-0001 只用于数据加工，SPLIT-0002 才是评估视图。**不要在两个 split 上都跑实验**，否则同一行会被计两次曝光；论文/claim 里明确写“SPLIT-0001 仅用于映射参数估计，SPLIT-0002 用于评估，两者 assignment 相同”。
- Q2/Q3 不设 `splitId`，所以不占 holdout 预算；它们的评估是关联分析/风格留出，不是“随机 holdout 预测”，在 plan/claim 里如实写。
- 不要为了“看起来干净”再注册第三个随机 split；2.8.6 的曝光追踪按真实样本行累计，换 ID 不会重置。

### 4.2 曝光预算表（先填后跑）

| 问题 | 评估集 | 实验使用的 splitId | 会带 splitId 的实验 | 曝光数 | 备注 |
|---|---|---|---|---|---|
| Q1 | SPLIT-0002 的 50 行 | SPLIT-0002 | baseline、Ridge、HistGBM | 3 | Ridge 的 rerun 为 verifiedRerun，不计 |
| Q2 | SPLIT-0001 的 train 200 行 | 无 | 无 | 0 | 关联分析；SPLIT-0001 不跑实验 |
| Q3 | 49 行风格留出 | 无 | 无 | 0 | 风格留出视图；在 plan/claim 显式披露 |

> SPLIT-0001 与 SPLIT-0002 的 assignment 相同，但只有 SPLIT-0002 被实验使用；这是“避免循环”的工程手段，不是第二个测试集。任何行被两个以上实验当作 holdout 都是违规。

## 5. 执行顺序（Phase 0–9；每段有门禁）

> 每段结束都跑一次 `modeling_project {action:"status"}`，看 `checkpoints` 和 `blockers`。**门禁不过，不进入下一段。**

### Phase 0 — init + plan

> 调用约定：下文 JSON 是工具 args；工具名按动作对应——`modeling_project`（init/plan/status/select/freeze/quality/advance）、`modeling_data`（import/profile/register-clean/register-split/run-script）、`modeling_experiment`（register/run/status）、`modeling_validate`（plan/run/independent-rerun/quality-*）、`modeling_claim`（create/link）、`modeling_deliver`（figure/render/check/package）。

```json
{"action":"init","projectDir":"/Users/baozhashizitou/Documents/MATHORCUP/work/beer-rerun-2.8.6","taskType":"mixed","language":"zh-CN","python":"/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python"}
```
```json
{"action":"plan","fromFile":"problem/questions.yaml","createTasks":true}
```
门禁：
- `status` 显示 3 个小问、无 intake blocker。
- `shasum -a 256 contest.yaml` == `ledger.configSha256`；记下这个值，后续每次 status 都核对。
- 可选：`workbench describe` 后按小问 `configure`；**如果 configure，就必须产出 evidence 文件并通过 `analysis-evidence`**。不想承担就不 configure，别声称工作台覆盖。

### Phase 1 — 数据

1. **显式外部导入**（2.8.6 的 `import` 会复制并核对 SHA；不要手工放进项目）：
```json
{"action":"import","files":[
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/419849227a02e0c7-1.csv","role":"chem"},
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/415709ac10f2f730-2.csv","role":"corr"},
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/fe4dcabd48431e6d-3.xlsx","role":"scorecards"},
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/43a7b38682ed81ce-4.csv","role":"sensory"},
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/c512eed108de6f98-5.csv","role":"derived"},
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/a55004fb0390299a-6.csv","role":"derived"},
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/2083138df46640e2-7.csv","role":"sensory7"},
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/f2316766792111d9-8.xlsx","role":"calibrated"},
  {"path":"/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/data/raw/imported/40813e273e081ae0-数据说明.txt","role":"readme"}
]}
```
2. 跑既有数据脚本（`run-script` 会记录 stdout/stderr/输出 SHA；不要用 bash 手工跑完后不登记）：
```json
{"action":"run-script","script":"src/prepare.py","purpose":"audit/scale/targetcolumns","outputs":["analysis/sensory/targetcolumns.csv","outputs/audit/audit.json","outputs/audit/scale_identification.csv"],"timeoutSeconds":600}
```
3. **base 数据集**：跑 `build_q2raw.py`，注册 DATA-0001：
```json
{"action":"run-script","script":"src/build_q2raw.py","purpose":"base table: 231 features + 50 raw targets","outputs":["data/clean/q2_raw.csv","data/processed/fields_q2raw.json"],"timeoutSeconds":600}
```
```json
{"action":"register-clean","sourceFile":"data/raw/imported/419849227a02e0c7-1.csv","cleanedFile":"data/clean/q2_raw.csv","cleaningScript":"src/build_q2raw.py","fieldsFile":"data/processed/fields_q2raw.json","targetColumn":"A_malt_all","notes":"250 行；231 特征 + 50 原始目标 + 键"}
```
4. **映射用 split**：在 DATA-0001 上注册 SPLIT-0001（只用于估计 zmin/zmax，不跑实验）：
```json
{"action":"register-split","datasetId":"DATA-0001","method":"random-holdout","testFraction":0.2,"seed":20261024,"rowIdMapping":"positional"}
```
5. **mapped 数据集**：跑 `build_q1mapped.py --split SPLIT-0001`，注册 DATA-0002（parent DATA-0001）：
```json
{"action":"run-script","script":"src/build_q1mapped.py","args":["--split","SPLIT-0001"],"purpose":"mapped grade, train-only mapping","outputs":["data/clean/q1_mapped.csv","data/processed/fields_q1mapped.json","data/processed/q1_map_params.json"],"timeoutSeconds":600}
```
```json
{"action":"register-clean","sourceFile":"data/clean/q2_raw.csv","cleanedFile":"data/clean/q1_mapped.csv","cleaningScript":"src/build_q1mapped.py","fieldsFile":"data/processed/fields_q1mapped.json","targetColumn":"A_malt_all","parentId":"DATA-0001","notes":"50 维 mapped grade；zmin/zmax 仅用 SPLIT-0001 train 行估计"}
```
6. **评估用 split**：在 DATA-0002 上注册 SPLIT-0002（同 seed/同行，assignment 与 SPLIT-0001 相同）：
```json
{"action":"register-split","datasetId":"DATA-0002","method":"random-holdout","testFraction":0.2,"seed":20261024,"rowIdMapping":"positional"}
```
7. **Q3 视图**：跑 `build_q3.py`，注册 DATA-0003（`targetColumn` 选一个真实数值列，不要用字符串风格列；否则 leakage 无法算相关）：
```json
{"action":"run-script","script":"src/build_q3.py","purpose":"style holdout + defect thresholds","outputs":["data/clean/q3.csv","data/processed/fields_q3.json","data/processed/q3_style_holdout_assignment.csv"],"timeoutSeconds":600}
```
```json
{"action":"register-clean","sourceFile":"data/raw/imported/43a7b38682ed81ce-4.csv","cleanedFile":"data/clean/q3.csv","cleaningScript":"src/build_q3.py","fieldsFile":"data/processed/fields_q3.json","targetColumn":"<一个真实数值列，例如 ethanol>","notes":"风格整类留出；缺陷阈值来自 8.xlsx；不设随机 split"}
```
> `fieldsFile` 必须覆盖清洗后表的每一列**恰好一次**（2.8.6 会逐列核对）；旧项目的 `fields_*.json` 由同一脚本生成，可直接用；不要手抄，也不要写“其余列”。
门禁：`status` 的 data-ready blocker = 0；`data/raw/imported` 有 9 个文件；DATA-0001/0002/0003 存在；**SPLIT-0001 与 SPLIT-0002 的 `assignmentSha256` 必须相同**（不同就停：说明行顺序/种子不一致，映射会泄漏）；**只有 SPLIT-0002 会被实验使用**。

### Phase 2 — 契约与要求

1. **requirements**：逐条 `requirement-add`，`source.quote` 必须是题面原文精确子串（不要改写题面来适配结果）。Q1 的“0–6 分”要求要如实登记；如果交付 mapped grade，在 coverage 里用 `insufficient_data` + `blockedReason`，或由独立 review 明确接受代理口径——**不要偷偷把要求文本改成 mapped grade**。
2. **target contracts**（3 个）：`contract-add contract:"target"`，必须给 `questionId`、`researchObject`、`taskNature`、`labelSource`、`inputsAvailableAt`、`predictionTime`；Q1 的 `labelOrigin:"transformed"`，`dataset` 绑定 **DATA-0002** 的 **全部 50 个 mapped targetColumns**。
3. **model contracts**（3 个）：`contract-add contract:"model"`，必须给 `variables`（含 unit）、`objective`、`formula` 或 `boundaryCases`。公式只能用 2.8.6 的声明式子集：`constant` / `linear` / `max` / `sum`，分支 `{branches:[{condition:{gte|lte|gt|lt|eq:["x",v]},value:{...}}],default:{...}}`；**禁止 eval/自由文本**。边界样例的 `expected` 来自题面/定义，不来自生产代码。见附录 E 的 Q1 mapped-grade 公式示例。
4. 门禁：`quality status` 不再报 “no target contract / no model contract”。

### Phase 3 — baseline-ready（先基线，后候选）

每个小问都要**真的跑过**基线，且指标是 question.metric：

| 问题 | 基线 | 指标 | 说明 |
|---|---|---|---|
| Q1 | 常数基线（`params.family:"constant-train-mean"`, `params.features:[]`） | `mae` | 2.8.6 允许零特征常数模型；不要拿无关特征伪装 |
| Q2 | 全局统一 Top-3（所有维度共用一份榜单） | `topk-jaccard` | 与逐维 Top-3 的平均 Jaccard 作为“是否有增量”的锚 |
| Q3 | 无条件全局高斯（不看风格、不迁移） | `constraint-satisfaction` / 能量距离 | 这是上次的阴性结果来源，必须一开始就有 |

注册基线示例（Q1）：
```json
{"action":"register","questionId":"Q1","modelKind":"baseline","title":"B0 constant-train-mean","codeFile":"src/q1_baseline.py","datasetId":"DATA-0002","splitId":"SPLIT-0002","seed":20261024,"params":{"family":"constant-train-mean","features":[],"targetContractId":"TGT-0001","evaluation":{"kind":"multi-output","metricKey":"mae","predictionsFile":"predictions.csv","idColumn":"row","aggregation":"uniform-average"},"freezeSources":true,"dependenciesComplete":true,"dependencies":["src/lib.py","src/q1_common.py"]}}
```
门禁：`status` 的 baseline-ready blocker = 0；三问基线都有 succeeded 实验和 question.metric。

### Phase 4 — validation plan（必须在 candidate 之前！）

- **每个小问只调一次 `modeling_validate {action:"plan"}`**。plan 里 `metric` 用注册指标键；check 的 `metric` 必须与实验 `params.evaluation.metricKey` 一致。
- 推荐 checks：
  - Q1：`leakage`、`split-integrity`、`holdout-metrics`、`baseline-compare`、`independent-rerun`。
  - Q2：`leakage`、`independent-rerun`（不做 split-integrity/holdout-metrics，因为不设 splitId；`evaluation-ranking` 只有在你真的声明了加权评分协议时才用）。
  - Q3：`leakage`、`simulation-seeds`、`independent-rerun`。
- 参数必须能被执行：`split-integrity` 用已注册 split；`holdout-metrics` 需要 `predictions.csv` + split test truth；`simulation-seeds` 需要每 seed 的 run JSON 或 `params.runs`；`evaluation-ranking` 需要 weights/scores 或 criteria/items；`baseline-compare` 需要 `baselineExperimentId` 或 `baselineMetric`。
- 示例见附录 B。

门禁：三问各恰好一个 plan；`modeling` checkpoint 无 `NO_VALIDATION_PLAN`、无 `PLAN_AFTER_COMPARISON`。**plan 注册之后再跑 candidate。**

### Phase 5 — candidates + 验证 + validated select

1. 每问最多 2 个 candidate（旧项目 Q1 堆到 7 个，触发模型预算警告）。
2. 每个 candidate 注册时必须带：
   - `params.evaluation`（`kind`、`metricKey`、`predictionsFile`/`setsFile`、`idColumn`、`aggregation` 等）；
   - `params.targetContractId`；
   - `params.freezeSources:true`、`params.dependenciesComplete:true`、`params.dependencies:[...]`（含 helper 模块、数据、字段口径文件）；
   - 同一 `seed` 与 `args`，便于 verifiedRerun 判定。
3. 跑完候选后：
   - `modeling_validate {action:"run", experimentId:"EXP-…", checkTypes:[...]}` 跑计划里的非 rerun 检查；
   - `modeling_validate {action:"independent-rerun", experimentId:"EXP-…"}` 生成新实验 id 并比较；它要求原实验有 `sourceSnapshot`/`dependencies`，否则会拒绝。
   - 如果要做训练内部复跑（不碰 holdout），用 `params.evaluationUse:"train-only"` + `params.reuseSnapshotOf:"EXP-…"` + `freezeSources:true`，仅 macOS Seatbelt；非 macOS 不要声称同等隔离。
4. `modeling_project {action:"select", questionId:"Q1", modelId:"MODEL-…", selectionPhase:"validated"}`；如果 readiness 不满足，它会具名拒绝。
5. **最后**才做 validated select（它会让 question version 变化）。如果之后 `quality status` 报 target/model contract stale，用 `contract-revise` 重新绑定（不要重写结论），再补 review。

门禁：`status` 的 modeling/validation blocker = 0；三问都有 validated selection；Q1 的 independent-rerun 是**新实验 id**通过。

### Phase 6 — robustness（先登记 plan，再跑扰动）

- **稳健性实验不要用 Q1 的 holdout split**：否则 seed/alpha 每个扰动都增加一次曝光，3 次预算立刻爆掉。Q1 的稳健性用 **train-only/OOF**（不设 `splitId`；需要 macOS Seatbelt 时用 `evaluationUse:"train-only"` + `reuseSnapshotOf` + `freezeSources`，非 macOS 不要声称同等隔离）；Q2 用 train 行的 bootstrap seeds；Q3 用风格留出视图、不设随机 split。所有扰动实验与参照实验必须使用**同一指标定义**（例如都用 OOF MAE），否则 `metricKey` 对不上。
- 方法建议：`multiple-seeds` + `param-perturbation`（最便宜、最真实）。**不要用 `repeated-split`，除非你真的有不同 assignment 内容**；2.8.6 会拒绝“只换 seed/ID”的 repeated-split。
- `multiple-seeds` 要求**每个**关联实验 `params.requireSeedReceipt:true`，脚本必须调用 `modeling_contract.seed()` 产出 `seed-receipt.json`；不要 retro-fit 旧记录。
- 计划示例见附录 D；执行：
```json
{"action":"quality","subaction":"robustness-plan-add","questionId":"Q1","methods":["multiple-seeds","param-perturbation"],"perturbations":[{"name":"seed 20261024→20261025","change":{"seed":20261025}},{"name":"alpha 1000→300","change":{"alpha":300}}],"seeds":[20261024,20261025],"repeats":1,"metricKey":"mae","decisionRule":{"type":"relative-range","limit":0.05},"note":"先登记后执行"}
```
```json
{"action":"quality","subaction":"robustness-plan-execute","planId":"ROB-…","experimentIds":["EXP-…","EXP-…"]}
```
门禁：三问各有 robustness-plan + robustness-execution 且状态 passed（或按 negative_result 显式接受）；不要只登记不执行。

### Phase 7 — claims + coverage/reviews

1. **claims**（每问一条关键结论，可加辅助 claim）：
```json
{"action":"create","questionId":"Q1","statement":"在 50 维 mapped grade 上，Ridge 的留出 MAE 为 …，低于常数基线 …。","refs":[{"kind":"metric","experimentId":"EXP-…","metricKey":"mae"}],"critical":true,"claimType":"contemporaneous_association","appliesTo":"SPLIT-0001 留出的 50 款啤酒；50 维 mapped grade","limitations":["标签是 mapped grade，不是原始 0–6","映射端点假设与越界截断已披露"],"evidenceScope":"留出 50 行","targetContractId":"TGT-0001"}
```
   - Q3 若是阴性结果：`claimType:"negative_result"`，并确保 plan/claim review 是 fresh 的；不要为了绿把负结果改写。
2. **requirement coverage**：`requirement-map` 的 refs 用 `{kind:"experiment", id:"EXP-…"}` / `{kind:"figure", id:"FIG-…"}` / `{kind:"claim", id:"CLAIM-…"}`；**不要用 `experimentId/claimId/figureId` 作为 id**。示例见附录 F。
3. **reviews**（独立上下文）：
   - `review-add objectType:"targetContract", objectId:"TGT-0001", verdict:"passed"`（Q1 transformed 需要）；
   - `review-add objectType:"requirements-coverage"`（bundle 的要求）；
   - `review-add objectType:"delivery"`（如质量门要求）；
   - 用**子会话/成员**执行；root 自称 independent 会被 `review-independence` 拒绝。
4. 门禁：`quality status` 中 requirement-coverage / target-lineage / review-* 不再 failed/needs_review；claim 的 refs 能被 `claim check-stale` 验证为 fresh。

### Phase 8 — quality plan/run + freeze

**顺序很重要**：先把 requirements/contracts/claims/robustness/reviews 全部定稿，再 `quality-plan auto:true`；否则 plan 会把错误的 claim metricKey 固化成永久 QC。

```json
{"action":"quality-plan","auto":true}
```
```json
{"action":"quality-run"}
```
```json
{"action":"quality-report"}
```
- 如果某个 QC failed：**修对应记录，再 `quality-run` 同一个 check**；不要 `quality-plan` 再加一套（旧 check 不会消失）。
- 如果 failed 是 check 参数本身错了（例如 metricKey 用了子指标）：当前 ledger 无法修，**重开项目**。
- `quality-plan` 之后不要再改 claim/contract/requirement 的 key 字段；任何改动会让 check stale。

门禁：`quality report` 的 required checks 全部 passed；`needs_review` 只允许显式 `insufficient_data` 并有 review 接受；`stale=0`。

然后（freeze 前确认 `report/paper.md` 已存在——模板即可，否则 writing 的 `NO_PAPER` 会阻断）：
```json
{"action":"freeze","reason":"validation passed; claims/figures fixed"}
```
门禁：freeze 不报 blocker；`frozen.claimIds` 包含全部关键 claim。

### Phase 9 — render / check / package

1. 先把论文模板写成占位引用（`{{metric:EXP-…:mae}}`、`{{claim:CLAIM-…}}`、`{{figure:FIG-…}}`），不要手抄数字。
2. `modeling_deliver {action:"figure", experimentId:"EXP-…", path:"figures/…png", caption:"…", scriptFile:"src/make_figures.py"}` 登记所有图。
3. `modeling_deliver {action:"render"}` → `report/rendered.md`；确认无 `{{` 残留。
4. 用现有 `src/build_paper.py` 编译 md/tex/pdf；三份必须来自**同一版** `rendered.md`；改完论文要重新 render + 重新打包。
5. `modeling_deliver {action:"check"}`：
   - `engineeringComplete`、`qualityPassed`、`checkpointsPassed` 三者都为 true；
   - `final:true`；若声明了 contest，`submissionReady:true`。
6. `modeling_deliver {action:"package"}`（默认 final）；核对 manifest `final:true`、没有 `-DRAFT` 后缀、SHA256SUMS 完整、84/833 等文件数符合预期。
7. **不要**在 check 未过时 `draft:true` 打包后手工改名；DRAFT 只能作为 `final:false` 的评审稿。

---

## 6. 预算 / 监控 / 停止

1. 工程入口先 init 项目，再 `begin` 受控 run，最后才发模型请求：
```json
{"action":"quality","subaction":"run-control","control":"begin","requestAdmission":{"inputUpperBound":<实测上下文上界>,"maxOutputTokens":<上限>},"hardTokenLimit":<硬上限>}
```
2. 打开“◈ 解题监控”，确认有真实 run ID、请求上界、用量；**聊天里的预算文字不等于已配置准入**。
3. usage 出现 unknown/malformed/部分缺失：立即 `control:"stop"`，保留小计与上界，不继续付费调用；不删停止标记。
4. `control:"preflight"` 先检查 Python 模块；`control:"step"` 记录进展；`control:"resume"` 只在明确授权后。
5. 任何“为了凑通过再发一次请求”的冲动，先停下来核对预算；旧项目的教训是 unknown 后继续会掩盖真实用量。

---

## 7. 不可逆清单与故障决策树

| 现象 | 能否在当前项目修 | 正确动作 |
|---|---|---|
| init 后改了 `contest.yaml` | 否 | 重开项目；不要改 ledger |
| candidate 之后才登记 validation plan | 否（`PLAN_AFTER_COMPARISON` 永久） | 重开项目；下次 plan 前移 |
| 同一小问登记了第二个 plan | 否（plan 无删除） | 重开项目；一问一 plan |
| `quality-plan` 已跑，claim metricKey 错 | 否（QC 记录不可删/改参） | 重开项目；先修 claim 再 plan |
| requirement refs 缺 `id` | 是 | `requirement-map` 重映射 + `quality-run` 同一 check |
| MCON 缺 formula/boundaryCases | 是 | `contract-revise` 补公式/边界，`quality-run` 同一 check |
| TGT review 是 findings | 是 | 修文本后重新 `review-add`（独立上下文） |
| EXP 无 snapshot，`independent-rerun` 拒绝 | 否 | 新项目从第一天就 `freezeSources`；旧实验不能补历史证明 |
| holdout 超 3 次 | 否 | 新项目重排曝光；不要换 splitId 重置 |
| root 自称独立 review | 否（会被拒绝） | 用子会话/成员重做 review |
| unknown usage 后继续 | 不可接受 | 停止；保留证据；另授权后再动 |
| DRAFT 包改名 final | 禁止 | 重新 check/package；final 未过就交 DRAFT 并说明 |

---

## 8. 禁用 / 回滚 / 清理（按 04）

- 禁用/移除：宿主插件页操作并正常重启；不要用 PATH 旧版 dsh 改 desktop profile。
- 回滚：官方插件管理器安装 `…/建模实战整改最终交付/安装包/回滚/dsh-vibe-math-2.8.5.tgz`；必要时退出宿主，恢复 1.1 备份的 `package.json`/`pnpm-lock.yaml`/`cordis.patch.yml`。
- **不要清空 `~/.dsh`、不要删除会话、不要删除原竞赛目录。** 新项目可以保留作证据；旧项目只读。
- 隔离 CLI 复现只用于测试 profile（`DSH_HOME=/private/tmp/...`），不用于 desktop。
- 若同 profile 装过候选 2.8.6：移除候选、重装最终 SHA 包、逐字节核对；版本号不能证明字节正确。

---

## 9. 验收清单（逐项打勾）

**安装**
- [ ] 2.8.6 插件页可见；probe ok；SHA256 与 `安装包/SHA256SUMS` 一致
- [ ] 备份了 2.8.5 profile 三个文件；回滚路径可用

**配置**
- [ ] `contest.yaml` 在 init 前定稿；`problem/questions.yaml` 存在
- [ ] `shasum -a 256 contest.yaml` == ledger.configSha256（每次 status 都核对）
- [ ] `primaryMetric=mae`、`split.seed=20261024`、`robustness.methods` 非空

**数据**
- [ ] 9 个附件经 `import` 显式导入；SHA 入台账
- [ ] 完整字段清单（每列恰好一次，无“其余列”）
- [ ] base 数据集 + mapped 版本 + 两个同 assignment 的 split；只有 SPLIT-0002 被实验使用
- [ ] 曝光预算表已填；每行 ≤3

**契约**
- [ ] 3 个 target contract（Q1 transformed；Q2 observed；Q3 constraint/生成）
- [ ] 3 个 model contract（variables/units/objective/formula 或 boundaryCases）
- [ ] 6 条 requirement 的 quote 是题面精确子串；没有改写题面来适配结果

**协议/实验**
- [ ] 每问恰好一个 validation plan，且在 candidate 之前
- [ ] 每问 ≤2 candidate；baseline 都已跑
- [ ] 所有 candidate 有 freezeSources/dependenciesComplete/dependencies
- [ ] independent-rerun 是新实验 id 且通过
- [ ] validated select 三问都完成

**稳健性**
- [ ] 每问 robustness plan 先登记、后执行
- [ ] multiple-seeds 的每个实验带 requireSeedReceipt:true 与 seed-receipt
- [ ] 决策规则是对象（不是自由文本），`decisionPassed` 有记录

**结论/审查**
- [ ] claims 的 metricKey 全是注册指标键
- [ ] requirement refs 全是 `{kind,id}`
- [ ] target/coverage/delivery review 由独立上下文执行且 passed
- [ ] 没有 critical open finding

**质量/交付**
- [ ] `quality-report` required checks 全 passed；stale=0
- [ ] `freeze` 成功；frozen 包含全部关键 claim
- [ ] `delivery check` final=true；submissionReady=true（若声明 contest）
- [ ] md/tex/pdf 来自同一 rendered.md；无 `{{` 残留；包内 manifest final:true
- [ ] 所有图已登记；论文数字全部占位符解析

---

## 附录 A：`problem/questions.yaml` 骨架

```yaml
questions:
  - id: Q1
    title: "50 维感官评分的可复核代理（mapped grade）预测"
    objective: "用 1.csv 的 231 个化合物/理化特征预测 4.csv 的 50 维感官目标；原始 0–6 不可识别，交付显式 mapped grade。"
    inputs: ["1.csv 231 特征", "4.csv 50 维目标", "SPLIT-0002（评估）；SPLIT-0001（仅映射参数估计）"]
    outputs: ["predictions.csv（50 维）", "MAE/R²", "误差分层图"]
    constraints: ["映射参数只用训练集", "不得用 4/5/6/7/8.xlsx MDI/SHAP 作特征", "混合尺度逐列处理"]
    evaluation: "50 维等权 MAE（uniform-average）；另报逐维 MAE 与 OOF"
    metric: mae
    needsData: true
    needsBaseline: true
  - id: Q2
    title: "化合物–风味 Top-3 与稳定性"
    objective: "对 50 个感官维度给出 Top-3 关键化合物，并用 bootstrap 与方法间 Jaccard 量化稳定性。"
    inputs: ["1.csv 231 特征", "2.csv 相关矩阵", "4.csv 50 维目标", "SPLIT-0001 的 train 行"]
    outputs: ["sets.json（每维 Top-3）", "Jaccard/入选频率", "候选簇"]
    constraints: ["2.csv 先 PSD 投影", "只做同期关联，不宣称因果", "5/6/7.csv 不是独立外部验证"]
    evaluation: "方法间 Top-3 Jaccard + bootstrap 入选频率"
    metric: topk-jaccard
    needsData: true
    needsBaseline: true
  - id: Q3
    title: "风格条件生成与跨风格迁移"
    objective: "以 tasting_category_fine 为条件学习生成模型；Tripel/Kriek/Lambic 整类留出；跨风格迁移时缺陷不恶化。"
    inputs: ["1.csv 231 特征", "风格标签", "8.xlsx 缺陷阈值"]
    outputs: ["生成/迁移谱", "能量距离", "缺陷超阈值率", "感官画像"]
    constraints: ["风格整类留出，不得随机划分冒充", "缺陷列不平移", "结论只写生成合理性/约束满足，不写真实酿造验证"]
    evaluation: "能量距离 + 缺陷不恶化 + 约束满足"
    metric: constraint-satisfaction
    needsData: true
    needsBaseline: true
```

---

## 附录 B：validation plan 模板（按 2.8.6 的实际参数）

> 2.8.6 的检查参数名与旧版不同：`baseline-compare` 读 `baselineExperimentId`（不是 `baselineId`）；`leakage` 读 `forbiddenColumns` + `correlationThreshold`（不是 `forbiddenSources`）；`holdout-metrics` 的预测文件来自实验 `outputFiles` 的 `predictions.csv`（不是 plan 里的 `predictionsFile`）。下列模板按 2.8.6 写。

**Q1**：
```json
{"action":"plan","questionId":"Q1","protocolNote":"在候选比较前登记；mapped grade 口径；holdout 只评估一次","checks":[
  {"checkType":"leakage","required":true,"metric":"mae","params":{"correlationThreshold":0.999,"forbiddenColumns":["<8.xlsx 派生列的真实列名，没有就 []>"]}},
  {"checkType":"split-integrity","required":true,"metric":"mae","params":{"expectedRows":250}},
  {"checkType":"holdout-metrics","required":true,"metric":"mae","params":{"keyColumn":"row","aggregation":"uniform-average","nTargets":50}},
  {"checkType":"baseline-compare","required":true,"metric":"mae","params":{"baselineExperimentId":"EXP-0001"}},
  {"checkType":"independent-rerun","required":true,"metric":"mae","params":{"reruns":1}}
]}
```

> **重要**：2.8.6 的 `featureColumns` 必须是**列名数组或 JSON 数组字符串**；写数字 `231` 会被具名拒绝（`neither a list nor a JSON array string`）。优先把 231 个真实列名写进实验注册的 `params.features`（leakage 会优先读它）；plan 里可省略 `featureColumns`。`forbiddenColumns` 也必须是真实列名，不是文件名。

**Q2**（train 行上的关联分析；不设 `splitId`，所以不做 split-integrity/holdout-metrics；不硬套 `evaluation-ranking`，除非你有明确的加权评分协议）：
```json
{"action":"plan","questionId":"Q2","protocolNote":"train 行上的关联分析；2.csv PSD 投影；不做 holdout 预测；稳定性用 bootstrap/Jaccard + 独立复跑","checks":[
  {"checkType":"leakage","required":true,"metric":"topk-jaccard","params":{"correlationThreshold":0.999,"forbiddenColumns":["<目标列/派生列的真实列名>"]}},
  {"checkType":"independent-rerun","required":true,"metric":"topk-jaccard","params":{"reruns":1}}
]}
```
> 如果要用 `evaluation-ranking`，必须提供 2.8.6 认的 `scores/weights/directions` 或 `criteria/items` + `weightTolerance`；只有 `{topK,methods,bootstrap}` 会被具名拒绝。

**Q3**：
```json
{"action":"plan","questionId":"Q3","protocolNote":"Tripel/Kriek/Lambic 整类留出；缺陷阈值 8.xlsx；能量距离/不恶化率；每 seed 产出 run JSON","checks":[
  {"checkType":"leakage","required":true,"metric":"constraint-satisfaction","params":{"correlationThreshold":0.999,"forbiddenColumns":["<8.xlsx MDI/SHAP/price 的真实列名，没有就 []>"]}},
  {"checkType":"simulation-seeds","required":true,"metric":"constraint-satisfaction","params":{"metric":"constraint-satisfaction","expectedRange":{"min":0,"max":1},"requiredSeeds":3}},
  {"checkType":"independent-rerun","required":true,"metric":"constraint-satisfaction","params":{"reruns":1}}
]}
```
> `simulation-seeds` 的 run 证据来自实验 `outputFiles` 里 `run*.json` / `seed_*.json`（脚本必须每 seed 产一个）；也可显式 `params.runFiles:["experiments/EXP-…/run-seed-…json"]`，或 `params.runs:[{seed,metrics:{…}}]`。没有 run 证据会被具名拒绝。`targetColumns` 不是 leakage 的参数；优先用实验注册的 `params.features`（231 个真实列名），或 plan 里传列名数组的 `featureColumns`，再加 `correlationThreshold` 和真实 `forbiddenColumns`。

---

## 附录 C：candidate 注册模板（Q1 Ridge）

```json
{"action":"register","questionId":"Q1","modelKind":"candidate","title":"C1 Ridge α=1000","codeFile":"src/q1_candidate.py","datasetId":"DATA-0002","splitId":"SPLIT-0002","seed":20261024,"args":["--family","ridge","--alpha","1000"],"params":{
  "family":"ridge","alpha":1000,"features":["<231 个真实列名，由脚本生成，不手抄>"],
  "targetContractId":"TGT-0001",
  "evaluation":{"kind":"multi-output","targetContractId":"TGT-0001","metricKey":"mae","predictionsFile":"predictions.csv","idColumn":"row","aggregation":"uniform-average"},
  "freezeSources":true,"dependenciesComplete":true,
  "dependencies":["src/lib.py","src/q1_common.py","src/prepare.py","analysis/sensory/targetcolumns.csv","data/clean/q1_mapped.csv"]
}}
```

要点：
- `features` 长度 = 231；由 `data/clean/q1_mapped.csv` 的 231 个特征列生成，不要手写。
- `evaluation.metricKey` 必须是 `mae`；脚本 `emit_metrics` 的键也要是 `mae`。
- `predictions.csv` 的 id 列 `row` 必须与 split test 的注册 ID 对齐（`rowIdMapping:"positional"` 时是 0..n-1）。
- `dependencies` 包含所有 helper/calibration 文件；少一个都会让 `verifiedRerun` 判定失败。

---

## 附录 D：robustness plan 模板（Q1）

```json
{"action":"quality","subaction":"robustness-plan-add","questionId":"Q1",
 "methods":["multiple-seeds","param-perturbation"],
 "perturbations":[{"name":"seed 20261024→20261025","change":{"seed":20261025}},{"name":"alpha 1000→300","change":{"alpha":300}}],
 "seeds":[20261024,20261025],"repeats":1,"metricKey":"mae",
 "decisionRule":{"type":"relative-range","limit":0.05},
 "budget":{"bootstrapIterations":2000,"bootstrapSeed":20261024},
 "note":"先登记，后执行；结果是稳定性，不是改名复跑"}
```
执行实验时每个关联实验都要 `params.requireSeedReceipt:true`，脚本调用 `modeling_contract.seed()`；然后：
```json
{"action":"quality","subaction":"robustness-plan-execute","planId":"ROB-…","experimentIds":["EXP-…","EXP-…"]}
```
> `repeated-split` 只在“不同 assignment 内容”时用；`external-validation` 会自动 needs_review，不能自证独立。

---

## 附录 E：Q1 mapped-grade 模型契约公式示例

以某一维（如 `A_malt_all`）为例，`zmin/zmax` 取自训练集；公式只用声明式子集：

```json
{
  "formula": {
    "branches": [
      {"condition": {"gte": ["z", 6.1234]}, "value": {"constant": 6}},
      {"condition": {"lte": ["z", -2.3456]}, "value": {"constant": 0}}
    ],
    "default": {"sum": [
      {"linear": [{"var": "z", "coef": 0.7083}]},
      {"constant": 1.6602}
    ]}
  },
  "boundaryCases": [
    {"id": "z=zmin", "inputs": {"z": -2.3456}, "expected": 0, "unit": "score", "reason": "训练集最小→0"},
    {"id": "z=zmax", "inputs": {"z": 6.1234}, "expected": 6, "unit": "score", "reason": "训练集最大→6"},
    {"id": "mid", "inputs": {"z": 1.8889}, "expected": 3, "unit": "score", "reason": "线性中点"}
  ]
}
```
> 系数/端点必须从 `data/processed/q1_map_params.json` 里取真实值；`linear` 不能自带截距，所以用 `sum:[{linear},{constant}]`。不要用自由文本或 eval。

---

## 附录 F：requirement-add / requirement-map 正确写法（旧项目就错在这里）

先逐条登记（`quote` 必须是**当前题面文件**里的精确子串；题面是从 PDF 抽取的，含空格/换行伪影，示例只示意格式，务必用 `grep -F` 或脚本核对后再提交）：

```json
{"action":"quality","subaction":"requirement-add","questionId":"Q1","kind":"must_answer","text":"Q1 给出 3.xlsx 中定义的 Aroma 与 Flavour 两套、共约 40 个感官维度的 0–6 分制评分结果","source":{"path":"problem/2026年MathorCup大数据挑战赛-赛道A初赛.md","quote":"给出 3.xlsx 中定义的 Aroma 与 Flavour 两套、共约 40 个感官维度的 0–6 分制的分级评分结果"}}
```

再映射（refs 的 id 字段是 `id`，不是 `claimId/experimentId/figureId`）：

```json
{"action":"quality","subaction":"requirement-map","requirementId":"REQ-0001","coverage":"covered","refs":[
  {"kind":"experiment","id":"EXP-0002"},
  {"kind":"figure","id":"FIG-0001"},
  {"kind":"claim","id":"CLAIM-0001"}
]}
```
**不要**写 `{"kind":"experiment","experimentId":"EXP-0002"}`——检查读的是 `ref.id`，旧项目因此 6 条全部报 “experiment  does not exist”。

---

## 附录 G：跑前 60 秒 preflight（读台账，不写）

```bash
cd "$PROJ"
python3 - <<'PY'
import json, hashlib, sys
L=json.load(open('state/ledger.json'))
cfg_sha=hashlib.sha256(open('contest.yaml','rb').read()).hexdigest()
errs=[]
if cfg_sha != L.get('configSha256'): errs.append('config sha changed since init')
plans={}
for p in L.get('validationPlans',[]): plans.setdefault(p['questionId'],[]).append(p['id'])
for q,ids in plans.items():
    if len(ids)!=1: errs.append(f'{q} has {len(ids)} plans: {ids}')
for e in L.get('experiments',[]):
    if e.get('modelKind')=='candidate' and e.get('status')=='succeeded' and not e.get('sourceSnapshot'):
        errs.append(f'{e["id"]} candidate has no sourceSnapshot')
for c in L.get('claims',[]):
    for r in c.get('refs',[]):
        if r.get('kind')=='metric':
            exp=next((x for x in L['experiments'] if x['id']==r['experimentId']),None)
            k=(exp or {}).get('params',{}).get('evaluation',{}).get('metricKey')
            if k and r.get('metricKey')!=k: errs.append(f'{c["id"]} metricKey {r["metricKey"]} != {k}')
for r in L['quality'].get('requirements',[]):
    for ref in (r.get('coverage') or {}).get('refs',[]):
        if ref.get('kind') in ('claim','experiment','figure') and not ref.get('id'):
            errs.append(f'{r["id"]} ref missing id')
print('\n'.join(errs) if errs else 'PREFLIGHT OK')
sys.exit(1 if errs else 0)
PY
```
> 在 `quality-plan` 之前跑；任何一条不 OK，先修记录（不能修的，重开项目）。

---

## 一句话总结

**先把配置写死，再把协议写在候选之前，再把每个记录一次写对；不可删的记录（plan/check）绝不试错；一旦越过不可逆门，重开项目比修补便宜。**
