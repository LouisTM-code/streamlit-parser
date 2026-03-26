"""Инфраструктура пагинации категорий."""

from __future__ import annotations

import logging
import re
from typing import Generator, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from parser_domain.infrastructure.http_client.client import HttpClient


class CategoryPaginator:
    """Класс CategoryPaginator.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

    def __init__(self, http_client: HttpClient) -> None:
        """Выполняет операцию роли «__init__»."""
        self._http_client = http_client

    @staticmethod
    def normalize_to_first_page(url: str) -> str:
        """Выполняет операцию роли «normalize_to_first_page»."""
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
        """Выполняет операцию роли «iter_paginated_pages»."""
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
