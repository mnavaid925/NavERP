# Module 12.3 Pre-Build Contract — Risk Management (ISO 14971 / FMEA) (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.3"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0005_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/RiskManagement/`
  - `apps/quality/forms/RiskManagement/`
  - `apps/quality/views/RiskManagement/`
  - `apps/quality/urls/RiskManagement/`
  - `templates/quality/riskmanagement/{risk_management_plan,risk_assessment,risk_control_measure,risk_review_record}/{list,detail,form}.html` + `templates/quality/riskmanagement/fmea_matrix.html` + `templates/quality/riskmanagement/risk_traceability_matrix.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"activate"`, `"archive"`, `"approve"`, `"verify"`, `"export"`, `"recalc"` (all `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `core.OrgUnit`, `accounts.User`, `quality.DesignProject`, `quality.DesignInput`, `quality.DesignVerification`, `quality.ControlledDocument`, `quality.ElectronicSignatureRecord`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.

---

## 1. Models & Choices Contract (`apps/quality/models/RiskManagement/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `RiskManagementPlan` (`RiskManagementPlans.py`)
- **`NUMBER_PREFIX`**: `"QRMP"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Risk Management Plan"` / `"Risk Management Plans"`
- **Choices & Badge Maps**:
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Draft / Scoping")`
    - `("in_review", "In Review")`
    - `("active", "Active / Effective")`
    - `("periodic_review", "Under Periodic Review")`
    - `("superseded", "Superseded")`
    - `("archived", "Archived")`
  - `DEVICE_CLASSIFICATION_CHOICES` (`max_length=24`):
    - `("class_i", "Class I (Low Risk)")`
    - `("class_ii_a", "Class IIa (Moderate Risk)")`
    - `("class_ii_b", "Class IIb (High-Moderate Risk)")`
    - `("class_iii", "Class III (High Risk - Critical)")`
    - `("samd", "SaMD / Digital Health")`
    - `("non_medical", "Non-Medical Regulated Product")`
  - `MATRIX_DIMENSION_CHOICES` (`max_length=12`):
    - `("3x3", "3 x 3 Matrix (Low/Med/High)")`
    - `("4x4", "4 x 4 Matrix")`
    - `("5x5", "5 x 5 Matrix (Standard ISO 14971)")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_review": "badge-amber"`
    - `"active": "badge-green"`
    - `"periodic_review": "badge-info"`
    - `"superseded": "badge-muted"`
    - `"archived": "badge-muted"`
  - `DEVICE_CLASS_CSS`:
    - `"class_i": "badge-slate"`
    - `"class_ii_a": "badge-info"`
    - `"class_ii_b": "badge-amber"`
    - `"class_iii": "badge-red"`
    - `"samd": "badge-info"`
    - `"non_medical": "badge-slate"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `plan_version`: `CharField(max_length=16, default="1.0")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `design_project`: `ForeignKey("quality.DesignProject", on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_plans")`
  - `lead_risk_manager`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="managed_risk_plans")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_plans")`
  - `device_classification`: `CharField(max_length=24, choices=DEVICE_CLASSIFICATION_CHOICES, default="class_ii_a")`
  - `scope_description`: `TextField()`
  - `matrix_dimension`: `CharField(max_length=12, choices=MATRIX_DIMENSION_CHOICES, default="5x5")`
  - `risk_acceptability_policy`: `TextField()`
  - `overall_residual_risk_acceptable`: `BooleanField(default=False)`
  - `overall_benefit_risk_summary`: `TextField(blank=True)`
  - `periodic_review_frequency_months`: `PositiveSmallIntegerField(default=12)`
  - `next_review_due_date`: `DateField(null=True, blank=True)`
  - `approved_signature`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_risk_plans", editable=False)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrmp_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_qrmp_ten_status")`
  - `Index(fields=["tenant", "device_classification"], name="idx_qrmp_ten_class")`
  - `Index(fields=["tenant", "design_project"], name="idx_qrmp_ten_prj")`
  - `Index(fields=["tenant", "-created_at"], name="idx_qrmp_ten_created")`

### 1.2 `RiskAssessment` (`RiskAssessments.py`)
- **`NUMBER_PREFIX`**: `"QRSK"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Risk Assessment"` / `"Risk Assessments"`
- **Choices & Badge Maps**:
  - `ANALYSIS_TYPE_CHOICES` (`max_length=24`):
    - `("hazard_analysis", "Preliminary Hazard Analysis (PHA)")`
    - `("dfmea", "Design FMEA (DFMEA)")`
    - `("pfmea", "Process FMEA (PFMEA)")`
    - `("software_fmea", "Software FMEA / Cyber Risk")`
    - `("use_error_urra", "Usability / Use Error Analysis (URRA)")`
  - `HAZARD_CATEGORY_CHOICES` (`max_length=32`):
    - `("energy_electrical", "Electrical Energy / Shock")`
    - `("energy_thermal", "Thermal Energy / Burns")`
    - `("energy_mechanical", "Mechanical / Kinetic / Pressure")`
    - `("radiation", "Ionizing / Optical Radiation")`
    - `("biological_chemical", "Biological / Chemical Toxicity")`
    - `("operational_use_error", "Human Factors / Use Error")`
    - `("software_cybersecurity", "Software Failure / Cybersecurity")`
    - `("environmental", "Environmental / Storage / Transport")`
    - `("other", "Other Recognized Hazard")`
  - `SEVERITY_CHOICES`:
    - `(1, "1 - Negligible (Inconvenience / No Injury)")`
    - `(2, "2 - Minor (Reversible Injury / First Aid)")`
    - `(3, "3 - Serious (Medical Intervention Required)")`
    - `(4, "4 - Critical (Permanent Impairment / Life Threat)")`
    - `(5, "5 - Catastrophic (Patient or User Death)")`
  - `PROBABILITY_CHOICES`:
    - `(1, "1 - Improbable (< 1 in 100,000)")`
    - `(2, "2 - Remote (1 in 10,000)")`
    - `(3, "3 - Occasional (1 in 1,000)")`
    - `(4, "4 - Probable (1 in 100)")`
    - `(5, "5 - Frequent (> 1 in 10)")`
  - `DETECTABILITY_CHOICES`:
    - `(1, "1 - Almost Certain (Automated Interlock / Check)")`
    - `(2, "2 - High (Obvious Alarm / Clear Visual Warning)")`
    - `(3, "3 - Moderate (Detectability through routine check)")`
    - `(4, "4 - Low (Subtle warning / easily overlooked)")`
    - `(5, "5 - Undetectable (Silent failure until harm occurs)")`
  - `RISK_LEVEL_CHOICES` (`max_length=24`):
    - `("broadly_acceptable", "Broadly Acceptable (Green)")`
    - `("alarp", "ALARP / Conditionally Acceptable (Amber)")`
    - `("unacceptable", "Unacceptable (Red)")`
  - `LIFECYCLE_STATUS_CHOICES` (`max_length=28`):
    - `("open", "Open / Unmitigated")`
    - `("mitigation_in_progress", "Mitigation In Progress")`
    - `("mitigated", "Mitigated / Pending Residual Check")`
    - `("accepted", "Accepted with Clinical BRA")`
    - `("closed", "Closed / Verified Safe")`
  - `RISK_LEVEL_CSS`:
    - `"broadly_acceptable": "badge-green"`
    - `"alarp": "badge-amber"`
    - `"unacceptable": "badge-red"`
  - `LIFECYCLE_STATUS_CSS`:
    - `"open": "badge-red"`
    - `"mitigation_in_progress": "badge-amber"`
    - `"mitigated": "badge-info"`
    - `"accepted": "badge-purple"`
    - `"closed": "badge-green"`
  - `ANALYSIS_TYPE_CSS`:
    - `"hazard_analysis": "badge-info"`
    - `"dfmea": "badge-purple"`
    - `"pfmea": "badge-slate"`
    - `"software_fmea": "badge-amber"`
    - `"use_error_urra": "badge-info"`
