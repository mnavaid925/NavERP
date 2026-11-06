# Contract — Sub-module 10.9: Standard & Operational Reporting (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.9 Standard & Operational Reporting · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-06 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended across 10.2 through 10.8). Incremental migration: `0022_...`
- **Package Layout:** `OperationalReporting/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/operational_reporting/`.

---

## 1. Models & CHOICES Contract

All 4 top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `ReportDefinition` (`apps/bi/models/OperationalReporting/ReportDefinitions.py`)
- **Table:** `bi_report_definition`
- **Number Prefix:** `BRPT` (`BRPT-00001`)
- **CHOICES:**
  - `CATEGORY_CHOICES = [('finance', 'Finance & Accounting'), ('sales', 'Sales & CRM'), ('inventory', 'Inventory & Warehouse'), ('hr', 'Human Resources & Talent'), ('procurement', 'Procurement & Purchasing'), ('production', 'Manufacturing & Production'), ('compliance', 'Regulatory & Compliance'), ('custom', 'Custom Operational Report')]`
  - `REPORT_TYPE_CHOICES = [('standard_tabular', 'Standard Tabular Report'), ('pixel_perfect_document', 'Pixel-Perfect Banded Document'), ('regulatory_filing', 'Regulatory & Compliance Filing'), ('matrix_summary', 'Cross-Tab Matrix Summary'), ('subreport', 'Modular Subreport Component')]`
  - `PAPER_SIZE_CHOICES = [('a4', 'ISO A4 (210 x 297 mm)'), ('letter', 'US Letter (8.5 x 11 in)'), ('legal', 'US Legal (8.5 x 14 in)'), ('tabloid', 'US Tabloid (11 x 17 in)'), ('custom', 'Custom Dimensions')]`
  - `ORIENTATION_CHOICES = [('portrait', 'Portrait'), ('landscape', 'Landscape')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Design in Progress)'), ('published', 'Published (Live for Users)'), ('archived', 'Archived (Deprecated)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `category`: `CharField(max_length=40, choices=CATEGORY_CHOICES, default='finance')`
  - `report_type`: `CharField(max_length=40, choices=REPORT_TYPE_CHOICES, default='standard_tabular')`
  - `paper_size`: `CharField(max_length=20, choices=PAPER_SIZE_CHOICES, default='a4')`
  - `orientation`: `CharField(max_length=20, choices=ORIENTATION_CHOICES, default='portrait')`
  - `margins_json`: `JSONField(default=dict, help_text="Page margins in mm: {'top': 15, 'bottom': 15, 'left': 15, 'right': 15}")`
  - `bands_config_json`: `JSONField(default=dict, help_text="Banded layout configuration: title_band, page_header, group_header, detail_band, group_footer, page_footer, summary_band")`
  - `columns_config_json`: `JSONField(default=list, help_text="Tabular column definitions: field, title, width, align, format")`
  - `styling_css`: `TextField(blank=True, help_text="Custom CSS styling rules applied to rendered report output")`
  - `watermark_text`: `CharField(max_length=100, blank=True, help_text="Optional background watermark text")`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='operational_reports')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='operational_reports')`
  - `raw_query`: `TextField(blank=True, help_text="Optional direct analytical SQL/ORM query specification")`
  - `org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_operational_reports')`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_bi_reports')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `is_prebuilt_template`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_brpt_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_brpt_tenant_num_uniq')`
  - `Index(fields=['tenant', 'category'], name='idx_brpt_ten_cat')`
  - `Index(fields=['tenant', 'report_type'], name='idx_brpt_ten_type')`
  - `Index(fields=['tenant', 'status'], name='idx_brpt_ten_stat')`
  - `Index(fields=['tenant', 'semantic_model'], name='idx_brpt_ten_smdl')`
  - `Index(fields=['tenant', 'is_active'], name='idx_brpt_ten_act')`

---

### 1.2 `ReportParameter` (`apps/bi/models/OperationalReporting/ReportParameters.py`)
- **Table:** `bi_report_parameter`
- **Number Prefix:** `BPAR` (`BPAR-00001`)
- **CHOICES:**
  - `PARAMETER_TYPE_CHOICES = [('string', 'Text String'), ('integer', 'Integer Number'), ('decimal', 'Decimal Amount'), ('date', 'Single Date Picker'), ('daterange', 'Date Range (From / To)'), ('boolean', 'Boolean Checkbox'), ('choice_single', 'Single-Select Dropdown'), ('choice_multi', 'Multi-Select Badges / List')]`
  - `CHOICES_SOURCE_CHOICES = [('static_list', 'Static Pre-defined Choices'), ('semantic_dimension', 'Distinct Values from Semantic Model'), ('warehouse_column', 'Distinct Values from Warehouse Table')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `report`: `ForeignKey('bi.ReportDefinition', on_delete=CASCADE, related_name='parameters')`
  - `parameter_name`: `SlugField(max_length=60)`
  - `prompt_label`: `CharField(max_length=120)`
  - `parameter_type`: `CharField(max_length=30, choices=PARAMETER_TYPE_CHOICES, default='string')`
  - `default_value`: `CharField(max_length=255, blank=True)`
  - `choices_source`: `CharField(max_length=30, choices=CHOICES_SOURCE_CHOICES, default='static_list')`
  - `choices_config_json`: `JSONField(default=list)`
  - `validation_regex`: `CharField(max_length=200, blank=True)`
  - `help_text`: `CharField(max_length=255, blank=True)`
  - `prompt_order`: `PositiveIntegerField(default=10)`
  - `is_required`: `BooleanField(default=False)`
  - `is_hidden`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bpar_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'report', 'parameter_name'], name='bi_bpar_ten_rpt_pname_uniq')`
  - `Index(fields=['tenant', 'report'], name='idx_bpar_ten_rpt')`
  - `Index(fields=['tenant', 'parameter_type'], name='idx_bpar_ten_ptype')`
  - `Index(fields=['tenant', 'prompt_order'], name='idx_bpar_ten_ord')`

---

### 1.3 `ReportExecution` (`apps/bi/models/OperationalReporting/ReportExecutions.py`)
- **Table:** `bi_report_execution`
- **Number Prefix:** `BRUN` (`BRUN-00001`)
- **CHOICES:**
  - `EXECUTION_MODE_CHOICES = [('interactive_view', 'Interactive Web Viewer'), ('export_pdf', 'PDF Export Download'), ('export_excel', 'Excel (XLSX) Export'), ('export_csv', 'CSV Delimited Export'), ('export_docx', 'Word (DOCX) Export'), ('drill_through', 'Transactional Drill-Through Action')]`
  - `EXECUTION_STATUS_CHOICES = [('pending', 'Pending Execution'), ('running', 'Running Query'), ('completed', 'Completed Successfully'), ('failed', 'Execution Failed')]`
  - `OUTPUT_FORMAT_CHOICES = [('html', 'Interactive HTML'), ('pdf', 'Adobe PDF Document'), ('xlsx', 'Microsoft Excel Workbook'), ('csv', 'Comma-Separated Values (CSV)'), ('docx', 'Microsoft Word Document'), ('json', 'Raw JSON Data Payload')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `report`: `ForeignKey('bi.ReportDefinition', on_delete=CASCADE, related_name='executions')`
  - `executed_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_report_executions')`
  - `execution_mode`: `CharField(max_length=30, choices=EXECUTION_MODE_CHOICES, default='interactive_view')`
  - `execution_status`: `CharField(max_length=20, choices=EXECUTION_STATUS_CHOICES, default='completed')`
  - `started_at`: `DateTimeField(auto_now_add=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `duration_ms`: `PositiveIntegerField(default=0)`
  - `parameter_values_json`: `JSONField(default=dict)`
  - `row_count`: `PositiveIntegerField(default=0)`
  - `output_format`: `CharField(max_length=20, choices=OUTPUT_FORMAT_CHOICES, default='html')`
  - `output_file_name`: `CharField(max_length=255, blank=True)`
  - `file_size_bytes`: `PositiveIntegerField(default=0)`
  - `error_message`: `TextField(blank=True)`
  - `is_cached`: `BooleanField(default=False)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_brun_tenant_num_uniq')`
  - `Index(fields=['tenant', 'report'], name='idx_brun_ten_rpt')`
  - `Index(fields=['tenant', 'execution_status'], name='idx_brun_ten_stat')`
  - `Index(fields=['tenant', 'executed_by'], name='idx_brun_ten_exec')`
  - `Index(fields=['tenant', 'started_at'], name='idx_brun_ten_start')`

---

### 1.4 `ReportDrillPath` (`apps/bi/models/OperationalReporting/ReportDrillPaths.py`)
- **Table:** `bi_report_drill_path`
- **Number Prefix:** `BDRP` (`BDRP-00001`)
- **CHOICES:**
  - `TARGET_TYPE_CHOICES = [('subreport', 'Subreport Definition'), ('operational_report', 'Sibling Operational Report'), ('erp_record_url', 'Direct ERP Entity Detail URL')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `source_report`: `ForeignKey('bi.ReportDefinition', on_delete=CASCADE, related_name='source_drill_paths')`
  - `source_field`: `CharField(max_length=100)`
  - `drill_label`: `CharField(max_length=150)`
  - `target_type`: `CharField(max_length=30, choices=TARGET_TYPE_CHOICES, default='operational_report')`
  - `target_report`: `ForeignKey('bi.ReportDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='target_drill_paths')`
  - `target_url_pattern`: `CharField(max_length=255, blank=True)`
  - `parameter_mapping_json`: `JSONField(default=dict)`
  - `sort_order`: `PositiveIntegerField(default=10)`
  - `is_enabled`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdrp_tenant_num_uniq')`
  - `Index(fields=['tenant', 'source_report'], name='idx_bdrp_ten_srpt')`
  - `Index(fields=['tenant', 'target_report'], name='idx_bdrp_ten_trpt')`
  - `Index(fields=['tenant', 'target_type'], name='idx_bdrp_ten_ttype')`

---

## 2. Forms Contract

Forms live in `apps/bi/forms/OperationalReporting/` and re-export via `apps/bi/forms/__init__.py`.

1. `ReportDefinitionForm` (`ReportDefinitions.py`):
   - Model: `ReportDefinition`
   - Fields: `name`, `slug`, `category`, `report_type`, `paper_size`, `orientation`, `semantic_model`, `warehouse_table`, `org_unit`, `status`, `is_prebuilt_template`, `watermark_text`, `description`, `raw_query`, `styling_css`, `margins_json`, `bands_config_json`, `columns_config_json`
   - Excludes: `tenant`, `number`, `created_by`, `created_at`, `updated_at`
2. `ReportCloneForm` (`ReportDefinitions.py`):
   - Fields: `new_name`, `new_slug`
3. `ReportParameterForm` (`ReportParameters.py`):
   - Model: `ReportParameter`
   - Fields: `report`, `parameter_name`, `prompt_label`, `parameter_type`, `default_value`, `choices_source`, `choices_config_json`, `validation_regex`, `help_text`, `prompt_order`, `is_required`, `is_hidden`, `is_active`
   - Excludes: `tenant`, `number`, `created_at`, `updated_at`
4. `ReportExecutionRunForm` (`ReportExecutions.py`):
   - Model: `ReportExecution`
   - Fields: `report`, `execution_mode`, `output_format`
   - Dynamic prompt fields constructed from `report.parameters.filter(is_active=True)`
5. `ReportDrillPathForm` (`ReportDrillPaths.py`):
   - Model: `ReportDrillPath`
   - Fields: `source_report`, `source_field`, `drill_label`, `target_type`, `target_report`, `target_url_pattern`, `parameter_mapping_json`, `sort_order`, `is_enabled`
   - Excludes: `tenant`, `number`, `created_at`, `updated_at`

---

## 3. Views & Context Variables Contract

All views live in `apps/bi/views/OperationalReporting/`, decorated with `@login_required` (and `@tenant_admin_required` for destructive/schema mutations), filtering `tenant=request.tenant`.

### 3.1 `ReportDefinition` Views (`ReportDefinitions.py`)
- `report_definition_list`:
  - Context keys:
    - `page_obj`: paginated `ReportDefinition` records (list var: `reports`)
    - `reports`: `page_obj.object_list`
    - `category_choices`: `ReportDefinition.CATEGORY_CHOICES`
    - `type_choices`: `ReportDefinition.REPORT_TYPE_CHOICES`
    - `status_choices`: `ReportDefinition.STATUS_CHOICES`
    - `total_count`: total count of reports
    - `prebuilt_count`: count of pre-built templates
    - `published_count`: count of published reports
- `report_definition_detail`:
  - Context keys:
    - `report`: `ReportDefinition` instance
    - `parameters`: `report.parameters.filter(is_active=True).order_by('prompt_order')`
    - `drill_paths`: `report.source_drill_paths.filter(is_enabled=True).order_by('sort_order')`
    - `executions`: `report.executions.order_by('-started_at')[:10]`
- `report_definition_create`:
  - Context keys: `form`, `is_edit=False`
- `report_definition_edit`:
  - Context keys: `form`, `report`, `is_edit=True`
- `report_definition_delete`:
  - POST-only confirmation; redirects to `bi:report_definition_list`
- `report_definition_clone`:
  - Context keys: `form`, `report`
- `report_definition_viewer` (Interactive Web Viewer & Print):
  - Context keys:
    - `report`: `ReportDefinition` instance
    - `parameters`: active parameter definitions
    - `applied_params`: dictionary of parameter values from request.GET / POST
    - `columns`: parsed column definitions from `report.columns_config_json`
    - `rows`: executed / evaluated data rows
    - `row_count`: number of data rows
    - `drill_paths`: active drill path mappings
    - `execution`: `ReportExecution` instance created for this run
    - `is_print`: boolean (`True` when rendering print-only view)

### 3.2 `ReportParameter` Views (`ReportParameters.py`)
- `report_parameter_list`:
  - Context keys: `page_obj`, `parameters`, `type_choices`, `report_filter`
- `report_parameter_detail`:
  - Context keys: `parameter`, `report`
- `report_parameter_create`:
  - Context keys: `form`, `is_edit=False`
- `report_parameter_edit`:
  - Context keys: `form`, `parameter`, `is_edit=True`
- `report_parameter_delete`:
  - POST-only confirmation; redirects to `bi:report_parameter_list`

### 3.3 `ReportExecution` Views (`ReportExecutions.py`)
- `report_execution_list`:
  - Context keys: `page_obj`, `executions`, `status_choices`, `mode_choices`, `format_choices`
- `report_execution_detail`:
  - Context keys: `execution`, `report`
- `report_execution_run` (Trigger on-demand execution):
  - Context keys: `form`, `report`
- `report_execution_delete`:
  - POST-only confirmation; redirects to `bi:report_execution_list`
- `report_execution_export` (Download CSV/XLSX/JSON):
  - Stream/File response with proper MIME type

### 3.4 `ReportDrillPath` Views (`ReportDrillPaths.py`)
- `report_drill_path_list`:
  - Context keys: `page_obj`, `drill_paths`, `target_type_choices`, `report_filter`
- `report_drill_path_detail`:
  - Context keys: `drill_path`
- `report_drill_path_create`:
  - Context keys: `form`, `is_edit=False`
- `report_drill_path_edit`:
  - Context keys: `form`, `drill_path`, `is_edit=True`
- `report_drill_path_delete`:
  - POST-only confirmation; redirects to `bi:report_drill_path_list`

---

## 4. URL Names Contract (`app_name = 'bi'`)

All routes defined under `apps/bi/urls/OperationalReporting/` and mounted in `apps/bi/urls/__init__.py`:

```python
# ReportDefinition
path('reports/', views.report_definition_list, name='report_definition_list'),
path('reports/create/', views.report_definition_create, name='report_definition_create'),
path('reports/<int:pk>/', views.report_definition_detail, name='report_definition_detail'),
path('reports/<int:pk>/edit/', views.report_definition_edit, name='report_definition_edit'),
path('reports/<int:pk>/delete/', views.report_definition_delete, name='report_definition_delete'),
path('reports/<int:pk>/clone/', views.report_definition_clone, name='report_definition_clone'),
path('reports/<int:pk>/view/', views.report_definition_viewer, name='report_definition_viewer'),
path('reports/<int:pk>/print/', views.report_definition_print, name='report_definition_print'),

# ReportParameter
path('report-parameters/', views.report_parameter_list, name='report_parameter_list'),
path('report-parameters/create/', views.report_parameter_create, name='report_parameter_create'),
path('report-parameters/<int:pk>/', views.report_parameter_detail, name='report_parameter_detail'),
path('report-parameters/<int:pk>/edit/', views.report_parameter_edit, name='report_parameter_edit'),
path('report-parameters/<int:pk>/delete/', views.report_parameter_delete, name='report_parameter_delete'),

# ReportExecution
path('report-executions/', views.report_execution_list, name='report_execution_list'),
path('report-executions/run/<int:report_pk>/', views.report_execution_run, name='report_execution_run'),
path('report-executions/<int:pk>/', views.report_execution_detail, name='report_execution_detail'),
path('report-executions/<int:pk>/delete/', views.report_execution_delete, name='report_execution_delete'),
path('report-executions/<int:pk>/export/<str:export_format>/', views.report_execution_export, name='report_execution_export'),

# ReportDrillPath
path('report-drill-paths/', views.report_drill_path_list, name='report_drill_path_list'),
path('report-drill-paths/create/', views.report_drill_path_create, name='report_drill_path_create'),
path('report-drill-paths/<int:pk>/', views.report_drill_path_detail, name='report_drill_path_detail'),
path('report-drill-paths/<int:pk>/edit/', views.report_drill_path_edit, name='report_drill_path_edit'),
path('report-drill-paths/<int:pk>/delete/', views.report_drill_path_delete, name='report_drill_path_delete'),
```

---

## 5. Template Paths & Structure Contract

Templates live under `templates/bi/operational_reporting/` extending `templates/base.html`:

```
templates/bi/operational_reporting/
├── report_definition/
│   ├── list.html           # Catalog with search, category tabs, badges, actions
│   ├── detail.html         # Specs, band layout summary, parameters, executions, drill paths
│   ├── form.html           # Full CRUD editor for report metadata & layout bands
│   ├── clone.html          # Quick clone dialog to fork system templates
│   ├── viewer.html         # Interactive web report viewer with parameter prompt bar
│   └── print.html          # Clean print-ready layout with @media print CSS and page headers
├── report_parameter/
│   ├── list.html           # Parameters list filtered by report
│   ├── detail.html         # Parameter specs, regex, choices configuration
│   └── form.html           # Parameter CRUD editor
├── report_execution/
│   ├── list.html           # Run audit log, execution durations, row counts, download links
│   ├── detail.html         # Full execution trace, frozen parameter values, error logs
│   └── form.html           # Manual on-demand execution trigger dialog
└── report_drill_path/
    ├── list.html           # Drill-through paths table with target types
    ├── detail.html         # Parameter mapping matrix, target URL pattern
    └── form.html           # Drill path CRUD editor
```

---

## 6. Seeder Contract (`apps/bi/management/commands/seed_bi.py`)

Extend `seed_bi.py` with idempotent rows for `ReportDefinition`, `ReportParameter`, `ReportExecution`, and `ReportDrillPath`:
- Pre-built templates across core domains:
  1. **Finance**: Monthly Profit & Loss Statement (`BRPT-00001`, banded, with DateRange and OrgUnit parameters)
  2. **Sales**: Sales Pipeline & Revenue by Customer (`BRPT-00002`, tabular, with Status and SalesRep parameters)
  3. **Inventory**: Stock Valuation & Inventory Aging Schedule (`BRPT-00003`, tabular, with Warehouse parameter)
  4. **HR**: Monthly Payroll & Department Headcount Summary (`BRPT-00004`, matrix summary)
- Dynamic parameters for each report with prompt ordering, defaults, and choice sources.
- Drill paths linking customer revenue rows to CRM customer profiles and GL accounts to General Ledger lines.
- Execution history records with realistic durations (`240ms`, `850ms`), row counts (`142`, `512`), and parameter JSON.
- Idempotence: Check `ReportDefinition.objects.filter(tenant=tenant).exists()`.

---

## 7. Navigation & Live Links Contract (`apps/core/navigation.py`)

Wire `LIVE_LINKS["10.9"]` mapping all 5 NavERP.md feature bullets to live routes:
```python
"10.9": {
    "Pre-Built Report Templates": "bi:report_definition_list",
    "Pixel-Perfect & Regulatory Reports": "bi:report_definition_list",
    "Parameterized & Drill Reports": "bi:report_parameter_list",
    "Operational & Real-Time Reports": "bi:report_execution_list",
    "Multi-Format Export": "bi:report_execution_list",
},
```

---

## 8. Migration Leaf Contract

- Next sequential migration: `0022_reportdefinition_reportparameter_reportexecution_reportdrillpath.py`
- Predecessor: `0021_bidashboard_idx_bdsh_ten_created_and_more.py`
- All index names strictly `<= 30` characters.
- All CharField `max_length` strictly `>=` longest choice value.
