# Milestone 0 — Audit Findings

## Existing FastAPI Routes

### Main API Server (`run.py` → `ai/endpoint/fastapi.py`)

| Method | Path     | Location                          | Description               |
|--------|----------|-----------------------------------|---------------------------|
| GET    | `/`      | `ai/endpoint/fastapi.py:33`       | Root welcome message      |
| GET    | `/health`| `ai/endpoint/fastapi.py:26`       | Health check              |
| POST   | `/chat/` | `ai/endpoint/chat.py:210`         | Chat Q&A endpoint         |

All routes are registered on a single FastAPI app with CORS enabled (`allow_origins=["*"]`).

### Embedding Trigger Server (`fastapi_embedding.py`)

| Method | Path             | Location                     | Description                           |
|--------|------------------|------------------------------|---------------------------------------|
| POST   | `/run-embedding` | `fastapi_embedding.py:34`    | Triggers `main.py` pipeline in thread |

This is a **separate** FastAPI instance, not part of the main API server.

---

## Existing Endpoint Details

### GET /health
- **Response:** `{"status": "ok", "service": "asnany-ai"}`
- **Status code:** 200
- **Reusable:** Yes — dashboard health section can call this for API status.

### GET /
- **Response:** `{"message": "Asnany AI API is running"}`
- **Status code:** 200
- **Reusable:** No direct dashboard use, confirms server is alive.

### POST /chat/
- **Request body:** `{"query": "string"}`
- **Response:** `{"reply": "string", "sources": [{"title": "string", "url": "string"}]}`
- **Status codes:** 200, 400 (empty query), 500 (retriever/DB/LLM failure)
- **Flow:** Validate → greeting check → Qdrant retrieval → MySQL source fetch → Groq LLM call → log to JSONL
- **Reusable:** Yes — dashboard Chat Test section can call this directly.

### POST /run-embedding (separate server)
- **Response:** `{"status": "started", "message": "..."}` or `{"status": "busy", "message": "..."}`
- **Status codes:** 200, 404 (main.py missing)
- **Behavior:** Runs `python main.py` in background thread, guarded by a threading lock.
- **Reusable:** Yes — dashboard Embedding section can call this directly.

---

## Reusable Services

| Service    | Module / File                       | Key Functions                          | Dashboard Use                        |
|------------|--------------------------------------|----------------------------------------|--------------------------------------|
| Scraper    | `scraper/asnany_scraper.py`          | `scrape_all_articles()`, `scrape_article()` | Scraper tab trigger              |
| Embedding  | `database/embedder.py`               | `embed_blog_articles()`, `chunk_text()`| Embedding tab trigger                |
| Chat       | `ai/chatbot/qdrant_retriever.py`     | `retrieve_chunks()`                    | Chat Test tab                        |
|            | `ai/chatbot/sql_fetch.py`            | `fetch_sources_by_ids()`               | Chat Test tab                        |
|            | `ai/chatbot/reply.py`                | `generate_reply()`                     | Chat Test tab                        |
| Health     | `ai/endpoint/fastapi.py`             | `health_check()`                       | Health tab                           |
| DB         | `database/database_server.py`        | `insert_blog_article()`, `load_known_urls_from_db()` | Knowledge tab CRUD |
| Qdrant     | `database/qdrant_uploader.py`        | `upload_embeddings()`, `ensure_collection()` | Embedding tab                  |

---

## Database Audit

### blog Table Schema

Defined in `database/tables/blog.py:10-26`:

```sql
CREATE TABLE IF NOT EXISTS blog (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    title       VARCHAR(500) NOT NULL,
    url         VARCHAR(1000) NOT NULL,
    content     LONGTEXT NOT NULL,
    is_embedded TINYINT(1) NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_blog_url (url(255)),
    INDEX idx_blog_is_embedded (is_embedded),
    INDEX idx_blog_url_prefix (url(255))
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Available Fields

| Field        | Type            | Notes                                    |
|--------------|-----------------|------------------------------------------|
| id           | BIGINT UNSIGNED | Auto-increment primary key               |
| title        | VARCHAR(500)    | Article title                            |
| url          | VARCHAR(1000)   | Normalized URL, unique key on first 255  |
| content      | LONGTEXT        | Full article body                        |
| is_embedded  | TINYINT(1)      | 0 = not embedded, 1 = embedded in Qdrant |
| created_at   | TIMESTAMP       | Auto-set on insert                       |
| updated_at   | TIMESTAMP       | Auto-updates on row modification         |

### is_embedded Field
- Default: `0` (not embedded)
- Set to `1` per-article only after successful Qdrant upload (`database/database_server.py:201-206`)
- Rolled back to `0` for all rows when Qdrant collection is missing (`main.py:35-47` — full rebuild mode)
- Indexed: `idx_blog_is_embedded` for efficient filtering

### Article Count Query
```sql
SELECT COUNT(*) FROM blog;            -- total
SELECT COUNT(*) FROM blog WHERE is_embedded = 1;  -- embedded
SELECT COUNT(*) FROM blog WHERE is_embedded = 0;  -- pending
```

### Delete Workflow
**No delete API exists in the current codebase.** The pipeline only inserts and updates. The only delete-related code:
- `scripts/dedupe_mysql_blog_urls.py` — removes duplicate URL rows (dry-run by default, not part of the API)
- `scripts/check_duplicate_urls.py` — read-only diagnostic

**For Dashboard V1:** A delete endpoint must be built from scratch (Milestone 2). It needs to:
1. Delete the row from MySQL `blog` table
2. Delete corresponding Qdrant points by `blog_id` prefix
3. Log the event to `dashboard_logs`

---

## Isolation Verification

- No Python file imports from or references `dashboard/` directory (confirmed via `grep`).
- `dashboard/` is completely standalone HTML/CSS/JS — no build step, no framework, no backend dependency.
- The existing RAG workflow (`main.py`, `run.py`, `fastapi_embedding.py`) is untouched.
