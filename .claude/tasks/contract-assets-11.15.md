# Module 11.15 Pre-Build Contract — Integration & API Hub (`apps/assets/`)

> Frozen before Phase 3 Entity Build. Every model field, `max_length`, `CHOICES` tuple,
> badge class, index/constraint name (<=30 chars), form `Meta.fields` whitelist, URL pattern,
> view context key, cross-module helper rule, and `LIVE_LINKS["11.15"]` entry below is
> authoritative across backend, templates, smoke verification, code review, and tests.

- **Parent App**: `apps.assets` (existing app; NO scaffold; NO `config/settings.py` or `config/urls.py` edit)
- **Previous Migration**: `0017_alter_assetcybersecurityprofile_cve_risk_score`
- **Next Migration**: `0018_...`
- **Package Directories**:
  - `apps/assets/models/IntegrationApiHub/`
  - `apps/assets/forms/IntegrationApiHub/`
  - `apps/assets/views/IntegrationApiHub/`
  - `apps/assets/urls/IntegrationApiHub/`
  - `templates/assets/integrationapihub/{asset_integration_connector,asset_telemetry_stream,asset_gl_sync_batch,asset_gis_mapping}/`
- **L55 Zero-FK Coexistence Rule**: Do NOT FK, import, or modify sibling integration tables (`core` 0.13, `accounting` 2.15, `scm` 4.19, `inventory` 5.19, `projects` 7.18, `sales` 8.18, `ecommerce` 9.19, `bi` 10.19, `crm` 1.10).
- **L66 AuditLog Action Max Length (`<= 10` chars)**: `apps.core.models.AuditLog.action` has `max_length=10`. Always pass `action` in `{"create", "update", "delete", "test", "rotate", "ingest", "reconcile", "verify"}` (all `<= 9` chars) to `write_audit_log(request.user, obj, action, changes=..., tenant=request.tenant)`.
- **Theme CSS Classes (`static/css/theme.css`)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`. (NO `badge-purple`, NO `badge-success`/`warning`/`danger`).
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`. (NO `amber` — use `orange`).
  - Detail pages use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.

---

## 1. Models & Choices Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (provides `tenant`, `number`, `created_at`, `updated_at`, auto-minting `PREFIX-00001` via `next_number(width=5)`).

### 1.1 `AssetIntegrationConnector` (`AssetIntegrationConnectors.py`)
- **`NUMBER_PREFIX`**: `"AICN"`
- **`Meta.db_table`**: default (`assets_assetintegrationconnector`), `ordering = ["number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Asset Integration Connector"` / `"Asset Integration Connectors"`
- **Constants / Choices / Badge Maps**:
  - `CATEGORY_CHOICES`:
    - `("erp_procurement", "ERP & Procurement")`
    - `("iot_scada", "IoT & SCADA Systems")`
    - `("cmms_eam", "CMMS / EAM Connectivity")`
    - `("financial_gl", "Financial Systems & GL")`
    - `("gis_spatial", "GIS & Mapping Tools")`
  - `PROVIDER_CHOICES`:
    - `("sap_s4hana", "SAP S/4HANA")`
    - `("oracle_fusion", "Oracle Fusion Cloud")`
    - `("netsuite", "Oracle NetSuite")`
    - `("microsoft_d365", "Microsoft Dynamics 365")`
    - `("maximo_eam", "IBM Maximo EAM")`
    - `("infor_eam", "Infor EAM")`
    - `("fiix", "Fiix CMMS")`
    - `("osisoft_pi", "AVEVA / OSIsoft PI")`
    - `("kepware_opcua", "Kepware OPC-UA")`
    - `("esri_arcgis", "Esri ArcGIS")`
    - `("qgis_postgis", "QGIS / PostGIS")`
    - `("custom_webhook", "Custom Webhook / API")`
  - `PROTOCOL_CHOICES`:
    - `("rest_json", "REST / JSON")`
    - `("odata_v4", "OData v4")`
    - `("opc_ua", "OPC-UA")`
    - `("mqtt_tls", "MQTT over TLS")`
    - `("modbus_tcp", "Modbus TCP")`
    - `("graphql", "GraphQL")`
    - `("sftp_csv", "SFTP / CSV")`
    - `("arcgis_feature_svc", "ArcGIS Feature Service")`
  - `SYNC_DIRECTION_CHOICES`:
    - `("inbound", "Inbound")`
    - `("outbound", "Outbound")`
    - `("bidirectional", "Bidirectional")`
  - `ENVIRONMENT_CHOICES`:
    - `("production", "Production")`
    - `("staging", "Staging")`
    - `("sandbox", "Sandbox")`
  - `AUTH_METHOD_CHOICES`:
    - `("api_key", "API Key")`
    - `("oauth2_client", "OAuth 2.0 Client Credentials")`
    - `("mtls_cert", "Mutual TLS (mTLS)")`
    - `("hmac_sha256", "HMAC-SHA256 Signature")`
    - `("basic_vault", "Vault-Backed Basic Auth")`
  - `STATUS_CHOICES`:
    - `("draft", "Draft")`
    - `("active", "Active")`
    - `("paused", "Paused")`
    - `("error", "Error")`
    - `("decommissioned", "Decommissioned")`
  - `HEALTH_STATUS_CHOICES`:
    - `("healthy", "Healthy")`
    - `("degraded", "Degraded")`
    - `("unreachable", "Unreachable")`
    - `("unverified", "Unverified")`
  - `STATUS_BADGE_MAP`:
    - `"draft": "badge-slate"`, `"active": "badge-green"`, `"paused": "badge-amber"`, `"error": "badge-red"`, `"decommissioned": "badge-muted"`
  - `HEALTH_BADGE_MAP`:
    - `"healthy": "badge-green"`, `"degraded": "badge-amber"`, `"unreachable": "badge-red"`, `"unverified": "badge-slate"`
  - `ALLOWED_ENDPOINT_SCHEMES = {"https", "http", "opc.tcp", "mqtts", "mqtt", "tcps", "sftp", "wss"}`
