"""Инфраструктурный экспорт результатов парсинга в Excel.

Роль и ответственность:
    - сериализует список словарей в один лист либо набор листов Excel;
    - возвращает бинарное содержимое файла для скачивания.

Границы:
    - не формирует доменную статистику;
    - не выполняет парсинг исходных HTML-данных.

Взаимодействие с другими ролями:
    - вызывается `ProductListParser` и UI-слоем для выдачи отчёта.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Mapping

import pandas as pd


class ExcelExporter:
    """Сервис записи табличных структур в формат XLSX."""

    @staticmethod
    def save(data: list[Mapping[str, str]], filename: str) -> None:
        """Сохраняет один табличный набор в файл Excel на диске."""
        try:
            dataframe = pd.DataFrame(data)
            dataframe.to_excel(filename, index=False)
            logging.info("Файл %s сохранён (%d столбцов)", filename, len(dataframe.columns))
        except Exception as error:  # noqa: BLE001
            logging.error("Ошибка сохранения: %s", str(error))

    @staticmethod
    def save_sheets(sheet_data: Mapping[str, list[Mapping[str, str]]], filename: str) -> bytes:
        """Сохраняет набор листов в XLSX и возвращает содержимое файла в `bytes`."""
        if not sheet_data:
            raise RuntimeError("Нет данных для сохранения. Сначала вызовите run().")

        logging.info("Сохраняем результаты в %s", filename)
        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            for sheet_name, rows in sheet_data.items():
                dataframe = pd.DataFrame(rows)
                if dataframe.empty:
                    dataframe = pd.DataFrame({"Нет данных": []})
                dataframe.to_excel(writer, sheet_name=sheet_name[:31], index=False)

        buffer.seek(0)
        Path(filename).write_bytes(buffer.getvalue())
        logging.info("Файл %s создан (%d листов)", Path(filename).name, len(sheet_data))
        buffer.seek(0)
        return buffer.getvalue()
