# Retrieval tests — one per specialist agent

Generated 2026-10-05T16:28:45.320021+00:00 by `python -m src.rag.retrieval_demo`.
Scenario 2 (DOCX §2.5), chunks T0–T3, full pipeline with live KBs. Agents with a successful retrieval: **7 / 7**.

*Why relevant* is computed (query, cosine similarity, shared terms); whether a passage supports a claim is decided only by the Verifier outcome.

## technical
- **Chunk:** scenario2_T0 — Intermittent latency and session drops in the private 5G slice.
- **KB:** Technical KB (3gpp_ts_23501, 3gpp_ts_33501)
- **Passages retrieved:** 14

### Retrieval 1
- **Query:** Intermittent latency and session drops in the private 5G slice.
- **Source:** 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19 (3rd Generation Partnership Project (3GPP); International; Standard)
- **Section:** Clause 5.37.7.1 — General
- **Date issued:** 2026-09 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.703; query terms in passage: none (semantic match only)
- **Chunk ID:** `3gpp_ts_23501:clause-5-37-7-1:1`

> The 5GS Packet Delay Variation is the variation of packet delay measured between UE and PSA UPF. The AF may send the requirement for Packet Delay Variation monitoring to 5GS together with the requirement for packet delay measurement, as described in clause 6.1.3.26 of TS 23.503 [45]. Upon AF request for Packet Delay Variation monitoring together with packet delay monitoring, the PCF triggers the QoS monitoring procedure and obtains the UL, DL or RT QoS Monitoring result from the SMF. After receiving the QoS Monitoring result, the PCF derives the 5GS Packet Delay Variation based on the QoS …

### Retrieval 2
- **Query:** PDU session release and loss of user plane connectivity
- **Source:** 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19 (3rd Generation Partnership Project (3GPP); International; Standard)
- **Section:** Clause 5.5.2 — Connection Management
- **Date issued:** 2026-09 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.759; query terms in passage: pdu, plane, user
- **Chunk ID:** `3gpp_ts_23501:clause-5-5-2:6`

> for the non-3GPP access, these PDU Sessions are not released to enable the UE to move the PDU Sessions over the 3GPP access based on UE policies. The core network maintains the PDU Sessions but deactivates the N3 user plane connection for such PDU Sessions.

### Retrieval 3
- **Query:** Intermittent latency and session drops in the private 5G slice.
- **Source:** 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19 (3rd Generation Partnership Project (3GPP); International; Standard)
- **Section:** Clause 5.33.1 — General
- **Date issued:** 2026-09 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.700; query terms in passage: latency, session
- **Chunk ID:** `3gpp_ts_23501:clause-5-33-1:1`

> The following features described in 5.33 may be used to enhance 5GS to support Ultra Reliable Low Latency Communication (URLLC): - Redundant transmission for high reliability communication. In this Release, URLLC applies to 3GPP access only. When a PDU Session is to serve URLLC QoS Flow, the UE and SMF should establish the PDU Session as always-on PDU Session as described in clause 5.6.13. NOTE 1: How the UE knows whether a PDU Session is to serve a URLLC QoS Flow when triggering PDU Session establishment is up to UE implementation. NOTE 2: No additional functionality is specified for URLLC …

### Structured agent output
- **Summary:** Technical assessment: Network performance degradation / potential service-quality failure. Affected components: Network Slice (performance layer), User Plane Function (UPF), Private 5G Network (dedicated slice). Further telemetry required to confirm root cause.
- **Claims:**
  - [UNSUPPORTED] The incident involves Network Slice (performance layer), User Plane Function (UPF), Private 5G Network (dedicated slice). — agent's reading of the facts
  - [UNSUPPORTED] Incident classification: Network performance degradation / potential service-quality failure. — agent's reading of the facts
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.37.7.1 states: "The 5GS Packet Delay Variation is the variation of packet delay measured between UE and PSA UPF. The AF may send the requirement for Packet Delay … — cites 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.37.7.1
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.5.2 states: "for the non-3GPP access, these PDU Sessions are not released to enable the UE to move the PDU Sessions over the 3GPP access based on UE policies. The … — cites 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.5.2
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.33.1 states: "The following features described in 5.33 may be used to enhance 5GS to support Ultra Reliable Low Latency Communication (URLLC): - Redundant … — cites 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.33.1
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.45.2 states: "QoS Monitoring for packet delay allows for the measurement of UL packet delay, DL packet delay or round trip packet delay between UE and PSA UPF. The … — cites 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.45.2

