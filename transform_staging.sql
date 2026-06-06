WITH parsed AS (
    SELECT
        r.fetched_at,
        (elem.value ->> 'date')::DATE AS source_date,
        (elem.value ->> 'base')::CHAR(3) AS base_currency,
        (elem.value ->> 'quote')::CHAR(3) AS target_currency,
        (elem.value ->> 'rate')::NUMERIC(12, 6) AS rate
    FROM raw.api_response AS r
    CROSS JOIN LATERAL jsonb_array_elements(r.payload) AS elem
    WHERE elem.value ->> 'rate' IS NOT NULL
),

ranked AS (
    SELECT
        source_date,
        base_currency,
        target_currency,
        rate,
        fetched_at,
        row_number() OVER (
            PARTITION BY
                source_date,
                base_currency,
                target_currency
            ORDER BY fetched_at DESC
        ) AS rn
    FROM parsed
)

INSERT INTO staging.stg_exchange_rate
(source_date, base_currency, target_currency, rate)
SELECT
    source_date,
    base_currency,
    target_currency,
    rate
FROM ranked
WHERE rn = 1
ON CONFLICT (source_date, base_currency, target_currency)
DO UPDATE SET
    rate = excluded.rate,
    loaded_at = now();
