# Contract — Sub-module 10.11: KPI & Performance Scorecards (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.11 KPI & Performance Scorecards · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-06 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (extended across 10.1 through 10.10). Incremental migration: `0026_...`
- **Package Layout:** `PerformanceScorecards/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/kpi_performance_scorecards/`.

---

## 1. Models & CHOICES Contract

All 4 top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `KpiDefinition` (`apps/bi/models/PerformanceScorecards/KpiDefinitions.py`)
- **Table:** `bi_kpi_definition`
- **Number Prefix:** `BKPI` (`BKPI-00001`)
- **CHOICES:**
  - `PERSPECTIVE_CHOICES = [('financial', 'Financial'), ('customer', 'Customer'), ('internal_process', 'Internal Business Process'), ('learning_growth', 'Learning & Growth')]`
  - `DIRECTION_CHOICES = [('maximize', 'Maximize (Higher is Better)'), ('minimize', 'Minimize (Lower is Better)'), ('in_range', 'In Range (Target Band)')]`
  - `UOM_CHOICES = [('percentage', 'Percentage (%)'), ('currency', 'Currency Amount ($)'), ('count', 'Integer Count (#)'), ('days', 'Days / Duration'), ('hours', 'Hours / Time'), ('ratio', 'Ratio / Decimal'), ('score', 'Index / Score (0-100)')]`
  - `FREQUENCY_CHOICES = [('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annual')]`
  - `CALC_TYPE_CHOICES = [('manual', 'Manual Entry / Qualitative'), ('semantic_measure', 'Governed Semantic Measure (10.4)'), ('formula_expression', 'Calculated Formula Expression'), ('aggregation', 'Database Aggregate')]`
  - `STATUS_CHOICES = [('draft', 'Draft Setup'), ('active', 'Active / In Production'), ('under_review', 'Under Review'), ('deprecated', 'Deprecated'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `code`: `CharField(max_length=50)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `category`: `CharField(max_length=60, default='operations')`
  - `perspective`: `CharField(max_length=30, choices=PERSPECTIVE_CHOICES, default='internal_process')`
  - `target_direction`: `CharField(max_length=20, choices=DIRECTION_CHOICES, default='maximize')`
  - `unit_of_measure`: `CharField(max_length=20, choices=UOM_CHOICES, default='percentage')`
  - `tracking_frequency`: `CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')`
  - `calculation_type`: `CharField(max_length=30, choices=CALC_TYPE_CHOICES, default='manual')`
  - `semantic_measure`: `ForeignKey('bi.CalculatedMeasure', null=True, blank=True, on_delete=models.SET_NULL, related_name='kpi_definitions')`
  - `formula_expression`: `CharField(max_length=500, blank=True)`
  - `target_value`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `warning_threshold`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `critical_threshold`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `current_value`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `previous_value`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `industry_benchmark_value`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `benchmark_source`: `CharField(max_length=150, blank=True)`
  - `benchmark_percentile`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `is_active`: `BooleanField(default=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_kpis')`
  - `department`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='kpi_definitions')`
  - `last_calculated_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bkpi_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bkpi_tenant_num_uniq')`
  - `Index(fields=['tenant', 'code'], name='idx_bkpi_ten_code')`
  - `Index(fields=['tenant', 'perspective'], name='idx_bkpi_ten_persp')`
  - `Index(fields=['tenant', 'status'], name='idx_bkpi_ten_stat')`
  - `Index(fields=['tenant', 'owner'], name='idx_bkpi_ten_owner')`

---

