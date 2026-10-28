# Research — Sub-module 8.18: Integration & API Hub (Module 8 — Sales, `sales`)

- **Sub-module:** 8.18 Integration & API Hub · **Module:** 8 Sales · **App:** `apps/sales`
- **Base commit:** `34a35ea6f3e5b3ee0bca4d010d80c05f7ff79998` (HEAD at research time)
- **Date:** 2026-10-28 · **Phase:** 1 (research) · **Output:** `.claude/tasks/research-sales-8.18.md` (read-only research agent)
- **Mission:** 8.18 is the **connector registry, field mapping, and sync execution layer** of the Sales Management module. It provides a sales-domain-scoped register of connections to the five external system categories specified in `NavERP.md` §8.18:
  1. **ERP Systems** for Order-to-Cash synchronization (SAP, Oracle, NetSuite, Microsoft Dynamics).
  2. **Marketing Automation** for bidirectional lead, contact, and engagement sync (HubSpot, Marketo, Pardot, Eloqua).
  3. **Communication Platforms** for deal alerts and collaborative revenue workflows (Slack, Microsoft Teams, Zoom, telephony).
  4. **Business Intelligence & Warehouses** for pipeline and performance datasets (Tableau, Power BI, Looker, Snowflake).
  5. **E-Signature & CLM Connectors** for agreement and signature lifecycle tracking (DocuSign, Adobe Acrobat Sign, PandaDoc).

Following **L55** (the 7.18 IXC ruling under L36), five integration registers coexist intentionally across NavERP to answer domain-specific questions:
- `scm` 4.19 `IntegrationEndpoint` [`CNX-`] — supply chain transport-less EDI/IoT/3PL register.
- `inventory` 5.19 `IntegrationChannel` [`INT-`] — commerce stock & listing register.
- `accounting` 2.15 `IntegrationConfig` — financial ledger & GL interface register.
- `projects` 7.18 `ProjectIntegrationConnector` [`IXC-`] — project delivery & task sync register.
- **`sales` 8.18 `SalesIntegrationConnector` [`SIC-`]** — revenue operations, order-to-cash, lead sync, deal alerts, and e-signature register.

Sub-module 8.18 FKs none of the sibling integration registers and re-declares none of their models. In accordance with repo architecture, 8.18 performs **zero outbound HTTP** and writes no accounting rows; `SalesSyncRun.status = "simulated"` is the honest status.

---

## 1. Repo state checked first (evidence, not docs)

### 1.1 Module 8 sidebar state (`apps/core/navigation.py`)
Grep check on `apps/core/navigation.py`:
- `LIVE_LINKS` contains `"8.1"` through `"8.17"` (:2327–:2630).
- Sub-module 8.17 (`Workflow & Process Automation`) is fully live with routes:
  - `sales:sales_process_definition_list`
  - `sales:sales_assignment_rule_list`
  - `sales:sales_approval_decision_list`
  - `sales:sales_alert_trigger_list`
  - `sales:party_enrichment_list`
- **Sub-module `"8.18"` is the next unbuilt sub-module in Module 8.**

