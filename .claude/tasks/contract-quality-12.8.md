# Module 12.8 Pre-Build Contract — In-Process Quality & SPC / Process Control (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.8"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0013_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/InProcessQuality/`
  - `apps/quality/forms/InProcessQuality/`
  - `apps/quality/views/InProcessQuality/`
  - `apps/quality/urls/InProcessQuality/`
  - `templates/quality/inprocessquality/{in_process_inspection,first_article_inspection,process_parameter_log,layered_process_audit}/{list,detail,form}.html` + `templates/quality/inprocessquality/spc_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"release"`, `"hold"`, `"mitigate"`, `"export"` (all `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `quality.ControlledDocument`, `quality.NonConformanceReport`, `quality.ProcessDeviation`, `scm.WorkOrder`, `scm.WorkCenter`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/InProcessQuality/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `InProcessInspection` (`InProcessInspections.py`)
- **`NUMBER_PREFIX`**: `"QIPQ"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"In-Process Inspection"` / `"In-Process Inspections"`
- **Choices & Badge Maps**:
  - `INSPECTION_TYPE_CHOICES` (`max_length=30`):
    - `("visual_surface", "Visual / Surface Finish Inspection")`
    - `("dimensional_gauging", "Dimensional / Gauging Verification")`
    - `("functional_test", "In-Line Functional / Electrical Test")`
    - `("automated_vision", "Automated Vision / Optical Inspection")`
    - `("in_line_stage_gate", "Stage-Gate Completion Inspection")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft / Scheduled")`
    - `("in_progress", "In Progress")`
    - `("completed", "Completed")`
    - `("cancelled", "Cancelled")`
  - `DISPOSITION_CHOICES` (`max_length=25`):
    - `("pending", "Pending Disposition")`
    - `("pass", "Pass / Conforming")`
    - `("conditional_pass", "Conditional Pass (Deviation)")`
    - `("rework_required", "Rework Required")`
    - `("reject_scrap", "Reject / Scrap")`
    - `("quarantine_hold", "Quarantine Hold")`
  - `DEFECT_CATEGORY_CHOICES` (`max_length=30`):
    - `("", "None / Conforming")`
    - `("dimensional", "Dimensional Out-of-Tolerance")`
    - `("surface_cosmetic", "Surface / Cosmetic Defect")`
    - `("functional_electrical", "Functional / Electrical Failure")`
    - `("material_flaw", "Raw Material Flaw / Void")`
    - `("assembly_error", "Assembly / Orientation Error")`
    - `("contamination", "Foreign Object / Contamination")`
    - `("other", "Other Defect Category")`
  - `INSPECTION_TYPE_CSS`:
    - `"visual_surface": "badge-slate"`
    - `"dimensional_gauging": "badge-info"`
    - `"functional_test": "badge-amber"`
    - `"automated_vision": "badge-purple"` (wait, purple is not in theme.css badges, use `"badge-info"`)
    - `"in_line_stage_gate": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_progress": "badge-amber"`
    - `"completed": "badge-green"`
    - `"cancelled": "badge-muted"`
  - `DISPOSITION_CSS`:
    - `"pending": "badge-slate"`
    - `"pass": "badge-green"`
    - `"conditional_pass": "badge-info"`
    - `"rework_required": "badge-amber"`
    - `"reject_scrap": "badge-red"`
    - `"quarantine_hold": "badge-red"`
  - `DEFECT_CATEGORY_CSS`:
    - `"": "badge-muted"`
    - `"dimensional": "badge-amber"`
    - `"surface_cosmetic": "badge-info"`
    - `"functional_electrical": "badge-red"`
    - `"material_flaw": "badge-red"`
    - `"assembly_error": "badge-amber"`
    - `"contamination": "badge-red"`
    - `"other": "badge-slate"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `inspection_type`: `CharField(max_length=30, choices=INSPECTION_TYPE_CHOICES, default="visual_surface", db_index=True)`
  - `stage_gate`: `CharField(max_length=100, blank=True, help_text="Manufacturing stage-gate (e.g. Primary Machining, Sub-Assembly, Final In-Line)")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `disposition`: `CharField(max_length=25, choices=DISPOSITION_CHOICES, default="pending", db_index=True)`
  - `production_order_number`: `CharField(max_length=64, blank=True)`
  - `work_order`: `ForeignKey("scm.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_in_process_inspections")`
  - `work_center_code`: `CharField(max_length=64, blank=True)`
  - `work_center`: `ForeignKey("scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_in_process_inspections")`
  - `operation_step`: `CharField(max_length=64, blank=True, help_text="e.g. Op 020 - Turning")`
  - `item_code`: `CharField(max_length=100, blank=True)`
  - `item_name`: `CharField(max_length=255, blank=True)`
  - `lot_number`: `CharField(max_length=100, blank=True)`
  - `serial_number`: `CharField(max_length=100, blank=True)`
  - `batch_quantity`: `PositiveIntegerField(default=1)`
  - `sample_size_inspected`: `PositiveIntegerField(default=1)`
  - `quantity_passed`: `PositiveIntegerField(default=0)`
  - `quantity_rejected`: `PositiveIntegerField(default=0)`
  - `quantity_reworked`: `PositiveIntegerField(default=0)`
  - `defect_category`: `CharField(max_length=30, choices=DEFECT_CATEGORY_CHOICES, blank=True, default="", db_index=True)`
  - `defect_description`: `TextField(blank=True)`
  - `controlled_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="in_process_inspections", help_text="Linked SOP or Digital Work Instruction")`
  - `work_instruction_step`: `CharField(max_length=100, blank=True)`
  - `operator_sign_off`: `BooleanField(default=False)`
  - `operator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="operator_in_process_inspections")`
  - `inspector`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="conducted_in_process_inspections")`
  - `inspection_date`: `DateField(null=True, blank=True)`
  - `non_conformance`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="in_process_inspections", help_text="Escalated NCR on inspection failure")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qipq_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qipq_ten_status")` (19)
  - `Index(fields=["tenant", "disposition"], name="idx_qipq_ten_disp")` (17)
  - `Index(fields=["tenant", "inspection_type"], name="idx_qipq_ten_type")` (17)
  - `Index(fields=["tenant", "work_center"], name="idx_qipq_ten_wc")` (15)
  - `Index(fields=["tenant", "work_order"], name="idx_qipq_ten_wo")` (15)
  - `Index(fields=["tenant", "-created_at"], name="idx_qipq_ten_created")` (20)