### 1.2 `PerformanceScorecard` (`apps/bi/models/PerformanceScorecards/PerformanceScorecards.py`)
- **Table:** `bi_performance_scorecard`
- **Number Prefix:** `BSCR` (`BSCR-00001`)
- **CHOICES:**
  - `SCORECARD_TYPE_CHOICES = [('balanced_scorecard', 'Balanced Scorecard (4 Perspectives)'), ('executive', 'Executive Leadership Scorecard'), ('departmental', 'Departmental Operating Scorecard'), ('operational', 'Operational Excellence Scorecard'), ('strategic_initiative', 'Strategic Initiative Scorecard')]`
  - `PERIOD_CHOICES = [('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('semi_annual', 'Semi-Annual'), ('annual', 'Annual'), ('rolling_12_months', 'Rolling 12 Months')]`
  - `RAG_STATUS_CHOICES = [('green', 'Green (On Track)'), ('amber', 'Amber (Needs Attention)'), ('red', 'Red (Critical / Off Track)'), ('gray', 'Gray (Not Evaluated)')]`
  - `STATUS_CHOICES = [('draft', 'Draft Setup'), ('active', 'Active Scorecard'), ('in_review', 'In Review / Audit'), ('closed', 'Closed Period'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `scorecard_type`: `CharField(max_length=30, choices=SCORECARD_TYPE_CHOICES, default='balanced_scorecard')`
  - `review_period`: `CharField(max_length=20, choices=PERIOD_CHOICES, default='quarterly')`
  - `fiscal_year`: `PositiveIntegerField(default=2026)`
  - `financial_weight`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('25.00'))`
  - `customer_weight`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('25.00'))`
  - `internal_process_weight`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('25.00'))`
  - `learning_growth_weight`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('25.00'))`
  - `overall_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `overall_rag_status`: `CharField(max_length=10, choices=RAG_STATUS_CHOICES, default='gray')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `is_default`: `BooleanField(default=False)`
  - `is_published`: `BooleanField(default=False)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_scorecards')`
  - `org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='performance_scorecards')`
  - `last_recalculated_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bscr_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bscr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'scorecard_type'], name='idx_bscr_ten_type')`
  - `Index(fields=['tenant', 'status'], name='idx_bscr_ten_stat')`
  - `Index(fields=['tenant', 'owner'], name='idx_bscr_ten_owner')`
  - `Index(fields=['tenant', 'fiscal_year'], name='idx_bscr_ten_fyr')`

---

### 1.3 `ScorecardKpiAssignment` (`apps/bi/models/PerformanceScorecards/ScorecardKpiAssignments.py`)
- **Table:** `bi_scorecard_kpi_assignment`
- **Number Prefix:** `BSCI` (`BSCI-00001`)
- **CHOICES:**
  - `PERSPECTIVE_CHOICES = [('financial', 'Financial'), ('customer', 'Customer'), ('internal_process', 'Internal Business Process'), ('learning_growth', 'Learning & Growth')]`
  - `RAG_STATUS_CHOICES = [('green', 'Green (On Track)'), ('amber', 'Amber (Needs Attention)'), ('red', 'Red (Critical / Off Track)'), ('gray', 'Gray (Not Evaluated)')]`
  - `TREND_CHOICES = [('improving', 'Improving (↗)'), ('steady', 'Steady / Neutral (→)'), ('deteriorating', 'Deteriorating (↘)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `scorecard`: `ForeignKey('bi.PerformanceScorecard', on_delete=CASCADE, related_name='kpi_assignments')`
  - `kpi`: `ForeignKey('bi.KpiDefinition', on_delete=CASCADE, related_name='scorecard_assignments')`
  - `objective`: `ForeignKey('bi.StrategicObjective', null=True, blank=True, on_delete=models.SET_NULL, related_name='scorecard_kpis')`
  - `perspective`: `CharField(max_length=30, choices=PERSPECTIVE_CHOICES, default='internal_process')`
  - `weight`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))`
  - `target_value`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `actual_value`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `variance`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))`
  - `variance_percentage`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal('0.00'))`
  - `rag_status`: `CharField(max_length=10, choices=RAG_STATUS_CHOICES, default='gray')`
  - `trend_direction`: `CharField(max_length=20, choices=TREND_CHOICES, default='steady')`
  - `normalized_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `benchmark_overlay_value`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `benchmark_gap`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)`
  - `manager_notes`: `TextField(blank=True)`
  - `sort_order`: `PositiveIntegerField(default=10)`
  - `evaluated_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bsci_tenant_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'scorecard', 'kpi'], name='bi_bsci_ten_sc_kpi_uniq')`
  - `Index(fields=['tenant', 'scorecard'], name='idx_bsci_ten_sc')`
  - `Index(fields=['tenant', 'kpi'], name='idx_bsci_ten_kpi')`
  - `Index(fields=['tenant', 'rag_status'], name='idx_bsci_ten_rag')`
  - `Index(fields=['tenant', 'perspective'], name='idx_bsci_ten_persp')`

