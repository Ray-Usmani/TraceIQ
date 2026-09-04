-- Indexes for expected investigation query patterns.
-- Applied by ingest_data.py AFTER bulk load (faster than indexing during COPY).

CREATE INDEX IF NOT EXISTS idx_ws_created_at
    ON analytics.website_sessions (created_at);

CREATE INDEX IF NOT EXISTS idx_wp_created_at
    ON analytics.website_pageviews (created_at);

CREATE INDEX IF NOT EXISTS idx_orders_created_at
    ON analytics.orders (created_at);

CREATE INDEX IF NOT EXISTS idx_ws_utm_source_campaign
    ON analytics.website_sessions (utm_source, utm_campaign);

CREATE INDEX IF NOT EXISTS idx_ws_user_id
    ON analytics.website_sessions (user_id);

CREATE INDEX IF NOT EXISTS idx_orders_user_id
    ON analytics.orders (user_id);

CREATE INDEX IF NOT EXISTS idx_wp_session_id
    ON analytics.website_pageviews (website_session_id);

CREATE INDEX IF NOT EXISTS idx_orders_session_id
    ON analytics.orders (website_session_id);

CREATE INDEX IF NOT EXISTS idx_oi_order_id
    ON analytics.order_items (order_id);

CREATE INDEX IF NOT EXISTS idx_oi_product_id
    ON analytics.order_items (product_id);

CREATE INDEX IF NOT EXISTS idx_oir_order_item_id
    ON analytics.order_item_refunds (order_item_id);
