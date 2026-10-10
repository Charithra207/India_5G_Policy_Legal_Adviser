# India 5G Policy & Legal Adviser — Project Report

ITU AI  Build-a-thon 5.0 · Policy & legal adviser track ·

## Executive summary

The India 5G Policy & Legal Adviser is decision support for 5G incidents in India. It follows an incident as it unfolds and tells an operator which Indian obligations apply, to whom and by when, with every statement quoted from an official source and checked against a separate one.

Seven specialist agents (Technical, Policy & Legal, Cybersecurity, Privacy, Critical Infrastructure, Standards, Policy Gap) each search their own knowledge base. A Verifier checks every claim against a separate Canonical KB. A Coordinator assembles one assessment per stage, and every step is written to a hash-chained audit trail that can be replayed and re-executed.

The same adviser is the policy (P) node of an ITU-T Y.3172 machine-learning pipeline running over a simulated 5G core. Beside it, a contained attack lab plays 13 attacks step by step, with humans approving every risky fix.

| Headline | Value |
| --- | --- |
| Specialist agents | 7 |
| Official sources ingested | 23, in 8 knowledge bases |
| Indexed documents for obligation checks | 284 (276 with text) |
| Retrieval test: right section in the top 5 | 12 of 12 queries (8 of 12 ranked first) |
| Verifier outcomes | VERIFIED, INCOMPLETE, UNSUPPORTED, CONFLICTING |
| Gap-register anchors verified word for word | 17 (5 pending, 2 listed) |
| Contained attacks | 13, in Basic, Intermediate and Advanced tiers |
| Automated tests | 497 passed, 39 skipped |

Everything runs locally and free of cost. An optional local language model (Ollama) can add reasoning, but its claims are kept only if they cite a retrieved passage.

## Problem and context

A 5G incident rarely arrives complete, and the law that applies changes as each piece arrives. A latency complaint can become a security event, then a hospital service carrying patient data, then a question of who must be told within hours.

The project's reference scenario (scenario 2, a private 5G slice serving a hospital) shows this in four stages:

| Stage | What is revealed | What changes legally |
| --- | --- | --- |
| T0 | Intermittent latency and session drops on the slice | A performance problem; no reporting duty yet |
| T1 | Unusual authentication and signalling attempts | A possible cyber incident: CERT-In and the Central Government must be told within 6 hours |
| T2 | The slice carries ICU patient-monitoring telemetry | Personal data (DPDP Act and Rules) and a possibly critical service (CTI Rules) |
| T3 | Management asks what is due, to whom, by when | One answer needed across four or more instruments |

The obligations sit in separate instruments with different clocks and recipients: the Telecommunications Act 2023 (section 22), the Telecom Cyber Security Rules 2024 (rule 7), the CERT-In Directions of 28 April 2022, the DPDP Act 2023 and DPDP Rules 2025, and the CTI Rules 2024. None refers to all the others.

The ITU AI for Good Sandbox Build-a-thon 5.0 asked the policy and legal adviser track for exactly this support, judged on knowledge-base quality, agent capability, gap identification (with global and neighbouring-region examples), auditability, and reflection of the ITU-T Y.3172 pipeline and the AI readiness framework.

## Objectives and scope

The goal is an adviser that is useful in the first hours of an incident and can be trusted because every step can be checked.

1. Follow an incident chunk by chunk and reassess at each stage, never answering once at the start.
2. Ground every legal statement in a quoted passage with document, section and page; never answer from model memory.
3. Verify each claim against a separate authoritative corpus and label what is not established.
4. Find links between legal domains and potential policy gaps, with global and neighbouring-region comparators.
5. Record everything so a run can be replayed, re-executed and audited.
6. Show the adviser working inside the ITU-T Y.3172 ML pipeline as its policy node.
7. Run locally, free of cost, on an ordinary laptop.

Out of scope by design: giving legal advice (the system is decision support and says so on every screen), acting on a live network (the 5G core is simulated), and declaring that Indian law is inadequate (gaps are always "potential gaps for expert review").

## System architecture

Each stage passes through the same chain: the Orchestrator picks agents from what the chunk reveals, the agents quote their own sources, a separate Verifier rates every claim, and the Coordinator assembles the assessment that is written to the audit trail.

&#91;embedded content: adviser architecture · one stage, from chunk to assessment\]

The chain is the same for every stage and every scenario. Only the facts released, and therefore the agents woken and the passages quoted, change. The pipeline is plain Python (`src/core/`, `src/agents/`, `src/pipeline.py`), and the demonstration UI is Streamlit (`src/ui/app.py`).

