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
- `LIVE_LINKS["10.3"] = "bi:warehouse_overview"`

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

---

## Sub-module 10.3: Data Warehouse & Storage

### Models
1. **`DataMart`** (`apps/bi/models/DataWarehouse/DataMarts.py`)
   - Prefix: `BDMT-`
   - Fields: `name`, `code` (unique per tenant), `subject_area` (finance, sales, procurement, inventory, hrm, crm, executive, operations), `access_tier` (public_internal, department, restricted, confidential, tenant), `certification_status` (draft, under_review, verified, certified, deprecated), `refresh_schedule_cadence` (realtime, hourly, daily, weekly, monthly, manual), `org_unit` (`core.OrgUnit`), `owner` (`auth.User`), `steward` (`auth.User`), `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, code)` and `(tenant, number)`, composite index on `(tenant, name)`.
2. **`LakehouseZone`** (`apps/bi/models/DataWarehouse/LakehouseZones.py`)
   - Prefix: `BLHZ-`
   - Fields: `name`, `code` (unique per tenant), `zone_type` (raw, bronze, silver, gold, sandbox), `storage_backend` (internal_db, s3_compatible, azure_blob, gcs, local_filesystem), `base_uri_path`, `default_format` (relational_table, delta_lake, apache_iceberg, parquet_raw), `managed_by_platform`, `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, code)` and `(tenant, number)`, composite index on `(tenant, zone_type)`.
3. **`WarehouseStoragePolicy`** (`apps/bi/models/DataWarehouse/WarehouseStoragePolicies.py`)
   - Prefix: `BWSP-`
   - Fields: `name`, `partition_strategy` (none, range_time, hash_bucket, list_categorical), `partition_granularity` (none, hourly, daily, weekly, monthly, yearly), `compression_codec` (none, gzip, snappy, zstd, lz4), `vacuum_cadence` (disabled, daily, weekly, monthly), `time_travel_days` (0-90), `hot_tier_retention_days`, `warm_tier_retention_days`, `cold_tier_retention_days`, `enable_zorder`, `enable_bloom_filters`, `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, number)`, composite index on `(tenant, name)`.
4. **`WarehouseTable`** (`apps/bi/models/DataWarehouse/WarehouseTables.py`)
   - Prefix: `BDWT-`
   - Fields: `lakehouse_zone` (`bi.LakehouseZone`, `PROTECT`), `storage_policy` (`bi.WarehouseStoragePolicy`, `SET_NULL`), `data_mart` (`bi.DataMart`, `SET_NULL`), `name`, `table_name` (SQL identifier), `table_type` (fact, dimension, aggregate, bridge, staging, snapshot), `schema_type` (star, snowflake, galaxy, flat_denormalized), `grain` (transaction, periodic_snapshot, accumulating_snapshot, line_item, summary), `primary_key_column`, `partition_key`, `cluster_keys`, `schema_definition` (JSON array of column objects), `row_count`, `compressed_bytes`, `compression_ratio`, `is_conformed`, `last_analyzed_at`, `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, table_name)` and `(tenant, number)`, composite indexes on `(tenant, storage_policy)`, `(tenant, -created_at)`, `(tenant, lakehouse_zone)`, `(tenant, data_mart)`.
   - Methods: `generate_ddl_sql()` supports ANSI DDL generation with `CREATE TABLE IF NOT EXISTS`, schema column mapping, primary key clauses, and `RANGE` / `HASH` / `LIST` partitioning.

### URLs & Routes
- Overview:
  - `bi:warehouse_overview` (`/bi/warehouse/`)
- Data Marts:
  - `bi:data_mart_list` (`/bi/warehouse/marts/`)
  - `bi:data_mart_create` (`/bi/warehouse/marts/create/`)
  - `bi:data_mart_detail` (`/bi/warehouse/marts/<int:pk>/`)
  - `bi:data_mart_edit` (`/bi/warehouse/marts/<int:pk>/edit/`)
  - `bi:data_mart_delete` (`/bi/warehouse/marts/<int:pk>/delete/`)
