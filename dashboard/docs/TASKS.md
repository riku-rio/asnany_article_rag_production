# dashboard/docs/TASKS.md

# Dashboard Implementation Tasks

Version: 1.0

Status: Approved

---

# Purpose

This document defines the implementation plan for Dashboard V1.

The goal is to transform the existing RAG project into a client-operable system without introducing unnecessary complexity.

The dashboard must:

* Reuse existing infrastructure.
* Reuse existing FastAPI application.
* Reuse existing MySQL database.
* Reuse existing RAG pipeline.
* Remain lightweight.

---

# Task Status Legend

```text
[] Not Started
[-] In Progress
[x] Completed
[!] Blocked
```

---

# Task ID Convention

```text
DG = Dashboard Generic
```

Format:

```text
DG-MAT
```

Where:

```text
M = Milestone Number
A = Atomic Milestone Number
T = Task Number
```

Example:

```text
DG-111

Milestone 1
Atomic Milestone 1
Task 1
```

---

# Milestone Map

```text
M0 Project Preparation

M1 Database & Logging

M2 Admin API Foundation

M3 Dashboard Shell & Navigation

M4 Knowledge Management

M5 Scraper & Embedding Controls

M6 Chat Test & Health

M7 Testing & Release
```

---

# ==================================================

# MILESTONE 0

# PROJECT PREPARATION

# ==================================================

# Milestone Goal

Prepare the existing project for dashboard integration without breaking the current RAG workflow.

---

# Atomic Milestone 0.1

## Atomic Milestone Goal

Create dashboard workspace structure.

---

### Atomic Tasks

#### DG-011

Create dashboard directory.

```text
dashboard/
```

---

#### DG-012

Create docs directory.

```text
dashboard/docs/
```

---

#### DG-013

Create dashboard entry file.

```text
dashboard/index.html
```

---

#### DG-014

Verify dashboard files are not imported into Python runtime.

---

#### DG-015

Verify dashboard remains standalone.

---

# Atomic Milestone 0.2

## Atomic Milestone Goal

Audit existing backend capabilities.

---

### Atomic Tasks

#### DG-021

Identify existing FastAPI routes.

---

#### DG-022

Document existing chat endpoint.

---

#### DG-023

Document existing embedding endpoint.

---

#### DG-024

Document existing health endpoint.

---

#### DG-025

Verify endpoint responses.

---

#### DG-026

Identify reusable services.

Examples:

```text
Scraper

Embedding

Chat

Health
```

---

# Atomic Milestone 0.3

## Atomic Milestone Goal

Audit database.

---

### Atomic Tasks

#### DG-031

Inspect blog table structure.

---

#### DG-032

Document available fields.

---

#### DG-033

Verify is_embedded field.

---

#### DG-034

Verify article count query.

---

#### DG-035

Verify delete workflow.

---

# Milestone 0 DoD

Milestone 0 is complete when:

* [x] dashboard directory exists
* [x] index.html exists
* [x] Existing endpoints documented
* [x] Existing database documented
* [x] Reusable services identified

---

# ==================================================

# MILESTONE 1

# DATABASE & LOGGING

# ==================================================

# Milestone Goal

Create minimum database additions required by the dashboard.

---

# Atomic Milestone 1.1

## Atomic Milestone Goal

Create dashboard_logs table.

---

### Atomic Tasks

#### DG-111

Create migration script.

---

#### DG-112

Create dashboard_logs table.

Fields:

```text
id
event_type
message
created_at
```

---

#### DG-113

Add created_at index.

---

#### DG-114

Run migration locally.

---

#### DG-115

Verify table creation.

---

# Atomic Milestone 1.2

## Atomic Milestone Goal

Create chat_logs table.

---

### Atomic Tasks

#### DG-121

Create migration script.

---

#### DG-122

Create chat_logs table.

Fields:

```text
id
question
answer
response_time_ms
sources_count
created_at
```

---

#### DG-123

Add created_at index.

---

#### DG-124

Run migration locally.

---

#### DG-125

Verify inserts.

---

# Atomic Milestone 1.3

## Atomic Milestone Goal

Create logging helpers.

---

### Atomic Tasks

#### DG-131

Create dashboard logger module.

---

#### DG-132

Create log_event function.

---

#### DG-133

Add scraper event logging.

