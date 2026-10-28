# Q2 v6.2 交付表重建与同模块替代候选去重报告

本报告由 `src/q2_v62_regen.py` 从 `experiments/EXP-0107/repeat{0,1,2}/` 已保存产物确定性生成：不重跑 500 次 bootstrap、不重训练任何模型，仅重新组装交付表并修复替代候选规则。

## 1. 缺陷与修复

- 缺陷：`module_alternatives()` 直接取同模块点估计排序第 4 名，未剔除刚交付的 Top-3，导致替代候选重复已交付化合物；`module_alternative_report()` 的 `moduleRank4To10` 池同样未剔除。
- 修复：先剔除该 (方法, 维度) 已交付 Top-3，再取第一个同模块候选；无候选时写 `none`。`sameModuleAlternativeExists` 改为“是否存在未交付的同模块候选”。
- 修复源码：`src/q2_fix.py::module_alternatives()` / `module_alternative_report()`。

## 2. 修复前后重叠计数（alternative_rank4 是否落在对应 Top-3 中）

| 重复 | consensus 150 行（修复前/后） | 其中 rank 3（修复前） | by-method 600 行对自身方法 Top-3（前/后） | by-method 对 consensus Top-3（修复前） | extended 150 行（前/后） | extended by-method（前/后） |
|---|---|---|---|---|---|---|
| 0 | 34 / 0 | 11 | 86 / 0 | 95 | 2 / 0 | 12 / 0 |
| 1 | 38 / 0 | 12 | 89 / 0 | 98 | 2 / 0 | 12 / 0 |
| 2 | 30 / 0 | 10 | 84 / 0 | 96 | 2 / 0 | 12 / 0 |

替换（alternative_rank4 取值发生变化的单元格）计数：重复 0：strictConsensus150 78 个，strictByMethod600 269 个，extendedConsensus150 91 个，extendedByMethod600 354 个，lowPiRows 54 个；重复 1：strictConsensus150 78 个，strictByMethod600 280 个，extendedConsensus150 94 个，extendedByMethod600 352 个，lowPiRows 51 个；重复 2：strictConsensus150 78 个，strictByMethod600 272 个，extendedConsensus150 94 个，extendedByMethod600 351 个，lowPiRows 51 个。每个替换项均校验为“同模块内未交付候选”或 `none`，无非法替换。

## 3. 三个分母（sign_stability 均值）

| 分母 | 行数 | sign_stability 均值 |
|---|---|---|
| repeat 0 交付 consensus 150 行 | 150 | 0.9994666666666667 |
| 单次重复 4 方法 600 行 | 600 | 0.98198 |
| 三次重复合并 1800 行 | 1800 | 0.9816877777777778 |

断言通过：0.9994667 / 0.9819800 / 0.9816878（7 位小数）。repeat 0 的 150 行均值 0.9994666666666667，600 行均值 0.98198，合并 1800 行均值 0.9816877777777778。

## 4. 回归校验（除三个允许变化的列外逐格比对原 EXP-0107 文件）

| 重复 | 文件 | 行数 | 结果 | 失败单元格 |
|---|---|---|---|---|
| 0 | strict_top3.csv | 150 | 通过 | 0 |
| 0 | strict_top3_by_method.csv | 600 | 通过 | 0 |
| 0 | extended_top3.csv | 150 | 通过 | 0 |
| 0 | extended_top3_by_method.csv | 600 | 通过 | 0 |
| 0 | strict_lowpi_sign_status.csv | 95 | 通过 | 0 |
| 1 | strict_top3.csv | 150 | 通过 | 0 |
| 1 | strict_top3_by_method.csv | 600 | 通过 | 0 |
| 1 | extended_top3.csv | 150 | 通过 | 0 |
| 1 | extended_top3_by_method.csv | 600 | 通过 | 0 |
| 1 | strict_lowpi_sign_status.csv | 93 | 通过 | 0 |
| 2 | strict_top3.csv | 150 | 通过 | 0 |
| 2 | strict_top3_by_method.csv | 600 | 通过 | 0 |
| 2 | extended_top3.csv | 150 | 通过 | 0 |
| 2 | extended_top3_by_method.csv | 600 | 通过 | 0 |
| 2 | strict_lowpi_sign_status.csv | 95 | 通过 | 0 |

