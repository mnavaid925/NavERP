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
- **10.11 KPI & Performance Scorecards**: KPI library, Balanced Scorecards (4 Kaplan & Norton perspectives: Financial, Customer, Internal Process, Learning & Growth), plan-vs-actual variance, trend arrows, industry benchmarks, and strategy maps.
- **10.12 OLAP & Multidimensional Analysis**: Pre-aggregated cubes, hierarchies, pivot matrix analysis, what-if planning scenarios, writeback adjustments.
- **10.13 Predictive & Advanced Analytics**: Time-series forecasting, predictive & propensity modeling, prescriptive scenario optimization, automated statistical anomaly detection, and AutoML model lifecycle management.
- **10.14 AI & Augmented Analytics**: Auto-generated insights (key-driver analysis, variance decomposition, narrative summaries), proactive Smart Insight Feed, automated data preparation suggestions (joins, casts, null imputation), text & sentiment analytics, and personalized recommendation engine.
- **10.15 Natural Language & Conversational BI**: Natural language query (NLQ), conversational BI assistant, natural language generation (NLG), voice-enabled analytics, search-driven discovery.
- **10.16 Alerts, Subscriptions & Distribution**: Threshold & anomaly alerts, report subscriptions, distribution & bursting, notification center, trigger-based workflows.
- **10.17 Embedded & Mobile BI**: Embedded analytics, mobile BI app (PWA/touch-optimized/offline caching), developer APIs & SDKs, portal/kiosk/wallboard display modes, SSO & row-level security context passthrough.
- **10.18 Collaboration & Data Storytelling**: Data stories & presentations, comments & discussions, shared workspaces, annotations & decision logging, export & embed to Office.
- **10.19 Integration & API Hub**: ERP & application connectors, external BI & warehouse sync, open APIs & webhooks, streaming & message queues, marketplace & extensions.
- **10.20 Administration, Governance & Security**: Enterprise security, audit & access logging, data masking & privacy, tenant provisioning, license & usage tracking.

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

---

## Sub-module 10.8: Dashboards & Visualization

### Overview
Enterprise multi-tenant executive dashboards, interactive analytical visualization canvases, visual layout builder with drag-and-drop coordinate persistence, full-screen auto-refreshing kiosk wallboards, customizable KPI/chart widgets (KPI card, line, area, bar, column, pie, donut, gauge, heatmap, funnel, treemap, table/pivot, streaming counter), cross-filtering dimensions, personal and shared view bookmarks, and dynamic dashboard filters.

### Models
1. **`BiDashboard`** (`apps/bi/models/Dashboards/BiDashboards.py`)
   - Prefix: `BDSH-`
   - Fields: `title`, `slug` (unique per tenant), `category` (executive, finance, sales_crm, supply_chain, operations, hr, custom), `layout_type` (grid_12, executive_summary, operational_monitoring, freeform), `refresh_interval_seconds` (0 = manual, 10, 30, 60, 300, 900, 3600), `theme` (slate_corporate, indigo_modern, emerald_growth, amber_industrial, dark_observability), `role_required` (all, executive, etc.), `org_unit` (FK `core.OrgUnit`), `is_published`, `is_template`, `is_default`, `is_kiosk_enabled`, `view_count`, `last_viewed_at`, `description`, `is_active`.
2. **`BiDashboardWidget`** (`apps/bi/models/Dashboards/BiDashboardWidgets.py`)
   - Prefix: `BDWG-`
   - Fields: `dashboard` (FK `bi.BiDashboard`), `title`, `subtitle`, `widget_type` (kpi_card, line, area, bar, column, pie, donut, gauge, heatmap, funnel, treemap, table_pivot, streaming_counter), `semantic_model` (FK `bi.SemanticModel`), `calculated_measure` (FK `bi.CalculatedMeasure`), `warehouse_table` (FK `bi.WarehouseTable`), `drill_hierarchy` (FK `bi.DrillHierarchy`), `aggregation_type` (sum, avg, count, count_distinct, min, max, last), `pos_x` (0–11), `pos_y` (0–100), `width_cols` (1–12), `height_rows` (1–12), `refresh_interval_seconds`, `drilldown_target_url`, `chart_config_json` (JSON), `filter_overrides_json` (JSON), `sort_order`, `is_active`.
3. **`BiDashboardBookmark`** (`apps/bi/models/Dashboards/BiDashboardBookmarks.py`)
   - Prefix: `BDBM-`
   - Fields: `dashboard` (FK `bi.BiDashboard`), `user` (FK `auth.User`), `name` (unique per tenant, dashboard, user), `filter_state_json` (JSON), `crossfilter_state_json` (JSON), `is_default`, `is_shared`, `view_count`, `last_viewed_at`, `description`, `is_active`.
4. **`BiDashboardFilter`** (`apps/bi/models/Dashboards/BiDashboardFilters.py`)
   - Prefix: `BDFL-`
   - Fields: `dashboard` (FK `bi.BiDashboard`), `filter_label`, `filter_key` (slug unique per tenant + dashboard), `filter_type` (dropdown, multi_select, date_range, date_preset, number_range, search_text), `target_field`, `default_value`, `options_source` (static_list, semantic_distinct, warehouse_column), `static_options_json` (JSON list), `order`, `is_required`, `is_active`.

