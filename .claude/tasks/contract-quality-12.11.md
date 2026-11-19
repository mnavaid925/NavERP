# Module 12.11 Pre-Build Contract — Audit Management (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.11"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0019_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/AuditManagement/`
  - `apps/quality/forms/AuditManagement/`
  - `apps/quality/views/AuditManagement/`
  - `apps/quality/urls/AuditManagement/`
  - `templates/quality/auditmanagement/{audit_program,quality_audit,audit_finding,regulatory_inspection_host}/{list,detail,form}.html` + `templates/quality/auditmanagement/audit_action_tracker.html` + `templates/quality/auditmanagement/audit_war_room.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"approve"`, `"close"`, `"publish"`, `"respond"`, `"verify"`, `"request"`, `"fulfill"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `core.Party`, `quality.AuditProgram`, `quality.QualityAudit`, `quality.ControlledDocument`, `quality.CapaInvestigation`, `quality.NonConformanceReport`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/AuditManagement/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `AuditProgram` (`AuditPrograms.py`)
- **`NUMBER_PREFIX`**: `"QPRG"`
- **`Meta.ordering`**: `["-program_year", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Quality Audit Program"` / `"Quality Audit Programs"`
- **Choices & Badge Maps**:
  - `PROGRAM_TYPE_CHOICES` (`max_length=32`):
    - `("internal_qms", "Internal QMS Audits")`
    - `("supplier_external", "Supplier & External Vendor Audits")`
    - `("regulatory_certification", "Regulatory & Notified Body Audits")`
    - `("integrated_enterprise", "Integrated Enterprise Quality Program")`
  - `RISK_BASIS_CHOICES` (`max_length=32`):
    - `("low_risk_annual", "Low Risk (Annual)")`
    - `("medium_risk_biennial", "Medium Risk (Biennial)")`
    - `("high_risk_semi_annual", "High Risk / Critical (Semi-Annual)")`
    - `("for_cause_triggered", "For-Cause / Event Triggered")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Draft")`
    - `("submitted", "Submitted for Approval")`
    - `("approved", "Approved")`
    - `("active", "Active / In Execution")`
    - `("completed", "Completed")`
    - `("cancelled", "Cancelled")`
  - `PROGRAM_TYPE_CSS`:
    - `"internal_qms": "badge-info"`
    - `"supplier_external": "badge-slate"`
    - `"regulatory_certification": "badge-amber"`
    - `"integrated_enterprise": "badge-green"`
  - `RISK_BASIS_CSS`:
    - `"low_risk_annual": "badge-muted"`
    - `"medium_risk_biennial": "badge-info"`
    - `"high_risk_semi_annual": "badge-red"`
    - `"for_cause_triggered": "badge-amber"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"submitted": "badge-info"`
    - `"approved": "badge-green"`
    - `"active": "badge-green"`
    - `"completed": "badge-muted"`
    - `"cancelled": "badge-red"`

- **Fields**:
  - `title`: `CharField(max_length=255, help_text="e.g. FY2026 Enterprise Quality & Regulatory Audit Program")`
  - `program_year`: `PositiveIntegerField(help_text="Operating fiscal year e.g. 2026")`
  - `program_type`: `CharField(max_length=32, choices=PROGRAM_TYPE_CHOICES, default="internal_qms", db_index=True)`
  - `risk_basis`: `CharField(max_length=32, choices=RISK_BASIS_CHOICES, default="low_risk_annual", db_index=True)`
  - `scope_description`: `TextField(help_text="Scope boundaries, audit universe coverage, and strategic objectives")`
  - `start_date`: `DateField(help_text="Program validity start date")`
  - `end_date`: `DateField(help_text="Program validity end date")`
  - `allocated_budget_hours`: `PositiveIntegerField(default=0, help_text="Budgeted auditor person-hours")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `program_manager`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="managed_audit_programs")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_audit_programs")`
  - `approval_date`: `DateField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qprg_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qprg_ten_status")` (19)
  - `Index(fields=["tenant", "program_year"], name="idx_qprg_ten_year")` (17)
  - `Index(fields=["tenant", "program_type"], name="idx_qprg_ten_type")` (17)
  - `Index(fields=["tenant", "risk_basis"], name="idx_qprg_ten_risk")` (17)
  - `Index(fields=["tenant", "program_manager"], name="idx_qprg_ten_mgr")` (16)
  - `Index(fields=["tenant", "-created_at"], name="idx_qprg_ten_created")` (20)

- **Helper Properties**:
  - `progress_percentage`: computed int/float based on completed audits / total audits
  - `total_audits_count`: count of related `audits`
  - `completed_audits_count`: count of related `audits` where status="closed"
  - `open_audits_count`: count of related `audits` where status != "closed" and status != "cancelled"

---

### 1.2 `QualityAudit` (`QualityAudits.py`)
- **`NUMBER_PREFIX`**: `"QAUD"`
- **`Meta.ordering`**: `["-planned_start_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Quality Audit"` / `"Quality Audits"`
- **Choices & Badge Maps**:
  - `AUDIT_TYPE_CHOICES` (`max_length=40`):
    - `("internal_system", "Internal Quality System Audit")`
    - `("internal_process", "Manufacturing / Process Audit")`
    - `("internal_product", "Product Quality Audit")`
    - `("supplier_qualification", "Supplier Quality Audit")`
    - `("regulatory_fda", "FDA Regulatory Inspection")`
    - `("certification_notified_body", "ISO / Notified Body Audit")`
    - `("customer_audit", "Customer / Client Quality Audit")`
    - `("special_for_cause", "Special / For-Cause Investigation Audit")`
  - `AUDIT_METHOD_CHOICES` (`max_length=24`):
    - `("on_site", "On-Site Audit")`
    - `("remote_virtual", "Remote / Virtual Audit")`
    - `("hybrid", "Hybrid Audit")`
    - `("desk_audit", "Desk / Off-Site Document Review")`
  - `STANDARD_FRAMEWORK_CHOICES` (`max_length=32`):
    - `("iso_9001_2015", "ISO 9001:2015")`
    - `("iso_13485_2016", "ISO 13485:2016 (Medical Devices)")`
    - `("iatf_16949", "IATF 16949 (Automotive)")`
    - `("fda_21cfr820_qmsr", "FDA 21 CFR 820 / QMSR")`
    - `("eu_mdr_2017_745", "EU MDR 2017/745")`
    - `("gmp_21cfr211", "cGMP 21 CFR 211 (Pharma)")`
    - `("as9100d", "AS9100D (Aerospace)")`
    - `("multiple_frameworks", "Multiple Frameworks / Comprehensive")`
    - `("internal_sop", "Internal Quality SOPs")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("scheduled", "Scheduled")`
    - `("in_preparation", "In Preparation")`
    - `("in_progress", "In Progress / Fieldwork")`
    - `("reporting", "Reporting & Evaluation")`
    - `("capa_pending", "CAPA Follow-Up Pending")`
    - `("closed", "Closed")`
    - `("cancelled", "Cancelled")`
  - `OUTCOME_CHOICES` (`max_length=36`):
    - `("pending", "Assessment Pending")`
    - `("conforming", "Conforming (No Deficiencies)")`
    - `("minor_findings", "Minor Deficiencies Only")`
    - `("major_findings", "Major Deficiencies Identified")`
    - `("critical_non_conformance", "Critical Non-Conformance")`
    - `("passed", "Passed / Satisfactory")`
    - `("conditional_pass", "Conditional Approval")`
    - `("failed", "Failed / Unsatisfactory")`
  - `AUDIT_TYPE_CSS`:
    - `"internal_system": "badge-info"`
    - `"internal_process": "badge-info"`
    - `"internal_product": "badge-info"`
    - `"supplier_qualification": "badge-slate"`
    - `"regulatory_fda": "badge-red"`
    - `"certification_notified_body": "badge-amber"`
    - `"customer_audit": "badge-slate"`
    - `"special_for_cause": "badge-red"`
  - `AUDIT_METHOD_CSS`:
    - `"on_site": "badge-info"`
    - `"remote_virtual": "badge-slate"`
    - `"hybrid": "badge-amber"`
    - `"desk_audit": "badge-muted"`
  - `STATUS_CSS`:
    - `"scheduled": "badge-slate"`
    - `"in_preparation": "badge-info"`
    - `"in_progress": "badge-amber"`
    - `"reporting": "badge-info"`
    - `"capa_pending": "badge-amber"`
    - `"closed": "badge-green"`
    - `"cancelled": "badge-red"`
  - `OUTCOME_CSS`:
    - `"pending": "badge-muted"`
    - `"conforming": "badge-green"`
    - `"minor_findings": "badge-amber"`
    - `"major_findings": "badge-red"`
    - `"critical_non_conformance": "badge-red"`
    - `"passed": "badge-green"`
    - `"conditional_pass": "badge-amber"`
    - `"failed": "badge-red"`

- **Fields**:
  - `program`: `ForeignKey("quality.AuditProgram", on_delete=models.SET_NULL, null=True, blank=True, related_name="audits", help_text="Parent audit program (nullable for ad-hoc / unannounced audits)")`
  - `title`: `CharField(max_length=255, help_text="Audit title e.g. ISO 13485 Internal Audit - Design & Document Control")`
  - `audit_type`: `CharField(max_length=40, choices=AUDIT_TYPE_CHOICES, default="internal_system", db_index=True)`
  - `audit_method`: `CharField(max_length=24, choices=AUDIT_METHOD_CHOICES, default="on_site", db_index=True)`
  - `standard_framework`: `CharField(max_length=32, choices=STANDARD_FRAMEWORK_CHOICES, default="iso_13485_2016", db_index=True)`
  - `target_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="audited_org_units", help_text="Audited internal plant, department, or business unit")`
  - `external_entity`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="external_quality_audits", help_text="External supplier, registrar, or regulatory agency audited/auditing")`
  - `lead_auditor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="led_quality_audits")`
  - `auditee_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_quality_audits")`
  - `audit_checklist_sop`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="referenced_in_audits", help_text="Governing audit protocol, SOP, or checklist document")`
  - `planned_start_date`: `DateField(db_index=True)`
  - `planned_end_date`: `DateField()`
  - `actual_start_date`: `DateField(null=True, blank=True)`
  - `actual_end_date`: `DateField(null=True, blank=True)`
  - `scope_objectives`: `TextField(help_text="Detailed scope, processes evaluated, and criteria")`
  - `product_scope`: `CharField(max_length=255, blank=True, help_text="Product family or device name evaluated (Module 5 unbuilt item stand-in)")`
  - `lot_number_sampled`: `CharField(max_length=100, blank=True, help_text="Sampled production lot / batch number (Module 5 unbuilt lot stand-in)")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="scheduled", db_index=True)`
  - `outcome`: `CharField(max_length=36, choices=OUTCOME_CHOICES, default="pending", db_index=True)`
  - `executive_summary`: `TextField(blank=True, help_text="Summary of observations, strengths, and leadership conclusion")`
  - `report_published_date`: `DateField(null=True, blank=True)`
  - `total_findings_count`: `PositiveIntegerField(default=0)`
  - `critical_findings_count`: `PositiveIntegerField(default=0)`
  - `major_findings_count`: `PositiveIntegerField(default=0)`
  - `minor_findings_count`: `PositiveIntegerField(default=0)`
  - `ofi_findings_count`: `PositiveIntegerField(default=0)`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qaud_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qaud_ten_status")` (19)
  - `Index(fields=["tenant", "audit_type"], name="idx_qaud_ten_type")` (17)
  - `Index(fields=["tenant", "outcome"], name="idx_qaud_ten_outcome")` (20)
  - `Index(fields=["tenant", "planned_start_date"], name="idx_qaud_ten_pstart")` (19)
  - `Index(fields=["tenant", "program"], name="idx_qaud_ten_prog")` (17)
  - `Index(fields=["tenant", "target_org_unit"], name="idx_qaud_ten_unit")` (17)
  - `Index(fields=["tenant", "lead_auditor"], name="idx_qaud_ten_auditor")` (20)
  - `Index(fields=["tenant", "-created_at"], name="idx_qaud_ten_created")` (20)

