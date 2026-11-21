# Module 12.16 Pre-Build Contract — Environmental, Health & Safety (EHS) (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.16"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0027_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/EhsManagement/`
  - `apps/quality/forms/EhsManagement/`
  - `apps/quality/views/EhsManagement/`
  - `apps/quality/urls/EhsManagement/`
  - `templates/quality/ehsmanagement/{hazardous_material,safety_incident,environmental_monitoring_log,waste_disposal_manifest}/{list,detail,form}.html` + `templates/quality/ehsmanagement/ehs_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"certify"`, `"investigate"`, `"evaluate"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `core.Party`, `quality.ControlledDocument`, `quality.CalibrationGage`, `quality.CapaInvestigation`, `quality.NonConformanceReport`, `quality.ProcessDeviation`, `quality.HazardousMaterial`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering (`org_unit`, `supplier`, `transporter`, `tsdf_facility`, `measurement_instrument`).

---

## 1. Models & Choices Contract (`apps/quality/models/EhsManagement/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `HazardousMaterial` (`HazardousMaterials.py`)
- **`NUMBER_PREFIX`**: `"QHAZ"`
- **`Meta.ordering`**: `["material_name", "number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Hazardous Material"` / `"Hazardous Materials"`
- **Choices & Badge Maps**:
  - `PHYSICAL_STATE_CHOICES` (`max_length=20`):
    - `("liquid", "Liquid")`
    - `("solid", "Solid")`
    - `("gas", "Compressed Gas")`
    - `("aerosol", "Aerosol")`
    - `("sludge", "Sludge / Paste")`
  - `GHS_SIGNAL_WORD_CHOICES` (`max_length=20`):
    - `("danger", "Danger")`
    - `("warning", "Warning")`
    - `("none", "None / Non-Hazardous")`
  - `NFPA_SPECIAL_HAZARD_CHOICES` (`max_length=20`):
    - `("none", "None")`
    - `("ox", "OX — Oxidizer")`
    - `("w_slash", "W (bar) — Reacts violently with water")`
    - `("sa", "SA — Simple Asphyxiant")`
    - `("cor", "COR — Corrosive")`
    - `("bio", "BIO — Biological Hazard")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("active", "Active In Use")`
    - `("restricted", "Restricted Access")`
    - `("under_review", "Under EHS Review")`
    - `("discontinued", "Discontinued / Phased Out")`
  - `STATUS_CSS`:
    - `"active": "badge-green"`
    - `"restricted": "badge-amber"`
    - `"under_review": "badge-info"`
    - `"discontinued": "badge-slate"`
  - `SIGNAL_WORD_CSS`:
    - `"danger": "badge-red"`
    - `"warning": "badge-amber"`
    - `"none": "badge-slate"`
