# Module 12.10 Pre-Build Contract — Calibration & Measurement System Analysis (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.10"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0016_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/CalibrationAnalysis/`
  - `apps/quality/forms/CalibrationAnalysis/`
  - `apps/quality/views/CalibrationAnalysis/`
  - `apps/quality/urls/CalibrationAnalysis/`
  - `templates/quality/calibrationanalysis/{calibration_gage,calibration_record,out_of_tolerance_investigation,measurement_system_analysis}/{list,detail,form}.html` + `templates/quality/calibrationanalysis/calibration_vendor_directory.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"calibrate"`, `"quarantine"`, `"release"`, `"approve"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `core.Party`, `scm.Asset`, `scm.WorkCenter`, `quality.ControlledDocument`, `quality.NonConformanceReport`, `quality.CapaInvestigation`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/CalibrationAnalysis/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `CalibrationGage` (`CalibrationGages.py`)
- **`NUMBER_PREFIX`**: `"QGAG"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Calibration Gage / Instrument"` / `"Calibration Gages & Instruments"`
- **Choices & Badge Maps**:
  - `GAGE_TYPE_CHOICES` (`max_length=32`):
    - `("caliper_micrometer", "Caliper / Micrometer / Depth Gage")`
    - `("pressure_vacuum", "Pressure / Vacuum Gage / Transducer")`
    - `("temperature_humidity", "Temperature Sensor / RTD / Hygrometer")`
    - `("electrical_multimeter", "Multimeter / Oscilloscope / Power Meter")`
    - `("torque_force", "Torque Wrench / Load Cell / Force Gage")`
    - `("optical_comparator", "Optical Comparator / Vision System")`
    - `("cmm_coordinate", "CMM Coordinate Measuring Machine")`
    - `("gauge_block_pin", "Gage Blocks / Pin & Plug Gages")`
    - `("mass_balance", "Mass Standard / Precision Analytical Balance")`
    - `("flow_level", "Flow Meter / Level Transmitter")`
    - `("other_instrument", "Other Specialized Test Equipment")`
  - `CRITICALITY_CHOICES` (`max_length=20`):
    - `("critical", "Critical (Direct Product / CTQ)")`
    - `("major", "Major (Process Control)")`
    - `("minor", "Minor (Reference / General)")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("active_in_service", "Active / In-Service")`
    - `("in_calibration", "In Calibration")`
    - `("pending_calibration", "Pending Calibration")`
    - `("past_due", "Past Due / Overdue")`
    - `("quarantined_oot", "Quarantined (Out-of-Tolerance)")`
    - `("out_of_service", "Out of Service / Maintenance")`
    - `("retired", "Retired / Decommissioned")`
  - `GAGE_TYPE_CSS`:
    - `"caliper_micrometer": "badge-info"`
    - `"pressure_vacuum": "badge-slate"`
    - `"temperature_humidity": "badge-amber"`
    - `"electrical_multimeter": "badge-info"`
    - `"torque_force": "badge-slate"`
    - `"optical_comparator": "badge-slate"`
    - `"cmm_coordinate": "badge-info"`
    - `"gauge_block_pin": "badge-slate"`
    - `"mass_balance": "badge-info"`
    - `"flow_level": "badge-slate"`
    - `"other_instrument": "badge-muted"`
  - `CRITICALITY_CSS`:
    - `"critical": "badge-red"`
    - `"major": "badge-amber"`
    - `"minor": "badge-muted"`
  - `STATUS_CSS`:
    - `"active_in_service": "badge-green"`
    - `"in_calibration": "badge-info"`
    - `"pending_calibration": "badge-amber"`
    - `"past_due": "badge-red"`
    - `"quarantined_oot": "badge-red"`
    - `"out_of_service": "badge-muted"`
    - `"retired": "badge-slate"`

