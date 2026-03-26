"""Инфраструктура парсинга страниц категории."""

from __future__ import annotations

from typing import Any, Dict, List

from bs4 import BeautifulSoup, Tag

from parser_domain.infrastructure.parsers.card_extractors.v1 import CardExtractorV1
from parser_domain.infrastructure.parsers.card_extractors.v2 import CardExtractorV2
from parser_domain.infrastructure.parsers.feature_extractor import FeatureExtractor


class CategoryPageParser:
    """Класс CategoryPageParser.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

    def __init__(
        self,
        extractor_v1: CardExtractorV1,
        extractor_v2: CardExtractorV2,
        feature_extractor: FeatureExtractor,
    ) -> None:
        """Сохраняет зависимости экстракторов для парсинга страницы категории."""
        self._extractor_v1 = extractor_v1
        self._extractor_v2 = extractor_v2
        self._feature_extractor = feature_extractor

    def parse_basic(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Парсит страницу категории в историческом режиме фиксированных колонок."""
        products: List[Dict[str, str]] = []

        rows_v1 = soup.select("div.cnc-product-categories-mob-card")
        for row in rows_v1:
            data = self._extractor_v1.extract(row)
            if data:
                products.append(data)

        if products:
            return products

        for row in soup.select("div.cnc-short-list-product"):
            data = self._extractor_v2.extract(row)
            if data:
                products.append(data)

        return products

    def parse_full(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Парсит страницу категории в режиме полной таблицы."""
        products: List[Dict[str, Any]] = []

        for row in soup.select("div.cnc-product-categories-mob-card"):
            data = self._extract_row_full(row)
            if data:
                products.append(data)

        for row in soup.select("div.cnc-short-list-product"):
            data = self._extract_row_full(row)
            if data:
                products.append(data)

        return products

    def _extract_row_full(self, row: Tag) -> Dict[str, Any] | None:
        """Извлекает полные данные строки без изменения исторической базовой логики."""
        base_data: Dict[str, Any] | None = self._extractor_v1.extract(row)
        if not base_data:
            base_data = self._extractor_v2.extract(row)

        if not base_data:
            base_data = {}

        features = self._feature_extractor.extract(row)
        if features:
            base_data.update(features)

        return base_data or None
