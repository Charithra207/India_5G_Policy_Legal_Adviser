"""Core pipeline package."""
from .models import (
    AgentID, VerifierOutcome, CoverageCategory,
    EvidenceItem, ScenarioChunk, AgentFinding,
    VerifiedClaim, VerifierResult, CoordinatorAssessment, AuditRecord,
)

# Pipeline components load lazily: the verifier imports the knowledge-base
# package, which imports these models, so an eager import here would make
# `import src.knowledge_base...` fail when it is the first import.
_LAZY = {
    "Verifier":          ".verifier",
    "Coordinator":       ".coordinator",
    "SwarmOrchestrator": ".orchestrator",
}


def __getattr__(name):
    if name in _LAZY:
        from importlib import import_module
        return getattr(import_module(_LAZY[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Data models
    "AgentID", "VerifierOutcome", "CoverageCategory",
    "EvidenceItem", "ScenarioChunk", "AgentFinding",
    "VerifiedClaim", "VerifierResult", "CoordinatorAssessment", "AuditRecord",
    # Pipeline components
    "Verifier", "Coordinator", "SwarmOrchestrator",
]
