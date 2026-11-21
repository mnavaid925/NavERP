# Module 12.15 Pre-Build Contract — Process Validation & Verification (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.15"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0027_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/ProcessValidation/`
  - `apps/quality/forms/ProcessValidation/`
  - `apps/quality/views/ProcessValidation/`
  - `apps/quality/urls/ProcessValidation/`
  - `templates/quality/processvalidation/{validation_protocol,process_capability_study,computer_system_validation,cleaning_validation}/{list,detail,form}.html` + `templates/quality/processvalidation/process_validation_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"approve"`, `"execute"`, `"complete"`, `"review"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `quality.ControlledDocument`, `quality.DocumentChangeOrder`, `quality.ProcessDeviation`, `quality.CapaInvestigation`, `quality.RiskAssessment`, `quality.CalibrationGage`, `quality.ProcessParameterLog`, `quality.ValidationProtocol`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/ProcessValidation/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `ValidationProtocol` (`ValidationProtocols.py`)
- **`NUMBER_PREFIX`**: `"QVAL"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Validation Protocol"` / `"Validation Protocols"`
- **Choices & Badge Maps**:
  - `STAGE_CHOICES` (`max_length=24`):
    - `("dq", "Design Qualification (DQ)")`
    - `("iq", "Installation Qualification (IQ)")`
    - `("oq", "Operational Qualification (OQ)")`
    - `("pq", "Performance Qualification (PQ)")`
    - `("ppq", "Process Performance Qualification (PPQ)")`
    - `("cpv", "Continued Process Verification (CPV)")`
    - `("revalidation", "Periodic / Change Revalidation")`
  - `TARGET_TYPE_CHOICES` (`max_length=30`):
    - `("equipment", "Manufacturing / Lab Equipment")`
    - `("process", "Manufacturing / Assembly Process")`
    - `("facility_utility", "Facility Cleanroom & Utility System")`
    - `("cleaning_procedure", "Equipment Cleaning Procedure")`
    - `("computerized_system", "Computerized System / Software")`
  - `STATUS_CHOICES` (`max_length=32`):
    - `("draft", "Draft Protocol")`
    - `("in_review", "Under Technical Review")`
    - `("approved_for_execution", "Approved for Execution")`
    - `("in_execution", "Active Execution in Progress")`
    - `("deviation_hold", "Execution on Hold (Deviation)")`
    - `("execution_completed", "Execution Testing Completed")`
    - `("final_approved", "Final Approved & Released")`
    - `("rejected", "Protocol Rejected")`
    - `("superseded", "Superseded by New Protocol")`
  - `REVALIDATION_TRIGGER_CHOICES` (`max_length=25`):
    - `("initial", "Initial Validation")`
    - `("periodic_review", "Scheduled Periodic Review")`
    - `("change_control", "Engineering / Process Change (DCO)")`
    - `("deviation", "CAPA / OOS Deviation Resolution")`
    - `("regulatory", "Regulatory Mandate / Inspection")`
  - `STAGE_CSS`:
    - `"dq": "badge-slate"`
    - `"iq": "badge-info"`
    - `"oq": "badge-info"`
    - `"pq": "badge-purple"` -> note: theme has badge-info, badge-green, badge-red, badge-amber, badge-muted, badge-slate. Map to:
    - `"dq": "badge-slate"`
    - `"iq": "badge-info"`
    - `"oq": "badge-info"`
    - `"pq": "badge-info"`
    - `"ppq": "badge-amber"`
    - `"cpv": "badge-green"`
    - `"revalidation": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-muted"`
    - `"in_review": "badge-info"`
    - `"approved_for_execution": "badge-info"`
    - `"in_execution": "badge-amber"`
    - `"deviation_hold": "badge-red"`
    - `"execution_completed": "badge-info"`
    - `"final_approved": "badge-green"`
    - `"rejected": "badge-red"`
    - `"superseded": "badge-slate"`
