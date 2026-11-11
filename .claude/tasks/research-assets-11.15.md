# Research — Sub-module 11.15: Integration & API Hub (Module 11 — Asset Management System, `assets`)

- **Sub-module:** 11.15 Integration & API Hub
- **Module:** 11. Asset Management System
- **Target app:** `apps/assets` (package target: `apps/assets/models/IntegrationApiHub/`)
- **Research date:** 2026-11-11
- **Phase:** Phase 1 (Research Catalog)
- **Output file:** `.claude/tasks/research-assets-11.15.md`

---

## Repo state checked first

### 1. Module 11 `LIVE_LINKS` state (`apps/core/navigation.py`)
- **Built and live (`11.1`–`11.13`):**
  - `11.1` Asset Procurement & Acquisition (`AssetRequisition` `AREQ-`, `AssetAcquisitionReceipt` `ARCV-`, `AssetCapitalization` `ACAP-`, `AssetTag` `ATAG-`)
  - `11.2` Asset Inventory & Tracking (`AssetAudit` `AAUD-`, `AssetMovementLog` `AMOV-`, `AssetCustodyLog` `ACHK-`, `AssetIncidentReport` `AINC-`)
  - `11.3` Asset Classification & Categorization (`AssetCategory` `ACAT-`, `AssetModel` `AMOD-`, `AssetCriticalityAssessment` `ACRT-`, `AssetSpecificationTemplate` `ASPC-`)
  - `11.4` Depreciation & Financial Management (`CapitalizationPolicy` `ACTH-`, `AssetDepreciationSchedule` `ADEP-`, `AssetRevaluation` `AREV-`, `AssetTransfer` `AXFR-`)
  - `11.5` Maintenance & Repair Management (`AssetMaintenanceRequest` `AMRQ-`, `AssetMaintenanceSchedule` `AMSC-`, `AssetServiceContract` `ASVC-`, `AssetMaintenanceLog` `AMLG-`)
  - `11.6` Asset Performance & Utilization (`AssetDowntimeLog` `ADWN-`, `AssetOeeRecord` `AOEE-`, `AssetEnergyReading` `AENG-`, `AssetPerformanceScorecard` `APSC-`)
  - `11.7` Asset Reliability & Condition Monitoring (`AssetConditionAssessment` `ACAS-`, `AssetTelemetryReading` `ATEL-`, `AssetFailureMode` `AFMA-`, `AssetCalibrationRecord` `ACAL-`)
  - `11.8` Warranty & Insurance Management (`AssetWarranty` `AWAR-`, `AssetWarrantyClaim` `AWCL-`, `AssetInsurancePolicy` `AINS-`, `AssetInsuranceClaim` `AICL-`)
  - `11.9` Asset Disposal & Retirement (`AssetDisposalRequest` `ADSP-`, `AssetResaleListing` `ARSL-`, `AssetTradeIn` `ATRD-`, `AssetScrapSalvage` `ASCR-`)
  - `11.10` Lease & Rental Management (`AssetLeaseContract` `ALC-`, `AssetLeaseSchedule` `ALSP-`, `AssetLeaseModification` `ALMD-`, `AssetLeaseBuyAnalysis` `ALBA-`)
  - `11.11` Compliance & Regulatory Management (`AssetComplianceFramework` `ACF-`, `AssetComplianceAudit` `ACA-`, `AssetPermitLicense` `APL-`, `AssetComplianceIncident` `ACI-`)
  - `11.12` Asset Risk Management (`AssetRiskRegister` `ARK-`, `AssetBusinessContinuityPlan` `ABC-`, `AssetCyberSecurityProfile` `ACS-`, `AssetRiskMitigationAction` `ARMA-`)
  - `11.13` Mobile Asset Management (`MobileAssetInspection` `MINS-`, `FieldWorkOrder` `MFWO-`, `AssetScanLog` `ASCN-`, `AssetGeofenceEvent` `AGEO-`)
- **Unbuilt in Module 11:** `11.14` Asset Analytics & Business Intelligence is not built yet; `11.15` Integration & API Hub is explicitly scoped for this pass (and `11.16`–`11.19` remain unbuilt).
- **Latest migration in `apps/assets/migrations/`:** `0017_alter_assetcybersecurityprofile_cve_risk_score.py` (next migration will be `0018_*`).

