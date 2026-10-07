"""
Tool definitions for the incident-response agent.
=================================================
One tool per simulator function (sim/engine.py) plus:
  search_kb            — category-filtered search of the prebuilt KB index
  report_tier_outcome  — the agent's account of the tier (the engine still
                         decides "resolved" itself from the catalog checks)

The engine exposes only the tools a tier needs: every diagnostic, the
remediations its playbook steps use, search_kb and report_tier_outcome.
"""

from __future__ import annotations

from sim.engine import FUNCTIONS, NFS

_NF = {"type": "string", "enum": list(NFS), "description": "network function"}

_SCHEMAS: dict[str, tuple[str, dict, list[str]]] = {
    "get_logs": ("Recent log lines of a network function.",
                 {"nf": _NF, "last": {"type": "integer", "minimum": 1, "maximum": 200}}, ["nf"]),
    "get_metrics": ("Metrics (CPU, offered/accepted rates, drops) of one NF, or all if nf omitted.",
                    {"nf": _NF}, []),
    "get_nf_health": ("Health (ok/degraded/isolated/down) of one NF, or all if nf omitted.", {"nf": _NF}, []),
    "list_neighbors": ("gNB neighbour list, unknown neighbours and whitelist mode.", {}, []),
    "check_auth_config": ("Authentication/security settings: 5G-AKA, ciphering, SUCI protection, key state.", {}, []),
    "check_interface_security": ("IPsec status of N2 and N3.", {}, []),
    "get_top_talkers": ("Highest-rate traffic sources towards an NF.",
                        {"nf": _NF, "n": {"type": "integer", "minimum": 1, "maximum": 20}}, ["nf"]),
    "check_api_access_log": ("API access summary for nef or udm.", {"nf": _NF}, ["nf"]),
    "check_file_integrity": ("Whether an NF host's files are encrypted; last clean backup.", {"nf": _NF}, ["nf"]),
    "list_registered_nfs": ("NF instances registered in the NRF and whether they are signed.", {}, []),
    "check_mgmt_exposure": ("Whether the OAM interface is exposed and uses default credentials.", {}, []),
    "get_alerts": ("Active alerts.", {}, []),
    "rate_limit_nf": ("STATE-CHANGING: cap the request rate accepted by an NF.",
                      {"nf": _NF, "limit": {"type": "integer", "minimum": 1}}, ["nf", "limit"]),
    "block_source": ("STATE-CHANGING: block one traffic source / consumer at an NF.",
                     {"nf": _NF, "source": {"type": "string"}}, ["nf", "source"]),
    "isolate_nf": ("STATE-CHANGING: isolate an NF from the service mesh (stops its traffic).", {"nf": _NF}, ["nf"]),
    "restore_nf": ("STATE-CHANGING: re-attach an isolated NF.", {"nf": _NF}, ["nf"]),
    "block_neighbor": ("STATE-CHANGING: remove and bar a gNB neighbour.", {"gnb_id": {"type": "string"}}, ["gnb_id"]),
    "rotate_keys": ("STATE-CHANGING: rotate keys/credentials.",
                    {"scope": {"type": "string", "enum": ["subscriber", "oam_credentials", "nf_certificates"]}},
                    ["scope"]),
    "reset_nf": ("STATE-CHANGING: restart an NF with clean runtime state.", {"nf": _NF}, ["nf"]),
    "patch_config": ("STATE-CHANGING: set one configuration key of an NF.",
                     {"nf": _NF, "key": {"type": "string"},
                      "value": {"type": ["string", "number", "boolean"]}}, ["nf", "key", "value"]),
    "revoke_tokens": ("STATE-CHANGING: revoke access tokens of abusive consumers (nef/udm).", {"nf": _NF}, ["nf"]),
    "enable_ipsec": ("STATE-CHANGING: enable IPsec on an interface.",
                     {"interface": {"type": "string", "enum": ["N2", "N3"]}}, ["interface"]),
    "restore_from_backup": ("STATE-CHANGING: restore an NF host from its last clean backup.", {"nf": _NF}, ["nf"]),
    "deregister_nf": ("STATE-CHANGING: deregister an NF instance from the NRF.",
                      {"instance_id": {"type": "string"}}, ["instance_id"]),
    "close_mgmt_interface": ("STATE-CHANGING: close the OAM interface to external networks.", {}, []),
    "scale_out": ("STATE-CHANGING: set the replica count of an NF.",
                  {"nf": _NF, "replicas": {"type": "integer", "minimum": 1, "maximum": 8}}, ["nf", "replicas"]),
}
assert set(_SCHEMAS) == set(FUNCTIONS), "every simulator function needs a tool schema"

SEARCH_KB = {
    "name": "search_kb",
    "description": "Search the incident-response knowledge base (Indian telecom law and rules, CERT-In, "
                   "DPDP, 3GPP, ENISA, NIST) within this attack's categories. Returns passages with file "
                   "and page citations.",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}},
                     "required": ["query"], "additionalProperties": False},
}
REPORT = {
    "name": "report_tier_outcome",
    "description": "Call once when you have finished this tier: whether you believe the incident is "
                   "resolved, and a short summary of what you did and found.",
    "input_schema": {"type": "object",
                     "properties": {"resolved": {"type": "boolean"}, "summary": {"type": "string"}},
                     "required": ["resolved", "summary"], "additionalProperties": False},
}


def sim_tool(name: str) -> dict:
    description, props, required = _SCHEMAS[name]
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": props, "required": required,
                             "additionalProperties": False}}


def tools_for_tier(steps: list[dict]) -> list[dict]:
    """All diagnostics, the remediations this tier's steps use, KB search, outcome report."""
    remediations = {s["action"]["fn"] for s in steps if s["is_state_changing"]}
    names = [n for n, kind in FUNCTIONS.items() if kind == "diagnostic" or n in remediations]
    return [sim_tool(n) for n in names] + [SEARCH_KB, REPORT]
