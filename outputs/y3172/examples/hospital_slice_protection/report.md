# Y.3172 ML pipeline run — Protect the hospital slice (URLLC) and its portal

Run `hospital_slice_protection_20261009T185626Z` · intent `hospital_slice_protection` (intents/hospital_slice_protection.yaml) · policy node in **advisory** mode

> Contained lab: the network is the Python simulation in `sim/`; nothing reaches a real system. Decision support, not legal advice.

## Summary

| measure | value |
|---|---|
| intent id | hospital_slice_protection |
| policy mode | advisory |
| ticks | 24 |
| initial model | iforest_rf |
| final model | iforest_rf |
| live accuracy | 1.000 |
| live macro f1 | 1.000 |
| live detection f1 | 1.000 |
| false alarm ticks | 0 |
| missed ticks | 0 |
| incidents dispatched | 2 |
| incidents correctly classified | 2 |
| remediations applied on wrong classification | 0 |
| attacks injected | 2 |
| attacks detected within deadline | 2 |
| mean detection delay ticks | 0.000 |
| deadline ticks | 1 |
| reselections | 0 |
| notices drafted | 8 |
| escalations | 0 |
| sandbox validation passed | 4 |
| sandbox validation total | 4 |
| mean inference ms | 21.979 |
| adviser knowledge bases | stubs — vector stores not built here (python -m src.rag.build); agents report no passages |

## 1. Pipeline instantiated by the MLFO from the ML Intent

Chain: SRC → C → PP → M → P → D → SINK · 76 features · levels used: CN, management

| node | id | level | detail |
|---|---|---|---|
| SRC | `src:amf` | CN | metrics, logs, devices |
| SRC | `src:smf` | CN | metrics, logs, slices, services |
| SRC | `src:upf` | CN | metrics, health, logs, user_plane |
| SRC | `src:udm` | CN | metrics, logs, subscribers |
| SRC | `src:oam` | management | alerts, oam |
| C | `collector` | CN |  |
| PP | `preprocessor` | CN |  |
| M | `model` | CN | threshold_centroid, iforest_rf |
| P | `policy_node` | management | advisory |
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

540 labelled samples (378 train / 162 held out, split by episode), background load [0.8, 1.2], 76 features. Rule: highest macro_f1 among candidates with macro_f1 ≥ 0.85 and p95 inference ≤ 80.0 ms.

| candidate | macro-F1 | detection F1 | false-alarm rate | p95 inference ms | meets intent |
|---|---|---|---|---|---|
| `threshold_centroid` | 0.8804 | 0.8939 | 0.2125 | 0.036 | yes |
| `iforest_rf` **(selected)** | 0.9781 | 0.975 | 0.0 | 22.965 | yes |

Most important features of the selected model: `upf.user_plane.source_validation_off` (0.0781), `upf.metrics.cpu` (0.0768), `upf.metrics.offered_rate` (0.0722), `smf.slices.sessions_not_on_allow_list` (0.0689), `upf.user_plane.flows_to_internal_ranges` (0.0654), `amf.devices.unblocked_c2_destinations` (0.0646)

## 3. Sandbox evaluation of effects on the network (before live use)

| incident | detected as | confidence | playbook resolved it | tier | after remediation |
|---|---|---|---|---|---|
| iot_botnet_mmtc | iot_botnet_mmtc ✔ | 1.0 | yes | advanced | normal |
| subscriber_profile_tampering | subscriber_profile_tampering ✔ | 1.0 | yes | advanced | normal |
| gtpu_spoofing_upf | gtpu_spoofing_upf ✔ | 0.993 | yes | intermediate | normal |
| core_ddos_upf | core_ddos_upf ✔ | 1.0 | yes | basic | core_ddos_upf |

## 4. Live operation

