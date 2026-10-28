#!/usr/bin/env python3
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""build_paper.py — table/claim-aware LaTeX builder for the MathorCup paper.

SINGLE SOURCE, ONE PATH
-----------------------
One markdown file goes in; one intermediate markdown, one .tex and (optionally)
one .pdf come out:

    <source> --(deterministic transform)--> paper.pandoc.md
             --(pandoc, template + header)--> paper.tex --(xelatex x2)--> paper.pdf

The transform resolves the paper's *structural* placeholders only:

  * ``<!-- table-begin:<id> sha256=... --> ... <!-- table-end:<id> -->`` blocks
    are validated against ``report/tables/INDEX.json`` + the fragment file bytes
    and converted to booktabs LaTeX tables (long -> longtable, wide -> resizebox
    or wrapped p{} columns, landscape for the long wide appendix tables).  Cell
    text is escaped for LaTeX but **never edited**: digits, units and order stay
    byte-identical.
  * ``**表 <id>　<caption>**`` lines immediately above a block become the table
    caption (numbered by LaTeX); the table id stays visible in the caption and in
    a ``%% table-id: ...`` comment for traceability.
  * ``{{claim:CLAIM-xxxx}}`` becomes a small-font framed evidence-registry block
    whose statement / evidence / limitations are copied verbatim from the ledger
    (never deleted, never reordered).
  * ``{{figure:FIG-xxxx}}`` becomes an ``\\includegraphics`` figure whose path,
    sha256 and caption come from ``state/ledger.json``.
  * ``<!-- PENDING-FIGURE:... -->`` is a NAMED REJECTION (a figure is not allowed
    to reach the paper as an empty placeholder).

Named rejections (non-zero exit, every hit printed with file:line):
  unresolved ``{{...}}``, ``PENDING-FIGURE``, ``@@``, retired claims
  (CLAIM-0012/0014/0018/0019/0021/0022), pilot-round experiments
  (EXP-0038..0072, EXP-0076, EXP-0077), fake FIG ids (not in the ledger, or
  retired), and table blocks whose sha256 disagrees with INDEX.json.

MODES
-----
``--check``     read-only structural audit; writes NOTHING.
``--selftest``  builds a small real-fragment document under .rework/build-test/,
                asserts the expected LaTeX environments, and compiles it to PDF
                *inside the test directory only* (reports honestly if it fails).
``--build``     writes paper.tex (+ PDF with --pdf) to --outdir only.  Writing
                report/paper.tex / report/paper.pdf requires the explicit
                --allow-report-output flag; it is refused by default.

This batch must not produce the official report/paper.tex|pdf, so only --check
and --selftest are meant to be run now.

Run from the project root (or anywhere; paths are resolved against the project):
    python src/build_paper.py --check --source report/paper.md
    python src/build_paper.py --selftest
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE = ROOT / "report" / "rendered.md"
PAPER_MD = ROOT / "report" / "paper.md"
INDEX_PATH = ROOT / "report" / "tables" / "INDEX.json"
LEDGER_PATH = ROOT / "state" / "ledger.json"
MANIFEST_PATH = ROOT / "report" / "evidence_manifest.json"
BUILD_DIR = ROOT / "src" / "build"
HEADER_PATH = BUILD_DIR / "header.tex"
TEMPLATE_PATH = BUILD_DIR / "template.tex"
TEST_ROOT = ROOT / ".rework" / "build-test"
PANDOC = shutil.which("pandoc") or "pandoc"
XELATEX = shutil.which("xelatex") or "xelatex"

TEX_NAME = "paper.tex"
PDF_NAME = "paper.pdf"
MD_NAME = "paper.pandoc.md"
SIDECAR_NAME = "paper.build.json"

TABLE_RE = re.compile(
    r"<!-- table-begin:(?P<id>\S+) sha256=(?P<sha>[0-9a-f]{64}) -->\n"
    r"(?P<body>.*?)\n"
    r"<!-- table-end:(?P=id) -->",
    re.S,
)
CAPTION_RE = re.compile(r"^\*\*表\s+(?P<id>\S+?)[\u3000\s]+(?P<cap>.+?)\*\*\s*$")
PENDING_RE = re.compile(r"<!--\s*PENDING-FIGURE:(?P<name>[^>]*?)\s*-->")
CLAIM_RE = re.compile(r"\{\{claim:(?P<id>CLAIM-\d{4})\}\}")
FIGURE_RE = re.compile(r"\{\{figure:(?P<id>FIG-\d{4})\}\}")
METRIC_RE = re.compile(r"\{\{metric:(?P<exp>EXP-\d{4}):(?P<key>[^}]+)\}\}")
ANY_PLACEHOLDER_RE = re.compile(r"\{\{[^}]*\}\}")
FIG_ID_RE = re.compile(r"FIG-\d{4}")
CLAIM_ID_RE = re.compile(r"CLAIM-\d{4}")
EXP_ID_RE = re.compile(r"EXP-\d{4}")
H1_RE = re.compile(r"^#\s+(?P<text>.+?)\s*$")
HEADING_NUM_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)[\s\u3000]")
SECTION_REF_RE = re.compile(r"§\s?(?P<num>\d+(?:\.\d+)*)")

RETIRED_CLAIMS = ("CLAIM-0012", "CLAIM-0014", "CLAIM-0018", "CLAIM-0019",
                  "CLAIM-0021", "CLAIM-0022")
PILOT_EXP_RE = re.compile(
    r"EXP-(?:00(?:3[89]|4\d|5\d|6\d|7[0-2])|007[67])\b"
)
EXPECTED_TABLES = 19
EXPECTED_CLAIMS = 8
EXPECTED_FIGURES = 10
CAPTION_IDS = True          # --caption-ids/--no-caption-ids; guards internal ids in captions
REQUIRED_PACKAGES = (
    "booktabs", "longtable", "array", "graphicx", "lscape", "xcolor",
    "caption", "geometry", "fontspec", "xeCJK", "amsmath", "amssymb",
)
REQUIRED_FONTS = ("Songti SC", "Times New Roman")

# A4 minus 2 x 2.2 cm margins = 16.6 cm ~= 470.6 pt; used only to *estimate*
# whether a table needs wrapping/resizing, never to alter any cell text.
TEXTWIDTH_PT = 470.0
TEXTWIDTH_LANDSCAPE_PT = 700.0  # lscape sets \linewidth to \textheight
TABLE_PAD_PT = 6.0          # 2 * \tabcolsep (3pt) per column
LONG_ROW_THRESHOLD = 14     # >= this many data rows -> longtable (page-breaking)
PROSE_CELL_CHARS = 24       # a text column this wide is wrapped with p{}
RESIZE_MIN_SCALE = 0.92     # native width / textwidth below this -> plain tabular


