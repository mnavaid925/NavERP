# Module 12.6 Pre-Build Contract — Supplier & Vendor Quality Management (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.6"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0009_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/SupplierQuality/`
  - `apps/quality/forms/SupplierQuality/`
  - `apps/quality/views/SupplierQuality/`
  - `apps/quality/urls/SupplierQuality/`
  - `templates/quality/supplierquality/{supplier_qualification_audit,supplier_quality_scorecard,supplier_corrective_action,supplier_change_notification}/{list,detail,form}.html` + `templates/quality/supplierquality/avl_directory.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"advance"`, `"close"`, `"verify"`, `"publish"`, `"approve"`, `"reject"`, `"export"` (all `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `core.Party` (with `PartyRole` supplier/vendor), `accounts.User`, `quality.ControlledDocument`, `quality.DesignProject`, `quality.CapaInvestigation`, `scm.PurchaseOrder`, `scm.NonConformance`, `quality.SupplierQualificationAudit`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/SupplierQuality/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `SupplierQualificationAudit` (`SupplierQualificationAudits.py`)
- **`NUMBER_PREFIX`**: `"QSQA"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Supplier Qualification & Audit"` / `"Supplier Qualification & Audits"`
- **Choices & Badge Maps**:
  - `ASSESSMENT_TYPE_CHOICES` (`max_length=35`):
    - `("initial_qualification", "Initial Qualification")`
    - `("periodic_reaudit", "Periodic Re-Audit")`
    - `("for_cause", "For-Cause Audit")`
    - `("certification_review", "Certification Review")`
    - `("quality_agreement_review", "Quality Agreement Review")`
  - `CRITICALITY_TIER_CHOICES` (`max_length=20`):
    - `("critical", "Critical (Direct Product Contact / High Risk)")`
    - `("major", "Major (Key Component / Service)")`
    - `("minor", "Minor (Standard Catalog / Low Risk)")`
    - `("indirect", "Indirect / Non-Product Services")`
  - `AUDIT_METHOD_CHOICES` (`max_length=25`):
    - `("on_site", "On-Site Facility Audit")`
    - `("desktop_survey", "Desktop / Questionnaire Survey")`
    - `("third_party_iso", "Third-Party ISO / Registrar Audit")`
    - `("virtual", "Virtual / Remote Audit")`
  - `QUALIFICATION_STATUS_CHOICES` (`max_length=25`):
    - `("under_evaluation", "Under Evaluation")`
    - `("approved", "Approved (Active AVL)")`
    - `("conditional", "Conditionally Approved")`
    - `("suspended", "Suspended Hold")`
    - `("disqualified", "Disqualified")`
  - `AUDIT_RESULT_CHOICES` (`max_length=25`):
    - `("pending", "Pending Assessment")`
    - `("passed", "Passed / Fully Qualified")`
    - `("passed_with_capa", "Passed with Corrective Actions")`
    - `("failed", "Failed / Unacceptable")`
    - `("exempt", "Audit Exempt")`
  - `ASSESSMENT_TYPE_CSS`:
    - `"initial_qualification": "badge-info"`
    - `"periodic_reaudit": "badge-slate"`
    - `"for_cause": "badge-red"`
    - `"certification_review": "badge-info"`
    - `"quality_agreement_review": "badge-slate"`
  - `CRITICALITY_TIER_CSS`:
    - `"critical": "badge-red"`
    - `"major": "badge-amber"`
    - `"minor": "badge-slate"`
    - `"indirect": "badge-muted"`
  - `QUALIFICATION_STATUS_CSS`:
    - `"under_evaluation": "badge-amber"`
    - `"approved": "badge-green"`
    - `"conditional": "badge-info"`
    - `"suspended": "badge-red"`
    - `"disqualified": "badge-muted"`
  - `AUDIT_RESULT_CSS`:
    - `"pending": "badge-slate"`
    - `"passed": "badge-green"`
    - `"passed_with_capa": "badge-amber"`
    - `"failed": "badge-red"`
    - `"exempt": "badge-muted"`
- **Fields**:
  - `supplier`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="quality_qualifications")`
  - `assessment_type`: `CharField(max_length=35, choices=ASSESSMENT_TYPE_CHOICES, default="initial_qualification", db_index=True)`
  - `criticality_tier`: `CharField(max_length=20, choices=CRITICALITY_TIER_CHOICES, default="major", db_index=True)`
  - `audit_method`: `CharField(max_length=25, choices=AUDIT_METHOD_CHOICES, default="on_site", db_index=True)`
  - `qualification_status`: `CharField(max_length=25, choices=QUALIFICATION_STATUS_CHOICES, default="under_evaluation", db_index=True)`
  - `scope_commodities`: `TextField(blank=True, help_text="Approved materials, services, or part categories")`
  - `score`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Audit compliance score 0-100%")`
  - `audit_result`: `CharField(max_length=25, choices=AUDIT_RESULT_CHOICES, default="pending", db_index=True)`
  - `critical_findings`: `PositiveIntegerField(default=0)`
  - `major_findings`: `PositiveIntegerField(default=0)`
  - `minor_findings`: `PositiveIntegerField(default=0)`
  - `lead_auditor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="led_supplier_audits")`
  - `audit_date`: `DateField(null=True, blank=True)`
  - `qualified_date`: `DateField(null=True, blank=True)`
  - `next_audit_due_date`: `DateField(null=True, blank=True)`
  - `certificate_expiry_date`: `DateField(null=True, blank=True)`
  - `dock_to_stock_eligible`: `BooleanField(default=False, help_text="Authorized to bypass receiving inspection")`
  - `skip_lot_approved`: `BooleanField(default=False, help_text="Approved for reduced inspection frequency")`
  - `requires_coa`: `BooleanField(default=True, help_text="Certificate of Analysis mandatory on shipments")`
  - `quality_agreement`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_qualifications")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qsqa_ten_num_uniq")`
  - `Index(fields=["tenant", "qualification_status"], name="idx_qsqa_ten_status")`
  - `Index(fields=["tenant", "supplier"], name="idx_qsqa_ten_supp")`
  - `Index(fields=["tenant", "criticality_tier"], name="idx_qsqa_ten_crit")`
  - `Index(fields=["tenant", "audit_result"], name="idx_qsqa_ten_res")`
  - `Index(fields=["tenant", "-created_at"], name="idx_qsqa_ten_created")`
- **Form Exclusions**: `tenant`, `number`, `created_at`, `updated_at`

---

### 1.2 `SupplierQualityScorecard` (`SupplierQualityScorecards.py`)
- **`NUMBER_PREFIX`**: `"QSSC"`
- **`Meta.ordering`**: `["-period_end", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Supplier Quality Scorecard"` / `"Supplier Quality Scorecards"`
- **Choices & Badge Maps**:
  - `CADENCE_CHOICES` (`max_length=20`):
    - `("monthly", "Monthly Evaluation")`
    - `("quarterly", "Quarterly Evaluation")`
    - `("semi_annual", "Semi-Annual Evaluation")`
    - `("annual", "Annual Evaluation")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft")`
    - `("under_review", "Under Review")`
    - `("published", "Published / Final")`
    - `("disputed", "Vendor Disputed")`
  - `GRADE_CHOICES` (`max_length=15`):
    - `("grade_a", "Grade A (Preferred / Excellent >= 90)")`
    - `("grade_b", "Grade B (Approved / Good 80-89.9)")`
    - `("grade_c", "Grade C (Conditional / At Risk 70-79.9)")`
    - `("grade_d", "Grade D (Unsatisfactory < 70)")`
  - `CADENCE_CSS`:
    - `"monthly": "badge-info"`
    - `"quarterly": "badge-slate"`
    - `"semi_annual": "badge-amber"`
    - `"annual": "badge-purple"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"under_review": "badge-amber"`
    - `"published": "badge-green"`
    - `"disputed": "badge-red"`
  - `GRADE_CSS`:
    - `"grade_a": "badge-green"`
    - `"grade_b": "badge-info"`
    - `"grade_c": "badge-amber"`
    - `"grade_d": "badge-red"`
- **Fields**:
  - `supplier`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="quality_scorecards")`
  - `cadence`: `CharField(max_length=20, choices=CADENCE_CHOICES, default="quarterly", db_index=True)`
  - `period_start`: `DateField()`
  - `period_end`: `DateField()`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `lot_acceptance_rate_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), help_text="Weight 30%")`
  - `defect_ppm_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), help_text="Weight 25%")`
  - `scar_responsiveness_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), help_text="Weight 20%")`
  - `audit_compliance_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), help_text="Weight 15%")`
  - `documentation_coa_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), help_text="Weight 10%")`
  - `overall_score`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Computed weighted composite score 0-100")`
  - `grade`: `CharField(max_length=15, choices=GRADE_CHOICES, blank=True, default="", db_index=True)`
  - `total_lots_received`: `PositiveIntegerField(default=0)`
  - `lots_rejected`: `PositiveIntegerField(default=0)`
  - `total_scars_issued`: `PositiveIntegerField(default=0)`
  - `evaluated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="evaluated_scorecards")`
  - `is_manual_override`: `BooleanField(default=False)`
  - `override_justification`: `TextField(blank=True)`
  - `evaluation_notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qssc_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_qssc_ten_status")`
  - `Index(fields=["tenant", "supplier"], name="idx_qssc_ten_supp")`
  - `Index(fields=["tenant", "grade"], name="idx_qssc_ten_grade")`
  - `Index(fields=["tenant", "cadence"], name="idx_qssc_ten_cadence")`
  - `Index(fields=["tenant", "period_start", "period_end"], name="idx_qssc_ten_period")`
  - `Index(fields=["tenant", "-created_at"], name="idx_qssc_ten_created")`
