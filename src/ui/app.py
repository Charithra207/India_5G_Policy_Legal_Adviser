"""
Demonstration UI — India 5G Policy & Legal Adviser
===================================================
    streamlit run src/ui/app.py

Live run: release the staged incident one chunk at a time into the core
pipeline.  Replay: step through a recorded audit trail, check its hash chain,
and optionally re-execute it to confirm the record is reproduced.

Everything displayed comes from a stage entry of the audit trail, which is
built from the pipeline's own AuditRecord.  The UI computes nothing but
layout and counts.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from src.audit.explain import explain_stage  # noqa: E402
from src.audit.replay import list_runs, load_run, reexecute  # noqa: E402
from src.audit.trail import audit_dir  # noqa: E402
from src.scenario.catalog import SCENARIOS, get_scenario  # noqa: E402
from src.scenario.engine import ScenarioEngine  # noqa: E402

logging.disable(logging.WARNING)

OUTCOME_STYLE = {
    "VERIFIED": ":green[**VERIFIED**]",
    "INCOMPLETE": ":orange[**INCOMPLETE**]",
    "UNSUPPORTED": ":red[**UNSUPPORTED**]",
    "CONFLICT": ":violet[**CONFLICT**]",
    None: ":gray[**NOT VERIFIED**]",
}
OUTCOME_MEANING = {
    "VERIFIED": "supported by the cited source, in force, amendments checked",
    "INCOMPLETE": "supported, but an amendment/exception applies or in-force "
                  "status / amendments were not checked; or a potential gap",
    "UNSUPPORTED": "the Canonical KB does not support it — preliminary only",
    "CONFLICT": "contradicted by another finding or source",
}
TABLE_A1 = (
    ("confirmed_facts", "1. Confirmed facts", "Facts established about the incident itself"),
    ("evidence_backed_conclusions", "2. Evidence-backed conclusions",
     "Conclusions the Verifier found supported by authoritative sources"),
    ("uncertain_conclusions", "3. Uncertain conclusions",
     "Conclusions with incomplete or ambiguous support"),
    ("conflicting_findings", "4. Conflicting findings",
     "Findings on which agents or sources disagree"),
    ("potential_policy_gaps", "5. Potential policy gaps",
     "Areas of unclear or absent coverage, framed as potential rather than established"),
)
HUMAN_REVIEW = (
    "Legal interpretation, regulatory decisions, and institutional action require "
    "qualified human judgment. This assessment is decision support only and does "
    "not replace legal counsel, regulators, or government decision-makers."
)


def shown_path(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def agent_name(agent_id: str) -> str:
    return {"critical_infrastructure": "Critical Infrastructure",
            "policy_legal": "Policy & Legal", "policy_gap": "Policy Gap",
            }.get(agent_id, agent_id.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Shared resources
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading knowledge bases and embedding model …")
def live_registry():
    from src.rag.registry import build_registry
    return build_registry()


# ---------------------------------------------------------------------------
# Rendering — one stage entry
# ---------------------------------------------------------------------------

def render_stage_progress(spec, stages: list[dict], index: int) -> None:
    cols = st.columns(len(spec.stages))
    for i, (col, stage) in enumerate(zip(cols, spec.stages)):
        if i == index:
            mark, colour = "▶ shown", "blue"
        elif i < len(stages):
            mark, colour = "✓ released", "green"
        else:
            mark, colour = "not yet released", "gray"
        col.markdown(f":{colour}[**{stage.label}** — {mark}]")
        col.caption(stage.information_released)


def render_scenario(spec, header: dict | None) -> None:
    st.header("Scenario")
    st.markdown(f"**{spec.title}** (DOCX {spec.docx_section})")
    st.write(spec.summary)
    if header:
        st.caption(f"Run `{header['run_id']}` · recorded {header['recorded_at'][:19]} UTC")


def render_chunk(entry: dict) -> None:
    stage = entry["stage"]
    st.header(f"Current chunk — {stage['label']}")
    st.markdown(f"**Information released:** {stage['information_released']}")
    st.caption(f"Chunk ID `{stage['chunk_id']}` · scenario time {stage['scenario_time']}"
               f" · earlier chunks visible: {', '.join(stage['prior_chunks']) or 'none'}")
    if stage["new_facts"]:
        st.markdown("**New facts in this chunk**")
        for fact in stage["new_facts"]:
            st.markdown(f"- {fact}")
    st.markdown(f"**DOCX expected assessment change:** {stage['docx_expected_change']}")
    changes = entry["coordinator"]["changes_from_prior"]
    if changes:
        st.info("**What changed since the previous chunk**\n\n"
                + "\n".join(f"- {c}" for c in changes))


def render_agents(entry: dict) -> None:
    orch = entry["orchestrator"]
    st.header("Active agents")
    st.markdown("  ".join(
        f":blue-background[**{agent_name(a)}**{' · NEW' if a in orch['newly_activated'] else ''}]"
        for a in orch["active_agents"]))
    if orch["no_longer_active"]:
        st.caption("Not active at this stage: "
                   + ", ".join(agent_name(a) for a in orch["no_longer_active"]))
    expected = ", ".join(agent_name(a) for a in orch["docx_primary_agents"])
    if orch["matches_docx_table"]:
        st.success(f"Orchestrator selection matches the DOCX stage table ({expected}).")
    elif orch["matches_docx_table"] is False:
        st.error(f"Orchestrator selection differs from the DOCX stage table ({expected}).")
    st.caption("Selected by the Orchestrator from the released information and the "
               "incident state; the DOCX table is shown for comparison only.")


def render_claim(claim: dict) -> None:
    st.markdown(f"{OUTCOME_STYLE.get(claim['verifier_outcome'], OUTCOME_STYLE[None])} "
                f"— {claim['claim']}")
    lines = []
    if claim["citations"]:
        lines.append("Cites: " + "; ".join(
            f"{c['source_title']}, {c['section']}" + (f" (p. {c['page']})" if c["page"] else "")
            for c in claim["citations"]))
    else:
        lines.append("No citation — the agent's own reading of the incident facts")
    lines.append(f"Verifier: {claim['verifier_rationale']}")
    if claim["cross_domain_flag"]:
        lines.append(f"Cross-domain: {claim['cross_domain_note']}")
    st.caption("  \n".join(lines))


def render_findings(entry: dict) -> None:
    st.header("Agent findings")
    tabs = st.tabs([agent_name(a["agent_id"]) for a in entry["agents"]])
    for tab, agent in zip(tabs, entry["agents"]):
        with tab:
            st.markdown(f"**Decision summary:** {agent['decision_summary']}")
            for key, value in agent["mandate_output"].items():
                shown = ", ".join(map(str, value)) if isinstance(value, list) else value
                st.markdown(f"- *{key.replace('_', ' ')}:* {shown}")
            st.markdown(f"**Claims ({len(agent['claims'])})**")
            for claim in agent["claims"]:
                render_claim(claim)
            if agent["uncertainty_notes"]:
                st.markdown("**Uncertainty**")
                for note in agent["uncertainty_notes"]:
                    st.markdown(f"- {note}")
            if agent["missing_facts"]:
                st.markdown("**Missing facts**")
                for fact in agent["missing_facts"]:
                    st.markdown(f"- {fact}")
            with st.expander("Input visible to this agent"):
                st.json(agent["visible_input"], expanded=False)
            with st.expander(f"Retrieval queries ({len(agent['queries'])})"):
                for q in agent["queries"]:
                    st.markdown(f"- {q}")


def render_passage(p: dict) -> None:
    title = f"**{p['source_title']}**, {p['section']}"
    if p["section_title"]:
        title += f" — {p['section_title']}"
    if p["page"]:
        title += f" (p. {p['page']})"
    if p["jurisdiction"].strip().lower() != "india":
        title += f"  :orange-background[REFERENCE ONLY — not Indian law ({p['jurisdiction']})]"
    st.markdown(title)
    st.markdown("> " + " ".join(p["excerpt"].split()))
    notes = [
        "in-force status not verified" if p["effective"] is None
        else ("in force" if p["effective"] else "NOT in force"),
        "amendments checked" if p["amendment_checked"] else "amendments not checked",
    ]
    if p["date_issued"]:
        notes.append(f"dated {p['date_issued']}")
    if p["url"]:
        notes.append(f"[source file]({p['url']})")
    if p["provenance_note"]:
        notes.append(f"provenance: {p['provenance_note']}")
    st.caption(" · ".join(notes))


def render_evidence(entry: dict) -> None:
    st.header("Evidence / sources")
    for agent in entry["agents"]:
        passages = agent["retrieved_passages"]
        real = [p for p in passages if not p["is_stub"]]
        label = (f"{agent_name(agent['agent_id'])} — {len(real)} passage(s) retrieved "
                 f"from its own knowledge base")
        with st.expander(label, expanded=False):
            if not real:
                st.warning("No passage retrieved (stub knowledge base). Claims from this "
                           "agent cannot be supported.")
            for p in real:
                render_passage(p)
                st.divider()


def render_verifier(entry: dict) -> None:
    st.header("Verifier result")
    counts = entry["verifier"]["outcome_counts"]
    cols = st.columns(4)
    for col, outcome in zip(cols, ("VERIFIED", "INCOMPLETE", "UNSUPPORTED", "CONFLICT")):
        col.metric(outcome, counts.get(outcome, 0))
        col.caption(OUTCOME_MEANING[outcome])
    if not counts.get("VERIFIED"):
        st.caption("No claim is VERIFIED: no ingested source's in-force status or "
                   "amendment history has been checked, so quoted provisions are "
                   "INCOMPLETE at best. This is the correct result, not a fault.")
    for outcome in ("CONFLICT", "UNSUPPORTED", "INCOMPLETE", "VERIFIED"):
        claims = [(a["agent_id"], c) for a in entry["agents"] for c in a["claims"]
                  if c["verifier_outcome"] == outcome]
        if claims:
            with st.expander(f"{outcome} — {len(claims)} claim(s)"):
                for agent_id, c in claims:
                    st.markdown(f"**{agent_name(agent_id)}:** {c['claim']}")
                    st.caption(c["verifier_rationale"])
    render_conflicts(entry)
    missing = entry["verifier"]["missing_evidence"]
    if missing:
        with st.expander(f"Missing evidence ({len(missing)})"):
            for item in missing:
                st.markdown(f"- {item}")


def render_conflict_side(col, label: str, side: dict) -> None:
    col.markdown(f"**{label} — {agent_name(side['agent_id'])}** ({side['chunk_id']})")
    col.markdown(side["claim"])
    if not side["evidence"]:
        col.caption("No passage cited.")
    for p in side["evidence"]:
        col.markdown(f"*Evidence:* **{p['source_title']}**, {p['section']}")
        col.markdown("> " + " ".join(p["excerpt"].split()))


def render_conflicts(entry: dict) -> None:
    conflicts = entry["verifier"].get("conflict_details")
    if conflicts is None:                        # recorded before structured conflicts
        for item in entry["verifier"]["conflicts"]:
            st.error(item)
        return
    for c in conflicts:
        st.subheader(f"Conflict — {c['rule'].replace('_', ' ')}")
        st.error(c["basis"])
        left, right = st.columns(2)
        render_conflict_side(left, "Finding A", c["finding_a"])
        render_conflict_side(right, "Finding B", c["finding_b"])
        st.markdown(f"**Status:** :violet[{c['status']}]")
        st.markdown(f"**Coordinator treatment:** {c['coordinator_treatment']}")


def render_coordinator(entry: dict) -> None:
    coord = entry["coordinator"]
    st.header("Coordinator assessment")
    st.caption("Categories kept separate, in DOCX Annex-1 Table A1 order. The assessment "
               "covers the whole incident so far: conclusions of agents not active in this "
               "chunk are carried forward and tagged, not dropped.")
    questions = coord.get("open_questions", [])
    if questions and questions[0].startswith("No conclusion is evidence-backed"):
        st.warning(questions[0])
    for key, title, meaning in TABLE_A1:
        items = coord[key]
        with st.expander(f"{title} ({len(items)})", expanded=key in ("confirmed_facts",
                                                                     "conflicting_findings")):
            st.caption(meaning)
            for item in items:
                if key == "conflicting_findings":
                    st.text(item)
                elif item.startswith("[carried forward"):
                    st.markdown(f"- :gray[{item}]")
                else:
                    st.markdown(f"- {item}")
            if not items:
                st.caption("None at this stage.")
    if coord["relevant_institutions"]:
        st.markdown("**Relevant institutions:** " + "; ".join(coord["relevant_institutions"]))
    rest = [q for q in questions if not q.startswith("No conclusion is evidence-backed")]
    if rest:
        with st.expander(f"Open questions — evidence still missing ({len(rest)})"):
            for q in rest:
                st.markdown(f"- {q}")


def render_gaps_and_links(entry: dict) -> None:
    coord = entry["coordinator"]
    st.header("Policy gap / cross-domain findings")
    st.subheader("Cross-domain relationships")
    st.caption("Each relationship is established from cited evidence: a shared provision, "
               "an instrument whose text names an Act cited in another domain, or parallel "
               "reporting duties for the same incident.")
    details = {d["note"]: d for d in entry["verifier"].get("cross_domain_details", [])}
    for rel in coord["cross_domain_relationships"]:
        if rel.startswith("[carried forward"):
            st.markdown(f"- :gray[{rel}]")
            continue
        st.markdown(f"- {rel}")
        link = details.get(rel)
        if link and link["members"]:
            with st.expander("Findings linked", expanded=False):
                for m in link["members"]:
                    st.markdown(f"- **{agent_name(m['agent_id'])}** ({m['chunk_id']}): "
                                f"{m['claim'][:300]}")
    if not coord["cross_domain_relationships"]:
        st.caption("None established from the evidence at this stage.")
    st.subheader("Potential policy gaps")
    gaps = coord["potential_policy_gaps"]
    if "policy_gap" not in entry["orchestrator"]["active_agents"]:
        st.caption("The Policy Gap Agent is not active at this stage.")
    for gap in gaps:
        if gap.startswith("[CANDIDATE GAP AREA"):
            st.markdown(f":gray[{gap}]")
        else:
            st.markdown(f"- {gap}")
    if gaps:
        st.caption("Potential gaps are for expert review; they are not findings that "
                   "policy is inadequate.")


def render_decision_path(entry: dict, expanded: bool) -> None:
    """The reviewer's questions, answered from the recorded entry."""
    with st.expander("Decision path — what happened, who acted, evidence, conclusion, "
                     "verification, Coordinator", expanded=expanded):
        for question, lines in explain_stage(entry).items():
            st.markdown(f"**{question}**")
            for line in lines:
                st.markdown(("    " if line.startswith("  ") else "") + f"- {line.strip()}")