## The seven specialist agents

Each agent speaks only within its mandate and searches only its own knowledge base. International material is always labelled "reference only, not Indian law".

| Agent | Mandate | Main sources |
| --- | --- | --- |
| Technical | Classify the network event; affected components | 3GPP TS 23.501, TS 33.501 |
| Cybersecurity | Classify the security event; reporting duties | Telecom Cyber Security Rules 2024, CERT-In Directions 2022, NCSP 2013; NIST as reference |
| Standards | Standards in scope, as reference points | 3GPP, ETSI NFV-SEC, NIST CSF 2.0, NIST SP 800-61r3, ITU-T Y.3172 |
| Critical Infrastructure | Critical-service relevance; CTI duties | Telecommunications Act 2023 s.22, CTI Rules 2024 |
| Privacy | Personal-data exposure and DPDP duties | DPDP Act 2023, DPDP Rules 2025 |
| Policy & Legal | Applicable Indian law, authorisations, institutions | Telecommunications Act 2023, TRAI Act 1997, NDCP 2018, commencement notifications |
| Policy Gap | Potential gaps and comparators | NDCP 2018, NCSP 2013, TRAI AI recommendations, NITI Aayog strategy, ENISA |

**Each agent receives different information.** Beside the facts released to all, each stage releases some facts to one agent only, as in a real organisation. In scenario 2, only Cybersecurity sees the security team's ticket (authentication failures about 40 times the baseline). Only Privacy hears from the data-protection officer that the telemetry includes patient names. Each agent searches first for what it alone was told. These facts are recorded per agent in the audit trail.

**How an agent works.** It builds queries from the released facts and its mandate and retrieves passages from its knowledge base. It then quotes the most relevant passages (at most four, with duties carrying a time limit first, and never a title page). It states its own classification separately; that classification is checked like any other claim.

## Knowledge bases and retrieval

The adviser draws on 23 official sources in 8 knowledge bases: one per agent plus the Canonical KB used only for verification. A separate 284-document index serves word-for-word obligation checks.

**Sources.** A curated manifest (`knowledge_base/sources/manifest.json`) lists 25 documents; 23 are ingested. The IT (NCIIPC) Rules 2013 were unobtainable from official sites, and no international policy examples were specified in the brief. Each entry records authority, jurisdiction, region and role (Indian law, guidance, standard, global or regional example), dates, source URL and provenance. A source file is refused at build time unless its own text contains the title it claims, which guards against the wrong file.

**Ingestion.** `python -m src.rag.fetch_sources` downloads each file from its official URL and checks its SHA-256. `python -m src.rag.build` then extracts text with page provenance (PyMuPDF, python-docx), detects sections (Act sections, Rules, Directions, 3GPP clauses, pages), and splits it into passages. It embeds them with BAAI/bge-small-en-v1.5 on the CPU (fastembed) and stores one vector store per knowledge base. Every passage carries source, section, heading, page, URL, provenance, in-force status where known, and an amendment flag.

**The 284-document index.** `kb/index/` holds the team's wider corpus (TRAI consultations, spectrum and licensing papers, Acts and rules, 3GPP, threat frameworks, data protection) in nine FAISS category indexes. It is committed to the repository and hash-checked, so nobody rebuilds it. The attack lab's Policy panel and the gap register use it to check obligations word for word.

**Retrieval quality**, measured on 12 labelled queries (`knowledge_base/retrieval_quality.md`):

| Measure | Result |
| --- | --- |
| Expected section in the top 5 | 12 / 12 |
| Expected section ranked first | 8 / 12 |
| Mean source precision at 5 | 0.78 |
| Results only from the agent's own KB | 12 / 12 |
| Metadata complete on every result | 12 / 12 |

## Verification and coordination

No agent marks its own work: a separate Verifier checks every claim against the Canonical KB and gives it one of four outcomes.

| Outcome | Meaning | Where the Coordinator puts it |
| --- | --- | --- |
| VERIFIED | The authoritative text supports it, the provision is in force, and its amendments were checked | Evidence-backed conclusions |
| INCOMPLETE | The text supports it, but in-force or amendment status is not confirmed | Uncertain conclusions |
| UNSUPPORTED | No authoritative passage states it | Uncertain conclusions, marked preliminary |
| CONFLICTING | Two sources disagree | Conflicting findings: Finding A and Finding B, both with evidence, for a human to decide |

