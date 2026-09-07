"""Shared JSON-only LLM invocation with deterministic Pydantic validation."""

from __future__ import annotations

import json
import re
from typing import Any, cast

from pydantic import BaseModel

from app.config import get_settings
from app.llm.client import get_llm_client

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_json_object(content: str) -> dict[str, object]:
    """Parse a JSON object, tolerating markdown fences or surrounding prose."""
    text = content.strip()
    match = _JSON_BLOCK_RE.search(text)
    if match:
        text = match.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise TypeError("LLM response must be a JSON object")
    return parsed


def call_structured[ModelT: BaseModel](
    response_model: type[ModelT],
    *,
    system_prompt: str,
    user_prompt: str,
    max_attempts: int = 2,
) -> ModelT:
    """Call the configured model and validate its JSON response, retrying once."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    settings = get_settings()
    client = get_llm_client()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        kwargs: dict[str, object] = {
            "model": settings.llm_model,
            "temperature": 0,
            "messages": messages,
        }
        if settings.llm_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        create = cast(Any, client.chat.completions.create)
        response = create(**kwargs)
        content = response.choices[0].message.content or "{}"
        try:
            return response_model.model_validate(parse_json_object(content))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < max_attempts:
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "The response failed schema validation: "
                                f"{exc}. Return one corrected JSON object only."
                            ),
                        },
                    ]
                )

    assert last_error is not None
    raise ValueError(f"Structured LLM output remained invalid: {last_error}")
