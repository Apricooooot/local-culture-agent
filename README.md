
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
- Native Ollama support with per-request thinking control
- Optional OpenAI-compatible model support
- Grounded catalog candidates from Open Library and Wikidata
- A deterministic offline mode that requires no API key
- Replies that follow the language used in the current message

## Quick start

Python 3.11 or newer is the only runtime requirement. The default offline mode
does not download a model, call a remote API, or require an API key.

```bash
git clone https://github.com/Apricooooot/local-culture-agent.git
cd local-culture-agent
```

Creating a virtual environment is optional because the MVP uses only the Python
standard library, but it keeps future dependencies isolated:

```bash
python -m venv .venv
```

Activate it:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS or Linux
source .venv/bin/activate
```

Start the app:

```bash
python -m culture_agent.server
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). To use a different
port:

```powershell
# Windows PowerShell
$env:CULTURE_AGENT_PORT="9000"
python -m culture_agent.server
```

```bash
# macOS or Linux
CULTURE_AGENT_PORT=9000 python -m culture_agent.server
```

The database is created at `data/culture_agent.db`. Ratings, reflections,
preference signals, and retrieved memories stay on the device by default.
Stop the server with `Ctrl+C`. Back up or move the `data/` directory to keep
your journal; it is excluded from Git.

### Use Ollama