# --------------------------------------------------------------------------- #
# small utilities
# --------------------------------------------------------------------------- #
def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_to_root(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def is_wide_char(ch: str) -> bool:
    if ch in "\u3000\uFF5C":
        return True
    return unicodedata.east_asian_width(ch) in ("W", "F")


def visual_len(text: str) -> int:
    return sum(2 if is_wide_char(ch) else 1 for ch in text)


def est_pt(text: str, font_pt: float = 11.0) -> float:
    """Rough typeset width estimate: CJK ~1em, ASCII ~0.52em."""
    return sum(font_pt if is_wide_char(ch) else 0.52 * font_pt for ch in text)


def has_cjk(text: str) -> bool:
    return any(is_wide_char(ch) for ch in text)


def line_no_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


LATEX_ESCAPES = (
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)


def latex_escape(text: str) -> str:
    out = []
    for ch in text:
        replaced = None
        for src, dst in LATEX_ESCAPES:
            if ch == src:
                replaced = dst
                break
        out.append(replaced if replaced is not None else ch)
    return "".join(out)


INLINE_TOKEN_RE = re.compile(r"(`[^`]+`|\*\*.+?\*\*)")


def latex_inline(text: str) -> str:
    """Convert one line/paragraph of plain (non-math) source text to LaTeX.

    Only two inline constructs are honoured -- ``code`` and **bold** -- because
    that is all the claim statements, table notes and the DRAFT banner use.
    Everything else is escaped literally, so no character of a claim statement or
    note is dropped or reinterpreted.
    """
    pieces = INLINE_TOKEN_RE.split(text)
    out: List[str] = []
    for piece in pieces:
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**") and len(piece) >= 4:
            out.append(r"\textbf{" + latex_escape(piece[2:-2]) + "}")
        elif piece.startswith("`") and piece.endswith("`") and len(piece) >= 2:
            out.append(r"\texttt{" + latex_escape(piece[1:-1]) + "}")
        else:
            out.append(latex_escape(piece))
    return "".join(out)


# --------------------------------------------------------------------------- #
# findings
# --------------------------------------------------------------------------- #
@dataclass
class Finding:
    code: str
    path: str
    line: Optional[int]
    detail: str

    def render(self) -> str:
        loc = self.path if self.line is None else f"{self.path}:{self.line}"
        return f"{loc}  {self.code}  {self.detail}"


@dataclass
class Findings:
    rejects: List[Finding] = field(default_factory=list)
    warns: List[Finding] = field(default_factory=list)
    passes: List[Tuple[str, str]] = field(default_factory=list)

    def reject(self, code: str, path: str, line: Optional[int], detail: str) -> None:
        self.rejects.append(Finding(code, path, line, detail))

    def warn(self, code: str, path: str, line: Optional[int], detail: str) -> None:
        self.warns.append(Finding(code, path, line, detail))

    def ok(self, code: str, detail: str) -> None:
        self.passes.append((code, detail))


# --------------------------------------------------------------------------- #
# project inputs
# --------------------------------------------------------------------------- #
@dataclass
class ProjectData:
    index: Dict[str, Any]
    ledger: Dict[str, Any]
    manifest: Optional[Dict[str, Any]]
    tables_by_id: Dict[str, Dict[str, Any]]
    claims: Dict[str, Dict[str, Any]]
    figures: Dict[str, Dict[str, Any]]


_INDEX_PATH: Path = INDEX_PATH


def set_index_path(path: Optional[Path]) -> None:
    """Allow --index (used by tests) without changing the default."""
    global _INDEX_PATH
    _INDEX_PATH = Path(path).resolve() if path else INDEX_PATH


def load_project() -> ProjectData:
    index = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    manifest = None
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    tables_by_id = {rec["id"]: rec for rec in index.get("tables", {}).values()}
    claims = {rec["id"]: rec for rec in ledger.get("claims", [])}
    figures = {rec["id"]: rec for rec in ledger.get("figures", [])}
    return ProjectData(index, ledger, manifest, tables_by_id, claims, figures)


def figure_is_active(rec: Dict[str, Any]) -> bool:
    return str(rec.get("status") or "active").lower() not in ("superseded", "retired")


def table_flags(rec: Dict[str, Any]) -> Tuple[bool, bool]:
    """Return (paperIncluded, supportOnly) with backwards-compatible defaults.

    INDEX.json now carries both flags per table.  Older indexes have neither, so
    such a table keeps the pre-flag behaviour: it is expected in the paper.
    """
    inc = rec.get("paperIncluded")
    sup = rec.get("supportOnly")
    if inc is None and sup is None:
        return True, False
    if inc is None:
        inc = not bool(sup)
    if sup is None:
        sup = not bool(inc)
    return bool(inc), bool(sup)


def expected_table_sets(data: ProjectData) -> Tuple[set, set]:
    inline: set = set()
    support: set = set()
    for tid, rec in data.tables_by_id.items():
        inc, sup = table_flags(rec)
        if inc:
            inline.add(tid)
        if sup:
            support.add(tid)
    return inline, support


def support_only_checks(data: ProjectData) -> List[Dict[str, Any]]:
    """Validate supportOnly fragments against INDEX (never for paper presence)."""
    _, support = expected_table_sets(data)
    results: List[Dict[str, Any]] = []
    for tid in sorted(support):
        rec = data.tables_by_id[tid]
        outputs = rec.get("outputs") or {}
        for kind in ("md", "csv"):
            meta = outputs.get(kind)
            if not meta or not meta.get("path"):
                continue
            path = ROOT / meta["path"]
            want = meta.get("sha256")
            if not path.exists():
                results.append({"tableId": tid, "kind": kind, "path": meta["path"],
                                "code": "SUPPORT_ONLY_FRAGMENT_MISSING",
                                "detail": f"supportOnly table {tid}: {kind} file "
                                          f"{meta['path']} is missing"})
                continue
            got = sha256_file(path)
            if want and got != want:
                results.append({"tableId": tid, "kind": kind, "path": meta["path"],
                                "code": "SUPPORT_ONLY_SHA_MISMATCH",
                                "detail": f"supportOnly table {tid}: {kind} file sha256={got} "
                                          f"but INDEX records {want}"})
    return results


def count_expanded_claims(source_text: str, data: ProjectData) -> int:
    """Count active claim statements found verbatim (upstream render expanded them)."""
    def compact(text: str) -> str:
        return re.sub(r"[\\\s*_`${}~^]", "", text)

    source = compact(source_text)
    found = 0
    for cid, rec in data.claims.items():
        if str(rec.get("status") or "").lower() != "active":
            continue
        statement = str(rec.get("statement") or "")
        fragment = None
        for m in re.finditer(r"[0-9A-Za-z\u4e00-\u9fff]{10,}", statement):
            fragment = m.group(0)[:24]
            break
        if fragment and compact(fragment) in source:
            found += 1
    return found


# --------------------------------------------------------------------------- #
# tables: parsing + LaTeX rendering
# --------------------------------------------------------------------------- #
def split_pipe_row(line: str) -> Optional[List[str]]:
    """Split a markdown pipe-table row, honouring the ``\\|`` escape.

    Returns None for a line that is not a pipe row.  An escaped pipe becomes a
    literal ``|`` inside the cell (this is exactly the source's intent, e.g. the
    ``max\\|z - w\\|`` cells of table q3-qp-certs).
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    body = stripped[1:]
    if body.endswith("|"):
        body = body[:-1]
    cells: List[str] = []
    current: List[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            current.append("|")
            i += 2
            continue
        if ch == "\\" and i + 1 < len(body):
            current.append(ch)
            current.append(body[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    cells.append("".join(current).strip())
    return cells


def parse_alignment(separator: str) -> str:
    token = separator.strip()
    if token.startswith(":") and token.endswith(":"):
        return "c"
    if token.endswith(":"):
        return "r"
    return "l"


def is_numeric_cell(cell: str) -> bool:
    if not cell or has_cjk(cell):
        return False
    return re.fullmatch(
        r"[\s0-9.,%+\-−–—/×≤≥<>=~^eE()]*", cell
    ) is not None and any(ch.isdigit() for ch in cell)


def numeric_column(cells: Sequence[str]) -> bool:
    non_empty = [c for c in cells if c not in ("", "—", "-", "–")]
    if not non_empty:
        return False
    hits = sum(1 for c in non_empty if is_numeric_cell(c))
    return hits / len(non_empty) >= 0.6


@dataclass
class Panel:
    header: List[str]
    aligns: List[str]
    rows: List[List[str]]


@dataclass
class TableSpec:
    tid: str
    sha: str
    caption: str
    panels: List[Panel]
    note: str
    line: int

    @property
    def ncols(self) -> int:
        return max(len(p.header) for p in self.panels)

    @property
    def nrows(self) -> int:
        return sum(len(p.rows) for p in self.panels)


def parse_table_block(match: re.Match, source_text: str,
                      data: ProjectData, findings: Findings,
                      source_label: str) -> Optional[TableSpec]:
    tid = match.group("id")
    header_sha = match.group("sha")
    body = match.group("body")
    line = line_no_of(source_text, match.start())
    rec = data.tables_by_id.get(tid)
    if rec is None:
        findings.reject("TABLE_ID_UNKNOWN", source_label, line,
                        f"table id {tid!r} is not registered in report/tables/INDEX.json")
        return None
    want = rec.get("outputs", {}).get("md", {}).get("sha256")
    if want != header_sha:
        findings.reject("TABLE_SHA_MISMATCH", source_label, line,
                        f"block {tid}: header sha256={header_sha} but INDEX says {want}")
        return None
    frag_path = ROOT / rec["outputs"]["md"]["path"]
    if not frag_path.exists():
        findings.reject("TABLE_FRAGMENT_MISSING", source_label, line,
                        f"block {tid}: fragment {rec['outputs']['md']['path']} is missing")
        return None
    frag_text = frag_path.read_text(encoding="utf-8")
    frag_sha = sha256_text(frag_text)
    if frag_sha != want:
        findings.reject("TABLE_SHA_MISMATCH", source_label, line,
                        f"block {tid}: fragment bytes sha256={frag_sha} but INDEX says {want}")
        return None
    if body != frag_text.rstrip("\n"):
        findings.reject("TABLE_BODY_MISMATCH", source_label, line,
                        f"block {tid}: inlined body differs from fragment bytes")
        return None

    # one block may hold several stacked pipe tables (q3-constraints has two
    # panels, i.e. 上表 / 下表, plus ONE note for the whole block)
    segments: List[List[str]] = []
    current: List[str] = []
    for raw_line in body.split("\n"):
        if raw_line.strip():
            current.append(raw_line)
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)

    panels: List[Panel] = []
    note_parts: List[str] = []
    for segment in segments:
        pipe_lines = [ln for ln in segment if ln.strip().startswith("|")]
        other = [ln.strip() for ln in segment if not ln.strip().startswith("|")]
        note_parts.extend(other)
        if not pipe_lines:
            continue
        if len(pipe_lines) < 3:
            findings.reject("TABLE_SHAPE_MISMATCH", source_label, line,
                            f"block {tid}: a panel needs header + separator + at least one data row")
            return None
        rows = [split_pipe_row(ln) for ln in pipe_lines]
        if any(r is None for r in rows):
            findings.reject("TABLE_SHAPE_MISMATCH", source_label, line,
                            f"block {tid}: unparsable pipe row")
            return None
        header = rows[0]  # type: ignore[assignment]
        separator = rows[1]  # type: ignore[assignment]
        data_rows = rows[2:]  # type: ignore[assignment]
        if any(len(r) != len(header) for r in data_rows) or len(separator) != len(header):
            findings.reject("TABLE_SHAPE_MISMATCH", source_label, line,
                            f"block {tid}: column count differs between header/separator/rows")
            return None
        if not all(re.fullmatch(r":?-{2,}:?", tok.strip()) for tok in separator):
            findings.reject("TABLE_SHAPE_MISMATCH", source_label, line,
                            f"block {tid}: second row of a panel is not a markdown alignment row")
            return None
        panels.append(Panel(header=header,  # type: ignore[arg-type]
                            aligns=[parse_alignment(tok) for tok in separator],  # type: ignore[arg-type]
                            rows=data_rows))  # type: ignore[arg-type]
    if not panels:
        findings.reject("TABLE_SHAPE_MISMATCH", source_label, line,
                        f"block {tid}: no pipe table found inside the block")
        return None
    return TableSpec(tid=tid, sha=header_sha, caption="", panels=panels,
                     note=" ".join(note_parts), line=line)


def char_width_pt(ch: str, font_pt: float) -> float:
    return font_pt if is_wide_char(ch) else 0.52 * font_pt


def is_break_after(text: str, i: int) -> bool:
    """True where LaTeX may break a line WITHOUT changing the visible text.

    Only separators that never split a numeric value are used:
      * after ``/``, ``｜`` and ``·`` (value-pair / cell-internal separators),
      * after ``.`` ``_`` ``-`` when BOTH neighbours are ASCII letters, so
        ``isopentyl_acetate`` may wrap but ``0.3982`` may never be split.
    CJK characters break on their own and are not listed here.
    """
    ch = text[i]
    if ch in "/｜·":
        return True
    if ch in "._-" and 0 < i < len(text) - 1:
        return text[i - 1].isalpha() and text[i + 1].isalpha()
    return False


def min_cell_width_pt(text: str, font_pt: float) -> float:
    """Width of the longest unbreakable chunk of a cell (see is_break_after)."""
    widest = 0.0
    current = 0.0
    for i, ch in enumerate(text):
        if is_wide_char(ch):
            widest = max(widest, current, font_pt)
            current = 0.0
            continue
        current += char_width_pt(ch, font_pt)
        if ch == " ":
            widest = max(widest, current - char_width_pt(ch, font_pt))
            current = 0.0
        elif is_break_after(text, i):
            widest = max(widest, current)
            current = 0.0
    widest = max(widest, current)
    return widest


def latex_cell(text: str) -> str:
    """Escape a cell and add invisible line-break opportunities.

    The visible characters are unchanged; only where LaTeX may wrap long ASCII
    identifiers changes (long compound names otherwise overrun p{} columns).
    """
    out: List[str] = []
    for i, ch in enumerate(text):
        out.append(latex_escape(ch))
        if is_break_after(text, i):
            out.append(r"\allowbreak{}")
    return "".join(out)


def panel_metrics(panel: Panel) -> Dict[str, Any]:
    ncols = len(panel.header)
    max_pt: List[float] = []
    max_chars: List[int] = []
    numeric: List[bool] = []
    for j in range(ncols):
        cells = [panel.header[j]] + [row[j] for row in panel.rows]
        max_pt.append(max(est_pt(c) for c in cells))
        max_chars.append(max(visual_len(c) for c in cells))
        numeric.append(numeric_column([row[j] for row in panel.rows]))
    native_pt = sum(max_pt) + TABLE_PAD_PT * ncols
    prose_cols = [j for j in range(ncols) if not numeric[j] and max_chars[j] >= PROSE_CELL_CHARS]
    return {"ncols": ncols, "nrows": len(panel.rows), "max_pt": max_pt,
            "max_chars": max_chars, "numeric": numeric,
            "native_ratio": native_pt / TEXTWIDTH_PT, "prose_cols": prose_cols}


FONT_PT = {"normalsize": 11.0, "small": 10.0, "footnotesize": 9.0,
           "scriptsize": 8.0, "tiny": 6.0}


def plan_panel_widths(panel: Panel, font: str, line_pt: float) -> Optional[List[float]]:
    """Return per-column \\linewidth fractions, or None if the panel cannot fit."""
    font_pt = FONT_PT.get(font, 10.0)
    ncols = len(panel.header)
    min_frac: List[float] = []
    weights: List[float] = []
    for j in range(ncols):
        cells = [panel.header[j]] + [row[j] for row in panel.rows]
        min_pt = max(min_cell_width_pt(c, font_pt) for c in cells) + 3.0
        # p{..} = frac*\linewidth - 2*\tabcolsep (6pt); require p >= min_pt
        min_frac.append((min_pt + TABLE_PAD_PT) / line_pt)
        weight = max(est_pt(c) * (font_pt / 11.0) for c in cells)
        weights.append(min(max(weight, 30.0), 260.0))
    if sum(min_frac) > 0.96:
        return None
    fracs = [w / sum(weights) for w in weights]
    for _ in range(6):
        fracs = [max(fracs[j], min_frac[j]) for j in range(ncols)]
        total = sum(fracs)
        if abs(total - 0.968) < 1e-6:
            break
        if total > 0.968:
            excess = total - 0.968
            flexible = [j for j in range(ncols)
                        if fracs[j] > min_frac[j] + 1e-9]
            slack = sum(fracs[j] - min_frac[j] for j in flexible)
            if not flexible or slack <= 1e-9:
                return None
            for j in flexible:
                fracs[j] -= excess * (fracs[j] - min_frac[j]) / slack
        else:
            scale = 0.968 / total
            fracs = [f * scale for f in fracs]
    return fracs


def plan_widths(spec: TableSpec, font: str, landscape: bool) -> Optional[List[List[float]]]:
    line_pt = TEXTWIDTH_LANDSCAPE_PT if landscape else TEXTWIDTH_PT
    plans: List[List[float]] = []
    for panel in spec.panels:
        plan = plan_panel_widths(panel, font, line_pt)
        if plan is None:
            return None
        plans.append(plan)
    return plans


def layout_table(spec: TableSpec, wide: str = "rotate") -> Dict[str, Any]:
    metrics = [panel_metrics(p) for p in spec.panels]
    ratio = max(m["native_ratio"] for m in metrics)
    prose = any(m["prose_cols"] for m in metrics)
    ncols = spec.ncols
    nrows = spec.nrows
    multi = len(spec.panels) > 1
    long = nrows >= LONG_ROW_THRESHOLD
    wide_long = long and ncols >= 8
    base_font = ("small" if (not long and ratio <= 1.0) else
                 "footnotesize" if (prose or ratio > 1.55) else "small")
    if multi and not long:
        base_font = "small" if ratio <= 1.0 else "footnotesize"
    candidates = ["small", "footnotesize", "scriptsize"]
    if not long and not multi:
        candidates = ["small", "footnotesize"]
    chosen: Optional[Dict[str, Any]] = None
    # Short tables with modest natural width are simply scaled to the text width
    # (no wrapping): that keeps cells on one line and is the cheapest to read.
    if not long and not multi and not prose and ratio <= 1.55:
        layout = "minipage-tabular" if ratio <= RESIZE_MIN_SCALE else "minipage-resizebox"
        chosen = {"layout": layout, "font": "small", "use_p_columns": False,
                  "landscape": False, "widths": None}
    # Wide short tables that would need tiny type portrait are rotated instead
    # (sidewaystable + small font): the rotated page width is \textheight, so the
    # table keeps a readable size.  The note is emitted INSIDE the float.
    if chosen is None and wide == "rotate" and not long and not multi and ncols >= 9:
        if ratio * TEXTWIDTH_PT <= 650.0:
            chosen = {"layout": "sidewaystable", "font": "small",
                      "use_p_columns": False, "landscape": True, "widths": None}
        else:
            for font in ("small", "footnotesize", "scriptsize"):
                plans = plan_widths(spec, font, True)
                if plans:
                    chosen = {"layout": "sidewaystable", "font": font,
                              "use_p_columns": True, "landscape": True,
                              "widths": plans}
                    break
    for landscape in ([] if chosen else
                      ([True, False] if (wide_long or (long and not multi)) else [False])):
        if landscape and not (wide_long or ncols >= 7):
            continue
        for font in candidates:
            plans = plan_widths(spec, font, landscape)
            if plans is None:
                continue
            layout = ("longtable-landscape" if landscape else
                      "longtable" if long else
                      "minipage-p")
            chosen = {"layout": layout, "font": font, "use_p_columns": True,
                      "landscape": landscape, "widths": plans}
            if layout == "longtable-landscape":
                break
            # portrait fit: stop at the largest font that fits, but keep looking
            # for a narrower one only when the first fit is very tight
            break
        if chosen is not None:
            break
    if chosen is None and long:
        # cannot fit with p{} columns: fall back to the smallest font portrait
        chosen = {"layout": "longtable", "font": "scriptsize", "use_p_columns": True,
                  "landscape": False,
                  "widths": [plan_panel_widths(p, "scriptsize", TEXTWIDTH_PT)
                             or [0.9 / len(p.header)] * len(p.header)
                             for p in spec.panels]}
    if chosen is None:
        resize_font = "small"
        chosen = {"layout": "minipage-resizebox", "font": resize_font,
                  "use_p_columns": False, "landscape": False, "widths": None}
    chosen.update({
        "id": spec.tid,
        "rows": nrows,
        "cols": ncols,
        "panels": len(spec.panels),
        "native_estimate_ratio": round(ratio, 3),
        "prose_columns": [m["prose_cols"] for m in metrics],
    })
    return chosen


def column_spec(panel: Panel, layout: Dict[str, Any], panel_index: int) -> str:
    if not layout["use_p_columns"]:
        return "@{}" + "".join(panel.aligns) + "@{}"
    numeric = panel_metrics(panel)["numeric"]
    widths = layout["widths"][panel_index]
    parts = []
    for j, frac in enumerate(widths):
        align = r"\raggedleft" if numeric[j] else r"\raggedright"
        parts.append(
            r">{" + align + r"\arraybackslash}p{\dimexpr "
            + f"{frac:.4f}" + r"\linewidth-6pt\relax}"
        )
    return "@{}" + "".join(parts) + "@{}"


def render_panel(panel: Panel, layout: Dict[str, Any], panel_index: int) -> List[str]:
    spec = column_spec(panel, layout, panel_index)
    lines = [r"\begin{tabular}{" + spec + "}", r"\toprule"]
    lines.append(" & ".join(latex_cell(c) for c in panel.header) + r" \\")
    lines.append(r"\midrule")
    for row in panel.rows:
        lines.append(" & ".join(latex_cell(c) for c in row) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return lines


def render_table(spec: TableSpec, layout: Dict[str, Any], caption_ids: bool,
                 table_number: int = 1) -> str:
    caption_tex = latex_inline(spec.caption)
    if caption_ids:
        caption_tex += r"（表 id \texttt{" + latex_escape(spec.tid) + r"}）"
    label = r"\label{tab:" + spec.tid + "}"
    note_tex = ""
    if spec.note:
        note_tex = r"\begin{tablenote}" + latex_inline(spec.note) + r"\end{tablenote}"

    # Prose (caption-less) tables still bump the `table` counter now that pandoc's
    # LTcaptype=none wrapper is gone; sync it to THIS evidence table's ordinal so
    # the Chinese numbering is exactly 1..N and never skips.
    sync = "\\setcounter{table}{" + str(max(0, table_number - 1)) + "}"

    out: List[str] = []
    if layout["layout"].startswith("longtable"):
        if layout["landscape"]:
            out.append(r"\begin{landscape}")
        out.append(r"\begin{bpLT" + layout["font"] + "}")
        out.append(sync)
        for idx, panel in enumerate(spec.panels):
            out.append(r"\begin{longtable}{" + column_spec(panel, layout, idx) + "}")
            if idx == 0:
                out.append(r"%% table-id: " + spec.tid + " sha256:" + spec.sha)
                out.append(r"\caption{" + caption_tex + "}" + label + r"\\")
            out.append(r"\toprule")
            out.append(" & ".join(latex_cell(c) for c in panel.header) + r" \\")
            out.append(r"\midrule")
            out.append(r"\endfirsthead")
            out.append(r"\toprule")
            out.append(" & ".join(latex_cell(c) for c in panel.header) + r" \\")
            out.append(r"\midrule")
            out.append(r"\endhead")
            out.append(r"\bottomrule")
            out.append(r"\endfoot")
            for row in panel.rows:
                out.append(" & ".join(latex_cell(c) for c in row) + r" \\")
            out.append(r"\end{longtable}")
            if idx + 1 < len(spec.panels):
                out.append(r"\par\smallskip")
        if note_tex:
            out.append(note_tex)
        out.append(r"\end{bpLT" + layout["font"] + "}")
        if layout["landscape"]:
            out.append(r"\end{landscape}")
        return "\n".join(out)

    if layout["layout"] == "sidewaystable":
        out.append(r"\begin{sidewaystable}")
        out.append(sync)
        out.append(r"%% table-id: " + spec.tid + " sha256:" + spec.sha)
        out.append(r"\centering")
        out.append(r"\caption{" + caption_tex + "}" + label)
        out.append("\\" + layout["font"])
        for idx, panel in enumerate(spec.panels):
            out.extend(render_panel(panel, layout, idx))
            if idx + 1 < len(spec.panels):
                out.append(r"\par\smallskip")
        if note_tex:
            out.append(note_tex)
        out.append(r"\end{sidewaystable}")
        return "\n".join(out)

    out.append(r"\begin{bptable}")
    out.append(sync)
    out.append(r"%% table-id: " + spec.tid + " sha256:" + spec.sha)
    out.append(r"\captionof{table}{" + caption_tex + "}" + label)
    out.append(r"\par\smallskip")
    out.append("\\" + layout["font"])
    for idx, panel in enumerate(spec.panels):
        if layout["layout"] == "minipage-resizebox":
            out.append(r"\resizebox{\linewidth}{!}{%")
        out.extend(render_panel(panel, layout, idx))
        if layout["layout"] == "minipage-resizebox":
            out.append(r"}%")
        if idx + 1 < len(spec.panels):
            out.append(r"\par\smallskip")
    if note_tex:
        out.append(note_tex)
    out.append(r"\end{bptable}")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# claims + figures
# --------------------------------------------------------------------------- #
def format_refs(claim: Dict[str, Any]) -> str:
    parts: List[str] = []
    for ref in claim.get("refs", []) or []:
        kind = ref.get("kind")
        if kind == "metric":
            parts.append(latex_escape(f"{ref.get('experimentId')}/{ref.get('metricKey')}"))
        elif kind == "figure":
            parts.append(latex_escape(str(ref.get("figureId"))))
        elif kind == "literature":
            parts.append(latex_escape(str(ref.get("citation"))))
    val_ids = claim.get("validationIds") or []
    if val_ids:
        parts.append(latex_escape("验证 " + "/".join(str(v) for v in val_ids)))
    return "；".join(parts)


def render_claim(claim_id: str, label: str, data: ProjectData,
                 findings: Findings, source_label: str,
                 line: Optional[int]) -> Optional[str]:
    claim = data.claims.get(claim_id)
    if claim is None:
        findings.reject("CLAIM_UNKNOWN", source_label, line,
                        f"{claim_id} is not in state/ledger.json claims")
        return None
    status = str(claim.get("status") or "").lower()
    if status != "active":
        findings.reject("CLAIM_NOT_ACTIVE", source_label, line,
                        f"{claim_id} status={status!r} (only active claims may be rendered)")
        return None
    if claim_id in RETIRED_CLAIMS:
        findings.reject("RETIRED_CLAIM", source_label, line,
                        f"{claim_id} is on the retired-claim list")
        return None

    quality = claim.get("quality") or {}
    limitations = quality.get("limitations") or claim.get("limitations") or []
    scope = quality.get("evidenceScope") or claim.get("scope") or ""
    critical = bool(claim.get("critical"))
    status_line = r"\textsf{" + latex_escape(claim_id) + "} · " + latex_escape(status)
    if critical:
        status_line += r" · critical"

    out: List[str] = []
    out.append(r"\begin{evidenceregistry}")
    head = ""
    if label:
        head = r"\textbf{" + latex_escape(label) + "} "
    out.append(head + status_line + r"\par")
    if scope:
        out.append(r"\noindent\textbf{范围：} " + latex_inline(str(scope)) + r"\par")
    out.append(latex_inline(str(claim.get("statement", ""))) + r"\par")
    refs = format_refs(claim)
    if refs:
        out.append(r"\noindent\textbf{证据：} " + refs + r"\par")
    if limitations:
        out.append(r"\noindent\textbf{限制：}")
        out.append(r"\begin{itemize}\setlength{\itemsep}{1pt}\setlength{\parsep}{0pt}")
        for lim in limitations:
            out.append(r"\item " + latex_inline(str(lim)))
        out.append(r"\end{itemize}")
    out.append(r"\end{evidenceregistry}")
    return "\n".join(out)


def figure_relpath(fig_path: str, tex_dir: Path) -> str:
    return os.path.relpath((ROOT / fig_path).resolve(), tex_dir.resolve()).replace(os.sep, "/")


def render_figure(fig_id: str, data: ProjectData, findings: Findings,
                  source_label: str, line: Optional[int], tex_dir: Path,
                  strict: bool) -> Optional[str]:
    rec = data.figures.get(fig_id)
    if rec is None:
        findings.reject("FAKE_FIGURE", source_label, line,
                        f"{fig_id} is not registered in state/ledger.json figures")
        return None
    if not figure_is_active(rec):
        findings.reject("FAKE_FIGURE", source_label, line,
                        f"{fig_id} is retired/superseded (status={rec.get('status')!r})")
        return None
    path = rec.get("path") or ""
    abs_path = ROOT / path
    if not path or not abs_path.exists():
        findings.reject("FIGURE_FILE_MISSING", source_label, line,
                        f"{fig_id}: file {path!r} does not exist")
        return None
    actual = sha256_file(abs_path)
    registered = rec.get("sha256")
    if registered and actual != registered:
        findings.reject("FIGURE_SHA_MISMATCH", source_label, line,
                        f"{fig_id}: file sha256={actual} but ledger says {registered}")
        return None
    caption = latex_inline(str(rec.get("caption") or ""))
    rel = figure_relpath(path, tex_dir)
    out = [
        r"\begin{bpfigure}",
        r"%% figure-id: " + fig_id + " sha256:" + actual,
        r"\includegraphics[width=0.92\linewidth,height=0.34\textheight,keepaspectratio]{"
        + rel + "}",
        r"\captionof{figure}{" + caption + ((r"（\texttt{" + fig_id + r"}）") if CAPTION_IDS else "")
        + r"\label{fig:" + fig_id + "}",
        r"\end{bpfigure}",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# source transform
# --------------------------------------------------------------------------- #
@dataclass
class TransformResult:
    pandoc_md: str
    rejects: List[Finding]
    warns: List[Finding]
    passes: List[Tuple[str, str]]
    tables: List[Dict[str, Any]]
    claim_ids: List[str]
    figure_ids: List[str]
    pending: List[Finding]
    metric_placeholders: List[Tuple[int, str]]
    unknown_placeholders: List[Tuple[int, str]]
    headings: List[Tuple[int, str]]
    page_structure: Dict[str, Any]
    caption_count: int

    def reject_count(self) -> int:
        return len(self.rejects) + len(self.pending) + len(self.unknown_placeholders)


def scan_forbidden(source_text: str, source_label: str, findings: Findings,
                   data: ProjectData) -> None:
    """Named rejections that apply to the whole source (not just inside blocks)."""
    for m in re.finditer(r"@@", source_text):
        findings.reject("AT_AT_TOKEN", source_label, line_no_of(source_text, m.start()),
                        "literal '@@' placeholder residue")
    for m in CLAIM_ID_RE.finditer(source_text):
        cid = m.group(0)
        if cid in RETIRED_CLAIMS:
            findings.reject("RETIRED_CLAIM", source_label,
                            line_no_of(source_text, m.start()),
                            f"retired claim {cid} appears in the source")
    for m in PILOT_EXP_RE.finditer(source_text):
        findings.reject("FORBIDDEN_EXPERIMENT", source_label,
                        line_no_of(source_text, m.start()),
                        f"pilot-round experiment {m.group(0)} may not be cited")
    for m in FIG_ID_RE.finditer(source_text):
        cid = m.group(0)
        rec = data.figures.get(cid)
        if rec is None or not figure_is_active(rec):
            findings.reject("FAKE_FIGURE", source_label,
                            line_no_of(source_text, m.start()),
                            f"FIG id {cid} is not an active ledger figure")


def transform(source_text: str, source_path: Path, data: ProjectData, *,
              strict: bool, number_sections: bool, caption_ids: bool,
              tex_dir: Path, wide: str = "rotate",
              require_all_tables: bool = True) -> TransformResult:
    source_label = rel_to_root(source_path)
    findings = Findings()
    pending: List[Finding] = []
    metric_placeholders: List[Tuple[int, str]] = []
    unknown_placeholders: List[Tuple[int, str]] = []

    scan_forbidden(source_text, source_label, findings, data)

    lines = source_text.split("\n")
    n_lines = len(lines)

    # 1. locate table blocks and their caption lines
    block_spans: List[Tuple[int, int, TableSpec]] = []
    consumed: set = set()
    for match in TABLE_RE.finditer(source_text):
        spec = parse_table_block(match, source_text, data, findings, source_label)
        start_line = line_no_of(source_text, match.start()) - 1
        end_line = line_no_of(source_text, match.end()) - 1
        # caption: first non-empty line above the block
        cap_idx = start_line - 1
        while cap_idx >= 0 and not lines[cap_idx].strip():
            cap_idx -= 1
        if spec is not None:
            if cap_idx >= 0:
                cm = CAPTION_RE.match(lines[cap_idx].strip())
                if cm and cm.group("id") == spec.tid:
                    spec.caption = cm.group("cap").strip()
                    # Index convention: this scan indexes `lines` 0-based, while
                    # transform_inline_lines() tests `idx = base_line + i` which is
                    # 1-based (base_line = cursor + 1).  Storing the 0-based index
                    # dropped the blank line above the capture line instead of the
                    # capture line itself, so every inline table's caption was also
                    # emitted as prose (duplicated title, sometimes orphaned across a
                    # page break).  Store the 1-based line number.
                    consumed.add(cap_idx + 1)
                else:
                    findings.reject("CAPTION_MISSING", source_label, start_line + 1,
                                    f"block {spec.tid}: no '**表 {spec.tid}　<caption>**' "
                                    f"line immediately above the block")
            else:
                findings.reject("CAPTION_MISSING", source_label, start_line + 1,
                                f"block {spec.tid}: block is the first line of the source")
        block_spans.append((start_line, end_line, spec))  # spec None -> diagnostic only
    block_spans.sort(key=lambda item: item[0])
    inline_ids = {spec.tid for (_, _, spec) in block_spans if spec is not None}
    expected_inline, support_only = expected_table_sets(data)

    # INDEX.json contract: paperIncluded tables must be inlined; supportOnly tables
    # live in the support material and are checked by fragment bytes, never by
    # presence in the paper.  Enforced for a real build (strict) so that a missing
    # full table cannot silently disappear from the paper.
    if strict:
        if require_all_tables:
            for tid in sorted(expected_inline - inline_ids):
                findings.reject("TABLE_MISSING_IN_PAPER", source_label, None,
                                f"table {tid} is marked paperIncluded=true in INDEX.json "
                                f"but no table block exists in the source")
        for tid in sorted(inline_ids - expected_inline):
            findings.warn("TABLE_NOT_INCLUDED", source_label, None,
                          f"table {tid} is inlined but INDEX.json does not mark it "
                          f"paperIncluded=true")
        for problem in support_only_checks(data):
            findings.reject(problem["code"], rel_to_root(ROOT / problem["path"]),
                            None, problem["detail"])

    # 2. rebuild the source line by line
    out: List[str] = []
    headings: List[Tuple[int, str]] = []
    claim_ids: List[str] = []
    figure_ids: List[str] = []
    table_no = 0
    cursor = 0
    for start_line, end_line, spec in block_spans:
        out.extend(transform_inline_lines(lines[cursor:start_line], source_label,
                                          data, findings, pending, metric_placeholders,
                                          unknown_placeholders, claim_ids, figure_ids,
                                          tex_dir, strict, consumed,
                                          set(range(start_line + 1, end_line + 2)),
                                          headings, base_line=cursor + 1,
                                          source_dir=source_path.parent))
        if spec is not None and spec.caption:
            layout = layout_table(spec, wide)
            table_no += 1
            latex = render_table(spec, layout, caption_ids, table_number=table_no)
            out.append("")
            out.extend(latex.split("\n"))
            out.append("")
            rec = layout
            rec["block_line"] = spec.line
            rec["block_sha256"] = spec.sha
            findings.ok("table:" + spec.tid,
                        f"{layout['layout']}, {layout['rows']}x{layout['cols']}, "
                        f"sha256 {spec.sha[:12]}…")
        # skip original block lines
        cursor = end_line + 1

    out.extend(transform_inline_lines(lines[cursor:], source_label, data, findings,
                                      pending, metric_placeholders, unknown_placeholders,
                                      claim_ids, figure_ids, tex_dir, strict, consumed,
                                      set(), headings, base_line=cursor + 1,
                                      source_dir=source_path.parent))

    # 3. page structure: page 1 title/abstract, page 2 TOC, body arabic from 1
    out, page_info = apply_page_structure(out)

    # 4. DRAFT banner (page 1) -- keep text, restyle
    out = apply_draft_banner(out)

    pandoc_md = "\n".join(out)
    if not pandoc_md.endswith("\n"):
        pandoc_md += "\n"

    # 5. structural counts / duplicate checks
    if len(block_spans) != len(expected_inline):
        findings.warn("TABLE_COUNT", source_label, None,
                      f"{len(block_spans)} inline table block(s), "
                      f"{len(expected_inline)} table(s) marked paperIncluded=true")
    else:
        findings.ok("table-count",
                    f"{len(block_spans)} inline table blocks "
                    f"(+{len(support_only)} supportOnly)")
    if len(set(claim_ids)) != len(claim_ids):
        findings.warn("CLAIM_DUPLICATE", source_label, None,
                      "duplicate {{claim:...}} ids: " + ", ".join(claim_ids))
    if page_info["toc_found"]:
        findings.ok("page-structure",
                    "TOC marker found; front matter switched to gobble, body to arabic 1")

    return TransformResult(
        pandoc_md=pandoc_md,
        rejects=findings.rejects,
        warns=findings.warns,
        passes=findings.passes,
        tables=[s for (_, _, s) in block_spans if s is not None],
        claim_ids=claim_ids,
        figure_ids=figure_ids,
        pending=pending,
        metric_placeholders=metric_placeholders,
        unknown_placeholders=unknown_placeholders,
        headings=headings,
        page_structure=page_info,
        caption_count=len(block_spans),
    )


IMG_RE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)\s*$")
FIG_COMMENT_RE = re.compile(
    r"^<!--\s*(?P<fid>FIG-\d{4})\s+sha256:(?P<sha>[0-9a-f]{64})\s*-->\s*$",
    re.M)


def render_markdown_figure(alt: str, src: str, fig_id: Optional[str], comment_sha: Optional[str],
                           data: ProjectData, findings: Findings, source_label: str,
                           line: Optional[int], tex_dir: Path, source_dir: Path) -> Optional[str]:
    """Render the upstream renderer's `![caption](../figures/x.png)` + FIG comment.

    The renderer writes image paths relative to report/, while xelatex runs inside
    the build/preview directory, so the path is re-resolved against the source
    directory and re-emitted relative to the .tex.  FIG provenance is validated
    against the ledger; an untracked image is rendered but reported.
    """
    abs_path = Path(src) if os.path.isabs(src) else (source_dir / src)
    abs_path = abs_path.resolve()
    if not abs_path.exists():
        findings.reject("FIGURE_FILE_MISSING", source_label, line,
                        f"image {src!r} not found (resolved {abs_path})")
        return None
    actual = sha256_file(abs_path)
    if fig_id:
        rec = data.figures.get(fig_id)
        if rec is None or not figure_is_active(rec):
            findings.reject("FAKE_FIGURE", source_label, line,
                            f"{fig_id} is not an active ledger figure")
            return None
        registered = rec.get("sha256")
        if comment_sha and actual != comment_sha:
            findings.reject("FIGURE_SHA_MISMATCH", source_label, line,
                            f"{fig_id}: image bytes sha256={actual} but the render comment "
                            f"records {comment_sha}")
            return None
        if registered and actual != registered:
            findings.reject("FIGURE_SHA_MISMATCH", source_label, line,
                            f"{fig_id}: image bytes sha256={actual} but ledger records {registered}")
            return None
        if rec.get("path") and (ROOT / rec["path"]).resolve() != abs_path:
            findings.warn("FIGURE_PATH_DIFF", source_label, line,
                          f"{fig_id}: rendered path {src!r} differs from ledger path "
                          f"{rec['path']!r} but bytes match")
        caption = alt.strip() or str(rec.get("caption") or "")
    else:
        findings.warn("FIGURE_UNTRACKED", source_label, line,
                      f"markdown image {src!r} carries no '<!-- FIG-xxxx sha256:... -->' comment")
        caption = alt.strip()
    rel = os.path.relpath(abs_path, tex_dir.resolve()).replace(os.sep, "/")
    out = [r"\begin{bpfigure}"]
    if fig_id:
        out.append(r"%% figure-id: " + fig_id + " sha256:" + actual)
    out.append(r"%% figure-src: " + rel)
    out.append(r"\includegraphics[width=0.92\linewidth,height=0.34\textheight,keepaspectratio]{"
               + rel + "}")
    cap_tex = latex_inline(caption)
    if fig_id and CAPTION_IDS:
        cap_tex += r"（\texttt{" + fig_id + r"}）"
    elif fig_id:
        # 交付口径：正文题注不暴露内部编号。台账 caption 里写着 EXP-/ROB-/FIG-/CLAIM- 等编号；
        # 在 --no-caption-ids 模式下把它们替换成**语义等价的中文角色词**，而不是整段删除——
        # 直接删括注会丢掉“复现 732 边/51 分量”等读数，删单个 id 会留下“/16/17 为…”这类残句。
        cap_tex = re.sub(r"ROB-\d{3,4}(?:\s*/\s*\d{2,4})*", "预登记的种子块计划", cap_tex)
        cap_tex = re.sub(r"EXP-\d{4}", "对应主实验", cap_tex)
        cap_tex = re.sub(r"[（(]?\s*(?:CLAIM|FIG|VAL|MODEL)-\d{3,4}\s*[）)]?", "", cap_tex)
        cap_tex = re.sub(r"[（(]\s*[）)]", "", cap_tex)
        # 同一题注里出现两次“预登记的种子块计划”时，第二处改成“该计划”，避免重复与悬空
        cap_tex = cap_tex.replace("，预登记的种子块计划 饱和", "，该计划的饱和")
        cap_tex = cap_tex.replace("计划 为", "计划为")
        cap_tex = cap_tex.replace("由 对应主实验 注册", "由对应主实验注册")
        cap_tex = re.sub(r"[ \t]{2,}", " ", cap_tex).strip()
    out.append(r"\captionof{figure}{" + cap_tex + r"}")
    out.append(r"\end{bpfigure}")
    return "\n".join(out)


def transform_inline_lines(lines: List[str], source_label: str, data: ProjectData,
                           findings: Findings, pending: List[Finding],
                           metric_placeholders: List[Tuple[int, str]],
                           unknown_placeholders: List[Tuple[int, str]],
                           claim_ids: List[str], figure_ids: List[str],
                           tex_dir: Path, strict: bool,
                           consumed: set, skip_lines: set,
                           headings: List[Tuple[int, str]],
                           base_line: int, source_dir: Optional[Path] = None) -> List[str]:
    out: List[str] = []
    source_dir = source_dir or ROOT / "report"
    i = 0
    while i < len(lines):
        line = lines[i]
        idx = base_line + i  # 1-based line number (base_line = cursor+1)
        i += 1
        if idx in skip_lines or idx in consumed:
            continue

        h1 = H1_RE.match(line)
        if h1:
            headings.append((idx, h1.group("text")))

        # --- rendered markdown image (+ optional FIG provenance comment) ------
        img = IMG_RE.match(line.strip())
        if img:
            fig_id = None
            comment_sha = None
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            consumed_comment = False
            if j < len(lines):
                cm = FIG_COMMENT_RE.match(lines[j].strip())
                if cm:
                    fig_id = cm.group("fid")
                    comment_sha = cm.group("sha")
                    consumed_comment = True
            latex = render_markdown_figure(img.group("alt"), img.group("src"), fig_id,
                                           comment_sha, data, findings, source_label, idx,
                                           tex_dir, source_dir)
            if latex:
                figure_ids.append(fig_id or f"src:{img.group('src')}")
                out.append("")
                out.extend(latex.split("\n"))
                out.append("")
            if consumed_comment:
                i = j + 1
            continue

        # --- pending figures are never allowed into a build ------------------
        for pm in PENDING_RE.finditer(line):
            pending.append(Finding("PENDING_FIGURE", source_label, idx,
                                   f"placeholder {pm.group('name').strip()!r} "
                                   f"(replace with {{{{figure:FIG-xxxx}}}} after registering)"))
        # --- {{figure:...}} --------------------------------------------------
        fig_ids = [m.group("id") for m in FIGURE_RE.finditer(line)]
        if fig_ids:
            for fid in fig_ids:
                latex = render_figure(fid, data, findings, source_label, idx, tex_dir, strict)
                if latex:
                    figure_ids.append(fid)
                    out.append("")
                    out.extend(latex.split("\n"))
                    out.append("")
            remainder = FIGURE_RE.sub("", line).strip()
            if remainder:
                out.append(transform_inline_line(remainder, source_label, idx))
            continue
        # --- {{claim:...}} ---------------------------------------------------
        first_claim = CLAIM_RE.search(line)
        if first_claim:
            prefix = line[:first_claim.start()].strip()
            suffix = line[first_claim.end():].strip()
            label = ""
            if prefix and re.fullmatch(r"\*\*[^*]+\*\*", prefix):
                label = prefix[2:-2].strip()
            elif prefix:
                out.append(transform_inline_line(prefix, source_label, idx))
            for cm in CLAIM_RE.finditer(line):
                cid = cm.group("id")
                latex = render_claim(cid, label, data, findings, source_label, idx)
                if latex:
                    claim_ids.append(cid)
                    label = ""  # only the first block carries the source label
                    out.append("")
                    out.extend(latex.split("\n"))
                    out.append("")
            if suffix:
                out.append(transform_inline_line(suffix, source_label, idx))
            continue
        # --- {{metric:...}} (resolved upstream by modeling_deliver render) ---
        for mm in METRIC_RE.finditer(line):
            metric_placeholders.append((idx, mm.group(0)))
            if strict:
                findings.reject("UNRESOLVED_PLACEHOLDER", source_label, idx,
                                f"{mm.group(0)} -- metric placeholders must be resolved by "
                                f"modeling_deliver render before a real build")
        for am in ANY_PLACEHOLDER_RE.finditer(line):
            token = am.group(0)
            if token.startswith("{{metric:") or token.startswith("{{claim:") or token.startswith("{{figure:"):
                continue
            unknown_placeholders.append((idx, token))
            findings.reject("UNRESOLVED_PLACEHOLDER", source_label, idx,
                            f"unknown placeholder {token!r}")
        out.append(line)
    return out


def transform_inline_line(line: str, source_label: str, idx: int) -> str:
    """Keep prose as markdown; just strip the already-handled inline tokens."""
    return line


def apply_page_structure(lines: List[str]) -> Tuple[List[str], Dict[str, Any]]:
    info = {"toc_found": False, "injected": False, "front_matter_pages": 2,
            "toc_line": None}
    toc_idx = None
    for i, line in enumerate(lines):
        if line.strip() == r"\tableofcontents":
            toc_idx = i
            break
    if toc_idx is not None:
        info["toc_found"] = True
        info["toc_line"] = toc_idx + 1
        pre = lines[:toc_idx]
        post = lines[toc_idx + 1:]
        non_empty = [ln for ln in pre if ln.strip()]
        if not non_empty:
            pre = [r"\newpage"]
        elif non_empty[-1].strip() != r"\newpage":
            pre = pre + ["", r"\newpage"]
        pre = pre + [r"\thispagestyle{empty}", r"\tableofcontents"]
        # first non-empty after the TOC
        j = 0
        while j < len(post) and not post[j].strip():
            j += 1
        if j < len(post) and post[j].strip() == r"\newpage":
            rest = post[:j] + [r"\newpage", r"\pagenumbering{arabic}"] + post[j + 1:]
        else:
            rest = ["", r"\newpage", r"\pagenumbering{arabic}", ""] + post
        return pre + rest, info

    # no marker: inject just before the first body H1 (after the 摘要 section)
    anchor = None
    for i, line in enumerate(lines):
        m = H1_RE.match(line)
        if m and "摘要" not in m.group("text"):
            anchor = i
            break
    block = ["", r"\newpage", r"\thispagestyle{empty}", r"\tableofcontents",
             "", r"\newpage", r"\pagenumbering{arabic}", ""]
    if anchor is None:
        info["injected"] = True
        return lines + block, info
    info["injected"] = True
    return lines[:anchor] + block + lines[anchor:], info


def apply_draft_banner(lines: List[str]) -> List[str]:
    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith(">"):
            j = i
            quote: List[str] = []
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                stripped = re.sub(r"^\s*>\s?", "", lines[j])
                quote.append(stripped)
                j += 1
            joined = " ".join(q for q in quote if q.strip())
            if "DRAFT" in joined:
                paragraphs: List[str] = []
                current: List[str] = []
                for q in quote:
                    if q.strip():
                        current.append(q.strip())
                    elif current:
                        paragraphs.append(" ".join(current))
                        current = []
                if current:
                    paragraphs.append(" ".join(current))
                body = r"\par ".join(latex_inline(p) for p in paragraphs)
                out.append("")
                out.append(r"\begin{draftbanner}")
                out.append(body)
                out.append(r"\end{draftbanner}")
                out.append("")
                i = j
                continue
            out.extend(lines[i:j])
            i = j
            continue
        out.append(line)
        i += 1
    return out


# --------------------------------------------------------------------------- #
# environment probes (used by --check)
# --------------------------------------------------------------------------- #
def probe_tools() -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        info["pandoc"] = subprocess.run([PANDOC, "--version"], capture_output=True,
                                        text=True).stdout.splitlines()[0]
    except Exception as exc:  # noqa: BLE001
        info["pandoc"] = f"ERROR {exc}"
    try:
        info["xelatex"] = subprocess.run([XELATEX, "--version"], capture_output=True,
                                         text=True).stdout.splitlines()[0].strip()
    except Exception as exc:  # noqa: BLE001
        info["xelatex"] = f"ERROR {exc}"
    return info


def probe_packages() -> Dict[str, bool]:
    result: Dict[str, bool] = {}
    for pkg in REQUIRED_PACKAGES:
        try:
            found = subprocess.run(["kpsewhich", pkg + ".sty"], capture_output=True,
                                   text=True).stdout.strip()
        except FileNotFoundError:
            found = ""
        result[pkg] = bool(found)
    return result


def probe_fonts() -> Dict[str, bool]:
    try:
        listing = subprocess.run(["fc-list"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        listing = ""
    return {name: (name in listing) for name in REQUIRED_FONTS}


# --------------------------------------------------------------------------- #
# --check
# --------------------------------------------------------------------------- #
def run_check(source_path: Path, number_sections: bool, caption_ids: bool,
              wide: str = "rotate") -> int:
    print("== build_paper.py --check ==")
    if not source_path.exists():
        print(f"[FAIL] SOURCE_MISSING  {source_path} does not exist")
        print("hint: use --source report/paper.md for the static draft source")
        return 2
    raw = source_path.read_bytes()
    source_text = raw.decode("utf-8")
    display = rel_to_root(source_path)
    print(f"source      : {display}")
    print(f"source-sha  : {sha256_bytes(raw)}")
    print(f"bytes       : {len(raw)}")
    mode = "with --number-sections (LaTeX numbering)" if number_sections else "default (no --number-sections)"
    print(f"numbering   : {mode}")
    print("writes      : none (read-only audit)")
    print()

    data = load_project()
    passed = 0
    failed = 0
    warned = 0

    def emit_pass(code: str, detail: str) -> None:
        nonlocal passed
        passed += 1
        print(f"[PASS] {code:<28} {detail}")

    def emit_fail(code: str, detail: str, line: Optional[int] = None) -> None:
        nonlocal failed
        failed += 1
        loc = display if line is None else f"{display}:{line}"
        print(f"[FAIL] {code:<28} {loc}  {detail}")

    def emit_warn(code: str, detail: str, line: Optional[int] = None) -> None:
        nonlocal warned
        warned += 1
        loc = display if line is None else f"{display}:{line}"
        print(f"[WARN] {code:<28} {loc}  {detail}")

    def emit_info(code: str, detail: str) -> None:
        print(f"[INFO] {code:<28} {display}  {detail}")

    # freshness hint: the default source is an older render than paper.md
    if source_path.name == "rendered.md" and PAPER_MD.exists():
        if PAPER_MD.stat().st_mtime > source_path.stat().st_mtime:
            emit_warn("STALE_RENDER_SOURCE",
                      f"report/paper.md is newer than {display}; "
                      f"this rendered.md predates the current paper source")

    # ---- table blocks (paperIncluded vs supportOnly) ------------------------
    matches = list(TABLE_RE.finditer(source_text))
    expected_inline, support_only = expected_table_sets(data)
    inline_ids: List[str] = []
    for match in matches:
        tid = match.group("id")
        line = line_no_of(source_text, match.start())
        if tid in inline_ids:
            emit_fail("TABLE_DUPLICATE", f"block {tid} appears more than once", line)
            continue
        inline_ids.append(tid)
        rec = data.tables_by_id.get(tid)
        if rec is None:
            emit_fail("TABLE_ID_UNKNOWN",
                      f"table id {tid!r} is not registered in report/tables/INDEX.json", line)
            continue
        inc, sup = table_flags(rec)
        if sup and not inc:
            emit_warn("TABLE_SUPPORT_ONLY_INLINE",
                      f"{tid} is marked supportOnly=true but is inlined in the paper", line)
        probe = Findings()
        spec = parse_table_block(match, source_text, data, probe, display)
        if spec is None:
            for f in probe.rejects:
                emit_fail(f.code, f.detail, f.line)
            continue
        idx = line - 2
        while idx >= 0 and not source_text.split("\n")[idx].strip():
            idx -= 1
        cm = CAPTION_RE.match(source_text.split("\n")[idx].strip()) if idx >= 0 else None
        if cm and cm.group("id") == tid:
            emit_pass("table:" + tid,
                      f"sha256 ok, caption {cm.group('cap')[:34]!r}, "
                      f"{spec.nrows}x{spec.ncols}"
                      + (f", {len(spec.panels)} panels" if len(spec.panels) > 1 else ""))
        else:
            emit_fail("CAPTION_MISSING", f"block {tid}: no matching caption line above", line)

    inline_set = set(inline_ids)
    for tid in sorted(expected_inline - inline_set):
        emit_fail("TABLE_MISSING_IN_PAPER",
                  f"table {tid} is marked paperIncluded=true in INDEX.json "
                  f"but has no block in {display}")
    for tid in sorted(inline_set - expected_inline):
        emit_warn("TABLE_NOT_INCLUDED",
                  f"table {tid} is inlined but is not marked paperIncluded=true")
    inline_ok = len(inline_set & expected_inline)
    if expected_inline and not (expected_inline - inline_set) \
            and not (inline_set - expected_inline):
        emit_pass("inline-tables",
                  f"{inline_ok}/{len(expected_inline)} paperIncluded tables inlined, "
                  f"four-way sha agreement")

    support_problems = support_only_checks(data)
    for problem in support_problems:
        emit_fail(problem["code"], problem["detail"])
    bad_support = {ply["tableId"] for ply in support_problems}
    support_ok = len(support_only) - len(bad_support)
    if support_only:
        emit_pass("support-only-tables",
                  f"{support_ok}/{len(support_only)} supportOnly tables: fragment bytes match "
                  f"INDEX (presence in the paper NOT required)")

    # ---- claim placeholders -------------------------------------------------
    claims_expanded = False
    claim_hits = [(line_no_of(source_text, m.start()), m.group("id"))
                  for m in CLAIM_RE.finditer(source_text)]
    active_claims = {cid for cid, rec in data.claims.items()
                     if str(rec.get("status")).lower() == "active"}
    retired_in_source = [(line_no_of(source_text, m.start()), m.group(0))
                         for m in CLAIM_ID_RE.finditer(source_text)
                         if m.group(0) in RETIRED_CLAIMS]
    for line, cid in retired_in_source:
        emit_fail("RETIRED_CLAIM", f"{cid} is retired and may not appear", line)
    if claim_hits:
        bad = []
        for line, cid in claim_hits:
            rec = data.claims.get(cid)
            if rec is None:
                bad.append((line, f"{cid} unknown"))
            elif str(rec.get("status")).lower() != "active":
                bad.append((line, f"{cid} status={rec.get('status')}"))
            elif cid in RETIRED_CLAIMS:
                bad.append((line, f"{cid} retired"))
        if bad:
            for line, detail in bad:
                emit_fail("CLAIM_NOT_ACTIVE", detail, line)
        else:
            emit_pass("claim-placeholders",
                      f"{len(claim_hits)} placeholders, all active: "
                      + ", ".join(sorted({c for _, c in claim_hits})))
        got = {c for _, c in claim_hits}
        if got != active_claims:
            missing = sorted(active_claims - got)
            extra = sorted(got - active_claims)
            emit_warn("CLAIM_COVERAGE",
                      f"placeholder set != active claims (missing={missing}, extra={extra})")
    else:
        expanded = count_expanded_claims(source_text, data)
        claims_expanded = expanded > 0
        if claims_expanded:
            emit_info("claims expanded upstream",
                      f"[INFO] claims already expanded upstream "
                      f"({expanded}/{len(active_claims)} active claim statements found as plain "
                      f"text; no evidence-registry styling applied, as the upstream renderer "
                      f"expands {{claim:...}} to its statement)")
            passed += 1
        elif source_path.name == "paper.md":
            emit_fail("CLAIM_COVERAGE",
                      f"0 {{claim:...}} placeholders, expected {EXPECTED_CLAIMS}")
        else:
            emit_warn("CLAIM_COVERAGE",
                      "no {{claim:...}} placeholders and no expanded claim text detected "
                      "(reported, not failed)")

    # ---- figure positions ---------------------------------------------------
    pending_hits = [(line_no_of(source_text, m.start()), m.group("name").strip())
                    for m in PENDING_RE.finditer(source_text)]
    figure_hits = [(line_no_of(source_text, m.start()), m.group("id"))
                   for m in FIGURE_RE.finditer(source_text)]
    fig_comment_hits = [(line_no_of(source_text, m.start()), m.group("fid"))
                        for m in FIG_COMMENT_RE.finditer(source_text)]
    all_fig_hits = figure_hits + fig_comment_hits
    for line, name in pending_hits:
        emit_fail("PENDING_FIGURE",
                  f"unregistered figure slot {name!r} -- replace with {{{{figure:FIG-xxxx}}}} "
                  f"after modeling_deliver figure", line)
    if pending_hits and all_fig_hits:
        emit_warn("FIGURE_MIXED",
                  f"{len(pending_hits)} pending + {len(all_fig_hits)} real figure slots")
    if not all_fig_hits and not pending_hits:
        if source_path.name == "paper.md":
            emit_fail("FIGURE_COVERAGE",
                      f"0 figure slots found, expected {EXPECTED_FIGURES}")
        else:
            emit_warn("FIGURE_COVERAGE",
                      f"0 figure slots found; expected {EXPECTED_FIGURES} when rendering the paper")
    if all_fig_hits:
        bad_fig = []
        for line, fid in all_fig_hits:
            rec = data.figures.get(fid)
            if rec is None:
                bad_fig.append((line, f"{fid} not in ledger figures"))
            elif not figure_is_active(rec):
                bad_fig.append((line, f"{fid} status={rec.get('status')!r}"))
            else:
                abs_path = ROOT / str(rec.get("path") or "")
                if not abs_path.exists():
                    bad_fig.append((line, f"{fid} file missing: {rec.get('path')}"))
                elif rec.get("sha256") and sha256_file(abs_path) != rec["sha256"]:
                    bad_fig.append((line, f"{fid} file sha256 != ledger sha256"))
        if bad_fig:
            for line, detail in bad_fig:
                emit_fail("FAKE_FIGURE", detail, line)
        else:
            emit_pass("figure-slots",
                      f"{len(all_fig_hits)} figure slot(s) "
                      f"({len(figure_hits)} {{{{figure:...}}}} + {len(fig_comment_hits)} "
                      f"rendered image comments): active and hash-match")
    # every FIG id mentioned anywhere must be a live ledger figure
    stray = []
    for m in FIG_ID_RE.finditer(source_text):
        fid = m.group(0)
        if any(fid == f for _, f in all_fig_hits):
            continue
        rec = data.figures.get(fid)
        if rec is None or not figure_is_active(rec):
            stray.append((line_no_of(source_text, m.start()), fid))
    for line, fid in stray:
        emit_fail("FAKE_FIGURE", f"FIG id {fid} occurs but is not an active ledger figure", line)

    # ---- unresolved placeholders -------------------------------------------
    metric_hits = list(METRIC_RE.finditer(source_text))
    unknown_hits = [m for m in ANY_PLACEHOLDER_RE.finditer(source_text)
                    if not (m.group(0).startswith("{{metric:")
                            or m.group(0).startswith("{{claim:")
                            or m.group(0).startswith("{{figure:"))]
    if metric_hits:
        exps = sorted({m.group("exp") for m in metric_hits})
        emit_fail("UNRESOLVED_PLACEHOLDER",
                  f"{len(metric_hits)} {{{{metric:...}}}} placeholder(s) across {len(exps)} experiments "
                  f"-- resolve with modeling_deliver render before a real build "
                  f"(first at line {line_no_of(source_text, metric_hits[0].start())})")
    else:
        emit_pass("metric-placeholders", "no unresolved {{metric:...}} placeholders")
    for m in unknown_hits:
        emit_fail("UNRESOLVED_PLACEHOLDER", f"unknown placeholder {m.group(0)!r}",
                  line_no_of(source_text, m.start()))

    # ---- forbidden tokens ---------------------------------------------------
    at_hits = list(re.finditer(r"@@", source_text))
    if at_hits:
        for m in at_hits[:10]:
            emit_fail("AT_AT_TOKEN", "literal '@@' residue", line_no_of(source_text, m.start()))
    else:
        emit_pass("at-at", "no '@@' residue")
    pilot_hits = list(PILOT_EXP_RE.finditer(source_text))
    if pilot_hits:
        for m in pilot_hits[:10]:
            emit_fail("FORBIDDEN_EXPERIMENT",
                      f"pilot-round experiment {m.group(0)} may not be cited",
                      line_no_of(source_text, m.start()))
    else:
        emit_pass("pilot-experiments", "no EXP-0038..0072 / EXP-0076 / EXP-0077 citations")
    for cid in RETIRED_CLAIMS:
        if cid in source_text:
            emit_fail("RETIRED_CLAIM", f"{cid} appears in the source",
                      line_no_of(source_text, source_text.index(cid)))
    if not any(cid in source_text for cid in RETIRED_CLAIMS):
        emit_pass("retired-claims", "none of the six retired claim ids appears")

    # ---- headings / numbering ----------------------------------------------
    headings = [(line_no_of(source_text, m.start()), m.group(1).strip())
                for m in re.finditer(r"^#\s+(.+?)\s*$", source_text, re.M)]
    if headings:
        emit_pass("headings", f"{len(headings)} H1: " + " | ".join(t.split("{")[0].strip()
                                                                   for _, t in headings))
    manual = [(line, HEADING_NUM_RE.match(t)) for line, t in headings]
    manual = [(line, m.group("num")) for line, m in manual if m]
    numbered_targets = [(line, t) for line, t in headings if "unnumbered" not in t]
    refs = [(line_no_of(source_text, m.start()), m.group("num"))
            for m in SECTION_REF_RE.finditer(source_text)]
    if manual:
        emit_pass("manual-heading-numbers",
                  "headings already carry manual numbers: " + ", ".join(n for _, n in manual))
        if number_sections:
            emit_fail("SECTION_NUMBERING_RISK",
                      "--number-sections would double-number headings that already have numbers")
    else:
        if number_sections:
            if refs:
                nums = [int(r.split(".")[0]) for _, r in refs]
                max_num = len(numbered_targets)
                if max(nums) <= max_num:
                    emit_pass("section-numbering",
                              f"--number-sections: {max_num} numbered H1, all §refs "
                              f"{sorted(set(nums))} resolve")
                else:
                    emit_fail("SECTION_REFERENCE_RISK",
                              f"§ref {max(nums)} exceeds the {max_num} numbered H1 headings")
            else:
                emit_pass("section-numbering", "--number-sections with no §refs")
        else:
            if refs:
                emit_fail("SECTION_NUMBERING_RISK",
                          "source headings have NO manual numbers, but the prose cites "
                          + ", ".join(sorted({f'§{n}' for _, n in refs}))
                          + f" -- with the default (no --number-sections) LaTeX prints unnumbered "
                            f"sections and every §ref dangles; either run --build/--check with "
                            f"--number-sections or add manual numbers to the source headings")
            else:
                emit_pass("section-numbering",
                          "no manual numbers and no §refs; unnumbered sections are consistent")
    dup = {t for _, t in numbered_targets if [x for _, x in headings].count(t) > 1}
    if dup:
        emit_fail("HEADING_DUPLICATE", "duplicate heading text: " + ", ".join(sorted(dup)))

    # ---- page structure / template feasibility ------------------------------
    result = transform(source_text, source_path, data, strict=False,
                       number_sections=number_sections, caption_ids=caption_ids,
                       tex_dir=ROOT / "report", wide=wide)
    if result.page_structure["toc_found"]:
        emit_pass("toc-marker", f"\\tableofcontents at line {result.page_structure['toc_line']}")
    else:
        emit_warn("TOC_INJECTED",
                  "no \\tableofcontents marker in the source; the builder will inject the "
                  "page-3 body switch itself")
    rendered_tables = [s for s in result.tables]
    if len(rendered_tables) == len(matches):
        dist: Dict[str, int] = {}
        for spec in rendered_tables:
            lay = layout_table(spec, wide)["layout"]
            dist[lay] = dist.get(lay, 0) + 1
        emit_pass("table-render",
                  f"{len(rendered_tables)} tables converted to LaTeX (dry run, not written): "
                  + ", ".join(f"{k}={v}" for k, v in sorted(dist.items())))
    for f in result.rejects:
        if f.code in ("TABLE_SHA_MISMATCH", "TABLE_BODY_MISMATCH", "TABLE_ID_UNKNOWN",
                      "TABLE_FRAGMENT_MISSING", "TABLE_SHAPE_MISMATCH", "CAPTION_MISSING",
                      "CLAIM_UNKNOWN", "CLAIM_NOT_ACTIVE", "RETIRED_CLAIM",
                      "FAKE_FIGURE", "FIGURE_FILE_MISSING", "FIGURE_SHA_MISMATCH"):
            emit_fail(f.code, f.detail, f.line)

    # ---- fonts + TeX packages ----------------------------------------------
    fonts = probe_fonts()
    missing_fonts = [n for n, ok in fonts.items() if not ok]
    if missing_fonts:
        emit_fail("FONT_MISSING", "system font(s) not found by fc-list: "
                  + ", ".join(missing_fonts) + " (xelatex would fail; not substituted silently)")
    else:
        emit_pass("fonts", "fc-list has " + ", ".join(f"{n}" for n in fonts))
    pkgs = probe_packages()
    missing_pkgs = [n for n, ok in pkgs.items() if not ok]
    if missing_pkgs:
        emit_fail("TEX_PACKAGE_MISSING", "kpsewhich cannot find: " + ", ".join(missing_pkgs))
    else:
        emit_pass("tex-packages", f"{len(pkgs)} required LaTeX packages found")
    tools = probe_tools()
    emit_pass("tools", f"{tools['pandoc']} / {tools['xelatex']}")

    # ---- summary ------------------------------------------------------------
    check_summary = {
        "source": display,
        "sourceSha256": sha256_bytes(raw),
        "pass": passed, "fail": failed, "warn": warned,
        "tables": len(matches),
        "inlineTables": len(inline_set & expected_inline),
        "inlineTablesExpected": len(expected_inline),
        "supportOnlyTables": len(support_only),
        "supportOnlyOk": support_ok,
        "claims": len(claim_hits),
        "claimsExpanded": bool(claims_expanded),
        "figures": len(all_fig_hits),
        "pending": len(pending_hits),
        "metricPlaceholders": len(metric_hits),
        "numberSections": number_sections,
    }
    print()
    print("-- summary --")
    print(f"pass={passed}  fail={failed}  warn={warned}  named_rejections={failed}")
    print(f"inlineTables={check_summary['inlineTables']}/{check_summary['inlineTablesExpected']}"
          f"  supportOnlyTables={check_summary['supportOnlyOk']}/{check_summary['supportOnlyTables']}"
          f"  claimsExpanded={str(check_summary['claimsExpanded']).lower()}")
    if failed:
        check_summary["verdict"] = "not-build-ready"
        print("verdict: NOT BUILD-READY (named rejections above; --check wrote nothing)")
        print("CHECK-JSON: " + json.dumps(check_summary, ensure_ascii=False))
        return 2
    check_summary["verdict"] = "structurally-build-ready"
    print("verdict: STRUCTURALLY BUILD-READY (this does NOT prove the PDF layout: only "
          "--build + --selftest do)")
    print("CHECK-JSON: " + json.dumps(check_summary, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- #
# output naming (preview vs official artefact path)
# --------------------------------------------------------------------------- #
REPORT_DIR = ROOT / "report"


def default_output_names(outdir: Path) -> Dict[str, Any]:
    """preview.tex/pdf for any test/preview dir; paper.tex/pdf only for report/.

    The official artefacts are refused for report/ unless --allow-report-output is
    given, so a preview build can never silently overwrite the delivered files.
    """
    if outdir.resolve() != REPORT_DIR.resolve():
        return {"tex": "preview.tex", "pdf": "preview.pdf",
                "md": "preview.pandoc.md", "sidecar": "preview.build.json",
                "logs": "preview-xelatex", "preview": True}
    return {"tex": TEX_NAME, "pdf": PDF_NAME, "md": MD_NAME,
            "sidecar": SIDECAR_NAME, "logs": "xelatex", "preview": False}


# --------------------------------------------------------------------------- #
# shared build routine
# --------------------------------------------------------------------------- #
def build_inputs_manifest(mode: str, source_path: Path, outputs: Sequence[Path],
                          preprocessed: Optional[Path], extra: Optional[Dict[str, Any]] = None
                          ) -> Dict[str, Any]:
    def entry(path: Path, role: str) -> Dict[str, Any]:
        return {
            "path": rel_to_root(path),
            "role": role,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }

    inputs = [entry(source_path, "build-source"),
              entry(INDEX_PATH, "table-index"),
              entry(LEDGER_PATH, "ledger")]
    if PAPER_MD.exists() and PAPER_MD.resolve() != source_path.resolve():
        inputs.append(entry(PAPER_MD, "paper-source-draft"))
    if MANIFEST_PATH.exists():
        inputs.append(entry(MANIFEST_PATH, "evidence-manifest"))
    data = load_project()
    manifest: Dict[str, Any] = {
        "kind": "build-paper-inputs",
        "generatedAt": now_utc(),
        "mode": mode,
        "projectDir": str(ROOT),
        "builder": entry(Path(__file__).resolve(), "builder-script"),
        "support": [entry(HEADER_PATH, "latex-header"),
                    entry(TEMPLATE_PATH, "pandoc-template")],
        "inputs": inputs,
        "tools": probe_tools(),
        "ledgerRevision": data.ledger.get("revision"),
        "outputs": [entry(p, "build-output") for p in outputs if p.exists()],
        "sameSourcePath": "tex and pdf are produced by ONE build_paper.py run from the "
                          "preprocessed markdown recorded above; the .tex embeds the source "
                          "sha256 as '% build=...' for independent verification",
    }
    if preprocessed is not None and preprocessed.exists():
        manifest["preprocessed"] = entry(preprocessed, "pandoc-input")
    if extra:
        manifest.update(extra)
    return manifest


LTCAPTYPE_NONE_RE = re.compile(r"\{\\def\\LTcaptype\{none\}[^\n]*\n")
TEXT_TT_RE = re.compile(r"\\texttt\{([^{}]*)\}")
DISPLAY_MATH_RE = re.compile(r"\\\[(.*?)\\\]", re.S)


def normalize_pandoc_tex(tex_text: str) -> Tuple[str, Dict[str, int]]:
    r"""Deterministic builder-side normalisation of pandoc's LaTeX output.

    1. Pandoc wraps a *caption-less* markdown table in
       ``{\def\LTcaptype{none} % do not increment counter ... }``.  Modern
       longtable (TeX Live 2025) refsteps ``\LTcaptype`` at table start, so
       ``none`` aborts with "No counter 'none' defined".  The def line is removed
       (the surrounding group is kept, braces stay balanced).  Those prose tables
       then touch the ``table`` counter; the builder compensates by explicitly
       syncing the ``table`` counter to the evidence-table ordinal before every
       evidence caption, so the Chinese table numbers are exactly 1..N.
    2. Long monospaced paths such as ``report/tables/q2-extended.md`` are a single
       unbreakable word for TeX; invisible break opportunities are added after
       ``/`` so a prose line can wrap without overfull boxes.  The visible text is
       unchanged.
    """
    tex, n_lt = LTCAPTYPE_NONE_RE.subn(lambda _m: "{\n", tex_text)

    def add_breaks(match: re.Match) -> str:
        body = match.group(1)
        if len(body) <= 12 or not ("/" in body or "-" in body):
            return match.group(0)
        body = body.replace("/", "/\\allowbreak{}")
        body = body.replace("-", "-\\allowbreak{}")
        return r"\texttt{" + body + "}"

    tex, n_tt = TEXT_TT_RE.subn(add_breaks, tex)

    def fit_math(match: re.Match) -> str:
        return "\\[\\bpMathFit{" + match.group(1) + "}\\]"

    tex, n_math = DISPLAY_MATH_RE.subn(fit_math, tex)
    return tex, {"ltcaptype_none_removed": n_lt, "texttt_breakpoints": n_tt,
                 "display_math_fitted": n_math, "changed": int(tex != tex_text)}


def run_pandoc(md_path: Path, out_path: Path, *, to: str = "latex",
               pdf_engine: Optional[str] = None, number_sections: bool,
               buildmeta: str, cwd: Path) -> subprocess.CompletedProcess:
    cmd = [
        PANDOC, str(md_path),
        "--from", "markdown+tex_math_dollars+pipe_tables+fenced_divs+raw_tex+footnotes",
        "--standalone",
        "--template", str(TEMPLATE_PATH),
        "--include-in-header", str(HEADER_PATH),
        "-V", "buildmeta=" + buildmeta,
        "-o", str(out_path),
    ]
    if number_sections:
        cmd.append("--number-sections")
    if pdf_engine:
        cmd.extend(["--pdf-engine", pdf_engine, "--to", "latex"])
    else:
        cmd.extend(["--to", to])
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))


def run_xelatex(tex_path: Path, cwd: Path, passes: int = 2,
                log_prefix: str = "xelatex") -> Dict[str, Any]:
    logs = []
    ok = True
    for n in range(1, passes + 1):
        proc = subprocess.run([XELATEX, "-interaction=nonstopmode", "-halt-on-error",
                               tex_path.name],
                              capture_output=True, text=True, cwd=str(cwd))
        log_path = cwd / f"{log_prefix}-{n}.log"
        log_path.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
        logs.append(rel_to_root(log_path))
        if proc.returncode != 0:
            ok = False
            break
    pdf = cwd / tex_path.with_suffix(".pdf").name
    return {"ok": ok, "logs": logs, "pdf": rel_to_root(pdf) if pdf.exists() else None,
            "pdfBytes": pdf.stat().st_size if pdf.exists() else 0}


def prepare_build(source_path: Path, outdir: Path, *, number_sections: bool,
                  caption_ids: bool, wide: str = "rotate",
                  names: Optional[Dict[str, Any]] = None
                  ) -> Tuple[int, Dict[str, Any]]:
    """Transform + write intermediate + run pandoc. Returns (exit, report)."""
    names = names or default_output_names(outdir)
    source_text = source_path.read_text(encoding="utf-8")
    data = load_project()
    result = transform(source_text, source_path, data, strict=True,
                       number_sections=number_sections, caption_ids=caption_ids,
                       tex_dir=outdir, wide=wide)
    rejects = list(result.rejects) + list(result.pending) + list(result.unknown_placeholders)
    if rejects:
        print("== named rejections (refusing to build) ==")
        for f in rejects:
            print("[REJECT] " + f.render())
        return 2, {"rejects": [f.render() for f in rejects]}

    outdir.mkdir(parents=True, exist_ok=True)  # create/use; never delete other files
    md_path = outdir / names["md"]
    md_path.write_text(result.pandoc_md, encoding="utf-8")
    md_sha = sha256_file(md_path)
    source_sha = sha256_text(source_text)

    buildmeta = (
        f"build=build_paper.py source={rel_to_root(source_path)} "
        f"source-sha256={source_sha} pandoc-input={md_path.name} "
        f"pandoc-input-sha256={md_sha} header-sha256={sha256_file(HEADER_PATH)} "
        f"template-sha256={sha256_file(TEMPLATE_PATH)} "
        f"builder-sha256={sha256_file(Path(__file__).resolve())} "
        f"outdir={rel_to_root(outdir)} "
        f"preview={'true' if names.get('preview') else 'false'} "
        f"number-sections={'true' if number_sections else 'false'} "
        f"wide-tables={wide} tables={len(result.tables)} "
        f"claims={len(set(result.claim_ids))} figures={len(result.figure_ids)} "
        f"generated-at={now_utc()}"
    )
    tex_path = outdir / names["tex"]
    proc = run_pandoc(md_path, tex_path, number_sections=number_sections,
                      buildmeta=buildmeta, cwd=outdir)
    if proc.returncode != 0:
        print("[FAIL] pandoc could not produce the .tex")
        print((proc.stdout or "")[-4000:])
        print((proc.stderr or "")[-4000:])
        return 3, {"rejects": ["PANDOC_FAILED"], "pandoc": proc.stderr[-2000:]}
    tex_text = tex_path.read_text(encoding="utf-8")
    tex_text, tex_norm = normalize_pandoc_tex(tex_text)
    if tex_norm["changed"]:
        tex_path.write_text(tex_text, encoding="utf-8")
    checks: List[Tuple[str, bool, str]] = [
        ("tex-no-ltcaptype-none", "LTcaptype{none}" not in tex_text,
         f"pandoc LTcaptype-none wrappers removed ({tex_norm['ltcaptype_none_removed']})"),
        ("tex-has-source-sha", source_sha in tex_text, "source sha256 embedded in .tex"),
        ("tex-has-md-sha", md_sha in tex_text, "pandoc-input sha256 embedded in .tex"),
        ("tex-no-placeholders",
         ("{{" not in tex_text) and ("metric:EXP-" not in tex_text)
         and ("\\{\\{" not in tex_text),
         "no unresolved {{...}} (nor pandoc-escaped \\{\\{) in .tex"),
        ("tex-no-pending", "PENDING-FIGURE" not in tex_text, "no PENDING-FIGURE in .tex"),
        ("tex-no-fancyhdr", "fancyhdr" not in tex_text, "no running-header package"),
        ("tex-booktabs", "\\toprule" in tex_text or not result.tables, "booktabs rules present"),
    ]

    pdf_info: Dict[str, Any] = {}
    report = {
        "preview": bool(names.get("preview")),
        "outdir": rel_to_root(outdir),
        "numberSections": bool(number_sections),
        "wideTables": wide,
        "source": rel_to_root(source_path),
        "sourceSha256": source_sha,
        "preprocessed": rel_to_root(md_path),
        "preprocessedSha256": md_sha,
        "tex": rel_to_root(tex_path),
        "texSha256": sha256_file(tex_path),
        "tables": len(result.tables),
        "layouts": {s.tid: layout_table(s, wide)["layout"] for s in result.tables},
        "claims": sorted(set(result.claim_ids)),
        "figures": sorted(set(result.figure_ids)),
        "texNormalization": tex_norm,
        "checks": [{"name": n, "passed": p, "detail": d} for n, p, d in checks],
        "pdf": pdf_info,
    }
    return (0 if all(p for _, p, _ in checks) else 4), report


# --------------------------------------------------------------------------- #
# --build
# --------------------------------------------------------------------------- #
def run_build(args: argparse.Namespace) -> int:
    source_path = resolve_source(args.source)
    outdir = Path(args.outdir).resolve() if args.outdir else (TEST_ROOT / "build")
    if outdir == (ROOT / "report").resolve() and not args.allow_report_output:
        print("[REJECT] OUTPUT_PATH_FORBIDDEN  refusing to write report/paper.tex|pdf "
              "without --allow-report-output (this batch must not produce the official artefacts)")
        return 2
    if not source_path.exists():
        print(f"[REJECT] SOURCE_MISSING  {source_path} does not exist")
        return 2
    names = default_output_names(outdir)
    print(f"== build_paper.py --build ==")
    print(f"source : {rel_to_root(source_path)}")
    print(f"outdir : {rel_to_root(outdir)}")
    print(f"mode   : {'PREVIEW (preview.tex/pdf, never bound)' if names['preview'] else 'official path (report/)'}")
    code, report = prepare_build(source_path, outdir, number_sections=args.number_sections,
                                 caption_ids=args.caption_ids, wide=args.wide_tables,
                                 names=names)
    if code != 0:
        return code
    if args.pdf:
        pdf_info = run_xelatex(outdir / names["tex"], outdir, passes=2,
                               log_prefix=str(names["logs"]))
        report["pdf"] = pdf_info
        if not pdf_info["ok"] or not pdf_info["pdf"]:
            print("[FAIL] xelatex could not compile the generated .tex (see logs)")
            print(json.dumps(pdf_info, ensure_ascii=False, indent=1))
            return 5
    outputs = [outdir / names["tex"]]
    if report["pdf"].get("pdf"):
        outputs.append(outdir / names["pdf"])
    manifest = build_inputs_manifest("build", source_path, outputs,
                                     outdir / MD_NAME, extra={"build": report})
    (outdir / "BUILD-INPUTS.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (outdir / names["sidecar"]).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(f"[PASS] tex   : {report['tex']}  sha256={report['texSha256']}")
    if report["pdf"].get("pdf"):
        print(f"[PASS] pdf   : {report['pdf']['pdf']}  bytes={report['pdf']['pdfBytes']}")
    print(f"[PASS] inputs: {rel_to_root(outdir / 'BUILD-INPUTS.json')}")
    if names["preview"]:
        print("PREVIEW: preview.tex/preview.pdf are NOT bound to a render; the formal artefacts "
              "require --outdir report --allow-report-output and modeling_deliver artifact.")
    else:
        print("NOTE: report/ output still has to be bound via modeling_deliver artifact "
              "before it counts as delivered.")
    return 0


# --------------------------------------------------------------------------- #
# --selftest
# --------------------------------------------------------------------------- #
SELFTEST_TITLE = "构建器自测：宽表、长表、图位与证据登记"


def extract_block(source_text: str, tid: str) -> Optional[Tuple[str, str]]:
    pat = re.compile(
        r"<!-- table-begin:" + re.escape(tid) + r" sha256=\S+ -->\n.*?\n"
        r"<!-- table-end:" + re.escape(tid) + r" -->",
        re.S,
    )
    m = pat.search(source_text)
    if not m:
        return None
    lines = source_text.split("\n")
    start = source_text.count("\n", 0, m.start())
    cap_idx = start - 1
    while cap_idx >= 0 and not lines[cap_idx].strip():
        cap_idx -= 1
    if cap_idx < 0:
        return None
    cm = CAPTION_RE.match(lines[cap_idx].strip())
    if not cm or cm.group("id") != tid:
        return None
    return lines[cap_idx], m.group(0)


def assertion(results: List[Dict[str, Any]], name: str, ok: bool, detail: str) -> bool:
    results.append({"name": name, "passed": bool(ok), "detail": detail})
    print(("  [PASS] " if ok else "  [FAIL] ") + f"{name:<26} {detail}")
    return ok


def pick_selftest_figure(data: ProjectData) -> Optional[Dict[str, Any]]:
    """First ACTIVE ledger figure whose file exists and whose bytes match its sha256."""
    for fig_id in sorted(data.figures, reverse=True):
        rec = data.figures[fig_id]
        if not figure_is_active(rec):
            continue
        path = ROOT / str(rec.get("path") or "")
        if not path.exists():
            continue
        if rec.get("sha256") and sha256_file(path) != rec["sha256"]:
            continue
        return rec
    return None


def run_selftest(args: argparse.Namespace) -> int:
    print("== build_paper.py --selftest ==")
    print("builds a tiny document out of REAL fragments (q1-models / q1-targets), "
          "one real claim (CLAIM-0056) and one real ACTIVE ledger figure")
    test_dir = TEST_ROOT / "selftest"
    test_dir.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []

    if not PAPER_MD.exists():
        print("[FAIL] SELFTEST_SOURCE_MISSING report/paper.md is needed for the real fragments")
        return 2
    paper_text = PAPER_MD.read_text(encoding="utf-8")
    wide = extract_block(paper_text, "q1-models")
    longb = extract_block(paper_text, "q1-targets")
    if not wide or not longb:
        print("[FAIL] SELFTEST_FRAGMENT_MISSING could not extract q1-models / q1-targets "
              "blocks (with captions) from report/paper.md")
        return 2

    selftest_fig = pick_selftest_figure(load_project())
    if selftest_fig is None:
        print("[FAIL] SELFTEST_FIGURE_UNAVAILABLE no ACTIVE ledger figure with a hash-matching file")
        return 2
    fig_id = selftest_fig["id"]
    mock = "\n".join([
        "---",
        f'title: "{SELFTEST_TITLE}"',
        "author: \"\"",
        "date: \"\"",
        "lang: zh-CN",
        "---",
        "",
        "> **DRAFT——构建器自测文档，非论文。** 本文件只验证 md→tex 路径。",
        "",
        "# 摘要 {.unnumbered}",
        "",
        "自测摘要：宽表、长表、证据登记块与图位都必须走到预期的 LaTeX 环境。",
        "",
        "**关键词：** 构建；自测；LaTeX",
        "",
        r"\newpage",
        r"\tableofcontents",
        r"\newpage",
        "",
        "# 一 表格",
        "",
        "宽表（7 列，应走 resizebox）：",
        "",
        wide[0],
        "",
        wide[1],
        "",
        "长表（30 行，应走 longtable）：",
        "",
        longb[0],
        "",
        longb[1],
        "",
        "# 二 图与证据登记",
        "",
        "图位：",
        "",
        "{{figure:" + fig_id + "}}",
        "",
        "**证据登记（自测主结论）。** {{claim:CLAIM-0056}}",
        "",
        "# 三 连排表格与链接",
        "",
        "无题注正文表（由 pandoc 生成 longtable，不得触发 LTcaptype 错误）：",
        "",
        "| 任务 | 建模对象 | 核心输出 |",
        "| --- | --- | --- |",
        "| 感官评分 | $Y=f(X)+E$ | 折外连续预测 |",
        "| 关键因素 | 化学成分与感官的同期关联 | 每个维度 3 个候选 |",
        "",
        "链接测试：[DOI](https://doi.org/10.1234/selftest)。",
        "",
        "# 四 结束",
        "",
        "自测结束。",
        "",
    ])
    md_path = test_dir / "selftest-paper.md"
    md_path.write_text(mock, encoding="utf-8")
    source_sha = sha256_text(mock)
    print(f"mock source : {rel_to_root(md_path)}  sha256={source_sha}")

    data = load_project()
    tex_dir = test_dir
    result = transform(mock, md_path, data, strict=True, number_sections=False,
                       caption_ids=True, tex_dir=tex_dir, require_all_tables=False)
    rejects = list(result.rejects) + list(result.pending) + list(result.unknown_placeholders)
    if rejects:
        print("== named rejections while transforming the selftest source ==")
        for f in rejects:
            print("[REJECT] " + f.render())
        return 2

    md_out = test_dir / MD_NAME
    md_out.write_text(result.pandoc_md, encoding="utf-8")
    md_sha = sha256_file(md_out)
    buildmeta = (f"build=build_paper.py mode=selftest source={rel_to_root(md_path)} "
                 f"source-sha256={source_sha} pandoc-input-sha256={md_sha} "
                 f"tables={len(result.tables)} claims={len(set(result.claim_ids))} "
                 f"figures={len(result.figure_ids)} generated-at={now_utc()}")
    tex_path = test_dir / TEX_NAME
    proc = run_pandoc(md_out, tex_path, number_sections=False, buildmeta=buildmeta,
                      cwd=test_dir)
    if proc.returncode != 0:
        print("[FAIL] PANDOC_FAILED")
        print((proc.stdout or "")[-3000:])
        print((proc.stderr or "")[-3000:])
        return 3
    tex = tex_path.read_text(encoding="utf-8")
    tex, selftest_norm = normalize_pandoc_tex(tex)
    if selftest_norm["changed"]:
        tex_path.write_text(tex, encoding="utf-8")
    print()
    print("-- static LaTeX assertions --")

    assertion(results, "booktabs-toprule", "\\toprule" in tex, "\\toprule present")
    assertion(results, "booktabs-midrule", "\\midrule" in tex, "\\midrule present")
    assertion(results, "booktabs-bottomrule", "\\bottomrule" in tex, "\\bottomrule present")
    assertion(results, "resizebox-wide", "\\resizebox{\\linewidth}" in tex,
              "wide 7-column table wrapped in resizebox")
    assertion(results, "longtable-long", "\\begin{longtable}" in tex,
              "30-row table rendered as longtable")
    n_captionof = tex.count("\\captionof{table}")
    n_longcap = tex.count("\\caption{")
    assertion(results, "table-captions", n_captionof + n_longcap == 2,
              f"2 table captions (captionof={n_captionof}, longtable caption={n_longcap})")
    assertion(results, "table-id-comment",
              "%% table-id: q1-models sha256:" in tex and "%% table-id: q1-targets sha256:" in tex,
              "table ids + sha256 kept as LaTeX comments")
    assertion(results, "tablenote", "\\begin{tablenote}" in tex, "table notes rendered small")
    assertion(results, "table-values-verbatim",
              "0.3593" in tex and "0.3982" in tex and "−" in tex,
              "table cell values (incl. U+2212 minus) are unchanged in the .tex")
    assertion(results, "figure-includegraphics", "\\includegraphics" in tex,
              "\\includegraphics emitted for the figure placeholder")
    assertion(results, "figure-caption", "\\captionof{figure}" in tex and fig_id in tex,
              f"figure caption + id present ({fig_id})")
    assertion(results, "figure-file-hash", "%% figure-id: " + fig_id + " sha256:" in tex,
              f"figure sha256 comment present ({fig_id})")
    assertion(results, "claim-block",
              "\\begin{evidenceregistry}" in tex and "\\end{evidenceregistry}" in tex
              and "CLAIM-0056" in tex,
              "evidence-registry environment emitted for CLAIM-0056")
    assertion(results, "claim-text-verbatim", "train-only" in tex and "3×3×3" in tex,
              "claim statement text survives verbatim")
    assertion(results, "claim-limitations", "\\textbf{限制：}" in tex, "limitations list present")
    assertion(results, "no-running-headers",
              "fancyhdr" not in tex and "\\pagestyle{fancy}" not in tex
              and "\\markboth" not in tex and "\\markright" not in tex,
              "no running-header package/style/mark")
    assertion(results, "footer-plain", "\\pagestyle{plain}" in tex, "article plain page style")
    assertion(results, "front-matter-gobble", "\\pagenumbering{gobble}" in tex,
              "front matter has no page numbers")
    assertion(results, "body-arabic", "\\pagenumbering{arabic}" in tex,
              "body renumbered from arabic 1")
    assertion(results, "title-page-empty-style", "\\thispagestyle{empty}" in tex,
              "title/TOC pages carry an empty page style")
    assertion(results, "toc", "\\tableofcontents" in tex, "TOC present on page 2")
    assertion(results, "draft-banner", "\\begin{draftbanner}" in tex, "DRAFT banner styled as a block")
    assertion(results, "secnumdepth-off", "\\setcounter{secnumdepth}{-\\maxdimen}" in tex,
              "no automatic section numbering (source controls it)")
    assertion(results, "chinese-captions",
              "\\renewcommand{\\tablename}{表}" in tex and "\\renewcommand{\\figurename}{图}" in tex
              and "\\renewcommand{\\contentsname}{目录}" in tex,
              "Chinese 表/图/目录 captions")
    assertion(results, "source-sha-comment", source_sha in tex, "source sha256 embedded in .tex")
    assertion(results, "no-unresolved-placeholders", "{{" not in tex, "no {{...}} in .tex")
    assertion(results, "no-pending-figure", "PENDING-FIGURE" not in tex, "no PENDING-FIGURE in .tex")
    assertion(results, "no-at-at", "@@" not in tex, "no @@ in .tex")
    assertion(results, "prose-table-no-ltcaptype", "LTcaptype{none}" not in tex,
              "pandoc caption-less longtable wrapper without LTcaptype{none}")
    assertion(results, "prose-table-pandoc-widths", "\\real{" in tex,
              "pandoc prose-table width expressions retained (calc)")
    assertion(results, "hyperref-href", "\\href" in tex, "markdown links became \\href")

    # -- optional compile, strictly inside .rework/build-test/ --
    print()
    print("-- xelatex compile (inside .rework/build-test/selftest only) --")
    pdf_info = run_xelatex(tex_path, test_dir, passes=2)
    compiled = bool(pdf_info["ok"] and pdf_info["pdf"])
    assertion(results, "xelatex-compiles", compiled,
              "xelatex exit 0" if compiled else "xelatex failed; see " + str(pdf_info["logs"]))
    if compiled:
        assertion(results, "pdf-nonempty", pdf_info["pdfBytes"] > 0,
                  f"pdf bytes={pdf_info['pdfBytes']}")
        page_info: Dict[str, Any] = {}
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(str(test_dir / PDF_NAME))
            pages = [p.extract_text() or "" for p in reader.pages]
            page_info = {"pages": len(pages)}
            assertion(results, "pdf-pages>=3", len(pages) >= 3, f"{len(pages)} pages")
            p1 = pages[0] if pages else ""
            p2 = pages[1] if len(pages) > 1 else ""
            assertion(results, "page1-title+draft+keywords",
                      "构建器自测" in p1 and "DRAFT" in p1 and "关键词" in p1,
                      "page 1 carries title, DRAFT marker and keywords")
            assertion(results, "page2-toc", "目录" in p2, "page 2 is the TOC")
            body_text = "\n".join(pages[2:]) if len(pages) > 2 else ""
            assertion(results, "body-captions-chinese",
                      all(f"表 {i}" in body_text for i in (1, 2)) and "图 1" in body_text,
                      "body shows continuous Chinese 表 1/表 2 and 图 1 counters")
            p1_last = p1.strip().splitlines()[-1].strip() if p1.strip() else ""
            p2_last = p2.strip().splitlines()[-1].strip() if p2.strip() else ""
            assertion(results, "pages1-2-unumbered",
                      not p1_last.isdigit() and not p2_last.isdigit(),
                      f"page1 tail={p1_last[:20]!r} page2 tail={p2_last[:20]!r}")
            body = pages[2] if len(pages) > 2 else ""
            body_last = body.strip().splitlines()[-1].strip() if body.strip() else ""
            assertion(results, "body-page-number=1", body_last == "1",
                      f"body page 1 footer={body_last[:20]!r}")
            page_info["page1_tail"] = p1_last
            page_info["page2_tail"] = p2_last
            page_info["body1_tail"] = body_last
        except ImportError:
            print("  [WARN] pypdf not available: PDF page assertions skipped (reported, not passed)")
            page_info = {"pages": None, "pypdf": "missing"}
    else:
        page_info = {"compile": "failed", **pdf_info}

    # -- report + manifest --
    passed = sum(1 for r in results if r["passed"])
    failed = [r for r in results if not r["passed"]]
    outputs = [tex_path]
    if pdf_info.get("pdf"):
        outputs.append(test_dir / PDF_NAME)
    manifest = build_inputs_manifest("selftest", md_path, outputs,
                                     md_out, extra={
                                         "selftest": {
                                             "assertions": results,
                                             "passed": passed,
                                             "failed": [r["name"] for r in failed],
                                             "pdf": page_info,
                                             "compile": pdf_info,
                                             "fragments": ["q1-models (resizebox)",
                                                           "q1-targets (longtable)",
                                                           "{{claim:CLAIM-0056}}",
                                                           "{{figure:" + fig_id + "}}"],
                                         }
                                     })
    (test_dir / "SELFTEST-REPORT.json").write_text(
        json.dumps({"assertions": results, "pdf": page_info, "compile": pdf_info},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    manifest_path = TEST_ROOT / "BUILD-INPUTS.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    print()
    print(f"-- selftest summary: {passed}/{len(results)} assertions passed --")
    if failed:
        print("failed: " + ", ".join(r["name"] for r in failed))
        print(f"artifacts kept: {rel_to_root(test_dir)}")
        return 2
    print(f"tex     : {rel_to_root(tex_path)}")
    if pdf_info.get("pdf"):
        print(f"pdf     : {pdf_info['pdf']} ({pdf_info['pdfBytes']} bytes, "
              f"{page_info.get('pages')} pages)")
    print(f"manifest: {rel_to_root(manifest_path)}")
    print("NOTE: the selftest PDF is a test artefact under .rework/build-test/, not report/paper.pdf.")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def resolve_source(arg: Optional[str]) -> Path:
    if not arg:
        return DEFAULT_SOURCE
    path = Path(arg)
    if not path.is_absolute():
        path = ROOT / path
    return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Table/claim-aware LaTeX builder (see module docstring).")
    parser.add_argument("--source", help="markdown source (default report/rendered.md)")
    parser.add_argument("--outdir", help="output directory for --build (never report/ by default)")
    parser.add_argument("--check", action="store_true", help="read-only structural audit")
    parser.add_argument("--selftest", action="store_true", help="build+assert a small real-fragment doc")
    parser.add_argument("--build", action="store_true", help="build .tex (and .pdf with --pdf)")
    parser.add_argument("--pdf", action="store_true", help="with --build: compile the generated .tex")
    parser.add_argument("--number-sections", action="store_true",
                        help="let LaTeX number sections (needed when the source has no manual numbers)")
    parser.add_argument("--caption-ids", dest="caption_ids", action="store_true", default=True,
                        help="append '（表 id ...）' to table captions (default on)")
    parser.add_argument("--no-caption-ids", dest="caption_ids", action="store_false",
                        help="omit the visible table id from captions")
    parser.add_argument("--allow-report-output", action="store_true",
                        help="allow --outdir report (the official artefacts); refused by default")
    parser.add_argument("--index", help="alternative report/tables/INDEX.json (tests only)")
    parser.add_argument("--wide-tables", choices=("rotate", "wrap"), default="rotate",
                        help="wide short tables: sidewaystable (rotate, default) or wrapped "
                             "p{} columns kept in place (wrap)")
    args = parser.parse_args(argv)
    global CAPTION_IDS
    CAPTION_IDS = bool(args.caption_ids)

    modes = [m for m in ("check", "selftest", "build") if getattr(args, m)]
    if len(modes) > 1:
        parser.error("choose exactly one of --check / --selftest / --build")
    if not modes:
        args.check = True
        modes = ["check"]
    if args.source and args.selftest:
        parser.error("--selftest builds its own source; do not pass --source")
    if args.index:
        set_index_path(Path(args.index))
    try:
        if args.selftest:
            return run_selftest(args)
        if args.build:
            return run_build(args)
        return run_check(resolve_source(args.source), args.number_sections,
                         args.caption_ids, args.wide_tables)
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] unhandled exception: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