| tick | clock | events | prediction (confidence) | truth | model | action |
|---|---|---|---|---|---|---|
| 0 | 09:02 |  | normal (0.893) | normal | iforest_rf |  |
| 1 | 09:03 |  | normal (0.973) | normal | iforest_rf |  |
| 2 | 09:04 |  | normal (0.973) | normal | iforest_rf |  |
| 3 | 09:05 | benign event: billing_batch | normal (0.98) | normal | iforest_rf |  |
| 4 | 09:06 |  | normal (0.947) | normal | iforest_rf |  |
| 5 | 09:07 |  | normal (0.973) | normal | iforest_rf |  |
| 6 | 09:08 | benign event ended: billing_batch | normal (0.887) | normal | iforest_rf |  |
| 7 | 09:10 | attack injected: iot_botnet_mmtc | iot_botnet_mmtc (0.987) | iot_botnet_mmtc | iforest_rf | hospital_slice_protection_20261009T185626Z-INC001: P=proceed_annotated; remediation=resolved |
| 8 | 09:11 |  | normal (0.953) | normal | iforest_rf |  |
| 9 | 09:12 |  | normal (1.0) | normal | iforest_rf |  |
| 10 | 09:13 |  | normal (0.907) | normal | iforest_rf |  |
| 11 | 09:14 |  | normal (0.993) | normal | iforest_rf |  |
| 12 | 09:15 |  | normal (0.88) | normal | iforest_rf |  |
| 13 | 09:16 | benign event: maintenance_window | normal (0.933) | normal | iforest_rf |  |
| 14 | 09:17 |  | normal (0.847) | normal | iforest_rf |  |
| 15 | 09:18 |  | normal (0.933) | normal | iforest_rf |  |
| 16 | 09:19 | benign event ended: maintenance_window | normal (0.96) | normal | iforest_rf |  |
| 17 | 09:21 | attack injected: subscriber_profile_tampering | subscriber_profile_tampering (0.993) | subscriber_profile_tampering | iforest_rf | hospital_slice_protection_20261009T185626Z-INC002: P=proceed_annotated; remediation=resolved |
| 18 | 09:22 |  | normal (0.84) | normal | iforest_rf |  |
| 19 | 09:23 |  | normal (0.96) | normal | iforest_rf |  |
| 20 | 09:24 |  | normal (0.967) | normal | iforest_rf |  |
| 21 | 09:25 |  | normal (0.953) | normal | iforest_rf |  |
| 22 | 09:26 |  | normal (0.953) | normal | iforest_rf |  |
| 23 | 09:27 |  | normal (0.94) | normal | iforest_rf |  |

## 5. Incidents

### hospital_slice_protection_20261009T185626Z-INC001 — iot_botnet_mmtc at 2026-10-07T09:10:00

- Model `iforest_rf`, confidence 0.9867; lab truth `iot_botnet_mmtc` (correct); detection delay 0 tick(s)
- P node: **proceed_annotated** (advisory) — rules: advisory_mode_annotate, preserve_logs_before_changes
  - Advisory mode: remediation proceeds through the incident-response gates; the obligations are attached for the operator.
  - Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).
- Why the model flagged it: `amf.devices.anomalous_devices` = 24.0 (normal ≈ 0.0); `smf.services.hospital_portal_latency_ms` = 366.0 (normal ≈ 37.474); `Δamf.devices.unblocked_c2_destinations` = 1.0 (normal ≈ -0.047); `Δsmf.services.hospital_portal_degraded` = 1.0 (normal ≈ -0.037)

| obligation | source (checked word for word) |
|---|---|
| Report the cyber incident to CERT-In within 6 hours of noticing it | CERT-In_Directions_70B_28.04.2022.pdf, p. 2 |
| Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require | cybersecurity-rules-2024.pdf, pp. 12–13 |
| If the affected network is notified as Critical Telecommunication Infrastructure, follow the CTI Rules, 2024 incident-reporting timelines | Critical Telecommunication Infrastructure Rules, 2024_0.pdf, pp. 7–8 |
| Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request | CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3 |
| Telecommunications Act, 2023 s.22 — measures to protect and ensure the cyber security of telecommunication networks and services | new-telecom-Act-2023.pdf, p. 10 |

Specialist agents (critical_infrastructure, cybersecurity, policy_legal, standards, technical): 9 claims; verifier outcomes {'UNSUPPORTED': 9}; Coordinator: {'evidence_backed_conclusions': 0, 'uncertain_conclusions': 9, 'conflicting_findings': 0, 'potential_policy_gaps': 0}.

SINKs:

