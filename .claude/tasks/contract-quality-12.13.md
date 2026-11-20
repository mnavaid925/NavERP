# Module 12.13 Pre-Build Contract — Customer Complaint Handling (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.13"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0020_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/CustomerComplaints/`
  - `apps/quality/forms/CustomerComplaints/`
  - `apps/quality/views/CustomerComplaints/`
  - `apps/quality/urls/CustomerComplaints/`
  - `templates/quality/customercomplaints/{customer_complaint,complaint_investigation,regulatory_report,field_action}/{list,detail,form}.html` + `templates/quality/customercomplaints/complaint_trending_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"triage"`, `"close"`, `"complete"`, `"submit"`, `"ack"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.Party`, `scm.SalesOrder`, `scm.ReturnAuthorization`, `quality.RiskAssessment`, `quality.CapaInvestigation`, `quality.NonConformanceReport`, `quality.ControlledDocument`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/CustomerComplaints/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `CustomerComplaint` (`CustomerComplaints.py`)
- **`NUMBER_PREFIX`**: `"QCMP"`
- **`Meta.ordering`**: `["-date_received", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Customer Complaint"` / `"Customer Complaints"`
- **Choices & Badge Maps**:
  - `INTAKE_CHANNEL_CHOICES` (`max_length=30`):
    - `("phone", "Telephone Call")`
    - `("email", "Direct Email")`
    - `("web_portal", "Web Customer Portal")`
    - `("sales_rep", "Sales Representative")`
    - `("service_tech", "Field Service Technician")`
    - `("distributor", "Distributor / Wholesaler")`
    - `("regulatory_agency", "Regulatory Agency Authority")`
    - `("other", "Other Inbound Channel")`
  - `SEVERITY_CHOICES` (`max_length=30`):
    - `("critical_safety", "Critical Safety / Health Hazard")`
    - `("major_malfunction", "Major Functional Malfunction")`
    - `("minor_cosmetic", "Minor Cosmetic / Packaging")`
    - `("service_inconvenience", "Service / Documentation Issue")`
    - `("unspecified", "Unspecified / Pending Triage")`
  - `COMPLAINT_STATUS_CHOICES` (`max_length=30`):
    - `("intake_received", "Intake Received / Open")`
    - `("under_triage", "Under Triage Review")`
    - `("under_investigation", "Under Active Investigation")`
    - `("pending_regulatory", "Pending Regulatory Action")`
    - `("capa_pending", "Pending CAPA / NCR Actions")`
    - `("resolved", "Resolved / Pending QA Closure")`
    - `("closed", "Closed")`
    - `("cancelled", "Cancelled / Invalid")`
  - `VALIDITY_CHOICES` (`max_length=30`):
    - `("pending_triage", "Pending Triage Determination")`
    - `("valid_complaint", "Confirmed Valid Quality Complaint")`
    - `("invalid_allegation", "Invalid / Unsubstantiated Allegation")`
    - `("commercial_inquiry", "Commercial / Pricing Inquiry (Not Quality)")`
  - `REPORTABILITY_CHOICES` (`max_length=30`):
    - `("undetermined", "Undetermined (Screening Open)")`
    - `("reportable_event", "Mandatory Reportable Adverse Event")`
    - `("non_reportable", "Non-Reportable (QA Justified)")`
    - `("exempt", "Exempt from Regulatory Reporting")`
  - `SAMPLE_RETURN_STATUS_CHOICES` (`max_length=30`):
    - `("not_requested", "Sample Not Requested")`
    - `("requested_pending", "Sample Requested (Pending Return)")`
    - `("sample_received", "Sample Received in Lab")`
    - `("sample_destroyed", "Sample Destroyed / Retained")`
    - `("customer_declined", "Customer Declined / Unable to Return")`
  - `SEVERITY_CSS`:
    - `"critical_safety": "badge-red"`
    - `"major_malfunction": "badge-amber"`
    - `"minor_cosmetic": "badge-info"`
    - `"service_inconvenience": "badge-slate"`
    - `"unspecified": "badge-muted"`
  - `STATUS_CSS`:
    - `"intake_received": "badge-info"`
    - `"under_triage": "badge-amber"`
    - `"under_investigation": "badge-amber"`
    - `"pending_regulatory": "badge-red"`
    - `"capa_pending": "badge-purple"`
    - `"resolved": "badge-green"`
    - `"closed": "badge-muted"`
    - `"cancelled": "badge-slate"`
  - `VALIDITY_CSS`:
    - `"pending_triage": "badge-amber"`
    - `"valid_complaint": "badge-green"`
    - `"invalid_allegation": "badge-slate"`
    - `"commercial_inquiry": "badge-info"`
  - `REPORTABILITY_CSS`:
    - `"undetermined": "badge-amber"`
    - `"reportable_event": "badge-red"`
    - `"non_reportable": "badge-green"`
    - `"exempt": "badge-muted"`

