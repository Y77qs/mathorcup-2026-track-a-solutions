#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ref_crosscheck.py — 8.xlsx 与 1/4/7.csv 行序/主键/类别一致性 + 2/5/6.csv 相关类型核验 + 7.csv 语义。
只读 data/raw/，输出 analysis/ref/crosscheck.json 与 crosscheck.csv。

复现：
  PY=/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
  cd work/my-new-contest && $PY analysis/scripts/ref_crosscheck.py
"""
import json
import os
import re

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, 'analysis', 'ref')
os.makedirs(OUT, exist_ok=True)


def norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def dump(name, obj):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


d1 = pd.read_csv(os.path.join(RAW, '1.csv'))
d2 = pd.read_csv(os.path.join(RAW, '2.csv'), index_col=0)
d4 = pd.read_csv(os.path.join(RAW, '4.csv'))
d5 = pd.read_csv(os.path.join(RAW, '5.csv'), index_col=0)
d6 = pd.read_csv(os.path.join(RAW, '6.csv'), index_col=0)
d7 = pd.read_csv(os.path.join(RAW, '7.csv'))
xl8 = pd.ExcelFile(os.path.join(RAW, '8.xlsx'))
cal = pd.read_excel(os.path.join(RAW, '8.xlsx'), sheet_name='Calibrated chemical dataset')
shp = pd.read_excel(os.path.join(RAW, '8.xlsx'), sheet_name='GBM SHAP Values')
mdi = pd.read_excel(os.path.join(RAW, '8.xlsx'), sheet_name='GBM importance MDI', header=None)
bp = pd.read_excel(os.path.join(RAW, '8.xlsx'), sheet_name='Beer Prices')
th = pd.read_excel(os.path.join(RAW, '8.xlsx'), sheet_name='Sensory thresholds')
nm = pd.read_excel(os.path.join(RAW, '8.xlsx'), sheet_name='Sensory names')
xl3 = pd.ExcelFile(os.path.join(RAW, '3.xlsx'))

chem1 = list(d1.columns[3:])
R = {}
R['shapes'] = {'1.csv': list(d1.shape), '2.csv': [d2.shape[0], d2.shape[1] + 1],
               '4.csv': list(d4.shape), '5.csv': [d5.shape[0], d5.shape[1] + 1],
               '6.csv': [d6.shape[0], d6.shape[1] + 1], '7.csv': list(d7.shape),
               '8.xlsx': {s: list(pd.read_excel(os.path.join(RAW, '8.xlsx'), sheet_name=s, header=None).shape)
                          for s in xl8.sheet_names},
               '3.xlsx': {'n_sheets': len(xl3.sheet_names), 'sheets': xl3.sheet_names,
                          'shapes': {s: list(pd.read_excel(os.path.join(RAW, '3.xlsx'), sheet_name=s, header=None).shape)
                                     for s in xl3.sheet_names}}}

# ---------------------------------------------------------------- A. 行对齐
def seq_eq(a, b):
    a = list(a)
    b = list(b)
    return len(a) == len(b) and all(
        (pd.isna(x) and pd.isna(y)) or x == y for x, y in zip(a, b))


def cmp_ids(a, b):
    """a/b 为同长度 beer_id 序列；返回精确一致数与舍入到 6 位有效数字后一致数。"""
    a = pd.Series(a).astype('float64')
    b = pd.Series(b).astype('float64')
    exact = int((a == b).sum())
    r6 = a.map(lambda x: float('%.6g' % x) if pd.notna(x) else np.nan)
    return {'n': int(len(a)), 'exact_equal': exact,
            'equal_after_6sig_round': int((r6 == b).sum()),
            'unique_a': int(a.nunique()), 'unique_b': int(b.nunique())}


align = {}
align['1_vs_4'] = {'beer_seq_equal': seq_eq(d1['beer'], d4['beer']),
                   'tasting_category_fine_equal': seq_eq(d1['tasting_category_fine'], d4['tasting_category_fine']),
                   'beer_id': cmp_ids(d1['beer_id'], d4['beer_id'])}
align['1_vs_7'] = {'beer_seq_equal': seq_eq(d1['beer'], d7['beer']),
                   'tasting_category_fine_equal': seq_eq(d1['tasting_category_fine'], d7['tasting_category_fine']),
                   'beer_id': cmp_ids(d1['beer_id'], d7['beer_id'])}
align['4_vs_7'] = {'beer_seq_equal': seq_eq(d4['beer'], d7['beer']),
                   'beer_id_equal': seq_eq(d4['beer_id'], d7['beer_id']),
                   'tasting_category_fine_equal': seq_eq(d4['tasting_category_fine'], d7['tasting_category_fine']),
                   'shared_columns': [c for c in d4.columns if c in set(d7.columns)]}
# 7.csv 186 个感官列与 4.csv 50 个感官列的重合
s4 = set(d4.columns[3:])
s7 = set(d7.columns[3:])
align['4_vs_7']['n_sensory_4'] = len(s4)
align['4_vs_7']['n_sensory_7'] = len(s7)
align['4_vs_7']['n_shared_sensory_names'] = len(s4 & s7)
# 4.csv beer_id 精度: 6 位有效数字舍入与原始一致率、碰撞
bid4 = d4['beer_id'].astype(float)
align['4_beer_id_precision'] = {
    'n_rows': int(len(bid4)), 'n_unique': int(bid4.nunique()),
    'n_rows_whose_6sig_round_equals_1csv': int((bid4.map(lambda x: float('%.6g' % x)) == d1['beer_id'].astype(float)).sum()),
    'max_rows_per_id': int(bid4.value_counts().max()),
    'raw_value_example': open(os.path.join(RAW, '4.csv'), encoding='utf-8').readlines()[1].split(',')[1],
}
# 8.xlsx cal / SHAP / BP 对齐
align['1_vs_cal'] = {'beer_seq_equal': seq_eq(d1['beer'], cal['beer']),
                     'tasting_category_fine_equal': seq_eq(d1['tasting_category_fine'], cal['tasting_category_fine']),
                     'beer_id': cmp_ids(d1['beer_id'], cal['beer_id'])}
sh_shap = shp[shp['data'] == 'SHAP'].reset_index(drop=True)
sh_conc = shp[shp['data'] == 'concentration'].reset_index(drop=True)
align['1_vs_shap_SHAPblock'] = {'beer_seq_equal': seq_eq(d1['beer'], sh_shap['beer']),
                                 'tasting_category_fine_equal': seq_eq(d1['tasting_category_fine'], sh_shap['tasting_category_fine']),
                                 'beer_id': cmp_ids(d1['beer_id'], sh_shap['beer_id'])}
align['1_vs_shap_concblock'] = {'beer_seq_equal': seq_eq(d1['beer'], sh_conc['beer']),
                                 'tasting_category_fine_equal': seq_eq(d1['tasting_category_fine'], sh_conc['tasting_category_fine']),
                                 'beer_id': cmp_ids(d1['beer_id'], sh_conc['beer_id'])}
# BP: 按 beer 索引合并后比较
m = d1[['beer', 'beer_id', 'tasting_category_fine']].merge(
    bp[['beer', 'beer_id', 'tasting_category', 'ABV']], on='beer', suffixes=('_1', '_bp'))
align['1_vs_BP'] = {'n_merged': int(len(m)),
                    'beer_id_equal': int((m['beer_id_1'] == m['beer_id_bp']).sum()),
                    'BP_beer_is_1_to_250': bool(seq_eq(sorted(bp['beer']), range(1, 251))),
                    'BP_sorted_by_beer': bool(bp['beer'].is_monotonic_increasing),
                    'category_1csv_sample': m['tasting_category_fine'].head(6).tolist(),
                    'category_BP_sample': m['tasting_category'].head(6).tolist(),
                    'ABV_describe': {'min': float(bp['ABV'].min()), 'median': float(bp['ABV'].median()),
                                     'max': float(bp['ABV'].max())}}
R['alignment'] = align

# ---------------------------------------------------------------- B. SHAP concentration 块取值来源
feat_cols = [c for c in shp.columns if c not in ('data', 'beer', 'beer_id', 'tasting_category_fine')]
feat_chem = [c for c in feat_cols if c != 'base_prediction']
conc = sh_conc.set_index('beer_id')
cal_i = cal.set_index('beer_id')
d1_i = d1.set_index('beer_id')
cross = {}
# concentration vs calibrated（70 个同名化合物）
common_cal = [c for c in feat_chem if c in set(cal.columns)]
eq_cal = 0
n_cal = 0
for c in common_cal:
    a = pd.to_numeric(conc[c], errors='coerce')
    b = pd.to_numeric(cal_i[c].reindex(a.index), errors='coerce')
    eq_cal += int(((a - b).abs() < 1e-9).sum())
    n_cal += int((a.notna() & b.notna()).sum())
# concentration vs 1.csv（231 个同名化合物）
common_1 = [c for c in feat_chem if c in set(d1.columns)]
eq_1 = 0
n_1 = 0
maxdiff_1 = 0.0
for c in common_1:
    a = pd.to_numeric(conc[c], errors='coerce')
    b = pd.to_numeric(d1_i[c].reindex(a.index), errors='coerce')
    eq_1 += int(((a - b).abs() < 1e-9).sum())
    n_1 += int((a.notna() & b.notna()).sum())
    maxdiff_1 = max(maxdiff_1, float((a - b).abs().max()))
cross['SHAP_concentration_vs_cal'] = {'n_common_cols': len(common_cal), 'n_cells': n_cal, 'n_cells_equal_1e-9': eq_cal}
cross['SHAP_concentration_vs_1csv'] = {'n_common_cols': len(common_1), 'n_cells': n_1,
                                        'n_cells_equal_1e-9': eq_1, 'max_abs_diff': maxdiff_1}
# SHAP 块加和 vs base_prediction（是否有 target/base 列语义）
sv = sh_shap[feat_chem].apply(pd.to_numeric, errors='coerce')
cross['SHAP_additivity'] = {'row_sum_min': float(sv.sum(axis=1).min()), 'row_sum_max': float(sv.sum(axis=1).max()),
                            'base_prediction_nunique': int(sh_shap['base_prediction'].nunique()),
                            'base_prediction_first': float(sh_shap['base_prediction'].iloc[0]),
                            'n_feature_chem_cols': len(feat_chem)}
# MDI 与 1.csv 对应
body = mdi.iloc[1:].copy()
body.columns = ['importance', 'feature']
cross['MDI_vs_1csv'] = {'n_features': int(len(body)),
                        'n_in_1csv': int(body['feature'].isin(chem1).sum()),
                        'not_in_1csv': [c for c in body['feature'] if c not in chem1],
                        'n_missing_from_mdi': int(len(set(chem1) - set(body['feature'])))}
# thresholds 与 1.csv 化合物名覆盖
n1norm = {norm(c): c for c in chem1}
th_norm = [norm(c) for c in th['field_name_python']]
def agg_norm(s):
    # 更激进的归一化：去前导 X、去标点；用于名称为 X2.3.hexanedione ↔ 2,3-hexanedione 的匹配
    x = norm(s)
    return x[1:] if x.startswith('x') and len(x) > 1 else x
n1agg = {agg_norm(c): c for c in chem1}
cross['thresholds_vs_1csv'] = {'n_rows': int(len(th)),
                               'n_exact_name': int(th['field_name_python'].isin(chem1).sum()),
                               'n_norm_name': int(sum(1 for x in th_norm if x in n1norm)),
                               'n_aggressive_norm_name': int(sum(1 for c in th['field_name_python'] if agg_norm(c) in n1agg)),
                               'n_with_threshold': int(pd.to_numeric(th['threshold_mean'], errors='coerce').notna().sum()),
                               'unmatched_examples': [c for c in th['field_name_python'] if norm(c) not in n1norm][:15]}
R['cross_8xlsx'] = cross

# ---------------------------------------------------------------- C. 2/5/6.csv 相关类型核验
def map2to1(names):
    """2.csv/6.csv 的化合物全名 → 1.csv 列名。优先 thresholds chemical_name 映射，再名称归一化。"""
    mp = {}
    for _, r in th.iterrows():
        if pd.notna(r['chemical_name']) and pd.notna(r['field_name_python']):
            mp[str(r['chemical_name']).strip().lower()] = str(r['field_name_python'])
    out = {}
    for nmx in names:
        k = str(nmx).strip().lower()
        if k in mp and mp[k] in chem1:
            out[nmx] = mp[k]
        elif norm(nmx) in n1norm:
            out[nmx] = n1norm[norm(nmx)]
    return out


def corr_type_test(df, feat_names, incol, matrix, ref_axis):
    """对若干特征对比较 Pearson/Spearman 与给定相关矩阵单元格的差。"""
    m = {k: v for k, v in df.items()}
    pairs = []
    for i in range(len(feat_names)):
        for j in range(i + 1, len(feat_names)):
            a, b = feat_names[i], feat_names[j]
            if a not in m or b not in m:
                continue
            x = pd.to_numeric(df[a], errors='coerce')
            y = pd.to_numeric(df[b], errors='coerce')
            ok = x.notna() & y.notna()
            if ok.sum() < 120:
                continue
            try:
                ref = float(matrix.loc[a, b]) if ref_axis == 'row' else float(matrix.loc[b, a])
            except Exception:
                continue
            pairs.append((x[ok].corr(y[ok]), x[ok].rank().corr(y[ok].rank()), ref, a, b))
    if not pairs:
        return None
    arr = np.array([[p[0], p[1], p[2]] for p in pairs], dtype=float)
    dP = np.abs(arr[:, 0] - arr[:, 2])
    dS = np.abs(arr[:, 1] - arr[:, 2])
    return {'n_pairs': int(len(pairs)),
            'median_abs_diff_if_Pearson': float(np.median(dP)),
            'median_abs_diff_if_Spearman': float(np.median(dS)),
            'max_abs_diff_if_Pearson': float(dP.max()),
            'max_abs_diff_if_Spearman': float(dS.max()),
            'n_pairs_Pearson_within_1e-6': int((dP < 1e-6).sum()),
            'n_pairs_Spearman_within_1e-6': int((dS < 1e-6).sum())}


# 2.csv（231 化合物 × 231）: 取映射成功率最高的 40 个化合物
map2 = map2to1(list(d2.index))
names2 = [k for k in map2 if map2[k] in set(chem1)][:40]
# 列名用 2.csv 全名（与 d2 索引一致），值取 1.csv 对应列
df2 = pd.DataFrame({k: pd.to_numeric(d1[map2[k]], errors='coerce') for k in names2})
R['corr_type_2csv'] = corr_type_test(df2, names2, 'row', d2, 'row')
R['corr_type_2csv']['n_mapped_compounds'] = len(map2)
R['corr_type_2csv']['n_compounds'] = len(d2.index)

# 5.csv（50 感官 × 50）: 5.csv 索引是 CleanName，通过 Sensory names 映射到 4.csv 列名
tr = nm[nm['dataset'] == 'Trained panel']
clean2r = {}
for _, rr in tr.iterrows():
    for col in ['CleanName_PanelFeedback', 'CleanName_Paper', 'CleanName_PaperLong']:
        if pd.notna(rr[col]):
            clean2r[str(rr[col]).replace('\r\n', ' ').replace('\n', ' ').strip()] = rr['R_name']
idx5 = [i for i in d5.index if i in clean2r]
df5 = pd.DataFrame({i: pd.to_numeric(d4[clean2r[i]], errors='coerce') for i in idx5})
# 列名用 5.csv CleanName（与 d5 索引一致）
R['corr_type_5csv'] = corr_type_test(df5, idx5, 'row', d5.loc[idx5, idx5], 'row')
R['corr_type_5csv']['n_mapped_dims'] = len(idx5)
R['corr_type_5csv']['n_dims'] = len(d5.index)

# 6.csv（44 化学 × 50 感官）: 6.csv 行=化合物全名(2.csv 风格)，列=感官 CleanName
map6 = map2to1(list(d6.index))
names6 = [k for k in map6 if map6[k] in set(chem1)][:30]
srows = [i for i in d6.columns if i in clean2r]
srows_r = [clean2r[i] for i in srows]
if names6 and srows_r:
    df6 = pd.DataFrame({map6[k]: pd.to_numeric(d1[map6[k]], errors='coerce') for k in names6})
    for c, cr in zip(srows, srows_r):
        df6[cr] = pd.to_numeric(d4[cr], errors='coerce')
    # 6.csv 需按行(化学)对列(感官)取单元格；构造对称式不方便，直接抽取样本对
    pairs = []
    for k in names6[:20]:
        for c, cr in zip(srows[:10], srows_r[:10]):
            x = pd.to_numeric(d1[map6[k]], errors='coerce')
            y = pd.to_numeric(d4[cr], errors='coerce')
            ok = x.notna() & y.notna()
            if ok.sum() < 120:
                continue
            ref = float(d6.loc[k, c])
            pairs.append((x[ok].corr(y[ok]), x[ok].rank().corr(y[ok].rank()), ref))
    if pairs:
        arr = np.array(pairs, dtype=float)
        dP = np.abs(arr[:, 0] - arr[:, 2])
        dS = np.abs(arr[:, 1] - arr[:, 2])
        R['corr_type_6csv'] = {'n_pairs': int(len(pairs)),
                               'median_abs_diff_if_Pearson': float(np.median(dP)),
                               'median_abs_diff_if_Spearman': float(np.median(dS)),
                               'n_pairs_Pearson_within_1e-6': int((dP < 1e-6).sum()),
                               'n_pairs_Spearman_within_1e-6': int((dS < 1e-6).sum())}
    R['corr_type_6csv_shape'] = {'n_rows': int(d6.shape[0]), 'n_cols': int(d6.shape[1]),
                                 'n_unique_row_names': int(d6.index.nunique()),
                                 'n_sensory_cols_matching_5csv': int(sum(1 for c in d6.columns if c in set(d5.columns)))}
# 6 列是否与 5 列完全同序
R['csv5_6_columns'] = {'same_columns_same_order': list(d5.columns) == list(d6.columns),
                       'n_cols_5': int(d5.shape[1]), 'n_cols_6': int(d6.shape[1])}

# ---------------------------------------------------------------- D. 7.csv 语义
num7 = d7.iloc[:, 3:].apply(pd.to_numeric, errors='coerce')
col_mean = num7.mean()
col_std = num7.std()
R['csv7'] = {
    'shape': list(d7.shape), 'n_meta_cols': 3, 'n_sensory_cols': int(d7.shape[1] - 3),
    'prefix_counts': {str(k): int(v) for k, v in
                      pd.Series([re.match(r'^([a-z]+_)', c).group(1) if re.match(r'^([a-z]+_)', c) else '(none)'
                                 for c in d7.columns[3:]]).value_counts().items()},
    'n_na_cells': int(d7.isna().sum().sum()),
    'na_cols': {str(k): int(v) for k, v in d7.isna().sum().items() if v > 0},
    'n_na_cols': int((d7.isna().sum() > 0).sum()),
    'numeric_range': [float(np.nanmin(num7.values)), float(np.nanmax(num7.values))],
    'frac_negative': float((num7.values < 0).mean()),
    'col_mean_describe': {'min': float(col_mean.min()), 'median': float(col_mean.median()), 'max': float(col_mean.max()),
                          'n_cols_abs_mean_lt_0.1': int((col_mean.abs() < 0.1).sum()), 'n_cols': int(len(col_mean))},
    'col_std_describe': {'min': float(col_std.min()), 'median': float(col_std.median()), 'max': float(col_std.max()),
                         'n_cols_std_lt_0.6': int((col_std < 0.6).sum())},
    'n_columns_matching_1csv_beer_order': int(seq_eq(d1['beer'], d7['beer'])),
}
# 7.csv 列名与 Sensory names Ratebeer 的 R_name 重合
rate_names = set(nm[nm['dataset'] == 'Ratebeer']['R_name'])
R['csv7']['n_cols_matching_sensorynames_ratebeer'] = int(sum(1 for c in d7.columns[3:] if c in rate_names))
R['csv7']['ratebeer_names_examples'] = sorted(rate_names)[:12]
R['csv7']['ratebeer_rows_not_in_7csv'] = [c for c in sorted(rate_names) if c not in set(d7.columns)]

# ---------------------------------------------------------------- E. 3.xlsx / 1.csv 计数
sm = pd.read_excel(os.path.join(RAW, '3.xlsx'), sheet_name='summary', header=None)
R['xlsx3'] = {'n_sheets': len(xl3.sheet_names), 'sheets': xl3.sheet_names,
              'summary_shape': list(sm.shape), 'summary_n_beers': int(sm.shape[0] - 1),
              'summary_columns': [None if pd.isna(x) else str(x) for x in sm.iloc[0].tolist()],
              'n_A_cols': int(sum(1 for x in sm.iloc[0] if isinstance(x, str) and x.startswith('A_'))),
              'n_F_cols': int(sum(1 for x in sm.iloc[0] if isinstance(x, str) and x.startswith('F_'))),
              'beer_sheet_shapes': {s: list(pd.read_excel(os.path.join(RAW, '3.xlsx'), sheet_name=s, header=None).shape)
                                    for s in xl3.sheet_names if s.startswith('beer_')}}
# 1.csv 列构成：5 个派生属性（kcalperc + 4 个 sum）
derived = ['kcalperc', 'esters_sum', 'aroma_hops_sum', 'acids_sum', 'sulfur_sum']
R['csv1'] = {'shape': list(d1.shape), 'n_features': len(chem1),
             'derived_cols_present': [c for c in derived if c in chem1],
             'n_derived': int(sum(1 for c in derived if c in chem1)),
             'n_measured_like': int(len(chem1) - sum(1 for c in derived if c in chem1))}
# 4/7/1 样本量
R['sample_counts'] = {'1.csv': len(d1), '4.csv': len(d4), '7.csv': len(d7),
                      '8.xlsx_Sensory_thresholds': len(th), '8.xlsx_Sensory_names': len(nm),
                      '8.xlsx_SHAP_per_block': int(len(sh_shap)),
                      '8.xlsx_calibrated': len(cal), '8.xlsx_BeerPrices': len(bp),
                      '3.xlsx_summary_beers': int(sm.shape[0] - 1)}
R['unique_values'] = {'4.csv beer_id': int(d4['beer_id'].nunique()),
                      '7.csv beer_id': int(d7['beer_id'].nunique()),
                      '1.csv beer_id': int(d1['beer_id'].nunique()),
                      '4.csv beer': int(d4['beer'].nunique())}


# ---------------------------------------------------------------- F. 3.xlsx 评分卡实际内容（是否含真实 0-6 评分）
beer_sheets = [s for s in xl3.sheet_names if s.startswith('beer_')]
score_scan = {}
for s in beer_sheets:
    df = pd.read_excel(os.path.join(RAW, '3.xlsx'), sheet_name=s, header=None)
    # 评分单元格列位：左面板 col16、右面板 col32（由 beer_1 布局核出）
    left = [v for v in df[16].tolist() if isinstance(v, (int, float, np.floating)) and pd.notna(v)]
    right = [v for v in df[32].tolist() if isinstance(v, (int, float, np.floating)) and pd.notna(v)]
    allnum = [float(v) for v in df.values.ravel() if isinstance(v, (int, float, np.floating)) and pd.notna(v)]
    score_scan[s] = {'shape': list(df.shape),
                     'score_cells_left_col16': left, 'score_cells_right_col32': right,
                     'n_numeric_cells': len(allnum),
                     'numeric_values_outside_0_to_6': sorted({v for v in allnum if v < 0 or v > 6}),
                     'n_nonzero_ratings': int(sum(1 for v in left + right if v != 0))}
# 3.xlsx 为公式驱动评分卡：统计各 sheet 公式数（data_only=False 读取）
import openpyxl
wb3 = openpyxl.load_workbook(os.path.join(RAW, '3.xlsx'), data_only=False)
formula_scan = {}
for ws in wb3.worksheets:
    fs = [(c.coordinate, str(c.value)) for row in ws.iter_rows() for c in row
          if isinstance(c.value, str) and c.value.startswith('=')]
    formula_scan[ws.title] = {'n_formulas': len(fs), 'examples': fs[:4]}
R['xlsx3']['formula_scan'] = formula_scan
R['xlsx3']['n_formulas_total'] = int(sum(v['n_formulas'] for v in formula_scan.values()))
smv = sm.iloc[1:, 1:-1].apply(pd.to_numeric, errors='coerce')
R['xlsx3']['scorecard_scan'] = score_scan
R['xlsx3']['summary_all_zero'] = bool((smv.values == 0).all())
R['xlsx3']['summary_n_cells'] = int(smv.size)
R['xlsx3']['summary_max_abs'] = float(np.nanmax(np.abs(smv.values)))
R['xlsx3']['is_blank_template'] = bool(all(v['n_nonzero_ratings'] == 0 for v in score_scan.values())
                                       and R['xlsx3']['summary_all_zero'])

# ---------------------------------------------------------------- G. SHAP 单目标识别：pred=base+sum(SHAP) 与 4/7.csv 感官列最大相关
pred = sh_shap[feat_chem].apply(pd.to_numeric, errors='coerce').sum(axis=1) + \
    pd.to_numeric(sh_shap['base_prediction'], errors='coerce')
best = []
for tag, df in [('4.csv', d4), ('7.csv', d7)]:
    for c in df.columns[3:]:
        y = pd.to_numeric(df[c], errors='coerce')
        best.append({'source': tag, 'col': str(c), 'pearson_r': float(y.corr(pred))})
best.sort(key=lambda x: -abs(x['pearson_r']))
R['shap_target_identify'] = {'pred_mean': float(pred.mean()), 'pred_range': [float(pred.min()), float(pred.max())],
                             'max_abs_corr_with_4csv_or_7csv': best[0], 'top5': best[:5],
                             'conclusion': 'SHAP 块为单目标模型的 SHAP（行内加和+常数 base_prediction），该目标与 4/7.csv 任一感官列最大 |r| 远小于 1，无法唯一对应到 50 个感官目标之一'}

# ---------------------------------------------------------------- H. 4.csv beer_id 精度丢失细节
bid = d4['beer_id'].astype(float)
vc = bid.value_counts()
R['alignment']['4_beer_id_precision'].update({
    'n_ids_shared_by_gt1_rows': int((vc > 1).sum()),
    'n_rows_in_collision_groups': int(vc[vc > 1].sum()),
    'max_rows_per_same_id': int(vc.max()),
    'example_same_id_rows': bid.value_counts().head(3).to_dict(),
    'interpretation': '4.csv/7.csv 的 beer_id 以 6 位有效数字科学计数法写出（如 5.41023E+12），250 行仅 96 个唯一值，无法作主键；行序与 beer 列（1–250 中的 Beer#）和 1.csv 完全一致，应按行位置/beer 列合并。',
})

dump('crosscheck.json', R)


# 摘要 csv
rows = []
for k, v in R['alignment'].items():
    if isinstance(v, dict):
        rows.append({'block': 'alignment', 'item': k,
                     'n_rows': v.get('n') or v.get('n_merged') or '',
                     'beer_seq_equal': v.get('beer_seq_equal', ''),
                     'beer_id_exact_equal': v.get('beer_id', {}).get('exact_equal', v.get('beer_id_equal', '')),
                     'beer_id_equal_after_6sig': v.get('beer_id', {}).get('equal_after_6sig_round', ''),
                     'cat_equal': v.get('tasting_category_fine_equal', '')})
for k in ['corr_type_2csv', 'corr_type_5csv', 'corr_type_6csv']:
    if k in R and R[k]:
        d = R[k]
        rows.append({'block': 'corr_type', 'item': k, 'n_rows': d.get('n_pairs', d.get('n_mapped_compounds', '')),
                     'beer_seq_equal': '', 'beer_id_exact_equal': '', 'beer_id_equal_after_6sig': '',
                     'cat_equal': 'median|P-m|=%.6f; median|S-m|=%.6f' % (
                         d['median_abs_diff_if_Pearson'], d['median_abs_diff_if_Spearman'])})
pd.DataFrame(rows).to_csv(os.path.join(OUT, 'crosscheck.csv'), index=False, encoding='utf-8-sig')

print('=== crosscheck summary ===')
print('alignment:', json.dumps(R['alignment'], ensure_ascii=False, default=str)[:1200])
print('corr 2csv:', R['corr_type_2csv'])
print('corr 5csv:', R['corr_type_5csv'])
print('corr 6csv:', R.get('corr_type_6csv'))
print('csv7:', {k: v for k, v in R['csv7'].items() if k in
                ['shape', 'n_sensory_cols', 'prefix_counts', 'n_na_cells', 'n_na_cols', 'numeric_range',
                 'frac_negative', 'col_std_describe', 'n_cols_matching_sensorynames_ratebeer']})
print('xlsx3:', {k: R['xlsx3'][k] for k in ['n_sheets', 'summary_n_beers', 'n_A_cols', 'n_F_cols']})
print('csv1:', R['csv1'])
print('samples:', R['sample_counts'])