### 2. Spine & sibling entities verified to exist (grep + file-read evidence)
| Entity | Verified Path & Class | Key Semantics for 11.15 |
|---|---|---|
| `scm.Asset` | `apps/scm/models/AssetManagement/Assets.py` (`Asset(TenantNumbered)`, `AST-`) | Operational equipment & machinery master target for telemetry streams & GIS spatial layers |
| `scm.Location` | `apps/scm/models/InventoryManagement/Locations.py` (`Location(TenantOwned)`) | Plant/warehouse/yard site linked to GIS feature layers & facility polygons |
| `scm.PurchaseOrder` | `apps/scm/models/ProcurementManagement/PurchaseOrders.py` (`PurchaseOrder(TenantNumbered)`, `PO-`) | CapEx & spare-parts POs synchronized with external ERP procurement |
| `accounting.FixedAsset` | `apps/accounting/models/FixedAssets/FixedAssetsRegister.py` (`FixedAsset(TenantNumbered)`, `FA-`) | Financial fixed asset subledger (cost, accumulated depreciation, GL accounts) |
| `accounting.JournalEntry` & `JournalLine` | `apps/accounting/models/GeneralLedger/JournalEntries.py` (`JournalEntry(TenantNumbered)`, `JE-`) | Authoritative GL journal header & balanced debit/credit lines |
| `accounting.GLAccount` | `apps/accounting/models/GeneralLedger/GLAccounts.py` (`GLAccount(TenantOwned)`) | Chart of Accounts target for asset posting & GL subledger reconciliation |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py` (`Currency(models.Model)`, global) | ISO 4217 currency reference (no tenant FK) |
| `accounting.FiscalPeriod` | `apps/accounting/models/GeneralLedger/FiscalPeriods.py` (`FiscalPeriod(TenantOwned)`) | Accounting period gating GL batch postings (`status="open"`) |
| `core.Party` | `apps/core/models/Party.py` (`Party(models.Model)`) | External system integrator, OEM telemetry vendor, or third-party service contractor |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py` (`OrgUnit(models.Model)`) | Cost center / branch / plant organization scope |
| `core.Document` | `apps/core/models/Document.py` (`Document(models.Model)`) | Optional technical interface specs / payload schemas (available if attached via DMS/core) |
| `accounts.User` | `settings.AUTH_USER_MODEL` | Integration owner, batch operator, telemetry stream steward |
| `assets.AssetTelemetryReading` | `apps/assets/models/AssetReliability/AssetTelemetryReadings.py` (`ATEL-`) | 11.7 condition reading ledger written to by 11.15 telemetry stream ingestion |
| `assets.AssetMaintenanceRequest` | `apps/assets/models/AssetMaintenance/AssetMaintenanceRequests.py` (`AMRQ-`) | 11.5 repair ticket triggered by 11.15 telemetry breach or synced with external CMMS |
| `assets.AssetMaintenanceLog` | `apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py` (`AMLG-`) | 11.5 repair log with labor/parts cost rolled up in GL sync batches |
| `assets.AssetDepreciationSchedule` | `apps/assets/models/AssetDepreciation/AssetDepreciationSchedules.py` (`ADEP-`) | 11.4 periodic depreciation schedule reconciled/posted via GL batches |
| `assets.AssetCapitalization` | `apps/assets/models/AssetProcurement/AssetCapitalizations.py` (`ACAP-`) | 11.1 CIP clearance & capitalization cost basis synced to ERP/GL |

### 3. Existing integration registers verified & L55 / L36 ownership ruling
Verified across `apps/` that **nine** domain-specific integration/webhook registers already exist:
1. `core` 0.13 (`apps/core/models/Integration.py`): `ApiCredential`, `RateLimitPolicy`, `ConnectorDefinition`, `MappingTemplate`, `SyncSchedule`
2. `accounting` 2.15 (`apps/accounting/models/Integration/IntegrationConfigs.py`): `IntegrationConfig`
3. `scm` 4.19 (`apps/scm/models/IntegrationApiGateway/`): `IntegrationEndpoint` [`CNX-`], `IntegrationMessage` [`MSG-`], `WebhookSubscription` [`WHK-`], `WebhookDelivery`
4. `inventory` 5.19 (`apps/inventory/models/ThirdPartyIntegrations/`): `IntegrationChannel` [`INT-`], `ChannelListingMap`, `StockSyncRun` [`SYN-`], `ApiClient` [`API-`]
5. `projects` 7.18 (`apps/projects/models/IntegrationApiHub/`): `ProjectIntegrationConnector` [`IXC-`], `ConnectorFieldMapping`, `ProjectSyncJob` [`SYJ-`], `ProjectSyncRun` [`SYR-`]
6. `sales` 8.18 (`apps/sales/models/IntegrationApiHub/`): `SalesIntegrationConnector` [`SIC-`], `SalesFieldMapping`, `SalesSyncJob` [`SSJ-`], `SalesSyncRun` [`SSR-`]
7. `ecommerce` 9.19 (`apps/ecommerce/models/IntegrationApi/`): `EcommerceConnector` [`ECON-`], `IntegrationSyncJob` [`ESYJ-`], `WebhookSubscription`, `ApiCredential` [`EAPI-`]
8. `bi` 10.19 (`apps/bi/models/IntegrationHub/`): `IntegrationConnector` [`BINT-`], `WarehouseSyncEndpoint` [`BSNC-`], `BiWebhookSubscription` [`BWHK-`], `BiExtensionPlugin` [`BEXT-`]
9. `crm` 1.10 (`apps/crm/models/AutomationWorkflow/Webhooks.py`): `Webhook` [`WH-`], `WebhookDelivery`

**L55 / L36 Coexistence Ruling for 11.15:**
- Under **L55** (coexistence under **L36**), NavERP intentionally avoids merging domain-specific integration registers into one generic table. None of the existing registers own **physical asset / EAM workflows**: CapEx PO & Fixed Asset ERP sync (SAP/Oracle/NetSuite/Dynamics), industrial OPC-UA / MQTT Sparkplug B / SCADA historian tag-to-`AssetTelemetryReading` streams, external CMMS work-order bridges (Maximo/HxGN/Fiix/MaintainX), Fixed Asset subledger-to-GL reconciliation batches, or Esri ArcGIS / Linear Referencing spatial feature synchronization.
- Sub-module `11.15` FKs **none** of the sibling integration registers, re-declares **none** of their class names, and performs **zero outbound HTTP** (all connector health pings, telemetry ingestion simulations, ERP/GL batch syncs, and GIS drift checks run deterministically in-process with honest `"simulated"` / diagnostic execution status and SSRF-safe configuration URLs).
- **Prefix Collision Check:** Audited all 619 `NUMBER_PREFIX` constants across `apps/`. The four selected prefixes — **`AICN`**, **`ATMS`**, **`AGLS`**, **`AGIS`** — and all four proposed model class names have **zero collisions** repo-wide.

