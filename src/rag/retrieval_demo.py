"""
Retrieval test: one demonstrated retrieval per specialist agent.

    python -m src.rag.retrieval_demo

Runs Scenario 2 (DOCX §2.5) through the full pipeline with the live
knowledge bases and records, for each of the seven agents at the chunk
where it first activates:

    Agent → Query → Retrieved passage → Source → Section → Why relevant
          → Structured agent output (claims, citations, verifier outcomes,
            uncertainty)

"Why relevant" is computed, not written by hand: the agent query that
returned the passage, its cosine similarity, and the query terms that
occur in the passage.  It does not assert that the passage supports any
claim — the Verifier outcome column says that.

Writes knowledge_base/retrieval_tests.json and knowledge_base/retrieval_tests.md.
"""

from __future__ import annotations

import json
import logging
import warnings
from datetime import datetime, timezone

from src.core.models import AgentID
from src.knowledge_base.text_match import content_terms
from src.pipeline import Pipeline
from src.rag.manifest import KB_ROOT
from src.rag.registry import KB_NAMES, build_registry
from scenarios.scenario2_healthcare_5g import get_chunks

AGENT_ORDER = [AgentID.TECHNICAL, AgentID.POLICY_LEGAL, AgentID.CYBERSECURITY,
               AgentID.PRIVACY, AgentID.CRITICAL_INFRA, AgentID.STANDARDS,
               AgentID.POLICY_GAP]


def _attribute(agent, chunk, state, evidence_item):
    """Which of the agent's queries returned this passage, and at what score."""
    for query in agent._build_queries(chunk, state):
        for hit in agent.kb.retrieve(query, top_k=5):
            if hit.chunk_id == evidence_item.chunk_id:
                return query, hit.relevance_score
    return None, evidence_item.relevance_score


