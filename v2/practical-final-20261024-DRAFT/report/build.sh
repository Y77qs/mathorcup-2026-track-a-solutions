#!/usr/bin/env bash
# report/build.sh — 一键把 Markdown 论文渲染稿转成 TeX 并编译 PDF。
#
# 用法：
#   ./report/build.sh            # 主论文：report/rendered.md -> report/paper.tex -> report/paper.pdf
#   ./report/build.sh minimal    # 管道最小样例：report/tex/minimal.md -> .../minimal.tex -> .../minimal.pdf
#
# 纪律（为什么这样组织）：
#   * 主论文的源是 **report/rendered.md**，由 `modeling_deliver {action:"render"}` 从项目台账解析占位符生成；
#     paper.md 里的数字是占位符，不能直接进 TeX（`holdout_r2_mean` 这类下划线会让 LaTeX 报错，且数字未经台账核对）。
#   * 本脚本只负责“已渲染的 Markdown -> TeX -> PDF”，不解析、不生成、不改写任何数字。
#   * rendered.md 缺失或比 paper.md 旧时直接失败（提示重新 render），避免把过期正文编进 PDF。
#   * 工作目录取 Markdown 所在目录，插图相对路径按 Markdown 作者视角生效；编译中间文件进 tex/build/。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-paper}"

XELATEX="${XELATEX:-/usr/local/bin/xelatex}"
PANDOC="${PANDOC:-pandoc}"
TEMPLATE_REL="tex/pandoc-template.tex"

PANDOC_COMMON=(
  --standalone
  --number-sections
  --toc
  --toc-depth=1
  -V documentclass=article
  -V classoption=a4paper,12pt
  -V geometry=margin=2.5cm
  -V CJKmainfont="Songti SC"
  -V colorlinks=true
  -V linkcolor=black
  -V urlcolor=black
  -V citecolor=black
  -V toc-title=目录
)

case "$TARGET" in
  paper)
    WORKDIR="$PROJECT_DIR/report"          # Markdown 与 paper.tex 所在目录
    SRC_MD="rendered.md"
    TEX_REL="paper.tex"
    PDF_REL="paper.pdf"
    OUTDIR="tex/build"                     # 相对于 WORKDIR
    ;;
  minimal)
    WORKDIR="$PROJECT_DIR/report/tex"      # 最小样例：Markdown 自带 ../../figures 相对路径
    SRC_MD="minimal.md"
    TEX_REL="minimal.tex"
    PDF_REL="minimal.pdf"
    OUTDIR="_build"
    TEMPLATE_REL="pandoc-template.tex"
    ;;
  *)
    echo "用法: $0 [paper|minimal]" >&2
    exit 2
    ;;
esac

cd "$WORKDIR"

if [ "$TARGET" = "paper" ]; then
  LOG="$WORKDIR/build.log"
else
  LOG="$PROJECT_DIR/report/build-sample.log"
fi
: > "$LOG"
log() { printf '%s\n' "$*" | tee -a "$LOG"; }

log "[build] target=$TARGET  workdir=$WORKDIR  $(date '+%Y-%m-%d %H:%M:%S')"

command -v "$PANDOC" >/dev/null 2>&1 || { log "[build][ERROR] 找不到 pandoc"; exit 3; }
[ -x "$XELATEX" ] || { log "[build][ERROR] 找不到可执行的 xelatex: $XELATEX"; exit 3; }
[ -f "$TEMPLATE_REL" ] || { log "[build][ERROR] 找不到模板: $WORKDIR/$TEMPLATE_REL"; exit 3; }

if [ ! -f "$SRC_MD" ]; then
  if [ "$TARGET" = "paper" ]; then
    log "[build][ERROR] 缺少 $SRC_MD：请先运行 modeling_deliver {action:\"render\"} 由台账生成渲染稿。"
  else
    log "[build][ERROR] 缺少 $SRC_MD。"
  fi
  exit 4
fi

