# REVIEW-R04 确认性轮次独立复审（MathorCup 2026 A / R03→R04）

- 审查者：`independent-reviewer`（独立上下文；只读项目，唯一写入 = 本文件）
- 项目：`P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6`；台账 revision 4132（updatedAt 2026-10-26T13:11:52Z）
- 方法：不采信执行者自述与 `.rework/R04-independent-recompute.json` 的结论，全部数字用独立脚本从原始产物重算；无法核验项列入 §cannotVerify。
- 未调用 `modeling_*`、未跑实验、未训练、未改任何其他文件。

---

## 0 总裁定

| 项 | 结果 |
|---|---|
| **readiness** | **B = READY_FOR_DRAFT_PAPER_ONLY**（数值证据可支撑草稿；最终稿被 paper 未更新 + 3 条 QC failed + Q1/Q3 provisional + 确认轮验证/评审缺失挡住） |
| checks | 3 PASS（C1/C3/C5）· 3 PARTIAL（C2/C4/C6） |
| 重算 | 17 个数值 + 1 组哈希同一性独立复现，全部与 claims 相符；另发现 4 处「口径/标签与数字不匹配」 |

**一句话**：R04 把 R03 里被指出的**文本性/披露性**问题真修了（questions 三问重写、analysisPlan 重配、claims 逐条自我设限），确认性实验是**逐字节确定性重放**且如实标注；但**验证层基本空转**（11 项 VP 必查只执行 1 项）、**Q2 validated 无确认轮验证背书**、**Q1/Q3 provisional 无台账理由**、**论文仍停在 10-24 并引用 6 条已撤回 claim**。

---

## 1 六项检查结论

### C1｜questions.yaml 与 ledger questions 文本 —— **PASS**

- **逐字一致**：三问的 title/objective/evaluation 与全部 constraints/inputs/outputs，在 `problem/questions.yaml` 与 `state/ledger.json questions[]` 中完全同一文本（我按字段做了字符串包含校验，逐项 True；无一处 ledger 独有或 yaml 独有）。
- **Q1 旧表述已删/改**：
  - 已无「20% 留出为主」「同一 SPLIT-0002 上可比」「HGB 对照」；现行主指标 = **Aroma/Flavour 30 项等权 OOF MAE**（`metricKey=mae`，750 行池化）；objective 明写「本问不含任何留出集承诺：4.csv 全部 250 行都进入内部重验证」。
  - 残留仅两处且均为**否定式**：constraints[4]「本轮不执行 HGB 与任何单次 20% 留出评估；旧 SPLIT-0002 结果只作历史，不参与本轮比较」；objective「不含任何留出集承诺」。不构成旧表述残留。
- **Q2 旧表述已删/改**：6.csv 固定为「**同源排序对照**（…6.csv 为同源参考表，不是独立外部验证，也不参与选择）」；严格 216 / 扩展 15 分表；constraints[4] 明写「**协议不得表述为嵌套交叉验证**：无 outer/inner 折、无逐行 OOF，50 行测试样本未参与任何计算」。全项目 questions 文本中已无「与 6.csv 独立 |r|」。
- **Q3 已改为分层口径**：生成侧 constraint-satisfaction **+ 归一化经验 V（n_gen 加权池化）+ 同风格重采样参照 + 有符号 U**；迁移侧按策略分层（逐化学列不增率 + source-fixed 平凡对照 + QP 状态/原始对偶残差 + 归一化与原始 V + PCA 中心化目标均值自距）；并强制披露「1.000 由投影循环保证、边界夹断规模、未核验比例、censor 地板码」。
- **仍存在的旧文本在题面之外**（不改变 C1 判定，但对交付致命）：`report/paper.md` 仍是 10-24 版本，10 处占位符引用 **6 条已撤回 claim**（`report/paper.md:131,180,246,282,327-332` → CLAIM-0014/0019/0022/0012/0018/0021），0 处引用 CLAIM-0036..0039；见 F1。

### C2｜analysisPlan 与题面一致性 / 是否隐藏 features 或降 profile —— **PARTIAL**

