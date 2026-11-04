# Contract — Sub-module 10.5: Data Quality & Cleansing (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.5 Data Quality & Cleansing · **Module:** 10 Business Intelligence · **App:** `apps/bi`
- **Date:** 2026-11-04 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended in 10.2, 10.3, 10.4). Incremental migration: `0013_...`
- **Package Layout:** `DataQuality/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/data_quality/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `DataQualityProfile` (`apps/bi/models/DataQuality/DataQualityProfiles.py`)
- **Table:** `bi_data_quality_profile`
- **Number Prefix:** `BDQP` (`BDQP-00001`)
- **CHOICES:**
  - `TARGET_TYPE_CHOICES = [('warehouse_table', 'Warehouse Table'), ('semantic_model', 'Semantic Model')]`
  - `STATUS_CHOICES = [('pending', 'Pending / Scheduled'), ('profiling', 'Profiling In Progress'), ('completed', 'Completed Successfully'), ('failed', 'Profiling Failed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `target_type`: `CharField(max_length=25, choices=TARGET_TYPE_CHOICES, default='warehouse_table')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.CASCADE, related_name='quality_profiles')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.CASCADE, related_name='quality_profiles')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='pending')`
  - `total_row_count`: `BigIntegerField(default=0)`
  - `total_column_count`: `PositiveIntegerField(default=0)`
  - `completeness_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `uniqueness_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `validity_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `column_profiles_json`: `JSONField(default=list)`
  - `profiled_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')`
  - `profiled_at`: `DateTimeField(null=True, blank=True)`
  - `duration_seconds`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `error_message`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdqp_tenant_num_uniq')`
  - `Index(fields=['tenant', 'target_type'], name='idx_bdqp_ten_ttype')`
  - `Index(fields=['tenant', 'status'], name='idx_bdqp_ten_status')`
  - `Index(fields=['tenant', 'warehouse_table'], name='idx_bdqp_ten_whtbl')`
  - `Index(fields=['tenant', 'semantic_model'], name='idx_bdqp_ten_smd')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdqp_ten_active')`

---

### 1.2 `DataQualityRule` (`apps/bi/models/DataQuality/DataQualityRules.py`)
- **Table:** `bi_data_quality_rule`
- **Number Prefix:** `BDQR` (`BDQR-00001`)
- **CHOICES:**
  - `RULE_CATEGORY_CHOICES = [('validation', 'Validation & Accuracy Check'), ('consistency', 'Consistency & Referential Integrity'), ('uniqueness', 'Uniqueness & Deduplication'), ('standardization', 'Standardization & Cleansing'), ('custom_sql', 'Custom SQL Assertion')]`
  - `DIMENSION_CHOICES = [('completeness', 'Completeness'), ('accuracy', 'Accuracy'), ('consistency', 'Consistency'), ('timeliness', 'Timeliness'), ('uniqueness', 'Uniqueness'), ('validity', 'Validity')]`
  - `TARGET_TYPE_CHOICES = [('warehouse_table', 'Warehouse Table'), ('semantic_model', 'Semantic Model')]`
  - `RULE_TYPE_CHOICES = [('not_null', 'Not Null / Mandatory Check'), ('unique', 'Uniqueness Constraint'), ('range_between', 'Value Range Boundary (Min/Max)'), ('regex_pattern', 'Regex Pattern Matching'), ('set_membership', 'Allowed Set Membership / Enum'), ('referential_integrity', 'Referential Integrity / Foreign Key'), ('date_freshness', 'Data Freshness / Timeliness SLA'), ('string_standardization', 'Standardization (Trim, Case, Regex Normalize)'), ('duplicate_cluster', 'Fuzzy Duplicate Cluster Check'), ('custom_sql', 'Custom SQL Boolean Condition')]`
  - `SEVERITY_CHOICES = [('info', 'Information (Advisory)'), ('warning', 'Warning (Low Impact)'), ('critical', 'Critical (Business SLA Impact)'), ('fatal', 'Fatal (Pipeline Blocking)')]`
  - `STATUS_CHOICES = [('passed', 'Passed'), ('warning', 'Warning (Within Tolerance)'), ('failed', 'Failed'), ('error', 'Execution Error'), ('skipped', 'Skipped')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=60)`
  - `rule_category`: `CharField(max_length=25, choices=RULE_CATEGORY_CHOICES, default='validation')`
  - `dimension`: `CharField(max_length=20, choices=DIMENSION_CHOICES, default='validity')`
  - `target_type`: `CharField(max_length=25, choices=TARGET_TYPE_CHOICES, default='warehouse_table')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.CASCADE, related_name='quality_rules')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.CASCADE, related_name='quality_rules')`
  - `target_column`: `CharField(max_length=100, blank=True)`
  - `rule_type`: `CharField(max_length=30, choices=RULE_TYPE_CHOICES, default='not_null')`
  - `parameters_json`: `JSONField(default=dict)`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default='warning')`
  - `failure_tolerance_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `last_run_at`: `DateTimeField(null=True, blank=True)`
  - `last_status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='passed')`
  - `passed_records_count`: `BigIntegerField(default=0)`
  - `failed_records_count`: `BigIntegerField(default=0)`
  - `pass_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `steward`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='stewarded_quality_rules')`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_bdqr_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdqr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'rule_category'], name='idx_bdqr_ten_rcat')`
  - `Index(fields=['tenant', 'dimension'], name='idx_bdqr_ten_dim')`
  - `Index(fields=['tenant', 'last_status'], name='idx_bdqr_ten_lstat')`
  - `Index(fields=['tenant', 'severity'], name='idx_bdqr_ten_sev')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdqr_ten_active')`