- **Fields**:
  - `title`: `CharField(max_length=255, help_text="Headline summary of customer allegation")`
  - `intake_channel`: `CharField(max_length=30, choices=INTAKE_CHANNEL_CHOICES, default="email", db_index=True)`
  - `customer`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_complaints", help_text="Complainant customer or hospital facility (core.Party)")`
  - `complainant_name`: `CharField(max_length=128, help_text="Contact person, reporter, or patient representative")`
  - `complainant_email`: `CharField(max_length=128, blank=True, help_text="Complainant contact email")`
  - `complainant_phone`: `CharField(max_length=64, blank=True, help_text="Complainant phone number")`
  - `complainant_organization`: `CharField(max_length=128, blank=True, help_text="Facility, hospital, clinic, or institution name")`
  - `sales_order`: `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints", help_text="Associated sales order")`
  - `item_code`: `CharField(max_length=100, db_index=True, help_text="Product catalog number / SKU")`
  - `item_name`: `CharField(max_length=255, help_text="Commercial product name")`
  - `lot_number`: `CharField(max_length=100, db_index=True, blank=True, help_text="Batch / lot number")`
  - `serial_number`: `CharField(max_length=100, db_index=True, blank=True, help_text="Unit serial number")`
  - `udi_di_number`: `CharField(max_length=100, blank=True, help_text="Unique Device Identification (UDI-DI / GTIN)")`
  - `date_received`: `DateField(db_index=True, help_text="Date complaint was received by company")`
  - `date_of_occurrence`: `DateField(null=True, blank=True, help_text="Date event occurred at user facility")`
  - `problem_description`: `TextField(help_text="Detailed narrative of customer allegation or product malfunction")`
  - `patient_involved`: `BooleanField(default=False, help_text="Was a patient or end-user directly involved in the event?")`
  - `adverse_event_alleged`: `BooleanField(default=False, help_text="Did the event involve death, injury, or severe medical intervention?")`
  - `severity`: `CharField(max_length=30, choices=SEVERITY_CHOICES, default="unspecified", db_index=True)`
  - `status`: `CharField(max_length=30, choices=COMPLAINT_STATUS_CHOICES, default="intake_received", db_index=True)`
  - `validity`: `CharField(max_length=30, choices=VALIDITY_CHOICES, default="pending_triage", db_index=True)`
  - `reportability`: `CharField(max_length=30, choices=REPORTABILITY_CHOICES, default="undetermined", db_index=True)`
  - `non_reportable_justification`: `TextField(blank=True, help_text="Mandatory regulatory rationale if determined non-reportable (21 CFR 820.198(a)(3))")`
  - `complaint_category`: `CharField(max_length=100, blank=True, db_index=True, help_text="Failure code e.g. 'Leakage', 'Broken Seal', 'Display Error'")`
  - `sample_return_status`: `CharField(max_length=30, choices=SAMPLE_RETURN_STATUS_CHOICES, default="not_requested", db_index=True)`
  - `return_authorization`: `ForeignKey("scm.ReturnAuthorization", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints", help_text="Linked RMA record")`
  - `sample_tracking_number`: `CharField(max_length=100, blank=True, help_text="Carrier tracking number for returned specimen")`
  - `sample_received_date`: `DateField(null=True, blank=True, help_text="Date physical sample reached analysis laboratory")`
  - `triage_notes`: `TextField(blank=True, help_text="Initial QA triage findings and next step assignments")`
  - `triaged_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="triaged_complaints")`
  - `triaged_at`: `DateTimeField(null=True, blank=True)`
  - `investigation_required`: `BooleanField(default=True, help_text="Is formal failure analysis / DHR investigation required?")`
  - `no_investigation_rationale`: `TextField(blank=True, help_text="Regulatory justification if formal investigation was bypassed")`
  - `resolution_summary`: `TextField(blank=True, help_text="Customer-facing resolution and corrective summary")`
  - `customer_letter_sent`: `BooleanField(default=False)`
  - `customer_letter_date`: `DateField(null=True, blank=True)`
  - `closed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="closed_complaints")`
  - `closed_at`: `DateTimeField(null=True, blank=True)`
  - `assigned_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_complaints")`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcmp_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qcmp_ten_status")` (19)
  - `Index(fields=["tenant", "severity"], name="idx_qcmp_ten_sev")` (16)
  - `Index(fields=["tenant", "reportability"], name="idx_qcmp_ten_rep")` (16)
  - `Index(fields=["tenant", "validity"], name="idx_qcmp_ten_val")` (16)
  - `Index(fields=["tenant", "item_code"], name="idx_qcmp_ten_item")` (17)
  - `Index(fields=["tenant", "lot_number"], name="idx_qcmp_ten_lot")` (16)
  - `Index(fields=["tenant", "date_received"], name="idx_qcmp_ten_drcv")` (17)
  - `Index(fields=["tenant", "-created_at"], name="idx_qcmp_ten_created")` (20)

---

