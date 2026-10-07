"""
Attack injector for the simulated 5G core (contained lab).
==========================================================
    python -m sim.inject --attack signalling_storm_amf
    python -m sim.inject --list

An "attack" here is a deterministic edit of the simulation's in-memory
state (sim/engine.py): it adds synthetic traffic entries, flips a config
flag, adds a neighbour id to a list, and writes the log lines and alerts an
operator would see.  It sends nothing anywhere and contains no exploit code.
"""

from __future__ import annotations

import argparse
import sys

from sim.engine import Sim


def _signalling_storm_amf(sim: Sim) -> None:
    s = sim.state
    s["traffic"]["amf"] += [{"source": "ue-range-404-45-77xx", "rate": 7800},
                            {"source": "ue-range-404-45-12xx", "rate": 900}]
    for _ in range(6):
        sim.log("amf", "WARN", "registration request burst: 7800/min from ue-range-404-45-77xx "
                               "(initial registrations, repeated SUCI, no service request)")
    sim.log("amf", "ERROR", "N1/N2 message queue above 95%; registration latency 4.8 s")
    sim.alert("AMF CPU above 90% for 3 consecutive ticks (registration storm suspected)")


def _core_ddos_upf(sim: Sim) -> None:
    s = sim.state
    s["traffic"]["upf"] += [{"source": f"dn-host-198.51.100.{i}", "rate": r}
                            for i, r in ((11, 2600), (12, 2400), (13, 2200))]
    sim.log("upf", "ERROR", "N6 ingress 7.6 Gbps against 2 Gbps capacity; GTP-U buffers full")
    sim.log("upf", "WARN", "packet drops on N3 for all slices")
    sim.alert("UPF packet drop above 5% (volumetric traffic on N6)")


def _rogue_base_station(sim: Sim) -> None:
    s = sim.state
    s["neighbors"].append("gnb-666")
    s["nfs"]["udm"]["config"]["suci_protection"] = "null-scheme"
    s["nfs"]["gnb"]["config"]["neighbor_whitelist"] = "disabled"
    sim.log("gnb", "WARN", "measurement reports list cell gnb-666 (PCI 999, unknown PLMN) at high RSRP")
    sim.log("amf", "WARN", "identity requests answered with null-scheme SUCI from 37 UEs near gnb-666")
    sim.alert("Unknown neighbour gnb-666 not in the planned neighbour list")


def _subscriber_cred_compromise(sim: Sim) -> None:
    s = sim.state
    s["auth"]["subscriber_keys_compromised"] = True
    sim.log("ausf", "WARN", "successful 5G-AKA for SUPI imsi-404450000001234 from two TAs 900 km apart in 2 min")
    sim.log("ausf", "WARN", "same SUPI authenticated on 3 devices (IMEI mismatch)")
    sim.alert("Possible cloned credentials: concurrent authentications for one SUPI")


def _sba_api_abuse_nef(sim: Sim) -> None:
    s = sim.state
    s["nfs"]["nef"]["config"]["oauth2"] = "optional"
    s["nef_tokens"]["abusive_tokens"] = ["af-unknown-77"]
    s["traffic"]["nef"].append({"source": "af-unknown-77", "rate": 4200})
    sim.log("nef", "WARN", "4200 calls/min to Nnef_EventExposure from af-unknown-77 without OAuth2 token")
    sim.alert("NEF API call rate 20x baseline from an unregistered application function")


def _subscriber_data_exfiltration(sim: Sim) -> None:
    s = sim.state
    s["nfs"]["udm"]["config"]["bulk_export"] = "enabled"
    s["exfiltration"].append("consumer-app-x")
    s["traffic"]["udm"].append({"source": "consumer-app-x", "rate": 1500})
    sim.log("udm", "WARN", "consumer-app-x read 48,000 subscriber profiles (SUPI, MSISDN, location) in 10 min")
    sim.alert("Bulk subscriber-data reads from consumer-app-x (possible personal-data exfiltration)")


def _nf_host_ransomware(sim: Sim) -> None:
    s = sim.state
    s["nfs"]["smf"]["files_encrypted"] = True
    s["nfs"]["smf"]["status"] = "crashed"
    sim.log("smf", "ERROR", "configuration and session store unreadable: files renamed *.locked")
    sim.log("smf", "ERROR", "ransom note found on SMF host; PDU session establishment failing")
    sim.alert("SMF down: host files encrypted")


def _exposed_mgmt_interface(sim: Sim) -> None:
    c = sim.state["nfs"]["oam"]["config"]
    c["exposed_to_internet"] = True
    c["default_credentials"] = True
    sim.log("oam", "WARN", "management login from external address 203.0.113.50 with the default admin account")
    sim.alert("OAM interface reachable from outside the operator network")


def _n2_n3_mitm(sim: Sim) -> None:
    s = sim.state
    s["interfaces"]["N2"]["ipsec"] = False
    s["interfaces"]["N3"]["ipsec"] = False
    s["nfs"]["gnb"]["config"]["up_integrity"] = "not_used"
    sim.log("gnb", "WARN", "N2/N3 transport without IPsec after transport-network change")
    sim.log("upf", "WARN", "GTP-U packets with unexpected TEIDs from an unknown hop")
    sim.alert("Backhaul (N2/N3) running unprotected; possible interception")


def _supply_chain_rogue_nf(sim: Sim) -> None:
    s = sim.state
    s["registered_nfs"].append({"id": "smf-x9", "type": "SMF", "signed": False})
    s["nfs"]["nrf"]["config"]["require_signed_nf_profiles"] = False
    sim.log("nrf", "WARN", "NF instance smf-x9 registered with an unsigned profile and an unapproved image digest")
    sim.alert("Unsigned NF instance smf-x9 in the NRF registry")


ATTACKS = {
    "signalling_storm_amf": _signalling_storm_amf,
    "core_ddos_upf": _core_ddos_upf,
    "rogue_base_station": _rogue_base_station,
    "subscriber_cred_compromise": _subscriber_cred_compromise,
    "sba_api_abuse_nef": _sba_api_abuse_nef,
    "subscriber_data_exfiltration": _subscriber_data_exfiltration,
    "nf_host_ransomware": _nf_host_ransomware,
    "exposed_mgmt_interface": _exposed_mgmt_interface,
    "n2_n3_mitm": _n2_n3_mitm,
    "supply_chain_rogue_nf": _supply_chain_rogue_nf,
}


def inject(sim: Sim, attack_id: str) -> dict:
    if attack_id not in ATTACKS:
        raise ValueError(f"unknown attack {attack_id!r}; known: {sorted(ATTACKS)}")
    sim.state["attack"] = attack_id
    ATTACKS[attack_id](sim)
    sim.tick()
    return {"ok": True, "attack": attack_id, "alerts": list(sim.state["alerts"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attack")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    if args.list or not args.attack:
        print("\n".join(sorted(ATTACKS)))
        return 0
    sim = Sim()                       # fresh baseline, then the attack
    result = inject(sim, args.attack)
    print(f"injected {result['attack']} into the simulation (state: sim/state.json)")
    for a in result["alerts"]:
        print("  ALERT:", a)
    print("  health:", sim.get_nf_health())
    return 0


if __name__ == "__main__":
    sys.exit(main())
