"""统一的实验产物桥接层（所有 EXP 脚本必须经由它输出）。

为什么需要它：`modeling_contract` 只在 `modeling_experiment run` 的进程里通过 sys.path 注入；
而 `run-script`（开发调试）里没有。本模块两条路径都支持：

  in-runner  : import modeling_contract，调用 emit_metrics / emit_predictions / emit_output / save_figure
  out-runner : 退化为直接写文件（默认 outputs/<area>/），保证调试产物与正式产物同格式

契约事实（由 src/probe_contract.py, EXP-0005 实测）：
  * cwd = experiments/<EXP>/；环境变量有 EXPERIMENT_ID / EXPERIMENT_DIR /
    MODELING_EXPERIMENT_DIR / MODELING_METRICS_PATH / MODELING_DATA_FILE /
    MODELING_ASSIGNMENT_FILE / MODELING_DATASET_ID / MODELING_CONFIG_SHA256 …
  * `emit_metrics(metrics: dict)` **只接受有限数值**（字符串会被具名拒绝），
    因此结构化信息必须走 `emit_output(name, value)`；
  * `emit_predictions(frame, name='predictions.csv')` 接受 DataFrame；
  * `save_figure(figure, name)` 接受 matplotlib figure。
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

try:  # 仅在实验运行器内可用
    import modeling_contract as _mc  # type: ignore
    IN_RUNNER = True
except Exception:  # noqa
    _mc = None
    IN_RUNNER = False


def experiment_id() -> str | None:
    return os.environ.get("EXPERIMENT_ID") or os.environ.get("MODELING_EXPERIMENT_ID")


def experiment_dir() -> Path | None:
    d = os.environ.get("MODELING_EXPERIMENT_DIR") or os.environ.get("EXPERIMENT_DIR")
    return Path(d) if d else None


def _fallback_dir(area: str) -> Path:
    p = ROOT / "outputs" / area
    p.mkdir(parents=True, exist_ok=True)
    return p


def _numeric_only(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(_numeric_only(v, key))
        elif isinstance(v, (bool, np.bool_)):
            out[key] = int(v)
        elif isinstance(v, (int, float, np.integer, np.floating)):
            fv = float(v)
            if math.isfinite(fv):
                out[key] = fv
        # 其它类型（字符串/列表/NaN）不进入 metrics，改走 emit_output
    return out


def emit_metrics(metrics: dict, area: str = "misc") -> dict:
    """写 metrics。自动丢弃非数值项（保证 runner 不因类型被拒）。"""
    num = _numeric_only(metrics)
    if IN_RUNNER:
        return _mc.emit_metrics(num)
    p = _fallback_dir(area) / "metrics.json"
    p.write_text(json.dumps(num, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(p), "n_metrics": len(num)}


def emit_output(name: str, value, area: str = "misc") -> dict:
    """结构化产物（逐维数组、fold 记录、模型参数等）走这里。"""
    if IN_RUNNER and hasattr(_mc, "emit_output"):
        return _mc.emit_output(name, value)
    p = _fallback_dir(area) / f"{name}.json"
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"path": str(p)}


def emit_predictions(frame: pd.DataFrame, name: str = "predictions.csv",
                     area: str = "misc") -> str:
    if IN_RUNNER and hasattr(_mc, "emit_predictions"):
        return _mc.emit_predictions(frame, name)
    p = _fallback_dir(area) / name
    frame.to_csv(p, index=False, encoding="utf-8")
    return str(p)


def save_figure(fig, name: str, area: str = "misc") -> dict:
    if IN_RUNNER and hasattr(_mc, "save_figure"):
        return _mc.save_figure(fig, name)
    p = _fallback_dir(area) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, bbox_inches="tight")
    return {"path": str(p)}


def dataset_path() -> Path:
    p = os.environ.get("MODELING_DATA_FILE")
    return Path(p) if p else ROOT / "data/clean/model_table.csv"


def assignment_path() -> Path:
    p = os.environ.get("MODELING_ASSIGNMENT_FILE")
    return Path(p) if p else ROOT / "data/splits/SPLIT-0002/assignment.csv"


def load_split() -> tuple[pd.DataFrame, str]:
    """返回 (beer, split) 并与 1.csv 的行序解耦（用 row_index 映射到 beer）。"""
    from common import RAW
    import pandas as _pd
    p = assignment_path()
    a = _pd.read_csv(p)
    order = _pd.read_csv(RAW / "1.csv")["beer"].tolist()
    if "row_index" in a.columns:
        a["beer"] = [order[int(i)] for i in a["row_index"].astype(int)]
    return a[["beer", "split"]], p.parent.name
