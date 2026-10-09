# Policy-gap register — 5G incidents (India and comparators)

> Potential gaps and regulatory ambiguities identified for expert review. No conclusion of policy failure is drawn; international material is a reference point, not Indian law.

Generated 2026-10-09T20:30:58+00:00 by `python -m src.gap.register` from `knowledge_base/policy_gap/gap_themes.yaml`. Anchors: 17 verified, 0 phrase not found, 5 pending: document not in corpus, 2 listed for comparison. Pending anchors become verified when their document is added (`knowledge_base/ADDING_SOURCES.md`) and the knowledge bases are rebuilt.

| id | domain | potential gap | category | status |
|---|---|---|---|---|
| G1 | Incident reporting and escalation | Parallel incident-reporting clocks with no single reporting channel | overlapping requirements | partly evidenced potential gap |
| G2 | Logging, retention and data minimisation | Different log-retention periods for the same incident logs | overlapping requirements | partly evidenced potential gap |
| G3 | Critical infrastructure designation | Two routes to "critical" status for telecom networks and services | missing institutional clarity | evidence-backed potential gap |
| G4 | Network slicing and private 5G | Network slicing for critical services is not named in the instruments examined | emerging technology not explicitly addressed | evidence-backed potential gap |
| G5 | AI in network operations | Human oversight of AI-driven network remediation | emerging technology not explicitly addressed | evidence-backed potential gap |

## G1 — Parallel incident-reporting clocks with no single reporting channel

**Domain:** Incident reporting and escalation · **Category:** overlapping requirements · **Status:** partly evidenced potential gap

**Why it matters.** One 5G security incident that touches personal data and a critical service can start several reporting clocks at once, to different recipients, counted from different moments (becoming aware, noticing, occurrence).

**Coordination problem.** The passages below set reporting duties to the Central Government (DoT), CERT-In, the CTI portal and the Data Protection Board. None of the quoted passages provides a single submission that satisfies all of them, or says which report takes precedence when their contents differ.

**Objectives in tension.** Speed of reporting vs. accuracy and consistency of what is reported.

**Indian provisions**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| ✔ Telecom Cyber Security Rules, 2024, rule 7(1)(a) | India | Report to the Central Government within 6 hours of becoming aware | verified — telecom_cyber_security_rules_2024, Rule 7, p. 12-13<br>“7. Reporting of security incidents. — (1) The telecommunication entity shall– (a) within six hours of becoming aware of a security incident affecting its telecommunication network or telecommunication service, report the same to the Central Government with relevant details of the affected system including the description of such incident; and (b) within twe…” |
| ✔ CERT-In Directions (28.04.2022), direction (ii) | India | Report to CERT-In within 6 hours of noticing | verified — certin_directions_2022, Direction (ii), p. 2<br>“(ii) Any service provider, intermediary, data centre, body corporate and Government organisation shall mandatorily report cyber incidents as mentioned in Annexure I to CERT-In within 6 hours of noticing such incidents or being brought to notice about such incidents. The incidents can be reported to CERT-In via email (incident@cert-in.org.in), Phone (1800- 11-4949) and Fax (1800-11-6969). The details regarding methods and formats of r…” |
| ✔ CTI Rules, 2024, rule 7(1)(j) | India | Intimation for CTI within 6 hours of occurrence | verified — cti_rules_2024, Rule 7, p. 8-9<br>“…standard operating procedures for security incident response systems, including disaster recovery and business continuity; (j) implement mechanisms to ensure intimation of security incident(s) to the Central Government, no later than six hours of occurrence of such incident, in the form and manner as may be specified on the portal; and (k) maintain a risk register including a graded risk assessment associated with different elements of Critical Telecommunication Infrastructure within its n…” |
| ✔ DPDP Rules, 2025, rule 7(2)(b) | India | Detailed intimation to the Data Protection Board within 72 hours | verified — dpdp_rules_2025, Rule 7, p. 26<br>“the Board, — (a) without delay, a description of the breach, including its nature, extent, timing and location of occurrence and the likely impact; (b) within seventy-two hours of becoming aware of the breach, or within such longer period as the Board may allow on a request made in writing in this behalf, — (i) updated and detailed information in respect of such description; (ii) the broad facts related to the events, circum…” |

**Global examples**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| … EU NIS2 Directive (EU) 2022/2555, Art. 23(4)(a) | European Union | Staged reporting (early warning, notification, final report) to one CSIRT or competent authority | pending: document not in corpus |
| … EU GDPR (EU) 2016/679, Art. 33(1) | European Union | Personal-data breach notification to the supervisory authority within 72 hours | pending: document not in corpus |

