# Escalation — amf_signalling_storm_20261009T185639Z-INC001

- Prediction: **signalling_storm_amf** by iforest_rf (confidence 0.95, anomaly score -0.11)
- Policy node: hold_for_approval (blocking mode)

## Why a human is needed

- Remediation status: held — blocking mode: the operator did not approve remediation; nothing was changed
- Blocking mode: remediation is held until a human approves it, having seen the obligations below.
- Logs are preserved before any state-changing step (CERT-In Directions: 180-day log retention).

## Telemetry that deviates from normal operation

- `amf.metrics.offered_rate` = 659.0 (normal ≈ 163.87, z = 8.2)
- `amf.metrics.accepted_rate` = 659.0 (normal ≈ 163.87, z = 8.2)
- `Δamf.metrics.cpu` = 34.0 (normal ≈ 0.808, z = 5.5)

_Decision support for a training lab; not legal advice._
