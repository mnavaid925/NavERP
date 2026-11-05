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
- **10.5 Data Quality & Cleansing**: Automated profiling, declarative validation rules, steward exception remediation queues, executive Data Trust Index (DTI) scorecards.
- **10.6 Master Data Management (MDM)**: Golden master records, source crosswalks, survivorship rules, multi-domain hierarchies, and reference data management (RDM).
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

---

## Sub-module 10.4: Data Modeling & Semantic Layer

### Models
1. **`SemanticModel`** (`apps/bi/models/SemanticLayer/SemanticModels.py`)
   - Prefix: `BSMD-` (`BSMD-00001`)
   - Fields: `name`, `code` (slug), `model_type` (`fact`, `dimension`, `bridge`, `virtual_view`, `reusable_dataset`), `warehouse_table` (`bi.WarehouseTable`, `SET_NULL`), `data_mart` (`bi.DataMart`, `SET_NULL`), `primary_key_column`, `natural_key_columns`, `grain_description`, `is_conformed_dimension`, `scd_type` (`type_0`, `type_1`, `type_2`, `type_3`), `is_virtual_view`, `sql_definition`, `access_tier` (`public`, `department`, `restricted`), `certification_status` (`draft`, `in_review`, `certified`, `deprecated`), `certified_by` (`auth.User`, `SET_NULL`), `certified_at`, `certification_notes`, `source_fingerprint`, `last_introspected_at`, `owner` (`auth.User`, `SET_NULL`), `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, code)` and `(tenant, number)`. Composite indexes on `(tenant, model_type)`, `(tenant, certification_status)`, `(tenant, warehouse_table)`, `(tenant, is_active)`, `(tenant, -created_at)`, `(tenant, data_mart)`.

2. **`BusinessGlossaryTerm`** (`apps/bi/models/SemanticLayer/BusinessGlossaryTerms.py`)
   - Prefix: `BGLO-` (`BGLO-00001`)
   - Fields: `name`, `code` (slug), `domain_category` (`finance`, `sales`, `marketing`, `hr`, `supply_chain`, `operations`, `general`), `short_definition`, `full_definition`, `calculation_rule`, `synonyms`, `steward` (`auth.User`, `SET_NULL`), `org_unit` (`core.OrgUnit`, `SET_NULL`), `certification_status` (`draft`, `in_review`, `certified`, `deprecated`), `certified_by` (`auth.User`, `SET_NULL`), `certified_at`, `certification_notes`, `related_terms` (symmetrical M2M to `self`), `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, code)` and `(tenant, number)`. Composite indexes on `(tenant, domain_category)`, `(tenant, domain_category, name)`, `(tenant, certification_status)`, `(tenant, is_active)`.

3. **`CalculatedMeasure`** (`apps/bi/models/SemanticLayer/CalculatedMeasures.py`)
   - Prefix: `BCMS-` (`BCMS-00001`)
   - Fields: `semantic_model` (`bi.SemanticModel`, `CASCADE`), `glossary_term` (`bi.BusinessGlossaryTerm`, `SET_NULL`), `name`, `code` (slug), `aggregation_type` (`sum`, `avg`, `count`, `count_distinct`, `min`, `max`, `formula`), `source_column`, `formula_expression`, `filter_expression`, `time_intelligence` (`none`, `yoy_growth`, `qtd`, `ytd`, `rolling_30d`, `prior_period`), `format_string` (`currency`, `percentage`, `integer`, `decimal`, `raw`), `display_units` (`auto`, `none`, `thousands`, `millions`, `billions`), `target_value`, `warning_threshold`, `critical_threshold`, `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, semantic_model, code)` and `(tenant, number)`. Composite indexes on `(tenant, aggregation_type)`, `(tenant, time_intelligence)`, `(tenant, glossary_term)`, `(tenant, is_active)`.

4. **`DrillHierarchy`** (`apps/bi/models/SemanticLayer/DrillHierarchies.py`)
   - Prefix: `BDHI-` (`BDHI-00001`)
   - Fields: `semantic_model` (`bi.SemanticModel`, `CASCADE`), `name`, `code` (slug), `hierarchy_type` (`time`, `geography`, `organizational`, `product`, `custom`), `levels_json` (JSON list of level dicts `[{'level': 1, 'name': 'Year', 'column': 'fiscal_year'}, ...]`), `primary_drill_path`, `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, semantic_model, code)` and `(tenant, number)`. Composite indexes on `(tenant, hierarchy_type)`, `(tenant, is_active)`.

### URLs & Routes
- Master Semantic Command Center: `bi:semantic_overview` (`/bi/semantic/`)
- Semantic Models:
  - `bi:semantic_model_list` (`/bi/semantic/models/`)
  - `bi:semantic_model_create` (`/bi/semantic/models/create/`)
  - `bi:semantic_model_detail` (`/bi/semantic/models/<int:pk>/`)
  - `bi:semantic_model_edit` (`/bi/semantic/models/<int:pk>/edit/`)
  - `bi:semantic_model_delete` (`/bi/semantic/models/<int:pk>/delete/`)
  - `bi:semantic_model_certify` (`/bi/semantic/models/<int:pk>/certify/`)
  - `bi:semantic_model_introspect` (`/bi/semantic/models/<int:pk>/introspect/`)