def run() -> dict:
    registry = build_registry()
    pipeline = Pipeline(registry)
    orchestrator = pipeline.orchestrator
    first_seen: dict[AgentID, dict] = {}

    for chunk in get_chunks():
        state_before = dict(orchestrator._incident_state)
        state_before["verified_findings"] = list(state_before["verified_findings"])
        record = pipeline.run_chunk(chunk)
        outcomes = {(v.agent_id, v.claim): v for v in record.verifier_result.verified_claims}
        for finding in record.agent_findings:
            if finding.agent_id in first_seen:
                continue
            agent = orchestrator.get_agent(finding.agent_id)
            first_seen[finding.agent_id] = {
                "chunk": chunk, "finding": finding, "agent": agent,
                "state": orchestrator._incident_state, "outcomes": outcomes,
            }

    results = []
    for agent_id in AGENT_ORDER:
        seen = first_seen.get(agent_id)
        if seen is None:
            results.append({"agent": agent_id.value, "activated": False})
            continue
        finding, agent, chunk = seen["finding"], seen["agent"], seen["chunk"]
        real = [e for e in finding.evidence if e.authority != "STUB"]
        retrievals = []
        for item in real[:3]:
            query, score = _attribute(agent, chunk, seen["state"], item)
            shared = sorted(content_terms(query or "") & content_terms(item.excerpt))
            retrievals.append({
                "query": query,
                "source": item.source_title,
                "authority": item.authority,
                "jurisdiction": item.jurisdiction,
                "document_type": item.document_type,
                "section": item.section,
                "section_title": item.section_title,
                "page": item.page,
                "date_issued": item.date_issued,
                "effective": "not verified" if item.effective is None else item.effective,
                "amendment_checked": item.amendment_checked,
                "url": item.url,
                "chunk_id": item.chunk_id,
                "passage": item.excerpt,
                "why_relevant": {
                    "returned_by_query": query,
                    "cosine_similarity": score,
                    "query_terms_in_passage": shared,
                    "kb": KB_NAMES[agent_id],
                },
            })
        claims = []
        for claim in finding.claims:
            v = seen["outcomes"].get((agent_id, claim))
            claims.append({
                "claim": claim,
                "cites": [f"{e.source_title}, {e.section}" for e in finding.claim_citations.get(claim, [])],
                "verifier_outcome": v.outcome.value if v else None,
                "verifier_rationale": v.rationale if v else None,
            })
        results.append({
            "agent": agent_id.value,
            "activated": True,
            "chunk_id": chunk.chunk_id,
            "chunk": chunk.description,
            "kb": KB_NAMES[agent_id],
            "kb_documents": getattr(agent.kb, "documents", []),
            "passages_retrieved": len(real),
            "retrievals": retrievals,
            "structured_output": {
                "summary": finding.summary,
                "claims": claims,
                "obligations": finding.obligations,
                "uncertainty_notes": finding.uncertainty_notes,
                "missing_facts": finding.missing_facts,
            },
            "success": bool(real),
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "Scenario 2 (DOCX §2.5), chunks T0–T3, full pipeline with live KBs",
        "agents_with_successful_retrieval": sum(r.get("success", False) for r in results),
        "results": results,
    }
    (KB_ROOT / "retrieval_tests.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (KB_ROOT / "retrieval_tests.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def _clip(text: str, n: int = 600) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


def to_markdown(report: dict) -> str:
    out = [
        "# Retrieval tests — one per specialist agent",
        "",
        f"Generated {report['generated_at']} by `python -m src.rag.retrieval_demo`.",
        f"{report['scenario']}. Agents with a successful retrieval: "
        f"**{report['agents_with_successful_retrieval']} / 7**.",
        "",
        "*Why relevant* is computed (query, cosine similarity, shared terms); whether "
        "a passage supports a claim is decided only by the Verifier outcome.",
        "",
    ]
    for r in report["results"]:
        out.append(f"## {r['agent']}")
        if not r["activated"]:
            out += ["Not activated in this scenario.", ""]
            continue
        out += [
            f"- **Chunk:** {r['chunk_id']} — {r['chunk']}",
            f"- **KB:** {r['kb']} ({', '.join(r['kb_documents'])})",
            f"- **Passages retrieved:** {r['passages_retrieved']}",
            "",
        ]
        for i, x in enumerate(r["retrievals"], 1):
            w = x["why_relevant"]
            out += [
                f"### Retrieval {i}",
                f"- **Query:** {x['query']}",
                f"- **Source:** {x['source']} ({x['authority']}; {x['jurisdiction']}; {x['document_type']})",
                f"- **Section:** {x['section']}" + (f" — {x['section_title']}" if x["section_title"] else "")
                + (f" (p. {x['page']})" if x["page"] else ""),
                f"- **Date issued:** {x['date_issued'] or 'not stated in source'} · "
                f"**In force:** {x['effective']} · **Amendments checked:** {x['amendment_checked']}",
                f"- **Why relevant:** returned by the query above with cosine similarity "
                f"{w['cosine_similarity']:.3f}; query terms in passage: "
                f"{', '.join(w['query_terms_in_passage']) or 'none (semantic match only)'}",
                f"- **Chunk ID:** `{x['chunk_id']}`",
                "",
                f"> {_clip(x['passage'])}",
                "",
            ]
        s = r["structured_output"]
        out += ["### Structured agent output", f"- **Summary:** {s['summary']}", "- **Claims:**"]
        for c in s["claims"]:
            cites = f" — cites {'; '.join(c['cites'])}" if c["cites"] else " — agent's reading of the facts"
            out.append(f"  - [{c['verifier_outcome']}] {_clip(c['claim'], 300)}{cites}")
        if s["uncertainty_notes"]:
            out.append("- **Uncertainty:** " + " / ".join(s["uncertainty_notes"]))
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    logging.basicConfig(level=logging.WARNING)
    rep = run()
    for r in rep["results"]:
        top = r.get("retrievals", [{}])[0] if r.get("retrievals") else {}
        print(f"{r['agent']:<24} {'OK ' if r.get('success') else 'NO '} "
              f"{r.get('passages_retrieved', 0):>2} passages | top: "
              f"{top.get('source', '-')[:40]} — {top.get('section', '-')}")
    print(f"\n{rep['agents_with_successful_retrieval']} / 7 agents retrieved evidence. "
          "Wrote knowledge_base/retrieval_tests.md and .json")