- **Fields**:
  - `plan`: `ForeignKey("quality.RiskManagementPlan", on_delete=models.CASCADE, related_name="assessments")`
  - `analysis_type`: `CharField(max_length=24, choices=ANALYSIS_TYPE_CHOICES, default="hazard_analysis", db_index=True)`
  - `hazard_category`: `CharField(max_length=32, choices=HAZARD_CATEGORY_CHOICES, default="other")`
  - `hazard_description`: `CharField(max_length=255)`
  - `hazardous_situation`: `TextField()`
  - `foreseeable_sequence_of_events`: `TextField(blank=True)`
  - `potential_harm`: `TextField()`
  - `item_function`: `CharField(max_length=255, blank=True)`
  - `failure_mode`: `CharField(max_length=255, blank=True)`
  - `failure_cause`: `TextField(blank=True)`
  - `failure_effect`: `TextField(blank=True)`
  - `initial_severity`: `PositiveSmallIntegerField(default=3, choices=SEVERITY_CHOICES)`
  - `initial_probability`: `PositiveSmallIntegerField(default=3, choices=PROBABILITY_CHOICES)`
  - `initial_detectability`: `PositiveSmallIntegerField(default=1, choices=DETECTABILITY_CHOICES)`
  - `initial_rpn`: `PositiveIntegerField(default=0, editable=False)`
  - `initial_risk_level`: `CharField(max_length=24, choices=RISK_LEVEL_CHOICES, default="unacceptable", editable=False)`
  - `residual_severity`: `PositiveSmallIntegerField(null=True, blank=True, choices=SEVERITY_CHOICES)`
  - `residual_probability`: `PositiveSmallIntegerField(null=True, blank=True, choices=PROBABILITY_CHOICES)`
  - `residual_detectability`: `PositiveSmallIntegerField(null=True, blank=True, choices=DETECTABILITY_CHOICES)`
  - `residual_rpn`: `PositiveIntegerField(null=True, blank=True, editable=False)`
  - `residual_risk_level`: `CharField(max_length=24, choices=RISK_LEVEL_CHOICES, blank=True, editable=False)`
  - `residual_risk_acceptable`: `BooleanField(default=False)`
  - `bra_required`: `BooleanField(default=False)`
  - `benefit_risk_justification`: `TextField(blank=True)`
  - `disclosed_in_ifu`: `BooleanField(default=False)`
  - `design_input`: `ForeignKey("quality.DesignInput", on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_assessments")`
  - `lifecycle_status`: `CharField(max_length=28, choices=LIFECYCLE_STATUS_CHOICES, default="open", db_index=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrsk_ten_num_uniq")`
  - `Index(fields=["tenant", "plan", "analysis_type"], name="idx_qrsk_ten_pln_type")`
  - `Index(fields=["tenant", "initial_risk_level"], name="idx_qrsk_ten_init_lvl")`
  - `Index(fields=["tenant", "residual_risk_level"], name="idx_qrsk_ten_res_lvl")`
  - `Index(fields=["tenant", "lifecycle_status"], name="idx_qrsk_ten_status")`
  - `Index(fields=["tenant", "-created_at"], name="idx_qrsk_ten_created")`

