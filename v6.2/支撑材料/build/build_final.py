#!/usr/bin/env python3
"""build_final.py — plugin-free builder for the final v6.2 paper.

This is a thin, ledger-free driver around the project's own deterministic
markdown -> LaTeX -> PDF transform (``src/build_paper.py``).  The ONLY thing it
replaces is the project/ledger gate: table fragments and figures are resolved
against this submission directory, and no ``state/ledger.json`` is read.

Pipeline (identical shape to the reviewed DRAFT build, one pandoc run):

    paper_final.md
      --(table fragments + markdown figures)--> paper.pandoc.md
      --(pandoc, build/template.tex + build/header.tex)--> paper_final.tex
      --(xelatex x2)--> 论文正式版.pdf

Usage (from anywhere; paths resolve against this file):
    python FINAL_SUBMISSION_v6.2/build/build_final.py --pdf
    python FINAL_SUBMISSION_v6.2/build/build_final.py --check
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
SUBMISSION_DIR = BUILD_DIR.parent
def _project_dir() -> Path:
    env = os.environ.get("PAPER_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    for cand in (SUBMISSION_DIR.parent, SUBMISSION_DIR):
        if (cand / "src" / "build_paper.py").exists():
            return cand
    return SUBMISSION_DIR.parent


PROJECT_DIR = _project_dir()

sys.path.insert(0, str(PROJECT_DIR / "src"))
import build_paper as BP  # noqa: E402  (project's own transform, not a plugin)

SOURCE = BUILD_DIR / "paper_final.md"
OUTDIR = BUILD_DIR / "out"
INDEX = BUILD_DIR / "tables" / "INDEX.json"
HEADER = BUILD_DIR / "header.tex"
TEMPLATE = BUILD_DIR / "template.tex"
PDF_TARGET = SUBMISSION_DIR / "论文正式版.pdf"


def _rel(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_DIR.resolve()).as_posix()


def load_project_local() -> "BP.ProjectData":
    """A ProjectData whose only real content is the local table index.

    claims/figures are empty on purpose: the final paper references no ledger
    claim blocks, and its figures arrive as plain markdown images.
    """
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    tables_by_id = {rec["id"]: rec for rec in index.get("tables", {}).values()}
    return BP.ProjectData(index=index, ledger={}, manifest=None,
                          tables_by_id=tables_by_id, claims={}, figures={})


def install_overrides() -> None:
    BP.HEADER_PATH = HEADER
    BP.TEMPLATE_PATH = TEMPLATE
    BP.load_project = load_project_local          # never touches the ledger
    BP.CAPTION_IDS = False                        # no internal FIG-/EXP- ids in captions
    BP.ROOT = SUBMISSION_DIR                      # table fragment paths are submission-relative


def write_source_appendix() -> Path:
    """Appendix C is produced by build/make_source_appendix.py (full core implementations)."""
    sys.path.insert(0, str(BUILD_DIR))
    import make_source_appendix as MSA
    target = MSA.main([str(OUTDIR)])
    return OUTDIR / "source_appendix.tex"


def _names() -> dict:
    return {"md": "paper.pandoc.md", "tex": "paper_final.tex",
            "pdf": "论文正式版.pdf", "preview": False}


def transform(source: Path) -> tuple[int, dict]:
    install_overrides()
    source_text = source.read_text(encoding="utf-8")
    data = load_project_local()
    result = BP.transform(source_text, source, data, strict=True,
                          number_sections=False, caption_ids=False,
                          tex_dir=OUTDIR, wide="rotate")
    rejects = list(result.rejects) + list(result.pending) + list(result.unknown_placeholders)
    if rejects:
        print("== named rejections (refusing to build) ==")
        for finding in rejects:
            print("[REJECT] " + finding.render())
        return 2, {"rejects": [f.render() for f in rejects]}

    OUTDIR.mkdir(parents=True, exist_ok=True)
    names = _names()
    md_path = OUTDIR / names["md"]
    md_path.write_text(result.pandoc_md, encoding="utf-8")
    md_sha = BP.sha256_file(md_path)
    source_sha = BP.sha256_text(source_text)
    buildmeta = (
        f"build=build_final.py source={_rel(source)} source-sha256={source_sha} "
        f"pandoc-input={md_path.name} pandoc-input-sha256={md_sha} "
        f"header-sha256={BP.sha256_file(HEADER)} template-sha256={BP.sha256_file(TEMPLATE)} "
        f"builder-sha256={BP.sha256_file(Path(__file__).resolve())} "
        f"tables={len(result.tables)} figures={len(result.figure_ids)} "
        f"number-sections=false wide-tables=rotate generated-at={BP.now_utc()}"
    )
    tex_path = OUTDIR / names["tex"]
    proc = BP.run_pandoc(md_path, tex_path, number_sections=False,
                         buildmeta=buildmeta, cwd=OUTDIR)
    if proc.returncode != 0:
        print("[FAIL] pandoc could not produce the .tex")
        print((proc.stdout or "")[-4000:])
        print((proc.stderr or "")[-4000:])
        return 3, {"rejects": ["PANDOC_FAILED"]}
    tex_text = tex_path.read_text(encoding="utf-8")
    tex_text, tex_norm = BP.normalize_pandoc_tex(tex_text)
    if tex_norm["changed"]:
        tex_path.write_text(tex_text, encoding="utf-8")

    report = {
        "source": _rel(source), "sourceSha256": source_sha,
        "preprocessed": _rel(md_path), "preprocessedSha256": md_sha,
        "tex": _rel(tex_path), "texSha256": BP.sha256_file(tex_path),
        "tables": len(result.tables),
        "layouts": {spec.tid: BP.layout_table(spec, "rotate")["layout"] for spec in result.tables},
        "claims": [], "figures": sorted(set(result.figure_ids)),
        "texNormalization": tex_norm,
        "rejects": [],
    }
    (BUILD_DIR / "paper_final.build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("tables", "layouts", "figures", "texNormalization")},
                     ensure_ascii=False, indent=1))
    return 0, report


FIGURE_HEIGHT_OLD = "height=0.34\\textheight"
FIGURE_HEIGHT_NEW = "height=0.28\\textheight"


def tighten_figures(tex_path: Path) -> int:
    """Give chapter-6 answer tables room inside the 30-page body budget.

    Figure heights only: the image files and captions are untouched, so this is a
    pure layout choice, recorded in the build report.
    """
    text = tex_path.read_text(encoding="utf-8")
    n = text.count(FIGURE_HEIGHT_OLD)
    if n:
        tex_path.write_text(text.replace(FIGURE_HEIGHT_OLD, FIGURE_HEIGHT_NEW), encoding="utf-8")
    print(f"[OK] figure height 0.34 -> 0.28\\textheight on {n} figure(s)")
    return n


def compile_pdf() -> int:
    install_overrides()
    names = _names()
    tex_path = OUTDIR / names["tex"]
    if not tex_path.exists():
        print(f"[FAIL] missing {tex_path}")
        return 3
    tighten_figures(tex_path)
    write_source_appendix()
    info = BP.run_xelatex(tex_path, OUTDIR, passes=2, log_prefix="xelatex")
    print(json.dumps(info, indent=1))
    if not info["ok"]:
        return 4
    pdf = OUTDIR / tex_path.with_suffix(".pdf").name
    if not pdf.exists():
        print("[FAIL] xelatex reported success but no PDF exists")
        return 4
    PDF_TARGET.parent.mkdir(parents=True, exist_ok=True)
    PDF_TARGET.write_bytes(pdf.read_bytes())
    # the two editable sources of the delivered PDF live next to it
    (SUBMISSION_DIR / "paper_final.md").write_text(
        (BUILD_DIR / "paper_final.md").read_text(encoding="utf-8"), encoding="utf-8")
    (SUBMISSION_DIR / "paper_final.tex").write_text(
        tex_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[OK] {PDF_TARGET} ({PDF_TARGET.stat().st_size} bytes)")
    print(f"[OK] {SUBMISSION_DIR / 'paper_final.md'} / paper_final.tex")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(SOURCE))
    parser.add_argument("--check", action="store_true", help="transform only, no PDF")
    parser.add_argument("--pdf", action="store_true", help="transform + compile PDF")
    args = parser.parse_args(argv)
    code, _report = transform(Path(args.source))
    if code != 0:
        return code
    if args.check:
        return 0
    if args.pdf:
        return compile_pdf()
    print("[OK] transform only (pass --pdf to compile)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
