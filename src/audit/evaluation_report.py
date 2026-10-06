"""
Internal evaluation summary (DOCX §6 evaluation areas)
======================================================
    python -m src.audit.evaluation_report

Runs the whole test suite, reads every test's real result (JUnit XML), maps
tests to the DOCX evaluation areas, adds what the recorded live run shows,
and writes knowledge_base/evaluation_report.md and .json.

Status rules
------------
* A status is never inferred from a test's existence: if any test mapped to
  an area fails or errors, the area is "Not working" whatever its rating.
* "Working" — the capability runs end to end on the live corpus and its tests
  pass.
* "Partially working" — it runs, but part of what the DOCX describes is
  missing (a source not obtained, a check not done, a path shown only with
  labelled fixtures).
* "Not yet implemented" — the DOCX describes it and the code does not do it.
Each rating states its reason; the counts come from the test run and the
recorded run, never typed in.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_MD = ROOT / "knowledge_base" / "evaluation_report.md"
OUT_JSON = ROOT / "knowledge_base" / "evaluation_report.json"
RUN = ROOT / "outputs" / "audit" / "day2_scenario2_full_T0_T3.jsonl"
CONFLICT_RUN = ROOT / "outputs" / "audit" / "day2_conflict_demo_FIXTURE.jsonl"

W, P, N = "Working", "Partially working", "Not yet implemented"

# (area, status, reason, test selectors "module[::Class]")
AREAS = [
    ("Technical analysis", W,
     "T0 classifies the symptom and quotes 3GPP TS 23.501 clauses from the Technical KB.",
     ["test_evaluation::TestTechnicalAnalysis"]),
    ("Legal / regulatory analysis", W,
     "Telecommunications Act, TRAI Act and NDCP-2018 provisions retrieved and quoted; duty "
     "passages recorded as obligations.",
     ["test_evaluation::TestLegalRegulatoryAnalysis"]),
    ("Cybersecurity analysis", W,
     "T1 reclassifies as a possible security event; TCS Rules Rule 7 and CERT-In Direction (ii) quoted.",
     ["test_evaluation::TestCybersecurityAnalysis"]),
    ("Privacy / data protection analysis", W,
     "Suspected (not confirmed) exposure kept distinct; DPDP Act and DPDP Rules Rules 6–7 quoted.",
     ["test_evaluation::TestPrivacyAnalysis"]),
    ("Critical infrastructure analysis", P,
     "Critical-service relevance assessed from the Telecommunications Act only: the IT (NCIIPC) "
     "Rules, 2013 could not be obtained, so NCIIPC provisions cannot be quoted or verified.",
     ["test_evaluation::TestCriticalInfrastructureAnalysis"]),
    ("International standards (reference only)", W,
     "3GPP, ETSI, NIST and ITU passages quoted with the reference-only label; never treated as Indian law.",
     ["test_evaluation::TestInternationalStandards"]),
    ("Policy-gap identification", P,
     "Three of the six DOCX categories are examined (overlapping requirements, institutional "
     "clarity, emerging technology); explicit/partial coverage are left to expert review, "
     "unclear coverage is not produced, and no international policy examples were ingested.",
     ["test_evaluation::TestPolicyGapIdentification"]),
    ("Verification", P,
     "All four outcomes are produced by the real Verifier, but on the live corpus nothing can be "
     "VERIFIED (in-force status and amendments were not checked for any source) and no real "
     "provisions conflict; VERIFIED and CONFLICT are shown with labelled fixtures.",
     ["test_evaluation::TestVerification", "test_verification_evidence"]),
    ("Cross-domain reasoning", W,
     "Links established from evidence on the live run (shared provision, instrument basis, "
     "parallel reporting), including across chunks.",
     ["test_evaluation::TestCrossDomainReasoning", "test_cross_domain"]),
    ("Uncertainty handling", W,
     "Insufficient evidence stated explicitly; open questions and missing facts listed; human-review notice always present.",
     ["test_evaluation::TestUncertaintyHandling"]),
    ("Progressive reassessment", W,
     "Each chunk re-issues the whole assessment: facts accumulate, earlier conclusions carried "
     "forward and tagged, changes computed by comparison.",
     ["test_evaluation::TestProgressiveReassessment"]),
    ("Role separation", W,
     "Each agent searches only its own KB and fills only its mandate's fields; results never "
     "come from another agent's KB.",
     ["test_evaluation::TestRoleSeparation"]),
    ("Auditability", W,
     "Append-only, hash-chained audit trail with the §7.6 fields; replay with integrity check, "
     "decision-path explanation and re-execution.",
     ["test_evaluation::TestAuditability", "test_scenario_audit", "test_demo_integration::TestAuditAndReplay"]),
]

OTHER = [
    ("Full 4-stage demo (live KBs)", W, "All four stages run end to end; agent sets match the DOCX table.",
     ["test_demo_integration::TestFullFourStageDemo"]),
    ("Demonstration UI", W, "Live 4-stage run, replay and conflict display driven by tests through Streamlit's AppTest; every required section checked.",
     ["test_scenario_audit::test_ui_updates_between_chunk_one_and_two",
      "test_scenario_audit::test_ui_full_demo_shows_every_required_element",
      "test_scenario_audit::test_ui_replay_shows_conflict_side_by_side"]),
    ("Knowledge foundation / RAG", P,
     "15 sources ingested and every artefact checked against the stores; NCIIPC Rules, IndiaAI/"
     "national AI strategy, international examples and six host-country categories not obtained.",
     ["test_rag", "test_kb_foundation", "test_foundation"]),
    ("Team integration (Members 1–3)", W, "One pipeline from scenario to audit; checklist tests pass.",
     ["test_demo_integration::TestIntegrationChecklist", "test_pipeline"]),
    ("In-force / amendment checking", N,
     "Not done for any source; this is what blocks VERIFIED on the real corpus.", []),
    ("Generative synthesis (DOCX §5.2 generative-AI perspective)", N,
     "No generative model is used: agents quote passages and the Coordinator organises verified claims.", []),
    ("Parallel agent execution", N,
     "Agents run sequentially; the asynchronous runner in the Orchestrator is a stub.", []),
    ("ITU AI for Good Sandbox stage", N, "Sandbox not available in this environment.", []),
]


def run_tests() -> dict[str, list[dict]]:
    """Every test's result, keyed by module (e.g. 'test_evaluation')."""
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "results.xml"
        subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
                        f"--junitxml={xml_path}"], cwd=ROOT, capture_output=True, text=True)
        tree = ET.parse(xml_path)
    results: dict[str, list[dict]] = {}
    for case in tree.iter("testcase"):
        classname = case.get("classname", "")           # tests.test_x.TestY  or tests.test_x
        parts = classname.split(".")
        module = next((p for p in parts if p.startswith("test_")), classname)
        cls = parts[-1] if parts[-1] != module else ""
        outcome = ("failed" if case.find("failure") is not None or case.find("error") is not None
                   else "skipped" if case.find("skipped") is not None else "passed")
        results.setdefault(module, []).append({"class": cls, "name": case.get("name"), "outcome": outcome})
    return results