- **Fields (exact names & types)**:
  - `material_name`: `CharField(max_length=255)`
  - `trade_name`: `CharField(max_length=255, blank=True)`
  - `cas_number`: `CharField(max_length=50, blank=True, db_index=True)`
  - `un_number`: `CharField(max_length=20, blank=True)`
  - `chemical_formula`: `CharField(max_length=100, blank=True)`
  - `physical_state`: `CharField(max_length=20, choices=PHYSICAL_STATE_CHOICES, default="liquid", db_index=True)`
  - `ghs_signal_word`: `CharField(max_length=20, choices=GHS_SIGNAL_WORD_CHOICES, default="warning", db_index=True)`
  - `ghs_pictograms`: `CharField(max_length=255, blank=True, help_text="Comma-separated GHS pictogram codes")`
  - `hazard_statements`: `TextField(blank=True)`
  - `precautionary_statements`: `TextField(blank=True)`
  - `nfpa_health`: `PositiveSmallIntegerField(default=0)`
  - `nfpa_flammability`: `PositiveSmallIntegerField(default=0)`
  - `nfpa_instability`: `PositiveSmallIntegerField(default=0)`
  - `nfpa_special_hazard`: `CharField(max_length=20, choices=NFPA_SPECIAL_HAZARD_CHOICES, default="none")`
  - `sds_revision`: `CharField(max_length=50, blank=True, default="Rev 1.0")`
  - `sds_issue_date`: `DateField(null=True, blank=True)`
  - `sds_expiry_date`: `DateField(null=True, blank=True, db_index=True)`
  - `sds_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="hazardous_materials")`
  - `osha_pel`: `CharField(max_length=100, blank=True)`
  - `acgih_tlv`: `CharField(max_length=100, blank=True)`
  - `exposure_uom`: `CharField(max_length=50, blank=True, default="ppm")`
  - `ppe_requirements`: `TextField(blank=True)`
  - `incompatible_materials`: `TextField(blank=True)`
  - `spill_cleanup_procedure`: `TextField(blank=True)`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="hazardous_materials")`
  - `storage_location_code`: `CharField(max_length=100, blank=True)`
  - `maximum_storage_quantity`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `quantity_uom`: `CharField(max_length=50, default="L")`
  - `supplier`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="hazardous_materials")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="active", db_index=True)`
  - `managed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="managed_hazardous_materials")`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `is_sds_expired`: `sds_expiry_date and sds_expiry_date < timezone.now().date()`
  - `sds_status_css`: `"badge-red"` if expired, `"badge-amber"` if expiring within 90 days, `"badge-green"` if active/current, `"badge-slate"` if no expiry set.
  - `status_css`: Maps `status` to `STATUS_CSS`.
  - `signal_word_css`: Maps `ghs_signal_word` to `SIGNAL_WORD_CSS`.
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qhaz_ten_num_uniq")` (26 chars)
  - `Index(fields=["tenant", "status"], name="idx_qhaz_ten_status")` (19 chars)
  - `Index(fields=["tenant", "physical_state"], name="idx_qhaz_ten_state")` (18 chars)
  - `Index(fields=["tenant", "cas_number"], name="idx_qhaz_ten_cas")` (16 chars)
  - `Index(fields=["tenant", "sds_expiry_date"], name="idx_qhaz_ten_exp_dt")` (19 chars)
  - `Index(fields=["tenant", "org_unit"], name="idx_qhaz_ten_org")` (16 chars)
  - `Index(fields=["tenant", "supplier"], name="idx_qhaz_ten_sup")` (16 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qhaz_ten_created")` (20 chars)

---

### 1.2 `SafetyIncident` (`SafetyIncidents.py`)
- **`NUMBER_PREFIX`**: `"QSIR"`
- **`Meta.ordering`**: `["-incident_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Safety Incident"` / `"Safety Incidents"`
- **Choices & Badge Maps**:
  - `INCIDENT_TYPE_CHOICES` (`max_length=30`):
    - `("injury_illness", "Occupational Injury / Illness")`
    - `("near_miss", "Near-Miss Event")`
    - `("hazardous_condition", "Hazardous Condition / Safety Hazard")`
    - `("chemical_spill", "Chemical Spill / Hazmat Release")`
    - `("fire_explosion", "Fire / Explosion")`
    - `("property_damage", "Equipment / Property Damage")`
    - `("cleanroom_breach", "Cleanroom Biocontainment / Protocol Breach")`
  - `SEVERITY_CHOICES` (`max_length=20`):
    - `("minor", "Minor (First Aid / No Lost Time)")`
    - `("moderate", "Moderate (Medical Treatment / Restricted)")`
    - `("severe", "Severe (Lost Time / Inpatient)")`
    - `("critical", "Critical (Amputation / Life Threatening)")`
    - `("fatal", "Fatal (Fatality)")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("reported", "Reported")`
    - `("investigating", "Under Investigation")`
    - `("under_review", "Under Review")`
    - `("capa_pending", "CAPA Pending")`
    - `("closed", "Closed")`
    - `("cancelled", "Cancelled / Void")`
  - `AFFECTED_PARTY_TYPE_CHOICES` (`max_length=30`):
    - `("employee", "Direct Company Employee")`
    - `("contractor", "On-Site Contractor")`
    - `("visitor", "Visitor / Guest")`
    - `("temporary_worker", "Temporary / Agency Worker")`
  - `NATURE_OF_INJURY_CHOICES` (`max_length=35`):
    - `("none", "None / Near-Miss")`
    - `("strain_sprain", "Strain / Sprain")`
    - `("laceration_cut", "Laceration / Cut / Puncture")`
    - `("burn_heat_chemical", "Burn (Thermal / Chemical)")`
    - `("fracture", "Fracture / Dislocation")`
    - `("contusion_bruise", "Contusion / Bruise / Crush")`
    - `("eye_injury", "Eye Injury / Foreign Body")`
    - `("inhalation_respiratory", "Chemical Inhalation / Respiratory")`
    - `("skin_irritation", "Dermatitis / Skin Irritation")`
    - `("hearing_impact", "Acoustic Trauma / Hearing Impact")`
    - `("other", "Other Specified Injury")`
  - `BODY_PART_CHOICES` (`max_length=30`):
    - `("none", "None / Not Applicable")`
    - `("head_face", "Head / Face")`
    - `("eyes", "Eyes")`
    - `("hands_fingers", "Hands / Fingers / Wrists")`
    - `("arms_shoulders", "Arms / Shoulders")`
    - `("back_spine", "Back / Spine")`
    - `("legs_knees", "Legs / Knees")`
    - `("feet_toes", "Feet / Toes")`
    - `("respiratory_system", "Respiratory System / Lungs")`
    - `("multiple", "Multiple Body Systems")`
  - `MEDICAL_TREATMENT_LEVEL_CHOICES` (`max_length=30`):
    - `("none", "None Required")`
    - `("first_aid_only", "First Aid On-Site Only")`
    - `("clinic_visit", "Occupational Clinic / Urgent Care")`
    - `("emergency_room", "Hospital Emergency Department")`
    - `("hospitalization", "Inpatient Hospitalization")`
  - `OSHA_CLASSIFICATION_CHOICES` (`max_length=35`):
    - `("non_recordable", "Non-Recordable Event")`
    - `("first_aid", "First Aid Only (Non-Recordable)")`
    - `("days_away_from_work", "Death or Days Away From Work")`
    - `("job_transfer_restriction", "Job Transfer or Work Restriction")`
    - `("other_recordable_case", "Other Recordable Case")`
  - `PPE_COMPLIANCE_CHOICES` (`max_length=25`):
    - `("compliant", "Fully Compliant with Required PPE")`
    - `("non_compliant", "Required PPE Not Worn")`
    - `("inadequate_ppe", "PPE Worn Was Inadequate for Hazard")`
    - `("not_applicable", "No Specific PPE Mandated")`
  - `ROOT_CAUSE_CATEGORY_CHOICES` (`max_length=35`):
    - `("human_factors", "Human Factors / Unsafe Behavior")`
    - `("equipment_failure", "Equipment / Tooling Failure")`
    - `("procedure_gap", "SOP / Procedure Deficient or Missing")`
    - `("training_deficiency", "Training / Competency Gap")`
    - `("ergonomic_strain", "Ergonomic Stress / Repetitive Motion")`
    - `("environmental_hazard", "Slip/Trip Hazard / Lighting / Noise")`
    - `("inadequate_ppe", "Defective or Inappropriate PPE")`
    - `("under_investigation", "Under Root Cause Investigation")`
  - `STATUS_CSS`:
    - `"reported": "badge-info"`
    - `"investigating": "badge-amber"`
    - `"under_review": "badge-amber"`
    - `"capa_pending": "badge-red"`
    - `"closed": "badge-green"`
    - `"cancelled": "badge-muted"`
  - `SEVERITY_CSS`:
    - `"minor": "badge-slate"`
    - `"moderate": "badge-info"`
    - `"severe": "badge-amber"`
    - `"critical": "badge-red"`
    - `"fatal": "badge-red"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `incident_date`: `DateTimeField(db_index=True)`
  - `report_date`: `DateField(db_index=True)`
  - `incident_type`: `CharField(max_length=30, choices=INCIDENT_TYPE_CHOICES, default="injury_illness", db_index=True)`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default="minor", db_index=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="reported", db_index=True)`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="safety_incidents")`
  - `location_details`: `CharField(max_length=255, blank=True)`
  - `reported_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_safety_incidents")`
  - `affected_person`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="involved_safety_incidents")`
  - `affected_party_name`: `CharField(max_length=255, blank=True)`
  - `affected_party_type`: `CharField(max_length=30, choices=AFFECTED_PARTY_TYPE_CHOICES, default="employee", db_index=True)`
  - `nature_of_injury`: `CharField(max_length=35, choices=NATURE_OF_INJURY_CHOICES, default="none", db_index=True)`
  - `body_part_affected`: `CharField(max_length=30, choices=BODY_PART_CHOICES, default="none")`
  - `medical_treatment_level`: `CharField(max_length=30, choices=MEDICAL_TREATMENT_LEVEL_CHOICES, default="none", db_index=True)`
  - `is_osha_recordable`: `BooleanField(default=False, db_index=True)`
  - `osha_classification`: `CharField(max_length=35, choices=OSHA_CLASSIFICATION_CHOICES, default="non_recordable", db_index=True)`
  - `lost_workdays_count`: `PositiveIntegerField(default=0)`
  - `restricted_workdays_count`: `PositiveIntegerField(default=0)`
  - `date_returned_to_work`: `DateField(null=True, blank=True)`
  - `ppe_compliance_status`: `CharField(max_length=25, choices=PPE_COMPLIANCE_CHOICES, default="compliant", db_index=True)`
  - `ppe_notes`: `TextField(blank=True)`
  - `immediate_actions_taken`: `TextField(blank=True)`
  - `lead_investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="investigated_safety_incidents")`
  - `root_cause_category`: `CharField(max_length=35, choices=ROOT_CAUSE_CATEGORY_CHOICES, default="under_investigation", db_index=True)`
  - `investigation_findings`: `TextField(blank=True)`
  - `capa_investigation`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="safety_incidents")`
  - `non_conformance_report`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="safety_incidents")`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `is_dart_incident`: `lost_workdays_count > 0 or restricted_workdays_count > 0`
  - `total_lost_and_restricted_days`: `lost_workdays_count + restricted_workdays_count`
  - `status_css`: Maps `status` to `STATUS_CSS`.
  - `severity_css`: Maps `severity` to `SEVERITY_CSS`.
  - `osha_css`: `"badge-red"` if `is_osha_recordable` else `"badge-slate"`.
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qsir_ten_num_uniq")` (26 chars)
  - `Index(fields=["tenant", "status"], name="idx_qsir_ten_status")` (19 chars)
  - `Index(fields=["tenant", "incident_type"], name="idx_qsir_ten_type")` (17 chars)
  - `Index(fields=["tenant", "severity"], name="idx_qsir_ten_sev")` (16 chars)
  - `Index(fields=["tenant", "is_osha_recordable"], name="idx_qsir_ten_osha")` (17 chars)
  - `Index(fields=["tenant", "incident_date"], name="idx_qsir_ten_date")` (17 chars)
  - `Index(fields=["tenant", "org_unit"], name="idx_qsir_ten_org")` (16 chars)
  - `Index(fields=["tenant", "reported_by"], name="idx_qsir_ten_rep")` (16 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qsir_ten_created")` (20 chars)

---

### 1.3 `EnvironmentalMonitoringLog` (`EnvironmentalMonitoringLogs.py`)
- **`NUMBER_PREFIX`**: `"QENV"`
- **`Meta.ordering`**: `["-sampling_timestamp", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Environmental Monitoring Log"` / `"Environmental Monitoring Logs"`
- **Choices & Badge Maps**:
  - `CLEANROOM_CLASS_CHOICES` (`max_length=35`):
    - `("iso_class_3", "ISO Class 3 (Class 1)")`
    - `("iso_class_4", "ISO Class 4 (Class 10)")`
    - `("iso_class_5", "ISO Class 5 (Class 100 / Grade A/B)")`
    - `("iso_class_6", "ISO Class 6 (Class 1,000)")`
    - `("iso_class_7", "ISO Class 7 (Class 10,000 / Grade C)")`
    - `("iso_class_8", "ISO Class 8 (Class 100,000 / Grade D)")`
    - `("iso_class_9", "ISO Class 9 (Room Air)")`
    - `("unclassified_controlled", "CNC — Controlled Non-Classified")`
  - `OPERATIONAL_STATE_CHOICES` (`max_length=25`):
    - `("at_rest", "At Rest (Unoccupied)")`
    - `("in_operation", "In Operation (Active Manufacturing)")`
  - `MONITORING_CATEGORY_CHOICES` (`max_length=40`):
    - `("airborne_particles_0_5um", "Airborne Particles (>= 0.5 um)")`
    - `("airborne_particles_5_0um", "Airborne Particles (>= 5.0 um)")`
    - `("viable_air_microbial", "Active Air Sampler Microbial (CFU/m3)")`
    - `("viable_settle_plate", "Passive Settle Plate Microbial (CFU/4hr)")`
    - `("viable_surface_contact", "Surface Contact Plate Microbial (CFU/plate)")`
    - `("viable_glove_print", "Personnel 5-Finger Glove Print (CFU)")`
    - `("differential_pressure", "Differential Room Pressure (Pa)")`
    - `("temperature", "Ambient Room Temperature (°C)")`
    - `("relative_humidity", "Relative Room Humidity (%RH)")`
  - `UNIT_OF_MEASURE_CHOICES` (`max_length=25`):
    - `("particles_m3", "particles/m3")`
    - `("particles_ft3", "particles/ft3")`
    - `("cfu_m3", "CFU/m3")`
    - `("cfu_plate", "CFU/plate")`
    - `("pascals", "Pa (Pascals)")`
    - `("celsius", "°C")`
    - `("percent_rh", "%RH")`
  - `EVALUATION_STATUS_CHOICES` (`max_length=25`):
    - `("normal", "Normal Within Limits")`
    - `("alert_exceeded", "Alert Limit Exceeded")`
    - `("action_exceeded", "Action Limit Exceeded (Excursion)")`
    - `("invalid_sample", "Invalid / Void Sample")`
  - `EVALUATION_STATUS_CSS`:
    - `"normal": "badge-green"`
    - `"alert_exceeded": "badge-amber"`
    - `"action_exceeded": "badge-red"`
    - `"invalid_sample": "badge-slate"`
- **Fields (exact names & types)**:
  - `sampling_point_id`: `CharField(max_length=100, db_index=True)`
  - `sampling_timestamp`: `DateTimeField(db_index=True)`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="environmental_logs")`
  - `cleanroom_class`: `CharField(max_length=35, choices=CLEANROOM_CLASS_CHOICES, default="iso_class_7", db_index=True)`
  - `operational_state`: `CharField(max_length=25, choices=OPERATIONAL_STATE_CHOICES, default="in_operation", db_index=True)`
  - `monitoring_category`: `CharField(max_length=40, choices=MONITORING_CATEGORY_CHOICES, default="airborne_particles_0_5um", db_index=True)`
  - `parameter_name`: `CharField(max_length=255)`
  - `measured_value`: `DecimalField(max_digits=12, decimal_places=3)`
  - `unit_of_measure`: `CharField(max_length=25, choices=UNIT_OF_MEASURE_CHOICES, default="particles_m3", db_index=True)`
  - `target_nominal_value`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `lower_alert_limit`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `upper_alert_limit`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `lower_action_limit`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `upper_action_limit`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `evaluation_status`: `CharField(max_length=25, choices=EVALUATION_STATUS_CHOICES, default="normal", db_index=True)`
  - `excursion_details`: `TextField(blank=True)`
  - `immediate_containment_action`: `TextField(blank=True)`
  - `sampled_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sampled_environmental_logs")`
  - `verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_environmental_logs")`
  - `measurement_instrument`: `ForeignKey("quality.CalibrationGage", on_delete=models.SET_NULL, null=True, blank=True, related_name="environmental_logs")`
  - `process_deviation`: `ForeignKey("quality.ProcessDeviation", on_delete=models.SET_NULL, null=True, blank=True, related_name="environmental_logs")`
  - `non_conformance_report`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="environmental_logs")`
  - `capa_investigation`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="environmental_logs")`
  - `notes`: `TextField(blank=True)`
