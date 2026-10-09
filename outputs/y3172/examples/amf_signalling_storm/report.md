# Y.3172 ML pipeline run — Detect and contain signalling storms on the AMF

Run `amf_signalling_storm_20261009T185618Z` · intent `amf_signalling_storm` (intents/amf_signalling_storm.yaml) · policy node in **blocking** mode

> Contained lab: the network is the Python simulation in `sim/`; nothing reaches a real system. Decision support, not legal advice.

## Summary

| measure | value |
|---|---|
| intent id | amf_signalling_storm |
| policy mode | blocking |
| ticks | 26 |
| initial model | iforest_rf |
| final model | iforest_rf |
| live accuracy | 0.885 |
| live macro f1 | 0.578 |
| live detection f1 | 0.571 |
| false alarm ticks | 3 |
| missed ticks | 0 |
| incidents dispatched | 3 |
| incidents correctly classified | 1 |
| remediations applied on wrong classification | 2 |
| attacks injected | 1 |
| attacks detected within deadline | 1 |
| mean detection delay ticks | 0.000 |
| deadline ticks | 1 |
| reselections | 1 |
| notices drafted | 12 |
| escalations | 0 |
| sandbox validation passed | 3 |
| sandbox validation total | 3 |
| mean inference ms | 20.227 |
| adviser knowledge bases | stubs — vector stores not built here (python -m src.rag.build); agents report no passages |

## 1. Pipeline instantiated by the MLFO from the ML Intent

Chain: SRC → C → PP → M → P → D → SINK · 52 features · levels used: AN, CN, management

| node | id | level | detail |
|---|---|---|---|
| SRC | `src:amf` | CN | metrics, health, logs |
| SRC | `src:gnb` | AN | metrics, logs, ran |
| SRC | `src:upf` | CN | metrics, health, logs |
| SRC | `src:oam` | management | alerts |
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

450 labelled samples (312 train / 138 held out, split by episode), background load [0.8, 1.2], 52 features. Rule: highest macro_f1 among candidates with macro_f1 ≥ 0.85 and p95 inference ≤ 80.0 ms.

| candidate | macro-F1 | detection F1 | false-alarm rate | p95 inference ms | meets intent |
|---|---|---|---|---|---|
| `threshold_centroid` | 0.8858 | 0.965 | 0.0 | 0.057 | yes |
| `iforest_rf` **(selected)** | 0.978 | 0.9793 | 0.0 | 28.885 | yes |

Most important features of the selected model: `upf.metrics.accepted_rate` (0.0916), `upf.metrics.cpu` (0.0881), `amf.metrics.cpu` (0.0845), `gnb.ran.unknown_neighbours` (0.0834), `upf.metrics.offered_rate` (0.0815), `amf.metrics.accepted_rate` (0.0771)

## 2.2 ML sandbox — training and model selection (monitoring: rolling accuracy 0.625 below 0.75 at tick 14)

450 labelled samples (312 train / 138 held out, split by episode), background load [0.8, 5.46], 52 features. Rule: highest macro_f1 among candidates with macro_f1 ≥ 0.85 and p95 inference ≤ 80.0 ms.

| candidate | macro-F1 | detection F1 | false-alarm rate | p95 inference ms | meets intent |
|---|---|---|---|---|---|
| `threshold_centroid` | 0.8728 | 0.9583 | 0.0156 | 0.106 | yes |
| `iforest_rf` **(selected)** | 0.9679 | 0.966 | 0.0312 | 27.526 | yes |

Most important features of the selected model: `upf.metrics.offered_rate` (0.1202), `upf.metrics.accepted_rate` (0.1197), `gnb.metrics.radio_link_failures` (0.0845), `amf.metrics.accepted_rate` (0.0771), `gnb.metrics.fallback_to_lte_ues` (0.0725), `amf.metrics.offered_rate` (0.0656)

## 3. Sandbox evaluation of effects on the network (before live use)

| incident | detected as | confidence | playbook resolved it | tier | after remediation |
|---|---|---|---|---|---|
| signalling_storm_amf | signalling_storm_amf ✔ | 1.0 | yes | basic | signalling_storm_amf |
| rogue_base_station | rogue_base_station ✔ | 1.0 | yes | intermediate | normal |
| core_ddos_upf | core_ddos_upf ✔ | 1.0 | yes | basic | core_ddos_upf |

