"""Модуль excel_exporter.

Роль и ответственность:
    - предоставляет публичные элементы этого слоя.

Границы:
    - не реализует ответственность соседних слоёв.

Взаимодействие с другими ролями:
    - используется через импорт другими модулями проекта.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


class ExcelExporter:
    """Класс ExcelExporter.
    
    Роль и ответственность:
        - инкапсулирует поведение и состояние своей предметной роли.
    
    Границы:
        - не берёт ответственность внешних оркестраторов и интерфейсов.
    
    Взаимодействие с другими ролями:
        - получает зависимости через конструктор и вызывает их контракты.
    """

    @staticmethod
    def save(data: List[Dict], filename: str) -> None:
        """Выполняет операцию роли «save»."""
        try:
            dataframe = pd.DataFrame(data)
            dataframe.to_excel(filename, index=False)
            logging.info(f"Файл {filename} сохранён ({len(dataframe.columns)} столбцов)")
        except Exception as error:  # noqa: BLE001
            logging.error(f"Ошибка сохранения: {str(error)}")

    @staticmethod
    def save_sheets(sheet_data: Dict[str, List[Dict[str, Any]]], filename: str) -> bytes:
        """Выполняет операцию роли «save_sheets»."""
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