- **Fields**:
  - `gage_id`: `CharField(max_length=64, db_index=True, help_text="Plant tool tag / barcode ID")`
  - `name`: `CharField(max_length=150, help_text="Descriptive gage name e.g. 0-150mm Digital Caliper")`
  - `gage_type`: `CharField(max_length=32, choices=GAGE_TYPE_CHOICES, default="caliper_micrometer", db_index=True)`
  - `criticality`: `CharField(max_length=20, choices=CRITICALITY_CHOICES, default="major", db_index=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="active_in_service", db_index=True)`
  - `manufacturer`: `CharField(max_length=100, blank=True)`
  - `model_number`: `CharField(max_length=100, blank=True)`
  - `serial_number`: `CharField(max_length=100, blank=True, db_index=True)`
  - `measurement_range`: `CharField(max_length=100, blank=True, help_text="e.g. 0 to 150 mm / 0 to 100 psi")`
  - `resolution`: `CharField(max_length=64, blank=True, help_text="e.g. 0.01 mm / 0.0005 in")`
  - `accuracy_spec`: `CharField(max_length=120, blank=True, help_text="e.g. +/- 0.02 mm / Class 1")`
  - `max_permissible_error`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0200"), help_text="Maximum Permissible Error (MPE) in primary engineering units")`
  - `engineering_unit`: `CharField(max_length=32, default="mm", help_text="mm, inch, psi, bar, deg_c, v, a, nm")`
  - `is_reference_standard`: `BooleanField(default=False, help_text="Designated primary/secondary calibration standard used to calibrate other working gages")`
  - `nist_traceability_number`: `CharField(max_length=100, blank=True, help_text="NIST / National metrology institute test report reference")`
  - `reference_standard_parent`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="subordinate_gages")`
  - `asset_link`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="calibration_gages")`
  - `work_center`: `ForeignKey("scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_gages")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_gages")`
  - `custodian`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="custody_gages")`
  - `storage_location`: `CharField(max_length=120, blank=True, help_text="Crib room, drawer, cabinet, or bench coordinate")`
  - `calibration_interval_days`: `PositiveIntegerField(default=365, help_text="Scheduled interval between routine recalibrations in days")`
  - `last_calibration_date`: `DateField(null=True, blank=True)`
  - `next_calibration_due`: `DateField(null=True, blank=True, db_index=True)`
  - `last_calibration_result`: `CharField(max_length=32, blank=True, default="")`
  - `sop_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="calibrated_gages")`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qgag_ten_num_uniq")` (25 chars)
  - `UniqueConstraint(fields=["tenant", "gage_id"], name="quality_qgag_ten_gid_uniq")` (25 chars)
  - `Index(fields=["tenant", "status"], name="idx_qgag_ten_status")` (19 chars)
  - `Index(fields=["tenant", "gage_type"], name="idx_qgag_ten_type")` (17 chars)
  - `Index(fields=["tenant", "next_calibration_due"], name="idx_qgag_ten_due")` (16 chars)
  - `Index(fields=["tenant", "is_reference_standard"], name="idx_qgag_ten_std")` (16 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qgag_ten_created")` (20 chars)

---

### 1.2 `CalibrationRecord` (`CalibrationRecords.py`)
- **`NUMBER_PREFIX`**: `"QCAL"`
- **`Meta.ordering`**: `["-calibration_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Calibration Event / Record"` / `"Calibration Events & Records"`
- **Choices & Badge Maps**:
  - `CALIBRATION_TYPE_CHOICES` (`max_length=24`):
    - `("internal_metrology", "Internal Metrology Lab")`
    - `("external_accredited", "External ISO/IEC 17025 Lab")`
    - `("oem_factory", "OEM Factory Calibration")`
    - `("on_site_field", "On-Site Field Verification")`
  - `CONDITION_CHOICES` (`max_length=24`):
    - `("in_tolerance", "In-Tolerance (Conforming)")`
    - `("out_of_tolerance", "Out-of-Tolerance (Non-Conforming)")`
    - `("damaged_malfunctioning", "Damaged / Malfunctioning")`
    - `("not_operational", "Not Operational / Inoperable")`
    - `("new_first_calibration", "New / Initial Calibration")`
  - `OVERALL_RESULT_CHOICES` (`max_length=24`):
    - `("pass", "Pass (Fully Conforming)")`
    - `("pass_with_limitations", "Pass with Limited Range / De-rated")`
    - `("fail_out_of_tolerance", "Fail (Out-of-Tolerance)")`
    - `("fail_unrepairable", "Fail (Scrap / Unrepairable)")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft / Scheduled")`
    - `("in_progress", "In Progress")`
    - `("completed", "Completed / Reviewed")`
    - `("rejected", "Rejected / Invalid")`
  - `OVERALL_RESULT_CSS`:
    - `"pass": "badge-green"`
    - `"pass_with_limitations": "badge-amber"`
    - `"fail_out_of_tolerance": "badge-red"`
    - `"fail_unrepairable": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_progress": "badge-amber"`
    - `"completed": "badge-green"`
    - `"rejected": "badge-red"`
  - `CALIBRATION_TYPE_CSS`:
    - `"internal_metrology": "badge-info"`
    - `"external_accredited": "badge-purple"` (use `badge-slate` in theme.css)
    - `"oem_factory": "badge-slate"`
    - `"on_site_field": "badge-info"`

- **Fields**:
  - `gage`: `ForeignKey("quality.CalibrationGage", on_delete=models.CASCADE, related_name="calibration_records")`
  - `calibration_date`: `DateField(default=timezone.now, db_index=True)`
  - `calibration_type`: `CharField(max_length=24, choices=CALIBRATION_TYPE_CHOICES, default="internal_metrology", db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="completed", db_index=True)`
  - `service_vendor`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="calibrations_performed")`
  - `certificate_number`: `CharField(max_length=100, blank=True, db_index=True)`
  - `as_found_condition`: `CharField(max_length=24, choices=CONDITION_CHOICES, default="in_tolerance", db_index=True)`
  - `as_left_condition`: `CharField(max_length=24, choices=CONDITION_CHOICES, default="in_tolerance", db_index=True)`
  - `overall_result`: `CharField(max_length=24, choices=OVERALL_RESULT_CHOICES, default="pass", db_index=True)`
  - `ambient_temperature_c`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("20.00"), help_text="Lab temperature e.g. 20.0 +/- 1.0 deg C")`
  - `ambient_relative_humidity`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("45.00"), help_text="Lab relative humidity %")`
  - `expanded_uncertainty`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0020"), help_text="Expanded measurement uncertainty (U, k=2 95% confidence)")`
  - `test_uncertainty_ratio`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("4.00"), help_text="TUR ratio (e.g. 4.0:1)")`
  - `max_observed_error`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0050"), help_text="Maximum deviation observed across all test points")`
  - `guardband_applied`: `BooleanField(default=True, help_text="ILAC-G8 / ISO 14253-1 decision rule guardband applied to acceptance")`
  - `test_points_data`: `JSONField(default=list, blank=True, help_text="Array of calibration points: nominal, as_found, error, as_left, limit")`
  - `standards_used`: `ManyToManyField("quality.CalibrationGage", blank=True, related_name="calibrations_verified", limit_choices_to={"is_reference_standard": True})`
  - `standard_traceability_notes`: `TextField(blank=True, help_text="Summary of reference standards, certificates, and expiration dates")`
  - `technician_name`: `CharField(max_length=120, blank=True, help_text="Name of internal metrologist or vendor cal technician")`
  - `calibrated_by_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="executed_calibrations")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_calibrations")`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcal_ten_num_uniq")` (25 chars)
  - `Index(fields=["tenant", "gage"], name="idx_qcal_ten_gage")` (17 chars)
  - `Index(fields=["tenant", "overall_result"], name="idx_qcal_ten_result")` (19 chars)
  - `Index(fields=["tenant", "calibration_date"], name="idx_qcal_ten_date")` (17 chars)
  - `Index(fields=["tenant", "status"], name="idx_qcal_ten_status")` (19 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qcal_ten_created")` (20 chars)

---

### 1.3 `OutOfToleranceInvestigation` (`OutOfToleranceInvestigations.py`)
- **`NUMBER_PREFIX`**: `"QOOT"`
- **`Meta.ordering`**: `["-discovery_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Out-of-Tolerance (OOT) Investigation"` / `"Out-of-Tolerance (OOT) Investigations"`
- **Choices & Badge Maps**:
  - `RISK_LEVEL_CHOICES` (`max_length=20`):
    - `("critical", "Critical (Safety / Regulatory / Customer Risk)")`
    - `("major", "Major (Fit / Form / Function CTQ Impact)")`
    - `("minor", "Minor (Negligible Measurement Uncertainty)")`
    - `("no_impact", "No Impact Confirmed")`
  - `DISPOSITION_CHOICES` (`max_length=24`):
    - `("pending_review", "Pending MRB / Quality Review")`
    - `("use_as_is", "Use As-Is (Risk Accepted)")`
    - `("re_inspect_inventory", "100% Re-Inspect Suspect Lots")`
    - `("customer_notification", "Customer Notification & Concession")`
    - `("quarantine_scrap", "Quarantine & Scrap Finished Goods")`
    - `("product_recall", "Formal Field Safety / Recall Action")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("open", "Open / Newly Quarantined")`
    - `("investigating", "Reverse-Tracing Investigation")`
    - `("mrb_review", "Material Review Board (MRB)")`
    - `("actions_pending", "Containment Actions Pending")`
    - `("closed", "Closed / Verified Complete")`
  - `RISK_LEVEL_CSS`:
    - `"critical": "badge-red"`
    - `"major": "badge-amber"`
    - `"minor": "badge-info"`
    - `"no_impact": "badge-green"`
  - `STATUS_CSS`:
    - `"open": "badge-red"`
    - `"investigating": "badge-amber"`
    - `"mrb_review": "badge-info"`
    - `"actions_pending": "badge-amber"`
    - `"closed": "badge-green"`
  - `DISPOSITION_CSS`:
    - `"pending_review": "badge-slate"`
    - `"use_as_is": "badge-info"`
    - `"re_inspect_inventory": "badge-amber"`
    - `"customer_notification": "badge-red"`
    - `"quarantine_scrap": "badge-red"`
    - `"product_recall": "badge-red"`

- **Fields**:
  - `calibration_record`: `ForeignKey("quality.CalibrationRecord", on_delete=models.CASCADE, related_name="oot_investigations")`
  - `gage`: `ForeignKey("quality.CalibrationGage", on_delete=models.CASCADE, related_name="oot_investigations")`
  - `discovery_date`: `DateField(default=timezone.now, db_index=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="open", db_index=True)`
  - `risk_level`: `CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default="major", db_index=True)`
  - `title`: `CharField(max_length=180, help_text="Brief summary of out-of-tolerance condition")`
  - `as_found_error_description`: `TextField(help_text="Detailed metrology finding: deviation magnitude, affected parameters")`
  - `suspect_window_start`: `DateField(help_text="Date of last valid calibration or last confirmed in-spec verification")`
  - `suspect_window_end`: `DateField(default=timezone.now, help_text="Date gage was flagged out of tolerance and quarantined")`
  - `suspect_work_center`: `ForeignKey("scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="oot_investigations")`
  - `suspect_production_orders`: `TextField(blank=True, help_text="Comma-separated or listed Work Orders/Batches processed during window")`
  - `suspect_lots_count`: `PositiveIntegerField(default=0, help_text="Count of identified production batches in suspect window")`
  - `products_affected`: `CharField(max_length=200, blank=True, help_text="Product numbers/descriptions measured with this gage")`
  - `consumer_risk_rating`: `PositiveSmallIntegerField(default=3, help_text="Consumer Risk rating (1-5, probability of accepting bad parts)")`
  - `producer_risk_rating`: `PositiveSmallIntegerField(default=3, help_text="Producer Risk rating (1-5, probability of rejecting good parts)")`
  - `containment_actions_taken`: `TextField(blank=True, help_text="Physical quarantine of gage, quarantine of suspect warehouse stock")`
  - `product_disposition`: `CharField(max_length=24, choices=DISPOSITION_CHOICES, default="pending_review", db_index=True)`
  - `customer_notification_required`: `BooleanField(default=False)`
  - `product_recall_required`: `BooleanField(default=False)`
  - `linked_ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="oot_investigations")`
  - `linked_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="oot_investigations")`
  - `investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="investigated_oots")`
  - `quality_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_oots")`
  - `closure_date`: `DateField(null=True, blank=True)`
  - `conclusion_summary`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qoot_ten_num_uniq")` (25 chars)
  - `Index(fields=["tenant", "gage"], name="idx_qoot_ten_gage")` (17 chars)
  - `Index(fields=["tenant", "status"], name="idx_qoot_ten_status")` (19 chars)
  - `Index(fields=["tenant", "risk_level"], name="idx_qoot_ten_risk")` (17 chars)
  - `Index(fields=["tenant", "discovery_date"], name="idx_qoot_ten_disc")` (17 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qoot_ten_created")` (20 chars)

---

### 1.4 `MeasurementSystemAnalysis` (`MeasurementSystemAnalyses.py`)
- **`NUMBER_PREFIX`**: `"QMSA"`
- **`Meta.ordering`**: `["-study_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Measurement System Analysis (MSA)"` / `"Measurement System Analyses (MSA)"`
- **Choices & Badge Maps**:
  - `STUDY_TYPE_CHOICES` (`max_length=32`):
    - `("gage_rr_crossed", "Gage R&R (Crossed / Standard)")`
    - `("gage_rr_nested", "Gage R&R (Nested / Destructive)")`
    - `("linearity_and_bias", "Gage Linearity & Bias Study")`
    - `("stability_study", "Measurement Stability (Control Chart)")`
    - `("attribute_agreement", "Attribute Agreement Analysis")`
    - `("type_1_gage_study", "Type 1 Gage Study (Bias & Cgk)")`
  - `ANALYSIS_METHOD_CHOICES` (`max_length=32`):
    - `("anova", "ANOVA (Analysis of Variance) Method")`
    - `("average_and_range_xbar_r", "Average & Range (X-bar & R) Method")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft / Setup")`
    - `("data_collection", "Data Collection")`
    - `("analyzed", "Analyzed")`
    - `("approved", "Approved")`
    - `("rejected", "Rejected")`
  - `RESULT_CHOICES` (`max_length=24`):
    - `("acceptable", "Acceptable (%GRR < 10% / NDC >= 5)")`
    - `("marginal_conditional", "Marginal / Conditional (%GRR 10-30%)")`
    - `("unacceptable", "Unacceptable (%GRR > 30% / NDC < 5)")`
  - `RESULT_CSS`:
    - `"acceptable": "badge-green"`
    - `"marginal_conditional": "badge-amber"`
    - `"unacceptable": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"data_collection": "badge-amber"`
    - `"analyzed": "badge-info"`
    - `"approved": "badge-green"`
    - `"rejected": "badge-red"`
  - `STUDY_TYPE_CSS`:
    - `"gage_rr_crossed": "badge-info"`
    - `"gage_rr_nested": "badge-slate"`
    - `"linearity_and_bias": "badge-amber"`
    - `"stability_study": "badge-slate"`
    - `"attribute_agreement": "badge-info"`
    - `"type_1_gage_study": "badge-info"`

- **Fields**:
  - `study_title`: `CharField(max_length=150, help_text="e.g. Micrometer 0-25mm Gage R&R for Pin OD")`
  - `gage`: `ForeignKey("quality.CalibrationGage", on_delete=models.CASCADE, related_name="msa_studies")`
  - `study_type`: `CharField(max_length=32, choices=STUDY_TYPE_CHOICES, default="gage_rr_crossed", db_index=True)`
  - `analysis_method`: `CharField(max_length=32, choices=ANALYSIS_METHOD_CHOICES, default="anova", db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `characteristic_name`: `CharField(max_length=150, help_text="Dimension or feature being measured e.g. Outer Diameter")`
  - `study_date`: `DateField(default=timezone.now, db_index=True)`
  - `number_of_operators`: `PositiveIntegerField(default=3)`
  - `number_of_parts`: `PositiveIntegerField(default=10)`
  - `number_of_trials`: `PositiveIntegerField(default=3)`
  - `specification_tolerance`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.1000"), help_text="Total process or product tolerance (USL - LSL)")`
  - `reference_master_value`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Certified master value for bias/linearity")`
  - `repeatability_ev`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"), help_text="EV - Equipment Variation")`
  - `reproducibility_av`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"), help_text="AV - Appraiser Variation")`
  - `gage_rr_grr`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"), help_text="GRR - Combined Gage R&R")`
  - `part_variation_pv`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"), help_text="PV - Part-to-part variation")`
  - `total_variation_tv`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"), help_text="TV - Total study variation")`
  - `percent_gage_rr_study_variation`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"), help_text="%GRR of Study Variation (<10% Acceptable, 10-30% Marginal, >30% Unacceptable)")`
  - `percent_tolerance_pt_ratio`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"), help_text="P/T ratio (% of Tolerance)")`
  - `number_of_distinct_categories_ndc`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"), help_text="NDC category count (>= 5 acceptable)")`
  - `bias_value`: `DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)`
  - `bias_percentage`: `DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)`
  - `linearity_slope`: `DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)`
  - `linearity_r_squared`: `DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)`
  - `study_result`: `CharField(max_length=24, choices=RESULT_CHOICES, default="acceptable", db_index=True)`
  - `raw_study_data`: `JSONField(default=dict, blank=True, help_text="Raw measurement data array (operator, part, trial, value)")`
  - `study_protocol_doc`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="msa_studies")`
  - `study_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="led_msa_studies")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_msa_studies")`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `conclusion`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qmsa_ten_num_uniq")` (25 chars)
  - `Index(fields=["tenant", "study_type"], name="idx_qmsa_ten_type")` (17 chars)
  - `Index(fields=["tenant", "study_result"], name="idx_qmsa_ten_res")` (16 chars)
  - `Index(fields=["tenant", "status"], name="idx_qmsa_ten_status")` (19 chars)
  - `Index(fields=["tenant", "gage"], name="idx_qmsa_ten_gage")` (17 chars)
  - `Index(fields=["tenant", "study_date"], name="idx_qmsa_ten_date")` (17 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qmsa_ten_created")` (20 chars)

