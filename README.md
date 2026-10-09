# India 5G Policy & Legal Adviser

**An Agentic AI System for Evidence-Backed Analysis of Evolving 5G Incidents**

Team: Harshini K (lead), Arshitha S, Charithra H S | Mentor: Rajat Duggal | Org: Nokia  
Build-a-thon role: Policy and Legal Adviser | Target environment: ITU AI for Good Sandbox  
(access was not available to the team; the knowledge bases are built and every run is executed locally)

---

## Purpose

Understanding an evolving 5G incident requires simultaneous analysis across
telecommunications regulation, cybersecurity, personal data protection,
critical infrastructure, and international standards.  A single incident
can trigger obligations under multiple Indian instruments, involve several
institutions, and expose gaps in the current framework — often all at once.

This system provides structured, evidence-linked decision support for such
incidents.  It does not replace legal counsel, regulators, or government
decision-makers.

---

## Architecture

```
Scenario Chunk
      |
      v
Swarm Orchestrator  --- selects relevant agents for this stage ---+
      |                                                            |
      |    Pass 1: specialist agents                               |
      |    +-----------+  +-------------+  +--------------+       |
      |    | Technical |  | Policy &    |  | Cybersecurity|       |
      |    |   Agent   |  | Legal Agent |  |    Agent     |       |
      |    |   (RAG)   |  |   (RAG)     |  |    (RAG)     |       |
      |    +-----------+  +-------------+  +--------------+       |
      |    +-----------+  +-------------+  +--------------+       |
      |    |  Privacy  |  | Critical    |  |  Standards   |       |
      |    |   Agent   |  | Infra Agent |  |    Agent     |       |
      |    |   (RAG)   |  |   (RAG)     |  |    (RAG)     |       |
      |    +-----------+  +-------------+  +--------------+       |
      |                                                            |
      |<-- Pass-1 AgentFindings <----------------------------------+
      |
      v
  Verifier (Pass 1)  <-- Canonical KB (independent verification corpus)
      |
      | verified findings -> incident_state
      |
      v
  Pass 2: Policy Gap Agent (T3 only, receives verified findings)
      |
      v
  Verifier (Pass 2)
      |
      v
  Coordinator
      |
      v
  CoordinatorAssessment
  +-- Confirmed facts
  +-- Evidence-backed conclusions  (VERIFIED)
  +-- Uncertain conclusions        (INCOMPLETE / UNSUPPORTED)
  +-- Conflicting findings         (CONFLICT)
  +-- Potential policy gaps
      |
      v
  AuditRecord  ->  outputs/  (text + JSON)
```

---

## Specialist agents

| Agent | Mandate | Indian instruments |
|---|---|---|
| Technical | 5G radio, core, slicing, network functions | 3GPP TS 23.501, TS 33.501 (reference) |
| Policy & Legal | Indian telecom law and regulation | Telecom Act 2023, TRAI Act 1997, NDCP-2018 |
| Cybersecurity | Cyber incident classification and response | Telecom Cyber Security Rules 2024, CERT-In Directions 2022, NCSP-2013 |
| Privacy | Personal data and data-protection implications | DPDP Act 2023, DPDP Rules 2025 |
| Critical Infrastructure | CII designation and additional obligations | IT (NCIIPC) Rules 2013, Telecom Act 2023 |
| Standards | International technical/security comparison | ITU-T Y.3172, 3GPP TS 23.501/33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61 Rev.3 |
| Policy Gap | Potential gaps, ambiguities, overlaps | All above + international policy examples |

Each agent speaks only within its defined mandate.  International standards
are always labelled as reference points, never as Indian law.

---

## Swarm Orchestrator

The swarm has no fixed sequence (DOCX §3.2).  For each chunk the
Orchestrator activates only the specialists justified by the information
released in that chunk (§2.5), read against the incident state (§3.3).
The chunk's position in the scenario is never used.

| Information released in the chunk | Agents activated |
|---|---|
| Performance symptom or security indicator | Technical |
| Security indicator | + Cybersecurity + Standards |
| Critical service | Critical Infrastructure + Policy & Legal |
| Personal data involved | Privacy + Policy & Legal |
| Possible data exposure | + Cybersecurity |
| Reporting / escalation question | Policy & Legal, plus each domain already flagged in the incident state (Cybersecurity, Privacy, Critical Infrastructure) |
| Policy-gap question | Policy Gap (only after earlier chunks have verified findings) |

These rules reproduce both staged scenarios in the DOCX:

