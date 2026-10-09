# Judge Q&A — India 5G Policy & Legal Adviser

Seven questions, each with: why it is asked · what to say · what to click.

> Synthetic scenarios; public/official sources; hackathon use. Decision support, not legal advice.

---

## 1. Show the core workflow actually running right now — not the slides or the video

**Why they ask:** they want the live system, not a recording.

**What to say:**
> I'll run Scenario 2 live. It's a healthcare 5G incident released in four chunks. At T0 it's just latency, so only the Technical agent runs. As I release each chunk, more specialists activate — but only the ones the new facts justify, not by position in the script. Every legal statement is a quote from a retrieved passage, with section and page. Nothing is generated.

**What to click:**
1. `streamlit run src/ui/app.py` → Live run → scenario2 → Use live knowledge bases → Start run.
2. Release T0, then T1. Point at the "Active agents / NEW" markers and the line "Orchestrator selection matches the stage table."
3. Point at the Human review required banner that is always on screen.

---

## 2. Is any of this real data, or is it all synthetic?

**Why they ask:** to confirm no real people are involved and the law texts are genuine.

**What to say:**
> The incident scenarios are synthetic. The law is real: 23 official documents, each fetched from its own URL and checked by SHA-256, so the file we ingested is byte-identical to the published one. Every citation opens the real section and page. We never paraphrase a statute from memory — if there's no passage, the agent says the matter isn't assessed.

**What to click:**
1. Open any citation in the run — it shows source, section, page and a link.
2. Show `knowledge_base/sources/manifest.json` (authority, URL, SHA-256).

---

## 3. How does a human stay in control of the AI?

**Why they ask:** they want to see that people, not the model, make the high-stakes calls.

**What to say:**
> Two ways. The adviser is decision-support only — it carries a permanent "human review required" banner and never draws a conclusion of policy failure. In the attack lab, the agent fixes an incident automatically only where a step is marked safe and idempotent; before any escalation it stops at a gate and asks the operator: agent runs it, I'll run it myself, or stop. Some attacks deliberately change nothing in the first tier because the cause could be an honest mistake.

**What to click:**
1. `python run.py --attack rogue_base_station` → at the gate show the three options.
2. Choose "I'll run it" → it prints the exact `sim.cli` commands for a human to run.

---

## 4. Which specific Indian policy — by name and clause — governs this decision?

**Why they ask:** they want a named instrument and clause, not vague "compliance."

**What to say:**
> We cite by instrument, section and page. In Scenario 2: the Telecom Cyber Security Rules 2024, Rule 7 — report to the Central Government within six hours; the CERT-In Directions 2022, Direction (ii) — report to CERT-In within six hours; and the DPDP Rules 2025, Rule 7 — intimate the Data Principal and the Board without delay. The Telecom Cyber Security Rules are made under Section 22 of the Telecommunications Act 2023 — that link comes from the Rules' own text. International standards like 3GPP and ITU-T Y.3172 are always labelled reference only, never Indian law.

**What to click:**
1. At T1/T2, open the Cybersecurity and Critical Infrastructure findings.
2. Point at the cross-domain "instrument basis" link (Rules → s.22 of the Act).

---

## 5. How do you know the citation is right, and not just a confident guess?

**Why they ask:** they want verification, not trust.

**What to say:**
> A separate Verifier checks every claim against an independent Canonical KB — 5,710 passages from all 23 sources. Support is decided by the authoritative text, not by similarity or confidence. It returns VERIFIED, INCOMPLETE, UNSUPPORTED or CONFLICT. Nothing on our live corpus is marked VERIFIED, because we haven't fully confirmed amendment histories — so supported claims are INCOMPLETE, stated honestly. On the recorded run that's 50 INCOMPLETE and 10 UNSUPPORTED. Our evidence audit catches planted fabrications — an altered quote, a standard mislabelled as Indian law, a false VERIFIED — all seven.

**What to click:**
1. Open a claim showing its Verifier outcome and rationale.
2. Show `knowledge_base/evaluation_report.md` (392 tests passed) and the evidence-audit line (60 claims, 0 problems).

---

## 6. Can we reproduce your results from the repo?

**Why they ask:** a result that cannot be reproduced is not a result.

**What to say:**
> Yes. `fetch_sources` downloads the documents and checks the hashes, `build` builds the knowledge bases, the test suite runs 392 checks, and the recorded run replays stage-by-stage with its hash chain verified. The retrieval is deterministic, so three rehearsals produced identical output. The attack lab's index is built once and committed with its file hashes, so it loads the same for everyone.

**What to click:**
1. `python -m pytest tests -v` (392 passed).
2. `python -m src.scenario.run --replay outputs/audit/day2_scenario2_full_T0_T3.jsonl --reexecute`.

---

## 7. How does this map to ITU-T Y.3172 and the readiness framework?

**Why they ask:** the track is built on these; they want to see it is not name-dropped.

**What to say:**
> Our code carries a machine-checked Y.3172 traceability map — each pipeline node quotes the Y.3172 definition and names the component that performs it — labelled as architectural correspondence, not formal compliance. The attack lab is the Y.3172 "sandbox" node: a simulated underlay where we test effects before any live network. On the ITU AI Ready 2.0 framework we claim three dimensions we can evidence — Cross-Domain Correlation Analysis, AI & Policies, and Collaboration with AI.

**What to click:**
1. Show the standards agent retrieving Y.3172 Clause 3.2 (the sandbox definition).
2. Show the IR lab running one attack with its Policy panel.