## 4. Live operation

| tick | clock | events | prediction (confidence) | truth | model | action |
|---|---|---|---|---|---|---|
| 0 | 09:02 |  | normal (1.0) | normal | iforest_rf |  |
| 1 | 09:03 |  | normal (1.0) | normal | iforest_rf |  |
| 2 | 09:04 |  | normal (0.98) | normal | iforest_rf |  |
| 3 | 09:05 | benign event: flash_crowd | normal (1.0) | normal | iforest_rf |  |
| 4 | 09:06 |  | normal (0.98) | normal | iforest_rf |  |
| 5 | 09:07 |  | normal (0.993) | normal | iforest_rf |  |
| 6 | 09:08 | benign event ended: flash_crowd | normal (1.0) | normal | iforest_rf |  |
| 7 | 09:09 | load drift: background load ×5.0 | signalling_storm_amf (0.947) ✘ | normal | iforest_rf | amf_signalling_storm_20261009T185618Z-INC001: P=hold_for_approval; remediation=resolved |
| 8 | 09:10 |  | normal (0.92) | normal | iforest_rf |  |
| 9 | 09:11 |  | normal (0.987) | normal | iforest_rf |  |
| 10 | 09:12 |  | normal (0.98) | normal | iforest_rf |  |
| 11 | 09:13 |  | normal (0.673) | normal | iforest_rf |  |
| 12 | 09:14 |  | normal (0.667) | normal | iforest_rf |  |
| 13 | 09:15 |  | core_ddos_upf (0.973) ✘ | normal | iforest_rf | amf_signalling_storm_20261009T185618Z-INC002: P=hold_for_approval; remediation=resolved |
| 14 | 09:16 |  | core_ddos_upf (0.653) ✘ | normal | iforest_rf | duplicate of an incident handled in the last ticks — not re-dispatched |
| 15 | 09:17 |  | normal (0.907) | normal | iforest_rf |  |
| 16 | 09:18 |  | normal (0.96) | normal | iforest_rf |  |
| 17 | 09:19 |  | normal (0.893) | normal | iforest_rf |  |
| 18 | 09:21 | attack injected: signalling_storm_amf | signalling_storm_amf (0.993) | signalling_storm_amf | iforest_rf | amf_signalling_storm_20261009T185618Z-INC003: P=hold_for_approval; remediation=resolved |
| 19 | 09:22 |  | signalling_storm_amf (0.813) | contained:signalling_storm_amf | iforest_rf | resolved incident still observed (contained) — not re-dispatched |
| 20 | 09:23 |  | normal (0.593) | contained:signalling_storm_amf | iforest_rf |  |
| 21 | 09:24 |  | normal (0.587) | contained:signalling_storm_amf | iforest_rf |  |
| 22 | 09:25 |  | normal (0.527) | contained:signalling_storm_amf | iforest_rf |  |
| 23 | 09:26 |  | normal (0.62) | contained:signalling_storm_amf | iforest_rf |  |
| 24 | 09:27 |  | normal (0.62) | contained:signalling_storm_amf | iforest_rf |  |
| 25 | 09:28 |  | normal (0.593) | contained:signalling_storm_amf | iforest_rf |  |

## 5. Incidents

### amf_signalling_storm_20261009T185618Z-INC001 — signalling_storm_amf at 2026-10-07T09:09:00

- Model `iforest_rf`, confidence 0.9467; lab truth `normal` (WRONG); detection delay — tick(s)
- P node: **hold_for_approval** (blocking) — rules: blocking_mode_human_approval, preserve_logs_before_changes
  - Blocking mode: remediation is held until a human approves it, having seen the obligations below.
  - Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).
- ⚠ **The classification was wrong and its playbook was still applied** (the operator approved it). Check what it changed below; this is what blocking mode and the operator's review exist to prevent.
- Why the model flagged it: `amf.metrics.offered_rate` = 659.0 (normal ≈ 163.87); `amf.metrics.accepted_rate` = 659.0 (normal ≈ 163.87); `Δamf.metrics.cpu` = 34.0 (normal ≈ 0.808)

