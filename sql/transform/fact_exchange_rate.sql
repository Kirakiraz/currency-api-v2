INSERT INTO mart.fact_exchange_rate (
    date_key, base_currency, target_currency, rate
)
SELECT
    TO_CHAR(source_date, 'YYYYMMDD')::INT AS date_key,
    base_currency,
    target_currency,
    rate
FROM staging.stg_exchange_rate
ON CONFLICT (date_key, base_currency, target_currency)
DO UPDATE SET
    rate = excluded.rate,
    refreshed_at = NOW();