## policy_legal
- **Chunk:** scenario2_T2 — The slice supports a healthcare application and may carry identifiable patient information.
- **KB:** Indian Legal/Regulatory KB (ncsp_2013, ndcp_2018, telecom_act_2023, trai_act_1997)
- **Passages retrieved:** 21

### Retrieval 1
- **Query:** The slice supports a healthcare application and may carry identifiable patient information.
- **Source:** National Cyber Security Policy - 2013 (Government of India (Department of Electronics and Information Technology); India; Policy)
- **Section:** Part III item 10 (p. 4)
- **Date issued:** 2013 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.635; query terms in passage: information
- **Chunk ID:** `ncsp_2013:part-iii-item-10:1`

> 10) To enable protection of information while in process, handling, storage & transit so as to safeguard privacy of citizen's data and for reducing economic losses due to cyber crime or data theft.

### Retrieval 2
- **Query:** measures to protect telecommunication networks and services and their security
- **Source:** The Telecommunications Act, 2023 (Government of India (Ministry of Law and Justice, Legislative Department); India; Act)
- **Section:** Section 22 (p. 10-11)
- **Date issued:** 24th December, 2023 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.805; query terms in passage: measures, networks, protect, security, services, telecommunication
- **Chunk ID:** `telecom_act_2023:section-22:1`

> 22. (1) The Central Government may by rules provide for the measures to protect and ensure cyber security of telecommunication networks and telecommunication services. (2) The measures may include collection, analysis and dissemination of traffic data that is generated, transmitted, received or stored in telecommunication networks. Explanation.—For the purposes of this sub-section, the expression "traffic data" means any data generated, transmitted, received or stored in telecommunication networks including data relating to the type, routing, duration or time of a telecommunication. (3) The …

### Retrieval 3
- **Query:** authorisation to provide telecommunication services and operate networks
- **Source:** The Telecommunications Act, 2023 (Government of India (Ministry of Law and Justice, Legislative Department); India; Act)
- **Section:** Section 3 (p. 3-4)
- **Date issued:** 24th December, 2023 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.821; query terms in passage: authorisation, operate, provide, services, telecommunication
- **Chunk ID:** `telecom_act_2023:section-3:1`

> 3. (1) Any person intending to— (a) provide telecommunication services; (b) establish, operate, maintain or expand telecommunication network; or (c) possess radio equipment, shall obtain an authorisation from the Central Government, subject to such terms and conditions, including fees or charges, as may be prescribed. (2) The Central Government may while making rules under sub-section (1) provide for different terms and conditions of authorisation for different types of telecommunication services, telecommunication network or radio equipment. (3) The Central Government, if it determines that …

### Structured agent output
- **Summary:** Policy & Legal assessment: 4 provision(s) quoted from the Indian Legal/Regulatory KB, 3 of which impose duties.
- **Claims:**
  - [INCOMPLETE] National Cyber Security Policy - 2013, Part III item 10 states: "10) To enable protection of information while in process, handling, storage & transit so as to safeguard privacy of citizen's data and for reducing economic losses due to cyber crime or data theft." — cites National Cyber Security Policy - 2013, Part III item 10
  - [INCOMPLETE] The Telecommunications Act, 2023, Section 22 states: "22. (1) The Central Government may by rules provide for the measures to protect and ensure cyber security of telecommunication networks and telecommunication services. (2) The measures may include collection, analysis and dissemination of … — cites The Telecommunications Act, 2023, Section 22
  - [INCOMPLETE] The Telecommunications Act, 2023, Section 3 states: "3. (1) Any person intending to— (a) provide telecommunication services; (b) establish, operate, maintain or expand telecommunication network; or (c) possess radio equipment, shall obtain an authorisation from the Central Government, subject to … — cites The Telecommunications Act, 2023, Section 3
  - [INCOMPLETE] The Telecom Regulatory Authority of India Act, 1997 (as amended, TDSAT compilation), Section 11 states: "11. Functions of Authority.— [(1)Notwithstanding anything contained in the Indian Telegraph Act, 1885 (13 of 1885), the functions of the Authority shall be to— (a) make recommendations, either … — cites The Telecom Regulatory Authority of India Act, 1997 (as amended, TDSAT compilation), Section 11