| obligation | source (checked word for word) |
|---|---|
| Report the cyber incident to CERT-In within 6 hours of noticing it | CERT-In_Directions_70B_28.04.2022.pdf, p. 2 |
| Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require | cybersecurity-rules-2024.pdf, pp. 12–13 |
| If the affected network is notified as Critical Telecommunication Infrastructure, follow the CTI Rules, 2024 incident-reporting timelines | Critical Telecommunication Infrastructure Rules, 2024_0.pdf, pp. 7–8 |
| Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request | CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3 |
| Telecommunications Act, 2023 s.22 — measures to protect and ensure the cyber security of telecommunication networks and services | new-telecom-Act-2023.pdf, p. 10 |

Specialist agents (cybersecurity, policy_legal, standards, technical): 8 claims; verifier outcomes {'UNSUPPORTED': 8}; Coordinator: {'evidence_backed_conclusions': 0, 'uncertain_conclusions': 8, 'conflicting_findings': 0, 'potential_policy_gaps': 0}.

SINKs:

- **evidence_preservation**: preserved — 10 files hashed before any change
- **remediation**: resolved — resolved after tiers ['basic']; gates: []
- **regulatory_notices**: drafted — 4 draft notices, 1 preservation actions
  - Central Government (Department of Telecommunications): Report of the security incident with relevant details of the affected system and a descrip… — deadline **2026-10-07T15:09:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - Central Government (Department of Telecommunications): Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which … — deadline **2026-10-08T09:09:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - CERT-In (incident@cert-in.org.in): Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)… — deadline **2026-10-07T15:09:00** — DRAFT — requires human review and sign-off; not sent (verified in CERT-In_Directions_70B_28.04.2022.pdf, p. 2)
  - Central Government (Critical Telecommunication Infrastructure): Intimation of the security incident in the form and manner specified on the portal… — deadline **2026-10-07T15:09:00** — CONDITIONAL DRAFT — only if the affected element is notified as Critical Telecommunication Infrastructure (verified in Critical Telecommunication Infrastructure Rules, 2024_0.pdf, p. 8)
  - action: Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling 180 days, within Indian jurisdiction); provide them to CERT-In with the incident report or on request (verified in CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3)

### amf_signalling_storm_20261009T185618Z-INC002 — core_ddos_upf at 2026-10-07T09:15:00

- Model `iforest_rf`, confidence 0.9733; lab truth `normal` (WRONG); detection delay — tick(s)
- P node: **hold_for_approval** (blocking) — rules: blocking_mode_human_approval, preserve_logs_before_changes
  - Blocking mode: remediation is held until a human approves it, having seen the obligations below.
  - Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).
- ⚠ **The classification was wrong and its playbook was still applied** (the operator approved it). Check what it changed below; this is what blocking mode and the operator's review exist to prevent.
- Why the model flagged it: `upf.metrics.accepted_rate` = 2006.0 (normal ≈ 590.815); `upf.metrics.offered_rate` = 2006.0 (normal ≈ 590.815); `upf.metrics.cpu` = 100.0 (normal ≈ 39.671); `Δupf.health.state` = 1.0 (normal ≈ 0.0)

| obligation | source (checked word for word) |
|---|---|
| Report the cyber incident to CERT-In within 6 hours of noticing it | CERT-In_Directions_70B_28.04.2022.pdf, p. 2 |
| Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require | cybersecurity-rules-2024.pdf, pp. 12–13 |
| If the affected network is notified as Critical Telecommunication Infrastructure, follow the CTI Rules, 2024 incident-reporting timelines | Critical Telecommunication Infrastructure Rules, 2024_0.pdf, pp. 7–8 |
| Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request | CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3 |

Specialist agents (critical_infrastructure, cybersecurity, policy_legal, privacy, standards, technical): 11 claims; verifier outcomes {'UNSUPPORTED': 11}; Coordinator: {'evidence_backed_conclusions': 0, 'uncertain_conclusions': 11, 'conflicting_findings': 0, 'potential_policy_gaps': 0}.

SINKs:

- **evidence_preservation**: preserved — 10 files hashed before any change
- **remediation**: resolved — resolved after tiers ['basic']; gates: []
- **regulatory_notices**: drafted — 4 draft notices, 1 preservation actions
  - Central Government (Department of Telecommunications): Report of the security incident with relevant details of the affected system and a descrip… — deadline **2026-10-07T15:15:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - Central Government (Department of Telecommunications): Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which … — deadline **2026-10-08T09:15:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - CERT-In (incident@cert-in.org.in): Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)… — deadline **2026-10-07T15:15:00** — DRAFT — requires human review and sign-off; not sent (verified in CERT-In_Directions_70B_28.04.2022.pdf, p. 2)
  - Central Government (Critical Telecommunication Infrastructure): Intimation of the security incident in the form and manner specified on the portal… — deadline **2026-10-07T15:15:00** — CONDITIONAL DRAFT — only if the affected element is notified as Critical Telecommunication Infrastructure (verified in Critical Telecommunication Infrastructure Rules, 2024_0.pdf, p. 8)
  - action: Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling 180 days, within Indian jurisdiction); provide them to CERT-In with the incident report or on request (verified in CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3)

