# 测试：啤酒风味建模

中文段落，含公式 $\mathrm{MAE}_t=\frac1n\sum_i|y_{it}-\hat y_{it}|$ 与独立公式：

$$
\min_{B,b}\frac1n\|Y-ZB-\mathbf 1b^\top\|_F^2+\lambda\|B\|_F^2+\gamma\operatorname{tr}(B^\top L_GB).
$$

| 项 | 值 |
|---|---|
| 样本 | 250 |
| 维度 | 50 |