Support is judged deterministically: the quoted words must be found in the authoritative passage (term coverage of at least 0.6), so the same input always gives the same verdict. In the recorded full run, 50 claims were INCOMPLETE and 10 UNSUPPORTED. The INCOMPLETE ratings are honest, not a fault: the quotes are exact, but amendment histories have not been fully checked. A labelled fixture run shows the same Verifier returning VERIFIED when amendment status is recorded as complete.

**Cross-domain links** are established from the cited text, not from two agents merely being active:

- **Instrument basis.** One cited instrument names another; for example, the Telecom Cyber Security Rules are made under section 22 of the Telecommunications Act, which the Critical Infrastructure agent cites.
- **Shared provision.** Two agents rely on the same section.
- **Parallel reporting.** The same incident triggers duties to different recipients, such as the six-hour report under rule 7 and the DPDP breach intimation.

**The Coordinator** keeps the categories of the brief's Table A1 strictly apart: confirmed facts, evidence-backed conclusions, uncertain conclusions, conflicts, potential policy gaps, cross-domain relationships, institutions, changes since the last stage, and open questions. Conclusions from agents not run again are carried forward and tagged. Conclusions an agent no longer makes are reported as superseded. Each institution is listed once.

## Scenario workflow and outputs

In scenario 2, the Orchestrator's agent selection matched the official stage table at all four stages, and the assessment rises as the facts arrive.

1. **T0, latency.** Technical runs alone and quotes 3GPP TS 23.501 on packet-delay and QoS monitoring, labelled reference only. Its guess that the UPF is involved is UNSUPPORTED.
2. **T1, suspicious authentication.** Cybersecurity and Standards join. The incident is reassessed as a possible security event, and rule 7 of the Telecom Cyber Security Rules and CERT-In Direction (ii) are quoted: report within 6 hours.
3. **T2, ICU telemetry.** Critical Infrastructure, Privacy and Policy & Legal join. Personal-data exposure is recorded as suspected, not confirmed. Cross-domain links appear, including the parallel reporting duties.
4. **T3, the reporting question.** Policy Gap joins, examines every one of the 886 Indian legal and policy passages in the Canonical KB, and raises three potential gaps.

**Every stage page ends with a plain-language close**, built only from the recorded stage entries, so a live run and its replay read the same:

- a **Summary** of the stages so far;
- a table of the **notifications the retrieved Indian provisions may require**: recipient, time limit, source and the condition under which each applies;
- a **Conclusion** with the open questions and the human-review reminder.

At T3 the notifications table reads:

| Recipient | Time limit | Source | Applies |
| --- | --- | --- | --- |
| CERT-In | within 6 hours | CERT-In Directions (28 April 2022), Direction (ii) | cyber incident of a type in Annexure I |
| Central Government | within 6 hours, then 24 hours | Telecom Cyber Security Rules 2024, rule 7 | security incident affecting the network or service |
| Each affected Data Principal | without delay | DPDP Rules 2025, rule 7 | only if a personal-data breach is confirmed |
| Data Protection Board | without delay | DPDP Rules 2025, rule 7 | only if a personal-data breach is confirmed |

The Live run page in the Streamlit UI releases one chunk at a time. The command line does the same: `python -m src.scenario.run --stages 4`. Both write an audit trail to `outputs/audit/`.

## Policy-gap analysis

The Policy Gap agent raised three potential gaps in the live run, and a domain-framed register goes deeper with five themes and comparators from other regions.

**Raised live at T3:**

- **Emerging technology not explicitly addressed.** None of the 886 Indian legal and policy passages examined mentions network slicing; it appears only in TRAI recommendations, which are not law.
- **Overlapping requirements.** CERT-In Direction (ii) and DPDP Rules rule 7 both carry reporting duties for the same incident, and neither refers to the other.
- **Missing institutional clarity.** NCSP 2013 addresses NCIIPC and NDCP 2018 addresses CERT-In, but no examined passage addresses both, so who leads is unclear.

The agent's comparators are labelled by region: a neighbouring-region example (South Asia) is listed first when retrieved, then global examples. It states when no neighbouring example was found.

**The gap register** (`python -m src.gap.register` → `knowledge_base/gap_register.md`) checks every Indian anchor word for word against the corpus, with its page:

| Theme | India | Comparator (reference only) |
| --- | --- | --- |
| G1 Reporting clocks | 6 hours: Telecom Cyber Security Rules rule 7(1)(a), CERT-In (ii), CTI Rules rule 7(1)(j); DPDP Rules: details to the Board within 72 hours | EU GDPR (72 hours), EU NIS2; Sri Lanka listed |
| G2 Log retention | CERT-In Direction (iv): 180 days, kept in India; DPDP Rules: logs of processing kept at least one year | EU GDPR storage limitation |
| G3 Critical telecom infrastructure vs NCIIPC | Telecommunications Act s.22(3); CTI Rules definition; TRAI consultation | EU NIS2, ENISA; Bangladesh listed |
| G4 Network slicing | Act refers to networks "or part thereof", without naming slices | ENISA names slice-as-a-service providers |
| G5 Human oversight of AI in network operations | NITI Aayog strategy; TRAI AI recommendation for a sector AI authority | EU AI Act, NIST AI RMF |

Anchor status today: 17 verified, 5 pending (the document is not yet in the corpus), 2 listed for comparison. Pending anchors become verified when their documents are added and the knowledge bases rebuilt (`knowledge_base/ADDING_SOURCES.md`).

The wording is deliberate: always "potential gap for expert review", never a finding that Indian law fails. Each theme ends with questions for experts.

## ITU-T Y.3172 ML pipeline

The project implements the ITU-T Y.3172 pipeline end to end over a simulated 5G core, with the legal adviser as the policy (P) node that stands between detection and any action (`src/y3172/`).

&#91;embedded content: ITU-T Y.3172 pipeline · intent, MLFO, sandbox, SRC to SINK\]

The MLFO turns the intent into a running chain and keeps it within the intent's targets; every detection passes the P node before the distributor acts.

- **ML Intent.** A YAML file (`intents/`) states the goal, for example "detect and contain signalling storms on the AMF", with the minimum macro-F1, the maximum inference time, the detection deadline and the P-node mode. Three intents ship with the project.
- **MLFO.** The ML function orchestrator reads the intent and instantiates the chain: sources (SRC: AMF, gNB, UPF, OAM), collector (C), preprocessor (PP), model (M), policy (P), distributor (D) and sinks (SINK). It also assigns each node a level (access network, core network or management).
- **ML sandbox.** Candidate models (an Isolation Forest + Random Forest model and a threshold baseline) are trained on simulated data and evaluated against the intent's targets. The best eligible one is selected, and every playbook's effect is tested before live use.
- **Live run and monitoring.** The selected model is deployed to the simulated live network and scored tick by tick. When its rolling score falls below the intent's minimum, the MLFO recalibrates and re-selects.
- **P node.** Each detection goes to the adviser. In **blocking** mode the fix is held until a person approves it, having seen the Indian obligations; in **advisory** mode it is advice only. The specialist agents run on the incident, and logs are preserved before any state-changing step.
- **D node and sinks.** Evidence is preserved with hashes, the remediation runs (if approved), draft regulatory notices with verified deadlines are written, and unresolved incidents are escalated. Notices stay drafts until a person approves them.

In the example run `amf_signalling_storm`, 1 of 1 injected attacks was detected within the deadline. The model was re-selected once after a load drift, 3 incidents were dispatched, and 12 draft notices were written. 2 remediations went to false alarms under changed load, and in blocking mode each was first held for human approval. The UI's Y.3172 page replays any run step by step from its audit trail and ends with a Summary and Conclusion.

The adviser's own document pipeline maps to Y.3172 mostly by analogy; `knowledge_base/y3172_pipeline_traceability.json` records which parts correspond directly and which are simulated.

## Contained incident-response lab

The lab injects one of 13 attacks into a simulated 5G core and shows the response step by step, with a human gate before every escalation. Nothing touches a real network: the core is Python data, the attacks edit that data, and no socket is opened.

**The simulated core** (`sim/`) models gNB, AMF, SMF, UPF, UDM, AUSF, NEF, NRF and OAM, plus base stations, three slices (eMBB, a hospital URLLC slice with an allow-list, mMTC), subscriber profiles, PDU sessions and per-device traffic. It writes logs in Open5GS layout.

**The attack catalog** (`catalog/attacks.yaml`) holds 13 attacks. Each has ENISA and 3GPP references, Indian obligations (an exact phrase and its document), resolution checks and Basic, Intermediate and Advanced playbooks. Examples include a signalling storm, a fake base station, subscriber-profile tampering, a rogue network function with data theft, GTP-U spoofing and an IoT botnet in the mMTC slice.

