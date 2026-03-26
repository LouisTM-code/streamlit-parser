"""Link extraction infrastructure for category pages."""

from __future__ import annotations

import logging
from typing import List

from bs4 import BeautifulSoup


class LinkExtractor:
    """Category product-link extraction role.

    Responsibility:
        - collect product links from supported category selectors;
        - deduplicate links while preserving first-seen order.

    Boundaries:
        - does not perform HTTP requests;
        - does not paginate category pages.

    Interactions:
        - invoked by ``WebParser`` during category traversal.
    """

    def extract_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract absolute product links using two existing selectors."""
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
