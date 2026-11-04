---
name: bi
description: Work on the Business Intelligence (BI) module (Module 10 — data integration & ingestion, ETL/ELT pipelines, data warehousing, semantic layers, reports, and dashboards). Use when the user asks to add/change/debug anything under apps/bi or templates/bi, extend the BI seeder, touch BI sidebar wiring (LIVE_LINKS 10.1+), or invokes /bi.
---

# Business Intelligence (BI) Module (Module 10)

Comprehensive enterprise Business Intelligence, data ingestion, transformation pipelines, data warehousing, semantic modeling, reporting, and dashboard visualization. Reuses the core spine (Core Tenants, Users, ApiCredentials, AuditLogs). App path: `apps/bi/`. Templates: `templates/bi/`. URL prefix: `/bi/` (`app_name="bi"`). Mounted in `config/urls.py`; app in `INSTALLED_APPS` as `apps.bi`.

## Sub-modules Overview
- **10.1 Data Integration & Ingestion**: Source connectors, batch/real-time ingestion schedules, CDC delta capture, webhook ingress, and execution run telemetry (`DataIntegrationHub`).
- **10.2 ETL/ELT & Data Pipelines**: Visual DAG pipeline designer, transformation steps (joins, aggregates, pivots, casts), version promotion, and run execution logs.
- **10.3 Data Warehouse & Lakehouse Management**: Star/snowflake schemas, facts & dimensions, storage tiers, partition pruning.
- **10.4 Semantic Layer & Metrics Store**: Reusable metrics, calculated KPIs, dimensions, business glossary, and virtual views.
- **10.5 Self-Service Data Discovery & Preparation**: Data wrangling recipes, profiling, catalog search, dataset sharing.
- **10.6 Ad-hoc Query & SQL Studio**: Interactive SQL editor, query history, permission-governed result sets, pushdown query runner.
- **10.7 Metadata & Data Catalog**: Enterprise catalog, automated schema discovery, data classification, and end-to-end lineage graph.
- **10.8 Master Data Management (MDM) Analytics**: Golden record resolution, survivorship rules, entity matching.
- **10.9 Data Quality & Governance**: Validation rules, anomaly detection, threshold alerting, quarantine workflows.
- **10.10 Real-time Streaming Analytics**: Micro-batch processing, stream windows, live telemetry feeds.
- **10.11 Operational Reporting**: Paginated tabular reports, print-ready PDFs, report schedules, bursting distributions.
- **10.12 Executive Dashboards & Data Visualization**: Interactive widgets, drag-and-drop dashboards, chart libraries, real-time KPI tiles.
- **10.13 Geospatial Analytics & Mapping**: Choropleth maps, territory heatmaps, spatial clustering.
- **10.14 Financial Analytics & Planning**: Variance analysis, budget vs. actuals, financial ratio scorecards.
- **10.15 Supply Chain & Operations Analytics**: Inventory turns, vendor delivery reliability, demand forecasts.
- **10.16 Sales & Marketing Analytics**: Pipeline velocity, CAC, LTV, conversion attribution.
- **10.17 HR & Workforce Analytics**: Headcount trends, turnover predictors, compensation distribution.
- **10.18 Embedded Analytics & White-labeling**: Multi-tenant customer portals, tokenized dashboard embeds, vanity branding.
- **10.19 Integration & API Ecosystem**: Reverse-ETL sync, external BI drivers (Snowflake, BigQuery, Tableau, Looker syndication).
- **10.20 Administration, Security & Compliance**: Row/column-level security policies, data masking, GDPR compliance exports, license quotas.

---

## App Layout & Architecture
Models, forms, views, and urls are organized into dedicated sub-module packages:

```
apps/bi/
  models/
    _base.py                                  <- TenantNumbered abstract model
    DataIntegration/                          <- Sub-module 10.1
      DataSourceConnectors.py                 <- DataSourceConnector [BDSC-]
      IngestionPipelines.py                   <- IngestionPipeline [BING-]
      CdcSyncConfigs.py                       <- CdcSyncConfig [BCDC-]
      IngestionRuns.py                        <- IngestionRun [BIJR-]
    __init__.py                               <- Re-exports all models
  forms/
    _common.py                                <- Base forms, TenantUniqueMixin, reject_foreign
    DataIntegration/                          <- Sub-module 10.1 forms
      DataSourceConnectors.py
      IngestionPipelines.py
      CdcSyncConfigs.py
      IngestionRuns.py
    __init__.py                               <- Re-exports all forms
  views/
    _common.py                                <- Shared helpers & CRUD mixins
    DataIntegration/                          <- Sub-module 10.1 views
      DataIntegrationHub.py                   <- Command Center Hub
      DataSourceConnectors.py
      IngestionPipelines.py
      CdcSyncConfigs.py
      IngestionRuns.py
    __init__.py                               <- Re-exports all views
  urls/
    DataIntegration/                          <- Sub-module 10.1 URL patterns
      DataIntegrationHub.py
      DataSourceConnectors.py
      IngestionPipelines.py
      CdcSyncConfigs.py
      IngestionRuns.py
    __init__.py                               <- Master app_name="bi", includes all entity urlconfs
  admin.py                                    <- Django Admin registrations
  management/commands/
    seed_bi.py                                <- Multi-tenant demo seeder command
  tests/                                      <- Pytest test package
```

---

## Sub-module 10.1: Data Integration & Ingestion

### Models
1. **`DataSourceConnector`** (`apps/bi/models/DataIntegration/DataSourceConnectors.py`)
   - Prefix: `BDSC-`
   - Fields: `name`, `slug`, `connector_type` (database, rest_api, webhook_push, s3_blob, ftp_sftp, file_upload), `database_type`, `host`, `port`, `database_name`, `username`, `password_encrypted`, `api_endpoint_url`, `credential` (`core.ApiCredential`), `sync_mode` (batch_pull, real_time_cdc, webhook_push, manual_file), `connection_params` (JSON), `status` (active, inactive, error, testing), `last_tested_at`, `last_test_status`, `error_message`.
2. **`IngestionPipeline`** (`apps/bi/models/DataIntegration/IngestionPipelines.py`)
   - Prefix: `BING-`
   - Fields: `name`, `slug`, `connector` (`bi.DataSourceConnector`), `target_staging_table`, `ingestion_mode` (full_refresh, incremental_append, cdc_delta, micro_batch), `schedule_cadence` (manual, every_5_min, hourly, daily, weekly, custom_cron), `cron_expression`, `watermark_column`, `watermark_value`, `watermark_type`, `batch_size`, `timeout_seconds`, `max_retries`, `alert_on_failure`, `webhook_secret`, `status` (draft, active, paused, archived), `last_run_at`, `next_run_due_at`.
3. **`CdcSyncConfig`** (`apps/bi/models/DataIntegration/CdcSyncConfigs.py`)
   - Prefix: `BCDC-`
   - Fields: `pipeline` (`bi.IngestionPipeline`), `cdc_strategy` (log_miner, postgres_wal, mysql_binlog, timestamp_watermark, hash_diff), `capture_schema`, `capture_table`, `primary_key_column`, `cdc_position_token`, `heartbeat_interval_seconds`, `include_before_image`, `tombstone_retention_days`, `is_paused`, `last_heartbeat_at`, `lag_seconds`.
4. **`IngestionRun`** (`apps/bi/models/DataIntegration/IngestionRuns.py`)
   - Prefix: `BIJR-`
   - Fields: `pipeline` (`bi.IngestionPipeline`), `trigger_type` (manual, scheduled, cdc_event, webhook, backfill), `status` (pending, queued, running, completed, partial, failed, cancelled), `started_at`, `finished_at`, `duration_seconds`, `rows_extracted`, `rows_loaded`, `rows_rejected`, `bytes_transferred`, `watermark_start`, `watermark_end`, `error_message`, `execution_log`, `retry_attempt`, `triggered_by` (`auth.User`).

