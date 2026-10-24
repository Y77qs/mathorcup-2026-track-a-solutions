"""report/tex/typeset.py — 把渲染稿转成“排版稿”（只影响 PDF，不改 report/rendered.md）。

做两件事，且只做这两件：
1. 图片按 80% 行宽缩放：matplotlib 以 160 dpi 保存的 PNG 原尺寸常超过版心宽度，
   直接 \\includegraphics 会溢出页边距并产生 Overfull \\hbox；这里给每个图片段落加
   pandoc 的 width 属性。
2. 原文其余部分逐字保留，方便事后比对（本脚本不做任何数字/文字替换）。

用法：python3 typeset.py <src.md> <dst.md>
"""
import re
import sys

IMAGE_LINE = re.compile(r'^!\[(.*)\]\(([^)]+)\)\s*$')


def main(src: str, dst: str) -> None:
    out = []
    with open(src, encoding='utf-8') as f:
        for line in f:
            stripped = line.rstrip('\n')
            m = IMAGE_LINE.match(stripped)
            if m:
                alt, path = m.group(1), m.group(2)
                # 图片段落后补一个空行：把紧随其后的 <!-- FIG-... --> 注释拆成独立段落，
                # pandoc 才会把“仅含图片的段落”识别为 figure 并保留图注（implicit_figures）。
                out.append('![%s](%s){width=72%%}\n\n' % (alt, path))
            else:
                out.append(line)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(''.join(out))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: typeset.py <src.md> <dst.md>')
    main(sys.argv[1], sys.argv[2])
