# How it works — team reference

> Synthetic scenarios; public/official sources; hackathon use. Decision support, not legal advice.

---

## The adviser in five sentences

1. It follows one 5G incident as facts arrive, chunk by chunk.
2. For each chunk it activates only the specialist agents the new facts justify — seven in all.
3. Each agent searches only its own knowledge base and quotes the law, with section and page — it never paraphrases from memory.
4. A Verifier checks every quote against a separate Canonical KB and marks it VERIFIED / INCOMPLETE / UNSUPPORTED / CONFLICT.
5. A Coordinator sorts the checked findings into five categories and writes a tamper-evident audit trail.

No generative model is in the path. Remove the language model from the adviser and the evidence, citations and verdicts still stand.

---

## The seven agents

| Agent | Its lane | Example Indian instruments |
| :--- | :--- | :--- |
| Technical | 5G radio, core, slicing | 3GPP TS 23.501 / 33.501 (reference only) |
| Policy & Legal | Telecom law & regulation | Telecommunications Act 2023, TRAI Act 1997 |
| Cybersecurity | Incident classification & reporting | Telecom Cyber Security Rules 2024, CERT-In Directions 2022 |
| Privacy | Personal-data impact | DPDP Act 2023, DPDP Rules 2025 |
| Critical Infrastructure | Critical-service duties | Telecommunications Act s.22, CTI Rules 2024 |
| Standards | International comparison | ITU-T Y.3172, 3GPP, ETSI, NIST (never Indian law) |
| Policy Gap | Potential gaps, for experts | All above + ENISA (EU) examples |

---

## How to read a result — the five categories

| Category | Meaning |
| :--- | :--- |
| Confirmed facts | What the incident actually tells us |
| Evidence-backed | Supported by the canonical text (VERIFIED) |
| Uncertain | Supported but unconfirmed (INCOMPLETE) or no evidence (UNSUPPORTED) |
| Conflicts | Two findings disagree — both shown, neither adopted |
| Potential gaps | Where coverage looks unclear or absent — for a human to judge |

---

## Scenario 2 — the demo arc

| Chunk | In plain words | What appears on screen |
| :--- | :--- | :--- |
| T0 | Just latency and dropped sessions | Technical agent only; 3GPP quoted, reference-only badge |
| T1 | Suspicious logins and signalling | "Possible security event"; six-hour reporting duties (TCS Rule 7, CERT-In) |
| T2 | A hospital service, possibly patient data | Critical Infra + Privacy; exposure suspected, not confirmed; cross-domain links appear |
| T3 | Who must be told, and what is missing | Parallel reporting duties; 4 potential policy gaps |

---

## The attack lab

- A simulated 5G core (software state only) — inject an attack, two panels appear: Policy (which Indian rules apply, with page) and Technical (network health + playbook).
- The agent fixes safe steps automatically; before anything bigger it stops and asks: `[1] Agent runs it  [2] I'll run it  [3] Stop`.
- "Resolved" is decided by the lab's own checks, not by the agent.

---

## Wording discipline

Say:
- Every statement is a quote with a source.
- Suspected exposure / confirmed exposure — keep them apart.
- International standards are reference only, not Indian law.
- Decision support — a human makes the call.

Do not say:
- "The AI decided / concluded that the law was broken." It does not conclude failure.
- "Verified" for anything on the live run. It is INCOMPLETE — amendment history not fully confirmed.
- "We cover NCIIPC." Those Rules were not obtained.
- Any number that cannot be pointed to on screen.

---

## Presenter split

| Person | Section |
| :--- | :--- |
| Harshini K (lead) | Opening problem, live run, close |
| Arshitha S | Knowledge base, sources, verification |
| Charithra H S | Cross-domain links, attack lab |
