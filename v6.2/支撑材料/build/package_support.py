#!/usr/bin/env python3
"""package_support.py — assemble FINAL_SUBMISSION_v6.2/支撑材料/ and its checksums.

Copies only the reproducible artefacts (never experiments/, never 2.9 GB of run
logs), strips .DS_Store / __pycache__ / historical archive directories, writes a
relative-path README.md + requirements.txt, and finally builds SHA256SUMS over the
whole support tree.

Run:
    python FINAL_SUBMISSION_v6.2/build/package_support.py
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SUBMISSION = BUILD.parent
PROJECT = SUBMISSION.parent
SUPPORT = SUBMISSION / "支撑材料"

EXCLUDE_DIRS = {".DS_Store", "__pycache__", ".pytest_cache", "revised-20261025", ".mpl"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log", ".aux", ".out", ".toc", ".bib"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, glob: str = "**/*") -> int:
    if not src.exists():
        print(f"[skip] missing {src}")
        return 0
    n = 0
    for path in sorted(src.glob(glob)):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.suffix in EXCLUDE_SUFFIX:
            continue
        if path.name.startswith("."):
            continue
        copy_file(path, dst / rel)
        n += 1
    return n


def copy_glob(src_glob: Path, dst: Path, pattern: str) -> int:
    n = 0
    for path in sorted(src_glob.glob(pattern)):
        if path.is_file() and path.name not in EXCLUDE_DIRS:
            copy_file(path, dst / path.name)
            n += 1
    return n



Q3_INDEX = """# Q3 结果文件索引（主键与形状）

本文件给出支撑材料 `outputs/q3/` 下各结果文件的**主键与用途**，便于逐格复核论文第 6 章。
全部文件均为 UTF-8 CSV/JSON；`chem__<name>` 列为 231 维化学/理化变量，`<dimension>` 列为 50 个感官标签。

| 文件 | 行数 × 列数 | 主键 / 结构 | 用途 |
| --- | --- | --- | --- |
| `samples.csv` | 750 × 237 | `sample_id`；键 `(repeat, fold, style, seed)`；`chem__*` 231 列 | 交付的约束后**设计谱**（题目要求的生成化合物谱全表） |
| `sensory_profiles.csv` | 1500 × 55 | `sample_id`；键 `(stage, repeat, fold, style)`；50 个 `<dimension>` 列 | 生成谱的感官代理画像（`stage=design` 与 `stage=raw` 各 750 行，题目要求的感官画像全表） |
| `samples_raw.csv` | 750 × 237 | 同上（`stage=raw`） | 未约束原始抽样，对照投影代价 |
| `q3_metrics.csv` / `energy_summary.csv` | 汇总 | 按格/按方案 | 归一化能量距离与质量指标 |
| `verdict_layers.csv` / `constraints.csv` | 逐条 | `(sample_id, constraint)` | 约束核验分层与逐条状态 |
| `transfers.csv` | 495 × 756 | 键 `(repeat, fold, source_beer, strategy)`；`src__/opt__/ref__ + chem__*` | 迁移前后设计值、缺陷状态与证书字段 |
| `transfer_verdicts.csv` | 逐 (策略, 字段, 边界类型, 判定) | 同左 | 约束核验计数 |
| `transfer_sources.csv` | 396 × 14 | 键 `(repeat, fold, source_beer, column)` | 源状态（实测/缺失/地板）与源值 |
| `transfer_constraints.csv` | 18810 = 5 策略 × 3762 | 键 `(strategy, …)` | 每条约束记录（3267 下界 + 396 源值上限 + 99 代理上界） |
| `solver_certificates.jsonl` | 198 行 | `problem_hash` | 每个 QP 的求解证书（状态/残差/KKT/半空间字段） |
| `v62_tables/tripel_kriek_lambic_profile_chem.csv` | 36 × 24 | 键 `(style, item_cn, column)` | 论文表 10 的三风格化学画像（含 P10/P90） |
| `v62_tables/tripel_kriek_lambic_profile_sensory.csv` | 15 × 24 | 键 `(style, item_cn, column)` | 论文表 11 的三风格感官画像 |
| `v62_tables/pils_to_tripel_single_source.csv` | 24 × 31 | 键 `(section, item_cn, column)` | 论文表 12 的单源迁移实例（源/锚点/参考/迁移后） |
| `v62_tables/defect_control_summary.csv` | 5 × 32 | 键 `column` | 论文表 15 的五类缺陷口径与核验计数 |
| `v62_tables/anchor_direct_projection.csv` | 159 × 17 | 键 `(level, strategy, repeat, fold)` | 论文表 17 的同锚点投影消融（pooled 与逐折） |
| `v62_tables/beer156_sensitivity.csv` | — | 键 `(scope, fold)` | beer156 极端坐标敏感性诊断 |
| `v62_tables/transfer_anchor_values.csv` | 22869 = 99 × 231 | 键 `(repeat, fold, source_beer, column)` | 99 个迁移点的分位数锚点全表（存储尺度 + 物理值） |
| `v62_diagnostics/v62_diagnostics.json` | — | 段：anchorDirectProjection / beer156Sensitivity / crossSetDiagnostic / assertions | 消融、敏感性与跨集邻近性的完整记录（54 条断言） |
| `v62_tables/q3_crossset_diagnostic.csv` | 10 行（9 折 + pooled） | 键 `(repeat, fold)` | 生成设计谱相对同折训练集的整行精确重合率与最近训练行标准化距离 |

