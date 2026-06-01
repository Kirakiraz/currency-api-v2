import os
import sys
import json
import logging
from datetime import datetime

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

# ============================================================
# Main
# ============================================================


def main():
    engine = create_engine(DB_URL)

    try:
        payload = fetch_fx_data()
        load_to_raw(payload, engine)
        logger.info("✓ Raw load done")
        transform_to_staging(engine)
        logger.info("✓ Staging complete")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

# ============================================================
# Extract: ยิง API → return JSON ดิบ
# ============================================================


def fetch_fx_data() -> list:
    url = f"{API_BASE}/rates"
    params = {
        "base": "USD",
        "quotes": "THB,JPY,EUR,GBP,SGD",
        "from": "2024-01-01",
        "to": "2024-01-31",
        "providers": "ECB",
    }

    logger.info(f"Fetching from {url}")
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    payload = response.json()
    logger.info(f"Got {len(payload)} records")
    return payload


# ============================================================
# Load: INSERT JSON ดิบเข้า raw.api_response
# ============================================================
def load_to_raw(payload: list, engine) -> int:
    query = text("""
        INSERT INTO raw.api_response (source, payload)
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
    return new_id

# ============================================================
# Load: INSERT JSON ดิบเข้า raw.api_response
# ============================================================


def transform_to_staging(engine) -> None:
    STAGING_SQL = """
    INSERT INTO staging.stg_exchange_rate
    (source_date, base_currency, target_currency, rate)
    SELECT
        source_date, base_currency, target_currency, rate
    FROM (
        SELECT
            (elem->>'date')::DATE              AS source_date,
            (elem->>'base')::CHAR(3)           AS base_currency,
            (elem->>'quote')::CHAR(3)          AS target_currency,
            (elem->>'rate')::NUMERIC(12,6)     AS rate,
            ROW_NUMBER() OVER (
                PARTITION BY 
                    (elem->>'date')::DATE,
                    (elem->>'base'),
                    (elem->>'quote')
                ORDER BY r.fetched_at DESC
            ) AS rn
        FROM raw.api_response r,
            jsonb_array_elements(r.payload) AS elem
        WHERE elem->>'rate' IS NOT NULL
    ) ranked
    WHERE rn = 1
    ON CONFLICT (source_date, base_currency, target_currency)
    DO UPDATE SET
        rate      = EXCLUDED.rate,
        loaded_at = NOW();
    """
    with engine.connect() as conn:
        result = conn.execute(text(STAGING_SQL))
        conn.commit()
    logger.info(f"Staging upsert done ({result.rowcount} rows affected)")


if __name__ == "__main__":
    main()
