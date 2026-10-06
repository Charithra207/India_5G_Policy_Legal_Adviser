"""
Retrieval quality evaluation (Day-2 Task 5)
===========================================
    python -m src.rag.retrieval_quality

For representative queries of each of the seven agents, checks against
labelled expectations:

  correct source    the expected document is among the agent's results
  correct section   the expected section is ranked in the top 1 / top 5
  relevant passage  the expected section's passage contains the expected phrase
  metadata          every result carries source, authority, jurisdiction,
                    document type, section, URL, chunk ID and provenance
  isolation         every result comes from the agent's own KB documents
  source precision  share of the top 5 results from the expected document

Labels: each query names the provision whose own printed heading or text
addresses the topic (e.g. "Rule 7. Reporting of security incidents").  The
label is checked to exist in the corpus before the query runs, so a label
cannot point at a provision that was not ingested.  Misses are reported, not
hidden: the numbers describe this corpus and this embedding model only.

Writes knowledge_base/retrieval_quality.md and .json.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from src.core.models import AgentID
from src.rag.manifest import KB_ROOT

TOP_K = 5
REQUIRED_METADATA = ("source_title", "authority", "jurisdiction", "document_type",
                     "section", "url", "chunk_id", "provenance_note")


@dataclass(frozen=True)
class Probe:
    agent: AgentID
    query: str
    doc_id: str          # expected document
    section: str         # expected section label
    phrase: str          # text that makes the expected passage relevant


PROBES = [
    Probe(AgentID.TECHNICAL, "network slice selection and isolation in the 5G core",
          "3gpp_ts_23501", "Clause 5.15.1", "Network Slice"),
    Probe(AgentID.TECHNICAL, "QoS monitoring of packet delay between UE and UPF",
          "3gpp_ts_23501", "Clause 5.45.2", "QoS Monitoring for packet delay"),
    Probe(AgentID.CYBERSECURITY, "telecommunication entity reporting of a security incident within six hours",
          "telecom_cyber_security_rules_2024", "Rule 7", "Reporting of security incidents"),
    Probe(AgentID.CYBERSECURITY, "mandatory reporting of cyber incidents to CERT-In",
          "certin_directions_2022", "Direction (ii)", "report cyber incidents"),
    Probe(AgentID.PRIVACY, "intimation of personal data breach to the Data Protection Board",
          "dpdp_rules_2025", "Rule 7", "Intimation of personal data breach"),
    Probe(AgentID.PRIVACY, "reasonable security safeguards to protect personal data",
          "dpdp_rules_2025", "Rule 6", "Reasonable security safeguards"),
    Probe(AgentID.CRITICAL_INFRA, "rules for measures to protect cyber security of telecommunication networks",
          "telecom_act_2023", "Section 22", "cyber security of telecommunication networks"),
    Probe(AgentID.POLICY_LEGAL, "authorisation required to provide telecommunication services",
          "telecom_act_2023", "Section 3", "shall obtain an authorisation"),
    Probe(AgentID.POLICY_LEGAL, "functions and powers of the Telecom Regulatory Authority of India",
          "trai_act_1997", "Section 11", "Functions of Authority"),
    Probe(AgentID.STANDARDS, "machine learning sandbox for training and testing before deployment in a live network",
          "itu_t_y3172", "Clause 3.2", "machine learning sandbox"),
    Probe(AgentID.STANDARDS, "incident response recommendations for cybersecurity risk management",
          "nist_sp_800_61r3", "Section 1", "incident response"),
    Probe(AgentID.POLICY_GAP, "protection of critical information infrastructure as a national objective",
          "ncsp_2013", "Part III item 5", "critical information infrastructure"),
]


def _check_label(canonical_rows: dict, probe: Probe) -> None:
    rows = canonical_rows.get((probe.doc_id, probe.section), [])
    if not any(probe.phrase.lower() in " ".join(r["excerpt"].split()).lower() for r in rows):
        raise ValueError(f"label not in corpus: {probe.doc_id} {probe.section} {probe.phrase!r}")


def evaluate(registry=None) -> dict:
    from src.rag.registry import build_registry
    registry = registry or build_registry()
    chunks = {}
    for kb in (registry.canonical_kb, *registry.agent_kbs.values()):
        for r in kb.store.chunks:
            chunks.setdefault((r["doc_id"], r["section"]), []).append(r)

    results = []
    for probe in PROBES:
        _check_label(chunks, probe)
        kb = registry.agent_kbs[probe.agent]
        allowed = {r["doc_id"] for r in kb.store.chunks}
        hits = kb.retrieve(probe.query, top_k=TOP_K)
        ranked = [(h.chunk_id.split(":")[0], h.section) for h in hits]
        target = (probe.doc_id, probe.section)
        rank = ranked.index(target) + 1 if target in ranked else None
        relevant = next((h for h in hits if (h.chunk_id.split(":")[0], h.section) == target
                         and probe.phrase.lower() in " ".join(h.excerpt.split()).lower()), None)
        results.append({
            "agent": probe.agent.value,
            "query": probe.query,
            "expected": {"doc_id": probe.doc_id, "section": probe.section, "phrase": probe.phrase},
            "rank_of_expected_section": rank,
            "hit_at_1": rank == 1,
            "hit_at_5": rank is not None,
            "expected_source_in_results": probe.doc_id in {d for d, _ in ranked},
            "relevant_passage_retrieved": relevant is not None,
            "source_precision_at_5": round(sum(d == probe.doc_id for d, _ in ranked) / max(len(ranked), 1), 2),
            "metadata_complete": all(all(getattr(h, f) for f in REQUIRED_METADATA) for h in hits),
            "isolated_to_agent_kb": all(d in allowed for d, _ in ranked),
            "results": [{"rank": i, "source_title": h.source_title, "section": h.section,
                         "page": h.page, "chunk_id": h.chunk_id,
                         "cosine_similarity": h.relevance_score}
                        for i, h in enumerate(hits, 1)],
        })

    n = len(results)
    summary = {
        "queries": n,
        "agents": sorted({r["agent"] for r in results}),
        "hit_at_1": sum(r["hit_at_1"] for r in results),
        "hit_at_5": sum(r["hit_at_5"] for r in results),
        "relevant_passage_retrieved": sum(r["relevant_passage_retrieved"] for r in results),
        "expected_source_in_results": sum(r["expected_source_in_results"] for r in results),
        "mean_source_precision_at_5": round(sum(r["source_precision_at_5"] for r in results) / n, 2),
        "metadata_complete": sum(r["metadata_complete"] for r in results),
        "isolated_to_agent_kb": sum(r["isolated_to_agent_kb"] for r in results),
        "misses": [f"{r['agent']}: {r['query']}" for r in results if not r["hit_at_5"]],
    }
    return {
        "_about": "Retrieval quality against labelled expectations. Generated by "
                  "`python -m src.rag.retrieval_quality`. Labels are checked to exist in the "
                  "corpus; misses are reported.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_k": TOP_K,
        "required_metadata": list(REQUIRED_METADATA),
        "summary": summary,
        "results": results,
    }


def write(report: dict) -> None:
    (KB_ROOT / "retrieval_quality.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    s = report["summary"]
    lines = [
        "# Retrieval quality", "",
        f"Generated {report['generated_at']} by `python -m src.rag.retrieval_quality`.", "",
        "Each query is labelled with the provision whose own heading or text addresses the "
        "topic; the label is checked to exist in the corpus. Results describe this corpus and "
        "embedding model only.", "",
        "| Measure | Result |", "|---|---|",
        f"| Expected section ranked first (hit@1) | {s['hit_at_1']} / {s['queries']} |",
        f"| Expected section in top {report['top_k']} (hit@{report['top_k']}) | {s['hit_at_5']} / {s['queries']} |",
        f"| Relevant passage retrieved | {s['relevant_passage_retrieved']} / {s['queries']} |",
        f"| Expected source among results | {s['expected_source_in_results']} / {s['queries']} |",
        f"| Mean source precision@{report['top_k']} | {s['mean_source_precision_at_5']} |",
        f"| Metadata complete on every result | {s['metadata_complete']} / {s['queries']} |",
        f"| Results only from the agent's own KB | {s['isolated_to_agent_kb']} / {s['queries']} |",
        "",
        "| Agent | Query | Expected | Rank | Top result |", "|---|---|---|---|---|",
    ]
    for r in report["results"]:
        top = r["results"][0] if r["results"] else None
        lines.append(
            f"| {r['agent']} | {r['query']} | {r['expected']['doc_id']}, {r['expected']['section']} | "
            f"{r['rank_of_expected_section'] or 'not in top ' + str(report['top_k'])} | "
            f"{top['source_title'] + ', ' + top['section'] if top else '—'} |")
    if s["misses"]:
        lines += ["", "**Misses:** " + "; ".join(s["misses"])]
    (KB_ROOT / "retrieval_quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = evaluate()
    write(report)
    s = report["summary"]
    print(f"hit@1 {s['hit_at_1']}/{s['queries']}  hit@5 {s['hit_at_5']}/{s['queries']}  "
          f"isolation {s['isolated_to_agent_kb']}/{s['queries']}  "
          f"metadata {s['metadata_complete']}/{s['queries']}")
    for m in s["misses"]:
        print("  miss:", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
