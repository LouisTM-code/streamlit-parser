# Сборка проекта в `.exe`

## Рекомендуемая команда

```bash
pyinstaller --noconfirm --clean --onefile --name streamlit-parser --collect-all streamlit --collect-all pandas --collect-all bs4 --collect-all xlsxwriter run_streamlit_app.py
```

## Почему именно так

- `run_streamlit_app.py` запускает приложение через `streamlit run App.py`, поэтому функционал UI и текущая логика не ломаются.
- `--collect-all ...` подтягивает ресурсы и метаданные библиотек, которые часто теряются при упаковке Streamlit-приложений.
- `--onefile` собирает единый исполняемый файл.

## Запуск

После сборки запускайте:

```bash
./dist/streamlit-parser.exe
```

Затем откройте адрес, который покажет приложение в консоли (обычно `http://localhost:8501`).
