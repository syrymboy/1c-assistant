"""Абстракция LLM-провайдера: любой провайдер отдаёт ответ потоком фрагментов текста."""
import json
import re
import time
from typing import Iterator, Protocol

from app.config import settings

SYSTEM_PROMPT = (
    "Ты — ассистент для получения управленческой информации из 1С:Предприятие. "
    "Отвечай по-русски, кратко и по делу, форматируй ответ в Markdown (списки, таблицы). "
    "Это демонстрационная версия: подключения к реальной базе 1С пока нет. Если для ответа нужны цифры из базы, "
    "приведи правдоподобный пример с вымышленными данными и обязательно пометь его строкой «Демонстрационные данные»."
)


def normalize(history: list[dict]) -> list[dict]:
    """API требует, чтобы диалог начинался с реплики пользователя и роли чередовались: склеиваем подряд идущие, отбрасываем начало с ответа ассистента."""
    out: list[dict] = []
    for m in history:
        if not m["content"].strip():
            continue
        if out and out[-1]["role"] == m["role"]:
            out[-1] = {"role": m["role"], "content": out[-1]["content"] + "\n\n" + m["content"]}
        else:
            out.append({"role": m["role"], "content": m["content"]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


class LLMError(Exception):
    """Ошибка провайдера с текстом, который можно показать пользователю."""


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
            max_tokens=2048,
            system=system,
            messages=normalize(history),
        ) as s:
            yield from s.text_stream


class _Retry(Exception):
    def __init__(self, msg: str, got: bool) -> None:
        super().__init__(msg)
        self.got = got


class GeminiProvider:
    """Google Gemini через Interactions API (бесплатный ключ: aistudio.google.com/apikey).

    Старый :generateContent у новых ключей отключён для большинства моделей, поэтому используется /v1beta/interactions.
    Без дополнительных зависимостей: обычный HTTP + SSE."""

    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

    def stream(self, history: list[dict], sources: list[str]) -> Iterator[str]:
        import httpx

        system = SYSTEM_PROMPT + (
            " Пользователь разрешил использовать только эти источники данных: " + ", ".join(sources) + "."
            if sources else " Пользователь пока не выбрал источники данных."
        )
        steps = [
            {"type": "model_output" if m["role"] == "assistant" else "user_input", "content": [{"type": "text", "text": m["content"]}]}
            for m in normalize(history)
        ]
        body = {
            "model": settings.gemini_model, "system_instruction": system, "input": steps, "stream": True, "store": False,
            "generation_config": {"max_output_tokens": 4096, "thinking_level": "low"},
        }
        # Gemini иногда не отвечает или отдаёт 503 «высокий спрос»: до первого фрагмента пробуем ещё раз
        for attempt in (1, 2):
            try:
                yield from self._once(httpx, body)
                return
            except _Retry as e:
                if attempt == 2:
                    raise LLMError(str(e)) from None
            except httpx.TimeoutException:
                if attempt == 2:
                    raise LLMError("Gemini не ответил вовремя. Повторите вопрос.") from None
            except httpx.HTTPError as e:
                raise LLMError("Не удалось связаться с Gemini. Проверьте интернет и повторите.") from e

    def _once(self, httpx, body: dict) -> Iterator[str]:
        got = False
        with httpx.stream(
            "POST", self.URL, json=body, timeout=httpx.Timeout(10, read=25),
            headers={"x-goog-api-key": settings.gemini_api_key},
        ) as r:
            if r.status_code != 200:
                r.read()
                msg = self._explain(r.status_code, r.text)
                if r.status_code in (500, 503):
                    raise _Retry(msg, got=False)
                raise LLMError(msg)
            kinds: dict[int, str] = {}  # index шага -> тип (текст отдаём только из model_output, «мысли» пропускаем)
            for line in r.iter_lines():
                if not line.startswith("data:") or line.strip() == "data: [DONE]":
                    continue
                ev = json.loads(line[5:])
                kind = ev.get("event_type")
                if kind == "step.start":
                    kinds[ev["index"]] = (ev.get("step") or {}).get("type", "")
                elif kind == "step.delta" and kinds.get(ev["index"]) == "model_output":
                    text = (ev.get("delta") or {}).get("text")
                    if text:
                        got = True
                        yield text
                elif kind == "error":
                    msg = self._explain((ev.get("error") or {}).get("code"), json.dumps(ev, ensure_ascii=False))
                    if got:
                        raise LLMError(msg)
                    raise _Retry(msg, got=False)
        if not got:
            raise LLMError("Gemini вернул пустой ответ. Повторите вопрос.")

    @staticmethod
    def _explain(status, text: str) -> str:
        if status in (429, "resource_exhausted"):
            return "Превышен бесплатный лимит запросов Gemini. Подождите минуту и повторите."
        if status in (503, "service_unavailable"):
            return "Gemini сейчас перегружен. Повторите через минуту или выберите другую модель (GEMINI_MODEL)."
        if status in (400, 403) and "API key" in text:
            return "Gemini отклонил ключ. Проверьте GEMINI_API_KEY."
        if status in (404, "not_found"):
            return f"Модель {settings.gemini_model} недоступна для этого ключа. Укажите другую в GEMINI_MODEL."
        return f"Gemini вернул ошибку {status}."


_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        if settings.llm_provider == "anthropic":
            if not settings.anthropic_api_key:
                raise RuntimeError("LLM_PROVIDER=anthropic, но ANTHROPIC_API_KEY не задан")
            _provider = AnthropicProvider()
        elif settings.llm_provider == "gemini":
            if not settings.gemini_api_key:
                raise RuntimeError("LLM_PROVIDER=gemini, но GEMINI_API_KEY не задан")
            _provider = GeminiProvider()
        else:
            _provider = MockProvider()
    return _provider
