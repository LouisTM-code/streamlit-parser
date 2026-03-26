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

import logging

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

        return f"{message} | trace[{', '.join(parts)}]"
