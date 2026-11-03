# Review Findings — Sub-module 10.1: Data Integration & Ingestion (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.1 Data Integration & Ingestion
- **Module:** 10 Business Intelligence
- **Changeset:** `176152520e23192afbc9628bb27f155889146634...HEAD`
- **Review Date:** 2026-11-03
- **Phase:** 4 Review (6 Reviewers run strictly serially)

---

## Reviewer 1: Code Reviewer

### Critical
- **[CR1] Plaintext secret in IngestionPipelineForm**: `apps/bi/forms/DataIntegration/IngestionPipelines.py:30` includes `webhook_secret` in `Meta.fields`, causing the plaintext secret to render in an editable input on form pages (violating lesson L20). Remove from `Meta.fields` and template `templates/bi/data_integration/ingestion_pipeline/form.html`.

### Important
- **[IR1] Unhandled non-integer query parameter in pipeline filter**: `apps/bi/views/DataIntegration/IngestionPipelines.py:44` does `queryset.filter(connector_id=connector_id)` without checking `.isdigit()`, triggering 500 on junk strings.
- **[IR2] Unhandled non-integer query parameter in run filter**: `apps/bi/views/DataIntegration/IngestionRuns.py:43` does `queryset.filter(pipeline_id=pipeline_id)` without checking `.isdigit()`, triggering 500 on junk strings.
- **[IR3] Missing atomic transaction in pipeline trigger**: `apps/bi/views/DataIntegration/IngestionPipelines.py:168-186` creates `IngestionRun` and updates `pipeline.last_run_at` in separate queries without `transaction.atomic()`.
- **[IR4] Missing atomic transaction in run retry**: `apps/bi/views/DataIntegration/IngestionRuns.py:105-123` creates new `IngestionRun` and updates `pipeline.last_run_at` without `transaction.atomic()`.

### Minor
- **[MR1] Inflexible redirect in cdc_sync_config_delete**: `apps/bi/views/DataIntegration/CdcSyncConfigs.py:143` always redirects to `bi:ingestion_pipeline_detail`. Support redirecting back to `bi:cdc_sync_config_list` if initiated from there.
- **[MR2] Missing --flush support in seed_bi**: `apps/bi/management/commands/seed_bi.py` lacks `--flush` argument option.
- **[MR3] Missing Back to List button in connector detail**: `templates/bi/data_integration/data_source_connector/detail.html:30-46` lacks an explicit "Back to List" button in page-actions.

---

## Reviewer 2: Explorer

### Critical
- *None*

### Important
- **[IE1] Uncaught ProtectedError on DataSourceConnector deletion**: `apps/bi/views/DataIntegration/DataSourceConnectors.py:142` calls `connector.delete()` directly without catching `ProtectedError`, causing a 500 crash when pipelines reference the connector. Wrap in `try ... except ProtectedError:` with a friendly message and redirect.

### Minor
- **[ME1] Default db_table naming vs contract underscores**: Models omit `db_table` in Meta, using standard Django naming (`bi_datasourceconnector`). Accept standard Django convention.
- **[ME2] Display of inbound webhook URL pattern in pipeline detail**: `templates/bi/data_integration/ingestion_pipeline/detail.html:112` displays `POST /api/bi/ingest/<token>/` which is a placeholder. Clarify in help text.
- **[ME3] Missing 'Back to List' buttons in detail page-actions**: Add explicit back-to-list buttons in page-actions for connector, pipeline, and CDC detail templates.

---

## Reviewer 3: Frontend Reviewer

### Critical
- *None*

### Important
- **[IF1] Non-existent CSS classes .text-secondary and .text-primary**: `theme.css` does not define `.text-secondary` or `.text-primary` (only `.text-muted`, `.text-brand`, `.text-danger`, etc.). Replace `text-secondary` with `text-muted` (or `text-slate-500`) and `text-primary` with `text-brand` (or `text-blue-600`) across `templates/bi/`.
- **[IF2] Ad-hoc KPI grid instead of theme.css .stat-grid / .stat-card**: In `data_integration_hub.html` and `ingestion_run/detail.html`, KPI metrics use ad-hoc grid cards instead of canonical `.stat-grid`, `.stat-card`, `.stat-value`, `.stat-label`.