---

### 1.4 `StrategicObjective` (`apps/bi/models/PerformanceScorecards/StrategicObjectives.py`)
- **Table:** `bi_strategic_objective`
- **Number Prefix:** `BOBJ` (`BOBJ-00001`)
- **CHOICES:**
  - `PERSPECTIVE_CHOICES = [('financial', 'Financial'), ('customer', 'Customer'), ('internal_process', 'Internal Business Process'), ('learning_growth', 'Learning & Growth')]`
  - `RAG_STATUS_CHOICES = [('green', 'Green (On Track)'), ('amber', 'Amber (Needs Attention)'), ('red', 'Red (Critical / Off Track)'), ('gray', 'Gray (Not Evaluated)')]`
  - `STATUS_CHOICES = [('proposed', 'Proposed / Draft'), ('active', 'Active Strategy'), ('achieved', 'Achieved / Completed'), ('postponed', 'Postponed'), ('canceled', 'Canceled')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `code`: `CharField(max_length=50)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `perspective`: `CharField(max_length=30, choices=PERSPECTIVE_CHOICES, default='financial')`
  - `statement_of_intent`: `TextField(blank=True)`
  - `parent_objective`: `ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_objectives')`
  - `target_date`: `DateField(null=True, blank=True)`
  - `rag_status`: `CharField(max_length=10, choices=RAG_STATUS_CHOICES, default='gray')`
  - `alignment_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_strategic_objectives')`
  - `org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='strategic_objectives')`
  - `sort_order`: `PositiveIntegerField(default=10)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bobj_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bobj_tenant_num_uniq')`
  - `Index(fields=['tenant', 'perspective'], name='idx_bobj_ten_persp')`
  - `Index(fields=['tenant', 'status'], name='idx_bobj_ten_stat')`
  - `Index(fields=['tenant', 'parent_objective'], name='idx_bobj_ten_parent')`

---

## 2. Forms Contract

### 2.1 `KpiDefinitionForm`
- **Model:** `KpiDefinition`
- **Fields:** `['code', 'name', 'slug', 'description', 'category', 'perspective', 'target_direction', 'unit_of_measure', 'tracking_frequency', 'calculation_type', 'semantic_measure', 'formula_expression', 'target_value', 'warning_threshold', 'critical_threshold', 'current_value', 'previous_value', 'industry_benchmark_value', 'benchmark_source', 'benchmark_percentile', 'status', 'is_active', 'owner', 'department']`
- **Excludes:** `['tenant', 'number', 'last_calculated_at', 'created_at', 'updated_at']`

### 2.2 `PerformanceScorecardForm`
- **Model:** `PerformanceScorecard`
- **Fields:** `['name', 'slug', 'description', 'scorecard_type', 'review_period', 'fiscal_year', 'financial_weight', 'customer_weight', 'internal_process_weight', 'learning_growth_weight', 'status', 'is_default', 'is_published', 'owner', 'org_unit']`
- **Excludes:** `['tenant', 'number', 'overall_score', 'overall_rag_status', 'last_recalculated_at', 'created_at', 'updated_at']`

### 2.3 `ScorecardKpiAssignmentForm`
- **Model:** `ScorecardKpiAssignment`
- **Fields:** `['scorecard', 'kpi', 'objective', 'perspective', 'weight', 'target_value', 'actual_value', 'benchmark_overlay_value', 'manager_notes', 'sort_order']`
- **Excludes:** `['tenant', 'number', 'variance', 'variance_percentage', 'rag_status', 'trend_direction', 'normalized_score', 'benchmark_gap', 'evaluated_at', 'created_at', 'updated_at']`

### 2.4 `ScorecardKpiRecordActualForm`
- **Model:** `ScorecardKpiAssignment`
- **Fields:** `['actual_value', 'manager_notes']`

### 2.5 `StrategicObjectiveForm`
- **Model:** `StrategicObjective`
- **Fields:** `['code', 'name', 'slug', 'perspective', 'statement_of_intent', 'parent_objective', 'target_date', 'status', 'owner', 'org_unit', 'sort_order']`
- **Excludes:** `['tenant', 'number', 'rag_status', 'alignment_score', 'created_at', 'updated_at']`

