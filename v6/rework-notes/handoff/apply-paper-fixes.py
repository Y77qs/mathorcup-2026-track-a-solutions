#!/usr/bin/env python3
"""Phase-2 helper: apply the REV-0038 residual fixes (F2/F4/F5, typo) to report/paper.md.

Runs on the ORIGINAL project (or a copy): python3 apply-paper-fixes.py <projectDir> [--include-figure-history-note]
Idempotent: every replacement asserts the OLD text is present exactly once; if a replacement is already applied it
reports "already applied" and continues. Writes report/paper.md in place; then the Phase-2 lifecycle must
render/build/artifact/check/package again (the paper source change invalidates the old render binding).
"""
import sys, pathlib

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
p = ROOT / 'report/paper.md'
text = p.read_text(encoding='utf-8')
edits = []

def rep(old, new, label):
    global text
    if old in text:
        assert text.count(old) == 1, f'{label}: old text occurs {text.count(old)} times'
        text = text.replace(old, new, 1)
        edits.append((label, 'applied'))
    elif new in text:
        edits.append((label, 'already applied'))
    else:
        raise SystemExit(f'{label}: neither old nor new text found; paper.md changed unexpectedly')

# F2 (overfull line p4): split one inline-math token list so the line can break at the ideographic comma
rep(
    '7 个边界样例（覆盖 $a=0,\\,1/12,\\,1/6,\\,1/2,\\,3/4,\\,11/12,\\,1$）固定下来',
    '7 个边界样例（覆盖 $a=0$、$1/12$、$1/6$、$1/2$、$3/4$、$11/12$、$1$）固定下来',
    'F2 split boundary-sample math',
)

# F5 (hand-written metric 1.0 in the abstract): use the registered metric placeholder and refer to it by name
rep(
    '但“策略相对不恶化率 1.0”是投影构造保证的；',
    '但“策略相对不恶化率 {{metric:EXP-0033:transfer-nonworsen-rate}}”是投影构造保证的；',
    'F5 abstract placeholder',
)
rep(
    '两种口径必须分开读，不能把 1.0 读成经验性的可行性结论。',
    '两种口径必须分开读，不能把该策略相对率读成经验性的可行性结论。',
    'F5 abstract wording',
)

# F4 (duplicated numbers between the prose and the registered CLAIM-0022 paragraph)
rep(
    '**两种策略的差别不在可行性或代价，而在保证的强度**：四种情景在各自可行域内都可行，平均 L1 改动与目标马氏距离在两种策略下几乎相同（逐情景数值见 EXP-0033 `outputs.transfer-scenarios`），差别只是后者把每个缺陷都压到不超过源样本、前者只压到不超过 $\\max(c^{\\mathrm{source}},T)$，因此后者的输出对“逐缺陷严格不增”这一更严标准的达标率只有 {{metric:EXP-0033:transfer-scenario-strict-nonworsen-min}}。上式的 {{metric:EXP-0033:transfer-scenario-strict-nonworsen-min}} 是**该策略输出的严格达标率**，不是“源样本中存在严格不增可行解的比例”；任何把两个口径混读的说法都不成立。迁移结论登记如下：',
    '**两种策略的差别不在可行性或代价，而在保证的强度**；逐情景数值与严格达标率口径见下方登记的迁移结论与 EXP-0033 `outputs.transfer-scenarios`，两种口径不可混读。迁移结论登记如下：',
    'F4 remove duplicated number restatement',
)

# F5 + typo in section 9: no hand-written 1.0, and remove the duplicated 也
rep(
    '不能把 1.0 读成经验性的可行性结论，也也不能把该达标率读成',
    '不能把该策略相对率读成经验性的可行性结论，也不能把该达标率读成',
    'F5 section 9 wording + typo',
)

# F5 (delta = 0 is a validation property, not a paper metric): point at the validation records instead
rep(
    '（VAL-0036 / VAL-0039 / VAL-0043，全部 delta = 0）',
    '（VAL-0036 / VAL-0039 / VAL-0043，全部在声明的容差内复现，逐项比较见各 VAL 的 `result.json`）',
    'F5 validation delta wording',
)

# F5 (data constants must be traceable to a registered source; they are not experiment metrics)
rep(
    '其余 **161 列**无校准表直接覆盖。',
    '其余 **161 列**无校准表直接覆盖（逐列判定表见 `outputs/audit/scale_identification.csv`，由 `src/prepare_base.py` 生成并随包交付）。',
    'F5 scale-audit source pointer',
)
rep(
    '（DMS 17.25 μg/L、双乙酰 0.29925 mg/L、4VG 0.206333 mg/L，取 8.xlsx 均值）',
    '（DMS 17.25 μg/L、双乙酰 0.29925 mg/L、4VG 0.206333 mg/L，取 8.xlsx 均值，阈值登记在 `data/clean/q3_thresholds.json`）',
    'F5 threshold source pointer',
)

if '--include-figure-history-note' in sys.argv:
    # After the Phase-2 figure migration (canonical archive paths), replace the stale "same path" sentence.
    rep(
        '逐图 sha256 入台账；被取代的 FIG-0025/0027 是同一路径的旧字节记录，保留为历史。',
        '逐图 sha256 入台账；被取代的 FIG-0025/0027 已用 figure-retire 标记为 superseded（分别指向 FIG-0030/FIG-0031），旧字节归档到 `figures/archive/FIG-0025-q3_defect_exceedance.png` 与 `figures/archive/FIG-0027-q3_pareto.png`（归档字节与登记 sha256 逐字节核验一致），旧记录、路径历史与旧→新关系保留在台账。',
        'figure history note',
    )

p.write_text(text, encoding='utf-8')
for label, state in edits:
    print(('  ok   ' if state == 'applied' else '  skip ') + label + ' — ' + state)
print('report/paper.md updated: ' + str(p))
