"""build_paper.py — compile report/rendered.md into report/paper.tex and report/paper.pdf.

The three deliverables must come from the SAME rendered.md:
  rendered.md --(pandoc stand-alone)--> paper.tex --(xelatex)--> paper.pdf
and both files are then bound to the current render id by modeling_deliver artifact.

Run from the project root:
    python src/build_paper.py
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
SOURCE = REPORT / "rendered.md"
TEX = REPORT / "paper.tex"
PDF = REPORT / "paper.pdf"

COMMON = [
    "--from", "markdown+tex_math_dollars+pipe_tables+grid_tables+backtick_code_blocks",
    "--standalone",
    "-V", "documentclass=article",
    "-V", "geometry:margin=2.0cm",
    "-V", "fontsize=11pt",
    "-V", "CJKmainfont=Songti SC",
    "-V", "mainfont=Times New Roman",
    "-V", "monofont=Menlo",
    "-V", "colorlinks=true",
    "--toc",
    "--toc-depth=2",
    "--number-sections",
]


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        sys.stderr.write(result.stdout[-4000:])
        sys.stderr.write(result.stderr[-4000:])
        raise SystemExit("command failed (%d): %s" % (result.returncode, " ".join(command)))
    return result


def pandoc_source() -> Path:
    """Prepare the pandoc input: the rendered paper with figure comments split off.

    WHY. `modeling_deliver render` writes every figure as

        ![caption](../figures/x.png)
        <!-- FIG-0001 sha256:... -->

    i.e. the image and the provenance comment are ONE markdown paragraph. pandoc's implicit-figure
    rule only promotes an image that stands alone in its paragraph, so the comment silently turns
    all figures into inline images with no `figure`/`caption` environment in the .tex/.pdf.
    Inserting a blank line before the comment restores one paragraph per figure; the content is
    otherwise byte-for-byte the rendered text (the comment is a provenance annotation, not prose).
    The transformed file is written next to the render and named explicitly, never silently.
    """
    text = SOURCE.read_text(encoding="utf-8")
    if "{{" in text:
        raise SystemExit("rendered.md still contains an unresolved placeholder; refusing to compile")
    fixed = re.sub(r"(\n)(<!-- FIG-[0-9]{4} sha256:)", r"\1\n\2", text)
    # Captions are prose set in the MAIN font; a few Unicode maths operators have no glyph in
    # Times New Roman and would print as a box (U+2208 seen in FIG-0031's caption). Rendering them
    # through math mode uses the math font instead; only the display form changes, never the text.
    fixed = fixed.replace("\u2208", "$\\in$")
    if fixed != text:
        target = REPORT / "rendered.pandoc.md"
        target.write_text(fixed, encoding="utf-8")
        return target
    return SOURCE


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit("missing %s: run modeling_deliver render first" % SOURCE)
    source = pandoc_source()
    # 图片路径是相对 report/ 的（../figures/...），因此以 report/ 为工作目录运行，
    # 否则 pandoc 会把图片当作不可获取的资源并在 tex 里退化成文字描述。
    run(["pandoc", str(source), "-o", str(TEX)] + COMMON + ["--to", "latex"], cwd=str(REPORT))
    # A second, independent pass compiles the PDF directly from the same source (not from the tex), so an
    # edited tex can never silently diverge from the delivered PDF.
    run(["pandoc", str(source), "-o", str(PDF)] + COMMON + ["--pdf-engine=xelatex"], cwd=str(REPORT))
    print("built %s (%d bytes) and %s (%d bytes)" % (TEX, TEX.stat().st_size, PDF, PDF.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
