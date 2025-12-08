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
#                               КЛАСС                                       #
# ========================================================================= #
class ProductListParser:
    """
    Класс для табличного/каталожного парсинга страниц категорий.

    Режимы работы:
        - "basic"     — исходный режим: извлечение фиксированного набора полей
                        через специализированные экстракторы (_extract_row_data_v1/v2).
        - "fulltable" — новый режим: универсальный парсер, который собирает
                        максимум текстовых и атрибутных данных из карточек товара,
                        не заходя во внутренние карточки.
    """

    # ------------------------------------------------------------------ #
    #                         Инициализация                              #
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        links: List[str],
        output_file: str = "product_list.xlsx",
        base_parser: WebParser | None = None,
        mode: str = "basic",
    ) -> None:
        """
        Параметры:
            links:       Список URL‑адресов категорий каталога.
            output_file: Имя Excel‑файла для сохранения результата.
            base_parser: Экземпляр WebParser для переиспользования HTTP‑сессии
                         и настроек; если None — создаётся новый.
            mode:        Режим работы:
                             * "basic"     — старый режим с ограниченным набором
                                             колонок (название, бренд, артикул и т.п.);
                             * "fulltable" — новый режим, собирающий все доступные
                                             текстовые и атрибутные значения из карточки.
        Исключения:
            ValueError:  Если список ссылок пуст/невалиден или передан неизвестный режим.
        """
        self.logger: logging.Logger = self._configure_logger()
        self.parser: WebParser = base_parser or WebParser()
        self.output_file: str = output_file

        allowed_modes = {"basic", "fulltable"}
        if mode not in allowed_modes:
            raise ValueError(
                f"Неизвестный режим '{mode}'. Допустимо: {', '.join(sorted(allowed_modes))}."
            )
        self.mode: str = mode

        self.links: List[str] = self.normalize_links(links)
        self._validate_links()
        self.logger.info("Принято %d ссылок, режим: %s", len(self.links), self.mode)

        # вспомогательные структуры для формирования Excel
        self._sheet_name_counts: Dict[str, int] = {}
        self._sheet_data: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()

    # ------------------------------------------------------------------ #
    #                         Логирование                                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _configure_logger() -> logging.Logger:
        """
        Настраивает изолированный логгер класса ProductListParser.

        Возвращает:
            logging.Logger: готовый к использованию логгер.
        """
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
    #                   Утилита нормализации ссылок                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_links(raw_links: List[str]) -> List[str]:
        """
        Очистка ссылок:
            - удаление пустых строк/пробелов;
            - добавление схемы http/https при отсутствии;
            - удаление завершающего слеша;
            - устранение дубликатов с сохранением порядка.

        Параметры:
            raw_links: Список строк, введённых пользователем (возможно "грязных").

        Возвращает:
            Список нормализованных URL.
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
    #                           Валидация URL                            #
    # ------------------------------------------------------------------ #
    def _validate_links(self) -> None:
        """
        Проверяет корректность URL и приводит каждую ссылку к нормализованному виду,
        НЕ навязывая items_per_page. Параметры запроса сохраняются как есть.
        Дополнительная нормализация под пагинацию выполняется в _normalize_to_first_page().

        Исключения:
            ValueError: если после очистки не осталось валидных ссылок
                        или найдены некорректные URL.
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

        # сохраняем нормализованные ссылки без вмешательства в query
        self.links = processed

    # ------------------------------------------------------------------ #
    #                   НОРМАЛИЗАЦИЯ И ПАГИНАЦИЯ                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_to_first_page(url: str) -> str:
        """
        Приводит URL категории к виду: .../page-1/?items_per_page=48

        Действия:
            - удаляет завершающий сегмент /page-N/ если присутствует;
            - гарантирует завершающий '/';
            - добавляет /page-1/ при отсутствии;
            - устанавливает items_per_page=48 (сохраняя прочие query‑параметры).

        Параметры:
            url: URL категории (любой страницы).

        Возвращает:
            Нормализованный URL первой страницы с параметром items_per_page=48.
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

        На каждой итерации:
            - загружает страницу категории;
            - yield'ит кортеж (page_index, page_url, soup).

        Останавливается, когда на странице отсутствует div.cnc-pagination__show-more.
        При ошибке загрузки текущей страницы прекращает обход категории.

        Параметры:
            base_url: Исходный URL категории (без привязки к номеру страницы).

        Возвращает:
            Итератор по страницам категории.
        """
        url = self._normalize_to_first_page(base_url)
        page = 1
        while True:
            self.logger.info("Загружаем страницу %d: %s", page, url)
            soup = self.parser.get_page(url)
            if not soup:
                self.logger.warning("Ошибка загрузки страницы %d: %s", page, url)
                # прекращаем обход этой категории
                return

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
    #                        PRIVATE HELPERS                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Очищает строку:
            - заменяет \xa0 и &nbsp; на пробел;
            - удаляет префикс 'Бренд: ';
            - схлопывает множественные пробелы.

        Параметры:
            text: Исходная строка.

        Возвращает:
            Очищенный текст.
        """
        cleaned = (
            text.replace("\xa0", " ")
            .replace("&nbsp;", " ")
            .replace("Бренд: ", "")
        )
        return " ".join(cleaned.split()).strip()

    @staticmethod
    def _clean_price(text: str) -> str:
        """
        Очищает текст цены:
            - удаляет все символы кроме цифр и разделителей (.,);
            - убирает пробелы и валютные символы.

        Параметры:
            text: Исходное текстовое представление цены.

        Возвращает:
            Строку с числовым значением цены.
        """
        no_nbsp = text.replace("\xa0", " ").replace("&nbsp;", " ")
        return re.sub(r"[^0-9.,]", "", no_nbsp).replace(" ", "")

    # ------------------------------------------------------------------ #
    #               Заголовок категории → имя листа Excel                #
    # ------------------------------------------------------------------ #
    def _extract_page_title(self, soup: BeautifulSoup) -> str:
        """
        Возвращает заголовок категории (текст <h1>).

        Параметры:
            soup: разобранный BeautifulSoup HTML.

        Возвращает:
            Заголовок категории либо "Категория" по умолчанию.
        """
        tag = soup.select_one("h1.cnc-title-xl span")
        if not tag:
            tag = soup.find("h1")
        return self._clean_text(tag.get_text()) if tag else "Категория"

    def _make_unique_sheet_name(self, title: str) -> str:
        """
        Создаёт уникальное имя листа Excel, учитывая ограничения:
            - длина ≤ 31 символ;
            - отсутствие запрещённых символов [: \\ / ? * [ ] ].

        При повторном использовании имени добавляет суффикс _N.

        Параметры:
            title: исходный заголовок категории.

        Возвращает:
            Безопасное и уникальное имя листа.
        """
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
        """
        Табличная верстка (v1).

        Извлекает фиксированный набор полей:
            - Название
            - Бренд
            - Артикул
            - Цена
            - Наличие

        Параметры:
            row: div.cnc-product-categories-mob-card.

        Возвращает:
            Словарь с данными по товару либо None, если разметка не подходит.
        """
        name_td = row.find("div", class_="cnc-product-categories-mob-card__header")
        if not name_td or not name_td.a:
            return None
        name = self._clean_text(name_td.a.get_text())

        brand_td = name_td.find(
            "span",
            class_="cnc-product-categories-mob-card__brand",
        )
        brand = self._clean_text(brand_td.get_text()) if brand_td else "Н/Д"

        article_span = row.find(
            "span",
            class_="cnc-product-categories-mob-card__sku",
        )
        article_block = None
        if article_span:
            article_block = article_span.select_one("span.cnc-sku__product-code")

        article = (
            f"119-{self._clean_text(article_block.get_text())}"
            if article_block
            else "Н/Д"
        )

        price_span = row.find(
            "div",
            class_="cnc-product-categories-mob-card__current-price",
        )
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        avail_span = row.find(
            "span",
            class_="cnc-product-amount__product-quantity",
        )
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
        """
        Блочная верстка (v2).

        Параметры:
            name_div: div.cnc-short-list-product.

        Возвращает:
            Словарь с данными по товару либо None, если разметка не подходит.
        """
        if not name_div or not name_div.a:
            return None

        name_place = name_div.find_next(
            "div",
            class_="cnc-short-list-product__info",
        )
        name = self._clean_text(name_place.a.get_text())

        brand_block = name_div.find_next(
            "div",
            class_="cnc-short-list-product__short-info",
        )
        brand = "Н/Д"
        article = "Н/Д"
        if brand_block:
            brand_link = brand_block.select_one(
                "div.cnc-short-list-product__brand-name"
            )
            if brand_link:
                brand = self._clean_text(brand_link.get_text())
            span_article = brand_block.find("span", class_="cnc-sku__product-code")
            if span_article:
                article = f"119-{self._clean_text(span_article.get_text())}"

        price_span = name_div.find_next("span", class_="ty-price")
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        avail_p = name_div.find_next(
            "span",
            class_="cnc-product-amount__status",
        )
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
    #                 Универсальный EXTRACTOR (fulltable)                #
    # ------------------------------------------------------------------ #
    def _extract_row_full(self, row: Tag) -> Dict[str, Any] | None:
        """
        Универсальный парсер карточки товара для режима "fulltable".

        Логика:
            1. Пытается извлечь базовые поля (Название, Бренд, Артикул, Цена, Наличие)
               через существующие специализированные экстракторы:
                   - _extract_row_data_v1(row)
                   - _extract_row_data_v2(row)
               (старое поведение НЕ меняется).
            2. Дополнительно извлекает все характеристики, размеченные блоками
               div.cnc-product-features__feature, формируя пары
                   <заголовок характеристики> → <значение>.
            3. Объединяет базовые поля и характеристики в один словарь.

        Таким образом, в Excel появляются НОРМАЛЬНЫЕ именованные колонки
        для характеристик без какого-либо хардкода их названий.

        Параметры:
            row: Корневой тег карточки товара
                 (div.cnc-product-categories-mob-card или div.cnc-short-list-product).

        Возвращает:
            Словарь с базовыми полями + характеристиками, либо None,
            если не удалось извлечь вообще ничего.
        """
        # 1. Базовые данные по старым экстракторам (v1 / v2)
        base_data: Dict[str, Any] | None = self._extract_row_data_v1(row)
        if not base_data:
            base_data = self._extract_row_data_v2(row)

        # Если ни один из специализированных экстракторов не отработал,
        # всё равно продолжаем — возможно, удастся вытащить только характеристики.
        if not base_data:
            base_data = {}

        # 2. Характеристики из блоков cnc-product-features__feature
        features = self._extract_feature_pairs(row)
        if features:
            base_data.update(features)

        # Если после всех попыток данных нет — считаем строку пустой
        return base_data or None


    def _extract_feature_pairs(self, container: Tag) -> Dict[str, str]:
        """
        Универсальный экстрактор характеристик товара.

        Работает и для блочной верстки (div.cnc-short-list-product),
        и для табличной (div.cnc-product-categories-mob-card), так как в обоих
        случаях характеристики размечены через блоки:
            div.cnc-product-features__feature
                span.cnc-product-features__label > span  -> название
                div (следующий)                          -> значение

        Параметры:
            container: Корневой тег карточки товара.

        Возвращает:
            Словарь {<название характеристики>: <значение>}.
        """
        features: Dict[str, str] = {}

        # Берём все блоки характеристик внутри конкретной карточки товара
        for feature_block in container.select("div.cnc-product-features__feature"):
            # 1) Заголовок характеристики
            label_inner_span = feature_block.select_one(
                "span.cnc-product-features__label span"
            )
            if not label_inner_span:
                continue

            # Собираем текст заголовка, чистим пробелы и двоеточие
            raw_label = " ".join(label_inner_span.stripped_strings)
            label = self._clean_text(raw_label)
            if label.endswith(":"):
                label = label[:-1].rstrip()
            if not label:
                continue

            # 2) Контейнер значения характеристики
            #    Сначала пытаемся найти div-соседа для span.cnc-product-features__label
            label_wrapper = label_inner_span.find_parent(
                "span",
                class_="cnc-product-features__label",
            )
            value_container: Tag | None = None

            if label_wrapper:
                sibling = label_wrapper.find_next_sibling("div")
                if isinstance(sibling, Tag):
                    value_container = sibling

            # fallback: первый div внутри блока характеристики
            if not value_container:
                value_container = feature_block.find("div")

            if not value_container:
                continue

            raw_value = " ".join(value_container.stripped_strings)
            value = self._clean_text(raw_value)
            if not value:
                continue

            # Если одно и то же имя встречается несколько раз,
            # оставляем последнее значение (упрощённый, предсказуемый вариант).
            features[label] = value

        return features


    # ------------------------------------------------------------------ #
    #                 Определение версии + парсинг страницы              #
    # ------------------------------------------------------------------ #
    def _parse_category_page(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Базовый (исторический) парсер страницы категории.

        Алгоритм:
            - Пытается сначала разметку v1 (табличная карточка);
            - если не найдено ни одной карточки v1, пытается v2 (блочная карточка).

        Параметры:
            soup: разобранный HTML страницы категории.

        Возвращает:
            Список словарей с фиксированными полями.
        """
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

    def _parse_full_table_page(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Новый режим парсинга страницы категории для mode="fulltable".

        Алгоритм:
            1. Находит все карточки товаров по двум основным селекторам:
               - div.cnc-product-categories-mob-card (v1)
               - div.cnc-short-list-product (v2)
            2. Для каждой карточки вызывает универсальный экстрактор _extract_row_full().
            3. Возвращает список словарей с максимально полным набором данных.

        Если ни одна карточка не найдена, возвращается пустой список.

        Параметры:
            soup: разобранный HTML страницы категории.

        Возвращает:
            Список словарей (произвольный набор колонок).
        """
        products: List[Dict[str, Any]] = []

        # v1: табличная верстка
        for row in soup.select("div.cnc-product-categories-mob-card"):
            data = self._extract_row_full(row)
            if data:
                products.append(data)

        # v2: блочная верстка
        for row in soup.select("div.cnc-short-list-product"):
            data = self._extract_row_full(row)
            if data:
                products.append(data)

        return products

    # ------------------------------------------------------------------ #
    #                      Основной метод run()                          #
    # ------------------------------------------------------------------ #
    def run(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Основной цикл обхода всех ВХОДНЫХ ссылок категорий.

        Для каждой ссылки:
            - последовательно загружает /page-1/, /page-2/, ...,
              пока на странице присутствует div.cnc-pagination__show-more;
            - парсит страницу в зависимости от выбранного режима:
                * mode == "basic"     → _parse_category_page();
                * mode == "fulltable" → _parse_full_table_page();
            - агрегирует все товары категории в один лист Excel.

        Возвращает:
            (all_products, stats), где:
                all_products: плоский список всех товаров (по всем категориям);
                stats:       сводная статистика по категориям и товарам.
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

                if self.mode == "fulltable":
                    products = self._parse_full_table_page(soup)
                else:
                    products = self._parse_category_page(soup)

                self.logger.info(
                    "  └— товаров на странице %d: %d",
                    page_index,
                    len(products),
                )
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
            "success": success_categories,  # успешно обработанные категории (URL)
            "failed": len(failed_links),
            "failed_links": failed_links,
            "total_products": len(all_products),
            "mode": self.mode,
        }
        self.logger.info(
            "Итого | режим: %(mode)s | категорий: %(total)d | "
            "успех: %(success)d | ошибок: %(failed)d | товаров: %(total_products)d",
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

        Важно:
            - Имя листа соответствует заголовку категории (_extract_page_title()),
              с учётом ограничений Excel (_make_unique_sheet_name()).
            - Колонки листа формируются автоматически как объединение ключей
              по всем строкам — это обеспечивает динамический набор колонок
              в режиме "fulltable" без изменения старой логики.
        """
        if not self._sheet_data:
            raise RuntimeError("Нет данных для сохранения. Сначала вызовите run().")

        self.logger.info("Сохраняем результаты в %s", self.output_file)
        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            for sheet_name, rows in self._sheet_data.items():
                df = pd.DataFrame(rows)
                # листы Excel не должны быть пустыми — проверяем
                if df.empty:
                    df = pd.DataFrame({"Нет данных": []})
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

        buffer.seek(0)
        # сохраняем на диск
        Path(self.output_file).write_bytes(buffer.getvalue())
        self.logger.info(
            "Файл %s создан (%d листов)",
            Path(self.output_file).name,
            len(self._sheet_data),
        )
        buffer.seek(0)
        return buffer.getvalue()