- **Uncertainty:** Critical-service relevance has been flagged. Whether the Telecommunications Act, 2023 critical telecommunication infrastructure provisions apply depends on retrieved provisions and formal designation. / Personal data may be involved. Any interaction between telecom obligations and data-protection obligations is for the Privacy Agent and the Verifier's cross-domain check, not this agent.

## cybersecurity
- **Chunk:** scenario2_T1 — Unusual authentication and signalling attempts are observed on the affected private 5G slice.
- **KB:** Cybersecurity KB (3gpp_ts_33501, certin_directions_2022, etsi_gr_nfv_sec_003, ncsp_2013, ndcp_2018, nist_csf_2_0, nist_sp_800_61r3, telecom_cyber_security_rules_2024)
- **Passages retrieved:** 22

### Retrieval 1
- **Query:** Unusual authentication and signalling attempts are observed on the affected private 5G slice.
- **Source:** 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19 (3rd Generation Partnership Project (3GPP); International; Standard)
- **Section:** Clause B.1 — Introduction
- **Date issued:** 2026-06 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.718; query terms in passage: 5g, authentication, private
- **Chunk ID:** `3gpp_ts_33501:clause-b-1:1`

> The present annex describes an example of the usage of additional EAP methods for primary authentication in private networks using the 5G system as specified in TS 22.261 [7]. It is provided as an example on how the 5G authentication framework for primary authentication can be applied to EAP methods other than EAP-AKA' The additional EAP methods are only intended for private networks or with IoT devices in isolated deployment scenarios, i.e. roaming is not considered, as specified in TS 22.261 [7]. When the 5G system is deployed in private networks, the SUPI and SUCI should be encoded using …

### Retrieval 2
- **Query:** telecommunication entity reporting of a security incident and the time limit
- **Source:** Telecommunications (Telecom Cyber Security) Rules, 2024 (Government of India (Ministry of Communications, Department of Telecommunications); India; Rules)
- **Section:** Rule 7 — Reporting of security incidents (p. 5-6)
- **Date issued:** 21st November, 2024 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.848; query terms in passage: entity, incident, reporting, security, telecommunication
- **Chunk ID:** `telecom_cyber_security_rules_2024:rule-7:1`

> 7. Reporting of security incidents. — (1) The telecommunication entity shall– (a) within six hours of becoming aware of a security incident affecting its telecommunication network or telecommunication service, report the same to the Central Government with relevant details of the affected system including the description of such incident; and (b) within twenty-four hours of becoming aware of such incident, furnish the following information, as applicable: the number of users affected by the security incident; the duration of the security incident; (iii) the geographical area affected by the …

### Retrieval 3
- **Query:** telecommunication entity reporting of a security incident and the time limit
- **Source:** CERT-In Directions under sub-section (6) of section 70B of the Information Technology Act, 2000 (28 April 2022) (Indian Computer Emergency Response Team (CERT-In), Ministry of Electronics and Information Technology; India; Direction)
- **Section:** Direction (ii) — Any service provider, intermediary, data centre, body corporate and (p. 2)
- **Date issued:** 28 April, 2022 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.783; query terms in passage: incident, reporting, security, time
- **Chunk ID:** `certin_directions_2022:direction-ii:1`

> (ii) Any service provider, intermediary, data centre, body corporate and Government organisation shall mandatorily report cyber incidents as mentioned in Annexure I to CERT-In within 6 hours of noticing such incidents or being brought to notice about such incidents. The incidents can be reported to CERT-In via email (incident@cert-in.org.in), Phone (1800- 11-4949) and Fax (1800-11-6969). The details regarding methods and formats of reporting cyber security incidents is also published on the website of CERT-In www.cert-in.org.in and will be updated from time to time.