---

## 3. URLs & Routing Contract

### URL Name Format: `bi:<entity>_<action>`
- **KpiDefinition:**
  - `bi:kpi_definition_list` -> `/bi/performance-scorecards/kpis/`
  - `bi:kpi_definition_create` -> `/bi/performance-scorecards/kpis/create/`
  - `bi:kpi_definition_detail` -> `/bi/performance-scorecards/kpis/<int:pk>/`
  - `bi:kpi_definition_edit` -> `/bi/performance-scorecards/kpis/<int:pk>/edit/`
  - `bi:kpi_definition_delete` -> `/bi/performance-scorecards/kpis/<int:pk>/delete/`
  - `bi:kpi_definition_refresh` -> `/bi/performance-scorecards/kpis/<int:pk>/refresh/`
- **PerformanceScorecard:**
  - `bi:performance_scorecard_list` -> `/bi/performance-scorecards/scorecards/`
  - `bi:performance_scorecard_create` -> `/bi/performance-scorecards/scorecards/create/`
  - `bi:performance_scorecard_detail` -> `/bi/performance-scorecards/scorecards/<int:pk>/`
  - `bi:performance_scorecard_edit` -> `/bi/performance-scorecards/scorecards/<int:pk>/edit/`
  - `bi:performance_scorecard_delete` -> `/bi/performance-scorecards/scorecards/<int:pk>/delete/`
  - `bi:performance_scorecard_recalculate` -> `/bi/performance-scorecards/scorecards/<int:pk>/recalculate/`
  - `bi:performance_scorecard_strategy_map` -> `/bi/performance-scorecards/scorecards/<int:pk>/strategy-map/`
- **ScorecardKpiAssignment:**
  - `bi:scorecard_kpi_assignment_list` -> `/bi/performance-scorecards/assignments/`
  - `bi:scorecard_kpi_assignment_create` -> `/bi/performance-scorecards/assignments/create/`
  - `bi:scorecard_kpi_assignment_detail` -> `/bi/performance-scorecards/assignments/<int:pk>/`
  - `bi:scorecard_kpi_assignment_edit` -> `/bi/performance-scorecards/assignments/<int:pk>/edit/`
  - `bi:scorecard_kpi_assignment_delete` -> `/bi/performance-scorecards/assignments/<int:pk>/delete/`
  - `bi:scorecard_kpi_assignment_record_actual` -> `/bi/performance-scorecards/assignments/<int:pk>/record-actual/`
- **StrategicObjective:**
  - `bi:strategic_objective_list` -> `/bi/performance-scorecards/objectives/`
  - `bi:strategic_objective_create` -> `/bi/performance-scorecards/objectives/create/`
  - `bi:strategic_objective_detail` -> `/bi/performance-scorecards/objectives/<int:pk>/`
  - `bi:strategic_objective_edit` -> `/bi/performance-scorecards/objectives/<int:pk>/edit/`
  - `bi:strategic_objective_delete` -> `/bi/performance-scorecards/objectives/<int:pk>/delete/`

---

## 4. View Context Keys Contract (L7 / L8 PINNED)

### 4.1 `kpi_definition_list`
- `kpis`: Paginated `Page` object of `KpiDefinition` records
- `status_choices`: `KpiDefinition.STATUS_CHOICES`
- `perspective_choices`: `KpiDefinition.PERSPECTIVE_CHOICES`
- `direction_choices`: `KpiDefinition.DIRECTION_CHOICES`
- `calc_type_choices`: `KpiDefinition.CALC_TYPE_CHOICES`
- `departments`: `OrgUnit.objects.filter(tenant=request.tenant)`
- `stats`: `{'total': int, 'active': int, 'under_review': int, 'on_target': int}`

### 4.2 `kpi_definition_detail`
- `kpi`: `KpiDefinition` instance
- `assignments`: Related `ScorecardKpiAssignment` records

### 4.3 `kpi_definition_create` / `kpi_definition_edit`
- `form`: `KpiDefinitionForm`
- `kpi`: `KpiDefinition` instance (or `None` on create)
- `is_edit`: `bool`