---

## 2. Forms Contract (`apps/quality/forms/CalibrationAnalysis/`)

### 2.1 Excluded Fields
- `tenant`, `number`, `created_at`, `updated_at`, `approved_at` across all forms.
- `CalibrationRecordForm`: exclude `guardband_applied` from manual input (or default True).
- `MeasurementSystemAnalysisForm`: exclude `raw_study_data` from standard form inputs.

### 2.2 Form Validation Rules
- All FK fields (`gage`, `service_vendor`, `asset_link`, `work_center`, `department`, `custodian`, `calibrated_by_user`, `approved_by`, `investigator`, `quality_approver`, `linked_ncr`, `linked_capa`, `sop_document`, `study_protocol_doc`, `study_lead`) MUST be validated in `clean()` via `reject_foreign(...)` to ensure tenant isolation.
- `CalibrationGageForm`:
  - `calibration_interval_days` must be `> 0`.
  - If `is_reference_standard` is True, `nist_traceability_number` is recommended.
- `CalibrationRecordForm`:
  - `calibration_date` cannot be in future.
- `OutOfToleranceInvestigationForm`:
  - `suspect_window_start` cannot be after `suspect_window_end`.
- `MeasurementSystemAnalysisForm`:
  - `number_of_operators`, `number_of_parts`, `number_of_trials` must be `>= 1`.
  - `specification_tolerance` must be `> 0`.

