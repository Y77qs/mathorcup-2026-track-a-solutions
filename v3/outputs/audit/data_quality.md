# 数据质量与尺度核对（prepare.py 实测）

- 形状：1.csv (250, 234)，4.csv (250, 53)，7.csv (250, 189)；2.csv (231, 231)，5.csv (50, 50)，6.csv (44, 50)
- 主键：跨表合并：beer（1..250）或行位置；禁用 beer_id；4.csv beer_id 不同值 96 / 250
- 目标：50 列，A/F 30，其余 20；与 4.csv 数值列顺序一致=True
- 缺失：1.csv 73 格 / 9 列；4.csv 0 格
- 尺度（对象：1.csv 的 231 个特征列）：与 Calibrated 对齐的 70 个化合物中 log10 37 列、原始浓度 33 列、无法核验 0 列；另有 5 个理化列经量程核对判为 log10（推断，非标定实测）；其余 156 列无可对齐标定，标注未核验
- 2.csv：与重算 Spearman max|Δ| = 6.661e-16，与 Pearson 符号相反占比 16.0817%，min eig = -0.042413
- 5.csv 与 Spearman(4.csv) max|Δ| = 5.551e-16；6.csv 与交叉 Spearman max|Δ| = 6.661e-16
- 3.xlsx：13 sheet（12 张评分卡 + summary），12 张卡片的评分格无数值评分（模板标签与公式仍在）=True，同一评分格被两个维度引用 2 处
- 8.xlsx：threshold 行 261，有阈值 43 行，异味标记 7 行；MDI/SHAP 仅作外部对照

## 公式误引明细

- `stale_hops`：summary 单元格 AG76 与 barnyard 共享同一评分格（summary 公式误引：两个感官维度引用同一评分格）
- `barnyard`：summary 单元格 AG76 与 stale_hops 共享同一评分格（summary 公式误引：两个感官维度引用同一评分格）