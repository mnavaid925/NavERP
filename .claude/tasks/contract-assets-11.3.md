# Contract — Sub-module 11.3: Asset Classification & Categorization (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.3 Asset Classification & Categorization • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-08 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0005_...`.
- **Package Layout:** `AssetClassification/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/asset_classification/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetCategory` (`apps/assets/models/AssetClassification/AssetCategories.py`)
- **Table:** `assets_category`
- **Number Prefix:** `ACAT` (format: `ACAT-00001`)
- **CHOICES:**
  - `CATEGORY_TYPE_CHOICES = [('machinery', 'Machinery & Equipment'), ('facility', 'Facility & Building Component'), ('vehicle', 'Fleet & Mobile Equipment'), ('it_hardware', 'IT & Communication Hardware'), ('tooling', 'Tooling & Test Instruments'), ('furniture', 'Furniture & Fixtures'), ('infrastructure', 'Utility & Civil Infrastructure'), ('electrical', 'Electrical Distribution'), ('piping', 'Piping & Fluid Systems'), ('other', 'Other Capital Asset')]`
  - `DEPRECIATION_METHOD_CHOICES = [('straight_line', 'Straight Line'), ('declining_balance', 'Declining Balance (150%)'), ('double_declining', 'Double Declining Balance (200%)'), ('sum_of_years', 'Sum-of-Years Digits'), ('none', 'No Depreciation (Land/CIP)')]`
  - `MAINTENANCE_STRATEGY_CHOICES = [('preventive_calendar', 'Calendar-Based PM'), ('preventive_meter', 'Meter/Usage-Based PM'), ('condition_based', 'Condition-Based Monitoring (CBM)'), ('predictive', 'Predictive Maintenance (PdM)'), ('run_to_failure', 'Run to Failure (Corrective Only)')]`
  - `CRITICALITY_CHOICES = [('critical', 'Critical (Class A)'), ('high', 'High (Class B)'), ('medium', 'Medium (Class B)'), ('low', 'Low (Class C)')]`
  - `STATUS_CSS = {'active': 'badge-green', 'inactive': 'badge-muted'}`
  - `CRITICALITY_CSS = {'critical': 'badge-red', 'high': 'badge-amber', 'medium': 'badge-info', 'low': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_categories')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `code`: `CharField(max_length=32, db_index=True, help_text='Short taxonomy code, e.g. HVAC-CHL, PUMP-CENT')`
  - `name`: `CharField(max_length=150)`
  - `parent`: `ForeignKey('self', on_delete=SET_NULL, null=True, blank=True, related_name='children', help_text='Parent classification node')`
  - `category_type`: `CharField(max_length=24, choices=CATEGORY_TYPE_CHOICES, default='machinery')`
  - `unspsc_code`: `CharField(max_length=16, blank=True, help_text='8-digit UNSPSC commodity code')`
  - `unspsc_title`: `CharField(max_length=150, blank=True, help_text='UNSPSC commodity category title')`
  - `default_depreciation_method`: `CharField(max_length=20, choices=DEPRECIATION_METHOD_CHOICES, default='straight_line')`
  - `default_useful_life_months`: `PositiveIntegerField(default=60, help_text='Standard accounting useful life in months')`
  - `default_maintenance_strategy`: `CharField(max_length=24, choices=MAINTENANCE_STRATEGY_CHOICES, default='preventive_calendar')`
  - `default_criticality`: `CharField(max_length=10, choices=CRITICALITY_CHOICES, default='medium')`
  - `description`: `TextField(blank=True)`
  - `display_order`: `PositiveIntegerField(default=10)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='assets_acat_ten_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_acat_ten_num_uniq')`
  - `Index(fields=['tenant', 'category_type'], name='idx_acat_ten_type')`
  - `Index(fields=['tenant', 'parent'], name='idx_acat_ten_parent')`
  - `Index(fields=['tenant', 'is_active'], name='idx_acat_ten_active')`

---

### 1.2 `AssetModel` (`apps/assets/models/AssetClassification/AssetModels.py`)
- **Table:** `assets_model`
- **Number Prefix:** `AMOD` (format: `AMOD-00001`)
- **CHOICES:**
  - `WARRANTY_COVERAGE_CHOICES = [('full_parts_labor', 'Full Warranty (Parts & Labor)'), ('parts_only', 'Parts Only'), ('powertrain_only', 'Powertrain / Core Component Only'), ('limited', 'Limited Commercial Warranty'), ('no_warranty', 'As-Is / No Warranty')]`
  - `MODEL_STATUS_CHOICES = [('active', 'Active Production'), ('phased_out', 'Phased Out / Legacy'), ('discontinued', 'Discontinued / Obsolete'), ('draft', 'Draft Engineering')]`
  - `STATUS_CSS = {'active': 'badge-green', 'phased_out': 'badge-amber', 'discontinued': 'badge-red', 'draft': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_models')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `model_number`: `CharField(max_length=64, db_index=True, help_text='Manufacturer model identifier')`
  - `name`: `CharField(max_length=200, help_text='Commercial model name / series')`
  - `category`: `ForeignKey('assets.AssetCategory', on_delete=PROTECT, related_name='models')`
  - `manufacturer`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='asset_models')`
  - `manufacturer_name_fallback`: `CharField(max_length=120, blank=True, help_text='Fallback manufacturer name if Party not assigned')`
  - `description`: `TextField(blank=True)`
  - `standard_warranty_months`: `PositiveIntegerField(default=12)`
  - `warranty_coverage_type`: `CharField(max_length=24, choices=WARRANTY_COVERAGE_CHOICES, default='full_parts_labor')`
  - `expected_useful_life_months`: `PositiveIntegerField(default=60)`
  - `default_meter_name`: `CharField(max_length=40, blank=True, help_text='Primary operating meter, e.g. Operating Hours, Cycles, Kilometers')`
  - `default_meter_unit`: `CharField(max_length=16, blank=True, help_text='e.g. h, km, cycles')`
  - `estimated_replacement_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
  - `model_status`: `CharField(max_length=20, choices=MODEL_STATUS_CHOICES, default='active')`
  - `technical_specifications`: `TextField(blank=True, help_text='Engineering specifications overview and operating parameters')`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'model_number'], name='assets_amod_ten_modnum_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_amod_ten_num_uniq')`
  - `Index(fields=['tenant', 'category'], name='idx_amod_ten_cat')`
  - `Index(fields=['tenant', 'manufacturer'], name='idx_amod_ten_mfr')`
  - `Index(fields=['tenant', 'model_status'], name='idx_amod_ten_status')`

---

### 1.3 `AssetCriticalityAssessment` (`apps/assets/models/AssetClassification/AssetCriticalityAssessments.py`)
- **Table:** `assets_criticality_assessment`
- **Number Prefix:** `ACRT` (format: `ACRT-00001`)
- **CHOICES:**
  - `ABC_RATING_CHOICES = [('A', 'Class A - Critical / Mission-Essential'), ('B', 'Class B - Important / Severe Impact'), ('C', 'Class C - Standard / Low Impact')]`
  - `STRATEGY_CHOICES = [('rcm_predictive', 'RCM / Predictive (PdM)'), ('rigorous_pm', 'Rigorous Preventive (Time/Meter PM)'), ('standard_pm', 'Standard Preventive Maintenance'), ('run_to_failure', 'Run-to-Failure (Corrective)')]`
  - `STATUS_CHOICES = [('draft', 'Draft Assessment'), ('reviewed', 'Under Peer Review'), ('approved', 'Approved & Active'), ('superseded', 'Superseded by Newer Audit')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'reviewed': 'badge-info', 'approved': 'badge-green', 'superseded': 'badge-muted'}`
  - `ABC_CSS = {'A': 'badge-red', 'B': 'badge-amber', 'C': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_criticality_assessments')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='criticality_assessments')`
  - `assessor`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='asset_assessments')`
  - `assessment_date`: `DateField(default=timezone.now)`
  - `safety_impact`: `PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)], help_text='Scale 1 (Negligible) to 5 (Fatality / Severe Hazard)')`
  - `environmental_impact`: `PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)], help_text='Scale 1 (Zero release) to 5 (Major toxic release / EPA breach)')`
  - `operational_downtime_impact`: `PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)], help_text='Scale 1 (No impact) to 5 (Full plant stoppage / Bottleneck)')`
  - `financial_impact`: `PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)], help_text='Scale 1 (<$1k) to 5 (Catastrophic repair >$250k)')`
  - `regulatory_compliance_impact`: `PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)], help_text='Scale 1 (Minor internal) to 5 (Loss of operating license)')`
  - `is_single_point_of_failure`: `BooleanField(default=False, help_text='No active redundancy or backup asset exists in the plant (+5 score bonus)')`
  - `composite_score`: `PositiveSmallIntegerField(default=5, help_text='Calculated sum of consequence scores + SPOF penalty')`
  - `abc_rating`: `CharField(max_length=1, choices=ABC_RATING_CHOICES, default='C')`
  - `recommended_strategy`: `CharField(max_length=24, choices=STRATEGY_CHOICES, default='standard_pm')`
  - `assessment_status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='draft')`
  - `review_cycle_months`: `PositiveIntegerField(default=12)`
  - `next_assessment_due`: `DateField(null=True, blank=True)`
  - `findings_and_mitigation`: `TextField(blank=True)`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='approved_asset_assessments')`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_acrt_ten_num_uniq')`
  - `Index(fields=['tenant', 'asset'], name='idx_acrt_ten_asset')`
  - `Index(fields=['tenant', 'assessment_status'], name='idx_acrt_ten_status')`
  - `Index(fields=['tenant', 'abc_rating'], name='idx_acrt_ten_abc')`
  - `Index(fields=['tenant', 'assessment_date'], name='idx_acrt_ten_date')`

