"""LLM backends.

Groq, OpenAI, Google Gemini and Ollama all expose an OpenAI-compatible chat API,
so ONE class (using the official `openai` SDK) covers every provider; only the
base URL, key and default model differ.

    DATATIDY_PROVIDER=groq   GROQ_API_KEY=...      (free tier, rate limited)
    DATATIDY_PROVIDER=ollama                       (local, free, no key)
    DATATIDY_PROVIDER=openai OPENAI_API_KEY=...    (paid, prepaid credits)
    DATATIDY_PROVIDER=gemini GEMINI_API_KEY=...    (free tier, rate limited)

Model names change often: override with --model or DATATIDY_MODEL.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0


class LLMBackend(Protocol):
    name: str

    def complete(self, system: str, user: str) -> LLMResponse: ...


PROVIDERS = {
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY",
             "model": "openai/gpt-oss-120b"},
    "openai": {"base_url": None, "key_env": "OPENAI_API_KEY", "model": "gpt-4o-mini"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "key_env": "GEMINI_API_KEY", "model": "gemini-2.5-flash"},
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": None, "model": "llama3.2"},
}


def load_env(path: str | Path = ".env") -> None:
    """Tiny .env loader (KEY=value lines). Never overrides real environment variables."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class OpenAICompatibleBackend:
    def __init__(self, provider: str = "groq", model: str | None = None,
                 api_key: str | None = None, base_url: str | None = None,
                 temperature: float = 0.0, timeout: float = 60.0, json_mode: bool = True):
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider '{provider}'. Choose from {sorted(PROVIDERS)}.")
        cfg = PROVIDERS[provider]
        key_env = cfg["key_env"]
        key = api_key or (os.environ.get(key_env) if key_env else "ollama")
        if not key:
            raise RuntimeError(
                f"No API key for '{provider}'. Set {key_env} in your environment or .env file "
                f"(see .env.example).")
        from openai import OpenAI          # imported lazily so tests/CLI work without a key
        self.provider = provider
        self.name = f"{provider}:{model or os.environ.get('DATATIDY_MODEL') or cfg['model']}"
        self.model = model or os.environ.get("DATATIDY_MODEL") or cfg["model"]
        self.temperature = temperature
        self.json_mode = json_mode
        self.client = OpenAI(api_key=key, base_url=base_url or cfg["base_url"],
                             timeout=timeout, max_retries=3)

    def complete(self, system: str, user: str) -> LLMResponse:
        from openai import BadRequestError
        kwargs = dict(model=self.model, temperature=self.temperature,
                      messages=[{"role": "system", "content": system},
                                {"role": "user", "content": user}])
        t0 = time.time()
        try:
            if self.json_mode:
                resp = self.client.chat.completions.create(
                    response_format={"type": "json_object"}, **kwargs)
            else:
                resp = self.client.chat.completions.create(**kwargs)
        except BadRequestError:
            if not self.json_mode:
                raise
            resp = self.client.chat.completions.create(**kwargs)   # model lacks JSON mode
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_s=round(time.time() - t0, 3),
        )


class FakeBackend:
    """Returns canned responses in order. For tests and offline demos."""

    def __init__(self, responses: list[str]):
        self.name = "fake"
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> LLMResponse:
        self.calls.append((system, user))
        if not self._responses:
            raise RuntimeError("FakeBackend ran out of responses.")
        return LLMResponse(text=self._responses.pop(0), prompt_tokens=10, completion_tokens=10)


def get_backend(provider: str | None = None, model: str | None = None) -> OpenAICompatibleBackend:
    load_env()
    provider = provider or os.environ.get("DATATIDY_PROVIDER", "groq")
    return OpenAICompatibleBackend(provider=provider, model=model)