### 1.2 `FirstArticleInspection` (`FirstArticleInspections.py`)
- **`NUMBER_PREFIX`**: `"QFAI"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"First Article Inspection"` / `"First Article Inspections"`
- **Choices & Badge Maps**:
  - `FAI_TYPE_CHOICES` (`max_length=25`):
    - `("full_fai", "Full First Article Inspection (AS9102)")`
    - `("delta_partial_fai", "Delta / Partial FAI (Change Only)")`
  - `SETUP_REASON_CHOICES` (`max_length=35`):
    - `("new_product_intro", "New Product Introduction (NPI)")`
    - `("machine_setup_change", "Machine / Tooling Setup Change")`
    - `("tooling_die_change", "Tooling / Die Replacement")`
    - `("process_revision", "Process / Routing Revision")`
    - `("material_lot_change", "Raw Material Source / Lot Change")`
    - `("drawing_revision", "Engineering Drawing / Revision Change")`
    - `("periodic_recertification", "Periodic Recertification / Dormancy")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("draft", "Draft / Scheduled")`
    - `("in_inspection", "In Inspection / Measurement")`
    - `("approved_run_released", "Approved (Production Released)")`
    - `("conditional_approval", "Conditional Approval (Pilot Run)")`
    - `("rejected_setup_hold", "Rejected (Setup Hold)")`
    - `("cancelled", "Cancelled")`
  - `RELEASE_VERDICT_CHOICES` (`max_length=30`):
    - `("pending", "Pending Verdict")`
    - `("released", "Full Production Run Released")`
    - `("conditional_pilot_release", "Conditional Pilot Release")`
    - `("rejected_retool", "Rejected / Retool & Re-inspect")`
  - `FAI_TYPE_CSS`:
    - `"full_fai": "badge-info"`
    - `"delta_partial_fai": "badge-slate"`
  - `SETUP_REASON_CSS`:
    - `"new_product_intro": "badge-info"`
    - `"machine_setup_change": "badge-slate"`
    - `"tooling_die_change": "badge-slate"`
    - `"process_revision": "badge-amber"`
    - `"material_lot_change": "badge-slate"`
    - `"drawing_revision": "badge-amber"`
    - `"periodic_recertification": "badge-info"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_inspection": "badge-amber"`
    - `"approved_run_released": "badge-green"`
    - `"conditional_approval": "badge-info"`
    - `"rejected_setup_hold": "badge-red"`
    - `"cancelled": "badge-muted"`
  - `RELEASE_VERDICT_CSS`:
    - `"pending": "badge-slate"`
    - `"released": "badge-green"`
    - `"conditional_pilot_release": "badge-info"`
    - `"rejected_retool": "badge-red"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `fai_type`: `CharField(max_length=25, choices=FAI_TYPE_CHOICES, default="full_fai", db_index=True)`
  - `setup_reason`: `CharField(max_length=35, choices=SETUP_REASON_CHOICES, default="machine_setup_change", db_index=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `production_order_number`: `CharField(max_length=64, blank=True)`
  - `work_order`: `ForeignKey("scm.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_fais")`
  - `work_center_code`: `CharField(max_length=64, blank=True)`
  - `work_center`: `ForeignKey("scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_fais")`
  - `machine_tooling_id`: `CharField(max_length=100, blank=True)`
  - `item_code`: `CharField(max_length=100, blank=True)`
  - `item_name`: `CharField(max_length=255, blank=True)`
  - `drawing_number`: `CharField(max_length=100, blank=True)`
  - `drawing_revision`: `CharField(max_length=32, blank=True)`
  - `first_piece_lot_number`: `CharField(max_length=100, blank=True)`
  - `serial_number`: `CharField(max_length=100, blank=True)`
  - `total_characteristics_inspected`: `PositiveIntegerField(default=0)`
  - `characteristics_conforming`: `PositiveIntegerField(default=0)`
  - `characteristics_out_of_spec`: `PositiveIntegerField(default=0)`
  - `max_deviation_found`: `CharField(max_length=100, blank=True, help_text="e.g. +0.003 mm on Bore Dia")`
  - `as9102_form1_complete`: `BooleanField(default=False, help_text="Part Number Accountability")`
  - `as9102_form2_complete`: `BooleanField(default=False, help_text="Product Process Accountability")`
  - `as9102_form3_complete`: `BooleanField(default=False, help_text="Characteristic Accountability & Verification")`
  - `gage_serial_numbers`: `CharField(max_length=255, blank=True, help_text="Calibrated instruments used (micrometer, CMM, height gauge)")`
  - `release_verdict`: `CharField(max_length=30, choices=RELEASE_VERDICT_CHOICES, default="pending", db_index=True)`
  - `conditional_release_notes`: `TextField(blank=True)`
  - `non_conformance`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="fais")`
  - `inspector`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="inspected_fais")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_fais")`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qfai_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qfai_ten_status")` (19)
  - `Index(fields=["tenant", "release_verdict"], name="idx_qfai_ten_verd")` (17)
  - `Index(fields=["tenant", "fai_type"], name="idx_qfai_ten_type")` (17)
  - `Index(fields=["tenant", "setup_reason"], name="idx_qfai_ten_reason")` (19)
  - `Index(fields=["tenant", "work_center"], name="idx_qfai_ten_wc")` (15)
  - `Index(fields=["tenant", "work_order"], name="idx_qfai_ten_wo")` (15)
  - `Index(fields=["tenant", "-created_at"], name="idx_qfai_ten_created")` (20)

