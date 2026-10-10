"""
Judge report — Markdown, complete
=================================
Renders one audit-trail JSON Lines file (see trail.py) as a Markdown document
that keeps EVERY recorded field: the readable summary and timeline come
first, then every entry in full — stage inputs, orchestrator choice, each
agent's visible input, queries, retrieved passages with all metadata, claims
with every citation and verifier outcome, the LLM prompts and raw response,
the Verifier and Coordinator output, and the hash chain.

Known fields get a readable layout; any field this module does not know is
still printed under "Other fields", so nothing in the trail is dropped.
`check_complete` confirms that every recorded value appears in the output.

    python -m src.audit.judge_report_md outputs/audit/<run>.jsonl [-o report.md]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from src.audit.narrative import adviser_narrative
from src.audit.trail import read_entries, verify_chain

AGENT_NAMES = {
    "technical": "Technical", "cybersecurity": "Cybersecurity", "standards": "Standards",
    "policy_legal": "Policy & Legal", "privacy": "Privacy",
    "critical_infrastructure": "Critical Infrastructure", "policy_gap": "Policy Gap",
}
OUTCOMES = ("VERIFIED", "INCOMPLETE", "UNSUPPORTED", "CONFLICT")
OUTCOME_ICON = {"VERIFIED": "🟢", "INCOMPLETE": "🟡", "UNSUPPORTED": "🔴", "CONFLICT": "⚠️"}
OUTCOME_HELP = {
    "VERIFIED": "Supported by the authoritative text, with in-force status and amendments checked.",
    "INCOMPLETE": "Supported by the authoritative text, but in-force status, amendments or a related "
                  "provision were not confirmed.",
    "UNSUPPORTED": "The Canonical KB passages checked do not support the claim; preliminary only.",
    "CONFLICT": "Authoritative sources disagree; the Coordinator records both sides.",
}


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def label(key: str) -> str:
    return key.replace("_", " ").capitalize()


def scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def cell(v) -> str:
    return scalar(v).replace("|", "\\|").replace("\n", "<br>")


def outcome(o: str) -> str:
    return f"{OUTCOME_ICON.get(o, '')} **{o}**"


def agent(a: str) -> str:
    return f"**{AGENT_NAMES.get(a, a)}** (`{a}`)"


def counts(c: dict) -> str:
    return ", ".join(f"{outcome(o)} {c[o]}" for o in OUTCOMES if o in c) + \
        "".join(f", {k} {v}" for k, v in c.items() if k not in OUTCOMES) or "none"


def bullets(items, empty: str = "_None recorded._") -> str:
    if not items:
        return empty + "\n"
    return "".join(f"- {generic_inline(i)}\n" for i in items)


def generic_inline(v) -> str:
    if isinstance(v, (dict, list)):
        return "`" + json.dumps(v, ensure_ascii=False) + "`"
    return scalar(v)


def fence(text: str, lang: str = "") -> str:
    return f"~~~~{lang}\n{text}\n~~~~\n"


def details(summary: str, body: str) -> str:
    return f"<details>\n<summary>{summary}</summary>\n\n{body}\n</details>\n\n"


def kv_table(d: dict, keys=None) -> str:
    keys = keys if keys is not None else list(d)
    rows = [f"| {label(k)} | {cell(d[k]) if not isinstance(d[k], (dict, list)) else cell(json.dumps(d[k], ensure_ascii=False))} |"
            for k in keys if k in d]
    return "| Field | Value |\n|---|---|\n" + "\n".join(rows) + "\n" if rows else ""


def generic(v, depth: int = 0) -> str:
    """Any value, fully, as nested bullets."""
    pad = "  " * depth
    if isinstance(v, dict):
        if not v:
            return f"{pad}- _(empty)_\n"
        out = ""
        for k, x in v.items():
            if isinstance(x, (dict, list)) and x:
                out += f"{pad}- **{label(k)}**:\n" + generic(x, depth + 1)
            else:
                out += f"{pad}- **{label(k)}**: {generic_inline(x) if x not in ([], {}) else '_(empty)_'}\n"
        return out
    if isinstance(v, list):
        if not v:
            return f"{pad}- _(empty)_\n"
        out = ""
        for i, x in enumerate(v, 1):
            if isinstance(x, (dict, list)):
                out += f"{pad}- #{i}\n" + generic(x, depth + 1)
            else:
                out += f"{pad}- {scalar(x)}\n"
        return out
    return f"{pad}- {scalar(v)}\n"


def rest(d: dict, known: set, title: str = "Other fields") -> str:
    left = {k: v for k, v in d.items() if k not in known}
    return f"**{title}:**\n\n" + generic(left) + "\n" if left else ""


def ref(c: dict) -> str:
    return f"{c.get('source_title', '')}, {c.get('section', '')}" + (f" (p. {c['page']})" if c.get("page") else "")


def citation_lines(cits: list[dict]) -> str:
    if not cits:
        return "_none_\n"
    out = ""
    for c in cits:
        if isinstance(c, dict):
            extra = {k: v for k, v in c.items() if k not in ("source_title", "section", "page", "chunk_id")}
            out += (f"- {ref(c)} — page `{scalar(c.get('page', ''))}` — chunk `{scalar(c.get('chunk_id', ''))}`"
                    + (f" — {generic_inline(extra)}" if extra else "") + "\n")
        else:
            out += f"- {scalar(c)}\n"
    return out


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def run_header(start: dict, stages: list, end: dict | None, problems: list) -> str:
    totals: Counter = Counter()
    for s in stages:
        totals.update(s.get("verifier", {}).get("outcome_counts", {}))
    passages = sum(len(a.get("retrieved_passages", [])) for s in stages for a in s.get("agents", []))
    used = sorted({a for s in stages for a in s.get("orchestrator", {}).get("active_agents", [])})
    stage_count = start.get("stage_count")
    status = (f"✅ Completed — {end['stages_recorded']} of {stage_count} stage(s) recorded"
              if end else f"⚠️ **Incomplete run** — {len(stages)} of {stage_count} stage(s) recorded; "
                          "no `run_completed` entry (the run stopped before finishing)")
    integrity = ("✅ **Intact** — every entry's SHA-256 hash and its link to the previous entry check out, "
                 "so no entry was edited, removed or reordered." if not problems
                 else "❌ **Broken** — " + "; ".join(problems))
    md = f"""# {start.get('scenario_title', start.get('scenario_id', 'Run'))}

