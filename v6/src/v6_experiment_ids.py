"""v6_experiment_ids.py — explicit experiment-id binding for the R00-R03 rerun.

WHY: three paper-side scripts (ablation_summary.py, headline_audit.py,
make_paper_figures.py) used to read HARD-CODED old experiment ids
(EXP-0003/0029/0033/0026/0004/...). A new rerun produces new ids, so a script
that keeps those literals would silently publish OLD numbers as if they were the
new evidence. This module makes the binding explicit: the caller has to pass
`MODELING_EXPERIMENT_IDS` (a JSON object of role -> EXP id), and a missing or
mismatched id is a NAMED failure, never a silent fallback.

Usage:
    from v6_experiment_ids import resolve
    IDS = resolve("headline_audit", ["q1_candidate", "q2_candidate"])
    path = f"experiments/{IDS['q1_candidate']}/metrics.json"
"""

from __future__ import annotations

import json
import os


class ExperimentIdError(SystemExit):
    """A named, non-silent refusal (SystemExit so a runner records a failure)."""


def _read_map() -> dict:
    raw = os.environ.get("MODELING_EXPERIMENT_IDS")
    if not raw:
        raise ExperimentIdError(
            "MODELING_EXPERIMENT_IDS is not set: this script must be told WHICH experiments to read. "
            "Pass a JSON object of role -> EXP id (e.g. "
            '\'{"q1_candidate":"EXP-00xx","q2_candidate":"EXP-00yy"}\'). '
            "Refusing to fall back to the historical hard-coded ids: they belong to the pre-rerun protocol.")
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExperimentIdError(f"MODELING_EXPERIMENT_IDS is not valid JSON: {exc}") from exc
    if not isinstance(mapping, dict):
        raise ExperimentIdError("MODELING_EXPERIMENT_IDS must be a JSON object of role -> EXP id")
    for role, value in mapping.items():
        if not isinstance(value, str) or not value.startswith("EXP-"):
            raise ExperimentIdError(f"role {role!r} does not name an experiment id: {value!r}")
    return mapping


def resolve(script: str, roles) -> dict:
    """Return {role: EXP id} for exactly the requested roles; refuse by name otherwise."""
    mapping = _read_map()
    missing = [r for r in roles if r not in mapping]
    if missing:
        raise ExperimentIdError(
            f"{script}: MODELING_EXPERIMENT_IDS is missing required role(s) {missing}; "
            f"available roles: {sorted(mapping)}")
    return {r: mapping[r] for r in roles}


def require_pinned(script: str, pinned: dict) -> dict:
    """For scripts whose audit table is pinned to specific ids.

    The environment must declare the SAME ids as the pinned table, otherwise the
    table would describe different experiments than the ones supplied. A new
    rerun must ship a new audit table, not reuse this one.
    """
    mapping = _read_map()
    wrong = {role: (want, mapping.get(role)) for role, want in pinned.items()
             if mapping.get(role) != want}
    if wrong:
        detail = "; ".join(f"{r}: table expects {w}, caller supplied {g}" for r, (w, g) in wrong.items())
        raise ExperimentIdError(
            f"{script}: the audit table is pinned to the pre-rerun experiments ({detail}). "
            "Register a NEW audit table for the new experiment ids instead of reusing this one.")
    return {r: mapping[r] for r in pinned}