- **Model Fields**:
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField(blank=True)`
  - `protocol_stage`: `CharField(max_length=24, choices=STAGE_CHOICES, default="iq", db_index=True)`
  - `target_type`: `CharField(max_length=30, choices=TARGET_TYPE_CHOICES, default="equipment", db_index=True)`
  - `status`: `CharField(max_length=32, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `revalidation_trigger`: `CharField(max_length=25, choices=REVALIDATION_TRIGGER_CHOICES, default="initial", db_index=True)`
  - `equipment_tag`: `CharField(max_length=100, blank=True)`
  - `process_name`: `CharField(max_length=150, blank=True)`
  - `facility_area`: `CharField(max_length=150, blank=True)`
  - `item_code`: `CharField(max_length=100, blank=True)`
  - `target_completion_date`: `DateField(null=True, blank=True)`
  - `actual_completion_date`: `DateField(null=True, blank=True)`
  - `revalidation_due_date`: `DateField(null=True, blank=True, db_index=True)`
  - `test_runs_planned`: `PositiveIntegerField(default=3)`
  - `test_runs_completed`: `PositiveIntegerField(default=0)`
  - `acceptance_criteria`: `TextField(blank=True)`
  - `summary_conclusions`: `TextField(blank=True)`
  - `deviations_encountered`: `PositiveIntegerField(default=0)`
  - `critical_parameters_verified`: `BooleanField(default=False)`
- **Foreign Keys**:
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="validation_protocols")`
  - `lead_author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_validation_protocols")`
  - `qa_reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviewed_validation_protocols")`
  - `final_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_validation_protocols")`
  - `governing_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="validation_protocols")`
  - `triggering_change`: `ForeignKey("quality.DocumentChangeOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_validation_protocols")`
  - `calibration_gage`: `ForeignKey("quality.CalibrationGage", on_delete=models.SET_NULL, null=True, blank=True, related_name="validation_protocols")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qval_ten_num_uniq")` (25 chars)
  - `Index(fields=["tenant", "status"], name="idx_qval_ten_status")` (19 chars)
  - `Index(fields=["tenant", "protocol_stage"], name="idx_qval_ten_stage")` (18 chars)
  - `Index(fields=["tenant", "target_type"], name="idx_qval_ten_target")` (19 chars)
  - `Index(fields=["tenant", "revalidation_due_date"], name="idx_qval_ten_reval_due")` (22 chars)
- **Properties**:
  - `@property is_overdue`: `bool` — True if `target_completion_date < date.today() and status not in ("final_approved", "rejected", "superseded")`
  - `@property is_revalidation_overdue`: `bool` — True if `revalidation_due_date and revalidation_due_date < date.today()`
  - `@property progress_percentage`: `int` — clamped 0..100 based on test runs completed / planned
  - `@property status_css`: returns mapped CSS badge class
  - `@property stage_css`: returns mapped CSS badge class

---

### 1.2 `ProcessCapabilityStudy` (`ProcessCapabilityStudies.py`)
- **`NUMBER_PREFIX`**: `"QCPK"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Process Capability Study"` / `"Process Capability Studies"`
- **Choices & Badge Maps**:
  - `PARAMETER_CATEGORY_CHOICES` (`max_length=30`):
    - `("dimensional_thickness", "Dimensional / Thickness / Diameter")`
    - `("temperature", "Temperature / Thermal Cycle")`
    - `("pressure", "Pressure / Vacuum Seal")`
    - `("speed_feed", "Speed / Flow / Feed Rate")`
    - `("torque", "Torque / Force Tension")`
    - `("ph_chemical", "pH / Conductivity / Concentration")`
    - `("humidity", "Relative Humidity / Moisture")`
    - `("voltage_current", "Voltage / Current / Resistance")`
    - `("cycle_time", "Cycle Time / Dwell Duration")`
    - `("weight_mass", "Fill Weight / Mass / Density")`
    - `("other", "Other Critical Parameter")`
  - `CAPABILITY_DETERMINATION_CHOICES` (`max_length=25`):
    - `("highly_capable", "Highly Capable (Cpk >= 1.67)")`
    - `("capable", "Capable (1.33 <= Cpk < 1.67)")`
    - `("marginally_capable", "Marginally Capable (1.00 <= Cpk < 1.33)")`
    - `("incapable", "Incapable / Action Required (Cpk < 1.00)")`
    - `("undetermined", "Undetermined / Incomplete Data")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("draft", "Draft Study")`
    - `("data_collection", "Data Collection in Progress")`
    - `("analyzed", "Statistical Analysis Completed")`
    - `("approved", "Capability Study Approved")`
    - `("action_required", "CAPA / Engineering Action Required")`
  - `DETERMINATION_CSS`:
    - `"highly_capable": "badge-green"`
    - `"capable": "badge-info"`
    - `"marginally_capable": "badge-amber"`
    - `"incapable": "badge-red"`
    - `"undetermined": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-muted"`
    - `"data_collection": "badge-info"`
    - `"analyzed": "badge-amber"`
    - `"approved": "badge-green"`
    - `"action_required": "badge-red"`
