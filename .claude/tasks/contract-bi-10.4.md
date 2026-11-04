# Contract — Sub-module 10.4: Data Modeling & Semantic Layer (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.4 Data Modeling & Semantic Layer · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-04 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended in 10.2 & 10.3). Incremental migration: `0011_...`
- **Package Layout:** `SemanticLayer/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/semantic_layer/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `SemanticModel` (`apps/bi/models/SemanticLayer/SemanticModels.py`)
- **Table:** `bi_semantic_model`
- **Number Prefix:** `BSMD` (`BSMD-00001`)
- **CHOICES:**
  - `MODEL_TYPE_CHOICES = [('fact', 'Fact Model'), ('dimension', 'Dimension Model'), ('bridge', 'Bridge / Disambiguation Model'), ('virtual_view', 'Virtual Analytical View'), ('reusable_dataset', 'Certified Reusable Dataset')]`
  - `SCD_TYPE_CHOICES = [('type_0', 'Type 0: Fixed / Non-Changing'), ('type_1', 'Type 1: Overwrite In-Place'), ('type_2', 'Type 2: Historical Versioning (Start/End Date)'), ('type_3', 'Type 3: Previous Value Tracking')]`
  - `ACCESS_TIER_CHOICES = [('public', 'Public (Tenant-Wide)'), ('department', 'Departmental Only'), ('restricted', 'Restricted / Confidential')]`
  - `CERTIFICATION_STATUS_CHOICES = [('draft', 'Draft / In Development'), ('in_review', 'Under Review & Validation'), ('certified', 'Certified Single Source of Truth'), ('deprecated', 'Deprecated / Sunset Pending')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=50)`
  - `model_type`: `CharField(max_length=25, choices=MODEL_TYPE_CHOICES, default='fact')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', on_delete=SET_NULL, null=True, blank=True, related_name='semantic_models')`
  - `data_mart`: `ForeignKey('bi.DataMart', on_delete=SET_NULL, null=True, blank=True, related_name='semantic_models')`
  - `primary_key_column`: `CharField(max_length=100, default='id')`
  - `natural_key_columns`: `CharField(max_length=255, blank=True)`
  - `grain_description`: `CharField(max_length=255, blank=True)`
  - `is_conformed_dimension`: `BooleanField(default=False)`
  - `scd_type`: `CharField(max_length=20, choices=SCD_TYPE_CHOICES, default='type_1')`
  - `is_virtual_view`: `BooleanField(default=False)`
  - `sql_definition`: `TextField(blank=True)`
  - `access_tier`: `CharField(max_length=25, choices=ACCESS_TIER_CHOICES, default='department')`
  - `certification_status`: `CharField(max_length=25, choices=CERTIFICATION_STATUS_CHOICES, default='draft')`
  - `certified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='+')`
  - `certified_at`: `DateTimeField(null=True, blank=True)`
  - `certification_notes`: `TextField(blank=True)`
  - `source_fingerprint`: `CharField(max_length=64, blank=True)`
  - `last_introspected_at`: `DateTimeField(null=True, blank=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='bi_semantic_models_owned')`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_bsmd_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bsmd_tenant_num_uniq')`
  - `Index(fields=['tenant', 'model_type'], name='idx_bsmd_ten_mtype')`
  - `Index(fields=['tenant', 'certification_status'], name='idx_bsmd_ten_cert')`
  - `Index(fields=['tenant', 'warehouse_table'], name='idx_bsmd_ten_whtbl')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bsmd_ten_active')`

---