### 1.2 Migration & Number Prefix State
- `apps/sales/migrations/` ends at **`0031_salesalerttrigger_salesapprovaldecision_and_more.py`**.
- Sub-module 8.18 claims migration **`0032_...`**.
- **Prefix Collision Audit across entire repo (`apps/**/models`):**
  - Taken in `projects` 7.18: `IXC`, `SYJ`, `SYR`.
  - Taken in `scm` 4.19: `CNX`, `MSG`, `WHK`.
  - Taken in `inventory` 5.19: `INT`, `SYN`.
  - Taken across `apps/sales`: `CMP`, `ACPL`, `OBL`, `CCT`, `CSB`, `UMR`, `QBR`, `CHS`, `COB`, `CRN`, `CADJ`, `CER`, `CMPL`, `CST`, `LNE`, `ATB`, `ATR`, `CNG`, `EVT`, `MQL`, `CHK`, `FSR`, `MDA`, `MDS`, `WLR`, `OUT`, `PIPE`, `OTM`, `AMD`, `OHD`, `OVR`, `RVS`, `CCF`, `DLR`, `JAP`, `PTR`, `CPQ`, `BND`, `QAR`, `SAL`, `ATY`, `SPC`, `TTPL`, `FNL`, `RPS`, `VCA`, `WLA`, `CSC`, `ECN`, `SCTF`, `SPB`, `FAD`, `FCP`, `FSC`, `FCS`, `TAS`, `QPA`, `TMB`, `TRG`, `SAT`, `SAD`, `SAR`, `SPD`.
  - **Free & recommended for 8.18:**
    - **`SIC-`** (`SalesIntegrationConnector`)
    - **`SSJ-`** (`SalesSyncJob`)
    - **`SSR-`** (`SalesSyncRun`)
    - Child table **`SalesFieldMapping`** (`TenantOwned`, unnumbered or `SFM-`).

### 1.3 As-built spine entities 8.18 reuses & FKs against (Verified via ORM import)
| Entity | Model Path | Key Fields & Semantics | URL Names in Repo |
|---|---|---|---|
| `Party` | `apps.core.models.Party` | Customer accounts, prospects, partners, vendors | `core:party_list`, `core:party_detail` |
| `SalesOrder` | `apps.scm.models.SalesOrder` [`SO-`] | Canonical ERP sales order for Order-to-Cash sync (L36/L37: owned by SCM 4.5, extended by Sales 8.6) | `scm:salesorder_list`, `scm:salesorder_detail` |
| `Opportunity` | `apps.crm.models.Opportunity` [`OPP-`] | Pipeline deals, stages, amounts, close dates | `crm:opportunity_list`, `crm:opportunity_detail` |
| `Lead` | `apps.crm.models.Lead` [`LEAD-`] | Inbound marketing leads for HubSpot/Marketo sync | `crm:lead_list`, `crm:lead_detail` |
| `CPQQuote` | `apps.sales.models.CPQQuote` [`CPQ-`] | Sales proposals and quote pricing configurations | `sales:cpq_quote_list`, `sales:cpq_quote_detail` |
| `CustomerContract` | `apps.sales.models.CustomerContract` [`CCT-`] | Customer commercial agreements for DocuSign CLM sync | `sales:customer_contract_list`, `sales:customer_contract_detail` |
| `User` | `apps.accounts.models.User` | Connector ownership and run execution actor | `accounts:user_list` |
| `Document` | `apps.core.models.Document` [`DOC-`] | Signed contracts and agreement attachments | `core:document_list` |
| `AuditLog` | `apps.core.models.AuditLog` | Security logging for credential changes & runs | System-wide audit log |

---

## 2. Leaders surveyed (with source links)

1. **Salesforce Integration Cloud / MuleSoft Composer for Salesforce** — Low-code native Salesforce integration app connecting CRM with NetSuite, SAP, Slack, Teams, Tableau, and Workday.
   - *Source:* `https://www.salesforce.com/products/integration/mulesoft-composer/`
   - *Key takeaway:* Unified integration canvas inside CRM UI; credential reuse with hidden post-setup secrets; multi-cloud connectors (SAP, NetSuite, Slack, Tableau).
2. **HubSpot Operations Hub (Data Sync)** — Real-time bidirectional CRM synchronization engine with custom field mapping, association sync, and conflict resolution rules.
   - *Source:* `https://www.hubspot.com/products/operations/data-sync`
   - *Key takeaway:* Explicit 2-way sync field mappings; record association preservation; conflict resolution policies (`last_updated_wins`, `hubspot_wins`, `external_wins`); picklist translation matrices.
