#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""00_prepare_pools.py — build three UNEXPOSED evaluation pools (row subsets, nothing recomputed).

Why this exists. The deployed pack counts, per actual sample row (a content hash over the whole row), how often the
row has already been used as a TEST row, and refuses a new run once that count reaches quality.robustness.
maxHoldoutReuse (3). The main splits already spent that budget: SPLIT-0001/0002/0003 test rows are at the limit, and
the seed-20261025/20261026 re-splits reuse 9-12 of those rows. A robustness experiment therefore needs a test pool
built ONLY from rows that were NEVER in a main test set.

What this script does:
  q1_pool.csv = the 200 rows of q1_mapped.csv that are NOT in SPLIT-0001's test set
  q2_pool.csv = the 200 rows of q2_raw.csv   that are NOT in SPLIT-0002's test set
  q3_pool.csv = the 200 rows of q3_table.csv that are NOT in SPLIT-0003's test set

Hard guarantees enforced here (assertions, not intentions):
  · it is a ROW SUBSET only: the column list is byte-identical to the parent, every value is carried over unchanged,
    and in particular the Q1 mapped grade is NOT recomputed (no new zmin/zmax — that would silently redefine labels);
  · the `row` column keeps the ORIGINAL 0-based ids (not renumbered), and the row order is the parent file order, so
    every pool row is traceable to the main dataset and the two pools/splits can be compared by `row`;
  · the retained `row` set is EXACTLY parent-rows minus main-split-test-rows (set equality, reported per pool);
  · the written CSV is read back and compared value-by-value against the parent rows (bit-identical check);
  · the three field lists are the parent field lists with the `row` description replaced (the columns are unchanged,
    so the remaining descriptions are still true) and an explicit "row subset of DATA-xxxx" statement.

