from __future__ import annotations

from unittest.mock import patch

from bs4 import BeautifulSoup

from application.use_cases.parse_category_list import ParseCategoryListUseCase
from application.use_cases.parse_products import ParseProductsUseCase
from parser_domain.infrastructure.parsers.category_page_parser import CategoryPageParser
from parser_domain.infrastructure.parsers.card_extractors.v1 import CardExtractorV1
from parser_domain.infrastructure.parsers.card_extractors.v2 import CardExtractorV2
from parser_domain.infrastructure.parsers.feature_extractor import FeatureExtractor
from parser_domain.product_list_parser import ProductListParser
from parser_domain.types import (
    CategoryListParseResult,
    CategoryPageRef,
    CategoryParseStats,
    ItemErrorInfo,
    ParseCategoryListCommand,
    ParseProductsCommand,
    ParserMode,
    ProductCardBase,
    ProductCardFull,
    ProductDetails,
    ProductsParseResult,
    ProgressUpdate,
)


class StubWebParser:
    def __init__(self) -> None:
        self._calls = 0

    def iter_category_product_links(self, base_url: str) -> list[str]:
        return ["https://example.com/p1", "https://example.com/p2"]

    def get_page(self, url: str):
        self._calls += 1
        if self._calls == 2:
            raise RuntimeError("boom")
        return BeautifulSoup("<html></html>", "html.parser")

    def parse_product(self, soup: BeautifulSoup) -> ProductDetails:
        return ProductDetails(
            title="Name",
            article="A1",
            brand="Brand",
            price="100",
            availability="В наличии",
            description="Desc",
            features={"Цвет": "Красный"},
        )


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _clean_price(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def test_parse_products_use_case_returns_dataclass_and_callbacks() -> None:
    use_case = ParseProductsUseCase(parser=StubWebParser())
    updates: list[ProgressUpdate] = []
    errors: list[ItemErrorInfo] = []

    result = use_case.execute(
        command=ParseProductsCommand(
            category_url="https://example.com/cat",
            output_filename="out.xlsx",
        ),
        on_progress=updates.append,
        on_item_error=errors.append,
    )

    assert isinstance(result, ProductsParseResult)
    assert result.output_filename == "out.xlsx"
    assert not result.dataframe.empty
    assert isinstance(updates[0], ProgressUpdate)
    assert isinstance(errors[0], ItemErrorInfo)
    assert errors[0].item_ref == "https://example.com/p2"


def test_category_page_parser_returns_card_dataclasses() -> None:
    parser = CategoryPageParser(
        extractor_v1=CardExtractorV1(_clean_text, _clean_price),
        extractor_v2=CardExtractorV2(_clean_text, _clean_price),
        feature_extractor=FeatureExtractor(_clean_text),
    )
    soup = BeautifulSoup(
        """
        <div class='cnc-product-categories-mob-card'>
            <div class='cnc-product-categories-mob-card__header'>
                <a href='https://example.com/item-1'> Товар 1 </a>
                <span class='cnc-product-categories-mob-card__brand'> Бренд 1 </span>
            </div>
            <div class='cnc-product-categories-mob-card__current-price'>1 999 ₽</div>
            <div class='cnc-product-features__feature'>
              <span class='cnc-product-features__label'><span>Мощность:</span></span>
              <div>500Вт</div>
            </div>
        </div>
        """,
        "html.parser",
    )

    basic_items = parser.parse_basic(soup)
    full_items = parser.parse_full(soup)

    assert isinstance(basic_items[0], ProductCardBase)
    assert isinstance(full_items[0], ProductCardFull)
    assert full_items[0].features["Мощность"] == "500Вт"


class StubListParser:
    def __init__(self, links, output_file, base_parser, mode):
        self.links = links
        self.output_file = output_file
        self.mode = mode

    def run(self):
        return [], CategoryParseStats(
            total_categories=1,
            success_categories=1,
            failed_categories=0,
            failed_links=(),
            total_products=2,
            parser_mode=self.mode,
        )

    def save_results(self):
        return b"excel"


def test_parse_category_list_use_case_returns_typed_result() -> None:
    use_case = ParseCategoryListUseCase(parser=object())
    command = ParseCategoryListCommand(
        links=("https://example.com/category",),
        output_filename="list.xlsx",
        parser_mode=ParserMode.FULLTABLE,
    )

    with patch("application.use_cases.parse_category_list.ProductListParser", StubListParser):
        result = use_case.execute(command)

    assert isinstance(result, CategoryListParseResult)
    assert isinstance(result.stats, CategoryParseStats)
    assert result.stats.parser_mode is ParserMode.FULLTABLE


def test_product_list_parser_returns_category_parse_stats() -> None:
    class FakeWebParser:
        def _iter_paginated_pages(self, base_url: str):
            soup = BeautifulSoup(
                """
                <h1>Категория A</h1>
                <div class='cnc-product-categories-mob-card'>
                    <div class='cnc-product-categories-mob-card__header'>
                        <a href='https://example.com/p'>Товар</a>
                        <span class='cnc-product-categories-mob-card__brand'>Brand</span>
                    </div>
                    <div class='cnc-product-categories-mob-card__current-price'>100 ₽</div>
                </div>
                """,
                "html.parser",
            )
            yield CategoryPageRef(page_index=1, page_url=base_url, soup=soup)

    parser = ProductListParser(
        links=["https://example.com/category"],
        output_file="tmp.xlsx",
        base_parser=FakeWebParser(),
        mode=ParserMode.BASIC,
    )

    rows, stats = parser.run()

    assert rows
    assert isinstance(stats, CategoryParseStats)
    assert stats.total_categories == 1
    assert stats.success_categories == 1