3. **Microsoft Dynamics 365 Dual-write & Dataverse Integrations** — Out-of-the-box infrastructure connecting Dynamics 365 Sales with ERP (F&O / SAP) for Order-to-Cash, Teams, and Power BI.
   - *Source:* `https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/data-entities/dual-write/dual-write-overview`
   - *Key takeaway:* Pre-configured table maps for Order-to-Cash (`Customers` $\leftrightarrow$ `accounts`, `Quotations` $\leftrightarrow$ `quotes`, `Sales orders` $\leftrightarrow$ `salesorders`, `Invoices` $\leftrightarrow$ `invoices`); catch-up and pause/play sync controls.
4. **Workato for Revenue Operations (RevOps)** — Enterprise iPaaS for end-to-end Lead-to-Cash, CRM, ERP, Slack bots, Snowflake, and DocuSign workflows.
   - *Source:* `https://www.workato.com/solutions/revops`
   - *Key takeaway:* Recipe jobs scoping data movement; connection profiles with environment tags (production/sandbox); sync run error diagnosis and replay.
5. **DocuSign eSignature & CLM for Salesforce** — E-signature and contract lifecycle management connector with automated envelope status sync, agreement generation, and CRM field write-back.
   - *Source:* `https://www.docusign.com/products/salesforce`
   - *Key takeaway:* Real-time Envelope Status lifecycle (`sent`, `delivered`, `signed`, `declined`, `voided`, `expired`); automated contract stage progression triggered by signature events.
6. **Slack Sales Elevate (Sales Cloud for Slack)** — Dedicated sales workspace in Slack featuring deal stage alerts, high-value opportunity triggers, closed-won celebrations, and pipeline digest notifications.
   - *Source:* `https://slack.com/solutions/sales`
   - *Key takeaway:* Real-time opportunity alerts routed to specific channels based on stage and deal amount; deal celebration webhooks.
7. **Snowflake Data Sharing & Salesforce Data Cloud** — Zero-copy data sharing and automated data warehouse feeds connecting CRM pipeline and order data into Snowflake for analytics.
   - *Source:* `https://www.snowflake.com/en/solutions/partners/salesforce/`
   - *Key takeaway:* Automated dataset extraction & warehouse feeds for deals, orders, quotes, reps; delta replication tracking via modified cursors.
8. **Breadwinner for Salesforce** — Specialized ERP integration connector for Salesforce connecting NetSuite, QuickBooks, and Xero for complete order-to-cash and payment sync.
   - *Source:* `https://breadwinner.com/`
   - *Key takeaway:* Real-time invoice and payment status visible to sales reps without giving them full ERP access; read-only cash collection visibility.
9. **Tray.ai (Tray.io) for Sales Ops** — Automated cloud connector platform linking CRM leads, orders, ERP back-office systems, and collaboration tools.
   - *Source:* `https://tray.ai/solutions/sales`
   - *Key takeaway:* Connector authentication tokens, data mapping formulas, execution run metrics (records processed, errors).
10. **Zapier for Sales & RevOps** — Web automation and integration platform connecting sales workflows, deal alerts, and document sign-offs across 6,000+ business apps.
    - *Source:* `https://zapier.com/solutions/sales`
    - *Key takeaway:* Test run simulations, field value fallbacks, status alerts.

---

## 3. Feature catalog (this sub-module only)