### 4.4 `performance_scorecard_list`
- `scorecards`: Paginated `Page` object of `PerformanceScorecard` records
- `type_choices`: `PerformanceScorecard.SCORECARD_TYPE_CHOICES`
- `status_choices`: `PerformanceScorecard.STATUS_CHOICES`
- `rag_choices`: `PerformanceScorecard.RAG_STATUS_CHOICES`
- `period_choices`: `PerformanceScorecard.PERIOD_CHOICES`
- `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
- `stats`: `{'total': int, 'active': int, 'on_track': int, 'needs_attention': int, 'critical': int}`

### 4.5 `performance_scorecard_detail`
- `scorecard`: `PerformanceScorecard` instance
- `financial_kpis`: QuerySet of assignments (`perspective='financial'`)
- `customer_kpis`: QuerySet of assignments (`perspective='customer'`)
- `process_kpis`: QuerySet of assignments (`perspective='internal_process'`)
- `learning_kpis`: QuerySet of assignments (`perspective='learning_growth'`)
- `perspective_scores`: Dictionary of perspective completion scores

### 4.6 `performance_scorecard_create` / `performance_scorecard_edit`
- `form`: `PerformanceScorecardForm`
- `scorecard`: `PerformanceScorecard` instance (or `None` on create)
- `is_edit`: `bool`

### 4.7 `performance_scorecard_strategy_map`
- `scorecard`: `PerformanceScorecard` instance
- `financial_objectives`: QuerySet of `StrategicObjective` (`perspective='financial'`)
- `customer_objectives`: QuerySet of `StrategicObjective` (`perspective='customer'`)
- `process_objectives`: QuerySet of `StrategicObjective` (`perspective='internal_process'`)
- `learning_objectives`: QuerySet of `StrategicObjective` (`perspective='learning_growth'`)
- `strategy_stats`: `{'total_objectives': int, 'achieved': int, 'on_track': int}`

### 4.8 `scorecard_kpi_assignment_list`
- `assignments`: Paginated `Page` object of `ScorecardKpiAssignment` records
- `scorecards`: `PerformanceScorecard.objects.filter(tenant=request.tenant)`
- `perspective_choices`: `ScorecardKpiAssignment.PERSPECTIVE_CHOICES`
- `rag_choices`: `ScorecardKpiAssignment.RAG_STATUS_CHOICES`
- `trend_choices`: `ScorecardKpiAssignment.TREND_CHOICES`
- `stats`: `{'total': int, 'on_track': int, 'improving': int, 'critical': int}`

### 4.9 `scorecard_kpi_assignment_detail`
- `assignment`: `ScorecardKpiAssignment` instance

### 4.10 `scorecard_kpi_assignment_create` / `scorecard_kpi_assignment_edit`
- `form`: `ScorecardKpiAssignmentForm`
- `assignment`: `ScorecardKpiAssignment` instance (or `None` on create)
- `is_edit`: `bool`

### 4.11 `strategic_objective_list`
- `objectives`: Paginated `Page` object of `StrategicObjective` records
- `perspective_choices`: `StrategicObjective.PERSPECTIVE_CHOICES`
- `status_choices`: `StrategicObjective.STATUS_CHOICES`
- `rag_choices`: `StrategicObjective.RAG_STATUS_CHOICES`
- `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
- `stats`: `{'total': int, 'active': int, 'achieved': int, 'on_track': int}`

### 4.12 `strategic_objective_detail`
- `objective`: `StrategicObjective` instance
- `child_objectives`: QuerySet of child `StrategicObjective` records
- `assigned_kpis`: QuerySet of linked `ScorecardKpiAssignment` records

### 4.13 `strategic_objective_create` / `strategic_objective_edit`
- `form`: `StrategicObjectiveForm`
- `objective`: `StrategicObjective` instance (or `None` on create)
- `is_edit`: `bool`

---

## 5. Navigation Wire-Up (`LIVE_LINKS["10.11"]`)
In `apps/core/navigation.py`:
```python
"10.11": {
    "KPI Library & Definitions": "bi:kpi_definition_list",
    "Scorecards & Balanced Scorecard": "bi:performance_scorecard_list",
    "Goal & Target Tracking": "bi:scorecard_kpi_assignment_list",
    "Benchmarking": "bi:kpi_definition_list",
    "Strategy Maps & Alignment": "bi:strategic_objective_list",
},
```
