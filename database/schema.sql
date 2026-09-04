-- Analytics schema tables for the Maven Fuzzy Factory dataset.
-- Applied on first Postgres init (via docker-entrypoint-initdb.d) and by ingest_data.py.

CREATE TABLE IF NOT EXISTS analytics.website_sessions (
    website_session_id BIGINT PRIMARY KEY,
    created_at         TIMESTAMP NOT NULL,
    user_id            BIGINT NOT NULL,
    is_repeat_session  SMALLINT NOT NULL DEFAULT 0,
    utm_source         VARCHAR(100),
    utm_campaign       VARCHAR(100),
    utm_content        VARCHAR(100),
    device_type        VARCHAR(50),
    http_referer       VARCHAR(256)
);

CREATE TABLE IF NOT EXISTS analytics.products (
    product_id   BIGINT PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL,
    product_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.website_pageviews (
    website_pageview_id BIGINT PRIMARY KEY,
    created_at          TIMESTAMP NOT NULL,
    website_session_id  BIGINT NOT NULL
        REFERENCES analytics.website_sessions (website_session_id),
    pageview_url        VARCHAR(256) NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.orders (
    order_id           BIGINT PRIMARY KEY,
    created_at         TIMESTAMP NOT NULL,
    website_session_id BIGINT NOT NULL
        REFERENCES analytics.website_sessions (website_session_id),
    user_id            BIGINT NOT NULL,
    primary_product_id BIGINT NOT NULL
        REFERENCES analytics.products (product_id),
    items_purchased    SMALLINT NOT NULL,
    price_usd          NUMERIC(10, 2) NOT NULL,
    cogs_usd           NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.order_items (
    order_item_id   BIGINT PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    order_id        BIGINT NOT NULL
        REFERENCES analytics.orders (order_id),
    product_id      BIGINT NOT NULL
        REFERENCES analytics.products (product_id),
    is_primary_item SMALLINT NOT NULL DEFAULT 1,
    price_usd       NUMERIC(10, 2) NOT NULL,
    cogs_usd        NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.order_item_refunds (
    order_item_refund_id BIGINT PRIMARY KEY,
    created_at           TIMESTAMP NOT NULL,
    order_item_id        BIGINT NOT NULL
        REFERENCES analytics.order_items (order_item_id),
    order_id             BIGINT NOT NULL
        REFERENCES analytics.orders (order_id),
    refund_amount_usd    NUMERIC(10, 2) NOT NULL
);