---

## Leaders surveyed (with source links)

1. **IBM Maximo Integration Framework (MIF), Maximo Connector for SAP & Maximo Spatial** — Enterprise EAM integration engine built on Object Structures (hierarchical business-object schemas exposed over REST/JSON), Enterprise Services (inbound sync/async via JMS/Kafka), Publish Channels (outbound event-driven queues), SAP FI/CO/MM adapters, and Esri ArcGIS FeatureServer synchronization.
   - Sources: https://www.ibm.com/docs · https://www.ibm.com/products/maximo
2. **SAP S/4HANA Enterprise Asset Management (EAM)** — Native ERP-integrated asset management linking plant maintenance orders, cost centers, WBS settlements, procurement requisitions, OPC-UA IoT telemetry (SAP Asset Performance Management), and real-time FI-AA Fixed Asset General Ledger capitalization and depreciation.
   - Source: https://www.sap.com
3. **Oracle Fusion Cloud Maintenance & Oracle NetSuite Fixed Assets Management (FAM)** — SCM Maintenance REST endpoints (`/fscmRestApi/.../maintenanceWorkOrders`) feeding Cost Management rollup processors into Subledger Accounting (SLA) & GL, alongside NetSuite SuiteTalk FAM automated asset capitalization, depreciation schedules, and subsidiary segment mapping.
   - Sources: https://www.oracle.com · https://www.netsuite.com
4. **Microsoft Dynamics 365 Asset Management** — Links operational maintenance assets directly to Dynamics 365 Finance Fixed Assets, rolls up work order material/labor costs into WIP/capex adjustments, ingests Azure IoT counter triggers to spawn maintenance requests, and emits webhook-backed Business Events.
   - Source: https://www.microsoft.com
5. **HxGN EAM (Hexagon, formerly Infor EAM) & Databridge Pro / ArcGIS Integration** — Asset-intensive EAM featuring REST/Swagger APIs, Apache NiFi-powered Databridge Pro pipelines, bidirectional Esri ArcGIS Utility Network & Linear Referencing System (LRS) sync with full-compare drift detection.
   - Sources: https://hexagon.com/products/hxgn-eam · https://www.geo-nexus.com
6. **Fiix Integration Hub (Rockwell Automation)** — Centralized CMMS connectivity hub uniting OT/SCADA/PLC/DCS telemetry triggers (condition-based work orders) with bidirectional ERP spare-parts, PO, and invoice sync (`SAP`, `NetSuite`, `Workday`, `Infor`) plus pre-built IIoT partner connectors (`AVEVA`, `MachineMetrics`).
   - Sources: https://www.fiixsoftware.com/cmms-software/integrations/ · https://www.fiixsoftware.com/cmms-software/integrations/ot/
7. **MaintainX REST API & Webhooks + UpKeep Edge IoT** — Modern developer-first CMMS REST v1 (`https://api.getmaintainx.com/v1`) and HMAC-SHA256 signed event webhooks (`workorder.created`, `workorder.status_changed`) paired alongside turnkey wireless IoT/4G gateway telemetry (`UpKeep Edge`) feeding asset health tabs and threshold alerts.
   - Sources: https://api.getmaintainx.com/v1 · https://www.getmaintainx.com · https://www.onupkeep.com
8. **Inductive Automation Ignition SCADA, AVEVA PI System & OPC Foundation (OPC-UA / MQTT Sparkplug B)** — Industrial Unified Namespace (UNS) telemetry stack connecting PLCs via `opc.tcp://` OPC-UA endpoints, normalizing tags into ISA-95 `spBv1.0/<group>/<msg>/<node>/<device>` Sparkplug B MQTT payloads with Report-by-Exception (RBE) deadbands, and archiving into AVEVA PI Asset Framework (PI AF) to trigger CBM work orders.
   - Sources: https://opcfoundation.org · https://inductiveautomation.com · https://www.aveva.com
9. **Esri ArcGIS Enterprise & Utility Network / LRS** — Geospatial system of record exposing REST Feature Layers, GlobalID GUID reconciliation, point/polyline/polygon GeoJSON geometries, and Linear Referencing Systems (route ID + start/end measure) for utilities, pipelines, roads, and distributed infrastructure.
   - Sources: https://www.esri.com · https://www.arcgis.com

---

## Feature catalog (this sub-module only)

### ERP Integration
- **Named ERP Asset Connector Profiles** — Register SAP S/4HANA, Oracle Fusion, NetSuite FAM, and Dynamics 365 environments (`production`, `sandbox`, `staging`), protocol (`rest_json`, `odata_v4`, `soap_xml`), base endpoint config, external company/subsidiary scope ref, and sync direction. · seen in: IBM Maximo Connector for SAP, Oracle NetSuite, Fiix Hub · priority: `table-stakes` · spine: new table `AssetIntegrationConnector` [`AICN-`] (reuses `core.OrgUnit`, `accounting.Currency`, `core.Party`) · buildable now
- **CapEx Purchase Order & Acquisition Sync** — Synchronize capital equipment POs (`scm.PurchaseOrder`) and asset capitalization bases (`assets.AssetCapitalization`) between external ERP purchasing (SAP MM / Oracle Procurement) and NavERP asset registers using external batch references. · seen in: SAP S/4HANA EAM, Dynamics 365, Fiix Hub · priority: `table-stakes` · spine: new table `AssetGlSyncBatch` [`AGLS-`] (FKs `scm.PurchaseOrder`, `assets.AssetCapitalization`, `accounting.FixedAsset`) · buildable now
- **Object Structure / Field Attribute Mapping JSON** — Store hierarchical payload schema definitions and attribute cross-walks (e.g., mapping SAP `ANLA-ANLN1` or Maximo `MXASSET` fields to NavERP `FixedAsset`/`Asset` attributes). · seen in: IBM Maximo MIF Object Structures, HxGN EAM Databridge Pro · priority: `common` · spine: `object_structure_ref` on `AssetIntegrationConnector` + `field_mapping_json` on `AssetGlSyncBatch` · buildable now
- **Live Outbound ERP HTTP/RFC/IDoc Dispatcher** — Runtime transport worker invoking live SAP BAPI/OData or NetSuite SuiteTalk REST endpoints over network. · seen in: SAP PI/PO, Maximo MIF · priority: `common` · spine: deferred transport (in-app run records `"simulated"` status with zero outbound HTTP) · integration/later

