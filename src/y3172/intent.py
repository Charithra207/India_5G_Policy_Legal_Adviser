"""
ML Intent (ITU-T Y.3172 clause 7.4, clause 8.1 NOTE 12)
=======================================================
A declarative, technology-agnostic description of one ML application: where
its data comes from (SRC nodes), which models may serve it, which targets
receive its output (SINKs), how the policy node treats that output, and its
time constraints.  The MLFO (mlfo.py) turns an intent into a running
pipeline; nothing in an intent names simulator internals.

    from src.y3172.intent import load_intent
    intent = load_intent("intents/amf_signalling_storm.yaml")

`load_intent` validates every field and fails with IntentError naming the
field, so a typo cannot silently change what the pipeline does.  The
optional `exercise` section is the lab schedule for a live run (events on
the simulated network); it is not part of the Y.3172 ML Intent itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

LEVELS = ("UE", "AN", "CN", "management")
POLICY_MODES = ("advisory", "blocking")
SINKS = ("remediation", "regulatory_notices", "evidence_preservation", "escalation")
SELECTION_METRICS = ("macro_f1", "detection_f1")
MONITORING_METRICS = ("accuracy", "macro_f1", "detection_f1")
REMEDIATION_AGENTS = ("offline", "anthropic")
TIERS = ("basic", "intermediate", "advanced")
BENIGN_EVENTS = ("flash_crowd", "billing_batch", "maintenance_window")


class IntentError(ValueError):
    """The intent is malformed; the message names the field."""


@dataclass(frozen=True)
class Source:
    nf: str
    level: str
    telemetry: tuple[str, ...]


@dataclass(frozen=True)
class Selection:
    metric: str
    min_score: float
    max_inference_ms: float


@dataclass(frozen=True)
class Training:
    samples_per_class: int
    holdout_fraction: float
    seed: int
    background_load: tuple[float, float]


@dataclass(frozen=True)
class Policy:
    level: str
    mode: str
    jurisdiction: str
    min_confidence: float
    legal_adviser: bool


@dataclass(frozen=True)
class Monitoring:
    metric: str
    window: int
    min_samples: int
    min_score: float
    cooldown_ticks: int


@dataclass(frozen=True)
class Event:
    at: int
    kind: str          # inject | benign | drift
    value: Any         # attack id | benign event name | load factor


@dataclass(frozen=True)
class Exercise:
    ticks: int
    seed: int
    events: tuple[Event, ...]


@dataclass(frozen=True)
class Intent:
    intent_id: str
    title: str
    description: str
    target_classes: tuple[str, ...]
    sources: tuple[Source, ...]
    placement: dict[str, str]                 # pipeline node -> level
    candidates: tuple[str, ...]
    selection: Selection
    training: Training
    policy: Policy
    sinks: tuple[str, ...]
    remediation_agent: str
    remediation_max_tier: str
    decision_deadline_ticks: int
    monitoring: Monitoring
    exercise: Exercise | None
    path: str = ""
    raw: dict = field(default_factory=dict, compare=False, repr=False)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _req(d: dict, key: str, where: str) -> Any:
    if not isinstance(d, dict) or key not in d:
        raise IntentError(f"{where}: missing field {key!r}")
    return d[key]


def _str(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntentError(f"{where}: must be a non-empty string")
    return value.strip()


def _int(value: Any, where: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise IntentError(f"{where}: must be an integer in [{lo}, {hi}], got {value!r}")
    return value


def _num(value: Any, where: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise IntentError(f"{where}: must be a number in [{lo}, {hi}], got {value!r}")
    return float(value)


def _choice(value: Any, where: str, options: tuple[str, ...]) -> str:
    if value not in options:
        raise IntentError(f"{where}: must be one of {list(options)}, got {value!r}")
    return value


def _level(section: dict, where: str, default: str) -> str:
    return _choice(section.get("level", default), f"{where}.level", LEVELS)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_intent(data: dict, path: str = "", catalog: dict | None = None) -> Intent:
    """Validate a parsed intent document and return an Intent."""
    from catalog.loader import load_catalog
    from sim.engine import NFS
    from sim.inject import ATTACKS
    from src.y3172.models import CANDIDATES
    from src.y3172.nodes import TELEMETRY

    if not isinstance(data, dict):
        raise IntentError("intent: the document must be a mapping")
    catalog = catalog or load_catalog()
    catalog_ids = [a["id"] for a in catalog["attacks"]]

    intent_id = _str(_req(data, "intent_id", "intent"), "intent_id")
    if not intent_id.replace("_", "").replace("-", "").isalnum():
        raise IntentError("intent_id: letters, digits, '_' and '-' only")

    # --- ML application: which incident classes the model must recognise
    app = _req(data, "ml_application", "intent")
    targets = _req(app, "target_classes", "ml_application")
    if targets == "all":
        targets = list(catalog_ids)
    if not isinstance(targets, list) or not targets:
        raise IntentError("ml_application.target_classes: a non-empty list of attack ids, or 'all'")
    unknown = [t for t in targets if t not in catalog_ids or t not in ATTACKS]
    if unknown:
        raise IntentError(f"ml_application.target_classes: unknown attack ids {unknown}")
    if len(set(targets)) != len(targets):
        raise IntentError("ml_application.target_classes: duplicate ids")

    # --- SRC nodes: network functions and the telemetry each provides
    sources = []
    raw_sources = _req(data, "sources", "intent")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise IntentError("sources: a non-empty list")
    seen = set()
    for i, s in enumerate(raw_sources):
        where = f"sources[{i}]"
        nf = _choice(_req(s, "nf", where), f"{where}.nf", tuple(NFS))
        if nf in seen:
            raise IntentError(f"{where}.nf: {nf!r} listed twice")
        seen.add(nf)
        groups = _req(s, "telemetry", where)
        if not isinstance(groups, list) or not groups:
            raise IntentError(f"{where}.telemetry: a non-empty list")
        for g in groups:
            if g not in TELEMETRY:
                raise IntentError(f"{where}.telemetry: unknown group {g!r}; known: {sorted(TELEMETRY)}")
            if nf not in TELEMETRY[g].nfs:
                raise IntentError(f"{where}.telemetry: {nf!r} does not provide {g!r} "
                                  f"(provided by {list(TELEMETRY[g].nfs)})")
        sources.append(Source(nf, _level(s, where, "AN" if nf == "gnb" else "CN"), tuple(dict.fromkeys(groups))))

    # --- Model candidates and selection rule
    model = _req(data, "model", "intent")
    cands = _req(model, "candidates", "model")
    if not isinstance(cands, list) or not cands:
        raise IntentError("model.candidates: a non-empty list")
    bad = [c for c in cands if c not in CANDIDATES]
    if bad:
        raise IntentError(f"model.candidates: unknown models {bad}; known: {sorted(CANDIDATES)}")
    sel = _req(model, "selection", "model")
    selection = Selection(
        metric=_choice(sel.get("metric", "macro_f1"), "model.selection.metric", SELECTION_METRICS),
        min_score=_num(_req(sel, "min_score", "model.selection"), "model.selection.min_score", 0.0, 1.0),
        max_inference_ms=_num(_req(sel, "max_inference_ms", "model.selection"),
                              "model.selection.max_inference_ms", 0.01, 60_000),
    )

    tr = data.get("training", {})
    load = tr.get("background_load", [0.8, 1.2])
    if (not isinstance(load, list) or len(load) != 2
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in load)
            or not 0 < load[0] <= load[1] <= 20):
        raise IntentError("training.background_load: [low, high] with 0 < low <= high <= 20")
    training = Training(
        samples_per_class=_int(tr.get("samples_per_class", 40), "training.samples_per_class", 5, 2000),
        holdout_fraction=_num(tr.get("holdout_fraction", 0.3), "training.holdout_fraction", 0.1, 0.5),
        seed=_int(tr.get("seed", 7), "training.seed", 0, 2**31 - 1),
        background_load=(float(load[0]), float(load[1])),
    )

    pol = _req(data, "policy", "intent")
    policy = Policy(
        level=_level(pol, "policy", "management"),
        mode=_choice(_req(pol, "mode", "policy"), "policy.mode", POLICY_MODES),
        jurisdiction=_choice(pol.get("jurisdiction", "IN"), "policy.jurisdiction", ("IN",)),
        min_confidence=_num(pol.get("min_confidence", 0.6), "policy.min_confidence", 0.0, 1.0),
        legal_adviser=bool(pol.get("legal_adviser", True)),
    )

    sinks = _req(data, "sinks", "intent")
    if not isinstance(sinks, list) or not sinks:
        raise IntentError("sinks: a non-empty list")
    for s in sinks:
        _choice(s, "sinks[]", SINKS)
    if "escalation" not in sinks:
        raise IntentError("sinks: 'escalation' is required — a human must always receive "
                          "what the pipeline cannot act on")

    rem = data.get("remediation", {})
    placement = {
        "collector": _level(data.get("collector", {}), "collector", "CN"),
        "preprocessor": _level(data.get("preprocessor", {}), "preprocessor", "CN"),
        "model": _level(model, "model", "CN"),
        "policy": policy.level,
        "distributor": _level(data.get("distributor", {}), "distributor", "management"),
    }

    cons = data.get("constraints", {})
    mon = _req(data, "monitoring", "intent")
    window = _int(_req(mon, "window", "monitoring"), "monitoring.window", 4, 1000)
    monitoring = Monitoring(
        metric=_choice(mon.get("metric", "accuracy"), "monitoring.metric", MONITORING_METRICS),
        window=window,
        min_samples=_int(mon.get("min_samples", max(2, window // 2)), "monitoring.min_samples", 2, window),
        min_score=_num(_req(mon, "min_score", "monitoring"), "monitoring.min_score", 0.0, 1.0),
        cooldown_ticks=_int(mon.get("cooldown_ticks", window // 2), "monitoring.cooldown_ticks", 0, 1000),
    )

    exercise = None
    if "exercise" in data:
        ex = data["exercise"]
        ticks = _int(_req(ex, "ticks", "exercise"), "exercise.ticks", 1, 2000)
        events = []
        for i, e in enumerate(ex.get("events", [])):
            where = f"exercise.events[{i}]"
            at = _int(_req(e, "at", where), f"{where}.at", 0, ticks - 1)
            kinds = [k for k in ("inject", "benign", "drift") if k in e]
            if len(kinds) != 1:
                raise IntentError(f"{where}: exactly one of inject / benign / drift")
            kind = kinds[0]
            if kind == "inject":
                value = _choice(e["inject"], f"{where}.inject", tuple(targets))
            elif kind == "benign":
                value = _choice(e["benign"], f"{where}.benign", BENIGN_EVENTS)
            else:
                value = _num(e["drift"], f"{where}.drift", 0.1, 20)
            events.append(Event(at, kind, value))
        events.sort(key=lambda ev: ev.at)
        exercise = Exercise(ticks, _int(ex.get("seed", 11), "exercise.seed", 0, 2**31 - 1), tuple(events))

    return Intent(
        intent_id=intent_id,
        title=_str(_req(data, "title", "intent"), "title"),
        description=" ".join(str(data.get("description", "")).split()),
        target_classes=tuple(targets),
        sources=tuple(sources),
        placement=placement,
        candidates=tuple(dict.fromkeys(cands)),
        selection=selection,
        training=training,
        policy=policy,
        sinks=tuple(dict.fromkeys(sinks)),
        remediation_agent=_choice(rem.get("agent", "offline"), "remediation.agent", REMEDIATION_AGENTS),
        remediation_max_tier=_choice(rem.get("max_tier", "advanced"), "remediation.max_tier", TIERS),
        decision_deadline_ticks=_int(cons.get("decision_deadline_ticks", 1),
                                     "constraints.decision_deadline_ticks", 1, 100),
        monitoring=monitoring,
        exercise=exercise,
        path=str(path),
        raw=data,
    )


def load_intent(path: str | Path, catalog: dict | None = None) -> Intent:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise IntentError(f"{path}: not valid YAML ({exc})") from exc
    return parse_intent(data, str(path), catalog)


def telemetry_plan(intent: Intent) -> list[tuple[str, str]]:
    """(nf, telemetry group) pairs the collector polls — the SRC nodes."""
    return [(s.nf, g) for s in intent.sources for g in s.telemetry]