- **Model Fields**:
  - `title`: `CharField(max_length=255)`
  - `parameter_name`: `CharField(max_length=150)`
  - `parameter_category`: `CharField(max_length=30, choices=PARAMETER_CATEGORY_CHOICES, default="dimensional_thickness", db_index=True)`
  - `unit_of_measure`: `CharField(max_length=50, default="mm")`
  - `upper_spec_limit`: `DecimalField(max_digits=12, decimal_places=4)`
  - `lower_spec_limit`: `DecimalField(max_digits=12, decimal_places=4)`
  - `target_nominal`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `subgroup_size`: `PositiveIntegerField(default=5)`
  - `number_of_subgroups`: `PositiveIntegerField(default=25)`
  - `total_samples`: `PositiveIntegerField(default=125)`
  - `mean_value`: `DecimalField(max_digits=12, decimal_places=4)`
  - `within_subgroup_stdev`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `overall_stdev`: `DecimalField(max_digits=12, decimal_places=4)`
  - `cp_index`: `DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)`
  - `cpk_index`: `DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)`
  - `pp_index`: `DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)`
  - `ppk_index`: `DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)`
  - `expected_ppm`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
  - `is_normally_distributed`: `BooleanField(default=True)`
  - `capability_determination`: `CharField(max_length=25, choices=CAPABILITY_DETERMINATION_CHOICES, default="undetermined", db_index=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `process_name`: `CharField(max_length=150, blank=True)`
  - `equipment_tag`: `CharField(max_length=100, blank=True)`
  - `item_code`: `CharField(max_length=100, blank=True)`
  - `lot_number`: `CharField(max_length=100, blank=True)`
  - `analysis_summary`: `TextField(blank=True)`
  - `study_date`: `DateField(null=True, blank=True)`
- **Foreign Keys**:
  - `validation_protocol`: `ForeignKey("quality.ValidationProtocol", on_delete=models.SET_NULL, null=True, blank=True, related_name="capability_studies")`
  - `investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="capability_studies")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_capability_studies")`
  - `linked_parameter_log`: `ForeignKey("quality.ProcessParameterLog", on_delete=models.SET_NULL, null=True, blank=True, related_name="capability_studies")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcpk_ten_num_uniq")` (25 chars)
  - `Index(fields=["tenant", "status"], name="idx_qcpk_ten_status")` (19 chars)
  - `Index(fields=["tenant", "capability_determination"], name="idx_qcpk_ten_determ")` (19 chars)
  - `Index(fields=["tenant", "parameter_category"], name="idx_qcpk_ten_param_cat")` (22 chars)
- **Properties & Calculation Methods**:
  - `@property tolerance_width`: `Decimal(upper_spec_limit - lower_spec_limit)`
  - `@property status_css`: returns mapped CSS badge class
  - `@property determination_css`: returns mapped CSS badge class
  - `calculate_indices()`: Recalculates `cp_index`, `cpk_index`, `pp_index`, `ppk_index`, and sets `capability_determination`.

---