### IoT & SCADA Systems
- **SCADA / IIoT Protocol & Broker Connector** — Configure OPC-UA server (`opc.tcp://`), MQTT Sparkplug B broker (`ssl://` / `tcps://`), Ignition SCADA gateway, AVEVA PI Web API, and UpKeep Edge wireless hubs with authentication posture and rate limits. · seen in: Ignition SCADA, AVEVA PI, UpKeep Edge, Fiix OT · priority: `table-stakes` · spine: `AssetIntegrationConnector` (`connector_category="iot_scada"`) · buildable now
- **Tag / Topic-to-Asset Telemetry Stream Binding** — Map external OPC-UA NodeIds (`ns=2;s=...`), Sparkplug B topics (`spBv1.0/...`), or PI AF attributes directly to `scm.Asset` and `accounting.FixedAsset` with metric type, unit, ingestion mode (`report_by_exception`, `polling_interval`, `streaming_pubsub`), polling cadence, and engineering scaling (`scale_factor`, `offset_value`, `deadband_delta`). · seen in: Ignition MQTT Engine, AVEVA PI Asset Framework, SAP APM · priority: `table-stakes` · spine: new table `AssetTelemetryStream` [`ATMS-`] (FKs `scm.Asset`, `accounting.FixedAsset`, `AssetIntegrationConnector`) · buildable now
- **Closed-Loop Condition-Based Maintenance (CBM) Trigger** — Evaluate incoming stream values against `baseline_value`, `warning_threshold`, and `critical_threshold`, persisting an `assets.AssetTelemetryReading` (11.7) and automatically creating/linking an `assets.AssetMaintenanceRequest` (11.5) when `auto_trigger_maintenance` is enabled and critical limits breach. · seen in: Fiix OT, UpKeep Edge, IBM Maximo Monitor, Dynamics 365 IoT · priority: `differentiator` · spine: `AssetTelemetryStream` writing to existing `assets.AssetTelemetryReading` (11.7) and `assets.AssetMaintenanceRequest` (11.5) · buildable now
- **Live Persistent OPC-UA / MQTT Daemon Subscriber** — Long-running async broker subscription worker ingesting sub-second Protobuf packets continuously. · seen in: Ignition Edge, HiveMQ · priority: `common` · spine: deferred background worker (in-app "Simulate / Ingest Telemetry Point" exercises the exact validation & 11.7/11.5 pipeline safely) · integration/later

### CMMS/EAM Connectivity
- **External CMMS Connector & MIF/REST Registry** — Configure connections to IBM Maximo MIF (`Enterprise Services` / `Publish Channels`), HxGN EAM REST/Databridge, Fiix CMMS, and MaintainX REST API v1 with environment isolation (`production`/`sandbox`) and external system identifiers. · seen in: IBM Maximo MIF, HxGN EAM, Fiix, MaintainX · priority: `table-stakes` · spine: `AssetIntegrationConnector` (`connector_category="cmms_eam"`) · buildable now
- **Maintenance Work Order & PM Workflow Sync Batch** — Track inbound/outbound synchronization batches between external CMMS work orders/service requests and `assets.AssetMaintenanceRequest` (11.5), capturing records processed/succeeded/failed, conflict diagnostics, and external batch IDs. · seen in: IBM Maximo MIF, Fiix Hub, MaintainX Webhooks · priority: `common` · spine: `AssetGlSyncBatch` (`sync_domain="cmms_work_order_sync"`, FK `assets.AssetMaintenanceRequest`) · buildable now
- **Inbound/Outbound Event Webhook Subscription Posture** — Register HMAC-SHA256 webhook endpoints (`workorder.created`, `telemetry.critical`, `asset.capitalized`) with write-only secret rotation and zero plaintext form leakage (L20/L25). · seen in: MaintainX Webhooks, Dynamics 365 Business Events · priority: `common` · spine: `AssetIntegrationConnector` (`connector_category="webhook_api"`, `api_key_prefix`/`api_key_hash`) · buildable now

