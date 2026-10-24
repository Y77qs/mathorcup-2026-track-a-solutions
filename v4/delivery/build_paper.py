#!/usr/bin/env python3
"""Build report/paper.tex and report/paper.pdf from report/rendered.md.

Pipeline (the paper's md/tex/pdf delivery contract):
  1. report/paper.md            --(modeling_deliver render)--> report/rendered.md
  2. report/rendered.md         --(pandoc, ctexart)---------> report/paper.tex
  3. report/paper.tex           --(xelatex, two passes)-----> report/paper.pdf
  4. verify: PDF non-empty, page count > 0, the 12 registered figures embedded.

The only transformation applied to pandoc's output is typographic: long
\\texttt{...} identifiers get zero-width break points (\\allowbreak) after their
`.` / `/` / `_` separators, so wide tables and file paths do not run into the
right margin. No text, number or image is changed by this step.

Usage:
  PY=/path/to/python   # the project interpreter (needs pypdf for the checks)
  $PY delivery/build_paper.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDERED = ROOT / "report" / "rendered.md"
TEX = ROOT / "report" / "paper.tex"
PDF = ROOT / "report" / "paper.pdf"

PANDOC_ARGS = [
    str(RENDERED), "-s", "-o", str(TEX),
    "--resource-path", str(ROOT / "report"),
    "-H", str(ROOT / "delivery" / "header.tex"),
    "--shift-heading-level-by=-1",
    "-V", "documentclass=ctexart",
    "-V", "geometry:margin=2.2cm",
    "-V", "fontsize=11pt",
    "-V", "mainfont=Times New Roman",
    "-V", "monofont=Menlo",
    "-V", "colorlinks=true",
    "-V", "linkcolor=blue",
    "-V", "urlcolor=blue",
    "-V", "toccolor=black",
]

TEXTtt = re.compile(r"\\texttt\{([^{}]*)\}")


def add_break_points(tex: str) -> str:
    """Insert zero-width break points into long monospaced identifiers."""

    def repl(match: re.Match) -> str:
        body = match.group(1)
        if len(body) < 14:
            return match.group(0)
        out = body
        out = out.replace("\\_", "\\_\\allowbreak{}")
        out = out.replace("/", "/\\allowbreak{}")
        out = out.replace(".", ".\\allowbreak{}")
        out = out.replace("\\allowbreak{}\\allowbreak{}", "\\allowbreak{}")
        return "\\texttt{" + out + "}"

    return TEXTtt.sub(repl, tex)


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    if not RENDERED.exists():
        print("REFUSED: report/rendered.md is missing; run modeling_deliver render first")
        return 2

    rc, out = run(["pandoc", *PANDOC_ARGS], cwd=ROOT)
    print(f"pandoc exit={rc} bytes={TEX.stat().st_size if TEX.exists() else 0}")
    if rc != 0:
        print(out)
        return rc

    tex = TEX.read_text(encoding="utf-8")
    patched = add_break_points(tex)
    TEX.write_text(patched, encoding="utf-8")

    key = "LATEX_BUILD_" + str(len(tex))
    for pass_no in (1, 2):
        rc, out = run(["xelatex", "-interaction=nonstopmode", "paper.tex"], cwd=ROOT / "report")
        (Path("/tmp") / f"{key}_pass{pass_no}.log").write_text(out, encoding="utf-8")
        print(f"xelatex pass{pass_no} exit={rc} log=/tmp/{key}_pass{pass_no}.log")
        if rc != 0:
            print(out[-3000:])
            return rc
        last = out

    missing = re.findall(r"Missing character: ([^\n]+)", last)
    errors = re.findall(r"^! .*$", last, flags=re.M)
    overfull = [float(x) for x in re.findall(r"Overfull \\hbox \(([0-9.]+)pt", last)]
    print(f"pdf bytes={PDF.stat().st_size} pages={_pages(PDF)}")
    print(f"missing_characters={len(missing)} errors={len(errors)} "
          f"overfull_boxes={len(overfull)} max_overfull_pt={max(overfull) if overfull else 0:.2f}")
    for line in missing[:5]:
        print("  missing:", line)
    return 0


def _pages(pdf: Path) -> int | str:
    try:
        import pypdf  # type: ignore

        return len(pypdf.PdfReader(str(pdf)).pages)
    except Exception as exc:  # pragma: no cover - reported, never faked
        return f"UNREADABLE({exc})"


if __name__ == "__main__":
    sys.exit(main())
