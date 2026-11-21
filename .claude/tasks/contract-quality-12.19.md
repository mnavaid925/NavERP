# Module 12.19 Pre-Build Contract — Laboratory Information Management (LIMS) (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.19"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0039_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/LimsManagement/`
  - `apps/quality/forms/LimsManagement/`
  - `apps/quality/views/LimsManagement/`
  - `apps/quality/urls/LimsManagement/`
  - `templates/quality/lims_management/{lab_sample,lab_specification,lab_test_worksheet,oos_investigation}/{list,detail,form}.html` + `templates/quality/lims_management/lims_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"receive"`, `"complete"`, `"approve"`, `"reject"`, `"close"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `scm.WorkOrder`, `quality.ControlledDocument`, `quality.CalibrationGage`, `quality.BatchRecord`, `quality.CapaInvestigation`, `quality.NonConformanceReport`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/LimsManagement/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `LabSample` (`LabSamples.py`)
- **`NUMBER_PREFIX`**: `"QSMP"`
- **`Meta.ordering`**: `["-created_at", "sample_name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Lab Sample"` / `"Lab Samples"`
- **Choices & Badge Maps**:
  - `SAMPLE_TYPE_CHOICES` (`max_length=35`):
    - `("raw_material", "Raw Material")`
    - `("in_process", "In-Process Intermediate")`
    - `("finished_product", "Finished Product")`
    - `("stability", "Stability Study Sample")`
    - `("environmental", "Environmental Monitoring")`
    - `("water_purified", "Purified Water / Utility")`
    - `("retained_sample", "Retained Archive Sample")`
    - `("blind_qc", "Blind QC / Proficiency")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("registered", "Registered / Logged")`
    - `("received", "Received in Lab")`
    - `("in_testing", "Testing in Progress")`
    - `("testing_completed", "Testing Completed")`
    - `("approved", "Approved / Conforms")`
    - `("rejected", "Rejected / OOS")`
    - `("disposed", "Sample Disposed")`
    - `("retained", "Retained in Vault")`
  - `STORAGE_CONDITION_CHOICES` (`max_length=30`):
    - `("ambient", "Ambient (15-25°C)")`
    - `("refrigerated_2_8c", "Refrigerated (2-8°C)")`
    - `("frozen_minus_20c", "Frozen (-20°C)")`
    - `("ultra_low_minus_80c", "Ultra-Low (-80°C)")`
    - `("desiccated", "Desiccated / Dry")`
    - `("light_protected", "Light-Protected / Amber")`
  - `STATUS_CSS`:
    - `"registered": "badge-slate"`
    - `"received": "badge-info"`
    - `"in_testing": "badge-amber"`
    - `"testing_completed": "badge-info"`
    - `"approved": "badge-green"`
    - `"rejected": "badge-red"`
    - `"disposed": "badge-muted"`
    - `"retained": "badge-slate"`
  - `SAMPLE_TYPE_CSS`:
    - `"raw_material": "badge-info"`
    - `"in_process": "badge-amber"`
    - `"finished_product": "badge-green"`
    - `"stability": "badge-slate"`
    - `"environmental": "badge-info"`
    - `"water_purified": "badge-info"`
    - `"retained_sample": "badge-slate"`
    - `"blind_qc": "badge-amber"`
- **Fields (exact names & types)**:
  - `sample_name`: `CharField(max_length=255)`
  - `sample_type`: `CharField(max_length=35, choices=SAMPLE_TYPE_CHOICES, default="raw_material", db_index=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="registered", db_index=True)`
  - `matrix_description`: `CharField(max_length=255, blank=True)`
  - `source_batch_number`: `CharField(max_length=100, blank=True, db_index=True)`
  - `item_code`: `CharField(max_length=100, blank=True, db_index=True)`
  - `item_name`: `CharField(max_length=255, blank=True)`
  - `sampling_point`: `CharField(max_length=150, blank=True)`
  - `sampled_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="collected_lab_samples")`
  - `sampled_at`: `DateTimeField(null=True, blank=True)`
  - `received_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_lab_samples")`
  - `received_at`: `DateTimeField(null=True, blank=True)`
  - `current_custodian`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="custody_lab_samples")`
  - `storage_location`: `CharField(max_length=150, blank=True, help_text="e.g. Cold Room 02, Freezer -80C Rack 4, Shelf B")`
  - `storage_condition`: `CharField(max_length=30, choices=STORAGE_CONDITION_CHOICES, default="ambient")`
  - `quantity_collected`: `DecimalField(max_digits=12, decimal_places=4, default=Decimal("1.0000"))`
  - `unit_of_measure`: `CharField(max_length=25, default="g")`
  - `retest_date`: `DateField(null=True, blank=True)`
  - `expiry_date`: `DateField(null=True, blank=True)`
  - `barcode_identifier`: `CharField(max_length=120, blank=True, db_index=True)`
  - `chain_of_custody_log`: `TextField(blank=True, help_text="Timestamped audit entries of custodian handoffs")`
  - `work_order`: `ForeignKey("scm.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="lab_samples")`
  - `batch_record`: `ForeignKey("quality.BatchRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="lab_samples")`
  - `facility`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="lab_samples")`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `@property is_received`: `status in ["received", "in_testing", "testing_completed", "approved", "rejected"]`
  - `@property can_test`: `status in ["received", "in_testing"]`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qsmp_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "sample_type"], name="idx_qsmp_ten_type")` (17)
  - `Index(fields=["tenant", "status"], name="idx_qsmp_ten_status")` (19)
  - `Index(fields=["tenant", "item_code"], name="idx_qsmp_ten_item")` (17)
  - `Index(fields=["tenant", "source_batch_number"], name="idx_qsmp_ten_batch")` (18)
  - `Index(fields=["tenant", "-created_at"], name="idx_qsmp_ten_created")` (20)

