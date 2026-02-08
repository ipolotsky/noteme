# Noteme Bot — Implementation Plan

## Context

Building a Telegram bot for storing important dates, discovering "beautiful date milestones" (e.g., "1000 days since wedding"), managing notes/wishes tied to people via tags, with voice control, daily notifications, and shareable web pages. Two languages: Russian and English with proper declensions.

The project is greenfield (empty directory). All code, infrastructure, and CI/CD to be built from scratch.

**Tech stack:**
- **Python 3.12+**
- **Telegram**: aiogram 3.x (async)
- **Web**: FastAPI + Uvicorn
- **Database**: PostgreSQL 16 + SQLAlchemy 2.0 (async, asyncpg driver) + Alembic (migrations)
- **Cache/Queue**: Redis 7 + arq (background tasks)
- **AI**: LangGraph (langchain) + OpenAI gpt-4o-mini + Whisper API
- **Admin**: sqladmin + Flowbite CSS (flowbite.com) for styling
- **Sharing pages**: Jinja2 templates + Flowbite CSS
- **Declensions**: pymorphy3 (RU), inflect (EN)
- **Infrastructure**: Docker + Docker Compose, Traefik v3 (prod)
- **Monitoring**: Prometheus + Grafana + Sentry
- **CI/CD**: GitHub Actions

**Key decisions:**
- Name: **Noteme** (replaces "DateMate" from spec)
- Package manager: **uv**
- AI: **LangGraph from the start** (not incremental migration)
- i18n: **JSON files + custom lightweight loader** — all user-facing text in `app/i18n/ru.json` and `app/i18n/en.json`
- IDs: **UUID** for all entity primary keys (except users table which uses Telegram user_id as BIGINT PK)
- UI framework: **Flowbite** (flowbite.com) via `flowbite-mcp` MCP server — for admin panel and sharing web pages
- Dev ports: **Non-standard** (5433 for PostgreSQL, 6380 for Redis, 8001 for app) to avoid conflicts with other local projects. Standard ports in production.
- Limits: `max_events`, `max_notes`, `max_tags_per_entity` — **architectural only** for now (future monetization). Enforce in services but no payment/subscription logic.

---

## Dev Port Mapping

| Service | Dev Port (host) | Container Port | Prod Port |
|---------|----------------|---------------|-----------|
| PostgreSQL | **5433** | 5432 | 5432 (internal only) |
| Redis | **6380** | 6379 | 6379 (internal only) |
| FastAPI (app) | **8001** | 8000 | 443 (via Traefik) |
| Traefik dashboard | — | — | 8080 |
| Prometheus | **9091** | 9090 | 9090 (internal) |
| Grafana | **3001** | 3000 | 3000 (via Traefik) |

---

## Phase 1: Project Scaffolding

**Goal:** Runnable skeleton — `uv run python -m app` starts, Docker Compose brings up PostgreSQL + Redis on non-standard ports, Alembic initialized, health endpoint responds.

### Tasks

| # | Task | Files |
|---|------|-------|
| 1.1 | Init uv project, configure pyproject.toml with all deps | `pyproject.toml`, `.python-version` |
| 1.2 | Create full package structure (all `__init__.py`) | `app/`, `app/models/`, `app/schemas/`, `app/services/`, `app/agents/`, `app/handlers/`, `app/keyboards/`, `app/middlewares/`, `app/api/`, `app/admin/`, `app/workers/`, `app/utils/`, `app/templates/`, `app/i18n/`, `app/static/`, `tests/` |
| 1.3 | Pydantic-settings config with env validation | `app/config.py` |
| 1.4 | `.env.template` with all required env vars for user to fill in | `.env.template` |
| 1.5 | Async SQLAlchemy 2.0 engine + session factory (PostgreSQL + asyncpg) | `app/database.py` |
| 1.6 | Alembic init with async PostgreSQL template | `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako` |
| 1.7 | FastAPI app with health endpoint | `app/main.py`, `app/api/health.py` |
| 1.8 | Aiogram bot skeleton (Dispatcher + Bot, no handlers) | `app/bot.py` |
| 1.9 | Entry point running both FastAPI and bot | `app/__main__.py` |
| 1.10 | Dockerfile (multi-stage, uv-based) | `Dockerfile` |
| 1.11 | docker-compose.yml (dev: non-standard ports) | `docker-compose.yml` |
| 1.12 | docker-compose.prod.yml (standard ports + Traefik) | `docker-compose.prod.yml`, `traefik/traefik.yml` |
| 1.13 | .gitignore, .dockerignore | `.gitignore`, `.dockerignore` |
| 1.14 | Linting config (ruff) | `ruff.toml` |
| 1.15 | Init git repo | `git init` |

### Verify
- `docker compose up -d db redis` → PostgreSQL on :5433, Redis on :6380
- `uv run alembic upgrade head` → connects to PostgreSQL, succeeds
- `curl localhost:8001/health` → `{"status": "ok"}`
- Bot starts polling (visible in logs)