---

### 1.3 `DataQualityException` (`apps/bi/models/DataQuality/DataQualityExceptions.py`)
- **Table:** `bi_data_quality_exception`
- **Number Prefix:** `BDQE` (`BDQE-00001`)
- **CHOICES:**
  - `EXCEPTION_TYPE_CHOICES = [('rule_violation', 'Rule Assertion Violation'), ('duplicate_candidate', 'Potential Duplicate Record Pair'), ('null_anomaly', 'Null / Missing Mandatory Value'), ('range_outlier', 'Range / Statistical Outlier'), ('format_invalid', 'Invalid Pattern or Format'), ('referential_orphan', 'Referential Integrity Orphan')]`
  - `SEVERITY_CHOICES = [('info', 'Information'), ('warning', 'Warning'), ('critical', 'Critical'), ('fatal', 'Fatal')]`
  - `STATUS_CHOICES = [('open', 'Open / Unassigned'), ('investigating', 'Under Investigation'), ('remediated', 'Remediated & Verified'), ('suppressed_false_positive', 'Suppressed (False Positive)'), ('accepted_risk', 'Accepted Business Risk'), ('rejected', 'Rejected / Invalid Exception')]`
  - `REMEDIATION_ACTION_CHOICES = [('none', 'No Action Taken'), ('manual_edit', 'Manual Record Correction'), ('automated_standardize', 'Automated Standardization Applied'), ('merge_duplicate', 'Duplicate Merged / Reconciled'), ('impute_value', 'Value Imputed / Defaulted'), ('quarantine_row', 'Record Quarantined')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `rule`: `ForeignKey('bi.DataQualityRule', null=True, blank=True, on_delete=models.SET_NULL, related_name='exceptions')`
  - `profile`: `ForeignKey('bi.DataQualityProfile', null=True, blank=True, on_delete=models.SET_NULL, related_name='exceptions')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='quality_exceptions')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='quality_exceptions')`
  - `record_identifier`: `CharField(max_length=150)`
  - `target_column`: `CharField(max_length=100, blank=True)`
  - `invalid_value`: `TextField(blank=True)`
  - `expected_condition`: `CharField(max_length=255, blank=True)`
  - `exception_type`: `CharField(max_length=30, choices=EXCEPTION_TYPE_CHOICES, default='rule_violation')`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default='warning')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='open')`
  - `remediation_action`: `CharField(max_length=30, choices=REMEDIATION_ACTION_CHOICES, default='none')`
  - `proposed_value`: `TextField(blank=True)`
  - `remediated_value`: `TextField(blank=True)`
  - `assigned_steward`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_quality_exceptions')`
  - `resolved_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `resolution_notes`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdqe_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_bdqe_ten_status')`
  - `Index(fields=['tenant', 'severity'], name='idx_bdqe_ten_sev')`
  - `Index(fields=['tenant', 'exception_type'], name='idx_bdqe_ten_etype')`
  - `Index(fields=['tenant', 'rule'], name='idx_bdqe_ten_rule')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdqe_ten_active')`

