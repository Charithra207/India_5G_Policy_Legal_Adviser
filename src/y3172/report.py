"""Run report of the Y.3172 pipeline: markdown for people, JSON for tools."""

from __future__ import annotations

from src.y3172.models import NORMAL, window_score

Y3172_MAP = [
    ("ML Intent", "cl. 7.4, 8.1 NOTE 12", "intents/*.yaml, src/y3172/intent.py"),
    ("SRC", "cl. 8.1", "simulated NFs (sim/engine.py) via read-only diagnostics"),
    ("C (collector)", "cl. 8.1", "src/y3172/nodes.py Collector"),
    ("PP (preprocessor)", "cl. 8.1", "src/y3172/nodes.py Preprocessor"),
    ("M (model)", "cl. 8.1", "src/y3172/models.py (threshold_centroid, iforest_rf)"),
    ("P (policy)", "cl. 8.1 NOTE 5", "src/y3172/policy_node.py + the specialist-agent swarm (src/)"),
    ("D (distributor)", "cl. 8.1", "src/y3172/distributor.py"),
    ("SINK", "cl. 8.1", "remediation (ir/engine.py), notices, evidence, escalation"),
    ("MLFO", "cl. 3.2.2, 8.1, 8.2", "src/y3172/mlfo.py"),
    ("ML sandbox + simulated underlay", "cl. 3.2.6, 8.2", "sim/datagen.py, sandbox simulations in the run folder"),
    ("ML underlay network", "cl. 3.2.7", "live simulation in the run folder (contained; not a real network)"),
]


