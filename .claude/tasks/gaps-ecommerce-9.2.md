# Gap Register — Sub-module 9.2: Inventory & Stock Management (Module 9 eCommerce, `ecommerce`)

- **Sub-module:** 9.2 Inventory & Stock Management
- **Date:** 2026-10-29
- **Status Summary:** All 15 review findings resolved. 0 skipped or deferred items. Architectural hand-offs documented below.

---

### GAP-ECOM-9.2-01: Physical Stock Movements & Valuation Ledger Handoff
- **Owner:** `inventory` (Module 5) / `scm` (Module 4)
- **Waiting For / Blocked On:** Module 5 Physical Inventory `StockMove` ledger and valuation engine.
- **Status:** `[~]` Closed / Handed off to architecture boundary by design.
- **Description:** Sub-module 9.2 delivers digital storefront Available-to-Promise (`ATP = max(0, quantity_on_hand - quantity_allocated - safety_stock_buffer)`), multi-channel inventory broadcasting, and stock adjustment workflows. Physical warehouse stock ledger adjustments and FIFO/moving-average valuation posting are intentionally kept in `scm.StockAdjustment` and `inventory.StockMove` to avoid duplicate physical stock ledgers in NavERP.
- **Done When:** Module 5 Inventory or 9.5 Orders & Fulfillment binds digital allocations directly to physical `StockMove` reservations upon storefront order placement.

---

### GAP-ECOM-9.2-02: Live Outbound Marketplace API Sync Handshake
- **Owner:** `ecommerce` (Module 9) / `scm` (Module 4.19 Integration Hub)
- **Waiting For / Blocked On:** Client third-party developer marketplace credentials (Shopify Admin API, Amazon SP-API, Walmart Marketplace API) and outbound integration gateway runtime.
- **Status:** `[~]` Deferred to integration runtime phase.
- **Description:** `channelinventorysync_trigger` computes the exact channel-buffered allocation quantity and writes immutable audit logs and timestamps. In alignment with NavERP's offline testability and zero-outbound-HTTP architecture, live external network calls are simulated until client API keys and background worker queues (Celery/cron) are attached.
- **Done When:** Asynchronous worker tasks (Celery/Redis) consume `ChannelInventorySync` triggers and dispatch signed REST/GraphQL payloads to authorized marketplace endpoints.