---

### 1.4 `DataQualityScorecard` (`apps/bi/models/DataQuality/DataQualityScorecards.py`)
- **Table:** `bi_data_quality_scorecard`
- **Number Prefix:** `BDQS` (`BDQS-00001`)
- **CHOICES:**
  - `SCOPE_TYPE_CHOICES = [('warehouse_table', 'Warehouse Table'), ('semantic_model', 'Semantic Model'), ('data_mart', 'Data Mart Domain'), ('tenant_wide', 'Tenant-Wide Aggregate')]`
  - `GRADE_CHOICES = [('A', 'Grade A: Excellent (>95%)'), ('B', 'Grade B: Good (85-95%)'), ('C', 'Grade C: Acceptable (75-84%)'), ('D', 'Grade D: Poor (60-74%)'), ('F', 'Grade F: Failing (<60%)')]`
  - `HEALTH_STATUS_CHOICES = [('healthy', 'Healthy (Meets SLAs)'), ('needs_attention', 'Needs Attention (Minor Breaches)'), ('critical', 'Critical (Major SLA Breaches)'), ('failing', 'Failing (Data Untrusted)')]`
  - `EVALUATION_PERIOD_CHOICES = [('ad_hoc', 'Ad-Hoc / Current'), ('daily', 'Daily Snapshot'), ('weekly', 'Weekly Rollup'), ('monthly', 'Monthly Scorecard')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=150)`
  - `code`: `SlugField(max_length=60)`
  - `scope_type`: `CharField(max_length=25, choices=SCOPE_TYPE_CHOICES, default='warehouse_table')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='scorecards')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='scorecards')`
  - `data_mart`: `ForeignKey('bi.DataMart', null=True, blank=True, on_delete=models.SET_NULL, related_name='scorecards')`
  - `org_unit`: `ForeignKey('core.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL, related_name='quality_scorecards')`
  - `overall_quality_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `completeness_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `accuracy_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `consistency_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `timeliness_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `uniqueness_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `validity_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))`
  - `grade`: `CharField(max_length=5, choices=GRADE_CHOICES, default='A')`
  - `health_status`: `CharField(max_length=20, choices=HEALTH_STATUS_CHOICES, default='healthy')`
  - `target_quality_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('95.00'))`
  - `meets_sla`: `BooleanField(default=True)`
  - `total_rules_evaluated`: `PositiveIntegerField(default=0)`
  - `rules_passed_count`: `PositiveIntegerField(default=0)`
  - `rules_failed_count`: `PositiveIntegerField(default=0)`
  - `open_exceptions_count`: `PositiveIntegerField(default=0)`
  - `critical_exceptions_count`: `PositiveIntegerField(default=0)`
  - `evaluation_period`: `CharField(max_length=20, choices=EVALUATION_PERIOD_CHOICES, default='ad_hoc')`
  - `last_calculated_at`: `DateTimeField(null=True, blank=True)`
  - `steward`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='stewarded_scorecards')`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'code'], name='bi_bdqs_tenant_code_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bdqs_tenant_num_uniq')`
  - `Index(fields=['tenant', 'scope_type'], name='idx_bdqs_ten_stype')`
  - `Index(fields=['tenant', 'grade'], name='idx_bdqs_ten_grade')`
  - `Index(fields=['tenant', 'health_status'], name='idx_bdqs_ten_hstat')`
  - `Index(fields=['tenant', 'is_active'], name='idx_bdqs_ten_active')`

---

## 2. Forms Contract (`apps/bi/forms/DataQuality/`)

