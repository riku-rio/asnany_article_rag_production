# dashboard/docs/API.md

# Dashboard API Specification

Version: 1.0

Status: Approved

---

# Purpose

This document defines all API endpoints required by Dashboard V1.

The goal is to provide a lightweight administration layer on top of the existing RAG project.

The API must remain simple.

The API must not become a separate product.

---

# Base URL

```text
/api/admin
```

Examples:

```text
/api/admin/stats
/api/admin/health
/api/admin/embedding
```

---

# Existing Endpoints

The following endpoints already exist and must be reused.

---

## Health Check

### Request

```http
GET /health
```

### Response

```json
{
  "status": "ok",
  "service": "asnany-ai"
}
```

Used by:

* Dashboard Health Tab

---

## Chat Endpoint

### Request

```http
POST /chat/
```

```json
{
  "query": "What is tooth decay?"
}
```

### Response

```json
{
  "reply": "...",
  "sources": []
}
```

Used by:

* Dashboard Chat Test

* Public Chat Widget

---

## Embedding Pipeline

### Request

```http
POST /run-embedding
```

### Response

```json
{
  "status": "started"
}
```

Used by:

* Dashboard Embedding Tab

---

# New Dashboard Endpoints

---

# Stats

Returns dashboard summary information.

---

## Request

```http
GET /api/admin/stats
```

---

## Response

```json
{
  "total_articles": 120,
  "embedded_articles": 118,
  "pending_articles": 2,
  "questions_count": 1523,
  "last_embedding": "2026-06-14T10:30:00Z",
  "last_scraping": "2026-06-14T09:10:00Z"
}
```

---

## Used By

Overview Tab

---

# Knowledge List

Returns indexed knowledge entries.

---

## Request

```http
GET /api/admin/knowledge
```

---

## Response

```json
[
  {
    "id": 1,
    "title": "Tooth Decay",
    "url": "https://example.com/article",
    "is_embedded": true,
    "created_at": "2026-06-14"
  }
]
```

---

## Used By

Knowledge Tab

---

# Knowledge Details

Returns full knowledge information.

---

## Request

```http
GET /api/admin/knowledge/{id}
```

---

## Response

```json
{
  "id": 1,
  "title": "Tooth Decay",
  "url": "https://example.com/article",
  "content": "...",
  "is_embedded": true
}
```

---

## Used By

View Dialog

---

# Delete Knowledge

Deletes a knowledge item.

---

## Request

```http
DELETE /api/admin/knowledge/{id}
```

---

## Response

```json
{
  "success": true,
  "message": "Knowledge deleted"
}
```

---

## Expected Behavior

Must:

* Remove database record
* Remove vector records
* Remove related metadata

---

# Run Embedding

Starts embedding execution.

---

## Request

```http
POST /api/admin/embedding
```

---

## Response

```json
{
  "status": "started",
  "message": "Job started in background"
}
```

When a job is already running:

```json
{
  "status": "busy",
  "message": "A maintenance job is already running"
}
```

---

## Expected Behavior

Runs existing embedding pipeline.

Must not block request.

---

# Run Scraper

Starts scraper execution.

---

## Request

```http
POST /api/admin/scrape
```

---

## Response

```json
{
  "status": "started",
  "message": "Job started in background"
}
```

When a job is already running:

```json
{
  "status": "busy",
  "message": "A maintenance job is already running"
}
```

---

## Expected Behavior

Runs existing scraper.

Must not block request.

---

# Rebuild Embeddings

Re-index entire knowledge base.

---

## Request

```http
POST /api/admin/rebuild
```

---

## Response

```json
{
  "status": "started",
  "message": "Job started in background"
}
```

When a job is already running:

```json
{
  "status": "busy",
  "message": "A maintenance job is already running"
}
```

---

## Expected Behavior

Equivalent to:

```bash
python main.py
```

or internal rebuild service.

---

# Logs

Returns latest activity logs.

---

## Request

```http
GET /api/admin/logs
```

---

## Response

```json
[
  {
    "timestamp": "2026-06-14 10:00:00",
    "event": "Embedding Started"
  },
  {
    "timestamp": "2026-06-14 10:05:00",
    "event": "Embedding Completed"
  }
]
```

---

## Used By

Logs Tab

---

# Chat Test

Wrapper around existing chat endpoint.

---

## Request

```http
POST /api/admin/chat-test
```

```json
{
  "query": "What is tooth decay?"
}
```

---

## Response

```json
{
  "reply": "...",
  "sources": []
}
```

---

## Expected Behavior

Internally calls:

```http
POST /chat/
```

No duplicate logic.

---

# Health Status

Dashboard-friendly health endpoint.

---

## Request

```http
GET /api/admin/health
```

---

## Response

```json
{
  "api": true,
  "database": true,
  "qdrant": true,
  "groq": true
}
```

---

## Expected Checks

### API

FastAPI running.

---

### Database

MySQL reachable.

---

### Qdrant

Collection accessible.

---

### Groq

API reachable.

---

# Error Format

All admin endpoints must return:

```json
{
  "success": false,
  "message": "Human readable error"
}
```

---

# HTTP Status Codes

## Success

```http
200 OK
```

---

## Validation Error

```http
400 Bad Request
```

---

## Not Found

```http
404 Not Found
```

---

## Internal Error

```http
500 Internal Server Error
```

---

# Final Endpoint Inventory

Existing:

```http
GET  /health
POST /chat/
POST /run-embedding
```

New:

```http
GET    /api/admin/stats

GET    /api/admin/knowledge

GET    /api/admin/knowledge/{id}

DELETE /api/admin/knowledge/{id}

POST   /api/admin/scrape

POST   /api/admin/embedding

POST   /api/admin/rebuild

GET    /api/admin/logs

POST   /api/admin/chat-test

GET    /api/admin/health
```

Total New Endpoints:

```text
9
```

Total Dashboard Complexity:

```text
Small
Portfolio-Friendly
Easy To Maintain
```

---

# API Design Rule

If a new dashboard feature requires more than one new endpoint, the feature should be questioned before implementation.

Dashboard V1 must remain lightweight.
