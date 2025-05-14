# Справочник модулей python. Web Parser
> Этот документ является единым источником истины (source of truth) о текущей структуре и состоянии кода проекта. Он служит опорой для AI‑генератора кода и всей команды разработчиков, предоставляя детальные описания существующих модулей. Используя этот справочник, AI сможет корректно генерировать и модифицировать код, опираясь на актуальные реализации.

---
## `App.py`
* **Назначение:** Точка входа в приложение; отвечает за инициализацию основных компонентов и запуск пользовательского интерфейса.  
* **Взаимодействие:** Импортирует  
  - `WebParser` — класс бизнес‑логики из `Parse.py`.  
  - `StreamlitUI` — слой представления из `web_ui.py`.  
- Проверяет, выполняется ли код внутри процесса Streamlit (`is_streamlit_running`) и в любом случае создаёт экземпляр `StreamlitUI`, передавая ему объект парсера.  
**Актаульный код `App.py`:**
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

---
## `Parse.py`
* **Назначение:** Инкапсулирует логику HTTP‑запросов, парсинга HTML‑страниц и подготовки структурированных данных о товарах для дальнейшего использования в UI или сохранения в файл.
* **Взаимодействие:** 
- Использует библиотеки: `requests`, `BeautifulSoup`, `pandas`, `logging`.  
- Экспортирует класс **`WebParser`**, который вызывается из `App.py` и `web_ui.py`.  
- Возвращает:  
  - `BeautifulSoup`‑объекты (метод `get_page`)  
  - Списки ссылок (`parse_links`)  
  - Словари с данными о товаре (`parse_product`)  
  - Excel‑файл (метод `save_to_excel`).
**Актаульный код `Parse.py`:**
```python
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
from typing import Optional, List, Dict

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
        for link in soup.select('td.gr-title.hidden_mobile a[href]'):
            href = link.get('href', '')
            if href.startswith('http'):
                links.append(href)
                logging.debug(f'Найдена ссылка (вариант 1): {href}')
        
        # Второй вариант (новый селектор)
        for link in soup.select('div.name_value_pc a[href]'):
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
```

---
## `web_ui.py`
* **Назначение:** Реализует интерактивный пользовательский интерфейс на Streamlit для управления процессом парсинга и визуализации результатов.  
* **Взаимодействие:** 
- Принимает объект `WebParser`, вызывая его методы для загрузки страниц и парсинга.  
- Интегрируется со Streamlit API: сайдбар, прогресс‑бар, спиннеры, `st.dataframe`, `st.download_button`.  
- Выводит пользователю DataFrame и предоставляет Excel‑файл через download‑кнопку.  
**Актаульный код `web_ui.py`:**
```python
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
            tab_start, tab_list = st.tabs(["Стартовый", "ProductList"])

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
                    "🚀 Начать парсинг", key="start_button", use_container_width=True
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
                    "🚀 Запустить ProductListParser",
                    key="list_button",
                    use_container_width=True,
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
            st.dataframe(data, use_container_width=True, height=400)

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
            use_container_width=True,
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
            use_container_width=True,
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
        self._update_progress(5, "Загрузка стартовой страницы…")
        start_page = self.parser.get_page(params["url"])
        if not start_page:
            raise Exception("Не удалось загрузить стартовую страницу")

        self._update_progress(15, "Поиск ссылок на товары…")
        links = self.parser.parse_links(start_page)
        if not links:
            raise Exception("Ссылки на товары не найдены")

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
        """Обработка произвольного списка URL‑адресов"""
        links: List[str] = params["links"]
        total = len(links)
        if total == 0:
            raise Exception("Список ссылок пуст")

        self._update_progress(5, "Инициализация ProductListParser…")
        pl_parser = ProductListParser(
            links=links, output_file=params["output"], base_parser=self.parser
        )

        failed_links: List[str] = []
        # --- последовательно обрабатываем ссылки --------------------- #
        for idx, link in enumerate(pl_parser.links, 1):
            progress = 5 + int(85 * (idx / total))
            self._update_progress(progress, f"Обработка {idx}/{total}")
            self._show_stats(total, idx)

            try:
                soup = self.parser.get_page(link)
                if not soup:
                    failed_links.append(link)
                    continue

                products_in_page = pl_parser._parse_category_page(soup)

                title = pl_parser._extract_page_title(soup)
                sheet_name = pl_parser._make_unique_sheet_name(title)
                pl_parser._sheet_data[sheet_name] = products_in_page

            except Exception as ex:
                st.warning(f"Пропущена ссылка {idx}: {ex}")
                failed_links.append(link)
        # --- финальная статистика ------------------------------------ #
        stats = {
            "total": total,
            "success": total - len(failed_links),
            "failed": len(failed_links),
            "failed_links": failed_links,
            "total_products": sum(len(v) for v in pl_parser._sheet_data.values()),
        }

        self._update_progress(95, "Формирование отчёта…")
        excel_bytes = pl_parser.save_results()
        return stats, excel_bytes, params["output"]
```

