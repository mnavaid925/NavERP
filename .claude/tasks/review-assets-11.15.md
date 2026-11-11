# Module 11.15 Review Findings — Integration & API Hub (`apps/assets/`)

> Changeset reviewed: `d1aa6e479b760216764b50899ded7488cdc07c15...HEAD`
> Six serial passes completed (all read-only; Pass 5 runtime QA run in report-only mode with throwaway `uuid4` tenant purged):
> 1. `nav-code-reviewer` (`08873c36-3bbe-4157-bb0f-251dc0a4a91a`)
> 2. `nav-explorer` (`3242fbbf-38b8-4a4e-82b5-6b084e7258a7`)
> 3. `nav-frontend-reviewer` (`28e670d2-4a91-4a2c-b741-02fee4ee0282`)
> 4. `nav-performance-reviewer` (`5711339c-8805-44e6-8b23-b02b2cb41cae`)
> 5. `nav-qa-smoke-tester` (`c37afbdf-4547-4f7c-90a1-a784b47c14f0`, report-only)
> 6. `nav-security-reviewer` (`ba8f040e-0a84-48c0-915c-e876bd4e65e8`)

## Summary / Stats

| Category | Raw Findings (6 Passes) | Deduplicated Actionable Findings | Out-of-Scope Cross-Module Notes |
|----------|-------------------------|----------------------------------|---------------------------------|
| Critical | 12 | **8** (`C1`–`C8`) | 0 |
| Important / High / Medium | 34 | **13** (`I1`–`I13`) | 2 (`X1`, `X2`) |
| Minor / Low | 19 | **10** (`M1`–`M10`) | 1 (`X3`) |
| **Total** | **65** | **31** (`C1`–`C8`, `I1`–`I13`, `M1`–`M10`) | **3** (`X1`–`X3`) |

> **Contract Sync Note:** Fixing `C1`, `C6`, `I4`, and `I5` changes form `Meta.fields`, view `@tenant_admin_required` decorators, and `UNIT_FALLBACK_MAP`. Update `.claude/tasks/contract-assets-11.15.md` accordingly (own single-file commit) so Phase 6 test contracts match the fixed code.

---

## Consolidated Deduplicated Findings

## Critical

### C1 — `apps/assets/forms/IntegrationApiHub/AssetGlSyncBatches.py:55-56` / `apps/assets/models/IntegrationApiHub/AssetGlSyncBatches.py` / `apps/assets/views/IntegrationApiHub/AssetGlSyncBatches.py:192-230` / `templates/assets/integrationapihub/asset_gl_sync_batch/{detail,list}.html`
- **Found by:** code-reviewer, explorer, frontend-reviewer, qa-smoke-tester, security-reviewer
- **Lesson:** L27, L40
- **Problem:** `AssetGlSyncBatchForm.Meta.fields` exposes `"status"` and `"reconciliation_status"`, allowing any tenant user to forge `status="posted"` / `reconciliation_status="reconciled"` without `@tenant_admin_required` or a real `JournalEntry`. Additionally, `batch_edit` permits editing already-posted batches (`journal_entry_id is not None or status == "posted"`) — runtime QA confirmed mutating posted `AGLS-00001` back to `"draft"` / `9999.00` — and `list.html:171` + `detail.html:28-30` render active `Edit` links on posted batches.
- **Fix:** Exclude `"status"` and `"reconciliation_status"` from `AssetGlSyncBatchForm.Meta.fields` (managed by system/`execute_reconcile_batch`); add `if batch.journal_entry_id is not None or batch.status == "posted": messages.error(...); return redirect("assets:asset_gl_sync_batch_detail", pk=batch.pk)` at top of `batch_edit` (mirroring `batch_delete`); and wrap `Edit` links in `asset_gl_sync_batch/list.html` and `detail.html` with `{% if not batch.journal_entry and batch.status != "posted" %}`.
- **Status:** [x] fixed — mark AssetGlSyncBatch status/reconciliation_status non-editable, block posted batch_edit, and hide Edit UI on posted rows (989aa2cf, 806cc9fc, 8aa654e2, cc7d5efc, 5506d7a9, 00068bb8; contract synced 1821e91f)

### C2 — `apps/assets/views/IntegrationApiHub/AssetGlSyncBatches.py:263-374`
- **Found by:** explorer, performance-reviewer, security-reviewer
- **Lesson:** L40
- **Problem:** `execute_reconcile_batch` fetches `batch = assets_object(...)` outside `transaction.atomic()` without `.select_for_update()`, enabling concurrent POST double-posting of duplicate `JournalEntry` rows. Furthermore, when `already_posted` is True it still mutates fields (`lines 343-374`), `can_post_je` creates live GL entries even when `batch.status == "failed"` or `variance != Decimal("0.00")`, `JournalLine.objects.create(...)` skips `JournalLine.full_clean()`, and `fiscal_period` / `cost_center` / `connector` lack `tenant_id == batch.tenant_id` checks.
- **Fix:** Move the batch lookup inside `with transaction.atomic():` using `get_object_or_404(AssetGlSyncBatch.objects.select_for_update(), pk=pk, tenant=request.tenant)` (resolving related objects safely after lock for MySQL/PostgreSQL compatibility); return immediately if `batch.journal_entry_id is not None or batch.status == "posted"` or `batch.status == "failed"`; verify `tenant_id == batch.tenant_id` on `connector`, `fiscal_period`, `gl_account`, `offset_gl_account`, and `cost_center`; require `variance == Decimal("0.00")` before `can_post_je`; and call `.full_clean()` + `.save()` on created `JournalLine`s.
- **Status:** [x] fixed — lock GL sync batch with select_for_update inside atomic() and harden failed/variance/same-tenant/JournalLine guards in execute_reconcile_batch (35505451)

