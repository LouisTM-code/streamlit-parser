"""Тонкий wrapper над стандартным logging с поддержкой типизированного контекста.

Роль и ответственность:
    - делегирует запись сообщений во встроенный `logging.Logger`;
    - добавляет детерминированный компактный trace context к сообщению при его наличии.

Границы:
    - не создаёт и не перенастраивает handler-ы/уровни/каналы вывода;
    - не внедряет DI-контейнер и не управляет жизненным циклом логгеров.

Взаимодействие с другими ролями:
    - получает экземпляр `logging.Logger` от инфраструктурного кода;
    - принимает `TraceContext` как типизированный источник полей трассировки.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import fields
import logging
from typing import Iterator

from parser_domain.infrastructure.logging.trace_context import TraceContext

_SCOPED_TRACE_CONTEXT: ContextVar[TraceContext | None] = ContextVar(
    "tracing_logger_scoped_context",
    default=None,
)


@contextmanager
def trace_scope(context: TraceContext) -> Iterator[None]:
    """Контекстный менеджер сквозной трассировки для всех экземпляров `TracingLogger`.

    Роль и ответственность:
        - задаёт trace context в рамках текущего `with`-блока;
        - обеспечивает наследование контекста во вложенных scope.

    Границы:
        - не меняет конфигурацию обработчиков/уровней стандартного logging;
        - не выполняет запись сообщений самостоятельно.

    Взаимодействие с другими ролями:
        - используется orchestration-кодом (`use-case`, фасады) для автоматического
          обогащения сообщений, записываемых через `TracingLogger`.
    """
    parent = _SCOPED_TRACE_CONTEXT.get()
    merged = TracingLogger._merge_contexts(parent, context)
    token: Token[TraceContext | None] = _SCOPED_TRACE_CONTEXT.set(merged)
    try:
        yield
    finally:
        _SCOPED_TRACE_CONTEXT.reset(token)


class TracingLogger:
    """Адаптер стандартного logger для логирования с необязательным trace context.

    Роль и ответственность:
        - предоставляет единый API уровней info/warning/error;
        - сохраняет поведение стандартного logger при отсутствии контекста.

    Границы:
        - не изменяет конфигурацию глобального logging;
        - не обрабатывает исключения и не преобразует уровни логирования.

    Взаимодействие с другими ролями:
        - вызывается доменными и инфраструктурными классами вместо прямого `logger.info`.
    """

    def __init__(self, logger: logging.Logger) -> None:
        """Инициализирует wrapper поверх переданного `logging.Logger`."""
        self._logger = logger

    @contextmanager
    def trace_scope(self, context: TraceContext) -> Iterator[None]:
        """Временно добавляет trace context к сообщениям внутри блока.

        Роль и ответственность:
            - задаёт scoped-контекст для серии логов в рамках одного `with`-блока;
            - поддерживает вложенные scope с детерминированным объединением полей.

        Границы:
            - не меняет конфигурацию `logging.Logger`;
            - не влияет на сообщения вне границ `with`-блока.

        Взаимодействие с другими ролями:
            - используется прикладным кодом для локального обогащения логов без
              ручной передачи `context` в каждый вызов.
        """
        with trace_scope(context):
            yield

    def info(self, message: str, context: TraceContext | None = None) -> None:
        """Пишет сообщение уровня INFO с необязательным контекстом трассировки."""
        self._logger.info(self._format_message(message, self._resolve_context(context)))

    def warning(self, message: str, context: TraceContext | None = None) -> None:
        """Пишет сообщение уровня WARNING с необязательным контекстом трассировки."""
        self._logger.warning(
            self._format_message(message, self._resolve_context(context))
        )

    def error(self, message: str, context: TraceContext | None = None) -> None:
        """Пишет сообщение уровня ERROR с необязательным контекстом трассировки."""
        self._logger.error(self._format_message(message, self._resolve_context(context)))

    def _resolve_context(self, context: TraceContext | None) -> TraceContext | None:
        """Возвращает итоговый контекст с учётом scoped-контекста логгера."""
        scoped = _SCOPED_TRACE_CONTEXT.get()
        return self._merge_contexts(scoped, context)

    @staticmethod
    def _merge_contexts(
        base: TraceContext | None, overlay: TraceContext | None
    ) -> TraceContext | None:
        """Объединяет контексты: значения `overlay` приоритетнее `base`."""
        if base is None:
            return overlay
        if overlay is None:
            return base

        merged_values = {
            field.name: getattr(overlay, field.name)
            if getattr(overlay, field.name) is not None
            else getattr(base, field.name)
            for field in fields(TraceContext)
        }
        return TraceContext(**merged_values)

    @staticmethod
    def _format_message(message: str, context: TraceContext | None) -> str:
        """Формирует строку лога с детерминированным добавлением контекста."""
        if context is None:
            return message

        parts: list[str] = []
        if context.operation is not None:
            parts.append(f"operation={context.operation}")
        if context.url is not None:
            parts.append(f"url={context.url}")
        if context.page is not None:
            parts.append(f"page={context.page}")
        if context.item_index is not None:
            parts.append(f"item_index={context.item_index}")
        if context.parser_mode is not None:
            parts.append(f"parser_mode={context.parser_mode}")

        if not parts:
            return message
        return f"{message} | context: " + ", ".join(parts)
