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

### Re-check after adding the team's sources (same day)

Eight documents from the team folder were ingested, each traced to its
official URL. They include:
- the Telecommunications Act commencement notifications;
- the CTI Rules;
- the TCS Amendment Rules;
- NITI Aayog's AI strategy;
- the ENISA EU examples;
- the Right of Way Rules.

The KBs were rebuilt and both recordings re-recorded. The three rehearsals
were then repeated:

| | Rehearsal 1 | Rehearsal 2 | Rehearsal 3 |
|---|---|---|---|
| System time, all steps | 5.1 s | 3.4 s | 3.3 s |
| Exceptions / issues | 0 / 0 | 0 / 0 | 0 / 0 |
| Live run identical to the recorded run | yes | yes | yes |
| Fixture T1 VERIFIED, T2 conflict | yes | yes | yes |

All 22 statements in `DEMO_SCRIPT.md` were found in the new recordings.

One retrieval defect surfaced and was fixed. A 45-character heading
fragment from the AI strategy scored above the cut-off for "football world
cup final score". Passages under 80 characters are now excluded from open
searches.

The first rehearsal round changed no core logic. Adding the sources needed
one recorded fix: evidence now carries the in-force status established by a
notification, and the Verifier names it. That fix is logged with its reason
in `CORE_FREEZE.json`, and the freeze check passes.

## Final team check

**Results from this check, all re-run today:**
- `python -m pytest tests`: **392 passed**.
- `python -m src.rag.evidence_audit`: **0 problems**.
- `python -m src.core.freeze --check`: **unchanged**.

| Owner | Item | Evidence | Status |
|---|---|---|---|
| Member 1 | Core pipeline works | 4-stage live run matches the DOCX table at every stage; hardening tests (8 failure modes, 4 verifier outcomes, 5 Coordinator categories) pass | ✔ checked |
| Member 2 | Sources and evidence are valid | Evidence audit: 60 claims and 53 cited passages traced, 13 in-force statuses and 2 amendment notes traced to their notifications, 0 problems; every source in the manifest with an official URL and a matching file hash | ✔ checked |
| All | 4-stage scenario works | Three rehearsals identical to the recorded run | ✔ checked |
| All | Verification works | VERIFIED (fixture), INCOMPLETE and UNSUPPORTED (live), CONFLICT (fixture) all on screen | ✔ checked |
| All | Policy-gap classification works | Three potential gaps at T3 in DOCX categories, worded as potential and for expert review | ✔ checked |
| All | Audit and replay work | Hash chain intact; decision path; re-execution reproduces every stage | ✔ checked |

**Sign-off.** Each member confirms after watching one rehearsal:

- Member 1 (core): ____________
- Member 2 (knowledge base and evidence): ____________
- Member 3 (scenario, UI, audit): ____________