- **Form Exclusions**: `tenant`, `number`, `overall_score`, `grade`, `created_at`, `updated_at`

---

### 1.3 `SupplierCorrectiveAction` (SCAR) (`SupplierCorrectiveActions.py`)
- **`NUMBER_PREFIX`**: `"QSCA"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Supplier Corrective Action (SCAR)"` / `"Supplier Corrective Actions (SCAR)"`
- **Choices & Badge Maps**:
  - `SEVERITY_CHOICES` (`max_length=15`):
    - `("minor", "Minor (Documentation / Non-Critical)")`
    - `("major", "Major (Out of Spec / Functional Defect)")`
    - `("critical", "Critical (Safety / Regulatory / Stop-Ship)")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("draft", "Draft")`
    - `("issued", "Issued to Vendor")`
    - `("containment_submitted", "Containment Submitted")`
    - `("rca_submitted", "RCA Submitted")`
    - `("action_plan_approved", "Action Plan Approved")`
    - `("implemented", "Actions Implemented")`
    - `("effectiveness_verified", "Effectiveness Verified")`
    - `("closed", "Closed / Resolved")`
    - `("cancelled", "Cancelled / Voided")`
  - `ROOT_CAUSE_CATEGORY_CHOICES` (`max_length=30`):
    - `("raw_material", "Raw Material Quality")`
    - `("process_parameter", "Manufacturing Process Parameter")`
    - `("tooling_equipment", "Tooling / Machine Wear")`
    - `("operator_training", "Operator / Workmanship Error")`
    - `("packaging_handling", "Packaging / Transit Damage")`
    - `("sub_tier_supplier", "Sub-Tier Supplier Defect")`
    - `("other", "Other / External Factor")`
  - `SEVERITY_CSS`:
    - `"minor": "badge-slate"`
    - `"major": "badge-amber"`
    - `"critical": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"issued": "badge-amber"`
    - `"containment_submitted": "badge-info"`
    - `"rca_submitted": "badge-info"`
    - `"action_plan_approved": "badge-info"`
    - `"implemented": "badge-info"`
    - `"effectiveness_verified": "badge-purple"`
    - `"closed": "badge-green"`
    - `"cancelled": "badge-muted"`
  - `ROOT_CAUSE_CATEGORY_CSS`:
    - `"raw_material": "badge-red"`
    - `"process_parameter": "badge-amber"`
    - `"tooling_equipment": "badge-slate"`
    - `"operator_training": "badge-info"`
    - `"packaging_handling": "badge-slate"`
    - `"sub_tier_supplier": "badge-amber"`
    - `"other": "badge-muted"`