### C3 — `apps/assets/views/IntegrationApiHub/{AssetIntegrationConnectors,AssetTelemetryStreams,AssetGlSyncBatches,AssetGisMappings}.py` & `apps/assets/forms/IntegrationApiHub/*.py`
- **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
- **Lesson:** L39 §2
- **Problem:** All four `*_create` views only reject `request.tenant is None` on `POST`, returning HTTP `200` on `GET` when `request.tenant is None`, while all four forms skip queryset filtering inside `if self.tenant is not None:` (`TenantModelForm.__init__` also skips when `tenant is None`). Runtime QA proved `GET` with `tenant=None` leaks foreign tenants' `Party`, `OrgUnit`, `User`, `AssetIntegrationConnector`, `Asset`, `FixedAsset`, `GLAccount`, `FiscalPeriod`, and `Location` options in HTML `<select>` tags.
- **Fix:** Reject `request.tenant is None` at the top of every `*_create` view (covering both GET and POST) with `messages.error` + redirect, AND add explicit `else:` branches (or a `_tenant_qs(Model, self.tenant)` helper returning `Model.objects.none()`) on every tenant-owned FK field in all four forms when `self.tenant is None`.
- **Status:** [x] fixed — return empty querysets when tenant is None in all 4 forms and block GET/POST when request.tenant is None in all 4 *_create views (7a435cf3, 94984ef9, 5ff7e044, c548053a, 1240cbaa, 4c8e4b0a, 99aede49, 77d12744)

### C4 — `apps/assets/views/IntegrationApiHub/AssetTelemetryStreams.py:260-383`
- **Found by:** code-reviewer, explorer, performance-reviewer, qa-smoke-tester, security-reviewer
- **Lesson:** L35
- **Problem:** `ingest_sample_reading` has five compounding defects verified in Pass 5: (1) `raw_value="1e50"` passes `.is_finite()` and throws unhandled HTTP `500` `decimal.InvalidOperation` at `.quantize(Decimal("0.0001"))`, while `9999999999.0` triggers MariaDB clamping on `deviation_percentage` (`8,2`) and `last_ingested_value` (`12,4`); (2) fetches `stream` outside `transaction.atomic()` without `.select_for_update()`, racing deadband/counter updates and performing redundant `reading.refresh_from_db()` + two sequential `UPDATE`s; (3) allows `"paused"` and `"faulted"` streams to ingest readings (only blocks `"decommissioned"`); (4) creates duplicate `AssetMaintenanceRequest`s on repeated critical readings even when `stream.latest_maintenance_request` is still open; and (5) when `warning_threshold=0.0000` evaluates a safe `"normal"` reading whose `baseline_value` differs, `AssetTelemetryReading.save()` overwrites `threshold_status` to `"critical"` and `lines 338-342` only restore `"warning"`/`"critical"`, leaving `"critical"` in MariaDB.
- **Fix:** Enter `with transaction.atomic():` first and lock via `AssetTelemetryStream.objects.select_for_update().select_related("connector", "operational_asset", "fixed_asset", "latest_maintenance_request")`; require `stream.stream_status == "active"`; check input length `<= 32`, wrap `.quantize()` in `try/except (InvalidOperation, ArithmeticError)`, and reject `abs(normalized) > Decimal("99999999.9999")` (plus verify `operational_asset`/`fixed_asset` `tenant_id == stream.tenant_id`); create `maint_req` BEFORE `AssetTelemetryReading.objects.create(...)` only when `computed_status == "critical" and stream.auto_trigger_maintenance` and existing `latest_maintenance_request` is not already in `("submitted", "triaged", "assigned", "in_progress")`; pass `triggered_maintenance_request=maint_req` into `.create(...)` directly (eliminating the second `UPDATE` and `refresh_from_db()`); and whenever `stream.warning_threshold is not None or stream.critical_threshold is not None`, ensure `AssetTelemetryReading` persists `computed_status` cleanly including `"normal"`.
- **Status:** [x] fixed — lock telemetry stream with select_for_update, validate overflow/NaN, gate active streams, dedup open MR, and preserve normal status (892def59; contract synced 1821e91f)