All forms inherit from `forms.ModelForm` and enforce Tailwind styling (`.form-input`, `.form-select`, `.form-textarea`, etc.).

### 2.1 `DataQualityProfileForm` (`apps/bi/forms/DataQuality/DataQualityProfileForms.py`)
- **Fields:** `['name', 'target_type', 'warehouse_table', 'semantic_model', 'notes', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'status', 'total_row_count', 'total_column_count', 'completeness_score', 'uniqueness_score', 'validity_score', 'column_profiles_json', 'profiled_by', 'profiled_at', 'duration_seconds', 'error_message', 'created_at', 'updated_at']`

### 2.2 `DataQualityRuleForm` (`apps/bi/forms/DataQuality/DataQualityRuleForms.py`)
- **Fields:** `['name', 'code', 'rule_category', 'dimension', 'target_type', 'warehouse_table', 'semantic_model', 'target_column', 'rule_type', 'parameters_json', 'severity', 'failure_tolerance_pct', 'steward', 'description', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'last_run_at', 'last_status', 'passed_records_count', 'failed_records_count', 'pass_rate_pct', 'created_at', 'updated_at']`

### 2.3 `DataQualityExceptionForm` (`apps/bi/forms/DataQuality/DataQualityExceptionForms.py`)
- **Fields:** `['rule', 'profile', 'warehouse_table', 'semantic_model', 'record_identifier', 'target_column', 'invalid_value', 'expected_condition', 'exception_type', 'severity', 'status', 'remediation_action', 'proposed_value', 'remediated_value', 'assigned_steward', 'resolution_notes', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'resolved_by', 'resolved_at', 'created_at', 'updated_at']`

### 2.4 `DataQualityExceptionRemediationForm` (`apps/bi/forms/DataQuality/DataQualityExceptionForms.py`)
- **Fields:** `['status', 'remediation_action', 'proposed_value', 'remediated_value', 'assigned_steward', 'resolution_notes']`

### 2.5 `DataQualityScorecardForm` (`apps/bi/forms/DataQuality/DataQualityScorecardForms.py`)
- **Fields:** `['name', 'code', 'scope_type', 'warehouse_table', 'semantic_model', 'data_mart', 'org_unit', 'target_quality_score', 'evaluation_period', 'steward', 'description', 'is_active']`
- **Exclusions:** `['tenant', 'number', 'overall_quality_score', 'completeness_score', 'accuracy_score', 'consistency_score', 'timeliness_score', 'uniqueness_score', 'validity_score', 'grade', 'health_status', 'meets_sla', 'total_rules_evaluated', 'rules_passed_count', 'rules_failed_count', 'open_exceptions_count', 'critical_exceptions_count', 'last_calculated_at', 'created_at', 'updated_at']`

---

## 3. URLs Contract (`apps/bi/urls/DataQuality/`)

App namespace: `bi`