| 问 | 结果 |
|---|---|
| configuredAt 是否早于实验 | ✅ 三问分别 `2026-10-26T13:04:44.849Z / 13:04:52.523Z / 13:04:56.582Z`，均早于 VP 注册（13:05:12-20）与首个确认性实验（13:06:12） |
| Q1 | ✅ profile=prediction、metricDirection=minimize、features=231（全部 `chem__*`）、excludedFeatures=50（正好 50 个感官目标），notes 与题面一致 |
| Q3 | ✅ profile=open-question、features=0、无预测目标，与「生成+约束迁移」相符；minimumModelFamilies=2（generation+transfer） |
| Q2 | ⚠️ **features=37，与模型实际输入（231 列）/候选宇宙（231×50）不一致**；这 37 项是「若干化合物 + iron/protein/betaglucan + 7 理化 + 4 派生和 + nonenal」的人挑子集，既非 231 输入，也不是交付 Top-3 里出现的 55 个化合物（`outputs/q2/factor_analysis.csv` 有 55 个不同化合物，其中 42 个不在这 37 项里）。EXP-0075 登记 `params.features` 长度 = **231**（leakage 检查用的是这 231 项） |
| 是否「隐藏 features」 | ❌ 无证据。实际特征在实验登记里是完整 231 项，分析计划是**少报**而非多报；无法从减少的清单里夹带未声明输入 |
| 是否「降低 profile 绕过 validated」 | ❌ 无证据。profile 与任务性质匹配（关联研究 ≠ 预测），minimumModelFamilies 未被压低（Q1=4 对 4 模型、Q2=2 对 4 方法）；Q2 得到 validated 的原因不是 profile 降级，而是其 VP 未列 holdout-metrics（见 C6/F3） |

### C3｜VP-0012/0013/0014 的登记时序与 protocolNote 诚实性 —— **PASS**

| 项 | 事实 |
|---|---|
| VP-0012 registeredAt | `2026-10-26T13:05:12.043Z` < EXP-0073 startedAt `13:06:12.519Z` ✅（差 60s） |
| VP-0013 registeredAt | `13:05:12.889Z` < EXP-0075 `13:06:23.302Z` ✅ |
| VP-0014 registeredAt | `13:05:20.962Z` < EXP-0076 `13:07:46.910Z` ✅ |
| protocolNote 诚实性 | ✅ 三份都明写：(1) 先前 EXP/VP 属**探索性先导轮**；(2) 本 VP 登记于本轮确认性实验之前；(3) 数据与旧结果已被查看，本轮是「**锁定协议后的确认性复跑/内部重验证**」，**不是首次预注册**，也**不是外部独立测试**；VP-0012 另写「独立复跑 = fixed-seed deterministic reproduction（不是独立实现）」与「holdout-metrics 在 train-only 嵌套 CV 下**结构性不可满足**」。 |
| 承诺兑现 | ⚠️ VP-0012 写着「该检查失败将如实保留为 selection 的具名 blocker」，但**台账中并不存在 EXP-0073 的 holdout-metrics 验证记录**（该 VP 下只有 VAL-0055 一条 independent-rerun）；见 F2。 |

### C4｜EXP-0073..0078 的来源冻结、依赖 SHA、与先导轮同一性 —— **PARTIAL**

| 实验 | dependenciesComplete | 依赖 SHA | freezeSources | sourceSnapshot | 运行路径 |
|---|---|---|---|---|---|
| EXP-0073 | true | 6/6 全部有 SHA 且与当前文件一致 | **true** | ✅ `inputs/`（6 文件，含 code） | 快照 |
| EXP-0074 | true | 5/5 一致 | **true** | ✅ | 快照 |
| EXP-0075 | true | 13/13 一致 | **true** | ✅ | 快照（`seed_receipt_wrapper.py` 包 `q2_fix.py`） |
| EXP-0076 | true | 10/10 一致 | **缺失** | **null（无 `inputs/`）** | **live `src/q3_fix.py`** |
| EXP-0077 | true | 11/11 一致 | **缺失** | **null（无 `inputs/`）** | **live `src/q3_transfer_fix.py`** |
| EXP-0078 | true | 6/6 一致（指向 EXP-0073 快照） | false | ✅（`reuseSnapshotOf=EXP-0073`，已声明） | 快照 |

