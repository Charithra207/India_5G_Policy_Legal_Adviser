"""
Command-line scenario runner and replay
=======================================
    python -m src.scenario.run --stages 2            # Day-1 test: T0 then T1
    python -m src.scenario.run                       # all four stages
    python -m src.scenario.run --replay outputs/audit/<run>.jsonl [--reexecute]

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
        print(f"    passages retrieved: {len(real)}")
        for p in real[:3]:
            print(f"      - {p['source_title']}, {p['section']}"
                  + (f" (p. {p['page']})" if p["page"] else ""))
        for c in agent["claims"]:
            print(f"    {c['verifier_outcome'] or 'NOT VERIFIED':<11} {c['claim'][:WIDTH + 20]}")
    counts = entry["verifier"]["outcome_counts"]
    print("\nVerifier        :", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print("Coordinator     :", "; ".join(
        f"{k.replace('_', ' ')} {len(coord[k])}" for k in (
            "confirmed_facts", "evidence_backed_conclusions", "uncertain_conclusions",
            "conflicting_findings", "potential_policy_gaps")))
    for change in coord["changes_from_prior"]:
        print("Changed         :", change)
    for rel in coord["cross_domain_relationships"]:
        print("Cross-domain    :", rel[:WIDTH + 40])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=DEFAULT_SCENARIO, choices=sorted(SCENARIOS))
    ap.add_argument("--stages", type=int, default=4, help="number of chunks to release")
    ap.add_argument("--stub", action="store_true", help="use stub knowledge bases")
    ap.add_argument("--run-id", help="fixed run ID for the audit file name")
    ap.add_argument("--replay", type=Path, help="replay a recorded audit trail")
    ap.add_argument("--reexecute", action="store_true",
                    help="with --replay: re-run the recorded chunks and compare")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)

    registry = None
    if not args.stub:
        from src.rag.registry import build_registry
        registry = build_registry()

    if args.replay:
        run = load_run(args.replay)
        print(f"Run {run.header['run_id']} — {run.header['scenario_title']}")
        print("Hash chain:", "intact" if run.intact else "BROKEN")
        for problem in run.integrity_problems:
            print("  !", problem)
        for entry in run.stages:
            print_stage(entry)
        if args.reexecute:
            diffs = reexecute(run, registry)
            print("=" * WIDTH)
            print("Re-execution:", "reproduced every stage" if not diffs else "DIFFERS")
            for d in diffs:
                print("  -", d)
            return 1 if diffs or not run.intact else 0
        return 0 if run.intact else 1

    engine = ScenarioEngine(args.scenario, registry=registry, run_id=args.run_id)
    live = [k for k, v in engine.kb_status.items() if v]
    print(f"{engine.spec.title} (DOCX {engine.spec.docx_section})")
    print(f"Live KBs: {', '.join(live) or 'none — stub run'}")
    for _ in range(min(args.stages, engine.stage_count)):
        print_stage(engine.next_stage())
    print("=" * WIDTH)
    print("Audit trail:", engine.audit_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
