"""HTTP-клиент инфраструктурного слоя для загрузки HTML-страниц.

Роль и ответственность:
    - выполняет GET-запросы и преобразует ответ в `BeautifulSoup`;
    - инкапсулирует настройки сессии и заголовков.

Границы:
    - не извлекает бизнес-поля из DOM;
    - не реализует ретраи/кеширование.

Взаимодействие с другими ролями:
    - используется фасадом `WebParser` и пагинатором категорий.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup


class HttpClient:
    """Адаптер `requests.Session` для получения и парсинга HTML-документов."""

    def __init__(self) -> None:
        """Инициализирует состояние сессии и заголовки по умолчанию для парсинга."""
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
        """Загружает URL и возвращает DOM (`BeautifulSoup`) либо `None` при ошибке."""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException as error:
            logging.error(f"Ошибка запроса {url}: {str(error)}")
            return None
