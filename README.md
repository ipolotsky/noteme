# Noteme Bot

Telegram bot for tracking important dates, discovering beautiful milestones, and managing notes.

## Quick Start

```bash
# Copy env template and fill in your values
cp .env.template .env

# Start PostgreSQL + Redis (dev ports: 5433, 6380)
docker compose up -d db redis

# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start the app (bot + web on port 8001)
uv run python -m app
```

## Dev Port Mapping

| Service    | Dev Port | Prod Port |
|------------|----------|-----------|
| PostgreSQL | 5433     | 5432      |
| Redis      | 6380     | 6379      |
| FastAPI    | 8001     | 443       |
| Prometheus | 9091     | 9090      |
| Grafana    | 3001     | 3000      |
