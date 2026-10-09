"""
Simulated 5G core — a contained, deterministic lab target.
==========================================================
Everything here is in-process Python state.  Nothing opens a socket, scans,
or touches any real host or network: the "network functions" are dicts, the
"attacks" (sim/inject.py) flip fields in those dicts, and the "fixes" below
flip them back.  State is written to <work>/state.json and logs to
<work>/logs/<nf>.log, where <work> is $LAB_WORK_DIR or sim/.  Log lines use
the Open5GS layout ("MM/DD HH:MM:SS.mmm: [amf] WARNING: ...") with a
simulated clock, so they read like real core logs.

Network functions: gNB, AMF, SMF, UPF, UDM, AUSF, NEF, NRF and an OAM
(management) endpoint.  Also modelled: base stations connected to the AMF,
network slices (embb, urllc-hospital with an allow-list, mmtc), subscriber
profiles with a known-good snapshot, PDU sessions, UPF flows, mMTC devices
and a service (hospital-portal) on the hospital slice.

Two kinds of functions, both listed in FUNCTIONS with their kind:
  diagnostic   read-only (DIAGNOSTICS below)
  remediation  state-changing (REMEDIATIONS below)
Derived metrics (CPU, failure rates, drops, flows) are recomputed from the
state after every action, so a fix has a visible, checkable effect.
"""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

NFS = ("gnb", "amf", "smf", "upf", "udm", "ausf", "nef", "nrf", "oam")
CLOCK_START = datetime(2026, 10, 7, 9, 0, 0)          # simulated clock for log lines
OPEN5GS_LEVEL = {"WARN": "WARNING", "ACTION": "INFO"}

HOSPITAL_ALLOW = ["imsi-404450000000101", "imsi-404450000000102"]
MMTC_DEVICES = [f"meter-{i:04d}" for i in range(1, 41)]


def work_dir() -> Path:
    return Path(os.environ.get("LAB_WORK_DIR", Path(__file__).resolve().parent))


def _baseline() -> dict:
    nf = lambda **kw: {"status": "running", "isolated": False, "replicas": 1, "rate_limit": None,  # noqa: E731
                       "blocked_sources": [], "files_encrypted": False, "config": {}, **kw}
    subscribers = {s: {"slices": ["embb", "urllc-hospital"]} for s in HOSPITAL_ALLOW}
    subscribers.update({"imsi-404450000000555": {"slices": ["embb"]},
                        "imsi-404450000000777": {"slices": ["embb"]}})
    return {
        "tick": 0,
        "attack": None,                 # id of the injected attack, if any
        "nfs": {
            "gnb": nf(config={"neighbor_whitelist": "enforced", "up_integrity": "required"}),
            "amf": nf(config={"overload_control": "enabled", "max_registration_rate": 1500}),
            "smf": nf(), "ausf": nf(),
            "upf": nf(config={"source_address_validation": "enabled"}),
            "udm": nf(config={"suci_protection": "profile_A", "bulk_export": "disabled"}),
            "nef": nf(config={"oauth2": "required"}),
            "nrf": nf(config={"require_signed_nf_profiles": True, "registration_auth": "required"}),
            "oam": nf(config={"exposed_to_internet": False, "default_credentials": False,
                              "admin_access": "jump-host-only"}),
        },
        # RAN: base stations connected to the AMF, and the neighbour list UEs measure
        "gnbs": [{"id": g, "in_inventory": True, "connected": True} for g in ("gnb-101", "gnb-102", "gnb-103")],
        "neighbors": ["gnb-101", "gnb-102", "gnb-103"],
        "allowed_neighbors": ["gnb-101", "gnb-102", "gnb-103"],
        "fake_cells": [],               # transmitters UEs hear that are not ours
        "hostile_cells": [], "device_policy": {"ignore_cells": []}, "field_tickets": [],
        "auth": {"method": "5G-AKA", "ciphering": "NEA2", "integrity": "NIA2",
                 "subscriber_keys_compromised": False, "key_version": 1, "oam_credentials_version": 1},
        "interfaces": {"N2": {"ipsec": True}, "N3": {"ipsec": True}},
        "nef_tokens": {"valid_tokens": ["af-partner-1"], "abusive_tokens": []},
        # slices, subscriber profiles (with a known-good snapshot) and PDU sessions
        "slices": {"embb": {"allow_list": None}, "urllc-hospital": {"allow_list": list(HOSPITAL_ALLOW)},
                   "mmtc": {"allow_list": None, "per_device_limit": None}},
        "subscribers": subscribers,
        "subscriber_snapshot": copy.deepcopy(subscribers),
        "subscriber_changes": [],
        "sessions": [{"id": "pdu-1001", "supi": "imsi-404450000000101", "slice": "urllc-hospital", "ue_ip": "10.46.0.101"},
                     {"id": "pdu-5001", "supi": "imsi-404450000000555", "slice": "embb", "ue_ip": "10.45.0.55"}],
        # user plane
        "upf_flows": [],                # suspicious GTP-U flows (see get_upf_flows)
        "acl_blocks": [],               # "src_range->dst_range"
        # NF registry, rogue components, evidence, egress
        "registered_nfs": [
            {"id": "smf-01", "type": "SMF", "signed": True, "host": "10.45.8.11"},
            {"id": "upf-01", "type": "UPF", "signed": True, "host": "10.45.8.12"},
            {"id": "udm-01", "type": "UDM", "signed": True, "host": "10.45.8.13"},
        ],
        "rogue_instances": [], "isolated_instances": [], "evidence": [], "egress_flows": [],
        # massive IoT devices and the service on the hospital slice
        "devices": {d: {"slice": "mmtc", "rate": 1, "dst": "meter-head-end"} for d in MMTC_DEVICES},
        "infected_devices": [],         # ground truth, never returned by a diagnostic
        "quarantined_devices": [], "c2_contacts": [], "blocked_destinations": [],
        "services": {"hospital-portal": {"slice": "urllc-hospital", "capacity": 800, "filter": False}},
        "backups": {n: "clean-2026-10-06" for n in NFS},
        # attack inputs: traffic sources and their request rates
        "traffic": {n: [] for n in NFS},     # [{"source": str, "rate": int, "via"?: gnb id}]
        "exfiltration": [],                  # active bulk readers of the UDM
        "alerts": [],
        "metrics": {},
        "logs": {n: [] for n in NFS},
    }


