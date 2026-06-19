import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ============================================================
# Config
# ============================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

DB_URL = (
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

API_BASE = "https://api.frankfurter.dev/v2"
SOURCE_NAME = "frankfurter"
SQL_DIR = Path(__file__).parent / "sql"

# ============================================================
# Main
# ============================================================


def main():
    engine = create_engine(DB_URL)

    try:
        start_date = get_last_loaded_date(engine)
        logger.info(f"Last loaded date found in DB: {start_date}")

        payload = fetch_fx_data(start_date)
        load_to_raw(payload, engine)
        logger.info("✓ Raw load done")

        transform_to_staging(engine)
        logger.info("✓ Staging complete")

        transform_to_mart(engine)
        logger.info("✓ Mart upsert complete")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

# ============================================================
# Get latest date from staging.stg_exchange_rate
# ============================================================


def get_last_loaded_date(engine) -> str:
    """Return last loaded date for incremental fetch, or backfill date if empty."""

    query = text("SELECT MAX(source_date) FROM staging.stg_exchange_rate")

    with engine.connect() as conn:
        result = conn.execute(query)
        last_date = result.scalar()

    if last_date:
        return last_date.strftime("%Y-%m-%d")

    # First run: table empty → backfill from project's chosen start date
    return "2024-01-01"

# ============================================================
# Extract: API → return raw JSON
# ============================================================


def fetch_fx_data(start_date: str) -> list[dict[str, any]]:
    url = f"{API_BASE}/rates"
    current_date = datetime.now().strftime("%Y-%m-%d")

    params = {
        "base": "USD",
        "quotes": "THB,JPY,EUR,GBP,SGD",
        "from": start_date,
        "to": current_date,
        "providers": "ECB",
    }

    logger.info(f"Fetching from {url}")
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    payload = response.json()
    logger.info(f"Got {len(payload)} records")
    return payload

# ============================================================
# Load: INSERT JSON into raw.api_response
# ============================================================


def load_to_raw(payload: list[dict[str, any]], engine) -> int:
    query = text("""
        insert INTO raw.api_response (source, payload)
        VALUES (:source, CAST(:payload AS JSONB))
        RETURNING id
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {
            "source": SOURCE_NAME,
            "payload": json.dumps(payload)
        })
        new_id = result.scalar()
        conn.commit()

    logger.info(f"Inserted into raw.api_response (id={new_id})")
    return new_id  # used by incremental staging transform (planned)

# ============================================================
# Transform: Unnest payload into staging.stg_exchange_rate
# ============================================================


def transform_to_staging(engine) -> None:
    with open(SQL_DIR / "transform" / "stg_exchange_rate.sql", "r", encoding="utf-8") as f:
        STAGING_SQL = f.read()

    with engine.connect() as conn:
        result = conn.execute(text(STAGING_SQL))
        conn.commit()
    logger.info(f"Staging upsert done ({result.rowcount} rows affected)")

# ============================================================
# Transform: Upsert data from staging.stg_exchange_rate to mart.fx_daily
# ============================================================


def transform_to_mart(engine) -> None:
    with open(SQL_DIR / "transform" / "fx_daily.sql", "r", encoding="utf8") as f:
        MART_SQL = f.read()

    with engine.connect() as conn:
        result = conn.execute(text(MART_SQL))
        conn.commit()
    logger.info(f"Mart upsert done ({result.rowcount} rows affected)")


if __name__ == "__main__":
    main()