---

## Phase 2: Data Models + Migrations

**Goal:** All DB tables exist with UUID primary keys, relationships defined, seed data for 16 strategies loaded.

**Depends on:** Phase 1

### Tables (all entity IDs are UUID, except users.id = BIGINT from Telegram)

| Table | Key fields |
|-------|-----------|
| **users** | id (BIGINT PK = TG user_id), username, first_name, language, timezone, notification_time, notifications_enabled, notification_count, max_events (default 10), max_notes (default 10), max_tags_per_entity (default 3), spoiler_enabled, onboarding_completed, is_active, shared_with (JSONB) |
| **tags** | id (**UUID** PK), user_id FK, name, created_at. UNIQUE(user_id, name) |
| **events** | id (**UUID** PK), user_id FK, title, event_date (DATE), description, is_system, created_at, updated_at |
| **event_tags** | event_id (UUID FK), tag_id (UUID FK). Composite PK |
| **notes** | id (**UUID** PK), user_id FK, text, reminder_date, reminder_sent, created_at, updated_at |
| **note_tags** | note_id (UUID FK), tag_id (UUID FK). Composite PK |
| **media_links** | id (**UUID** PK), note_id FK (UNIQUE), chat_id, message_id, media_type, is_deleted |
| **beautiful_date_strategies** | id (**UUID** PK), name_ru, name_en, strategy_type, params (JSONB), is_active, priority |
| **beautiful_dates** | id (**UUID** PK), event_id FK (CASCADE), target_date, strategy_id FK, label_ru, label_en, interval_value, interval_unit, compound_parts (JSONB), share_uuid (UUID UNIQUE NULL). Indexes on (event_id, target_date) and (target_date) |
| **notification_log** | id (**UUID** PK), user_id FK, beautiful_date_id FK NULL, note_id FK NULL, sent_at, notification_type |

### Verify
- `uv run alembic upgrade head` creates all tables with UUID PKs
- Seed script populates 16 strategies
- `alembic downgrade base && alembic upgrade head` works cleanly

---

## Phase 3: i18n + Declensions + Core Services

**Goal:** Business logic layer works independently. All CRUD tested via direct service calls. i18n functional with proper Russian declensions. All user-facing text in JSON files.

**Depends on:** Phase 2

### Verify
- `uv run pytest tests/test_services/ -v` — all pass
- `t('welcome', 'ru', name='Илья')` returns proper Russian
- Declension: `decline_ru(1000, 'day')` → "1000 дней"
- Creating 11th event when max_events=10 → error

---

## Phase 4: Telegram Bot Handlers (Button Navigation)

**Goal:** Bot fully navigable via inline keyboards. CRUD for events/notes/tags through buttons. Settings, onboarding. Zero AI calls.

**Depends on:** Phase 3

---

## Phase 5: AI Agents (LangGraph)

**Goal:** Text and voice messages processed by LangGraph agent graph. Natural language creates events, notes, queries data. Voice transcribed by Whisper.

**Depends on:** Phase 4, Phase 3

---

## Phase 6: Beautiful Dates Calculation Engine

**Goal:** Calculate all beautiful milestones for events, store in DB, display feed.

**Depends on:** Phase 3 (can run in parallel with Phase 4)

---

## Phase 7: Notifications System

**Goal:** Daily morning digests + note reminders sent via background worker.

**Depends on:** Phase 6, Phase 4

---

## Phase 8: Sharing Web Pages

**Goal:** Shareable links for beautiful dates with pretty web pages (Flowbite CSS) and OG meta tags.

**Depends on:** Phase 6, Phase 1 (FastAPI)

---

## Phase 9: Admin Panel

**Goal:** Web admin for managing all entities, strategies, user settings. Styled with Flowbite.

**Depends on:** Phase 2

---

## Phase 10: Monitoring + CI/CD

**Goal:** Production observability and automated pipeline.

**Depends on:** All previous phases

---

## Phase 11: Testing + Polish

**Goal:** >80% coverage, edge cases handled, performance optimized.

**Depends on:** All previous phases

---

## Phase Dependency Graph

```
Phase 1 (Scaffolding)
  └→ Phase 2 (Models)
      └→ Phase 3 (i18n + Services)
          ├→ Phase 4 (Bot Handlers) ──→ Phase 5 (AI Agents)
          │                                    │
          └→ Phase 6 (Beautiful Dates) ←───────┘
              ├→ Phase 7 (Notifications)
              └→ Phase 8 (Sharing)
          └→ Phase 9 (Admin)
              └→ Phase 10 (Monitoring + CI/CD)
                  └→ Phase 11 (Testing + Polish)
```

**Critical path:** 1 → 2 → 3 → 4 → 5 (AI is highest risk/complexity)
**Parallel tracks:** After Phase 3, Phases 4 and 6 can run simultaneously. Phase 9 can start after Phase 2.