- Business Glossary Terms:
  - `bi:business_glossary_term_list` (`/bi/semantic/glossary/`)
  - `bi:business_glossary_term_create` (`/bi/semantic/glossary/create/`)
  - `bi:business_glossary_term_detail` (`/bi/semantic/glossary/<int:pk>/`)
  - `bi:business_glossary_term_edit` (`/bi/semantic/glossary/<int:pk>/edit/`)
  - `bi:business_glossary_term_delete` (`/bi/semantic/glossary/<int:pk>/delete/`)
  - `bi:business_glossary_term_certify` (`/bi/semantic/glossary/<int:pk>/certify/`)
- Calculated Measures:
  - `bi:calculated_measure_list` (`/bi/semantic/measures/`)
  - `bi:calculated_measure_create` (`/bi/semantic/measures/create/`)
  - `bi:calculated_measure_detail` (`/bi/semantic/measures/<int:pk>/`)
  - `bi:calculated_measure_edit` (`/bi/semantic/measures/<int:pk>/edit/`)
  - `bi:calculated_measure_delete` (`/bi/semantic/measures/<int:pk>/delete/`)
- Drill Hierarchies:
  - `bi:drill_hierarchy_list` (`/bi/semantic/hierarchies/`)
  - `bi:drill_hierarchy_create` (`/bi/semantic/hierarchies/create/`)
  - `bi:drill_hierarchy_detail` (`/bi/semantic/hierarchies/<int:pk>/`)
  - `bi:drill_hierarchy_edit` (`/bi/semantic/hierarchies/<int:pk>/edit/`)
  - `bi:drill_hierarchy_delete` (`/bi/semantic/hierarchies/<int:pk>/delete/`)

### Templates & Design Patterns
- Templates reside in `templates/bi/semantic_layer/`:
  - `semantic_overview.html` (Command center with KPI stat cards, distribution charts, recent certified models/terms)
  - `semantic_model/` (`list.html`, `detail.html`, `form.html`)
  - `business_glossary_term/` (`list.html`, `detail.html`, `form.html`)
  - `calculated_measure/` (`list.html`, `detail.html`, `form.html`)
  - `drill_hierarchy/` (`list.html`, `detail.html`, `form.html`)
- Design System: Colour-named badges only (`.badge-info`, `.badge-slate`, `.badge-green`, `.badge-amber`, `.badge-red`). Icon buttons include accessible `aria-label` attributes.
- Detail pages include "Back to List" navigation in `.page-actions`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant demo data for:
  - 4 Semantic Models (Acme Sales Orders Mart Model, Acme Financial Performance Model, Executive ARR & Retention View, Globex Orders Mart Model)
  - 4 Business Glossary Terms (Net Recurring Revenue, Customer Acquisition Cost, Days Sales Outstanding, Globex Gross Churn)
  - 4 Calculated Measures (Gross Merchandise Value, Gross Margin %, Rolling 30-Day Moving Revenue, Globex Net Sales)
  - 3 Drill Hierarchies (Fiscal Calendar Drill, Regional Territory Drill, Globex Customer Geography Drill)
- 100% idempotent.

### Key Conventions
- **Dedicated Certification Workflow**: `certification_status` and `certification_notes` are excluded from general CRUD forms and managed strictly via `@require_POST` certify endpoints that enforce user stamping (`certified_by`, `certified_at`) and audit logging.
- **Virtual View SQL Requirement**: `SemanticModelForm.clean()` enforces non-empty `sql_definition` when `is_virtual_view` is true.
- **Audit Logging Protocol**: All mutating operations invoke `write_audit_log(request.user, instance, "<action>", tenant=request.tenant)`. Delete views log before calling `instance.delete()`.
- **Queryset Pre-evaluation**: Reverse relation counts in detail headers evaluate via `list()` in view and use `|length` in templates to eliminate duplicate counting queries.

---

## Sub-module 10.5: Data Quality & Cleansing

