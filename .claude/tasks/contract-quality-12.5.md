# Module 12.5 Pre-Build Contract — Non-Conformance & Deviation Management (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.5"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0009_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/NonConformance/`
  - `apps/quality/forms/NonConformance/`
  - `apps/quality/views/NonConformance/`
  - `apps/quality/urls/NonConformance/`
  - `templates/quality/nonconformance/{nonconformancereport,quarantinecontainment,mrbdisposition,processdeviation}/{list,detail,form}.html` + `templates/quality/nonconformance/ncr_analytics_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"contain"`, `"release"`, `"disposition"`, `"approve"`, `"close"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `red`, `slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `core.OrgUnit`, `core.Party`, `accounts.User`, `quality.NonConformanceReport`, `quality.CapaInvestigation`, `quality.ControlledDocument`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.

---

## 1. Models & Choices Contract (`apps/quality/models/NonConformance/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `NonConformanceReport` (`NonConformanceReports.py`)
- **`NUMBER_PREFIX`**: `"QNCR"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Non-Conformance Report"` / `"Non-Conformance Reports"`
- **Choices & Badge Maps**:
  - `SOURCE_TYPE_CHOICES` (`max_length=24`):
    - `("incoming", "Incoming Inspection")`
    - `("in_process", "In-Process Production")`
    - `("final_inspection", "Final Product Inspection")`
    - `("customer_return", "Customer Return / RMA")`
    - `("internal_audit", "Internal Quality Audit")`
    - `("supplier", "Supplier Facility Issue")`
  - `CATEGORY_CHOICES` (`max_length=24`):
    - `("material", "Raw Material / Component Defect")`
    - `("process", "Manufacturing Process Deviation")`
    - `("product", "Finished Product Out-of-Spec")`
    - `("supplier", "Supplier Quality Issue")`
    - `("facility", "Facility / Environmental Excursion")`
    - `("documentation", "Documentation / Labeling Error")`
  - `SEVERITY_CHOICES` (`max_length=16`):
    - `("minor", "Minor (Low Risk)")`
    - `("major", "Major (Quality Impact)")`
    - `("critical", "Critical (Safety / Regulatory)")`
  - `STATUS_CHOICES` (`max_length=32`):
    - `("draft", "Draft / Triage")`
    - `("containment_active", "Containment Active")`
    - `("under_investigation", "Under Investigation")`
    - `("mrb_review", "MRB Review")`
    - `("disposition_approved", "Disposition Approved")`
    - `("rework_in_progress", "Rework in Progress")`
    - `("closed", "Closed / Verified")`
    - `("voided", "Voided / Cancelled")`
  - `SOURCE_TYPE_CSS`:
    - `"incoming": "badge-info"`
    - `"in_process": "badge-amber"`
    - `"final_inspection": "badge-info"`
    - `"customer_return": "badge-red"`
    - `"internal_audit": "badge-slate"`
    - `"supplier": "badge-amber"`
  - `CATEGORY_CSS`:
    - `"material": "badge-amber"`
    - `"process": "badge-info"`
    - `"product": "badge-red"`
    - `"supplier": "badge-amber"`
    - `"facility": "badge-slate"`
    - `"documentation": "badge-info"`
  - `SEVERITY_CSS`:
    - `"minor": "badge-slate"`
    - `"major": "badge-amber"`
    - `"critical": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"containment_active": "badge-red"`
    - `"under_investigation": "badge-amber"`
    - `"mrb_review": "badge-info"`
    - `"disposition_approved": "badge-info"`
    - `"rework_in_progress": "badge-amber"`
    - `"closed": "badge-green"`
    - `"voided": "badge-muted"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField(help_text="Detailed description of the defect or non-conformance event")`
  - `source_type`: `CharField(max_length=24, choices=SOURCE_TYPE_CHOICES, default="in_process", db_index=True)`
  - `category`: `CharField(max_length=24, choices=CATEGORY_CHOICES, default="material", db_index=True)`
  - `severity`: `CharField(max_length=16, choices=SEVERITY_CHOICES, default="major", db_index=True)`
  - `status`: `CharField(max_length=32, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `defect_code`: `CharField(max_length=64, blank=True, help_text="Defect code (e.g., DIM-OOS, CONTAM, PKG-FAIL)")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="non_conformance_reports")`
  - `initiator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="initiated_ncrs")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_ncrs")`
  - `supplier_party`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_ncrs", help_text="Vendor or external supplier")`
  - `affected_item_code`: `CharField(max_length=100, blank=True, help_text="SKU or part number affected")`
  - `affected_item_name`: `CharField(max_length=255, blank=True, help_text="Item name or description")`
  - `lot_serial_numbers`: `CharField(max_length=255, blank=True, help_text="Batch, lot, or serial numbers")`
  - `quantity_inspected`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `quantity_nonconforming`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `unit_of_measure`: `CharField(max_length=32, default="EA", blank=True)`
  - `estimated_financial_loss`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `immediate_containment_required`: `BooleanField(default=True, help_text="Immediate physical quarantine or stop-shipment required")`
  - `capa_required`: `BooleanField(default=False, help_text="Critical or recurring defect requiring CAPA investigation")`
  - `capa_investigation`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="originating_ncrs", help_text="Linked CAPA record")`
  - `target_resolution_date`: `DateField(null=True, blank=True)`
  - `closed_at`: `DateTimeField(null=True, blank=True)`
  - `closed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="closed_ncrs")`
  - `closure_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qncr_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qncr_ten_status")` (19)
  - `Index(fields=["tenant", "severity"], name="idx_qncr_ten_severity")` (21)
  - `Index(fields=["tenant", "source_type"], name="idx_qncr_ten_src_type")` (21)
  - `Index(fields=["tenant", "category"], name="idx_qncr_ten_category")` (21)
  - `Index(fields=["tenant", "-created_at"], name="idx_qncr_ten_created")` (20)