### 1.3 `ProcessParameterLog` (`ProcessParameterLogs.py`)
- **`NUMBER_PREFIX`**: `"QPAR"`
- **`Meta.ordering`**: `["-recorded_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Process Parameter Log"` / `"Process Parameter Logs"`
- **Choices & Badge Maps**:
  - `PARAMETER_CATEGORY_CHOICES` (`max_length=30`):
    - `("temperature", "Thermal / Temperature (°C)")`
    - `("pressure", "Hydraulic / Pneumatic Pressure (bar)")`
    - `("speed_feed", "Spindle Speed / Feed Rate (RPM / mm/min)")`
    - `("torque", "Fastener Torque / Clamping Force (Nm)")`
    - `("ph_chemical", "Chemical Concentration / pH")`
    - `("humidity", "Cleanroom Humidity / Environmental (%RH)")`
    - `("dimensional_thickness", "In-Line Thickness / Dimension (mm)")`
    - `("voltage_current", "Electrical Voltage / Current (V / A)")`
    - `("cycle_time", "Process Cycle Time (sec)")`
    - `("other", "Other Critical Parameter")`
  - `EXCURSION_STATUS_CHOICES` (`max_length=25`):
    - `("normal", "Normal (In Control & In Spec)")`
    - `("warning_pre_control", "Warning (Pre-Control Zone / Trend)")`
    - `("out_of_control", "Out of Control (SPC 3-Sigma Rule Violation)")`
    - `("out_of_spec", "Out of Spec (Exceeded USL/LSL Tolerance)")`
  - `CONTAINMENT_ACTION_CHOICES` (`max_length=35`):
    - `("none", "None / In Control")`
    - `("machine_parameter_adjusted", "Machine Parameter Adjusted")`
    - `("machine_paused", "Machine Paused / Maintenance Alerted")`
    - `("wip_quarantined", "WIP Material Quarantined")`
    - `("supervisor_escalated", "Supervisor / Engineer Escalated")`
    - `("ncr_initiated", "Formal NCR Initiated")`
  - `PARAMETER_CATEGORY_CSS`:
    - `"temperature": "badge-red"`
    - `"pressure": "badge-amber"`
    - `"speed_feed": "badge-info"`
    - `"torque": "badge-slate"`
    - `"ph_chemical": "badge-info"`
    - `"humidity": "badge-slate"`
    - `"dimensional_thickness": "badge-info"`
    - `"voltage_current": "badge-amber"`
    - `"cycle_time": "badge-slate"`
    - `"other": "badge-muted"`
  - `EXCURSION_STATUS_CSS`:
    - `"normal": "badge-green"`
    - `"warning_pre_control": "badge-amber"`
    - `"out_of_control": "badge-amber"`
    - `"out_of_spec": "badge-red"`
  - `CONTAINMENT_ACTION_CSS`:
    - `"none": "badge-slate"`
    - `"machine_parameter_adjusted": "badge-info"`
    - `"machine_paused": "badge-amber"`
    - `"wip_quarantined": "badge-red"`
    - `"supervisor_escalated": "badge-amber"`
    - `"ncr_initiated": "badge-red"`
