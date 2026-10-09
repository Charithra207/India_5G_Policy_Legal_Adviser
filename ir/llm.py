"""
Agent providers for the tiered incident response.
=================================================
LLM_PROVIDER selects the provider:
  anthropic (default)  Claude via the Messages API with tool use; needs
                       ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN). Uses
                       claude-opus-5-5 with server-side refusal fallback.
  ollama               A local open-weight model through Ollama with tool
                       calling (OLLAMA_MODEL, default qwen2.5:7b-instruct;
                       OLLAMA_HOST, default http://localhost:11434). Free;
                       falls back to the offline playbook if Ollama is not
                       reachable.
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


def system_prompt(incident, tier: str) -> str:
    """The tier instructions shared by the Claude and Ollama agents."""
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


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic
        self.client = anthropic.Anthropic()

    def _system(self, incident, tier: str) -> str:
        return system_prompt(incident, tier)

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


class OllamaProvider:
    """
    The tier agent on a local open-weight model (Ollama /api/chat with tools).
    Acts only through Incident.execute, like every provider; if Ollama cannot
    be reached the tier falls back to the offline playbook.
    """
    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None, timeout: float = 180.0) -> None:
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout

    def _chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        import urllib.request
        body = {"model": self.model, "messages": messages, "stream": False, "options": {"temperature": 0}}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                              "parameters": t["input_schema"]}} for t in tools]
        request = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def run_tier(self, incident, tier: str) -> dict:
        from ir.tools import tools_for_tier
        tools = tools_for_tier(incident.attack["playbook"][tier])
        messages = [{"role": "system", "content": system_prompt(incident, tier)},
                    {"role": "user", "content": f"The {tier} tier starts now. Current alerts: "
                                                f"{json.dumps(incident.sim.get_alerts()['alerts'])}"}]
        summary = ""
        for _ in range(MAX_TURNS):
            try:
                message = self._chat(messages, tools).get("message") or {}
            except (OSError, ValueError) as exc:
                incident.record(tier, "system", "model unavailable", note=f"Ollama: {exc}; offline playbook")
                return {**OfflineProvider().run_tier(incident, tier), "provider": "ollama→offline (unavailable)"}
            messages.append({"role": "assistant", "content": message.get("content", ""),
                             "tool_calls": message.get("tool_calls", [])})
            calls = message.get("tool_calls") or []
            if not calls:
                summary = summary or message.get("content", "")
                break
            finished = False
            for call in calls:
                fn = (call.get("function") or {})
                name, args = fn.get("name", ""), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                if name == "report_tier_outcome":
                    summary, finished = str(args.get("summary", "")), True
                    content = json.dumps({"recorded": True})
                elif name == "search_kb":
                    content = json.dumps(_search(incident, str(args.get("query", ""))))
                else:
                    content = json.dumps(incident.execute(tier, name, args, reason="agent decision"), default=str)
                    content += f"\n(lab resolution checks currently {'PASS' if incident.resolved() else 'FAIL'})"
                messages.append({"role": "tool", "tool_name": name, "content": content})
            if finished:
                break
        return {"provider": self.name, "summary": summary}

    def interpret(self, incident, tier: str, pasted: str) -> str:
        ok, details = incident.resolution()
        try:
            message = self._chat([{"role": "user", "content": (
                f"Lab incident '{incident.attack['name']}', {tier} tier, run by the operator. Their pasted "
                f"command output:\n\n{pasted[:12000]}\n\nLab resolution checks: {json.dumps(details, default=str)}\n"
                "In 3-5 sentences: what do the results show, is the incident resolved, and what next?")}]).get("message")
        except (OSError, ValueError):
            return OfflineProvider().interpret(incident, tier, pasted)
        return (message or {}).get("content", "") or OfflineProvider().interpret(incident, tier, pasted)


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
    if choice == "ollama":
        return OllamaProvider()
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("[ir] no ANTHROPIC_API_KEY set — using the offline playbook provider", file=sys.stderr)
        return OfflineProvider()
    try:
        return AnthropicProvider()
    except ImportError:
        print("[ir] anthropic SDK not installed — using the offline playbook provider", file=sys.stderr)
        return OfflineProvider()
