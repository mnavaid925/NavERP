# Module 12.7 Pre-Build Contract — Incoming Quality Control (IQC) (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.7"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0013_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/IncomingQuality/`
  - `apps/quality/forms/IncomingQuality/`
  - `apps/quality/views/IncomingQuality/`
  - `apps/quality/urls/IncomingQuality/`
  - `templates/quality/incoming_quality/{incoming_inspection_plan,incoming_inspection_lot,certificate_of_analysis,quality_return_authorization}/{list,detail,form}.html` + `templates/quality/incoming_quality/spc_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"sample"`, `"decide"`, `"verify"`, `"advance"`, `"close"`, `"reject"` (all `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `core.Party` (with `PartyRole` supplier/vendor), `accounts.User`, `quality.ControlledDocument`, `scm.PurchaseOrder`, `scm.GoodsReceiptNote`, `quality.NonConformanceReport`, `quality.ProcessDeviation`, `quality.QuarantineContainment`, `quality.SupplierCorrectiveAction`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/IncomingQuality/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `IncomingInspectionPlan` (`IncomingInspectionPlans.py`)
- **`NUMBER_PREFIX`**: `"QIIP"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Incoming Inspection Plan"` / `"Incoming Inspection Plans"`
- **Choices & Badge Maps**:
  - `SAMPLING_STANDARD_CHOICES` (`max_length=25`):
    - `("ansi_asq_z14", "ANSI/ASQ Z1.4 (Attribute Sampling)")`
    - `("iso_2859_1", "ISO 2859-1 (Lot-by-Lot Inspection)")`
    - `("c_zero_squeglia", "Zero-Defect (c=0 Squeglia Plan)")`
    - `("fixed_percentage", "Fixed Percentage Sampling")`
    - `("one_hundred_pct", "100% Comprehensive Inspection")`
  - `INSPECTION_LEVEL_CHOICES` (`max_length=15`):
    - `("level_1", "General Level I (Reduced)")`
    - `("level_2", "General Level II (Normal / Default)")`
    - `("level_3", "General Level III (Tightened)")`
    - `("special_s1", "Special Level S-1")`
    - `("special_s2", "Special Level S-2")`
    - `("special_s3", "Special Level S-3")`
    - `("special_s4", "Special Level S-4")`
  - `INSPECTION_SEVERITY_CHOICES` (`max_length=15`):
    - `("normal", "Normal Inspection")`
    - `("tightened", "Tightened Inspection")`
    - `("reduced", "Reduced Inspection")`
  - `INSPECTION_FREQUENCY_CHOICES` (`max_length=20`):
    - `("every_lot", "Every Received Lot")`
    - `("skip_lot", "Skip-Lot (1 in N Lots)")`
    - `("dock_to_stock", "Dock-to-Stock (Bypass Inspection)")`
    - `("first_article", "First Article Inspection (FAI)")`
  - `STATUS_CHOICES` (`max_length=15`):
    - `("draft", "Draft")`
    - `("active", "Active")`
    - `("under_revision", "Under Revision")`
    - `("obsolete", "Obsolete")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"active": "badge-green"`
    - `"under_revision": "badge-amber"`
    - `"obsolete": "badge-muted"`
  - `FREQUENCY_CSS`:
    - `"every_lot": "badge-info"`
    - `"skip_lot": "badge-slate"`
    - `"dock_to_stock": "badge-green"`
    - `"first_article": "badge-amber"`
- **Fields**:
  - `title`: `CharField(max_length=150)`
  - `item_code`: `CharField(max_length=50, db_index=True)`
  - `item_name`: `CharField(max_length=150)`
  - `revision`: `CharField(max_length=20, default="A")`
  - `supplier`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_inspection_plans")`
  - `sampling_standard`: `CharField(max_length=25, choices=SAMPLING_STANDARD_CHOICES, default="ansi_asq_z14", db_index=True)`
  - `inspection_level`: `CharField(max_length=15, choices=INSPECTION_LEVEL_CHOICES, default="level_2")`
  - `inspection_severity`: `CharField(max_length=15, choices=INSPECTION_SEVERITY_CHOICES, default="normal")`
  - `inspection_frequency`: `CharField(max_length=20, choices=INSPECTION_FREQUENCY_CHOICES, default="every_lot", db_index=True)`
  - `skip_lot_interval`: `PositiveIntegerField(default=5, help_text="Inspect 1 in every N lots if skip-lot enabled")`
  - `aql_critical`: `DecimalField(max_digits=4, decimal_places=2, default=0.00, help_text="Critical Defect AQL (typically 0.00)")`
  - `aql_major`: `DecimalField(max_digits=4, decimal_places=2, default=1.00, help_text="Major Defect AQL (typically 1.00 or 0.65)")`
  - `aql_minor`: `DecimalField(max_digits=4, decimal_places=2, default=4.00, help_text="Minor Defect AQL (typically 4.00 or 2.50)")`
  - `requires_coa`: `BooleanField(default=True, help_text="CoA must be received and verified prior to lot release")`
  - `requires_coc`: `BooleanField(default=False, help_text="Certificate of Conformance required")`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `characteristics_matrix`: `JSONField(default=list, blank=True, help_text="List of CTQ specs: [{name, type, usl, lsl, target, unit, test_method}]")`
  - `sop_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_inspection_plans")`
  - `assigned_team`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_inspection_plans")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qiip_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_qiip_ten_status")`
  - `Index(fields=["tenant", "item_code"], name="idx_qiip_ten_item")`
  - `Index(fields=["tenant", "supplier"], name="idx_qiip_ten_supp")`
  - `Index(fields=["tenant", "inspection_frequency"], name="idx_qiip_ten_freq")`

---

### 1.2 `IncomingInspectionLot` (`IncomingInspectionLots.py`)
- **`NUMBER_PREFIX`**: `"QIIL"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Incoming Inspection Lot"` / `"Incoming Inspection Lots"`
- **Choices & Badge Maps**:
  - `STAGE_CHOICES` (`max_length=20`):
    - `("pending_receipt", "Pending Dock Receipt")`
    - `("in_inspection", "In Inspection")`
    - `("sampling_complete", "Sampling Completed")`
    - `("under_mrb", "Under MRB / Disposition Review")`
    - `("completed", "Completed / Closed")`
    - `("cancelled", "Cancelled")`
  - `USAGE_DECISION_CHOICES` (`max_length=25`):
    - `("pending", "Pending Decision")`
    - `("accepted", "Accepted (Full Release)")`
    - `("accepted_with_deviation", "Accepted with Concession / Deviation")`
    - `("quarantined", "Quarantined for Containment")`
    - `("rejected", "Rejected / Return to Vendor")`
    - `("skip_lot_passed", "Skip-Lot Auto Released")`
  - `STAGE_CSS`:
    - `"pending_receipt": "badge-slate"`
    - `"in_inspection": "badge-info"`
    - `"sampling_complete": "badge-amber"`
    - `"under_mrb": "badge-amber"`
    - `"completed": "badge-green"`
    - `"cancelled": "badge-muted"`
  - `USAGE_DECISION_CSS`:
    - `"pending": "badge-slate"`
    - `"accepted": "badge-green"`
    - `"accepted_with_deviation": "badge-amber"`
    - `"quarantined": "badge-red"`
    - `"rejected": "badge-red"`
    - `"skip_lot_passed": "badge-info"`
