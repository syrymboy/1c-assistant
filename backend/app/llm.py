"""Абстракция LLM-провайдера: любой провайдер отдаёт ответ потоком фрагментов текста."""
import re
import time
from typing import Iterator, Protocol

from app.config import settings

SYSTEM_PROMPT = (
    "Ты — ассистент для получения управленческой информации из 1С:Предприятие. "
    "Отвечай по-русски, кратко и по делу. Пока доступа к данным 1С у тебя нет: "
    "если для ответа нужны цифры из базы, честно скажи об этом и не выдумывай их."
)


class LLMProvider(Protocol):
    name: str

    def stream(self, history: list[dict], sources: list[str]) -> Iterator[str]:
        """sources — названия источников 1С, выбранных пользователем. history — список {"role": "user"|"assistant", "content": str}, последним идёт вопрос."""
        ...


class MockProvider:
    """Заглушка без внешних вызовов: нужна для демо и разработки без ключей."""

    name = "mock"

    def stream(self, history: list[dict], sources: list[str]) -> Iterator[str]:
        question = history[-1]["content"].strip()
        listed = "\n".join(f"- {x}" for x in sources) if sources else "- пока не выбраны"
        text = (
            f"Вы спросили: «{question}».\n\n"
            f"**Источники, по которым я бы искал ответ:**\n{listed}\n\n"
            "Сейчас ассистент работает в **демо-режиме**: подключение к 1С и языковой модели ещё не настроено, "
            "поэтому реальных данных я показать не могу. Когда оно появится, здесь будут таблицы и графики."
        )
        for token in re.findall(r"\S+\s*|\s+", text):
            yield token
            time.sleep(0.03)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def stream(self, history: list[dict], sources: list[str]) -> Iterator[str]:
        system = SYSTEM_PROMPT + (
            " Пользователь разрешил использовать только эти источники данных: " + ", ".join(sources) + "."
            if sources else " Пользователь пока не выбрал источники данных."
        )
        with self.client.messages.stream(
            model=settings.llm_model,
            max_tokens=1024,
            system=system,
            messages=history,
        ) as s:
            yield from s.text_stream


_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        if settings.llm_provider == "anthropic":
            if not settings.anthropic_api_key:
                raise RuntimeError("LLM_PROVIDER=anthropic, но ANTHROPIC_API_KEY не задан")
            _provider = AnthropicProvider()
        else:
            _provider = MockProvider()
    return _provider
