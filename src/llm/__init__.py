"""
Optional LLM reasoning layer for the specialist agents.

    from src.llm import configure, active
    configure("ollama")          # or "anthropic", or "offline" (the default)

The setting is process-wide: every agent of every pipeline reads `active()`
when it analyses a chunk.  ADVISER_LLM sets the initial value.  With
"offline" (or nothing set) no model is called and runs are exactly
reproducible.  See src/llm/provider.py and src/llm/synthesis.py.
"""

from __future__ import annotations

from src.llm.provider import PROVIDERS, LLMProvider, make_provider

_ACTIVE: LLMProvider | None = None


def configure(name: str | None = None, provider: LLMProvider | None = None) -> LLMProvider:
    """Select the provider by name (or ADVISER_LLM), or install a ready provider."""
    global _ACTIVE
    _ACTIVE = provider if provider is not None else make_provider(name)
    return _ACTIVE


def active() -> LLMProvider:
    """The configured provider (configured from ADVISER_LLM on first use)."""
    return _ACTIVE if _ACTIVE is not None else configure()


__all__ = ["PROVIDERS", "LLMProvider", "active", "configure"]
