"""实验产物桥接：runner 内用 modeling_contract，runner 外落到 outputs/<area>/。"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

try:
    import modeling_contract as _mc  # type: ignore
    IN_RUNNER = True
except Exception:  # noqa
    _mc = None
    IN_RUNNER = False


def experiment_id():
    return os.environ.get("EXPERIMENT_ID") or os.environ.get("MODELING_EXPERIMENT_ID")


def _numeric(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, (bool, np.bool_)):
            out[k] = int(v)
        elif isinstance(v, (int, float, np.integer, np.floating)):
            fv = float(v)
            if math.isfinite(fv):
                out[k] = fv
        elif isinstance(v, dict):
            out.update({f"{k}.{kk}": vv for kk, vv in _numeric(v).items()})
    return out


def _area_dir(area: str) -> Path:
    p = ROOT / "outputs" / area
    p.mkdir(parents=True, exist_ok=True)
    return p


def metrics(d: dict, area: str = "q1") -> dict:
    num = _numeric(d)
    if IN_RUNNER:
        return _mc.emit_metrics(num)
    p = _area_dir(area) / "metrics.json"
    p.write_text(json.dumps(num, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(p)}


def predictions(df: pd.DataFrame, name: str = "predictions.csv", area: str = "q1") -> str:
    if IN_RUNNER:
        return _mc.emit_predictions(df, name)
    p = _area_dir(area) / name
    df.to_csv(p, index=False, encoding="utf-8")
    return str(p)


def output(name: str, value, area: str = "q1") -> dict:
    if IN_RUNNER and hasattr(_mc, "emit_output"):
        return _mc.emit_output(name, value)
    p = _area_dir(area) / f"{name}.json"
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"path": str(p)}
