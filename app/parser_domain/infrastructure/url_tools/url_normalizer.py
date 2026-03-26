"""Утилиты нормализации и валидации URL категорий.

Роль и ответственность:
    - очищает пользовательский ввод ссылок и удаляет дубликаты с сохранением порядка;
    - проверяет синтаксическую валидность URL перед запуском парсинга.

Границы:
    - не проверяет доступность ресурса по сети;
    - не исправляет семантические ошибки маршрутов сайта.

Взаимодействие с другими ролями:
    - используется `ProductListParser` перед обходом категорий.
"""

from __future__ import annotations

import re
from typing import List
from urllib.parse import urlparse, urlunparse


class URLNormalizer:
    """Сервис подготовки списка URL для пакетной обработки."""

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
        """Проверяет формат ссылок и возвращает нормализованный список или `ValueError`."""
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