### 1.2 `QuarantineContainment` (`QuarantineContainments.py`)
- **`NUMBER_PREFIX`**: `"QCNT"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Quarantine & Containment Record"` / `"Quarantine & Containment Records"`
- **Choices & Badge Maps**:
  - `HOLD_TYPE_CHOICES` (`max_length=24`):
    - `("physical_quarantine", "Physical Quarantine Cage / Bin")`
    - `("digital_hold", "Digital System / ERP Hold")`
    - `("stop_shipment", "Stop Shipment Notice")`
    - `("stop_production", "Stop Production Order")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("active", "Active Hold")`
    - `("partially_released", "Partially Released")`
    - `("released", "Fully Released")`
    - `("disposed", "Disposed / Scrapped")`
  - `HOLD_TYPE_CSS`:
    - `"physical_quarantine": "badge-amber"`
    - `"digital_hold": "badge-info"`
    - `"stop_shipment": "badge-red"`
    - `"stop_production": "badge-red"`
  - `STATUS_CSS`:
    - `"active": "badge-red"`
    - `"partially_released": "badge-amber"`
    - `"released": "badge-green"`
    - `"disposed": "badge-slate"`
- **Fields**:
  - `ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.CASCADE, related_name="containment_records")`
  - `title`: `CharField(max_length=255)`
  - `hold_type`: `CharField(max_length=24, choices=HOLD_TYPE_CHOICES, default="physical_quarantine", db_index=True)`
  - `quarantine_location`: `CharField(max_length=150, help_text="Quarantine storage location or holding bin")`
  - `red_tag_number`: `CharField(max_length=64, blank=True, help_text="Physical red tag identifier attached to items")`
  - `quantity_on_hold`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `unit_of_measure`: `CharField(max_length=32, default="EA", blank=True)`
  - `hold_date`: `DateField(default=timezone.now)`
  - `hold_applied_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="applied_quarantines")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="active", db_index=True)`
  - `release_criteria`: `TextField(blank=True, help_text="Conditions required before lifting quarantine")`
  - `released_quantity`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `release_date`: `DateField(null=True, blank=True)`
  - `released_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="released_quarantines")`
  - `disposition_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcnt_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qcnt_ten_status")` (19)
  - `Index(fields=["tenant", "hold_type"], name="idx_qcnt_ten_hold_type")` (22)
  - `Index(fields=["tenant", "ncr"], name="idx_qcnt_ten_ncr")` (16)
  - `Index(fields=["tenant", "-created_at"], name="idx_qcnt_ten_created")` (20)

