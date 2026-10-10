"""
Judge report — Markdown, complete
=================================
Renders one audit-trail JSON Lines file (see trail.py) as a report in plain
Markdown (no HTML), laid out for judges:

    Executive summary and observations  →  run status and configuration
    →  timeline  →  stage-by-stage analysis  →  notifications
    →  appendices holding every recorded value verbatim
       (passages, claims and citations, LLM prompts and responses,
        agent inputs, entry records and the hash chain)

Known fields get a readable layout; a field this module does not know is
still printed under "Other recorded fields", so nothing in the trail is
dropped.  `check_complete` confirms that every recorded value appears in the
report.

    python -m src.audit.judge_report_md outputs/audit/<run>.jsonl [-o report.md]
"""

from __future__ import annotations

import argparse
import json
import re
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
FLAG_NAMES = {"cyber_event_suspected": "Cyber event suspected", "cii_flagged": "Critical infrastructure flagged",
              "data_exposure_suspected": "Personal-data exposure suspected"}


# ---------------------------------------------------------------------------
# Markdown helpers (plain Markdown only)
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
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    s = scalar(v)
    return (s.replace("|", "\\|").replace("\n", " ") if s != "" else "_(empty)_")


def anchor(text: str) -> str:
    """GitHub-style heading anchor."""
    text = re.sub(r"[^\w\- ]", "", text.lower(), flags=re.UNICODE)
    return text.strip().replace(" ", "-")


def outcome(o: str) -> str:
    return f"{OUTCOME_ICON.get(o, '')} **{o}**"


def name(a: str) -> str:
    return AGENT_NAMES.get(a, a)


def agents(ids) -> str:
    return ", ".join(f"{name(a)} (`{a}`)" for a in ids) or "_none_"


def counts(c: dict) -> str:
    parts = [f"{outcome(o)} {c[o]}" for o in OUTCOMES if o in c]
    parts += [f"{k} {v}" for k, v in c.items() if k not in OUTCOMES]
    return ", ".join(parts) or "none"


def inline(v) -> str:
    if isinstance(v, (dict, list)):
        return "`" + json.dumps(v, ensure_ascii=False) + "`"
    return scalar(v) if scalar(v) != "" else "_(empty)_"


def bullets(items, empty: str = "_None recorded._") -> str:
    return "".join(f"- {inline(i)}\n" for i in items) if items else empty + "\n"


def quote(text: str) -> str:
    return "".join(f"> {line}\n" if line else ">\n" for line in scalar(text).split("\n"))


def fence(text: str, lang: str = "text") -> str:
    return f"~~~~{lang}\n{text}\n~~~~\n"


def table(headers: list[str], rows: list[list]) -> str:
    out = "| " + " | ".join(headers) + " |\n|" + "---|" * len(headers) + "\n"
    return out + "".join("| " + " | ".join(cell(c) if not isinstance(c, Raw) else c for c in r) + " |\n" for r in rows)


class Raw(str):
    """A table cell that is already Markdown."""


def kv(d: dict, keys=None) -> str:
    keys = [k for k in (keys if keys is not None else d) if k in d]
    return table(["Field", "Value"], [[label(k), d[k]] for k in keys]) if keys else ""


def generic(v, depth: int = 0) -> str:
    pad = "  " * depth
    if isinstance(v, dict):
        if not v:
            return f"{pad}- _(empty)_\n"
        out = ""
        for k, x in v.items():
            if isinstance(x, (dict, list)) and x:
                out += f"{pad}- **{label(k)}:**\n" + generic(x, depth + 1)
            else:
                out += f"{pad}- **{label(k)}:** {inline(x) if x not in ([], {}) else '_(empty)_'}\n"
        return out
    if isinstance(v, list):
        if not v:
            return f"{pad}- _(empty)_\n"
        return "".join(f"{pad}- Item {i}:\n" + generic(x, depth + 1) if isinstance(x, (dict, list))
                       else f"{pad}- {inline(x)}\n" for i, x in enumerate(v, 1))
    return f"{pad}- {inline(v)}\n"


def rest(d: dict, known: set) -> str:
    left = {k: v for k, v in d.items() if k not in known}
    return "**Other recorded fields:**\n\n" + generic(left) + "\n" if left else ""


def ref(c: dict) -> str:
    return f"{c.get('source_title', '')}, {c.get('section', '')}" + (f" (p. {c['page']})" if c.get("page") else "")


