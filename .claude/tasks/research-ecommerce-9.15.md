# Research — Sub-module 9.15: Analytics & Business Intelligence (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.15 Analytics & Business Intelligence
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.14)
- **Research date:** 2026-11-01
- **Phase:** 1 Research only
- **Output file:** `.claude/tasks/research-ecommerce-9.15.md`

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.15 delivers the **Analytics & Business Intelligence Engine** for the NavERP eCommerce platform, covering:
1. **Sales Performance Dashboards** — Revenue, average order value (AOV), conversion rate, units sold, discount impacts, and cart abandonment trend visualizations.
2. **Customer Analytics** — Cohort retention matrices, customer lifetime value (LTV) progression curves, churn rates, and repeat purchase timing behavior.
3. **Product & Merchandising Analytics** — Best sellers, slow movers, dead stock risk, sell-through velocity, and gross margin contribution analysis.
4. **Marketing Attribution** — Multi-touch attribution modeling (first-touch, last-touch, linear), channel ROI, campaign effectiveness, and customer acquisition cost (CAC) tracking.
5. **Real-Time Operational Monitoring** — Live checkout funnel conversion health, active cart velocity, order velocity anomaly detection, and operational alerting thresholds.

In high-growth digital commerce, operational decisions cannot rely on slow batch data warehouses or ad-hoc raw SQL over multi-million-row order tables. Leading enterprise eCommerce analytics architectures (Triple Whale, Glew, Daasity, Polar Analytics) combine:
- **Pre-Aggregated Time-Series Snapshots**: Nightly or hourly rollups of gross revenue, refunds, discounts, order counts, tax, and shipping amounts per store currency and date (`DailySalesSnapshot`), enabling sub-millisecond dashboard renders and Chart.js trendlines.
- **Cohort Analysis Cubes**: Period-over-period tracking of customer cohorts acquired in month $M$ across subsequent offsets $M+0, M+1, \dots, M+12$ (`CustomerCohortMetric`), recording customer retention percentages, cumulative net revenue, gross margin, and cumulative LTV.
- **Merchandising Performance Classifications**: Product and SKU-level aggregations (`ProductMerchandisingMetric`) calculating sell-through velocity, return rates, margin percentages, and categorizing inventory health into actionable merchandising tiers (`best_seller`, `core_performer`, `slow_mover`, `dead_stock`).
- **Attribution Touchpoints**: Granular session and referral tracking (`AttributionTouchpoint`) linking completed orders and conversion events to UTM parameters, marketing channels (`organic_search`, `paid_search`, `paid_social`, `email`, `affiliate`, `direct`, `referral`), campaigns, and attribution weights for true return on ad spend (ROAS) and CAC calculation.
- **Real-Time Operational Cockpit**: Live interactive monitoring console rendering checkout abandonment funnels, live shopping session traffic, and anomalous checkout failure warnings.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Catalog, Order, and Cart Integration (L36/L37)**:
   - Sales analytics aggregate data from **`ecommerce.EcommerceOrder`** (`EORD-`, 9.5) and **`ecommerce.EcommerceOrderLine`** (`9.5`).
   - Cart abandonment analytics calculate drop-offs directly from **`ecommerce.Cart`** (`ECRT-`, 9.4) and **`ecommerce.CheckoutSession`** (`ECKS-`, 9.4).
   - Merchandising analytics link directly to **`ecommerce.CatalogProduct`** (`EPRD-`, 9.1) and optional **`ecommerce.ProductVariant`** (`PVR-`, 9.1).
   - Marketing attribution links to **`ecommerce.MarketingCampaign`** (`EMCP-`, 9.10) and **`ecommerce.AffiliatePartner`** (`EAFF-`, 9.10).
   - Financial ledger entries remain strictly anchored in Module 2 `accounting` (`JournalEntry`, `Invoice`, `Bill`). eCommerce analytics displays revenue, discounts, and margins for merchandising intelligence without maintaining duplicate accounting ledgers (L29).
