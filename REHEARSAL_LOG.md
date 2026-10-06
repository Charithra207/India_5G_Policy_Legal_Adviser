# Final rehearsal log and team check

## Rehearsals

The golden demo path was run three times through the real UI, using
Streamlit's AppTest against the live knowledge bases on the presentation
laptop (Windows 11, CPU only). Each rehearsal covered:

1. A live 4-stage run.
2. Replay of the full run.
3. Replay of the fixture run, for VERIFIED (T1) and the conflict (T2).

| | Rehearsal 1 (cold) | Rehearsal 2 | Rehearsal 3 |
|---|---|---|---|
| System time, all steps | 17.1 s | 8.5 s | 3.6 s |
| Slowest step | T3 9.9 s | T1 3.7 s | T3 1.2 s |
| Exceptions | 0 | 0 | 0 |
| Live run identical to the recorded run | yes | yes | yes |
| Replay opens on the full live run | yes | yes | yes |
| Decision path shown in replay | yes | yes | yes |
| Fixture T1 shows VERIFIED | 1 | 1 | 1 |
| Fixture T2 shows the conflict | yes | yes | yes |

**Spoken runtime:** about 9 minutes, following `DEMO_SCRIPT.md`; the
system's own time is under 20 seconds.

**Other checks:**
- Re-execute and compare: 2.5 s, no differences.
- With the network blocked, the full live run completed and matched the
  DOCX table at every stage.

### Findings and what was done

| Finding | Kind | Action |
|---|---|---|
| Missing evidence was listed three times (Verifier, Uncertainty, Coordinator) | Confusing screen | Kept once, in the Uncertainty section |
| Replay opened on the newest file, possibly the synthetic fixture run | Confusing screen | Replay now lists complete live runs first |
| The Day-1 recording appeared in Replay and re-executes as "differs" (recorded before the Day-2 core changes) | Confusing screen | Moved to `outputs/audit/archive/`, which the UI does not list |
| The KB list showed internal IDs (`critical_infrastructure`) | Confusing screen | Readable names |
| The CLI replay of the fixture run did not say it uses synthetic passages | Missing label | It now prints the fixture note |
| T3 takes about 10 s on a cold machine (exhaustive Policy Gap scan) | Slow step | Not changed (it is the exhaustive check); the script says to talk through it |
| First model load | Slow step | The script presses Start run before the audience arrives |
| Missing evidence | — | None: every cited passage traces to a stored passage (`knowledge_base/evidence_audit.md`, 0 problems) |
| Inconsistent outputs | — | None across the three rehearsals |

No core logic was changed today. `CORE_FREEZE.json` is unchanged and the
check passes.

## Final team check

**Results from this check, all re-run today:**
- `python -m pytest tests`: **386 passed**.
- `python -m src.rag.evidence_audit`: **0 problems**.
- `python -m src.core.freeze --check`: **unchanged**.

| Owner | Item | Evidence | Status |
|---|---|---|---|
| Member 1 | Core pipeline works | 4-stage live run matches the DOCX table at every stage; hardening tests (8 failure modes, 4 verifier outcomes, 5 Coordinator categories) pass | ✔ checked |
| Member 2 | Sources and evidence are valid | Evidence audit: 60 claims and 53 cited passages traced, 0 problems; every demo source in the manifest with a matching file hash | ✔ checked |
| All | 4-stage scenario works | Three rehearsals identical to the recorded run | ✔ checked |
| All | Verification works | VERIFIED (fixture), INCOMPLETE and UNSUPPORTED (live), CONFLICT (fixture) all on screen | ✔ checked |
| All | Policy-gap classification works | Three potential gaps at T3 in DOCX categories, worded as potential and for expert review | ✔ checked |
| All | Audit and replay work | Hash chain intact; decision path; re-execution reproduces every stage | ✔ checked |

**Sign-off.** Each member confirms after watching one rehearsal:

- Member 1 (core): ____________
- Member 2 (knowledge base and evidence): ____________
- Member 3 (scenario, UI, audit): ____________
