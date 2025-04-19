# ui/web_ui.py
import streamlit as st
import time
from typing import Optional, Tuple
from Parse import WebParser
import pandas as pd

class StreamlitUI:
    def __init__(self, parser: WebParser):
        self.parser = parser
        self._setup_page_config()
        self.progress_bar = None
        self.status_text = None

    def _setup_page_config(self):
        st.set_page_config(
            page_title="Web Parser",
            layout="centered",
            page_icon="🔍",
            initial_sidebar_state="expanded"
        )

    def render_sidebar(self) -> Optional[dict]:
        """Отрисовка боковой панели с настройками"""
        with st.sidebar:
            st.title("⚙️ Управление парсером")
            url = st.text_input("Стартовый URL", "https://example.com")
            output_file = st.text_input("Имя файла", "products.xlsx")
            
            if st.button("🚀 Начать парсинг", use_container_width=True):
                return {"url": url, "output": output_file}
            
            st.markdown("---")
            self.stats_placeholder = st.empty()
        return None

    def _init_progress(self):
        """Инициализация элементов прогресса"""
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.stats_placeholder = st.empty()

    def _update_progress(self, value: float, status: str):
        """Обновление индикатора прогресса"""
        self.progress_bar.progress(value)
        self.status_text.markdown(f"**Статус:** {status}")
        
    def _show_stats(self, total: int, processed: int):
        """Отображение статистики"""
        self.stats_placeholder.markdown(f"""
        ### 📊 Прогресс
        - Всего товаров: **{total}**
        - Обработано: **{processed}**
        - Осталось: **{total - processed}**
        """)

    def render_results(self, data: pd.DataFrame, filename: str):
        """Отрисовка результатов парсинга"""
        st.success("✅ Парсинг успешно завершен!")
        
        with st.expander("📁 Просмотр данных", expanded=True):
            st.dataframe(data, use_container_width=True, height=400)
        
        # Создаем временный Excel файл в памяти
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            data.to_excel(writer, index=False, sheet_name='Products')
            writer.close()
        
        st.download_button(
            label="💾 Скачать Excel",
            data=output.getvalue(),
            file_name=filename,
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            use_container_width=True
        )

    def run(self):
        """Основной цикл интерфейса"""
        st.title("🔍 Web Parser")
        
        params = self.render_sidebar()
        if params:
            self._init_progress()
            try:
                result = self._run_parsing(params)
                if result is not None:
                    self.render_results(*result)
            except Exception as e:
                st.error(f"⛔ Ошибка: {str(e)}")
            finally:
                time.sleep(0.5)
                self.progress_bar.empty()
                self.status_text.empty()

    def _run_parsing(self, params: dict) -> Optional[Tuple[pd.DataFrame, str]]:
        """Основной процесс парсинга"""
        # Этап 1: Загрузка стартовой страницы
        self._update_progress(5, "Загрузка стартовой страницы...")
        start_page = self.parser.get_page(params['url'])
        if not start_page:
            raise Exception("Не удалось загрузить стартовую страницу")

        # Этап 2: Сбор ссылок
        self._update_progress(15, "Поиск ссылок на товары...")
        links = self.parser.parse_links(start_page)
        if not links:
            raise Exception("Ссылки на товары не найдены")
        
        # Этап 3: Парсинг товаров
        total = len(links)
        products = []
        for idx, link in enumerate(links, 1):
            try:
                # Обновление прогресса
                progress = 15 + int(70 * (idx / total))
                status = f"Обработка товара {idx}/{total}"
                self._update_progress(progress, status)
                self._show_stats(total, idx)
                
                # Парсинг страницы
                with st.spinner(f"Обработка: {link.split('/')[-1]}"):
                    product_page = self.parser.get_page(link)
                    if product_page:
                        products.append(self.parser.parse_product(product_page))
                        time.sleep(0.1)  # Имитация задержки

            except Exception as e:
                st.warning(f"Пропущен товар {idx}: {str(e)}")

        # Этап 4: Сохранение результатов
        self._update_progress(95, "Формирование отчёта...")
        df = pd.DataFrame(products)
        if df.empty:
            raise Exception("Не удалось собрать данные")
        
        return df, params['output']