**Audit-trail report** — run `{start.get('run_id')}` · scenario `{start.get('scenario_id')}` (DOCX {start.get('docx_section', '')})

> **Run status:** {status}
>
> **Hash-chain integrity:** {integrity}

| Stages recorded | Specialist agents used | Passages retrieved | Claims verified | Selections matching DOCX table |
|---|---|---|---|---|
| {len(stages)} / {stage_count} | {len(used)} | {passages} | {sum(totals.values())} | {sum(1 for s in stages if s.get('orchestrator', {}).get('matches_docx_table'))} / {len(stages)} |

**Verifier outcomes (all stages):** {counts(dict(totals))}

**Contents:** [1. Summary](#1-summary-and-conclusion) · [2. Timeline](#2-timeline) · [3. Run header](#3-run-header-entry-1) · """
    md += " · ".join(f"[Stage {s['stage']['label']}](#stage-{s['stage']['label'].lower()})" for s in stages)
    md += " · [Run completion](#run-completion) · [Hash chain](#hash-chain)\n\n"
    md += "**Verifier outcome key:**\n\n| Outcome | Meaning |\n|---|---|\n" + "".join(
        f"| {outcome(o)} | {OUTCOME_HELP[o]} |\n" for o in OUTCOMES) + "\n"
    return md


def summary(stages: list) -> str:
    n = adviser_narrative(stages)
    md = "## 1. Summary and conclusion\n\n" \
         "_Condensed by the project's `src/audit/narrative.py` from the recorded entries; every sentence " \
         "restates a recorded fact, quoted provision or Verifier outcome._\n\n"
    md += f"### What happened\n\n{n['summary']}\n\n### What follows\n\n{n['conclusion']}\n\n"
    md += "### Notifications that may be due\n\n_Read from the quoted Indian provisions; each must be confirmed by a qualified person._\n\n"
    if n["notifications"]:
        md += "| To | Time limit | Provision | Page | Applies if | Raised by | First raised |\n|---|---|---|---|---|---|---|\n"
        for r in n["notifications"]:
            md += (f"| {cell(r['recipient'])} | {cell(', then '.join(r['limits']))} | {cell(r['source'])}, "
                   f"{cell(r['section'])} | {cell(r.get('page', ''))} | {cell(r['condition'])} | "
                   f"{cell(', '.join(r.get('agents', [])))} | {cell(r['stage'])} |\n")
    else:
        md += "_No reporting duty was found in the provisions quoted so far._\n"
    return md + "\n"


def timeline(stages: list) -> str:
    md = "## 2. Timeline\n\n| Stage | Scenario time | Information released | Agents active | Newly activated | Verifier outcomes | Flags raised |\n|---|---|---|---|---|---|---|\n"
    for s in stages:
        st, o = s["stage"], s["orchestrator"]
        flags = s.get("coordinator", {}).get("incident_flags", {})
        raised = [k.replace("_", " ") for k, v in flags.items() if v] or ["—"]
        md += (f"| [{st['label']}](#stage-{st['label'].lower()}) | {cell(st['scenario_time'])} | "
               f"{cell(st['information_released'])} | {cell(', '.join(AGENT_NAMES.get(a, a) for a in o['active_agents']))} | "
               f"{cell(', '.join(AGENT_NAMES.get(a, a) for a in o['newly_activated']) or '—')} | "
               f"{cell(counts(s['verifier']['outcome_counts']))} | {cell(', '.join(raised))} |\n")
    return md + "\n"


def start_entry(start: dict) -> str:
    md = "## 3. Run header (entry 1)\n\n"
    top = ["seq", "run_id", "type", "schema_version", "recorded_at", "scenario_id", "scenario_title",
           "docx_section", "stage_count", "knowledge_base_note", "prev_hash", "hash"]
    md += kv_table(start, top) + "\n"
    if "knowledge_bases_live" in start:
        md += "### Knowledge bases live\n\n| Knowledge base | Live |\n|---|---|\n" + "".join(
            f"| {k} | {'✅ true' if v else '❌ false'} |\n" for k, v in start["knowledge_bases_live"].items()) + "\n"
    kb = start.get("knowledge_base_build")
    if kb is not None:
        md += "### Knowledge-base build\n\n" + kv_table({k: v for k, v in kb.items() if k != "not_ingested"})
        md += f"\n**Not ingested:**\n\n{bullets(kb.get('not_ingested', []))}\n"
    if "llm" in start:
        md += "### Language model\n\n" + kv_table(start["llm"]) + "\n"
    if "code" in start:
        md += "### Code\n\n" + kv_table(start["code"]) + "\n"
    if kb and "none" in str(kb.get("generator_model", "")).lower() and start.get("llm", {}).get("model"):
        md += ("> ℹ️ **Note for readers:** the header records both `generator_model: "
               f"\"{kb['generator_model']}\"` and an LLM (`{start['llm'].get('provider')}` · "
               f"`{start['llm'].get('model')}`). Both values are reproduced exactly as recorded.\n\n")
    return md + rest(start, set(top) | {"knowledge_bases_live", "knowledge_base_build", "llm", "code"})


def passage_md(i: int, p: dict) -> str:
    known = ["source_title", "authority", "jurisdiction", "document_type", "section", "section_title", "page",
             "date_issued", "effective", "effective_status", "amendment_checked", "amendment_note", "url",
             "provenance_note", "chunk_id", "relevance_score", "is_stub"]
    md = f"**{i}. {ref(p)}** — relevance {scalar(p.get('relevance_score'))}\n\n" + kv_table(p, known)
    md += "\n**Excerpt:**\n\n" + "".join(f"> {line}\n" for line in scalar(p.get("excerpt", "")).split("\n")) + "\n"
    return md + rest(p, set(known) | {"excerpt"})


def claim_md(i: int, c: dict) -> str:
    md = f"**Claim {i}** — {outcome(c.get('verifier_outcome', ''))}\n\n"
    md += "".join(f"> {line}\n" for line in scalar(c.get("claim", "")).split("\n")) + "\n"
    md += f"- **Verifier rationale:** {scalar(c.get('verifier_rationale', ''))}\n"
    md += f"- **Cross-domain flag:** {scalar(c.get('cross_domain_flag'))}"
    md += f" — note: {scalar(c.get('cross_domain_note'))}\n" if c.get("cross_domain_note") else " — note: _(none)_\n"
    md += "\n**Citations (cited by the agent):**\n\n" + citation_lines(c.get("citations", []))
    md += "\n**Verifier — supporting passages:**\n\n" + citation_lines(c.get("verifier_supporting", []))
    md += "\n**Verifier — conflicting / non-supporting passages checked:**\n\n" + citation_lines(c.get("verifier_conflicting", []))
    return md + "\n" + rest(c, {"claim", "citations", "verifier_outcome", "verifier_rationale", "verifier_supporting",
                                "verifier_conflicting", "cross_domain_flag", "cross_domain_note"})


def llm_md(llm: dict) -> str:
    md = kv_table(llm, ["provider", "model", "status", "latency_ms", "prompt_sha256"])
    if "usage" in llm:
        md += "\n**Token usage:** " + ", ".join(f"{k} {v}" for k, v in (llm["usage"] or {}).items()) + "\n"
    md += f"\n**Reasoning summary:** {scalar(llm.get('reasoning_summary', ''))}\n\n"
    md += "**Passages offered to the LLM:**\n\n" + "".join(f"- `{p}`\n" for p in llm.get("passages_offered", [])) + "\n"
    md += "**Accepted claims (passed to the Verifier):**\n\n"
    acc = llm.get("accepted_claims", [])
    md += generic(acc) if acc else "_None._\n"
    md += "\n**Rejected claims (not passed on):**\n\n"
    rej = llm.get("rejected_claims", [])
    if rej:
        for j, r in enumerate(rej, 1):
            if isinstance(r, dict):
                md += (f"{j}. {scalar(r.get('claim', ''))}\n   - cites: "
                       f"{', '.join('`' + str(x) + '`' for x in r.get('cites', [])) or '_none_'}\n"
                       f"   - reason rejected: {scalar(r.get('reason', ''))}\n")
                extra = {k: v for k, v in r.items() if k not in ("claim", "cites", "reason")}
                if extra:
                    md += generic(extra, 1)
            else:
                md += f"{j}. {scalar(r)}\n"
    else:
        md += "_None._\n"
    md += "\n"
    for key, title in (("system_prompt", "System prompt"), ("user_prompt", "User prompt"),
                       ("raw_response", "Raw LLM response")):
        if key in llm:
            md += details(title, fence(scalar(llm[key]), "json" if key == "raw_response" else "text"))
    return md + rest(llm, {"provider", "model", "status", "latency_ms", "prompt_sha256", "usage", "reasoning_summary",
                           "passages_offered", "accepted_claims", "rejected_claims", "system_prompt", "user_prompt",
                           "raw_response"})


def agent_md(label_: str, a: dict) -> str:
    aid = a.get("agent_id", "")
    md = f"#### {label_} · Agent: {AGENT_NAMES.get(aid, aid)} (`{aid}`)\n\n"
    md += f"**Decision summary:** {scalar(a.get('decision_summary', ''))}\n\n"
    m = a.get("mandate_output", {})
    md += "**Mandate output:**\n\n" + (generic(m) if m else "_(empty)_\n") + "\n"
    claims = a.get("claims", [])
    c_counts = Counter(c.get("verifier_outcome") for c in claims)
    md += f"**Claims and verification** ({len(claims)}: {counts(dict(c_counts))}):\n\n"
    md += "".join(claim_md(i, c) for i, c in enumerate(claims, 1)) or "_No claims._\n\n"
    md += "**Uncertainty notes:**\n\n" + bullets(a.get("uncertainty_notes", [])) + "\n"
    md += "**Missing facts:**\n\n" + bullets(a.get("missing_facts", [])) + "\n"
    vi = a.get("visible_input", {})
    vi_md = kv_table(vi, ["chunk_id", "information_released"])
    vi_md += "\n**New facts:**\n\n" + bullets(vi.get("new_facts", []))
    vi_md += "\n**Agent-only view:**\n\n" + bullets(vi.get("agent_view", []))
    vi_md += "\n**Prior chunk IDs:**\n\n" + bullets(vi.get("prior_chunk_ids", []))
    vi_md += "\n**Incident state given to the agent:**\n\n" + generic(vi.get("incident_state", {}))
    vi_md += "\n" + rest(vi, {"chunk_id", "information_released", "new_facts", "agent_view", "prior_chunk_ids", "incident_state"})
    md += details(f"Input visible to {AGENT_NAMES.get(aid, aid)}", vi_md)
    md += "**Retrieval queries:**\n\n" + bullets(a.get("queries", [])) + "\n"
    ps = a.get("retrieved_passages", [])
    md += details(f"Retrieved passages ({len(ps)}) — full metadata and excerpts",
                  "".join(passage_md(i, p) for i, p in enumerate(ps, 1)) or "_None._")
    if "llm_reasoning" in a:
        llm = a["llm_reasoning"] or {}
        md += f"**LLM reasoning** — {scalar(llm.get('status', ''))}\n\n" + (llm_md(llm) if llm else "_(none recorded)_\n\n")
    return md + rest(a, {"agent_id", "decision_summary", "mandate_output", "claims", "uncertainty_notes", "missing_facts",
                         "visible_input", "queries", "retrieved_passages", "llm_reasoning"})


def link_md(links: list) -> str:
    if not links:
        return "_None._\n"
    md = ""
    for i, l in enumerate(links, 1):
        if not isinstance(l, dict):
            md += f"{i}. {scalar(l)}\n"
            continue
        md += f"{i}. **{' ↔ '.join(l.get('agents', []))}**" + (f" — kind: `{l['kind']}`" if "kind" in l else "") + \
              (f" — chunk `{l['chunk_id']}`" if "chunk_id" in l else "") + f"\n   - {scalar(l.get('note', ''))}\n"
        for mbr in l.get("members", []):
            md += (f"   - member: {agent(mbr.get('agent_id', ''))} at `{mbr.get('chunk_id', '')}` — "
                   f"{scalar(mbr.get('claim', ''))}\n")
            extra = {k: v for k, v in mbr.items() if k not in ("agent_id", "chunk_id", "claim")}
            if extra:
                md += generic(extra, 2)
        extra = {k: v for k, v in l.items() if k not in ("agents", "kind", "chunk_id", "note", "members")}
        if extra:
            md += generic(extra, 1)
    return md


def stage_md(s: dict) -> str:
    st, o = s["stage"], s["orchestrator"]
    lab = st["label"]
    md = f"## Stage {lab}\n\n**{scalar(st.get('information_released'))}**\n\n"
    md += "### Entry record\n\n" + kv_table(s, ["seq", "run_id", "type", "scenario_id", "recorded_at",
                                               "pipeline_timestamp", "prev_hash", "hash"]) + "\n"
    md += "### What was released\n\n" + kv_table(st, ["index", "label", "chunk_id", "scenario_time",
                                                      "information_released", "docx_information_released",
                                                      "docx_expected_change"])
    md += "\n**New facts:**\n\n" + bullets(st.get("new_facts", []))
    md += "\n**Information released only to specific agents:**\n\n"
    av = st.get("agent_views", {})
    md += "".join(f"- {agent(k)}:\n" + "".join(f"  - {scalar(x)}\n" for x in v) for k, v in av.items()) or "_None._\n"
    md += "\n**Prior chunks:**\n\n" + bullets(st.get("prior_chunks", []))
    md += "\n" + rest(st, {"index", "label", "chunk_id", "scenario_time", "information_released", "new_facts",
                           "agent_views", "prior_chunks", "docx_information_released", "docx_expected_change"})
    md += "### Orchestrator — which agents acted\n\n"
    md += f"- **Active:** {', '.join(agent(a) for a in o.get('active_agents', [])) or '_none_'}\n"
    md += f"- **Newly activated:** {', '.join(agent(a) for a in o.get('newly_activated', [])) or '_none_'}\n"
    md += f"- **No longer active (carried forward, not re-examined):** {', '.join(agent(a) for a in o.get('no_longer_active', [])) or '_none_'}\n"
    md += f"- **DOCX primary agents:** {', '.join(agent(a) for a in o.get('docx_primary_agents', [])) or '_none_'}\n"
    md += f"- **Matches DOCX table:** {'✅ true' if o.get('matches_docx_table') else '❌ ' + scalar(o.get('matches_docx_table'))}\n\n"
    md += rest(o, {"active_agents", "newly_activated", "no_longer_active", "docx_primary_agents", "matches_docx_table"})
    md += "### Specialist agents\n\n" + "".join(agent_md(lab, a) for a in s.get("agents", []))
    v = s.get("verifier", {})
    md += f"### Verifier\n\n**Outcome counts:** {counts(v.get('outcome_counts', {}))}\n\n"
    md += "**Cross-domain links:**\n\n" + bullets(v.get("cross_domain_links", []))
    md += "\n**Cross-domain link details:**\n\n" + link_md(v.get("cross_domain_details", []))
    md += "\n**Conflicts:**\n\n" + bullets(v.get("conflicts", []))
    md += "\n**Conflict details:**\n\n" + (generic(v["conflict_details"]) if v.get("conflict_details") else "_None._\n")
    md += "\n**Missing evidence:**\n\n" + bullets(v.get("missing_evidence", [])) + "\n"
    md += rest(v, {"outcome_counts", "cross_domain_links", "conflicts", "missing_evidence", "cross_domain_details",
                   "conflict_details"})
    c = s.get("coordinator", {})
    md += f"### Coordinator assessment\n\n- **Chunk:** `{scalar(c.get('chunk_id'))}`\n"
    md += f"- **Active agents:** {', '.join(agent(a) for a in c.get('active_agents', []))}\n"
    md += "- **Incident flags:** " + ", ".join(f"{k} = {'✅ true' if x else 'false'}"
                                               for k, x in c.get("incident_flags", {}).items()) + "\n\n"
    for key, title in (("changes_from_prior", "What changed from the previous stage"),
                       ("confirmed_facts", "Confirmed facts"),
                       ("evidence_backed_conclusions", "Evidence-backed conclusions"),
                       ("uncertain_conclusions", "Uncertain / preliminary conclusions"),
                       ("conflicting_findings", "Conflicting findings"),
                       ("potential_policy_gaps", "Potential policy gaps (for expert review)"),
                       ("cross_domain_relationships", "Cross-domain relationships"),
                       ("relevant_institutions", "Relevant institutions"),
                       ("open_questions", "Open questions")):
        md += f"**{title}** ({len(c.get(key, []))}):\n\n" + bullets(c.get(key, [])) + "\n"
    reg = c.get("claim_register", [])
    md += f"**Claim register** ({len(reg)}):\n\n"
    if reg:
        md += "| # | Agent | Outcome | Claim | Rationale | Citations | Chunk | Carried forward | In conflict |\n|---|---|---|---|---|---|---|---|---|\n"
        for i, r in enumerate(reg, 1):
            md += (f"| {i} | {cell(r.get('agent_id'))} | {cell(r.get('outcome'))} | {cell(r.get('claim'))} | "
                   f"{cell(r.get('rationale'))} | {cell('; '.join(map(str, r.get('citations', []))) or '—')} | "
                   f"{cell(r.get('chunk_id'))} | {cell(r.get('carried_forward'))} | {cell(r.get('in_conflict'))} |\n")
        extras = [{k: x for k, x in r.items() if k not in ("agent_id", "outcome", "claim", "rationale", "citations",
                                                           "chunk_id", "carried_forward", "in_conflict")} for r in reg]
        if any(extras):
            md += "\n**Claim register — other fields:**\n\n" + generic(extras)
    else:
        md += "_Empty._\n"
    md += "\n**Link register:**\n\n" + link_md(c.get("link_register", []))
    md += f"\n> ⚖️ **Human review required:** {scalar(c.get('human_review_required', ''))}\n\n"
    md += rest(c, {"chunk_id", "active_agents", "confirmed_facts", "evidence_backed_conclusions", "uncertain_conclusions",
                   "conflicting_findings", "potential_policy_gaps", "cross_domain_relationships", "relevant_institutions",
                   "changes_from_prior", "open_questions", "claim_register", "incident_flags", "link_register",
                   "human_review_required"})
    return md + rest(s, {"seq", "run_id", "type", "scenario_id", "recorded_at", "pipeline_timestamp", "prev_hash", "hash",
                         "stage", "orchestrator", "agents", "verifier", "coordinator"}) + "\n---\n\n"


def build(path: Path) -> str:
    entries = read_entries(path)
    problems = verify_chain(entries)
    start = next((x for x in entries if x.get("type") == "run_started"), {})
    stages = [x for x in entries if x.get("type") == "stage"]
    end = next((x for x in entries if x.get("type") == "run_completed"), None)
    md = run_header(start, stages, end, problems) + summary(stages) + timeline(stages) + start_entry(start)
    md += "\n---\n\n" + "".join(stage_md(s) for s in stages)
    md += "## Run completion\n\n" + (kv_table(end) if end else
                                     "⚠️ _No `run_completed` entry: the run stopped before all stages were recorded._\n")
    others = [x for x in entries if x.get("type") not in ("run_started", "stage", "run_completed")]
    if others:
        md += "\n### Other entries\n\n" + generic(others)
    md += ("\n## Hash chain\n\nEach entry stores the SHA-256 of its own content (`hash`) and the hash of the entry "
           f"before it (`prev_hash`). Source file: `{path.name}`. Re-check with `src.audit.trail.verify_chain`.\n\n"
           "| Seq | Entry | Recorded at | prev_hash | hash |\n|---|---|---|---|---|\n")
    for x in entries:
        name = x.get("type", "") + (f" {x['stage']['label']}" if x.get("type") == "stage" else "")
        md += f"| {x.get('seq')} | {name} | {x.get('recorded_at')} | `{x.get('prev_hash')}` | `{x.get('hash')}` |\n"
    md += ("\n> **Decision support only:** legal interpretation, regulatory decisions and institutional action "
           "remain with qualified people.\n")
    return md


def check_complete(path: Path, md: str) -> list[str]:
    """Every recorded scalar value must appear in the Markdown; returns the ones that do not."""
    missing = []

    def walk(v, where):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{where}.{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{where}[{i}]")
        else:
            s = scalar(v)
            lines = [line for line in s.split("\n") if line.strip()] or [s]
            if s and cell(s) not in md and any(line not in md and cell(line) not in md for line in lines):
                missing.append(f"{where} = {s[:80]}")

    for i, entry in enumerate(read_entries(path)):
        walk(entry, f"entry{i + 1}")
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description="Render an audit-trail JSONL as a complete Markdown report.")
    ap.add_argument("trail", type=Path)
    ap.add_argument("-o", "--output", type=Path, help="default: <trail>.md next to the trail")
    args = ap.parse_args()
    out = args.output or args.trail.with_suffix(".md")
    md = build(args.trail)
    out.write_text(md, encoding="utf-8")
    missing = check_complete(args.trail, md)
    print(out, "— complete: every recorded value is in the report" if not missing
          else f"— {len(missing)} value(s) missing:\n" + "\n".join(missing[:20]))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
