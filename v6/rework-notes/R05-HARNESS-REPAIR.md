# Harness 故障修复与续接状态

记录时间：2026-10-26（北京时间）。这是运行基础设施的修复回执，不是建模实验或科学验证结果。

- 已安装并重启加载 `dsh-vibe-math 2.8.10+runcontrol.20261026`。
- 修复了 `hardTokenLimit:null` 在请求准入阶段被错误拒绝的问题；null 仍表示没有总 token 上限，有限预算、在途预留和未知 usage 停止保护保留。
- 修复了 probe 模块版本字符串不被 preflight 识别的问题。当前新 run 已对 numpy/pandas/scipy/sklearn/matplotlib/openpyxl/sympy 的已记录探针执行模块检查并通过；这不会把旧 run 的未启用检查追溯改成通过。
- 未归属请求的 host usage、已结算的重复回执不再无故增加 revision；真实的 usage 更新仍会增加 revision。CAS 冲突必须重新读取，不猜 revision。
- `RUN-0001` 保留 stopped/budget 失败历史，未修改其内容。
- 通过公开 `modeling_project quality/run-control begin` 创建了 `RUN-0002`，软硬总预算均为 null。requestAdmission 为真实宿主记录的 `{inputUpperBound:1048576,maxOutputTokens:256000}`。
- 已在原主会话 `session-de3df4e1-3b5c-4065-b8a1-a6c10d5d500d` 的 turn 13 发出最小连通性请求，收到 `HARNESS_RECOVERY_OK`；turn/end=completed，未调用任何工具。
- 本次请求实际结算 725307 token，usage.source=host-reported、unknown=false；在途上界 0。验收时 `RUN-0002` 为 running，revision=4022。以上是验收快照，续接前必须重新 status，不使用此 revision 盲写，也不重复 begin。
- 旧 goal 仍为 blocked，完整保留。继续原任务时按宿主公开的目标续接/编辑流程处理，不能对已存在的 blocked goal 再调用 create_goal；此次未把旧目标标记 complete，也未触发自动建模轮次。
- 已有 runtime/questions/数据/模型/EXP/VP/VAL/claim/图/论文/frozen/forkOrigin/configLifecycle 及原质量集合经过修复前后深比较一致。旧的科学与交付 blocker 保留。
- 此次没有运行确认性建模实验；后续仍需按用户原授权，先更新 questions/workbench、先登记新 VP，再运行新的确认性 EXP。不得把这次连通性测试当作建模验证。

完整修复包、源代码补丁、安装回执、回滚备份与测试材料：
`/Users/baozhashizitou/Documents/MATHORCUP/outputs/harness-repair-20261026/`
