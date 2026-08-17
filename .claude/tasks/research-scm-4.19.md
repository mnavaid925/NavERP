# Research — Sub-module 4.19: Integration & API Gateway (Module 4 — Supply Chain Management, `scm`)

> **4.19 is the LAST unbuilt sub-module of Module 4.** `apps/core/navigation.py` carries `LIVE_LINKS` keys
> `"4.1" … "4.18"` (grep `^    "4\.\d+":` → lines 770, 783, 793, 803, 815, 827, 839, 849, 869, 885, 914, 934, 978,
> 1022, 1057, 1090, 1113, 1126). No `"4.19"` key exists. Everything in 4.1–4.18 is therefore fair game to FK.

---

## Repo state checked first

### LIVE_LINKS built so far in module 4
`4.1 4.2 4.3 4.4 4.5 4.6 4.7 4.8 4.9 4.10 4.11 4.12 4.13 4.14 4.15 4.16 4.17 4.18` — all 18. 4.19 is the only gap.

### Sibling scm models verified to exist (grep `^class \w+` on `apps/scm/models/`)
All confirmed present, by sub-module folder:

| Folder | Classes |
|---|---|
| `ProcurementManagement/` | `PurchaseRequisition(+Line)`, `RFQ(+Line/+Vendor)`, `RFQQuote(+Line)`, `PurchaseOrder(+Line)`, `GoodsReceiptNote(+GoodsReceiptLine)` |
| `SupplierRelationshipManagement/` | `SupplierProfile`, `SupplierCatalog(+Item)`, `SupplierContract`, `SupplierScorecard`, `SupplierRiskAssessment` |
| `InventoryManagement/` | `Item`, `ItemCategory`, `UOM`, `Location`, `StockMove`, `LotSerial`, `ReorderRule`, `StockTransfer(+Line)`, `StockAdjustment(+Line)` |
| `WarehouseManagement/` | `PickTask(+Line)`, `PutawayTask`, `CycleCountTask(+Line)`, `YardVisit` |
| `OrderManagement/` | `SalesOrder(+Line)`, `SalesOrderAllocation` |
| `TransportationManagement/` | `Carrier(+RateCard)`, `Shipment`, `TrackingEvent`, `Load(+Stop)`, `FreightInvoice(+Line)` |
| `DemandPlanning/` | `DemandForecast(+Period)`, `DemandSignal`, `ForecastAdjustment`, `SeasonalityProfile(+Index)` |
| `Manufacturing/` | `WorkOrder(+Component)`, `WorkCenter`, `BillOfMaterials(+BOMLine)`, `ProductionTimeLog` |
| `QualityManagement/` | `QualityInspection(+InspectionResult)`, `NonConformance`, `CapaAction(+Task)`, `QualityAudit`, `InspectionPlan(+Characteristic)` |
| `ReturnsManagement/` | `ReturnAuthorization(+ReturnLine)`, `WarrantyClaim(+Cost)`, `ReturnReason`, `ReturnDisposition`, `ReturnPolicy` |
| `SupplyChainAnalytics/` | `KpiTarget`, `KpiSnapshot`, `SupplyChainAlert` |
| `ContractCompliance/` | `ComplianceRequirement(+Check)`, `TradeDocument(+Line)`, `TradeLicense`, `SustainabilityAssessment` |
| `AssetManagement/` | `Asset(+SparePart)`, `MaintenancePlan(+Task)`, `MaintenanceWorkOrder(+Part/+Task)`, `MeterReading` |
| `LaborManagement/` | `LaborStandard`, `LaborPlan(+Line)`, `LaborSession`, `LaborActivity` |
| `ColdChainManagement/` | `ColdChainMonitor`, `TemperatureReading`, `TemperatureExcursion` |
| `CustomerPortal/` | `PortalAccount`, `PortalOrderInquiry`, `PortalDocumentShare`, `PortalActivity` |
| `ThirdPartyLogistics/` | `LogisticsClient`, `ClientSLA`, `ClientRateCard(+Line)`, `ClientBillingRun(+Line)` |
| `FinanceIntegration/` | `LandedCostVoucher(+Charge/+Allocation)`, `DutyTariff` |

### Core spine entities verified to exist
`grep -rn "^class (Tenant|Party|PartyRole|Address|ContactMethod|Activity|AuditLog|Document|OrgUnit|Employment)\b" apps/core/models/`
→ **all ten hit**: `core/models/Tenant.py:5`, `Party.py:5`, `PartyRole.py:5`, `Address.py:5`, `ContactMethod.py:5`,
`Activity.py:5`, `AuditLog.py:5`, `Document.py:5`, `OrgUnit.py:5`, `Employment.py:5`.
`core.AuditLog` (read in full) is append-only with `tenant / user / content_type+object_id GenericFK / target /
action / changes JSON / at`.

### Prior art in OTHER apps — verified, and it changes the design
Two integration subsystems are already built elsewhere. **Both were read.** Neither is reusable for 4.19, but both
set the pattern 4.19 must follow.

- **`apps/accounting/models/Integration/IntegrationConfigs.py:6` — `IntegrationConfig(TenantOwned)`** (Accounting
  2.15). `PROVIDER_CHOICES` (plaid/stripe/paypal/square/avalara/vertex/shopify/woocommerce/salesforce/hubspot/
  quickbooks/netsuite/workday/custom) × `CATEGORY_CHOICES` (banking/payments/tax/ecommerce/crm/erp/hris/storage/
  other) × `STATUS_CHOICES` (disconnected/connected/error), plus `api_key_prefix` + `api_key_hash` (both
  `editable=False`), `last_sync`, `is_active`. Has `set_secret()`, `hash_secret()`, `generate_secret()`, `masked`.
  Docstring: *"Live sync against the provider is deferred."*
  → **This is the exact shape 4.19's connector model should copy**, but it is **financial-connector scoped** and
  lives in another app's tenant tables. 4.19 must NOT FK into it and must NOT extend it (that would put EDI
  trading-partner config inside the accounting app).