- **同一性（是否只是确定性重现）**：是。不仅 metrics，连逐行产物都**逐字节相同**：`EXP-0073/oof_long.csv`(=9,545,500B)、`predictions.csv`、`inner_grid.json` 与 EXP-0039/0048 同 sha；`EXP-0075/{sets.json,bootstrap_pi.csv,candidate_scores.csv}` 与 EXP-0041 同 sha；`EXP-0076/{samples.csv,constraints.csv,q3_metrics.csv}` 与 EXP-0042 同 sha；`EXP-0077/{transfers.csv,solver_certificates.jsonl,transfer_constraints.csv}` 与 EXP-0043 同 sha；`EXP-0078` 与 EXP-0073 同 sha。metrics SHA：0073=0039=0048=`1dcce1aa…`，0074=0038=`19a74561…`，0075=0041=0071=0072=`27f90dad…`，0076=0042=0050=`f6d5e524…`，0077=0043=0051=`8d3574f5…`。
- **是否用旧 EXP metrics 冒充新结果**：❌ 无。每个确认性实验都有自己的 `experiment.json/result.json/run.json/heartbeat/stdout/token`，有真实起止时间与 exit 0（0073 2.45s、0075 77.0s、0076 58.5s、0077 7.9s、0078 2.1s）；claims 每一条都主动写「确认轮与先导轮数字逐位相同 → **只确认冻结流程可重现**」，没有把它包装成新信息。
- **Q2 补丁的合法性**：EXP-0075 用 `--patch-align-to data/processed/sensory_name_alignment.csv` 绕开非 ASCII 路径；我核对被替换文件与原件 **sha256 完全相同**（`971a0e47…`），是字节等价替换，不是改输入。
- 缺口只在 **Q3 两个确认性实验没有冻结源**（无 snapshot、直接跑 live src），见 F5。

### C5｜独立重算 —— **PASS（数字全中；4 处口径/标签需订正）**

见 §3 `recomputed`。要点：
- `.rework/R04-independent-recompute.json` 自身承认其 **π 与 claim 不可比**，且 **Q3 负值列是 storage-space**（≠ 校准线性浓度）；我按 claim 的真实定义另行重算，两者都成立但**该文件不能直接当作 claim 证据**。
- 另发现 3 处「数字对、标签错」：`0.1199` 是 `edge-fraction` 而非约束贴边；`3.556e-17/1.804e-16` 是约束残差而非 transfers 的 new−source 差；`decision.md` 的「removes all 142 negative」是旧 v5 口径。

### C6｜claims 与状态、QC —— **PARTIAL**

- **CLAIM-0036..0039（均 active/critical/stale=false）的 19 个 metric ref 全部解析成功且数值与 statement 相符**（我逐条对照，并在 §3 独立重算）。
- **statement 没有明显强于证据**，反而在多数条目上主动自我设限（比历史口径更保守）：
  - 0036：「确认轮与先导轮数字逐位相同 → 只确认冻结流程可重现」；limitations 写「不构成新信息」「Q1 selection 仍为 provisional：原生 holdout-metrics 在 train-only 嵌套 CV 下结构性不可满足」「本轮未产出逐维汇总表与评分卡映射」。
  - 0037：「不是嵌套 CV、无 OOF，50 行测试样本未参与」「6.csv 只是同源排序对照…不是独立外部验证」「稳定性偏低属实：1800 个入选中 1263 个 π<0.5」。
  - 0038：「该值由投影循环保证、约束集含 stale_hops 的 Ridge 代理上界，不能读成全由化学/物理约束构成」+ 行级夹断 508/361/46 + verified 68.84% + 494/750 行 4VG 地板码。
  - 0039：「什么都不做的 source-fixed 对照四列同为 99/99=1.000 → 该指标对『是否真的迁移』零区分度」「主策略下 t2n 感官代理仍 7/99 上升」。
- **但状态层有三处「标签强于记录」**（见 F2/F3/F4）：
  1. 11 项 VP 必查只执行 1 项（VAL-0055）；Q2/Q3 确认性实验**零验证**；
  2. Q2 `validated` 无确认轮验证背书，只继承先导轮 VAL-0053/0054（EXP-0071/0072）；
  3. Q1/Q3 `provisional` 在 question 记录里没有理由、没有 selectedAt、没有 selectionEvidence（三者全 null）；Q3 的原因**不能**归到 holdout-metrics（VP-0014 根本没有此项）。
