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

import logging

from parser_domain.infrastructure.logging.trace_context import TraceContext


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

    def info(self, message: str, context: TraceContext | None = None) -> None:
        """Пишет сообщение уровня INFO с необязательным контекстом трассировки."""
        self._logger.info(self._format_message(message, context))

    def warning(self, message: str, context: TraceContext | None = None) -> None:
        """Пишет сообщение уровня WARNING с необязательным контекстом трассировки."""
        self._logger.warning(self._format_message(message, context))

    def error(self, message: str, context: TraceContext | None = None) -> None:
        """Пишет сообщение уровня ERROR с необязательным контекстом трассировки."""
        self._logger.error(self._format_message(message, context))

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