def render_uncertainty(entry: dict) -> None:
    coord = entry["coordinator"]
    st.header("Uncertainty")
    st.caption("What is not established at this stage. Uncertain conclusions are listed in "
               "the Coordinator assessment below; nothing here is filled from outside the evidence.")
    st.metric("Uncertain conclusions", len(coord["uncertain_conclusions"]))
    notes = [(a["agent_id"], n) for a in entry["agents"] for n in a["uncertainty_notes"]]
    if notes:
        with st.expander(f"Agents' uncertainty notes ({len(notes)})"):
            for agent_id, note in notes:
                st.markdown(f"- **{agent_name(agent_id)}:** {note}")
    questions = coord.get("open_questions", [])
    if questions:
        with st.expander(f"Missing evidence / open questions ({len(questions)})"):
            for q in questions:
                st.markdown(f"- {q}")


def render_previous(stages: list[dict], index: int) -> None:
    if index == 0:
        return
    st.header("Previous findings")
    for entry in stages[:index]:
        with st.expander(f"{entry['stage']['label']} — "
                         f"{entry['stage']['information_released']}"):
            for agent in entry["agents"]:
                outcomes = {}
                for c in agent["claims"]:
                    outcomes[c["verifier_outcome"]] = outcomes.get(c["verifier_outcome"], 0) + 1
                st.markdown(f"**{agent_name(agent['agent_id'])}:** {agent['decision_summary']}")
                st.caption(", ".join(f"{k}: {v}" for k, v in outcomes.items()))


