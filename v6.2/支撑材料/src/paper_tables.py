#!/usr/bin/env python
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""paper_tables.py -- evidence-driven business tables for report/paper.md.

What it does
------------
Reads ONLY the confirmatory artifacts listed in ALLOWED_EXPERIMENTS (plus the
read-only ``report/evidence_manifest.json`` and ``state/ledger.json`` used for
cross-checks), and writes:

  report/tables/<id>.md     markdown pipe table fragment (embeddable in paper.md)
  report/tables/<id>.csv    the same data in machine-readable form (full precision)
  report/tables/INDEX.json  per-table input paths + sha256, output sha256,
                            table -> experiment mapping, script sha256, status

Rules enforced by construction
-----------------------------
* No hand-typed numbers: every value is read from an artifact at run time; a
  missing file / metric key produces a NAMED failure
  ``TABLE <key> INCOMPLETE: <detail>`` and a non-zero exit code. Nothing is
  substituted with 0 and nothing falls back to a retired experiment.
* ``.md`` fragments (which are spliced into the paper body) carry no ledger
  identifiers at all: no EXP-/VAL-/ROB-/CLAIM-/MCON-/FIG- ids, no raw run
  labels (seed numbers, "repeat N").  Ids, paths and sha256 live in the
  ``.csv`` ``_source`` column and in INDEX.json only.
* Deterministic: repeated builds produce byte-identical md/csv. Only
  INDEX.json carries ``generatedAt``.
* Self-check: every metric value used is compared digit-for-digit against the
  same metric key stored in ``state/ledger.json`` for the same experiment.

Sub-commands
------------
  --build              build all tables + INDEX.json (default)
  --verify             recompute every recorded sha256 and compare with INDEX.json
  --splice PATH        replace ``<!-- TABLE:<id> -->`` lines in PATH with
                       table-begin/fragment/table-end blocks (idempotent).
                       NOT run against report/paper.md by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES_DIR = ROOT / "report" / "tables"
INDEX_PATH = TABLES_DIR / "INDEX.json"

# --------------------------------------------------------------------------- whitelist
# v6 confirmatory round: Q1 EXP-0073/0074 (+ ROB-0011 = EXP-0100/0101/0102),
# Q2 EXP-0107 (reference) + EXP-0113/0114, Q3 generation EXP-0109 + EXP-0115/0116,
# Q3 transfer EXP-0110 + EXP-0117/0118.
SUPPORT_ONLY_TABLES = frozenset({
    "q1-targets", "q1-styles", "q2-full-top3", "q2-extended",
})

ALLOWED_EXPERIMENTS = (
    "EXP-0073", "EXP-0074", "EXP-0107", "EXP-0109", "EXP-0110",
    "EXP-0125", "EXP-0126", "EXP-0127", "EXP-0128", "EXP-0129", "EXP-0130",
    "EXP-0131", "EXP-0132", "EXP-0133",
    "EXP-0100", "EXP-0101", "EXP-0102",
)
# EXP-0131/0132/0133 are the repeat-2 seed blocks executed AFTER the robustness plans
# were registered: they are cited ONLY as a separately labelled supplementary block
# (never merged into a plan's values/spread/decision).
FORBIDDEN_EXP_PATTERNS = (
    re.compile(r"EXP-00(?:3[89]|[456]\d|7[0-2])\b"),   # EXP-0038..EXP-0072
    re.compile(r"EXP-007[67]\b"),                       # EXP-0076 / EXP-0077
    re.compile(r"EXP-00(?:7[59]|8[0])\b"),              # EXP-0075 / 0079 / 0080 (superseded by 0107/0109/0110)
    re.compile(r"EXP-00(?:8[9]|9\d)\b"),                # EXP-0089..0099 (superseded robustness round)
)
LEDGER_REL = "state/ledger.json"
MANIFEST_REL = "report/evidence_manifest.json"

# identifiers that must never reach a .md fragment
MD_FORBIDDEN_ID = re.compile(r"\b(?:EXP|VAL|ROB|CLAIM|MCON|FIG)-\d+\b")
MD_FORBIDDEN_RUNLABEL = re.compile(r"(?:seed\s*20\d{4}|repeat\s*\d|外折\s*[012]\b)", re.IGNORECASE)


class TableIncomplete(Exception):
    """A table cannot be built from the confirmatory artifacts."""

    def __init__(self, key: str, detail: str):
        self.key = key
        self.detail = detail
        super().__init__(f"TABLE {key} INCOMPLETE: {detail}")


class GuardFailure(TableIncomplete):
    """Two artifacts disagree; building this table would publish a wrong number."""


# --------------------------------------------------------------------------- formatting
def fnum(x, nd: int = 4) -> str:
    """3-4 decimals for ordinary magnitudes, scientific notation for tiny/huge.

    Never collapses a non-zero residual to 0.0000: values below 1e-3 and above
    1e6 are printed with ``nd`` significant digits instead.
    """
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "是" if x else "否"
    if isinstance(x, int):
        return str(x)
    x = float(x)
    if math.isnan(x):
        return "—"
    a = abs(x)
    if a == 0.0:
        return f"{0.0:.{nd}f}"
    if 1e-3 <= a < 1e6:
        return f"{x:.{nd}f}"
    return f"{x:.{nd}g}"


def fint(x) -> str:
    if x is None:
        return "—"
    return str(int(round(float(x))))


def fshare(count, total, nd: int = 4) -> str:
    if not total:
        return "—"
    return f"{count / total:.{nd}f}"


def csv_cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return str(v)


def md_table(header, rows, aligns=None) -> str:
    aligns = aligns or (["l"] + ["r"] * (len(header) - 1))
    sep = []
    for a in aligns:
        sep.append("---" if a == "l" else "---:")
    def cell(value):
        return str(value).replace("|", "\\|")

    out = ["| " + " | ".join(cell(h) for h in header) + " |",
           "| " + " | ".join(sep) + " |"]
    for row in rows:
        out.append("| " + " | ".join(cell(c) for c in row) + " |")
    return "\n".join(out)


def pct(x, nd: int = 2) -> str:
    return f"{100.0 * float(x):.{nd}f}%"


def close(a, b, rel_tol=1e-12, abs_tol=0.0) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b or math.isclose(float(a), float(b), rel_tol=rel_tol, abs_tol=abs_tol)
    return a == b