- **Fields**:
  - `name`: `CharField(max_length=160)`
  - `connector_category`: `CharField(max_length=24, choices=CATEGORY_CHOICES, default="erp_procurement")`
  - `provider`: `CharField(max_length=32, choices=PROVIDER_CHOICES, default="custom_webhook")`
  - `protocol`: `CharField(max_length=24, choices=PROTOCOL_CHOICES, default="rest_json")`
  - `sync_direction`: `CharField(max_length=20, choices=SYNC_DIRECTION_CHOICES, default="bidirectional")`
  - `environment`: `CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default="sandbox")`
  - `endpoint_url`: `CharField(max_length=500)` *(NOT `URLField`; validated via `validate_connector_endpoint_url`)*
  - `auth_method`: `CharField(max_length=20, choices=AUTH_METHOD_CHOICES, default="api_key")`
  - `api_key_prefix`: `CharField(max_length=12, blank=True, editable=False)`
  - `api_key_hash`: `CharField(max_length=128, blank=True, editable=False)`
  - `rate_limit_rpm`: `PositiveIntegerField(default=120)`
  - `timeout_seconds`: `PositiveIntegerField(default=30)`
  - `retry_policy_max`: `PositiveSmallIntegerField(default=3)`
  - `polling_interval_minutes`: `PositiveIntegerField(default=15)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`
  - `health_status`: `CharField(max_length=20, choices=HEALTH_STATUS_CHOICES, default="unverified", editable=False)`
  - `vendor_partner`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_integration_connectors")`
  - `default_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_integration_connectors")`
  - `default_currency`: `ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_integration_connectors")` *(GLOBAL — no tenant)*
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_asset_connectors")`
  - `last_heartbeat_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `last_sync_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `consecutive_failures`: `PositiveIntegerField(default=0, editable=False)`
  - `last_error_message`: `TextField(blank=True, editable=False)`
  - `webhook_verify_tls`: `BooleanField(default=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_aicn_ten_num_uniq")` *(24 chars)*
  - `Index(fields=["tenant", "connector_category"], name="idx_aicn_ten_cat")` *(16 chars)*
  - `Index(fields=["tenant", "status"], name="idx_aicn_ten_stat")` *(17 chars)*
  - `Index(fields=["tenant", "health_status"], name="idx_aicn_ten_hlth")` *(17 chars)*
- **Validation (`validate_connector_endpoint_url` + `clean()`)**:
  - Require valid scheme in `ALLOWED_ENDPOINT_SCHEMES`, non-empty `parsed.hostname`, zero whitespace/control characters (`\r`, `\n`, `\t`, spaces).
  - Reject SSRF targets in ALL environments: hostnames `localhost`, `localhost.localdomain`, `127.0.0.1`, `::1`, `0.0.0.0`, `metadata.google.internal`, `169.254.169.254`, suffixes `.local`, `.internal`, `.localhost`, and any literal IP (`ipaddress.ip_address`) where `is_private`, `is_loopback`, `is_link_local`, `is_multicast`, `is_reserved`, or `is_unspecified` is True.
  - Require `rate_limit_rpm >= 1`, `timeout_seconds >= 1`, `polling_interval_minutes >= 1`.
- **`__str__`**: `f"{self.number} · {self.name}"`
- **Badge / Credential Helpers**:
  - `status_badge_class` property returning `STATUS_BADGE_MAP.get(self.status, "badge-slate")`
  - `health_badge_class` property returning `HEALTH_BADGE_MAP.get(self.health_status, "badge-slate")`
  - `issue_new_secret()` helper on model: mints `"aicn_" + secrets.token_urlsafe(24)` (or 32-char token), stores `api_key_prefix = plaintext[:6]` (actually `"aicn_"` + prefix chars: e.g. `plaintext[:12]` fits `max_length=12`, wait: store `plaintext[:12]` or `plaintext[:6]`? Let's store `plaintext[:12]`? Wait: `todo.md` says "prefix (first 6 chars)", `research` says 6-8 chars; `"aicn_" + secrets.token_urlsafe(24)` where `plaintext[:8]` keeps prefix useful (`aicn_XXX`) AND within `max_length=12`, OR set `api_key_prefix = plaintext[:8]`, `api_key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()`! Let's freeze `api_key_prefix = plaintext[:8]` and `api_key_hash = SHA-256 hex`!).

---

