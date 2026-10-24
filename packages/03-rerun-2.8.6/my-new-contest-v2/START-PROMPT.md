这是一个已经初始化、配置已冻结的干净项目。不要运行 modeling_project init，不要改写 contest.yaml。按顺序完成 Q1/Q2/Q3，最终交付 md/tex/pdf 三种论文。

【项目与环境】
projectDir=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v2
项目已初始化；初始 configSha256 必须是 466a882bcee6a3dc4cd956131d1aa82db168e284bf2296bd2fb5f2fd42b0e399。
先运行 modeling_project {action:"status"} 和 {action:"probe"}：
- 若 status.configChanged=true，或 status.configSha256 不等于上述值：立即停止，报告“配置已变化”，不要改 config、不要跑实验。
- 若 probe 失败：先修 Python 绑定/环境，不要继续实验。
Python：/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python

【唯一题面来源】
只读 Markdown 题面，不读 PDF：
problem/2026年MathorCup大数据挑战赛-赛道A初赛.md
原始 PDF 只作为来源存档，不读取、不引用、不作为 source.path：
problem/2026年MathorCup大数据挑战赛-赛道A初赛.pdf

【数据契约】
- problem/targetcolumns.csv 是已确认的 50 个 Q1 目标列映射（含 4.csv/3.xlsx/5.csv/8.xlsx 的对应关系）；
  先用它核对 4.csv/3.xlsx summary，确认 50/50 后再建目标契约。
- 附件在 data/raw/：
  1.csv 250×234 化合物/理化 + tasting_category_fine；有缺失；
  2.csv 231×232 是实测 Spearman 相关矩阵（不是 Pearson）；非 PSD（min eig≈−0.0424）；
  3.xlsx 13 sheet（beer_1…beer_12 + summary）；12 张评分卡均为空白模板；
  4.csv 250×53，含 50 个感官数值列，是标准化/中心化值，不是原始 0–6；
  5.csv 50×50、6.csv 实际 44×51，均是派生 Spearman 相关矩阵；
  7.csv 250×189，与 4.csv 同批 250 样本，不是论坛评论；
  8.xlsx 7 sheet（6 有效+空 Sheet2）：thresholds 261 行仅 43 行有阈值/7 个异味标记；
    names 50 Trained+51 Ratebeer；Calibrated 是 250×73（3 元数据+70 化合物原始浓度）；
    MDI/SHAP 是同批 250 样本拟合产物，禁止当输入特征；Prices 大量 NA；
  数据说明.txt 只作说明，不替代题面。

【必须遵守的数据事实】
1. Q1 targetColumns = 50 列，以 problem/targetcolumns.csv 为准；
   不是“约40”，不是只取 A_*+F_* 的30列，不能自造列名。
2. Q1 原始 0–6 不可精确还原；3.xlsx 评分卡为空、summary 结果全0、4.csv 标准化参数未知，
   clove max=6.17>6；Q1 只能交付 mapped grade，不能称原始 0–6。
   推荐映射 x=6*(z-zmin)/(zmax-zmin)；映射参数只能用训练数据估计，不能用测试目标拟合；
   论文/契约写明“mapped grade, non-original 0–6”，并保留越界/端点处理说明。
3. 2.csv 是 Spearman；与1.csv重算 max|Δ|≈7.8e−16；与Pearson有16.94%符号相反；
   若做矩阵运算/图，先说明非PSD，必要时做PSD投影；不能当独立外部先验。
4. 5/6/7 不是独立外部数据；不能当外部验证；Q2 只用它们作派生/描述证据。
5. 1.csv 混合尺度：70个可对齐列中约35列log10、33列原始浓度、2列CS2/X4VG零值底限编码；
   pH/color/bitterness/ethanol/CO2也是log10；必须逐列核对，禁止统一取log或统一当原始浓度。
6. 跨表合并只用 beer 或行位置，不用 beer_id（4.csv/7.csv 的 beer_id 截断，250行仅96个不同值）。
7. 3.xlsx summary 已知公式误引（如 barnyard 误引 stale_hops）；不要修改原始文件，差异写入数据质量报告；
   以 4.csv 为权威标签。
8. 8.xlsx 的 MDI/SHAP 不能作输入特征；Prices 不作核心输入；Calibrated 只用于核对尺度。
9. Q2/Q3 不做因果/未来预测表述；Q3 生成是“约束满足/生成合理性”，不是真实酿造验证。

【第一步：数据导入与版本】
1. modeling_data {action:"import"} 显式导入附件，files 用绝对路径并写 role：
   1.csv=chemical_features；2.csv=compound_correlation；3.xlsx=sensory_scorecards；
   4.csv=sensory_targets；5.csv=sensory_correlation；6.csv=chemical_sensory_correlation；
   7.csv=sensory_descriptors；8.xlsx=reference_thresholds；数据说明.txt=data_notes。
   不依赖自动猜字段；不要 import PDF。