### C5 — `apps/assets/models/IntegrationApiHub/AssetIntegrationConnectors.py:16-78`
- **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
- **Problem:** `validate_connector_endpoint_url` misses SSRF obfuscation vectors: integer/hex/octal/shorthand IPv4 (`http://2130706433/`, `http://0x7f000001/`, `http://0177.0.0.1/`, `http://127.1/` — proven to pass in Pass 5!), embedded IPv6 transition mechanisms (`ipv4_mapped` e.g. `::ffff:127.0.0.1` on Python 3.12+, `sixtofour` `2002::/16`, `teredo` `2001::/32`), CGNAT (`100.64.0.0/10`), encoded zone IDs (`[::1%25eth0]`), userinfo/backslash confusion (`https://allowed.com\@127.0.0.1/`), and non-ASCII/IDNA homographs.
- **Fix:** Reject `parsed.username`, `parsed.password`, `"\\"` and ASCII control chars; strip `%` zone IDs and IDNA-normalize hostname to ASCII; parse dotted/numeric IPv4 via `socket.inet_aton(host)` alongside `ipaddress.ip_address(host)` to catch int/hex/octal/shorthand IPv4; recursively unwrap `.ipv4_mapped`, `.sixtofour`, and `.teredo` (handling Teredo tuple); and reject any address where `not ip_check.is_global` or `ip_check in ipaddress.ip_network("100.64.0.0/10")` (plus internal suffixes).
- **Status:** [x] fixed — harden validate_connector_endpoint_url against obfuscated IPv4/IPv6/CGNAT/userinfo/backslash/IDNA SSRF (37d06282)

### C6 — `apps/assets/views/IntegrationApiHub/*.py` (`*_delete`, `connector_{create,edit}`) & `templates/assets/integrationapihub/**/*.html`
- **Found by:** code-reviewer, frontend-reviewer, qa-smoke-tester, security-reviewer
- **Lesson:** L27
- **Problem:** Two AuthZ / UI parity defects: (1) Non-admin tenant members (`is_tenant_admin=False`) can delete connectors/streams/GL batches/GIS mappings and create/modify egress URLs + `webhook_verify_tls` because `*_delete` and `connector_{create,edit}` only enforce `@login_required` instead of `@tenant_admin_required`; (2) `detail.html` for connectors (`lines 29-43`) and GL batches (`lines 22-27`) renders `@tenant_admin_required` POST action forms (`Rotate Secret`, `Execute & Reconcile GL Batch`) unconditionally to non-admins, causing `403` on click (and `Execute & Reconcile GL Batch` stays visible even after posting).
- **Fix:** Add `@tenant_admin_required` to all 4 `*_delete` views and `connector_create`/`connector_edit`; pass `is_tenant_admin` context (or check `request.user.is_superuser or request.user.is_tenant_admin` cleanly in templates matching sibling `depreciation_schedule/detail.html`); wrap admin-only POST action forms and delete/connector create-edit UI buttons accordingly; and hide `Execute & Reconcile GL Batch` once `batch.journal_entry` is linked or `batch.status == "posted"`.
- **Status:** [x] fixed — enforce @tenant_admin_required on connector_create/edit and all 4 *_delete views and hide admin-only UI actions from non-admins (cdc54f4d, 13e04c89, eff93ccf, 61098f84, 74af1d06, 2cc1efd9, 96c092aa, 682d3aef, 1119c4e6; contract synced 1821e91f)

### C7 — `apps/assets/forms/IntegrationApiHub/AssetGlSyncBatches.py:138-148` & `apps/assets/views/IntegrationApiHub/{AssetGlSyncBatches,AssetTelemetryStreams}.py`
- **Found by:** performance-reviewer, qa-smoke-tester
- **Lesson:** L18
- **Problem:** Runtime `CaptureQueriesContext` confirmed two severe chained `__str__` / detail N+1 defects: (1) `AssetGlSyncBatchForm` evaluates `PurchaseOrder` (`__str__` reads `self.vendor`) and `AssetDepreciationSchedule` (`__str__` reads `self.fixed_asset.name`) without `.select_related(...)`, causing `batch_create` GET to jump `18 -> 38` queries (`+20` for 10 POs + 10 Schedules), and `batch_detail` (`AssetGlSyncBatches.py:169-183`) omits `"purchase_order__vendor"` and `"depreciation_schedule__fixed_asset"`; (2) `stream_detail` (`AssetTelemetryStreams.py:175-185`) iterates `recent_readings` rendering `r.triggered_maintenance_request.number` (`detail.html:192-193`) without `.select_related("triggered_maintenance_request")`, jumping `10 -> 20` queries (`+10` for 10 readings) while joining 3 unused FKs (`operational_asset`, `fixed_asset`, `recorded_by`).
- **Fix:** Add `.select_related("vendor")` on `purchase_order` and `.select_related("fixed_asset").only(...)` on `depreciation_schedule` in `AssetGlSyncBatchForm`; add `"purchase_order__vendor"` and `"depreciation_schedule__fixed_asset"` to `batch_detail`'s `select_related`; and replace `stream_detail`'s 3 unused joins with `.select_related("triggered_maintenance_request").only(...)`.
- **Status:** [x] fixed — select_related vendor/fixed_asset in AssetGlSyncBatchForm and batch_detail and replace unused joins with triggered_maintenance_request in stream_detail (888861e4, 5ecca08f, fc578c15)

### C8 — `templates/assets/integrationapihub/{asset_integration_connector,asset_telemetry_stream,asset_gl_sync_batch,asset_gis_mapping}/list.html` & `asset_telemetry_stream/detail.html:161`
- **Found by:** explorer, frontend-reviewer
- **Problem:** Five data tables wrap `<table>` in `.table-responsive`, which is undefined in `static/css/theme.css` (`theme.css:294` defines `.table-wrap { overflow-x: auto; border-radius: var(--radius); }`), breaking horizontal table scroll containment on narrow screens.
- **Fix:** Replace `<div class="table-responsive">` with `<div class="table-wrap">` across all 5 templates.
- **Status:** [x] fixed — replace undefined .table-responsive with .table-wrap across all 5 table templates (1e061fda, cc3b4a7d, 0d2ad47b, 5f0e8618, c5c69a00)

