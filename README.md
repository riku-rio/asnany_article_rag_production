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
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DATA INGESTION (main.py)                           │
│                                                                              │
│  blog.asnany.net                                                            │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌───────────┐  │
│  │  Scraper     │───▶│  MySQL       │───▶│  Embedder     │───▶│  Qdrant   │  │
│  │  (asnany_   │    │  (database_  │    │  (sentence-   │    │  Uploader │  │
│  │  scraper.py) │    │  server.py)  │    │  transformers) │    │  (batch)  │  │
│  └─────────────┘    └──────────────┘    └───────────────┘    └───────────┘  │
│       │                    │                      │                │         │
│       ▼                    ▼                      ▼                ▼         │
│  articles.csv       MySQL (source of truth)   chunk + embed      Qdrant     │
│  (CSV backup)       ┌──────────────────────┐  → passage: ...     Cloud      │
│                     │ blog (articles)       │                 (COSINE)       │
│                     │ dashboard_logs        │                               │
│                     │ chat_logs             │                               │
│                     └──────────────────────┘                               │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                           QUERY PIPELINE (run.py)                            │
│                                                                              │
│  ┌──────────┐    ┌────────────────┐    ┌──────────────┐    ┌────────────┐   │
│  │  Chat     │───▶│  Qdrant        │───▶│  MySQL Fetch │───▶│  Groq LLM  │   │
│  │  Widget   │    │  Retriever     │    │  (sources)   │    │  (answer)  │   │
│  │  (RTL UI) │    │  (top-K=3)     │    │              │    │            │   │
│  └──────────┘    └────────────────┘    └──────────────┘    └────────────┘   │
│       │                    │                      │                │         │
│       │                    ▼                      │                ▼         │
│       │           query → embedding               │         Arabic reply    │
│       │           → COSINE search                 │         + sources       │
│       ├──────────────────────────────────────────────────────────────────────┤
│       │            chat_logs.jsonl + chat_logs (DB table)                   │
│       └──────────────────────────────────────────────────────────────────────┘
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                      AUTH & DASHBOARD (run.py)                            │
│                                                                              │
│  ┌──────────────────┐        ┌──────────────────────────────────────┐       │
│  │  Dashboard        │───────▶│  Auth API   (/api/admin/auth)       │       │
│  │  (dashboard/     │        │  (public)                            │       │
│  │   index.html)    │        │  POST /login    GET  /me            │       │
│  │                  │        │  POST /logout                        │       │
│  │  • Overview      │        ├──────────────────────────────────────┤       │
│  │  • Knowledge     │        │  Admin API   (/api/admin/*)          │       │
│  │  • Scraper       │        │  (JWT-protected with require_auth)   │       │
│  │  • Embedding     │        │                                      │       │
│  │  • Chat Test     │        │  GET  /stats        POST /scrape     │       │
│  │  • Users         │        │  GET  /knowledge    POST /embedding   │       │
│  │  • Logs          │        │  GET  /knowledge/{id} POST /rebuild  │       │
│  │  • Health        │        │  DELETE /knowledge/{id}             │       │
│  │                  │        │  POST /knowledge/add-url            │       │
│  └──────────────────┘        │  GET  /logs         POST /chat-test  │       │
│                              │  GET  /health      GET/POST /users   │       │
│                              │  PATCH /users/{id}                  │       │
│                              │  DELETE /users/{id}                 │       │
│                              │  POST /users/{id}/reset-password    │       │
│                              └──────┬───────────────────────────────┘       │
│                                     │                                      │
│  ┌───────────────────────┐         ▼                                      │
│  │  Lifespan Startup     │  ┌──────────────────────┐   ┌──────────────────┐│
│  │  (auto on boot):      │  │  MySQL               │   │  Qdrant          ││
│  │  • Create dashboard_ │  │  (dashboard_logs,     │   │  (health check)  ││
│  │    users table        │  │   dashboard_users,    │   │                  ││
│  │  • Seed owner from   │  │   blog, chat_logs)    │   │                  ││
│  │    .env               │  └──────────────────────┘   └──────────────────┘│
│  └───────────────────────┘                                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Role |
|-----------|------|
| **Scraper** | Incrementally crawls the WordPress blog paginated listing, extracts article title/content, normalizes URLs, writes to CSV or inserts directly into MySQL |
| **MySQL Seed** | Reads CSV into a MySQL database with normalized URL deduplication (`INSERT IGNORE`) |
| **Embedder** | Chunks article content (800 chars, 200 overlap), prepends `"passage: {title}"` for E5 compatibility, generates 1024-dim vectors via SentenceTransformer |
| **Qdrant Uploader** | Creates a Qdrant collection with named vector `"embedding_text"` (COSINE distance), batch-upserts with deterministic UUIDv5 point IDs |
| **Qdrant Retriever** | Encodes query with `"query: {text}"` prefix, searches Qdrant for top-K most similar chunks |
| **Groq LLM** | Generates Arabic medical answers using `openai/gpt-oss-20b` with a strict system prompt |
| **Chat Widget** | Arabic RTL frontend with typewriter animation, health checks, and source links |
| **Admin API & Auth** | Two FastAPI routers: public `auth_router` (login/logout/me) and JWT-protected `router` (19 endpoints under `/api/admin`) for stats, knowledge CRUD, scraper/embedding control, user management, job status, multi-component health |
| **Admin Service** | Business logic layer — stats aggregation, Qdrant/Groq health checks, user CRUD with bcrypt hashing, JWT authentication, background job management with threading lock, single-URL knowledge addition |
| **Dashboard Logger** | Writes operational events (`scraper_started`, `embedding_completed`, `system_error`, etc.) to the `dashboard_logs` MySQL table |
| **Dashboard Frontend** | Single-file Arabic RTL admin UI with 8 tabs (Overview, Knowledge, Scraper, Embedding, Chat Test, Users, Logs, Health), login screen, theme switching, responsive layout |
| **Auth System** | JWT-based session authentication with 24-hour expiry, httponly cookie, bcrypt password hashing, owner/admin roles |
| **Dashboard Users Table** | MySQL `dashboard_users` table with `owner`/`admin` roles, auto-created and owner-seeded via lifespan handler on server startup |
| **Migration Scripts** | One-time scripts to create `dashboard_logs` and `chat_logs` MySQL tables |
| **Utility Scripts** | MySQL import, deduplication, diagnostics, connectivity test, and chat log verification scripts |

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
| bcrypt | >=4.0.0 | Password hashing for dashboard authentication |
| pyjwt | >=2.0.0 | JWT token creation and validation for dashboard sessions |
| Requests | >=2.32.5 | HTTP client |
| PyMySQL | >=1.2.0 | MySQL client for article source of truth |
| python-dotenv | >=1.2.1 | Environment variable loading |
| MySQL | >=8.0 | Primary article storage (source of truth) |
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
├── main.py                       # Entry point: scrape → MySQL → embed → upload to Qdrant
├── run.py                        # Entry point: start FastAPI server with uvicorn on port 8000
├── fastapi_embedding.py          # Standalone server with POST /run-embedding to trigger pipeline
│
├── ai/                           # AI / chat / admin logic
│   ├── prompt/
│   │   └── system_prompt.txt     # Arabic system prompt for the LLM (medical answer generator)
│   ├── chatbot/
│   │   ├── qdrant_retriever.py   # Embeds query, searches Qdrant, returns relevant chunks
│   │   ├── sql_fetch.py          # Fetches article title + URL from MySQL by blog_id
│   │   └── reply.py              # Builds context, calls Groq API, returns answer + deduped sources
│   └── endpoint/
│       ├── admin.py              # FastAPI admin routers: auth (public) + protected /api/admin (stats, CRUD, users, health, background jobs)
│       ├── chat.py               # FastAPI router: POST /chat/ validation, orchestration, logging
│       └── fastapi.py            # FastAPI app factory: CORS, health check, mounts chat + admin routers, /dashboard static
│
├── dashboard/                    # Admin dashboard (no build step, single HTML file)
│   ├── index.html                # Dashboard frontend (all inline CSS/JS, 8 tabs, login screen, theme support)
│   └── docs/                     # Specification documents
│       ├── API.md                # Admin API endpoint specifications
│       ├── DB_SCHEMA.md          # New database table specifications
│       ├── TASKS.md              # Implementation tasks & milestones
│       ├── UI.md                 # User interface specifications
│       ├── SCOPE.md              # Dashboard scope definition
│       └── M0_FINDINGS.md        # Milestone 0 audit findings
│
├── database/                     # Data storage / embedding / upload / admin
│   ├── db.py                     # MySQL connection manager (PyMySQL, env-based config)
│   ├── database_server.py        # MySQL seeding from CSV + per-article embedding pipeline
│   ├── embedder.py               # Text chunking, SentenceTransformer embedding, Qdrant point prep
│   ├── qdrant_uploader.py        # Collection creation, batch upsert, UUID normalization
│   ├── admin_service.py          # Admin business logic: stats, knowledge CRUD, health checks, background jobs
│   ├── dashboard_logger.py       # Operational event logging to dashboard_logs table
│   └── tables/
│       ├── blog.py               # MySQL DDL: CREATE TABLE blog (articles)
│       ├── dashboard_logs.py     # MySQL DDL: dashboard_logs (operational event log)
│       ├── chat_logs.py          # MySQL DDL: chat_logs (chat analytics)
│       └── dashboard_users.py    # MySQL DDL: dashboard_users (auth: owner/admin roles)
│
├── scraper/                      # Web scraping
│   ├── articles.csv              # Scraped data backup (exported from MySQL at runtime — gitignored)
│   └── asnany_scraper.py         # WordPress scraper with URL normalization and incremental mode
│
├── scripts/                      # Utility scripts
│   ├── import_csv_to_mysql.py    # One-time legacy CSV → MySQL import
│   ├── test_mysql.py             # MySQL connectivity smoke test
│   ├── check_duplicate_urls.py   # Diagnostic for duplicate normalized URLs in MySQL
│   ├── dedupe_mysql_blog_urls.py # Deduplicate tool (dry-run by default)
│   ├── migrate_001_create_dashboard_logs.py  # Create dashboard_logs table
│   ├── migrate_002_create_chat_logs.py       # Create chat_logs table
│   ├── migrate_003_create_dashboard_users.py # Create dashboard_users table
│   ├── verify_chat_logs.py       # Verify chat_logs insert/select/delete workflow
│   └── delete_all_users.py       # Delete all dashboard users (recovery/reset tool)
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
- **MySQL** >= 8.0 — the article source of truth. Connect via a local or cloud MySQL instance.

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
| `GROQ_MAX_COMPLETION_TOKENS` | Max tokens for LLM response | No | `500` |
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
| `MYSQL_HOST` | MySQL server hostname | Yes | `localhost` |
| `MYSQL_PORT` | MySQL server port | No | `3306` |
| `MYSQL_USER` | MySQL username | Yes | `root` |
| `MYSQL_PASSWORD` | MySQL password | Yes | `password` |
| `MYSQL_DATABASE` | MySQL database name | Yes | `asnany_rag` |
| `DASHBOARD_SECRET_KEY` | JWT signing secret for dashboard sessions | Yes | `xxx` |
| `DASHBOARD_OWNER_USERNAME` | Default owner username seeded on first run | No | `owner` |
| `DASHBOARD_OWNER_PASSWORD` | Default owner password for initial setup | Yes | `your-strong-password-here` |
| `DASHBOARD_OWNER_NAME` | Display name for the seeded owner | No | `Owner` |

---

## Running the Project

### Database migrations

Run these once to create the required MySQL tables:

```bash
uv run python scripts/migrate_001_create_dashboard_logs.py
uv run python scripts/migrate_002_create_chat_logs.py
uv run python scripts/migrate_003_create_dashboard_users.py
```

Note: The `blog` table is auto-created by `main.py` on first run. The `dashboard_users` table is also auto-created (and the owner user seeded) by the FastAPI lifespan handler on server startup.

### Full data pipeline (scrape → MySQL → embed → upload)

```bash
python main.py
```

This runs the following stages sequentially:
1. Ensures the MySQL `blog` table exists
2. Loads known article URLs from MySQL to avoid re-scraping
3. Scrapes new articles from `blog.asnany.net` (incremental — skips known URLs) and inserts directly into MySQL via the `on_article` callback
4. Exports all articles from MySQL to `scraper/articles.csv` as a backup
5. Checks if the Qdrant collection exists (if not, resets `is_embedded = 0` for all articles to trigger a full rebuild)
6. Embeds only unembedded articles (`is_embedded = 0`) and uploads to Qdrant, marking each article as embedded per-article after successful upload

### FastAPI server (chatbot backend + admin dashboard)

```bash
python run.py
```

Starts uvicorn on `0.0.0.0:8000` with hot reload. On startup, the lifespan handler auto-creates the `dashboard_users` MySQL table and seeds the owner user from `DASHBOARD_OWNER_*` env vars.

Serves everything in one process:

**Chatbot endpoints:**
- `GET  /` — welcome message
- `GET  /health` — health check
- `POST /chat/` — ask a question

**Auth API (public):**
- `POST /api/admin/auth/login` — login with username/password
- `POST /api/admin/auth/logout` — logout, clear session cookie
- `GET  /api/admin/auth/me` — return current user info

**Admin API (JWT-protected — see full reference below):**
- `GET    /api/admin/stats` — dashboard summary
- `GET    /api/admin/knowledge` — list all articles
- `GET    /api/admin/knowledge/{id}` — article detail
- `DELETE /api/admin/knowledge/{id}` — delete article
- `POST   /api/admin/knowledge/add-url` — add single article by URL
- `POST   /api/admin/scrape` — trigger scraper
- `POST   /api/admin/embedding` — trigger embedding
- `POST   /api/admin/rebuild` — full rebuild
- `GET    /api/admin/logs` — operational logs
- `POST   /api/admin/chat-test` — test chat
- `GET    /api/admin/health` — multi-component health
- `GET    /api/admin/users` — list dashboard users
- `POST   /api/admin/users` — create user
- `PATCH  /api/admin/users/{id}` — update user
- `DELETE /api/admin/users/{id}` — delete user
- `POST   /api/admin/users/{id}/reset-password` — reset user password

**Dashboard frontend:**
- `GET  /dashboard` — Arabic admin dashboard UI (login required)

### Scraper only

```bash
python -m scraper.asnany_scraper
```

Scrapes all article pages from the WordPress blog and appends new articles to `scraper/articles.csv` (standalone CSV mode). For production, the scraper is called by `main.py` with `write_csv=False` and `on_article=insert_blog_article` for direct MySQL insertion.

### Utility scripts

```bash
# Test MySQL connectivity and verify the blog table
uv run python scripts/test_mysql.py

# One-time legacy CSV import into MySQL
uv run python scripts/import_csv_to_mysql.py

# Check for duplicate normalized URLs in MySQL
uv run python scripts/check_duplicate_urls.py

# Deduplicate MySQL blog URLs (dry-run by default — set DRY_RUN=False inside the script to execute)
uv run python scripts/dedupe_mysql_blog_urls.py

# Create dashboard_logs table (operational event log)
uv run python scripts/migrate_001_create_dashboard_logs.py

# Create chat_logs table (chat analytics)
uv run python scripts/migrate_002_create_chat_logs.py

# Create dashboard_users table (auth)
uv run python scripts/migrate_003_create_dashboard_users.py

# Verify chat_logs insert/select/delete workflow
uv run python scripts/verify_chat_logs.py

# Delete all dashboard users (interactive recovery/reset)
uv run python scripts/delete_all_users.py
```

### Embedding trigger endpoint (standalone server)

```bash
python fastapi_embedding.py
```

Starts a separate FastAPI server on port 8000 with `POST /run-embedding` that runs the full pipeline (`main.py`) in a background thread.

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

### `POST /api/admin/auth/login`

Login with username and password. Returns a JWT session cookie (httponly, 24-hour expiry).

**Request Body**
```json
{
  "username": "owner",
  "password": "your-strong-password-here"
}
```

**Response** `200 OK`
```json
{
  "success": true,
  "message": "Logged in successfully",
  "user": {
    "id": 1,
    "display_name": "Owner",
    "username": "owner",
    "role": "owner"
  }
}
```

**Response** `401`
```json
{"success": false, "message": "Invalid username or password"}
```

---

### `POST /api/admin/auth/logout`

Logout and clear the session cookie.

**Request Body:** None

**Response** `200 OK`
```json
{"success": true, "message": "Logged out successfully"}
```

---

### `GET /api/admin/auth/me`

Return the currently authenticated user's info.

**Response** `200 OK`
```json
{
  "success": true,
  "user": {
    "id": 1,
    "display_name": "Owner",
    "username": "owner",
    "role": "owner"
  }
}
```

---

### `POST /api/admin/users`

Create a new dashboard user. Requires `owner` role.

**Request Body**
```json
{
  "display_name": "Admin User",
  "username": "admin1",
  "password": "securepassword",
  "role": "admin"
}
```

**Response** `200 OK`
```json
{"success": true, "message": "User created"}
```

---

### `GET /api/admin/users`

List all dashboard users.

**Response** `200 OK`
```json
{
  "success": true,
  "data": [
    {"id": 1, "display_name": "Owner", "username": "owner", "role": "owner", "is_active": 1, "last_login_at": null, "created_at": "2026-06-17T12:00:00"}
  ]
}
```

---

### `PATCH /api/admin/users/{user_id}`

Update a user's fields (display_name, role, is_active). Requires `owner` role.

**Request Body**
```json
{
  "display_name": "New Name",
  "role": "admin",
  "is_active": 1
}
```

**Response** `200 OK`
```json
{"success": true, "message": "User updated"}
```

---

### `POST /api/admin/users/{user_id}/reset-password`

Reset a user's password. Requires `owner` role.

**Request Body**
```json
{
  "password": "new-strong-password"
}
```

**Response** `200 OK`
```json
{"success": true, "message": "Password updated"}
```

---

### `DELETE /api/admin/users/{user_id}`

Delete a user. The last `owner` account cannot be deleted.

**Response** `200 OK`
```json
{"success": true, "message": "User deleted"}
```

---

### `POST /api/admin/scrape`

Trigger the scraper in a background thread. Uses a threading lock to prevent concurrent maintenance jobs.

**Request Body:** None

**Response** `200 OK`
```json
{"success": true, "message": "Scraper started"}
```

If a job is already running:
```json
{"success": true, "message": "Scraping is already running"}
```

---

### `POST /api/admin/embedding`

Run the embedding pipeline (incremental — only unembedded articles) in a background thread.

**Request Body:** None

**Response** `200 OK`
```json
{"success": true, "message": "Embedding started"}
```

If a job is already running:
```json
{"success": true, "message": "Embedding is already running"}
```

---

### `POST /api/admin/rebuild`

Full rebuild: resets `is_embedded = 0` for all articles, then re-embeds and uploads everything to Qdrant. Runs in a background thread.

**Request Body:** None

**Response** `200 OK`
```json
{"success": true, "message": "Rebuild started"}
```

If a job is already running:
```json
{"success": true, "message": "A maintenance job is already running"}
```

---

### `GET /api/admin/stats`

Dashboard summary statistics.

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "total_articles": 42,
    "embedded_articles": 40,
    "pending_articles": 2,
    "questions_count": 150,
    "last_scraping": "2026-06-17T10:30:00",
    "last_embedding": "2026-06-17T11:00:00"
  }
}
```

---

### `GET /api/admin/knowledge`

List all articles in the knowledge base.

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Max results (capped at 200) |

**Response** `200 OK`
```json
{
  "success": true,
  "data": [
    {"id": 1, "title": "أسباب تسوس الأسنان", "url": "https://...", "is_embedded": 1, "created_at": "2026-06-01T12:00:00"}
  ]
}
```

---

### `GET /api/admin/knowledge/{id}`

Full article details including content.

**Response** `200 OK`
```json
{
  "success": true,
  "data": {
    "id": 1,
    "title": "أسباب تسوس الأسنان",
    "url": "https://blog.asnany.net/...",
    "content": "نص المقال الكامل...",
    "is_embedded": 1,
    "created_at": "2026-06-01T12:00:00",
    "updated_at": "2026-06-17T11:00:00"
  }
}
```

**Response** `404`
```json
{"success": false, "message": "Knowledge not found"}
```

---

### `DELETE /api/admin/knowledge/{id}`

Delete an article and all its chunks. Removes from MySQL, Qdrant (all points with matching `blog_id`), and logs the event.

**Response** `200 OK`
```json
{"success": true, "message": "Knowledge deleted"}
```

**Response** `404`
```json
{"success": false, "message": "Knowledge not found"}
```

---

### `POST /api/admin/knowledge/add-url`

Add a single article by URL: scrapes the URL, chunks the content, embeds, and uploads to Qdrant atomically.

**Request Body**
```json
{"url": "https://blog.asnany.net/..."}
```

**Response** `200 OK`
```json
{"success": true, "message": "Article added and embedded successfully"}
```

---

### `GET /api/admin/logs`

Recent operational events from the `dashboard_logs` table.

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Number of log entries (capped at 200) |

**Response** `200 OK`
```json
{
  "success": true,
  "data": [
    {"id": 1, "event_type": "rebuild_completed", "message": "Pipeline completed successfully", "created_at": "2026-06-17T11:00:00"}
  ]
}
```

---

### `POST /api/admin/chat-test`

Dashboard-internal chat wrapper. Mirrors `POST /chat/` with the same greeting detection, retrieval, and generation logic.

**Request Body**
```json
{"query": "ما هي أسباب تسوس الأسنان؟"}
```

**Response** `200 OK`
```json
{
  "reply": "تسوس الأسنان يحدث بسبب...",
  "sources": [
    {"title": "أسباب تسوس الأسنان وعلاجه", "url": "https://blog.asnany.net/..."}
  ]
}
```

---

### `GET /api/admin/health`

Multi-component health check.

**Response** `200 OK`
```json
{
  "api": true,
  "database": true,
  "qdrant": true,
  "groq": true
}
```

If a component is down, its value will be `false`.

---

## How RAG Works

### Step 1: Article Ingestion

1. **Scrape** — `asnany_scraper.py` visits the WordPress blog paginated listing (`/`, `/page/2/`, ...), extracts each article's title (from `<h1 class="wp-block-post-title">`) and content (from `<div class="entry-content">`), normalizes URLs (lowercase, decodes percent-encoding, removes fragments and tracking params like `utm_*`, `fbclid`, `gclid`), and inserts directly into MySQL via the `on_article` callback (`insert_blog_article`).
2. **Export backup** — `database_server.py` exports all articles from MySQL to `scraper/articles.csv` as a backup CSV.
3. **Chunk** — `embedder.py` splits each article's content into overlapping chunks of 800 characters with 200 characters of overlap (a sliding window).
4. **Embed** — Each chunk is prefixed with `"passage: {title}\n\n"` (the E5 model expects this format) and encoded into a 1024-dimensional vector using `intfloat/multilingual-e5-large` via SentenceTransformer.
5. **Upload** — Each chunk becomes a Qdrant point with a deterministic ID (`{blog_id}_{chunk_index}` → UUIDv5), the named vector `embedding_text`, and a payload containing `blog_id`, `chunk_index`, and `chunk_text`. Points are upserted in batches of 8. After each article's chunks are successfully uploaded, the article is marked `is_embedded = 1` in MySQL. If the Qdrant collection doesn't exist, all articles are reset to `is_embedded = 0` for a full rebuild.

### Step 2: Answering a Question

1. **User types** a question in the Arabic chat widget (`web/index.html`) or sends a `POST /chat/` request.
2. **Greeting detection** — The query is normalized (lowercased, Arabic Alef variants unified, tatweel removed, punctuation/emoji stripped) and compared against a curated list of Arabic and English greetings. If it's a standalone greeting (or greeting with ≤2 filler tokens), a polite welcome message is returned without hitting the database.
3. **Short query rejection** — Queries under 6 characters return a prompt for a clear medical question.
4. **Retrieve** — The question is encoded with the prefix `"query: {text}"` using the same embedding model, then Qdrant searches for the top-K (default 3) most similar chunks using COSINE distance.
5. **Fetch sources** — The unique `blog_id` values from the retrieved chunks are used to look up the article title and URL from MySQL.
6. **Build context** — Retrieved chunks are assembled into a structured context (up to `CONTEXT_MAX_CHARS` characters) with `[CHUNK 1] TEXT: ...` markers.
7. **Generate answer** — The system prompt, user question, and context are sent to Groq's `openai/gpt-oss-20b` model with retry logic (4 attempts, exponential backoff). The prompt instructs the LLM to answer in Arabic (Modern Standard Arabic), use the context as its primary reference, prioritize meaning over literal wording, always try to answer (do not refuse unnecessarily), avoid fabricating statistics, never mention sources or URLs in the answer text, and output 3–6 short lines maximum with no headings, bullet points, markdown, or extra commentary.
8. **Return** — The LLM's answer is cleaned of Arabic diacritics, deduplicated source links are appended, and the final `{reply, sources}` response is returned to the user. The interaction is logged to `chat_logs.jsonl` and the `chat_logs` MySQL table (with `response_time_ms` and `sources_count`).

---

## Deployment Notes

- **HuggingFace model download (~1.1 GB):** The embedding model `intfloat/multilingual-e5-large` downloads automatically on first run via SentenceTransformer. The cache directory is `.cache/` (gitignored). Ensure sufficient disk space and internet connectivity on the deployment server.
- **Runtime-created files:** The following files are gitignored and created at runtime:
  - `logs/chat_logs.jsonl` — chat interaction logs
  - `scraper/articles.csv` — MySQL backup export
  - `.cache/` — HuggingFace model cache
- **Dynamic API URL in frontend:** The chat widget at `web/index.html` dynamically selects the API base URL based on the hostname: `localhost`/`127.0.0.1` → `http://localhost:8000`, otherwise → `https://blog-chat.alahliadental.com`. Change the production URL to match your deployment.
- **Dashboard authentication:** The admin dashboard at `/dashboard` and all `/api/admin/*` operational endpoints require JWT-based authentication (httponly cookie, 24-hour expiry). The auth endpoints (`/api/admin/auth/login`, `/api/admin/auth/logout`, `/api/admin/auth/me`) are public. Uses bcrypt for password hashing. On first server startup, the `dashboard_users` table is auto-created and the owner user is seeded from `DASHBOARD_OWNER_*` env vars.
- **Database migrations:** New deployments must run `scripts/migrate_001_create_dashboard_logs.py`, `scripts/migrate_002_create_chat_logs.py`, and `scripts/migrate_003_create_dashboard_users.py` to create the required operational tables. The `blog` table is auto-created by `main.py`. The `dashboard_users` table is also auto-created on FastAPI server startup.
- **CORS:** The FastAPI server allows all origins (`allow_origins=["*"]`). Restrict this in production.
- **No chat authentication:** The chat API endpoints (`POST /chat/`) have no authentication layer. Add API key validation or a reverse proxy for production use.

---

## Known Limitations

1. **Dynamic API URL (still environment-specific)** — `web/index.html` selects the API URL based on hostname, but custom deployments must edit `const API_BASE` logic in the frontend. The dashboard at `dashboard/index.html` has the same pattern.
2. **Synchronous architecture** — All Qdrant, MySQL, and Groq calls are synchronous (`def`, not `async def`). Long requests block the entire event loop.
3. **Character-based chunking** — Text is split at exact character boundaries (800 chars, 200 overlap), which can cut sentences or words in half. No sentence-aware or semantic splitting is used.
4. **No similarity threshold** — The retriever returns the top-K results regardless of how low the similarity score is, which can lead to irrelevant context being fed to the LLM.
5. **Wide-open CORS** — `allow_origins=["*"]` allows any website to call the API.
6. **No rate limiting** — The chat endpoint has no request rate limiting or throttling.
7. **No caching** — Every query independently embeds the input, searches Qdrant, fetches from MySQL, and calls Groq. Repeated identical queries are processed fresh each time.
8. **Large model download** — The embedding model (~1.1 GB) downloads on first run, which can be slow and requires substantial disk space.

---

## License

MIT
