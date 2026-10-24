"""Q3 实验入口：在**训练集内部 5 折 CV** 上评估指定生成模型族（A/B/C），供独立 EXP 登记/复跑。

用法（argv，无 shell 插值）：
    --family A --k 15
    --family B --latent 8 --beta 0.2
    --family C --k 10
    --seed 42 --n-gen 60

输出：`outputs/q3/exp_family_<family>_<cfg>.json`（含 5 折 CV 的命中率/ED 比/多样性/分风格明细），
stdout 末尾打印 `METRICS_JSON {...}` 一行，便于台账/复算脚本抓取。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import q3_utils as U  # noqa: E402
import q3_models as M  # noqa: E402

try:
    import emit as E
except Exception:  # noqa: BLE001
    E = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True, choices=["A", "B", "C"])
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--latent", type=int, default=8)
    ap.add_argument("--beta", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=U.SEED)
    ap.add_argument("--n-gen", type=int, default=60)
    ap.add_argument("--anchor", type=int, default=1)
    args = ap.parse_args()

    tab = U.load_style_table()
    split = U.load_split("primary")
    prep = U.fit_preprocessor(tab, split["train_beer"])
    Z = prep.transform(U.train_matrix(tab, split["train_beer"]))
    y = tab.set_index("beer").loc[split["train_beer"], "style"].values
    styles = sorted(set(tab["style"]))
    sid = M.style_id_map(styles)
    y_idx = np.array([sid[s] for s in y], dtype=int)
    sel = U.load_json("outputs/q3/model_selection.json")
    clf_name = sel["classifier_selected"]

    if args.family == "A":
        cfg = {"k": args.k, "anchor": bool(args.anchor)}
    elif args.family == "B":
        cfg = {"latent": args.latent, "beta": args.beta}
    else:
        cfg = {"k": 10}

    r = M.inner_cv_family(args.family, cfg, Z, y, y_idx, len(styles), clf_name,
                          seed=args.seed, n_gen=args.n_gen, style_ids=sid)
    out = {
        "family": r["family"], "config": cfg, "seed": args.seed,
        "split": U.split_meta(split),
        "evaluation": "training-only 5-fold stratified CV",
        "score": r["score"], "mean_hit_rate": r["mean_hit_rate"],
        "mean_ed_ratio": r["mean_ed_ratio"],
        "mean_diversity_ratio": r["mean_diversity_ratio"],
        "admissible": r.get("admissibility_rule") and r["mean_diversity_ratio"] >= M.DIVERSITY_FLOOR,
        "required_styles": r["required_styles"],
        "per_style": r["per_style"],
        "n_gen_per_style_per_fold": args.n_gen,
        "stochastic": True,
        "n_features": int(U.N_FEATURES),
    }
    tag = (f"A_k{args.k}_anchor{int(args.anchor)}" if args.family == "A" else
           f"B_lat{args.latent}_beta{args.beta}" if args.family == "B" else
           f"C_k{cfg['k']}")
    U.write_json(out, f"outputs/q3/exp_family_{tag}.json")
    print(json.dumps({k: out[k] for k in ("family", "config", "score", "mean_hit_rate",
                                          "mean_ed_ratio", "mean_diversity_ratio",
                                          "admissible")}, ensure_ascii=False))
    if E is not None:
        req = {r["style"]: r for r in out["required_styles"]}
        _m = {
            "ed_over_dref_tripel": req["Tripel"]["ed_ratio"] if "Tripel" in req else None,
            "r2": (1.0 - req["Tripel"]["ed_ratio"]) if "Tripel" in req else None,
            "r2_overall": (1.0 - req["Tripel"]["ed_ratio"]) if "Tripel" in req else None,
            "style_hit_macro": out["mean_hit_rate"],
            "style_hit_tripel": req["Tripel"]["hit_rate"] if "Tripel" in req else None,
            "gen_style_fidelity": out["mean_hit_rate"],
            "energy_distance_ratio": out["mean_ed_ratio"],
            "diversity_ratio": out["mean_diversity_ratio"],
            "selection_score": out["score"],
            "admissible": out["admissible"],
            "n_features": out["n_features"],
            "stochastic": True,
            "seed": args.seed,
        }
        E.emit_metrics({k: v for k, v in _m.items() if v is not None}, area="q3_exp")
        E.emit_output("cv_per_style", U.clean_json(out["per_style"]), area="q3_exp")
        E.emit_output("cv_required_styles", U.clean_json(out["required_styles"]), area="q3_exp")
        E.emit_output("experiment_config",
                      U.clean_json({k: v for k, v in out.items()
                                    if k not in ("per_style", "required_styles")}),
                      area="q3_exp")
    print("METRICS_JSON " + json.dumps({
        "gen_style_fidelity": out["mean_hit_rate"],
        "energy_distance_ratio": out["mean_ed_ratio"],
        "diversity_ratio": out["mean_diversity_ratio"],
        "selection_score": out["score"],
        "n_features": out["n_features"],
        "stochastic": True,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