- **Helper Properties**:
  - `is_overdue`: `date.today() > planned_end_date and status not in ("closed", "cancelled")`
  - `days_open`: days elapsed between actual_start_date (or planned_start_date) and actual_end_date/today
  - `open_findings_count`: count of child `findings` where status != "closed"

---

### 1.3 `AuditFinding` (`AuditFindings.py`)
- **`NUMBER_PREFIX`**: `"QFND"`
- **`Meta.ordering`**: `["-audit__planned_start_date", "finding_number_in_audit"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Audit Finding"` / `"Audit Findings"`
- **Choices & Badge Maps**:
  - `SEVERITY_CHOICES` (`max_length=24`):
    - `("critical", "Critical Non-Conformance (Immediate Regulatory / Safety Risk)")`
    - `("major", "Major Non-Conformance (Systemic Process Failure)")`
    - `("minor", "Minor Non-Conformance (Isolated Procedural Lapse)")`
    - `("observation_ofi", "Opportunity for Improvement (OFI)")`
    - `("commendation", "Commendation / Best Practice")`
  - `STATUS_CHOICES` (`max_length=32`):
    - `("draft", "Draft Finding")`
    - `("issued", "Issued to Auditee")`
    - `("response_submitted", "Remediation Response Submitted")`
    - `("response_accepted", "Response Accepted by Auditor")`
    - `("capa_in_progress", "CAPA Investigation In Progress")`
    - `("verification_pending", "Closure Verification Pending")`
    - `("closed", "Closed / Verified Effective")`
    - `("escalated", "Escalated / Past Due")`
  - `SEVERITY_CSS`:
    - `"critical": "badge-red"`
    - `"major": "badge-red"`
    - `"minor": "badge-amber"`
    - `"observation_ofi": "badge-info"`
    - `"commendation": "badge-green"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"issued": "badge-amber"`
    - `"response_submitted": "badge-info"`
    - `"response_accepted": "badge-info"`
    - `"capa_in_progress": "badge-amber"`
    - `"verification_pending": "badge-amber"`
    - `"closed": "badge-green"`
    - `"escalated": "badge-red"`

