# Asnany Article RAG Production

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.129+-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

End-to-end Retrieval-Augmented Generation (RAG) pipeline that scrapes Arabic dental articles from [blog.asnany.net](https://blog.asnany.net), embeds them into Qdrant, and serves a chatbot that answers medical questions in Arabic using Groq's LLM.

---

## Project Overview

**English** — Asnany Article RAG Production is a production-ready Q&A system for Arabic dental/medical content. It incrementally scrapes a WordPress blog, chunks the articles, generates embeddings using `intfloat/multilingual-e5-large`, stores them in a Qdrant vector database, and serves a FastAPI chatbot endpoint that retrieves relevant chunks and answers user questions via Groq's LLM. The frontend is an Arabic-language chat widget with source attribution. Built for dental clinics, medical educators, and Arabic-speaking patients seeking reliable dental health information.

**العربية** — نظام أسئلة وأجوبة متكامل للمحتوى الطبي السني العربي. يقوم بجمع المقالات من مدونة WordPress بشكل تدريجي، وتقسيمها إلى أجزاء، ثم تحويلها إلى تمثيلات رياضية (embeddings) باستخدام نموذج `intfloat/multilingual-e5-large`، وتخزينها في قاعدة بيانات متجهات Qdrant. يقدم واجهة API للمحادثة تسترجع الأجزاء ذات الصلة وتجيب على أسئلة المستخدمين عبر نموذج Groq اللغوي. الواجهة الأمامية بالعربية مع عرض المصادر. صُمم لعيادات الأسنان والمعلمين والمرضى الناطقين بالعربية.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA INGESTION (main.py)                          │
│                                                                             │
│  blog.asnany.net                                                           │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌───────────┐ │
│  │  Scraper     │───▶│  SQLite Seed │───▶│  Embedder     │───▶│  Qdrant   │ │
│  │  (asnany_   │    │  (database_  │    │  (sentence-   │    │  Uploader │ │
│  │  scraper.py) │    │  server.py)  │    │  transformers) │    │  (batch)  │ │
│  └─────────────┘    └──────────────┘    └───────────────┘    └───────────┘ │
│       │                    │                      │                │        │
│       ▼                    ▼                      ▼                ▼        │
│  articles.csv         database.db           chunk + embed      Qdrant Cloud │
│  (CSV output)         (SQLite store)        → passage: ...     (COSINE)    │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                           QUERY PIPELINE (run.py)                           │
│                                                                             │
│  ┌──────────┐    ┌────────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │  Chat     │───▶│  Qdrant        │───▶│  SQL Fetch   │───▶│  Groq LLM  │  │
│  │  Widget   │    │  Retriever     │    │  (sources)   │    │  (answer)  │  │
│  │  (RTL UI) │    │  (top-K=3)     │    │              │    │            │  │
│  └──────────┘    └────────────────┘    └──────────────┘    └────────────┘  │
│       │                    │                      │                │        │
│       │                    ▼                      │                ▼        │
│       │           query → embedding               │         Arabic reply   │
│       │           → COSINE search                 │         + sources      │
│       └─────────────────────────────────────────────── chat_logs.jsonl ────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Role |
|-----------|------|
| **Scraper** | Incrementally crawls the WordPress blog paginated listing, extracts article title/content, normalizes URLs, writes to CSV |
| **SQLite Seed** | Reads CSV into a local SQLite database with `UNIQUE` url constraint for deduplication |
| **Embedder** | Chunks article content (800 chars, 200 overlap), prepends `"passage: {title}"` for E5 compatibility, generates 1024-dim vectors via SentenceTransformer |
| **Qdrant Uploader** | Creates a Qdrant collection with named vector `"embedding_text"` (COSINE distance), batch-upserts with deterministic UUIDv5 point IDs |
| **Qdrant Retriever** | Encodes query with `"query: {text}"` prefix, searches Qdrant for top-K most similar chunks |
| **Groq LLM** | Generates Arabic medical answers using `openai/gpt-oss-20b` with a strict system prompt |
| **Chat Widget** | Arabic RTL frontend with typewriter animation, health checks, and source links |

---

## Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | >=3.10 | Runtime language |
| FastAPI | >=0.129.0 | REST API framework |
| Uvicorn | >=0.40.0 | ASGI server |
| Qdrant Client | >=1.16.2 | Vector database client (cloud) |
| SentenceTransformers | >=5.2.2 | Local embedding model inference |
| Groq (SDK) | >=1.0.0 | LLM API client |
| BeautifulSoup4 | >=4.14.3 | HTML parsing for scraping |
| Requests | >=2.32.5 | HTTP client |
| python-dotenv | >=1.2.1 | Environment variable loading |
| SQLite | (stdlib) | Metadata & source storage |
| HuggingFace Hub | (via sentence-transformers) | Model hosting (`intfloat/multilingual-e5-large`) |

---

## Project Structure

```
asnany_article_rag_production/
│
├── .env.example                  # Template for all required environment variables
├── .gitignore                    # Ignores __pycache__, .venv, .env, logs/, database.db, articles.csv, .cache/
├── .python-version               # Pins Python to 3.10
├── pyproject.toml                # Project metadata + uv dependency declarations
├── uv.lock                       # Lockfile for deterministic uv installs
├── main.py                       # Entry point: scrape → seed → embed → upload to Qdrant
├── run.py                        # Entry point: start FastAPI server with uvicorn on port 8000
├── fastapi_embedding.py          # Standalone server with POST /run-embedding to trigger pipeline
│
├── ai/                           # AI / chat logic
│   ├── prompt/
│   │   └── system_prompt.txt     # Arabic system prompt for the LLM (medical answer generator)
│   ├── chatbot/
│   │   ├── qdrant_retriever.py   # Embeds query, searches Qdrant, returns relevant chunks
│   │   ├── sql_fetch.py          # Fetches article title + URL from SQLite by blog_id
│   │   └── reply.py              # Builds context, calls Groq API, returns answer + deduped sources
│   └── endpoint/
│       ├── chat.py               # FastAPI router: POST /chat/ validation, orchestration, logging
│       └── fastapi.py            # FastAPI app factory: CORS, health check, mounts chat router
│
├── database/                     # Data storage / embedding / upload
│   ├── database.db               # SQLite database (created at runtime — gitignored)
│   ├── database_server.py        # SQL seeding from CSV + per-article embedding pipeline
│   ├── embedder.py               # Text chunking, SentenceTransformer embedding, Qdrant point prep
│   ├── qdrant_uploader.py        # Collection creation, batch upsert, UUID normalization
│   └── tables/
│       └── blog.py               # SQLite DDL: CREATE TABLE blog (id, title, url UNIQUE, content, is_embedded)
│
├── scraper/                      # Web scraping
│   ├── articles.csv              # Scraped data output (created at runtime — gitignored)
│   └── asnany_scraper.py         # WordPress scraper with URL normalization and incremental mode
│
├── web/
│   └── index.html                # Chat widget frontend (Arabic RTL, typewriter effect, source links)
│
└── logs/
    └── chat_logs.jsonl           # JSONL log of every chat interaction (created at runtime)
```

---

## Prerequisites

- **Python** >= 3.10
- **uv** package manager — install it:
  ```bash
  pip install uv
  ```
  or see [the official docs](https://docs.astral.sh/uv/#installation)
- **Qdrant** — a cloud cluster (e.g., [Qdrant Cloud](https://cloud.qdrant.io)) or a local instance with URL + API token
- **Groq API key** — obtain from [console.groq.com](https://console.groq.com)
- **HuggingFace token** — required to download the gated model `intfloat/multilingual-e5-large`; get one at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

---

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/asnany_article_rag_production.git
cd asnany_article_rag_production
```

### 2. Install dependencies with uv

```bash
uv sync
```

This creates a virtual environment and installs all packages from `pyproject.toml` and `uv.lock`.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials. Every variable is documented below:

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `GROQ_TOKEN` | Groq API key for LLM access | Yes | `gsk_abc123...` |
| `GROQ_MODEL` | LLM model name on Groq | Yes | `openai/gpt-oss-20b` |
| `GROQ_BASE_URL` | Groq API base URL | No | `https://api.groq.com/openai/v1` |
| `GROQ_TIMEOUT` | HTTP request timeout (seconds) | No | `60` |
| `GROQ_MAX_COMPLETION_TOKENS` | Max tokens for LLM response | No | `500` |
| `GROQ_TEMPERATURE` | LLM temperature | No | `0.2` |
| `QDRANT_TOKEN` | Qdrant Cloud API key | Yes | `eyJhbGciOi...` |
| `QDRANT_URL` | Qdrant cluster URL | Yes | `https://xxx.us-east4-0.gcp.cloud.qdrant.io` |
| `QDRANT_COLLECTION` | Qdrant collection name | No | `asnany_article_rag_production` |
| `QDRANT_TIMEOUT` | Qdrant client timeout (seconds) | No | `300` |
| `QDRANT_UPSERT_BATCH_SIZE` | Batch size for Qdrant upsert | No | `8` |
| `HF_TOKEN` | HuggingFace token for gated model access | Yes | `hf_abc123...` |
| `HF_MODEL` | SentenceTransformer embedding model | Yes | `intfloat/multilingual-e5-large` |
| `EMBED_BATCH_SIZE` | Batch size for SentenceTransformer.encode | No | `64` |
| `CONTEXT_MAX_CHARS` | Max characters for LLM context window | No | `10000` |
| `ARTICLE_MAX_CHARS` | Max chars per chunk in context | No | `2000` |
| `RETRIEVER_TOP_K` | Number of chunks to retrieve from Qdrant | No | `3` |
| `CHUNK_SIZE` | Character chunk size for text splitting | No | `800` |
| `CHUNK_OVERLAP` | Character overlap between chunks | No | `200` |

---

## Running the Project

### Full data pipeline (scrape → seed → embed → upload)

```bash
python main.py
```

This runs four stages sequentially:
1. Scrapes new articles from `blog.asnany.net` (incremental — skips known URLs)
2. Seeds the SQLite database from `scraper/articles.csv`
3. Checks if the Qdrant collection exists (if not, resets embedding state)
4. Embeds only unembedded articles (`is_embedded = 0`) and uploads to Qdrant

### FastAPI server (chatbot backend)

```bash
python run.py
```

Starts uvicorn on `0.0.0.0:8000` with hot reload. Endpoints:
- `GET  /` — welcome message
- `GET  /health` — health check
- `POST /chat/` — ask a question

### Scraper only

```bash
python -m scraper.asnany_scraper
```

Scrapes all article pages from the WordPress blog and appends new articles to `scraper/articles.csv`.

### Embedding trigger endpoint (standalone server)

```bash
python fastapi_embedding.py
```

Starts a separate FastAPI server with `POST /run-embedding` that runs the full pipeline (`main.py`) in a background thread.

---

## API Reference

### `GET /`

Returns a welcome message.

**Response** `200 OK`
```json
{"message": "Asnany AI API is running"}
```

**Example:**
```bash
curl http://localhost:8000/
```

---

### `GET /health`

Health check endpoint.

**Response** `200 OK`
```json
{"status": "ok", "service": "asnany-ai"}
```

**Example:**
```bash
curl http://localhost:8000/health
```

---

### `POST /chat/`

Main Q&A endpoint. Accepts an Arabic medical question and returns an answer with sources.

**Request Body**
```json
{
  "query": "ما هي أسباب تسوس الأسنان؟"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Arabic medical/dental question (minimum 6 characters) |

**Response** `200 OK`
```json
{
  "reply": "تسوس الأسنان يحدث بسبب تراكم البلاك الناتج عن...",
  "sources": [
    {"title": "أسباب تسوس الأسنان وعلاجه", "url": "https://blog.asnany.net/..."},
    {"title": "الوقاية من تسوس الأسنان", "url": "https://blog.asnany.net/..."}
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `reply` | string | Arabic answer generated by the LLM |
| `sources` | array | Deduplicated list of source articles (title + url) |

**Error Responses**

| Status | Condition | Example Response |
|--------|-----------|-----------------|
| `400` | Empty query | `{"detail": "query cannot be empty"}` |
| `500` | Retriever failure | `{"detail": "retriever failed: ..."}` |
| `500` | Database failure | `{"detail": "database fetch failed: ..."}` |
| `500` | LLM failure | `{"detail": "reply generation failed: ..."}` |

**Example:**
```bash
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "ما هي أسباب تسوس الأسنان؟"}'
```

---

### `POST /run-embedding`

Trigger the full pipeline (scrape → seed → embed → upload) in a background thread.

**Request Body:** None

**Response** `200 OK`
```json
{"status": "started", "message": "Embedding job started in background"}
```

If a job is already running:
```json
{"status": "busy", "message": "Embedding already running"}
```

**Example:**
```bash
curl -X POST http://localhost:8001/run-embedding
```

---

## How RAG Works

### Step 1: Article Ingestion

1. **Scrape** — `asnany_scraper.py` visits the WordPress blog paginated listing (`/`, `/page/2/`, ...), extracts each article's title (from `<h1 class="wp-block-post-title">`) and content (from `<div class="entry-content">`), normalizes URLs (lowercase, removes fragments and tracking params), and appends new articles to `articles.csv`.
2. **Seed** — `database_server.py` reads the CSV and inserts rows into SQLite with `INSERT OR IGNORE` — the `UNIQUE` constraint on `url` prevents duplicates.
3. **Chunk** — `embedder.py` splits each article's content into overlapping chunks of 800 characters with 200 characters of overlap (a sliding window).
4. **Embed** — Each chunk is prefixed with `"passage: {title}\n\n"` (the E5 model expects this format) and encoded into a 1024-dimensional vector using `intfloat/multilingual-e5-large` via SentenceTransformer.
5. **Upload** — Each chunk becomes a Qdrant point with a deterministic ID (`{blog_id}_{chunk_index}` → UUIDv5), the named vector `embedding_text`, and a payload containing `blog_id`, `chunk_index`, and `chunk_text`. Points are upserted in batches of 8. After each article's chunks are successfully uploaded, the article is marked `is_embedded = 1` in SQLite.

### Step 2: Answering a Question

1. **User types** a question in the Arabic chat widget (`web/index.html`) or sends a `POST /chat/` request.
2. **Short/greeting filter** — queries under 6 characters or containing greeting keywords return a polite message without hitting the database.
3. **Retrieve** — The question is encoded with the prefix `"query: {text}"` using the same embedding model, then Qdrant searches for the top-3 most similar chunks using COSINE distance.
4. **Fetch sources** — The unique `blog_id` values from the retrieved chunks are used to look up the article title and URL from SQLite.
5. **Build context** — Retrieved chunks are assembled into a structured context (up to `CONTEXT_MAX_CHARS` characters) with `[CHUNK 1] TEXT: ...` markers.
6. **Generate answer** — The system prompt, user question, and context are sent to Groq's `openai/gpt-oss-20b` model. The prompt instructs the LLM to answer in Arabic, use the context as its primary reference, avoid fabricating statistics, and never mention sources or URLs in the answer text.
7. **Return** — The LLM's answer is cleaned of Arabic diacritics, deduplicated source links are appended, and the final `{reply, sources}` response is returned to the user and logged to `chat_logs.jsonl`.

---

## Deployment Notes

- **HuggingFace model download (~1.1 GB):** The embedding model `intfloat/multilingual-e5-large` downloads automatically on first run via SentenceTransformer. The cache directory is `.cache/` (gitignored). Ensure sufficient disk space and internet connectivity on the deployment server.
- **Runtime-created files:** The following files are gitignored and created at runtime:
  - `database/database.db` — SQLite database
  - `logs/chat_logs.jsonl` — chat interaction logs
  - `scraper/articles.csv` — scraped article data
  - `.cache/` — HuggingFace model cache
- **Hardcoded API URL in frontend:** The chat widget at `web/index.html` hardcodes `const API_BASE = "https://api.alahliadental.com"` (line 302). Change this to match your deployment URL before using the frontend.
- **CORS:** The FastAPI server allows all origins (`allow_origins=["*"]`). Restrict this in production.
- **No authentication:** The API has no authentication layer. Add API key validation or a reverse proxy for production use.

---

## Known Limitations

1. **Hardcoded API URL** — `web/index.html` has `const API_BASE = "https://api.alahliadental.com"` hardcoded in two places, making it impossible to switch environments without editing the file.
2. **Synchronous architecture** — All Qdrant, SQLite, and Groq calls are synchronous (`def`, not `async def`). Long requests block the entire event loop.
3. **Character-based chunking** — Text is split at exact character boundaries (800 chars, 200 overlap), which can cut sentences or words in half. No sentence-aware or semantic splitting is used.
4. **No similarity threshold** — The retriever returns the top-K results regardless of how low the similarity score is, which can lead to irrelevant context being fed to the LLM.
5. **Wide-open CORS** — `allow_origins=["*"]` allows any website to call the API.
6. **No rate limiting** — The chat endpoint has no request rate limiting or throttling.
7. **No caching** — Every query independently embeds the input, searches Qdrant, fetches from SQLite, and calls Groq. Repeated identical queries are processed fresh each time.
8. **No user authentication** — The API is fully open; there is no mechanism to identify or restrict users.
9. **Inconsistent default values** — `QDRANT_TIMEOUT` defaults to `120` in `main.py` but `60` in `qdrant_retriever.py`.
10. **Large model download** — The embedding model (~1.1 GB) downloads on first run, which can be slow and requires substantial disk space.

---

## License

MIT