### 1.3 `MrbDisposition` (`MrbDispositions.py`)
- **`NUMBER_PREFIX`**: `"QMRB"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"MRB Disposition"` / `"MRB Dispositions"`
- **Choices & Badge Maps**:
  - `DISPOSITION_DECISION_CHOICES` (`max_length=24`):
    - `("scrap", "Scrap & Destroy")`
    - `("rework", "Rework to Specification")`
    - `("repair", "Repair to Usable Condition")`
    - `("use_as_is", "Use-As-Is (Concession)")`
    - `("return_to_vendor", "Return to Vendor (RTV)")`
    - `("regrade", "Downgrade / Re-grade")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Draft")`
    - `("under_review", "Under MRB Review")`
    - `("approved", "Disposition Approved")`
    - `("rejected", "Disposition Rejected")`
    - `("executed", "Executed / Completed")`
  - `DISPOSITION_DECISION_CSS`:
    - `"scrap": "badge-red"`
    - `"rework": "badge-amber"`
    - `"repair": "badge-amber"`
    - `"use_as_is": "badge-info"`
    - `"return_to_vendor": "badge-slate"`
    - `"regrade": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"under_review": "badge-info"`
    - `"approved": "badge-green"`
    - `"rejected": "badge-red"`
    - `"executed": "badge-green"`
- **Fields**:
  - `ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.CASCADE, related_name="mrb_dispositions")`
  - `title`: `CharField(max_length=255)`
  - `disposition_decision`: `CharField(max_length=24, choices=DISPOSITION_DECISION_CHOICES, default="rework", db_index=True)`
  - `technical_justification`: `TextField(help_text="Engineering and quality rationale for the chosen disposition")`
  - `concession_rationale`: `TextField(blank=True, help_text="Safety and efficacy rationale if Use-As-Is concession is granted")`
  - `rework_instructions`: `TextField(blank=True, help_text="Detailed step-by-step rework or repair instructions")`
  - `rework_assignee`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_reworks")`
  - `rework_completed_date`: `DateField(null=True, blank=True)`
  - `reinspection_required`: `BooleanField(default=True, help_text="Requires quality reinspection after rework")`
  - `reinspection_criteria`: `TextField(blank=True, help_text="Acceptance test criteria for post-rework inspection")`
  - `reinspection_passed`: `BooleanField(null=True, blank=True, help_text="Outcome of reinspection (None=pending, True=passed, False=failed)")`
  - `reinspection_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reinspected_mrb_items")`
  - `scrap_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `rework_labor_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `vendor_chargeback_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `total_cost_impact`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `mrb_chair`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="chaired_mrb_dispositions")`
  - `quality_approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_approved_mrbs")`
  - `engineering_approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="engineering_approved_mrbs")`
  - `operations_approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="operations_approved_mrbs")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="under_review", db_index=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qmrb_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qmrb_ten_status")` (19)
  - `Index(fields=["tenant", "disposition_decision"], name="idx_qmrb_ten_disp_dec")` (21)
  - `Index(fields=["tenant", "ncr"], name="idx_qmrb_ten_ncr")` (16)
  - `Index(fields=["tenant", "-created_at"], name="idx_qmrb_ten_created")` (20)

