# Единый **source of truth** кодовой базы

- Документ сформирован автоматически.
- Корень обхода: `D:/Git/streamlit-parser`
- Время сборки: 2025-12-08 23:05:50 RTZ 2 (зима)
- Всего модулей: 4
- Пустых модулей: 0

# Дерево абсолютных импортов модулей (Python)

> Имена приведены в точечной нотации; соответствуют абсолютным путям импортов.

- [App](#app.py)
- [Parse](#parse.py)
- [product_list_parser](#product_list_parser.py)
- [web_ui](#web_ui.py)

# Актуальный код

## App.py
<a id="app.py"></a>

```python
from Parse import WebParser
from web_ui import StreamlitUI

def main():
    parser = WebParser()
    
    is_streamlit_running()
    ui = StreamlitUI(parser)
    ui.run()

def is_streamlit_running() -> bool:
    """Проверка запущен ли Streamlit"""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except ImportError:
        return False

if __name__ == "__main__":
    main()
```

## Parse.py
<a id="parse.py"></a>

```python
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from typing import Optional, List, Dict
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import re 


class WebParser:
    def __init__(self):
        self.setup_logging()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    @staticmethod
    def setup_logging():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )

    @staticmethod
    def clean_text(text: str) -> str:
        return ' '.join(text.replace('\xa0', ' ').strip().split())

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            logging.error(f'Ошибка запроса {url}: {str(e)}')
            return None

    def parse_links(self, soup: BeautifulSoup) -> List[str]:
        """Сбор ссылок с главной страницы с двух разных селекторов"""
        links = []
        
        # Первый вариант (оригинальный селектор)
        for link in soup.select('div.cnc-product-categories-mob-card__header a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 1): {href}')
        
        # Второй вариант (новый селектор)
        for link in soup.select('div.cnc-short-list-product a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 2): {href}')
        
        # Удаление дубликатов с сохранением порядка
        seen = set()
        return [x for x in links if not (x in seen or seen.add(x))]

    def parse_features(self, soup: BeautifulSoup) -> Dict[str, str]:
        features = {}
        try:
            for feature_div in soup.find_all('div', class_='cnc-product-features__feature'):
                # Извлекаем название характеристики
                label = feature_div.find('span', class_='cnc-product-features__label')
                if not label:
                    continue
                
                feature_name = self.clean_text(label.text).rstrip(':')
                value_div = feature_div.find('div')

                if not feature_name or not value_div:
                    continue

                # Обработка разных форматов значений
                if value_div.find('a'):
                    # Случай со ссылкой
                    value = self.clean_text(value_div.find('a').text)
                elif value_div.find('ul'):
                    # Случай со списком
                    items = [self.clean_text(li.text) for li in value_div.find_all('li')]
                    value = ', '.join(items)
                else:
                    # Стандартный случай
                    value = self.clean_text(value_div.text.strip())

                features[feature_name] = value

        except Exception as e:
            logging.error(f'Ошибка парсинга характеристик: {str(e)}')
        
        return features

    def parse_product(self, soup: BeautifulSoup) -> Dict[str, str]:
        product_data = {
            'Товар': 'Н/Д',
            'Цена': 'Н/Д',
            'Описание': 'Н/Д',
            'Артикул': 'Н/Д'
        }

        try:
            # Основные данные
            title = soup.find('h1', class_='cnc-product-detail__title')
            if title:
                product_data['Товар'] = self.clean_text(title.text)

            price_div = soup.find('div', class_='cnc-product-detail__price-actual')
            if price_div:
                price = price_div.find('span', class_='ty-price-num')
                if price:
                    product_data['Цена'] = self.clean_text(price.text)

            description_div = soup.find('div', class_='cnc-product-description__left')
            if description_div:
                paragraphs = description_div.find_all(
                    'p', class_=lambda x: x != 'cnc-product-description__notice'
                )
                product_data['Описание'] = ' '.join(
                    self.clean_text(p.text) for p in paragraphs if p.text.strip()
                )

            sku = soup.find('span', class_='g-js-text-for-copy cnc-product-detail__product-code')
            if sku:
                product_data['Артикул'] = self.clean_text(sku.text)

            # Добавляем характеристики
            product_data.update(self.parse_features(soup))
            
            logging.info(f'Извлечено {len(product_data)-4} характеристик')

        except Exception as e:
            logging.error(f'Ошибка парсинга товара: {str(e)}')

        return product_data

    @staticmethod
    def save_to_excel(data: List[Dict], filename: str) -> None:
        try:
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            logging.info(f'Файл {filename} сохранён ({len(df.columns)} столбцов)')
        except Exception as e:
            logging.error(f'Ошибка сохранения: {str(e)}')

    @staticmethod
    def _normalize_to_first_page(url: str) -> str:
        """
        Приводит URL категории к виду: .../page-1/?items_per_page=48
        - удаляет завершающий сегмент /page-N/ если присутствует
        - гарантирует завершающий '/'
        - устанавливает items_per_page=48 (прочие query сохраняются)
        """
        parsed = urlparse(url)
        path = parsed.path or "/"

        # Удаляем конечный сегмент /page-N/ при наличии
        path = re.sub(r"/page-\d+/?$", "/", path)

        # Гарантируем завершающий '/'
        if not path.endswith("/"):
            path = path + "/"

        # Добавляем /page-1/ если его нет
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
        На каждой итерации возвращает (page_index, page_url, soup).
        Останавливается, когда на странице НЕТ div.cnc-pagination__show-more.
        При ошибке загрузки текущей страницы прекращает обход категории.
        """
        url = self._normalize_to_first_page(base_url)
        page = 1
        while True:
            logging.info(f"Загружаем страницу {page}: {url}")
            soup = self.get_page(url)
            if not soup:
                logging.warning(f"Ошибка загрузки страницы {page}: {url}")
                return  # прекращаем обход категории

            yield page, url, soup

            # На последней странице блока "показать ещё" нет
            show_more = soup.select_one("div.cnc-pagination__show-more")
            if not show_more:
                return

            page += 1
            parsed = urlparse(url)
            next_path = re.sub(r"/page-\d+/", f"/page-{page}/", parsed.path)
            url = urlunparse(parsed._replace(path=next_path))


    def iter_category_product_links(self, base_url: str) -> List[str]:
        """
        Возвращает все ссылки на товары из категории, обходя /page-1/, /page-2/, ...
        На каждой странице использует существующий parse_links(soup).
        Дубликаты убираются с сохранением порядка.
        """
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
```

## product_list_parser.py
<a id="product_list_parser.py"></a>

```python
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
```

## web_ui.py
<a id="web_ui.py"></a>

```python
# ui/web_ui.py
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from Parse import WebParser
from product_list_parser import ProductListParser


class StreamlitUI:
    """
    Класс UI‑обёртки для работы со Streamlit.

    Отвечает за:
        - конфигурацию страницы;
        - отрисовку вкладок/форм;
        - запуск соответствующих режимов парсинга;
        - отображение прогресса и результатов.
    """

    def __init__(self, parser: WebParser):
        """
        Параметры:
            parser: Экземпляр WebParser, переиспользуемый во всех режимах.
        """
        self.parser = parser
        self._setup_page_config()
        self.progress_bar = None
        self.status_text = None
        self.stats_placeholder = None

    # ------------------------------------------------------------------ #
    #                        BASIC PAGE CONFIG                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _setup_page_config() -> None:
        """Базовая конфигурация страницы Streamlit."""
        st.set_page_config(
            page_title="Web Parser",
            layout="centered",
            page_icon="🔍",
            initial_sidebar_state="expanded",
        )

    # ------------------------------------------------------------------ #
    #                        SIDEBAR / TABS                              #
    # ------------------------------------------------------------------ #
    def render_sidebar(self) -> Optional[dict]:
        """
        Отрисовка боковой панели с двумя вкладками:

        1. Парсинг Характеристик  (оригинальный режим, по стартовому URL)
        2. Табличный-парсинг Каталога (ProductListParser, список ссылок категорий)

        Возвращает:
            Словарь параметров выбранного режима либо None, если ещё ничего не запущено.
        """
        with st.sidebar:
            st.title("⚙️ Управление парсером")
            tab_start, tab_list = st.tabs(
                ["Парсинг Характеристик", "Табличный-парсинг Каталога"]
            )

            params: Optional[dict] = None

            # ---------- Вкладка 1 – Стартовый парсер ------------------- #
            with tab_start:
                url = st.text_input(
                    "Стартовый URL",
                    "https://example.com",
                    key="start_url",
                )
                output_file = st.text_input(
                    "Имя файла",
                    "products.xlsx",
                    key="start_output",
                )
                if st.button(
                    "🚀 Начать парсинг",
                    key="start_button",
                    width="stretch",
                ):
                    params = {
                        "mode": "start",  # UI-режим
                        "url": url,
                        "output": output_file,
                    }

            # ---------- Вкладка 2 – ProductListParser ------------------ #
            with tab_list:
                links_text = st.text_area(
                    "Ссылки категорий (по одной на строке)",
                    height=200,
                    placeholder="https://example.com/category/",
                    key="links_input",
                )

                # Новый выбор режима табличного парсинга
                mode_display_to_value = {
                    "basic (стандартный)": "basic",
                    "fulltable (расширенный)": "fulltable",
                }
                mode_label = st.selectbox(
                    "Режим табличного парсинга",
                    list(mode_display_to_value.keys()),
                    index=0,
                    key="catalog_mode",
                    help=(
                        "basic — старый режим с фиксированными колонками; "
                        "fulltable — расширенный режим, собирающий все данные "
                        "из карточек каталога без захода в карточку товара."
                    ),
                )
                parser_mode = mode_display_to_value[mode_label]

                output_file_links = st.text_input(
                    "Имя файла",
                    "product_list.xlsx",
                    key="links_output",
                )
                if st.button(
                    "🚀 Запустить",
                    key="list_button",
                    width="stretch",
                ):
                    raw_links = [
                        ln for ln in links_text.splitlines() if ln.strip()
                    ]
                    params = {
                        "mode": "productlist",       # UI-режим
                        "parser_mode": parser_mode,  # режим ProductListParser
                        "links": raw_links,
                        "output": output_file_links,
                    }

            st.markdown("---")
            self.stats_placeholder = st.empty()

        return params

    # ------------------------------------------------------------------ #
    #                       COMMON PROGRESS HELPERS                      #
    # ------------------------------------------------------------------ #
    def _init_progress(self) -> None:
        """Инициализация элементов прогресса."""
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.stats_placeholder = st.empty()

    def _update_progress(self, value: float, status: str) -> None:
        """
        Обновление индикатора прогресса.

        Параметры:
            value: Число от 0 до 100 (процент выполнения).
            status: Текстовый статус.
        """
        self.progress_bar.progress(int(value))
        self.status_text.markdown(f"**Статус:** {status}")

    def _show_stats(self, total: int, processed: int) -> None:
        """
        Отображение краткой статистики в сайдбаре.

        Параметры:
            total: Общее количество элементов.
            processed: Обработанное количество элементов.
        """
        self.stats_placeholder.markdown(
            f"""
        ### 📊 Прогресс
        - Всего: **{total}**
        - Обработано: **{processed}**
        - Осталось: **{total - processed}**
        """
        )

    # ------------------------------------------------------------------ #
    #                   RENDER RESULTS :  START PARSER                   #
    # ------------------------------------------------------------------ #
    def render_results(self, data: pd.DataFrame, filename: str) -> None:
        """
        Отрисовка результатов парсинга (оригинальный режим).

        Параметры:
            data:     DataFrame с результатами.
            filename: Имя файла для выгрузки Excel.
        """
        st.success("✅ Парсинг успешно завершен!")

        with st.expander("📁 Просмотр данных", expanded=True):
            st.dataframe(data, width="stretch", height=400)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            data.to_excel(writer, index=False, sheet_name="Products")

        st.download_button(
            label="💾 Скачать Excel",
            data=output.getvalue(),
            file_name=filename,
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            width="stretch",
        )

    # ------------------------------------------------------------------ #
    #               RENDER RESULTS :  PRODUCT LIST PARSER                #
    # ------------------------------------------------------------------ #
    def render_product_list_results(
        self,
        stats: Dict[str, Any],
        excel_content: bytes,
        filename: str,
    ) -> None:
        """
        Выводит сводную статистику + кнопку скачивания Excel с несколькими листами.

        Параметры:
            stats:         Сводная статистика, возвращённая ProductListParser.run().
            excel_content: Бинарный контент Excel‑файла.
            filename:      Имя файла для скачивания.
        """
        st.success("✅ Обработка списка ссылок завершена!")
        st.subheader("📊 Итоговая статистика")
        st.markdown(
            f"""
        - Режим: **{stats.get('mode', 'basic')}**
        - Всего ссылок: **{stats['total']}**
        - Успешно обработано: **{stats['success']}**
        - Ошибок: **{stats['failed']}**
        - Товаров собрано: **{stats['total_products']}**
        """
        )

        if stats["failed"]:
            with st.expander("⚠️ Ссылки с ошибками"):
                st.write(stats["failed_links"])

        # кнопка скачивания много‑листового файла
        st.download_button(
            label="💾 Скачать Excel",
            data=excel_content,
            file_name=filename,
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            width="stretch",
        )

    # ------------------------------------------------------------------ #
    #                             MAIN LOOP                              #
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """Главный метод запуска UI‑цикла."""
        st.title("🔍 Web Parser")

        params = self.render_sidebar()
        if not params:
            return

        self._init_progress()
        try:
            if params["mode"] == "start":
                result = self._run_parsing(params)
                if result:
                    self.render_results(*result)
            else:  # mode == "productlist"
                stats, excel_data, out_file = self._run_product_list(params)
                self.render_product_list_results(stats, excel_data, out_file)
        except Exception as exc:  # noqa: BLE001 — выводим ошибку пользователю
            st.error(f"⛔ Ошибка: {exc}")
        finally:
            time.sleep(0.5)
            self.progress_bar.empty()
            self.status_text.empty()

    # ------------------------------------------------------------------ #
    #                      ORIGINAL START‑PARSER FLOW                    #
    # ------------------------------------------------------------------ #
    def _run_parsing(self, params: dict) -> Optional[Tuple[pd.DataFrame, str]]:
        """
        Процесс парсинга для стартового URL (оригинальный режим).

        Параметры:
            params: Словарь параметров из сайдбара, ожидает ключи:
                - "url":    стартовый URL категории;
                - "output": имя выходного файла.

        Возвращает:
            Кортеж (DataFrame, имя файла) либо None.
        """
        links = self.parser.iter_category_product_links(params["url"])
        if not links:
            raise Exception("Ссылки на товары не найдены")

        self._update_progress(15, "Поиск ссылок на товары…")
        total = len(links)
        products: List[Dict[str, Any]] = []

        for idx, link in enumerate(links, 1):
            try:
                progress = 15 + int(70 * (idx / total))
                self._update_progress(
                    progress,
                    f"Обработка товара {idx}/{total}",
                )
                self._show_stats(total, idx)

                with st.spinner(f"Обработка: {link.split('/')[-1]}"):
                    product_page = self.parser.get_page(link)
                    if product_page:
                        products.append(self.parser.parse_product(product_page))
                    # Имитация небольшой задержки, чтобы прогресс был нагляднее
                    time.sleep(0.1)
            except Exception as ex:  # noqa: BLE001
                st.warning(f"Пропущен товар {idx}: {ex}")

        self._update_progress(95, "Формирование отчёта…")
        df = pd.DataFrame(products)
        if df.empty:
            raise Exception("Не удалось собрать данные")

        return df, params["output"]

    # ------------------------------------------------------------------ #
    #                 NEW FLOW  –  PRODUCT LIST PARSER                   #
    # ------------------------------------------------------------------ #
    def _run_product_list(
        self,
        params: dict,
    ) -> Tuple[Dict[str, Any], bytes, str]:
        """
        Обработка произвольного списка URL‑адресов категорий.

        Для каждой категории:
            - обходит /page-1/, /page-2/, ... (логика в ProductListParser);
            - агрегирует все страницы категории в один лист Excel.

        Параметры:
            params: Словарь параметров из сайдбара, ожидает ключи:
                - "links":        список URL категорий;
                - "output":       имя выходного файла;
                - "parser_mode":  режим ProductListParser ("basic"/"fulltable").

        Возвращает:
            (stats, excel_bytes, output_filename)
        """
        links: List[str] = params["links"]
        total = len(links)
        if total == 0:
            raise Exception("Список ссылок пуст")

        parser_mode: str = params.get("parser_mode", "basic")

        self._update_progress(
            5,
            f"Инициализация ProductListParser (режим: {parser_mode})…",
        )
        pl_parser = ProductListParser(
            links=links,
            output_file=params["output"],
            base_parser=self.parser,
            mode=parser_mode,
        )

        # весь обход /page-N/ и сбор строк — внутри ProductListParser.run()
        self._update_progress(20, "Сканирование страниц и сбор данных…")
        _, stats = pl_parser.run()

        self._update_progress(95, "Формирование отчёта…")
        excel_bytes = pl_parser.save_results()
        return stats, excel_bytes, params["output"]
```

## Project Docs/
<a id="project-docs"></a>

### ExistModuleCode.md
<a id="project-docs-existmodulecode.md"></a>

```md
# Единый **source of truth** кодовой базы

- Документ сформирован автоматически.
- Корень обхода: `D:/Git/streamlit-parser`
- Время сборки: 2025-12-08 23:05:36 RTZ 2 (зима)
- Всего модулей: 4
- Пустых модулей: 0

# Дерево абсолютных импортов модулей (Python)

> Имена приведены в точечной нотации; соответствуют абсолютным путям импортов.

- [App](#app.py)
- [Parse](#parse.py)
- [product_list_parser](#product_list_parser.py)
- [web_ui](#web_ui.py)

# Актуальный код

## App.py
<a id="app.py"></a>

```python
from Parse import WebParser
from web_ui import StreamlitUI

def main():
    parser = WebParser()
    
    is_streamlit_running()
    ui = StreamlitUI(parser)
    ui.run()

def is_streamlit_running() -> bool:
    """Проверка запущен ли Streamlit"""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except ImportError:
        return False

if __name__ == "__main__":
    main()
```

## Parse.py
<a id="parse.py"></a>

```python
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from typing import Optional, List, Dict
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import re 


class WebParser:
    def __init__(self):
        self.setup_logging()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    @staticmethod
    def setup_logging():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )

    @staticmethod
    def clean_text(text: str) -> str:
        return ' '.join(text.replace('\xa0', ' ').strip().split())

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            logging.error(f'Ошибка запроса {url}: {str(e)}')
            return None

    def parse_links(self, soup: BeautifulSoup) -> List[str]:
        """Сбор ссылок с главной страницы с двух разных селекторов"""
        links = []
        
        # Первый вариант (оригинальный селектор)
        for link in soup.select('div.cnc-product-categories-mob-card__header a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 1): {href}')
        
        # Второй вариант (новый селектор)
        for link in soup.select('div.cnc-short-list-product a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 2): {href}')
        
        # Удаление дубликатов с сохранением порядка
        seen = set()
        return [x for x in links if not (x in seen or seen.add(x))]

    def parse_features(self, soup: BeautifulSoup) -> Dict[str, str]:
        features = {}
        try:
            for feature_div in soup.find_all('div', class_='cnc-product-features__feature'):
                # Извлекаем название характеристики
                label = feature_div.find('span', class_='cnc-product-features__label')
                if not label:
                    continue
                
                feature_name = self.clean_text(label.text).rstrip(':')
                value_div = feature_div.find('div')

                if not feature_name or not value_div:
                    continue

                # Обработка разных форматов значений
                if value_div.find('a'):
                    # Случай со ссылкой
                    value = self.clean_text(value_div.find('a').text)
                elif value_div.find('ul'):
                    # Случай со списком
                    items = [self.clean_text(li.text) for li in value_div.find_all('li')]
                    value = ', '.join(items)
                else:
                    # Стандартный случай
                    value = self.clean_text(value_div.text.strip())

                features[feature_name] = value

        except Exception as e:
            logging.error(f'Ошибка парсинга характеристик: {str(e)}')
        
        return features

    def parse_product(self, soup: BeautifulSoup) -> Dict[str, str]:
        product_data = {
            'Товар': 'Н/Д',
            'Цена': 'Н/Д',
            'Описание': 'Н/Д',
            'Артикул': 'Н/Д'
        }

        try:
            # Основные данные
            title = soup.find('h1', class_='cnc-product-detail__title')
            if title:
                product_data['Товар'] = self.clean_text(title.text)

            price_div = soup.find('div', class_='cnc-product-detail__price-actual')
            if price_div:
                price = price_div.find('span', class_='ty-price-num')
                if price:
                    product_data['Цена'] = self.clean_text(price.text)

            description_div = soup.find('div', class_='cnc-product-description__left')
            if description_div:
                paragraphs = description_div.find_all(
                    'p', class_=lambda x: x != 'cnc-product-description__notice'
                )
                product_data['Описание'] = ' '.join(
                    self.clean_text(p.text) for p in paragraphs if p.text.strip()
                )

            sku = soup.find('span', class_='g-js-text-for-copy cnc-product-detail__product-code')
            if sku:
                product_data['Артикул'] = self.clean_text(sku.text)

            # Добавляем характеристики
            product_data.update(self.parse_features(soup))
            
            logging.info(f'Извлечено {len(product_data)-4} характеристик')

        except Exception as e:
            logging.error(f'Ошибка парсинга товара: {str(e)}')

        return product_data

    @staticmethod
    def save_to_excel(data: List[Dict], filename: str) -> None:
        try:
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            logging.info(f'Файл {filename} сохранён ({len(df.columns)} столбцов)')
        except Exception as e:
            logging.error(f'Ошибка сохранения: {str(e)}')

    @staticmethod
    def _normalize_to_first_page(url: str) -> str:
        """
        Приводит URL категории к виду: .../page-1/?items_per_page=48
        - удаляет завершающий сегмент /page-N/ если присутствует
        - гарантирует завершающий '/'
        - устанавливает items_per_page=48 (прочие query сохраняются)
        """
        parsed = urlparse(url)
        path = parsed.path or "/"

        # Удаляем конечный сегмент /page-N/ при наличии
        path = re.sub(r"/page-\d+/?$", "/", path)

        # Гарантируем завершающий '/'
        if not path.endswith("/"):
            path = path + "/"

        # Добавляем /page-1/ если его нет
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
        На каждой итерации возвращает (page_index, page_url, soup).
        Останавливается, когда на странице НЕТ div.cnc-pagination__show-more.
        При ошибке загрузки текущей страницы прекращает обход категории.
        """
        url = self._normalize_to_first_page(base_url)
        page = 1
        while True:
            logging.info(f"Загружаем страницу {page}: {url}")
            soup = self.get_page(url)
            if not soup:
                logging.warning(f"Ошибка загрузки страницы {page}: {url}")
                return  # прекращаем обход категории

            yield page, url, soup

            # На последней странице блока "показать ещё" нет
            show_more = soup.select_one("div.cnc-pagination__show-more")
            if not show_more:
                return

            page += 1
            parsed = urlparse(url)
            next_path = re.sub(r"/page-\d+/", f"/page-{page}/", parsed.path)
            url = urlunparse(parsed._replace(path=next_path))


    def iter_category_product_links(self, base_url: str) -> List[str]:
        """
        Возвращает все ссылки на товары из категории, обходя /page-1/, /page-2/, ...
        На каждой странице использует существующий parse_links(soup).
        Дубликаты убираются с сохранением порядка.
        """
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
```

## product_list_parser.py
<a id="product_list_parser.py"></a>

```python
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
```

## web_ui.py
<a id="web_ui.py"></a>

```python
# ui/web_ui.py
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from Parse import WebParser
from product_list_parser import ProductListParser


class StreamlitUI:
    """
    Класс UI‑обёртки для работы со Streamlit.

    Отвечает за:
        - конфигурацию страницы;
        - отрисовку вкладок/форм;
        - запуск соответствующих режимов парсинга;
        - отображение прогресса и результатов.
    """

    def __init__(self, parser: WebParser):
        """
        Параметры:
            parser: Экземпляр WebParser, переиспользуемый во всех режимах.
        """
        self.parser = parser
        self._setup_page_config()
        self.progress_bar = None
        self.status_text = None
        self.stats_placeholder = None

    # ------------------------------------------------------------------ #
    #                        BASIC PAGE CONFIG                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _setup_page_config() -> None:
        """Базовая конфигурация страницы Streamlit."""
        st.set_page_config(
            page_title="Web Parser",
            layout="centered",
            page_icon="🔍",
            initial_sidebar_state="expanded",
        )

    # ------------------------------------------------------------------ #
    #                        SIDEBAR / TABS                              #
    # ------------------------------------------------------------------ #
    def render_sidebar(self) -> Optional[dict]:
        """
        Отрисовка боковой панели с двумя вкладками:

        1. Парсинг Характеристик  (оригинальный режим, по стартовому URL)
        2. Табличный-парсинг Каталога (ProductListParser, список ссылок категорий)

        Возвращает:
            Словарь параметров выбранного режима либо None, если ещё ничего не запущено.
        """
        with st.sidebar:
            st.title("⚙️ Управление парсером")
            tab_start, tab_list = st.tabs(
                ["Парсинг Характеристик", "Табличный-парсинг Каталога"]
            )

            params: Optional[dict] = None

            # ---------- Вкладка 1 – Стартовый парсер ------------------- #
            with tab_start:
                url = st.text_input(
                    "Стартовый URL",
                    "https://example.com",
                    key="start_url",
                )
                output_file = st.text_input(
                    "Имя файла",
                    "products.xlsx",
                    key="start_output",
                )
                if st.button(
                    "🚀 Начать парсинг",
                    key="start_button",
                    width="stretch",
                ):
                    params = {
                        "mode": "start",  # UI-режим
                        "url": url,
                        "output": output_file,
                    }

            # ---------- Вкладка 2 – ProductListParser ------------------ #
            with tab_list:
                links_text = st.text_area(
                    "Ссылки категорий (по одной на строке)",
                    height=200,
                    placeholder="https://example.com/category/",
                    key="links_input",
                )

                # Новый выбор режима табличного парсинга
                mode_display_to_value = {
                    "basic (стандартный)": "basic",
                    "fulltable (расширенный)": "fulltable",
                }
                mode_label = st.selectbox(
                    "Режим табличного парсинга",
                    list(mode_display_to_value.keys()),
                    index=0,
                    key="catalog_mode",
                    help=(
                        "basic — старый режим с фиксированными колонками; "
                        "fulltable — расширенный режим, собирающий все данные "
                        "из карточек каталога без захода в карточку товара."
                    ),
                )
                parser_mode = mode_display_to_value[mode_label]

                output_file_links = st.text_input(
                    "Имя файла",
                    "product_list.xlsx",
                    key="links_output",
                )
                if st.button(
                    "🚀 Запустить",
                    key="list_button",
                    width="stretch",
                ):
                    raw_links = [
                        ln for ln in links_text.splitlines() if ln.strip()
                    ]
                    params = {
                        "mode": "productlist",       # UI-режим
                        "parser_mode": parser_mode,  # режим ProductListParser
                        "links": raw_links,
                        "output": output_file_links,
                    }

            st.markdown("---")
            self.stats_placeholder = st.empty()

        return params

    # ------------------------------------------------------------------ #
    #                       COMMON PROGRESS HELPERS                      #
    # ------------------------------------------------------------------ #
    def _init_progress(self) -> None:
        """Инициализация элементов прогресса."""
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.stats_placeholder = st.empty()

    def _update_progress(self, value: float, status: str) -> None:
        """
        Обновление индикатора прогресса.

        Параметры:
            value: Число от 0 до 100 (процент выполнения).
            status: Текстовый статус.
        """
        self.progress_bar.progress(int(value))
        self.status_text.markdown(f"**Статус:** {status}")

    def _show_stats(self, total: int, processed: int) -> None:
        """
        Отображение краткой статистики в сайдбаре.

        Параметры:
            total: Общее количество элементов.
            processed: Обработанное количество элементов.
        """
        self.stats_placeholder.markdown(
            f"""
        ### 📊 Прогресс
        - Всего: **{total}**
        - Обработано: **{processed}**
        - Осталось: **{total - processed}**
        """
        )

    # ------------------------------------------------------------------ #
    #                   RENDER RESULTS :  START PARSER                   #
    # ------------------------------------------------------------------ #
    def render_results(self, data: pd.DataFrame, filename: str) -> None:
        """
        Отрисовка результатов парсинга (оригинальный режим).

        Параметры:
            data:     DataFrame с результатами.
            filename: Имя файла для выгрузки Excel.
        """
        st.success("✅ Парсинг успешно завершен!")

        with st.expander("📁 Просмотр данных", expanded=True):
            st.dataframe(data, width="stretch", height=400)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            data.to_excel(writer, index=False, sheet_name="Products")

        st.download_button(
            label="💾 Скачать Excel",
            data=output.getvalue(),
            file_name=filename,
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            width="stretch",
        )

    # ------------------------------------------------------------------ #
    #               RENDER RESULTS :  PRODUCT LIST PARSER                #
    # ------------------------------------------------------------------ #
    def render_product_list_results(
        self,
        stats: Dict[str, Any],
        excel_content: bytes,
        filename: str,
    ) -> None:
        """
        Выводит сводную статистику + кнопку скачивания Excel с несколькими листами.

        Параметры:
            stats:         Сводная статистика, возвращённая ProductListParser.run().
            excel_content: Бинарный контент Excel‑файла.
            filename:      Имя файла для скачивания.
        """
        st.success("✅ Обработка списка ссылок завершена!")
        st.subheader("📊 Итоговая статистика")
        st.markdown(
            f"""
        - Режим: **{stats.get('mode', 'basic')}**
        - Всего ссылок: **{stats['total']}**
        - Успешно обработано: **{stats['success']}**
        - Ошибок: **{stats['failed']}**
        - Товаров собрано: **{stats['total_products']}**
        """
        )

        if stats["failed"]:
            with st.expander("⚠️ Ссылки с ошибками"):
                st.write(stats["failed_links"])

        # кнопка скачивания много‑листового файла
        st.download_button(
            label="💾 Скачать Excel",
            data=excel_content,
            file_name=filename,
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            width="stretch",
        )

    # ------------------------------------------------------------------ #
    #                             MAIN LOOP                              #
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """Главный метод запуска UI‑цикла."""
        st.title("🔍 Web Parser")

        params = self.render_sidebar()
        if not params:
            return

        self._init_progress()
        try:
            if params["mode"] == "start":
                result = self._run_parsing(params)
                if result:
                    self.render_results(*result)
            else:  # mode == "productlist"
                stats, excel_data, out_file = self._run_product_list(params)
                self.render_product_list_results(stats, excel_data, out_file)
        except Exception as exc:  # noqa: BLE001 — выводим ошибку пользователю
            st.error(f"⛔ Ошибка: {exc}")
        finally:
            time.sleep(0.5)
            self.progress_bar.empty()
            self.status_text.empty()

    # ------------------------------------------------------------------ #
    #                      ORIGINAL START‑PARSER FLOW                    #
    # ------------------------------------------------------------------ #
    def _run_parsing(self, params: dict) -> Optional[Tuple[pd.DataFrame, str]]:
        """
        Процесс парсинга для стартового URL (оригинальный режим).

        Параметры:
            params: Словарь параметров из сайдбара, ожидает ключи:
                - "url":    стартовый URL категории;
                - "output": имя выходного файла.

        Возвращает:
            Кортеж (DataFrame, имя файла) либо None.
        """
        links = self.parser.iter_category_product_links(params["url"])
        if not links:
            raise Exception("Ссылки на товары не найдены")

        self._update_progress(15, "Поиск ссылок на товары…")
        total = len(links)
        products: List[Dict[str, Any]] = []

        for idx, link in enumerate(links, 1):
            try:
                progress = 15 + int(70 * (idx / total))
                self._update_progress(
                    progress,
                    f"Обработка товара {idx}/{total}",
                )
                self._show_stats(total, idx)

                with st.spinner(f"Обработка: {link.split('/')[-1]}"):
                    product_page = self.parser.get_page(link)
                    if product_page:
                        products.append(self.parser.parse_product(product_page))
                    # Имитация небольшой задержки, чтобы прогресс был нагляднее
                    time.sleep(0.1)
            except Exception as ex:  # noqa: BLE001
                st.warning(f"Пропущен товар {idx}: {ex}")

        self._update_progress(95, "Формирование отчёта…")
        df = pd.DataFrame(products)
        if df.empty:
            raise Exception("Не удалось собрать данные")

        return df, params["output"]

    # ------------------------------------------------------------------ #
    #                 NEW FLOW  –  PRODUCT LIST PARSER                   #
    # ------------------------------------------------------------------ #
    def _run_product_list(
        self,
        params: dict,
    ) -> Tuple[Dict[str, Any], bytes, str]:
        """
        Обработка произвольного списка URL‑адресов категорий.

        Для каждой категории:
            - обходит /page-1/, /page-2/, ... (логика в ProductListParser);
            - агрегирует все страницы категории в один лист Excel.

        Параметры:
            params: Словарь параметров из сайдбара, ожидает ключи:
                - "links":        список URL категорий;
                - "output":       имя выходного файла;
                - "parser_mode":  режим ProductListParser ("basic"/"fulltable").

        Возвращает:
            (stats, excel_bytes, output_filename)
        """
        links: List[str] = params["links"]
        total = len(links)
        if total == 0:
            raise Exception("Список ссылок пуст")

        parser_mode: str = params.get("parser_mode", "basic")

        self._update_progress(
            5,
            f"Инициализация ProductListParser (режим: {parser_mode})…",
        )
        pl_parser = ProductListParser(
            links=links,
            output_file=params["output"],
            base_parser=self.parser,
            mode=parser_mode,
        )

        # весь обход /page-N/ и сбор строк — внутри ProductListParser.run()
        self._update_progress(20, "Сканирование страниц и сбор данных…")
        _, stats = pl_parser.run()

        self._update_progress(95, "Формирование отчёта…")
        excel_bytes = pl_parser.save_results()
        return stats, excel_bytes, params["output"]
```

## Project Docs/
<a id="project-docs"></a>

### ExistModuleCode.md
<a id="project-docs-existmodulecode.md"></a>

```md
# Единый **source of truth** кодовой базы

- Документ сформирован автоматически.
- Корень обхода: `D:/Git/streamlit-parser/app`
- Время сборки: 2025-12-08 16:38:45 RTZ 2 (зима)
- Всего модулей: 4
- Пустых модулей: 0

# Дерево абсолютных импортов модулей (Python)

> Имена приведены в точечной нотации; соответствуют абсолютным путям импортов.

- [App](#app.py)
- [Parse](#parse.py)
- [product_list_parser](#product_list_parser.py)
- [web_ui](#web_ui.py)

# Актуальный код

## App.py
<a id="app.py"></a>

```python
from Parse import WebParser
from web_ui import StreamlitUI

def main():
    parser = WebParser()
    
    is_streamlit_running()
    ui = StreamlitUI(parser)
    ui.run()

def is_streamlit_running() -> bool:
    """Проверка запущен ли Streamlit"""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except ImportError:
        return False

if __name__ == "__main__":
    main()
```

## Parse.py
<a id="parse.py"></a>

```python
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from typing import Optional, List, Dict
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode  # [+] для нормализации URL
import re  # [+] для работы с /page-N/


class WebParser:
    def __init__(self):
        self.setup_logging()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    @staticmethod
    def setup_logging():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )

    @staticmethod
    def clean_text(text: str) -> str:
        return ' '.join(text.replace('\xa0', ' ').strip().split())

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            logging.error(f'Ошибка запроса {url}: {str(e)}')
            return None

    def parse_links(self, soup: BeautifulSoup) -> List[str]:
        """Сбор ссылок с главной страницы с двух разных селекторов"""
        links = []
        
        # Первый вариант (оригинальный селектор)
        for link in soup.select('div.cnc-product-categories-mob-card__header a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 1): {href}')
        
        # Второй вариант (новый селектор)
        for link in soup.select('div.cnc-short-list-product a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 2): {href}')
        
        # Удаление дубликатов с сохранением порядка
        seen = set()
        return [x for x in links if not (x in seen or seen.add(x))]

    def parse_features(self, soup: BeautifulSoup) -> Dict[str, str]:
        features = {}
        try:
            for feature_div in soup.find_all('div', class_='cnc-product-features__feature'):
                # Извлекаем название характеристики
                label = feature_div.find('span', class_='cnc-product-features__label')
                if not label:
                    continue
                
                feature_name = self.clean_text(label.text).rstrip(':')
                value_div = feature_div.find('div')

                if not feature_name or not value_div:
                    continue

                # Обработка разных форматов значений
                if value_div.find('a'):
                    # Случай со ссылкой
                    value = self.clean_text(value_div.find('a').text)
                elif value_div.find('ul'):
                    # Случай со списком
                    items = [self.clean_text(li.text) for li in value_div.find_all('li')]
                    value = ', '.join(items)
                else:
                    # Стандартный случай
                    value = self.clean_text(value_div.text.strip())

                features[feature_name] = value

        except Exception as e:
            logging.error(f'Ошибка парсинга характеристик: {str(e)}')
        
        return features

    def parse_product(self, soup: BeautifulSoup) -> Dict[str, str]:
        product_data = {
            'Товар': 'Н/Д',
            'Цена': 'Н/Д',
            'Описание': 'Н/Д',
            'Артикул': 'Н/Д'
        }

        try:
            # Основные данные
            title = soup.find('h1', class_='cnc-product-detail__title')
            if title:
                product_data['Товар'] = self.clean_text(title.text)

            price_div = soup.find('div', class_='cnc-product-detail__price-actual')
            if price_div:
                price = price_div.find('span', class_='ty-price-num')
                if price:
                    product_data['Цена'] = self.clean_text(price.text)

            description_div = soup.find('div', class_='cnc-product-description__left')
            if description_div:
                paragraphs = description_div.find_all(
                    'p', class_=lambda x: x != 'cnc-product-description__notice'
                )
                product_data['Описание'] = ' '.join(
                    self.clean_text(p.text) for p in paragraphs if p.text.strip()
                )

            sku = soup.find('span', class_='g-js-text-for-copy cnc-product-detail__product-code')
            if sku:
                product_data['Артикул'] = self.clean_text(sku.text)

            # Добавляем характеристики
            product_data.update(self.parse_features(soup))
            
            logging.info(f'Извлечено {len(product_data)-4} характеристик')

        except Exception as e:
            logging.error(f'Ошибка парсинга товара: {str(e)}')

        return product_data

    @staticmethod
    def save_to_excel(data: List[Dict], filename: str) -> None:
        try:
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            logging.info(f'Файл {filename} сохранён ({len(df.columns)} столбцов)')
        except Exception as e:
            logging.error(f'Ошибка сохранения: {str(e)}')

    @staticmethod
    def _normalize_to_first_page(url: str) -> str:
        """
        Приводит URL категории к виду: .../page-1/?items_per_page=48
        - удаляет завершающий сегмент /page-N/ если присутствует
        - гарантирует завершающий '/'
        - устанавливает items_per_page=48 (прочие query сохраняются)
        """
        parsed = urlparse(url)
        path = parsed.path or "/"

        # Удаляем конечный сегмент /page-N/ при наличии
        path = re.sub(r"/page-\d+/?$", "/", path)

        # Гарантируем завершающий '/'
        if not path.endswith("/"):
            path = path + "/"

        # Добавляем /page-1/ если его нет
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
        На каждой итерации возвращает (page_index, page_url, soup).
        Останавливается, когда на странице НЕТ div.cnc-pagination__show-more.
        При ошибке загрузки текущей страницы прекращает обход категории.
        """
        url = self._normalize_to_first_page(base_url)
        page = 1
        while True:
            logging.info(f"Загружаем страницу {page}: {url}")
            soup = self.get_page(url)
            if not soup:
                logging.warning(f"Ошибка загрузки страницы {page}: {url}")
                return  # прекращаем обход категории

            yield page, url, soup

            # На последней странице блока "показать ещё" нет
            show_more = soup.select_one("div.cnc-pagination__show-more")
            if not show_more:
                return

            page += 1
            parsed = urlparse(url)
            next_path = re.sub(r"/page-\d+/", f"/page-{page}/", parsed.path)
            url = urlunparse(parsed._replace(path=next_path))


    def iter_category_product_links(self, base_url: str) -> List[str]:
        """
        Возвращает все ссылки на товары из категории, обходя /page-1/, /page-2/, ...
        На каждой странице использует существующий parse_links(soup).
        Дубликаты убираются с сохранением порядка.
        """
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
```

## product_list_parser.py
<a id="product_list_parser.py"></a>

```python
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
```

## web_ui.py
<a id="web_ui.py"></a>

```python
# ui/web_ui.py
import streamlit as st
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from Parse import WebParser
from product_list_parser import ProductListParser


class StreamlitUI:
    def __init__(self, parser: WebParser):
        self.parser = parser
        self._setup_page_config()
        self.progress_bar = None
        self.status_text = None
        self.stats_placeholder = None

    # ------------------------------------------------------------------ #
    #                        BASIC PAGE CONFIG                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _setup_page_config():
        st.set_page_config(
            page_title="Web Parser",
            layout="centered",
            page_icon="🔍",
            initial_sidebar_state="expanded",
        )

    # ------------------------------------------------------------------ #
    #                        SIDEBAR / TABS                              #
    # ------------------------------------------------------------------ #
    def render_sidebar(self) -> Optional[dict]:
        """Отрисовка боковой панели с двумя вкладками:
        1. Стартовый парсер  (старый функционал)
        2. ProductListParser (массовый парсинг списка ссылок)
        """
        with st.sidebar:
            st.title("⚙️ Управление парсером")
            tab_start, tab_list = st.tabs(["Парсинг Характеристик", "Парсинг Каталога"])

            params: Optional[dict] = None

            # ---------- Вкладка 1 – Стартовый парсер ------------------- #
            with tab_start:
                url = st.text_input(
                    "Стартовый URL", "https://example.com", key="start_url"
                )
                output_file = st.text_input(
                    "Имя файла", "products.xlsx", key="start_output"
                )
                if st.button(
                    "🚀 Начать парсинг", key="start_button", width='stretch'
                ):
                    params = {
                        "mode": "start",
                        "url": url,
                        "output": output_file,
                    }

            # ---------- Вкладка 2 – ProductListParser ------------------ #
            with tab_list:
                links_text = st.text_area(
                    "Ссылки (по одной на строке)",
                    height=200,
                    placeholder="https://example.com/product/123",
                    key="links_input",
                )
                output_file_links = st.text_input(
                    "Имя файла",
                    "product_list.xlsx",
                    key="links_output",
                )
                if st.button(
                    "🚀 Запустить",
                    key="list_button",
                    width='stretch',
                ):
                    raw_links = [ln for ln in links_text.splitlines() if ln.strip()]
                    params = {
                        "mode": "productlist",
                        "links": raw_links,
                        "output": output_file_links,
                    }

            st.markdown("---")
            self.stats_placeholder = st.empty()

        return params

    # ------------------------------------------------------------------ #
    #                       COMMON PROGRESS HELPERS                      #
    # ------------------------------------------------------------------ #
    def _init_progress(self):
        """Инициализация элементов прогресса"""
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.stats_placeholder = st.empty()

    def _update_progress(self, value: float, status: str):
        """Обновление индикатора прогресса"""
        self.progress_bar.progress(int(value))
        self.status_text.markdown(f"**Статус:** {status}")

    def _show_stats(self, total: int, processed: int):
        """Отображение статистики"""
        self.stats_placeholder.markdown(
            f"""
        ### 📊 Прогресс
        - Всего: **{total}**
        - Обработано: **{processed}**
        - Осталось: **{total - processed}**
        """
        )

    # ------------------------------------------------------------------ #
    #                   RENDER RESULTS :  START PARSER                   #
    # ------------------------------------------------------------------ #
    def render_results(self, data: pd.DataFrame, filename: str):
        """Отрисовка результатов парсинга (старый режим)"""
        st.success("✅ Парсинг успешно завершен!")

        with st.expander("📁 Просмотр данных", expanded=True):
            st.dataframe(data, width='stretch', height=400)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            data.to_excel(writer, index=False, sheet_name="Products")

        st.download_button(
            label="💾 Скачать Excel",
            data=output.getvalue(),
            file_name=filename,
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            width='stretch',
        )

    # ------------------------------------------------------------------ #
    #               RENDER RESULTS :  PRODUCT LIST PARSER                #
    # ------------------------------------------------------------------ #
    def render_product_list_results(
        self,
        stats: Dict[str, Any],
        excel_content: bytes,
        filename: str,
    ):
        """Выводит сводную статистику + кнопку скачивания Excel с несколькими листами"""
        st.success("✅ Обработка списка ссылок завершена!")
        st.subheader("📊 Итоговая статистика")
        st.markdown(
            f"""
        - Всего ссылок: **{stats['total']}**
        - Успешно обработано: **{stats['success']}**
        - Ошибок: **{stats['failed']}**
        - Товаров собрано: **{stats['total_products']}**
        """
        )

        if stats["failed"]:
            with st.expander("⚠️ Ссылки с ошибками"):
                st.write(stats["failed_links"])

        # кнопка скачивания много-листового файла
        st.download_button(
            label="💾 Скачать Excel",
            data=excel_content,
            file_name=filename,
            mime=(
                "application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            width='stretch',
        )

    # ------------------------------------------------------------------ #
    #                             MAIN LOOP                              #
    # ------------------------------------------------------------------ #
    def run(self):
        st.title("🔍 Web Parser")

        params = self.render_sidebar()
        if not params:
            return

        self._init_progress()
        try:
            if params["mode"] == "start":
                result = self._run_parsing(params)
                if result:
                    self.render_results(*result)
            else:  # mode == productlist
                stats, excel_data, out_file = self._run_product_list(params)
                self.render_product_list_results(stats, excel_data, out_file)
        except Exception as exc:
            st.error(f"⛔ Ошибка: {exc}")
        finally:
            time.sleep(0.5)
            self.progress_bar.empty()
            self.status_text.empty()

    # ------------------------------------------------------------------ #
    #                      ORIGINAL START‑PARSER FLOW                    #
    # ------------------------------------------------------------------ #
    def _run_parsing(self, params: dict) -> Optional[Tuple[pd.DataFrame, str]]:
        """Процесс парсинга для стартового URL (оригинальный режим)"""
        links = self.parser.iter_category_product_links(params["url"])
        if not links:
            raise Exception("Ссылки на товары не найдены")

        self._update_progress(15, "Поиск ссылок на товары…")
        total = len(links)
        products: List[Dict[str, Any]] = []

        for idx, link in enumerate(links, 1):
            try:
                progress = 15 + int(70 * (idx / total))
                self._update_progress(progress, f"Обработка товара {idx}/{total}")
                self._show_stats(total, idx)

                with st.spinner(f"Обработка: {link.split('/')[-1]}"):
                    product_page = self.parser.get_page(link)
                    if product_page:
                        products.append(self.parser.parse_product(product_page))
                    time.sleep(0.1)  # имитация задержки
            except Exception as ex:
                st.warning(f"Пропущен товар {idx}: {ex}")

        self._update_progress(95, "Формирование отчёта…")
        df = pd.DataFrame(products)
        if df.empty:
            raise Exception("Не удалось собрать данные")

        return df, params["output"]

    # ------------------------------------------------------------------ #
    #                 NEW FLOW  –  PRODUCT LIST PARSER                   #
    # ------------------------------------------------------------------ #
    def _run_product_list(
        self, params: dict
    ) -> Tuple[Dict[str, Any], bytes, str]:
        """Обработка произвольного списка URL-адресов (агрегация страниц в одном листе на URL)"""
        links: List[str] = params["links"]
        total = len(links)
        if total == 0:
            raise Exception("Список ссылок пуст")

        self._update_progress(5, "Инициализация ProductListParser…")
        pl_parser = ProductListParser(
            links=links, output_file=params["output"], base_parser=self.parser
        )

        # весь обход /page-N/ и сбор строк — внутри ProductListParser.run()
        self._update_progress(20, "Сканирование страниц и сбор данных…")
        _, stats = pl_parser.run()

        self._update_progress(95, "Формирование отчёта…")
        excel_bytes = pl_parser.save_results()
        return stats, excel_bytes, params["output"]
```
```

### NewFeature.md
<a id="project-docs-newfeature.md"></a>

```md
# **Техническое задание: Расширенный режим табличного парсинга каталога**

## 1. **Цель обновления**

Расширить функционал `ProductListParser`, добавив новый режим обработки, позволяющий:

* собирать **всю доступную информацию** из блоков/таблиц на страницах категорий;
* работать **аналогично текущему ProductListParser** (обход `/page-N/`, агрегация в один лист Excel);
* не заходить во внутренние карточки товара;
* поддерживать динамический набор колонок;
* сохранить совместимость со старым режимом (basic mode).

---

# 2. **Параметры нового режима**

В `ProductListParser.__init__` добавить параметр:

```python
mode: str = "basic"
```

Допустимые значения:

* `"basic"` — текущий режим, использующий `_parse_category_page()`, `_extract_row_data_v1`, `_extract_row_data_v2`.
* `"fulltable"` — новый режим, использующий универсальный парсер таблиц/блоков.

---

# 3. **Поведение режима `fulltable`**

## 3.1. Источники данных

Использовать те же DOM-селекторы, что и `_parse_category_page()`:

* `div.cnc-product-categories-mob-card` (табличная верстка v1)
* `div.cnc-short-list-product` (блочная верстка v2)

Но вместо точечного извлечения «5 фиксированных полей» — извлекать **все подэлементы** строки.

## 3.2. Новый универсальный экстрактор `_extract_row_full(row: Tag)`:

Требования:

1. Собрать все текстовые значения из вложенных:
   
   * `<div>`
   * `<span>`
   * `<p>`
   * `<a>`
   * `<li>` и т. д.

2. Извлечь **все атрибуты**, которые несут значение:
   
   * `data-*`
   * `title`
   * `alt`

3. Сформировать структуру:

```python
{
    "col_1": "...",
    "col_2": "...",
    "col_3": "...",
    ...
}
```

или, если возможно, использовать реальные имена колонок, если таблица содержит `<th>`.

4. Удалить:
* пустые строки

* управляющие символы

* повторяющиеся значения (если они буквально дублируют друг друга)
5. Применять очистку текста по аналогии с текущими `_clean_text` / `WebParser.clean_text`.

---

# 4. **Новый метод `_parse_full_table_page()`**

Создать новый метод:

```python
def _parse_full_table_page(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
```

Требования:

1. Найти все строки товаров:
   
   * `div.cnc-product-categories-mob-card`
   * `div.cnc-short-list-product`

2. Для каждого найденного блока вызвать `_extract_row_full()`.

3. Возвращать список словарей.

Если блоки не найдены → вернуть пустой список (поведение аналогично базовому режиму).

---

# 5. **Интеграция с run()**

Внутри `run()` заменить строку:

```python
products = self._parse_category_page(soup)
```

на:

```python
if self.mode == "fulltable":
    products = self._parse_full_table_page(soup)
else:
    products = self._parse_category_page(soup)
```

Остальная логика `run()` остаётся неизменной.

---

# 6. **Сохранение Excel**

Система листов Excel должна работать **без изменений**:

* имя листа = название категории (`_extract_page_title`)
* все товары из всех страниц одной категории → один лист
* колонки — объединённый набор всех ключей из row-dict

Pandas автоматически выровняет отсутствующие колонки заполнением `NaN`.

---

# 7. **UI-изменения (минимальные)**

В `StreamlitUI.render_sidebar()` добавить новую вкладку или опцию:

```python
mode = st.selectbox(
    "Режим", 
    ["basic (стандартный)", "fulltable (расширенный)"],
    index=0
)
```

В параметры передавать:

```python
"mode": "fulltable"
```

В вызове:

```python
pl_parser = ProductListParser(
    links=links,
    output_file=params["output"],
    base_parser=self.parser,
    mode=params["mode"]
)
```

---

# 8. **Ограничения и требования**

1. Не изменять структуру существующих методов:
   
   * `_iter_paginated_pages`
   * `_normalize_to_first_page`
   * `_make_unique_sheet_name`
   * `save_results`

2. Не изменять `WebParser` и его `parse_product()`, чтобы не смешивать два разных механизма.

3. Полная обратная совместимость:
   
   * Старый режим `basic` должен работать без изменений.
   * Новый режим должен быть опциональным.

4. Код должен соблюдать принципы проекта:
   
   * строгая модульность;
   * отсутствие циклических зависимостей;
   * ООП-подход: отдельный метод для полного извлечения, без вмешательства в существующие extract-функции.

---

# 9. **Результат, который должен появиться**

### Новый режим позволит:

* Собрать *все текстовые данные* из каждой табличной/блочной карточки товара в каталоге.
* Автоматически формировать Excel с максимальным количеством информации.
* Работать на любых версиях HTML-разметки, даже если структура карточек расширена.

---

# 10. **Объём изменений**

* Добавить 1 параметр в `__init__`

* Добавить 2 новых метода:
  
  * `_extract_row_full`
  * `_parse_full_table_page`

* 1 строка модификации в `run()`

* Малое изменение UI

Общий объём — **локальный и безопасный**, не затрагивает обработку характеристик и исходный WebParser.
```

### Roadmap.md
<a id="project-docs-roadmap.md"></a>

```md
# Roadmap интеграции `ProductListParser`  
*(покомпонентно‑итеративный подход)*  

> Документ описывает поэтапный план встраивания режима парсинга по списку ссылок в существующую архитектуру **Web Parser**. Базовые модули (`App.py`, `Parse.py`, `web_ui.py`) остаются «источником истины» и не ломаются — мы надстраиваемся поверх них.

---
## 1. Цель
Расширить функциональность, позволив пользователю загружать набор URL‑ов карточек товаров, автоматически собирать данные и получать сводную статистику с XLSX‑отчётом.

---
## 2. Принципы реализации
| Принцип | Что это значит на практике |
|---------|---------------------------|
| **Покомпонентность** | Меняем/добавляем один файл за раз, фиксируем; остальной код компилируется и тесты проходят. |
| **Итеративность** | Каждая итерация ≤ 1–2 раб. дня, завершается работающей «микрофичей» и ревью. |
| **Пере‑использование** | Никакой дублирующей логики: `ProductListParser` вызывает публичные методы `WebParser`. |
| **Обратная совместимость** | Режим «Стартовый парсер» работает как раньше; UI переключается вкладкой. |

---
## 3. Итерации и вехи
| # | Итерация / Веха | Основные задачи | Артефакты | Длит.* |
|---|-----------------|-----------------|-----------|--------|
| 0 | **Подготовка** | • Создать ветку `feature/product‑list`<br>• Настроить playground‑данные (3 валидные + 1 битая ссылка)<br>• Сгенерировать пустые юнит‑тесты | `tests/test_product_list_parser.py` | 0.5 д |
| 1 | **Новый класс `ProductListParser`** | • Скелет класса (init, валидация ссылок)<br>• Утилита `normalize_links()`<br>• Логирование | `product_list_parser.py` | 1 д |
| 2 | **Бизнес‑цикл** | • Метод `run()` с цикл‑обработкой ссылок (последовательный)<br>• Счётчики `total / success / failed` | Обновл. `product_list_parser.py` | 1 д |
| 3 | **Интеграция с UI** | • В `web_ui.py` добавить `st.tabs()` («Стартовый», «ProductList»)<br>• Новые поля ввода: `st.text_area` + `st.text_input` | Патч `web_ui.py` | 0.5 д |
| 4 | **Прогресс‑бар & статистика** | • Переиспользовать `_init_progress()` / `_update_progress()`<br>• Блок резюме: `st.success/fail` | Патч `web_ui.py` | 0.5 д |
| 5 | **Скачивание XLSX** | • Формирование файла в памяти (`BytesIO + pd.ExcelWriter`)<br>• `st.download_button` | XLSX‑аут, e2e‑тест | 0.5 д |
| 6 | **Тесты & CI** | • Покрытие: ≥ 80 % для нового кода<br>• GitHub Action → pytest + flake8 | `README_dev.md` + badge | 1 д |
| 7 | **Код‑ревью / Merge** | • Финальный рефакторинг (typing, docstrings)<br>• Обновить `ExistModuls.md`, добавить ссылку на `NewFeature.md` | Pull Request → `main` | 0.5 д |

\*Длительность указана ориентировочно (рабочие дни).

---

## 4. Диаграмма потоков данных (текст)
```text
UI (Streamlit, вкладка ProductList)
│ links, filename
▼
ProductListParser.run()
│ (итеративно)
▼
WebParser.get\_page() ➜ WebParser.parse\_product()
│ dict
▼
DataFrame ← агрегирует
│
▼
BytesIO (XLSX) → UI.download\_button
```

---
## 5. Риски и смягчения
| Риск | Мера |
|------|------|
| Некачественные ссылки тормозят цикл | Таймаут requests (10 с) + рetry = 3 |
| Неочевидная UX‑переключалка | Чёткие лейблы вкладок + Tooltip |
| Рост зависимостей | Используем уже установленные пакеты (`requests`, `bs4`, `pandas`, `xlsxwriter`) |
| Потеря данных при падении | Сохраняем частичные результаты каждые N ссылок (TODO v2) |

---
## 6. Definition of Done
* ✔ Все итерации смержены в `main`, CI зелёный.  
* ✔ Режим «Стартовый парсер» работает без регрессий.  
* ✔ При вводе ≥ 1 ссылки пользователь получает корректный XLSX + статистику.  
* ✔ Документация обновлена (`ExistModuls.md`, `README.md`).  
* ✔ Code Coverage ≥ 80 %, все TODO вынесены в issue‑трекер.

---
## 7. Post‑MVP бэклог
* Асинхронная обработка (`aiohttp`, семафор 10 запросов).  
* DnD‑загрузка CSV/Excel со ссылками.  
* Кэширование по URL (hashing + pickle).  
* Экспорт ошибок в отдельный XLSX «failed_links.xlsx».
```
```

### NewFeature.md
<a id="project-docs-newfeature.md"></a>

```md
# **Техническое задание: Расширенный режим табличного парсинга каталога**

## 1. **Цель обновления**

Расширить функционал `ProductListParser`, добавив новый режим обработки, позволяющий:

* собирать **всю доступную информацию** из блоков/таблиц на страницах категорий;
* работать **аналогично текущему ProductListParser** (обход `/page-N/`, агрегация в один лист Excel);
* не заходить во внутренние карточки товара;
* поддерживать динамический набор колонок;
* сохранить совместимость со старым режимом (basic mode).

---

# 2. **Параметры нового режима**

В `ProductListParser.__init__` добавить параметр:

```python
mode: str = "basic"
```

Допустимые значения:

* `"basic"` — текущий режим, использующий `_parse_category_page()`, `_extract_row_data_v1`, `_extract_row_data_v2`.
* `"fulltable"` — новый режим, использующий универсальный парсер таблиц/блоков.

---

# 3. **Поведение режима `fulltable`**

## 3.1. Источники данных

Использовать те же DOM-селекторы, что и `_parse_category_page()`:

* `div.cnc-product-categories-mob-card` (табличная верстка v1)
* `div.cnc-short-list-product` (блочная верстка v2)

Но вместо точечного извлечения «5 фиксированных полей» — извлекать **все подэлементы** строки.

## 3.2. Новый универсальный экстрактор `_extract_row_full(row: Tag)`:

Требования:

1. Собрать все текстовые значения из вложенных:
   
   * `<div>`
   * `<span>`
   * `<p>`
   * `<a>`
   * `<li>` и т. д.

2. Извлечь **все атрибуты**, которые несут значение:
   
   * `data-*`
   * `title`
   * `alt`

3. Сформировать структуру:

```python
{
    "col_1": "...",
    "col_2": "...",
    "col_3": "...",
    ...
}
```

или, если возможно, использовать реальные имена колонок, если таблица содержит `<th>`.

4. Удалить:
* пустые строки

* управляющие символы

* повторяющиеся значения (если они буквально дублируют друг друга)
5. Применять очистку текста по аналогии с текущими `_clean_text` / `WebParser.clean_text`.

---

# 4. **Новый метод `_parse_full_table_page()`**

Создать новый метод:

```python
def _parse_full_table_page(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
```

Требования:

1. Найти все строки товаров:
   
   * `div.cnc-product-categories-mob-card`
   * `div.cnc-short-list-product`

2. Для каждого найденного блока вызвать `_extract_row_full()`.

3. Возвращать список словарей.

Если блоки не найдены → вернуть пустой список (поведение аналогично базовому режиму).

---

# 5. **Интеграция с run()**

Внутри `run()` заменить строку:

```python
products = self._parse_category_page(soup)
```

на:

```python
if self.mode == "fulltable":
    products = self._parse_full_table_page(soup)
else:
    products = self._parse_category_page(soup)
```

Остальная логика `run()` остаётся неизменной.

---

# 6. **Сохранение Excel**

Система листов Excel должна работать **без изменений**:

* имя листа = название категории (`_extract_page_title`)
* все товары из всех страниц одной категории → один лист
* колонки — объединённый набор всех ключей из row-dict

Pandas автоматически выровняет отсутствующие колонки заполнением `NaN`.

---

# 7. **UI-изменения (минимальные)**

В `StreamlitUI.render_sidebar()` добавить новую вкладку или опцию:

```python
mode = st.selectbox(
    "Режим", 
    ["basic (стандартный)", "fulltable (расширенный)"],
    index=0
)
```

В параметры передавать:

```python
"mode": "fulltable"
```

В вызове:

```python
pl_parser = ProductListParser(
    links=links,
    output_file=params["output"],
    base_parser=self.parser,
    mode=params["mode"]
)
```

---

# 8. **Ограничения и требования**

1. Не изменять структуру существующих методов:
   
   * `_iter_paginated_pages`
   * `_normalize_to_first_page`
   * `_make_unique_sheet_name`
   * `save_results`

2. Не изменять `WebParser` и его `parse_product()`, чтобы не смешивать два разных механизма.

3. Полная обратная совместимость:
   
   * Старый режим `basic` должен работать без изменений.
   * Новый режим должен быть опциональным.

4. Код должен соблюдать принципы проекта:
   
   * строгая модульность;
   * отсутствие циклических зависимостей;
   * ООП-подход: отдельный метод для полного извлечения, без вмешательства в существующие extract-функции.

---

# 9. **Результат, который должен появиться**

### Новый режим позволит:

* Собрать *все текстовые данные* из каждой табличной/блочной карточки товара в каталоге.
* Автоматически формировать Excel с максимальным количеством информации.
* Работать на любых версиях HTML-разметки, даже если структура карточек расширена.

---

# 10. **Объём изменений**

* Добавить 1 параметр в `__init__`

* Добавить 2 новых метода:
  
  * `_extract_row_full`
  * `_parse_full_table_page`

* 1 строка модификации в `run()`

* Малое изменение UI

Общий объём — **локальный и безопасный**, не затрагивает обработку характеристик и исходный WebParser.
```

### Roadmap.md
<a id="project-docs-roadmap.md"></a>

```md
# Roadmap интеграции `ProductListParser`  
*(покомпонентно‑итеративный подход)*  

> Документ описывает поэтапный план встраивания режима парсинга по списку ссылок в существующую архитектуру **Web Parser**. Базовые модули (`App.py`, `Parse.py`, `web_ui.py`) остаются «источником истины» и не ломаются — мы надстраиваемся поверх них.

---
## 1. Цель
Расширить функциональность, позволив пользователю загружать набор URL‑ов карточек товаров, автоматически собирать данные и получать сводную статистику с XLSX‑отчётом.

---
## 2. Принципы реализации
| Принцип | Что это значит на практике |
|---------|---------------------------|
| **Покомпонентность** | Меняем/добавляем один файл за раз, фиксируем; остальной код компилируется и тесты проходят. |
| **Итеративность** | Каждая итерация ≤ 1–2 раб. дня, завершается работающей «микрофичей» и ревью. |
| **Пере‑использование** | Никакой дублирующей логики: `ProductListParser` вызывает публичные методы `WebParser`. |
| **Обратная совместимость** | Режим «Стартовый парсер» работает как раньше; UI переключается вкладкой. |

---
## 3. Итерации и вехи
| # | Итерация / Веха | Основные задачи | Артефакты | Длит.* |
|---|-----------------|-----------------|-----------|--------|
| 0 | **Подготовка** | • Создать ветку `feature/product‑list`<br>• Настроить playground‑данные (3 валидные + 1 битая ссылка)<br>• Сгенерировать пустые юнит‑тесты | `tests/test_product_list_parser.py` | 0.5 д |
| 1 | **Новый класс `ProductListParser`** | • Скелет класса (init, валидация ссылок)<br>• Утилита `normalize_links()`<br>• Логирование | `product_list_parser.py` | 1 д |
| 2 | **Бизнес‑цикл** | • Метод `run()` с цикл‑обработкой ссылок (последовательный)<br>• Счётчики `total / success / failed` | Обновл. `product_list_parser.py` | 1 д |
| 3 | **Интеграция с UI** | • В `web_ui.py` добавить `st.tabs()` («Стартовый», «ProductList»)<br>• Новые поля ввода: `st.text_area` + `st.text_input` | Патч `web_ui.py` | 0.5 д |
| 4 | **Прогресс‑бар & статистика** | • Переиспользовать `_init_progress()` / `_update_progress()`<br>• Блок резюме: `st.success/fail` | Патч `web_ui.py` | 0.5 д |
| 5 | **Скачивание XLSX** | • Формирование файла в памяти (`BytesIO + pd.ExcelWriter`)<br>• `st.download_button` | XLSX‑аут, e2e‑тест | 0.5 д |
| 6 | **Тесты & CI** | • Покрытие: ≥ 80 % для нового кода<br>• GitHub Action → pytest + flake8 | `README_dev.md` + badge | 1 д |
| 7 | **Код‑ревью / Merge** | • Финальный рефакторинг (typing, docstrings)<br>• Обновить `ExistModuls.md`, добавить ссылку на `NewFeature.md` | Pull Request → `main` | 0.5 д |

\*Длительность указана ориентировочно (рабочие дни).

---

## 4. Диаграмма потоков данных (текст)
```text
UI (Streamlit, вкладка ProductList)
│ links, filename
▼
ProductListParser.run()
│ (итеративно)
▼
WebParser.get\_page() ➜ WebParser.parse\_product()
│ dict
▼
DataFrame ← агрегирует
│
▼
BytesIO (XLSX) → UI.download\_button
```

---
## 5. Риски и смягчения
| Риск | Мера |
|------|------|
| Некачественные ссылки тормозят цикл | Таймаут requests (10 с) + рetry = 3 |
| Неочевидная UX‑переключалка | Чёткие лейблы вкладок + Tooltip |
| Рост зависимостей | Используем уже установленные пакеты (`requests`, `bs4`, `pandas`, `xlsxwriter`) |
| Потеря данных при падении | Сохраняем частичные результаты каждые N ссылок (TODO v2) |

---
## 6. Definition of Done
* ✔ Все итерации смержены в `main`, CI зелёный.  
* ✔ Режим «Стартовый парсер» работает без регрессий.  
* ✔ При вводе ≥ 1 ссылки пользователь получает корректный XLSX + статистику.  
* ✔ Документация обновлена (`ExistModuls.md`, `README.md`).  
* ✔ Code Coverage ≥ 80 %, все TODO вынесены в issue‑трекер.

---
## 7. Post‑MVP бэклог
* Асинхронная обработка (`aiohttp`, семафор 10 запросов).  
* DnD‑загрузка CSV/Excel со ссылками.  
* Кэширование по URL (hashing + pickle).  
* Экспорт ошибок в отдельный XLSX «failed_links.xlsx».
```