### Financial Systems & General Ledger
- **Automated Depreciation & Capitalization GL Batching** — Link 11.4 `AssetDepreciationSchedule` (`ADEP-`) and 11.1 `AssetCapitalization` (`ACAP-`) records into governed GL posting batches targeting `accounting.FiscalPeriod`, `accounting.GLAccount` (debit/offset), `core.OrgUnit`, and `accounting.Currency`, generating/linking an authoritative `accounting.JournalEntry` (`JE-`) without creating a second ledger (L29). · seen in: SAP FI-AA, NetSuite FAM, Dynamics 365 Fixed Assets · priority: `table-stakes` · spine: `AssetGlSyncBatch` [`AGLS-`] (reuses `accounting.JournalEntry`, `accounting.GLAccount`, `accounting.FiscalPeriod`, `accounting.Currency`) · buildable now
- **Work Order Cost Rollup to GL / ERP** — Aggregate maintenance labor & spare-parts repair costs from `assets.AssetMaintenanceRequest` / `AssetMaintenanceLog` into GL expense or CIP overhaul postings (`sync_domain="work_order_cost_rollup"`). · seen in: Oracle Fusion Cost Management, Dynamics 365 Asset Management, SAP FI/CO · priority: `common` · spine: `AssetGlSyncBatch` (FK `assets.AssetMaintenanceRequest`, `accounting.GLAccount`, `accounting.JournalEntry`) · buildable now
- **Fixed Asset Subledger-to-GL Reconciliation** — Compare Asset Subledger carrying amount (`source_amount`) against General Ledger / external ERP account balance (`target_gl_amount`), computing exact `variance_amount` and flagging `matched` vs `variance_detected` for audit close. · seen in: SAP FI-AA Reconciliation, NetSuite FAM, Oracle SLA · priority: `table-stakes` · spine: `AssetGlSyncBatch` (`sync_domain="gl_subledger_reconciliation"`) · buildable now

### GIS & Mapping Tools
- **Spatial Feature Layer & Esri GlobalID Sync** — Map `scm.Asset` and `scm.Location` records to external GIS Feature Services (Esri ArcGIS Enterprise, Utility Network, GeoServer WFS, PostGIS) storing `feature_layer_name`, `external_global_id` (GUID), coordinate reference system (`coordinate_system_srid` e.g. `EPSG:4326`), `system_of_record`, and `sync_direction`. · seen in: IBM Maximo Spatial, HxGN EAM ArcGIS Integration, Geonexus · priority: `table-stakes` · spine: new table `AssetGisMapping` [`AGIS-`] (FKs `scm.Asset`, `scm.Location`, `core.OrgUnit`, `AssetIntegrationConnector`) · buildable now
- **Point, Polyline & Polygon GeoJSON Geometry Storage** — Capture `geometry_type` (`point`, `polyline`, `polygon`, `multipoint`), WGS84 coordinates (`latitude`, `longitude`, `elevation_meters`), and full `geojson_geometry` payloads for geographic asset visualization and spatial analysis. · seen in: Esri ArcGIS, IBM Maximo Spatial · priority: `common` · spine: fields on `AssetGisMapping` · buildable now
- **Linear Referencing System (LRS) Attributes** — Support linear infrastructure (pipelines, rail, transmission lines, roads) via `is_linear_asset`, `lrs_route_id`, `lrs_from_measure`, `lrs_to_measure`, and `lrs_measure_unit`. · seen in: Esri ArcGIS LRS, Maximo Linear Asset Manager, HxGN EAM · priority: `differentiator` · spine: fields on `AssetGisMapping` · buildable now
- **Spatial Full-Compare Drift Detection** — Audit spatial vs tabular alignment (`in_sync`, `geometry_drift`, `attribute_drift`, `unmatched_gis`, `unmatched_eam`) with in-app coordinate/LRS verification action. · seen in: Geonexus Integration Platform, HxGN EAM GIS · priority: `common` · spine: `drift_status` & verify action on `AssetGisMapping` · buildable now
- **Embedded Interactive Esri ArcGIS JS Web Map Canvas** — Live third-party basemap tile rendering requiring external ArcGIS API keys/JS SDK bundle. · seen in: Maximo Spatial Map Manager, HxGN EAM Maps · priority: `common` · spine: deferred UI SDK (data model stores coordinates + GeoJSON cleanly today) · integration/later

### Beyond the Bullets: Secret Security, SSRF Posture & Observability
- **Zero-Plaintext Credential Rotation & Pop-Once Reveal (L20 / L25)** — API keys, bearer tokens, and webhook HMAC secrets are stored strictly as `api_key_prefix` + SHA-256 `api_key_hash` (`editable=False`), excluded from every `ModelForm`, and issued/rotated only via a dedicated POST endpoint using a pop-once session key (`request.session["_aicn_secret_reveal"]`, never `messages.success`). · seen in: NavERP `accounting.IntegrationConfig`, `scm.IntegrationEndpoint`, `core.ApiCredential` · priority: `table-stakes` · spine: `AssetIntegrationConnector` · buildable now
- **SSRF-Safe Non-Fetching Endpoint Registry** — Connection strings (`https://`, `opc.tcp://`, `mqtts://`, `sftp://`) are validated as configuration metadata only; zero server-side outbound HTTP requests occur in this pass, and any future live transport requires RFC1918/loopback/link-local allow-list guards. · seen in: NavERP `scm.IntegrationEndpoint`, `projects.ProjectIntegrationConnector` · priority: `table-stakes` · spine: `AssetIntegrationConnector`, `AssetGisMapping` · buildable now

---

## Recommended build scope (this pass — 4 models)

All 4 models live under `apps/assets/models/IntegrationApiHub/`, inherit `TenantNumbered` (`apps/assets/models/_base.py`), strictly scope by `tenant`, use collision-free 4-letter `NUMBER_PREFIX` strings, obey L20/L22/L25/L65 (`max_length` >= longest choice value; `models.Index` & `UniqueConstraint` names <= 30 chars; system timestamps `editable=False`), and link cleanly to verified core/accounting/scm/assets models:

