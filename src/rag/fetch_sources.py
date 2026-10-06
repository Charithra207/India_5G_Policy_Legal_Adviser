"""
Download the source documents from their official URLs
======================================================
    python -m src.rag.fetch_sources            # into knowledge_base/sources/raw/
    python -m src.rag.fetch_sources --dest DIR # elsewhere (e.g. to test)

The source files are not in the repository: several (ITU, 3GPP, ETSI) state
that no part may be reproduced without permission, so the repository holds
the manifest instead.  This script fetches every ingested source from the
`source_url` recorded in knowledge_base/sources/manifest.json, unpacks the
3GPP archives, and checks each file against the SHA-256 recorded at
ingestion (knowledge_base/ingestion_manifest.json).

A file that already exists with the right hash is skipped.  A download that
fails, or whose hash differs (the publisher changed the file), is reported;
the build would then not reproduce the committed knowledge bases exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from src.rag.manifest import KB_ROOT, MANIFEST_PATH

SOURCES = KB_ROOT / "sources"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _curl(url: str) -> bytes:
    """Some government sites (meity.gov.in, niti.gov.in) refuse Python's HTTP client but
    serve curl, which ships with Windows 10+, macOS and Linux."""
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("download refused and curl is not available")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "file"
        subprocess.run([curl, "-sSfL", "--retry", "2", "-o", str(out), url],
                       check=True, capture_output=True, timeout=300)
        return out.read_bytes()


def _get(url: str, attempts: int = 3) -> bytes:
    parts = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(urllib.parse.unquote(parts.path))))
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (source fetch)"})
    for i in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=90, context=ssl.create_default_context()) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                return _curl(url)
            if i == attempts - 1:
                raise
        except Exception:  # noqa: BLE001 — retried, then raised
            if i == attempts - 1:
                raise
        time.sleep(3 * (i + 1))
    raise RuntimeError("unreachable")


def fetch(dest: Path) -> list[dict]:
    docs = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["documents"]
    expected = {d["id"]: d.get("sha256") for d in json.loads(
        (KB_ROOT / "ingestion_manifest.json").read_text(encoding="utf-8"))["documents"]}
    results = []
    for d in docs:
        if d.get("status") != "downloaded":
            continue
        target = dest / Path(d["file"]).relative_to("raw")
        want = expected.get(d["id"])
        row = {"id": d["id"], "file": str(target), "url": d["source_url"]}
        if target.exists() and _sha256(target) == want:
            results.append({**row, "result": "present"})
            continue
        try:
            data = _get(d["source_url"])
        except Exception as exc:  # noqa: BLE001
            results.append({**row, "result": f"FAILED: {type(exc).__name__}: {exc}"})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if d["source_url"].lower().endswith(".zip"):      # 3GPP: the .docx is inside the archive
            archive = target.parent.with_suffix(".zip")
            archive.write_bytes(data)
            with zipfile.ZipFile(archive) as z:
                member = next(n for n in z.namelist() if n.endswith(target.name))
                target.write_bytes(z.read(member))
        else:
            target.write_bytes(data)
        got = _sha256(target)
        results.append({**row, "result": "downloaded" if got == want else
                        "DOWNLOADED, BUT HASH DIFFERS (the publisher changed the file)"})
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", type=Path, default=SOURCES / "raw")
    args = ap.parse_args(argv)
    results = fetch(args.dest)
    for r in results:
        print(f"  {r['result'][:70]:<70} {r['id']}")
    bad = [r for r in results if r["result"] not in ("present", "downloaded")]
    print(f"{len(results) - len(bad)} of {len(results)} sources ready in {args.dest}")
    if bad:
        print("Not ready: " + ", ".join(r["id"] for r in bad) +
              " — retry later, or copy those files from a team member's knowledge_base/sources/raw/.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
