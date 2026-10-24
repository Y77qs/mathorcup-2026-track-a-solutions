"""论文三格式构建：report/rendered.md → paper.tex（pandoc）→ paper.pdf（xelatex ×2）。

不伪造：pandoc/xelatex 缺失或编译失败时，如实记录失败原因并以非零退出码结束。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L

REPORT = L.ROOT / "report"
HEADER = REPORT / "paper-header.tex"
HEADER_TEX = r"""\usepackage{xeCJK}
\usepackage{graphicx}
\usepackage{float}
\usepackage{longtable}
\usepackage{booktabs}
\usepackage{amsmath}
\setmainfont{Arial Unicode MS}
\setCJKmainfont{PingFang SC}
\setCJKsansfont{PingFang SC}
\setCJKmonofont{PingFang SC}
\graphicspath{{../figures/}}
\setlength{\emergencystretch}{3em}
"""


def run(cmd, cwd, timeout=600):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return {"cmd": " ".join(cmd), "returncode": p.returncode,
            "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}


def main() -> int:
    md = REPORT / "rendered.md"
    if not md.exists():
        print(json.dumps({"ok": False, "reason": "report/rendered.md missing"}, ensure_ascii=False))
        return 2
    HEADER.write_text(HEADER_TEX, encoding="utf-8")
    # 展示层取整：render 输出的机器精度数字在这里收敛到 4 位小数（不改动 rendered.md 本体）
    import re as _re
    txt = md.read_text(encoding="utf-8")
    def _round(m):
        v = float(m.group(0))
        return f"{v:.4f}"
    rounded = _re.sub(r"-?\d+\.\d{5,}", _round, txt)
    build_md = REPORT / "rendered_build.md"
    build_md.write_text(rounded, encoding="utf-8")
    pandoc = shutil.which("pandoc")
    xelatex = shutil.which("xelatex")
    res = {"pandoc": pandoc, "xelatex": xelatex, "steps": []}
    if not pandoc or not xelatex:
        res["ok"] = False
        res["reason"] = "pandoc or xelatex not found"
        (REPORT / "build_report.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 3

    cmds = [
        ["pandoc", "rendered_build.md", "-o", "paper.tex", "--standalone",
         "--resource-path=report:figures", "-V", "documentclass=ctexart",
         "-V", "classoption=UTF8", "-H", "paper-header.tex", "--number-sections"],
    ]
    ok = True
    for c in cmds:
        r = run(c, REPORT)
        res["steps"].append(r)
        if r["returncode"] != 0:
            ok = False
            break
    if ok:
        for _ in range(2):
            r = run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "paper.tex"], REPORT)
            res["steps"].append(r)
            if r["returncode"] != 0:
                ok = False
                break

    pdf = REPORT / "paper.pdf"
    tex = REPORT / "paper.tex"
    res["tex_exists"] = tex.exists() and tex.stat().st_size > 0
    res["pdf_exists"] = pdf.exists() and pdf.stat().st_size > 0
    res["pdf_bytes"] = pdf.stat().st_size if pdf.exists() else 0
    res["pages"] = None
    if res["pdf_exists"]:
        try:
            from pypdf import PdfReader
            res["pages"] = len(PdfReader(str(pdf)).pages)
        except Exception as e:  # noqa
            res["pages_error"] = str(e)
    # 图片可打开性
    figs, bad = [], []
    for f in sorted((L.ROOT / "figures").glob("*.png")):
        figs.append(f.name)
        try:
            from PIL import Image
            with Image.open(f) as im:
                im.verify()
        except Exception:
            bad.append(f.name)
    res["figures"] = figs
    res["bad_figures"] = bad
    res["ok"] = bool(ok and res["tex_exists"] and res["pdf_exists"]
                     and (res["pages"] or 0) > 0 and not bad)
    (REPORT / "build_report.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ["ok", "tex_exists", "pdf_exists", "pdf_bytes",
                                          "pages", "bad_figures", "pandoc", "xelatex"]},
                     ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