### 1.2 `ComplaintInvestigation` (`ComplaintInvestigations.py`)
- **`NUMBER_PREFIX`**: `"QCIN"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Complaint Investigation"` / `"Complaint Investigations"`
- **Choices & Badge Maps**:
  - `INVESTIGATION_STATUS_CHOICES` (`max_length=30`):
    - `("assigned", "Assigned / Pending Analysis")`
    - `("in_progress", "Lab & DHR Analysis In Progress")`
    - `("pending_sample", "Awaiting Return Sample Delivery")`
    - `("hhe_review", "Clinical Health Hazard Review")`
    - `("pending_qa_review", "Pending QA Manager Sign-Off")`
    - `("approved", "Investigation Approved & Closed")`
    - `("rejected_rework", "Rejected (Requires Rework)")`
  - `ANALYTICAL_METHOD_CHOICES` (`max_length=32`):
    - `("visual_microscopy", "Visual & Optical Microscopy")`
    - `("dimensional_metrology", "Dimensional Metrology & CMM")`
    - `("mechanical_stress", "Mechanical Stress / Tensile Testing")`
    - `("electrical_functional", "Electrical Functional Diagnostic")`
    - `("chemical_spectroscopy", "Chemical Spectroscopy / FTIR")`
    - `("software_code_audit", "Software Trace & Log Audit")`
    - `("historical_data_review", "Historical DHR & Batch Audit Only")`
    - `("other", "Other Specialized Laboratory Method")`
  - `ROOT_CAUSE_CATEGORY_CHOICES` (`max_length=32`):
    - `("component_defect", "Raw Material / Component Defect")`
    - `("assembly_workmanship", "Manufacturing / Assembly Workmanship")`
    - `("process_deviation", "Equipment / Process Parameter Drift")`
    - `("design_flaw", "Design Flaw / Specification Inadequacy")`
    - `("software_bug", "Firmware / Software Bug")`
    - `("packaging_barrier", "Sterile Packaging / Barrier Breach")`
    - `("transit_damage", "Storage / Transportation / Transit Damage")`
    - `("user_error_misuse", "User Operational Error / Clinical Misuse")`
    - `("unconfirmed_no_defect", "Unconfirmed / No Defect Found (NDF)")`
    - `("other", "Other Root Cause")`
  - `STATUS_CSS`:
    - `"assigned": "badge-info"`
    - `"in_progress": "badge-amber"`
    - `"pending_sample": "badge-slate"`
    - `"hhe_review": "badge-purple"`
    - `"pending_qa_review": "badge-amber"`
    - `"approved": "badge-green"`
    - `"rejected_rework": "badge-red"`

- **Fields**:
  - `complaint`: `ForeignKey("quality.CustomerComplaint", on_delete=models.CASCADE, related_name="investigations", help_text="Parent customer complaint")`
  - `lead_investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lead_complaint_investigations")`
  - `target_completion_date`: `DateField(null=True, blank=True)`
  - `actual_completion_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=30, choices=INVESTIGATION_STATUS_CHOICES, default="assigned", db_index=True)`
  - `dhr_reviewed`: `BooleanField(default=False, help_text="Was the Device History Record / Batch Record reviewed?")`
  - `dhr_lot_number`: `CharField(max_length=100, blank=True, help_text="Batch/DHR examined")`
  - `dhr_quantity_produced`: `PositiveIntegerField(default=0, help_text="Total units produced in examined batch")`
  - `dhr_anomalies_identified`: `BooleanField(default=False, help_text="Were non-conformances or deviations recorded in batch history?")`
  - `dhr_review_summary`: `TextField(blank=True, help_text="Detailed notes from manufacturing and testing records")`
  - `physical_sample_examined`: `BooleanField(default=False)`
  - `analytical_method`: `CharField(max_length=32, choices=ANALYTICAL_METHOD_CHOICES, default="visual_microscopy", db_index=True)`
  - `sample_testing_findings`: `TextField(blank=True, help_text="Laboratory diagnostics and observed failure mode")`
  - `failure_reproduced`: `BooleanField(default=False, help_text="Was customer reported failure replicated under test conditions?")`
  - `hhe_required`: `BooleanField(default=False, help_text="Is a Health Hazard Evaluation (HHE) clinically mandated?")`
  - `health_hazard_evaluation`: `TextField(blank=True, help_text="Clinical medical assessment of patient/user injury likelihood and severity")`
  - `risk_assessment`: `ForeignKey("quality.RiskAssessment", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaint_investigations", help_text="Linked ISO 14971 FMEA Risk Assessment")`
  - `risk_exceeds_threshold`: `BooleanField(default=False, help_text="Does observed event frequency or severity exceed FMEA anticipated limits?")`
  - `root_cause_category`: `CharField(max_length=32, choices=ROOT_CAUSE_CATEGORY_CHOICES, default="unconfirmed_no_defect", db_index=True)`
  - `root_cause_narrative`: `TextField(blank=True, help_text="5 Whys or failure tree root cause analysis summary")`
  - `capa_required`: `BooleanField(default=False, help_text="Does root cause warrant formal CAPA initiation?")`
  - `capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaint_investigations", help_text="Linked CAPA record")`
  - `ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaint_investigations", help_text="Linked Non-Conformance Report")`
  - `investigation_conclusion`: `TextField(blank=True, help_text="Formal engineering conclusion and risk disposition")`
  - `qa_approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_complaint_investigations")`
  - `qa_approved_date`: `DateField(null=True, blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcin_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qcin_ten_status")` (19)
  - `Index(fields=["tenant", "complaint"], name="idx_qcin_ten_cmp")` (16)
  - `Index(fields=["tenant", "root_cause_category"], name="idx_qcin_ten_rcat")` (17)
  - `Index(fields=["tenant", "lead_investigator"], name="idx_qcin_ten_inv")` (16)
  - `Index(fields=["tenant", "-created_at"], name="idx_qcin_ten_created")` (20)

---