| Chunk | Scenario 1 (§2.4, Annex-1 A.4) | Scenario 2 (§2.5) |
|---|---|---|
| 1 / T0 | Technical | Technical |
| 2 / T1 | Technical + Cybersecurity + Standards | Technical + Cybersecurity + Standards |
| 3 / T2 | Critical Infrastructure + Policy & Legal | Critical Infrastructure + Privacy + Policy & Legal |
| 4 / T3 | Privacy + Policy & Legal + Cybersecurity | Policy & Legal + Cybersecurity + Privacy + Critical Infrastructure + Policy Gap |

Accumulated incident context (whether a cybersecurity event has been
suspected, whether CII is flagged, etc.) is preserved across chunks for
agent reasoning.  It re-activates earlier domains only when the current
chunk asks a reporting/escalation question that spans the whole incident.

---

## Knowledge bases

Each specialist agent has its own domain KB and retrieval mechanism.
A separate Canonical KB is used exclusively by the Verifier for independent
claim verification (DOCX §7.2).

| KB | Ingested sources | Passages |
|---|---|---|
| Technical KB | 3GPP TS 23.501, TS 33.501 | 3,739 |
| Policy & Legal KB | Telecommunications Act 2023 + commencement notifications S.O. 2408(E), S.O. 2623(E); TRAI Act 1997; NDCP-2018; NCSP-2013; CTI Rules 2024; NITI Aayog National Strategy for AI | 603 |
| Cybersecurity KB | Telecom Cyber Security Rules 2024 (official DoT copy) + Amendment Rules 2025, CERT-In Directions 2022, NCSP-2013, NDCP-2018; reference: 3GPP TS 33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 | 1,680 |
| Privacy KB | DPDP Act 2023, DPDP Rules 2025 | 159 |
| Critical Infra KB | Telecommunications Act 2023, Critical Telecommunication Infrastructure Rules 2024 (**NCIIPC Rules 2013 not ingested**) | 126 |
| Standards KB | ITU-T Y.3172, 3GPP TS 23.501/33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 | 4,259 |
| Policy Gap KB | TRAI AI & Big Data Recommendations 2023, NCSP-2013, NDCP-2018, NITI Aayog National Strategy for AI, Right of Way Rules 2024; EU policy examples: ENISA 5G Security Controls Matrix, ENISA 5G Cybersecurity Standards | 1,029 |
| Canonical KB | All 23 ingested sources (separate verification corpus) | 5,710 |

Sources, provenance and what was not ingested: `knowledge_base/sources/manifest.json`
(curated) and `knowledge_base/ingestion_manifest.json` (generated). Details:
`INTEGRATION_RAG_KB.md`.

In-force status and amendment history have not been checked for any source,
so a claim fully supported by its cited text is **INCOMPLETE, not VERIFIED**.

---

## Verification

Agents state what a law or standard says only by quoting a passage
retrieved from their own KB, and record it as the claim's citation
(`AgentFinding.claim_citations`).  With no passages, an agent names the
instruments in its mandate and states that their applicability is not
assessed — it never supplies their content from memory.

The Verifier checks every claim against the Canonical KB: does the cited
source/section exist there, and does the authoritative text support the
claim?  Support is decided by text, never by retrieval similarity, model
confidence, or a disclaimer label.

| Outcome | Meaning |
|---|---|
| VERIFIED | The canonical text of the cited section supports the claim; in force; no amendment recorded |
| INCOMPLETE | Supported, but an amendment applies — or the claim matches its cited passage while the Canonical KB is not yet populated |
| UNSUPPORTED | Cited section not in the Canonical KB, text does not support the claim, passage not in force, or no evidence |
| INCOMPLETE (live corpus) | Supported by the cited text, but in-force status / amendments not checked — currently every quoted provision |
| CONFLICT | Another finding or source contradicts the claim; both sides kept with their evidence |

The support check is pluggable (`Verifier(..., support_judge=...)`); the
default `LexicalSupportJudge` is deterministic so runs can be replayed.

**Cross-domain verification** (`src/core/cross_domain.py`) links findings of
different domains only where the evidence establishes it — never because
two agents are active:

| Relationship | Established when | Live example (Scenario 2) |
|---|---|---|
| shared provision | both domains cite the same source and section | Critical Infrastructure and Policy & Legal both cite Telecommunications Act, 2023, Section 22 |
| instrument basis | an instrument cited in one domain names, in its own Canonical KB text, an Act cited in the other | Telecom Cyber Security Rules (Cybersecurity) are made "in exercise of the powers conferred by … section 22 … of the Telecommunications Act, 2023" (Critical Infrastructure / Policy & Legal) |
| parallel reporting | both domains cite Indian legal duties to report the same incident, to different recipients | TCS Rules Rule 7 (Central Government, six hours) and CERT-In Direction (ii) (CERT-In, 6 hours) vs DPDP Rules Rule 7 (Data Principal and Board, without delay) |

