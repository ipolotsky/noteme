# Noteme

[![CI/CD](https://github.com/ipolotsky/noteme/actions/workflows/ci.yml/badge.svg)](https://github.com/ipolotsky/noteme/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-proprietary-red.svg)](#license)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)](https://t.me/remark_right_now_bot)

Telegram bot for tracking important dates, discovering beautiful date milestones, and managing personal notes with smart tagging.

Built with **aiogram 3** + **FastAPI** + **LangGraph AI agents**.

## Features

- **Events & dates** — save important dates (birthdays, anniversaries, etc.) via text or voice
- **Beautiful date milestones** — automatic discovery of mathematically interesting milestones for your events (palindromes, round numbers, powers of two, sequences, and more)
- **Smart notes** — create notes with AI-powered tag extraction (person names prioritized)
- **Voice input** — full voice message support via OpenAI Whisper
- **Daily digest** — morning notifications with upcoming beautiful dates and related notes
- **Spoiler mode** — hide notification content behind spoiler tags
- **Media notes** — save photos, videos, video notes, and documents as tagged notes
- **Sharing** — generate public links for beautiful date milestones
- **Admin panel** — sqladmin-based interface with session authentication
- **Bilingual** — full Russian and English support

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Bot framework | [aiogram 3.x](https://docs.aiogram.dev/) |
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) |
| AI agents | [LangGraph](https://langchain-ai.github.io/langgraph/) + OpenAI (gpt-4o-mini, Whisper) |
| Database | PostgreSQL 16 + [SQLAlchemy 2](https://docs.sqlalchemy.org/) (async) |
| Migrations | [Alembic](https://alembic.sqlalchemy.org/) |
| Cache & queue | [Redis 7](https://redis.io/) + [arq](https://arq-docs.helpmanual.io/) |
| Admin | [sqladmin](https://aminalaee.dev/sqladmin/) |
| Monitoring | [Sentry](https://sentry.io/) + [Prometheus](https://prometheus.io/) |
| Reverse proxy | [Traefik v3](https://traefik.io/) with Let's Encrypt |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Linter | [Ruff](https://docs.astral.sh/ruff/) |
| Python | 3.12+ |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Telegram    │────▶│  aiogram Bot  │────▶│  Handlers    │
│  Users       │◀────│  (polling)    │     │              │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                │
                    ┌──────────────┐             │
                    │  FastAPI     │◀────────────┤
                    │  (API/Admin) │             │
                    └──────────────┘     ┌──────▼───────┐
                                         │  Services    │
┌─────────────┐     ┌──────────────┐     │  (business   │
│  arq Worker  │────▶│  Notifications│    │   logic)     │
│  (background)│     │  Reminders   │     └──────┬───────┘
└─────────────┘     └──────────────┘            │
                                         ┌──────▼───────┐
┌─────────────┐                          │  LangGraph   │
│  PostgreSQL  │◀────────────────────────│  AI Agents   │
└─────────────┘                          └──────┬───────┘
                                                │
┌─────────────┐                          ┌──────▼───────┐
│  Redis       │◀────────────────────────│  OpenAI API  │
│  (cache/FSM) │                         │  (GPT/Whisper)│
└─────────────┘                          └──────────────┘
```

### AI Agent Pipeline

```
User message ─▶ Whisper (voice) ─▶ Validation ─▶ Router
                                                    │
                                    ┌───────────────┼───────────────┐
                                    ▼               ▼               ▼
                              Event Agent     Note Agent      Query Agent
                                    │               │               │
                                    └───────────────┼───────────────┘
                                                    ▼
                                               Formatter ─▶ Response
```

### Beautiful Date Strategies

The engine calculates mathematically interesting milestones between an event date and the current date:

| Strategy | Example |
|----------|---------|
| Anniversary | 1 year, 5 years, 10 years... |
| Repdigits | 111 days, 2222 days, 33333 hours... |
| Palindrome | 121 days, 12321 hours... |
| Powers of two | 256 days, 1024 days, 4096 hours... |
| Sequence | 123 days, 1234 hours... |
| Round multiples | 500 days, 10000 hours... |
| Special | 365 days, 1000 days, 42 days... |
| Compound | Combinations using years + months + days |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Docker & Docker Compose (for PostgreSQL and Redis)

### Setup

```bash
# Clone the repository
git clone https://github.com/ipolotsky/noteme.git
cd noteme

# Copy env template and fill in required values
cp .env.template .env

# Start PostgreSQL + Redis
docker compose up -d db redis

# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start the app (bot polling + FastAPI server)
uv run python -m app
```

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `NOTEME_BOT_TOKEN` | Telegram Bot API token from [@BotFather](https://t.me/BotFather) |
| `NOTEME_BOT_USERNAME` | Bot username without `@` |
| `NOTEME_DB_PASSWORD` | PostgreSQL password |
| `NOTEME_OPENAI_API_KEY` | OpenAI API key (for GPT + Whisper) |
| `NOTEME_ADMIN_USERNAME` | Admin panel login |
| `NOTEME_ADMIN_PASSWORD` | Admin panel password |
| `NOTEME_ADMIN_SECRET_KEY` | Session signing secret |

See [.env.template](.env.template) for the full list of configuration options.

## Development

### Port Mapping

| Service | Dev | Prod |
|---------|-----|------|
| PostgreSQL | 5433 | 5432 |
| Redis | 6380 | 6379 |
| FastAPI | 8000 | 443 (via Traefik) |

### Running Tests

```bash
# Run full test suite
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Run a specific test file
uv run pytest tests/test_services/test_event_service.py -v
```

### Linting

```bash
# Check
uv run ruff check app/ tests/

# Auto-fix
uv run ruff check --fix app/ tests/
```

### Background Worker

The arq worker handles scheduled tasks (daily digests, note reminders):

```bash
uv run arq app.workers.WorkerSettings
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1
```

## Production Deployment

### CI/CD

The GitHub Actions pipeline runs on every push to `main`:

1. **Lint** — Ruff checks
2. **Test** — Full pytest suite with PostgreSQL + Redis services
3. **Build** — Docker image built and pushed to GHCR
4. **Deploy** — SSH to server, pull image, run migrations, restart services

### Server Setup

```bash
# On the server
mkdir -p /opt/noteme/traefik
cd /opt/noteme

# Create .env with production values
nano .env

# The CI/CD pipeline handles the rest:
# - Copies docker-compose.prod.yml and traefik/ config
# - Pulls the latest image from GHCR
# - Runs migrations
# - Starts all services
```

### Production Services

- **app** — Bot + FastAPI (behind Traefik)
- **worker** — arq background worker
- **db** — PostgreSQL 16
- **redis** — Redis 7
- **traefik** — Reverse proxy with auto SSL
- **databasus** — Database backup panel

## Project Structure

```
noteme/
├── app/
│   ├── __main__.py          # Entry point
│   ├── bot.py               # Aiogram dispatcher
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Pydantic settings
│   ├── database.py          # Async SQLAlchemy engine
│   ├── admin/               # sqladmin views & auth
│   ├── agents/              # LangGraph AI pipeline
│   ├── api/                 # FastAPI endpoints
│   ├── handlers/            # Telegram message handlers
│   ├── keyboards/           # Inline & reply keyboards
│   ├── middlewares/         # Bot & ASGI middlewares
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   │   └── beautiful_dates/ # Milestone strategies
│   ├── workers/             # arq background tasks
│   ├── i18n/                # Translations (en, ru)
│   ├── templates/           # Jinja2 HTML templates
│   ├── static/              # CSS, JS, images
│   └── utils/               # Helpers
├── alembic/                 # Database migrations
├── tests/                   # Test suite (376 tests)
├── traefik/                 # Traefik config
├── docker-compose.yml       # Dev environment
├── docker-compose.prod.yml  # Production environment
├── Dockerfile               # Multi-stage build
├── pyproject.toml           # Project config
└── uv.lock                  # Dependency lockfile
```

## License

**Proprietary.** This source code is provided for reference only. You may not copy, modify, distribute, or use this code (in whole or in part) without explicit written permission from the author. See [LICENSE](LICENSE) for details.
