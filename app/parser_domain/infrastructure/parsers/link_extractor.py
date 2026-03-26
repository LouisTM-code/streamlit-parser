"""Извлечение ссылок на товары из HTML категории.

Роль и ответственность:
    - считывает ссылки из поддерживаемых DOM-паттернов каталога;
    - возвращает дедуплицированный список абсолютных URL.

Границы:
    - не загружает страницы по сети;
    - не извлекает детальные поля товаров.

Взаимодействие с другими ролями:
    - используется фасадом `WebParser` в сценариях поиска карточек.
"""

from __future__ import annotations

import logging
from typing import List

from bs4 import BeautifulSoup


class LinkExtractor:
    """Компонент извлечения ссылок на карточки товаров из страницы категории."""

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
