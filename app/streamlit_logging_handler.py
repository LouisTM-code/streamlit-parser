"""Bridge-обработчик логов для безопасного вывода сообщений в Streamlit UI.

Роль и ответственность:
    - принимает готовые сообщения логирования из стандартного `logging`;
    - передаёт их во внешний UI-callback без зависимости от глобального `streamlit`.

Границы:
    - не форматирует сообщения и не меняет их текст;
    - не управляет конфигурацией root/logger-уровней и цепочкой обработчиков.

Взаимодействие с другими ролями:
    - подключается в `StreamlitUI` как дополнительный канал вывода логов;
    - получает callback-и отображения от UI-слоя (`markdown`, `warning`, `error`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable


class StreamlitLogHandler(logging.Handler):
    """Безопасный `logging.Handler` для дублирования логов в Streamlit.

    Роль и ответственность:
        - маршрутизирует сообщение по уровню (`INFO`/`WARNING`/`ERROR`) в переданные callback-и;
        - изолирует ошибки UI-вывода, чтобы логирование не влияло на сценарий выполнения.

    Границы:
        - не обращается к глобальному `st` и не хранит состояние Streamlit-сессии;
        - не изменяет строку сообщения и не выполняет дополнительную бизнес-логику.

    Взаимодействие с другими ролями:
        - используется `StreamlitUI` как bridge между `TracingLogger`/`logging` и UI.
    """

    def __init__(
        self,
        info_writer: Callable[[str], None],
        warning_writer: Callable[[str], None],
        error_writer: Callable[[str], None],
    ) -> None:
        """Сохраняет callback-и вывода сообщений по уровням логирования."""
        super().__init__()
        self._info_writer = info_writer
        self._warning_writer = warning_writer
        self._error_writer = error_writer

    def emit(self, record: logging.LogRecord) -> None:
        """Передаёт готовое сообщение в UI и подавляет ошибки визуализации."""
        try:
            message = record.getMessage()
            if record.levelno >= logging.ERROR:
                self._error_writer(message)
            elif record.levelno >= logging.WARNING:
                self._warning_writer(message)
            else:
                self._info_writer(message)
        except Exception:  # noqa: BLE001
            return