**How a run unfolds**, in the CLI (`python run.py --attack 2 --step`) and on the web page (`streamlit run ir/ui.py`, with Next step, Show all and Auto-play):

1. The network before the attack: every function green.
2. The attack unfolds: each log line and alert it causes, in the order written.
3. Detection: the health of each network function.
4. The Policy panel: the Indian obligations that now apply, each phrase checked word for word in its cited document with file and page.
5. Basic tier: diagnostics run freely; only fixes marked auto-safe may change state.
6. A gate before Intermediate, and again before Advanced: the agent runs it, the operator runs the printed commands, or the response stops. Every state-changing step the agent proposes needs a yes.
7. A Summary and a Conclusion, with the full report (timeline, what fixed it or the escalation, policy recap) saved.

"Resolved" is decided by the catalog's checks against the simulator, never by the agent's own claim. The response agent can be the deterministic offline playbook, Claude, or a local Ollama model. Some attacks carry traps, such as quarantining healthy meters in the botnet attack counting as a failure. An optional Windows Sandbox launcher isolates the lab further.

## Auditability and AI governance

Every run can be replayed, re-executed and inspected entry by entry, and any tampering is detected.

- **Hash-chained audit trail.** Each run is an append-only JSONL file in `outputs/audit/`. Each entry carries the hash of the one before, so an edited, removed or reordered entry breaks the chain. The header records the scenario, the knowledge-base build hash, the code commit and the reasoning model, if any.
- **What each stage records.** For each agent: the facts it could see (including those released to it alone), its queries, every retrieved passage with source, section, page, URL and provenance, each claim with its citations, the Verifier's outcome and rationale, and its uncertainty and missing information. For the stage: the Orchestrator's selection against the official table, cross-domain links, conflicts and the full Coordinator assessment.
- **Replay and re-execution.** `python -m src.scenario.run --replay <run> --reexecute --explain` checks the chain and walks the decision path stage by stage. It re-runs the recorded chunks and compares agents, passages, claims, outcomes and the assessment.
- **Protected core.** `CORE_FREEZE.json` fingerprints the orchestrator, agents, Verifier, Coordinator, data contracts and scenarios. A test fails on any unrecorded change, and every recorded change carries its reason.

**Optional reasoning model, on a short leash.** By default the agents are deterministic and fully replayable. With `--llm ollama` (a free local model) or `--llm anthropic`, each agent can reason over its own retrieved passages and facts. Only claims that cite a retrieved passage are kept; they are labelled "LLM-assisted" and verified like any other claim. The prompt hash, the model's response, and the accepted and rejected claims are written to the audit trail. If the model is unreachable or not installed, the run continues without it and says why.

**Human oversight** is built in rather than added on: a human-review notice on every screen and report, P-node holds and tier gates that wait for a person, notices that stay drafts, conflicts left unresolved for people, and gaps phrased for expert review. The repository maps the project to the ITU AI readiness framework (`knowledge_base/itu_ai_readiness_mapping.json`).

## Evaluation and testing

The automated suite passes 497 tests with 39 skipped. The skipped tests need the built vector stores and run on a machine where the knowledge bases are built.

| Area | What is checked |
| --- | --- |
| Pipeline and agents | Agent selection per stage, mandates, quotes only from retrieved passages, view facts searched first, off-topic and title-page passages not quoted |
| Verifier | VERIFIED, INCOMPLETE, UNSUPPORTED and CONFLICTING paths, using labelled fixtures |
| Cross-domain and Coordinator | Instrument-basis, shared-provision and parallel-reporting links; categories kept apart; carried-forward and superseded claims; one entry per institution |
| Audit and replay | Hash-chain tamper detection; exact re-execution of offline runs; the decision path |
| Optional LLM | Fake Ollama server: claims without a citation rejected, the model's trace recorded, a missing model explained |
| Gap analysis | Regions and roles, comparator labels, anchor statuses, the committed register |
| Y.3172 | Intent validation, model selection, sandbox, P-node modes, sinks, notices |
| Attack lab | All 13 attacks resolve in their expected tier, refused and declined steps, gates, step-by-step CLI and web page |
| UI | Every page renders, using Streamlit's AppTest |
| Core freeze | Fingerprints of the protected core match the recorded change log |

Beyond the tests, `python -m src.rag.evidence_audit` re-checks every citation of the recorded run against the stores. The retrieval-quality report gives the 12/12 and 8/12 results above. `python -m src.audit.evaluation_report` labels each area Working, Partially working or Not yet implemented from a real test run.

