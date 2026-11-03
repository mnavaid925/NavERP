# Research — Sub-module 9.19: Integration & API Ecosystem (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.19 Integration & API Ecosystem
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.18)
- **Research date:** 2026-11-03
- **Phase:** 1 Research only
- **Output file:** `.claude/tasks/research-ecommerce-9.19.md`

---

## 1. Repo State Checked First

### 1.1 Navigation & App Tree State
- **`apps/core/navigation.py` status:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PRL`)
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`)
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`)
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`)
  - `"9.5"` is live: Order Management System (`EORD`, `EFUL`, `ERMA`, `EORT`)
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`)
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`)
  - `"9.8"` is live: Personalization & Recommendation Engine (`EREC`, `EUSR`, `EACF`, `ECST`)
  - `"9.9"` is live: Content Management System (`ECMP`, `EBLP`, `EBNR`, `ENAV`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `ECPN`, `EABT`, `EADF`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EVND`, `EVPL`, `EVST`, `EVCO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESBP`, `ECSB`, `ESBO`, `ESBD`)
  - `"9.13"` is live: Reviews & User-Generated Content (`EPRV`, `EQNA`, `EUGC`, `ERVR`)
  - `"9.14"` is live: Customer Service & Support (`ECST`, `ELCS`, `ESKB`, `ESLA`)
  - `"9.15"` is live: Analytics & Business Intelligence (`EATT`, `ECMT`, `EPMM`, `ECKM`)
  - `"9.16"` is live: Mobile Commerce (`EMAC`, `EMDR`, `EMPC`, `EMLR`)
  - `"9.17"` is live: B2B & Wholesale Commerce (`EBCA`, `EBCU`, `EBQR`, `EBQT`)
  - `"9.18"` is live: Fraud & Risk Management (`EFRR`, `ETRA`, `ECBD`, `EASA`)
  - `"9.19"`: Target sub-module (Integration & API Ecosystem) — unbuilt, next in sequence.

### 1.2 Sibling Models Available to FK (Verified in `apps/ecommerce/models/`)
- `EcommerceOrder` (`apps/ecommerce/models/OrderManagement/EcommerceOrders.py`)
- `CatalogProduct` & `ProductVariant` (`apps/ecommerce/models/ProductCatalog/CatalogProducts.py`, `ProductVariants.py`)
- `FulfillmentCenter` (`apps/ecommerce/models/InventoryStock/FulfillmentCenters.py`)
- `PaymentMethodConfig` (`apps/ecommerce/models/CartCheckout/PaymentMethods.py`)
- `ShippingMethodConfig` (`apps/ecommerce/models/CartCheckout/ShippingMethods.py`)
- `CustomerAccountProfile` (`apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py`)
- `MarketplaceVendor` (`apps/ecommerce/models/Marketplace/MarketplaceVendors.py`)

### 1.3 Spine Entities Verified to Exist (Grep Evidence)
- `apps/core/models/`:
  - `Tenant`: verified (`apps/core/models/Tenant.py`)
  - `Party`: verified (`apps/core/models/Party.py`)
  - `User`: verified via `django.conf.settings.AUTH_USER_MODEL`
  - `AuditLog`: verified (`apps/core/models/AuditLog.py`)
- `apps/accounting/models/`:
  - `Currency`: verified (`apps/accounting/models/GeneralLedger/Currencies.py`)
  - `Invoice`: verified (`apps/accounting/models/AccountsReceivable/Invoices.py`)
  - `Payment`: verified (`apps/accounting/models/CashBank/Payments.py`)

### 1.4 Architectural Boundary Invariants (L28, L29, L36, L37)
1. **Multi-Tenancy & Data Isolation (L28, L36)**:
   - All Integration & API models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation.
   - Connector profiles, credentials, sync jobs, and webhook subscriptions are strictly partitioned per tenant.
2. **Financial Ledger & Payment Ownership (L29)**:
   - Payment gateway connectors configure external API connectivity and sync payment status events, but Module 2 `accounting` remains the authoritative financial ledger (`Invoice`, `Payment`, `JournalEntry`).
3. **Core Spine & Security Integration (L28)**:
   - Integrations link to `core.Party` for partner/client identity.
   - Operational interventions and key generation log through `core.AuditLog`.
   - Credentials use SHA-256 hash digests for verification and masked strings for display.

---

## 2. Leaders Surveyed (with Source Links)

1. **Shopify (Flow, Admin API, Storefront API & Webhook Subscriptions)**
   - *Global benchmark for eCommerce developer platforms, headless APIs, and app connectors.*
   - Sources: [Shopify Webhook Subscriptions](https://shopify.dev/docs/api/admin-graphql/latest/mutations/webhookSubscriptionCreate), [Shopify Storefront API](https://shopify.dev/docs/api/storefront), [Shopify Connectors & Flow](https://shopify.dev/docs/apps/build/flow/connectors).
   - Key capabilities: Granular OAuth permission scopes (`read_products`, `write_orders`), HMAC-SHA256 signature verification headers, leaky-bucket rate limiting, dual-tier token architecture (public storefront access tokens vs private server admin keys), exponential backoff on webhook failures.

2. **commercetools (commercetools Connect & Subscriptions)**
   - *Pioneer of MACH (Microservices, API-first, Cloud-native, Headless) enterprise commerce.*
   - Sources: [commercetools Connect](https://docs.commercetools.com/connect), [commercetools Subscriptions](https://docs.commercetools.com/api/projects/subscriptions), [commercetools API Extensions](https://docs.commercetools.com/api/projects/api-extensions).
   - Key capabilities: Event-driven asynchronous Subscriptions (pushing to webhooks or cloud queues on resource mutations), pre-packaged connectors deployed via `connect.yaml`, synchronous API Extensions for real-time payload interception, decoupled serverless execution.

3. **Celigo (integrator.io)**
   - *Leading eCommerce-to-ERP integration platform specializing in NetSuite, SAP, and Dynamics sync.*
   - Sources: [Celigo integrator.io Core](https://www.celigo.com/platform/integrator-io/), [Celigo Error Management & Retries](https://docs.celigo.com/hc/en-us/articles/360046182572-Manage-errors-in-integrator-io).
   - Key capabilities: Bidirectional order-to-cash flows, dedicated record-level error management queue with inline payload editing and retry, automatic rate-limit throttling and backoff, scheduled batch runs with granular processed/failed metrics.

4. **Patchworks**
   - *Enterprise retail and eCommerce iPaaS connecting storefronts to ERPs (SAP, NetSuite, Dynamics 365, Sage) and 3PLs.*
   - Sources: [Patchworks Platform Overview](https://www.wearepatchworks.com/platform/), [Patchworks Connectors](https://www.wearepatchworks.com/connectors/).
   - Key capabilities: Pre-built connector marketplace for retail stacks, bidirectional inventory level sync to prevent overselling, dispatch tracking updates back-synced from 3PLs, automated alert triggers on sync failure.

5. **Commerce Layer**
   - *API-first transactional commerce engine for global multi-market and headless architectures.*
   - Sources: [Commerce Layer External Gateways](https://docs.commercelayer.io/core/external-resources), [Commerce Layer Webhooks](https://docs.commercelayer.io/core/v/api-reference/webhooks).
   - Key capabilities: Clean external endpoint delegation for custom payment gateways and shipping rate calculators, `X-CommerceLayer-Signature` HMAC verification, built-in circuit breaker to bypass failing endpoints and protect checkout flow.

6. **Alloy Automation**
   - *Embedded eCommerce automation and iPaaS connecting storefronts to ERPs, marketing, and logistics.*
   - Sources: [Alloy Automation Platform](https://www.runalloy.com/), [Alloy Stream Data Connector](https://support.runalloy.com/docs/stream-data-connector).
   - Key capabilities: Event triggers (Order Placed, Inventory Depleted), multi-system fanout (ERP + WMS + Klaviyo in one pipeline), unified OAuth authentication, webhook retries and resiliency.

7. **BigCommerce (Multi-Storefront APIs & Channel Manager)**
   - *Open SaaS eCommerce leader with native REST/GraphQL APIs and enterprise ERP/shipping connectors.*
   - Sources: [BigCommerce Webhooks API](https://developer.bigcommerce.com/docs/rest-management/webhooks), [BigCommerce API Accounts & Tokens](https://developer.bigcommerce.com/docs/start/authentication/api-accounts).
   - Key capabilities: Channel-specific API client bindings, granular per-resource OAuth scopes (`Orders`, `Inventory`, `Customers`, `Products`), automatic webhook deactivation after repeated delivery failures, rate limit response headers.

8. **MuleSoft Anypoint Platform (Retail & Commerce Accelerators)**
   - *Enterprise API-led connectivity benchmark for SAP, Oracle, and Salesforce Commerce Cloud.*
   - Sources: [MuleSoft Accelerator for Retail](https://www.mulesoft.com/exchange/org.mule.examples/mulesoft-accelerator-for-retail/), [MuleSoft NetSuite Connector](https://docs.mulesoft.com/netsuite-connector/latest/).
   - Key capabilities: 3-tier API architecture (Experience, Process, System APIs), canonical data models, guaranteed delivery queues, API client registry with token introspection and rate limiting.

---

## 3. Feature Catalog (Sub-module 9.19 only)

### 3.1 ERP & Back-Office Sync
- **Pre-configured ERP Connector Profiles** — Standardized connection profiles for SAP S/4HANA, Oracle NetSuite, Microsoft Dynamics 365, Odoo, and Generic REST/SOAP ERPs with base URLs, environment modes (sandbox/production), and authentication credentials. · seen in: *Celigo, Patchworks, MuleSoft* · priority: `table-stakes` · spine: new table `EcommerceConnector` · `buildable now`
- **Bidirectional Order-to-Cash Data Flows** — Outbound export of paid ecommerce orders to ERP sales orders and inbound synchronization of fulfillment status, shipping tracking, and invoice numbers. · seen in: *Celigo, Patchworks, MuleSoft* · priority: `table-stakes` · spine: new table `IntegrationSyncJob` (links to `EcommerceConnector`) · `buildable now`
- **Inventory Level Reconciliation** — Periodic or triggered stock-on-hand synchronization between NavERP/ERP systems and ecommerce fulfillment centers with safety buffer thresholds to prevent overselling. · seen in: *Patchworks, Celigo, Alloy* · priority: `table-stakes` · spine: `IntegrationSyncJob` · `buildable now`
- **Sync Execution Audit & Metrics Log** — Granular job run records capturing started/completed timestamps, duration, records processed, records succeeded, and records failed with detailed JSON diagnostics. · seen in: *Celigo, Patchworks* · priority: `table-stakes` · spine: `IntegrationSyncJob` · `buildable now`
- **Record-Level Error Recovery & Retry Queue** — Dedicated failure review queue storing exact error codes, payloads, and messages with manual and automated retry execution. · seen in: *Celigo integrator.io* · priority: `common` · spine: `IntegrationSyncJob` (parent/retry relationship) · `buildable now`

### 3.2 Payment Gateway Connectors
- **Multi-PSP Gateway Connector Registry** — Tenant-scoped integration profiles for Stripe, Adyen, PayPal, Square, Authorize.net, and regional payment providers. · seen in: *Commerce Layer, Shopify, commercetools Connect* · priority: `table-stakes` · spine: `EcommerceConnector` (category=`payment`) · `buildable now`
- **Environment & Credential Isolation** — Strict separation between Sandbox/Test and Production/Live credentials with encrypted token storage, masked key display, and account identifier mapping. · seen in: *Shopify, Stripe, BigCommerce* · priority: `table-stakes` · spine: `EcommerceConnector` · `buildable now`
- **Cryptographic Webhook Ingestion & Signature Verification** — Verifying incoming gateway callbacks (e.g. `payment_intent.succeeded`, `charge.refunded`) via HMAC signatures before status transitions occur. · seen in: *Commerce Layer, Stripe, Shopify* · priority: `table-stakes` · spine: new table `WebhookSubscription` · `buildable now`
- **External Payment Event Status Synchronization** — Mapping external payment states (authorized, captured, voided, refunded, disputed) into NavERP order and checkout sessions without creating redundant ledgers. · seen in: *Commerce Layer, commercetools* · priority: `common` · spine: `IntegrationSyncJob` + reuses `accounting.Payment` / `ecommerce.EcommerceOrder` · `buildable now`
- **Gateway Health Check & Ping Monitoring** — Real-time latency ping and connection test diagnostics verifying gateway endpoint availability and reporting uptime status (`healthy`, `degraded`, `unreachable`). · seen in: *Commerce Layer, Celigo* · priority: `differentiator` · spine: `EcommerceConnector` · `buildable now`

### 3.3 Shipping & Logistics APIs
- **Multi-Carrier Shipping Connector Profiles** — Standardized connectors for FedEx, UPS, DHL Express, USPS, EasyPost, ShipStation, and Freightview. · seen in: *Commerce Layer, Patchworks, Shopify* · priority: `table-stakes` · spine: `EcommerceConnector` (category=`shipping`) · `buildable now`
- **Carrier Rate Shopping API Integration** — Configurable endpoint parameters and rating credentials for fetching live negotiated carrier shipping rates during checkout. · seen in: *Commerce Layer, BigCommerce* · priority: `common` · spine: `EcommerceConnector` · `buildable now`
- **Fulfillment & Dispatch Tracking Synchronization** — Real-time inbound tracking updates and dispatch notifications synchronized from external 3PL and carrier APIs to update order fulfillment records. · seen in: *Patchworks, Celigo, Alloy* · priority: `table-stakes` · spine: `IntegrationSyncJob` + reuses `ecommerce.OrderFulfillment` · `buildable now`
- **Carrier Timeout Fallback Policies** — Automatic fallback to tenant-configured flat shipping rates if a carrier API fails to respond within defined timeout thresholds. · seen in: *Commerce Layer, Shopify* · priority: `common` · spine: `EcommerceConnector` · `buildable now`

### 3.4 Marketing Tool Integrations
- **Marketing Platform Connectors** — Connector profiles for Klaviyo, Mailchimp, Braze, Segment, and Google Analytics 4 (Measurement Protocol / CAPI). · seen in: *Alloy, Shopify Flow, commercetools* · priority: `table-stakes` · spine: `EcommerceConnector` (category=`marketing`) · `buildable now`
- **E-Commerce Event Streaming** — Real-time dispatch of customer behavioral events (Cart Abandoned, Checkout Started, Order Placed, Customer Registered) to marketing platforms. · seen in: *Alloy Automation, Klaviyo, Segment* · priority: `table-stakes` · spine: `WebhookSubscription` · `buildable now`
- **Customer Profile & List Synchronization** — Synchronizing opt-in customer profiles, lifetime spend, and purchase categories with external email/SMS marketing segments. · seen in: *Alloy, Patchworks* · priority: `common` · spine: `IntegrationSyncJob` + reuses `ecommerce.CustomerAccountProfile` · `buildable now`
- **Event Delivery Metrics & Throughput Tracking** — Daily throughput counters tracking events queued, dispatched, and failed per marketing tool integration. · seen in: *Segment, Alloy* · priority: `common` · spine: `EcommerceConnector` / `IntegrationSyncJob` · `buildable now`

### 3.5 Headless Commerce & API-First
- **API Credential & Client Management** — Tenant-scoped API credential management for headless web storefronts (Next.js, Nuxt), native mobile apps (iOS/Android), in-store POS, and third-party developer integrations. · seen in: *Shopify, BigCommerce, commercetools* · priority: `table-stakes` · spine: new table `ApiCredential` · `buildable now`
- **Public Storefront vs Private Admin Credential Split** — Dual-tier token architecture: Public Storefront tokens (browser-safe, restricted to read catalog and manage carts/orders) vs Private Admin credentials (server-to-server only, hashed secrets). · seen in: *Shopify, commercetools, BigCommerce* · priority: `table-stakes` · spine: `ApiCredential` (credential_type) · `buildable now`
- **Granular Permission Scopes** — Fine-grained capability scoping (`read_products`, `write_carts`, `read_orders`, `write_checkouts`, `read_inventory`, `manage_customers`, `manage_webhooks`). · seen in: *Shopify, BigCommerce* · priority: `table-stakes` · spine: `ApiCredential` · `buildable now`
- **Rate Limiting & CORS Origin Security** — Configurable requests-per-minute (RPM) limits (Standard: 60 rpm, Elevated: 300 rpm, Dedicated: 1200 rpm) paired with allowed CORS origins (e.g. `https://shop.acme.com`) and IP whitelist filters. · seen in: *Shopify, BigCommerce, MuleSoft* · priority: `common` · spine: `ApiCredential` · `buildable now`
- **Real-Time Outbound Webhook Subscriptions** — External event subscriptions with topic filtering (`order.created`, `order.fulfilled`, `inventory.low_stock`, `customer.registered`, `payment.captured`), HMAC-SHA256 signature signing (`X-NavERP-Signature`), and configurable payload formats (`json_standard`, `json_api`, `cloud_events`). · seen in: *commercetools Subscriptions, Shopify Webhooks, Commerce Layer* · priority: `table-stakes` · spine: `WebhookSubscription` · `buildable now`
- **Circuit Breaker Resilience Pattern** — Automatic trip mechanism (`closed` -> `open`) after repeated consecutive delivery failures (e.g. 10 errors) to protect server performance from dead consumer endpoints. · seen in: *Commerce Layer, commercetools* · priority: `differentiator` · spine: `WebhookSubscription` · `buildable now`

---

## 4. Recommended Build Scope (This Pass — 4 Models)

To deliver a production-ready, enterprise-grade Integration & API Ecosystem for Sub-module 9.19, we recommend **exactly four tenant-scoped models** located in `apps/ecommerce/models/IntegrationApi/`:

```
apps/ecommerce/models/IntegrationApi/
├── __init__.py
├── EcommerceConnectors.py       # EcommerceConnector [ECON-]
├── IntegrationSyncJobs.py       # IntegrationSyncJob [ESYJ-]
├── WebhookSubscriptions.py      # WebhookSubscription [EWBS-]
└── ApiCredentials.py            # ApiCredential [EAPC-]
```

### 4.1 `EcommerceConnector` [Prefix: `ECON`]
- **Purpose:** Central registry for external integration connection profiles across ERP, Payment, Shipping, and Marketing providers.
- **Fields & Choices:**
  - `number`: auto-generated via `next_number` with prefix `ECON`
  - `name`: `CharField(max_length=120)` (e.g., "NetSuite Production ERP", "Stripe Live Gateway", "FedEx Rate & Ship API", "Klaviyo Marketing Sync")
  - `category`: `CharField(max_length=30)` — `erp` (ERP & Back-Office), `payment` (Payment Gateway), `shipping` (Shipping & Logistics), `marketing` (Marketing & Analytics), `custom` (Custom REST API)
  - `provider`: `CharField(max_length=40)` —
    - ERP: `netsuite`, `sap_s4hana`, `ms_dynamics`, `odoo`, `custom_erp`
    - Payment: `stripe`, `adyen`, `paypal`, `square`, `generic_psp`
    - Shipping: `fedex`, `ups`, `dhl`, `easypost`, `shipstation`, `custom_carrier`
    - Marketing: `klaviyo`, `mailchimp`, `braze`, `segment`, `ga4_measurement`
  - `environment`: `CharField(max_length=20)` — `sandbox` (Sandbox/Test), `production` (Production/Live)
  - `base_url`: `URLField()` — Base endpoint URL for external service API
  - `auth_type`: `CharField(max_length=20)` — `api_key`, `oauth2_bearer`, `basic_auth`, `hmac_signature`, `none`
  - `api_key_masked`: `CharField(max_length=100, blank=True)` — Safe display key (e.g. `sk_live_...4f8a`)
  - `api_secret_hash`: `CharField(max_length=255, blank=True)` — Secure stored hash/token
  - `account_identifier`: `CharField(max_length=100, blank=True)` — External Merchant ID / Account ID / NetSuite Realm ID
  - `status`: `CharField(max_length=20)` — `draft`, `active`, `paused`, `error`, `maintenance`
  - `is_sync_enabled`: `BooleanField(default=True)`
  - `timeout_seconds`: `PositiveIntegerField(default=30)`
  - `max_retries`: `PositiveIntegerField(default=3)`
  - `last_health_check_at`: `DateTimeField(null=True, blank=True)`
  - `last_health_status`: `CharField(max_length=20, default="unknown")` — `healthy`, `degraded`, `unreachable`, `unknown`
  - `last_error_message`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
- **FKs & Spine:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE)` (via `TenantNumbered`)
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)`