### 1.3 `RegulatoryReport` (`RegulatoryReports.py`)
- **`NUMBER_PREFIX`**: `"QRPT"`
- **`Meta.ordering`**: `["statutory_due_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Regulatory Vigilance Report"` / `"Regulatory Vigilance Reports"`
- **Choices & Badge Maps**:
  - `AGENCY_CHOICES` (`max_length=30`):
    - `("fda_cdrh", "FDA CDRH (Medical Devices / eMDR)")`
    - `("fda_cder", "FDA CDER (Pharmaceuticals / FAERS)")`
    - `("eu_competent_auth", "EU Competent Authority (EUDAMED / MIR)")`
    - `("health_canada", "Health Canada Medical Device Directorate")`
    - `("pmda_japan", "PMDA Japan (Pharmaceuticals & Medical Devices)")`
    - `("tga_australia", "TGA Australia Therapeutic Goods Admin")`
    - `("mhra_uk", "MHRA UK Medicines & Healthcare Products")`
    - `("other_authority", "Other National Regulatory Authority")`
  - `REPORT_TYPE_CHOICES` (`max_length=32`):
    - `("initial_report", "Initial Adverse Event Report")`
    - `("follow_up_supplemental", "Follow-up / Supplemental Report")`
    - `("final_closure_report", "Final Investigation / Closure Report")`
    - `("non_reportable_justification", "Non-Reportable Decision Documentation")`
  - `ADVERSE_EVENT_CLASS_CHOICES` (`max_length=32`):
    - `("death", "Death Allegation")`
    - `("serious_injury", "Serious Injury / Life-Threatening")`
    - `("malfunction_recurrent", "Malfunction with Recurrence Potential")`
    - `("public_health_threat", "Public Health Threat / Outbreak")`
    - `("remedial_action_trigger", "Statutory Field Remedial Action")`
  - `TIMELINE_CATEGORY_CHOICES` (`max_length=32`):
    - `("2_day_public_health", "2-Day Public Health Threat Clock")`
    - `("5_day_remedial", "5-Day Remedial Action / Urgent Clock")`
    - `("10_day_death_deterioration", "10-Day Death / Unanticipated Deterioration")`
    - `("15_day_serious_incident", "15-Day EU MIR Serious Incident Clock")`
    - `("30_day_standard_mdr", "30-Day Standard FDA MDR / Annual Clock")`
  - `SUBMISSION_STATUS_CHOICES` (`max_length=30`):
    - `("draft", "Draft / In Preparation")`
    - `("under_internal_review", "Under Regulatory Affairs Review")`
    - `("ready_to_transmit", "Approved & Ready to Transmit")`
    - `("submitted", "Submitted to Agency Gateway")`
    - `("acknowledged", "Agency Acknowledged & Accepted")`
    - `("rejected_supplement_needed", "Agency Deficient / Supplemental Required")`
    - `("withdrawn", "Formally Withdrawn / Voided")`
  - `SUBMISSION_FORMAT_CHOICES` (`max_length=30`):
    - `("fda_medwatch_3500a", "FDA MedWatch Form 3500A (Paper/PDF)")`
    - `("fda_emdr_xml", "FDA eMDR Gateway (XML AS2)")`
    - `("eu_mir_xml", "EU MIR Manufacturer Incident Report XML")`
    - `("eudamed_portal", "EUDAMED Web Portal Upload")`
    - `("health_canada_portal", "Health Canada Regulatory Web Portal")`
    - `("other_transmission", "Other Electronic / Secure Transmission")`
  - `AGENCY_CSS`:
    - `"fda_cdrh": "badge-blue"`
    - `"fda_cder": "badge-info"`
    - `"eu_competent_auth": "badge-purple"`
    - `"health_canada": "badge-red"`
    - `"pmda_japan": "badge-amber"`
    - `"tga_australia": "badge-green"`
    - `"mhra_uk": "badge-slate"`
    - `"other_authority": "badge-muted"`
  - `SUBMISSION_STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"under_internal_review": "badge-amber"`
    - `"ready_to_transmit": "badge-info"`
    - `"submitted": "badge-purple"`
    - `"acknowledged": "badge-green"`
    - `"rejected_supplement_needed": "badge-red"`
    - `"withdrawn": "badge-muted"`

