"""
Judge report
============
Turns one audit-trail JSON Lines file (see trail.py) into a single,
self-contained HTML page a judge can read in a browser or print to PDF:

    1. Run facts and an integrity check of the hash chain
    2. Plain-language summary, conclusion and the notifications that may be due
    3. A one-table timeline of the stages
    4. One section per stage: what was released, which agents acted, every
       claim with its citation and Verifier outcome, the Coordinator's view
    5. The full detail (retrieved passages, LLM reasoning) folded away

Nothing is added: every line restates a recorded field.

    python -m src.audit.judge_report outputs/audit/<run>.jsonl [-o report.html]
"""

from __future__ import annotations

import argparse
import html
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
OUTCOME_HELP = {
    "VERIFIED": "Supported by the authoritative text, with in-force status and amendments checked.",
    "INCOMPLETE": "Supported by the authoritative text, but in-force status, amendments or a related "
                  "provision were not confirmed.",
    "UNSUPPORTED": "The Canonical KB passages checked do not support the claim; preliminary only.",
    "CONFLICT": "Authoritative sources disagree; the Coordinator records both sides.",
}
MANDATE_LABELS = {
    "incident_class": "Incident class", "affected_components": "Affected components",
    "applicable_provisions": "Applicable provisions", "responsible_institutions": "Responsible institutions",
    "obligations": "Obligations quoted", "exposure_status": "Personal-data exposure",
    "cii_relevant": "Critical-infrastructure relevant", "standards_compared": "Standards compared",
    "gap_category": "Gap category", "gap_description": "Gap description",
}

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#5f6368;--line:#dcd9d2;--card:#fff;--accent:#1f4e79;
--ok:#1e7b34;--okbg:#e3f3e6;--warn:#8a5a00;--warnbg:#fdf0d5;--bad:#a12622;--badbg:#fbe3e1;
--info:#3c4b9c;--infobg:#e6e9f8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#17181a;--fg:#e8e6e1;
--muted:#a3a7ad;--line:#33353a;--card:#1f2124;--accent:#8db8e3;--ok:#7fd391;--okbg:#1f3324;
--warn:#f0c46a;--warnbg:#3a2f17;--bad:#f39a95;--badbg:#3d1f1e;--info:#a9b4f0;--infobg:#24284a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,"Segoe UI",Roboto,
Helvetica,Arial,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.7rem;margin:.2em 0}h2{font-size:1.3rem;margin:2em 0 .6em;padding-bottom:.25em;
border-bottom:2px solid var(--accent)}h3{font-size:1.08rem;margin:1.4em 0 .4em}h4{margin:1em 0 .3em;font-size:.97rem}
.muted{color:var(--muted)}.small{font-size:.85rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 18px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.stat b{display:block;font-size:1.4rem}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:.92rem}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--bg)}
.wrap{overflow-x:auto}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:.78rem;font-weight:600;white-space:nowrap}
.VERIFIED,.ok{background:var(--okbg);color:var(--ok)}.INCOMPLETE,.warn{background:var(--warnbg);color:var(--warn)}
.UNSUPPORTED,.CONFLICT,.bad{background:var(--badbg);color:var(--bad)}.agent{background:var(--infobg);color:var(--info)}
details{margin:8px 0}summary{cursor:pointer;font-weight:600;color:var(--accent)}
blockquote{margin:6px 0;padding:4px 12px;border-left:3px solid var(--line);color:var(--muted);font-size:.88rem}
ul{padding-left:1.3em}li{margin:2px 0}
.notice{border-left:4px solid var(--warn);background:var(--warnbg);padding:10px 14px;border-radius:4px}
nav a{color:var(--accent);margin-right:12px}
code{font-size:.82rem;word-break:break-all}
@media print{details{display:block}details>*{display:block}summary{display:none}
.card,.stat,table{break-inside:avoid}h2{break-before:page}body{font-size:12px}}
"""


def e(text) -> str:
    return html.escape("" if text is None else str(text))


def agent(name: str) -> str:
    return f'<span class="badge agent">{e(AGENT_NAMES.get(name, name))}</span>'


def badge(outcome: str) -> str:
    return f'<span class="badge {e(outcome)}" title="{e(OUTCOME_HELP.get(outcome, ""))}">{e(outcome)}</span>'


def ul(items, cls: str = "") -> str:
    items = [i for i in items if i]
    if not items:
        return '<p class="muted small">None recorded.</p>'
    return f'<ul class="{cls}">' + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>"


def ref(c: dict) -> str:
    return f"{c['source_title']}, {c['section']}" + (f" (p. {c['page']})" if c.get("page") else "")


def counts_text(counts: dict) -> str:
    return " ".join(f"{badge(o)}&nbsp;{counts[o]}" for o in OUTCOMES if counts.get(o))


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def header(start: dict, stages: list[dict], end: dict | None, problems: list[str]) -> str:
    kb = start.get("knowledge_base_build", {})
    llm = start.get("llm", {})
    live = start.get("knowledge_bases_live", {})
    totals: Counter = Counter()
    for s in stages:
        totals.update(s["verifier"]["outcome_counts"])
    claims = sum(totals.values())
    passages = sum(len(a["retrieved_passages"]) for s in stages for a in s["agents"])
    agents_used = sorted({a for s in stages for a in s["orchestrator"]["active_agents"]})
    integrity = ('<span class="badge ok">Intact</span> every entry\'s SHA-256 hash and link to the '
                 'previous entry check out, so no entry was edited, removed or reordered.'
                 if not problems else '<span class="badge bad">Broken</span> ' + e("; ".join(problems)))
    completed = (f"completed at {e(end['recorded_at'])} with {end['stages_recorded']} stage(s)"
                 if end else '<span class="badge bad">run did not complete</span>')
    return f"""
