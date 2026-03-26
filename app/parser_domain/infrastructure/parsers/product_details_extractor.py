"""Инфраструктура извлечения деталей товара."""

from __future__ import annotations

import logging
from typing import Callable, Dict

from bs4 import BeautifulSoup


class ProductDetailsExtractor:
    """Класс ProductDetailsExtractor.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

    def __init__(self, text_cleaner: Callable[[str], str]) -> None:
        """Сохраняет внешнюю стратегию очистки текста для всех распарсенных полей."""
        self._clean_text = text_cleaner

    def extract(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Выполняет операцию роли «extract»."""
        return self.parse_product(soup)

    def parse_features(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Парсит строки характеристик товара из секции характеристик."""
        features: Dict[str, str] = {}
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
            logging.error(f"Ошибка парсинга характеристик: {str(error)}")

        return features

    def parse_product(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Парсит базовые поля товара и объединяет их с извлечёнными характеристиками."""
        product_data = {
            "Товар": "Н/Д",
            "Цена": "Н/Д",
            "Описание": "Н/Д",
            "Артикул": "Н/Д",
        }

        try:
            title = soup.find("h1", class_="cnc-product-detail__title")
            if title:
                product_data["Товар"] = self._clean_text(title.text)

            price_div = soup.find("div", class_="cnc-product-detail__price-actual")
            if price_div:
                price = price_div.find("span", class_="ty-price-num")
                if price:
                    product_data["Цена"] = self._clean_text(price.text)

            description_div = soup.find("div", class_="cnc-product-description__left")
            if description_div:
                paragraphs = description_div.find_all(
                    "p", class_=lambda value: value != "cnc-product-description__notice"
                )
                product_data["Описание"] = " ".join(
                    self._clean_text(item.text) for item in paragraphs if item.text.strip()
                )

            sku = soup.find("span", class_="g-js-text-for-copy cnc-product-detail__product-code")
            if sku:
                product_data["Артикул"] = self._clean_text(sku.text)

            product_data.update(self.parse_features(soup))
            logging.info(f"Извлечено {len(product_data) - 4} характеристик")
        except Exception as error:  # noqa: BLE001
            logging.error(f"Ошибка парсинга товара: {str(error)}")

        return product_data