class Sim:
    """
    One simulated core.  All functions return plain dicts (JSON-serialisable).

    `root` is the folder for state.json and logs/.  By default it follows
    work_dir() ($LAB_WORK_DIR or sim/) at each save; give an explicit folder
    to run several simulations side by side (e.g. the Y.3172 ML sandbox and
    the live network in src/y3172/mlfo.py).
    """

    def __init__(self, persist: bool = True, root: Path | str | None = None) -> None:
        self.persist = persist
        self._root = Path(root) if root is not None else None
        self.state: dict = {}
        self.reset()

    @property
    def root(self) -> Path:
        """Where this simulation saves its state, logs and reports."""
        return self._root if self._root is not None else work_dir()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> dict:
        self.state = _baseline()
        self._recompute()
        self.log("oam", "INFO", "simulation reset to baseline")
        self._save()
        return {"ok": True, "tick": 0}

    @classmethod
    def resume(cls, root: Path | str | None = None) -> "Sim":
        """A Sim continuing from <work>/state.json (without first saving a fresh baseline)."""
        sim = cls(persist=False, root=root)
        sim.load()
        sim.persist = True
        return sim

    def load(self) -> dict:
        """Continue from <work>/state.json and logs (e.g. after an operator ran sim.cli)."""
        root = self.root
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        state["logs"] = {nf: ((root / "logs" / f"{nf}.log").read_text(encoding="utf-8").splitlines()
                              if (root / "logs" / f"{nf}.log").exists() else []) for nf in NFS}
        self.state = state
        self._recompute()
        return {"ok": True, "tick": state["tick"], "attack": state["attack"]}

    def tick(self, n: int = 1) -> dict:
        for _ in range(n):
            self.state["tick"] += 1
            self._recompute()
        self._save()
        return {"tick": self.state["tick"]}

    def log(self, nf: str, level: str, message: str) -> None:
        """Open5GS-style line on the simulated clock (one minute per tick)."""
        lines = self.state["logs"][nf]
        at = CLOCK_START + timedelta(minutes=self.state["tick"], milliseconds=7 * len(lines))
        if level == "ACTION":
            message = f"[lab action] {message}"
        lines.append(f"{at:%m/%d %H:%M:%S}.{at.microsecond // 1000:03d}: [{nf}] "
                     f"{OPEN5GS_LEVEL.get(level, level)}: {message}")
        self.state["logs"][nf] = lines[-500:]

    def alert(self, text: str) -> None:
        if text not in self.state["alerts"]:
            self.state["alerts"].append(text)

    def _save(self) -> None:
        if not self.persist:
            return
        root = self.root
        (root / "logs").mkdir(parents=True, exist_ok=True)
        public = {k: v for k, v in self.state.items() if k != "logs"}
        (root / "state.json").write_text(json.dumps(public, indent=2), encoding="utf-8")
        for nf, lines in self.state["logs"].items():
            (root / "logs" / f"{nf}.log").write_text("\n".join(lines) + ("\n" if lines else ""),
                                                     encoding="utf-8")

    # ------------------------------------------------------------------
    # Derived metrics
    # ------------------------------------------------------------------

    def _gnb_connected(self, gnb_id: str | None) -> bool:
        return gnb_id is None or any(g["id"] == gnb_id and g["connected"] for g in self.state["gnbs"])

    def _offered(self, nf: str) -> int:
        n = self.state["nfs"][nf]
        return sum(t["rate"] for t in self.state["traffic"][nf]
                   if t["source"] not in n["blocked_sources"] and self._gnb_connected(t.get("via")))

    def _instance_active(self, instance_id: str) -> bool:
        s = self.state
        return (any(i["id"] == instance_id for i in s["registered_nfs"])
                and instance_id not in s["isolated_instances"])

    def _device_flood(self) -> int:
        s, limit = self.state, self.state["slices"]["mmtc"].get("per_device_limit")
        rates = [s["devices"][d]["rate"] for d in s["infected_devices"] if d not in s["quarantined_devices"]]
        return sum(min(r, limit) if limit else r for r in rates)

    def _recompute(self) -> None:
        s, m = self.state, {}
        for nf in NFS:
            n = s["nfs"][nf]
            baseline = {"amf": 50, "upf": 400, "nef": 20, "udm": 30}.get(nf, 10)
            offered = baseline + self._offered(nf)
            accepted = min(offered, n["rate_limit"]) if n["rate_limit"] else offered
            if n["isolated"] or n["status"] != "running":
                accepted = 0
            capacity = 1200 * n["replicas"] if nf != "upf" else 2000 * n["replicas"]
            cpu = min(100, round(15 + 85 * accepted / capacity)) if accepted else 5
            if n["files_encrypted"]:
                cpu = 0
            m[nf] = {"cpu": cpu, "offered_rate": offered, "accepted_rate": accepted,
                     "rate_limit": n["rate_limit"], "replicas": n["replicas"]}
        amf = s["nfs"]["amf"]
        m["amf"]["registration_rate"] = m["amf"]["accepted_rate"]
        # share of registrations (legitimate ones included) that fail: capacity or rate limit exceeded
        served = 1200 * amf["replicas"] if not amf["rate_limit"] else min(1200 * amf["replicas"], amf["rate_limit"])
        ok_share = 0.0 if m["amf"]["accepted_rate"] == 0 else min(1.0, served / m["amf"]["offered_rate"])
        m["amf"]["registration_failure_pct"] = round(100 * (1 - ok_share), 1)
        m["upf"]["packet_drop_pct"] = round(max(0.0, 100 * (1 - 2000 * s["nfs"]["upf"]["replicas"]
                                                       / max(m["upf"]["accepted_rate"], 1))), 1)
        m["nef"]["api_calls_per_min"] = m["nef"]["accepted_rate"]
        m["udm"]["bulk_reads_active"] = len(self._bulk_readers())
        unheeded = [c for c in s["fake_cells"] if c not in s["device_policy"]["ignore_cells"]]
        m["gnb"]["fallback_to_lte_ues"] = 38 * len(unheeded)
        m["gnb"]["radio_link_failures"] = 12 * len(unheeded)
        m["active_pdu_sessions"] = 0 if s["nfs"]["smf"]["files_encrypted"] else 1200
        m["registered_ues"] = 5000
        s["metrics"] = m

    def _bulk_readers(self) -> list[str]:
        s = self.state
        return [e for e in s["exfiltration"] if e not in s["nfs"]["udm"]["blocked_sources"]
                and (e not in s["rogue_instances"] or self._instance_active(e))]

    def _health(self, nf: str) -> str:
        n, m = self.state["nfs"][nf], self.state["metrics"][nf]
        if n["files_encrypted"]:
            return "down"
        if n["isolated"]:
            return "isolated"
        if m["cpu"] >= 90 or (nf == "upf" and self.state["metrics"]["upf"]["packet_drop_pct"] > 5):
            return "degraded"
        return "ok"

    def _session(self, session_id: str) -> dict | None:
        return next((x for x in self.state["sessions"] if x["id"] == session_id), None)

    # ------------------------------------------------------------------
    # Diagnostics (read-only)
    # ------------------------------------------------------------------

    def get_logs(self, nf: str, last: int = 20) -> dict:
        return {"nf": nf, "lines": self.state["logs"][nf][-last:]}

    def get_metrics(self, nf: str | None = None) -> dict:
        m = self.state["metrics"]
        return copy.deepcopy(m[nf] if nf else m)

    def get_nf_health(self, nf: str | None = None) -> dict:
        names = [nf] if nf else list(NFS)
        return {n: self._health(n) for n in names}

    def list_gnbs(self) -> dict:
        s = self.state
        rate = {}
        for t in s["traffic"]["amf"]:
            if t.get("via") and t["source"] not in s["nfs"]["amf"]["blocked_sources"]:
                rate[t["via"]] = rate.get(t["via"], 0) + t["rate"]
        rows = [{**g, "registration_rate": rate.get(g["id"], 0) if g["connected"] else 0} for g in s["gnbs"]]
        return {"gnbs": rows,
                "unauthorised_connected": [g["id"] for g in s["gnbs"] if g["connected"] and not g["in_inventory"]]}

    def list_neighbors(self) -> dict:
        s = self.state
        return {"neighbors": list(s["neighbors"]),
                "unknown": [g for g in s["neighbors"] if g not in s["allowed_neighbors"]],
                "whitelist": s["nfs"]["gnb"]["config"]["neighbor_whitelist"]}

    def get_ran_kpis(self) -> dict:
        s, m = self.state, self.state["metrics"]["gnb"]
        reports = [{"cell": c, "pci": 999, "rsrp_dbm": -61, "area": "TA-4501", "reports_last_hour": 214,
                    "in_cell_inventory": False} for c in s["fake_cells"]]
        return {"area": "TA-4501", "fallback_to_lte_ues": m["fallback_to_lte_ues"],
                "radio_link_failures": m["radio_link_failures"], "unknown_cells_reported": reports,
                "hostile_cells": list(s["hostile_cells"]), "ignored_by_device_policy": list(s["device_policy"]["ignore_cells"]),
                "field_ticket_cells": [t["cell"] for t in s["field_tickets"]]}

    def check_auth_config(self) -> dict:
        a, cfg = self.state["auth"], self.state["nfs"]
        return {"method": a["method"], "ciphering": a["ciphering"], "integrity": a["integrity"],
                "suci_protection": cfg["udm"]["config"]["suci_protection"],
                "up_integrity": cfg["gnb"]["config"]["up_integrity"],
                "subscriber_keys_compromised": a["subscriber_keys_compromised"],
                "key_version": a["key_version"]}

    def check_interface_security(self) -> dict:
        return {k: dict(v) for k, v in self.state["interfaces"].items()}

    def get_top_talkers(self, nf: str, n: int = 5) -> dict:
        node = self.state["nfs"][nf]
        rows = sorted(self.state["traffic"][nf], key=lambda t: t["rate"], reverse=True)[:n]
        return {"nf": nf, "top": [{**t, "blocked": t["source"] in node["blocked_sources"],
                                   "path_connected": self._gnb_connected(t.get("via"))} for t in rows]}

    def check_api_access_log(self, nf: str) -> dict:
        s = self.state
        if nf == "nef":
            return {"nf": nf, "oauth2": s["nfs"]["nef"]["config"]["oauth2"],
                    "abusive_tokens": list(s["nef_tokens"]["abusive_tokens"]),
                    "calls_per_min": s["metrics"]["nef"]["api_calls_per_min"]}
        if nf == "udm":
            return {"nf": nf, "bulk_export": s["nfs"]["udm"]["config"]["bulk_export"],
                    "bulk_readers": self._bulk_readers()}
        return {"nf": nf, "note": "no API access log for this function"}

    def check_file_integrity(self, nf: str) -> dict:
        n = self.state["nfs"][nf]
        return {"nf": nf, "files_encrypted": n["files_encrypted"], "last_clean_backup": self.state["backups"][nf]}

    def list_registered_nfs(self) -> dict:
        s = self.state
        known = {"10.45.8.11", "10.45.8.12", "10.45.8.13"}
        return {"instances": copy.deepcopy(s["registered_nfs"]),
                "unsigned": [i["id"] for i in s["registered_nfs"] if not i["signed"]],
                "unexpected_hosts": [i["id"] for i in s["registered_nfs"] if i.get("host") not in known],
                "registration_auth": s["nfs"]["nrf"]["config"]["registration_auth"],
                "require_signed_nf_profiles": s["nfs"]["nrf"]["config"]["require_signed_nf_profiles"]}

    def get_egress_flows(self) -> dict:
        s = self.state
        active = [f for f in s["egress_flows"] if f["active"] and f["src"] not in s["isolated_instances"]]
        flows = [{**f, "active": f in active} for f in s["egress_flows"]]
        return {"active": [f"{f['src']}->{f['dst']}" for f in active], "flows": flows,
                "isolated_instances": list(s["isolated_instances"]), "evidence": copy.deepcopy(s["evidence"])}

    def check_mgmt_exposure(self) -> dict:
        c = self.state["nfs"]["oam"]["config"]
        return {"exposed_to_internet": c["exposed_to_internet"], "default_credentials": c["default_credentials"],
                "admin_access": c["admin_access"], "credentials_version": self.state["auth"]["oam_credentials_version"]}

    def check_slice_sessions(self, slice: str) -> dict:
        s = self.state
        allow = s["slices"][slice]["allow_list"]
        sessions = [x for x in s["sessions"] if x["slice"] == slice]
        return {"slice": slice, "allow_list": allow, "sessions": copy.deepcopy(sessions),
                "session_ids": [x["id"] for x in sessions],
                "not_on_allow_list": [x for x in sessions if allow is not None and x["supi"] not in allow]}

    def get_subscriber_changes(self) -> dict:
        changes = copy.deepcopy(self.state["subscriber_changes"])
        return {"changes": changes, "unreverted": [c for c in changes if not c["reverted"]]}

    def get_upf_flows(self) -> dict:
        s, sav = self.state, self.state["nfs"]["upf"]["config"]["source_address_validation"]
        live = [f for f in s["upf_flows"] if self._session(f["session"])]
        spoofed = [f for f in live if f["inner_src"] != f["assigned_ip"] and sav != "enabled"]
        internal = [f for f in live if f"{f['src_range']}->{f['dst_range']}" not in s["acl_blocks"]]
        return {"source_address_validation": sav, "flows": copy.deepcopy(s["upf_flows"]),
                "spoofed": copy.deepcopy(spoofed),
                "to_internal_ranges": copy.deepcopy(internal), "acl_blocks": list(s["acl_blocks"])}

    def get_device_stats(self, slice: str = "mmtc", top: int = 10) -> dict:
        s = self.state
        limit = s["slices"][slice].get("per_device_limit")
        rows = [{"device": d, "offered_rate": v["rate"], "effective_rate": min(v["rate"], limit) if limit else v["rate"],
                 "dst": v["dst"], "quarantined": d in s["quarantined_devices"]}
                for d, v in s["devices"].items() if v["slice"] == slice]
        rows.sort(key=lambda r: r["offered_rate"], reverse=True)
        anomalous = [r["device"] for r in rows if r["offered_rate"] > 50 and not r["quarantined"]]
        healthy_q = [d for d in s["quarantined_devices"] if d not in s["infected_devices"]]
        return {"slice": slice, "devices": len(rows), "per_device_limit": limit, "top": rows[:top],
                "anomalous": anomalous, "quarantined": list(s["quarantined_devices"]),
                "healthy_quarantined": len(healthy_q)}

    def get_flow_logs(self) -> dict:
        s = self.state
        dsts: dict[str, int] = {}
        for c in s["c2_contacts"]:
            dsts[c["dst"]] = dsts.get(c["dst"], 0) + 1
        common = sorted(dsts, key=dsts.get, reverse=True)
        return {"earlier_contacts": copy.deepcopy(s["c2_contacts"][:10]),
                "common_destinations": [{"dst": d, "devices": dsts[d],
                                         "blocked": d in s["blocked_destinations"]} for d in common],
                "c2_candidates": [d for d in common if dsts[d] >= 5],
                "unblocked_c2": [d for d in common if dsts[d] >= 5 and d not in s["blocked_destinations"]],
                "new_devices_contacting_c2": 5 if any(d not in s["blocked_destinations"] and dsts[d] >= 5
                                                      for d in common) else 0}

    def get_service_health(self, service: str) -> dict:
        svc = self.state["services"][service]
        inbound = self._device_flood() if svc["slice"] == "urllc-hospital" else 0
        if svc["filter"]:
            inbound = round(inbound * 0.05)
        load = 120 + inbound
        return {"service": service, "slice": svc["slice"], "inbound_rate": load, "capacity": svc["capacity"],
                "traffic_filter": svc["filter"], "status": "ok" if load <= svc["capacity"] else "degraded",
                "latency_ms": 40 if load <= svc["capacity"] else round(40 * load / svc["capacity"])}

    def get_alerts(self) -> dict:
        return {"alerts": list(self.state["alerts"])}

    # ------------------------------------------------------------------
    # Remediation (state-changing)
    # ------------------------------------------------------------------

    def _done(self, nf: str, message: str, **extra) -> dict:
        self.log(nf, "ACTION", message)
        self._recompute()
        self._save()
        return {"ok": True, "action": message, **extra}

    def rate_limit_nf(self, nf: str, limit: int) -> dict:
        self.state["nfs"][nf]["rate_limit"] = int(limit)
        return self._done(nf, f"rate limit set to {limit}/min")

    def block_source(self, nf: str, source: str) -> dict:
        blocked = self.state["nfs"][nf]["blocked_sources"]
        if source not in blocked:
            blocked.append(source)
        return self._done(nf, f"blocked source {source}")

    def isolate_nf(self, nf: str) -> dict:
        self.state["nfs"][nf]["isolated"] = True
        return self._done(nf, "isolated from the service mesh")

    def restore_nf(self, nf: str) -> dict:
        self.state["nfs"][nf]["isolated"] = False
        return self._done(nf, "re-attached to the service mesh")

    def disconnect_gnb(self, gnb_id: str) -> dict:
        g = next((g for g in self.state["gnbs"] if g["id"] == gnb_id), None)
        if g is None:
            return {"ok": False, "error": f"no base station {gnb_id!r} connected to the AMF"}
        g["connected"] = False
        return self._done("amf", f"NG setup of {gnb_id} released; base station disconnected and barred")

    def flag_cell_hostile(self, cell_id: str) -> dict:
        s = self.state
        if cell_id not in s["hostile_cells"]:
            s["hostile_cells"].append(cell_id)
        s["neighbors"] = [g for g in s["neighbors"] if g != cell_id]
        return self._done("gnb", f"cell {cell_id} flagged hostile and removed from neighbour lists")

    def push_device_policy(self, cell_id: str) -> dict:
        ignore = self.state["device_policy"]["ignore_cells"]
        if cell_id not in ignore:
            ignore.append(cell_id)
        return self._done("gnb", f"policy pushed to UEs in TA-4501: do not camp on or hand over to {cell_id}")

    def dispatch_field_team(self, cell_id: str) -> dict:
        if not any(t["cell"] == cell_id for t in self.state["field_tickets"]):
            self.state["field_tickets"].append({"cell": cell_id, "area": "TA-4501",
                                                "status": "handed off to the field team (real-world action, recorded only)"})
        return self._done("gnb", f"field-team ticket opened to locate the transmitter of {cell_id}")

    def rotate_keys(self, scope: str) -> dict:
        a = self.state["auth"]
        if scope == "subscriber":
            a["subscriber_keys_compromised"] = False
            a["key_version"] += 1
        elif scope == "oam_credentials":
            a["oam_credentials_version"] += 1
            self.state["nfs"]["oam"]["config"]["default_credentials"] = False
        elif scope == "nf_certificates":
            for inst in self.state["registered_nfs"]:
                inst["cert_rotated"] = True
        else:
            return {"ok": False, "error": f"unknown key scope {scope!r}"}
        return self._done("ausf" if scope == "subscriber" else "oam", f"rotated keys: {scope}")

    def restrict_admin_access(self) -> dict:
        self.state["nfs"]["oam"]["config"]["admin_access"] = "jump-host-only"
        return self._done("oam", "admin access restricted to the jump host")

    def reset_nf(self, nf: str) -> dict:
        n = self.state["nfs"][nf]
        n.update(status="running", rate_limit=None, isolated=False)
        return self._done(nf, "restarted with clean runtime state")

    def patch_config(self, nf: str, key: str, value: Any) -> dict:
        self.state["nfs"][nf]["config"][key] = value
        return self._done(nf, f"config {key} = {value!r}")

    def revoke_tokens(self, nf: str) -> dict:
        if nf == "nef":
            for t in self.state["nef_tokens"]["abusive_tokens"]:
                if t not in self.state["nfs"]["nef"]["blocked_sources"]:
                    self.state["nfs"]["nef"]["blocked_sources"].append(t)
            self.state["nef_tokens"]["abusive_tokens"] = []
        if nf == "udm":
            self.state["nfs"]["udm"]["blocked_sources"].extend(
                e for e in self.state["exfiltration"] if e not in self.state["nfs"]["udm"]["blocked_sources"])
        return self._done(nf, "revoked access tokens of abusive consumers")

    def enable_ipsec(self, interface: str) -> dict:
        self.state["interfaces"][interface]["ipsec"] = True
        return self._done("gnb", f"IPsec enabled on {interface}")

    def restore_from_backup(self, nf: str) -> dict:
        n = self.state["nfs"][nf]
        n.update(files_encrypted=False, status="running")
        return self._done(nf, f"restored from backup {self.state['backups'][nf]}")

    def deregister_nf(self, instance_id: str) -> dict:
        self.state["registered_nfs"] = [i for i in self.state["registered_nfs"] if i["id"] != instance_id]
        return self._done("nrf", f"deregistered NF instance {instance_id}")

    def capture_evidence(self, target: str) -> dict:
        s = self.state
        if target in s["isolated_instances"]:
            return {"ok": False, "error": f"{target} is already isolated and torn down; live evidence is lost"}
        if not any(e["target"] == target for e in s["evidence"]):
            s["evidence"].append({"target": target, "captured": ["container image digest", "process memory",
                                                                 "NRF registration record", "UDM query log",
                                                                 "egress flow records"]})
        return self._done("oam", f"forensic snapshot of {target} preserved")

    def isolate_instance(self, instance_id: str) -> dict:
        if instance_id not in self.state["isolated_instances"]:
            self.state["isolated_instances"].append(instance_id)
        return self._done("nrf", f"instance {instance_id} network-isolated (container quarantined)")

    def cut_flow(self, src: str) -> dict:
        for f in self.state["egress_flows"]:
            if f["src"] == src:
                f["active"] = False
        return self._done("upf", f"egress session from {src} terminated")

    def end_session(self, session_id: str) -> dict:
        sess = self._session(session_id)
        if sess is None:
            return {"ok": False, "error": f"no PDU session {session_id!r}"}
        self.state["sessions"].remove(sess)
        return self._done("smf", f"PDU session {session_id} ({sess['supi']}, {sess['slice']}) released")

    def restore_profile(self, supi: str) -> dict:
        s = self.state
        if supi not in s["subscriber_snapshot"]:
            return {"ok": False, "error": f"no known-good snapshot for {supi!r}"}
        s["subscribers"][supi] = copy.deepcopy(s["subscriber_snapshot"][supi])
        for c in s["subscriber_changes"]:
            if c["supi"] == supi:
                c["reverted"] = True
        return self._done("udm", f"subscription profile of {supi} restored from the known-good snapshot")

    def block_route(self, src_range: str, dst_range: str) -> dict:
        rule = f"{src_range}->{dst_range}"
        if rule not in self.state["acl_blocks"]:
            self.state["acl_blocks"].append(rule)
        return self._done("upf", f"ACL: drop {rule}")

    def rate_limit_slice(self, slice: str, per_device: int) -> dict:
        self.state["slices"][slice]["per_device_limit"] = int(per_device)
        return self._done("upf", f"slice {slice}: per-device rate limit {per_device}")

    def quarantine_devices(self, devices: list[str]) -> dict:
        if isinstance(devices, str):
            devices = [devices]
        unknown = [d for d in devices if d not in self.state["devices"]]
        if unknown:
            return {"ok": False, "error": f"unknown devices {unknown}"}
        q = self.state["quarantined_devices"]
        q.extend(d for d in devices if d not in q)
        return self._done("amf", f"{len(devices)} devices moved to the quarantine slice")

    def block_destination(self, address: str) -> dict:
        if address not in self.state["blocked_destinations"]:
            self.state["blocked_destinations"].append(address)
        return self._done("upf", f"traffic to {address} blocked for all slices")

    def enable_traffic_filter(self, service: str) -> dict:
        self.state["services"][service]["filter"] = True
        return self._done("upf", f"traffic filtering in front of {service} enabled")

    def close_mgmt_interface(self) -> dict:
        self.state["nfs"]["oam"]["config"]["exposed_to_internet"] = False
        return self._done("oam", "management interface closed to external networks")

    def scale_out(self, nf: str, replicas: int) -> dict:
        self.state["nfs"][nf]["replicas"] = int(replicas)
        return self._done(nf, f"scaled to {replicas} replicas")


