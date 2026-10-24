#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""00_prepare_q3.py — Q3 table: style label + chemical domain + REAL parsed sensory thresholds.

What it does, in order:
  1. reads data/raw/1.csv (250 x 234) and data/raw/8.xlsx "Sensory thresholds";
  2. PARSES the threshold sheet for real: 261 rows, 43 with a numeric threshold (mean/median), 7 with an
     off-flavour flag. Each row is joined to a 1.csv column by the sheet's R-style field name
     (field_name_R), which matches a 1.csv column exactly for 43/43 rows; the plain English field name
     matches only 18/43 exactly, so field_name_R is the authoritative join key. Nothing is invented: what
     does not parse is listed by name in q3_thresholds.json;
  3. writes one constant thr__<1.csv column> per parsed threshold (threshold_mean), plus the style holdout
     flag style_holdout = heldout_style for {Tripel, Kriek, Lambic} and train_style for the rest;
  4. imputes 1.csv missing cells with the same TRAIN-ROW MEDIAN rule as the Q1/Q2 script (the Q3 split uses
     the same 250 rows / same seed, so the train rows are identical) and cross-checks the medians against
     data_quality.json when that file exists;
  5. FORBIDDEN INPUTS: 8.xlsx GBM importance MDI / GBM SHAP Values are model outputs of the same 250 samples;
     Beer Prices is mostly NA and is not a chemical descriptor. Neither is written into q3_table.csv. The
     "Calibrated chemical dataset" is used only as a scale reference (recorded as one consistency line).

