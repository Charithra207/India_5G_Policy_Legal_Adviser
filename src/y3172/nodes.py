"""
SRC, C and PP nodes of the Y.3172 ML pipeline (clause 8.1)
==========================================================
SRC (source)        a network function of the simulated 5G core, exposing
                    one or more telemetry groups (metrics, logs, RAN, ...).
                    The intent's `sources` list is the set of SRC nodes.
C (collector)       polls the SRC nodes through the simulator's read-only
                    diagnostics — never a state-changing function — and
                    keeps what is new since the previous poll (log lines,
                    alerts).  Reference point: underlay network → pipeline
                    (Y.3172 Figure 4, reference point 4).
PP (preprocessor)   turns a collected snapshot into a fixed-length feature
                    vector: cleaning (non-finite values to 0), the features
                    of every SRC node in a canonical order, and the change
                    since the previous snapshot (a two-step window).

Every feature is named "<nf>.<group>.<signal>" so model output can be
explained in terms an operator recognises.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable

from sim.engine import FUNCTIONS, NFS, Sim, call

HEALTH_CODE = {"ok": 0.0, "degraded": 1.0, "isolated": 2.0, "down": 3.0}


@dataclass(frozen=True)
class TelemetryGroup:
    """One kind of telemetry, the NFs that provide it and how to read it."""
    name: str
    nfs: tuple[str, ...]
    description: str
    read: Callable[[Sim, str], dict]              # (sim, nf) -> raw diagnostic results
    features: Callable[[dict, str, dict], dict]   # (raw, nf, novelty) -> {signal: value}


def _d(sim: Sim, fn: str, **args) -> dict:
    """Run one diagnostic.  The collector may only read the network."""
    if FUNCTIONS.get(fn) != "diagnostic":
        raise PermissionError(f"collector may only call diagnostics, not {fn!r}")
    result = call(sim, fn, args)
    return result if isinstance(result, dict) else {}


def _n(value) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return 0.0


# --- metrics ----------------------------------------------------------------

_METRIC_EXTRAS = {
    "amf": ("registration_failure_pct",),
    "upf": ("packet_drop_pct",),
    "nef": ("api_calls_per_min",),
    "udm": ("bulk_reads_active",),
    "gnb": ("fallback_to_lte_ues", "radio_link_failures"),
}


def _read_metrics(sim: Sim, nf: str) -> dict:
    allm = _d(sim, "get_metrics")
    return {"nf": allm.get(nf, {}), "active_pdu_sessions": allm.get("active_pdu_sessions", 0)}


def _metric_features(raw: dict, nf: str, _: dict) -> dict:
    m = raw["nf"]
    out = {"cpu": _n(m.get("cpu")), "offered_rate": _n(m.get("offered_rate")),
           "accepted_rate": _n(m.get("accepted_rate"))}
    for key in _METRIC_EXTRAS.get(nf, ()):
        out[key] = _n(m.get(key))
    if nf == "smf":
        out["active_pdu_sessions"] = _n(raw["active_pdu_sessions"])
    return out


# --- groups -----------------------------------------------------------------

def _logs_features(raw: dict, nf: str, novelty: dict) -> dict:
    new = novelty.get("logs", {}).get(nf, [])
    return {"new_warnings": float(sum(": WARNING: " in line for line in new)),
            "new_errors": float(sum(": ERROR: " in line for line in new))}


def _ran(sim: Sim, nf: str) -> dict:
    return {"gnbs": _d(sim, "list_gnbs"), "neighbors": _d(sim, "list_neighbors"), "kpis": _d(sim, "get_ran_kpis")}


def _ran_features(raw: dict, nf: str, _: dict) -> dict:
    return {"unauthorised_gnbs": float(len(raw["gnbs"].get("unauthorised_connected", []))),
            "unknown_neighbours": float(len(raw["neighbors"].get("unknown", []))),
            "neighbour_whitelist_off": _n(raw["neighbors"].get("whitelist") != "enforced"),
            "unknown_cells_reported": float(len(raw["kpis"].get("unknown_cells_reported", [])))}


def _transport_features(raw: dict, nf: str, _: dict) -> dict:
    ifs = raw["interfaces"]
    return {"interfaces_without_ipsec": float(sum(not v.get("ipsec", True) for v in ifs.values())),
            "up_integrity_off": _n(raw["auth"].get("up_integrity") == "not_used")}


def _sba(sim: Sim, nf: str) -> dict:
    return _d(sim, "check_api_access_log", nf=nf)


def _sba_features(raw: dict, nf: str, _: dict) -> dict:
    if nf == "nef":
        return {"oauth2_not_required": _n(raw.get("oauth2") != "required"),
                "abusive_tokens": float(len(raw.get("abusive_tokens", [])))}
    return {"bulk_export_enabled": _n(raw.get("bulk_export") == "enabled"),
            "bulk_readers": float(len(raw.get("bulk_readers", [])))}


def _registry_features(raw: dict, nf: str, _: dict) -> dict:
    return {"unsigned_instances": float(len(raw.get("unsigned", []))),
            "unexpected_hosts": float(len(raw.get("unexpected_hosts", []))),
            "registration_auth_off": _n(raw.get("registration_auth") != "required"),
            "signed_profiles_not_required": _n(raw.get("require_signed_nf_profiles") is False)}


def _oam_features(raw: dict, nf: str, _: dict) -> dict:
    return {"exposed_to_internet": _n(raw.get("exposed_to_internet")),
            "default_credentials": _n(raw.get("default_credentials")),
            "admin_access_open": _n(raw.get("admin_access") != "jump-host-only")}


def _user_plane_features(raw: dict, nf: str, _: dict) -> dict:
    return {"spoofed_flows": float(len(raw.get("spoofed", []))),
            "flows_to_internal_ranges": float(len(raw.get("to_internal_ranges", []))),
            "source_validation_off": _n(raw.get("source_address_validation") != "enabled")}


def _devices(sim: Sim, nf: str) -> dict:
    return {"stats": _d(sim, "get_device_stats", slice="mmtc"), "flows": _d(sim, "get_flow_logs")}


def _devices_features(raw: dict, nf: str, _: dict) -> dict:
    return {"anomalous_devices": float(len(raw["stats"].get("anomalous", []))),
            "unblocked_c2_destinations": float(len(raw["flows"].get("unblocked_c2", [])))}


def _service_features(raw: dict, nf: str, _: dict) -> dict:
    return {"hospital_portal_latency_ms": _n(raw.get("latency_ms")),
            "hospital_portal_degraded": _n(raw.get("status") != "ok")}


TELEMETRY: dict[str, TelemetryGroup] = {g.name: g for g in (
    TelemetryGroup("metrics", tuple(NFS), "CPU, offered/accepted rates and NF-specific KPIs",
                   _read_metrics, _metric_features),
    TelemetryGroup("health", tuple(NFS), "health state (ok / degraded / isolated / down)",
                   lambda sim, nf: _d(sim, "get_nf_health", nf=nf),
                   lambda raw, nf, _: {"state": HEALTH_CODE.get(raw.get(nf), 0.0)}),
    TelemetryGroup("logs", tuple(NFS), "new WARNING / ERROR log lines since the previous poll",
                   lambda sim, nf: {}, _logs_features),
    TelemetryGroup("alerts", ("oam",), "new monitoring alerts since the previous poll",
                   lambda sim, nf: {},
                   lambda raw, nf, nov: {"new_alerts": float(len(nov.get("alerts", [])))}),
    TelemetryGroup("ran", ("gnb",), "base stations on the AMF, neighbour lists and UE-reported cells",
                   _ran, _ran_features),
    TelemetryGroup("auth", ("ausf",), "authentication state and subscriber-key status",
                   lambda sim, nf: _d(sim, "check_auth_config"),
                   lambda raw, nf, _: {"subscriber_keys_compromised": _n(raw.get("subscriber_keys_compromised"))}),
    TelemetryGroup("transport", ("gnb",), "IPsec on N2/N3 and user-plane integrity",
                   lambda sim, nf: {"interfaces": _d(sim, "check_interface_security"),
                                    "auth": _d(sim, "check_auth_config")},
                   _transport_features),
    TelemetryGroup("sba", ("nef", "udm"), "service-based API access (NEF exposure, UDM bulk reads)",
                   _sba, _sba_features),
    TelemetryGroup("integrity", tuple(NFS), "host file integrity",
                   lambda sim, nf: _d(sim, "check_file_integrity", nf=nf),
                   lambda raw, nf, _: {"files_encrypted": _n(raw.get("files_encrypted"))}),
    TelemetryGroup("registry", ("nrf",), "NF instances registered in the NRF",
                   lambda sim, nf: _d(sim, "list_registered_nfs"), _registry_features),
    TelemetryGroup("egress", ("upf",), "active outbound flows from core hosts",
                   lambda sim, nf: _d(sim, "get_egress_flows"),
                   lambda raw, nf, _: {"active_egress_flows": float(len(raw.get("active", [])))}),
    TelemetryGroup("oam", ("oam",), "management-interface exposure and credentials",
                   lambda sim, nf: _d(sim, "check_mgmt_exposure"), _oam_features),
    TelemetryGroup("slices", ("smf",), "sessions on the hospital slice outside its allow-list",
                   lambda sim, nf: _d(sim, "check_slice_sessions", slice="urllc-hospital"),
                   lambda raw, nf, _: {"sessions_not_on_allow_list": float(len(raw.get("not_on_allow_list", [])))}),
    TelemetryGroup("subscribers", ("udm",), "unreverted subscription-profile changes",
                   lambda sim, nf: _d(sim, "get_subscriber_changes"),
                   lambda raw, nf, _: {"unreverted_profile_changes": float(len(raw.get("unreverted", [])))}),
    TelemetryGroup("user_plane", ("upf",), "GTP-U flows: spoofed sources, flows to internal ranges",
                   lambda sim, nf: _d(sim, "get_upf_flows"), _user_plane_features),
    TelemetryGroup("devices", ("amf",), "mMTC device rates and command-and-control contacts",
                   _devices, _devices_features),
    TelemetryGroup("services", ("smf",), "health of the hospital portal on the URLLC slice",
                   lambda sim, nf: _d(sim, "get_service_health", service="hospital-portal"),
                   _service_features),
)}


# ---------------------------------------------------------------------------
# C — collector
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    tick: int
    raw: dict[tuple[str, str], dict]          # (nf, group) -> diagnostic results
    novelty: dict                             # new log lines per NF, new alerts
    missing: list[tuple[str, str]] = field(default_factory=list)   # SRC nodes not read this poll


class Collector:
    """
    Polls the SRC nodes named in the intent.  `dropout` (0-1) drops a whole
    SRC node from a poll at random — used in the ML sandbox to train models
    that tolerate telemetry gaps; the live collector uses 0.
    """

    def __init__(self, plan: list[tuple[str, str]], dropout: float = 0.0,
                 rng: random.Random | None = None) -> None:
        self.plan = list(plan)
        self.dropout = dropout
        self.rng = rng or random.Random(0)
        self._last_line: dict[str, str | None] = {}
        self._alerts_seen = 0

    def reset(self) -> None:
        self._last_line, self._alerts_seen = {}, 0

    def _new_lines(self, sim: Sim, nf: str) -> list[str]:
        lines = _d(sim, "get_logs", nf=nf, last=500).get("lines", [])
        last = self._last_line.get(nf)
        start = 0
        if last is not None:
            for i in range(len(lines) - 1, -1, -1):
                if lines[i] == last:
                    start = i + 1
                    break
        self._last_line[nf] = lines[-1] if lines else last
        return lines[start:]

    def poll(self, sim: Sim) -> Snapshot:
        log_nfs = sorted({nf for nf, g in self.plan if g == "logs"})
        alerts = _d(sim, "get_alerts").get("alerts", [])
        novelty = {"logs": {nf: self._new_lines(sim, nf) for nf in log_nfs},
                   "alerts": alerts[self._alerts_seen:]}
        self._alerts_seen = len(alerts)
        raw, missing = {}, []
        for nf, group in self.plan:
            if self.dropout and self.rng.random() < self.dropout:
                missing.append((nf, group))
                continue
            raw[(nf, group)] = TELEMETRY[group].read(sim, nf)
        return Snapshot(sim.state["tick"], raw, novelty, missing)


# ---------------------------------------------------------------------------
# PP — preprocessor
# ---------------------------------------------------------------------------

class Preprocessor:
    """
    Snapshot -> feature vector: the current value of every signal, then its
    change since the previous snapshot.  A missing SRC node contributes
    zeros (and no change), so the vector length never varies.
    """

    def __init__(self, plan: list[tuple[str, str]]) -> None:
        self.plan = list(plan)
        names = []
        for nf, group in self.plan:
            names += [f"{nf}.{group}.{s}" for s in self._signals(nf, group)]
        self.base_names = names
        self.feature_names = names + [f"Δ{n}" for n in names]
        self._previous: list[float] | None = None

    @staticmethod
    def _signals(nf: str, group: str) -> list[str]:
        """Signal names of one SRC node, read from a fresh baseline simulation."""
        key = (nf, group)
        if key not in _SIGNAL_CACHE:
            sim = Sim(persist=False)
            raw = TELEMETRY[group].read(sim, nf)
            _SIGNAL_CACHE[key] = list(TELEMETRY[group].features(raw, nf, {"logs": {}, "alerts": []}))
        return _SIGNAL_CACHE[key]

    def reset(self) -> None:
        self._previous = None

    def current(self, snap: Snapshot) -> list[float]:
        values: list[float] = []
        for nf, group in self.plan:
            signals = self._signals(nf, group)
            if (nf, group) in snap.raw:
                feats = TELEMETRY[group].features(snap.raw[(nf, group)], nf, snap.novelty)
                values += [_n(feats.get(s, 0.0)) for s in signals]
            else:
                values += [0.0] * len(signals)
        return values

    def transform(self, snap: Snapshot) -> list[float]:
        cur = self.current(snap)
        prev = self._previous if self._previous is not None else cur
        owners = self._owners()
        delta = [0.0 if o in snap.missing else c - p for c, p, o in zip(cur, prev, owners)]
        # a node missing from this poll keeps its last known value as the reference
        self._previous = [p if o in snap.missing else c for c, p, o in zip(cur, prev, owners)]
        return cur + delta

    def _owners(self) -> list[tuple[str, str]]:
        owners = []
        for nf, group in self.plan:
            owners += [(nf, group)] * len(self._signals(nf, group))
        return owners


_SIGNAL_CACHE: dict[tuple[str, str], list[str]] = {}