---

## Important

### I1 — `apps/assets/models/IntegrationApiHub/{AssetIntegrationConnectors,AssetTelemetryStreams,AssetGlSyncBatches,AssetGisMappings}.py` (`clean()`)
- **Found by:** explorer, qa-smoke-tester, security-reviewer
- **Problem:** Runtime QA confirmed direct model `.full_clean()` calls bypass form checks: (1) all 4 models omit `fk.tenant_id == self.tenant_id` validation on tenant-owned FKs when `self.tenant_id` is set; (2) `AssetTelemetryStream.clean()` does not require `operational_asset or fixed_asset`; and (3) `AssetGlSyncBatch.clean()` leaves `variance_amount` stale prior to `save()`.
- **Fix:** In each model's `clean()`, validate `rel.tenant_id == self.tenant_id` for all populated tenant-owned FKs whenever `self.tenant_id` is set; enforce `if not self.operational_asset_id and not self.fixed_asset_id:` in `AssetTelemetryStream.clean()`; and compute `self.variance_amount = src - tgt` inside `AssetGlSyncBatch.clean()` as well as `save()`.
- **Status:** [x] fixed — add shared validate_tenant_fks helper, enforce same-tenant FKs across all 4 models, require linked asset on stream clean(), and compute variance_amount in batch clean() (ca8a64e6, 9798b97b, 616dba87, 79d4c051, 9c1b0b69)

### I2 — `apps/assets/views/IntegrationApiHub/{AssetTelemetryStreams,AssetGlSyncBatches,AssetGisMappings}.py`
- **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
- **Lesson:** L11, L35
- **Problem:** Using `.isdigit()` instead of strict ASCII decimal parsing on GET query IDs (`connector`, `operational_asset` across list filters and `*_create` prefill) throws unhandled HTTP `500` `ValueError` on Unicode digits like `"²"` (`\u00b2`), confirmed across 6 routes in Pass 5. Furthermore, `GET ?connector=<pk>` initial prefill in `stream_create`, `batch_create`, and `mapping_create` does not verify `AssetIntegrationConnector.objects.filter(tenant=request.tenant, pk=...).exists()`.
- **Fix:** Extract a shared `_parse_pos_int` helper (in `apps/assets/views/IntegrationApiHub/_common.py` or `IntegrationApiHub/__init__` helper — keep DRY, `isascii() and isdigit()` / `try: int(...)`) for all 8 filter/prefill sites, and verify `AssetIntegrationConnector` exists in `request.tenant` before setting `initial["connector"]`.
- **Status:** [x] fixed — add shared parse_pos_int (ASCII BigAutoField range) and verified_connector_initial helpers in _common.py and wire into stream, batch, and mapping views (2d3c5c42, 2aacc712, b7bbff2b, 9c324899)

### I3 — `apps/assets/models/IntegrationApiHub/{AssetGlSyncBatches,AssetGisMappings}.py` & `apps/assets/forms/IntegrationApiHub/{AssetGlSyncBatches,AssetGisMappings}.py`
- **Found by:** security-reviewer
- **Problem:** Unbounded `TextField` JSON validation (`field_mapping_json`, `payload_summary`, `geojson_payload`) calls raw `json.loads()` without payload size limits, `RecursionError` protection (deeply nested JSON throws HTTP 500), or `parse_constant` rejection of non-RFC `NaN`/`Infinity` literals.
- **Fix:** Use a shared strict JSON validator helper enforcing `<= 65536` UTF-8 bytes, catching `(ValueError, RecursionError)`, and passing `parse_constant` to reject `NaN`/`Infinity`/`-Infinity`.
- **Status:** [x] fixed — add shared validate_json_object helper (64 KB cap, dict root, NaN/Infinity/RecursionError guard) and payload_summary cap across models and forms (e3a789fa, 99e375fe, 35eb2aec, ad4f1505, fc2b02a4; contract synced 1821e91f)

### I4 — `apps/assets/forms/IntegrationApiHub/{AssetIntegrationConnectors,AssetGisMappings}.py`
- **Found by:** security-reviewer
- **Lesson:** L40
- **Problem:** `"health_status"` on `AssetIntegrationConnectorForm` (`Meta.fields`, line 39) and `"drift_status"` on `AssetGisMappingForm` (`Meta.fields`, line 49) expose system-verified state fields for mass assignment without executing `test_connection` or `verify_spatial_sync`.
- **Fix:** Remove `"health_status"` from `AssetIntegrationConnectorForm.Meta.fields` and `"drift_status"` from `AssetGisMappingForm.Meta.fields` (keep them driven by probe/verification actions and defaults; document update in `contract-assets-11.15.md`).
- **Status:** [x] fixed — mark health_status and drift_status editable=False on models and remove them from connector/mapping forms and templates (ea35c16a, a6adaa84, c98322b0, 1b121087, debb0317, 9c8d02ab; contract synced 1821e91f)

