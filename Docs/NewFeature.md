# NewFeature.md

**Интеграция функционала `ProductListParser` в Web Parser**

---

## 1. Цель и мотивация

`ProductListParser` — это дополнительный режим парсинга, позволяющий пользователю загрузить сразу набор готовых ссылок на карточки товаров, автоматически извлечь данные с каждой страницы, отобразить статистику успешности обработки и сформировать XLSX‑файл для скачивания. Фича расширяет диапазон сценариев использования парсера (ручные подборки, выгрузки из рекламных кабинетов и т.д.) без вмешательства в текущий механизм «стартовой страницы».

---

## 2. Обзор архитектурных изменений

| Слой               | Текущее состояние                                             | Что добавляем / меняем                                                                                                                                                         | Причина                                                                |
| ------------------ | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| **Бизнес‑логика**  | `Parse.py` с классом `WebParser`                              | Новый класс‑обёртка **`ProductListParser`** (наследует или агрегирует `WebParser`)<br>+ вспомогательные функции валидации входных ссылок                                       | Изолируем логику работы по списку ссылок, не меняя существующие методы |
| **UI (Streamlit)** | `StreamlitUI.render_sidebar()` рендерит одиночный набор полей | Добавляем **вкладочную навигацию** в левом сайдбаре («Стартовый парсер» ↔ «ProductListParser»). Вкладка 2 содержит `st.text_area` для ссылок и `st.text_input` для имени файла | Пользовательский выбор режима без усложнения одного экрана             |
| **Точка входа**    | `App.py` создаёт `StreamlitUI(parser)`                        | Экземпляр `WebParser` передаётся UI как «базовый парсер»; новая обёртка создаётся динамически при запуске режима ProductListParser                                             | Сохраняем обратную совместимость и единый App                          |

*Все остальные модули остаются неизменны; маршруты импорта и публичные интерфейсы не ломаются.*

---

## 3. Подробности реализации

### 3.1 `ProductListParser` (уровень бизнес‑логики)

1. **Инициализация**

   * Принимает: список URL, объект `WebParser`, имя выходного файла.
   * Проверяет и нормализует ссылки (удаление пустых строк, дубликатов, необоснованных параметров).
2. **Основной цикл**

   1. Итеративно вызывает `WebParser.get_page()` и `WebParser.parse_product()` для каждой ссылки.
   2. Ведёт счётчики: *total / success / failed*; сохраняет список пропущенных URL (для логирования).
   3. Позволяет прервать процесс через UI‑кнопку «Стоп» (использовать `st.stop` или флаг в сессии).
3. **Выходные данные**

   * `pandas.DataFrame` с агрегацией всех товаров.
   * Человеко‑читаемое резюме: «Обработано N, успешно M, пропущено K».
4. **Формирование XLSX**

   * Использует существующий `save_to_excel` или аналог в памяти (`BytesIO + pd.ExcelWriter`).
5. **Логирование и ошибки**

   * Сообщения уровня `WARNING` при ошибке конкретной ссылки, `ERROR` — при сбое сети.
   * Исключения не прерывают весь процесс, а фиксируются и позволяют продолжить.

### 3.2 Изменения в UI

| Элемент                    | Новое поведение                                                                                                                                                      | Подробности                                                                   |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **Sidebar**                | `st.tabs(["Стартовый парсер", "ProductListParser"])` (или радиокнопки)                                                                                               | Активная вкладка определяет набор полей ввода и лейбл кнопки запуска          |
| **Поля ввода (вкладка 2)** | *Текстовое поле* `links_input` – многострочный, placeholder «вставьте по одному URL на строку»<br>*Имя файла* `output_file_links` – по умолчанию `product_list.xlsx` | Ссылки разбираются на бэкэнде; имя файла – валидируется на расширение `.xlsx` |
| **Кнопка запуска**         | «🚀 Запустить ProductListParser»                                                                                                                                     | При нажатии — передаёт ссылки и имя файла в экземпляр `ProductListParser`     |
| **Прогресс и статистика**  | Переиспользуем существующие `_init_progress()`, `_update_progress()` с другим статус‑текстом                                                                         | Стадии: «Загрузка M/N», «Формирование отчёта»                                 |
| **Результаты**             | Отображается только резюме (без DataFrame, если пользователь не выберет раскрывающийся блок)                                                                         | Уменьшаем визуальный шум при большом объёме                                   |
| **Скачивание**             | `st.download_button` c `file_name=output_file_links`                                                                                                                 | Поведение идентично текущему сценарию                                         |

### 3.3 Поток данных (end‑to‑end)

1. Пользователь → UI (ввод ссылок / имя файла).
2. UI → `ProductListParser` (передача параметров).
3. `ProductListParser` → `WebParser` (итеративные вызовы `get_page` + `parse_product`).
4. `WebParser` возвращает словари → собираются в `DataFrame`.
5. `ProductListParser` формирует XLSX в памяти → UI.
6. UI отображает статистику, предоставляет кнопку скачивания.

---

## 4. Сохранение стабильности существующего кода

| Риск                            | Митигирующая мера                                                                                            |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Ломаемый API `WebParser`        | Новый парсер работает **поверх** существующих публичных методов, без их изменения                            |
| Перегрузка UI‑функций прогресса | Используем те же методы, но с отдельным блоком состояния, не меняя сигнатур                                  |
| Конфликты зависимостей          | Используются уже присутствующие `requests`, `bs4`, `pandas`, `xlsxwriter`; новых пакетов не требуется        |
| Потеря производительности       | Обработка по ссылкам параллелизуется в следующих версиях (сейчас последовательная, как и в основном парсере) |
| Дублирование кода               | Повторное использование `parse_product` уменьшает дубли; валидация выделяется в утилиту                      |

---

## 5. План тестирования

1. **Unit‑тесты**

   * Валидация и нормализация входного списка ссылок (edge‑cases: пустые строки, пробелы, https vs http).
   * Обработка одной валидной и одной заведомо битой ссылки.
2. **Интеграционные**

   * Полный проход по 3‑5 реальным ссылкам, сравнение счётчиков и выходного XLSX.
   * Проверка, что стартовый режим парсера работает без изменений.
3. **UI‑тест (Streamlit)**

   * Ручной smoke‑test: переключение вкладок, ввод данных, корректное появление прогресса и скачивание файла.

---

## 6. Будущие улучшения (roadmap)

* Асинхронные запросы (`asyncio + aiohttp`) для ускорения массового парсинга.
* Поддержка drag‑and‑drop CSV/Excel‑файла со ссылками вместо ручного ввода.
* Отдельный отчёт об ошибках со ссылками, которые не удалось обработать.
* Кэширование результатов для избежания повторных запросов к тем же страницам.

---

## 7. Открытые вопросы

1. Какие CSS‑селекторы понадобятся для новых площадок? (оставить TODO‑заглушку в коде).
2. Нужна ли автоматическая идентификация дубликатов товаров внутри одной выборки?
3. Следует ли выводить DataFrame по умолчанию, если ссылок < N (например 10)?

---

### Итог

Документ описывает, как безболезненно встроить `ProductListParser` в существующую архитектуру Web Parser, не затронув текущую логику и интерфейсы. Реализация сводится к добавлению небольшого слоя‑обёртки и расширению панели управления в UI; все ключевые механизмы (HTTP‑запросы, парсинг, сохранение XLSX, индикаторы прогресса) переиспользуются.