### 1.2 `AssetTelemetryStream` (`AssetTelemetryStreams.py`)
- **`NUMBER_PREFIX`**: `"ATMS"`
- **`Meta.ordering`**: `["number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Asset Telemetry Stream"` / `"Asset Telemetry Streams"`
- **Constants / Choices / Badge Maps**:
  - `STREAM_PROTOCOL_CHOICES`:
    - `("opc_ua_node", "OPC-UA Node")`
    - `("mqtt_topic", "MQTT Topic")`
    - `("modbus_register", "Modbus Register")`
    - `("pi_tag", "OSIsoft PI Tag")`
    - `("bacnet_object", "BACnet Object")`
    - `("rest_webhook_key", "REST Webhook Payload Key")`
  - `METRIC_TYPE_CHOICES`:
    - `("vibration_velocity_rms", "Vibration Velocity (RMS)")`
    - `("vibration_peak_accel", "Vibration Peak Acceleration")`
    - `("bearing_temperature", "Bearing Temperature")`
    - `("acoustic_ultrasound", "Acoustic Ultrasound")`
    - `("operating_pressure", "Operating Pressure")`
    - `("oil_dielectric_viscosity", "Oil Dielectric / Viscosity")`
    - `("motor_current_amperage", "Motor Current (Amperage)")`
    - `("ambient_temperature", "Ambient Temperature")`
    - `("runtime_hours", "Operating Runtime Hours")`
    - `("cycle_count", "Equipment Cycle Count")`
    - `("energy_kwh", "Energy Consumption (kWh)")`
  - `METRIC_UNIT_CHOICES`:
    - `("mm_per_s", "mm/s")`
    - `("g_force", "g")`
    - `("celsius", "deg C")`
    - `("fahrenheit", "deg F")`
    - `("decibel_uv", "dBuV")`
    - `("bar", "bar")`
    - `("psi", "psi")`
    - `("amperes", "A")`
    - `("viscosity_cst", "cSt")`
    - `("hours", "hrs")`
    - `("cycles", "cycles")`
    - `("kwh", "kWh")`
  - `INGESTION_MODE_CHOICES`:
    - `("streaming_pubsub", "Streaming Pub/Sub")`
    - `("polling", "Scheduled Polling")`
    - `("edge_batch_store", "Edge Store-and-Forward")`
    - `("manual_sample", "Manual Sample Capture")`
  - `STREAM_STATUS_CHOICES`:
    - `("active", "Active")`
    - `("paused", "Paused")`
    - `("faulted", "Faulted")`
    - `("decommissioned", "Decommissioned")`
  - `STREAM_STATUS_BADGE_MAP`:
    - `"active": "badge-green"`, `"paused": "badge-amber"`, `"faulted": "badge-red"`, `"decommissioned": "badge-muted"`
  - **11.7 Cross-Module Metric Mapping (`AssetTelemetryReading` accepts ONLY 8 metric types & 9 units)**:
    - Valid `AssetTelemetryReading` metric types: `{"vibration_velocity_rms", "vibration_peak_accel", "bearing_temperature", "acoustic_ultrasound", "operating_pressure", "oil_dielectric_viscosity", "motor_current_amperage", "ambient_temperature"}`
    - Valid `AssetTelemetryReading` metric units: `{"mm_per_s", "g_force", "celsius", "fahrenheit", "decibel_uv", "bar", "psi", "amperes", "viscosity_cst"}`
    - Stream-only mapping:
      - `"runtime_hours"` -> `("motor_current_amperage", "amperes")`
      - `"cycle_count"` -> `("vibration_peak_accel", "g_force")`
      - `"energy_kwh"` -> `("motor_current_amperage", "amperes")`
      - Fallback for any unmapped unit paired with a valid 11.7 metric: `{"hours": "celsius", "cycles": "g_force", "kwh": "amperes"}`
- **Fields**:
  - `connector`: `ForeignKey("assets.AssetIntegrationConnector", on_delete=models.PROTECT, related_name="telemetry_streams")`
  - `operational_asset`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="integration_telemetry_streams")`
  - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="integration_telemetry_streams")`
  - `tag_address`: `CharField(max_length=160)`
  - `stream_name`: `CharField(max_length=160)`
  - `stream_protocol`: `CharField(max_length=24, choices=STREAM_PROTOCOL_CHOICES, default="opc_ua_node")`
  - `metric_type`: `CharField(max_length=32, choices=METRIC_TYPE_CHOICES, default="bearing_temperature")`
  - `metric_unit`: `CharField(max_length=20, choices=METRIC_UNIT_CHOICES, default="celsius")`
  - `ingestion_mode`: `CharField(max_length=24, choices=INGESTION_MODE_CHOICES, default="polling")`
  - `polling_interval_seconds`: `PositiveIntegerField(default=60)`
  - `deadband_delta`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"))`
  - `scale_factor`: `DecimalField(max_digits=12, decimal_places=6, default=Decimal("1.000000"))`
  - `offset_value`: `DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0000"))`
  - `baseline_value`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `warning_threshold`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `critical_threshold`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `auto_trigger_maintenance`: `BooleanField(default=True)`
  - `stream_status`: `CharField(max_length=20, choices=STREAM_STATUS_CHOICES, default="active")`
  - `last_ingested_value`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, editable=False)`
  - `last_ingested_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `readings_ingested_count`: `PositiveIntegerField(default=0, editable=False)`
  - `last_telemetry_reading`: `ForeignKey("assets.AssetTelemetryReading", on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="source_integration_streams")`
  - `latest_maintenance_request`: `ForeignKey("assets.AssetMaintenanceRequest", on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="triggered_by_streams")`
  - `steward`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="stewarded_telemetry_streams")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_atms_ten_num_uniq")` *(24 chars)*
  - `Index(fields=["tenant", "operational_asset"], name="idx_atms_ten_asset")` *(18 chars)*
  - `Index(fields=["tenant", "connector"], name="idx_atms_ten_conn")` *(17 chars)*
  - `Index(fields=["tenant", "stream_status"], name="idx_atms_ten_stat")` *(17 chars)*
- **Validation (`clean()`)**:
  - `polling_interval_seconds >= 1`
  - `scale_factor != Decimal("0")`
  - `deadband_delta >= Decimal("0")`
  - If both `warning_threshold` and `critical_threshold` are not None: require `critical_threshold >= warning_threshold`
