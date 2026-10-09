# Golden demo — 8 to 10 minutes

The script follows the live run. Everything it says appears on screen and
matches the recorded run `outputs/audit/day2_scenario2_full_T0_T3.jsonl`
(three rehearsals produced identical output; see `REHEARSAL_LOG.md`).
Wording rules for the whole demo are in `FINAL_HANDOFF.md` → "Claims that
should NOT be made".

## Before the audience arrives (5 minutes)

1. Run `streamlit run src/ui/app.py` and open the browser tab.
2. Choose **Live run**, scenario **scenario2**, with **Use live knowledge
   bases** on. Press **Start run**. This loads the models; do it now, not in
   front of the audience.
3. In a second tab, keep the app open in **Replay** mode. It opens on
   `day2_scenario2_full_T0_T3.jsonl`.
4. Keep `outputs/demo/backup_full_run_replay.txt` open in an editor as the
   fallback.

## 0:00 – 1:00 Problem

> A 5G incident rarely arrives complete. A latency complaint can become a
> security event, then a hospital service with patient data, then a
> question of who must be told. Each step brings in different Indian law,
> institutions and standards. One answer given at the start cannot follow
> that. This adviser follows the incident chunk by chunk, with seven
> specialist agents. Each searches its own knowledge base, and a Verifier
> checks every claim against a separate Canonical KB. It is decision
> support; legal judgment stays with people.

Point at the always-visible **Human review required** banner.

## 1:00 – 2:15 Chunk 1 — latency and session drops

Press **Release next chunk (T0)**.

- **Active agents:** Technical (NEW). The green line reads "Orchestrator
  selection matches the DOCX stage table."
- **Agent findings → Technical:** network performance degradation; affected
  components inferred from the symptoms.
- **Evidence / sources → Technical:** 3GPP TS 23.501 Clause 5.37.7.1 (packet
  delay variation) is quoted with section, page, link, "in-force status not
  verified" and the **REFERENCE ONLY — not Indian law** badge.
- **Verifier result:** INCOMPLETE 4, UNSUPPORTED 2.

> The quotes are supported by the authoritative text. Where we hold the
> commencement notification, the Verifier names the in-force date: at T1 and
> T2, open a TCS Rule 7 or Telecommunications Act s.22 claim, which reads
> "in force from … (S.O. 2408(E))". The amendment history isn't shown to be
> complete, so they stay INCOMPLETE rather than VERIFIED. The agent's own reading
> ("the incident involves the UPF…") is UNSUPPORTED: no passage states it.

## 2:15 – 3:30 Chunk 2 — suspicious authentication and signalling

Press **Release next chunk (T1)**.

- **Active agents:** Cybersecurity and Standards marked NEW.
- **What changed** banner: "Incident reassessed as a possible security event".
- **Evidence → Cybersecurity:**
  - Telecom Cyber Security Rules 2024, **Rule 7**: report a security
    incident to the Central Government within six hours.
  - CERT-In Directions, **Direction (ii)**: report to CERT-In within 6 hours.
- **Standards:** 3GPP TS 33.501 passages, labelled reference only.

## 3:30 – 5:15 Chunk 3 — healthcare service and possible patient data

Press **Release next chunk (T2)**.

- **Active agents:** Critical Infrastructure, Privacy, Policy & Legal.
- **Critical Infrastructure:** quotes the Critical Telecommunication
  Infrastructure Rules 2024 (Rules 3, 5, 8) and Telecommunications Act s.22.
- **What changed:**
  - "Critical-service relevance appears for the first time"
  - "Possible personal-data involvement appears for the first time"
  - T1 conclusions are carried forward and shown greyed.
- **Privacy:** exposure is **suspected**, not confirmed. DPDP Rules 2025,
  Rule 7 (intimation of a personal data breach) is quoted.
- **Cross-domain relationships** — the key moment:
  - The Telecom Cyber Security Rules (Cybersecurity, from T1) state they are
    made "in exercise of the powers conferred by … section 22 … of the
    Telecommunications Act, 2023", which Critical Infrastructure and
    Policy & Legal cite now.
  - DPDP Rules Rule 7 (Data Principal, Board: without delay) and the T1
    six-hour reporting duties are parallel obligations for the same
    incident.

> These links come from the cited text, not from the agents simply both
> being active.

## 5:15 – 6:45 Chunk 4 — reporting, escalation and policy uncertainty

Press **Release next chunk (T3)**. This step takes about 10 seconds on a
cold machine, because the Policy Gap Agent examines every Indian passage.
Talk through it.

