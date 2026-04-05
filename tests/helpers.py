from __future__ import annotations


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