- **`__str__`**: `f"{self.number} · {self.stream_name}"`

---

### 1.3 `AssetGlSyncBatch` (`AssetGlSyncBatches.py`)
- **`NUMBER_PREFIX`**: `"AGLS"`
- **`Meta.ordering`**: `["-batch_date", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Asset GL Sync Batch"` / `"Asset GL Sync Batches"`
- **Constants / Choices / Badge Maps**:
  - `SYNC_DOMAIN_CHOICES`:
    - `("depreciation_posting", "Depreciation Posting")`
    - `("capitalization_sync", "Capitalization Sync")`
    - `("work_order_cost_rollup", "Work Order Cost Rollup")`
    - `("asset_subledger_sync", "Asset Subledger Sync")`
    - `("po_asset_clearing", "PO Asset Clearing")`
  - `SYNC_DIRECTION_CHOICES`:
    - `("inbound", "Inbound")`
    - `("outbound", "Outbound")`
    - `("bidirectional", "Bidirectional")`
  - `RECONCILIATION_STATUS_CHOICES`:
    - `("pending", "Pending")`
    - `("reconciled", "Reconciled")`
    - `("variance_flagged", "Variance Flagged")`
    - `("resolved", "Resolved")`
  - `STATUS_CHOICES`:
    - `("draft", "Draft")`
    - `("ready", "Ready")`
    - `("posted", "Posted")`
    - `("simulated", "Simulated")`
    - `("failed", "Failed")`
    - `("reconciled", "Reconciled")`
  - `STATUS_BADGE_MAP`:
    - `"draft": "badge-slate"`, `"ready": "badge-info"`, `"posted": "badge-green"`, `"simulated": "badge-amber"`, `"failed": "badge-red"`, `"reconciled": "badge-green"`
  - `RECON_BADGE_MAP`:
    - `"pending": "badge-slate"`, `"reconciled": "badge-green"`, `"variance_flagged": "badge-red"`, `"resolved": "badge-info"`
- **Fields**:
  - `connector`: `ForeignKey("assets.AssetIntegrationConnector", on_delete=models.PROTECT, related_name="gl_sync_batches")`
  - `sync_domain`: `CharField(max_length=32, choices=SYNC_DOMAIN_CHOICES, default="depreciation_posting")`
  - `sync_direction`: `CharField(max_length=20, choices=SYNC_DIRECTION_CHOICES, default="outbound")`
  - `external_batch_ref`: `CharField(max_length=100, blank=True)`
  - `fiscal_period`: `ForeignKey("accounting.FiscalPeriod", on_delete=models.PROTECT, null=True, blank=True, related_name="asset_gl_sync_batches")`
  - `gl_account`: `ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="asset_gl_sync_debit_batches")`
  - `offset_gl_account`: `ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="asset_gl_sync_credit_batches")`
  - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="gl_sync_batches")`
  - `purchase_order`: `ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_gl_sync_batches")`
  - `capitalization`: `ForeignKey("assets.AssetCapitalization", on_delete=models.SET_NULL, null=True, blank=True, related_name="gl_sync_batches")`
  - `depreciation_schedule`: `ForeignKey("assets.AssetDepreciationSchedule", on_delete=models.SET_NULL, null=True, blank=True, related_name="gl_sync_batches")`
  - `maintenance_request`: `ForeignKey("assets.AssetMaintenanceRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="gl_sync_batches")`
  - `cost_center`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_gl_sync_batches")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.PROTECT, null=True, blank=True, related_name="asset_gl_sync_batches")` *(GLOBAL — no tenant)*
  - `batch_date`: `DateField(default=timezone.localdate)`
  - `source_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `target_gl_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `variance_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), editable=False)`
  - `reconciliation_status`: `CharField(max_length=24, choices=RECONCILIATION_STATUS_CHOICES, default="pending", editable=False)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", editable=False)`
  - `records_processed`: `PositiveIntegerField(default=0, editable=False)`
  - `records_succeeded`: `PositiveIntegerField(default=0, editable=False)`
  - `records_failed`: `PositiveIntegerField(default=0, editable=False)`
  - `synced_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `journal_entry`: `ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="asset_gl_sync_batches")`
  - `executed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="executed_asset_gl_batches")`
  - `field_mapping_json`: `TextField(blank=True, default="{}")`
  - `payload_summary`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_agls_ten_num_uniq")` *(24 chars)*
  - `Index(fields=["tenant", "sync_domain"], name="idx_agls_ten_dom")` *(16 chars)*
  - `Index(fields=["tenant", "status"], name="idx_agls_ten_stat")` *(17 chars)*
  - `Index(fields=["tenant", "reconciliation_status"], name="idx_agls_ten_rec")` *(16 chars)*
  - `Index(fields=["tenant", "batch_date", "number"], name="idx_agls_ten_date_num")` *(21 chars)*
  - `Index(fields=["tenant", "connector"], name="idx_agls_ten_conn")` *(17 chars)*
- **Validation (`clean()`)**:
  - `source_amount >= 0`, `target_gl_amount >= 0`.
  - If `gl_account` and `offset_gl_account` are both set and `gl_account_id == offset_gl_account_id`: ValidationError on `offset_gl_account`.
  - If `field_mapping_json.strip()`: must parse via `json.loads(...)` as `dict`, else ValidationError on `field_mapping_json`.
  - Compute `self.variance_amount = (self.source_amount or Decimal("0.00")) - (self.target_gl_amount or Decimal("0.00"))` in `clean()` / `save()` (before save if not overriding blindly, e.g., `self.variance_amount = (self.source_amount or Decimal("0.00")) - (self.target_gl_amount or Decimal("0.00"))` inside `save()`).
