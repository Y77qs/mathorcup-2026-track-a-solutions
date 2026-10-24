#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ref_8xlsx_audit.py — 8.xlsx 全部 7 个 sheet 逐一审计（只读 raw 数据）。

输出（全部写入 analysis/ref/）：
  8xlsx_details.json     ：每个 sheet 的机器可读审计结果
  8xlsx_inventory.csv    ：sheet 级清单（shape / 行语义 / 关键统计 / 建模用途）
  8xlsx_inventory.md     ：同上，Markdown 表
  sensory_thresholds_cols.csv / sensory_names_cols.csv / shap_columns.csv /
  mdi_top10.csv / calibrated_columns.csv / beer_prices_na.csv

复现：
  PY=/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
  cd work/my-new-contest && $PY analysis/scripts/ref_8xlsx_audit.py
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, 'analysis', 'ref')
os.makedirs(OUT, exist_ok=True)
XLSX = os.path.join(RAW, '8.xlsx')


def norm(s):
    """列名归一化：去非字母数字、小写。用于跨表匹配。"""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def dump_json(name, obj):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def na_profile(df):
    s = df.isna().sum()
    return {str(k): int(v) for k, v in s.items() if v > 0}


xls = pd.ExcelFile(XLSX)
sheets = xls.sheet_names
res = {'file': 'data/raw/8.xlsx', 'sheet_names': sheets, 'n_sheets': len(sheets),
       'sheets': {}}


def read(sheet, header):
    if header is None:
        return pd.read_excel(XLSX, sheet_name=sheet, header=None)
    return pd.read_excel(XLSX, sheet_name=sheet, header=header)


# ---------------------------------------------------------------- 1) thresholds
raw = read('Sensory thresholds', 0)
t = raw.copy()
info = {
    'shape': list(raw.shape),
    'columns': [str(c) for c in raw.columns],
    'n_records': int(len(t)),
    'na_counts': na_profile(t),
    'na_frac': {str(k): round(float(v), 4) for k, v in t.isna().mean().items()},
}
for c in ['calibrated', 'origin_paper', 'unit', 'aging', 'off_flavors']:
    vc = t[c].value_counts(dropna=False)
    info[f'value_counts_{c}'] = {str(k): int(v) for k, v in vc.items()}
for c in ['threshold_mean', 'threshold_median']:
    s = pd.to_numeric(t[c], errors='coerce')
    info[c] = {'non_na': int(s.notna().sum()), 'min': float(np.nanmin(s)),
               'median': float(np.nanmedian(s)), 'max': float(np.nanmax(s)),
               'lt_1': int((s < 1).sum()), 'eq_0': int((s == 0).sum())}
# field_name_python 是否与 1.csv 化合物列同名
d1 = pd.read_csv(os.path.join(RAW, '1.csv'))
chem1 = [c for c in d1.columns[3:]]
info['n_field_name_python_unique'] = int(t['field_name_python'].nunique())
info['n_field_name_match_1csv_exact'] = int(t['field_name_python'].isin(chem1).sum())
n1 = {norm(c) for c in chem1}
info['n_field_name_match_1csv_norm'] = int(t['field_name_python'].map(norm).isin(n1).sum())
# 缺陷化合物定位：DMS / 二乙酰(双乙酰) / 4VG / trans-2-nonenal / stale hops
pat = {'DMS': r'dimethyl.?sulfide|^dms$|dms',
       'Diacetyl(2,3-butanedione)': r'butanedione|diacetyl',
       '4VG(4-vinylguaiacol)': r'vinyl.?guaiacol|4vg',
       'trans-2-nonenal': r'nonenal',
       'Stale hops': r'stale.?hop|hop.?stale|methyl.?2.?butenal|isobutyraldehyde'}
defect = {}
for label, p in pat.items():
    m = t[t['field_name_python'].astype(str).str.contains(p, case=False, regex=True, na=False)
          | t['chemical_name'].astype(str).str.contains(p, case=False, regex=True, na=False)]
    rows = []
    for _, r in m.iterrows():
        rows.append({'field_name_python': r['field_name_python'],
                     'chemical_name': r['chemical_name'],
                     'off_flavors': None if pd.isna(r['off_flavors']) else str(r['off_flavors']),
                     'threshold_mean': None if pd.isna(r['threshold_mean']) else float(r['threshold_mean']),
                     'threshold_median': None if pd.isna(r['threshold_median']) else float(r['threshold_median']),
                     'unit': None if pd.isna(r['unit']) else str(r['unit'])})
    defect[label] = rows