---

#### DG-134

Add embedding event logging.

---

#### DG-135

Add delete event logging.

---

#### DG-136

Add error event logging.

---

# Milestone 1 DoD

Milestone 1 is complete when:

* [x] dashboard_logs exists
* [x] chat_logs exists
* [x] logging helper exists
* [x] scraper logs events
* [x] embedding logs events

---

# ==================================================

# MILESTONE 2

# ADMIN API FOUNDATION

# ==================================================

# Milestone Goal

Create all dashboard endpoints required by V1.

---

# Atomic Milestone 2.1

## Atomic Milestone Goal

Create admin router.

---

### Atomic Tasks

#### DG-211

Create admin router module.

---

#### DG-212

Register router.

---

#### DG-213

Add route prefix.

```text
/api/admin
```

---

#### DG-214

Verify router registration.

---

# Atomic Milestone 2.2

## Atomic Milestone Goal

Implement stats endpoint.

---

### Atomic Tasks

#### DG-221

Create stats service.

---

#### DG-222

Implement total knowledge query.

---

#### DG-223

Implement embedded knowledge query.

---

#### DG-224

Implement pending knowledge query.

---

#### DG-225

Implement questions count query.

---

#### DG-226

Create:

```http
GET /api/admin/stats
```

---

#### DG-227

Verify JSON response.

---

# Atomic Milestone 2.3

## Atomic Milestone Goal

Implement knowledge endpoints.

---

### Atomic Tasks

#### DG-231

Create knowledge service.

---

#### DG-232

Create knowledge listing query.

---

#### DG-233

Create knowledge details query.

---

#### DG-234

Create delete knowledge query.

---

#### DG-235

Implement:

```http
GET /api/admin/knowledge
```

---

#### DG-236

Implement:

```http
GET /api/admin/knowledge/{id}
```

---

#### DG-237

Implement:

```http
DELETE /api/admin/knowledge/{id}
```

---

#### DG-238

Verify delete behavior.

---

# Atomic Milestone 2.4

## Atomic Milestone Goal

Implement logs endpoint.

---

### Atomic Tasks

#### DG-241

Create logs query.

---

#### DG-242

Implement:

```http
GET /api/admin/logs
```

---

#### DG-243

Sort by newest first.

---

#### DG-244

Limit results.

```text
50
```

---

#### DG-245

Verify response.

---

# Atomic Milestone 2.5

## Atomic Milestone Goal

Implement health endpoint.

---

### Atomic Tasks

#### DG-251

Create health service.

---

#### DG-252

Check FastAPI status.

---

#### DG-253

Check MySQL connection.

---

#### DG-254

Check Qdrant connection.

---

#### DG-255

Check Groq availability.

---

#### DG-256

Implement:

```http
GET /api/admin/health
```

---

#### DG-257

Verify response.

---

# Milestone 2 DoD

Milestone 2 is complete when:

* [x] Admin router exists
* [x] Stats endpoint works
* [x] Knowledge endpoints work
* [x] Logs endpoint works
* [x] Health endpoint works
* [x] API.md matches implementation

---

# ==================================================

# MILESTONE 3

# DASHBOARD SHELL & NAVIGATION

# ==================================================

# Milestone Goal

Create the complete dashboard user interface shell using a single HTML file.

---

# Atomic Milestone 3.1

## Atomic Milestone Goal

Create page structure.

---

### Atomic Tasks

#### DG-311

Create HTML skeleton.

---

#### DG-312

Create header section.

---

#### DG-313

Create sidebar section.

---

#### DG-314

Create content section.

---

#### DG-315

Verify layout rendering.

---

# Atomic Milestone 3.2

## Atomic Milestone Goal

Create navigation system.

---

### Atomic Tasks

#### DG-321

Create Overview tab.

---

#### DG-322

Create Knowledge tab.

---

#### DG-323

Create Scraper tab.

---

#### DG-324

Create Embedding tab.

---

#### DG-325

Create Chat Test tab.

---

#### DG-326

Create Logs tab.

---

#### DG-327

Create Health tab.

---

#### DG-328

Implement tab switching.

---

#### DG-329

Hide inactive sections.

---

# Atomic Milestone 3.3

## Atomic Milestone Goal

Create reusable UI utilities.

---

### Atomic Tasks

#### DG-331