- **Active agents:** Policy & Legal, Cybersecurity, Privacy, Critical
  Infrastructure, Policy Gap.
- **Potential policy gaps.** Read the categories as written:
  - **Emerging technology not explicitly addressed:** none of the 886
    passages of the Indian legal and policy instruments examined mentions
    network slicing. It appears only in TRAI recommendations, which are
    not law.
  - **Overlapping requirements:** CERT-In Direction (ii) and DPDP Rules Rule 7
    both carry reporting duties for the same incident, and neither refers to
    the other.
  - **Missing institutional clarity:** NCSP-2013 addresses NCIIPC and
    NDCP-2018 addresses CERT-In, but no examined passage addresses both.

> These are *potential* gaps for expert review, identified in the documents
> we ingested. They are not a finding that Indian law is inadequate, and not
> a claim that no provision exists anywhere.

- **Uncertainty:** "No conclusion is evidence-backed at this stage", followed
  by the open questions (for example "Formal CII designation status", "Whether
  NCIIPC has been notified").

## 6:45 – 7:30 Verification: valid evidence → VERIFIED

Switch to the **Replay** tab and select `day2_conflict_demo_FIXTURE.jsonl`.
A yellow banner says it uses FIXTURE knowledge bases. Press **Next ▶** to T1.

- **Verifier result:** VERIFIED 1. Evidence-backed conclusions holds the
  synthetic Direction 4 passage.

> This uses a labelled test passage whose amendment history is recorded as
> complete. The same Verifier returns VERIFIED when the text supports the
> claim, the provision is in force, and no amendment applies. For the real
> sources we hold the in-force notifications but cannot show that no other
> amendment exists, so we show INCOMPLETE rather than pretend.

## 7:30 – 8:15 Failure handling: unsupported claim → UNSUPPORTED, and a conflict

- **Policy Gap comparators** are quoted from ENISA's 5G Cybersecurity
  Standards, an EU policy example, labelled "REFERENCE ONLY — not Indian
  law".
- Still in the fixture replay, press **Next ▶** to T2. The **Conflict** shows
  Finding A (Policy & Legal: report to CERT-In within twenty-four hours) and
  Finding B (Cybersecurity, T1: within six hours), each with its evidence.
  Status: unresolved, for human review. Neither is adopted.
- Select the full run, step back to **T0**, and open **Verifier result →
  UNSUPPORTED**: "The incident involves … UPF …" with the rationale "the
  authoritative text does not support the claim".

## 8:15 – 9:15 Audit and replay

On the full run:

- In the sidebar, **Hash chain intact (4 stage entries)**: any edited,
  removed or reordered entry would be detected.
- Open **Decision path** for a stage. It answers what happened, which agent
  acted, what evidence was retrieved, what was concluded, how it was
  verified, and how the Coordinator reached the assessment.
- Press **Re-execute and compare** (about 3 seconds). "Re-execution
  reproduced every stage."
- **Audit record for this stage → Full audit entry (JSON)** holds the
  detailed log.

## 9:15 – 9:45 Close

> Every statement shown traces to a quoted passage with its source, section
> and page. What we have not done is equally explicit:
> - in-force and amendment checks;
> - the NCIIPC Rules and international comparators;
> - a generative model by default (the optional Ollama/Claude mode only adds claims that cite retrieved passages, and the Verifier still checks them);
> - the ITU AI for Good Sandbox (access was not available; everything runs locally);
> - a live network: the Y.3172 ML pipeline (`python run.py --intent …`) runs on the contained simulator.

## If something fails

| Failure | What to do | Real material used |
|---|---|---|
| API | Nothing to do: the system calls no external API | — |
| Network | Nothing to do: the models and stores are local (tested with the network blocked) | — |
| Retrieval or KB load fails during the live run | Switch to the **Replay** tab and present the same four stages | `outputs/audit/day2_scenario2_full_T0_T3.jsonl` |
| An agent fails | The assessment states "AGENT FAILURE — … not assessed" in Uncertainty; say so and continue, or switch to Replay | — |
| UI crashes | Restart `streamlit run src/ui/app.py` (it starts in a few seconds); if it won't start, present from the text replay | `outputs/demo/backup_full_run_replay.txt` and `backup_conflict_fixture_replay.txt` (generated by `python -m src.scenario.run --replay … --explain`) |
| Laptop fails | Present from `TECHNICAL_EXPLANATION.md` and `knowledge_base/evidence_audit.md` | — |