### Models
1. **`DataQualityProfile`** (`apps/bi/models/DataQuality/DataQualityProfiles.py`)
   - Prefix: `BDQP-` (`BDQP-00001`)
   - Fields: `name`, `target_type` (`warehouse_table`, `semantic_model`), `warehouse_table` (`bi.WarehouseTable`, `CASCADE`), `semantic_model` (`bi.SemanticModel`, `CASCADE`), `status` (`pending`, `running`, `completed`, `failed`), `total_row_count`, `total_column_count`, `completeness_score`, `validity_score`, `uniqueness_score`, `consistency_score`, `timeliness_score`, `column_profiles_json`, `profiled_by` (`auth.User`, `SET_NULL`), `profiled_at`, `duration_seconds`, `error_message`, `notes`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, number)`. Composite indexes on `(tenant, status)`, `(tenant, target_type)`, `(tenant, warehouse_table)`, `(tenant, semantic_model)`, `(tenant, -created_at)`.

2. **`DataQualityRule`** (`apps/bi/models/DataQuality/DataQualityRules.py`)
   - Prefix: `BDQR-` (`BDQR-00001`)
   - Fields: `name`, `code` (slug), `rule_category` (`validation`, `anomaly_detection`, `uniqueness`, `standardization`, `custom_sql`), `dimension` (`completeness`, `accuracy`, `consistency`, `timeliness`, `uniqueness`, `validity`), `target_type` (`warehouse_table`, `semantic_model`), `warehouse_table` (`bi.WarehouseTable`, `CASCADE`), `semantic_model` (`bi.SemanticModel`, `CASCADE`), `target_column`, `rule_type` (`not_null`, `unique`, `range_between`, `regex_pattern`, `set_membership`, `referential_integrity`, `date_freshness`, `string_standardization`, `duplicate_cluster`, `custom_sql`), `parameters_json`, `severity` (`info`, `warning`, `critical`, `fatal`), `failure_tolerance_pct`, `last_run_at`, `last_status` (`passed`, `warning`, `failed`, `error`), `pass_rate_pct`, `records_evaluated`, `records_passed`, `records_failed`, `steward` (`auth.User`, `SET_NULL`), `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, code)` and `(tenant, number)`. Composite indexes on `(tenant, dimension)`, `(tenant, rule_type)`, `(tenant, severity)`, `(tenant, last_status)`, `(tenant, warehouse_table)`, `(tenant, semantic_model)`, `(tenant, -last_run_at)`.

3. **`DataQualityException`** (`apps/bi/models/DataQuality/DataQualityExceptions.py`)
   - Prefix: `BDQE-` (`BDQE-00001`)
   - Fields: `profile` (`bi.DataQualityProfile`, `SET_NULL`), `rule` (`bi.DataQualityRule`, `SET_NULL`), `target_type` (`warehouse_table`, `semantic_model`), `warehouse_table` (`bi.WarehouseTable`, `SET_NULL`), `semantic_model` (`bi.SemanticModel`, `SET_NULL`), `target_column`, `record_identifier`, `exception_type` (`null_value`, `duplicate_key`, `range_violation`, `pattern_mismatch`, `fk_orphan`, `freshness_lag`, `format_error`, `schema_drift`, `fuzzy_duplicate`), `invalid_value`, `expected_condition`, `severity` (`info`, `warning`, `critical`, `fatal`), `status` (`open`, `investigating`, `remediated`, `suppressed_false_positive`, `accepted_risk`, `rejected`), `remediation_action` (`none`, `investigate`, `enrich_data`, `correct_value`, `suppress`, `delete_record`, `quarantine`), `proposed_value`, `remediated_value`, `resolution_notes`, `assigned_steward` (`auth.User`, `SET_NULL`), `resolved_by` (`auth.User`, `SET_NULL`), `resolved_at`.
   - Constraints & Indexes: Unique constraint on `(tenant, number)`. Composite indexes on `(tenant, status)`, `(tenant, severity)`, `(tenant, exception_type)`, `(tenant, profile)`, `(tenant, assigned_steward)`, `(tenant, warehouse_table)`, `(tenant, semantic_model)`, `(tenant, -created_at)`.

4. **`DataQualityScorecard`** (`apps/bi/models/DataQuality/DataQualityScorecards.py`)
   - Prefix: `BDQS-` (`BDQS-00001`)
   - Fields: `name`, `code` (slug), `scope_type` (`tenant_wide`, `warehouse_table`, `semantic_model`, `data_mart`, `department`), `warehouse_table` (`bi.WarehouseTable`, `SET_NULL`), `semantic_model` (`bi.SemanticModel`, `SET_NULL`), `data_mart` (`bi.DataMart`, `SET_NULL`), `org_unit` (`core.OrgUnit`, `SET_NULL`), `evaluation_period` (`real_time`, `daily`, `weekly`, `monthly`, `quarterly`), `overall_quality_score`, `target_sla_pct`, `grade` (`A`, `B`, `C`, `D`, `F`), `health_status` (`healthy`, `needs_attention`, `critical`, `failing`), `meets_sla`, `completeness_score`, `accuracy_score`, `consistency_score`, `timeliness_score`, `uniqueness_score`, `validity_score`, `total_rules_evaluated`, `passed_rules_count`, `failed_rules_count`, `open_exceptions_count`, `critical_exceptions_count`, `last_calculated_at`, `steward` (`auth.User`, `SET_NULL`), `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, code)` and `(tenant, number)`. Composite indexes on `(tenant, scope_type)`, `(tenant, grade)`, `(tenant, health_status)`, `(tenant, meets_sla)`, `(tenant, -created_at)`.

### URLs & Routes
- Master Quality Overview Dashboard: `bi:quality_overview` (`/bi/data-quality/`)
- Data Quality Profiles:
  - `bi:data_quality_profile_list` (`/bi/data-quality/profiles/`)
  - `bi:data_quality_profile_create` (`/bi/data-quality/profiles/create/`)
  - `bi:data_quality_profile_detail` (`/bi/data-quality/profiles/<int:pk>/`)
  - `bi:data_quality_profile_edit` (`/bi/data-quality/profiles/<int:pk>/edit/`)
  - `bi:data_quality_profile_delete` (`/bi/data-quality/profiles/<int:pk>/delete/`)
  - `bi:data_quality_profile_run` (`/bi/data-quality/profiles/<int:pk>/run/`)
- Data Quality Rules:
  - `bi:data_quality_rule_list` (`/bi/data-quality/rules/`)
  - `bi:data_quality_rule_create` (`/bi/data-quality/rules/create/`)
  - `bi:data_quality_rule_detail` (`/bi/data-quality/rules/<int:pk>/`)
  - `bi:data_quality_rule_edit` (`/bi/data-quality/rules/<int:pk>/edit/`)
  - `bi:data_quality_rule_delete` (`/bi/data-quality/rules/<int:pk>/delete/`)
  - `bi:data_quality_rule_run` (`/bi/data-quality/rules/<int:pk>/run/`)
- Data Quality Exceptions:
  - `bi:data_quality_exception_list` (`/bi/data-quality/exceptions/`)
  - `bi:data_quality_exception_create` (`/bi/data-quality/exceptions/create/`)
  - `bi:data_quality_exception_detail` (`/bi/data-quality/exceptions/<int:pk>/`)
  - `bi:data_quality_exception_edit` (`/bi/data-quality/exceptions/<int:pk>/edit/`)
  - `bi:data_quality_exception_delete` (`/bi/data-quality/exceptions/<int:pk>/delete/`)
  - `bi:data_quality_exception_remediate` (`/bi/data-quality/exceptions/<int:pk>/remediate/`)
- Data Quality Scorecards:
  - `bi:data_quality_scorecard_list` (`/bi/data-quality/scorecards/`)
  - `bi:data_quality_scorecard_create` (`/bi/data-quality/scorecards/create/`)
  - `bi:data_quality_scorecard_detail` (`/bi/data-quality/scorecards/<int:pk>/`)
  - `bi:data_quality_scorecard_edit` (`/bi/data-quality/scorecards/<int:pk>/edit/`)
  - `bi:data_quality_scorecard_delete` (`/bi/data-quality/scorecards/<int:pk>/delete/`)
  - `bi:data_quality_scorecard_recalculate` (`/bi/data-quality/scorecards/<int:pk>/recalculate/`)

### Templates & Design Patterns
- Templates reside in `templates/bi/data_quality/`:
  - `quality_overview.html` (Enterprise Data Trust Command Center with 6 ISO dimension gauges, rules requiring attention, exception queue, executive scorecards, recent profiling)
  - `data_quality_profile/` (`list.html`, `detail.html`, `form.html`)
  - `data_quality_rule/` (`list.html`, `detail.html`, `form.html`)
  - `data_quality_exception/` (`list.html`, `detail.html`, `form.html` with interactive steward remediation workbench)
  - `data_quality_scorecard/` (`list.html`, `detail.html`, `form.html` with visual dimension SLA radar)
- Design System: Colour-named badges only (`.badge-info`, `.badge-slate`, `.badge-green`, `.badge-amber`, `.badge-red`). Icon action buttons include accessible `title` and `aria-label` attributes.
- Detail pages include "Back to List" navigation in `.page-actions`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant demo data for Sub-module 10.5:
  - 4 Profiles (Acme Invoices Fact Profiling, Acme Customers Conformed Profiling, Acme Sales Model Profile, Globex Orders Fact Profiling)
  - 6 Rules (Invoice Amount Positive Check, Customer Email Format Check, Sales Order Reference Integrity, Order Line Quantity Positive, Delivery Date Timeliness SLA, Globex Order Total Positive)
  - 5 Exceptions (Negative invoice amount, malformed customer email, orphan invoice customer FK, stale unfulfilled shipment, Globex negative order total)
  - 4 Scorecards (Enterprise Data Trust Index, Sales & Distribution DTI, Customer 360 Master Trust, Globex Executive Operations Trust)
- 100% idempotent; `--flush` clears Sub-module 10.5 records in reverse dependency order without integrity errors.

### Key Conventions
- **ISO/DAMA 6-Dimension Model**: Profiling and scorecards compute scores across Completeness, Accuracy, Consistency, Timeliness, Uniqueness, and Validity.
- **Audit Logging Protocol**: Every mutating action invokes `write_audit_log(request.user, instance, "<action>", tenant=request.tenant)`. Delete views log before calling `instance.delete()`.
- **Atomic Tenant Numbering**: Automatic generation of `BDQP-#####`, `BDQR-#####`, `BDQE-#####`, `BDQS-#####` using `TenantNumbered`.
- **Sidebar Wiring**: Live links mapped under `apps/core/navigation.py` via `LIVE_LINKS["10.5"]`.