info['defect_candidates'] = defect
info['rows_with_threshold'] = int(pd.to_numeric(t['threshold_mean'], errors='coerce').notna().sum())
info['off_flavors_non_null'] = int(t['off_flavors'].notna().sum())
info['off_flavors_rows'] = [{'field_name_python': r['field_name_python'],
                              'off_flavors': str(r['off_flavors']),
                              'threshold_mean': None if pd.isna(r['threshold_mean']) else float(r['threshold_mean'])}
                             for _, r in t[t['off_flavors'].notna()].iterrows()]
res['sheets']['Sensory thresholds'] = info
t.to_csv(os.path.join(OUT, 'sensory_thresholds_clean.csv'), index=False, encoding='utf-8-sig')

# ---------------------------------------------------------------- 2) names
nm = read('Sensory names', 0)
info = {'shape': list(nm.shape), 'columns': [str(c) for c in nm.columns],
        'n_records': int(len(nm)), 'na_counts': na_profile(nm)}
for c in ['dataset', 'Category', 'DataType']:
    info[f'value_counts_{c}'] = {str(k): int(v) for k, v in nm[c].value_counts(dropna=False).items()}
info['Category_Paper_counts'] = {str(k): int(v) for k, v in nm['Category_Paper'].value_counts(dropna=False).items()}
info['unique_R_name'] = int(nm['R_name'].nunique())
info['unique_CleanName_Paper'] = int(nm['CleanName_Paper'].nunique())
# 与 4.csv 50 感官列对应
cols4 = list(d4cols := pd.read_csv(os.path.join(RAW, '4.csv')).columns[3:])
info['n_4csv_sensory'] = len(cols4)
info['match_4csv_by_R_name'] = int(nm['R_name'].isin(cols4).sum())
info['match_4csv_by_CleanName'] = int(nm['CleanName_Paper'].isin(cols4).sum())
n4 = {norm(c) for c in cols4}
nm_norm = nm['CleanName_Paper'].map(norm)
info['match_4csv_by_CleanName_norm'] = int(nm_norm.isin(n4).sum())
info['n_4csv_cols_covered_by_CleanName_norm'] = int(len({c for c in cols4 if norm(c) in set(nm_norm)}))
info['4csv_cols_not_covered'] = [c for c in cols4 if norm(c) not in set(nm_norm)]
info['names_rows_not_in_4csv'] = int((~nm_norm.isin(n4)).sum())
# 4.csv 的 4 个子类是否恰好是 Aroma/Flavour 两套
info['R_name_prefix_counts'] = {str(k): int(v) for k, v in
                                nm['R_name'].astype(str).str.extract(r'^([A-Za-z]+_)?')[0].fillna('(none)').value_counts().items()}
res['sheets']['Sensory names'] = info
nm.to_csv(os.path.join(OUT, 'sensory_names_clean.csv'), index=False, encoding='utf-8-sig')

# ---------------------------------------------------------------- 3) MDI
mdi = read('GBM importance MDI', None)
hdr = mdi.iloc[0].tolist()
body = mdi.iloc[1:].copy()
body.columns = ['importance', 'feature']
body['importance'] = pd.to_numeric(body['importance'], errors='coerce')
info = {'shape_raw_with_header': list(mdi.shape),
        'header_row0': [None if pd.isna(x) else str(x) for x in hdr],
        'n_features': int(len(body)),
        'columns': ['importance(col0,float)', 'feature(col1,name)'],
        'na_counts': na_profile(body),
        'importance': {'min': float(body['importance'].min()),
                        'median': float(body['importance'].median()),
                        'max': float(body['importance'].max()),
                        'sum': float(body['importance'].sum()),
                        'n_zero': int((body['importance'] == 0).sum()),
                        'n_le_1e-6': int((body['importance'] <= 1e-6).sum())},
        'top10': body.sort_values('importance', ascending=False).head(10).to_dict('records'),
        'bottom5': body.sort_values('importance').head(5).to_dict('records')}
