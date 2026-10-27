"""Second-pass audit from source tables, plus a small exact-solver oracle.

No imports of project or previous audit code; no model training on contest data.
Usage: python independent_recheck.py --repo /path/to/repository --out /path/to/results
Requires numpy, pandas, openpyxl.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import re
import numpy as np
import pandas as pd
import openpyxl


def norm(value):
    return re.sub('[^a-z0-9]', '', str(value).replace('_x000D_', '').lower())


def constants(path):
    values = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return values


def crosscorr(a, b):
    a = a - a.mean(axis=0)
    b = b - b.mean(axis=0)
    den = np.outer(np.linalg.norm(a, axis=0), np.linalg.norm(b, axis=0))
    return a.T @ b / np.maximum(den, 1e-15)


def ranked(a):
    return pd.DataFrame(a).rank(method='average').to_numpy()


def distances(a, b):
    return np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)


def energy(a, b):
    n, m = len(a), len(b)
    aa, bb = distances(a, a).sum(), distances(b, b).sum()
    cross = 2 * distances(a, b).mean()
    return {'U_raw': float(cross - aa / (n * (n - 1)) - bb / (m * (m - 1))),
            'V_raw': float(cross - aa / n**2 - bb / m**2)}


def lowrank_oracle():
    """Two equivalent factorizations and an attained analytic lower bound, synthetic data only."""
    rng = np.random.default_rng(20261025)
    n, p, q, rank = 23, 8, 5, 2
    x = rng.normal(size=(n, p)) + np.arange(p)
    y = rng.normal(size=(n, q)) + np.arange(q)
    xc, yc = x - x.mean(0), y - y.mean(0)
    edges = rng.normal(size=(p, p)); edges = (edges + edges.T) / 2
    np.fill_diagonal(edges, 0)
    lap = np.diag(np.abs(edges).sum(1)) - edges
    lam, gamma = .7, .3
    a = xc.T @ xc / n + lam * np.eye(p) + gamma * lap
    c = xc.T @ yc / n
    full = np.linalg.solve(a, c)
    _, v = np.linalg.eigh(c.T @ full)
    vr = v[:, -rank:]
    beta = full @ vr @ vr.T
    chol = np.linalg.cholesky(a)
    m = np.linalg.solve(chol, c)
    u, s, vt = np.linalg.svd(m, full_matrices=False)
    mr = (u[:, :rank] * s[:rank]) @ vt[:rank]
    beta2 = np.linalg.solve(chol.T, mr)
    lower = float(np.sum(yc**2) / n - np.sum(s[:rank]**2))
    value = float(np.sum((yc - xc @ beta)**2) / n + lam * np.sum(beta**2)
                  + gamma * np.trace(beta.T @ lap @ beta))
    intercept = y.mean(0) - x.mean(0) @ beta
    full_rank_v = v @ v.T
    result = {'scope': 'synthetic 23x8 -> 5 outputs; rank 2, NOT contest performance',
              'objective': value, 'analytic_lower_bound': lower,
              'absolute_gap': abs(value-lower),
              'two_factorizations_max_difference': float(np.max(np.abs(beta-beta2))),
              'matrix_rank': int(np.linalg.matrix_rank(beta)),
              'mean_residual_max': float(np.max(np.abs((y-x@beta-intercept).mean(0)))),
              'full_rank_equals_graph_ridge_max_difference': float(np.max(np.abs(full@full_rank_v-full)))}
    assert result['absolute_gap'] < 1e-10
    assert result['two_factorizations_max_difference'] < 1e-10
    assert result['matrix_rank'] <= rank
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    r = root / 'v5'
    k = constants(r/'src/target_columns.py')
    features, targets = k['FEATURE_COLS'], k['TARGET_COLS']
    chem = ['chem__'+s for s in features]
    train = pd.read_csv(r/'data/splits/SPLIT-0001/train.csv')
    test = pd.read_csv(r/'data/splits/SPLIT-0001/test.csv')
    raw = pd.read_csv(r/'data/clean/q3.csv')
    saved = pd.read_csv(r/'experiments/EXP-0033/samples.csv')
    q1 = {}
    for exp in ['EXP-0001', 'EXP-0003', 'EXP-0004']:
        pred = pd.read_csv(r/f'experiments/{exp}/predictions.csv')
        yp = pred[['y_pred__'+s for s in targets]].to_numpy()
        yt = pred[['y_true__'+s for s in targets]].to_numpy()
        err = np.abs(yt-yp)
        af = [i for i,s in enumerate(targets) if s.startswith(('A_', 'F_'))]
        q1[exp] = {'MAE_50': float(err.mean()), 'MAE_AF30': float(err[:,af].mean()),
                    'macro_R2_50': float(np.mean(1-((yt-yp)**2).sum(0)/((yt-yt.mean(0))**2).sum(0)))}
    xtr = train[chem].fillna(train[chem].median()).to_numpy()
    xte = test[chem].fillna(train[chem].median()).to_numpy()
    centre, scale = xtr.mean(0), xtr.std(0)
    scale[scale < 1e-12] = 1
    q1['clipped_chemical_cells'] = {'train': int((np.abs((xtr-centre)/scale)>8).sum()),
                                     'test': int((np.abs((xte-centre)/scale)>8).sum())}
    # Use every sensory name in the original workbook, rather than assuming the first 47 positions.
    book = openpyxl.load_workbook(next((r/'data/raw/imported').glob('*-8.xlsx')),read_only=True,data_only=True)
    sensory = list(book['Sensory names'].values)
    sensory_lookup = {norm(row[6]): row[1] for row in sensory[1:] if row[0]=='Trained panel'}
    external = pd.read_csv(next((r/'data/raw/imported').glob('*-6.csv')))
    sensory_order = [sensory_lookup[norm(s)] for s in external.columns[1:]]
    assert len(set(sensory_order)) == 50 and set(sensory_order) == set(targets)
    meta = json.loads((r/'data/clean/q2_chem_meta.json').read_text())['features']
    chem_lookup = {norm(m['corrLabel']):m['name'] for m in meta}
    ext_chem = [chem_lookup[norm(s)] for s in external.iloc[:,0]]
    total = crosscorr(ranked(xtr), ranked(train[targets].to_numpy()))
    pos = [features.index(s) for s in ext_chem]
    candidates = k['COMPOUND_CANDIDATES']
    reduced = total[[features.index(s) for s in candidates]]
    def compare(a,b):
        return np.diag(crosscorr(ranked(np.abs(a)), ranked(np.abs(b))))
    extv = external.iloc[:,1:].to_numpy()
    wrong = compare(reduced[pos], extv)
    correct = compare(total[pos], extv[:,[sensory_order.index(s) for s in targets]])
    q2 = {'mean_bug_reproduced':float(wrong.mean()),'mean_all_names_aligned':float(correct.mean()),
          'row_mismatches':sum(candidates[p]!=s for p,s in zip(pos,ext_chem)),
          'column_mismatches':[{'column':s,'actual_target':t,'old_assumed':targets[i]}
                               for i,(s,t) in enumerate(zip(external.columns[1:],sensory_order)) if t!=targets[i]],
          'all_50_columns_mapped_by_workbook_names':True}
    pd.DataFrame({'external_header':external.columns[1:],'target':sensory_order}).to_csv(out/'sensory_name_alignment.csv',index=False)
    lin = ['chem__'+s for s in k['LINEAR_CALIBRATED']]
    gen = saved[saved.group=='generation']
    bad = gen[lin] < -1e-10
    tr = saved[saved.group=='transfer']
    source = raw.set_index('row').loc[tr.slot]
    t2n = 'chem__X.E..2.nonenal'
    delta = tr[t2n].to_numpy()-source[t2n].to_numpy()
    rows = []
    for i in gen.index:
        for name in lin:
            if bad.loc[i,name]:
                rows.append({'saved_row':int(gen.loc[i,'row']),'style':gen.loc[i,'style'],'column':name,'value':float(gen.loc[i,name])})
    pd.DataFrame(rows).to_csv(out/'negative_concentrations_rechecked.csv',index=False)
    pd.DataFrame({'source_row':tr.slot,'source_beer':source.beer.to_numpy(),'before':source[t2n].to_numpy(),'after':tr[t2n].to_numpy(),'delta':delta}).to_csv(out/'t2n_rechecked.csv',index=False)
    x = raw[chem].fillna(raw[chem].median()).to_numpy()
    mean, std = x.mean(0), x.std(0)
    std[std < 1e-12] = 1
    z = (x-mean)/std
    zt = z[raw.tasting_category_fine=='Tripel']
    mu = zt.mean(0)
    _,_,vt = np.linalg.svd(zt-mu,full_matrices=False)
    v = vt[:10]
    scores = (zt-mu)@v.T
    sm, ss = scores.mean(0), scores.std(0,ddof=1)
    ss[ss < 1e-12]=1
    cov = .9*np.corrcoef((scores-sm)/ss,rowvar=False)+.1*np.eye(10)
    inv = np.linalg.inv(cov)
    def mahal(z, corrected):
        s = ((z-mu if corrected else z)@v.T-sm)/ss
        return np.sqrt(np.maximum(np.einsum('...i,ij,...j->...',s,inv,s),0))
    zgen = (tr[chem].to_numpy()-mean)/std
    q3 = {'negative_linear_cells':int(bad.to_numpy().sum()),'negative_linear_rows':int(bad.any(axis=1).sum()),
          'negative_linear_fields':int(bad.any(axis=0).sum()),
          'original_negative_linear_cells':int((raw[lin]<-1e-10).to_numpy().sum()),
          't2n_increases':int((delta>1e-10).sum()),'t2n_max_increase':float(delta.max()),
          'target_mean_distance_old':float(mahal(mu,False)),'target_mean_distance_correct':float(mahal(mu,True)),
          'transfer_mean_distance_old':float(mahal(zgen,False).mean()),'transfer_mean_distance_corrected_fixed_spectra':float(mahal(zgen,True).mean()),
          'transfer_energy':energy(zgen,zt),
          'scope':'fixed saved spectra; centering changes evaluation only; no transfer optimization rerun'}
    # Negative unbiased energy is possible even for identical finite empirical samples.
    toy = np.array([[0.],[1.]])
    oracle = lowrank_oracle()
    result = {'scope':'independent source/CSV arithmetic and synthetic oracle; no trained contest model',
              'q1':q1,'q2':q2,'q3':q3,'energy_identical_two_point_toy':energy(toy,toy),
              'exact_graph_reduced_rank_oracle':oracle,
              'input_hashes':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [
                  r/'src/q1_lib.py',r/'src/q2_lib.py',r/'src/q3_lib.py',r/'src/q3_generate.py',
                  r/'experiments/EXP-0033/samples.csv',r/'data/clean/q3.csv']}}
    (out/'independent_recheck.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({s:result[s] for s in ['q1','q2','q3','energy_identical_two_point_toy','exact_graph_reduced_rank_oracle']},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
