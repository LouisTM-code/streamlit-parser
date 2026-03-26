"""URL normalization infrastructure."""

from __future__ import annotations

import re
from typing import List
from urllib.parse import urlparse, urlunparse


class URLNormalizer:
    """URL normalization and validation role for category links.

    Responsibility:
        - normalize raw category links entered by users;
        - validate URL format and keep query parameters unchanged.

    Boundaries:
        - does not fetch pages from network;
        - does not implement pagination traversal.

    Interactions:
        - used by ``ProductListParser`` before parsing pipeline starts.
    """

    @staticmethod
    def normalize_links(raw_links: List[str]) -> List[str]:
        """Clean user-provided links and preserve input order for unique values."""
        cleaned: List[str] = []
        seen: set[str] = set()

        for item in raw_links:
            link = item.strip()
            if not link:
                continue

            if not re.match(r"^https?://", link, flags=re.IGNORECASE):
                link = "http://" + link

            link = link.rstrip("/")
            if link not in seen:
                cleaned.append(link)
                seen.add(link)

        return cleaned

    @staticmethod
    def validate_links(links: List[str]) -> List[str]:
        """Validate links and return normalized URL strings without query rewriting."""
        if not links:
            raise ValueError(
                "Список ссылок пуст или содержит только невалидные элементы."
            )

        url_re = re.compile(r"^https?://[\w\-.:/?#=&%~+]+$", re.IGNORECASE)
        invalid: List[str] = []
        processed: List[str] = []

        for url in links:
            if not url_re.match(url):
                invalid.append(url)
                continue

            parsed = urlparse(url)
            processed.append(urlunparse(parsed))

        if invalid:
            raise ValueError("Обнаружены некорректные URL: " + ", ".join(invalid))

        return processed
