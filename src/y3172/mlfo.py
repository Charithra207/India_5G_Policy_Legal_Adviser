"""
MLFO — machine learning function orchestrator (Y.3172 clauses 3.2.2, 8.1, 8.2)
==============================================================================
Reads an ML Intent and runs the ML application it describes:

  1. instantiate   the SRC nodes, C, PP, M, P, D and SINKs, with the level
                   (UE / AN / CN / management) the intent places each on and
                   the reference points between them (Figure 4)
  2. sandbox       ML sandbox subsystem: simulated underlay networks
                   (sim/datagen.py) generate labelled telemetry; every
                   candidate model is trained and evaluated on held-out
                   episodes; the best one that meets the intent's score and
                   latency constraints is selected (MNG-001, MNG-004)
  3. validate      the selected model and the remediation playbooks are run
                   against each target incident in a sandbox simulation, so
                   their effect on the network is evaluated before live use
                   (clause 3.2.6)
  4. deploy        to a separate live simulation (its own state and logs)
  5. operate       each tick: SRC -> C -> PP -> M -> P -> D -> SINKs
  6. monitor       rolling score of predictions against incident outcomes;
                   when it falls below the intent's minimum, the sandbox is
                   re-calibrated to the live load, the candidates retrained
                   and a model re-selected (MNG-003, MNG-004)

Every decision is appended to a hash-chained audit trail
(src/audit/trail.py) in the run folder.  "Truth" for monitoring is the
incident outcome; in the lab the simulator supplies it, in a real network
it would come from incident closure.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from catalog.loader import load_catalog
from sim.datagen import (BACKGROUND, NORMAL, apply_background, attack_residual, end_benign, inject_scaled,
                         run_episode, start_benign)
from sim.engine import CLOCK_START, Sim, check
from src.audit.trail import AuditTrail, stage_entry
from src.y3172.distributor import Distributor
from src.y3172.intent import Intent, telemetry_plan
from src.y3172.models import CANDIDATES, CandidateModel, evaluate, propose_remediation, window_score
from src.y3172.nodes import Collector, Preprocessor
from src.y3172.policy_node import PolicyNode

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "outputs" / "y3172"
BENIGN_TICKS = 3                 # how long a benign exercise event lasts
DEDUP_TICKS = 5                  # the same incident class is not re-dispatched within this many ticks
# offered load the simulator adds on top of background, per NF (sim/engine.py _recompute)
_ENGINE_BASE = {"amf": 50, "upf": 400, "nef": 20, "udm": 30, "smf": 10}

# Y.3172 Figure 4 reference points used by this pipeline
REFERENCE_POINTS = {
    "4": "ML underlay network (live simulation) ↔ ML pipeline: collector reads diagnostics; SINKs act",
    "1,2": "simulated ML underlay networks ↔ ML pipeline in the sandbox subsystem",
    "3": "ML sandbox subsystem ↔ ML pipeline subsystem: trained model handed over at deployment",
    "5": "management subsystem (MLFO) ↔ ML pipeline subsystem: instantiation, model updates",
    "6": "management subsystem (MLFO) ↔ ML sandbox subsystem: training, evaluation, selection",
    "7": "MLFO ↔ other management functions: the incident-response engine (ir/engine.py) and its human gates",
}


class AutoOperator:
    """Sandbox only: approves everything so a playbook's full effect can be measured."""
    def gate(self, tier, message):
        return "agent"

    def confirm(self, description):
        return True

    def manual(self, tier, commands):
        return ""


def remediate_in_sandbox(sim: Sim, label: str, catalog: dict) -> bool:
    """Run the catalog playbook tier by tier, every step approved (sandbox only; writes no report)."""
    from ir.engine import Incident
    from ir.llm import OfflineProvider
    incident = Incident(label, provider=OfflineProvider(), human=AutoOperator(), catalog=catalog, sim=sim,
                        search=lambda *a, **k: [])
    incident.phase = "basic"
    for tier in ("basic", "intermediate", "advanced"):
        if incident.run_tier(tier, "agent"):
            return True
    return False


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    episode: np.ndarray
    feature_names: list[str]


def sim_time(sim: Sim) -> datetime:
    return CLOCK_START + timedelta(minutes=sim.state["tick"])


