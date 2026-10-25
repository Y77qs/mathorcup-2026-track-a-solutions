"""Check delivered content, numeric provenance, and preservation of originals."""
from pathlib import Path
import hashlib,json,re
import numpy as np
import pandas as pd
import pdfplumber
from pypdf import PdfReader
from scipy.stats import spearmanr
OUT=Path(__file__).resolve().parents[1]
ROOT=OUT.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
original=json.loads((OUT/'support/original_sha256.json').read_text())
preserved={n:sha(ROOT/'report'/n)==h for n,h in original.items()}
assert all(preserved.values())
md=(OUT/'paper_revised.md').read_text()
assert not re.search(r'(EXP|VAL|SPLIT|DATA|TGT|MCON|ROB|VP|FIG)-\d{4}|\{\{|@@',md)
assert len(re.findall(r'^# (?!.*unnumbered)',md,flags=re.M))==11 # nine chapters, two appendices
g=pd.read_csv(OUT/'data/grades_250x50.csv');cols=[c for c in g if c.startswith('g6__')]
assert len(g)==250 and len(cols)==50
assert g[cols].isin(range(7)).all().all()
assert g.equals(pd.read_csv(ROOT/'experiments/EXP-0026/grades_all.csv'))
top=pd.read_csv(OUT/'data/top3_all_50_dimensions.csv')
assert len(top)==150 and top.dimension.nunique()==50
assert top.groupby('dimension').size().eq(3).all()
assert top.pi.between(0,1).all() and top.S.between(0,1).all()
assert np.isclose(top.pi.mean(),.46468)
for _,group in top.groupby('dimension'):
 assert group.pi.is_monotonic_decreasing
original_top=pd.DataFrame(json.loads((ROOT/'experiments/EXP-0029/outputs.json').read_text())['final_top3'])
for c in original_top:
 if pd.api.types.is_numeric_dtype(original_top[c]):assert np.allclose(top[c],original_top[c])
 else:assert top[c].equals(original_top[c])
profiles=pd.read_csv(OUT/'data/style_profiles_oof.csv')
q3=json.loads((ROOT/'experiments/EXP-0033/outputs.json').read_text())
profile_checks={}
for style in ['Tripel','Kriek','Lambic']:
 rows=[]
 for no,group in profiles[profiles['style']==style].groupby('fold'):
  tab=group.groupby('dimension')[['generated_proxy','real_label']].mean()
  rows.append([spearmanr(tab.generated_proxy,tab.real_label).statistic,np.mean(abs(tab.generated_proxy-tab.real_label))])
 rho,mae=np.mean(rows,axis=0);expected=q3['profile-metrics']['perStyle'][style]
 assert np.isclose(rho,expected['spearman'],atol=1e-10)
 assert np.isclose(mae,expected['mae'],atol=1e-10)
 profile_checks[style]={'fold_mean_spearman':rho,'fold_mean_mae':mae,'agrees_with_original':True}
samples=pd.read_csv(OUT/'data/generated_spectra_310.csv')
assert len(samples)==310
assert all((samples[c]<=1e-8).all() for c in ['excess__DMS','excess__X2.3.butanedione','excess__X4VG'])
assert all((samples[c]>=-1e-8).all() for c in ['t2n_margin','stale_hops_margin'])
assert sha(OUT/'data/generated_spectra_310.csv')==sha(ROOT/'experiments/EXP-0033/samples.csv')
reader=PdfReader(OUT/'paper_revised.pdf');pdftext='\n'.join(p.extract_text() for p in reader.pages)
assert all(term in pdftext for term in ['Beer#1','Citronellol','Geraniol','0.7940','35.9232','Kriek','Lambic'])
assert not re.search(r'(EXP|VAL|MCON|ROB|SPLIT)-\d{4}',pdftext)
log=(OUT/'paper_revised.log').read_text(errors='replace')
assert not re.search(r'^!|Overfull|Missing character|Undefined control sequence',log,re.M)
assert 'Output written on' in log
positions=[]
with pdfplumber.open(OUT/'paper_revised.pdf') as pdf:
 for i,p in enumerate(pdf.pages):
  bad=[c for c in p.chars if c['x0']<20 or c['x1']>p.width-20]
  assert not bad,(i+1,bad[:1])
  positions.append({'page':i+1,'text_characters':len(p.chars),'inside_page_bounds':True})
report={'originals_preserved':preserved,'pdf_pages':len(reader.pages),'main_figures':len(list((OUT/'figures').glob('*.png'))),
        'grade_shape':[250,50],'top3_dimensions':50,'top3_entries':150,'profile_reconstruction':profile_checks,
        'generated_spectra_rows':310,'five_declared_constraints_recounted':True,
        'no_internal_ids_or_placeholders':True,'no_overfull_boxes_or_missing_glyphs':True,
        'page_bounds':positions,'outputs_sha256':{n:sha(OUT/n) for n in ['paper_revised.md','paper_revised.tex','paper_revised.pdf']}}
(OUT/'support/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['page_bounds','outputs_sha256']},ensure_ascii=False,indent=2))