- **Fields**:
  - `audit`: `ForeignKey("quality.QualityAudit", on_delete=models.CASCADE, related_name="findings")`
  - `finding_number_in_audit`: `PositiveSmallIntegerField(default=1, help_text="Sequential number within this audit e.g. 1, 2, 3")`
  - `title`: `CharField(max_length=255, help_text="Finding headline / observation summary")`
  - `severity`: `CharField(max_length=24, choices=SEVERITY_CHOICES, default="minor", db_index=True)`
  - `standard_clause`: `CharField(max_length=128, help_text="Standard & clause cited e.g. ISO 13485:2016 §8.2.4, 21 CFR 820.22")`
  - `requirement_statement`: `TextField(help_text="Specified requirement, procedure, or regulation text")`
  - `condition_evidence`: `TextField(help_text="Objective evidence observed proving non-conformance")`
  - `audited_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="unit_audit_findings")`
  - `assignee`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_audit_findings", help_text="Auditee owner responsible for remediation")`
  - `response_due_date`: `DateField(db_index=True, help_text="Enforced turnaround SLA for auditee response")`
  - `response_received_date`: `DateField(null=True, blank=True)`
  - `containment_action`: `TextField(blank=True, help_text="Immediate correction taken to contain non-conformance")`
  - `root_cause_summary`: `TextField(blank=True, help_text="Root cause analysis submitted by auditee")`
  - `corrective_action_plan`: `TextField(blank=True, help_text="Proposed corrective action plan")`
  - `linked_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="source_audit_findings", help_text="Closed-loop CAPA investigation")`
  - `linked_ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="source_audit_findings", help_text="Immediate Non-Conformance Report")`
  - `status`: `CharField(max_length=32, choices=STATUS_CHOICES, default="issued", db_index=True)`
  - `closure_verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_audit_findings")`
  - `closed_date`: `DateField(null=True, blank=True)`
  - `closure_notes`: `TextField(blank=True, help_text="Lead auditor verification rationale and objective evidence of closure")`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qfnd_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qfnd_ten_status")` (19)
  - `Index(fields=["tenant", "severity"], name="idx_qfnd_ten_sev")` (16)
  - `Index(fields=["tenant", "audit"], name="idx_qfnd_ten_audit")` (18)
  - `Index(fields=["tenant", "assignee"], name="idx_qfnd_ten_assignee")` (21)
  - `Index(fields=["tenant", "response_due_date"], name="idx_qfnd_ten_due")` (16)
  - `Index(fields=["tenant", "linked_capa"], name="idx_qfnd_ten_capa")` (17)
  - `Index(fields=["tenant", "-created_at"], name="idx_qfnd_ten_created")` (20)