**Neighbouring-region examples**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| · Sri Lanka Personal Data Protection Act, No. 9 of 2022 | Sri Lanka | Personal-data breach duties in a neighbouring jurisdiction — add the Act and a phrase to compare | listed for comparison |

**Link to the Y.3172 pipeline.** The regulatory-notice SINK of the Y.3172 pipeline (src/y3172/notices.py) drafts each of these notices with its own deadline, which makes the parallel clocks visible on every incident.

**Questions for expert review**

- Can one incident report be filed once and shared between DoT, CERT-In and (where applicable) the Board?
- When "becoming aware", "noticing" and "occurrence" differ, which time should operators record?

## G2 — Different log-retention periods for the same incident logs

**Domain:** Logging, retention and data minimisation · **Category:** overlapping requirements · **Status:** partly evidenced potential gap

**Why it matters.** Incident logs from a 5G core contain traffic data and personal data; the quoted passages set different minimum retention periods for logs.

**Coordination problem.** CERT-In asks for a rolling 180 days within Indian jurisdiction; the DPDP Rules ask a Data Fiduciary to retain logs of processing for at least one year. The quoted passages do not say how the two periods relate for logs that fall under both.

**Objectives in tension.** Forensic availability of logs vs. data minimisation and storage limitation.

**Indian provisions**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| ✔ CERT-In Directions (28.04.2022), direction (iv) | India | ICT logs kept for a rolling 180 days, within India | verified — certin_directions_2022, Direction (iv), p. 3<br>“(iv) All service providers, intermediaries, data centres, body corporate and Government organisations shall mandatorily enable logs of all their ICT systems and maintain them securely for a rolling period of 180 days and the same shall be maintained within the Indian jurisdiction. These should be provided to CERT-In along with reporting of any incident or when ordered / directed by CERT-In.” |
| ✔ DPDP Rules, 2025 — retention of personal data, traffic data and logs of processing | India | Personal data, traffic data and logs of processing retained for at least one year | verified — dpdp_rules_2025, Rule 8, p. 27<br>“…) and (2), a Data Fiduciary shall retain, in respect of any processing of personal data undertaken by it or on its behalf by a Data Processor, such personal data, associated traffic data and other logs of the processing for a minimum period of one year from the date of such processing, for the purposes as specified in the Seventh Schedule, after which the Data Fiduciary shall cause such personal data and logs to be erased, unless further retention is required for comp…” |
| ✔ Telecom Cyber Security Rules, 2024 — data the Central Government may seek | India | The Central Government may seek traffic data from a telecommunication entity | verified — telecom_cyber_security_rules_2024, Rule 3, p. 9-10<br>“…nd analysis of data. — (1) The Central Government, or any agency authorised by the Central Government, may, for the purposes of protecting and ensuring telecom cyber security, — (a) seek from a telecommunication entity, traffic data and any other data, other than content of messages, in the form and manner as may be specified by the Central Government on the portal; and (b) direct a telecommunication entity to establish necessary infrastructure and equipment for collection and provision of such dat…” |

**Global examples**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| … EU GDPR (EU) 2016/679, Art. 5(1)(e) | European Union | Storage limitation principle | pending: document not in corpus |

**Link to the Y.3172 pipeline.** The evidence-preservation SINK hashes the live network's logs before any change; how long such evidence may or must be kept is exactly the question above.

**Questions for expert review**

- For logs that are both ICT logs (CERT-In) and logs of personal-data processing (DPDP), which period governs?

## G3 — Two routes to "critical" status for telecom networks and services

**Domain:** Critical infrastructure designation · **Category:** missing institutional clarity · **Status:** evidence-backed potential gap

**Why it matters.** A private 5G slice carrying hospital traffic may be critical in fact but not notified; which designation applies decides which reporting timeline and which institution leads.

**Coordination problem.** The Telecommunications Act lets the Central Government notify Critical Telecommunication Infrastructure (DoT/CTI Rules), while NCIIPC designates Critical Information Infrastructure under the IT Act. The quoted passages do not set out how an operator learns which applies to a given slice.

**Objectives in tension.** Sector-specific control by the telecom department vs. a national CII protection regime.

