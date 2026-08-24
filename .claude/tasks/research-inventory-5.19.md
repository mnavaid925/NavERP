# Research — Inventory Module 5.19 "Third-Party Integrations & API"
Phase-1 feature catalog · prepared 2026-08-25 · READ-ONLY pass (this file is the only write)

Spec bullets (NavERP.md verbatim):
1. **E-commerce Integration** — Syncing stock levels with Shopify, Amazon, WooCommerce, etc.
2. **ERP Integration** — Bi-directional data flow with systems like SAP, Oracle, or NetSuite.
3. **Accounting Software Integration** — Direct sync with QuickBooks, Xero, or Sage.
4. **API Management** — RESTful or GraphQL APIs for custom integrations with proprietary tools.

---

## 1. Product research (commercial + native-API landscape)

### iPaaS / commerce-integration platforms
- **Celigo integrator.io** — 200+ prebuilt connectors (incl. Shopify↔NetSuite reference flows);
  flow-level field/SKU mapping with lookup tables and transforms; an error-management console
  where each failed record can be retried/suppressed individually; OAuth credential vault per
  connection.
- **Patchworks** — retail-only iPaaS; connector catalog aimed at commerce stacks;
  trigger- and schedule-based sync flows; a run/audit dashboard showing every sync execution;
  mapping engine keyed on SKU/variant identity across channels.
- **MuleSoft Anypoint** — API-led connectivity: API Manager policies (rate limiting, client-id
  enforcement) govern who may CALL you; DataWeave as the declarative field-mapping language;
  environment-scoped secure properties for credentials (sandbox vs production separation).
- **Boomi AtomSphere** — process library with connector shapes (Shopify, Amazon marketplace,
  QuickBooks); document-tracking "warehouse" auditing every document through every process step;
  retry/error queues with document queueing; atom-level schedules.