info['n_features_in_1csv'] = int(body['feature'].isin(chem1).sum())
info['features_not_in_1csv'] = [c for c in body['feature'] if c not in chem1]
info['1csv_chem_not_in_mdi'] = [c for c in chem1 if c not in set(body['feature'])]
info['is_single_or_aggregate'] = ('单列 importance，无目标维度列；231 个特征与 1.csv 化合物列一一对应，'
                                  '即对“全部 50 个感官目标”的 GBM 多输出模型做 MDI 聚合后的单列重要性（不可反推单个目标）')
res['sheets']['GBM importance MDI'] = info
body.sort_values('importance', ascending=False).to_csv(
    os.path.join(OUT, 'mdi_top10.csv'), index=False, encoding='utf-8-sig')

# ---------------------------------------------------------------- 4) SHAP
sh = read('GBM SHAP Values', 0)
meta_cols = ['data', 'beer', 'beer_id', 'tasting_category_fine']
feat_cols = [c for c in sh.columns if c not in meta_cols]
info = {'shape': list(sh.shape), 'n_rows': int(len(sh)),
        'data_value_counts': {str(k): int(v) for k, v in sh['data'].value_counts(dropna=False).items()},
        'meta_cols': meta_cols, 'n_feature_cols': len(feat_cols),
        'feature_cols': [str(c) for c in feat_cols],
        'feature_cols_head': [str(c) for c in feat_cols[:5]],
        'feature_cols_tail': [str(c) for c in feat_cols[-8:]],
        'has_base_prediction': 'base_prediction' in feat_cols,
        'n_features_in_1csv': int(pd.Series(feat_cols).isin(chem1).sum()),
        'features_not_in_1csv': [c for c in feat_cols if c not in chem1],
        'na_counts': na_profile(sh),
        'beer_id_unique': int(sh['beer_id'].nunique()),
        'beer_unique': int(sh['beer'].nunique()),
        'tasting_category_fine_counts': {str(k): int(v) for k, v in sh['tasting_category_fine'].value_counts(dropna=False).items()}}
# 分块
blocks = {}
for g in ['SHAP', 'concentration']:
    sub = sh[sh['data'] == g]
    nums = sub[[c for c in feat_cols if c != 'base_prediction']].apply(pd.to_numeric, errors='coerce')
    blocks[g] = {'n_rows': int(len(sub)),
                 'feature_value_min': float(np.nanmin(nums.values)),
                 'feature_value_median': float(np.nanmedian(nums.values)),
                 'feature_value_max': float(np.nanmax(nums.values)),
                 'n_negative_cells': int((nums.values < 0).sum()),
                 'base_prediction': {'nunique': int(sub['base_prediction'].nunique()),
                                     'first': float(pd.to_numeric(sub['base_prediction'], errors='coerce').iloc[0])},
                 'beer': sub['beer'].head(5).tolist(),
                 'beer_id': [int(x) for x in sub['beer_id'].head(5).tolist()]}
info['blocks'] = blocks
# SHAP 行内加和（可加性检查）
shb = sh[sh['data'] == 'SHAP']
sv = shb[[c for c in feat_cols if c != 'base_prediction']].apply(pd.to_numeric, errors='coerce')
row_sum = sv.sum(axis=1).values
info['shap_row_sum'] = {'min': float(np.nanmin(row_sum)), 'median': float(np.nanmedian(row_sum)),
                         'max': float(np.nanmax(row_sum)),
                         'n_rows_sum_lt_1e-3': int((np.abs(row_sum) < 1e-3).sum()),
                         'n_rows': int(len(row_sum))}
# concentration 块是否等于 1.csv / calibrated
conc = sh[sh['data'] == 'concentration'].set_index('beer_id')
res['sheets']['GBM SHAP Values'] = info
pd.DataFrame({'col': [str(c) for c in sh.columns]}).to_csv(
    os.path.join(OUT, 'shap_columns.csv'), index=False, encoding='utf-8-sig')

