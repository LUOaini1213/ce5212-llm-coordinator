"""Pull a JSON object/array out of messy model text."""

from __future__ import annotations

import json
from typing import Any


THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"


def strip_think_blocks(text: str) -> str:
    """Remove each ``<think>...</think>`` pair, searching for the close tag
    only after its open tag.

    A stray ``</think>`` before ``<think>``, or an unclosed ``<think>``, is
    left in place for the brace extraction below to step over. Every pass
    either removes a pair (the text gets shorter) or stops, so this always
    terminates.
    """
    while True:
        start = text.find(THINK_OPEN)
        if start < 0:
            return text
        end = text.find(THINK_CLOSE, start + len(THINK_OPEN))
        if end < 0:
            return text
        text = (text[:start] + text[end + len(THINK_CLOSE):]).strip()


def extract_json_text(raw: str) -> str:
    text = strip_think_blocks(raw.strip())
    text = text.replace("```json", "").replace("```", "").strip()
    first_brace = text.find("{")
    first_bracket = text.find("[")
    if first_brace >= 0 and (first_bracket < 0 or first_brace < first_bracket):
        text = text[first_brace:]
    elif first_bracket >= 0:
        text = text[first_bracket:]
    last_brace = text.rfind("}")
    last_bracket = text.rfind("]")
    cut = max(last_brace, last_bracket)
    if cut >= 0:
        text = text[: cut + 1]
    return text


def parse_json(text: str, fallback: Any) -> Any:
    blob = extract_json_text(text)
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        start = blob.find("{")
        end = blob.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(blob[start:end])
            except json.JSONDecodeError:
                pass
        start = blob.find("[")
        end = blob.rfind("]") + 1
        if start != -1 and end > start:
            try:
                return json.loads(blob[start:end])
            except json.JSONDecodeError:
                pass
        return fallback