End-to-end runs exit cleanly for both scenarios, the conflict demo, replay with re-execution, all attacks, the Y.3172 intents and the gap register.

## Alignment with the judging criteria

Each criterion maps to something a judge can see running, not only to a design document.

| Criterion | Evidence in the project | Where to see it |
| --- | --- | --- |
| Knowledge-base quality | 23 official sources in 8 KBs with section, page, URL and provenance per passage; title check at build; 284-document index; 12/12 test queries find the right section in the top 5 | `knowledge_base/ingestion_manifest.json`, `retrieval_quality.md` |
| Agent capability | 7 agents with separate mandates and information; progressive reassessment over 4 stages; evidence-based cross-domain links; optional local LLM reasoning under verification | Live run page, T0 to T3 |
| Gap identification, with global and neighbouring-region examples | 3 potential gaps raised live; a 5-theme register with Indian anchors verified word for word and EU and South Asian comparators labelled by region | Live run at T3; Gap register page |
| Auditability | Hash-chained trail, replay, re-execution, decision path per stage, logged model reasoning, protected core | Replay page; `outputs/audit/` |
| Y.3172 pipeline and AI readiness | Intent, MLFO, ML sandbox, SRC to SINK over the simulated core; the adviser as the P node with human holds; readiness mapping and traceability files | Y.3172 pipeline page; `knowledge_base/` |

## Limitations

The system labels what it has not established rather than hiding it, and these limits apply today:

- **No real-source claim is VERIFIED yet.** In-force status is recorded where a commencement notification is held, but amendment histories have not been fully checked, so quoted claims read INCOMPLETE.
- **Simulated network.** The 5G core, attacks and Y.3172 run are a contained simulation. Reference points and levels are logical, in one process, not service-based interfaces on a live network.
- **Deterministic support check.** Support is judged by term coverage, not semantic understanding, which favours exact quotes over paraphrase.
- **Optional LLM not evaluated for quality.** The model's claims are constrained and verified, but the quality of its reasoning has not been measured.
- **Sequential agents.** Agents run one after another, not in parallel.

## How to run it

The project runs on a laptop with Python 3.12 or 3.13, about 10 GB of free disk and 8 GB of RAM. It needs internet only for the first downloads.

1. Clone the repository and create a virtual environment: `python -m venv .venv`, then activate it.
2. Install the dependencies: `pip install -r requirements.txt`.
3. Download the official sources: `python -m src.rag.fetch_sources`. A file that fails can be saved by hand into `knowledge_base/sources/raw/` under its manifest file name.
4. Build and regenerate: `python -m src.rag.build`, then `src.rag.foundation`, `src.rag.evidence_audit`, `src.gap.register` and `src.rag.retrieval_demo`, each with `python -m`.
5. Check: `python -m pytest tests -q`.
6. Open the demonstration UI: `streamlit run src/ui/app.py`. It has four pages: Live run, Replay, Y.3172 pipeline and Gap register.
7. Open the attack lab: `streamlit run ir/ui.py`, or `python run.py --attack 2 --step` in a terminal.
8. Run a Y.3172 intent: `python run.py --intent intents/amf_signalling_storm.yaml --auto`.
9. Optional local reasoning model: install Ollama, run `ollama pull qwen2.5:7b-instruct`, then choose `ollama` as the agents' reasoning model in the Live run sidebar.

New documents are added through the manifest, with region and role, then the knowledge bases are rebuilt (`knowledge_base/ADDING_SOURCES.md`).

## Next steps and conclusion

The adviser follows a 5G incident as it unfolds, quotes Indian law exactly, verifies every claim against a separate source, and finds cross-domain links and potential policy gaps. It works as the policy node of an ITU-T Y.3172 pipeline and can be fully audited and replayed. The next steps turn its honest gaps into verified results:

1. Record amendment checks for the instruments the scenarios rely on (CERT-In Directions, DPDP Act and Rules, CTI Rules, Telecommunications Act), so their claims can reach VERIFIED.
2. Add the pending global documents (GDPR, NIS2, EU AI Act) and more neighbouring-country instruments, then rebuild so the gap register's pending anchors are checked.
3. Measure the optional LLM's reasoning against labelled expert answers before relying on it.
4. Pilot with an operator's security team on recorded incidents, and add their incident types to the catalog.
5. Run the pipeline in the ITU AI for Good Sandbox when access is available.

Throughout, the system stays decision support: legal interpretation, regulatory decisions and any action on a network remain with qualified people.