### I5 — `apps/assets/models/IntegrationApiHub/AssetTelemetryStreams.py:26-30, 237-238`
- **Found by:** explorer
- **Problem:** `resolve_telemetry_metric_and_unit()` checks `if self.metric_unit in UNIT_FALLBACK_MAP:` (line 237) and then ignores `UNIT_FALLBACK_MAP[self.metric_unit]` in favor of `FALLBACK_11_7_METRIC_DEFAULT_UNIT`, while `UNIT_FALLBACK_MAP["hours"] = "amperes"` contradicts `.claude/tasks/contract-assets-11.15.md:193` (`"celsius"`).
- **Fix:** Set `UNIT_FALLBACK_MAP["hours"] = "celsius"` matching the contract, apply `UNIT_FALLBACK_MAP[self.metric_unit]` on line 238 when `metric_unit` is in the fallback map, and update/verify contract parity.
- **Status:** [x] fixed — align UNIT_FALLBACK_MAP["hours"] = "celsius" and apply mapped unit in resolve_telemetry_metric_and_unit (cad4abe7; contract synced 1821e91f)

### I6 — `apps/assets/models/IntegrationApiHub/{AssetGlSyncBatches,AssetGisMappings}.py` & `apps/assets/migrations/`
- **Found by:** performance-reviewer
- **Problem:** `AssetGlSyncBatch` lacks composite indexes `(tenant, batch_date, number)` and `(tenant, connector)`, and `AssetGisMapping` lacks `(tenant, connector)` (used by `batch_list` ordering/filtering and `connector_detail` child panels).
- **Fix:** Add `idx_agls_ten_date_num`, `idx_agls_ten_conn`, and `idx_agis_ten_conn` (`<= 30`-char names) to `Meta.indexes` and generate + apply + commit migration `0019` cleanly.
- **Status:** [x] fixed — add composite indexes idx_agls_ten_date_num, idx_agls_ten_conn, idx_agis_ten_conn and migrate cleanly via 0019 (692adec7, 4b59f904, 2ff55a71; contract synced e593d35f)

### I7 — `apps/assets/views/IntegrationApiHub/*.py` & `apps/assets/forms/IntegrationApiHub/AssetGlSyncBatches.py:121-133`
- **Found by:** performance-reviewer
- **Problem:** List views carry 14 unused `select_related` JOINs (`connector_list` joins 4 unused FKs; `stream_list` 3; `batch_list` 4; `mapping_list` 3), `connector_detail` joins 6 unused FKs across child panels, all 4 list views + `connector_detail` eagerly fetch large un-deferred `TextField` blobs (`geojson_payload`, `field_mapping_json`, `payload_summary`, `last_error_message`, `notes`), filter dropdowns load full `SELECT *` `AssetIntegrationConnector`/`scm.Asset` rows, and `AssetGlSyncBatchForm.__init__` runs duplicate `GLAccount` queries.
- **Fix:** Trim `select_related` strictly to FKs rendered in templates; add `.defer(...)` / `.only(...)` on list & `connector_detail` child queries; narrow filter dropdown querysets to `.only("id", "number", "name")` / `.only("id", "code", "name")`; and share one evaluated `GLAccount` queryset/choices pass + `.only(...)` dropdown queries in `AssetGlSyncBatchForm`.
- **Status:** [x] fixed — dedupe GLAccount query and narrow dropdowns in AssetGlSyncBatchForm; trim unused joins, defer blob columns, and narrow filter dropdowns after kpis.aggregate across all 4 view modules (5ea26e75, df643067, 2fa9570e, b2e9f1a2, 940bd4b1)

### I8 — `apps/assets/forms/IntegrationApiHub/{AssetIntegrationConnectors,AssetTelemetryStreams,AssetGisMappings}.py` & `templates/assets/integrationapihub/**/{list,detail}.html`
- **Found by:** code-reviewer, explorer, frontend-reviewer
- **Problem:** Templates and forms use CSS classes absent from `static/css/theme.css`: `form-checkbox` on 3 checkbox widgets (instead of `.form-check`), `btn-xs` on 11 row action/card header buttons (instead of `.btn-sm`), `.stat-body` in all 4 KPI grids, and `.card-footer` on all 4 pagination wrappers.
- **Fix:** Replace `form-checkbox` with `form-check` (or inherit `TenantModelForm` default) and `btn-xs` with `btn-sm`; remove `.stat-body` (matching `.stat-card` flex column layout in `templates/assets/overview.html`) and replace `.card-footer` with valid card/flex footer classes/styles from `theme.css`.
- **Status:** [x] fixed — replace form-checkbox with form-check, btn-xs with btn-sm, and remove undefined stat-body/card-footer across forms and templates (4b0913f1, bb295667, f4fc0c89, 57db1eff, d807b6f6, 19fd1499, d8d6f0a8, e042e91f, d1650b55)

### I9 — `templates/assets/integrationapihub/asset_telemetry_stream/{list,detail}.html` & `asset_gis_mapping/detail.html:99`
- **Found by:** code-reviewer, frontend-reviewer, qa-smoke-tester
- **Problem:** Django's `|default` filter treats `Decimal("0.0000")` and `Decimal("0.000")` as falsy, hiding valid zero values on `stream.warning_threshold` (`list.html:164`), `detail.html:47` placeholder + `:107` threshold triad, and `lrs_from_measure|default:"0"` (`asset_gis_mapping/detail.html:99`).
- **Fix:** Replace `|default` on numeric/decimal values with explicit `{% if val is not None %}` branches or `|default_if_none`.
- **Status:** [x] fixed — preserve zero numeric thresholds and LRS measures with explicit is not None checks across list and detail templates (96cd17e0, 6fa70add, 7bdd99a5, cef831d7)

