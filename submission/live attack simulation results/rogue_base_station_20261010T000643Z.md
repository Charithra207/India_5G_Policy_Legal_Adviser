# Incident report — Fake base station (rogue cell)

- Attack id: `rogue_base_station` (simulated, contained lab)
- Outcome: **RESOLVED** in the intermediate tier
- Provider: offline

## Timeline

| time | tier | actor | action | approved | result / note |
|---|---|---|---|---|---|
| 23:57:42 | start | system | `inject` {"attack": "rogue_base_station"} |  | {"alerts": ["UE measurement reports show a cell that is not in the cell inventory (TA-4501)"]}  |
| 23:57:43 | basic | agent | `get_alerts`  |  | {"alerts": ["UE measurement reports show a cell that is not in the cell inventory (TA-4501)"]} b1_alerts: Read the active alerts |
| 23:57:43 | basic | agent | `get_ran_kpis`  |  | {"area": "TA-4501", "fallback_to_lte_ues": 38, "radio_link_failures": 12, "unknown_cells_reported": [{"cell": "gnb-666", "pci": 999, "rsrp_d b2_ran_kpis: Read RAN KPIs - unknown cells in measurement reports |
| 23:57:43 | basic | agent | `list_neighbors`  |  | {"neighbors": ["gnb-101", "gnb-102", "gnb-103", "gnb-666"], "unknown": ["gnb-666"], "whitelist": "disabled"} b3_neighbors: Compare reported cells with the planned neighbour list |
| 23:57:43 | basic | agent | `get_logs` {"nf": "gnb", "last": 10} |  | {"nf": "gnb", "lines": ["10/07 09:00:00.000: [gnb] WARNING: measurement reports from 214 UEs in TA-4501 list cell gnb-666 (PCI 999, RSRP -61 b4_gnb_logs: Read gNB logs (measurement reports) |
| 23:57:43 | basic | agent | `get_logs` {"nf": "amf", "last": 10} |  | {"nf": "amf", "lines": ["10/07 09:00:00.000: [amf] WARNING: registration attempts with downgraded security capabilities from UEs in TA-4501" b5_amf_logs: Read AMF logs (downgraded registrations) |
| 23:57:43 | basic | agent | `check_auth_config`  |  | {"method": "5G-AKA", "ciphering": "NEA2", "integrity": "NIA2", "suci_protection": "profile_A", "up_integrity": "required", "subscriber_keys_ b6_auth: Confirm SUCI protection is still on (identity not exposed) |
| 23:57:43 | basic | agent | `patch_config` {"nf": "gnb", "key": "neighbor_whitelist", "value": "enforced"} | yes | {"ok": true, "action": "config neighbor_whitelist = 'enforced'"} b7_whitelist: Re-enable the planned-neighbour whitelist (restores the baseline control; safe, idempotent) |
| 23:57:43 | basic | system | `success_check`  |  | {"ok": true, "actual": "enforced"} b7_whitelist: list_neighbors.whitelist == enforced → passed |
| 23:57:43 | basic | system | `resolution check`  |  | {"resolved": false, "checks": [{"fn": "get_ran_kpis", "path": "fallback_to_lte_ues", "op": "==", "value": 0, "actual": 38, "ok": false}, {"f  |
| 00:06:36 | intermediate | operator | `gate`  |  | agent  |
| 00:06:39 | intermediate | agent | `flag_cell_hostile` {"cell_id": "gnb-666"} | yes | {"ok": true, "action": "cell gnb-666 flagged hostile and removed from neighbour lists"} i1_flag_hostile: Flag the cell that is not in the inventory as hostile |
| 00:06:39 | intermediate | system | `success_check`  |  | {"ok": true, "actual": ["gnb-666"]} i1_flag_hostile: get_ran_kpis.hostile_cells contains gnb-666 → passed |
| 00:06:41 | intermediate | agent | `push_device_policy` {"cell_id": "gnb-666"} | yes | {"ok": true, "action": "policy pushed to UEs in TA-4501: do not camp on or hand over to gnb-666"} i2_device_policy: Push a policy telling devices in TA-4501 to ignore that cell |
| 00:06:41 | intermediate | system | `success_check`  |  | {"ok": true, "actual": 0} i2_device_policy: get_ran_kpis.fallback_to_lte_ues == 0 → passed |
| 00:06:43 | intermediate | agent | `dispatch_field_team` {"cell_id": "gnb-666"} | yes | {"ok": true, "action": "field-team ticket opened to locate the transmitter of gnb-666"} i3_field_team: Hand off to a field team to locate the transmitter (physical removal is a real-world action; recorded her |
| 00:06:43 | intermediate | system | `resolution check`  |  | {"resolved": true, "checks": [{"fn": "get_ran_kpis", "path": "fallback_to_lte_ues", "op": "==", "value": 0, "actual": 0, "ok": true}, {"fn":  |

## What fixed it

- `patch_config` {"nf": "gnb", "key": "neighbor_whitelist", "value": "enforced"} (basic)
- `flag_cell_hostile` {"cell_id": "gnb-666"} (intermediate)
- `push_device_policy` {"cell_id": "gnb-666"} (intermediate)
- `dispatch_field_team` {"cell_id": "gnb-666"} (intermediate)

## Policy obligations recap

- **Report the cyber incident to CERT-In within 6 hours of noticing it** — when the incident is of a type listed in Annexure I of the CERT-In Directions (e.g. targeted scanning, compromise of critical systems, attacks on servers, DoS/DDoS, data breach, unauthorised access)  
  Source: CERT-In_Directions_70B_28.04.2022.pdf, p. 2
- **Telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require** — when the incident affects the telecommunication network or service  
  Source: cybersecurity-rules-2024.pdf, pp. 12–13
- **Keep ICT system logs for a rolling 180 days and provide them to CERT-In on request** — when always (preserve the incident's logs; do not let them roll over)  
  Source: CERT-In_Directions_70B_28.04.2022.pdf, pp. 2–3
- **Telecommunications Act, 2023 s.22 — measures to protect and ensure the cyber security of telecommunication networks and services** — when always (statutory basis of the Telecom Cyber Security Rules)  
  Source: new-telecom-Act-2023.pdf, p. 10

_Decision support for a training lab; not legal advice._