---
## `product_list_parser.py`
* **Назначение:** Модуль реализует класс **ProductListParser** – обёртку над `WebParser`, предназначенную для пакетного парсинга *категорий* или произвольного списка URL‑адресов. В данной версии реализована поддержка новой HTML‑разметки сайта
* **Взаимодействие:** 
- инициализацию с валидацией ссылок
- нормализацию и валидацию входных URL‑адресов
- базовую настройку логирования
- метод run() для последовательной обработки ссылок
- Класс последовательно обходит все переданные ссылки категории, извлекает список товаров в каждой категории и аккумулирует результаты.
> Полная бизнес‑логика (итеративный парсинг, сбор статистики,
формирование XLSX) будет добавлена на следующих итерациях в соответствии с NewFeature.md

**Актаульный код `product_list_parser.py`:**
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
    #            Валидация URL + добавление items_per_page=3000           #
    # ------------------------------------------------------------------ #
    def _validate_links(self) -> None:
        """
        Проверяет корректность URL и приводит каждую ссылку к виду,
        где параметр `items_per_page` гарантированно равен 3000.
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

            parsed = urlparse(url)
            query_dict = dict(parse_qsl(parsed.query, keep_blank_values=True))
            query_dict["items_per_page"] = "3000"  # всегда 3000

            new_query = urlencode(query_dict, doseq=True)
            new_url = urlunparse(parsed._replace(query=new_query))
            processed.append(new_url)

        if invalid:
            raise ValueError("Обнаружены некорректные URL: " + ", ".join(invalid))

        self.links = processed  # сохраняем «доработанные» ссылки
    # ------------------------------------------------------------------ #
    #                        PRIVATE HELPERS                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_text(text: str) -> str:
        """Удаляет множественные пробелы, \xa0 и &nbsp;."""
        return " ".join(text.replace("\xa0", " ").replace("&nbsp;", " ").split()).strip()

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
        tag = soup.select_one("div.ty-mainbox-container h1.ty-mainbox-title span")
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
        name_td = row.find("td", class_="gr-title hidden_mobile")
        if not name_td or not name_td.a:
            return None
        name = self._clean_text(name_td.a.get_text())

        brand_td = name_td.find_next_sibling("td")
        brand = self._clean_text(brand_td.get_text()) if brand_td else "Н/Д"

        article_span = row.find("span", onclick=re.compile(r"copyCode\('\d+"))
        article = (
            f"119-{self._clean_text(article_span.get_text())}" if article_span else "Н/Д"
        )

        price_span = row.find("span", class_="ty-price-num")
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        avail_span = row.select_one("div.rg-available > span")
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
        """Блочная верстка (v2). Принимает <div class="name_value_pc">."""
        if not name_div or not name_div.a:
            return None
        name = self._clean_text(name_div.a.get_text())

        brand_block = name_div.find_next("div", class_="brand_list compact pc")
        brand = "Н/Д"
        article = "Н/Д"
        if brand_block:
            brand_link = brand_block.select_one("div.ty-features-list a")
            if brand_link:
                brand = self._clean_text(brand_link.get_text())
            span_article = brand_block.find("span", style=re.compile("cursor"))
            if span_article:
                article = f"119-{self._clean_text(span_article.get_text())}"

        price_span = name_div.find_next("span", class_="ty-price-num")
        price = self._clean_price(price_span.get_text()) if price_span else "Н/Д"

        avail_p = name_div.find_next("p", style=re.compile(r"margin:5px"))
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
        rows = soup.select("tr")
        for row in rows:
            data = self._extract_row_data_v1(row)
            if data:
                products.append(data)
        if products:
            return products

        # --- v2 -------------------------------------------------------- #
        for name_div in soup.select("div.name_value_pc"):
            data = self._extract_row_data_v2(name_div)
            if data:
                products.append(data)
        return products
    # ------------------------------------------------------------------ #
    #                      Основной метод run()                          #
    # ------------------------------------------------------------------ #
    def run(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Обходит все ссылки, аккумулируя товары и статистику.
        (Метод сохранён для совместимости; структура листов
         формируется параллельно в self._sheet_data.)
        """
        all_products: List[Dict[str, Any]] = []
        failed_links: List[str] = []
        success_pages = 0

        for url in self.links:
            self.logger.info("Загружаем: %s", url)
            soup = self.parser.get_page(url)
            if not soup:
                self.logger.warning("Ошибка загрузки: %s", url)
                failed_links.append(url)
                continue

            products = self._parse_category_page(soup)
            self.logger.info("\u2514— товаров: %d", len(products))
            all_products.extend(products)
            success_pages += 1

            # ----------------  подготовка листа ----------------------- #
            title = self._extract_page_title(soup)
            sheet_name = self._make_unique_sheet_name(title)
            self._sheet_data[sheet_name] = products

        stats = {
            "total": len(self.links),
            "success": success_pages,
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

---