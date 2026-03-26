"""Use-case сценария парсинга карточек товаров из одной категории.

Роль и ответственность:
    - оркестрирует последовательность: ссылки категории -> карточки товаров -> DataFrame;
    - транслирует прогресс и ошибки во внешние callback-и UI.

Границы:
    - не управляет отображением и хранением UI-состояния;
    - не реализует низкоуровневый HTTP и разбор DOM.

Взаимодействие с другими ролями:
    - использует контракт `WebParser` для загрузки страниц и извлечения данных.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd

from parser_domain.web_parser import WebParser

ProgressCallback = Callable[[float, str], None]
StatsCallback = Callable[[int, int], None]
ProcessPageCallback = Callable[[str, Callable[[str], Any]], Any]
ErrorCallback = Callable[[int, Exception], None]


class ParseProductsUseCase:
    """Координатор бизнес-сценария по сбору карточек товаров."""

    def __init__(self, parser: WebParser) -> None:
        """Фиксирует зависимость на доменный парсер, реализующий операции чтения данных."""
        self._parser = parser

    def execute(
        self,
        url: str,
        output_filename: str,
        on_progress: Optional[ProgressCallback] = None,
        on_stats: Optional[StatsCallback] = None,
        on_page_request: Optional[ProcessPageCallback] = None,
        on_item_error: Optional[ErrorCallback] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """Выполняет парсинг товаров и возвращает `(DataFrame, output_filename)`.

        Контракт:
            - бросает `Exception`, если ссылки товаров не найдены или итоговые данные пусты;
            - вызывает callback-и только если они переданы;
            - пропускает ошибки отдельных карточек через `on_item_error`, не прерывая цикл.
        """
        links = self._parser.iter_category_product_links(url)
        if not links:
            raise Exception("Ссылки на товары не найдены")

        if on_progress:
            on_progress(15, "Поиск ссылок на товары…")

        total = len(links)
        products: list[Dict[str, Any]] = []

        for idx, link in enumerate(links, 1):
            try:
                if on_progress:
                    progress = 15 + int(70 * (idx / total))
                    on_progress(progress, f"Обработка товара {idx}/{total}")
                if on_stats:
                    on_stats(total, idx)
                if on_page_request:
                    product_page = on_page_request(link, self._parser.get_page)
                else:
                    product_page = self._parser.get_page(link)
                if product_page:
                    products.append(self._parser.parse_product(product_page))

                time.sleep(0.1)
            except Exception as ex:  # noqa: BLE001
                if on_item_error:
                    on_item_error(idx, ex)

        if on_progress:
            on_progress(95, "Формирование отчёта…")

        frame = pd.DataFrame(products)
        if frame.empty:
            raise Exception("Не удалось собрать данные")

        return frame, output_filename
