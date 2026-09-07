"""Tests for the shared structured-output LLM boundary."""

from __future__ import annotations

from types import SimpleNamespace

from pydantic import BaseModel

from app.llm import structured


class _Answer(BaseModel):
    value: int


class _FakeCompletions:
    def __init__(self, contents: list[str]):
        self.contents = contents
        self.calls = 0

    def create(self, **_kwargs: object) -> SimpleNamespace:
        content = self.contents[self.calls]
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def test_parse_json_object_accepts_fences_and_surrounding_text() -> None:
    assert structured.parse_json_object("```json\n{\"value\": 3}\n```") == {
        "value": 3
    }
    assert structured.parse_json_object("result: {\"value\": 4} done") == {
        "value": 4
    }


def test_call_structured_retries_invalid_response(monkeypatch: object) -> None:
    completions = _FakeCompletions(["not json", '{"value": 7}'])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    settings = SimpleNamespace(llm_model="test", llm_json_mode=False)
    monkeypatch.setattr(structured, "get_llm_client", lambda: client)
    monkeypatch.setattr(structured, "get_settings", lambda: settings)

    result = structured.call_structured(
        _Answer,
        system_prompt="system",
        user_prompt="user",
        max_attempts=2,
    )

    assert result.value == 7
    assert completions.calls == 2