### URLs & Routes
- Dashboards:
  - `bi:bi_dashboard_list` (`/bi/dashboards/`)
  - `bi:bi_dashboard_create` (`/bi/dashboards/create/` - `@tenant_admin_required`)
  - `bi:bi_dashboard_detail` (`/bi/dashboards/<int:pk>/`)
  - `bi:bi_dashboard_edit` (`/bi/dashboards/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:bi_dashboard_delete` (`/bi/dashboards/<int:pk>/delete/` - POST only, `@tenant_admin_required`)
  - `bi:bi_dashboard_duplicate` (`/bi/dashboards/<int:pk>/duplicate/` - clone with widgets and filters)
  - `bi:bi_dashboard_publish` (`/bi/dashboards/<int:pk>/publish/` - POST only, toggle publish status)
  - `bi:bi_dashboard_canvas_view` (`/bi/dashboards/<int:pk>/view/` - visual interactive canvas with cross-filtering)
  - `bi:bi_dashboard_canvas_builder` (`/bi/dashboards/<int:pk>/builder/` - drag-and-drop layout builder, `@tenant_admin_required`)
  - `bi:bi_dashboard_kiosk_view` (`/bi/dashboards/<int:pk>/kiosk/` - full-screen wallboard view)
- Dashboard Widgets:
  - `bi:bi_dashboard_widget_list` (`/bi/dashboards/widgets/`)
  - `bi:bi_dashboard_widget_create` (`/bi/dashboards/widgets/create/` - `@tenant_admin_required`)
  - `bi:bi_dashboard_widget_detail` (`/bi/dashboards/widgets/<int:pk>/`)
  - `bi:bi_dashboard_widget_edit` (`/bi/dashboards/widgets/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:bi_dashboard_widget_delete` (`/bi/dashboards/widgets/<int:pk>/delete/` - POST only, `@tenant_admin_required`)
  - `bi:bi_dashboard_widget_data` (`/bi/dashboards/widgets/<int:pk>/data/` - JSON telemetry data feed)
- Dashboard Bookmarks:
  - `bi:bi_dashboard_bookmark_list` (`/bi/dashboards/bookmarks/`)
  - `bi:bi_dashboard_bookmark_create` (`/bi/dashboards/bookmarks/create/`)
  - `bi:bi_dashboard_bookmark_detail` (`/bi/dashboards/bookmarks/<int:pk>/`)
  - `bi:bi_dashboard_bookmark_edit` (`/bi/dashboards/bookmarks/<int:pk>/edit/` - Owner/Admin gate)
  - `bi:bi_dashboard_bookmark_delete` (`/bi/dashboards/bookmarks/<int:pk>/delete/` - POST only, Owner/Admin gate)
  - `bi:bi_dashboard_bookmark_apply` (`/bi/dashboards/bookmarks/<int:pk>/apply/` - loads and applies saved view)
- Dashboard Filters:
  - `bi:bi_dashboard_filter_list` (`/bi/dashboards/filters/`)
  - `bi:bi_dashboard_filter_create` (`/bi/dashboards/filters/create/` - `@tenant_admin_required`)
  - `bi:bi_dashboard_filter_detail` (`/bi/dashboards/filters/<int:pk>/`)
  - `bi:bi_dashboard_filter_edit` (`/bi/dashboards/filters/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:bi_dashboard_filter_delete` (`/bi/dashboards/filters/<int:pk>/delete/` - POST only, `@tenant_admin_required`)

### Templates & Design Patterns
- Templates reside in `templates/bi/dashboards/`:
  - `dashboard/` (`list.html` with card grid & widget count badges, `detail.html` with tabbed widgets/filters/bookmarks tables and null-user safe rendering, `form.html`, `duplicate_form.html`)
  - `canvas/` (`viewer.html` visual interactive canvas with Chart.js charts and filter bar, `builder.html` interactive drag-and-drop grid layout tool, `kiosk.html` full-screen dark TV wallboard with auto-reloading timer)
  - `widget/` (`list.html` with widget type badges, `detail.html` with chart preview card and telemetry link, `form.html`)
  - `bookmark/` (`list.html` with default/shared badges, `detail.html` with JSON filter state view, `form.html`)
  - `filter/` (`list.html` with filter type badges, `detail.html` with option preview chips, `form.html`)
- Design System: Colour-named badges (`.badge-green`, `.badge-info`, `.badge-amber`, `.badge-slate`, `.badge-muted`), card grid, `.stat-card`, `.table-wrap`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Dashboards & Visualization records:
  - Dashboards: Executive Command Center, Financial Operations & Margin Monitor, Supply Chain & Logistics Pulse, Globex Strategic Dashboard.
  - Widgets: Monthly Recurring Revenue KPI, Operating Margin KPI, Regional Revenue Share Donut, Quarterly Sales Growth Trend, Inventory Turn Rate Ticker.
  - Bookmarks: Q3 Fiscal Review View (Shared), EMEA Enterprise Slice (Default), Globex APAC Operations View.
  - Filters: Operating Region (Dropdown), Fiscal Year (Dropdown), Product Category (Multi-Select).
- 100% idempotent with cascade flush.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Baseline queries scoped by `request.tenant` via `bi_scope` and `bi_object`. All forms reject foreign tenant FKs via `reject_foreign`.
- **Draft Access Gate**: Unpublished draft dashboards (`is_published=False`) return 403 when accessed by non-creator regular users on canvas and kiosk views.
- **Bookmark Scoping**: Cross-user bookmark IDOR prevention via `Q(user=request.user) | Q(is_shared=True)` in canvas viewer and `apply` route.
- **Visual Builder Security**: `bi_dashboard_canvas_builder` and its AJAX coordinate updater are protected by `@tenant_admin_required` with coordinate clamping (`0 <= pos_x <= 11`, `1 <= width_cols <= 12`, `pos_x + width_cols <= 12`).
- **Sidebar Wiring**: Live links registered in `apps/core/navigation.py` under `LIVE_LINKS["10.8"]`.

---

## Sub-module 10.9: Standard & Operational Reporting

### Overview
Enterprise pixel-perfect, banded operational reports, dynamic runtime parameter prompt filtering, transactional drill-through navigation, and multi-format document exporting (HTML, PDF, Excel/CSV, Word, JSON).
- App package: `apps/bi/models/OperationalReporting/`, `forms/OperationalReporting/`, `views/OperationalReporting/`, `urls/OperationalReporting/`
- Templates: `templates/bi/operational_reporting/`
- Navigation Key: `LIVE_LINKS["10.9"]`

### Models & Key Fields
1. **`ReportDefinition`** (`BRPT-`):
   - Represents a governed operational report template.
   - Key fields: `name`, `slug`, `category` (finance, sales, inventory, procurement, hr, operations), `report_type` (tabular, summary_banded, matrix_crosstab, invoice_statement, composite_document), `status` (draft, in_review, published, deprecated), `semantic_model`, `warehouse_table`, `raw_query`, `page_orientation` (portrait, landscape), `page_size` (letter, legal, A4, A3), `margins_json`, `bands_config_json`, `columns_config_json`, `styling_css`, `is_prebuilt`.
2. **`ReportParameter`** (`BPAR-`):
   - Runtime input prompt filtering operational report queries.
   - Key fields: `report` (FK `ReportDefinition`), `parameter_name` (slug token), `prompt_label`, `parameter_type` (string, integer, decimal, date, daterange, boolean, choice_single, choice_multi), `choices_source` (static_list, semantic_dimension, warehouse_column), `choices_config_json`, `default_value`, `is_required`, `is_hidden`, `validation_regex`, `prompt_order`.
3. **`ReportExecution`** (`BRUN-`):
   - Telemetry log and audit trail of interactive viewer runs and batch export jobs.
   - Key fields: `report` (FK `ReportDefinition`), `executed_by` (FK `User`), `execution_mode` (interactive_view, export_pdf, export_excel, export_csv, export_docx, drill_through), `execution_status` (pending, running, completed, failed), `started_at`, `completed_at`, `duration_ms`, `parameter_values_json`, `row_count`, `output_format` (html, pdf, xlsx, csv, docx, json), `output_file_name`, `file_size_bytes`, `error_message`, `is_cached`.
   - Composite indexes: `idx_brun_ten_rpt_start` (`tenant, report, -started_at`), `idx_brun_ten_format` (`tenant, output_format`), `idx_brun_ten_mode` (`tenant, execution_mode`).
4. **`ReportDrillPath`** (`BDRP-`):
   - Hyperlink action navigation from summary operational report cells to sub-reports or ERP record detail pages.
   - Key fields: `source_report` (FK `ReportDefinition`), `source_field`, `drill_label`, `target_type` (subreport, operational_report, erp_record_url), `target_report` (FK `ReportDefinition`), `target_url_pattern`, `parameter_mapping_json`, `is_enabled`, `sort_order`.

### URLs & Routes
- Report Definitions:
  - `bi:report_definition_list` (`/bi/reports/`)
  - `bi:report_definition_create` (`/bi/reports/create/` - `@tenant_admin_required`)
  - `bi:report_definition_detail` (`/bi/reports/<int:pk>/`)
  - `bi:report_definition_edit` (`/bi/reports/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:report_definition_delete` (`/bi/reports/<int:pk>/delete/` - POST only, `@tenant_admin_required`)
  - `bi:report_definition_clone` (`/bi/reports/<int:pk>/clone/` - copy dialog with parameter/drill path duplication, `@tenant_admin_required`)
  - `bi:report_definition_viewer` (`/bi/reports/<int:pk>/view/` - interactive grid viewer with prompt bar)
  - `bi:report_definition_print` (`/bi/reports/<int:pk>/print/` - print-ready preview with CSS page styles)
- Report Parameters:
  - `bi:report_parameter_list` (`/bi/report-parameters/`)
  - `bi:report_parameter_create` (`/bi/report-parameters/create/` - `@tenant_admin_required`)
  - `bi:report_parameter_detail` (`/bi/report-parameters/<int:pk>/`)
  - `bi:report_parameter_edit` (`/bi/report-parameters/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:report_parameter_delete` (`/bi/report-parameters/<int:pk>/delete/` - POST only, `@tenant_admin_required`)
- Report Executions:
  - `bi:report_execution_list` (`/bi/report-executions/`)
  - `bi:report_execution_run` (`/bi/report-executions/run/<int:report_pk>/` - trigger on-demand run)
  - `bi:report_execution_detail` (`/bi/report-executions/<int:pk>/`)
  - `bi:report_execution_delete` (`/bi/report-executions/<int:pk>/delete/` - POST only, `@tenant_admin_required`)
  - `bi:report_execution_export` (`/bi/report-executions/<int:pk>/export/<str:export_format>/` - download CSV/JSON/XLSX)
- Report Drill Paths:
  - `bi:report_drill_path_list` (`/bi/report-drill-paths/`)
  - `bi:report_drill_path_create` (`/bi/report-drill-paths/create/` - `@tenant_admin_required`)
  - `bi:report_drill_path_detail` (`/bi/report-drill-paths/<int:pk>/`)
  - `bi:report_drill_path_edit` (`/bi/report-drill-paths/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:report_drill_path_delete` (`/bi/report-drill-paths/<int:pk>/delete/` - POST only, `@tenant_admin_required`)

### Templates & Design Patterns
- Templates reside in `templates/bi/operational_reporting/`:
  - `report_definition/` (`list.html` with category filters, KPI stat cards, and prebuilt badges; `detail.html` with tabbed parameters/executions/drill paths and action buttons; `form.html`; `clone.html`; `viewer.html` with interactive filter prompt bar and column rendering; `print.html` with print-specific `@page` CSS layout).
  - `report_parameter/` (`list.html` with type badges; `detail.html` with choices preview; `form.html`).
  - `report_execution/` (`list.html` with mode and status badges; `detail.html` with runtime metrics and export download buttons; `form.html`).
  - `report_drill_path/` (`list.html` with target type badges; `detail.html`; `form.html`).
- Design System: Colour-named badges (`.badge-green`, `.badge-info`, `.badge-amber`, `.badge-slate`, `.badge-muted`), `.stat-card`, `.table-wrap`, and `.btn`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Standard & Operational Reporting records:
  - 4 Pre-built Reports:
    - Acme Inc Monthly Profit & Loss Statement (Finance, Tabular)
    - Sales Performance & Commission Audit (Sales, Summary Banded)
    - Warehouse Stock Balance & Valuation Report (Inventory, Tabular)
    - Department Headcount & Payroll Allocation (HR, Summary Banded)
  - Pre-configured prompt parameters (Fiscal Year, Department, Status).
  - Transactional drill paths (Item drill-through, Customer 360 link).
  - Simulated execution history telemetry across interactive and export runs.
- 100% idempotent with `--flush` support.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Stored XSS Protection**: Custom report CSS is validated by `clean_styling_css` in `ReportDefinitionForm` to block `</style>`, `<script>`, `<iframe>`, and dangerous protocols, with closing tags stripped prior to rendering.
- **CSV Formula Injection Mitigation**: All column headers and cell values in `report_execution_export` are escaped via `csv_safe(...)` to prevent DDE formula execution (`=`, `+`, `-`, `@`).
- **Read-Only Viewer Idempotency**: `report_definition_viewer` is read-only on GET requests and does not flood execution audit logs; execution runs require deliberate POST submissions.
- **Safe Filtering**: Integer FK GET parameters (`report_id`) are guarded with `.isdigit()` before querying the database, preventing `ValueError` 500s.
- **Unique Slugs on Clone**: `ReportCloneForm` enforces uniqueness of `new_slug` within the tenant to prevent unhandled database constraint crashes.
- **Sidebar Wiring**: Live links registered in `apps/core/navigation.py` under `LIVE_LINKS["10.9"]`.

---

## Sub-module 10.10: Self-Service & Ad-Hoc Analytics

### Overview
Sub-module 10.10 provides business and analytical users with visual query composition, ad-hoc metrics computation, multi-source dataset blending, and interactive analysis exploration with personal and team workspace sharing.

App Path: `apps/bi/`
Sub-package Path: `apps/bi/{models,forms,views,urls}/SelfServiceAnalytics/`

### Models
1. **`AdHocQuery`** (`apps/bi/models/SelfServiceAnalytics/AdHocQueries.py`):
   - Table: `bi_ad_hoc_query`, Prefix: `BAHQ` (`TenantNumbered`).
   - Fields: `name`, `slug`, `description`, `source_type` (`semantic_model`, `warehouse_table`, `blend`), `semantic_model` (FK `SemanticModel`), `warehouse_table` (FK `WarehouseTable`), `data_blend` (FK `DataBlendDefinition`), `fields_config_json` (selected dimensions and measures with aggregations), `filter_criteria_json` (rules with operators), `sort_config_json`, `visualization_type` (`table`, `bar_chart`, `line_chart`, `area_chart`, `pie_chart`, `kpi_card`, `pivot_table`), `chart_config_json`, `row_limit`, `status` (`draft`, `active`, `archived`), `last_executed_at`, `execution_duration_ms`, `row_count`, `created_by` (FK `User`).
   - Indexes: composite on `(tenant, source_type)`, `(tenant, visualization_type)`, `(tenant, status)`, `(tenant, created_by)`.

2. **`AdHocCalculatedField`** (`apps/bi/models/SelfServiceAnalytics/AdHocCalculatedFields.py`):
   - Table: `bi_ad_hoc_calculated_field`, Prefix: `BACF` (`TenantNumbered`).
   - Fields: `query` (FK `AdHocQuery`), `field_name`, `display_label`, `formula_expression`, `return_type` (`decimal`, `integer`, `percentage`, `currency`, `string`, `boolean`), `aggregation_mode` (`formula`, `pre_agg`, `post_agg`), `is_valid`, `error_message`, `created_by` (FK `User`).
   - UniqueConstraint: `(tenant, query, field_name)`.
   - Badge Properties: `badge_return_type` (`badge-info`, `badge-green`, `badge-slate`, `badge-amber`), `badge_mode`.

3. **`DataBlendDefinition`** (`apps/bi/models/SelfServiceAnalytics/DataBlendDefinitions.py`):
   - Table: `bi_data_blend_definition`, Prefix: `BBLD` (`TenantNumbered`).
   - Fields: `name`, `slug`, `description`, `primary_source_type`, `primary_semantic_model`, `primary_warehouse_table`, `secondary_source_type`, `secondary_semantic_model`, `secondary_warehouse_table`, `join_type` (`inner`, `left_outer`, `right_outer`, `full_outer`), `join_keys_mapping_json`, `cardinality` (`one_to_one`, `one_to_many`, `many_to_one`), `collision_resolution`, `status` (`active`, `draft`, `deprecated`), `created_by` (FK `User`).
   - Indexes: composite on `(tenant, status)`, `(tenant, join_type)`, `(tenant, created_by)`, `(tenant, created_at)`.
   - Badge Properties: `badge_join`, `badge_status`.

4. **`SavedAnalysisView`** (`apps/bi/models/SelfServiceAnalytics/SavedAnalysisViews.py`):
   - Table: `bi_saved_analysis_view`, Prefix: `BSAV` (`TenantNumbered`).
   - Fields: `name`, `slug`, `description`, `query` (FK `AdHocQuery`), `sharing_scope` (`personal`, `team`, `tenant_public`), `org_unit` (FK `core.OrgUnit`), `is_template`, `is_favorite`, `parent_view` (self-referential FK), `share_token`, `view_count`, `last_viewed_at`, `created_by` (FK `User`).
   - Indexes: composite on `(tenant, sharing_scope)`, `(tenant, org_unit)`, `(tenant, created_by)`, `(tenant, is_template)`, `(tenant, query)`, `(tenant, created_at)`.
   - Badge Property: `badge_scope` (`badge-slate`, `badge-info`, `badge-green`).

### URLs & Routes
- Ad-Hoc Queries:
  - `bi:ad_hoc_query_list` (`/bi/queries/`)
  - `bi:ad_hoc_query_create` (`/bi/queries/create/`)
  - `bi:ad_hoc_query_detail` (`/bi/queries/<int:pk>/`)
  - `bi:ad_hoc_query_edit` (`/bi/queries/<int:pk>/edit/`)
  - `bi:ad_hoc_query_delete` (`/bi/queries/<int:pk>/delete/` - `@require_POST`)
  - `bi:ad_hoc_query_composer` (`/bi/queries/<int:pk>/composer/`)
  - `bi:ad_hoc_query_execute` (`/bi/queries/<int:pk>/execute/` - `@require_POST`)
  - `bi:ad_hoc_query_export` (`/bi/queries/<int:pk>/export/`)
- Calculated Fields:
  - `bi:ad_hoc_calculated_field_list` (`/bi/calculated-fields/`)
  - `bi:ad_hoc_calculated_field_validate` (`/bi/calculated-fields/validate/` - JSON formula validator)
  - `bi:ad_hoc_calculated_field_create` (`/bi/calculated-fields/create/`)
  - `bi:ad_hoc_calculated_field_detail` (`/bi/calculated-fields/<int:pk>/`)
  - `bi:ad_hoc_calculated_field_edit` (`/bi/calculated-fields/<int:pk>/edit/`)
  - `bi:ad_hoc_calculated_field_delete` (`/bi/calculated-fields/<int:pk>/delete/` - `@require_POST`)
- Data Blends:
  - `bi:data_blend_definition_list` (`/bi/data-blends/`)
  - `bi:data_blend_definition_create` (`/bi/data-blends/create/`)
  - `bi:data_blend_definition_detail` (`/bi/data-blends/<int:pk>/`)
  - `bi:data_blend_definition_edit` (`/bi/data-blends/<int:pk>/edit/`)
  - `bi:data_blend_definition_delete` (`/bi/data-blends/<int:pk>/delete/` - `@require_POST`)
  - `bi:data_blend_definition_preview` (`/bi/data-blends/<int:pk>/preview/`)
- Saved Analysis Views:
  - `bi:saved_analysis_view_list` (`/bi/saved-views/`)
  - `bi:saved_analysis_view_create` (`/bi/saved-views/create/`)
  - `bi:saved_analysis_view_detail` (`/bi/saved-views/<int:pk>/`)
  - `bi:saved_analysis_view_edit` (`/bi/saved-views/<int:pk>/edit/`)
  - `bi:saved_analysis_view_delete` (`/bi/saved-views/<int:pk>/delete/` - `@require_POST`)
  - `bi:saved_analysis_view_share` (`/bi/saved-views/<int:pk>/share/`)
  - `bi:saved_analysis_view_explore` (`/bi/saved-views/<int:pk>/explore/`)
  - `bi:saved_analysis_view_clone` (`/bi/saved-views/<int:pk>/clone/` - `@require_POST`, atomic, unique slug de-duplication)

### Templates & Design Patterns
- Templates reside in `templates/bi/self_service_analytics/`:
  - `ad_hoc_query/` (`list.html`, `detail.html`, `form.html`, `composer.html`).
  - `ad_hoc_calculated_field/` (`list.html`, `detail.html`, `form.html`).
  - `data_blend_definition/` (`list.html`, `detail.html`, `form.html`).
  - `saved_analysis_view/` (`list.html`, `detail.html`, `form.html`, `explore.html`, `share.html`).
- Design System: Pure colour-named badge modifiers (`.badge-green`, `.badge-info`, `.badge-amber`, `.badge-slate`, `.badge-muted`), `.card`, `.stat-card`, `.table-wrap`, and `.btn`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Self-Service & Ad-Hoc records:
  - Demo ad-hoc queries: Monthly Revenue Trend by Region (visual builder with simulated execution telemetry).
  - Calculated fields: Net Margin Percentage, Gross Profit per Unit.
  - Data blends: Sales and Procurement Orders Mashup.
  - Saved views: Executive Revenue Run Rate (with personal and tenant public scopes).
- 100% idempotent with `--flush` support.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Intra-Tenant Authorization**: Personal views (`sharing_scope="personal"`) are restricted to the owner and tenant administrators; other tenant members attempting to view or modify receive 403 Forbidden.
- **CSRF & State Mutation Protection**: All mutating actions (`delete`, `clone`, `execute`) strictly require POST requests and validate CSRF tokens.
- **Slug De-duplication on Clone**: View cloning generates a unique tenant-scoped slug in a loop (`copy-of-...-<counter>`) avoiding database unique constraint collisions.
- **CSV Formula Injection Mitigation**: All exported columns and cells are sanitized via `csv_safe(...)`.
- **Sidebar Wiring**: Registered in `apps/core/navigation.py` under `LIVE_LINKS["10.10"]`.

---

## Sub-module 10.11: KPI & Performance Scorecards

### Models
1. **`KpiDefinition`** (`apps/bi/models/PerformanceScorecards/KpiDefinitions.py`)
   - Table: `bi_kpidefinition`, Prefix: `BKPI-` (`TenantNumbered`).
   - Fields: `name`, `code`, `slug`, `description`, `category`, `perspective` (`financial`, `customer`, `internal_process`, `learning_growth`), `target_direction` (`maximize`, `minimize`, `in_range`), `unit_of_measure` (`percentage`, `currency`, `count`, `days`, `hours`, `ratio`, `score`), `tracking_frequency` (`daily`, `weekly`, `monthly`, `quarterly`, `annual`), `calculation_type` (`manual`, `semantic_measure`, `formula_expression`, `aggregation`), `semantic_measure` (FK `CalculatedMeasure`), `formula_expression`, `target_value`, `warning_threshold`, `critical_threshold`, `current_value`, `previous_value`, `industry_benchmark_value`, `benchmark_source`, `benchmark_percentile`, `status` (`draft`, `active`, `under_review`, `deprecated`, `archived`), `is_active`, `owner` (FK `User`), `department` (FK `OrgUnit`), `last_calculated_at`.
   - Methods: `calculate_rag_status()`, `record_measurement(new_value, save=True)`, `variance_from_target`, `benchmark_variance`.
   - Badges: `badge_status` (`badge-slate`, `badge-green`, `badge-amber`, `badge-red`), `badge_perspective`.

2. **`PerformanceScorecard`** (`apps/bi/models/PerformanceScorecards/PerformanceScorecards.py`)
   - Table: `bi_performancescorecard`, Prefix: `BSCR-` (`TenantNumbered`).
   - Fields: `name`, `slug`, `description`, `scorecard_type` (`balanced_scorecard`, `departmental`, `strategic_initiative`, `operational`, `individual`), `review_period` (`monthly`, `quarterly`, `semi_annual`, `annual`), `fiscal_year`, `financial_weight`, `customer_weight`, `internal_process_weight`, `learning_growth_weight`, `overall_score`, `overall_rag_status` (`green`, `amber`, `red`, `gray`), `status` (`draft`, `active`, `under_review`, `archived`), `is_default`, `is_published`, `owner` (FK `User`), `org_unit` (FK `OrgUnit`), `last_recalculated_at`.
   - Methods: `recalculate_performance()`, `get_perspective_summary(assignments=None)`, `save()` (atomic default reset).
   - Indexes: composite on `(tenant, overall_rag_status)` (`idx_bscr_ten_rag`).

3. **`ScorecardKpiAssignment`** (`apps/bi/models/PerformanceScorecards/ScorecardKpiAssignments.py`)
   - Table: `bi_scorecardkpiassignment`, Prefix: `BSCI-` (`TenantNumbered`).
   - Fields: `scorecard` (FK `PerformanceScorecard`), `kpi` (FK `KpiDefinition`), `objective` (FK `StrategicObjective`), `perspective`, `weight`, `target_value`, `actual_value`, `variance`, `variance_percentage`, `rag_status` (`green`, `amber`, `red`, `gray`), `trend_direction` (`improving`, `steady`, `declining`), `normalized_score`, `benchmark_overlay_value`, `benchmark_variance`, `measurement_date`, `notes`, `sort_order`.
   - Methods: `calculate_performance_metrics()`, `record_actual_value(actual_value, save=True)`.
   - Constraints & Indexes: unique together on `(scorecard, kpi)`, index on `(tenant, trend_direction)` (`idx_bsci_ten_trend`).

4. **`StrategicObjective`** (`apps/bi/models/PerformanceScorecards/StrategicObjectives.py`)
   - Table: `bi_strategic_objective`, Prefix: `BOBJ-` (`TenantNumbered`).
   - Fields: `name`, `code`, `slug`, `perspective`, `statement_of_intent`, `parent_objective` (FK `self`), `target_date`, `rag_status`, `alignment_score`, `status` (`draft`, `active`, `achieved`, `canceled`, `postponed`), `owner` (FK `User`), `org_unit` (FK `OrgUnit`), `sort_order`.
   - Methods: `recalculate_alignment()`.
   - Indexes: composite on `(tenant, rag_status)` (`idx_bobj_ten_rag`).

### URLs & Routes
- KPI Definitions:
  - `bi:kpi_definition_list` (`/bi/kpis/`)
  - `bi:kpi_definition_create` (`/bi/kpis/create/` - `@tenant_admin_required`)
  - `bi:kpi_definition_detail` (`/bi/kpis/<int:pk>/`)
  - `bi:kpi_definition_edit` (`/bi/kpis/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:kpi_definition_delete` (`/bi/kpis/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:kpi_definition_refresh` (`/bi/kpis/<int:pk>/refresh/` - `@tenant_admin_required`, `@require_POST`)
- Performance Scorecards:
  - `bi:performance_scorecard_list` (`/bi/scorecards/`)
  - `bi:performance_scorecard_create` (`/bi/scorecards/create/` - `@tenant_admin_required`)
  - `bi:performance_scorecard_detail` (`/bi/scorecards/<int:pk>/`)
  - `bi:performance_scorecard_edit` (`/bi/scorecards/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:performance_scorecard_delete` (`/bi/scorecards/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:performance_scorecard_strategy_map` (`/bi/scorecards/<int:pk>/strategy-map/`)
  - `bi:performance_scorecard_recalculate` (`/bi/scorecards/<int:pk>/recalculate/` - `@tenant_admin_required`, `@require_POST`)
- Scorecard KPI Assignments:
  - `bi:scorecard_kpi_assignment_list` (`/bi/assignments/`)
  - `bi:scorecard_kpi_assignment_create` (`/bi/assignments/create/` - `@tenant_admin_required`)
  - `bi:scorecard_kpi_assignment_detail` (`/bi/assignments/<int:pk>/`)
  - `bi:scorecard_kpi_assignment_edit` (`/bi/assignments/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:scorecard_kpi_assignment_delete` (`/bi/assignments/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:scorecard_kpi_assignment_record_actual` (`/bi/assignments/<int:pk>/record-actual/` - `@tenant_admin_required`)
- Strategic Objectives:
  - `bi:strategic_objective_list` (`/bi/objectives/`)
  - `bi:strategic_objective_create` (`/bi/objectives/create/` - `@tenant_admin_required`)
  - `bi:strategic_objective_detail` (`/bi/objectives/<int:pk>/`)
  - `bi:strategic_objective_edit` (`/bi/objectives/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:strategic_objective_delete` (`/bi/objectives/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)

### Templates & Design Patterns
- Templates reside in `templates/bi/kpi_performance_scorecards/`:
  - `kpi_definition/` (`list.html`, `detail.html`, `form.html`).
  - `performance_scorecard/` (`list.html`, `detail.html`, `form.html`, `strategy_map.html`, `_kpi_row.html`, `_objective_card.html`).
  - `scorecard_kpi_assignment/` (`list.html`, `detail.html`, `form.html`, `record_actual.html`).
  - `strategic_objective/` (`list.html`, `detail.html`, `form.html`).
- Design System: Colour-named badge modifiers only (`badge-green`, `badge-red`, `badge-amber`, `badge-slate`, `badge-info`), card components, stat-cards, table wrappers, and interactive strategy map.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant KPI & Performance Scorecards demo data:
  - KPI Definitions: Net Profit Margin (financial), Customer Retention Rate (customer), Order Fulfillment Cycle Time (internal_process), Employee Training Completion Rate (learning_growth).
  - Performance Scorecards: Corporate Balanced Scorecard (default, published, weighted across 4 perspectives).
  - Strategic Objectives: Expand High-Margin Enterprise Services, Deliver Frictionless Customer Experience, Automate Supply Chain & Manufacturing Fulfillment, Build Data & AI Capabilities.
  - Scorecard KPI Assignments: Linked to scorecards and objectives with actual measurements, target values, normalized scores, and trend arrows.
- 100% idempotent with `--flush` support.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Role-Based Authorization**: `@tenant_admin_required` strictly enforced on all create, edit, delete, refresh, recalculate, and record-actual views.
- **Audit Logging**: `write_audit_log(request.user, obj, action, changes=..., tenant=request.tenant)` implemented across all mutation endpoints.
- **Sidebar Wiring**: Registered in `apps/core/navigation.py` under `LIVE_LINKS["10.11"]`.

---

## Sub-module 10.12: OLAP & Multidimensional Analysis

### Models
1. **`OlapCube`** (`apps/bi/models/OlapAnalysis/OlapCubes.py`):
   - Table: `bi_olap_cube`, Prefix: `BOCB` (`TenantNumbered`).
   - Fields: `name`, `slug`, `description`, `storage_mode` (`rolap`, `molap`, `holap`), `semantic_model` (FK `SemanticModel`), `warehouse_table` (FK `WarehouseTable`), `default_hierarchy` (FK `DrillHierarchy`), `dimensions_config` (JSON list of dimension objects), `measures_config` (JSON list of measure definitions with aggregations), `aggregations_config` (JSON pre-aggregation rules), `status` (`draft`, `active`, `processing`, `archived`), `is_realtime_enabled`, `cache_ttl_minutes`, `last_refreshed_at`, `created_by` (FK `User`).
   - Indexes: composite on `(tenant, status)`, `(tenant, storage_mode)`, `(tenant, created_by)`, `(tenant, created_at)`.
   - Methods: `refresh_cube()` (stamps `last_refreshed_at` and records audit log).
   - Badge Properties: `badge_storage_mode` (`badge-info`, `badge-slate`), `badge_status`.

2. **`PivotAnalysisView`** (`apps/bi/models/OlapAnalysis/PivotViews.py`):
   - Table: `bi_pivot_analysis_view`, Prefix: `BPIV` (`TenantNumbered`).
   - Fields: `cube` (FK `OlapCube`), `name`, `slug`, `description`, `row_dimensions` (JSON list), `column_dimensions` (JSON list), `measures_selection` (JSON list), `filter_slice_json`, `conditional_formatting` (JSON formatting rules), `total_position` (`bottom_right`, `top_left`, `none`), `show_subtotals`, `drill_through_enabled`, `drill_through_target` (validated URL route name), `status` (`active`, `draft`, `archived`), `created_by` (FK `User`).
   - Indexes: composite on `(tenant, cube)`, `(tenant, status)`, `(tenant, created_by)`, `(tenant, created_at)`.
   - Badge Properties: `badge_status`.

3. **`WhatIfScenario`** (`apps/bi/models/OlapAnalysis/WhatIfScenarios.py`):
   - Table: `bi_what_if_scenario`, Prefix: `BWIF` (`TenantNumbered`).
   - Fields: `cube` (FK `OlapCube`), `name`, `slug`, `description`, `fiscal_period` (FK `accounting.FiscalPeriod`), `baseline_budget` (FK `accounting.Budget`), `status` (`draft`, `simulated`, `committed`, `archived`), `total_baseline_amount`, `total_adjusted_amount`, `total_variance_amount` (auto-calculated on save), `default_disaggregation` (`proportional`, `equal`, `custom_weights`), `driver_parameters` (JSON dict), `is_committed`, `committed_at`, `committed_by` (FK `User`), `created_by` (FK `User`).
   - Indexes: composite on `(tenant, cube)` (`idx_bwif_ten_cube`), `(tenant, status)`, `(tenant, fiscal_period)`, `(tenant, created_by)`, `(tenant, created_at)`.
   - Badge Properties: `badge_status` (`badge-slate`, `badge-info`, `badge-green`, `badge-muted`).

4. **`ScenarioWritebackCell`** (`apps/bi/models/OlapAnalysis/WritebackCells.py`):
   - Table: `bi_scenario_writeback_cell`, Prefix: `BWBC` (`TenantNumbered`).
   - Fields: `scenario` (FK `WhatIfScenario`), `coordinate_keys_json` (JSON dict of coordinate key-value pairs), `baseline_amount`, `adjustment_delta` (auto-calculated), `simulated_amount`, `adjustment_method` (`absolute`, `percentage_delta`, `formula_spread`), `is_committed`, `committed_at`, `committed_budget_line` (FK `accounting.BudgetLine`), `created_by` (FK `User`).
   - `__str__`: `f"{self.number}"` (simplified to avoid N+1 queries during audit logging).
   - Indexes: composite on `(tenant, scenario)`, `(tenant, is_committed)`, `(tenant, created_by)`, `(tenant, created_at)`.
   - Badge Properties: `badge_status` (`badge-green` for committed, `badge-slate` for draft).

### URLs & Routes
- OLAP Cubes:
  - `bi:olap_cube_list` (`/bi/cubes/`)
  - `bi:olap_cube_create` (`/bi/cubes/create/`)
  - `bi:olap_cube_detail` (`/bi/cubes/<int:pk>/`)
  - `bi:olap_cube_edit` (`/bi/cubes/<int:pk>/edit/`)
  - `bi:olap_cube_delete` (`/bi/cubes/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:olap_cube_refresh` (`/bi/cubes/<int:pk>/refresh/` - `@require_POST`)
- Pivot Views:
  - `bi:pivot_view_list` (`/bi/pivots/`)
  - `bi:pivot_view_create` (`/bi/pivots/create/`)
  - `bi:pivot_view_detail` (`/bi/pivots/<int:pk>/`)
  - `bi:pivot_view_edit` (`/bi/pivots/<int:pk>/edit/`)
  - `bi:pivot_view_delete` (`/bi/pivots/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:pivot_view_matrix` (`/bi/pivots/<int:pk>/matrix/` - Interactive pivot matrix workspace)
- What-If Scenarios:
  - `bi:what_if_scenario_list` (`/bi/scenarios/`)
  - `bi:what_if_scenario_create` (`/bi/scenarios/create/`)
  - `bi:what_if_scenario_detail` (`/bi/scenarios/<int:pk>/`)
  - `bi:what_if_scenario_edit` (`/bi/scenarios/<int:pk>/edit/` - guarded against committed status)
  - `bi:what_if_scenario_delete` (`/bi/scenarios/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`, guarded against committed status)
  - `bi:what_if_scenario_simulate` (`/bi/scenarios/<int:pk>/simulate/` - Simulation workbench)
  - `bi:what_if_scenario_commit` (`/bi/scenarios/<int:pk>/commit/` - `@tenant_admin_required`, `@require_POST`)
- Writeback Cells:
  - `bi:writeback_cell_list` (`/bi/writeback-cells/`)
  - `bi:writeback_cell_create` (`/bi/writeback-cells/create/` - guarded against committed scenario)
  - `bi:writeback_cell_detail` (`/bi/writeback-cells/<int:pk>/`)
  - `bi:writeback_cell_edit` (`/bi/writeback-cells/<int:pk>/edit/` - guarded against committed status)
  - `bi:writeback_cell_delete` (`/bi/writeback-cells/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`, guarded against committed status)

### Templates & Design Patterns
- Templates reside in `templates/bi/olap_analysis/`:
  - `olap_cube/` (`list.html`, `detail.html`, `form.html`).
  - `pivot_view/` (`list.html`, `detail.html`, `form.html`, `matrix.html`).
  - `what_if_scenario/` (`list.html`, `detail.html`, `form.html`, `simulate.html`).
  - `writeback_cell/` (`list.html`, `detail.html`, `form.html`).
- Design System: Colour-named badge modifiers only (`badge-info`, `badge-green`, `badge-slate`, `badge-amber`, `badge-muted`), card components, stat-cards, table wrappers, and interactive modal/matrix layouts.
- Nullable User FK Guards: All templates use explicit `{% if obj.created_by %}` and `{% if scenario.committed_by %}` checks, avoiding Lesson L10 crashes.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant OLAP & Multidimensional records:
  - Demo OLAP Cubes: Enterprise Financial Performance Cube (MOLAP, 4 dimensions, 3 measures, pre-aggregations).
  - Pivot Views: Departmental Expense Breakdown Matrix, Quarterly Revenue Matrix with subtotal calculations.
  - What-If Scenarios: FY2026 Optimistic Budgeting Scenario, Baseline Disaggregation Model.
  - Writeback Cells: Multi-coordinate leaf adjustments across departments, expense accounts, and fiscal quarters with calculated variances.
- 100% idempotent with `--flush` support.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Financial Ledger & State Immutability**: Committed scenarios (`status="committed"`) and committed writeback cells are locked against modification or deletion across both UI and backend views.
- **Role-Based Authorization**: `@tenant_admin_required` strictly enforced on commit (`what_if_scenario_commit`) and all delete views (`olap_cube_delete`, `pivot_view_delete`, `what_if_scenario_delete`, `writeback_cell_delete`).
- **Audit Logging**: `write_audit_log(request.user, obj, action, changes=..., tenant=request.tenant)` correctly implemented across all 14 mutation endpoints.
- **Route Validation**: `drill_through_target` dynamically validated in form via `django.urls.reverse` to prevent `NoReverseMatch` 500 crashes.
- **Sidebar Wiring**: Registered in `apps/core/navigation.py` under `LIVE_LINKS["10.12"]`.

---

## Sub-module 10.13: Predictive & Advanced Analytics

### Models
1. **`PredictiveModel`** (`apps/bi/models/PredictiveAnalytics/PredictiveModels.py`):
   - Table: `bi_predictive_model`, Prefix: `BPML` (`TenantNumbered`).
   - Fields: `name`, `slug`, `description`, `problem_type` (`time_series_forecast`, `binary_classification`, `multiclass_classification`, `regression`, `anomaly_detection`), `algorithm` (`linear_regression`, `logistic_regression`, `random_forest`, `gradient_boosting`, `exponential_smoothing`, `arima`, `isolation_forest`, `z_score`), `semantic_model` (FK `SemanticModel`), `warehouse_table` (FK `WarehouseTable`), `target_metric`, `features_list` (JSON list), `hyperparameters` (JSON dict), `model_version`, `status` (`draft`, `training`, `active`, `under_review`, `retired`), `accuracy_metric_name`, `accuracy_metric_value`, `feature_importance` (JSON dict), `drift_threshold`, `is_active`, `created_by` (FK `User`).
   - Constraints & Indexes: unique on `(tenant, slug)`, composite indexes on `(tenant, -created_at)`, `(tenant, status)`, `(tenant, problem_type)`.
   - Methods: `trigger_training()` (simulates AutoML training, calculates accuracy metrics, updates status and feature importance).
   - Badge Properties: `badge_status` (`badge-info`, `badge-green`, `badge-amber`, `badge-muted`), `badge_problem_type`.

2. **`ForecastExecution`** (`apps/bi/models/PredictiveAnalytics/ForecastExecutions.py`):
   - Table: `bi_forecast_execution`, Prefix: `BFOR` (`TenantNumbered`).
   - Fields: `name`, `model` (FK `PredictiveModel`), `semantic_model` (FK `SemanticModel`), `kpi_definition` (FK `KpiDefinition`), `cadence` (`daily`, `weekly`, `monthly`, `quarterly`, `yearly`), `horizon_periods`, `confidence_level` (`80`, `90`, `95`, `99`), `historical_window_periods`, `seasonality_detected`, `seasonal_cycle_length`, `trend_direction` (`upward`, `downward`, `stationary`), `mape_score`, `forecast_output_data` (JSON list of predictions and intervals), `status` (`completed`, `running`, `failed`), `execution_duration_ms`, `notes`, `executed_by` (FK `User`), `executed_at`.
   - Constraints & Indexes: unique on `(tenant, number)`, composite indexes on `(tenant, -executed_at)`, `(tenant, status)`, `(tenant, model)`.
   - Methods: `generate_forecast_points(base_value=..., trend_rate=..., save=True)` generates point projections with lower and upper confidence intervals.
   - Badge Properties: `badge_status` (`badge-green`, `badge-amber`, `badge-red`).

3. **`StatisticalAnomaly`** (`apps/bi/models/PredictiveAnalytics/StatisticalAnomalies.py`):
   - Table: `bi_statistical_anomaly`, Prefix: `BANM` (`TenantNumbered`).
   - Fields: `title`, `model` (FK `PredictiveModel`), `semantic_model` (FK `SemanticModel`), `kpi_definition` (FK `KpiDefinition`), `metric_name`, `anomaly_type` (`spike`, `drop`, `level_shift`, `trend_change`, `variance_outlier`), `detection_method` (`z_score`, `iqr`, `isolation_forest`, `moving_average`), `severity` (`info`, `warning`, `critical`), `observed_value`, `expected_value`, `deviation_percentage`, `anomaly_timestamp`, `root_cause_factors` (JSON list), `triage_status` (`open`, `acknowledged`, `investigating`, `false_positive`, `resolved`), `resolution_notes`, `assigned_to` (FK `User`).
   - Constraints & Indexes: unique on `(tenant, number)`, composite indexes on `(tenant, -anomaly_timestamp)`, `(tenant, triage_status)`, `(tenant, severity)`, `(tenant, assigned_to)`.
   - Methods: `mark_triage(status, notes, user)` updates triage state and assigned user with audit trail.
   - Badge Properties: `badge_severity` (`badge-red`, `badge-amber`, `badge-info`), `badge_triage_status`.

4. **`OptimizationScenario`** (`apps/bi/models/PredictiveAnalytics/OptimizationScenarios.py`):
   - Table: `bi_optimization_scenario`, Prefix: `BOPT` (`TenantNumbered`).
   - Fields: `name`, `slug`, `description`, `objective_type` (`maximize`, `minimize`), `target_metric_name`, `kpi_definition` (FK `KpiDefinition`), `baseline_value`, `target_value`, `optimal_value`, `projected_lift_percentage`, `solver_algorithm` (`linear_programming`, `goal_programming`, `heuristic`), `solver_status` (`draft`, `optimal`, `feasible`, `infeasible`), `decision_variables` (JSON list), `constraint_rules` (JSON list), `recommended_actions` (JSON list), `status` (`active`, `draft`, `applied`, `archived`), `owner` (FK `User`).
   - Constraints & Indexes: unique on `(tenant, slug)`, composite indexes on `(tenant, -created_at)`, `(tenant, status)`, `(tenant, solver_status)`.
   - Methods: `solve_scenario()` runs prescriptive solver heuristic, updates optimal value, lift, solver status, and recommendations.
   - Badge Properties: `badge_status`, `badge_solver_status` (`badge-green`, `badge-amber`, `badge-red`, `badge-slate`).

### URLs & Routes
- Predictive Models:
  - `bi:predictive_model_list` (`/bi/predictive-models/`)
  - `bi:predictive_model_create` (`/bi/predictive-models/create/`)
  - `bi:predictive_model_detail` (`/bi/predictive-models/<int:pk>/`)
  - `bi:predictive_model_edit` (`/bi/predictive-models/<int:pk>/edit/`)
  - `bi:predictive_model_delete` (`/bi/predictive-models/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:predictive_model_train` (`/bi/predictive-models/<int:pk>/train/` - `@require_POST`)
- Forecast Executions:
  - `bi:forecast_execution_list` (`/bi/forecast-executions/`)
  - `bi:forecast_execution_create` (`/bi/forecast-executions/create/`)
  - `bi:forecast_execution_detail` (`/bi/forecast-executions/<int:pk>/`)
  - `bi:forecast_execution_edit` (`/bi/forecast-executions/<int:pk>/edit/`)
  - `bi:forecast_execution_delete` (`/bi/forecast-executions/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
- Statistical Anomalies:
  - `bi:statistical_anomaly_list` (`/bi/statistical-anomalies/`)
  - `bi:statistical_anomaly_create` (`/bi/statistical-anomalies/create/`)
  - `bi:statistical_anomaly_detail` (`/bi/statistical-anomalies/<int:pk>/`)
  - `bi:statistical_anomaly_edit` (`/bi/statistical-anomalies/<int:pk>/edit/`)
  - `bi:statistical_anomaly_delete` (`/bi/statistical-anomalies/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:statistical_anomaly_triage` (`/bi/statistical-anomalies/<int:pk>/triage/` - `@require_POST`)
- Optimization Scenarios:
  - `bi:optimization_scenario_list` (`/bi/optimization-scenarios/`)
  - `bi:optimization_scenario_create` (`/bi/optimization-scenarios/create/`)
  - `bi:optimization_scenario_detail` (`/bi/optimization-scenarios/<int:pk>/`)
  - `bi:optimization_scenario_edit` (`/bi/optimization-scenarios/<int:pk>/edit/`)
  - `bi:optimization_scenario_delete` (`/bi/optimization-scenarios/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:optimization_scenario_solve` (`/bi/optimization-scenarios/<int:pk>/solve/` - `@require_POST`)

### Templates & Design Patterns
- Templates reside in `templates/bi/predictive_analytics/`:
  - `predictive_model/` (`list.html`, `detail.html`, `form.html`).
  - `forecast_execution/` (`list.html`, `detail.html`, `form.html`).
  - `statistical_anomaly/` (`list.html`, `detail.html`, `form.html`).
  - `optimization_scenario/` (`list.html`, `detail.html`, `form.html`).
- Design System: Colour-named badge modifiers only (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`), stat-card icons (`stat-icon blue`, `stat-icon green`, `stat-icon orange`, `stat-icon purple`, `stat-icon slate`), table wrappers (`.table-wrap` with accessible `scope="col"` headers).
- Safe Client-Side Rendering: Forecast charts consume data safely via Django's `json_script` tag (`JSON.parse`) without raw `|safe` in `<script>` tags.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Predictive & Advanced Analytics records:
  - Predictive Models: Enterprise Monthly Demand Forecast (ARIMA), Churn Propensity Classifier.
  - Forecast Executions: Forward-looking multi-period demand projections with 95% confidence intervals and MAPE scores.
  - Statistical Anomalies: Outlier latency spikes and volume drops with categorized root causes and triage workflows.
  - Optimization Scenarios: Supply chain inventory buffer and delivery cost optimization models with decision levers and operational constraints.
- 100% idempotent with `--flush` support for all four 10.13 tables.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Form Scoping**: `assigned_to` User selection in `StatisticalAnomalyForm` strictly filtered by tenant (`tenant=self.tenant`).
- **Role-Based Authorization**: `@tenant_admin_required` strictly enforced on all delete views.
- **Audit Logging**: `write_audit_log` records all model fittings, triage changes, optimizations, and CRUD mutations.
- **Sidebar Wiring**: Registered in `apps/core/navigation.py` under `LIVE_LINKS["10.13"]`.

---

## Sub-module 10.14: AI & Augmented Analytics

### Models
1. **`AugmentedInsight`** (`apps/bi/models/AiAugmentedAnalytics/AugmentedInsights.py`):
   - Table: `bi_augmentedinsight`, Prefix: `BAIN` (`TenantNumbered`).
   - Fields: `title`, `insight_type` (`key_driver`, `anomaly`, `trend_shift`, `threshold_cross`, `correlation`, `cohort_drift`), `impact_direction` (`positive`, `negative`, `neutral`), `severity` (`info`, `low`, `medium`, `high`, `critical`), `status` (`new`, `acknowledged`, `actioned`, `dismissed`, `bookmarked`), `metric_name`, `dimension_name`, `dimension_value`, `baseline_value`, `observed_value`, `variance_percentage`, `confidence_score`, `narrative_summary` (NLG text), `driver_decomposition` (JSON list of factor dicts), `semantic_model` (FK `SemanticModel`), `kpi_definition` (FK `KpiDefinition`), `warehouse_table` (FK `WarehouseTable`), `action_notes`, `created_by` (FK `User`), `actioned_by` (FK `User`), `actioned_at`.
   - Constraints & Indexes: unique on `(tenant, number)`, composite indexes on `(tenant, -created_at)`, `(tenant, insight_type)`, `(tenant, severity)`, `(tenant, status)`.
   - Methods: `badge_color`, `impact_badge_color` (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`).

2. **`SmartDataPrepSuggestion`** (`apps/bi/models/AiAugmentedAnalytics/SmartDataPrepSuggestions.py`):
   - Table: `bi_smartdataprepsuggestion`, Prefix: `BSDP` (`TenantNumbered`).
   - Fields: `target_table` (FK `WarehouseTable`), `target_column`, `suggestion_type` (`join_inference`, `type_cast`, `null_impute`, `outlier_clip`, `column_split`, `standardize_format`, `dimension_extract`), `confidence_score`, `status` (`pending`, `accepted`, `rejected`, `applied`), `rationale`, `suggested_config` (JSON dict), `suggested_transformation_sql`, `related_table` (FK `WarehouseTable`), `rejection_reason`, `reviewed_by` (FK `User`), `reviewed_at`.
   - Constraints & Indexes: unique on `(tenant, number)`, composite indexes on `(tenant, -created_at)`, `(tenant, suggestion_type)`, `(tenant, status)`, `(tenant, target_table)`.
   - Methods: `badge_color`, `suggestion_type_badge`.

3. **`TextSentimentAnalysis`** (`apps/bi/models/AiAugmentedAnalytics/TextSentimentAnalyses.py`):
   - Table: `bi_textsentimentanalysis`, Prefix: `BSNT` (`TenantNumbered`).
   - Fields: `source_type` (`customer_review`, `support_ticket`, `survey_response`, `product_feedback`, `social_mention`, `internal_note`), `source_reference`, `text_content`, `polarity_score` (-1.00 to 1.00), `subjectivity_score` (0.00 to 1.00), `sentiment_category` (`positive`, `neutral`, `negative`, `mixed`), `confidence_score`, `extracted_themes` (JSON list), `linked_party` (FK `core.Party`), `linked_org_unit` (FK `core.OrgUnit`), `analyzed_by` (FK `User`), `analyzed_at`.
   - Constraints & Indexes: unique on `(tenant, number)`, composite indexes on `(tenant, -created_at)`, `(tenant, source_type)`, `(tenant, sentiment_category)`.
   - Methods: `badge_color`, `compute_sentiment_from_text()` for lightweight NLP polarity, subjectivity, and sentiment category auto-scoring.

4. **`AnalyticsRecommendation`** (`apps/bi/models/AiAugmentedAnalytics/AnalyticsRecommendations.py`):
   - Table: `bi_analyticsrecommendation`, Prefix: `BARC` (`TenantNumbered`).
   - Fields: `user` (FK `auth.User`), `recommendation_type` (`dashboard`, `report`, `kpi`, `semantic_model`, `dataset`), `target_title`, `target_url`, `reason` (`trending`, `role_based`, `collaborative`, `recently_added`, `usage_pattern`), `rationale_text`, `affinity_score`, `status` (`active`, `clicked`, `dismissed`, `saved`), `dashboard` (FK `BiDashboard`), `report` (FK `ReportDefinition`), `kpi` (FK `KpiDefinition`), `semantic_model` (FK `SemanticModel`), `last_interacted_at`.
   - Constraints & Indexes: unique on `(tenant, number)`, composite indexes on `(tenant, -created_at)`, `(tenant, user)`, `(tenant, recommendation_type)`, `(tenant, status)`.
   - Methods: `badge_color`, `reason_badge`.

### URLs & Routes
- Auto-Generated Insights & Feed:
  - `bi:augmented_insight_list` (`/bi/augmented-insights/`)
  - `bi:augmented_insight_create` (`/bi/augmented-insights/new/`)
  - `bi:augmented_insight_feed` (`/bi/augmented-insights/feed/` - Smart streaming insight stream with severity filters)
  - `bi:augmented_insight_detail` (`/bi/augmented-insights/<int:pk>/`)
  - `bi:augmented_insight_edit` (`/bi/augmented-insights/<int:pk>/edit/`)
  - `bi:augmented_insight_delete` (`/bi/augmented-insights/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:augmented_insight_triage` (`/bi/augmented-insights/<int:pk>/triage/` - `@require_POST`)
- Automated Data Preparation Suggestions:
  - `bi:smart_data_prep_suggestion_list` (`/bi/data-prep-suggestions/`)
  - `bi:smart_data_prep_suggestion_create` (`/bi/data-prep-suggestions/new/`)
  - `bi:smart_data_prep_suggestion_detail` (`/bi/data-prep-suggestions/<int:pk>/`)
  - `bi:smart_data_prep_suggestion_edit` (`/bi/data-prep-suggestions/<int:pk>/edit/`)
  - `bi:smart_data_prep_suggestion_delete` (`/bi/data-prep-suggestions/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:smart_data_prep_suggestion_action` (`/bi/data-prep-suggestions/<int:pk>/action/` - `@require_POST`, accepts `accept`, `reject`, `apply`)
- Text & Sentiment Analytics:
  - `bi:text_sentiment_analysis_list` (`/bi/sentiment-analyses/`)
  - `bi:text_sentiment_analysis_create` (`/bi/sentiment-analyses/new/`)
  - `bi:text_sentiment_analysis_detail` (`/bi/sentiment-analyses/<int:pk>/`)
  - `bi:text_sentiment_analysis_edit` (`/bi/sentiment-analyses/<int:pk>/edit/`)
  - `bi:text_sentiment_analysis_delete` (`/bi/sentiment-analyses/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:text_sentiment_analysis_recalculate` (`/bi/sentiment-analyses/<int:pk>/recalculate/` - `@require_POST`)
- Recommendation Engine:
  - `bi:analytics_recommendation_list` (`/bi/recommendations/`)
  - `bi:analytics_recommendation_create` (`/bi/recommendations/new/`)
  - `bi:analytics_recommendation_detail` (`/bi/recommendations/<int:pk>/`)
  - `bi:analytics_recommendation_edit` (`/bi/recommendations/<int:pk>/edit/`)
  - `bi:analytics_recommendation_delete` (`/bi/recommendations/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:analytics_recommendation_interact` (`/bi/recommendations/<int:pk>/interact/` - `@require_POST`, owner/admin gated)

### Templates & Design Patterns
- Templates reside in `templates/bi/ai_augmented_analytics/`:
  - `augmented_insight/` (`list.html`, `detail.html`, `form.html`).
  - `feed.html` (Smart Insight Feed card stream with severity left-border accents and inline triage).
  - `smart_data_prep_suggestion/` (`list.html`, `detail.html`, `form.html`).
  - `text_sentiment_analysis/` (`list.html`, `detail.html`, `form.html`).
  - `analytics_recommendation/` (`list.html`, `detail.html`, `form.html`).
- Design System: Colour-named badge modifiers only (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`), stat-card icons (`blue`, `green`, `orange`, `purple`, `slate`), accessible `<table class="table">` in `.table-wrap`.

### Seeder Details
- `manage.py seed_bi` seeds comprehensive multi-tenant AI & Augmented Analytics records:
  - Augmented Insights: Key-driver revenue analysis, SaaS customer churn statistical anomaly, checkout conversion surge with structured driver decomposition factors.
  - Data Prep Suggestions: Automatic timestamp casting, customer zip code null imputation with modal centroids, and customer ID foreign key join inference.
  - Text & Sentiment Analyses: Support tickets and customer feedback reviews auto-scored for polarity, subjectivity, and extracted themes.
  - Analytics Recommendations: Role-based and trending executive dashboard and report recommendations with affinity match scores.
- 100% idempotent with `--flush` cleanup across all four 10.14 tables.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Role-Based Authorization**: `@tenant_admin_required` strictly enforced on all delete views (`augmented_insight_delete`, `smart_data_prep_suggestion_delete`, `text_sentiment_analysis_delete`, `analytics_recommendation_delete`).
- **Open Redirect Protection**: `url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()})` enforced on all redirect parameters.
- **XSS & Protocol Injection Defense**: `target_url` validated to ensure only relative paths starting with a single `/` are accepted, rejecting `javascript:` and protocol-relative `//` URLs.
- **State Transition & Ownership Guards**: Suggestions already marked `applied` cannot be overwritten via quick action. Recommendation interactions are strictly gated to the assigned recipient user or tenant admin.
- **Transactional Consistency**: All 16 mutating views wrapped in `transaction.atomic()`, ensuring consistent state between entity mutations and `write_audit_log` records.
- **Sidebar Wiring**: Registered in `apps/core/navigation.py` under `LIVE_LINKS["10.14"]`.






---

## Sub-module 10.15: Natural Language & Conversational BI

### Overview
Natural Language & Conversational BI brings search-first and conversation-first analytics to NavERP. It enables non-technical business leaders and operational teams to ask natural language questions (NLQ), engage in multi-turn analytical chat dialogs with conversational context, receive auto-written executive narrative briefings (NLG), listen to generated audio scripts, and explore analytical assets through global search-driven discovery.

### Models
1. **`NaturalLanguageQuery`** (`apps/bi/models/ConversationalBi/NaturalLanguageQueries.py`):
   - Table: `bi_naturallanguagequery`, Prefix: `BNLQ` (`TenantNumbered`).
   - Fields: `query_text`, `input_modality` (`text`, `voice`, `api`, `suggested`), `intent_type` (`metric_lookup`, `trend_analysis`, `comparative`, `root_cause`, `drill_down`, `forecasting`, `filter_slice`), `semantic_model` (FK `SemanticModel`), `warehouse_table` (FK `WarehouseTable`), `grounded_sql`, `execution_status` (`pending`, `translating`, `executing`, `completed`, `ambiguous`, `failed`), `execution_duration_ms`, `error_message`, `chart_type` (`table`, `bar_chart`, `line_chart`, `pie_chart`, `kpi_card`, `scatter_plot`), `user` (FK `auth.User`), `user_rating` (`unrated`, `helpful`, `unhelpful`), `user_feedback_notes`, `parsed_measures` (JSON list), `parsed_dimensions` (JSON list), `parsed_filters` (JSON dict), `chart_config` (JSON dict), `result_summary` (JSON dict), `conversation_session` (FK `BiConversationSession`).
   - Constraints & Indexes: unique on `(tenant, number)`, indexes on `(tenant, execution_status)`, `(tenant, input_modality)`, `(tenant, intent_type)`, `(tenant, user)`.
   - Properties: `status_badge_color`, `modality_badge_color`.

2. **`BiConversationSession`** (`apps/bi/models/ConversationalBi/BiConversationSessions.py`):
   - Table: `bi_biconversationsession`, Prefix: `BCON` (`TenantNumbered`).
   - Fields: `title`, `user` (FK `auth.User`), `primary_semantic_model` (FK `SemanticModel`), `active_dashboard` (FK `BiDashboard`), `session_status` (`active`, `archived`, `closed`), `is_pinned` (bool), `message_count` (int), `last_interaction_at`, `suggested_prompts` (JSON list), `context_state` (JSON dict), `suggested_followups` (JSON list).
   - Constraints & Indexes: unique on `(tenant, number)`, indexes on `(tenant, -last_interaction_at)`, `(tenant, is_pinned)`, `(tenant, session_status)`, `(tenant, user)`.
   - Properties: `session_status_badge_color`.

3. **`NarrativeExplanation`** (`apps/bi/models/ConversationalBi/NarrativeExplanations.py`):
   - Table: `bi_narrativeexplanation`, Prefix: `BNLG` (`TenantNumbered`).
   - Fields: `title`, `target_artifact_type` (`dashboard`, `report`, `kpi`, `semantic_model`, `anomaly`), `dashboard` (FK `BiDashboard`), `report` (FK `ReportDefinition`), `kpi` (FK `KpiDefinition`), `narrative_style` (`executive_briefing`, `operational_summary`, `anomaly_alert`, `performance_driver`, `board_presentation`), `headline`, `narrative_body` (TextField markdown), `top_positive_driver`, `top_negative_driver`, `key_takeaways` (JSON list), `audio_ready_script` (TextField spoken summary), `status` (`draft`, `generated`, `published`, `archived`), `author` (FK `auth.User`).
   - Constraints & Indexes: unique on `(tenant, number)`, indexes on `(tenant, target_artifact_type)`, `(tenant, narrative_style)`, `(tenant, status)`.
   - Properties: `narrative_style_badge_color`, `status_badge_color`.

4. **`SearchDiscoveryIndex`** (`apps/bi/models/ConversationalBi/SearchDiscoveryIndexes.py`):
   - Table: `bi_searchdiscoveryindex`, Prefix: `BSDI` (`TenantNumbered`).
   - Fields: `asset_name`, `asset_type` (`dashboard`, `report`, `kpi`, `semantic_model`, `dataset`, `glossary_term`), `semantic_model` (FK `SemanticModel`), `dashboard` (FK `BiDashboard`), `report` (FK `ReportDefinition`), `kpi` (FK `KpiDefinition`), `glossary_term` (FK `BusinessGlossaryTerm`), `synonyms` (JSON list), `description`, `category`, `relevance_weight` (Decimal 0.10-99.99), `view_count`, `search_hit_count`, `is_featured` (bool), `is_verified` (bool), `target_url`.
   - Constraints & Indexes: unique on `(tenant, number)`, indexes on `(tenant, asset_type)`, `(tenant, is_featured)`, `(tenant, is_verified)`, composite index `idx_bsdi_ten_feat_rw` on `(tenant, is_featured, -relevance_weight)`.
   - Properties: `asset_type_badge_color`, `type_badge_color`.

### URLs & Routes
- Natural Language Queries (NLQ):
  - `bi:natural_language_query_list` (`/bi/natural-language-queries/`)
  - `bi:natural_language_query_create` (`/bi/natural-language-queries/create/`)
  - `bi:natural_language_query_detail` (`/bi/natural-language-queries/<int:pk>/`)
  - `bi:natural_language_query_edit` (`/bi/natural-language-queries/<int:pk>/edit/`)
  - `bi:natural_language_query_delete` (`/bi/natural-language-queries/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:natural_language_query_rate` (`/bi/natural-language-queries/<int:pk>/rate/` - `@require_POST`)
- Conversational BI Assistant:
  - `bi:bi_conversation_session_list` (`/bi/conversations/`)
  - `bi:bi_conversation_session_create` (`/bi/conversations/create/`)
  - `bi:bi_conversation_session_detail` (`/bi/conversations/<int:pk>/`)
  - `bi:bi_conversation_session_edit` (`/bi/conversations/<int:pk>/edit/`)
  - `bi:bi_conversation_session_delete` (`/bi/conversations/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:bi_conversation_session_toggle_pin` (`/bi/conversations/<int:pk>/toggle-pin/` - `@require_POST`)
  - `bi:bi_conversation_session_close` (`/bi/conversations/<int:pk>/close/` - `@require_POST`)
  - `bi:bi_conversation_session_ask` (`/bi/conversations/<int:pk>/ask/` - `@require_POST`, open redirect safe with `next`)
  - `bi:bi_chat_workspace` (`/bi/conversations/workspace/` - Interactive chat workspace with session selector)
- Natural Language Generation (NLG):
  - `bi:narrative_explanation_list` (`/bi/narratives/`)
  - `bi:narrative_explanation_create` (`/bi/narratives/create/`)
  - `bi:narrative_explanation_detail` (`/bi/narratives/<int:pk>/`)
  - `bi:narrative_explanation_edit` (`/bi/narratives/<int:pk>/edit/`)
  - `bi:narrative_explanation_delete` (`/bi/narratives/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:narrative_explanation_publish` (`/bi/narratives/<int:pk>/publish/` - `@require_POST`, atomic)
  - `bi:narrative_explanation_regenerate` (`/bi/narratives/<int:pk>/regenerate/` - `@require_POST`)
- Search-Driven Discovery:
  - `bi:search_discovery_index_list` (`/bi/search-discovery/`)
  - `bi:search_discovery_index_create` (`/bi/search-discovery/create/`)
  - `bi:search_discovery_index_detail` (`/bi/search-discovery/<int:pk>/`)
  - `bi:search_discovery_index_edit` (`/bi/search-discovery/<int:pk>/edit/`)
  - `bi:search_discovery_index_delete` (`/bi/search-discovery/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:search_discovery_index_reweight` (`/bi/search-discovery/<int:pk>/reweight/` - `@require_POST`, `is_finite()` guarded)
  - `bi:search_discovery_hub` (`/bi/search-discovery/hub/` - Enterprise search discovery hub with synonym search)

### Templates & Design Patterns
- Templates reside in `templates/bi/conversational_bi/`:
  - `natural_language_query/` (`list.html`, `detail.html`, `form.html`).
  - `bi_conversation_session/` (`list.html`, `detail.html`, `form.html`).
  - `chat_workspace.html` (Full-featured split-pane conversational analytics assistant with suggestion chips and AST drawers).
  - `narrative_explanation/` (`list.html`, `detail.html`, `form.html` with audio briefing audio script player).
  - `search_discovery_index/` (`list.html`, `detail.html`, `form.html`, `hub.html` enterprise search console).
- Design System: Colour-named badge modifiers only (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`), stat-card icons (`blue`, `green`, `orange`, `purple`), accessible `<table class="table">` in `.table-wrap`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Conversational BI demo records:
  - Natural Language Queries: Revenue by product line in Q3, territory performance, inventory stock exceptions with grounded SQL and simulated Chart.js JSON configs.
  - Conversation Sessions: Q4 Executive Revenue & Profitability Analysis, Logistics Fulfillment Review with suggested follow-up prompts.
  - Narrative Explanations: Executive Briefings on margin expansion, On-Time Delivery operational summaries with audio TTS scripts.
  - Search Discovery Indexes: High-relevance indexed dashboards, reports, and KPIs with colloquial business synonyms (`gross margin`, `bottom line`, `ebitda`, `lead time`).
- 100% idempotent with `--flush` cleanup across all 10.15 tables.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Role-Based Authorization**: `@tenant_admin_required` strictly enforced on all delete views.
- **Open Redirect Protection**: `url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()})` enforced on all next redirect parameters.
- **Numeric Input Hardening (Lesson L35)**: `Decimal(weight_val)` is guarded with `is_finite()` before persistence.
- **Protocol-Relative URL Defense (M8)**: `clean_target_url` disallows `//evil.com` protocol-relative paths.
- **Mass Assignment Defense (M9)**: `status` excluded from `NarrativeExplanationForm` to require dedicated atomic publish view.
- **Sidebar Wiring**: Registered in `apps/core/navigation.py` under `LIVE_LINKS["10.15"]`.

---

## Sub-module 10.16: Alerts, Subscriptions & Distribution

Proactive anomaly detection, threshold-driven automated alerting, scheduled report subscriptions, multi-format distribution bursting, multi-channel delivery (in-app, email, webhooks), and an interactive Notification Center incident triage workspace.

### Models
1. **`BiAlertRule`** (`apps/bi/models/AlertsSubscriptions/BiAlertRules.py`)
   - Table: `bi_alert_rule`, Prefix: `BALR` (`TenantNumbered`).
   - Fields: `name`, `description`, `alert_type` (`kpi_threshold`, `statistical_anomaly`, `forecast_breach`, `data_freshness_sla`, `composite_rule`), `kpi_definition` (FK `KpiDefinition`), `anomaly_detection` (FK `StatisticalAnomaly`), `condition_operator` (`gt`, `lt`, `gte`, `lte`, `eq`, `outside_range`, `pct_change_gt`, `anomaly_flagged`), `threshold_value` (Decimal), `secondary_threshold_value` (Decimal), `severity` (`critical`, `warning`, `info`, `cosmetic`), `evaluation_cadence` (`realtime_event`, `every_15_min`, `hourly`, `daily`, `weekly`), `trigger_frequency` (`every_time`, `once_until_resolved`, `max_daily_once`), `delivery_channel` (`in_app_only`, `in_app_email`, `email_only`, `webhook_slack_teams`), `recipient_users` (M2M `auth.User`), `notification_email_list` (TextField), `webhook_url` (URLField), `downstream_workflow` (`none`, `create_task`, `request_approval`, `trigger_webhook`), `status` (`active`, `paused`, `tripped`, `archived`), `last_evaluated_at`, `last_triggered_at`, `trigger_count`, `last_trigger_value`.
   - Constraints & Indexes: unique on `(tenant, number)`, composite index on `(tenant, -created_at)` (`idx_balr_ten_created`), indexes on `(tenant, alert_type)`, `(tenant, severity)`, `(tenant, status)`.
   - Properties: `severity_badge_class`, `status_badge_class`, `is_tripped`.
   - Methods: `evaluate_condition(current_value, anomaly_flag=False)`, `record_evaluation(...)`.

2. **`ReportSubscription`** (`apps/bi/models/AlertsSubscriptions/ReportSubscriptions.py`)
   - Table: `bi_report_subscription`, Prefix: `BSUB` (`TenantNumbered`).
   - Fields: `name`, `target_asset_type` (`dashboard`, `report`), `dashboard` (FK `BiDashboard`), `report` (FK `ReportDefinition`), `cadence` (`daily`, `weekly`, `monthly`, `quarterly`, `custom_cron`), `scheduled_time` (TimeField), `cron_expression` (CharField), `export_format` (`pdf`, `excel`, `csv`, `html_inline`), `burst_mode` (`broadcast`, `sliced_per_recipient`), `subscriber_users` (M2M `auth.User`), `subscriber_org_units` (M2M `core.OrgUnit`), `external_recipient_emails` (TextField), `filter_overrides` (JSONField), `include_cover_page` (bool), `skip_if_empty` (bool), `status` (`active`, `paused`, `failing`, `archived`), `last_run_at`, `next_run_at`, `run_count`.
   - Constraints & Indexes: unique on `(tenant, number)`, composite index on `(tenant, -created_at)` (`idx_bsub_ten_created`), indexes on `(tenant, cadence)`, `(tenant, export_format)`, `(tenant, status)`.
   - Properties: `status_badge_class`, `format_badge_class`.
   - Methods: `record_run(success=True)`.

3. **`DistributionBurstRun`** (`apps/bi/models/AlertsSubscriptions/DistributionBurstRuns.py`)
   - Table: `bi_distribution_burst_run`, Prefix: `BBRS` (`TenantNumbered`).
   - Fields: `subscription` (FK `ReportSubscription`), `alert_rule` (FK `BiAlertRule`), `run_trigger` (`scheduled_subscription`, `alert_trigger`, `ad_hoc_manual`, `api_burst`), `delivery_channel` (`email`, `in_app`, `webhook`, `sftp`), `status` (`queued`, `processing`, `completed`, `partially_delivered`, `failed`), `recipient_count`, `delivered_count`, `failed_count`, `execution_duration_ms`, `generated_file_name`, `file_size_bytes`, `burst_slicing_metadata` (JSONField), `error_summary`, `executed_by` (FK `auth.User`), `started_at`, `completed_at`.
   - Constraints & Indexes: unique on `(tenant, number)`, indexes on `(tenant, run_trigger)`, `(tenant, status)`, `(tenant, started_at)`.
   - Properties: `success_rate`, `status_badge_class`, `channel_badge_class`.
   - Methods: `mark_completed(...)`, `mark_failed(...)`.

4. **`BiNotificationItem`** (`apps/bi/models/AlertsSubscriptions/BiNotificationItems.py`)
   - Table: `bi_notification_item`, Prefix: `BNTF` (`TenantNumbered`).
   - Fields: `recipient` (FK `auth.User`), `title`, `message`, `severity` (`critical`, `warning`, `info`, `low`), `category` (`kpi_alert`, `statistical_anomaly`, `subscription_digest`, `workflow_trigger`, `system_event`), `alert_rule` (FK `BiAlertRule`), `burst_run` (FK `DistributionBurstRun`), `action_url` (CharField relative/http), `status` (`unread`, `read`, `acknowledged`, `snoozed`, `escalated`, `dismissed`), `read_at`, `acknowledged_at`, `acknowledged_by` (FK `auth.User`), `acknowledgment_notes`, `snoozed_until`, `escalation_level` (SmallIntegerField 0-3), `escalated_to` (FK `auth.User`), `workflow_converted` (bool), `workflow_reference`.
   - Constraints & Indexes: unique on `(tenant, number)`, composite index on `(tenant, created_at)` (`idx_bntf_ten_created`), indexes on `(tenant, recipient, status)`, `(tenant, severity)`, `(tenant, category)`.
   - Properties: `severity_badge_class`, `status_badge_class`, `category_badge_class`, `is_snoozed_active`.
   - Methods: `mark_read()`, `acknowledge(user, notes)`, `snooze(until_dt)`, `escalate(user)`.

### URLs & Routes
- Master Command Center / Workspace: `bi:notification_center` (`/bi/notifications/center/`)
- Alert Rules:
  - `bi:bi_alert_rule_list` / `bi:alert_rule_list` (`/bi/alerts/`)
  - `bi:bi_alert_rule_create` / `bi:alert_rule_create` (`/bi/alerts/create/`)
  - `bi:bi_alert_rule_detail` / `bi:alert_rule_detail` (`/bi/alerts/<int:pk>/`)
  - `bi:bi_alert_rule_edit` / `bi:alert_rule_edit` (`/bi/alerts/<int:pk>/edit/`)
  - `bi:bi_alert_rule_delete` / `bi:alert_rule_delete` (`/bi/alerts/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:bi_alert_rule_test_evaluate` / `bi:alert_rule_test_evaluate` (`/bi/alerts/<int:pk>/evaluate/` - `@require_POST`)
- Report Subscriptions:
  - `bi:report_subscription_list` (`/bi/subscriptions/`)
  - `bi:report_subscription_create` (`/bi/subscriptions/create/`)
  - `bi:report_subscription_detail` (`/bi/subscriptions/<int:pk>/`)
  - `bi:report_subscription_edit` (`/bi/subscriptions/<int:pk>/edit/`)
  - `bi:report_subscription_delete` (`/bi/subscriptions/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:report_subscription_run_now` (`/bi/subscriptions/<int:pk>/run-now/` - `@require_POST`)
- Distribution Burst Runs:
  - `bi:distribution_burst_run_list` (`/bi/burst-runs/`)
  - `bi:distribution_burst_run_create` (`/bi/burst-runs/create/`)
  - `bi:distribution_burst_run_detail` (`/bi/burst-runs/<int:pk>/`)
  - `bi:distribution_burst_run_edit` (`/bi/burst-runs/<int:pk>/edit/`)
  - `bi:distribution_burst_run_delete` (`/bi/burst-runs/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
- Notifications:
  - `bi:bi_notification_item_list` / `bi:notification_item_list` (`/bi/notifications/`)
  - `bi:bi_notification_item_create` / `bi:notification_item_create` (`/bi/notifications/create/`)
  - `bi:bi_notification_item_detail` / `bi:notification_item_detail` (`/bi/notifications/<int:pk>/` - auto-marks read)
  - `bi:bi_notification_item_edit` / `bi:notification_item_edit` (`/bi/notifications/<int:pk>/edit/`)
  - `bi:bi_notification_item_delete` / `bi:notification_item_delete` (`/bi/notifications/<int:pk>/delete/` - `@require_POST`)
  - `bi:notification_mark_read` (`/bi/notifications/<int:pk>/mark-read/` - `@require_POST`)
  - `bi:notification_acknowledge` (`/bi/notifications/<int:pk>/acknowledge/` - `@require_POST`)
  - `bi:notification_snooze` (`/bi/notifications/<int:pk>/snooze/` - `@require_POST`)
  - `bi:notification_escalate` (`/bi/notifications/<int:pk>/escalate/` - `@require_POST`)

### Templates & Design Patterns
- Templates reside in `templates/bi/alerts_subscriptions/`:
  - `bi_alert_rule/` (`list.html`, `detail.html`, `form.html`).
  - `report_subscription/` (`list.html`, `detail.html`, `form.html`).
  - `distribution_burst_run/` (`list.html`, `detail.html`, `form.html`).
  - `bi_notification_item/` (`list.html`, `detail.html`, `form.html`).
  - `notification_center.html` (interactive operational triage workspace with status filter tabs, inline quick actions, and critical counters).
- Design system: Colour-named badge modifiers (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`), stat-card icons (`blue`, `green`, `orange`, `purple`), accessible `<table class="table">` in `.table-wrap`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Alerts, Subscriptions & Distribution demo records:
  - Alert Rules: Operating Margin Threshold Alert (`BALR-00001`), Freight Cost Spike Anomaly (`BALR-00002`).
  - Report Subscriptions: Weekly Executive KPI Digest (`BSUB-00001`), Monthly Financial Statements Pack (`BSUB-00002`).
  - Distribution Burst Runs: Scheduled Monday Morning Burst (`BBRS-00001`), Ad-hoc Board Pack Burst (`BBRS-00002`).
  - Notification Items: Revenue Target Breach Incident (`BNTF-00001`), Freight Anomaly Warning (`BNTF-00002`).
- 100% idempotent with `--flush` cleanup across all 10.16 tables.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Role-Based Authorization**: `@tenant_admin_required` strictly enforced on all delete views (`bi_alert_rule_delete`, `report_subscription_delete`, `distribution_burst_run_delete`).
- **Open Redirect Protection**: `_safe_redirect()` uses `url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()})` on post-action transitions.
- **Stored XSS Prevention**: `clean_action_url()` validates relative `/` or `http://`/`https://` paths and strictly rejects `javascript:`, `data:`, `vbscript:`.
- **Numeric Input Hardening (Lesson L35)**: Hand-parsed snooze `hours` input is validated within allowed range `(1, 4, 24, 72)` with error fallback.
- **Sidebar Wiring**: Registered in `apps/core/navigation.py` under `LIVE_LINKS["10.16"]`.

---

## Sub-module 10.17: Embedded & Mobile BI

Comprehensive embedded analytics, mobile business intelligence (PWA / offline-ready / touch-optimized), developer APIs & SDKs, kiosk/wallboard display modes, and SSO row-level context passthrough.

### Models
1. **`EmbeddedAnalyticsConfig`** (`apps/bi/models/EmbeddedMobileBi/EmbeddedAnalyticsConfigs.py`)
   - Table: `bi_embedded_analytics_config`, Prefix: `EMB` (`TenantNumbered`).
   - Fields: `name`, `slug`, `target_type` (`dashboard`, `report`, `semantic_model`), `dashboard` (FK `BiDashboard`), `report` (FK `ReportDefinition`), `semantic_model` (FK `SemanticModel`), `embedding_mode` (`iframe`, `web_component`, `sdk_react`, `headless_api`), `auth_mode` (`signed_jwt`, `sso_saml_oidc`, `anonymous_public`, `api_key`), `allowed_origins` (CharField comma-separated domains/origins), `theme_mode` (`light`, `dark`, `auto_system`, `custom`), `primary_color` (hex regex validated), `accent_color` (hex regex validated), `custom_css` (sanitized against XSS), `enable_rls_filter` (bool), `default_rls_attributes` (JSON dict), `view_count` (PositiveIntegerField), `last_accessed_at` (DateTimeField), `status` (`active`, `draft`, `disabled`, `deprecated`).
   - Constraints & Indexes: unique on `(tenant, number)`, `(tenant, slug)`, indexes on `(tenant, status)`, `(tenant, target_type)`.
   - Properties: `target_name`, `status_badge_color`, `mode_badge_color`, `auth_mode_badge_color`.

2. **`KioskWallboardDisplay`** (`apps/bi/models/EmbeddedMobileBi/KioskWallboardDisplays.py`)
   - Table: `bi_kiosk_wallboard_display`, Prefix: `WALL` (`TenantNumbered`).
   - Fields: `name`, `slug`, `location_description`, `playlist_items` (JSON list of slides), `default_slide_duration_seconds` (integer), `transition_effect` (`fade`, `slide_horizontal`, `slide_vertical`, `instant`, `zoom`), `theme` (`dark_navy`, `dark_oled`, `light`, `high_contrast`), `display_schedule` (`continuous_24_7`, `business_hours`, `weekdays_only`, `custom`), `operating_hours_json` (JSON dict), `auto_refresh_data_interval_seconds` (integer), `is_public_kiosk` (bool), `access_passcode` (CharField), `last_heartbeat_at` (DateTimeField), `device_ip_address` (GenericIPAddressField), `device_user_agent` (CharField), `status` (`active`, `standby`, `maintenance`, `offline`).
   - Constraints & Indexes: unique on `(tenant, number)`, `(tenant, slug)`, indexes on `(tenant, status)`, composite index `idx_wall_ten_schedule` on `(tenant, display_schedule)`.
   - Methods: `verify_passcode(passcode)` using `secrets.compare_digest`, `record_heartbeat(ip, user_agent)`.

3. **`MobileBiConfiguration`** (`apps/bi/models/EmbeddedMobileBi/MobileBiConfigurations.py`)
   - Table: `bi_mobile_bi_configuration`, Prefix: `MOB` (`TenantNumbered`).
   - Fields: `name`, `slug`, `target_user` (FK `auth.User`, null=True), `is_default_profile` (bool, enforced single default per tenant in `save()`), `touch_layout_preset` (`comfortable`, `compact`, `dense_grid`, `card_deck`), `push_digest_frequency` (`daily_morning`, `daily_evening`, `weekly_monday`, `disabled`), `offline_caching_enabled` (bool), `cache_max_age_hours` (integer), `max_cache_storage_mb` (integer), `pinned_dashboard_ids` (JSON list of IDs, validated in form clean), `pinned_report_ids` (JSON list of IDs, validated in form clean), `require_biometric_lock` (bool), `inactivity_lock_minutes` (integer), `last_synced_at` (DateTimeField), `status` (`active`, `draft`, `disabled`).
   - Constraints & Indexes: unique on `(tenant, number)`, `(tenant, slug)`, composite indexes `idx_mob_ten_preset` on `(tenant, touch_layout_preset)` and `idx_mob_ten_digest` on `(tenant, push_digest_frequency)`.
   - Invariant: `__str__` inspects `_state.fields_cache` before dereferencing `target_user` to avoid N+1 queries (Lesson L18).

4. **`EmbedApiToken`** (`apps/bi/models/EmbeddedMobileBi/EmbedApiTokens.py`)
   - Table: `bi_embed_api_token`, Prefix: `EAPI` (`TenantNumbered`).
   - Fields: `name`, `embedded_config` (FK `EmbeddedAnalyticsConfig`), `token_prefix` (e.g. `eapi_live_`), `token_hash` (SHA-256 hex string, secret never stored in plaintext), `scopes` (JSON list), `allowed_ip_ranges` (TextField), `rate_limit_rpm` (PositiveIntegerField), `expires_at` (DateTimeField, nullable), `total_requests_count` (PositiveIntegerField), `last_used_at` (DateTimeField), `injected_rls_context` (JSON dict), `status` (`active`, `revoked`, `expired`).
   - Constraints & Indexes: unique on `(tenant, number)`.
   - Methods: `verify_token(raw_token)` constant-time comparison, `revoke(revoked_by=None)`.
   - Lifecycle: Generated via `generate_secret()`, revealed exactly once on create via session pop (`request.session.pop('_new_token_key')`), excluded from ModelForm.

### URLs & Routes
All routes under `bi:` namespace:
- **Embedded Analytics Configurations**:
  - `bi:embedded_analytics_config_list` (`/bi/embedded-configs/`)
  - `bi:embedded_analytics_config_create` (`/bi/embedded-configs/create/` - `@tenant_admin_required`)
  - `bi:embedded_analytics_config_detail` (`/bi/embedded-configs/<int:pk>/`)
  - `bi:embedded_analytics_config_edit` (`/bi/embedded-configs/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:embedded_analytics_config_delete` (`/bi/embedded-configs/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:embedded_analytics_config_preview` (`/bi/embedded-configs/<int:pk>/preview/` - Atomic `F("view_count") + 1` increment)
- **Kiosk & Wallboard Displays**:
  - `bi:kiosk_wallboard_display_list` (`/bi/kiosk-displays/`)
  - `bi:kiosk_wallboard_display_create` (`/bi/kiosk-displays/create/` - `@tenant_admin_required`)
  - `bi:kiosk_wallboard_display_detail` (`/bi/kiosk-displays/<int:pk>/`)
  - `bi:kiosk_wallboard_display_edit` (`/bi/kiosk-displays/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:kiosk_wallboard_display_delete` (`/bi/kiosk-displays/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:kiosk_wallboard_display_player` (`/bi/kiosk-displays/<int:pk>/player/` - Standalone kiosk player, constant-time passcode check, superuser support)
  - `bi:kiosk_wallboard_display_heartbeat` (`/bi/kiosk-displays/<int:pk>/heartbeat/` - `@require_POST`, atomic update, returns fresh timestamp)
- **Mobile BI App Configurations**:
  - `bi:mobile_bi_config_list` (`/bi/mobile-configs/`)
  - `bi:mobile_bi_config_create` (`/bi/mobile-configs/create/` - `@tenant_admin_required`)
  - `bi:mobile_bi_config_detail` (`/bi/mobile-configs/<int:pk>/`)
  - `bi:mobile_bi_config_edit` (`/bi/mobile-configs/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:mobile_bi_config_delete` (`/bi/mobile-configs/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
- **Developer APIs & Embed Tokens**:
  - `bi:embed_api_token_list` (`/bi/api-tokens/`)
  - `bi:embed_api_token_create` (`/bi/api-tokens/create/` - `@tenant_admin_required`, session pop secret reveal)
  - `bi:embed_api_token_detail` (`/bi/api-tokens/<int:pk>/` - Snippets and masked token display)
  - `bi:embed_api_token_edit` (`/bi/api-tokens/<int:pk>/edit/` - `@tenant_admin_required`)
  - `bi:embed_api_token_delete` (`/bi/api-tokens/<int:pk>/delete/` - `@tenant_admin_required`, `@require_POST`)
  - `bi:embed_api_token_revoke` (`/bi/api-tokens/<int:pk>/revoke/` - `@tenant_admin_required`, `@require_POST`)

### Templates & Design Patterns
- Templates reside in `templates/bi/embedded_mobile_bi/`:
  - `embeddedanalyticsconfig/` (`list.html`, `detail.html`, `form.html`, `preview.html` with sandboxed custom CSS).
  - `kioskwallboarddisplay/` (`list.html`, `detail.html`, `form.html`, `player.html` with safe `json_script` playlist and auto-rotation).
  - `mobilebiconfiguration/` (`list.html`, `detail.html`, `form.html`).
  - `embedapitoken/` (`list.html`, `detail.html`, `form.html` with one-time copy banner).
- Design system: Colour-named badge modifiers (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`), stat-card icons (`blue`, `green`, `orange`, `purple`), accessible `<table class="table">` in `.table-wrap`.

### Seeder Details
- `manage.py seed_bi` seeds multi-tenant Embedded & Mobile BI demo records:
  - Embedded Analytics Configs: Executive Revenue Embed (iframe), Vendor Logistics Portal (web component).
  - Kiosk Wallboard Displays: HQ Operations Wallboard (dark OLED), Frankfurt Depot Kiosk (light).
  - Mobile BI Configurations: Executive Mobile Profile, Globex Field Rep Mobile with touch presets and pinned assets.
  - Embed API Tokens: Production SDK Key, Globex Read Token with SHA-256 hashing.
- Idempotent and safe to run repeatedly.

### Key Conventions & Security Invariants
- **Multi-Tenant Isolation**: Scoped by `tenant=request.tenant` via `bi_scope()` and `bi_object()`. All foreign keys in forms validated with `reject_foreign`.
- **Role-Based Authorization**: `@tenant_admin_required` strictly enforced on all create, edit, delete, and revoke views.
- **Lesson L10 Guarding**: All detail templates guard author badge with `{% if obj.created_by %}{{ obj.created_by.get_full_name|default:obj.created_by.username }}{% else %}System{% endif %}`.
- **Lesson L20 & L25 Secret Handling**: Tokens generated with 192-bit cryptographic entropy, SHA-256 hashed in DB, excluded from ModelForm, and popped once from session.
- **Constant-Time Passcode Verification**: Wallboard player and heartbeat verify passcodes via `secrets.compare_digest`.
- **Stored XSS Prevention**: `custom_css` stripped/rejected of `<style>` and `<script>`, playlist JSON interpolated safely via `json_script`.
- **Sidebar Wiring**: Registered in `apps/core/navigation.py` under `LIVE_LINKS["10.17"]`.

