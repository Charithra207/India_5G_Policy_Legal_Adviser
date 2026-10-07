"""
Simulated 5G core — a contained, deterministic lab target.
==========================================================
Everything here is in-process Python state.  Nothing opens a socket, scans,
or touches any real host or network: the "network functions" are dicts, the
"attacks" (sim/inject.py) flip fields in those dicts, and the "fixes" below
flip them back.  State is written to <work>/state.json and logs to
<work>/logs/<nf>.log, where <work> is $LAB_WORK_DIR or sim/.

Network functions: gNB, AMF, SMF, UPF, UDM, AUSF, NEF, NRF and an OAM
(management) endpoint.

Two kinds of functions, both listed in FUNCTIONS with their kind:
  diagnostic   read-only:  get_logs, get_metrics, get_nf_health, list_neighbors,
               check_auth_config, check_interface_security, get_top_talkers,
               check_api_access_log, check_file_integrity, list_registered_nfs,
               check_mgmt_exposure, get_alerts
  remediation  state-changing: rate_limit_nf, block_source, isolate_nf,
               restore_nf, block_neighbor, rotate_keys, reset_nf, patch_config,
               revoke_tokens, enable_ipsec, restore_from_backup, deregister_nf,
               close_mgmt_interface, scale_out
Derived metrics (CPU, rates, drops) are recomputed from the state after every
action, so a fix has a visible, checkable effect.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Callable

NFS = ("gnb", "amf", "smf", "upf", "udm", "ausf", "nef", "nrf", "oam")


def work_dir() -> Path:
    return Path(os.environ.get("LAB_WORK_DIR", Path(__file__).resolve().parent))


def _baseline() -> dict:
    nf = lambda **kw: {"status": "running", "isolated": False, "replicas": 1, "rate_limit": None,  # noqa: E731
                       "blocked_sources": [], "files_encrypted": False, "config": {}, **kw}
    return {
        "tick": 0,
        "attack": None,                 # id of the injected attack, if any
        "nfs": {
            "gnb": nf(config={"neighbor_whitelist": "enforced", "up_integrity": "required"}),
            "amf": nf(config={"overload_control": "enabled", "max_registration_rate": 1500}),
            "smf": nf(), "upf": nf(), "ausf": nf(),
            "udm": nf(config={"suci_protection": "profile_A", "bulk_export": "disabled"}),
            "nef": nf(config={"oauth2": "required"}),
            "nrf": nf(config={"require_signed_nf_profiles": True}),
            "oam": nf(config={"exposed_to_internet": False, "default_credentials": False}),
        },
        "neighbors": ["gnb-101", "gnb-102", "gnb-103"],
        "allowed_neighbors": ["gnb-101", "gnb-102", "gnb-103"],
        "auth": {"method": "5G-AKA", "ciphering": "NEA2", "integrity": "NIA2",
                 "subscriber_keys_compromised": False, "key_version": 1, "oam_credentials_version": 1},
        "interfaces": {"N2": {"ipsec": True}, "N3": {"ipsec": True}},
        "nef_tokens": {"valid_tokens": ["af-partner-1"], "abusive_tokens": []},
        "registered_nfs": [
            {"id": "smf-01", "type": "SMF", "signed": True},
            {"id": "upf-01", "type": "UPF", "signed": True},
            {"id": "udm-01", "type": "UDM", "signed": True},
        ],
        "backups": {n: "clean-2026-10-06" for n in NFS},
        # attack inputs: traffic sources and their request rates
        "traffic": {n: [] for n in NFS},     # [{"source": str, "rate": int}]
        "exfiltration": [],                  # active bulk reads from the UDM
        "alerts": [],
        "metrics": {},
        "logs": {n: [] for n in NFS},
    }


class Sim:
    """One simulated core.  All functions return plain dicts (JSON-serialisable)."""

    def __init__(self, persist: bool = True) -> None:
        self.persist = persist
        self.state: dict = {}
        self.reset()

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
    def resume(cls) -> "Sim":
        """A Sim continuing from <work>/state.json (without first saving a fresh baseline)."""
        sim = cls(persist=False)
        sim.load()
        sim.persist = True
        return sim

    def load(self) -> dict:
        """Continue from <work>/state.json and logs (e.g. after an operator ran sim.cli)."""
        root = work_dir()
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
        line = f"t={self.state['tick']:04d} {level:<5} {nf.upper():<4} {message}"
        self.state["logs"][nf].append(line)
        self.state["logs"][nf] = self.state["logs"][nf][-500:]

    def alert(self, text: str) -> None:
        if text not in self.state["alerts"]:
            self.state["alerts"].append(text)

    def _save(self) -> None:
        if not self.persist:
            return
        root = work_dir()
        (root / "logs").mkdir(parents=True, exist_ok=True)
        public = {k: v for k, v in self.state.items() if k != "logs"}
        (root / "state.json").write_text(json.dumps(public, indent=2), encoding="utf-8")
        for nf, lines in self.state["logs"].items():
            (root / "logs" / f"{nf}.log").write_text("\n".join(lines) + ("\n" if lines else ""),
                                                     encoding="utf-8")

    # ------------------------------------------------------------------
    # Derived metrics
    # ------------------------------------------------------------------

    def _offered(self, nf: str) -> int:
        n = self.state["nfs"][nf]
        return sum(t["rate"] for t in self.state["traffic"][nf] if t["source"] not in n["blocked_sources"])

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
        m["amf"]["registration_rate"] = m["amf"]["accepted_rate"]
        m["upf"]["packet_drop_pct"] = round(max(0.0, 100 * (1 - 2000 * s["nfs"]["upf"]["replicas"]
                                                       / max(m["upf"]["accepted_rate"], 1))), 1)
        m["nef"]["api_calls_per_min"] = m["nef"]["accepted_rate"]
        m["udm"]["bulk_reads_active"] = len([e for e in s["exfiltration"]
                                            if e not in s["nfs"]["udm"]["blocked_sources"]])
        m["active_pdu_sessions"] = 0 if s["nfs"]["smf"]["files_encrypted"] else 1200
        m["registered_ues"] = 5000
        s["metrics"] = m

    def _health(self, nf: str) -> str:
        n, m = self.state["nfs"][nf], self.state["metrics"][nf]
        if n["files_encrypted"]:
            return "down"
        if n["isolated"]:
            return "isolated"
        if m["cpu"] >= 90 or (nf == "upf" and self.state["metrics"]["upf"]["packet_drop_pct"] > 5):
            return "degraded"
        return "ok"

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

    def list_neighbors(self) -> dict:
        s = self.state
        return {"neighbors": list(s["neighbors"]),
                "unknown": [g for g in s["neighbors"] if g not in s["allowed_neighbors"]],
                "whitelist": s["nfs"]["gnb"]["config"]["neighbor_whitelist"]}

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
        return {"nf": nf, "top": [{**t, "blocked": t["source"] in node["blocked_sources"]} for t in rows]}

    def check_api_access_log(self, nf: str) -> dict:
        s = self.state
        if nf == "nef":
            return {"nf": nf, "oauth2": s["nfs"]["nef"]["config"]["oauth2"],
                    "abusive_tokens": list(s["nef_tokens"]["abusive_tokens"]),
                    "calls_per_min": s["metrics"]["nef"]["api_calls_per_min"]}
        if nf == "udm":
            return {"nf": nf, "bulk_export": s["nfs"]["udm"]["config"]["bulk_export"],
                    "bulk_readers": [e for e in s["exfiltration"] if e not in s["nfs"]["udm"]["blocked_sources"]]}
        return {"nf": nf, "note": "no API access log for this function"}

    def check_file_integrity(self, nf: str) -> dict:
        n = self.state["nfs"][nf]
        return {"nf": nf, "files_encrypted": n["files_encrypted"], "last_clean_backup": self.state["backups"][nf]}

    def list_registered_nfs(self) -> dict:
        return {"instances": copy.deepcopy(self.state["registered_nfs"]),
                "unsigned": [i["id"] for i in self.state["registered_nfs"] if not i["signed"]],
                "require_signed_nf_profiles": self.state["nfs"]["nrf"]["config"]["require_signed_nf_profiles"]}

    def check_mgmt_exposure(self) -> dict:
        c = self.state["nfs"]["oam"]["config"]
        return {"exposed_to_internet": c["exposed_to_internet"], "default_credentials": c["default_credentials"],
                "credentials_version": self.state["auth"]["oam_credentials_version"]}

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

    def block_neighbor(self, gnb_id: str) -> dict:
        s = self.state
        s["neighbors"] = [g for g in s["neighbors"] if g != gnb_id]
        return self._done("gnb", f"removed neighbour {gnb_id} and barred it")

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

    def close_mgmt_interface(self) -> dict:
        self.state["nfs"]["oam"]["config"]["exposed_to_internet"] = False
        return self._done("oam", "management interface closed to external networks")

    def scale_out(self, nf: str, replicas: int) -> dict:
        self.state["nfs"][nf]["replicas"] = int(replicas)
        return self._done(nf, f"scaled to {replicas} replicas")


DIAGNOSTICS = ("get_logs", "get_metrics", "get_nf_health", "list_neighbors", "check_auth_config",
               "check_interface_security", "get_top_talkers", "check_api_access_log",
               "check_file_integrity", "list_registered_nfs", "check_mgmt_exposure", "get_alerts")
REMEDIATIONS = ("rate_limit_nf", "block_source", "isolate_nf", "restore_nf", "block_neighbor",
                "rotate_keys", "reset_nf", "patch_config", "revoke_tokens", "enable_ipsec",
                "restore_from_backup", "deregister_nf", "close_mgmt_interface", "scale_out")
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
    """'amf.cpu' / 'unknown' / 'N2.ipsec' — dotted lookup in a function result."""
    value = result
    for part in path.split(".") if path else []:
        value = value[int(part)] if isinstance(value, list) else value.get(part) if isinstance(value, dict) else None
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
