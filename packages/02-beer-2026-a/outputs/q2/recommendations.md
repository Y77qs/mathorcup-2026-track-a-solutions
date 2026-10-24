# Q2 建议（全部绑定真实指标）

- 交付形式应为“每个维度的候选簇（A/B/C 三法）+ bootstrap 入选频率”，而不是单一 Top-3：A–B Jaccard 仅 0.228，bootstrap 平均入选频率 0.478。
- 推荐把 Spearman 排序（A）作为主排序、网络平滑（C）作为稳健性复核：二者 Jaccard 0.614。
- 对稳定性低的维度（见 factor_analysis.json 的 leastStable），应补样本或改用分层/分风格分析。
- 任何因果表述都不允许；2.csv 非 PSD，矩阵运算前必须投影并披露。