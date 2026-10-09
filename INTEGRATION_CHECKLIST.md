# Integration checklist — running the whole project

Members 1–3 in one flow: **Scenario → Chunk → Orchestrator → Specialist agents
→ Agent-specific RAG → Evidence → Cross-domain verification → Verifier →
Coordinator → Assessment → Audit → Replay**.

Run from the repository root (Python 3.12). Each step lists what a correct
run shows.

| # | Step | Command | Expected |
|---|---|---|---|
| 1 | Install | `pip install -r requirements.txt` | Installs PyMuPDF, python-docx, numpy, fastembed, Streamlit, pytest |
| 2 | Sources | `python -m src.rag.fetch_sources` | Downloads all 23 sources from their official URLs into `knowledge_base/sources/raw/` and checks each SHA-256: "23 of 23 sources ready" (needs internet; uses curl where a site refuses Python's client) |
| 3 | Build the KBs (Member 2) | `python -m src.rag.build` | 8 stores; Canonical KB holds all 23 documents; in-force and amendment status applied from the notifications; `ingestion_manifest.json` rewritten |
| 4 | Retrieval checks | `python -m src.rag.retrieval_demo` and `python -m src.rag.retrieval_quality` | 7/7 agents retrieve evidence; labelled queries isolated to each agent's KB |
| 5 | Full 4-stage run (Members 1+3) | `python -m src.scenario.run --run-id <id>` | T0 Technical; T1 +Cybersecurity, Standards; T2 Critical Infrastructure, Privacy, Policy & Legal; T3 + Policy Gap — each "→ match" with the DOCX table; written to `outputs/audit/<id>.jsonl` |
| 6 | Replay | `python -m src.scenario.run --replay outputs/audit/<id>.jsonl --explain --reexecute` | Hash chain intact; per-stage decision path; "reproduced every stage" |
| 7 | Conflict handling | `python -m src.scenario.run --conflict-demo` | Labelled FIXTURE run; reporting-deadline conflict at T2 and T3 with Finding A / Finding B |
| 8 | Foundation artefacts (Member 2) | `python -m src.rag.foundation --run outputs/audit/<id>.jsonl` | Six artefacts regenerated; fails if any quote is not in the stores |
| 9 | UI (Member 3) | `streamlit run src/ui/app.py` | Live run (release chunks one by one) and Replay (pick a run, step through, decision path, re-execute) |
| 10 | Tests | `python -m pytest tests -q` | All pass; live-KB tests skip only if step 3 was not done |
| 11 | Evaluation summary | `python -m src.audit.evaluation_report` | `knowledge_base/evaluation_report.md` from a real test run |

Recorded reference runs in the repository:

- `outputs/audit/day2_scenario2_full_T0_T3.jsonl` — live KBs, all four stages
- `outputs/audit/day2_conflict_demo_FIXTURE.jsonl` — labelled synthetic passages, conflict demonstration
- `outputs/audit/archive/day1_scenario2_T0_T1.jsonl` — Day-1 run, archived (recorded before the Day-2 core changes, so re-execution differs; its hash chain is intact). Archived runs are not listed in the UI.

Known limits (see `knowledge_base/evaluation_report.md`): nothing can be
VERIFIED until in-force and amendment status are checked; NCIIPC Rules and
neighbouring-country instruments are not ingested; no generative model by default
(optional Ollama/Claude reasoning per agent via `--llm`, verified and audited); agents run
sequentially; the ITU AI for Good Sandbox was not available, so everything runs
locally; the Y.3172 ML pipeline (`src/y3172/`) runs over the contained
simulator, not a live network, with logical reference points and levels.
