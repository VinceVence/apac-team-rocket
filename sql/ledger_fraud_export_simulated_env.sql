-- Training export: minttown-apac-2026.minttown_simulated_env (standard SQL, not BQML).
SELECT
  t.transaction_id,
  t.is_fraud,
  CAST(t.amount AS FLOAT64) AS amount_php,
  t.transaction_type,
  t.channel,
  sc.kyc_status AS sender_kyc_status,
  sc.risk_tier AS sender_risk_tier,
  TIMESTAMP_DIFF(
    t.timestamp,
    SAFE_CAST(sc.creation_date AS TIMESTAMP),
    DAY
  ) AS sender_account_age_days,
  sw.wallet_type AS sender_wallet_type,
  CAST(sw.current_balance AS FLOAT64) AS sender_balance_php,
  CAST(sw.daily_spent AS FLOAT64) AS sender_daily_spent_php,
  sw.wallet_status AS sender_wallet_status,
  SAFE_DIVIDE(CAST(t.amount AS FLOAT64), NULLIF(CAST(sw.current_balance AS FLOAT64), 0)) AS amount_to_balance_ratio,
  rc.kyc_status AS receiver_kyc_status,
  rc.risk_tier AS receiver_risk_tier,
  rw.wallet_type AS receiver_wallet_type,
  rw.wallet_status AS receiver_wallet_status,
  d.trust_score AS device_trust_score,
  d.device_model AS device_model
FROM `minttown-apac-2026.minttown_simulated_env.wallet_transactions` AS t
JOIN `minttown-apac-2026.minttown_simulated_env.wallets` AS sw ON sw.wallet_id = t.sender_wallet_id
JOIN `minttown-apac-2026.minttown_simulated_env.customers` AS sc ON sc.customer_id = sw.customer_id
JOIN `minttown-apac-2026.minttown_simulated_env.wallets` AS rw ON rw.wallet_id = t.receiver_wallet_id
JOIN `minttown-apac-2026.minttown_simulated_env.customers` AS rc ON rc.customer_id = rw.customer_id
JOIN `minttown-apac-2026.minttown_simulated_env.devices` AS d ON d.device_id = t.device_id;
