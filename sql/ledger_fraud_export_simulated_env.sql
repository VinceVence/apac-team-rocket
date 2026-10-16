-- Read-only AE source. At most 100 training customers; no mutable wallet state or risk labels as inputs.
WITH owners AS (
  SELECT wallet_id, customer_id FROM `minttown-apac-2026.minttown_simulated_env.wallets`
  WHERE customer_id IN (
    SELECT customer_id FROM `minttown-apac-2026.minttown_simulated_env.customers`
    ORDER BY customer_id LIMIT 100
  )
), scoped AS (
  SELECT t.*, w.customer_id FROM `minttown-apac-2026.minttown_simulated_env.wallet_transactions` t
  JOIN owners w ON w.wallet_id = t.sender_wallet_id
), features AS (
  SELECT transaction_id, customer_id, timestamp AS event_timestamp, is_fraud,
    CAST(amount AS FLOAT64) AS amount_php,
    CASE transaction_type WHEN 'P2P_TRANSFER' THEN 0 WHEN 'MERCHANT_QR' THEN 1
      WHEN 'CASH_OUT_AGENT' THEN 2 WHEN 'CASH_IN_AGENT' THEN 3 ELSE NULL END AS transaction_type_code,
    CASE channel WHEN 'MOBILE_APP' THEN 0 WHEN 'WEB_PORTAL' THEN 1 ELSE NULL END AS channel_code,
    EXTRACT(HOUR FROM timestamp AT TIME ZONE 'UTC') AS hour_utc,
    COUNT(*) OVER (PARTITION BY sender_wallet_id ORDER BY UNIX_SECONDS(timestamp) RANGE BETWEEN 3600 PRECEDING AND 1 PRECEDING) AS prior_count_1h,
    COALESCE(SUM(CAST(amount AS FLOAT64)) OVER (PARTITION BY sender_wallet_id ORDER BY UNIX_SECONDS(timestamp) RANGE BETWEEN 86400 PRECEDING AND 1 PRECEDING),0) AS prior_spend_24h_php,
    COALESCE(AVG(CAST(amount AS FLOAT64)) OVER (PARTITION BY sender_wallet_id ORDER BY UNIX_SECONDS(timestamp) RANGE BETWEEN 2592000 PRECEDING AND 1 PRECEDING),0) AS prior_mean_30d_php,
    COUNT(*) OVER (PARTITION BY sender_wallet_id ORDER BY UNIX_SECONDS(timestamp) RANGE BETWEEN 2592000 PRECEDING AND 1 PRECEDING) AS prior_count_30d
  FROM scoped
)
SELECT * FROM features ORDER BY event_timestamp, transaction_id LIMIT 20001