**命名说明。** `outputs/q2/v62_clean/` 中的替代候选列历史名为 `alternative_rank4`；修复后该列语义已变为
“**首个合格同模块替代项**”（在模块点分序中剔除本维 Top-3 后取第一个），因此不再必然是模块点分第 4 名。
为保持与既有表格生成代码的兼容性未改列名，引用时请按正文口径读作“首个合格替代项”。

`outputs/q2/v62_clean/` 的四个 Top-3 CSV 与 `strict_lowpi_sign_status.csv` 同时带有
`alternative_rank4` 与 `alternative_first_valid` 两列，**两列取值逐格相同**：
`alternative_rank4` 为历史列名（下游脚本兼容用），`alternative_first_valid` 为本次修复后的规范列名
（“首个合格同模块替代项”）。两者同义，任取其一即可。
"""


# -- version map for the legacy hashes quoted inside sign_stability_summary.json --
def write_legacy_version_map() -> int:
    """[v6.1 §3.5-4] map every old-export hash to its identity and successor."""
    import json
    summary = json.loads((PROJECT / "outputs" / "q2" / "v62_clean" / "sign_stability_summary.json")
                         .read_text(encoding="utf-8"))
    rows = []
    for repeat in ("0", "1", "2"):
        rec = summary.get("legacyReproduction", {}).get(repeat)
        if not rec:
            continue
        rows.append({
            "repeat": int(repeat),
            "referenceFile": rec.get("reference"),
            "referenceSha256": rec.get("referenceSha256"),
            "identity": "旧导出的 Q2 符号稳定性表（EXP-0075 时代，schema q2-sign-stability/1）",
            "role": "历史对照，仅用于复现旧口径 P(rho>0)；不是当前交付结果",
            "supersededBy": f"outputs/q2/v62_clean/repeat{repeat}/strict_top3.csv",
            "supersededBySha256": hashlib.sha256(
                (PROJECT / "outputs/q2/v62_clean" / f"repeat{repeat}" / "strict_top3.csv").read_bytes()
            ).hexdigest(),
        })
    payload = {
        "purpose": "版本映射：sign_stability_summary.json 的 legacyReproduction.referenceSha256 指向的旧导出，"
                   "与其身份和被取代后的当前文件一一对应，避免把历史哈希误当当前结果。",
        "currentSchemaVersion": summary.get("schemaVersion"),
        "supersededSchemaVersion": "q2-sign-stability/1",
        "currentEntry": "outputs/q2/v62_clean/",
        "mapping": rows,
    }
    target = SUPPORT / "outputs" / "q2" / "LEGACY_VERSION_MAP.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(rows)



AI_SRC_BANNER = (
    "# AI-ASSISTANCE NOTICE\n"
    "# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由\n"
    "# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。\n"
    "# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,\n"
    "# constraint corrections and experimental parameters were reviewed, amended and independently verified\n"
    "# by the team members, who take responsibility for the contents.\n"
)

AI_NOTICE_MD = """# 源码 AI 辅助声明（支撑材料）

