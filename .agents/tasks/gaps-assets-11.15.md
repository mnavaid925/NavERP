# Gap Register — Sub-module 11.15: Integration & API Hub

**Module:** 11 — Asset Management System (`apps/assets/`)  
**Sub-module:** 11.15 — Integration & API Hub  
**Status:** COMPLETE (`31 / 31` review findings closed in [review-assets-11.15.md](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-assets-11.15.md); `375 / 375` dedicated 11.15 tests & `2,283` total `apps/assets/tests/` tests passing on SQLite; deferred roadmap & cross-module follow-ups tracked below)

---

## Gaps & Deferred Follow-Ups Inventory

### GAP-assets-11.15-01 — Live Outbound Transport & Async Worker Execution
- **Owner:** Platform Async Worker / Transport Infrastructure (`core` + `assets`)
- **Waiting For / Blocked On:** Enterprise async worker broker (Celery/queue), runtime secrets vault, and centralized connect-time pinned-IP DNS resolution wrapper so outbound HTTP/OPC-UA/MQTT/ArcGIS requests cannot regress SSRF protections via DNS rebinding.
- **Status:** `[~]` Deferred by architecture (`contract-assets-11.15.md` & `.claude/tasks/todo.md`) — `test_connection`, telemetry ingestion, GL reconciliation, and spatial verification run deterministically offline on ORM records with zero outbound sockets.
- **Done When:** Sandboxed transport adapters use connect-time IP pinning after SSRF validation, update `AssetIntegrationConnector` / `AssetTelemetryStream` / `AssetGisMapping` status via async jobs, and pass mocked transport security + integration tests.

### GAP-assets-11.15-02 — Encrypted KMS Envelope Storage for Outbound OAuth/Basic Credentials
- **Owner:** Security / Module 0 `core` Secrets Vault
- **Waiting For / Blocked On:** Enterprise KMS / envelope key management primitive in `apps/core` for decryptable outbound client secrets (`OAuth2`, mTLS passphrases, basic auth vault).
- **Status:** `[~]` Deferred by design — `11.15` stores only `api_key_prefix` + SHA-256 `api_key_hash` (`editable=False`) with one-time session pop reveal (`_aicn_secret_reveal`, L20/L25) and never echoes secrets in forms or `AuditLog`.
- **Done When:** Outbound credentials are encrypted at rest with tenant KMS keys, excluded from all forms/`AuditLog` serialization, and verified by encryption/rotation tests.

### GAP-assets-11.15-03 — Interactive GIS Vector Map Viewer & PostGIS Spatial Indexing
- **Owner:** `assets` GIS & Spatial Infrastructure (`core` spatial backend)
- **Waiting For / Blocked On:** Dual-backend spatial portability strategy (`django.contrib.gis` / PostGIS geometry columns vs SQLite in-memory test DB and MariaDB dev DB compatibility).
- **Status:** `[~]` Deferred — `AssetGisMapping` stores WGS84/SRID coordinates, LRS linear measures, and validated `<= 64 KB` JSON `geojson_payload` dicts portably across MariaDB and SQLite.
- **Done When:** Interactive map viewer renders verified GeoJSON/LRS routes on `asset_gis_mapping_detail` while maintaining SQLite test suite & MariaDB compatibility.

### GAP-assets-11.15-04 — Form `.form-grid` CSS Alignment (`review-assets-11.15.md` `M9`)
- **Owner:** Shared UI / `static/css/theme.css` Pass
- **Waiting For / Blocked On:** Updating shared `.form-grid` rules in `static/css/theme.css` (`grid-template-columns: repeat(2, minmax(0, 1fr))`) so 2-column form cards (`max-w-4xl`) do not auto-fit into 3 columns and break `md:col-span-2` spans.
- **Status:** `[~]` Skipped / deferred in Phase 5 (`review-assets-11.15.md` `M9`) — `11.15` form templates retain `grid grid-cols-1 md:grid-cols-2 gap-4` per `contract-assets-11.15.md:509` and sibling Assets forms.
- **Done When:** `.form-grid` in `theme.css` renders predictable 2-column form grids across desktop breakpoints and 11.15 forms migrate cleanly without column-span breakage.

### GAP-assets-11.15-05 — Central `AuditLog` Sensitive Field Redaction Hardening (`review-assets-11.15.md` `X1`)
- **Owner:** Module 0 `core` Maintainers (`apps/core/crud.py:265-289`, `apps/core/utils.py:51-60`)
- **Waiting For / Blocked On:** Cross-module Module 0 `core` hardening pass (intentionally kept out of `11.15` diff scope).
- **Status:** `[ ]` Open (cross-module follow-up)
- **Done When:** `_SENSITIVE_AUDIT_FIELDS` includes `"api_key_hash"`, `"api_key_prefix"`, `"signing_secret_hash"`, `"credential_hash"`, `"webhook_secret"`, `"private_key"`, and `"client_secret"`, `write_audit_log()` enforces redaction across that set centrally, and `apps/core/tests/` passes unfiltered.

### GAP-assets-11.15-06 — Sibling 11.4 `AssetDepreciationSchedule` Form/GL Lock & Legacy Fixture Sync (`review-assets-11.15.md` `X2`)
- **Owner:** `assets` Sub-module 11.4 Maintenance Pass (`apps/assets/{forms,models}/AssetDepreciation/AssetDepreciationSchedules.py`, `apps/assets/tests/conftest.py:800,825`)
- **Waiting For / Blocked On:** Dedicated 11.4 hardening pass (left untouched in 11.15 per scope isolation rules; discovered via L28 pattern-clone sweep and Phase 6 fixture audit).
- **Status:** `[ ]` Open (upstream 11.4 follow-up)
- **Done When:** `AssetDepreciationScheduleForm` sets FK querysets to `.none()` when `tenant is None`; `post_to_gl` enforces `select_for_update()`, `fiscal_period.is_open`, and FK `tenant_id` equality; and `conftest.py` fixtures `depreciation_schedule_a` / `depreciation_schedule_b` drop removed kwargs (`salvage_value`, `accumulated_depreciation_prior`, `useful_life_months_total`) cleanly with full green tests.

### GAP-assets-11.15-07 — Upstream 11.7 `AssetTelemetryReading` Composite Indexes (`review-assets-11.15.md` `X3`)
- **Owner:** `assets` Sub-module 11.7 Optimization Pass (`apps/assets/models/AssetReliability/AssetTelemetryReadings.py:189-195`)
- **Waiting For / Blocked On:** Next schema pass on `AssetReliability` outside `11.15` scope.
- **Status:** `[ ]` Open (cross-sub-module optimization)
- **Done When:** Composite indexes `(tenant, operational_asset, recorded_at)` and `(tenant, fixed_asset, recorded_at)` exist on `AssetTelemetryReading`, migration is applied, and `stream_detail` recent-reading lookup uses indexed scans cleanly.

---

## Completed Scope Note (`11.15` Deliverables)
- All `4` models (`AssetIntegrationConnector` `AICN-`, `AssetTelemetryStream` `ATMS-`, `AssetGlSyncBatch` `AGLS-`, `AssetGisMapping` `AGIS-`), `4` ModelForms, `25` FBV views across 4 entities, `12` templates, `LIVE_LINKS["11.15"]`, `apps/assets/admin.py`, `_seed_tenant_11_15` (`seed_assets`), `assets:overview` KPI cards, migrations `0018` & `0019`, and `375` dedicated unit/form/view/security tests (`2,283` total `apps/assets/tests/` tests) are shipped and passing.