def cite_rows(cits: list) -> str:
    if not cits:
        return "_None._\n"
    rows = []
    for c in cits:
        if isinstance(c, dict):
            rows.append([c.get("source_title", ""), c.get("section", ""), c.get("page", ""), Raw(f"`{c.get('chunk_id', '')}`"),
                         Raw(inline({k: v for k, v in c.items() if k not in ("source_title", "section", "page", "chunk_id")}))
                         if set(c) - {"source_title", "section", "page", "chunk_id"} else ""])
        else:
            rows.append([c, "", "", "", ""])
    return table(["Source", "Section", "Page", "Chunk ID", "Other"], rows)


def strip_brackets(x: str) -> str:
    return str(x).strip().strip("[]")


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

def observations(start: dict, stages: list, end: dict | None, problems: list) -> list[str]:
    """Factual points a reader should notice, each read from the trail."""
    obs = []
    n_stages, planned = len(stages), start.get("stage_count")
    if not end:
        obs.append(f"**The run is incomplete.** Only {n_stages} of {planned} planned stages {'was' if n_stages == 1 else 'were'} recorded and there "
                   "is no `run_completed` entry, so the run stopped before the remaining stages were processed. "
                   "Everything below describes the stage(s) that were recorded.")
    obs.append("**The audit trail is intact.** Every entry's SHA-256 hash and its link to the previous entry check out."
               if not problems else "**The audit trail is broken:** " + "; ".join(problems))
    matched = sum(1 for s in stages if s.get("orchestrator", {}).get("matches_docx_table"))
    obs.append(f"**Agent selection matched the official DOCX stage table at {matched} of {n_stages} stage(s).**")
    totals: Counter = Counter()
    for s in stages:
        totals.update(s.get("verifier", {}).get("outcome_counts", {}))
    if not totals.get("VERIFIED"):
        obs.append(f"**No claim reached VERIFIED** ({counts(dict(totals))}). The quoted passages match the authoritative "
                   "text, but the in-force and amendment status of the sources was not confirmed, so the system "
                   "reports them as INCOMPLETE rather than overstating them; claims without a supporting passage are "
                   "UNSUPPORTED and treated as preliminary.")
    accepted = rejected = bracketed = 0
    for s in stages:
        for a in s.get("agents", []):
            llm = a.get("llm_reasoning") or {}
            offered = set(llm.get("passages_offered", []))
            accepted += len(llm.get("accepted_claims", []))
            for r in llm.get("rejected_claims", []):
                rejected += 1
                cites = r.get("cites", []) if isinstance(r, dict) else []
                if cites and all(strip_brackets(c) in offered for c in cites) and any(c != strip_brackets(c) for c in cites):
                    bracketed += 1
    if rejected or accepted:
        text = (f"**LLM claims: {accepted} accepted, {rejected} rejected** by the citation check before reaching the "
                "Verifier; only passages quoted from the knowledge base were verified.")
        if bracketed:
            text += (f" In {bracketed} of the rejected claims the LLM did cite passages it had been offered, but wrote "
                     "the IDs inside square brackets (e.g. `[3gpp_ts_23501:clause-5-45-2:1]`), so they did not match "
                     "the offered IDs exactly and were rejected as \"cites no retrieved passage id\".")
        obs.append(text)
    kb, llm = start.get("knowledge_base_build", {}), start.get("llm", {})
    if "none" in str(kb.get("generator_model", "")).lower() and llm.get("model"):
        obs.append(f"**The run header records two different statements about generation:** "
                   f"`generator_model` is \"{kb['generator_model']}\", while `llm` records "
                   f"{llm.get('provider')} · {llm.get('model')}, which the agents used for reasoning. Both are "
                   "reproduced as recorded.")
    if kb.get("not_ingested"):
        obs.append("**Sources not ingested into the knowledge base:** " + ", ".join(f"`{x}`" for x in kb["not_ingested"]) + ".")
    if start.get("code", {}).get("uncommitted_changes"):
        obs.append(f"**The run was made from commit `{start['code'].get('commit')}` with uncommitted changes.**")
    return obs


