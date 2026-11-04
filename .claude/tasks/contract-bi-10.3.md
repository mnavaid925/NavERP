# Contract — Sub-module 10.3: Data Warehouse & Storage (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.3 Data Warehouse & Storage · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-04 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended in 10.2). Incremental migration: `0007_...`
- **Package Layout:** `DataWarehouse/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/data_warehouse/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `DataMart` (`apps/bi/models/DataWarehouse/DataMarts.py`)
- **Table:** `bi_data_mart`
- **Number Prefix:** `BDMT` (`BDMT-00001`)
- **CHOICES:**
  - `SUBJECT_AREA_CHOICES = [('finance', 'Finance & Accounting'), ('sales', 'Sales & Customer Relationship'), ('hr', 'Human Resources & Workforce'), ('supply_chain', 'Supply Chain & Logistics'), ('procurement', 'Procurement & Purchasing'), ('manufacturing', 'Manufacturing & Production'), ('executive', 'Executive & Cross-Functional')]`
  - `ACCESS_TIER_CHOICES = [('public', 'Public (Tenant-Wide)'), ('department', 'Departmental Only'), ('restricted', 'Restricted / Confidential')]`
  - `CERTIFICATION_STATUS_CHOICES = [('draft', 'Draft / In Development'), ('in_review', 'Under Review & Validation'), ('certified', 'Certified Single Source of Truth'), ('deprecated', 'Deprecated / Sunset Pending')]`
  - `REFRESH_CADENCE_CHOICES = [('real_time', 'Real-Time / Streaming'), ('hourly', 'Hourly Micro-Batch'), ('daily', 'Daily Overnight Batch'), ('weekly', 'Weekly Snapshot'), ('on_demand', 'On-Demand Only')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=50)`
  - `subject_area`: `CharField(max_length=30, choices=SUBJECT_AREA_CHOICES, default='finance')`
  - `org_unit`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='bi_data_marts')`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='bi_data_marts_owned')`
  - `steward`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='bi_data_marts_stewarded')`
  - `access_tier`: `CharField(max_length=25, choices=ACCESS_TIER_CHOICES, default='department')`
  - `certification_status`: `CharField(max_length=25, choices=CERTIFICATION_STATUS_CHOICES, default='draft')`
  - `refresh_cadence`: `CharField(max_length=25, choices=REFRESH_CADENCE_CHOICES, default='daily')`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_bdmt_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdmt_tenant_num_uniq')`
  - `Index(fields=['tenant', 'subject_area'], name='idx_bdmt_ten_subj')`
  - `Index(fields=['tenant', 'certification_status'], name='idx_bdmt_ten_cert')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdmt_ten_active')`

---

### 1.2 `LakehouseZone` (`apps/bi/models/DataWarehouse/LakehouseZones.py`)
- **Table:** `bi_lakehouse_zone`
- **Number Prefix:** `BLHZ` (`BLHZ-00001`)
- **CHOICES:**
  - `ZONE_TYPE_CHOICES = [('bronze', 'Bronze (Raw Ingestion / Append-Only Landing)'), ('silver', 'Silver (Curated / Cleaned / Conformed Master)'), ('gold', 'Gold (Aggregated / Dimensional Star Schemas / Business-Ready)'), ('sandbox', 'Sandbox (Ad-Hoc Exploration / Data Science)')]`
  - `STORAGE_BACKEND_CHOICES = [('internal_db', 'Internal Relational Database'), ('aws_s3', 'Amazon Web Services S3'), ('azure_blob', 'Microsoft Azure Blob / ADLS Gen2'), ('gcs', 'Google Cloud Storage'), ('local_filesystem', 'Local Dedicated Shared Storage')]`
  - `DEFAULT_FORMAT_CHOICES = [('relational_table', 'Relational Table / View'), ('parquet', 'Apache Parquet Columnar File'), ('delta_lake', 'Delta Lake (Delta-Parquet + Log)'), ('iceberg', 'Apache Iceberg Table Format'), ('csv_compressed', 'Compressed CSV / Gzip')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=50)`
  - `zone_type`: `CharField(max_length=25, choices=ZONE_TYPE_CHOICES, default='bronze')`
  - `storage_backend`: `CharField(max_length=30, choices=STORAGE_BACKEND_CHOICES, default='internal_db')`
  - `default_format`: `CharField(max_length=25, choices=DEFAULT_FORMAT_CHOICES, default='relational_table')`
  - `base_uri_path`: `CharField(max_length=500, blank=True)`
  - `is_read_only`: `BooleanField(default=False)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_blhz_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_blhz_tenant_num_uniq')`
  - `Index(fields=['tenant', 'zone_type'], name='idx_blhz_ten_zone')`
  - `Index(fields=['tenant', 'storage_backend'], name='idx_blhz_ten_backend')`
  - `Index(fields=['tenant', 'is_active'], name='idx_blhz_ten_active')`