- **Fields**:
  - `complaint`: `ForeignKey("quality.CustomerComplaint", on_delete=models.CASCADE, related_name="regulatory_reports", help_text="Associated customer complaint")`
  - `agency`: `CharField(max_length=30, choices=AGENCY_CHOICES, default="fda_cdrh", db_index=True)`
  - `report_type`: `CharField(max_length=32, choices=REPORT_TYPE_CHOICES, default="initial_report", db_index=True)`
  - `adverse_event_class`: `CharField(max_length=32, choices=ADVERSE_EVENT_CLASS_CHOICES, default="malfunction_recurrent", db_index=True)`
  - `timeline_category`: `CharField(max_length=32, choices=TIMELINE_CATEGORY_CHOICES, default="30_day_standard_mdr", db_index=True)`
  - `statutory_due_date`: `DateField(db_index=True, help_text="Legally mandated agency transmission deadline")`
  - `submission_status`: `CharField(max_length=30, choices=SUBMISSION_STATUS_CHOICES, default="draft", db_index=True)`
  - `submission_format`: `CharField(max_length=30, choices=SUBMISSION_FORMAT_CHOICES, default="fda_emdr_xml")`
  - `submission_date`: `DateField(null=True, blank=True, help_text="Date report was transmitted to agency")`
  - `agency_report_identifier`: `CharField(max_length=100, blank=True, help_text="Agency reference / case file number (e.g. FDA MDR #, EU MIR ID)")`
  - `agency_acknowledgement_number`: `CharField(max_length=100, blank=True, help_text="Electronic submission gateway receipt / ACK number")`
  - `agency_acknowledgement_date`: `DateField(null=True, blank=True)`
  - `event_summary`: `TextField(help_text="Official medical adverse event narrative for regulatory submission")`
  - `device_operator`: `CharField(max_length=64, blank=True, help_text="e.g. 'Healthcare Professional', 'Patient', 'Lay User'")`
  - `patient_remedial_action`: `TextField(blank=True, help_text="Medical interventions, surgeries, or therapies administered to patient")`
  - `prepared_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_regulatory_reports")`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_regulatory_reports")`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrpt_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "submission_status"], name="idx_qrpt_ten_status")` (19)
  - `Index(fields=["tenant", "agency"], name="idx_qrpt_ten_agency")` (19)
  - `Index(fields=["tenant", "statutory_due_date"], name="idx_qrpt_ten_due")` (16)
  - `Index(fields=["tenant", "complaint"], name="idx_qrpt_ten_cmp")` (16)
  - `Index(fields=["tenant", "-created_at"], name="idx_qrpt_ten_created")` (20)

---

### 1.4 `FieldAction` (`FieldActions.py`)
- **`NUMBER_PREFIX`**: `"QFMA"`
- **`Meta.ordering`**: `["-initiation_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Field Action & Recall"` / `"Field Actions & Recalls"`
- **Choices & Badge Maps**:
  - `ACTION_TYPE_CHOICES` (`max_length=32`):
    - `("recall_removal", "Product Recall (Physical Removal / Return)")`
    - `("fsca_safety_notice", "Field Safety Corrective Action (FSCA / Notice)")`
    - `("field_correction_rework", "Field Correction / Software Patch / On-site Rework")`
    - `("safety_advisory_alert", "Safety Advisory / Updated Instructions for Use")`
    - `("market_withdrawal", "Market Withdrawal (Non-Violative Commercial)")`
  - `RECALL_CLASS_CHOICES` (`max_length=32`):
    - `("class_i_critical", "Class I Recall (High Risk: Death / Serious Injury)")`
    - `("class_ii_moderate", "Class II Recall (Moderate Risk: Temporary / Reversible)")`
    - `("class_iii_minor", "Class III Recall (Low Risk: Unlikely Health Consequence)")`
    - `("fsca_safety_alert", "Field Safety Alert (Advisory Only)")`
    - `("not_classified", "Unclassified / Initial Assessment")`
  - `ACTION_STATUS_CHOICES` (`max_length=30`):
    - `("planning", "Strategy & Health Hazard Evaluation")`
    - `("regulatory_consultation", "Agency Notification & Recall Strategy Review")`
    - `("notifications_dispatched", "Consignee Notifications Dispatched")`
    - `("quarantine_in_progress", "Field Quarantine & Recovery In Progress")`
    - `("reconciliation_complete", "Reconciliation Complete (Audit In Progress)")`
    - `("closed_terminated", "Recall Terminated & Agency Concurred")`
    - `("cancelled", "Cancelled / Abandoned")`
  - `ACTION_TYPE_CSS`:
    - `"recall_removal": "badge-red"`
    - `"fsca_safety_notice": "badge-amber"`
    - `"field_correction_rework": "badge-info"`
    - `"safety_advisory_alert": "badge-slate"`
    - `"market_withdrawal": "badge-muted"`
  - `RECALL_CLASS_CSS`:
    - `"class_i_critical": "badge-red"`
    - `"class_ii_moderate": "badge-amber"`
    - `"class_iii_minor": "badge-info"`
    - `"fsca_safety_alert": "badge-purple"`
    - `"not_classified": "badge-slate"`
  - `STATUS_CSS`:
    - `"planning": "badge-slate"`
    - `"regulatory_consultation": "badge-amber"`
    - `"notifications_dispatched": "badge-info"`
    - `"quarantine_in_progress": "badge-amber"`
    - `"reconciliation_complete": "badge-purple"`
    - `"closed_terminated": "badge-green"`
    - `"cancelled": "badge-muted"`

