# Metadata Source Decision Record

## Status

Proposed for the next milestone. No external catalog provider is called by the
current MVP.

## Goals

- Resolve titles without forcing users to type every metadata field.
- Keep the journal useful when offline or when a provider is unavailable.
- Preserve source attribution and avoid mixing provider facts with AI inference.
- Make every installation bring its own credentials where a provider requires
  them.

## Books: Open Library

Open Library is the default book provider because its Search API returns
work-level and edition-level fields, including authors, publication years,
identifiers, languages, and cover identifiers.

Integration rules:

1. Use low-volume, user-initiated lookups.
2. Request only the fields required by the UI.
3. Store the Open Library work/edition ID and retrieval timestamp.
4. Use the Covers API by identifier instead of copying images into the repo.
5. Do not perform bulk imports through the live API; use published data dumps
   if a future feature genuinely requires bulk access.

Official documentation:

- https://openlibrary.org/dev/docs/api/search
- https://openlibrary.org/developers/api

## Films and television: TMDB

TMDB is the proposed default provider for films and television because it has
strong internationalized title, credit, poster, and release metadata.

Integration rules:

1. Require users or deployers to supply their own API credential.
2. Never commit credentials or proxy a shared secret from this repository.
3. Add the official TMDB attribution notice and approved logo to the About or
   Credits screen before releasing the integration.
4. Store TMDB IDs and locale alongside cached facts.
5. Treat provider ratings as catalog metadata, never as the user's rating.

Official documentation:

- https://developer.themoviedb.org/docs/faq
- https://developer.themoviedb.org/v4/docs/authentication-application

## Data boundaries

| Data | Default location | May leave the device? |
| --- | --- | --- |
| Ratings, reflections, status | Local SQLite | No |
| Preference memories and confidence | Local SQLite | Only minimal retrieved context when a remote model is explicitly enabled |
| Embeddings | Local storage | No by default |
| Catalog search terms | Request-time only | Yes, to the selected catalog provider |
| Provider facts and IDs | Local cache | Refetched only as needed |
| API credentials | Environment or OS secret store | Only to their provider |

The model must never overwrite provider facts or user-authored text. Inferred
tags and preferences require provenance, confidence, and an easy correction or
deletion path.

