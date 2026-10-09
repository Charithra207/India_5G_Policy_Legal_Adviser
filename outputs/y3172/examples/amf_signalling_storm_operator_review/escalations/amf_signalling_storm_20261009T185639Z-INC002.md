# Escalation — amf_signalling_storm_20261009T185639Z-INC002

- Prediction: **core_ddos_upf** by iforest_rf (confidence 0.50, anomaly score -0.04)
- Policy node: escalate (blocking mode)

## Why a human is needed

- Confidence 0.50 is below the intent's minimum 0.60; no automated action is taken.

## Telemetry that deviates from normal operation

- `upf.metrics.accepted_rate` = 2006.0 (normal ≈ 837.021, z = 4.3)
- `upf.metrics.offered_rate` = 2006.0 (normal ≈ 837.021, z = 4.3)
- `upf.health.state` = 1.0 (normal ≈ 0.0, z = 4.0)
- `upf.metrics.cpu` = 100.0 (normal ≈ 50.144, z = 3.8)

_Decision support for a training lab; not legal advice._
