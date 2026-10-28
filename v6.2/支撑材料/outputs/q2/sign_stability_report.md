# Q2 direction stability (v6 §3)

- zero tolerance: **1e-12** (pre-declared; |rho| <= tolerance is `zero`)
- reference direction: point-estimate total Spearman on the 200 SPLIT-0001 train rows
- sign_stability: replicates agreeing with the reference direction / valid (valid = reps - n_invalid); p_positive = n_positive/valid; p_negative = n_negative/valid
- a zero or non-computable point estimate is `direction-undetermined`, never negative
- p_positive_legacy keeps the superseded (rho > 0)/reps rule; it does not enter the ranking

## repeat 0 (seed 20261025, reps 500)

- direction counts (150 delivered consensus rows): {'positive': 114, 'negative': 36, 'direction-undetermined': 0}
- evidence status counts: {'stable': 55, 'sign-mixed': 0, 'low-pi': 95, 'low-pi+sign-mixed': 0, 'direction-undetermined': 0}
- replicate counts over those rows: {'n_positive': 57006, 'n_negative': 17994, 'n_zero': 0, 'n_invalid': 0}
- mean sign_stability (new): 0.981980; mean p_positive_legacy (old): 0.720313
- rows with pi < 0.5: 95; status {'low-pi': 95}; direction {'negative': 29, 'positive': 66}
- legacy reproduction: rows compared 150, compound mismatches 0, pi exact 150 (max |diff| 0.0), old sign_stability exact 150 (max |diff| 0.0), passed=True
- negative-direction rows re-derived: 36, legacy in [0, 0.022] = 36, exactly zero = 27
- v6 reference claim (36 rows / 27 zeros) reproduced = True (the v6 note quotes the primary repeat (seed 20261025); this repeat is it)

## repeat 1 (seed 20261026, reps 500)

- direction counts (150 delivered consensus rows): {'positive': 111, 'negative': 39, 'direction-undetermined': 0}
- evidence status counts: {'stable': 57, 'sign-mixed': 0, 'low-pi': 93, 'low-pi+sign-mixed': 0, 'direction-undetermined': 0}
- replicate counts over those rows: {'n_positive': 55504, 'n_negative': 19496, 'n_zero': 0, 'n_invalid': 0}
- mean sign_stability (new): 0.982197; mean p_positive_legacy (old): 0.724657
- rows with pi < 0.5: 93; status {'low-pi': 93}; direction {'negative': 31, 'positive': 62}
- legacy reproduction: rows compared 150, compound mismatches 0, pi exact 150 (max |diff| 0.0), old sign_stability exact 150 (max |diff| 0.0), passed=True
- negative-direction rows re-derived: 39, legacy in [0, 0.022] = 39, exactly zero = 34
- v6 reference claim (36 rows / 27 zeros): not applicable: the v6 note's 36 / 27 counts quote the primary repeat only; this repeat is a different seed block, reported here for completeness

## repeat 2 (seed 20261027, reps 500)

- direction counts (150 delivered consensus rows): {'positive': 111, 'negative': 39, 'direction-undetermined': 0}
- evidence status counts: {'stable': 55, 'sign-mixed': 0, 'low-pi': 94, 'low-pi+sign-mixed': 1, 'direction-undetermined': 0}
- replicate counts over those rows: {'n_positive': 55450, 'n_negative': 19550, 'n_zero': 0, 'n_invalid': 0}
- mean sign_stability (new): 0.980887; mean p_positive_legacy (old): 0.722693
- rows with pi < 0.5: 95; status {'low-pi': 94, 'low-pi+sign-mixed': 1}; direction {'negative': 33, 'positive': 62}
- legacy reproduction: rows compared 150, compound mismatches 0, pi exact 150 (max |diff| 0.0), old sign_stability exact 150 (max |diff| 0.0), passed=True
- negative-direction rows re-derived: 39, legacy in [0, 0.022] = 39, exactly zero = 31
- v6 reference claim (36 rows / 27 zeros): not applicable: the v6 note's 36 / 27 counts quote the primary repeat only; this repeat is a different seed block, reported here for completeness

## definition self-test (hand-built vectors, run before any replicate)

- zero tolerance 1e-12, checks passed = True

| case | point | n_pos | n_neg | n_zero | n_invalid | valid | p_positive | p_negative | p_positive_legacy | sign_stability | direction_status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| stable-positive | 0.420 | 20 | 0 | 0 | 0 | 20 | 1.000 | 0.000 | 1.000 | 1.000 | positive |
| stable-negative | -0.420 | 0 | 20 | 0 | 0 | 20 | 0.000 | 1.000 | 0.000 | 1.000 | negative |
| alternating-signs | 0.050 | 10 | 10 | 0 | 0 | 20 | 0.500 | 0.500 | 0.500 | 0.500 | positive |
| all-zero | 0.000 | 0 | 0 | 20 | 0 | 20 | 0.000 | 0.000 | 0.000 | 0.000 | direction-undetermined |
| all-invalid | nan | 0 | 0 | 0 | 20 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | direction-undetermined |
| near-zero-tolerance | 0.000 | 0 | 0 | 20 | 0 | 20 | 0.000 | 0.000 | 0.500 | 0.000 | direction-undetermined |

checks: stable-positive.sign_stability==1=ok; stable-negative.sign_stability==1=ok; stable-negative.legacy==0 (the superseded bug)=ok; alternating.sign_stability==0.5=ok; all-zero.status==direction-undetermined=ok; all-zero.n_zero==reps=ok; all-zero.sign_stability==0=ok; all-invalid.n_invalid==reps and valid==0=ok; all-invalid.status==direction-undetermined=ok; near-zero.all_bucketed_as_zero=ok; alternating.p_positive==p_negative==0.5=ok

## delivered files

- strict_top3.csv / strict_top3.md, strict_top3_by_method.csv
- extended_top3.csv, extended_top3_by_method.csv
- sign_counts.csv (231 x 50 cells with counts and ratios)
- strict_lowpi_sign_status.csv / .md (every pi < 0.5 row with status and substitutes)
- sign_stability_summary.json (definition, tolerance, seeds, denominators, legacy check)