### 1.4 `ProcessDeviation` (`ProcessDeviations.py`)
- **`NUMBER_PREFIX`**: `"QDEV"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Process Deviation"` / `"Process Deviations"`
- **Choices & Badge Maps**:
  - `DEVIATION_TYPE_CHOICES` (`max_length=16`):
    - `("planned", "Planned (Temporary Concession)")`
    - `("unplanned", "Unplanned (Process Excursion)")`
  - `CATEGORY_CHOICES` (`max_length=32`):
    - `("process_parameter", "Process Parameter Out-of-Spec")`
    - `("equipment_substitution", "Equipment / Machine Substitution")`
    - `("material_substitution", "Raw Material / Component Substitution")`
    - `("procedural_exemption", "Procedural / SOP Exemption")`
    - `("environmental", "Cleanroom / Environmental Excursion")`
  - `RISK_IMPACT_CHOICES` (`max_length=16`):
    - `("negligible", "Negligible Impact")`
    - `("minor", "Minor Risk")`
    - `("moderate", "Moderate Risk")`
    - `("critical", "Critical Product Risk")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Draft")`
    - `("under_assessment", "Under Impact Assessment")`
    - `("approved", "Approved")`
    - `("active", "Active Production Run")`
    - `("expired", "Expired")`
    - `("closed", "Closed / Completed")`
    - `("cancelled", "Cancelled")`
  - `DEVIATION_TYPE_CSS`:
    - `"planned": "badge-info"`
    - `"unplanned": "badge-amber"`
  - `CATEGORY_CSS`:
    - `"process_parameter": "badge-amber"`
    - `"equipment_substitution": "badge-info"`
    - `"material_substitution": "badge-amber"`
    - `"procedural_exemption": "badge-slate"`
    - `"environmental": "badge-red"`
  - `RISK_IMPACT_CSS`:
    - `"negligible": "badge-slate"`
    - `"minor": "badge-info"`
    - `"moderate": "badge-amber"`
    - `"critical": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"under_assessment": "badge-info"`
    - `"approved": "badge-green"`
    - `"active": "badge-amber"`
    - `"expired": "badge-red"`
    - `"closed": "badge-green"`
    - `"cancelled": "badge-muted"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `deviation_type`: `CharField(max_length=16, choices=DEVIATION_TYPE_CHOICES, default="unplanned", db_index=True)`
  - `category`: `CharField(max_length=32, choices=CATEGORY_CHOICES, default="process_parameter", db_index=True)`
  - `ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="process_deviations", help_text="Originating NCR if unplanned")`
  - `controlled_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="process_deviations", help_text="Operating procedure or work instruction being deviated from")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="process_deviations")`
  - `requested_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_deviations")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_deviations")`
  - `risk_impact_level`: `CharField(max_length=16, choices=RISK_IMPACT_CHOICES, default="minor", db_index=True)`
  - `quality_impact_assessment`: `TextField(help_text="Detailed assessment of impact on product safety, efficacy, validation, and stability")`
  - `affected_lots_summary`: `TextField(blank=True, help_text="List of batches, lots, or serial runs produced under this deviation")`
  - `customer_notification_required`: `BooleanField(default=False, help_text="Customer notification or concession approval required")`
  - `customer_concession_obtained`: `BooleanField(default=False)`
  - `regulatory_reporting_required`: `BooleanField(default=False, help_text="Regulatory health authority notification required")`
  - `regulatory_authority_notified`: `BooleanField(default=False)`
  - `valid_from`: `DateField(null=True, blank=True)`
  - `valid_until`: `DateField(null=True, blank=True, help_text="Mandatory expiration date for temporary deviation")`
  - `max_batches_permitted`: `PositiveIntegerField(default=1, help_text="Maximum number of batches/lots permitted under this deviation")`
  - `batches_produced_count`: `PositiveIntegerField(default=0, help_text="Actual number of batches produced to date")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qdev_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qdev_ten_status")` (19)
  - `Index(fields=["tenant", "deviation_type"], name="idx_qdev_ten_dev_type")` (21)
  - `Index(fields=["tenant", "valid_until"], name="idx_qdev_ten_valid_until")` (24)
  - `Index(fields=["tenant", "-created_at"], name="idx_qdev_ten_created")` (20)

---

## 2. Forms Contract (`apps/quality/forms/NonConformance/`)

All ModelForms inherit `django.forms.ModelForm`. They inject `self.tenant` in `__init__`, apply standard CSS classes (`form-input`, `form-select`, `form-textarea`), populate tenant-scoped foreign keys with `Model.objects.filter(tenant=self.tenant)`, and validate in `clean()` via `reject_foreign(...)`.

### 2.1 `NonConformanceReportForm` (`NonConformanceReports.py`)
- **`Meta.model`**: `NonConformanceReport`
- **`Meta.fields`**:
  `title`, `description`, `source_type`, `category`, `severity`, `status`, `defect_code`, `department`, `initiator`, `owner`, `supplier_party`, `affected_item_code`, `affected_item_name`, `lot_serial_numbers`, `quantity_inspected`, `quantity_nonconforming`, `unit_of_measure`, `estimated_financial_loss`, `immediate_containment_required`, `capa_required`, `capa_investigation`, `target_resolution_date`, `closure_notes`
- **Excluded**:
  `tenant`, `number`, `closed_at`, `closed_by`, `created_at`, `updated_at`

### 2.2 `QuarantineContainmentForm` (`QuarantineContainments.py`)
- **`Meta.model`**: `QuarantineContainment`
- **`Meta.fields`**:
  `ncr`, `title`, `hold_type`, `quarantine_location`, `red_tag_number`, `quantity_on_hold`, `unit_of_measure`, `hold_date`, `hold_applied_by`, `status`, `release_criteria`, `released_quantity`, `release_date`, `released_by`, `disposition_notes`
- **Excluded**:
  `tenant`, `number`, `created_at`, `updated_at`

