import logging
from typing import Optional

from bs4 import BeautifulSoup

from parser_domain.infrastructure.http_client.client import HttpClient
from parser_domain.infrastructure.logging.trace_context import TraceContext
from parser_domain.infrastructure.logging.tracing_logger import TracingLogger
from parser_domain.infrastructure.parsers.link_extractor import LinkExtractor
from parser_domain.infrastructure.parsers.pagination import CategoryPaginator
from parser_domain.infrastructure.parsers.product_details_extractor import ProductDetailsExtractor
from parser_domain.types import CategoryPageRef, ProductDetails


class WebParser:
    """Доменный фасад парсинга HTML-страниц каталога и карточек товара.

    Роль и ответственность:
        - объединяет инфраструктурные экстракторы ссылок, карточек и пагинации;
        - предоставляет стабильный API для use-case слоя.

    Границы:
        - не формирует UI-результаты и не экспортирует данные в файлы;
        - не управляет пользовательскими сценариями запуска.

    Взаимодействие с другими ролями:
        - делегирует загрузку `HttpClient`, извлечение `LinkExtractor`/`ProductDetailsExtractor`,
          переходы по страницам `CategoryPaginator`.
    """

    def __init__(self, http_client: Optional[HttpClient] = None):
        """Инициализирует инфраструктурные зависимости парсера домена."""
        self.setup_logging()
        self._logger = TracingLogger(logging.getLogger("WebParser"))
        self._http_client = http_client or HttpClient()
        self._link_extractor = LinkExtractor()
        self._product_details_extractor = ProductDetailsExtractor(self.clean_text)
        self._paginator = CategoryPaginator(self._http_client)

    @staticmethod
    def setup_logging():
        """Конфигурирует стандартный вывод логов для операций парсинга."""
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
        """Загружает страницу и возвращает `BeautifulSoup` либо `None` при ошибке запроса."""
        return self._http_client.get_soup(url)

    def parse_links(self, soup: BeautifulSoup) -> list[str]:
        """Собирает ссылки на товары категории через выделенную роль экстрактора."""
        return self._link_extractor.extract_links(soup)

    def parse_product(self, soup: BeautifulSoup) -> ProductDetails:
        """Собирает детали товара через выделенную роль экстрактора."""
        return self._product_details_extractor.extract(soup)

    def _normalize_to_first_page(self, url: str) -> str:
        """Нормализует URL категории к первой странице через выделенный paginator."""
        return self._paginator.normalize_to_first_page(url)

    def _iter_paginated_pages(self, base_url: str):
        """Проксирует итератор пагинации в виде `CategoryPageRef` без модификаций."""
        return self._paginator.iter_paginated_pages(base_url)

    def iter_category_product_links(self, base_url: str) -> list[str]:
        """Собирает все уникальные ссылки на товары со страниц пагинации категории."""
        all_links: list[str] = []
        seen: set[str] = set()

        for page in self._iter_paginated_pages(base_url):
            with self._logger.trace_scope(TraceContext(page=page.page_index)):
                page_links = self.parse_links(page.soup)
                self._logger.info(
                    f"  └— ссылок на странице {page.page_index}: {len(page_links)}"
                )
                for href in page_links:
                    if href not in seen:
                        seen.add(href)
                        all_links.append(href)

        self._logger.info(f"Итого ссылок в категории: {len(all_links)}")
        return all_links
