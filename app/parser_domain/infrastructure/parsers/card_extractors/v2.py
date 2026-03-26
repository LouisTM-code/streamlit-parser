"""Извлечение фиксированных полей из карточки каталога формата V2.

Роль и ответственность:
    - считывает имя, бренд, цену и ссылку товара из DOM-блока V2;
    - применяет внешние нормализаторы текста и цены.

Границы:
    - не извлекает характеристики из feature-блоков;
    - не занимается обходом страниц.

Взаимодействие с другими ролями:
    - подключается в `CategoryPageParser` как fallback для альтернативной разметки.
"""

from __future__ import annotations

from typing import Callable

from bs4 import Tag

from parser_domain.types import ProductCardBase


class CardExtractorV2:
    """Стратегия извлечения базовых колонок из карточки версии V2."""

    def __init__(
        self,
        clean_text: Callable[[str], str],
        clean_price: Callable[[str], str],
    ) -> None:
        """Сохраняет зависимости нормализации для извлечённых значений."""
        self._clean_text = clean_text
        self._clean_price = clean_price

    def extract(self, name_div: Tag) -> ProductCardBase | None:
        """Извлекает базовую карточку `ProductCardBase` из блока v2."""
        if not name_div or not name_div.a:
            return None

        name_place = name_div.find_next(
            "div",
            class_="cnc-short-list-product__info",
        )
        if not name_place or not name_place.a:
            return None
        name = self._clean_text(name_place.a.get_text())

        product_url = str(name_div.a.get("href", "")).strip()
        if not product_url:
            return None

        brand_block = name_div.find_next(
            "div",
            class_="cnc-short-list-product__short-info",
        )
        brand = "Н/Д"
        if brand_block:
            brand_link = brand_block.select_one(
                "div.cnc-short-list-product__brand-name"
            )
            if brand_link:
                brand = self._clean_text(brand_link.get_text())

        price_span = name_div.find_next("span", class_="ty-price")
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        return ProductCardBase(
            name=name,
            brand=brand,
            price=price,
            product_url=product_url,
        )
