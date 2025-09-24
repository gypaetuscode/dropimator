# dropimator

`dropimator` automates the journey of supplier catalogue data from a semicolon-separated CSV into a merchandisable product catalogue.
It downloads the latest feed, stores product records in PostgreSQL, enriches them with OpenAI-powered marketing content, and
synchronises the result with a PrestaShop storefront via the official web service API.

## System overview

The pipeline is composed of three main stages:

1. **CSV acquisition (`get_csv/`)** &mdash; a Selenium automation signs into the supplier portal defined by environment variables and
   downloads the newest CSV file.
2. **Product import and enrichment (`main.py` + `dropimator/`)** &mdash; the CLI entry point orchestrates the reusable importer
   package to load the CSV into PostgreSQL, request GPT-generated category assignments plus marketing copy, and persist the
   responses alongside the raw product fields.
3. **Store synchronisation (`sync/`)** &mdash; a PHP CLI app reads the enriched products, multiplies prices, ensures taxonomy and
   attribute options exist, and pushes product data (including images and combinations) to PrestaShop using its web service.

The legacy `run.sh` script shows how these pieces were orchestrated in production: refresh CSV files, run the importer, then
launch the PHP sync.

## Repository structure

```
.
├── docker-compose.yml          # Local PostgreSQL + pgAdmin services
├── dropimator/                 # Python package powering the importer (configuration, services, OpenAI helpers)
│   ├── __init__.py             # Public package interface used by main.py
│   ├── config.py               # Logging/OpenAI/database configuration helpers
│   ├── csv_utils.py            # CSV discovery + streaming helpers
│   ├── models.py               # SQLAlchemy metadata and Product model
│   ├── openai_client.py        # Prompt builders and ChatCompletion utilities
│   └── product_service.py      # Domain logic for imports and enrichment
├── main.py                     # Thin CLI wrapper that wires the importer together
├── requirements.txt            # Python dependencies for the importer and notebooks
├── run.sh                      # Legacy orchestration script (uses historical deployment paths)
├── get_csv/
│   ├── docker-compose.yml      # Selenium Chrome container for the CSV downloader
│   └── main.py                 # Headless Chrome automation for retrieving the supplier CSV
├── sync/
│   ├── composer.json           # PHP dependencies (PrestaShop web service client, dotenv)
│   ├── index.php               # Entry point that pulls products from PostgreSQL and syncs them to PrestaShop
│   └── service.php             # Helper functions for interacting with the PrestaShop API
└── get_product_*.ipynb         # Exploratory notebooks for embeddings and category experiments
```

## Prerequisites

- Python 3.10+ with `pip`
- PHP 8.1+ with `composer`
- Docker and Docker Compose (for local PostgreSQL/pgAdmin and optional Selenium)
- An OpenAI API key with access to `gpt-3.5-turbo`
- Access credentials for the supplier portal and the destination PrestaShop instance

## Environment configuration

Create a `.env` file in the repository root so both the importer and Selenium script can read it via `python-dotenv`:

```env
# OpenAI + PostgreSQL used by main.py
OPENAI_API_KEY=sk-...
PG_HOST=localhost
PG_USERNAME=postgres
PG_PASSWORD=postgres
PG_DATABASE=dropimator
# Optional: override CSV discovery instead of picking the newest *.csv in the repo root
# PRODUCT_CSV_PATH=/absolute/path/to/products.csv

# Credentials for get_csv/main.py
CSV_URL=https://supplier.example.com/export
EMAIL=buyer@example.com
PASSWORD=SuperSecret
```

Create a second `.env` inside `sync/` for the PHP application:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=dropimator
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=postgres
STORE_URL=https://prestashop.example.com
WEBSERVICE_KEY=XXXXXXXXXXXXXXXXXXXX
```

> **Note:** The PHP sync multiplies inbound prices by the constant `PRICE_MULTIPLIER = 4.96`. Adjust the logic if your margin
> model differs.

## Running the pipeline locally

1. **Start PostgreSQL and pgAdmin**
   ```bash
   docker compose up -d
   ```
   This creates a persistent `data/` volume for PostgreSQL and exposes pgAdmin on port 5050.

2. **Install Python dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Download the supplier CSV (optional automation)**
   ```bash
   # Launch Selenium Chrome if you are not running a local Chrome/driver
   docker compose -f get_csv/docker-compose.yml up -d
   python get_csv/main.py
   ```
   The script stores the downloaded file in `get_csv/`; move it next to `main.py` or set `PRODUCT_CSV_PATH` so the importer
   knows which file to ingest.

4. **Import and enrich products**
   ```bash
   python main.py
   ```
   The script connects to PostgreSQL using the configured credentials, creates the `products` table if needed, ingests rows from
   the newest CSV, and asks OpenAI for category and marketing metadata when the database fields are empty.

5. **Install PHP dependencies and sync to PrestaShop**
   ```bash
   cd sync
   composer install
   php index.php
   ```
   The synchroniser ensures manufacturers, categories, attributes, and product images exist in PrestaShop before updating stock
   quantities. Products without required marketing fields are skipped until the importer populates them.

## Operational notes

- `main.py` expects semicolon-delimited CSV headers matching the column names (e.g. `sku`, `manufacturer_name`, `retail_price`).
- Any OpenAI failures are logged and skipped; rerunning the importer is idempotent thanks to SQLAlchemy upserts on `sku`.
- The Selenium downloader targets specific XPaths in the supplier portal; adjust them if the UI changes.
- `run.sh` is preserved for reference but still points to the historical deployment path `/home/dev/projects/power_store`.
  Update it before reusing the automation verbatim.
- The exploratory notebooks (`get_product_category.ipynb`, `get_product_embeddings.ipynb`) demonstrate alternative enrichment
  workflows; they rely on the same environment variables as `main.py`.

## Troubleshooting

- Ensure your OpenAI quota covers the volume of completions you plan to generate.
- If the importer cannot find a CSV, either move the file to the repository root or set `PRODUCT_CSV_PATH` explicitly.
- The PHP sync requires existing attribute groups named `Aroma` and `Greutate`; they are created in PrestaShop before new
  attribute values are added.
- When running inside containers, map hostnames/ports appropriately (e.g. use `postgres` as the host when PHP runs from a
  container attached to the same Compose network).