### 2.3 `MrbDispositionForm` (`MrbDispositions.py`)
- **`Meta.model`**: `MrbDisposition`
- **`Meta.fields`**:
  `ncr`, `title`, `disposition_decision`, `technical_justification`, `concession_rationale`, `rework_instructions`, `rework_assignee`, `rework_completed_date`, `reinspection_required`, `reinspection_criteria`, `reinspection_passed`, `reinspection_by`, `scrap_cost`, `rework_labor_cost`, `vendor_chargeback_cost`, `total_cost_impact`, `mrb_chair`, `quality_approved_by`, `engineering_approved_by`, `operations_approved_by`, `status`
- **Excluded**:
  `tenant`, `number`, `created_at`, `updated_at`

### 2.4 `ProcessDeviationForm` (`ProcessDeviations.py`)
- **`Meta.model`**: `ProcessDeviation`
- **`Meta.fields`**:
  `title`, `deviation_type`, `category`, `ncr`, `controlled_document`, `department`, `requested_by`, `approved_by`, `risk_impact_level`, `quality_impact_assessment`, `affected_lots_summary`, `customer_notification_required`, `customer_concession_obtained`, `regulatory_reporting_required`, `regulatory_authority_notified`, `valid_from`, `valid_until`, `max_batches_permitted`, `batches_produced_count`, `status`
- **Excluded**:
  `tenant`, `number`, `created_at`, `updated_at`

---

## 3. Views & URLs Contract (`apps/quality/views/NonConformance/` & `apps/quality/urls/NonConformance/`)

All views are function-based, decorated with `@login_required` (mutating/destructive views with `@require_POST`, admin-only actions with `@tenant_admin_required`), filter by `tenant=request.tenant`, and call `write_audit_log(request.user, obj, verb, tenant=request.tenant)`.

### 3.1 `NonConformanceReport`
- **URL Patterns**:
  - `path('ncrs/', views.non_conformance_report_list, name='non_conformance_report_list')`
  - `path('ncrs/create/', views.non_conformance_report_create, name='non_conformance_report_create')`
  - `path('ncrs/<int:pk>/', views.non_conformance_report_detail, name='non_conformance_report_detail')`
  - `path('ncrs/<int:pk>/edit/', views.non_conformance_report_edit, name='non_conformance_report_edit')`
  - `path('ncrs/<int:pk>/delete/', views.non_conformance_report_delete, name='non_conformance_report_delete')`
  - `path('ncrs/export/csv/', views.non_conformance_report_export_csv, name='non_conformance_report_export_csv')`
- **Context Keys**:
  - List view:
    - `non_conformance_reports`: paginated records
    - `page_obj`: paginator page object
    - `paginator`: Paginator instance
    - `q`: search query string
    - `selected_status`: filter value
    - `selected_severity`: filter value
    - `selected_source_type`: filter value
    - `selected_category`: filter value
    - `status_choices`: `NonConformanceReport.STATUS_CHOICES`
    - `severity_choices`: `NonConformanceReport.SEVERITY_CHOICES`
    - `source_type_choices`: `NonConformanceReport.SOURCE_TYPE_CHOICES`
    - `category_choices`: `NonConformanceReport.CATEGORY_CHOICES`
    - `total_count`: integer total
  - Detail view:
    - `non_conformance_report`: the object
    - `containment_records`: related `QuarantineContainment` queryset
    - `mrb_dispositions`: related `MrbDisposition` queryset
    - `process_deviations`: related `ProcessDeviation` queryset
  - Form view:
    - `form`: form instance
    - `non_conformance_report`: instance if editing, None if creating
    - `is_edit`: boolean

### 3.2 `QuarantineContainment`
- **URL Patterns**:
  - `path('quarantines/', views.quarantine_containment_list, name='quarantine_containment_list')`
  - `path('quarantines/create/', views.quarantine_containment_create, name='quarantine_containment_create')`
  - `path('quarantines/<int:pk>/', views.quarantine_containment_detail, name='quarantine_containment_detail')`
  - `path('quarantines/<int:pk>/edit/', views.quarantine_containment_edit, name='quarantine_containment_edit')`
  - `path('quarantines/<int:pk>/delete/', views.quarantine_containment_delete, name='quarantine_containment_delete')`
