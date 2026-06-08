INSERT INTO mart.fx_daily (
	source_date,
	base_currency,
	target_currency,
	rate,
	prev_rate,
	daily_change_pct,
	ma_7d,
	ma_30d,
	volatility_30d
)
SELECT
	source_date,
	base_currency,
	target_currency,
	rate,
	LAG(rate) OVER W AS prev_rate,
	ROUND((rate - LAG(rate) OVER W) / NULLIF(LAG(rate) OVER W, 0) * 100, 4) AS daily_change_pct,
	ROUND(AVG(rate) OVER (W ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 6) AS ma_7d,
	ROUND(AVG(rate) OVER (W ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 6) AS ma_30d,
	ROUND(STDDEV_SAMP(rate) OVER (W ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 6) AS volatility_30d
FROM staging.stg_exchange_rate s
WINDOW W AS (PARTITION BY base_currency, target_currency ORDER BY source_date)
ON CONFLICT (source_date, base_currency, target_currency)
DO UPDATE SET
	rate = EXCLUDED.rate,
	prev_rate = EXCLUDED.prev_rate,
	daily_change_pct = EXCLUDED.daily_change_pct,
	ma_7d = EXCLUDED.ma_7d,
	ma_30d = EXCLUDED.ma_30d,
	volatility_30d = EXCLUDED.volatility_30d,
	refreshed_at = NOW();