- **Helper Properties**:
  - `is_overdue`: `date.today() > response_due_date and status in ("draft", "issued")`
  - `requires_capa`: `severity in ("critical", "major") and not linked_capa_id`

---

### 1.4 `RegulatoryInspectionHost` (`RegulatoryInspectionHosts.py`)
- **`NUMBER_PREFIX`**: `"QHST"`
- **`Meta.ordering`**: `["-scheduled_start_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Regulatory Inspection Host Record"` / `"Regulatory Inspection Host Records"`
- **Choices & Badge Maps**:
  - `AGENCY_CHOICES` (`max_length=32`):
    - `("fda_cdrh", "US FDA - CDRH (Medical Devices)")`
    - `("fda_cder", "US FDA - CDER (Pharmaceuticals)")`
    - `("iso_notified_body", "EU Notified Body (MDR/IVDR)")`
    - `("ema_eu", "European Medicines Agency (EMA)")`
    - `("health_canada", "Health Canada")`
    - `("pmda_japan", "PMDA Japan")`
    - `("customer_corporate", "Customer Corporate Quality Audit")`
    - `("iso_registrar", "ISO Accredited Registrar")`
    - `("other_authority", "Other Regulatory / Health Authority")`
  - `PURPOSE_CHOICES` (`max_length=32`):
    - `("routine_surveillance", "Routine cGMP / QMS Surveillance")`
    - `("pre_approval_pma_nda", "Pre-Approval Inspection (PAI / PMA)")`
    - `("for_cause_directed", "For-Cause / Directed Investigation")`
    - `("unannounced_inspection", "Unannounced Facility Inspection")`
    - `("mdsap_audit", "MDSAP Comprehensive Audit")`
    - `("recertification_audit", "Triennial Recertification Audit")`
  - `ANNOUNCEMENT_CHOICES` (`max_length=24`):
    - `("announced", "Announced")`
    - `("unannounced", "Unannounced")`
    - `("short_notice", "Short Notice (< 48 Hours)")`
  - `STATUS_CHOICES` (`max_length=32`):
    - `("preparation", "Pre-Inspection Preparation")`
    - `("active_inspection", "Active Inspection In Session")`
    - `("daily_wrapup", "Daily Debrief / Wrap-up")`
    - `("inspection_closed", "Inspection Closed / Exit Complete")`
    - `("post_inspection_followup", "Post-Inspection Response Tracking")`
  - `OUTCOME_CHOICES` (`max_length=36`):
    - `("pending", "Pending Final Agency Classification")`
    - `("nai_no_action_indicated", "NAI - No Action Indicated")`
    - `("vai_voluntary_action_indicated", "VAI - Voluntary Action Indicated")`
    - `("oai_official_action_indicated", "OAI - Official Action Indicated")`
    - `("certified_unconditional", "Unconditional Certification / Clearance")`
    - `("conditional_clearance", "Conditional Clearance / Action Plan Required")`
    - `("refusal_warning_letter", "Warning Letter / Certification Refused")`
  - `AGENCY_CSS`:
    - `"fda_cdrh": "badge-red"`
    - `"fda_cder": "badge-red"`
    - `"iso_notified_body": "badge-amber"`
    - `"ema_eu": "badge-info"`
    - `"health_canada": "badge-info"`
    - `"pmda_japan": "badge-info"`
    - `"customer_corporate": "badge-slate"`
    - `"iso_registrar": "badge-amber"`
    - `"other_authority": "badge-muted"`
  - `STATUS_CSS`:
    - `"preparation": "badge-slate"`
    - `"active_inspection": "badge-amber"`
    - `"daily_wrapup": "badge-info"`
    - `"inspection_closed": "badge-green"`
    - `"post_inspection_followup": "badge-muted"`
  - `OUTCOME_CSS`:
    - `"pending": "badge-muted"`
    - `"nai_no_action_indicated": "badge-green"`
    - `"vai_voluntary_action_indicated": "badge-amber"`
    - `"oai_official_action_indicated": "badge-red"`
    - `"certified_unconditional": "badge-green"`
    - `"conditional_clearance": "badge-amber"`
    - `"refusal_warning_letter": "badge-red"`

