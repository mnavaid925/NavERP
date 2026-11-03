# Review Findings — Sub-module 10.1: Data Integration & Ingestion (Module 10 — Business Intelligence, `bi`)

- **Sub-module:** 10.1 Data Integration & Ingestion
- **Module:** 10 Business Intelligence
- **Changeset:** `176152520e23192afbc9628bb27f155889146634...HEAD`
- **Review Date:** 2026-11-03
- **Phase:** 4 Review (6 Reviewers run strictly serially)

---

## Consolidated Actionable Findings

### Critical

- [x] **C1**: `apps/bi/views/DataIntegration/*.py` — **TypeError on write_audit_log**: `apps/core/utils.py:10` defines `write_audit_log(user, obj, action, changes=None, tenant=None)`. All views pass `request, action=..., model_name=..., object_id=...`, which raises `TypeError: write_audit_log() got an unexpected keyword argument 'model_name'` on every POST save/delete/action (create, edit, delete, test, trigger, reset, retry). Fix: Update all 14 calls to `write_audit_log(request.user, obj, action, tenant=request.tenant)`. Fixed in `d377ba04`, `ce795f7c`, `6cf154e7`, `4e068f41`.
- [x] **C2**: `apps/bi/forms/DataIntegration/IngestionPipelines.py:30` — **Plaintext secret exposure in form (Lesson L20)**: `webhook_secret` is listed in `Meta.fields`, causing plaintext HMAC secrets to be rendered into HTML `<input type="text" name="webhook_secret" value="...">` on edit pages. Fix: Remove `'webhook_secret'` from `Meta.fields` and remove the form group from `templates/bi/data_integration/ingestion_pipeline/form.html`. Fixed in `035c499d`, `e2091789`.
- [x] **C3**: `templates/bi/data_integration/ingestion_pipeline/detail.html:116` — **Cleartext secret displayed in detail view**: Secret token is rendered unmasked in the HTML body. Fix: Mask secret display with `••••••••••••••••` or hide unless revealed. Fixed in `7ec2ad0a`.

### Important

