"""Use-case пакетного парсинга списка категорий.

Роль и ответственность:
    - подготавливает `ProductListParser` и запускает его сценарий;
    - возвращает статистику и бинарное содержимое Excel-отчёта.

Границы:
    - не занимается рендером интерфейса;
    - не реализует извлечение полей из карточек самостоятельно.

Взаимодействие с другими ролями:
    - использует `WebParser` как базовую инфраструктуру загрузки страниц;
    - делегирует табличный сбор `ProductListParser`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from parser_domain.web_parser import WebParser
from parser_domain.product_list_parser import ProductListParser


class ParseCategoryListUseCase:
    """Сценарий пакетного парсинга каталожных ссылок."""

    def __init__(self, parser: WebParser) -> None:
        """Сохраняет общий `WebParser` для повторного использования в дочернем парсере."""
        self._parser = parser

    def execute(
        self,
        links: list[str],
        output_filename: str,
        parser_mode: str = "basic",
    ) -> Tuple[Dict[str, Any], bytes, str]:
        """Запускает batch-парсинг и возвращает `(stats, excel_bytes, output_filename)`.

        Контракт:
            - бросает `Exception`, если список ссылок пуст;
            - режим парсинга передаётся без преобразования в `ProductListParser`.
        """
        if len(links) == 0:
            raise Exception("Список ссылок пуст")

        list_parser = ProductListParser(
            links=links,
            output_file=output_filename,
            base_parser=self._parser,
            mode=parser_mode,
        )
        _, stats = list_parser.run()
        excel_bytes = list_parser.save_results()
        return stats, excel_bytes, output_filename
