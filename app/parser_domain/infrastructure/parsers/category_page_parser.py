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

from typing import Mapping

from bs4 import BeautifulSoup, Tag

from parser_domain.infrastructure.parsers.card_extractors.v1 import CardExtractorV1
from parser_domain.infrastructure.parsers.card_extractors.v2 import CardExtractorV2
from parser_domain.infrastructure.parsers.feature_extractor import FeatureExtractor
from parser_domain.types import ProductCardBase, ProductCardFull


class CategoryPageParser:
    """Координатор извлечения карточек товаров из одной DOM-страницы категории."""

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

    def parse_basic(self, soup: BeautifulSoup) -> list[ProductCardBase]:
        """Возвращает базовые карточки `ProductCardBase` для страницы категории."""
        products: list[ProductCardBase] = []

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

    def parse_full(self, soup: BeautifulSoup) -> list[ProductCardFull]:
        """Возвращает расширенные карточки `ProductCardFull` с характеристиками."""
        products: list[ProductCardFull] = []

        for row in soup.select("div.cnc-product-categories-mob-card"):
            data = self._extract_row_full(row)
            if data:
                products.append(data)

        for row in soup.select("div.cnc-short-list-product"):
            data = self._extract_row_full(row)
            if data:
                products.append(data)

        return products

    def _extract_row_full(self, row: Tag) -> ProductCardFull | None:
        """Собирает одну карточку `ProductCardFull` из базовых полей и features."""
        base_data = self._extractor_v1.extract(row)
        if not base_data:
            base_data = self._extractor_v2.extract(row)
        if not base_data:
            return None

        features: Mapping[str, str] = self._feature_extractor.extract(row)
        return ProductCardFull(
            name=base_data.name,
            brand=base_data.brand,
            price=base_data.price,
            product_url=base_data.product_url,
            features=dict(features),
        )