- **Fields**:
  - `parameter_name`: `CharField(max_length=150)`
  - `parameter_category`: `CharField(max_length=30, choices=PARAMETER_CATEGORY_CHOICES, default="temperature", db_index=True)`
  - `unit_of_measure`: `CharField(max_length=32, help_text="e.g. °C, bar, RPM, Nm, mm, V, sec")`
  - `work_center_code`: `CharField(max_length=64, blank=True)`
  - `work_center`: `ForeignKey("scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_parameter_logs")`
  - `production_order_number`: `CharField(max_length=64, blank=True)`
  - `work_order`: `ForeignKey("scm.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_parameter_logs")`
  - `operation_step`: `CharField(max_length=64, blank=True)`
  - `item_code`: `CharField(max_length=100, blank=True)`
  - `lot_number`: `CharField(max_length=100, blank=True)`
  - `target_nominal_value`: `DecimalField(max_digits=12, decimal_places=4)`
  - `upper_spec_limit`: `DecimalField(max_digits=12, decimal_places=4, help_text="USL - Engineering upper tolerance")`
  - `lower_spec_limit`: `DecimalField(max_digits=12, decimal_places=4, help_text="LSL - Engineering lower tolerance")`
  - `upper_control_limit`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="UCL - Statistical upper limit (μ + 3σ)")`
  - `lower_control_limit`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="LCL - Statistical lower limit (μ - 3σ)")`
  - `recorded_value`: `DecimalField(max_digits=12, decimal_places=4)`
  - `recorded_at`: `DateTimeField(default=timezone.now)`
  - `excursion_status`: `CharField(max_length=25, choices=EXCURSION_STATUS_CHOICES, default="normal", db_index=True)`
  - `logged_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="logged_parameters")`
  - `containment_action`: `CharField(max_length=35, choices=CONTAINMENT_ACTION_CHOICES, default="none", db_index=True)`
  - `containment_notes`: `TextField(blank=True)`
  - `non_conformance`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="parameter_logs")`
  - `process_deviation`: `ForeignKey("quality.ProcessDeviation", on_delete=models.SET_NULL, null=True, blank=True, related_name="parameter_logs", help_text="Authorized temporary waiver/concession")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qpar_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "excursion_status"], name="idx_qpar_ten_excurs")` (19)
  - `Index(fields=["tenant", "parameter_category"], name="idx_qpar_ten_cat")` (16)
  - `Index(fields=["tenant", "work_center"], name="idx_qpar_ten_wc")` (15)
  - `Index(fields=["tenant", "work_order"], name="idx_qpar_ten_wo")` (15)
  - `Index(fields=["tenant", "recorded_at"], name="idx_qpar_ten_rec_at")` (19)
  - `Index(fields=["tenant", "-created_at"], name="idx_qpar_ten_created")` (20)

### 1.4 `LayeredProcessAudit` (`LayeredProcessAudits.py`)
- **`NUMBER_PREFIX`**: `"QLPA"`
- **`Meta.ordering`**: `["-scheduled_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Layered Process Audit"` / `"Layered Process Audits"`
- **Choices & Badge Maps**:
  - `AUDIT_LAYER_CHOICES` (`max_length=30`):
    - `("tier_1_operator_lead", "Tier 1: Shift Team Leader (Daily)")`
    - `("tier_2_supervisor", "Tier 2: Area Production Supervisor (Weekly)")`
    - `("tier_3_quality_manager", "Tier 3: Quality / Operations Manager (Monthly)")`
    - `("tier_4_plant_executive", "Tier 4: Plant Manager / Director (Quarterly)")`
  - `FOCUS_AREA_CHOICES` (`max_length=30`):
    - `("standard_work_wi", "Standard Work & Work Instruction Adherence")`
    - `("tooling_machine_setup", "Machine Setup, Fixturing & Poka-Yoke")`
    - `("material_handling_fifo", "Material Identification & FIFO / Lot Control")`
    - `("gauging_calibration", "Measurement Gauging & Calibration Validity")`
    - `("environmental_5s", "5S Housekeeping & Cleanliness")`
    - `("safety_poka_yoke", "Operator Safety & Error-Proofing Verification")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("scheduled", "Scheduled")`
    - `("in_progress", "In Progress")`
    - `("completed", "Completed")`
    - `("cancelled", "Cancelled")`
  - `AUDIT_LAYER_CSS`:
    - `"tier_1_operator_lead": "badge-slate"`
    - `"tier_2_supervisor": "badge-info"`
    - `"tier_3_quality_manager": "badge-amber"`
    - `"tier_4_plant_executive": "badge-green"`
  - `FOCUS_AREA_CSS`:
    - `"standard_work_wi": "badge-info"`
    - `"tooling_machine_setup": "badge-slate"`
    - `"material_handling_fifo": "badge-slate"`
    - `"gauging_calibration": "badge-info"`
    - `"environmental_5s": "badge-green"`
    - `"safety_poka_yoke": "badge-amber"`
  - `STATUS_CSS`:
    - `"scheduled": "badge-slate"`
    - `"in_progress": "badge-amber"`
    - `"completed": "badge-green"`
    - `"cancelled": "badge-muted"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `audit_layer`: `CharField(max_length=30, choices=AUDIT_LAYER_CHOICES, default="tier_1_operator_lead", db_index=True)`
  - `focus_area`: `CharField(max_length=30, choices=FOCUS_AREA_CHOICES, default="standard_work_wi", db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled", db_index=True)`
  - `work_center_code`: `CharField(max_length=64, blank=True)`
  - `work_center`: `ForeignKey("scm.WorkCenter", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_lpas")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_lpas")`
  - `shift`: `CharField(max_length=32, blank=True, help_text="e.g. Shift 1 (Morning), Shift 2, Night")`
  - `total_questions_audited`: `PositiveIntegerField(default=10)`
  - `questions_conforming`: `PositiveIntegerField(default=10)`
  - `questions_non_conforming`: `PositiveIntegerField(default=0)`
  - `compliance_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"), help_text="Calculated compliance score 0-100%")`
  - `findings_summary`: `TextField(blank=True)`
  - `controlled_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="lpa_audits", help_text="LPA Checklist or standard work instruction")`
  - `on_the_spot_mitigation`: `BooleanField(default=False, help_text="Identified non-conformances contained immediately during audit")`
  - `mitigation_details`: `TextField(blank=True)`
  - `non_conformance`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="lpas")`
  - `auditor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="conducted_lpas")`
  - `scheduled_date`: `DateField()`
  - `conducted_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qlpa_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qlpa_ten_status")` (19)
  - `Index(fields=["tenant", "audit_layer"], name="idx_qlpa_ten_layer")` (18)
  - `Index(fields=["tenant", "focus_area"], name="idx_qlpa_ten_focus")` (18)
  - `Index(fields=["tenant", "work_center"], name="idx_qlpa_ten_wc")` (15)
  - `Index(fields=["tenant", "scheduled_date"], name="idx_qlpa_ten_sched")` (18)
  - `Index(fields=["tenant", "-created_at"], name="idx_qlpa_ten_created")` (20)