### I10 — `templates/assets/integrationapihub/asset_gis_mapping/{list,detail}.html`
- **Found by:** code-reviewer, frontend-reviewer
- **Problem:** In `asset_gis_mapping/list.html:166-174` and `detail.html:90`, records with `is_linear_asset=True` and blank `lrs_route_id`, or with only one of `latitude`/`longitude` set, render an empty `<td>` in list rows or `Not specified` in detail.
- **Fix:** Explicitly show `{{ mapping.latitude|default_if_none:"—" }}, {{ mapping.longitude|default_if_none:"—" }}` whenever either coordinate `is not None`, and fall back to `<span class="text-muted">—</span>` when neither coordinates nor `lrs_route_id` exist.
- **Status:** [x] fixed — render partial latitude/longitude coordinates and dash fallback cleanly in GIS mapping list and detail templates (12044e43, 51ecd77b)

### I11 — `templates/assets/integrationapihub/**/{form,detail,list}.html`
- **Found by:** frontend-reviewer
- **Problem:** Unscoped light-mode Tailwind color utilities (`bg-red-50`, `bg-amber-50`, `bg-white`, `bg-slate-50`, `text-slate-*`, `border-slate-*`) break contrast when `html.dark` is active (`templates/base.html:27`).
- **Fix:** Replace `text-slate-*` and `border-slate-*` with `theme.css` variables/classes (`.text-muted`, `var(--text)`, `var(--border)`, `var(--bg)`) and add matching `dark:*` variants on alert/reveal/code boxes (`bg-red-50 dark:bg-red-950/30`, `bg-amber-50 dark:bg-amber-950/30`, etc.).
- **Status:** [x] fixed — add dark-mode variants and theme text variables across all 12 Integration & API Hub templates (776e7043, 52bfb11e, 172c9c56, 485e6ff3, cf98e72a, 23531942, bef84367, 4d9736e4, 5918678c, 8b15e51c, fff0814c, d937c044)

### I12 — `templates/assets/integrationapihub/*/list.html` (all 4 filter bars)
- **Found by:** code-reviewer, frontend-reviewer
- **Problem:** All 23 filter `<label class="form-label text-xs">` tags omit matching `for=`/`id=` pairs, and the 4 icon-only Reset buttons omit `aria-label`.
- **Fix:** Add paired `for="id_filter_<name>"` / `id="id_filter_<name>"` on all filter labels/controls and `aria-label="Reset filters"` on the 4 Reset `<a>` controls.
- **Status:** [x] fixed — add paired filter label for/id attributes and reset aria-label across all 4 list templates (964f7555, eea77109, 011a5a97, 28d8c166)

### I13 — `templates/assets/integrationapihub/{asset_integration_connector,asset_telemetry_stream,asset_gis_mapping}/form.html`
- **Found by:** frontend-reviewer
- **Problem:** Boolean checkbox rows omit inline `form.<field>.errors` rendering, and `asset_telemetry_stream/form.html:68-78` omits `.form-help` guidance explaining that at least one of Operational Asset or Financial Fixed Asset is required.
- **Fix:** Render `<div class="form-error">{{ form.<field>.errors.0 }}</div>` conditionally inside all 3 checkbox rows and add `.form-help` guidance beneath the asset fields on `asset_telemetry_stream/form.html`.
- **Status:** [x] fixed — add inline form-error rendering on checkboxes and asset linkage form-help guidance across form templates (c890fafe, d8c0e352, 97309004)

---

## Minor

### M1 — `apps/assets/views/IntegrationApiHub/AssetIntegrationConnectors.py:153-157`
- **Found by:** security-reviewer
- **Lesson:** L25
- **Problem:** `connector_detail` peeks `request.session.get("_aicn_secret_reveal")` before popping only if `pk` matches, allowing a rotated secret to persist in DB-backed `django_session` if the operator opens a different page before returning.
- **Fix:** Use unconditional `reveal = request.session.pop("_aicn_secret_reveal", None)` on detail render and check `isinstance(reveal, dict) and reveal.get("pk") == connector.pk`.
- **Status:** [x] fixed — pop one-time _aicn_secret_reveal session key unconditionally in connector_detail (470adc67)

### M2 — `apps/assets/admin.py:479-509` & `apps/assets/views/IntegrationApiHub/AssetIntegrationConnectors.py:159-167`
- **Found by:** security-reviewer
- **Problem:** The 4 new `ModelAdmin` classes omit `exclude = ("api_key_hash",)` (on connector admin), `"tenant"` in `list_filter`, `readonly_fields`, and posted-batch delete/change protection on `AssetGlSyncBatchAdmin`; `connector_detail` queries `connector.telemetry_streams`/`gl_sync_batches`/`gis_mappings` without `.filter(tenant=connector.tenant)`.
- **Fix:** Harden the 4 `ModelAdmin` definitions (`exclude = ("api_key_hash",)`, `"tenant"` filter, `readonly_fields`, posted-batch lock in `AssetGlSyncBatchAdmin`) and add `.filter(tenant=connector.tenant)` to all 3 child queries in `connector_detail`.
- **Status:** [x] fixed — add defense-in-depth tenant filter on connector_detail child queries and harden 11.15 ModelAdmins with secret exclusion, tenant filters, readonly fields, and posted-batch guards (f36a8c22, 4888e4fc)