总结果：全部通过（浮点容差 1e-12；允许变化列：alternative_rank4 / module_rank4_to_10 / same_module_alternative_exists）。

## 5. 文件清单

| 文件 | 字节数 | sha256 |
|---|---|---|
| repeat0/extended_top3.csv | 25201 | `f121d84a1c2671c4ec258681195078e73c7ad8938df4fcf4f11d76971153aa74` |
| repeat0/extended_top3_by_method.csv | 107957 | `cc976cc1144b3cb17257925cafda34ae00bd72d5eecb460d9c8bd3edc967089f` |
| repeat0/sign_stability_summary.json | 36131 | `48de586225b2866aeb64336704198c4c668b8c8a23639e8e752973e59735b656` |
| repeat0/strict_lowpi_sign_status.csv | 30345 | `7038be697fcd88924235f8d0e31d223ee96dc8131dd245ddfa60ecf36fd7e78a` |
| repeat0/strict_top3.csv | 27350 | `a7f558de45c3e17d53c69264abd720a0ea0aa8077642aa9f31700fce427671be` |
| repeat0/strict_top3_by_method.csv | 117173 | `1c1098c34c895ee16435cfaa3cdded8d05d2d173b97716fad262f04374e410c8` |
| repeat1/extended_top3.csv | 25116 | `a4a03fdf80e780872bf120705733a6060edfb4020b53e30ee02a137675444cf9` |
| repeat1/extended_top3_by_method.csv | 107680 | `e9cfefd1512f24ebe0892b6f10ec9de406f38b165d268994e6abf2ae0bff0f47` |
| repeat1/sign_stability_summary.json | 36226 | `e5ddcedf210f7a97083c2a742c67d56ca5178765897a67b3387c4fbb4180bf18` |
| repeat1/strict_lowpi_sign_status.csv | 30136 | `4fc316d31501a0b51908e75cb053799c8c66688a09571854c6408b7c8d7a1a80` |
| repeat1/strict_top3.csv | 27278 | `e5453c11cb05c2fd31f246c2f3ee7497522195ed7ada60435a5fea6dfb0811e5` |
| repeat1/strict_top3_by_method.csv | 116788 | `5793437c5f3c728c7c49aa4d5989f0b4941d217a931f2bb16d04a5ee3d9fcae4` |
| repeat2/extended_top3.csv | 25079 | `d06d61dd1b8f52e1d66f658a89052b8ff97dc688859fd8692b7bb56a64f895d9` |
| repeat2/extended_top3_by_method.csv | 107692 | `9f7cc82df5e15f7ca026efb60f845ceb25aa74feeb4b50054e00813e9c83f79e` |
| repeat2/sign_stability_summary.json | 36245 | `91d44a73498b39c690feb5c7d11b51c15176b9db79ec6f3b86ac756c94ab3057` |
| repeat2/strict_lowpi_sign_status.csv | 30985 | `553dcd7c604a573b36c20f26e74776d879f59456925cf8a555fa7256e8a15fb2` |
| repeat2/strict_top3.csv | 27415 | `f69e86f4312adbb2d353b94f0e0a768d73e449377bb0d024163599302456e1e4` |
| repeat2/strict_top3_by_method.csv | 117105 | `2146c6a017d2b905408382f1b2b23ce6cc4bf4b43137196be367f3388762280d` |
| sign_stability_summary.json | 218761 | `5922f4bc46872e3b0ed3e60306fb582a1b98839f3c588437b64e5f9cfc94ec38` |

## 6. 复现

```
python src/q2_v62_regen.py
```

脚本不读取 `state/ledger.json`，不重跑 bootstrap，不写入 `experiments/`；输出同时镜像到 `FINAL_SUBMISSION_v6.2/支撑材料/outputs/q2/`。