1. **`AssetIntegrationConnector`** [`AICN-`] (`AssetIntegrationConnectors.py`)
   - **Purpose:** Master registry for external ERP, IoT/SCADA, CMMS/EAM, Financial/GL, GIS, and Webhook/REST API endpoints powering Module 11 integrations.
   - **Fields & choices justified by:** Named ERP/CMMS/SCADA/GIS connectors, MIF Object Structure refs, rate limiting, L20/L25 secret security, SSRF-safe endpoint metadata, health pings:
     - `name` (`CharField(200)`), `connector_category` (`erp_procurement`, `cmms_eam`, `iot_scada`, `financial_gl`, `gis_spatial`, `webhook_api`; `max_length=24`), `provider` (`sap_s4hana`, `oracle_fusion`, `netsuite_fam`, `dynamics_365`, `ibm_maximo_mif`, `hxgn_eam`, `fiix_hub`, `maintainx_api`, `ignition_scada`, `aveva_pi`, `opcua_server`, `mqtt_sparkplug_b`, `upkeep_edge`, `esri_arcgis`, `geoserver_wfs`, `custom_webhook`; `max_length=32`), `protocol` (`rest_json`, `odata_v4`, `soap_xml`, `opc_ua`, `mqtt_sparkplug_b`, `arcgis_feature_rest`, `graphql`, `sftp_csv`; `max_length=24`)
     - `sync_direction` (`inbound`, `outbound`, `bidirectional`; `max_length=20`), `environment` (`production`, `sandbox`, `staging`; `max_length=20`)
     - `endpoint_url` (`CharField(500, blank=True)` — accepts `https://`, `opc.tcp://`, `mqtts://`; never dialed), `external_system_ref` (`CharField(150, blank=True)`), `object_structure_ref` (`CharField(150, blank=True)`)
     - `auth_method` (`none`, `api_key`, `oauth2_client`, `bearer_jwt`, `webhook_hmac`, `mtls_cert`, `opcua_x509`, `basic_auth`; `max_length=20`)
     - `api_key_prefix` (`CharField(16, blank=True, editable=False)`), `api_key_hash` (`CharField(64, blank=True, editable=False)`) — L20/L25 excluded from ModelForm
     - `rate_limit_rpm` (`PositiveIntegerField(default=600)`), `is_active` (`BooleanField(default=True)`), `status` (`draft`, `active`, `paused`, `error`, `decommissioned`; `max_length=20`), `health_status` (`untested`, `healthy`, `degraded`, `unreachable`; `max_length=20`)
     - `last_heartbeat_at`, `last_sync_at`, `consecutive_failures` (`editable=False` per L22), `last_error_message` (`TextField(blank=True, editable=False)`), `notes` (`TextField(blank=True)`)
   - **Verified FKs:** `tenant -> core.Tenant`, `vendor_partner -> core.Party` (null/blank), `default_org_unit -> core.OrgUnit` (null/blank), `default_currency -> accounting.Currency` (null/blank), `owner -> settings.AUTH_USER_MODEL` (null/blank)
   - **Indexes/Constraints (<=30 chars):** `assets_aicn_ten_num_uniq`, `idx_aicn_ten_cat`, `idx_aicn_ten_stat`, `idx_aicn_ten_hlth`
   - **Actions:** `test_connection` (POST -> simulated diagnostic ping updating `health_status` & `last_heartbeat_at`), `rotate_secret` (POST -> generates new secret, stores prefix+SHA-256 hash, reveals once in pop-once session key).

2. **`AssetTelemetryStream`** [`ATMS-`] (`AssetTelemetryStreams.py`)
   - **Purpose:** Maps industrial SCADA/IoT tags (OPC-UA NodeIds, MQTT Sparkplug B topics, Ignition/AVEVA PI paths) to plant equipment and drives condition-based ingestion into `assets.AssetTelemetryReading` (11.7) & `assets.AssetMaintenanceRequest` (11.5).
   - **Fields & choices justified by:** OPC-UA/MQTT Sparkplug B tag addressing, engineering unit scaling, RBE deadband, threshold alarms, CBM work-order creation:
     - `stream_name` (`CharField(200)`), `stream_protocol` (`opc_ua`, `mqtt_sparkplug_b`, `modbus_tcp`, `aveva_pi_webapi`, `ignition_tag_bus`, `rest_webhook`, `lorawan_gateway`; `max_length=24`)
     - `node_topic_address` (`CharField(255)`), `historian_tag_path` (`CharField(255, blank=True)`)
     - `metric_type` (`max_length=32`, aligns with `AssetTelemetryReading.METRIC_TYPE_CHOICES` + `runtime_hours`, `cycle_count`, `energy_kwh`), `metric_unit` (`max_length=20`, aligns with `AssetTelemetryReading.METRIC_UNIT_CHOICES` + `hours`, `cycles`, `kwh`)
     - `ingestion_mode` (`report_by_exception`, `polling_interval`, `edge_batch`, `streaming_pubsub`; `max_length=24`), `polling_interval_seconds` (`PositiveIntegerField(default=30)`)
     - `scale_factor` (`DecimalField(12, 4, default=1.0000)`), `offset_value` (`DecimalField(12, 4, default=0.0000)`), `deadband_delta` (`DecimalField(12, 4, default=0.0500)`)
     - `baseline_value`, `warning_threshold`, `critical_threshold` (`DecimalField(14, 4, null=True, blank=True)`)
     - `auto_trigger_maintenance` (`BooleanField(default=True)`), `stream_status` (`provisioning`, `streaming`, `stale_heartbeat`, `paused`, `faulted`; `max_length=20`), `is_active` (`BooleanField(default=True)`)
     - `last_ingested_value` (`DecimalField(14, 4, null=True, blank=True, editable=False)`), `last_ingested_at` (`DateTimeField(null=True, blank=True, editable=False)`), `readings_ingested_count` (`PositiveIntegerField(default=0, editable=False)`)
   - **Verified FKs:** `tenant -> core.Tenant`, `connector -> assets.AssetIntegrationConnector`, `operational_asset -> scm.Asset`, `fixed_asset -> accounting.FixedAsset` (null/blank), `last_telemetry_reading -> assets.AssetTelemetryReading` (null/blank, `editable=False`), `latest_maintenance_request -> assets.AssetMaintenanceRequest` (null/blank, `editable=False`), `steward -> settings.AUTH_USER_MODEL` (null/blank)
   - **Indexes/Constraints (<=30 chars):** `assets_atms_ten_num_uniq`, `idx_atms_ten_asset`, `idx_atms_ten_conn`, `idx_atms_ten_stat`
   - **Action:** `ingest_sample_reading` (POST -> scales raw value, creates `AssetTelemetryReading` [11.7], evaluates thresholds, optionally raises `AssetMaintenanceRequest` [11.5] when critical & `auto_trigger_maintenance=True`, updates read-only stream stats).

