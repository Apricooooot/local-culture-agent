from __future__ import annotations

from typing import Any, Callable

try:
    from langchain_core.tools import StructuredTool
except ImportError:
    class StructuredTool:  # type: ignore[no-redef]
        """Small source-checkout fallback; installed builds use LangChain."""

        def __init__(self, func: Callable[..., Any], name: str) -> None:
            self.func = func
            self.name = name

        @classmethod
        def from_function(
            cls,
            func: Callable[..., Any],
            name: str,
        ) -> "StructuredTool":
            return cls(func, name)

        def invoke(self, values: dict[str, Any]) -> Any:
            return self.func(**values)

from .catalog import CatalogHub
from .database import CultureDatabase


def build_read_tools(
    database: CultureDatabase,
    catalog: CatalogHub | None,
) -> dict[str, StructuredTool]:
    """Expose read-only application capabilities through LangChain tools.

    Database writes deliberately stay outside this registry. They must pass
    through CultureHarness validation before the storage layer is called.
    """

    def search_local_memory(query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Search the user's local book and film memory.

        Args:
            query: Natural-language search terms.
            limit: Maximum number of local records to return.
        """
        return database.search(query, max(1, min(limit, 50)))

    def list_local_library(limit: int = 50) -> list[dict[str, Any]]:
        """List the user's most recent local book and film records.

        Args:
            limit: Maximum number of local records to return.
        """
        return database.list_entries(max(1, min(limit, 100)))

    tools = [
        StructuredTool.from_function(
            func=search_local_memory,
            name="search_local_memory",
        ),
        StructuredTool.from_function(
            func=list_local_library,
            name="list_local_library",
        ),
    ]

    if catalog is not None:
        def search_culture_catalog(
            message: str,
            kind: str,
            limit: int = 12,
            language: str = "en",
        ) -> list[dict[str, Any]]:
            """Search configured public metadata catalogs for grounded candidates.

            Args:
                message: The user's complete recommendation request.
                kind: Either book or film.
                limit: Maximum number of candidates.
                language: Preferred label language, currently en or zh.
            """
            return [
                item.as_dict()
                for item in catalog.candidates(
                    message,
                    kind,
                    max(1, min(limit, 20)),
                    language,
                )
            ]

        tools.append(
            StructuredTool.from_function(
                func=search_culture_catalog,
                name="search_culture_catalog",
            )
        )

    return {tool.name: tool for tool in tools}

