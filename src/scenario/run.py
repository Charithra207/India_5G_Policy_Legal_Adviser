"""
Command-line scenario runner and replay
=======================================
    python -m src.scenario.run --stages 2            # Day-1 test: T0 then T1
    python -m src.scenario.run                       # all four stages
    python -m src.scenario.run --replay outputs/audit/<run>.jsonl [--reexecute]
    python -m src.scenario.run --conflict-demo       # labelled fixture KBs (see
                                                     # src/scenario/conflict_fixture.py)

Live knowledge bases are used when built (python -m src.rag.build);
`--stub` forces the core's stub KBs.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.audit.replay import load_run, reexecute
from src.scenario.catalog import DEFAULT_SCENARIO, SCENARIOS
from src.scenario.engine import ScenarioEngine

WIDTH = 78


def print_stage(entry: dict) -> None:
    stage, orch, coord = entry["stage"], entry["orchestrator"], entry["coordinator"]
    print("=" * WIDTH)
    print(f"{stage['label']}  [{stage['chunk_id']}]  {stage['information_released']}")
    print("-" * WIDTH)
    print("Active agents   :", ", ".join(orch["active_agents"]))
    if orch["newly_activated"]:
        print("Newly activated :", ", ".join(orch["newly_activated"]))
    print("DOCX table      :", ", ".join(orch["docx_primary_agents"]),
          "→ match" if orch["matches_docx_table"] else "→ DIFFERS")
    for agent in entry["agents"]:
        real = [p for p in agent["retrieved_passages"] if not p["is_stub"]]
        print(f"\n  [{agent['agent_id']}] {agent['decision_summary']}")
        for fact in agent["visible_input"].get("agent_view", []):
            print(f"    only this agent was told: {fact}")
        print(f"    passages retrieved: {len(real)}")
        for p in real[:3]:
            print(f"      - {p['source_title']}, {p['section']}"
                  + (f" (p. {p['page']})" if p["page"] else ""))
        for c in agent["claims"]:
            print(f"    {c['verifier_outcome'] or 'NOT VERIFIED':<11} {c['claim'][:WIDTH + 20]}")
        trace = agent.get("llm_reasoning") or {}
        if trace:
            print(f"    LLM ({trace.get('provider')}:{trace.get('model')}): {trace.get('status', '')}")
            if trace.get("reasoning_summary"):
                print(f"      rationale: {trace['reasoning_summary'][:WIDTH * 2]}")
    counts = entry["verifier"]["outcome_counts"]
    print("\nVerifier        :", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print("Coordinator     :", "; ".join(
        f"{k.replace('_', ' ')} {len(coord[k])}" for k in (
            "confirmed_facts", "evidence_backed_conclusions", "uncertain_conclusions",
            "conflicting_findings", "potential_policy_gaps")))
    for change in coord["changes_from_prior"]:
        print("Changed         :", change)
    kinds: dict[str, int] = {}
    for link in entry["verifier"].get("cross_domain_details", []):
        kinds[link["kind"]] = kinds.get(link["kind"], 0) + 1
    if kinds:
        print("Cross-domain    :", ", ".join(f"{k.replace('_', ' ')} {n}"
                                               for k, n in sorted(kinds.items())))
    for rel in coord["cross_domain_relationships"]:
        print("  -", rel[:WIDTH + 60])
    for c in entry["verifier"].get("conflict_details", []):
        print("CONFLICT        :", c["basis"])
        for label in ("finding_a", "finding_b"):
            side = c[label]
            print(f"  {label[-1].upper()}: [{side['agent_id']}, {side['chunk_id']}] {side['claim'][:WIDTH + 40]}")
        print("  Status        :", c["status"])
        print("  Treatment     :", c["coordinator_treatment"])
    if coord.get("open_questions"):
        print("Uncertainty     :", coord["open_questions"][0][:WIDTH + 80])


def live_registry():
    from src.rag.registry import build_registry
    return build_registry()


def registry_for(header: dict, stub: bool = False):
    """The knowledge bases a recorded run used: fixture, stub or live."""
    from src.scenario.conflict_fixture import FIXTURE_LABEL, conflict_registry
    if header.get("knowledge_base_note") == FIXTURE_LABEL:
        return conflict_registry()
    if stub or not all(header["knowledge_bases_live"].values()):
        return None
    return live_registry()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=DEFAULT_SCENARIO, choices=sorted(SCENARIOS))
    ap.add_argument("--stages", type=int, default=4, help="number of chunks to release")
    ap.add_argument("--stub", action="store_true", help="use stub knowledge bases")
    ap.add_argument("--conflict-demo", action="store_true",
                    help="run on the labelled FIXTURE KBs in which two agents disagree")
    ap.add_argument("--run-id", help="fixed run ID for the audit file name")
    ap.add_argument("--replay", type=Path, help="replay a recorded audit trail")
    ap.add_argument("--explain", action="store_true",
                    help="with --replay: answer, per stage, what happened, who acted, the "
                         "evidence, the conclusion, the verification and the Coordinator's path")
    ap.add_argument("--reexecute", action="store_true",
                    help="with --replay: re-run the recorded chunks and compare")
    ap.add_argument("--llm", choices=["offline", "ollama", "anthropic"],
                    help="agents' optional reasoning model (default: ADVISER_LLM, else offline)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)
    from src import llm
    provider = llm.configure(args.llm) if args.llm else llm.active()
    if getattr(provider, "notice", ""):
        print("NOTE:", provider.notice)
    elif not args.replay:
        ready, problem = provider.check()
        if not ready:
            print("WARNING:", problem)

    if args.replay:
        run = load_run(args.replay)
        registry = registry_for(run.header, args.stub)
        print(f"Run {run.header['run_id']} — {run.header['scenario_title']}")
        if run.header.get("knowledge_base_note"):
            print(f"NOTE: {run.header['knowledge_base_note']}")
        print("Hash chain:", "intact" if run.intact else "BROKEN")
        for problem in run.integrity_problems:
            print("  !", problem)
        for entry in run.stages:
            print_stage(entry)
            if args.explain:
                from src.audit.explain import explain_stage
                for question, lines in explain_stage(entry).items():
                    print(f"\n  {question}")
                    for line in lines:
                        print(f"    {line}")
        print_narrative(run.stages)
        if args.reexecute:
            diffs = reexecute(run, registry)
            print("=" * WIDTH)
            print("Re-execution:", "reproduced every stage" if not diffs else "DIFFERS")
            for d in diffs:
                print("  -", d)
            return 1 if diffs or not run.intact else 0
        return 0 if run.intact else 1

    if args.conflict_demo:
        from src.scenario.conflict_fixture import FIXTURE_LABEL, conflict_registry
        registry, note = conflict_registry(), FIXTURE_LABEL
        print("NOTE:", FIXTURE_LABEL)
    else:
        registry, note = (None if args.stub else live_registry()), None
    engine = ScenarioEngine(args.scenario, registry=registry, run_id=args.run_id,
                            registry_note=note)
    live = [k for k, v in engine.kb_status.items() if v]
    print(f"{engine.spec.title} (DOCX {engine.spec.docx_section})")
    print(f"Live KBs: {', '.join(live) or 'none — stub run'}")
    print(f"Agents' reasoning model: {provider.describe()}")
    for _ in range(min(args.stages, engine.stage_count)):
        print_stage(engine.next_stage())
    print_narrative(engine.stages)
    print("=" * WIDTH)
    print("Audit trail:", engine.audit_path)
    return 0


def print_narrative(stages: list[dict]) -> None:
    """Summary, notifications that may be due, and conclusion of the stages run."""
    import textwrap

    from src.audit.narrative import adviser_narrative
    story = adviser_narrative(stages)
    if not story["summary"]:
        return
    wrap = lambda text: textwrap.fill(text, WIDTH, initial_indent="  ", subsequent_indent="  ")  # noqa: E731
    print("=" * WIDTH)
    print("SUMMARY")
    print(wrap(story["summary"]))
    if story["notifications"]:
        print("\nNOTIFICATIONS THE RETRIEVED INDIAN PROVISIONS MAY REQUIRE (each subject to its condition "
              "and to confirmation)")
        for r in story["notifications"]:
            print(f"  - {'; '.join(r['limits'])} to {r['recipient']} — {r['source']}, {r['section']}")
            print(f"      applies: {r['condition']}")
    print("\nCONCLUSION")
    print(wrap(story["conclusion"]))


if __name__ == "__main__":
    sys.exit(main())
