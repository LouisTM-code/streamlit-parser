"""Извлечение характеристик товара из карточки категории.

Роль и ответственность:
    - выделяет пары `метка -> значение` из блока характеристик карточки;
    - применяет внешнюю стратегию нормализации текста.

Границы:
    - не извлекает базовые поля карточки (название, цену, SKU);
    - не разрешает конфликты между одинаковыми метками.

Взаимодействие с другими ролями:
    - используется `CategoryPageParser` в режиме `fulltable`.
"""

from __future__ import annotations

from typing import Callable, Dict

from bs4 import Tag


class FeatureExtractor:
    """Компонент чтения товарных характеристик из DOM-узла карточки."""

    def __init__(self, clean_text: Callable[[str], str]) -> None:
        """Сохраняет зависимость нормализации текста для меток и значений."""
        self._clean_text = clean_text

    def extract(self, container: Tag) -> Dict[str, str]:
        """Извлекает нормализованные пары характеристик из контейнера карточки товара."""
        features: Dict[str, str] = {}

        for feature_block in container.select("div.cnc-product-features__feature"):
            label_inner_span = feature_block.select_one(
                "span.cnc-product-features__label span"
            )
            if not label_inner_span:
                continue

            raw_label = " ".join(label_inner_span.stripped_strings)
            label = self._clean_text(raw_label)
            if label.endswith(":"):
                label = label[:-1].rstrip()
            if not label:
                continue

            label_wrapper = label_inner_span.find_parent(
                "span",
                class_="cnc-product-features__label",
            )
            value_container: Tag | None = None

            if label_wrapper:
                sibling = label_wrapper.find_next_sibling("div")
                if isinstance(sibling, Tag):
                    value_container = sibling

            if not value_container:
                value_container = feature_block.find("div")

            if not value_container:
                continue

            raw_value = " ".join(value_container.stripped_strings)
            value = self._clean_text(raw_value)
            if not value:
                continue

            features[label] = value

        return features