<p class="muted small">Audit-trail report · run <code>{e(start['run_id'])}</code></p>
<h1>{e(start.get('scenario_title', start.get('scenario_id')))}</h1>
<p class="muted">Scenario <b>{e(start.get('scenario_id'))}</b> (DOCX {e(start.get('docx_section', ''))}) ·
started {e(start['recorded_at'])} · {completed}</p>
<div class="grid">
 <div class="stat"><b>{len(stages)}</b>stages released</div>
 <div class="stat"><b>{len(agents_used)}</b>specialist agents used</div>
 <div class="stat"><b>{passages}</b>passages retrieved</div>
 <div class="stat"><b>{claims}</b>claims verified</div>
 <div class="stat"><b>{sum(s['orchestrator'].get('matches_docx_table') is True for s in stages)}/{len(stages)}</b>
   agent selections match DOCX table</div>
</div>
<div class="card">
<table>
<tr><th style="width:28%">Hash-chain integrity</th><td>{integrity}</td></tr>
<tr><th>Verifier outcomes (all stages)</th><td>{counts_text(totals)}</td></tr>
<tr><th>Language model</th><td>{e(llm.get('provider'))} · {e(llm.get('model'))}</td></tr>
<tr><th>Embedding model</th><td>{e(kb.get('embedding_model'))}</td></tr>
<tr><th>Generation policy</th><td>{e(kb.get('generator_model'))}</td></tr>
<tr><th>Knowledge bases live</th><td>{', '.join(e(k) + (' ✓' if v else ' ✗') for k, v in live.items())}</td></tr>
<tr><th>Not ingested</th><td>{e(', '.join(kb.get('not_ingested', [])) or 'none')}</td></tr>
<tr><th>Sandbox</th><td>{e(kb.get('sandbox'))}</td></tr>
<tr><th>KB built</th><td>{e(kb.get('built_at'))} · manifest <code>{e(kb.get('ingestion_manifest_sha256'))}</code></td></tr>
<tr><th>Code</th><td><code>{e(start.get('code', {}).get('commit'))}</code>
{' (with uncommitted changes)' if start.get('code', {}).get('uncommitted_changes') else ''}</td></tr>
</table></div>"""


def summary(stages: list[dict]) -> str:
    n = adviser_narrative(stages)
    rows = "".join(
        f"<tr><td>{e(r['recipient'])}</td><td>{e(', then '.join(r['limits']))}</td>"
        f"<td>{e(r['source'])}, {e(r['section'])}{' (p. ' + e(r['page']) + ')' if r.get('page') else ''}</td>"
        f"<td>{e(r['condition'])}</td><td>{e(r['stage'])}</td></tr>"
        for r in n["notifications"])
    table = (f"""<div class="wrap"><table><tr><th>To</th><th>Time limit</th><th>Provision</th>
<th>Applies if</th><th>First raised</th></tr>{rows}</table></div>""" if rows
             else '<p class="muted">No reporting duty was found in the quoted provisions.</p>')
    return f"""
<h2 id="summary">1. Summary and conclusion</h2>
<h3>What happened</h3><div class="card">{e(n['summary'])}</div>
<h3>What follows</h3><div class="card">{e(n['conclusion'])}</div>
<h3>Notifications that may be due</h3>
<p class="muted small">Read from the quoted Indian provisions; each must be confirmed by a qualified person.</p>
{table}"""


def timeline(stages: list[dict]) -> str:
    rows = []
    for s in stages:
        st, o = s["stage"], s["orchestrator"]
        flags = s["coordinator"].get("incident_flags", {})
        raised = [label for key, label in (("cyber_event_suspected", "cyber event suspected"),
                                           ("cii_flagged", "critical infrastructure"),
                                           ("data_exposure_suspected", "personal data")) if flags.get(key)]
        rows.append(
            f"<tr><td><a href='#{e(st['label'])}'><b>{e(st['label'])}</b></a><br>"
            f"<span class='small muted'>{e(st['scenario_time'])}</span></td>"
            f"<td>{e(st['information_released'])}</td>"
            f"<td>{' '.join(agent(a) for a in o['active_agents'])}"
            f"{'<br><span class=small>✓ matches DOCX</span>' if o.get('matches_docx_table') else ''}</td>"
            f"<td>{counts_text(s['verifier']['outcome_counts'])}</td>"
            f"<td>{e(', '.join(raised) or '—')}</td></tr>")
    return f"""