---

### 1.2 `LabSpecification` (`LabSpecifications.py`)
- **`NUMBER_PREFIX`**: `"QSPC"`
- **`Meta.ordering`**: `["product_code", "-version", "title"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Lab Specification"` / `"Lab Specifications"`
- **Choices & Badge Maps**:
  - `SPEC_TYPE_CHOICES` (`max_length=30`):
    - `("raw_material", "Raw Material Release")`
    - `("in_process", "In-Process Control (IPC)")`
    - `("finished_product", "Finished Product Release")`
    - `("stability", "Stability Specification")`
    - `("cleaning_verification", "Cleaning Verification / Swab")`
    - `("environmental", "Environmental Monitoring Limit")`
  - `TEST_CATEGORY_CHOICES` (`max_length=30`):
    - `("chemical", "Chemical / Wet Chemistry")`
    - `("physical", "Physical Testing / Appearance")`
    - `("microbiological", "Microbiological Bioburden / Sterility")`
    - `("chromatographic", "Chromatography (HPLC / GC / UPLC)")`
    - `("spectroscopic", "Spectroscopy (UV-Vis / FT-IR / NIR)")`
    - `("biological_assay", "Biological / Immuno-Assay")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft")`
    - `("under_review", "Under Review")`
    - `("approved", "Approved / Active")`
    - `("superseded", "Superseded")`
    - `("retired", "Retired")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"under_review": "badge-amber"`
    - `"approved": "badge-green"`
    - `"superseded": "badge-muted"`
    - `"retired": "badge-muted"`
  - `TEST_CATEGORY_CSS`:
    - `"chemical": "badge-info"`
    - `"physical": "badge-slate"`
    - `"microbiological": "badge-red"`
    - `"chromatographic": "badge-purple"`
    - `"spectroscopic": "badge-info"`
    - `"biological_assay": "badge-amber"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `specification_type`: `CharField(max_length=30, choices=SPEC_TYPE_CHOICES, default="finished_product", db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `version`: `CharField(max_length=20, default="1.0")`
  - `product_code`: `CharField(max_length=100, db_index=True)`
  - `product_name`: `CharField(max_length=255)`
  - `analytical_method_number`: `CharField(max_length=100, blank=True, help_text="e.g. AM-QC-304 / USP <621>")`
  - `test_category`: `CharField(max_length=30, choices=TEST_CATEGORY_CHOICES, default="chemical")`
  - `sop_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="lab_specifications")`
  - `target_parameter_name`: `CharField(max_length=150, help_text="Primary parameter tested, e.g. Assay Purity, Dissolution, pH, Endotoxin")`
  - `parameter_unit`: `CharField(max_length=25, blank=True, help_text="e.g., %, pH, EU/mL, ppm, mg/mL")`
  - `lower_limit`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `upper_limit`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `target_value`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `text_acceptance_criteria`: `TextField(blank=True, help_text="Qualitative visual or spectroscopic criteria")`
  - `method_validation_reference`: `CharField(max_length=150, blank=True)`
  - `method_validation_date`: `DateField(null=True, blank=True)`
  - `effective_date`: `DateField(null=True, blank=True)`
  - `review_due_date`: `DateField(null=True, blank=True)`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_lab_specifications")`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `@property is_active`: `status == "approved"`
  - `@property is_overdue_review`: `review_due_date is not None and review_due_date < date.today()`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qspc_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "product_code"], name="idx_qspc_ten_prod")` (17)
  - `Index(fields=["tenant", "specification_type"], name="idx_qspc_ten_type")` (17)
  - `Index(fields=["tenant", "status"], name="idx_qspc_ten_status")` (19)
  - `Index(fields=["tenant", "test_category"], name="idx_qspc_ten_cat")` (16)

---

### 1.3 `LabTestWorksheet` (`LabTestWorksheets.py`)
- **`NUMBER_PREFIX`**: `"QWKS"`
- **`Meta.ordering`**: `["-scheduled_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Lab Test Worksheet"` / `"Lab Test Worksheets"`
- **Choices & Badge Maps**:
  - `STATUS_CHOICES` (`max_length=25`):
    - `("assigned", "Assigned / Pending")`
    - `("in_progress", "Execution in Progress")`
    - `("review_pending", "Pending QA Review")`
    - `("approved", "Approved / Closed")`
    - `("rejected", "Rejected")`
    - `("cancelled", "Cancelled")`
  - `DISPOSITION_CHOICES` (`max_length=25`):
    - `("pending", "Pending Results")`
    - `("conforms", "Conforms to Specification")`
    - `("oos_flagged", "Out of Specification (OOS)")`
    - `("inconclusive", "Inconclusive Run")`
    - `("invalid_run", "Invalid Run (Lab Error)")`
  - `STATUS_CSS`:
    - `"assigned": "badge-slate"`
    - `"in_progress": "badge-amber"`
    - `"review_pending": "badge-info"`
    - `"approved": "badge-green"`
    - `"rejected": "badge-red"`
    - `"cancelled": "badge-muted"`
  - `DISPOSITION_CSS`:
    - `"pending": "badge-slate"`
    - `"conforms": "badge-green"`
    - `"oos_flagged": "badge-red"`
    - `"inconclusive": "badge-amber"`
    - `"invalid_run": "badge-amber"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `sample`: `ForeignKey("quality.LabSample", on_delete=models.CASCADE, related_name="test_worksheets")`
  - `specification`: `ForeignKey("quality.LabSpecification", on_delete=models.PROTECT, related_name="test_worksheets")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="assigned", db_index=True)`
  - `disposition`: `CharField(max_length=25, choices=DISPOSITION_CHOICES, default="pending", db_index=True)`
  - `assigned_analyst`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_worksheets")`
  - `reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_worksheets")`
  - `scheduled_date`: `DateField(null=True, blank=True)`
  - `execution_date`: `DateField(null=True, blank=True)`
  - `completion_timestamp`: `DateTimeField(null=True, blank=True)`
  - `instrument`: `ForeignKey("quality.CalibrationGage", on_delete=models.SET_NULL, null=True, blank=True, related_name="test_worksheets")`
  - `instrument_name`: `CharField(max_length=150, blank=True, help_text="e.g. HPLC-03, UV-Vis-01")`
  - `reagent_lot_number`: `CharField(max_length=100, blank=True)`
  - `reagent_expiry_date`: `DateField(null=True, blank=True)`
  - `standards_lot_number`: `CharField(max_length=100, blank=True)`
  - `standards_expiry_date`: `DateField(null=True, blank=True)`
  - `raw_data_summary`: `TextField(blank=True, help_text="Instrument readings, replicates, peak areas")`
  - `numeric_result`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `qualitative_result`: `CharField(max_length=255, blank=True)`
  - `is_within_specification`: `BooleanField(default=True)`
  - `relative_standard_deviation`: `DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="% RSD of analytical replicates")`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `@property is_overdue`: `scheduled_date is not None and scheduled_date < date.today() and status in ["assigned", "in_progress"]`
  - `@property reagent_expired`: `reagent_expiry_date is not None and reagent_expiry_date < date.today()`
  - `@property standards_expired`: `standards_expiry_date is not None and standards_expiry_date < date.today()`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qwks_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "sample"], name="idx_qwks_ten_sample")` (19)
  - `Index(fields=["tenant", "specification"], name="idx_qwks_ten_spec")` (17)
  - `Index(fields=["tenant", "status"], name="idx_qwks_ten_status")` (19)
  - `Index(fields=["tenant", "disposition"], name="idx_qwks_ten_disp")` (17)
  - `Index(fields=["tenant", "-scheduled_date"], name="idx_qwks_ten_date")` (17)

---

### 1.4 `OosInvestigation` (`OosInvestigations.py`)
- **`NUMBER_PREFIX`**: `"QOOS"`
- **`Meta.ordering`**: `["-created_at", "title"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"OOS Investigation"` / `"OOS Investigations"`
- **Choices & Badge Maps**:
  - `PHASE_CHOICES` (`max_length=30`):
    - `("phase_1_lab", "Phase I: Laboratory Investigation")`
    - `("phase_2_manufacturing", "Phase II: Manufacturing Investigation")`
    - `("awaiting_capa", "Awaiting CAPA / Disposition")`
    - `("closed", "Investigation Closed")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("open", "Open / In Progress")`
    - `("retest_authorized", "Retest Authorized")`
    - `("root_cause_found", "Root Cause Identified")`
    - `("closed", "Closed")`
  - `SEVERITY_CHOICES` (`max_length=20`):
    - `("critical", "Critical (Patient Safety / Product Impact)")`
    - `("major", "Major (Regulatory / CQA Breach)")`
    - `("minor", "Minor (Inconsequential)")`
  - `DISPOSITION_CHOICES` (`max_length=30`):
    - `("pending", "Pending Disposition")`
    - `("batch_released", "Batch Released")`
    - `("batch_rejected", "Batch Rejected")`
    - `("batch_reprocessed", "Batch Reprocessed")`
    - `("quarantined", "Quarantined / Hold")`
  - `PHASE_CSS`:
    - `"phase_1_lab": "badge-amber"`
    - `"phase_2_manufacturing": "badge-red"`
    - `"awaiting_capa": "badge-info"`
    - `"closed": "badge-green"`
  - `STATUS_CSS`:
    - `"open": "badge-amber"`
    - `"retest_authorized": "badge-info"`
    - `"root_cause_found": "badge-purple"`
    - `"closed": "badge-green"`
  - `SEVERITY_CSS`:
    - `"critical": "badge-red"`
    - `"major": "badge-amber"`
    - `"minor": "badge-slate"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `test_worksheet`: `ForeignKey("quality.LabTestWorksheet", on_delete=models.CASCADE, related_name="oos_investigations")`
  - `sample`: `ForeignKey("quality.LabSample", on_delete=models.CASCADE, related_name="oos_investigations")`
  - `investigation_phase`: `CharField(max_length=30, choices=PHASE_CHOICES, default="phase_1_lab", db_index=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="open", db_index=True)`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default="critical", db_index=True)`
  - `analyst_interview_completed`: `BooleanField(default=False)`
  - `calculation_verification_completed`: `BooleanField(default=False)`
  - `instrument_verification_completed`: `BooleanField(default=False)`
  - `reagent_verification_completed`: `BooleanField(default=False)`
  - `lab_error_identified`: `BooleanField(default=False)`
  - `lab_error_description`: `TextField(blank=True, help_text="Details of documented lab error")`
  - `manufacturing_investigation_required`: `BooleanField(default=False)`
  - `process_equipment_checked`: `BooleanField(default=False)`
  - `raw_material_lots_checked`: `BooleanField(default=False)`
  - `environmental_conditions_checked`: `BooleanField(default=False)`
  - `assignable_cause`: `TextField(blank=True, help_text="Identified assignable root cause for OOS finding")`
  - `hypothesis_testing_summary`: `TextField(blank=True, help_text="Hypothesis test protocol and outcome")`
  - `retest_plan_authorized`: `BooleanField(default=False)`
  - `retest_results_summary`: `TextField(blank=True)`
  - `final_batch_disposition`: `CharField(max_length=30, choices=DISPOSITION_CHOICES, default="pending", db_index=True)`
  - `investigation_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="led_oos_investigations")`
  - `qa_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_oos_investigations")`
  - `target_completion_date`: `DateField(null=True, blank=True)`
  - `closed_at`: `DateTimeField(null=True, blank=True)`
  - `capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="oos_investigations")`
  - `non_conformance`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="oos_investigations")`
  - `summary_and_conclusions`: `TextField(blank=True)`
- **Properties**:
  - `@property phase_1_completed`: `analyst_interview_completed and calculation_verification_completed and instrument_verification_completed and reagent_verification_completed`
  - `@property is_overdue`: `target_completion_date is not None and target_completion_date < date.today() and status != "closed"`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qoos_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "investigation_phase"], name="idx_qoos_ten_phase")` (18)
  - `Index(fields=["tenant", "status"], name="idx_qoos_ten_status")` (19)
  - `Index(fields=["tenant", "severity"], name="idx_qoos_ten_sev")` (16)
  - `Index(fields=["tenant", "final_batch_disposition"], name="idx_qoos_ten_disp")` (17)
  - `Index(fields=["tenant", "-created_at"], name="idx_qoos_ten_created")` (20)

