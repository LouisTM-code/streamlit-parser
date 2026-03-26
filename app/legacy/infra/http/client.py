"""HTTP client infrastructure for parser modules."""

from __future__ import annotations

import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup


class HttpClient:
    """HTTP transport role for HTML retrieval.

    Responsibility:
        - create and own a persistent ``requests.Session`` with parser headers;
        - execute GET requests and convert HTML to ``BeautifulSoup``.

    Boundaries:
        - does not parse domain fields or product structures;
        - does not implement pagination or link extraction policies.

    Interactions:
        - consumed by ``WebParser`` and other parsing roles as a soup provider.
    """

    def __init__(self) -> None:
        """Initialize session state and default headers for scraping."""
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        self.session.headers.update(self.headers)

    def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch URL and return parsed HTML tree or ``None`` on request errors."""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException as error:
            logging.error(f"Ошибка запроса {url}: {str(error)}")
            return None