---

### 1.4 `AssetSpecificationTemplate` (`apps/assets/models/AssetClassification/AssetSpecificationTemplates.py`)
- **Table:** `assets_specification_template`
- **Number Prefix:** `ASPC` (format: `ASPC-00001`)
- **CHOICES:**
  - `DATA_TYPE_CHOICES = [('text', 'Text / Alphanumeric'), ('number', 'Numeric (Decimal / Integer)'), ('boolean', 'Yes / No (Boolean)'), ('date', 'Date'), ('select', 'Dropdown Selection')]`
  - `DATA_TYPE_CSS = {'text': 'badge-info', 'number': 'badge-green', 'boolean': 'badge-amber', 'date': 'badge-slate', 'select': 'badge-purple'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_spec_templates')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `attribute_key`: `CharField(max_length=50, db_index=True, help_text='Machine-readable attribute key, e.g. rated_voltage')`
  - `display_name`: `CharField(max_length=120, help_text='Human-readable label, e.g. Rated Operating Voltage')`
  - `category`: `ForeignKey('assets.AssetCategory', on_delete=CASCADE, null=True, blank=True, related_name='spec_templates')`
  - `model`: `ForeignKey('assets.AssetModel', on_delete=CASCADE, null=True, blank=True, related_name='spec_templates')`
  - `data_type`: `CharField(max_length=16, choices=DATA_TYPE_CHOICES, default='text')`
  - `unit_of_measure`: `CharField(max_length=24, blank=True, help_text='e.g. V, kW, PSI, GPM, RPM, ton')`
  - `default_value`: `CharField(max_length=255, blank=True)`
  - `dropdown_options`: `TextField(blank=True, help_text='Comma-separated values for select data type')`
  - `min_numeric_value`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `max_numeric_value`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `validation_regex`: `CharField(max_length=120, blank=True)`
  - `is_required`: `BooleanField(default=False)`
  - `is_filterable`: `BooleanField(default=True)`
  - `display_order`: `PositiveIntegerField(default=10)`
  - `help_text`: `CharField(max_length=255, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_aspc_ten_num_uniq')`
  - `Index(fields=['tenant', 'category'], name='idx_aspc_ten_cat')`
  - `Index(fields=['tenant', 'model'], name='idx_aspc_ten_model')`
  - `Index(fields=['tenant', 'attribute_key'], name='idx_aspc_ten_attrkey')`
  - `Index(fields=['tenant', 'data_type'], name='idx_aspc_ten_dtype')`

---

## 2. Forms Contract & Exclusions

All forms inherit from `apps.core.forms.TenantModelForm` + `TenantUniqueMixin`.

| Form Class | Model | Excluded Fields | Clean / Validation Rules |
|------------|-------|-----------------|--------------------------|
| `AssetCategoryForm` | `AssetCategory` | `tenant`, `number`, `created_at`, `updated_at` | `clean_parent`: loop prevention (detect circular hierarchy up to 10 hops). `clean_code`: uppercase alphanumeric slug. `reject_foreign(form, cleaned, ['parent'])`. |
| `AssetModelForm` | `AssetModel` | `tenant`, `number`, `created_at`, `updated_at` | `reject_foreign(form, cleaned, ['category', 'manufacturer'])`. `clean_model_number`: uppercase/trim. |
| `AssetCriticalityAssessmentForm` | `AssetCriticalityAssessment` | `tenant`, `number`, `composite_score`, `abc_rating`, `assessment_status`, `approved_by`, `approved_at`, `created_at`, `updated_at` | `reject_foreign(form, cleaned, ['asset', 'assessor'])`. Bounds check 1..5 for all 5 impact fields. Auto-computes composite score and ABC rating on save. |
| `AssetSpecificationTemplateForm` | `AssetSpecificationTemplate` | `tenant`, `number`, `created_at`, `updated_at` | `reject_foreign(form, cleaned, ['category', 'model'])`. Require at least one of `category` or `model`. `clean_attribute_key`: lowercase snake_case identifier. |

---

## 3. URLs Contract (`apps/assets/urls/AssetClassification/`)

All routes mounted under `assets:` namespace (`app_name = "assets"`).

| Entity | Pattern | URL Name | View Function |
|--------|---------|----------|---------------|
| `AssetCategory` | `categories/` | `asset_category_list` | `asset_category_list` |
| | `categories/create/` | `asset_category_create` | `asset_category_create` |
| | `categories/<int:pk>/` | `asset_category_detail` | `asset_category_detail` |
| | `categories/<int:pk>/edit/` | `asset_category_edit` | `asset_category_edit` |
| | `categories/<int:pk>/delete/` | `asset_category_delete` | `asset_category_delete` |
| `AssetModel` | `models/` | `asset_model_list` | `asset_model_list` |
| | `models/create/` | `asset_model_create` | `asset_model_create` |
| | `models/<int:pk>/` | `asset_model_detail` | `asset_model_detail` |
| | `models/<int:pk>/edit/` | `asset_model_edit` | `asset_model_edit` |
| | `models/<int:pk>/delete/` | `asset_model_delete` | `asset_model_delete` |
| `AssetCriticalityAssessment` | `criticality-assessments/` | `asset_criticality_assessment_list` | `asset_criticality_assessment_list` |
| | `criticality-assessments/create/` | `asset_criticality_assessment_create` | `asset_criticality_assessment_create` |
| | `criticality-assessments/<int:pk>/` | `asset_criticality_assessment_detail` | `asset_criticality_assessment_detail` |
| | `criticality-assessments/<int:pk>/edit/` | `asset_criticality_assessment_edit` | `asset_criticality_assessment_edit` |
| | `criticality-assessments/<int:pk>/delete/` | `asset_criticality_assessment_delete` | `asset_criticality_assessment_delete` |
| | `criticality-assessments/<int:pk>/approve/` | `asset_criticality_assessment_approve` | `asset_criticality_assessment_approve` |
| `AssetSpecificationTemplate` | `spec-templates/` | `asset_specification_template_list` | `asset_specification_template_list` |
| | `spec-templates/create/` | `asset_specification_template_create` | `asset_specification_template_create` |
| | `spec-templates/<int:pk>/` | `asset_specification_template_detail` | `asset_specification_template_detail` |
| | `spec-templates/<int:pk>/edit/` | `asset_specification_template_edit` | `asset_specification_template_edit` |
| | `spec-templates/<int:pk>/delete/` | `asset_specification_template_delete` | `asset_specification_template_delete` |

---

## 4. View Context Keys Contract (L7 / L8 PINNED)

Every view must pass these exact context keys.

### 4.1 `AssetCategory`
- **List (`asset_category_list`):**
  - `page_obj`: paginated `AssetCategory` queryset
  - `category_list`: alias list for `page_obj.object_list`
  - `category_types`: `AssetCategory.CATEGORY_TYPE_CHOICES`
  - `parent_categories`: `AssetCategory.objects.filter(tenant=request.tenant, parent__isnull=True)`
  - `search_query`: `request.GET.get('q', '')`
  - `selected_type`: `request.GET.get('type', '')`
  - `selected_parent`: `request.GET.get('parent', '')`
- **Detail (`asset_category_detail`):**
  - `category`: the `AssetCategory` object (pinned object var!)
  - `children`: child categories
  - `models`: related `AssetModel` records
  - `spec_templates`: related specification templates
- **Create / Edit (`asset_category_create` / `asset_category_edit`):**
  - `form`: `AssetCategoryForm`
  - `category`: `AssetCategory` object in edit mode (None in create mode)

### 4.2 `AssetModel`
- **List (`asset_model_list`):**
  - `page_obj`: paginated `AssetModel` queryset
  - `model_list`: alias list for `page_obj.object_list`
  - `model_statuses`: `AssetModel.MODEL_STATUS_CHOICES`
  - `categories`: `AssetCategory.objects.filter(tenant=request.tenant, is_active=True)`
  - `search_query`: `request.GET.get('q', '')`
  - `selected_status`: `request.GET.get('status', '')`
  - `selected_category`: `request.GET.get('category', '')`
- **Detail (`asset_model_detail`):**
  - `model`: the `AssetModel` object (pinned object var!)
  - `spec_templates`: related specification templates
  - `deployed_assets`: related `scm.Asset` records matching model number
- **Create / Edit (`asset_model_create` / `asset_model_edit`):**
  - `form`: `AssetModelForm`
  - `model`: `AssetModel` object in edit mode (None in create mode)

### 4.3 `AssetCriticalityAssessment`
- **List (`asset_criticality_assessment_list`):**
  - `page_obj`: paginated `AssetCriticalityAssessment` queryset
  - `assessment_list`: alias list for `page_obj.object_list`
  - `abc_choices`: `AssetCriticalityAssessment.ABC_RATING_CHOICES`
  - `status_choices`: `AssetCriticalityAssessment.STATUS_CHOICES`
  - `search_query`: `request.GET.get('q', '')`
  - `selected_abc`: `request.GET.get('abc', '')`
  - `selected_status`: `request.GET.get('status', '')`
- **Detail (`asset_criticality_assessment_detail`):**
  - `assessment`: the `AssetCriticalityAssessment` object (pinned object var!)
- **Create / Edit (`asset_criticality_assessment_create` / `asset_criticality_assessment_edit`):**
  - `form`: `AssetCriticalityAssessmentForm`
  - `assessment`: `AssetCriticalityAssessment` object in edit mode (None in create mode)

### 4.4 `AssetSpecificationTemplate`
- **List (`asset_specification_template_list`):**
  - `page_obj`: paginated `AssetSpecificationTemplate` queryset
  - `template_list`: alias list for `page_obj.object_list`
  - `data_types`: `AssetSpecificationTemplate.DATA_TYPE_CHOICES`
  - `categories`: `AssetCategory.objects.filter(tenant=request.tenant, is_active=True)`
  - `search_query`: `request.GET.get('q', '')`
  - `selected_type`: `request.GET.get('type', '')`
  - `selected_category`: `request.GET.get('category', '')`
- **Detail (`asset_specification_template_detail`):**
  - `template`: the `AssetSpecificationTemplate` object (pinned object var!)
- **Create / Edit (`asset_specification_template_create` / `asset_specification_template_edit`):**
  - `form`: `AssetSpecificationTemplateForm`
  - `template`: `AssetSpecificationTemplate` object in edit mode (None in create mode)

---

## 5. Navigation LIVE_LINKS Wiring (`apps/core/navigation.py`)

`LIVE_LINKS["11.3"]` mapping:
```python
    "11.3": {
        "Asset Hierarchy & Taxonomy": "assets:asset_category_list",
        "Asset Type & Model Management": "assets:asset_model_list",
        "Criticality & Risk Classification": "assets:asset_criticality_assessment_list",
        "Asset Lifecycle Stage Tracking": "assets:asset_model_list",
        "Custom Attributes & Specifications": "assets:asset_specification_template_list",
        # Plural and convenience aliases
        "Asset Categories": "assets:asset_category_list",
        "Asset Models": "assets:asset_model_list",
        "Criticality Assessments": "assets:asset_criticality_assessment_list",
        "Specification Templates": "assets:asset_specification_template_list",
        "Taxonomy & Classification": "assets:asset_category_list",
    },
```