def _f(v, nd=3):
    return "—" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def build_report(mlfo) -> dict:
    i, sel = mlfo.intent, mlfo.history[0] if mlfo.history else {}
    pairs = [(t["prediction"], t["scored_truth"]) for t in mlfo.ticks]
    overall = window_score(pairs)
    notices = [n for inc in mlfo.incidents for s in inc["sinks"] if s["sink"] == "regulatory_notices"
               for n in s.get("notices", []) if "recipient" in n]
    escalations = [s for inc in mlfo.incidents for s in inc["sinks"] if s["sink"] == "escalation"]
    attack_incidents = [x for x in mlfo.incidents if x["lab_truth"] != NORMAL]
    delays = [x["detection_delay_ticks"] for x in attack_incidents if x["detection_delay_ticks"] is not None]
    fp_applied = [x for x in mlfo.incidents if not x["correct"] and any(
        s["sink"] == "remediation" and s.get("approved") and s["status"] != "held" for s in x["sinks"])]
    summary = {
        "intent_id": i.intent_id, "policy_mode": i.policy.mode, "ticks": len(mlfo.ticks),
        "initial_model": sel.get("selected"), "final_model": mlfo.model.model_id if mlfo.model else None,
        "live_accuracy": overall["accuracy"], "live_macro_f1": overall["macro_f1"],
        "live_detection_f1": overall["detection_f1"],
        "false_alarm_ticks": overall.get("false_alarms", 0), "missed_ticks": overall.get("missed", 0),
        "incidents_dispatched": len(mlfo.incidents),
        "incidents_correctly_classified": sum(x["correct"] for x in mlfo.incidents),
        "remediations_applied_on_wrong_classification": len(fp_applied),
        "attacks_injected": len(getattr(mlfo, "injected", {})),
        "attacks_detected_within_deadline": sum(d <= i.decision_deadline_ticks for d in delays),
        "mean_detection_delay_ticks": round(sum(delays) / len(delays), 2) if delays else None,
        "deadline_ticks": i.decision_deadline_ticks,
        "reselections": len(getattr(mlfo, "reselections", [])),
        "notices_drafted": len(notices), "escalations": len(escalations),
        "sandbox_validation_passed": sum(r["detected"] and r["playbook_resolved"] for r in mlfo.sandbox_validation),
        "sandbox_validation_total": len(mlfo.sandbox_validation),
        "mean_inference_ms": round(sum(t["inference_ms"] for t in mlfo.ticks) / max(1, len(mlfo.ticks)), 3),
    }
    L = [f"# Y.3172 ML pipeline run — {i.title}", "",
         f"Run `{mlfo.run_id}` · intent `{i.intent_id}` ({i.path}) · policy node in **{i.policy.mode}** mode", "",
         "> Contained lab: the network is the Python simulation in `sim/`; nothing reaches a real system. "
         "Decision support, not legal advice.", "", "## Summary", "", "| measure | value |", "|---|---|"]
    L += [f"| {k.replace('_', ' ')} | {_f(v)} |" for k, v in summary.items()]

    L += ["", "## 1. Pipeline instantiated by the MLFO from the ML Intent", "",
          f"Chain: {mlfo.instantiation['chain']} · {mlfo.instantiation['feature_count']} features · "
          f"levels used: {', '.join(mlfo.instantiation['levels'])}", "", "| node | id | level | detail |", "|---|---|---|---|"]
    for n in mlfo.instantiation["nodes"]:
        detail = ", ".join(n.get("telemetry", [])) or n.get("mode", "") or ", ".join(n.get("candidates", []))
        L.append(f"| {n['node']} | `{n['id']}` | {n['level']} | {detail} |")
    L += ["", "Reference points (Y.3172 Figure 4):", ""]
    L += [f"- **{k}** — {v}" for k, v in mlfo.instantiation["reference_points"].items()]

    for k, s in enumerate(mlfo.history, 1):
        L += ["", f"## 2.{k} ML sandbox — training and model selection ({s['reason']})", "",
              f"{s['samples']} labelled samples ({s['train_samples']} train / {s['test_samples']} held out, "
              f"split by episode), background load {s['training_load']}, {s['features']} features. "
              f"Rule: {s['rule']}.", "",
              "| candidate | macro-F1 | detection F1 | false-alarm rate | p95 inference ms | meets intent |",
              "|---|---|---|---|---|---|"]
        for c in s["candidates"]:
            m = c["metrics"]
            L.append(f"| `{c['model_id']}`{' **(selected)**' if c['model_id'] == s['selected'] else ''} | "
                     f"{m['macro_f1']} | {m['detection_f1']} | {m['false_alarm_rate']} | {m['inference_ms_p95']} | "
                     f"{'yes' if c['eligible'] else 'no'} |")
        if s.get("warning"):
            L += ["", f"**{s['warning']}**"]
        top = next((c["card"].get("top_features") for c in s["candidates"] if c["model_id"] == s["selected"]), None)
        if top:
            L += ["", "Most important features of the selected model: " +
                  ", ".join(f"`{t['feature']}` ({t['importance']})" for t in top[:6])]

    if mlfo.sandbox_validation:
        L += ["", "## 3. Sandbox evaluation of effects on the network (before live use)", "",
              "| incident | detected as | confidence | playbook resolved it | tier | after remediation |",
              "|---|---|---|---|---|---|"]
        for r in mlfo.sandbox_validation:
            L.append(f"| {r['incident']} | {r['detected_as']}{' ✔' if r['detected'] else ' ✘'} | {r['confidence']} | "
                     f"{'yes' if r['playbook_resolved'] else 'no'} | {r['resolved_in'] or '—'} | {r['after_remediation']} |")

    L += ["", "## 4. Live operation", "", "| tick | clock | events | prediction (confidence) | truth | model | action |",
          "|---|---|---|---|---|---|---|"]
    for t in mlfo.ticks:
        mark = "" if t["prediction"] == t["scored_truth"] else " ✘"
        L.append(f"| {t['tick']} | {t['clock']} | {'; '.join(t['events'])} | {t['prediction']} ({t['confidence']}){mark} | "
                 f"{t['truth']} | {t['model']} | {t['action'] or ''} |")

    L += ["", "## 5. Incidents", ""]
    if not mlfo.incidents:
        L.append("No incident was dispatched.")
    for x in mlfo.incidents:
        d, p = x["decision"], x["prediction"]
        L += [f"### {x['incident_id']} — {p['label']} at {x['detected_at']}", "",
              f"- Model `{p['model_id']}`, confidence {p['confidence']}; lab truth `{x['lab_truth']}` "
              f"({'correct' if x['correct'] else 'WRONG'}); detection delay {_f(x['detection_delay_ticks'])} tick(s)",
              f"- P node: **{d['decision']}** ({d['mode']}) — rules: {', '.join(d['rules_applied'])}"]
        L += [f"  - {r}" for r in d["reasons"]]
        if x in fp_applied:
            L.append("- ⚠ **The classification was wrong and its playbook was still applied** (the operator "
                     "approved it). Check what it changed below; this is what blocking mode and the "
                     "operator's review exist to prevent.")
        if p.get("evidence"):
            L.append("- Why the model flagged it: " + "; ".join(
                f"`{e['feature']}` = {e['value']} (normal ≈ {e['normal_mean']})" for e in p["evidence"][:4]))
        if d["obligations"]:
            L += ["", "| obligation | source (checked word for word) |", "|---|---|"]
            L += [f"| {o['summary']} | {o['citation']}{'' if o['verified'] else ' ⚠'} |" for o in d["obligations"]]
        if d.get("adviser"):
            a = d["adviser"]
            if "error" in a:
                L += ["", f"Specialist agents: {a['error']}"]
            else:
                L += ["", f"Specialist agents ({', '.join(a['active_agents'])}): {a['claims']} claims; verifier "
                      f"outcomes {a['verifier_outcomes']}; Coordinator: {a['counts']}."]
                for g in a["potential_policy_gaps"][:2]:
                    L.append(f"  - potential gap: {g[:220]}")
        L += ["", "SINKs:", ""]
        for s in x["sinks"]:
            L.append(f"- **{s['sink']}**: {s['status']} — {s.get('detail', '')}")
            for n in s.get("notices", []):
                if "recipient" in n:
                    L.append(f"  - {n['recipient']}: {n['what'][:90]}… — deadline **{n['deadline']}** — "
                             f"{n['status']} ({n['source_check']})")
                else:
                    L.append(f"  - action: {n['action']} ({n['source_check']})")
        L.append("")

    resel = getattr(mlfo, "reselections", [])
    L += ["## 6. Monitoring and re-selection", "",
          f"Rolling window {i.monitoring.window} ticks; minimum {i.monitoring.metric} {i.monitoring.min_score}."]
    if resel:
        for r in resel:
            L.append(f"- Tick {r['tick']}: rolling score {r['rolling_score']} → sandbox re-calibrated "
                     f"(estimated live background load {_f(r['estimated_live_load'], 2)}), retrained on load "
                     f"{r['training_load']}; `{r['previous_model']}` → `{r['new_model']}`.")
    else:
        L.append("- No re-selection was needed.")

    L += ["", "## 7. Y.3172 mapping", "", "| Y.3172 component | clause | implementation |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in Y3172_MAP]
    L += ["", f"Audit trail (hash-chained): `{mlfo.trail.path.name}`.", "",
          "_Simulated network and incidents; legal obligations are shown with their sources for a qualified "
          "person to review. Not legal advice._"]
    data = {"summary": summary, "intent": i.raw, "instantiation": mlfo.instantiation,
            "selections": mlfo.history, "sandbox_validation": mlfo.sandbox_validation, "ticks": mlfo.ticks,
            "incidents": mlfo.incidents, "reselections": resel}
    return {"markdown": "\n".join(L) + "\n", "data": data}