- **Fields**:
  - `inspection_plan`: `ForeignKey(IncomingInspectionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="inspection_lots")`
  - `item_code`: `CharField(max_length=50, db_index=True)`
  - `item_name`: `CharField(max_length=150)`
  - `supplier`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="incoming_inspection_lots")`
  - `purchase_order`: `ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_inspection_lots")`
  - `goods_receipt_note`: `ForeignKey("scm.GoodsReceiptNote", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_inspection_lots")`
  - `lot_number`: `CharField(max_length=50, db_index=True)`
  - `heat_or_batch`: `CharField(max_length=50, blank=True)`
  - `receipt_date`: `DateField(null=True, blank=True)`
  - `inspection_date`: `DateField(null=True, blank=True)`
  - `lot_quantity`: `DecimalField(max_digits=12, decimal_places=3, default=0.000)`
  - `sample_size`: `PositiveIntegerField(default=0, help_text="Sample size computed from ANSI/ASQ Z1.4")`
  - `inspected_quantity`: `PositiveIntegerField(default=0)`
  - `accepted_quantity`: `DecimalField(max_digits=12, decimal_places=3, default=0.000)`
  - `rejected_quantity`: `DecimalField(max_digits=12, decimal_places=3, default=0.000)`
  - `quarantine_quantity`: `DecimalField(max_digits=12, decimal_places=3, default=0.000)`
  - `critical_defects`: `PositiveIntegerField(default=0)`
  - `major_defects`: `PositiveIntegerField(default=0)`
  - `minor_defects`: `PositiveIntegerField(default=0)`
  - `stage`: `CharField(max_length=20, choices=STAGE_CHOICES, default="pending_receipt", db_index=True)`
  - `usage_decision`: `CharField(max_length=25, choices=USAGE_DECISION_CHOICES, default="pending", db_index=True)`
  - `usage_decision_notes`: `TextField(blank=True)`
  - `decided_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="decided_inspection_lots")`
  - `decided_at`: `DateTimeField(null=True, blank=True)`
  - `inspector`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="inspected_inspection_lots")`
  - `measurements_data`: `JSONField(default=list, blank=True, help_text="Raw CTQ measurements: [{characteristic, sample_no, value, is_pass}]")`
  - `spc_mean`: `DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)`
  - `spc_std_dev`: `DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)`
  - `spc_cp`: `DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)`
  - `spc_cpk`: `DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)`
  - `spc_out_of_control`: `BooleanField(default=False)`
  - `linked_ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="originating_inspection_lots")`
  - `linked_deviation`: `ForeignKey("quality.ProcessDeviation", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_inspection_lots")`
  - `linked_containment`: `ForeignKey("quality.QuarantineContainment", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_inspection_lots")`
  - `linked_scar`: `ForeignKey("quality.SupplierCorrectiveAction", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_inspection_lots")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qiil_ten_num_uniq")`
  - `Index(fields=["tenant", "stage"], name="idx_qiil_ten_stage")`
  - `Index(fields=["tenant", "usage_decision"], name="idx_qiil_ten_decision")`
  - `Index(fields=["tenant", "supplier"], name="idx_qiil_ten_supp")`
  - `Index(fields=["tenant", "item_code"], name="idx_qiil_ten_item")`
  - `Index(fields=["tenant", "lot_number"], name="idx_qiil_ten_lot")`

---

### 1.3 `CertificateOfAnalysis` (`CertificatesOfAnalysis.py`)
- **`NUMBER_PREFIX`**: `"QCOA"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Certificate of Analysis"` / `"Certificates of Analysis"`
- **Choices & Badge Maps**:
  - `STATUS_CHOICES` (`max_length=20`):
    - `("received", "Received / Unverified")`
    - `("verified_compliant", "Verified Compliant")`
    - `("exception_detected", "Specification Exception Detected")`
    - `("rejected", "Rejected / Invalid CoA")`
  - `STATUS_CSS`:
    - `"received": "badge-slate"`
    - `"verified_compliant": "badge-green"`
    - `"exception_detected": "badge-amber"`
    - `"rejected": "badge-red"`
- **Fields**:
  - `certificate_number`: `CharField(max_length=100, help_text="Supplier's original CoA/Test Report number")`
  - `supplier`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="certificates_of_analysis")`
  - `item_code`: `CharField(max_length=50, db_index=True)`
  - `item_name`: `CharField(max_length=150)`
  - `lot_number`: `CharField(max_length=50, db_index=True)`
  - `inspection_lot`: `ForeignKey(IncomingInspectionLot, on_delete=models.SET_NULL, null=True, blank=True, related_name="certificates_of_analysis")`
  - `inspection_plan`: `ForeignKey(IncomingInspectionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="certificates_of_analysis")`
  - `manufacturer_name`: `CharField(max_length=150, blank=True)`
  - `date_of_manufacture`: `DateField(null=True, blank=True)`
  - `expiry_or_retest_date`: `DateField(null=True, blank=True)`
  - `lab_accreditation`: `CharField(max_length=100, blank=True, help_text="e.g. ISO/IEC 17025 accredited laboratory")`
  - `parameters_payload`: `JSONField(default=list, blank=True, help_text="Analytical parameters: [{parameter, method, lsl, target, usl, actual_value, unit, is_pass}]")`
  - `variance_count`: `PositiveIntegerField(default=0, help_text="Number of parameters failing tolerance limits")`
  - `is_within_spec`: `BooleanField(default=True, db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="received", db_index=True)`
  - `verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_coas")`
  - `verified_at`: `DateTimeField(null=True, blank=True)`
  - `supporting_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_coas")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcoa_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_qcoa_ten_status")`
  - `Index(fields=["tenant", "supplier"], name="idx_qcoa_ten_supp")`
  - `Index(fields=["tenant", "item_code"], name="idx_qcoa_ten_item")`
  - `Index(fields=["tenant", "lot_number"], name="idx_qcoa_ten_lot")`
  - `Index(fields=["tenant", "is_within_spec"], name="idx_qcoa_ten_within_spec")`