---

## 3. URLs Contract (`apps/quality/urls/CalibrationAnalysis/`)

All URL patterns belong to `app_name = "quality"`.

### 3.1 Entity URLs
1. **CalibrationGage**:
   - `gage/` -> `name="calibration_gage_list"`
   - `gage/create/` -> `name="calibration_gage_create"`
   - `gage/export/` -> `name="calibration_gage_export_csv"`
   - `gage/<int:pk>/` -> `name="calibration_gage_detail"`
   - `gage/<int:pk>/edit/` -> `name="calibration_gage_edit"`
   - `gage/<int:pk>/delete/` -> `name="calibration_gage_delete"`
2. **CalibrationRecord**:
   - `calibration-record/` -> `name="calibration_record_list"`
   - `calibration-record/create/` -> `name="calibration_record_create"`
   - `calibration-record/export/` -> `name="calibration_record_export_csv"`
   - `calibration-record/<int:pk>/` -> `name="calibration_record_detail"`
   - `calibration-record/<int:pk>/edit/` -> `name="calibration_record_edit"`
   - `calibration-record/<int:pk>/delete/` -> `name="calibration_record_delete"`
3. **OutOfToleranceInvestigation**:
   - `oot-investigation/` -> `name="out_of_tolerance_investigation_list"`
   - `oot-investigation/create/` -> `name="out_of_tolerance_investigation_create"`
   - `oot-investigation/export/` -> `name="out_of_tolerance_investigation_export_csv"`
   - `oot-investigation/<int:pk>/` -> `name="out_of_tolerance_investigation_detail"`
   - `oot-investigation/<int:pk>/edit/` -> `name="out_of_tolerance_investigation_edit"`
   - `oot-investigation/<int:pk>/delete/` -> `name="out_of_tolerance_investigation_delete"`