def select(results: dict, selectors: list[str]) -> Counter:
    counts: Counter = Counter()
    for sel in selectors:
        module, _, rest = sel.partition("::")
        for t in results.get(module, []):
            if not rest or t["class"] == rest or t["name"] == rest:
                counts[t["outcome"]] += 1
    return counts


def run_facts() -> dict:
    def stages(path):
        return [json.loads(l) for l in path.open(encoding="utf-8") if '"type": "stage"' in l]
    live, fixture = stages(RUN), stages(CONFLICT_RUN)
    outcomes = Counter()
    for s in live:
        outcomes.update(s["verifier"]["outcome_counts"])
    links = Counter(l["kind"] for s in live for l in s["verifier"].get("cross_domain_details", []))
    return {
        "live_run": RUN.relative_to(ROOT).as_posix(),
        "stages": [f"{s['stage']['label']}: {', '.join(s['orchestrator']['active_agents'])}" for s in live],
        "agent_sets_match_docx": all(s["orchestrator"]["matches_docx_table"] for s in live),
        "verifier_outcomes_live": dict(outcomes),
        "cross_domain_links_live": dict(links),
        "conflicts_live": sum(len(s["verifier"].get("conflict_details", [])) for s in live),
        "potential_policy_gaps_final": len(live[-1]["coordinator"]["potential_policy_gaps"]),
        "conflicts_fixture_demo": sum(len(s["verifier"].get("conflict_details", [])) for s in fixture),
        "fixture_run": CONFLICT_RUN.relative_to(ROOT).as_posix(),
    }


