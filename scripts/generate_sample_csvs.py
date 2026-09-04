"""Generate small FK-valid sample CSVs for local smoke tests (not the full Maven dump)."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

N_PRODUCTS = 4
N_SESSIONS = 1200
N_ORDERS = 150
N_ITEMS = 180
N_REFUNDS = 20
N_PAGEVIEWS = 1500


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    start = datetime(2014, 1, 1, 10, 0, 0)

    products = [
        (1, start, "The Original Mr. Fuzzy"),
        (2, start + timedelta(days=30), "Mini Fuzzy"),
        (3, start + timedelta(days=90), "Love Bear"),
        (4, start + timedelta(days=180), "Forever Love Bear"),
    ]
    with (RAW / "products.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "created_at", "product_name"])
        for row in products:
            w.writerow([row[0], row[1].isoformat(sep=" "), row[2]])

    sources = ["gsearch", "bsearch", "social", None]
    campaigns = ["brand", "nonbrand", "promo", None]
    devices = ["desktop", "mobile"]

    with (RAW / "website_sessions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "website_session_id",
                "created_at",
                "user_id",
                "is_repeat_session",
                "utm_source",
                "utm_campaign",
                "utm_content",
                "device_type",
                "http_referer",
            ]
        )
        for i in range(1, N_SESSIONS + 1):
            src = rng.choice(sources)
            camp = rng.choice(campaigns) if src else None
            w.writerow(
                [
                    i,
                    (start + timedelta(minutes=i)).isoformat(sep=" "),
                    1000 + (i % 400),
                    1 if i % 7 == 0 else 0,
                    src or "",
                    camp or "",
                    "ad_1" if src else "",
                    rng.choice(devices),
                    "https://www.gsearch.com" if src == "gsearch" else "",
                ]
            )

    with (RAW / "website_pageviews.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "website_pageview_id",
                "created_at",
                "website_session_id",
                "pageview_url",
            ]
        )
        urls = ["/", "/products", "/cart", "/shipping", "/billing", "/thank-you"]
        for i in range(1, N_PAGEVIEWS + 1):
            sid = ((i - 1) % N_SESSIONS) + 1
            w.writerow(
                [
                    i,
                    (start + timedelta(minutes=sid, seconds=i % 50)).isoformat(sep=" "),
                    sid,
                    rng.choice(urls),
                ]
            )

    with (RAW / "orders.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "order_id",
                "created_at",
                "website_session_id",
                "user_id",
                "primary_product_id",
                "items_purchased",
                "price_usd",
                "cogs_usd",
            ]
        )
        for i in range(1, N_ORDERS + 1):
            pid = ((i - 1) % N_PRODUCTS) + 1
            price = round(29.99 + pid * 10, 2)
            cogs = round(price * 0.4, 2)
            w.writerow(
                [
                    i,
                    (start + timedelta(hours=i)).isoformat(sep=" "),
                    i,  # session 1..N_ORDERS have orders
                    1000 + i,
                    pid,
                    1 + (i % 2),
                    price,
                    cogs,
                ]
            )

    with (RAW / "order_items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "order_item_id",
                "created_at",
                "order_id",
                "product_id",
                "is_primary_item",
                "price_usd",
                "cogs_usd",
            ]
        )
        for i in range(1, N_ITEMS + 1):
            oid = ((i - 1) % N_ORDERS) + 1
            pid = ((i - 1) % N_PRODUCTS) + 1
            price = round(19.99 + pid * 5, 2)
            w.writerow(
                [
                    i,
                    (start + timedelta(hours=oid, minutes=1)).isoformat(sep=" "),
                    oid,
                    pid,
                    1 if i <= N_ORDERS else 0,
                    price,
                    round(price * 0.4, 2),
                ]
            )

    with (RAW / "order_item_refunds.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "order_item_refund_id",
                "created_at",
                "order_item_id",
                "order_id",
                "refund_amount_usd",
            ]
        )
        for i in range(1, N_REFUNDS + 1):
            item_id = i
            order_id = ((item_id - 1) % N_ORDERS) + 1
            w.writerow(
                [
                    i,
                    (start + timedelta(days=2, hours=i)).isoformat(sep=" "),
                    item_id,
                    order_id,
                    19.99,
                ]
            )

    print(f"Wrote sample CSVs to {RAW}")
    print(
        f"  products={N_PRODUCTS}, sessions={N_SESSIONS}, pageviews={N_PAGEVIEWS}, "
        f"orders={N_ORDERS}, items={N_ITEMS}, refunds={N_REFUNDS}"
    )
    print("Replace these with the full Maven Fuzzy Factory CSVs for production use.")


if __name__ == "__main__":
    main()
