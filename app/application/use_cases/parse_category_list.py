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

from parser_domain.product_list_parser import ProductListParser
from parser_domain.types import (
    CategoryListParseResult,
    ParseCategoryListCommand,
)
from parser_domain.web_parser import WebParser


class ParseCategoryListUseCase:
    """Сценарий пакетного парсинга каталожных ссылок."""

    def __init__(self, parser: WebParser) -> None:
        """Сохраняет общий `WebParser` для повторного использования в дочернем парсере."""
        self._parser = parser

    def execute(self, command: ParseCategoryListCommand) -> CategoryListParseResult:
        """Запускает batch-парсинг и возвращает типизированный `CategoryListParseResult`."""
        if len(command.links) == 0:
            raise Exception("Список ссылок пуст")

        list_parser = ProductListParser(
            links=list(command.links),
            output_file=command.output_filename,
            base_parser=self._parser,
            mode=command.parser_mode,
        )
        _, stats = list_parser.run()
        excel_bytes = list_parser.save_results()
        return CategoryListParseResult(
            stats=stats,
            excel_bytes=excel_bytes,
            output_filename=command.output_filename,
        )