---

## 2. Forms Contract (`apps/quality/forms/InProcessQuality/`)

Every form inherits `apps.core.forms.TenantModelForm` and `apps.quality.forms._common.TenantUniqueMixin`.

### 2.1 `InProcessInspectionForm` (`InProcessInspections.py`)
- **`model`**: `InProcessInspection`
- **`exclude`**: `["tenant", "number", "created_at", "updated_at"]`
- **Tenant FK validation**: Filters querysets by `tenant=self.tenant` in `__init__` for:
  `work_order`, `work_center`, `controlled_document`, `operator`, `inspector`, `non_conformance`.
- **`clean()` validations**:
  - `reject_foreign(self, cleaned_data, ["work_order", "work_center", "controlled_document", "operator", "inspector", "non_conformance"])`
  - Quantity consistency: `sample_size_inspected <= batch_quantity`
  - Sum validation: `quantity_passed + quantity_rejected + quantity_reworked <= sample_size_inspected`
  - Mandatory defect description if `disposition in ["rework_required", "reject_scrap", "quarantine_hold"]` or `quantity_rejected > 0`

### 2.2 `FirstArticleInspectionForm` (`FirstArticleInspections.py`)
- **`model`**: `FirstArticleInspection`
- **`exclude`**: `["tenant", "number", "approved_at", "created_at", "updated_at"]`
- **Tenant FK validation**: Filters querysets by `tenant=self.tenant` in `__init__` for:
  `work_order`, `work_center`, `non_conformance`, `inspector`, `approved_by`.
- **`clean()` validations**:
  - `reject_foreign(self, cleaned_data, ["work_order", "work_center", "non_conformance", "inspector", "approved_by"])`
  - Characteristic counts: `characteristics_conforming + characteristics_out_of_spec <= total_characteristics_inspected`
  - If `status == "approved_run_released"` or `release_verdict == "released"`:
    - `characteristics_out_of_spec == 0` (Zero defect rule for full release)
    - `as9102_form1_complete`, `as9102_form2_complete`, and `as9102_form3_complete` MUST all be True.
  - If `status == "conditional_approval"` or `release_verdict == "conditional_pilot_release"`:
    - `conditional_release_notes` MUST NOT be blank.

### 2.3 `ProcessParameterLogForm` (`ProcessParameterLogs.py`)
- **`model`**: `ProcessParameterLog`
- **`exclude`**: `["tenant", "number", "created_at", "updated_at"]`
- **Tenant FK validation**: Filters querysets by `tenant=self.tenant` in `__init__` for:
  `work_center`, `work_order`, `logged_by`, `non_conformance`, `process_deviation`.