if [ "$TARGET" = "paper" ] && [ -f paper.md ] && [ paper.md -nt "$SRC_MD" ]; then
  log "[build][ERROR] rendered.md 比 paper.md 旧：正文已改动，请重新运行 modeling_deliver {action:\"render\"}。"
  exit 5
fi

# 防御：渲染稿里若仍有未解析的占位符，TeX 会因为下划线/冒号而失败，且数字未被台账核对。
if grep -qF '{{' "$SRC_MD"; then
  log "[build][ERROR] $SRC_MD 仍含有未解析的 '{{' 占位符，拒绝编译。"
  grep -nF '{{' "$SRC_MD" | head -20 | tee -a "$LOG" >&2
  exit 6
fi

mkdir -p "$OUTDIR"

log "[build] pandoc: $SRC_MD -> $TEX_REL"
# 排版变换（只影响 PDF，不改 rendered.md）：图片按 80% 行宽缩放，避免原尺寸溢出。
TYPESET_MD="$OUTDIR/typeset.md"
python3 "$PROJECT_DIR/report/tex/typeset.py" "$SRC_MD" "$TYPESET_MD"
log "[build] pandoc: $SRC_MD (typeset: $TYPESET_MD) -> $TEX_REL"
"$PANDOC" "$TYPESET_MD" -o "$TEX_REL" --template="$TEMPLATE_REL" "${PANDOC_COMMON[@]}" 2>&1 | tee -a "$LOG"
[ -s "$TEX_REL" ] || { log "[build][ERROR] pandoc 未产出 $TEX_REL"; exit 7; }

# 强制 [H] 放置：pandoc 默认的浮动体在连续插图时会在页面底部溢出（Overfull \vbox），
# 用 float 包的 [H] 就地放置（放不下时自动换页），保证图不越界、且紧跟正文。
python3 - "$TEX_REL" <<'PYFIX'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
n = s.count('\\begin{figure}')
s = s.replace('\\begin{figure}', '\\begin{figure}[H]')
open(p, 'w', encoding='utf-8').write(s)
print('figures forced to [H]:', n)
PYFIX

for pass in 1 2; do
  log "[build] xelatex pass $pass"
  if ! "$XELATEX" -interaction=nonstopmode -halt-on-error -file-line-error \
        -output-directory="$OUTDIR" "$TEX_REL" > "$OUTDIR/pass$pass.out" 2>&1; then
    log "[build][ERROR] xelatex pass $pass 失败，最后 40 行日志："
    tail -40 "$OUTDIR/pass$pass.out" | tee -a "$LOG" >&2
    log "[build][HINT] 完整日志: $WORKDIR/$OUTDIR/${TEX_REL%.tex}.log"
    exit 8
  fi
done

BUILT_PDF="$OUTDIR/${TEX_REL%.tex}.pdf"
[ -f "$BUILT_PDF" ] || { log "[build][ERROR] 未生成 PDF: $WORKDIR/$BUILT_PDF"; exit 9; }
cp "$BUILT_PDF" "$PDF_REL"

PAGES="$("$PANDOC" --version >/dev/null 2>&1; \
  /Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python - "$PDF_REL" 2>/dev/null <<'PY' || true
import sys
try:
    import pypdf
    print(len(pypdf.PdfReader(sys.argv[1]).pages))
except Exception:
    print("?")
PY
)"

WARNINGS="$(grep -c 'Overfull \\hbox' "$OUTDIR/${TEX_REL%.tex}.log" 2>/dev/null || true)"
log "[build] OK  pdf=$WORKDIR/$PDF_REL  pages=$PAGES  overfull_hbox=$WARNINGS"
log "[build] 完整 LaTeX 日志: $WORKDIR/$OUTDIR/${TEX_REL%.tex}.log"
log "[build] 编译命令: cd $WORKDIR && $XELATEX -interaction=nonstopmode -halt-on-error -output-directory=$OUTDIR $TEX_REL （两遍）"