### Structured agent output
- **Summary:** Cybersecurity assessment: possible cybersecurity incident indicated by the released facts. 4 provision(s) quoted from the Cybersecurity KB.
- **Claims:**
  - [UNSUPPORTED] The security indicators released in this chunk ("Unusual authentication and signalling attempts are observed on the affected private 5G slice.") are consistent with a possible cybersecurity incident affecting the 5G network, such as an unauthorised access attempt, a signalling attack, or an … — agent's reading of the facts
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19, Clause B.1 states: "The present annex describes an example of the usage of additional EAP methods for primary authentication in private networks using the 5G system as … — cites 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19, Clause B.1
  - [INCOMPLETE] Telecommunications (Telecom Cyber Security) Rules, 2024, Rule 7 states: "7. Reporting of security incidents. — (1) The telecommunication entity shall– (a) within six hours of becoming aware of a security incident affecting its telecommunication network or telecommunication service, report the same … — cites Telecommunications (Telecom Cyber Security) Rules, 2024, Rule 7
  - [INCOMPLETE] CERT-In Directions under sub-section (6) of section 70B of the Information Technology Act, 2000 (28 April 2022), Direction (ii) states: "(ii) Any service provider, intermediary, data centre, body corporate and Government organisation shall mandatorily report cyber incidents as mentioned in Annexure … — cites CERT-In Directions under sub-section (6) of section 70B of the Information Technology Act, 2000 (28 April 2022), Direction (ii)
  - [INCOMPLETE] Telecommunications (Telecom Cyber Security) Rules, 2024, Rule 5 states: "5. Measures to protect and ensure telecom cyber security.— (1) The Central Government may put in place digital and other mechanisms as it may consider necessary to identify, or for enabling any person to identify and report, … — cites Telecommunications (Telecom Cyber Security) Rules, 2024, Rule 5

## privacy
- **Chunk:** scenario2_T2 — The slice supports a healthcare application and may carry identifiable patient information.
- **KB:** Privacy KB (dpdp_act_2023, dpdp_rules_2025)
- **Passages retrieved:** 14

### Retrieval 1
- **Query:** The slice supports a healthcare application and may carry identifiable patient information.
- **Source:** The Digital Personal Data Protection Act, 2023 (Government of India (Ministry of Law and Justice, Legislative Department); India; Act)
- **Section:** Section 2 (p. 2-3)
- **Date issued:** 11th August, 2023 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.680; query terms in passage: none (semantic match only)
- **Chunk ID:** `dpdp_act_2023:section-2:2`

> facts, concepts, opinions or instructions in a manner suitable for communication, interpretation or processing by human beings or by automated means; (i) “Data Fiduciary” means any person who alone or in conjunction with other persons determines the purpose and means of processing of personal data; (j) “Data Principal” means the individual to whom the personal data relates and where such individual is— (i) a child, includes the parents or lawful guardian of such a child; (ii) a person with disability, includes her lawful guardian, acting on her behalf; (k) “Data Processor” means any person …

### Retrieval 2
- **Query:** intimation of a personal data breach to the Board and to affected Data Principals
- **Source:** Digital Personal Data Protection Rules, 2025 (Government of India (Ministry of Electronics and Information Technology); India; Rules)
- **Section:** Rule 7 — Intimation of personal data breach (p. 26)
- **Date issued:** 13th November, 2025 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.827; query terms in passage: affected, board, breach, data, intimation, personal
- **Chunk ID:** `dpdp_rules_2025:rule-7:1`

> 7. Intimation of personal data breach. — (1) On becoming aware of any personal data breach, the Data Fiduciary shall, to the best of its knowledge, intimate to each affected Data Principal, in a concise, clear and plain manner and without delay, through her user account or any mode of communication registered by her with the Data Fiduciary, — (a) a description of the breach, including its nature, extent and the timing of its occurrence; (b) the consequences relevant to her, that are likely to arise from the breach; (c) the measures implemented and being implemented by the Data Fiduciary, if …

### Retrieval 3
- **Query:** reasonable security safeguards a Data Fiduciary must take to prevent personal data breach
- **Source:** Digital Personal Data Protection Rules, 2025 (Government of India (Ministry of Electronics and Information Technology); India; Rules)
- **Section:** Rule 6 — Reasonable security safeguards (p. 26)
- **Date issued:** 13th November, 2025 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.917; query terms in passage: breach, data, fiduciary, personal, prevent, reasonable, safeguards, security
- **Chunk ID:** `dpdp_rules_2025:rule-6:1`

