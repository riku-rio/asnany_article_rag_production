# dashboard/docs/DB_SCHEMA.md

# Dashboard Database Schema

Version: 1.0

Status: Approved

---

# Purpose

This document defines the database schema required for Dashboard V1.

The primary goal is:

> Extend the existing project with the minimum number of new tables.

The dashboard must reuse existing project data whenever possible.

---

# Database Engine

```text
MySQL 8+
```

---

# Existing Tables

The dashboard must reuse existing tables.

---

## blog

Already exists.

Current project source of truth.

Used for:

* Knowledge List
* Knowledge Details
* Embedded Status
* Delete Operations
* Dashboard Statistics

---

### Existing Structure

```sql
CREATE TABLE blog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500),
    url VARCHAR(1000) UNIQUE,
    content LONGTEXT,
    is_embedded TINYINT DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

### Dashboard Usage

Overview:

```text
Total Knowledge
Embedded Knowledge
Pending Knowledge
```

Knowledge Tab:

```text
List
View
Delete
```

No additional migration required.

---

# New Tables

Dashboard V1 introduces only two new tables.

---

# dashboard_logs

Purpose:

Store operational events for dashboard visibility.

Examples:

* Scraper Started
* Scraper Completed
* Embedding Started
* Embedding Completed
* Rebuild Started
* Rebuild Completed
* Knowledge Deleted
* System Error

---

## Schema

```sql
CREATE TABLE dashboard_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    event_type VARCHAR(100) NOT NULL,

    message TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Example Records

```text
ID: 1

event_type:
scraper_started

message:
Scraper execution started

created_at:
2026-06-14 10:00:00
```

---

```text
ID: 2

event_type:
embedding_completed

message:
118 articles embedded successfully

created_at:
2026-06-14 10:05:00
```

---

## Supported Event Types

```text
scraper_started
scraper_completed
scraper_failed

embedding_started
embedding_completed
embedding_failed

rebuild_started
rebuild_completed
rebuild_failed

knowledge_deleted

system_error
```

---

# chat_logs

Purpose:

Store dashboard analytics.

Used for:

* Questions Count
* Chat Statistics
* Recent Questions

This table replaces the need to parse JSONL files for dashboard metrics.

---

## Schema

```sql
CREATE TABLE chat_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    question TEXT NOT NULL,

    answer LONGTEXT,

    response_time_ms INT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Example Record

```text
question:
What causes tooth decay?

answer:
Tooth decay occurs because...

response_time_ms:
1250
```

---

## Dashboard Usage

Overview:

```text
Total Questions
Questions Today
Questions This Month
```

Analytics:

```text
Question Volume
Recent Questions
```

---

# No Additional Tables

The following tables are intentionally excluded.

---

## users

Reason:

Single Admin Dashboard.

No user management.

---

## roles

Reason:

No RBAC.

---

## permissions

Reason:

No RBAC.

---

## sources

Reason:

Existing project already uses blog.

---

## documents

Reason:

Overengineering for V1.

---

## chunks

Reason:

Internal implementation detail.

Dashboard does not need chunk visibility.

---

## embeddings

Reason:

Stored in Qdrant.

Not MySQL.

---

## vector_index

Reason:

Stored in Qdrant.

---

## reports

Reason:

Reports generated dynamically.

No storage needed.

---

## settings

Reason:

Not required in V1.

Can be added later.

---

# Relationships

Dashboard V1 contains no relational complexity.

```text
blog

dashboard_logs

chat_logs
```

All tables are independent.

---

# Query Examples

---

## Total Knowledge

```sql
SELECT COUNT(*)
FROM blog;
```

---

## Embedded Knowledge

```sql
SELECT COUNT(*)
FROM blog
WHERE is_embedded = 1;
```

---

## Pending Knowledge

```sql
SELECT COUNT(*)
FROM blog
WHERE is_embedded = 0;
```

---

## Total Questions

```sql
SELECT COUNT(*)
FROM chat_logs;
```

---

## Questions Today

```sql
SELECT COUNT(*)
FROM chat_logs
WHERE DATE(created_at) = CURDATE();
```

---

## Latest Logs

```sql
SELECT *
FROM dashboard_logs
ORDER BY id DESC
LIMIT 50;
```

---

# Indexes

Recommended:

```sql
CREATE INDEX idx_blog_embedded
ON blog(is_embedded);
```

---

```sql
CREATE INDEX idx_dashboard_logs_created_at
ON dashboard_logs(created_at);
```

---

```sql
CREATE INDEX idx_chat_logs_created_at
ON chat_logs(created_at);
```

---

# Data Retention

dashboard_logs:

```text
Keep Last 90 Days
```

Optional cleanup job.

---

chat_logs:

```text
Keep Forever
```

Useful for analytics.

---

# Migration Summary

Dashboard V1 requires:

```sql
CREATE TABLE dashboard_logs (...);

CREATE TABLE chat_logs (...);
```

No modifications required to:

```text
blog
```

No additional infrastructure required.

No schema redesign required.

---

# Final Schema Statement

Dashboard V1 intentionally keeps the database extremely small.

The existing blog table remains the primary knowledge source.

Only two lightweight tables are introduced:

* dashboard_logs
* chat_logs

This minimizes complexity while providing enough data for monitoring, analytics, and operational visibility.