- **Fields**:
  - `audit`: `ForeignKey("quality.QualityAudit", on_delete=models.SET_NULL, null=True, blank=True, related_name="regulatory_hosts", help_text="Linked QualityAudit record")`
  - `inspection_title`: `CharField(max_length=255, help_text="e.g. FDA cGMP / QSIT Inspection - Medical Device Facility")`
  - `agency_or_body`: `CharField(max_length=32, choices=AGENCY_CHOICES, default="fda_cdrh", db_index=True)`
  - `agency_name`: `CharField(max_length=128, help_text="Official body name e.g. US FDA - District Office, TÜV SÜD Product Service")`
  - `lead_inspector_name`: `CharField(max_length=128, help_text="Lead inspector / investigator name")`
  - `inspector_credentials`: `CharField(max_length=128, blank=True, help_text="Badge number, division, or contact identifier")`
  - `inspection_purpose`: `CharField(max_length=32, choices=PURPOSE_CHOICES, default="routine_surveillance", db_index=True)`
  - `announcement_status`: `CharField(max_length=24, choices=ANNOUNCEMENT_CHOICES, default="announced", db_index=True)`
  - `scheduled_start_date`: `DateField(db_index=True)`
  - `scheduled_end_date`: `DateField()`
  - `actual_start_date`: `DateField(null=True, blank=True)`
  - `actual_end_date`: `DateField(null=True, blank=True)`
  - `front_room_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="hosted_front_rooms", help_text="Primary company spokesperson / Front Room facilitator")`
  - `back_room_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="managed_back_rooms", help_text="Back Room document staging & SME coordinator")`
  - `scribe_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="scribed_inspections", help_text="Official inspection scribe and request logger")`
  - `war_room_location`: `CharField(max_length=255, help_text="Staging conference room or secure virtual bridge URL")`
  - `status`: `CharField(max_length=32, choices=STATUS_CHOICES, default="preparation", db_index=True)`
  - `requests_logged_count`: `PositiveIntegerField(default=0, help_text="Count of records/documents requested by inspectors")`
  - `requests_fulfilled_count`: `PositiveIntegerField(default=0, help_text="Count of requests successfully fulfilled")`
  - `form_483_issued`: `BooleanField(default=False, help_text="Whether FDA Form 483 / Inspectional Observations was issued")`
  - `observations_count`: `PositiveIntegerField(default=0, help_text="Number of formal inspection observations / Form 483 citations")`
  - `formal_outcome`: `CharField(max_length=36, choices=OUTCOME_CHOICES, default="pending", db_index=True)`
  - `daily_summary_notes`: `TextField(blank=True, help_text="Daily debrief log, inspector questions, and SME interview notes")`
  - `closeout_memo`: `TextField(blank=True, help_text="Exit conference debrief, commitments, and executive response plan")`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qhst_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qhst_ten_status")` (19)
  - `Index(fields=["tenant", "agency_or_body"], name="idx_qhst_ten_agency")` (19)
  - `Index(fields=["tenant", "formal_outcome"], name="idx_qhst_ten_out")` (16)
  - `Index(fields=["tenant", "audit"], name="idx_qhst_ten_audit")` (18)
  - `Index(fields=["tenant", "scheduled_start_date"], name="idx_qhst_ten_sched")` (18)
  - `Index(fields=["tenant", "front_room_lead"], name="idx_qhst_ten_flead")` (18)
  - `Index(fields=["tenant", "-created_at"], name="idx_qhst_ten_created")` (20)

- **Helper Properties**:
  - `fulfillment_rate`: int/float percentage `(requests_fulfilled_count / requests_logged_count * 100)` if logged > 0 else 100
  - `is_active`: `status in ("active_inspection", "daily_wrapup")`
  - `pending_requests_count`: `max(0, requests_logged_count - requests_fulfilled_count)`

---

## 2. Forms Contract (`apps/quality/forms/AuditManagement/`)

All forms subclass `forms.ModelForm` (or `forms.Form`), inject standard Tailwind classes via `self.fields[field].widget.attrs["class"] = "..."` or widgets, set tenant-scoped querysets in `__init__`, and reject foreign tenant instances in `clean()`.

### 2.1 `AuditProgramForm` (`AuditPrograms.py`)
- **Model**: `AuditProgram`
- **Fields**: `["title", "program_year", "program_type", "risk_basis", "scope_description", "start_date", "end_date", "allocated_budget_hours", "status", "program_manager", "notes"]`
- **Exclusions**: `["tenant", "number", "approved_by", "approval_date", "created_at", "updated_at"]`
- **Tenant Scoping in `__init__`**:
  - `program_manager`: `User.objects.filter(tenant=self.tenant)`

### 2.2 `QualityAuditForm` (`QualityAudits.py`)
- **Model**: `QualityAudit`
- **Fields**: `["program", "title", "audit_type", "audit_method", "standard_framework", "target_org_unit", "external_entity", "lead_auditor", "auditee_lead", "audit_checklist_sop", "planned_start_date", "planned_end_date", "actual_start_date", "actual_end_date", "scope_objectives", "product_scope", "lot_number_sampled", "status", "outcome", "executive_summary", "notes"]`
- **Exclusions**: `["tenant", "number", "report_published_date", "total_findings_count", "critical_findings_count", "major_findings_count", "minor_findings_count", "ofi_findings_count", "created_at", "updated_at"]`
- **Tenant Scoping in `__init__`**:
  - `program`: `AuditProgram.objects.filter(tenant=self.tenant)`
  - `target_org_unit`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - `external_entity`: `Party.objects.filter(tenant=self.tenant)`
  - `lead_auditor`: `User.objects.filter(tenant=self.tenant)`
  - `auditee_lead`: `User.objects.filter(tenant=self.tenant)`
  - `audit_checklist_sop`: `ControlledDocument.objects.filter(tenant=self.tenant)`

