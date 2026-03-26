"""Category page parsing infrastructure."""

from __future__ import annotations

from typing import Any, Dict, List

from bs4 import BeautifulSoup, Tag

from legacy.infra.parsing.extractors.v1 import CardExtractorV1
from legacy.infra.parsing.extractors.v2 import CardExtractorV2
from legacy.infra.parsing.feature_extractor import FeatureExtractor


class CategoryPageParser:
    """Page-level parser role for category listing HTML.

    Responsibility:
        - parse basic fixed fields using v1/v2 card extractors;
        - parse full rows by combining base fields and feature pairs.

    Boundaries:
        - does not handle pagination traversal;
        - does not persist parsing results.

    Interactions:
        - composes ``CardExtractorV1``, ``CardExtractorV2`` and ``FeatureExtractor``;
        - used by ``ProductListParser`` for page parsing in both modes.
    """

    def __init__(
        self,
        extractor_v1: CardExtractorV1,
        extractor_v2: CardExtractorV2,
        feature_extractor: FeatureExtractor,
    ) -> None:
        """Store extractor dependencies for category-page parsing."""
        self._extractor_v1 = extractor_v1
        self._extractor_v2 = extractor_v2
        self._feature_extractor = feature_extractor

    def parse_basic(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Parse category page with historical fixed-column behavior."""
        products: List[Dict[str, str]] = []

        rows_v1 = soup.select("div.cnc-product-categories-mob-card")
        for row in rows_v1:
            data = self._extractor_v1.extract(row)
            if data:
                products.append(data)

        if products:
            return products

        for row in soup.select("div.cnc-short-list-product"):
            data = self._extractor_v2.extract(row)
            if data:
                products.append(data)

        return products

    def parse_full(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse category page with full-table behavior."""
        products: List[Dict[str, Any]] = []

        for row in soup.select("div.cnc-product-categories-mob-card"):
            data = self._extract_row_full(row)
            if data:
                products.append(data)

        for row in soup.select("div.cnc-short-list-product"):
            data = self._extract_row_full(row)
            if data:
                products.append(data)

        return products

    def _extract_row_full(self, row: Tag) -> Dict[str, Any] | None:
        """Extract full row payload without changing historical base logic."""
        base_data: Dict[str, Any] | None = self._extractor_v1.extract(row)
        if not base_data:
            base_data = self._extractor_v2.extract(row)

        if not base_data:
            base_data = {}

        features = self._feature_extractor.extract(row)
        if features:
            base_data.update(features)

        return base_data or None
