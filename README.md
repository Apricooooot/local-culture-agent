# Local Culture Agent

A local-first AI companion that remembers what you read and watch, helps you
record ratings and reflections, and recommends what to explore next.

> **Project status:** early, usable MVP. The local journal works today.
> External book and film catalog integrations are documented but not yet
> implemented.

The product is built around a **model + harness** architecture:

- the **model** understands conversation and writes natural responses;
- the **harness** owns memory retrieval, validated writes, recommendation
  ranking, and tool execution;
- your records remain in a local SQLite database.

## What works today

- A calm, chat-first web interface
- Natural-language recording for books and films
- Ratings, reflections, tags, and watch/read status
- Searchable local library
- Recommendations grounded in your own ratings and tags
- Explainable memory: see which records informed a response
- Optional OpenAI-compatible model support, including Ollama
- A deterministic offline mode that requires no API key
- Replies that follow the language used in the current message

## Quick start

Python 3.11 or newer is the only requirement.

```bash
python -m culture_agent.server
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

The database is created at `data/culture_agent.db`. Ratings, reflections,
preference signals, and retrieved memories stay on the device by default.

### Use Ollama

Start an OpenAI-compatible Ollama endpoint, then set:

```powershell
$env:CULTURE_AGENT_MODEL_PROVIDER="openai-compatible"
$env:CULTURE_AGENT_MODEL_BASE_URL="http://localhost:11434/v1"
$env:CULTURE_AGENT_MODEL_NAME="qwen3:8b"
python -m culture_agent.server
```

Any OpenAI-compatible provider can be used by setting `CULTURE_AGENT_API_KEY`.

## Try these conversations

```text
I watched 《Arrival》, 9/10. I loved its quiet approach to language and grief.

I finished the book 《Invisible Cities》, 8.5/10. Every city felt like a dream.

Recommend a gentle film for a tired evening.

What do I seem to enjoy, and what records support that?
```

The same interactions work in Chinese. Conversation language is chosen from
the user's current message rather than from the README or source-code language.

## Architecture

```text
Browser chat UI
      |
HTTP/JSON API
      |
CultureHarness
  |       |        |
router  memory   model adapter
  |       |        |
validated tools  optional local/cloud LLM
      |
SQLite + FTS
```

The model never writes directly to the database. It proposes or interprets an
action; the harness validates it and calls a typed storage method.

## Metadata sources

The current MVP does **not** fetch external catalog metadata yet. The planned
provider layer is:

- **Books:** Open Library Search, Works/Edition, and Covers APIs. It is a good
  fit for low-volume, real-time lookup in an open-source project. It should not
  be treated as an unlimited third-party database or used for bulk scraping.
- **Films and TV:** TMDB API. Each installation should provide its own API
  credential. The UI must include TMDB's required attribution before this
  integration is released.
- **User-entered metadata:** always remains available as a fallback, so the
  journal is useful offline and is never locked to one catalog provider.

Provider results should be cached locally with their provider ID, source URL,
locale, and retrieval time. Provider facts must remain separate from user
ratings and model-generated preference inferences.

See [`docs/METADATA_SOURCES.md`](docs/METADATA_SOURCES.md) for the decision
record and integration boundaries.

## API

- `GET /api/health`
- `GET /api/library`
- `POST /api/chat` with `{ "message": "..." }`
- `POST /api/entries`
- `DELETE /api/entries/:id`

## Development

```bash
python -m unittest discover -s tests -v
```

## Roadmap

- Metadata lookup for books and films
- Editable preference memories with confidence and provenance
- Semantic retrieval and cross-work reflection
- Import/export for common culture-tracking services
- Desktop packaging with Tauri

## Privacy

Local-first is a product boundary, not just a deployment option:

- the SQLite database, ratings, reflections, preference memories, and future
  embeddings remain local by default;
- offline mode makes no model network requests;
- if a remote model is explicitly configured, only the prompt and retrieved
  context needed for that request are sent to that provider;
- secrets belong in environment variables and are excluded from Git;
- catalog lookups send search terms to the configured metadata provider, but
  never send the user's journal or preference profile.

Before a production release, the app will also expose local export, deletion,
memory inspection, and per-provider consent controls.

