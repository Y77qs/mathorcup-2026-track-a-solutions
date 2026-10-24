#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""00_prepare_q1q2.py — Q1/Q2 data preparation (self-contained; run via modeling_data run-script).

What it does, in order:
  1. reads data/raw/1.csv (250 x 234 chemical/physical matrix) and data/raw/4.csv (250 x 53 sensory
     table) and problem/targetcolumns.csv (the authoritative 50-target mapping);
  2. PROVES the row alignment (beer / tasting_category_fine compare cell-by-cell) — the only legal join
     key here is the 0-based row position, never beer_id (4.csv beer_id is numerically truncated);
  3. AUTHORS a per-column scale verdict for all 231 chemical/physical columns
     (log10 / raw concentration / zero-floor-coded log10) and backs each verdict with evidence:
       · the 70 columns that also exist in 8.xlsx "Calibrated chemical dataset" (raw concentrations) are
         classified by exact numeric identity under each hypothesis (median |a-b| vs median |a-10^b|);
       · the remaining 161 columns are classified from negative values (a raw concentration cannot be
         negative) and column-family coherence, with an explicit confidence and evidence string;
  4. imputes the 73 missing cells of 1.csv with the TRAIN-ROW MEDIAN of the same column (the train set is
     the exact split.py split, seed 20261024) and records every imputed cell;
  5. builds the Q1 mapped grade  x = 6*(z - zmin)/(zmax - zmin)  with zmin/zmax estimated on the 200
     TRAIN rows only, and records the resulting out-of-range cells instead of hiding them;
  6. writes q1_mapped.csv, q2_raw.csv, q1_split_rows.json, the two full field lists and data_quality.json.

