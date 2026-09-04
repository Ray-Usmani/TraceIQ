# TraceIQ

Autonomous data-analysis agent for ecommerce business questions — multi-step investigation with evidence-backed claims, not a text-to-SQL chatbot.

## Quick start

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY if needed

docker compose up --build
```

| Service  | URL                      |
|----------|--------------------------|
| Frontend | http://localhost:5173    |
| Backend  | http://localhost:8000    |
| Health   | http://localhost:8000/health |
| Postgres | localhost:5432           |

## Status

**Phase 0** — repository structure and Docker infrastructure.
