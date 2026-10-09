"""
Training and exercise data for the simulated 5G core (contained lab).
=====================================================================
The simulator in sim/engine.py is deterministic; real networks are not.
This module adds what a learning system has to cope with, all of it seeded
so a run can be reproduced:

  background load     legitimate traffic on the AMF, UPF, NEF, UDM and SMF,
                      re-drawn at every step and scaled by a load factor
                      (load 1.0 = the level the models are trained on;
                      "drift" = the live network's load moving away from it)
  benign events       look-alikes that must NOT be reported as attacks:
                        flash_crowd         a registration surge through our
                                            own base stations (stadium, outage
                                            recovery)
                        billing_batch       a large, authorised UDM read job
                        maintenance_window  one security setting relaxed for
                                            planned work (one at a time, which
                                            attacks rarely do)
  attack intensity    the traffic an attack adds is scaled (0.3x-1.3x), so
                      weak and strong variants both occur

`run_episode` drives one simulation through an episode and calls `poll` at
each sampling point; the caller (the ML sandbox in src/y3172/mlfo.py)
collects the telemetry.  Nothing here reaches a real network.
"""

from __future__ import annotations

import random
from typing import Callable

from sim.engine import Sim
from sim.inject import ATTACKS, inject

NORMAL = "normal"
BENIGN_EVENTS = ("flash_crowd", "billing_batch", "maintenance_window")

# Legitimate background load per NF at load factor 1.0 (requests or msgs / min)
BACKGROUND = {"amf": 300, "upf": 500, "nef": 25, "udm": 40, "smf": 60}
_BG = "bg-"


def apply_background(sim: Sim, rng: random.Random, load: float) -> None:
    """Replace the background-load entries with a fresh draw at `load`."""
    for nf, base in BACKGROUND.items():
        entries = [t for t in sim.state["traffic"][nf] if not t["source"].startswith(_BG)]
        entries.append({"source": f"{_BG}{nf}", "rate": int(base * load * rng.uniform(0.15, 0.65))})
        sim.state["traffic"][nf] = entries


def start_benign(sim: Sim, rng: random.Random, event: str) -> dict:
    """Apply a benign event; returns what is needed to end it (end_benign)."""
    s = sim.state
    if event == "flash_crowd":
        rate = int(rng.uniform(900, 2400))
        s["traffic"]["amf"].append({"source": f"{_BG}flash-crowd", "rate": rate,
                                    "via": rng.choice(["gnb-101", "gnb-102", "gnb-103"])})
        sim.log("amf", "WARN", f"registration surge {rate}/min from in-inventory cells "
                               "(event venue / outage recovery)")
        return {"event": event}
    if event == "billing_batch":
        s["traffic"]["udm"].append({"source": f"{_BG}billing-batch", "rate": int(rng.uniform(600, 1500))})
        sim.log("udm", "INFO", "scheduled billing-batch job reading subscription data (authorised, change ticket CR-2291)")
        return {"event": event}
    if event == "maintenance_window":
        choice = rng.choice(["whitelist", "ipsec_n3", "nef_oauth", "admin_access"])
        undo: dict = {"event": event, "choice": choice}
        if choice == "whitelist":
            undo["old"] = s["nfs"]["gnb"]["config"]["neighbor_whitelist"]
            s["nfs"]["gnb"]["config"]["neighbor_whitelist"] = "disabled"
        elif choice == "ipsec_n3":
            undo["old"] = s["interfaces"]["N3"]["ipsec"]
            s["interfaces"]["N3"]["ipsec"] = False
        elif choice == "nef_oauth":
            undo["old"] = s["nfs"]["nef"]["config"]["oauth2"]
            s["nfs"]["nef"]["config"]["oauth2"] = "optional"
        else:
            undo["old"] = s["nfs"]["oam"]["config"]["admin_access"]
            s["nfs"]["oam"]["config"]["admin_access"] = "any-internal"
        sim.log("oam", "INFO", f"planned maintenance window MW-17 started ({choice})")
        return undo
    raise ValueError(f"unknown benign event {event!r}; known: {list(BENIGN_EVENTS)}")