3. **`AssetGlSyncBatch`** [`AGLS-`] (`AssetGlSyncBatches.py`)
   - **Purpose:** Governs ERP CapEx procurement sync, CMMS work-order workflow/cost-rollup sync, automated depreciation/capitalization GL journal posting, and Fixed Asset subledger-to-GL reconciliation batches.
   - **Fields & choices justified by:** SAP FI-AA / Oracle SLA / NetSuite FAM / Dynamics Fixed Assets GL posting, work-order cost rollup, subledger reconciliation variance, CapEx PO sync, MIF attribute mapping:
     - `title` (`CharField(200)`), `sync_domain` (`depreciation_posting`, `capitalization_sync`, `work_order_cost_rollup`, `procurement_po_sync`, `cmms_work_order_sync`, `gl_subledger_reconciliation`; `max_length=32`)
     - `sync_direction` (`inbound`, `outbound`, `bidirectional`; `max_length=20`), `batch_date` (`DateField(default=timezone.now)` — user-set `DateField` per L22)
     - `external_batch_ref` (`CharField(120, blank=True)`), `field_mapping_json` (`JSONField(default=dict, blank=True)`)
     - `source_amount` (`DecimalField(16, 2, default=0.00)`), `target_gl_amount` (`DecimalField(16, 2, default=0.00)`), `variance_amount` (`DecimalField(16, 2, default=0.00, editable=False)`)
     - `reconciliation_status` (`unreconciled`, `matched`, `variance_detected`, `adjusted`, `not_applicable`; `max_length=24`), `status` (`draft`, `queued`, `simulated`, `posted_reconciled`, `variance_flagged`, `failed`; `max_length=24`)
     - `records_processed`, `records_succeeded`, `records_failed` (`PositiveIntegerField(default=0, editable=False)`), `synced_at` (`DateTimeField(null=True, blank=True, editable=False)`), `execution_notes` (`TextField(blank=True)`)
   - **Verified FKs:** `tenant -> core.Tenant`, `connector -> assets.AssetIntegrationConnector` (null/blank), `fiscal_period -> accounting.FiscalPeriod` (null/blank), `gl_account -> accounting.GLAccount` (null/blank), `offset_gl_account -> accounting.GLAccount` (null/blank), `journal_entry -> accounting.JournalEntry` (null/blank, `editable=False`), `fixed_asset -> accounting.FixedAsset` (null/blank), `purchase_order -> scm.PurchaseOrder` (null/blank), `capitalization -> assets.AssetCapitalization` (null/blank), `depreciation_schedule -> assets.AssetDepreciationSchedule` (null/blank), `maintenance_request -> assets.AssetMaintenanceRequest` (null/blank), `cost_center -> core.OrgUnit` (null/blank), `currency -> accounting.Currency` (null/blank), `executed_by -> settings.AUTH_USER_MODEL` (null/blank, `editable=False`)
   - **Indexes/Constraints (<=30 chars):** `assets_agls_ten_num_uniq`, `idx_agls_ten_dom`, `idx_agls_ten_stat`, `idx_agls_ten_rec`
   - **Action:** `execute_reconcile_batch` (POST -> computes `variance_amount`, resolves `reconciliation_status`, optionally creates balanced `accounting.JournalEntry` + two `JournalLine`s when posting eligible balanced batch to open `FiscalPeriod`, or stamps `"simulated"` ERP/CMMS sync).

