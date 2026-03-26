"""Excel export infrastructure."""

from __future__ import annotations

import logging
from typing import Dict, List

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