2. profile 1.csv/4.csv/3.xlsx/8.xlsx；写 src/prepare.py 做清洗、连接、尺度逐列核对、
   缺失处理、mapped-grade 探索；run-script 实际执行。
3. 建立三个独立数据版本，不混用：
   - DATA-Q1mapped：4.csv 的 50 个目标列，按显式映射生成 mapped grade；
     保留 50 个原始列名，fields 注明 transformed/mapped；targetColumns=50 个真实目标列。
   - DATA-Q2raw：4.csv 的 50 个原始标准化列，仅用于 Q2 相关/贡献分析。
   - DATA-Q3：1.csv 的 tasting_category_fine + 化合物域 + 8.xlsx 阈值；用于 Q3。
4. register-clean 必须提供 sourceFile/cleanedFile/cleaningScript/targetColumn/完整 fields 或 fieldsFile；
   字段清单来自 profile，不能只登记目标列；禁止覆盖原始 4.csv/1.csv。
5. register-split：
   DATA-Q1mapped 和 DATA-Q2raw 各用 random-holdout，testFraction=0.2，seed=20261024；
   按 beer 一行，避免同一啤酒跨折；若输出0..n-1行号，显式 rowIdMapping:"positional"。
   Q3 跨风格迁移显式构造 style holdout（Tripel/Kriek/Lambic 等），不能用随机split冒充。

【第二步：先契约，后实验（顺序不能反）】
6. modeling_project {action:"plan"}：
   Q1 metric="mae"；needsData=true；needsBaseline=true；targetColumns=50（mapped）；
      outputs=50维 mapped grade、误差/分层误差、图；
      evaluation=多输出 mapped-grade MAE；limitations写“原始0–6不可识别，mapped grade非原始评分”。
   Q2 metric="topk-jaccard"；needsData=true；needsBaseline=false；
      outputs=每感官维度Top-3、bootstrap频率、方法间Jaccard、稳定性报告；
      limitations写“同期关联、非因果、相关矩阵为派生Spearman”。
   Q3 metric="constraint-satisfaction"；needsData=true；needsBaseline=false；
      targetNature=conditional_generation；outputs=风格生成谱/感官画像/跨风格迁移/缺陷不恶化检查；
      limitations写“生成合理性/约束满足，不是真实酿造验证”。
7. requirement-add：source.path 一律
   problem/2026年MathorCup大数据挑战赛-赛道A初赛.md；
   source.quote 必须从该 Markdown 逐字复制题面原句；Q1/Q2/Q3 分别登记原子要求。
8. target/model contract：
   Q1：taskNature=association_analysis；labelSource=“4.csv标准化结果 + mapped-grade映射”；
       labelOrigin=transformed；inputsAvailableAt=“化合物/理化检测时”；
       dataset={datasetId:DATA-Q1mapped, targetColumns:50个mapped目标列, targetColumn:第一列}；
       写明“不是原始0–6；映射公式/端点/越界处理见数据说明”。
   Q2：taskNature=association_analysis；labelSource=4.csv标准化感官结果；labelOrigin=transformed；
       dataset={datasetId:DATA-Q2raw, targetColumns:50个原始标准化列, targetColumn:第一列}。
   Q3：用 contract:"model" 登记 conditional_generation 目标/风格条件/化合物域/缺陷阈值约束；
       不要把 style 或生成结果伪装成普通预测标签。
   model contract 创建时就要完整填 formula、variables、constraints、boundaryCases；不要等报错再补。
9. workbench：
   Q1 profile=prediction，decisionTime=“化合物检测完成、感官评分未知时”，metricDirection=minimize，
      features=1.csv实际化学/理化字段，excludedFeatures=4.csv全部50个感官目标列；
      evidence按 data-audit/model-comparison/error-analysis/robustness/paper。
   Q2 profile=factor-analysis，decisionTime=“分析时使用1.csv与4.csv汇总；不声称因果”；
      evidence按 data-audit/factor-analysis/robustness/recommendations/paper。
   Q3 profile=open-question，decisionTime=“生成时已知风格与缺陷阈值”；
      evidence按 question-definition/method/results/robustness/recommendations/paper。
   先describe再configure，反复status；文件未生成只报缺口，不伪造。

【第三步：holdout 预算与验证计划（先于任何候选实验）】
10. 严格 holdout 预算：maxHoldoutReuse=3，不得修改配置/提高上限。
    Q1：baseline + 最多2个候选 = 最多3次 holdout；选模用 train-only OOF/CV；
        holdout只做最终比较；不要反复跑。
    Q1 若需要 independent-rerun：优先 train-only 隔离口径（evaluationUse:"train-only"、
        freezeSources:true、dependenciesComplete:true），不额外消耗 holdout；
        如果 pack 要求 sourceSnapshot，先确认实验已保存 snapshot，再登记验证；不得事后修改台账。
    Q2/Q3 各自独立数据/划分，别把 Q1 holdout 再用到 Q2/Q3。