- **Context Keys**:
  - List view:
    - `quarantine_containments`: paginated records
    - `page_obj`: paginator page object
    - `paginator`: Paginator instance
    - `q`: search query string
    - `selected_status`: filter value
    - `selected_hold_type`: filter value
    - `status_choices`: `QuarantineContainment.STATUS_CHOICES`
    - `hold_type_choices`: `QuarantineContainment.HOLD_TYPE_CHOICES`
    - `total_count`: integer total
  - Detail view:
    - `quarantine_containment`: the object
  - Form view:
    - `form`: form instance
    - `quarantine_containment`: instance if editing, None if creating
    - `is_edit`: boolean

### 3.3 `MrbDisposition`
- **URL Patterns**:
  - `path('mrb-dispositions/', views.mrb_disposition_list, name='mrb_disposition_list')`
  - `path('mrb-dispositions/create/', views.mrb_disposition_create, name='mrb_disposition_create')`
  - `path('mrb-dispositions/<int:pk>/', views.mrb_disposition_detail, name='mrb_disposition_detail')`
  - `path('mrb-dispositions/<int:pk>/edit/', views.mrb_disposition_edit, name='mrb_disposition_edit')`
  - `path('mrb-dispositions/<int:pk>/delete/', views.mrb_disposition_delete, name='mrb_disposition_delete')`
- **Context Keys**:
  - List view:
    - `mrb_dispositions`: paginated records
    - `page_obj`: paginator page object
    - `paginator`: Paginator instance
    - `q`: search query string
    - `selected_status`: filter value
    - `selected_decision`: filter value
    - `status_choices`: `MrbDisposition.STATUS_CHOICES`
    - `decision_choices`: `MrbDisposition.DISPOSITION_DECISION_CHOICES`
    - `total_count`: integer total
  - Detail view:
    - `mrb_disposition`: the object
  - Form view:
    - `form`: form instance
    - `mrb_disposition`: instance if editing, None if creating
    - `is_edit`: boolean

### 3.4 `ProcessDeviation`
- **URL Patterns**:
  - `path('deviations/', views.process_deviation_list, name='process_deviation_list')`
  - `path('deviations/create/', views.process_deviation_create, name='process_deviation_create')`
  - `path('deviations/<int:pk>/', views.process_deviation_detail, name='process_deviation_detail')`
  - `path('deviations/<int:pk>/edit/', views.process_deviation_edit, name='process_deviation_edit')`
  - `path('deviations/<int:pk>/delete/', views.process_deviation_delete, name='process_deviation_delete')`
- **Context Keys**:
  - List view:
    - `process_deviations`: paginated records
    - `page_obj`: paginator page object
    - `paginator`: Paginator instance
    - `q`: search query string
    - `selected_status`: filter value
    - `selected_deviation_type`: filter value
    - `selected_risk_level`: filter value
    - `status_choices`: `ProcessDeviation.STATUS_CHOICES`
    - `deviation_type_choices`: `ProcessDeviation.DEVIATION_TYPE_CHOICES`
    - `risk_level_choices`: `ProcessDeviation.RISK_IMPACT_CHOICES`
    - `total_count`: integer total
  - Detail view:
    - `process_deviation`: the object
  - Form view:
    - `form`: form instance
    - `process_deviation`: instance if editing, None if creating
    - `is_edit`: boolean

### 3.5 `NcrAnalytics` (Trending & Dashboard)
- **URL Pattern**:
  - `path('analytics/', views.ncr_analytics_dashboard, name='ncr_analytics_dashboard')`
- **Context Keys**:
  - `total_ncrs`: integer
  - `open_ncrs`: integer
  - `active_quarantines`: integer
  - `pending_mrbs`: integer
  - `total_scrap_cost`: Decimal
  - `total_rework_cost`: Decimal
  - `severity_breakdown`: list of `{"severity": label, "count": count, "css": badge_class}`
  - `category_breakdown`: list of `{"category": label, "count": count, "css": badge_class}`
  - `source_breakdown`: list of `{"source": label, "count": count, "css": badge_class}`
  - `recent_ncrs`: queryset of 5 recent NCRs

---

## 4. `apps/core/navigation.py` Wire-Up Contract

Add to `LIVE_LINKS` under `"12.5"`:
```python
    "12.5": {
        "NCR Initiation & Classification": "quality:non_conformance_report_list",
        "Containment & Segregation": "quality:quarantine_containment_list",
        "Disposition & Material Review": "quality:mrb_disposition_list",
        "Impact Assessment & Customer Notification": "quality:process_deviation_list",
        "Trending & Metrics": "quality:ncr_analytics_dashboard",
    },
```
All 5 feature bullets from `NavERP.md 12.5` mapped directly to live URLs.