4. **`AssetGisMapping`** [`AGIS-`] (`AssetGisMappings.py`)
   - **Purpose:** Synchronizes physical assets and plant/utility locations with GIS feature layers (Esri ArcGIS, GeoServer, PostGIS), capturing point/polyline/polygon GeoJSON geometries, Linear Referencing (LRS) measures, and spatial drift state.
   - **Fields & choices justified by:** Esri ArcGIS FeatureServer GlobalID sync, SRID coordinate systems, point/linear/polygon GeoJSON, LRS route & milepost measures, Geonexus/HxGN full-compare drift audit:
     - `title` (`CharField(200)`), `feature_layer_name` (`CharField(150)`), `external_global_id` (`CharField(120, blank=True)`)
     - `geometry_type` (`point`, `polyline`, `polygon`, `multipoint`; `max_length=20`), `coordinate_system_srid` (`CharField(32, default="EPSG:4326")`)
     - `latitude` (`DecimalField(9, 6, null=True, blank=True)`), `longitude` (`DecimalField(9, 6, null=True, blank=True)`), `elevation_meters` (`DecimalField(10, 2, null=True, blank=True)`)
     - `is_linear_asset` (`BooleanField(default=False)`), `lrs_route_id` (`CharField(100, blank=True)`), `lrs_from_measure` (`DecimalField(12, 3, null=True, blank=True)`), `lrs_to_measure` (`DecimalField(12, 3, null=True, blank=True)`), `lrs_measure_unit` (`km`, `miles`, `meters`, `feet`; `max_length=16`)
     - `geojson_geometry` (`JSONField(default=dict, blank=True)`), `spatial_zone_label` (`CharField(120, blank=True)`)
     - `system_of_record` (`gis_master`, `eam_master`, `split_spatial_gis`; `max_length=24`), `sync_direction` (`inbound`, `outbound`, `bidirectional`; `max_length=20`)
     - `drift_status` (`in_sync`, `geometry_drift`, `attribute_drift`, `unmatched_gis`, `unmatched_eam`; `max_length=24`), `status` (`draft`, `active`, `sync_pending`, `synced`, `conflict`, `retired`; `max_length=20`)
     - `last_spatial_sync_at` (`DateTimeField(null=True, blank=True, editable=False)`), `notes` (`TextField(blank=True)`)
   - **Verified FKs:** `tenant -> core.Tenant`, `connector -> assets.AssetIntegrationConnector` (null/blank), `operational_asset -> scm.Asset`, `location -> scm.Location` (null/blank), `org_unit -> core.OrgUnit` (null/blank), `gis_custodian -> settings.AUTH_USER_MODEL` (null/blank)
   - **Indexes/Constraints (<=30 chars):** `assets_agis_ten_num_uniq`, `idx_agis_ten_asset`, `idx_agis_ten_drift`, `idx_agis_ten_stat`
   - **Action:** `verify_spatial_sync` (POST -> checks coordinate/LRS validity and `external_global_id` presence, updates `drift_status`, `status`, and `last_spatial_sync_at`).

### Recommended `LIVE_LINKS["11.15"]` Navigation Mapping
All 5 `NavERP.md` §11.15 bullets mapped byte-identically to distinct targets (plus operational extra leaves):
- `"ERP Integration"` -> `"assets:asset_integration_connector_list?connector_category=erp_procurement"`
- `"IoT & SCADA Systems"` -> `"assets:asset_telemetry_stream_list"`
- `"CMMS/EAM Connectivity"` -> `"assets:asset_integration_connector_list?connector_category=cmms_eam"`
- `"Financial Systems & General Ledger"` -> `"assets:asset_gl_sync_batch_list"`
- `"GIS & Mapping Tools"` -> `"assets:asset_gis_mapping_list"`
- Extra operational leaves: `"Integration Connectors"` (`assets:asset_integration_connector_list`), `"Telemetry Streams"` (`assets:asset_telemetry_stream_list`), `"GL & ERP Sync Batches"` (`assets:asset_gl_sync_batch_list`), `"GIS Spatial Mappings"` (`assets:asset_gis_mapping_list`).

---

## Belongs to sibling sub-modules (parked, not scoped here)
- **Raw Sensor Condition Readings, NDT & FMEA/RCM Analysis** -> `11.7` (`AssetTelemetryReading`, `AssetFailureMode`)
- **OT/ICS Purdue Network Zoning & CVE Patching** -> `11.12` (`AssetCyberSecurityProfile`)
- **Mobile Yard Geofencing Breaches & Barcode/RFID Scans** -> `11.13` (`AssetGeofenceEvent`, `AssetScanLog`)
- **Depreciation Formulas, Revaluations & Inter-Dept Transfers** -> `11.4` (`AssetDepreciationSchedule`, `AssetRevaluation`, `AssetTransfer`)
- **Maintenance Work Order Execution & PM Calendars** -> `11.5` (`AssetMaintenanceRequest`, `AssetMaintenanceSchedule`, `AssetMaintenanceLog`)
- **TCO Lifecycle Analytics & Replacement Forecasting** -> `11.14` (next/unbuilt analytics sub-module)
- **Engineering Schematics, CAD/BIM & SOP Repository** -> `11.16` (Document & Knowledge Management)
- **Fleet Telematics, Fuel Cards & Route Telemetry** -> `11.19` (Fleet & Vehicle Management)
- **Platform-Wide API Credentials, Rate Limits & Marketplace** -> `0.13` (`core.ApiCredential`, `core.RateLimitPolicy`, `core.ConnectorDefinition`)
- **SCM EDI/3PL, Accounting Configs, Sales/Projects/BI Hubs** -> `4.19`, `2.15`, `5.19`, `7.18`, `8.18`, `9.19`, `10.19` (coexisting per L55)

---

## Deferred (later passes / integrations)
- **Outbound HTTP / SAP RFC / SOAP / OData Transport Workers** — Production gateway workers enforcing RFC1918/SSRF allow-lists and exponential backoff queues; current build executes deterministic in-process `"simulated"` diagnostics with zero outbound network calls.
- **Persistent OPC-UA & MQTT Sparkplug B Daemon Subscribers** — Always-on industrial edge collectors streaming continuous sub-second telemetry packets into `AssetTelemetryReading`.
- **Reversible Encrypted Token Vault Upgrade (`apps.core.crypto` Fernet)** — Migrating `api_key_prefix`/`api_key_hash` markers to Fernet-encrypted reversible tokens when live OAuth2 token refresh and outbound HMAC payload signing ship.
- **Interactive Esri ArcGIS JS / Leaflet Map Tile Widget** — Browser-side basemap visualization SDK consuming `AssetGisMapping.geojson_geometry` and coordinates.
