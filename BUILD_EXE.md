# Сборка проекта в `.exe`

Используйте эту команду из корня проекта (Windows, `cmd`/PowerShell):

```bash
pyinstaller --noconfirm --clean --onefile --name streamlit-parser --add-data "App.py;." --add-data "Parse.py;." --add-data "product_list_parser.py;." --add-data "web_ui.py;." --collect-all streamlit --collect-all pandas --collect-all bs4 --collect-all xlsxwriter run_streamlit_app.py
```

После сборки файл будет в `dist/streamlit-parser.exe`