### 1.3 `ComputerSystemValidation` (`ComputerSystemValidations.py`)
- **`NUMBER_PREFIX`**: `"QCSV"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Computer System Validation"` / `"Computer System Validations"`
- **Choices & Badge Maps**:
  - `GAMP_CATEGORY_CHOICES` (`max_length=28`):
    - `("cat_1_infrastructure", "Category 1: Infrastructure Software (OS, DB, Network)")`
    - `("cat_3_non_configured", "Category 3: Non-Configured Software (Commercial COTS)")`
    - `("cat_4_configured", "Category 4: Configured Software (Standard LIMS/QMS/ERP)")`
    - `("cat_5_custom", "Category 5: Custom Built Software / Bespoke Scripts")`
  - `GXP_IMPACT_CHOICES` (`max_length=20`):
    - `("direct_gxp", "Direct GxP Impact")`
    - `("indirect_gxp", "Indirect GxP Impact")`
    - `("non_gxp", "Non-GxP / Business Only")`
  - `VALIDATION_APPROACH_CHOICES` (`max_length=25`):
    - `("traditional_csv", "Traditional CSV (Rigorous Scripted Testing)")`
    - `("csa_risk_based", "FDA CSA (Risk-Based & Unscripted Testing)")`
  - `HOSTING_MODEL_CHOICES` (`max_length=25`):
    - `("cloud_saas", "Cloud SaaS (Multi-Tenant)")`
    - `("cloud_dedicated", "Cloud Dedicated / Private Cloud")`
    - `("on_premises", "On-Premises Bare Metal / VM")`
    - `("hybrid", "Hybrid Architecture")`
    - `("embedded_firmware", "Embedded Instrument Firmware")`
  - `TRACEABILITY_STATUS_CHOICES` (`max_length=25`):
    - `("not_started", "Traceability Not Started")`
    - `("drafting", "Matrix In Progress")`
    - `("matrix_verified", "Traceability Matrix Verified (100%)")`
    - `("gaps_identified", "Traceability Gaps Flagged")`
  - `STATUS_CHOICES` (`max_length=28`):
    - `("inventory_only", "System Inventory Registered")`
    - `("planning", "Validation Plan Approved")`
    - `("in_qualification", "Qualification Testing Active")`
    - `("validated_live", "Validated for Live GxP Use")`
    - `("periodic_review_due", "Periodic Review Overdue")`
    - `("decommissioned", "Decommissioned / Retired")`
  - `GAMP_CSS`:
    - `"cat_1_infrastructure": "badge-slate"`
    - `"cat_3_non_configured": "badge-info"`
    - `"cat_4_configured": "badge-green"`
    - `"cat_5_custom": "badge-amber"`
  - `STATUS_CSS`:
    - `"inventory_only": "badge-slate"`
    - `"planning": "badge-info"`
    - `"in_qualification": "badge-amber"`
    - `"validated_live": "badge-green"`
    - `"periodic_review_due": "badge-red"`
    - `"decommissioned": "badge-muted"`
- **Model Fields**:
  - `system_name`: `CharField(max_length=200)`
  - `version_release`: `CharField(max_length=50)`
  - `vendor_name`: `CharField(max_length=150)`
  - `gamp_category`: `CharField(max_length=28, choices=GAMP_CATEGORY_CHOICES, default="cat_4_configured", db_index=True)`
  - `gxp_impact`: `CharField(max_length=20, choices=GXP_IMPACT_CHOICES, default="direct_gxp", db_index=True)`
  - `validation_approach`: `CharField(max_length=25, choices=VALIDATION_APPROACH_CHOICES, default="csa_risk_based")`
  - `hosting_model`: `CharField(max_length=25, choices=HOSTING_MODEL_CHOICES, default="cloud_saas")`
  - `is_part_11_compliant`: `BooleanField(default=True)`
  - `requires_audit_trail`: `BooleanField(default=True)`
  - `has_disaster_recovery_plan`: `BooleanField(default=True)`
  - `traceability_status`: `CharField(max_length=25, choices=TRACEABILITY_STATUS_CHOICES, default="not_started")`
  - `urs_requirements_count`: `PositiveIntegerField(default=0)`
  - `test_scripts_count`: `PositiveIntegerField(default=0)`
  - `deviations_found_count`: `PositiveIntegerField(default=0)`
  - `status`: `CharField(max_length=28, choices=STATUS_CHOICES, default="inventory_only", db_index=True)`
  - `validated_date`: `DateField(null=True, blank=True)`
  - `periodic_review_frequency_months`: `PositiveIntegerField(default=24)`
  - `last_review_date`: `DateField(null=True, blank=True)`
  - `next_review_due`: `DateField(null=True, blank=True, db_index=True)`
  - `description`: `TextField(blank=True)`