def front(path: Path, start: dict, stages: list, end: dict | None, problems: list) -> str:
    title = start.get("scenario_title", start.get("scenario_id", "Run"))
    last = (end or (stages[-1] if stages else start)).get("recorded_at", "")
    status = (f"✅ Complete — {end.get('stages_recorded')} of {start.get('stage_count')} stages" if end else
              f"⚠️ Incomplete — {len(stages)} of {start.get('stage_count')} stages recorded, run did not finish")
    md = f"# Audit Report: {title}\n\n"
    md += table(["Item", "Detail"], [
        ["Run ID", Raw(f"`{start.get('run_id')}`")], ["Scenario", f"{start.get('scenario_id')} (DOCX {start.get('docx_section', '')})"],
        ["Run started", start.get("recorded_at")], ["Last entry recorded", last], ["Run status", status],
        ["Audit-trail integrity", "✅ Intact" if not problems else "❌ Broken"],
        ["Source file", Raw(f"`{path.name}`")]]) + "\n"
    sections = ["1. Executive summary", "2. Run status and integrity", "3. Run configuration", "4. Incident timeline",
                "5. Stage-by-stage analysis", "6. Notifications that may be due", "7. Glossary",
                "Appendix A. Retrieved passages in full", "Appendix B. Claims and citations in full",
                "Appendix C. LLM prompts and responses", "Appendix D. Inputs visible to each agent",
                "Appendix E. Entry records and hash chain"]
    md += "## Contents\n\n" + "".join(f"- [{s}](#{anchor(s)})\n" for s in sections) + "\n---\n\n"
    return md


def executive(start: dict, stages: list, end: dict | None, problems: list) -> str:
    n = adviser_narrative(stages)
    totals: Counter = Counter()
    for s in stages:
        totals.update(s.get("verifier", {}).get("outcome_counts", {}))
    used = sorted({a for s in stages for a in s.get("orchestrator", {}).get("active_agents", [])})
    md = "## 1. Executive summary\n\n### Key figures\n\n"
    md += table(["Measure", "Value"], [
        ["Stages recorded", f"{len(stages)} of {start.get('stage_count')}"],
        ["Specialist agents used", f"{len(used)} ({', '.join(name(a) for a in used)})"],
        ["Passages retrieved", sum(len(a.get('retrieved_passages', [])) for s in stages for a in s.get('agents', []))],
        ["Claims checked by the Verifier", sum(totals.values())],
        ["Verifier outcomes", Raw(counts(dict(totals)))],
        ["Evidence-backed conclusions (final stage)", len(stages[-1].get("coordinator", {}).get("evidence_backed_conclusions", [])) if stages else 0],
        ["Agent selection matching DOCX table", f"{sum(1 for s in stages if s.get('orchestrator', {}).get('matches_docx_table'))} of {len(stages)}"]])
    md += f"\n### What happened\n\n{n['summary']}\n\n### What follows\n\n{n['conclusion']}\n\n"
    md += "_The two paragraphs above are produced by the project's `src/audit/narrative.py` from the recorded entries; " \
          "each sentence restates a recorded fact, quoted provision or Verifier outcome._\n\n"
    md += "### Observations for judges\n\n" + "".join(f"{i}. {o}\n" for i, o in enumerate(observations(start, stages, end, problems), 1))
    return md + "\n---\n\n"


def status_section(start: dict, stages: list, end: dict | None, problems: list, entries: list) -> str:
    md = "## 2. Run status and integrity\n\n"
    rows = [[e.get("seq"), e.get("type") + (f" {e['stage']['label']}" if e.get("type") == "stage" else ""), e.get("recorded_at")]
            for e in entries]
    md += "### Entries in the audit trail\n\n" + table(["Seq", "Entry", "Recorded at"], rows) + "\n"
    if end:
        md += "### Run completion entry\n\n" + kv(end) + "\n"
    else:
        md += (f"### Run completion\n\n⚠️ No `run_completed` entry was recorded. The header planned "
               f"{start.get('stage_count')} stages; {len(stages)} {'was' if len(stages) == 1 else 'were'} recorded. The remaining stages were not run "
               "or not recorded, so this report covers only the recorded stage(s).\n\n")
    md += "### Integrity check\n\n"
    md += ("✅ **Intact.** Each entry stores the SHA-256 of its own content (`hash`) and the hash of the entry before it "
           "(`prev_hash`). All hashes were recomputed with `src.audit.trail.verify_chain` and match, so no entry was "
           "edited, removed or reordered. The full chain is in [Appendix E](#appendix-e-entry-records-and-hash-chain).\n\n"
           if not problems else "❌ **Broken:**\n\n" + bullets(problems) + "\n")
    return md + "---\n\n"


