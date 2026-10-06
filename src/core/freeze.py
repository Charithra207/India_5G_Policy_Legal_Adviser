"""
Core freeze (release candidate)
===============================
    python -m src.core.freeze --check
    python -m src.core.freeze --record "bug fix: <what and why>"

The frozen core — Orchestrator, agent protocol and agents, Verifier,
cross-domain logic, Coordinator, output schema (data models) and scenario
logic — is fingerprinted in CORE_FREEZE.json.  tests/test_core_freeze.py
fails if any frozen file changes.  After the freeze only genuine bug fixes
are allowed: make the fix, then record it with a reason, which is appended
to the change log and re-fingerprints the files.

Hashes are taken over the text with line endings normalised, so a checkout
on Windows (CRLF) and Linux (LF) gives the same fingerprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FREEZE_FILE = ROOT / "CORE_FREEZE.json"

FROZEN = {
    "Orchestrator": ["src/core/orchestrator.py", "src/pipeline.py"],
    "Agent protocol and agents": ["src/agents/base_agent.py", "src/agents/technical_agent.py",
                                  "src/agents/policy_legal_agent.py", "src/agents/cybersecurity_agent.py",
                                  "src/agents/privacy_agent.py", "src/agents/critical_infra_agent.py",
                                  "src/agents/standards_agent.py", "src/agents/policy_gap_agent.py"],
    "Verifier": ["src/core/verifier.py"],
    "Cross-domain logic": ["src/core/cross_domain.py"],
    "Coordinator": ["src/core/coordinator.py"],
    "Output schema": ["src/core/models.py"],
    "Scenario logic": ["scenarios/scenario1_slicing_incident.py", "scenarios/scenario2_healthcare_5g.py",
                       "src/scenario/catalog.py", "src/scenario/engine.py"],
}


def fingerprint(rel: str) -> str:
    text = (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(text).hexdigest()


def current() -> dict[str, str]:
    return {rel: fingerprint(rel) for files in FROZEN.values() for rel in files}


def check() -> list[str]:
    """Frozen files whose content differs from the recorded fingerprint."""
    if not FREEZE_FILE.exists():
        return ["CORE_FREEZE.json missing"]
    recorded = json.loads(FREEZE_FILE.read_text(encoding="utf-8"))["files"]
    now = current()
    changed = [f"{rel}: changed since the freeze" for rel in now if recorded.get(rel) != now[rel]]
    changed += [f"{rel}: no longer frozen" for rel in recorded if rel not in now]
    return changed


def record(reason: str) -> dict:
    data = (json.loads(FREEZE_FILE.read_text(encoding="utf-8")) if FREEZE_FILE.exists()
            else {"frozen_at": datetime.now(timezone.utc).isoformat(), "components": FROZEN,
                  "rule": "Only genuine bug fixes after the freeze; each is recorded here with its reason.",
                  "change_log": []})
    changed = [rel for rel, h in current().items() if data.get("files", {}).get(rel) != h]
    data["change_log"].append({"at": datetime.now(timezone.utc).isoformat(), "reason": reason,
                               "files": changed if data.get("files") else ["(initial freeze)"]})
    data["components"] = FROZEN
    data["files"] = current()
    FREEZE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--record", metavar="REASON")
    args = ap.parse_args(argv)
    if args.record:
        data = record(args.record)
        print(f"recorded: {data['change_log'][-1]}")
        return 0
    problems = check()
    print("core frozen: unchanged" if not problems else "\n".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
