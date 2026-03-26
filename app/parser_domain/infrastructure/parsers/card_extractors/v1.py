"""V1 product card extractor."""

from __future__ import annotations

from typing import Callable, Dict

from bs4 import Tag


class CardExtractorV1:
    """Extractor role for v1 mobile-category card markup.

    Responsibility:
        - parse fixed product fields from ``cnc-product-categories-mob-card`` blocks.

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

    def extract(self, row: Tag) -> Dict[str, str] | None:
        """Extract fixed data fields from v1 card row."""
        name_td = row.find("div", class_="cnc-product-categories-mob-card__header")
        if not name_td or not name_td.a:
            return None

        name = self._clean_text(name_td.a.get_text())

        brand_td = name_td.find(
            "span",
            class_="cnc-product-categories-mob-card__brand",
        )
        brand = self._clean_text(brand_td.get_text()) if brand_td else "Н/Д"

        article_span = row.find(
            "span",
            class_="cnc-product-categories-mob-card__sku",
        )
        article_block = None
        if article_span:
            article_block = article_span.select_one("span.cnc-sku__product-code")

        article = (
            f"119-{self._clean_text(article_block.get_text())}"
            if article_block
            else "Н/Д"
        )

        price_span = row.find(
            "div",
            class_="cnc-product-categories-mob-card__current-price",
        )
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        avail_span = row.find(
            "span",
            class_="cnc-product-amount__product-quantity",
        )
        if not avail_span:
            avail_span = row.find("span", class_="cnc-product-amount__status")

        availability = self._clean_text(avail_span.get_text()) if avail_span else "Н/Д"

        return {
            "Название": name,
            "Бренд": brand,
            "Артикул": article,
            "Цена": price,
            "Наличие": availability,
        }
