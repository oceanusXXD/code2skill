from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request


class LLMBackend(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


@dataclass(frozen=True)
class OpenAIBackend:
    model: str = "gpt-4o-mini"
    api_key: str | None = None

    def complete(self, prompt: str, system: str | None = None) -> str:
        payload: dict[str, object] = {
            "model": self.model,
            "input": prompt,
        }
        if system:
            payload["instructions"] = system
        data = _post_json(
            url="https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self._api_key()}",
            },
            payload=payload,
        )
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        parts: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        if parts:
            return "\n".join(parts)
        raise RuntimeError("OpenAI response did not contain text output.")

    def _api_key(self) -> str:
        api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI backend.")
        return api_key


@dataclass(frozen=True)
class ClaudeBackend:
    model: str = "claude-sonnet-4-20250514"
    api_key: str | None = None

    def complete(self, prompt: str, system: str | None = None) -> str:
        payload: dict[str, object] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }
        if system:
            payload["system"] = system
        data = _post_json(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._api_key(),
                "anthropic-version": "2023-06-01",
            },
            payload=payload,
        )
        parts: list[str] = []
        for block in data.get("content", []):
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
        raise RuntimeError("Claude response did not contain text output.")

    def _api_key(self) -> str:
        api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for the Claude backend.")
        return api_key


@dataclass(frozen=True)
class QwenBackend:
    model: str = "qwen-plus"
    api_key: str | None = None
    base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

    def complete(self, prompt: str, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data = _post_json(
            url=self.base_url,
            headers={
                "Authorization": f"Bearer {self._api_key()}",
            },
            payload={
                "model": self.model,
                "messages": messages,
            },
        )
        choices = data.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Qwen response did not contain choices.")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict)
                and isinstance(block.get("text"), str)
                and block.get("text")
            ]
            if parts:
                return "\n".join(parts)
        raise RuntimeError("Qwen response did not contain text output.")

    def _api_key(self) -> str:
        api_key = (
            self.api_key
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("QWEN_API_KEY")
        )
        if not api_key:
            raise RuntimeError(
                "DASHSCOPE_API_KEY or QWEN_API_KEY is required for the Qwen backend."
            )
        return api_key


class MockBackend:
    def __init__(self, responses: list[str] | dict[str, str] | str) -> None:
        self.responses = responses
        self.calls: list[dict[str, str | None]] = []
        self._index = 0

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
            }
        )
        if isinstance(self.responses, str):
            return self.responses
        if isinstance(self.responses, list):
            if self._index >= len(self.responses):
                raise RuntimeError("MockBackend ran out of queued responses.")
            response = self.responses[self._index]
            self._index += 1
            return response
        if isinstance(self.responses, dict):
            for needle, response in self.responses.items():
                if needle in prompt:
                    return response
            raise RuntimeError("MockBackend did not find a matching prompt response.")
        raise RuntimeError("Unsupported MockBackend response payload.")


def build_llm_backend(provider: str, model: str | None = None) -> LLMBackend:
    normalized = provider.strip().lower()
    if normalized == "openai":
        return OpenAIBackend(model=model or OpenAIBackend.model)
    if normalized == "claude":
        return ClaudeBackend(model=model or ClaudeBackend.model)
    if normalized == "qwen":
        return QwenBackend(model=model or QwenBackend.model)
    raise ValueError(f"Unsupported LLM backend: {provider}")


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
) -> dict[str, object]:
    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **headers,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("LLM response payload was not a JSON object.")
    return data
