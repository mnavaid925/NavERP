# Gaps Register: eCommerce Sub-module 9.15 (Analytics & Business Intelligence)

> **Context**: Sub-module 9.15 delivers daily sales performance snapshots (`DailySalesSnapshot`), customer cohort retention curves and cumulative LTV metrics (`CustomerCohortMetric`), product & merchandising economics with velocity tiers (`ProductMerchandisingMetric`), multi-touch marketing attribution models (`AttributionTouchpoint`), and an executive real-time operational monitoring dashboard (`AnalyticsCockpit`).
> All core CRUD operations, multi-tenancy isolation, sargable query optimization, compound unique constraint validations, recalculation engines, and role-based permissions are implemented, reviewed by 6 serial reviewers, burned down with 0 open findings, tested (37 dedicated tests in 9.15, 1,257 green tests across the full eCommerce test suite), and documented.

---

### GAP-9.15-01: External BI & Data Warehouse Sync (Snowflake / BigQuery / Databricks)
- **Owner**: `ecommerce` / Module 10 (`apps/bi`) Integration Agent
- **Waiting For / Blocked On**: Module 10 (Business Intelligence) ELT pipeline and enterprise data lake connector infrastructure.
- **Status**: `- [~]` Deferred (Historical snapshots and cohort metrics aggregate natively in relational database tables).
- **Done When**: Scheduled ELT pipelines extract and stream `DailySalesSnapshot`, `CustomerCohortMetric`, and `ProductMerchandisingMetric` partitions to cloud data warehouses for enterprise-wide OLAP reporting.

### GAP-9.15-02: Real-Time WebSocket Streaming for Executive Analytics Cockpit
- **Owner**: `ecommerce` / Frontend / Realtime Messaging Agent
- **Waiting For / Blocked On**: Platform-wide Django Channels / ASGI Redis message broker deployment.
- **Status**: `- [~]` Deferred (Analytics Cockpit aggregates live 24h operational telemetry via fast indexed, sargable ORM queries on page load).
- **Done When**: Storefront visitor sessions, live cart creations, and conversion funnel step movements broadcast over WebSocket channels into the Cockpit with live UI counter increments.

### GAP-9.15-03: Predictive LTV & Machine Learning Churn Forecasting
- **Owner**: `ecommerce` / Module 23 (`apps/ai`) Machine Learning Agent
- **Waiting For / Blocked On**: Module 23 (AI & Intelligent Automation) predictive model training and inference runtime.
- **Status**: `- [~]` Deferred (Customer cohort retention curves and cumulative LTV are computed deterministically from observed order histories).
- **Done When**: Supervised ML models ingest cohort purchase cadences and predict individualized 12-month forward LTV, repeat probability, and churn risk scores.

### GAP-9.15-04: Server-Side Conversions API (CAPI) Ad Network Synchronization
- **Owner**: `ecommerce` / Marketing Integration Agent
- **Waiting For / Blocked On**: External ad platform credentials (Google Enhanced Conversions, Meta CAPI, TikTok Events API).
- **Status**: `- [~]` Deferred (Attribution touchpoints compute multi-touch channel credit internally across first-touch, last-touch, linear, time-decay, and position-based models).
- **Done When**: Order completions automatically trigger server-to-server HTTP conversions payload dispatches to external ad network APIs with hashed customer identifiers and attributed revenue.
