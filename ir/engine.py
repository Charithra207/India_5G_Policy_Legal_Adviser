"""
Tiered incident response with human-in-the-loop gates.
======================================================
State machine for one incident:

    start → BASIC (agent, automatic) ──resolved──→ RESOLVED
                 │ not resolved
                 ▼
       gate "Intermediate tier?"  [1] agent  [2] operator  [3] stop
                 ▼
            INTERMEDIATE ──resolved──→ RESOLVED
                 │ not resolved
                 ▼
       gate "Advanced tier?"      [1] agent  [2] operator  [3] stop
                 ▼
             ADVANCED ──resolved──→ RESOLVED   │ not resolved → EXHAUSTED

Every action goes through `Incident.execute`, which enforces the rules:
  * diagnostics (read-only) always run;
  * in BASIC, a state-changing action runs only if it is a playbook step
    marked `auto_safe` (safe and idempotent) — anything else is refused;
  * in INTERMEDIATE/ADVANCED run by the agent, each state-changing action is
    shown to the operator and needs an explicit yes;
  * every action, approval and result is recorded in the timeline.
"Resolved" is decided by the catalog's `resolved_when` checks against the
simulator — never by the agent's own claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from catalog.loader import TIERS, get_attack, load_catalog, resolve_args
from sim.cli import format_args
from sim.engine import FUNCTIONS, Sim, call, check, work_dir
from sim.inject import inject


class Human(Protocol):
    """The operator. CLI, web UI and tests each provide one."""

    def gate(self, tier: str, message: str) -> str: ...            # "agent" | "manual" | "stop"
    def confirm(self, description: str) -> bool: ...               # approve one state-changing action
    def manual(self, tier: str, commands: list[str]) -> str: ...   # run these yourself; paste results


@dataclass
class Event:
    at: str
    tier: str
    actor: str               # agent | operator | system
    action: str
    args: dict = field(default_factory=dict)
    state_changing: bool = False
    approved: bool | None = None
    result: dict | str | None = None
    note: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


class Incident:
    def __init__(self, attack_id: str, provider=None, human: Human | None = None,
                 catalog: dict | None = None, sim: Sim | None = None,
                 search: Callable | None = None, on_event: Callable[[Event], None] | None = None) -> None:
        from ir.llm import get_provider
        self.attack = get_attack(attack_id, catalog or load_catalog())
        self.sim = sim or Sim()
        self.human = human
        self.provider = provider or get_provider()
        self.search = search
        self.on_event = on_event            # e.g. the CLI prints each event as it happens
        self.timeline: list[Event] = []
        self.phase = "new"
        self.tier_outcomes: dict[str, dict] = {}
        self.policy_panel: dict = {}

    # ------------------------------------------------------------------

    def record(self, tier: str, actor: str, action: str, **kw) -> Event:
        event = Event(_now(), tier, actor, action, **kw)
        self.timeline.append(event)
        if self.on_event:
            self.on_event(event)
        return event

    def resolution(self) -> tuple[bool, list[dict]]:
        details = []
        for cond in self.attack["resolved_when"]:
            ok, actual = check(self.sim, cond)
            details.append({**cond, "actual": actual, "ok": ok})
        return all(d["ok"] for d in details), details

    def resolved(self) -> bool:
        return self.resolution()[0]

    def start(self) -> dict:
        """Reset the sim, inject the attack, build both panels."""
        from ir.policy import build_policy_panel
        self.sim.reset()
        result = inject(self.sim, self.attack["id"])
        self.record("start", "system", "inject", args={"attack": self.attack["id"]},
                    state_changing=True, result={"alerts": result["alerts"]})
        self.policy_panel = build_policy_panel(self.attack, self.search)
        self.phase = "basic"
        return {"policy": self.policy_panel, "technical": self.technical_panel()}

    def technical_panel(self) -> dict:
        return {"attack": {k: self.attack[k] for k in ("id", "name", "description", "affected_nf")},
                "health": self.sim.get_nf_health(), "alerts": self.sim.get_alerts()["alerts"],
                "tiers": {t: [{"id": s["id"], "description": s["description"], "fn": s["action"]["fn"],
                               "state_changing": s["is_state_changing"], "auto_safe": bool(s.get("auto_safe"))}
                              for s in self.attack["playbook"][t]] for t in TIERS}}

    # ------------------------------------------------------------------
    # The single gate every action passes through
    # ------------------------------------------------------------------

    def _auto_safe(self, fn: str, args: dict) -> dict | None:
        for step in self.attack["playbook"]["basic"]:
            if step.get("auto_safe") and step["action"]["fn"] == fn and \
                    resolve_args(self.sim, step["action"].get("args")) == args:
                return step
        return None

    def execute(self, tier: str, fn: str, args: dict | None, reason: str = "", actor: str = "agent") -> dict:
        args = dict(args or {})
        kind = FUNCTIONS.get(fn)
        if kind is None:
            return {"ok": False, "error": f"unknown function {fn!r}"}
        if kind == "remediation":
            if tier == "basic":
                if not self._auto_safe(fn, args):
                    self.record(tier, actor, fn, args=args, state_changing=True, approved=False,
                                note="refused: not an auto-safe Basic step")
                    return {"ok": False, "error": "refused: only playbook steps marked auto_safe may change "
                                                  "state in the Basic tier; escalate to Intermediate"}
                approved = True
            else:
                description = f"{fn}({json.dumps(args)})" + (f" — {reason}" if reason else "")
                approved = bool(self.human and self.human.confirm(description))
                if not approved:
                    self.record(tier, actor, fn, args=args, state_changing=True, approved=False,
                                note="declined by operator")
                    return {"ok": False, "error": "operator declined this action"}
        else:
            approved = None
        result = call(self.sim, fn, args)
        self.record(tier, actor, fn, args=args, state_changing=kind == "remediation", approved=approved,
                    result=result, note=reason)
        return result

    # ------------------------------------------------------------------
    # Tiers
    # ------------------------------------------------------------------

    def manual_commands(self, tier: str) -> list[str]:
        cmds = []
        for step in self.attack["playbook"][tier]:
            args = resolve_args(self.sim, step["action"].get("args"))
            cmds.append(f"# {step['id']}: {step['description']}\n"
                        f"python -m sim.cli {step['action']['fn']} {format_args(args)}".rstrip())
        return cmds

    def run_tier(self, tier: str, mode: str = "agent") -> bool:
        self.phase = tier
        if mode == "manual":
            commands = self.manual_commands(tier)
            self.record(tier, "system", "handed to operator", note=f"{len(commands)} steps printed")
            pasted = self.human.manual(tier, commands) if self.human else ""
            self.sim.load()                                  # pick up the operator's changes
            interpretation = self.provider.interpret(self, tier, pasted)
            self.record(tier, "operator", "pasted results", result=pasted[:2000], note=interpretation)
            outcome = {"mode": "manual", "summary": interpretation}
        else:
            outcome = {"mode": "agent", **self.provider.run_tier(self, tier)}
        ok, details = self.resolution()
        outcome.update(resolved=ok, checks=details)
        self.tier_outcomes[tier] = outcome
        self.record(tier, "system", "resolution check", result={"resolved": ok, "checks": details})
        return ok

    def gate_message(self, tier: str) -> str:
        previous = "Basic" if tier == "intermediate" else "Intermediate"
        return f"{previous} steps did not resolve it. {tier.title()} tier?"

    def advance(self, tier: str, choice: str) -> str:
        """Apply the operator's gate choice for `tier`; returns the new phase."""
        self.record(tier, "operator", "gate", result=choice)
        if choice == "stop":
            self.phase = "stopped"
        elif self.run_tier(tier, choice):
            self.phase = "resolved"
        elif tier == TIERS[-1]:
            self.phase = "exhausted"
        return self.phase

    def run(self) -> dict:
        """Full flow: Basic automatically, then a gate before each further tier."""
        if self.phase == "new":
            self.start()
        if self.run_tier("basic", "agent"):
            self.phase = "resolved"
            return self.final_report()
        for tier in TIERS[1:]:
            choice = self.human.gate(tier, self.gate_message(tier)) if self.human else "stop"
            if self.advance(tier, choice) in ("resolved", "stopped", "exhausted"):
                break
        return self.final_report()

    def final_report(self) -> dict:
        from ir.report import build_report
        report = build_report(self)
        out = work_dir() / "reports"
        out.mkdir(parents=True, exist_ok=True)
        stem = f"{self.attack['id']}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        (out / f"{stem}.md").write_text(report["markdown"], encoding="utf-8")
        (out / f"{stem}.json").write_text(json.dumps(report["data"], indent=2, default=str), encoding="utf-8")
        report["paths"] = [str(out / f"{stem}.md"), str(out / f"{stem}.json")]
        return report


def report_dir() -> Path:
    return work_dir() / "reports"