- **QC-0020 仍 failed，理由属实**：`report/paper.md` 仍以占位符引用 6 条已撤回 claim（10 处）。
- **QC-0033 仍 failed，理由字面属实**：EXP-0017/18/26/35/36 缺 input feature manifest（0017/18 只有 `featuresRef`，0035/36 的 `featuresRef=null`；均无 `params.features`）。属**继承自旧实验**的失败，不由 R04 证据造成，但会让 Q1 的 analysis-evidence 永远不过。
- 另：QC-0002 也仍 failed（REQ-0007 仍把已撤回的 CLAIM-0032 放在 refs 里）；4 条新 claim **没有任何评审记录**（REV 最新 4 条只覆盖 CLAIM-0026..0030）。

---

## 2 findings

```json
[
 {"severity":"critical",
  "text":"论文层未随 R03/R04 更新：report/paper.md 仍是 2026-10-24 版本，10 处占位符引用 6 条已撤回 claim，0 处引用 CLAIM-0036..0039；rendered/tex/pdf 仍是 10-24 产物；31 张图 0 张来自 R04 实验；QC-0020 因此仍 failed。最终稿若现在打包，正文仍会断言被撤回的旧结论。",
  "evidence":"report/paper.md:131,180,246,282,327-332；report/{paper.tex,paper.pdf,rendered.md} mtime=10-24；ledger QC-0020(state/ledger.json:137357)；figures 全部绑定 EXP-0003..0035"},

 {"severity":"major",
  "text":"确认性验证层几乎空转：VP-0012(5 项)+VP-0013(2 项)+VP-0014(4 项) 共 11 项 required 检查，本轮只执行 1 项（VAL-0055 independent-rerun）；EXP-0075/0076/0077 没有任何 validation 记录（leakage、baseline/optimization-feasibility/objective、independent-rerun 全部未跑）；VP-0012 承诺『holdout-metrics 失败将保留为具名 blocker』，但台账没有任何 EXP-0073 的 holdout-metrics 记录。",
  "evidence":"ledger validations 仅 VAL-0055(EXP-0073)/2026-10-26T13:10:02Z 属 R04；VP-0012/13/14 protocolNote:76493/76528（VP-0014 76535 起）；validations 中 VP-0013/VP-0014 计数为 0"},

 {"severity":"major",
  "text":"Q2 selectionStatus=validated 缺少确认轮验证背书：CLAIM-0037 引用的 EXP-0075 无 leakage、无 independent-rerun；Q2 的 VAL-0053/0054 绑定的是先导轮 EXP-0071/0072（VP-0011 登记于 08:48:11，晚于 EXP-0071 启动的 08:46:51，早于 EXP-0072 的 08:48:17）。Q2 与 Q1/Q3 证据强度相同（无 holdout、无独立实现、确认轮为逐字节重放），却因 VP-0013 未列 holdout-metrics 而拿到 validated——差别在检查清单，不在证据。",
  "evidence":"state/ledger.json:1104(selectionStatus validated)；CLAIM-0037 validationIds=[]；VAL-0053/0054(EXP-0071/0072, VP-0011)；VP-0013 仅含 leakage/independent-rerun"},

 {"severity":"major",
  "text":"Q1/Q3 的 provisional 没有台账理由：questions[Q1/Q3] 的 selectionReason=null、selectedAt=null、selectionEvidence=null。Q1 的原因仅写在 CLAIM-0036 limitation（holdout-metrics 结构性不可满足，属实）；Q3 的原因无处记录，且不能归因于 holdout——VP-0014 的 4 项检查里没有 holdout-metrics，它的 provisional 实际是「4 项必查一项未跑」。",
  "evidence":"state/ledger.json:959(Q1)/1161(Q3)；CLAIM-0036 limitation；VP-0014 checks=[leakage, optimization-feasibility, optimization-objective, independent-rerun]"},

 {"severity":"major",
  "text":"Q3 确认性实验未冻结来源：EXP-0076/0077 无 sourceSnapshot、无 params.freezeSources，run.json 显示直接执行 live src/q3_fix.py 与 src/q3_transfer_fix.py；而 CLAIM-0033/0034 的 retractedReason 写「已由 CLAIM-0038/0039 以 EXP-0076/0077（VP-0014，freezeSources）重建」——与这两条实验的实际登记不符（EXP-0073/0074/0075 才带 freezeSources）。",
  "evidence":"experiments/EXP-0076/experiment.json、EXP-0077/experiment.json（无 freezeSources/sourceSnapshot，grep 计数 0）；EXP-0076/run.json cmd 指向 src/q3_fix.py；CLAIM-0033/0034 retractedReason"},

 {"severity":"major",
  "text":"Q2 analysisPlan.features=37 与实际分析不符：模型输入是 231 列（EXP-0075 登记 params.features=231，候选矩阵 231×50），37 项既非 231 输入也不是交付 Top-3 的 55 个化合物。方向是『少报』而非夹带，故不构成隐藏 features 或 profile 降级，但 analysisPlan 作为记录中的证据计划与实际分析不一致。",
  "evidence":"state/ledger.json Q2.analysisPlan.features(37)；experiments/EXP-0075/experiment.json params.features=231；outputs/q2/factor_analysis.csv(55 compounds)"},

 {"severity":"major",
  "text":"4 条新 critical claim（CLAIM-0036..0039）没有任何独立评审记录；最新 REV-0040..0044 只覆盖 CLAIM-0026..0030。quality.review.required=true 下，当前 active 的 4 条关键结论处于「未经评审」状态。",
  "evidence":"ledger quality.reviews：reviewed claim ids 到 CLAIM-0030 为止；QC-0018/QC-0019 仍 passed（只校验已有评审的来源，不校验关键 claim 是否被评审）"},

 {"severity":"minor",
  "text":"CLAIM-0038 的『单元格级贴边 0.1199（20775/173250）』与代码定义不符：q3_fix.edge_fraction 统计的是『地板码 / 观测支撑 min-max / 线性 0』的单元格占比，不是约束上界命中率；把它紧接在 508/361/46 行级夹断之后，读者会误以为这是约束边界贴边规模。REV-0043 已提出同一问题（被标 resolved），本轮 CLAIM-0038 仍复现该并置。",
  "evidence":"src/q3_fix.py:480-490(edge_fraction 定义)；CLAIM-0038 statement；我重算 edge_fraction 加权=0.1199134199132130、20775/173250=0.1199134"},

 {"severity":"minor",
  "text":"CLAIM-0039『实测 nonenal max Δ=3.556e-17、四列最大 Δ 为双乙酰 1.804e-16』取自 transfer_constraints.csv 的 residual（约束残差），不是 transfers.csv 的 new−source 差；后者实测 nonenal=0、双乙酰=1.11022e-16。数字可追溯，但『Δ』标签与来源文件不符。",
  "evidence":"experiments/EXP-0077/transfer_constraints.csv residual（nonenal 3.55618e-17、butanedione 1.80411e-16）；transfers.csv physical new−source（0、1.11022e-16）"},

 {"severity":"minor",
  "text":"`.rework/R04-independent-recompute.json` 的 π 与 claim 的 π 不可比，但其解释写成『per-slot stability normalisation』，实际差别是统计总体：claim 的 0.420457/1263 是 1800 个**交付条目**（50 维×4 方法×3 名次×3 重复）的均值/计数，该文件算的是 16032 个 (dimension,method,compound) 成员的入选频率均值 0.0374。claim 的 π 我另行从 500 次轨迹重算并 1800/1800 精确复现，故结论不受影响。",
  "evidence":".rework/R04-independent-recompute.json Q2.pi_note(+pi_mean_groupwise 0.037425/15854)；experiments/EXP-0075/repeat{0,1,2}/strict_top3_by_method.csv 与 bootstrap_pi.csv（1800 条 π 全部逐位命中）"},

 {"severity":"minor",
  "text":"Q3 题面 constraint 要求『风格整类留出（Tripel/Kriek/Lambic）不得用随机划分冒充』，但 R04 交付物没有任何 unseen-style 结果；q3_style_protocol.json 把它声明为『另行报告的扩展』，而 claims/方法文档未披露该扩展未做。",
  "evidence":"data/clean/q3_style_protocol.json excludedStyles/excludedStyles note；CLAIM-0038 appliesTo『22 styles』；outputs/q3/method.md 无相关说明"},

 {"severity":"minor",
  "text":"outputs/q3 的说明文件与当前证据不一致：method.md 写『as implemented in EXP-0042 / EXP-0043』（先导轮 id）；decision.md 写投影『removes all 142 negative linear concentrations』，但当前原始抽样本身就有 0 个校准线性负值（142 是旧 v5 谱的缺陷计数）。",
  "evidence":"outputs/q3/method.md:1；outputs/q3/decision.md 第 1 条；我重算 samples.csv 与 samples_raw.csv 的线性列负值均为 0"},

 {"severity":"minor",
  "text":"QC-0002 仍 failed 且原因未清：REQ-0007 同时引用 CLAIM-0036..0039（active）与 CLAIM-0032（retracted/stale），导致 requirement-coverage 失败；这与 paper 无关，属台账记账残留。",
  "evidence":"state/ledger.json:126743(QC-0002)；REQ-0007 refs"},

 {"severity":"minor",
  "text":"QC-0033 的失败是继承性的：它点名 EXP-0017/18/26/35/36 缺 input feature manifest（0017/18 仅有 featuresRef，0035/36 连 featuresRef 也为 null）。理由字面属实，但不反映 R04 证据缺陷（EXP-0073 有 231 项 features 清单）。",
  "evidence":"state/ledger.json:165099(QC-0033) + experiments/EXP-00{17,18,26,35,36}/experiment.json params"}
]
```

