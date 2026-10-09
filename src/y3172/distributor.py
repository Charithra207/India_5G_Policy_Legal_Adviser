"""
D node and SINKs (Y.3172 clause 8.1)
====================================
The distributor identifies the SINKs for one incident and hands each its
part of the output, in this order:

  evidence_preservation  snapshot of the live network's state and logs, with
                         SHA-256 hashes, BEFORE anything is changed (CERT-In
                         direction (iv); the forensic order of the playbooks)
  remediation            the catalog playbook, run through the existing
                         incident-response engine (ir/engine.py): auto-safe
                         steps only in Basic, a human gate before every later
                         tier and a human yes for every later state-changing
                         step; in blocking mode nothing runs until a human
                         approves the policy node's hold
  regulatory_notices     draft notices with verified deadlines (notices.py)
  escalation             a hand-off to a human for whatever the pipeline did
                         not or could not act on

Only the SINKs listed in the intent run; escalation is always listed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Callable

from src.y3172.models import Prediction
from src.y3172.notices import draft_notices
from src.y3172.policy_node import ESCALATE, HOLD, PolicyDecision

TIERS = ("basic", "intermediate", "advanced")


class _TierLimiter:
    """The operator, as the remediation SINK sees them: no gate beyond the intent's max tier."""

    def __init__(self, human, max_tier: str) -> None:
        self.human, self.max_index = human, TIERS.index(max_tier)
        self.gates: list[tuple[str, str]] = []

    def gate(self, tier: str, message: str) -> str:
        if TIERS.index(tier) > self.max_index:
            choice = "stop"
        else:
            choice = self.human.gate(tier, message) if self.human else "stop"
        self.gates.append((tier, choice))
        return choice

    def confirm(self, description: str) -> bool:
        return bool(self.human and self.human.confirm(description))

    def manual(self, tier: str, commands: list[str]) -> str:
        return self.human.manual(tier, commands) if self.human else ""