Findings of agents that ran in an earlier chunk take part (a T2 privacy
finding links to a T1 cybersecurity finding).

**Conflicts** are recorded as `ConflictRecord`s: Finding A and Finding B,
each with its evidence, the basis, the status ("unresolved; requires
qualified human review") and the Coordinator's treatment.  Rules:

- *reporting deadline* — two cited duties to report the same incident to
  the same recipient within different time limits;
- *CII obligations* — CII relevance found, but Policy & Legal examined its
  sources and found no corresponding obligation;
- *exposure classification* — exposure confirmed by Privacy, but
  Cybersecurity does not treat the incident as a security event.

The ingested corpus contains no disagreeing provisions, so the live run has
no conflict — correctly.  The conflict path is demonstrated with labelled
synthetic passages (`src/scenario/conflict_fixture.py`,
`python -m src.scenario.run --conflict-demo`, recorded in
`outputs/audit/day2_conflict_demo_FIXTURE.jsonl`).

---

## Coordinator

The Coordinator combines verified multi-agent findings into one unified
assessment with five strictly separated categories (DOCX Annex-1 Table A1):

1. **Confirmed facts** — raw incident facts from the scenario
2. **Evidence-backed conclusions** — VERIFIED by Canonical KB
3. **Uncertain conclusions** — INCOMPLETE or UNSUPPORTED
4. **Conflicting findings** — contradictions between agents or sources
5. **Potential policy gaps** — areas of unclear or absent coverage, for expert review

**Progressive reassessment.** Each chunk's assessment covers the whole
incident so far:

- confirmed facts accumulate across chunks;
- conclusions of agents not active in this chunk are carried forward under
  their last outcome, tagged `[carried forward from <chunk> — not re-examined]`;
- `changes_from_prior` is computed by comparison: newly active / inactive
  agents, incident flags that became true in this chunk, newly cited
  provisions, re-rated claims, superseded claims, new cross-domain links,
  conflicts and policy gaps.

**Conflicts** are shown with both findings and their evidence; neither is
adopted, and both are withheld from the other categories.

**Uncertainty.** UNSUPPORTED claims are labelled "insufficient evidence;
preliminary only"; `open_questions` lists the evidence the agents and the
Verifier found missing, and states explicitly when no conclusion is
evidence-backed.

Policy gaps use non-conclusive language ("potential gap", "regulatory
ambiguity").  No conclusion of policy failure is drawn.

---

## Audit and replay

Every pipeline run produces an `AuditRecord` containing:
- Timestamp and chunk ID
- Active agent IDs
- All agent findings with claims, evidence references, and uncertainty notes
- Verifier outcomes per claim
- Cross-domain links and conflicts
- Coordinator assessment (all five categories)

The scenario engine (`src/scenario/`) writes each run to an append-only,
hash-chained audit trail, `outputs/audit/<run_id>.jsonl` (`src/audit/`), with
the DOCX §7.6 fields per agent: visible input, retrieval queries, retrieved
passages with source/section/page, decision summary, citations, verifier
outcome, cross-domain flags and the Coordinator decision.  A run can be
replayed stage by stage (UI Replay mode, or `--replay`), its hash chain
checked, and its recorded chunk sequence re-executed and compared with the
record.

---

## Scenario workflow

The system is evaluated against staged scenario chunks in which facts are
released progressively so that later facts are not visible to earlier agent
runs (DOCX §2.5).

Two scenarios are provided:
- `scenarios/scenario1_slicing_incident.py` — 5G network-slicing incident (DOCX §2.4)
- `scenarios/scenario2_healthcare_5g.py` — Healthcare 5G private network incident (DOCX §2.5)

---

## How to run

```powershell
pip install -r requirements.txt

# Download the source documents from their official URLs (checked by SHA-256)
python -m src.rag.fetch_sources

# Build the knowledge bases from knowledge_base/sources (~10-12 min on CPU)
python -m src.rag.build

# One retrieval test per agent -> knowledge_base/retrieval_tests.md
python -m src.rag.retrieval_demo

# Run the test suite
python -m pytest tests -v

# Demonstration UI: live run (chunk by chunk) and replay
streamlit run src/ui/app.py

# Command line: release T0 and T1, record the audit trail; then replay it
python -m src.scenario.run --stages 2
python -m src.scenario.run --replay outputs/audit/<run_id>.jsonl --reexecute
python -m src.scenario.run --conflict-demo       # conflict handling (labelled fixtures)
python -m src.scenario.run --replay outputs/audit/<run_id>.jsonl --explain  # decision path per stage
python -m src.audit.evaluation_report            # evaluation summary from a real test run

# Run Scenario 2 (T0-T3) with the live knowledge bases
python -c "
import sys; sys.path.insert(0, '.')
from src.pipeline import Pipeline
from src.rag.registry import build_registry
from src.utils.output_formatter import format_audit_record
from scenarios.scenario2_healthcare_5g import get_chunks
pipeline = Pipeline(build_registry())
for chunk in get_chunks():
    record = pipeline.run_chunk(chunk)
    print(format_audit_record(record))
"
```

---

## Incident-response lab (contained 5G attack simulation)

A self-contained module beside the adviser (it does not touch `src/`).
An attack is injected into a **simulated** 5G core. Two panels then show
what applies: a **Policy panel** listing the Indian obligations with file
and page, and a **Technical panel** showing NF health, alerts and the
playbook. An agent works through tiered playbooks, and a human gate stands
before every escalation.

> **Contained by design.** The "network" is Python dicts in `sim/engine.py`;
> the "attacks" in `sim/inject.py` edit those dicts and contain no exploit code.
> Nothing opens a socket, scans or touches any real host. The only network use
> is the optional Claude API call (and `pip`/Python download in the sandbox).

| Part | Path | What it does |
|---|---|---|
| Index | `kb/build_index.py`, `kb/retriever.py`, `kb/index/` | 276 unique PDFs from the team folder; text by pymupdf, Tesseract OCR for scanned pages; ~450-token chunks; bge-small-en-v1.5 (fastembed, CPU); one FAISS index per category: `law_and_acts`, `cyber_incident_rules`, `gpp_security`, `gpp_architecture`, `threat_frameworks`, `data_protection`, `spectrum_licensing_row`, `trai_consultations`, `other_rules`. `manifest.json` has each document's category plus the hashes of the index files. |
| Simulator | `sim/engine.py`, `sim/inject.py`, `sim/cli.py` | gNB, AMF, SMF, UPF, UDM, AUSF, NEF, NRF, OAM, plus connected base stations, slices (embb, urllc-hospital with an allow-list, mmtc), subscriber profiles with a known-good snapshot, PDU sessions, UPF flows and per-device mMTC traffic. Deterministic. State goes to `<work>/state.json`; logs go to `<work>/logs/*.log` in Open5GS layout. |
| Catalog | `catalog/attacks.yaml` | 13 attacks, each with ENISA / 3GPP references, Indian obligations (verbatim phrase + document), resolution checks and Basic / Intermediate / Advanced playbooks. Editable; validated on load. |
| Engine | `ir/engine.py`, `ir/llm.py`, `ir/policy.py`, `ir/report.py` | Tier state machine and gates; Claude tool use (`LLM_PROVIDER=anthropic`) or the deterministic offline playbook |
| CLI / UI | `run.py`, `ir/ui.py` | CLI is the source of truth; one-file Streamlit page |
| Sandbox | `sandbox/` | Windows Sandbox config and setup |

**Train once, nobody retrains.** The index is built a single time and
committed in `kb/index/` together with its manifest. Users only load it, and
`kb.retriever.verify()` checks the files against the hashes in the manifest.

### Run it (host)

```bash
pip install -r requirements.txt
copy .env.example .env            # optional: add ANTHROPIC_API_KEY for the Claude agent

python run.py --list
python run.py --attack signalling_storm_amf                 # interactive gates and y/n
python run.py --attack nf_host_ransomware --provider offline
python run.py --attack core_ddos_upf --auto                 # non-interactive demo
streamlit run ir/ui.py                                      # web UI

python -m kb.retriever "report a security incident within six hours" --categories cyber_incident_rules
python -m sim.inject --attack rogue_base_station            # just inject; then:
python -m sim.cli list_neighbors                            # operator commands (key=value args)
python -m pytest tests/test_ir_lab.py -q
```

How a run goes:

1. The simulation is reset and the attack injected; both panels are printed.
2. **Basic**: the agent runs the diagnostics and applies only the fixes
   marked `auto_safe` (safe and idempotent), checking each one afterwards.
3. If the incident is not resolved, a gate appears:
   *"Basic steps did not resolve it. Intermediate tier?"*
   `[1] Agent runs it` `[2] I'll run it` `[3] Stop`.
   - In agent mode, every state-changing step is printed and needs `y/n`.
   - In manual mode, the commands (`python -m sim.cli …`) are printed; you
     run them, paste the output, and the agent interprets it.
4. The same gate appears before **Advanced**.
5. A final report (timeline, what fixed it or the escalation, and a policy
   recap) is written to `<work>/reports/`.

"Resolved" is decided by the catalog's `resolved_when` checks against the
simulator, never by the agent's own claim.

The six attacks from the team's attack sheet resolve in the tier that
matches their difficulty there:

| Attack sheet | id | Difficulty | Resolves in |
|---|---|---|---|
| 1 Signalling storm | `signalling_storm_amf` | easy | Basic |
| 2 Fake base station | `rogue_base_station` | medium | Intermediate |
| 3 Profile tampering / slice breach | `subscriber_profile_tampering` | difficult | Advanced |
| 4 Rogue NF + data theft | `supply_chain_rogue_nf` | advanced | Advanced |
| 5 GTP-U spoofing | `gtpu_spoofing_upf` | medium | Intermediate |
| 6 IoT botnet in the mMTC slice | `iot_botnet_mmtc` | medium-advanced | Advanced |

The other seven resolve as follows. `core_ddos_upf` resolves in Basic.
`subscriber_cred_compromise` and `nf_host_ransomware` need Advanced. The
rest (`sba_api_abuse_nef`, `subscriber_data_exfiltration`,
`exposed_mgmt_interface`, `n2_n3_mitm`) resolve in Intermediate.

Some attacks carry built-in traps:
- In profile tampering, Basic changes nothing, because the edit could be an
  honest mistake.
- In the rogue NF attack, the agent first asks the operator whether to
  preserve evidence or kill the component. Isolating before capturing loses
  the evidence.
- In the botnet attack, quarantining healthy meters counts as a failure.
- The fake-cell field-team step is a recorded hand-off, because physical
  removal happens in the real world.

**Policy panel caveat.** Before an obligation is shown with its file and
page, its phrase is searched for word for word in the cited document. If the
phrase isn't found, the panel says so instead. The DPDP Act s.8(6) and DPDP
Rules r.7 breach duties are labelled as commencing 18 months after 13 Nov 2025
(G.S.R. 843(E)). The panel is decision support for a training lab, not legal
advice.

### Run it in Windows Sandbox

> Windows Sandbox is Microsoft's local isolation feature. It is not the ITU AI
> for Good Sandbox, and not the ML sandbox of ITU-T Y.3172.

```powershell
powershell -ExecutionPolicy Bypass -File sandbox\launch.ps1              # downloads Python + packages inside
powershell -ExecutionPolicy Bypass -File sandbox\launch.ps1 -HostPython  # reuse the host's Python (read-only)
powershell -ExecutionPolicy Bypass -File sandbox\launch.ps1 -Offline     # no network at all (offline agent)
```

- The sandbox is **ephemeral**. Everything inside it is discarded when it
  closes, except `sandbox\work\` (sim state, logs, reports), the only
  writable mapping.
- The repository, including the committed **`kb\index\`**, is mounted from
  the host **read-only**. The index is loaded, never rebuilt, and its hashes
  are checked at start-up.
- Embeddings run on the **CPU** (fastembed ONNX). There is no GPU, Docker or
  WSL inside. The host's model cache is copied in, so nothing is downloaded.
- Network is needed only for the **Claude API**, plus downloading Python and
  packages unless `-HostPython` is used. With `-Offline`, the deterministic
  playbook provider runs.
- `sandbox\5g-sandbox.wsb` is a template, because Windows Sandbox needs
  absolute paths. `launch.ps1` fills them in and writes
  `sandbox\5g-sandbox.local.wsb`, which is git-ignored.

### Rebuild the index (maintainers only, once)

```bash
# needs the team source folder ("knowledge base/" or data/knowledge_base/, git-ignored) and Tesseract
python -m kb.build_index            # ~10.4M tokens, 21,779 chunks; CPU, a few hours
```

---

## ITU-T Y.3172 ML pipeline (`src/y3172/`)

The adviser becomes the **policy (P) node** of an ITU-T Y.3172 machine-learning
pipeline that watches the contained simulated 5G core (`sim/`). An **ML Intent**
says what the operator wants; the **MLFO** builds the pipeline from it, trains
and selects a model in an **ML sandbox**, deploys it to a separate "live"
simulation, and keeps checking it:

```
                      ML Intent (intents/*.yaml)
                               │
   ┌──────────────────── MLFO (src/y3172/mlfo.py) ─────────────────────┐
   │ instantiate · sandbox train/evaluate/select · validate · deploy · │
   │ monitor · re-calibrate and re-select                              │
   └───────┬───────────────────────────────────────────────┬──────────┘
           │ (ref. points 6, 1-2)                          │ (ref. points 5, 3)
   ML sandbox: simulated underlay networks          ML pipeline on the live (simulated) network
   (sim/datagen.py) → labelled telemetry             SRC → C → PP → M → P → D → SINKs
                                                     NFs   collector  model  │   │   ├─ evidence (hashed)
                                                     (read-only           policy &  ├─ remediation (ir/engine.py,
                                                      diagnostics)        legal     │   human gates)
                                                                          adviser   ├─ regulatory notices
                                                                                    └─ escalation to a human
```

| Y.3172 component | Here |
|---|---|
| ML Intent (cl. 7.4) | `intents/*.yaml`, validated by `src/y3172/intent.py` (sources and their levels, target incidents, candidate models and selection rule, P-node mode, SINKs, time constraints, monitoring) |
| SRC / C / PP (cl. 8.1) | Simulated NFs; the collector only calls read-only diagnostics; the preprocessor builds a fixed-length vector and its change since the last poll |
| M (cl. 8.1) | `threshold_centroid` (z-score baseline) and `iforest_rf` (IsolationForest + RandomForest); each prediction carries the signals that deviate from normal and the catalog playbook |
| P (cl. 8.1 NOTE 5) | `policy_node.py`: unknown / low-confidence / out-of-intent detections go to a human; the attack's Indian obligations are checked word for word in their sources; the specialist-agent swarm assesses the detection; **blocking** holds remediation for a human, **advisory** proceeds with the obligations attached |
| D and SINKs (cl. 8.1) | Evidence preserved and hashed before any change; remediation through the incident-response engine and its gates; draft notices with deadlines (DoT 6 h / 24 h, CERT-In 6 h, CTI 6 h from occurrence, DPDP without delay / 72 h — marked *not yet in force* before 13 May 2027); escalation |
| MLFO (cl. 8.1, 8.2) | Placement on UE/AN/CN/management levels, model selection (MNG-001), monitoring and re-selection (MNG-003/004), every decision in a hash-chained audit trail |
| ML sandbox (cl. 3.2.6, 8.2) | Background load, benign look-alikes (flash crowd, billing batch, maintenance window), attack intensity and post-remediation states; each playbook's effect evaluated in a sandbox simulation before live use |

```bash
pip install -r requirements.txt
python run.py --intent intents/amf_signalling_storm.yaml            # interactive: you approve the P-node hold
python run.py --intent intents/amf_signalling_storm.yaml --auto     # approve everything (demo)
python run.py --intent intents/hospital_slice_protection.yaml --auto   # advisory mode
python run.py --intent intents/core_security_full.yaml --auto       # all 13 incident types
python -m pytest tests/test_y3172.py -q
```

Each run writes `outputs/y3172/<run id>/`: `report.md` (summary, pipeline,
sandbox selection, sandbox validation, live timeline, incidents with their
obligations and SINK results, monitoring), `report.json`, the hash-chained
audit trail `<run id>.jsonl`, `notices/`, `evidence/`, `escalations/`.

Recorded example runs (`outputs/y3172/examples/`, each with its report, audit trail, notices, escalations and evidence):

| run | P node | sandbox: playbooks validated | attacks detected within 1 tick | live tick accuracy | false-alarm ticks | remediations on a wrong classification | re-selections | draft notices | escalations |
|---|---|---|---|---|---|---|---|---|---|
| [AMF storm — operator reviews each hold (answers piped to `python run.py --intent …`: decline, approve, intermediate tier)](outputs/y3172/examples/amf_signalling_storm_operator_review/report.md) | blocking | 3/3 | 1/1 | 0.8077 | 5 | 0 | 2 | 8 | 2 |
| [AMF storm — `--auto` (every hold approved)](outputs/y3172/examples/amf_signalling_storm/report.md) | blocking | 3/3 | 1/1 | 0.8846 | 3 | 2 | 1 | 12 | 0 |
| [Hospital slice — advisory mode, `--auto`](outputs/y3172/examples/hospital_slice_protection/report.md) | advisory | 4/4 | 2/2 | 1.0 | 0 | 0 | 0 | 8 | 0 |
| [Whole core, all 13 incident types — `--auto`](outputs/y3172/examples/core_security_full/report.md) | blocking | 13/13 | 4/4 | 1.0 | 0 | 0 | 0 | 16 | 2 |

What the runs show: benign look-alikes (flash crowd, authorised billing batch, maintenance window) are not reported; every injected attack is detected in the tick it starts; a ×5 growth in legitimate load first causes false alarms, which monitoring catches — the MLFO re-calibrates the sandbox to the live load, retrains and re-selects, and the false alarms stop; a low-confidence detection is escalated, not acted on. With `--auto` the false alarms' playbooks are applied (the report flags them); with an operator reviewing the blocking-mode holds, none is. These runs used stub knowledge bases for the specialist agents (vector stores are not committed); with `python -m src.rag.build` done first, the agents quote the ingested passages.

**Limits, stated plainly.** The "live" network is a second instance of the
contained simulator, not an operator network. Reference points and node levels
are logical: everything runs in one Python process. Monitoring feedback
("truth") comes from the simulator; in a real network it would come from
incident closure. Labels and obligations are decision support for a training
lab, not legal advice.

---

## Integration interfaces

- **RAG / Knowledge Base layer:** `INTEGRATION_RAG_KB.md`
- **UI layer:** `INTEGRATION_UI.md`
- **Whole-project run steps:** `INTEGRATION_CHECKLIST.md`
- **Evaluation summary:** `knowledge_base/evaluation_report.md`
- **Technical explanation (presentation):** `TECHNICAL_EXPLANATION.md`
- **Final handoff — sources, evidence examples, claims not to make:** `FINAL_HANDOFF.md`
- **Golden demo script (8–10 min) and failure fallbacks:** `DEMO_SCRIPT.md`
- **Rehearsal log and final team check:** `REHEARSAL_LOG.md`
- **Evidence audit:** `knowledge_base/evidence_audit.md` (`python -m src.rag.evidence_audit`)
- **Core freeze:** `CORE_FREEZE.json` (`python -m src.core.freeze --check`)

---

## Project structure

```
India_5G_Policy_Legal_Adviser/
├── src/
│   ├── core/
│   │   ├── models.py          # Data contracts (EvidenceItem, AgentFinding, ...)
│   │   ├── orchestrator.py    # Swarm Orchestrator
│   │   ├── verifier.py        # Verifier (4 outcomes)
│   │   ├── cross_domain.py    # Evidence-based cross-domain links and conflicts
│   │   └── coordinator.py     # Coordinator (5-category synthesis)
│   ├── agents/
│   │   ├── base_agent.py      # Abstract base — RAG integration point
│   │   ├── technical_agent.py
│   │   ├── policy_legal_agent.py
│   │   ├── cybersecurity_agent.py
│   │   ├── privacy_agent.py
│   │   ├── critical_infra_agent.py
│   │   ├── standards_agent.py
│   │   └── policy_gap_agent.py
│   ├── knowledge_base/
│   │   ├── base_kb.py         # Abstract KB interface
│   │   ├── in_memory_kb.py    # Dependency-free KB for tests and early integration
│   │   ├── text_match.py      # Deterministic text helpers (support check)
│   │   └── kb_registry.py     # Maps AgentID to KB instance
│   ├── rag/                   # RAG / knowledge-base layer
│   │   ├── manifest.py        # Source manifest loading; KB names
│   │   ├── extract.py         # PDF / DOCX extraction with page provenance
│   │   ├── sections.py        # Cleaning, section detection, chunking
│   │   ├── embedding.py       # bge-small-en-v1.5 embeddings
│   │   ├── vector_store.py    # One store per KB
│   │   ├── vector_kb.py       # Live KnowledgeBase / CanonicalKnowledgeBase
│   │   ├── build.py           # python -m src.rag.build
│   │   ├── registry.py        # build_registry() -> live KBRegistry
│   │   ├── interface.py       # run_agent(agent_id, chunk) -> AgentFinding
│   │   └── retrieval_demo.py  # python -m src.rag.retrieval_demo
│   ├── scenario/
│   │   ├── catalog.py         # DOCX stage tables (display/check only)
│   │   ├── engine.py          # ScenarioEngine: chunk-by-chunk release + state
│   │   ├── conflict_fixture.py # Labelled synthetic KBs for the conflict demonstration
│   │   └── run.py             # python -m src.scenario.run
│   ├── audit/
│   │   ├── trail.py           # Append-only, hash-chained JSONL audit trail
│   │   └── replay.py          # Load, verify, step through, re-execute
│   ├── ui/
│   │   └── app.py             # streamlit run src/ui/app.py
│   ├── utils/
│   │   └── output_formatter.py
│   ├── y3172/                 # ITU-T Y.3172 ML pipeline over the simulated core
│   │   ├── intent.py          # ML Intent: schema and validation
│   │   ├── nodes.py           # SRC, C (collector), PP (preprocessor)
│   │   ├── models.py          # M: candidate models, evaluation, explanations
│   │   ├── policy_node.py     # P: operator rules + Indian obligations + the agent swarm
│   │   ├── distributor.py     # D and SINKs (evidence, remediation, notices, escalation)
│   │   ├── notices.py         # Draft regulatory notices with verified deadlines
│   │   ├── mlfo.py            # MLFO: instantiate, sandbox, select, deploy, monitor, reselect
│   │   └── report.py          # Run report (markdown + JSON)
│   └── pipeline.py            # Top-level entry point
├── intents/                   # ML Intents (YAML) for the Y.3172 pipeline
├── sim/                       # Contained simulated 5G core; datagen.py: sandbox data
├── scenarios/
│   ├── scenario1_slicing_incident.py
│   └── scenario2_healthcare_5g.py
├── knowledge_base/
│   ├── sources/
│   │   ├── manifest.json      # Curated source manifest (in git)
│   │   └── raw/               # Downloaded source files (git-ignored)
│   ├── ingestion_manifest.json  # What was actually ingested (generated, in git)
│   ├── retrieval_tests.md     # One retrieval test per agent (generated, in git)
│   ├── canonical/ technical/ policy_legal/ cybersecurity/ privacy/
│   │   critical_infrastructure/ standards/ policy_gap/   # vector stores (git-ignored)
├── outputs/                   # Assessment text/JSON; audit/ holds recorded runs;
│                              # y3172/examples/ holds recorded Y.3172 pipeline runs
├── tests/
│   ├── test_pipeline.py
│   ├── test_verification_evidence.py
│   ├── test_rag.py
│   ├── test_scenario_audit.py
│   └── test_cross_domain.py
├── requirements.txt
├── INTEGRATION_RAG_KB.md
├── INTEGRATION_UI.md
└── README.md
```

---

## Implementation status

| Component | Status |
|---|---|
| Project structure | Complete |
| 7 specialist agents | Complete (role-bounded; source content only from cited retrieved passages) |
| Swarm Orchestrator | Complete (selection from released information; matches both DOCX scenario tables) |
| Two-pass Policy Gap execution | Complete |
| Verifier (4 outcomes) | Complete (citation + canonical-text support check; pluggable judge) |
| Coordinator (5 categories) | Complete |
| Scenario chunks T0-T3 | Complete |
| RAG / vector store | Complete — 14 of 16 DOCX sources ingested, 8 KBs, one retrieval test per agent passing |
| Not ingested | IT (NCIIPC) Rules 2013 (source unreachable); international policy examples (not specified in DOCX) |
| In-force / amendment checks | Not done for any source — quoted claims are INCOMPLETE, not VERIFIED |
| Scenario engine, audit trail, replay | Complete — stage tables checked against the DOCX; hash-chained JSONL; re-execution compare |
| Demonstration UI | Day-1 functional UI (Streamlit): live run and replay |
| Cross-domain verification | Complete — evidence-based (shared provision, instrument basis, parallel reporting), across chunks |
| Conflict handling | Complete — structured Finding A / Finding B with evidence; demonstrated with labelled fixtures (the live corpus has no conflicting provisions) |
| Progressive reassessment | Complete — cumulative facts, carried-forward conclusions, computed changes |
| Full 4-stage run | Recorded: `outputs/audit/day2_scenario2_full_T0_T3.jsonl` (replays and re-executes exactly) |
| ITU-T Y.3172 ML pipeline | Implemented over the simulated 5G core (`src/y3172/`): ML Intent, SRC/C/PP/M/P/D/SINK nodes, MLFO, ML sandbox, monitoring and re-selection, with the adviser as the P node. Not a live network; reference points and levels are logical (one process). The adviser's own document pipeline maps to Y.3172 mostly by analogy. See `knowledge_base/y3172_pipeline_traceability.json` |
| Generative model | None in the adviser (`src/`); the incident-response lab (`ir/`) can optionally use a Claude model, with an offline fallback |
| ITU AI for Good Sandbox | Not used — access was not available; everything runs locally |
| Tests | All passing — see `knowledge_base/evaluation_report.md` for per-area counts and status (Working / Partially working / Not yet implemented) |

---

## Key design rules

1. No cross-agent role bleed — each agent speaks only within its mandate
2. No fake verification — claims are UNSUPPORTED until the Canonical KB confirms them
3. Standards are reference points only — never stated as Indian law
4. Uncertainty preserved — DOCX Table A1 categories are strictly separated
5. Non-conclusive gap language — policy gaps use "potential gap", never assert failure
6. Human review notice present — in every output, unconditionally