### 1.3 `RiskControlMeasure` (`RiskControlMeasures.py`)
- **`NUMBER_PREFIX`**: `"QRCM"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Risk Control Measure"` / `"Risk Control Measures"`
- **Choices & Badge Maps**:
  - `CONTROL_HIERARCHY_CHOICES` (`max_length=28`):
    - `("inherent_safety", "1. Inherent Safety by Design")`
    - `("protective_measure", "2. Protective Measures in Device/Process")`
    - `("information_for_safety", "3. Information for Safety / Training")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("planned", "Planned / Under Design")`
    - `("in_progress", "Implementation In Progress")`
    - `("implemented", "Implemented / Ready for Verification")`
    - `("verified", "Verified Effective")`
    - `("ineffective", "Ineffective / Needs Revision")`
    - `("obsolete", "Obsolete / Retired")`
  - `CONTROL_HIERARCHY_CSS`:
    - `"inherent_safety": "badge-green"`
    - `"protective_measure": "badge-info"`
    - `"information_for_safety": "badge-amber"`
  - `STATUS_CSS`:
    - `"planned": "badge-slate"`
    - `"in_progress": "badge-info"`
    - `"implemented": "badge-amber"`
    - `"verified": "badge-green"`
    - `"ineffective": "badge-red"`
    - `"obsolete": "badge-muted"`