- **`clean()` validations**:
  - `reject_foreign(self, cleaned_data, ["work_center", "work_order", "logged_by", "non_conformance", "process_deviation"])`
  - Spec limit order: `lower_spec_limit <= target_nominal_value <= upper_spec_limit`
  - Control limit order (if provided): `lower_control_limit <= target_nominal_value <= upper_control_limit` and `lower_spec_limit <= lower_control_limit` and `upper_control_limit <= upper_spec_limit`
  - Automatic excursion detection helper in `clean()`:
    - If `recorded_value > upper_spec_limit` or `recorded_value < lower_spec_limit`:
      `cleaned_data["excursion_status"] = "out_of_spec"`
    - Else if control limits exist and (`recorded_value > upper_control_limit` or `recorded_value < lower_control_limit`):
      `cleaned_data["excursion_status"] = "out_of_control"`
    - Else:
      `cleaned_data["excursion_status"] = "normal"` (unless already set to warning)
  - If `excursion_status == "out_of_spec"` and `containment_action == "none"`:
    - Require `containment_action != "none"` or raise validation error.

### 2.4 `LayeredProcessAuditForm` (`LayeredProcessAudits.py`)
- **`model`**: `LayeredProcessAudit`
- **`exclude`**: `["tenant", "number", "compliance_percentage", "created_at", "updated_at"]`
- **Tenant FK validation**: Filters querysets by `tenant=self.tenant` in `__init__` for:
  `work_center`, `org_unit`, `controlled_document`, `non_conformance`, `auditor`.
- **`clean()` validations**:
  - `reject_foreign(self, cleaned_data, ["work_center", "org_unit", "controlled_document", "non_conformance", "auditor"])`
  - Questions count: `questions_conforming + questions_non_conforming == total_questions_audited` (if total > 0)
  - If `questions_non_conforming > 0`:
    - `findings_summary` cannot be blank.
    - If `on_the_spot_mitigation` is True, `mitigation_details` cannot be blank.

---

## 3. Views Contract (`apps/quality/views/InProcessQuality/`)

All views function-based, `@login_required`, multi-tenant scoped via `quality_scope` / `quality_object`. Privileged mutations use `@tenant_admin_required`. Every mutation writes `write_audit_log`.

### 3.1 `InProcessInspections.py`
- `in_process_inspection_list(request)`
  - URL: `in-process-inspections/` (`quality:in_process_inspection_list`)
  - Template: `quality/inprocessquality/in_process_inspection/list.html`
  - Context keys:
    - `page_obj`: paginated `InProcessInspection` records
    - `status_choices`: `InProcessInspection.STATUS_CHOICES`
    - `disposition_choices`: `InProcessInspection.DISPOSITION_CHOICES`
    - `type_choices`: `InProcessInspection.INSPECTION_TYPE_CHOICES`
    - `defect_choices`: `InProcessInspection.DEFECT_CATEGORY_CHOICES`
    - `work_centers`: tenant's `scm.WorkCenter` queryset
    - `total_inspections_count`: int
    - `passed_count`: int
    - `rework_count`: int
    - `rejected_count`: int
  - Search fields: `number`, `title`, `item_code`, `item_name`, `lot_number`, `production_order_number`, `work_center_code`
  - Filters: `status`, `disposition`, `inspection_type`, `defect_category`, `work_center_id` (guarded with `.isdigit()`)
- `in_process_inspection_detail(request, pk)`
  - URL: `in-process-inspections/<int:pk>/` (`quality:in_process_inspection_detail`)
  - Template: `quality/inprocessquality/in_process_inspection/detail.html`
  - Context key: `inspection`
- `in_process_inspection_create(request)`
  - URL: `in-process-inspections/create/` (`quality:in_process_inspection_create`)
  - Template: `quality/inprocessquality/in_process_inspection/form.html`
  - Context key: `form`, `title="New In-Process Inspection"`
- `in_process_inspection_edit(request, pk)`
  - URL: `in-process-inspections/<int:pk>/edit/` (`quality:in_process_inspection_edit`)
  - Template: `quality/inprocessquality/in_process_inspection/form.html`
  - Context key: `form`, `inspection`, `title="Edit In-Process Inspection"`
- `in_process_inspection_delete(request, pk)`
  - URL: `in-process-inspections/<int:pk>/delete/` (`quality:in_process_inspection_delete`)
  - Requires: `@require_POST`, `@tenant_admin_required`
- `in_process_inspection_export_csv(request)`
  - URL: `in-process-inspections/export/csv/` (`quality:in_process_inspection_export_csv`)

### 3.2 `FirstArticleInspections.py`
- `first_article_inspection_list(request)`
  - URL: `first-article-inspections/` (`quality:first_article_inspection_list`)
  - Template: `quality/inprocessquality/first_article_inspection/list.html`
  - Context keys:
    - `page_obj`: paginated `FirstArticleInspection` records
    - `status_choices`: `FirstArticleInspection.STATUS_CHOICES`
    - `fai_type_choices`: `FirstArticleInspection.FAI_TYPE_CHOICES`
    - `setup_reason_choices`: `FirstArticleInspection.SETUP_REASON_CHOICES`
    - `verdict_choices`: `FirstArticleInspection.RELEASE_VERDICT_CHOICES`
    - `work_centers`: tenant's `scm.WorkCenter` queryset
    - `total_fais_count`: int
    - `approved_count`: int
    - `conditional_count`: int
    - `rejected_count`: int
  - Search fields: `number`, `title`, `item_code`, `item_name`, `drawing_number`, `machine_tooling_id`
  - Filters: `status`, `fai_type`, `setup_reason`, `release_verdict`, `work_center_id` (`.isdigit()`)