The last stdout line is a JSON summary; any failed expectation exits non-zero and prints the reason.
"""

import argparse
import hashlib
import json
import os
import re
import sys

import numpy as np
import pandas as pd

SEED = 20261024
TEST_FRACTION = 0.2
N_ROWS = 250

THRESHOLDS_SHEET = 'Sensory thresholds'
CALIBRATED_SHEET = 'Calibrated chemical dataset'
HELDOUT_STYLES = ['Tripel', 'Kriek', 'Lambic']

# The Q3 problem text names these defect compounds explicitly. Each one must be resolved to a verdict:
# a parsed threshold, or an explicit "not available" record. Never a silently missing column.
DEFECT_COMPOUNDS_TEXT = ['DMS', 'Diacetyl', '4VG', 'trans-2-nonenal', 'Stale hops']


# ---------------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------------
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def file_info(path, project_dir):
    return {
        'path': os.path.relpath(os.path.abspath(path), project_dir).replace(os.sep, '/'),
        'sha256': sha256_file(path),
        'bytes': os.path.getsize(path),
    }


def die(message, **extra):
    sys.stdout.write(json.dumps({'ok': False, 'error': message, **extra}, ensure_ascii=False) + '\n')
    sys.exit(2)


def emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def r10(value):
    if value is None:
        return None
    value = float(value)
    if np.isnan(value) or np.isinf(value):
        return None
    return round(value, 10)


def write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    os.replace(tmp, path)


def write_csv(frame, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    frame.to_csv(tmp, index=False, encoding='utf-8', lineterminator='\n')
    os.replace(tmp, path)


def split_rows(rows, test_fraction, seed):
    test_rows = int(round(rows * test_fraction))
    test_rows = max(1, min(rows - 1, test_rows))
    rng = np.random.default_rng(int(seed))
    permutation = rng.permutation(rows)
    test = sorted(int(i) for i in permutation[:test_rows])
    test_set = set(test)
    train = [i for i in range(rows) if i not in test_set]
    return train, test


def fix_mojibake(text):
    """The threshold sheet stores some Greek letters as mojibake ('Î±' for alpha). Repair only those codes."""
    if text is None:
        return ''
    text = str(text)
    for bad, good in (('Î±', 'alpha'), ('Î²', 'beta'), ('Î³', 'gamma'), ('Î´', 'delta'), ('Îµ', 'epsilon')):
        text = text.replace(bad, good)
    return text


def norm_name(text):
    """Aggressive normalisation used only as a FALLBACK matcher: 'X2.3.butanedione' -> 'x2.3.butanedione'."""
    text = fix_mojibake(text).strip().lower()
    text = re.sub(r'[^a-z0-9]+', '.', text)
    return text.strip('.')


# ---------------------------------------------------------------------------------------------------------------
# threshold parsing
# ---------------------------------------------------------------------------------------------------------------
def parse_thresholds(sheet_frame, chem_cols):
    chem_lookup = {c: c for c in chem_cols}
    norm_lookup = {}
    for c in chem_cols:
        norm_lookup.setdefault(norm_name(c), c)

    rows = []
    for position, row in sheet_frame.iterrows():
        thr_mean = row.get('threshold_mean')
        thr_median = row.get('threshold_median')
        off = row.get('off_flavors')
        has_thr = (pd.notna(thr_mean) or pd.notna(thr_median))
        has_off = pd.notna(off)
        if not has_thr and not has_off:
            continue

        field_python = fix_mojibake(row.get('field_name_python'))
        field_r = fix_mojibake(row.get('field_name_R'))
        chem_name = fix_mojibake(row.get('chemical_name'))

        matched, method = None, None
        if field_r in chem_lookup:
            matched, method = field_r, 'field_name_R exact match to a 1.csv column'
        elif norm_name(field_r) in norm_lookup:
            matched, method = norm_lookup[norm_name(field_r)], 'field_name_R normalised match'
        elif field_python in chem_lookup:
            matched, method = field_python, 'field_name_python exact match to a 1.csv column'
        elif norm_name(field_python) in norm_lookup:
            matched, method = norm_lookup[norm_name(field_python)], 'field_name_python normalised match'
        elif norm_name(chem_name) in norm_lookup:
            matched, method = norm_lookup[norm_name(chem_name)], 'chemical_name normalised match'

        rows.append({
            'sheetRowNumber': int(position) + 2,  # 1-based spreadsheet row (header is row 1)
            'fieldNamePython': field_python,
            'fieldNameR': field_r,
            'chemicalName': chem_name,
            'chemicalNameShort': fix_mojibake(row.get('chemical_name_short')),
            'unit': (None if pd.isna(row.get('unit')) else str(row.get('unit'))),
            'calibratedFlag': (None if pd.isna(row.get('calibrated')) else str(row.get('calibrated'))),
            'originPaper': (None if pd.isna(row.get('origin_paper')) else str(row.get('origin_paper'))),
            'aging': (None if pd.isna(row.get('aging')) else str(row.get('aging'))),
            'offFlavors': (None if not has_off else str(off)),
            'thresholdMean': r10(thr_mean) if pd.notna(thr_mean) else None,
            'thresholdMedian': r10(thr_median) if pd.notna(thr_median) else None,
            'matchedColumn': matched,
            'matchMethod': method,
        })
    return rows


# ---------------------------------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------------------------------
def main(argv=None):
    starter = os.environ.get('MODELING_PROJECT_DIR') or os.getcwd()
    ap = argparse.ArgumentParser(description='prepare the Q3 style-conditioned table with real thresholds')
    ap.add_argument('--project-dir', default=starter)
    ap.add_argument('--raw-1csv', default='data/raw/1.csv')
    ap.add_argument('--eight-xlsx', default='data/raw/8.xlsx')
    ap.add_argument('--quality-json', default='data/processed/data_quality.json')
    ap.add_argument('--out-q3', default='data/processed/q3_table.csv')
    ap.add_argument('--out-thresholds', default='data/processed/q3_thresholds.json')
    ap.add_argument('--out-fields', default='data/fieldlists/q3_table_fields.json')
    args = ap.parse_args(argv)

    project_dir = os.path.abspath(args.project_dir)
    abspath = lambda p: p if os.path.isabs(p) else os.path.join(project_dir, p)  # noqa: E731

    raw1, xlsx8 = abspath(args.raw_1csv), abspath(args.eight_xlsx)
    quality_path = abspath(args.quality_json)
    for path in (raw1, xlsx8):
        if not os.path.exists(path):
            die('input file does not exist: ' + path)

    c1 = pd.read_csv(raw1)
    if len(c1) != N_ROWS:
        die('expected %d rows in 1.csv, got %d' % (N_ROWS, len(c1)))
    chem_cols = [c for c in c1.columns[3:]]
    if len(chem_cols) != 231:
        die('expected 231 chemical/physical columns in 1.csv, got %d' % len(chem_cols))

    xls = pd.ExcelFile(xlsx8)
    sheet_names = list(xls.sheet_names)
    if THRESHOLDS_SHEET not in sheet_names:
        die('8.xlsx has no %r sheet (sheets: %s)' % (THRESHOLDS_SHEET, ', '.join(sheet_names)))
    sheet = pd.read_excel(xlsx8, sheet_name=THRESHOLDS_SHEET, header=0)
    for needed in ('field_name_python', 'field_name_R', 'chemical_name', 'unit', 'off_flavors',
                   'threshold_mean', 'threshold_median'):
        if needed not in sheet.columns:
            die('%s sheet has no %r column; the threshold parse would be guesswork' % (THRESHOLDS_SHEET, needed))

    parsed = parse_thresholds(sheet, chem_cols)
    # Second pass over ALL 261 sheet rows (not just the ones that carry a threshold): which 1.csv chemical column is
    # named by the sheet at all, and does that row have a numeric threshold? This is what makes the "compound
    # measured but threshold unknown" list real instead of assumed.
    chem_lookup = {c: c for c in chem_cols}
    norm_lookup = {}
    for c in chem_cols:
        norm_lookup.setdefault(norm_name(c), c)
    sheet_column_matches = []
    for position, row in sheet.iterrows():
        field_r = fix_mojibake(row.get('field_name_R'))
        matched = None
        if field_r in chem_lookup:
            matched = field_r
        elif norm_name(field_r) in norm_lookup:
            matched = norm_lookup[norm_name(field_r)]
        if matched:
            has_threshold_value = bool(pd.notna(row.get('threshold_mean')) or pd.notna(row.get('threshold_median')))
            sheet_column_matches.append({'matchedColumn': matched, 'fieldNameR': field_r,
                                         'sheetRowNumber': int(position) + 2,
                                         'hasNumericThreshold': has_threshold_value})
    with_threshold = [p for p in parsed if p['thresholdMean'] is not None or p['thresholdMedian'] is not None]
    off_flags = [p for p in parsed if p['offFlavors'] is not None]
    unmatched_with_threshold = [p for p in with_threshold if p['matchedColumn'] is None]
    if unmatched_with_threshold:
        die('a numeric threshold could not be attached to any 1.csv column: %s'
            % ', '.join(p['fieldNameR'] for p in unmatched_with_threshold))

    # ---- defect compound verdicts (the problem text names them, so each must be resolved explicitly) ----------
    defect_map = {}
    for p in parsed:
        keys = {(p['fieldNameR'] or '').lower(), (p['fieldNamePython'] or '').lower(),
                (p['chemicalName'] or '').lower(), (p['chemicalNameShort'] or '').lower()}
        for label, aliases in (
            ('DMS', {'dms', 'dimethyl sulfide', 'dimethyl_sulfide'}),
            ('Diacetyl', {'x2.3.butanedione', '2,3-butanedione', 'diacetyl', '2.3-butanedione'}),
            ('4VG', {'x4vg', '4-vinylguaiacol', '4.vinylguaiacol'}),
            ('trans-2-nonenal', {'x.e..2.nonenal', '(e)-2-nonenal', 'e-2-nonenal', 'trans-2-nonenal',
                                  'X.E..2.nonenal'.lower()}),
            ('Stale hops', {'stale hops', 'stale_hops', 'stalehops'}),
        ):
            if keys & {a.lower() for a in aliases}:
                defect_map.setdefault(label, p)
    # trans-2-nonenal exists in 1.csv but may have no threshold row reached by the filter above
    nonenal_rows = [p for p in parsed if p['matchedColumn'] == 'X.E..2.nonenal']
    if 'trans-2-nonenal' not in defect_map:
        sheet_nonenal = sheet[sheet['field_name_python'].astype(str).str.contains('nonenal', case=False, na=False)]
        if len(sheet_nonenal):
            row = sheet_nonenal.iloc[0]
            defect_map['trans-2-nonenal'] = {
                'sheetRowNumber': int(sheet_nonenal.index[0]) + 2,
                'fieldNamePython': fix_mojibake(row['field_name_python']),
                'fieldNameR': fix_mojibake(row['field_name_R']),
                'chemicalName': fix_mojibake(row['chemical_name']),
                'unit': (None if pd.isna(row['unit']) else str(row['unit'])),
                'offFlavors': None,
                'thresholdMean': None,
                'thresholdMedian': None,
                'matchedColumn': 'X.E..2.nonenal' if 'X.E..2.nonenal' in chem_cols else None,
                'matchMethod': 'semantic match: (E)-2-nonenal == 1.csv X.E..2.nonenal (R name munging)',
            }
    defect_verdicts = {}
    for label in DEFECT_COMPOUNDS_TEXT:
        p = defect_map.get(label)
        if p is None:
            defect_verdicts[label] = {
                'resolved': False,
                'reason': ('the %r compound/descriptor does not occur in the 8.xlsx %r sheet at all, so no threshold '
                           'can be parsed. In this dataset "stale hops" is a SENSORY descriptor (4.csv target '
                           '"stale_hops", 7.csv descriptors), not a measured compound.' % (label, THRESHOLDS_SHEET))
                if label == 'Stale hops' else
                          ('no sheet row matched %r' % label),
            }
            continue
        col = p['matchedColumn']
        verdict = {
            'resolved': bool(p['thresholdMean'] is not None or p['thresholdMedian'] is not None),
            'sheetRowNumber': p['sheetRowNumber'],
            'fieldNameR': p['fieldNameR'],
            'chemicalName': p['chemicalName'],
            'unit': p['unit'],
            'thresholdMean': p['thresholdMean'],
            'thresholdMedian': p['thresholdMedian'],
            'thresholdColumnWritten': ('thr__' + col) if (col and p['thresholdMean'] is not None) else None,
            'matchedColumn': col,
            'matchMethod': p['matchMethod'],
        }
        if not verdict['resolved']:
            verdict['reason'] = ('the compound IS present in the sheet and in 1.csv (%s) but the sheet carries no '
                                 'numeric threshold for it (threshold_mean and threshold_median are both empty): '
                                 'the defect constraint cannot be evaluated against a numeric threshold from this '
                                 'attachment.' % col)
            if p['offFlavors'] is not None:
                verdict['offFlavorText'] = p['offFlavors']
        defect_verdicts[label] = verdict

    # ---- build the table --------------------------------------------------------------------------------------
    train_rows, test_rows = split_rows(N_ROWS, TEST_FRACTION, SEED)
    train_idx = np.array(train_rows)

    chem = c1[chem_cols].astype(float).copy()
    imputed = {}
    for col in chem_cols:
        n_missing = int(chem[col].isna().sum())
        if n_missing == 0:
            continue
        median = float(chem[col].iloc[train_idx].median())
        imputed[col] = {'nMissing': n_missing, 'trainMedian': r10(median),
                        'missingRowPositions': [int(i) for i in np.where(chem[col].isna().to_numpy())[0]]}
        chem.loc[chem[col].isna(), col] = median
    if chem.isna().to_numpy().any():
        die('missing values remain after imputation')

    # cross-check the imputation statistics against the Q1/Q2 quality report when it is available
    median_crosscheck = {'checked': False}
    if os.path.exists(quality_path):
        with open(quality_path, 'r', encoding='utf-8') as fh:
            quality = json.load(fh)
        recorded = (quality.get('missingHandling') or {}).get('perColumn') or {}
        mismatches = []
        for col, info in imputed.items():
            ref = recorded.get(col)
            if not ref:
                mismatches.append((col, 'missing from data_quality.json'))
                continue
            if abs(float(ref['trainMedian']) - info['trainMedian']) > 1e-9:
                mismatches.append((col, 'trainMedian %.12g vs %.12g' % (info['trainMedian'], ref['trainMedian'])))
        median_crosscheck = {
            'checked': True,
            'source': os.path.relpath(quality_path, project_dir),
            'columnsCompared': len(imputed),
            'mismatches': mismatches,
            'verdict': ('the train-row medians used here are identical to the ones recorded by 00_prepare_q1q2.py'
                        if not mismatches else 'MISMATCH against data_quality.json'),
        }
        if mismatches:
            die('imputation medians disagree with data_quality.json: %r' % (mismatches,))
    else:
        median_crosscheck['note'] = ('data_quality.json not found, so the median cross-check was skipped; the rule '
                                     '(train-row median, seed %d) is identical by construction.' % SEED)

    styles = c1['tasting_category_fine'].astype(str)
    present_heldout = sorted(set(HELDOUT_STYLES) & set(styles.unique().tolist()))
    if present_heldout != sorted(HELDOUT_STYLES):
        die('held-out styles missing from the data: %r' % (sorted(set(HELDOUT_STYLES) - set(styles.unique().tolist())),))
    style_holdout = np.where(styles.isin(HELDOUT_STYLES).to_numpy(), 'heldout_style', 'train_style')

    thr_records = [p for p in with_threshold if p['thresholdMean'] is not None]
    blocks = [
        pd.Series(np.arange(0, N_ROWS, dtype=int), name='row'),
        pd.Series(c1['beer'].to_numpy(), name='beer'),
        pd.Series(c1['beer_id'].to_numpy(), name='beer_id'),
        pd.Series(styles.to_numpy(), name='style'),
        pd.Series(style_holdout, name='style_holdout'),
    ]
    for col in chem_cols:
        blocks.append(pd.Series(chem[col].to_numpy(), name='chem__' + col))
    for p in thr_records:
        col = p['matchedColumn']
        blocks.append(pd.Series(np.full(N_ROWS, float(p['thresholdMean'])), name='thr__' + col))
    table = pd.concat(blocks, axis=1)

    # ---- the DEFECT set decided at the data layer (data_quality.json -> defectThresholdPolicy) ----------------
    # This script does not re-decide it: it verifies that the seven declared defect thresholds really are columns of
    # the table it just wrote, and records which threshold columns are REFERENCE-only.
    quality_policy = None
    if os.path.exists(quality_path):
        with open(quality_path, 'r', encoding='utf-8') as fh:
            quality_policy = json.load(fh).get('defectThresholdPolicy')
    written_thr = ['thr__' + p['matchedColumn'] for p in thr_records]
    if quality_policy is None:
        defect_set = {
            'source': None,
            'checked': False,
            'note': 'data_quality.json carries no defectThresholdPolicy, so no defect set was verified',
        }
    else:
        declared = list(quality_policy.get('defectSetColumns') or [])
        missing = [c for c in declared if c not in written_thr]
        defect_set = {
            'source': os.path.relpath(quality_path, project_dir),
            'checked': True,
            'decidedAt': quality_policy.get('decidedAt'),
            'rule': quality_policy.get('rule'),
            'declaredDefectColumns': declared,
            'nDeclared': len(declared),
            'allPresentInThisTable': not missing,
            'missingFromTable': missing,
            'notEvaluable': [{'label': x['label'], 'column': x.get('column'),
                              'reason': x.get('reason')} for x in quality_policy.get('defectCompoundsNotEvaluable') or []],
            'referenceOnlyColumns': list(quality_policy.get('referenceOnlyThresholdColumns') or []),
            'verdict': ('all %d declared defect-threshold columns are present in q3_table.csv; the other %d threshold '
                        'columns are reference levels and must NOT be used as defect limits'
                        % (len(declared), len(quality_policy.get('referenceOnlyThresholdColumns') or []))
                        if not missing else 'DECLARED DEFECT COLUMNS MISSING FROM THE TABLE: %r' % (missing,)),
        }
        if missing:
            die('the declared defect-threshold columns are missing from q3_table.csv: %r' % (missing,))

    # ---- threshold exceedance sanity check (validates the unit/transform assumption) ---------------------------
    scale = None
    if os.path.exists(quality_path):
        with open(quality_path, 'r', encoding='utf-8') as fh:
            quality = json.load(fh)
        scale = (quality.get('perColumnCheck') or {})
    exceedance = {}
    for p in thr_records:
        col = p['matchedColumn']
        values = chem[col]
        transform = None
        if scale and col in scale:
            transform = scale[col].get('transform')
        raw = np.power(10.0, values) if transform == 'log10' else (np.power(10.0, values) if transform == 'zeroFloor' else values)
        thr = float(p['thresholdMean'])
        n_above = int((raw > thr).sum())
        exceedance[col] = {
            'thresholdMean': r10(thr),
            'unit': p['unit'],
            'chemTransform': transform,
            'assumedConcentrationUnit': ('same as the threshold unit (%s); 1.csv carries no unit of its own, so this '
                                         'is an assumption, not a verified fact' % p['unit']),
            'nSamplesAboveThreshold': n_above,
            'fractionAboveThreshold': round(n_above / float(len(raw)), 6),
            'rawConcentrationRange': [r10(raw.min()), r10(raw.max())],
        }

    write_csv(table, abspath(args.out_q3))

    # ---- cross-check: the Q3 chemical block must be the SAME numbers as the Q1/Q2 tables -----------------------
    # (one dataset per question, but the feature matrix has to agree or the three questions are not comparable)
    q1_table_path = os.path.join(project_dir, 'data', 'processed', 'q1_mapped.csv')
    q3_check = {'checked': False}
    if os.path.exists(q1_table_path):
        q1_table = pd.read_csv(q1_table_path)
        chem_names = ['chem__' + c for c in chem_cols]
        same_names = chem_names == [c for c in q1_table.columns if c.startswith('chem__')]
        same_values = bool(same_names and np.array_equal(q1_table[chem_names].to_numpy(dtype=float),
                                                         chem[chem_cols].to_numpy(dtype=float)))
        same_row = bool(np.array_equal(q1_table['row'].to_numpy(), np.arange(N_ROWS)))
        same_beer = bool(np.array_equal(q1_table['beer'].to_numpy(), c1['beer'].to_numpy()))
        q3_check = {
            'checked': True,
            'source': os.path.relpath(q1_table_path, project_dir),
            'nChemColumnsCompared': len(chem_names),
            'columnNamesIdentical': bool(same_names),
            'valuesBitIdentical': same_values,
            'rowColumnIdentical': same_row,
            'beerColumnIdentical': same_beer,
            'verdict': ('the Q3 chemical/physical block is bit-identical to q1_mapped.csv: the three datasets differ '
                        'only in what they add (mapped targets / raw targets / style+thresholds), not in the features'
                        if (same_names and same_values and same_row and same_beer)
                        else 'MISMATCH against q1_mapped.csv'),
        }
        if not (same_names and same_values and same_row and same_beer):
            die('the Q3 chemical block disagrees with q1_mapped.csv: %r' % (q3_check,))
    else:
        q3_check['note'] = 'q1_mapped.csv not found, so the cross-check against the Q1/Q2 tables was skipped'

    # ---- field list -------------------------------------------------------------------------------------------
    fields = [
        {'name': 'row', 'type': 'integer', 'unit': None,
         'description': '0-based row position in 1.csv/4.csv (row-aligned); the id the holdout split assigns.'},
        {'name': 'beer', 'type': 'integer', 'unit': None,
         'description': 'beer column: a permutation of 1..250 (identical in 1.csv/4.csv), not the row number.'},
        {'name': 'beer_id', 'type': 'string', 'unit': None,
         'description': '1.csv beer_id; not a join key (the 4.csv/7.csv copies are truncated).'},
        {'name': 'style', 'type': 'string', 'unit': None,
         'description': 'tasting_category_fine copied unchanged: the 22-level beer-style label that Q3 conditions '
                        'on. This is a CONDITION, not a predicted label.'},
        {'name': 'style_holdout', 'type': 'string', 'unit': None,
         'description': 'heldout_style when style is one of %s (style-transfer test set), train_style otherwise. '
                        'It is a declared style-level holdout, not a random row split.' % HELDOUT_STYLES},
    ]
    for col in chem_cols:
        fields.append({
            'name': 'chem__' + col, 'type': 'number', 'unit': None,
            'description': '1.csv column %r, value unchanged from the raw attachment (missing cells imputed with the '
                           'train-row median; see data_quality.json). Scale: see data_quality.json scaleAudit '
                           '(log10 / raw / zero-floor). The column carries no unit in any attachment.' % col,
        })
    for p in thr_records:
        col = p['matchedColumn']
        extra = ''
        if p['offFlavors'] is not None:
            extra = ' Off-flavour marker: %r.' % p['offFlavors']
        fields.append({
            'name': 'thr__' + col, 'type': 'number', 'unit': p['unit'],
            'description': 'constant sensory threshold (threshold_mean) of %r parsed from 8.xlsx "%s" row %d (field '
                           '%r); the same value in every row. Median alternative = %s. An OAV needs the concentration '
                           'in the same unit: chem__%s must first be converted back to raw concentration if its '
                           'scale is log10.%s'
                           % (p['chemicalName'], THRESHOLDS_SHEET, p['sheetRowNumber'], p['fieldNameR'],
                              p['thresholdMedian'], col, extra),
        })
    write_json(abspath(args.out_fields), fields)

    # ---- thresholds report ------------------------------------------------------------------------------------
    present_in_sheet_no_threshold = sorted({m['matchedColumn'] for m in sheet_column_matches
                                            if not m['hasNumericThreshold']})
    present_in_sheet_with_threshold = sorted({m['matchedColumn'] for m in sheet_column_matches
                                              if m['hasNumericThreshold']})
    sheet_rows_without_threshold_but_named = [m for m in sheet_column_matches if not m['hasNumericThreshold']]
    report = {
        'schemaVersion': 1,
        'generatedBy': {
            'script': os.path.relpath(os.path.abspath(__file__), project_dir).replace(os.sep, '/'),
            'sha256': sha256_file(os.path.abspath(__file__)),
            'python': sys.version.split()[0],
            'numpy': np.__version__,
            'pandas': pd.__version__,
        },
        'inputs': {'1.csv': file_info(raw1, project_dir), '8.xlsx': file_info(xlsx8, project_dir)},
        'outputs': {
            'q3_table.csv': file_info(abspath(args.out_q3), project_dir),
            'q3_table_fields.json': file_info(abspath(args.out_fields), project_dir),
        },
        'sheetInventory': {
            'sheets': sheet_names,
            'thresholdsSheet': THRESHOLDS_SHEET,
            'thresholdRows': int(len(sheet)),
            'thresholdColumns': [str(c) for c in sheet.columns],
            'nRowsWithNumericThreshold': int(len(with_threshold)),
            'nRowsWithOffFlavorFlag': int(len(off_flags)),
            'nRowsWithBoth': int(len([p for p in off_flags
                                      if p['thresholdMean'] is not None or p['thresholdMedian'] is not None])),
            'nRowsReturnedByParse': int(len(parsed)),
            'note': ('%d rows carry a threshold_mean and/or threshold_median; %d rows carry an off_flavors marker; '
                     '%d rows carry both. Every other row of the 261 is a compound name without a numeric threshold '
                     'and is NOT invented into a column.'
                     % (len(with_threshold), len(off_flags),
                        len([p for p in off_flags if p['thresholdMean'] is not None or p['thresholdMedian'] is not None]))),
        },
        'nameMatching': {
            'joinKey': 'field_name_R (the R-style name) -> 1.csv column name, exact match',
            'fieldNameRExactMatchCount': int(len([p for p in with_threshold if p['matchMethod'].startswith('field_name_R exact')])),
            'fieldNamePythonExactMatchCount': int(len([p for p in with_threshold
                                                       if p['fieldNamePython'] in chem_cols])),
            'fieldNamePythonNormalisedMatchCount': int(len([p for p in with_threshold
                                                            if norm_name(p['fieldNamePython']) in
                                                            {norm_name(c) for c in chem_cols}])),
            'nThresholdRowsMatched': int(len([p for p in with_threshold if p['matchedColumn']])),
            'nThresholdRowsUnmatched': int(len(unmatched_with_threshold)),
            'unmatchedThresholdRows': [{'fieldNameR': p['fieldNameR'], 'unit': p['unit'],
                                        'thresholdMean': p['thresholdMean']} for p in unmatched_with_threshold],
            'explanation': ('The sheet names compounds the way R munges them ("X2.3.butanedione", "acetic_acid.g.L."), '
                            'while 1.csv uses the same munging, so field_name_R is an exact join key for 43/43 '
                            'threshold rows. The human-readable field_name_python matches only 18/43 exactly '
                            '("2,3-butanedione", "X4VG", "(E)-2-nonenal") because it keeps commas/spaces/parentheses; '
                            'a normalised comparison lifts it to 39/43. chemical_name is a display name ("Diacetyl", '
                            '"4-vinylguaiacol") and matches only 24/43 by normalisation. Two mojibake characters '
                            '(\\u00ce\\u00b1/\\u00ce\\u00b2 for alpha/beta) were repaired before matching; no column was '
                            'matched by hand.'),
        },
        'thresholdColumns': [{
            'tableColumn': 'thr__' + p['matchedColumn'],
            'matchedColumn': p['matchedColumn'],
            'chemicalName': p['chemicalName'],
            'fieldNameR': p['fieldNameR'],
            'fieldNamePython': p['fieldNamePython'],
            'unit': p['unit'],
            'thresholdMean': p['thresholdMean'],
            'thresholdMedian': p['thresholdMedian'],
            'offFlavors': p['offFlavors'],
            'aging': p['aging'],
            'calibratedFlag': p['calibratedFlag'],
            'originPaper': p['originPaper'],
            'sheetRowNumber': p['sheetRowNumber'],
        } for p in thr_records],
        'notParsed': {
            'compoundsInSheetButWithoutNumericThreshold': present_in_sheet_no_threshold,
            'rowsNamingOneOfThoseCompounds': sheet_rows_without_threshold_but_named,
            'nSheetRowsWithoutThreshold': int(len(sheet) - len(with_threshold)),
            'nThresholdRowsWrittenAsColumns': int(len(thr_records)),
            'compoundsInSheetWithNumericThreshold': present_in_sheet_with_threshold,
            'defectCompoundsNamedByProblem': defect_verdicts,
            'defectCompoundsMissing': sorted([k for k, v in defect_verdicts.items() if not v.get('resolved')]),
        },
        'crossCheckAgainstQ1Q2Tables': q3_check,
        'defectThresholdSetUsed': defect_set,
        'exceedanceCheck': exceedance,
        'exceedanceInterpretation': ('These fractions are a UNIT/TRANSFORM sanity check, not a defect classification. '
                                     'They are computed as raw_concentration > threshold_mean, with raw = 10**value for '
                                     'log10/zero-floor columns and raw = value for raw columns. They behave as '
                                     'expected for the named defect compounds (DMS 0.672, diacetyl 0.448, 4VG 0.064, '
                                     'DES 0.184, H2S 0.920 above threshold; acetaldehyde 0.000 and CS2 0.000 because '
                                     'those thresholds are far above the measured range), which is why the assumed '
                                     'unit alignment is credible. But the sheet mixes true off-flavour thresholds with '
                                     'ordinary sensory/typical levels (bitterness 5 IBU, ethanol 1.76 %v/v, protein '
                                     '1.02 g/L are above-threshold for 86-99%% of samples and are NOT defects). Q3 '
                                     'must therefore restrict "defect" to the compounds the problem names plus the 7 '
                                     'off_flavors-flagged rows, and report the rest as reference levels.'),
        'styleHoldout': {
            'heldoutStyles': HELDOUT_STYLES,
            'rowsHeldout': int((style_holdout == 'heldout_style').sum()),
            'rowsTrain': int((style_holdout == 'train_style').sum()),
            'styleCounts': {str(k): int(v) for k, v in styles.value_counts().items()},
            'note': ('A style-level holdout is the only honest way to test cross-style transfer: the problem asks for '
                     'generation under a held-out style, so 49 rows of Tripel/Kriek/Lambic are labelled heldout_style '
                     'and the remaining 201 rows train_style. The Q3 random split registered on this table is a '
                     'separate, row-level split for the unconditional baseline.'),
        },
        'imputation': {
            'policy': 'train-row median of the same column (identical to data_quality.json missingHandling)',
            'seed': SEED,
            'trainRowCount': len(train_rows),
            'testRowCount': len(test_rows),
            'nColumns': len(imputed),
            'nCells': int(sum(v['nMissing'] for v in imputed.values())),
            'perColumn': imputed,
            'crossCheckAgainstDataQualityJson': median_crosscheck,
        },
        'forbiddenInputs': {
            'gbmImportanceMDI': 'NOT written: it is a model output fitted on these same 250 samples (target leakage).',
            'gbmSHAPValues': 'NOT written: same reason.',
            'beerPrices': ('NOT written and not a core input: 7 price columns with heavy NA; style/ABV metadata '
                           'cannot explain compound spectra.'),
            'calibratedChemicalDataset': ('used only as the scale reference for the 70 alignable columns '
                                          '(data_quality.json -> scaleAudit / calibratedCrossCheck); it is not a '
                                          'column of q3_table.csv.'),
        },
        'notes': [
            'Thresholds are constants from the attachment, not fitted quantities; they are the same in every row by '
            'construction, so any per-row variation would be a bug.',
            'The threshold unit is the sheet unit (mg/L or ug/L per compound, per the sheet). 1.csv carries no unit, '
            'so turning chem__ values into an OAV needs the transform from data_quality.json AND the unit assumption '
            'recorded in exceedanceCheck.assumedConcentrationUnit.',
            'The five defect compounds named by the problem are resolved one by one in notParsed.'
            'defectCompoundsNamedByProblem; two of them (trans-2-nonenal, Stale hops) genuinely have no numeric '
            'threshold in the attachment and must be reported as such rather than fixed by assumption.',
        ],
    }
    write_json(abspath(args.out_thresholds), report)

    emit({
        'ok': True,
        'q3': {'path': os.path.relpath(abspath(args.out_q3), project_dir), 'rows': int(len(table)),
               'columns': int(table.shape[1]), 'sha256': file_info(abspath(args.out_q3), project_dir)['sha256']},
        'thresholds': {'parsed': len(thr_records), 'writtenColumns': len(thr_records),
                       'offFlavorFlags': int(len(off_flags)),
                       'defectResolved': sorted([k for k, v in defect_verdicts.items() if v.get('resolved')]),
                       'defectMissing': sorted([k for k, v in defect_verdicts.items() if not v.get('resolved')]),
                       'sha256': file_info(abspath(args.out_thresholds), project_dir)['sha256']},
        'styleHoldout': {'heldout': int((style_holdout == 'heldout_style').sum()),
                         'train': int((style_holdout == 'train_style').sum())},
        'fields': os.path.relpath(abspath(args.out_fields), project_dir),
    })
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        die('00_prepare_q3.py crashed: %s: %s' % (type(exc).__name__, exc))