2. **Clear Sibling & Cross-Module Boundaries**:
   - **Module 10 (`apps/bi`)**: Enterprise-wide cross-functional Business Intelligence (cross-department OLAP data sources, SQL report builder, company-wide executive KPI cards). 9.15 provides domain-native eCommerce storefront telemetry, merchant cohort grids, channel attribution, and merchandise velocity consoles within `apps/ecommerce`.
   - **Sub-module 9.5 (`OrderManagement`)**: Owns order state transitions, fulfillment routing, and refund execution. 9.15 reads order rows to aggregate time-series revenue and performance snapshots.
   - **Sub-module 9.8 (`Personalization`)**: Owns real-time behavioral recommendation algorithms (`ShopperBehaviorEvent`). 9.15 consumes event streams for aggregate conversion rate and funnel drop-off analytics.
   - **Sub-module 9.10 (`MarketingCampaign`)**: Owns campaign creation and coupon generation. 9.15 provides multi-touch attribution and ROAS measurement.
3. **Multi-Tenancy & Data Isolation**:
   All 4 analytics models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation. All queries, aggregations, and dashboard views filter strictly on `tenant=request.tenant`.
4. **Base Class & Prefix Discipline**:
   All 4 models inherit from `TenantNumbered`, implementing thread-safe auto-number generation, audit timestamps, and strictly unique prefixes.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PRL`)
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`)
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`)
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`)
  - `"9.5"` is live: Order Management System (`EORD`, `EFUL`, `ERMA`, `EORT`)
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`)
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`)
  - `"9.8"` is live: Personalization & Recommendation Engine (`ESEG`, `EREC`, `EPEX`, `ESBE`)
  - `"9.9"` is live: Content Management System (`EPAG`, `EBLG`, `EMED`, `EBLK`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `EAFF`, `EARC`, `ESEO`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EMKV`, `EVPL`, `EVSO`, `EVPO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESPL`, `ESUB`, `ESBX`, `ESRT`)
  - `"9.13"` is live: Reviews & User-Generated Content (`EPRV`, `EPQA`, `EUGC`, `ERVM`)
  - `"9.14"` is live: Customer Service & Support (`ESTK`, `EKBA`, `ECLM`, `ECSF`)
  - Sub-module `"9.15"` currently has no `LIVE_LINKS` entries yet.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.15 will add package directory `AnalyticsBi/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/analytics_bi/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.15 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Customer identity for cohort LTV |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10` | **Present** | Order revenue and attribution source |
| `ecommerce.EcommerceOrderLine` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:247` | **Present** | Line item sales and merchandise velocity |
| `ecommerce.Cart` | `apps/ecommerce/models/CartCheckout/Carts.py:10` | **Present** | Cart abandonment rate tracking |
| `ecommerce.CheckoutSession` | `apps/ecommerce/models/CartCheckout/CheckoutSessions.py:10` | **Present** | Checkout funnel step drop-off analysis |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Target product for merchandising analytics |
| `ecommerce.ProductVariant` | `apps/ecommerce/models/ProductCatalog/ProductVariants.py:9` | **Present** | Variant-level margin and inventory turnover |
| `ecommerce.MarketingCampaign` | `apps/ecommerce/models/MarketingCampaign/MarketingCampaigns.py:9` | **Present** | Marketing campaign target for attribution |
| `ecommerce.AffiliatePartner` | `apps/ecommerce/models/MarketingCampaign/AffiliatePartners.py:9` | **Present** | Affiliate channel attribution |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in repository via `git grep -E '\b(EDSS|ECCM|EPMM|EATT)\b'`:
- `EDSS`: 0 collisions in repository (100% free)
- `ECCM`: 0 collisions in repository (100% free)
- `EPMM`: 0 collisions in repository (100% free)
- `EATT`: 0 collisions in repository (100% free)

---

## 3. Commercial Leaders Surveyed

### 1. Triple Whale (triplewhale.com)
- **Positioning**: The preeminent DTC analytics platform providing unified multi-channel attribution (Triple Pixel), blended ROAS, real-time sales summaries, and cohort retention grids.
- **Key Capabilities**: Summary dashboards visualizing net revenue, orders, AOV, blended ROAS, first-time vs returning customer ratio, customer cohort matrix mapping LTV progression over months 0 to 12+, first-click and last-click attribution models, and operational alerts on unexpected traffic drops or checkout anomalies.

### 2. Glew.io (glew.io)
- **Positioning**: Enterprise eCommerce business intelligence and merchandising analytics for multi-channel retailers.
- **Key Capabilities**: Product performance categorizations (best sellers, slow movers, high-margin, dead stock), inventory velocity and run-out projections, customer lifetime value and churn probability scoring, coupon profitability analysis, and automated daily performance digest summaries.

### 3. Daasity (daasity.com)
- **Positioning**: Modular data platform and analytics suite built specifically for DTC and omni-channel consumer brands.
- **Key Capabilities**: Comprehensive repurchase behavior analysis (time to second order distribution), cohort retention heatmap by acquisition month and first product purchased, channel-level CAC vs LTV ratios, and gross margin waterfalls deducting discounts, returns, and shipping subsidies.

### 4. Lifetimely (lifetimely.io)
- **Positioning**: Specialized eCommerce customer analytics and LTV forecasting engine for Shopify brands.
- **Key Capabilities**: Cohort LTV curves charting cumulative gross profit and order frequency over 24 months, CAC payback period visualization, repurchase rate benchmarks, and order count distribution (1-time buyers vs repeat brand loyalists).

### 5. Polar Analytics (polaranalytics.com)
- **Positioning**: Full-stack modern BI platform connecting marketing ad channels, Shopify storefronts, and warehouse data into real-time health dashboards.
- **Key Capabilities**: Real-time sales ticker with live order velocity, checkout conversion funnel monitoring (sessions → product views → add-to-cart → checkout started → completed), conversion drop-off alerts, and multi-touch marketing attribution.

### 6. Metrilo (metrilo.com)
- **Positioning**: Growth and retention analytics suite featuring real-time eCommerce sales tracking and customer lifecycle intelligence.
- **Key Capabilities**: Funnel conversion visualization, product cross-sell affinity analysis, retention cohorts with repeat purchase frequency, and revenue breakdown by acquisition channel.

### 7. Peel Insights (peelinsights.com)
- **Positioning**: Automated post-purchase analysis platform delivering automated cohort breakdowns and retention metrics.
- **Key Capabilities**: Automatic discovery of top-performing acquisition channels, subscription vs one-time cohort decay curves, average days between orders, and high-LTV customer segment identification.

### 8. Littledata (littledata.io)
- **Positioning**: eCommerce server-side event tracking and attribution audit engine.
- **Key Capabilities**: End-to-end checkout funnel step validation, marketing touchpoint capture, attribution integrity verification, and real-time transaction error monitoring.

---

## 4. Feature Catalog (Sub-Module 9.15 Only)

### 4.1 Sales Performance Dashboards
- **Daily Sales Aggregation Snapshot** — Automated or triggerable pre-aggregated daily sales summaries recording gross sales, net sales, order counts, AOV, units sold, discount totals, returns/refunds, tax, and shipping per currency.
  - *Seen in:* Triple Whale, Glew, Daasity, Polar Analytics
  - *Priority:* Table-stakes
  - *Spine:* Implemented via `DailySalesSnapshot` model (`EDSS-`).
  - *Buildable now:* Yes, with live aggregation view action.
- **AOV & Conversion Trend Visualizations** — Historical time-series charts displaying Average Order Value fluctuations, discount depth percentage, and order velocity.
  - *Seen in:* Triple Whale, Metrilo
  - *Priority:* Table-stakes
  - *Spine:* Rendered via Chart.js on `DailySalesSnapshot` and live `EcommerceOrder`.
  - *Buildable now:* Yes.
- **Cart Abandonment Velocity & Recovery Rate** — Tracking total abandoned carts versus recovered checkouts, calculating abandoned revenue and recovery conversion rate.
  - *Seen in:* Polar Analytics, Metrilo
  - *Priority:* Table-stakes
  - *Spine:* Aggregated from `ecommerce.Cart` (`ECRT-`) and `ecommerce.CheckoutSession` (`ECKS-`).
  - *Buildable now:* Yes.

### 4.2 Customer Analytics
- **Cohort Retention Matrix** — Tracking customer cohorts grouped by acquisition month/quarter across subsequent period offsets (Month 0 to Month 12+), calculating retained active shoppers, retention percentage, and cumulative revenue.
  - *Seen in:* Triple Whale, Lifetimely, Daasity, Peel Insights
  - *Priority:* Table-stakes
  - *Spine:* Implemented via `CustomerCohortMetric` model (`ECCM-`).
  - *Buildable now:* Yes, with recalculation engine.
- **Customer Lifetime Value (LTV) Progression Curves** — Cumulative gross margin and net spend per customer over time, enabling calculation of CAC payback periods.
  - *Seen in:* Lifetimely, Daasity, Glew
  - *Priority:* Differentiator
  - *Spine:* Stored on `CustomerCohortMetric` (`ECCM-`).
  - *Buildable now:* Yes.
- **Repeat Purchase Behavior & Churn Risk** — Tracking time between consecutive orders (days to repeat purchase), order frequency distribution, and customer lapse intervals.
  - *Seen in:* Peel Insights, Daasity
  - *Priority:* Common
  - *Spine:* Calculated across `CustomerAccountProfile` and `EcommerceOrder`.
  - *Buildable now:* Yes.

### 4.3 Product & Merchandising Analytics
- **Merchandising Performance Snapshot** — SKU and product-level intelligence capturing units sold, gross sales, return rate %, cost of goods sold, gross margin %, view counts, and conversion rate.
  - *Seen in:* Glew, Daasity
  - *Priority:* Table-stakes
  - *Spine:* Implemented via `ProductMerchandisingMetric` model (`EPMM-`).
  - *Buildable now:* Yes.
- **Inventory Velocity Classification Tiers** — Actionable merchandising categorization classifying products into `best_seller` (top 20% velocity), `core_performer`, `slow_mover` (low turnover), and `dead_stock` (no sales > 90 days).
  - *Seen in:* Glew, Triple Whale
  - *Priority:* Common
  - *Spine:* Categorical choice field and algorithm on `ProductMerchandisingMetric`.
  - *Buildable now:* Yes.
- **Return & Refund Drag Analysis** — Identifying products with abnormally high refund/return rates dragging down category profitability.
  - *Seen in:* Daasity, Glew
  - *Priority:* Common
  - *Spine:* `return_rate_pct` and `refund_amount` on `ProductMerchandisingMetric`.
  - *Buildable now:* Yes.

### 4.4 Marketing Attribution
- **Multi-Touch Marketing Attribution Touchpoints** — Logging customer acquisition and conversion touchpoints with channel categorization (`organic_search`, `paid_search`, `paid_social`, `email`, `affiliate`, `direct`, `referral`), campaign references, UTM parameters, and attribution models (`first_touch`, `last_touch`, `linear`, `time_decay`).
  - *Seen in:* Triple Whale (Triple Pixel), Polar Analytics, Littledata
  - *Priority:* Table-stakes
  - *Spine:* Implemented via `AttributionTouchpoint` model (`EATT-`).
  - *Buildable now:* Yes.
- **Channel ROAS & CAC Analysis** — Calculating attributed revenue versus marketing expenditure or estimated customer acquisition cost per channel.
  - *Seen in:* Triple Whale, Daasity, Polar Analytics
  - *Priority:* Differentiator
  - *Spine:* `attributed_revenue` and `estimated_cac` on `AttributionTouchpoint`.
  - *Buildable now:* Yes.

### 4.5 Real-Time Operational Monitoring
- **Real-Time Analytics & Operational Cockpit** — Live management console displaying today's real-time sales ticker, active shopping carts, recent order velocity, and checkout funnel conversion stages.
  - *Seen in:* Polar Analytics, Triple Whale
  - *Priority:* Table-stakes
  - *Spine:* Dynamic view console aggregating live `Cart`, `CheckoutSession`, and `EcommerceOrder`.
  - *Buildable now:* Yes.
- **Checkout Funnel Drop-Off Health** — Visualizing conversion drop-off percentages from cart creation → customer info → shipping step → payment step → order placed.
  - *Seen in:* Metrilo, Littledata
  - *Priority:* Common
  - *Spine:* Aggregated dynamically from `CheckoutSession.current_step`.
  - *Buildable now:* Yes.

---

## 5. Recommended Build Scope (4 Models for Sub-Module 9.15)

To deliver comprehensive analytics and business intelligence while staying strictly within the 1–4 model build unit:

### 1. `DailySalesSnapshot` [`EDSS-`]
- **Purpose**: Pre-aggregated historical daily sales snapshot capturing top-line revenue, order counts, AOV, and margin components for high-speed reporting and Chart.js dashboards.
- **Key Fields**:
  - `snapshot_date` (`DateField`, `db_index=True`)
  - `currency` (`CharField`, max_length=3, default="USD")
  - `gross_sales` (`DecimalField`, 14, 2, default=0.00)
  - `discounts_total` (`DecimalField`, 14, 2, default=0.00)
  - `refunds_total` (`DecimalField`, 14, 2, default=0.00)
  - `net_sales` (`DecimalField`, 14, 2, default=0.00)
  - `shipping_collected` (`DecimalField`, 14, 2, default=0.00)
  - `taxes_collected` (`DecimalField`, 14, 2, default=0.00)
  - `cost_of_goods_sold` (`DecimalField`, 14, 2, default=0.00)
  - `gross_profit` (`DecimalField`, 14, 2, default=0.00)
  - `orders_count` (`PositiveIntegerField`, default=0)
  - `units_sold` (`PositiveIntegerField`, default=0)
  - `average_order_value` (`DecimalField`, 10, 2, default=0.00)
  - `carts_created` (`PositiveIntegerField`, default=0)
  - `carts_abandoned` (`PositiveIntegerField`, default=0)
  - `conversion_rate_pct` (`DecimalField`, 5, 2, default=0.00)
  - `is_finalized` (`BooleanField`, default=False)
- **FKs**: Inherits `TenantNumbered` (`tenant`). Unique together per `(tenant, snapshot_date, currency)`.
- **Key Methods**: `recalculate_from_orders(tenant, date)`.

### 2. `CustomerCohortMetric` [`ECCM-`]
- **Purpose**: Period-over-period cohort retention and LTV tracking cube by acquisition month and period offset.
- **Key Fields**:
  - `cohort_month` (`DateField`, `db_index=True` — e.g. 2026-01-01 for Jan 2026 cohort)
  - `period_offset_months` (`PositiveSmallIntegerField`, default=0 — 0 for month 0, 1 for month 1...)
  - `initial_cohort_size` (`PositiveIntegerField`, default=0 — total new customers acquired in cohort month)
  - `active_customers` (`PositiveIntegerField`, default=0 — repeat purchasing customers in offset month)
  - `retention_rate_pct` (`DecimalField`, 5, 2, default=0.00)
  - `cohort_orders_count` (`PositiveIntegerField`, default=0)
  - `cumulative_gross_revenue` (`DecimalField`, 14, 2, default=0.00)
  - `cumulative_net_revenue` (`DecimalField`, 14, 2, default=0.00)
  - `cumulative_margin` (`DecimalField`, 14, 2, default=0.00)
  - `cumulative_ltv_per_customer` (`DecimalField`, 10, 2, default=0.00)
  - `churn_rate_pct` (`DecimalField`, 5, 2, default=0.00)
  - `acquisition_channel_tag` (`CharField`, max_length=64, blank=True, default="")
- **FKs**: Inherits `TenantNumbered` (`tenant`). Unique together per `(tenant, cohort_month, period_offset_months, acquisition_channel_tag)`.
- **Key Methods**: `recalculate_cohort(tenant, cohort_month, offset)`.

### 3. `ProductMerchandisingMetric` [`EPMM-`]
- **Purpose**: Product and variant-level sales velocity, inventory turnover, margin contribution, and catalog health classification.
- **Key Fields**:
  - `product` (`ForeignKey('ecommerce.CatalogProduct')`, `on_delete=CASCADE`, `related_name='merchandising_metrics'`)
  - `variant` (`ForeignKey('ecommerce.ProductVariant')`, `null=True`, `blank=True`, `on_delete=SET_NULL`, `related_name='merchandising_metrics'`)
  - `period_start` (`DateField`)
  - `period_end` (`DateField`)
  - `velocity_tier` (`CharField`, max_length=20, choices: `best_seller`, `core_performer`, `slow_mover`, `dead_stock`, default="core_performer")
  - `units_sold` (`PositiveIntegerField`, default=0)
  - `gross_revenue` (`DecimalField`, 14, 2, default=0.00)
  - `cost_of_goods` (`DecimalField`, 14, 2, default=0.00)
  - `gross_margin_pct` (`DecimalField`, 5, 2, default=0.00)
  - `refunds_count` (`PositiveIntegerField`, default=0)
  - `return_rate_pct` (`DecimalField`, 5, 2, default=0.00)
  - `page_views_count` (`PositiveIntegerField`, default=0)
  - `add_to_cart_count` (`PositiveIntegerField`, default=0)
  - `conversion_rate_pct` (`DecimalField`, 5, 2, default=0.00)
  - `inventory_turnover_ratio` (`DecimalField`, 6, 2, default=0.00)
- **FKs**: Inherits `TenantNumbered` (`tenant`).
- **Key Methods**: `classify_velocity()`.

### 4. `AttributionTouchpoint` [`EATT-`]
- **Purpose**: Marketing attribution event recording customer acquisition touchpoints, channel grouping, UTM parameters, and order attribution weighting.
- **Key Fields**:
  - `order` (`ForeignKey('ecommerce.EcommerceOrder')`, `null=True`, `blank=True`, `on_delete=SET_NULL`, `related_name='attribution_touchpoints'`)
  - `cart` (`ForeignKey('ecommerce.Cart')`, `null=True`, `blank=True`, `on_delete=SET_NULL`, `related_name='attribution_touchpoints'`)
  - `channel_type` (`CharField`, max_length=32, choices: `organic_search`, `paid_search`, `paid_social`, `email`, `affiliate`, `direct`, `referral`, `influencer`, `other`)
  - `attribution_model` (`CharField`, max_length=20, choices: `first_touch`, `last_touch`, `linear`, `time_decay`, default="last_touch")
  - `campaign` (`ForeignKey('ecommerce.MarketingCampaign')`, `null=True`, `blank=True`, `on_delete=SET_NULL`, `related_name='attribution_touchpoints'`)
  - `affiliate` (`ForeignKey('ecommerce.AffiliatePartner')`, `null=True`, `blank=True`, `on_delete=SET_NULL`, `related_name='attribution_touchpoints'`)
  - `utm_source` (`CharField`, max_length=100, blank=True, default="")
  - `utm_medium` (`CharField`, max_length=100, blank=True, default="")
  - `utm_campaign` (`CharField`, max_length=100, blank=True, default="")
  - `touchpoint_timestamp` (`DateTimeField`)
  - `attribution_weight` (`DecimalField`, 5, 4, default=1.0000)
  - `attributed_revenue` (`DecimalField`, 14, 2, default=0.00)
  - `estimated_cac` (`DecimalField`, 10, 2, default=0.00)
  - `landing_page_url` (`CharField`, max_length=255, blank=True, default="")
  - `referrer_url` (`CharField`, max_length=255, blank=True, default="")
- **FKs**: Inherits `TenantNumbered` (`tenant`).

---

## 6. Real-Time Operational Cockpit View & Dashboards

In addition to the 4 models, Sub-module 9.15 provides an interactive **Analytics & BI Management Console** (`/ecommerce/analytics/cockpit/`):
- **Live Sales & Performance Cards**: Today's revenue, order velocity, real-time AOV, and cart recovery rate.
- **Funnel Drop-Off Stages**: Interactive visual stage pipeline (Sessions → Active Carts → Checkout Initiated → Payment Completed).
- **Chart.js Visualizations**: Daily revenue trendline, cohort retention heatmap table, and marketing channel revenue distribution doughnut.
- **Ad-Hoc Snapshot & Recalculate Actions**: One-click manual triggers to generate today's daily snapshot or recalculate customer cohort matrices.

---

## 7. Belongs to Sibling Sub-Modules (Parked)
- Mobile app analytics and PWA offline telemetry → Parked for Sub-module 9.16 (Mobile Commerce).
- B2B company account spend analytics and volume contract reporting → Parked for Sub-module 9.17 (B2B & Wholesale Commerce).
- Cross-module company-wide financial general ledger OLAP analytics → Owned by Module 10 (`apps/bi`) and Module 2 (`apps/accounting`).

---

## 8. Deferred Features (Future Enhancements)
- External third-party Google Analytics 4 (GA4) / Meta Conversions API (CAPI) direct server sync → Deferred for integration layer.
- Predictive machine learning churn forecasting models → Reuses Module 23 (`apps/ai`) when invoked.
- Multi-currency real-time FX spot rate conversion on historical snapshots → Handled via Module 2 `accounting.Currency`.