### 2.3 `AuditFindingForm` (`AuditFindings.py`)
- **Model**: `AuditFinding`
- **Fields**: `["audit", "finding_number_in_audit", "title", "severity", "standard_clause", "requirement_statement", "condition_evidence", "audited_org_unit", "assignee", "response_due_date", "containment_action", "root_cause_summary", "corrective_action_plan", "linked_capa", "linked_ncr", "status", "closure_notes"]`
- **Exclusions**: `["tenant", "number", "response_received_date", "closure_verified_by", "closed_date", "created_at", "updated_at"]`
- **Tenant Scoping in `__init__`**:
  - `audit`: `QualityAudit.objects.filter(tenant=self.tenant)`
  - `audited_org_unit`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - `assignee`: `User.objects.filter(tenant=self.tenant)`
  - `linked_capa`: `CapaInvestigation.objects.filter(tenant=self.tenant)`
  - `linked_ncr`: `NonConformanceReport.objects.filter(tenant=self.tenant)`

### 2.4 `AuditFindingResponseForm` (`AuditFindings.py`)
- **Model**: `AuditFinding`
- **Fields**: `["containment_action", "root_cause_summary", "corrective_action_plan"]`
- Used when auditee submits remediation response.

### 2.5 `RegulatoryInspectionHostForm` (`RegulatoryInspectionHosts.py`)
- **Model**: `RegulatoryInspectionHost`
- **Fields**: `["audit", "inspection_title", "agency_or_body", "agency_name", "lead_inspector_name", "inspector_credentials", "inspection_purpose", "announcement_status", "scheduled_start_date", "scheduled_end_date", "actual_start_date", "actual_end_date", "front_room_lead", "back_room_lead", "scribe_user", "war_room_location", "status", "form_483_issued", "observations_count", "formal_outcome", "daily_summary_notes", "closeout_memo"]`
- **Exclusions**: `["tenant", "number", "requests_logged_count", "requests_fulfilled_count", "created_at", "updated_at"]`
- **Tenant Scoping in `__init__`**:
  - `audit`: `QualityAudit.objects.filter(tenant=self.tenant)`
  - `front_room_lead`: `User.objects.filter(tenant=self.tenant)`
  - `back_room_lead`: `User.objects.filter(tenant=self.tenant)`
  - `scribe_user`: `User.objects.filter(tenant=self.tenant)`

### 2.6 `InspectionLogRequestForm` (`RegulatoryInspectionHosts.py`)
- **Form type**: Non-model or simple action form
- **Fields**: `["request_description", "assigned_sme", "priority"]`

---

## 3. URLs & Route Names (`apps/quality/urls/AuditManagement/`)

All URLs prefixed under `quality:` namespace (from `apps/quality/urls/__init__.py`).
Literal string routes are defined BEFORE `<int:pk>/` routes to prevent first-match masking.

### 3.1 `AuditPrograms.py`
- `audits/programs/` -> name: `audit_program_list`
- `audits/programs/create/` -> name: `audit_program_create`
- `audits/programs/export/` -> name: `audit_program_export_csv`
- `audits/programs/<int:pk>/` -> name: `audit_program_detail`
- `audits/programs/<int:pk>/edit/` -> name: `audit_program_edit`
- `audits/programs/<int:pk>/delete/` -> name: `audit_program_delete`
- `audits/programs/<int:pk>/approve/` -> name: `audit_program_approve`

### 3.2 `QualityAudits.py`
- `audits/records/` -> name: `quality_audit_list`
- `audits/records/create/` -> name: `quality_audit_create`
- `audits/records/export/` -> name: `quality_audit_export_csv`
- `audits/records/<int:pk>/` -> name: `quality_audit_detail`
- `audits/records/<int:pk>/edit/` -> name: `quality_audit_edit`
- `audits/records/<int:pk>/delete/` -> name: `quality_audit_delete`
- `audits/records/<int:pk>/publish/` -> name: `quality_audit_publish_report`
- `audits/records/<int:pk>/close/` -> name: `quality_audit_close`

### 3.3 `AuditFindings.py`
- `audits/findings/` -> name: `audit_finding_list`
- `audits/findings/create/` -> name: `audit_finding_create`
- `audits/findings/export/` -> name: `audit_finding_export_csv`
- `audits/findings/<int:pk>/` -> name: `audit_finding_detail`
- `audits/findings/<int:pk>/edit/` -> name: `audit_finding_edit`
- `audits/findings/<int:pk>/delete/` -> name: `audit_finding_delete`
- `audits/findings/<int:pk>/respond/` -> name: `audit_finding_submit_response`
- `audits/findings/<int:pk>/verify/` -> name: `audit_finding_verify_close`
- `audits/findings/<int:pk>/create-capa/` -> name: `audit_finding_create_capa`