class MLFO:
    def __init__(self, intent: Intent, run_dir: Path | None = None, human=None, catalog: dict | None = None,
                 on_event: Callable[[dict], None] | None = None, incident_event: Callable | None = None,
                 pipeline_factory: Callable | None = None, provider_factory: Callable | None = None,
                 run_id: str | None = None) -> None:
        self.intent = intent
        self.catalog = catalog or load_catalog()
        self.attacks = {a["id"]: a for a in self.catalog["attacks"]}
        self.run_id = run_id or f"{intent.intent_id}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
        self.run_dir = Path(run_dir) if run_dir else DEFAULT_OUT / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.human = human
        self.on_event = on_event or (lambda e: None)
        self.incident_event = incident_event
        self.plan = telemetry_plan(intent)
        self.policy = PolicyNode(intent, self.catalog, pipeline_factory)
        self.provider_factory = provider_factory
        self.trail = AuditTrail.start_run(self.run_id, {
            "intent_id": intent.intent_id, "intent_title": intent.title, "intent_path": intent.path,
            "intent": intent.raw, "policy_mode": intent.policy.mode}, self.run_dir)
        self.model: CandidateModel | None = None
        self.selection: dict = {}
        self.history: list[dict] = []          # every model selection (initial + reselections)
        self.sandbox_validation: list[dict] = []
        self.ticks: list[dict] = []
        self.incidents: list[dict] = []
        self.train_load = intent.training.background_load
        self.live: Sim | None = None

    # ------------------------------------------------------------------
    def _emit(self, kind: str, **data) -> None:
        self.on_event({"kind": kind, **data})

    def _audit(self, kind: str, payload: dict) -> dict:
        return self.trail.record(kind, json.loads(json.dumps(payload, default=str)))

    # ------------------------------------------------------------------
    # 1. Instantiate
    # ------------------------------------------------------------------

    def instantiate(self) -> dict:
        i = self.intent
        nodes = [{"node": "SRC", "id": f"src:{s.nf}", "level": s.level, "telemetry": list(s.telemetry)}
                 for s in i.sources]
        nodes += [{"node": "C", "id": "collector", "level": i.placement["collector"],
                   "polls": [f"{nf}.{g}" for nf, g in self.plan]},
                  {"node": "PP", "id": "preprocessor", "level": i.placement["preprocessor"]},
                  {"node": "M", "id": "model", "level": i.placement["model"], "candidates": list(i.candidates)},
                  {"node": "P", "id": "policy_node", "level": i.placement["policy"], "mode": i.policy.mode},
                  {"node": "D", "id": "distributor", "level": i.placement["distributor"]}]
        nodes += [{"node": "SINK", "id": f"sink:{s}", "level": "management" if s != "remediation" else "CN"}
                  for s in i.sinks]
        levels = sorted({n["level"] for n in nodes})
        plan = {"nodes": nodes, "levels": levels, "reference_points": REFERENCE_POINTS,
                "chain": "SRC → C → PP → M → P → D → SINK",
                "feature_count": len(Preprocessor(self.plan).feature_names)}
        self._audit("pipeline_instantiated", plan)
        self._emit("instantiated", **plan)
        self.instantiation = plan
        return plan

    # ------------------------------------------------------------------
    # 2. ML sandbox: data, training, evaluation, selection
    # ------------------------------------------------------------------

    def generate(self, samples_per_class: int, load: tuple[float, float], seed: int) -> Dataset:
        rng = random.Random(seed)
        pp = Preprocessor(self.plan)
        X, y, ep = [], [], []
        labels = [NORMAL] + list(self.intent.target_classes)
        episode = 0
        for label in labels:
            n = samples_per_class * 3 if label == NORMAL else samples_per_class
            for _ in range((n + 1) // 2):
                collector = Collector(self.plan, dropout=0.05, rng=random.Random(rng.random()))
                pp.reset()

                def poll(sim, lab, _e=episode):
                    v = pp.transform(collector.poll(sim))
                    if lab is not None:
                        X.append(v)
                        y.append(lab)
                        ep.append(_e)
                run_episode(label, rng, rng.uniform(*load), poll)
                episode += 1
            if label != NORMAL:                     # the network after its playbook has run
                for _ in range(max(2, samples_per_class // 4)):
                    collector = Collector(self.plan, dropout=0.05, rng=random.Random(rng.random()))
                    pp.reset()
                    for lab, vec in self._post_remediation_episode(label, rng, rng.uniform(*load), collector, pp):
                        X.append(vec)
                        y.append(lab)
                        ep.append(episode)
                    episode += 1
        return Dataset(np.array(X, dtype=float), np.array(y), np.array(ep), pp.feature_names)

    def _post_remediation_episode(self, label: str, rng: random.Random, load: float,
                                  collector: Collector, pp: Preprocessor) -> list[tuple[str, list[float]]]:
        """
        Inject, remediate with the catalog playbook (sandbox: every step
        approved), then sample twice.  Label: the attack if any of it still
        reaches the network (contained), else normal.
        """
        sim = Sim(persist=False)
        apply_background(sim, rng, load)
        sim.tick()
        pp.transform(collector.poll(sim))
        added = inject_scaled(sim, label, rng.uniform(0.3, 1.3))["added_traffic"]
        apply_background(sim, rng, load)
        sim.tick()
        pp.transform(collector.poll(sim))
        remediate_in_sandbox(sim, label, self.catalog)
        out = []
        for _ in range(2):
            apply_background(sim, rng, load)
            sim.tick()
            vec = pp.transform(collector.poll(sim))
            out.append((label if attack_residual(sim, added) else NORMAL, vec))
        return out

    def _split(self, data: Dataset, seed: int) -> tuple[np.ndarray, np.ndarray]:
        """Stratified split by episode, so both samples of an episode land on the same side."""
        rng = random.Random(seed)
        test_eps = set()
        for label in sorted(set(data.y)):
            eps = sorted({int(e) for e, l in zip(data.episode, data.y) if l == label})
            rng.shuffle(eps)
            k = max(1, round(len(eps) * self.intent.training.holdout_fraction))
            test_eps.update(eps[:k])
        test = np.array([int(e) in test_eps for e in data.episode])
        return ~test, test

    def train_and_select(self, reason: str = "initial") -> dict:
        t = self.intent.training
        seed = t.seed + len(self.history) * 1000
        t0 = time.perf_counter()
        data = self.generate(t.samples_per_class, self.train_load, seed)
        gen_s = time.perf_counter() - t0
        train, test = self._split(data, seed)
        self._emit("sandbox_data", samples=len(data.y), features=len(data.feature_names),
                   classes=len(set(data.y)), load=self.train_load, seconds=round(gen_s, 2))
        results, models = [], {}
        for cid in self.intent.candidates:
            t1 = time.perf_counter()
            model = CANDIDATES[cid](seed=t.seed).fit(data.X[train], data.y[train], data.feature_names)
            train_s = time.perf_counter() - t1
            metrics = evaluate(model, data.X[test], data.y[test])
            sel = self.intent.selection
            eligible = (metrics[sel.metric] >= sel.min_score
                        and (metrics["inference_ms_p95"] or 0) <= sel.max_inference_ms)
            results.append({"model_id": cid, "train_seconds": round(train_s, 3), "eligible": eligible,
                            "metrics": metrics, "card": model.card()})
            models[cid] = model
            self._emit("candidate_evaluated", model_id=cid, eligible=eligible, metrics=metrics)
        metric = self.intent.selection.metric
        ranked = sorted(results, key=lambda r: (r["eligible"], r["metrics"][metric],
                                                -(r["metrics"]["inference_ms_mean"] or 0)), reverse=True)
        best = ranked[0]
        selection = {
            "reason": reason, "selected": best["model_id"], "meets_intent": best["eligible"],
            "rule": f"highest {metric} among candidates with {metric} ≥ {self.intent.selection.min_score} "
                    f"and p95 inference ≤ {self.intent.selection.max_inference_ms} ms",
            "training_load": list(self.train_load), "samples": int(len(data.y)),
            "train_samples": int(train.sum()), "test_samples": int(test.sum()),
            "features": len(data.feature_names), "data_seconds": round(gen_s, 2), "candidates": results,
        }
        if not best["eligible"]:
            selection["warning"] = ("No candidate meets the intent's constraints; the best available is "
                                    "deployed and every detection is escalated to a human.")
        self.model, self.selection = models[best["model_id"]], selection
        self.history.append(selection)
        sandbox = self.run_dir / "sandbox"
        sandbox.mkdir(parents=True, exist_ok=True)
        (sandbox / f"model_selection_{len(self.history)}.json").write_text(
            json.dumps(selection, indent=2, default=str), encoding="utf-8")
        self._audit("model_selected", selection)
        self._emit("model_selected", **{k: selection[k] for k in ("reason", "selected", "meets_intent", "rule")})
        return selection

    # ------------------------------------------------------------------
    # 3. Sandbox validation of effects on the network
    # ------------------------------------------------------------------

    def validate_in_sandbox(self) -> list[dict]:
        from ir.engine import Incident
        from ir.llm import OfflineProvider
        from src.y3172.distributor import safe_search
        root = self.run_dir / "sandbox" / "sim"
        rows = []
        for label in self.intent.target_classes:
            sim = Sim(root=root)
            rng = random.Random(self.intent.training.seed)
            apply_background(sim, rng, 1.0)
            sim.tick()
            collector, pp = Collector(self.plan), Preprocessor(self.plan)
            pp.transform(collector.poll(sim))
            inject_scaled(sim, label, 1.0)
            apply_background(sim, rng, 1.0)
            sim.tick()
            pred = self.model.predict(np.array(pp.transform(collector.poll(sim))))
            incident = Incident(label, provider=OfflineProvider(), human=AutoOperator(), catalog=self.catalog,
                                sim=sim, search=safe_search)
            incident.phase = "basic"
            report = incident.run()
            resolved_in = next((t for t, o in incident.tier_outcomes.items() if o.get("resolved")), None)
            sim.tick()
            after = self.model.predict(np.array(pp.transform(collector.poll(sim))))
            rows.append({"incident": label, "detected_as": pred.label, "detected": pred.label == label,
                         "confidence": round(pred.confidence, 3), "playbook_resolved": report["resolved"],
                         "resolved_in": resolved_in, "after_remediation": after.label})
        self.sandbox_validation = rows
        self._audit("sandbox_effect_evaluation", {"rows": rows, "note": "sandbox simulation only; every step "
                                                  "auto-approved to measure the playbook's full effect"})
        self._emit("sandbox_validated", rows=rows)
        return rows

    # ------------------------------------------------------------------
    # 4-6. Deploy, operate, monitor
    # ------------------------------------------------------------------

    def _truth(self) -> str:
        """
        The incident outcome used as monitoring feedback (in a real network
        it comes from incident closure; in the lab the simulator knows it):

          <attack>             injected and not yet resolved
          contained:<attack>   resolved by the catalog's checks, but the
                               attack's traffic or devices still reach the
                               network (mitigated, not stopped)
          normal               no attack, or resolved and nothing of it left

        Once resolved, an incident stays resolved even if later load makes a
        symptom check fail again — that is congestion, not the attack.
        """
        attack = self.live.state.get("attack")
        if not attack:
            return NORMAL
        if attack not in self._closed:
            if not all(check(self.live, c)[0] for c in self.attacks[attack]["resolved_when"]):
                return attack
            self._closed.add(attack)
        return f"contained:{attack}" if self._residual(attack) else NORMAL

    def _residual(self, attack: str) -> bool:
        return attack_residual(self.live, self._attack_traffic.get(attack, []))

    @staticmethod
    def _scored_truth(prediction: str, truth: str) -> str:
        """For a contained incident, both 'still seeing it' and 'normal' are right."""
        if truth.startswith("contained:"):
            return prediction if prediction in (NORMAL, truth.split(":", 1)[1]) else NORMAL
        return truth

    def deploy(self) -> None:
        self.live = Sim(root=self.run_dir / "live")
        self._closed: set[str] = set()
        self._attack_traffic: dict[str, list[tuple[str, str, str | None]]] = {}
        self.collector, self.pp = Collector(self.plan), Preprocessor(self.plan)
        self.distributor = Distributor(self.intent, self.catalog, self.human, self.live, self.run_dir,
                                       on_event=self.incident_event, provider_factory=self.provider_factory)
        self._audit("model_deployed", {"model_id": self.model.model_id, "live_network": str(self.live.root),
                                       "reference_point": "3 (sandbox → pipeline), 5 (MLFO → pipeline)"})
        self._emit("deployed", model_id=self.model.model_id, live=str(self.live.root))

    def _estimate_load(self, rows: list[np.ndarray]) -> float | None:
        """
        Calibrate the sandbox to the live network: the background load implied
        by the offered rates of recent normal ticks (the background draw
        averages 0.4 of the per-NF base, see sim/datagen.py).  The largest
        per-NF estimate is used: a remediation can block traffic and so lower
        one NF's offered rate, but nothing in the lab raises it.
        """
        names = self.pp.feature_names
        ests = []
        for nf, base in BACKGROUND.items():
            name = f"{nf}.metrics.offered_rate"
            if name in names and rows:
                live = float(np.mean([r[names.index(name)] for r in rows]))
                ests.append(max(0.1, (live - _ENGINE_BASE[nf]) / (base * 0.4)))
        return round(float(max(ests)), 2) if ests else None

    def reselect(self, tick: int, score: dict, normal_rows: list[np.ndarray]) -> dict:
        before = self.model.model_id
        est = self._estimate_load(normal_rows)
        low, high = self.train_load
        if est is not None:
            self.train_load = (round(min(low, est * 0.8), 2), round(max(high, est * 1.25), 2))
        else:
            self.train_load = (low, round(high * 2, 2))
        self._emit("reselecting", tick=tick, score=score, estimated_load=est, new_training_load=self.train_load)
        selection = self.train_and_select(reason=f"monitoring: rolling {self.intent.monitoring.metric} "
                                                 f"{score.get(self.intent.monitoring.metric)} below "
                                                 f"{self.intent.monitoring.min_score} at tick {tick}")
        event = {"tick": tick, "previous_model": before, "new_model": selection["selected"],
                 "rolling_score": score, "estimated_live_load": est, "training_load": list(self.train_load)}
        self._audit("model_reselected", event)
        return event

    def operate(self) -> None:
        intent, ex = self.intent, self.intent.exercise
        rng = random.Random(ex.seed if ex else 11)
        events = list(ex.events) if ex else []
        ticks = ex.ticks if ex else 20
        if not ex:
            from src.y3172.intent import Event
            events = [Event(3, "inject", intent.target_classes[0])]
        load, benign_active, last_handled = 1.0, [], {}
        injected_at: dict[str, int] = {}
        self.injected = injected_at
        window: list[tuple[str, str]] = []
        normal_rows: list[np.ndarray] = []
        last_reselect = -10**6
        self.reselections: list[dict] = []
        apply_background(self.live, rng, load)
        self.live.tick()
        self.pp.transform(self.collector.poll(self.live))         # reference poll
        for tick in range(ticks):
            happened = []
            for e in [e for e in events if e.at == tick]:
                if e.kind == "inject":
                    self._attack_traffic[e.value] = inject_scaled(self.live, e.value, 1.0)["added_traffic"]
                    injected_at[e.value] = tick
                    happened.append(f"attack injected: {e.value}")
                elif e.kind == "benign":
                    benign_active.append((tick + BENIGN_TICKS, start_benign(self.live, rng, e.value)))
                    happened.append(f"benign event: {e.value}")
                else:
                    load = float(e.value)
                    happened.append(f"load drift: background load ×{load}")
            for end_at, undo in [b for b in benign_active if b[0] == tick]:
                end_benign(self.live, undo)
                benign_active.remove((end_at, undo))
                happened.append(f"benign event ended: {undo['event']}")
            apply_background(self.live, rng, load)
            self.live.tick()
            snap = self.collector.poll(self.live)
            x = np.array(self.pp.transform(snap))
            t0 = time.perf_counter()
            pred = self.model.predict(x)
            infer_ms = (time.perf_counter() - t0) * 1000
            truth = self._truth()
            if truth == NORMAL:
                normal_rows = (normal_rows + [x])[-intent.monitoring.window:]
            window = (window + [(pred.label, self._scored_truth(pred.label, truth))])[-intent.monitoring.window:]
            score = window_score(window)
            row = {"tick": tick, "clock": sim_time(self.live).strftime("%H:%M"), "events": happened,
                   "prediction": pred.label, "confidence": round(pred.confidence, 3), "truth": truth,
                   "scored_truth": self._scored_truth(pred.label, truth),
                   "inference_ms": round(infer_ms, 3), "rolling": score, "model": self.model.model_id,
                   "load": load, "action": None}
            self._emit("tick", **row)
            if pred.is_incident:
                if pred.label in self._closed:
                    row["action"] = "resolved incident still observed (contained) — not re-dispatched"
                elif tick - last_handled.get(pred.label, -10**6) < DEDUP_TICKS:
                    row["action"] = "duplicate of an incident handled in the last ticks — not re-dispatched"
                else:
                    last_handled[pred.label] = tick
                    row["action"] = self.handle(pred, snap, tick, injected_at)
            self.ticks.append(row)
            self._audit("tick", row)
            m = intent.monitoring
            metric_value = score.get(m.metric)
            if (len(window) >= m.min_samples and metric_value is not None and metric_value < m.min_score
                    and tick - last_reselect >= m.cooldown_ticks):
                event = self.reselect(tick, score, normal_rows)
                self.reselections.append(event)
                last_reselect, window = tick, []

    def handle(self, pred, snap, tick: int, injected_at: dict) -> str:
        n = len(self.incidents) + 1
        incident_id = f"{self.run_id}-INC{n:03d}"
        when = sim_time(self.live)
        pred.proposal = propose_remediation(pred.label, self.catalog)
        alerts = list(snap.novelty.get("alerts", [])) or self.live.get_alerts()["alerts"][-3:]
        hospital = self.live.get_service_health("hospital-portal")["status"] != "ok" or \
            "hospital" in json.dumps(self.attacks.get(pred.label, {}).get("description", "")).lower()
        truth = self._truth()
        first = not any(x["lab_truth"] == truth for x in self.incidents)
        delay = (tick - injected_at[truth]) if (pred.label == truth and truth in injected_at and first) else None
        self._audit("detection", {"incident_id": incident_id, "tick": tick, "detected_at": when.isoformat(),
                                  "prediction": pred.as_dict(), "lab_truth": truth,
                                  "detection_delay_ticks": delay,
                                  "deadline_ticks": self.intent.decision_deadline_ticks})
        self._emit("detection", incident_id=incident_id, tick=tick, prediction=pred.as_dict(), truth=truth)
        decision, record = self.policy.assess(incident_id, pred, alerts, when, hospital)
        payload = {"decision": decision.as_dict()}
        if record is not None:
            payload["specialist_agents"] = stage_entry(record, incident_id, None, [])
        self._audit("p_node_decision", payload)
        self._emit("policy", incident_id=incident_id, decision=decision.as_dict())
        sinks = self.distributor.dispatch(pred, decision, alerts, when)
        self._audit("dispatch", {"incident_id": incident_id, "sinks": sinks})
        self._emit("dispatch", incident_id=incident_id, sinks=sinks)
        self.incidents.append({"incident_id": incident_id, "tick": tick, "detected_at": when.isoformat(),
                               "prediction": pred.as_dict(), "lab_truth": truth, "correct": pred.label == truth,
                               "detection_delay_ticks": delay, "decision": decision.as_dict(), "sinks": sinks})
        status = next((s["status"] for s in sinks if s["sink"] == "remediation"), decision.decision)
        return f"{incident_id}: P={decision.decision}; remediation={status}"

    # ------------------------------------------------------------------

    def run(self, validate: bool = True) -> dict:
        from src.y3172.report import build_report
        self.instantiate()
        self.train_and_select("initial")
        if validate:
            self.validate_in_sandbox()
        self.deploy()
        self.operate()
        report = build_report(self)
        (self.run_dir / "report.md").write_text(report["markdown"], encoding="utf-8")
        (self.run_dir / "report.json").write_text(json.dumps(report["data"], indent=2, default=str),
                                                  encoding="utf-8")
        self._audit("run_completed", {"summary": report["data"]["summary"]})
        report["paths"] = {"report": str(self.run_dir / "report.md"), "audit": str(self.trail.path),
                           "run_dir": str(self.run_dir)}
        return report