- **`__str__`**: `f"{self.number} · {self.get_sync_domain_display()} ({self.batch_date})"`

---

### 1.4 `AssetGisMapping` (`AssetGisMappings.py`)
- **`NUMBER_PREFIX`**: `"AGIS"`
- **`Meta.ordering`**: `["number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Asset GIS Mapping"` / `"Asset GIS Mappings"`
- **Constants / Choices / Badge Maps**:
  - `GEOMETRY_TYPE_CHOICES`:
    - `("point", "Point")`
    - `("linestring", "LineString")`
    - `("polygon", "Polygon")`
    - `("multipoint", "MultiPoint")`
  - `LRS_UNIT_CHOICES`:
    - `("meters", "Meters")`
    - `("km", "Kilometers")`
    - `("miles", "Miles")`
    - `("feet", "Feet")`
  - `SYSTEM_OF_RECORD_CHOICES`:
    - `("gis_authoritative", "GIS Authoritative")`
    - `("erp_authoritative", "ERP Authoritative")`
    - `("shared_field", "Shared Field")`
  - `SYNC_DIRECTION_CHOICES`:
    - `("inbound", "Inbound")`
    - `("outbound", "Outbound")`
    - `("bidirectional", "Bidirectional")`
  - `DRIFT_STATUS_CHOICES`:
    - `("in_sync", "In Sync")`
    - `("location_drift", "Location Drift")`
    - `("attribute_drift", "Attribute Drift")`
    - `("unverified", "Unverified")`
  - `STATUS_CHOICES`:
    - `("active", "Active")`
    - `("paused", "Paused")`
    - `("archived", "Archived")`
  - `DRIFT_BADGE_MAP`:
    - `"in_sync": "badge-green"`, `"location_drift": "badge-red"`, `"attribute_drift": "badge-amber"`, `"unverified": "badge-slate"`
  - `STATUS_BADGE_MAP`:
    - `"active": "badge-green"`, `"paused": "badge-amber"`, `"archived": "badge-muted"`
- **Fields**:
  - `connector`: `ForeignKey("assets.AssetIntegrationConnector", on_delete=models.PROTECT, related_name="gis_mappings")`
  - `operational_asset`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="gis_mappings")`
  - `location`: `ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="gis_mappings")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="gis_mappings")`
  - `external_feature_id`: `CharField(max_length=120)`
  - `layer_name`: `CharField(max_length=120)`
  - `geometry_type`: `CharField(max_length=20, choices=GEOMETRY_TYPE_CHOICES, default="point")`
  - `coordinate_system_srid`: `PositiveIntegerField(default=4326)`
  - `latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `elevation_meters`: `DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)`
  - `is_linear_asset`: `BooleanField(default=False)`
  - `lrs_route_id`: `CharField(max_length=80, blank=True)`
  - `lrs_from_measure`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `lrs_to_measure`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `lrs_measure_unit`: `CharField(max_length=16, choices=LRS_UNIT_CHOICES, default="km")`
  - `geojson_payload`: `TextField(blank=True)`
  - `system_of_record`: `CharField(max_length=24, choices=SYSTEM_OF_RECORD_CHOICES, default="erp_authoritative")`
  - `sync_direction`: `CharField(max_length=20, choices=SYNC_DIRECTION_CHOICES, default="bidirectional")`
  - `drift_status`: `CharField(max_length=24, choices=DRIFT_STATUS_CHOICES, default="unverified", editable=False)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active")`
  - `last_spatial_sync_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `gis_custodian`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="custodian_gis_mappings")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_agis_ten_num_uniq")` *(24 chars)*
  - `Index(fields=["tenant", "operational_asset"], name="idx_agis_ten_asset")` *(18 chars)*
  - `Index(fields=["tenant", "drift_status"], name="idx_agis_ten_drift")` *(18 chars)*
  - `Index(fields=["tenant", "status"], name="idx_agis_ten_stat")` *(17 chars)*
  - `Index(fields=["tenant", "connector"], name="idx_agis_ten_conn")` *(17 chars)*
- **Validation (`clean()`)**:
  - `latitude`: if not None, `-90 <= latitude <= 90`
  - `longitude`: if not None, `-180 <= longitude <= 180`
  - `coordinate_system_srid >= 1`
  - If `lrs_from_measure is not None and lrs_to_measure is not None`: `lrs_to_measure >= lrs_from_measure`
  - If `geojson_payload.strip()`: must parse via `json.loads(...)` as `dict`, else ValidationError on `geojson_payload`.
- **`__str__`**: `f"{self.number} · {self.layer_name} / {self.external_feature_id}"`

---

## 2. Forms Contract

All 4 forms subclass `(TenantUniqueMixin, TenantModelForm)` (from `apps.assets.forms._common`), use explicit `Meta.fields` whitelists (NEVER `__all__` or `exclude`), scope tenant FKs to `self.tenant` inside `if hasattr(self, "tenant") and self.tenant is not None:` (and fail closed to `.none()` when `self.tenant is None`), NEVER pass global `Currency` to `reject_foreign(...)`, and NEVER query `.filter(is_active=True)` on `core.OrgUnit` or `core.Party`.

