from __future__ import annotations

import logging
import re
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
from bs4 import BeautifulSoup, Tag

from Parse import WebParser

__all__ = ["ProductListParser"]

# ========================================================================= #
#                               КЛАСС                                        #
# ========================================================================= #
class ProductListParser:
    # ------------------------------------------------------------------ #
    #                         Инициализация                               #
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        links: List[str],
        output_file: str = "product_list.xlsx",
        base_parser: WebParser | None = None,
    ) -> None:
        self.logger: logging.Logger = self._configure_logger()
        self.parser: WebParser = base_parser or WebParser()
        self.output_file: str = output_file

        self.links: List[str] = self.normalize_links(links)
        self._validate_links()
        self.logger.info("Принято %d ссылок", len(self.links))

        # вспомогательные структуры для формирования Excel
        self._sheet_name_counts: Dict[str, int] = {}
        self._sheet_data: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()

    # ------------------------------------------------------------------ #
    #                         Логирование                                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _configure_logger() -> logging.Logger:
        logger = logging.getLogger("ProductListParser")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
                )
            )
            logger.addHandler(handler)
        logger.propagate = False
        return logger

    # ------------------------------------------------------------------ #
    #                   Утилита нормализации ссылок                       #
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_links(raw_links: List[str]) -> List[str]:
        """
        Очистка ссылок: удаление пустых строк/пробелов, добавление http/https,
        удаление завершающего слеша, устранение дубликатов c сохранением порядка.
        """
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

    # ------------------------------------------------------------------ #
    #            Валидация URL         #
    # ------------------------------------------------------------------ #
    def _validate_links(self) -> None:
            """
            Проверяет корректность URL и приводит каждую ссылку к нормализованному виду,
            НЕ навязывая items_per_page. Параметры запроса сохраняются как есть.
            Дополнительная нормализация под пагинацию выполняется в _normalize_to_first_page().
            """
            if not self.links:
                raise ValueError(
                    "Список ссылок пуст или содержит только невалидные элементы."
                )

            url_re = re.compile(r"^https?://[\w\-.:/?#=&%~+]+$", re.IGNORECASE)
            invalid: List[str] = []
            processed: List[str] = []

            for url in self.links:
                if not url_re.match(url):
                    invalid.append(url)
                    continue

                # Сохраняем URL без принудительных правок query; только пересобираем обратно
                parsed = urlparse(url)
                new_url = urlunparse(parsed)
                processed.append(new_url)

            if invalid:
                raise ValueError("Обнаружены некорректные URL: " + ", ".join(invalid))

            self.links = processed  # сохраняем нормализованные ссылки без вмешательства в query

    # ------------------------------------------------------------------ #
    #                   НОРМАЛИЗАЦИЯ И ПАГИНАЦИЯ                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_to_first_page(url: str) -> str:
            """
            Приводит URL категории к виду: .../page-1/?items_per_page=48
            - удаляет завершающий сегмент /page-N/ если присутствует
            - гарантирует завершающий '/'
            - устанавливает items_per_page=48 (сохраняя прочие query-параметры)
            """
            parsed = urlparse(url)
            path = parsed.path or "/"
            # Удаляем конечный сегмент /page-N/ (если был передан)
            path = re.sub(r"/page-\d+/?$", "/", path)
            # Нормализуем завершающий '/'
            if not path.endswith("/"):
                path = path + "/"
            # Добавляем page-1/
            if not re.search(r"/page-1/+$", path):
                path = path + "page-1/"
            # Обновляем query: items_per_page=48
            q = dict(parse_qsl(parsed.query, keep_blank_values=True))
            q["items_per_page"] = "48"
            new_query = urlencode(q, doseq=True)
            return urlunparse(parsed._replace(path=path, query=new_query))

    def _iter_paginated_pages(self, base_url: str):
            """
            Генератор страниц категории.
            На каждой итерации загружает страницу и yield'ит кортеж (page_index, page_url, soup).
            Останавливается, когда на странице отсутствует div.cnc-pagination__show-more.
            """
            url = self._normalize_to_first_page(base_url)
            page = 1
            while True:
                self.logger.info("Загружаем страницу %d: %s", page, url)
                soup = self.parser.get_page(url)
                if not soup:
                    self.logger.warning("Ошибка загрузки страницы %d: %s", page, url)
                    return  # прекращаем обход этой категории

                yield page, url, soup

                # если есть блок "показать ещё" — есть следующая страница
                show_more = soup.select_one("div.cnc-pagination__show-more")
                if not show_more:
                    return

                page += 1
                parsed = urlparse(url)
                next_path = re.sub(r"/page-\d+/", f"/page-{page}/", parsed.path)
                url = urlunparse(parsed._replace(path=next_path))


    # ------------------------------------------------------------------ #
    #                        PRIVATE HELPERS                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_text(text: str) -> str:
        """Удаляет множественные пробелы, \xa0, &nbsp; и префикс 'Бренд: '."""
        cleaned = (
            text.replace("\xa0", " ")
                .replace("&nbsp;", " ")
                .replace("Бренд: ", "")
        )
        return " ".join(cleaned.split()).strip()

    @staticmethod
    def _clean_price(text: str) -> str:
        """Извлекает цифры и десятичные разделители, убирая пробелы и валюту."""
        no_nbsp = text.replace("\xa0", " ").replace("&nbsp;", " ")
        return re.sub(r"[^0-9.,]", "", no_nbsp).replace(" ", "")

    # ------------------------------------------------------------------ #
    #               Заголовок категории → имя листа Excel                #
    # ------------------------------------------------------------------ #
    def _extract_page_title(self, soup: BeautifulSoup) -> str:
        """Возвращает заголовок категории (текст <h1>)."""
        tag = soup.select_one("h1.cnc-title-xl span")
        if not tag:
            tag = soup.find("h1")
        return self._clean_text(tag.get_text()) if tag else "Категория"

    def _make_unique_sheet_name(self, title: str) -> str:
        """Создаёт уникальное имя листа, учитывая ограничения Excel (≤31 символ)."""
        # убираем запрещённые символы
        safe = re.sub(r"[:\\/?*\[\]]", " ", title).strip()
        if not safe:
            safe = "Sheet"

        base = safe[:31]  # предварительное обрезание до лимита
        count = self._sheet_name_counts.get(base, 0)

        if count:
            # если имя уже использовалось, добавляем суффикс _n
            while True:
                count += 1
                suffix = f"_{count}"
                candidate = (base[: 31 - len(suffix)]) + suffix
                if candidate not in self._sheet_name_counts:
                    safe = candidate
                    break
        else:
            safe = base

        self._sheet_name_counts[safe] = 1
        return safe

    # ------------------------------------------------------------------ #
    #                         EXTRACTORS (v1)                            #
    # ------------------------------------------------------------------ #
    def _extract_row_data_v1(self, row: Tag) -> Dict[str, str] | None:
        """Табличная верстка (v1)."""
        name_td = row.find("div", class_="cnc-product-categories-mob-card__header")
        if not name_td or not name_td.a:
            return None
        name = self._clean_text(name_td.a.get_text())

        brand_td = name_td.find("span", class_="cnc-product-categories-mob-card__brand")
        brand = self._clean_text(brand_td.get_text()) if brand_td else "Н/Д"

        article_span = row.find("span", class_="cnc-product-categories-mob-card__sku")
        if article_span:
            article_block=article_span.select_one("span.cnc-sku__product-code")
        article = (
            f"119-{self._clean_text(article_block.get_text())}" if article_block else "Н/Д"
        )

        price_span = row.find("div", class_="cnc-product-categories-mob-card__current-price")
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        avail_span = row.find("span", class_="cnc-product-amount__product-quantity")
        if not avail_span:
            avail_span = row.find("span", class_="cnc-product-amount__status")
        availability = self._clean_text(avail_span.get_text()) if avail_span else "Н/Д"

        return {
            "Название": name,
            "Бренд": brand,
            "Артикул": article,
            "Цена": price,
            "Наличие": availability,
        }

    # ------------------------------------------------------------------ #
    #                         EXTRACTORS (v2)                            #
    # ------------------------------------------------------------------ #
    def _extract_row_data_v2(self, name_div: Tag) -> Dict[str, str] | None:
        """Блочная верстка (v2). Принимает <div class="cnc-short-list-product">."""
        if not name_div or not name_div.a:
            return None
        name_place = name_div.find_next("div", class_="cnc-short-list-product__info")
        name = self._clean_text(name_place.a.get_text())

        brand_block = name_div.find_next("div", class_="cnc-short-list-product__short-info")
        brand = "Н/Д"
        article = "Н/Д"
        if brand_block:
            brand_link = brand_block.select_one("div.cnc-short-list-product__brand-name")
            if brand_link:
                brand = self._clean_text(brand_link.get_text())
            span_article = brand_block.find("span", class_="cnc-sku__product-code")
            if span_article:
                article = f"119-{self._clean_text(span_article.get_text())}"

        price_span = name_div.find_next("span", class_="ty-price")
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        avail_p = name_div.find_next("span", class_="cnc-product-amount__status")
        availability = "Н/Д"
        if avail_p:
            avail_span = avail_p.find("span")
            if avail_span:
                availability = self._clean_text(avail_span.get_text())

        return {
            "Название": name,
            "Бренд": brand,
            "Артикул": article,
            "Цена": price,
            "Наличие": availability,
        }

    # ------------------------------------------------------------------ #
    #                 Определение версии + парсинг страницы              #
    # ------------------------------------------------------------------ #
    def _parse_category_page(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Пытается сначала v1, затем v2 (если v1 не найдена)."""
        products: List[Dict[str, str]] = []

        # --- v1 -------------------------------------------------------- #
        rows = soup.select("div.cnc-product-categories-mob-card")
        for row in rows:
            data = self._extract_row_data_v1(row)
            if data:
                products.append(data)
        if products:
            return products

        # --- v2 -------------------------------------------------------- #
        for name_div in soup.select("div.cnc-short-list-product"):
            data = self._extract_row_data_v2(name_div)
            if data:
                products.append(data)
        return products

    # ------------------------------------------------------------------ #
    #                      Основной метод run()                          #
    # ------------------------------------------------------------------ #
    def run(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
            """
            Обходит все ВХОДНЫЕ ссылки категорий.
            Для каждой ссылки последовательно загружает /page-1/, /page-2/, ...
            пока на странице присутствует div.cnc-pagination__show-more.
            Все страницы одной категории агрегируются в ОДИН лист Excel.
            """
            all_products: List[Dict[str, Any]] = []
            failed_links: List[str] = []
            success_categories = 0

            for base_url in self.links:
                category_rows: List[Dict[str, Any]] = []
                first_title: str | None = None
                success_any_page = False

                for page_index, page_url, soup in self._iter_paginated_pages(base_url):
                    if first_title is None:
                        first_title = self._extract_page_title(soup)

                    products = self._parse_category_page(soup)
                    self.logger.info("  └— товаров на странице %d: %d", page_index, len(products))
                    category_rows.extend(products)
                    all_products.extend(products)
                    success_any_page = True

                if success_any_page:
                    # один лист на весь URL категории
                    title_for_sheet = first_title or base_url
                    sheet_name = self._make_unique_sheet_name(title_for_sheet)
                    self._sheet_data[sheet_name] = category_rows
                    success_categories += 1
                else:
                    failed_links.append(base_url)

            stats = {
                "total": len(self.links),
                "success": success_categories,   # успешно обработанные категории (URL)
                "failed": len(failed_links),
                "failed_links": failed_links,
                "total_products": len(all_products),
            }
            self.logger.info(
                "Итого | категорий: %(total)d | успех: %(success)d "
                "| ошибок: %(failed)d | товаров: %(total_products)d",
                stats,
            )
            return all_products, stats


    # ------------------------------------------------------------------ #
    #                   Сохранение результата в Excel                    #
    # ------------------------------------------------------------------ #
    def save_results(self) -> bytes:
        """
        Записывает результаты в Excel‑файл, создавая отдельный лист
        для каждой категории. Возвращает бинарный контент для скачивания.
        """
        if not self._sheet_data:
            raise RuntimeError("Нет данных для сохранения. Сначала вызовите run().")

        self.logger.info("Сохраняем результаты в %s", self.output_file)
        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            for sheet_name, rows in self._sheet_data.items():
                df = pd.DataFrame(rows)
                # листы Excel не должны быть пустыми — проверяем
                if df.empty:
                    df = pd.DataFrame({"Нет данных": []})
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

        buffer.seek(0)
        # сохраняем на диск
        Path(self.output_file).write_bytes(buffer.getvalue())
        self.logger.info(
            "Файл %s создан (%d листов)",
            Path(self.output_file).name,
            len(self._sheet_data),
        )
        buffer.seek(0)
        return buffer.getvalue()