---

### 1.3 `WarehouseStoragePolicy` (`apps/bi/models/DataWarehouse/WarehouseStoragePolicies.py`)
- **Table:** `bi_warehouse_storage_policy`
- **Number Prefix:** `BWSP` (`BWSP-00001`)
- **CHOICES:**
  - `PARTITION_STRATEGY_CHOICES = [('none', 'None (Unpartitioned Flat Table)'), ('range_time', 'Range / Time-Based (Date/Timestamp)'), ('range_numeric', 'Numeric Range (Integer Buckets)'), ('hash', 'Hash / Slices (Distributed Keys)'), ('list_category', 'List / Categorical (Region/Branch/Status)')]`
  - `PARTITION_GRANULARITY_CHOICES = [('hour', 'Hourly'), ('day', 'Daily'), ('month', 'Monthly'), ('quarter', 'Quarterly'), ('year', 'Yearly')]`
  - `COMPRESSION_CODEC_CHOICES = [('none', 'None (Uncompressed)'), ('snappy', 'Snappy (Fast Decompression)'), ('zstd', 'Zstandard (ZSTD Balanced High Ratio)'), ('lz4', 'LZ4 (Ultra-Low Latency)'), ('gzip', 'Gzip (Maximum Compression Ratio)')]`
  - `VACUUM_CADENCE_CHOICES = [('daily', 'Daily Vacuum & Compaction'), ('weekly', 'Weekly Vacuum & Compaction'), ('monthly', 'Monthly Cleanup'), ('manual', 'Manual Trigger Only')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `partition_strategy`: `CharField(max_length=30, choices=PARTITION_STRATEGY_CHOICES, default='range_time')`
  - `partition_key`: `CharField(max_length=100, blank=True)`
  - `partition_granularity`: `CharField(max_length=25, choices=PARTITION_GRANULARITY_CHOICES, default='month')`
  - `compression_codec`: `CharField(max_length=25, choices=COMPRESSION_CODEC_CHOICES, default='zstd')`
  - `enable_zone_maps`: `BooleanField(default=True)`
  - `hot_tier_days`: `PositiveIntegerField(default=90)`
  - `warm_tier_days`: `PositiveIntegerField(default=365)`
  - `cold_tier_days`: `PositiveIntegerField(default=2555)`
  - `time_travel_days`: `PositiveIntegerField(default=7)`
  - `auto_purge_enabled`: `BooleanField(default=False)`
  - `vacuum_cadence`: `CharField(max_length=25, choices=VACUUM_CADENCE_CHOICES, default='weekly')`
  - `is_default`: `BooleanField(default=False)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bwsp_tenant_num_uniq')`
  - `Index(fields=['tenant', 'partition_strategy'], name='idx_bwsp_ten_part')`
  - `Index(fields=['tenant', 'is_default'], name='idx_bwsp_ten_def')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bwsp_ten_active')`