**Indian provisions**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| ✔ Telecommunications Act, 2023, s.22(3) | India | Notification of Critical Telecommunication Infrastructure | verified — telecom_act_2023, Section 22, p. 10-11<br>“…ansmitted, received or stored in telecommunication networks including data relating to the type, routing, duration or time of a telecommunication. (3) The Central Government may, by notification in the Official Gazette, declare any telecommunication network, or part thereof, as Critical Telecommunication Infrastructure, disruption of which shall have debilitating impact on national security, economy, public health or safety. (4) The Central Government may by rules provide for the standards, security practices, upgradation requirements…” |
| ✔ CTI Rules, 2024 — definition of Critical Telecommunication Infrastructure | India | CTI means a network notified under s.22(3) | verified — cti_rules_2024, Rule 2, p. 7<br>“…communication Security Officer appointed under rule 6 of the Telecommunications (Telecom Cyber Security) Rules, 2024; (c) “Critical Telecommunication Infrastructure” means any telecommunication network, or part thereof, notified under sub-section (3) of section 22 of the Act; (d) “portal” means the portal notified by the Central Government under sub-rule(1) of rule 10; (e) “security incident” shall have the same meaning assigned to it in clause (f) of sub-rule (1) of rule 2 of the Telecommu…” |
| ✔ TRAI consultation paper on privacy, security and ownership of data (2017) — context, not law | India | NCIIPC's role as described by TRAI | verified — Consultation_Paper _on_Privacy_Security_ownership_of_data_09082017_0.pdf, p. 14-17<br>“…ational security, governance, economy and social well being of the nation. Keeping in view the critical rule of the telecommunications sector, the National Critical Information Infrastructure Protection Centre (NCIIPC), the agency mandated to facilitate the protection of critical infrastructure, has designated this to be one of the CIIs. 14 Chapter III Stakeholders: Digital Eco System 3.1 While the aforementioned conditions of privacy, confidentiality and security discussed” |

**Global examples**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| … EU NIS2 Directive (EU) 2022/2555, Art. 3 | European Union | Size- and sector-based classification of entities, with one competent authority per sector | pending: document not in corpus |
| ✔ ENISA, 5G Cybersecurity Standards (2022) | European Union | EU 5G Toolbox risk assessment of suppliers for critical networks | verified — enisa_5g_cybersecurity_standards_2022, SO 2 - Governance and risk management, p. 53-54<br>“…he list of identified risks aligned with the main risks for 5G networks identified in the Coordinated risk assessment? Report RM ENISATL All except opensource community Are threats related to the exposure to potentially high-risk suppliers or managed service providers, including those residing in other jurisdictions, taken in consideration? RM ISOIECSUPL Telecom Need to be implemented according to Member States’ provisions Build and Run Has a potential dependency on a single supplier…” |

**Neighbouring-region examples**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| · Bangladesh Cyber Security Act, 2023 (critical information infrastructure) | Bangladesh | CII designation in a neighbouring jurisdiction — add the Act and a phrase to compare | listed for comparison |

**Link to the Y.3172 pipeline.** The CTI notice drafted by the Y.3172 notice SINK is marked CONDITIONAL because the pipeline cannot know whether the affected slice is notified.

**Questions for expert review**

- Is a hospital's private 5G slice within CTI, CII, both or neither until notified?

## G4 — Network slicing for critical services is not named in the instruments examined

**Domain:** Network slicing and private 5G · **Category:** emerging technology not explicitly addressed · **Status:** evidence-backed potential gap

**Why it matters.** Slices share physical infrastructure; isolation failures and slice- specific authentication are recognised 5G threats in the reference material, while the Indian passages quoted address networks as a whole.

**Coordination problem.** Whether slice isolation, slice-specific authentication or an enterprise slice's security is the operator's or the enterprise's responsibility is not addressed in the passages quoted. (The Policy Gap Agent checks the whole Indian Canonical KB for the word before raising this; see its "Emerging technology" result in a scenario run.)

**Objectives in tension.** Flexible, sliced service offers vs. clear security accountability per slice.

**Indian provisions**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| ✔ Telecommunications Act, 2023, s.22(3) | India | Instruments refer to networks 'or part thereof', without naming slices | verified — telecom_act_2023, Section 22, p. 10-11<br>“…eceived or stored in telecommunication networks including data relating to the type, routing, duration or time of a telecommunication. (3) The Central Government may, by notification in the Official Gazette, declare any telecommunication network, or part thereof, as Critical Telecommunication Infrastructure, disruption of which shall have debilitating impact on national security, economy, public health or safety. (4) The Central Government may by rules provide for the standards…” |