<h2 id="timeline">2. Timeline of the incident</h2>
<div class="wrap"><table><tr><th>Stage</th><th>Information released</th><th>Agents active</th>
<th>Verifier outcomes</th><th>Flags raised</th></tr>{''.join(rows)}</table></div>
<h4>How to read the Verifier outcomes</h4>
<table>{''.join(f'<tr><td style="width:18%">{badge(o)}</td><td>{e(OUTCOME_HELP[o])}</td></tr>' for o in OUTCOMES)}</table>"""


def claims_table(claims: list[dict]) -> str:
    rows = []
    for c in claims:
        cites = "<br>".join(e(ref(x)) for x in c["citations"]) or '<span class="muted">no citation</span>'
        cross = f"<br><span class='small'>↔ {e(c['cross_domain_note'])}</span>" if c.get("cross_domain_flag") else ""
        rows.append(f"<tr><td>{e(c['claim'])}{cross}</td><td class='small'>{cites}</td>"
                    f"<td>{badge(c['verifier_outcome'])}<div class='small muted'>{e(c['verifier_rationale'])}</div></td></tr>")
    return (f"<div class='wrap'><table><tr><th style='width:46%'>Claim</th><th style='width:20%'>Cites</th>"
            f"<th>Verifier</th></tr>{''.join(rows)}</table></div>")


def mandate(m: dict) -> str:
    rows = []
    for k, v in m.items():
        if v in (None, "", [], False) and k != "cii_relevant":
            continue
        if isinstance(v, list):
            cell = ul(v)
        elif isinstance(v, bool):
            cell = "yes" if v else "no"
        else:
            cell = e(v)
        rows.append(f"<tr><th style='width:24%'>{e(MANDATE_LABELS.get(k, k))}</th><td>{cell}</td></tr>")
    return f"<table>{''.join(rows)}</table>" if rows else ""


def agent_block(a: dict) -> str:
    llm = a.get("llm_reasoning") or {}
    passages = "".join(
        f"<li><b>{e(ref(p))}</b> <span class='small muted'>({e(p['authority'])}, {e(p['document_type'])}, "
        f"relevance {p['relevance_score']})</span><blockquote>{e(p['excerpt'])}</blockquote></li>"
        for p in a["retrieved_passages"] if not p.get("is_stub"))
    rejected = "".join(f"<li>{e(r['claim'])} <span class='small muted'>— rejected: {e(r['reason'])}</span></li>"
                       for r in llm.get("rejected_claims", []))
    accepted = "".join(f"<li>{e(r['claim'] if isinstance(r, dict) else r)}</li>" for r in llm.get("accepted_claims", []))
    llm_html = ""
    if llm:
        llm_html = f"""<details><summary>LLM reasoning ({e(llm.get('model'))}): {e(llm.get('status'))}</summary>
<p>{e(llm.get('reasoning_summary'))}</p>
{'<h4>Accepted claims</h4><ul>' + accepted + '</ul>' if accepted else ''}
{'<h4>Rejected claims (not passed on)</h4><ul>' + rejected + '</ul>' if rejected else ''}
<p class="small muted">Latency {llm.get('latency_ms')} ms · tokens {e(llm.get('usage'))} ·
prompt SHA-256 <code>{e(llm.get('prompt_sha256'))}</code></p></details>"""
    return f"""<div class="card">
<h4>{agent(a['agent_id'])} {e(a['decision_summary'])}</h4>
{mandate(a.get('mandate_output', {}))}
<h4>Claims and verification</h4>{claims_table(a['claims'])}
{'<h4>Uncertainty</h4>' + ul(a['uncertainty_notes']) if a.get('uncertainty_notes') else ''}
{'<h4>Missing facts</h4>' + ul(a['missing_facts']) if a.get('missing_facts') else ''}
<details><summary>Queries and {len(a['retrieved_passages'])} retrieved passage(s)</summary>
<p class="small"><b>Queries:</b> {e(' | '.join(a.get('queries', [])))}</p><ol>{passages}</ol></details>
{llm_html}</div>"""


def stage_section(s: dict, number: int) -> str:
    st, o, c, v = s["stage"], s["orchestrator"], s["coordinator"], s["verifier"]
    joined = f"Newly activated: {' '.join(agent(a) for a in o['newly_activated'])}" if o["newly_activated"] else ""
    left = (f" · Carried forward, not re-examined: {' '.join(agent(a) for a in o['no_longer_active'])}"
            if o.get("no_longer_active") else "")
    conflicts = [f"{x.get('basis', '')} Treatment: {x.get('coordinator_treatment', '')}"
                 for x in v.get("conflict_details", [])] or c["conflicting_findings"]
    return f"""