4. **MeasurementSystemAnalysis**:
   - `msa/` -> `name="measurement_system_analysis_list"`
   - `msa/create/` -> `name="measurement_system_analysis_create"`
   - `msa/export/` -> `name="measurement_system_analysis_export_csv"`
   - `msa/<int:pk>/` -> `name="measurement_system_analysis_detail"`
   - `msa/<int:pk>/edit/` -> `name="measurement_system_analysis_edit"`
   - `msa/<int:pk>/delete/` -> `name="measurement_system_analysis_delete"`
5. **Vendor Directory**:
   - `calibration-vendors/` -> `name="calibration_vendor_directory"`

*Note: Order in `urls/__init__.py`: Literal exports and creates MUST precede `<int:pk>/` patterns (first-match-wins).*

---

## 4. Views & Context Keys Contract (Mandatory, L7 / L8)

Every view must provide the exact context keys specified below. Both the domain-specific key AND `obj` are passed to detail/form views to prevent silent template blanks.

### 4.1 `CalibrationGage` Views
- `calibration_gage_list`:
  - `gages`: Page queryset
  - `page_obj`: Paginator Page object
  - `search_query`: String from `request.GET.get('q', '')`
  - `status_filter`: String from `request.GET.get('status', '')`
  - `type_filter`: String from `request.GET.get('gage_type', '')`
  - `criticality_filter`: String from `request.GET.get('criticality', '')`
  - `status_choices`: `CalibrationGage.STATUS_CHOICES`
  - `type_choices`: `CalibrationGage.GAGE_TYPE_CHOICES`
  - `criticality_choices`: `CalibrationGage.CRITICALITY_CHOICES`
  - `total_gages`: Integer count
  - `past_due_count`: Integer count
  - `in_service_count`: Integer count