### URLs & Routes
- Master Command Center: `bi:data_integration_hub` (`/bi/data-integration/`)
- Data Source Connectors:
  - `bi:connector_list` (`/bi/connectors/`)
  - `bi:connector_create` (`/bi/connectors/create/`)
  - `bi:connector_detail` (`/bi/connectors/<int:pk>/`)
  - `bi:connector_edit` (`/bi/connectors/<int:pk>/edit/`)
  - `bi:connector_delete` (`/bi/connectors/<int:pk>/delete/`)
  - `bi:connector_test_connection` (`/bi/connectors/<int:pk>/test/`)
- Ingestion Pipelines:
  - `bi:ingestion_pipeline_list` (`/bi/pipelines/`)
  - `bi:ingestion_pipeline_create` (`/bi/pipelines/create/`)
  - `bi:ingestion_pipeline_detail` (`/bi/pipelines/<int:pk>/`)
  - `bi:ingestion_pipeline_edit` (`/bi/pipelines/<int:pk>/edit/`)
  - `bi:ingestion_pipeline_delete` (`/bi/pipelines/<int:pk>/delete/`)
  - `bi:ingestion_pipeline_trigger` (`/bi/pipelines/<int:pk>/trigger/`)
- CDC Sync Configs:
  - `bi:cdc_sync_list` (`/bi/cdc/`)
  - `bi:cdc_sync_create` (`/bi/cdc/create/`)
  - `bi:cdc_sync_detail` (`/bi/cdc/<int:pk>/`)
  - `bi:cdc_sync_edit` (`/bi/cdc/<int:pk>/edit/`)
  - `bi:cdc_sync_delete` (`/bi/cdc/<int:pk>/delete/`)
  - `bi:cdc_sync_toggle` (`/bi/cdc/<int:pk>/toggle/`)
- Ingestion Runs:
  - `bi:ingestion_run_list` (`/bi/runs/`)
  - `bi:ingestion_run_detail` (`/bi/runs/<int:pk>/`)
  - `bi:ingestion_run_retry` (`/bi/runs/<int:pk>/retry/`)

### Sidebar Navigation & Live Links
In `apps/core/navigation.py`:
- `LIVE_LINKS["10.1"] = "bi:data_integration_hub"`
- `LIVE_LINKS["10.2"] = "bi:etl_pipeline_list"`

---

## Sub-module 10.2: ETL/ELT & Data Pipelines

### Models
1. **`EtlPipeline`** (`apps/bi/models/EtlPipelines/EtlPipelines.py`)
   - Prefix: `BETL-`
   - Fields: `name`, `description`, `source_ingestion_pipeline` (`bi.IngestionPipeline`), `source_staging_table`, `target_table`, `target_layer` (staging, warehouse_fact, warehouse_dim, data_mart), `trigger_type` (manual, scheduled_cron, event_on_ingest, dependency_chained), `cron_expression`, `upstream_dependencies` (JSON list), `retry_policy` (JSON dict), `sla_timeout_seconds`, `alert_on_sla_miss`, `alert_rule` (`core.AlertRule`), `status` (draft, active, paused, deprecated, error), `canvas_layout` (JSON dict), `active_version` (`bi.EtlPipelineVersion`), `last_run_at`, `next_run_due_at`, `created_by` (`auth.User`).
2. **`TransformationStep`** (`apps/bi/models/EtlPipelines/TransformationSteps.py`)
   - Prefix: `BTRN-`
   - Fields: `pipeline` (`bi.EtlPipeline`), `name`, `step_type` (join, aggregate, pivot, unpivot, cast, filter, derived_column, lookup_enrichment, deduplicate, business_rule), `sequence`, `upstream_step_ids` (JSON list), `step_config` (JSON dict), `mapping_template` (`core.MappingTemplate`), `status` (active, disabled, draft), `is_blocking`, `canvas_x`, `canvas_y`, `description`.
3. **`EtlPipelineVersion`** (`apps/bi/models/EtlPipelines/EtlPipelineVersions.py`)
   - Prefix: `BPVR-`
   - Fields: `pipeline` (`bi.EtlPipeline`), `version_number`, `environment` (development, staging, production), `status` (draft, published, archived, rolled_back), `environment_instance` (`core.EnvironmentInstance`), `dag_definition` (JSON dict), `changelog`, `rollback_source` (`self`), `promoted_by` (`auth.User`), `promoted_at`.