- **Workato** — recipe automations whose triggers poll on delta windows ("new/updated since last
  run"); job reports with replay of failed jobs; lookup tables for SKU cross-reference; on-prem
  agent for reaching private ERP networks.
- **Zapier** — the largest app catalog; polling vs webhook trigger sources; task history with
  error filters and one-click replay; automatic retry of failed tasks; visual field mapping.
- **Jitterbit Harmony** — operation schedules plus "run when file arrives" triggers; transaction
  recovery with success/failure folders; an API Manager that PUBLISHES custom REST endpoints from
  operations (the "expose an API to partners" half of bullet 4).

### Native platform APIs (the other end of our connectors)
- **Shopify Admin API** — `inventorySetQuantities`/`inventoryAdjustQuantities` GraphQL mutations
  with compare-and-set (`compareQuantity`) + required idempotency key (as of 2026-04) so
  concurrent pushes cannot double-apply; REST leaky-bucket limits (40-bucket / 2 rps; Plus
  80/4) vs GraphQL cost bucket (1,000 points / 50 pts-per-second refill); async bulk operations
  (JSONL) for full-catalog syncs; webhooks fire out-of-order/duplicated → de-dupe on
  `X-Shopify-Webhook-Id`.
- **Amazon SP-API** — inventory read via FBA Inventory listings, stock writes via Inventory
  Feeds (JSON flat files, async); usage-plan rate limits surfaced through 429 +
  `x-amzn-RateLimit-Limit` restore-rate headers; grantless-operation tokens; notifications via
  EventBridge/webhook subscriptions.
- **WooCommerce REST API v3** — consumer-key/consumer-secret pair over HTTPS basic auth;
  batch endpoint `/wp-json/wc/v3/products/batch` capped at ~100 objects; direct
  `stock_quantity` updates; its webhook resource signs deliveries HMAC-SHA256 and keeps a
  delivery log.
- **SAP** — OData services (e.g. `API_PRODUCT_SRV`) and IDocs (MATMAS/ORDERS) with change-pointer
  DELTA feeds; SAP Integration Suite is the commercial wrapper. Bi-directional = push stock
  status, pull orders/material masters.
- **Oracle NetSuite SuiteTalk / SuiteScript** — SOAP+REST web services driven by saved searches
  as delta cursors; token-based auth needs FOUR credentials (consumer key/secret + token id/
  secret); hard concurrency caps (~10); scheduled SuiteScript 2.x scripts are how partners run
  inventory syncs.
- **QuickBooks Online API** — OAuth2 with refresh-token rotation; `minorversion` header
  versioning; strict throttling (429 with Retry-After, concurrency caps ≈10); batch ops ≤30.
- **Xero API** — OAuth2; rolling 60-calls/minute + 10,000/day per-org budgets; Items carry
  `quantity_on_hand`; webhooks use intent-based HMAC signature validation with a handshake.
- **Sage Business Cloud Accounting API** — OAuth2, Items service, low per-second call budgets —
  the "sync must be polite" end of the spectrum.

### Deduplicated, prioritized feature list for 5.19
P0 (build this pass):
1. **Connection register discriminated by kind** (ecommerce/erp/accounting/custom) — Celigo,
   Patchworks, Boomi all compress their catalogs this way; house precedent
   `accounting.IntegrationConfig.CATEGORY_CHOICES`.
2. **Credential lifecycle: prefix + SHA-256 hash, generate-once plaintext shown once, rotate**
   — accounting.IntegrationConfig mechanics (L20/L25 lessons).
3. **SKU/channel listing map** (local item ↔ external product/variant id ↔ stocking location)
   — Celigo/Patchworks/Workato lookup tables; THE inventory-domain content nothing else owns.
4. **Append-only sync-run log** per push/pull batch with record counts, error text, retry
   counter — Boomi document tracking, Workato job reports; posture of scm.IntegrationMessage.
P1 (columns recorded as INTENT, no engine):
5. Direction + schedule columns (push/pull/bidirectional; manual/scheduled/webhook trigger) —
   Workato/Zapier triggers; scm 4.19's "records intent, nothing runs" ruling.
6. Rate-limit documentation column per channel ("GraphQL 1,000 pts / 50 s") — Shopify leaky
   bucket, Amazon restore rates, Xero 60/min: a note humans read, not a throttle we enforce.
7. Error/retry queue STATE on the run log (`attempt_no`, `next_retry_at`, manual Retry POST that
   advances state but sends no HTTP) — Zapier replay, scm.WebhookDelivery retry semantics.
P2 (explicitly NOT built here):
8. Generic outbound webhook subscriptions — scm 4.19 owns them.
9. Inbound HTTP receiver for channel webhooks — no transport in any NavERP integration module.
10. Real OAuth2 token exchange/storage — deferred everywhere; auth_method records intent.

---

## 2. Prior-art rulings (files actually read)

### apps/scm/models/IntegrationApiGateway/ (scm 4.19, just built)
Four models:
- **IntegrationEndpoint [CNX]** (TenantNumbered): name, category(erp/ecommerce/iot/edi/custom —
  the discriminator behind ITS sidebar bullets), system(sap/oracle/netsuite/shopify/amazon/...),
  direction, transport(api_rest/as2/van/mqtt/llrp/...), auth_method, endpoint_url CharField
  (# SSRF WARNING), external_account_ref, interchange_id/_qualifier (blank when logistics_client
  set — constraint A), device_identifier, trigger_mode, schedule_note, environment(sandbox/
  production), lifecycle_stage(setup→live/suspended), status(disconnected/connected/error/
  disabled), is_active, consecutive_failures/last_run_at/last_success_at/last_seen_at (all
  editable=False), credential_prefix(12)/credential_hash(64) editable=False +
  hash_secret/set_credential/generate_credential/masked, FKs partner_party/logistics_client/
  location/spec_document SET_NULL; unique (tenant,number)+(tenant,name).
- **IntegrationMessage [MSG]** (TenantNumbered): APPEND-ONLY exchange log — endpoint CASCADE,
  direction, document_type(X12 sets/order_import/inventory_feed/fulfilment_export/...),
  status(pending/sent/received/acknowledged/failed/ignored), control_number, external_id (de-dupe
  probe, NOT unique — redelivery is a fact to record), record_count (batch size, not row count),
  payload_excerpt TRUNCATED, error_code/message, attempt_count editable=False,
  occurred_at(default=timezone.now, editable=False), source+source_reference soft pointer (NO
  GenericForeignKey), acknowledges self-FK SET_NULL, typed FKs only purchase_order/sales_order.
- **WebhookSubscription [WHK]** (TenantNumbered): trigger_entity (verified scm classes ONLY —
  the documented reason it is NOT crm.Webhook), trigger_event, target_url URLField,
  payload_format, filter_expression/include_fields (recorded never evaluated), headers JSON,
  auto_disable_threshold, consecutive_failures editable=False, last_delivery_at,
  signing_secret_prefix/hash + set_signing_secret/masked.
- **WebhookDelivery** (TenantOwned — deliberately NO number: per-attempt telemetry): subscription
  CASCADE, event, payload_excerpt, signature (BLANK by design — no transport, hash cannot sign),
  status(pending/success/failed/exhausted/**simulated**), attempt_no, next_attempt_at stamp,
  response_code, error_message, triggered_at. No unique_together. Svix backoff tuple adopted
  verbatim: (0,5,300,1800,7200,18000,36000,36000).

**RULING (scm 4.19 boundary):** 5.19 does NOT re-declare a generic gateway. scm.IntegrationEndpoint
already answers "a connection to an outside system" at the supply-chain boundary (EDI/IoT/3PL), and
its sidebar bullets even share OUR bullet names ("ERP/E-commerce Integration") — that is exactly why
inventory must stay narrow. 5.19 builds the COMMERCE-STOCK layer scm does not have: which SKUs and
which `scm.Location`s are exposed to which channel, and what each stock push did. Peer apps do not
import each other's internals (house rule in `apps/inventory/models/_base.py:8-9`), so 5.19 does
not FK scm.IntegrationEndpoint either — it owns its own narrow register and keeps NO EDI/IoT
vocabulary (no interchange_id, no device_identifier, no llrp/as2 transports). Same two-vocabularies
precedent as crm.Webhook vs scm.WebhookSubscription.

### apps/accounting/models/Integration/IntegrationConfigs.py (accounting 2.15)
`IntegrationConfig(TenantOwned)` — name; provider(16 incl. shopify/woocommerce/netsuite/
quickbooks); category(banking/payments/tax/ecommerce/crm/erp/hris/storage/other);
status(disconnected/connected/error); `api_key_prefix CharField(12, blank, editable=False)`;
`api_key_hash CharField(64, blank, editable=False)`; last_sync DateTimeField(null, editable=False);
is_active; notes. Methods EXACTLY:
```python
@staticmethod
def hash_secret(secret): return hashlib.sha256(secret.encode()).hexdigest()
def set_secret(self, secret): self.api_key_prefix = secret[:6]; self.api_key_hash = self.hash_secret(secret)
@property
def masked: return f"{self.api_key_prefix}{'•' * 8}"   # "" when no hash
@staticmethod
def generate_secret(): return secrets.token_urlsafe(24)
```
Plaintext NEVER persisted; revealed exactly once on rotate; live sync deferred.

**RULING (secret-handling pattern source):** copy these mechanics verbatim into both credential
holders below (channel connector key + inbound ApiClient token): prefix+SHA-256 hash, both
editable=False so they are structurally off every ModelForm, generate-once plaintext shown once,
`masked` property rendered, never `.api_key_prefix` directly. CRITICAL DIFFERENCE vs scm:
`apps/inventory/models/_base.py` star-exports NEITHER `hashlib` NOR `secrets` (verified — scm._base
star-exports secrets but not hashlib). Each 5.19 entity module MUST `import hashlib` and
`import secrets` itself and must NOT edit `_base.py` (L43 shared-file rule under concurrent
sessions). Hash-as-marker is correct because 5.19 ships no transport either (nothing signs,
nothing authenticates from the stored value); the day real transport lands, migrate to Fernet via
`apps/core/crypto.py` (`encrypt`/`decrypt`, the worked example is crm.Webhook.secret
CharField(512) ciphertext + `get_secret()`), NEVER revert to plaintext.

### apps/inventory/models/AccountingFinancialIntegration/ (inventory 5.18 — UNCOMMITTED concurrent session; READ ONLY, never edit)
- **GLPostRule(TenantOwned)** — account map per event_type(adjustment/cogs),
  unique_together(tenant,event_type), PROTECT FKs to accounting.GLAccount ×2, clean() tenant guard.
- **JournalSyncLog [JSY](TenantNumbered)** — register of what was POSTED into accounting's ledger;
  source_kind(adjustment/cogs_batch), StockAdjustment PROTECT nullable, COGS date window,
  moves_count/total_value, journal_entry SET_NULL editable=False, posted_by/posted_at; PLUS the
  posting SERVICES post_adjustment_to_gl()/post_cogs_batch() writing balanced posted
  accounting.JournalEntry rows atomically, admin-gated, audited via core.write_audit_log.
- **TaxRule [TRT](TenantNumbered)** — product×geography resolver → accounting.TaxCode
  (specificity 8/4/2 scoring), item/category PROTECT nullable.

**RULING (5.18 boundary):** 5.18 = INTERNAL automation that WRITES Module-2 ledger documents.
5.19's "Accounting Software Integration" = the CONNECTOR REGISTER toward EXTERNAL packages
(QuickBooks/Xero/Sage tenants sync WITH), writing NO JournalEntry, touching NO accounting model,
posting nothing. If both exist for one tenant (a Xero channel AND a GL rule) they answer different
questions — same split as 4.18 DutyTariff vs 5.18 TaxRule. 5.19 also writes no StockMove: stock
level changes stay the spine's business; a sync run RECORDS what was pushed, it never mutates
on-hand.

### Spine verification (grep `^class ...` under apps/scm/models — ALL CONFIRMED)
- `scm.Item` — apps/scm/models/InventoryManagement/Items.py:73 (+ ItemCategory :34, UOM :51)
- `scm.Location` — apps/scm/models/InventoryManagement/Locations.py:14
- `scm.StockMove` — apps/scm/models/InventoryManagement/StockMoves.py:13

### Other wiring facts verified
- Abstract bases: `TenantOwned` (tenant CASCADE related_name="+", created_at, updated_at) and
  `TenantNumbered` (adds number CharField(20) editable=False, NUMBER_PREFIX class attr,
  retry-on-collision save) at apps/inventory/models/_base.py:31/44. Exports available from
  `_base import *`: Decimal, ZERO, ValidationError, Min/MaxValueValidator, models, IntegrityError,
  transaction, F/Q/Sum, timezone, next_number — NOT hashlib/secrets.
- `tenant_admin_required` decorator: apps/core/decorators.py:13.
- Audit helper: `write_audit_log(user, obj, action, payload)` from apps.core.utils (used by 5.18).
- Sidebar: LIVE_LINKS dict in apps/core/navigation.py (:36; "5.18" entry at :1374 shows the shape —
  bullet-name → "inventory:<route>"). Logs/runs get NO sidebar key (ClientRateCardLine/ReorderRule
  rule; scm stated the omission per-log at navigation.py:1406-1414).

---

## 3. Recommended build scope — 4 tenant-scoped models

Backend package `apps/inventory/models/ThirdPartyIntegrations/`; first entity owns a local
`_choices.py` (imports NOTHING, `__all__` explicit; siblings import BY NAME — never star-import a
_choices module, shadow risk documented in scm 4.19). All constraints start with `tenant`.

### 3.1 `IntegrationChannel` — TenantNumbered, NUMBER_PREFIX `"INT"` → INT-
The connection register (Celigo/Patchworks compression; serves bullets 1–3).
- `name` CharField(120); unique_together (("tenant","number"), ("tenant","name")).
- `kind` choices KIND_CHOICES: ecommerce / erp / accounting / custom (max_length=12) — the three
  bullets + escape hatch, mirroring scm's category-discriminator trick minus IoT/EDI.
- `platform` PLATFORM_CHOICES (max_length=20): shopify/amazon_sp_api/woocommerce/ebay/walmart/
  magento/bigcommerce/sap/oracle_erp/netsuite/dynamics/quickbooks/xero/sage/custom.
- `direction` SYNC_DIRECTION_CHOICES: push_stock / pull_orders / bidirectional (default
  bidirectional — NetSuite/SAP bi-directional bullet).
- `auth_method` AUTH_METHOD_CHOICES: none/api_key/basic/oauth2/signature (default api_key;
  oauth2 records intent, stores nothing).
- `base_url` CharField(500, blank) — # WARNING SSRF comment REQUIRED (tenant-editable URL the
  server WOULD dial; no requests/urllib/httpx/http.client anywhere in this build; future transport
  needs allow-list + RFC1918/loopback/link-local block + DNS-rebinding re-resolve).
- `external_account_ref` CharField(120, blank) — shop domain / seller id / realm / company id.
- Credential store (accounting.IntegrationConfig mechanics verbatim): `api_key_prefix`(12)/
  `api_key_hash`(64) BOTH blank editable=False; `set_api_key()` (prefix=secret[:6]),
  `generate_api_key()` (secrets.token_urlsafe(24)), `masked` property, `import hashlib`,
  `import secrets` IN THIS MODULE.
- `environment`: sandbox/production; `status`: disconnected/connected/error/disabled (human
  marker ON the form — no transport observes success, same ruling as scm endpoint.status).
- `trigger_mode`: manual/scheduled/webhook (INTENT only, no scheduler exists);
  `schedule_note` CharField(200, blank).
- `rate_limit_note` CharField(120, blank) — P1 feature 6: e.g. "QBO: 429 w/ Retry-After, ~10
  concurrent" or "Xero: 60 req/min + 10k/day". Documentation, not enforcement.
- `default_location` FK "scm.Location" SET_NULL null blank related_name="+" — WHICH stocking
  location backs this channel's availability (inventory-flavored content scm's endpoint lacks).
- System-maintained, ALL editable=False: `last_sync_at` DateTimeField(null) (home for the future
  transport pass, like LogisticsClient.last_synced_at), `last_run_status` CharField(14, blank).
- `is_active`, `notes`. Indexes: (tenant,kind), (tenant,status), (tenant,is_active).
- Writes: create/edit/delete/rotate-key @tenant_admin_required (credentials).

### 3.2 `ChannelListingMap` — TenantOwned (no number: high-volume plumbing)
The SKU↔channel identity table (Celigo/Patchworks lookup tables; the sub-module's core
inventory-domain asset; serves bullets 1–2, supports 3).
- `channel` FK "inventory.IntegrationChannel" CASCADE related_name="listings".
- `item` FK "scm.Item" PROTECT null blank related_name="channel_listings" (channel-wide row when
  blank); `location` FK "scm.Location" PROTECT null blank (blank = every location).
- `external_product_id` CharField(80, blank); `external_variant_id` CharField(80, blank);
  `external_sku` CharField(80, blank) — Shopify variant gid / Amazon ASIN-SKU / Woo product id.
- `sync_enabled` BooleanField(default=True); `price_override` Decimal(18,2) null blank.
- Derived, editable=False: `last_pushed_qty` Decimal null blank, `last_pushed_at` DateTimeField(null).
- `notes`. unique_together ("tenant","channel","external_variant_id") — MariaDB allows duplicate
  NULLs so local-only rows coexist; index (tenant,item). Writes: staff-level CRUD; clean()
  enforces tenant-scope on channel/item/location (TENANT_SCOPED_FKS loop, scm idiom).

### 3.3 `StockSyncRun` — TenantNumbered, NUMBER_PREFIX `"SYN"` → SYN-
Append-only run log (Boomi document tracking / Workato job report; serves bullets 1–3 audit need).
- `channel` FK CASCADE related_name="runs" (the module's ONE cascade, like scm MSG.endpoint).
- `direction`: outbound_push/inbound_pull (no default — never assume); `trigger_mode`: manual/
  scheduled/webhook_inbound.
- `status` RUN_STATUS_CHOICES: pending/success/partial/failed/exhausted/**simulated** —
  `simulated` is mandatory honesty: nothing leaves the process, so recording "success" would make
  the log evidence of something that did not happen (scm WebhookDelivery ruling).
- Counts: records_total/records_ok/records_failed PositiveIntegerField(default 0).
- `payload_excerpt` TextField(blank) — TRUNCATED excerpt; may contain buyer PII; never full body.
- `error_code` CharField(40, blank); `error_message` TextField(blank).
- Retry queue state (Zapier-replay feature, scm WHD semantics): `attempt_no`
  PositiveSmallIntegerField(default 1), `next_retry_at` DateTimeField(null blank) — a STAMP not a
  trigger; the single UI write is a `stocksyncrun_retry` POST advancing attempt_no/next_retry_at
  along a backoff tuple and firing NO HTTP request.
- `started_at` DateTimeField(default=timezone.now, editable=False), `finished_at` null.
- **APPEND-ONLY: no ModelForm anywhere** (forms package carries the "deliberately absent" comment);
  list + detail + retry POST only. Runs ARE human-discussed ("last night's Shopify push"), hence
  SYN- numbering — unlike scm.WebhookDelivery telemetry. ordering ["-started_at","-id"];
  indexes (tenant,channel), (tenant,status,started_at). No sidebar entry; reached from the channel
  detail page's recent-runs panel + deep-link filter ?channel=<pk> / ?status=failed.

### 3.4 `ApiClient` — TenantNumbered, NUMBER_PREFIX `"API"` → API-
Bullet 4 (API Management): keys WE issue to third parties calling OUR REST/GraphQL surface
(MuleSoft/Jitterbit client-management half; nobody else owns inbound access control — crm/scm
webhooks are OUTBOUND push).
- `name` CharField(120) unique with tenant; `description` TextField(blank).
- `scopes` CharField(255, blank) comma list, e.g. "stock:read,moves:read"; `protocol` choice
  rest_graphql: rest/graphql (max_length=8, default rest).
- Token store: SAME prefix+SHA-256 mechanics (api_token_prefix/api_token_hash editable=False,
  set_api_token(), generate_api_token(), masked). Plaintext shown exactly once on issue/rotate.
- `status`: active/revoked (default active); `revoked_at` DateTimeField(null, editable=False).
- `allowed_ips` CharField(255, blank) — RECORDED intent, not enforced (no middleware this pass;
  say so in help_text).
- `last_used_at` DateTimeField(null, editable=False) — home for the future gateway pass.
- `rate_limit_note` CharField(120, blank) (our own budget promise to the consumer).
- Writes: ALL @tenant_admin_required (issuing access to data). Revoke is a POST action, never an
  unguarded edit. Audit via write_audit_log on issue/revoke.

### Migration-number etiquette (L43)
Disk today ends at `0025_alter_quarantineorder_status.py` (0024 is 5.18's uncommitted
glpostrule_journalsynclog_taxrule work of the CONCURRENT session). **5.19 claims `0026_...` but
MUST re-run `ls apps/inventory/migrations/` immediately before generating** — if 0026 appeared,
take the next free number instead; never renumber another session's migration.

### Computed-page candidates
- Channel detail page: masked credential chip + rotate button, default-location context, and the
  recent-runs timeline panel (deep-links into stocksyncrun_list?channel=<pk>).
- Failed-runs exceptions view = stocksyncrun_list filtered ?status=failed, linked from channel
  detail when last_run_status=="error". NOT a separate NavERP.md bullet page.
- LIVE_LINKS["5.19"]: "E-commerce Integration"/"ERP Integration"/"Accounting Software
  Integration" → three routes onto integrationchannel_list?kind=<x>; "API Management" →
  apiclient_list. Logs get no keys.

## 4. Boundary rulings — what 5.19 does NOT build
1. **No outbound HTTP.** Zero requests/urllib/httpx/http.client imports. `base_url` and any target
   column carry `# WARNING SSRF` comments; `stocksyncrun_retry` performs no HTTP; statuses include
   `simulated`; rate-limit notes are prose, not throttles.
2. **No re-declaration of the spine.** scm.Item/UOM/Location/StockMove are string-FK'd only
   (paths verified above); no parallel item/location/quantity fields beyond derived display copies.
3. **No GL posting, no accounting models touched.** That is 5.18 (GLPostRule/JournalSyncLog own
   internal JE automation; UNCOMMITTED files — never edit them). QuickBooks/Xero/Sage appear only
   as external connector registrations.
4. **No SCM partner EDI/IoT/webhook machinery.** scm 4.19 owns IntegrationEndpoint/
   IntegrationMessage/WebhookSubscription/WebhookDelivery; 5.19 declares no interchange_id, no
   transport vocab beyond rest/graphql/feed-file, no webhook subscription table. Inbound channel
   events are merely RECORDED on StockSyncRun(trigger_mode=webhook_inbound).
5. **No GenericForeignKey** (app ban): soft-pointer source/source_reference idiom if correlation
   is ever needed; typed FKs (channel/item/location) only.
6. **No new crypto primitives:** reuse the accounting prefix+hash mechanics; reversible storage
   (apps/core/crypto.py Fernet) is the FUTURE transport pass's move, not ours.

## 5. Gotchas for build agents
- Templates: `templates/inventory/integration/<entity>/<page>.html` — short slug `integration`
  while the backend package is PascalCase `ThirdPartyIntegrations/`. The asymmetry is the house
  rule (same note sits in scm 4.19's docstrings); do not "fix" either side.
- Backend packages `apps/inventory/{models,forms,views}/ThirdPartyIntegrations/<Entity>.py`;
  absolute imports; the re-export blocks in the models/forms/views package `__init__.py` (and
  urls/__init__.py) are added surgically by the INTEGRATOR — builders never touch shared __init__
  files, `_base.py`, or 5.18's files.
- Badge classes are colour-named ONLY: badge-green/red/amber/info/muted/slate (theme.css reality —
  there is no badge-success/warning/danger; those render unstyled, four times shipped).
- pk filters in templates/HTMX compare `|stringformat:"d"`.
- `import hashlib` AND `import secrets` inside the entity modules — inventory `_base.py` exports
  neither (unlike scm's `_base`). Never widen `_base.py` mid-flight.
- Every unique constraint/index leads with `tenant`; TenantNumbered.number is max_length=20 —
  prefixes INT/CLM-less/SYN/API all fit.
- All derived/system-maintained columns get editable=False (structurally off forms, L20/L22);
  counters a human could type are also derived-state violations (L29).
- `next_number` collision retry already handled by TenantNumbered.save; don't roll your own.
