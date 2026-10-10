# Incident report — Signalling storm (registration flood)

- Attack id: `signalling_storm_amf` (simulated, contained lab)
- Outcome: **RESOLVED** in the basic tier
- Provider: offline

## Timeline

| time | tier | actor | action | approved | result / note |
|---|---|---|---|---|---|
| 01:56:35 | start | system | `inject` {"attack": "signalling_storm_amf"} |  | {"alerts": ["AMF CPU above 90% for 3 consecutive ticks; legitimate registrations failing"]}  |
| 01:56:37 | basic | agent | `get_alerts`  |  | {"alerts": ["AMF CPU above 90% for 3 consecutive ticks; legitimate registrations failing"]} b1_alerts: Read the active alerts to confirm what the monitoring saw |
| 01:56:37 | basic | agent | `get_nf_health` {"nf": "amf"} |  | {"amf": "degraded"} b2_health: Check AMF health (ok / degraded / down) |
| 01:56:37 | basic | agent | `get_metrics` {"nf": "amf"} |  | {"cpu": 100, "offered_rate": 8750, "accepted_rate": 8750, "rate_limit": null, "replicas": 1, "registration_rate": 8750, "registration_failur b3_metrics: Read AMF CPU, registration rate and registration failure rate |
| 01:56:37 | basic | agent | `get_logs` {"nf": "amf", "last": 10} |  | {"nf": "amf", "lines": ["10/07 09:00:00.000: [amf] INFO: NG setup request from gnb-207 (not in the cell inventory) accepted", "10/07 09:00:0 b4_logs: Read recent AMF logs for the registration pattern (repeated SUCI, no service request) |
| 01:56:37 | basic | agent | `list_gnbs`  |  | {"gnbs": [{"id": "gnb-101", "in_inventory": true, "connected": true, "registration_rate": 0}, {"id": "gnb-102", "in_inventory": true, "conne b5_gnbs: List base stations on the AMF; find any not in the cell inventory |
| 01:56:37 | basic | agent | `get_top_talkers` {"nf": "amf"} |  | {"nf": "amf", "top": [{"source": "ue-range-404-45-77xx", "rate": 7800, "via": "gnb-207", "blocked": false, "path_connected": true}, {"source b6_top_talkers: Identify the subscriber range and the base station it comes through |
| 01:56:37 | basic | agent | `disconnect_gnb` {"gnb_id": "gnb-207"} | yes | {"ok": true, "action": "NG setup of gnb-207 released; base station disconnected and barred"} b7_disconnect_gnb: Disconnect the base station that is not in the cell inventory (safe - it is not ours; idempotent) |
| 01:56:37 | basic | system | `success_check`  |  | {"ok": true, "actual": []} b7_disconnect_gnb: list_gnbs.unauthorised_connected empty  → passed |
| 01:56:38 | basic | agent | `block_source` {"nf": "amf", "source": "ue-range-404-45-77xx"} | yes | {"ok": true, "action": "blocked source ue-range-404-45-77xx"} b8_block_range: Block the subscriber range that generated the storm (safe - every request from it was storm traffic; ide |
| 01:56:38 | basic | system | `success_check`  |  | {"ok": true, "actual": true} b8_block_range: get_top_talkers.top.0.blocked == True → passed |
| 01:56:38 | basic | system | `resolution check`  |  | {"resolved": true, "checks": [{"fn": "list_gnbs", "path": "unauthorised_connected", "op": "empty", "actual": [], "ok": true}, {"fn": "get_to  |

## What fixed it

- `disconnect_gnb` {"gnb_id": "gnb-207"} (basic)
- `block_source` {"nf": "amf", "source": "ue-range-404-45-77xx"} (basic)

## Policy obligations recap

- **Report the cyber incident to CERT-In within 6 hours of noticing it** — when the incident is of a type listed in Annexure I of the CERT-In Directions (e.g. targeted scanning, compromise of critical systems, attacks on servers, DoS/DDoS, data breach, unauthorised access)  
  Source: CERT-In_Directions_70B_28.04.2022.pdf, p. 2
- **Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require** — when the incident affects the telecommunication network or service  
  Source: cybersecurity-rules-2024.pdf, pp. 12–13
- **If the affected network is notified as Critical Telecommunication Infrastructure, follow the CTI Rules, 2024 incident-reporting timelines** — when the affected network or element is notified as Critical Telecommunication Infrastructure  
  Source: Critical Telecommunication Infrastructure Rules, 2024_0.pdf, pp. 7–8
- **Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request** — when always (preserve the incident's logs; do not let them roll over)  
  Source: CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3
- **Telecommunications Act, 2023 s.22 — measures to protect and ensure the cyber security of telecommunication networks and services** — when always (statutory basis of the Telecom Cyber Security Rules)  
  Source: new-telecom-Act-2023.pdf, p. 10

_Decision support for a training lab; not legal advice._