**Global examples**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| ✔ ENISA Threat Landscape for 5G Networks (2020) | European Union | Slice isolation identified as a security expectation and threat area | verified — ENISA 5G Threat Landscape - Update.pdf, p. 31-32<br>“…horisation Identifier that enables network-slice-specific authentication and authorisation mechanisms to complement network-side authentication mechanisms. Related component(s): Network Slice Instance Resource isolation One of key expectations of network slicing is resources isolation. Each slice may be perceived as isolated set of resources configured through the network environment and providing defined set of functions. Level and strength of isolation may vary depending on requirements and usage s…” |
| ✔ ENISA, 5G Cybersecurity Standards (2022) | European Union | Slice-as-a-service providers named as a distinct actor | verified — enisa_5g_cybersecurity_standards_2022, Section 2.1.3, p. 14-16<br>“…s. Examples include communication service providers offering traditional telecom services, digital service providers offering digital services such as enhanced mobile broadband and IoT to various vertical industries, or network slice as a service (NSaaS) providers offering a network slice along with the services that it may support and configure. • Virtualisation infrastructure service providers (VISP): entities that provide virtualised infrastructure services a…” |

**Link to the Y.3172 pipeline.** The hospital-slice intent (intents/hospital_slice_protection.yaml) monitors sessions outside the slice allow-list — a control the quoted Indian passages do not mention.

**Questions for expert review**

- Should slice-level security responsibilities be stated in authorisation conditions or rules?

## G5 — Human oversight of AI-driven network remediation

**Domain:** AI in network operations · **Category:** emerging technology not explicitly addressed · **Status:** evidence-backed potential gap

**Why it matters.** ML models increasingly detect incidents and propose (or apply) network changes. ITU-T Y.3172's policy node can be advisory or blocking; the Sandbox India register lists "policy-node enforcement semantics (advisory vs blocking)" as having no India-specific instrument.

**Coordination problem.** The Indian passages quoted are principles and recommendations, not binding rules on when an automated network action needs human approval or how such decisions are recorded.

**Objectives in tension.** Speed of automated response vs. accountability and the risk of acting on a false positive.

**Indian provisions**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| ✔ NITI Aayog, Responsible AI (Part 1, 2021) — principle, not law | India | Human intervention for consequential decisions | verified — Responsible-AI-22022021.pdf, p. 25-26<br>“…stem. General lack of awareness could also lead to over-dependence due to false or exaggerated belief in such technologies (automation bias) and may further aggravate the problem.21 A typical approach towards this is to introduce a human intervention whenever such consequential decisions are made. 20. https://www.reuters.com/article/us-amazon-com-jobs-automation-insight/amazon-scraps-secret-ai-recruiting-tool- that-showed-bias-against-women-idUSKCN1MK08G 21. https://doi.org/10.2514/6.2004-6313 17 The Issue Its I…” |
| ✔ TRAI Recommendations on Leveraging AI and Big Data in Telecom (2023) — recommendation, not law | India | Proposed AI regulator for the sector | verified — trai_ai_bigdata_recs_2023, Para 2.79, p. 42-43<br>“…recommendation-ethics-artificial-intelligence statutory authority should be established immediately for ensuring development of responsible AI and regulation of use cases in India. The authority should be designated as “Artificial Intelligence and Data Authority of India” (AIDAI). 2.80” |

**Global examples**

| instrument | jurisdiction | what it does | check |
|---|---|---|---|
| … EU AI Act (EU) 2024/1689, Art. 14(1) | European Union | Human oversight of high-risk AI, including safety components of critical digital infrastructure (Annex III) | pending: document not in corpus |
| ✔ NIST AI Risk Management Framework 1.0, MAP 3.5 | United States | Documented human-oversight processes | verified — NIST.AI.100-1.pdf, p. 32-33<br>“…zation. MAP 3.4: Processes for operator and practitioner proficiency with AI system performance and trustworthiness – and relevant technical standards and certifications – are defined, assessed, and documented. MAP 3.5: Processes for human oversight are defined, assessed, and documented in accordance with organizational policies from the GOVERN function. MAP 4: Risks and benefits are mapped for all components of the AI system including third-party software and data. MAP 4.1: Approaches for mapping AI t…” |

**Link to the Y.3172 pipeline.** The project's P node implements both modes; the recorded runs show what auto-approval of false positives does (outputs/y3172/examples/amf_signalling_storm) and what operator review prevents (outputs/y3172/examples/amf_signalling_storm_operator_review).

**Questions for expert review**

- Which automated network actions, if any, should be allowed without prior human approval?

_Decision support; not legal advice._