### M3 — `templates/assets/integrationapihub/**/{list,detail}.html`
- **Found by:** frontend-reviewer
- **Problem:** Action and numeric columns use physical `text-right` instead of RTL-consistent logical `text-end`.
- **Fix:** Switch `text-right` to `text-end` on all 11.15 table headers/cells.
- **Status:** [x] fixed — switch physical text-right to RTL-logical text-end across all 4 list templates (ee31f66c, 9fa844f4, 58496f65, 7e5747e4)

### M4 — `templates/assets/integrationapihub/{asset_gl_sync_batch,asset_telemetry_stream}/detail.html`
- **Found by:** explorer, frontend-reviewer
- **Problem:** `asset_gl_sync_batch/detail.html:136` renders `batch.purchase_order` as plain text while sibling ERP references link to their detail views, and check `asset_telemetry_stream/detail.html` operational/fixed asset link parity (`scm:asset_detail` / `accounting:fixed_asset_detail`).
- **Fix:** Link `batch.purchase_order` with `{% url 'scm:purchaseorder_detail' batch.purchase_order.pk %}` (and ensure `stream/detail.html` links both asset FKs if plain text).
- **Status:** [x] fixed — link Purchase Order detail in batch detail, operational/fixed asset details in stream detail, and SCM Location detail in GIS mapping detail (f65ee548, afabd489, a6e393b5)

### M5 — `templates/assets/integrationapihub/asset_telemetry_stream/detail.html:183-189`
- **Found by:** frontend-reviewer
- **Problem:** Recent Telemetry Readings duplicates threshold status-to-badge `if/elif` mapping instead of using `r.threshold_status_css`.
- **Fix:** Render `<span class="badge {{ r.threshold_status_css }}">{{ r.get_threshold_status_display }}</span>`.
- **Status:** [x] fixed — reuse AssetTelemetryReading.threshold_status_css property on stream detail readings table (01841bc1)

### M6 — `templates/assets/integrationapihub/asset_integration_connector/detail.html:56-60`
- **Found by:** frontend-reviewer
- **Problem:** One-time `plaintext_once` secret reveal banner lacks a copy-to-clipboard button.
- **Fix:** Add a static `<button type="button">` using `navigator.clipboard.writeText(...)` reading `data-*` / DOM sibling text (no template values interpolated into JS).
- **Status:** [x] fixed — add static progressive-enhancement Copy button reading DOM secret text safely (b4ebfa73)

### M7 — `apps/core/navigation.py:3340-3355`
- **Found by:** explorer
- **Problem:** The convenience aliases in `LIVE_LINKS["11.15"]` share identical URLs/queries across multiple bullet entries, causing `_mark_active` to highlight multiple items simultaneously when visiting `stream_list`, `gl_sync_batch_list`, or `gis_mapping_list`.
- **Fix:** Inspect `apps/core/navigation.py` & any nav parity tests — keep distinct route/query combinations if safe without breaking 5-bullet `NavERP.md` parity, or skip with reason if parity requires exact aliases.
- **Status:** [x] fixed — remove duplicate convenience aliases from LIVE_LINKS["11.15"] keeping all 5 NavERP.md bullets and unfiltered connector hub unique (adb30b79; contract synced f0ba3378; verified with test_navigation_active.py)

### M8 — `apps/assets/views/IntegrationApiHub/*.py` & `apps/assets/management/commands/seed_assets.py:3342`
- **Found by:** performance-reviewer
- **Problem:** Minor clarity/determinism polish: list views attach `select_related` on `base_qs` before `kpis = base_qs.aggregate(...)`, and `_seed_tenant_11_15` calls `Currency.objects.filter(is_active=True).first()` without `.order_by("code")`.
- **Fix:** Apply `select_related`/`defer` after `kpis = base_qs.aggregate(...)` and add `.order_by("code")` in `_seed_tenant_11_15`.
- **Status:** [x] fixed — enforce deterministic Currency.order_by("code") in _seed_tenant_11_15 (35905fe3; list views aggregate-before-select_related completed in I7)

### M9 — `templates/assets/integrationapihub/*/form.html:41`
- **Found by:** frontend-reviewer
- **Problem:** Form templates use Tailwind `grid grid-cols-1 md:grid-cols-2 gap-4` instead of `.form-grid` (`static/css/theme.css:308`).
- **Fix:** Align on `.form-grid` if compatible with responsive 2-column layout (or skip noting `contract-assets-11.15.md:505` exception).
- **Status:** [~] skipped — static/css/theme.css .form-grid uses auto-fit minmax(260px,1fr) (3 cols inside max-w-4xl), breaking full-width md:col-span-2 fields; grid grid-cols-1 md:grid-cols-2 gap-4 matches contract-assets-11.15.md:509 and 100% of sibling templates/assets/**/form.html

### M10 — `apps/assets/views/overview.py` & `templates/assets/overview.html`
- **Found by:** explorer
- **Problem:** Assets command center `overview.html` does not yet surface 11.15 Integration & API Hub summary counts/quick links.
- **Fix:** Evaluate `overview.py` / `overview.html` — add concise 11.15 quick link/KPI tile if consistent with existing sub-modules (or defer to module-level overview close-out in gaps if out of 11.15 scope).
- **Status:** [x] fixed — add tenant-scoped 11.15 Integration & API Hub summary KPIs to overview view and quick-navigation cards strip to overview.html (9984ba72, 95f68637, 5352750e)