---

### 1.4 `QualityReturnAuthorization` (`QualityReturnAuthorizations.py`)
- **`NUMBER_PREFIX`**: `"QRMA"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Quality Return Authorization"` / `"Quality Return Authorizations"`
- **Choices & Badge Maps**:
  - `RETURN_REASON_CHOICES` (`max_length=30`):
    - `("dimensional_oos", "Dimensional Out-of-Specification")`
    - `("functional_failure", "Functional / Electrical Failure")`
    - `("coa_non_compliance", "Certificate of Analysis Non-Compliance")`
    - `("cosmetic_visual", "Cosmetic / Visual Defect")`
    - `("wrong_material", "Wrong Material / Incorrect Grade")`
    - `("packaging_damage", "Packaging Damage / Transit Breach")`
    - `("contamination", "Foreign Matter / Bioburden Contamination")`
    - `("expired_shelf_life", "Expired or Past Retest Shelf-Life")`
  - `DISPOSITION_TYPE_CHOICES` (`max_length=25`):
    - `("return_for_credit", "Return for Credit / Debit Memo")`
    - `("return_for_replacement", "Return for Replacement")`
    - `("return_for_rework", "Return for Supplier Rework")`
    - `("scrap_on_site", "Scrap on Site (Supplier Credit)")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("draft", "Draft Initiation")`
    - `("rma_requested", "RMA Requested from Vendor")`
    - `("rma_approved", "RMA Approved by Vendor")`
    - `("shipped_to_vendor", "Goods Shipped to Vendor")`
    - `("received_by_vendor", "Received by Vendor")`
    - `("settled_closed", "Settled & Closed")`
    - `("cancelled", "Cancelled")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"rma_requested": "badge-amber"`
    - `"rma_approved": "badge-info"`
    - `"shipped_to_vendor": "badge-info"`
    - `"received_by_vendor": "badge-amber"`
    - `"settled_closed": "badge-green"`
    - `"cancelled": "badge-muted"`
  - `DISPOSITION_CSS`:
    - `"return_for_credit": "badge-green"`
    - `"return_for_replacement": "badge-info"`
    - `"return_for_rework": "badge-amber"`
    - `"scrap_on_site": "badge-red"`