- Lakehouse Zones:
  - `bi:lakehouse_zone_list` (`/bi/warehouse/zones/`)
  - `bi:lakehouse_zone_create` (`/bi/warehouse/zones/create/`)
  - `bi:lakehouse_zone_detail` (`/bi/warehouse/zones/<int:pk>/`)
  - `bi:lakehouse_zone_edit` (`/bi/warehouse/zones/<int:pk>/edit/`)
  - `bi:lakehouse_zone_delete` (`/bi/warehouse/zones/<int:pk>/delete/`)
- Warehouse Storage Policies:
  - `bi:warehouse_storage_policy_list` (`/bi/warehouse/policies/`)
  - `bi:warehouse_storage_policy_create` (`/bi/warehouse/policies/create/`)
  - `bi:warehouse_storage_policy_detail` (`/bi/warehouse/policies/<int:pk>/`)
  - `bi:warehouse_storage_policy_edit` (`/bi/warehouse/policies/<int:pk>/edit/`)
  - `bi:warehouse_storage_policy_delete` (`/bi/warehouse/policies/<int:pk>/delete/`)
- Warehouse Tables:
  - `bi:warehouse_table_list` (`/bi/warehouse/tables/`)
  - `bi:warehouse_table_create` (`/bi/warehouse/tables/create/`)
  - `bi:warehouse_table_detail` (`/bi/warehouse/tables/<int:pk>/`)
  - `bi:warehouse_table_edit` (`/bi/warehouse/tables/<int:pk>/edit/`)
  - `bi:warehouse_table_delete` (`/bi/warehouse/tables/<int:pk>/delete/`)
  - `bi:warehouse_table_ddl_preview` (`/bi/warehouse/tables/<int:pk>/ddl/`)
  - `bi:warehouse_table_analyze` (`/bi/warehouse/tables/<int:pk>/analyze/`)

### Templates & Design Patterns
- Templates reside in `templates/bi/data_warehouse/`:
  - `warehouse_overview.html` (Stat cards, storage breakdown, recent tables table, quick links)
  - `data_mart/` (`list.html`, `detail.html`, `form.html`)
  - `lakehouse_zone/` (`list.html`, `detail.html`, `form.html`)
  - `warehouse_storage_policy/` (`list.html`, `detail.html`, `form.html`)
  - `warehouse_table/` (`list.html`, `detail.html`, `form.html`, `ddl_preview.html`)
- Design System: Colour-named badges only (`.badge-info`, `.badge-slate`, `.badge-green`, `.badge-amber`, `.badge-red`). Empty state typography uses semantic `<h3>`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant data for:
  - 4 Lakehouse Zones (Bronze, Silver, Gold, Sandbox)
  - 3 Warehouse Storage Policies (Hot Daily Snappy, Balanced Weekly Zstd, Cold Archive Gzip)
  - 4 Data Marts (Executive, Sales & Revenue, Finance & GL, Supply Chain)
  - 6 Warehouse Tables (`fact_daily_revenue`, `fact_sales_order_lines`, `fact_gl_journal_entries`, `dim_customer_master`, `dim_product_catalog`, `dim_fiscal_calendar`) with populated JSON column schemas.
- 100% idempotent; guarded against duplicate executions.

### Key Conventions
- **JSON Column Deferral**: Queries for tables in `warehouse_overview` and `warehouse_table_list` use `.defer("schema_definition")` to conserve RAM and reduce serialization load.
- **Foreign Key Permissiveness on Edit**: Model forms permit currently bound inactive FKs on edit via `Q(is_active=True) | Q(pk=self.instance.<fk_id>)`.
- **SQL Identifier Validation**: `table_name` and `primary_key_column` are sanitized with regex `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$`.