| URL Pattern | View Name | View Function |
|---|---|---|
| `data-quality/overview/` | `bi:quality_overview` | `quality_overview` |
| `data-quality/profiles/` | `bi:data_quality_profile_list` | `data_quality_profile_list` |
| `data-quality/profiles/create/` | `bi:data_quality_profile_create` | `data_quality_profile_create` |
| `data-quality/profiles/<int:pk>/` | `bi:data_quality_profile_detail` | `data_quality_profile_detail` |
| `data-quality/profiles/<int:pk>/edit/` | `bi:data_quality_profile_edit` | `data_quality_profile_edit` |
| `data-quality/profiles/<int:pk>/delete/` | `bi:data_quality_profile_delete` | `data_quality_profile_delete` |
| `data-quality/profiles/<int:pk>/run/` | `bi:data_quality_profile_run` | `data_quality_profile_run` |
| `data-quality/rules/` | `bi:data_quality_rule_list` | `data_quality_rule_list` |
| `data-quality/rules/create/` | `bi:data_quality_rule_create` | `data_quality_rule_create` |
| `data-quality/rules/<int:pk>/` | `bi:data_quality_rule_detail` | `data_quality_rule_detail` |
| `data-quality/rules/<int:pk>/edit/` | `bi:data_quality_rule_edit` | `data_quality_rule_edit` |
| `data-quality/rules/<int:pk>/delete/` | `bi:data_quality_rule_delete` | `data_quality_rule_delete` |
| `data-quality/rules/<int:pk>/run/` | `bi:data_quality_rule_run` | `data_quality_rule_run` |
| `data-quality/exceptions/` | `bi:data_quality_exception_list` | `data_quality_exception_list` |
| `data-quality/exceptions/create/` | `bi:data_quality_exception_create` | `data_quality_exception_create` |
| `data-quality/exceptions/<int:pk>/` | `bi:data_quality_exception_detail` | `data_quality_exception_detail` |
| `data-quality/exceptions/<int:pk>/edit/` | `bi:data_quality_exception_edit` | `data_quality_exception_edit` |
| `data-quality/exceptions/<int:pk>/delete/` | `bi:data_quality_exception_delete` | `data_quality_exception_delete` |
| `data-quality/exceptions/<int:pk>/remediate/` | `bi:data_quality_exception_remediate` | `data_quality_exception_remediate` |
| `data-quality/scorecards/` | `bi:data_quality_scorecard_list` | `data_quality_scorecard_list` |
| `data-quality/scorecards/create/` | `bi:data_quality_scorecard_create` | `data_quality_scorecard_create` |
| `data-quality/scorecards/<int:pk>/` | `bi:data_quality_scorecard_detail` | `data_quality_scorecard_detail` |
| `data-quality/scorecards/<int:pk>/edit/` | `bi:data_quality_scorecard_edit` | `data_quality_scorecard_edit` |
| `data-quality/scorecards/<int:pk>/delete/` | `bi:data_quality_scorecard_delete` | `data_quality_scorecard_delete` |
| `data-quality/scorecards/<int:pk>/recalculate/` | `bi:data_quality_scorecard_recalculate` | `data_quality_scorecard_recalculate` |

---

## 4. View Context Keys Contract (MANDATORY — Every Key Pinned)

### 4.1 Overview View
- **`quality_overview`**:
  - `total_profiles`: count of profiles
  - `total_rules`: count of rules
  - `open_exceptions`: count of exceptions with status in ('open', 'investigating')
  - `total_scorecards`: count of scorecards
  - `avg_trust_score`: average overall_quality_score across scorecards
  - `healthy_scorecards_count`: count of scorecards with health_status='healthy'
  - `recent_profiles`: QuerySet of recent 5 DataQualityProfile
  - `failing_rules`: QuerySet of failing/error DataQualityRule
  - `critical_exceptions`: QuerySet of open critical/fatal DataQualityException
  - `scorecards`: QuerySet of recent 6 DataQualityScorecard
  - `dimension_scores`: dict of average completeness, accuracy, consistency, timeliness, uniqueness, validity scores

### 4.2 Profile Views
- **`data_quality_profile_list`**:
  - `page_obj`: paginated Page object
  - `profiles`: page_obj alias
  - `status_choices`: `DataQualityProfile.STATUS_CHOICES`
  - `target_type_choices`: `DataQualityProfile.TARGET_TYPE_CHOICES`
  - `warehouse_tables`: QuerySet of tenant WarehouseTable
  - `semantic_models`: QuerySet of tenant SemanticModel
  - `total_count`: total count
  - `completed_count`: count with status='completed'
  - `failed_count`: count with status='failed'
- **`data_quality_profile_detail`**:
  - `profile`: `DataQualityProfile` instance
  - `exceptions`: QuerySet of exceptions linked to this profile
  - `column_profiles`: parsed list of dicts from `column_profiles_json`
  - `total_exceptions_count`: int
- **`data_quality_profile_create`** / **`data_quality_profile_edit`**:
  - `form`: `DataQualityProfileForm`
  - `profile`: instance or `None`
  - `is_edit`: boolean

