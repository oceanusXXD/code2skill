from __future__ import annotations

import pytest

from code2skill.llm_backend import OpenAIBackend


def test_openai_backend_uses_configured_base_url_and_key(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post_json(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {"output_text": "OK"}

    monkeypatch.setenv("CODE2SKILL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("CODE2SKILL_OPENAI_BASE_URL", "https://proxy.example/v1")
    monkeypatch.setattr("code2skill.llm_backend._post_json", fake_post_json)

    result = OpenAIBackend(model="gpt-test").complete("hello", system="strict")

    assert result == "OK"
    assert captured["url"] == "https://proxy.example/v1/responses"
    assert captured["headers"] == {"Authorization": "Bearer test-key"}
    assert captured["payload"] == {
        "model": "gpt-test",
        "input": "hello",
        "instructions": "strict",
    }


def test_post_json_sends_default_user_agent(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"output_text":"OK"}'

    def fake_urlopen(req, timeout):
        captured["timeout"] = timeout
        captured["headers"] = dict(req.header_items())
        return FakeResponse()

    monkeypatch.setattr("code2skill.llm_backend.request.urlopen", fake_urlopen)

    result = OpenAIBackend(model="gpt-test", api_key="direct-key").complete("hello")

    assert result == "OK"
    assert captured["timeout"] == 90
    assert captured["headers"]["User-agent"].startswith("code2skill/")


def test_openai_backend_accepts_responses_url(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post_json(url, headers, payload):
        captured["url"] = url
        return {"output_text": "OK"}

    monkeypatch.setattr("code2skill.llm_backend._post_json", fake_post_json)

    result = OpenAIBackend(
        model="gpt-test",
        api_key="direct-key",
        base_url="https://proxy.example/v1/responses",
    ).complete("hello")

    assert result == "OK"
    assert captured["url"] == "https://proxy.example/v1/responses"


def test_openai_backend_reports_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("CODE2SKILL_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="CODE2SKILL_OPENAI_API_KEY or OPENAI_API_KEY"):
        OpenAIBackend().complete("hello")