- **Fields**:
  - `title`: `CharField(max_length=255, help_text="Recall / Field Action title")`
  - `action_type`: `CharField(max_length=32, choices=ACTION_TYPE_CHOICES, default="recall_removal", db_index=True)`
  - `recall_class`: `CharField(max_length=32, choices=RECALL_CLASS_CHOICES, default="not_classified", db_index=True)`
  - `initiating_complaint`: `ForeignKey("quality.CustomerComplaint", on_delete=models.SET_NULL, null=True, blank=True, related_name="field_actions", help_text="Triggering customer complaint")`
  - `coordinator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="coordinated_field_actions")`
  - `initiation_date`: `DateField(db_index=True, help_text="Official initiation date of the field action")`
  - `status`: `CharField(max_length=30, choices=ACTION_STATUS_CHOICES, default="planning", db_index=True)`
  - `affected_product_code`: `CharField(max_length=100, db_index=True, help_text="Affected item / model catalog code")`
  - `affected_product_name`: `CharField(max_length=255, help_text="Commercial product name")`
  - `affected_lot_numbers`: `TextField(help_text="Comma-separated or list of recalled batch/lot numbers")`
  - `distribution_start_date`: `DateField(null=True, blank=True, help_text="Earliest shipment date of affected lots")`
  - `distribution_end_date`: `DateField(null=True, blank=True, help_text="Latest shipment date of affected lots")`
  - `reason_for_action`: `TextField(help_text="Statement of defect, failure mode, and health hazard justification")`
  - `hhe_summary`: `TextField(blank=True, help_text="Clinical Health Hazard Evaluation risk assessment rationale")`
  - `fsn_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="field_actions", help_text="Controlled Field Safety Notice customer communication letter")`
  - `total_units_distributed`: `PositiveIntegerField(default=0, help_text="Total population of affected units shipped to commerce")`
  - `consignees_targeted`: `PositiveIntegerField(default=0, help_text="Total number of accounts / hospitals receiving notification")`
  - `consignees_notified`: `PositiveIntegerField(default=0, help_text="Number of consignees successfully delivered notification")`
  - `consignees_responded`: `PositiveIntegerField(default=0, help_text="Number of consignees returning acknowledgment certificates")`
  - `units_quarantined_field`: `PositiveIntegerField(default=0, help_text="Units held in customer quarantine awaiting disposition")`
  - `units_recovered_destroyed`: `PositiveIntegerField(default=0, help_text="Units physically returned to factory or certified destroyed")`
  - `regulatory_agency_notified`: `CharField(max_length=100, blank=True, help_text="e.g. FDA CDRH Recall Operations, BfArM, MHRA")`
  - `regulatory_recall_number`: `CharField(max_length=100, blank=True, help_text="Agency designated recall classification identifier (e.g. FDA Z-####-2026)")`
  - `agency_notification_date`: `DateField(null=True, blank=True)`
  - `termination_date`: `DateField(null=True, blank=True, help_text="Date regulatory authority formally concurred with recall closure")`
  - `closure_summary`: `TextField(blank=True, help_text="Final effectiveness audit and reconciliation summary")`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qfma_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qfma_ten_status")` (19)
  - `Index(fields=["tenant", "action_type"], name="idx_qfma_ten_atype")` (18)
  - `Index(fields=["tenant", "recall_class"], name="idx_qfma_ten_rclass")` (19)
  - `Index(fields=["tenant", "affected_product_code"], name="idx_qfma_ten_pcode")` (18)
  - `Index(fields=["tenant", "initiation_date"], name="idx_qfma_ten_idate")` (18)
  - `Index(fields=["tenant", "-created_at"], name="idx_qfma_ten_created")` (20)

---

## 2. Forms Contract (`apps/quality/forms/CustomerComplaints/`)

All forms inherit `forms.ModelForm` and enforce tenant scoping on querysets in `__init__(self, *args, **kwargs)` where `tenant = kwargs.pop('tenant', None)`. All cross-tenant foreign keys are rejected in `clean()`.

### 2.1 `CustomerComplaintForm` (`CustomerComplaints.py`)
- **Excludes**: `["tenant", "number", "created_at", "updated_at", "triaged_by", "triaged_at", "closed_by", "closed_at"]`
- **Tenant-scoped FKs**: `customer` (`core.Party`), `sales_order` (`scm.SalesOrder`), `return_authorization` (`scm.ReturnAuthorization`), `assigned_to` (`accounts.User`).
- **Validation**: If `reportability == "non_reportable"`, `non_reportable_justification` must be provided. If `investigation_required is False`, `no_investigation_rationale` must be provided.

### 2.2 `ComplaintTriageForm` (`CustomerComplaints.py`)
- Lightweight triage form: `validity`, `severity`, `reportability`, `non_reportable_justification`, `complaint_category`, `investigation_required`, `no_investigation_rationale`, `assigned_to`, `triage_notes`.

### 2.3 `ComplaintInvestigationForm` (`ComplaintInvestigations.py`)
- **Excludes**: `["tenant", "number", "created_at", "updated_at", "qa_approved_by", "qa_approved_date"]`
- **Tenant-scoped FKs**: `complaint` (`quality.CustomerComplaint`), `lead_investigator` (`accounts.User`), `risk_assessment` (`quality.RiskAssessment`), `capa` (`quality.CapaInvestigation`), `ncr` (`quality.NonConformanceReport`).
- **Validation**: If `capa_required is True`, `investigation_conclusion` or linked `capa`/`ncr` must be documented.

### 2.4 `RegulatoryReportForm` (`RegulatoryReports.py`)
- **Excludes**: `["tenant", "number", "created_at", "updated_at", "agency_acknowledgement_date"]`
- **Tenant-scoped FKs**: `complaint` (`quality.CustomerComplaint`), `prepared_by` (`accounts.User`), `reviewed_by` (`accounts.User`).
- **Validation**: `statutory_due_date` required.