Outputs (declared to run-script): the three pool CSVs, the three pool field lists, and pools_quality.json, which records
every assertion above plus the style-holdout composition of q3_pool (Q3 robustness still fits on style_holdout, so the
held-out styles must not be emptied by the subsetting).
"""

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

PRECISION = 12
FLOAT_NOISE = 1e-12

POOLS = [
    # (pool name, parent dataset id, parent csv, main split id, parent field list, pool field list, note)
    ('q1_pool', 'DATA-0001', 'data/processed/q1_mapped.csv', 'SPLIT-0001',
     'data/fieldlists/q1_mapped_fields.json', 'data/fieldlists/q1_pool_fields.json', 'Q1'),
    ('q2_pool', 'DATA-0002', 'data/processed/q2_raw.csv', 'SPLIT-0002',
     'data/fieldlists/q2_raw_fields.json', 'data/fieldlists/q2_pool_fields.json', 'Q2'),
    ('q3_pool', 'DATA-0003', 'data/processed/q3_table.csv', 'SPLIT-0003',
     'data/fieldlists/q3_table_fields.json', 'data/fieldlists/q3_pool_fields.json', 'Q3'),
]


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


def main(argv=None):
    starter = os.environ.get('MODELING_PROJECT_DIR') or os.getcwd()
    ap = argparse.ArgumentParser(description='build unexposed evaluation pools as row subsets of the main datasets')
    ap.add_argument('--project-dir', default=starter)
    ap.add_argument('--out-q1', default='data/processed/q1_pool.csv')
    ap.add_argument('--out-q2', default='data/processed/q2_pool.csv')
    ap.add_argument('--out-q3', default='data/processed/q3_pool.csv')
    ap.add_argument('--out-fields-q1', default='data/fieldlists/q1_pool_fields.json')
    ap.add_argument('--out-fields-q2', default='data/fieldlists/q2_pool_fields.json')
    ap.add_argument('--out-fields-q3', default='data/fieldlists/q3_pool_fields.json')
    ap.add_argument('--out-quality', default='data/processed/pools_quality.json')
    args = ap.parse_args(argv)

    project_dir = os.path.abspath(args.project_dir)
    abspath = lambda p: p if os.path.isabs(p) else os.path.join(project_dir, p)  # noqa: E731
    out_csv = {'q1_pool': abspath(args.out_q1), 'q2_pool': abspath(args.out_q2), 'q3_pool': abspath(args.out_q3)}
    out_fields = {'q1_pool': abspath(args.out_fields_q1), 'q2_pool': abspath(args.out_fields_q2),
                  'q3_pool': abspath(args.out_fields_q3)}

    report = {'schemaVersion': 1, 'pools': {}, 'checks': {}}
    for name, parent_id, parent_rel, split_id, fields_rel, _ignored, question in POOLS:
        parent_path = abspath(parent_rel)
        split_path = abspath('data/splits/%s/assignment.csv' % split_id)
        for path in (parent_path, split_path, abspath(fields_rel)):
            if not os.path.exists(path):
                die('%s: required input does not exist: %s' % (name, path))

        parent = pd.read_csv(parent_path)
        assignment = pd.read_csv(split_path)
        if list(assignment.columns) != ['row_index', 'split']:
            die('%s: %s assignment header is not row_index,split' % (name, split_id))
        if len(parent) != 250:
            die('%s: the parent dataset has %d rows, expected 250' % (name, len(parent)))

        # row_index in assignment.csv is the POSITIONAL index inside the parent file; the `row` column holds the
        # original sample id. They coincide today (row == 0..249), but we map through both so the intent is explicit.
        test_positions = sorted(assignment.loc[assignment['split'] == 'test', 'row_index'].astype(int).tolist())
        train_positions = sorted(assignment.loc[assignment['split'] == 'train', 'row_index'].astype(int).tolist())
        if len(test_positions) != 50 or len(train_positions) != 200:
            die('%s: %s has %d test / %d train rows, expected 50/200'
                % (name, split_id, len(test_positions), len(train_positions)))
        if set(test_positions) & set(train_positions) or len(test_positions) + len(train_positions) != 250:
            die('%s: %s is not a partition of the 250 rows' % (name, split_id))

        parent_rows = parent['row'].astype(int).tolist()
        test_row_ids = [parent_rows[i] for i in test_positions]
        train_row_ids = [parent_rows[i] for i in train_positions]

        # the pool = the parent rows in TRAIN positions, in parent file order -> EXACTLY parent rows minus test rows
        keep_mask = np.zeros(len(parent), dtype=bool)
        keep_mask[train_positions] = True
        pool = parent.loc[keep_mask].reset_index(drop=True)

        expected_row_set = set(parent_rows) - set(test_row_ids)
        got_row_set = set(pool['row'].astype(int).tolist())
        if got_row_set != expected_row_set:
            die('%s: the pool row set is not parent-minus-test (missing %r, extra %r)'
                % (name, sorted(expected_row_set - got_row_set)[:5], sorted(got_row_set - expected_row_set)[:5]))
        if len(pool) != 200:
            die('%s: the pool has %d rows, expected 200' % (name, len(pool)))
        if list(pool.columns) != list(parent.columns):
            die('%s: the pool column list differs from the parent' % name)
        if pool['row'].astype(int).tolist() != train_row_ids:
            die('%s: the pool lost the parent row order' % name)
        if list(pool['row'].astype(int)) != sorted(pool['row'].astype(int).tolist()):
            die('%s: the pool row ids are not in ascending order' % name)

        write_csv(pool, out_csv[name])

        # ---- read the written file back and prove it is the parent rows, value for value --------------------
        written = pd.read_csv(out_csv[name])
        if list(written.columns) != list(parent.columns):
            die('%s: the written pool header changed' % name)
        parent_indexed = parent.set_index(parent['row'].astype(int))
        written_indexed = written.set_index(written['row'].astype(int))
        if list(written_indexed.index) != list(parent_indexed.loc[written_indexed.index].index):
            die('%s: row alignment during the round-trip check failed' % name)
        reference = parent_indexed.loc[written_indexed.index]
        per_column_max_diff = {}
        max_abs_diff = 0.0
        for col in parent.columns:
            a = reference[col].to_numpy()
            b = written[col].to_numpy()
            if a.dtype.kind in 'if' and b.dtype.kind in 'if':
                diff = float(np.nanmax(np.abs(a.astype(float) - b.astype(float)))) if len(a) else 0.0
                per_column_max_diff[col] = diff
                max_abs_diff = max(max_abs_diff, diff)
                if diff > FLOAT_NOISE:
                    die('%s: column %r changed value in the pool (max|diff| = %.12g)' % (name, col, diff))
            else:
                if [str(x) for x in a] != [str(x) for x in b]:
                    die('%s: text column %r changed value in the pool' % (name, col))
        if max_abs_diff > FLOAT_NOISE:
            die('%s: numeric drift %g' % (name, max_abs_diff))

        entry = {
            'poolFile': file_info(out_csv[name], project_dir),
            'parentDatasetId': parent_id,
            'parentFile': file_info(parent_path, project_dir),
            'mainSplitId': split_id,
            'mainSplitAssignment': file_info(split_path, project_dir),
            'rows': int(len(pool)),
            'columns': int(pool.shape[1]),
            'rowSetEqualsParentMinusMainTest': bool(got_row_set == expected_row_set),
            'nParentRows': int(len(parent)),
            'nMainTestRows': int(len(test_positions)),
            'nMainTrainRows': int(len(train_positions)),
            'rowIdsOriginalNotRenumbered': True,
            'rowIdsAscending': True,
            'rowIdsMin': int(pool['row'].min()),
            'rowIdsMax': int(pool['row'].max()),
            'mainTestRowIds': test_row_ids,
            'columnListIdenticalToParent': True,
            'maxAbsDiffVersusParentRows': max_abs_diff,
            'metricCheckedColumns': [c for c in parent.columns
                                     if parent[c].dtype.kind in 'if' and c != 'row'],
            'subsetOnlyNoRecomputation': True,
        }

        if question == 'Q1':
            target_cols = [c for c in parent.columns if c not in
                           ('row', 'beer', 'beer_id', 'tasting_category_fine') and not c.startswith('chem__')]
            diffs = {c: per_column_max_diff.get(c, None) for c in target_cols}
            worst = max((v for v in diffs.values() if v is not None), default=0.0)
            entry['q1TargetColumns'] = len(target_cols)
            entry['q1TargetMaxAbsDiffVersusParent'] = worst
            entry['q1TargetAllBitIdentical'] = bool(worst == 0.0)
            entry['q1MappedGradeNotRecomputed'] = (
                'the 50 target columns are copied byte-for-byte from q1_mapped.csv: no zmin/zmax is re-estimated for '
                'the pool. Consequence to state honestly: these 200 rows ARE the rows that fitted the main affine '
                'map, so every pool row participated in the rescaling (that is the weak, 2-scalars-per-target leakage;'
                ' it is not per-sample information).')
            if worst != 0.0:
                die('Q1 pool changed a mapped-grade value (max|diff| = %g)' % worst)
        if question == 'Q3':
            style_counts = {str(k): int(v) for k, v in pool['style'].value_counts().items()}
            holdout_counts = {str(k): int(v) for k, v in pool['style_holdout'].value_counts().items()}
            entry['styleHoldoutCounts'] = holdout_counts
            entry['heldoutStyleCounts'] = {s: int(style_counts.get(s, 0)) for s in ('Tripel', 'Kriek', 'Lambic')}
            entry['nDistinctStyles'] = int(pool['style'].nunique())
            if entry['heldoutStyleCounts'].get('Tripel', 0) == 0:
                die('q3_pool lost the held-out style Tripel: Q3 robustness could not fit on style_holdout')
            thr_cols = [c for c in pool.columns if c.startswith('thr__')]
            entry['thresholdColumns'] = len(thr_cols)
            entry['thresholdColumnsConstant'] = bool(all(pool[c].nunique() == 1 for c in thr_cols))

        report['pools'][name] = entry

        # ---- field list: the parent's, with the `row` description replaced ----------------------------------
        with open(abspath(fields_rel), 'r', encoding='utf-8') as fh:
            parent_fields = json.load(fh)
        fields = []
        for field in parent_fields:
            if field['name'] == 'row':
                fields.append({
                    'name': 'row',
                    'type': 'integer',
                    'unit': None,
                    'description': ('ORIGINAL 0-based row position in 1.csv/4.csv — NOT renumbered: this pool is a row '
                                    'subset of %s kept in parent file order, so `row` is still the id of the same beer '
                                    'sample in the parent dataset. The gaps are the rows used as the main split %s '
                                    'test set (%d of 250); %d rows are kept.'
                                    % (parent_id, split_id, len(test_positions), len(pool))),
                })
            else:
                fields.append(field)
        write_json(out_fields[name], fields)
        entry['fieldList'] = file_info(out_fields[name], project_dir)
        entry['fieldListColumns'] = int(len(fields))
        if [f['name'] for f in fields] != list(pool.columns):
            die('%s: the pool field list does not match the pool header' % name)

    # ---- cross-pool facts the eval plan depends on ---------------------------------------------------------
    q1 = report['pools']['q1_pool']
    report['checks'] = {
        'allPoolsHave200Rows': all(v['rows'] == 200 for v in report['pools'].values()),
        'allRowSetsEqualParentMinusMainTest': all(v['rowSetEqualsParentMinusMainTest'] for v in report['pools'].values()),
        'noValueChangedAnywhere': all(v['maxAbsDiffVersusParentRows'] <= FLOAT_NOISE for v in report['pools'].values()),
        'q1TargetsBitIdentical': report['pools']['q1_pool']['q1TargetAllBitIdentical'],
        'q3HeldoutStylesSurvive': report['pools']['q3_pool']['heldoutStyleCounts'],
        'note': ('The three pools are ROW SUBSETS of the main datasets. They carry no new information and no new '
                 'labels: they exist so that a robustness experiment can put its TEST rows on samples that were never '
                 'in a main test set, without re-using the main holdout. Their `row` values still identify the original '
                 'beer, so any pool split can be compared row-by-row with the main split.'),
    }
    report['inputsParentDatasets'] = {v['parentDatasetId']: v['parentFile'] for v in report['pools'].values()}
    write_json(abspath(args.out_quality), report)

    emit({
        'ok': True,
        'pools': {k: {'path': v['poolFile']['path'], 'rows': v['rows'], 'columns': v['columns'],
                      'sha256': v['poolFile']['sha256']} for k, v in report['pools'].items()},
        'rowSetEqualsParentMinusMainTest': report['checks']['allRowSetsEqualParentMinusMainTest'],
        'q1TargetsBitIdentical': report['checks']['q1TargetsBitIdentical'],
        'q3HeldoutStyles': report['checks']['q3HeldoutStylesSurvive'],
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
        die('00_prepare_pools.py crashed: %s: %s' % (type(exc).__name__, exc))