def build() -> dict:
    results = run_tests()
    total = Counter(t["outcome"] for ts in results.values() for t in ts)
    negative = {cls: Counter(t["outcome"] for t in results.get("test_negative", []) if t["class"] == cls)
                for cls in ("TestUnsupported", "TestIncomplete", "TestConflict", "TestVerified")}

    def rows(table):
        out = []
        for name, status, reason, selectors in table:
            counts = select(results, selectors)
            if counts.get("failed"):
                status, reason = "Not working", f"{counts['failed']} mapped test(s) fail. " + reason
            out.append({"capability": name, "status": status, "reason": reason,
                        "tests": selectors, "passed": counts.get("passed", 0),
                        "failed": counts.get("failed", 0), "skipped": counts.get("skipped", 0)})
        return out

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "python -m src.audit.evaluation_report",
        "test_totals": dict(total),
        "evaluation_areas": rows(AREAS),
        "other_capabilities": rows(OTHER),
        "negative_tests": {
            "A. Unsupported citation → UNSUPPORTED": dict(negative["TestUnsupported"]),
            "B. Missing/incomplete source information → INCOMPLETE": dict(negative["TestIncomplete"]),
            "C. Conflicting findings → CONFLICT": dict(negative["TestConflict"]),
            "D. Valid evidence-backed claim → VERIFIED": dict(negative["TestVerified"]),
        },
        "recorded_runs": run_facts(),
    }


def write(report: dict) -> None:
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    t, f = report["test_totals"], report["recorded_runs"]
    lines = [
        "# Evaluation summary (internal)", "",
        f"Generated {report['generated_at'][:19]} UTC by `{report['generated_by']}` — "
        "statuses follow the rules in that module; counts are from the test run and the recorded runs.", "",
        f"**Test suite:** {t.get('passed', 0)} passed, {t.get('failed', 0)} failed, "
        f"{t.get('skipped', 0)} skipped.", "",
        f"**Live 4-stage run** (`{f['live_run']}`): " + "; ".join(f["stages"])
        + f". Agent sets match the DOCX table: {'yes' if f['agent_sets_match_docx'] else 'NO'}. "
        "Verifier outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(f["verifier_outcomes_live"].items()))
        + ". Cross-domain links: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(f["cross_domain_links_live"].items()))
        + f". Conflicts: {f['conflicts_live']} (none expected — no real provisions disagree). "
        f"Potential policy gaps at T3: {f['potential_policy_gaps_final']}. "
        f"Conflict demonstration on labelled fixtures (`{f['fixture_run']}`): {f['conflicts_fixture_demo']} conflict records.",
        "",
    ]
    for title, key in (("DOCX evaluation areas", "evaluation_areas"), ("Other capabilities", "other_capabilities")):
        lines += [f"## {title}", "", "| Capability | Status | Tests (pass/fail) | Why |", "|---|---|---|---|"]
        for r in report[key]:
            tests = f"{r['passed']}/{r['failed']}" if r["tests"] else "—"
            lines.append(f"| {r['capability']} | {r['status']} | {tests} | {r['reason']} |")
        lines.append("")
    lines += ["## Negative tests", "", "| Case | Passed | Failed |", "|---|---|---|"]
    for case, c in report["negative_tests"].items():
        lines.append(f"| {case} | {c.get('passed', 0)} | {c.get('failed', 0)} |")
    lines += ["", "VERIFIED and CONFLICT are reached through the real Verifier with labelled fixture "
              "passages; on the live corpus neither occurs, for the reasons given above.", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    report = build()
    write(report)
    t = report["test_totals"]
    print(f"tests: {t}")
    for r in report["evaluation_areas"] + report["other_capabilities"]:
        print(f"  {r['status']:<22} {r['capability']}")
    return 0 if not t.get("failed") else 1


if __name__ == "__main__":
    sys.exit(main())