- **`apps/crm/models/AutomationWorkflow/Webhooks.py:7` — `Webhook(TenantNumbered, NUMBER_PREFIX="WH")` +
  `:43 WebhookDelivery(models.Model)`** (CRM 1.10). Webhook = `name / target_url / trigger_entity / trigger_event /
  secret / is_active / headers JSON / description`; delivery = `webhook / event / payload / signature / status
  (pending·success·failed·simulated) / response_code / error_msg / created_at`, documented as *"Immutable
  append-only delivery record … Real outbound HTTP is deferred (status starts pending). Accessed list+detail only
  — never edited."*
  → **The config+log pair is the proven NavERP shape and 4.19 should mirror it.** But `Webhook.trigger_entity`
  uses `WorkflowRule.ENTITY_CHOICES` — a CRM vocabulary (lead/opportunity/case/…). It **cannot express**
  `shipment.delivered` or `goods_receipt.posted`. An SCM webhook needs SCM trigger entities, which is the concrete
  justification for a separate scm table rather than a cross-app FK.
  → **WARNING — do NOT copy `crm.Webhook.secret`.** It is a plaintext `CharField(max_length=128)` masked only at
  render time (`secret_masked` shows the last 4). That is a credential at rest. 4.19 uses the prefix+hash pattern
  instead (see *Secrets* below).

### Backlog handed to 4.19 by earlier scm research files (Glob `.claude/tasks/research-scm*.md` → 4.2–4.18 all present)
Explicitly parked **to 4.19** by name:
- `research-scm-4.17.md:309-312` — *"The actual connector layer — real 940/945 exchange, webhooks, REST endpoints,
  marketplace connectors … **parked → 4.19**"*; `:313-316` — *"SECURITY — do not add an endpoint URL + credential
  column … secret handling is 4.19's problem, with a proper secrets store"*; `:449` — Client Integration was shipped
  as **data-only fields**, execution parked; `:460-461`.
- `research-scm-4.18.md:490` — *"EDI / e-invoicing / PEPPOL / ERP connectors / tariff-content feeds → 4.19"*.
- `research-scm-4.12.md:632` — *"EDI transmission of trade documents → 4.19 Integration & API Gateway"*.
- `research-scm-4.16.md:451-452` — *"Carrier API / GPS / EDI ingestion of tracking events, webhooks to customer
  systems → 4.6 (event log) and 4.19"*.
- `research-scm.md:236-238, 361` — the original module survey listed 4.19 as ERP/e-commerce connectors, IoT gateway
  (RFID/barcode/sensors), EDI, webhooks.

**4.17 already shipped the non-secret half of this.** `apps/scm/models/ThirdPartyLogistics/LogisticsClients.py`
carries `integration_mode`, `client_system`, `edi_partner_id`, `edi_qualifier`, `last_synced_at` (`editable=False`)
with a module docstring at `:24-28` stating *"No secret of any kind lives on this row (L20) … credential storage,
EDI transport and webhooks are **4.19's**. `last_synced_at` is written by NOTHING in 4.17 — it exists so that when
4.19 lands it writes a real value."* → 4.19 must **not** duplicate those columns; it links to the client instead.