- `calibration_gage_detail`:
  - `gage`: Target `CalibrationGage` instance
  - `obj`: Target `CalibrationGage` instance (L7 dual-binding)
  - `calibration_history`: Queryset of linked `CalibrationRecord`s
  - `oot_history`: Queryset of linked `OutOfToleranceInvestigation`s
  - `msa_studies`: Queryset of linked `MeasurementSystemAnalysis` records
- `calibration_gage_create` & `calibration_gage_edit`:
  - `form`: `CalibrationGageForm`
  - `gage` / `obj`: Target instance (None on create)
  - `is_edit`: Boolean

### 4.2 `CalibrationRecord` Views
- `calibration_record_list`:
  - `calibration_records`: Page queryset
  - `page_obj`: Paginator Page object
  - `search_query`: String from `request.GET.get('q', '')`
  - `result_filter`: String from `request.GET.get('overall_result', '')`
  - `type_filter`: String from `request.GET.get('calibration_type', '')`
  - `status_filter`: String from `request.GET.get('status', '')`
  - `result_choices`: `CalibrationRecord.OVERALL_RESULT_CHOICES`
  - `type_choices`: `CalibrationRecord.CALIBRATION_TYPE_CHOICES`
  - `status_choices`: `CalibrationRecord.STATUS_CHOICES`
  - `total_calibrations`: Integer count
  - `oot_count`: Integer count