---

## 3 recomputed（我实际重算的数值）

全部从原始逐行产物计算（项目解释器，只读）；括注与 claim 对照。

**Q1（`experiments/EXP-0073/oof_long.csv`，150000 行；model=`graph-lowrank`，22500 行 A/F30）**
1. A/F30 等权 MAE = **0.3592915658821918**（claim 0.359292 / metrics 0.35929156588219174）✅
2. 全 50 维 MAE = **0.35050415692002407**（claim 0.350504）✅
3. Aroma15 = **0.364626380622291**；Flavour15 = **0.3539567511420926**；Other20 = **0.3373230434767725**（claim 0.364626 / 0.353957 / 0.337323）✅
4. 三对照：median **0.398177328372889**、ridge(γ=0,r=50) **0.366661758010525**、graph-ridge **0.366411015782692**（claim 0.398177/0.366662/0.366411）✅
5. 逐重复 A/F30：**0.3542235461855925 / 0.36243390816790516 / 0.36121724329307775** ✅
6. 逐折范围：**0.34498906961519554 – 0.37313415100959674**（claim「0.34499–0.37313」）✅
7. 每瓶每 repeat 每目标 (beer,repeat,target) 重复行 = **0**；22 个风格的 MAE 与 `outputs/q1/error_analysis.csv` **22/22 完全一致**，按 n_rows 加权回 **0.3592915658821918** ✅