- **Fields**:
  - `inspection_lot`: `ForeignKey(IncomingInspectionLot, on_delete=models.CASCADE, related_name="return_authorizations")`
  - `supplier`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="quality_return_authorizations")`
  - `vendor_rma_number`: `CharField(max_length=100, blank=True, help_text="Vendor-issued return authorization reference")`
  - `return_reason`: `CharField(max_length=30, choices=RETURN_REASON_CHOICES, default="dimensional_oos", db_index=True)`
  - `disposition_type`: `CharField(max_length=25, choices=DISPOSITION_TYPE_CHOICES, default="return_for_credit", db_index=True)`
  - `return_quantity`: `DecimalField(max_digits=12, decimal_places=3, default=0.000)`
  - `unit_of_measure`: `CharField(max_length=20, default="EA")`
  - `estimated_credit_value`: `DecimalField(max_digits=12, decimal_places=2, default=0.00)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `carrier`: `CharField(max_length=100, blank=True)`
  - `tracking_number`: `CharField(max_length=100, blank=True)`
  - `bill_of_lading`: `CharField(max_length=100, blank=True)`
  - `shipped_date`: `DateField(null=True, blank=True)`
  - `vendor_receipt_date`: `DateField(null=True, blank=True)`
  - `debit_memo_number`: `CharField(max_length=50, blank=True)`
  - `settled_amount`: `DecimalField(max_digits=12, decimal_places=2, default=0.00)`
  - `settlement_date`: `DateField(null=True, blank=True)`
  - `assigned_coordinator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="coordinated_rmas")`
  - `linked_ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="return_authorizations")`
  - `linked_scar`: `ForeignKey("quality.SupplierCorrectiveAction", on_delete=models.SET_NULL, null=True, blank=True, related_name="return_authorizations")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrma_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_qrma_ten_status")`
  - `Index(fields=["tenant", "supplier"], name="idx_qrma_ten_supp")`
  - `Index(fields=["tenant", "disposition_type"], name="idx_qrma_ten_disp")`
  - `Index(fields=["tenant", "return_reason"], name="idx_qrma_ten_reason")`

