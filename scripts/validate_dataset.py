"""
Post-load validation for the Maven Fuzzy Factory analytics dataset.

Exits 0 on success, nonzero on any failed check.
Writes data/data_profile.json with per-table stats.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", REPO_ROOT / "data"))
PROFILE_PATH = DATA_DIR / "data_profile.json"

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "traceiq")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

TABLES: dict[str, list[str]] = {
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

PRIMARY_KEYS = {
    "products": "product_id",
    "website_sessions": "website_session_id",
    "website_pageviews": "website_pageview_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "order_item_refunds": "order_item_refund_id",
}

FK_CHECKS = [
    (
        "orders.website_session_id → website_sessions",
        """
        SELECT COUNT(*) FROM analytics.orders o
        LEFT JOIN analytics.website_sessions ws
          ON o.website_session_id = ws.website_session_id
        WHERE ws.website_session_id IS NULL
        """,
    ),
    (
        "website_pageviews.website_session_id → website_sessions",
        """
        SELECT COUNT(*) FROM analytics.website_pageviews wp
        LEFT JOIN analytics.website_sessions ws
          ON wp.website_session_id = ws.website_session_id
        WHERE ws.website_session_id IS NULL
        """,
    ),
    (
        "orders.primary_product_id → products",
        """
        SELECT COUNT(*) FROM analytics.orders o
        LEFT JOIN analytics.products p
          ON o.primary_product_id = p.product_id
        WHERE p.product_id IS NULL
        """,
    ),
    (
        "order_items.order_id → orders",
        """
        SELECT COUNT(*) FROM analytics.order_items oi
        LEFT JOIN analytics.orders o ON oi.order_id = o.order_id
        WHERE o.order_id IS NULL
        """,
    ),
    (
        "order_items.product_id → products",
        """
        SELECT COUNT(*) FROM analytics.order_items oi
        LEFT JOIN analytics.products p ON oi.product_id = p.product_id
        WHERE p.product_id IS NULL
        """,
    ),
    (
        "order_item_refunds.order_item_id → order_items",
        """
        SELECT COUNT(*) FROM analytics.order_item_refunds r
        LEFT JOIN analytics.order_items oi ON r.order_item_id = oi.order_item_id
        WHERE oi.order_item_id IS NULL
        """,
    ),
    (
        "order_item_refunds.order_id → orders",
        """
        SELECT COUNT(*) FROM analytics.order_item_refunds r
        LEFT JOIN analytics.orders o ON r.order_id = o.order_id
        WHERE o.order_id IS NULL
        """,
    ),
]


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{mark}] {label}{suffix}")
    return ok


def validate(conn: psycopg.Connection) -> tuple[bool, dict[str, Any]]:
    all_ok = True
    profile: dict[str, Any] = {}

    print("Checking tables and columns ...")
    with conn.cursor() as cur:
        for table, expected_cols in TABLES.items():
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'analytics' AND table_name = %s
                )
                """,
                (table,),
            )
            exists = cur.fetchone()[0]
            all_ok &= check(f"table analytics.{table} exists", exists)
            if not exists:
                continue

            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'analytics' AND table_name = %s
                """,
                (table,),
            )
            actual = {r[0] for r in cur.fetchall()}
            missing = [c for c in expected_cols if c not in actual]
            all_ok &= check(
                f"analytics.{table} columns",
                not missing,
                f"missing={missing}" if missing else "ok",
            )

            cur.execute(f"SELECT COUNT(*) FROM analytics.{table}")
            rows = int(cur.fetchone()[0])
            all_ok &= check(f"analytics.{table} row count > 0", rows > 0, f"rows={rows:,}")

            pk = PRIMARY_KEYS[table]
            cur.execute(
                f"""
                SELECT COUNT(*) - COUNT(DISTINCT {pk})
                FROM analytics.{table}
                """
            )
            dupes = int(cur.fetchone()[0])
            all_ok &= check(
                f"analytics.{table}.{pk} unique",
                dupes == 0,
                f"duplicates={dupes}" if dupes else "ok",
            )

            cur.execute(
                f"SELECT COUNT(*) FROM analytics.{table} WHERE created_at IS NULL"
            )
            null_ts = int(cur.fetchone()[0])
            all_ok &= check(
                f"analytics.{table}.created_at not null",
                null_ts == 0,
                f"nulls={null_ts}" if null_ts else "ok",
            )

            cur.execute(
                f"SELECT MIN(created_at), MAX(created_at) FROM analytics.{table}"
            )
            min_at, max_at = cur.fetchone()

            null_rates: dict[str, float] = {}
            for col in expected_cols:
                if col == pk:
                    continue
                cur.execute(
                    f"""
                    SELECT COUNT(*) FILTER (WHERE {col} IS NULL)::float
                           / NULLIF(COUNT(*), 0)
                    FROM analytics.{table}
                    """
                )
                rate = cur.fetchone()[0]
                null_rates[col] = round(float(rate or 0.0), 4)

            profile[table] = {
                "rows": rows,
                "min_created_at": min_at.isoformat() if isinstance(min_at, datetime) else str(min_at),
                "max_created_at": max_at.isoformat() if isinstance(max_at, datetime) else str(max_at),
                "null_rates": null_rates,
            }

    print("Checking foreign-key relationships ...")
    with conn.cursor() as cur:
        for label, sql in FK_CHECKS:
            cur.execute(sql)
            orphans = int(cur.fetchone()[0])
            all_ok &= check(label, orphans == 0, f"orphans={orphans}" if orphans else "ok")

    print("Checking analytics_reader can SELECT ...")
    reader_password = os.getenv("ANALYTICS_READER_PASSWORD", "reader_password")
    try:
        with psycopg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=POSTGRES_DB,
            user="analytics_reader",
            password=reader_password,
        ) as reader_conn:
            with reader_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM analytics.products")
                count = cur.fetchone()[0]
            all_ok &= check("analytics_reader SELECT works", True, f"products={count}")

            # Confirm write is denied
            write_denied = False
            try:
                with reader_conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO analytics.products (product_id, created_at, product_name) "
                        "VALUES (-1, NOW(), 'should_fail')"
                    )
                reader_conn.commit()
            except psycopg.Error:
                reader_conn.rollback()
                write_denied = True
            all_ok &= check("analytics_reader INSERT denied", write_denied)
    except psycopg.Error as exc:
        all_ok &= check("analytics_reader can connect", False, str(exc))

    return all_ok, profile


def main() -> None:
    print("TraceIQ dataset validation")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        ok, profile = validate(conn)

    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    print(f"\nWrote profile to {PROFILE_PATH}")

    if ok:
        print("Validation PASSED")
        sys.exit(0)

    print("Validation FAILED")
    sys.exit(1)


if __name__ == "__main__":
    main()