### 4.2 `IntegrationSyncJob` [Prefix: `ESYJ`]
- **Purpose:** Records and tracks synchronization job runs, scheduled data batch flows, execution metrics, and error retry queues.
- **Fields & Choices:**
  - `number`: auto-generated via `next_number` with prefix `ESYJ`
  - `connector`: `ForeignKey(EcommerceConnector, on_delete=models.CASCADE, related_name="sync_jobs")`
  - `job_type`: `CharField(max_length=40)` —
    - `orders_export` (Order-to-Cash Export)
    - `orders_import` (Inbound Order Ingestion)
    - `inventory_sync` (Stock Level Reconciliation)
    - `catalog_export` (Product/Pricing Push)
    - `fulfillment_tracking` (Carrier Tracking Update)
    - `customer_sync` (Customer/Party Alignment)
    - `marketing_events` (Customer Event Push)
    - `payment_settlement` (Settlement Reconciliation)
  - `direction`: `CharField(max_length=20)` — `outbound` (NavERP -> External), `inbound` (External -> NavERP), `bidirectional`
  - `trigger_type`: `CharField(max_length=20)` — `manual`, `scheduled`, `event_driven`, `retry`
  - `status`: `CharField(max_length=20)` — `queued`, `running`, `completed`, `partial_success`, `failed`, `cancelled`
  - `started_at`: `DateTimeField(null=True, blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `duration_seconds`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))`
  - `records_total`: `PositiveIntegerField(default=0)`
  - `records_succeeded`: `PositiveIntegerField(default=0)`
  - `records_failed`: `PositiveIntegerField(default=0)`
  - `payload_summary`: `TextField(blank=True)` — JSON/text summary of batch
  - `error_log`: `TextField(blank=True)` — Detailed failure diagnostic log
  - `retry_count`: `PositiveIntegerField(default=0)`
  - `parent_job`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries")`
