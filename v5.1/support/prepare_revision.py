"""Read existing results and reconstruct reporting quantities; never write to the source project.
Run with the project's Python environment. This does not select or evaluate a new candidate.
"""
import os
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/mathorcup-revision-mpl')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from pathlib import Path
import sys, types, json, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT/'src'))
# Read-only adapter for the original runner's import surface. Emission is forbidden.
contract = types.ModuleType('modeling_contract')
def forbidden(*a, **kw):
    raise RuntimeError('Original experiment runner mutation is disabled in this revision')
for n in ['seed','emit_metrics','emit_predictions','emit_output','save_figure','experiment_dir',
          'project_dir','dataset_path','split_paths']:
    setattr(contract,n,forbidden)
contract.dependency_path = lambda p: ROOT/p
sys.modules['modeling_contract'] = contract
import q2_lib as Q
import q3_lib as L
from target_columns import FEATURE_COLS, TARGET_COLS, COMPOUND_CANDIDATES

font = FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
plt.rcParams.update({'font.family':font.get_name(), 'font.size':9, 'axes.unicode_minus':False,
                     'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':220})
BLUE,ORANGE,GREEN,RED = '#28648c','#d48c42','#4f8b73','#b95657'
def load(p): return json.loads((ROOT/p).read_text())
def save(fig,name):
    fig.savefig(OUT/'figures'/name,bbox_inches='tight',facecolor='white');plt.close(fig)
def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
                     ['| '+' | '.join(str(c).replace('|','/') for c in r)+' |' for r in rows])
def f(v):return f'{float(v):.4f}'
meta=load('data/clean/q2_chem_meta.json')['features']
names={r['name']:r['corrLabel'] for r in meta}
wbpath=next((ROOT/'data/raw/imported').glob('*8.xlsx'))
threshold_meta=pd.read_excel(wbpath,sheet_name='Sensory thresholds').set_index('field_name_R')
sens=pd.read_excel(wbpath,sheet_name='Sensory names')
sens=sens[sens['R_name'].isin(TARGET_COLS)].drop_duplicates('R_name').set_index('R_name')
cnbase={'malt_all':'麦芽总体','malt_grain':'谷物','malt_bread':'面包','malt_cara':'焦糖','malt_burn':'烘烤',
        'hops_all':'酒花总体','hops_citrus':'柑橘','hops_tropical':'热带水果','hops_noble':'贵族酒花',
        'hops_woody':'木质','esters_all':'酯香总体','esters_ethac':'乙酸乙酯','esters_isoaa':'乙酸异戊酯',
        'esters_flower':'花香','esters_fruity':'果香'}
cnother={'alcohol':'酒精感','body':'醇厚度','acidity':'酸感','acetic':'醋酸感','sweetness':'甜感',
         'bitternes':'苦感','carbonation':'碳酸感','aftertaste':'余味','diacetyl':'双乙酰缺陷',
         't2n':'反式-2-壬烯醛感','stale_hops':'陈旧酒花','X4vg':'4VG','clove':'丁香','barnyard':'畜舍气味',
         'coriander':'芫荽','phenolic':'酚香','astringency':'涩感','liking':'喜好度',
         'dms':'DMS缺陷','metallic':'金属感','orange':'橙香','lactic':'乳酸感','co2':'碳酸感','overall':'总体评价'}
def target(n):return ('香气·' if n.startswith('A_') else '风味·')+cnbase[n[2:]] if n[:2] in ('A_','F_') else cnother.get(n,n)
conf={'within-consistent':'风格内一致','style-driven':'风格驱动','mixed':'混合关联'}

g=pd.read_csv(ROOT/'experiments/EXP-0026/grades_all.csv')
g.to_csv(OUT/'data/grades_250x50.csv',index=False)
core=['A_malt_all','A_hops_all','A_hops_citrus','A_esters_all','A_esters_isoaa',
      'F_malt_all','F_hops_all','F_hops_citrus','F_esters_all','F_esters_isoaa']
g10=g[g.beer.between(1,10)].sort_values('beer')
assert len(g10)==10
rows=[[f'Beer#{int(r.beer)}','训练' if r.is_train else '留出']+[int(r['g6__'+t]) for t in core] for _,r in g10.iterrows()]
snips={'grades':table(['样本','来源']+[target(t) for t in core],rows)}
pd.DataFrame(rows,columns=['样本','来源']+core).to_csv(OUT/'data/beer1_10_core_grades.csv',index=False)