<h2 id="{e(st['label'])}">3.{number} Stage {e(st['label'])} — {e(st['scenario_time'])}</h2>
<div class="card"><p><b>Information released:</b> {e(st['information_released'])}</p>
<h4>New facts</h4>{ul(st['new_facts'])}
{''.join(f"<h4>Seen only by {agent(k)}</h4>{ul(vals)}" for k, vals in st.get('agent_views', {}).items())}
<p class="small muted"><b>Expected change (DOCX):</b> {e(st.get('docx_expected_change'))}</p></div>
<h3>Orchestrator</h3>
<p>Active: {' '.join(agent(a) for a in o['active_agents'])}<br>{joined}{left}<br>
<span class="small">DOCX primary agents: {', '.join(e(AGENT_NAMES.get(a, a)) for a in o['docx_primary_agents'])}
— {'<span class="badge ok">match</span>' if o.get('matches_docx_table') else '<span class="badge bad">differs</span>'}</span></p>
<h3>Specialist agents</h3>{''.join(agent_block(a) for a in s['agents'])}
<h3>Verifier</h3>
<p>{counts_text(v['outcome_counts'])}</p>
<h4>Cross-domain links ({len(v.get('cross_domain_links', []))})</h4>{ul(v.get('cross_domain_links', []))}
<h4>Conflicts</h4>{ul(conflicts)}
<h4>Missing evidence</h4>{ul(v.get('missing_evidence', []))}
<h3>Coordinator assessment</h3>
<div class="card">
<h4>What changed from the previous stage</h4>{ul(c['changes_from_prior'])}
<h4>Evidence-backed conclusions ({len(c['evidence_backed_conclusions'])})</h4>{ul(c['evidence_backed_conclusions'])}
<details><summary>Uncertain / preliminary conclusions ({len(c['uncertain_conclusions'])})</summary>{ul(c['uncertain_conclusions'])}</details>
<details><summary>Confirmed facts ({len(c['confirmed_facts'])})</summary>{ul(c['confirmed_facts'])}</details>
<h4>Potential policy gaps (for expert review)</h4>{ul(c['potential_policy_gaps'])}
<h4>Relevant institutions</h4>{ul(c['relevant_institutions'])}
<h4>Open questions</h4>{ul(c['open_questions'])}
<p class="notice small"><b>Human review:</b> {e(c['human_review_required'])}</p>
</div>"""


def build(path: Path) -> str:
    entries = read_entries(path)
    problems = verify_chain(entries)
    start = next(x for x in entries if x["type"] == "run_started")
    stages = [x for x in entries if x["type"] == "stage"]
    end = next((x for x in entries if x["type"] == "run_completed"), None)
    nav = "".join(f"<a href='#{e(s['stage']['label'])}'>{e(s['stage']['label'])}</a>" for s in stages)
    chain = "".join(f"<tr><td>{x['seq']}</td><td>{e(x['type'])}{' ' + e(x['stage']['label']) if x['type'] == 'stage' else ''}</td>"
                    f"<td>{e(x['recorded_at'])}</td><td><code>{e(x['hash'])}</code></td></tr>" for x in entries)
    title = f"{start.get('scenario_id', 'Run')} audit report"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<style>{CSS}</style></head><body><main>
<nav class="small"><a href="#summary">Summary</a><a href="#timeline">Timeline</a>{nav}<a href="#chain">Integrity</a></nav>
{header(start, stages, end, problems)}
{summary(stages)}
{timeline(stages)}
{''.join(stage_section(s, i + 1) for i, s in enumerate(stages))}
<h2 id="chain">4. Audit-trail integrity</h2>
<p class="small muted">Each entry stores the SHA-256 of its own content and the hash of the entry before it.
Source file: <code>{e(path.name)}</code>. Re-check with <code>src.audit.trail.verify_chain</code>.</p>
<div class="wrap"><table><tr><th>#</th><th>Entry</th><th>Recorded</th><th>SHA-256</th></tr>{chain}</table></div>
<p class="notice small">Decision support only: legal interpretation, regulatory decisions and institutional
action remain with qualified people.</p>
</main></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render an audit-trail JSONL as a judge-readable HTML report.")
    ap.add_argument("trail", type=Path)
    ap.add_argument("-o", "--output", type=Path, help="default: <trail>.html next to the trail")
    args = ap.parse_args()
    out = args.output or args.trail.with_suffix(".html")
    out.write_text(build(args.trail), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