### 3.1 ERP Integration (SAP, Oracle, NetSuite, Dynamics — Order-to-Cash)
- **Named Connector Profile** — Dedicated connection configuration per ERP instance specifying environment (production vs. sandbox) and credentials. · *seen in:* MuleSoft Composer, Dual-write, Breadwinner · *priority:* `table-stakes` · *spine:* `SalesIntegrationConnector` [`SIC-`] · *buildable now*
- **Order-to-Cash Entity Scopes** — Scoped sync jobs mapping Quotes, Sales Orders, Invoices, and Payment status between NavERP and external ERPs. · *seen in:* Dynamics 365 Dual-write, Breadwinner, Workato · *priority:* `table-stakes` · *spine:* Reuses `scm.SalesOrder`, `sales.CPQQuote`, `core.Party` via `SalesSyncJob` [`SSJ-`] · *buildable now*
- **Match / External Identity Key Mapping** — Identifying primary remote IDs (e.g., SAP Document Number, NetSuite Internal ID) mapped to NavERP numbers to ensure idempotent deduplication. · *seen in:* Dual-write, HubSpot Data Sync · *priority:* `table-stakes` · *spine:* `SalesFieldMapping.is_key` · *buildable now*
- **Invoice & Fulfillment Visibility in Sales** — Read-only reflection of ERP invoice payment and shipment delivery status on the sales record. · *seen in:* Breadwinner, MuleSoft · *priority:* `common` · *spine:* `SalesSyncRun` simulated execution log · *buildable now*
- **Live Two-Way ERP HTTP Web Service Calls** — Direct real-time SOAP/RFC/REST invocation into SAP/Oracle backends. · *seen in:* SAP PI/PO, MuleSoft · *priority:* `table-stakes` · *spine:* Deferred to production integration infrastructure · *integration/later*

### 3.2 Marketing Automation (HubSpot, Marketo, Pardot, Eloqua — Bidirectional Sync)
- **Bidirectional Lead & Contact Sync** — Ingesting new marketing leads from HubSpot/Marketo into CRM and pushing qualified sales opportunities back. · *seen in:* HubSpot Data Sync, Marketo Sales Insight · *priority:* `table-stakes` · *spine:* Reuses `crm.Lead`, `core.Party`, `crm.Opportunity` via `SalesSyncJob` · *buildable now*
- **Picklist & Choice Value Translation (`value_map`)** — Translation dictionary mapping remote stage/status strings to NavERP choices (e.g. `{"MQL": "qualified", "SQL": "in_pipeline"}`). · *seen in:* HubSpot Operations Hub, Tray.ai · *priority:* `table-stakes` · *spine:* `SalesFieldMapping.value_map` (JSONField) · *buildable now*
- **Conflict Resolution Rules** — Configurable precedence policy when records update simultaneously in both systems (`last_updated_wins`, `local_wins`, `remote_wins`, `flag_manual`). · *seen in:* HubSpot Data Sync, Workato · *priority:* `common` · *spine:* `SalesSyncJob.conflict_policy` · *buildable now*
- **Marketing Engagement Activity Score Ingestion** — Syncing email clicks, webinar attendance, and lead scoring events. · *seen in:* Marketo, Pardot · *priority:* `common` · *spine:* Reuses 8.1 `LeadScoreEvent` (L36: CRM owns leads, Sales owns score events) · *buildable now*

### 3.3 Communication Platforms (Slack, Microsoft Teams, Zoom, Telephony)
- **Deal Alert & Milestone Notification Trigger** — Automated alert configurations routing high-value deal changes, stage progressions, or discount requests to team chat channels. · *seen in:* Slack Sales Elevate, Teams Sales Integration · *priority:* `table-stakes` · *spine:* `SalesSyncJob(entity_scope="deal_alerts")` targeting `SalesIntegrationConnector(category="communication")` · *buildable now*
- **Channel / Room Mapping (`remote_scope_ref`)** — Storing external Slack channel IDs, Teams webhook endpoints, or Zoom room links per connector/job. · *seen in:* Slack Sales Elevate, Zapier · *priority:* `table-stakes` · *spine:* `SalesIntegrationConnector.remote_scope_ref` · *buildable now*
- **Closed-Won Celebration & Win Bot Feeds** — Pre-templated markdown payload formats announcing major deal wins and contract sign-offs. · *seen in:* Slack Sales Elevate, Troops.ai · *priority:* `common` · *spine:* Handled via connector alert configuration · *buildable now*
- **Telephony Click-to-Call Real-Time SIP Audio Streaming** — Live voice trunk integration. · *seen in:* Aircall, Talkdesk · *priority:* `differentiator` · *spine:* CRM 1.5 `CommunicationLog` records the calls; real-time audio deferred · *integration/later*

