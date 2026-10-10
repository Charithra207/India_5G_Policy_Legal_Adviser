# Y.3172 ML pipeline run — Security monitoring of the whole 5G core (all catalog incidents)

Run `core_security_full_20261009T185631Z` · intent `core_security_full` (intents/core_security_full.yaml) · policy node in **blocking** mode

> Contained lab: the network is the Python simulation in `sim/`; nothing reaches a real system. Decision support, not legal advice.

## Summary

| measure | value |
|---|---|
| intent id | core_security_full |
| policy mode | blocking |
| ticks | 34 |
| initial model | iforest_rf |
| final model | iforest_rf |
| live accuracy | 1.000 |
| live macro f1 | 1.000 |
| live detection f1 | 1.000 |
| false alarm ticks | 0 |
| missed ticks | 0 |
| incidents dispatched | 5 |
| incidents correctly classified | 5 |
| remediations applied on wrong classification | 0 |
| attacks injected | 4 |
| attacks detected within deadline | 4 |
| mean detection delay ticks | 0.000 |
| deadline ticks | 1 |
| reselections | 0 |
| notices drafted | 16 |
| escalations | 2 |
| sandbox validation passed | 13 |
| sandbox validation total | 13 |
| mean inference ms | 20.642 |
| adviser knowledge bases | stubs — vector stores not built here (python -m src.rag.build); agents report no passages |

## 1. Pipeline instantiated by the MLFO from the ML Intent

Chain: SRC → C → PP → M → P → D → SINK · 152 features · levels used: AN, CN, management

| node | id | level | detail |
|---|---|---|---|
| SRC | `src:gnb` | AN | metrics, logs, ran, transport |
| SRC | `src:amf` | CN | metrics, health, logs, devices |
| SRC | `src:smf` | CN | metrics, health, logs, integrity, slices, services |
| SRC | `src:upf` | CN | metrics, health, logs, user_plane, egress |
| SRC | `src:ausf` | CN | logs, auth |
| SRC | `src:udm` | CN | metrics, logs, sba, subscribers |
| SRC | `src:nef` | CN | metrics, logs, sba |
| SRC | `src:nrf` | CN | logs, registry |
| SRC | `src:oam` | management | logs, alerts, oam |
| C | `collector` | CN |  |
| PP | `preprocessor` | CN |  |
| M | `model` | CN | threshold_centroid, iforest_rf |
| P | `policy_node` | management | blocking |
| D | `distributor` | management |  |
| SINK | `sink:evidence_preservation` | management |  |
| SINK | `sink:remediation` | CN |  |
| SINK | `sink:regulatory_notices` | management |  |
| SINK | `sink:escalation` | management |  |

Reference points (Y.3172 Figure 4):

- **4** — ML underlay network (live simulation) ↔ ML pipeline: collector reads diagnostics; SINKs act
- **1,2** — simulated ML underlay networks ↔ ML pipeline in the sandbox subsystem
- **3** — ML sandbox subsystem ↔ ML pipeline subsystem: trained model handed over at deployment
- **5** — management subsystem (MLFO) ↔ ML pipeline subsystem: instantiation, model updates
- **6** — management subsystem (MLFO) ↔ ML sandbox subsystem: training, evaluation, selection
- **7** — MLFO ↔ other management functions: the incident-response engine (ir/engine.py) and its human gates

## 2.1 ML sandbox — training and model selection (initial)

900 labelled samples (630 train / 270 held out, split by episode), background load [0.8, 1.2], 152 features. Rule: highest macro_f1 among candidates with macro_f1 ≥ 0.85 and p95 inference ≤ 80.0 ms.

| candidate | macro-F1 | detection F1 | false-alarm rate | p95 inference ms | meets intent |
|---|---|---|---|---|---|
| `threshold_centroid` | 0.8685 | 0.8607 | 0.5729 | 0.058 | yes |
| `iforest_rf` **(selected)** | 0.9855 | 0.9855 | 0.0104 | 42.407 | yes |

Most important features of the selected model: `ausf.auth.subscriber_keys_compromised` (0.0521), `oam.oam.exposed_to_internet` (0.041), `nrf.registry.signed_profiles_not_required` (0.0328), `gnb.transport.interfaces_without_ipsec` (0.0323), `gnb.transport.up_integrity_off` (0.0311), `oam.oam.default_credentials` (0.0283)

