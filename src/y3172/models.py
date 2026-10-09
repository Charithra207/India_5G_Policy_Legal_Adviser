"""
M node: candidate ML models (Y.3172 clause 8.1)
===============================================
Each candidate learns, from labelled telemetry produced in the ML sandbox,
to tell normal operation (including benign look-alikes) from each incident
class in the intent, and returns:

    label            "normal", an attack id from the catalog, or
                     "unknown_anomaly" (abnormal, but no known class fits)
    confidence       0-1
    anomaly_score    how far the telemetry is from normal operation
    evidence         the features that deviate most from normal, with values
    proposal         the remediation playbook the catalog holds for the label

Candidates (the MLFO trains each and selects one, MNG-001):

  threshold_centroid  baseline — per-feature z-score against normal
                      operation; a threshold chosen on the training data
                      decides "abnormal", the nearest class centroid names it
  iforest_rf          IsolationForest (unsupervised: anything unlike normal
                      operation) + RandomForest (supervised: which incident);
                      abnormal-but-unrecognised telemetry becomes
                      "unknown_anomaly" and goes to a human

Models run on the CPU in a few milliseconds per prediction.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

NORMAL = "normal"
UNKNOWN = "unknown_anomaly"


@dataclass
class Prediction:
    label: str
    confidence: float
    anomaly_score: float
    model_id: str
    evidence: list[dict] = field(default_factory=list)
    proposal: dict | None = None

    @property
    def is_incident(self) -> bool:
        return self.label != NORMAL

    def as_dict(self) -> dict:
        return {"label": self.label, "confidence": round(self.confidence, 4),
                "anomaly_score": round(self.anomaly_score, 4), "model_id": self.model_id,
                "evidence": self.evidence, "proposal": self.proposal}


class CandidateModel:
    model_id = "base"
    description = ""

    def __init__(self, seed: int = 7) -> None:
        self.seed = seed
        self.feature_names: list[str] = []
        self._mu = self._sd = None

    # --- shared: normal-operation statistics, used for explanations
    def _fit_normal_stats(self, X: np.ndarray, y: np.ndarray) -> None:
        normal = X[y == NORMAL]
        self._mu = normal.mean(axis=0)
        # floor: a count that is always 0 in normal operation and 1 now is 4 standard deviations off
        self._sd = np.maximum.reduce([normal.std(axis=0), 0.1 * np.abs(self._mu), np.full(X.shape[1], 0.25)])

    def _z(self, X: np.ndarray) -> np.ndarray:
        return np.clip((X - self._mu) / self._sd, -1e3, 1e3)

    def explain(self, x: np.ndarray, k: int = 5) -> list[dict]:
        """The k signals furthest from normal operation (|z| >= 3), one entry per signal."""
        z = self._z(x.reshape(1, -1))[0]
        out, seen = [], set()
        for i in np.argsort(-np.abs(z)):
            if abs(z[i]) < 3 or len(out) == k:
                break
            name = self.feature_names[i]
            signal = name.lstrip("Δ")
            if signal in seen:
                continue
            seen.add(signal)
            out.append({"feature": name, "value": round(float(x[i]), 3),
                        "normal_mean": round(float(self._mu[i]), 3), "z": round(float(z[i]), 1)})
        return out

    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: list[str]) -> "CandidateModel":
        raise NotImplementedError

    def predict_batch(self, X: np.ndarray) -> list[tuple[str, float, float]]:
        raise NotImplementedError

    def predict(self, x: np.ndarray) -> Prediction:
        label, conf, score = self.predict_batch(x.reshape(1, -1))[0]
        return Prediction(label, conf, score, self.model_id,
                          evidence=self.explain(x) if label != NORMAL else [])

    def card(self) -> dict:
        return {"model_id": self.model_id, "description": self.description}


class ThresholdCentroid(CandidateModel):
    model_id = "threshold_centroid"
    description = ("Baseline: max per-feature z-score against normal operation with a trained "
                   "threshold; nearest class centroid names the incident")

    def fit(self, X, y, feature_names):
        self.feature_names = list(feature_names)
        self._fit_normal_stats(X, y)
        Z = self._z(X)
        scores = np.abs(Z).max(axis=1)
        abnormal = y != NORMAL
        best, best_f1 = float(np.median(scores)), -1.0
        for thr in np.unique(np.quantile(scores, np.linspace(0.02, 0.98, 97))):
            pred = scores > thr
            tp = float(np.sum(pred & abnormal))
            f1 = 2 * tp / max(1.0, float(np.sum(pred) + np.sum(abnormal)))
            if f1 > best_f1:
                best, best_f1 = float(thr), f1
        self.threshold = best
        self.classes = sorted(str(c) for c in set(y[abnormal]))
        Zc = np.clip(Z, -50, 50)
        self.centroids = np.array([Zc[y == c].mean(axis=0) for c in self.classes])
        return self

    def predict_batch(self, X):
        Z = self._z(X)
        scores = np.abs(Z).max(axis=1)
        Zc = np.clip(Z, -50, 50)
        out = []
        for z, s in zip(Zc, scores):
            if s <= self.threshold or not self.classes:
                out.append((NORMAL, float(min(1.0, 1 - s / (2 * self.threshold + 1e-9))), float(s)))
                continue
            d = np.linalg.norm(self.centroids - z, axis=1)
            order = np.argsort(d)
            d1 = float(d[order[0]])
            d2 = float(d[order[1]]) if len(order) > 1 else d1 + 1.0
            out.append((str(self.classes[order[0]]), d2 / (d1 + d2 + 1e-9), float(s)))
        return out

    def card(self):
        return {**super().card(), "threshold_max_abs_z": round(self.threshold, 3), "classes": self.classes}


class IForestRF(CandidateModel):
    model_id = "iforest_rf"
    description = ("IsolationForest on normal operation (unknown anomalies) + RandomForest "
                   "classifier (known incident classes)")

    def fit(self, X, y, feature_names):
        from sklearn.ensemble import IsolationForest, RandomForestClassifier
        self.feature_names = list(feature_names)
        self._fit_normal_stats(X, y)
        normal = X[y == NORMAL]
        self.iforest = IsolationForest(n_estimators=150, random_state=self.seed).fit(normal)
        # "abnormal" = scoring below the 1st percentile of normal training data
        self.iforest_threshold = float(np.quantile(self.iforest.score_samples(normal), 0.01))
        self.rf = RandomForestClassifier(n_estimators=150, class_weight="balanced",
                                         random_state=self.seed, n_jobs=1).fit(X, y)
        self.classes = [str(c) for c in self.rf.classes_]
        return self

    def predict_batch(self, X):
        proba = self.rf.predict_proba(X)
        iso = self.iforest.score_samples(X)
        out = []
        for p, s in zip(proba, iso):
            top = int(np.argmax(p))
            label, conf = self.classes[top], float(p[top])
            anomaly = float(self.iforest_threshold - s)          # > 0: less normal than 99% of training
            if label == NORMAL and anomaly > 0.05 and conf < 0.7:
                label, conf = UNKNOWN, 1.0 - conf
            out.append((label, conf, anomaly))
        return out

    def card(self):
        imp = self.rf.feature_importances_
        top = np.argsort(-imp)[:10]
        return {**super().card(), "iforest_threshold": round(self.iforest_threshold, 4),
                "classes": self.classes,
                "top_features": [{"feature": self.feature_names[i], "importance": round(float(imp[i]), 4)}
                                 for i in top]}


CANDIDATES: dict[str, type[CandidateModel]] = {m.model_id: m for m in (ThresholdCentroid, IForestRF)}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(model: CandidateModel, X: np.ndarray, y: np.ndarray, latency_samples: int = 60) -> dict:
    """Held-out metrics: class-level and detection-level, plus single-prediction latency."""
    from sklearn.metrics import f1_score

    preds = [p[0] for p in model.predict_batch(X)]
    labels = sorted(set(y))
    y_det = y != NORMAL
    p_det = np.array([p != NORMAL for p in preds])
    tp = int(np.sum(y_det & p_det))
    fp = int(np.sum(~y_det & p_det))
    fn = int(np.sum(y_det & ~p_det))
    per_class = f1_score(y, preds, labels=labels, average=None, zero_division=0)
    times = []
    for x in X[:latency_samples]:
        t0 = time.perf_counter()
        model.predict_batch(x.reshape(1, -1))
        times.append((time.perf_counter() - t0) * 1000)
    return {
        "macro_f1": round(float(f1_score(y, preds, labels=labels, average="macro", zero_division=0)), 4),
        "detection_f1": round(2 * tp / max(1, 2 * tp + fp + fn), 4),
        "detection_precision": round(tp / max(1, tp + fp), 4),
        "detection_recall": round(tp / max(1, tp + fn), 4),
        "false_alarm_rate": round(fp / max(1, int(np.sum(~y_det))), 4),
        "unknown_anomaly_predictions": int(sum(p == UNKNOWN for p in preds)),
        "per_class_f1": {c: round(float(f), 4) for c, f in zip(labels, per_class)},
        "inference_ms_mean": round(float(np.mean(times)), 3) if times else None,
        "inference_ms_p95": round(float(np.percentile(times, 95)), 3) if times else None,
        "test_samples": int(len(y)),
    }


def window_score(pairs: list[tuple[str, str]]) -> dict:
    """Monitoring score over (predicted, true) pairs from the live network."""
    from sklearn.metrics import f1_score
    if not pairs:
        return {"accuracy": None, "macro_f1": None, "detection_f1": None, "n": 0}
    pred = [p for p, _ in pairs]
    true = [t for _, t in pairs]
    labels = sorted(set(true) | ({p for p in pred if p != UNKNOWN}))
    tp = sum(p != NORMAL and t != NORMAL for p, t in pairs)
    fp = sum(p != NORMAL and t == NORMAL for p, t in pairs)
    fn = sum(p == NORMAL and t != NORMAL for p, t in pairs)
    return {"accuracy": round(sum(p == t for p, t in pairs) / len(pairs), 4),
            "macro_f1": round(float(f1_score(true, pred, labels=labels, average="macro", zero_division=0)), 4),
            "detection_f1": round(2 * tp / max(1, 2 * tp + fp + fn), 4) if (tp + fp + fn) else 1.0,
            "false_alarms": fp, "missed": fn, "n": len(pairs)}


# ---------------------------------------------------------------------------
# Remediation proposal attached to a prediction
# ---------------------------------------------------------------------------

def propose_remediation(label: str, catalog: dict) -> dict | None:
    """The catalog playbook for a predicted incident class (None for normal / unknown)."""
    attack = next((a for a in catalog["attacks"] if a["id"] == label), None)
    if attack is None:
        return None
    pb = attack["playbook"]
    return {
        "attack_id": attack["id"], "name": attack["name"], "affected_nf": list(attack["affected_nf"]),
        "basic_auto_safe_steps": [s["action"]["fn"] for s in pb["basic"] if s.get("auto_safe")],
        "steps_needing_approval": {t: [s["action"]["fn"] for s in pb[t] if s["is_state_changing"]]
                                   for t in ("intermediate", "advanced")},
        "references": {"enisa": " ".join(attack["enisa_ref"].split()),
                       "3gpp": " ".join(attack["threegpp_ref"].split())},
    }