### 2.1 `AssetIntegrationConnectorForm`
- **`Meta.fields`** (19 editable fields; excludes `tenant`, `number`, `health_status`, `api_key_prefix`, `api_key_hash`, `last_heartbeat_at`, `last_sync_at`, `consecutive_failures`, `last_error_message`, `created_at`, `updated_at`):
  `["name", "connector_category", "provider", "protocol", "sync_direction", "environment", "endpoint_url", "auth_method", "rate_limit_rpm", "timeout_seconds", "retry_policy_max", "polling_interval_minutes", "status", "vendor_partner", "default_org_unit", "default_currency", "owner", "webhook_verify_tls", "notes"]`
- **Widgets**: `"endpoint_url": forms.TextInput(...)` (NOT `URLInput`).
- **FK Querysets**: `vendor_partner` (`Party.objects.filter(tenant=self.tenant)`), `default_org_unit` (`OrgUnit.objects.filter(tenant=self.tenant)`), `default_currency` (`Currency.objects.filter(is_active=True)`), `owner` (`User.objects.filter(tenant=self.tenant)`).
- **`clean_endpoint_url()`**: delegates to `validate_connector_endpoint_url`.
- **`clean()`**: `reject_foreign(self, cleaned_data, ["vendor_partner", "default_org_unit", "owner"])`.

### 2.2 `AssetTelemetryStreamForm`
- **`Meta.fields`** (20 editable fields; excludes `tenant`, `number`, `last_ingested_value`, `last_ingested_at`, `readings_ingested_count`, `last_telemetry_reading`, `latest_maintenance_request`, `created_at`, `updated_at`):
  `["connector", "operational_asset", "fixed_asset", "tag_address", "stream_name", "stream_protocol", "metric_type", "metric_unit", "ingestion_mode", "polling_interval_seconds", "deadband_delta", "scale_factor", "offset_value", "baseline_value", "warning_threshold", "critical_threshold", "auto_trigger_maintenance", "stream_status", "steward", "notes"]`
- **FK Querysets**: `connector`, `operational_asset`, `fixed_asset`, `steward` filtered by `tenant=self.tenant`.
- **`clean()`**:
  - `reject_foreign(self, cleaned_data, ["connector", "operational_asset", "fixed_asset", "steward"])`
  - Require `operational_asset` OR `fixed_asset` (error on `operational_asset`).
  - `polling_interval_seconds >= 1`, `scale_factor != 0`, `deadband_delta >= 0`, `critical_threshold >= warning_threshold` when both provided.

### 2.3 `AssetGlSyncBatchForm`
- **`Meta.fields`** (20 editable fields; excludes `tenant`, `number`, `variance_amount`, `reconciliation_status`, `status`, `records_processed`, `records_succeeded`, `records_failed`, `synced_at`, `journal_entry`, `executed_by`, `created_at`, `updated_at`):
  `["connector", "sync_domain", "sync_direction", "external_batch_ref", "fiscal_period", "gl_account", "offset_gl_account", "fixed_asset", "purchase_order", "capitalization", "depreciation_schedule", "maintenance_request", "cost_center", "currency", "batch_date", "source_amount", "target_gl_amount", "field_mapping_json", "payload_summary", "notes"]`
- **FK Querysets**: 10 tenant FKs (`connector`, `fiscal_period`, `gl_account` [is_active=True or saved], `offset_gl_account`, `fixed_asset`, `purchase_order`, `capitalization`, `depreciation_schedule`, `maintenance_request`, `cost_center`) scoped by `tenant=self.tenant`; `currency` filtered `Currency.objects.filter(is_active=True)`.
- **`clean()`**: `reject_foreign(self, cleaned_data, ["connector", "fiscal_period", "gl_account", "offset_gl_account", "fixed_asset", "purchase_order", "capitalization", "depreciation_schedule", "maintenance_request", "cost_center"])` (NOT `currency`); validate `source_amount >= 0`, `target_gl_amount >= 0`, `gl_account != offset_gl_account`, bounded finite JSON dict on `field_mapping_json`, bounded size on `payload_summary`.

### 2.4 `AssetGisMappingForm`
- **`Meta.fields`** (22 editable fields; excludes `tenant`, `number`, `drift_status`, `last_spatial_sync_at`, `created_at`, `updated_at`):
  `["connector", "operational_asset", "location", "org_unit", "external_feature_id", "layer_name", "geometry_type", "coordinate_system_srid", "latitude", "longitude", "elevation_meters", "is_linear_asset", "lrs_route_id", "lrs_from_measure", "lrs_to_measure", "lrs_measure_unit", "geojson_payload", "system_of_record", "sync_direction", "status", "gis_custodian", "notes"]`
- **FK Querysets**: `connector`, `operational_asset`, `location`, `org_unit`, `gis_custodian` scoped by `tenant=self.tenant`.
- **`clean()`**: `reject_foreign(self, cleaned_data, ["connector", "operational_asset", "location", "org_unit", "gis_custodian"])`; validate coordinate bounds, SRID >= 1, LRS measure range, valid JSON object on `geojson_payload`.

---

## 3. Views, Custom Actions & URLconf Contract

All list/detail/edit/delete/action views use `assets_scope` and `assets_object(..., select_related=...)` from `apps.assets.views._common`, `@login_required` (with `@tenant_admin_required` on `connector_create`, `connector_edit`, `connector_delete`, `rotate_secret`, `stream_delete`, `batch_delete`, `execute_reconcile_batch`, `mapping_delete`; create views also fail closed when `request.tenant is None`), and `@require_POST` on mutations (`delete` and custom actions). Non-admin users do not see `@tenant_admin_required` action/delete buttons in list/detail templates. Pagination: `Paginator(qs, 25)` passing `paginator`, `page_obj`, `is_paginated` alongside entity-specific context keys.