### Two as-built scm conventions 4.19 must obey
- **No `GenericForeignKey` in scm — ever.** Documented twice: `ColdChainMonitors.py:18` (*"three typed FKs, exactly
  one of which is set — never a GenericForeignKey"*) and `PortalDocumentShares.py:9-11` (*"a `(content_type,
  object_id)` pair cannot be tenant-joined"*). The app's correlation idiom is a **`source` choice + `source_reference`
  CharField** soft pointer — see `DemandSignal.source_reference` (`DemandSignals.py:74`, with index
  `scm_ds_tnt_ref_idx` at `:117` and de-dupe use at `:258`), `ComplianceRequirement.source_reference:239`,
  `ClientBillingRunLine.source_reference:810`.
- **Append-only logs are read-only (list + detail, no edit/delete route).** Precedent: `crm.WebhookDelivery`
  ("never edited"), and `apps/scm/tests/test_security.py:6126 TestMeterReadingHasNoEditOrDeleteRoute` — the pattern
  is enforced by a shipped test. High-volume telemetry logs are `TenantOwned` with **no** number (`StockMove`,
  `TemperatureReading`, `PortalActivity`, `KpiSnapshot`); human-discussed records are `TenantNumbered`
  (`TemperatureExcursion` = `EXC-`).
- **Auto-number prefixes already taken in scm** (58 of them): `ADJ AST ALR BOM CAPA CAR CAT CBR CC CCM CR DF DS DTY
  ESG EXC FA FRT GRN KPI LAB LC LD LIC LPL LSN LST MWO NCR PAC PDS PIK PIQ PM PO PR PRD PUT QA QC QT RFQ RMA SC
  SCR SEA SHP SLA SO SRA TAR TD TRF WC WO WTY YRD`. → `CNX`, `MSG`, `WHK` are **free**.

---

## Leaders surveyed (with source links)

1. **Cleo Integration Cloud** — EDI + API + MFT in one ecosystem-integration platform; the "operational cockpit"
   framing for transaction visibility — <https://www.cleo.com/cleo-integration-cloud>,
   <https://www.cleo.com/blog/best-edi-software-providers>
2. **SPS Commerce** — the largest retail trading-partner network, sold as a managed EDI service with pre-built
   connections to 100+ ERP/WMS systems — <https://www.spscommerce.com/products/>
3. **TrueCommerce** — mid-market EDI tied directly to a named ERP (NetSuite, Acumatica, Sage, QuickBooks); noted for
   VMI and international e-invoicing coverage — surveyed via Cleo's and Celigo's comparison write-ups
   (<https://www.celigo.com/blog/sps-commerce-competitors/>, <https://www.cleo.com/blog/best-edi-software-providers>)
4. **Celigo integrator.io** — iPaaS with prebuilt connectors + "Integration Apps", error management, and an API
   management layer with rate limiting and a developer portal — <https://www.celigo.com/ipaas/>,
   <https://www.celigo.com/integration-apps/shopify-netsuite/>
5. **Boomi** — pioneer iPaaS; process reporting dashboards, B2B/EDI trading-partner management, API management,
   event streams, MFT, ML-assisted mapping suggestions — <https://boomi.com/platform/integration/>
6. **Workato** — recipe/automation-centric iPaaS with a built-in API gateway, federation, portal, and
   "enterprise observability" (audit trails, health) — <https://www.workato.com/features>
7. **MuleSoft Anypoint** — API-led enterprise integration for large orgs with dedicated dev teams (positioning
   confirmed in the 2026 iPaaS surveys) — <https://www.appseconnect.com/top-10-ipaas-platforms-of-2026-for-cios-it-leaders/>
8. **Shopify (webhook subsystem)** — the reference e-commerce event-push model: topic + destination + API version +
   filters + `include_fields`, HMAC-SHA256 signature, webhook-id de-dupe, explicit no-ordering guarantee —
   <https://shopify.dev/docs/apps/build/webhooks>
9. **Svix** — purpose-built webhook-sending service; the cleanest published *data model* for this problem
   (Application → Endpoint → Message → Attempt, event types, filters, retry schedule, auto-disable, replay) —
   <https://docs.svix.com/overview>, <https://docs.svix.com/retries>
10. **Kong Gateway** — the API-gateway half of the sub-module title: consumers/credentials, key-auth/OAuth2/JWT/mTLS,
    sliding-window rate limiting, request validation, request/response transformation, audit logging —
    <https://konghq.com/products/kong-gateway>
11. **RFID middleware (Impinj ItemSense / Zebra FX Connect class)** — the IoT-gateway reference: reader registry and
    health, LLRP/SDK adapters, read filtering + deduplication + zone logic before anything reaches ERP/WMS —
    <https://www.rfidnews.co.uk/2026/04/24/rfid-middleware-explained-why-you-cant-just-plug-readers-into-your-erp/>,
    <https://itemit.com/rfid-middleware/>
12. **Azure IoT Hub / Device Registry** — device identity registry, provisioning, device twin
    (desired vs reported properties), telemetry ingestion —
    <https://learn.microsoft.com/en-us/azure/iot/iot-introduction>,
    <https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-devguide-device-twins>

Cross-cutting market context: Nucleus Research's 2026 iPaaS Value Matrix names Boomi, Infor, Oracle, Salesforce
(Informatica) and Tray.ai as Leaders, with Boomi and MuleSoft leading share
(<https://www.prnewswire.com/news-releases/nucleus-research-releases-2026-ipaas-technology-value-matrix-302741817.html>).
EDI transaction-set vocabulary taken from <https://www.edibasics.com/edi-resources/document-standards/ansi/>.

---

## Secrets — the mandatory pattern for every credential field in this sub-module

**Nothing in 4.19 stores a plaintext credential. Not one field.** The as-built reference is
`apps/tenants/models/EncryptionKey.py` (read in full):

```
prefix   = models.CharField(max_length=16, editable=False)
key_hash = models.CharField(max_length=128, editable=False)

@staticmethod
def generate_plaintext():        return "nk_" + secrets.token_urlsafe(32)
def set_secret(self, plaintext): self.prefix = plaintext[:10]
                                 self.key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
```

…and the accounting sibling `IntegrationConfig.set_secret()` / `.masked` / `.generate_secret()`
(`apps/accounting/models/Integration/IntegrationConfigs.py:36-53`), whose docstring already says *"The API secret is
NEVER stored — only a prefix + SHA-256 hash (lessons L20/L25); the plaintext is revealed exactly once on rotate."*

Rules for 4.19:
1. Every credential (ERP API key, e-commerce access token, SFTP/AS2/VAN password, webhook HMAC signing secret) is
   stored as **`*_prefix` + `*_hash`, both `editable=False`** — never on a ModelForm, never in a template, never in
   a queryset the template iterates.
2. The plaintext is **generated server-side** and **displayed exactly once** on a `generate`/`rotate` POST action,
   then discarded. There is no "reveal" view and no "test connection" that needs it back.
3. `secrets.token_urlsafe(...)` only — never `random`, never `uuid4().hex`. `secrets` is already star-exported from
   `apps/scm/models/_base.py:17` (it exists there for `ReturnAuthorization.public_token`), so no new import.
4. **No OAuth access/refresh tokens.** They are bearer credentials that must be usable in plaintext by a runtime
   NavERP does not have. Record `auth_method="oauth2"` and stop there.
5. **WARNING — SSRF.** `WebhookSubscription.target_url` and `IntegrationEndpoint.endpoint_url` are
   user-supplied URLs. Nothing in this pass performs an outbound request, and nothing may be added that does
   without an allow-list / private-IP-range block first. Carry the same `# WARNING` comment `crm/views` carries on
   its deferred delivery helper.
6. **Payload retention.** `IntegrationMessage.payload` can contain partner PII (ship-to names/addresses on an 856).
   Store a truncated `payload_excerpt`, not a full document body, and say so in the field help text.

---

## Feature catalog (this sub-module only)

### Bullet 1 — ERP Integration ("connectors for SAP, Oracle, NetSuite, or Microsoft Dynamics")

- **A named connection per external system, typed by vendor** — a first-class row naming the counterpart system
  (SAP S/4HANA, Oracle, NetSuite, Dynamics 365) rather than a free-text note. · seen in: Cleo (native connectors for
  SAP S/4HANA, NetSuite, Dynamics), Celigo, Boomi (1000+ connectors), TrueCommerce (NetSuite/Acumatica plug-ins),
  SPS ("pre-built connections to 100+ ERP, WMS and business systems") · priority: **table-stakes** · spine: **new
  table `IntegrationEndpoint`**, `system` choice mirroring `accounting.IntegrationConfig.PROVIDER_CHOICES` ·
  buildable now
- **Connection status + last successful run** — connected / disconnected / error, with a `last_run_at` and a
  `last_success_at`, so a human can see at a glance whether a link is alive. · seen in: Celigo ("monitoring
  dashboards, real-time visibility"), Boomi (process reporting), Workato ("system health"), Cleo · priority:
  **table-stakes** · spine: `IntegrationEndpoint.status` + `last_run_at`/`last_success_at` (`editable=False`) —
  identical to the verified `accounting.IntegrationConfig.status` + `last_sync` · buildable now
- **Direction of the flow (inbound / outbound / bidirectional)** — the single most load-bearing classification in
  every product surveyed; determines the whole meaning of the row. · seen in: Celigo (Shopify→NetSuite orders,
  NetSuite→Shopify items, bidirectional fulfillments/refunds), Boomi, Cleo · priority: **table-stakes** · spine:
  `IntegrationEndpoint.direction` · buildable now
- **Trigger mode: real-time/webhook vs scheduled poll vs manual/file drop** — how the flow is supposed to fire. ·
  seen in: Celigo (real-time flows + scheduled flows), Boomi, Workato (triggers), Cleo (scheduled MFT vs event) ·
  priority: **common** · spine: `IntegrationEndpoint.trigger_mode` + `schedule_note` · **data now, execution later**
  (no scheduler exists — the field records intent, exactly as 4.17's `last_synced_at` does)
- **Environment separation (production / sandbox)** — every serious platform isolates test from live. · seen in:
  Celigo, Boomi (environments/deployment), Svix ("completely isolated instances with separate API keys") ·
  priority: **common** · spine: one `environment` choice field on `IntegrationEndpoint` — a cheap field, not a table ·
  buildable now
- **Field-level mapping / transformation designer** — visual any-to-any mapping, Boomi Suggest's ML mapping hints. ·
  seen in: Cleo (visual mapping), Boomi (Boomi Suggest), Celigo (prebuilt mappings), MuleSoft · priority:
  **table-stakes in-market** · spine: would need a 5th+6th table (`MappingProfile` + `MappingRule`) · **deferred —
  see Deferred**
- **Live sync against the ERP** — actual SOAP/REST calls, SuiteTalk, OData. · priority: table-stakes in-market ·
  **integration/later** — Django 5.1 server-rendered CRUD, no worker, no queue

### Bullet 2 — E-commerce Integration ("connectors for Shopify, Magento, WooCommerce, or Amazon")

- **Storefront/marketplace connection with a store identifier** — the shop domain / seller ID / marketplace region
  is the practical key, distinct from the credential. · seen in: Celigo Shopify–NetSuite Integration App, Cleo
  (marketplace systems), Boomi, TrueCommerce (marketplace + e-commerce channels) · priority: **table-stakes** ·
  spine: `IntegrationEndpoint` with `category="ecommerce"` + `external_account_ref` (shop domain / seller id) ·
  buildable now
- **The canonical channel flows: orders in, inventory out, fulfilments back, refunds/cancellations both ways** —
  Celigo's Shopify↔NetSuite app enumerates exactly this set (orders → sales orders, customers →, items/collections
  ←, inventory levels ←, fulfilments ↔, refunds ↔, cancellations →, draft orders/abandoned carts → quotes). ·
  seen in: Celigo, Cleo, Boomi, TrueCommerce · priority: **table-stakes** · spine: this is a **document-type
  vocabulary**, not tables — `IntegrationMessage.document_type` gets non-EDI members (`order_import`,
  `inventory_feed`, `fulfilment_export`, `item_export`, `refund_sync`, `customer_sync`) · buildable now
- **Correlate the external order to the internal record** — "which NetSuite sales order is this Shopify order?" is
  the question the log exists to answer. · seen in: Celigo, Cleo (end-to-end order visibility), Shopify
  (`X-Shopify-Webhook-Id` / `eventId`), Svix (`eventId` "for mapping to your internal systems") · priority:
  **table-stakes** · spine: `IntegrationMessage.external_id` + the scm `source` / `source_reference` soft-pointer
  idiom (**verified** on `DemandSignal:74`, `ComplianceRequirement:239`, `ClientBillingRunLine:810`) — **never a
  GenericForeignKey**, which scm bans at `ColdChainMonitors.py:18` and `PortalDocumentShares.py:9` ·
  buildable now. Optional typed FK to the **verified** `scm.SalesOrder` (`OrderManagement/SalesOrders.py:20`)
  for the common case.
- **Duplicate suppression on redelivery** — Shopify: *"use the `X-Shopify-Webhook-Id` header to identify and ignore
  duplicates"*; delivery is explicitly not ordered and not guaranteed. · seen in: Shopify, Svix · priority:
  **common** · spine: `IntegrationMessage.external_id` + an index on `(tenant, external_id)`, the exact de-dupe
  shape `DemandSignal` already uses (`scm_ds_tnt_ref_idx`, `DemandSignals.py:117,258`) · buildable now

### Bullet 3 — IoT Gateway ("ingestion of data from RFID tags, barcode scanners, and sensors")

- **A device/reader registry with health and last-seen** — middleware is *"a single control plane for all readers,
  handling reader configuration, monitoring device health … ensuring each reader operates with correct power levels
  and read intervals"*; Azure IoT Hub calls it the identity registry, one row per permitted device. · seen in:
  Impinj ItemSense / Zebra FX Connect class middleware, Azure IoT Hub Device Registry · priority: **table-stakes for
  this bullet** · spine: **`IntegrationEndpoint` with `category="iot"`** — a reader/scanner/sensor gateway *is* an
  endpoint (a name, a transport, a credential, an enabled flag, a last-seen stamp), plus `device_identifier` and a
  **verified** FK to `scm.Location` (`InventoryManagement/Locations.py:14`) for the zone it watches ·
  buildable now — **see the "one shared model" argument below; this is why IoT does not get its own table**
- **Transport/protocol of the feed (MQTT, HTTP POST, serial/LLRP, file drop, AS2, SFTP)** — reader estates are
  connected *"through standard interfaces such as LLRP and vendor SDK adapters"*; Cleo lists AS2/SFTP/FTP/VAN/API on
  the B2B side. · seen in: RFID middleware, Cleo, Boomi (MFT), Kong (multi-protocol) · priority: **common** ·
  spine: one `transport` choice on `IntegrationEndpoint`, shared across all four connector bullets · buildable now
- **Ingestion batches recorded as messages, with a raw-read count and an accepted count** — the middleware value
  proposition is *"filters noisy raw reads, applies deduplication and zone logic, and delivers clean operational
  events"*; a single UHF reader emits thousands of reads/second. Recording the batch (not every tag) is what fits a
  CRUD app. · seen in: Impinj/Zebra-class middleware, itemit · priority: **common** · spine:
  `IntegrationMessage` with `document_type="tag_read_batch" | "scan_batch" | "sensor_reading"` and a
  `record_count` · buildable now
- **Do NOT build a sensor-reading table.** `scm.TemperatureReading` (`ColdChainManagement/TemperatureReadings.py:83`)
  and `scm.MeterReading` (`AssetManagement/MeterReadings.py:60`) are **both verified to exist** and already own
  per-sensor telemetry for 4.15 and 4.13 respectively. A third reading table in 4.19 is a duplicate spine. ·
  priority: n/a · spine: **reuse the verified 4.15/4.13 tables**; 4.19 records only *that a batch arrived over which
  endpoint*
- **Device twin / desired-vs-reported configuration push** — Azure IoT Hub's `telemetryConfig` desired/reported
  property sync. · seen in: Azure IoT Hub · priority: **differentiator** · spine: would need a per-device config
  table · **deferred**

### Bullet 4 — EDI Management ("Electronic Data Interchange for standardized B2B communication")

- **Trading-partner connection keyed to a real party** — the partner is not a new customer/vendor entity; it is an
  existing counterparty with EDI envelope identity attached. · seen in: SPS Commerce (partner network + onboarding),
  Cleo (self-service partner onboarding, reusable partner templates), Boomi (B2B/EDI trading-partner management),
  TrueCommerce · priority: **table-stakes** · spine: `IntegrationEndpoint.partner_party` → **verified**
  `core.Party` (`apps/core/models/Party.py:5`; scm FKs it 20+ times — `TradeDocuments.py:175-179`,
  `Assets.py:175-180`, `LandedCostVouchers.py:150`). **Never a second partner table** — customers/vendors are
  `core.PartyRole`s (verified `core/models/PartyRole.py:5`) · buildable now
- **Interchange envelope identity (ISA sender/receiver ID + qualifier)** — the non-secret routing identity on every
  X12 envelope. · seen in: SPS, Cleo, TrueCommerce, all EDI vendors · priority: **table-stakes** · spine:
  `IntegrationEndpoint.interchange_id` + `interchange_qualifier` — **the same non-secret pair 4.17 already shipped**
  as `LogisticsClient.edi_partner_id` / `edi_qualifier` (`LogisticsClients.py:178-182`). For a 3PL client, FK the
  **verified** `scm.LogisticsClient` (`ThirdPartyLogistics/LogisticsClients.py:61`) instead of re-typing them ·
  buildable now
- **Per-document-type transaction log with the X12 vocabulary** — 850 PO, 855 PO acknowledgement, 860 PO change,
  856 ASN/ship notice, 810 invoice, 820 remittance, 846 inventory advice, 214 carrier shipment status, 940 warehouse
  shipping order, 945 warehouse shipping advice, 997 functional acknowledgement, 864 text. · seen in: EDI Basics
  (standard), Cleo, SPS, TrueCommerce, Boomi · priority: **table-stakes** · spine:
  `IntegrationMessage.document_type` choices · buildable now. Every one of these maps to a **verified** scm entity:
  850/855/860→`PurchaseOrder`, 856→`Shipment`, 810→`FreightInvoice`, 846→`Item`/`StockMove`, 214→`TrackingEvent`,
  940/945→`PickTask`/`Shipment`, 947→`StockAdjustment`
- **Acknowledgement tracking (997 outstanding / received)** — an unacknowledged 850 is the single most common EDI
  support ticket. · seen in: Cleo ("end-to-end visibility across orders, invoices, ASNs, acknowledgments"), SPS,
  Boomi, EDI Basics · priority: **table-stakes** · spine: `IntegrationMessage.status` gets an `acknowledged` member
  + `acknowledged_at` + a self-FK `acknowledges` (the 997 row points at the 850 row) · buildable now
- **Control number / interchange reference per transmission** — how a human and a partner talk about one specific
  transmission. · seen in: all EDI vendors · priority: **table-stakes** · spine:
  `IntegrationMessage.control_number` · buildable now
- **Partner onboarding lifecycle + compliance scoring** — Cleo: *"guided setup, testing, validation, and ongoing
  lifecycle management"*, plus *"compliance scoring and partner performance measurement"*; SPS sells onboarding and
  chargeback/deduction recovery as products. · seen in: Cleo, SPS, TrueCommerce · priority: **common** · spine:
  a `lifecycle_stage` choice (`setup → testing → certified → live → suspended`) on `IntegrationEndpoint` — a field,
  not a table. **Scorecarding is out of scope**: `scm.SupplierScorecard` (verified,
  `SupplierRelationshipManagement/SupplierScorecards.py:11`) already owns partner performance → 4.2 ·
  buildable now (the stage field only)
- **Actual AS2/SFTP/VAN transmission, envelope parsing, 997 auto-generation, X12 validation** · seen in: all ·
  priority: table-stakes in-market · **integration/later** — no transport layer exists

### Bullet 5 — Webhooks ("configurable triggers to send data to external applications upon specific events")

- **Subscription = (event topic, destination URL, active flag)** — the irreducible core in every product. · seen in:
  Shopify (topic + delivery destination, declared in `shopify.app.toml` or the Admin API), Svix (endpoint subscribes
  to event types), Workato, Boomi (event streams), `crm.Webhook` (built) · priority: **table-stakes** · spine:
  **new table `WebhookSubscription`** — `trigger_entity` + `trigger_event` + `target_url` + `is_active`, mirroring
  the verified `crm.Webhook` shape but with an **SCM** entity vocabulary · buildable now
- **SCM-specific trigger entities** — `purchase_order`, `goods_receipt`, `sales_order`, `shipment`, `stock_move`,
  `return_authorization`, `quality_inspection`, `work_order`, `asset`, `supply_chain_alert` — each of which is a
  **verified** existing class. Events: `created / updated / status_changed / approved / posted / cancelled /
  delivered`. · priority: **table-stakes for this sub-module** · spine: `WebhookSubscription.ENTITY_CHOICES` — this
  is precisely what `crm.Webhook` cannot express (its choices come from `crm.WorkflowRule.ENTITY_CHOICES`) ·
  buildable now
- **HMAC-signed payloads** — Shopify sends `X-Shopify-Hmac-Sha256`; Svix signs every message; `crm.Webhook` has a
  `secret` for the same purpose. · seen in: Shopify, Svix, crm (built) · priority: **table-stakes** · spine:
  `WebhookSubscription.signing_secret_prefix` + `signing_secret_hash` — **the prefix+hash pattern, NOT crm's
  plaintext column** (see *Secrets*) · buildable now
- **Per-attempt delivery log with response code and error** — Svix's `Attempts` are *"records of individual delivery
  tries … capturing response status codes and content for debugging"*; `crm.WebhookDelivery` is exactly this and is
  already shipped. · seen in: Svix, Shopify, crm (built) · priority: **table-stakes** · spine: **new table
  `WebhookDelivery`**, append-only, list+detail only (the `MeterReading`/`crm.WebhookDelivery` precedent) ·
  buildable now
- **Retry with exponential backoff, then auto-disable** — Svix publishes the exact schedule: immediate, 5s, 5min,
  30min, 2h, 5h, 10h, 10h — **8 attempts over ~32 hours**; an endpoint failing repeatedly for 5 days is
  *automatically disabled and the customer notified*. · seen in: Svix, Shopify (failing endpoints removed) ·
  priority: **table-stakes in-market** · spine: **model the state, not the daemon** —
  `WebhookDelivery.attempt_no` + `next_attempt_at` + `status(pending/success/failed/exhausted/simulated)`, and
  `WebhookSubscription.consecutive_failures` + an auto-disable threshold. A **human** presses Retry; the view
  bumps `attempt_no`, resets status to `pending`, and stamps `next_attempt_at` — **it does not fire HTTP**. That is
  the honest CRUD analogue and it is exactly what the prompt's "queued/status-tracked row" means · buildable now
- **Manual replay / bulk recover** — Svix offers single retry, "Recover Failed" since a date, and "Replay Missing". ·
  seen in: Svix · priority: **common** · spine: a POST `retry` action route on `WebhookDelivery` (single) — bulk
  recovery **deferred** · buildable now (single only)
- **Event-type filtering and payload field selection** — Shopify's `filter` params and `include_fields`; Svix
  endpoint filters. · seen in: Shopify, Svix · priority: **common** · spine:
  `WebhookSubscription.filter_expression` (CharField, e.g. `status=shipped`) + `include_fields` (CharField, csv) —
  recorded, not evaluated · **data now, evaluation later**
- **Custom request headers per subscription** — `crm.Webhook.headers` is a `JSONField` and does the job. · seen in:
  Shopify, Svix, crm (built) · priority: **common** · spine: `WebhookSubscription.headers` JSONField ·
  buildable now
- **Ordering is not guaranteed; reconcile separately** — Shopify says so outright and recommends a reconciliation
  job as backup. · priority: documentation, not a field · spine: note it in the model docstring so nobody builds
  order-dependent logic on the log

### Beyond the bullets — strong features the five bullets don't name

- **The exception cockpit: one filtered list of everything that failed, with a categorized error and a reprocess
  action** — the single most-emphasised capability across the whole survey. Cleo: *"detect, categorize, and resolve
  connectivity, data, and process issues"* + *"monitor transactions, partner activity, exceptions, anomalies … from a
  unified operational cockpit"*; Celigo: error management + "autonomous recovery tools"; Boomi: process reporting +
  error handling/retry. · priority: **table-stakes** · spine: **no new table** — a status-filtered
  `IntegrationMessage` list view (`status=failed`) + `error_code` / `error_message` fields + a POST reprocess action
  that flips the row back to `pending`. This is the highest-value page in the sub-module · buildable now
- **Auto-disable a persistently failing connection** — Svix disables an endpoint after 5 days of failures; Cleo
  flags "at-risk" transactions. · priority: **common** · spine: `consecutive_failures` counter +
  `status="error"`/`disabled` on both `IntegrationEndpoint` and `WebhookSubscription` · buildable now
- **Volume / throughput counters per connection** — messages in/out, last 24h, success rate; the number every
  dashboard in every product leads with. · priority: **common** · spine: **derived**, not stored — annotate over
  `IntegrationMessage` on the endpoint detail page, the way `scm.KpiSnapshot` consumers do · buildable now
- **API gateway proper: consumers, key auth, sliding-window rate limiting, request validation, developer portal** —
  Kong's whole feature set; Celigo and Workato both ship an API-management layer with rate limiting and a portal. ·
  priority: **table-stakes for a real gateway, but NavERP has no public API surface to put behind one** · spine:
  would be a `ApiConsumer` + `ApiKey` + `RateLimitPolicy` trio · **deferred** — building a gateway with nothing
  behind it is scaffolding, not a feature. When Module 13 or a public API lands, this is its own pass
- **Audit trail on configuration changes** — Workato "audit trails", Kong "audit logging for cluster configuration",
  Boomi governance. · priority: **common** · spine: **reuse the verified `core.AuditLog`**
  (`apps/core/models/AuditLog.py:5`, append-only, `changes` JSONField) — do **not** add a per-endpoint change log ·
  buildable now
- **Attachment of a partner spec / EDI implementation guide** — priority: **common** · spine: **reuse the verified
  `core.Document`** (`apps/core/models/Document.py:5`), the same call 4.12 made
  (`TradeDocuments.py:229`, `TradeLicenses.py:180`: *"No FileField anywhere in 4.12"*) · buildable now
- **AI/ML assistance: mapping suggestions, anomaly detection, conversational root-cause** — Boomi Suggest
  (*"10+ years of data"*), Cleo's AI exception workflows, Celigo's ML error management. · priority: **differentiator**
  · **deferred/integration**

---

## Which of the five bullets share a model — the compression decision

Five bullets must land in ≤4 models. **They compress 4 + 1, not 5 × 1.**

**Bullets 1, 2, 3 and 4 are the same object under four labels.** Strip away the marketing and an ERP connector, a
Shopify channel, an RFID reader gateway and an EDI trading-partner link are all: *a named external counterpart, a
direction, a transport, an identifier for the far end, a credential we must never store in the clear, an
enabled/disabled state, and a last-seen stamp.* The market itself models it this way — Cleo sells EDI, API and MFT
as one "connection" concept; Boomi puts B2B/EDI, API management and connectors on one platform object; and NavERP's
own **verified** `accounting.IntegrationConfig` already collapses banking, payments, tax, e-commerce, CRM, ERP,
HRIS and storage into `PROVIDER_CHOICES × CATEGORY_CHOICES` on **one** table. Splitting them into four near-identical
tables would produce four near-identical CRUD stacks, four seeders and four sets of templates that drift apart —
and would still not describe the domain any better than a `category` field does.

So: **one `IntegrationEndpoint` for bullets 1–4**, discriminated by `category ∈ {erp, ecommerce, iot, edi, custom}`,
with the handful of category-specific columns (`interchange_id`/`interchange_qualifier` for EDI,
`external_account_ref` for e-commerce, `device_identifier`+`location` for IoT) living as blank-able fields on the
one table. Precisely how `scm.ReturnAuthorization` carries source-specific columns rather than spawning a table per
return source.

And **one `IntegrationMessage` for bullets 1–4's traffic** — the append-only exchange log. An 850 sent to a
supplier, a Shopify order pulled in, an inventory feed pushed out and an RFID read batch ingested are one shape:
*(endpoint, direction, document type, timestamp, status, control/external id, record count, error, soft pointer to
the internal record)*. The document-type vocabulary differs; the table does not. This is also the table that makes
the sub-module *useful* rather than decorative — the exception cockpit, the acknowledgement tracker and the
end-to-end trace are all views over it.

**Bullet 5 genuinely does not fit.** A webhook subscription is not a connection to a system we integrate with; it is
a *rule that fires on an internal event*. Its identity is `(entity, event)`, not `(system, partner)`; its log rows
carry HTTP response codes and retry schedules, not control numbers and acknowledgements; and NavERP has a shipped
precedent (`crm.Webhook` + `crm.WebhookDelivery`) for exactly this pair. Forcing it into `IntegrationEndpoint` would
mean a `category="webhook"` row where `direction`, `transport`, `partner_party`, `interchange_id` and
`lifecycle_stage` are all meaningless — a nullable-column swamp. **Bullet 5 gets its own pair.**

**4 + 1 → 4 models.** No bullet is dropped and no table is invented for symmetry.

---

## Recommended build scope (this pass — 4 models)

Two full-CRUD configuration models + two append-only read-only logs. The effort profile is closer to "3 CRUD stacks"
than 4, because logs ship list + detail only (no form, no edit, no delete) per the
`crm.WebhookDelivery` / `MeterReading` precedent.

Package paths follow the mandatory structure: `apps/scm/{models,forms,views,urls}/IntegrationApiGateway/` with
entity files `IntegrationEndpoints.py`, `IntegrationMessages.py`, `WebhookSubscriptions.py`; templates under
`templates/scm/integration/<entity>/{list,detail,form}.html`.

### 1. `IntegrationEndpoint(TenantNumbered)` — `CNX-` — full CRUD
The one connector/config table for bullets 1–4.

- **Justified by:** typed vendor connections (Cleo/Celigo/Boomi/SPS/TrueCommerce) · connection status +
  last-success (Celigo/Boomi/Workato) · direction (Celigo Shopify↔NetSuite flows) · trigger mode (Celigo/Boomi) ·
  transport/protocol incl. LLRP/MQTT/AS2/SFTP/VAN (RFID middleware, Cleo) · trading-partner envelope identity
  (SPS/Cleo/TrueCommerce) · partner onboarding lifecycle + compliance stage (Cleo/SPS) · device registry with
  last-seen (Impinj/Zebra-class, Azure IoT Hub) · environment separation (Celigo/Boomi/Svix) · auto-disable on
  repeated failure (Svix).
- **Fields:** `name`, `category (erp·ecommerce·iot·edi·custom)`, `system (sap·oracle·netsuite·dynamics·shopify·
  magento·woocommerce·amazon·ebay·walmart·rfid_reader·barcode_scanner·sensor_gateway·edi_van·custom)`,
  `direction (inbound·outbound·bidirectional)`, `transport (api_rest·api_soap·webhook·sftp·ftps·as2·van·file_drop·
  mqtt·llrp·serial·manual)`, `auth_method (none·api_key·basic·oauth2·mtls·ssh_key)`, `endpoint_url` (blank; **SSRF
  WARNING comment**), `external_account_ref` (shop domain / seller id), `interchange_id`, `interchange_qualifier`,
  `device_identifier`, `trigger_mode (realtime·scheduled·manual)`, `schedule_note`,
  `environment (production·sandbox)`, `lifecycle_stage (setup·testing·certified·live·suspended)`,
  `status (disconnected·connected·error·disabled)`, `is_active`, `consecutive_failures` (`editable=False`),
  `last_run_at` / `last_success_at` / `last_seen_at` (all `editable=False`), `notes`.
- **Credential (never plaintext):** `credential_prefix` + `credential_hash`, both `editable=False`, set only by a
  POST `generate`/`rotate` action that shows the plaintext once. Copy
  `apps/accounting/models/Integration/IntegrationConfigs.py:36-53` and `apps/tenants/models/EncryptionKey.py:22-31`.
- **FKs (all verified to exist):** `tenant → core.Tenant` (via `TenantOwned`, `apps/scm/models/_base.py:58`) ·
  `partner_party → core.Party` (`apps/core/models/Party.py:5`, `SET_NULL`, null/blank) ·
  `logistics_client → scm.LogisticsClient` (`ThirdPartyLogistics/LogisticsClients.py:61`, `SET_NULL`, null/blank —
  reuses 4.17's shipped `edi_partner_id`/`edi_qualifier` rather than re-typing them) ·
  `location → scm.Location` (`InventoryManagement/Locations.py:14`, `SET_NULL`, null/blank — the zone an IoT reader
  watches).

### 2. `IntegrationMessage(TenantNumbered)` — `MSG-` — **append-only; list + detail only**
The exchange/transaction log for bullets 1–4, and the exception cockpit.

- **Justified by:** transaction visibility cockpit (Cleo) · process reporting (Boomi) · error management + reprocess
  (Celigo/Cleo) · the X12 document vocabulary 850/855/856/810/820/846/214/860/864/940/945/947/997 (EDI Basics, Cleo,
  SPS) · 997 acknowledgement tracking (Cleo/SPS/Boomi) · control numbers (all EDI vendors) · e-commerce flow types
  (Celigo Shopify–NetSuite) · RFID batch counts after dedupe (Impinj/Zebra-class) · external-id de-dupe (Shopify
  `X-Shopify-Webhook-Id`, Svix `eventId`) · internal-record correlation (Cleo/Celigo).
- **Fields:** `endpoint` FK, `direction (inbound·outbound)`,
  `document_type` — EDI members `edi_850·edi_855·edi_856·edi_810·edi_820·edi_846·edi_214·edi_860·edi_864·edi_940·
  edi_945·edi_947·edi_997` plus non-EDI `order_import·inventory_feed·fulfilment_export·item_export·refund_sync·
  customer_sync·tag_read_batch·scan_batch·sensor_reading·other`,
  `status (pending·sent·received·acknowledged·failed·ignored)`, `control_number`, `external_id`,
  `record_count`, `payload_excerpt` (**truncated — PII note in help_text**), `error_code`, `error_message`,
  `attempt_count` (`editable=False`), `occurred_at`, `acknowledged_at` (`editable=False`),
  `source` + `source_reference` — the **verified** scm soft-pointer idiom (`DemandSignals.py:74`), **not** a
  GenericForeignKey (banned: `ColdChainMonitors.py:18`, `PortalDocumentShares.py:9`).
- **FKs (verified):** `tenant` · `endpoint → scm.IntegrationEndpoint` (CASCADE) ·
  `acknowledges → self` (`SET_NULL`, null/blank — the 997 pointing at its 850) ·
  optional typed `sales_order → scm.SalesOrder` (`OrderManagement/SalesOrders.py:20`) and
  `purchase_order → scm.PurchaseOrder` (`ProcurementManagement/PurchaseOrders.py:15`), both `SET_NULL`/null/blank,
  for the two flows worth a joinable link.
- **Views:** list (filters: endpoint, category, direction, document_type, status, date) + detail + a **POST
  `reprocess` action** that sets `status="pending"` and bumps `attempt_count`. **No create/edit/delete form.**
- **Indexes:** `(tenant, status)`, `(tenant, endpoint)`, `(tenant, external_id)`, `(tenant, occurred_at)`.

### 3. `WebhookSubscription(TenantNumbered)` — `WHK-` — full CRUD
Bullet 5's configuration half.

- **Justified by:** topic + destination subscription (Shopify, Svix) · event-type subscription and filtering (Svix,
  Shopify `filter`/`include_fields`) · HMAC signing (Shopify `X-Shopify-Hmac-Sha256`, Svix) · custom headers
  (Shopify/Svix/crm) · active flag and auto-disable after sustained failure (Svix).
- **Fields:** `name`, `trigger_entity` — **SCM** vocabulary over verified classes: `purchase_order·goods_receipt·
  sales_order·shipment·stock_move·return_authorization·quality_inspection·work_order·asset·supply_chain_alert`,
  `trigger_event (created·updated·status_changed·approved·posted·cancelled·delivered)`, `target_url` (**SSRF
  WARNING**), `payload_format (json·xml)`, `filter_expression`, `include_fields`, `headers` (JSONField, default
  `dict`), `is_active`, `consecutive_failures` + `last_delivery_at` (both `editable=False`), `description`.
- **Signing secret (never plaintext):** `signing_secret_prefix` + `signing_secret_hash`, `editable=False`,
  generated + shown once on a POST `rotate_secret` action. **Explicitly NOT `crm.Webhook.secret`'s plaintext
  CharField** — that column is the anti-pattern this pass corrects.
- **FKs (verified):** `tenant → core.Tenant`. Nothing else — a subscription is about internal events.
- **Why not `crm.Webhook`:** its `trigger_entity` choices come from `crm.WorkflowRule.ENTITY_CHOICES`
  (`crm/models/AutomationWorkflow/Webhooks.py:3,17`) and cannot name an SCM entity. Documented decision, not drift.

### 4. `WebhookDelivery(TenantOwned)` — no number — **append-only; list + detail only**
Bullet 5's log half.

- **Justified by:** Svix `Attempts` (*"records of individual delivery tries … response status codes and content"*) ·
  Svix's published backoff schedule (immediate, 5s, 5min, 30min, 2h, 5h, 10h, 10h — 8 attempts / ~32h) and
  auto-disable-after-5-days · Svix single-message retry and replay · Shopify's no-ordering / not-guaranteed
  delivery caveat · the shipped `crm.WebhookDelivery` shape.
- **Fields:** `subscription` FK, `event` (CharField, e.g. `shipment.delivered`), `payload_excerpt`,
  `signature` (the HMAC hex of the payload — a *derived* value, not a credential), `status (pending·success·failed·
  exhausted·simulated)`, `attempt_no` (default 1), `next_attempt_at`, `response_code`, `error_message`,
  `triggered_at`.
- **FKs (verified):** `tenant` · `subscription → scm.WebhookSubscription` (CASCADE).
- **Views:** list (filters: subscription, status, date) + detail + a **POST `retry` action** that sets
  `status="pending"`, `attempt_no += 1`, and stamps `next_attempt_at` from the Svix-style backoff table.
  **It performs no HTTP request** — the model docstring must say so, exactly as `crm.WebhookDelivery`'s does.
  No create/edit/delete form.
- **Numbering:** none. Matches the verified high-volume-log convention (`StockMove`, `TemperatureReading`,
  `PortalActivity`, `KpiSnapshot`) and `crm.WebhookDelivery`.

### Fallback if the build wave needs to cut scope
Drop model 4. Fold deliveries into `IntegrationMessage` with `document_type="webhook_delivery"` and the subscription
carried in `source`/`source_reference`. It is muddier (HTTP response codes on an EDI-shaped row) and departs from
the shipped crm pair — take it only under clock pressure, never as the first choice.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Sensor / temperature telemetry rows** → **4.15** — `ColdChainMonitor` + `TemperatureReading` +
  `TemperatureExcursion` are built and own this. 4.19 records the ingestion batch, not the readings.
- **Asset meter/gauge readings** → **4.13** — `MeterReading` is built.
- **Carrier tracking events (EDI 214 content)** → **4.6** — `TrackingEvent` is built; 4.19 logs the 214 *message*,
  4.6 owns the *event*.
- **Per-3PL-client integration profile** → **4.17** — `LogisticsClient.integration_mode / client_system /
  edi_partner_id / edi_qualifier / last_synced_at` already shipped. 4.19 FKs the client; it does not re-declare them.
- **Trading-partner performance scorecards / compliance scoring** → **4.2** — `SupplierScorecard` is built.
- **Chargeback & deduction recovery** (SPS's revenue-recovery product) → **4.18 / accounting** — money owed sits in
  the accounting ledger; SCM must not grow a second one (L29).
- **Financial/banking/tax connectors** (Plaid, Stripe, Avalara, Vertex, QuickBooks) → **accounting 2.15**, already
  built as `accounting.IntegrationConfig`. 4.19 must not absorb them.
- **CRM-entity webhooks** (lead/opportunity/case events) → **crm 1.10**, already built as `crm.Webhook`.
- **Customer-facing portal delivery of documents** → **4.16** — `PortalDocumentShare` is built.
- **Item/product master catalogue that an e-commerce connector syncs** → **4.3** (`Item`, `ItemCategory`, `UOM`,
  built) and Module 5 long-term.
- **Alerting on integration failure as a supply-chain alert** → **4.11** — `SupplyChainAlert` is built; if a failed
  message should raise one, that is a 4.11 concern, not a new 4.19 table.

---

## Deferred (later passes / integrations)

- **Any actual transport.** Outbound HTTP, AS2, SFTP/FTPS, VAN, MQTT, SOAP. Django 5.1 server-rendered CRUD with no
  Celery, no queue, no worker — there is nothing to run a retry schedule. Every model here records *state a human
  manages*; `next_attempt_at` is a displayed intent, not a cron.
- **Field-level mapping / transformation designer** (`MappingProfile` + `MappingRule`) — Cleo's visual mapper, Boomi
  Suggest, Celigo's prebuilt mappings. Two more tables and a rule-editor UI; a whole pass of its own.
- **EDI envelope parsing/validation and 997 auto-generation** — needs an X12 parser. 4.19 stores the control number
  and the acknowledgement link; it does not read an ISA segment.
- **The inbound API gateway proper** — Kong-style consumers, key auth, sliding-window rate limits, request
  validation, developer portal. NavERP exposes no public API for a gateway to front. Revisit when one exists.
- **OAuth2 authorization-code flows and token storage** — access/refresh tokens are plaintext bearer credentials
  requiring a runtime that can refresh them. Record `auth_method="oauth2"`; store nothing.
- **Bulk recovery / replay-missing** (Svix "Recover Failed" since a date) — single-row retry ships; bulk is a later
  action.
- **Device twin desired-vs-reported config push** (Azure IoT Hub) — needs a per-device config table and a device
  that reads it.
- **A trading-partner network directory** — SPS's pre-built network is a *business*, not a table.
- **AI/ML: mapping suggestions, anomaly detection, conversational root-cause** (Boomi Suggest, Cleo AI workflows,
  Celigo ML error management) — differentiators across the market, all integration/later.
- **Sandbox↔production promotion and versioning** — `environment` ships as a field; deployment pipelines do not.
- **Payload archival and retention policy** — `payload_excerpt` is truncated by design; a real archive with a
  retention clock belongs with Module 13 (DMS).
