"""Feature extraction infrastructure."""

from __future__ import annotations

from typing import Callable, Dict

from bs4 import Tag


class FeatureExtractor:
    """Extractor role for product feature key-value blocks.

    Responsibility:
        - extract named feature pairs from product card containers.

    Boundaries:
        - does not parse base product identity fields;
        - does not orchestrate page-level parsing flow.

    Interactions:
        - receives text cleaning callable from parser composition layer;
        - used by full-card parsing in ``CategoryPageParser``.
    """

    def __init__(self, clean_text: Callable[[str], str]) -> None:
        """Store text normalization dependency for labels and values."""
        self._clean_text = clean_text

    def extract(self, container: Tag) -> Dict[str, str]:
        """Extract normalized feature pairs from a product card container."""
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