- `calibration_record_detail`:
  - `calibration_record`: Target `CalibrationRecord` instance
  - `obj`: Target `CalibrationRecord` instance
  - `standards_list`: Queryset of linked reference standards
  - `oot_investigation`: First linked OOT investigation if any
- `calibration_record_create` & `calibration_record_edit`:
  - `form`: `CalibrationRecordForm`
  - `calibration_record` / `obj`: Target instance (None on create)
  - `is_edit`: Boolean

### 4.3 `OutOfToleranceInvestigation` Views
- `out_of_tolerance_investigation_list`:
  - `oot_investigations`: Page queryset
  - `page_obj`: Paginator Page object
  - `search_query`: String from `request.GET.get('q', '')`
  - `status_filter`: String from `request.GET.get('status', '')`
  - `risk_filter`: String from `request.GET.get('risk_level', '')`
  - `status_choices`: `OutOfToleranceInvestigation.STATUS_CHOICES`
  - `risk_choices`: `OutOfToleranceInvestigation.RISK_LEVEL_CHOICES`
  - `total_oots`: Integer count
  - `critical_count`: Integer count
  - `open_count`: Integer count
- `out_of_tolerance_investigation_detail`:
  - `oot_investigation`: Target `OutOfToleranceInvestigation` instance
  - `obj`: Target `OutOfToleranceInvestigation` instance
