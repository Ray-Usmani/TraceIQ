# TraceIQ

Autonomous data-analysis agent for ecommerce business questions — multi-step investigation with evidence-backed claims, not a text-to-SQL chatbot.

## Quick start

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY if needed

docker compose up --build
```

| Service  | URL                          |
|----------|------------------------------|
| Frontend | http://localhost:5173        |
| Backend  | http://localhost:8000        |
| Health   | http://localhost:8000/health |
| Postgres | localhost:5432               |

## Dataset setup (Phase 1)

TraceIQ uses the public-domain **Maven Fuzzy Factory** ecommerce dataset (~1.7M rows across six tables).

1. Download the dataset from [Maven Analytics](https://mavenanalytics.io/) (search for “Fuzzy Factory” / ecommerce toy store).
2. Place these CSV files in `data/raw/` (filenames must match exactly):

   ```text
   data/raw/
     website_sessions.csv
     website_pageviews.csv
     products.csv
     orders.csv
     order_items.csv
     order_item_refunds.csv
   ```

3. Ensure Docker is running, then create empty tables (fresh volume) and load data:

   ```bash
   docker compose up -d --build
   docker compose exec backend python -m scripts.ingest_data
   docker compose exec backend python -m scripts.validate_dataset
   ```

   For a quick smoke test without the full Maven dump, generate small sample CSVs first:

   ```bash
   python scripts/generate_sample_csvs.py
   ```

4. Validation writes `data/data_profile.json` and confirms the read-only `analytics_reader` role can SELECT but cannot INSERT.

Do **not** commit the CSVs — `data/raw/*` is gitignored.

## LLM

TraceIQ uses **OpenRouter** (OpenAI-compatible). Set in `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MODEL=minimax/minimax-m3:free
```

### Optional LangSmith tracing

Tracing is **off** unless `LANGCHAIN_API_KEY` is set. When present, OpenRouter chat calls are wrapped for LangSmith (`LANGCHAIN_PROJECT=TraceIQ` by default).

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=           # leave empty to disable
LANGCHAIN_PROJECT=TraceIQ
```

## Status

**Phase 2** — safe SQL analyst (schema context, SQLGlot validation, read-only execution, `POST /api/v1/analysis`).
