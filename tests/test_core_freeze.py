"""
The core is frozen for the release candidate (see src/core/freeze.py).

If this fails, a frozen file changed.  If the change is a genuine bug fix,
record it:  python -m src.core.freeze --record "bug fix: <what and why>"
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.freeze import check


def test_frozen_core_is_unchanged() -> None:
    problems = check()
    assert not problems, "Frozen core changed:\n  " + "\n  ".join(problems)