---

## Sub-module 10.6: Master Data Management (MDM)

### Models
1. **`MdmGoldenRecord`** (`apps/bi/models/MasterData/MdmGoldenRecords.py`)
   - Prefix: `BMGR-` (`BMGR-00001`)
   - Purpose: Authoritative single source of truth across core domains with confidence scoring, trust tiers, and source lineage.
   - Fields: `name`, `code` (slug), `domain` (`customer`, `vendor`, `product`, `asset`, `employee`, `location`, `general_ledger`), `status` (`draft`, `pending_review`, `approved`, `merged`, `in_dispute`, `archived`), `trust_tier` (`bronze`, `silver`, `gold`, `platinum`), `confidence_score` (Decimal 0.00-100.00), `party` (`core.Party`), `party_role` (`core.PartyRole`), `item` (`scm.Item`), `asset` (`scm.Asset`), `warehouse_table` (`bi.WarehouseTable`), `primary_tax_identifier`, `primary_email`, `primary_phone`, `primary_address`, `source_record_count`, `source_crosswalks_json` (list of feeder identifiers), `golden_attributes_json` (consolidated authoritative payload), `merged_into_record` (`MdmGoldenRecord`), `merged_at`, `stewardship_notes`, `assigned_steward` (`auth.User`), `reviewed_by` (`auth.User`), `reviewed_at`.
   - Constraints & Indexes: Unique constraint on `(tenant, domain, code)` and `(tenant, number)`. Composite indexes on `(tenant, domain)`, `(tenant, status)`, `(tenant, trust_tier)`, `(tenant, -created_at)`.