## 3. Sandbox evaluation of effects on the network (before live use)

| incident | detected as | confidence | playbook resolved it | tier | after remediation |
|---|---|---|---|---|---|
| signalling_storm_amf | signalling_storm_amf ✔ | 0.993 | yes | basic | signalling_storm_amf |
| core_ddos_upf | core_ddos_upf ✔ | 0.993 | yes | basic | core_ddos_upf |
| rogue_base_station | rogue_base_station ✔ | 1.0 | yes | intermediate | normal |
| subscriber_cred_compromise | subscriber_cred_compromise ✔ | 0.907 | yes | advanced | normal |
| sba_api_abuse_nef | sba_api_abuse_nef ✔ | 1.0 | yes | intermediate | normal |
| subscriber_data_exfiltration | subscriber_data_exfiltration ✔ | 1.0 | yes | intermediate | normal |
| nf_host_ransomware | nf_host_ransomware ✔ | 0.993 | yes | advanced | normal |
| exposed_mgmt_interface | exposed_mgmt_interface ✔ | 0.96 | yes | intermediate | normal |
| n2_n3_mitm | n2_n3_mitm ✔ | 0.98 | yes | intermediate | normal |
| supply_chain_rogue_nf | supply_chain_rogue_nf ✔ | 1.0 | yes | advanced | supply_chain_rogue_nf |
| subscriber_profile_tampering | subscriber_profile_tampering ✔ | 0.967 | yes | advanced | normal |
| gtpu_spoofing_upf | gtpu_spoofing_upf ✔ | 1.0 | yes | intermediate | normal |
| iot_botnet_mmtc | iot_botnet_mmtc ✔ | 1.0 | yes | advanced | normal |

## 4. Live operation