---

### 1.4 `WarehouseTable` (`apps/bi/models/DataWarehouse/WarehouseTables.py`)
- **Table:** `bi_warehouse_table`
- **Number Prefix:** `BDWT` (`BDWT-00001`)
- **CHOICES:**
  - `TABLE_TYPE_CHOICES = [('fact', 'Fact Table (Transactional / Periodic Metrics)'), ('dimension', 'Dimension Table (Contextual Attributes & Master Data)'), ('aggregate', 'Aggregate Table (Pre-Calculated Summary Rollups)'), ('bridge', 'Bridge Table (Many-to-Many Disambiguation)'), ('staging', 'Staging / Transient Target Table')]`
  - `SCHEMA_TYPE_CHOICES = [('star', 'Star Schema (Direct Joins)'), ('snowflake', 'Snowflake Schema (Normalized Sub-Dimensions)'), ('flat', 'Flat / Denormalized Wide Table'), ('medallion', 'Medallion Delta Format')]`
  - `GRAIN_CHOICES = [('transaction', 'Transactional (One row per business event)'), ('daily_snapshot', 'Daily Periodic Snapshot'), ('monthly_snapshot', 'Monthly Periodic Snapshot'), ('accumulating_snapshot', 'Accumulating Milestone Snapshot'), ('entity_state', 'Entity Current State (Dimension)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `table_name`: `CharField(max_length=100)`
  - `table_type`: `CharField(max_length=25, choices=TABLE_TYPE_CHOICES, default='fact')`
  - `schema_type`: `CharField(max_length=25, choices=SCHEMA_TYPE_CHOICES, default='star')`
  - `grain`: `CharField(max_length=30, choices=GRAIN_CHOICES, default='transaction')`
  - `lakehouse_zone`: `ForeignKey('bi.LakehouseZone', on_delete=models.PROTECT, related_name='tables')`
  - `data_mart`: `ForeignKey('bi.DataMart', on_delete=models.SET_NULL, null=True, blank=True, related_name='tables')`
  - `storage_policy`: `ForeignKey('bi.WarehouseStoragePolicy', on_delete=models.SET_NULL, null=True, blank=True, related_name='tables')`
  - `primary_key_column`: `CharField(max_length=100, default='id')`
  - `natural_key_column`: `CharField(max_length=100, blank=True)`
  - `is_conformed_dimension`: `BooleanField(default=False)`
  - `schema_definition`: `JSONField(default=list, blank=True)`
  - `row_count`: `BigIntegerField(default=0)`
  - `compressed_bytes`: `BigIntegerField(default=0)`
  - `compression_ratio`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))`
  - `last_analyzed_at`: `DateTimeField(null=True, blank=True)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'table_name'], name='bi_bdwt_tenant_tbl_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdwt_tenant_num_uniq')`
  - `Index(fields=['tenant', 'table_type'], name='idx_bdwt_ten_type')`
  - `Index(fields=['tenant', 'lakehouse_zone'], name='idx_bdwt_ten_zone')`
  - `Index(fields=['tenant', 'data_mart'], name='idx_bdwt_ten_mart')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdwt_ten_active')`

---

## 2. Forms & Exclusions Contract

### 2.1 `DataMartForm`
- **Class:** `apps.bi.forms.DataWarehouse.DataMarts.DataMartForm`
- **Model:** `DataMart`
- **Excluded:** `tenant`, `number`, `created_at`, `updated_at`
- **Fields included:** `name`, `code`, `subject_area`, `org_unit`, `owner`, `steward`, `access_tier`, `certification_status`, `refresh_cadence`, `description`, `is_active`

### 2.2 `LakehouseZoneForm`
- **Class:** `apps.bi.forms.DataWarehouse.LakehouseZones.LakehouseZoneForm`
- **Model:** `LakehouseZone`
- **Excluded:** `tenant`, `number`, `created_at`, `updated_at`
- **Fields included:** `name`, `code`, `zone_type`, `storage_backend`, `default_format`, `base_uri_path`, `is_read_only`, `description`, `is_active`