Create loading spinner.

---

#### DG-332

Create success toast.

---

#### DG-333

Create error toast.

---

#### DG-334

Create modal component.

---

#### DG-335

Create badge component.

---

#### DG-336

Create empty-state component.

---

# Atomic Milestone 3.4

## Atomic Milestone Goal

Implement System, Light, and Dark theme modes with persistence.

---

### Atomic Tasks

#### DG-341

Refactor CSS to use custom properties (CSS variables).

Replace all hardcoded colors with `var(--token)` references.

---

#### DG-342

Define dark palette CSS variables.

Tokens:

```text
--bg-body:       #0f0f1a
--bg-surface:    #1a1a2e
--bg-sidebar:    #16162a
--bg-sidebar-active: #25254a
--bg-sidebar-hover:  #1e1e38
--bg-card:       #1a1a2e
--border-color:  #2a2a44
--text-primary:  #e8e8f0
--text-heading:  #f0f0ff
--text-secondary:#8888aa
--text-sidebar:  #6666aa
--color-accent:  #8b9dff
```

---

#### DG-343

Add theme toggle button to `.header`.

Cycle order: System → Light → Dark → System.

Icons:

```text
System: 🖥
Light:  ☀️
Dark:   🌙
```

---

#### DG-344

Implement theme switching logic.

Apply `theme-light` or `theme-dark` class on `<html>`.

---

#### DG-345

Add system preference listener.

Watch `matchMedia('(prefers-color-scheme: dark)')` — apply dark when matches, light otherwise. Re-evaluate on change event when mode is `system`.

---

#### DG-346

Add localStorage persistence.

```text
localStorage.setItem('theme', mode)
```

Default to `'system'` when no saved preference exists.

---

#### DG-347

Verify theme persists across page reloads.

---

# Milestone 3 DoD

Milestone 3 is complete when:

* [x] Single index.html exists
* [x] Sidebar works
* [x] Tab switching works
* [x] All sections render
* [x] No external UI framework is required
* [x] Dashboard works from one HTML file
* [x] Theme toggle appears in header
* [x] System mode respects OS preference
* [x] Light mode forces light palette
* [x] Dark mode forces dark palette
* [x] Preference persists across reloads

---

# ==================================================

# MILESTONE 4

# KNOWLEDGE MANAGEMENT

# ==================================================

# Milestone Goal

Allow the client to browse, inspect, and delete knowledge entries from the dashboard.

---

# Atomic Milestone 4.1

## Atomic Milestone Goal

Build Knowledge section UI.

---

### Atomic Tasks

#### DG-411

Create Knowledge section container.

---

#### DG-412

Create search input.

Placeholder:

```text
Search knowledge...
```

---

#### DG-413

Create table container.

---

#### DG-414

Create table header.

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

#### DG-415

Create empty state.

---

# Atomic Milestone 4.2

## Atomic Milestone Goal

Connect knowledge listing endpoint.

---

### Atomic Tasks

#### DG-421

Create fetchKnowledge() function.

---

#### DG-422

Call:

```http
GET /api/admin/knowledge
```

---

#### DG-423

Render table rows.

---

#### DG-424

Render embedded badge.

Values:

```text
Embedded
Pending
```

---

#### DG-425

Handle empty response.

---

#### DG-426

Handle API errors.

---

# Atomic Milestone 4.3

## Atomic Milestone Goal

Implement knowledge details view.

---

### Atomic Tasks

#### DG-431

Create View button.

---

#### DG-432

Create details modal.

---

#### DG-433

Load knowledge details.

---

#### DG-434

Call:

```http
GET /api/admin/knowledge/{id}
```

---

#### DG-435

Render title.

---

#### DG-436

Render URL.

---

#### DG-437

Render content preview.

---

#### DG-438

Verify long content scrolling.

---

# Atomic Milestone 4.4

## Atomic Milestone Goal

Implement delete workflow.

---

### Atomic Tasks

#### DG-441

Create Delete button.

---

#### DG-442

Create confirmation modal.

---

#### DG-443

Create delete request.

---

#### DG-444

Call:

```http
DELETE /api/admin/knowledge/{id}
```

---

#### DG-445

Refresh table after deletion.

---

#### DG-446

Display success notification.

---

#### DG-447

Display failure notification.

---

#### DG-448