4. **`EtlPipelineRun`** (`apps/bi/models/EtlPipelines/EtlPipelineRuns.py`)
   - Prefix: `BEXR-`
   - Fields: `pipeline` (`bi.EtlPipeline`), `version` (`bi.EtlPipelineVersion`), `trigger_type` (manual, scheduled, event_upstream, backfill), `status` (pending, queued, running, completed, warning, failed, cancelled, timed_out), `started_at`, `ended_at`, `duration_seconds`, `records_in`, `records_transformed`, `records_out`, `records_rejected`, `bytes_processed`, `sla_missed`, `is_backfill`, `backfill_range_start`, `backfill_range_end`, `retry_count`, `step_progress` (JSON dict), `error_message`, `execution_log`.

### URLs & Routes
- ETL Pipelines:
  - `bi:etl_pipeline_list` (`/bi/etl-pipelines/`)
  - `bi:etl_pipeline_create` (`/bi/etl-pipelines/create/`)
  - `bi:etl_pipeline_detail` (`/bi/etl-pipelines/<int:pk>/`)
  - `bi:etl_pipeline_edit` (`/bi/etl-pipelines/<int:pk>/edit/`)
  - `bi:etl_pipeline_delete` (`/bi/etl-pipelines/<int:pk>/delete/`)
  - `bi:etl_pipeline_canvas` (`/bi/etl-pipelines/<int:pk>/canvas/`)
  - `bi:etl_pipeline_trigger` (`/bi/etl-pipelines/<int:pk>/trigger/`)
- Transformation Steps:
  - `bi:transformation_step_list` (`/bi/transformation-steps/`)
  - `bi:transformation_step_create` (`/bi/transformation-steps/create/`)
  - `bi:transformation_step_detail` (`/bi/transformation-steps/<int:pk>/`)
  - `bi:transformation_step_edit` (`/bi/transformation-steps/<int:pk>/edit/`)
  - `bi:transformation_step_delete` (`/bi/transformation-steps/<int:pk>/delete/`)
- Pipeline Versions:
  - `bi:etl_pipeline_version_list` (`/bi/pipeline-versions/`)
  - `bi:etl_pipeline_version_create` (`/bi/pipeline-versions/create/`)
  - `bi:etl_pipeline_version_detail` (`/bi/pipeline-versions/<int:pk>/`)
  - `bi:etl_pipeline_version_edit` (`/bi/pipeline-versions/<int:pk>/edit/`)
  - `bi:etl_pipeline_version_delete` (`/bi/pipeline-versions/<int:pk>/delete/`)
  - `bi:etl_pipeline_version_promote` (`/bi/pipeline-versions/<int:pk>/promote/`)
- Pipeline Runs:
  - `bi:etl_pipeline_run_list` (`/bi/etl-runs/`)
  - `bi:etl_pipeline_run_detail` (`/bi/etl-runs/<int:pk>/`)

### Conventions & Development Rules
- **Multi-Tenancy**: All models inherit from `TenantNumbered` (`apps/bi/models/_base.py`) with strict `tenant` (`core.Tenant`, CASCADE) isolation. Every query in views, forms, and actions must filter on `tenant=request.tenant`.
- **Security & Data Protection**:
  - Passwords and connection credentials must never be rendered in plaintext or returned in forms without proper masking (`password_encrypted`).
  - Webhook signing secrets (`webhook_secret`) are write-once or auto-generated; never exposed in edit forms.
  - SSRF protection: Target URLs and API endpoints are validated against private/loopback IP address ranges via `is_safe_url`.
- **Audit Logging**: Any destructive action or state change (create, edit, delete, trigger run, test connection, cdc toggle) must record an immutable audit log entry via `write_audit_log(request.user, obj, action, tenant=request.tenant)`.
- **Testing**: Tests run using in-memory SQLite (`config.settings_test`). Test functions must follow `test_dataintegration_*` naming convention with zero hardcoded cross-tenant leaks.
