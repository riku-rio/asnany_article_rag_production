# dashboard/docs/UI.md

# Dashboard UI Specification

Version: 1.0

Status: Approved

---

# Purpose

This document defines the user interface requirements for Dashboard V1.

The dashboard is designed for:

* Simplicity
* Clarity
* Fast Navigation
* Non-Technical Users

The dashboard is NOT designed as a complex admin system.

---

# Technical Constraints

Frontend Technology:

```text
Single HTML File
```

Location:

```text
dashboard/index.html
```

Rules:

* One file only
* Inline CSS
* Inline JavaScript
* No React
* No Next.js
* No Routing
* No Build Process

---

# Layout Structure

```text
+--------------------------------------------------+
|                 HEADER                           |
+--------------------------------------------------+

+----------------+---------------------------------+
|                |                                 |
|                |                                 |
|     SIDEBAR    |            CONTENT              |
|                |                                 |
|                |                                 |
+----------------+---------------------------------+
```

---

# Desktop Layout

Sidebar Width:

```text
250px
```

Content Area:

```text
Remaining Width
```

---

# Mobile Layout

Sidebar becomes:

```text
Top Navigation
```

Tabs become scrollable.

---

# Color Philosophy

Style:

```text
Clean
Minimal
Professional
```

Not:

```text
Flashy
Colorful
Complex
```

---

# Navigation

Sidebar contains:

```text
Overview
Knowledge
Scraper
Embedding
Chat Test
Logs
Health
```

---

# Navigation Behavior

Clicking a menu item:

```text
Hide Current Section
Show Selected Section
```

Single-page experience.

No page reloads.

---

# HEADER

Position:

```text
Top
```

Contents:

```text
Dashboard Title

Current System Status
```

Example:

```text
RAG Dashboard

● Online
```

---

# SECTION 1

# Overview

Purpose:

Provide quick visibility.

---

## KPI Cards

Row Layout:

```text
+---------------+
| Total Content |
+---------------+

+---------------+
| Embedded      |
+---------------+

+---------------+
| Pending       |
+---------------+

+---------------+
| Questions     |
+---------------+
```

---

## Statistics Grid

Fields:

```text
Last Scraping

Last Embedding

Database Status

Qdrant Status
```

---

## Refresh Behavior

Auto-refreshes on tab switch and initial load (no separate button needed).

---

# SECTION 2

# Knowledge

Purpose:

View existing knowledge.

---

## Search Input

Placeholder:

```text
Search knowledge...
```

---

## Knowledge Table

Columns:

```text
ID

Title

URL

Embedded

Created At

Actions
```

---

## Embedded Badge

Values:

```text
Embedded
Pending
```

---

## Actions Column

Buttons:

```text
View

Delete
```

---

## View Modal

Contents:

```text
Title

URL

Content
```

Scrollable content.

---

## Delete Modal

Confirmation:

```text
Are you sure?
```

Buttons:

```text
Cancel

Delete
```

---

# SECTION 3

# Scraper

Purpose:

Allow scraping control.

---

## Main Button

```text
Run Scraper
```

Action:

```text
POST /api/admin/scrape
```

---

## Status Card

Displays:

```text
Last Run

Current Status
```

Examples:

```text
Idle

Running

Completed

Failed
```

---

# SECTION 4

# Embedding

Purpose:

Manage indexing.

---

## Main Button

```text
Run Embedding
```

Action:

```text
POST /api/admin/embedding
```

---

## Rebuild Button

```text
Rebuild Everything
```

Action:

```text
POST /api/admin/rebuild
```

---

## Status Area

Displays:

```text
Embedded Count

Pending Count

Last Embedding
```

---

# SECTION 5

# Chat Test

Purpose:

Test AI responses.

---

## Question Input

Type:

```text
Textarea
```

Placeholder:

```text
Type your question in Arabic...
```

---

## Ask Button

```text
Ask
```

Action:

```text
POST /api/admin/chat-test
```

---

## Loading State

Display:

```text
Thinking...
```

---

## Result Card

Contains:

```text
AI Response
```

---

## Sources Card

Contains:

```text
Source Title

Source URL
```

---

# SECTION 6

# Logs

Purpose:

Display system activity.

---

## Refresh Button

```text
↻ Refresh
```

---

## Logs Table

Columns:

```text
Timestamp

Event
```

---

## Example

```text
2026-06-14 10:00

embedding_started

Embedding execution started
```

---

# SECTION 7

# Health

Purpose:

Display system health.

---

## Health Cards

Card Layout:

```text
API

Database

Qdrant

Groq
```

---

## Status Values

```text
Online
Offline
```

---

## Indicators

```text
🟢 Online

🔴 Offline
```

---

# Global Components

---

# Loading Spinner

Used During:

```text
Stats

Scraping

Embedding

Chat
```

---

# Toast Notifications

Success:

```text
Operation completed successfully
```

---

Error:

```text
Operation failed
```

---

# Empty State

Used When:

```text
No Knowledge

No Logs

No Questions
```

Example:

```text
No data available
```

---

# API Mapping

Overview

```text
GET /api/admin/stats
```

---

Knowledge

```text
GET /api/admin/knowledge

GET /api/admin/knowledge/{id}

DELETE /api/admin/knowledge/{id}
```

---

Scraper

```text
POST /api/admin/scrape
```

---

Embedding

```text
POST /api/admin/embedding

POST /api/admin/rebuild
```

---

Chat Test

```text
POST /api/admin/chat-test
```

---

Logs

```text
GET /api/admin/logs
```

---

Health

```text
GET /api/admin/health
```

---

# UI Complexity Budget

Maximum Tabs:

```text
7
```

Maximum Sidebar Items:

```text
7
```

Maximum Clicks To Any Action:

```text
2
```

Maximum Learning Time:

```text
5 Minutes
```

---

# Final UI Statement

The dashboard must feel like a lightweight control panel.

A client should be able to:

* Check status
* Run scraping
* Run embedding
* Test the chatbot
* Review knowledge
* Delete outdated content

Without reading documentation or requiring technical knowledge.