Verify deleted item disappears.

---

# Milestone 4 DoD

Milestone 4 is complete when:

* [] Knowledge list loads
* [] Knowledge search works
* [] View modal works
* [] Delete workflow works
* [] UI refreshes correctly
* [] Errors are handled

---

# ==================================================

# MILESTONE 5

# SCRAPER & EMBEDDING CONTROLS

# ==================================================

# Milestone Goal

Allow the client to run maintenance operations without developer assistance.

---

# Atomic Milestone 5.1

## Atomic Milestone Goal

Build Scraper section.

---

### Atomic Tasks

#### DG-511

Create Scraper section container.

---

#### DG-512

Create scraper status card.

---

#### DG-513

Create Run Scraper button.

---

#### DG-514

Create last execution area.

---

#### DG-515

Create operation feedback area.

---

# Atomic Milestone 5.2

## Atomic Milestone Goal

Connect scraper endpoint.

---

### Atomic Tasks

#### DG-521

Create runScraper() function.

---

#### DG-522

Call:

```http
POST /api/admin/scrape
```

---

#### DG-523

Disable button during request.

---

#### DG-524

Display loading state.

---

#### DG-525

Display success toast.

---

#### DG-526

Display error toast.

---

#### DG-527

Refresh logs after execution.

---

# Atomic Milestone 5.3

## Atomic Milestone Goal

Build Embedding section.

---

### Atomic Tasks

#### DG-531

Create Embedding section container.

---

#### DG-532

Create Run Embedding button.

---

#### DG-533

Create Rebuild Everything button.

---

#### DG-534

Create status cards.

---

#### DG-535

Create last execution display.

---

# Atomic Milestone 5.4

## Atomic Milestone Goal

Connect embedding endpoints.

---

### Atomic Tasks

#### DG-541

Create runEmbedding() function.

---

#### DG-542

Call:

```http
POST /run-embedding
```

---

#### DG-543

Create rebuildEverything() function.

---

#### DG-544

Call:

```http
POST /api/admin/rebuild
```

---

#### DG-545

Add confirmation dialog.

---

#### DG-546

Show loading state.

---

#### DG-547

Show success notification.

---

#### DG-548

Show failure notification.

---

#### DG-549

Refresh dashboard stats.

---

# Milestone 5 DoD

Milestone 5 is complete when:

* [] Scraper can be triggered
* [] Embedding can be triggered
* [] Rebuild can be triggered
* [] Loading states work
* [] Success states work
* [] Failure states work

---

# ==================================================

# MILESTONE 6

# CHAT TEST & HEALTH

# ==================================================

# Milestone Goal

Allow clients to validate AI behavior and verify system health.

---

# Atomic Milestone 6.1

## Atomic Milestone Goal

Build Chat Test UI.

---

### Atomic Tasks

#### DG-611

Create Chat Test section.

---

#### DG-612

Create textarea input.

---

#### DG-613

Create Ask button.

---

#### DG-614

Create response card.

---

#### DG-615

Create sources card.

---

#### DG-616

Create loading indicator.

---

# Atomic Milestone 6.2

## Atomic Milestone Goal

Connect Chat Test endpoint.

---

### Atomic Tasks

#### DG-621

Create askQuestion() function.

---

#### DG-622

Call:

```http
POST /api/admin/chat-test
```

---

#### DG-623

Display AI response.

---

#### DG-624

Display source list.

---

#### DG-625

Display empty sources state.

---

#### DG-626

Handle API errors.

---

#### DG-627

Verify long responses.

---

# Atomic Milestone 6.3

## Atomic Milestone Goal

Build Health section.

---

### Atomic Tasks

#### DG-631

Create Health section.

---

#### DG-632

Create API card.

---

#### DG-633

Create Database card.

---

#### DG-634

Create Qdrant card.

---

#### DG-635

Create Groq card.

---

#### DG-636

Create refresh button.

---

# Atomic Milestone 6.4

## Atomic Milestone Goal

Connect health endpoint.

---

### Atomic Tasks

#### DG-641

Create fetchHealth() function.

---

#### DG-642

Call:

```http
GET /api/admin/health
```

---

#### DG-643

Render API status.

---

#### DG-644

Render Database status.

---

#### DG-645

Render Qdrant status.

---

#### DG-646

Render Groq status.