> 6. Reasonable security safeguards. — (1) A Data Fiduciary shall protect personal data in its possession or under its control, including in respect of any processing undertaken by it or on its behalf by a Data Processor, by taking reasonable security safeguards to prevent personal data breach, which shall include, at the minimum, — (a) appropriate data security measures, such as securing of personal data through encryption, obfuscation, masking or the use of virtual tokens mapped to that personal data; (b) appropriate measures to control access to the computer resources used by such Data …

### Structured agent output
- **Summary:** Privacy assessment: personal data exposure status is 'suspected'. 4 DPDP provision(s) quoted from the Privacy KB.
- **Claims:**
  - [UNSUPPORTED] Personal data exposure is SUSPECTED: the affected slice may carry identifiable patient or subscriber information. Confirmed exposure cannot be established from current facts — further investigation required. — agent's reading of the facts
  - [INCOMPLETE] The Digital Personal Data Protection Act, 2023, Section 2 states: "facts, concepts, opinions or instructions in a manner suitable for communication, interpretation or processing by human beings or by automated means; (i) “Data Fiduciary” means any person who alone or in conjunction with other … — cites The Digital Personal Data Protection Act, 2023, Section 2
  - [INCOMPLETE] Digital Personal Data Protection Rules, 2025, Rule 7 states: "7. Intimation of personal data breach. — (1) On becoming aware of any personal data breach, the Data Fiduciary shall, to the best of its knowledge, intimate to each affected Data Principal, in a concise, clear and plain manner and … — cites Digital Personal Data Protection Rules, 2025, Rule 7
  - [INCOMPLETE] Digital Personal Data Protection Rules, 2025, Rule 6 states: "6. Reasonable security safeguards. — (1) A Data Fiduciary shall protect personal data in its possession or under its control, including in respect of any processing undertaken by it or on its behalf by a Data Processor, by taking … — cites Digital Personal Data Protection Rules, 2025, Rule 6
  - [INCOMPLETE] The Digital Personal Data Protection Act, 2023, Section 2 states: "undivided family; (iii) a company; (iv) a firm; (v) an association of persons or a body of individuals, whether incorporated or not; (vi) the State; and (vii) every artificial juristic person, not falling within any of the preceding … — cites The Digital Personal Data Protection Act, 2023, Section 2
- **Uncertainty:** Whether patient/subscriber data has actually been accessed or exfiltrated is UNKNOWN at this stage. Data-protection obligations that depend on confirmed exposure must not be reported as triggered. / Obligation passages are quoted for review; exposure is only suspected, so whether they are triggered is not established.

## critical_infrastructure
- **Chunk:** scenario2_T2 — The slice supports a healthcare application and may carry identifiable patient information.
- **KB:** Critical Infrastructure KB (telecom_act_2023)
- **Passages retrieved:** 9

### Retrieval 1
- **Query:** notification of critical telecommunication infrastructure and measures for its protection
- **Source:** The Telecommunications Act, 2023 (Government of India (Ministry of Law and Justice, Legislative Department); India; Act)
- **Section:** Section 19 (p. 9)
- **Date issued:** 24th December, 2023 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.798; query terms in passage: measures, telecommunication
- **Chunk ID:** `telecom_act_2023:section-19:1`

> 19. The Central Government may notify standards and conformity assessment measures in respect of— (a) telecommunication equipment, telecommunication identifiers and telecommunication network; (b) telecommunication services, in consonance with any regulations notified by the Telecom Regulatory Authority of India from time to time; (c) manufacture, import, distribution and sale of telecommunication equipment; (d) telecommunication security, including identification, analysis and prevention of intrusion in telecommunication services and telecommunication networks; (e) cyber security for …

### Retrieval 2
- **Query:** notification of critical telecommunication infrastructure and measures for its protection
- **Source:** The Telecommunications Act, 2023 (Government of India (Ministry of Law and Justice, Legislative Department); India; Act)
- **Section:** Section 22 (p. 10-11)
- **Date issued:** 24th December, 2023 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.797; query terms in passage: critical, infrastructure, measures, notification, protection, telecommunication
- **Chunk ID:** `telecom_act_2023:section-22:1`