- **Fields**:
  - `supplier`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="quality_scars")`
  - `title`: `CharField(max_length=255)`
  - `severity`: `CharField(max_length=15, choices=SEVERITY_CHOICES, default="major", db_index=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `defect_summary`: `TextField(help_text="Detailed description of defect or non-conformance")`
  - `affected_item_code`: `CharField(max_length=100, blank=True)`
  - `affected_item_name`: `CharField(max_length=255, blank=True)`
  - `affected_lots`: `CharField(max_length=255, blank=True)`
  - `purchase_order`: `ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_scars")`
  - `non_conformance`: `ForeignKey("scm.NonConformance", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_scars")`
  - `qualification_audit`: `ForeignKey("quality.SupplierQualificationAudit", on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_scars")`
  - `internal_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_scars")`
  - `issued_date`: `DateField(null=True, blank=True)`
  - `response_due_date`: `DateField(null=True, blank=True)`
  - `issued_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_scars")`
  - `containment_action`: `TextField(blank=True, help_text="Emergency containment actions taken within 24-48 hours")`
  - `containment_due_date`: `DateField(null=True, blank=True)`
  - `containment_verified_at`: `DateField(null=True, blank=True)`
  - `root_cause_summary`: `TextField(blank=True)`
  - `root_cause_category`: `CharField(max_length=30, choices=ROOT_CAUSE_CATEGORY_CHOICES, blank=True, default="", db_index=True)`
  - `vendor_investigation_details`: `TextField(blank=True, help_text="Vendor 5 Whys or Fishbone investigation details")`
  - `corrective_action_plan`: `TextField(blank=True)`
  - `preventive_action_plan`: `TextField(blank=True)`
  - `implementation_due_date`: `DateField(null=True, blank=True)`
  - `implemented_at`: `DateField(null=True, blank=True)`
  - `effectiveness_due_date`: `DateField(null=True, blank=True)`
  - `effectiveness_method`: `CharField(max_length=255, blank=True)`
  - `effectiveness_results`: `TextField(blank=True)`
  - `is_effective`: `BooleanField(null=True, blank=True)`
  - `verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_scars")`
  - `closed_at`: `DateField(null=True, blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qsca_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_qsca_ten_status")`
  - `Index(fields=["tenant", "supplier"], name="idx_qsca_ten_supp")`
  - `Index(fields=["tenant", "severity"], name="idx_qsca_ten_sev")`
  - `Index(fields=["tenant", "root_cause_category"], name="idx_qsca_ten_cat")`
  - `Index(fields=["tenant", "response_due_date"], name="idx_qsca_ten_due")`
  - `Index(fields=["tenant", "-created_at"], name="idx_qsca_ten_created")`
- **Form Exclusions**: `tenant`, `number`, `closed_at`, `created_at`, `updated_at`

---

### 1.4 `SupplierChangeNotification` (SCN) (`SupplierChangeNotifications.py`)
- **`NUMBER_PREFIX`**: `"QSCN"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Supplier Change Notification (SCN)"` / `"Supplier Change Notifications (SCN)"`
- **Choices & Badge Maps**:
  - `CHANGE_CATEGORY_CHOICES` (`max_length=30`):
    - `("raw_material", "Raw Material / Component Change")`
    - `("manufacturing_process", "Manufacturing Process / Line Relocation")`
    - `("facility_location", "Facility / Manufacturing Site Change")`
    - `("tooling_equipment", "Tooling / Mold / Machine Replacement")`
    - `("packaging_labeling", "Packaging / Labeling Specification")`
    - `("specification_testing", "Testing Method / Specification Change")`
    - `("sub_tier_supplier", "Sub-Tier Supplier / Source Change")`
    - `("other", "Other Operational Change")`
  - `RISK_LEVEL_CHOICES` (`max_length=25`):
    - `("level_1_minor", "Level 1: Minor (Low Risk / Notification Only)")`
    - `("level_2_moderate", "Level 2: Moderate (Technical Review Required)")`
    - `("level_3_major", "Level 3: Major (Re-qualification / Validation Mandatory)")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("received", "Received / Logged")`
    - `("under_assessment", "Under Assessment")`
    - `("technical_evaluation", "Technical Evaluation")`
    - `("samples_pending", "Samples / Test Pending")`
    - `("approved", "Approved")`
    - `("conditional_approval", "Conditionally Approved")`
    - `("rejected", "Rejected")`
    - `("implemented", "Implemented / Live")`
  - `DISPOSITION_CHOICES` (`max_length=30`):
    - `("pending", "Pending Disposition")`
    - `("approved", "Approved (Proceed)")`
    - `("conditional_approval", "Conditional Approval (With Caveats)")`
    - `("rejected", "Rejected (Change Disallowed)")`
  - `CHANGE_CATEGORY_CSS`:
    - `"raw_material": "badge-red"`
    - `"manufacturing_process": "badge-amber"`
    - `"facility_location": "badge-info"`
    - `"tooling_equipment": "badge-slate"`
    - `"packaging_labeling": "badge-slate"`
    - `"specification_testing": "badge-amber"`
    - `"sub_tier_supplier": "badge-amber"`
    - `"other": "badge-muted"`
  - `RISK_LEVEL_CSS`:
    - `"level_1_minor": "badge-slate"`
    - `"level_2_moderate": "badge-amber"`
    - `"level_3_major": "badge-red"`
  - `STATUS_CSS`:
    - `"received": "badge-slate"`
    - `"under_assessment": "badge-amber"`
    - `"technical_evaluation": "badge-info"`
    - `"samples_pending": "badge-info"`
    - `"approved": "badge-green"`
    - `"conditional_approval": "badge-amber"`
    - `"rejected": "badge-red"`
    - `"implemented": "badge-green"`
  - `DISPOSITION_CSS`:
    - `"pending": "badge-slate"`
    - `"approved": "badge-green"`
    - `"conditional_approval": "badge-amber"`
    - `"rejected": "badge-red"`
- **Fields**:
  - `supplier`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="quality_scns")`
  - `title`: `CharField(max_length=255)`
  - `supplier_scn_number`: `CharField(max_length=100, blank=True)`
  - `change_category`: `CharField(max_length=30, choices=CHANGE_CATEGORY_CHOICES, default="raw_material", db_index=True)`
  - `risk_level`: `CharField(max_length=25, choices=RISK_LEVEL_CHOICES, default="level_2_moderate", db_index=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="received", db_index=True)`
  - `description`: `TextField(help_text="Detailed description of proposed process or material change")`
  - `proposed_effective_date`: `DateField(null=True, blank=True)`
  - `first_affected_lot`: `CharField(max_length=100, blank=True)`
  - `affected_item_code`: `CharField(max_length=100, blank=True)`
  - `affected_item_name`: `CharField(max_length=255, blank=True)`
  - `affects_form_fit_function`: `BooleanField(default=False)`
  - `requires_requalification`: `BooleanField(default=False)`
  - `requires_design_change`: `BooleanField(default=False)`
  - `requires_regulatory_filing`: `BooleanField(default=False)`
  - `requires_customer_notification`: `BooleanField(default=False)`
  - `samples_required`: `BooleanField(default=False)`
  - `impact_assessment_notes`: `TextField(blank=True)`
  - `design_project`: `ForeignKey("quality.DesignProject", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_scns")`
  - `requalification_audit`: `ForeignKey("quality.SupplierQualificationAudit", on_delete=models.SET_NULL, null=True, blank=True, related_name="change_notifications")`
  - `disposition`: `CharField(max_length=30, choices=DISPOSITION_CHOICES, default="pending", db_index=True)`
  - `disposition_notes`: `TextField(blank=True)`
  - `disposition_date`: `DateField(null=True, blank=True)`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_scns")`
  - `evaluated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="evaluated_scns")`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qscn_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_qscn_ten_status")`
  - `Index(fields=["tenant", "supplier"], name="idx_qscn_ten_supp")`
  - `Index(fields=["tenant", "risk_level"], name="idx_qscn_ten_risk")`
  - `Index(fields=["tenant", "change_category"], name="idx_qscn_ten_cat")`
  - `Index(fields=["tenant", "disposition"], name="idx_qscn_ten_disp")`
  - `Index(fields=["tenant", "-created_at"], name="idx_qscn_ten_created")`
- **Form Exclusions**: `tenant`, `number`, `disposition_date`, `created_at`, `updated_at`

---

## 2. Views, Forms & URLs Contract

### 2.1 URLs (`apps/quality/urls/SupplierQuality/`)
All namespaced under `quality:`:

#### `SupplierQualificationAudits.py`
- `path("audits/", views.supplier_qualification_audit_list, name="supplier_qualification_audit_list")`
- `path("audits/create/", views.supplier_qualification_audit_create, name="supplier_qualification_audit_create")`
- `path("audits/export/", views.supplier_qualification_audit_export, name="supplier_qualification_audit_export")`
- `path("audits/<int:pk>/", views.supplier_qualification_audit_detail, name="supplier_qualification_audit_detail")`
- `path("audits/<int:pk>/edit/", views.supplier_qualification_audit_edit, name="supplier_qualification_audit_edit")`
- `path("audits/<int:pk>/delete/", views.supplier_qualification_audit_delete, name="supplier_qualification_audit_delete")`
- `path("audits/<int:pk>/status/", views.supplier_qualification_audit_status, name="supplier_qualification_audit_status")`

#### `SupplierQualityScorecards.py`
- `path("scorecards/", views.supplier_quality_scorecard_list, name="supplier_quality_scorecard_list")`
- `path("scorecards/create/", views.supplier_quality_scorecard_create, name="supplier_quality_scorecard_create")`
- `path("scorecards/export/", views.supplier_quality_scorecard_export, name="supplier_quality_scorecard_export")`
- `path("scorecards/<int:pk>/", views.supplier_quality_scorecard_detail, name="supplier_quality_scorecard_detail")`
- `path("scorecards/<int:pk>/edit/", views.supplier_quality_scorecard_edit, name="supplier_quality_scorecard_edit")`
- `path("scorecards/<int:pk>/delete/", views.supplier_quality_scorecard_delete, name="supplier_quality_scorecard_delete")`
- `path("scorecards/<int:pk>/publish/", views.supplier_quality_scorecard_publish, name="supplier_quality_scorecard_publish")`

#### `SupplierCorrectiveActions.py`
- `path("scars/", views.supplier_corrective_action_list, name="supplier_corrective_action_list")`
- `path("scars/create/", views.supplier_corrective_action_create, name="supplier_corrective_action_create")`
- `path("scars/export/", views.supplier_corrective_action_export, name="supplier_corrective_action_export")`
- `path("scars/<int:pk>/", views.supplier_corrective_action_detail, name="supplier_corrective_action_detail")`
- `path("scars/<int:pk>/edit/", views.supplier_corrective_action_edit, name="supplier_corrective_action_edit")`
- `path("scars/<int:pk>/delete/", views.supplier_corrective_action_delete, name="supplier_corrective_action_delete")`
- `path("scars/<int:pk>/status/", views.supplier_corrective_action_status, name="supplier_corrective_action_status")`

#### `SupplierChangeNotifications.py`
- `path("scns/", views.supplier_change_notification_list, name="supplier_change_notification_list")`
- `path("scns/create/", views.supplier_change_notification_create, name="supplier_change_notification_create")`
- `path("scns/export/", views.supplier_change_notification_export, name="supplier_change_notification_export")`
- `path("scns/<int:pk>/", views.supplier_change_notification_detail, name="supplier_change_notification_detail")`
- `path("scns/<int:pk>/edit/", views.supplier_change_notification_edit, name="supplier_change_notification_edit")`
- `path("scns/<int:pk>/delete/", views.supplier_change_notification_delete, name="supplier_change_notification_delete")`
- `path("scns/<int:pk>/disposition/", views.supplier_change_notification_disposition, name="supplier_change_notification_disposition")`

#### `SupplierQualityDirectory.py`
- `path("avl/", views.avl_directory, name="avl_directory")`

---

### 2.2 View Context Keys Contract
- `supplier_qualification_audit_list`:
  - `audits`: paginated `Page` of `SupplierQualificationAudit`
  - `status_choices`: `SupplierQualificationAudit.QUALIFICATION_STATUS_CHOICES`
  - `tier_choices`: `SupplierQualificationAudit.CRITICALITY_TIER_CHOICES`
  - `result_choices`: `SupplierQualificationAudit.AUDIT_RESULT_CHOICES`
  - `suppliers`: queryset of `Party` with supplier/vendor role
  - `search_query`: `str`
  - `current_status`: `str`
  - `current_tier`: `str`
  - `current_supplier`: `str`
- `supplier_qualification_audit_detail`:
  - `audit`: `SupplierQualificationAudit` instance
  - `scars`: related `SupplierCorrectiveAction` queryset
  - `scns`: related `SupplierChangeNotification` queryset
- `supplier_qualification_audit_form`:
  - `form`: `SupplierQualificationAuditForm` instance
  - `audit`: `SupplierQualificationAudit` instance or `None`
- `supplier_quality_scorecard_list`:
  - `scorecards`: paginated `Page` of `SupplierQualityScorecard`
  - `cadence_choices`: `SupplierQualityScorecard.CADENCE_CHOICES`
  - `grade_choices`: `SupplierQualityScorecard.GRADE_CHOICES`
  - `status_choices`: `SupplierQualityScorecard.STATUS_CHOICES`
  - `suppliers`: queryset of `Party`
  - `search_query`: `str`
  - `current_status`: `str`
  - `current_grade`: `str`
  - `current_cadence`: `str`
- `supplier_quality_scorecard_detail`:
  - `scorecard`: `SupplierQualityScorecard` instance
- `supplier_quality_scorecard_form`:
  - `form`: `SupplierQualityScorecardForm` instance
  - `scorecard`: `SupplierQualityScorecard` instance or `None`
- `supplier_corrective_action_list`:
  - `scars`: paginated `Page` of `SupplierCorrectiveAction`
  - `severity_choices`: `SupplierCorrectiveAction.SEVERITY_CHOICES`
  - `status_choices`: `SupplierCorrectiveAction.STATUS_CHOICES`
  - `category_choices`: `SupplierCorrectiveAction.ROOT_CAUSE_CATEGORY_CHOICES`
  - `suppliers`: queryset of `Party`
  - `search_query`: `str`
  - `current_status`: `str`
  - `current_severity`: `str`
  - `current_category`: `str`
- `supplier_corrective_action_detail`:
  - `scar`: `SupplierCorrectiveAction` instance
- `supplier_corrective_action_form`:
  - `form`: `SupplierCorrectiveActionForm` instance
  - `scar`: `SupplierCorrectiveAction` instance or `None`
- `supplier_change_notification_list`:
  - `scns`: paginated `Page` of `SupplierChangeNotification`
  - `category_choices`: `SupplierChangeNotification.CHANGE_CATEGORY_CHOICES`
  - `risk_choices`: `SupplierChangeNotification.RISK_LEVEL_CHOICES`
  - `status_choices`: `SupplierChangeNotification.STATUS_CHOICES`
  - `disposition_choices`: `SupplierChangeNotification.DISPOSITION_CHOICES`
  - `suppliers`: queryset of `Party`
  - `search_query`: `str`
  - `current_status`: `str`
  - `current_risk`: `str`
  - `current_disposition`: `str`
- `supplier_change_notification_detail`:
  - `scn`: `SupplierChangeNotification` instance
- `supplier_change_notification_form`:
  - `form`: `SupplierChangeNotificationForm` instance
  - `scn`: `SupplierChangeNotification` instance or `None`
- `avl_directory`:
  - `qualifications`: queryset / Page of approved/active `SupplierQualificationAudit`
  - `active_count`: `int`
  - `critical_count`: `int`
  - `dock_to_stock_count`: `int`
  - `pending_audits_count`: `int`
  - `status_choices`: `SupplierQualificationAudit.QUALIFICATION_STATUS_CHOICES`
  - `tier_choices`: `SupplierQualificationAudit.CRITICALITY_TIER_CHOICES`

---

## 3. Sidebar Navigation Wiring (`apps/core/navigation.py`)

`LIVE_LINKS["12.6"]`:
```python
    "12.6": {
        "Supplier Qualification & Audit": "quality:supplier_qualification_audit_list",
        "Incoming Inspection & Receiving": "quality:avl_directory",
        "Supplier Performance Monitoring": "quality:supplier_quality_scorecard_list",
        "Supplier CAPA & Development": "quality:supplier_corrective_action_list",
        "Supplier Change Notification (SCN)": "quality:supplier_change_notification_list",
    },
```

---

## 4. Templates Directory Structure

```
templates/quality/supplierquality/
├── supplier_qualification_audit/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── supplier_quality_scorecard/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── supplier_corrective_action/
│   ├── list.html
│   ├── detail.html
│   └── form.html
├── supplier_change_notification/
│   ├── list.html
│   ├── detail.html
│   └── form.html
└── avl_directory.html
```