---

#### DG-647

Display online indicator.

---

#### DG-648

Display offline indicator.

---

# Milestone 6 DoD

Milestone 6 is complete when:

* [] Chat Test works
* [] AI response displays
* [] Sources display
* [] Health section loads
* [] All status cards render
* [] Refresh works

---

# ==================================================

# MILESTONE 7

# TESTING & RELEASE

# ==================================================

# Milestone Goal

Validate Dashboard V1 and prepare it for client use.

---

# Atomic Milestone 7.1

## Atomic Milestone Goal

Validate API integration.

---

### Atomic Tasks

#### DG-711

Test stats endpoint.

---

#### DG-712

Test knowledge endpoint.

---

#### DG-713

Test delete endpoint.

---

#### DG-714

Test logs endpoint.

---

#### DG-715

Test scraper endpoint.

---

#### DG-716

Test embedding endpoint.

---

#### DG-717

Test rebuild endpoint.

---

#### DG-718

Test health endpoint.

---

#### DG-719

Test chat endpoint.

---

# Atomic Milestone 7.2

## Atomic Milestone Goal

Validate UI flows.

---

### Atomic Tasks

#### DG-721

Test navigation.

---

#### DG-722

Test modal behavior.

---

#### DG-723

Test notifications.

---

#### DG-724

Test loading states.

---

#### DG-725

Test empty states.

---

#### DG-726

Test error states.

---

# Atomic Milestone 7.3

## Atomic Milestone Goal

Validate dashboard operations.

---

### Atomic Tasks

#### DG-731

Run scraper from dashboard.

---

#### DG-732

Run embedding from dashboard.

---

#### DG-733

Run rebuild from dashboard.

---

#### DG-734

Open knowledge item.

---

#### DG-735

Delete knowledge item.

---

#### DG-736

Run chat test.

---

#### DG-737

Verify logs update.

---

#### DG-738

Verify stats update.

---

# Atomic Milestone 7.4

## Atomic Milestone Goal

Prepare release.

---

### Atomic Tasks

#### DG-741

Remove unused code.

---

#### DG-742

Remove debug logs.

---

#### DG-743

Review API.md compliance.

---

#### DG-744

Review UI.md compliance.

---

#### DG-745

Review DB_SCHEMA.md compliance.

---

#### DG-746

Verify single-file requirement.

---

#### DG-747

Create backup before release.

---

# Milestone 7 DoD

Milestone 7 is complete when:

* [] All endpoints tested
* [] All UI flows tested
* [] All operations validated
* [] Documentation matches implementation
* [] Dashboard ready for client usage

---

# ==================================================

# DASHBOARD V1 COMPLETION DOD

# ==================================================

Dashboard V1 is complete when:

* [] dashboard/index.html exists
* [] Dashboard works from a single HTML file
* [] No frontend framework is used
* [] Overview section works
* [] Knowledge section works
* [] Scraper section works
* [] Embedding section works
* [] Chat Test section works
* [] Logs section works
* [] Health section works
* [] Existing RAG pipeline still works
* [] Existing chat endpoint still works
* [] Existing embedding endpoint still works
* [] Existing health endpoint still works
* [] Database migrations completed
* [] dashboard_logs records events
* [] chat_logs records interactions
* [] No breaking changes introduced

---

# ANTI-SCOPE VALIDATION CHECKLIST

Before adding any feature, verify:

* [] Does this help the client operate the RAG?
* [] Does this avoid developer intervention?
* [] Does this fit Dashboard V1?
* [] Does this avoid new infrastructure?
* [] Does this avoid frontend frameworks?
* [] Does this avoid unnecessary complexity?

If any answer is NO:

```text
Move feature to V2.
```

---

# PRODUCTION READINESS CHECKLIST

* [] API endpoints respond correctly
* [] Dashboard loads without errors
* [] MySQL connection works
* [] Qdrant connection works
* [] Groq connection works
* [] Scraper execution works
* [] Embedding execution works
* [] Chat responses work
* [] Health checks work
* [] Logs are generated
* [] Stats are accurate
* [] Client can operate system independently

---

# Final Statement

Dashboard V1 is intentionally small.

Its purpose is not to become a platform.

Its purpose is to expose the most important operational actions of the RAG system through a simple interface that any client can use without technical knowledge.
