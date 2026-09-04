"""Bulk-load the Maven Fuzzy Factory CSVs into PostgreSQL analytics schema."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import psycopg

# ---------------------------------------------------------------------------
# Paths & connection settings
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_DIR = Path(os.getenv("DATABASE_DIR", REPO_ROOT / "database"))
DATA_RAW_DIR = Path(os.getenv("DATA_RAW_DIR", REPO_ROOT / "data" / "raw"))

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "traceiq")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

ANALYTICS_ADMIN_PASSWORD = os.getenv("ANALYTICS_ADMIN_PASSWORD", "admin_password")
ANALYTICS_READER_PASSWORD = os.getenv("ANALYTICS_READER_PASSWORD", "reader_password")

# FK-safe load order
TABLE_LOAD_ORDER = [
    "products",
    "website_sessions",
    "website_pageviews",
    "orders",
    "order_items",
    "order_item_refunds",
]

EXPECTED_COLUMNS: dict[str, list[str]] = {
    "products": ["product_id", "created_at", "product_name"],
    "website_sessions": [
        "website_session_id",
        "created_at",
        "user_id",
        "is_repeat_session",
        "utm_source",
        "utm_campaign",
        "utm_content",
        "device_type",
        "http_referer",
    ],
    "website_pageviews": [
        "website_pageview_id",
        "created_at",
        "website_session_id",
        "pageview_url",
    ],
    "orders": [
        "order_id",
        "created_at",
        "website_session_id",
        "user_id",
        "primary_product_id",
        "items_purchased",
        "price_usd",
        "cogs_usd",
    ],
    "order_items": [
        "order_item_id",
        "created_at",
        "order_id",
        "product_id",
        "is_primary_item",
        "price_usd",
        "cogs_usd",
    ],
    "order_item_refunds": [
        "order_item_refund_id",
        "created_at",
        "order_item_id",
        "order_id",
        "refund_amount_usd",
    ],
}

# Soft lower bounds (Maven Fuzzy Factory full dump)
MIN_ROW_COUNTS: dict[str, int] = {
    "products": 1,
    "website_sessions": 1000,
    "website_pageviews": 1000,
    "orders": 100,
    "order_items": 100,
    "order_item_refunds": 1,
}


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def run_sql_file(conn: psycopg.Connection, path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    print(f"  Applying {path.name} ...")
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def ensure_roles(conn: psycopg.Connection) -> None:
    """Create/update roles using passwords from the environment."""
    print("  Ensuring analytics_admin and analytics_reader roles ...")

    def q(password: str) -> str:
        return password.replace("'", "''")

    with conn.cursor() as cur:
        cur.execute(
            f"""
            DO $do$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_admin') THEN
                    CREATE ROLE analytics_admin WITH LOGIN CREATEDB
                        PASSWORD '{q(ANALYTICS_ADMIN_PASSWORD)}';
                ELSE
                    ALTER ROLE analytics_admin WITH PASSWORD '{q(ANALYTICS_ADMIN_PASSWORD)}';
                END IF;

                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_reader') THEN
                    CREATE ROLE analytics_reader WITH LOGIN
                        PASSWORD '{q(ANALYTICS_READER_PASSWORD)}';
                ELSE
                    ALTER ROLE analytics_reader WITH PASSWORD '{q(ANALYTICS_READER_PASSWORD)}';
                END IF;
            END
            $do$;
            """
        )
        cur.execute("GRANT USAGE ON SCHEMA analytics TO analytics_admin")
        cur.execute("GRANT ALL ON SCHEMA analytics TO analytics_admin")
        cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA analytics TO analytics_admin")
        cur.execute("GRANT USAGE ON SCHEMA analytics TO analytics_reader")
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO analytics_reader")
        cur.execute(
            """
            ALTER DEFAULT PRIVILEGES IN SCHEMA analytics
                GRANT SELECT ON TABLES TO analytics_reader
            """
        )
    conn.commit()


def verify_csvs() -> dict[str, Path]:
    print("Verifying CSV files ...")
    paths: dict[str, Path] = {}
    missing: list[str] = []
    for table in TABLE_LOAD_ORDER:
        path = DATA_RAW_DIR / f"{table}.csv"
        if not path.exists():
            missing.append(str(path))
        else:
            paths[table] = path
    if missing:
        print("ERROR: Missing required CSV files:")
        for m in missing:
            print(f"  - {m}")
        print(
            "\nDownload the Maven Fuzzy Factory dataset from Maven Analytics "
            "and place the six CSV files in data/raw/."
        )
        sys.exit(1)
    print(f"  Found {len(paths)} CSV files in {DATA_RAW_DIR}")
    return paths


def validate_headers(paths: dict[str, Path]) -> None:
    print("Validating CSV headers ...")
    for table, path in paths.items():
        expected = EXPECTED_COLUMNS[table]
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
        normalized = [h.strip().lower() for h in header]
        missing = [c for c in expected if c not in normalized]
        if missing:
            print(f"ERROR: {path.name} missing columns: {missing}")
            print(f"  Found: {normalized}")
            sys.exit(1)
        print(f"  {table}: OK ({len(normalized)} columns)")


def truncate_tables(conn: psycopg.Connection) -> None:
    print("Truncating analytics tables (CASCADE) ...")
    with conn.cursor() as cur:
        tables = ", ".join(f"analytics.{t}" for t in reversed(TABLE_LOAD_ORDER))
        cur.execute(f"TRUNCATE {tables} CASCADE")
    conn.commit()


def copy_table(conn: psycopg.Connection, table: str, path: Path) -> int:
    columns = ", ".join(EXPECTED_COLUMNS[table])
    copy_sql = (
        f"COPY analytics.{table} ({columns}) "
        f"FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
    )
    print(f"  Loading {table} from {path.name} ...")
    with conn.cursor() as cur:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            with cur.copy(copy_sql) as copy:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    copy.write(chunk)
        cur.execute(f"SELECT COUNT(*) FROM analytics.{table}")
        count = cur.fetchone()[0]
    conn.commit()
    print(f"    -> {count:,} rows")
    return int(count)


def create_indexes(conn: psycopg.Connection) -> None:
    run_sql_file(conn, DATABASE_DIR / "indexes.sql")


def grant_select(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO analytics_reader")
        cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA analytics TO analytics_admin")
    conn.commit()


def print_summary(conn: psycopg.Connection, counts: dict[str, int]) -> None:
    print("\n=== Ingest summary ===")
    with conn.cursor() as cur:
        for table in TABLE_LOAD_ORDER:
            count = counts[table]
            min_expected = MIN_ROW_COUNTS[table]
            status = "OK" if count >= min_expected else "LOW"
            date_range = ""
            cur.execute(
                f"""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'analytics'
                      AND table_name = %s
                      AND column_name = 'created_at'
                )
                """,
                (table,),
            )
            if cur.fetchone()[0]:
                cur.execute(
                    f"SELECT MIN(created_at), MAX(created_at) FROM analytics.{table}"
                )
                mn, mx = cur.fetchone()
                date_range = f"  |  {mn} → {mx}"
            print(f"  {table:22s} {count:>10,}  [{status}]{date_range}")
    total = sum(counts.values())
    print(f"  {'TOTAL':22s} {total:>10,}")
    print("======================\n")


def main() -> None:
    print("TraceIQ data ingest")
    print(f"  DATA_RAW_DIR = {DATA_RAW_DIR}")
    print(f"  DATABASE_DIR = {DATABASE_DIR}")
    print(f"  Postgres     = {POSTGRES_USER}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")

    paths = verify_csvs()
    validate_headers(paths)

    print("Connecting to PostgreSQL ...")
    with connect() as conn:
        print("Ensuring schemas exist ...")
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS analytics")
            cur.execute("CREATE SCHEMA IF NOT EXISTS agent")
        conn.commit()

        run_sql_file(conn, DATABASE_DIR / "schema.sql")
        ensure_roles(conn)
        truncate_tables(conn)

        counts: dict[str, int] = {}
        print("Bulk loading (COPY) ...")
        for table in TABLE_LOAD_ORDER:
            counts[table] = copy_table(conn, table, paths[table])

        print("Creating indexes ...")
        create_indexes(conn)
        grant_select(conn)

        failed = [
            t for t, c in counts.items() if c < MIN_ROW_COUNTS[t]
        ]
        print_summary(conn, counts)
        if failed:
            print(f"ERROR: Row counts below expected minimum for: {failed}")
            sys.exit(1)

    print("Ingest complete. Run scripts/validate_dataset.py next.")


if __name__ == "__main__":
    main()