---

## 2. Forms Contract (`apps/quality/forms/LimsManagement/`)

All ModelForms inherit `django.forms.ModelForm`. Form `__init__` sets `self.tenant` and populates all tenant FK querysets (`Model.objects.filter(tenant=self.tenant)`). Clean methods reject foreign tenant objects via `reject_foreign(...)`.

### 2.1 `LabSampleForm` (`LabSamples.py`)
- **`Meta.model`**: `LabSample`
- **`Meta.fields`**: All model fields except exclusions.
- **`Meta.exclude`**: `["tenant", "number", "received_at", "created_at", "updated_at"]`

### 2.2 `LabSpecificationForm` (`LabSpecifications.py`)
- **`Meta.model`**: `LabSpecification`
- **`Meta.fields`**: All model fields except exclusions.
- **`Meta.exclude`**: `["tenant", "number", "created_at", "updated_at"]`

### 2.3 `LabTestWorksheetForm` (`LabTestWorksheets.py`)
- **`Meta.model`**: `LabTestWorksheet`
- **`Meta.fields`**: All model fields except exclusions.
- **`Meta.exclude`**: `["tenant", "number", "completion_timestamp", "created_at", "updated_at"]`

### 2.4 `OosInvestigationForm` (`OosInvestigations.py`)
- **`Meta.model`**: `OosInvestigation`
- **`Meta.fields`**: All model fields except exclusions.
- **`Meta.exclude`**: `["tenant", "number", "closed_at", "created_at", "updated_at"]`