### 2.3 `WarehouseStoragePolicyForm`
- **Class:** `apps.bi.forms.DataWarehouse.WarehouseStoragePolicies.WarehouseStoragePolicyForm`
- **Model:** `WarehouseStoragePolicy`
- **Excluded:** `tenant`, `number`, `created_at`, `updated_at`
- **Fields included:** `name`, `partition_strategy`, `partition_key`, `partition_granularity`, `compression_codec`, `enable_zone_maps`, `hot_tier_days`, `warm_tier_days`, `cold_tier_days`, `time_travel_days`, `auto_purge_enabled`, `vacuum_cadence`, `is_default`, `description`, `is_active`

### 2.4 `WarehouseTableForm`
- **Class:** `apps.bi.forms.DataWarehouse.WarehouseTables.WarehouseTableForm`
- **Model:** `WarehouseTable`
- **Excluded:** `tenant`, `number`, `created_at`, `updated_at`, `row_count`, `compressed_bytes`, `compression_ratio`, `last_analyzed_at`
- **Fields included:** `name`, `table_name`, `table_type`, `schema_type`, `grain`, `lakehouse_zone`, `data_mart`, `storage_policy`, `primary_key_column`, `natural_key_column`, `is_conformed_dimension`, `schema_definition`, `description`, `is_active`

---

## 3. URLs & Routing Contract

Namespace: `bi` (in `apps/bi/urls/DataWarehouse/`)

| Route Pattern | View Name | URL Name | Purpose |
|---------------|-----------|----------|---------|
| `data-marts/` | `data_mart_list` | `bi:data_mart_list` | Mart list with filters & stats |
| `data-marts/create/` | `data_mart_create` | `bi:data_mart_create` | Create mart |
| `data-marts/<int:pk>/` | `data_mart_detail` | `bi:data_mart_detail` | Mart detail & table manifest |
| `data-marts/<int:pk>/edit/` | `data_mart_edit` | `bi:data_mart_edit` | Edit mart |
| `data-marts/<int:pk>/delete/` | `data_mart_delete` | `bi:data_mart_delete` | POST-only delete |
| `lakehouse-zones/` | `lakehouse_zone_list` | `bi:lakehouse_zone_list` | Medallion zone list |
| `lakehouse-zones/create/` | `lakehouse_zone_create` | `bi:lakehouse_zone_create` | Create zone |
| `lakehouse-zones/<int:pk>/` | `lakehouse_zone_detail` | `bi:lakehouse_zone_detail` | Zone detail & tables |
| `lakehouse-zones/<int:pk>/edit/` | `lakehouse_zone_edit` | `bi:lakehouse_zone_edit` | Edit zone |
| `lakehouse-zones/<int:pk>/delete/` | `lakehouse_zone_delete` | `bi:lakehouse_zone_delete` | POST-only delete |
| `storage-policies/` | `warehouse_storage_policy_list` | `bi:warehouse_storage_policy_list` | Storage policy list |
| `storage-policies/create/` | `warehouse_storage_policy_create` | `bi:warehouse_storage_policy_create` | Create storage policy |
| `storage-policies/<int:pk>/` | `warehouse_storage_policy_detail` | `bi:warehouse_storage_policy_detail` | Policy detail & thresholds |
| `storage-policies/<int:pk>/edit/` | `warehouse_storage_policy_edit` | `bi:warehouse_storage_policy_edit` | Edit storage policy |
| `storage-policies/<int:pk>/delete/` | `warehouse_storage_policy_delete` | `bi:warehouse_storage_policy_delete` | POST-only delete |
| `warehouse-tables/` | `warehouse_table_list` | `bi:warehouse_table_list` | Table catalog list |
| `warehouse-tables/create/` | `warehouse_table_create` | `bi:warehouse_table_create` | Register table |
| `warehouse-tables/<int:pk>/` | `warehouse_table_detail` | `bi:warehouse_table_detail` | Table detail & schema |
| `warehouse-tables/<int:pk>/edit/` | `warehouse_table_edit` | `bi:warehouse_table_edit` | Edit table |
| `warehouse-tables/<int:pk>/delete/` | `warehouse_table_delete` | `bi:warehouse_table_delete` | POST-only delete |
| `warehouse-tables/<int:pk>/ddl/` | `warehouse_table_ddl_preview` | `bi:warehouse_table_ddl_preview` | SQL DDL preview |
| `warehouse-tables/<int:pk>/analyze/` | `warehouse_table_analyze` | `bi:warehouse_table_analyze` | POST-only analyze stats |
| `warehouse-overview/` | `warehouse_overview` | `bi:warehouse_overview` | Consolidated operational overview |

