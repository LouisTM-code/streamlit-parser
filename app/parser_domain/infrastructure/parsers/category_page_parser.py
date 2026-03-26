"""Парсер HTML-страницы категории в режимах `basic` и `fulltable`.

Роль и ответственность:
    - агрегирует результаты экстракторов карточек разных версий разметки;
    - в полном режиме объединяет базовые поля с характеристиками.

Границы:
    - не управляет пагинацией и сетевыми запросами;
    - не сохраняет итог в файл.

Взаимодействие с другими ролями:
    - принимает `CardExtractorV1`, `CardExtractorV2` и `FeatureExtractor` через DI.
"""

from __future__ import annotations

from typing import Any, Dict, List

from bs4 import BeautifulSoup, Tag

from parser_domain.infrastructure.parsers.card_extractors.v1 import CardExtractorV1
from parser_domain.infrastructure.parsers.card_extractors.v2 import CardExtractorV2
from parser_domain.infrastructure.parsers.feature_extractor import FeatureExtractor


class CategoryPageParser:
    """Координатор извлечения строк товаров из одной DOM-страницы категории."""

    def __init__(
        self,
        extractor_v1: CardExtractorV1,
        extractor_v2: CardExtractorV2,
        feature_extractor: FeatureExtractor,
    ) -> None:
        """Регистрирует стратегии извлечения данных для разных вариантов карточек."""
        self._extractor_v1 = extractor_v1
        self._extractor_v2 = extractor_v2
        self._feature_extractor = feature_extractor

    def parse_basic(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Возвращает фиксированный набор колонок, сохраняя обратную совместимость старого формата."""
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
        """Возвращает расширенные строки карточек с объединёнными характеристиками."""
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
        """Собирает одну строку fulltable: базовые поля карточки + динамические характеристики."""
        base_data: Dict[str, Any] | None = self._extractor_v1.extract(row)
        if not base_data:
            base_data = self._extractor_v2.extract(row)

        if not base_data:
            base_data = {}

        features = self._feature_extractor.extract(row)
        if features:
            base_data.update(features)

        return base_data or None