---

## 2. Forms Contract (`apps/quality/forms/IncomingQuality/`)

All ModelForms inherit `apps.quality.forms._common.TenantModelForm`.
- Exclude from form `Meta.fields`: `tenant`, `number`, `created_at`, `updated_at`, derived/computed statistics (`spc_mean`, `spc_std_dev`, `spc_cp`, `spc_cpk`, `spc_out_of_control`, `variance_count`, `is_within_spec`), and workflow closure timestamps (`decided_at`, `verified_at`).
- All foreign keys filtered in `__init__` by `tenant=self.tenant`.
- Forms validate non-negative quantities, date order (`receipt_date <= inspection_date`, `shipped_date <= vendor_receipt_date`), and cross-tenant isolation in `clean()`.

---

## 3. Views & URLs Contract (`apps/quality/views/IncomingQuality/` & `urls/IncomingQuality/`)

### 3.1 Views List & Context Keys
1. **`IncomingInspectionPlan`**:
   - `incoming_inspection_plan_list`:
     - URL: `iqc/plans/` -> `quality:incoming_inspection_plan_list`
     - Context: `{"plans": page_obj.object_list, "page_obj": page_obj, "paginator": paginator, "is_paginated": is_paginated, "total_count": total, "status_choices": IncomingInspectionPlan.STATUS_CHOICES, "frequency_choices": IncomingInspectionPlan.INSPECTION_FREQUENCY_CHOICES, "suppliers": suppliers_qs}`
   - `incoming_inspection_plan_detail`:
     - URL: `iqc/plans/<int:pk>/` -> `quality:incoming_inspection_plan_detail`
     - Context: `{"plan": obj, "obj": obj, "status_css": IncomingInspectionPlan.STATUS_CSS, "freq_css": IncomingInspectionPlan.FREQUENCY_CSS}`
   - `incoming_inspection_plan_create`:
     - URL: `iqc/plans/create/` -> `quality:incoming_inspection_plan_create`
     - Context: `{"form": form, "title": "Create Incoming Inspection Plan"}`
   - `incoming_inspection_plan_edit`:
     - URL: `iqc/plans/<int:pk>/edit/` -> `quality:incoming_inspection_plan_edit`
     - Context: `{"form": form, "plan": obj, "obj": obj, "title": f"Edit {obj.number}"}`
   - `incoming_inspection_plan_delete`:
     - URL: `iqc/plans/<int:pk>/delete/` -> `quality:incoming_inspection_plan_delete` (POST-only + confirm)
   - `incoming_inspection_plan_export`:
     - URL: `iqc/plans/export/` -> `quality:incoming_inspection_plan_export` (CSV)