DIAGNOSTICS = ("get_logs", "get_metrics", "get_nf_health", "list_gnbs", "list_neighbors", "get_ran_kpis",
               "check_auth_config", "check_interface_security", "get_top_talkers", "check_api_access_log",
               "check_file_integrity", "list_registered_nfs", "get_egress_flows", "check_mgmt_exposure",
               "check_slice_sessions", "get_subscriber_changes", "get_upf_flows", "get_device_stats",
               "get_flow_logs", "get_service_health", "get_alerts")
REMEDIATIONS = ("rate_limit_nf", "block_source", "isolate_nf", "restore_nf", "disconnect_gnb",
                "flag_cell_hostile", "push_device_policy", "dispatch_field_team", "rotate_keys",
                "restrict_admin_access", "reset_nf", "patch_config", "revoke_tokens", "enable_ipsec",
                "restore_from_backup", "deregister_nf", "capture_evidence", "isolate_instance", "cut_flow",
                "end_session", "restore_profile", "block_route", "rate_limit_slice", "quarantine_devices",
                "block_destination", "enable_traffic_filter", "close_mgmt_interface", "scale_out")
FUNCTIONS: dict[str, str] = {**{f: "diagnostic" for f in DIAGNOSTICS},
                             **{f: "remediation" for f in REMEDIATIONS}}