---

## 4. View Context Keys Contract (MANDATORY)

### 4.1 DataMart Views
- **`data_mart_list`**:
  - `page_obj`: paginated query of `DataMart`
  - `data_marts`: list/page iterator
  - `subject_area_choices`: `DataMart.SUBJECT_AREA_CHOICES`
  - `certification_status_choices`: `DataMart.CERTIFICATION_STATUS_CHOICES`
  - `access_tier_choices`: `DataMart.ACCESS_TIER_CHOICES`
  - `active_choices`: `[('1', 'Active'), ('0', 'Inactive')]`
  - `total_count`: integer
  - `certified_count`: integer
  - `draft_count`: integer
  - `search_query`: `request.GET.get('q', '')`
- **`data_mart_detail`**:
  - `data_mart`: single `DataMart` instance
  - `tables`: queryset of `WarehouseTable` belonging to this mart
- **`data_mart_create` / `data_mart_edit`**:
  - `form`: `DataMartForm`
  - `data_mart`: instance (or None)
  - `is_edit`: boolean

### 4.2 LakehouseZone Views
- **`lakehouse_zone_list`**:
  - `page_obj`: paginated query of `LakehouseZone`
  - `lakehouse_zones`: list/page iterator
  - `zone_type_choices`: `LakehouseZone.ZONE_TYPE_CHOICES`
  - `storage_backend_choices`: `LakehouseZone.STORAGE_BACKEND_CHOICES`
  - `default_format_choices`: `LakehouseZone.DEFAULT_FORMAT_CHOICES`
  - `active_choices`: `[('1', 'Active'), ('0', 'Inactive')]`
  - `total_count`: integer
  - `bronze_count`: integer
  - `silver_count`: integer
  - `gold_count`: integer
  - `search_query`: `request.GET.get('q', '')`
- **`lakehouse_zone_detail`**:
  - `lakehouse_zone`: single `LakehouseZone` instance
  - `tables`: queryset of `WarehouseTable` residing in this zone
- **`lakehouse_zone_create` / `lakehouse_zone_edit`**:
  - `form`: `LakehouseZoneForm`
  - `lakehouse_zone`: instance (or None)
  - `is_edit`: boolean

### 4.3 WarehouseStoragePolicy Views
- **`warehouse_storage_policy_list`**:
  - `page_obj`: paginated query of `WarehouseStoragePolicy`
  - `storage_policies`: list/page iterator
  - `partition_strategy_choices`: `WarehouseStoragePolicy.PARTITION_STRATEGY_CHOICES`
  - `compression_codec_choices`: `WarehouseStoragePolicy.COMPRESSION_CODEC_CHOICES`
  - `vacuum_cadence_choices`: `WarehouseStoragePolicy.VACUUM_CADENCE_CHOICES`
  - `active_choices`: `[('1', 'Active'), ('0', 'Inactive')]`
  - `total_count`: integer
  - `default_policy`: single `WarehouseStoragePolicy` or None
  - `search_query`: `request.GET.get('q', '')`