def end_benign(sim: Sim, undo: dict) -> None:
    s, event = sim.state, undo["event"]
    if event == "flash_crowd":
        s["traffic"]["amf"] = [t for t in s["traffic"]["amf"] if t["source"] != f"{_BG}flash-crowd"]
    elif event == "billing_batch":
        s["traffic"]["udm"] = [t for t in s["traffic"]["udm"] if t["source"] != f"{_BG}billing-batch"]
    elif event == "maintenance_window":
        choice, old = undo["choice"], undo["old"]
        if choice == "whitelist":
            s["nfs"]["gnb"]["config"]["neighbor_whitelist"] = old
        elif choice == "ipsec_n3":
            s["interfaces"]["N3"]["ipsec"] = old
        elif choice == "nef_oauth":
            s["nfs"]["nef"]["config"]["oauth2"] = old
        else:
            s["nfs"]["oam"]["config"]["admin_access"] = old
        sim.log("oam", "INFO", "planned maintenance window MW-17 closed")


def inject_scaled(sim: Sim, attack_id: str, intensity: float) -> dict:
    """
    Inject an attack, then scale the traffic it added by `intensity`.
    The result lists the traffic entries the attack added, as
    (nf, source, via) — see `attack_residual`.
    """
    before = {nf: len(v) for nf, v in sim.state["traffic"].items()}
    result = inject(sim, attack_id)
    added = []
    for nf, entries in sim.state["traffic"].items():
        for t in entries[before.get(nf, 0):]:
            if not t["source"].startswith(_BG):
                t["rate"] = max(1, int(t["rate"] * intensity))
                added.append((nf, t["source"], t.get("via")))
    for d in sim.state.get("infected_devices", []):
        sim.state["devices"][d]["rate"] = max(51, int(sim.state["devices"][d]["rate"] * intensity))
    return {**result, "added_traffic": added}


def attack_residual(sim: Sim, added_traffic: list[tuple[str, str, str | None]]) -> bool:
    """
    Does anything an attack introduced still reach the network — traffic
    that is neither blocked nor cut off, infected devices not quarantined, or
    an active bulk reader of subscriber data?  True after a remediation that
    mitigates without stopping (e.g. rate-limiting a DDoS).
    """
    s = sim.state
    for nf, source, via in added_traffic:
        connected = via is None or any(g["id"] == via and g["connected"] for g in s["gnbs"])
        if source not in s["nfs"][nf]["blocked_sources"] and connected:
            return True
    if any(d not in s["quarantined_devices"] for d in s.get("infected_devices", [])):
        return True
    return bool(sim.check_api_access_log("udm").get("bulk_readers"))


def run_episode(label: str, rng: random.Random, load: float,
                poll: Callable[[Sim, str], None], benign_share: float = 0.5) -> None:
    """
    One training episode: a fresh simulation, a first poll (the collector's
    reference), then the event, then two labelled polls — one right after
    the event (new log lines, a step change) and one a tick later (the
    condition persisting).  `poll(sim, label)` receives label None for the
    reference poll.
    """
    sim = Sim(persist=False)
    apply_background(sim, rng, load)
    sim.tick()
    poll(sim, None)
    if label == NORMAL:
        if rng.random() < benign_share:
            start_benign(sim, rng, rng.choice(BENIGN_EVENTS))
    else:
        if label not in ATTACKS:
            raise ValueError(f"unknown attack {label!r}")
        if rng.random() < 0.15:                     # attacks also happen during maintenance
            start_benign(sim, rng, "maintenance_window")
        inject_scaled(sim, label, rng.uniform(0.3, 1.3))
    apply_background(sim, rng, load)
    sim.tick()
    poll(sim, label)
    apply_background(sim, rng, load)
    sim.tick()
    poll(sim, label)
