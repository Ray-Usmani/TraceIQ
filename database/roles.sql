-- PostgreSQL roles for TraceIQ.
-- Passwords match .env.example defaults. ingest_data.py can rotate them from env.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_admin') THEN
        CREATE ROLE analytics_admin WITH LOGIN PASSWORD 'admin_password' CREATEDB;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_reader') THEN
        CREATE ROLE analytics_reader WITH LOGIN PASSWORD 'reader_password';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA analytics TO analytics_admin;
GRANT ALL ON SCHEMA analytics TO analytics_admin;
GRANT ALL ON ALL TABLES IN SCHEMA analytics TO analytics_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA analytics TO analytics_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics
    GRANT ALL ON TABLES TO analytics_admin;

GRANT USAGE ON SCHEMA analytics TO analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO analytics_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics
    GRANT SELECT ON TABLES TO analytics_reader;

-- Ensure reader cannot write even if privileges are mishandled later.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA analytics FROM analytics_reader;
