-- =============================================================================
-- SUNLIGHT PostgreSQL Schema Migration
-- =============================================================================
-- Version: 1.0.0
-- Date: 2026-02-17
-- Target: PostgreSQL 16+
-- Status: PREPARED — DO NOT EXECUTE without review
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Custom ENUM types
-- ---------------------------------------------------------------------------

CREATE TYPE fraud_tier AS ENUM ('RED', 'YELLOW', 'GREEN', 'GRAY');
CREATE TYPE run_status AS ENUM ('RUNNING', 'COMPLETED', 'ABORTED', 'FAILED');

-- ---------------------------------------------------------------------------
-- contracts — primary scoring table (42K rows)
-- ---------------------------------------------------------------------------

CREATE TABLE contracts (
    contract_id     TEXT            PRIMARY KEY,
    award_amount    NUMERIC(18,2)  NOT NULL CHECK (award_amount >= 0),
    vendor_name     TEXT            NOT NULL,
    agency_name     TEXT            NOT NULL,
    description     TEXT            DEFAULT '',
    start_date      DATE,
    raw_data_hash   CHAR(64),
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE contracts IS 'Primary contract table used by the scoring pipeline.';
COMMENT ON COLUMN contracts.raw_data_hash IS 'SHA-256 hash of original source record.';

CREATE INDEX idx_contracts_vendor  ON contracts (vendor_name);
CREATE INDEX idx_contracts_agency  ON contracts (agency_name);
CREATE INDEX idx_contracts_amount  ON contracts (award_amount);

-- ---------------------------------------------------------------------------
-- contracts_clean — extended dataset from FPDS (337K rows)
-- ---------------------------------------------------------------------------

CREATE TABLE contracts_clean (
    contract_id     TEXT            PRIMARY KEY,
    award_amount    NUMERIC(18,2)  NOT NULL CHECK (award_amount >= 0),
    vendor_name     TEXT            NOT NULL,
    agency_name     TEXT            NOT NULL,
    description     TEXT            DEFAULT '',
    start_date      DATE,
    end_date        DATE,
    award_type      TEXT,           -- NULL means unknown (was "None" string in SQLite)
    num_offers      SMALLINT,       -- NULL means unknown (was 0 in SQLite)
    extent_competed TEXT,           -- NULL means unknown (was "None" string in SQLite)
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE contracts_clean IS
    'Extended contract dataset from FPDS. Independent from contracts table — '
    'only 19% overlap by contract_id. Not used by scoring pipeline.';

CREATE INDEX idx_cc_vendor          ON contracts_clean (vendor_name);
CREATE INDEX idx_cc_agency          ON contracts_clean (agency_name);
CREATE INDEX idx_cc_amount          ON contracts_clean (award_amount);
CREATE INDEX idx_cc_extent_competed ON contracts_clean (extent_competed);
CREATE INDEX idx_cc_award_type      ON contracts_clean (award_type);

-- ---------------------------------------------------------------------------
-- analysis_runs — pipeline run metadata (10s of rows)
-- ---------------------------------------------------------------------------

CREATE TABLE analysis_runs (
    run_id              TEXT            PRIMARY KEY,
    started_at          TIMESTAMPTZ    NOT NULL,
    completed_at        TIMESTAMPTZ,
    status              run_status      NOT NULL DEFAULT 'RUNNING',
    run_seed            INTEGER         NOT NULL,
    config_json         JSONB           NOT NULL DEFAULT '{}',
    config_hash         CHAR(64)        NOT NULL,
    dataset_hash        CHAR(64)        NOT NULL,
    n_contracts         INTEGER         NOT NULL,
    n_scored            INTEGER         DEFAULT 0,
    n_errors            INTEGER         DEFAULT 0,
    summary_json        JSONB           DEFAULT '{}',
    fdr_n_tests         INTEGER,
    fdr_n_significant   INTEGER,
    fdr_alpha           NUMERIC(5,4)    DEFAULT 0.10,
    model_version       TEXT,
    code_commit_hash    CHAR(16),
    environment_json    JSONB           DEFAULT '{}'
);

COMMENT ON TABLE analysis_runs IS 'Metadata for each pipeline execution. Immutable after COMPLETED.';

CREATE INDEX idx_runs_status ON analysis_runs (status);

-- ---------------------------------------------------------------------------
-- contract_scores — scoring results (56K+ rows, grows per run)
-- ---------------------------------------------------------------------------

CREATE TABLE contract_scores (
    score_id                TEXT            PRIMARY KEY,
    contract_id             TEXT            NOT NULL REFERENCES contracts(contract_id),
    run_id                  TEXT            NOT NULL REFERENCES analysis_runs(run_id),

    -- Tier & priority
    fraud_tier              fraud_tier      NOT NULL,
    triage_priority         INTEGER         NOT NULL,
    confidence_score        SMALLINT        NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),

    -- Bootstrap markup
    markup_pct              NUMERIC(10,2),
    markup_ci_lower         NUMERIC(10,2),
    markup_ci_upper         NUMERIC(10,2),

    -- Z-scores
    raw_zscore              NUMERIC(10,4),
    log_zscore              NUMERIC(10,4),

    -- Bootstrap percentile
    bootstrap_percentile    NUMERIC(6,2),
    percentile_ci_lower     NUMERIC(6,2),
    percentile_ci_upper     NUMERIC(6,2),

    -- Bayesian
    bayesian_prior          NUMERIC(8,6),
    bayesian_likelihood_ratio NUMERIC(10,2),
    bayesian_posterior      NUMERIC(8,6),

    -- P-values & FDR
    raw_pvalue              NUMERIC(10,8),
    fdr_adjusted_pvalue     NUMERIC(10,8),
    survives_fdr            BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Metadata
    comparable_count        INTEGER         NOT NULL,
    insufficient_comparables BOOLEAN        NOT NULL DEFAULT FALSE,
    selection_params_json   JSONB,
    scored_at               TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    UNIQUE (contract_id, run_id)
);

COMMENT ON TABLE contract_scores IS
    'Per-contract scoring results. Each row is one contract scored in one run.';

CREATE INDEX idx_scores_run_id      ON contract_scores (run_id);
CREATE INDEX idx_scores_tier        ON contract_scores (fraud_tier);
CREATE INDEX idx_scores_contract    ON contract_scores (contract_id);
CREATE INDEX idx_scores_priority    ON contract_scores (triage_priority);
CREATE INDEX idx_scores_survives    ON contract_scores (survives_fdr) WHERE survives_fdr = TRUE;

-- ---------------------------------------------------------------------------
-- audit_log — cryptographic hash chain
-- ---------------------------------------------------------------------------

CREATE TABLE audit_log (
    log_id              CHAR(16)        PRIMARY KEY,
    sequence_number     INTEGER         NOT NULL UNIQUE,
    timestamp           TIMESTAMPTZ    NOT NULL,
    action_type         TEXT            NOT NULL,
    entity_id           TEXT,
    previous_log_hash   CHAR(64)        NOT NULL,
    current_log_hash    CHAR(64)        NOT NULL,
    run_id              TEXT,
    details             JSONB           NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE audit_log IS
    'Tamper-evident hash chain. Each entry hashes the previous, '
    'providing cryptographic integrity verification.';
COMMENT ON COLUMN audit_log.previous_log_hash IS 'SHA-256 of the previous entry (0x00...0 for first).';
COMMENT ON COLUMN audit_log.current_log_hash IS 'SHA-256 of this entry payload.';

CREATE INDEX idx_audit_sequence ON audit_log (sequence_number);
CREATE INDEX idx_audit_run      ON audit_log (run_id);

-- ---------------------------------------------------------------------------
-- political_donations — vendor donation records
-- ---------------------------------------------------------------------------

CREATE TABLE political_donations (
    id                  SERIAL          PRIMARY KEY,
    vendor_name         TEXT            NOT NULL,
    recipient_name      TEXT            NOT NULL,
    amount              NUMERIC(14,2)  NOT NULL CHECK (amount >= 0),
    donation_date       DATE,
    cycle               TEXT,
    source              TEXT            NOT NULL DEFAULT 'UNKNOWN',

    UNIQUE (vendor_name, recipient_name, cycle)
);

COMMENT ON TABLE political_donations IS
    'Vendor political donations. Used as a risk amplifier in Bayesian priors.';

CREATE INDEX idx_donations_vendor ON political_donations (vendor_name);

-- ---------------------------------------------------------------------------
-- api_keys — authentication
-- ---------------------------------------------------------------------------

CREATE TABLE api_keys (
    key_id          TEXT            PRIMARY KEY,
    key_hash        CHAR(64)        NOT NULL UNIQUE,
    client_name     TEXT            NOT NULL,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    rate_limit      INTEGER         NOT NULL DEFAULT 100,
    rate_window     INTEGER         NOT NULL DEFAULT 3600,
    scopes          TEXT            NOT NULL DEFAULT 'read,analyze',
    notes           TEXT
);

CREATE INDEX idx_api_keys_hash   ON api_keys (key_hash);
CREATE INDEX idx_api_keys_active ON api_keys (is_active) WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- api_usage — request logging (partitioned by month)
-- ---------------------------------------------------------------------------

CREATE TABLE api_usage (
    id              BIGSERIAL,
    key_id          TEXT            NOT NULL REFERENCES api_keys(key_id),
    timestamp       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    endpoint        TEXT            NOT NULL,
    method          TEXT            NOT NULL,
    status_code     SMALLINT,
    response_time_ms NUMERIC(10,2),
    ip_address      INET,

    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

COMMENT ON TABLE api_usage IS 'API request log. Partitioned by month for performance.';

-- Create initial partitions (extend as needed)
CREATE TABLE api_usage_2026_02 PARTITION OF api_usage
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE api_usage_2026_03 PARTITION OF api_usage
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE api_usage_2026_04 PARTITION OF api_usage
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE api_usage_2026_05 PARTITION OF api_usage
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE api_usage_2026_06 PARTITION OF api_usage
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_usage_key_id    ON api_usage (key_id);
CREATE INDEX idx_usage_timestamp ON api_usage (timestamp);

-- ---------------------------------------------------------------------------
-- Full-text search on contract descriptions
-- ---------------------------------------------------------------------------

CREATE INDEX idx_contracts_desc_fts ON contracts
    USING GIN (to_tsvector('english', COALESCE(description, '')));

CREATE INDEX idx_cc_desc_fts ON contracts_clean
    USING GIN (to_tsvector('english', COALESCE(description, '')));

COMMIT;