2. **`MdmSurvivorshipRule`** (`apps/bi/models/MasterData/MdmSurvivorshipRules.py`)
   - Prefix: `BMSR-` (`BMSR-00001`)
   - Purpose: Deterministic precedence matrices and algorithms governing attribute consolidation across feeder systems.
   - Fields: `name`, `code` (slug), `domain` (`customer`, `vendor`, `product`, `asset`, `employee`, `location`, `general_ledger`), `target_attribute_name`, `survivorship_strategy` (`most_recent`, `source_priority`, `highest_frequency`, `longest_string`, `manual_curation`), `source_priority_list_json` (ordered list of feeder systems), `match_algorithm` (`exact`, `fuzzy_levenshtein`, `fuzzy_jaro_winkler`, `token_set_ratio`, `soundex`, `rule_heuristic`), `match_threshold_pct` (Decimal 0.00-100.00), `auto_merge_threshold_pct` (Decimal 0.00-100.00, must be >= `match_threshold_pct`), `description`, `is_active`, `steward` (`auth.User`).
   - Constraints & Indexes: Unique constraint on `(tenant, code)` and `(tenant, number)`. Composite indexes on `(tenant, domain)`, `(tenant, survivorship_strategy)`, `(tenant, match_algorithm)`, `(tenant, is_active)`.

3. **`MdmHierarchyNode`** (`apps/bi/models/MasterData/MdmHierarchyNodes.py`)
   - Prefix: `BMHR-` (`BMHR-00001`)
   - Purpose: Multi-domain recursive trees and materialized path graphs for corporate holding structures, product taxonomies, and reporting rollups.
   - Fields: `name`, `code` (slug), `hierarchy_type` (`corporate_legal`, `product_taxonomy`, `sales_territory`, `cost_center`, `asset_category`, `org_reporting`), `relationship_kind` (`holding_company`, `subsidiary`, `division`, `business_unit`, `product_line`, `category`, `sub_category`, `territory_region`, `territory_country`), `parent` (`MdmHierarchyNode`), `golden_record` (`bi.MdmGoldenRecord`), `party` (`core.Party`), `org_unit` (`core.OrgUnit`), `item_category` (`scm.ItemCategory`), `level` (root=0, child=parent.level+1), `path` (materialized path e.g. `/{parent.pk}/{child.pk}/`), `sort_order`, `description`, `is_active`.
   - Constraints & Indexes: Unique constraint on `(tenant, hierarchy_type, code)` and `(tenant, number)`. Composite indexes on `(tenant, hierarchy_type)`, `(tenant, level)`, `(tenant, hierarchy_type, level)`, `(tenant, parent)`.

4. **`MdmReferenceCode`** (`apps/bi/models/MasterData/MdmReferenceCodes.py`)
   - Prefix: `BMRD-` (`BMRD-00001`)
   - Purpose: Enterprise reference data management (RDM) crosswalks, standardizing internal and partner code sets to ISO/ANSI canonical taxonomies.
   - Fields: `code_set` (`ISO-4217-CURRENCY`, `ISO-3166-COUNTRY`, `UN-LOCODE-PORT`, `INCOTERMS-2020`, `NAICS-INDUSTRY`, `UNSPSC-COMMODITY`, `INTERNAL-PAYMENT-TERMS`, `CUSTOM`), `source_system`, `source_code`, `canonical_code`, `canonical_name`, `status` (`active`, `deprecated`, `superseded`, `draft`), `effective_from`, `effective_to`, `superseded_by` (`MdmReferenceCode`), `attributes_json`, `description`.
   - Constraints & Indexes: Unique constraint on `(tenant, code_set, canonical_code, source_system, source_code)` and `(tenant, number)`. Composite indexes on `(tenant, code_set)`, `(tenant, source_system)`, `(tenant, status)`, `(tenant, canonical_code)`.

