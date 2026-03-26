from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup

from parser_domain.web_parser import WebParser
from parser_domain.infrastructure.exporters.excel_exporter import ExcelExporter
from parser_domain.infrastructure.parsers.category_page_parser import CategoryPageParser
from parser_domain.infrastructure.parsers.card_extractors.v1 import CardExtractorV1
from parser_domain.infrastructure.parsers.card_extractors.v2 import CardExtractorV2
from parser_domain.infrastructure.parsers.feature_extractor import FeatureExtractor
from parser_domain.infrastructure.url_tools.url_normalizer import URLNormalizer

__all__ = ["ProductListParser"]


class ProductListParser:
    """Класс для табличного/каталожного парсинга страниц категорий."""

    def __init__(
        self,
        links: List[str],
        output_file: str = "product_list.xlsx",
        base_parser: WebParser | None = None,
        mode: str = "basic",
    ) -> None:
        """Инициализирует парсер списка товаров."""
        self.logger: logging.Logger = self._configure_logger()
        self.parser: WebParser = base_parser or WebParser()
        self.output_file: str = output_file

        allowed_modes = {"basic", "fulltable"}
        if mode not in allowed_modes:
            raise ValueError(
                f"Неизвестный режим '{mode}'. Допустимо: {', '.join(sorted(allowed_modes))}."
            )
        self.mode: str = mode

        self._url_normalizer = URLNormalizer()
        self.links: List[str] = self._url_normalizer.normalize_links(links)
        self.links = self._url_normalizer.validate_links(self.links)
        self.logger.info("Принято %d ссылок, режим: %s", len(self.links), self.mode)

        self._sheet_name_counts: Dict[str, int] = {}
        self._sheet_data: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()

        self._category_page_parser = CategoryPageParser(
            extractor_v1=CardExtractorV1(self._clean_text, self._clean_price),
            extractor_v2=CardExtractorV2(self._clean_text, self._clean_price),
            feature_extractor=FeatureExtractor(self._clean_text),
        )

    @staticmethod
    def _configure_logger() -> logging.Logger:
        """Настраивает изолированный логгер класса ProductListParser."""
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
        """Возвращает заголовок категории для имени листа Excel."""
        tag = soup.select_one("h1.cnc-title-xl span")
        if not tag:
            tag = soup.find("h1")
        return self._clean_text(tag.get_text()) if tag else "Категория"

    def _make_unique_sheet_name(self, title: str) -> str:
        """Создаёт уникальное и безопасное имя листа Excel."""
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

    def run(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Основной цикл обхода всех входных ссылок категорий."""
        all_products: List[Dict[str, Any]] = []
        failed_links: List[str] = []
        success_categories = 0

        for base_url in self.links:
            category_rows: List[Dict[str, Any]] = []
            first_title: str | None = None
            success_any_page = False

            for page_index, page_url, soup in self.parser._iter_paginated_pages(base_url):
                if first_title is None:
                    first_title = self._extract_page_title(soup)

                if self.mode == "fulltable":
                    products = self._category_page_parser.parse_full(soup)
                else:
                    products = self._category_page_parser.parse_basic(soup)

                self.logger.info(
                    "  └— товаров на странице %d: %d",
                    page_index,
                    len(products),
                )
                category_rows.extend(products)
                all_products.extend(products)
                success_any_page = True

            if success_any_page:
                title_for_sheet = first_title or base_url
                sheet_name = self._make_unique_sheet_name(title_for_sheet)
                self._sheet_data[sheet_name] = category_rows
                success_categories += 1
            else:
                failed_links.append(base_url)

        stats = {
            "total": len(self.links),
            "success": success_categories,
            "failed": len(failed_links),
            "failed_links": failed_links,
            "total_products": len(all_products),
            "mode": self.mode,
        }
        self.logger.info(
            "Итого | режим: %(mode)s | категорий: %(total)d | "
            "успех: %(success)d | ошибок: %(failed)d | товаров: %(total_products)d",
            stats,
        )
        return all_products, stats

    def save_results(self) -> bytes:
        """Сохраняет результаты в Excel через инфраструктурный экспортёр."""
        return ExcelExporter.save_sheets(self._sheet_data, self.output_file)