> 22. (1) The Central Government may by rules provide for the measures to protect and ensure cyber security of telecommunication networks and telecommunication services. (2) The measures may include collection, analysis and dissemination of traffic data that is generated, transmitted, received or stored in telecommunication networks. Explanation.—For the purposes of this sub-section, the expression "traffic data" means any data generated, transmitted, received or stored in telecommunication networks including data relating to the type, routing, duration or time of a telecommunication. (3) The …

### Retrieval 3
- **Query:** notification of critical telecommunication infrastructure and measures for its protection
- **Source:** The Telecommunications Act, 2023 (Government of India (Ministry of Law and Justice, Legislative Department); India; Act)
- **Section:** Section 21 (p. 10)
- **Date issued:** 24th December, 2023 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.793; query terms in passage: measures, notification, telecommunication
- **Chunk ID:** `telecom_act_2023:section-21:1`

> 21. The Central Government may, if satisfied that it is necessary or expedient so to do, in the interest of national security, friendly relations with foreign States, or in the event of war, by notification take such measures as are necessary in the circumstances of the case, including issuing directions in respect of the following, namely:— (a) use of telecommunication equipment, telecommunication services, telecommunication network and telecommunication identifiers; (b) standards applicable to manufacture, import and distribution of telecommunication equipment; (c) standards to be adopted …

### Structured agent output
- **Summary:** Critical infrastructure assessment: critical-service relevance indicated by the facts; formal CII designation unconfirmed. 4 provision(s) quoted from the Critical Infrastructure KB.
- **Claims:**
  - [UNSUPPORTED] The incident facts indicate that the affected 5G slice supports a healthcare application, so critical-infrastructure provisions are relevant to examine. Formal CII designation status is not established by the facts. — agent's reading of the facts
  - [INCOMPLETE] The Telecommunications Act, 2023, Section 19 states: "19. The Central Government may notify standards and conformity assessment measures in respect of— (a) telecommunication equipment, telecommunication identifiers and telecommunication network; (b) telecommunication services, in consonance with … — cites The Telecommunications Act, 2023, Section 19
  - [INCOMPLETE] The Telecommunications Act, 2023, Section 22 states: "22. (1) The Central Government may by rules provide for the measures to protect and ensure cyber security of telecommunication networks and telecommunication services. (2) The measures may include collection, analysis and dissemination of … — cites The Telecommunications Act, 2023, Section 22
  - [INCOMPLETE] The Telecommunications Act, 2023, Section 21 states: "21. The Central Government may, if satisfied that it is necessary or expedient so to do, in the interest of national security, friendly relations with foreign States, or in the event of war, by notification take such measures as are necessary in … — cites The Telecommunications Act, 2023, Section 21
  - [INCOMPLETE] The Telecommunications Act, 2023, Section 23 states: "23. If it appears necessary or expedient so to do in the public interest, the Central Government may direct any authorised entity to transmit in its telecommunication services or telecommunication network, specific messages, in such manner as … — cites The Telecommunications Act, 2023, Section 23
- **Uncertainty:** CII designation is UNCONFIRMED at this stage. The service may or may not be formally designated. This uncertainty must be carried through the assessment.

## standards
- **Chunk:** scenario2_T1 — Unusual authentication and signalling attempts are observed on the affected private 5G slice.
- **KB:** International Standards KB (3gpp_ts_23501, 3gpp_ts_33501, etsi_gr_nfv_sec_003, itu_t_y3172, nist_csf_2_0, nist_sp_800_61r3)
- **Passages retrieved:** 18

### Retrieval 1
- **Query:** Unusual authentication and signalling attempts are observed on the affected private 5G slice.
- **Source:** 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19 (3rd Generation Partnership Project (3GPP); International; Standard)
- **Section:** Clause B.1 — Introduction
- **Date issued:** 2026-06 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.718; query terms in passage: 5g, authentication, private
- **Chunk ID:** `3gpp_ts_33501:clause-b-1:1`

> The present annex describes an example of the usage of additional EAP methods for primary authentication in private networks using the 5G system as specified in TS 22.261 [7]. It is provided as an example on how the 5G authentication framework for primary authentication can be applied to EAP methods other than EAP-AKA' The additional EAP methods are only intended for private networks or with IoT devices in isolated deployment scenarios, i.e. roaming is not considered, as specified in TS 22.261 [7]. When the 5G system is deployed in private networks, the SUPI and SUCI should be encoded using …