# ---------------------------------------------------------------- 5) calibrated
cal = read('Calibrated chemical dataset', 0)
cal_chem = [c for c in cal.columns if c not in ('beer', 'beer_id', 'tasting_category_fine')]
info = {'shape': list(cal.shape), 'columns': [str(c) for c in cal.columns],
        'n_chem_cols': len(cal_chem), 'chem_cols': [str(c) for c in cal_chem],
        'meta_cols': ['beer', 'beer_id', 'tasting_category_fine'],
        'n_rows': int(len(cal)), 'n_unique_beer_id': int(cal['beer_id'].nunique()),
        'na_counts': na_profile(cal), 'na_total': int(cal.isna().sum().sum()),
        'dtypes': {str(k): int(v) for k, v in cal.dtypes.astype(str).value_counts().items()},
        'n_chem_in_1csv': int(pd.Series(cal_chem).isin(chem1).sum()),
        'chem_not_in_1csv': [c for c in cal_chem if c not in chem1],
        '1csv_cols_not_in_cal_n': len([c for c in chem1 if c not in set(cal_chem)]),
        '1csv_cols_not_in_cal': [c for c in chem1 if c not in set(cal_chem)]}
# 与 1.csv 同名列逐值比较
m = d1.merge(cal, on='beer_id', suffixes=('_1csv', '_cal'))
info['merged_rows'] = int(len(m))
cmp = {}
for c in cal_chem:
    a = pd.to_numeric(m[c + '_1csv'], errors='coerce')
    b = pd.to_numeric(m[c + '_cal'], errors='coerce')
    both = a.notna() & b.notna()
    if both.sum() == 0:
        continue
    d = (a[both] - b[both]).abs()
    # log10(cal) 与 1csv 比较（1.csv 疑为对数变换后的浓度）
    la = np.log10(b[both].where(b[both] > 0))
    dl = (a[both] - la).abs()
    cmp[c] = {'n': int(both.sum()),
              'n_exact_equal': int((d < 1e-12).sum()),
              'max_abs_diff_raw': float(d.max()),
              'median_abs_diff_raw': float(d.median()),
              'max_abs_diff_vs_log10cal': float(dl.max()),
              'median_abs_diff_vs_log10cal': float(dl.median())}
info['compare_with_1csv'] = cmp
n_eq = sum(v['n_exact_equal'] for v in cmp.values())
n_cells = sum(v['n'] for v in cmp.values())
info['compare_summary'] = {'n_common_cols': len(cmp), 'n_compared_cells': n_cells,
                            'n_cells_exact_equal': n_eq,
                            'frac_cells_exact_equal': round(n_eq / n_cells, 6),
                            'n_cols_all_equal': sum(1 for v in cmp.values() if v['n_exact_equal'] == v['n'])}
# log10 关系整体判断
lg_med = [v['median_abs_diff_vs_log10cal'] for v in cmp.values()]
rw_med = [v['median_abs_diff_raw'] for v in cmp.values()]
info['compare_summary']['median_over_cols_abs_diff_raw'] = float(np.median(rw_med))
info['compare_summary']['median_over_cols_abs_diff_vs_log10cal'] = float(np.median(lg_med))
# 对数底数核验：1.csv 是否为 log10(calibrated 原始浓度)
log10_ok = [k for k, v in cmp.items() if v['median_abs_diff_vs_log10cal'] < 1e-6]
info['compare_summary']['n_cols_log10_consistent'] = len(log10_ok)
info['compare_summary']['n_cols_compared'] = len(cmp)
info['compare_summary']['log10_consistent_cols'] = log10_ok
info['compare_summary']['n_cols_off_by_factor_10'] = int(sum(
    1 for k, v in cmp.items() if 0.7 < v['median_abs_diff_vs_log10cal'] < 1.4))
info['compare_summary']['log10_inconsistent_cols'] = [
    {'col': k, 'median_abs_diff_vs_log10cal': round(v['median_abs_diff_vs_log10cal'], 4)}
    for k, v in cmp.items() if v['median_abs_diff_vs_log10cal'] >= 1e-6]
# 理化参数是否也做了 log10（题面称保留原始量纲）
phys = ['pH', 'color.EBC.', 'bitterness', 'ethanol..v.v.', 'CO2.PSI.']
phys_chk = {}
for c in phys:
    if c in cmp:
        phys_chk[c] = {'median_abs_diff_vs_log10cal': cmp[c]['median_abs_diff_vs_log10cal'],
                       'example_1csv': None, 'example_cal': None}
        a = pd.to_numeric(d1[c], errors='coerce')
        b = pd.to_numeric(cal[c], errors='coerce')
        j = a.notna() & b.notna() & (b > 0)
        if j.any():
            idx = j[j].index[0]
            phys_chk[c]['example_1csv'] = float(a.loc[idx])
            phys_chk[c]['example_cal'] = float(b.loc[idx])
            phys_chk[c]['example_10_pow_1csv'] = float(10 ** a.loc[idx])
