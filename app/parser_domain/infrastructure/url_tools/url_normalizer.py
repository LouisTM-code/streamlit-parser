"""Модуль url_normalizer.

Роль и ответственность:
    - предоставляет публичные элементы этого слоя.

Границы:
    - не реализует ответственность соседних слоёв.

Взаимодействие с другими ролями:
    - используется через импорт другими модулями проекта.
"""

from __future__ import annotations

import re
from typing import List
from urllib.parse import urlparse, urlunparse


class URLNormalizer:
    """Класс URLNormalizer.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

    @staticmethod
    def normalize_links(raw_links: List[str]) -> List[str]:
        """Очищает пользовательские ссылки и сохраняет порядок уникальных значений."""
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
        """Выполняет операцию роли «validate_links»."""
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
