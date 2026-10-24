"""受控环境探针：查清实验运行器如何注入 modeling_contract 与产物目录。

这是**环境探测**，不产生科学结论；登记时带真实 datasetId/features，不绕过门禁。
输出：outputs/probe/experiment_env.json（env/cwd/模块定位/写入探测结果）
"""
import json
import os
import sys
import traceback
from pathlib import Path

info = {
    "cwd": os.getcwd(),
    "script": str(Path(__file__).resolve()),
    "argv": sys.argv,
    "python": sys.executable,
    "env_all_keys": sorted(os.environ.keys()),
    "env_modeling": {k: v for k, v in sorted(os.environ.items())
                     if any(t in k.upper() for t in ("MODEL", "EXP", "VMU", "CONTEST", "RUN"))},
    "sys_path": sys.path,
    "probes": {},
}

# 1) 定位 modeling_contract
try:
    import modeling_contract as mc  # noqa
    info["probes"]["modeling_contract"] = {
        "file": getattr(mc, "__file__", None),
        "public": [a for a in dir(mc) if not a.startswith("_")],
        "signatures": {},
    }
    import inspect
    for name in info["probes"]["modeling_contract"]["public"]:
        try:
            info["probes"]["modeling_contract"]["signatures"][name] = str(
                inspect.signature(getattr(mc, name)))
        except Exception:
            pass
except Exception as e:  # noqa
    info["probes"]["modeling_contract"] = {"error": f"{type(e).__name__}: {e}",
                                           "tb": traceback.format_exc()[-800:]}

# 2) 探测可写目录：cwd / 项目 experiments 下最新的 EXP 目录
cands = [os.getcwd()]
proj = Path(__file__).resolve().parents[1]
exp_root = proj / "experiments"
if exp_root.exists():
    dirs = sorted(exp_root.glob("EXP-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    cands += [str(d) for d in dirs[:3]]
info["probes"]["candidate_write_dirs"] = cands
wrote = []
for d in cands:
    try:
        p = Path(d) / "_probe_write_test.json"
        p.write_text(json.dumps({"ok": True, "d": d}), encoding="utf-8")
        wrote.append(str(p))
        p.unlink()
    except Exception as e:  # noqa
        wrote.append(f"FAIL {d}: {type(e).__name__}")
info["probes"]["writable"] = wrote

# 3) 若 modeling_contract 可用，尝试用它写一份最小 metrics（证明通道可用）
try:
    import modeling_contract as mc  # noqa
    if hasattr(mc, "emit_metrics"):
        mc.emit_metrics({"probe": 1.0, "note": "environment probe, not a scientific metric"})
        info["probes"]["emit_metrics_called"] = True
    else:
        info["probes"]["emit_metrics_called"] = "no emit_metrics attribute"
except Exception as e:  # noqa
    info["probes"]["emit_metrics_called"] = f"FAIL {type(e).__name__}: {e}"

out = proj / "outputs/probe/experiment_env.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(info, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps({k: info["probes"][k] for k in ("modeling_contract", "writable",
                                                 "emit_metrics_called")},
                 ensure_ascii=False, indent=2, default=str)[:3000])
