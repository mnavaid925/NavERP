# Contract — Sub-module 10.12: OLAP & Multidimensional Analysis (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.12 OLAP & Multidimensional Analysis • **Module:** 10 Business Intelligence • **App:** `apps/bi`
- **Date:** 2026-11-06 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended across 10.2 through 10.10). Incremental migration: `0026_...`
- **Package Layout:** `OlapAnalysis/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/olap_analysis/`.

---

## 1. Models & CHOICES Contract

All 4 top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `OlapCube` (`apps/bi/models/OlapAnalysis/OlapCubes.py`)
- **Table:** `bi_olap_cube`
- **Number Prefix:** `BOCB` (`BOCB-00001`)
- **CHOICES:**
  - `STORAGE_MODE_CHOICES = [('rolap', 'Relational OLAP (Dynamic Query)'), ('summary_rollup', 'Pre-Aggregated Summary Rollup'), ('hybrid', 'Hybrid (Fast Cache + Passthrough)')]`
  - `STATUS_CHOICES = [('draft', 'Draft Definition'), ('active', 'Active / Ready'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `storage_mode`: `CharField(max_length=20, choices=STORAGE_MODE_CHOICES, default='rolap')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='olap_cubes')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='olap_cubes')`
  - `default_hierarchy`: `ForeignKey('bi.DrillHierarchy', null=True, blank=True, on_delete=models.SET_NULL, related_name='olap_cubes')`
  - `dimensions_config`: `JSONField(default=list, help_text="Dimensional attributes, levels, and keys")`
  - `measures_config`: `JSONField(default=list, help_text="Measures, formulas, aggregations and format strings")`
  - `aggregations_config`: `JSONField(default=list, help_text="Pre-calculated cuboid grain specifications")`
  - `time_intelligence_enabled`: `BooleanField(default=True, help_text="Enables YTD, QTD, YoY, and rolling period calculations")`
  - `cache_ttl_minutes`: `PositiveIntegerField(default=60, help_text="Cache expiry in minutes for materialized aggregations")`
  - `last_refreshed_at`: `DateTimeField(null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_olap_cubes')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bocb_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bocb_tenant_num_uniq')`
  - `Index(fields=['tenant', 'storage_mode'], name='idx_bocb_ten_mode')`
  - `Index(fields=['tenant', 'status'], name='idx_bocb_ten_stat')`
  - `Index(fields=['tenant', 'created_by'], name='idx_bocb_ten_user')`

---

### 1.2 `PivotAnalysisView` (`apps/bi/models/OlapAnalysis/PivotViews.py`)
- **Table:** `bi_pivot_analysis_view`
- **Number Prefix:** `BPIV` (`BPIV-00001`)
- **CHOICES:**
  - `TOTAL_POSITION_CHOICES = [('bottom_right', 'Bottom & Right'), ('top_left', 'Top & Left'), ('none', 'No Totals')]`
  - `STATUS_CHOICES = [('active', 'Active View'), ('draft', 'Draft Exploration'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `cube`: `ForeignKey('bi.OlapCube', on_delete=models.CASCADE, related_name='pivot_views')`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `row_dimensions`: `JSONField(default=list, help_text="Ordered list of dimensions plotted along rows")`
  - `column_dimensions`: `JSONField(default=list, help_text="Ordered list of dimensions plotted along columns")`
  - `selected_measures`: `JSONField(default=list, help_text="Selected measures and aggregations")`
  - `filters_json`: `JSONField(default=list, help_text="Dimensional slicers and value filters")`
  - `show_row_subtotals`: `BooleanField(default=True)`
  - `show_col_subtotals`: `BooleanField(default=True)`
  - `show_grand_totals`: `BooleanField(default=True)`
  - `total_position`: `CharField(max_length=20, choices=TOTAL_POSITION_CHOICES, default='bottom_right')`
  - `conditional_formatting`: `JSONField(default=dict, help_text="Heatmap, threshold, and alert styling rules")`
  - `drill_through_enabled`: `BooleanField(default=True)`
  - `drill_through_target`: `CharField(max_length=150, default='accounting:journal_entry_list')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `is_favorite`: `BooleanField(default=False)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_pivot_views')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bpiv_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bpiv_tenant_num_uniq')`
  - `Index(fields=['tenant', 'cube'], name='idx_bpiv_ten_cube')`
  - `Index(fields=['tenant', 'status'], name='idx_bpiv_ten_stat')`
  - `Index(fields=['tenant', 'created_by'], name='idx_bpiv_ten_user')`

---

### 1.3 `WhatIfScenario` (`apps/bi/models/OlapAnalysis/WhatIfScenarios.py`)
- **Table:** `bi_what_if_scenario`
- **Number Prefix:** `BWIF` (`BWIF-00001`)
- **CHOICES:**
  - `STATUS_CHOICES = [('draft', 'Draft Simulation'), ('simulated', 'Simulated'), ('approved', 'Approved by Management'), ('committed', 'Committed to Ledger / Budget'), ('archived', 'Archived')]`
  - `DEFAULT_DISAGGREGATION_CHOICES = [('pro_rata', 'Pro-Rata / Proportional Splash'), ('equal', 'Equal Split Across Leaf Cells'), ('delta', 'Direct Delta Offset')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `cube`: `ForeignKey('bi.OlapCube', null=True, blank=True, on_delete=models.SET_NULL, related_name='scenarios')`
  - `baseline_budget`: `ForeignKey('accounting.Budget', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_what_if_scenarios')`
  - `fiscal_period`: `ForeignKey('accounting.FiscalPeriod', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_what_if_scenarios')`
  - `driver_parameters`: `JSONField(default=dict, help_text="Global simulation drivers: e.g. revenue_growth_pct, cost_inflation_pct")`
  - `default_disaggregation`: `CharField(max_length=20, choices=DEFAULT_DISAGGREGATION_CHOICES, default='pro_rata')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `total_baseline_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `total_adjusted_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `total_variance_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `committed_at`: `DateTimeField(null=True, blank=True)`
  - `committed_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='committed_scenarios')`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_what_if_scenarios')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bwif_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bwif_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_bwif_ten_stat')`
  - `Index(fields=['tenant', 'fiscal_period'], name='idx_bwif_ten_period')`
  - `Index(fields=['tenant', 'created_by'], name='idx_bwif_ten_user')`

---

### 1.4 `ScenarioWritebackCell` (`apps/bi/models/OlapAnalysis/WritebackCells.py`)
- **Table:** `bi_scenario_writeback_cell`
- **Number Prefix:** `BWBC` (`BWBC-00001`)
- **CHOICES:**
  - `SPREAD_METHOD_CHOICES = [('direct_leaf', 'Direct Leaf Adjustment'), ('pro_rata', 'Pro-Rata Top-Down Splash'), ('equal', 'Equal Split'), ('delta', 'Incremental Delta')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `scenario`: `ForeignKey('bi.WhatIfScenario', on_delete=models.CASCADE, related_name='writeback_cells')`
  - `gl_account`: `ForeignKey('accounting.GLAccount', null=True, blank=True, on_delete=models.SET_NULL, related_name='scenario_writeback_cells')`
  - `org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='scenario_writeback_cells')`
  - `cell_coordinates`: `JSONField(default=dict, help_text="Dimensional tuple coordinates: e.g. {'period': '2026-Q1', 'region': 'East'}")`
  - `baseline_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `adjusted_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `variance_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `spread_method`: `CharField(max_length=20, choices=SPREAD_METHOD_CHOICES, default='direct_leaf')`
  - `is_committed`: `BooleanField(default=False)`
  - `committed_budget_line`: `ForeignKey('accounting.BudgetLine', null=True, blank=True, on_delete=models.SET_NULL, related_name='bi_writeback_cells')`
  - `commentary`: `TextField(blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_writeback_cells')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bwbc_tenant_num_uniq')`
  - `Index(fields=['tenant', 'scenario'], name='idx_bwbc_ten_scen')`
  - `Index(fields=['tenant', 'gl_account'], name='idx_bwbc_ten_gl')`
  - `Index(fields=['tenant', 'org_unit'], name='idx_bwbc_ten_org')`
  - `Index(fields=['tenant', 'is_committed'], name='idx_bwbc_ten_sync')`

---

## 2. Forms Contract (`apps/bi/forms/OlapAnalysis/`)

### 2.1 `OlapCubeForm` (`OlapCubes.py`)
- **Model:** `OlapCube`
- **Fields:** `['name', 'slug', 'description', 'storage_mode', 'semantic_model', 'warehouse_table', 'default_hierarchy', 'dimensions_config', 'measures_config', 'aggregations_config', 'time_intelligence_enabled', 'cache_ttl_minutes', 'status']`
- **Excludes:** `['tenant', 'number', 'last_refreshed_at', 'created_by']`

### 2.2 `PivotAnalysisViewForm` (`PivotViews.py`)
- **Model:** `PivotAnalysisView`
- **Fields:** `['cube', 'name', 'slug', 'description', 'row_dimensions', 'column_dimensions', 'selected_measures', 'filters_json', 'show_row_subtotals', 'show_col_subtotals', 'show_grand_totals', 'total_position', 'conditional_formatting', 'drill_through_enabled', 'drill_through_target', 'status', 'is_favorite']`
- **Excludes:** `['tenant', 'number', 'created_by']`

### 2.3 `WhatIfScenarioForm` (`WhatIfScenarios.py`)
- **Model:** `WhatIfScenario`
- **Fields:** `['name', 'slug', 'description', 'cube', 'baseline_budget', 'fiscal_period', 'driver_parameters', 'default_disaggregation', 'status']`
- **Excludes:** `['tenant', 'number', 'total_baseline_amount', 'total_adjusted_amount', 'total_variance_amount', 'committed_at', 'committed_by', 'created_by']`

### 2.4 `ScenarioWritebackCellForm` (`WritebackCells.py`)
- **Model:** `ScenarioWritebackCell`
- **Fields:** `['scenario', 'gl_account', 'org_unit', 'cell_coordinates', 'baseline_value', 'adjusted_value', 'spread_method', 'commentary']`
- **Excludes:** `['tenant', 'number', 'variance_amount', 'is_committed', 'committed_budget_line', 'created_by']`

---

## 3. URLs Contract (`apps/bi/urls/OlapAnalysis/`)

Namespace: `bi` (via `apps/bi/urls/__init__.py`)

### 3.1 `OlapCubes.py`
- `olap/cubes/` -> `name='olap_cube_list'`
- `olap/cubes/create/` -> `name='olap_cube_create'`
- `olap/cubes/<int:pk>/` -> `name='olap_cube_detail'`
- `olap/cubes/<int:pk>/edit/` -> `name='olap_cube_edit'`
- `olap/cubes/<int:pk>/delete/` -> `name='olap_cube_delete'`
- `olap/cubes/<int:pk>/refresh/` -> `name='olap_cube_refresh'`

### 3.2 `PivotViews.py`
- `olap/pivots/` -> `name='pivot_view_list'`
- `olap/pivots/create/` -> `name='pivot_view_create'`
- `olap/pivots/<int:pk>/` -> `name='pivot_view_detail'`
- `olap/pivots/<int:pk>/edit/` -> `name='pivot_view_edit'`
- `olap/pivots/<int:pk>/delete/` -> `name='pivot_view_delete'`
- `olap/pivots/<int:pk>/matrix/` -> `name='pivot_view_matrix'`

### 3.3 `WhatIfScenarios.py`
- `olap/scenarios/` -> `name='what_if_scenario_list'`
- `olap/scenarios/create/` -> `name='what_if_scenario_create'`
- `olap/scenarios/<int:pk>/` -> `name='what_if_scenario_detail'`
- `olap/scenarios/<int:pk>/edit/` -> `name='what_if_scenario_edit'`
- `olap/scenarios/<int:pk>/delete/` -> `name='what_if_scenario_delete'`
- `olap/scenarios/<int:pk>/simulate/` -> `name='what_if_scenario_simulate'`
- `olap/scenarios/<int:pk>/commit/` -> `name='what_if_scenario_commit'`

### 3.4 `WritebackCells.py`
- `olap/writeback-cells/` -> `name='writeback_cell_list'`
- `olap/writeback-cells/create/` -> `name='writeback_cell_create'`
- `olap/writeback-cells/<int:pk>/` -> `name='writeback_cell_detail'`
- `olap/writeback-cells/<int:pk>/edit/` -> `name='writeback_cell_edit'`
- `olap/writeback-cells/<int:pk>/delete/` -> `name='writeback_cell_delete'`

---

## 4. Views & Context Variables Contract (`apps/bi/views/OlapAnalysis/`)

### 4.1 `OlapCubes.py`
- `olap_cube_list`:
  - `cubes`: QuerySet of `OlapCube`
  - `page_obj`: Paginator page
  - `total_count`: Integer count
  - `status_choices`: `OlapCube.STATUS_CHOICES`
  - `storage_mode_choices`: `OlapCube.STORAGE_MODE_CHOICES`
- `olap_cube_detail`:
  - `cube`: `OlapCube` instance
  - `pivot_views`: Related `PivotAnalysisView` QuerySet
  - `scenarios`: Related `WhatIfScenario` QuerySet
- `olap_cube_create` / `olap_cube_edit`:
  - `form`: `OlapCubeForm`
  - `cube`: `OlapCube` instance (if edit)
  - `is_edit`: Boolean

### 4.2 `PivotViews.py`
- `pivot_view_list`:
  - `views`: QuerySet of `PivotAnalysisView`
  - `page_obj`: Paginator page
  - `total_count`: Integer count
  - `cubes`: Tenant `OlapCube` QuerySet for filter dropdown
  - `status_choices`: `PivotAnalysisView.STATUS_CHOICES`
- `pivot_view_detail`:
  - `view`: `PivotAnalysisView` instance
- `pivot_view_matrix` (Interactive Pivot Workspace):
  - `view`: `PivotAnalysisView` instance
  - `cube`: `OlapCube` instance
  - `matrix_rows`: Nested list of dimensional row headers and cell values
  - `col_headers`: List of column headers
  - `grand_totals`: Dict of calculated column/row summaries
- `pivot_view_create` / `pivot_view_edit`:
  - `form`: `PivotAnalysisViewForm`
  - `view`: `PivotAnalysisView` instance (if edit)
  - `is_edit`: Boolean

### 4.3 `WhatIfScenarios.py`
- `what_if_scenario_list`:
  - `scenarios`: QuerySet of `WhatIfScenario`
  - `page_obj`: Paginator page
  - `total_count`: Integer count
  - `status_choices`: `WhatIfScenario.STATUS_CHOICES`
  - `fiscal_periods`: Tenant `FiscalPeriod` QuerySet
- `what_if_scenario_detail`:
  - `scenario`: `WhatIfScenario` instance
  - `writeback_cells`: Related `ScenarioWritebackCell` QuerySet
- `what_if_scenario_simulate` (Simulation Workbench):
  - `scenario`: `WhatIfScenario` instance
  - `writeback_cells`: QuerySet of adjustments
  - `baseline_total`: Decimal
  - `adjusted_total`: Decimal
  - `variance_total`: Decimal
  - `driver_parameters`: Dict
- `what_if_scenario_create` / `what_if_scenario_edit`:
  - `form`: `WhatIfScenarioForm`
  - `scenario`: `WhatIfScenario` instance (if edit)
  - `is_edit`: Boolean

### 4.4 `WritebackCells.py`
- `writeback_cell_list`:
  - `cells`: QuerySet of `ScenarioWritebackCell`
  - `page_obj`: Paginator page
  - `total_count`: Integer count
  - `scenarios`: Tenant `WhatIfScenario` QuerySet
  - `spread_method_choices`: `ScenarioWritebackCell.SPREAD_METHOD_CHOICES`
- `writeback_cell_detail`:
  - `cell`: `ScenarioWritebackCell` instance
- `writeback_cell_create` / `writeback_cell_edit`:
  - `form`: `ScenarioWritebackCellForm`
  - `cell`: `ScenarioWritebackCell` instance (if edit)
  - `is_edit`: Boolean

---

## 5. Templates Contract (`templates/bi/olap_analysis/`)

- `olap_cube/list.html`
- `olap_cube/detail.html`
- `olap_cube/form.html`
- `pivot_view/list.html`
- `pivot_view/detail.html`
- `pivot_view/form.html`
- `pivot_view/matrix.html` (Interactive Pivot Workspace)
- `what_if_scenario/list.html`
- `what_if_scenario/detail.html`
- `what_if_scenario/form.html`
- `what_if_scenario/simulate.html` (Simulation Workbench)
- `writeback_cell/list.html`
- `writeback_cell/detail.html`
- `writeback_cell/form.html`

All templates extend `base.html`, use design-system CSS classes (`card`, `table`, `table-wrap`, `btn`, `btn-primary`, `btn-outline`, `btn-danger`, `badge-green`, `badge-amber`, `badge-red`, `badge-info`, `badge-slate`), Lucide icons, and CSRF tokens on all POST forms.

---

## 6. Navigation `LIVE_LINKS["10.12"]` Contract

In `apps/core/navigation.py`:
```python
LIVE_LINKS["10.12"] = {
    "OLAP Cubes & Aggregations": "bi:olap_cube_list",
    "Pivot & Cross-Tab Analysis": "bi:pivot_view_list",
    "Drill-Down, Up & Through": "bi:pivot_view_list",
    "Time Intelligence": "bi:olap_cube_list",
    "What-If & Writeback": "bi:what_if_scenario_list",
}
```
Mapped 100% to NavERP.md 10.12 feature bullets.
