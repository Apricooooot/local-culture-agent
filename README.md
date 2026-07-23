# Local Culture Agent

A local-first AI companion that remembers what you read and watch, helps you
record ratings and reflections, and recommends what to explore next.

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

## Quick start

Python 3.11 or newer is the only requirement.

```bash
python -m culture_agent.server
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

The database is created at `data/culture_agent.db`. Nothing is uploaded by
default.

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
我看完《一一》，9分。喜欢它从日常里观察人生，但觉得有些段落略长。

记录一本书：卡尔维诺的《看不见的城市》，8.5分，像在读很多关于城市的梦。

今天有点累，想看一部温柔、不要太甜的电影。

我最近都喜欢什么？为什么？
```

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

This is an early MVP. Local records stay on the device, but messages are sent
to a remote provider if you explicitly configure one. Offline mode makes no
model network requests.