### amf_signalling_storm_20261009T185618Z-INC003 — signalling_storm_amf at 2026-10-07T09:21:00

- Model `iforest_rf`, confidence 0.9933; lab truth `signalling_storm_amf` (correct); detection delay 0 tick(s)
- P node: **hold_for_approval** (blocking) — rules: blocking_mode_human_approval, preserve_logs_before_changes
  - Blocking mode: remediation is held until a human approves it, having seen the obligations below.
  - Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).
- Why the model flagged it: `amf.metrics.registration_failure_pct` = 86.3 (normal ≈ 0.0); `Δamf.metrics.offered_rate` = 8700.0 (normal ≈ 16.027); `Δamf.metrics.accepted_rate` = 8700.0 (normal ≈ 16.027); `Δamf.metrics.cpu` = 81.0 (normal ≈ 1.548)

| obligation | source (checked word for word) |
|---|---|
| Report the cyber incident to CERT-In within 6 hours of noticing it | CERT-In_Directions_70B_28.04.2022.pdf, p. 2 |
| Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require | cybersecurity-rules-2024.pdf, pp. 12–13 |
| If the affected network is notified as Critical Telecommunication Infrastructure, follow the CTI Rules, 2024 incident-reporting timelines | Critical Telecommunication Infrastructure Rules, 2024_0.pdf, pp. 7–8 |
| Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request | CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3 |
| Telecommunications Act, 2023 s.22 — measures to protect and ensure the cyber security of telecommunication networks and services | new-telecom-Act-2023.pdf, p. 10 |

Specialist agents (cybersecurity, policy_legal, standards, technical): 8 claims; verifier outcomes {'UNSUPPORTED': 8}; Coordinator: {'evidence_backed_conclusions': 0, 'uncertain_conclusions': 8, 'conflicting_findings': 0, 'potential_policy_gaps': 0}.

SINKs:

- **evidence_preservation**: preserved — 10 files hashed before any change
- **remediation**: resolved — resolved after tiers ['basic']; gates: []
- **regulatory_notices**: drafted — 4 draft notices, 1 preservation actions
  - Central Government (Department of Telecommunications): Report of the security incident with relevant details of the affected system and a descrip… — deadline **2026-10-07T15:21:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - Central Government (Department of Telecommunications): Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which … — deadline **2026-10-08T09:21:00** — DRAFT — requires human review and sign-off; not sent (verified in cybersecurity-rules-2024.pdf, pp. 12–13)
  - CERT-In (incident@cert-in.org.in): Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)… — deadline **2026-10-07T15:21:00** — DRAFT — requires human review and sign-off; not sent (verified in CERT-In_Directions_70B_28.04.2022.pdf, p. 2)
  - Central Government (Critical Telecommunication Infrastructure): Intimation of the security incident in the form and manner specified on the portal… — deadline **2026-10-07T15:21:00** — CONDITIONAL DRAFT — only if the affected element is notified as Critical Telecommunication Infrastructure (verified in Critical Telecommunication Infrastructure Rules, 2024_0.pdf, p. 8)
  - action: Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling 180 days, within Indian jurisdiction); provide them to CERT-In with the incident report or on request (verified in CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3)

## 6. Monitoring and re-selection

Rolling window 8 ticks; minimum accuracy 0.75.
- Tick 14: rolling score {'accuracy': 0.625, 'macro_f1': 0.2564, 'detection_f1': 0.0, 'false_alarms': 3, 'missed': 0, 'n': 8} → sandbox re-calibrated (estimated live background load 4.37), retrained on load [0.8, 5.46]; `iforest_rf` → `iforest_rf`.

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

Audit trail (hash-chained): `amf_signalling_storm_20261009T185618Z.jsonl`.

_Simulated network and incidents; legal obligations are shown with their sources for a qualified person to review. Not legal advice._