`src/*.py` 中每个脚本的文件头都带有统一声明：

> 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由参赛队员人工审阅、
> 修改并独立核验通过，队员对最终内容负责。

说明：

- 论文附录 C 展示的源码同样带该声明（每个模块代码块首部）。
- 加入声明只增加注释行、不改变任何可执行语义；因此**支撑材料副本**的 sha256 与原始运行脚本不同。
- 原始运行脚本（即实验清单里登记的 run-time 哈希对应文件）与副本的逐一映射见 `src/SOURCE_HASHES.json`；
  其中 `originalSha256` 是项目 `src/` 的原始文件哈希，`supportSha256` 是加入声明后的本目录副本哈希。
- `SHA256SUMS` 覆盖本目录所有文件（含带声明的副本）。
"""


def add_source_banner() -> int:
    """[v6.1 §6] prepend the uniform AI-assistance notice to every support src/*.py."""
    import json
    rows = []
    count = 0
    for path in sorted((SUPPORT / "src").glob("*.py")):
        original = PROJECT / "src" / path.name
        text = path.read_text(encoding="utf-8")
        if "AI-ASSISTANCE NOTICE" in text:
            continue
        lines = text.split("\n")
        insert_at = 0
        if lines and lines[0].startswith("#!"):
            insert_at = 1
        lines.insert(insert_at, AI_SRC_BANNER.rstrip("\n"))
        path.write_text("\n".join(lines), encoding="utf-8")
        count += 1
        rows.append({
            "file": path.name,
            "originalSha256": sha256(original) if original.exists() else None,
            "supportSha256": sha256(path),
            "note": "支撑材料副本在文件头加入统一 AI 辅助声明；originalSha256 对应实验清单登记的运行脚本",
        })
    (SUPPORT / "src" / "AI-ASSISTANCE-NOTICE.md").write_text(AI_NOTICE_MD, encoding="utf-8")
    (SUPPORT / "src" / "SOURCE_HASHES.json").write_text(
        json.dumps({"rule": AI_NOTICE_MD.splitlines()[0], "files": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return count


README = """# MathorCup 2026 A 题 · v6.2 支撑材料

本目录是参赛论文《基于稳健表示、共表达网络与风格条件生成的啤酒化合物—感官强度建模》
（`../论文正式版.pdf`）的完整支撑材料：可复现源码、清洗与划分数据、三问全部结果表，
以及论文生成脚本。所有路径均为**相对路径**，不依赖任何个人机器的绝对目录。

## 1. 目录结构

| 目录 | 内容 |
| --- | --- |
| `src/` | 三问全部可复现源码（数据准备、四模型嵌套交叉验证、Q2 共表达网络与 bootstrap、Q3 条件生成与迁移 QP、稳健性与复核脚本），另含 `build_paper.py`（Markdown→LaTeX 转换器） |
| `data/clean/` | 清洗后的三问输入表：`q1_mapped.csv`、`q2_raw.csv`、`q3.csv`、阈值与风格协议 |
| `data/splits/` | 冻结数据划分：`NESTED-CV-1`（问题一 3×3×3 嵌套交叉验证）、`SPLIT-0001`（问题二 200 行训练集）、`SPLIT-0002` |
| `data/processed/` | 特征字典与派生常量（单位/尺度校准、感官名称对齐、分级参数） |
| `outputs/q1/` | 问题一结果：250×50 连续评分与 0–6 相对等级、750 行折外预测、逐维/逐风格误差 |
| `outputs/q2/` | 问题二结果：`v62_clean/`（**去重后**的 Top-3、符号计数与稳定性摘要；Top-3 表同时含 `alternative_rank4` 与 `alternative_first_valid` 两列，取值相同、后者为规范名）、附件 2 描述性网络四件套、bootstrap 频率、点估计相关矩阵、旧哈希版本映射 |
| `outputs/q3/` | 问题三结果：生成谱 `samples*.csv`、感官画像 `sensory_profiles.csv`、迁移结果 `transfers.csv`、198 个 QP 证书、同锚点投影消融、`beer156` 敏感性诊断、分位数锚点全表、三张实体答案表 |
| `outputs/robustness/` | 四组稳健性检验的确认性汇总 |
| `build/` | 论文生成脚本、LaTeX 头/模板、最终论文 `.md`/`.tex` 源与源程序附录、PDF 版式核验结果、`build_all.sh` 一键重建 |
| `AI说明/` | 《AI 工具使用详情说明》的 `.tex`/`.md`/`.pdf` |

## 2. 环境

- Python 3.12，依赖见 `requirements.txt`（`numpy`、`pandas`、`scipy`、`scikit-learn`、`matplotlib`、`pypdf`）。
- 复现论文 PDF 另需 `pandoc` 3.x 与 `xelatex`（TeX Live 2025），以及系统字体
  `Times New Roman`、`Arial`、`Menlo`、`Songti SC`。

## 3. 直接复现（在本目录内，完全自包含）

```bash
python -m pip install -r requirements.txt
export PAPER_PROJECT_DIR="$PWD"
bash build/build_all.sh
```

`build_all.sh` 的四步含义：① 由 `outputs/q2/v62_clean/` 重建论文表 7 与附录长表；
② 由 `outputs/q3/v62_diagnostics/v62_diagnostics.json` 重建同锚点投影消融表；③ 由 `outputs/q3/v62_tables/`
重建三张实体答案表；④ 由 `build/paper_draft_base.md`（评审稿）+ 上述表片段生成
`build/paper_final.md`、`paper_final.tex`，经 `pandoc` + `xelatex` 编出 `论文正式版.pdf`，
最后运行 PDF 版式核验并输出 `build/out/pdf-audit.json`。

## 4. 归约到原始实验（可选）

两个**重导脚本**的输入是竞赛实验目录 `experiments/` 的已保存产物（该目录约 2.9 GB，未打包）；
在原始项目根目录下可运行：

```bash
python src/q2_v62_regen.py        # 问题二：重导去重后的交付表（不重跑 bootstrap）
python src/q3_v62_diagnostics.py  # 问题三：同锚点投影消融 + beer156 敏感性诊断
```

二者都已在本材料 `outputs/` 中留有**全部输出**；论文中的每个数字都可以直接从 `outputs/`
复核，无需重跑实验。三问主实验的运行命令见项目根目录 `REPRODUCE.md`。

## 5. 论文数字 → 文件对照

| 论文位置 | 数据文件 |
| --- | --- |
| 表 1–2（问题一四模型与分组误差） | `outputs/q1/model_comparison.csv`、`outputs/q1/error_analysis.csv` |
| 表 3（相对等级一致性） | `outputs/q1/grades_250.csv`、`outputs/q1/export_manifest.json` |
| 表 4–5（Beer#1–10 核心维度等级） | `outputs/q1/oof_predictions_750.csv`（评价侧，首轮重复） |
| 表 6（候选宇宙） | `outputs/q2/v62_clean/repeat0/strict_top3.csv`、`outputs/q2/v62_clean/v62_manifest.json` |
| 表 7、附录长表（Top-3 与同模块替代） | `outputs/q2/v62_clean/repeat0/strict_top3.csv`、`strict_top3_by_method.csv`、`extended_top3.csv` |
| 表 8–9（生成谱与分布质量） | `outputs/q3/samples.csv`、`energy_summary.csv`、`q3_metrics.csv` |
| 表 10（QP 证书） | `outputs/q3/solver_certificates.jsonl`、`transfer_metrics.json` |
| 表 11（迁移策略） | `outputs/q3/transfers.csv`、`transfer_metrics.json` |
| 表 12–17（迁移、缺陷、消融与三张实体表） | `outputs/q3/v62_tables/`（含 `anchor_direct_projection.csv`、`beer156_sensitivity.csv`、`transfer_anchor_values.csv`） |
| 表 18–20（稳健性与约束） | `outputs/robustness/`、`outputs/q2/v62_clean/sign_stability_summary.json` |
| 图 1–10 | `build/figures/confirmatory_v2/` |

## 5b. 源码 AI 辅助声明

`src/*.py` 每个文件头都带有统一的 AI 辅助声明（框架由 DeepSeek Harness 辅助生成；核心算法逻辑、约束修正与实验参数
由队员人工审阅、修改并独立核验）。声明只增加注释、不改变语义，因此副本的 sha256 与运行脚本不同；
原始哈希与副本哈希的对应关系见 `src/SOURCE_HASHES.json`，说明见 `src/AI-ASSISTANCE-NOTICE.md`。

## 6. 校验

`SHA256SUMS` 覆盖本目录除自身外的全部文件：

```bash
shasum -a 256 -c SHA256SUMS
```

## 7. 口径声明

- 问题一没有独立外部测试集：全部误差为 3×3×3 嵌套交叉验证的外折结果。
- 问题二的方向一致率按 150 / 600 / 1800 三个分母分列，引用时必须写明分母；同模块替代候选已剔除同维 Top-3。
- 问题三的生成未优于同量源样本重采样参照；迁移只是声明模型下的最优，没有迁移后真实标签。
- 缺陷约束是“不高于源样本”的数学筛查，不是感官阈值合格证明。
"""

REQUIREMENTS = """numpy==2.3.5
pandas==2.2.3
scipy==1.18.1
scikit-learn==1.9.1
matplotlib==3.11.2
pypdf==6.10.0
"""


def main() -> int:
    if SUPPORT.exists():
        shutil.rmtree(SUPPORT)
    SUPPORT.mkdir(parents=True)

    counts: dict[str, int] = {}

    # 1) source code (the modeling scripts + the paper builder)
    n = 0
    for path in sorted((PROJECT / "src").glob("*.py")):
        if path.name.startswith("."):
            continue
        copy_file(path, SUPPORT / "src" / path.name)
        n += 1
    counts["src"] = n

    # 2) cleaned data + frozen splits + processed dictionary
    counts["data/clean"] = copy_tree(PROJECT / "data" / "clean", SUPPORT / "data" / "clean")
    for split in ("NESTED-CV-1", "SPLIT-0001", "SPLIT-0002"):
        src = PROJECT / "data" / "splits" / split
        if src.exists():
            counts[f"data/splits/{split}"] = copy_tree(src, SUPPORT / "data" / "splits" / split)
    counts["data/processed"] = copy_tree(PROJECT / "data" / "processed", SUPPORT / "data" / "processed")

    # 3) results
    counts["outputs/q1"] = copy_tree(PROJECT / "outputs" / "q1", SUPPORT / "outputs" / "q1")
    counts["outputs/q2"] = copy_tree(PROJECT / "outputs" / "q2", SUPPORT / "outputs" / "q2")
    counts["outputs/q3"] = copy_tree(PROJECT / "outputs" / "q3", SUPPORT / "outputs" / "q3")
    counts["outputs/robustness"] = copy_tree(PROJECT / "outputs" / "robustness",
                                             SUPPORT / "outputs" / "robustness")

    # 4) the exact experiment artefacts the paper cites (small, selected files only)
    picks = [
        ("experiments/EXP-0109/samples.csv", "outputs/q3/samples.csv"),
        ("experiments/EXP-0109/sensory_profiles.csv", "outputs/q3/sensory_profiles.csv"),
        ("experiments/EXP-0109/q3_metrics.csv", "outputs/q3/q3_metrics.csv"),
        ("experiments/EXP-0109/energy_summary.csv", "outputs/q3/energy_summary.csv"),
        ("experiments/EXP-0109/verdict_layers.csv", "outputs/q3/verdict_layers.csv"),
        ("experiments/EXP-0109/constraints.csv", "outputs/q3/constraints.csv"),
        ("experiments/EXP-0110/transfers.csv", "outputs/q3/transfers.csv"),
        ("experiments/EXP-0110/transfer_verdicts.csv", "outputs/q3/transfer_verdicts.csv"),
        ("experiments/EXP-0110/transfer_sources.csv", "outputs/q3/transfer_sources.csv"),
        ("experiments/EXP-0110/transfer_constraints.csv", "outputs/q3/transfer_constraints.csv"),
        ("experiments/EXP-0110/transfer_metrics.json", "outputs/q3/transfer_metrics.json"),
        ("experiments/EXP-0110/solver_certificates.jsonl", "outputs/q3/solver_certificates.jsonl"),
        ("experiments/EXP-0107/bootstrap_pi.csv", "outputs/q2/bootstrap_pi.csv"),
        ("experiments/EXP-0107/repeat0/sign_counts.csv", "outputs/q2/v62_clean/repeat0/sign_counts.csv"),
        ("experiments/EXP-0073/oof_long.csv", "outputs/q1/oof_long.csv"),
        ("experiments/EXP-0073/metrics.json", "outputs/q1/metrics.json"),
    ]
    n = 0
    for rel_src, rel_dst in picks:
        src = PROJECT / rel_src
        if not src.exists():
            print(f"[skip] {rel_src}")
            continue
        copy_file(src, SUPPORT / rel_dst)
        n += 1
    counts["experiment extracts"] = n

    # derived point-score extract so the Q2 table can be rebuilt without experiments/
    scores_src = PROJECT / "experiments" / "EXP-0107" / "candidate_scores.csv"
    if scores_src.exists():
        import pandas as pd
        frame = pd.read_csv(scores_src, usecols=["dimension", "compound", "rho_total", "rho_within"])
        frame.to_csv(SUPPORT / "outputs" / "q2" / "candidate_scores_point.csv", index=False)
        counts["q2 point-score extract"] = 1

    # 5) paper build tree: scripts, sources, final tex, audit
    build_dst = SUPPORT / "build"
    n = 0
    for name in ("make_paper.py", "sync_tables.py", "build_final.py", "make_q2_table.py",
                 "make_q3_extra_tables.py", "make_q3_answer_tables.py", "make_source_appendix.py",
                 "package_support.py",
                 "header.tex", "template.tex", "paper_final.md", "paper_final.build.json",
                 "paper_draft_base.md", "build_all.sh"):
        src = BUILD / name
        if src.exists():
            copy_file(src, build_dst / name)
            n += 1
    for name in ("paper.pandoc.md", "paper_final.tex", "source_appendix.tex", "pdf-audit.json"):
        src = BUILD / "out" / name
        if src.exists():
            copy_file(src, build_dst / "out" / name)
            n += 1
    counts["build"] = n
    counts["build/tables"] = copy_tree(BUILD / "tables", build_dst / "tables")
    counts["build/figures"] = copy_tree(BUILD / "figures", build_dst / "figures")

    # 6) AI-usage document sources
    for name in ("AI工具使用详情说明.tex", "AI工具使用详情说明.md",
                 "AI工具使用详情说明.pdf"):
        src = SUBMISSION / name
        if src.exists():
            copy_file(src, SUPPORT / "AI说明" / name)

    counts["src AI banners"] = add_source_banner()

    # 6b) strip every personal absolute path from the copied text artefacts
    replacements = [
        (str(PROJECT) + "/FINAL_SUBMISSION_v6.2/", ""),
        (str(PROJECT) + "/", ""),
        (str(PROJECT), "."),
        ("python", "python"),
    ]
    text_suffixes = {".md", ".py", ".json", ".txt", ".csv", ".tex", ".sh", ".jsonl", ".md"}
    cleaned = 0
    for path in SUPPORT.rglob("*"):
        if not path.is_file() or path.suffix not in text_suffixes:
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text = raw
        for old_text, new_value in replacements:
            new_text = new_text.replace(old_text, new_value)
        new_text = new_text.replace("", "")
        if new_text != raw:
            path.write_text(new_text, encoding="utf-8")
            cleaned += 1
    counts["path-sanitised files"] = cleaned

    (SUPPORT / "outputs" / "q3" / "OUTPUT_INDEX.md").write_text(Q3_INDEX, encoding="utf-8")
    counts["legacy version map"] = write_legacy_version_map()
    counts["q3 output index"] = 1

    # 7) README + requirements
    (SUPPORT / "README.md").write_text(README, encoding="utf-8")
    (SUPPORT / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")

    # 8) checksums over everything except SHA256SUMS itself
    lines = []
    for path in sorted(SUPPORT.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        rel = path.relative_to(SUPPORT).as_posix()
        lines.append(f"{sha256(path)}  {rel}")
    (SUPPORT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[OK] support tree assembled")
    for key, value in counts.items():
        print(f"  {key}: {value} file(s)")
    total = sum(1 for p in SUPPORT.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in SUPPORT.rglob("*") if p.is_file())
    print(f"  total: {total} files, {size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