| tick | clock | events | prediction (confidence) | truth | model | action |
|---|---|---|---|---|---|---|
| 0 | 09:02 |  | normal (0.847) | normal | iforest_rf |  |
| 1 | 09:03 |  | normal (0.88) | normal | iforest_rf |  |
| 2 | 09:04 |  | normal (0.84) | normal | iforest_rf |  |
| 3 | 09:05 | benign event: maintenance_window | normal (0.753) | normal | iforest_rf |  |
| 4 | 09:06 |  | normal (0.753) | normal | iforest_rf |  |
| 5 | 09:07 |  | normal (0.7) | normal | iforest_rf |  |
| 6 | 09:09 | attack injected: rogue_base_station; benign event ended: maintenance_window | rogue_base_station (0.893) | rogue_base_station | iforest_rf | core_security_full_20261009T185631Z-INC001: P=hold_for_approval; remediation=resolved |
| 7 | 09:10 |  | normal (0.713) | normal | iforest_rf |  |
| 8 | 09:11 |  | normal (0.753) | normal | iforest_rf |  |
| 9 | 09:12 |  | normal (0.733) | normal | iforest_rf |  |
| 10 | 09:13 |  | normal (0.76) | normal | iforest_rf |  |
| 11 | 09:14 |  | normal (0.767) | normal | iforest_rf |  |
| 12 | 09:16 | attack injected: subscriber_data_exfiltration | subscriber_data_exfiltration (0.907) | subscriber_data_exfiltration | iforest_rf | core_security_full_20261009T185631Z-INC002: P=hold_for_approval; remediation=resolved |
| 13 | 09:17 |  | normal (0.72) | normal | iforest_rf |  |
| 14 | 09:18 |  | normal (0.773) | normal | iforest_rf |  |
| 15 | 09:19 |  | normal (0.673) | normal | iforest_rf |  |
| 16 | 09:20 |  | normal (0.753) | normal | iforest_rf |  |
| 17 | 09:21 |  | normal (0.727) | normal | iforest_rf |  |
| 18 | 09:22 | benign event: flash_crowd | normal (0.74) | normal | iforest_rf |  |
| 19 | 09:23 |  | normal (0.747) | normal | iforest_rf |  |
| 20 | 09:24 |  | normal (0.76) | normal | iforest_rf |  |
| 21 | 09:25 | benign event ended: flash_crowd | normal (0.72) | normal | iforest_rf |  |
| 22 | 09:27 | attack injected: supply_chain_rogue_nf | supply_chain_rogue_nf (0.887) | supply_chain_rogue_nf | iforest_rf | core_security_full_20261009T185631Z-INC003: P=hold_for_approval; remediation=resolved |
| 23 | 09:28 |  | supply_chain_rogue_nf (0.84) | contained:supply_chain_rogue_nf | iforest_rf | resolved incident still observed (contained) — not re-dispatched |
| 24 | 09:29 |  | supply_chain_rogue_nf (0.8) | contained:supply_chain_rogue_nf | iforest_rf | resolved incident still observed (contained) — not re-dispatched |
| 25 | 09:30 |  | supply_chain_rogue_nf (0.827) | contained:supply_chain_rogue_nf | iforest_rf | resolved incident still observed (contained) — not re-dispatched |
| 26 | 09:31 |  | supply_chain_rogue_nf (0.813) | contained:supply_chain_rogue_nf | iforest_rf | resolved incident still observed (contained) — not re-dispatched |
| 27 | 09:32 |  | supply_chain_rogue_nf (0.767) | contained:supply_chain_rogue_nf | iforest_rf | resolved incident still observed (contained) — not re-dispatched |
| 28 | 09:34 | attack injected: nf_host_ransomware | nf_host_ransomware (0.573) | nf_host_ransomware | iforest_rf | core_security_full_20261009T185631Z-INC004: P=escalate; remediation=escalate |
| 29 | 09:35 |  | nf_host_ransomware (0.547) | nf_host_ransomware | iforest_rf | duplicate of an incident handled in the last ticks — not re-dispatched |
| 30 | 09:36 |  | nf_host_ransomware (0.553) | nf_host_ransomware | iforest_rf | duplicate of an incident handled in the last ticks — not re-dispatched |
| 31 | 09:37 |  | nf_host_ransomware (0.553) | nf_host_ransomware | iforest_rf | duplicate of an incident handled in the last ticks — not re-dispatched |
| 32 | 09:38 |  | nf_host_ransomware (0.54) | nf_host_ransomware | iforest_rf | duplicate of an incident handled in the last ticks — not re-dispatched |
| 33 | 09:39 |  | nf_host_ransomware (0.547) | nf_host_ransomware | iforest_rf | core_security_full_20261009T185631Z-INC005: P=escalate; remediation=escalate |

## 5. Incidents

### core_security_full_20261009T185631Z-INC001 — rogue_base_station at 2026-10-07T09:09:00

- Model `iforest_rf`, confidence 0.8933; lab truth `rogue_base_station` (correct); detection delay 0 tick(s)
- P node: **hold_for_approval** (blocking) — rules: blocking_mode_human_approval, preserve_logs_before_changes
  - Blocking mode: remediation is held until a human approves it, having seen the obligations below.
  - Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).
- Why the model flagged it: `gnb.metrics.fallback_to_lte_ues` = 38.0 (normal ≈ 0.0); `gnb.metrics.radio_link_failures` = 12.0 (normal ≈ 0.0); `Δgnb.ran.unknown_neighbours` = 1.0 (normal ≈ -0.022); `oam.alerts.new_alerts` = 1.0 (normal ≈ 0.0)

| obligation | source (checked word for word) |
|---|---|
| Report the cyber incident to CERT-In within 6 hours of noticing it | CERT-In_Directions_70B_28.04.2022.pdf, p. 2 |
| Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require | cybersecurity-rules-2024.pdf, pp. 12–13 |
| Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request | CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3 |
| Telecommunications Act, 2023 s.22 — measures to protect and ensure the cyber security of telecommunication networks and services | new-telecom-Act-2023.pdf, p. 10 |

Specialist agents (cybersecurity, policy_legal, standards, technical): 7 claims; verifier outcomes {'UNSUPPORTED': 7}; Coordinator: {'evidence_backed_conclusions': 0, 'uncertain_conclusions': 7, 'conflicting_findings': 0, 'potential_policy_gaps': 0}.

SINKs:

- **evidence_preservation**: preserved — 10 files hashed before any change
- **remediation**: resolved — resolved after tiers ['basic', 'intermediate']; gates: [('intermediate', 'agent')]
- **regulatory_notices**: drafted — 3 draft notices, 1 preservation actions
  - Central Government (Department of Telecommunications): Report of the security incident with relevant details of the affected system and a descrip… — deadline **2026-10-07T15:09:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - Central Government (Department of Telecommunications): Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which … — deadline **2026-10-08T09:09:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - CERT-In (incident@cert-in.org.in): Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)… — deadline **2026-10-07T15:09:00** — DRAFT — requires human review and sign-off; not sent (verified in CERT-In_Directions_70B_28.04.2022.pdf, p. 2)
  - action: Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling 180 days, within Indian jurisdiction); provide them to CERT-In with the incident report or on request (verified in CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3)

### core_security_full_20261009T185631Z-INC002 — subscriber_data_exfiltration at 2026-10-07T09:16:00

- Model `iforest_rf`, confidence 0.9067; lab truth `subscriber_data_exfiltration` (correct); detection delay 0 tick(s)
- P node: **hold_for_approval** (blocking) — rules: blocking_mode_human_approval, preserve_logs_before_changes
  - Blocking mode: remediation is held until a human approves it, having seen the obligations below.
  - Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).
- Why the model flagged it: `udm.metrics.offered_rate` = 1537.0 (normal ≈ 44.433); `udm.metrics.accepted_rate` = 1537.0 (normal ≈ 44.433); `udm.metrics.cpu` = 100.0 (normal ≈ 17.71); `Δudm.metrics.bulk_reads_active` = 1.0 (normal ≈ -0.036)

| obligation | source (checked word for word) |
|---|---|
| Report the cyber incident to CERT-In within 6 hours of noticing it | CERT-In_Directions_70B_28.04.2022.pdf, p. 2 |
| Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require | cybersecurity-rules-2024.pdf, pp. 12–13 |
| DPDP Act, 2023 s.8(6) — on a personal data breach, intimate the Data Protection Board and each affected Data Principal | 2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf, p. 7 |
| DPDP Rules, 2025 rule 7 — detailed intimation to the Board within seventy-two hours of becoming aware of the breach | 53450e6e5dc0bfa85ebd78686cadad39.pdf, pp. 26–27 |
| Commencement notification G.S.R. 843(E), 13 Nov 2025 — the breach-intimation provisions (ss. 3-17 incl. s.8) come into force eighteen months after publication | c56ceae6c383460ca69577428d36828b.pdf, pp. 1–2 |
| Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request | CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3 |

Specialist agents (cybersecurity, policy_legal, privacy, standards, technical): 10 claims; verifier outcomes {'UNSUPPORTED': 10}; Coordinator: {'evidence_backed_conclusions': 0, 'uncertain_conclusions': 10, 'conflicting_findings': 0, 'potential_policy_gaps': 0}.

SINKs:

- **evidence_preservation**: preserved — 10 files hashed before any change
- **remediation**: resolved — resolved after tiers ['basic', 'intermediate']; gates: [('intermediate', 'agent')]
- **regulatory_notices**: drafted — 6 draft notices, 1 preservation actions
  - Central Government (Department of Telecommunications): Report of the security incident with relevant details of the affected system and a descrip… — deadline **2026-10-07T15:16:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - Central Government (Department of Telecommunications): Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which … — deadline **2026-10-08T09:16:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - CERT-In (incident@cert-in.org.in): Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)… — deadline **2026-10-07T15:16:00** — DRAFT — requires human review and sign-off; not sent (verified in CERT-In_Directions_70B_28.04.2022.pdf, p. 2)
  - Each affected Data Principal: Description of the breach, likely consequences, mitigation, safety measures and a contact… — deadline **without delay** — PREPAREDNESS DRAFT — duty not yet in force on the incident date (verified in 53450e6e5dc0bfa85ebd78686cadad39.pdf, p. 26)
  - Data Protection Board of India: Without delay: description of the breach — nature, extent, timing, location, likely impact… — deadline **without delay** — PREPAREDNESS DRAFT — duty not yet in force on the incident date (verified in 53450e6e5dc0bfa85ebd78686cadad39.pdf, pp. 26–27)
  - Data Protection Board of India: Updated and detailed information, facts and reasons, mitigation, findings about the person… — deadline **2026-10-10T09:16:00** — PREPAREDNESS DRAFT — duty not yet in force on the incident date (verified in 53450e6e5dc0bfa85ebd78686cadad39.pdf, pp. 26–27)
  - action: Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling 180 days, within Indian jurisdiction); provide them to CERT-In with the incident report or on request (verified in CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3)

