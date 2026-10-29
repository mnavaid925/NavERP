# Gap Register — Sub-module 9.3: Pricing & Promotion Engine (Module 9 eCommerce, `ecommerce`)

- **Sub-module:** 9.3 Pricing & Promotion Engine
- **Date:** 2026-10-29
- **Status Summary:** All review findings (`I1`, `M1`, `M2`) and view audit-logging defects resolved. 0 open defects. Architectural hand-offs documented below.

---

### GAP-ECOM-9.3-01: Runtime Cart & Checkout Application Pipeline Handoff
- **Owner:** `ecommerce` (Sub-module 9.4 Shopping Cart & Checkout)
- **Waiting For / Blocked On:** Sub-module 9.4 Shopping Cart & Checkout session and line-item evaluation pipeline.
- **Status:** `[~]` Deferred to sub-module 9.4 by architectural boundary design.
- **Description:** Sub-module 9.3 delivers the promotional data models, business logic methods (`calculate_price`, `calculate_discount`, `calculate_effective_price`), validation, and admin CRUD management consoles. Real-time application to anonymous/logged-in shopper cart sessions, line item promotional splits, coupon redemption checks, and stackability arbitration are executed within 9.4.
- **Done When:** Sub-module 9.4 cart engine calls `rule.calculate_price(item.price)` and `coupon.calculate_discount(cart.subtotal)` during active checkout sessions.

---

### GAP-ECOM-9.3-02: Live External Price Scraping Daemon & Headless Browser Runtime
- **Owner:** `ecommerce` (Module 9) / `core` (Background Worker Infrastructure)
- **Waiting For / Blocked On:** Background worker queue (Celery/cron) and headless web-scraping daemon (Playwright/Scrapy/proxy network).
- **Status:** `[~]` Deferred to background worker phase.
- **Description:** `competitorpricemonitor_sync` view triggers on-demand price verification, updates `last_scraped_at`, computes suggested repricing, and flags margin risks (`is_margin_risk`). Live automated scraping of dynamic JavaScript competitor sites (Amazon, Walmart) is simulated to maintain NavERP's strict offline zero-network testability.
- **Done When:** An asynchronous background worker periodically crawls `competitor_url`, extracts live product price and stock metadata, and updates `CompetitorPriceMonitor` records.

---

### GAP-ECOM-9.3-03: Customer Loyalty Tier Ledger Binding
- **Owner:** `crm` (Module 1) / `ecommerce` (Sub-module 9.7 Customer Accounts & Loyalty)
- **Waiting For / Blocked On:** Sub-module 9.7 (Customer Accounts & Loyalty) or CRM loyalty reward points ledger.
- **Status:** `[~]` Deferred to sub-module 9.7.
- **Description:** `DynamicPriceRule.loyalty_tier` and `CouponPromotion.loyalty_tier_required` provide five standardized tiers (`none`, `bronze`, `silver`, `gold`, `platinum`). In 9.3, tier restrictions are verified in models, forms, and views; dynamic derivation of a shopper's tier based on historical spend points will be wired in 9.7.
- **Done When:** 9.7 provides a `customer.loyalty_tier` resolver evaluated by the pricing engine during cart valuation.
