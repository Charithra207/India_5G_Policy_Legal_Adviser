# India 5G Policy & Legal Adviser
### An Agentic AI System for Evidence-Backed Analysis of Evolving 5G Incidents
**ITU AI Readiness Build-a-thon — India · Policy & Legal Adviser role · Evaluation environment: ITU AI for Good Sandbox**

> Synthetic incident scenarios and public/official documents only — hackathon use. Decision support, not legal advice.

---

## Executive Summary

**The problem.** A 5G incident rarely arrives complete. A latency complaint becomes a security event, then a hospital service carrying patient data, then a question of who must be told and within how many hours. Each step pulls in different Indian law, different institutions and different standards. A single answer given at the start cannot follow that, and ordinary document search finds provisions but does not connect them across domains or check them.

**The solution.** The adviser follows one incident chunk by chunk. For each chunk a swarm orchestrator activates only the specialists the released facts justify — seven in all (Technical, Policy & Legal, Cybersecurity, Privacy, Critical Infrastructure, Standards, Policy Gap). Each agent searches only its own knowledge base and states what a law says only by quoting the passage it retrieved, with source, section and page. A Verifier then checks every claim against a separate Canonical KB, and a Coordinator assembles the result into five strictly separated categories: confirmed facts, evidence-backed conclusions, uncertain conclusions, conflicting findings, and potential policy gaps.

**What makes it defensible.** The analysis is evidence-first, not generated. No generative model is in the path: agents quote retrieved passages and the Coordinator organises claims the Verifier has checked against the authoritative text — by text, never by model confidence or a similarity score. Remove the language model from the adviser and the evidence, the citations and the verdicts still stand. Every claim is traceable to a passage; the whole run is written to an append-only, hash-chained audit trail and can be replayed.

**Two authorities, never conflated.** Indian law is Indian law; international standards (3GPP, ETSI, NIST, ITU-T) are always labelled reference only, never Indian law. A claim is called VERIFIED only when the canonical text supports it, it is in force, and no amendment is recorded — so because amendment histories are not yet shown to be complete, the live system reports supported claims as INCOMPLETE, not VERIFIED.

**Contained attack sandbox.** Beside the adviser is an incident-response lab: an attack is injected into a simulated 5G core (Python state, no real network), and two panels appear — a Policy panel (the Indian obligations that apply, with file and page) and a Technical panel (network-function health and a Basic → Intermediate → Advanced playbook). An agent works the tiers automatically where it is safe to, and a human gate stands before every escalation.

**Team**

- Harshini K — team lead
- Arshitha S
- Charithra H S
- Mentor: Rajat Duggal · Organisation: Nokia

**Submission**

- Repository — https://github.com/Charithra207/India_5G_Policy_Legal_Adviser
- Knowledge base & provenance — `knowledge_base/sources/manifest.json`, `knowledge_base/ingestion_manifest.json`
- Recorded demo run — `outputs/audit/day2_scenario2_full_T0_T3.jsonl`
- Demo video — ⟨paste link⟩
- Live system — ⟨paste link, if deployed⟩
- Contact — itubuildathon@gmail.com

---

## Problem, and Why Existing Tools Do Not Solve It

One 5G incident can simultaneously engage the Telecommunications Act 2023, the Telecom Cyber Security Rules 2024, the CERT-In Directions 2022, the DPDP Act 2023 and its 2025 Rules, and the Critical Telecommunication Infrastructure Rules 2024 — each with its own trigger, its own institution and its own reporting clock. The duties are not in one place, they interact (one instrument is made under another), and some point to the same incident with different deadlines and different recipients.

A keyword search or a general chatbot will surface provisions, but it will not tell you which ones are actually engaged by this incident as facts arrive; connect a cybersecurity reporting duty to the Act it is made under; flag that two duties report the same event to two bodies in parallel; or stop itself from stating law it cannot cite. A chatbot that paraphrases a statute from memory is the failure mode a regulator cannot accept. This system is built so that every legal statement is a quotation with a checkable source, and anything unsupported is labelled as such rather than asserted.

---

## Architecture — ITU-T Y.3172

The system is organised on the ITU-T Y.3172 ML pipeline (SRC → C → PP → M → P → D → SINK). The repository contains a machine-checked traceability map (`src/rag/foundation.py` §4.3, `y3172_traceability`) that quotes each Y.3172 node definition and names the component that performs it; it is labelled architectural correspondence only — formal Y.3172 compliance is not claimed.