- [x] **I1**: `apps/bi/views/DataIntegration/IngestionPipelines.py:44` — **500 ValueError on non-integer connector_id**: Passing `?connector_id=notanint` crashes with an unhandled `ValueError`. Fix: Guard with `if connector_id and connector_id.isdigit(): queryset = queryset.filter(connector_id=int(connector_id))`. Fixed in `a1ac4d5e`.
- [x] **I2**: `apps/bi/views/DataIntegration/IngestionRuns.py:43` — **500 ValueError on non-integer pipeline_id**: Passing `?pipeline_id=junk` crashes with an unhandled `ValueError`. Fix: Guard with `if pipeline_id and pipeline_id.isdigit(): queryset = queryset.filter(pipeline_id=int(pipeline_id))`. Fixed in `d8141491`.
- [x] **I3**: `apps/bi/views/DataIntegration/DataSourceConnectors.py:142` — **Uncaught ProtectedError on connector deletion**: `IngestionPipeline.connector` uses `on_delete=models.PROTECT`. Deleting a connector that is referenced by pipelines crashes with `ProtectedError`. Fix: Wrap `connector.delete()` in `try ... except ProtectedError:` with a friendly warning message and redirect. Fixed in `c1752ce9`.
- [x] **I4**: `apps/bi/views/DataIntegration/IngestionPipelines.py:168-186` — **Missing atomic transaction in pipeline trigger**: `IngestionRun` creation and `pipeline.last_run_at` update run in separate queries without a transaction. Fix: Wrap in `with transaction.atomic():`. Fixed in `25df0436`.
- [ ] **I5**: `apps/bi/views/DataIntegration/IngestionRuns.py:105-123` — **Missing atomic transaction in run retry**: Run creation and pipeline update run in separate queries without a transaction. Fix: Wrap in `with transaction.atomic():`.
- [ ] **I6**: `templates/bi/data_integration/**/*.html` — **Non-existent CSS classes .text-secondary and .text-primary (Lesson L13)**: Neither class exists in `theme.css`. Fix: Replace `.text-secondary` with `.text-muted` (or `text-slate-500`) and `.text-primary` with `.text-brand` (or `text-blue-600`) across all templates.
- [ ] **I7**: `templates/bi/data_integration/data_integration_hub.html` & `ingestion_run/detail.html` — **Ad-hoc KPI metrics grid**: Summary cards use ad-hoc layout instead of canonical `.stat-grid`, `.stat-card`, `.stat-value`, `.stat-label` from `theme.css`. Fix: Adopt design-system classes.
- [ ] **I8**: `apps/bi/views/DataIntegration/IngestionPipelines.py:72` — **Missing select_related('cdc_config') on pipeline detail**: Reverse OneToOne `pipeline.cdc_config` is accessed in detail view without `select_related`, triggering an extra DB query. Fix: Add `"cdc_config"` to `select_related`.
- [ ] **I9**: `templates/bi/data_integration/data_source_connector/detail.html` & `ingestion_pipeline/detail.html` — **Redundant .count() and sliced count queries**: Multiple queries triggered by `{{ pipelines.count }}` and `{{ runs.count }}`. Fix: Pre-evaluate `list(...)` and pass counts in context.
- [ ] **I10**: `apps/bi/models/DataIntegration/IngestionRuns.py:65` — **Missing (tenant, -started_at) composite index**: Queries sorted by `-started_at` without status or pipeline filter require filesort on large append-only telemetry table. Fix: Add `models.Index(fields=["tenant", "-started_at"], name="idx_bijr_ten_start_desc")` and run `makemigrations bi` / `migrate`.
- [ ] **I11**: `apps/bi/views/DataIntegration/*.py` — **Redundant unfiltered count before pagination**: List views run `queryset.count()` before parsing filter params. Fix: Pass `page_obj.paginator.count` instead.
- [ ] **I12**: `apps/bi/views/DataIntegration/CdcSyncConfigs.py:146` — **Missing @tenant_admin_required gate on reset cursor**: High-impact CDC stream reset requires privileged admin role. Fix: Add `@tenant_admin_required`.
- [ ] **I13**: `apps/bi/forms/DataIntegration/DataSourceConnectors.py:15` — **Insecure credential prompt in JSON help text**: Help text suggests entering credentials into cleartext JSONField. Fix: Direct users to `core.ApiCredential` dropdown.
- [ ] **I14**: `templates/bi/data_integration/**/*.html` — **Missing tenant-admin UI checks on destructive buttons (Lesson L27 converse)**: Delete and reset buttons rendered for non-admins lead to 403. Fix: Wrap in `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

### Minor

- [ ] **M1**: `apps/bi/views/DataIntegration/CdcSyncConfigs.py:143` — **Inflexible redirect in cdc_sync_config_delete**: Always redirects to pipeline detail. Support redirecting back to `cdc_sync_config_list` when initiated from list.
- [ ] **M2**: `apps/bi/management/commands/seed_bi.py` — **Missing --flush argument in seeder**: Support `--flush` flag to reset and re-seed demo data.
- [ ] **M3**: `templates/bi/data_integration/**/detail.html` — **Missing "Back to List" button in page-actions**: Add explicit back-to-list navigation button in detail headers and sidebars.
- [ ] **M4**: `templates/bi/data_integration/**/list.html` — **Filter reset buttons missing .btn-icon and aria-label**: Add `.btn-icon` and `aria-label="Clear filters"`.
- [ ] **M5**: `templates/bi/data_integration/cdc_sync_config/detail.html:85` — **Physical margin ml-1**: Replace `ml-1` with logical `ms-1` for RTL support.
- [ ] **M6**: `apps/bi/views/DataIntegration/DataIntegrationHub.py:18` — **Consolidate hub KPI counts via conditional aggregation**: Consolidate `.count()` queries using `Count(..., filter=Q(...))`.
- [ ] **M7**: `apps/bi/views/DataIntegration/IngestionPipelines.py:50` & `IngestionRuns.py:49` — **Defer heavy JSON fields in dropdown querysets**: Use `.only("id", "name")` when loading connector/pipeline dropdown options.
- [ ] **M8**: `apps/bi/models/DataIntegration/DataSourceConnectors.py` & `IngestionPipelines.py` — **Missing composite ordering indexes**: Add `(tenant, -created_at)` indexes `idx_bdsc_ten_created` and `idx_bing_ten_created`.
- [ ] **M9**: `apps/bi/admin.py:24` — **Missing readonly_fields for webhook_secret in Django Admin**: Add `"webhook_secret"` to `readonly_fields`.
- [ ] **M10**: `apps/bi/views/DataIntegration/IngestionPipelines.py:164` — **Missing status guard on pipeline trigger**: Check if `pipeline.status == 'paused'` before triggering manual run.