- **Properties & Methods**:
  - `is_excursion`: `evaluation_status in ("alert_exceeded", "action_exceeded")`
  - `evaluation_status_css`: Maps `evaluation_status` to `EVALUATION_STATUS_CSS`.
  - `cleanroom_display`: Formatted cleanroom class and operational state.
  - `calculate_evaluation_status()`: Computes `evaluation_status` comparing `measured_value` against lower/upper alert/action limits.
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qenv_ten_num_uniq")` (26 chars)
  - `Index(fields=["tenant", "evaluation_status"], name="idx_qenv_ten_status")` (19 chars)
  - `Index(fields=["tenant", "monitoring_category"], name="idx_qenv_ten_cat")` (16 chars)
  - `Index(fields=["tenant", "cleanroom_class"], name="idx_qenv_ten_class")` (18 chars)
  - `Index(fields=["tenant", "sampling_timestamp"], name="idx_qenv_ten_time")` (17 chars)
  - `Index(fields=["tenant", "sampling_point_id"], name="idx_qenv_ten_pt")` (15 chars)
  - `Index(fields=["tenant", "org_unit"], name="idx_qenv_ten_org")` (16 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qenv_ten_created")` (20 chars)

---

### 1.4 `WasteDisposalManifest` (`WasteDisposalManifests.py`)
- **`NUMBER_PREFIX`**: `"QWST"`
- **`Meta.ordering`**: `["-shipment_date", "-accumulation_start_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Waste Disposal Manifest"` / `"Waste Disposal Manifests"`
- **Choices & Badge Maps**:
  - `MANIFEST_TYPE_CHOICES` (`max_length=35`):
    - `("hazardous_chemical", "RCRA Hazardous Chemical Waste")`
    - `("universal_waste", "Universal Waste (Batteries / Lamps / Mercury)")`
    - `("biohazard_infectious", "Biohazardous / Medical Infectious Waste")`
    - `("radioactive", "Radioactive / Low-Level Waste")`
    - `("non_hazardous_industrial", "Non-Hazardous Regulated Industrial Waste")`
    - `("electronic_weee", "Electronic Waste (WEEE / RoHS Regulated)")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("draft", "Draft In Preparation")`
    - `("scheduled", "Scheduled for Transport Pickup")`
    - `("in_transit", "In Transit to TSDF")`
    - `("received_by_tsdf", "Received at TSDF Facility")`
    - `("certified_disposed", "Final Destruction Certified")`
    - `("discrepancy_flagged", "TSDF Discrepancy Flagged")`
  - `PHYSICAL_STATE_CHOICES` (`max_length=25`):
    - `("liquid", "Liquid")`
    - `("solid", "Solid")`
    - `("sludge", "Sludge / Semi-Solid")`
    - `("gas_cylinder", "Compressed Gas Cylinder")`
  - `CONTAINER_TYPE_CHOICES` (`max_length=25`):
    - `("drum_55gal", "55-Gallon Steel / Poly Drum (DM)")`
    - `("tote_ibc", "275/330-Gallon IBC Tote (TT)")`
    - `("cylinder", "Cylinder / Pressure Vessel (CY)")`
    - `("box_fiberboard", "Fiberboard Box / Gaylord (BA)")`
    - `("tank_bulk", "Bulk Tanker / Tank Truck (TK)")`
    - `("roll_off", "Roll-Off Box / Dumpster (RO)")`
  - `QUANTITY_UOM_CHOICES` (`max_length=20`):
    - `("pounds", "Pounds (P)")`
    - `("kilograms", "Kilograms (K)")`
    - `("gallons", "Gallons (G)")`
    - `("liters", "Liters (L)")`
    - `("tons", "Tons (T)")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"scheduled": "badge-info"`
    - `"in_transit": "badge-amber"`
    - `"received_by_tsdf": "badge-info"`
    - `"certified_disposed": "badge-green"`
    - `"discrepancy_flagged": "badge-red"`
  - `MANIFEST_TYPE_CSS`:
    - `"hazardous_chemical": "badge-red"`
    - `"universal_waste": "badge-amber"`
    - `"biohazard_infectious": "badge-red"`
    - `"radioactive": "badge-red"`
    - `"non_hazardous_industrial": "badge-slate"`
    - `"electronic_weee": "badge-info"`
- **Fields (exact names & types)**:
  - `manifest_title`: `CharField(max_length=255)`
  - `regulatory_manifest_id`: `CharField(max_length=100, db_index=True)`
  - `manifest_type`: `CharField(max_length=35, choices=MANIFEST_TYPE_CHOICES, default="hazardous_chemical", db_index=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `generator_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="waste_manifests")`
  - `generator_epa_id`: `CharField(max_length=50, blank=True)`
  - `accumulation_start_date`: `DateField(db_index=True)`
  - `waste_description`: `TextField()`
  - `epa_waste_codes`: `CharField(max_length=255, blank=True)`
  - `associated_hazardous_material`: `ForeignKey("quality.HazardousMaterial", on_delete=models.SET_NULL, null=True, blank=True, related_name="waste_manifests")`
  - `physical_state`: `CharField(max_length=25, choices=PHYSICAL_STATE_CHOICES, default="liquid", db_index=True)`
  - `is_ignitable`: `BooleanField(default=False)`
  - `is_corrosive`: `BooleanField(default=False)`
  - `is_reactive`: `BooleanField(default=False)`
  - `is_toxic`: `BooleanField(default=False)`
  - `container_type`: `CharField(max_length=25, choices=CONTAINER_TYPE_CHOICES, default="drum_55gal", db_index=True)`
  - `container_count`: `PositiveIntegerField(default=1)`
  - `quantity_value`: `DecimalField(max_digits=12, decimal_places=2)`
  - `quantity_uom`: `CharField(max_length=20, choices=QUANTITY_UOM_CHOICES, default="pounds", db_index=True)`
  - `transporter`: `ForeignKey("core.Party", on_delete=models.PROTECT, related_name="transported_waste_manifests")`
  - `transporter_epa_id`: `CharField(max_length=50, blank=True)`
  - `tsdf_facility`: `ForeignKey("core.Party", on_delete=models.PROTECT, related_name="received_waste_manifests")`
  - `tsdf_epa_id`: `CharField(max_length=50, blank=True)`
  - `shipment_date`: `DateField(null=True, blank=True, db_index=True)`
  - `tsdf_receipt_date`: `DateField(null=True, blank=True)`
  - `management_method_code`: `CharField(max_length=50, blank=True)`
  - `certificate_of_disposal_number`: `CharField(max_length=100, blank=True)`
  - `certificate_received_date`: `DateField(null=True, blank=True)`
  - `discrepancy_details`: `TextField(blank=True)`
  - `certifying_officer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="certified_waste_manifests")`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `accumulation_days`: Elapsed days between `accumulation_start_date` and `shipment_date` (or `timezone.now().date()` if unshipped).
  - `is_accumulation_overdue`: `accumulation_days > 90 and status in ("draft", "scheduled")`.
  - `status_css`: Maps `status` to `STATUS_CSS`.
  - `manifest_type_css`: Maps `manifest_type` to `MANIFEST_TYPE_CSS`.
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qwst_ten_num_uniq")` (26 chars)
  - `Index(fields=["tenant", "status"], name="idx_qwst_ten_status")` (19 chars)
  - `Index(fields=["tenant", "manifest_type"], name="idx_qwst_ten_type")` (17 chars)
  - `Index(fields=["tenant", "shipment_date"], name="idx_qwst_ten_ship_dt")` (20 chars)
  - `Index(fields=["tenant", "accumulation_start_date"], name="idx_qwst_ten_acc_dt")` (19 chars)
  - `Index(fields=["tenant", "generator_org_unit"], name="idx_qwst_ten_gen_org")` (20 chars)
  - `Index(fields=["tenant", "transporter"], name="idx_qwst_ten_transp")` (19 chars)
  - `Index(fields=["tenant", "tsdf_facility"], name="idx_qwst_ten_tsdf")` (17 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qwst_ten_created")` (20 chars)

---

## 2. Forms Contract (`apps/quality/forms/EhsManagement/`)

All forms inherit `forms.ModelForm`, receive `tenant` as the first positional argument in `__init__(self, tenant, *args, **kwargs)`, filter all FK querysets by `tenant=self.tenant`, and call `reject_foreign(...)` in `clean()`.

### 2.1 `HazardousMaterialForm` (`HazardousMaterials.py`)
- **`model`**: `HazardousMaterial`
- **`fields`**: `["material_name", "trade_name", "cas_number", "un_number", "chemical_formula", "physical_state", "ghs_signal_word", "ghs_pictograms", "hazard_statements", "precautionary_statements", "nfpa_health", "nfpa_flammability", "nfpa_instability", "nfpa_special_hazard", "sds_revision", "sds_issue_date", "sds_expiry_date", "sds_document", "osha_pel", "acgih_tlv", "exposure_uom", "ppe_requirements", "incompatible_materials", "spill_cleanup_procedure", "org_unit", "storage_location_code", "maximum_storage_quantity", "quantity_uom", "supplier", "status", "managed_by", "notes"]`
- **Excluded**: `tenant`, `number`, `created_at`, `updated_at`.
- **Tenant-scoped FK querysets in `__init__`**:
  - `org_unit`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - `sds_document`: `ControlledDocument.objects.filter(tenant=self.tenant)`
  - `supplier`: `Party.objects.filter(tenant=self.tenant)`
  - `managed_by`: `User.objects.filter(tenant=self.tenant)`

### 2.2 `SafetyIncidentForm` (`SafetyIncidents.py`)
- **`model`**: `SafetyIncident`
- **`fields`**: `["title", "incident_date", "report_date", "incident_type", "severity", "status", "org_unit", "location_details", "reported_by", "affected_person", "affected_party_name", "affected_party_type", "nature_of_injury", "body_part_affected", "medical_treatment_level", "is_osha_recordable", "osha_classification", "lost_workdays_count", "restricted_workdays_count", "date_returned_to_work", "ppe_compliance_status", "ppe_notes", "immediate_actions_taken", "lead_investigator", "root_cause_category", "investigation_findings", "capa_investigation", "non_conformance_report", "notes"]`
- **Excluded**: `tenant`, `number`, `created_at`, `updated_at`.
- **Tenant-scoped FK querysets in `__init__`**:
  - `org_unit`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - `reported_by`: `User.objects.filter(tenant=self.tenant)`
  - `affected_person`: `User.objects.filter(tenant=self.tenant)`
  - `lead_investigator`: `User.objects.filter(tenant=self.tenant)`
  - `capa_investigation`: `CapaInvestigation.objects.filter(tenant=self.tenant)`
  - `non_conformance_report`: `NonConformanceReport.objects.filter(tenant=self.tenant)`

### 2.3 `EnvironmentalMonitoringLogForm` (`EnvironmentalMonitoringLogs.py`)
- **`model`**: `EnvironmentalMonitoringLog`
- **`fields`**: `["sampling_point_id", "sampling_timestamp", "org_unit", "cleanroom_class", "operational_state", "monitoring_category", "parameter_name", "measured_value", "unit_of_measure", "target_nominal_value", "lower_alert_limit", "upper_alert_limit", "lower_action_limit", "upper_action_limit", "excursion_details", "immediate_containment_action", "sampled_by", "verified_by", "measurement_instrument", "process_deviation", "non_conformance_report", "capa_investigation", "notes"]`
- **Excluded**: `tenant`, `number`, `evaluation_status`, `created_at`, `updated_at`.
- **Tenant-scoped FK querysets in `__init__`**:
  - `org_unit`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - `sampled_by`: `User.objects.filter(tenant=self.tenant)`
  - `verified_by`: `User.objects.filter(tenant=self.tenant)`
  - `measurement_instrument`: `CalibrationGage.objects.filter(tenant=self.tenant)`
  - `process_deviation`: `ProcessDeviation.objects.filter(tenant=self.tenant)`
  - `non_conformance_report`: `NonConformanceReport.objects.filter(tenant=self.tenant)`
  - `capa_investigation`: `CapaInvestigation.objects.filter(tenant=self.tenant)`

### 2.4 `WasteDisposalManifestForm` (`WasteDisposalManifests.py`)
- **`model`**: `WasteDisposalManifest`
- **`fields`**: `["manifest_title", "regulatory_manifest_id", "manifest_type", "status", "generator_org_unit", "generator_epa_id", "accumulation_start_date", "waste_description", "epa_waste_codes", "associated_hazardous_material", "physical_state", "is_ignitable", "is_corrosive", "is_reactive", "is_toxic", "container_type", "container_count", "quantity_value", "quantity_uom", "transporter", "transporter_epa_id", "tsdf_facility", "tsdf_epa_id", "shipment_date", "tsdf_receipt_date", "management_method_code", "certificate_of_disposal_number", "certificate_received_date", "discrepancy_details", "certifying_officer", "notes"]`
- **Excluded**: `tenant`, `number`, `created_at`, `updated_at`.
- **Tenant-scoped FK querysets in `__init__`**:
  - `generator_org_unit`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - `associated_hazardous_material`: `HazardousMaterial.objects.filter(tenant=self.tenant)`
  - `transporter`: `Party.objects.filter(tenant=self.tenant)`
  - `tsdf_facility`: `Party.objects.filter(tenant=self.tenant)`
  - `certifying_officer`: `User.objects.filter(tenant=self.tenant)`

---

## 3. URLs & Routes Contract (`apps/quality/urls/EhsManagement/`)

All routes defined inside `urlpatterns` in `apps/quality/urls/EhsManagement/<Entity>.py` and included in `apps/quality/urls/__init__.py`. Literal patterns placed before `<int:pk>`.

### 3.1 `HazardousMaterials.py`
- `GET quality/hazardous-materials/` -> `name="hazardous_material_list"`
- `GET/POST quality/hazardous-materials/create/` -> `name="hazardous_material_create"`
- `GET quality/hazardous-materials/export/` -> `name="hazardous_material_export"`
- `GET quality/hazardous-materials/<int:pk>/` -> `name="hazardous_material_detail"`
- `GET/POST quality/hazardous-materials/<int:pk>/edit/` -> `name="hazardous_material_update"`
- `POST quality/hazardous-materials/<int:pk>/delete/` -> `name="hazardous_material_delete"`
- `GET quality/hazardous-materials/<int:pk>/label/` -> `name="hazardous_material_label"`

### 3.2 `SafetyIncidents.py`
- `GET quality/safety-incidents/` -> `name="safety_incident_list"`
- `GET/POST quality/safety-incidents/create/` -> `name="safety_incident_create"`
- `GET quality/safety-incidents/export/` -> `name="safety_incident_export"`
- `GET quality/safety-incidents/<int:pk>/` -> `name="safety_incident_detail"`
- `GET/POST quality/safety-incidents/<int:pk>/edit/` -> `name="safety_incident_update"`
- `POST quality/safety-incidents/<int:pk>/delete/` -> `name="safety_incident_delete"`
- `POST quality/safety-incidents/<int:pk>/investigate/` -> `name="safety_incident_investigate"`

### 3.3 `EnvironmentalMonitoringLogs.py`
- `GET quality/environmental-logs/` -> `name="environmental_monitoring_log_list"`
- `GET/POST quality/environmental-logs/create/` -> `name="environmental_monitoring_log_create"`
- `GET quality/environmental-logs/export/` -> `name="environmental_monitoring_log_export"`
- `GET quality/environmental-logs/<int:pk>/` -> `name="environmental_monitoring_log_detail"`
- `GET/POST quality/environmental-logs/<int:pk>/edit/` -> `name="environmental_monitoring_log_update"`
- `POST quality/environmental-logs/<int:pk>/delete/` -> `name="environmental_monitoring_log_delete"`
- `POST quality/environmental-logs/<int:pk>/evaluate/` -> `name="environmental_monitoring_log_evaluate"`

### 3.4 `WasteDisposalManifests.py`
- `GET quality/waste-manifests/` -> `name="waste_disposal_manifest_list"`
- `GET/POST quality/waste-manifests/create/` -> `name="waste_disposal_manifest_create"`
- `GET quality/waste-manifests/export/` -> `name="waste_disposal_manifest_export"`
- `GET quality/waste-manifests/<int:pk>/` -> `name="waste_disposal_manifest_detail"`
- `GET/POST quality/waste-manifests/<int:pk>/edit/` -> `name="waste_disposal_manifest_update"`
- `POST quality/waste-manifests/<int:pk>/delete/` -> `name="waste_disposal_manifest_delete"`
- `POST quality/waste-manifests/<int:pk>/certify/` -> `name="waste_disposal_manifest_certify"`

### 3.5 `EhsDashboard.py`
- `GET quality/ehs-dashboard/` -> `name="ehs_dashboard"`
- `GET quality/ehs-dashboard/export/` -> `name="ehs_dashboard_export"`

---

## 4. Views & Context Contract (`apps/quality/views/EhsManagement/`)

Every view is function-based and decorated with `@login_required`. Mutating views execute with `write_audit_log(request.user, obj, action.lower(), tenant=request.tenant)` (L66).

### 4.1 `HazardousMaterials.py`
- `hazardous_material_list`:
  - Context keys:
    - `hazardous_materials`: `page_obj.object_list`
    - `page_obj`: `page_obj`
    - `paginator`: `paginator`
    - `is_paginated`: boolean
    - `total_count`: integer count
    - `status_choices`: `HazardousMaterial.STATUS_CHOICES`
    - `physical_state_choices`: `HazardousMaterial.PHYSICAL_STATE_CHOICES`
    - `signal_word_choices`: `HazardousMaterial.GHS_SIGNAL_WORD_CHOICES`
    - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
    - `suppliers`: `Party.objects.filter(tenant=request.tenant)`
- `hazardous_material_detail`:
  - Context keys:
    - `hazardous_material`: `obj`
    - `linked_waste_manifests`: `obj.waste_manifests.filter(tenant=request.tenant)[:10]`
- `hazardous_material_create` & `hazardous_material_update`:
  - Context keys:
    - `form`: `HazardousMaterialForm`
    - `hazardous_material`: `obj` (or `None` on create)
    - `is_edit`: boolean
- `hazardous_material_label`:
  - Context keys:
    - `hazardous_material`: `obj`

### 4.2 `SafetyIncidents.py`
- `safety_incident_list`:
  - Context keys:
    - `safety_incidents`: `page_obj.object_list`
    - `page_obj`: `page_obj`
    - `paginator`: `paginator`
    - `is_paginated`: boolean
    - `total_count`: integer count
    - `status_choices`: `SafetyIncident.STATUS_CHOICES`
    - `incident_type_choices`: `SafetyIncident.INCIDENT_TYPE_CHOICES`
    - `severity_choices`: `SafetyIncident.SEVERITY_CHOICES`
    - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
- `safety_incident_detail`:
  - Context keys:
    - `safety_incident`: `obj`
- `safety_incident_create` & `safety_incident_update`:
  - Context keys:
    - `form`: `SafetyIncidentForm`
    - `safety_incident`: `obj` (or `None` on create)
    - `is_edit`: boolean

### 4.3 `EnvironmentalMonitoringLogs.py`
- `environmental_monitoring_log_list`:
  - Context keys:
    - `environmental_logs`: `page_obj.object_list`
    - `page_obj`: `page_obj`
    - `paginator`: `paginator`
    - `is_paginated`: boolean
    - `total_count`: integer count
    - `evaluation_status_choices`: `EnvironmentalMonitoringLog.EVALUATION_STATUS_CHOICES`
    - `cleanroom_class_choices`: `EnvironmentalMonitoringLog.CLEANROOM_CLASS_CHOICES`
    - `category_choices`: `EnvironmentalMonitoringLog.MONITORING_CATEGORY_CHOICES`
    - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
- `environmental_monitoring_log_detail`:
  - Context keys:
    - `environmental_log`: `obj`
- `environmental_monitoring_log_create` & `environmental_monitoring_log_update`:
  - Context keys:
    - `form`: `EnvironmentalMonitoringLogForm`
    - `environmental_log`: `obj` (or `None` on create)
    - `is_edit`: boolean

### 4.4 `WasteDisposalManifests.py`
- `waste_disposal_manifest_list`:
  - Context keys:
    - `waste_manifests`: `page_obj.object_list`
    - `page_obj`: `page_obj`
    - `paginator`: `paginator`
    - `is_paginated`: boolean
    - `total_count`: integer count
    - `status_choices`: `WasteDisposalManifest.STATUS_CHOICES`
    - `manifest_type_choices`: `WasteDisposalManifest.MANIFEST_TYPE_CHOICES`
    - `transporters`: `Party.objects.filter(tenant=request.tenant)`
    - `tsdfs`: `Party.objects.filter(tenant=request.tenant)`
    - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
- `waste_disposal_manifest_detail`:
  - Context keys:
    - `waste_manifest`: `obj`
- `waste_disposal_manifest_create` & `waste_disposal_manifest_update`:
  - Context keys:
    - `form`: `WasteDisposalManifestForm`
    - `waste_manifest`: `obj` (or `None` on create)
    - `is_edit`: boolean

### 4.5 `EhsDashboard.py`
- `ehs_dashboard`:
  - Context keys:
    - `active_materials_count`: integer
    - `expiring_sds_count`: integer
    - `total_incidents_count`: integer
    - `osha_recordable_count`: integer
    - `dart_cases_count`: integer
    - `total_lost_days`: integer
    - `total_restricted_days`: integer
    - `active_excursions_count`: integer
    - `pending_manifests_count`: integer
    - `overdue_accumulation_count`: integer
    - `recent_incidents`: list of `SafetyIncident`
    - `recent_excursions`: list of `EnvironmentalMonitoringLog`
    - `expiring_sds_list`: list of `HazardousMaterial`
    - `pending_manifests`: list of `WasteDisposalManifest`
    - `incidents_by_severity`: dict
    - `manifests_by_type`: dict

---

## 5. Navigation LIVE_LINKS Contract (`apps/core/navigation.py`)

Exact mapping for Sub-module 12.16 in `apps/core/navigation.py`:
```python
"12.16": {
    "Hazardous Material Management": "quality:hazardous_material_list",
    "Workplace Safety Inspections": "quality:safety_incident_list",
    "Environmental Monitoring": "quality:environmental_monitoring_log_list",
    "Waste Management & Disposal": "quality:waste_disposal_manifest_list",
    "Occupational Health & Ergonomics": "quality:ehs_dashboard",
},
```
All 5 bullet strings match `NavERP.md` verbatim.