**Q2（`EXP-0075/repeat*/sets.json` + `bootstrap_pi.csv` + `strict_top3_by_method.csv`）**
8. 每 repeat 两两 Jaccard（300 对）= **0.21033333333333332 / 0.20733333333333334 / 0.20966666666666664**；池化 = **0.2091111111111111**（claim 0.209111）✅
9. 跨重复一致性（同 (dim,method) 集合）= **0.8748333333333335**（claim 0.874833）✅
10. 交付条目 π 均值 = **0.42045666666666665**；π<0.5 = **1263 / 1800**；符号一致性均值 = **0.7225544444444444** ✅
11. π 逐条从 500 次轨迹重算：repeat0/1/2 的 600×3 条交付条目 **1800/1800 逐位命中**（偏差 0）✅

**Q3 生成（`EXP-0076/samples.csv`、`constraints.csv`、`q3_metrics.csv`）**
12. 行级夹断：DMS **508/750**、双乙酰 **361/750**、4VG **46/750**；三者在 raw 中的超阈行数正是 508/361/46 ✅
13. 33 个校准线性列负值：design **0**、raw **0**；4VG 处于 censor 地板码的行 = **494/750** ✅
14. 约束记录：verified **19619** / conditional **8201** / not_identifiable **680** / infeasible **0**，max residual **0.0**（28500 条）✅
15. 能量 V（n_gen 加权池化，design/copula-selected）= **0.884025621542**（claim 0.884026），源参照 = **0.8137313223527718**（claim 0.8137），U = **+1.1138668332620816**；diversity = **19.735647194424246**；duplicate=0；t2n 代理上升合计 = **360**；edge-fraction 加权 = **0.1199134199132130**（=20775/173250）；198 格中 `n_real==1` = **21**（E_V 为 NaN）✅

