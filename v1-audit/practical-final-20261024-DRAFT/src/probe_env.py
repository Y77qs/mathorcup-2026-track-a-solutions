"""探针：发现 modeling_experiment 的运行时契约（不产出任何科学结论）。

目的：确认脚本被调用时的 cwd、环境变量、可导入的 modeling_contract 接口，
      以便后续实验脚本按契约输出 metrics/predictions/figures。
"""
import json
import os
import sys
from pathlib import Path

info = {
    "cwd": os.getcwd(),
    "argv": sys.argv,
    "python": sys.executable,
    "env_modeling": {k: v for k, v in sorted(os.environ.items()) if "MODEL" in k.upper() or "EXP" in k.upper()},
    "sys_path_head": sys.path[:12],
}

try:
    import modeling_contract as mc  # noqa
    info["modeling_contract"] = {
        "file": getattr(mc, "__file__", None),
        "dir": [a for a in dir(mc) if not a.startswith("_")],
    }
except Exception as e:  # noqa
    info["modeling_contract"] = {"error": f"{type(e).__name__}: {e}"}

try:
    import modeling_contract as mc  # noqa
    if hasattr(mc, "describe"):
        info["modeling_contract"]["describe"] = str(mc.describe())[:4000]
except Exception:
    pass

Path("outputs/probe").mkdir(parents=True, exist_ok=True)
Path("outputs/probe/experiment_env.json").write_text(
    json.dumps(info, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(info, ensure_ascii=False, indent=2, default=str)[:4000])
