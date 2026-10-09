"""
P node: policy and legal checks on the model output (Y.3172 clause 8.1)
=======================================================================
Y.3172 (clause 8.1, NOTE 5): the policy node applies policies to the model
output "to minimize impact when the output of machine learning is applied
to a live ML underlay network".  Here the policies are the operator's own
rules plus Indian law, and the policy node is the policy & legal adviser:

  1. Operator rules (from the intent)
       - an "unknown_anomaly" is never acted on automatically;
       - a prediction below `policy.min_confidence` is never acted on
         automatically;
       - a class outside the intent's target classes is never acted on.
     Each of these sends the detection to a human (escalation SINK).
  2. Indian obligations for the predicted incident class, from the attack
     catalog (catalog/attacks.yaml).  Each obligation's phrase is looked up
     word for word in the cited document in the committed index
     (kb/index) — found: file, page and passage; not found: marked
     UNVERIFIED and never presented as fact.
  3. The specialist-agent swarm (src/): the detection is turned into a
     scenario chunk and run through the Orchestrator, agents, Verifier and
     Coordinator, exactly as a scenario chunk is.  Its assessment, with
     verifier outcomes, goes into the audit trail.
  4. Mode (the intent's `policy.mode`) — the "advisory vs blocking" choice
     the Sandbox India register names as a Y.3172 policy-node gap:
       blocking   remediation is HELD until a human approves it, having
                  seen the obligations;
       advisory   remediation proceeds; the obligations are attached.
     Either way the existing human gates of the incident-response engine
     (auto-safe steps only in Basic, approval for every later step) apply.

Decision support for a training lab; legal interpretation needs a qualified
human.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from src.y3172.models import NORMAL, UNKNOWN, Prediction

HOLD = "hold_for_approval"
PROCEED = "proceed_annotated"
ESCALATE = "escalate"
NO_ACTION = "no_action"


@dataclass
class PolicyDecision:
    incident_id: str
    label: str
    mode: str
    decision: str
    reasons: list[str]
    obligations: list[dict] = field(default_factory=list)
    adviser: dict | None = None
    rules_applied: list[str] = field(default_factory=list)
    detected_at: str = ""

    @property
    def allows_remediation(self) -> bool:
        return self.decision in (HOLD, PROCEED)

    def as_dict(self) -> dict:
        return {"incident_id": self.incident_id, "label": self.label, "mode": self.mode,
                "decision": self.decision, "reasons": self.reasons, "obligations": self.obligations,
                "adviser": self.adviser, "rules_applied": self.rules_applied, "detected_at": self.detected_at}


def _quote(text: str, phrase: str, width: int = 200) -> str:
    flat = " ".join(text.split())
    i = flat.lower().find(" ".join(phrase.lower().split()))
    if i < 0:
        return flat[: 2 * width]
    s, e = max(0, i - width), min(len(flat), i + len(phrase) + width)
    return ("…" if s else "") + flat[s:e] + ("…" if e < len(flat) else "")


def verified_obligations(attack: dict) -> list[dict]:
    """The attack's tagged obligations, each checked word for word in its source."""
    try:
        from kb.retriever import cite, find_passage
    except ImportError as exc:                              # pragma: no cover
        find_passage, cite, error = None, None, str(exc)
    out = []
    for ob in attack["policy_tags"].get("obligations", []):
        hit, note = None, ""
        if find_passage is not None:
            try:
                hit = find_passage(ob["doc"], ob["phrase"])
            except FileNotFoundError as exc:                # index not present
                note = f"index not available ({exc})"
        else:
            note = f"retriever unavailable ({error})"
        out.append({
            "id": ob["id"], "summary": ob["summary"], "applies_when": ob.get("applies_when", ""),
            "doc": ob["doc"], "phrase": ob["phrase"], "verified": hit is not None,
            "citation": cite(hit) if hit else f"{ob['doc']} — UNVERIFIED{': ' + note if note else ' (phrase not found)'}",
            "passage": _quote(hit["text"], ob["phrase"]) if hit else "",
        })
    return out


def _personal_data(attack: dict) -> bool:
    ids = {o["id"] for o in attack["policy_tags"].get("obligations", [])}
    return bool(ids & {"dpdp_act_s8_6", "dpdp_rules_rule7_72h"}) or \
        "data_protection" in attack.get("retrieval_categories", [])


def adviser_chunk(incident_id: str, prediction: Prediction, attack: dict, alerts: list[str],
                  when: datetime, hospital_affected: bool):
    """The detection as a scenario chunk for the specialist-agent swarm."""
    from src.core.models import ScenarioChunk
    parts = [
        f"Machine-learning detection on the live 5G core: suspected {attack['name']} "
        f"(model {prediction.model_id}, confidence {prediction.confidence:.2f}).",
        f"Affected network functions: {', '.join(n.upper() for n in attack['affected_nf'])}.",
        "Security indicator: unusual activity consistent with a cyber attack on the network.",
    ]
    if _personal_data(attack):
        parts.append("Subscriber personal data may be involved.")
    if hospital_affected:
        parts.append("The affected network carries a hospital slice (critical service).")
    parts.append("Question: which reporting and escalation obligations apply to the operator?")
    facts = [f"Alert: {a}" for a in alerts[:4]] + [
        f"Telemetry: {e['feature']} = {e['value']} (normal ≈ {e['normal_mean']})" for e in prediction.evidence[:4]]
    return ScenarioChunk(chunk_index=0, chunk_id=incident_id, timestamp=when.isoformat(),
                         description=" ".join(parts), new_facts=facts)


