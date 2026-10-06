"""
Evidence audit of the demonstration run
=======================================
    python -m src.rag.evidence_audit [--run outputs/audit/<run>.jsonl]

Traces every passage cited in a recorded run along

    source → authority → document → section → passage → retrieval → agent conclusion

and checks, for every claim and every assessment line:

  trace       the passage is in a KB the agent may search; its text, section,
              authority, jurisdiction and URL match the stored passage and the
              manifest; the quoted words are in the stored text
  legal       no uncited claim states a legal requirement; Indian passages are
              not labelled as references, international ones always are;
              effective/amendment status is carried as recorded (unchecked) and
              nothing unchecked is VERIFIED
  standards   no text presents ITU/3GPP/ETSI/NIST material as Indian law
  policy gap  gaps are phrased as potential, name what was examined, and never
              say the law does not exist or is inadequate
  manifest    every cited document is in the manifest, ingested, with the file
              on disk hashing to the recorded SHA-256

Writes knowledge_base/evidence_audit.json and .md, including one traced
evidence example per agent.  Exit code 1 if any problem is found.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.rag.manifest import ALL_KBS, KB_ROOT, MANIFEST_PATH

ROOT = KB_ROOT.parent
DEFAULT_RUN = ROOT / "outputs" / "audit" / "day2_scenario2_full_T0_T3.jsonl"
REFERENCE_LABEL = "[REFERENCE ONLY — not Indian law]"

# KBs each agent may draw passages from (DOCX §7.1: own KB; the Policy Gap
# Agent also reads the Canonical KB and the Standards KB, read-only)
ALLOWED_KBS = {
    "technical": {"technical"}, "policy_legal": {"policy_legal"},
    "cybersecurity": {"cybersecurity"}, "privacy": {"privacy"},
    "critical_infrastructure": {"critical_infrastructure"}, "standards": {"standards"},
    "policy_gap": {"policy_gap", "canonical", "standards"},
}

_LEGAL_REQUIREMENT = re.compile(
    r"\b(shall|must|is required to|are required to|obliged to|mandatory|within \d+ hours)\b", re.I)
# "[^.]" alone would stop at the dots of "TS 33.501": a dot followed by a
# digit is part of a document number, not the end of a sentence
_NOT_SENTENCE_END = r'(?:[^."]|\.(?=\d))'
_STANDARD_AS_LAW = re.compile(
    r"\b(3GPP|ETSI|NIST|ITU-T|Y\.3172)\b" + _NOT_SENTENCE_END + r"{0,80}\b(is|are|constitutes?)\b"
    + _NOT_SENTENCE_END + r"{0,30}\b(Indian law|binding in India|legally binding|mandatory in India)\b",
    re.I)
_FORBIDDEN_GAP = [
    re.compile(p, re.I) for p in (
        r"\b(Indian|the) law (has|contains|makes) no provision",
        r"\bno (Indian )?(law|provision) (exists|addresses|covers)",
        r"\b(law|provision|regulation) does not exist",
        r"\bthere is no (Indian )?law\b",
        r"\b(policy|framework|law|regulation) is inadequate",
    )]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _quote_in(claim: str) -> str | None:
    m = re.search(r'states: "(.*)"\s*$', claim, re.S)
    if not m:
        return None
    return _flat(m.group(1)).removesuffix("…").strip()


class Audit:
    def __init__(self, run_path: Path) -> None:
        from src.audit.replay import load_run
        self.run_path = run_path
        self.run = load_run(run_path)
        self.manifest = {d["id"]: d for d in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["documents"]}
        self.ingested = {d["id"]: d for d in json.loads(
            (KB_ROOT / "ingestion_manifest.json").read_text(encoding="utf-8"))["documents"]}
        self.stored: dict[str, dict] = {}
        self.kbs_of: dict[str, set[str]] = {}
        for kb in ALL_KBS:
            for line in (KB_ROOT / kb / "chunks.jsonl").open(encoding="utf-8"):
                r = json.loads(line)
                self.stored[r["chunk_id"]] = r
                self.kbs_of.setdefault(r["chunk_id"], set()).add(kb)
        self.problems: list[str] = []
        self.counts: Counter = Counter()

    def flag(self, where: str, problem: str) -> None:
        self.problems.append(f"{where}: {problem}")

    # ------------------------------------------------------------------

    def check_passage(self, where: str, agent_id: str, claim: str, cite: dict, recorded: dict | None,
                      outcome: str) -> None:
        self.counts["cited passages checked"] += 1
        chunk = self.stored.get(cite["chunk_id"])
        if chunk is None:
            return self.flag(where, f"cited chunk {cite['chunk_id']} is not in any built KB")
        doc = self.manifest.get(chunk["doc_id"])
        if doc is None or doc.get("status") != "downloaded":
            return self.flag(where, f"document {chunk['doc_id']} not an ingested manifest source")
        if not (self.kbs_of[cite["chunk_id"]] & ALLOWED_KBS[agent_id]):
            self.flag(where, f"{agent_id} cites a passage from {sorted(self.kbs_of[cite['chunk_id']])}, "
                             "outside the KBs it may search")
        if recorded is None:
            self.flag(where, f"cited chunk {cite['chunk_id']} is not among the passages the agent retrieved")
        elif _flat(recorded["excerpt"]) != _flat(chunk["excerpt"]):
            self.flag(where, f"recorded passage text differs from the stored passage {cite['chunk_id']}")
        for field in ("source_title", "section"):
            if cite[field] != chunk[field]:
                self.flag(where, f"{field} {cite[field]!r} != stored {chunk[field]!r}")
        if chunk["authority"] != doc["authority"] or chunk["jurisdiction"] != doc["jurisdiction"]:
            self.flag(where, "authority/jurisdiction differ from the manifest")
        if chunk["url"] != doc["source_url"]:
            self.flag(where, "URL differs from the manifest")
        quote = _quote_in(claim)
        if quote is not None and quote not in _flat(chunk["excerpt"]):
            self.flag(where, "quoted words are not in the stored passage")
        international = chunk["jurisdiction"].strip().lower() != "india"
        if claim.startswith(("Potential gap", "Coverage check", "Candidate area")):
            pass                                  # examination results, not quotations
        elif international and not claim.startswith(REFERENCE_LABEL) and not claim.startswith(
                f"Comparator — {REFERENCE_LABEL}"):
            self.flag(where, "international passage quoted without the reference-only label")
        elif not international and REFERENCE_LABEL in claim:
            self.flag(where, "Indian passage labelled as a reference")
        self.check_status(where, chunk, doc)
        if outcome == "VERIFIED":
            self.flag(where, "claim VERIFIED although in-force status and amendments are unchecked")

    def check_status(self, where: str, chunk: dict, doc: dict) -> None:
        """
        In-force status and amendment notes must trace to a manifest entry
        whose authorising document was ingested (the build has already
        checked the entry's quoted evidence in that document's text).
        No passage may claim a complete amendment check.
        """
        m = re.match(r"^(?:Section|Rule|Regulation)\s+(\d+[A-Z]?)\b", chunk["section"])
        unit = m.group(1) if m else None

        def covers(entry: dict) -> bool:
            return ("*" in entry["units"] and not chunk["section"].startswith("p. ")) or unit in entry["units"]

        if chunk["effective"] is not None:
            backing = [e for e in doc.get("in_force", []) if covers(e)
                       and self.ingested.get(e["by"], {}).get("status") == "ingested"]
            if not backing or chunk["effective"] is not True:
                self.flag(where, f"in-force status of {chunk['chunk_id']} is not established by an obtained document")
            elif chunk["effective_status"] not in {e["status"] for e in backing}:
                self.flag(where, "in-force status text differs from the establishing entry")
            else:
                self.counts["in-force statuses traced to a notification"] += 1
        if chunk["amendment_note"]:
            if not any(covers(e) and self.ingested.get(e["by"], {}).get("status") == "ingested"
                       for e in doc.get("amended_by", [])):
                self.flag(where, f"amendment note on {chunk['chunk_id']} is not backed by an obtained amendment")
            else:
                self.counts["amendment notes traced to an amendment"] += 1
        if chunk["amendment_checked"]:
            self.flag(where, "passage claims a complete amendment check")

    def check_stage(self, stage: dict) -> None:
        label = stage["stage"]["label"]
        texts: list[tuple[str, str]] = []
        for agent in stage["agents"]:
            aid = agent["agent_id"]
            retrieved = {p["chunk_id"]: p for p in agent["retrieved_passages"]}
            for i, claim in enumerate(agent["claims"], 1):
                where = f"{label} {aid} claim {i}"
                self.counts["claims checked"] += 1
                texts.append((where, claim["claim"]))
                if claim["citations"]:
                    for cite in claim["citations"]:
                        recorded = retrieved.get(cite["chunk_id"])
                        if recorded is None and aid == "policy_gap":
                            recorded = self.stored.get(cite["chunk_id"])   # Canonical KB examination
                        self.check_passage(where, aid, claim["claim"], cite, recorded,
                                           claim["verifier_outcome"])
                elif (_LEGAL_REQUIREMENT.search(claim["claim"]) and "not assessed" not in claim["claim"]
                      and not claim["claim"].startswith(("Potential gap", "Coverage check", "Candidate area"))):
                    self.flag(where, f"uncited claim states a requirement: {claim['claim'][:120]}")
                if aid == "policy_gap" and claim["claim"].startswith("Potential gap"):
                    self.counts["potential gaps checked"] += 1
                    if "for expert review" not in claim["claim"]:
                        self.flag(where, "potential gap lacks the non-conclusive disclaimer")
                    if "examined" not in claim["claim"] and not claim["citations"]:
                        self.flag(where, "potential gap names neither examined instruments nor passages")
        coord = stage["coordinator"]
        for key in ("evidence_backed_conclusions", "uncertain_conclusions", "conflicting_findings",
                    "potential_policy_gaps", "cross_domain_relationships", "changes_from_prior"):
            texts += [(f"{label} coordinator {key}", t) for t in coord[key]]
        for where, text in texts:
            if _STANDARD_AS_LAW.search(text.replace(REFERENCE_LABEL, "")):
                self.flag(where, "presents an international standard as Indian law")
            for pattern in _FORBIDDEN_GAP:
                if pattern.search(text):
                    self.flag(where, f"unsupported absence/inadequacy claim: {pattern.pattern}")

    def check_manifest(self, cited_docs: set[str]) -> list[dict]:
        rows = []
        stored_docs = {r["doc_id"] for r in self.stored.values()}
        for doc_id in sorted(stored_docs - set(self.manifest)):
            self.flag("manifest", f"{doc_id} is in a KB but not in the manifest")
        for doc_id, doc in self.manifest.items():
            ing = self.ingested.get(doc_id, {})
            if doc.get("status") != "downloaded":
                rows.append({"id": doc_id, "title": doc["title"], "status": ing.get("status", doc["status"]),
                             "used_in_demo": False})
                continue
            path = KB_ROOT / "sources" / doc["file"]
            file_ok = path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == ing.get("sha256")
            if path.exists() and not file_ok:
                self.flag("manifest", f"{doc_id}: file on disk does not hash to the recorded SHA-256")
            if not doc.get("source_url", "").startswith("https://"):
                self.flag("manifest", f"{doc_id}: no https source URL")
            rows.append({"id": doc_id, "title": doc["title"], "authority": doc["authority"],
                         "jurisdiction": doc["jurisdiction"], "document_type": doc["document_type"],
                         "url": doc["source_url"], "status": ing.get("status"),
                         "chunks": ing.get("chunks"), "sha256_matches_file": file_ok if path.exists() else None,
                         "used_in_demo": doc_id in cited_docs})
        for doc_id in cited_docs - set(self.manifest):
            self.flag("manifest", f"{doc_id} is cited in the demo but missing from the manifest")
        return rows

    # ------------------------------------------------------------------

    # Example selection rule (stated, not hand-picked):
    #   Indian-law agents — the highest-ranked quoted Indian passage that
    #     imposes a duty ("shall"), else their highest-ranked quote;
    #   Technical / Standards — their highest-ranked quote;
    #   Policy Gap — its first potential gap that cites passages (an
    #     examination of the Canonical KB, not a retrieval query).
    _INDIAN_LAW_AGENTS = {"policy_legal", "cybersecurity", "privacy", "critical_infrastructure"}

    def _pick(self, agent_id: str):
        candidates = []
        for stage in self.run.stages:
            for agent in stage["agents"]:
                if agent["agent_id"] != agent_id:
                    continue
                rank = {p["chunk_id"]: i for i, p in enumerate(agent["retrieved_passages"])}
                for claim in agent["claims"]:
                    if not claim["citations"]:
                        continue
                    if agent_id == "policy_gap":
                        if claim["claim"].startswith("Potential gap"):
                            return stage, agent, claim
                        continue
                    if _quote_in(claim["claim"]) is None:
                        continue
                    chunk = self.stored[claim["citations"][0]["chunk_id"]]
                    duty = (chunk["jurisdiction"] == "India" and " shall" in chunk["excerpt"].lower())
                    preferred = duty if agent_id in self._INDIAN_LAW_AGENTS else True
                    candidates.append((not preferred, stage["seq"],
                                       rank.get(chunk["chunk_id"], 99), stage, agent, claim))
        if not candidates:
            return None
        best = min(candidates, key=lambda c: c[:3])
        return best[3], best[4], best[5]

    def examples(self) -> list[dict]:
        """One traced example per agent, chosen by the stated rule."""
        from src.rag.registry import build_registry
        registry = build_registry()
        out = []
        for agent_id in ALLOWED_KBS:
            found = self._pick(agent_id)
            if not found:
                out.append({"agent": agent_id, "example": None,
                            "note": "no cited passage in the recorded run"})
                continue
            stage, agent, claim = found
            cite = claim["citations"][0]
            chunk = self.stored[cite["chunk_id"]]
            question, score = None, None
            if agent_id == "policy_gap":
                question = ("Examination of the Canonical KB for the candidate area "
                            "(not a retrieval query)")
            else:
                kb = next(k for k in registry.agent_kbs if k.value == agent_id)
                for q in agent["queries"]:
                    for hit in registry.agent_kbs[kb].retrieve(q, top_k=5):
                        if hit.chunk_id == cite["chunk_id"]:
                            question, score = q, hit.relevance_score
                            break
                    if question:
                        break
            out.append({
                "agent": agent_id,
                "stage": stage["stage"]["label"],
                "question": question,
                "retrieval_cosine_similarity": score,
                "source": chunk["source_title"],
                "authority": chunk["authority"],
                "jurisdiction": chunk["jurisdiction"],
                "section": chunk["section"],
                "section_title": chunk["section_title"],
                "page": chunk["page"],
                "url": chunk["url"],
                "chunk_id": chunk["chunk_id"],
                "other_cited_passages": [f"{c['source_title']}, {c['section']}" for c in claim["citations"][1:]],
                "retrieved_evidence": _flat(chunk["excerpt"])[:600],
                "conclusion": claim["claim"],
                "verification_status": claim["verifier_outcome"],
                "verification_rationale": claim["verifier_rationale"],
                "cross_domain_note": claim["cross_domain_note"] or None,
            })
        return out

    def run_all(self) -> dict:
        if not self.run.intact:
            self.flag("run", f"audit hash chain broken: {self.run.integrity_problems}")
        cited_docs = set()
        for stage in self.run.stages:
            self.check_stage(stage)
            for agent in stage["agents"]:
                for claim in agent["claims"]:
                    cited_docs |= {c["chunk_id"].split(":")[0] for c in claim["citations"]}
        sources = self.check_manifest(cited_docs)
        return {
            "_about": "Evidence audit of a recorded demonstration run. Generated by "
                      "`python -m src.rag.evidence_audit`.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run": self.run_path.relative_to(ROOT).as_posix(),
            "checks": dict(self.counts),
            "problems": self.problems,
            "sources": sources,
            "sources_used_in_demo": sorted(cited_docs),
            "agent_examples": self.examples(),
        }


def write(report: dict) -> None:
    (KB_ROOT / "evidence_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                 encoding="utf-8")
    c = report["checks"]
    lines = [
        "# Evidence audit", "",
        f"Run audited: `{report['run']}`. Generated {report['generated_at'][:19]} UTC by "
        "`python -m src.rag.evidence_audit`.", "",
        f"**Checked:** {c.get('claims checked', 0)} claims, {c.get('cited passages checked', 0)} cited "
        f"passages, {c.get('potential gaps checked', 0)} potential gaps, every Coordinator line, and "
        f"{len(report['sources'])} manifest sources.", "",
        f"**Problems found:** {len(report['problems'])}", "",
    ]
    lines += [f"- {p}" for p in report["problems"]]
    lines += ["", "## Sources used in the demonstration", "",
              "| Document | Authority | Jurisdiction | Type | Chunks | File hash matches | URL |",
              "|---|---|---|---|---|---|---|"]
    for s in report["sources"]:
        if s["used_in_demo"]:
            lines.append(f"| {s['title']} | {s['authority']} | {s['jurisdiction']} | {s['document_type']} | "
                         f"{s['chunks']} | {s['sha256_matches_file']} | {s['url']} |")
    unused = [s for s in report["sources"] if not s["used_in_demo"]]
    lines += ["", "Not cited in the demonstration run: " + "; ".join(
        f"{s['title']} ({s['status']})" for s in unused), "",
        "## One traced evidence example per agent", "",
        "Selection rule: for the Indian-law agents, the highest-ranked quoted Indian passage that "
        "imposes a duty; for Technical and Standards, the highest-ranked quote; for Policy Gap, its "
        "first potential gap that cites passages.", ""]
    for e in report["agent_examples"]:
        if not e.get("source"):
            lines += [f"### {e['agent']}", "", e.get("note", ""), ""]
            continue
        lines += [
            f"### {e['agent']} ({e['stage']})", "",
            f"- **Question (agent query):** {e['question']}",
            f"- **Source:** {e['source']} — {e['authority']} ({e['jurisdiction']})",
            f"- **Section:** {e['section']}" + (f" — {e['section_title']}" if e["section_title"] else "")
            + (f", p. {e['page']}" if e["page"] else ""),
            f"- **Retrieved evidence:** \"{e['retrieved_evidence'][:400]}…\"",
            f"- **Conclusion:** {e['conclusion'][:400]}",
            f"- **Verification status:** {e['verification_status']} — {e['verification_rationale']}",
            f"- **Trace:** `{e['chunk_id']}`"
            + (f" · cosine {e['retrieval_cosine_similarity']}" if e["retrieval_cosine_similarity"] else "")
            + f" · {e['url']}"
            + (f" · also cites: {'; '.join(e['other_cited_passages'])}" if e["other_cited_passages"] else ""),
            "",
        ]
    (KB_ROOT / "evidence_audit.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, default=DEFAULT_RUN)
    args = ap.parse_args(argv)
    report = Audit(args.run).run_all()
    write(report)
    print(f"checked: {report['checks']}")
    print(f"problems: {len(report['problems'])}")
    for p in report["problems"]:
        print("  -", p)
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