- **`warehouse_storage_policy_detail`**:
  - `storage_policy`: single `WarehouseStoragePolicy` instance
  - `tables`: queryset of `WarehouseTable` governed by this policy
- **`warehouse_storage_policy_create` / `warehouse_storage_policy_edit`**:
  - `form`: `WarehouseStoragePolicyForm`
  - `storage_policy`: instance (or None)
  - `is_edit`: boolean

### 4.4 WarehouseTable Views
- **`warehouse_table_list`**:
  - `page_obj`: paginated query of `WarehouseTable`
  - `warehouse_tables`: list/page iterator
  - `table_type_choices`: `WarehouseTable.TABLE_TYPE_CHOICES`
  - `schema_type_choices`: `WarehouseTable.SCHEMA_TYPE_CHOICES`
  - `grain_choices`: `WarehouseTable.GRAIN_CHOICES`
  - `lakehouse_zones`: queryset of active `LakehouseZone`
  - `data_marts`: queryset of active `DataMart`
  - `active_choices`: `[('1', 'Active'), ('0', 'Inactive')]`
  - `total_count`: integer
  - `fact_count`: integer
  - `dimension_count`: integer
  - `total_rows`: integer
  - `search_query`: `request.GET.get('q', '')`
- **`warehouse_table_detail`**:
  - `warehouse_table`: single `WarehouseTable` instance
  - `table`: alias for `warehouse_table`
  - `ddl_sql`: formatted SQL DDL string
- **`warehouse_table_form`**:
  - `form`: `WarehouseTableForm`
  - `warehouse_table`: instance (or None)
  - `table`: alias for `warehouse_table`
  - `is_edit`: boolean

### 4.5 WarehouseOverview View
- **`warehouse_overview`**:
  - `total_tables`: integer
  - `fact_count`: integer
  - `dim_count`: integer
  - `total_rows`: integer
  - `total_compressed_bytes`: integer
  - `total_marts`: integer
  - `certified_marts`: integer
  - `total_zones`: integer
  - `total_policies`: integer
  - `recent_tables`: queryset of latest `WarehouseTable`
  - `marts`: queryset of `DataMart` with table counts
  - `zones`: queryset of `LakehouseZone` with table counts

---

## 5. Navigation `LIVE_LINKS["10.3"]` Mapping

```python
LIVE_LINKS["10.3"] = {
    "Centralized Data Warehouse": "bi:warehouse_table_list",
    "Data Marts": "bi:data_mart_list",
    "Data Lake & Lakehouse": "bi:lakehouse_zone_list",
    "Partitioning & Compression": "bi:warehouse_storage_policy_list",
    "Archival & Retention": "bi:warehouse_storage_policy_list",
    "Warehouse Tables": "bi:warehouse_table_list",
    "Storage Policies": "bi:warehouse_storage_policy_list",
    "Lakehouse Zones": "bi:lakehouse_zone_list",
    "Warehouse Overview": "bi:warehouse_overview",
}
```

---

## 6. Template Hierarchy & File Paths

```
templates/bi/data_warehouse/
  warehouse_overview.html
  data_mart/
    list.html
    detail.html
    form.html
  lakehouse_zone/
    list.html
    detail.html
    form.html
  warehouse_storage_policy/
    list.html
    detail.html
    form.html
  warehouse_table/
    list.html
    detail.html
    form.html
```

Design system compliance:
- `.badge-green`, `.badge-amber`, `.badge-red`, `.badge-info`, `.badge-muted`, `.badge-slate` (NO semantic names like badge-success).
- Table actions: `<i data-lucide="eye"></i>`, `<i data-lucide="pencil"></i>`, `<i data-lucide="trash-2"></i>`.
- Single-line comments only `{# ... #}`. Never multiline with `{#`.
