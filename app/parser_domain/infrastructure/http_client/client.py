"""Модуль client.

Роль и ответственность:
    - предоставляет публичные элементы этого слоя.

Границы:
    - не реализует ответственность соседних слоёв.

Взаимодействие с другими ролями:
    - используется через импорт другими модулями проекта.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup


class HttpClient:
    """Класс HttpClient.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

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
        """Выполняет операцию роли «get_soup»."""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException as error:
            logging.error(f"Ошибка запроса {url}: {str(error)}")
            return None