---

## Out-of-Scope Cross-Module / L28 Observations (Log in `.agents/tasks/gaps-assets-11.15.md`, Do Not Edit Sibling Apps Here)

- **X1 (Core `apps/core/crud.py:265-289` & `apps/core/utils.py:51-60`, Found by: security-reviewer):** `_SENSITIVE_AUDIT_FIELDS` omits `"api_key_hash"`, `"api_key_prefix"`, `"signing_secret_hash"`, `"credential_hash"`, `"webhook_secret"`, `"private_key"`, `"client_secret"`, and `write_audit_log` does not centrally redact keys matching `_SENSITIVE_AUDIT_FIELDS`. Track for Module 0 `core` pass.
- **X2 (Assets 11.4 `apps/assets/{forms,models}/AssetDepreciation/AssetDepreciationSchedules.py`, Found by: security-reviewer L28):** `AssetDepreciationScheduleForm` omits `else: .none()` when `tenant is None`, and `post_to_gl` lacks `select_for_update()`, `fiscal_period.is_open`, and FK tenant checks. Out of 11.15 scope — log in `.agents/tasks/gaps-assets-11.15.md` and skip any 11.4 edits here.
- **X3 (Assets 11.7 `apps/assets/models/AssetReliability/AssetTelemetryReadings.py:189-195`, Found by: performance-reviewer):** Adding composite indexes `(tenant, operational_asset, recorded_at)` and `(tenant, fixed_asset, recorded_at)` on 11.7's `AssetTelemetryReading` improves `stream_detail` scale at high volume. Track for 11.7/module index pass.

---

## Audit Pass Verification Summaries (Archive)

### Pass 1 (`nav-code-reviewer` `08873c36`)
- Audited models, forms, views, URLs, admin, seeder, migration `0018`, navigation, and all 12 templates; flagged C1–C2, I1–I4, M1–M2 (consolidated into `C1, C3, C4, C5, C6, I2, I8, I9, I10, I12`).

### Pass 2 (`nav-explorer` `3242fbbf-38b8-4a4e-82b5-6b084e7258a7`)
- **Verified Clean:** Package exports (`apps/assets/{models,forms,views,urls}/__init__.py`), 4 admin registrations (`apps/assets/admin.py:479-508`), additive migration `0018` (`<= 30`-char index/constraint names), `LIVE_LINKS["11.15"]` (`apps/core/navigation.py:3340-3355`, zero portal links L32), L55 sibling coexistence, cross-module field lengths (`JournalEntry.entry_type`, `AssetTelemetryReading.sensor_identifier`, `AuditLog.action`), `ProtectedError` delete guard, and idempotent `seed_assets.py`.

### Pass 3 (`nav-frontend-reviewer` `28e670d2-4a91-4a2c-b741-02fee4ee0282`)
- **Verified Clean:** Zero `{# ... #}` comment leaks (L2), only valid `theme.css` badge modifiers & KPI colors (L33), valid `{% url %}` resolution & view context alignment, `|stringformat:"d"` PK filter preservation across paginators (L9), None-safe FK filters (L10), safe session-popped `plaintext_once` rendering, CSRF tokens on all POST forms, and 100% `Meta.fields` coverage across all 4 forms.

### Pass 4 (`nav-performance-reviewer` `5711339c-8805-44e6-8b23-b02b2cb41cae`)
- **Verified Clean:** Single-query conditional `.aggregate(Count("id", filter=Q(...)))` KPI stat cards across all 4 list views, pre-pagination filtering, `Paginator(..., 25)`, zero unbounded `list(qs)` calls, remaining FK `__str__` methods free of secondary hops, zero template `.all`/`.count` loop queries, bounded `[:10]` child panels, atomic audit-logged action writes, and idempotent `_seed_tenant_11_15`.

### Pass 5 (`nav-qa-smoke-tester` `c37afbdf-4547-4f7c-90a1-a784b47c14f0`, Report-Only Runtime Probe)
- **Verified Clean:** `manage.py check` (`0` issues), `makemigrations --check --dry-run` (`No changes detected`), all 25 routes resolve + auth redirect + 9 POST-only `405` on GET, 21 cross-tenant IDOR -> `404` probes, empty states, full CRUD happy paths, `ProtectedError` on connector delete, posted `batch_delete` block, `test_connection`, `rotate_secret`, `execute_reconcile_batch`, `verify_spatial_sync`, pagination (`?page=2`, `?page=999`), junk query strings, non-admin POST -> `403`, and clean workspace/DB teardown.

### Pass 6 (`nav-security-reviewer` `ba8f040e-0a84-48c0-915c-e876bd4e65e8`)
- **Verified Clean:** `api_key_prefix`/`api_key_hash` `editable=False` + excluded from forms + SHA-256 `secrets.token_urlsafe(24)` secret minting + masked display (`L20`), zero-outbound endpoint probe in `test_connection`, `@require_POST` + `{% csrf_token %}` on all 9 mutating routes, zero `|safe`/`mark_safe`/`<script>` XSS vectors, tenant-scoped telemetry reading history, `.example.com` seeder fixtures, and zero portal sidebar links (`L32`).