### Retrieval 2
- **Query:** network slice isolation, quality of service and service level
- **Source:** 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19 (3rd Generation Partnership Project (3GPP); International; Standard)
- **Section:** Clause 5.15.1 — General
- **Date issued:** 2026-09 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.742; query terms in passage: network, service, slice
- **Chunk ID:** `3gpp_ts_23501:clause-5-15-1:5`

> as described in clause 5.15.13. The selection of N3IWF/TNGF supporting a set of slice(s) is described in clause 6.3.6 and clause 6.3.12 respectively. The support of Network Slice usage control is described in clause 5.15.15. Support of Optimized handling of temporarily available network slices is described in clause 5.15.16. It also covers aspects related to graceful release of network slices connectivity during slice decommissioning. The Partial Network Slice support in a Registration Area is described in clause 5.15.17. Support for Network Slices with Network Slice Area of Service not …

### Retrieval 3
- **Query:** primary authentication procedure and protection against signalling attacks
- **Source:** 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19 (3rd Generation Partnership Project (3GPP); International; Standard)
- **Section:** Clause 5.2.2 — User data and signalling data confidentiality
- **Date issued:** 2026-06 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.755; query terms in passage: protection, signalling
- **Chunk ID:** `3gpp_ts_33501:clause-5-2-2:1`

> The UE shall support ciphering of user data between the UE and the gNB. The UE shall activate ciphering of user data based on the indication sent by the gNB. The UE shall support ciphering of RRC and NAS-signalling. The UE shall implement the following ciphering algorithms: NEA0, 128-NEA1, 128-NEA2 as defined in Annex D of the present document. The UE may implement the following ciphering algorithm: 128-NEA3 as defined in Annex D of the present document. The UE shall implement the ciphering algorithms as specified in TS 33.401 [10] if it supports E-UTRA connected to 5GC. Confidentiality …

### Structured agent output
- **Summary:** Standards assessment: in scope for comparison — 3GPP TS 23.501, 3GPP TS 33.501, NIST SP 800-61 Rev. 3. 4 passage(s) quoted. All standards are reference points only, not Indian law.
- **Claims:**
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19, Clause B.1 states: "The present annex describes an example of the usage of additional EAP methods for primary authentication in private networks using the 5G system as … — cites 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19, Clause B.1
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.15.1 states: "as described in clause 5.15.13. The selection of N3IWF/TNGF supporting a set of slice(s) is described in clause 6.3.6 and clause 6.3.12 respectively. … — cites 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.15.1
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19, Clause 5.2.2 states: "The UE shall support ciphering of user data between the UE and the gNB. The UE shall activate ciphering of user data based on the indication sent … — cites 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19, Clause 5.2.2
  - [INCOMPLETE] [REFERENCE ONLY — not Indian law] NIST SP 800-61r3: Incident Response Recommendations and Considerations for Cybersecurity Risk Management (A CSF 2.0 Community Profile), Section 1 states: "access to network communications • Compromising a vendor’s software, which is subsequently distributed to … — cites NIST SP 800-61r3: Incident Response Recommendations and Considerations for Cybersecurity Risk Management (A CSF 2.0 Community Profile), Section 1

## policy_gap
- **Chunk:** scenario2_T3 — The question asks: what should be reported or escalated, and what policy gap remains?
- **KB:** International Policy Examples KB (ncsp_2013, ndcp_2018, trai_ai_bigdata_recs_2023)
- **Passages retrieved:** 22

### Retrieval 1
- **Query:** The question asks: what should be reported or escalated, and what policy gap remains?
- **Source:** National Digital Communications Policy 2018 (Government of India (Department of Telecommunications); India; Policy)
- **Section:** Para 8 (p. 3)
- **Date issued:** 2018 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.655; query terms in passage: policy
- **Chunk ID:** `ndcp_2018:para-8:1`

> 8. Improvement in regulation and ongoing structural reforms are the pillars of a sound policy initiative. Regulatory reform is not a one-off effort, but a dynamic, long-term and multidisciplinary process. The Policy recognises the importance of continued improvement in the regulatory framework for attracting investments and ensuring fair competition, to serve the needs of Indian citizens. Given the sector’s capital-intensive nature, the Policy aims to attract long-term, high quality and sustainable investments. To serve this objective, the Policy further aims to pursue regulatory reforms to …