| Y.3172 node | Role in the standard | In this system |
| :--- | :--- | :--- |
| SRC | Source of data | Official source documents, listed with provenance (authority, URL, SHA-256) in the source manifest |
| C | Collection | Text extraction with page numbers (PyMuPDF; python-docx for 3GPP); a file is refused if its own title text is absent |
| PP | Preprocessing | Running headers/footers removed, sections detected from headings or bookmarks, chunked within one section |
| M | Model | A sentence-embedding retriever (BAAI/bge-small-en-v1.5, CPU) per agent. No generative model — agents quote what they retrieve |
| P | Policy | The Verifier: checks each claim against the Canonical KB and assigns VERIFIED / INCOMPLETE / UNSUPPORTED / CONFLICT; adds cross-domain links |
| D | Distribution | The Coordinator places each verified claim in one of five categories and writes the hash-chained audit entry |
| SINK | Application | The Streamlit UI (live run + replay) and the exported assessment the operator reads |
| Sandbox | Isolated test domain | The incident-response lab — a simulated 5G core where attacks are injected and effects observed without touching a live network |

### The Verifier — the defensible core

1. **Support decided by text, not by the model.** A claim is supported only if the authoritative passage in the Canonical KB actually says so — not because retrieval similarity was high, not because an agent was confident, not because a disclaimer was attached. The default judge (`LexicalSupportJudge`) is deterministic, so a run replays identically.
2. **Refusal to overclaim.** Four outcomes are possible — VERIFIED / INCOMPLETE / UNSUPPORTED / CONFLICT — and nothing on the live corpus is marked VERIFIED, because in-force status and amendment history are not yet shown to be complete. Supported-but-unconfirmed is INCOMPLETE, stated plainly.
3. **Cross-domain links only from evidence.** Two findings are linked only where the text establishes it — a shared provision (both cite the same section), an instrument basis (one instrument's own text names the Act the other cites), or parallel reporting (two legal duties to report the same incident to different bodies) — never because two agents happened to be active.

### Sandbox and data protection

Every incident scenario is synthetic; every source document is public or official, fetched from its own URL and checked by SHA-256. The attack lab is contained by construction: the "network" is Python dictionaries in `sim/engine.py`, the "attacks" in `sim/inject.py` edit those dictionaries and contain no exploit code, and nothing opens a socket or touches a real host. The only network use anywhere is the optional Claude API call in the lab agent — remove the key and a deterministic offline playbook takes over. Retrieval embeddings run on CPU, locally.

---

## Policy Gaps and ITU AI Readiness 2.0

The Policy Gap agent runs only after earlier chunks have produced verified findings, and it draws comparisons against international examples (ENISA 5G Security Controls Matrix; ENISA 5G Cybersecurity Standards). It never declares a policy failure; it raises a potential gap for a qualified human. On the recorded Scenario 2 run it surfaced 4 potential gaps at T3, each tied to the findings that motivated it. Themes it examines include overlapping reporting duties to multiple bodies with different clocks, institutional clarity across DoT / CERT-In / the Data Protection Board, and coverage for emerging technology where an Indian instrument is absent and only an international comparator exists.

Mapped to the ITU AI Ready — Standardized Readiness Framework, Report 2.0 (January 2026):

| Dimension | Why it fits | Evidence in the system |
| :--- | :--- | :--- |
| 3 · Cross-Domain Correlation Analysis | The system's purpose is correlating one incident across technical, legal, cyber, privacy, CII and standards domains | Seven specialist domains; evidence-based cross-domain links on the live run — instrument basis ×12, shared provision ×7, parallel reporting ×4 (`src/core/cross_domain.py`) |
| 10 · AI & Policies | "Ability to use AI for policy experimentation and extrapolation" — a policy adviser with gap identification and a policy-mapping attack lab | Five-category assessment; Policy Gap agent; the lab's Policy panel citing obligations by document and page |
| 8 · Collaboration with AI | High-stakes legal and remediation decisions stay with people | "Human review required" banner on every assessment; Basic→Intermediate→Advanced human gates in the lab; decision-support framing throughout |

---

## Evaluation and References

Two staged scenarios, facts released progressively so later facts are invisible to earlier agent runs (challenge brief §2.5):

| # | Scenario | File |
| :--- | :--- | :--- |
| 1 | 5G network-slicing incident | `scenarios/scenario1_slicing_incident.py` |
| 2 | Healthcare 5G private-network incident (T0–T3) | `scenarios/scenario2_healthcare_5g.py` |

**Scenario 2, recorded run** (`outputs/audit/day2_scenario2_full_T0_T3.jsonl`):

| Chunk | Agents activated (match the brief's stage table) | What appears |
| :--- | :--- | :--- |
| T0 latency & session drops | Technical | 3GPP TS 23.501 quoted, labelled reference-only |
| T1 suspicious auth & signalling | + Cybersecurity + Standards | Reclassified as a possible security event; TCS Rules Rule 7 + CERT-In Direction (ii), both six-hour duties |
| T2 hospital service & possible patient data | Critical Infrastructure + Privacy + Policy & Legal | Cross-domain links appear; exposure kept suspected, not confirmed |
| T3 reporting, escalation, policy uncertainty | Policy & Legal + Cybersecurity + Privacy + Critical Infrastructure + Policy Gap | Parallel reporting duties; 4 potential gaps |

Run totals: Verifier outcomes INCOMPLETE 50, UNSUPPORTED 10; cross-domain links instrument basis 12, parallel reporting 4, shared provision 7; conflicts 0 — no two ingested provisions disagree. The conflict path is demonstrated on labelled synthetic passages (`--conflict-demo`, 2 conflict records).

**Quality and integrity:**

- Test suite: 392 passed, 0 failed, 0 skipped.
- Retrieval quality (12 labelled queries across all 7 agents): expected section ranked first 8/12, in top-5 12/12, relevant passage retrieved 12/12, expected source present 12/12, mean source precision@5 0.78, results only from the agent's own KB 12/12.
- Evidence audit (`python -m src.rag.evidence_audit`): traced 60 claims, 53 cited passages, 13 in-force statuses and 2 amendment notes — 0 problems — and it is tested against seven planted fabrications (altered quote, missing "not Indian law" label, a standard called Indian law, a fabricated gap, an uncited requirement, a cross-KB passage, a false VERIFIED), catching each.

**Knowledge bases:**

| KB | Passages |
| :--- | :--- |
| Technical (3GPP TS 23.501, TS 33.501) | 3,739 |
| Policy & Legal (Telecom Act 2023 + notifications, TRAI Act, NDCP-2018, NCSP-2013, CTI Rules, NITI Aayog) | 603 |
| Cybersecurity (TCS Rules 2024 + 2025 Amendment, CERT-In Directions; references 3GPP/ETSI/NIST) | 1,680 |
| Privacy (DPDP Act 2023, DPDP Rules 2025) | 159 |
| Critical Infrastructure (Telecom Act 2023, CTI Rules 2024) | 126 |
| Standards (ITU-T Y.3172, 3GPP, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3) | 4,259 |
| Policy Gap (TRAI AI & Big Data, NCSP, NDCP, NITI Aayog, Right of Way Rules; ENISA EU examples) | 1,029 |
| Canonical (verification corpus, all 23 sources) | 5,710 |

**The incident-response lab.** A simulated 5G core — gNB, AMF, SMF, UPF, UDM, AUSF, NEF, NRF, OAM, plus base stations, slices (eMBB, a hospital URLLC slice with an allow-list, mMTC), subscriber profiles, PDU sessions and flows — all deterministic Python state. The attack catalog (`catalog/attacks.yaml`) holds 13 attacks, each with ENISA / 3GPP references, the Indian obligations it triggers (verbatim phrase + document), resolution checks, and Basic / Intermediate / Advanced playbooks. "Resolved" is decided by the catalog's `resolved_when` checks against the simulator, never by the agent's own claim. The retrieval index behind the Policy panel is built once from 276 unique PDFs across 9 categories (bge-small, fastembed, CPU, FAISS) and committed, so nobody retrains.

**Limitations (stated to avoid overclaiming):**

- Nothing on the live corpus is VERIFIED — only INCOMPLETE — because amendment histories are not shown to be complete. VERIFIED and CONFLICT are demonstrated on labelled fixtures.
- IT (NCIIPC) Rules 2013 were not obtained, so NCIIPC provisions cannot be quoted; CII designation is stated as unconfirmed.
- No generative synthesis in the adviser (by design); the challenge's generative-AI perspective is not implemented there.
- Agents run sequentially; the parallel runner is a stub.
- The ITU AI for Good Sandbox stage was not available in the build environment; recorded-run replay is the local substitute.

**Primary sources (Indian, ingested).** Telecommunications Act 2023 (+ commencement notifications S.O. 2408(E), S.O. 2623(E)); TRAI Act 1997; Telecom Cyber Security Rules 2024 (official DoT copy) + Amendment Rules 2025; CERT-In Directions 2022; DPDP Act 2023 + DPDP Rules 2025; Critical Telecommunication Infrastructure Rules 2024; NDCP-2018; NCSP-2013; Right of Way Rules 2024; NITI Aayog National Strategy for AI; TRAI AI & Big Data Recommendations 2023. International (reference only): ITU-T Y.3172; 3GPP TS 23.501 / TS 33.501; ETSI GR NFV-SEC 003; NIST CSF 2.0; NIST SP 800-61r3; ENISA 5G documents. All 23 ingested sources form the Canonical KB (5,710 passages); each source's official URL serves a file byte-identical to the one ingested.

---

Decision support only. It does not replace legal counsel, regulators, or government decision-makers. Synthetic scenarios; public/official sources; hackathon use.