def safe_search(query: str, categories: list[str] | None = None, k: int = 4) -> list[dict]:
    """KB search for the remediation agent that never breaks a run (e.g. no embedding model offline)."""
    try:
        from kb.retriever import search
        return search(query, categories=categories, k=k)
    except Exception:                                      # noqa: BLE001
        return []


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Distributor:
    def __init__(self, intent, catalog: dict, human, live_sim, run_dir: Path,
                 on_event: Callable | None = None, provider_factory: Callable | None = None) -> None:
        self.intent, self.catalog, self.human, self.sim = intent, catalog, human, live_sim
        self.run_dir = Path(run_dir)
        self.on_event = on_event
        self.attacks = {a["id"]: a for a in catalog["attacks"]}
        self._provider_factory = provider_factory

    # ------------------------------------------------------------------

    def dispatch(self, prediction: Prediction, decision: PolicyDecision, alerts: list[str],
                 detected_at) -> list[dict]:
        sinks = self.intent.sinks
        results: list[dict] = []
        remediation = None
        if decision.allows_remediation and "evidence_preservation" in sinks:
            results.append(self.preserve_evidence(decision.incident_id))
        if "remediation" in sinks and decision.allows_remediation:
            remediation = self.remediate(prediction, decision)
            results.append(remediation)
        if "regulatory_notices" in sinks and decision.obligations:
            results.append(self.notices(prediction, decision, alerts, detected_at, remediation))
        needs_human = (decision.decision == ESCALATE
                       or (remediation is not None and remediation["status"] != "resolved"))
        if "escalation" in sinks and needs_human:
            results.append(self.escalate(prediction, decision, remediation))
        return results

    # ------------------------------------------------------------------
    # SINK: evidence preservation
    # ------------------------------------------------------------------

    def preserve_evidence(self, incident_id: str) -> dict:
        out = self.run_dir / "evidence" / incident_id
        out.mkdir(parents=True, exist_ok=True)
        state = {k: v for k, v in copy.deepcopy(self.sim.state).items() if k != "logs"}
        files = {"state.json": json.dumps(state, indent=2, sort_keys=True)}
        for nf, lines in self.sim.state["logs"].items():
            files[f"logs/{nf}.log"] = "\n".join(lines) + ("\n" if lines else "")
        manifest = {}
        for name, text in files.items():
            path = out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            manifest[name] = _sha(text)
        (out / "MANIFEST.json").write_text(json.dumps({"incident_id": incident_id, "tick": self.sim.state["tick"],
                                                       "sha256": manifest}, indent=2), encoding="utf-8")
        return {"sink": "evidence_preservation", "status": "preserved",
                "detail": f"{len(manifest)} files hashed before any change",
                "paths": [str(out / "MANIFEST.json")], "sha256_of_manifest": _sha(json.dumps(manifest, sort_keys=True))}

    # ------------------------------------------------------------------
    # SINK: remediation through the incident-response engine
    # ------------------------------------------------------------------

    def _provider(self):
        if self._provider_factory is not None:
            return self._provider_factory()
        from ir.llm import OfflineProvider, get_provider
        return get_provider() if self.intent.remediation_agent == "anthropic" else OfflineProvider()

    def remediate(self, prediction: Prediction, decision: PolicyDecision) -> dict:
        from ir.engine import Incident
        attack = self.attacks[prediction.label]
        if decision.decision == HOLD:
            summary = "; ".join(f"{o['summary']} [{o['citation']}]" for o in decision.obligations[:4])
            why = "; ".join(f"{e['feature']}={e['value']} (normal≈{e['normal_mean']})"
                            for e in prediction.evidence[:4]) or "no feature beyond 3 standard deviations"
            question = (f"P node (blocking): apply the '{attack['name']}' playbook to the live network? "
                        f"Detected by {prediction.model_id} (confidence {prediction.confidence:.2f}). "
                        f"Model evidence: {why}. Obligations: {summary or 'none tagged'}")
            approved = bool(self.human and self.human.confirm(question))
            if not approved:
                return {"sink": "remediation", "status": "held", "detail": "blocking mode: the operator did not "
                        "approve remediation; nothing was changed", "approved": False}
        limiter = _TierLimiter(self.human, self.intent.remediation_max_tier)
        incident = Incident(prediction.label, provider=self._provider(), human=limiter, catalog=self.catalog,
                            sim=self.sim, search=safe_search, on_event=self.on_event)
        incident.policy_panel = {"obligations": [
            {"summary": o["summary"], "applies_when": o["applies_when"], "citation": o["citation"],
             "found": o["verified"]} for o in decision.obligations]}
        incident.phase = "basic"                  # the network is live: no reset, no injection
        incident.record("start", "system", "ml_detection",
                        args={"incident_id": decision.incident_id, "model": prediction.model_id},
                        result={"label": prediction.label, "confidence": round(prediction.confidence, 3)},
                        note=f"P node decision: {decision.decision} ({decision.mode})")
        report = incident.run()
        changes = [f"{e.action} {json.dumps(e.args)}" for e in incident.timeline
                   if e.state_changing and e.approved is not False and e.action not in ("inject", "ml_detection")]
        resolved = report["resolved"]
        return {"sink": "remediation", "status": "resolved" if resolved else incident.phase,
                "detail": f"{'resolved' if resolved else 'not resolved'} after tiers "
                          f"{list(incident.tier_outcomes)}; gates: {limiter.gates}",
                "resolved_in": next((t for t, o in incident.tier_outcomes.items() if o.get("resolved")), None),
                "changes": changes, "provider": getattr(incident.provider, "name", "?"),
                "paths": report.get("paths", []), "approved": True}

    # ------------------------------------------------------------------
    # SINK: regulatory notices
    # ------------------------------------------------------------------

    def notices(self, prediction: Prediction, decision: PolicyDecision, alerts: list[str], detected_at,
                remediation: dict | None) -> dict:
        attack = self.attacks.get(prediction.label, {})
        ran = "gnb" in attack.get("affected_nf", [])
        facts = {
            "name": attack.get("name", prediction.label),
            "detected_by": f"{prediction.model_id} (confidence {prediction.confidence:.2f})",
            "affected_nf": [n.upper() for n in attack.get("affected_nf", [])],
            "alerts": alerts[:5],
            "users": f"up to {self.sim.state['metrics'].get('registered_ues', 'unknown')} registered UEs in the "
                     "simulated network (to be narrowed down)",
            "area": "tracking area TA-4501 (simulated)" if ran else "core network (simulated)",
            "remedial_measures": (remediation or {}).get("changes", []),
        }
        out = self.run_dir / "notices" / decision.incident_id
        drafts = draft_notices(decision, detected_at, facts, out)
        return {"sink": "regulatory_notices", "status": "drafted",
                "detail": f"{sum('recipient' in d for d in drafts)} draft notices, "
                          f"{sum('action' in d for d in drafts)} preservation actions",
                "notices": drafts, "paths": [str(out)]}

    # ------------------------------------------------------------------
    # SINK: escalation to a human
    # ------------------------------------------------------------------

    def escalate(self, prediction: Prediction, decision: PolicyDecision, remediation: dict | None) -> dict:
        out = self.run_dir / "escalations"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{decision.incident_id}.md"
        why = list(decision.reasons)
        if remediation is not None and remediation["status"] != "resolved":
            why.append(f"Remediation status: {remediation['status']} — {remediation['detail']}")
        lines = [f"# Escalation — {decision.incident_id}", "",
                 f"- Prediction: **{prediction.label}** by {prediction.model_id} "
                 f"(confidence {prediction.confidence:.2f}, anomaly score {prediction.anomaly_score:.2f})",
                 f"- Policy node: {decision.decision} ({decision.mode} mode)", "", "## Why a human is needed", ""]
        lines += [f"- {w}" for w in why] + ["", "## Telemetry that deviates from normal operation", ""]
        lines += [f"- `{e['feature']}` = {e['value']} (normal ≈ {e['normal_mean']}, z = {e['z']})"
                  for e in prediction.evidence] or ["- (none above 3 standard deviations)"]
        lines += ["", "_Decision support for a training lab; not legal advice._"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"sink": "escalation", "status": "escalated", "detail": why[0] if why else "",
                "paths": [str(path)]}