- `first_article_inspection_detail(request, pk)`
  - URL: `first-article-inspections/<int:pk>/` (`quality:first_article_inspection_detail`)
  - Template: `quality/inprocessquality/first_article_inspection/detail.html`
  - Context key: `fai`
- `first_article_inspection_create(request)`
  - URL: `first-article-inspections/create/` (`quality:first_article_inspection_create`)
  - Template: `quality/inprocessquality/first_article_inspection/form.html`
  - Context key: `form`, `title="New First Article Inspection"`
- `first_article_inspection_edit(request, pk)`
  - URL: `first-article-inspections/<int:pk>/edit/` (`quality:first_article_inspection_edit`)
  - Template: `quality/inprocessquality/first_article_inspection/form.html`
  - Context key: `form`, `fai`, `title="Edit First Article Inspection"`
- `first_article_inspection_delete(request, pk)`
  - URL: `first-article-inspections/<int:pk>/delete/` (`quality:first_article_inspection_delete`)
  - Requires: `@require_POST`, `@tenant_admin_required`
- `first_article_inspection_release(request, pk)`
  - URL: `first-article-inspections/<int:pk>/release/` (`quality:first_article_inspection_release`)
  - Workflow quick action: Releases production run, sets `approved_by=request.user`, `approved_at=now`, `release_verdict="released"`, `status="approved_run_released"`. Requires `@require_POST`.
- `first_article_inspection_export_csv(request)`
  - URL: `first-article-inspections/export/csv/` (`quality:first_article_inspection_export_csv`)

### 3.3 `ProcessParameterLogs.py`
- `process_parameter_log_list(request)`
  - URL: `process-parameter-logs/` (`quality:process_parameter_log_list`)
  - Template: `quality/inprocessquality/process_parameter_log/list.html`
  - Context keys:
    - `page_obj`: paginated `ProcessParameterLog` records
    - `category_choices`: `ProcessParameterLog.PARAMETER_CATEGORY_CHOICES`
    - `excursion_choices`: `ProcessParameterLog.EXCURSION_STATUS_CHOICES`
    - `containment_choices`: `ProcessParameterLog.CONTAINMENT_ACTION_CHOICES`
    - `work_centers`: tenant's `scm.WorkCenter` queryset
    - `total_logs_count`: int
    - `normal_count`: int
    - `out_of_control_count`: int
    - `out_of_spec_count`: int
  - Search fields: `number`, `parameter_name`, `item_code`, `lot_number`, `work_center_code`
  - Filters: `parameter_category`, `excursion_status`, `containment_action`, `work_center_id` (`.isdigit()`)
- `process_parameter_log_detail(request, pk)`
  - URL: `process-parameter-logs/<int:pk>/` (`quality:process_parameter_log_detail`)
  - Template: `quality/inprocessquality/process_parameter_log/detail.html`
  - Context key: `log`
- `process_parameter_log_create(request)`
  - URL: `process-parameter-logs/create/` (`quality:process_parameter_log_create`)
  - Template: `quality/inprocessquality/process_parameter_log/form.html`
  - Context key: `form`, `title="Log Process Parameter"`
- `process_parameter_log_edit(request, pk)`
  - URL: `process-parameter-logs/<int:pk>/edit/` (`quality:process_parameter_log_edit`)
  - Template: `quality/inprocessquality/process_parameter_log/form.html`
  - Context key: `form`, `log`, `title="Edit Process Parameter Log"`
- `process_parameter_log_delete(request, pk)`
  - URL: `process-parameter-logs/<int:pk>/delete/` (`quality:process_parameter_log_delete`)
  - Requires: `@require_POST`, `@tenant_admin_required`
- `process_parameter_log_export_csv(request)`
  - URL: `process-parameter-logs/export/csv/` (`quality:process_parameter_log_export_csv`)

### 3.4 `LayeredProcessAudits.py`
- `layered_process_audit_list(request)`
  - URL: `layered-process-audits/` (`quality:layered_process_audit_list`)
  - Template: `quality/inprocessquality/layered_process_audit/list.html`
  - Context keys:
    - `page_obj`: paginated `LayeredProcessAudit` records
    - `layer_choices`: `LayeredProcessAudit.AUDIT_LAYER_CHOICES`
    - `focus_choices`: `LayeredProcessAudit.FOCUS_AREA_CHOICES`
    - `status_choices`: `LayeredProcessAudit.STATUS_CHOICES`
    - `work_centers`: tenant's `scm.WorkCenter` queryset
    - `total_audits_count`: int
    - `avg_compliance_rate`: float/Decimal
    - `completed_count`: int
    - `scheduled_count`: int
  - Search fields: `number`, `title`, `work_center_code`, `findings_summary`
  - Filters: `audit_layer`, `focus_area`, `status`, `work_center_id` (`.isdigit()`)
