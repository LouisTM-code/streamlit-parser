"""V2 product card extractor."""

from __future__ import annotations

from typing import Callable, Dict

from bs4 import Tag


class CardExtractorV2:
    """Extractor role for v2 short-list product markup.

    Responsibility:
        - parse fixed product fields from ``cnc-short-list-product`` blocks.

    Boundaries:
        - does not paginate category pages;
        - does not save parsed results.

    Interactions:
        - receives text/price cleaning callables from orchestration layer;
        - used by ``CategoryPageParser`` in basic and full parsing modes.
    """

    def __init__(
        self,
        clean_text: Callable[[str], str],
        clean_price: Callable[[str], str],
    ) -> None:
        """Store normalization dependencies for extracted values."""
        self._clean_text = clean_text
        self._clean_price = clean_price

    def extract(self, name_div: Tag) -> Dict[str, str] | None:
        """Extract fixed data fields from v2 card block."""
        if not name_div or not name_div.a:
            return None

        name_place = name_div.find_next(
            "div",
            class_="cnc-short-list-product__info",
        )
        name = self._clean_text(name_place.a.get_text())

        brand_block = name_div.find_next(
            "div",
            class_="cnc-short-list-product__short-info",
        )
        brand = "Н/Д"
        article = "Н/Д"
        if brand_block:
            brand_link = brand_block.select_one(
                "div.cnc-short-list-product__brand-name"
            )
            if brand_link:
                brand = self._clean_text(brand_link.get_text())

            span_article = brand_block.find("span", class_="cnc-sku__product-code")
            if span_article:
                article = f"119-{self._clean_text(span_article.get_text())}"

        price_span = name_div.find_next("span", class_="ty-price")
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        avail_p = name_div.find_next(
            "span",
            class_="cnc-product-amount__status",
        )
        availability = "Н/Д"
        if avail_p:
            avail_span = avail_p.find("span")
            if avail_span:
                availability = self._clean_text(avail_span.get_text())

        return {
            "Название": name,
            "Бренд": brand,
            "Артикул": article,
            "Цена": price,
            "Наличие": availability,
        }
