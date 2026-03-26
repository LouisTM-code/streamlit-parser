"""Инфраструктура извлечения ссылок со страниц категории."""

from __future__ import annotations

import logging
from typing import List

from bs4 import BeautifulSoup


class LinkExtractor:
    """Класс LinkExtractor.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

    def extract_links(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает абсолютные ссылки на товары двумя существующими селекторами."""
        links = []

        for link in soup.select("div.cnc-product-categories-mob-card__header a[href]"):
            href = link.get("href", "")
            if href.startswith("http"):
                links.append(href)
                logging.debug(f"Найдена ссылка (вариант 1): {href}")

        for link in soup.select("div.cnc-short-list-product a[href]"):
            href = link.get("href", "")
            if href.startswith("http"):
                links.append(href)
                logging.debug(f"Найдена ссылка (вариант 2): {href}")

        seen = set()
        return [item for item in links if not (item in seen or seen.add(item))]
