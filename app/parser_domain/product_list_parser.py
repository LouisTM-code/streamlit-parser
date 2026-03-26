from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Mapping

from bs4 import BeautifulSoup

from parser_domain.infrastructure.exporters.excel_exporter import ExcelExporter
from parser_domain.infrastructure.logging.trace_context import TraceContext
from parser_domain.infrastructure.logging.tracing_logger import TracingLogger
from parser_domain.infrastructure.parsers.card_extractors.v1 import CardExtractorV1
from parser_domain.infrastructure.parsers.card_extractors.v2 import CardExtractorV2
from parser_domain.infrastructure.parsers.category_page_parser import CategoryPageParser
from parser_domain.infrastructure.parsers.feature_extractor import FeatureExtractor
from parser_domain.infrastructure.url_tools.url_normalizer import URLNormalizer
from parser_domain.types import (
    CategoryParseStats,
    ParserMode,
    ProductCardBase,
    ProductCardFull,
)
from parser_domain.web_parser import WebParser

__all__ = ["ProductListParser"]


class ProductListParser:
    """Парсер списка категорий с накоплением результатов по листам Excel.

    Роль и ответственность:
        - обходит переданные категории с учётом пагинации;
        - извлекает строки товаров в режимах `ParserMode.BASIC` и `ParserMode.FULLTABLE`;
        - формирует статистику и структуру данных для экспортера.

    Границы:
        - не выполняет UI-обновления;
        - не реализует запись Excel напрямую (делегирует `ExcelExporter`).

    Взаимодействие с другими ролями:
        - использует `WebParser` для доступа к страницам;
        - использует `CategoryPageParser` для извлечения строк категорий.
    """

    def __init__(
        self,
        links: list[str],
        output_file: str = "product_list.xlsx",
        base_parser: WebParser | None = None,
        mode: ParserMode = ParserMode.BASIC,
    ) -> None:
        """Подготавливает режим, ссылки, парсеры карточек и внутренние буферы результата."""
        self.logger = TracingLogger(self._configure_logger())
        self.parser: WebParser = base_parser or WebParser()
        self.output_file: str = output_file
        self.mode: ParserMode = mode

        self._url_normalizer = URLNormalizer()
        self.links: list[str] = self._url_normalizer.normalize_links(links)
        self.links = self._url_normalizer.validate_links(self.links)
        self.logger.info(
            f"Принято {len(self.links)} ссылок, режим: {self.mode.value}",
            TraceContext(operation="init", parser_mode=self.mode.value),
        )

        self._sheet_name_counts: dict[str, int] = {}
        self._sheet_data: OrderedDict[str, list[dict[str, str]]] = OrderedDict()

        self._category_page_parser = CategoryPageParser(
            extractor_v1=CardExtractorV1(self._clean_text, self._clean_price),
            extractor_v2=CardExtractorV2(self._clean_text, self._clean_price),
            feature_extractor=FeatureExtractor(self._clean_text),
        )

    @staticmethod
    def _configure_logger() -> logging.Logger:
        """Создаёт выделенный logger парсера категорий без дублирования обработчиков."""
        logger = logging.getLogger("ProductListParser")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
                )
            )
            logger.addHandler(handler)
        logger.propagate = False
        return logger

    @staticmethod
    def _clean_text(text: str) -> str:
        """Нормализует текстовые значения, повторяя прежнее поведение."""
        cleaned = (
            text.replace("\xa0", " ")
            .replace("&nbsp;", " ")
            .replace("Бренд: ", "")
        )
        return " ".join(cleaned.split()).strip()

    @staticmethod
    def _clean_price(text: str) -> str:
        """Нормализует значение цены, повторяя прежнее поведение."""
        no_nbsp = text.replace("\xa0", " ").replace("&nbsp;", " ")
        return re.sub(r"[^0-9.,]", "", no_nbsp).replace(" ", "")

    def _extract_page_title(self, soup: BeautifulSoup) -> str:
        """Извлекает заголовок категории для имени листа; fallback — `Категория`."""
        tag = soup.select_one("h1.cnc-title-xl span")
        if not tag:
            tag = soup.find("h1")
        return self._clean_text(tag.get_text()) if tag else "Категория"

    def _make_unique_sheet_name(self, title: str) -> str:
        """Генерирует уникальное имя листа длиной до 31 символа по правилам Excel."""
        safe = re.sub(r"[:\\/?*\[\]]", " ", title).strip()
        if not safe:
            safe = "Sheet"

        base = safe[:31]
        count = self._sheet_name_counts.get(base, 0)

        if count:
            while True:
                count += 1
                suffix = f"_{count}"
                candidate = (base[: 31 - len(suffix)]) + suffix
                if candidate not in self._sheet_name_counts:
                    safe = candidate
                    break
        else:
            safe = base

        self._sheet_name_counts[safe] = 1
        return safe

    @staticmethod
    def _card_to_row(card: ProductCardBase) -> dict[str, str]:
        """Преобразует карточку в строку табличного отчёта с фиксированными колонками."""
        return {
            "Название": card.name,
            "Бренд": card.brand,
            "Цена": card.price,
            "Ссылка": card.product_url,
        }

    @staticmethod
    def _full_card_to_row(card: ProductCardFull) -> dict[str, str]:
        """Преобразует расширенную карточку в строку табличного отчёта."""
        row = ProductListParser._card_to_row(card)
        row.update(dict(card.features))
        return row

    def run(self) -> tuple[list[dict[str, str]], CategoryParseStats]:
        """Выполняет обход категорий и возвращает накопленные строки и статистику."""
        all_products: list[dict[str, str]] = []
        failed_links: list[str] = []
        success_categories = 0

        for base_url in self.links:
            category_rows: list[dict[str, str]] = []
            first_title: str | None = None
            success_any_page = False

            for page in self.parser._iter_paginated_pages(base_url):
                if first_title is None:
                    first_title = self._extract_page_title(page.soup)

                if self.mode is ParserMode.FULLTABLE:
                    products = self._category_page_parser.parse_full(page.soup)
                    rows = [self._full_card_to_row(item) for item in products]
                else:
                    products = self._category_page_parser.parse_basic(page.soup)
                    rows = [self._card_to_row(item) for item in products]

                self.logger.info(
                    f"  └— товаров на странице {page.page_index}: {len(rows)}",
                    TraceContext(
                        operation="parse_category_page",
                        url=base_url,
                        page=page.page_index,
                        parser_mode=self.mode.value,
                    ),
                )
                category_rows.extend(rows)
                all_products.extend(rows)
                success_any_page = True

            if success_any_page:
                title_for_sheet = first_title or base_url
                sheet_name = self._make_unique_sheet_name(title_for_sheet)
                self._sheet_data[sheet_name] = category_rows
                success_categories += 1
            else:
                failed_links.append(base_url)

        stats = CategoryParseStats(
            total_categories=len(self.links),
            success_categories=success_categories,
            failed_categories=len(failed_links),
            failed_links=tuple(failed_links),
            total_products=len(all_products),
            parser_mode=self.mode,
        )
        self.logger.info(
            (
                "Итого | режим: "
                f"{stats.parser_mode.value} | категорий: {stats.total_categories} | "
                f"успех: {stats.success_categories} | ошибок: {stats.failed_categories} | "
                f"товаров: {stats.total_products}"
            ),
            TraceContext(operation="run_summary", parser_mode=stats.parser_mode.value),
        )
        return all_products, stats

    def save_results(self) -> bytes:
        """Сериализует накопленные листы в Excel и возвращает байты файла."""
        return ExcelExporter.save_sheets(self._sheet_data, self.output_file)
