# dashboard/docs/SCOPE.md

# Dashboard Scope Definition

Version: 1.0

Status: Approved

---

# Purpose

This document defines exactly what the Dashboard V1 is and what it is not.

The goal is to prevent scope creep and keep the dashboard aligned with the project's purpose.

This dashboard is a lightweight administration panel for managing a RAG project.

It is not a SaaS platform.

It is not an enterprise product.

It is not a multi-user management system.

It is not a standalone business product.

---

# Project Goal

The dashboard exists for one reason:

> Allow a non-technical client to operate and maintain a RAG project without requiring the developer.

The dashboard should make common operations accessible through buttons and simple forms.

---

# Target Audience

Single Client

Examples:

* Clinic Owner
* Business Owner
* Store Owner
* Freelancer Client
* Internal Team Representative

Technical Knowledge:

Low

Expected Skills:

* Upload files
* Click buttons
* Read reports

No technical knowledge should be required.

---

# Dashboard Philosophy

The dashboard is a control panel.

The dashboard is NOT a development tool.

Clients should never see:

* Embeddings
* Chunk Size
* Vector Search Settings
* AI Parameters
* Prompt Engineering
* Model Configuration
* Qdrant Configuration
* Database Configuration

The system should hide implementation details.

---

# Supported RAG Types

The dashboard must remain generic.

It must not be designed specifically for article-based RAG.

Supported examples:

* Article RAG
* Product Catalog RAG
* FAQ RAG
* Company Documentation RAG
* Internal Knowledge Base RAG

All content is treated as knowledge.

---

# Frontend Scope

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
* Inline CSS only
* Inline JavaScript only
* No React
* No Next.js
* No Build Step
* No Tailwind
* No External Framework Dependency

The dashboard must be deployable by simply opening or serving index.html.

---

# Backend Scope

Backend Technology:

```text
FastAPI
```

Purpose:

* Expose admin endpoints
* Read project status
* Trigger project actions
* Return analytics

The backend must reuse the existing RAG project.

The backend must not introduce a new architecture.

---

# Existing System Reuse

The dashboard must build on top of:

* Existing FastAPI API
* Existing MySQL Database
* Existing Qdrant Collection
* Existing Embedding Pipeline
* Existing Scraper
* Existing Chat System

The dashboard is an extension layer.

Not a rewrite.

---

# Features Included

## Overview

Display:

* Total Knowledge Entries
* Embedded Entries
* Non Embedded Entries
* Questions Count
* Last Sync Time
* System Status

---

## Knowledge View

Display:

* Existing Knowledge
* Titles
* URLs
* Status

Actions:

* View
* Delete

---

## Scraper Controls

Actions:

* Run Scraper
* View Scraper Status

---

## Embedding Controls

Actions:

* Run Embedding
* Rebuild Embeddings

---

## Chat Testing

Actions:

* Ask Question
* View AI Response

Purpose:

Allow clients to verify system behavior.

---

## Logs

Display:

* Recent Operations
* Pipeline Activity

Examples:

* Scraper Started
* Scraper Finished
* Embedding Started
* Embedding Completed

---

## Health Check

Display:

* API Status
* Database Status
* Qdrant Status
* AI Provider Status

---

# Features Explicitly Excluded

The following are OUT OF SCOPE.

---

## Multi User System

Excluded.

Only one admin user.

---

## Team Management

Excluded.

---

## Roles & Permissions

Excluded.

---

## Multi Tenant

Excluded.

---

## Multiple Workspaces

Excluded.

---

## Multiple Knowledge Bases

Excluded.

---

## Prompt Editor

Excluded.

---

## AI Configuration

Excluded.

No:

* Temperature
* Top-K
* Context Length
* Model Selection

---

## Qdrant Management

Excluded.

Clients should never interact with vector databases.

---

## Database Management

Excluded.

Clients should never interact with database structures.

---

## Analytics Platform

Excluded.

Only basic metrics.

---

## Conversation History

Excluded.

---

## Feedback System

Excluded.

---

## User Tracking

Excluded.

---

## Audit Logs

Excluded.

---

## Notifications

Excluded.

---

## Email System

Excluded.

---

## File Manager

Excluded.

Files exist only as uploaded knowledge.

---

# V1 Endpoints Budget

The dashboard should remain small.

Target:

Maximum 10 admin endpoints.

Examples:

```text
GET  /admin/stats

GET  /admin/knowledge

POST /admin/scrape

POST /admin/embed

POST /admin/rebuild

POST /admin/chat-test

GET  /admin/logs

GET  /admin/health
```

Avoid endpoint explosion.

---

# UI Complexity Budget

Maximum Tabs:

```text
Overview
Knowledge
Scraper
Embedding
Chat Test
Logs
Health
```

No nested dashboards.

No complex navigation.

No routing system.

No SPA framework.

---

# Database Scope

The dashboard should add the minimum number of tables required.

Avoid redesigning the entire project.

Prefer extending existing tables whenever possible.

---

# Success Criteria

The dashboard is successful if a client can:

* Verify system health
* Run scraping
* Run embedding
* Test the chatbot
* Review knowledge
* Delete outdated knowledge

Without contacting the developer.

---

# Failure Criteria

The dashboard has failed if:

* It requires React or Next.js
* It introduces unnecessary infrastructure
* It becomes a SaaS platform
* It requires technical knowledge
* It exceeds the needs of a portfolio project
* It takes longer to manage than using the API directly

---

# Final Scope Statement

This dashboard is a lightweight operational control panel for a single RAG project.

It exists to expose common maintenance actions through a simple interface while hiding all technical complexity.

Nothing more.