- **Foreign Keys**:
  - `system_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_computer_systems")`
  - `quality_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="qa_computer_systems")`
  - `validation_protocol`: `ForeignKey("quality.ValidationProtocol", on_delete=models.SET_NULL, null=True, blank=True, related_name="computer_system_validations")`
  - `urs_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="csv_urs_docs")`
  - `vsr_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="csv_vsr_docs")`
  - `risk_assessment`: `ForeignKey("quality.RiskAssessment", on_delete=models.SET_NULL, null=True, blank=True, related_name="computer_system_validations")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcsv_ten_num_uniq")` (25 chars)
  - `Index(fields=["tenant", "status"], name="idx_qcsv_ten_status")` (19 chars)
  - `Index(fields=["tenant", "gamp_category"], name="idx_qcsv_ten_gamp")` (17 chars)
  - `Index(fields=["tenant", "next_review_due"], name="idx_qcsv_ten_review_due")` (23 chars)
- **Properties**:
  - `@property is_review_overdue`: `bool` — True if `next_review_due and next_review_due < date.today()`
  - `@property status_css`: returns mapped CSS badge class
  - `@property gamp_css`: returns mapped CSS badge class

---

### 1.4 `CleaningValidation` (`CleaningValidations.py`)
- **`NUMBER_PREFIX`**: `"QCLN"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Cleaning Validation"` / `"Cleaning Validations"`
- **Choices & Badge Maps**:
  - `WORST_CASE_RATIONALE_CHOICES` (`max_length=28`):
    - `("lowest_solubility", "Lowest Solubility in Cleaning Solvent")`
    - `("highest_toxicity_pde", "Highest Toxicity / Lowest PDE Limit")`
    - `("highest_potency", "Highest Therapeutic Potency")`
    - `("hardest_to_clean", "Physical Hardness / Residue Tenacity")`
  - `CALCULATION_BASIS_CHOICES` (`max_length=25`):
    - `("therapeutic_dose", "1/1000th Minimum Therapeutic Dose")`
    - `("ten_ppm_limit", "10 ppm General Default Limit")`
    - `("toxicological_pde", "Health-Based Toxicological PDE/ADE")`
    - `("most_stringent", "Most Stringent (Safety Envelope)")`
  - `ANALYTICAL_METHOD_CHOICES` (`max_length=20`):
    - `("hplc", "HPLC / UPLC UV Specific Assay")`
    - `("toc", "Total Organic Carbon (TOC)")`
    - `("uv_vis", "UV-Vis Spectrophotometry")`
    - `("conductivity", "Conductivity Verification")`
    - `("visual_clean", "Visual Cleanliness Inspection")`
  - `CLEANING_STATUS_CHOICES` (`max_length=28`):
    - `("draft", "Draft Study Protocol")`
    - `("protocol_approved", "Protocol Approved for Execution")`
    - `("sampling_in_progress", "Swab / Rinse Sampling Active")`
    - `("analytical_testing", "Analytical Lab Testing in Progress")`
    - `("validated_pass", "Cleaning Validated (Passed)")`
    - `("failed_recleaning", "Failed (Recleaning Required)")`
    - `("expired", "Revalidation Cycle Expired")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"protocol_approved": "badge-info"`
    - `"sampling_in_progress": "badge-amber"`
    - `"analytical_testing": "badge-amber"`
    - `"validated_pass": "badge-green"`
    - `"failed_recleaning": "badge-red"`
    - `"expired": "badge-muted"`