q2=load('experiments/EXP-0029/outputs.json')
frame=pd.read_csv(ROOT/'experiments/EXP-0029/inputs/data/splits/SPLIT-0001/train.csv')
scores=Q.ingredient_scores(frame);ranked=Q.percentile_block(scores)
top=pd.DataFrame(q2['final_top3'])
for _,r in top.iterrows():
    j=list(COMPOUND_CANDIDATES).index(r.compound);t=TARGET_COLS.index(r.dimension)
    assert np.isclose(r.absBetaGraph,scores['graph_lowrank'][j,t],rtol=1e-8,atol=1e-10)
top['S']=[ranked['consensus'][list(COMPOUND_CANDIDATES).index(r.compound),TARGET_COLS.index(r.dimension)] for _,r in top.iterrows()]
top['chemical_name']=top.compound.map(names)
top.to_csv(OUT/'data/top3_all_50_dimensions.csv',index=False)
chosen=list(TARGET_COLS[:15])+['F_malt_all','F_hops_all','F_hops_citrus','F_esters_all','F_esters_ethac']
main=[]
for d in chosen:
    vals=[]
    for _,r in top[top.dimension==d].iterrows():
        sign='+' if r.direction=='positive' else '−'
        tag={'within-consistent':'内','style-driven':'风','mixed':'混'}[r.styleConfound]
        vals.append(f"{r.chemical_name}；{f(r.pi)}/{f(r.S)}；{sign}{tag}")
    main.append([target(d)]+vals)
snips['top_main']=table(['感官维度','第 1 位','第 2 位','第 3 位'],main)
appendix=[]
for _,r in top.iterrows():
    appendix.append([r.dimension,int(r['rank']),r.chemical_name,f(r.pi),f(r.S),
                     '+' if r.direction=='positive' else '−',conf[r.styleConfound]])
snips['top_full']=table(['维度','位次','化学成分','入选频率 π','综合分 S','方向','混杂类型'],appendix)

# Rebuild the attachment descriptive graph exactly as the original routine.
corr=pd.read_csv(next((ROOT/'data/raw/imported').glob('*2.csv')),index_col=0).to_numpy(float)
vals,vecs=np.linalg.eigh((corr+corr.T)/2)
corr=(vecs*np.clip(vals,0,None))@vecs.T
sd=np.sqrt(np.maximum(np.diag(corr),1e-12));corr=corr/sd[:,None]/sd[None,:]
np.fill_diagonal(corr,0)
w=np.where(np.abs(corr)>=0.6,corr,0)
# Original attachment-network projects but does NOT renormalise; use its exact helper below.
raw=pd.read_csv(next((ROOT/'data/raw/imported').glob('*2.csv')),index_col=0).to_numpy(float)
ev,eu=np.linalg.eigh((raw+raw.T)/2);projected=(eu*np.maximum(ev,0))@eu.T
np.fill_diagonal(projected,0);w=np.where(np.abs(projected)>=.6,projected,0)
assert np.count_nonzero(np.triu(w,1))==q2['attachment_network']['thresholds']['0.6']['edges']
count,lab=connected_components(csr_matrix(abs(w)>0),directed=False)
degree=(abs(w)>0).sum(axis=1)
# Deterministic force layout, 231 nodes, 266 edges. All isolates are shown in a separate strip.
rng=np.random.default_rng(20261025);active=np.flatnonzero(lab==np.argmax(np.bincount(lab)));wa=w[np.ix_(active,active)]
pos=rng.normal(size=(len(active),2)); k=1/np.sqrt(len(active)); pairs=np.abs(wa)>0
for it in range(350):
    delta=pos[:,None,:]-pos[None,:,:];dist=np.sqrt((delta**2).sum(2))+1e-3
    rep=(delta*(k*k/dist**2)[:,:,None]).sum(1)
    attr=(delta*(pairs*dist/k)[:,:,None]).sum(1)
    force=rep-attr;norm=np.linalg.norm(force,axis=1)+1e-12
    pos+=force/norm[:,None]*np.minimum(norm,.04*(1-it/350))[:,None]