### 3.4 Business Intelligence & Data Warehouse (Tableau, Power BI, Looker, Snowflake)
- **Dataset Export & Feed Scopes** — Scoped extraction definitions for pipeline stages, quarterly forecasts, rep quota attainment, and revenue schedules. · *seen in:* Salesforce Data Cloud, Tableau Sync Out · *priority:* `table-stakes` · *spine:* `SalesSyncJob(entity_scope="bi_warehouse_feed")` · *buildable now*
- **Delta Replication Cursor (`modified_since`)** — Storing high-watermark timestamps for incremental ETL replication to Snowflake or Power BI. · *seen in:* Snowflake Data Cloud, Fivetran · *priority:* `common` · *spine:* `SalesSyncJob.last_run_at` and filter expressions · *buildable now*
- **Target Table & Schema Mapping** — Defining destination warehouse table and column naming conventions. · *seen in:* Snowflake, Looker · *priority:* `common` · *spine:* `SalesFieldMapping` with `target_entity="analytics_feed"` · *buildable now*
- **Direct Snowflake Warehouse Zero-Copy Micro-Partitioning** — Cloud storage zero-copy protocol. · *seen in:* Snowflake BYOL · *priority:* `differentiator` · *spine:* Requires external Snowflake warehouse credentials; simulated run status used · *integration/later*

### 3.5 E-Signature & CLM Connectors (DocuSign, Adobe Sign, PandaDoc)
- **Envelope Lifecycle Tracking** — Tracking e-signature agreement statuses (`sent`, `delivered`, `signed`, `declined`, `voided`, `expired`) on commercial customer contracts and quotes. · *seen in:* DocuSign for Salesforce, Adobe Acrobat Sign for Dynamics · *priority:* `table-stakes` · *spine:* `SalesSyncJob(entity_scope="contract_envelope_status")` linked to `sales.CustomerContract` and `sales.CPQQuote` · *buildable now*
- **E-Signature Agreement ID Mapping** — Storing remote envelope UUIDs and linking executed document records. · *seen in:* DocuSign, PandaDoc · *priority:* `table-stakes` · *spine:* `SalesFieldMapping.is_key` and `remote_scope_ref` · *buildable now*
- **Automated Stage Progression on Signature** — Advancing CPQQuote from `sent` to `accepted` and CustomerContract from `draft` to `active` upon signature completion. · *seen in:* DocuSign CLM, PandaDoc · *priority:* `common` · *spine:* Handled through status sync events · *buildable now*
- **Embedded In-Browser Biometric Signature Capture Canvas** — Native pen-pad signature widget. · *seen in:* DocuSign · *priority:* `common` · *spine:* External e-sign providers own the signing UI; NavERP tracks the envelope lifecycle · *integration/later*

### 3.6 Beyond the Bullets: Integration Hub Management & Operations
- **Centralized Integration Hub Dashboard** — Single pane of glass categorizing all connectors by family (ERP, Marketing, Communication, BI, E-Signature) with active health status badges. · *seen in:* MuleSoft Composer, Asana App Directory, Workato · *priority:* `table-stakes` · *spine:* Hub dashboard view rendering categorized connector cards · *buildable now*
- **Connection Test Ping (Zero Outbound HTTP)** — Simulated health check proving credential validity and producing an auditable `SalesSyncRun(status="simulated")`. · *seen in:* Tray.ai, Workfront Fusion, Projects 7.18 · *priority:* `table-stakes` · *spine:* POST test action creating `SalesSyncRun` · *buildable now*
- **Secret Encryption at Rest & Masked Display** — Fernet symmetric encryption using `apps.core.crypto` for all API keys and OAuth secrets with one-time copy reveal and `••••••••` masked detail views. · *seen in:* NavERP standard (L20/L25), MuleSoft, Workato · *priority:* `table-stakes` · *spine:* `apps.core.crypto.encrypt/decrypt` on `SalesIntegrationConnector` · *buildable now*
- **Sync Execution Run Ledger & Diagnostics** — Append-only execution history recording records read, written, failed, error traces, and duration. · *seen in:* Fivetran, MuleSoft, Projects 7.18 · *priority:* `table-stakes` · *spine:* `SalesSyncRun` [`SSR-`] · *buildable now*