### 3.4 `RegulatoryInspectionHosts.py`
- `audits/inspections/` -> name: `regulatory_inspection_host_list`
- `audits/inspections/create/` -> name: `regulatory_inspection_host_create`
- `audits/inspections/export/` -> name: `regulatory_inspection_host_export_csv`
- `audits/inspections/<int:pk>/` -> name: `regulatory_inspection_host_detail`
- `audits/inspections/<int:pk>/edit/` -> name: `regulatory_inspection_host_edit`
- `audits/inspections/<int:pk>/delete/` -> name: `regulatory_inspection_host_delete`
- `audits/inspections/<int:pk>/log-request/` -> name: `regulatory_inspection_host_log_request`
- `audits/inspections/<int:pk>/fulfill-request/` -> name: `regulatory_inspection_host_fulfill_request`
- `audits/inspections/<int:pk>/close/` -> name: `regulatory_inspection_host_close`

### 3.5 Dedicated Command Center Views
- `audits/action-tracker/` -> name: `audit_action_tracker`
- `audits/war-room/` -> name: `audit_war_room`

---

## 4. Views & Context Variables Contract (`apps/quality/views/AuditManagement/`)

Every view passes the pinned context variables. Single detail object variables are pinned and dual-bound to both `<entity>` and `obj` to avoid `NoReverseMatch` / blank render issues (L7, L8).

### 4.1 `AuditPrograms.py`
- `audit_program_list`:
  - `audit_programs`: `page_obj.object_list` (and `object_list` alias)
  - `page_obj`: paginated slice
  - `paginator`: Paginator object
  - `is_paginated`: boolean
  - `total_count`: total records for tenant
  - `active_count`: count of status="active"
  - `completed_count`: count of status="completed"
  - `program_type_choices`: `AuditProgram.PROGRAM_TYPE_CHOICES`
  - `risk_basis_choices`: `AuditProgram.RISK_BASIS_CHOICES`
  - `status_choices`: `AuditProgram.STATUS_CHOICES`
  - `selected_program_type`: request.GET.get('program_type', '')
  - `selected_risk_basis`: request.GET.get('risk_basis', '')
  - `selected_status`: request.GET.get('status', '')
  - `search_query`: request.GET.get('q', '')
- `audit_program_detail`:
  - `audit_program`: target `AuditProgram` instance
  - `obj`: target `AuditProgram` instance (dual bound)
  - `audits`: child `QualityAudit` queryset
  - `completion_rate`: percentage
- `audit_program_create` / `audit_program_edit`:
  - `form`: `AuditProgramForm` instance
  - `is_edit`: boolean
  - `audit_program`: instance if edit else None
  - `obj`: instance if edit else None (dual bound)

### 4.2 `QualityAudits.py`
- `quality_audit_list`:
  - `quality_audits`: `page_obj.object_list` (and `object_list` alias)
  - `page_obj`: paginated slice
  - `paginator`: Paginator object
  - `is_paginated`: boolean
  - `total_count`: total records
  - `scheduled_count`: count of status="scheduled"
  - `in_progress_count`: count of status="in_progress"
  - `closed_count`: count of status="closed"
  - `audit_type_choices`: `QualityAudit.AUDIT_TYPE_CHOICES`
  - `audit_method_choices`: `QualityAudit.AUDIT_METHOD_CHOICES`
  - `standard_framework_choices`: `QualityAudit.STANDARD_FRAMEWORK_CHOICES`
  - `status_choices`: `QualityAudit.STATUS_CHOICES`
  - `outcome_choices`: `QualityAudit.OUTCOME_CHOICES`
  - `programs`: `AuditProgram.objects.filter(tenant=request.tenant)`
  - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
  - `selected_audit_type`: request.GET.get('audit_type', '')
  - `selected_framework`: request.GET.get('standard_framework', '')
  - `selected_status`: request.GET.get('status', '')
  - `selected_outcome`: request.GET.get('outcome', '')
  - `selected_program`: request.GET.get('program', '')
  - `selected_org_unit`: request.GET.get('org_unit', '')
  - `search_query`: request.GET.get('q', '')
- `quality_audit_detail`:
  - `quality_audit`: target `QualityAudit` instance
  - `obj`: target `QualityAudit` instance (dual bound)
  - `findings`: child `AuditFinding` queryset
  - `regulatory_hosts`: child `RegulatoryInspectionHost` queryset
  - `days_open`: helper integer
  - `is_overdue`: helper boolean
- `quality_audit_create` / `quality_audit_edit`:
  - `form`: `QualityAuditForm` instance
  - `is_edit`: boolean
  - `quality_audit`: instance if edit else None
  - `obj`: instance if edit else None (dual bound)

### 4.3 `AuditFindings.py`
- `audit_finding_list`:
  - `audit_findings`: `page_obj.object_list` (and `object_list` alias)
  - `page_obj`: paginated slice
  - `paginator`: Paginator object
  - `is_paginated`: boolean
  - `total_count`: total records
  - `open_count`: count where status != "closed"
  - `critical_count`: count where severity in ("critical", "major")
  - `overdue_count`: count where response is overdue
  - `severity_choices`: `AuditFinding.SEVERITY_CHOICES`
  - `status_choices`: `AuditFinding.STATUS_CHOICES`
  - `audits`: `QualityAudit.objects.filter(tenant=request.tenant)`
  - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
  - `assignees`: `User.objects.filter(tenant=request.tenant)`
  - `selected_severity`: request.GET.get('severity', '')
  - `selected_status`: request.GET.get('status', '')
  - `selected_audit`: request.GET.get('audit', '')
  - `selected_org_unit`: request.GET.get('org_unit', '')
  - `selected_assignee`: request.GET.get('assignee', '')
  - `search_query`: request.GET.get('q', '')