### URLs & Routes
- Master MDM Command Center: `bi:mdm_overview` (`/bi/mdm/overview/`)
- Golden Records:
  - `bi:mdm_golden_record_list` (`/bi/mdm/golden-records/`)
  - `bi:mdm_golden_record_create` (`/bi/mdm/golden-records/create/`)
  - `bi:mdm_golden_record_detail` (`/bi/mdm/golden-records/<int:pk>/`)
  - `bi:mdm_golden_record_edit` (`/bi/mdm/golden-records/<int:pk>/edit/`)
  - `bi:mdm_golden_record_delete` (`/bi/mdm/golden-records/<int:pk>/delete/`)
  - `bi:mdm_golden_record_merge` (`/bi/mdm/golden-records/<int:pk>/merge/`)
  - `bi:mdm_golden_record_unmerge` (`/bi/mdm/golden-records/<int:pk>/unmerge/`)
  - `bi:mdm_golden_record_approve` (`/bi/mdm/golden-records/<int:pk>/approve/`)
- Survivorship Rules:
  - `bi:mdm_survivorship_rule_list` (`/bi/mdm/survivorship-rules/`)
  - `bi:mdm_survivorship_rule_create` (`/bi/mdm/survivorship-rules/create/`)
  - `bi:mdm_survivorship_rule_detail` (`/bi/mdm/survivorship-rules/<int:pk>/`)
  - `bi:mdm_survivorship_rule_edit` (`/bi/mdm/survivorship-rules/<int:pk>/edit/`)
  - `bi:mdm_survivorship_rule_delete` (`/bi/mdm/survivorship-rules/<int:pk>/delete/`)
- Hierarchy Nodes:
  - `bi:mdm_hierarchy_node_list` (`/bi/mdm/hierarchy-nodes/`)
  - `bi:mdm_hierarchy_node_create` (`/bi/mdm/hierarchy-nodes/create/`)
  - `bi:mdm_hierarchy_node_detail` (`/bi/mdm/hierarchy-nodes/<int:pk>/`)
  - `bi:mdm_hierarchy_node_edit` (`/bi/mdm/hierarchy-nodes/<int:pk>/edit/`)
  - `bi:mdm_hierarchy_node_delete` (`/bi/mdm/hierarchy-nodes/<int:pk>/delete/`)
- Reference Codes:
  - `bi:mdm_reference_code_list` (`/bi/mdm/reference-codes/`)
  - `bi:mdm_reference_code_create` (`/bi/mdm/reference-codes/create/`)
  - `bi:mdm_reference_code_detail` (`/bi/mdm/reference-codes/<int:pk>/`)
  - `bi:mdm_reference_code_edit` (`/bi/mdm/reference-codes/<int:pk>/edit/`)
  - `bi:mdm_reference_code_delete` (`/bi/mdm/reference-codes/<int:pk>/delete/`)

### Templates & Design Patterns
- Templates reside in `templates/bi/master_data/`:
  - `mdm_overview.html` (Master Data Command Center with domain KPI breakdown, recent golden records, active survivorship policies, and code sets)
  - `golden_record/` (`list.html`, `detail.html` with crosswalks provenance table and merge workbench, `form.html`)
  - `survivorship_rule/` (`list.html`, `detail.html` with visual precedence matrix, `form.html`)
  - `hierarchy_node/` (`list.html` with tree level indentation, `detail.html` with ancestor path breadcrumbs and children list, `form.html`)
  - `reference_code/` (`list.html`, `detail.html` with translation crosswalks and superseding history, `form.html`)
- Design System: Colour-named badges (`.badge-green`, `.badge-info`, `.badge-amber`, `.badge-red`, `.badge-slate`, `.badge-muted`). Accessible icon buttons with `title` and `aria-label`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Master Data demo records:
  - Golden Records (Acme Global Holding, Acme Electronics US, Acme Industrial Supply, Acme Duplicate Staging, Globex Master Entity)
  - Survivorship Rules (Customer Master Rule, Vendor Master Rule, Product Catalog Rule, Asset Registry Rule)
  - Hierarchy Nodes (Acme Global Enterprise, North America Holding, US Commercial Ops, US Defense Systems)
  - Reference Codes (ISO Currency USD/EUR/GBP, ISO Country US/CA/DE, Incoterms FOB/CIF/DDP)
- 100% idempotent; `--flush` cleanly deletes records in reverse dependency order.

