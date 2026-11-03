# Contract — Sub-module 10.1: Data Integration & Ingestion (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.1 Data Integration & Ingestion · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-03 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Brand-new app `apps/bi/` to be scaffolded. Initial migration: `0001_initial.py`
- **Package Layout:** `DataIntegration/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/data_integration/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `DataSourceConnector` (`apps/bi/models/DataIntegration/DataSourceConnectors.py`)
- **Table:** `bi_data_source_connector`
- **Number Prefix:** `BDSC` (`BDSC-00001`)
- **CHOICES:**
  - `CONNECTOR_TYPE_CHOICES = [('internal_erp', 'NavERP Internal Module'), ('database_rdbms', 'Relational Database (RDBMS)'), ('database_nosql', 'NoSQL / Document Store'), ('cloud_storage', 'Cloud Object Storage (S3/GCS/Azure)'), ('sftp_server', 'SFTP / Secure File Server'), ('rest_api', 'REST API Endpoint'), ('webhook_push', 'Inbound HTTP Webhook'), ('file_upload', 'Manual File Upload Buffer')]`
  - `STATUS_CHOICES = [('active', 'Active / Ready'), ('inactive', 'Inactive / Disabled'), ('testing', 'Testing Connection'), ('error', 'Connection Error')]`
  - `TEST_STATUS_CHOICES = [('untested', 'Untested'), ('success', 'Connection Verified'), ('failed', 'Connection Failed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150, help_text="Source connector identifier name")`
  - `connector_type`: `CharField(max_length=30, choices=CONNECTOR_TYPE_CHOICES, default='internal_erp')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `connection_config`: `JSONField(default=dict, blank=True, help_text="Host, port, database, bucket, sftp_path, query_options")`
  - `credential`: `ForeignKey('core.ApiCredential', on_delete=SET_NULL, null=True, blank=True, related_name='bi_connectors')`
  - `discovered_catalog`: `JSONField(default=dict, blank=True, help_text="Cached list of discovered streams, tables, and column attributes")`
  - `last_tested_at`: `DateTimeField(null=True, blank=True)`
  - `test_status`: `CharField(max_length=20, choices=TEST_STATUS_CHOICES, default='untested')`
  - `test_message`: `CharField(max_length=255, blank=True)`
  - `description`: `TextField(blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='bi_connectors_created')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdsc_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'connector_type'], name='idx_bdsc_ten_stat_type')`
  - `Index(fields=['tenant', 'name'], name='idx_bdsc_ten_name')`

---

### 1.2 `IngestionPipeline` (`apps/bi/models/DataIntegration/IngestionPipelines.py`)
- **Table:** `bi_ingestion_pipeline`
- **Number Prefix:** `BING` (`BING-00001`)
- **CHOICES:**
  - `INGESTION_MODE_CHOICES = [('batch_scheduled', 'Scheduled Batch'), ('micro_batch', 'Micro-Batch (Near-Real-Time)'), ('real_time_webhook', 'Real-Time Webhook Push'), ('manual_on_demand', 'Manual On-Demand Only')]`
  - `SCHEDULE_CADENCE_CHOICES = [('manual', 'Manual Trigger Only'), ('every_15_min', 'Every 15 Minutes'), ('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('custom_cron', 'Custom Cron Expression')]`
  - `FILE_FORMAT_CHOICES = [('none', 'Not Applicable / Database Query'), ('csv', 'CSV (Comma-Separated)'), ('tsv', 'TSV (Tab-Separated)'), ('json', 'JSON Array / Objects'), ('ndjson', 'Newline-Delimited JSON'), ('excel', 'Excel Spreadsheet (.xlsx)'), ('parquet', 'Apache Parquet')]`
  - `STATUS_CHOICES = [('active', 'Active / Scheduled'), ('paused', 'Paused'), ('draft', 'Draft / Configuring'), ('error', 'Execution Error')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150, help_text="Pipeline pipeline label")`
  - `connector`: `ForeignKey('bi.DataSourceConnector', on_delete=PROTECT, related_name='pipelines')`
  - `ingestion_mode`: `CharField(max_length=30, choices=INGESTION_MODE_CHOICES, default='batch_scheduled')`
  - `source_entity`: `CharField(max_length=150, help_text="Source table, collection, API endpoint, or ERP model identifier")`
  - `target_staging_table`: `CharField(max_length=150, help_text="Target analytical staging table, e.g. stg_accounting_invoices")`
  - `schedule_cadence`: `CharField(max_length=30, choices=SCHEDULE_CADENCE_CHOICES, default='daily')`
  - `cron_expression`: `CharField(max_length=60, blank=True)`
  - `file_format`: `CharField(max_length=20, choices=FILE_FORMAT_CHOICES, default='none')`
  - `file_parsing_options`: `JSONField(default=dict, blank=True, help_text="delimiter, quote_char, has_header, skip_rows, encoding, path_pattern")`
  - `webhook_token`: `CharField(max_length=64, blank=True, unique=True, db_index=True, help_text="Unique secret URL slug for inbound webhook ingress")`
  - `webhook_secret`: `CharField(max_length=128, blank=True, help_text="HMAC verification secret or shared token")`
  - `rate_limit_policy`: `ForeignKey('core.RateLimitPolicy', on_delete=SET_NULL, null=True, blank=True, related_name='bi_pipelines')`
  - `mapping_template`: `ForeignKey('core.MappingTemplate', on_delete=SET_NULL, null=True, blank=True, related_name='bi_pipelines')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `last_run_at`: `DateTimeField(null=True, blank=True)`
  - `next_run_due_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bing_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'ingestion_mode'], name='idx_bing_ten_stat_mode')`
  - `Index(fields=['tenant', 'connector'], name='idx_bing_ten_connector')`

---

### 1.3 `CdcSyncConfig` (`apps/bi/models/DataIntegration/CdcSyncConfigs.py`)
- **Table:** `bi_cdc_sync_config`
- **Number Prefix:** `BCDC` (`BCDC-00001`)
- **CHOICES:**
  - `CAPTURE_METHOD_CHOICES = [('log_based', 'Log-Based CDC (WAL / Binlog / Redo)'), ('query_timestamp', 'Query Timestamp Cursor (Modified Date)'), ('query_incrementing_id', 'Query Incrementing Sequence (Auto-Increment / Sequence ID)'), ('full_snapshot', 'Full Snapshot Table Scan')]`
  - `SYNC_MODE_CHOICES = [('full_refresh_overwrite', 'Full Refresh Overwrite'), ('full_refresh_append', 'Full Refresh Append'), ('incremental_append', 'Incremental Append (Change Log)'), ('incremental_deduped', 'Incremental Deduped (Upsert by Primary Key)')]`
  - `SCHEMA_DRIFT_CHOICES = [('auto_propagate', 'Auto-Propagate New Columns'), ('detect_and_warn', 'Detect & Warn (Flag Log)'), ('block_and_pause', 'Block & Pause Pipeline')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `pipeline`: `OneToOneField('bi.IngestionPipeline', on_delete=CASCADE, related_name='cdc_config')`
  - `capture_method`: `CharField(max_length=30, choices=CAPTURE_METHOD_CHOICES, default='query_timestamp')`
  - `sync_mode`: `CharField(max_length=30, choices=SYNC_MODE_CHOICES, default='incremental_deduped')`
  - `primary_key_fields`: `CharField(max_length=150, default='id', help_text="Comma-separated primary key column names")`
  - `cursor_field`: `CharField(max_length=100, blank=True, default='updated_at', help_text="Column used for delta detection, e.g. updated_at or id")`
  - `last_cursor_value`: `CharField(max_length=255, blank=True, help_text="Committed high-water mark value")`
  - `last_checkpoint_at`: `DateTimeField(null=True, blank=True)`
  - `schema_drift_policy`: `CharField(max_length=25, choices=SCHEMA_DRIFT_CHOICES, default='detect_and_warn')`
  - `capture_deletes`: `BooleanField(default=True, help_text="Track source record deletions")`
  - `soft_delete_field`: `CharField(max_length=60, default='is_deleted', blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bcdc_tenant_num_uniq')`
  - `Index(fields=['tenant', 'capture_method', 'sync_mode'], name='idx_bcdc_ten_meth_mode')`

---

### 1.4 `IngestionRun` (`apps/bi/models/DataIntegration/IngestionRuns.py`)
- **Table:** `bi_ingestion_run`
- **Number Prefix:** `BIJR` (`BIJR-00001`)
- **CHOICES:**
  - `TRIGGER_TYPE_CHOICES = [('scheduled', 'Automated Scheduled Cadence'), ('manual', 'Manual User Trigger'), ('webhook', 'Inbound Webhook Event'), ('cdc_stream', 'CDC Log Stream Micro-Batch')]`
  - `STATUS_CHOICES = [('pending', 'Pending / Enqueued'), ('running', 'Running / Ingesting'), ('completed', 'Completed Successfully'), ('warning', 'Completed with Warnings'), ('failed', 'Execution Failed'), ('cancelled', 'Cancelled by User')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `pipeline`: `ForeignKey('bi.IngestionPipeline', on_delete=CASCADE, related_name='runs')`
  - `trigger_type`: `CharField(max_length=25, choices=TRIGGER_TYPE_CHOICES, default='manual')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='pending')`
  - `started_at`: `DateTimeField(default=timezone.now)`
  - `ended_at`: `DateTimeField(null=True, blank=True)`
  - `duration_seconds`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `records_extracted`: `PositiveIntegerField(default=0)`
  - `records_inserted`: `PositiveIntegerField(default=0)`
  - `records_updated`: `PositiveIntegerField(default=0)`
  - `records_rejected`: `PositiveIntegerField(default=0)`
  - `bytes_transferred`: `BigIntegerField(default=0)`
  - `committed_cursor`: `CharField(max_length=255, blank=True)`
  - `error_message`: `CharField(max_length=500, blank=True)`
  - `log_summary`: `TextField(blank=True, help_text="Diagnostic execution log messages")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bijr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'started_at'], name='idx_bijr_ten_stat_start')`
  - `Index(fields=['tenant', 'pipeline', 'started_at'], name='idx_bijr_ten_pipe_start')`

---

## 2. Forms & Exclusions Contract

All forms inherit from `apps.bi.forms._common.BiModelForm` (or `forms.ModelForm`).
Excludes strictly enforced:
- **`DataSourceConnectorForm`**: excludes `tenant`, `number`, `discovered_catalog`, `last_tested_at`, `test_status`, `test_message`, `created_at`, `updated_at`, `created_by`
- **`IngestionPipelineForm`**: excludes `tenant`, `number`, `webhook_token`, `last_run_at`, `next_run_due_at`, `created_at`, `updated_at`
- **`CdcSyncConfigForm`**: excludes `tenant`, `number`, `last_cursor_value`, `last_checkpoint_at`, `created_at`, `updated_at`
- **`IngestionRunForm`**: excludes `tenant`, `number`, `started_at`, `ended_at`, `duration_seconds`, `records_extracted`, `records_inserted`, `records_updated`, `records_rejected`, `bytes_transferred`, `committed_cursor`, `created_at`, `updated_at`

---

## 3. URL Names & Routing Contract (`app_name = 'bi'`)

All routes defined under `apps/bi/urls/`:
- `bi:data_integration_hub` (`bi/`)
- `bi:data_source_connector_list` (`bi/connectors/`)
- `bi:data_source_connector_create` (`bi/connectors/create/`)
- `bi:data_source_connector_detail` (`bi/connectors/<int:pk>/`)
- `bi:data_source_connector_edit` (`bi/connectors/<int:pk>/edit/`)
- `bi:data_source_connector_delete` (`bi/connectors/<int:pk>/delete/`)
- `bi:data_source_connector_test` (`bi/connectors/<int:pk>/test/`)
- `bi:ingestion_pipeline_list` (`bi/pipelines/`)
- `bi:ingestion_pipeline_create` (`bi/pipelines/create/`)
- `bi:ingestion_pipeline_detail` (`bi/pipelines/<int:pk>/`)
- `bi:ingestion_pipeline_edit` (`bi/pipelines/<int:pk>/edit/`)
- `bi:ingestion_pipeline_delete` (`bi/pipelines/<int:pk>/delete/`)
- `bi:ingestion_pipeline_trigger` (`bi/pipelines/<int:pk>/trigger/`)
- `bi:cdc_sync_config_list` (`bi/cdc/`)
- `bi:cdc_sync_config_create` (`bi/cdc/create/`)
- `bi:cdc_sync_config_detail` (`bi/cdc/<int:pk>/`)
- `bi:cdc_sync_config_edit` (`bi/cdc/<int:pk>/edit/`)
- `bi:cdc_sync_config_delete` (`bi/cdc/<int:pk>/delete/`)
- `bi:cdc_sync_config_reset_cursor` (`bi/cdc/<int:pk>/reset-cursor/`)
- `bi:ingestion_run_list` (`bi/runs/`)
- `bi:ingestion_run_detail` (`bi/runs/<int:pk>/`)
- `bi:ingestion_run_delete` (`bi/runs/<int:pk>/delete/`)
- `bi:ingestion_run_retry` (`bi/runs/<int:pk>/retry/`)

---

## 4. View Context Keys Contract (Pinned Variable Names)

Every view must pass exactly these pinned context keys:

### 4.1 `data_source_connector_list`
- `connectors`: Paginator page object
- `q`: Search query string
- `status`: Filter string
- `connector_type`: Filter string
- `status_choices`: `DataSourceConnector.STATUS_CHOICES`
- `type_choices`: `DataSourceConnector.CONNECTOR_TYPE_CHOICES`
- `total_count`: Total record count for tenant

### 4.2 `data_source_connector_detail`
- `connector`: `DataSourceConnector` instance
- `pipelines`: Queryset of pipelines for this connector
- `runs`: Queryset of recent ingestion runs for pipelines under this connector

### 4.3 `data_source_connector_create` / `data_source_connector_edit`
- `form`: `DataSourceConnectorForm`
- `connector`: Instance if edit, else None
- `is_edit`: Boolean

### 4.4 `ingestion_pipeline_list`
- `pipelines`: Paginator page object
- `q`: Search query string
- `status`: Filter string
- `ingestion_mode`: Filter string
- `connector_id`: Filter string
- `status_choices`: `IngestionPipeline.STATUS_CHOICES`
- `mode_choices`: `IngestionPipeline.INGESTION_MODE_CHOICES`
- `connectors`: `DataSourceConnector.objects.filter(tenant=request.tenant)`
- `total_count`: Total record count for tenant

### 4.5 `ingestion_pipeline_detail`
- `pipeline`: `IngestionPipeline` instance
- `cdc_config`: Related `CdcSyncConfig` or None
- `runs`: Queryset of recent runs for this pipeline

### 4.6 `ingestion_pipeline_create` / `ingestion_pipeline_edit`
- `form`: `IngestionPipelineForm`
- `pipeline`: Instance if edit, else None
- `is_edit`: Boolean

### 4.7 `cdc_sync_config_list`
- `cdc_configs`: Paginator page object
- `q`: Search query string
- `capture_method`: Filter string
- `sync_mode`: Filter string
- `method_choices`: `CdcSyncConfig.CAPTURE_METHOD_CHOICES`
- `mode_choices`: `CdcSyncConfig.SYNC_MODE_CHOICES`
- `total_count`: Total record count for tenant

### 4.8 `cdc_sync_config_detail`
- `config`: `CdcSyncConfig` instance
- `pipeline`: `config.pipeline`

### 4.9 `cdc_sync_config_create` / `cdc_sync_config_edit`
- `form`: `CdcSyncConfigForm`
- `config`: Instance if edit, else None
- `is_edit`: Boolean

### 4.10 `ingestion_run_list`
- `runs`: Paginator page object
- `q`: Search query string
- `status`: Filter string
- `trigger_type`: Filter string
- `pipeline_id`: Filter string
- `status_choices`: `IngestionRun.STATUS_CHOICES`
- `trigger_choices`: `IngestionRun.TRIGGER_TYPE_CHOICES`
- `pipelines`: `IngestionPipeline.objects.filter(tenant=request.tenant)`
- `total_count`: Total record count for tenant

### 4.11 `ingestion_run_detail`
- `run`: `IngestionRun` instance
- `pipeline`: `run.pipeline`

### 4.12 `data_integration_hub`
- `total_connectors`: Count
- `active_connectors`: Count
- `total_pipelines`: Count
- `active_pipelines`: Count
- `cdc_streams_count`: Count
- `total_runs`: Count
- `recent_runs`: Queryset
- `active_pipelines_list`: Queryset
- `connectors`: Queryset
