import logging
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from parser_domain.infrastructure.http_client.client import HttpClient
from parser_domain.infrastructure.parsers.link_extractor import LinkExtractor
from parser_domain.infrastructure.parsers.pagination import CategoryPaginator
from parser_domain.infrastructure.parsers.product_details_extractor import ProductDetailsExtractor


class WebParser:
    """Facade parser that orchestrates HTTP, pagination and extraction roles.

    Responsibility:
        - configure logging and compose infrastructure collaborators;
        - provide backward-compatible parser API used by UI and parser domain modules.

    Boundaries:
        - does not implement low-level HTTP, pagination and link/product extraction logic.

    Interactions:
        - delegates soup loading to ``HttpClient``;
        - delegates category links to ``LinkExtractor``;
        - delegates product details to ``ProductDetailsExtractor``;
        - delegates page traversal to ``CategoryPaginator``.
    """

    def __init__(self, http_client: Optional[HttpClient] = None):
        """Initialize parser facade with injectable HTTP client dependency."""
        self.setup_logging()
        self._http_client = http_client or HttpClient()
        self._link_extractor = LinkExtractor()
        self._product_details_extractor = ProductDetailsExtractor(self.clean_text)
        self._paginator = CategoryPaginator(self._http_client)

    @staticmethod
    def setup_logging():
        """Configure base logging handlers for parser domain parser execution."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )

    @staticmethod
    def clean_text(text: str) -> str:
        """Normalize text spacing and non-breaking spaces for parsed values."""
        return " ".join(text.replace("\xa0", " ").strip().split())

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Backward-compatible soup loader delegated to ``HttpClient``."""
        return self._http_client.get_soup(url)

    def parse_links(self, soup: BeautifulSoup) -> List[str]:
        """Collect category product links through dedicated extractor role."""
        return self._link_extractor.extract_links(soup)

    def parse_product(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Collect product details through dedicated extractor role."""
        return self._product_details_extractor.extract(soup)

    def _normalize_to_first_page(self, url: str) -> str:
        """Backward-compatible access to category URL normalization logic."""
        return self._paginator.normalize_to_first_page(url)

    def _iter_paginated_pages(self, base_url: str):
        """Backward-compatible iterator delegated to paginator role."""
        return self._paginator.iter_paginated_pages(base_url)

    def iter_category_product_links(self, base_url: str) -> List[str]:
        """Collect all unique product links from paginated category pages."""
        all_links: List[str] = []
        seen = set()

        for page_index, page_url, soup in self._iter_paginated_pages(base_url):
            page_links = self.parse_links(soup)
            logging.info(f"  └— ссылок на странице {page_index}: {len(page_links)}")
            for href in page_links:
                if href not in seen:
                    seen.add(href)
                    all_links.append(href)

        logging.info(f"Итого ссылок в категории: {len(all_links)}")
        return all_links