def config_section(start: dict) -> str:
    md = "## 3. Run configuration\n\n### Run header\n\n"
    top = ["seq", "run_id", "type", "schema_version", "recorded_at", "scenario_id", "scenario_title", "docx_section",
           "stage_count", "knowledge_base_note", "prev_hash", "hash"]
    md += kv(start, top) + "\n"
    if "knowledge_bases_live" in start:
        md += "### Knowledge bases\n\n" + table(["Knowledge base", "Live"], [
            [k, "✅ true" if v else "❌ false"] for k, v in start["knowledge_bases_live"].items()]) + "\n"
    kb = start.get("knowledge_base_build")
    if kb is not None:
        md += "### Knowledge-base build\n\n" + kv({k: v for k, v in kb.items() if k != "not_ingested"}) + "\n"
        md += "**Not ingested:**\n\n" + bullets(kb.get("not_ingested", [])) + "\n"
    if "llm" in start:
        md += "### Language model\n\n" + kv(start["llm"]) + "\n"
    if "code" in start:
        md += "### Code version\n\n" + kv(start["code"]) + "\n"
    return md + rest(start, set(top) | {"knowledge_bases_live", "knowledge_base_build", "llm", "code"}) + "---\n\n"


def timeline_section(stages: list) -> str:
    md = "## 4. Incident timeline\n\n"
    rows = []
    for s in stages:
        st, o = s["stage"], s["orchestrator"]
        flags = [FLAG_NAMES.get(k, k) for k, v in s.get("coordinator", {}).get("incident_flags", {}).items() if v]
        rows.append([Raw(f"[{st['label']}](#{anchor(stage_heading(s))})"), st.get("scenario_time"), st.get("information_released"),
                     ", ".join(name(a) for a in o.get("active_agents", [])),
                     ", ".join(name(a) for a in o.get("newly_activated", [])) or "—",
                     Raw(counts(s.get("verifier", {}).get("outcome_counts", {}))), ", ".join(flags) or "none"])
    md += table(["Stage", "Scenario time", "Information released", "Agents active", "Newly activated",
                 "Verifier outcomes", "Flags raised"], rows) if rows else "_No stages recorded._\n"
    return md + "\n---\n\n"


def stage_heading(s: dict) -> str:
    return f"5.{s['stage'].get('index', 0) + 1} Stage {s['stage']['label']}"


def agent_section(s: dict, a: dict, num: str) -> str:
    aid, lab = a.get("agent_id", ""), s["stage"]["label"]
    md = f"#### {num} {name(aid)} agent\n\n"
    md += f"**Decision summary:** {a.get('decision_summary', '')}\n\n"
    m = a.get("mandate_output", {})
    md += "**Mandate output:**\n\n" + (generic(m) if m else "_(empty)_\n") + "\n"
    md += "**Search queries used:**\n\n" + "".join(f"{i}. {q}\n" for i, q in enumerate(a.get("queries", []), 1)) + "\n"
    ps = a.get("retrieved_passages", [])
    md += f"**Evidence retrieved ({len(ps)} passages; full text in [Appendix A](#appendix-a-retrieved-passages-in-full)):**\n\n"
    md += table(["#", "Source", "Section", "Section title", "Page", "Relevance", "Chunk ID"],
                [[i, p.get("source_title"), p.get("section"), p.get("section_title"), p.get("page"), p.get("relevance_score"),
                  Raw(f"`{p.get('chunk_id')}`")] for i, p in enumerate(ps, 1)]) + "\n" if ps else "_None._\n\n"
    claims = a.get("claims", [])
    md += (f"**Claims and verification ({len(claims)}: {counts(dict(Counter(c.get('verifier_outcome') for c in claims)))}; "
           "citations in full in [Appendix B](#appendix-b-claims-and-citations-in-full)):**\n\n")
    md += table(["#", "Claim", "Verifier outcome", "Verifier rationale"],
                [[i, c.get("claim"), Raw(outcome(c.get("verifier_outcome", ""))), c.get("verifier_rationale")]
                 for i, c in enumerate(claims, 1)]) + "\n" if claims else "_No claims._\n\n"
    md += "**Uncertainty noted by the agent:**\n\n" + bullets(a.get("uncertainty_notes", [])) + "\n"
    md += "**Missing facts noted by the agent:**\n\n" + bullets(a.get("missing_facts", [])) + "\n"
    llm = a.get("llm_reasoning")
    if llm:
        md += "**LLM-assisted reasoning** (prompts and raw output in [Appendix C](#appendix-c-llm-prompts-and-responses)):\n\n"
        md += table(["Field", "Value"], [["Provider / model", f"{llm.get('provider')} · {llm.get('model')}"],
                                         ["Outcome", llm.get("status")], ["Latency (ms)", llm.get("latency_ms")],
                                         ["Tokens", ", ".join(f"{k} {v}" for k, v in (llm.get("usage") or {}).items())]]) + "\n"
        md += f"Reasoning summary:\n\n{quote(llm.get('reasoning_summary', ''))}\n"
        acc, rej = llm.get("accepted_claims", []), llm.get("rejected_claims", [])
        md += "Accepted claims:\n\n" + (generic(acc) if acc else "_None._\n") + "\n"
        md += "Rejected claims:\n\n"
        md += table(["#", "Claim proposed by the LLM", "Passages it cited", "Reason rejected"],
                    [[i, r.get("claim"), Raw(", ".join(f"`{c}`" for c in r.get("cites", [])) or "_none_"), r.get("reason")]
                     if isinstance(r, dict) else [i, r, "", ""] for i, r in enumerate(rej, 1)]) + "\n" if rej else "_None._\n\n"
    elif "llm_reasoning" in a:
        md += "**LLM-assisted reasoning:** _none recorded._\n\n"
    return md + rest(a, {"agent_id", "decision_summary", "mandate_output", "queries", "retrieved_passages", "claims",
                         "uncertainty_notes", "missing_facts", "llm_reasoning", "visible_input"})


