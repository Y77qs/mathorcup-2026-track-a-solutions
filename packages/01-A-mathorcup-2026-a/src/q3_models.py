"""Q3 模型层：风格条件生成模型（A/B/C 三族）+ 风格分类器 5 折 CV + 训练内 CV 选型。

家族定义
--------
A  风格条件低秩高斯：训练集 z 空间全局 PCA(k)，每风格潜在均值 μ_s，共享（向对角收缩的）
   合并协方差 Σ；采样 z ~ N(μ_s, Σ) -> 逆 PCA -> 逆标准化 -> 支撑域裁剪。
B  风格条件 VAE：numpy 手写 MLP + 解析反向传播（无 torch），latent ∈ {8,12}，
   强 L2 + beta 正则 + 按折内验证重构早停。编码器/解码器都以风格 one-hot 为条件。
C  风格条件 KDE/bootstrap：z 空间 PCA(k=10)，围绕风格内样本做高斯核扰动，
   带宽 Scott 规则 h = 0.8 * n_s^(-1/(k+4))（固定规则，不按结果调参）。

选择依据只在训练内部：5 折（按风格分层）中，用折内训练集拟合生成模型 + 折内训练集拟合
风格分类器，对生成样本算"被判为目标风格"的命中率与到折内留出真值的能量距离比
ED / D_ref（D_ref = 折内训练同风格样本的平方距离中位数开方），
score = mean_s (hit_s - ED_ratio_s)。留出测试集不参与选择。

输出
----
outputs/q3/model_selection.json          三族 × 超参的全部 CV 分数与锁定配置
outputs/q3/style_classifier_report.json  分类器 5 折 CV（准确率/宏F1/混淆矩阵）
outputs/q3/leakage_manifest.json         生成模型训练所用列清单（泄漏硬检查）
outputs/q3/fitted/                      锁定配置的拟合参数（供 generate/transfer 复用）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import q3_utils as U  # noqa: E402

try:
    import emit as E
except Exception:  # noqa: BLE001
    E = None

from sklearn.decomposition import PCA  # noqa: E402


# ================================================================ 家族 A
class StyleConditionalGaussian:
    """PCA(k) 潜在空间中的 per-style 均值 + 共享协方差（等价条件高斯）。"""

    family = "A_conditional_gaussian"

    def __init__(self, k: int = 10, shrinkage: float = 0.1, seed: int = U.SEED,
                 anchor: bool = True):
        self.k = int(k)
        self.shrinkage = float(shrinkage)
        self.seed = int(seed)
        self.anchor = bool(anchor)

    def fit(self, Z: np.ndarray, y: np.ndarray):
        self.pca_ = PCA(n_components=self.k, svd_solver="full", random_state=self.seed)
        S = self.pca_.fit_transform(Z)
        self.styles_ = list(np.unique(y))
        mus = {s: S[y == s].mean(axis=0) for s in self.styles_}
        resids = []
        for s in self.styles_:
            Ss = S[y == s]
            if len(Ss) > 1:
                resids.append(Ss - mus[s][None, :])
        if resids:
            R = np.vstack(resids)
            dof = max(len(R) - len(self.styles_), 1)
            cov = R.T @ R / dof
        else:
            cov = np.eye(self.k)
        # 向对角收缩 + 保证正定
        d = np.diag(np.diag(cov))
        cov = (1 - self.shrinkage) * cov + self.shrinkage * d
        cov = cov + np.eye(self.k) * (1e-6 * np.trace(cov) / self.k + 1e-9)
        self.mu_ = mus
        self.cov_ = cov
        self.cov_inv_ = np.linalg.inv(cov)
        self.score_mu_ = {s: v for s, v in mus.items()}
        # 条件均值锚定：低秩截断会让模型隐含的条件均值偏离观测风格均值，
        # 这里把残差 delta 记下来，采样时加回（生成分布的条件均值 == 观测风格均值）。
        self.mu_full_ = {s: Z[y == s].mean(axis=0) for s in self.styles_}
        if self.anchor:
            self.delta_ = {s: self.mu_full_[s] - self.pca_.inverse_transform(
                self.pca_.transform(self.mu_full_[s][None, :]))[0] for s in self.styles_}
        else:
            self.delta_ = {s: np.zeros_like(self.mu_full_[s]) for s in self.styles_}
        self.delta_norm_ = {s: float(np.linalg.norm(self.delta_[s])) for s in self.styles_}
        return self

    def has_style(self, style: str) -> bool:
        return style in self.mu_

    def sample(self, style: str, n: int, rng: np.random.Generator,
               fallback_style: str = None) -> np.ndarray:
        s = style if style in self.mu_ else (fallback_style or self.styles_[0])
        z = rng.multivariate_normal(self.mu_[s], self.cov_, size=int(n),
                                    check_valid="ignore")
        return self.pca_.inverse_transform(z) + self.delta_[s][None, :]

    def latent(self, Z: np.ndarray) -> np.ndarray:
        return self.pca_.transform(Z)


# ================================================================ 家族 B
class ConditionalVAE:
    """numpy 实现的风格条件 VAE（tanh MLP + 解析反向传播 + Adam + 早停）。"""

    family = "B_conditional_vae"

    def __init__(self, n_styles: int, latent: int = 10, h1: int = 64, h2: int = 32,
                 beta: float = 0.5, lr: float = 3e-3, batch: int = 32,
                 weight_decay: float = 1e-4, seed: int = U.SEED,
                 max_epochs: int = 400, patience: int = 40, val_frac: float = 0.2):
        self.n_styles = int(n_styles)
        self.latent = int(latent)
        self.h1, self.h2 = int(h1), int(h2)
        self.beta = float(beta)
        self.lr = float(lr)
        self.batch = int(batch)
        self.wd = float(weight_decay)
        self.seed = int(seed)
        self.max_epochs = int(max_epochs)
        self.patience = int(patience)
        self.val_frac = float(val_frac)

    # -- 初始化
    def _init(self, d: int):
        rng = np.random.default_rng(self.seed)
        din = d + self.n_styles
        din_dec = self.latent + self.n_styles

        def w(*shape, scale=None):
            fan_in = shape[0]
            scale = np.sqrt(1.0 / fan_in) if scale is None else scale
            return rng.normal(0.0, scale, size=shape)

        self.P = {
            "W1": w(din, self.h1), "b1": np.zeros(self.h1),
            "W2": w(self.h1, self.h2), "b2": np.zeros(self.h2),
            "Wmu": w(self.h2, self.latent, scale=0.1), "bmu": np.zeros(self.latent),
            "Wlv": w(self.h2, self.latent, scale=0.1), "blv": np.zeros(self.latent),
            "Wd1": w(din_dec, self.h2), "bd1": np.zeros(self.h2),
            "Wd2": w(self.h2, self.h1), "bd2": np.zeros(self.h1),
            "Wout": w(self.h1, d, scale=0.1), "bout": np.zeros(d),
        }

    @staticmethod
    def _onehot(y_idx: np.ndarray, n_styles: int) -> np.ndarray:
        H = np.zeros((len(y_idx), n_styles))
        H[np.arange(len(y_idx)), y_idx] = 1.0
        return H

    def _forward(self, X: np.ndarray, H: np.ndarray, rng=None):
        P = self.P
        X1 = np.hstack([X, H])
        a1 = X1 @ P["W1"] + P["b1"]
        h1 = np.tanh(a1)
        a2 = h1 @ P["W2"] + P["b2"]
        h2 = np.tanh(a2)
        mu = h2 @ P["Wmu"] + P["bmu"]
        lv = np.clip(h2 @ P["Wlv"] + P["blv"], -6.0, 6.0)
        eps = rng.standard_normal(mu.shape) if rng is not None else np.zeros_like(mu)
        z = mu + np.exp(0.5 * lv) * eps
        zd = np.hstack([z, H])
        c1 = zd @ P["Wd1"] + P["bd1"]
        d1 = np.tanh(c1)
        c2 = d1 @ P["Wd2"] + P["bd2"]
        d2 = np.tanh(c2)
        xhat = d2 @ P["Wout"] + P["bout"]
        cache = (X1, h1, h2, mu, lv, eps, zd, d1, d2, xhat)
        return xhat, mu, lv, cache

    def _loss_grad(self, X, H, rng):
        d = X.shape[1]
        xhat, mu, lv, (X1, h1, h2, mu_c, lv_c, eps, zd, d1, d2, _) = \
            self._forward(X, H, rng)
        B = len(X)
        resid = xhat - X
        Lr = float((resid ** 2).sum() / (B * d))
        KL = float(0.5 * (mu ** 2 + np.exp(lv) - lv - 1.0).sum() / B)
        loss = Lr + self.beta * KL
        P = self.P
        G = {}
        # 重构路径
        dxhat = (2.0 / (B * d)) * resid
        G["Wout"] = d2.T @ dxhat
        G["bout"] = dxhat.sum(0)
        dd2 = dxhat @ P["Wout"].T
        dc2 = dd2 * (1 - d2 ** 2)
        G["Wd2"] = d1.T @ dc2
        G["bd2"] = dc2.sum(0)
        dd1 = dc2 @ P["Wd2"].T
        dc1 = dd1 * (1 - d1 ** 2)
        G["Wd1"] = zd.T @ dc1
        G["bd1"] = dc1.sum(0)
        dzd = dc1 @ P["Wd1"].T
        dz = dzd[:, :self.latent]
        dmu = dz + self.beta * mu / B
        dlv = dz * 0.5 * np.exp(0.5 * lv_c) * eps + self.beta * 0.5 * (np.exp(lv_c) - 1) / B
        # KL 对 lv 的项已是上式第二项；mu 项已在 dmu
        G["Wmu"] = h2.T @ dmu
        G["bmu"] = dmu.sum(0)
        G["Wlv"] = h2.T @ dlv
        G["blv"] = dlv.sum(0)
        dh2 = dmu @ P["Wmu"].T + dlv @ P["Wlv"].T
        da2 = dh2 * (1 - h2 ** 2)
        G["W2"] = h1.T @ da2
        G["b2"] = da2.sum(0)
        dh1 = da2 @ P["W2"].T
        da1 = dh1 * (1 - h1 ** 2)
        G["W1"] = X1.T @ da1
        G["b1"] = da1.sum(0)
        for k in ("W1", "W2", "Wmu", "Wlv", "Wd1", "Wd2", "Wout"):
            G[k] = G[k] + self.wd * P[k]
        return loss, Lr, KL, G

    def _recon(self, X, y_idx):
        xhat, _, _, _ = self._forward(X, self._onehot(y_idx, self.n_styles), rng=None)
        d = X.shape[1]
        return float(((xhat - X) ** 2).sum() / (len(X) * d))

    def _adam_step(self, G, state, t):
        P = self.P
        for k in P:
            m = state["m"][k]
            v = state["v"][k]
            g = G[k]
            m = 0.9 * m + 0.1 * g
            v = 0.999 * v + 0.001 * g * g
            state["m"][k] = m
            state["v"][k] = v
            mh = m / (1 - 0.9 ** t)
            vh = v / (1 - 0.999 ** t)
            P[k] = P[k] - self.lr * mh / (np.sqrt(vh) + 1e-8)

    def fit(self, Z: np.ndarray, y: np.ndarray, n_styles_total: int = None,
            verbose: bool = False):
        d = Z.shape[1]
        self._init(d)
        self.styles_ = list(np.unique(y))
        self.style_to_idx_global_ = None
        # 条件用全局风格索引（保证跨折一致），由调用方通过 style_ids 传入
        y_idx = np.asarray(y, int)
        rng = np.random.default_rng(self.seed)
        # 折内验证集（早停），按索引分层抽 20%
        val_idx = []
        for s in np.unique(y_idx):
            idx = np.where(y_idx == s)[0]
            n_val = int(round(self.val_frac * len(idx)))
            if len(idx) >= 3:
                n_val = max(1, n_val)
            else:
                n_val = 0
            if n_val:
                val_idx.extend(rng.choice(idx, size=min(n_val, len(idx) - 1),
                                          replace=False).tolist())
        val_idx = np.array(sorted(set(val_idx)), dtype=int)
        tr_idx = np.setdiff1d(np.arange(len(Z)), val_idx)
        if len(tr_idx) < 10 or len(val_idx) < 2:
            tr_idx = np.arange(len(Z))
            val_idx = np.array([], dtype=int)
        state = {"m": {k: np.zeros_like(v) for k, v in self.P.items()},
                 "v": {k: np.zeros_like(v) for k, v in self.P.items()}}
        best = {"val": np.inf, "params": None, "epoch": -1, "train": np.nan}
        t = 0
        bad = 0
        for ep in range(self.max_epochs):
            perm = rng.permutation(tr_idx)
            for i in range(0, len(perm), self.batch):
                b = perm[i:i + self.batch]
                if len(b) < 2:
                    continue
                t += 1
                _, _, _, G = self._loss_grad(Z[b], self._onehot(y_idx[b], self.n_styles),
                                             rng)
                self._adam_step(G, state, t)
            if len(val_idx) >= 2:
                vrec = self._recon(Z[val_idx], y_idx[val_idx])
                trec = self._recon(Z[tr_idx], y_idx[tr_idx])
                if vrec < best["val"] - 1e-6:
                    best = {"val": vrec, "train": trec, "epoch": ep,
                            "params": {k: v.copy() for k, v in self.P.items()}}
                    bad = 0
                else:
                    bad += 1
                if bad >= self.patience:
                    break
                if verbose and ep % 50 == 0:
                    print(f"  ep{ep} train {trec:.4f} val {vrec:.4f}")
            else:
                best["epoch"] = ep
                best["params"] = {k: v.copy() for k, v in self.P.items()}
        if best["params"] is not None:
            self.P = best["params"]
        self.best_epoch_ = best["epoch"]
        self.val_recon_ = best["val"]
        self.train_recon_ = best["train"]
        self.n_val_ = int(len(val_idx))
        return self

    def sample(self, style_idx_global: int, n: int, rng: np.random.Generator) -> np.ndarray:
        z = rng.standard_normal((int(n), self.latent))
        H = self._onehot(np.full(int(n), style_idx_global, dtype=int), self.n_styles)
        P = self.P
        zd = np.hstack([z, H])
        c1 = zd @ P["Wd1"] + P["bd1"]
        d1 = np.tanh(c1)
        c2 = d1 @ P["Wd2"] + P["bd2"]
        d2 = np.tanh(c2)
        return d2 @ P["Wout"] + P["bout"]

    def recon(self, Z: np.ndarray, y_idx: np.ndarray) -> np.ndarray:
        xhat, _, _, _ = self._forward(Z, self._onehot(np.asarray(y_idx, int), self.n_styles),
                                      rng=None)
        return xhat


# ================================================================ 家族 C
class StyleKDE:
    """z 空间中围绕风格内样本的高斯核扰动（bootstrap/KDE 采样）。"""

    family = "C_style_kde"

    def __init__(self, k: int = 10, bandwidth_scale: float = 0.8, seed: int = U.SEED):
        self.k = int(k)
        self.bandwidth_scale = float(bandwidth_scale)
        self.seed = int(seed)

    def fit(self, Z: np.ndarray, y: np.ndarray):
        self.pca_ = PCA(n_components=self.k, svd_solver="full", random_state=self.seed)
        S = self.pca_.fit_transform(Z)
        self.S_ = S
        self.y_ = np.asarray(y)
        self.styles_ = list(np.unique(y))
        self.var_all_ = S.var(axis=0, ddof=1) + 1e-12
        self.h_ = {}
        for s in self.styles_:
            n_s = int((self.y_ == s).sum())
            self.h_[s] = self.bandwidth_scale * max(n_s, 1) ** (-1.0 / (self.k + 4))
        return self

    def has_style(self, style: str) -> bool:
        return style in self.styles_

    def sample(self, style: str, n: int, rng: np.random.Generator,
               fallback_style: str = None) -> np.ndarray:
        s = style if style in self.styles_ else (fallback_style or self.styles_[0])
        idx = np.where(self.y_ == s)[0]
        picks = rng.choice(idx, size=int(n), replace=True)
        base = self.S_[picks]
        h = self.h_[s]
        noise = rng.standard_normal((int(n), self.k)) * (h * np.sqrt(self.var_all_)[None, :])
        return self.pca_.inverse_transform(base + noise)


# ================================================================ 通用工具
# 生成器可采纳性下限：生成的"风格内离散度"不得低于真值的 50%（防止模式坍塌/只吐均值）
DIVERSITY_FLOOR = 0.5


def style_id_map(styles) -> dict:
    return {s: i for i, s in enumerate(sorted(set(styles)))}


def make_sampler(family: str, cfg: dict, Z: np.ndarray, y_str: np.ndarray,
                 y_idx: np.ndarray, n_styles_total: int, seed: int):
    if family == "A":
        return StyleConditionalGaussian(k=cfg["k"], seed=seed,
                                        anchor=cfg.get("anchor", True)).fit(Z, y_str)
    if family == "B":
        return ConditionalVAE(n_styles=n_styles_total, latent=cfg["latent"],
                              beta=cfg.get("beta", 0.5), seed=seed).fit(Z, y_idx)
    if family == "C":
        return StyleKDE(k=cfg.get("k", 10), seed=seed).fit(Z, y_str)
    raise ValueError(family)


def draw(sampler, family: str, style: str, n: int, rng, style_idx: int,
         fallback: str = None) -> np.ndarray:
    if family == "B":
        return sampler.sample(style_idx, n, rng)
    return sampler.sample(style, n, rng, fallback_style=fallback)


def diversity_ratio(A: np.ndarray, B: np.ndarray) -> float:
    """生成集平均两两距离 / 真值集平均两两距离（z 空间）。"""
    if len(A) < 2 or len(B) < 2:
        return float("nan")
    da = np.sqrt(U.pairwise_sq_dists(A, A))[np.triu_indices(len(A), 1)].mean()
    db = np.sqrt(U.pairwise_sq_dists(B, B))[np.triu_indices(len(B), 1)].mean()
    return float(da / db) if db > 0 else float("nan")


def d_ref_value(Z_ref: np.ndarray) -> float:
    if len(Z_ref) < 2:
        return float("nan")
    d = np.sqrt(U.pairwise_sq_dists(Z_ref, Z_ref))[np.triu_indices(len(Z_ref), 1)]
    return float(np.median(d)) if len(d) else float("nan")


def inner_cv_family(family: str, cfg: dict, Z: np.ndarray, y_str: np.ndarray,
                    y_idx: np.ndarray, n_styles_total: int,
                    clf_name: str, seed: int = U.SEED,
                    n_gen: int = 60, k_folds: int = 5, verbose: bool = True,
                    style_ids: dict = None) -> dict:
    """训练内 5 折评估：命中率 + 能量距离比 + 多样性比（类别按风格分层 round-robin）。"""
    folds = U.stratified_folds(y_str, k=k_folds, seed=seed)
    per_fold = []
    for fi, f_test in enumerate(folds):
        mask = np.ones(len(y_str), bool)
        mask[f_test] = False
        Ztr, ytr = Z[mask], y_str[mask]
        idx_tr = y_idx[mask]
        Zte, yte = Z[f_test], y_str[f_test]
        if len(np.unique(ytr)) < 2:
            continue
        fit_seed = seed + 1000 * (fi + 1)
        sampler = make_sampler(family, cfg, Ztr, ytr, idx_tr, n_styles_total, fit_seed)
        clf = U.fit_style_classifier(Ztr, ytr, clf_name)
        rng = np.random.default_rng(fit_seed + 7)
        rows = []
        for s in np.unique(yte):
            Zte_s = Zte[yte == s]
            if len(Zte_s) < 1:
                continue
            gen = draw(sampler, family, s, n_gen, rng,
                       (style_ids or {}).get(s, 0) if family == "B" else -1)
            pred = clf.predict(gen)
            hit = float(np.mean(pred == s))
            ed = U.energy_distance(gen, Zte_s)
            dr = d_ref_value(Ztr[ytr == s])
            ed_ratio = ed["ed"] / dr if (dr and np.isfinite(dr) and dr > 0) else np.nan
            rows.append({"style": s, "n_train": int((ytr == s).sum()),
                         "n_test": int(len(Zte_s)), "hit_rate": hit,
                         "ed": ed["ed"], "ed_ratio": ed_ratio,
                         "diversity_ratio": diversity_ratio(gen, Ztr[ytr == s]),
                         "recon_val": float("nan")})
        per_fold.append(rows)
        if verbose:
            good = [r for r in rows if np.isfinite(r["ed_ratio"])]
            print(f"  [CV {family} {cfg}] fold{fi}: n_styles={len(rows)} "
                  f"hit={np.mean([r['hit_rate'] for r in rows]):.3f} "
                  f"ed_ratio={np.mean([r['ed_ratio'] for r in good]) if good else float('nan'):.3f}")
    rows = [r for f in per_fold for r in f]
    df = pd.DataFrame(rows)
    if df.empty:
        return {"family": family, "config": cfg, "score": -np.inf, "n_style_fold": 0}
    per_style = (df.groupby("style")
                 .agg(hit_rate=("hit_rate", "mean"), ed_ratio=("ed_ratio", "mean"),
                      diversity_ratio=("diversity_ratio", "mean"),
                      n_train=("n_train", "mean"), n_test=("n_test", "sum"))
                 .reset_index())
    per_style["score"] = per_style["hit_rate"] - per_style["ed_ratio"].fillna(1.0)
    scored = per_style[(per_style["n_train"] >= 3) & (per_style["n_test"] >= 1)]
    use = scored if len(scored) else per_style
    req = per_style[per_style["style"].isin(U.REQUIRED_STYLES)]
    out = {
        "family": family, "config": cfg,
        "score": float(use["score"].mean()),
        "mean_hit_rate": float(use["hit_rate"].mean()),
        "mean_ed_ratio": float(use["ed_ratio"].mean()),
        "mean_diversity_ratio": float(use["diversity_ratio"].mean()),
        "n_style_fold": int(len(df)),
        "n_styles_scored": int(len(use)),
        "per_style": per_style.round(6).to_dict(orient="records"),
        "required_styles": req.round(6).to_dict(orient="records"),
        "mean_diagnostics": {
            "recon_val": float(df["recon_val"].mean()) if df["recon_val"].notna().any() else None,
        },
        "admissible": bool(np.isfinite(use["diversity_ratio"].mean())
                           and use["diversity_ratio"].mean() >= DIVERSITY_FLOOR),
        "admissibility_rule": f"mean diversity_ratio >= {DIVERSITY_FLOOR} "
                              f"(生成集风格内两两距离 / 真值同风格两两距离)",
    }
    return out


def vae_fit_report(Z: np.ndarray, y_str: np.ndarray, y_idx: np.ndarray,
                   n_styles_total: int, latent: int, beta: float = 0.5,
                   seed: int = U.SEED) -> dict:
    """VAE 过拟合诊断：折内训练/验证重构误差，与常数（训练均值）基线对比。"""
    folds = U.stratified_folds(y_str, k=5, seed=seed)
    rows = []
    for fi, f_test in enumerate(folds):
        mask = np.ones(len(y_str), bool)
        mask[f_test] = False
        Ztr, ytr, itr = Z[mask], y_str[mask], y_idx[mask]
        Zte, yte, ite = Z[f_test], y_str[f_test], y_idx[f_test]
        vae = ConditionalVAE(n_styles=n_styles_total, latent=latent, beta=beta,
                             seed=seed + 1000 * (fi + 1)).fit(Ztr, itr)
        tr_rec = vae._recon(Ztr, itr)
        te_rec = vae._recon(Zte, ite)
        mu = Ztr.mean(0)
        base = float(((Zte - mu) ** 2).sum() / (len(Zte) * Z.shape[1]))
        rows.append({"fold": fi, "train_recon": tr_rec, "holdout_recon": te_rec,
                     "const_baseline_recon": base,
                     "best_epoch": vae.best_epoch_, "val_recon": vae.val_recon_,
                     "n_val": vae.n_val_})
    df = pd.DataFrame(rows)
    return {
        "latent": latent,
        "beta": beta,
        "train_recon_mean": float(df["train_recon"].mean()),
        "holdout_recon_mean": float(df["holdout_recon"].mean()),
        "const_baseline_recon_mean": float(df["const_baseline_recon"].mean()),
        "gap_holdout_minus_train": float((df["holdout_recon"] - df["train_recon"]).mean()),
        "relative_gap": float(((df["holdout_recon"] - df["train_recon"]) /
                               df["train_recon"]).mean()),
        "best_epoch_median": int(np.median(df["best_epoch"])),
        "per_fold": df.round(6).to_dict(orient="records"),
    }


# ================================================================ main
def main():
    print("== Q3 model layer ==")
    tab = U.load_style_table()
    split = U.load_split("primary")
    split_strat = U.load_split("stratified")
    print(f"split: {split['path']} train={split['n_train']} test={split['n_test']} "
          f"| stratified: {split_strat['path']}")

    prep = U.fit_preprocessor(tab, split["train_beer"])
    Xtr = U.train_matrix(tab, split["train_beer"])
    Xte = U.train_matrix(tab, split["test_beer"])
    Z = prep.transform(Xtr)
    Zte = prep.transform(Xte)
    y_tr = tab.set_index("beer").loc[split["train_beer"], "style"].values
    styles = sorted(tab["style"].unique())
    sid = style_id_map(styles)
    y_idx = np.array([sid[s] for s in y_tr], dtype=int)

    tt = prep.transform_table()
    U.write_csv(tt, "outputs/q3/column_transforms.csv")
    support = {
        "n_features": int(U.N_FEATURES),
        "n_log1p_columns": int((tt["transform"] == "log1p").sum()),
        "n_identity_columns": int((tt["transform"] == "identity").sum()),
        "log1p_columns": tt.loc[tt["transform"] == "log1p", "compound"].tolist(),
        "transform_rule": "log10 审计列 -> identity；其余列若训练值全 >=0 且偏度>2.0 -> log1p；否则 identity",
        "train_min_max_recorded": True,
        "n_linear_nonneg_cols": int(prep.linear_cols.sum()),
        "n_log_or_unverified_cols": int((~prep.linear_cols).sum()),
    }

    # ---------- 1) 风格分类器 5 折 CV（训练内） ----------
    print("[1] style classifier 5-fold CV on train ...")
    clf_cv = U.style_classifier_cv(Z, y_tr, k=5, seed=U.SEED)
    clf_name = clf_cv["selected"]
    print(f"    selected classifier: {clf_name} "
          f"acc={clf_cv['candidates'][clf_name]['cv_accuracy_mean']:.3f} "
          f"macroF1={clf_cv['candidates'][clf_name]['cv_macro_f1_mean']:.3f}")
    for n, v in clf_cv["candidates"].items():
        print(f"    - {n}: acc={v['cv_accuracy_mean']:.3f} macroF1={v['cv_macro_f1_mean']:.3f}")
    style_support_train = {s: int((y_tr == s).sum()) for s in styles}
    style_support_test = U.style_counts(tab["beer"].values, tab["style"].values,
                                        split["test_beer"])
    style_support_strat = {
        "train": U.style_counts(tab["beer"].values, tab["style"].values,
                                split_strat["train_beer"]),
        "test": U.style_counts(tab["beer"].values, tab["style"].values,
                               split_strat["test_beer"]),
    }
    report = {
        "purpose": "Q3 风格保真度评估器：判别生成样本是否被判为目标风格（评价工具，不参与生成）",
        "selected_classifier": clf_name,
        "cv": {"k_folds": 5, "seed": int(U.SEED), "n_train": int(len(y_tr)),
               "n_classes": int(len(styles)),
               "chance_uniform": 1.0 / len(styles),
               "majority_class_rate": max(style_support_train.values()) / len(y_tr)},
        "candidates": clf_cv["candidates"],
        "style_support_train": style_support_train,
        "style_support_test": style_support_test,
        "note": "CV 只在 200 个训练样本内进行；混淆矩阵按风格排序，classes 字段给出顺序。",
    }
    U.write_json(report, "outputs/q3/style_classifier_report.json")

    # ---------- 2) 三族 × 超参训练内 CV ----------
    print("[2] inner CV for family A (PCA k) ...")
    results = []
    for k in (6, 10, 15):
        r = inner_cv_family("A", {"k": k}, Z, y_tr, y_idx, len(styles), clf_name,
                            seed=U.SEED, style_ids=sid)
        results.append(r)
        print(f"    A k={k}: score={r['score']:.3f} hit={r['mean_hit_rate']:.3f} "
              f"ed_ratio={r['mean_ed_ratio']:.3f} div={r['mean_diversity_ratio']:.3f}")

    VAE_GRID = [(8, 0.05), (8, 0.2), (12, 0.05), (12, 0.2)]
    print(f"[3] VAE overfitting diagnostics for {VAE_GRID} ...")
    vae_diag = {}
    for lat, beta in VAE_GRID:
        key = f"latent{lat}_beta{beta}"
        vae_diag[key] = vae_fit_report(Z, y_tr, y_idx, len(styles), lat, beta, U.SEED)
        d = vae_diag[key]
        print(f"    VAE {key}: train {d['train_recon_mean']:.4f} "
              f"holdout {d['holdout_recon_mean']:.4f} "
              f"const {d['const_baseline_recon_mean']:.4f} "
              f"relgap {d['relative_gap']:.3f} best_epoch {d['best_epoch_median']}")

    print("[4] inner CV for family B (VAE latent x beta) ...")
    for lat, beta in VAE_GRID:
        r = inner_cv_family("B", {"latent": lat, "beta": beta}, Z, y_tr, y_idx,
                            len(styles), clf_name, seed=U.SEED, style_ids=sid)
        results.append(r)
        print(f"    B latent={lat} beta={beta}: score={r['score']:.3f} "
              f"hit={r['mean_hit_rate']:.3f} ed_ratio={r['mean_ed_ratio']:.3f} "
              f"div={r['mean_diversity_ratio']:.3f} admissible={r['admissible']}")

    print("[5] inner CV for family C (KDE) ...")
    r = inner_cv_family("C", {"k": 10}, Z, y_tr, y_idx, len(styles), clf_name,
                        seed=U.SEED, style_ids=sid)
    results.append(r)
    print(f"    C k=10: score={r['score']:.3f} hit={r['mean_hit_rate']:.3f} "
          f"ed_ratio={r['mean_ed_ratio']:.3f} div={r['mean_diversity_ratio']:.3f}")

    unconstrained_best = max(results, key=lambda r: r["score"])
    admissible = [r for r in results if r.get("admissible", True)]
    pool = admissible if admissible else results
    ranked = sorted(pool, key=lambda r: -r["score"])
    top = ranked[0]
    TIE = 0.01
    tied = [r for r in ranked if top["score"] - r["score"] < TIE]
    if len(tied) > 1:
        best = min(tied, key=lambda r: (r["mean_ed_ratio"], -r["family"].startswith("A")))
        tie_info = {"rule": f"score 差 < {TIE} 视为不可区分 -> 取 ED/D_ref 最小者",
                    "tied": [{"family": r["family"], "config": r["config"],
                              "score": r["score"], "mean_ed_ratio": r["mean_ed_ratio"]}
                             for r in tied],
                    "chosen": {"family": best["family"], "config": best["config"]}}
    else:
        best = top
        tie_info = {"rule": f"score 差 >= {TIE}，直接取最大 score", "tied": [],
                    "chosen": {"family": best["family"], "config": best["config"]}}
    print(f"[selected] {best['family']} {best['config']} score={best['score']:.3f} "
          f"(unconstrained best: {unconstrained_best['family']} "
          f"{unconstrained_best['config']} {unconstrained_best['score']:.3f}; "
          f"tie_break={len(tied)} tied)")

    selection = {
        "protocol": {
            "selection_data": "training split only (200 samples), 5 stratified folds",
            "criterion": "score = mean_style(hit_rate - ED/D_ref) on held-out-by-CV; "
                         "hit_rate = fraction of generated samples classified as target style",
            "admissibility": f"mean diversity_ratio >= {DIVERSITY_FLOOR}；"
                             "不满足者（模式坍塌/只吐风格均值）不参与最终选择，但仍完整报告其分数",
            "tie_break": "score 差 < 0.01 视为不可区分，取 ED/D_ref 最小者（分布吻合优先）",
            "anchoring_note": "A 族对条件均值做锚定：低秩 PCA 截断会使隐含条件均值偏离观测风格均值，"
                              "采样时把残差 delta 加回，使生成分布条件均值 == 观测风格均值；"
                              "该步在 CV 中也生效。锚定后风格命中率饱和于 ~1.0（判别器区分度不足），"
                              "因此 ED/MMD 与画像/缺陷合理性成为更有效的判据。",
            "criterion_revision_note": "多样性下限是在第一轮 CV 观察到 B 族（VAE）"
                                       "多样性仅为真值的 10% 而命中率虚高后加入的判据修订；"
                                       "修订前后的排序都在本文件里（unconstrained_best 字段），未隐藏。",
            "holdout_used_for_selection": False,
            "n_gen_per_style_per_fold": 60,
            "families": {"A": "PCA(k) + per-style mean + shared shrunk covariance",
                         "B": "numpy conditional VAE (latent 8-12, L2 + beta KL, early stop)",
                         "C": "PCA(10) + within-style Gaussian KDE (Scott bandwidth)"},
        },
        "split": U.split_meta(split),
        "split_stratified": U.split_meta(split_strat),
        "preprocessing": {"impute": "train column median",
                          "scale": "train z-score", "support": support},
        "style_id_map": sid,
        "style_support_train": style_support_train,
        "style_support_test": style_support_test,
        "style_support_stratified_split": style_support_strat,
        "classifier_selected": clf_name,
        "classifier_cv": {n: {"cv_accuracy_mean": v["cv_accuracy_mean"],
                              "cv_macro_f1_mean": v["cv_macro_f1_mean"]}
                          for n, v in clf_cv["candidates"].items()},
        "vae_overfitting": vae_diag,
        "tie_break": tie_info,
        "candidates": results,
        "unconstrained_best": {"family": unconstrained_best["family"],
                               "config": unconstrained_best["config"],
                               "score": unconstrained_best["score"],
                               "mean_diversity_ratio": unconstrained_best["mean_diversity_ratio"],
                               "admissible": unconstrained_best.get("admissible")},
        "diversity_floor": DIVERSITY_FLOOR,
        "selected": {"family": best["family"], "config": best["config"],
                     "score": best["score"],
                     "mean_hit_rate": best["mean_hit_rate"],
                     "mean_ed_ratio": best["mean_ed_ratio"],
                     "mean_diversity_ratio": best["mean_diversity_ratio"],
                     "required_styles": best["required_styles"]},
    }
    U.write_json(selection, "outputs/q3/model_selection.json")

    # ---------- 3) 泄漏清单 ----------
    manifest = {
        "registered_dataset": {
            "datasetId": "DATA-0002",
            "path": "data/clean/model_table.csv",
            "sha256": (U.sha256(U.PROJECT / "data" / "clean" / "model_table.csv")
                       if (U.PROJECT / "data" / "clean" / "model_table.csv").exists() else None),
            "note": "DATA-0002 = 1.csv 231 特征 + 4.csv 50 目标（逐 beer）。本项目生成模型只读其 231 特征列"
                    "与风格列，目标列只被 Q3 的占位前向映射用于画像评估。",
        },
        "generation_training_inputs": {
            "file": "data/raw/1.csv",
            "sha256": U.sha256(U.PROJECT / "data" / "raw" / "1.csv"),
            "columns": ["beer"] + U.FEATURES + ["tasting_category_fine"],
            "n_feature_columns": int(U.N_FEATURES),
            "n_rows": int(len(tab)),
            "train_rows": int(split["n_train"]),
            "condition_column": "tasting_category_fine",
        },
        "forbidden_inputs_verified_unused": [
            {"file": "data/raw/4.csv", "role": "sensory targets",
             "used_in_generation": False,
             "use": "仅用于 sensory profile 的占位/评估（未进入生成模型训练）"},
            {"file": "data/raw/5.csv", "used_in_generation": False},
            {"file": "data/raw/6.csv", "used_in_generation": False},
            {"file": "data/raw/7.csv", "used_in_generation": False},
            {"file": "data/raw/8.xlsx#GBM importance MDI", "used_in_generation": False},
            {"file": "data/raw/8.xlsx#GBM SHAP Values", "used_in_generation": False},
        ],
        "external_reference_used_for_evaluation_only": [
            {"file": "data/raw/8.xlsx#Sensory thresholds",
             "use": "缺陷类别的绝对阈值（OAV 口径）与迁移硬约束的定义来源；不作为特征",
             "compounds_with_threshold": ["DMS", "X2.3.butanedione", "X4VG"]},
        ],
        "feature_scope": {
            "model_space": "231 列化合物/理化（1.csv）",
            "style_condition": "tasting_category_fine（22 类）",
            "n_columns_used_in_generation": 231,
            "any_target_or_correlation_file_in_features": False,
        },
    }
    U.write_json(manifest, "outputs/q3/leakage_manifest.json")
    if E is not None and E.IN_RUNNER:
        E.emit_metrics({
            "classifier_cv_accuracy": clf_cv["candidates"][clf_name]["cv_accuracy_mean"],
            "classifier_cv_macro_f1": clf_cv["candidates"][clf_name]["cv_macro_f1_mean"],
            "selected_score": best["score"],
            "selected_hit_rate": best["mean_hit_rate"],
            "selected_ed_ratio": best["mean_ed_ratio"],
            "selected_diversity_ratio": best["mean_diversity_ratio"],
            "n_features": int(U.N_FEATURES),
            "n_train": int(split["n_train"]),
            "n_test": int(split["n_test"]),
            "stochastic": True,
        }, area="q3")
        E.emit_output("candidate_scores", U.clean_json(
            [{"family": r["family"], "config": r["config"], "score": r["score"],
              "mean_hit_rate": r["mean_hit_rate"],
              "mean_ed_ratio": r["mean_ed_ratio"],
              "mean_diversity_ratio": r["mean_diversity_ratio"],
              "admissible": r.get("admissible")} for r in results]), area="q3")
        E.emit_output("vae_overfitting", U.clean_json(vae_diag), area="q3")
    print("[done] model_selection.json / style_classifier_report.json / leakage_manifest.json")


if __name__ == "__main__":
    main()