def render_audit_entry(entry: dict, path) -> None:
    st.header("Audit record for this stage")
    st.caption(f"Entry {entry['seq']} of `{path}` · recorded {entry['recorded_at'][:19]} UTC · "
               f"hash `{entry['hash'][:16]}…` · previous `{entry['prev_hash'][:16]}…`")
    with st.expander("Full audit entry (JSON)"):
        st.json(entry, expanded=False)


def render_stage(spec, stages: list[dict], index: int, header: dict | None, path,
                 explain_open: bool = False) -> None:
    entry = stages[index]
    render_stage_progress(spec, stages, index)
    render_scenario(spec, header)
    render_decision_path(entry, explain_open)
    render_chunk(entry)
    render_agents(entry)
    render_findings(entry)
    render_evidence(entry)
    render_verifier(entry)
    render_uncertainty(entry)
    render_coordinator(entry)
    render_gaps_and_links(entry)
    render_previous(stages, index)
    if "hash" in entry:
        render_audit_entry(entry, path)


def render_kb_status(kb_status: dict[str, bool], header: dict | None = None) -> None:
    st.sidebar.subheader("Knowledge bases")
    for kb, live in kb_status.items():
        st.sidebar.markdown(f"{'🟢' if live else '🔴'} {kb} — {'live' if live else 'stub'}")
    if not all(kb_status.values()):
        st.sidebar.warning("Stub KBs retrieve nothing; every claim from them is UNSUPPORTED. "
                           "Build with `python -m src.rag.build`.")
    build = (header or {}).get("knowledge_base_build") or {}
    missing = build.get("not_ingested")
    if missing is None:
        manifest = ROOT / "knowledge_base" / "ingestion_manifest.json"
        if manifest.exists():
            docs = json.loads(manifest.read_text(encoding="utf-8")).get("documents", [])
            missing = [d["id"] for d in docs if d.get("status") != "ingested"]
    if missing:
        st.sidebar.caption("Sources not ingested: " + ", ".join(missing))


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def stage_picker(stages: list[dict], key: str) -> int:
    labels = [s["stage"]["label"] for s in stages]
    choice = st.radio("Stage shown", labels, index=len(labels) - 1, horizontal=True,
                      key=f"{key}-{len(labels)}")
    return labels.index(choice)