def link_list(links: list) -> str:
    if not links:
        return "_None._\n"
    md = ""
    for i, l in enumerate(links, 1):
        if not isinstance(l, dict):
            md += f"{i}. {inline(l)}\n"
            continue
        md += (f"{i}. **{' ↔ '.join(name(x) for x in l.get('agents', []))}**"
               + (f", kind `{l['kind']}`" if "kind" in l else "") + (f", chunk `{l['chunk_id']}`" if "chunk_id" in l else "")
               + f": {l.get('note', '')}\n")
        for mbr in l.get("members", []):
            md += f"    - Member: {name(mbr.get('agent_id', ''))} at `{mbr.get('chunk_id', '')}`: {mbr.get('claim', '')}\n"
            extra = {k: v for k, v in mbr.items() if k not in ("agent_id", "chunk_id", "claim")}
            md += generic(extra, 3) if extra else ""
        extra = {k: v for k, v in l.items() if k not in ("agents", "kind", "chunk_id", "note", "members")}
        md += generic(extra, 2) if extra else ""
    return md


def stage_section(s: dict) -> str:
    st, o, v, c = s["stage"], s["orchestrator"], s.get("verifier", {}), s.get("coordinator", {})
    h = stage_heading(s)
    md = f"### {h}\n\n**Scenario time:** {st.get('scenario_time')}  \n**Chunk:** `{st.get('chunk_id')}`\n\n"
    md += f"#### What was released\n\n{quote(st.get('information_released', ''))}\n"
    md += "**New facts:**\n\n" + bullets(st.get("new_facts", [])) + "\n"
    av = st.get("agent_views", {})
    md += "**Information released only to specific agents:**\n\n"
    md += ("".join(f"- {name(k)} (`{k}`) only:\n" + "".join(f"    - {x}\n" for x in vals) for k, vals in av.items()) or "_None._\n") + "\n"
    md += "**Prior chunks considered:** " + (", ".join(f"`{x}`" for x in st.get("prior_chunks", [])) or "_none (first stage)_") + "\n\n"
    md += table(["Official DOCX stage table", "Text"], [["Information released", st.get("docx_information_released")],
                                                         ["Expected change", st.get("docx_expected_change")]]) + "\n"
    md += rest(st, {"index", "label", "chunk_id", "scenario_time", "information_released", "new_facts", "agent_views",
                    "prior_chunks", "docx_information_released", "docx_expected_change"})
    md += "#### Agents selected by the Orchestrator\n\n"
    md += table(["Item", "Agents"], [["Active", agents(o.get("active_agents", []))],
                                     ["Newly activated", agents(o.get("newly_activated", []))],
                                     ["No longer active (conclusions carried forward)", agents(o.get("no_longer_active", []))],
                                     ["Primary agents in the DOCX table", agents(o.get("docx_primary_agents", []))],
                                     ["Matches the DOCX table", "✅ Yes" if o.get("matches_docx_table") else f"❌ {scalar(o.get('matches_docx_table'))}"]]) + "\n"
    md += rest(o, {"active_agents", "newly_activated", "no_longer_active", "docx_primary_agents", "matches_docx_table"})
    md += "#### Findings of the specialist agents\n\n"
    base = h.split(" ")[0]
    md += "".join(agent_section(s, a, f"{base}.{i}") for i, a in enumerate(s.get("agents", []), 1))
    md += f"#### Verification\n\n**Outcome counts:** {counts(v.get('outcome_counts', {}))}\n\n"
    md += "**Cross-domain links:**\n\n" + bullets(v.get("cross_domain_links", []), "_None._") + "\n"
    md += "**Cross-domain link details:**\n\n" + link_list(v.get("cross_domain_details", [])) + "\n"
    md += "**Conflicts:**\n\n" + bullets(v.get("conflicts", []), "_None._") + "\n"
    md += "**Conflict details:**\n\n" + (generic(v["conflict_details"]) if v.get("conflict_details") else "_None._\n") + "\n"
    md += "**Missing evidence:**\n\n" + bullets(v.get("missing_evidence", [])) + "\n"
    md += rest(v, {"outcome_counts", "cross_domain_links", "conflicts", "missing_evidence", "cross_domain_details", "conflict_details"})
    md += f"#### Coordinator assessment\n\n**Chunk:** `{c.get('chunk_id')}` · **Active agents:** {agents(c.get('active_agents', []))}\n\n"
    md += "**Incident flags:**\n\n" + table(["Flag", "Raised"], [[FLAG_NAMES.get(k, k) + f" (`{k}`)", "✅ true" if x else "false"]
                                                                 for k, x in c.get("incident_flags", {}).items()]) + "\n"
    for key, title in (("changes_from_prior", "What changed from the previous stage"), ("confirmed_facts", "Confirmed facts"),
                       ("evidence_backed_conclusions", "Evidence-backed conclusions"),
                       ("uncertain_conclusions", "Uncertain or preliminary conclusions"),
                       ("conflicting_findings", "Conflicting findings"),
                       ("potential_policy_gaps", "Potential policy gaps (for expert review)"),
                       ("cross_domain_relationships", "Cross-domain relationships"),
                       ("relevant_institutions", "Relevant institutions"), ("open_questions", "Open questions")):
        items = c.get(key, [])
        md += f"**{title} ({len(items)}):**\n\n" + ("".join(f"{i}. {inline(x)}\n" for i, x in enumerate(items, 1)) if items else "_None._\n") + "\n"
    reg = c.get("claim_register", [])
    md += f"**Claim register ({len(reg)}):**\n\n"
    known_r = ("agent_id", "outcome", "claim", "rationale", "citations", "chunk_id", "carried_forward", "in_conflict")
    md += table(["#", "Agent", "Outcome", "Claim", "Rationale", "Citations", "Chunk", "Carried forward", "In conflict"],
                [[i, name(r.get("agent_id", "")), Raw(outcome(r.get("outcome", ""))), r.get("claim"), r.get("rationale"),
                  "; ".join(map(str, r.get("citations", []))) or "—", r.get("chunk_id"), r.get("carried_forward"), r.get("in_conflict")]
                 for i, r in enumerate(reg, 1)]) + "\n" if reg else "_Empty._\n\n"
    extras = [{k: x for k, x in r.items() if k not in known_r} for r in reg]
    md += ("**Claim register, other recorded fields:**\n\n" + generic(extras) + "\n") if any(extras) else ""
    md += "**Link register:**\n\n" + link_list(c.get("link_register", [])) + "\n"
    md += f"**Human review required:** {c.get('human_review_required', '')}\n\n"
    md += rest(c, {"chunk_id", "active_agents", "confirmed_facts", "evidence_backed_conclusions", "uncertain_conclusions",
                   "conflicting_findings", "potential_policy_gaps", "cross_domain_relationships", "relevant_institutions",
                   "changes_from_prior", "open_questions", "claim_register", "incident_flags", "link_register",
                   "human_review_required"})
    return md + rest(s, {"seq", "run_id", "type", "scenario_id", "recorded_at", "pipeline_timestamp", "prev_hash", "hash",
                         "stage", "orchestrator", "agents", "verifier", "coordinator"})


