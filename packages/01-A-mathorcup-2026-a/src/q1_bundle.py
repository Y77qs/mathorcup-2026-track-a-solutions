"""Q1 model_bundle 的唯一读取入口（Q3 必须通过它，不要自己 open pickle）。

bundle 是 gzip 压缩的 pickle（原始 ~91MB，压缩后 ~25-30MB）。
用法：
    import sys; sys.path.insert(0,'src')
    from q1_bundle import load_bundle, predict_spectra
    B = load_bundle()
    Z, G = predict_spectra(B, spectra_df_231cols)   # Z: (n,50) 连续强度; G: (n,50) 0-6 等级
"""
import gzip
import pickle
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "outputs/q1/model_bundle.pkl.gz"


def load_bundle(path=None):
    p = Path(path) if path else DEFAULT
    if not p.exists():
        raise FileNotFoundError(
            f"Q1 bundle not found at {p}; 请先跑 src/08c_q1_final.py（Lead 版）或等 modeler-q1 导出")
    with gzip.open(p, "rb") as f:
        return pickle.load(f)


def _transform(B, X):
    X = np.asarray(X, dtype=float)
    med = np.asarray(B["prep"]["median"]); lo = np.asarray(B["prep"]["lo"]); hi = np.asarray(B["prep"]["hi"])
    Xi = np.where(np.isnan(X), med, X)
    Xw = np.clip(Xi, lo, hi)
    mu = np.asarray(B["prep"]["scaler_mean"]); sd = np.asarray(B["prep"]["scaler_scale"])
    return (Xw - mu) / sd


def predict_spectra(B, df_or_array, features=None):
    """把 231 维化合物谱映射到 50 维感官画像（连续 z）与 0-6 等级（P1 主口径）。"""
    feats = features or B["features"]
    if hasattr(df_or_array, "columns"):
        X = df_or_array[feats].values
    else:
        X = np.asarray(df_or_array, dtype=float)
    Xs = _transform(B, X)
    m = B["models"]
    z = (m["pls5"].predict(Xs) + m["extratrees300"].predict(Xs) + m["randomforest300"].predict(Xs)) / 3.0
    dims = B["target_dims"]
    a = np.array([B["calibration"]["a"][d] for d in dims], dtype=float)
    s = np.array([B["calibration"]["s"][d] for d in dims], dtype=float)
    g = np.clip(np.floor(1.0 + (z - a) / s + 0.5), 0, 6).astype(int)
    return z, g