**Q3 迁移（`EXP-0077/transfers.csv` + `solver_certificates.jsonl` + `transfer_constraints.csv`）**
16. 四策略不增率 = **1.0 / 1.0 / 1.0 / 0.41414141414141414**；source-fixed 也是 **99/99=1.0**；qp-quantile 四化学列各 **99/99**；t2n 感官代理上升 **7/99**；target-mean-projection 不可行 **58/99** ✅
17. QP 证书：**198/198 optimal**；primal ≤ **9.989717497660422e-09**、dual ≤ **3.393784142602385e-10**、constraint violation = **0.0**、KKT ≤ **5.616718630759355e-09**；nonenal 约束残差 max = **3.5561831257524545e-17**、双乙酰 = **1.8041124150158794e-16**（即 claim 引用的两个数）✅

**同一性/来源（哈希）**
18. 确认轮 vs 先导轮：metrics 文件 sha 全等（5 组），且 oof_long/predictions/inner_grid/sets/bootstrap_pi/candidate_scores/samples/constraints/q3_metrics/transfers/solver_certificates/transfer_constraints **全部逐字节相同**；EXP-0078 与 EXP-0073 同 sha。

---

## 4 cannotVerify

1. **R04 是否有独立实现型复跑**：没有。全部 `independent-rerun` 是 fixed-seed deterministic reproduction（同快照/同种子、delta=0）。我无法核验「独立实现」这一维度，因为它不存在。
2. **Q3 未跑的风格整类留出扩展**：项目内没有任何 unseen-style 输出，无法评估「Tripel/Kriek/Lambic 整类留出」的结论，只能确认它未交付。
3. **VP-0012 承诺的 holdout-metrics blocker 记录**：台账不存在该验证记录，无法核验「失败被保留」的说法，只能确认记录缺失。
4. **`modeling_*` 内部如何判定 `validated`**：实现位于 app.asar，不可读；只能从 VP 检查清单与 selectionStatus 反推（Q2 validated / Q1/Q3 provisional 的差别与 holdout-metrics 是否列入清单一致）。
5. **稳健性（ROB-0004/0005/0006）**：`outputs/q1/robustness.json`、`outputs/q3/robustness.json` 明确写 `status="preregistered-not-executed"`，无法核验任何稳健性结论——这一点执行者自己也未主张。
6. **PDF 页眉/页码等格式项**：R04 无新 PDF（`report/paper.pdf` 仍是 10-24 产物），未做页面几何实测。
7. **`.rework/R04-independent-recompute.json` 未被列为 claim ref**：它是执行侧脚本产物，不是独立评审；我未把它当作证据，只把它当作被审对象。

---

## 5 需要明确写出的「声称强于证据」

1. **不能**说「R04 已完成确认性验证」：11 项 VP 必查只执行 1 项，Q2/Q3 确认性实验零验证。确认的是「流程可重现」，不是「结论被独立复核」。
2. **不能**说「Q2 已达到 validated 级证据」：Q2 与 Q1/Q3 证据强度相同，其 validated 来自 VP 是否列 holdout-metrics，而非额外检查。若对外表述，必须写成「按当前 VP 清单记 validated，但与 Q1/Q3 同级证据」。
3. **不能**说「Q3 provisional 是因为 holdout-metrics」：VP-0014 不含该检查；Q3 的 provisional 实际是 4 项必查未执行。
4. **不能**说「EXP-0076/0077 有冻结来源」：两者无 snapshot、无 freezeSources，直接跑 live src；CLAIM-0033/0034 的 retract 理由里那句「freezeSources」不成立。
5. **不能**说「0.1199 是约束边界贴边率」：它是 edge-fraction（地板码/支撑端点/线性 0）。
6. **不能**说「R04 的论文已经同步」：paper.md 0 处引用新 claim、10 处引用已撤回 claim。

---

## 6 readiness 判定

**B = READY_FOR_DRAFT_PAPER_ONLY**

理由：三问的**数值证据**已可支撑一份草稿——4 条 active critical claim 的每个数字我都能从逐行产物复现（§3，含 18 组），确认轮的确定性同一性也被如实标注；但**最终稿**被四类硬阻塞挡住：(a) `report/paper.md` 未重写、仍引用 6 条已撤回 claim，QC-0020 failed；(b) QC-0002/QC-0033 仍 failed；(c) Q1/Q3 selection 仍 provisional 且 Q3 的必查未跑、Q2 的 validated 无确认轮验证；(d) 4 条新 critical claim 无任何独立评审。在这些解除前，只能写草稿，不能做 `deliver check`/打包为最终稿。