---

## 4. Recommended build scope (this pass — exactly 4 models)

To strictly satisfy the Module Creation Sequence and maintain consistency with `projects` 7.18 and `inventory` 5.19, 8.18 builds a focused 4-model architecture:

### Model 1: `SalesIntegrationConnector` [`SIC-`]
- **Base:** `TenantNumbered` (`number` auto-numbered with prefix `SIC-`, length 20).
- **Core fields:**
  - `name`: CharField(255) — Human-readable connector title (e.g. "NetSuite Production ERP", "HubSpot Marketing Sync", "Revenue Slack Alerts", "Snowflake Analytics Feed", "DocuSign Production").
  - `category`: CharField(30, choices=CATEGORY_CHOICES) — `("erp", "ERP & Order-to-Cash")`, `("marketing", "Marketing Automation")`, `("communication", "Communication & Telephony")`, `("bi_warehouse", "BI & Data Warehouse")`, `("esignature", "E-Signature & CLM")`, `("custom", "Custom / Other")`.
  - `provider`: CharField(40, choices=PROVIDER_CHOICES) — `sap`, `oracle`, `netsuite`, `dynamics`, `hubspot`, `marketo`, `pardot`, `eloqua`, `slack`, `teams`, `zoom`, `tableau`, `powerbi`, `snowflake`, `looker`, `docusign`, `adobesign`, `pandadoc`, `custom`.
  - `environment`: CharField(20, choices=ENVIRONMENT_CHOICES) — `production`, `sandbox`, `staging`, `development`.
  - `base_url`: URLField(blank=True) — Remote API endpoint base URL.
  - `auth_method`: CharField(30, choices=AUTH_METHOD_CHOICES) — `api_key`, `oauth2`, `bearer_token`, `basic_auth`, `webhook_secret`.
  - `credential_encrypted`: TextField(blank=True) — Encrypted via `apps.core.crypto.encrypt` (never plaintext at rest; excluded from ModelForm per L20).
  - `remote_scope_ref`: CharField(255, blank=True) — External account/org/channel reference (e.g. ERP Company Code, Slack Channel ID `#sales-wins`, DocuSign Account ID, Snowflake Database name).
  - `is_active`: BooleanField(default=True, db_index=True).
  - `health_status`: CharField(20, choices=HEALTH_STATUS_CHOICES, default="untested") — `healthy`, `degraded`, `failing`, `untested`.
  - `last_sync_at`: DateTimeField(null=True, blank=True, editable=False).
  - `consecutive_failures`: PositiveIntegerField(default=0, editable=False).
  - `owner`: ForeignKey(`accounts.User`, null=True, blank=True, on_delete=SET_NULL, related_name="owned_sales_connectors").
  - `description`: TextField(blank=True).
- **Methods:** `set_credential(raw)`, `get_credential()`, `credential_masked` property.
- **FKs:** `tenant -> core.Tenant`, `owner -> accounts.User`.