### 1.2 `BusinessGlossaryTerm` (`apps/bi/models/SemanticLayer/BusinessGlossaryTerms.py`)
- **Table:** `bi_business_glossary_term`
- **Number Prefix:** `BGLO` (`BGLO-00001`)
- **CHOICES:**
  - `DOMAIN_CATEGORY_CHOICES = [('finance', 'Finance & Accounting'), ('sales', 'Sales & Commercial'), ('marketing', 'Marketing & Demand Gen'), ('hr', 'Human Resources & People'), ('supply_chain', 'Supply Chain & Inventory'), ('operations', 'Operations & Manufacturing'), ('general', 'General Enterprise')]`
  - `CERTIFICATION_STATUS_CHOICES = [('draft', 'Draft / In Development'), ('in_review', 'Under Review & Validation'), ('certified', 'Certified Corporate Standard'), ('deprecated', 'Deprecated / Superseded')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=50)`
  - `domain_category`: `CharField(max_length=30, choices=DOMAIN_CATEGORY_CHOICES, default='finance')`
  - `short_definition`: `CharField(max_length=300)`
  - `full_definition`: `TextField(blank=True)`
  - `calculation_rule`: `TextField(blank=True)`
  - `synonyms`: `CharField(max_length=255, blank=True)`
  - `steward`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='bi_glossary_terms_stewarded')`
  - `org_unit`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='bi_glossary_terms')`
  - `certification_status`: `CharField(max_length=25, choices=CERTIFICATION_STATUS_CHOICES, default='draft')`
  - `certified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='+')`
  - `certified_at`: `DateTimeField(null=True, blank=True)`
  - `certification_notes`: `TextField(blank=True)`
  - `related_terms`: `ManyToManyField('self', blank=True, symmetrical=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_bglo_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bglo_tenant_num_uniq')`
  - `Index(fields=['tenant', 'domain_category'], name='idx_bglo_ten_domain')`
  - `Index(fields=['tenant', 'certification_status'], name='idx_bglo_ten_cert')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bglo_ten_active')`

---

### 1.3 `CalculatedMeasure` (`apps/bi/models/SemanticLayer/CalculatedMeasures.py`)
- **Table:** `bi_calculated_measure`
- **Number Prefix:** `BCMS` (`BCMS-00001`)
- **CHOICES:**
  - `AGGREGATION_TYPE_CHOICES = [('sum', 'Sum'), ('avg', 'Average'), ('count', 'Count'), ('count_distinct', 'Count Distinct'), ('min', 'Minimum'), ('max', 'Maximum'), ('formula', 'Custom Calculated Expression / Ratio')]`
  - `TIME_INTELLIGENCE_CHOICES = [('none', 'None (Standard Aggregation)'), ('yoy_growth', 'Year-over-Year (YoY) Growth %'), ('qtd', 'Quarter-to-Date (QTD)'), ('ytd', 'Year-to-Date (YTD)'), ('rolling_30d', 'Rolling 30-Day Moving Sum/Avg'), ('prior_period', 'Prior Period Difference')]`
  - `FORMAT_STRING_CHOICES = [('currency', 'Currency ($#,##0.00)'), ('percentage', 'Percentage (0.00%)'), ('integer', 'Whole Number (#,##0)'), ('decimal', 'Decimal Number (#,##0.00)'), ('raw', 'Raw Unformatted')]`
  - `DISPLAY_UNITS_CHOICES = [('auto', 'Auto-Scale (K/M/B)'), ('none', 'None (Raw Value)'), ('thousands', 'Thousands (K)'), ('millions', 'Millions (M)'), ('billions', 'Billions (B)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', on_delete=CASCADE, related_name='measures')`
  - `glossary_term`: `ForeignKey('bi.BusinessGlossaryTerm', on_delete=SET_NULL, null=True, blank=True, related_name='measures')`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=50)`
  - `aggregation_type`: `CharField(max_length=25, choices=AGGREGATION_TYPE_CHOICES, default='sum')`
  - `source_column`: `CharField(max_length=100, blank=True)`
  - `formula_expression`: `CharField(max_length=500, blank=True)`
  - `filter_expression`: `CharField(max_length=500, blank=True)`
  - `time_intelligence`: `CharField(max_length=25, choices=TIME_INTELLIGENCE_CHOICES, default='none')`
  - `format_string`: `CharField(max_length=25, choices=FORMAT_STRING_CHOICES, default='decimal')`
  - `display_units`: `CharField(max_length=20, choices=DISPLAY_UNITS_CHOICES, default='auto')`
  - `target_value`: `DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)`
  - `warning_threshold`: `DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)`
  - `critical_threshold`: `DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'semantic_model', 'code'], name='bi_bcms_tenant_model_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bcms_tenant_num_uniq')`
  - `Index(fields=['tenant', 'aggregation_type'], name='idx_bcms_ten_agg')`
  - `Index(fields=['tenant', 'time_intelligence'], name='idx_bcms_ten_ti')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bcms_ten_active')`

---