---

## 3. URLs Contract (`apps/quality/urls/LimsManagement/` & `apps/quality/urls/__init__.py`)

All URL patterns live in `apps/quality/urls/LimsManagement/<Entity>.py`. Literal patterns are strictly registered before `<int:pk>` patterns.

| Pattern | View Name | Route Name | Notes |
|---------|-----------|------------|-------|
| `lims/` | `lims_dashboard` | `lims_dashboard` | Command center & laboratory KPIs |
| `lims/export/` | `lims_export_csv` | `lims_export_csv` | CSV telemetry export |
| `lims/samples/` | `lab_sample_list` | `lab_sample_list` | List + Search + Filter |
| `lims/samples/create/` | `lab_sample_create` | `lab_sample_create` | Create sample |
| `lims/samples/<int:pk>/` | `lab_sample_detail` | `lab_sample_detail` | Detail sample |
| `lims/samples/<int:pk>/edit/` | `lab_sample_edit` | `lab_sample_edit` | Edit sample |
| `lims/samples/<int:pk>/delete/` | `lab_sample_delete` | `lab_sample_delete` | POST delete |
| `lims/samples/<int:pk>/receive/` | `lab_sample_receive` | `lab_sample_receive` | POST receive sample in lab |
| `lims/specifications/` | `lab_specification_list` | `lab_specification_list` | List + Search + Filter |
| `lims/specifications/create/` | `lab_specification_create` | `lab_specification_create` | Create specification |
| `lims/specifications/<int:pk>/` | `lab_specification_detail` | `lab_specification_detail` | Detail specification |
| `lims/specifications/<int:pk>/edit/` | `lab_specification_edit` | `lab_specification_edit` | Edit specification |
| `lims/specifications/<int:pk>/delete/` | `lab_specification_delete` | `lab_specification_delete` | POST delete |
| `lims/worksheets/` | `lab_test_worksheet_list` | `lab_test_worksheet_list` | List + Search + Filter |
| `lims/worksheets/create/` | `lab_test_worksheet_create` | `lab_test_worksheet_create` | Create worksheet |
| `lims/worksheets/<int:pk>/` | `lab_test_worksheet_detail` | `lab_test_worksheet_detail` | Detail worksheet |
| `lims/worksheets/<int:pk>/edit/` | `lab_test_worksheet_edit` | `lab_test_worksheet_edit` | Edit worksheet |
| `lims/worksheets/<int:pk>/delete/` | `lab_test_worksheet_delete` | `lab_test_worksheet_delete` | POST delete |
| `lims/worksheets/<int:pk>/complete/` | `lab_test_worksheet_complete` | `lab_test_worksheet_complete` | POST complete worksheet |
| `lims/oos/` | `oos_investigation_list` | `oos_investigation_list` | List + Search + Filter |
| `lims/oos/create/` | `oos_investigation_create` | `oos_investigation_create` | Create OOS |
| `lims/oos/<int:pk>/` | `oos_investigation_detail` | `oos_investigation_detail` | Detail OOS |
| `lims/oos/<int:pk>/edit/` | `oos_investigation_edit` | `oos_investigation_edit` | Edit OOS |
| `lims/oos/<int:pk>/delete/` | `oos_investigation_delete` | `oos_investigation_delete` | POST delete |
| `lims/oos/<int:pk>/close/` | `oos_investigation_close` | `oos_investigation_close` | POST close investigation |