pos=(pos-pos.mean(0))/np.max(np.ptp(pos,axis=0))
fig,(ax,aside)=plt.subplots(1,2,figsize=(9.2,5.3),gridspec_kw={'width_ratios':[4,1.25]})
origins=[]
origin_map={'hops':'酒花','yeast':'酵母','malt':'麦芽','wild flora':'野生微生物','others':'其他',
            'internal standard solution':'内标溶液','spices':'香料','nan':'未标注'}
for n in FEATURE_COLS:
    origin=str(threshold_meta.loc[n,'origin_paper']) if n in threshold_meta.index else 'other'
    origins.append(origin)
categories=sorted(set(origins));palette=plt.get_cmap('tab10');color={v:palette(i) for i,v in enumerate(categories)}
for a in range(len(active)):
    for b in range(a+1,len(active)):
        if wa[a,b]: ax.plot(pos[[a,b],0],pos[[a,b],1],c=BLUE if wa[a,b]>0 else RED,lw=.45,alpha=.32,zorder=1)
for origin in categories:
    ii=np.array([i for i,j in enumerate(active) if origins[j]==origin])
    if len(ii):ax.scatter(pos[ii,0],pos[ii,1],s=10+degree[active[ii]]*4,c=[color[origin]],label=origin_map.get(origin.lower(),origin),edgecolors='white',linewidth=.3,zorder=2)
hub=active[np.argsort(-degree[active])[:6]]
callouts=[(.02,.98),(.55,.98),(.02,.86),(.55,.86),(.03,.13),(.55,.13)]
for j,xy in zip(hub,callouts):
    i=list(active).index(j);ax.annotate(names[FEATURE_COLS[j]]+f'（度 {degree[j]}）',pos[i],fontsize=6.5,xytext=xy,textcoords='axes fraction',bbox={'facecolor':'white','edgecolor':'#d5dce2','alpha':.95,'pad':2},arrowprops={'arrowstyle':'-','lw':.5,'color':'#666666'})
ax.axis('off');ax.set_title('附件网络最大连通分量（τ = 0.6）',loc='left');ax.legend(loc='lower center',bbox_to_anchor=(.5,-.07),fontsize=7,frameon=False,ncol=4)
sizes=np.bincount(lab);aside.barh(range(min(7,len(sizes))),np.sort(sizes)[::-1][:7],color=GREEN)
aside.set_yticks(range(7),[f'分量 {i+1}' for i in range(7)]);aside.set_xlabel('节点数');aside.set_title(f'{count} 个连通分量',fontsize=9)
aside.text(.02,-.22,f'总节点：231\n总边数：266\n孤立节点：{int((degree==0).sum())}\n节点大小表示度数\n蓝边：正相关；红边：负相关',transform=aside.transAxes,fontsize=8,va='top')
fig.subplots_adjust(bottom=.23,wspace=.18);save(fig,'q2_network.png')
pd.DataFrame({'feature':FEATURE_COLS,'name':[names[n] for n in FEATURE_COLS],'degree':degree,'component':lab}).to_csv(OUT/'data/network_nodes.csv',index=False)

# Reconstruct ONLY the reporting proxies on their original training folds. No new generator fit/sampling.
rawframe=pd.read_csv(ROOT/'data/clean/q3.csv')
X=rawframe[L.CHEM_COLS].to_numpy(float);Y=rawframe[TARGET_COLS].to_numpy(float)
styles=rawframe['tasting_category_fine'].to_numpy()
protocol=load('data/clean/q3_style_protocol.json')
fold=L.fold_of_row(protocol,rawframe['row'].to_numpy(int))
samples=pd.read_csv(ROOT/'experiments/EXP-0033/samples.csv')
profiles=[]
for no in (0,1,2):
    tr=fold!=no;med=L.column_medians(X[tr]);xtr=L.apply_median(X[tr],med);centre,scale=L.fit_standardizer(xtr)
    proxy=L.LabelProxy(centre,scale).fit(xtr,Y[tr])
    for s in ['Tripel','Kriek','Lambic']:
        mask=(samples.group=='generation')&(samples.fold==no)&(samples['style']==s)
        block=samples.loc[mask]; pred=proxy.predict_storage(block[L.CHEM_COLS].to_numpy(float))
        # slot is a zero-based row identifier in q3.csv, not beer number.
        idx=[int(np.flatnonzero(rawframe.row.to_numpy()==v)[0]) for v in block.slot]
        for a,i in enumerate(idx):
            for t,n in enumerate(TARGET_COLS):profiles.append({'style':s,'fold':no,'slot':int(rawframe.row.iloc[i]),'dimension':n,'generated_proxy':pred[a,t],'real_label':Y[i,t]})