### core_security_full_20261009T185631Z-INC003 — supply_chain_rogue_nf at 2026-10-07T09:27:00

- Model `iforest_rf`, confidence 0.8867; lab truth `supply_chain_rogue_nf` (correct); detection delay 0 tick(s)
- P node: **hold_for_approval** (blocking) — rules: blocking_mode_human_approval, preserve_logs_before_changes
  - Blocking mode: remediation is held until a human approves it, having seen the obligations below.
  - Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).
- Why the model flagged it: `Δudm.metrics.bulk_reads_active` = 1.0 (normal ≈ -0.036); `Δudm.sba.bulk_readers` = 1.0 (normal ≈ -0.036); `udm.metrics.accepted_rate` = 85.0 (normal ≈ 44.433); `udm.metrics.offered_rate` = 85.0 (normal ≈ 44.433)

| obligation | source (checked word for word) |
|---|---|
| Report the cyber incident to CERT-In within 6 hours of noticing it | CERT-In_Directions_70B_28.04.2022.pdf, p. 2 |
| Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require | cybersecurity-rules-2024.pdf, pp. 12–13 |
| If the affected network is notified as Critical Telecommunication Infrastructure, follow the CTI Rules, 2024 incident-reporting timelines | Critical Telecommunication Infrastructure Rules, 2024_0.pdf, pp. 7–8 |
| Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request | CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3 |
| DPDP Act, 2023 s.8(6) — on a personal data breach, intimate the Data Protection Board and each affected Data Principal | 2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf, p. 7 |
| DPDP Rules, 2025 rule 7 — detailed intimation to the Board within seventy-two hours of becoming aware of the breach | 53450e6e5dc0bfa85ebd78686cadad39.pdf, pp. 26–27 |
| Commencement notification G.S.R. 843(E), 13 Nov 2025 — the breach-intimation provisions (ss. 3-17 incl. s.8) come into force eighteen months after publication | c56ceae6c383460ca69577428d36828b.pdf, pp. 1–2 |

Specialist agents (cybersecurity, policy_legal, privacy, standards, technical): 9 claims; verifier outcomes {'UNSUPPORTED': 9}; Coordinator: {'evidence_backed_conclusions': 0, 'uncertain_conclusions': 9, 'conflicting_findings': 0, 'potential_policy_gaps': 0}.

SINKs:

- **evidence_preservation**: preserved — 10 files hashed before any change
- **remediation**: resolved — resolved after tiers ['basic', 'intermediate', 'advanced']; gates: [('intermediate', 'agent'), ('advanced', 'agent')]
- **regulatory_notices**: drafted — 7 draft notices, 1 preservation actions
  - Central Government (Department of Telecommunications): Report of the security incident with relevant details of the affected system and a descrip… — deadline **2026-10-07T15:27:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - Central Government (Department of Telecommunications): Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which … — deadline **2026-10-08T09:27:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - CERT-In (incident@cert-in.org.in): Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)… — deadline **2026-10-07T15:27:00** — DRAFT — requires human review and sign-off; not sent (verified in CERT-In_Directions_70B_28.04.2022.pdf, p. 2)
  - Central Government (Critical Telecommunication Infrastructure): Intimation of the security incident in the form and manner specified on the portal… — deadline **2026-10-07T15:27:00** — CONDITIONAL DRAFT — only if the affected element is notified as Critical Telecommunication Infrastructure (verified in Critical Telecommunication Infrastructure Rules, 2024_0.pdf, p. 8)
  - Each affected Data Principal: Description of the breach, likely consequences, mitigation, safety measures and a contact… — deadline **without delay** — PREPAREDNESS DRAFT — duty not yet in force on the incident date (verified in 53450e6e5dc0bfa85ebd78686cadad39.pdf, p. 26)
  - Data Protection Board of India: Without delay: description of the breach — nature, extent, timing, location, likely impact… — deadline **without delay** — PREPAREDNESS DRAFT — duty not yet in force on the incident date (verified in 53450e6e5dc0bfa85ebd78686cadad39.pdf, pp. 26–27)
  - Data Protection Board of India: Updated and detailed information, facts and reasons, mitigation, findings about the person… — deadline **2026-10-10T09:27:00** — PREPAREDNESS DRAFT — duty not yet in force on the incident date (verified in 53450e6e5dc0bfa85ebd78686cadad39.pdf, pp. 26–27)
  - action: Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling 180 days, within Indian jurisdiction); provide them to CERT-In with the incident report or on request (verified in CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3)

