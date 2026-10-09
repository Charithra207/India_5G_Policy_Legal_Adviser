# Escalation — core_security_full_20261009T185631Z-INC005

- Prediction: **nf_host_ransomware** by iforest_rf (confidence 0.55, anomaly score -0.08)
- Policy node: escalate (blocking mode)

## Why a human is needed

- Confidence 0.55 is below the intent's minimum 0.60; no automated action is taken.

## Telemetry that deviates from normal operation

- `smf.health.state` = 3.0 (normal ≈ 0.0, z = 12.0)
- `smf.metrics.active_pdu_sessions` = 0.0 (normal ≈ 1157.143, z = -5.2)
- `smf.metrics.cpu` = 0.0 (normal ≈ 16.723, z = -5.1)
- `udm.metrics.accepted_rate` = 91.0 (normal ≈ 44.433, z = 4.6)
- `udm.metrics.offered_rate` = 91.0 (normal ≈ 44.433, z = 4.6)

_Decision support for a training lab; not legal advice._
