-- ============================================================
-- Schemas
-- ============================================================
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;


-- ============================================================
-- RAW LAYER: Collect raw API response
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.api_response (
    id SERIAL PRIMARY KEY,
    fetched_at TIMESTAMP NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL DEFAULT 'frankfurter',
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_fetched_at
ON raw.api_response (fetched_at);


-- ============================================================
-- STAGING LAYER: flat, typed, deduplicated
-- ============================================================
CREATE TABLE IF NOT EXISTS staging.stg_exchange_rate (
    source_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    target_currency CHAR(3) NOT NULL,
    rate NUMERIC(12, 6) NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_date, base_currency, target_currency)
);


-- ============================================================
-- MART LAYER: business-ready by window functions
-- ============================================================
CREATE TABLE IF NOT EXISTS mart.fx_daily (
    source_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    target_currency CHAR(3) NOT NULL,
    rate NUMERIC(12, 6) NOT NULL,
    prev_rate NUMERIC(12, 6),
    daily_change_pct NUMERIC(8, 4),
    ma_7d NUMERIC(12, 6),
    ma_30d NUMERIC(12, 6)
    volatility_30d NUMERIC(12, 6),
    refreshed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_date, base_currency, target_currency)
);
