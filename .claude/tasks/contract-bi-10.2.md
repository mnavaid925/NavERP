# Contract — Sub-module 10.2: ETL/ELT & Data Pipelines (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.2 ETL/ELT & Data Pipelines · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-03 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1). Incremental migration: `0004_...`
- **Package Layout:** `EtlPipelines/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/etl_pipelines/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `EtlPipeline` (`apps/bi/models/EtlPipelines/EtlPipelines.py`)
- **Table:** `bi_etl_pipeline`
- **Number Prefix:** `BETL` (`BETL-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('draft', 'Draft / Configuring'), ('active', 'Active / Ready'), ('paused', 'Paused / Inactive'), ('deprecated', 'Deprecated'), ('error', 'Execution Error')]`
  - `TRIGGER_TYPE_CHOICES = [('manual', 'Manual Trigger Only'), ('scheduled_cron', 'Scheduled Cron / Time Window'), ('event_on_ingest', 'Event-Driven (On Ingestion Completion)'), ('dependency_chained', 'Dependency Chained (DAG Trigger)')]`
  - `TARGET_LAYER_CHOICES = [('staging', 'Raw / Staging Buffer'), ('warehouse_fact', 'Enterprise Warehouse Fact Table'), ('warehouse_dim', 'Enterprise Warehouse Dimension Table'), ('data_mart', 'Subject-Specific Data Mart')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150, help_text="Descriptive ETL/ELT pipeline name")`
  - `description`: `TextField(blank=True)`
  - `source_ingestion_pipeline`: `ForeignKey('bi.IngestionPipeline', on_delete=SET_NULL, null=True, blank=True, related_name='downstream_etl_pipelines', help_text="Upstream ingestion pipeline producing staging data")`
  - `source_staging_table`: `CharField(max_length=150, help_text="Source staging dataset or table, e.g. stg_accounting_invoices")`
  - `target_table`: `CharField(max_length=150, help_text="Target analytical table or mart table")`
  - `target_layer`: `CharField(max_length=30, choices=TARGET_LAYER_CHOICES, default='warehouse_fact')`
  - `trigger_type`: `CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES, default='scheduled_cron')`
  - `cron_expression`: `CharField(max_length=60, blank=True, help_text="Cron expression for scheduled executions, e.g. 0 2 * * *")`
  - `upstream_dependencies`: `JSONField(default=list, blank=True, help_text="List of upstream BETL pipeline numbers or IDs required before trigger")`
  - `retry_policy`: `JSONField(default=dict, blank=True, help_text="Configurable retry rules: max_retries, retry_delay_seconds, backoff_factor")`
  - `sla_timeout_seconds`: `PositiveIntegerField(default=3600, help_text="Maximum allowed runtime in seconds before SLA breach is flagged")`
  - `alert_on_sla_miss`: `BooleanField(default=True, help_text="Dispatch system alert when SLA runtime threshold is breached")`
  - `alert_rule`: `ForeignKey('core.AlertRule', on_delete=SET_NULL, null=True, blank=True, related_name='bi_etl_pipelines', help_text="Linked observability alert policy")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `canvas_layout`: `JSONField(default=dict, blank=True, help_text="Visual pipeline designer node coordinates and layout metadata")`
  - `active_version`: `ForeignKey('bi.EtlPipelineVersion', on_delete=SET_NULL, null=True, blank=True, related_name='+', help_text="Currently published active DAG version")`
  - `last_run_at`: `DateTimeField(null=True, blank=True)`
  - `next_run_due_at`: `DateTimeField(null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='bi_etl_pipelines_created')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_betl_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status', 'trigger_type'], name='idx_betl_ten_stat_trig')`
  - `Index(fields=['tenant', 'target_layer'], name='idx_betl_ten_tgt_layer')`
  - `Index(fields=['tenant', 'name'], name='idx_betl_ten_name')`

---

