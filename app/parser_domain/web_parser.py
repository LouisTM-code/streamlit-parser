import logging
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from parser_domain.infrastructure.http_client.client import HttpClient
from parser_domain.infrastructure.parsers.link_extractor import LinkExtractor
from parser_domain.infrastructure.parsers.pagination import CategoryPaginator
from parser_domain.infrastructure.parsers.product_details_extractor import ProductDetailsExtractor


class WebParser:
    """Класс WebParser.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

    def __init__(self, http_client: Optional[HttpClient] = None):
        """Выполняет операцию роли «__init__»."""
        self.setup_logging()
        self._http_client = http_client or HttpClient()
        self._link_extractor = LinkExtractor()
        self._product_details_extractor = ProductDetailsExtractor(self.clean_text)
        self._paginator = CategoryPaginator(self._http_client)

    @staticmethod
    def setup_logging():
        """Настраивает базовые обработчики логирования для выполнения парсера домена."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )

    @staticmethod
    def clean_text(text: str) -> str:
        """Нормализует пробелы и неразрывные пробелы в распарсенных значениях."""
        return " ".join(text.replace("\xa0", " ").strip().split())

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Выполняет операцию роли «get_page»."""
        return self._http_client.get_soup(url)

    def parse_links(self, soup: BeautifulSoup) -> List[str]:
        """Собирает ссылки на товары категории через выделенную роль экстрактора."""
        return self._link_extractor.extract_links(soup)

    def parse_product(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Собирает детали товара через выделенную роль экстрактора."""
        return self._product_details_extractor.extract(soup)

    def _normalize_to_first_page(self, url: str) -> str:
        """Выполняет операцию роли «_normalize_to_first_page»."""
        return self._paginator.normalize_to_first_page(url)

    def _iter_paginated_pages(self, base_url: str):
        """Предоставляет совместимый итератор, делегированный роли пагинатора."""
        return self._paginator.iter_paginated_pages(base_url)

    def iter_category_product_links(self, base_url: str) -> List[str]:
        """Собирает все уникальные ссылки на товары со страниц пагинации категории."""
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
