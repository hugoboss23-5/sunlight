-- =============================================================================
-- SUNLIGHT Post-Migration Verification Queries
-- =============================================================================
-- Run these against PostgreSQL after migration to verify data integrity.
-- Every query should return expected results or clearly indicate issues.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Row count verification
-- ---------------------------------------------------------------------------

SELECT 'contracts' AS table_name, COUNT(*) AS row_count FROM contracts
UNION ALL
SELECT 'contracts_clean', COUNT(*) FROM contracts_clean
UNION ALL
SELECT 'analysis_runs', COUNT(*) FROM analysis_runs
UNION ALL
SELECT 'contract_scores', COUNT(*) FROM contract_scores
UNION ALL
SELECT 'audit_log', COUNT(*) FROM audit_log
UNION ALL
SELECT 'political_donations', COUNT(*) FROM political_donations
UNION ALL
SELECT 'api_keys', COUNT(*) FROM api_keys
ORDER BY table_name;

-- ---------------------------------------------------------------------------
-- 2. Verify NO "None" strings remain in contracts_clean
-- ---------------------------------------------------------------------------

SELECT 'contracts_clean None strings' AS check_name,
       COUNT(*) AS should_be_zero
FROM contracts_clean
WHERE award_type = 'None'
   OR extent_competed = 'None'
   OR description = 'None';

-- ---------------------------------------------------------------------------
-- 3. Verify NO zero-offers remain (should all be NULL now)
-- ---------------------------------------------------------------------------

SELECT 'contracts_clean zero offers' AS check_name,
       COUNT(*) AS should_be_zero
FROM contracts_clean
WHERE num_offers = 0;

-- ---------------------------------------------------------------------------
-- 4. Verify enum types are enforced
-- ---------------------------------------------------------------------------

SELECT 'fraud_tier distribution' AS check_name,
       fraud_tier, COUNT(*) AS count
FROM contract_scores
GROUP BY fraud_tier
ORDER BY count DESC;

SELECT 'run_status distribution' AS check_name,
       status, COUNT(*) AS count
FROM analysis_runs
GROUP BY status
ORDER BY count DESC;

-- ---------------------------------------------------------------------------
-- 5. Verify foreign key integrity
-- ---------------------------------------------------------------------------

SELECT 'orphan scores (no contract)' AS check_name,
       COUNT(*) AS should_be_zero
FROM contract_scores cs
LEFT JOIN contracts c ON cs.contract_id = c.contract_id
WHERE c.contract_id IS NULL;

SELECT 'orphan scores (no run)' AS check_name,
       COUNT(*) AS should_be_zero
FROM contract_scores cs
LEFT JOIN analysis_runs ar ON cs.run_id = ar.run_id
WHERE ar.run_id IS NULL;

-- ---------------------------------------------------------------------------
-- 6. Verify audit hash chain
-- ---------------------------------------------------------------------------

WITH chain AS (
    SELECT sequence_number,
           previous_log_hash,
           current_log_hash,
           LAG(current_log_hash) OVER (ORDER BY sequence_number) AS expected_prev
    FROM audit_log
)
SELECT 'audit chain breaks' AS check_name,
       COUNT(*) AS should_be_zero
FROM chain
WHERE sequence_number > 1
  AND previous_log_hash != expected_prev;

-- ---------------------------------------------------------------------------
-- 7. Verify no stale RUNNING runs
-- ---------------------------------------------------------------------------

SELECT 'stale RUNNING runs' AS check_name,
       COUNT(*) AS should_be_zero
FROM analysis_runs
WHERE status = 'RUNNING'
  AND started_at < NOW() - INTERVAL '1 hour';

-- ---------------------------------------------------------------------------
-- 8. Verify financial precision (no floating point artifacts)
-- ---------------------------------------------------------------------------

SELECT 'award_amount precision check' AS check_name,
       COUNT(*) AS should_be_zero
FROM contracts
WHERE award_amount != ROUND(award_amount, 2);

-- ---------------------------------------------------------------------------
-- 9. Verify JSONB fields are valid
-- ---------------------------------------------------------------------------

SELECT 'invalid config_json' AS check_name,
       COUNT(*) AS should_be_zero
FROM analysis_runs
WHERE config_json IS NOT NULL
  AND config_json::text NOT LIKE '{%';

-- ---------------------------------------------------------------------------
-- 10. Index presence verification
-- ---------------------------------------------------------------------------

SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- ---------------------------------------------------------------------------
-- 11. Summary statistics to cross-check with SQLite audit report
-- ---------------------------------------------------------------------------

-- Contracts: award amount stats
SELECT 'contracts amount stats' AS check_name,
       COUNT(*) AS total,
       MIN(award_amount) AS min_amount,
       MAX(award_amount) AS max_amount,
       ROUND(AVG(award_amount), 2) AS avg_amount
FROM contracts;

-- Scores: tier distribution
SELECT 'scores tier dist' AS check_name,
       fraud_tier, COUNT(*) AS count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM contract_scores
GROUP BY fraud_tier
ORDER BY count DESC;

-- Scores: FDR survival rate
SELECT 'FDR survival' AS check_name,
       survives_fdr, COUNT(*) AS count
FROM contract_scores
GROUP BY survives_fdr;
