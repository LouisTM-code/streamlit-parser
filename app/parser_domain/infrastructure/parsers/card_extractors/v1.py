"""Извлечение фиксированных полей из карточки каталога формата V1.

Роль и ответственность:
    - считывает имя, бренд, цену и ссылку товара из DOM-блока V1;
    - применяет переданные функции нормализации текста и цены.

Границы:
    - не извлекает расширенные характеристики;
    - не выполняет сетевые операции.

Взаимодействие с другими ролями:
    - используется `CategoryPageParser` как стратегия парсинга V1-разметки.
"""

from __future__ import annotations

from typing import Callable

from bs4 import Tag

from parser_domain.types import ProductCardBase


class CardExtractorV1:
    """Стратегия извлечения базовых колонок из карточки версии V1."""

    def __init__(
        self,
        clean_text: Callable[[str], str],
        clean_price: Callable[[str], str],
    ) -> None:
        """Сохраняет зависимости нормализации для извлечённых значений."""
        self._clean_text = clean_text
        self._clean_price = clean_price

    def extract(self, row: Tag) -> ProductCardBase | None:
        """Извлекает базовую карточку `ProductCardBase` из строки v1."""
        name_td = row.find("div", class_="cnc-product-categories-mob-card__header")
        if not name_td or not name_td.a:
            return None

        name = self._clean_text(name_td.a.get_text())
        product_url = str(name_td.a.get("href", "")).strip()
        if not product_url:
            return None

        brand_td = name_td.find(
            "span",
            class_="cnc-product-categories-mob-card__brand",
        )
        brand = self._clean_text(brand_td.get_text()) if brand_td else "Н/Д"

        price_span = row.find(
            "div",
            class_="cnc-product-categories-mob-card__current-price",
        )
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        return ProductCardBase(
            name=name,
            brand=brand,
            price=price,
            product_url=product_url,
        )