### 2.5 `FieldActionForm` (`FieldActions.py`)
- **Excludes**: `["tenant", "number", "created_at", "updated_at"]`
- **Tenant-scoped FKs**: `initiating_complaint` (`quality.CustomerComplaint`), `coordinator` (`accounts.User`), `fsn_document` (`quality.ControlledDocument`).
- **Validation**: `affected_lot_numbers` and `reason_for_action` required. `total_units_distributed >= units_recovered_destroyed + units_quarantined_field`.

---

## 3. URLs and Route Names (`apps/quality/urls/CustomerComplaints/`)

All literal routes defined BEFORE `<int:pk>` (first-match-wins rule):

```python
# CustomerComplaints.py
urlpatterns = [
    path("complaints/", views.customer_complaint_list, name="customer_complaint_list"),
    path("complaints/create/", views.customer_complaint_create, name="customer_complaint_create"),
    path("complaints/export/csv/", views.customer_complaint_export_csv, name="customer_complaint_export_csv"),
    path("complaints/<int:pk>/", views.customer_complaint_detail, name="customer_complaint_detail"),
    path("complaints/<int:pk>/edit/", views.customer_complaint_edit, name="customer_complaint_edit"),
    path("complaints/<int:pk>/delete/", views.customer_complaint_delete, name="customer_complaint_delete"),
    path("complaints/<int:pk>/triage/", views.customer_complaint_triage, name="customer_complaint_triage"),
    path("complaints/<int:pk>/close/", views.customer_complaint_close, name="customer_complaint_close"),
]

# ComplaintInvestigations.py
urlpatterns = [
    path("investigations/", views.complaint_investigation_list, name="complaint_investigation_list"),
    path("investigations/create/", views.complaint_investigation_create, name="complaint_investigation_create"),
    path("investigations/export/csv/", views.complaint_investigation_export_csv, name="complaint_investigation_export_csv"),
    path("investigations/<int:pk>/", views.complaint_investigation_detail, name="complaint_investigation_detail"),
    path("investigations/<int:pk>/edit/", views.complaint_investigation_edit, name="complaint_investigation_edit"),
    path("investigations/<int:pk>/delete/", views.complaint_investigation_delete, name="complaint_investigation_delete"),
    path("investigations/<int:pk>/complete/", views.complaint_investigation_complete, name="complaint_investigation_complete"),
]

# RegulatoryReports.py
urlpatterns = [
    path("regulatory-reports/", views.regulatory_report_list, name="regulatory_report_list"),
    path("regulatory-reports/create/", views.regulatory_report_create, name="regulatory_report_create"),
    path("regulatory-reports/export/csv/", views.regulatory_report_export_csv, name="regulatory_report_export_csv"),
    path("regulatory-reports/<int:pk>/", views.regulatory_report_detail, name="regulatory_report_detail"),
    path("regulatory-reports/<int:pk>/edit/", views.regulatory_report_edit, name="regulatory_report_edit"),
    path("regulatory-reports/<int:pk>/delete/", views.regulatory_report_delete, name="regulatory_report_delete"),
    path("regulatory-reports/<int:pk>/submit/", views.regulatory_report_submit, name="regulatory_report_submit"),
    path("regulatory-reports/<int:pk>/acknowledge/", views.regulatory_report_acknowledge, name="regulatory_report_acknowledge"),
]

# FieldActions.py
urlpatterns = [
    path("field-actions/", views.field_action_list, name="field_action_list"),
    path("field-actions/create/", views.field_action_create, name="field_action_create"),
    path("field-actions/export/csv/", views.field_action_export_csv, name="field_action_export_csv"),
    path("field-actions/<int:pk>/", views.field_action_detail, name="field_action_detail"),
    path("field-actions/<int:pk>/edit/", views.field_action_edit, name="field_action_edit"),
    path("field-actions/<int:pk>/delete/", views.field_action_delete, name="field_action_delete"),
    path("field-actions/<int:pk>/close/", views.field_action_close, name="field_action_close"),
]

# ComplaintTrendingDashboard.py
urlpatterns = [
    path("trending/", views.complaint_trending_dashboard, name="complaint_trending_dashboard"),
]
```

---

## 4. View Context Keys Contract (`apps/quality/views/CustomerComplaints/`)

### 4.1 `CustomerComplaint` Views
- **List** (`customer_complaint_list`):
  - `complaints`: page slice of `CustomerComplaint` objects
  - `page_obj`: paginator page object
  - `paginator`: Paginator instance
  - `is_paginated`: boolean
  - `total_count`: total records matching filters
  - `intake_channel_choices`: `CustomerComplaint.INTAKE_CHANNEL_CHOICES`
  - `severity_choices`: `CustomerComplaint.SEVERITY_CHOICES`
  - `status_choices`: `CustomerComplaint.COMPLAINT_STATUS_CHOICES`
  - `validity_choices`: `CustomerComplaint.VALIDITY_CHOICES`
  - `reportability_choices`: `CustomerComplaint.REPORTABILITY_CHOICES`
  - `open_count`: int
  - `reportable_count`: int
  - `critical_count`: int
- **Detail** (`customer_complaint_detail`):
  - `complaint`: `CustomerComplaint` instance
  - `investigations`: queryset of linked `ComplaintInvestigation`
  - `reports`: queryset of linked `RegulatoryReport`
  - `field_actions`: queryset of linked `FieldAction`
  - `triage_form`: `ComplaintTriageForm` (if under triage)