### 3.1 `AssetIntegrationConnectors`
- **URL Patterns** (prefix `integration/connectors/`):
  - `""` -> `asset_integration_connector_list` (`connector_list`)
  - `"create/"` -> `asset_integration_connector_create` (`connector_create`)
  - `"<int:pk>/"` -> `asset_integration_connector_detail` (`connector_detail`)
  - `"<int:pk>/edit/"` -> `asset_integration_connector_edit` (`connector_edit`)
  - `"<int:pk>/delete/"` -> `asset_integration_connector_delete` (`connector_delete`)
  - `"<int:pk>/test/"` -> `asset_integration_connector_test` (`test_connection`)
  - `"<int:pk>/rotate-secret/"` -> `asset_integration_connector_rotate_secret` (`rotate_secret`)
- **Filters on List** (`q`, `connector_category`, `provider`, `status`, `health_status`)
- **Context Keys**:
  - List: `connectors`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `active_count`, `healthy_count`, `error_count`, `category_choices`, `provider_choices`, `status_choices`, `health_choices`, `search_query`
  - Detail: `connector`, `plaintext_once` (popped from `request.session.pop("_aicn_secret_reveal", None)` ONLY when `reveal["pk"] == connector.pk`, NEVER via `messages`), `streams`, `gl_batches`, `gis_mappings`
  - Form: `form`, `connector` (`None` on create), `is_edit`, `title`
- **Actions**:
  - `test_connection` (`@login_required`, `@require_POST`): Zero outbound HTTP! Evaluates URL/auth completeness & TLS setting -> if valid endpoint URL (`validate_connector_endpoint_url`), sets `health_status="healthy"`, `last_heartbeat_at=now`, `consecutive_failures=0`, `last_error_message=""`; if paused/decommissioned sets `"degraded"`. Logs `write_audit_log(..., "test", ...)`.
  - `rotate_secret` (`@tenant_admin_required`, `@require_POST`): Calls `connector.issue_new_secret()`, saves `api_key_prefix`/`api_key_hash`, sets `request.session["_aicn_secret_reveal"] = {"pk": connector.pk, "secret": plaintext}`, logs `write_audit_log(..., "rotate", changes={"prefix": connector.api_key_prefix}, ...)`, redirects to detail.

### 3.2 `AssetTelemetryStreams`
- **URL Patterns** (prefix `integration/telemetry-streams/`):
  - `""` -> `asset_telemetry_stream_list`
  - `"create/"` -> `asset_telemetry_stream_create`
  - `"<int:pk>/"` -> `asset_telemetry_stream_detail`
  - `"<int:pk>/edit/"` -> `asset_telemetry_stream_edit`
  - `"<int:pk>/delete/"` -> `asset_telemetry_stream_delete`
  - `"<int:pk>/ingest/"` -> `asset_telemetry_stream_ingest` (`ingest_sample_reading`)
- **Filters on List** (`q`, `connector`, `operational_asset`, `stream_protocol`, `stream_status`)
- **Context Keys**:
  - List: `streams`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `active_count`, `faulted_count`, `auto_cbm_count`, `connectors`, `assets_list`, `protocol_choices`, `status_choices`, `search_query`
  - Detail: `stream`, `recent_readings` (last 10 `AssetTelemetryReading` records filtered by tenant + linked asset)
  - Form: `form`, `stream` (`None` on create), `is_edit`, `title`
- **Action `ingest_sample_reading` (`@login_required`, `@require_POST`)**:
  - Reads `raw_value` from POST (defaults to `stream.warning_threshold or stream.baseline_value or Decimal("25.0000")` when omitted/blank; rejects invalid/non-finite decimals, inputs > 32 chars, or `abs(normalized) > Decimal("99999999.9999")` with `messages.error` and redirect).
  - Inside `transaction.atomic()` locking the stream with `select_for_update()`: requires `stream.stream_status == "active"`, validates linked FK tenancy, computes `normalized = (raw * stream.scale_factor) + stream.offset_value`.
  - If `stream.deadband_delta > 0 and stream.last_ingested_value is not None and abs(normalized - stream.last_ingested_value) < stream.deadband_delta`: updates `last_ingested_at` only and reports deadband skip.
  - Otherwise maps `metric_type`/`metric_unit` via `STREAM_TO_TELEMETRY_METRIC_MAP` / `UNIT_FALLBACK_MAP`, computes stream threshold status (`critical` if `>= critical_threshold`, `warning` if `>= warning_threshold`, else `normal`), deduplicates open `AssetMaintenanceRequest` when `latest_maintenance_request.status in ("submitted", "triaged", "assigned", "in_progress")`, creates `AssetTelemetryReading` (linking `triggered_maintenance_request`), syncs `threshold_status` post-save when thresholds are configured (including `"normal"`), updates `stream` telemetry pointers/counts, logs `write_audit_log(..., "ingest", ...)`.

### 3.3 `AssetGlSyncBatches`
- **URL Patterns** (prefix `integration/gl-sync-batches/`):
  - `""` -> `asset_gl_sync_batch_list`
  - `"create/"` -> `asset_gl_sync_batch_create`
  - `"<int:pk>/"` -> `asset_gl_sync_batch_detail`
  - `"<int:pk>/edit/"` -> `asset_gl_sync_batch_edit`
  - `"<int:pk>/delete/"` -> `asset_gl_sync_batch_delete`
  - `"<int:pk>/execute/"` -> `asset_gl_sync_batch_execute` (`execute_reconcile_batch`)