def call(sim: Sim, name: str, args: dict | None = None) -> dict:
    """Run a sim function by name (the only way the agent touches the sim)."""
    if name not in FUNCTIONS:
        return {"ok": False, "error": f"unknown function {name!r}"}
    fn: Callable = getattr(sim, name)
    try:
        return fn(**(args or {}))
    except (KeyError, TypeError, ValueError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def lookup(result: Any, path: str) -> Any:
    """'amf.cpu' / 'unknown' / 'N2.ipsec' / 'top.0.source' — dotted lookup in a function result."""
    value = result
    for part in path.split(".") if path else []:
        if isinstance(value, list):
            value = value[int(part)] if part.isdigit() and int(part) < len(value) else None
        else:
            value = value.get(part) if isinstance(value, dict) else None
    return value


def check(sim: Sim, condition: dict) -> tuple[bool, Any]:
    """Evaluate {"fn": name, "args": {...}, "path": "...", "op": "<", "value": v}."""
    if FUNCTIONS.get(condition["fn"]) != "diagnostic":
        raise ValueError(f"checks may only call diagnostics, not {condition['fn']!r}")
    actual = lookup(call(sim, condition["fn"], condition.get("args")), condition.get("path", ""))
    op, want = condition["op"], condition.get("value")
    ops: dict[str, Callable[[], bool]] = {
        "==": lambda: actual == want, "!=": lambda: actual != want,
        "<": lambda: actual is not None and actual < want, "<=": lambda: actual is not None and actual <= want,
        ">": lambda: actual is not None and actual > want, ">=": lambda: actual is not None and actual >= want,
        "empty": lambda: not actual,
        "not_contains": lambda: isinstance(actual, (list, str)) and want not in actual,
        "contains": lambda: isinstance(actual, (list, str)) and want in actual}
    return ops[op](), actual
