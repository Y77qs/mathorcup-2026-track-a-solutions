# RUN-0002 再次中断：原因、修复与现场验收

## 本次直接原因

2026-10-26 20:48:13（北京时间），RUN-0002 因 no-progress 自动停止。三次 questions plan 失败分别为 expected/current = 4025/4032、4033/4036、4045/4042。最后一次还出现了猜测未来 revision 的调用行为。随后 agent/request 拒绝下一次请求，界面显示通用的 controlled run stopped。

这次预算状态 within-budget，所有请求均已结算，原生已知用量 3083084 token。无上限预算修复已正常工作；直接原因是连续 CAS 冲突触发无进展保护。

## 上次修复遗漏

上次仅避免无归属/重复宿主事件写入，仍让真实请求预留、用量结算、自动工具观测推进业务 revision。模型读到状态后，下一次模型请求的记账会使读到的 expectedRevision 过期。单条纯文本连通性核验没有覆盖这个多步写入场景。

## 第二版修复

- 自动请求预留、usage 结算和自动工具观测改为更新 runtimeRevision/runtimeUpdatedAt，并保留审计事件。
- 业务 revision 继续严格执行 CAS；真实业务修改后，旧 expectedRevision 仍被拒绝，不猜测、不自动合并。
- runtime-only 路径在原子写入前核对非运行控制对象；试图借此修改 questions/实验/其他科学与质量对象会具名拒绝，不落盘。
- 监控同时观察业务与运行序号，运行停止和用量更新仍能显示。
- 无进展保护、有限预算和缺失 usage 保护未放宽。

## 已安装与恢复

版本 2.8.10+runcontrol.20261026.2，依赖指向本目录的独立 tgz，已完整退出并重开 Harness。通过公开 begin 建立 RUN-0003；RUN-0001/0002 原样保留。

## 验证

- 准入回归 46 passed / 0 failed。
- 无进展/用量/恢复回归 26 passed / 0 failed。
- 最终原生环境建模套件 24 passed / 0 failed。
- 大范围 VMU 382 passed / 46 failed；失败文件集合与上次相同，没有新增失败套件。大范围门禁未全绿。
- 派生同步 16/16。
- 现场主会话 turn 15：status 返回业务 revision=4045；经历真实模型请求与记账后，step 仍用 expectedRevision=4045 成功，业务 revision 变为 4046；resume 确认 RUN-0003 running；最终 CAS_RECOVERY_OK，turn/end=completed。
- 这条诊断 step significant=false，不代表科学进展，不填自报 token 用量。
- 最终 runtimeRevision=10，真实原生用量 962542 token，未结算上界 0。
- 修复前后深比较：既有科学/质量对象、历史 runs 和上轮已修改的 questions.yaml 均未变。

## 待续接事项

上次失败回合已经修改 problem/questions.yaml，但三次公开 plan 均失败，故 ledger.questions 仍是旧协议。此次未代为提交、未回滚文件，也未运行建模实验。后续需重新读取真实 status 和文件差异，再按用户原授权公开 plan；不得将文件已修改误报成计划已登记。

R05 中“真实 usage 仍推进业务 revision”的说明已由本次 R06 修复取代。历史 revision 不重编号，旧 goal 不伪标完成。

完整证据目录：`/Users/baozhashizitou/Documents/MATHORCUP/outputs/harness-repair-20261026-cas`。