- **Filters on List** (`q`, `connector`, `sync_domain`, `status`, `reconciliation_status`, `date_from`, `date_to` via `safe_parse_date`)
- **Context Keys**:
  - List: `batches`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `posted_count`, `variance_count`, `draft_count`, `connectors`, `domain_choices`, `status_choices`, `reconciliation_choices`, `search_query`
  - Detail: `batch`
  - Form: `form`, `batch` (`None` on create), `is_edit`, `title`
- **Action `execute_reconcile_batch` (`@tenant_admin_required`, `@require_POST`) & Posted Edit Lock**:
  - `batch_edit` rejects editing once `batch.journal_entry_id is not None or batch.status == "posted"`; UI hides Execute/Edit/Delete on posted batches.
  - Inside `transaction.atomic()` locking the batch row with `select_for_update()`: exits early if already posted (`journal_entry_id is not None or status == "posted"`) or `status == "failed"`, verifies same-tenant FKs (`connector`, `fiscal_period`, `gl_account`, `offset_gl_account`, `cost_center`), and if `batch.fiscal_period and not batch.fiscal_period.is_open`: error + redirect cleanly without state change or JE creation.
  - Computes `variance = batch.source_amount - batch.target_gl_amount`.
  - Sets `reconciliation_status = "reconciled" if variance == Decimal("0.00") else "variance_flagged"`.
  - Creates 1 balanced `JournalEntry(entry_type="recurring", status="posted", entry_date=batch.batch_date, fiscal_period=batch.fiscal_period)` + 2 validated `JournalLine` rows (`full_clean()` + `save()`, Debit `gl_account`, Credit `offset_gl_account`, strictly one nonzero per line) ONLY when `sync_domain in ("depreciation_posting", "capitalization_sync", "work_order_cost_rollup")`, both accounts set, `source_amount > 0`, `variance == Decimal("0.00")`, and `batch.journal_entry_id is None`.
  - Updates `status` (`"posted"` if JE created/already posted, else `"reconciled"` if zero variance else `"simulated"`), `variance_amount`, counts, `synced_at`, `executed_by`, logs `write_audit_log(..., "reconcile", ...)`.

### 3.4 `AssetGisMappings`
- **URL Patterns** (prefix `integration/gis-mappings/`):
  - `""` -> `asset_gis_mapping_list`
  - `"create/"` -> `asset_gis_mapping_create`
  - `"<int:pk>/"` -> `asset_gis_mapping_detail`
  - `"<int:pk>/edit/"` -> `asset_gis_mapping_edit`
  - `"<int:pk>/delete/"` -> `asset_gis_mapping_delete`
  - `"<int:pk>/verify/"` -> `asset_gis_mapping_verify_sync` (`verify_spatial_sync`)
- **Filters on List** (`q`, `connector`, `operational_asset`, `geometry_type`, `drift_status`, `status`)
- **Context Keys**:
  - List: `mappings`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `in_sync_count`, `drift_count`, `linear_count`, `connectors`, `assets_list`, `geometry_choices`, `drift_choices`, `status_choices`, `search_query`
  - Detail: `mapping`
  - Form: `form`, `mapping` (`None` on create), `is_edit`, `title`
- **Action `verify_spatial_sync` (`@login_required`, `@require_POST`)**:
  - Checks coordinates (`latitude`/`longitude` OR `is_linear_asset` + `lrs_route_id` OR `geojson_payload`) and ERP link (`operational_asset` or `location`): sets `drift_status` to `"location_drift"`, `"attribute_drift"`, or `"in_sync"`, updates `last_spatial_sync_at=timezone.now()`, logs `write_audit_log(..., "verify", ...)`.

---

## 4. Templates Contract

Paths: `templates/assets/integrationapihub/{asset_integration_connector,asset_telemetry_stream,asset_gl_sync_batch,asset_gis_mapping}/{list,detail,form}.html`.
- All extend `"base.html"`.
- List templates: breadcrumb (`Assets / Integration & API Hub / <Section>`), `.page-header`, 4 KPI `.stat-card`s (`.stat-icon.{blue,green,orange,purple}` only), `<form method="get">` filter card preserving selections (`|stringformat:"d"` for FK PKs, NEVER `|slugify`), sortable/linked table + `.empty-state` + pagination block preserving filter GET params via `|urlencode`.
- Detail templates: status/severity badges (`badge-*` valid classes only), explicit POST forms (`{% csrf_token %}`) for custom actions & Delete, `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`, related cross-module links (only where links/routes exist!), and for `asset_integration_connector/detail.html` the one-time `{% if plaintext_once %}` reveal card.
- Form templates: `<div class="card max-w-4xl">` + `grid grid-cols-1 md:grid-cols-2 gap-4`, rendering `form.non_field_errors` + per-field errors/help text cleanly.

---

## 5. Navigation Wiring Contract (`apps/core/navigation.py`)

Exact key in `LIVE_LINKS`: `"11.15"` mapping every `NavERP.md` bullet byte-for-byte plus the unfiltered `"Integration Connectors"` hub leaf so every entry has a strictly unique URL+query:
- `"ERP Integration": "assets:asset_integration_connector_list?connector_category=erp_procurement"`
- `"IoT & SCADA Systems": "assets:asset_telemetry_stream_list"`
- `"CMMS/EAM Connectivity": "assets:asset_integration_connector_list?connector_category=cmms_eam"`
- `"Financial Systems & General Ledger": "assets:asset_gl_sync_batch_list"`
- `"GIS & Mapping Tools": "assets:asset_gis_mapping_list"`
- Extra live leaf: `"Integration Connectors": "assets:asset_integration_connector_list"`.