- **Fields**:
  - `risk_assessment`: `ForeignKey("quality.RiskAssessment", on_delete=models.CASCADE, related_name="control_measures")`
  - `control_hierarchy`: `CharField(max_length=28, choices=CONTROL_HIERARCHY_CHOICES, default="inherent_safety")`
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField()`
  - `assigned_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_risk_controls")`
  - `due_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="planned", db_index=True)`
  - `design_input`: `ForeignKey("quality.DesignInput", on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_controls")`
  - `controlled_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_controls")`
  - `design_verification`: `ForeignKey("quality.DesignVerification", on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_controls")`
  - `implementation_verified`: `BooleanField(default=False)`
  - `effectiveness_verified`: `BooleanField(default=False)`
  - `verification_notes`: `TextField(blank=True)`
  - `introduces_new_hazard`: `BooleanField(default=False)`
  - `new_hazard_details`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrcm_ten_num_uniq")`
  - `Index(fields=["tenant", "risk_assessment"], name="idx_qrcm_ten_assessment")`
  - `Index(fields=["tenant", "control_hierarchy"], name="idx_qrcm_ten_hier")`
  - `Index(fields=["tenant", "status"], name="idx_qrcm_ten_status")`
  - `Index(fields=["tenant", "-created_at"], name="idx_qrcm_ten_created")`

### 1.4 `RiskReviewRecord` (`RiskReviewRecords.py`)
- **`NUMBER_PREFIX`**: `"QRMR"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Risk Review Record"` / `"Risk Review Records"`
- **Choices & Badge Maps**:
  - `REVIEW_TYPE_CHOICES` (`max_length=32`):
    - `("initial_rmr", "Initial Risk Management Report (RMR)")`
    - `("periodic_review", "Scheduled Periodic Review")`
    - `("design_change_review", "Design Change / ECO Review")`
    - `("post_market_surveillance", "Post-Market Surveillance (PMS) Review")`
    - `("complaint_trend_trigger", "Complaint Trend Triggered Review")`
    - `("ncr_capa_trigger", "NCR / CAPA Triggered Review")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Draft")`
    - `("under_review", "Under Review")`
    - `("approved", "Approved")`
    - `("rejected", "Rejected")`
  - `REVIEW_TYPE_CSS`:
    - `"initial_rmr": "badge-info"`
    - `"periodic_review": "badge-slate"`
    - `"design_change_review": "badge-amber"`
    - `"post_market_surveillance": "badge-purple"`
    - `"complaint_trend_trigger": "badge-red"`
    - `"ncr_capa_trigger": "badge-amber"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"under_review": "badge-amber"`
    - `"approved": "badge-green"`
    - `"rejected": "badge-red"`
