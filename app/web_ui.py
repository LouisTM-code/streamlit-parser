"""UI-слой на Streamlit для запуска сценариев парсинга.

Роль и ответственность:
    - собирает пользовательские параметры и отображает результаты;
    - связывает виджеты интерфейса с use-case слоя приложения.

Границы:
    - не выполняет HTTP-запросы напрямую;
    - не содержит доменную логику извлечения данных из HTML.

Взаимодействие с другими ролями:
    - вызывает `ParseProductsUseCase` и `ParseCategoryListUseCase`;
    - использует `streamlit` как механизм рендера и событий.
"""

import time
from io import BytesIO
from typing import Optional

import pandas as pd
import streamlit as st

from application.use_cases.parse_category_list import ParseCategoryListUseCase
from application.use_cases.parse_products import ParseProductsUseCase
from parser_domain.types import (
    CategoryListParseResult,
    CategoryParseStats,
    ItemErrorInfo,
    ParseCategoryListCommand,
    ParseProductsCommand,
    ParserMode,
    ProductsParseResult,
    ProgressUpdate,
)
from parser_domain.web_parser import WebParser


class StreamlitUI:
    """Фасад взаимодействия с пользователем в Streamlit.

    Роль и ответственность:
        - управляет жизненным циклом UI: параметры → запуск → прогресс → результат;
        - хранит ссылки на плейсхолдеры прогресса в рамках сессии.

    Границы:
        - не валидирует HTML-разметку источника;
        - не определяет структуру доменных сущностей парсинга.

    Взаимодействие с другими ролями:
        - оркестрирует вызовы use-case и отображает их выходные данные.
    """

    def __init__(
        self,
        parse_products_use_case: ParseProductsUseCase,
        parse_category_list_use_case: ParseCategoryListUseCase,
    ):
        """Сохраняет use-case зависимости и настраивает конфигурацию страницы."""
        self._parse_products_use_case = parse_products_use_case
        self._parse_category_list_use_case = parse_category_list_use_case
        self._setup_page_config()
        self.progress_bar = None
        self.status_text = None
        self.stats_placeholder = None

    @staticmethod
    def _setup_page_config() -> None:
        """Применяет глобальные параметры страницы Streamlit до первого рендера."""
        st.set_page_config(
            page_title="Web Parser",
            layout="centered",
            page_icon="🔍",
            initial_sidebar_state="expanded",
        )

    def render_sidebar(self) -> Optional[object]:
        """Строит sidebar и возвращает команду запуска выбранного сценария."""
        with st.sidebar:
            st.title("⚙️ Управление парсером")
            tab_start, tab_list = st.tabs(
                ["Парсинг Характеристик", "Табличный-парсинг Каталога"]
            )

            command: Optional[object] = None

            with tab_start:
                url = st.text_input("Стартовый URL", "https://example.com", key="start_url")
                output_file = st.text_input("Имя файла", "products.xlsx", key="start_output")
                if st.button("🚀 Начать парсинг", key="start_button", width="stretch"):
                    command = ParseProductsCommand(
                        category_url=url,
                        output_filename=output_file,
                    )

            with tab_list:
                links_text = st.text_area(
                    "Ссылки категорий (по одной на строке)",
                    height=200,
                    placeholder="https://example.com/category/",
                    key="links_input",
                )

                mode_display_to_value = {
                    "basic (стандартный)": ParserMode.BASIC,
                    "fulltable (расширенный)": ParserMode.FULLTABLE,
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
                if st.button("🚀 Запустить", key="list_button", width="stretch"):
                    raw_links = tuple(ln for ln in links_text.splitlines() if ln.strip())
                    command = ParseCategoryListCommand(
                        links=raw_links,
                        output_filename=output_file_links,
                        parser_mode=parser_mode,
                    )

            st.markdown("---")
            self.stats_placeholder = st.empty()

        return command

    def _init_progress(self) -> None:
        """Создаёт виджеты прогресса, используемые callback-ами use-case слоя."""
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.stats_placeholder = st.empty()

    def _update_progress(self, update: ProgressUpdate) -> None:
        """Обновляет визуальный прогресс по контракту `ProgressUpdate`."""
        self.progress_bar.progress(int(update.percent))
        self.status_text.markdown(f"**Статус:** {update.message}")

    def _show_stats(self, total: int, processed: int) -> None:
        """Публикует в sidebar метрики: всего, обработано и осталось."""
        self.stats_placeholder.markdown(
            f"""
        ### 📊 Прогресс
        - Всего: **{total}**
        - Обработано: **{processed}**
        - Осталось: **{total - processed}**
        """
        )

    def render_results(self, result: ProductsParseResult) -> None:
        """Показывает результаты сценария `start` и готовит Excel-файл в памяти."""
        st.success("✅ Парсинг успешно завершен!")

        with st.expander("📁 Просмотр данных", expanded=True):
            st.dataframe(result.dataframe, width="stretch", height=400)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            result.dataframe.to_excel(writer, index=False, sheet_name="Products")

        st.download_button(
            label="💾 Скачать Excel",
            data=output.getvalue(),
            file_name=result.output_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    def render_product_list_results(self, result: CategoryListParseResult) -> None:
        """Отображает сводку batch-парсинга категорий и отчёт для скачивания."""
        stats: CategoryParseStats = result.stats
        st.success("✅ Обработка списка ссылок завершена!")
        st.subheader("📊 Итоговая статистика")
        st.markdown(
            f"""
        - Режим: **{stats.parser_mode.value}**
        - Всего ссылок: **{stats.total_categories}**
        - Успешно обработано: **{stats.success_categories}**
        - Ошибок: **{stats.failed_categories}**
        - Товаров собрано: **{stats.total_products}**
        """
        )

        if stats.failed_categories:
            with st.expander("⚠️ Ссылки с ошибками"):
                st.write(list(stats.failed_links))

        st.download_button(
            label="💾 Скачать Excel",
            data=result.excel_bytes,
            file_name=result.output_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    def run(self) -> None:
        """Выполняет основной UI-сценарий: выбор режима, запуск и вывод результата."""
        st.title("🔍 Web Parser")

        command = self.render_sidebar()
        if not command:
            return

        self._init_progress()
        try:
            if isinstance(command, ParseProductsCommand):
                result = self._parse_products_use_case.execute(
                    command=command,
                    on_progress=self._update_progress,
                    on_stats=self._show_stats,
                    on_page_request=self._fetch_with_spinner,
                    on_item_error=self._on_product_item_error,
                )
                self.render_results(result)
            else:
                batch_command = command
                self._update_progress(
                    ProgressUpdate(
                        percent=5,
                        message=(
                            "Инициализация ProductListParser "
                            f"(режим: {batch_command.parser_mode.value})…"
                        ),
                    )
                )
                self._update_progress(
                    ProgressUpdate(percent=20, message="Сканирование страниц и сбор данных…")
                )
                result = self._parse_category_list_use_case.execute(batch_command)
                self._update_progress(ProgressUpdate(percent=95, message="Формирование отчёта…"))
                self.render_product_list_results(result)
        except Exception as exc:  # noqa: BLE001
            st.error(f"⛔ Ошибка: {exc}")
        finally:
            time.sleep(0.5)
            self.progress_bar.empty()
            self.status_text.empty()

    @staticmethod
    def _fetch_with_spinner(link: str, fetch_page_callable):
        """Оборачивает загрузку одной страницы в spinner без изменения сигнатуры callback."""
        with st.spinner(f"Обработка: {link.split('/')[-1]}"):
            return fetch_page_callable(link)

    @staticmethod
    def _on_product_item_error(error_info: ItemErrorInfo) -> None:
        """Показывает ошибку обработки товара, не прерывая общий прогон."""
        st.warning(
            f"Пропущен товар {error_info.item_index} ({error_info.item_ref}): "
            f"{error_info.error_type} - {error_info.message}"
        )


def create_streamlit_ui(parser: WebParser) -> StreamlitUI:
    """Собирает экземпляр UI с use-case, разделяющими общий `WebParser`."""
    parse_products_use_case = ParseProductsUseCase(parser=parser)
    parse_category_list_use_case = ParseCategoryListUseCase(parser=parser)
    return StreamlitUI(
        parse_products_use_case=parse_products_use_case,
        parse_category_list_use_case=parse_category_list_use_case,
    )


def run_streamlit_ui() -> None:
    """Создаёт зависимости по умолчанию и запускает визуальный интерфейс."""
    parser = WebParser()
    ui = create_streamlit_ui(parser=parser)
    ui.run()
