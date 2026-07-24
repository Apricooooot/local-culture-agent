from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from pathlib import Path

# Allow direct execution from a source checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from culture_agent.catalog import OpenLibraryCatalog, WikidataFilmCatalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Test an open catalog provider.")
    parser.add_argument("query")
    parser.add_argument("--kind", choices=("book", "film"), required=True)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    provider = OpenLibraryCatalog() if args.kind == "book" else WikidataFilmCatalog()
    try:
        items = provider.search(args.query, args.limit)
    except urllib.error.URLError as exc:
        raise SystemExit(f"Catalog request failed: {exc}") from exc
    print(json.dumps([item.as_dict() for item in items], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

