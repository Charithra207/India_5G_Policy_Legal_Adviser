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
_SLICE = {"type": "string", "enum": ["embb", "urllc-hospital", "mmtc"], "description": "network slice"}
_STR = {"type": "string"}

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
    "list_gnbs": ("Base stations connected to the AMF: in the cell inventory or not, registration rate each.", {}, []),
    "get_ran_kpis": ("RAN KPIs for TA-4501: LTE fallbacks, radio link failures, cells UEs report that are not in "
                     "the inventory, hostile/ignored cells and field tickets.", {}, []),
    "get_egress_flows": ("Active outbound flows from core hosts, isolated instances, preserved evidence.", {}, []),
    "check_slice_sessions": ("PDU sessions on a slice, its allow-list, and sessions not on the allow-list.",
                             {"slice": _SLICE}, ["slice"]),
    "get_subscriber_changes": ("Subscriber-database change records (who changed which profile, from where).", {}, []),
    "get_upf_flows": ("UPF source-address validation state, flows with spoofed inner source, flows to internal "
                      "ranges, ACL blocks.", {}, []),
    "get_device_stats": ("Per-device traffic on a slice (offered/effective rate, destination), anomalous devices, "
                         "quarantined devices.", {"slice": _SLICE, "top": {"type": "integer", "minimum": 1,
                                                                          "maximum": 40}}, []),
    "get_flow_logs": ("Earlier connections from devices to outside destinations; destinations many devices "
                      "contacted (command-server candidates).", {}, []),
    "get_service_health": ("Inbound load, status and latency of a service.",
                           {"service": {"type": "string", "enum": ["hospital-portal"]}}, ["service"]),
    "rate_limit_nf": ("STATE-CHANGING: cap the request rate accepted by an NF.",
                      {"nf": _NF, "limit": {"type": "integer", "minimum": 1}}, ["nf", "limit"]),
    "block_source": ("STATE-CHANGING: block one traffic source / consumer at an NF.",
                     {"nf": _NF, "source": {"type": "string"}}, ["nf", "source"]),
    "isolate_nf": ("STATE-CHANGING: isolate an NF from the service mesh (stops its traffic).", {"nf": _NF}, ["nf"]),
    "restore_nf": ("STATE-CHANGING: re-attach an isolated NF.", {"nf": _NF}, ["nf"]),
    "disconnect_gnb": ("STATE-CHANGING: release a base station's NG connection to the AMF and bar it.",
                       {"gnb_id": _STR}, ["gnb_id"]),
    "flag_cell_hostile": ("STATE-CHANGING: flag a cell id as hostile and remove it from neighbour lists.",
                          {"cell_id": _STR}, ["cell_id"]),
    "push_device_policy": ("STATE-CHANGING: tell UEs in the area not to camp on or hand over to a cell.",
                           {"cell_id": _STR}, ["cell_id"]),
    "dispatch_field_team": ("STATE-CHANGING: open a field-team ticket to locate a transmitter (recorded handoff).",
                            {"cell_id": _STR}, ["cell_id"]),
    "restrict_admin_access": ("STATE-CHANGING: allow admin logins only from the jump host.", {}, []),
    "capture_evidence": ("STATE-CHANGING: preserve a forensic snapshot of a component before containment.",
                         {"target": _STR}, ["target"]),
    "isolate_instance": ("STATE-CHANGING: network-isolate a (rogue) NF instance / container.",
                         {"instance_id": _STR}, ["instance_id"]),
    "cut_flow": ("STATE-CHANGING: terminate outbound flows from a source.", {"src": _STR}, ["src"]),
    "end_session": ("STATE-CHANGING: release a PDU session.", {"session_id": _STR}, ["session_id"]),
    "restore_profile": ("STATE-CHANGING: restore a subscriber profile from the known-good snapshot.",
                        {"supi": _STR}, ["supi"]),
    "block_route": ("STATE-CHANGING: UPF ACL dropping traffic from one address range to another.",
                    {"src_range": _STR, "dst_range": _STR}, ["src_range", "dst_range"]),
    "rate_limit_slice": ("STATE-CHANGING: per-device rate limit on a slice.",
                         {"slice": _SLICE, "per_device": {"type": "integer", "minimum": 1}}, ["slice", "per_device"]),
    "quarantine_devices": ("STATE-CHANGING: move devices to the quarantine slice (only infected ones!).",
                           {"devices": {"type": "array", "items": _STR, "minItems": 1}}, ["devices"]),
    "block_destination": ("STATE-CHANGING: block traffic to an outside address for all slices.",
                          {"address": _STR}, ["address"]),
    "enable_traffic_filter": ("STATE-CHANGING: enable traffic filtering in front of a service.",
                              {"service": {"type": "string", "enum": ["hospital-portal"]}}, ["service"]),
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