- **Model Fields**:
  - `title`: `CharField(max_length=255)`
  - `equipment_train_tag`: `CharField(max_length=150)`
  - `target_residue`: `CharField(max_length=150)`
  - `cleaning_agent_used`: `CharField(max_length=150)`
  - `worst_case_rationale`: `CharField(max_length=28, choices=WORST_CASE_RATIONALE_CHOICES, default="highest_potency")`
  - `calculation_basis`: `CharField(max_length=25, choices=CALCULATION_BASIS_CHOICES, default="most_stringent")`
  - `min_daily_dose_active_mg`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `max_daily_dose_subsequent_mg`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `smallest_batch_size_kg`: `DecimalField(max_digits=12, decimal_places=3)`
  - `safety_factor`: `DecimalField(max_digits=8, decimal_places=1, default=Decimal("1000.0"))`
  - `toxicological_pde_mg_day`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `calculated_maco_mg`: `DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)`
  - `total_surface_area_sqcm`: `DecimalField(max_digits=14, decimal_places=2)`
  - `swab_sampling_area_sqcm`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal("25.0"))`
  - `calculated_swab_limit_ug`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `rinse_volume_liters`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
  - `calculated_rinse_limit_ppm`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `analytical_method`: `CharField(max_length=20, choices=ANALYTICAL_METHOD_CHOICES, default="hplc")`
  - `method_recovery_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("80.00"))`
  - `dirty_hold_time_hours`: `DecimalField(max_digits=8, decimal_places=1)`
  - `clean_hold_time_hours`: `DecimalField(max_digits=8, decimal_places=1)`
  - `consecutive_successful_runs`: `PositiveIntegerField(default=0)`
  - `is_visually_clean`: `BooleanField(default=True)`
  - `worst_swab_result_ug`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `worst_rinse_result_ppm`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `cleaning_status`: `CharField(max_length=28, choices=CLEANING_STATUS_CHOICES, default="draft", db_index=True)`
  - `next_revalidation_date`: `DateField(null=True, blank=True, db_index=True)`
  - `notes`: `TextField(blank=True)`
- **Foreign Keys**:
  - `validation_protocol`: `ForeignKey("quality.ValidationProtocol", on_delete=models.SET_NULL, null=True, blank=True, related_name="cleaning_studies")`
  - `cleaning_sop`: `ForeignKey("quality.ControlledDocument", on_delete=models.PROTECT, related_name="cleaning_validation_studies")`
  - `analytical_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cleaning_studies")`
  - `qa_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_cleaning_studies")`
  - `linked_deviation`: `ForeignKey("quality.ProcessDeviation", on_delete=models.SET_NULL, null=True, blank=True, related_name="cleaning_studies")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcln_ten_num_uniq")` (25 chars)
  - `Index(fields=["tenant", "cleaning_status"], name="idx_qcln_ten_status")` (19 chars)
  - `Index(fields=["tenant", "next_revalidation_date"], name="idx_qcln_ten_reval_due")` (22 chars)
- **Properties & Calculation Methods**:
  - `@property is_revalidation_overdue`: `bool` — True if `next_revalidation_date and next_revalidation_date < date.today()`
  - `@property status_css`: returns mapped CSS badge class
  - `calculate_limits()`: Computes `calculated_maco_mg`, `calculated_swab_limit_ug`, and `calculated_rinse_limit_ppm`.

---

## 2. Forms Contract (`apps/quality/forms/ProcessValidation/`)

All forms inherit `TenantModelForm` (which scopes FKs in `__init__` and handles multi-tenancy).

### Form Exclusions:
- **`ValidationProtocolForm`**:
  - Excluded from `Meta.fields`: `["tenant", "number", "created_at", "updated_at"]`
- **`ProcessCapabilityStudyForm`**:
  - Excluded from `Meta.fields`: `["tenant", "number", "cp_index", "cpk_index", "pp_index", "ppk_index", "expected_ppm", "capability_determination", "created_at", "updated_at"]` (calculated automatically in `save()` / view)
- **`ComputerSystemValidationForm`**:
  - Excluded from `Meta.fields`: `["tenant", "number", "created_at", "updated_at"]`
- **`CleaningValidationForm`**:
  - Excluded from `Meta.fields`: `["tenant", "number", "calculated_maco_mg", "calculated_swab_limit_ug", "calculated_rinse_limit_ppm", "created_at", "updated_at"]` (calculated automatically in `save()` / view)