2. **`IncomingInspectionLot`**:
   - `incoming_inspection_lot_list`:
     - URL: `iqc/lots/` -> `quality:incoming_inspection_lot_list`
     - Context: `{"lots": page_obj.object_list, "page_obj": page_obj, "paginator": paginator, "is_paginated": is_paginated, "total_count": total, "stage_choices": IncomingInspectionLot.STAGE_CHOICES, "usage_decision_choices": IncomingInspectionLot.USAGE_DECISION_CHOICES, "suppliers": suppliers_qs}`
   - `incoming_inspection_lot_detail`:
     - URL: `iqc/lots/<int:pk>/` -> `quality:incoming_inspection_lot_detail`
     - Context: `{"lot": obj, "obj": obj, "stage_css": IncomingInspectionLot.STAGE_CSS, "decision_css": IncomingInspectionLot.USAGE_DECISION_CSS}`
   - `incoming_inspection_lot_create`:
     - URL: `iqc/lots/create/` -> `quality:incoming_inspection_lot_create`
     - Context: `{"form": form, "title": "Record Incoming Inspection Lot"}`
   - `incoming_inspection_lot_edit`:
     - URL: `iqc/lots/<int:pk>/edit/` -> `quality:incoming_inspection_lot_edit`
     - Context: `{"form": form, "lot": obj, "obj": obj, "title": f"Edit {obj.number}"}`
   - `incoming_inspection_lot_delete`:
     - URL: `iqc/lots/<int:pk>/delete/` -> `quality:incoming_inspection_lot_delete` (POST-only + confirm)
   - `incoming_inspection_lot_record_sample`:
     - URL: `iqc/lots/<int:pk>/sample/` -> `quality:incoming_inspection_lot_record_sample` (POST sample measurements & compute SPC)
   - `incoming_inspection_lot_make_decision`:
     - URL: `iqc/lots/<int:pk>/decision/` -> `quality:incoming_inspection_lot_make_decision` (POST formal usage decision)
   - `incoming_inspection_lot_export`:
     - URL: `iqc/lots/export/` -> `quality:incoming_inspection_lot_export` (CSV)