### 1.2 `TransformationStep` (`apps/bi/models/EtlPipelines/TransformationSteps.py`)
- **Table:** `bi_transformation_step`
- **Number Prefix:** `BTRN` (`BTRN-00001`)
- **CHOICES:**
  - `STEP_TYPE_CHOICES = [('join', 'Relational Join (Inner/Left/Right/Full/Cross)'), ('aggregate', 'Grouped Aggregation (Sum/Avg/Count/Min/Max)'), ('pivot', 'Matrix Pivot (Rows to Columns)'), ('unpivot', 'Matrix Unpivot (Columns to Rows)'), ('cast', 'Type Casting & Schema Sanitization'), ('filter', 'Row Filter & Conditional Split'), ('derived_column', 'Derived Calculated Expression'), ('lookup_enrichment', 'Master Data Lookup Enrichment'), ('deduplicate', 'Row Deduplication & Distinct'), ('business_rule', 'Reusable ERP Business Rule Transform')]`
  - `STATUS_CHOICES = [('active', 'Active / Enabled'), ('disabled', 'Disabled / Skipped'), ('draft', 'Draft / Configuring')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `pipeline`: `ForeignKey('bi.EtlPipeline', on_delete=CASCADE, related_name='steps')`
  - `name`: `CharField(max_length=150, help_text="Transform step label or operation name")`
  - `step_type`: `CharField(max_length=30, choices=STEP_TYPE_CHOICES, default='derived_column')`
  - `sequence`: `PositiveIntegerField(default=1, help_text="Topological execution order sequence within DAG")`
  - `upstream_step_ids`: `JSONField(default=list, blank=True, help_text="List of prerequisite step numbers/IDs feeding input into this node")`
  - `step_config`: `JSONField(default=dict, blank=True, help_text="Detailed transform specifications: join keys, aggregation metrics, formulas, cast rules")`
  - `mapping_template`: `ForeignKey('core.MappingTemplate', on_delete=SET_NULL, null=True, blank=True, related_name='etl_transformation_steps')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `is_blocking`: `BooleanField(default=True, help_text="If True, step failure halts entire pipeline execution")`
  - `canvas_x`: `IntegerField(default=100, help_text="X-coordinate on visual DAG canvas")`
  - `canvas_y`: `IntegerField(default=100, help_text="Y-coordinate on visual DAG canvas")`
  - `description`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_btrn_tenant_num_uniq')`
  - `Index(fields=['tenant', 'pipeline', 'sequence'], name='idx_btrn_ten_pipe_seq')`
  - `Index(fields=['tenant', 'step_type', 'status'], name='idx_btrn_ten_type_stat')`

---

### 1.3 `EtlPipelineVersion` (`apps/bi/models/EtlPipelines/EtlPipelineVersions.py`)
- **Table:** `bi_etl_pipeline_version`
- **Number Prefix:** `BPVR` (`BPVR-00001`)
- **CHOICES:**
  - `ENVIRONMENT_CHOICES = [('development', 'Development (Dev Sandbox)'), ('staging', 'Staging / Pre-Production (QA)'), ('production', 'Production (Live Analytical DWH)')]`
  - `STATUS_CHOICES = [('draft', 'Draft Version'), ('published', 'Published / Active'), ('archived', 'Archived / Historical'), ('rolled_back', 'Rolled Back')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `pipeline`: `ForeignKey('bi.EtlPipeline', on_delete=CASCADE, related_name='versions')`
  - `version_number`: `CharField(max_length=20, default='v1.0.0', help_text="Semantic version string, e.g. v1.0.0, v1.1.0")`
  - `environment`: `CharField(max_length=25, choices=ENVIRONMENT_CHOICES, default='development')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `environment_instance`: `ForeignKey('core.EnvironmentInstance', on_delete=SET_NULL, null=True, blank=True, related_name='etl_pipeline_versions')`
  - `dag_definition`: `JSONField(default=dict, blank=True, help_text="Full declarative JSON snapshot of pipeline configuration and transformation steps")`
  - `changelog`: `TextField(blank=True, help_text="Release notes, schema changes, and transformation modifications")`
  - `rollback_source`: `ForeignKey('self', on_delete=SET_NULL, null=True, blank=True, related_name='rolled_back_versions', help_text="Prior version restored by this rollback")`
  - `promoted_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='etl_promotions')`
  - `promoted_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bpvr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'pipeline', 'environment'], name='idx_bpvr_ten_pipe_env')`
  - `Index(fields=['tenant', 'status'], name='idx_bpvr_ten_stat')`