- **FKs & Spine:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE)`
  - `connector`: `EcommerceConnector`
  - `parent_job`: self-referential for retries
  - `initiated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)`

### 4.3 `WebhookSubscription` [Prefix: `EWBS`]
- **Purpose:** Manages outbound real-time event webhooks to external consumer systems (JAMstack storefronts, ERPs, 3PLs, marketing tools) with HMAC signature security and circuit breaker resilience.
- **Fields & Choices:**
  - `number`: auto-generated via `next_number` with prefix `EWBS`
  - `name`: `CharField(max_length=120)` (e.g. "Klaviyo Real-Time Order Stream", "Warehouse 3PL Fulfillment Listener", "Next.js ISR Revalidation")
  - `target_url`: `URLField()` — External HTTPS endpoint receiving event payloads
  - `event_topics`: `CharField(max_length=255)` — Comma-separated or wildcard topics (e.g. `order.created`, `order.fulfilled`, `inventory.low_stock`, `customer.registered`, `payment.captured`, `*`)
  - `secret_key`: `CharField(max_length=120)` — HMAC-SHA256 secret for `X-NavERP-Signature` generation
  - `payload_format`: `CharField(max_length=20)` — `json_standard`, `json_api`, `cloud_events`
  - `status`: `CharField(max_length=20)` — `active`, `paused`, `disabled_failures`, `archived`
  - `consecutive_failures`: `PositiveIntegerField(default=0)`
  - `max_failure_threshold`: `PositiveIntegerField(default=10)` — Trips circuit breaker when exceeded
  - `circuit_state`: `CharField(max_length=20)` — `closed` (Healthy/Normal), `half_open` (Testing Recovery), `open` (Tripped/Bypassed)
  - `last_delivery_at`: `DateTimeField(null=True, blank=True)`
  - `last_http_status`: `PositiveIntegerField(null=True, blank=True)`
  - `total_delivered_count`: `PositiveIntegerField(default=0)`
  - `total_failed_count`: `PositiveIntegerField(default=0)`
  - `connector`: `ForeignKey(EcommerceConnector, on_delete=models.SET_NULL, null=True, blank=True, related_name="webhooks")`
- **FKs & Spine:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE)`
  - `connector`: `EcommerceConnector` (optional association)

