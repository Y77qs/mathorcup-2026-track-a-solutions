# v6.3 · 论文复核与图表修订版

日期：2026-10-28。基于仓库提交`c42dae7849a52f08162545a83f52ea82b0c7e47d`中的v6.2论文，独立归档本轮已核对的修订。v6.2原目录与历史实验产物保留。

**v6.3沿用冻结主结果。** 本轮完成31组文字/引用/披露修正、7组表格调整、7张图重绘、5处代码附录标题修复；没有重新训练模型、重新bootstrap、运行生成器或迁移QP求解。20表结果数值和5段附录代码正文保持。

## 文件

| 文件 | 用途 |
|---|---|
| [论文修订版.pdf](论文修订版.pdf) | 58页修订论文；正文与参考文献止于编号29页，AI声明30页，附录31页起。 |
| [可编辑源文件.zip](可编辑源文件.zip) | 解压后的`v6.3-source/project/main.tex`为编译入口，含全部所需图、代码附录、补丁脚本与便携重绘数据。 |
| [修改说明.md](修改说明.md) | 相对v6.2已修项目、验证范围和团队待确认事项。 |
| [本次修订AI辅助记录.md](本次修订AI辅助记录.md) | 本轮Codex复核、口径纠错、措辞及图表工作的事实记录。 |
| [验证摘要.json](验证摘要.json) | 编译、页数、20表/10图编号、源文件独立重建及哈希检查。 |
| [ARCHIVE-NOTES.md](ARCHIVE-NOTES.md) | 版本来源、完整模型工程依赖和历史标识说明。 |
| [打包清单.json](打包清单.json)、[SHA256SUMS](SHA256SUMS) | 本v6.3目录的文件清单及校验。 |

## 编译与重绘

解压源文件ZIP，进入`v6.3-source/project/`，执行两遍：

```sh
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error main.tex
```

使用Times New Roman、Arial、Menlo、Songti SC及XeLaTeX宏包；换字体后应重查分页和缺字。重绘7张图可在`v6.3-source/`运行`python3 scripts/redraw_figures.py`，依赖与冻结输入说明见`scripts/README-redraw.md`及`repro-data/manifest.json`。

源文件包已在独立目录两轮编译成功，58页文本与交付PDF逐页一致。原v6.2 Markdown/插件生成器尚未同步这些补丁，直接运行旧入口会覆盖修订；后续编辑以本包`project/main.tex`为准，或先把补丁合并回原生成源。

## 版本与验证边界

本目录归档的PDF内容与已核对的v6.2修订交付完全相同，仅使用新的v6.3目录和交付名称；SHA256为`3defeac7f5eb6cc847bbf3877caec3af95ef2e9cb0ce48286515d99a7ff61d5b`。本轮修订不表示新增模型收益或全工程独立复现。

完整建模源码、原始/清洗数据及全部三问输出继续依赖仓库[v6.2/支撑材料](../v6.2/支撑材料/)。本目录提供可独立编译的论文和可独立重绘的最小证据；不把该最小重绘包称为完整模型复现包。

正式提交前，队员仍需按实际会话补齐AI工具版本、历史使用与人工核验记录，确认beer156极端观测来源/单位，并把最终论文及AI说明同步进正式总包后重建总清单。本v6.3目录的校验命令为`shasum -a 256 -c SHA256SUMS`。
