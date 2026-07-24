from __future__ import annotations

import argparse
import csv
import gzip
import sqlite3
from pathlib import Path
from typing import Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS imdb_titles (
    tconst TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    original_title TEXT NOT NULL,
    year INTEGER,
    runtime_minutes INTEGER,
    genres TEXT NOT NULL,
    average_rating REAL,
    num_votes INTEGER
);
CREATE TABLE IF NOT EXISTS imdb_akas (
    tconst TEXT NOT NULL,
    title TEXT NOT NULL,
    region TEXT,
    language TEXT,
    PRIMARY KEY (tconst, title, region, language)
);
CREATE INDEX IF NOT EXISTS imdb_titles_year_idx ON imdb_titles(year);
CREATE INDEX IF NOT EXISTS imdb_akas_title_idx ON imdb_akas(title);
"""


def rows(path: Path) -> Iterable[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
        yield from csv.DictReader(source, delimiter="\t")


def nullable_int(value: str) -> int | None:
    return None if value == r"\N" else int(value)


def import_basics(connection: sqlite3.Connection, path: Path) -> int:
    batch: list[tuple[object, ...]] = []
    imported = 0
    for row in rows(path):
        if row["titleType"] not in {"movie", "tvMovie"} or row["isAdult"] == "1":
            continue
        batch.append(
            (
                row["tconst"],
                row["primaryTitle"],
                row["originalTitle"],
                nullable_int(row["startYear"]),
                nullable_int(row["runtimeMinutes"]),
                "" if row["genres"] == r"\N" else row["genres"],
            )
        )
        if len(batch) >= 5000:
            connection.executemany(
                """INSERT OR REPLACE INTO imdb_titles
                (tconst, title, original_title, year, runtime_minutes, genres)
                VALUES (?, ?, ?, ?, ?, ?)""",
                batch,
            )
            imported += len(batch)
            batch.clear()
    if batch:
        connection.executemany(
            """INSERT OR REPLACE INTO imdb_titles
            (tconst, title, original_title, year, runtime_minutes, genres)
            VALUES (?, ?, ?, ?, ?, ?)""",
            batch,
        )
        imported += len(batch)
    return imported


def import_ratings(connection: sqlite3.Connection, path: Path) -> int:
    batch: list[tuple[object, ...]] = []
    updated = 0
    for row in rows(path):
        batch.append((float(row["averageRating"]), int(row["numVotes"]), row["tconst"]))
        if len(batch) >= 5000:
            connection.executemany(
                "UPDATE imdb_titles SET average_rating = ?, num_votes = ? WHERE tconst = ?",
                batch,
            )
            updated += len(batch)
            batch.clear()
    if batch:
        connection.executemany(
            "UPDATE imdb_titles SET average_rating = ?, num_votes = ? WHERE tconst = ?",
            batch,
        )
        updated += len(batch)
    return updated


def import_akas(connection: sqlite3.Connection, path: Path) -> int:
    batch: list[tuple[str, str, str, str]] = []
    imported = 0
    for row in rows(path):
        region = "" if row["region"] == r"\N" else row["region"]
        language = "" if row["language"] == r"\N" else row["language"]
        if region not in {"", "CN", "US", "GB"} and language not in {"", "cmn", "en"}:
            continue
        batch.append((row["titleId"], row["title"], region, language))
        if len(batch) >= 5000:
            connection.executemany(
                "INSERT OR IGNORE INTO imdb_akas VALUES (?, ?, ?, ?)",
                batch,
            )
            imported += len(batch)
            batch.clear()
    if batch:
        connection.executemany(
            "INSERT OR IGNORE INTO imdb_akas VALUES (?, ?, ?, ?)",
            batch,
        )
        imported += len(batch)
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import user-downloaded IMDb non-commercial TSV datasets."
    )
    parser.add_argument("--basics", required=True, type=Path)
    parser.add_argument("--ratings", type=Path)
    parser.add_argument("--akas", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/imdb_catalog.db"))
    parser.add_argument(
        "--accept-imdb-noncommercial-terms",
        action="store_true",
        help="Confirm that you reviewed IMDb's personal/non-commercial dataset terms.",
    )
    args = parser.parse_args()
    if not args.accept_imdb_noncommercial_terms:
        parser.error(
            "Review https://www.imdb.com/interfaces/ and pass "
            "--accept-imdb-noncommercial-terms to continue."
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.out) as connection:
        connection.executescript(SCHEMA)
        print(f"Imported {import_basics(connection, args.basics):,} movie titles.")
        if args.ratings:
            print(f"Processed {import_ratings(connection, args.ratings):,} rating rows.")
        if args.akas:
            print(f"Imported {import_akas(connection, args.akas):,} localized title rows.")
    print(f"Local IMDb catalog written to {args.out}")
    print("Do not redistribute this database; IMDb limits these datasets to personal, non-commercial use.")


if __name__ == "__main__":
    main()

