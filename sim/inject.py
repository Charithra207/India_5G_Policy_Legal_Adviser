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
    # one base station that is not in the cell inventory carries the whole storm
    s["gnbs"].append({"id": "gnb-207", "in_inventory": False, "connected": True})
    s["traffic"]["amf"] += [{"source": "ue-range-404-45-77xx", "rate": 7800, "via": "gnb-207"},
                            {"source": "ue-range-404-45-12xx", "rate": 900, "via": "gnb-102"}]
    sim.log("amf", "INFO", "NG setup request from gnb-207 (not in the cell inventory) accepted")
    for _ in range(5):
        sim.log("amf", "WARN", "registration request burst: 7800/min via gnb-207 from ue-range-404-45-77xx "
                               "(initial registrations, repeated SUCI, no service request)")
    sim.log("amf", "ERROR", "N1/N2 message queue above 95%; registration latency 4.8 s")
    sim.log("amf", "WARN", "registration reject (cause #22 congestion) for UEs on gnb-101/102/103")
    sim.alert("AMF CPU above 90% for 3 consecutive ticks; legitimate registrations failing")


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
    s["fake_cells"].append("gnb-666")
    s["nfs"]["gnb"]["config"]["neighbor_whitelist"] = "disabled"
    sim.log("gnb", "WARN", "measurement reports from 214 UEs in TA-4501 list cell gnb-666 (PCI 999, RSRP -61 dBm); "
                           "no such cell in the cell inventory")
    sim.log("gnb", "WARN", "38 UEs in TA-4501 fell back to LTE and 12 radio link failures in 10 min")
    sim.log("amf", "WARN", "registration attempts with downgraded security capabilities from UEs in TA-4501")
    sim.alert("UE measurement reports show a cell that is not in the cell inventory (TA-4501)")


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
    s["nfs"]["nrf"]["config"]["registration_auth"] = "disabled"
    s["nfs"]["nrf"]["config"]["require_signed_nf_profiles"] = False
    s["registered_nfs"].append({"id": "nf-x9", "type": "SMF", "signed": False, "host": "10.45.9.99"})
    s["rogue_instances"].append("nf-x9")
    s["exfiltration"].append("nf-x9")
    s["traffic"]["udm"].append({"source": "nf-x9", "rate": 40})
    s["egress_flows"].append({"src": "nf-x9", "dst": "203.0.113.200:443", "kbps": 96, "active": True})
    sim.log("nrf", "INFO", "NF instance nf-x9 (SMF) registered from 10.45.9.99 without client authentication; "
                           "image digest not in the approved list")
    sim.log("udm", "INFO", "Nudm_SDM_Get from nf-x9: 1,240 SUPIs in 6 h (an SMF normally queries 0 full profiles)")
    sim.log("upf", "INFO", "steady 96 kbps upload 10.45.9.99 -> 203.0.113.200:443 for 6 h")
    sim.alert("NRF registration from an unexpected host (10.45.9.99)")


def _subscriber_profile_tampering(sim: Sim) -> None:
    s = sim.state
    supi = "imsi-404450000000777"
    s["nfs"]["oam"]["config"]["default_credentials"] = True
    s["nfs"]["oam"]["config"]["admin_access"] = "any-internal"
    s["subscribers"][supi]["slices"].append("urllc-hospital")
    s["subscriber_changes"].append({"supi": supi, "field": "allowed_slices", "old": ["embb"],
                                    "new": ["embb", "urllc-hospital"], "by": "admin", "from": "10.20.30.77",
                                    "reverted": False})
    s["sessions"].append({"id": "pdu-9001", "supi": supi, "slice": "urllc-hospital", "ue_ip": "10.46.0.177"})
    sim.log("oam", "INFO", "admin login (default account 'admin') from 10.20.30.77; usual source is the jump host")
    sim.log("udm", "INFO", f"subscription data updated for {supi}: allowed NSSAI += urllc-hospital (by admin)")
    sim.log("smf", "INFO", f"PDU session pdu-9001 established for {supi} on S-NSSAI urllc-hospital")
    sim.alert("Session on urllc-hospital from a subscriber that is not on the slice allow-list")


def _gtpu_spoofing_upf(sim: Sim) -> None:
    s = sim.state
    s["nfs"]["upf"]["config"]["source_address_validation"] = "disabled"
    s["upf_flows"].append({"session": "pdu-5001", "supi": "imsi-404450000000555", "assigned_ip": "10.45.0.55",
                           "inner_src": "10.45.0.12", "dst": "10.10.0.5:22", "src_range": "10.45.0.0/16",
                           "dst_range": "10.10.0.0/16", "pps": 812})
    sim.log("upf", "WARN", "pdu-5001 (UE IP 10.45.0.55): 812 pkt/s with inner source 10.45.0.12, "
                           "which does not match the session address")
    sim.log("upf", "WARN", "GTP-U payload from pdu-5001 to 10.10.0.5:22 (OAM management range)")
    sim.alert("UPF: user-plane packets with a spoofed inner source towards the management range")


INFECTED = [f"meter-{i:04d}" for i in (2, 3, 5, 7, 8, 11, 12, 14, 15, 17, 19, 20, 22, 23, 25, 26,
                                        28, 29, 31, 32, 34, 35, 37, 38)]


def _iot_botnet_mmtc(sim: Sim) -> None:
    s = sim.state
    s["infected_devices"] = list(INFECTED)
    for d in INFECTED:
        s["devices"][d].update(rate=300, dst="hospital-portal")
        s["c2_contacts"].append({"device": d, "dst": "203.0.113.66:23", "at": "08:12"})
    s["c2_contacts"] += [{"device": "meter-0004", "dst": "198.51.100.20:443", "at": "08:30"},
                         {"device": "meter-0010", "dst": "198.51.100.20:443", "at": "08:31"}]
    sim.log("upf", "WARN", "24 devices on slice mmtc: rate up from 1 to 300 msg/min, all towards hospital-portal")
    sim.log("upf", "INFO", "flow log: 24 mmtc devices opened sessions to 203.0.113.66:23 between 08:10 and 08:14")
    sim.log("smf", "WARN", "hospital-portal (slice urllc-hospital) latency 290 ms, availability degraded")
    sim.alert("hospital-portal degraded: synchronised traffic from many mMTC devices")


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
    "subscriber_profile_tampering": _subscriber_profile_tampering,
    "gtpu_spoofing_upf": _gtpu_spoofing_upf,
    "iot_botnet_mmtc": _iot_botnet_mmtc,
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