def live_mode() -> None:
    scenario_id = st.sidebar.selectbox(
        "Scenario", list(SCENARIOS), format_func=lambda s: f"{s} — {SCENARIOS[s].title}")
    use_live = st.sidebar.toggle("Use live knowledge bases", value=True)

    engine: ScenarioEngine | None = st.session_state.get("engine")
    if engine is None or engine.spec.scenario_id != scenario_id \
            or st.session_state.get("engine_live") != use_live:
        if st.sidebar.button("Start run", type="primary"):
            registry = live_registry() if use_live else None
            st.session_state.engine = ScenarioEngine(scenario_id, registry=registry)
            st.session_state.engine_live = use_live
            st.rerun()
        spec = get_scenario(scenario_id)
        render_scenario(spec, None)
        st.info("Press **Start run** to begin. Chunks are released one at a time; later "
                "facts are not visible to earlier agent runs.")
        for stage in spec.stages:
            st.markdown(f"- **{stage.label}** — {stage.information_released}")
        return

    render_kb_status(engine.kb_status)
    st.sidebar.caption(f"Audit trail: `{shown_path(engine.audit_path)}`")
    if engine.has_next():
        nxt = engine.spec.stages[engine.stages_run]
        if st.sidebar.button(f"Release next chunk ({nxt.label})", type="primary"):
            with st.spinner(f"Running {nxt.label} through the pipeline …"):
                engine.next_stage()
            st.rerun()
    else:
        st.sidebar.success("All chunks released. The run is complete and can be replayed.")
    if st.sidebar.button("New run"):
        del st.session_state["engine"]
        st.rerun()

    if not engine.stages:
        render_stage_progress(engine.spec, [], -1)
        render_scenario(engine.spec, None)
        st.info(f"Run `{engine.trail.run_id}` started. Release the first chunk "
                f"({engine.spec.stages[0].label}) from the sidebar.")
        return
    index = stage_picker(engine.stages, "live")
    render_stage(engine.spec, engine.stages, index, engine.trail.entries[0],
                 shown_path(engine.audit_path))


