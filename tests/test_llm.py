"""Tests for the LLM abstraction layer."""

from app.llm import MockLLM, get_llm


def test_mock_llm_returns_deterministic_response() -> None:
    """MockLLM should return a predictable local response."""
    llm = MockLLM()

    response = llm.generate("system", "  Summarize   this request.  ")

    assert response == "MockLLM response: Summarize this request."


def test_get_llm_returns_mock_without_api_key(monkeypatch) -> None:
    """get_llm should avoid real API clients when no key is configured."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    llm = get_llm()

    assert isinstance(llm, MockLLM)