---

## 4. Views & Context Contract (`apps/quality/views/LimsManagement/`)

Every view context key is pinned below. Missing context keys or typos cause blank renders or `NoReverseMatch`.

### 4.1 `lab_sample_list`
- **Context**:
  - `page_obj`: paginated `LabSample` queryset
  - `samples`: `page_obj.object_list`
  - `sample_type_choices`: `LabSample.SAMPLE_TYPE_CHOICES`
  - `status_choices`: `LabSample.STATUS_CHOICES`
  - `storage_condition_choices`: `LabSample.STORAGE_CONDITION_CHOICES`
  - `selected_type`: `request.GET.get('sample_type', '')`
  - `selected_status`: `request.GET.get('status', '')`
  - `selected_storage`: `request.GET.get('storage_condition', '')`
  - `query`: `request.GET.get('q', '')`

### 4.2 `lab_sample_detail`
- **Context**:
  - `sample`: `LabSample` instance
  - `test_worksheets`: `sample.test_worksheets.all()`
  - `oos_investigations`: `sample.oos_investigations.all()`

### 4.3 `lab_sample_form` (shared create/edit)
- **Context**:
  - `form`: `LabSampleForm`
  - `sample`: instance or `None`
  - `is_edit`: boolean

### 4.4 `lab_specification_list`
- **Context**:
  - `page_obj`: paginated `LabSpecification` queryset
  - `specifications`: `page_obj.object_list`
  - `spec_type_choices`: `LabSpecification.SPEC_TYPE_CHOICES`
  - `test_category_choices`: `LabSpecification.TEST_CATEGORY_CHOICES`
  - `status_choices`: `LabSpecification.STATUS_CHOICES`
  - `selected_type`: `request.GET.get('specification_type', '')`
  - `selected_category`: `request.GET.get('test_category', '')`
  - `selected_status`: `request.GET.get('status', '')`
  - `query`: `request.GET.get('q', '')`

