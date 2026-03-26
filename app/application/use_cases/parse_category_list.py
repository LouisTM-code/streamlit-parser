"""Модуль parse_category_list.

Роль и ответственность:
    - предоставляет публичные элементы этого слоя.

Границы:
    - не реализует ответственность соседних слоёв.

Взаимодействие с другими ролями:
    - используется через импорт другими модулями проекта.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from parser_domain.web_parser import WebParser
from parser_domain.product_list_parser import ProductListParser


class ParseCategoryListUseCase:
    """Класс ParseCategoryListUseCase.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

    def __init__(self, parser: WebParser) -> None:
        """Выполняет операцию роли «__init__»."""
        self._parser = parser

    def execute(
        self,
        links: list[str],
        output_filename: str,
        parser_mode: str = "basic",
    ) -> Tuple[Dict[str, Any], bytes, str]:
        """Выполняет операцию роли «execute»."""
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