def notifications_section(stages: list) -> str:
    rows = adviser_narrative(stages)["notifications"]
    md = "## 6. Notifications that may be due\n\n_Read from the quoted Indian provisions; each must be confirmed by a qualified person before it is sent._\n\n"
    md += table(["To", "Time limit", "Provision", "Page", "Applies if", "Raised by", "First raised"],
                [[r["recipient"], ", then ".join(r["limits"]), f"{r['source']}, {r['section']}", r.get("page", ""), r["condition"],
                  ", ".join(name(a) for a in r.get("agents", [])), r["stage"]] for r in rows]) if rows else \
        "No reporting duty with a recipient or time limit appears in the provisions quoted in the recorded stage(s).\n"
    return md + "\n---\n\n"


def glossary() -> str:
    md = "## 7. Glossary\n\n**Verifier outcomes**\n\n" + table(["Outcome", "Meaning"], [[Raw(outcome(o)), OUTCOME_HELP[o]] for o in OUTCOMES])
    md += "\n**Terms**\n\n" + table(["Term", "Meaning"], [
        ["Stage (T0, T1, …)", "One release of incident information; the scenario is revealed stage by stage."],
        ["Orchestrator", "Chooses which specialist agents act at each stage from what that stage reveals."],
        ["Specialist agent", "Retrieves passages from its own knowledge base and makes claims quoting them."],
        ["Verifier", "Checks every claim against the separate Canonical knowledge base."],
        ["Coordinator", "Combines verified findings into facts, conclusions, conflicts, gaps and open questions."],
        ["Chunk ID", "Identifier of the stage, or of a passage in a knowledge base (document:section:part)."],
        ["REFERENCE ONLY — not Indian law", "International standard used as a reference point, never as an Indian obligation."],
        ["Hash chain", "Each entry carries a SHA-256 of its content and of the previous entry, so edits are detectable."]])
    return md + "\n---\n\n"


