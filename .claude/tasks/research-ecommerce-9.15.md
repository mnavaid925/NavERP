# Research — Sub-module 9.15: Analytics & Business Intelligence (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.15 Analytics & Business Intelligence
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.14)
- **Research date:** 2026-11-01
- **Phase:** 1 Research only
- **Output file:** `.claude/tasks/research-ecommerce-9.15.md`

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.15 delivers the **Executive Sales Performance Dashboards, Customer Cohort Retention & Lifetime Value (LTV) Modeling, Product & Merchandising Profitability Analytics, Multi-Touch Marketing Attribution (MTA), and Real-Time Operational Funnel Health Monitoring** for the NavERP eCommerce platform.

In modern retail and direct-to-consumer (DTC) eCommerce, analytics and business intelligence have shifted from passive, monthly historical reporting into an active, real-time command center:
- **First-Party Data & Unified Source of Truth**: Post-iOS14 privacy restrictions and third-party cookie deprecation have broken native ad-network reporting (where Google, Meta, and TikTok double-count the same conversions). Modern eCommerce BI platforms (Triple Whale, Northbeam, Polar Analytics) unify first-party transactional data directly from the eCommerce database with marketing touchpoints to provide an unskewed, deduplicated source of truth.
- **Unit Economics & Contribution Margin**: Gross revenue is a vanity metric; profitability is sanity. Modern merchants require instant visibility into net margins after Cost of Goods Sold (COGS), discounts, returns, gateway fees, and advertising spend—calculating blended ROAS (Return On Ad Spend), MER (Marketing Efficiency Ratio), and CAC (Customer Acquisition Cost) Payback periods.
- **Longitudinal Cohort Retention & LTV Curves**: Customer acquisition costs have risen across all digital channels. Sustainable growth requires tracking customer cohorts over 30, 60, 90, 180, and 365 days to determine which initial products ("merchandise hooks") and acquisition channels generate high-retention, high-LTV repeat buyers versus one-and-done discount seekers (Peel Insights, RetentionX, Lifetimely).
- **Proactive Funnel & Operational Exception Alerts**: Rather than waiting for daily sales summaries, operations teams require real-time anomaly detection to identify checkout funnel drop-offs, payment gateway error spikes, or sudden conversion rate collapses within minutes rather than hours.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Financial Ledger & Margin Ownership (L29)**:
   - Module 9 eCommerce owns commercial storefront metric aggregation (Gross Merchandise Value, Storefront Net Sales, Storefront AOV, Blended Ad Spend / ROAS, Cart Abandonment rates).
   - Module 2 `accounting` remains the authoritative financial general ledger (no duplicate general ledger or double-entry bookkeeping tables in `ecommerce`). All COGS and gross margin calculations in 9.15 reference transactional unit prices, line item sub-totals, and product costs.
2. **Clear Sibling & Module Boundaries**:
   - **CRM 1.6 (`apps/crm/models/AnalyticsReporting/Dashboards.py`)**: B2B sales pipeline velocity, CRM lead stages, and enterprise account health dashboards.
   - **SCM 4.11 (`apps/scm/models/SupplyChainAnalytics/`)**: Warehouse fulfillment velocity, vendor lead times, PO receipt metrics, and manufacturing work-center efficiency.
   - **Sales 8.11 (`apps/sales/models/SalesAnalytics/`)**: Direct sales quota attainment, rep scorecards, and deal win/loss debriefs.
   - **Sub-module 9.4 (Cart & Checkout)**: Captures cart creation, items, and checkout session progression states. 9.15 reads these states to monitor checkout funnel drop-offs and abandonment rates.
   - **Sub-module 9.5 (Order Management)**: Authoritative source for orders (`EcommerceOrder`), line items (`EcommerceOrderLine`), and returns (`ReturnMerchandiseAuthorization`). 9.15 aggregates order data into historical KPI snapshots and attribution records.
   - **Sub-module 9.10 (Marketing Campaigns)**: Executes campaigns, tracking codes, and affiliate partnerships. 9.15 models multi-touch attribution (first-touch, last-touch, linear, position-based) and calculates channel ROAS/CAC.
