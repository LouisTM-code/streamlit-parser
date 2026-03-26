# ui/web_ui.py
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from legacy.Parse import WebParser
from legacy.product_list_parser import ProductListParser


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
