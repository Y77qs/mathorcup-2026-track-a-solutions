# v5.1 · v5 论文修订版（21 页 / 8 图）

**这是 v5（`beer-2026-a-v3`，18 页 final）论文的修订版**：2026-10-25 09:15 完成，按《论文修改建议》
重写摘要与正文、重绘图表、补充 Top-3 全表与迁移逐样本核验。**结果沿用 v5 台账，未新跑实验、未改台账**；
修订前后原件 SHA-256 对照见 `support/original_sha256.json` 与 `support/verification.json`。

- 论文题目：《基于稳健表示、共表达网络与风格条件生成的啤酒化合物—感官强度建模》
- 页数/图数：**21 页 / 8 图**；正文表 1–11，附录 A 完整 50 维 Top-3（150 条目）
- 修订日期：2026-10-25 09:15（源目录 `work/my-new-contest-v3/report/revised-20261025`）
- 体量：62 文件 / 约 12 MB
- 状态：**论文修订稿**（可用于提交/阅读；不等同于新一次台账交付，v5 的 `final=true` 仍以 v5 台账为准）

---

## 1. 主要修订（依《修改建议》逐项落实）

| 修改事项 | 处理 |
|---|---|
| 摘要去工程台账、精简精度、补化合物名称 | 重写摘要，保留量化结论并补入香茅醇、香叶醇、乙酸异戊酯、乙酸 |
| Beer#1–Beer#10 的 0–6 评分 | 第 4.4 节表 1–2（10 个核心维度，标注训练/留出）；完整 250×50 评分随附 CSV |
| 低秩/图正则叙述 | 第 4.3、4.6 节突出共享结构、去噪与非线性互补，保留“单组件证据有限”的结论 |
| 正文核心 Top-3 大表 | 第 5.5 节表 4（20 维，每候选含名称、π、S、方向、混杂类型） |
| 完整 50 维 Top-3 | 附录 A 共 150 条，另附无舍入损失 CSV |
| 化学合理性论证 | 第 5.6 节按酯类、萜烯、高级醇/有机酸、硫化物/双乙酰讨论并补原始研究引用 |
| 实际网络节点连接图 | 第 5.2 节图 4（τ=0.6，最大连通分量，6 个 Hub 与全图统计） |
| 三风格生成画像 | 第 6.4 节图 7 与表 6（Tripel/Kriek/Lambic 折外生成代理 vs 真实感官均值） |
| 迁移前后浓度与缺陷 | 第 6.5 节表 7–9（源谱、分位数初始化、优化谱、目标均值、逐样本缺陷核验） |
| 第 7 节去报错日志 | 改写为稳健性与灵敏度分析（表 10 汇总三问扰动结果） |
| 消融去重复 | 第 8 节表 11 一次汇总九项消融 |
| 附录台账复述 | 改为完整 Top-3、数据字典与复核要点 |
| 重复编号 / 内部代号 / 路径 | LaTeX 自动编号 + 附录 A/B；清理实验、验证、模型契约编号与工程路径 |
| 精度与图表汉化 | 结果 4 位小数、权重 3 位；图坐标、图例、图注中文，化学/风格名保留标准名 |

**核查后纠正的实质表述**（详见 `修改说明.md`）：评分工作簿实为 12 张空白卡 + 汇总页；排序的 S 是原样本点估计（π 优先、S 裁决并列）；
219 项候选含蛋白质/铁等非单体指标，保留真实排序而未替换；Q3 感官代理是 Ridge 而非 Q1 最终融合模型；
图拉普拉斯理论上半正定（特征值截断仅为浮点稳定化）；1.4813 是可行化初始化、7.1899 是相对初始化的 L1 改动；
stale hops 代理容差 0.05 倍标签标准差，不能笼统称“五项严格不增”；稳健性扰动未含 stale hops；13.48% 是固定留出上的误差改善、无额外显著性检验。

## 2. 目录

```text
paper/
├── paper_revised.pdf        21 页，1,062,111 B（XeLaTeX 编译；页面/长表/图位/越界均已核对）
├── paper_revised.md         正文 Markdown（含 LaTeX 数学）
├── paper_revised.tex        LaTeX 源码（77 KB）
└── 修改说明.md              本修订的逐项说明与复建方式
figures/                     8 张重绘图（q1_* / q2_* / q3_*）
data/                        8 份支撑表：250×50 评分、Beer#1–10 核心评分、150 条 Top-3、
                             231 项数据字典、网络节点、310 行生成谱、风格画像、迁移对照
support/
├── prepare_revision.py      从 v5 结果重算/生成表格与图
├── build_revision.py        Markdown → TeX → PDF 构建
├── verify_revision.py       复核（原件保全、页数、图数、表行数、复算一致性）
├── manuscript.template.md   论文模板（后续改正文用）
├── header.tex / compile.log / render.log
├── tables.json / reporting_checks.json / verification.json / verification_summary.txt
├── delivery_manifest.json   全部交付文件的 sha256
├── original_sha256.json     原件（v5 report/*）修订前哈希
└── pages/                   21 张逐页核对图（checked-01…21）+ 6 张 QA 图
论文修订版_含图表与支撑数据.zip   原始交接包（2.34 MB，内容与上述一致）
```

## 3. 与 v5 的区别

| | v5 | v5.1 |
|---|---|---|
| 时间 | 2026-10-24 19:20–22:40 | 2026-10-25 09:15 |
| 论文 | 18 页 / 14 图（台账渲染稿） | **21 页 / 8 图（重写修订稿）** |
| 内容 | 台账占位符渲染，含工程编号与路径 | 去工程化叙述，补 Top-3 全表、化学论证、迁移核验、稳健性汇总 |
| 状态 | `final=true`（台账交付） | **论文级修订**（不改 v5 台账） |

## 4. 复现与复核

```bash
cd /Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3/report/revised-20261025
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
$PY support/prepare_revision.py     # 从 v5 已存结果重算表格与图
$PY support/build_revision.py       # 构建 md/tex/pdf
latexmk -norc -xelatex -interaction=nonstopmode -halt-on-error paper_revised.tex
$PY support/verify_revision.py      # 复核并写 verification.json
```

> 脚本依赖原项目中的已存结果与模型工具模块，需保持目录相对原项目位置；不要运行 v5 的 `src/build_paper.py` 来构建本副本。
> 逐条复核结论：原件全部保全、PDF 21 页、8 图、250×50 评分、50 维 150 条 Top-3、迁移距离复现为 0.4328202679486976、
> 无内部编号/占位符、无缺字与 Overfull 文字越界。
