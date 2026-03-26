"""Excel export infrastructure."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


class ExcelExporter:
    """Tabular export role for parser results.

    Responsibility:
        - serialize list-of-dict payloads into Excel files.

    Boundaries:
        - does not fetch HTML;
        - does not parse product/category content.

    Interactions:
        - can be used by orchestration layers or UI flows after parsing.
    """

    @staticmethod
    def save(data: List[Dict], filename: str) -> None:
        """Persist parsed data to Excel file with original logging behavior."""
        try:
            dataframe = pd.DataFrame(data)
            dataframe.to_excel(filename, index=False)
            logging.info(f"Файл {filename} сохранён ({len(dataframe.columns)} столбцов)")
        except Exception as error:  # noqa: BLE001
            logging.error(f"Ошибка сохранения: {str(error)}")

    @staticmethod
    def save_sheets(sheet_data: Dict[str, List[Dict[str, Any]]], filename: str) -> bytes:
        """Persist category sheets to Excel and return binary payload."""
        if not sheet_data:
            raise RuntimeError("Нет данных для сохранения. Сначала вызовите run().")

        logging.info(f"Сохраняем результаты в {filename}")
        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            for sheet_name, rows in sheet_data.items():
                dataframe = pd.DataFrame(rows)
                if dataframe.empty:
                    dataframe = pd.DataFrame({"Нет данных": []})
                dataframe.to_excel(writer, sheet_name=sheet_name[:31], index=False)

        buffer.seek(0)
        Path(filename).write_bytes(buffer.getvalue())
        logging.info(f"Файл {Path(filename).name} создан ({len(sheet_data)} листов)")
        buffer.seek(0)
        return buffer.getvalue()