- **Fields**:
  - `plan`: `ForeignKey("quality.RiskManagementPlan", on_delete=models.CASCADE, related_name="reviews")`
  - `review_title`: `CharField(max_length=255)`
  - `review_type`: `CharField(max_length=32, choices=REVIEW_TYPE_CHOICES, default="periodic_review", db_index=True)`
  - `review_date`: `DateField()`
  - `review_period_start`: `DateField(null=True, blank=True)`
  - `review_period_end`: `DateField(null=True, blank=True)`
  - `pms_sources_reviewed`: `TextField(blank=True)`
  - `new_hazards_identified`: `BooleanField(default=False)`
  - `risk_profile_changed`: `BooleanField(default=False)`
  - `overall_residual_risk_reconfirmed`: `BooleanField(default=True)`
  - `findings_summary`: `TextField()`
  - `action_items_required`: `TextField(blank=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `lead_reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conducted_risk_reviews")`
  - `approved_signature`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_risk_reviews", editable=False)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrmr_ten_num_uniq")`
  - `Index(fields=["tenant", "plan", "review_type"], name="idx_qrmr_ten_pln_type")`
  - `Index(fields=["tenant", "status"], name="idx_qrmr_ten_status")`
  - `Index(fields=["tenant", "review_date"], name="idx_qrmr_ten_date")`
  - `Index(fields=["tenant", "-created_at"], name="idx_qrmr_ten_created")`

---

## 2. Forms Contract (`apps/quality/forms/RiskManagement/`)

All forms inherit `django.forms.ModelForm`.
In `__init__(self, *args, **kwargs)`, accept `request=None` or `tenant=None`:
- Extract `self.tenant = kwargs.pop("tenant", None) or getattr(request, "tenant", None)`.
- If `self.tenant`:
  - Filter all FK querysets: `design_project`, `lead_risk_manager`, `department`, `plan`, `assigned_to`, `design_input`, `controlled_document`, `design_verification`, `lead_reviewer`.
- Form widgets styled with standard form CSS (`form-input`, `form-select`, `form-textarea`, `checkbox`).
- Form `clean()` validates cross-tenant FK boundaries with `reject_foreign(...)` or explicit tenant check.

### 2.1 `RiskManagementPlanForm`
- `Meta.model`: `RiskManagementPlan`
- `Meta.fields`: `["title", "plan_version", "status", "design_project", "lead_risk_manager", "department", "device_classification", "scope_description", "matrix_dimension", "risk_acceptability_policy", "overall_residual_risk_acceptable", "overall_benefit_risk_summary", "periodic_review_frequency_months", "next_review_due_date"]`
- Excluded: `["tenant", "number", "approved_signature", "created_at", "updated_at"]`

### 2.2 `RiskAssessmentForm`
- `Meta.model`: `RiskAssessment`
- `Meta.fields`: `["plan", "analysis_type", "hazard_category", "hazard_description", "hazardous_situation", "foreseeable_sequence_of_events", "potential_harm", "item_function", "failure_mode", "failure_cause", "failure_effect", "initial_severity", "initial_probability", "initial_detectability", "residual_severity", "residual_probability", "residual_detectability", "residual_risk_acceptable", "bra_required", "benefit_risk_justification", "disclosed_in_ifu", "design_input", "lifecycle_status"]`
- Excluded: `["tenant", "number", "initial_rpn", "initial_risk_level", "residual_rpn", "residual_risk_level", "created_at", "updated_at"]`

### 2.3 `RiskControlMeasureForm`
- `Meta.model`: `RiskControlMeasure`
- `Meta.fields`: `["risk_assessment", "control_hierarchy", "title", "description", "assigned_to", "due_date", "status", "design_input", "controlled_document", "design_verification", "implementation_verified", "effectiveness_verified", "verification_notes", "introduces_new_hazard", "new_hazard_details"]`
- Excluded: `["tenant", "number", "created_at", "updated_at"]`

### 2.4 `RiskReviewRecordForm`
- `Meta.model`: `RiskReviewRecord`
- `Meta.fields`: `["plan", "review_title", "review_type", "review_date", "review_period_start", "review_period_end", "pms_sources_reviewed", "new_hazards_identified", "risk_profile_changed", "overall_residual_risk_reconfirmed", "findings_summary", "action_items_required", "status", "lead_reviewer"]`
- Excluded: `["tenant", "number", "approved_signature", "created_at", "updated_at"]`

---

## 3. URLs Contract (`apps/quality/urls/RiskManagement/`)

All routes defined under `app_name = "quality"`.
Literal routes precede parameterized `<int:pk>` routes.

### 3.1 `RiskManagementPlans.py`
- `risk-plans/` → `name="risk_management_plan_list"`
- `risk-plans/create/` → `name="risk_management_plan_create"`
- `risk-plans/export/` → `name="risk_management_plan_export"`
- `risk-plans/<int:pk>/` → `name="risk_management_plan_detail"`
- `risk-plans/<int:pk>/edit/` → `name="risk_management_plan_edit"`
- `risk-plans/<int:pk>/delete/` → `name="risk_management_plan_delete"`
- `risk-plans/<int:pk>/activate/` → `name="risk_management_plan_activate"`
- `risk-plans/<int:pk>/archive/` → `name="risk_management_plan_archive"`

### 3.2 `RiskAssessments.py`
- `risk-assessments/` → `name="risk_assessment_list"`
- `risk-assessments/create/` → `name="risk_assessment_create"`
- `risk-assessments/export/` → `name="risk_assessment_export"`
- `risk-assessments/<int:pk>/` → `name="risk_assessment_detail"`
- `risk-assessments/<int:pk>/edit/` → `name="risk_assessment_edit"`
- `risk-assessments/<int:pk>/delete/` → `name="risk_assessment_delete"`

### 3.3 `RiskControlMeasures.py`
- `risk-controls/` → `name="risk_control_measure_list"`
- `risk-controls/create/` → `name="risk_control_measure_create"`
- `risk-controls/export/` → `name="risk_control_measure_export"`
- `risk-controls/<int:pk>/` → `name="risk_control_measure_detail"`
- `risk-controls/<int:pk>/edit/` → `name="risk_control_measure_edit"`
- `risk-controls/<int:pk>/delete/` → `name="risk_control_measure_delete"`
- `risk-controls/<int:pk>/verify-implementation/` → `name="risk_control_measure_verify_impl"`
- `risk-controls/<int:pk>/verify-effectiveness/` → `name="risk_control_measure_verify_eff"`

### 3.4 `RiskReviewRecords.py`
- `risk-reviews/` → `name="risk_review_record_list"`
- `risk-reviews/create/` → `name="risk_review_record_create"`
- `risk-reviews/export/` → `name="risk_review_record_export"`
- `risk-reviews/<int:pk>/` → `name="risk_review_record_detail"`
- `risk-reviews/<int:pk>/edit/` → `name="risk_review_record_edit"`
- `risk-reviews/<int:pk>/delete/` → `name="risk_review_record_delete"`
- `risk-reviews/<int:pk>/approve/` → `name="risk_review_record_approve"`

### 3.5 `FmeaMatrix.py`
- `risk-matrix/` → `name="fmea_matrix"`
- `risk-matrix/export/` → `name="fmea_matrix_export"`
- `risk-traceability/` → `name="risk_traceability_matrix"`
- `risk-traceability/export/` → `name="risk_traceability_matrix_export"`

---

## 4. Views Context Contract (Mandatory Pinned Keys)

Every template gets exactly these keys. No key may be renamed or omitted.

### 4.1 `risk_management_plan_list`
- `plans`: list of `RiskManagementPlan` objects on current page
- `page_obj`: paginator page object
- `total_count`: integer total plans count
- `active_count`: count with status `active`
- `overdue_count`: count with overdue reviews
- `archived_count`: count with status `archived`
- `status_choices`: `RiskManagementPlan.STATUS_CHOICES`
- `device_class_choices`: `RiskManagementPlan.DEVICE_CLASSIFICATION_CHOICES`
- `selected_status`: string from `request.GET.get("status", "")`
- `selected_class`: string from `request.GET.get("device_class", "")`
- `q`: string search term

### 4.2 `risk_management_plan_detail`
- `plan`: single `RiskManagementPlan` instance
- `assessments`: queryset of associated `RiskAssessment` records
- `reviews`: queryset of associated `RiskReviewRecord` records
- `stats`: dict with `total_assessments`, `unacceptable_count`, `alarp_count`, `acceptable_count`, `controls_count`, `verified_controls_count`

### 4.3 `risk_management_plan_create` & `risk_management_plan_edit`
- `form`: `RiskManagementPlanForm` instance
- `plan`: `RiskManagementPlan` instance on edit, `None` on create
- `is_edit`: boolean

### 4.4 `risk_assessment_list`
- `assessments`: list of `RiskAssessment` objects on current page
- `page_obj`: paginator page object
- `total_count`: integer total assessments count
- `high_risk_count`: count with `initial_risk_level="unacceptable"`
- `unmitigated_count`: count with `residual_risk_acceptable=False`
- `closed_count`: count with `lifecycle_status="closed"`
- `analysis_type_choices`: `RiskAssessment.ANALYSIS_TYPE_CHOICES`
- `hazard_category_choices`: `RiskAssessment.HAZARD_CATEGORY_CHOICES`
- `risk_level_choices`: `RiskAssessment.RISK_LEVEL_CHOICES`
- `lifecycle_status_choices`: `RiskAssessment.LIFECYCLE_STATUS_CHOICES`
- `plans`: queryset of tenant `RiskManagementPlan` instances for filter dropdown
- `selected_type`: string from `request.GET.get("analysis_type", "")`
- `selected_cat`: string from `request.GET.get("hazard_category", "")`
- `selected_level`: string from `request.GET.get("risk_level", "")`
- `selected_status`: string from `request.GET.get("lifecycle_status", "")`
- `selected_plan`: string from `request.GET.get("plan", "")`
- `q`: string search term

### 4.5 `risk_assessment_detail`
- `assessment`: single `RiskAssessment` instance
- `control_measures`: queryset of associated `RiskControlMeasure` records

### 4.6 `risk_assessment_create` & `risk_assessment_edit`
- `form`: `RiskAssessmentForm` instance
- `assessment`: `RiskAssessment` instance on edit, `None` on create
- `is_edit`: boolean

### 4.7 `risk_control_measure_list`
- `control_measures`: list of `RiskControlMeasure` objects on current page
- `page_obj`: paginator page object
- `total_count`: integer total controls count
- `verified_count`: count where `implementation_verified=True and effectiveness_verified=True`
- `inherent_safety_count`: count with `control_hierarchy="inherent_safety"`
- `in_progress_count`: count with `status="in_progress"`
- `hierarchy_choices`: `RiskControlMeasure.CONTROL_HIERARCHY_CHOICES`
- `status_choices`: `RiskControlMeasure.STATUS_CHOICES`
- `plans`: queryset of tenant `RiskManagementPlan` instances
- `selected_hierarchy`: string from `request.GET.get("control_hierarchy", "")`
- `selected_status`: string from `request.GET.get("status", "")`
- `selected_plan`: string from `request.GET.get("plan", "")`
- `q`: string search term

### 4.8 `risk_control_measure_detail`
- `control_measure`: single `RiskControlMeasure` instance

### 4.9 `risk_control_measure_create` & `risk_control_measure_edit`
- `form`: `RiskControlMeasureForm` instance
- `control_measure`: `RiskControlMeasure` instance on edit, `None` on create
- `is_edit`: boolean

### 4.10 `risk_review_record_list`
- `review_records`: list of `RiskReviewRecord` objects on current page
- `page_obj`: paginator page object
- `total_count`: integer total reviews count
- `approved_count`: count with `status="approved"`
- `pms_count`: count with `review_type="post_market_surveillance"`
- `draft_count`: count with `status="draft"`
- `review_type_choices`: `RiskReviewRecord.REVIEW_TYPE_CHOICES`
- `status_choices`: `RiskReviewRecord.STATUS_CHOICES`
- `plans`: queryset of tenant `RiskManagementPlan` instances
- `selected_type`: string from `request.GET.get("review_type", "")`
- `selected_status`: string from `request.GET.get("status", "")`
- `selected_plan`: string from `request.GET.get("plan", "")`
- `q`: string search term

### 4.11 `risk_review_record_detail`
- `review_record`: single `RiskReviewRecord` instance

### 4.12 `risk_review_record_create` & `risk_review_record_edit`
- `form`: `RiskReviewRecordForm` instance
- `review_record`: `RiskReviewRecord` instance on edit, `None` on create
- `is_edit`: boolean

### 4.13 `fmea_matrix`
- `plans`: queryset of tenant `RiskManagementPlan` instances
- `selected_plan`: selected `RiskManagementPlan` instance or `None`
- `matrix_cells`: 2D dict/grid mapping `(severity, probability) -> list of items and count`
- `severity_range`: list of severity tuples `[(5, "5 - Catastrophic"), ...]`
- `probability_range`: list of probability tuples `[(1, "1 - Improbable"), ...]`
- `high_risk_items`: list of assessments in unacceptable zone
- `rpn_pareto_items`: top 10 items sorted by RPN descending
- `stats`: dict with total, unacceptable, alarp, acceptable counts

### 4.14 `risk_traceability_matrix`
- `plans`: queryset of tenant `RiskManagementPlan` instances
- `selected_plan`: selected `RiskManagementPlan` instance or `None`
- `traceability_rows`: list of structured rows linking `Hazard -> Assessment -> Control Measure -> Verification / Document`
- `stats`: dict with coverage metrics

---

## 5. Navigation Wire-Up (`apps/core/navigation.py`)

Add to `LIVE_LINKS["12.3"]`:
```python
"12.3": {
    "Hazard Identification & Analysis": "quality:risk_assessment_list",
    "Risk Evaluation & Scoring": "quality:fmea_matrix",
    "Risk Control & Mitigation": "quality:risk_control_measure_list",
    "Residual Risk Assessment": "quality:risk_assessment_list",
    "Risk Management File & Reporting": "quality:risk_management_plan_list",
},
```