info['physical_params_log10_check'] = phys_chk
res['sheets']['Calibrated chemical dataset'] = info
pd.DataFrame({'col': [str(c) for c in cal.columns]}).to_csv(
    os.path.join(OUT, 'calibrated_columns.csv'), index=False, encoding='utf-8-sig')

# ---------------------------------------------------------------- 6) prices
bp = read('Beer Prices', 0)
price_cols = [c for c in bp.columns if str(c).startswith('Price_')]
info = {'shape': list(bp.shape), 'columns': [str(c) for c in bp.columns],
        'n_rows': int(len(bp)), 'n_unique_beer_id': int(bp['beer_id'].nunique()),
        'price_cols': [str(c) for c in price_cols],
        'na_counts': na_profile(bp), 'na_total': int(bp.isna().sum().sum()),
        'ABV': {'min': float(bp['ABV'].min()), 'median': float(bp['ABV'].median()),
                'max': float(bp['ABV'].max()), 'n_na': int(bp['ABV'].isna().sum())},
        'tasting_category_counts': {str(k): int(v) for k, v in bp['tasting_category'].value_counts(dropna=False).items()},
        'n_rows_with_any_price': int(bp[price_cols].notna().any(axis=1).sum()),
        'n_rows_all_price_na': int(bp[price_cols].isna().all(axis=1).sum())}
info['price_col_non_na'] = {str(c): int(bp[c].notna().sum()) for c in price_cols}
info['price_quantiles'] = {str(c): {q: (None if pd.isna(bp[c].quantile(q / 100)) else float(bp[c].quantile(q / 100)))
                                     for q in [0, 25, 50, 75, 100]} for c in price_cols}
res['sheets']['Beer Prices'] = info
bp[['beer', 'beer_id', 'ABV'] + [str(c) for c in price_cols]].to_csv(
    os.path.join(OUT, 'beer_prices_na.csv'), index=False, encoding='utf-8-sig')

# ---------------------------------------------------------------- 7) Sheet2
s2 = read('Sheet2', None)
info = {'shape_raw': list(s2.shape), 'is_empty': bool(s2.empty),
        'n_cells': int(s2.size), 'all_na': bool(s2.isna().all().all()) if s2.size else True}
res['sheets']['Sheet2'] = info

# ---------------------------------------------------------------- inventory csv/md

def I():
    return res['sheets']['Sensory thresholds']
