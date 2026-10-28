# 附件2 描述性化学相关网络（Q2 网络/因素解释）

规则（预先声明，v6 §5）：无向边 `{i, j}`，`i < j`（因此不可能有自环），当且仅当 `|rho_ij| >= 0.5`；保留 `rho_ij` 的符号。

- 输入：`data/raw/imported/415709ac10f2f730-2.csv`（sha256 `415709ac10f2f730d31f249bd6ac108250bdfbfd62e0055f4d8db9b41ec9cc4c`）
- 对齐：position (corrIndex) is used ONLY after it is verified by the corrLabel text on both axes；精确 corrLabel 匹配 231/231 行、231/231 列；按名加入=否

| 指标 | 实测 | 预期 | 一致 |
|---|---|---|---|
| 节点数 | 231 | 231 | 是 |
| 边数 | 645 | 645 | 是 |
| 连通分量数 | 52 | 52 | 是 |
| 最大分量规模 | 175 | 175 | 是 |

- 正边 629 条，负边 16 条（负边占 2.5%）
- |rho| 在边上：最小 0.5001，中位 0.5775，最大 0.9663
- 度：中位 4，最大 30，孤立节点 48 个
- 分量规模（降序）：[175, 3, 3, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]

## 最大分量内度最高的 10 个节点

| # | feature | corrLabel | kind | degree | moduleId |
|---|---|---|---|---|---|
| 1 | nerol.oxide | Nerol oxide | single_compound | 30 | 0 |
| 2 | alpha.calacorene | α-calacorene | single_compound | 26 | 0 |
| 3 | trans.dihydro.alpha.terpinyl.acetate | Trans-dihydro-α-terpinyl acetate | single_compound | 22 | 0 |
| 4 | isopentyl.hexanoate | Isopentyl hexanoate | single_compound | 21 | 0 |
| 5 | X1.2.dihydro.8.hydroxy..2E..linalool | 1,2-dihydro-8-hydroxy-2E-linalool | single_compound | 21 | 0 |
| 6 | pentyl.octanoate | Pentyl octanoate | single_compound | 20 | 0 |
| 7 | caryophylla.4.12..8.13..dien.5.alpha.ol | Caryophylla-4,8-dien-5-ol | single_compound | 20 | 0 |
| 8 | alpha.muurolol | α-muurolol | single_compound | 20 | 0 |
| 9 | ethanol..v.v. | Ethanol | physical_parameter | 19 | 0 |
| 10 | isobutyl.hexanoate | Isobutyl hexanoate | single_compound | 19 | 0 |

## 用途与边界

- 该网络是**描述性**的：它来自附件随附的 231×231 相关矩阵（与附件同源），用来说明 Q2 的化学模块结构与正负相关格局，不参与任何 Top-3 选择，也不是独立外部验证。
- **独立预测的训练图仍在训练折内构建**：`q2_fix.py` 的每次 bootstrap 重采样都会重新计算 `tau = 0.5` 的训练内 Spearman 图（`q1_lib.build_graph`），全样本矩阵不会进入验证，避免把全样本结构泄漏到预测评价里。
- 连通分量只是 `|rho| >= 0.5` 的阈值图结构，不代表因果关系；阈值本身是预先声明的规则，不是调参结果。