### core_security_full_20261009T185631Z-INC004 — nf_host_ransomware at 2026-10-07T09:34:00

- Model `iforest_rf`, confidence 0.5733; lab truth `nf_host_ransomware` (correct); detection delay 0 tick(s)
- P node: **escalate** (blocking) — rules: low_confidence_to_human
  - Confidence 0.57 is below the intent's minimum 0.60; no automated action is taken.
- Why the model flagged it: `smf.health.state` = 3.0 (normal ≈ 0.0); `Δsmf.metrics.active_pdu_sessions` = -1200.0 (normal ≈ 32.143); `Δsmf.metrics.cpu` = -17.0 (normal ≈ 0.473); `Δsmf.integrity.files_encrypted` = 1.0 (normal ≈ -0.027)

SINKs:

- **escalation**: escalated — Confidence 0.57 is below the intent's minimum 0.60; no automated action is taken.

### core_security_full_20261009T185631Z-INC005 — nf_host_ransomware at 2026-10-07T09:39:00

- Model `iforest_rf`, confidence 0.5467; lab truth `nf_host_ransomware` (correct); detection delay — tick(s)
- P node: **escalate** (blocking) — rules: low_confidence_to_human
  - Confidence 0.55 is below the intent's minimum 0.60; no automated action is taken.
- Why the model flagged it: `smf.health.state` = 3.0 (normal ≈ 0.0); `smf.metrics.active_pdu_sessions` = 0.0 (normal ≈ 1157.143); `smf.metrics.cpu` = 0.0 (normal ≈ 16.723); `udm.metrics.accepted_rate` = 91.0 (normal ≈ 44.433)

SINKs:

- **escalation**: escalated — Confidence 0.55 is below the intent's minimum 0.60; no automated action is taken.

## 6. Monitoring and re-selection

Rolling window 10 ticks; minimum accuracy 0.75.
- No re-selection was needed.

## 7. Y.3172 mapping

| Y.3172 component | clause | implementation |
|---|---|---|
| ML Intent | cl. 7.4, 8.1 NOTE 12 | intents/*.yaml, src/y3172/intent.py |
| SRC | cl. 8.1 | simulated NFs (sim/engine.py) via read-only diagnostics |
| C (collector) | cl. 8.1 | src/y3172/nodes.py Collector |
| PP (preprocessor) | cl. 8.1 | src/y3172/nodes.py Preprocessor |
| M (model) | cl. 8.1 | src/y3172/models.py (threshold_centroid, iforest_rf) |
| P (policy) | cl. 8.1 NOTE 5 | src/y3172/policy_node.py + the specialist-agent swarm (src/) |
| D (distributor) | cl. 8.1 | src/y3172/distributor.py |
| SINK | cl. 8.1 | remediation (ir/engine.py), notices, evidence, escalation |
| MLFO | cl. 3.2.2, 8.1, 8.2 | src/y3172/mlfo.py |
| ML sandbox + simulated underlay | cl. 3.2.6, 8.2 | sim/datagen.py, sandbox simulations in the run folder |
| ML underlay network | cl. 3.2.7 | live simulation in the run folder (contained; not a real network) |

Audit trail (hash-chained): `core_security_full_20261009T185631Z.jsonl`.

_Simulated network and incidents; legal obligations are shown with their sources for a qualified person to review. Not legal advice._