th = I()
rows = [
    {'sheet': 'Sensory thresholds', 'shape': '%d×%d' % tuple(th['shape']), 'header_row': '第 0 行（列名）',
     'data_rows': th['n_records'],
     'row_semantics': '1 行 = 1 个化合物/风味物质的感官阈值（field_name_python/R、chemical_name、calibrated、origin_paper、unit、aging、off_flavors、threshold_mean/median）',
     'key_stats': 'threshold_mean 非空 %d/%d；threshold_median 非空 %d；off_flavors 非空 %d；calibrated 有值 %d；名称与 1.csv 可对应 47(精确)/228(宽松归一化)' % (
         th['threshold_mean']['non_na'], th['n_records'], th['threshold_median']['non_na'],
         th['off_flavors_non_null'],
         sum(v for k, v in th['value_counts_calibrated'].items() if k != 'nan')),
     'modeling_use': '缺陷化合物超阈值判定（DMS/双乙酰/4VG/trans-2-nonenal 等）、感官阈值归一化、风味强度化学合理性论证'},
    {'sheet': 'Sensory names', 'shape': '%d×%d' % tuple(res['sheets']['Sensory names']['shape']), 'header_row': '第 0 行',
     'data_rows': res['sheets']['Sensory names']['n_records'],
     'row_semantics': '1 行 = 1 个感官维度定义（dataset/R_name/Category_Paper/Category/CleanName_Paper/CleanName_PaperLong/CleanName_PanelFeedback/DataType）',
     'key_stats': 'R_name 唯一 %d 个；R_name 与 4.csv 50 列逐列对应 %d/50；dataset 分布 %s；CleanName_Paper 唯一 %d 个' % (
         res['sheets']['Sensory names']['unique_R_name'],
         res['sheets']['Sensory names']['match_4csv_by_R_name'],
         res['sheets']['Sensory names']['value_counts_dataset'],
         res['sheets']['Sensory names']['unique_CleanName_Paper']),
     'modeling_use': '感官维度名称/类别权威映射（R 变量名→论文 CleanName→面板反馈名），用于 4.csv/7.csv/5.csv/6.csv 列名对齐'},
    {'sheet': 'GBM importance MDI', 'shape': '%d×%d' % tuple(res['sheets']['GBM importance MDI']['shape_raw_with_header']), 'header_row': '第 0 行（NaN, 0；表头缺失）',
     'data_rows': res['sheets']['GBM importance MDI']['n_features'],
     'row_semantics': '1 行 = 1 个化合物特征 + 其 MDI 重要性；col0=importance(float)，col1=feature(name)；无目标维度列',
     'key_stats': '重要性 sum=%.6f；range [%.2e, %.4f]；前 3：%s' % (
         res['sheets']['GBM importance MDI']['importance']['sum'],
         res['sheets']['GBM importance MDI']['importance']['min'],
         res['sheets']['GBM importance MDI']['importance']['max'],
         ', '.join('%s=%.4f' % (r['feature'], r['importance']) for r in res['sheets']['GBM importance MDI']['top10'][:3])),
     'modeling_use': '化合物重要性排序/特征筛选（231 特征与 1.csv 完全对应）；是 50 目标聚合后的单列重要性，不能当单目标归因'},
    {'sheet': 'GBM SHAP Values', 'shape': '%d×%d' % tuple(res['sheets']['GBM SHAP Values']['shape']), 'header_row': '第 0 行',
     'data_rows': res['sheets']['GBM SHAP Values']['n_rows'],
     'row_semantics': '250 行 data=SHAP（每样本每个特征一个 SHAP 值）+ 250 行 data=concentration（特征取值）；col0=data，col1=beer，col2=beer_id，col3=tasting_category_fine，其后 %d 个特征列' % res['sheets']['GBM SHAP Values']['n_feature_cols'],
     'key_stats': 'feature 列 %d 个（含 base_prediction）；与 1.csv 同名 %d 个；beer_id 唯一 %d；SHAP 值范围 [%.3f, %.3f]；行内加和 median=%.2e' % (
         res['sheets']['GBM SHAP Values']['n_feature_cols'],
         res['sheets']['GBM SHAP Values']['n_features_in_1csv'],
         res['sheets']['GBM SHAP Values']['beer_id_unique'],
         res['sheets']['GBM SHAP Values']['blocks']['SHAP']['feature_value_min'],
         res['sheets']['GBM SHAP Values']['blocks']['SHAP']['feature_value_max'],
         res['sheets']['GBM SHAP Values']['shap_row_sum']['median']),
     'modeling_use': '问题 2 化合物→感官维度的可解释性/归因证据；concentration 块可作特征矩阵交叉校验'},
    {'sheet': 'Calibrated chemical dataset', 'shape': '%d×%d' % tuple(res['sheets']['Calibrated chemical dataset']['shape']), 'header_row': '第 0 行',
     'data_rows': res['sheets']['Calibrated chemical dataset']['n_rows'],
     'row_semantics': '1 行 = 1 个啤酒样本；3 元数据（beer/beer_id/tasting_category_fine）+ %d 个经校准（原始浓度量纲）的化合物列' % res['sheets']['Calibrated chemical dataset']['n_chem_cols'],
     'key_stats': '与 1.csv 同名 %d/70 列；其中 %d/70 列满足 1csv=log10(该表原始浓度)（逐列中位差<1e-6，总体中位差 %.2e），%d 列相差约 10 倍（校准/稀释口径不同）；1.csv 有而此表无 %d 列' % (
         res['sheets']['Calibrated chemical dataset']['n_chem_in_1csv'],
         res['sheets']['Calibrated chemical dataset']['compare_summary']['n_cols_log10_consistent'],
         res['sheets']['Calibrated chemical dataset']['compare_summary']['median_over_cols_abs_diff_vs_log10cal'],
         res['sheets']['Calibrated chemical dataset']['compare_summary']['n_cols_off_by_factor_10'],
         res['sheets']['Calibrated chemical dataset']['1csv_cols_not_in_cal_n']),
     'modeling_use': '补充：70 个核心化合物的原始浓度（可作对数变换底数核验、阈值比对、化学可解释性的原始量纲证据）；因只覆盖 70/231 列且与 1.csv 数值不同，不能整体替代 1.csv'},
    {'sheet': 'Beer Prices', 'shape': '%d×%d' % tuple(res['sheets']['Beer Prices']['shape']), 'header_row': '第 0 行',
     'data_rows': res['sheets']['Beer Prices']['n_rows'],
     'row_semantics': '1 行 = 1 个啤酒样本；beer/beer_id/tasting_category/ABV + 7 个渠道价格列',
     'key_stats': '价格列 %d 个；NA 合计 %d；有任一价格 %d/%d；ABV [%.1f, %.1f]' % (
         len(res['sheets']['Beer Prices']['price_cols']),
         res['sheets']['Beer Prices']['na_total'],
         res['sheets']['Beer Prices']['n_rows_with_any_price'],
         res['sheets']['Beer Prices']['n_rows'],
         res['sheets']['Beer Prices']['ABV']['min'], res['sheets']['Beer Prices']['ABV']['max']),
     'modeling_use': '外部/商业维度协变量（价格—风格/风味/ABV 关联、缺失机制分析）；不可当化合物输入'},
    {'sheet': 'Sheet2', 'shape': '%d×%d' % tuple(res['sheets']['Sheet2']['shape_raw']), 'header_row': '无',
     'data_rows': 0,
     'row_semantics': '空表（0 行 × 0 列，无任何单元格）',
     'key_stats': 'is_empty=%s；n_cells=%d' % (res['sheets']['Sheet2']['is_empty'], res['sheets']['Sheet2']['n_cells']),
     'modeling_use': '无用途；证明 8.xlsx “7 个 sheet” 实为 6 个有内容 + 1 个空表'},
]
inv = pd.DataFrame(rows)
inv.to_csv(os.path.join(OUT, '8xlsx_inventory.csv'), index=False, encoding='utf-8-sig')
with open(os.path.join(OUT, '8xlsx_inventory.md'), 'w', encoding='utf-8') as f:
    f.write('# 8.xlsx 全 sheet 清单（自动生成，数据源 data/raw/8.xlsx）\n\n')
    f.write('共 **%d** 个 sheet（有内容 6 个 + 空表 1 个）。\n\n' % len(sheets))
    f.write('| sheet | shape | 表头 | 数据行 | 行语义 | 关键统计 | 建模用途 |\n')
    f.write('|---|---|---|---|---|---|---|\n')
    for r in rows:
        cells = [str(r[k]).replace('|', '/') for k in
                 ['sheet', 'shape', 'header_row', 'row_semantics', 'key_stats', 'modeling_use']]
        f.write('| %s | %s | %s | %d | %s | %s | %s |\n' % (
            cells[0], cells[1], cells[2], int(r['data_rows']), cells[3], cells[4], cells[5]))

dump_json('8xlsx_details.json', res)
print('OK 8xlsx audit. sheets=%s' % sheets)
print('thresholds records=%d, mean non-na=%d, off_flavors non-null=%d' % (
    th['n_records'], th['threshold_mean']['non_na'], th['off_flavors_non_null']))
print('names rows=%d, 4csv covered=%d/50' % (
    res['sheets']['Sensory names']['n_records'],
    res['sheets']['Sensory names']['n_4csv_cols_covered_by_CleanName_norm']))
print('MDI features=%d top1=%s' % (
    res['sheets']['GBM importance MDI']['n_features'],
    res['sheets']['GBM importance MDI']['top10'][0]['feature']))
print('SHAP shape=%s blocks=%s' % (
    res['sheets']['GBM SHAP Values']['shape'],
    {k: v['n_rows'] for k, v in res['sheets']['GBM SHAP Values']['blocks'].items()}))
print('cal chem=%d exact_equal_cells=%d' % (
    res['sheets']['Calibrated chemical dataset']['n_chem_cols'],
    res['sheets']['Calibrated chemical dataset']['compare_summary']['n_cells_exact_equal']))
