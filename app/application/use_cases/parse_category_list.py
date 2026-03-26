"""Use-case for parsing a provided list of category URLs.

Role and responsibility:
    - orchestrate ``ProductListParser`` lifecycle for category list mode;
    - return parser stats, Excel bytes and output filename.

Boundaries:
    - does not depend on Streamlit components;
    - does not render progress or messages.

Interactions:
    - creates and invokes ``parser_domain.product_list_parser.ProductListParser``;
    - accepts externally provided ``WebParser`` dependency.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from parser_domain.web_parser import WebParser
from parser_domain.product_list_parser import ProductListParser


class ParseCategoryListUseCase:
    """Application use-case for tabular parsing of category link lists.

    Role and responsibility:
        - validate input links and parser mode;
        - run parsing and export aggregation pipeline.

    Boundaries:
        - does not implement UI concerns;
        - does not expose ``ProductListParser`` internals to presentation layer.

    Interactions:
        - composes ``ProductListParser`` with injected ``WebParser`` facade.
    """

    def __init__(self, parser: WebParser) -> None:
        """Initialize use-case with shared parser dependency."""
        self._parser = parser

    def execute(
        self,
        links: list[str],
        output_filename: str,
        parser_mode: str = "basic",
    ) -> Tuple[Dict[str, Any], bytes, str]:
        """Run category list parsing and return stats and Excel binary payload."""
        if len(links) == 0:
            raise Exception("Список ссылок пуст")

        list_parser = ProductListParser(
            links=links,
            output_file=output_filename,
            base_parser=self._parser,
            mode=parser_mode,
        )
        _, stats = list_parser.run()
        excel_bytes = list_parser.save_results()
        return stats, excel_bytes, output_filename
