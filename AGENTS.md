# dropimator Contribution Guide

## Repository overview
- `main.py` ingests product rows from a semicolon-delimited CSV into PostgreSQL using SQLAlchemy, enriches each product with OpenAI-powered categorisation and marketing copy, and persists the model responses alongside price and metadata fields.
- `get_csv/` hosts a Selenium automation that logs into a supplier portal defined by environment variables (`CSV_URL`, `EMAIL`, `PASSWORD`) to download the latest product CSV.
- `sync/` contains a small PHP application that reads the PostgreSQL `products` table and synchronises data to a PrestaShop store through the official web service client.
- `run.sh` orchestrates the full pipeline on the original deployment environment: refresh CSV files, run the Python importer, then trigger the PHP sync script.
- `docker-compose.yml` files provide local services for PostgreSQL/pgAdmin at the repo root and Selenium Chrome inside `get_csv/`.

## Data flow at a glance
1. Use `get_csv/main.py` to download the latest CSV from the remote portal (Chrome webdriver runs headless; ensure Selenium Hub from `get_csv/docker-compose.yml` is available if you are not using a local browser).
2. Execute `main.py` in the repository root to populate/update the `products` table and request completions from OpenAI. The script expects `OPENAI_API_KEY` plus PostgreSQL credentials (`PG_USERNAME`, `PG_PASSWORD`, `PG_DATABASE`) in your environment or an `.env` file.
3. Run the PHP sync in `sync/index.php` to push enriched products, images, and combinations to PrestaShop using the web service credentials stored in that directory's `.env`.

## Python guidelines
- Follow PEP 8 style conventions and prefer explicit functions/helpers instead of duplicating inline logic (e.g., for new OpenAI prompts or database fields, extend helper functions in `main.py`).
- Keep SQLAlchemy schema changes in sync with the actual PostgreSQL database and document any new columns in this file.
- When you modify Python code, run `python -m compileall main.py get_csv/main.py` and delete any generated `__pycache__` directories before committing.
- Add new third-party dependencies to `requirements.txt` and pin them appropriately.

## PHP guidelines
- Use the provided PrestaShop Webservice helper functions in `sync/service.php` for new operations; prefer extending them over writing raw cURL logic elsewhere.
- Store PrestaShop credentials in environment variables via `.env`. Never hard-code secrets in source files.
- When you modify PHP files under `sync/`, run `php -l <file>` for each changed file to ensure the syntax is valid.

## Operational notes
- `run.sh` still references the historical deployment path (`/home/dev/projects/power_store`). Update those paths if you adapt the automation to a new environment.
- The automation is network- and credentials-dependent. Provide mock data or guard your code with feature flags if you need to run it in CI.
- There is no dedicated test suite. Prefer creating focused scripts or notebooks for experiments (see the existing Jupyter notebooks at the repo root) and document any manual validation steps in your pull request description.
