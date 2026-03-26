"""Обход пагинированных страниц категории.

Роль и ответственность:
    - нормализует URL категории к первой странице и стандартному размеру выдачи;
    - итерирует страницы до исчезновения блока «показать ещё».

Границы:
    - не извлекает ссылки/товары из DOM;
    - не хранит состояние между разными категориями.

Взаимодействие с другими ролями:
    - использует `HttpClient` для загрузки страниц;
    - вызывается из `WebParser` и `ProductListParser`.
"""

from __future__ import annotations

import logging
import re
from typing import Generator, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from parser_domain.infrastructure.http_client.client import HttpClient


class CategoryPaginator:
    """Итератор страниц категории с пошаговой выдачей `(index, url, soup)`."""

    def __init__(self, http_client: HttpClient) -> None:
        """Сохраняет HTTP-клиент, используемый для всех запросов пагинации."""
        self._http_client = http_client

    @staticmethod
    def normalize_to_first_page(url: str) -> str:
        """Преобразует URL к формату `/page-1/` и добавляет `items_per_page=48`."""
        parsed = urlparse(url)
        path = parsed.path or "/"

        path = re.sub(r"/page-\d+/?$", "/", path)
        if not path.endswith("/"):
            path = path + "/"
        if not re.search(r"/page-1/+$", path):
            path = path + "page-1/"

        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["items_per_page"] = "48"
        new_query = urlencode(query, doseq=True)
        return urlunparse(parsed._replace(path=path, query=new_query))

    def iter_paginated_pages(
        self,
        base_url: str,
    ) -> Generator[Tuple[int, str, BeautifulSoup], None, None]:
        """Итерирует страницы категории до отсутствия блока подгрузки следующей страницы."""
        url = self.normalize_to_first_page(base_url)
        page = 1

        while True:
            logging.info(f"Загружаем страницу {page}: {url}")
            soup = self._http_client.get_soup(url)
            if not soup:
                logging.warning(f"Ошибка загрузки страницы {page}: {url}")
                return

            yield page, url, soup

            show_more = soup.select_one("div.cnc-pagination__show-more")
            if not show_more:
                return

            page += 1
            parsed = urlparse(url)
            next_path = re.sub(r"/page-\d+/", f"/page-{page}/", parsed.path)
            url = urlunparse(parsed._replace(path=next_path))
