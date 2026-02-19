# Сборка проекта в `.exe`

## Рекомендуемая команда (Windows)

```bash
pyinstaller --noconfirm --clean --onefile --name streamlit-parser --add-data "App.py;." --collect-all streamlit --collect-all pandas --collect-all bs4 --collect-all xlsxwriter run_streamlit_app.py
```

## Почему именно так

- `run_streamlit_app.py` запускает приложение через `streamlit run App.py`, сохраняя поведение текущего UI.
- В режиме `--onefile` файл `App.py` должен быть явно добавлен как данные: `--add-data "App.py;."`.
- `--collect-all ...` подтягивает ресурсы и метаданные зависимостей, часто критичные для Streamlit-сборок.
- `--onefile` собирает единый исполняемый файл.

## Запуск

После сборки запускайте:

```bash
./dist/streamlit-parser.exe
```

Затем откройте адрес, который покажет приложение в консоли (обычно `http://localhost:8501`).