### Key Conventions
- **Merge/Unmerge State Machine**: Merging absorbs secondary records, consolidates feeder crosswalks, increments source counts, and flags duplicates as `merged`. Unmerging restores records to `pending_review` for steward certification. Master deletion is blocked while absorbed duplicates exist.
- **Tree Homogeneity & Loop Prevention**: Hierarchy nodes enforce matching `hierarchy_type` between parent and child, prevent circular hierarchies, and dynamically cascade materialized paths (`/{pk}/...`) on re-parenting.
- **Auto-Numbering**: Automatic sequence generation for `BMGR-#####`, `BMSR-#####`, `BMHR-#####`, and `BMRD-#####`.
- **Sidebar Wiring**: Live links registered in `apps/core/navigation.py` under `LIVE_LINKS["10.6"]`.



---

## Sub-module 10.7: Data Catalog, Lineage & Governance

### Overview
Enterprise Data Catalog, searchable metadata repository, automated dataset discovery, column- and table-level lineage graph, data governance compliance policies (GDPR, CCPA, SOX, HIPAA, ISO 27001), and multi-dimensional trust endorsements/star ratings. Provides technical metadata, sensitivity classifications, stewardship tracking, and upstream/downstream impact analysis.

### Models
1. **`CatalogAsset`** (`apps/bi/models/DataCatalog/CatalogAssets.py`)
   - Prefix: `BCAT-`
   - Fields: `name`, `code` (unique per tenant), `domain` (sales, finance, supply_chain, procurement, human_resources, customer, product, marketing, operations, legal_compliance), `asset_type` (warehouse_table, semantic_model, golden_record, metric, report, pipeline, source_dataset, view, ml_feature_set, file_object), `data_sensitivity` (public, internal, confidential, restricted_pii, highly_sensitive_pci_phi), `enterprise_tier` (tier_1_mission_critical, tier_2_production_core, tier_3_departmental, tier_4_sandbox), `certification_status` (draft, under_review, certified, verified, deprecated, rejected), `certification_notes`, `deprecation_reason`, `deprecation_replacement` (self-referential FK), `warehouse_table` (FK `bi.WarehouseTable`), `semantic_model` (FK `bi.SemanticModel`), `golden_record` (FK `bi.MdmGoldenRecord`), `glossary_term` (FK `bi.BusinessGlossaryTerm`), `quality_scorecard` (FK `bi.DataQualityScorecard`), `data_steward` (FK `auth.User`), `owning_org_unit` (FK `core.OrgUnit`), `schema_columns_json`, `search_tags_json`, `view_count`, `average_rating`, `description`, `is_active`.
2. **`CatalogLineageEdge`** (`apps/bi/models/DataCatalog/CatalogLineageEdges.py`)
   - Prefix: `BLIN-`
   - Fields: `upstream_asset` (FK `bi.CatalogAsset`), `downstream_asset` (FK `bi.CatalogAsset`), `lineage_type` (table_level, column_level, view_derivation, etl_transformation, semantic_metric, report_source), `upstream_column`, `downstream_column`, `transformation_pipeline` (FK `bi.EtlPipeline`), `transformation_step` (FK `bi.TransformationStep`), `impact_criticality` (low, medium, high, critical), `confidence_score`, `last_verified_at`, `notes`, `is_active`.
3. **`DataGovernancePolicy`** (`apps/bi/models/DataCatalog/DataGovernancePolicies.py`)
   - Prefix: `BGOV-`
   - Fields: `name`, `code` (unique per tenant), `policy_type` (regulatory_compliance, retention_archival, sensitivity_classification, data_masking, acceptable_use, sox_financial_control), `regulatory_framework` (gdpr_eu, hipaa_healthcare, sox_financial, pci_dss, ccpa_cpra, iso_27001, internal_standard), `enforcement_level` (advisory_informational, audit_warning, strict_blocking, automated_masking), `retention_period_days`, `masking_algorithm` (none, full_redaction, partial_mask_email_phone, hash_sha256, tokenization, nullify), `policy_owner` (FK `auth.User`), `effective_date`, `expiration_date`, `review_frequency_days`, `last_reviewed_at`, `compliance_notes`, `description`, `is_active`.
4. **`CatalogTrustEndorsement`** (`apps/bi/models/DataCatalog/CatalogTrustEndorsements.py`)
   - Prefix: `BTRU-`
   - Fields: `asset` (FK `bi.CatalogAsset`), `endorsement_type` (formal_certification, security_clearance, steward_approval, peer_review, audit_attestation, automated_benchmark), `verdict` (approved_certified, qualified_approval, rejected_unfit, needs_remediation, revoked), `rating_value` (1–5 integer stars), `attested_by` (FK `auth.User`), `attested_at`, `valid_until`, `review_comments`, `is_active`.