### Model 2: `SalesFieldMapping` [Unnumbered Child Table]
- **Base:** `TenantOwned` (`tenant`, `created_at`, `updated_at`).
- **Core fields:**
  - `connector`: ForeignKey(`SalesIntegrationConnector`, on_delete=CASCADE, related_name="field_mappings").
  - `target_entity`: CharField(40, choices=TARGET_ENTITY_CHOICES) — `lead`, `account`, `opportunity`, `cpq_quote`, `sales_order`, `customer_contract`, `customer_subscription`, `analytics_feed`.
  - `local_field`: CharField(100) — Local model field name (e.g. `total_amount`, `stage`, `status`, `customer_name`, `email`).
  - `remote_field`: CharField(100) — Remote provider attribute (e.g. `TotalNetPrice`, `DealStage`, `CompanyId`, `EnvelopeStatus`).
  - `direction`: CharField(20, choices=DIRECTION_CHOICES) — `inbound` ("Inbound (Remote to NavERP)"), `outbound` ("Outbound (NavERP to Remote)"), `bidirectional` ("Bidirectional (Two-Way)").
  - `is_key`: BooleanField(default=False) — True if this field is the primary match/external ID for idempotent resolution.
  - `value_map`: JSONField(default=dict, blank=True) — Picklist/choice translation dictionary (e.g. `{"Won": "closed_won", "Lost": "closed_lost"}`).
  - `default_value`: CharField(255, blank=True).
  - `is_active`: BooleanField(default=True).
- **Constraints:** `models.UniqueConstraint(fields=["tenant", "connector", "target_entity", "local_field", "remote_field"], name="sales_field_map_unique_idx")`.
- **FKs:** `tenant -> core.Tenant`, `connector -> SalesIntegrationConnector`.

### Model 3: `SalesSyncJob` [`SSJ-`]
- **Base:** `TenantNumbered` (`number` auto-numbered with prefix `SSJ-`, length 20).
- **Core fields:**
  - `connector`: ForeignKey(`SalesIntegrationConnector`, on_delete=CASCADE, related_name="sync_jobs").
  - `name`: CharField(255) — Job descriptive name (e.g. "Hourly Order-to-Cash Sync", "Daily Marketing Lead Ingestion", "Deal Close Won Slack Alerts").
  - `entity_scope`: CharField(50, choices=ENTITY_SCOPE_CHOICES) — `order_to_cash`, `lead_lifecycle`, `deal_alerts`, `bi_warehouse_feed`, `contract_envelope_status`, `custom_payload`.
  - `sync_direction`: CharField(20, choices=DIRECTION_CHOICES, default="outbound").
  - `conflict_policy`: CharField(30, choices=CONFLICT_POLICY_CHOICES, default="last_updated_wins") — `last_updated_wins`, `local_wins`, `remote_wins`, `flag_manual`.
  - `sync_cadence`: CharField(30, choices=SYNC_CADENCE_CHOICES, default="manual") — `manual`, `realtime_event`, `interval_15m`, `hourly`, `daily`.
  - `filter_expression`: CharField(255, blank=True) — Query criteria (e.g. `stage='closed_won' AND amount > 50000`).
  - `is_active`: BooleanField(default=True, db_index=True).
  - `last_run_at`: DateTimeField(null=True, blank=True, editable=False).
  - `last_run_status`: CharField(20, choices=RUN_STATUS_CHOICES, default="simulated", editable=False).
- **FKs:** `tenant -> core.Tenant`, `connector -> SalesIntegrationConnector`.

### Model 4: `SalesSyncRun` [`SSR-`]
- **Base:** `TenantNumbered` (`number` auto-numbered with prefix `SSR-`, length 20).
- **Core fields:**
  - `connector`: ForeignKey(`SalesIntegrationConnector`, on_delete=CASCADE, related_name="sync_runs").
  - `job`: ForeignKey(`SalesSyncJob`, null=True, blank=True, on_delete=SET_NULL, related_name="sync_runs").
  - `run_type`: CharField(20, choices=RUN_TYPE_CHOICES, default="manual") — `scheduled`, `manual`, `test_ping`, `webhook_event`.
  - `status`: CharField(20, choices=RUN_STATUS_CHOICES, default="simulated") — `queued`, `in_progress`, `completed`, `partial_failure`, `failed`, `simulated`.
  - `started_at`: DateTimeField(default=timezone.now).
  - `completed_at`: DateTimeField(null=True, blank=True).
  - `records_read`: PositiveIntegerField(default=0).
  - `records_written`: PositiveIntegerField(default=0).
  - `records_failed`: PositiveIntegerField(default=0).
  - `error_log`: TextField(blank=True).
  - `execution_summary`: TextField(blank=True).
  - `triggered_by`: ForeignKey(`accounts.User`, null=True, blank=True, on_delete=SET_NULL, related_name="triggered_sales_sync_runs").
