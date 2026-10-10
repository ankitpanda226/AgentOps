"""LLM abstraction layer with deterministic local fallback."""

from __future__ import annotations

import os
from typing import Protocol


class BaseLLM(Protocol):
    """Interface for language model clients."""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """Generate text from system and user prompts."""


class MockLLM:
    """Deterministic local LLM used for tests and offline development."""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """Return a predictable response derived from the user prompt."""
        compact_prompt = " ".join(user_prompt.split())
        return f"MockLLM response: {compact_prompt}"


class OpenAICompatibleLLM:
    """OpenAI-compatible LLM client with safe fallback behavior."""

    def __init__(self) -> None:
        """Load configuration from environment variables."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._fallback = MockLLM()

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """Generate text with OpenAI SDK when configured, otherwise mock."""
        if not self.api_key:
            return self._fallback.generate(system_prompt, user_prompt, temperature)

        try:
            from openai import OpenAI
        except Exception:
            return self._fallback.generate(system_prompt, user_prompt, temperature)

        try:
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            content = response.choices[0].message.content
            return content or ""
        except Exception:
            return self._fallback.generate(system_prompt, user_prompt, temperature)


def get_llm() -> BaseLLM:
    """Return an OpenAI-compatible LLM when configured, otherwise a mock."""
    if not os.getenv("OPENAI_API_KEY"):
        return MockLLM()

    try:
        import openai  # noqa: F401
    except Exception:
        return MockLLM()

    return OpenAICompatibleLLM()