### 4.5 `lab_specification_detail`
- **Context**:
  - `specification`: `LabSpecification` instance
  - `worksheets`: `specification.test_worksheets.all()[:15]`

### 4.6 `lab_specification_form` (shared create/edit)
- **Context**:
  - `form`: `LabSpecificationForm`
  - `specification`: instance or `None`
  - `is_edit`: boolean

### 4.7 `lab_test_worksheet_list`
- **Context**:
  - `page_obj`: paginated `LabTestWorksheet` queryset
  - `worksheets`: `page_obj.object_list`
  - `status_choices`: `LabTestWorksheet.STATUS_CHOICES`
  - `disposition_choices`: `LabTestWorksheet.DISPOSITION_CHOICES`
  - `selected_status`: `request.GET.get('status', '')`
  - `selected_disposition`: `request.GET.get('disposition', '')`
  - `query`: `request.GET.get('q', '')`

### 4.8 `lab_test_worksheet_detail`
- **Context**:
  - `worksheet`: `LabTestWorksheet` instance
  - `oos_investigations`: `worksheet.oos_investigations.all()`

### 4.9 `lab_test_worksheet_form` (shared create/edit)
- **Context**:
  - `form`: `LabTestWorksheetForm`
  - `worksheet`: instance or `None`
  - `is_edit`: boolean

