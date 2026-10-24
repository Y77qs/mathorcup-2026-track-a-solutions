#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""00_prepare_outlier_audit.py — register (do NOT hide) the single-point outlier at row id 73.

The modeler found, during a Q1 sensitivity experiment, that one cell of 1.csv is ~6 orders of magnitude away from its
own column: `X2.methyltetrahydrofuran.3.one` at row id 73. This script re-verifies that fact against the RAW attachment
and against every derived table, quantifies it, and records the consequence it had on the holdout metric — without
touching a single value (no winsorising, no row removal, no re-imputation).

What is verified here:
  1. the raw cell in data/raw/1.csv (value, row, beer) and the column's own distribution (median, 2nd largest, ratio);
  2. that the same value is carried unchanged into q1_mapped.csv / q2_raw.csv / q3_table.csv;
  3. the standardised magnitude under the SPLIT-0015 train statistics (the de-confounding run that saw it in test),
     together with the largest |z| any column reaches on that same train set;
  4. which splits put row 73 in their TEST set;
  5. the measured consequence on EXP-0026: prediction range, the row-73 per-row MAE, and the mean MAE over the other
     39 holdout rows (the "what the metric would be without this row" number, reported as a sensitivity statement only).

Output: data/processed/outlier_audit.json (declared to run-script). No existing CSV is written.
"""

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

COLUMN = 'X2.methyltetrahydrofuran.3.one'
ROW_ID = 73
RAW_CSV = 'data/raw/1.csv'
DERIVED = {'DATA-0001': 'data/processed/q1_mapped.csv',
           'DATA-0002': 'data/processed/q2_raw.csv',
           'DATA-0003': 'data/processed/q3_table.csv'}
STANDARDISATION_SPLIT = 'SPLIT-0015'     # the Q1 de-confounding run whose TEST set contains row 73
IMPACT_EXPERIMENT = 'EXP-0026'           # Ridge on SPLIT-0015
COMPARISON_EXPERIMENTS = ['EXP-0016', 'EXP-0025']   # same model family, row 73 NOT in test


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def die(message, **extra):
    sys.stdout.write(json.dumps({'ok': False, 'error': message, **extra}, ensure_ascii=False) + '\n')
    sys.exit(2)


def emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def main(argv=None):
    starter = os.environ.get('MODELING_PROJECT_DIR') or os.getcwd()
    ap = argparse.ArgumentParser(description='verify and register the row-73 single-point outlier')
    ap.add_argument('--project-dir', default=starter)
    ap.add_argument('--out', default='data/processed/outlier_audit.json')
    args = ap.parse_args(argv)

    project_dir = os.path.abspath(args.project_dir)
    abspath = lambda p: p if os.path.isabs(p) else os.path.join(project_dir, p)  # noqa: E731

    # A split's `row_index` is the POSITION inside ITS OWN dataset file (which may be a 200-row pool), while the
    # `row` column carries the original sample id. Map position -> original id through the dataset the ledger says the
    # split belongs to, so "row 73" always means the same beer no matter which table the split sits on.
    ledger_path = abspath('state/ledger.json')
    with open(ledger_path, 'r', encoding='utf-8') as fh:
        ledger = json.load(fh)
    dataset_path = {d['id']: d['processedPath'] for d in ledger['datasets']}
    split_dataset = {s['id']: s['datasetId'] for s in ledger['splits']}

    def split_row_ids(split_id):
        dataset_file = abspath(dataset_path[split_dataset[split_id]])
        table = pd.read_csv(dataset_file)
        original = [int(v) for v in table['row']]
        assignment = pd.read_csv(abspath('data/splits/%s/assignment.csv' % split_id))
        pick = lambda kind: [original[i] for i in
                             sorted(assignment.loc[assignment['split'] == kind, 'row_index'].astype(int))]
        return pick('train'), pick('test')
    for rel in [RAW_CSV] + list(DERIVED.values()) + ['data/splits/%s/assignment.csv' % STANDARDISATION_SPLIT,
                                                     'experiments/%s/predictions.csv' % IMPACT_EXPERIMENT]:
        if not os.path.exists(abspath(rel)):
            die('required input does not exist: ' + rel)

    raw = pd.read_csv(abspath(RAW_CSV))
    if COLUMN not in raw.columns:
        die('column %r is not in 1.csv' % COLUMN)
    series = raw[COLUMN].astype(float)
    value = float(series.iloc[ROW_ID])
    rest = series.drop(index=ROW_ID)
    median = float(series.median())
    median_without = float(rest.median())
    second_largest = float(rest.max())

    entry = {
        'column': COLUMN,
        'rowId0based': ROW_ID,
        'csvDataRow1based': ROW_ID + 2,  # header is line 1
        'beer': int(raw.loc[ROW_ID, 'beer']),
        'rawFile': {'path': RAW_CSV, 'sha256': sha256_file(abspath(RAW_CSV))},
        'rawValue': round(value, 6),
        'columnN': int(series.notna().sum()),
        'columnNA': int(series.isna().sum()),
        'columnMedianAll250': round(median, 9),
        'columnMedianWithoutRow73': round(median_without, 9),
        'columnSecondLargest': round(second_largest, 6),
        'columnSecondLargestRowId': int(series.drop(index=ROW_ID).idxmax()),
        'ratioToMedian': round(value / median_without, 1),
        'ratioToSecondLargest': round(value / second_largest, 2),
        'isColumnMax': bool(int(series.idxmax()) == ROW_ID),
        'ordersOfMagnitudeAboveMedian': round(float(np.log10(value / median_without)), 2),
    }

    # ---- carried over unchanged into every derived table ------------------------------------------------
    carried = {}
    for dataset_id, rel in DERIVED.items():
        frame = pd.read_csv(abspath(rel))
        cell = frame.loc[frame['row'] == ROW_ID, 'chem__' + COLUMN]
        carried[dataset_id] = {'path': rel, 'value': None if cell.empty else float(cell.iloc[0]),
                              'identicalToRaw': bool(not cell.empty and float(cell.iloc[0]) == value)}
        if carried[dataset_id]['identicalToRaw'] is not True:
            die('%s does not carry the raw row-73 value unchanged' % dataset_id)
    entry['carriedUnchangedInto'] = carried
    entry['valuesModifiedAnywhere'] = False

    # ---- standardised magnitude under the de-confounding split's train statistics -----------------------
    q1 = pd.read_csv(abspath('data/processed/q1_mapped.csv'))
    train_ids, test_ids = split_row_ids(STANDARDISATION_SPLIT)
    if ROW_ID not in test_ids:
        die('row 73 is not in the test set of %s; the impact story would be wrong' % STANDARDISATION_SPLIT)
    train = series.iloc[train_ids]
    mean_train, std_train = float(train.mean()), float(train.std(ddof=0))
    z_row73 = abs(value - mean_train) / std_train
    chem = [c for c in q1.columns if c.startswith('chem__')]
    q1_by_row = q1.set_index(q1['row'].astype(int))
    train_x = q1_by_row.loc[train_ids, chem]
    mu, sd = train_x.mean(), train_x.std(ddof=0).replace(0, np.nan)
    z_all = ((q1_by_row[chem] - mu) / sd).abs()
    entry['standardisation'] = {
        'splitId': STANDARDISATION_SPLIT,
        'splitDataset': split_dataset.get(STANDARDISATION_SPLIT),
        'row73InTestSet': True,
        'trainRows': len(train_ids),
        'trainMeanThisColumn': round(mean_train, 6),
        'trainStdThisColumn': round(std_train, 6),
        'zOfRow73ThisColumn': round(z_row73, 2),
        'maxAbsZAnyColumnOnSameTrainRows': round(float(z_all.iloc[train_ids].max().max()), 3),
        'note': ('row 73 is a TEST row here, so the train statistics do not contain it: the row standardised with '
                 'train statistics lands ~%.0f standard deviations out, while the largest |z| any of the 231 '
                 'chemical columns reaches inside the training rows is %.1f.'
                 % (z_row73, float(z_all.iloc[train_ids].max().max()))),
    }

    # ---- which splits put row 73 into TEST ---------------------------------------------------------------
    hits = []
    for name in sorted(os.listdir(abspath('data/splits'))):
        if name not in split_dataset:
            continue
        _train, test_ids_of_split = split_row_ids(name)
        if ROW_ID in test_ids_of_split:
            hits.append(name)
    entry['rowId73InTestOfSplits'] = hits

    # ---- measured consequence on the holdout metric ------------------------------------------------------
    predictions = pd.read_csv(abspath('experiments/%s/predictions.csv' % IMPACT_EXPERIMENT))
    truth_cols = [c for c in predictions.columns if c.startswith('y_true__')]
    pred_cols = [c.replace('y_true__', 'y_pred__') for c in truth_cols]
    per_row = np.abs(predictions[pred_cols].to_numpy() - predictions[truth_cols].to_numpy()).mean(axis=1)
    is_73 = predictions['row'].to_numpy() == ROW_ID
    entry['measuredImpact'] = {
        'experimentId': IMPACT_EXPERIMENT,
        'model': 'ridge-L2-multioutput',
        'nHoldoutRows': int(len(predictions)),
        'holdoutMeanMae': round(float(per_row.mean()), 6),
        'perRowMaeAtRow73': round(float(per_row[is_73][0]), 6),
        'meanMaeOverOtherHoldoutRows': round(float(per_row[~is_73].mean()), 6),
        'maxPerRowMaeOtherRows': round(float(per_row[~is_73].max()), 6),
        'predictionRangeOverall': [round(float(predictions[pred_cols].to_numpy().min()), 3),
                                   round(float(predictions[pred_cols].to_numpy().max()), 3)],
        'predictionRangeAtRow73': [round(float(predictions.loc[is_73, pred_cols].to_numpy().min()), 3),
                                   round(float(predictions.loc[is_73, pred_cols].to_numpy().max()), 3)],
        'truthRangeAtRow73': [round(float(predictions.loc[is_73, truth_cols].to_numpy().min()), 3),
                              round(float(predictions.loc[is_73, truth_cols].to_numpy().max()), 3)],
        'comparisonRunsWithoutRow73InTest': {
            eid: round(float(json.load(open(abspath('experiments/%s/metrics.json' % eid)))['holdout_mae_mean']), 6)
            for eid in COMPARISON_EXPERIMENTS
        },
        'statement': ('One single sample owns the whole blow-up: the linear Ridge extrapolates that row to the '
                      '[-123, 349] mapped-grade range while its true grades are 0.04-6, giving that row a per-row MAE '
                      'of 51.5 and lifting the 40-row holdout mean MAE from 0.691 (the other 39 rows) to 1.962. '
                      'The same model on splits where row 73 is not a test row lands at 0.61-0.76.'),
    }

    entry['policy'] = ('REGISTERED, NOT FIXED. No CSV value is altered, no row is dropped, no winsorising and no '
                       're-imputation is applied: the outlier is an original data fact and is reported as a data-quality '
                       'defect. Any robustness statement must therefore either (a) report metrics with and without this '
                       'row, or (b) use a non-linear / outlier-robust learner; silently trimming it would hide a real '
                       'property of the attachment.')
    entry['whereWritten'] = 'report/data-quality.md section 14 (and referenced from the Q1 limitations)'

    out = abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(entry, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    os.replace(tmp, out)

    emit({
        'ok': True,
        'outlier': {'column': COLUMN, 'rowId': ROW_ID, 'beer': entry['beer'], 'rawValue': entry['rawValue'],
                    'ratioToMedian': entry['ratioToMedian'], 'ratioToSecondLargest': entry['ratioToSecondLargest'],
                    'zUnderSplit0015Train': entry['standardisation']['zOfRow73ThisColumn'],
                    'maxAbsZTrain': entry['standardisation']['maxAbsZAnyColumnOnSameTrainRows']},
        'measuredImpact': {k: entry['measuredImpact'][k] for k in
                           ('holdoutMeanMae', 'perRowMaeAtRow73', 'meanMaeOverOtherHoldoutRows',
                            'predictionRangeOverall')},
        'valuesModifiedAnywhere': False,
        'audit': os.path.relpath(out, project_dir),
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
        die('00_prepare_outlier_audit.py crashed: %s: %s' % (type(exc).__name__, exc))
