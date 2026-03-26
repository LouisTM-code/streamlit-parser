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
from collections.abc import Callable

import pandas as pd

from application.dto.tracing import (
    ErrorCallback,
    ItemErrorEvent,
    ProgressCallback,
    ProgressEvent,
    StatsCallback,
    StatsEvent,
)
from parser_domain.infrastructure.logging.trace_context import TraceContext
from parser_domain.infrastructure.logging.tracing_logger import trace_scope
from parser_domain.types import ParseProductsCommand, ProductDetails, ProductsParseResult
from parser_domain.web_parser import WebParser

ProcessPageCallback = Callable[[str, Callable[[str], object]], object]


class ParseProductsUseCase:
    """Координатор бизнес-сценария по сбору карточек товаров."""

    def __init__(self, parser: WebParser) -> None:
        """Фиксирует зависимость на доменный парсер, реализующий операции чтения данных."""
        self._parser = parser

    @staticmethod
    def _detail_to_row(details: ProductDetails) -> dict[str, str]:
        """Преобразует `ProductDetails` в плоскую строку отчёта."""
        row: dict[str, str] = {
            "Товар": details.title,
            "Артикул": details.article,
            "Бренд": details.brand,
            "Цена": details.price,
            "Наличие": details.availability,
            "Описание": details.description,
        }
        row.update(dict(details.features))
        return row

    def execute(
        self,
        command: ParseProductsCommand,
        on_progress: ProgressCallback | None = None,
        on_stats: StatsCallback | None = None,
        on_page_request: ProcessPageCallback | None = None,
        on_item_error: ErrorCallback | None = None,
    ) -> ProductsParseResult:
        """Выполняет парсинг товаров и публикует типизированные callback-события."""
        with trace_scope(
            TraceContext(operation="parse_products", url=command.category_url)
        ):
            links = self._parser.iter_category_product_links(command.category_url)
            if not links:
                raise Exception("Ссылки на товары не найдены")

            if on_progress:
                on_progress(ProgressEvent(progress=15, status="Поиск ссылок на товары…"))

            total = len(links)
            products: list[dict[str, str]] = []

            for idx, link in enumerate(links, 1):
                with trace_scope(TraceContext(item_index=idx)):
                    try:
                        if on_progress:
                            progress = 15 + int(70 * (idx / total))
                            on_progress(
                                ProgressEvent(
                                    progress=progress,
                                    status=f"Обработка товара {idx}/{total}",
                                )
                            )
                        if on_stats:
                            on_stats(StatsEvent(total=total, processed=idx))
                        if on_page_request:
                            product_page = on_page_request(link, self._parser.get_page)
                        else:
                            product_page = self._parser.get_page(link)
                        if product_page:
                            details = self._parser.parse_product(product_page)
                            products.append(self._detail_to_row(details))

                        time.sleep(0.1)
                    except Exception as ex:  # noqa: BLE001
                        if on_item_error:
                            on_item_error(
                                ItemErrorEvent(
                                    index=idx,
                                    error=f"({link}): {type(ex).__name__} - {ex}",
                                )
                            )

        if on_progress:
            on_progress(ProgressEvent(progress=95, status="Формирование отчёта…"))

        frame = pd.DataFrame(products)
        if frame.empty:
            raise Exception("Не удалось собрать данные")

        return ProductsParseResult(
            dataframe=frame,
            output_filename=command.output_filename,
        )
