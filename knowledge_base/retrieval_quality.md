# Retrieval quality

Generated 2026-10-06T16:38:02.157531+00:00 by `python -m src.rag.retrieval_quality`.

Each query is labelled with the provision whose own heading or text addresses the topic; the label is checked to exist in the corpus. Results describe this corpus and embedding model only.

| Measure | Result |
|---|---|
| Expected section ranked first (hit@1) | 8 / 12 |
| Expected section in top 5 (hit@5) | 12 / 12 |
| Relevant passage retrieved | 12 / 12 |
| Expected source among results | 12 / 12 |
| Mean source precision@5 | 0.78 |
| Metadata complete on every result | 12 / 12 |
| Results only from the agent's own KB | 12 / 12 |

| Agent | Query | Expected | Rank | Top result |
|---|---|---|---|---|
| technical | network slice selection and isolation in the 5G core | 3gpp_ts_23501, Clause 5.15.1 | 5 | 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 4.2.11 |
| technical | QoS monitoring of packet delay between UE and UPF | 3gpp_ts_23501, Clause 5.45.2 | 1 | 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.45.2 |
| cybersecurity | telecommunication entity reporting of a security incident within six hours | telecom_cyber_security_rules_2024, Rule 7 | 1 | Telecommunications (Telecom Cyber Security) Rules, 2024, Rule 7 |
| cybersecurity | mandatory reporting of cyber incidents to CERT-In | certin_directions_2022, Direction (ii) | 1 | CERT-In Directions under sub-section (6) of section 70B of the Information Technology Act, 2000 (28 April 2022), Direction (ii) |
| privacy | intimation of personal data breach to the Data Protection Board | dpdp_rules_2025, Rule 7 | 1 | Digital Personal Data Protection Rules, 2025, Rule 7 |
| privacy | reasonable security safeguards to protect personal data | dpdp_rules_2025, Rule 6 | 1 | Digital Personal Data Protection Rules, 2025, Rule 6 |
| critical_infrastructure | rules for measures to protect cyber security of telecommunication networks | telecom_act_2023, Section 22 | 1 | The Telecommunications Act, 2023, Section 22 |
| policy_legal | authorisation required to provide telecommunication services | telecom_act_2023, Section 3 | 1 | The Telecommunications Act, 2023, Section 3 |
| policy_legal | functions and powers of the Telecom Regulatory Authority of India | trai_act_1997, Section 11 | 1 | The Telecom Regulatory Authority of India Act, 1997 (as amended, TDSAT compilation), Section 11 |
| standards | machine learning sandbox for training and testing before deployment in a live network | itu_t_y3172, Clause 3.2 | 5 | ITU-T Recommendation Y.3172 (06/2019) Architectural framework for machine learning in future networks including IMT-2020, Clause 8.3 |
| standards | incident response recommendations for cybersecurity risk management | nist_sp_800_61r3, Section 1 | 5 | NIST SP 800-61r3: Incident Response Recommendations and Considerations for Cybersecurity Risk Management (A CSF 2.0 Community Profile), p. 5 |
| policy_gap | protection of critical information infrastructure as a national objective | ncsp_2013, Part III item 5 | 2 | National Cyber Security Policy - 2013, Part IV G |