- **FKs:** `tenant -> core.Tenant`, `connector -> SalesIntegrationConnector`, `job -> SalesSyncJob`, `triggered_by -> accounts.User`.

---

## 5. Belongs to sibling sub-modules (parked, not scoped here)

- **Event-Driven Webhook Dispatch & Trigger Rules** → Belongs to **8.17 Workflow & Process Automation** (`SalesAlertTrigger` and `SalesProcessDefinition`). 8.18 handles connection profiles and scheduled data synchronization; event evaluation belongs to 8.17.
- **In-App Mobile Deal Push Alerts** → Belongs to **8.16 Mobile Sales** (`MobileDealAlert` [`MDA-`]).
- **Commercial Contract Obligations & Invoicing** → Belongs to **8.15 Contract & Subscription Management** (`ContractObligation` [`OBL-`] and `CustomerSubscription` [`CSB-`]).
- **Lead Qualification & Nurturing Engine** → Belongs to **8.1 Lead Management** (`LeadQualification` and `LeadNurtureEnrollment` [`LNE-`]).
- **Sales Order Amendments & Order Holds** → Belongs to **8.6 Order Management** (`OrderAmendment` [`AMD-`] and `OrderHold` [`OHD-`]).
- **Strategic Sourcing & Supplier EDI Connections** → Belongs to **4.19 SCM Integration** (`IntegrationEndpoint` [`CNX-`]).
- **eCommerce Stock & Inventory Channel Feeds** → Belongs to **5.19 Inventory Integration** (`IntegrationChannel` [`INT-`]).

---

## 6. Deferred (later passes / external integrations)

- **Outbound HTTP / Webhook Dispatcher Network Stack:** Production deployment requiring external internet gateway, celery/redis worker pools, retry queues, and rate-limiting throttling. In this build, simulated runs (`status="simulated"`) and connection test runs record honest execution records with zero outbound network traffic.
- **Live OAuth2 Token Refresh Handshake Engine:** Production token renewal flows requiring registered public callback endpoints and secure token refresh vaults. Stored as encrypted secrets at rest.
- **Real-Time Telephony WebRTC / SIP Audio Stream Engine:** Direct voice transport; call logging is already supported via CRM 1.5 `CommunicationLog`.
- **Snowflake Zero-Copy Native Direct-Query Pipeline:** Production warehouse infrastructure requiring active Snowflake tenant credentials.

---

## 7. Architectural Decisions & Lessons Compliance

1. **L55 Integration Register Independence:**
   - 8.18 defines its own `SalesIntegrationConnector` [`SIC-`], `SalesFieldMapping`, `SalesSyncJob` [`SSJ-`], and `SalesSyncRun` [`SSR-`].
   - Does NOT merge with or duplicate 4.19, 5.19, 2.15, or 7.18.
2. **L36/L37 Spine Re-use:**
   - Reuses `scm.SalesOrder` (canonical sales order), `crm.Opportunity`, `crm.Lead`, `sales.CPQQuote`, `sales.CustomerContract`, `core.Party`, `core.Document`, and `accounts.User`.
3. **Secret Security (L20/L25):**
   - API keys and secrets stored with Fernet encryption (`apps.core.crypto.encrypt`).
   - Plaintext secret is excluded from ModelForms; displayed only as masked `••••••••` or revealed via temporary session key on generation/rotation.
4. **Clean Number Prefixes:**
   - `SIC-` (Sales Integration Connector), `SSJ-` (Sales Sync Job), `SSR-` (Sales Sync Run) verified 100% collision-free across all apps.