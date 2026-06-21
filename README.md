# Attribute AI Resolver

A local attribute deduplication and review system for large catalogs.

It does not include scraper code and it does not connect to WooCommerce directly. Your existing scraper can call the local API before creating a new attribute.

## What it does

- Normalizes Persian/Arabic/English attribute names.
- Detects exact aliases.
- Uses RapidFuzz for spelling and formatting similarity.
- Uses a local SentenceTransformers embedding model for semantic similarity.
- Stores embeddings in PostgreSQL with pgvector.
- Keeps uncertain matches in a human review queue.
- Provides a Streamlit admin dashboard.

## Default stack

- FastAPI backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Streamlit dashboard: http://localhost:8501
- PostgreSQL + pgvector
- Default embedding model: BAAI/bge-m3

For weaker hardware, set:

```bash
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384
```

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Backend docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501

Seed sample data:

```bash
docker compose exec api python scripts/seed_examples.py
```

Reindex embeddings:

```bash
curl -X POST http://localhost:8000/embeddings/reindex
```

## API examples

Create a canonical attribute:

```bash
curl -X POST http://localhost:8000/canonical \
  -H "Content-Type: application/json" \
  -d '{
    "name":"RAM",
    "slug":"ram",
    "aliases":["ram", "memory ram", "computer ram"],
    "sample_values":["8GB", "16GB", "DDR4", "DDR5"]
  }'
```

Resolve a new input:

```bash
curl -X POST http://localhost:8000/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "raw_name":"Ram",
    "category":"laptop",
    "sample_values":["8GB", "16GB", "DDR4"]
  }'
```

## Decision types

- `match`: use an existing canonical attribute.
- `review`: send to the dashboard for human confirmation.
- `create_new_candidate`: likely a new attribute, but still queued for review by default.

## Recommended workflow

1. Import your current canonical attributes.
2. Add known aliases.
3. Run `reindex`.
4. Make your scraper call `/resolve` before creating any attribute.
5. Review uncertain results in the dashboard.
6. Every approved decision automatically creates a new alias and improves future matches.

## Offline model usage

The first model load downloads files from Hugging Face. For fully offline deployment, pre-download the model into a Hugging Face cache directory and mount it into the API container, or set `EMBEDDING_MODEL` to a local path.

## Project layout

```text
backend/app/
  main.py              FastAPI app
  normalizer.py        Persian/English normalization
  resolver.py          exact + fuzzy + semantic decision engine
  embedding.py         local SentenceTransformers wrapper
  models.py            SQLAlchemy models
  routes/              API endpoints

dashboard/
  dashboard.py         Streamlit admin UI
```


## Dashboard UI v1.4

نسخه v1.4 داشبورد را مرتب‌تر کرده و برای `Attributes` و `Review queue` صفحه‌بندی اضافه می‌کند. برای هر attribute فقط یک دکمه `Edit` نمایش داده می‌شود و فرم ویرایش فقط برای همان آیتم باز می‌شود. جزئیات بیشتر در `DASHBOARD_UI_V1.4.md` آمده است.