# --------------------------------------------------------------------------- constants from the project
def _load_target_columns():
    path = ROOT / "src" / "target_columns.py"
    spec = importlib.util.spec_from_file_location("_paper_tables_target_columns", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # pure constants module
    return mod


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


DIM_LABELS = {
    "A_malt_all": "香气·麦芽总体", "A_malt_grain": "香气·谷物", "A_malt_bread": "香气·面包",
    "A_malt_cara": "香气·焦糖", "A_malt_burn": "香气·烘烤",
    "A_hops_all": "香气·酒花总体", "A_hops_citrus": "香气·柑橘", "A_hops_tropical": "香气·热带水果",
    "A_hops_noble": "香气·贵族酒花", "A_hops_woody": "香气·木质",
    "A_esters_all": "香气·酯香总体", "A_esters_ethac": "香气·乙酸乙酯", "A_esters_isoaa": "香气·乙酸异戊酯",
    "A_esters_flower": "香气·花香", "A_esters_fruity": "香气·果香",
    "F_malt_all": "风味·麦芽总体", "F_malt_grain": "风味·谷物", "F_malt_bread": "风味·面包",
    "F_malt_cara": "风味·焦糖", "F_malt_burn": "风味·烘烤",
    "F_hops_all": "风味·酒花总体", "F_hops_citrus": "风味·柑橘", "F_hops_tropical": "风味·热带水果",
    "F_hops_noble": "风味·贵族酒花", "F_hops_woody": "风味·木质",
    "F_esters_all": "风味·酯香总体", "F_esters_ethac": "风味·乙酸乙酯", "F_esters_isoaa": "风味·乙酸异戊酯",
    "F_esters_flower": "风味·花香", "F_esters_fruity": "风味·果香",
    "acidity": "酸感", "bitternes": "苦感", "sweetness": "甜感", "X4vg": "4-乙烯基愈创木酚",
    "diacetyl": "双乙酰", "dms": "二甲基硫", "metallic": "金属感", "stale_hops": "老化酒花",
    "t2n": "反-2-壬烯醛", "orange": "橙香", "coriander": "芫荽", "clove": "丁香",
    "lactic": "乳酸感", "acetic": "醋酸感", "barnyard": "马厩味", "alcohol": "酒精感",
    "aftertaste": "回味", "body": "酒体", "co2": "二氧化碳", "overall": "总体评价",
}

KIND_LABELS = {
    "single_compound": "单体化合物",
    "element_or_index": "元素/指数",
    "physical_parameter": "理化参数",
    "derived_sum": "派生和",
}

CORE_A5 = ["A_malt_all", "A_hops_all", "A_hops_citrus", "A_esters_all", "A_esters_isoaa"]
CORE_F5 = ["F_malt_all", "F_hops_all", "F_hops_citrus", "F_esters_all", "F_esters_isoaa"]

QUESTION_LABELS = {
    "Q1": "问题一", "Q2": "问题二", "Q3gen": "问题三·生成", "Q3mig": "问题三·迁移",
}

STRATEGY_LABELS = {
    "qp-quantile-anchor": "QP·分位数锚定（交付策略）",
    "qp-source-anchor": "QP·源锚定",
    "source-fixed": "源固定（平凡对照）",
    "target-mean-projection": "目标均值投影（盒约束诊断对照）",
    "target-mean-projection-full": "目标均值投影·完整可行域（参照基线）",
}

COMPARISON_LABELS = {
    "copula-selected": "分层收缩混合 Copula 设计谱（主方案）",
    "copula-shared-only": "仅共享相关 Copula",
    "copula-style-empirical": "风格内经验 Copula",
    "independent-marginals": "独立边际",
    "source-resample": "源样本重采样参照",
}

CHEM_LABELS = {
    "DMS": "二甲基硫（DMS）",
    "X2.3.butanedione": "双乙酰（2,3-丁二酮）",
    "X.E..2.nonenal": "反-2-壬烯醛",
    "X4VG": "4-乙烯基愈创木酚（4VG）",
    "stale_hops(ridge-proxy)": "老化酒花代理（岭回归代理）",
}


# --------------------------------------------------------------------------- context
class Ctx:
    """Filesystem access with per-table input tracking and ledger cross-checks."""

    def __init__(self, with_ledger: bool = True):
        self.inputs_by_table = {}
        self.checks_by_table = {}
        self._md_by_table = {}
        self._target_columns = None
        self._ledger = None
        self._manifest = None
        self.ledger_rel = LEDGER_REL
        self.manifest_rel = MANIFEST_REL
        if with_ledger:
            self._ledger = self._load_ledger()
            self._manifest = json.loads((ROOT / MANIFEST_REL).read_text(encoding="utf-8"))

    # ---- input bookkeeping
    def note_input(self, key: str, rel: str):
        if FORBIDDEN_EXP_PATTERNS:
            for pat in FORBIDDEN_EXP_PATTERNS:
                if pat.search(rel):
                    raise GuardFailure(key, f"输入落在禁引实验上：{rel}")
        m = re.search(r"EXP-(\d{4})", rel)
        if m and f"EXP-{m.group(1)}" not in ALLOWED_EXPERIMENTS:
            raise GuardFailure(key, f"输入实验不在白名单：{rel}")
        self.inputs_by_table.setdefault(key, set()).add(rel)

    def _read(self, key: str, rel: str) -> bytes:
        self.note_input(key, rel)
        path = ROOT / rel
        if not path.is_file():
            raise TableIncomplete(key, f"缺少输入文件 {rel}")
        data = path.read_bytes()
        if not data.strip():
            raise TableIncomplete(key, f"输入文件为空 {rel}")
        return data

    def json(self, key: str, rel: str, what: str = ""):
        raw = self._read(key, rel)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            raise TableIncomplete(key, f"无法解析 {rel}（{exc}）") from exc

    def jsonl(self, key: str, rel: str):
        raw = self._read(key, rel)
        out = []
        for i, line in enumerate(raw.decode("utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception as exc:  # pragma: no cover
                raise TableIncomplete(key, f"{rel} 第 {i + 1} 行无法解析（{exc}）") from exc
        if not out:
            raise TableIncomplete(key, f"{rel} 没有记录")
        return out

    def frame(self, key: str, rel: str, **kwargs):
        raw = self._read(key, rel)
        import io
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise TableIncomplete(key, f"缺少 pandas，无法读取 {rel}") from exc
        try:
            return pd.read_csv(io.BytesIO(raw), **kwargs)
        except Exception as exc:
            raise TableIncomplete(key, f"{rel} 读取失败（{exc}）") from exc

    # ---- metric access with named failures
    @staticmethod
    def metric(metrics: dict, name: str, key: str, rel: str):
        if name not in metrics:
            raise TableIncomplete(key, f"{rel} 缺少 metric key '{name}'")
        return metrics[name]

    # ---- ledger cross-checks
    def _load_ledger(self):
        path = ROOT / LEDGER_REL
        if not path.is_file():
            raise SystemExit(f"缺少台账 {LEDGER_REL}，无法做自检")
        return json.loads(path.read_text(encoding="utf-8"))

    def ledger_metrics(self, key: str, exp: str) -> dict:
        for record in self._ledger.get("experiments", []):
            if record.get("id") == exp:
                metrics = record.get("metrics") or {}
                if not metrics:
                    raise TableIncomplete(key, f"台账 {exp} 没有 metrics")
                return metrics
        raise TableIncomplete(key, f"台账中找不到实验 {exp}")

    def assert_ledger(self, key: str, exp: str, metric_key: str, value):
        led = self.ledger_metrics(key, exp)
        if metric_key not in led:
            raise TableIncomplete(key, f"台账 {exp} 缺少 metric '{metric_key}'")
        if not close(value, led[metric_key]):
            raise GuardFailure(
                key,
                f"{exp}/{metric_key} 产物值 {value!r} 与台账值 {led[metric_key]!r} 不一致")
        self.checks_by_table.setdefault(key, []).append(
            {"check": "artifact==ledger", "experimentId": exp, "metricKey": metric_key,
             "artifactValue": value, "ledgerValue": led[metric_key], "passed": True})

    def cross_check_metrics(self, key: str, exp: str, metrics: dict):
        """Compare every shared metric key of a metrics.json against the ledger."""
        led = self.ledger_metrics(key, exp)
        compared = 0
        for name, value in metrics.items():
            if name not in led:
                continue
            if not close(value, led[name]):
                raise GuardFailure(
                    key, f"{exp}/{name} 产物值 {value!r} 与台账值 {led[name]!r} 不一致")
            compared += 1
        if compared == 0:
            raise TableIncomplete(key, f"{exp} 与台账没有可比对的 metric key")
        self.checks_by_table.setdefault(key, []).append(
            {"check": "metrics.json==ledger(all shared keys)", "experimentId": exp,
             "keysCompared": compared, "passed": True})
        return compared

    # ---- shared accessors
    def target_columns(self):
        if self._target_columns is None:
            mod = _load_target_columns()
            self._target_columns = mod
            missing = [t for t in mod.TARGET_COLS if t not in DIM_LABELS]
            if missing:
                raise SystemExit(f"DIM_LABELS 缺少维度中文名：{missing}")
            extra = [t for t in DIM_LABELS if t not in mod.TARGET_COLS]
            if extra:
                raise SystemExit(f"DIM_LABELS 存在多余维度：{extra}")
        return self._target_columns

    def manifest_plan(self, key: str, block: str) -> dict:
        plan = self._manifest["questions"][block].get("robustnessPlan")
        if not plan:
            raise TableIncomplete(key, f"evidence_manifest 的 {block} 缺少 robustnessPlan")
        return plan


# --------------------------------------------------------------------------- table specs
class Spec:
    def __init__(self, tid, key, title, builder):
        self.tid = tid          # short id == file stem, e.g. "q1-models"
        self.key = key          # "T1 q1-models"
        self.title = title
        self.builder = builder


# --------------------------------------------------------------------------- T1
def build_q1_models(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_m = "experiments/EXP-0073/metrics.json"
    rel_b = "experiments/EXP-0074/metrics.json"
    rel_g = "experiments/EXP-0073/inner_grid.json"
    m = ctx.json(k, rel_m)
    base = ctx.json(k, rel_b)
    grid = ctx.json(k, rel_g)
    ctx.cross_check_metrics(k, "EXP-0073", m)
    ctx.cross_check_metrics(k, "EXP-0074", base)

    ranks = sorted({cell["rank"] for rep in grid.values() for fold in rep.values()
                    for cell in fold["cells"] if cell.get("rank") is not None})
    if not ranks:
        raise TableIncomplete(k, f"{rel_g} 中没有非空 rank 网格")
    gammas = sorted({cell["gamma"] for rep in grid.values() for fold in rep.values()
                     for cell in fold["cells"]})
    lambdas = sorted({cell["lambda"] for rep in grid.values() for fold in rep.values()
                      for cell in fold["cells"]})

    suffixes = [
        ("最小中位数基线", "median", "逐目标训练中位数；无化学特征"),
        ("普通 Ridge", "ridge0", "无图惩罚（γ=0），无低秩项"),
        ("图 Ridge", "graph_ridge", "图惩罚（γ>0），无低秩项"),
        ("图正则低秩", "graph_lowrank", "图惩罚 + 低秩，秩内层选参"),
    ]
    af30, all50, macro, skill = {}, {}, {}, {}
    for _, suffix, _ in suffixes:
        af30[suffix] = ctx.metric(m, f"mae_{suffix}", k, rel_m)
        all50[suffix] = ctx.metric(m, f"mae_all50_{suffix}", k, rel_m)
        macro[suffix] = ctx.metric(m, f"macro_r2_af30_{suffix}", k, rel_m)
        skill[suffix] = ctx.metric(m, f"skill_af30_{suffix}", k, rel_m)

    # artifact-internal consistency: lowrank columns are the primary metric
    ctx.assert_ledger(k, "EXP-0073", "mae", af30["graph_lowrank"])
    ctx.assert_ledger(k, "EXP-0073", "mae_all50", all50["graph_lowrank"])
    ctx.assert_ledger(k, "EXP-0074", "mae", base["mae"])
    ctx.assert_ledger(k, "EXP-0074", "mae_all50", base["mae_all50"])
    for name, a, b in (("mae_median==EXP-0074.mae", af30["median"], base["mae"]),
                       ("mae_all50_median==EXP-0074.mae_all50", all50["median"], base["mae_all50"]),
                       ("macro_r2_af30_median==EXP-0074.macro_r2_af30", macro["median"], base["macro_r2_af30"])):
        if not close(a, b):
            raise GuardFailure(k, f"{name} 不一致：{a!r} vs {b!r}")
    if not close(m.get("mae_graph_lowrank"), m.get("mae")):
        raise GuardFailure(k, "mae_graph_lowrank 与主指标 mae 不一致")

    base_af30 = af30["median"]
    base_all50 = all50["median"]
    header = ["模型", "A/F30 等权 MAE", "全 50 维 MAE", "宏平均 R²（A/F30）",
              "Skill（A/F30）", "相对中位数差值（A/F30）", "相对中位数差值（全 50 维）"]
    rows, csv_rows = [], []
    for label, suffix, _desc in suffixes:
        rel_af = (af30[suffix] - base_af30) / base_af30
        rel_all = (all50[suffix] - base_all50) / base_all50
        rows.append([label, fnum(af30[suffix]), fnum(all50[suffix]), fnum(macro[suffix]),
                     fnum(skill[suffix]), fnum(rel_af), fnum(rel_all)])
        src = (f"{rel_m}#mae_{suffix},{rel_m}#mae_all50_{suffix},"
               f"{rel_m}#macro_r2_af30_{suffix},{rel_m}#skill_af30_{suffix}")
        if suffix == "median":
            src += f" | {rel_b}#mae,{rel_b}#mae_all50,{rel_b}#macro_r2_af30"
        csv_rows.append([label, af30[suffix], all50[suffix], macro[suffix], skill[suffix],
                         rel_af, rel_all, src])

    note = (
        "注：三次重复 × 三次外折的折外池化结果；A/F30 为香气 15 维与风味 15 维的等权平均，"
        "“全 50 维”另加其余 20 维。Skill（A/F30）= 1 − MAE / 中位数基线 MAE；"
        "相对中位数差值 =（本模型 MAE − 中位数基线 MAE）/ 中位数基线 MAE，负值表示优于基线。"
        f"普通 Ridge 固定无图惩罚（γ=0）且不含低秩项；图 Ridge 不含低秩项；"
        f"图正则低秩的秩在 {{{', '.join(str(r) for r in ranks)}}} 中由内层验证选参，"
        f"图惩罚强度 γ 与正则强度 λ 的选参网格为 γ∈{{{', '.join(_num_list(gammas))}}}、"
        f"λ∈{{{', '.join(_num_list(lambdas))}}}。"
        "本表只描述同一协议下的相对拟合差异，不构成对任一分量的显著性结论。"
    )
    fragment = md_table(header, rows, ["l"] + ["r"] * 6) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["模型", "af30_mae", "all50_mae", "macro_r2_af30", "skill_af30",
                       "rel_diff_af30", "rel_diff_all50", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"秩网格 {ranks}；γ 网格 {gammas}；λ 网格 {lambdas}"],
        "shape": "wide",
    }


def _num_list(values) -> list:
    out = []
    for v in values:
        out.append(f"{float(v):g}")
    return out


# --------------------------------------------------------------------------- T2
def build_q1_groups(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel = "experiments/EXP-0073/metrics.json"
    m = ctx.json(k, rel)
    ctx.cross_check_metrics(k, "EXP-0073", m)

    group_labels = [("Aroma15", "香气 15 维（指标组）"), ("Flavour15", "风味 15 维（指标组）"),
                    ("Other20", "其余 20 维（指标组）")]

    header = ["对象", "口径", "MAE", "样本数", "同折中位数基线 MAE"]
    rows, csv_rows = [], []
    total_n = 0.0
    total_group_mae_num = 0.0
    for raw, label in group_labels:
        mae = ctx.metric(m, f"per_group__{raw}__mae", k, rel)
        n = ctx.metric(m, f"per_group__{raw}__n", k, rel)
        total_n += float(n)
        total_group_mae_num += float(mae) * float(n)
        rows.append([label, "指标组", fnum(mae), fint(n), "—"])
        csv_rows.append([label, "group", mae, n, None, f"{rel}#per_group__{raw}__mae,{rel}#per_group__{raw}__n"])
    n_targets = ctx.metric(m, "n_targets_all50", k, rel)
    if int(total_n) != int(n_targets):
        raise GuardFailure(k, f"三组维数之和 {total_n} 与全 50 维目标数 {n_targets} 不一致")
    if not close(total_group_mae_num / total_n, ctx.metric(m, "mae_all50", k, rel), rel_tol=1e-9):
        raise GuardFailure(k, "三组 MAE 的维数加权平均与全 50 维主指标不一致")

    fold_keys = sorted(key[len("per_fold__"):-len("__mae")] for key in m
                       if key.startswith("per_fold__") and key.endswith("__mae"))
    if len(fold_keys) != 9:
        raise TableIncomplete(k, f"{rel} 期望 9 个 per_fold__*__mae，实得 {len(fold_keys)}")
    fold_rows = []
    for fk in fold_keys:
        rep = int(fk[1])
        fld = int(fk[3])
        mae = ctx.metric(m, f"per_fold__{fk}__mae", k, rel)
        med = ctx.metric(m, f"per_fold__{fk}__mae_median", k, rel)
        nrows = ctx.metric(m, f"per_fold__{fk}__n_rows", k, rel)
        fold_rows.append((mae, nrows, fld, rep, med, fk))
    fold_rows.sort(key=lambda r: (r[3], r[2]))
    n_rows = ctx.metric(m, "n_rows", k, rel)
    if not close(sum(float(r[1]) for r in fold_rows), float(n_rows)):
        raise GuardFailure(k, "9 个折外行数之和与 n_rows 不一致")
    for mae, nrows, fld, rep, med, fk in fold_rows:
        label = f"第 {rep + 1} 次重复 · 第 {fld + 1} 折"
        rows.append([label, "折外分段", fnum(mae), fint(nrows), fnum(med)])
        csv_rows.append([label, "fold", mae, nrows, med,
                         f"{rel}#per_fold__{fk}__mae,{rel}#per_fold__{fk}__n_rows,"
                         f"{rel}#per_fold__{fk}__mae_median"])

    note = (
        "注：上三行为三个指标组的折外池化 MAE 与组内维数；下九行为三次重复 × 三次外折逐折的折外 MAE、"
        "折内行数与同一折的中位数基线 MAE，用于展示折间波动而非模型间比较。"
        "逐折行数不同是因为外折按风格分层切分。"
    )
    fragment = md_table(header, rows, ["l", "l", "r", "r", "r"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["对象", "口径", "mae", "n", "mae_median_same_fold", "_source"],
        "csv_rows": csv_rows,
        "notes": ["9 个 per_fold 行数之和 = n_rows = 750"],
        "shape": "wide",
    }


# --------------------------------------------------------------------------- T3
def build_q1_styles(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel = "experiments/EXP-0073/metrics.json"
    m = ctx.json(k, rel)
    ctx.cross_check_metrics(k, "EXP-0073", m)

    styles = sorted(key[len("per_style__"):-len("__mae")] for key in m
                    if key.startswith("per_style__") and key.endswith("__mae"))
    if not styles:
        raise TableIncomplete(k, f"{rel} 没有 per_style__*__mae")
    tc = ctx.target_columns()
    by_norm = {_norm(name): name for name in tc.STYLE_COUNTS}
    labels = {}
    for s in styles:
        if _norm(s) not in by_norm:
            raise TableIncomplete(k, f"风格 '{s}' 无法映射到 data clean 中的可读名")
        labels[s] = by_norm[_norm(s)]
    n_repeats = int(ctx.metric(m, "n_repeats", k, rel))
    n_rows = float(ctx.metric(m, "n_rows", k, rel))

    records = []
    for s in styles:
        mae = ctx.metric(m, f"per_style__{s}__mae", k, rel)
        n = float(ctx.metric(m, f"per_style__{s}__n", k, rel))
        beers = n / n_repeats
        if abs(beers - round(beers)) > 1e-9:
            raise GuardFailure(k, f"风格 {labels[s]} 的折外行数 {n} 不能被重复次数 {n_repeats} 整除")
        beers = int(round(beers))
        expected = int(tc.STYLE_COUNTS[labels[s]])
        if beers != expected:
            raise GuardFailure(k, f"风格 {labels[s]} 的啤酒数 {beers} 与常量表 {expected} 不一致")
        records.append((beers, labels[s], mae, n, s))
    records.sort(key=lambda r: (r[0], r[1]))
    if not close(sum(r[3] for r in records), n_rows):
        raise GuardFailure(k, f"逐风格折外行数之和与 n_rows={n_rows} 不一致")

    header = ["风格", "MAE", "啤酒数", "折外行数", "备注"]
    rows, csv_rows = [], []
    for beers, label, mae, n, raw in records:
        flag = "小样本（≤5 款）" if beers <= 5 else ""
        rows.append([label, fnum(mae), int(beers), fint(n), flag])
        csv_rows.append([label, mae, int(beers), n, flag,
                         f"{rel}#per_style__{raw}__mae,{rel}#per_style__{raw}__n"])
    n_small = sum(1 for r in records if r[0] <= 5)
    note = (
        "注：按啤酒数升序排列（小样本风格在前）；折外行数 = 风格内啤酒数 × 重复次数。"
        f"共 {len(records)} 个风格，其中 {n_small} 个风格的折外样本不超过 5 款啤酒，"
        "其 MAE 受个别样本影响很大，不能与其他风格等量比较；Brut 等小样本风格只作描述。"
    )
    fragment = md_table(header, rows, ["l", "r", "r", "r", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["风格", "mae", "beers", "oof_rows", "remark", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"风格数 {len(records)}，折外行数合计 {n_rows}"],
        "shape": "wide",
    }


# --------------------------------------------------------------------------- T4
def build_q1_targets(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_oof = "experiments/EXP-0073/oof_long.csv"
    rel_wide = "experiments/EXP-0073/predictions_all_models.csv"
    rel_m = "experiments/EXP-0073/metrics.json"
    tc = ctx.target_columns()
    m = ctx.json(k, rel_m)
    ctx.cross_check_metrics(k, "EXP-0073", m)

    oof = ctx.frame(k, rel_oof)
    for col in ("beer", "repeat", "target", "model", "y_true", "y_pred"):
        if col not in oof.columns:
            raise TableIncomplete(k, f"{rel_oof} 缺少列 '{col}'")
    cand_name = "graph-lowrank"
    med_name = "median"
    if cand_name not in set(oof["model"].unique()) or med_name not in set(oof["model"].unique()):
        raise TableIncomplete(k, f"{rel_oof} 缺少模型 {cand_name}/{med_name}")

    cand = oof[oof["model"] == cand_name].copy()
    med = oof[oof["model"] == med_name].copy()
    cand["ae"] = (cand["y_pred"] - cand["y_true"]).abs()
    med["ae"] = (med["y_pred"] - med["y_true"]).abs()

    targets = list(tc.TARGET_COLS)
    af30 = targets[:30]
    if len(af30) != 30:
        raise TableIncomplete(k, "目标列常量不足 30 个 A/F 维度")
    if set(cand["target"].unique()) != set(targets):
        raise TableIncomplete(k, f"{rel_oof} 的目标集合与常量 TARGET_COLS 不一致")

    per_t = cand.groupby("target")["ae"].mean()
    per_t_med = med.groupby("target")["ae"].mean()
    n_t = cand.groupby("target")["ae"].size()

    cand_af30 = float(cand.loc[cand["target"].isin(af30), "ae"].mean())
    med_af30 = float(med.loc[med["target"].isin(af30), "ae"].mean())
    cand_all50 = float(cand["ae"].mean())
    if not close(cand_af30, ctx.metric(m, "mae", k, rel_m), rel_tol=1e-12):
        raise GuardFailure(k, f"重算 A/F30 MAE {cand_af30!r} 与 metrics.mae 不一致")
    if not close(med_af30, ctx.metric(m, "mae_median", k, rel_m), rel_tol=1e-12):
        raise GuardFailure(k, f"重算中位数基线 MAE {med_af30!r} 与 metrics.mae_median 不一致")
    if not close(cand_all50, ctx.metric(m, "mae_all50", k, rel_m), rel_tol=1e-12):
        raise GuardFailure(k, f"重算全 50 维 MAE {cand_all50!r} 与 metrics.mae_all50 不一致")
    ctx.assert_ledger(k, "EXP-0073", "mae", cand_af30)
    ctx.assert_ledger(k, "EXP-0073", "mae_median", med_af30)
    ctx.assert_ledger(k, "EXP-0073", "mae_all50", cand_all50)

    # align with the wide prediction table (independent of oof_long's long layout)
    wide = ctx.frame(k, rel_wide)
    if "model" not in wide.columns:
        raise TableIncomplete(k, f"{rel_wide} 缺少列 'model'")
    gw = wide[wide["model"] == cand_name]
    max_align = 0.0
    for t in targets:
        pc, tc_ = f"y_pred__{t}", f"y_true__{t}"
        if pc not in wide.columns or tc_ not in wide.columns:
            raise TableIncomplete(k, f"{rel_wide} 缺少列 '{pc}' 或 '{tc_}'")
        v = float((gw[pc] - gw[tc_]).abs().mean())
        max_align = max(max_align, abs(v - float(per_t[t])))
    if max_align > 1e-9:
        raise GuardFailure(k, f"折外长表与宽表逐维 MAE 最大差 {max_align} 超过 1e-9（对齐失败）")

    records = []
    for t in af30:
        c_val, m_val = float(per_t[t]), float(per_t_med[t])
        records.append((1.0 - c_val / m_val, t, c_val, m_val, int(n_t[t])))
    records.sort(key=lambda r: (r[0], r[1]))
    improve = sum(1 for r in records if r[2] < r[3])
    worse = len(records) - improve

    header = ["指标", "候选 MAE", "中位数基线 MAE", "差值（候选 − 基线）", "Skill", "折外样本数"]
    rows, csv_rows = [], []
    for skill, t, c_val, m_val, n in records:
        rows.append([DIM_LABELS[t], fnum(c_val), fnum(m_val), fnum(c_val - m_val), fnum(skill), n])
        csv_rows.append([t, DIM_LABELS[t], c_val, m_val, c_val - m_val, skill, n,
                         f"{rel_oof}#(model={cand_name})abs(y_pred-y_true);{rel_oof}#(model={med_name})abs(y_pred-y_true)"])
    note = (
        "注：逐维 MAE 由折外明细按（重复, 啤酒, 指标）重算后池化，候选与中位数基线使用同一批折外行；"
        "Skill = 1 − 候选 MAE / 中位数基线 MAE。按 Skill 升序排列，最上方为相对基线恶化最多的维度；"
        f"本协议下 30 维中 {improve} 维优于基线、{worse} 维劣于基线。"
        f"折外长表与宽表逐维 MAE 的最大对齐差为 {fnum(max_align)}。"
    )
    fragment = md_table(header, rows, ["l", "r", "r", "r", "r", "r"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["指标键", "指标", "candidate_mae", "median_mae", "diff",
                       "skill", "n", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"改善 {improve} 维 / 恶化 {worse} 维；宽表对齐最大差 {max_align:.3e}"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- T5
def build_q1_grades(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel = "experiments/EXP-0073/outputs.json"
    rel_m = "experiments/EXP-0073/metrics.json"
    out = ctx.json(k, rel)
    ctx.json(k, rel_m)
    try:
        grade = out["q1"]["grade"]
        per_model = grade["perModel"]
    except KeyError as exc:
        raise TableIncomplete(k, f"{rel} 缺少 q1.grade.perModel（{exc}）") from exc
    if not per_model:
        raise TableIncomplete(k, f"{rel} 的 q1.grade.perModel 为空")

    order = [("graph-lowrank", "图正则低秩"), ("graph-ridge", "图 Ridge"),
             ("ridge", "普通 Ridge"), ("median", "最小中位数基线")]
    present = set(per_model)
    for raw, _ in order:
        if raw not in present:
            raise TableIncomplete(k, f"{rel} 缺少 grade.perModel['{raw}']")

    counts_ref = None
    n_cells = None
    header = ["模型", "等级 MAE", "整级一致率", "二次加权 κ",
              "等级 0", "等级 1", "等级 2", "等级 3", "等级 4", "等级 5", "等级 6"]
    rows, csv_rows = [], []
    for raw, label in order:
        rec = per_model[raw]
        for field in ("grade_mae", "exact_agreement", "qwk", "grade_counts_predicted",
                      "grade_counts_reference", "n_grade_cells"):
            if field not in rec:
                raise TableIncomplete(k, f"{rel} q1.grade.perModel['{raw}'] 缺少 '{field}'")
        counts = list(rec["grade_counts_predicted"])
        if len(counts) != 7:
            raise TableIncomplete(k, f"{rel} 预测等级计数长度 {len(counts)} ≠ 7")
        if counts_ref is None:
            counts_ref = list(rec["grade_counts_reference"])
            n_cells = rec["n_grade_cells"]
        elif list(rec["grade_counts_reference"]) != counts_ref:
            raise GuardFailure(k, "各模型的参照等级分布不一致")
        if rec["n_grade_cells"] != n_cells:
            raise GuardFailure(k, "各模型的等级格数不一致")
        if sum(counts) != sum(counts_ref):
            raise GuardFailure(k, f"{label} 的预测等级计数总和与参照不一致")
        rows.append([label, fnum(rec["grade_mae"]), fnum(rec["exact_agreement"]),
                     fnum(rec["qwk"])] + [fint(c) for c in counts])
        csv_rows.append([label, rec["grade_mae"], rec["exact_agreement"], rec["qwk"],
                         *counts, f"{rel}#q1.grade.perModel.{raw}"])
    rows.append(["参照等级（真实标签同映射）", "—", "—", "—"] + [fint(c) for c in counts_ref])
    csv_rows.append(["参照等级（真实标签同映射）", None, None, None, *counts_ref,
                     f"{rel}#q1.grade.perModel.*.grade_counts_reference"])

    metrics_q1 = ctx.json(k, rel_m)
    ctx.cross_check_metrics(k, "EXP-0073", metrics_q1)
    rows_n = int(ctx.metric(metrics_q1, "n_rows", k, rel_m))
    dims_n = int(ctx.metric(metrics_q1, "n_targets_all50", k, rel_m))
    if rows_n * dims_n != int(n_cells):
        raise GuardFailure(k, f"等级格数 {int(n_cells)} ≠ 行数 {rows_n} × 维数 {dims_n}")

    note = (
        "注：等级为训练折内经验中点分布映射出的 0–6 相对强度等级，参照等级是真实标准化标签经同一映射得到的等级；"
        "本表衡量的是相对等级的一致性，不是恢复人工感官评分，也不代表等级 0/6 对应原始评分卡的 0/6 分。"
        f"二次加权 κ 与整级一致率均在 {int(n_cells)} 个等级格（{int(rows_n)} 行 × {int(dims_n)} 维）上计算；"
        "最小中位数基线的预测恒为中间等级，"
        "其等级分布只有一档，因此 κ 为 0。预测等级向中间收缩，说明离散等级仍有改善空间。"
    )
    fragment = md_table(header, rows, ["l"] + ["r"] * 10) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["模型", "grade_mae", "exact_agreement", "qwk",
                       "grade0", "grade1", "grade2", "grade3", "grade4", "grade5", "grade6",
                       "_source"],
        "csv_rows": csv_rows,
        "notes": [f"等级格数 {n_cells}"],
        "shape": "wide",
    }


# --------------------------------------------------------------------------- T6 / T7
def _build_q1_core_grades(ctx: Ctx, spec: Spec, dims, dim_prefix: str) -> dict:
    k = spec.key
    rel = "experiments/EXP-0073/oof_long.csv"
    oof = ctx.frame(k, rel)
    for col in ("beer", "repeat", "target", "model", "grade_pred", "grade_true"):
        if col not in oof.columns:
            raise TableIncomplete(k, f"{rel} 缺少列 '{col}'")
    cand = oof[oof["model"] == "graph-lowrank"]
    if cand.empty:
        raise TableIncomplete(k, f"{rel} 中没有候选模型的折外记录")
    rep = int(cand["repeat"].min())
    part = cand[cand["repeat"] == rep]
    beers = sorted(int(b) for b in part["beer"].unique())[:10]
    if len(beers) != 10:
        raise TableIncomplete(k, f"{rel} 中啤酒数不足 10，实得 {len(beers)}")
    for d in dims:
        if d not in set(part["target"].unique()):
            raise TableIncomplete(k, f"{rel} 缺少维度 '{d}'")

    rel_out = "experiments/EXP-0073/outputs.json"
    grade_out = ctx.json(k, rel_out)
    try:
        grade_mae_out = grade_out["q1"]["grade"]["perModel"]["graph-lowrank"]["grade_mae"]
    except KeyError as exc:
        raise TableIncomplete(k, f"{rel_out} 缺少 q1.grade.perModel['graph-lowrank']['grade_mae']（{exc}）") from exc
    grade_mae_local = float((cand["grade_pred"] - cand["grade_true"]).abs().mean())
    if not close(grade_mae_local, grade_mae_out, rel_tol=1e-9):
        raise GuardFailure(
            k, f"折外明细重算的等级 MAE {grade_mae_local!r} 与等级产物 {grade_mae_out!r} 不一致")

    sub = part[part["beer"].isin(beers) & part["target"].isin(dims)]
    if len(sub) != len(beers) * len(dims):
        raise TableIncomplete(
            k, f"{rel} 的 (啤酒, 维度) 组合数 {len(sub)} ≠ {len(beers) * len(dims)}（存在重复或缺行）")
    pred = sub.pivot(index="beer", columns="target", values="grade_pred")
    true = sub.pivot(index="beer", columns="target", values="grade_true")
    for frame, name in ((pred, "grade_pred"), (true, "grade_true")):
        if frame.isna().any().any():
            raise TableIncomplete(k, f"{rel} 的 {name} 存在缺失格")

    header = ["样本"] + [f"{DIM_LABELS[d]}·预测" for d in dims] + [f"{DIM_LABELS[d]}·参照" for d in dims]
    rows, csv_rows = [], []
    for i, beer in enumerate(beers, start=1):
        p = [int(pred.loc[beer, d]) for d in dims]
        t = [int(true.loc[beer, d]) for d in dims]
        rows.append([f"Beer#{i}"] + p + t)
        csv_rows.append([f"Beer#{i}", int(beer), rep] + p + t +
                        [f"{rel}#(beer={beer},repeat={rep})grade_pred,grade_true"])
    note = (
        "注：等级为训练折内经验分布映射得到的 0–6 相对强度等级，预测列为折外预测、参照列为真实标签经同一映射的等级；"
        "样本编号与题面评分卡的 Beer# 对齐（第 n 号样本即 beer_n 评分卡对应的啤酒）；"
        f"表内为{('首轮重复' if rep == 0 else f'第 {rep + 1} 次重复')}的折外结果，五维为核心{DIM_CORE_NOTE[dim_prefix]}；"
        "等级是相对强度，不是人工评分恢复，也不表示风味存在与否。"
    )
    fragment = md_table(header, rows, ["l"] + ["r"] * 10) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["样本", "beer_id", "repeat_index"] + [f"pred_{d}" for d in dims] +
                      [f"ref_{d}" for d in dims] + ["_source"],
        "csv_rows": csv_rows,
        "notes": [f"重复序号 {rep}，十个样本 beer_id={beers}"],
        "shape": "wide",
    }


DIM_CORE_NOTE = {"A": "香气维度（麦芽总体、酒花总体、柑橘、酯香总体、乙酸异戊酯）",
                 "F": "风味维度（麦芽总体、酒花总体、柑橘、酯香总体、乙酸异戊酯）"}


def build_q1_scores_aroma(ctx: Ctx, spec: Spec) -> dict:
    return _build_q1_core_grades(ctx, spec, CORE_A5, "A")


def build_q1_scores_flavour(ctx: Ctx, spec: Spec) -> dict:
    return _build_q1_core_grades(ctx, spec, CORE_F5, "F")


# --------------------------------------------------------------------------- T8
def build_q2_universe(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_cs = "experiments/EXP-0107/candidate_scores.csv"
    rel_out = "experiments/EXP-0107/outputs.json"
    rel_m = "experiments/EXP-0107/metrics.json"
    cs = ctx.frame(k, rel_cs)
    out = ctx.json(k, rel_out)
    m = ctx.json(k, rel_m)
    ctx.cross_check_metrics(k, "EXP-0107", m)
    for col in ("dimension", "compound", "kind"):
        if col not in cs.columns:
            raise TableIncomplete(k, f"{rel_cs} 缺少列 '{col}'")
    try:
        counts = out["q2"]["category_counts"]
    except KeyError as exc:
        raise TableIncomplete(k, f"{rel_out} 缺少 q2.category_counts（{exc}）") from exc

    universe = cs[["compound", "kind"]].drop_duplicates()
    if universe["compound"].duplicated().any():
        raise GuardFailure(k, "同一化合物在候选表中出现多个类别")
    observed = universe.groupby("kind").size().to_dict()
    for kind in ("single_compound", "element_or_index", "physical_parameter", "derived_sum"):
        if kind not in observed:
            raise TableIncomplete(k, f"{rel_cs} 中缺少类别 '{kind}'")
        if int(observed[kind]) != int(counts.get(kind, -1)):
            raise GuardFailure(
                k, f"候选表类别 {kind} 计数 {observed[kind]} 与 outputs.json {counts.get(kind)} 不一致")
    total = int(sum(observed.values()))
    if total != int(counts.get("strictSize", -1)) + int(counts.get("element_or_index", 0)) + \
            int(counts.get("physical_parameter", 0)) + int(counts.get("derived_sum", 0)):
        raise GuardFailure(k, "候选类别计数之和与合计不一致")
    if int(ctx.metric(m, "n_strict_candidates", k, rel_m)) != int(observed["single_compound"]):
        raise GuardFailure(k, "严格榜候选数与 metrics.n_strict_candidates 不一致")
    ext_total = int(observed["element_or_index"]) + int(observed["physical_parameter"]) + \
        int(observed["derived_sum"])
    if int(ctx.metric(m, "n_extended_candidates", k, rel_m)) != ext_total:
        raise GuardFailure(k, "扩展榜候选数与 metrics.n_extended_candidates 不一致")
    n_dim = int(cs["dimension"].nunique())
    if len(cs) != total * n_dim:
        raise GuardFailure(k, f"候选矩阵行数 {len(cs)} ≠ 候选数 {total} × 维度数 {n_dim}")

    desc = {
        "single_compound": ("严格榜唯一允许的宇宙：参与 50 维 Top-3 选择", "是", "否"),
        "element_or_index": ("元素/指数项，非单体化合物，移出严格榜", "否", "是"),
        "physical_parameter": ("理化参数，非化合物丰度，只进扩展榜", "否", "是"),
        "derived_sum": ("派生汇总量，不是独立化合物，只进扩展榜", "否", "是"),
    }
    header = ["类别", "候选数", "进入严格榜", "进入扩展榜", "说明"]
    rows, csv_rows = [], []
    for kind in ("single_compound", "element_or_index", "physical_parameter", "derived_sum"):
        n = int(observed[kind])
        note_txt, inbox, inext = desc[kind]
        rows.append([KIND_LABELS[kind], n, inbox, inext, note_txt])
        csv_rows.append([KIND_LABELS[kind], kind, n, inbox, inext, note_txt,
                         f"{rel_cs}#kind(distinct compounds);{rel_out}#q2.category_counts.{kind}"])
    rows.append(["合计", total, "—", "—", f"候选矩阵为 {total} 个候选 × {n_dim} 个维度"])
    csv_rows.append(["合计", "total", total, "—", "—", f"候选矩阵 {total}×{n_dim}",
                     f"{rel_cs}#compounds"])
    note = (
        "注：严格榜只允许单体化合物，元素/指数、理化参数与派生和另一张扩展榜单独报告，"
        "两张表不得混排；同一化合物在不同维度上的候选一致。"
        f"候选矩阵共 {total} 个候选 × {n_dim} 个维度 = {len(cs)} 个候选-维度单元。"
    )
    fragment = md_table(header, rows, ["l", "r", "l", "l", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["类别", "kind", "n", "strict_table", "extended_table", "remark", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"类别计数 {observed}；维度数 {n_dim}"],
        "shape": "wide",
    }


# --------------------------------------------------------------------------- T9-T11 helpers
def _style_type(rho_total: float, rho_within: float) -> str:
    """Style-confound class from src/q2_lib.py: 内 / 风 / 混."""
    at, aw = abs(float(rho_total)), abs(float(rho_within))
    if aw >= 0.8 * at:
        return "内"
    if at >= 0.25 and aw < 0.5 * at:
        return "风"
    return "混"


def _q2_top3_frame(ctx: Ctx, key: str, rel: str, cs, dims=None):
    frame = ctx.frame(key, rel)
    needed = ("dimension", "rank", "compound", "kind", "score", "pi", "direction", "alternative_rank4")
    for col in needed:
        if col not in frame.columns:
            raise TableIncomplete(key, f"{rel} 缺少列 '{col}'")
    if dims is not None:
        missing = [d for d in dims if d not in set(frame["dimension"])]
        if missing:
            raise TableIncomplete(key, f"{rel} 缺少维度 {missing}")
        frame = frame[frame["dimension"].isin(dims)].copy()
    rho = cs.set_index(["dimension", "compound"])
    types, dirs = [], []
    for dim, compound, direction in zip(frame["dimension"], frame["compound"], frame["direction"]):
        if (dim, compound) not in rho.index:
            raise TableIncomplete(key, f"候选表缺少 ({dim}, {compound}) 的相关系数")
        row = rho.loc[(dim, compound)]
        types.append(_style_type(row["rho_total"], row["rho_within"]))
        dirs.append("+" if str(direction).lower().startswith("pos") else "−")
    frame["type"] = types
    frame["dir"] = dirs
    frame = frame.sort_values(["dimension", "rank"], key=lambda s: s.map(
        {d: i for i, d in enumerate(dims)}) if s.name == "dimension" else s)
    return frame


def _alt_text(value, compound) -> str:
    if value is None:
        return "—（无）"
    text = str(value).strip()
    if text == "" or text.lower() in ("none", "null", "nan"):
        return "—（无）"
    if text == str(compound):
        return "—（无同模块替代）"
    return text


# --------------------------------------------------------------------------- T9
def build_q2_core_top3(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_cs = "experiments/EXP-0107/candidate_scores.csv"
    rel_t3 = "experiments/EXP-0107/strict_top3.csv"
    cs = ctx.frame(k, rel_cs)
    tc = ctx.target_columns()
    aroma15 = [t for t in tc.TARGET_COLS if t.startswith("A_")]
    if len(aroma15) != 15:
        raise TableIncomplete(k, f"目标常量中香气维度数 {len(aroma15)} ≠ 15")
    dims = aroma15 + CORE_F5
    if len(dims) != 20:
        raise TableIncomplete(k, f"核心维度数 {len(dims)} ≠ 20")
    frame = _q2_top3_frame(ctx, k, rel_t3, cs, dims)

    header = ["感官维度", "第 1 位", "第 2 位", "第 3 位", "第 3 位同模块替代候选"]
    rows, csv_rows = [], []
    for dim in dims:
        part = frame[frame["dimension"] == dim].sort_values("rank")
        if len(part) != 3:
            raise TableIncomplete(k, f"维度 {DIM_LABELS[dim]} 的 Top-3 条目数为 {len(part)} ≠ 3")
        cells = []
        for _, rec in part.iterrows():
            cells.append(f"{rec['compound']}｜{fnum(rec['pi'], 3)}/{fnum(rec['score'])}｜{rec['dir']}·{rec['type']}")
        third = part.iloc[2]
        rows.append([DIM_LABELS[dim]] + cells + [_alt_text(third["alternative_rank4"], third["compound"])])
        for _, rec in part.iterrows():
            csv_rows.append([dim, DIM_LABELS[dim], int(rec["rank"]), rec["compound"], rec["kind"],
                             rec["pi"], rec["score"], rec["dir"], rec["type"],
                             _alt_text(rec["alternative_rank4"], rec["compound"]), rec["alternative_rank4"],
                             f"{rel_t3}#dimension={dim},rank={rec['rank']} | {rel_cs}#(dimension,compound)rho_total,rho_within"])
    note = (
        "注：单元格格式为“名称｜π/S｜方向·类型”。π 为 500 次风格内分层 bootstrap 的入选频率，"
        "S 为四种方法在维度内百分位排名的共识分；方向为总体 Spearman 相关的符号；"
        "类型按原脚本口径判定——“内”表示 |风格内相关| ≥ 0.8|总体相关|，“风”表示未满足前者且 "
        "|总体相关| ≥ 0.25、|风格内相关| < 0.5|总体相关|，其余为“混”。"
        "维度取香气 15 维全部与风味 5 个核心维度；完整 50 维见附录长表。"
        "最后一列为第 3 位候选的同模块替代项：第 3 位入选频率偏低或符号混杂时，用它说明名次的不确定性；"
        "“无”表示该参考模块内没有其他可替代候选。"
    )
    fragment = md_table(header, rows, ["l", "l", "l", "l", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["维度键", "感官维度", "位次", "化合物", "类别", "pi", "score", "方向", "类型",
                       "同模块替代候选", "alternative_rank4_raw", "_source"],
        "csv_rows": csv_rows,
        "notes": ["md 为横向排版，csv 为等价的逐条目长表（20 维 × 3 位 = 60 行）"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- T10
def build_q2_full_top3(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_cs = "experiments/EXP-0107/candidate_scores.csv"
    rel_t3 = "experiments/EXP-0107/strict_top3.csv"
    cs = ctx.frame(k, rel_cs)
    tc = ctx.target_columns()
    dims = list(tc.TARGET_COLS)
    frame = _q2_top3_frame(ctx, k, rel_t3, cs, dims)
    if len(frame) != len(dims) * 3:
        raise TableIncomplete(k, f"完整 Top-3 条目数 {len(frame)} ≠ {len(dims) * 3}")
    kinds = set(frame["kind"].unique())
    if kinds != {"single_compound"}:
        raise GuardFailure(k, f"严格榜出现非单体类别：{sorted(kinds)}")

    header = ["感官维度", "位次", "化合物", "类别", "π", "S", "方向", "类型", "同模块替代候选"]
    rows, csv_rows = [], []
    for dim in dims:
        part = frame[frame["dimension"] == dim].sort_values("rank")
        for _, rec in part.iterrows():
            alt = _alt_text(rec["alternative_rank4"], rec["compound"])
            rows.append([DIM_LABELS[dim], int(rec["rank"]), rec["compound"], KIND_LABELS[rec["kind"]],
                         fnum(rec["pi"], 3), fnum(rec["score"]), rec["dir"], rec["type"], alt])
            csv_rows.append([dim, DIM_LABELS[dim], int(rec["rank"]), rec["compound"], rec["kind"],
                             rec["pi"], rec["score"], rec["dir"], rec["type"], alt,
                             rec["alternative_rank4"],
                             f"{rel_t3}#dimension={dim},rank={rec['rank']} | {rel_cs}#(dimension,compound)"])
    note = (
        "注：附录长表，覆盖全部 50 个感官维度、每维 3 个条目。列定义与核心维表一致："
        "π 为 bootstrap 入选频率，S 为方法内百分位共识分，方向为总体 Spearman 符号，"
        "类型为“内/风/混”的风格混杂分类，最后一列为第 3 位的同模块替代候选。"
        "严格榜只含单体化合物；元素/指数、理化参数与派生和见扩展榜。"
    )
    fragment = md_table(header, rows, ["l", "r", "l", "l", "r", "r", "l", "l", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["维度键", "感官维度", "位次", "化合物", "类别", "pi", "score", "方向", "类型",
                       "同模块替代候选", "alternative_rank4_raw", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"{len(dims)} 维 × 3 = {len(frame)} 条目"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- T11
def build_q2_extended(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_cs = "experiments/EXP-0107/candidate_scores.csv"
    rel_t3 = "experiments/EXP-0107/extended_top3.csv"
    rel_m = "experiments/EXP-0107/metrics.json"
    cs = ctx.frame(k, rel_cs)
    frame = ctx.frame(k, rel_t3)
    m = ctx.json(k, rel_m)
    for col in ("dimension", "rank", "compound", "kind", "score", "pi", "direction", "alternative_rank4"):
        if col not in frame.columns:
            raise TableIncomplete(k, f"{rel_t3} 缺少列 '{col}'")
    tc = ctx.target_columns()
    dims = list(tc.TARGET_COLS)
    missing = [d for d in dims if d not in set(frame["dimension"])]
    if missing:
        raise TableIncomplete(k, f"{rel_t3} 缺少维度 {missing}")
    if len(frame) != len(dims) * 3:
        raise TableIncomplete(k, f"扩展榜条目数 {len(frame)} ≠ {len(dims) * 3}")
    universe = sorted(set(frame["compound"]))
    n_ext = int(ctx.metric(m, "n_extended_candidates", k, rel_m))
    if len(universe) != n_ext:
        raise GuardFailure(k, f"扩展榜候选数 {len(universe)} 与 metrics.n_extended_candidates={n_ext} 不一致")
    kinds = set(frame["kind"].unique())
    if "single_compound" in kinds:
        raise GuardFailure(k, "扩展榜混入了单体化合物")
    if not kinds <= {"element_or_index", "physical_parameter", "derived_sum"}:
        raise GuardFailure(k, f"扩展榜出现未知类别 {sorted(kinds)}")
    rho = cs.set_index(["dimension", "compound"])

    header = ["感官维度", "位次", "化合物", "类别", "π", "S", "方向", "类型", "同模块替代候选"]
    rows, csv_rows = [], []
    for dim in dims:
        part = frame[frame["dimension"] == dim].sort_values("rank")
        if len(part) != 3:
            raise TableIncomplete(k, f"维度 {DIM_LABELS[dim]} 的扩展榜条目数为 {len(part)} ≠ 3")
        for _, rec in part.iterrows():
            if (dim, rec["compound"]) not in rho.index:
                raise TableIncomplete(k, f"候选表缺少 ({dim}, {rec['compound']}) 的相关系数")
            row = rho.loc[(dim, rec["compound"])]
            typ = _style_type(row["rho_total"], row["rho_within"])
            direction = "+" if str(rec["direction"]).lower().startswith("pos") else "−"
            alt = _alt_text(rec["alternative_rank4"], rec["compound"])
            label = DIM_LABELS[dim]
            rows.append([label, int(rec["rank"]), rec["compound"], KIND_LABELS[rec["kind"]],
                         fnum(rec["pi"], 3), fnum(rec["score"]), direction, typ, alt])
            csv_rows.append([dim, label, int(rec["rank"]), rec["compound"], rec["kind"],
                             rec["pi"], rec["score"], direction, typ, alt, rec["alternative_rank4"],
                             f"{rel_t3}#dimension={dim},rank={rec['rank']} | {rel_cs}#(dimension,compound)"])
    note = (
        f"注：扩展榜的候选宇宙只有 {len(universe)} 个非单体指标（元素/指数、理化参数与派生和），"
        "每个感官维度在这 15 个指标中取前 3，因此本表与严格单体榜的候选集合完全不同，"
        "两张表必须分表报告、不得混排。π、S、方向与类型的口径同核心维表；"
        "这些指标本身是可测量量或派生量，入选只能读作同期关联，不能当作化合物作用机理，"
        "也不能用它们替代严格榜。"
    )
    fragment = md_table(header, rows, ["l", "r", "l", "l", "r", "r", "l", "l", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["维度键", "感官维度", "位次", "化合物", "类别", "pi", "score", "方向", "类型",
                       "同模块替代候选", "alternative_rank4_raw", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"{len(dims)} 维 × 3 = {len(frame)} 条目；候选宇宙 {len(universe)} 个扩展指标"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- T12
def build_q2_stability(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_m = "experiments/EXP-0107/metrics.json"
    rel_o = "experiments/EXP-0107/outputs.json"
    m = ctx.json(k, rel_m)
    out = ctx.json(k, rel_o)
    ctx.cross_check_metrics(k, "EXP-0107", m)

    # ROB-0015 = reference block EXP-0125 (post-registration repeat-0 rerun) + EXP-0126.
    # Two executed blocks; the ledger records the method as param-perturbation (perturbed
    # object = frozen seed block). The repeat-2 block EXP-0131 was executed AFTER the plan
    # was registered and is reported as a supplementary block, never merged into the plan
    # values, spread or decision.
    rob_exps = ["EXP-0125", "EXP-0126"]
    supp_exp = "EXP-0131"
    rob_metrics = {}
    for exp in rob_exps + [supp_exp]:
        rel = f"experiments/{exp}/metrics.json"
        rob_metrics[exp] = ctx.json(k, rel)
        ctx.cross_check_metrics(k, exp, rob_metrics[exp])
        ctx.assert_ledger(k, exp, "topk-jaccard", rob_metrics[exp]["topk-jaccard"])

    main = ctx.metric(m, "topk-jaccard", k, rel_m)
    ctx.assert_ledger(k, "EXP-0107", "topk-jaccard", main)
    point = ctx.metric(m, "topk-jaccard-point", k, rel_m)
    reps = [ctx.metric(m, f"topk-jaccard-rep{i}", k, rel_m) for i in range(3)]
    cross_rep = ctx.metric(m, "cross_repeat_jaccard", k, rel_m)
    pi_mean = ctx.metric(m, "pi_mean", k, rel_m)
    pi_below = int(ctx.metric(m, "pi_below_0.5_count", k, rel_m))
    pi_denom = int(ctx.metric(m, "pi_below_0.5_denominator", k, rel_m))
    # current definition: agreement with the point-estimate direction
    sign_mean = ctx.metric(m, "sign_stability_mean", k, rel_m)
    # superseded reading P(rho>0); reported separately because it must not be called
    # "sign stability" any more
    sign_legacy = ctx.metric(m, "sign_stability_legacy_mean", k, rel_m)
    sign_negative = int(ctx.metric(m, "sign_negative_point_count", k, rel_m))
    boot = int(ctx.metric(m, "bootstrap_reps", k, rel_m))
    aligned = ctx.metric(m, "external_6csv_mean_spearman_aligned", k, rel_m)
    superseded = ctx.metric(m, "external_6csv_mean_spearman_superseded_positional", k, rel_m)
    rows_csv_matched = ctx.metric(m, "external_6csv_rows_matched", k, rel_m)
    n_methods = int(ctx.metric(m, "n_methods", k, rel_m))
    n_dims = int(ctx.metric(m, "n_dimensions", k, rel_m))

    values = [rob_metrics[e]["topk-jaccard"] for e in rob_exps]
    supp_value = rob_metrics[supp_exp]["topk-jaccard"]
    spread = max(values) - min(values)
    plan = ctx.manifest_plan(k, "Q2")
    limit = plan["decisionRule"]["limit"]
    rel_spread = spread / abs(values[0]) if values[0] else float("nan")
    if plan.get("experimentIds") != rob_exps:
        raise GuardFailure(k, f"稳健性计划的实验序列 {plan.get('experimentIds')} 与本表不一致")
    if not close(spread, plan["spread"], rel_tol=1e-9):
        raise GuardFailure(k, f"重算绝对极差 {spread!r} 与计划记录 {plan['spread']!r} 不一致")
    if len(plan.get("values") or []) != len(values):
        raise GuardFailure(k, f"计划记录值个数 {len(plan.get('values') or [])} 与执行块数 {len(values)} 不一致")
    for got, want in zip(values, plan["values"]):
        if not close(got, want):
            raise GuardFailure(k, f"稳健性执行值 {got!r} 与计划记录 {want!r} 不一致")
    if bool(rel_spread <= limit) != bool(plan["decisionPassed"]):
        raise GuardFailure(k, "相对极差与判定上限的关系和计划判定不一致")
    if "jaccard" not in out["q2"] or "pointEstimateSets" not in out["q2"]["jaccard"]:
        raise TableIncomplete(k, f"{rel_o} 缺少 q2.jaccard.pointEstimateSets")
    point_cross = out["q2"]["jaccard"]["pointEstimateSets"].get("summary", {}).get("overall")
    if point_cross is None:
        raise TableIncomplete(k, f"{rel_o} 的 q2.jaccard.pointEstimateSets.summary 缺少 overall")
    if not close(point_cross, point):
        raise GuardFailure(k, f"点估计 Jaccard {point!r} 与 outputs 汇总 {point_cross!r} 不一致")

    method_labels = {
        "total_spearman": "总体 Spearman",
        "within_style_spearman": "风格内 Spearman",
        "graph_lowrank": "图正则低秩系数",
        "consensus": "共识分",
    }
    names = out["q2"]["method"]["names"]
    if sorted(names) != sorted(method_labels):
        raise TableIncomplete(k, f"{rel_o} 的方法名单 {names} 未覆盖四种方法")

    entries = [
        ("Top-3 平均两两 Jaccard（入选频率优先集合，主指标）", fnum(main),
         f"{n_dims} 维 × {n_methods} 方法 × 6 个方法对，三次重复池化；集合为最终交付集合"),
        ("Top-3 平均两两 Jaccard（点估计集合）", fnum(point),
         "同一统计量，集合改为点估计 Top-3；与主指标的差异来自集合规则而不是数据"),
        ("第一次重复的 Jaccard", fnum(reps[0]), "该次重复自身的池化值"),
        ("第二次重复的 Jaccard", fnum(reps[1]), "该次重复自身的池化值"),
        ("第三次重复的 Jaccard", fnum(reps[2]), "该次重复自身的池化值"),
        ("跨重复集合一致率（Jaccard）", fnum(cross_rep), "交付集合在两次重复之间的重合程度"),
        ("入选频率 π 均值", fnum(pi_mean),
         "交付严格榜条目：四种方法 × 三次重复池化（每次重复 600 条）"),
        ("π < 0.5 的条目数 / 分母", f"{pi_below} / {pi_denom}",
         f"占比 {pct(pi_below / pi_denom)}；分母为该口径下的条目总数"),
        ("符号方向一致率均值（现行口径）", fnum(sign_mean),
         "同一批交付条目中，bootstrap 复制里总体 Spearman 与点估计同方向的比例"),
        ("符号稳定性（已弃用口径 P(ρ>0)，不得再称为 sign stability）", fnum(sign_legacy),
         f"旧口径把 {sign_negative} 条点估计为负方向的条目计为“不稳定”；"
         "该值偏低源于定义而不是方向不稳，仅作历史对照"),
        ("与附件 6.csv 的同源秩相关（双侧名称对齐）", fnum(aligned),
         f"{int(rows_csv_matched)} 行名称两侧对齐；同源对照，不是外部验证"),
        ("与附件 6.csv 的同源秩相关（已废弃：列位置口径）", fnum(superseded),
         "该值由按列位置对齐加索引混用产生，属错位伪影，已弃用，不得作为佐证"),
        ("bootstrap 预算（每次重复）", f"{boot}", "风格内分层重采样次数，各执行块相同"),
        ("稳健性执行值（计划内 2 块：种子块 0 参考 / 种子块 1）",
         " / ".join(fnum(v) for v in values),
         "同一指标在两个已执行冻结种子块下的取值；台账方法为 param-perturbation（被扰动对象是冻结种子块），"
         "不是 multiple-seeds，也没有预算扰动"),
        ("补充种子块（种子块 2，登记后执行，未并入计划记录）", fnum(supp_value),
         "该块在计划登记后才执行，工具拒绝覆盖已执行计划；不得并入上面的执行值、极差与判定，"
         "也不得写成 n=3 的计划结果"),
        ("绝对极差", fnum(spread), "计划内两值的最大值 − 最小值（不含补充块）"),
        ("真实相对极差", fnum(rel_spread), f"绝对极差 / 参考值；判定上限 {fnum(limit)}"),
        ("稳健性判定", "通过" if plan["decisionPassed"] else "未通过",
         f"预注册规则 {plan['decisionRule']['type']}；只描述本组扰动"),
    ]
    header = ["指标", "数值", "口径与说明"]
    rows, csv_rows = [], []
    src_rob = ",".join(f"experiments/{e}/metrics.json#topk-jaccard" for e in rob_exps)
    srcs = [f"{rel_m}#topk-jaccard", f"{rel_m}#topk-jaccard-point",
            f"{rel_m}#topk-jaccard-rep0", f"{rel_m}#topk-jaccard-rep1", f"{rel_m}#topk-jaccard-rep2",
            f"{rel_m}#cross_repeat_jaccard", f"{rel_m}#pi_mean",
            f"{rel_m}#pi_below_0.5_count,pi_below_0.5_denominator", f"{rel_m}#sign_stability_mean",
            f"{rel_m}#sign_stability_legacy_mean,sign_negative_point_count",
            f"{rel_m}#external_6csv_mean_spearman_aligned",
            f"{rel_m}#external_6csv_mean_spearman_superseded_positional",
            f"{rel_m}#bootstrap_reps", src_rob + "; report/evidence_manifest.json#Q2.robustnessPlan",
            f"experiments/{supp_exp}/metrics.json#topk-jaccard (supplementary, not in plan)",
            src_rob, src_rob, src_rob]
    for (label, value, note_txt), src in zip(entries, srcs):
        rows.append([label, value, note_txt])
        csv_rows.append([label, value, note_txt, src])
    note = (
        "注：Jaccard 衡量的是不同方法/重复之间 Top-3 集合的重合程度，不是预测准确率；"
        "π 是候选在 bootstrap 复制中的入选频率，低于 0.5 表示名次不稳；"
        "符号方向一致率与旧口径 P(ρ>0) 是两种定义，必须分开引用：现行口径只问“与点估计同方向”，"
        "旧口径把负方向条目一律计为不一致，因此其数值天然偏低。"
        "6.csv 与本研究同源，只作排序一致性对照，不能称为外部独立验证；"
        f"bootstrap 预算固定为每次重复 {boot} 次，各执行块之间没有预算差异。"
        "稳健性执行值只覆盖计划内已链接的冻结种子块（方法记为 param-perturbation），"
        "计划参考块是登记后的重跑，因此其值不必等于主实验的池化值；"
        "种子块 2 的补充块在登记后执行、单独列出且未并入计划记录；"
        "这些判定都不构成模型全面稳定的证据。"
    )
    fragment = md_table(header, rows, ["l", "r", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["指标", "数值", "口径与说明", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"计划内两值 {values}（极差 {spread}，相对 {rel_spread}）；补充块值 {supp_value}（未并入计划）"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- T13
def build_q3_raw_design(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_m = "experiments/EXP-0109/metrics.json"
    rel_o = "experiments/EXP-0109/outputs.json"
    m = ctx.json(k, rel_m)
    out = ctx.json(k, rel_o)
    ctx.cross_check_metrics(k, "EXP-0109", m)
    ctx.assert_ledger(k, "EXP-0109", "energy-distance", ctx.metric(m, "energy-distance", k, rel_m))

    try:
        comp = out["q3"]["comparisons"]["copula-selected"]
        rounds = out["q3"]["projection_rounds"]
        change = out["q3"]["raw_design_change"]
    except KeyError as exc:
        raise TableIncomplete(k, f"{rel_o} 缺少 q3.comparisons/projection_rounds/raw_design_change（{exc}）") from exc
    raw = comp.get("raw")
    design = comp.get("design")
    if not isinstance(raw, dict) or not isinstance(design, dict):
        raise TableIncomplete(k, f"{rel_o} 的 copula-selected 缺少 raw/design 块")

    e_raw = ctx.metric(m, "energy-distance-raw", k, rel_m)
    e_design = ctx.metric(m, "energy-distance", k, rel_m)
    if not close(e_raw, raw["energy-distance"]):
        raise GuardFailure(k, f"原始能量距离 {raw['energy-distance']!r} 与 metrics {e_raw!r} 不一致")
    if not close(e_design, design["energy-distance"]):
        raise GuardFailure(k, f"设计能量距离 {design['energy-distance']!r} 与 metrics {e_design!r} 不一致")
    cs_raw = ctx.metric(m, "constraint-satisfaction-raw", k, rel_m)
    cs_design = ctx.metric(m, "constraint-satisfaction", k, rel_m)
    neg_raw = ctx.metric(m, "n-linear-negative-raw", k, rel_m)
    neg_design = ctx.metric(m, "n-linear-negative-design", k, rel_m)
    mean_change = ctx.metric(change, "mean_abs_change_std_all_columns", k, rel_o)
    proj = out["q3"].get("design_projection") or {}
    if "maxResidualFromAudit" not in proj:
        raise TableIncomplete(k, f"{rel_o} 缺少 q3.design_projection.maxResidualFromAudit")
    max_res = proj["maxResidualFromAudit"]
    allowed_rounds = proj.get("maxRoundsAllowed")
    if allowed_rounds is None:
        raise TableIncomplete(k, f"{rel_o} 缺少 q3.design_projection.maxRoundsAllowed")
    cs_from_csv = proj.get("constraintSatisfactionFromCsv")
    if cs_from_csv is not None and not close(cs_from_csv, cs_design):
        raise GuardFailure(k, "设计谱约束满足率与从写出样本复核的值不一致")

    top_changed = sorted(change["top_changed_columns"].items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    if len(top_changed) < 3:
        raise TableIncomplete(k, f"{rel_o} 的改动最大列不足 3 个")

    rows = [
        ["归一化经验能量距离 V", fnum(raw["energy-distance"]), fnum(design["energy-distance"]),
         "按 n_gen 加权池化；越小表示生成谱越接近真实谱"],
        ["无符号能量 V", fnum(raw["energy-V"]), fnum(design["energy-V"]), "非负的分布差异量"],
        ["带符号能量 U", fnum(raw["energy-U"]), fnum(design["energy-U"]),
         "可负、不截零；U 的符号只表示带符号统计量的读数方向，不用它推断偏移方向或过度分散"],
        ["约束满足率", fnum(cs_raw), fnum(cs_design),
         "同时满足全部声明约束的样本比例；设计侧由投影循环保证"],
        ["负浓度格数", fint(neg_raw), fint(neg_design), "线性非负约束被违反的格数"],
        ["约束投影轮数（均值）", "—", fnum(rounds["mean"]),
         f"逐格迭代直到最大残差 ≤ 1e-9；允许轮数上限 {int(allowed_rounds)}"],
        ["约束投影轮数（最大）", "—", fint(rounds["max"]),
         f"允许轮数上限 {int(allowed_rounds)}，本轮实际最大 {int(rounds['max'])}"],
        ["约束投影最大残差", "—", fnum(max_res), "投影后从写出的样本文件复核"],
        ["全列平均绝对改动（标准化单位）", "—", fnum(mean_change),
         "约束投影相对未约束原始抽样的逐列平均绝对改动"],
    ]
    for name, value in top_changed:
        rows.append([f"改动最大的列：{CHEM_LABELS.get(name.split('chem__', 1)[-1], name)}", "—", fnum(value),
                     "约束投影相对未约束原始抽样的逐列平均绝对改动"])
    src_common = (f"{rel_m}#energy-distance,energy-distance-raw,energy-V-raw,energy-U-signed,"
                  f"constraint-satisfaction,constraint-satisfaction-raw,n-linear-negative-raw,"
                  f"n-linear-negative-design | {rel_o}#q3.comparisons.copula-selected.raw,design")
    csv_rows = []
    csv_label = ["归一化经验能量距离 V", "无符号能量 V", "带符号能量 U", "约束满足率", "负浓度格数",
                 "约束投影轮数（均值）", "约束投影轮数（最大）", "约束投影最大残差",
                 "全列平均绝对改动（标准化单位）"]
    csv_vals = [
        (raw["energy-distance"], design["energy-distance"]),
        (raw["energy-V"], design["energy-V"]),
        (raw["energy-U"], design["energy-U"]),
        (cs_raw, cs_design),
        (neg_raw, neg_design),
        (None, rounds["mean"]),
        (None, rounds["max"]),
        (None, max_res),
        (None, mean_change),
    ]
    for label, (rv, dv) in zip(csv_label, csv_vals):
        csv_rows.append([label, rv, dv,
                         f"{rel_o}#q3.comparisons.copula-selected | {rel_m} | {rel_o}#q3.projection_rounds,raw_design_change"])
    for name, value in top_changed:
        csv_rows.append([f"改动最大的列：{CHEM_LABELS.get(name.split('chem__', 1)[-1], name)}", None, value,
                         f"{rel_o}#q3.raw_design_change.top_changed_columns"])

    header = ["指标", "未约束原始生成", "约束后设计谱", "说明"]
    note = (
        "注：左侧为未施加约束的原始条件生成，右侧为约束投影后的设计谱。能量距离按可估格加权池化，"
        "V 与 U 是同一能量统计量的无符号与带符号读数。"
        f"约束满足率在未约束原始生成上为 {fnum(cs_raw)}，在设计谱上为 {fnum(cs_design)}，"
        "后者是投影循环的构造性质，不能当作分布质量证据。"
        "设计谱中真实化学反-2-壬烯醛的增加条数为 "
        f"{fint(ctx.metric(m, 'nonenal-increases-design', k, rel_m))}；"
        "感官 t2n 代理的增加条数另计"
        f"（{fint(ctx.metric(m, 't2n-increases', k, rel_m))} / {fint(ctx.metric(m, 'n-samples', k, rel_m))}），"
        "两者是不同命题，不能互相替代。"
        "改动量以标准化单位给出，只描述“投影改了多少”，不是约束残差。"
    )
    fragment = md_table(header, rows, ["l", "r", "r", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["指标", "raw_value", "design_value", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"投影轮数 mean={rounds['mean']}, max={rounds['max']}; 平均改动 {mean_change}"],
        "shape": "wide",
    }


# --------------------------------------------------------------------------- T14
def build_q3_quality(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_m = "experiments/EXP-0109/metrics.json"
    rel_o = "experiments/EXP-0109/outputs.json"
    rel_s = "outputs/q3/style_and_displacement_scope.json"
    m = ctx.json(k, rel_m)
    out = ctx.json(k, rel_o)
    scope = ctx.json(k, rel_s)
    ctx.cross_check_metrics(k, "EXP-0109", m)
    ctx.assert_ledger(k, "EXP-0109", "energy-distance", ctx.metric(m, "energy-distance", k, rel_m))
    ctx.assert_ledger(k, "EXP-0109", "energy-U-signed", ctx.metric(m, "energy-U-signed", k, rel_m))

    comps = out["q3"]["comparisons"]
    order = ["copula-selected", "copula-shared-only", "copula-style-empirical",
             "independent-marginals", "source-resample"]
    for name in order:
        if name not in comps:
            raise TableIncomplete(k, f"{rel_o} 缺少比较方案 '{name}'")
    if not close(comps["copula-selected"]["design"]["energy-distance"], ctx.metric(m, "energy-distance", k, rel_m)):
        raise GuardFailure(k, "copula-selected 设计谱能量距离与主指标不一致")
    if not close(comps["copula-selected"]["design"]["energy-U"], ctx.metric(m, "energy-U-signed", k, rel_m)):
        raise GuardFailure(k, "copula-selected 设计谱带符号 U 与主指标不一致")

    n_samples = int(ctx.metric(m, "n-samples", k, rel_m))
    n_features = int(ctx.target_columns().N_FEATURES)
    n_cells_all = int(ctx.metric(m, "n-cells", k, rel_m))
    n_cells_excluded = int(ctx.metric(m, "n-cells-excluded-from-energy", k, rel_m))
    pooling0 = scope.get("energy_distance_pooling", {})
    all_est0 = pooling0.get("all_estimable_styles")
    if not all_est0:
        raise TableIncomplete(k, f"{rel_s} 缺少 all_estimable_styles")
    if n_cells_all - n_cells_excluded != int(all_est0["cells"]):
        raise GuardFailure(
            k, f"可估格数 {all_est0['cells']} 与 总格 {n_cells_all} − 不可估 {n_cells_excluded} 不一致")
    if n_samples - int(all_est0["n_gen"]) != n_cells_excluded:
        raise GuardFailure(
            k, f"进入能量距离的生成份数 {int(all_est0['n_gen'])} 与 总样本 {n_samples} − 不可估 {n_cells_excluded} 不一致")
    n_stored_cells = n_samples * n_features

    header = ["方案", "归一化能量距离 V", "带符号 U", "多样性", "最近邻距离", "精确复制率", "边饱和比例", "范围说明"]
    rows, csv_rows = [], []
    for name in order:
        d = comps[name]["design"]
        for field in ("energy-distance", "energy-U", "diversity", "nearest-neighbor",
                      "duplicate-share", "edge-fraction"):
            if field not in d:
                raise TableIncomplete(k, f"{rel_o} comparisons['{name}'].design 缺少 '{field}'")
        scope_note = (f"能量/U/多样性/最近邻按 {int(all_est0['cells'])} 格 · "
                      f"{int(all_est0['n_gen'])} 份加权；复制率与边饱和按 "
                      f"{n_features}×{n_samples} 格")
        if name == "source-resample":
            scope_note = "同风格训练行重采样参照，不是生成模型；" + scope_note
        edge_hits = float(d["edge-fraction"]) * n_stored_cells
        if abs(edge_hits - round(edge_hits)) > 1e-6:
            raise GuardFailure(
                k, f"{name} 的边饱和比例 {d['edge-fraction']!r} × {n_stored_cells} 格 不是整数命中数"
                   f"（{edge_hits!r}），存储格分母口径不成立")
        if not close(round(edge_hits) / n_stored_cells, d["edge-fraction"], rel_tol=1e-9):
            raise GuardFailure(k, f"{name} 的边饱和比例不能用 {n_stored_cells} 个存储格复算")
        dup = float(d["duplicate-share"]) * n_samples
        if abs(dup - round(dup)) > 1e-6:
            raise GuardFailure(
                k, f"{name} 的精确复制率 {d['duplicate-share']!r} × {n_samples} 行 不是整数行数（{dup!r}）")
        rows.append([COMPARISON_LABELS[name], fnum(d["energy-distance"]), fnum(d["energy-U"]),
                     fnum(d["diversity"]), fnum(d["nearest-neighbor"]), fnum(d["duplicate-share"]),
                     fnum(d["edge-fraction"]), scope_note])
        csv_rows.append([COMPARISON_LABELS[name], name, d["energy-distance"], d["energy-U"],
                         d["diversity"], d["nearest-neighbor"], d["duplicate-share"],
                         d["edge-fraction"], scope_note,
                         f"{rel_o}#q3.comparisons.{name}.design"])

    pooling = scope.get("energy_distance_pooling", {})
    all_est = pooling.get("all_estimable_styles")
    three = pooling.get("tripel_kriek_lambic")
    if not all_est or not three:
        raise TableIncomplete(k, f"{rel_s} 缺少 all_estimable_styles / tripel_kriek_lambic")
    if not close(all_est["value"], ctx.metric(m, "energy-distance", k, rel_m), rel_tol=1e-12):
        raise GuardFailure(k, "范围文件的 21 风格池化值与主指标不一致")
    scope_rows = [
        (f"范围口径：{all_est['styles']} 个可估风格 · {all_est['cells']} 个可估格池化（归一化 V）",
         all_est["value"], all_est.get("U_signed"),
         f"n_gen={int(all_est['n_gen'])}；未归一化 V = {fnum(all_est.get('V_raw'))}；与主方案同值，用于声明池化范围"),
        (f"范围口径：Tripel/Kriek/Lambic 三风格 · {three['cells']} 个格单独池化（归一化 V）",
         three["value"], three.get("U_signed"),
         f"n_gen={int(three['n_gen'])}；未归一化 V = {fnum(three.get('V_raw'))}；与上一行不是同一范围，不可互换"),
    ]
    for label, value, u, note_txt in scope_rows:
        rows.append([label, fnum(value), fnum(u), "—", "—", "—", "—", note_txt])
        csv_rows.append([label, "scope-pooling", value, u, None, None, None, None,
                         note_txt, f"{rel_s}#energy_distance_pooling"])

    note = (
        "注：前五行为同一评价协议下不同采样方案的设计谱比较，能量距离越小越好；U 可负、不截零。"
        "**分母不同，不可混读**：归一化能量距离、带符号 U、多样性与最近邻距离按 "
        f"{int(all_est0['cells'])} 个可估格、{int(all_est0['n_gen'])} 份生成的 n_gen 加权口径计算；"
        f"精确复制率与边饱和比例的分母是 {n_features}×{n_samples} = {n_stored_cells} 个存储单元格"
        f"（{n_samples} 行），其中包含未进入能量距离的 {n_cells_excluded} 个不可估格 / {n_cells_excluded} 份生成，"
        "因此两类指标的分母不是同一批格。"
        "四个分布侧指标各自回答不同问题，不可互相解释：多样性为生成样本在标准化空间中的两两欧氏距离均值"
        "（按固定抽样次数子采样）；最近邻距离为每个样本到最近样本距离的均值；"
        "精确复制率为与已有行完全重复的行占比；边饱和比例为落在声明边界上的单元格占比"
        "（地板编码、观测支撑上下界、线性列零值）。"
        "源样本重采样参照直接复用同风格的训练行，其能量距离低于各生成方案；该行的作用是给出“不生成”的参照，"
        "不能与生成模型等同比较。"
        "后两行只声明池化范围："
        f"{all_est['styles']} 个可估风格 {all_est['cells']} 个可估格的池化值与三风格单独池化值不可互换，"
        "两者的带符号 U 也随范围变化，引用时必须写明范围。"
    )
    fragment = md_table(header, rows, ["l"] + ["r"] * 6 + ["l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["方案", "comparison_key", "energy_distance", "energy_U", "diversity",
                       "nearest_neighbor", "duplicate_share", "edge_fraction", "scope_remark",
                       "_source"],
        "csv_rows": csv_rows,
        "notes": [f"{all_est['styles']} 风格池化 {all_est['value']}（{all_est['cells']} 格 / n_gen={int(all_est['n_gen'])}）；"
                  f"三风格池化 {three['value']}（{three['cells']} 格 / n_gen={int(three['n_gen'])}）"],
        "shape": "wide",
    }


# --------------------------------------------------------------------------- T15
def build_q3_constraints(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_c = "experiments/EXP-0109/constraints.csv"
    rel_m = "experiments/EXP-0109/metrics.json"
    frame = ctx.frame(k, rel_c)
    m = ctx.json(k, rel_m)
    ctx.cross_check_metrics(k, "EXP-0109", m)
    for col in ("field", "bound_type", "verdict"):
        if col not in frame.columns:
            raise TableIncomplete(k, f"{rel_c} 缺少列 '{col}'")

    verdicts = frame["verdict"].value_counts().to_dict()
    total = len(frame)
    m_ver = int(ctx.metric(m, "constraints-verified", k, rel_m))
    m_cond = int(ctx.metric(m, "constraints-conditional", k, rel_m))
    m_ni = int(ctx.metric(m, "constraints-not-identifiable", k, rel_m))
    m_inf = int(ctx.metric(m, "constraints-infeasible", k, rel_m))
    got = (int(verdicts.get("verified", 0)), int(verdicts.get("conditional", 0)),
           int(verdicts.get("not_identifiable", 0)), int(verdicts.get("infeasible", 0)))
    if got != (m_ver, m_cond, m_ni, m_inf):
        raise GuardFailure(k, f"约束记录计数 {got} 与 metrics 计数 {(m_ver, m_cond, m_ni, m_inf)} 不一致")
    if m_ver + m_cond + m_ni + m_inf != total:
        raise GuardFailure(k, "四类约束计数之和与记录总数不一致")
    ver_share = ctx.metric(m, "constraint-records-verified-share", k, rel_m)
    if not close(ver_share, m_ver / total):
        raise GuardFailure(k, "核验占比与计数不一致")

    lower_zero_fields = sorted(frame.loc[frame["bound_type"] == "lower_zero", "field"].unique())
    if len(lower_zero_fields) != 33:
        raise TableIncomplete(k, f"{rel_c} 中线性非负列数 {len(lower_zero_fields)} ≠ 33")

    def classify(row):
        field, btype = row["field"], row["bound_type"]
        if btype == "upper_threshold" and field == "chem__DMS":
            return "缺陷硬阈值·二甲基硫上界"
        if btype == "upper_threshold" and field == "chem__X4VG":
            return "缺陷硬阈值·4-乙烯基愈创木酚上界"
        if btype == "upper_threshold" and field == "chem__X2.3.butanedione":
            return "缺陷硬阈值·双乙酰上界"
        if btype == "upper_training_q90_chemical":
            return "反-2-壬烯醛化学不增（训练 q90 上界）"
        if btype == "upper_training_q90_proxy":
            return "老化酒花代理上界（岭回归代理）"
        if btype == "lower_zero":
            return "线性非负（33 列）"
        raise GuardFailure(k, f"未识别的约束类型 field={field!r} bound_type={btype!r}")

    frame = frame.copy()
    frame["cls"] = frame.apply(classify, axis=1)
    classes = ["缺陷硬阈值·二甲基硫上界", "缺陷硬阈值·4-乙烯基愈创木酚上界",
               "缺陷硬阈值·双乙酰上界", "反-2-壬烯醛化学不增（训练 q90 上界）",
               "老化酒花代理上界（岭回归代理）", "线性非负（33 列）"]
    piv = frame.groupby(["cls", "verdict"]).size().unstack(fill_value=0)

    header_a = ["核验状态", "记录数", "占比"]
    status_cn = [("verified", "已验证（verified）"), ("conditional", "条件成立（conditional）"),
                 ("not_identifiable", "不可识别（not identifiable）"), ("infeasible", "不可行（infeasible）")]
    rows_a, csv_rows = [], []
    for raw, label in status_cn:
        n = int(verdicts.get(raw, 0))
        rows_a.append([label, n, fshare(n, total)])
        csv_rows.append(["status", label, raw, n, fshare(n, total),
                         f"{rel_c}#verdict | {rel_m}#constraints-{raw.replace('_','-')}"])
    rows_a.append(["合计", total, "1.0000"])
    csv_rows.append(["status", "合计", "total", total, "1.0000", f"{rel_c}#rows"])

    header_b = ["约束类", "记录数", "已验证", "条件成立", "不可识别", "不可行"]
    rows_b = []
    for cls in classes:
        sub = piv.loc[cls] if cls in piv.index else None
        if sub is None:
            raise TableIncomplete(k, f"约束类 '{cls}' 在约束记录中不存在")
        n = int(sub.sum())
        counts = (int(sub.get("verified", 0)), int(sub.get("conditional", 0)),
                  int(sub.get("not_identifiable", 0)), int(sub.get("infeasible", 0)))
        rows_b.append([cls, n] + list(counts))
        for raw, label in status_cn:
            csv_rows.append(["class", cls, raw, int(sub.get(raw, 0)), fshare(int(sub.get(raw, 0)), n),
                             f"{rel_c}#field/bound_type × verdict"])
    rows_b.append(["合计", total, m_ver, m_cond, m_ni, m_inf])
    csv_rows.append(["class", "合计", "total", total, "1.0000", f"{rel_c}#rows"])

    cs_design = ctx.metric(m, "constraint-satisfaction", k, rel_m)
    cs_raw = ctx.metric(m, "constraint-satisfaction-raw", k, rel_m)
    note = (
        "注：上表为逐条约束记录的四类核验状态，下表按约束类拆分。"
        "“已验证”指约束在写出的样本文件中被直接复核；“条件成立”指约束依赖训练折内的数据派生界或代理变量；"
        "“不可识别”指该格的上界无法从数据确定（如缺陷列缺测）；不可行记录为零。"
        f"设计谱的约束满足率为 {fnum(cs_design)}（由约束投影保证），未约束原始生成仅 {fnum(cs_raw)}；"
        f"核验记录合计 {total} 条，其中已验证占比 {fnum(ver_share)}。"
        "线性非负类覆盖 33 个化学列；老化酒花只有训练折内的代理约束，不能读作实测老化指标。"
    )
    fragment = (md_table(header_a, rows_a, ["l", "r", "r"]) + "\n\n" +
                md_table(header_b, rows_b, ["l"] + ["r"] * 5) + "\n\n" + note + "\n")
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["block", "label", "verdict", "count", "share", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"记录 {total}；verified {m_ver} / conditional {m_cond} / not_identifiable {m_ni} / infeasible {m_inf}"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- T16
def build_q3_transfer_stages(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_m = "experiments/EXP-0110/metrics.json"
    rel_o = "experiments/EXP-0110/outputs.json"
    m = ctx.json(k, rel_m)
    out = ctx.json(k, rel_o)
    ctx.cross_check_metrics(k, "EXP-0110", m)
    ctx.assert_ledger(k, "EXP-0110", "transfer-energy", ctx.metric(m, "transfer-energy", k, rel_m))
    ctx.assert_ledger(k, "EXP-0110", "nonincrease-rate", ctx.metric(m, "nonincrease-rate", k, rel_m))

    energy = out.get("energy_by_strategy")
    noninc = out.get("nonincrease_by_strategy")
    tma = out.get("target_mean_assertion")
    if not energy or not noninc or not tma:
        raise TableIncomplete(k, f"{rel_o} 缺少 energy_by_strategy / nonincrease_by_strategy / target_mean_assertion")

    order = ["qp-quantile-anchor", "qp-source-anchor", "source-fixed",
             "target-mean-projection", "target-mean-projection-full"]
    for name in order:
        if name not in energy or name not in noninc:
            raise TableIncomplete(k, f"{rel_o} 缺少策略 '{name}'")
        for field in ("V", "V_normalized"):
            if field not in energy[name]:
                raise TableIncomplete(k, f"{rel_o} energy_by_strategy['{name}'] 缺少 '{field}'")
        for field in ("nonincreaseRate", "staleProxyRate", "fallbackShare"):
            if field not in noninc[name]:
                raise TableIncomplete(k, f"{rel_o} nonincrease_by_strategy['{name}'] 缺少 '{field}'")
    if not close(energy["qp-quantile-anchor"]["V"], ctx.metric(m, "transfer-energy", k, rel_m)):
        raise GuardFailure(k, "交付策略的转移能量与主指标不一致")
    defect_cols = tuple(ctx.target_columns().DEFECT_COLUMNS)
    for name in order:
        per_field = noninc[name].get("perField")
        if not isinstance(per_field, dict):
            raise TableIncomplete(k, f"{rel_o} nonincrease_by_strategy['{name}'] 缺少 'perField'")
        if set(per_field) != set(defect_cols):
            raise TableIncomplete(
                k, f"{rel_o} nonincrease_by_strategy['{name}'].perField 的列集合 {sorted(per_field)} "
                   f"与缺陷化学列 {sorted(defect_cols)} 不一致")
        values = [float(per_field[c]) for c in defect_cols]
        if max(values) != min(values):
            raise GuardFailure(
                k, f"策略 {name} 的四条化学列不增率不相等 {dict(zip(defect_cols, values))}，"
                   f"不能用单列代表四列")
        common = values[0]
        composite = float(noninc[name]["nonincreaseRate"])
        stale = float(noninc[name]["staleProxyRate"])
        if not close(composite, min(common, stale)):
            raise GuardFailure(
                k, f"策略 {name} 的综合不增率 {composite!r} 不等于 min(四条化学列 {common!r}, "
                   f"代理 {stale!r})，指标口径与产物不一致")
        if name == "qp-quantile-anchor":
            for defect in defect_cols:
                key_field = f"nonincrease-rate-{defect}"
                if key_field not in m:
                    raise TableIncomplete(k, f"{rel_m} 缺少 metric key '{key_field}'")
                if not close(per_field[defect], m[key_field]):
                    raise GuardFailure(k, f"{defect} 的逐列不增率与 metrics 不一致")
    for name in order:
        key = f"fallback-share-{name}"
        if key not in m:
            raise TableIncomplete(k, f"{rel_m} 缺少 metric key '{key}'")
        if not close(noninc[name]["fallbackShare"], m[key]):
            raise GuardFailure(k, f"策略 {name} 的 fallback 份额与 metrics 不一致")
        rate_key = f"nonincrease-rate-{name}"
        if rate_key in m and not close(noninc[name]["nonincreaseRate"], m[rate_key]):
            raise GuardFailure(k, f"策略 {name} 的综合不增率与 metrics 不一致")
    self_dist = ctx.metric(m, "target-mean-self-distance", k, rel_m)
    if not close(self_dist, tma["maxObserved"]):
        raise GuardFailure(k, "目标均值自距与 metrics 不一致")

    rows, csv_rows = [], []
    header = ["策略", "转移能量 V", "归一化 V", "四条化学列不增率", "老化酒花代理不增率",
              "综合不增率（含代理）", "fallback 份额", "目标均值自距"]
    for name in order:
        e = energy[name]
        n = noninc[name]
        per_field = n["perField"]
        common = float(per_field[defect_cols[0]])
        extra = fnum(self_dist) if name == "target-mean-projection" else "—"
        rows.append([STRATEGY_LABELS[name], fnum(e["V"]), fnum(e["V_normalized"]),
                     fnum(common), fnum(n["staleProxyRate"]), fnum(n["nonincreaseRate"]),
                     fnum(n["fallbackShare"]), extra])
        csv_rows.append([STRATEGY_LABELS[name], name, e["V"], e["V_normalized"],
                         common, n["staleProxyRate"], n["nonincreaseRate"], n["fallbackShare"],
                         self_dist if name == "target-mean-projection" else None,
                         f"{rel_o}#nonincrease_by_strategy.{name}.perField,staleProxyRate,nonincreaseRate | "
                         f"{rel_o}#energy_by_strategy.{name} | {rel_m}#target-mean-self-distance"])
    box_only = noninc["target-mean-projection"]
    full = noninc["target-mean-projection-full"]
    box_only_rate = float(box_only["nonincreaseRate"])
    full_rate = float(full["nonincreaseRate"])
    if not close(float(full["perField"][defect_cols[0]]), 1.0):
        raise GuardFailure(k, "完整可行域均值投影的四条化学列不增率不是 1")
    note = (
        "注：转移能量按同一批目标参考行计算，越小表示迁移后的谱越接近目标风格。"
        "四条化学列不增率只统计二甲基硫、双乙酰、4-乙烯基愈创木酚、反-2-壬烯醛四条 cap；"
        "综合不增率另要求老化酒花代理不增。"
        f"盒约束均值投影（不含半空间）的综合不增率为 {fnum(box_only_rate)}，其偏低完全由代理越界驱动，"
        "四条化学 cap 仍全部满足，因此该值不等于“四条 cap 有相应比例不满足”。"
        f"完整可行域均值投影（box ∩ 同一条 stale 半空间）的综合不增率为 {fnum(full_rate)}，"
        "它是本轮新增的参照基线：与交付 QP 策略有相同的可行域和非增性质，但转移能量更高，"
        "因此“非增率 = 1”本身不能区分策略优劣。"
        "源固定策略是不做任何迁移的平凡对照，其四条化学列与综合不增率同样为 1，"
        "因此不能把 1.000 读成迁移效果；老化酒花代理是训练折内的岭回归代理，不是实测老化指标。"
        "该复合指标在计划内两个执行块与补充种子块中均为 1.000（有界饱和），"
        "min-value 规则下“min 1 ≥ 1”不构成改善或强稳健证据。"
        "盒约束均值投影是诊断对照，其代理越界记录只属该参照控制，不参与交付判定。"
        "fallback 份额为 0 表示没有迁移结果被退回源谱。"
        "目标均值自距是“目标均值到自身”的距离，只对盒约束均值投影策略有意义；"
        "早期中心化口径下的同名值偏大，已被修复，不再引用。"
    )
    fragment = md_table(header, rows, ["l"] + ["r"] * 7) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["策略", "strategy_key", "transfer_energy_V", "transfer_energy_normalized",
                       "nonincrease_rate_chem4", "stale_proxy_rate", "nonincrease_rate_composite",
                       "fallback_share", "target_mean_self_distance", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"目标均值自距 {self_dist}；旧口径 {tma.get('maxObservedLegacyCentering')}"],
        "shape": "wide",
    }


# --------------------------------------------------------------------------- T17
def build_q3_transfer_columns(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_tc = "experiments/EXP-0110/transfer_constraints.csv"
    rel_tr = "experiments/EXP-0110/transfers.csv"
    rel_o = "experiments/EXP-0110/outputs.json"
    rel_s = "outputs/q3/style_and_displacement_scope.json"
    rel_z = "outputs/q3/zspace_recompute.json"
    tc = ctx.frame(k, rel_tc)
    tr = ctx.frame(k, rel_tr)
    out = ctx.json(k, rel_o)
    scope = ctx.json(k, rel_s)
    zre = ctx.json(k, rel_z)

    strategy = "qp-quantile-anchor"
    keyed = {"chem__X.E..2.nonenal": "反-2-壬烯醛",
             "chem__X2.3.butanedione": "双乙酰",
             "chem__X4VG": "4-乙烯基愈创木酚"}
    group = tc[tc["strategy"] == strategy]
    if group.empty:
        raise TableIncomplete(k, f"{rel_tc} 中没有策略 '{strategy}' 的记录")
    disp = scope.get("transfer_displacement", {})
    if disp.get("strategy") != strategy:
        raise TableIncomplete(k, f"{rel_s} 的位移策略不是 '{strategy}'")
    per_col = disp.get("per_column", {})

    groups = scope.get("transfer_target_vs_movement", {}).get("per_strategy", {}).get(strategy)
    if not groups:
        raise TableIncomplete(k, f"{rel_s} 缺少 transfer_target_vs_movement.per_strategy['{strategy}']")

    rows, csv_rows = [], []
    header = ["对象", "①约束残差 max", "②存储空间位移 max", "②存储空间位移 mean", "③z 空间位移 max", "③z 空间位移 mean"]
    for field, label in keyed.items():
        sub = group[group["field"] == field]
        if sub.empty:
            raise TableIncomplete(k, f"{rel_tc} 缺少列 '{field}' 的迁移约束记录")
        resid_max = float(sub["residual"].max())
        raw_name = field.split("chem__", 1)[1]
        if raw_name not in per_col:
            raise TableIncomplete(k, f"{rel_s} 的 transfer_displacement.per_column 缺少 '{raw_name}'")
        pc = per_col[raw_name]
        rows.append([label, fnum(resid_max), fnum(pc["max_abs_stored"]), fnum(pc["mean_abs_stored"]), "—", "—"])
        csv_rows.append([label, field, resid_max, pc["max_abs_stored"], pc["mean_abs_stored"], None, None,
                         f"{rel_tc}#strategy={strategy},field={field} | {rel_s}#transfer_displacement.per_column.{raw_name}"])

    sel = tr[tr["strategy"] == strategy]
    if sel.empty:
        raise TableIncomplete(k, f"{rel_tr} 中没有策略 '{strategy}' 的行")
    if "nonincrease_all" in tr.columns and not bool(sel["nonincrease_all"].all()):
        raise GuardFailure(k, f"{rel_tr} 中交付策略存在“不增”为假的迁移行")
    fixed = tr[tr["strategy"] == "source-fixed"]
    if fixed.empty:
        raise TableIncomplete(k, f"{rel_tr} 中缺少平凡对照 source-fixed 的行")
    if float(fixed["l1_change_z"].abs().max()) != 0.0:
        raise GuardFailure(k, "平凡对照的 z 空间位移不为 0，源固定对照失效")
    n_dims = int(ctx.target_columns().N_FEATURES)
    z_identity = (sel["l1_change_z"] / n_dims - sel["mean_abs_change_z"]).abs().max()
    if not float(z_identity) <= 1e-12:
        raise GuardFailure(
            k, f"{rel_tr} 的 z 空间位移不满足 l1_change_z / {n_dims} = mean_abs_change_z"
               f"（最大差 {z_identity!r}），行内恒等式不成立")
    l1_max, l1_mean = float(sel["l1_change_z"].max()), float(sel["l1_change_z"].mean())
    maz_max, maz_mean = float(sel["mean_abs_change_z"].max()), float(sel["mean_abs_change_z"].mean())
    if not close(maz_mean, groups["mean_abs_change_z_mean"], rel_tol=1e-9):
        raise GuardFailure(k, "重算的 z 空间平均位移与范围文件不一致")

    # The independent centre/scale rebuild may only be cited when it was built for THIS
    # run: same frozen input hashes and same strategy/row coverage. Otherwise it describes
    # an earlier run and is reported as such instead of being reused as current evidence.
    def _input_sha(rel: str):
        path = ROOT / "experiments" / "EXP-0110" / "inputs" / rel
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    frozen = zre.get("frozen_inputs") or {}
    frozen_mismatch = {}
    for rel in ("src/q3_lib.py", "src/q3_transfer_fix.py", "src/v6_common.py",
                "src/target_columns.py", "data/clean/q3.csv",
                "data/splits/NESTED-CV-1/splits.csv"):
        want = (frozen.get(rel) or {}).get("sha256")
        got = _input_sha(rel)
        if want is None or got is None or want != got:
            frozen_mismatch[rel] = {"audit": want, "current": got}
    zre_strategies = set((zre.get("per_strategy") or {}).keys())
    zre_rows = int(zre.get("rows_checked") or 0)
    coverage_ok = zre_strategies == set(tr["strategy"].unique()) and zre_rows == len(tr)
    zre_fresh = not frozen_mismatch and coverage_ok
    if zre_fresh:
        if int(zre.get("rows_mismatched", -1)) != 0:
            raise GuardFailure(k, f"{rel_z} 报告 {zre.get('rows_mismatched')} 行 z 位移复算失配")
        zre_note = "z 空间读数已由本轮冻结输入上的独立 centre/scale 重建逐行复核，失配 0 行"
    else:
        detail = []
        if frozen_mismatch:
            detail.append(f"冻结代码/数据 sha 与当前运行不同（{sorted(frozen_mismatch)}）")
        if not coverage_ok:
            detail.append(f"复算覆盖 {sorted(zre_strategies)} / {zre_rows} 行，本轮为 "
                          f"{sorted(set(tr['strategy'].unique()))} / {len(tr)} 行")
        zre_note = ("z 空间的独立 centre/scale 重建产物属于上一轮运行（" + "；".join(detail) +
                    "），本轮不引用该过期重建；本轮只做行内恒等式核对 "
                    f"l1_change_z / {n_dims} = mean_abs_change_z（最大差 {float(z_identity):.3e}）")
    rows.append(["z 空间·逐行 231 维绝对位移均值", "—", "—", "—", fnum(maz_max), fnum(maz_mean)])
    csv_rows.append(["z 空间·逐行 231 维绝对位移均值", "z-space", None, None, None, maz_max, maz_mean,
                     f"{rel_tr}#strategy={strategy},mean_abs_change_z | {rel_z}#rows_mismatched"
                     f"{'' if zre_fresh else ' (STALE: not cited as current evidence)'}"])
    rows.append(["z 空间·逐行 231 维 L1 位移", "—", "—", "—", fnum(l1_max), fnum(l1_mean)])
    csv_rows.append(["z 空间·逐行 231 维 L1 位移", "z-space", None, None, None, l1_max, l1_mean,
                     f"{rel_tr}#strategy={strategy},l1_change_z | {rel_z}#rows_mismatched"
                     f"{'' if zre_fresh else ' (STALE: not cited as current evidence)'}"])

    note = (
        "注：三组量不是同一对象，不能相互替代或相减。①约束残差是上限约束下 clamp(新值 − 源值, 0) 的逐行最大值，"
        "量级在浮点误差附近，只说明约束未被违反；②存储空间位移是 |新值 − 源值| 的逐列最大/均值，描述配方改动了多少；"
        "③z 空间位移是 231 维中心化标准化后的逐行位移，逐列分解未随产物保存，故只给出行级读数。"
        f"{zre_note}。三组都只针对交付的 QP 分位数锚定策略。"
    )
    fragment = md_table(header, rows, ["l"] + ["r"] * 5) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["对象", "key", "constraint_residual_max", "stored_disp_max", "stored_disp_mean",
                       "z_disp_max", "z_disp_mean", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"z 位移复算失配 {zre.get('rows_mismatched')} 行（本轮引用={zre_fresh}）；stored 位移源为范围文件；"
                  f"行内恒等式最大差 {float(z_identity):.3e}"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- T18
def build_q3_qp_certs(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    rel_c = "experiments/EXP-0110/solver_certificates.jsonl"
    rel_m = "experiments/EXP-0110/metrics.json"
    rel_o = "experiments/EXP-0110/outputs.json"
    rel_a = "outputs/q3/qp_cert_audit.json"
    certs = ctx.jsonl(k, rel_c)
    m = ctx.json(k, rel_m)
    out = ctx.json(k, rel_o)
    audit = ctx.json(k, rel_a)
    ctx.cross_check_metrics(k, "EXP-0110", m)
    ctx.assert_ledger(k, "EXP-0110", "qp-max-primal-residual",
                      ctx.metric(m, "qp-max-primal-residual", k, rel_m))
    ctx.assert_ledger(k, "EXP-0110", "qp-status-optimal", ctx.metric(m, "qp-status-optimal", k, rel_m))

    for field in ("status", "problem_hash", "primal_residual", "dual_residual",
                  "max_constraint_violation", "kkt_stationarity_residual", "strategy"):
        for i, rec in enumerate(certs):
            if field not in rec:
                raise TableIncomplete(k, f"{rel_c} 第 {i + 1} 条证书缺少字段 '{field}'")
    status_counts = {}
    for rec in certs:
        status_counts[rec["status"]] = status_counts.get(rec["status"], 0) + 1
    n = len(certs)
    hashes = {rec["problem_hash"] for rec in certs}
    if len(hashes) != n:
        raise GuardFailure(k, f"唯一问题哈希数 {len(hashes)} 与证书数 {n} 不一致（存在重复问题）")

    metrics_checks = [
        ("qp-solves", float(n)),
        ("qp-status-optimal", float(status_counts.get("optimal", 0))),
        ("qp-status-infeasible", float(status_counts.get("infeasible", 0))),
        ("qp-status-not-converged", float(status_counts.get("not_converged", 0))),
    ]
    for name, value in metrics_checks:
        got = ctx.metric(m, name, k, rel_m)
        if not close(value, got):
            raise GuardFailure(k, f"证书重算 {name}={value} 与 metrics {got} 不一致")
    max_primal = max(rec["primal_residual"] for rec in certs)
    max_dual = max(rec["dual_residual"] for rec in certs)
    max_viol = max(rec["max_constraint_violation"] for rec in certs)
    max_kkt = max(rec["kkt_stationarity_residual"] for rec in certs)
    for name, value in (("qp-max-primal-residual", max_primal), ("qp-max-dual-residual", max_dual),
                        ("qp-max-constraint-violation", max_viol)):
        got = ctx.metric(m, name, k, rel_m)
        if not close(value, got):
            raise GuardFailure(k, f"证书重算 {name}={value!r} 与 metrics {got!r} 不一致")

    grad = out.get("objective_gradient_check")
    if not grad:
        raise TableIncomplete(k, f"{rel_o} 缺少 objective_gradient_check")
    grad_abs = ctx.metric(m, "objective-gradient-fd-max-abs", k, rel_m)
    grad_rel = ctx.metric(m, "objective-gradient-fd-max-rel", k, rel_m)
    checks = [c for c in grad.get("checks", []) if c.get("max_abs_error") is not None]
    if not checks:
        raise TableIncomplete(k, f"{rel_o} objective_gradient_check.checks 没有有限差分读数")
    if not close(max(c["max_abs_error"] for c in checks), grad_abs):
        raise GuardFailure(k, "逐条有限差分绝对差的最大值与 metrics 汇总不一致")
    if not close(max(c["max_rel_error"] for c in checks
                     if c.get("max_rel_error") is not None), grad_rel):
        raise GuardFailure(k, "逐条有限差分相对差的最大值与 metrics 汇总不一致")

    cert = audit.get("certificates", {})
    if not cert:
        raise TableIncomplete(k, f"{rel_a} 缺少 certificates 汇总")
    if int(cert.get("count", -1)) != n:
        raise GuardFailure(k, "复核汇总的证书数与本脚本重算不一致")
    if int(cert.get("unique_problem_hash", -1)) != len(hashes):
        raise GuardFailure(k, "复核汇总的唯一问题哈希数不一致")
    if int(cert.get("internal_inconsistencies", -1)) != 0:
        raise GuardFailure(k, f"{rel_a} 报告内部不一致 {cert.get('internal_inconsistencies')} 处")

    strategy_counts = {}
    for rec in certs:
        strategy_counts[rec["strategy"]] = strategy_counts.get(rec["strategy"], 0) + 1
    max_iter = max(rec.get("iterations", 0) for rec in certs)
    # 198 solves are a REPEATED design: sources x (repeat, fold) contexts x 2 strategies.
    sources = {rec.get("source_beer") for rec in certs}
    contexts = {(rec.get("repeat"), rec.get("fold")) for rec in certs}
    strategies = set(strategy_counts)
    if len(sources) * len(contexts) * len(strategies) != n:
        raise GuardFailure(
            k, f"QP 证书数 {n} 不能由 源 {len(sources)} × 上下文 {len(contexts)} × 策略 "
               f"{len(strategies)} 复算")
    # v6 stale half-space repair: intercept c, identity error and half-space residual are
    # recorded per certificate and aggregated in metrics; recompute both here.
    stale_res_max = max(rec.get("stale_halfspace_residual", 0.0) for rec in certs)
    stale_ident_max = max(rec.get("stale_identity_error", 0.0) for rec in certs)
    stale_c = [rec["stale_intercept_c"] for rec in certs if rec.get("stale_intercept_c") is not None]
    for name, value in (("qp-max-stale-halfspace-residual", stale_res_max),
                        ("qp-max-stale-identity-error", stale_ident_max),
                        ("qp-stale-intercept-c-min", min(stale_c) if stale_c else None),
                        ("qp-stale-intercept-c-max", max(stale_c) if stale_c else None)):
        got = ctx.metric(m, name, k, rel_m)
        if value is None or not close(value, got):
            raise GuardFailure(k, f"证书重算 {name}={value!r} 与 metrics {got!r} 不一致")
    if max(stale_c) >= 0:
        raise GuardFailure(k, f"stale 半空间截距 c 存在非负值（max={max(stale_c)!r}），右端修正未生效")
    verdict_layer = {
        "verified": int(ctx.metric(m, "verdict-verified-primary", k, rel_m)),
        "verified_denominator": int(ctx.metric(m, "verdict-verified-denominator-primary", k, rel_m)),
        "conditional": int(ctx.metric(m, "verdict-conditional-primary", k, rel_m)),
        "not_identifiable": int(ctx.metric(m, "verdict-not-identifiable-primary", k, rel_m)),
        "failed": int(ctx.metric(m, "verdict-failed-primary", k, rel_m)),
        "records": int(ctx.metric(m, "verdict-records-primary", k, rel_m)),
    }
    if verdict_layer["verified_denominator"] + verdict_layer["not_identifiable"] != verdict_layer["records"]:
        raise GuardFailure(k, "源状态分层的可核验分母 + 不可识别 不等于记录总数")
    if verdict_layer["verified"] + verdict_layer["conditional"] + verdict_layer["failed"] != \
            verdict_layer["verified_denominator"]:
        raise GuardFailure(k, "源状态分层的 verified + conditional + failed 不等于可核验分母")

    header = ["指标", "数值", "口径与说明"]
    entries = [
        ("QP 求解次数", f"{n}", f"两种锚定策略分别 {strategy_counts.get('qp-source-anchor', 0)} / "
                               f"{strategy_counts.get('qp-quantile-anchor', 0)} 次"),
        ("求解设计：源 × 训练上下文 × 策略",
         f"{len(sources)} × {len(contexts)} × {len(strategies)}",
         "同一源在 9 个训练上下文里被重复求解：这是重复求解，不是独立样本数"),
        ("状态 optimal", f"{status_counts.get('optimal', 0)}", "solver 返回最优"),
        ("状态 infeasible", f"{status_counts.get('infeasible', 0)}", "声明可行域内未出现不可行问题"),
        ("状态 未收敛", f"{status_counts.get('not_converged', 0)}", "未出现未收敛"),
        ("唯一问题哈希数", f"{len(hashes)}",
         "逐问题哈希互不相同（不同问题实例），但同一源在 9 个训练上下文中被重复求解"),
        ("最大原始残差", fnum(max_primal), "ADMM 一致性分裂的 max |z − w|"),
        ("最大对偶残差", fnum(max_dual), "缩放对偶残差 rho·max|w_k − w_{k−1}|"),
        ("最大约束违反", fnum(max_viol), "box 界与半空间约束的违反量"),
        ("最大 KKT 平稳性残差", fnum(max_kkt), "平滑梯度 + L1 次梯度 + 紧约束乘子的平稳性"),
        ("stale 半空间右端修正：截距 c 范围",
         f"[{fnum(min(stale_c))}, {fnum(max(stale_c))}]",
         f"每折截距由 b = a'z_source + 1e-9 反解，{len(stale_c)} 个证书全部为负"),
        ("stale 半空间最大残差", fnum(stale_res_max), "用修正后的右端复核 a'z − b"),
        ("stale 半空间恒等式误差最大值", fnum(stale_ident_max), "预测值与代理预测通道的恒等式误差"),
        ("源状态分层：verified / conditional / not_identifiable / failed",
         f"{verdict_layer['verified']} / {verdict_layer['conditional']} / "
         f"{verdict_layer['not_identifiable']} / {verdict_layer['failed']}",
         f"共 {verdict_layer['records']} 条上界记录，可核验分母 {verdict_layer['verified_denominator']}；"
         "不可识别记录不计入分母，也不计为失败"),
        ("目标梯度有限差分最大绝对差", fnum(grad_abs), f"{len(checks)} 个检查点的最大值"),
        ("目标梯度有限差分最大相对差", fnum(grad_rel), "同一批检查点"),
        ("策略分布", f"{strategy_counts.get('qp-source-anchor', 0)} / {strategy_counts.get('qp-quantile-anchor', 0)}",
         "QP·源锚定 / QP·分位数锚定"),
        ("最大迭代次数", fint(max_iter), "ADMM 迭代上限内收敛"),
        ("内部不一致记录", "0", "证书字段之间的自洽检查"),
    ]
    rows, csv_rows = [], []
    src = (f"{rel_c}#{n} records | {rel_m}#qp-* | {rel_o}#certificates_summary,objective_gradient_check | "
           f"{rel_a}#certificates")
    for label, value, note_txt in entries:
        rows.append([label, value, note_txt])
        csv_rows.append([label, value, note_txt, src])
    note = (
        f"注：本表是 {n} 个逐问题凸二次规划证书的汇总，不是原生优化验证，也不保证全局最优之外的任何性质。"
        f"{n} 次求解是 {len(sources)} 个源 × {len(contexts)} 个训练上下文 × {len(strategies)} 个策略的"
        "重复求解，不能当作独立样本数。"
        "残差是求解器收敛读数，不是迁移准确率；约束违反为 0 说明解在声明的可行域内，"
        "可行域本身（box 界、一条 stale 半空间、秩 10 二次目标与两处正则项）由模型声明固定。"
        "stale 半空间右端已修正为 b = a'z_source + 1e-9，截距 c 全为负、半空间残差与恒等式误差在浮点误差内；"
        "这只说明约束实现一致，不说明 stale 代理是实测老化指标——它是训练折内的岭回归代理。"
        "目标梯度有限差分只核对实现中的梯度与目标函数一致。"
    )
    fragment = md_table(header, rows, ["l", "r", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["指标", "数值", "口径与说明", "_source"],
        "csv_rows": csv_rows,
        "notes": [f"证书 {n} 条；状态 {status_counts}；唯一哈希 {len(hashes)}；最大迭代 {max_iter}"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- T19
def build_rob_confirmatory(ctx: Ctx, spec: Spec) -> dict:
    k = spec.key
    blocks = [
        ("Q1", ["EXP-0100", "EXP-0101", "EXP-0102"], None,
         "问题一稳健性检验", "问题一候选模型的 A/F30 等权 MAE",
         "只覆盖三个冻结种子中的两个，且参数扰动只改内层正则网格的 λ 倍数。",
         "多种子 + 参数扰动"),
        ("Q2", ["EXP-0125", "EXP-0126"], "EXP-0131",
         "问题二稳健性检验", "问题二 Top-3 平均两两 Jaccard",
         "计划内只有两个执行块（种子块 0 参考 + 种子块 1）；种子块 2 的补充块在登记后执行、未并入计划记录；"
         "台账方法为 param-perturbation（被扰动对象是冻结种子块），不是 multiple-seeds；Jaccard 是集合一致率不是准确率。",
         "param-perturbation（冻结种子块）"),
        ("Q3gen", ["EXP-0127", "EXP-0128"], "EXP-0132",
         "问题三生成稳健性检验", "问题三生成谱的归一化能量距离",
         "计划内只有两个执行块；种子块 2 的补充块在登记后执行、未并入计划记录；"
         "constraint-satisfaction 恒为 1 是构造性质，不参与判定。",
         "param-perturbation（冻结种子块）"),
        ("Q3mig", ["EXP-0129", "EXP-0130"], "EXP-0133",
         "问题三迁移稳健性检验",
         "问题三迁移的综合不增率（四条化学列 + 老化酒花代理合计口径；旧称逐列不增率）",
         "指标有界且饱和（计划内两值均为 1），只能说明没有变差，不能读成强稳健；"
         "198 个 QP 是重复求解；种子块 2 的补充块未并入计划记录。",
         "param-perturbation（冻结种子块）"),
    ]
    header = ["稳健性检验", "对象与指标", "计划执行值（按计划链接块数）", "补充种子块（未并入计划）",
              "绝对极差", "真实相对极差", "判定规则与上限", "判定", "扰动方法", "限制"]
    rows, csv_rows = [], []
    for block, exps, supp_exp, label, metric_label, limitation, methods in blocks:
        plan = ctx.manifest_plan(k, block)
        if plan.get("experimentIds") != exps:
            raise GuardFailure(k, f"{block} 稳健性计划的实验序列 {plan.get('experimentIds')} 与本表不一致")
        key_name = plan["metricKey"]
        values = []
        for exp in exps:
            rel = f"experiments/{exp}/metrics.json"
            metrics = ctx.json(k, rel)
            ctx.cross_check_metrics(k, exp, metrics)
            value = ctx.metric(metrics, key_name, k, rel)
            ctx.assert_ledger(k, exp, key_name, value)
            values.append(value)
        if len(plan.get("values") or []) != len(values):
            raise GuardFailure(k, f"{label} 计划记录值个数 {len(plan.get('values') or [])} 与执行块数 {len(values)} 不一致")
        for got, want in zip(values, plan["values"]):
            if not close(got, want):
                raise GuardFailure(k, f"{label} 执行值 {got!r} 与计划记录 {want!r} 不一致")
        spread = max(values) - min(values)
        if not close(spread, plan["spread"], rel_tol=1e-9):
            raise GuardFailure(k, f"{label} 重算极差 {spread!r} 与计划记录 {plan['spread']!r} 不一致")
        rule = plan["decisionRule"]
        limit = rule.get("limit")
        if rule.get("type") == "min-value":
            rel_spread = spread / abs(values[0]) if values[0] else float("nan")
            rule_text = f"每个取值须 ≥ {fnum(limit)}（min-value）"
            passed = min(values) >= float(limit)
        else:
            rel_spread = spread / abs(values[0]) if values[0] else float("nan")
            rule_text = f"相对极差 ≤ {fnum(limit)}（{rule.get('type')}）"
            passed = rel_spread <= float(limit)
        if bool(passed) != bool(plan["decisionPassed"]):
            raise GuardFailure(k, f"{label} 依规则重算的判定与计划记录不一致")
        # supplementary block: read + cross-check, but never merged into the plan values
        supp_value = None
        supp_src = ""
        if supp_exp:
            rel_supp = f"experiments/{supp_exp}/metrics.json"
            supp_metrics = ctx.json(k, rel_supp)
            ctx.cross_check_metrics(k, supp_exp, supp_metrics)
            supp_value = ctx.metric(supp_metrics, key_name, k, rel_supp)
            ctx.assert_ledger(k, supp_exp, key_name, supp_value)
            supp_src = f"; experiments/{supp_exp}/metrics.json#{key_name} (supplementary, not in plan)"
        rows.append([label, metric_label, " / ".join(fnum(v) for v in values),
                     fnum(supp_value) if supp_value is not None else "—",
                     fnum(spread), fnum(rel_spread), rule_text,
                     "通过" if passed else "未通过", methods, limitation])
        src = ",".join(f"experiments/{e}/metrics.json#{key_name}" for e in exps)
        padded = list(values) + [None] * (3 - len(values))
        csv_rows.append([label, block, key_name, " / ".join(fnum(v) for v in values),
                         padded[0], padded[1], padded[2], supp_value, spread, rel_spread, rule_text,
                         "passed" if passed else "failed", methods, limitation,
                         src + f"; report/evidence_manifest.json#{block}.robustnessPlan" + supp_src])
    note = (
        "注：每行是一次预注册的稳健性检验。“计划执行值”只含计划内已执行的块（问题一 3 块；"
        "问题二/三各 2 块，方法记为 param-perturbation，被扰动对象是冻结种子块），"
        "“补充种子块”是计划登记之后才执行的第三个种子块，单独列出、不并入计划记录，"
        "因此不能把本表读成 n=3 的多种子结果。"
        "绝对极差为计划内取值的最大值减最小值；真实相对极差为绝对极差除以参考值——"
        "台账的 relative spread 以分母 1 计算（reference 为自由文本），本表按真实分母重算并分列。"
        "判定规则与上限在比较之前登记；问题三迁移用 min-value 规则，因指标有界饱和，1.0 是构造上界。"
        "所有判定只描述本组扰动，不构成模型全面稳定的证据。"
    )
    fragment = md_table(header, rows, ["l", "l", "r", "r", "r", "r", "l", "l", "l", "l"]) + "\n\n" + note + "\n"
    ctx._md_by_table[k] = fragment
    return {
        "md": fragment,
        "csv_header": ["稳健性检验", "manifest_block", "metricKey", "plan_values_text",
                       "value_1", "value_2", "value_3", "supplementary_seed_block_value",
                       "absolute_spread", "relative_spread",
                       "decision_rule", "decision", "methods", "limitation", "_source"],
        "csv_rows": csv_rows,
        "notes": ["四行分别对应 evidence_manifest 的四个稳健性计划块；补充种子块单独成列，不并入计划"],
        "shape": "long",
    }


# --------------------------------------------------------------------------- registry
TABLES = [
    Spec("q1-models", "T1 q1-models", "问题一：同协议四模型对照（A/F30、全 50 维、宏平均 R²、Skill）", build_q1_models),
    Spec("q1-groups", "T2 q1-groups", "问题一：三个指标组与九次折外分段的 MAE 与样本数", build_q1_groups),
    Spec("q1-styles", "T3 q1-styles", "问题一：逐风格折外 MAE 与样本数", build_q1_styles),
    Spec("q1-targets", "T4 q1-targets", "问题一：30 个香气/风味维度的逐维 MAE 与 Skill（升序）", build_q1_targets),
    Spec("q1-grades", "T5 q1-grades", "问题一：各模型的 0–6 相对等级一致性", build_q1_grades),
    Spec("q1-scores-aroma", "T6 q1-scores-aroma", "问题一：Beer#1–Beer#10 的香气核心维度相对等级", build_q1_scores_aroma),
    Spec("q1-scores-flavour", "T7 q1-scores-flavour", "问题一：Beer#1–Beer#10 的风味核心维度相对等级", build_q1_scores_flavour),
    Spec("q2-universe", "T8 q2-universe", "问题二：候选宇宙构成（严格榜 / 扩展榜分表）", build_q2_universe),
    Spec("q2-core-top3", "T9 q2-core-top3", "问题二：20 个核心维度的 Top-3 关键化学因素", build_q2_core_top3),
    Spec("q2-full-top3", "T10 q2-full-top3", "问题二：完整 50 维 Top-3（附录长表）", build_q2_full_top3),
    Spec("q2-extended", "T11 q2-extended", "问题二：15 个扩展指标的 Top-3", build_q2_extended),
    Spec("q2-stability", "T12 q2-stability", "问题二：稳定性与同源秩相关对照", build_q2_stability),
    Spec("q3-raw-design", "T13 q3-raw-design", "问题三：未约束原始生成与约束后设计谱对照", build_q3_raw_design),
    Spec("q3-quality", "T14 q3-quality", "问题三：生成质量方案比较与池化范围", build_q3_quality),
    Spec("q3-constraints", "T15 q3-constraints", "问题三：约束核验汇总与逐类满足情况", build_q3_constraints),
    Spec("q3-transfer-stages", "T16 q3-transfer-stages", "问题三：五种迁移策略的转移能量与不增率", build_q3_transfer_stages),
    Spec("q3-transfer-columns", "T17 q3-transfer-columns", "问题三：关键列的三组位移与残差", build_q3_transfer_columns),
    Spec("q3-qp-certs", "T18 q3-qp-certs", "问题三：198 个 QP 求解证书汇总", build_q3_qp_certs),
    Spec("rob-confirmatory", "T19 rob-confirmatory", "四个稳健性检验的确认性结果", build_rob_confirmatory),
]


# --------------------------------------------------------------------------- md hygiene
def assert_md_clean(spec: Spec, fragment: str):
    for pat, what in ((MD_FORBIDDEN_ID, "台账编号"), (MD_FORBIDDEN_RUNLABEL, "内部运行标签")):
        match = pat.search(fragment)
        if match:
            raise GuardFailure(spec.key, f"表格片段含{what} '{match.group(0)}'（正文不得出现内部编号）")


# --------------------------------------------------------------------------- build
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_if_changed(path: Path, text: str) -> str:
    data = text.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return hashlib.sha256(data).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def build_all(verbose: bool = True) -> int:
    import datetime as _dt

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    ctx = Ctx(with_ledger=True)
    index = {
        "kind": "paper-tables-index",
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "script": {"path": "src/paper_tables.py", "sha256": sha256_file(Path(__file__))},
        "allowedExperiments": list(ALLOWED_EXPERIMENTS),
        "selfCheck": {
            "ledger": {"path": LEDGER_REL, "sha256": sha256_file(ROOT / LEDGER_REL),
                       "revision": ctx._ledger.get("revision")},
            "manifest": {"path": MANIFEST_REL, "sha256": sha256_file(ROOT / MANIFEST_REL)},
            "rule": "每个用到的实验指标都与台账同 id 同 key 的值逐位比对；不一致即该表具名失败",
        },
        "tables": {},
    }
    failures = 0
    for spec in TABLES:
        entry = {
            "id": spec.tid,
            "key": spec.key,
            "title": spec.title,
            "status": "INCOMPLETE",
            "complete": False,
            "reason": None,
            "inputs": [],
            "outputs": {"md": None, "csv": None},
            "experiments": [],
            "checks": [],
            "notes": [],
            "csvShape": None,
        }
        try:
            result = spec.builder(ctx, spec)
            fragment = result["md"]
            assert_md_clean(spec, fragment)

            md_path = TABLES_DIR / f"{spec.tid}.md"
            csv_path = TABLES_DIR / f"{spec.tid}.csv"
            md_sha = write_if_changed(md_path, fragment)

            import io
            lines = [",".join(result["csv_header"])]
            for row in result["csv_rows"]:
                if len(row) != len(result["csv_header"]):
                    raise GuardFailure(
                        spec.key, f"csv 行长 {len(row)} 与表头 {len(result['csv_header'])} 不一致")
                lines.append(",".join(_csv_quote(csv_cell(cell)) for cell in row))
            csv_sha = write_if_changed(csv_path, "\n".join(lines) + "\n")

            input_paths = sorted(ctx.inputs_by_table.get(spec.key, set()))
            if not input_paths:
                raise TableIncomplete(spec.key, "没有记录任何输入文件")
            experiments = sorted({m.group(1) for rel in input_paths
                                  for m in [re.search(r"EXP-(\d{4})", rel)] if m})
            for exp in experiments:
                if f"EXP-{exp}" not in ALLOWED_EXPERIMENTS:
                    raise GuardFailure(spec.key, f"输出溯源含白名单外实验 EXP-{exp}")
            entry.update({
                "status": "COMPLETE",
                "complete": True,
                "reason": None,
                "inputs": [{"path": rel, "sha256": sha256_file(ROOT / rel)} for rel in input_paths],
                "outputs": {
                    "md": {"path": f"report/tables/{spec.tid}.md", "sha256": md_sha,
                           "bytes": (TABLES_DIR / f"{spec.tid}.md").stat().st_size},
                    "csv": {"path": f"report/tables/{spec.tid}.csv", "sha256": csv_sha,
                            "bytes": (TABLES_DIR / f"{spec.tid}.csv").stat().st_size},
                },
                "experiments": [f"EXP-{e}" for e in experiments],
                "checks": ctx.checks_by_table.get(spec.key, []),
                "notes": result.get("notes", []),
                "csvShape": result.get("shape"),
                # the four long per-dimension dumps are shipped as support material: printing them costs
                # 13 pages and they are not needed to follow the argument, so the paper cites them instead
                "paperIncluded": spec.tid not in SUPPORT_ONLY_TABLES,
                "supportOnly": spec.tid in SUPPORT_ONLY_TABLES,
            })
            if verbose:
                print(f"[ok] {spec.key}: md {md_sha[:12]} csv {csv_sha[:12]} "
                      f"inputs {len(input_paths)} experiments {len(experiments)}")
        except TableIncomplete as exc:
            failures += 1
            entry["reason"] = exc.detail
            entry["inputs"] = [{"path": rel, "sha256": (sha256_file(ROOT / rel) if (ROOT / rel).is_file() else None)}
                               for rel in sorted(ctx.inputs_by_table.get(spec.key, set()))]
            entry["experiments"] = sorted({f"EXP-{m.group(1)}" for rel in ctx.inputs_by_table.get(spec.key, set())
                                           for m in [re.search(r"EXP-(\d{4})", rel)] if m})
            entry["checks"] = ctx.checks_by_table.get(spec.key, [])
            entry["csvShape"] = None
            print(f"TABLE {spec.key} INCOMPLETE: {exc.detail}", file=sys.stderr)
        index["tables"][spec.key] = entry

    payload = json.dumps(index, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    write_if_changed(INDEX_PATH, payload)
    complete = sum(1 for e in index["tables"].values() if e["complete"])
    print(f"\nbuilt {complete}/{len(TABLES)} tables -> {INDEX_PATH.relative_to(ROOT)}")
    if failures:
        print(f"{failures} table(s) INCOMPLETE", file=sys.stderr)
        return 1
    return 0


def _csv_quote(text: str) -> str:
    if any(ch in text for ch in (",", '"', "\n", "\r")):
        return '"' + text.replace('"', '""') + '"'
    return text


# --------------------------------------------------------------------------- verify
def verify() -> int:
    if not INDEX_PATH.is_file():
        print(f"缺少 {INDEX_PATH.relative_to(ROOT)}，先运行 --build", file=sys.stderr)
        return 1
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    problems = 0
    for key, entry in index["tables"].items():
        if not entry["complete"]:
            print(f"[--] {key}: INCOMPLETE ({entry['reason']})")
            continue
        for kind in ("md", "csv"):
            rec = entry["outputs"][kind]
            path = ROOT / rec["path"]
            if not path.is_file():
                print(f"[FAIL] {key}.{kind}: 缺少输出 {rec['path']}")
                problems += 1
                continue
            got = sha256_file(path)
            if got != rec["sha256"]:
                print(f"[FAIL] {key}.{kind}: sha256 不一致 {got} != {rec['sha256']}")
                problems += 1
        for inp in entry["inputs"]:
            path = ROOT / inp["path"]
            if not path.is_file():
                print(f"[FAIL] {key}: 输入消失 {inp['path']}")
                problems += 1
                continue
            if inp["sha256"] and sha256_file(path) != inp["sha256"]:
                print(f"[INPUT-CHANGED] {key}: {inp['path']} 与建表时字节不同")
                problems += 1
        if entry["complete"]:
            print(f"[ok] {key}: md/csv sha256 与 INDEX 一致，{len(entry['inputs'])} 个输入未变")
    total = len(index["tables"])
    done = sum(1 for e in index["tables"].values() if e["complete"])
    print(f"\nverify: {done}/{total} complete, {problems} problem(s)")
    return 0 if problems == 0 else 1


# --------------------------------------------------------------------------- splice
SPLICE_BEGIN = "<!-- table-begin:{tid} sha256={sha} -->"
SPLICE_END = "<!-- table-end:{tid} -->"


def _aliases() -> dict:
    table = {}
    for spec in TABLES:
        for alias in (spec.tid, spec.key, spec.tid.upper(), spec.key.split(" ", 1)[0]):
            table[alias] = spec
    return table


def _load_fragments():
    if not INDEX_PATH.is_file():
        raise SystemExit(f"缺少 {INDEX_PATH.relative_to(ROOT)}，先运行 --build")
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    fragments = {}
    for spec in TABLES:
        entry = index["tables"].get(spec.key)
        if not entry or not entry["complete"]:
            raise SystemExit(f"表格 {spec.key} 未完成，不能 splice")
        path = ROOT / entry["outputs"]["md"]["path"]
        text = path.read_text(encoding="utf-8")
        if sha256_file(path) != entry["outputs"]["md"]["sha256"]:
            raise SystemExit(f"{entry['outputs']['md']['path']} 与 INDEX 的 sha256 不符，先重新 --build")
        fragments[spec.tid] = (text, entry["outputs"]["md"]["sha256"])
    return fragments


def splice(target: str) -> int:
    path = Path(target)
    if not path.is_absolute():
        path = ROOT / target
    if not path.is_file():
        print(f"目标文件不存在：{path}", file=sys.stderr)
        return 1
    if path.resolve() == (ROOT / "report" / "paper.md").resolve():
        # explicit guard: this script must not rewrite the paper source
        print("拒绝直接改写 report/paper.md（论文写域不属本工具）", file=sys.stderr)
        return 1
    fragments = _load_fragments()
    aliases = _aliases()
    original = path.read_text(encoding="utf-8")
    out_lines = []
    replaced = 0
    skipped_blocks = 0
    i = 0
    lines = original.splitlines()
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        begin_match = re.match(r"^<!--\s*table-begin:\s*([A-Za-z0-9\- ]+?)\s+sha256=[0-9a-f]+\s*-->$", stripped)
        if begin_match and begin_match.group(1).strip() in aliases:
            tid = aliases[begin_match.group(1).strip()].tid
            end_marker = SPLICE_END.format(tid=tid).strip()
            j = i + 1
            while j < len(lines) and lines[j].strip() != end_marker:
                j += 1
            if j >= len(lines):
                print(f"未闭合的表格块：{stripped}", file=sys.stderr)
                return 1
            skipped_blocks += 1
            i = j + 1
            continue
        token = re.match(r"^<!--\s*TABLE:\s*(.+?)\s*-->$", stripped)
        if token:
            alias = token.group(1).strip()
            spec = aliases.get(alias)
            if spec is None:
                print(f"未知表占位：{alias}", file=sys.stderr)
                return 1
            text, sha = fragments[spec.tid]
            body = text.rstrip("\n")
            out_lines.append(SPLICE_BEGIN.format(tid=spec.tid, sha=sha))
            out_lines.extend(body.split("\n"))
            out_lines.append(SPLICE_END.format(tid=spec.tid))
            replaced += 1
            i += 1
            continue
        out_lines.append(line)
        i += 1
    new_text = "\n".join(out_lines)
    if original.endswith("\n"):
        new_text += "\n"
    if replaced == 0 and skipped_blocks > 0:
        print(f"未发现 <!-- TABLE:... --> 占位；已跳过 {skipped_blocks} 个既有表格块，文件未改动")
    else:
        if new_text != original:
            path.write_text(new_text, encoding="utf-8")
            print(f"已替换 {replaced} 个占位，移除 {skipped_blocks} 个旧表格块 -> {path}")
        else:
            print(f"已替换 {replaced} 个占位（内容未变，字节一致）")
    return 0


# --------------------------------------------------------------------------- main
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="构建证据驱动的论文表格")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--build", action="store_true", help="生成全部表格与 INDEX.json（默认）")
    group.add_argument("--verify", action="store_true", help="重算 sha256 并与 INDEX.json 比对")
    group.add_argument("--splice", metavar="PATH", help="把 <!-- TABLE:<id> --> 替换为表格片段")
    args = parser.parse_args(argv)
    if args.verify:
        return verify()
    if args.splice:
        return splice(args.splice)
    return build_all()


if __name__ == "__main__":
    sys.exit(main())