- **Create/Edit** (`customer_complaint_create`, `customer_complaint_edit`):
  - `form`: `CustomerComplaintForm`
  - `complaint`: `CustomerComplaint` instance (on edit only)
  - `is_edit`: boolean

### 4.2 `ComplaintInvestigation` Views
- **List** (`complaint_investigation_list`):
  - `investigations`: page slice
  - `page_obj`: paginator page object
  - `paginator`: Paginator instance
  - `is_paginated`: boolean
  - `total_count`: total records
  - `status_choices`: `ComplaintInvestigation.INVESTIGATION_STATUS_CHOICES`
  - `analytical_method_choices`: `ComplaintInvestigation.ANALYTICAL_METHOD_CHOICES`
  - `root_cause_category_choices`: `ComplaintInvestigation.ROOT_CAUSE_CATEGORY_CHOICES`
  - `in_progress_count`: int
  - `capa_triggered_count`: int
- **Detail** (`complaint_investigation_detail`):
  - `investigation`: `ComplaintInvestigation` instance
- **Create/Edit** (`complaint_investigation_create`, `complaint_investigation_edit`):
  - `form`: `ComplaintInvestigationForm`
  - `investigation`: `ComplaintInvestigation` instance (on edit)
  - `is_edit`: boolean

### 4.3 `RegulatoryReport` Views
- **List** (`regulatory_report_list`):
  - `reports`: page slice
  - `page_obj`: paginator page object
  - `paginator`: Paginator instance
  - `is_paginated`: boolean
  - `total_count`: total records
  - `agency_choices`: `RegulatoryReport.AGENCY_CHOICES`
  - `report_type_choices`: `RegulatoryReport.REPORT_TYPE_CHOICES`
  - `submission_status_choices`: `RegulatoryReport.SUBMISSION_STATUS_CHOICES`
  - `timeline_category_choices`: `RegulatoryReport.TIMELINE_CATEGORY_CHOICES`
  - `pending_submission_count`: int
  - `overdue_count`: int
- **Detail** (`regulatory_report_detail`):
  - `report`: `RegulatoryReport` instance
- **Create/Edit** (`regulatory_report_create`, `regulatory_report_edit`):
  - `form`: `RegulatoryReportForm`
  - `report`: `RegulatoryReport` instance (on edit)
  - `is_edit`: boolean

### 4.4 `FieldAction` Views
- **List** (`field_action_list`):
  - `field_actions`: page slice
  - `page_obj`: paginator page object
  - `paginator`: Paginator instance
  - `is_paginated`: boolean
  - `total_count`: total records
  - `action_type_choices`: `FieldAction.ACTION_TYPE_CHOICES`
  - `recall_class_choices`: `FieldAction.RECALL_CLASS_CHOICES`
  - `status_choices`: `FieldAction.ACTION_STATUS_CHOICES`
  - `active_recall_count`: int
  - `class_i_count`: int
- **Detail** (`field_action_detail`):
  - `field_action`: `FieldAction` instance
- **Create/Edit** (`field_action_create`, `field_action_edit`):
  - `form`: `FieldActionForm`
  - `field_action`: `FieldAction` instance (on edit)
  - `is_edit`: boolean

### 4.5 `ComplaintTrendingDashboard` View
- **Dashboard** (`complaint_trending_dashboard`):
  - `total_complaints_ytd`: int
  - `open_complaints`: int
  - `reportable_adverse_events`: int
  - `active_field_recalls`: int
  - `avg_cycle_days`: float
  - `category_distribution`: list of dicts `[{"category": ..., "count": ...}]`
  - `severity_distribution`: list of dicts `[{"severity": ..., "label": ..., "count": ..., "css": ...}]`
  - `intake_channel_stats`: list of dicts `[{"channel": ..., "label": ..., "count": ...}]`
  - `root_cause_pareto`: list of dicts `[{"cause": ..., "label": ..., "count": ...}]`
  - `urgent_regulatory_deadlines`: list of `RegulatoryReport` objects due soon
  - `active_recalls`: list of `FieldAction` objects in execution

---

## 5. Sidebar Navigation Wire-Up (`apps/core/navigation.py`)

`LIVE_LINKS["12.13"]`:
```python
    "12.13": {
        "Complaint Intake & Triage": "quality:customer_complaint_list",
        "Investigation & Root Cause Analysis": "quality:complaint_investigation_list",
        "Regulatory Reporting & Vigilance": "quality:regulatory_report_list",
        "Field Action & Recall Management": "quality:field_action_list",
        "Complaint Trending & Closure": "quality:complaint_trending_dashboard",
    },
```

---

## 6. Verification and Smoke Invariants
- `python manage.py check` must report 0 issues.
- `python manage.py makemigrations quality` generates incremental migration `0020_...`.
- `python manage.py migrate quality` applies cleanly.
- `python manage.py seed_quality` runs twice idempotently without unique constraint violations.
- Smoke script renders all 29 URLs as `admin_acme` (200/302), checks for zero `{#` / `{% comment` leaks, validates that IDOR access across tenants yields 404, checks that filter params with non-numeric strings do not 500 (L11), checks that pagination on page 2 works without `EmptyPage` error (L9).