---

## 3. URLs Contract (`apps/quality/urls/ProcessValidation/`)

All URLs are registered in `apps/quality/urls/__init__.py`. Literal patterns placed before `<int:pk>` patterns.

| Pattern | View Function | Route Name |
|---|---|---|
| `validation/protocols/` | `validation_protocol_list` | `quality:validation_protocol_list` |
| `validation/protocols/create/` | `validation_protocol_create` | `quality:validation_protocol_create` |
| `validation/protocols/export/` | `validation_protocol_export` | `quality:validation_protocol_export` |
| `validation/protocols/<int:pk>/` | `validation_protocol_detail` | `quality:validation_protocol_detail` |
| `validation/protocols/<int:pk>/edit/` | `validation_protocol_edit` | `quality:validation_protocol_edit` |
| `validation/protocols/<int:pk>/delete/` | `validation_protocol_delete` | `quality:validation_protocol_delete` |
| `validation/capability-studies/` | `process_capability_study_list` | `quality:process_capability_study_list` |
| `validation/capability-studies/create/` | `process_capability_study_create` | `quality:process_capability_study_create` |
| `validation/capability-studies/export/` | `process_capability_study_export` | `quality:process_capability_study_export` |
| `validation/capability-studies/<int:pk>/` | `process_capability_study_detail` | `quality:process_capability_study_detail` |
| `validation/capability-studies/<int:pk>/edit/` | `process_capability_study_edit` | `quality:process_capability_study_edit` |
| `validation/capability-studies/<int:pk>/delete/` | `process_capability_study_delete` | `quality:process_capability_study_delete` |
| `validation/computer-systems/` | `computer_system_validation_list` | `quality:computer_system_validation_list` |
| `validation/computer-systems/create/` | `computer_system_validation_create` | `quality:computer_system_validation_create` |
| `validation/computer-systems/export/` | `computer_system_validation_export` | `quality:computer_system_validation_export` |
| `validation/computer-systems/<int:pk>/` | `computer_system_validation_detail` | `quality:computer_system_validation_detail` |
| `validation/computer-systems/<int:pk>/edit/` | `computer_system_validation_edit` | `quality:computer_system_validation_edit` |
| `validation/computer-systems/<int:pk>/delete/` | `computer_system_validation_delete` | `quality:computer_system_validation_delete` |
| `validation/cleaning/` | `cleaning_validation_list` | `quality:cleaning_validation_list` |
| `validation/cleaning/create/` | `cleaning_validation_create` | `quality:cleaning_validation_create` |
| `validation/cleaning/export/` | `cleaning_validation_export` | `quality:cleaning_validation_export` |
| `validation/cleaning/<int:pk>/` | `cleaning_validation_detail` | `quality:cleaning_validation_detail` |
| `validation/cleaning/<int:pk>/edit/` | `cleaning_validation_edit` | `quality:cleaning_validation_edit` |
| `validation/cleaning/<int:pk>/delete/` | `cleaning_validation_delete` | `quality:cleaning_validation_delete` |
| `validation/dashboard/` | `process_validation_dashboard` | `quality:process_validation_dashboard` |

---

## 4. View Context Keys Contract

### 4.1 `ValidationProtocol`
- **`validation_protocol_list`**:
  - `page_obj`: paginated slice of protocols
  - `validation_protocols`: alias for `page_obj`
  - `total_count`: total filtered protocols count
  - `stage_choices`: `ValidationProtocol.STAGE_CHOICES`
  - `status_choices`: `ValidationProtocol.STATUS_CHOICES`
  - `target_type_choices`: `ValidationProtocol.TARGET_TYPE_CHOICES`
  - `revalidation_trigger_choices`: `ValidationProtocol.REVALIDATION_TRIGGER_CHOICES`
  - `search_query`: `request.GET.get('q', '').strip()`
- **`validation_protocol_detail`**:
  - `validation_protocol`: object instance
  - `is_detail`: `True`
- **`validation_protocol_form` (create/edit)**:
  - `form`: bound or unbound form instance
  - `is_edit`: `bool`
  - `validation_protocol`: object instance (edit mode) or `None` (create mode)