### 4.10 `oos_investigation_list`
- **Context**:
  - `page_obj`: paginated `OosInvestigation` queryset
  - `investigations`: `page_obj.object_list`
  - `phase_choices`: `OosInvestigation.PHASE_CHOICES`
  - `status_choices`: `OosInvestigation.STATUS_CHOICES`
  - `severity_choices`: `OosInvestigation.SEVERITY_CHOICES`
  - `selected_phase`: `request.GET.get('investigation_phase', '')`
  - `selected_status`: `request.GET.get('status', '')`
  - `selected_severity`: `request.GET.get('severity', '')`
  - `query`: `request.GET.get('q', '')`

### 4.11 `oos_investigation_detail`
- **Context**:
  - `investigation`: `OosInvestigation` instance

### 4.12 `oos_investigation_form` (shared create/edit)
- **Context**:
  - `form`: `OosInvestigationForm`
  - `investigation`: instance or `None`
  - `is_edit`: boolean

### 4.13 `lims_dashboard`
- **Context**:
  - `total_samples`: count of active samples
  - `samples_in_testing`: count in testing
  - `pending_worksheets`: count of worksheets assigned/in_progress
  - `open_oos_count`: count of open OOS investigations
  - `expiring_reagents_count`: count of worksheets with reagents expiring in 30 days
  - `recent_samples`: latest 5 `LabSample` records
  - `recent_worksheets`: latest 5 `LabTestWorksheet` records
  - `recent_oos`: latest 5 `OosInvestigation` records

---

## 5. Navigation Wiring Contract (`apps/core/navigation.py`)

`LIVE_LINKS["12.19"]` must match the bold feature bullets of `NavERP.md` (`### 12.19 Laboratory Information Management (LIMS)`):

```python
    "12.19": {
        "Sample Management & Chain of Custody": "quality:lab_sample_list",
        "Test Method & Specification Management": "quality:lab_specification_list",
        "Test Execution & Result Capture": "quality:lab_test_worksheet_list",
        "Out-of-Specification (OOS) Investigation": "quality:oos_investigation_list",
        "Laboratory Equipment & Reagent Management": "quality:lims_dashboard",
    },
```
