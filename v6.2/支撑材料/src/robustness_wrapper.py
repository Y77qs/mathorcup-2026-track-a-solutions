# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""robustness_wrapper.py — run a FROZEN model script with one declared parameter changed.

WHY. The confirmatory robustness plans need a real `param-perturbation` (and a
runner-verified seed receipt for `multiple-seeds`), but the frozen scripts expose only
`--repeat` and read their hyper-parameter grids from module-level constants. Editing the
frozen scripts would change the code hash of evidence already cited, so this wrapper is a
NEW file with its own hash: it loads the frozen script, overrides the named constants, and
calls its `main()` unchanged in the same process.

`--set NAME=<JSON>` replaces a module-level constant (e.g. `LAMBDAS=[0.05,0.5,5.0]`); the
override is recorded in the seed receipt and in the caller's `params`, so the perturbation
is auditable. Exactly one constant is expected per invocation.

Usage (through the experiment runner, so MODELING_* env vars are set):
    python src/robustness_wrapper.py --target src/q1_fix.py --set LAMBDAS=[0.05,0.5,5.0] --repeat 0
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def load_module(path: Path):
    name = "wrapped_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load wrapped module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _take(argv, flag, repeatable=False):
    values = []
    while flag in argv:
        index = argv.index(flag)
        if index + 1 >= len(argv):
            raise SystemExit(f"{flag} needs a value")
        values.append(argv[index + 1])
        argv = argv[:index] + argv[index + 2:]
        if not repeatable:
            break
    return values, argv


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets, argv = _take(argv, "--target")
    if len(targets) != 1:
        raise SystemExit("robustness_wrapper needs exactly one --target <project-relative script>")
    overrides, argv = _take(argv, "--set", repeatable=True)
    rest = argv

    import modeling_contract as mc

    receipt = mc.seed()
    if receipt is None:
        raise SystemExit("MODELING_SEED is not set: a seeded robustness run must declare its seed")

    path = (PROJECT / targets[0]).resolve()
    if not path.exists():
        raise SystemExit(f"wrapped target does not exist: {path}")
    module = load_module(path)
    if not hasattr(module, "main"):
        raise SystemExit(f"wrapped target has no main(): {path}")

    applied = {}
    for item in overrides:
        if "=" not in item:
            raise SystemExit(f"--set needs NAME=JSON, got {item!r}")
        name, raw = item.split("=", 1)
        if not hasattr(module, name):
            raise SystemExit(f"wrapped target has no module constant {name!r}")
        before = getattr(module, name)
        value = json.loads(raw)
        if isinstance(value, list):
            value = tuple(value)
        # A path constant must stay a Path: the frozen scripts call .read_bytes()/.relative_to() on it.
        if isinstance(before, Path) and isinstance(value, str):
            value = Path(value) if Path(value).is_absolute() else (PROJECT / value)
        applied[name] = {"before": repr(before), "after": repr(value)}
        setattr(module, name, value)
    if applied:
        print("[robustness_wrapper] overrides: " + json.dumps(applied, ensure_ascii=False))

    saved = sys.argv
    sys.argv = [str(path)] + rest
    try:
        try:
            result = module.main(rest)
        except TypeError:
            result = module.main()
    finally:
        sys.argv = saved
    return _exit_code(result)


def _exit_code(result) -> int:
    if isinstance(result, bool):
        return 0 if result else 1
    if isinstance(result, int):
        return result
    if isinstance(result, dict):
        return 0 if result.get("ok", True) is not False else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