### 4.4 `ApiCredential` [Prefix: `EAPC`]
- **Purpose:** Manages API keys and client access credentials for Headless Storefronts, Jamstack frontends, native mobile apps, and third-party developer integrations.
- **Fields & Choices:**
  - `number`: auto-generated via `next_number` with prefix `EAPC`
  - `client_name`: `CharField(max_length=120)` (e.g. "Next.js Public Storefront", "iOS Mobile App", "POS In-Store Checkout Terminal", "B2B Punchout Client")
  - `credential_type`: `CharField(max_length=30)` —
    - `storefront_public` (Public Client Token — browser/mobile safe, read catalog, manage cart/checkout)
    - `admin_secret` (Server-to-Server Private Key — full merchant management scopes)
    - `webhook_receiver` (Inbound Webhook Verification Key)
    - `partner_integration` (Third-Party SaaS Partner)
  - `api_key_prefix`: `CharField(max_length=16)` — Public identifier prefix (e.g. `nep_live_...`)
  - `api_key_hash`: `CharField(max_length=255)` — SHA-256 hashed secret for authentication verification
  - `scopes`: `TextField(default="read_products,write_carts,write_orders")` — Comma-separated permission scopes
  - `allowed_origins`: `TextField(blank=True)` — CORS whitelist (e.g. `https://shop.example.com`)
  - `allowed_ips`: `TextField(blank=True)` — IP/CIDR whitelist for server-to-server admin keys
  - `rate_limit_rpm`: `PositiveIntegerField(default=60)` — Requests per minute rate limit tier
  - `status`: `CharField(max_length=20)` — `active`, `suspended`, `revoked`, `expired`
  - `expires_at`: `DateTimeField(null=True, blank=True)`
  - `last_used_at`: `DateTimeField(null=True, blank=True)`
  - `total_request_count`: `PositiveIntegerField(default=0)`
  - `notes`: `TextField(blank=True)`