def appendix_passages(stages: list) -> str:
    md = "## Appendix A. Retrieved passages in full\n\n"
    known = ["source_title", "authority", "jurisdiction", "document_type", "section", "section_title", "page", "date_issued",
             "effective", "effective_status", "amendment_checked", "amendment_note", "url", "provenance_note", "chunk_id",
             "relevance_score", "is_stub"]
    for s in stages:
        for a in s.get("agents", []):
            ps = a.get("retrieved_passages", [])
            md += f"### Stage {s['stage']['label']}: {name(a.get('agent_id', ''))} agent ({len(ps)} passages)\n\n"
            for i, p in enumerate(ps, 1):
                md += f"#### A.{s['stage']['label']}.{a.get('agent_id')}.{i} {ref(p)}\n\n" + kv(p, known)
                md += "\n**Excerpt:**\n\n" + quote(p.get("excerpt", "")) + "\n" + rest(p, set(known) | {"excerpt"})
    return md + "---\n\n"


def appendix_claims(stages: list) -> str:
    md = "## Appendix B. Claims and citations in full\n\n"
    for s in stages:
        for a in s.get("agents", []):
            md += f"### Stage {s['stage']['label']}: {name(a.get('agent_id', ''))} agent\n\n"
            for i, c in enumerate(a.get("claims", []), 1):
                md += f"#### Claim {s['stage']['label']}.{a.get('agent_id')}.{i}: {outcome(c.get('verifier_outcome', ''))}\n\n"
                md += quote(c.get("claim", "")) + "\n"
                md += f"- **Verifier rationale:** {c.get('verifier_rationale', '')}\n"
                md += f"- **Cross-domain flag:** {scalar(c.get('cross_domain_flag'))}\n"
                md += f"- **Cross-domain note:** {inline(c.get('cross_domain_note', ''))}\n\n"
                md += "**Citations given by the agent:**\n\n" + cite_rows(c.get("citations", [])) + "\n"
                md += "**Passages the Verifier found supporting:**\n\n" + cite_rows(c.get("verifier_supporting", [])) + "\n"
                md += "**Passages the Verifier checked that do not support the claim:**\n\n" + cite_rows(c.get("verifier_conflicting", [])) + "\n"
                md += rest(c, {"claim", "citations", "verifier_outcome", "verifier_rationale", "verifier_supporting",
                               "verifier_conflicting", "cross_domain_flag", "cross_domain_note"})
    return md + "---\n\n"


