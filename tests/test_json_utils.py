from __future__ import annotations

from code2skill.json_utils import parse_json_object


class FakeBackend:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self.response


def test_parse_json_object_accepts_fenced_json_with_trailing_commas() -> None:
    raw = """结果如下：

```json
{
  "updated_sections": [
    {
      "heading": "Core Rules",
      "content": "## Core Rules\\n- Keep behavior stable.",
    }
  ],
}
```
"""

    payload = parse_json_object(
        raw,
        error_context="test",
        expected_top_level_key="updated_sections",
    )

    assert payload["updated_sections"][0]["heading"] == "Core Rules"


def test_parse_json_object_repairs_invalid_payload_with_backend_retry() -> None:
    backend = FakeBackend('{"updated_sections": []}')

    payload = parse_json_object(
        "updated_sections: []",
        error_context="test",
        backend=backend,
        expected_top_level_key="updated_sections",
    )

    assert payload == {"updated_sections": []}
    assert len(backend.calls) == 1
    assert "updated_sections" in backend.calls[0][0]
