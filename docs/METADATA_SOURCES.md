# Metadata Source Decision Record

## Status

Implemented as an opt-in provider layer. User records remain useful offline.

## Grounding boundary

Catalog providers establish which works exist and supply identifiers, titles,
years, creators, genres, and source URLs. The model may rank verified
candidates and explain a match, but it must not alter provider facts or add a
title outside the candidate set.

If a configured provider returns no candidates, the agent returns an explicit
no-results response instead of asking the model to invent alternatives.

## Books: Open Library

Open Library is the default open book provider. Use only user-initiated,
low-volume lookups, identify the application with
`CULTURE_AGENT_CATALOG_CONTACT`, cache repeated requests, and use monthly dumps
rather than the live API for future bulk features.

- https://openlibrary.org/developers/api
- https://openlibrary.org/developers/licensing

## Films and television: Wikidata

Wikidata is the default open film provider. Its structured data is CC0 and is
used for canonical identity, year, director, broad genre, source URL, and
cross-database IDs. Coverage is uneven; missing data must remain missing.

- https://www.wikidata.org/wiki/Help:Data_access
- https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service

## Optional local IMDb datasets

IMDb is not an open-source database. It publishes selected TSV datasets for
personal and non-commercial use. Users may download those files themselves and
import a private local copy:

```powershell
python scripts/import_imdb.py `
  --basics C:\datasets\title.basics.tsv.gz `
  --ratings C:\datasets\title.ratings.tsv.gz `
  --akas C:\datasets\title.akas.tsv.gz `
  --out data\imdb_catalog.db `
  --accept-imdb-noncommercial-terms
```

The script never downloads IMDb data or accepts terms on the user's behalf.
The generated database is ignored by Git and must not be redistributed.

- https://www.imdb.com/interfaces/
- https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX

## Why TMDB is not the default

TMDB has a convenient discovery API, but its current terms restrict using TMDB
content in AI/LLM/chatbot applications and require separate arrangements for
commercial use. This project therefore does not ship a TMDB integration.

- https://www.themoviedb.org/api-terms-of-use

## Data boundaries

| Data | Default location | May leave the device? |
| --- | --- | --- |
| Ratings, reflections, status | Local SQLite | No |
| Conversation window | Browser memory | Only to the configured model |
| Preference context | Local SQLite | Only minimal retrieved context sent to the configured model |
| Catalog search terms | Request-time only | Yes, when open catalogs are enabled |
| Provider facts and IDs | Response-time data; future local cache | Refetched only as needed |
| Optional IMDb subset | Local SQLite | No; do not redistribute |
| API credentials | Environment or OS secret store | Only to their provider |

Provider facts, user-authored text, and model inferences must remain separate.

