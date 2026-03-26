"""Тонкий adapter над стандартным `logging.Logger` с поддержкой trace context.

Роль и ответственность:
    - проксирует запись логов в стандартный logger без изменения каналов вывода;
    - детерминированно добавляет опциональный trace context в сообщение.

Границы:
    - не создаёт и не настраивает глобальный logging root;
    - не внедряет внешние зависимости и DI-контейнеры.

Взаимодействие с другими ролями:
    - принимает уже настроенный `logging.Logger` от вызывающего слоя;
    - использует `TraceContext` как типизированный источник метаданных записи.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
import logging
from typing import Iterator

from parser_domain.infrastructure.logging.trace_context import TraceContext


class TracingLogger:
    """Обёртка для единообразного логирования с опциональным контекстом.

    Роль и ответственность:
        - сохраняет поведение уровней `info`, `warning`, `error` стандартного logger;
        - формирует компактный суффикс контекста при его наличии.

    Границы:
        - не изменяет уровень и обработчики underlying logger;
        - не перехватывает исключения и не меняет семантику вызывающего кода.

    Взаимодействие с другими ролями:
        - принимает `logging.Logger` в конструкторе;
        - вызывается прикладными парсерами вместо прямых вызовов logger-методов.
    """

    def __init__(self, logger: logging.Logger) -> None:
        """Инициализирует обёртку вокруг переданного `logging.Logger`."""
        self._logger = logger
        self._scoped_contexts: ContextVar[tuple[TraceContext, ...]] = ContextVar(
            "tracing_logger_scoped_contexts", default=()
        )

    @contextmanager
    def trace_scope(self, context: TraceContext) -> Iterator[None]:
        """Временно добавляет контекст трассировки для серии вложенных логов.

        Роль и ответственность:
            - навешивает `TraceContext` на текущий execution-scope;
            - автоматически снимает добавленный контекст при выходе из блока.

        Границы:
            - не меняет порядок и уровень лог-записей;
            - не модифицирует глобальную конфигурацию `logging`.

        Взаимодействие с другими ролями:
            - используется прикладными парсерами через `with`-блоки;
            - итоговый контекст объединяется с явным `context` в `info/warning/error`.
        """
        current = self._scoped_contexts.get()
        token: Token[tuple[TraceContext, ...]] = self._scoped_contexts.set(
            current + (context,)
        )
        try:
            yield
        finally:
            self._scoped_contexts.reset(token)

    def info(self, message: str, context: TraceContext | None = None) -> None:
        """Записывает сообщение уровня INFO с опциональным trace context."""
        self._logger.info(self._with_context(message, context))

    def warning(self, message: str, context: TraceContext | None = None) -> None:
        """Записывает сообщение уровня WARNING с опциональным trace context."""
        self._logger.warning(self._with_context(message, context))

    def error(self, message: str, context: TraceContext | None = None) -> None:
        """Записывает сообщение уровня ERROR с опциональным trace context."""
        self._logger.error(self._with_context(message, context))

    def _with_context(self, message: str, context: TraceContext | None) -> str:
        """Возвращает исходное сообщение или сообщение с детерминированным trace-суффиксом."""
        resolved_context = self._compose_context(context)
        if resolved_context is None:
            return message

        parts: list[str] = []
        if resolved_context.operation is not None:
            parts.append(f"operation={resolved_context.operation}")
        if resolved_context.url is not None:
            parts.append(f"url={resolved_context.url}")
        if resolved_context.page is not None:
            parts.append(f"page={resolved_context.page}")
        if resolved_context.item_index is not None:
            parts.append(f"item_index={resolved_context.item_index}")
        if resolved_context.parser_mode is not None:
            parts.append(f"parser_mode={resolved_context.parser_mode}")

        if not parts:
            return message

        return f"{message} | trace[{', '.join(parts)}]"

    def _compose_context(self, context: TraceContext | None) -> TraceContext | None:
        """Объединяет scoped-контексты и явный контекст в единый `TraceContext`."""
        scoped = self._scoped_contexts.get()
        if not scoped and context is None:
            return None

        operation: str | None = None
        url: str | None = None
        page: int | None = None
        item_index: int | None = None
        parser_mode: str | None = None

        for ctx in (*scoped, context) if context is not None else scoped:
            if ctx.operation is not None:
                operation = ctx.operation
            if ctx.url is not None:
                url = ctx.url
            if ctx.page is not None:
                page = ctx.page
            if ctx.item_index is not None:
                item_index = ctx.item_index
            if ctx.parser_mode is not None:
                parser_mode = ctx.parser_mode

        if (
            operation is None
            and url is None
            and page is None
            and item_index is None
            and parser_mode is None
        ):
            return None

        return TraceContext(
            operation=operation,
            url=url,
            page=page,
            item_index=item_index,
            parser_mode=parser_mode,
        )
