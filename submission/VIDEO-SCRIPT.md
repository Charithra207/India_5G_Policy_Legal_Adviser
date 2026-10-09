# Demo video script — India 5G Policy & Legal Adviser

Approximately 5 minutes, read at a calm pace. Everything spoken appears on screen and matches the recorded run `outputs/audit/day2_scenario2_full_T0_T3.jsonl`.

Before recording:
- `streamlit run src/ui/app.py`, browser at 1920×1080, light theme.
- Live run chosen, scenario2, Use live knowledge bases on — press Start once before recording so the models load off-camera.
- A second tab in Replay mode on the recorded run, as a fallback.
- Nothing released yet; the Human review required banner visible.

---

## 0:00 – 0:40 · The problem

> [Show: the UI, nothing released, banner visible]

"This is the India 5G Policy and Legal Adviser.

A 5G incident rarely arrives complete. A latency complaint becomes a security event, then a hospital service carrying patient data, then a question of who must be told, and within how many hours. Each step brings in different Indian law.

One answer at the start cannot follow that. So this system follows the incident chunk by chunk — with seven specialist agents. Each one quotes the law; none of it is generated. And this banner never leaves: a human makes the decision."

---

## 0:40 – 1:20 · Where every answer comes from

> [Show: the knowledge-base / sources view]

"Every statement comes from here — twenty-three official documents: the Telecommunications Act, the Telecom Cyber Security Rules, the CERT-In Directions, the DPDP Act and Rules, and more. Each one was fetched from its own government URL and checked by a hash, so the file we use is identical to the published one.

If a question is not covered, the agent says so — it never fills the gap from memory. That refusal is the point."

---

## 1:20 – 2:05 · Chunk one — just latency

> [Click: Release next chunk (T0)]

"Chunk one: latency and dropped sessions. Only the Technical agent activates — because only a performance symptom has been released.

It quotes 3GPP TS 23.501, with the section, the page, and a link — carrying a 'reference only, not Indian law' badge. We never dress an international standard up as national law.

The Verifier has already rated each claim: supported-but-unconfirmed is marked INCOMPLETE, not verified. We do not overclaim."

---

## 2:05 – 2:55 · Chunk two — it becomes a security event

> [Click: Release next chunk (T1)]

"New facts: suspicious authentication and signalling. The banner changes — the incident is now a possible security event — and two new agents wake up: Cybersecurity and Standards.

Here is the first sharp result. Two separate Indian duties now apply to the same incident: the Telecom Cyber Security Rules, Rule seven — report to the Central Government within six hours — and the CERT-In Directions — report to CERT-In within six hours. Same clock, different bodies."

---

## 2:55 – 3:55 · Chunk three — a hospital, and the links

> [Click: Release next chunk (T2)]

"Now we learn it is a hospital service, possibly with patient data. Critical Infrastructure, Privacy and Policy & Legal activate.

Privacy is careful: exposure is suspected, not confirmed — the system keeps those apart.

And this is the moment ordinary search cannot do. The Telecom Cyber Security Rules state, in their own text, that they are made under Section 22 of the Telecommunications Act — the very section Critical Infrastructure is citing. The system draws that link from the evidence, not because two agents are switched on. Alongside it: the privacy duty to tell the Data Protection Board runs in parallel with the six-hour duties from before."

---

## 3:55 – 4:40 · Chunk four — reporting, and what is missing

> [Click: Release next chunk (T3)]

"The last chunk asks the reporting and escalation question. The adviser pulls together the whole incident: the parallel duties, the institutions, and four potential policy gaps — raised as questions for a human expert, never as a verdict that the law failed.

Everything you have seen is written to an append-only, hash-chained audit trail. It can be replayed stage by stage and the chain checked — and an evidence audit traces all sixty claims to their passages, with zero problems, catching planted fabrications like a false 'verified' or a mislabelled standard."

---

## 4:40 – 5:05 · Close

> [Show: the full assessment, banner visible]

"An evolving 5G incident, followed chunk by chunk, across technical, legal, cybersecurity, privacy and critical-infrastructure domains. Every line is a quote with a source. Nothing is generated, nothing is overclaimed, and a human stays in charge.

The India 5G Policy and Legal Adviser. Thank you."

---

Over-time cut: remove 0:40–1:20 (the knowledge-base block) and go straight from the problem to the first chunk; this lands at about 4:15.

Optional 30-second add-on — the attack lab:
> [Terminal: `python run.py --attack signalling_storm_amf`]
"Beside the adviser is a contained attack lab — a simulated 5G core, no real network. Inject a signalling storm, and two panels appear: the Indian rules that apply, and the technical playbook. The agent runs the safe fixes itself, and before anything bigger it stops and asks a human. 'Resolved' is decided by the lab's own checks, not by the agent."
