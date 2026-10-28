# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""r00_build_splits.py — build the immutable nested-CV split manifest (R00).

THE PROTOCOL (frozen before any candidate is compared; declared in contest.yaml
evaluation.tuning and rebuilt here as a data artifact):

    repeats   = 3      seeds = 20261025, 20261026, 20261027
    outer     = 3      stratified by tasting_category_fine, round-robin with a
                       rotated start per repeat so fold sizes stay balanced
    inner     = 3      inside every outer TRAINING set, own seed (seed, fold),
                       same stratification

WHY NOT register-split: the plugin's split plane only knows random-holdout and
time-holdout. A nested CV is not a holdout, so it is registered as an immutable
*protocol artifact* (this CSV + manifest), not as a fake split.

Rows in splits.csv (one per beer x repeat x outer_fold):
    beer, repeat, outer_fold, inner_fold, role, style
    role = "outer_test"  -> this beer is held out for this outer fold (inner_fold = -1)
    role = "inner"       -> the beer belongs to inner fold `inner_fold` of the outer
                            TRAINING set; for inner iteration j, valid = (inner_fold == j)

Usage: python src/r00_build_splits.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v6_common as C  # noqa: E402


def round_robin(beers, n_folds, rng, offset):
    """Stratified round-robin inside one style: shuffle, then deal with a rotated start."""
    beers = list(beers)
    order = rng.permutation(len(beers))
    out = {}
    for rank, pos in enumerate(order):
        out[beers[pos]] = int((rank + offset) % n_folds)
    return out


def build():
    frame = C.load_frame(C.DATA_Q1)
    frame["beer"] = frame["beer"].astype(int)
    frame["style"] = frame[C.STYLE_COL].astype(str)
    beers = frame["beer"].to_numpy()
    style_of_beer = dict(zip(beers, frame["style"]))
    if len(set(beers)) != 250:
        raise RuntimeError("expected 250 unique beers")

    rows = []
    for repeat, seed in enumerate(C.SEEDS):
        rng_outer = np.random.default_rng(seed)
        outer = {}
        for style in sorted(set(style_of_beer.values())):
            members = sorted(b for b, s in style_of_beer.items() if s == style)
            outer.update(round_robin(members, C.N_OUTER, rng_outer, repeat))
        for fold in range(C.N_OUTER):
            rng_inner = np.random.default_rng([seed, fold])
            train = sorted(b for b, f in outer.items() if f != fold)
            test = sorted(b for b, f in outer.items() if f == fold)
            inner = {}
            for style in sorted(set(style_of_beer.values())):
                members = sorted(b for b in train if style_of_beer[b] == style)
                if members:
                    inner.update(round_robin(members, C.N_INNER, rng_inner, fold))
            for beer in sorted(beers):
                if beer in test:
                    rows.append({"beer": int(beer), "repeat": repeat, "outer_fold": fold,
                                 "inner_fold": -1, "role": "outer_test",
                                 "style": style_of_beer[beer]})
                else:
                    rows.append({"beer": int(beer), "repeat": repeat, "outer_fold": fold,
                                 "inner_fold": int(inner[beer]), "role": "inner",
                                 "style": style_of_beer[beer]})

    table = pd.DataFrame(rows)[["beer", "repeat", "outer_fold", "inner_fold", "role", "style"]]
    table = table.sort_values(["repeat", "outer_fold", "beer"]).reset_index(drop=True)

    # ---- invariants (a violated invariant is a named failure, never a silent pass)
    checks = {}
    for repeat in range(C.N_REPEATS):
        for fold in range(C.N_OUTER):
            part = table[(table["repeat"] == repeat) & (table["outer_fold"] == fold)]
            train = set(part.loc[part["role"] == "inner", "beer"])
            test = set(part.loc[part["role"] == "outer_test", "beer"])
            if train & test:
                raise RuntimeError(f"overlap repeat={repeat} fold={fold}")
            if train | test != set(beers):
                raise RuntimeError(f"fold does not partition the sample repeat={repeat} fold={fold}")
            for inner in range(C.N_INNER):
                valid = set(part.loc[part["inner_fold"] == inner, "beer"])
                rest = train - valid
                if valid & rest or valid | rest != train:
                    raise RuntimeError(f"inner fold does not partition outer train repeat={repeat} fold={fold} inner={inner}")
            checks[f"r{repeat}f{fold}"] = {
                "n_train": len(train), "n_test": len(test),
                "styles_train": len({style_of_beer[b] for b in train}),
                "styles_test": len({style_of_beer[b] for b in test}),
            }

    # ---- per-style counts (small styles are reported, never padded)
    style_counts = {}
    for style in sorted(set(style_of_beer.values())):
        members = [b for b, s in style_of_beer.items() if s == style]
        per_outer = []
        for fold in range(C.N_OUTER):
            hit = table[(table["repeat"] == 0) & (table["outer_fold"] == fold) &
                        (table["role"] == "outer_test") & (table["style"] == style)]
            per_outer.append(int(len(hit)))
        style_counts[style] = {"n": len(members), "outer_test_counts": per_outer}

    C.SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(C.SPLITS_CSV, index=False)
    manifest = {
        "kind": "nested-cv-manifest",
        "purpose": "frozen internal re-validation protocol for the R00-R03 rerun; NOT an external test set",
        "seeds": list(C.SEEDS),
        "repeats": C.N_REPEATS, "outer_folds": C.N_OUTER, "inner_folds": C.N_INNER,
        "stratify": C.STYLE_COL,
        "assignment": "per-style shuffled round-robin, start rotated by repeat (outer) / fold (inner)",
        "splits_csv": str(C.SPLITS_CSV.relative_to(C.PROJECT)),
        "splits_sha256": C.sha256_file(C.SPLITS_CSV),
        "source_data": str(C.DATA_Q1.relative_to(C.PROJECT)),
        "source_sha256": C.sha256_file(C.DATA_Q1),
        "n_rows": int(len(table)),
        "fold_checks": checks,
        "style_counts": style_counts,
        "notes": [
            "role=inner means: inside this outer fold's TRAINING set the beer sits in inner fold `inner_fold`",
            "for inner iteration j: valid = (inner_fold == j), train = the other inner folds",
            "outer_test rows are never used for fitting, tuning or calibration",
            "Faro (n=3) has 2 outer-training rows, so some inner folds hold 0 rows of that style; this is recorded, not padded",
        ],
    }
    C.write_json(C.SPLITS_MANIFEST, manifest)
    print(f"wrote {C.SPLITS_CSV.relative_to(C.PROJECT)} rows={len(table)} sha256={manifest['splits_sha256'][:16]}")
    print(f"wrote {C.SPLITS_MANIFEST.relative_to(C.PROJECT)}")
    print("style counts:", {k: v["n"] for k, v in sorted(style_counts.items())})
    return manifest


if __name__ == "__main__":
    build()
