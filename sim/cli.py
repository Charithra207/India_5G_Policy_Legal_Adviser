"""
Operator command line for the simulated 5G core (the "I'll run it" path).
=========================================================================
    python -m sim.cli list
    python -m sim.cli get_metrics nf=amf
    python -m sim.cli rate_limit_nf nf=amf limit=1000

Arguments are key=value (values are read as JSON when they parse — numbers,
true/false — and as text otherwise), so the same command works in cmd,
PowerShell and bash.  A single JSON object is accepted too.

Loads <work>/state.json, runs one simulator function, saves the state and
prints the result as JSON.  The simulator is in-process Python; nothing here
touches a real network.
"""

from __future__ import annotations

import json
import sys

from sim.engine import FUNCTIONS, Sim, call


def _value(text: str):
    try:
        return json.loads(text)
    except ValueError:
        if text.startswith("[") and text.endswith("]"):     # PowerShell 5.1 strips inner quotes
            return [v.strip().strip("'\"") for v in text[1:-1].split(",") if v.strip()]
        return text


def parse_args(items: list[str]) -> dict:
    if len(items) == 1 and items[0].lstrip().startswith("{"):
        return json.loads(items[0])
    out = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"expected key=value, got {item!r}")
        key, value = item.split("=", 1)
        out[key] = _value(value)
    return out


def format_args(args: dict) -> str:
    """The inverse of parse_args, for printing commands an operator can paste."""
    parts = []
    for key, value in args.items():
        text = value if isinstance(value, str) and _value(value) == value else json.dumps(value, separators=(",", ":"))
        parts.append(f"{key}={text}")
    return " ".join(parts)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("list", "-h", "--help"):
        for name, kind in FUNCTIONS.items():
            print(f"{kind:<12} {name}")
        return 0
    try:
        sim = Sim.resume()
    except FileNotFoundError:
        print("no simulation state yet: run `python -m sim.inject --attack <id>` first")
        return 1
    try:
        args = parse_args(argv[1:])
    except ValueError as exc:
        print(f"bad arguments: {exc}")
        return 1
    result = call(sim, argv[0], args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
