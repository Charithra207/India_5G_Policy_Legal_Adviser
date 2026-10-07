"""
Load and validate catalog/attacks.yaml.
=======================================
The catalog is editable YAML: add an attack by adding an entry, no code
change needed.  `load_catalog()` checks every entry against the simulator so
a typo fails loudly instead of misleading the responder:

  * every action names a real simulator function (sim.engine.FUNCTIONS);
  * `is_state_changing` matches that function's kind (diagnostics are
    read-only, remediations change state);
  * `auto_safe` is only set on state-changing steps (the steps the Basic tier
    may run without asking);
  * success checks and `resolved_when` call diagnostics only;
  * policy categories and retrieval categories exist in kb/categories.py.

Step arguments may refer to an earlier finding instead of a hard-coded value:
    args: {nf: amf, source: {from: {fn: get_top_talkers, args: {nf: amf}, path: top.0.source}}}
`resolve_args()` evaluates such references against the simulator at run time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kb.categories import CATEGORIES
from sim.engine import FUNCTIONS, call, lookup

CATALOG_PATH = Path(__file__).resolve().parent / "attacks.yaml"
TIERS = ("basic", "intermediate", "advanced")


class CatalogError(ValueError):
    pass


def _check_condition(where: str, cond: dict) -> None:
    if FUNCTIONS.get(cond.get("fn")) != "diagnostic":
        raise CatalogError(f"{where}: check must call a diagnostic, not {cond.get('fn')!r}")
    if cond.get("op") not in ("==", "!=", "<", "<=", ">", ">=", "empty", "not_contains", "contains"):
        raise CatalogError(f"{where}: unknown op {cond.get('op')!r}")


def _check_args(where: str, args: dict) -> None:
    for key, value in (args or {}).items():
        if isinstance(value, dict) and "from" in value:
            _check_condition(f"{where}.args.{key}", {**value["from"], "op": "=="})


def validate(catalog: dict) -> dict:
    ids = set()
    for attack in catalog.get("attacks", []):
        aid = attack.get("id")
        if not aid or aid in ids:
            raise CatalogError(f"missing or duplicate attack id {aid!r}")
        ids.add(aid)
        for field in ("name", "description", "affected_nf", "enisa_ref", "threegpp_ref", "policy_tags",
                      "retrieval_categories", "resolved_when", "playbook"):
            if field not in attack:
                raise CatalogError(f"{aid}: missing field {field!r}")
        cats = attack["retrieval_categories"] + attack["policy_tags"].get("categories", [])
        bad = [c for c in cats if c not in CATEGORIES]
        if bad:
            raise CatalogError(f"{aid}: unknown categories {bad}")
        for i, cond in enumerate(attack["resolved_when"]):
            _check_condition(f"{aid}.resolved_when[{i}]", cond)
        for tier in TIERS:
            steps = attack["playbook"].get(tier, [])
            if not steps:
                raise CatalogError(f"{aid}: tier {tier!r} has no steps")
            if tier == "basic" and not 5 <= len(steps) <= 10:
                raise CatalogError(f"{aid}: basic tier must have 5-10 steps, has {len(steps)}")
            for step in steps:
                where = f"{aid}.{tier}.{step.get('id')}"
                fn = step.get("action", {}).get("fn")
                kind = FUNCTIONS.get(fn)
                if kind is None:
                    raise CatalogError(f"{where}: unknown simulator function {fn!r}")
                if step.get("is_state_changing") != (kind == "remediation"):
                    raise CatalogError(f"{where}: is_state_changing must be {kind == 'remediation'} for {fn}")
                if step.get("auto_safe") and kind != "remediation":
                    raise CatalogError(f"{where}: auto_safe applies to state-changing steps only")
                _check_args(where, step["action"].get("args", {}))
                if step.get("success_check"):
                    _check_condition(f"{where}.success_check", step["success_check"])
    return catalog


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    return validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def get_attack(attack_id: str, catalog: dict | None = None) -> dict:
    catalog = catalog or load_catalog()
    for attack in catalog["attacks"]:
        if attack["id"] == attack_id:
            return attack
    raise KeyError(f"attack {attack_id!r} not in catalog; known: {[a['id'] for a in catalog['attacks']]}")


def resolve_args(sim, args: dict | None) -> dict[str, Any]:
    """Replace {from: {fn, args, path}} references with live diagnostic values."""
    out = {}
    for key, value in (args or {}).items():
        if isinstance(value, dict) and "from" in value:
            ref = value["from"]
            value = lookup(call(sim, ref["fn"], ref.get("args")), ref.get("path", ""))
        out[key] = value
    return out