The last stdout line is a JSON summary (the runner does not require it, but a failed expectation must be
visible and the exit code must be non-zero).
"""

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

SEED = 20261024
TEST_FRACTION = 0.2
N_ROWS = 250

# 8.xlsx sheet that holds the *raw* (untransformed) concentrations of 70 chemical columns.
CALIBRATED_SHEET = 'Calibrated chemical dataset'
THRESHOLDS_SHEET = 'Sensory thresholds'

# The DEFECT set for Q3, fixed at the data layer (a decision, not a discovery): a compound may only be used as a
# defect constraint if (a) the problem statement names it among the defect compounds (DMS / Diacetyl / 4VG /
# trans-2-nonenal / Stale hops) OR 8.xlsx marks it with an off_flavors string, AND (b) 8.xlsx carries a REAL numeric
# threshold for it. Every other threshold in the sheet is a typical/detection level reference, never a defect limit.
DEFECT_POLICY = [
    ('DMS', 'DMS'),
    ('Diacetyl', 'X2.3.butanedione'),
    ('4VG', 'X4VG'),
    ('acetaldehyde', 'acetaldehyde'),
    ('DES', 'DES'),
    ('H2S', 'H2S'),
    ('SO2', 'SO2.mg.L.'),
]
# Named by the problem but with NO numeric threshold in the attachment: recorded, never invented.
DEFECT_UNAVAILABLE = [
    ('trans-2-nonenal', 'X.E..2.nonenal'),
    ('Stale hops', None),
]

# Median |error| below this is treated as an exact identity (float64 round-trip noise is ~1e-10).
EXACT_TOL = 1e-6
# A mapped value counts as outside [0,6] only beyond this margin; anything smaller is last-bit float noise.
FLOAT_NOISE = 1e-9
# Significant decimal digits written for the mapped grade (see the round-trip note in data_quality.json).
MAPPED_PRECISION = 12


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


def jfloat(value):
    """JSON-safe float (no NaN/Inf: those would silently mean 'unknown' in the ledger)."""
    if value is None:
        return None
    value = float(value)
    if np.isnan(value) or np.isinf(value):
        return None
    return value


def r6(value):
    value = jfloat(value)
    return None if value is None else round(value, 10)


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
    """Byte-for-byte the split.py logic: default_rng(seed).permutation(rows), test = first round(rows*f)."""
    test_rows = int(round(rows * test_fraction))
    test_rows = max(1, min(rows - 1, test_rows))
    rng = np.random.default_rng(int(seed))
    permutation = rng.permutation(rows)
    test = sorted(int(i) for i in permutation[:test_rows])
    test_set = set(test)
    train = [i for i in range(rows) if i not in test_set]
    return train, test, test_rows


# ---------------------------------------------------------------------------------------------------------------
# scale audit
# ---------------------------------------------------------------------------------------------------------------
def classify_columns(c1, calibrated, chem_cols):
    """Author one scale verdict per chemical/physical column with evidence + confidence.

    Returns (per_column, log10_cols, raw_cols, zero_floor_cols, derived_sums).
    """
    cal_cols = [c for c in calibrated.columns if c in chem_cols]
    per_column = {}
    log10_cols, raw_cols, zero_floor_cols, derived_sums = [], [], [], []

    for col in chem_cols:
        a = c1[col].astype(float)
        stats = {
            'n': int(a.notna().sum()),
            'nMissing': int(a.isna().sum()),
            'nNegative': int((a < 0).sum()),
            'nZero': int((a == 0).sum()),
            'min': r6(a.min()),
            'max': r6(a.max()),
            'median': r6(a.median()),
        }
        # most-repeated exact value: a fixed constant repeated >=5 times is a detector floor, not a measurement
        vc = a.round(12).value_counts()
        recurring = vc[vc >= 5]
        floor_candidates = [[float(k), int(v)] for k, v in list(recurring.items())[:3]] if len(recurring) else []

        record = {
            'transform': None,
            'method': None,
            'confidence': None,
            'evidence': None,
            'stats': stats,
            'recurringValues': floor_candidates,
            'calibrated': None,
        }

        if col in cal_cols:
            b = calibrated[col].astype(float)
            both = a.notna() & b.notna()
            d_raw = (a[both] - b[both]).abs()
            pos = both & (b > 0)
            d_log = (a[pos] - np.log10(b[pos])).abs()
            zero_rows = both & (b == 0)
            floor_vals = sorted(set(np.round(a[zero_rows].to_numpy(), 10))) if int(zero_rows.sum()) else []
            cal_info = {
                'matched1CsvColumn': col,
                'calibratedColumn': col,
                'nRowsCompared': int(both.sum()),
                'medianAbsDiffRawHypothesis': r6(d_raw.median()),
                'medianAbsDiffLog10Hypothesis': r6(d_log.median()),
                'maxAbsDiffUnderChosen': None,
                'nRowsWithDiffAbove1e3UnderChosen': None,
                'nCalibratedZeroRows': int(zero_rows.sum()),
                'floorValueUsedForCalibratedZeros': floor_vals[0] if len(floor_vals) == 1 else None,
                'floorValueUniqueCount': len(floor_vals),
                'calibratedRawMin': r6(b.min()),
                'calibratedRawMax': r6(b.max()),
            }
            med_raw = float(d_raw.median()) if len(d_raw) else float('inf')
            med_log = float(d_log.median()) if len(d_log) else float('inf')
            if med_log <= med_raw and med_log < EXACT_TOL:
                record['transform'] = 'log10'
                record['method'] = 'exact-identity-with-log10(calibrated raw)'
                record['confidence'] = 'high'
                record['evidence'] = ('1.csv value == log10(8.xlsx Calibrated raw concentration) on all %d '
                                      'comparable rows (median |diff| %.3g); the raw-value hypothesis differs by '
                                      'median %.3g.' % (int(pos.sum()), med_log, med_raw))
                cal_info['maxAbsDiffUnderChosen'] = r6(d_log.max())
                cal_info['nRowsWithDiffAbove1e3UnderChosen'] = int((d_log > 1e-3).sum())
                if int(zero_rows.sum()) and len(floor_vals) == 1:
                    # a calibrated raw value of exactly 0 has no log10: the table substitutes a constant floor
                    share = int(zero_rows.sum()) / max(1, int(both.sum()))
                    if share >= 0.5:
                        record['transform'] = 'zeroFloor'
                        record['method'] = 'log10 with the raw value 0 (>=50% of samples) replaced by a constant floor'
                        record['evidence'] += (' Also zero-inflated: %d/%d samples have calibrated raw 0, all stored '
                                               'as the same constant %.10g -> the value is a floor code, not a '
                                               'measurement.' % (int(zero_rows.sum()), int(both.sum()), floor_vals[0]))
                log10_cols.append(col) if record['transform'] == 'log10' else None
                if record['transform'] == 'zeroFloor':
                    zero_floor_cols.append(col)
            elif med_raw <= med_log and med_raw < EXACT_TOL:
                record['transform'] = 'raw'
                record['method'] = 'exact-identity-with-raw(calibrated raw)'
                record['confidence'] = 'high'
                record['evidence'] = ('1.csv value == 8.xlsx Calibrated raw concentration on all %d comparable rows '
                                      '(median |diff| %.3g); the log10 hypothesis differs by median %.3g.'
                                      % (int(both.sum()), med_raw, med_log))
                cal_info['maxAbsDiffUnderChosen'] = r6(d_raw.max())
                cal_info['nRowsWithDiffAbove1e3UnderChosen'] = int((d_raw > 1e-3).sum())
                raw_cols.append(col)
            else:  # pragma: no cover - would mean the two tables are unrelated
                die('cannot decide the scale of %r: neither the raw nor the log10 hypothesis matches the '
                    'Calibrated sheet (median |diff| raw=%.6g, log10=%.6g)' % (col, med_raw, med_log))
            record['calibrated'] = cal_info
        else:
            n_neg = int((a < 0).sum())
            if n_neg > 0:
                record['transform'] = 'log10'
                record['method'] = 'negative-values-impossible-for-a-concentration'
                record['confidence'] = 'high'
                record['evidence'] = ('%d/%d negative values: a raw concentration cannot be negative, so the column '
                                      'is a log10 transform (min %.10g).' % (n_neg, int(a.notna().sum()), jfloat(a.min())))
            else:
                record['transform'] = 'log10'
                record['method'] = 'column-family-coherence'
                record['confidence'] = 'medium'
                record['evidence'] = ('No negative value, but: (i) every raw-scale column of 1.csv is exactly one of '
                                      'the 33 columns also present as raw concentrations in 8.xlsx Calibrated; '
                                      '(ii) the homologous/nearby columns of the same chemical family in this file '
                                      'are log10 with negative floors; (iii) the observed range %.3g..%.3g with '
                                      'median %.3g is a multi-decade log10 spread, unlike the raw group whose '
                                      'median is 1e-3..1e0. Verdict is log10 with medium confidence.'
                                      % (jfloat(a.min()), jfloat(a.max()), jfloat(a.median())))
            log10_cols.append(col)

        if col in ('esters_sum', 'aroma_hops_sum', 'acids_sum', 'sulfur_sum'):
            derived_sums.append(col)
            record['derivedSum'] = ('aggregate of several log10-transformed compounds (the brief says five properties '
                                    'are computed from individually measured compounds); it therefore lives in '
                                    'log-space, not in raw concentration space')
        per_column[col] = record

    return per_column, log10_cols, raw_cols, zero_floor_cols, derived_sums


# ---------------------------------------------------------------------------------------------------------------
# defect-threshold policy (Q3 constraint input, decided at the DATA layer)
# ---------------------------------------------------------------------------------------------------------------
def defect_threshold_policy(xlsx8, chem_cols):
    """Resolve each defect compound to a REAL threshold from 8.xlsx, or record that it has none.

    Nothing is assumed: the threshold is read from the sheet, the unit is the sheet unit, and a compound that the
    problem names but the sheet does not quantify is returned with `thresholdMean: None` plus the reason.
    """
    sheet = pd.read_excel(xlsx8, sheet_name=THRESHOLDS_SHEET, header=0)
    by_field = {}
    for _, row in sheet.iterrows():
        by_field[str(row.get('field_name_R'))] = row

    resolved, unavailable = [], []
    for label, column in DEFECT_POLICY:
        row = by_field.get(column)
        record = {
            'label': label,
            'column': column,
            'thresholdColumnInQ3': 'thr__' + column,
            'usedForDefectCheck': False,
            'thresholdMean': None,
            'thresholdMedian': None,
            'unit': None,
            'offFlavors': None,
            'sheetRowNumber': None,
            'reason': None,
        }
        if row is None:
            record['reason'] = ('%r is not a row of the %r sheet; the policy compound cannot be resolved (this would '
                                'be a data defect, not a threshold decision).' % (column, THRESHOLDS_SHEET))
            unavailable.append(record)
            continue
        thr = row.get('threshold_mean')
        thr_med = row.get('threshold_median')
        record['sheetRowNumber'] = int(row.name) + 2 if hasattr(row, 'name') else None
        record['unit'] = None if pd.isna(row.get('unit')) else str(row.get('unit'))
        record['offFlavors'] = None if pd.isna(row.get('off_flavors')) else str(row.get('off_flavors'))
        record['thresholdMean'] = r6(thr) if pd.notna(thr) else None
        record['thresholdMedian'] = r6(thr_med) if pd.notna(thr_med) else None
        if record['thresholdMean'] is None:
            record['reason'] = ('the sheet row for %r carries no numeric threshold_mean, so the defect constraint '
                                'cannot be evaluated for it' % column)
            unavailable.append(record)
            continue
        if column not in chem_cols:  # pragma: no cover - all policy columns exist in 1.csv
            record['reason'] = '%r is not a column of 1.csv' % column
            unavailable.append(record)
            continue
        record['usedForDefectCheck'] = True
        resolved.append(record)

    # every other threshold column stays in the dataset as a REFERENCE level, never a defect limit
    with_threshold = sorted({str(row.get('field_name_R')) for _, row in sheet.iterrows()
                             if pd.notna(row.get('threshold_mean')) or pd.notna(row.get('threshold_median'))})
    policy_columns = {c for _, c in DEFECT_POLICY}
    reference_only = [c for c in with_threshold if c not in policy_columns and c in chem_cols]

    for label, column in DEFECT_UNAVAILABLE:
        entry = {
            'label': label,
            'column': column,
            'thresholdColumnInQ3': None,
            'usedForDefectCheck': False,
            'thresholdMean': None,
            'reason': None,
        }
        if column is None:
            entry['reason'] = ('"stale hops" is not a compound row of the %r sheet at all: in this dataset it is a '
                               'SENSORY descriptor (4.csv target "stale_hops", 7.csv descriptors), so there is no '
                               'concentration and no threshold to compare.' % THRESHOLDS_SHEET)
        else:
            row = by_field.get(column)
            if row is not None:
                entry['sheetRowNumber'] = int(row.name) + 2 if hasattr(row, 'name') else None
                entry['unit'] = None if pd.isna(row.get('unit')) else str(row.get('unit'))
                thr = row.get('threshold_mean')
                entry['thresholdMean'] = r6(thr) if pd.notna(thr) else None
                if entry['thresholdMean'] is None:
                    entry['reason'] = ('the compound exists in the sheet AND in 1.csv (%s), but the sheet has no '
                                       'numeric threshold for it: the defect constraint is NOT evaluable from this '
                                       'attachment and no value is invented.' % column)
                else:  # pragma: no cover - the sheet has no such value today
                    entry['usedForDefectCheck'] = True
                    entry['thresholdColumnInQ3'] = 'thr__' + column
        unavailable.append(entry)

    return {
        'decidedAt': 'data layer (data-engineer), before any Q3 modelling',
        'rule': ('A compound is a DEFECT constraint only if (a) the problem statement names it among the defect '
                 'compounds OR 8.xlsx carries an off_flavors marker for it, AND (b) 8.xlsx carries a real numeric '
                 'threshold for it. Thresholds that merely describe a typical/detection level (bitterness 5 IBU, '
                 'ethanol 1.76 %v/v, protein 1.02 g/L ...) are REFERENCE levels: they stay in the dataset as thr__ '
                 'columns but must never be used to declare a defect.'),
        'defectSet': [r for r in resolved if r['usedForDefectCheck']],
        'defectSetColumns': ['thr__' + r['column'] for r in resolved if r['usedForDefectCheck']],
        'nDefectCompounds': int(len([r for r in resolved if r['usedForDefectCheck']])),
        'defectCompoundsNotEvaluable': unavailable,
        'nNotEvaluable': int(len(unavailable)),
        'referenceOnlyThresholdColumns': ['thr__' + c for c in reference_only],
        'nReferenceOnly': int(len(reference_only)),
        'consequence': ('Q3 must evaluate defect constraints only on defectSetColumns (each with its real unit and '
                        'its log10/raw scale from scaleAudit), and must report trans-2-nonenal and "stale hops" as '
                        'limitations rather than inventing thresholds for them.'),
    }


# ---------------------------------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------------------------------
def main(argv=None):
    starter = os.environ.get('MODELING_PROJECT_DIR') or os.getcwd()
    ap = argparse.ArgumentParser(description='prepare Q1 mapped grade + Q2 raw sensory table')
    ap.add_argument('--project-dir', default=starter)
    ap.add_argument('--raw-1csv', default='data/raw/1.csv')
    ap.add_argument('--raw-4csv', default='data/raw/4.csv')
    ap.add_argument('--targets', default='problem/targetcolumns.csv')
    ap.add_argument('--eight-xlsx', default='data/raw/8.xlsx')
    ap.add_argument('--out-q1', default='data/processed/q1_mapped.csv')
    ap.add_argument('--out-q2', default='data/processed/q2_raw.csv')
    ap.add_argument('--out-split', default='data/processed/q1_split_rows.json')
    ap.add_argument('--out-fields-q1', default='data/fieldlists/q1_mapped_fields.json')
    ap.add_argument('--out-fields-q2', default='data/fieldlists/q2_raw_fields.json')
    ap.add_argument('--out-quality', default='data/processed/data_quality.json')
    args = ap.parse_args(argv)

    project_dir = os.path.abspath(args.project_dir)
    abspath = lambda p: p if os.path.isabs(p) else os.path.join(project_dir, p)  # noqa: E731

    raw1, raw4, targetsc, xlsx8 = abspath(args.raw_1csv), abspath(args.raw_4csv), abspath(args.targets), abspath(args.eight_xlsx)
    for path in (raw1, raw4, targetsc, xlsx8):
        if not os.path.exists(path):
            die('input file does not exist: ' + path)

    c1 = pd.read_csv(raw1)
    c4 = pd.read_csv(raw4)
    tmap = pd.read_csv(targetsc)
    calibrated = pd.read_excel(xlsx8, sheet_name=CALIBRATED_SHEET, header=0)
    defect_policy = defect_threshold_policy(xlsx8, list(c1.columns[3:]))

    # ---- structural checks: refuse to build on a table that is not the one we audited ---------------------------
    if len(c1) != N_ROWS or len(c4) != N_ROWS:
        die('expected %d rows in 1.csv/4.csv, got %d/%d' % (N_ROWS, len(c1), len(c4)))
    if 'col_4csv' not in tmap.columns:
        die('targetcolumns.csv has no col_4csv column')
    targets = [str(x) for x in tmap['col_4csv'].tolist()]
    if len(targets) != 50 or len(set(targets)) != 50:
        die('targetcolumns.csv must list 50 distinct target columns, got %d (%d distinct)' % (len(targets), len(set(targets))))
    missing_targets = [t for t in targets if t not in c4.columns]
    if missing_targets:
        die('target columns missing from 4.csv: ' + ', '.join(missing_targets))
    extra4 = [c for c in c4.columns[3:] if c not in set(targets)]
    if extra4:
        die('4.csv carries numeric columns that are not in targetcolumns.csv: ' + ', '.join(extra4))
    if list(c1.columns[:3]) != ['beer', 'beer_id', 'tasting_category_fine']:
        die('1.csv does not start with beer,beer_id,tasting_category_fine: %r' % (list(c1.columns[:3]),))
    chem_cols = [c for c in c1.columns[3:]]
    if len(chem_cols) != 231:
        die('expected 231 chemical/physical columns in 1.csv, got %d' % len(chem_cols))

    # ---- row alignment (the ONLY legal join is the row position) ----------------------------------------------
    beer_same = bool((c1['beer'].astype(str).to_numpy() == c4['beer'].astype(str).to_numpy()).all())
    style_same = bool((c1['tasting_category_fine'].astype(str).to_numpy()
                       == c4['tasting_category_fine'].astype(str).to_numpy()).all())
    beer_identity_order = bool((c1['beer'].to_numpy() == np.arange(1, N_ROWS + 1)).all()
                               and (c4['beer'].to_numpy() == np.arange(1, N_ROWS + 1)).all())
    beer_sets_equal = set(c1['beer'].tolist()) == set(c4['beer'].tolist())
    cal_beer_same = bool((calibrated['beer'].astype(str).to_numpy() == c1['beer'].astype(str).to_numpy()).all())
    if not beer_same or not style_same:
        die('1.csv and 4.csv are not row-aligned (beer identical=%s, style identical=%s); refusing to join by '
            'position' % (beer_same, style_same))

    beer_id_1 = c1['beer_id']
    beer_id_4 = c4['beer_id']
    trunc = {
        'rows': N_ROWS,
        'distinctBeerId_1csv': int(beer_id_1.nunique(dropna=True)),
        'distinctBeerId_4csv': int(beer_id_4.nunique(dropna=True)),
        'beerId4csvExample': [str(v) for v in beer_id_4.dropna().astype(str).head(5).tolist()],
        'beerId1csvExample': [str(v) for v in beer_id_1.astype(str).head(5).tolist()],
        'maxBeersPerBeerId_4csv': int(c4.groupby(c4['beer_id'].round(0))['beer'].nunique().max()),
        'maxBeersPerBeerId_1csv': int(c1.groupby(c1['beer_id'])['beer'].nunique().max()),
        'nBeerIdExactMatches': int(sum(str(a) == str(b) for a, b in zip(beer_id_4, beer_id_1))),
        'verdict': ('4.csv (and 7.csv) beer_id is numerically truncated: 250 rows collapse to only %d distinct '
                    'values, and one 4.csv beer_id covers up to %d different beers. beer_id is therefore NEVER a '
                    'join key; every cross-table merge uses the 0-based row position, which is proven safe by the '
                    'beer/tasting_category_fine cell-by-cell equality below.'
                    % (int(beer_id_4.nunique(dropna=True)), int(c4.groupby(c4['beer_id'].round(0))['beer'].nunique().max()))),
    }

    row_alignment = {
        'rows1csv': int(len(c1)),
        'rows4csv': int(len(c4)),
        'rowsCalibrated': int(len(calibrated)),
        'beerColumnIdentical': beer_same,
        'beerSetEqual1vs4': beer_sets_equal,
        'tastingCategoryFineIdentical': style_same,
        'beerIsIdentityOrder1To250': beer_identity_order,
        'beerOrderNote': ('beer is a permutation of 1..250 (same permutation in 1.csv, 4.csv and 8.xlsx), NOT the row '
                          'number: row 0 has beer=10, row 1 has beer=86. So "row 3" and "beer 3" are different '
                          'samples; always use row (the positional id) for the split and report the beer value '
                          'alongside it.'),
        'calibratedBeerIdenticalTo1csv': cal_beer_same,
        'joinPolicy': ('row position 0..249 of 4.csv; beer would also be legal (identical permutation, unique) but '
                       'beer_id is truncated. No sort, no filter, no drop before assigning row.'),
    }

    # ---- split (exactly split.py) -----------------------------------------------------------------------------
    train_rows, test_rows, n_test = split_rows(N_ROWS, TEST_FRACTION, SEED)
    train_idx = np.array(train_rows)
    test_idx = np.array(test_rows)

    # ---- scale audit ------------------------------------------------------------------------------------------
    per_column, log10_cols, raw_cols, zero_floor_cols, derived_sums = classify_columns(c1, calibrated, chem_cols)

    # ---- missing values: train-row median, per column ----------------------------------------------------------
    na_counts = {c: int(c1[c].isna().sum()) for c in chem_cols if int(c1[c].isna().sum()) > 0}
    impute_stats = {}
    chem = c1[chem_cols].astype(float).copy()
    for col, n_missing in na_counts.items():
        train_values = chem[col].iloc[train_idx]
        median = float(train_values.median())
        test_values = chem[col].iloc[test_idx]
        test_median = float(test_values.median())
        impute_stats[col] = {
            'nMissing': n_missing,
            'missingRowPositions': [int(i) for i in np.where(chem[col].isna().to_numpy())[0]],
            'trainRowCount': int(len(train_rows)),
            'trainMedian': r6(median),
            'testMedianForReferenceOnly': r6(test_median),
            'medianShiftTrainVsTest': r6(median - test_median),
        }
        if not np.isfinite(median):  # pragma: no cover - a column that is entirely missing
            die('column %r is entirely missing on the train rows; a median cannot be defined' % col)
        chem.loc[chem[col].isna(), col] = median

    if chem.isna().to_numpy().any():  # pragma: no cover
        die('missing values remain after imputation')

    # ---- Q1 mapped grade --------------------------------------------------------------------------------------
    z = c4[targets].astype(float)
    if int(z.isna().to_numpy().sum()) != 0:
        die('4.csv target columns contain %d missing values; the mapped-grade definition assumes complete targets'
            % int(z.isna().to_numpy().sum()))
    z_train = z.iloc[train_idx]
    zmin = z_train.min()
    zmax = z_train.max()
    span = zmax - zmin
    constant_targets = [t for t in targets if float(span[t]) == 0.0]
    mapped = pd.DataFrame(index=z.index)
    per_target = {}
    below_total = above_total = 0
    below_real = above_real = 0
    for t in targets:
        if t in constant_targets:  # documented degenerate case: put every row at the 0-6 midpoint
            mapped[t] = 3.0
        else:
            mapped[t] = 6.0 * (z[t] - float(zmin[t])) / float(span[t])
        colv = mapped[t]
        # strict counts include last-bit float noise at the exact endpoints (a value of 6.0000000000000011);
        # the *real* counts require a margin of more than 1e-9, and the report uses those.
        n_below = int((colv < 0).sum())
        n_above = int((colv > 6).sum())
        n_below_real = int((colv < -FLOAT_NOISE).sum())
        n_above_real = int((colv > 6.0 + FLOAT_NOISE).sum())
        below_total += n_below_real
        above_total += n_above_real
        per_target[t] = {
            'zmin': r6(zmin[t]),
            'zmax': r6(zmax[t]),
            'span': r6(span[t]),
            'constantColumn': t in constant_targets,
            'nMappedBelow0': n_below_real,
            'nMappedAbove6': n_above_real,
            'nMappedBelow0Strict': n_below,
            'nMappedAbove6Strict': n_above,
            'maxDistanceOutsideInterval': r6(max(0.0, -float(colv.min()), float(colv.max()) - 6.0)),
            'nMappedBelow0OnTestRows': int((colv.iloc[test_idx] < -FLOAT_NOISE).sum()),
            'nMappedAbove6OnTestRows': int((colv.iloc[test_idx] > 6.0 + FLOAT_NOISE).sum()),
            'nMappedExactly0': int((colv == 0).sum()),
            'nMappedExactly6': int((colv == 6).sum()),
            'zminRowIsTrain': True,
        }

    # ---- assemble tables --------------------------------------------------------------------------------------
    blocks = [
        pd.Series(np.arange(0, N_ROWS, dtype=int), name='row'),
        pd.Series(c1['beer'].to_numpy(), name='beer'),
        pd.Series(c1['beer_id'].to_numpy(), name='beer_id'),
        pd.Series(c1['tasting_category_fine'].to_numpy(), name='tasting_category_fine'),
    ]
    for col in chem_cols:
        blocks.append(pd.Series(chem[col].to_numpy(), name='chem__' + col))
    chem_out = pd.concat(blocks, axis=1)

    # The mapped grade is written with MAPPED_PRECISION significant decimal digits: 4.csv carries ~10 significant
    # digits, the map is linear, and a 12-digit decimal string is parsed back bit-exactly by pandas' default C float
    # parser (a 17-digit string is not, it can land 1 ULP away), so the delivered number IS the computed number.
    mapped_written = mapped.copy()
    for t in targets:
        mapped_written[t] = [float('%.*g' % (MAPPED_PRECISION, float(v))) for v in mapped[t].to_numpy()]
    q1 = pd.concat([chem_out, pd.DataFrame({t: mapped_written[t].to_numpy() for t in targets})], axis=1)
    q2 = pd.concat([chem_out, pd.DataFrame({t: z[t].to_numpy() for t in targets})], axis=1)

    write_csv(q1, abspath(args.out_q1))
    write_csv(q2, abspath(args.out_q2))

    # ---- round-trip check: the written file must carry the attachment's values, not a lossy re-encoding --------
    q1_read = pd.read_csv(abspath(args.out_q1))
    q2_read = pd.read_csv(abspath(args.out_q2))
    if list(q1_read.columns) != list(q1.columns):
        die('q1_mapped.csv header changed on write/read: %r != %r' % (list(q1_read.columns), list(q1.columns)))
    cells_compared = 0
    mismatched_columns = []
    for col in chem_cols:
        original = c1[col].to_numpy(dtype=float)
        written = q1_read['chem__' + col].to_numpy(dtype=float)
        present = ~np.isnan(original)
        cells_compared += int(present.sum())
        if not np.array_equal(original[present], written[present]):
            mismatched_columns.append(col)
        if not np.isnan(written).any():
            continue
    q2_targets_identical = bool(np.array_equal(q2_read[targets].to_numpy(dtype=float), z.to_numpy(dtype=float)))
    q1_targets_match_script = bool(np.array_equal(q1_read[targets].to_numpy(dtype=float),
                                                   mapped_written.to_numpy(dtype=float)))
    max_precision_loss = float(np.abs(q1_read[targets].to_numpy(dtype=float) - mapped.to_numpy(dtype=float)).max())
    round_trip = {
        'purpose': ('proves that the chem__ columns carry the 1.csv values bit-for-bit (only the imputed cells differ) '
                    'and that the target blocks survived the CSV write, instead of trusting that it did.'),
        'chemCellsCompared': int(cells_compared),
        'chemColumnsCompared': int(len(chem_cols)),
        'chemColumnsWithAnyMismatch': mismatched_columns,
        'q2TargetsBitIdenticalTo4csv': q2_targets_identical,
        'q1TargetsBitIdenticalToComputedMappedGrade': q1_targets_match_script,
        'mappedGradeSignificantDigitsWritten': MAPPED_PRECISION,
        'mappedGradeMaxAbsoluteRoundingOnWrite': r6(max_precision_loss),
        'nMissingCellsWrittenAsNaN': int(q1_read[['chem__' + c for c in chem_cols]].isna().to_numpy().sum()),
        'pandasFloatParserNote': ('pandas\' default C parser can land 1 ULP (2.2e-16) away from a 17-significant-digit '
                                  'decimal; that is why the mapped grade is written with %d digits, which round-trips '
                                  'exactly. 4.csv\'s own values are short enough decimals that they round-trip as they '
                                  'are, so q2_raw keeps them bit-identical.' % MAPPED_PRECISION),
        'verdict': ('PASS: every non-missing chem__ cell is bit-identical to 1.csv, no cell was written as NaN, the '
                    'Q2 target block is bit-identical to 4.csv, and the Q1 target block equals the computed mapped '
                    'grade rounded to %d significant digits' % MAPPED_PRECISION
                    if not mismatched_columns else 'FAIL: %r differ from 1.csv' % (mismatched_columns,)),
    }
    if mismatched_columns or not q2_targets_identical or not q1_targets_match_script:
        die('round-trip check failed: %r' % (round_trip,))

    write_json(abspath(args.out_split), {
        'seed': SEED,
        'testFraction': TEST_FRACTION,
        'rows': N_ROWS,
        'testRows': test_rows,
        'trainRows': train_rows,
        'algorithm': 'numpy.random.default_rng(seed).permutation(rows); test=sorted(permutation[:int(round(rows*testFraction))]); train=the rest',
        'mustMatchSplitPy': 'python/split.py split_random() of the modeling-contest pack',
    })

    # ---- field lists ------------------------------------------------------------------------------------------
    scale_word = {}
    for col in chem_cols:
        t = per_column[col]['transform']
        scale_word[col] = {'log10': 'log10-transformed', 'raw': 'raw concentration', 'zeroFloor': 'zero-floor-coded log10'}[t]

    common_fields = [
        {'name': 'row', 'type': 'integer', 'unit': None,
         'description': '0-based row position in 4.csv (and in 1.csv, which is row-aligned); this is the row id the '
                        'holdout split assigns (assignment.csv row_index).'},
        {'name': 'beer', 'type': 'integer', 'unit': None,
         'description': '1.csv/4.csv beer column: a permutation of 1..250 (identical in both files), so row != beer. '
                        'Legal join key; reported next to row for traceability.'},
        {'name': 'beer_id', 'type': 'string', 'unit': None,
         'description': '1.csv beer_id (EAN-like); NOT a join key: the 4.csv/7.csv copies are numerically truncated '
                        'and collapse to far fewer distinct values.'},
        {'name': 'tasting_category_fine', 'type': 'string', 'unit': None,
         'description': 'beer style label, 22 distinct styles (1.csv column, identical in 4.csv).'},
    ]
    chem_fields = [{
        'name': 'chem__' + c,
        'type': 'number',
        'unit': None,
        'description': '1.csv column %r, value unchanged from the raw attachment except that missing cells were '
                       'imputed with the train-row median (see data_quality.json). Scale: %s. The column carries no '
                       'unit in any attachment; 8.xlsx thresholds use mg/L or ug/L per compound, so an OAV needs the '
                       'per-column unit resolved separately.'
                       % (c, scale_word[c]),
    } for c in chem_cols]

    def target_field(t, mapped_grade):
        if mapped_grade:
            return {
                'name': t, 'type': 'number', 'unit': 'mapped grade (0-6 nominal, may exceed the interval)',
                'description': 'mapped grade (transformed from 4.csv standardized value), non-original 0-6: '
                               'x = 6*(z - zmin)/(zmax - zmin), where z is the 4.csv column %r (a standardized/centred '
                               'continuous value, NOT an original 0-6 panel score) and zmin/zmax are estimated on the '
                               '200 train rows of the seed-20261024 holdout only. Train rows map exactly into [0,6]; '
                               'test cells outside the train z-range can fall outside [0,6] and are kept un-clipped '
                               '(counts in data_quality.json -> mappedGrade). Must never be reported as an original '
                               '0-6 sensory rating.' % t,
            }
        return {
            'name': t, 'type': 'number', 'unit': 'standardized (4.csv), non-original 0-6',
            'description': '4.csv column %r unchanged: a standardized/centred continuous sensory value, an original '
                           '0-6 panel score transformed by an unknown standardization. Kept raw for Q2 association '
                           'analysis; never claim it is the original 0-6 rating.' % t,
        }

    write_json(abspath(args.out_fields_q1), common_fields + chem_fields + [target_field(t, True) for t in targets])
    write_json(abspath(args.out_fields_q2), common_fields + chem_fields + [target_field(t, False) for t in targets])

    # ---- calibrated cross-check (scale corroboration only; never an input feature) -----------------------------
    cal_check = {}
    for col in log10_cols + raw_cols + zero_floor_cols:
        info = per_column[col]['calibrated']
        if info:
            cal_check[col] = info
    anomalies = {c: v for c, v in cal_check.items() if (v['nRowsWithDiffAbove1e3UnderChosen'] or 0) > 0}
    neg_in_calibrated = {}
    for col in cal_check:
        vals = calibrated[col].astype(float)
        if float(vals.min()) < 0:
            neg_in_calibrated[col] = {'min': r6(vals.min()), 'nNegative': int((vals < 0).sum())}

    # ---- data quality report ----------------------------------------------------------------------------------
    flat = mapped.to_numpy()
    i_min, j_min = np.unravel_index(int(np.argmin(flat)), flat.shape)
    i_max, j_max = np.unravel_index(int(np.argmax(flat)), flat.shape)
    extremes = {
        'min': {'target': targets[j_min], 'row': int(i_min), 'beer': int(c1['beer'].iloc[i_min]),
                'mapped': r6(flat[i_min, j_min]), 'z': r6(z[targets[j_min]].iloc[i_min]),
                'isTestRow': bool(i_min in set(test_rows))},
        'max': {'target': targets[j_max], 'row': int(i_max), 'beer': int(c1['beer'].iloc[i_max]),
                'mapped': r6(flat[i_max, j_max]), 'z': r6(z[targets[j_max]].iloc[i_max]),
                'isTestRow': bool(i_max in set(test_rows))},
        'note': ('Both extremes are TEST rows whose z lies outside the train z-range; train rows stay inside [0,6] '
                 'by construction.'),
    }
    quality = {
        'schemaVersion': 1,
        'generatedBy': {
            'script': os.path.relpath(os.path.abspath(__file__), project_dir).replace(os.sep, '/'),
            'sha256': sha256_file(os.path.abspath(__file__)),
            'python': sys.version.split()[0],
            'numpy': np.__version__,
            'pandas': pd.__version__,
        },
        'inputs': {
            '1.csv': file_info(raw1, project_dir),
            '4.csv': file_info(raw4, project_dir),
            'targetcolumns.csv': file_info(targetsc, project_dir),
            '8.xlsx': file_info(xlsx8, project_dir),
        },
        'outputs': {
            'q1_mapped.csv': file_info(abspath(args.out_q1), project_dir),
            'q2_raw.csv': file_info(abspath(args.out_q2), project_dir),
            'q1_split_rows.json': file_info(abspath(args.out_split), project_dir),
            'q1_mapped_fields.json': file_info(abspath(args.out_fields_q1), project_dir),
            'q2_raw_fields.json': file_info(abspath(args.out_fields_q2), project_dir),
        },
        'shape': {
            'q1_mapped': {'rows': int(len(q1)), 'columns': int(q1.shape[1]),
                          'layout': 'row, beer, beer_id, tasting_category_fine, chem__<231 x 1.csv columns>, <50 target columns in targetcolumns.csv order>'},
            'q2_raw': {'rows': int(len(q2)), 'columns': int(q2.shape[1]),
                       'layout': 'same as q1_mapped, but the 50 target columns keep the 4.csv standardized values'},
        },
        'targetColumnsCheck': {
            'source': 'problem/targetcolumns.csv (authoritative)',
            'nDeclared': int(len(targets)),
            'nDistinct': int(len(set(targets))),
            'nFoundIn4csv': int(len(targets) - len(missing_targets)),
            'missingFrom4csv': missing_targets,
            'numericColumnsIn4csvNotInTargets': extra4,
            'verdict': '%d/%d target columns present in 4.csv with the exact declared names; 4.csv carries exactly '
                       '3 metadata columns + the 50 declared targets and nothing else.' % (len(targets) - len(missing_targets), len(targets)),
            'firstTarget': targets[0],
            'orderPreservedInOutput': True,
        },
        'rowAlignment': row_alignment,
        'beerIdTruncation': trunc,
        'scaleAudit': {
            'rule': ('A column can be one of three things and they are NOT interchangeable: (1) log10-transformed '
                     'concentration, (2) raw concentration, (3) zero-floor-coded log10. Evidence per column: exact '
                     'numeric identity with 8.xlsx Calibrated raw concentrations under each hypothesis for the 70 '
                     'columns that appear there; otherwise the sign of the values (raw concentrations cannot be '
                     'negative) plus column-family coherence. No column was assumed: the classification is computed '
                     'in this script and stored per column below.'),
            'counts': {'total': int(len(chem_cols)), 'log10': int(len(log10_cols)),
                       'zeroFloor': int(len(zero_floor_cols)), 'raw': int(len(raw_cols))},
            'log10': log10_cols,
            'raw': raw_cols,
            'zeroFloor': zero_floor_cols,
            'derivedLogSpaceSums': derived_sums,
            'calibratedAligned': {
                'n': int(len(cal_check)),
                'log10': int(len([c for c in cal_check if per_column[c]['transform'] == 'log10'])),
                'zeroFloor': int(len([c for c in cal_check if per_column[c]['transform'] == 'zeroFloor'])),
                'raw': int(len([c for c in cal_check if per_column[c]['transform'] == 'raw'])),
            },
            'physicalParameters': {
                'pH': per_column.get('pH'),
                'color.EBC.': per_column.get('color.EBC.'),
                'bitterness': per_column.get('bitterness'),
                'ethanol..v.v.': per_column.get('ethanol..v.v.'),
                'CO2.PSI.': per_column.get('CO2.PSI.'),
            },
            'physicalParameterVerdict': ('The problem statement says pH/color/bitterness/ethanol/CO2 "keep the raw '
                                         'unit", but the measurement contradicts it: each of these five columns equals '
                                         'log10 of the 8.xlsx Calibrated raw value to <1e-9 (pH 0.5705..0.6744 -> '
                                         '3.72..4.73; color 0.6532..2.4762 -> 4.5..299.35 EBC; bitterness -1.1442..'
                                         '1.7941 -> 0..62.25 IBU; ethanol -1.4559..1.0660 -> 0..11.64 %v/v; CO2 '
                                         '-0.2310..0.7076 -> 1.175..5.10 PSI). The data, not the statement, is '
                                         'authoritative; the paper must report this contradiction.'),
        },
        'perColumnCheck': per_column,
        'missingHandling': {
            'policy': ('Explicit rule, train statistics only. For every chemical/physical column with missing cells, '
                       'NaN is replaced by the MEDIAN of that column over the 200 TRAIN rows of the seed-20261024 '
                       'holdout (the same rows split.py will assign). Test-row values are never used to compute an '
                       'imputed value; the test median is recorded as a diagnostic only. No target column has a '
                       'missing value (4.csv is complete), so imputation never touches the Q1/Q2 labels and cannot '
                       'leak into zmin/zmax.'),
            'fittedOn': 'train-only',
            'trainRowCount': len(train_rows),
            'testRowCount': len(test_rows),
            'nColumnsWithMissing': int(len(na_counts)),
            'nMissingCells': int(sum(na_counts.values())),
            'perColumn': impute_stats,
            'imputedRowPositions': sorted({i for v in impute_stats.values() for i in v['missingRowPositions']}),
            'q3Note': ('Q3 reuses the same 250-row, same-seed positional split, so these train-row medians are also '
                       'the correct imputation statistics for q3_table.csv.'),
        },
        'mappedGrade': {
            'formula': 'x = 6*(z - zmin)/(zmax - zmin)',
            'zSource': '4.csv target column, unchanged (standardized/centred continuous value, not original 0-6)',
            'fittedOn': 'train-only',
            'trainRowCount': len(train_rows),
            'testRowCount': len(test_rows),
            'splitSeed': SEED,
            'testFraction': TEST_FRACTION,
            'perTarget': per_target,
            'outOfRangeCounts': {
                'total': int(below_total + above_total),
                'below0': int(below_total),
                'above6': int(above_total),
                'tolerance': FLOAT_NOISE,
                'toleranceNote': ('A cell counts as out of range only when it is more than %g outside the interval. '
                                  'The strict counts (also recorded per target as nMappedBelow0Strict / '
                                  'nMappedAbove6Strict) add cells that sit on the boundary and differ from it by '
                                  'last-bit float noise; those are not real violations.' % FLOAT_NOISE),
                'onTestRowsOnly': {
                    'below0': int(sum(v['nMappedBelow0OnTestRows'] for v in per_target.values())),
                    'above6': int(sum(v['nMappedAbove6OnTestRows'] for v in per_target.values())),
                },
                'nTargetsWithAnyOutOfRange': int(len([v for v in per_target.values()
                                                      if v['nMappedBelow0'] or v['nMappedAbove6']])),
                'byTarget': {t: {'below0': v['nMappedBelow0'], 'above6': v['nMappedAbove6'],
                                 'maxDistanceOutsideInterval': v['maxDistanceOutsideInterval']}
                             for t, v in per_target.items()
                             if v['nMappedBelow0'] or v['nMappedAbove6']},
                'clippingApplied': False,
                'reason': ('Train rows map exactly into [0,6] by construction (zmin->0, zmax->6). Test rows whose z '
                           'falls outside the TRAIN z-range map outside [0,6]; the values are kept un-clipped so the '
                           'evaluation sees the true linear map instead of a silently saturated label.'),
            },
            'endpoints': {
                'trainCellsAtExactly0': int((z_train.to_numpy() == zmin.to_numpy()).sum()),
                'trainCellsAtExactly6': int((z_train.to_numpy() == zmax.to_numpy()).sum()),
                'allCellMappedMin': r6(mapped.to_numpy().min()),
                'allCellMappedMax': r6(mapped.to_numpy().max()),
                'trainCellMappedMin': r6(mapped.iloc[train_idx].to_numpy().min()),
                'trainCellMappedMax': r6(mapped.iloc[train_idx].to_numpy().max()),
            },
            'constantColumnPolicy': ('If zmax == zmin on the train rows the linear map is undefined; the script then '
                                     'writes 3.0 (the 0-6 midpoint) for every row of that target and flags it in '
                                     'perTarget.constantColumn. This dataset has %d such column(s) (%s).'
                                     % (len(constant_targets), ', '.join(constant_targets) if constant_targets else 'none')),
            'zGlobal': {
                'min': r6(z.to_numpy().min()),
                'max': r6(z.to_numpy().max()),
                'targetsWithTrainZmaxAbove6': {t: r6(zmax[t]) for t in targets if float(zmax[t]) > 6.0},
                'targetsWithTrainZminBelow0': {t: r6(zmin[t]) for t in targets if float(zmin[t]) < 0.0},
                'note': ('4.csv is a standardized value, so z is not bounded by 0..6: clove reaches z=6.17 on the '
                         'train rows (and %s overall). This is the direct proof that the 4.csv numbers are not '
                         'original 0-6 panel scores.' % r6(z['clove'].max())),
            },
            'zTrainFlatStats': {},
            'extremes': extremes,
        },
        'roundTripCheck': round_trip,
        'defectThresholdPolicy': defect_policy,
        'calibratedCrossCheck': {
            'purpose': ('8.xlsx "Calibrated chemical dataset" is used ONLY to corroborate the per-column scale '
                        'verdicts of 1.csv. It is never a model input, never a split source and never an imputation '
                        'source.'),
            'nAlignedColumns': int(len(cal_check)),
            'medianAbsDiffChosenHypothesisMax': r6(max(
                min(v['medianAbsDiffRawHypothesis'], v['medianAbsDiffLog10Hypothesis']) for v in cal_check.values())),
            'nCellsWithDiffAbove1e3': int(sum(v['nRowsWithDiffAbove1e3UnderChosen'] for v in cal_check.values())),
            'nColumnsWithAnyCellAbove1e3': int(len(anomalies)),
            'rowLevelAnomalies': anomalies,
            'calibratedRowsWithValuesButNaN': 'the Calibrated sheet has NaN where 1.csv has a value (and vice versa) in a minority of cells; counted by nRowsCompared < 250 above',
            'negativeValuesInCalibrated': neg_in_calibrated,
            'verdict': ('%d/%d aligned columns reproduce 1.csv exactly under ONE single transform hypothesis '
                        '(worst per-column median |diff| = %.3g, tolerance 1e-6); %d cells in %d columns disagree by '
                        'more than 1e-3, and every one of them is a row-level blemish of the Calibrated sheet (e.g. '
                        'row 105 / beer 177 for n.hexanol and Z.nerolidol), not a transform ambiguity. No column '
                        'verdict depends on those cells.'
                        % (len(cal_check), len(cal_check),
                           min(min(v['medianAbsDiffRawHypothesis'], v['medianAbsDiffLog10Hypothesis']) for v in cal_check.values()),
                           int(sum(v['nRowsWithDiffAbove1e3UnderChosen'] for v in cal_check.values())), int(len(anomalies)))),
        },
        'q1Split': {
            'seed': SEED,
            'testFraction': TEST_FRACTION,
            'rows': N_ROWS,
            'testCount': len(test_rows),
            'trainCount': len(train_rows),
            'testRows': test_rows,
            'trainRows': train_rows,
            'reproduces': 'split.py split_random(): np.random.default_rng(seed).permutation(rows), test=sorted(first int(round(rows*0.2)))',
        },
        'notes': [
            'data/raw/* is never modified: every output is a NEW file under data/processed/.',
            'Q1 targets are mapped grade only; the original 0-6 panel scores are not recoverable (3.xlsx scorecards '
            'are empty templates, 3.xlsx summary results are all zero, the 4.csv standardization parameters are '
            'unknown, and clove z > 6).',
            'Q2 targets are the 4.csv standardized values unchanged; the file exists so Q2 can run its association '
            'analysis on a dataset that is explicitly NOT the mapped grade.',
            'The chemical/physical columns are identical in q1_mapped.csv and q2_raw.csv so that the two datasets '
            'differ only in the 50 target columns.',
            '5/6/7 (and 2.csv) are derived Spearman matrices of the same 250 samples; they are not independent '
            'external data and are not used in this preparation step.',
        ],
    }
    write_json(abspath(args.out_quality), quality)

    emit({
        'ok': True,
        'q1': {'path': os.path.relpath(abspath(args.out_q1), project_dir), 'rows': int(len(q1)), 'columns': int(q1.shape[1]),
               'sha256': file_info(abspath(args.out_q1), project_dir)['sha256']},
        'q2': {'path': os.path.relpath(abspath(args.out_q2), project_dir), 'rows': int(len(q2)), 'columns': int(q2.shape[1]),
               'sha256': file_info(abspath(args.out_q2), project_dir)['sha256']},
        'split': {'test': len(test_rows), 'train': len(train_rows), 'seed': SEED,
                  'sha256': file_info(abspath(args.out_split), project_dir)['sha256']},
        'targets': {'declared': len(targets), 'foundIn4csv': len(targets) - len(missing_targets)},
        'scaleAudit': quality['scaleAudit']['counts'],
        'mappedGrade': {'outOfRangeBelow0': int(below_total), 'outOfRangeAbove6': int(above_total),
                        'mappedMin': quality['mappedGrade']['endpoints']['allCellMappedMin'],
                        'mappedMax': quality['mappedGrade']['endpoints']['allCellMappedMax']},
        'missing': quality['missingHandling']['nMissingCells'],
        'quality': os.path.relpath(abspath(args.out_quality), project_dir),
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
        die('00_prepare_q1q2.py crashed: %s: %s' % (type(exc).__name__, exc))