### 4.2 `ProcessCapabilityStudy`
- **`process_capability_study_list`**:
  - `page_obj`: paginated slice
  - `capability_studies`: alias for `page_obj`
  - `total_count`: total count
  - `status_choices`: `ProcessCapabilityStudy.STATUS_CHOICES`
  - `determination_choices`: `ProcessCapabilityStudy.CAPABILITY_DETERMINATION_CHOICES`
  - `category_choices`: `ProcessCapabilityStudy.PARAMETER_CATEGORY_CHOICES`
  - `search_query`: `request.GET.get('q', '').strip()`
- **`process_capability_study_detail`**:
  - `capability_study`: object instance
  - `is_detail`: `True`
- **`process_capability_study_form` (create/edit)**:
  - `form`: bound or unbound form instance
  - `is_edit`: `bool`
  - `capability_study`: object instance (edit mode) or `None` (create mode)

### 4.3 `ComputerSystemValidation`
- **`computer_system_validation_list`**:
  - `page_obj`: paginated slice
  - `computer_systems`: alias for `page_obj`
  - `total_count`: total count
  - `gamp_choices`: `ComputerSystemValidation.GAMP_CATEGORY_CHOICES`
  - `gxp_choices`: `ComputerSystemValidation.GXP_IMPACT_CHOICES`
  - `status_choices`: `ComputerSystemValidation.STATUS_CHOICES`
  - `approach_choices`: `ComputerSystemValidation.VALIDATION_APPROACH_CHOICES`
  - `search_query`: `request.GET.get('q', '').strip()`
- **`computer_system_validation_detail`**:
  - `computer_system`: object instance
  - `is_detail`: `True`
- **`computer_system_validation_form` (create/edit)**:
  - `form`: bound or unbound form instance
  - `is_edit`: `bool`
  - `computer_system`: object instance (edit mode) or `None` (create mode)

### 4.4 `CleaningValidation`
- **`cleaning_validation_list`**:
  - `page_obj`: paginated slice
  - `cleaning_validations`: alias for `page_obj`
  - `total_count`: total count
  - `status_choices`: `CleaningValidation.CLEANING_STATUS_CHOICES`
  - `method_choices`: `CleaningValidation.ANALYTICAL_METHOD_CHOICES`
  - `basis_choices`: `CleaningValidation.CALCULATION_BASIS_CHOICES`
  - `search_query`: `request.GET.get('q', '').strip()`
- **`cleaning_validation_detail`**:
  - `cleaning_validation`: object instance
  - `is_detail`: `True`
- **`cleaning_validation_form` (create/edit)**:
  - `form`: bound or unbound form instance
  - `is_edit`: `bool`
  - `cleaning_validation`: object instance (edit mode) or `None` (create mode)

### 4.5 `ProcessValidationDashboard`
- **`process_validation_dashboard`**:
  - `total_protocols`: count of validation protocols
  - `active_protocols`: protocols in review or execution
  - `total_studies`: count of capability studies
  - `capable_studies`: studies with Cpk >= 1.33
  - `total_systems`: count of computer systems
  - `validated_systems`: systems validated for live GxP use
  - `total_cleaning`: count of cleaning studies
  - `validated_cleaning`: cleaning studies passed
  - `overdue_revalidations`: protocols or cleaning studies with past-due revalidation dates
  - `recent_protocols`: latest 5 protocols
  - `recent_studies`: latest 5 capability studies
  - `recent_systems`: latest 5 computer systems
  - `recent_cleaning`: latest 5 cleaning validation records

---

## 5. Navigation Wiring (`LIVE_LINKS["12.15"]`)

```python
    "12.15": {
        "Process Validation Planning (IQ/OQ/PQ)": "quality:validation_protocol_list",
        "Process Capability Studies (Cp/Cpk)": "quality:process_capability_study_list",
        "Computer System Validation (CSV)": "quality:computer_system_validation_list",
        "Cleaning Validation": "quality:cleaning_validation_list",
        "Revalidation & Periodic Review": "quality:process_validation_dashboard",
    },
```