- **evidence_preservation**: preserved — 10 files hashed before any change
- **remediation**: resolved — resolved after tiers ['basic', 'intermediate', 'advanced']; gates: [('intermediate', 'agent'), ('advanced', 'agent')]
- **regulatory_notices**: drafted — 4 draft notices, 1 preservation actions
  - Central Government (Department of Telecommunications): Report of the security incident with relevant details of the affected system and a descrip… — deadline **2026-10-07T15:10:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - Central Government (Department of Telecommunications): Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which … — deadline **2026-10-08T09:10:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - CERT-In (incident@cert-in.org.in): Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)… — deadline **2026-10-07T15:10:00** — DRAFT — requires human review and sign-off; not sent (verified in CERT-In_Directions_70B_28.04.2022.pdf, p. 2)
  - Central Government (Critical Telecommunication Infrastructure): Intimation of the security incident in the form and manner specified on the portal… — deadline **2026-10-07T15:10:00** — CONDITIONAL DRAFT — only if the affected element is notified as Critical Telecommunication Infrastructure (verified in Critical Telecommunication Infrastructure Rules, 2024_0.pdf, p. 8)
  - action: Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling 180 days, within Indian jurisdiction); provide them to CERT-In with the incident report or on request (verified in CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3)

### hospital_slice_protection_20261009T185626Z-INC002 — subscriber_profile_tampering at 2026-10-07T09:21:00

- Model `iforest_rf`, confidence 0.9933; lab truth `subscriber_profile_tampering` (correct); detection delay 0 tick(s)
- P node: **proceed_annotated** (advisory) — rules: advisory_mode_annotate, preserve_logs_before_changes
  - Advisory mode: remediation proceeds through the incident-response gates; the obligations are attached for the operator.
  - Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).
- Why the model flagged it: `Δudm.subscribers.unreverted_profile_changes` = 1.0 (normal ≈ -0.063); `Δsmf.slices.sessions_not_on_allow_list` = 1.0 (normal ≈ -0.068); `Δoam.oam.default_credentials` = 1.0 (normal ≈ -0.074); `oam.alerts.new_alerts` = 1.0 (normal ≈ 0.0)

| obligation | source (checked word for word) |
|---|---|
| Report the cyber incident to CERT-In within 6 hours of noticing it | CERT-In_Directions_70B_28.04.2022.pdf, p. 2 |
| Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require | cybersecurity-rules-2024.pdf, pp. 12–13 |
| If the affected network is notified as Critical Telecommunication Infrastructure, follow the CTI Rules, 2024 incident-reporting timelines | Critical Telecommunication Infrastructure Rules, 2024_0.pdf, pp. 7–8 |
| Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request | CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3 |
| Telecommunications Act, 2023 s.22 — measures to protect and ensure the cyber security of telecommunication networks and services | new-telecom-Act-2023.pdf, p. 10 |

Specialist agents (critical_infrastructure, cybersecurity, policy_legal, privacy, standards, technical): 12 claims; verifier outcomes {'UNSUPPORTED': 12}; Coordinator: {'evidence_backed_conclusions': 0, 'uncertain_conclusions': 12, 'conflicting_findings': 0, 'potential_policy_gaps': 0}.

SINKs:

- **evidence_preservation**: preserved — 10 files hashed before any change
- **remediation**: resolved — resolved after tiers ['basic', 'intermediate', 'advanced']; gates: [('intermediate', 'agent'), ('advanced', 'agent')]
- **regulatory_notices**: drafted — 4 draft notices, 1 preservation actions
  - Central Government (Department of Telecommunications): Report of the security incident with relevant details of the affected system and a descrip… — deadline **2026-10-07T15:21:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - Central Government (Department of Telecommunications): Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which … — deadline **2026-10-08T09:21:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - CERT-In (incident@cert-in.org.in): Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)… — deadline **2026-10-07T15:21:00** — DRAFT — requires human review and sign-off; not sent (verified in CERT-In_Directions_70B_28.04.2022.pdf, p. 2)
  - Central Government (Critical Telecommunication Infrastructure): Intimation of the security incident in the form and manner specified on the portal… — deadline **2026-10-07T15:21:00** — CONDITIONAL DRAFT — only if the affected element is notified as Critical Telecommunication Infrastructure (verified in Critical Telecommunication Infrastructure Rules, 2024_0.pdf, p. 8)
  - action: Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling 180 days, within Indian jurisdiction); provide them to CERT-In with the incident report or on request (verified in CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3)

## 6. Monitoring and re-selection

Rolling window 8 ticks; minimum accuracy 0.75.
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

Audit trail (hash-chained): `hospital_slice_protection_20261009T185626Z.jsonl`.

_Simulated network and incidents; legal obligations are shown with their sources for a qualified person to review. Not legal advice._