- `layered_process_audit_detail(request, pk)`
  - URL: `layered-process-audits/<int:pk>/` (`quality:layered_process_audit_detail`)
  - Template: `quality/inprocessquality/layered_process_audit/detail.html`
  - Context key: `lpa`
- `layered_process_audit_create(request)`
  - URL: `layered-process-audits/create/` (`quality:layered_process_audit_create`)
  - Template: `quality/inprocessquality/layered_process_audit/form.html`
  - Context key: `form`, `title="Schedule Layered Process Audit"`
- `layered_process_audit_edit(request, pk)`
  - URL: `layered-process-audits/<int:pk>/edit/` (`quality:layered_process_audit_edit`)
  - Template: `quality/inprocessquality/layered_process_audit/form.html`
  - Context key: `form`, `lpa`, `title="Edit Layered Process Audit"`
- `layered_process_audit_delete(request, pk)`
  - URL: `layered-process-audits/<int:pk>/delete/` (`quality:layered_process_audit_delete`)
  - Requires: `@require_POST`, `@tenant_admin_required`
- `layered_process_audit_export_csv(request)`
  - URL: `layered-process-audits/export/csv/` (`quality:layered_process_audit_export_csv`)

### 3.5 `SpcDashboard.py`
- `spc_dashboard(request)`
  - URL: `spc-dashboard/` (`quality:spc_dashboard`)
  - Template: `quality/inprocessquality/spc_dashboard.html`
  - Context keys:
    - `total_inspections`: int
    - `fai_pending_release_count`: int
    - `active_ooc_oos_count`: int
    - `avg_lpa_compliance`: float/Decimal
    - `recent_inspections`: queryset of last 5 `InProcessInspection`
    - `recent_fais`: queryset of last 5 `FirstArticleInspection`
    - `recent_excursions`: queryset of last 5 `ProcessParameterLog` with `excursion_status in ["out_of_control", "out_of_spec"]`
    - `recent_lpas`: queryset of last 5 `LayeredProcessAudit`

---

## 4. URLconf Contract (`apps/quality/urls/InProcessQuality/`)

Concatenated in `apps/quality/urls/__init__.py`. Literals precede parameter routes.
- `in_process_inspection_list`: `in-process-inspections/`
- `in_process_inspection_create`: `in-process-inspections/create/`
- `in_process_inspection_export_csv`: `in-process-inspections/export/csv/`
- `in_process_inspection_detail`: `in-process-inspections/<int:pk>/`
- `in_process_inspection_edit`: `in-process-inspections/<int:pk>/edit/`
- `in_process_inspection_delete`: `in-process-inspections/<int:pk>/delete/`

- `first_article_inspection_list`: `first-article-inspections/`
- `first_article_inspection_create`: `first-article-inspections/create/`
- `first_article_inspection_export_csv`: `first-article-inspections/export/csv/`
- `first_article_inspection_detail`: `first-article-inspections/<int:pk>/`
- `first_article_inspection_edit`: `first-article-inspections/<int:pk>/edit/`
- `first_article_inspection_delete`: `first-article-inspections/<int:pk>/delete/`
- `first_article_inspection_release`: `first-article-inspections/<int:pk>/release/`

- `process_parameter_log_list`: `process-parameter-logs/`
- `process_parameter_log_create`: `process-parameter-logs/create/`
- `process_parameter_log_export_csv`: `process-parameter-logs/export/csv/`
- `process_parameter_log_detail`: `process-parameter-logs/<int:pk>/`
- `process_parameter_log_edit`: `process-parameter-logs/<int:pk>/edit/`
- `process_parameter_log_delete`: `process-parameter-logs/<int:pk>/delete/`

- `layered_process_audit_list`: `layered-process-audits/`
- `layered_process_audit_create`: `layered-process-audits/create/`
- `layered_process_audit_export_csv`: `layered-process-audits/export/csv/`
- `layered_process_audit_detail`: `layered-process-audits/<int:pk>/`
- `layered_process_audit_edit`: `layered-process-audits/<int:pk>/edit/`
- `layered_process_audit_delete`: `layered-process-audits/<int:pk>/delete/`

- `spc_dashboard`: `spc-dashboard/`

---

## 5. Navigation Contract (`LIVE_LINKS["12.8"]` in `apps/core/navigation.py`)

Mapped exact NavERP.md bullet text:
```python
"12.8": {
    "Process Parameter Monitoring": "quality:process_parameter_log_list",
    "First Article Inspection (FAI)": "quality:first_article_inspection_list",
    "In-Line Inspection & Testing": "quality:in_process_inspection_list",
    "Work Instruction Adherence": "quality:spc_dashboard",
    "Process Audit & Layered Process Audits (LPA)": "quality:layered_process_audit_list",
},
```
