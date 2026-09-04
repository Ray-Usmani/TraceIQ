-- Bootstrap schemas for TraceIQ.
-- Docker Postgres runs numbered scripts in /docker-entrypoint-initdb.d/ alphabetically:
--   01-init.sql (this file), 02-schema.sql, 03-roles.sql

CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS agent;
