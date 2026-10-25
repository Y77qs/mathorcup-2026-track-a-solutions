"""Build revised Markdown and TeX only within the independent revision folder."""
from pathlib import Path
import json,re,subprocess,shutil,hashlib
OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[1]
t=json.loads((OUT/'support/tables.json').read_text())
s=(OUT/'support/manuscript.template.md').read_text()
g=t['grades'].splitlines()
def subset(indices):
    rows=[]
    for line in g:
        cells=[x.strip() for x in line.strip('|').split('|')]
        rows.append('| '+' | '.join(cells[i] for i in indices)+' |')
    return '\n'.join(rows)
replacements={'GRADES_AROMA':subset([0,1,2,3,4,5,6]),
              'GRADES_FLAVOUR':subset([0,1,7,8,9,10,11]),'TOP_MAIN':t['top_main'],
              'TOP_FULL':t['top_full'],'PROFILES':t['profiles'],'TRANSFER':t['transfer'],
              'DEFECT_CHECK':t['defect_check'],'DICTIONARY':t['dictionary'],
              'BASE_R2':f"{json.loads((ROOT/'experiments/EXP-0001/metrics.json').read_text())['r2_50dim']:.4f}",
              'SCENARIO_DIST':f"{json.loads((ROOT/'experiments/EXP-0033/outputs.json').read_text())['transfer-scenarios'][-1]['targetMahalanobis']:.4f}"}
for k,v in replacements.items():s=s.replace('@@'+k+'@@',v)
assert '@@' not in s
assert not re.search(r'(EXP|VAL|ROB|MCON|SPLIT|DATA|TGT|FIG)-\d{4}',s)
(OUT/'paper_revised.md').write_text(s)
header=r'''\usepackage{caption}
\captionsetup{font=small,labelfont=bf,labelsep=quad,hypcap=false}
\renewcommand{\figurename}{图}
\renewcommand{\tablename}{表}
\renewcommand{\contentsname}{目录}
\usepackage{etoolbox}
\newcommand{\tablefontsize}{\small}
\newcommand{\tablestretch}{1.15}
\BeforeBeginEnvironment{longtable}{\begingroup\tablefontsize\setlength{\tabcolsep}{3pt}\setlength{\parskip}{0pt}\renewcommand{\arraystretch}{\tablestretch}}
\AfterEndEnvironment{longtable}{\endgroup}
\setlength{\parindent}{2em}
\setlength{\parskip}{0.35em}
\setlength{\emergencystretch}{3em}
\setCJKsansfont{Songti SC}
\setCJKmonofont{Songti SC}
\AtBeginDocument{\hypersetup{linkcolor=black,urlcolor=blue,citecolor=black}}
\makeatletter
\newcommand{\EnsureSpace}[1]{\par\begingroup\@tempdima=\pagegoal\advance\@tempdima by-\pagetotal\ifdim\@tempdima<#1\newpage\fi\endgroup}
\renewenvironment{figure}[1][]{\par\medskip\noindent\begin{minipage}{\linewidth}\def\@captype{figure}\centering}{\end{minipage}\par\medskip}
\def\ps@paper{\def\@oddhead{\hfil\small 啤酒化合物与感官强度建模\hfil}\let\@evenhead\@oddhead\def\@oddfoot{\hfil\thepage\hfil}\let\@evenfoot\@oddfoot}
\makeatother
\pagestyle{paper}
\setlength{\headheight}{14pt}
'''
(OUT/'support/header.tex').write_text(header)
cmd=['pandoc','paper_revised.md','-o','paper_revised.tex','--standalone','--number-sections',
     '--toc-depth=2','-V','documentclass=article','-V','fontsize=11pt','-V','geometry:a4paper',
     '-V','geometry:margin=2.0cm','-V','mainfont=Times New Roman','-V','CJKmainfont=Songti SC',
     '-V','monofont=Menlo','-V','colorlinks=true','-H','support/header.tex']
subprocess.run(cmd,cwd=OUT,check=True)
# Set a concise title size, allow long names to break at punctuation, keep tables readable.
tex=(OUT/'paper_revised.tex').read_text()
tex=tex.replace('\\maketitle',r'\begingroup\let\newpage\relax\maketitle\endgroup\vspace{-2em}')
tex=tex.replace(r'\tableofcontents',r'\begingroup\small\setlength{\parskip}{0pt}\tableofcontents\endgroup')
def size_table(match):
    block=match.group()
    if '化学成分\n' in block and '入选频率' in block:
        weights=[.18,.05,.32,.11,.11,.06,.17]
        wrap=True
    elif '感官维度\n' in block and '第 1 位' in block:
        weights=[.19,.27,.27,.27]
        wrap=False
    else:
        return block.replace(r'\real{0.1429}',r'\real{0.142857}')
    it=iter(weights)
    block=re.sub(r'\\real\{[0-9.]+\}',lambda m:r'\real{'+f'{next(it):.6f}'+'}',block)
    if wrap:block=r'\begingroup\renewcommand{\tablefontsize}{\footnotesize}\renewcommand{\tablestretch}{1.1}'+'\n'+block+'\n'+r'\endgroup'
    return block
tex=re.sub(r'\\begin\{longtable\}.*?\\end\{longtable\}',size_table,tex,flags=re.S)
tex=tex.replace(r'\IfFileExists{footnotehyper.sty}{\usepackage{footnotehyper}}{\usepackage{footnote}}','')
tex=tex.replace(r'\makesavenoteenv{longtable}','')
tex=tex.replace(r'\captionsetup[table]{skip=6pt}','')
tex=re.sub(r'(\\textbf\{表 \d+.*?\})',lambda m:r'\EnsureSpace{6\baselineskip}'+'\n'+m.group(),tex,flags=re.S)
(OUT/'paper_revised.tex').write_text(tex)
shutil.copyfile(ROOT/'experiments/EXP-0033/samples.csv',OUT/'data/generated_spectra_310.csv')
originals=json.loads((OUT/'support/original_sha256.json').read_text())
assert all(hashlib.sha256((ROOT/'report'/n).read_bytes()).hexdigest()==v for n,v in originals.items())
print('Built independent revised Markdown and TeX; originals unchanged.')
