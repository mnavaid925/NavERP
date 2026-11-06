# Contract — Sub-module 10.10: Self-Service & Ad-Hoc Analytics (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.10 Self-Service & Ad-Hoc Analytics · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-06 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended across 10.2 through 10.9). Incremental migration: `0024_...`
- **Package Layout:** `SelfServiceAnalytics/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/self_service_analytics/`.

---

## 1. Models & CHOICES Contract

All 4 top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AdHocQuery` (`apps/bi/models/SelfServiceAnalytics/AdHocQueries.py`)
- **Table:** `bi_ad_hoc_query`
- **Number Prefix:** `BAHQ` (`BAHQ-00001`)
- **CHOICES:**
  - `SOURCE_TYPE_CHOICES = [('semantic_model', 'Governed Semantic Model'), ('warehouse_table', 'Warehouse Fact/Dimension Table'), ('blend', 'Blended Dataset Mashup')]`
  - `VISUALIZATION_TYPE_CHOICES = [('table', 'Data Table Grid'), ('bar_chart', 'Bar / Column Chart'), ('line_chart', 'Line Trend Chart'), ('area_chart', 'Area Chart'), ('pie_chart', 'Donut / Pie Chart'), ('kpi_card', 'Single Metric KPI Card'), ('pivot_table', 'Multi-Dimensional Pivot Matrix')]`
  - `STATUS_CHOICES = [('draft', 'Draft Exploration'), ('active', 'Active / Ready'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `source_type`: `CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default='semantic_model')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='ad_hoc_queries')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='ad_hoc_queries')`
  - `data_blend`: `ForeignKey('bi.DataBlendDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='ad_hoc_queries')`
  - `fields_config_json`: `JSONField(default=list, help_text="List of selected dimensions and measures with aggregations")`
  - `filter_criteria_json`: `JSONField(default=list, help_text="Multi-condition filter rules: field, operator, value")`
  - `sort_config_json`: `JSONField(default=list, help_text="Sorting criteria: field, direction")`
  - `visualization_type`: `CharField(max_length=30, choices=VISUALIZATION_TYPE_CHOICES, default='table')`
  - `chart_config_json`: `JSONField(default=dict, help_text="Chart styling, colors, axes labels, legends")`
  - `row_limit`: `PositiveIntegerField(default=500)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `last_executed_at`: `DateTimeField(null=True, blank=True)`
  - `execution_duration_ms`: `PositiveIntegerField(default=0)`
  - `row_count`: `PositiveIntegerField(default=0)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_ad_hoc_queries')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bahq_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bahq_tenant_num_uniq')`
  - `Index(fields=['tenant', 'source_type'], name='idx_bahq_ten_src')`
  - `Index(fields=['tenant', 'visualization_type'], name='idx_bahq_ten_viz')`
  - `Index(fields=['tenant', 'status'], name='idx_bahq_ten_stat')`
  - `Index(fields=['tenant', 'created_by'], name='idx_bahq_ten_user')`

---

### 1.2 `AdHocCalculatedField` (`apps/bi/models/SelfServiceAnalytics/AdHocCalculatedFields.py`)
- **Table:** `bi_ad_hoc_calculated_field`
- **Number Prefix:** `BACF` (`BACF-00001`)
- **CHOICES:**
  - `RETURN_TYPE_CHOICES = [('decimal', 'Decimal Amount'), ('integer', 'Integer Number'), ('percentage', 'Percentage (%)'), ('currency', 'Currency ($)'), ('string', 'Text String'), ('boolean', 'Boolean (True/False)')]`
  - `AGGREGATION_MODE_CHOICES = [('formula', 'Direct Formula Calculation'), ('pre_agg', 'Row-Level Before Aggregation'), ('post_agg', 'Summary-Level After Aggregation')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `query`: `ForeignKey('bi.AdHocQuery', on_delete=CASCADE, related_name='calculated_fields')`
  - `field_name`: `SlugField(max_length=60)`
  - `display_label`: `CharField(max_length=120)`
  - `formula_expression`: `CharField(max_length=500, help_text="e.g. [revenue] - [cost] or ([margin] / [revenue]) * 100")`
  - `return_type`: `CharField(max_length=30, choices=RETURN_TYPE_CHOICES, default='decimal')`
  - `aggregation_mode`: `CharField(max_length=30, choices=AGGREGATION_MODE_CHOICES, default='formula')`
  - `is_valid`: `BooleanField(default=True)`
  - `error_message`: `CharField(max_length=255, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_ad_hoc_calc_fields')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bacf_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'query', 'field_name'], name='bi_bacf_ten_qry_fname_uniq')`
  - `Index(fields=['tenant', 'query'], name='idx_bacf_ten_qry')`
  - `Index(fields=['tenant', 'return_type'], name='idx_bacf_ten_rtype')`

---

### 1.3 `DataBlendDefinition` (`apps/bi/models/SelfServiceAnalytics/DataBlendDefinitions.py`)
- **Table:** `bi_data_blend_definition`
- **Number Prefix:** `BBLD` (`BBLD-00001`)
- **CHOICES:**
  - `SOURCE_TYPE_CHOICES = [('semantic_model', 'Governed Semantic Model'), ('warehouse_table', 'Warehouse Fact/Dimension Table')]`
  - `JOIN_TYPE_CHOICES = [('inner', 'Inner Join (Matching Records Only)'), ('left_outer', 'Left Outer Join (All Primary Records)'), ('right_outer', 'Right Outer Join (All Secondary Records)'), ('full_outer', 'Full Outer Join (All Records from Both)')]`
  - `CARDINALITY_CHOICES = [('one_to_one', 'One-to-One (1:1)'), ('one_to_many', 'One-to-Many (1:N)'), ('many_to_one', 'Many-to-One (N:1)')]`
  - `STATUS_CHOICES = [('active', 'Active / In Use'), ('draft', 'Draft Setup'), ('deprecated', 'Deprecated')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `primary_source_type`: `CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default='semantic_model')`
  - `primary_semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='primary_blends')`
  - `primary_warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='primary_blends')`
  - `secondary_source_type`: `CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default='semantic_model')`
  - `secondary_semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='secondary_blends')`
  - `secondary_warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='secondary_blends')`
  - `join_type`: `CharField(max_length=20, choices=JOIN_TYPE_CHOICES, default='left_outer')`
  - `join_keys_mapping_json`: `JSONField(default=list, help_text="Pairs of primary and secondary field keys to join on")`
  - `cardinality`: `CharField(max_length=20, choices=CARDINALITY_CHOICES, default='many_to_one')`
  - `collision_resolution`: `CharField(max_length=50, default='prefix_secondary')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_data_blends')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bbld_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bbld_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_bbld_ten_stat')`
  - `Index(fields=['tenant', 'join_type'], name='idx_bbld_ten_jtype')`

---

### 1.4 `SavedAnalysisView` (`apps/bi/models/SelfServiceAnalytics/SavedAnalysisViews.py`)
- **Table:** `bi_saved_analysis_view`
- **Number Prefix:** `BSAV` (`BSAV-00001`)
- **CHOICES:**
  - `SHARING_SCOPE_CHOICES = [('personal', 'Personal Workspace (Private)'), ('team', 'Team / Department (Org Unit)'), ('tenant_public', 'Tenant Public (All Users)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `query`: `ForeignKey('bi.AdHocQuery', on_delete=CASCADE, related_name='saved_views')`
  - `sharing_scope`: `CharField(max_length=20, choices=SHARING_SCOPE_CHOICES, default='personal')`
  - `org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_saved_analysis_views')`
  - `is_template`: `BooleanField(default=False)`
  - `is_favorite`: `BooleanField(default=False)`
  - `parent_view`: `ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='forked_views')`
  - `share_token`: `CharField(max_length=64, blank=True)`
  - `view_count`: `PositiveIntegerField(default=0)`
  - `last_viewed_at`: `DateTimeField(null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_saved_analysis_views')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bsav_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bsav_tenant_num_uniq')`
  - `Index(fields=['tenant', 'sharing_scope'], name='idx_bsav_ten_scope')`
  - `Index(fields=['tenant', 'org_unit'], name='idx_bsav_ten_org')`
  - `Index(fields=['tenant', 'created_by'], name='idx_bsav_ten_user')`
  - `Index(fields=['tenant', 'is_template'], name='idx_bsav_ten_tmpl')`

---

## 2. Forms Contract

### 2.1 `AdHocQueryForm` (`AdHocQueries.py`)
- **Model:** `AdHocQuery`
- **Fields:** `['name', 'description', 'source_type', 'semantic_model', 'warehouse_table', 'data_blend', 'visualization_type', 'row_limit', 'status']`
- **Exclusions:** `['tenant', 'number', 'slug', 'fields_config_json', 'filter_criteria_json', 'sort_config_json', 'chart_config_json', 'last_executed_at', 'execution_duration_ms', 'row_count', 'created_by', 'created_at', 'updated_at']`

### 2.2 `AdHocQueryComposerForm` (`AdHocQueries.py`)
- **Model:** `AdHocQuery`
- **Fields:** `['name', 'description', 'source_type', 'semantic_model', 'warehouse_table', 'data_blend', 'fields_config_json', 'filter_criteria_json', 'sort_config_json', 'visualization_type', 'chart_config_json', 'row_limit', 'status']`

### 2.3 `AdHocCalculatedFieldForm` (`AdHocCalculatedFields.py`)
- **Model:** `AdHocCalculatedField`
- **Fields:** `['query', 'field_name', 'display_label', 'formula_expression', 'return_type', 'aggregation_mode']`
- **Exclusions:** `['tenant', 'number', 'is_valid', 'error_message', 'created_by', 'created_at', 'updated_at']`

### 2.4 `DataBlendDefinitionForm` (`DataBlendDefinitions.py`)
- **Model:** `DataBlendDefinition`
- **Fields:** `['name', 'description', 'primary_source_type', 'primary_semantic_model', 'primary_warehouse_table', 'secondary_source_type', 'secondary_semantic_model', 'secondary_warehouse_table', 'join_type', 'join_keys_mapping_json', 'cardinality', 'collision_resolution', 'status']`
- **Exclusions:** `['tenant', 'number', 'slug', 'created_by', 'created_at', 'updated_at']`

### 2.5 `SavedAnalysisViewForm` (`SavedAnalysisViews.py`)
- **Model:** `SavedAnalysisView`
- **Fields:** `['name', 'description', 'query', 'sharing_scope', 'org_unit', 'is_template', 'is_favorite']`
- **Exclusions:** `['tenant', 'number', 'slug', 'parent_view', 'share_token', 'view_count', 'last_viewed_at', 'created_by', 'created_at', 'updated_at']`

### 2.6 `SavedAnalysisViewShareForm` (`SavedAnalysisViews.py`)
- **Model:** `SavedAnalysisView`
- **Fields:** `['sharing_scope', 'org_unit']`

---

## 3. Views & Context Variables Contract

### 3.1 `AdHocQuery` Views (`AdHocQueries.py`)
- `ad_hoc_query_list`:
  - Context keys: `queries`, `page_obj`, `source_type_choices`, `viz_choices`, `status_choices`
- `ad_hoc_query_detail`:
  - Context keys: `query`, `calculated_fields`, `saved_views`, `sample_data`
- `ad_hoc_query_create`:
  - Context keys: `form`, `is_edit=False`, `semantic_models`, `warehouse_tables`, `blends`
- `ad_hoc_query_edit`:
  - Context keys: `form`, `query`, `is_edit=True`, `semantic_models`, `warehouse_tables`, `blends`
- `ad_hoc_query_delete`:
  - POST-only confirmation; redirects to `bi:ad_hoc_query_list`
- `ad_hoc_query_composer`:
  - Context keys: `query`, `form`, `semantic_models`, `warehouse_tables`, `blends`, `viz_choices`, `preview_results`
- `ad_hoc_query_execute`:
  - JSON execution endpoint returning data rows, columns, and duration
- `ad_hoc_query_export`:
  - CSV export stream

### 3.2 `AdHocCalculatedField` Views (`AdHocCalculatedFields.py`)
- `ad_hoc_calculated_field_list`:
  - Context keys: `calculated_fields`, `page_obj`, `return_type_choices`, `query_filter`
- `ad_hoc_calculated_field_detail`:
  - Context keys: `calculated_field`, `query`
- `ad_hoc_calculated_field_create`:
  - Context keys: `form`, `is_edit=False`, `queries`
- `ad_hoc_calculated_field_edit`:
  - Context keys: `form`, `calculated_field`, `is_edit=True`, `queries`
- `ad_hoc_calculated_field_delete`:
  - POST-only confirmation; redirects to `bi:ad_hoc_calculated_field_list`
- `ad_hoc_calculated_field_validate`:
  - JSON endpoint validating formula expression syntax

### 3.3 `DataBlendDefinition` Views (`DataBlendDefinitions.py`)
- `data_blend_definition_list`:
  - Context keys: `blends`, `page_obj`, `join_type_choices`, `status_choices`
- `data_blend_definition_detail`:
  - Context keys: `blend`, `queries`
- `data_blend_definition_create`:
  - Context keys: `form`, `is_edit=False`, `semantic_models`, `warehouse_tables`
- `data_blend_definition_edit`:
  - Context keys: `form`, `blend`, `is_edit=True`, `semantic_models`, `warehouse_tables`
- `data_blend_definition_delete`:
  - POST-only confirmation; redirects to `bi:data_blend_definition_list`
- `data_blend_definition_preview`:
  - Context keys: `blend`, `preview_rows`, `preview_cols`

### 3.4 `SavedAnalysisView` Views (`SavedAnalysisViews.py`)
- `saved_analysis_view_list`:
  - Context keys: `views`, `page_obj`, `scope_choices`, `org_units`
- `saved_analysis_view_detail`:
  - Context keys: `view_obj`, `query`
- `saved_analysis_view_create`:
  - Context keys: `form`, `is_edit=False`, `queries`, `org_units`
- `saved_analysis_view_edit`:
  - Context keys: `form`, `view_obj`, `is_edit=True`, `queries`, `org_units`
- `saved_analysis_view_delete`:
  - POST-only confirmation; redirects to `bi:saved_analysis_view_list`
- `saved_analysis_view_clone`:
  - Clone action duplicating query view into personal workspace
- `saved_analysis_view_share`:
  - Context keys: `form`, `view_obj`
- `saved_analysis_view_explore`:
  - Context keys: `view_obj`, `query`, `chart_config`, `preview_results`

---

## 4. URL Names Contract (`app_name = 'bi'`)

All routes defined under `apps/bi/urls/SelfServiceAnalytics/` and mounted in `apps/bi/urls/__init__.py`:

```python
# AdHocQuery
path('queries/', views.ad_hoc_query_list, name='ad_hoc_query_list'),
path('queries/create/', views.ad_hoc_query_create, name='ad_hoc_query_create'),
path('queries/<int:pk>/', views.ad_hoc_query_detail, name='ad_hoc_query_detail'),
path('queries/<int:pk>/edit/', views.ad_hoc_query_edit, name='ad_hoc_query_edit'),
path('queries/<int:pk>/delete/', views.ad_hoc_query_delete, name='ad_hoc_query_delete'),
path('queries/<int:pk>/composer/', views.ad_hoc_query_composer, name='ad_hoc_query_composer'),
path('queries/<int:pk>/execute/', views.ad_hoc_query_execute, name='ad_hoc_query_execute'),
path('queries/<int:pk>/export/', views.ad_hoc_query_export, name='ad_hoc_query_export'),

# AdHocCalculatedField
path('calculated-fields/', views.ad_hoc_calculated_field_list, name='ad_hoc_calculated_field_list'),
path('calculated-fields/create/', views.ad_hoc_calculated_field_create, name='ad_hoc_calculated_field_create'),
path('calculated-fields/<int:pk>/', views.ad_hoc_calculated_field_detail, name='ad_hoc_calculated_field_detail'),
path('calculated-fields/<int:pk>/edit/', views.ad_hoc_calculated_field_edit, name='ad_hoc_calculated_field_edit'),
path('calculated-fields/<int:pk>/delete/', views.ad_hoc_calculated_field_delete, name='ad_hoc_calculated_field_delete'),
path('calculated-fields/validate/', views.ad_hoc_calculated_field_validate, name='ad_hoc_calculated_field_validate'),

# DataBlendDefinition
path('data-blends/', views.data_blend_definition_list, name='data_blend_definition_list'),
path('data-blends/create/', views.data_blend_definition_create, name='data_blend_definition_create'),
path('data-blends/<int:pk>/', views.data_blend_definition_detail, name='data_blend_definition_detail'),
path('data-blends/<int:pk>/edit/', views.data_blend_definition_edit, name='data_blend_definition_edit'),
path('data-blends/<int:pk>/delete/', views.data_blend_definition_delete, name='data_blend_definition_delete'),
path('data-blends/<int:pk>/preview/', views.data_blend_definition_preview, name='data_blend_definition_preview'),

# SavedAnalysisView
path('saved-views/', views.saved_analysis_view_list, name='saved_analysis_view_list'),
path('saved-views/create/', views.saved_analysis_view_create, name='saved_analysis_view_create'),
path('saved-views/<int:pk>/', views.saved_analysis_view_detail, name='saved_analysis_view_detail'),
path('saved-views/<int:pk>/edit/', views.saved_analysis_view_edit, name='saved_analysis_view_edit'),
path('saved-views/<int:pk>/delete/', views.saved_analysis_view_delete, name='saved_analysis_view_delete'),
path('saved-views/<int:pk>/clone/', views.saved_analysis_view_clone, name='saved_analysis_view_clone'),
path('saved-views/<int:pk>/share/', views.saved_analysis_view_share, name='saved_analysis_view_share'),
path('saved-views/<int:pk>/explore/', views.saved_analysis_view_explore, name='saved_analysis_view_explore'),
```

---

## 5. Template Paths & Structure Contract

Templates live under `templates/bi/self_service_analytics/` extending `templates/base.html`:

```
templates/bi/self_service_analytics/
├── ad_hoc_query/
│   ├── list.html           # Catalog of ad-hoc queries, search, status/viz filter pills, actions
│   ├── detail.html         # Query specs, fields, filters, executed summary, linked views/formulas
│   ├── form.html           # Standard CRUD metadata form (name, description, source dataset)
│   └── composer.html       # Visual drag-and-drop query builder (fields, filters, chart picker, live preview)
├── ad_hoc_calculated_field/
│   ├── list.html           # Calculated fields list with formula expressions and return types
│   ├── detail.html         # Formula detail, parent query link, syntax validity check
│   └── form.html           # Formula editor with expression input and validation helper
├── data_blend_definition/
│   ├── list.html           # Blends table with join types, primary/secondary sources, status
│   ├── detail.html         # Blend architecture, join key mappings matrix, linked queries
│   └── form.html           # Multi-dataset mashup builder with join key configuration
└── saved_analysis_view/
    ├── list.html           # Personal workspace and team catalog views, favorites filter
    ├── detail.html         # Saved view metadata, sharing permissions, parent lineage
    ├── form.html           # Saved view properties editor
    └── explore.html        # Interactive analytical exploration view with Chart.js visualization
```