- `audit_finding_detail`:
  - `audit_finding`: target `AuditFinding` instance
  - `obj`: target `AuditFinding` instance (dual bound)
  - `response_form`: `AuditFindingResponseForm` if status in ("issued", "draft") else None
- `audit_finding_create` / `audit_finding_edit`:
  - `form`: `AuditFindingForm` instance
  - `is_edit`: boolean
  - `audit_finding`: instance if edit else None
  - `obj`: instance if edit else None (dual bound)

### 4.4 `RegulatoryInspectionHosts.py`
- `regulatory_inspection_host_list`:
  - `regulatory_inspection_hosts`: `page_obj.object_list` (and `object_list` alias)
  - `page_obj`: paginated slice
  - `paginator`: Paginator object
  - `is_paginated`: boolean
  - `total_count`: total records
  - `active_count`: count where status in ("active_inspection", "daily_wrapup")
  - `form_483_count`: count where form_483_issued=True
  - `agency_choices`: `RegulatoryInspectionHost.AGENCY_CHOICES`
  - `purpose_choices`: `RegulatoryInspectionHost.PURPOSE_CHOICES`
  - `status_choices`: `RegulatoryInspectionHost.STATUS_CHOICES`
  - `outcome_choices`: `RegulatoryInspectionHost.OUTCOME_CHOICES`
  - `selected_agency`: request.GET.get('agency', '')
  - `selected_status`: request.GET.get('status', '')
  - `selected_outcome`: request.GET.get('formal_outcome', '')
  - `search_query`: request.GET.get('q', '')
- `regulatory_inspection_host_detail`:
  - `regulatory_inspection_host`: target `RegulatoryInspectionHost` instance
  - `obj`: target `RegulatoryInspectionHost` instance (dual bound)
  - `fulfillment_rate`: percentage
  - `pending_requests_count`: integer
- `regulatory_inspection_host_create` / `regulatory_inspection_host_edit`:
  - `form`: `RegulatoryInspectionHostForm` instance
  - `is_edit`: boolean
  - `regulatory_inspection_host`: instance if edit else None
  - `obj`: instance if edit else None (dual bound)

### 4.5 Dedicated Command Center Views
- `audit_action_tracker`:
  - `open_findings`: list/qs of open findings
  - `overdue_findings`: list/qs of overdue findings
  - `pending_verification`: list/qs of verification_pending findings
  - `escalated_findings`: list/qs of escalated findings
  - `total_open_count`: int
  - `critical_count`: int
  - `overdue_count`: int
  - `pending_verification_count`: int
- `audit_war_room`:
  - `active_inspections`: qs of active `RegulatoryInspectionHost`
  - `selected_host`: active inspection or latest inspection
  - `total_active_count`: int
  - `fulfillment_rate`: int/float

---

## 5. Navigation LIVE_LINKS Contract (`apps/core/navigation.py`)

Exact NavERP.md feature bullet text mapping:
```python
"12.11": {
    "Audit Program Planning": "quality:audit_program_list",
    "Audit Execution & Checklists": "quality:quality_audit_list",
    "Audit Findings & Reporting": "quality:audit_finding_list",
    "Corrective Action Tracking": "quality:audit_action_tracker",
    "Regulatory & Certification Audits": "quality:regulatory_inspection_host_list",
},
```

---

## 6. Verification & Smoke Test Targets

1. **HTTP 200/302 Status Code Sweep**:
   - `quality:audit_program_list` -> 200
   - `quality:audit_program_create` -> 200
   - `quality:audit_program_detail` -> 200
   - `quality:audit_program_edit` -> 200
   - `quality:audit_program_export_csv` -> 200 (content-type text/csv)
   - `quality:quality_audit_list` -> 200
   - `quality:quality_audit_create` -> 200
   - `quality:quality_audit_detail` -> 200
   - `quality:quality_audit_edit` -> 200
   - `quality:quality_audit_export_csv` -> 200 (content-type text/csv)
   - `quality:audit_finding_list` -> 200
   - `quality:audit_finding_create` -> 200
   - `quality:audit_finding_detail` -> 200
   - `quality:audit_finding_edit` -> 200
   - `quality:audit_finding_export_csv` -> 200 (content-type text/csv)
   - `quality:regulatory_inspection_host_list` -> 200
   - `quality:regulatory_inspection_host_create` -> 200
   - `quality:regulatory_inspection_host_detail` -> 200
   - `quality:regulatory_inspection_host_edit` -> 200
   - `quality:regulatory_inspection_host_export_csv` -> 200 (content-type text/csv)
   - `quality:audit_action_tracker` -> 200
   - `quality:audit_war_room` -> 200
2. **Content Assertions (L8, L57)**:
   - Check presence of seeded record numbers (`QPRG-`, `QAUD-`, `QFND-`, `QHST-`).
   - Check zero unrendered template leaks (`{#` or `{% comment`).
3. **Cross-Tenant IDOR (404 Isolation)**:
   - Requesting a Globex record pk as Acme admin returns 404 for all detail/edit views.
4. **Resilience**:
   - Non-numeric FK query param (`?program=abc`, `?org_unit=xyz`) handled without 500 (L11).
   - Empty page pagination handles out-of-range pages cleanly (L9).