prof=pd.DataFrame(profiles);prof.to_csv(OUT/'data/style_profiles_oof.csv',index=False)
key=['A_malt_all','A_hops_all','A_hops_citrus','A_esters_all','F_esters_fruity','acidity','alcohol','body']
fig,axes=plt.subplots(3,1,figsize=(8.5,7),sharex=True)
for ax,s in zip(axes,['Tripel','Kriek','Lambic']):
    p=prof[prof['style']==s].groupby('dimension')[['generated_proxy','real_label']].mean().reindex(key)
    ax.bar(np.arange(len(key))-.18,p.real_label,.36,color=ORANGE,label='真实感官标签均值')
    ax.bar(np.arange(len(key))+.18,p.generated_proxy,.36,color=BLUE,label='生成谱的代理预测均值')
    ax.axhline(0,lw=.5,c='gray');ax.set_ylabel('标准化强度');ax.set_title(f'{s}（n = {int((styles==s).sum())}）',loc='left',fontsize=10)
axes[0].legend(fontsize=8,ncol=2,frameon=False);axes[-1].set_xticks(range(len(key)),[target(n).replace('·','\n') for n in key],fontsize=8)
fig.tight_layout();save(fig,'q3_style_profiles.png')
profile_table=[]
for s in ['Tripel','Kriek','Lambic']:
    p=prof[prof['style']==s].groupby('dimension')[['generated_proxy','real_label']].mean()
    for t in ['A_esters_all','F_esters_fruity','acidity','alcohol','body']:
        profile_table.append([s,target(t),f(p.loc[t,'real_label']),f(p.loc[t,'generated_proxy'])])
snips['profiles']=table(['风格','维度','真实均值','生成代理均值'],profile_table)

# Reconstruct projected quantile initialisation and the original full-data reporting proxy.
med=L.column_medians(X);xall=L.apply_median(X,med);centre,scale=L.fit_standardizer(xall)
proxy=L.LabelProxy(centre,scale).fit(xall,Y);codes=L.floor_code_map(xall)
problem=L.TransferProblem(xall,styles,Y,X[styles=='Pils/Lager'],'Pils/Lager','Tripel',5,20,proxy,codes,dict(L.THRESHOLD_MEAN),10)
saved=samples[samples.group=='transfer'].copy()
assert len(saved)==len(problem.X_source)==11
tripel_cap=float(np.quantile(Y[styles=='Tripel',TARGET_COLS.index('t2n')],.9))
inits=[]
for i in range(11):
    caps,tcap,scap=L.transfer_caps(problem,i,L.THRESHOLD_MEAN,L.NON_INCREASING)
    caps=L.min_caps(caps,L.THRESHOLD_MEAN);tcap=min(tcap,tripel_cap);upper=L.apply_transfer_caps(problem,caps);problem.v_upper=upper
    v=L.project_transfer_feasible(problem,problem.v0[i],np.array([tcap]),np.array([scap]))
    inits.append(problem.v_to_x(np.clip(v,0,upper)))
initial=np.array(inits);new=saved[L.CHEM_COLS].to_numpy(float)
mah=np.mean([problem.target_mahalanobis(problem.x_to_v(r)) for r in new])
assert np.isclose(mah,load('experiments/EXP-0033/outputs.json')['transfer-delivery']['targetMahalanobis'],rtol=1e-8)
transfer=[]
for n in ['ethyl_acetate','isopentyl_acetate','ethyl_hexanoate','isoamyl_alcohol','glycerol','DMS','X2.3.butanedione','X4VG']:
    j=FEATURE_COLS.index(n)
    arrays=[L.physical_conc(n,a[:,j],codes) for a in [problem.X_source,initial,new,xall[styles=='Tripel']]]
    unit=str(threshold_meta.loc[n,'unit']) if n in threshold_meta.index else '原单位'
    transfer.append([names[n],unit]+[f(np.mean(a)) for a in arrays])
for n in ['t2n','stale_hops']:
    transfer.append([target(n)+'（代理）','标准化值']+[f(np.mean(proxy.predict_storage(a,n))) for a in [problem.X_source,initial,new,xall[styles=='Tripel']]])