### Minor
- **[MF1] Filter clear buttons missing .btn-icon and aria-label**: Filter reset buttons on all 4 list views should use `class="btn btn-icon btn-outline"` with `aria-label="Clear filters"`.
- **[MF2] Missing Back-to-List button in detail sidebars**: Detail templates should include an explicit "Back to List" button in their action sidebars.
- **[MF3] Physical margin ml-1 in CDC detail**: `cdc_sync_config/detail.html:85` uses physical `ml-1`; replace with logical `ms-1` for RTL compatibility.

---

## Reviewer 4: Performance Reviewer

### Critical
- *None*

### Important
- **[IP1] Missing select_related('cdc_config') on pipeline detail**: `apps/bi/views/DataIntegration/IngestionPipelines.py:72` retrieves pipeline without `cdc_config` in `select_related`, issuing an extra query when accessing `pipeline.cdc_config`. Add `"cdc_config"` to `select_related`.
- **[IP2] Redundant .count() and sliced count queries in detail views**: `data_source_connector/detail.html` and `ingestion_pipeline/detail.html` evaluate `{{ pipelines.count }}` and `{{ runs.count }}` multiple times and on sliced querysets. Pre-evaluate `list(...)` and pass `len(...)` or use `|length` in templates.
- **[IP3] Missing (tenant, -started_at) index on high-volume IngestionRun table**: `apps/bi/models/DataIntegration/IngestionRuns.py` orders by `-started_at`, but indexes have intermediate columns (`status`, `pipeline`), causing filesorts on high-volume unfiltered queries. Add `models.Index(fields=["tenant", "-started_at"], name="idx_bijr_ten_start_desc")`.
- **[IP4] Redundant unfiltered count before pagination in list views**: In all 4 list views, `queryset.count()` is evaluated before filters are applied, adding a redundant query. Pass `page_obj.paginator.count` instead.

### Minor
- **[MP1] Consolidate hub KPI counts via conditional aggregation**: In `DataIntegrationHub.py`, combine separate `.count()` calls using `Count("id", filter=Q(...))` to reduce round-trips from 6 to 4.
- **[MP2] Defer heavy JSON fields in dropdown querysets**: In `ingestion_pipeline_list` and `ingestion_run_list`, use `.only("id", "name")` when loading filter dropdown querysets.
- **[MP3] Add (tenant, -created_at) indexes on connectors and pipelines**: Add composite ordering indexes `idx_bdsc_ten_created` and `idx_bing_ten_created`.

---

## Reviewer 5: QA Smoke Tester

### Critical
- **[CS1] TypeError in write_audit_log call signature on all POST/mutation views**: `write_audit_log(user, obj, action, changes=None, tenant=None)` in `apps/core/utils.py:10` requires `user, obj, action`. All views in `apps/bi/views/DataIntegration/` pass `request, action=..., model_name=..., object_id=...`, which raises `TypeError: write_audit_log() got an unexpected keyword argument 'model_name'` on every POST save/delete/action (create, edit, delete, test, trigger, reset, retry). Update all 14 calls to `write_audit_log(request.user, obj, action, tenant=request.tenant)`.

### Important
- **[IS1] 500 ValueError on non-integer connector_id in pipeline list**: `GET /bi/pipelines/?connector_id=notanint` raises unhandled ValueError. Guard with `.isdigit()`.
- **[IS2] 500 ValueError on non-integer pipeline_id in run list**: `GET /bi/runs/?pipeline_id=junk` raises unhandled ValueError. Guard with `.isdigit()`.
- **[IS3] 500 ProtectedError on DataSourceConnector delete**: Deleting a connector referenced by pipelines raises uncaught `ProtectedError`. Wrap in `try ... except ProtectedError:` with user-friendly warning message.

### Minor
- *None*

---

## Reviewer 6: Security Reviewer