3. **Multi-Tenancy & Data Isolation**:
   All KPI snapshots, cohort records, attribution models, and operational alerts inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation.
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
  - `"9.8"` is live: Personalization & Recommendation (`ESEG`, `EREC`, `EPEX`, `ESBE`)
  - `"9.9"` is live: Content Management System (`EPAG`, `EBLG`, `EBLK`, `EMED`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `EAFF`, `EARC`, `ESEO`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EMKV`, `EVPL`, `EVCS`, `EVPO`, `EVSO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESPL`, `ESUB`, `ESBX`, `ESRT`)
  - `"9.13"` is live: Reviews & User-Generated Content (`EPRV`, `EPQA`, `EUGC`, `ERVM`)
  - `"9.14"` is live: Customer Service & Support (`ESTK`, `EKBA`, `ECLM`, `ECSF`)
  - Sub-module `"9.15"` is the current target under construction.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.15 will add package directory `EcommerceAnalytics/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/analytics/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.15 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Unified customer party identity |
| `accounts.User` | `apps/accounts/models.py:52` | **Present** | Alert acknowledgment, dashboard owner, report author |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10` | **Present** | Primary transaction anchor for revenue, AOV, attribution |
| `ecommerce.EcommerceOrderLine` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:247` | **Present** | SKU sales velocity, merchandise margins, basket analysis |
| `ecommerce.CustomerAccountProfile` | `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py:11` | **Present** | Customer cohort anchor and LTV tracking |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Merchandising performance and product velocity |
| `ecommerce.StoreCategory` | `apps/ecommerce/models/ProductCatalog/StoreCategories.py:9` | **Present** | Category-level sales and initial-hook cohort grouping |
| `ecommerce.MarketingCampaign` | `apps/ecommerce/models/MarketingCampaign/MarketingCampaigns.py:10` | **Present** | Campaign ROI and multi-touch attribution linkage |
| `ecommerce.AffiliatePartner` | `apps/ecommerce/models/MarketingCampaign/AffiliatePartners.py:10` | **Present** | Partner referral attribution and conversion value |
| `ecommerce.Cart` | `apps/ecommerce/models/CartCheckout/Carts.py:11` | **Present** | Cart abandonment rate and checkout step drop-off |
| `ecommerce.CheckoutSession` | `apps/ecommerce/models/CartCheckout/CheckoutSessions.py:11` | **Present** | Checkout funnel step tracking and conversion analysis |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E '\b(EKPI|ECHT|EMAR|EALT)\b'`:
- `EKPI`: 0 collisions in repository (100% free)
- `ECHT`: 0 collisions in repository (100% free)
- `EMAR`: 0 collisions in repository (100% free)
- `EALT`: 0 collisions in repository (100% free)

---

## 3. Commercial Leaders Surveyed

### 1. Triple Whale (triplewhale.com)
- **Positioning**: The premier eCommerce business intelligence and attribution platform for high-growth direct-to-consumer (DTC) brands.
- **Key Capabilities**:
  - The Summary Board: Central real-time dashboard consolidating sales, ad spend, blended ROAS, and net profit.
  - Multi-touch attribution modeling (first-click, last-click, linear, time-decay, Triple Pixel).
  - Cohort analysis segmented by acquisition month, first-purchased product, category, and source channel.
  - LTV payback tracking with 30, 60, 90, 180, and 365-day milestone curves.
  - Blended MER (Marketing Efficiency Ratio) and blended CAC calculation across fragmented ad networks.
- **Feature Reference**: https://triplewhale.com/features

### 2. Glew.io (glew.io)
- **Positioning**: Multi-channel eCommerce analytics platform providing deep merchandise, inventory velocity, and customer segmentation intelligence.
- **Key Capabilities**:
  - Merchandise Profitability & COGS: Evaluates true gross profit by factoring in cost of goods sold.
  - Sales Velocity (Hot & Cold): Automatically classifies catalog into fast movers, slow movers, and dead stock.
  - Full-Price vs. Markdown Sell-Through: Analyzes margin impact of promotional discounting.
  - Product Bundling & Basket Affinity: Identifies items frequently bought together and high-AOV cross-sell pairs.
  - New vs. Repeat Customer Product Hooks: Discovers which SKUs successfully acquire loyal first-time customers.
- **Feature Reference**: https://glew.io/features

### 3. Daasity (daasity.com)
- **Positioning**: Data warehouse-native analytics platform transforming multi-channel eCommerce data into structured semantic explore layers.
- **Key Capabilities**:
  - Longitudinal Cohort Explore: Measures customer retention and cumulative spend indexed by "Months Since First Purchase".
  - Multi-Model Attribution: Granular order-level and customer-level attribution comparing first-touch, last-touch, and position-based models.
  - RFM (Recency, Frequency, Monetary) Customer Scoring: Integrates customer behavioral tiers directly into lifetime value modeling.
  - Repurchase Latency: Measures average days between first order and subsequent replenishment orders.
- **Feature Reference**: https://daasity.com/platform

### 4. Lifetimely (lifetimely.com)
- **Positioning**: eCommerce profit-tracking command center and predictive LTV analytics engine.
- **Key Capabilities**:
  - Real-Time P&L Dashboard: Tracks net margin in real time by subtracting COGS, shipping expenses, payment processing fees, and ad spend.
  - Dynamic Cohort Heatmaps: Visual color-coded matrix tracking cumulative revenue per customer over 12+ months.
  - CAC Payback Period: Pinpoints the exact month/day an acquisition cohort achieves break-even profitability.
  - Automated Profit Anomaly Alerts: Proactive triggers notifying teams of sudden margin erosion, CAC spikes, or conversion dips.
- **Feature Reference**: https://lifetimely.com

### 5. Polar Analytics (polaranalytics.com)
- **Positioning**: Full-stack DTC BI platform combining server-side event tracking, real-time dashboards, and retention metrics.
- **Key Capabilities**:
  - Real-time modular KPI metric cards, sparklines, and period-over-period comparisons (DoD, WoW, MoM, YoY).
  - Blended Marketing Efficiency Ratio (MER) and blended Customer Acquisition Cost (CAC) monitoring.
  - Product-level LTV: Identifies which SKUs yield the highest 12-month repeat purchase value.
  - Conversion rate tracking across device types (mobile vs. desktop) and marketing channels.
- **Feature Reference**: https://polaranalytics.com

### 6. Peel Insights (peelinsights.com)
- **Positioning**: Automated eCommerce retention and cohort analysis platform built for DTC subscription and retail brands.
- **Key Capabilities**:
  - Permanent Cohort Assignment: Freezes customers into acquisition cohorts (first order month) and maps all lifetime repurchases back to the origin group.
  - Retention Curves: Visualizes retention drop-off rates across 1 to 12 months post-acquisition.
  - Repurchase Rate (RPR): Tracks percentage of customers making 2nd, 3rd, and 4th purchases.
  - Segment-Specific Cohorts: Slices retention curves by discount codes used, acquisition campaigns, and product categories.
- **Feature Reference**: https://peelinsights.com

### 7. Metrilo (metrilo.com)
- **Positioning**: eCommerce growth platform uniting KPI analytics, customer retention cohorts, and conversion funnel tracking.
- **Key Capabilities**:
  - Real-Time Sales & Revenue KPI Dashboard: Filters out canceled and refunded orders to display true net run rate.
  - Multi-Step Checkout Conversion Funnels: Pinpoints exact drop-off points between cart view, shipping entry, payment details, and order confirmation.
  - Correlation & Affinity Reports: Cross-tabulates product views with ultimate order conversions.
- **Feature Reference**: https://metrilo.com/features

### 8. Littledata (littledata.io)
- **Positioning**: First-party data collection and server-side tracking engine fixing eCommerce attribution and funnel gaps.
- **Key Capabilities**:
  - Session Stitching: Connects initial marketing campaign parameters (UTMs, click IDs) to final server-side purchase events, eliminating "Direct / (none)" misattribution.
  - Full-Funnel Checkout Health: Step-by-step telemetry capturing product impressions, cart additions, checkout steps, transactions, and refunds.
  - Channel Attribution Reconciliation: Accurately maps revenue back to paid channels and affiliates.
- **Feature Reference**: https://littledata.io

### 9. Northbeam (northbeam.io)
- **Positioning**: Enterprise-grade eCommerce marketing attribution platform utilizing machine learning and multi-touch modeling.
- **Key Capabilities**:
  - Algorithmic Multi-Touch Attribution: Compares first-touch, last-touch, linear, time-decay, and position-based (U-shaped 40/20/40) attribution models.
  - Side-by-Side Model Comparison: Allows media buyers to evaluate ad spend performance under different attribution philosophies.
  - Media Mix Modeling (MMM): High-level top-down econometric modeling balancing bottom-up digital attribution.
  - Granular Campaign & Creative Attribution: Tracks downstream revenue generated by individual campaign codes and channels.
- **Feature Reference**: https://northbeam.io/features

### 10. RetentionX (retentionx.com)
- **Positioning**: Predictive customer intelligence and retention platform optimizing customer lifetime value.
- **Key Capabilities**:
  - Cohort Matrix Heatmaps: Visual green-to-red color grading showing monthly retention and repeat spend velocity.
  - LTV Milestones: Tracks cumulative LTV at 30, 60, 90, 180, and 365 days.
  - Early Churn Prediction ("Fight Churn"): Flags customer accounts exceeding their expected repurchase interval.
  - Repeat Purchase Rate (RPR) & Repurchase Latency: Measures customer purchase rhythm.
- **Feature Reference**: https://retentionx.com

---

## 4. Feature Catalog (Sub-Module 9.15 Only)

### 4.1 Sales Performance Dashboards
- **Periodic Storefront KPI Aggregation** — Computes and freezes key retail metrics (Gross Sales, Net Sales, Discounts, Refunds, Shipping Collected, Taxes, Net Orders, Units Sold, AOV, UPT) across daily, weekly, monthly, and quarterly intervals · seen in: Triple Whale, Lifetimely, Polar Analytics · priority: `table-stakes` · spine: new table `EcommerceKpiSnapshot` · buildable now.
- **Period-Over-Period Comparison Benchmarks** — Compares current period metrics against previous period (DoD, WoW, MoM) or previous year (YoY) with absolute and percentage variance indicators · seen in: Polar Analytics, Metrilo, Triple Whale · priority: `table-stakes` · spine: computed in view from `EcommerceKpiSnapshot` · buildable now.
- **Cart Abandonment & Checkout Funnel Trends** — Tracks total carts created, abandoned carts, checkout initiations, and abandonment rate (%) over time · seen in: Metrilo, Triple Whale, Littledata · priority: `table-stakes` · spine: aggregated from `ecommerce.Cart` and stored in `EcommerceKpiSnapshot` · buildable now.
- **Blended Commercial Efficiency Metrics** — Calculates Marketing Efficiency Ratio (MER = Net Sales / Ad Spend) and Blended ROAS to assess store health beyond siloed ad platform metrics · seen in: Triple Whale, Polar Analytics, Northbeam · priority: `common` · spine: stored on `EcommerceKpiSnapshot` · buildable now.
- **Customizable Multi-Tenant Dashboard View** — Responsive executive analytics view featuring metric highlight cards, trend sparklines, and channel breakdowns with quick date-range presets (Today, Yesterday, Last 7 Days, Month-to-Date, Last Month, Year-to-Date) · seen in: Triple Whale, Glew.io · priority: `table-stakes` · spine: view layer + template · buildable now.

### 4.2 Customer Analytics
- **Acquisition Month Cohort Retention Matrix** — Groups customers by the calendar month/period of their first purchase and tracks the percentage of those customers who return to make subsequent purchases in Months 1, 2, 3, 6, and 12 · seen in: Peel Insights, RetentionX, Lifetimely, Triple Whale · priority: `table-stakes` · spine: new table `CustomerCohortAnalysis` · buildable now.
- **Cumulative Lifetime Value (LTV) Milestone Curves** — Calculates average cumulative gross and net revenue generated per acquired customer at key lifecycle intervals: 30-day, 60-day, 90-day, 180-day, and 365-day milestones · seen in: Lifetimely, Triple Whale, RetentionX, Daasity · priority: `table-stakes` · spine: stored on `CustomerCohortAnalysis` · buildable now.
- **Repeat Purchase Rate (RPR) & Repurchase Latency** — Measures the overall proportion of buyers with 2+ orders and the average number of days elapsed between orders · seen in: Glew.io, Peel Insights, RetentionX · priority: `common` · spine: stored on `CustomerCohortAnalysis` · buildable now.
- **Channel & Category Hook Cohort Segmentation** — Allows slicing cohort retention and LTV curves by original acquisition channel (e.g. Paid Social vs. Organic) or initial entry product category · seen in: Peel Insights, Glew.io, Daasity · priority: `differentiator` · spine: `channel` choice + FK to `ecommerce.StoreCategory` on `CustomerCohortAnalysis` · buildable now.
- **Churn Rate & Dormancy Tracking** — Identifies cohort attrition rates and flags cohorts suffering severe retention drop-offs · seen in: RetentionX, Peel Insights · priority: `common` · spine: stored on `CustomerCohortAnalysis` · buildable now.

### 4.3 Product & Merchandising Analytics
- **Catalog Sales Velocity (ABC Classification)** — Classifies products into Class A (top 80% of revenue), Class B (next 15%), and Class C (bottom 5% slow movers / dead stock) · seen in: Glew.io, Metrilo · priority: `common` · spine: computed dynamically from `ecommerce.CatalogProduct` and `ecommerce.EcommerceOrderLine` in view · buildable now.
- **Product Gross Margin & Profitability Analysis** — Combines catalog selling prices with cost of goods sold (COGS) to calculate individual product and category gross margin dollars and gross margin percentage · seen in: Glew.io, Lifetimely · priority: `table-stakes` · spine: computed from `CatalogProduct.item` cost vs `EcommerceOrderLine.unit_price` · buildable now.
- **Best Sellers & High-Return SKUs** — Aggregates units sold, total revenue, return rates, and net margin per SKU to surface top revenue drivers versus profit-eroding products · seen in: Glew.io, Metrilo, Polar Analytics · priority: `table-stakes` · spine: computed from `ecommerce.EcommerceOrderLine` and `ecommerce.ReturnMerchandiseAuthorization` in view · buildable now.
- **First-Time Buyer "Hook" Products** — Analyzes which specific catalog products most frequently serve as the first purchase for new customers and evaluate the subsequent LTV of those customers · seen in: Glew.io, Triple Whale · priority: `differentiator` · spine: computed cross-linking `CustomerCohortAnalysis` and `CatalogProduct` · buildable now.

### 4.4 Marketing Attribution
- **Multi-Touch Attribution Journey Logging** — Records multi-touch customer interaction sequences (touchpoint 1, 2, 3... first-touch, nurturing, closing touch) connecting marketing campaigns, channels, and affiliates to orders · seen in: Northbeam, Triple Whale, Daasity, Littledata · priority: `table-stakes` · spine: new table `MarketingAttributionRecord` · buildable now.
- **Multi-Model Attribution Weighting** — Simultaneously calculates revenue attribution under four major attribution frameworks: First-Touch (100% to discovery touchpoint), Last-Touch (100% to closing touchpoint), Linear (equal distribution across all touchpoints), and Position-Based / U-Shaped (40% first, 40% last, 20% divided among middle) · seen in: Northbeam, Triple Whale, Daasity · priority: `differentiator` · spine: fields on `MarketingAttributionRecord` · buildable now.
- **Channel ROI, ROAS & CAC Estimation** — Attributes gross order revenue and marketing cost share to acquisition channels (paid search, paid social, organic, email, affiliate) to evaluate return on ad spend (ROAS) and customer acquisition cost (CAC) · seen in: Triple Whale, Polar Analytics, Northbeam · priority: `table-stakes` · spine: fields on `MarketingAttributionRecord` · buildable now.
- **Affiliate & Campaign Performance Linkage** — Links attribution records directly to built sub-module 9.10 entities (`MarketingCampaign`, `AffiliatePartner`) for end-to-end campaign tracking · seen in: Triple Whale, Daasity · priority: `table-stakes` · spine: FKs to `ecommerce.MarketingCampaign` and `ecommerce.AffiliatePartner` · buildable now.

### 4.5 Real-Time Operational Monitoring
- **Real-Time Funnel Health & Drop-Off Telemetry** — Monitors the continuous health of the eCommerce conversion funnel across key checkpoints: Cart Creation → Checkout Initiated → Shipping Selected → Payment Submitted → Order Placed · seen in: Metrilo, Littledata, Polar Analytics · priority: `table-stakes` · spine: new table `OperationalHealthAlert` · buildable now.
- **Automated Anomaly & Threshold Exception Rules** — Defines configurable monitoring rules triggering alerts when key metrics breach acceptable boundaries (e.g. checkout conversion rate drops below 1.5%, cart abandonment exceeds 80%, payment failure rate exceeds 5%, traffic velocity crashes) · seen in: Lifetimely (Profit Agent), Polar Analytics · priority: `common` · spine: fields on `OperationalHealthAlert` · buildable now.
- **Operational Incident Tracking & Acknowledgment** — Tracks alert lifecycle state (`active`, `acknowledged`, `investigating`, `resolved`, `silenced`), severity levels (`info`, `warning`, `high`, `critical`), trigger count, last-triggered timestamp, and assigned user acknowledgment · seen in: Datadog/Sentry retail monitoring, Lifetimely · priority: `common` · spine: fields on `OperationalHealthAlert` · buildable now.
- **Multi-Channel Alert Dispatch Configuration** — Configures intended dispatch channel for operational exceptions (in-app banner, email notification, webhook, SMS) · seen in: Lifetimely, Polar Analytics · priority: `table-stakes` · spine: field on `OperationalHealthAlert` · buildable now.

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To deliver a production-grade, comprehensive, and performant Analytics & Business Intelligence foundation that addresses all five bullets in `NavERP.md` 9.15, we recommend 4 tenant-scoped models under `apps/ecommerce/models/EcommerceAnalytics/`:

```
apps/ecommerce/models/EcommerceAnalytics/
├── __init__.py
├── EcommerceKpiSnapshots.py        # Model 1: EcommerceKpiSnapshot [EKPI-]
├── CustomerCohortAnalyses.py       # Model 2: CustomerCohortAnalysis [ECHT-]
├── MarketingAttributionRecords.py  # Model 3: MarketingAttributionRecord [EMAR-]
└── OperationalHealthAlerts.py       # Model 4: OperationalHealthAlert [EALT-]
```

### Model 1: `EcommerceKpiSnapshot` (Prefix: `EKPI`)
- **Role**: Frozen, periodic storefront sales performance and commercial efficiency snapshot across customizable time windows (daily, weekly, monthly, quarterly). Backs high-speed **Sales Performance Dashboards** and executive trend reports without running expensive multi-table scans on millions of orders.
- **Inheritance**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `number`: Auto-generated via `NUMBER_PREFIX = "EKPI"` (thread-safe, e.g. `EKPI-2026-00001`)
  - `period_type`: CharField with choices: `daily`, `weekly`, `monthly`, `quarterly`, `custom`
  - `start_date`: DateField
  - `end_date`: DateField
  - `channel`: CharField with choices: `all`, `web_desktop`, `web_mobile`, `marketplace`, `social_commerce`, `b2b`
  - `gross_sales`: DecimalField(max_digits=14, decimal_places=2, default=0.00)
  - `net_sales`: DecimalField(max_digits=14, decimal_places=2, default=0.00)
  - `discounts_total`: DecimalField(max_digits=12, decimal_places=2, default=0.00)
  - `refunds_total`: DecimalField(max_digits=12, decimal_places=2, default=0.00)
  - `shipping_collected`: DecimalField(max_digits=12, decimal_places=2, default=0.00)
  - `taxes_collected`: DecimalField(max_digits=12, decimal_places=2, default=0.00)
  - `total_orders`: PositiveIntegerField(default=0)
  - `units_sold`: PositiveIntegerField(default=0)
  - `average_order_value`: DecimalField(max_digits=10, decimal_places=2, default=0.00) (AOV)
  - `units_per_transaction`: DecimalField(max_digits=6, decimal_places=2, default=0.00) (UPT)
  - `total_visitors`: PositiveIntegerField(default=0)
  - `total_sessions`: PositiveIntegerField(default=0)
  - `conversion_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `cart_creations`: PositiveIntegerField(default=0)
  - `cart_abandonments`: PositiveIntegerField(default=0)
  - `cart_abandonment_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `new_customers_count`: PositiveIntegerField(default=0)
  - `repeat_customers_count`: PositiveIntegerField(default=0)
  - `cost_of_goods_sold`: DecimalField(max_digits=14, decimal_places=2, default=0.00) (COGS)
  - `gross_margin`: DecimalField(max_digits=14, decimal_places=2, default=0.00)
  - `gross_margin_percentage`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `total_ad_spend`: DecimalField(max_digits=12, decimal_places=2, default=0.00)
  - `blended_roas`: DecimalField(max_digits=8, decimal_places=2, default=0.00)
  - `marketing_efficiency_ratio`: DecimalField(max_digits=8, decimal_places=2, default=0.00) (MER)
  - `is_finalized`: BooleanField(default=False)
  - `notes`: TextField(blank=True)
- **FKs & Verification**:
  - `tenant`: `core.Tenant` (via `TenantNumbered`)

### Model 2: `CustomerCohortAnalysis` (Prefix: `ECHT`)
- **Role**: Longitudinal cohort retention matrix and lifetime value (LTV) milestone progression table. Backs **Customer Analytics** heatmaps, repurchase latency curves, and churn prevention.
- **Inheritance**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `number`: Auto-generated via `NUMBER_PREFIX = "ECHT"` (e.g. `ECHT-2026-00001`)
  - `cohort_name`: CharField(max_length=120) (e.g. "January 2026 Acquisition Cohort")
  - `cohort_month`: DateField(help_text="First calendar day of the cohort acquisition month")
  - `acquisition_channel`: CharField with choices: `all`, `organic_search`, `paid_search`, `paid_social`, `email_marketing`, `affiliate`, `referral`, `direct`, `marketplace`
  - `first_category`: ForeignKey to `ecommerce.StoreCategory` (null=True, blank=True, on_delete=models.SET_NULL, help_text="Initial entry-point product category for hook analysis")
  - `initial_customers_count`: PositiveIntegerField(default=0) (Cohort size at Month 0)
  - `initial_gross_revenue`: DecimalField(max_digits=14, decimal_places=2, default=0.00)
  - `initial_aov`: DecimalField(max_digits=10, decimal_places=2, default=0.00)
  - `m01_retention_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `m02_retention_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `m03_retention_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `m06_retention_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `m12_retention_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `cumulative_ltv_30d`: DecimalField(max_digits=10, decimal_places=2, default=0.00)
  - `cumulative_ltv_60d`: DecimalField(max_digits=10, decimal_places=2, default=0.00)
  - `cumulative_ltv_90d`: DecimalField(max_digits=10, decimal_places=2, default=0.00)
  - `cumulative_ltv_180d`: DecimalField(max_digits=10, decimal_places=2, default=0.00)
  - `cumulative_ltv_365d`: DecimalField(max_digits=10, decimal_places=2, default=0.00)
  - `repeat_purchase_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `average_days_between_orders`: DecimalField(max_digits=6, decimal_places=1, default=0.0)
  - `churn_rate`: DecimalField(max_digits=5, decimal_places=2, default=0.00) (%)
  - `status`: CharField with choices: `active`, `maturing`, `archived`
- **FKs & Verification**:
  - `tenant`: `core.Tenant` (via `TenantNumbered`)
  - `first_category`: `ecommerce.StoreCategory` (`apps/ecommerce/models/ProductCatalog/StoreCategories.py:9`)

### Model 3: `MarketingAttributionRecord` (Prefix: `EMAR`)
- **Role**: Multi-touch marketing attribution ledger connecting completed customer orders, marketing campaigns, touchpoints, and affiliate referrals. Backs **Marketing Attribution** (Channel ROI, ROAS, CAC, multi-touch comparison).
- **Inheritance**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `number`: Auto-generated via `NUMBER_PREFIX = "EMAR"` (e.g. `EMAR-2026-00001`)
  - `order`: ForeignKey to `ecommerce.EcommerceOrder` (on_delete=models.CASCADE, related_name="attribution_records")
  - `customer`: ForeignKey to `ecommerce.CustomerAccountProfile` (null=True, blank=True, on_delete=models.SET_NULL, related_name="attribution_touchpoints")
  - `campaign`: ForeignKey to `ecommerce.MarketingCampaign` (null=True, blank=True, on_delete=models.SET_NULL, related_name="attribution_records")
  - `affiliate`: ForeignKey to `ecommerce.AffiliatePartner` (null=True, blank=True, on_delete=models.SET_NULL, related_name="attribution_records")
  - `touchpoint_timestamp`: DateTimeField
  - `channel`: CharField with choices: `paid_search`, `paid_social`, `organic_search`, `email_marketing`, `sms`, `affiliate`, `influencer`, `referral`, `direct`
  - `source`: CharField(max_length=100) (e.g. "google", "meta", "tiktok", "klaviyo")
  - `medium`: CharField(max_length=100) (e.g. "cpc", "paid_social", "email", "banner")
  - `campaign_code`: CharField(max_length=120, blank=True)
  - `landing_page`: CharField(max_length=255, blank=True)
  - `touchpoint_position`: CharField with choices: `first_touch`, `intermediate`, `lead_creation`, `last_touch`, `single_touch`
  - `touchpoint_sequence`: PositiveIntegerField(default=1)
  - `attributed_revenue`: DecimalField(max_digits=12, decimal_places=2, default=0.00)
  - `first_touch_weight`: DecimalField(max_digits=5, decimal_places=4, default=0.0000)
  - `last_touch_weight`: DecimalField(max_digits=5, decimal_places=4, default=0.0000)
  - `linear_weight`: DecimalField(max_digits=5, decimal_places=4, default=0.0000)
  - `position_based_weight`: DecimalField(max_digits=5, decimal_places=4, default=0.0000)
  - `acquisition_cost`: DecimalField(max_digits=10, decimal_places=2, default=0.00) (CAC share)
  - `return_on_ad_spend`: DecimalField(max_digits=8, decimal_places=2, default=0.00) (ROAS)
  - `is_assisted_conversion`: BooleanField(default=False)
- **FKs & Verification**:
  - `tenant`: `core.Tenant` (via `TenantNumbered`)
  - `order`: `ecommerce.EcommerceOrder` (`apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10`)
  - `customer`: `ecommerce.CustomerAccountProfile` (`apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py:11`)
  - `campaign`: `ecommerce.MarketingCampaign` (`apps/ecommerce/models/MarketingCampaign/MarketingCampaigns.py:10`)
  - `affiliate`: `ecommerce.AffiliatePartner` (`apps/ecommerce/models/MarketingCampaign/AffiliatePartners.py:10`)

### Model 4: `OperationalHealthAlert` (Prefix: `EALT`)
- **Role**: Automated threshold anomaly detection and exception monitoring log for checkout funnel conversion, payment errors, and store traffic velocity. Backs **Real-Time Operational Monitoring**.
- **Inheritance**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `number`: Auto-generated via `NUMBER_PREFIX = "EALT"` (e.g. `EALT-2026-00001`)
  - `title`: CharField(max_length=150) (e.g. "Checkout Step 2 Drop-off Exceeds 65%")
  - `metric_type`: CharField with choices:
    - `checkout_conversion_drop`: "Checkout Conversion Drop"
    - `cart_abandonment_spike`: "Cart Abandonment Spike"
    - `payment_failure_rate`: "Payment Gateway Failure Rate Spike"
    - `traffic_velocity_drop`: "Storefront Traffic Drop"
    - `aov_crash`: "Average Order Value Collapse"
    - `stockout_velocity_surge`: "High-Demand Stockout Alert"
    - `page_latency_spike`: "Storefront Page Latency Spike"
  - `funnel_step`: CharField with choices:
    - `none`: "General Storefront"
    - `cart_view`: "Cart Page View"
    - `checkout_initiation`: "Checkout Initiation (Step 1)"
    - `shipping_selection`: "Shipping Method Selection (Step 2)"
    - `payment_submission`: "Payment Detail Submission (Step 3)"
    - `order_completion`: "Order Confirmation & Placement"
  - `severity`: CharField with choices: `info`, `warning`, `high`, `critical`
  - `threshold_operator`: CharField with choices:
    - `greater_than`: "Greater than (>)"
    - `less_than`: "Less than (<)"
    - `equal_to`: "Equal to (==)"
    - `percent_increase`: "Percent Increase (+%)"
    - `percent_decrease`: "Percent Decrease (-%)"
  - `threshold_value`: DecimalField(max_digits=10, decimal_places=2)
  - `current_value`: DecimalField(max_digits=10, decimal_places=2, default=0.00)
  - `evaluation_window_minutes`: PositiveIntegerField(default=60)
  - `status`: CharField with choices: `active`, `acknowledged`, `investigating`, `resolved`, `silenced`
  - `trigger_count`: PositiveIntegerField(default=1)
  - `last_triggered_at`: DateTimeField(auto_now=True)
  - `acknowledged_by`: ForeignKey to `settings.AUTH_USER_MODEL` (null=True, blank=True, on_delete=models.SET_NULL, related_name="acknowledged_ecom_alerts")
  - `acknowledged_at`: DateTimeField(null=True, blank=True)
  - `resolution_notes`: TextField(blank=True)
  - `notification_channel`: CharField with choices: `in_app`, `email`, `slack_webhook`, `sms`
- **FKs & Verification**:
  - `tenant`: `core.Tenant` (via `TenantNumbered`)
  - `acknowledged_by`: `accounts.User` (`apps/accounts/models.py:52`)

---

## 6. Belongs to Sibling Sub-Modules (Parked, Not Scoped Here)

- **9.4 Shopping Cart & Checkout**: Interactive customer checkout progression, cart recovery email firing triggers (`CartRecoveryRule`).
- **9.5 Order Management System**: Operational order status state transitions, physical warehouse fulfillment packing (`OrderFulfillment`), and return merchandise authorisations (`ReturnMerchandiseAuthorization`).
- **9.8 Personalization & Recommendation Engine**: Dynamic on-site product recommendation widgets and machine-learning shopper behavior event feeds (`ShopperBehaviorEvent`).
- **9.10 Marketing & Campaign Management**: Outbound email/SMS broadcast scheduling, affiliate partner commission payout ledgers (`AffiliateReferralConversion`).
- **9.11 Marketplace & Multi-Vendor**: Vendor-specific commission splits and sub-order accounting (`VendorPayout`).
- **9.12 Subscription Commerce**: Recurring billing cycles, dunning retries, and subscriber churn intervention offers (`SubscriptionRetentionAction`).
- **9.13 Reviews & UGC**: Sentiment analysis summaries and keyword tagging of public customer reviews (`ReviewSentimentSummary`).
- **9.14 Customer Support**: Support ticket SLA tracking, WISMO claim workflows, and customer satisfaction surveys (`CustomerSatisfactionSurvey`).
- **9.18 Fraud & Risk Management**: Automated transaction risk scoring, device fingerprinting, and chargeback dispute representment.
- **Module 2 Accounting**: Corporate General Ledger journal postings, asset depreciation, tax filings, and company-wide balance sheets.

---

## 7. Deferred (Later Passes / External Integrations)

- **Automated External Ad Platform Connectors (Meta Ads, Google Ads, TikTok Ads)**: Live automatic synchronization of ad spend via third-party OAuth Graph APIs. Fields for total ad spend and channel attribution exist now in `EcommerceKpiSnapshot` and `MarketingAttributionRecord`, but background third-party API polling workers are deferred to an integration pass.
- **Server-Side Conversion APIs (Meta CAPI, Google Enhanced Conversions)**: Direct outbound webhook dispatch of sanitized server-side purchase events to ad platforms.
- **Advanced Machine Learning Media Mix Modeling (MMM)**: Macro econometric regression solvers (e.g. Robyn, LightweightMMM) that run Python statistical packages against historical spend. The foundational touchpoint and spend matrices are preserved in 9.15.
- **Automated Slack/SMS Webhook Delivery Dispatcher**: Active outbound network calls to external Slack or Twilio endpoints when an `OperationalHealthAlert` is triggered. The notification channel field is modeled and in-app alerts are live immediately.
