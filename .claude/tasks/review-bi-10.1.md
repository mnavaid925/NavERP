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



