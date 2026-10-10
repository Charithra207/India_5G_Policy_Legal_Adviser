"""
LLM providers for the specialist agents (optional reasoning layer)
=================================================================
    ADVISER_LLM=offline     (default) no generative model; agents are deterministic
    ADVISER_LLM=ollama      a local open-weight model through Ollama (free, runs on a
                            laptop): OLLAMA_MODEL (default qwen2.5:7b-instruct),
                            OLLAMA_HOST (default http://localhost:11434)
    ADVISER_LLM=anthropic   Claude through the Anthropic API (ANTHROPIC_API_KEY);
                            model from ANTHROPIC_MODEL, default as in ir/llm.py

Each provider answers one request — a system prompt and one user message —
with text.  `complete` returns None when the model cannot answer (not
running, no key, refusal, error); the agent then keeps its deterministic
finding, so a run never fails because a model is unavailable.

The model never decides what counts as evidence: the agent only accepts
claims that cite passages it retrieved, and the Verifier checks those
against the Canonical KB (src/llm/synthesis.py).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    latency_ms: float
    usage: dict = field(default_factory=dict)


class LLMProvider:
    name = "base"
    model = ""

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> LLMResponse | None:
        raise NotImplementedError

    def describe(self) -> str:
        return f"{self.name}:{self.model}" if self.model else self.name

    def check(self) -> tuple[bool, str]:
        """(ready, problem) — whether the model can be reached before a run starts."""
        return True, ""


class OfflineLLM(LLMProvider):
    """No generative model: the agents stay fully deterministic and replayable."""
    name = "offline"

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> LLMResponse | None:
        return None


class OllamaLLM(LLMProvider):
    """A local open-weight model served by Ollama (https://ollama.com), JSON output, temperature 0."""
    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None, timeout: float = 120.0) -> None:
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout
        self.last_error = ""

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> LLMResponse | None:
        body = json.dumps({
            "model": self.model, "stream": False, "format": "json",
            "options": {"temperature": 0, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode("utf-8")
        request = urllib.request.Request(f"{self.host}/api/chat", data=body,
                                         headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.last_error = (self._missing_model() if exc.code == 404 else f"HTTP {exc.code} from Ollama: "
                               f"{exc.read().decode('utf-8', 'replace')[:200]}")
            return None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, urllib.error.URLError) and "refused" in str(exc).lower():
                self.last_error = f"Ollama is not running at {self.host} (start the Ollama app)"
            return None
        text = (data.get("message") or {}).get("content", "")
        if not text:
            self.last_error = "empty response"
            return None
        usage = {"input_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count")}
        return LLMResponse(text, self.name, self.model, round((time.perf_counter() - t0) * 1000, 1), usage)


    def _missing_model(self) -> str:
        return (f"model {self.model!r} is not installed in Ollama — run: ollama pull {self.model} "
                "(or set OLLAMA_MODEL to a name from `ollama list`)")

    def installed_models(self) -> list[str]:
        """Names Ollama reports in /api/tags (raises if Ollama cannot be reached)."""
        with urllib.request.urlopen(f"{self.host}/api/tags", timeout=5) as resp:
            return [m.get("name", "") for m in json.loads(resp.read().decode("utf-8")).get("models", [])]

    def check(self) -> tuple[bool, str]:
        """(ready, problem): is Ollama running, and is this model pulled?"""
        try:
            names = self.installed_models()
        except (urllib.error.URLError, OSError, ValueError):
            return False, (f"Ollama is not reachable at {self.host}: start the Ollama app. Until then the "
                           "agents run without a model (deterministic findings only).")
        wanted = {self.model, f"{self.model}:latest"} if ":" not in self.model else {self.model}
        if wanted & set(names):
            return True, ""
        return False, (self._missing_model() + ". Installed: " + (", ".join(names) or "none")
                       + ". Until then the agents run without a model (deterministic findings only).")


class AnthropicLLM(LLMProvider):
    """Claude through the Anthropic SDK, with the server-side refusal fallback ir/llm.py uses."""
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        import anthropic                                    # ImportError → caller falls back
        if model is None:
            from ir.llm import MODEL as model               # one model setting for the whole project
        self.model = model
        self.client = anthropic.Anthropic()
        self.last_error = ""

    def complete(self, system: str, user: str, max_tokens: int = 4000) -> LLMResponse | None:
        import anthropic
        t0 = time.perf_counter()
        try:
            response = self.client.beta.messages.create(
                model=self.model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": "low"},            # one bounded synthesis per agent
                betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"})
        except anthropic.APIStatusError as exc:
            self.last_error = f"API error {exc.status_code}: {exc.message}"
            return None
        except anthropic.APIConnectionError as exc:
            self.last_error = f"connection error: {exc}"
            return None
        if response.stop_reason == "refusal":
            self.last_error = "the model declined the request"
            return None
        text = "".join(b.text for b in response.content if b.type == "text")
        if not text:
            self.last_error = f"no text (stop_reason {response.stop_reason})"
            return None
        usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
        return LLMResponse(text, self.name, response.model, round((time.perf_counter() - t0) * 1000, 1), usage)


PROVIDERS = ("offline", "ollama", "anthropic")


def make_provider(name: str | None = None) -> LLMProvider:
    """
    The provider named (or ADVISER_LLM).  A provider that cannot be set up
    (SDK missing, no credential) becomes OfflineLLM, with a note in `.notice`.
    """
    name = (name or os.environ.get("ADVISER_LLM", "offline")).strip().lower()
    if name not in PROVIDERS:
        raise ValueError(f"unknown LLM provider {name!r}; choose one of {PROVIDERS}")
    if name == "ollama":
        return OllamaLLM()
    if name == "anthropic":
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            off = OfflineLLM()
            off.notice = "ADVISER_LLM=anthropic but no ANTHROPIC_API_KEY is set; agents run offline"
            return off
        try:
            return AnthropicLLM()
        except ImportError:
            off = OfflineLLM()
            off.notice = "anthropic SDK not installed; agents run offline"
            return off
    return OfflineLLM()