def appendix_llm(stages: list) -> str:
    md = "## Appendix C. LLM prompts and responses\n\n"
    known = {"provider", "model", "status", "latency_ms", "prompt_sha256", "usage", "reasoning_summary", "passages_offered",
             "accepted_claims", "rejected_claims", "system_prompt", "user_prompt", "raw_response"}
    for s in stages:
        for a in s.get("agents", []):
            llm = a.get("llm_reasoning")
            if not llm:
                continue
            md += f"### Stage {s['stage']['label']}: {name(a.get('agent_id', ''))} agent\n\n"
            md += kv(llm, ["provider", "model", "status", "latency_ms", "prompt_sha256"])
            md += "\n**Token usage:** " + (", ".join(f"{k} {v}" for k, v in (llm.get("usage") or {}).items()) or "_none_") + "\n\n"
            md += "**Passages offered to the LLM:**\n\n" + "".join(f"- `{p}`\n" for p in llm.get("passages_offered", [])) + "\n"
            for r_i, r in enumerate(llm.get("rejected_claims", []), 1):
                if isinstance(r, dict) and set(r) - {"claim", "cites", "reason"}:
                    md += f"**Rejected claim {r_i}, other recorded fields:**\n\n" + generic({k: v for k, v in r.items() if k not in ("claim", "cites", "reason")}) + "\n"
            for key, title, lang in (("system_prompt", "System prompt", "text"), ("user_prompt", "User prompt", "text"),
                                     ("raw_response", "Raw LLM response", "json")):
                if key in llm:
                    md += f"**{title}:**\n\n" + fence(scalar(llm[key]), lang) + "\n"
            md += rest(llm, known)
    return md + "---\n\n"


def appendix_inputs(stages: list) -> str:
    md = "## Appendix D. Inputs visible to each agent\n\n"
    known = {"chunk_id", "information_released", "new_facts", "agent_view", "prior_chunk_ids", "incident_state"}
    for s in stages:
        for a in s.get("agents", []):
            vi = a.get("visible_input", {})
            md += f"### Stage {s['stage']['label']}: {name(a.get('agent_id', ''))} agent\n\n"
            md += kv(vi, ["chunk_id", "information_released"])
            md += "\n**New facts:**\n\n" + bullets(vi.get("new_facts", []))
            md += "\n**Information only this agent received:**\n\n" + bullets(vi.get("agent_view", []), "_None._")
            md += "\n**Prior chunk IDs:**\n\n" + bullets(vi.get("prior_chunk_ids", []), "_None._")
            md += "\n**Incident state passed to the agent:**\n\n" + generic(vi.get("incident_state", {})) + "\n"
            md += rest(vi, known)
    return md + "---\n\n"


def appendix_chain(path: Path, entries: list) -> str:
    md = ("## Appendix E. Entry records and hash chain\n\n"
          f"Source file `{path.name}`. Each `hash` is the SHA-256 of the entry without its `hash` field; each `prev_hash` "
          "is the previous entry's `hash`.\n\n")
    rows = []
    for e in entries:
        rows.append([e.get("seq"), e.get("type") + (f" {e['stage']['label']}" if e.get("type") == "stage" else ""),
                     e.get("run_id"), e.get("scenario_id", "—"), e.get("recorded_at"), e.get("pipeline_timestamp", "—"),
                     Raw(f"`{e.get('prev_hash')}`"), Raw(f"`{e.get('hash')}`")])
    md += table(["Seq", "Entry", "Run ID", "Scenario", "Recorded at", "Pipeline timestamp", "prev_hash", "hash"], rows)
    others = [e for e in entries if e.get("type") not in ("run_started", "stage", "run_completed")]
    if others:
        md += "\n**Other entries:**\n\n" + generic(others)
    return md + ("\n---\n\n**Decision support only.** Legal interpretation, regulatory decisions and institutional action "
                 "remain with qualified people.\n")


def build(path: Path) -> str:
    entries = read_entries(path)
    problems = verify_chain(entries)
    start = next((e for e in entries if e.get("type") == "run_started"), {})
    stages = [e for e in entries if e.get("type") == "stage"]
    end = next((e for e in entries if e.get("type") == "run_completed"), None)
    md = front(path, start, stages, end, problems) + executive(start, stages, end, problems)
    md += status_section(start, stages, end, problems, entries) + config_section(start) + timeline_section(stages)
    md += "## 5. Stage-by-stage analysis\n\n" + "".join(stage_section(s) + "\n" for s in stages) + "---\n\n"
    md += notifications_section(stages) + glossary()
    md += appendix_passages(stages) + appendix_claims(stages) + appendix_llm(stages) + appendix_inputs(stages)
    return md + appendix_chain(path, entries)


def check_complete(path: Path, md: str) -> list[str]:
    """Every recorded scalar value must appear in the report; returns the ones that do not."""
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
    ap.add_argument("-o", "--output", type=Path, help="default: <trail>_report.md next to the trail")
    args = ap.parse_args()
    out = args.output or args.trail.with_name(args.trail.stem + "_report.md")
    md = build(args.trail)
    out.write_text(md, encoding="utf-8")
    missing = check_complete(args.trail, md)
    print(out, "— complete: every recorded value is in the report" if not missing
          else f"— {len(missing)} value(s) missing:\n" + "\n".join(missing[:20]))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
