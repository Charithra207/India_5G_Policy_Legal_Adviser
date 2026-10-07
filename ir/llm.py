"""
Agent providers for the tiered incident response.
=================================================
LLM_PROVIDER selects the provider:
  anthropic (default)  Claude via the Messages API with tool use; needs
                       ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN). Uses
                       claude-opus-5-5 with server-side refusal fallback.
  offline              Deterministic: follows the YAML playbook step by step.
                       No network, no key.
If "anthropic" is selected but no credential is configured or the SDK is
missing, the offline provider is used and a notice is printed.

Both providers act only through Incident.execute, so the same gating rules
(auto-safe in Basic, operator approval later) apply to both.
"""

from __future__ import annotations

import json
import os
import sys

from catalog.loader import resolve_args
from sim.engine import check

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
MAX_TURNS = 20


class OfflineProvider:
    name = "offline"

    def run_tier(self, incident, tier: str) -> dict:
        notes = []
        for step in incident.attack["playbook"][tier]:
            if incident.resolved():
                notes.append("resolved; remaining steps not needed")
                break
            if step["is_state_changing"] and tier == "basic" and not step.get("auto_safe"):
                incident.record(tier, "agent", step["action"]["fn"], state_changing=True, approved=False,
                                note=f"{step['id']}: skipped in Basic (needs operator approval)")
                continue
            args = resolve_args(incident.sim, step["action"].get("args"))
            result = incident.execute(tier, step["action"]["fn"], args, reason=f"{step['id']}: {step['description']}")
            if step.get("success_check") and result.get("ok", True) is not False:
                ok, actual = check(incident.sim, step["success_check"])
                sc = step["success_check"]
                incident.record(tier, "system", "success_check", result={"ok": ok, "actual": actual},
                                note=f"{step['id']}: {sc['fn']}.{sc.get('path', '')} {sc['op']} "
                                     f"{sc.get('value', '')} → {'passed' if ok else 'not met'}")
        return {"provider": self.name, "summary": "; ".join(notes) or f"ran the {tier} playbook steps in order"}

    def interpret(self, incident, tier: str, pasted: str) -> str:
        ok, details = incident.resolution()
        failing = [f"{d['fn']}.{d.get('path', '')} {d['op']} {d.get('value')} (actual {d['actual']})"
                   for d in details if not d["ok"]]
        return ("Operator results received; resolution checks now pass." if ok else
                "Operator results received; still failing: " + "; ".join(failing))


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic
        self.client = anthropic.Anthropic()

    def _system(self, incident, tier: str) -> str:
        a = incident.attack
        steps = "\n".join(f"- {s['id']}: {s['description']} -> {s['action']['fn']}"
                          f"{' [state-changing' + (', auto-safe' if s.get('auto_safe') else ', needs approval') + ']' if s['is_state_changing'] else ''}"
                          for s in a["playbook"][tier])
        return (
            "You are the incident-response agent in a contained 5G security training lab. The network is a "
            "local Python simulation; your tools are its diagnostic and remediation functions plus a "
            "knowledge-base search. Nothing you do reaches a real system.\n\n"
            f"Incident: {a['name']} — {a['description']}\nAffected NF(s): {', '.join(a['affected_nf'])}\n"
            f"Current tier: {tier.upper()}. Playbook steps for this tier (guidance, in order):\n{steps}\n\n"
            "Work through the tier: run diagnostics, read the results, decide, and apply fixes. "
            "State-changing calls are gated by the lab: in the Basic tier only auto-safe steps run; in later "
            "tiers the operator approves each one, so state exactly why you need it. Use the identifiers you "
            "observe in diagnostics (sources, neighbour ids, instance ids) as arguments. Cite the knowledge "
            "base (file and page) when a rule or standard informs a step. When done, call "
            "report_tier_outcome once with whether you think the incident is resolved and a short summary."
        )

    def _create(self, **kwargs):
        # Server-side refusal fallback: a declined turn is re-run on a fallback model
        return self.client.beta.messages.create(
            model=MODEL, max_tokens=16000, output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"}, **kwargs)

    def run_tier(self, incident, tier: str) -> dict:
        from ir.tools import tools_for_tier
        tools = tools_for_tier(incident.attack["playbook"][tier])
        messages = [{"role": "user", "content": f"The {tier} tier starts now. Current alerts: "
                                                 f"{json.dumps(incident.sim.get_alerts()['alerts'])}"}]
        summary = ""
        for _ in range(MAX_TURNS):
            response = self._create(system=self._system(incident, tier), tools=tools, messages=messages)
            if response.stop_reason == "refusal":
                incident.record(tier, "system", "model declined", note="falling back to the offline playbook")
                return {**OfflineProvider().run_tier(incident, tier), "provider": "anthropic→offline (refusal)"}
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "pause_turn":
                continue
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                summary = summary or next((b.text for b in response.content if b.type == "text"), "")
                break
            results, finished = [], False
            for block in tool_uses:
                inp = block.input if isinstance(block.input, dict) else json.loads(block.input)
                if block.name == "report_tier_outcome":
                    summary, finished = inp.get("summary", ""), True
                    content = json.dumps({"recorded": True})
                elif block.name == "search_kb":
                    content = json.dumps(_search(incident, inp.get("query", "")))
                else:
                    content = json.dumps(incident.execute(tier, block.name, inp, reason="agent decision"),
                                         default=str)
                    content += f"\n(lab resolution checks currently {'PASS' if incident.resolved() else 'FAIL'})"
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
            messages.append({"role": "user", "content": results})
            if finished:
                break
        return {"provider": self.name, "summary": summary}

    def interpret(self, incident, tier: str, pasted: str) -> str:
        ok, details = incident.resolution()
        response = self._create(messages=[{"role": "user", "content": (
            f"Lab incident '{incident.attack['name']}', {tier} tier, run by the operator. Their pasted "
            f"command output:\n\n{pasted[:12000]}\n\nLab resolution checks: {json.dumps(details, default=str)}\n"
            "In 3-5 sentences: what do the results show, is the incident resolved, and what next?")}])
        if response.stop_reason == "refusal":
            return OfflineProvider().interpret(incident, tier, pasted)
        return next((b.text for b in response.content if b.type == "text"), "")


def _search(incident, query: str) -> list[dict]:
    from kb.retriever import cite
    from kb.retriever import search as kb_search
    search = incident.search or kb_search
    try:
        hits = search(query, categories=incident.attack["retrieval_categories"], k=4)
    except FileNotFoundError as exc:
        return [{"error": str(exc)}]
    return [{"citation": cite(h), "category": h["category"], "text": h["text"][:900]} for h in hits]


def get_provider():
    choice = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if choice == "offline":
        return OfflineProvider()
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("[ir] no ANTHROPIC_API_KEY set — using the offline playbook provider", file=sys.stderr)
        return OfflineProvider()
    try:
        return AnthropicProvider()
    except ImportError:
        print("[ir] anthropic SDK not installed — using the offline playbook provider", file=sys.stderr)
        return OfflineProvider()