---

### 1.4 `EtlPipelineRun` (`apps/bi/models/EtlPipelines/EtlPipelineRuns.py`)
- **Table:** `bi_etl_pipeline_run`
- **Number Prefix:** `BEXR` (`BEXR-00001`)
- **CHOICES:**
  - `TRIGGER_TYPE_CHOICES = [('manual', 'Manual User Trigger'), ('scheduled', 'Automated Scheduled Cadence'), ('event_upstream', 'Upstream Ingestion Event'), ('backfill', 'Historical Partition Backfill')]`
  - `STATUS_CHOICES = [('pending', 'Pending / Enqueued'), ('queued', 'Queued in Work Pool'), ('running', 'Running Transformations'), ('completed', 'Completed Successfully'), ('warning', 'Completed with Non-Fatal Warnings'), ('failed', 'Execution Failed'), ('cancelled', 'Cancelled by User'), ('timed_out', 'Timed Out (SLA Breached)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `pipeline`: `ForeignKey('bi.EtlPipeline', on_delete=CASCADE, related_name='runs')`
  - `version`: `ForeignKey('bi.EtlPipelineVersion', on_delete=SET_NULL, null=True, blank=True, related_name='runs')`
  - `trigger_type`: `CharField(max_length=25, choices=TRIGGER_TYPE_CHOICES, default='manual')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='pending')`
  - `started_at`: `DateTimeField(default=timezone.now)`
  - `ended_at`: `DateTimeField(null=True, blank=True)`
  - `duration_seconds`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))`
  - `records_in`: `PositiveIntegerField(default=0, help_text="Total source staging records extracted")`
  - `records_transformed`: `PositiveIntegerField(default=0, help_text="Records successfully processed through transformations")`
  - `records_out`: `PositiveIntegerField(default=0, help_text="Records successfully written to target table")`
  - `records_rejected`: `PositiveIntegerField(default=0, help_text="Records failing filters, joins, or type assertions")`
  - `bytes_processed`: `BigIntegerField(default=0, help_text="Total data volume processed in bytes")`
  - `sla_missed`: `BooleanField(default=False, help_text="Flagged True if duration exceeded pipeline SLA threshold")`
  - `is_backfill`: `BooleanField(default=False, help_text="True if run executes a historical partition backfill")`
  - `backfill_range_start`: `DateTimeField(null=True, blank=True)`
  - `backfill_range_end`: `DateTimeField(null=True, blank=True)`
  - `retry_count`: `PositiveIntegerField(default=0)`
  - `step_progress`: `JSONField(default=dict, blank=True, help_text="Dictionary of step execution progress, status, and row counts")`
  - `error_message`: `TextField(blank=True)`
  - `execution_log`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bexr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'pipeline', 'started_at'], name='idx_bexr_ten_pipe_start')`
  - `Index(fields=['tenant', 'status', 'started_at'], name='idx_bexr_ten_stat_start')`

---

## 2. Forms Contract & Exclusions

All forms inherit from `apps.bi.forms._common.BiModelForm` (with Tailwind CSS widgets).

### 2.1 `EtlPipelineForm`
- **Model:** `EtlPipeline`
- **Fields:** `['name', 'description', 'source_ingestion_pipeline', 'source_staging_table', 'target_table', 'target_layer', 'trigger_type', 'cron_expression', 'upstream_dependencies', 'retry_policy', 'sla_timeout_seconds', 'alert_on_sla_miss', 'alert_rule', 'status']`
- **Excluded:** `tenant`, `number`, `created_at`, `updated_at`, `canvas_layout`, `active_version`, `last_run_at`, `next_run_due_at`, `created_by`

### 2.2 `TransformationStepForm`
- **Model:** `TransformationStep`
- **Fields:** `['pipeline', 'name', 'step_type', 'sequence', 'upstream_step_ids', 'step_config', 'mapping_template', 'status', 'is_blocking', 'description']`
- **Excluded:** `tenant`, `number`, `created_at`, `updated_at`, `canvas_x`, `canvas_y`

### 2.3 `EtlPipelineVersionForm`
- **Model:** `EtlPipelineVersion`
- **Fields:** `['pipeline', 'version_number', 'environment', 'environment_instance', 'status', 'changelog']`
- **Excluded:** `tenant`, `number`, `created_at`, `updated_at`, `dag_definition`, `rollback_source`, `promoted_by`, `promoted_at`

### 2.4 `EtlPipelineRunForm`
- **Model:** `EtlPipelineRun`
- **Fields:** `['pipeline', 'version', 'trigger_type', 'is_backfill', 'backfill_range_start', 'backfill_range_end']`
- **Excluded:** `tenant`, `number`, `created_at`, `status`, `started_at`, `ended_at`, `duration_seconds`, `records_in`, `records_transformed`, `records_out`, `records_rejected`, `bytes_processed`, `sla_missed`, `retry_count`, `step_progress`, `error_message`, `execution_log`

---

## 3. URLs & Routing Contract

App namespace: `bi`
Routes defined in `apps/bi/urls/EtlPipelines/*.py` and registered in `apps/bi/urls/__init__.py`:

| URL Pattern | Name | View Function |
|---|---|---|
| `etl-pipelines/` | `etl_pipeline_list` | `etl_pipeline_list` |
| `etl-pipelines/create/` | `etl_pipeline_create` | `etl_pipeline_create` |
| `etl-pipelines/<int:pk>/` | `etl_pipeline_detail` | `etl_pipeline_detail` |
| `etl-pipelines/<int:pk>/edit/` | `etl_pipeline_edit` | `etl_pipeline_edit` |
| `etl-pipelines/<int:pk>/delete/` | `etl_pipeline_delete` | `etl_pipeline_delete` |
| `etl-pipelines/<int:pk>/canvas/` | `etl_pipeline_canvas` | `etl_pipeline_canvas` |
| `etl-pipelines/<int:pk>/trigger/` | `etl_pipeline_trigger` | `etl_pipeline_trigger` |
| `transformation-steps/` | `transformation_step_list` | `transformation_step_list` |
| `transformation-steps/create/` | `transformation_step_create` | `transformation_step_create` |
| `transformation-steps/<int:pk>/` | `transformation_step_detail` | `transformation_step_detail` |
| `transformation-steps/<int:pk>/edit/` | `transformation_step_edit` | `transformation_step_edit` |
| `transformation-steps/<int:pk>/delete/` | `transformation_step_delete` | `transformation_step_delete` |
| `pipeline-versions/` | `etl_pipeline_version_list` | `etl_pipeline_version_list` |
| `pipeline-versions/create/` | `etl_pipeline_version_create` | `etl_pipeline_version_create` |
| `pipeline-versions/<int:pk>/` | `etl_pipeline_version_detail` | `etl_pipeline_version_detail` |
| `pipeline-versions/<int:pk>/edit/` | `etl_pipeline_version_edit` | `etl_pipeline_version_edit` |
| `pipeline-versions/<int:pk>/delete/` | `etl_pipeline_version_delete` | `etl_pipeline_version_delete` |
| `pipeline-versions/<int:pk>/promote/` | `etl_pipeline_version_promote` | `etl_pipeline_version_promote` |
| `etl-runs/` | `etl_pipeline_run_list` | `etl_pipeline_run_list` |
| `etl-runs/<int:pk>/` | `etl_pipeline_run_detail` | `etl_pipeline_run_detail` |

---

## 4. View Context Keys Contract

### 4.1 `etl_pipeline_list` (`templates/bi/etl_pipelines/etl_pipeline/list.html`)
- `pipelines`: Page queryset of `EtlPipeline`
- `paginator`, `page_obj`: Pagination objects
- `status_choices`: `EtlPipeline.STATUS_CHOICES`
- `trigger_type_choices`: `EtlPipeline.TRIGGER_TYPE_CHOICES`
- `target_layer_choices`: `EtlPipeline.TARGET_LAYER_CHOICES`
- `q`: Search query string
- `status_filter`: Filter GET param
- `trigger_filter`: Filter GET param
- `target_layer_filter`: Filter GET param
- `total_count`, `active_count`, `running_count`: Dashboard metrics

### 4.2 `etl_pipeline_detail` (`templates/bi/etl_pipelines/etl_pipeline/detail.html`)
- `pipeline`: Single `EtlPipeline` instance
- `steps`: QuerySet of child `TransformationStep`
- `versions`: QuerySet of child `EtlPipelineVersion`
- `recent_runs`: QuerySet of recent `EtlPipelineRun`
- `active_version`: Linked active version if any

### 4.3 `etl_pipeline_canvas` (`templates/bi/etl_pipelines/etl_pipeline/canvas.html`)
- `pipeline`: Single `EtlPipeline` instance
- `steps`: QuerySet of child `TransformationStep`
- `step_type_choices`: `TransformationStep.STEP_TYPE_CHOICES`
- `available_sources`: Staging sources from `IngestionPipeline`

### 4.4 `transformation_step_list` (`templates/bi/etl_pipelines/transformation_step/list.html`)
- `steps`: Page queryset of `TransformationStep`
- `paginator`, `page_obj`: Pagination objects
- `step_type_choices`: `TransformationStep.STEP_TYPE_CHOICES`
- `status_choices`: `TransformationStep.STATUS_CHOICES`
- `pipelines`: Tenant-scoped `EtlPipeline` queryset for dropdown filter
- `q`: Search query string
- `step_type_filter`, `status_filter`, `pipeline_filter`: Filter GET params
- `total_count`: Total steps count

### 4.5 `etl_pipeline_version_list` (`templates/bi/etl_pipelines/etl_pipeline_version/list.html`)
- `versions`: Page queryset of `EtlPipelineVersion`
- `paginator`, `page_obj`: Pagination objects
- `environment_choices`: `EtlPipelineVersion.ENVIRONMENT_CHOICES`
- `status_choices`: `EtlPipelineVersion.STATUS_CHOICES`
- `pipelines`: Tenant-scoped `EtlPipeline` queryset for dropdown filter
- `q`: Search query string
- `environment_filter`, `status_filter`, `pipeline_filter`: Filter GET params
- `total_count`: Total versions count

### 4.6 `etl_pipeline_run_list` (`templates/bi/etl_pipelines/etl_pipeline_run/list.html`)
- `runs`: Page queryset of `EtlPipelineRun`
- `paginator`, `page_obj`: Pagination objects
- `status_choices`: `EtlPipelineRun.STATUS_CHOICES`
- `trigger_type_choices`: `EtlPipelineRun.TRIGGER_TYPE_CHOICES`
- `pipelines`: Tenant-scoped `EtlPipeline` queryset for dropdown filter
- `q`: Search query string
- `status_filter`, `trigger_filter`, `pipeline_filter`: Filter GET params
- `total_count`, `success_count`, `failed_count`: Run telemetry metrics

---

## 5. Navigation LIVE_LINKS Contract

`apps/core/navigation.py`:
```python
"10.2": {
    "Visual Pipeline Builder": "bi:etl_pipeline_list",
    "Transformation Library": "bi:transformation_step_list",
    "Orchestration & Scheduling": "bi:etl_pipeline_list",
    "Pipeline Monitoring & Logging": "bi:etl_pipeline_run_list",
    "Version Control & CI/CD": "bi:etl_pipeline_version_list",
    "ETL Pipelines": "bi:etl_pipeline_list",
    "Transformation Steps": "bi:transformation_step_list",
    "Pipeline Versions": "bi:etl_pipeline_version_list",
    "Execution Runs": "bi:etl_pipeline_run_list",
}
```
