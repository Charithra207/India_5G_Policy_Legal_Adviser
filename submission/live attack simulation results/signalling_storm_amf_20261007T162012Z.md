# Incident report — Signalling storm on the AMF

- Attack id: `signalling_storm_amf` (simulated, contained lab)
- Outcome: **RESOLVED** in the intermediate tier
- Provider: offline

## Timeline

| time | tier | actor | action | approved | result / note |
|---|---|---|---|---|---|
| 16:20:12 | start | system | `inject` {"attack": "signalling_storm_amf"} |  | {"alerts": ["AMF CPU above 90% for 3 consecutive ticks (registration storm suspected)"]}  |
| 16:20:12 | basic | agent | `get_alerts`  |  | {"alerts": ["AMF CPU above 90% for 3 consecutive ticks (registration storm suspected)"]} b1_alerts: Read the active alerts to confirm what the monitoring saw |
| 16:20:12 | basic | agent | `get_nf_health` {"nf": "amf"} |  | {"amf": "degraded"} b2_health: Check AMF health (ok / degraded / down) |
| 16:20:12 | basic | agent | `get_metrics` {"nf": "amf"} |  | {"cpu": 100, "offered_rate": 8750, "accepted_rate": 8750, "rate_limit": null, "replicas": 1, "registration_rate": 8750} b3_metrics: Read AMF CPU, offered and accepted registration rate |
| 16:20:12 | basic | agent | `get_logs` {"nf": "amf", "last": 10} |  | {"nf": "amf", "lines": ["t=0000 WARN  AMF  registration request burst: 7800/min from ue-range-404-45-77xx (initial registrations, repeated S b4_logs: Read recent AMF logs for the registration pattern (repeated SUCI, no service request) |
| 16:20:12 | basic | agent | `get_top_talkers` {"nf": "amf"} |  | {"nf": "amf", "top": [{"source": "ue-range-404-45-77xx", "rate": 7800, "blocked": false}, {"source": "ue-range-404-45-12xx", "rate": 900, "b b5_top_talkers: Identify which UE ranges generate the registrations |
| 16:20:12 | basic | agent | `check_auth_config`  |  | {"method": "5G-AKA", "ciphering": "NEA2", "integrity": "NIA2", "suci_protection": "profile_A", "up_integrity": "required", "subscriber_keys_ b6_auth_config: Rule out an authentication misconfiguration causing re-registration loops |
| 16:20:12 | basic | agent | `rate_limit_nf` {"nf": "amf", "limit": 1000} | yes | {"ok": true, "action": "rate limit set to 1000/min"} b7_rate_limit: Cap accepted registrations at 1000/min (AMF overload control; safe, idempotent, reversible) |
| 16:20:12 | basic | system | `success_check`  |  | {"ok": true, "actual": 1000} b7_rate_limit: get_metrics.accepted_rate <= 1000 → passed |
| 16:20:12 | basic | agent | `scale_out` {"nf": "amf", "replicas": 2} | yes | {"ok": true, "action": "scaled to 2 replicas"} b8_scale_out: Add a second AMF instance for headroom (safe, idempotent) |
| 16:20:12 | basic | system | `success_check`  |  | {"ok": true, "actual": 50} b8_scale_out: get_metrics.cpu < 70 → passed |
| 16:20:12 | basic | system | `resolution check`  |  | {"resolved": false, "checks": [{"fn": "get_metrics", "args": {"nf": "amf"}, "path": "cpu", "op": "<", "value": 70, "actual": 50, "ok": true}  |
| 16:20:12 | intermediate | operator | `gate`  |  | agent  |
| 16:20:12 | intermediate | agent | `block_source` {"nf": "amf", "source": "ue-range-404-45-77xx"} | yes | {"ok": true, "action": "blocked source ue-range-404-45-77xx"} i1_block_top_source: Block the top registration source found by get_top_talkers (needs approval — legitimate UEs in the  |
| 16:20:12 | intermediate | system | `success_check`  |  | {"ok": true, "actual": true} i1_block_top_source: get_top_talkers.top.0.blocked == True → passed |
| 16:20:12 | intermediate | system | `resolution check`  |  | {"resolved": true, "checks": [{"fn": "get_metrics", "args": {"nf": "amf"}, "path": "cpu", "op": "<", "value": 70, "actual": 49, "ok": true},  |

## What fixed it

- `rate_limit_nf` {"nf": "amf", "limit": 1000} (basic)
- `scale_out` {"nf": "amf", "replicas": 2} (basic)
- `block_source` {"nf": "amf", "source": "ue-range-404-45-77xx"} (intermediate)

## Policy obligations recap


_Decision support for a training lab; not legal advice._