def summarise_record(record) -> dict:
    """The swarm's assessment, compact, for the report (the full record goes to the audit trail)."""
    a = record.coordinator_assessment
    outcomes: dict[str, int] = {}
    for vc in record.verifier_result.verified_claims:
        outcomes[vc.outcome.value] = outcomes.get(vc.outcome.value, 0) + 1
    return {
        "active_agents": [x.value for x in record.active_agents],
        "claims": sum(len(f.claims) for f in record.agent_findings),
        "verifier_outcomes": outcomes,
        "evidence_backed_conclusions": a.evidence_backed_conclusions[:5],
        "uncertain_conclusions": a.uncertain_conclusions[:5],
        "conflicting_findings": a.conflicting_findings[:5],
        "potential_policy_gaps": a.potential_policy_gaps[:5],
        "relevant_institutions": a.relevant_institutions[:8],
        "open_questions": a.open_questions[:5],
        "counts": {k: len(getattr(a, k)) for k in ("evidence_backed_conclusions", "uncertain_conclusions",
                                                   "conflicting_findings", "potential_policy_gaps")},
        "human_review_required": a.human_review_required,
    }


class PolicyNode:
    """
    `pipeline_factory()` returns a fresh src.pipeline.Pipeline for one
    incident (each incident is its own scenario).  By default the live
    knowledge bases are used when they have been built, the stubs otherwise
    (the agents then say that no passage was retrieved).
    """

    def __init__(self, intent, catalog: dict, pipeline_factory: Callable | None = None) -> None:
        self.intent = intent
        self.catalog = catalog
        self.attacks = {a["id"]: a for a in catalog["attacks"]}
        self._factory = pipeline_factory
        self._registry = None
        self.kb_status: dict[str, bool] = {}

    def _pipeline(self):
        if self._factory is not None:
            return self._factory()
        from src.pipeline import Pipeline
        if self._registry is None:
            try:
                from src.rag.registry import build_registry
                self._registry = build_registry()
            except Exception:                               # noqa: BLE001 — fall back to stubs
                from src.knowledge_base.kb_registry import KBRegistry
                self._registry = KBRegistry()
            self.kb_status = self._registry.status_report()
        return Pipeline(self._registry)

    def assess(self, incident_id: str, prediction: Prediction, alerts: list[str],
               when: datetime, hospital_affected: bool = False) -> tuple[PolicyDecision, object | None]:
        """Returns the decision and the swarm's AuditRecord (None if the swarm did not run)."""
        mode, label = self.intent.policy.mode, prediction.label
        rules, reasons = [], []
        if label == NORMAL:
            return PolicyDecision(incident_id, label, mode, NO_ACTION, ["normal operation"],
                                  detected_at=when.isoformat()), None
        if label == UNKNOWN:
            rules.append("unknown_anomaly_to_human")
            reasons.append("The telemetry is abnormal but matches no known incident class; "
                           "no automated action is taken.")
        elif label not in self.intent.target_classes or label not in self.attacks:
            rules.append("outside_intent_to_human")
            reasons.append(f"'{label}' is not a target class of intent {self.intent.intent_id}.")
        elif prediction.confidence < self.intent.policy.min_confidence:
            rules.append("low_confidence_to_human")
            reasons.append(f"Confidence {prediction.confidence:.2f} is below the intent's minimum "
                           f"{self.intent.policy.min_confidence:.2f}; no automated action is taken.")
        if rules:
            return PolicyDecision(incident_id, label, mode, ESCALATE, reasons, rules_applied=rules,
                                  detected_at=when.isoformat()), None

        attack = self.attacks[label]
        obligations = verified_obligations(attack)
        record, adviser = None, None
        if self.intent.policy.legal_adviser:
            try:
                record = self._pipeline().run_chunk(
                    adviser_chunk(incident_id, prediction, attack, alerts, when, hospital_affected))
                adviser = summarise_record(record)
            except Exception as exc:                        # noqa: BLE001 — never block on the adviser
                adviser = {"error": f"specialist agents did not run: {type(exc).__name__}: {exc}"}
        if mode == "blocking":
            rules.append("blocking_mode_human_approval")
            reasons.append("Blocking mode: remediation is held until a human approves it, having seen "
                           "the obligations below.")
            decision = HOLD
        else:
            rules.append("advisory_mode_annotate")
            reasons.append("Advisory mode: remediation proceeds through the incident-response gates; "
                           "the obligations are attached for the operator.")
            decision = PROCEED
        if any(o["id"] == "certin_logs_180d" for o in obligations):
            rules.append("preserve_logs_before_changes")
            reasons.append("Logs are preserved before any state-changing step (CERT-In Directions: "
                           "180-day log retention).")
        unverified = [o["id"] for o in obligations if not o["verified"]]
        if unverified:
            reasons.append(f"Obligations not verified in their source: {', '.join(unverified)} — "
                           "shown as UNVERIFIED.")
        return PolicyDecision(incident_id, label, mode, decision, reasons, obligations, adviser, rules,
                              when.isoformat()), record
