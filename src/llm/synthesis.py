"""
LLM-assisted reasoning for a specialist agent: the model proposes, the text verifies
==================================================================================
After an agent has retrieved passages from its own KB and produced its
deterministic finding, an LLM (if one is configured) reads ONLY:

  - the agent's mandate,
  - the information released to THIS agent (the chunk plus its agent view),
  - the incident flags and the verified findings of earlier stages,
  - the passages the agent retrieved, each with its id,

and returns JSON: a short reasoning summary, up to four claims each citing
passage ids, uncertainties and missing information.

Guardrails (applied here, not left to the model):
  - a claim that cites no retrieved passage id is rejected and recorded as such;
  - accepted claims carry the label "[LLM-assisted — <provider:model>]" and
    the passages they cite, so the Verifier checks them against the
    Canonical KB exactly like any other claim — paraphrase that the
    authoritative text does not support becomes UNSUPPORTED;
  - a claim citing only international material is labelled
    "[REFERENCE ONLY — not Indian law]";
  - the full exchange (prompts, raw response, accepted and rejected claims,
    latency, tokens) is kept in finding.reasoning_trace for the audit trail.

The "reasoning summary" is the model's own stated rationale, recorded for
review; hidden chain-of-thought is neither requested nor stored.
"""

from __future__ import annotations

import hashlib
import json
import re

from src.llm import active
from src.llm.provider import LLMProvider

MAX_CLAIMS = 4
MAX_CLAIM_CHARS = 600
EXCERPT_CHARS = 900
MAX_PASSAGES = 8

SYSTEM = """You are the {agent} in a multi-agent policy and legal adviser for 5G network incidents in India.
Your mandate: {mandate}

Rules:
1. Use ONLY the passages provided below. Do not use outside knowledge of any law, rule, standard or institution.
2. Every claim must cite at least one passage id from the list, and should reuse the key words of the cited passage so a reviewer can check it against that text.
3. A passage marked [REFERENCE ONLY — not Indian law] is an international reference point: never present it as an obligation in India.
4. Stay within your mandate. Do not decide legal questions: say what the passages say and how they may bear on the incident, for qualified human review.
5. Say plainly what is uncertain and what information is missing.

Answer with one JSON object and nothing else:
{{"reasoning_summary": "<2-4 sentences: how the passages bear on the facts you were given>",
  "claims": [{{"text": "<one claim, under 60 words>", "cites": ["<passage id>"]}}],
  "uncertainties": ["<...>"],
  "missing_information": ["<...>"]}}
At most {max_claims} claims."""


def _label(item) -> str:
    return "" if item.jurisdiction.strip().lower() == "india" else " [REFERENCE ONLY — not Indian law]"


def build_prompt(agent, chunk, incident_state: dict, evidence: list) -> tuple[str, str, list]:
    """System prompt, user message and the passages offered (real ones only)."""
    passages = [e for e in evidence if agent._is_real(e) and e.chunk_id][:MAX_PASSAGES]
    agent_name = agent.agent_id.value.replace("_", " ").title() + " Agent"
    system = SYSTEM.format(agent=agent_name, mandate=getattr(agent, "MANDATE", ""), max_claims=MAX_CLAIMS)
    view = list(getattr(chunk, "agent_views", {}).get(agent.agent_id.value, []))
    flags = {k: incident_state.get(k) for k in ("cyber_event_suspected", "cii_flagged", "data_exposure_suspected")}
    verified = [f"- ({v['agent_id']}, {v['outcome']}) {v['claim'][:300]}"
                for v in incident_state.get("verified_findings", [])[-5:]]
    lines = ["Information released to you at this stage:", f"- {chunk.description}"]
    lines += [f"- {f}" for f in chunk.new_facts if f not in view]     # the orchestrator appends the view
    if view:
        lines += ["Information only you received:"] + [f"- {f}" for f in view]
    lines += ["", f"Incident flags: {json.dumps(flags)}"]
    if verified:
        lines += ["Findings of other agents from earlier stages (with verifier outcome):"] + verified
    lines += ["", "Retrieved passages:"]
    for e in passages:
        excerpt = " ".join(e.excerpt.split())[:EXCERPT_CHARS]
        page = f", p. {e.page}" if e.page else ""
        lines.append(f"[{e.chunk_id}] {e.source_title}, {e.section}{page}{_label(e)}: {excerpt}")
    if not passages:
        lines.append("(none — say that nothing can be claimed from the knowledge base)")
    return system, "\n".join(lines), passages