### 1.4 `DrillHierarchy` (`apps/bi/models/SemanticLayer/DrillHierarchies.py`)
- **Table:** `bi_drill_hierarchy`
- **Number Prefix:** `BDHI` (`BDHI-00001`)
- **CHOICES:**
  - `HIERARCHY_TYPE_CHOICES = [('time', 'Calendar / Fiscal Time (Year -> Quarter -> Month -> Day)'), ('geography', 'Geographical Territory (Region -> Country -> State -> City)'), ('organizational', 'Organizational Unit (Company -> Division -> Department)'), ('product', 'Product Catalog (Category -> Subcategory -> Item)'), ('custom', 'Custom Business Dimension Path')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', on_delete=CASCADE, related_name='drill_hierarchies')`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=50)`
  - `hierarchy_type`: `CharField(max_length=25, choices=HIERARCHY_TYPE_CHOICES, default='time')`
  - `levels_json`: `JSONField(default=list)`
  - `primary_drill_path`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'semantic_model', 'code'], name='bi_bdhi_tenant_model_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdhi_tenant_num_uniq')`
  - `Index(fields=['tenant', 'hierarchy_type'], name='idx_bdhi_ten_htype')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdhi_ten_active')`

---

## 2. Forms Contract (`apps/bi/forms/SemanticLayer/`)

- **`SemanticModelForm`** (`SemanticModelForms.py`):
  - Model: `SemanticModel`
  - Fields: `['name', 'code', 'model_type', 'warehouse_table', 'data_mart', 'primary_key_column', 'natural_key_columns', 'grain_description', 'is_conformed_dimension', 'scd_type', 'is_virtual_view', 'sql_definition', 'access_tier', 'certification_status', 'owner', 'description', 'is_active']`
  - Excludes: `['tenant', 'number', 'certified_by', 'certified_at', 'certification_notes', 'source_fingerprint', 'last_introspected_at', 'created_at', 'updated_at']`
  - Scoping in `__init__`: `warehouse_table` filtered by `tenant=tenant`, `data_mart` filtered by `tenant=tenant`, `owner` filtered by active users in tenant.

- **`SemanticModelCertificationForm`** (`SemanticModelForms.py`):
  - Form class: `forms.Form`
  - Fields: `certification_status` (ChoiceField), `certification_notes` (CharField, widget=Textarea)

- **`BusinessGlossaryTermForm`** (`BusinessGlossaryTermForms.py`):
  - Model: `BusinessGlossaryTerm`
  - Fields: `['name', 'code', 'domain_category', 'short_definition', 'full_definition', 'calculation_rule', 'synonyms', 'steward', 'org_unit', 'certification_status', 'certification_notes', 'related_terms', 'is_active']`
  - Excludes: `['tenant', 'number', 'certified_by', 'certified_at', 'created_at', 'updated_at']`
  - Scoping in `__init__`: `steward` filtered by active users, `org_unit` filtered by `tenant=tenant`, `related_terms` filtered by `tenant=tenant`.

- **`BusinessGlossaryTermCertificationForm`** (`BusinessGlossaryTermForms.py`):
  - Form class: `forms.Form`
  - Fields: `certification_status` (ChoiceField), `certification_notes` (CharField, widget=Textarea)

- **`CalculatedMeasureForm`** (`CalculatedMeasureForms.py`):
  - Model: `CalculatedMeasure`
  - Fields: `['semantic_model', 'glossary_term', 'name', 'code', 'aggregation_type', 'source_column', 'formula_expression', 'filter_expression', 'time_intelligence', 'format_string', 'display_units', 'target_value', 'warning_threshold', 'critical_threshold', 'description', 'is_active']`
  - Excludes: `['tenant', 'number', 'created_at', 'updated_at']`
  - Scoping in `__init__`: `semantic_model` filtered by `tenant=tenant`, `glossary_term` filtered by `tenant=tenant`.

- **`DrillHierarchyForm`** (`DrillHierarchyForms.py`):
  - Model: `DrillHierarchy`
  - Fields: `['semantic_model', 'name', 'code', 'hierarchy_type', 'levels_json', 'primary_drill_path', 'description', 'is_active']`
  - Excludes: `['tenant', 'number', 'created_at', 'updated_at']`
  - Scoping in `__init__`: `semantic_model` filtered by `tenant=tenant`.

---

## 3. URLs Contract (`apps/bi/urls/SemanticLayer/`)

All URL paths under `bi:` namespace:

| Pattern | View Function | URL Name | Description |
|---|---|---|---|
| `semantic/` | `semantic_overview` | `bi:semantic_overview` | Command center overview dashboard |
| `semantic/models/` | `semantic_model_list` | `bi:semantic_model_list` | Semantic models list page with filters |
| `semantic/models/create/` | `semantic_model_create` | `bi:semantic_model_create` | Semantic model create form |
| `semantic/models/<int:pk>/` | `semantic_model_detail` | `bi:semantic_model_detail` | Semantic model detail view |
| `semantic/models/<int:pk>/edit/` | `semantic_model_edit` | `bi:semantic_model_edit` | Semantic model edit form |
| `semantic/models/<int:pk>/delete/` | `semantic_model_delete` | `bi:semantic_model_delete` | Semantic model POST delete |
| `semantic/models/<int:pk>/certify/` | `semantic_model_certify` | `bi:semantic_model_certify` | Certify model status transition |
| `semantic/models/<int:pk>/introspect/` | `semantic_model_introspect` | `bi:semantic_model_introspect` | Schema introspection & auto-sync |
| `semantic/glossary/` | `business_glossary_term_list` | `bi:business_glossary_term_list` | Glossary terms list with category filters |
| `semantic/glossary/create/` | `business_glossary_term_create` | `bi:business_glossary_term_create` | Glossary term create form |
| `semantic/glossary/<int:pk>/` | `business_glossary_term_detail` | `bi:business_glossary_term_detail` | Glossary term detail view |
| `semantic/glossary/<int:pk>/edit/` | `business_glossary_term_edit` | `bi:business_glossary_term_edit` | Glossary term edit form |
| `semantic/glossary/<int:pk>/delete/` | `business_glossary_term_delete` | `bi:business_glossary_term_delete` | Glossary term POST delete |
| `semantic/glossary/<int:pk>/certify/` | `business_glossary_term_certify` | `bi:business_glossary_term_certify` | Certify glossary term |
| `semantic/measures/` | `calculated_measure_list` | `bi:calculated_measure_list` | Calculated measures list with filters |
| `semantic/measures/create/` | `calculated_measure_create` | `bi:calculated_measure_create` | Calculated measure create form |
| `semantic/measures/<int:pk>/` | `calculated_measure_detail` | `bi:calculated_measure_detail` | Calculated measure detail view |
| `semantic/measures/<int:pk>/edit/` | `calculated_measure_edit` | `bi:calculated_measure_edit` | Calculated measure edit form |
| `semantic/measures/<int:pk>/delete/` | `calculated_measure_delete` | `bi:calculated_measure_delete` | Calculated measure POST delete |
| `semantic/hierarchies/` | `drill_hierarchy_list` | `bi:drill_hierarchy_list` | Drill hierarchies list with filters |
| `semantic/hierarchies/create/` | `drill_hierarchy_create` | `bi:drill_hierarchy_create` | Drill hierarchy create form |
| `semantic/hierarchies/<int:pk>/` | `drill_hierarchy_detail` | `bi:drill_hierarchy_detail` | Drill hierarchy detail view |
| `semantic/hierarchies/<int:pk>/edit/` | `drill_hierarchy_edit` | `bi:drill_hierarchy_edit` | Drill hierarchy edit form |
| `semantic/hierarchies/<int:pk>/delete/` | `drill_hierarchy_delete` | `bi:drill_hierarchy_delete` | Drill hierarchy POST delete |

---

## 4. View Context Keys Contract (L7 / L8 PINNED)

### 4.1 Overview View (`semantic_overview`)
- `total_models`: integer count of tenant's semantic models
- `total_certified_models`: count of certified models
- `total_glossary_terms`: integer count of glossary terms
- `total_certified_terms`: count of certified glossary terms
- `total_measures`: integer count of calculated measures
- `total_hierarchies`: integer count of drill hierarchies
- `recent_models`: queryset of top 5 recently updated semantic models
- `recent_terms`: queryset of top 5 recently updated glossary terms
- `model_type_counts`: dictionary or list of counts per `model_type`
- `domain_term_counts`: dictionary or list of counts per `domain_category`

### 4.2 SemanticModel Views
- **List View (`semantic_model_list`)**:
  - `models` / `semantic_models` / `object_list`: paginated page object
  - `page_obj`: paginated page object
  - `is_paginated`: boolean
  - `total_count`: total records before pagination
  - `search_query`: `request.GET.get('q', '')` (clamped to 100 chars)
  - `model_type_filter`: `request.GET.get('model_type', '')`
  - `certification_status_filter`: `request.GET.get('certification_status', '')`
  - `scd_type_filter`: `request.GET.get('scd_type', '')`
  - `data_mart_filter`: `request.GET.get('data_mart', '')`
  - `model_type_choices`: `SemanticModel.MODEL_TYPE_CHOICES`
  - `certification_status_choices`: `SemanticModel.CERTIFICATION_STATUS_CHOICES`
  - `scd_type_choices`: `SemanticModel.SCD_TYPE_CHOICES`
  - `data_marts`: `DataMart.objects.filter(tenant=request.tenant)`