### Retrieval 2
- **Query:** policy for 5G and next generation network technologies and their security
- **Source:** National Digital Communications Policy 2018 (Government of India (Department of Telecommunications); India; Policy)
- **Section:** Para 11 (p. 4-22)
- **Date issued:** 2018 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.758; query terms in passage: 5g, generation, network, next, policy, security, technologies
- **Chunk ID:** `ndcp_2018:para-11:20`

> services and network elements incorporating international best practices Earmarking adequate licensed and unlicensed spectrum for IoT/ M2M services Encourage use of Open APIs for emerging technologies (b) Promoting innovation in the creation of Communication services and network infrastructure by Developing a policy framework for ‘Over The Top’ services (c) Ensuring the Transition to IPv6 for all existing communications systems, equipment, networks and devices (d) Enabling Hi-speed internet, Internet of Things and M2M by rollout of 5G technologies: Implementing an action plan for rollout of …

### Retrieval 3
- **Query:** coordination between agencies for cyber security incident response
- **Source:** National Cyber Security Policy - 2013 (Government of India (Department of Electronics and Information Technology); India; Policy)
- **Section:** Part IV E — Creating mechanisms for security threat early warning, vulnerability management and (p. 6)
- **Date issued:** 2013 · **In force:** not verified · **Amendments checked:** False
- **Why relevant:** returned by the query above with cosine similarity 0.800; query terms in passage: coordination, cyber, response, security
- **Chunk ID:** `ncsp_2013:part-iv-e:2`

> all coordination and communication actions within the respective sectors for effective incidence response & resolution and cyber crisis management. To implement Cyber Crisis Management Plan for dealing with cyber related incidents impacting critical national processes or endangering public safety and security of the Nation, by way of well coordinated, multi disciplinary approach at the National, Sectoral as well as entity levels. To conduct and facilitate regular cyber security drills & exercises at National, sectoral and entity levels to enable assessment of the security posture and level of …

### Structured agent output
- **Summary:** Policy gap assessment: 3 candidate area(s) from verified findings; 3 potential gap(s) raised after Canonical KB examination. Potential gaps are for expert review, not conclusions of inadequacy.
- **Claims:**
  - [INCOMPLETE] Potential gap — Emerging technology not explicitly addressed: none of the 485 Indian passages in the Canonical KB (every one examined) mentions network slicing (instruments examined: CERT-In Directions under sub-section (6) of section 70B of the Information Technology Act, 2000 (28 April 2022); … — agent's reading of the facts
  - [INCOMPLETE] Potential gap — Overlapping requirements: CERT-In Directions under sub-section (6) of section 70B of the Information Technology Act, 2000 (28 April 2022), Direction (ii) and Digital Personal Data Protection Rules, 2025, Rule 7 both carry reporting duties for the same incident, and neither passage … — cites CERT-In Directions under sub-section (6) of section 70B of the Information Technology Act, 2000 (28 April 2022), Direction (ii); Digital Personal Data Protection Rules, 2025, Rule 7
  - [INCOMPLETE] Potential gap — Missing institutional clarity: National Cyber Security Policy - 2013, Part III item 5 addresses NCIIPC and National Digital Communications Policy 2018, Para 11 addresses CERT-In, but none of the 485 Indian passages in the Canonical KB addresses both, so which institution leads is … — cites National Cyber Security Policy - 2013, Part III item 5; National Digital Communications Policy 2018, Para 11
  - [INCOMPLETE] Comparator — [REFERENCE ONLY — not Indian law] 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.15.1 states: "as described in clause 5.15.13. The selection of N3IWF/TNGF supporting a set of slice(s) is described in clause 6.3.6 and clause 6.3.12 … — cites 3GPP TS 23.501 V19.9.0 (2026-09) System architecture for the 5G System (5GS), Release 19, Clause 5.15.1
  - [INCOMPLETE] Comparator — [REFERENCE ONLY — not Indian law] 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19, Clause 9.5 states: "This clause applies to all DIAMETER or GTP-based interfaces between the 5G Core and other network entities that are not part of the 5G … — cites 3GPP TS 33.501 V19.7.0 (2026-06) Security architecture and procedures for 5G system, Release 19, Clause 9.5
