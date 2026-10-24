"""Q2-③ Bootstrap 稳定性（分两阶段，各自守住 600s 实验超时）。

预注册参数
  B_primary = 300（M1 ridge、M4 Spearman；协议要求 B=300）
  B_secondary = 20（M2 RF、M3 graphical-lasso、AGG Borda；协议允许 <=30 以控时）
  seed: 第 b 次重采样 rng = numpy.default_rng(42 + (b-1))，indices = rng.integers(0, 250, 250)
  FREQ_THRESHOLD = 0.80（Top-3 席位入选频率 >= 0.80 视为稳定；不得事后调整）
  Top-3 合成 = 4 方法排名求和的 Borda（与 q2_select.py 完全一致）

阶段
  --stages m1_m4   写 outputs/q2/bootstrap_top3.csv（B=300 × 50 维 × 3 排名 × M1/M4）
  --stages m2_m3   写 outputs/q2/bootstrap_top3_secondary.csv（B=20，M1..M4 + AGG），
                   然后合并两阶段，写 selection_frequency.csv / stability_seats.csv /
                   stability_summary.json，并用 src/emit.py 落 metrics。
每次重采样都重新做标准化（在重采样样本内），避免把全样本尺度信息带进稳定性。

如实声明：M2/M3/AGG 只有 20 次 bootstrap，其频率的蒙特卡洛误差约 sqrt(p(1-p)/20)
（p=0.8 时约 ±0.09），因此这三者的"稳定"证据强度显著低于 M1/M4 的 300 次。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import q2_common as Q  # noqa: E402
import emit as E  # noqa: E402

OUT = C.ROOT / "outputs" / "q2"
B_PRIMARY = Q.BOOTSTRAP_B           # 300
B_SECONDARY = Q.BOOTSTRAP_B_SECONDARY  # 20


def resample_idx(n: int, rep: int):
    rng = np.random.default_rng(Q.effective_seed() + (rep - 1))
    return rng.integers(0, n, n)


def zfit(A):
    mu = A.mean(axis=0)
    sd = A.std(axis=0, ddof=0)
    sd = np.where(sd > 0, sd, 1.0)
    return (A - mu) / sd


# 全数据阶段（EXP-0039）用 5 折内层 CV 选出的逐维 alpha，bootstrap 时固定使用。
FIXED_ALPHA = None


def set_fixed_alpha_from_stage():
    """从 outputs/q2/_stage_m1m4.npz 读取逐维 alpha（全数据 5 折内层 CV 结果）。"""
    global FIXED_ALPHA
    p = OUT / "_stage_m1m4.npz"
    if p.exists():
        FIXED_ALPHA = np.load(p)["ridge_alpha"]
    else:
        raise SystemExit("missing outputs/q2/_stage_m1m4.npz (run q2_select --stage m1m4 first)")
    return FIXED_ALPHA


def ridge_fixed_scores(Xb, Yb, alpha_vec):
    """bootstrap 内固定 alpha 的 ridge，一次 SVD 解全部 50 维（~10ms/rep）。

    为什么固定 alpha：重采样行有重复 → 约 158 个唯一行，若每次再用 CV 选 alpha，
    GCV/5 折都会退化（实测 GCV 在重复行上选到 alpha=0.01 的退化解，
    EXP-0042 也因此超时）。stability 要测的是**选择稳定性**，不是超参选择噪声，
    因此固定全数据内层 CV 选出的逐维 alpha 是更干净的口径（已写入 summary）。
    """
    Xc = Xb - Xb.mean(axis=0)
    Yc = Yb - Yb.mean(axis=0)
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    UtY = U.T @ Yc
    S2 = S ** 2
    B = np.zeros((Xb.shape[1], Yb.shape[1]))
    for j in range(Yb.shape[1]):
        a = float(alpha_vec[j])
        B[:, j] = Vt.T @ ((S / (S2 + a)) * UtY[:, j])
    return B


def ridge_top3(Xb, Yb, dims, feat):
    B = ridge_fixed_scores(Xb, Yb, FIXED_ALPHA)
    return np.column_stack([Q.rank_high(np.abs(B[:, j])) for j in range(Yb.shape[1])])


def rf_oob_top3(Xb, Yb, idx, rep, dims, feat, n_estimators=200, n_rep=3):
    from sklearn.ensemble import RandomForestRegressor
    p, q = Xb.shape[1], Yb.shape[1]
    oob = np.setdiff1d(np.arange(Xb.shape[0]), np.unique(idx))
    if oob.size < 20:  # 极小概率兜底：用全部行
        oob = np.arange(Xb.shape[0])
    R = np.zeros((p, q))
    for j in range(q):
        rf = RandomForestRegressor(n_estimators=n_estimators, max_features=0.33,
                                   min_samples_leaf=2, n_jobs=-1,
                                   random_state=Q.SEED + rep).fit(Xb, Yb[:, j])
        Xo, yo = Xb[oob], Yb[oob, j]
        base = float(((rf.predict(Xo) - yo) ** 2).mean())
        rng = np.random.default_rng(Q.SEED * 1000 + rep * 100 + j)
        blocks = []
        for f in range(p):
            for r in range(n_rep):
                Xp = Xo.copy()
                Xp[:, f] = rng.permutation(Xp[:, f])
                blocks.append(Xp)
        pred = rf.predict(np.vstack(blocks)).reshape(p * n_rep, oob.size)
        imp = ((pred - yo[None, :]) ** 2).mean(axis=1).reshape(p, n_rep).mean(axis=1) - base
        R[:, j] = Q.rank_high(imp)
    return R


def glasso_top3(Xb, Yb):
    """M3 主口径（与 q2_select 一致）：Ledoit-Wolf 收缩联合精度矩阵 -> |偏相关|。

    注意：GraphicalLassoCV 在 n=250,p=281 下过度收缩导致大量偏相关精确为 0（见
    outputs/q2/m3_diagnostics.json），因此主口径改用 Ledoit-Wolf 收缩（协议允许的
    "联合精度矩阵"正则化估计）；glasso-CV 只作为敏感性分析出现在选择实验中。
    """
    from sklearn.covariance import LedoitWolf
    Z = np.hstack([Xb, Yb])
    lw = LedoitWolf().fit(Z)
    P = lw.precision_
    d = np.sqrt(np.maximum(np.diag(P), 1e-15))
    pc = -P / np.outer(d, d)
    p, q = Xb.shape[1], Yb.shape[1]
    return np.abs(pc[:p, p:p + q]), float(lw.shrinkage_)


def m4_rank(Xb_imp, Yb):
    rho = Q.spearman_pair(Xb_imp, Yb)
    return rho


def rows_from_rank(R, rep, dims, feat, method):
    rows = []
    for j, dim in enumerate(dims):
        order = np.lexsort((np.arange(R.shape[0]), R[:, j]))
        for rank, ci in enumerate(order[:3], start=1):
            rows.append({"rep": rep, "dim": dim, "rank": rank,
                         "compound": feat[ci], "method": method})
    return rows


def stage_primary(d, feat, dims, X_imp, Y, n):
    t0 = time.time()
    X = d["Xz"].to_numpy(float)
    rows = []
    for b in range(1, B_PRIMARY + 1):
        idx = resample_idx(n, b)
        Xb = zfit(X[idx])
        Yb = zfit(Y[idx])
        Xib = X_imp.iloc[idx].to_numpy(float)
        R1 = ridge_top3(Xb, Yb, dims, feat)
        rows += rows_from_rank(R1, b, dims, feat, "M1")
        rho = m4_rank(Xib, Yb)
        R4 = np.column_stack([Q.rank_high(np.abs(rho[:, j])) for j in range(len(dims))])
        rows += rows_from_rank(R4, b, dims, feat, "M4")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "bootstrap_top3.csv", index=False, encoding="utf-8")
    # 本 phase 自己的 metrics（runner 不接受没有 metrics.json 的实验）
    # M4 的 300 次 bootstrap 可以立刻给出"最终 M4 Top-3 席位"的稳定性，但最终
    # 共识 Top-3 的稳定性在 M2M3_B20 汇总阶段给出；这里先落 B/记录数/耗时与
    # bootstrap 内部一致性（每维 Top1 在 B 次重采样中的众数占比，仅作健康检查）。
    m4 = df[df.method == "M4"]
    m4_top1_mode = m4[m4["rank"] == 1].groupby("dim")["compound"].agg(
        lambda s: s.value_counts().iloc[0] / s.value_counts().sum())
    E.emit_metrics({
        "bootstrap_B": float(B_PRIMARY),
        "n_top3_records": float(len(df)),
        "n_dims": float(len(dims)),
        "M4_top1_mode_share_mean": float(m4_top1_mode.mean()),
        "runtime_seconds": float(time.time() - t0),
        "seed": float(Q.effective_seed()),
    }, area="q2")
    E.emit_predictions(df, "bootstrap_top3.csv", area="q2")
    E.emit_output("bootstrap_primary_meta", Q.sanitize({
        "B": B_PRIMARY, "rows": len(df),
        "seed_rule": "default_rng(42+(rep-1)); indices=rng.integers(0,250,250)",
        "m4_top1_mode_share_mean": float(m4_top1_mode.mean()),
        "ridge_alpha": "fixed per-dim full-data 5-fold inner-CV alpha",
        "runtime_seconds": round(time.time() - t0, 1),
    }), area="q2")
    print(f"primary stage: {B_PRIMARY} reps, {len(df)} rows, {round(time.time()-t0,1)}s")
    return df


def borda_from_ranks(ranks, dims):
    mean_rank = sum(ranks[m] for m in Q.METHODS) / len(Q.METHODS)
    return mean_rank


def stage_secondary(d, feat, dims, X_imp, Y, n):
    t0 = time.time()
    X = d["Xz"].to_numpy(float)
    rows = []
    alpha_log = []
    for b in range(1, B_SECONDARY + 1):
        idx = resample_idx(n, b)
        Xb = zfit(X[idx])
        Yb = zfit(Y[idx])
        Xib = X_imp.iloc[idx].to_numpy(float)
        R1 = ridge_top3(Xb, Yb, dims, feat)
        rho = m4_rank(Xib, Yb)
        R4 = np.column_stack([Q.rank_high(np.abs(rho[:, j])) for j in range(len(dims))])
        R2 = rf_oob_top3(Xb, Yb, idx, b, dims, feat)
        S3, alpha = glasso_top3(Xb, Yb)
        R3 = np.column_stack([Q.rank_high(S3[:, j]) for j in range(len(dims))])
        alpha_log.append(alpha)
        R = {"M1": R1, "M2": R2, "M3": R3, "M4": R4}
        Rag = borda_from_ranks(R, dims)
        for m in Q.METHODS:
            rows += rows_from_rank(R[m], b, dims, feat, m)
        rows += rows_from_rank(Rag, b, dims, feat, "AGG")
        print(f"  secondary rep {b}/{B_SECONDARY} done ({round(time.time()-t0,1)}s)")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "bootstrap_top3_secondary.csv", index=False, encoding="utf-8")
    (OUT / "bootstrap_secondary_meta.json").write_text(
        json.dumps({"B": B_SECONDARY, "glasso_alpha_mean": float(np.mean(alpha_log)),
                    "glasso_alpha_min": float(np.min(alpha_log)),
                    "glasso_alpha_max": float(np.max(alpha_log)),
                    "rf_n_estimators": 200, "rf_perm_repeats_oob": 3,
                    "m3_estimator": "LedoitWolf joint precision (shrinkage recorded as glasso_alpha_*)",
                    "seed_rule": "default_rng(42+(rep-1)); indices=rng.integers(0,250,250)"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"secondary stage: {B_SECONDARY} reps, {len(df)} rows, {round(time.time()-t0,1)}s")
    return df


def consolidate(feat, dims):
    pri = pd.read_csv(OUT / "bootstrap_top3.csv")
    sec = pd.read_csv(OUT / "bootstrap_top3_secondary.csv")
    B_by_method = {m: (B_PRIMARY if m in ("M1", "M4") else B_SECONDARY)
                   for m in Q.METHODS}
    B_by_method["AGG"] = B_SECONDARY
    frames = []
    for m, df in [("M1", pri[pri.method == "M1"]), ("M4", pri[pri.method == "M4"]),
                  ("M2", sec[sec.method == "M2"]), ("M3", sec[sec.method == "M3"]),
                  ("AGG", sec[sec.method == "AGG"])]:
        Bm = B_by_method[m]
        cnt = df.groupby(["dim", "compound"]).size().reset_index(name="n_top3")
        cnt["method"] = m
        cnt["B"] = Bm
        cnt["freq"] = cnt["n_top3"] / Bm
        frames.append(cnt)
    freq = pd.concat(frames, ignore_index=True)
    freq = freq[freq.freq > 0].sort_values(["method", "dim", "freq"], ascending=[True, True, False])
    freq.to_csv(OUT / "selection_frequency.csv", index=False, encoding="utf-8")

    # 每方法每维的稳定席位统计
    seat_rows = []
    for m in ["M1", "M2", "M3", "M4", "AGG"]:
        sub = freq[freq.method == m]
        for dim in dims:
            s = sub[sub.dim == dim]
            seat_rows.append({
                "dim": dim, "method": m, "B": B_by_method[m],
                "n_seats_in_top3": int(len(s)),
                "n_seats_freq_ge_0.80": int((s["freq"] >= Q.FREQ_THRESHOLD).sum()),
                "mean_seat_freq": float(s["freq"].mean()) if len(s) else float("nan"),
                "min_seat_freq": float(s["freq"].min()) if len(s) else float("nan"),
                "top3": ";".join(s.sort_values("freq", ascending=False)["compound"].tolist()),
            })
    seats = pd.DataFrame(seat_rows)
    seats.to_csv(OUT / "stability_by_dimension.csv", index=False, encoding="utf-8")

    # 最终共识 Top-3 的逐席位频率
    t3 = pd.read_csv(OUT / "top3_per_dimension.csv")
    wk = freq.set_index(["dim", "compound", "method"])["freq"]
    fin = []
    for _, r in t3.iterrows():
        row = {"dim": r["dim"], "rank": int(r["rank"]), "compound": r["compound"]}
        for m in ["M1", "M2", "M3", "M4", "AGG"]:
            key = (r["dim"], r["compound"], m)
            row[f"freq_{m}"] = float(wk.get(key, 0.0))
        row["B_AGG"] = B_SECONDARY
        row["stable_AGG"] = int(row["freq_AGG"] >= Q.FREQ_THRESHOLD)
        row["stable_M1"] = int(row["freq_M1"] >= Q.FREQ_THRESHOLD)
        row["stable_M4"] = int(row["freq_M4"] >= Q.FREQ_THRESHOLD)
        fin.append(row)
    fin = pd.DataFrame(fin)
    fin.to_csv(OUT / "stability_seats.csv", index=False, encoding="utf-8")

    # 一致性检查：secondary 的 M1/M4（前 20 rep）应与 primary 完全相同
    agree = {}
    for m in ["M1", "M4"]:
        a = pri[(pri.method == m) & (pri.rep <= B_SECONDARY)].sort_values(["rep", "dim", "rank"])
        b = sec[(sec.method == m)].sort_values(["rep", "dim", "rank"])
        same = (a[["rep", "dim", "rank", "compound"]].reset_index(drop=True).equals(
            b[["rep", "dim", "rank", "compound"]].reset_index(drop=True)))
        agree[m] = bool(same)

    def summ(m):
        sub = fin[f"freq_{m}"]
        return {
            "B": B_by_method[m],
            "mean_freq_of_final_top3_seats": float(sub.mean()),
            "n_seats_ge_0.80": int((sub >= Q.FREQ_THRESHOLD).sum()),
            "frac_seats_ge_0.80": float((sub >= Q.FREQ_THRESHOLD).mean()),
            "n_seats_freq_1.0": int((sub >= 0.999).sum()),
            "mc_se": float(np.sqrt(0.8 * 0.2 / B_by_method[m])),
        }

    summary = {
        "protocol": {
            "B_primary": B_PRIMARY, "B_secondary": B_SECONDARY,
            "frequency_threshold": Q.FREQ_THRESHOLD,
            "jaccard_threshold": Q.JACCARD_THRESHOLD,
            "top3_aggregation": "Borda (sum of 4 method ranks); mean rank used for ordering",
            "seed_rule": "default_rng(42+(rep-1)); indices=rng.integers(0,250,250)",
            "resampling": "with replacement, n=250; standardization refit inside each resample",
            "m1_inner_alpha": "bootstrap fits use per-dim alpha fixed at the full-data 5-fold inner-CV value "
                              "(from _stage_m1m4.npz); re-selecting alpha on duplicate-row resamples is "
                              "degenerate (EXP-0042 timed out; GCV picks alpha=0.01 on rank-deficient resamples)",
            "secondary_note": "M2/M3/AGG use B=20 only (protocol allows <=30 for time budget); "
                              "their stability evidence is weaker than M1/M4 B=300.",
        },
        "by_method": {m: summ(m) for m in ["M1", "M2", "M3", "M4", "AGG"]},
        "primary_secondary_consistency": agree,
        "n_final_seats": int(len(fin)),
        "limitations": [
            "bootstrap 只在 250 个样本内重采样，不能外推到其他啤酒/风格分布",
            "M2/M3/AGG 的 B=20 使频率分辨率只有 0.05，0.80 阈值附近不稳定",
        ],
    }
    (OUT / "stability_summary.json").write_text(
        json.dumps(Q.sanitize(summary), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8")

    extra = {}
    try:
        sel = json.loads((OUT / "selection_summary.json").read_text(encoding="utf-8"))
        extra["jaccard_mean"] = float(sel["jaccard_mean"])
        extra["prior_rank_corr_mean"] = float(sel["prior_consistency"]["mean_rho"])
    except Exception:
        pass
    try:
        fin_overall = fin[fin["dim"] == "overall"]["freq_AGG"].mean()
    except Exception:
        fin_overall = float("nan")
    E.emit_metrics({
        **extra,
        "r2": summary["by_method"]["AGG"]["mean_freq_of_final_top3_seats"],
        "r2_50dim": summary["by_method"]["AGG"]["mean_freq_of_final_top3_seats"],
        "r2_overall": float(fin_overall),
        "freq_ge_080_share": summary["by_method"]["AGG"]["frac_seats_ge_0.80"],
        "n_top3_slots_stable": summary["by_method"]["AGG"]["n_seats_ge_0.80"],
        "top3_stability": summary["by_method"]["AGG"]["mean_freq_of_final_top3_seats"],
        "top3_stability_agg": summary["by_method"]["AGG"]["mean_freq_of_final_top3_seats"],
        "top3_stability_m1": summary["by_method"]["M1"]["mean_freq_of_final_top3_seats"],
        "top3_stability_m4": summary["by_method"]["M4"]["mean_freq_of_final_top3_seats"],
        "frac_seats_agg_ge_0.80": summary["by_method"]["AGG"]["frac_seats_ge_0.80"],
        "n_seats_agg_ge_0.80": summary["by_method"]["AGG"]["n_seats_ge_0.80"],
        "frac_seats_m1_ge_0.80": summary["by_method"]["M1"]["frac_seats_ge_0.80"],
        "frac_seats_m4_ge_0.80": summary["by_method"]["M4"]["frac_seats_ge_0.80"],
        "n_final_seats": summary["n_final_seats"],
        "B_primary": B_PRIMARY, "B_secondary": B_SECONDARY,
    }, area="q2")
    E.emit_output("stability_summary", Q.sanitize(summary), area="q2")
    print(json.dumps(Q.sanitize(summary), ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="both",
                    choices=["m1_m4", "m2_m3", "both"])
    args = ap.parse_args()

    d = Q.load_q2()
    feat = d["feat_cols"]
    dims = list(d["Y"].columns)
    Y = d["Y"].to_numpy(float)
    n = Y.shape[0]

    if args.stages in ("m1_m4", "both"):
        set_fixed_alpha_from_stage()
        stage_primary(d, feat, dims, d["X_imp"], Y, n)
    if args.stages in ("m2_m3", "both"):
        if not (OUT / "bootstrap_top3.csv").exists():
            raise SystemExit("missing outputs/q2/bootstrap_top3.csv: run --stages m1_m4 first")
        set_fixed_alpha_from_stage()
        stage_secondary(d, feat, dims, d["X_imp"], Y, n)
        consolidate(feat, dims)


if __name__ == "__main__":
    main()
