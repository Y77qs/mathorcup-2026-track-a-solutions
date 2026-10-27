# v6.1 显式恢复交接（2026-10-27）

此文件是本次恢复的当前交接。较早交接关于 RUN-0003 running、旧 CLAIM/ROB 及旧输出路径的描述只作历史；以实时台账为准。

用户已明确授权：补充显式恢复机制，完整保留 RUN-0003、失败请求、unknown 和 1,304,576 token 未结算上界；先回收已完成实验，再续做缺口；不重复训练、不清空历史、不降低科学质量门。

## 已完成的运行控制修复

- 已安装 `dsh-vibe-math@2.8.10+recovery.20261027`。新增公开 `modeling_project quality/run-control control:recover`，必须提供实时 expectedRevision、fromRunId、完整 requestKeys、精确 unsettledUpperBound、授权 reason 和真实 requestAdmission。
- 已通过该公开接口建立 `RUN-0004`，关联 `RUN-0001/0002/0003`；RUN-0003 仍 stopped/unknown-usage，不改写为运行成功。
- 原请求 `ab5ac473-ca97-4385-8a48-22c3023c4fc7:1:67` 仍 `settled:false,usageUnknown:true,reserved:1304576`。其未知用量没有记为 0，后续预算动态继承该上界及历史已知用量。
- soft/hard 均 null；requestAdmission 沿用真实已验证宿主上界（inputUpperBound=1048576，maxOutputTokens=256000）。这些是单请求技术上界。
- 新 run 开始时自身 usage=unobserved，不等于历史用量为 0。`runcontrol-budget` 对继承的未知仍 needs_review；没有取消质量检查。
- 普通 begin 不能洗掉未结算历史；新请求必须用新身份。新的缺失 native usage 仍保护停止，不能自动 recover、伪造结算或反复重试。真正的晚到 native usage 只会结算原所有者一次。
- 此次是 `DeepSeek Messages stream idle timeout` 后的显式恢复；尚无证据能把超时归因到具体服务器或网络环节。不要声称传输超时已经根治。

## 已回收，禁止重复训练

通过公开 `modeling_experiment action:status` 已将以下磁盘结果回收到台账，全部 exitCode=0、succeeded：

| 计划 | 参考 | 扰动 | 主指标 |
| --- | --- | --- | --- |
| ROB-0015 Q2 | EXP-0125 | EXP-0126 | topk-jaccard |
| ROB-0016 Q3生成 | EXP-0127 | EXP-0128 | energy-distance |
| ROB-0017 Q3迁移 | EXP-0129 | EXP-0130 | nonincrease-rate |

此次回收前后 EXP 计数均为 130。未调用 register/run/retry/independent-rerun，也未启动训练。旧 queued/failed 和 ROB-0012..0014 均保留。不能因聊天中失败就重新训练这些实验。

回收证据：`.rework/recovery-20261027/collected-experiments.json`。完整恢复证明与恢复前台账快照位于同目录的 recovery-proof.json、recovery-receipt.json、ledger-before.json。已校验恢复时所有旧 RUN、失败会话文件及 v3 台账未改变。

## 下一个动作与边界

1. 先 status/config status 和读取本文件，确认 activeRunId=RUN-0004；不要再次 begin/stop/recover，不重放首条全流程提示词。
2. 读取本会话原有分工与实际产物，再核对 ROB-0015/0016/0017 计划要求、实验时序、真实 seed 回执和输出。只有满足原始计划才能执行 robustness-plan-execute，不减少 repeats、种子或放宽阈值。不满足则具名报告，不能重新训练已成功实验来应付接口。
3. 继续原本尚未完成的结论/coverage、下游 paper_tables.py/evidence_manifest.json/INDEX-confirmatory.json 与 confirmatory_v2 图件工作。中断前 CLAIM-0063/0064/0065 仅是预期编号，截至恢复时实际 claim 最大 0062；必须先取得真实回执，禁止预填 ID 或 passed。
4. 负责下游表格的子代理 ab5ac473-ca97-4385-8a48-22c3023c4fc7 在部分 write 参数流中超时；失败请求没有完成的 write 工具回执。先核对磁盘已有内容和子代理任务状态，分小块 patch，不把该半截流当已执行修改。图脚本子代理 d83ee0f9-a080-4ee8-97eb-9af8a84ea521 同样应先核对实际产物。
5. 主控串行处理 modeling_* 写调用；子代理只处理约定文件与真实独立审查，不并行改台账。继续原会话授权的剩余工作；不重新训练已有成功实验，也不把旧结果包装成新结果。
6. 保持所有科学质量门、holdout 曝光、冻结依赖、独立审查要求和历史失败。未知用量的治理限制如实保留，不能声称 qualityPassed/FINAL 或用删检查处理。若只能 DRAFT，按原始指令输出真实 DRAFT。
7. 新业务内容只写 P=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v6；v3 只读。

恢复专项测试 56/56；建模原生套件 24/24；全 VMU 382 通过/46 失败，失败集合与修复前基线完全相同，无新增失败。文档 lint 保留原有缺页失败，不声称全仓通过。

## 恢复后的实际进展（20:27:55 本地验收快照）

新请求已走真实宿主并收到 native usage：RUN-0004 有 6 次新请求已结算，source=host-reported，run 仍 running，无新保护停止。旧 RUN 逐对象比较仍未改变，旧 1,304,576 上界仍未结算；EXP 总数仍 130。ROB-0015/0016/0017 已有实际 execute 回执，计划状态仍 pending；execute 的 decisionRule.passed 不能单独等于计划完整覆盖或独立审查通过。

特别需要核对：以上三个计划登记 repeats=3、seeds=20261025/20261026/20261027、perturbations 含 repeat=1 与 repeat=2，但当前每个仅链接 2 个 EXP（参考 repeat=0 与扰动 repeat=1）。必须解释第三种子/第二扰动的覆盖，优先复用已存在、符合预登记时序与冻结来源的真实证据；不能减少计划要求，也不能把二项统计判定写成三种子验收通过。