def replay_mode() -> None:
    runs = list_runs()
    if not runs:
        st.info(f"No recorded runs in `{audit_dir()}`. Do a live run first.")
        return
    path = st.sidebar.selectbox("Recorded run", runs, format_func=lambda p: p.name)
    run = load_run(path)
    spec = get_scenario(run.header["scenario_id"])
    render_kb_status(run.header["knowledge_bases_live"], run.header)
    if run.header.get("knowledge_base_note"):
        st.warning(f"**{run.header['knowledge_base_note']}.**")

    if run.intact:
        st.sidebar.success(f"Hash chain intact ({len(run.stages)} stage entries).")
    else:
        st.sidebar.error("Audit trail integrity check FAILED:\n\n"
                         + "\n".join(f"- {p}" for p in run.integrity_problems))
    code = run.header.get("code", {})
    st.sidebar.caption(f"Recorded at commit `{code.get('commit', '')[:10]}`"
                       + (" with uncommitted changes" if code.get("uncommitted_changes") else ""))
    if not run.stages:
        st.info("This run has no recorded stages.")
        return

    key = f"replay-step-{path.name}"
    step = st.session_state.setdefault(key, 0)
    c1, c2, c3 = st.columns([1, 1, 4])
    if c1.button("◀ Previous", disabled=step == 0):
        st.session_state[key] = step - 1
        st.rerun()
    if c2.button("Next ▶", disabled=step >= len(run.stages) - 1):
        st.session_state[key] = step + 1
        st.rerun()
    c3.markdown(f"Replaying stage **{step + 1} of {len(run.stages)}** "
                f"({'complete run' if run.completed else 'incomplete run'})")

    if st.sidebar.button("Re-execute and compare"):
        from src.scenario.conflict_fixture import FIXTURE_LABEL, conflict_registry
        if run.header.get("knowledge_base_note") == FIXTURE_LABEL:
            registry = conflict_registry()
        elif all(run.header["knowledge_bases_live"].values()):
            registry = live_registry()
        else:
            registry = None
        with st.spinner("Re-running the recorded chunk sequence through the pipeline …"):
            diffs = reexecute(run, registry)
        st.session_state[f"diffs-{path.name}"] = diffs
    diffs = st.session_state.get(f"diffs-{path.name}")
    if diffs is not None:
        if diffs:
            st.warning("Re-execution differs from the record (code or knowledge bases "
                       "changed since recording):\n\n" + "\n".join(f"- {d}" for d in diffs))
        else:
            st.success("Re-execution reproduced every recorded stage: same agents, "
                       "passages, claims, verifier outcomes and assessment.")

    render_stage(spec, run.stages, step, run.header, shown_path(path), explain_open=True)


def main() -> None:
    st.set_page_config(page_title="India 5G Policy & Legal Adviser", layout="wide")
    st.title("India 5G Policy & Legal Adviser")
    st.warning(f"**Human review required.** {HUMAN_REVIEW}")
    mode = st.sidebar.radio("Mode", ["Live run", "Replay"], horizontal=True)
    if mode == "Live run":
        live_mode()
    else:
        replay_mode()


main()