3. **`CertificateOfAnalysis`**:
   - `certificate_of_analysis_list`:
     - URL: `iqc/coas/` -> `quality:certificate_of_analysis_list`
     - Context: `{"coas": page_obj.object_list, "page_obj": page_obj, "paginator": paginator, "is_paginated": is_paginated, "total_count": total, "status_choices": CertificateOfAnalysis.STATUS_CHOICES, "suppliers": suppliers_qs}`
   - `certificate_of_analysis_detail`:
     - URL: `iqc/coas/<int:pk>/` -> `quality:certificate_of_analysis_detail`
     - Context: `{"coa": obj, "obj": obj, "status_css": CertificateOfAnalysis.STATUS_CSS}`
   - `certificate_of_analysis_create`:
     - URL: `iqc/coas/create/` -> `quality:certificate_of_analysis_create`
     - Context: `{"form": form, "title": "Intake Certificate of Analysis"}`
   - `certificate_of_analysis_edit`:
     - URL: `iqc/coas/<int:pk>/edit/` -> `quality:certificate_of_analysis_edit`
     - Context: `{"form": form, "coa": obj, "obj": obj, "title": f"Edit {obj.number}"}`
   - `certificate_of_analysis_delete`:
     - URL: `iqc/coas/<int:pk>/delete/` -> `quality:certificate_of_analysis_delete` (POST-only + confirm)
   - `certificate_of_analysis_verify`:
     - URL: `iqc/coas/<int:pk>/verify/` -> `quality:certificate_of_analysis_verify` (POST run spec verification)
   - `certificate_of_analysis_export`:
     - URL: `iqc/coas/export/` -> `quality:certificate_of_analysis_export` (CSV)

4. **`QualityReturnAuthorization`**:
   - `quality_return_authorization_list`:
     - URL: `iqc/rmas/` -> `quality:quality_return_authorization_list`
     - Context: `{"rmas": page_obj.object_list, "page_obj": page_obj, "paginator": paginator, "is_paginated": is_paginated, "total_count": total, "status_choices": QualityReturnAuthorization.STATUS_CHOICES, "disposition_choices": QualityReturnAuthorization.DISPOSITION_TYPE_CHOICES, "suppliers": suppliers_qs}`
   - `quality_return_authorization_detail`:
     - URL: `iqc/rmas/<int:pk>/` -> `quality:quality_return_authorization_detail`
     - Context: `{"rma": obj, "obj": obj, "status_css": QualityReturnAuthorization.STATUS_CSS, "disp_css": QualityReturnAuthorization.DISPOSITION_CSS}`
   - `quality_return_authorization_create`:
     - URL: `iqc/rmas/create/` -> `quality:quality_return_authorization_create`
     - Context: `{"form": form, "title": "Initiate Quality Return Authorization"}`
   - `quality_return_authorization_edit`:
     - URL: `iqc/rmas/<int:pk>/edit/` -> `quality:quality_return_authorization_edit`
     - Context: `{"form": form, "rma": obj, "obj": obj, "title": f"Edit {obj.number}"}`
   - `quality_return_authorization_delete`:
     - URL: `iqc/rmas/<int:pk>/delete/` -> `quality:quality_return_authorization_delete` (POST-only + confirm)
   - `quality_return_authorization_advance`:
     - URL: `iqc/rmas/<int:pk>/advance/` -> `quality:quality_return_authorization_advance` (POST advance RMA workflow state)
   - `quality_return_authorization_export`:
     - URL: `iqc/rmas/export/` -> `quality:quality_return_authorization_export` (CSV)

5. **`IqcSpcDashboard`**:
   - `iqc_spc_dashboard`:
     - URL: `iqc/spc-dashboard/` -> `quality:iqc_spc_dashboard`
     - Context: `{"lots_inspected_count": count, "acceptance_rate": rate, "avg_cpk": cpk, "out_of_control_count": ooc, "recent_alerts": alerts_qs, "supplier_leaderboard": leaderboard_data, "defect_pareto": pareto_data}`

---

## 4. Navigation Contract (`LIVE_LINKS["12.7"]` in `apps/core/navigation.py`)

```python
"12.7": {
    "Inspection Planning & Sampling": "quality:incoming_inspection_plan_list",
    "Goods Receipt & Inspection Execution": "quality:incoming_inspection_lot_list",
    "Certificate of Analysis (CoA) Management": "quality:certificate_of_analysis_list",
    "Inspection Data Capture & SPC": "quality:iqc_spc_dashboard",
    "Reject & Return Material Authorization (RMA)": "quality:quality_return_authorization_list",
}
```