[Ollama](https://ollama.com/download) is a local model runner, not a model
itself. Install Ollama, download a model, and confirm that the local service is
running:

```powershell
# Windows PowerShell
ollama pull qwen3:8b
ollama list

$env:CULTURE_AGENT_MODEL_PROVIDER="ollama"
$env:CULTURE_AGENT_MODEL_BASE_URL="http://localhost:11434"
$env:CULTURE_AGENT_MODEL_NAME="qwen3:8b"
$env:CULTURE_AGENT_CATALOG_PROVIDERS="openlibrary,wikidata"
$env:CULTURE_AGENT_CATALOG_CONTACT="you@example.com"
python -m culture_agent.server
```

```bash
# macOS or Linux
ollama pull qwen3:8b
ollama list

export CULTURE_AGENT_MODEL_PROVIDER="ollama"
export CULTURE_AGENT_MODEL_BASE_URL="http://localhost:11434"
export CULTURE_AGENT_MODEL_NAME="qwen3:8b"
export CULTURE_AGENT_CATALOG_PROVIDERS="openlibrary,wikidata"
export CULTURE_AGENT_CATALOG_CONTACT="you@example.com"
python -m culture_agent.server
```

If Ollama is installed but the service is not running, start it with
`ollama serve`. The app uses Ollama's native
[`/api/chat`](https://docs.ollama.com/api/chat) endpoint so the harness can
control thinking on each request. No API key is required.

The native Ollama adapter chooses thinking per request. Recording, ordinary
chat, catalog filtering, and recommendations use `think: false`. Complex
comparisons, cross-record synthesis, trend analysis, and review-style prompts
use `think: true`. Catalog providers are opt-in because search terms leave the
device; omit `CULTURE_AGENT_CATALOG_PROVIDERS` for a fully offline session.

### Other local model servers

The harness works with any server that exposes
`POST /v1/chat/completions`. Set these four variables:

| Variable | Meaning |
| --- | --- |
| `CULTURE_AGENT_MODEL_PROVIDER` | Use `openai-compatible` |
| `CULTURE_AGENT_MODEL_BASE_URL` | Server URL ending in `/v1` |
| `CULTURE_AGENT_MODEL_NAME` | Exact model ID exposed by the server |
| `CULTURE_AGENT_API_KEY` | Optional local-server key; leave empty when authentication is disabled |

Recommended local servers:

| Server | Best for | Default base URL | Setup |
| --- | --- | --- | --- |
| **LM Studio** | The easiest graphical setup on Windows, macOS, or Linux | `http://localhost:1234/v1` | Download a model, open **Developer**, load it, and select **Start server**. [Official server guide](https://lmstudio.ai/docs/developer/core/server) |
| **llama.cpp** | A small native runtime, CPU/GPU flexibility, and direct GGUF control | `http://localhost:8080/v1` | Run `llama-server -m path/to/model.gguf --port 8080`. [Official server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) |
| **LocalAI** | Docker, a web UI, multiple model backends, and a self-hosted OpenAI replacement | `http://localhost:8080/v1` | Docker is the recommended installation path; install a model from its UI or gallery. [Official quick start](https://localai.io/getting-started/index.html) |
| **vLLM** | NVIDIA GPU servers, higher throughput, and multi-user deployments | `http://localhost:8000/v1` | Run `vllm serve MODEL_ID --api-key local-token`. [Official OpenAI-compatible server guide](https://docs.vllm.ai/en/stable/serving/openai_compatible_server/) |

Example for LM Studio:

```powershell
$env:CULTURE_AGENT_MODEL_PROVIDER="openai-compatible"
$env:CULTURE_AGENT_MODEL_BASE_URL="http://localhost:1234/v1"
$env:CULTURE_AGENT_MODEL_NAME="the-model-id-shown-by-lm-studio"
python -m culture_agent.server
```

Example for llama.cpp:

```powershell
llama-server -m C:\models\model.gguf --host 127.0.0.1 --port 8080

$env:CULTURE_AGENT_MODEL_PROVIDER="openai-compatible"
$env:CULTURE_AGENT_MODEL_BASE_URL="http://localhost:8080/v1"
$env:CULTURE_AGENT_MODEL_NAME="the-model-id-returned-by-the-server"
python -m culture_agent.server
```

Example for vLLM:

```bash
vllm serve Qwen/Qwen3-8B --api-key local-token

export CULTURE_AGENT_MODEL_PROVIDER="openai-compatible"
export CULTURE_AGENT_MODEL_BASE_URL="http://localhost:8000/v1"
export CULTURE_AGENT_MODEL_NAME="Qwen/Qwen3-8B"
export CULTURE_AGENT_API_KEY="local-token"
python -m culture_agent.server
```

Use the server's `/v1/models` endpoint when you are unsure which exact model ID
to configure:

```bash
curl http://localhost:1234/v1/models
```

### Suggested local models

Start with an instruction/chat model rather than a base model. Prefer a
quantized build when using a laptop or CPU-only machine.

“Free” below means that the model weights can be downloaded and run locally
without a per-request API fee. You still provide the hardware, storage, and
electricity. Review the linked license before redistributing a model or using
it commercially.

| Model | Free for local use? | License | Why it fits this project | Suggested starting point |
| --- | --- | --- | --- | --- |
| [Qwen3 4B](https://huggingface.co/Qwen/Qwen3-4B) | Yes; no model or per-request fee | [Apache 2.0](https://qwenlm.github.io/blog/qwen3/) | Small, multilingual, and a sensible first test on modest hardware | A 4-bit quantization through Ollama, LM Studio, or llama.cpp |
| [Qwen3 8B](https://huggingface.co/Qwen/Qwen3-8B) | Yes; no model or per-request fee | [Apache 2.0](https://qwenlm.github.io/blog/qwen3/) | Stronger multilingual conversation, instruction following, and agent-oriented behavior | A 4-bit quantization when the machine can comfortably run an 8B model |
| [Gemma 3 4B IT](https://huggingface.co/google/gemma-3-4b-it) | Yes; no model or per-request fee, but you must accept Google's terms | [Gemma Terms of Use](https://ai.google.dev/gemma/terms), including use restrictions; this is not an Apache/MIT-style license | Lightweight instruction model with broad multilingual support | Good alternative when a compatible runner provides an accepted-terms build |
| [Ministral 3 8B Instruct](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF) | Yes; no model or per-request fee | [Apache 2.0](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF#license) | Multilingual support and an edge-deployment focus | A GGUF quantization with llama.cpp or LM Studio |

Model quality and memory usage depend on quantization, context size, backend,
and hardware. A smaller model that runs reliably is a better starting point
than a larger model that continuously swaps memory. For this agent's
Chinese/English conversation and constraint-following workload, Qwen3 8B is the
recommended local baseline; Qwen3 4B is best treated as a low-resource demo.

### Grounded book and film data

The agent can retrieve candidates before asking the model to rank them:

| Kind | Source | License and boundary |
| --- | --- | --- |
| Books | [Open Library](https://openlibrary.org/developers/api) | Public low-volume APIs; identify the app, cache repeated requests, and use dumps for bulk work |
| Films | [Wikidata](https://www.wikidata.org/wiki/Help:Data_access) | Structured data is CC0; coverage may be incomplete |
| Optional film subset | [IMDb non-commercial datasets](https://www.imdb.com/interfaces/) | Personal/non-commercial use only; users download and import their own copy |

Test the open providers without starting the web app:

```powershell
python scripts/search_catalog.py "轻松喜剧，2000年以后，不要动画" --kind film
python scripts/search_catalog.py "城市 梦 卡尔维诺" --kind book
```

IMDb is not open source. For a private, non-commercial local installation,
download the permitted TSV files yourself and run:

```powershell
python scripts/import_imdb.py `
  --basics C:\datasets\title.basics.tsv.gz `
  --ratings C:\datasets\title.ratings.tsv.gz `
  --akas C:\datasets\title.akas.tsv.gz `
  --out data\imdb_catalog.db `
  --accept-imdb-noncommercial-terms
```

The generated database remains under `data/` and must not be committed or
redistributed. The importer never downloads IMDb data automatically. It
prepares a local database for a future opt-in IMDb candidate adapter; the
current recommendation path uses Open Library and Wikidata.

TMDB is not enabled by default. Its current API terms contain restrictions for
AI/LLM/chatbot applications, so this project does not depend on it without
permission compatible with the intended use.

### Connection troubleshooting

1. Confirm the model server is running.
2. Open or query `BASE_URL/models`.
3. Copy the returned model ID exactly into `CULTURE_AGENT_MODEL_NAME`.
4. Confirm that `CULTURE_AGENT_MODEL_BASE_URL` includes `/v1`.
5. Restart Local Culture Agent after changing environment variables.

If the model server is unavailable, local records are not lost. Restart without
`CULTURE_AGENT_MODEL_PROVIDER` to return to the deterministic offline mode.

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

Open Library and Wikidata are implemented as opt-in catalog providers.
Recommendations receive provider IDs and source URLs. When verified candidates
are present, the model is restricted to that candidate set; if no candidate is
returned, the harness reports that instead of asking the model to invent one.
User-entered metadata remains available offline.

See [`docs/METADATA_SOURCES.md`](docs/METADATA_SOURCES.md) for licensing,
IMDb import instructions, provider boundaries, and the TMDB decision.

## API

- `GET /api/health`
- `GET /api/library`
- `POST /api/chat` with `{ "message": "...", "history": [...] }`; responses
  include `thinking_used` and grounded `catalog_items`
- `POST /api/entries`
- `DELETE /api/entries/:id`

## Development

```bash
python -m unittest discover -s tests -v
```

## Roadmap

- Better catalog ranking, caching, and multilingual title resolution
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

