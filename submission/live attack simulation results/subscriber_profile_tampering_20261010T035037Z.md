# Incident report — Subscriber profile tampering (slice breach)

- Attack id: `subscriber_profile_tampering` (simulated, contained lab)
- Outcome: **RESOLVED** in the advanced tier
- Provider: offline

## Summary

The simulated attack "Subscriber profile tampering (slice breach)" was injected into the contained 5G core, affecting OAM, UDM and SMF. It was first visible as: session on urllc-hospital from a subscriber that is not on the slice allow-list. The response agent (offline) worked through the basic, intermediate and advanced tiers, running 7 diagnostic steps and 1 approved fix (end_session). The Policy panel listed 5 Indian obligations for this kind of incident, 5 confirmed word for word in the cited documents.

## Conclusion

The incident was resolved in the advanced tier: every resolution check passes against the simulator (not on the agent's own say-so). Whatever the technical outcome, the Indian obligations listed still apply, among them: report the cyber incident to CERT-In within 6 hours of noticing it; telecommunication entity reports the security incident to the Central Government within six hours of becoming aware (Telecom Cyber Security Rules, 2024, rule 7), followed by the details the rules require; if the affected network is notified as Critical Telecommunication Infrastructure, follow the CTI Rules, 2024 incident-reporting timelines. Every action, approval and refusal is in the timeline and the saved report. This is a training simulation and decision support, not legal advice.

## Timeline

| time | tier | actor | action | approved | result / note |
|---|---|---|---|---|---|
| 03:47:50 | start | system | `inject` {"attack": "subscriber_profile_tampering"} |  | {"alerts": ["Session on urllc-hospital from a subscriber that is not on the slice allow-list"]}  |
| 03:48:03 | basic | agent | `get_alerts`  |  | {"alerts": ["Session on urllc-hospital from a subscriber that is not on the slice allow-list"]} b1_alerts: Read the active alerts |
| 03:48:03 | basic | agent | `check_slice_sessions` {"slice": "urllc-hospital"} |  | {"slice": "urllc-hospital", "allow_list": ["imsi-404450000000101", "imsi-404450000000102"], "sessions": [{"id": "pdu-1001", "supi": "imsi-40 b2_slice_sessions: Sessions on the hospital slice that are not on its allow-list |
| 03:48:04 | basic | agent | `get_subscriber_changes`  |  | {"changes": [{"supi": "imsi-404450000000777", "field": "allowed_slices", "old": ["embb"], "new": ["embb", "urllc-hospital"], "by": "admin",  b3_db_changes: Subscriber-database change records (who changed what |
| 03:48:04 | basic | agent | `get_logs` {"nf": "oam", "last": 10} |  | {"nf": "oam", "lines": ["10/07 09:00:00.000: [oam] INFO: simulation reset to baseline", "10/07 09:00:00.007: [oam] INFO: admin login (defaul b4_admin_logins: Admin login log - was the change made from an unusual source |
| 03:48:05 | basic | agent | `check_mgmt_exposure`  |  | {"exposed_to_internet": false, "default_credentials": true, "admin_access": "any-internal", "credentials_version": 1} b5_mgmt: Are default admin credentials still in use |
| 03:48:06 | basic | agent | `get_logs` {"nf": "smf", "last": 10} |  | {"nf": "smf", "lines": ["10/07 09:00:00.000: [smf] INFO: PDU session pdu-9001 established for imsi-404450000000777 on S-NSSAI urllc-hospital b6_smf_logs: When was the session established |
| 03:48:06 | basic | system | `resolution check`  |  | {"resolved": false, "checks": [{"fn": "check_slice_sessions", "args": {"slice": "urllc-hospital"}, "path": "not_on_allow_list", "op": "empty  |
| 03:48:16 | intermediate | operator | `gate`  |  | agent  |
| 03:48:19 | intermediate | agent | `end_session` {"session_id": "pdu-9001"} | yes | {"ok": true, "action": "PDU session pdu-9001 (imsi-404450000000777, urllc-hospital) released"} i1_end_session: End the session that is not on the slice allow-list |
| 03:48:19 | intermediate | system | `success_check`  |  | {"ok": true, "actual": []} i1_end_session: check_slice_sessions.not_on_allow_list empty  → passed |
| 03:48:20 | intermediate | agent | `get_subscriber_changes`  |  | {"changes": [{"supi": "imsi-404450000000777", "field": "allowed_slices", "old": ["embb"], "new": ["embb", "urllc-hospital"], "by": "admin",  i2_verify: Re-check the change records (the profile still allows the slice) |
| 03:48:20 | intermediate | system | `resolution check`  |  | {"resolved": false, "checks": [{"fn": "check_slice_sessions", "args": {"slice": "urllc-hospital"}, "path": "not_on_allow_list", "op": "empty  |
| 03:48:24 | advanced | operator | `gate`  |  | manual  |
| 03:48:24 | advanced | system | `handed to operator`  |  | null 4 steps printed |
| 03:50:35 | advanced | operator | `pasted results`  |  | {
  "ok": true,
  "action": "subscription profile of imsi-404450000000777 restored from the known-good snapshot"
}
{
  "ok": true,
  "action Operator results received; resolution checks now pass. |
| 03:50:36 | advanced | system | `resolution check`  |  | {"resolved": true, "checks": [{"fn": "check_slice_sessions", "args": {"slice": "urllc-hospital"}, "path": "not_on_allow_list", "op": "empty"  |

## What fixed it

- `end_session` {"session_id": "pdu-9001"} (intermediate)

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
