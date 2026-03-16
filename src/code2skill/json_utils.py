from __future__ import annotations

import json
import re
from json import JSONDecodeError

from .llm_backend import LLMBackend


JSON_REPAIR_SYSTEM = (
    "你是一个 JSON 修复器。"
    "你的任务是把给定内容改写成严格合法的 JSON 对象。"
    "不要解释，不要输出 Markdown 代码块，不要补充额外字段，不要改变原始语义。"
)


def parse_json_object(
    raw: str,
    *,
    error_context: str,
    backend: LLMBackend | None = None,
    expected_top_level_key: str | None = None,
    repair_hint: str | None = None,
) -> dict[str, object]:
    errors: list[str] = []

    payload, error = _parse_from_candidates(raw)
    if payload is not None:
        return payload
    if error is not None:
        errors.append(error)

    if backend is not None:
        repaired = backend.complete(
            prompt=_build_repair_prompt(
                raw=raw,
                expected_top_level_key=expected_top_level_key,
                repair_hint=repair_hint,
            ),
            system=JSON_REPAIR_SYSTEM,
        )
        payload, repair_error = _parse_from_candidates(repaired)
        if payload is not None:
            return payload
        if repair_error is not None:
            errors.append(f"repair attempt failed: {repair_error}")

    details = f" Last error: {errors[-1]}" if errors else ""
    raise RuntimeError(f"{error_context}.{details}")


def _parse_from_candidates(raw: str) -> tuple[dict[str, object] | None, str | None]:
    last_error: str | None = None
    for candidate in _json_candidates(raw):
        payload, error = _decode_json_object(candidate)
        if payload is not None:
            return payload, None
        if error is not None:
            last_error = error
    return None, last_error


def _json_candidates(raw: str) -> list[str]:
    stripped = raw.lstrip("\ufeff").strip()
    candidates: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        normalized = value.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    add(stripped)

    for block in re.findall(r"```(?:json)?\s*([\s\S]*?)```", stripped, flags=re.IGNORECASE):
        add(block)

    for block in _extract_balanced_json_objects(stripped):
        add(block)

    return candidates


def _extract_balanced_json_objects(text: str) -> list[str]:
    blocks: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(text[start : index + 1])
                start = None
    return blocks


def _decode_json_object(candidate: str) -> tuple[dict[str, object] | None, str | None]:
    last_error: str | None = None
    for variant in _candidate_variants(candidate):
        payload, error = _decode_single_variant(variant)
        if payload is not None:
            return payload, None
        if error is not None:
            last_error = error
    return None, last_error


def _candidate_variants(candidate: str) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        normalized = value.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        variants.append(normalized)

    add(candidate)
    add(_strip_leading_json_marker(candidate))
    add(_strip_trailing_commas(candidate))
    add(_strip_trailing_commas(_strip_leading_json_marker(candidate)))
    return variants


def _decode_single_variant(candidate: str) -> tuple[dict[str, object] | None, str | None]:
    try:
        payload = json.loads(candidate)
    except JSONDecodeError as exc:
        decoder = json.JSONDecoder()
        try:
            payload, end = decoder.raw_decode(candidate)
        except JSONDecodeError:
            return None, str(exc)
        if candidate[end:].strip():
            return None, str(exc)

    if not isinstance(payload, dict):
        return None, "top-level JSON value was not an object"
    return payload, None


def _strip_leading_json_marker(candidate: str) -> str:
    return re.sub(r"^\s*json\s*", "", candidate, count=1, flags=re.IGNORECASE)


def _strip_trailing_commas(candidate: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False
    pending_comma = False

    for char in candidate:
        if escaped:
            if pending_comma:
                result.append(",")
                pending_comma = False
            result.append(char)
            escaped = False
            continue

        if char == "\\":
            if pending_comma:
                result.append(",")
                pending_comma = False
            result.append(char)
            escaped = True
            continue

        if char == '"':
            if pending_comma:
                result.append(",")
                pending_comma = False
            result.append(char)
            in_string = not in_string
            continue

        if not in_string and char == ",":
            pending_comma = True
            continue

        if pending_comma:
            if not in_string and char in "}]":
                pending_comma = False
            elif char.isspace():
                continue
            else:
                result.append(",")
                pending_comma = False

        result.append(char)

    if pending_comma:
        result.append(",")
    return "".join(result)


def _build_repair_prompt(
    *,
    raw: str,
    expected_top_level_key: str | None,
    repair_hint: str | None,
) -> str:
    requirements = [
        "把下面内容修正为严格合法的 JSON 对象。",
        "只修复格式、转义、逗号、引号、代码块包裹和多余说明文字。",
        "不要改变语义，不要新增解释。",
    ]
    if expected_top_level_key:
        requirements.append(f"顶层对象必须包含键 `{expected_top_level_key}`。")
    if repair_hint:
        requirements.append(repair_hint)
    return "\n".join(
        [
            *requirements,
            "",
            "原始内容：",
            raw,
        ]
    )