- `out_of_tolerance_investigation_create` & `out_of_tolerance_investigation_edit`:
  - `form`: `OutOfToleranceInvestigationForm`
  - `oot_investigation` / `obj`: Target instance (None on create)
  - `is_edit`: Boolean

### 4.4 `MeasurementSystemAnalysis` Views
- `measurement_system_analysis_list`:
  - `msa_studies`: Page queryset
  - `page_obj`: Paginator Page object
  - `search_query`: String from `request.GET.get('q', '')`
  - `study_type_filter`: String from `request.GET.get('study_type', '')`
  - `result_filter`: String from `request.GET.get('study_result', '')`
  - `study_type_choices`: `MeasurementSystemAnalysis.STUDY_TYPE_CHOICES`
  - `result_choices`: `MeasurementSystemAnalysis.RESULT_CHOICES`
  - `total_studies`: Integer count
  - `acceptable_count`: Integer count
- `measurement_system_analysis_detail`:
  - `msa_study`: Target `MeasurementSystemAnalysis` instance
  - `obj`: Target `MeasurementSystemAnalysis` instance
- `measurement_system_analysis_create` & `measurement_system_analysis_edit`:
  - `form`: `MeasurementSystemAnalysisForm`
  - `msa_study` / `obj`: Target instance (None on create)
  - `is_edit`: Boolean

### 4.5 `CalibrationVendorDirectory` View
- `calibration_vendor_directory`:
  - `vendors`: Queryset of `core.Party` instances with vendor roles or calibration service contracts
  - `page_obj`: Paginator Page object
  - `search_query`: String from `request.GET.get('q', '')`

---

## 5. Navigation `LIVE_LINKS["12.10"]` Contract

Mapped in `apps/core/navigation.py`:

```python
    "12.10": {
        "Calibration Schedule & Planning": "quality:calibration_gage_list",
        "Calibration Execution & Records": "quality:calibration_record_list",
        "Out-of-Tolerance (OOT) Handling": "quality:out_of_tolerance_investigation_list",
        "Measurement System Analysis (MSA / Gage R&R)": "quality:measurement_system_analysis_list",
        "Calibration Vendor Management": "quality:calibration_vendor_directory",
    },
```

---

## 6. Seeder Contract (`apps/quality/management/commands/seed_quality.py`)

- Must be idempotent (`get_or_create` or existence checks by `tenant` and unique identifiers).
- Seeds at least:
  - 6 `CalibrationGage` records per tenant (covering calipers, micrometers, pressure gages, multimeters, reference standard blocks, with at least 1 in `past_due`, 1 in `quarantined_oot`, 1 in `in_calibration`, and 1 `is_reference_standard=True`).
  - 4 `CalibrationRecord` records per tenant (covering internal and external calibrations, passing events, test points data, and 1 failing/OOT event).
  - 2 `OutOfToleranceInvestigation` records per tenant (1 `critical` with reverse-tracing suspect window and containment actions, 1 `minor` closed).
  - 3 `MeasurementSystemAnalysis` studies per tenant (1 `gage_rr_crossed` with %GRR = 7.42% acceptable, 1 `gage_rr_crossed` marginal 18.5%, 1 `linearity_and_bias` study).