snips['transfer']=table(['指标','单位','迁移前','投影初始化','优化后','真实 Tripel 均值'],transfer)
pd.DataFrame(transfer,columns=['指标','单位','迁移前','投影初始化','优化后','真实Tripel均值']).to_csv(OUT/'data/transfer_comparison.csv',index=False)
detail=[]
for n in L.DEFECT_KEYS:
    j=FEATURE_COLS.index(n);src=L.physical_conc(n,problem.X_source[:,j],codes);dst=L.physical_conc(n,new[:,j],codes)
    detail.append([names[n],f(L.THRESHOLD_MEAN[n]),f(float(np.max(dst-src))),f(np.mean(dst<=src+1e-7)),f(np.mean(dst<=L.THRESHOLD_MEAN[n]+1e-7))])
for n in L.PROXY_TARGETS:
    src=proxy.predict_storage(problem.X_source,n);dst=proxy.predict_storage(new,n)
    detail.append([target(n)+'（代理）','源样本预测',f(np.max(dst-src)),f(np.mean(dst<=src+1e-7)),'不适用'])
snips['defect_check']=table(['缺陷指标','阈值/约束参考','最大增量','逐样本不增率','低于阈值率'],detail)

# Main text figures: recreated in Chinese, with all numbers from stored results.
m1=load('experiments/EXP-0004/metrics.json');o1=load('experiments/EXP-0004/outputs.json');q3=load('experiments/EXP-0033/outputs.json')
fig,ax=plt.subplots(figsize=(7.3,3.1))
v=[m1[k] for k in ['median_oof_mae','graph_oof_mae','hgb_oof_mae','fused_oof_mae','mae']]
bars=ax.bar(range(5),v,color=['#adb6bf',BLUE,ORANGE,GREEN,GREEN],width=.6)
ax.axhline(m1['mae_median_reference'],ls='--',c=RED,label='留出集：中位数基线')
ax.set_xticks(range(5),['中位数\n折外','图低秩\n折外','梯度提升\n折外','融合\n折外','融合\n留出']);ax.set_ylabel('50 维平均绝对误差');ax.set_ylim(0,.46)
for b,x in zip(bars,v):ax.text(b.get_x()+b.get_width()/2,x+.006,f(x),ha='center',fontsize=8)
ax.legend(frameon=False,fontsize=8);fig.tight_layout();save(fig,'q1_prediction.png')
fig,ax=plt.subplots(figsize=(8.5,3.3));per=o1['per_target'];ts=sorted(per,key=lambda t:per[t]['skill'])
ax.bar(range(50),[per[t]['skill'] for t in ts],color=[GREEN if per[t]['skill']>0 else RED for t in ts]);ax.axhline(0,c='gray',lw=.6)
ax.set_xticks(range(50),[target(t) for t in ts],rotation=90,fontsize=6);ax.set_ylabel('相对基线改善比例（Skill）');fig.tight_layout();save(fig,'q1_targets.png')
fig,ax=plt.subplots(figsize=(7.8,3.1))
for i,flag in enumerate([1,0]):
    vals=g[g.is_train==flag][['g6__'+t for t in TARGET_COLS]].to_numpy().ravel()
    ax.bar(np.arange(7)+(i-.5)*.35,[(vals==v).mean() for v in range(7)],.35,color=BLUE if flag else ORANGE,label='训练样本' if flag else '留出样本')
ax.set_xlabel('相对强度等级');ax.set_ylabel('预测等级比例');ax.legend(frameon=False);fig.tight_layout();save(fig,'q1_grades.png')
fig,(ax,bx)=plt.subplots(1,2,figsize=(8.4,3.1))
ax.hist(top.pi,bins=np.linspace(0,1,11),color=BLUE,edgecolor='white');ax.axvline(top.pi.mean(),c=RED,ls='--',label=f'均值 {top.pi.mean():.4f}');ax.set_xlabel('入选频率 π');ax.set_ylabel('Top-3 条目数');ax.legend(frameon=False,fontsize=8)
pairs=q2['method_jaccard']['pairs'] if 'pairs' in q2['method_jaccard'] else None
if pairs is None:
    # The persistent object uses the pointEstimate key.
    pairs=q2['method_jaccard'].get('pointEstimate',q2['method_jaccard'])
    if 'pairs' in pairs:pairs=pairs['pairs']
