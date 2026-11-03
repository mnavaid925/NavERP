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