### URLs & Routes
- Master Command Center: `bi:catalog_overview` (`/bi/catalog/`)
- Catalog Assets:
  - `bi:catalog_asset_list` (`/bi/catalog/assets/`)
  - `bi:catalog_asset_create` (`/bi/catalog/assets/create/`)
  - `bi:catalog_asset_detail` (`/bi/catalog/assets/<int:pk>/`)
  - `bi:catalog_asset_edit` (`/bi/catalog/assets/<int:pk>/edit/`)
  - `bi:catalog_asset_delete` (`/bi/catalog/assets/<int:pk>/delete/` - POST only, `@tenant_admin_required`)
  - `bi:catalog_asset_certify` (`/bi/catalog/assets/<int:pk>/certify/` - POST only, Steward/Admin gate)
  - `bi:catalog_asset_deprecate` (`/bi/catalog/assets/<int:pk>/deprecate/` - POST only, Steward/Admin gate)
- Lineage Edges:
  - `bi:catalog_lineage_edge_list` (`/bi/catalog/lineage/`)
  - `bi:catalog_lineage_edge_create` (`/bi/catalog/lineage/create/`)
  - `bi:catalog_lineage_edge_detail` (`/bi/catalog/lineage/<int:pk>/`)
  - `bi:catalog_lineage_edge_edit` (`/bi/catalog/lineage/<int:pk>/edit/`)
  - `bi:catalog_lineage_edge_delete` (`/bi/catalog/lineage/<int:pk>/delete/` - POST only, `@tenant_admin_required`)
- Governance Policies:
  - `bi:data_governance_policy_list` (`/bi/catalog/policies/`)
  - `bi:data_governance_policy_create` (`/bi/catalog/policies/create/`)
  - `bi:data_governance_policy_detail` (`/bi/catalog/policies/<int:pk>/`)
  - `bi:data_governance_policy_edit` (`/bi/catalog/policies/<int:pk>/edit/`)
  - `bi:data_governance_policy_delete` (`/bi/catalog/policies/<int:pk>/delete/` - POST only, `@tenant_admin_required`)
- Trust Endorsements:
  - `bi:catalog_trust_endorsement_list` (`/bi/catalog/endorsements/`)
  - `bi:catalog_trust_endorsement_create` (`/bi/catalog/endorsements/create/`)
  - `bi:catalog_trust_endorsement_detail` (`/bi/catalog/endorsements/<int:pk>/`)
  - `bi:catalog_trust_endorsement_edit` (`/bi/catalog/endorsements/<int:pk>/edit/` - Reviewer/Admin gate)
  - `bi:catalog_trust_endorsement_delete` (`/bi/catalog/endorsements/<int:pk>/delete/` - POST only, `@tenant_admin_required`)

### Templates & Design Patterns
- Templates reside in `templates/bi/data_catalog/`:
  - `catalog_overview.html`: Master metadata command center with KPI summary cards, domain & sensitivity distribution progress bars, recent assets, policies, lineage edges, and endorsements.
  - `catalog_asset/` (`list.html` with filter bar and rating stars, `detail.html` with technical metadata, lineage card graph, steward certification workbench, and deprecation notices, `form.html`)
  - `catalog_lineage_edge/` (`list.html`, `detail.html` with upstream/downstream node cards and transformation step links, `form.html`)
  - `data_governance_policy/` (`list.html`, `detail.html` with regulatory framework details and retention timers, `form.html`)
  - `catalog_trust_endorsement/` (`list.html`, `detail.html` with star rating pills and reviewer comments, `form.html`)
- Design System: Colour-named badges (`.badge-green`, `.badge-info`, `.badge-amber`, `.badge-red`, `.badge-slate`, `.badge-muted`), `.stat-card`, `.stat-icon`, `.card`, and `.table-wrap`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Data Catalog demo records:
  - Catalog Assets: Ingestion Source Ledger, Core Sales Fact, Customer Dimension, Sales Performance Dashboard, Inactive Sandbox Table, Globex Confidential Source.
  - Lineage Edges: Raw Ingestion -> Staging Table -> Core Fact Mart.
  - Governance Policies: GDPR Customer PII Erasure Policy, SOX Financial Data Retention Schedule, HIPAA PHI Access Masking Standard.
  - Trust Endorsements: Formal certification (5 stars), Security clearance (5 stars), Steward peer review (4 stars).
- 100% idempotent with cascade flush.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: All queries scoped by `request.tenant` via `bi_scope` and `bi_object`. All forms reject foreign tenant FKs via `reject_foreign`.
- **Workflow & Steward Authorization**: Sensitive lifecycle mutations (`catalog_asset_certify` and `catalog_asset_deprecate`) restricted to the asset's assigned `data_steward`, tenant admin, or superuser.
- **Identity Integrity**: `attested_by` is excluded from form input and bound to `request.user` to prevent attestation spoofing.
- **Audit Logging Before Deletion**: `write_audit_log` is executed before `obj.delete()` to ensure `obj.pk` / `AuditLog.object_id` is permanently captured in compliance logs.
- **Atomic Star Rating Calculation**: `_recalculate_asset_rating(asset)` is wrapped in `transaction.atomic()` across endorsement create, edit, and delete operations.
- **Sidebar Wiring**: Live links registered in `apps/core/navigation.py` under `LIVE_LINKS["10.7"]`.
