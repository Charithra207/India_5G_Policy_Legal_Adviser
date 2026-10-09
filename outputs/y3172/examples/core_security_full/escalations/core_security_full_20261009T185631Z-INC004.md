# Escalation — core_security_full_20261009T185631Z-INC004

- Prediction: **nf_host_ransomware** by iforest_rf (confidence 0.57, anomaly score -0.07)
- Policy node: escalate (blocking mode)

## Why a human is needed

- Confidence 0.57 is below the intent's minimum 0.60; no automated action is taken.

## Telemetry that deviates from normal operation

- `smf.health.state` = 3.0 (normal ≈ 0.0, z = 12.0)
- `Δsmf.metrics.active_pdu_sessions` = -1200.0 (normal ≈ 32.143, z = -6.4)
- `Δsmf.metrics.cpu` = -17.0 (normal ≈ 0.473, z = -5.9)
- `Δsmf.integrity.files_encrypted` = 1.0 (normal ≈ -0.027, z = 4.1)
- `oam.alerts.new_alerts` = 1.0 (normal ≈ 0.0, z = 4.0)

_Decision support for a training lab; not legal advice._