11. 在跑候选前：
    modeling_validate {action:"plan"} 登记 holdout-metrics / leakage / split-integrity /
    baseline-compare / independent-rerun 协议；
    明确第一候选比较方案；先跑 baseline，再跑候选；
    不能先跑候选再补验证协议。
12. Q1 先 register+run 真实多输出基线，params 必须带：
      features:[...]
      family:"constant-per-target"
      evaluation:{kind:"multi-output", targetContractId:实际Q1 TGT id,
        metric:"mae", metricKey:"mae", predictionsFile:"predictions.csv",
        idColumn:"row", aggregation:"uniform-average"}
    predictions.csv 含 y_pred__<每个目标列>，与50列一一对应；
    基线通过后最多再跑2个候选，不要额外 holdout。
13. Q2 先跑简单基线（全局统一Top-3）再跑逐维方法；
    用bootstrap重采样统计Top-3入选频率；
    至少两种方法/排序算Jaccard；
    如用实验，evaluation:{kind:"set-stability", metricKey:"topk-jaccard",
      topK:3, setsFile:"sets.json", dimensions:[...], methods:[...]}；
    2.csv只作相关结构参考，5/6/7不作独立验证。
14. Q3 先跑无条件/全局基线，再做风格条件生成/迁移；
    用8.xlsx thresholds对DMS/Diacetyl/4VG/trans-2-nonenal/Stale hops等做OAV/阈值检查；
    可用 energy-distance/constraint-satisfaction/profile-consistency；
    没有外部金标准就写“生成合理性/约束满足”，不声称真实酿造验证；
    禁止MDI/SHAP作输入特征。

【第四步：robustness 预注册（必须早于扰动实验）】
15. Q1/Q2/Q3 各自在跑扰动/重复划分前先：
    quality {subaction:"robustness-plan-add"} 登记 methods、perturbations、seeds、metricKey、decisionRule；
    再运行预注册之后的实验，再 robustness-plan-execute 链接实验；
    不得用“同 seed 复跑”冒充稳健性；不得事后补计划。
    若当前 holdout 预算已用完，使用新的预注册 split/seed，不要提高 maxHoldoutReuse。

【第五步：claims 与指标命名】
16. 等最终模型/验证完成后再创建 claim。
    claim 的 refs 只引用实验 evaluation.metricKey：
      Q1 -> "mae"
      Q2 -> "topk-jaccard"
      Q3 -> "constraint-satisfaction"
    不要再把 holdout_mae_mean、oof_mae_mean、defect_nonworsen_rate_raw 等子指标放进 claim refs；
    子指标只能出现在论文表格/图中，或显式声明为 alias（当前 pack 不支持 alias）。
17. 每个 claim 写 appliesTo、limitations、targetContractId；
    Q1写 mapped grade；Q2写同期关联非因果；Q3写生成非实验验证。
18. requirement-map 把6条要求映射到 claim/analysis/experiment；
    然后独立上下文 review-add：
      targetContract（target-lineage）
      requirements-coverage（要求覆盖）
    不能只审 target contract 就认为 coverage 通过。

【第六步：质量检查与三格式论文】
19. 反复运行：
    quality-plan auto → quality-run → quality-report
    只补 blocker，不关质量门；不允许改台账/放宽maxHoldoutReuse/伪造robustness。
20. 写 report/paper.md，必须包含：
    摘要、问题分析、数据质量与尺度核对（混合尺度/主键/同源矩阵/3.xlsx空白/8.xlsx限制）、
    Q1 50维 mapped grade 与限制、Q2 Top-3稳定性与非PSD说明、
    Q3生成/缺陷约束与限制、结论与建议、复现说明；
    数字用 {{metric:EXP:...}} 结构化引用，不手抄；图必须登记/引用。
21. 三格式：
    contest.yaml 已设置 delivery.paperFormats: [md, tex, pdf]；不要再改配置。
    先 modeling_deliver render 生成 report/rendered.md；
    用 report/rendered.md 生成 report/paper.tex（pandoc/ctex），再 xelatex 两遍生成 report/paper.pdf；
    必须验证 pdf 非空、页数>0、图能打开；缺 TeX 或编译失败就保留 DRAFT，不伪造。
22. 最后：
    modeling_project freeze（需要时）；
    modeling_deliver check：formats.declared/produced 必须都有 md/tex/pdf；
    final/qualityPassed/checkpointsPassed 按真实结果报告；
    未通过只能 draft:true 出 -DRAFT 包，不能强行 final。

【停止条件（立即报告，不要继续跑）】
- status.configChanged=true 或 configSha256 不是 466a882b…；
- targetcolumns 不是50/50对应，或目标契约 targetColumns 不是50个真实列；
- Q1 需要超过3次 holdout 才能选模；
- robustness 尚未预注册就要跑扰动/重复划分；
- claim refs 与 evaluation.metricKey 不一致；
- model contract 缺 formula/boundaryCases；
- quality 仍失败时不要为了 final 改数据/改配置/删记录。