- **Detail View (`semantic_model_detail`)**:
  - `model` / `semantic_model` / `object`: the `SemanticModel` instance
  - `measures`: related `CalculatedMeasure` queryset
  - `drill_hierarchies`: related `DrillHierarchy` queryset
  - `certify_form`: `SemanticModelCertificationForm`
- **Form Views (`create`, `edit`)**:
  - `form`: `SemanticModelForm` instance
  - `model` / `semantic_model` / `object`: `SemanticModel` instance (in edit mode)
  - `is_edit`: boolean

### 4.3 BusinessGlossaryTerm Views
- **List View (`business_glossary_term_list`)**:
  - `terms` / `glossary_terms` / `object_list`: paginated page object
  - `page_obj`: paginated page object
  - `is_paginated`: boolean
  - `total_count`: total records before pagination
  - `search_query`: `request.GET.get('q', '')`
  - `domain_filter`: `request.GET.get('domain', '')`
  - `certification_status_filter`: `request.GET.get('certification_status', '')`
  - `domain_category_choices`: `BusinessGlossaryTerm.DOMAIN_CATEGORY_CHOICES`
  - `certification_status_choices`: `BusinessGlossaryTerm.CERTIFICATION_STATUS_CHOICES`
- **Detail View (`business_glossary_term_detail`)**:
  - `term` / `glossary_term` / `object`: the `BusinessGlossaryTerm` instance
  - `related_measures`: measures referencing this term
  - `certify_form`: `BusinessGlossaryTermCertificationForm`
- **Form Views (`create`, `edit`)**:
  - `form`: `BusinessGlossaryTermForm` instance
  - `term` / `glossary_term` / `object`: `BusinessGlossaryTerm` instance (in edit mode)
  - `is_edit`: boolean

### 4.4 CalculatedMeasure Views
- **List View (`calculated_measure_list`)**:
  - `measures` / `calculated_measures` / `object_list`: paginated page object
  - `page_obj`: paginated page object
  - `is_paginated`: boolean
  - `total_count`: total count
  - `search_query`: `request.GET.get('q', '')`
  - `model_filter`: `request.GET.get('model', '')`
  - `aggregation_filter`: `request.GET.get('aggregation', '')`
  - `time_intelligence_filter`: `request.GET.get('time_intelligence', '')`
  - `aggregation_type_choices`: `CalculatedMeasure.AGGREGATION_TYPE_CHOICES`
  - `time_intelligence_choices`: `CalculatedMeasure.TIME_INTELLIGENCE_CHOICES`
  - `semantic_models`: `SemanticModel.objects.filter(tenant=request.tenant)`
- **Detail View (`calculated_measure_detail`)**:
  - `measure` / `calculated_measure` / `object`: the `CalculatedMeasure` instance
- **Form Views (`create`, `edit`)**:
  - `form`: `CalculatedMeasureForm` instance
  - `measure` / `calculated_measure` / `object`: `CalculatedMeasure` instance (in edit mode)
  - `is_edit`: boolean

### 4.5 DrillHierarchy Views
- **List View (`drill_hierarchy_list`)**:
  - `hierarchies` / `drill_hierarchies` / `object_list`: paginated page object
  - `page_obj`: paginated page object
  - `is_paginated`: boolean
  - `total_count`: total count
  - `search_query`: `request.GET.get('q', '')`
  - `hierarchy_type_filter`: `request.GET.get('hierarchy_type', '')`
  - `model_filter`: `request.GET.get('model', '')`
  - `hierarchy_type_choices`: `DrillHierarchy.HIERARCHY_TYPE_CHOICES`
  - `semantic_models`: `SemanticModel.objects.filter(tenant=request.tenant)`
- **Detail View (`drill_hierarchy_detail`)**:
  - `hierarchy` / `drill_hierarchy` / `object`: the `DrillHierarchy` instance
- **Form Views (`create`, `edit`)**:
  - `form`: `DrillHierarchyForm` instance
  - `hierarchy` / `drill_hierarchy` / `object`: `DrillHierarchy` instance (in edit mode)
  - `is_edit`: boolean