### 4.3 Rule Views
- **`data_quality_rule_list`**:
  - `page_obj`: paginated Page object
  - `rules`: page_obj alias
  - `category_choices`: `DataQualityRule.RULE_CATEGORY_CHOICES`
  - `dimension_choices`: `DataQualityRule.DIMENSION_CHOICES`
  - `severity_choices`: `DataQualityRule.SEVERITY_CHOICES`
  - `status_choices`: `DataQualityRule.STATUS_CHOICES`
  - `warehouse_tables`: QuerySet of tenant WarehouseTable
  - `semantic_models`: QuerySet of tenant SemanticModel
  - `total_count`: total count
  - `passed_count`: count with last_status='passed'
  - `failed_count`: count with last_status in ('failed', 'error')
- **`data_quality_rule_detail`**:
  - `rule`: `DataQualityRule` instance
  - `exceptions`: QuerySet of exceptions linked to this rule
  - `open_exceptions_count`: int
  - `parameters_pretty`: formatted JSON string of parameters_json
- **`data_quality_rule_create`** / **`data_quality_rule_edit`**:
  - `form`: `DataQualityRuleForm`
  - `rule`: instance or `None`
  - `is_edit`: boolean

### 4.4 Exception Views
- **`data_quality_exception_list`**:
  - `page_obj`: paginated Page object
  - `exceptions`: page_obj alias
  - `status_choices`: `DataQualityException.STATUS_CHOICES`
  - `severity_choices`: `DataQualityException.SEVERITY_CHOICES`
  - `exception_type_choices`: `DataQualityException.EXCEPTION_TYPE_CHOICES`
  - `rules`: QuerySet of tenant DataQualityRule
  - `stewards`: QuerySet of tenant User
  - `total_count`: total count
  - `open_count`: count with status in ('open', 'investigating')
  - `remediated_count`: count with status='remediated'
  - `critical_count`: count with severity in ('critical', 'fatal')
- **`data_quality_exception_detail`**:
  - `exception`: `DataQualityException` instance
  - `remediation_form`: `DataQualityExceptionRemediationForm`
- **`data_quality_exception_create`** / **`data_quality_exception_edit`**:
  - `form`: `DataQualityExceptionForm`
  - `exception`: instance or `None`
  - `is_edit`: boolean

### 4.5 Scorecard Views
- **`data_quality_scorecard_list`**:
  - `page_obj`: paginated Page object
  - `scorecards`: page_obj alias
  - `scope_type_choices`: `DataQualityScorecard.SCOPE_TYPE_CHOICES`
  - `grade_choices`: `DataQualityScorecard.GRADE_CHOICES`
  - `health_status_choices`: `DataQualityScorecard.HEALTH_STATUS_CHOICES`
  - `total_count`: total count
  - `grade_a_count`: count with grade='A'
  - `sla_breached_count`: count with meets_sla=False
- **`data_quality_scorecard_detail`**:
  - `scorecard`: `DataQualityScorecard` instance
  - `evaluated_rules`: QuerySet of rules matching scope
  - `related_exceptions`: QuerySet of open exceptions matching scope
- **`data_quality_scorecard_create`** / **`data_quality_scorecard_edit`**:
  - `form`: `DataQualityScorecardForm`
  - `scorecard`: instance or `None`
  - `is_edit`: boolean

---

## 5. Navigation `LIVE_LINKS["10.5"]` Contract

Mapped verbatim to `NavERP.md` 10.5 feature bullets in `apps/core/navigation.py`:
```python
"10.5": {
    "Data Profiling": "bi:data_quality_profile_list",
    "Validation & Quality Rules": "bi:data_quality_rule_list",
    "Deduplication & Matching": "bi:data_quality_rule_list",
    "Standardization & Enrichment": "bi:data_quality_rule_list",
    "Quality Scorecards & Remediation": "bi:data_quality_scorecard_list",
    # Extra live leaves
    "Quality Profiles": "bi:data_quality_profile_list",
    "Quality Rules": "bi:data_quality_rule_list",
    "Quality Exceptions": "bi:data_quality_exception_list",
    "Quality Scorecards": "bi:data_quality_scorecard_list",
    "Quality Overview": "bi:quality_overview",
},
```