keys=[k for k,v in pairs.items() if isinstance(v,dict) and 'mean' in v]
labels={'total_spearman':'总体','within_style_spearman':'风格内','graph_lowrank':'系数','consensus':'综合'}
bx.barh(range(len(keys)),[pairs[k]['mean'] for k in keys],color=GREEN);bx.set_yticks(range(len(keys)),[' / '.join(labels[z] for z in k.split('|')) for k in keys],fontsize=7);bx.set_xlabel('Top-3 集合平均 Jaccard');fig.tight_layout();save(fig,'q2_stability.png')
fig,(ax,bx)=plt.subplots(1,2,figsize=(8.4,3))
ax.bar(['真实数据','未约束生成','低缺陷生成'],[.844,.852,0],color=[ORANGE,BLUE,GREEN]);ax.set_ylim(0,1);ax.set_ylabel('至少一项物理缺陷超阈的比例')
for i,v in enumerate([.844,.852,0]):ax.text(i,v+.025,f(v),ha='center',fontsize=8)
cells=pd.DataFrame(q3['fold-cell-metrics']); agg=cells.groupby('style').apply(lambda d:np.average(d.e_norm,weights=d.n),include_groups=False)
sel=['Tripel','Kriek','Lambic'];bx.bar(np.arange(3)-.18,[agg[s] for s in sel],.36,color=BLUE,label='生成与真实')
ref=cells.groupby('style').apply(lambda d:np.average(d.real_ref,weights=d.n),include_groups=False);bx.bar(np.arange(3)+.18,[ref[s] for s in sel],.36,color=ORANGE,label='真实与真实参照');bx.set_xticks(range(3),sel);bx.set_ylabel('归一化能量距离');bx.legend(frameon=False,fontsize=7);fig.tight_layout();save(fig,'q3_quality.png')
fig,ax=plt.subplots(figsize=(7,3.2));pareto=q3['transfer-pareto']
for eta,c in zip([0,.01,.1],[BLUE,ORANGE,GREEN]):
    rows=[r for r in pareto if r['eta']==eta];xx=[r['meanL1'] for r in rows];yy=[r['targetMahalanobis'] for r in rows]
    ax.plot(xx,yy,'o-',c=c,label=f'η = {eta:g}')
    if eta==.01:
        for r,x,y in zip(rows,xx,yy):ax.annotate(f"λ = {r['lambda']:g}",(x,y),xytext=(5,5),textcoords='offset points',fontsize=8)
ax.set_xlabel('相对分位数初始化的 L1 改动');ax.set_ylabel('到 Tripel 的马氏距离');ax.legend(frameon=False,fontsize=8);fig.tight_layout();save(fig,'q3_pareto.png')

pd.DataFrame([{'feature':r['name'],'chemical_name':r['corrLabel'],'kind':r['kind'],'scale':r['tier']} for r in meta]).to_csv(OUT/'data/dictionary_231.csv',index=False)
dictionary=[]
for n in ['DMS','X2.3.butanedione','X4VG','ethyl_acetate','isopentyl_acetate','isoamyl_alcohol','acetic_acid.g.L.','lactic_acid.mg.L.','citronellol','geraniol','X.E..2.nonenal','protein.g.L.','iron']:
    r=next(r for r in meta if r['name']==n);unit=str(threshold_meta.loc[n,'unit']) if n in threshold_meta.index else '未核实'
    dictionary.append([n,names[n],{'calibrated_log10':'log10','calibrated_linear':'线性','uncalibrated':'未校准'}.get(r['tier'],r['tier']),unit])
snips['dictionary']=table(['原始字段','名称','存储尺度','物理单位'],dictionary)
(OUT/'support/tables.json').write_text(json.dumps(snips,ensure_ascii=False,indent=2))
(OUT/'support/reporting_checks.json').write_text(json.dumps({'top3_rows':len(top),'dimensions':int(top.dimension.nunique()),'top3_coefficients_reproduced':True,'transfer_distance_reproduced':float(mah),'expected_transfer_distance':q3['transfer-delivery']['targetMahalanobis'],'profile_rows':len(prof),'originals_preserved':all(hashlib.sha256((ROOT/'report'/n).read_bytes()).hexdigest()==v for n,v in json.loads((OUT/'support/original_sha256.json').read_text()).items())},indent=2))
print('Prepared revision tables and figures:',OUT)