def parse_json(text: str) -> dict | None:
    """The first JSON object in the model's text (models sometimes wrap it in prose or fences)."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def enrich(agent, chunk, incident_state: dict, evidence: list, finding,
           llm: LLMProvider | None = None) -> None:
    """Add verified-citation LLM claims and a reasoning trace to `finding` (in place)."""
    llm = llm or active()
    if llm is None or llm.name == "offline":
        return
    system, user, passages = build_prompt(agent, chunk, incident_state, evidence)
    trace = {"provider": llm.name, "model": llm.model, "system_prompt": system, "user_prompt": user,
             "prompt_sha256": hashlib.sha256((system + "\n" + user).encode("utf-8")).hexdigest(),
             "passages_offered": [p.chunk_id for p in passages], "accepted_claims": [],
             "rejected_claims": [], "reasoning_summary": "", "status": ""}
    finding.reasoning_trace = trace
    if not passages:
        trace["status"] = "skipped: no retrieved passages to reason over"
        return
    response = llm.complete(system, user)
    if response is None:
        trace["status"] = f"model unavailable: {getattr(llm, 'last_error', '') or 'no response'}"
        finding.uncertainty_notes.append(f"LLM reasoning not available ({llm.describe()}): "
                                         f"{trace['status']}; deterministic finding only.")
        return
    trace.update(raw_response=response.text, latency_ms=response.latency_ms, usage=response.usage,
                 model=response.model)
    data = parse_json(response.text)
    if data is None:
        trace["status"] = "rejected: response was not a JSON object"
        return
    trace["reasoning_summary"] = str(data.get("reasoning_summary", ""))[:1500]
    by_id = {p.chunk_id: p for p in passages}
    label = f"[LLM-assisted — {llm.name}:{response.model}]"
    for raw in (data.get("claims") or [])[:MAX_CLAIMS * 2]:
        text = str(raw.get("text", "")).strip() if isinstance(raw, dict) else ""
        cites = [c for c in (raw.get("cites") or []) if isinstance(c, str)] if isinstance(raw, dict) else []
        valid = [by_id[c] for c in dict.fromkeys(cites) if c in by_id]
        if not text:
            trace["rejected_claims"].append({"claim": raw, "reason": "empty claim"})
            continue
        if not valid:
            trace["rejected_claims"].append({"claim": text, "cites": cites,
                                             "reason": "cites no retrieved passage id"})
            continue
        if len(trace["accepted_claims"]) >= MAX_CLAIMS:
            trace["rejected_claims"].append({"claim": text, "reason": f"more than {MAX_CLAIMS} claims"})
            continue
        reference = all(p.jurisdiction.strip().lower() != "india" for p in valid)
        claim = f"{label} {'[REFERENCE ONLY — not Indian law] ' if reference else ''}{text[:MAX_CLAIM_CHARS]}"
        if claim in finding.claims:
            continue
        finding.claims.append(claim)
        finding.claim_citations[claim] = valid
        trace["accepted_claims"].append({"claim": claim, "cites": [p.chunk_id for p in valid]})
    for key, target in (("uncertainties", finding.uncertainty_notes), ("missing_information", finding.missing_facts)):
        for item in (data.get(key) or [])[:5]:
            if isinstance(item, str) and item.strip():
                target.append(f"{label} {item.strip()[:300]}")
    trace["status"] = (f"{len(trace['accepted_claims'])} claim(s) accepted, "
                       f"{len(trace['rejected_claims'])} rejected; accepted claims go to the Verifier")
