"""Извлечение полей детальной страницы товара.

Роль и ответственность:
    - парсит базовые атрибуты товара (название, цена, описание, артикул);
    - дополняет результат характеристиками из секции features.

Границы:
    - не загружает страницу по сети;
    - не выполняет постобработку в табличный формат.

Взаимодействие с другими ролями:
    - вызывается фасадом `WebParser`; нормализация текста передаётся извне.
"""

from __future__ import annotations

import logging
from typing import Callable

from bs4 import BeautifulSoup

from parser_domain.types import ProductDetails


class ProductDetailsExtractor:
    """Экстрактор структурированных данных из страницы товара."""

    def __init__(self, text_cleaner: Callable[[str], str]) -> None:
        """Сохраняет внешнюю стратегию очистки текста для всех распарсенных полей."""
        self._clean_text = text_cleaner

    def extract(self, soup: BeautifulSoup) -> ProductDetails:
        """Публичный метод извлечения; делегирует в `parse_product` для совместимости API."""
        return self.parse_product(soup)

    def parse_features(self, soup: BeautifulSoup) -> dict[str, str]:
        """Парсит строки характеристик товара из секции характеристик."""
        features: dict[str, str] = {}
        try:
            for feature_div in soup.find_all("div", class_="cnc-product-features__feature"):
                label = feature_div.find("span", class_="cnc-product-features__label")
                if not label:
                    continue

                feature_name = self._clean_text(label.text).rstrip(":")
                value_div = feature_div.find("div")

                if not feature_name or not value_div:
                    continue

                if value_div.find("a"):
                    value = self._clean_text(value_div.find("a").text)
                elif value_div.find("ul"):
                    items = [self._clean_text(li.text) for li in value_div.find_all("li")]
                    value = ", ".join(items)
                else:
                    value = self._clean_text(value_div.text.strip())

                features[feature_name] = value
        except Exception as error:  # noqa: BLE001
            logging.error("Ошибка парсинга характеристик: %s", str(error))

        return features

    def parse_product(self, soup: BeautifulSoup) -> ProductDetails:
        """Парсит базовые поля товара и возвращает `ProductDetails`."""
        title = "Н/Д"
        price = "Н/Д"
        description = "Н/Д"
        article = "Н/Д"
        brand = "Н/Д"
        availability = "Н/Д"

        try:
            title_tag = soup.find("h1", class_="cnc-product-detail__title")
            if title_tag:
                title = self._clean_text(title_tag.text)

            price_div = soup.find("div", class_="cnc-product-detail__price-actual")
            if price_div:
                price_tag = price_div.find("span", class_="ty-price-num")
                if price_tag:
                    price = self._clean_text(price_tag.text)

            description_div = soup.find("div", class_="cnc-product-description__left")
            if description_div:
                paragraphs = description_div.find_all(
                    "p", class_=lambda value: value != "cnc-product-description__notice"
                )
                description = " ".join(
                    self._clean_text(item.text) for item in paragraphs if item.text.strip()
                )

            sku = soup.find("span", class_="g-js-text-for-copy cnc-product-detail__product-code")
            if sku:
                article = self._clean_text(sku.text)

            brand_tag = soup.select_one("a.cnc-product-detail__brand")
            if brand_tag:
                brand = self._clean_text(brand_tag.text)

            availability_tag = soup.select_one("span.cnc-product-amount__status")
            if availability_tag:
                availability = self._clean_text(availability_tag.text)
        except Exception as error:  # noqa: BLE001
            logging.error("Ошибка парсинга товара: %s", str(error))

        features = self.parse_features(soup)
        logging.info("Извлечено %d характеристик", len(features))
        return ProductDetails(
            title=title,
            article=article,
            brand=brand,
            price=price,
            availability=availability,
            description=description,
            features=features,
        )