- **FKs & Spine:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE)`
  - `issued_to_party`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="ecommerce_api_credentials")`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)`

---

## 5. Belongs to Sibling Sub-modules (Parked, Not Scoped Here)

- **Storefront CMS pages, themes, and navigation menus** → Belongs to `9.9 Content Management System (CMS)` (already built)
- **Customer cart calculation, discount coupon application, checkout sessions** → Belongs to `9.4 Shopping Cart & Checkout` (already built)
- **Internal order status transitions, fulfillment routing, and RMAs inside NavERP** → Belongs to `9.5 Order Management System (OMS)` (already built)
- **Push notification delivery and mobile device tokens** → Belongs to `9.16 Mobile Commerce` (already built)
- **B2B company accounts, quote negotiations, and credit limits** → Belongs to `9.17 B2B & Wholesale Commerce` (already built)
- **Transaction fraud risk scoring and chargeback disputes** → Belongs to `9.18 Fraud & Risk Management` (already built)
- **Multi-store brand management, domain routing, and CI/CD operations** → Belongs to `9.20 Multi-Store & Platform Operations` (next sub-module)
- **Financial journal posting, GL accounts, and tax reconciliation** → Belongs to Module 2 `accounting` (`accounting.JournalEntry`, `accounting.Invoice`)
- **Physical warehouse bin tracking and cycle counting** → Belongs to Module 4 `scm` / Module 5 `inventory`

---

## 6. Deferred (Later Passes / Integrations)

- **Distributed Celery / Redis Asynchronous Task Workers:** Background task worker infrastructure for processing high-volume HTTP webhook queues and ERP sync runs. *Why deferred:* Current pass provides database models, job status tracking, manual run/retry actions, and synchronous HTTP mock/live dispatch; dedicated Celery worker task definitions belong to cross-cutting background processing (Module 0 / DevOps).
- **Interactive OAuth 2.0 PKCE Authorization Server:** A complete OAuth 2.0 authorization server UI with consent screens for third-party marketplace apps. *Why deferred:* Enterprise API credentials using bearer tokens, public storefront keys, and server-to-server hashed keys fulfill headless and ERP integration requirements cleanly without OAuth server overhead.
- **Direct GraphQL Execution Engine & AST Schema Parser:** Native GraphQL endpoint processing inside Django. *Why deferred:* Headless storefront integration in NavERP operates via RESTful API views and token-authorized endpoints; GraphQL schema builders can sit on top of the established `ApiCredential` scope engine in a future platform release.
- **Physical Thermal Shipping Label Printing (ZPL / EPL streaming):** Raw socket streaming to thermal label printers. *Why deferred:* Pertains to physical warehouse fulfillment execution in Module 5 / WMS.
