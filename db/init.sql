-- =============================================================================
-- Industrial IoT Pipeline — PostgreSQL Schema
-- Auto-loaded on first boot via docker-entrypoint-initdb.d
-- =============================================================================

-- ── Device Registry ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS machines (
    id              serial PRIMARY KEY,
    machine_id      varchar(50)  NOT NULL UNIQUE,
    name            varchar(100) NOT NULL,
    type            varchar(50)  NOT NULL,
    location        varchar(100) NOT NULL,
    commissioned_date date       NOT NULL DEFAULT CURRENT_DATE,
    created_at      timestamptz  NOT NULL DEFAULT now()
);

-- Seed 5 demo machines matching the simulator
INSERT INTO machines (machine_id, name, type, location, commissioned_date)
VALUES
    ('machine-1', 'CNC Mill A',      'CNC',        'Hall A – Line 1', '2023-01-15'),
    ('machine-2', 'CNC Lathe B',     'CNC',        'Hall A – Line 2', '2023-03-22'),
    ('machine-3', 'Assembly Robot C', 'Robot',      'Hall B – Line 1', '2022-11-05'),
    ('machine-4', 'Press D',         'Hydraulic',   'Hall B – Line 2', '2024-01-10'),
    ('machine-5', 'Conveyor E',      'Conveyor',    'Hall C – Line 1', '2024-06-01')
ON CONFLICT (machine_id) DO NOTHING;

-- ── Alert Log ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id              serial PRIMARY KEY,
    machine_id      varchar(50)  NOT NULL,
    metric          varchar(50)  NOT NULL,
    value           double precision NOT NULL,
    threshold       double precision NOT NULL,
    severity        varchar(20)  NOT NULL CHECK (severity IN ('warning', 'critical')),
    status          varchar(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved')),
    fired_at        timestamptz  NOT NULL DEFAULT now(),
    acknowledged_at timestamptz,
    resolved_at     timestamptz
);

CREATE INDEX IF NOT EXISTS idx_alerts_machine_id ON alerts (machine_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status     ON alerts (status);

-- ── ERP Ingested Records ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS erp_data (
    id              serial PRIMARY KEY,
    machine_id      varchar(50)  NOT NULL,
    production_date date         NOT NULL,
    units_produced  integer      NOT NULL,
    energy_kwh      double precision NOT NULL,
    defect_count    integer      NOT NULL DEFAULT 0,
    operator        varchar(100),
    shift           varchar(20),
    ingested_at     timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_erp_data_machine_id ON erp_data (machine_id);

-- ── Data Quality Log ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_log (
    id              serial PRIMARY KEY,
    source          varchar(50)  NOT NULL,
    record_id       varchar(100),
    issue_type      varchar(50)  NOT NULL,
    field_name      varchar(100),
    details         text,
    detected_at     timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quality_source ON data_quality_log (source);
CREATE INDEX IF NOT EXISTS idx_quality_type   ON data_quality_log (issue_type);
