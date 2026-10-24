# 被取代的协议产物（保留审计痕迹，不得再被引用）

## grade_calibration.csv / grade_calibration.json
- 来源：SCRIPT-0005（`src/06_calibration.py` 的早期版本）。
- 为什么作废：该版本在**全部 250 个样本**上拟合标定参数（`fit_scope: n=250`），
  而协议要求标定参数**只在训练集**估计；且它未按划分区分，锚定维数（14/50）与
  QWK 数值（P1-P2 0.674 / P1-P3 0.538 / P1-P4 0.320）都与两份 canonical 文件不一致。
- 由谁指出：reviewer 独立复核（REV-0001）。
- 现在唯一有效的两份：
  - `outputs/protocol/grade_calibration_SPLIT-0001.csv/.json`（SCRIPT-0010，锚定 13/50）
  - `outputs/protocol/grade_calibration_stratified.csv/.json`（SCRIPT-0010，锚定 15/50）
- 论文与台账只准引用上述两份 tagged 文件。
