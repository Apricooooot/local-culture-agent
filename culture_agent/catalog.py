from __future__ import annotations

import json
import gzip
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from .i18n import excludes_animation, is_comedy_request


@dataclass
class CatalogItem:
    provider: str
    provider_id: str
    title: str
    kind: str
    year: int | None = None
    creator: str = ""
    genres: tuple[str, ...] = ()
    source_url: str = ""

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["genres"] = list(self.genres)
        return result


def _read_json(url: str, user_agent: str, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": user_agent,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw)


def _catalog_timeout() -> int:
    try:
        configured = int(os.getenv("CULTURE_AGENT_CATALOG_TIMEOUT", "8"))
    except ValueError:
        configured = 8
    return max(1, min(configured, 60))


class OpenLibraryCatalog:
    provider = "openlibrary"

    def __init__(self) -> None:
        contact = os.getenv("CULTURE_AGENT_CATALOG_CONTACT", "local-installation")
        self.user_agent = f"local-culture-agent/0.1 ({contact})"
        self.timeout = _catalog_timeout()

    def search(self, query: str, limit: int = 12) -> list[CatalogItem]:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "limit": min(limit, 20),
                "fields": "key,title,author_name,first_publish_year,subject",
            }
        )
        data = _read_json(
            f"https://openlibrary.org/search.json?{params}",
            self.user_agent,
            timeout=self.timeout,
        )
        items: list[CatalogItem] = []
        for row in data.get("docs", []):
            key = str(row.get("key", "")).strip()
            title = str(row.get("title", "")).strip()
            if not key or not title:
                continue
            creators = row.get("author_name") or []
            subjects = row.get("subject") or []
            items.append(
                CatalogItem(
                    provider=self.provider,
                    provider_id=key,
                    title=title,
                    kind="book",
                    year=row.get("first_publish_year"),
                    creator=", ".join(str(value) for value in creators[:3]),
                    genres=tuple(str(value) for value in subjects[:5]),
                    source_url=f"https://openlibrary.org{key}",
                )
            )
        return items


class WikidataFilmCatalog:
    provider = "wikidata"
    endpoint = "https://query.wikidata.org/sparql"

    def __init__(self) -> None:
        contact = os.getenv("CULTURE_AGENT_CATALOG_CONTACT", "local-installation")
        self.user_agent = f"local-culture-agent/0.1 ({contact})"
        self.timeout = _catalog_timeout()

    def search(
        self,
        query: str,
        limit: int = 16,
        language: str = "en",
    ) -> list[CatalogItem]:
        year_match = re.search(r"(19|20)\d{2}", query)
        minimum_year = int(year_match.group()) if year_match else 2000
        genre_clause = (
            "?item wdt:P136/wdt:P279* wd:Q157443 ."
            if is_comedy_request(query)
            else "?item wdt:P136 ?genre ."
        )
        animation_filter = (
            "FILTER NOT EXISTS { ?item wdt:P136/wdt:P279* wd:Q202866 . }"
            if excludes_animation(query)
            else ""
        )
        label_languages = "zh,en" if language == "zh" else "en"
        sparql = f"""
SELECT DISTINCT ?item ?itemLabel ?year ?directorLabel ?imdb WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q11424 ;
        wdt:P577 ?date .
  {genre_clause}
  FILTER(YEAR(?date) >= {minimum_year})
  {animation_filter}
  OPTIONAL {{ ?item wdt:P57 ?director . }}
  OPTIONAL {{ ?item wdt:P345 ?imdb . }}
  BIND(YEAR(?date) AS ?year)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{label_languages}". }}
}}
ORDER BY DESC(?year)
LIMIT {min(limit, 25)}
"""
        params = urllib.parse.urlencode({"query": sparql, "format": "json"})
        data = _read_json(
            f"{self.endpoint}?{params}",
            self.user_agent,
            timeout=self.timeout,
        )
        items: list[CatalogItem] = []
        seen: set[str] = set()
        for row in data.get("results", {}).get("bindings", []):
            item_url = row.get("item", {}).get("value", "")
            provider_id = item_url.rsplit("/", 1)[-1]
            title = row.get("itemLabel", {}).get("value", "").strip()
            if not provider_id or not title or provider_id in seen:
                continue
            seen.add(provider_id)
            year_value = row.get("year", {}).get("value")
            items.append(
                CatalogItem(
                    provider=self.provider,
                    provider_id=provider_id,
                    title=title,
                    kind="film",
                    year=int(year_value) if year_value else None,
                    creator=row.get("directorLabel", {}).get("value", ""),
                    source_url=item_url,
                )
            )
        return items


class CatalogHub:
    def __init__(self, providers: set[str]) -> None:
        self.providers = providers
        self.books = OpenLibraryCatalog() if "openlibrary" in providers else None
        self.films = WikidataFilmCatalog() if "wikidata" in providers else None

    def candidates(
        self,
        message: str,
        kind: str,
        limit: int = 12,
        language: str = "en",
    ) -> list[CatalogItem]:
        if kind == "book" and self.books:
            return self.books.search(message, limit)
        if kind == "film" and self.films:
            return self.films.search(message, limit, language)
        return []


def catalog_from_environment() -> CatalogHub | None:
    configured = os.getenv("CULTURE_AGENT_CATALOG_PROVIDERS", "").strip()
    if not configured:
        return None
    providers = {part.strip().lower() for part in configured.split(",") if part.strip()}
    supported = providers & {"openlibrary", "wikidata"}
    return CatalogHub(supported) if supported else None

