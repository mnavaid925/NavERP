# Module 12.20 Pre-Build Contract — Data Integrity & Electronic Records (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.2 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.20"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; claims incremental migration `0039_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/DataIntegrity/`
  - `apps/quality/forms/DataIntegrity/`
  - `apps/quality/views/DataIntegrity/`
  - `apps/quality/urls/DataIntegrity/`
  - `templates/quality/data_integrity/{electronic_record_policy,data_integrity_assessment,audit_trail_review,system_change_control}/{list,detail,form}.html` + `templates/quality/data_integrity/data_integrity_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"approve"`, `"review"`, `"close"`, `"reject"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `quality.ComputerSystemValidation`, `quality.ControlledDocument`, `quality.NonConformanceReport`, `quality.CapaInvestigation`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/DataIntegrity/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `ElectronicRecordPolicy` (`ElectronicRecordPolicies.py`)
- **`NUMBER_PREFIX`**: `"QREC"`
- **`Meta.ordering`**: `["-created_at", "record_type_name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Electronic Record Policy"` / `"Electronic Record Policies"`
- **Choices & Badge Maps**:
  - `RECORD_CATEGORY_CHOICES` (`max_length=40`):
    - `("production_batch", "Batch Production & Lot Records")`
    - `("lab_analytical", "Laboratory & Analytical Test Data")`
    - `("equipment_calibration", "Equipment Calibration & Maintenance")`
    - `("change_control", "Change Control & System Validation")`
    - `("deviation_ncr", "Deviation, OOS & Non-Conformance")`
    - `("capa", "Corrective & Preventive Action (CAPA)")`
    - `("audit_inspection", "Audits & Regulatory Inspections")`
    - `("training_competency", "Training & Competency Records")`
    - `("complaint_pharmacovigilance", "Complaints & Pharmacovigilance")`
    - `("electronic_signature", "Electronic Signature Logs")`
  - `SIGNATURE_REQUIREMENT_CHOICES` (`max_length=30`):
    - `("none", "No Electronic Signature Required")`
    - `("single_author", "Single Signature: Author / Originator")`
    - `("dual_peer_review", "Dual Signature: Author + Technical Verifier")`
    - `("triple_qa_approval", "Triple Signature: Author + Reviewer + QA Approval")`
    - `("ccb_approval", "Change Control Board (CCB) Multi-Signoff")`
  - `STORAGE_FORMAT_CHOICES` (`max_length=30`):
    - `("database_relational", "Relational Database with Encrypted Storage")`
    - `("pdf_a_immutable", "PDF/A-1a Archival Blob with Digital Signature")`
    - `("xml_json_raw", "Structured XML/JSON Raw Stream")`
    - `("hybrid_blob", "Hybrid: Structured Table + WORM Object Store")`
  - `BACKUP_FREQUENCY_CHOICES` (`max_length=30`):
    - `("continuous_wal", "Continuous Write-Ahead Log (WAL) Streaming")`
    - `("hourly_incremental", "Hourly Incremental Snapshot")`
    - `("daily_snapshot", "Daily Automated Snapshot")`
    - `("weekly_full", "Weekly Full Cold Storage Backup")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("draft", "Draft Policy")`
    - `("active", "Active & Enforced")`
    - `("under_revision", "Under Periodic Revision")`
    - `("archived", "Archived / Retired")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"active": "badge-green"`
    - `"under_revision": "badge-amber"`
    - `"archived": "badge-muted"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `record_type_name`: `CharField(max_length=150, db_index=True)`
  - `record_category`: `CharField(max_length=40, choices=RECORD_CATEGORY_CHOICES, default="production_batch", db_index=True)`
  - `target_model_name`: `CharField(max_length=100, blank=True)`
  - `system`: `ForeignKey("quality.ComputerSystemValidation", on_delete=models.SET_NULL, null=True, blank=True, related_name="electronic_record_policies")`
  - `governing_sop`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="record_policies")`
  - `is_part_11_regulated`: `BooleanField(default=True, db_index=True)`
  - `is_annex_11_regulated`: `BooleanField(default=True)`
  - `signature_requirement`: `CharField(max_length=30, choices=SIGNATURE_REQUIREMENT_CHOICES, default="dual_peer_review")`
  - `reauthentication_required`: `BooleanField(default=True)`
  - `dual_signature_required`: `BooleanField(default=False)`
  - `audit_trail_mandatory`: `BooleanField(default=True)`
  - `retention_period_years`: `PositiveIntegerField(default=10)`
  - `storage_format`: `CharField(max_length=30, choices=STORAGE_FORMAT_CHOICES, default="database_relational")`
  - `backup_frequency`: `CharField(max_length=30, choices=BACKUP_FREQUENCY_CHOICES, default="daily_snapshot")`
  - `legal_hold`: `BooleanField(default=False, db_index=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `system_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_record_policies")`
  - `qa_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_record_policies")`
  - `approval_date`: `DateField(null=True, blank=True)`
  - `description`: `TextField(blank=True)`
- **Properties**:
  - `@property is_active`: `return self.status == "active"`
  - `@property requires_signature`: `return self.signature_requirement != "none"`
- **Constraints & Indexes**:
  - Unique: `UniqueConstraint(fields=["tenant", "number"], name="quality_qrec_ten_num_uniq")`
  - Indexes:
    - `Index(fields=["tenant", "record_category", "status"], name="idx_qrec_ten_cat_stat")`
    - `Index(fields=["tenant", "is_part_11_regulated"], name="idx_qrec_ten_part11")`

---

### 1.2 `DataIntegrityAssessment` (`DataIntegrityAssessments.py`)
- **`NUMBER_PREFIX`**: `"QDIR"`
- **`Meta.ordering`**: `["-created_at", "title"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Data Integrity Assessment"` / `"Data Integrity Assessments"`
- **Choices & Badge Maps**:
  - `ALCOA_RATING_CHOICES` (`max_length=25`):
    - `("fully_compliant", "Fully Compliant (Technical Controls)")`
    - `("partially_compliant", "Partially Compliant (Procedural Safeguards)")`
    - `("non_compliant", "Non-Compliant (Identified Vulnerability)")`
    - `("not_applicable", "Not Applicable / Out of Scope")`
  - `RISK_LEVEL_CHOICES` (`max_length=20`):
    - `("low", "Low Risk (Negligible GxP/Product Impact)")`
    - `("medium", "Medium Risk (Procedural Safeguards in Place)")`
    - `("high", "High Risk (Direct Quality / Release Vulnerability)")`
    - `("critical", "Critical Risk (Data Falsification / Uncontrolled Edit)")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("draft", "Draft Assessment")`
    - `("in_assessment", "Active Assessment / Review")`
    - `("remediation_pending", "Remediation Plan Pending")`
    - `("approved", "QA Approved & Closed")`
    - `("superseded", "Superseded by Periodic Review")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_assessment": "badge-info"`
    - `"remediation_pending": "badge-amber"`
    - `"approved": "badge-green"`
    - `"superseded": "badge-muted"`
  - `RISK_LEVEL_CSS`:
    - `"low": "badge-green"`
    - `"medium": "badge-info"`
    - `"high": "badge-amber"`
    - `"critical": "badge-red"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `assessment_scope`: `CharField(max_length=150)`
  - `system`: `ForeignKey("quality.ComputerSystemValidation", on_delete=models.SET_NULL, null=True, blank=True, related_name="data_integrity_assessments")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="data_integrity_assessments")`
  - `lead_assessor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="conducted_di_assessments")`
  - `qa_reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_di_assessments")`
  - `assessment_date`: `DateField(null=True, blank=True)`
  - `next_review_due`: `DateField(null=True, blank=True)`
  - `attributable_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `legible_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `contemporaneous_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `original_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `accurate_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `complete_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `consistent_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `enduring_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `available_rating`: `CharField(max_length=25, choices=ALCOA_RATING_CHOICES, default="fully_compliant")`
  - `overall_risk_level`: `CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default="low", db_index=True)`
  - `vulnerabilities_summary`: `TextField(blank=True)`
  - `remediation_plan`: `TextField(blank=True)`
  - `linked_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="di_assessments")`
  - `linked_ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="di_assessments")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `qa_approved_at`: `DateTimeField(null=True, blank=True)`
  - `comments`: `TextField(blank=True)`
- **Properties**:
  - `@property non_compliant_count`: returns count of ratings == "non_compliant"
  - `@property is_high_risk`: `return self.overall_risk_level in ["high", "critical"]`
  - `@property is_overdue`: `return bool(self.next_review_due and self.next_review_due < timezone.now().date() and self.status != "approved")`
- **Constraints & Indexes**:
  - Unique: `UniqueConstraint(fields=["tenant", "number"], name="quality_qdir_ten_num_uniq")`
  - Indexes:
    - `Index(fields=["tenant", "overall_risk_level", "status"], name="idx_qdir_ten_rsk_stat")`
    - `Index(fields=["tenant", "next_review_due"], name="idx_qdir_ten_rev_due")`

---

### 1.3 `AuditTrailReview` (`AuditTrailReviews.py`)
- **`NUMBER_PREFIX`**: `"QATR"`
- **`Meta.ordering`**: `["-review_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Audit Trail Review"` / `"Audit Trail Reviews"`
- **Choices & Badge Maps**:
  - `REVIEW_TYPE_CHOICES` (`max_length=30`):
    - `("routine_batch", "Routine Batch / Lot Release Review")`
    - `("periodic_system", "Scheduled Periodic System Audit Review")`
    - `("event_investigation", "Event-Driven / Deviation Investigation")`
    - `("regulatory_inspection", "Pre-Inspection Readiness Audit")`
    - `("user_access_drift", "User Access & Privilege Drift Review")`
  - `AUDIT_SOURCE_CHOICES` (`max_length=30`):
    - `("database_audit_log", "Core Database Audit Trail (AuditLog)")`
    - `("application_event_log", "Application Security & Event Log")`
    - `("instrument_raw_log", "Analytical Instrument Raw Data Log")`
    - `("cloud_infrastructure", "Cloud Infrastructure & Admin Access Log")`
    - `("batch_execution_log", "MES / Batch Execution Log")`
  - `SEVERITY_CHOICES` (`max_length=20`):
    - `("none", "No Anomalies Detected (Clean)")`
    - `("minor", "Minor Procedural Discrepancy (No GxP Risk)")`
    - `("major", "Major Exception (Unapproved Change / Retry Alert)")`
    - `("critical", "Critical Integrity Breach (Unauthorized Alteration / Data Loss)")`
  - `DISPOSITION_CHOICES` (`max_length=25`):
    - `("pending_review", "Under Examination")`
    - `("approved_clean", "Approved — Audit Trail Clean")`
    - `("approved_remediated", "Approved — Discrepancies Remediated")`
    - `("rejected_escalated", "Rejected — Escalated to Deviation / CAPA")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("scheduled", "Review Scheduled")`
    - `("in_progress", "Examination In Progress")`
    - `("completed", "Review Completed")`
    - `("closed", "Closed & Archived")`
  - `SEVERITY_CSS`:
    - `"none": "badge-green"`
    - `"minor": "badge-info"`
    - `"major": "badge-amber"`
    - `"critical": "badge-red"`
  - `DISPOSITION_CSS`:
    - `"pending_review": "badge-slate"`
    - `"approved_clean": "badge-green"`
    - `"approved_remediated": "badge-amber"`
    - `"rejected_escalated": "badge-red"`
  - `STATUS_CSS`:
    - `"scheduled": "badge-slate"`
    - `"in_progress": "badge-info"`
    - `"completed": "badge-green"`
    - `"closed": "badge-muted"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `system`: `ForeignKey("quality.ComputerSystemValidation", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_trail_reviews")`
  - `review_type`: `CharField(max_length=30, choices=REVIEW_TYPE_CHOICES, default="periodic_system", db_index=True)`
  - `audit_source`: `CharField(max_length=30, choices=AUDIT_SOURCE_CHOICES, default="database_audit_log")`
  - `period_start`: `DateField()`
  - `period_end`: `DateField()`
  - `reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="conducted_audit_reviews")`
  - `qa_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_audit_reviews")`
  - `review_date`: `DateField(null=True, blank=True)`
  - `records_sampled_count`: `PositiveIntegerField(default=0)`
  - `anomalies_detected_count`: `PositiveIntegerField(default=0)`
  - `anomaly_severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default="none", db_index=True)`
  - `findings_summary`: `TextField(blank=True)`
  - `disposition`: `CharField(max_length=25, choices=DISPOSITION_CHOICES, default="pending_review", db_index=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="scheduled", db_index=True)`
  - `linked_ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_trail_reviews")`
  - `linked_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_trail_reviews")`
  - `qa_comments`: `TextField(blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
- **Properties**:
  - `@property is_clean`: `return self.anomalies_detected_count == 0 and self.anomaly_severity == "none"`
  - `@property requires_escalation`: `return self.anomaly_severity in ["major", "critical"]`
- **Constraints & Indexes**:
  - Unique: `UniqueConstraint(fields=["tenant", "number"], name="quality_qatr_ten_num_uniq")`
  - Indexes:
    - `Index(fields=["tenant", "review_type", "disposition"], name="idx_qatr_ten_typ_disp")`
    - `Index(fields=["tenant", "anomaly_severity", "status"], name="idx_qatr_ten_sev_stat")`

---

### 1.4 `SystemChangeControl` (`SystemChangeControls.py`)
- **`NUMBER_PREFIX`**: `"QCCR"`
- **`Meta.ordering`**: `["-created_at", "title"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"System Change Control"` / `"System Change Controls"`
- **Choices & Badge Maps**:
  - `CHANGE_TYPE_CHOICES` (`max_length=30`):
    - `("software_patch", "Software Patch / Minor Update")`
    - `("major_upgrade", "Major Software Version Upgrade")`
    - `("cloud_saas_update", "Cloud / SaaS Vendor Release")`
    - `("infrastructure_network", "Hardware, OS or Network Infrastructure")`
    - `("configuration_rule", "System Configuration / Workflow Rule Change")`
    - `("database_schema", "Database Schema / Data Migration")`
    - `("security_patch", "Security Vulnerability Patch")`
    - `("decommission", "System Retirement / Decommissioning")`
  - `GXP_IMPACT_CHOICES` (`max_length=20`):
    - `("direct_gxp", "Direct GxP Impact (Product Quality / Patient Safety)")`
    - `("indirect_gxp", "Indirect GxP Impact (Supporting Quality Data)")`
    - `("non_gxp", "Non-GxP (Operational / Administrative Only)")`
  - `CHANGE_PRIORITY_CHOICES` (`max_length=20`):
    - `("routine", "Routine Planned Change")`
    - `("urgent", "Urgent / Business Critical")`
    - `("emergency", "Emergency / Break-Fix Fix")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("draft", "Draft Proposal")`
    - `("impact_assessment", "Impact Assessment & Validation Scoping")`
    - `("ccb_review", "Change Control Board (CCB) Review")`
    - `("approved_for_build", "Approved for Implementation & Testing")`
    - `("testing_verification", "Testing & Verification In Progress")`
    - `("qa_release_pending", "QA Final Release Authorization")`
    - `("implemented_closed", "Implemented & Operational (Closed)")`
    - `("rejected", "Change Proposal Rejected")`
    - `("cancelled", "Cancelled / Backed Out")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"impact_assessment": "badge-info"`
    - `"ccb_review": "badge-amber"`
    - `"approved_for_build": "badge-info"`
    - `"testing_verification": "badge-amber"`
    - `"qa_release_pending": "badge-amber"`
    - `"implemented_closed": "badge-green"`
    - `"rejected": "badge-red"`
    - `"cancelled": "badge-muted"`
  - `PRIORITY_CSS`:
    - `"routine": "badge-slate"`
    - `"urgent": "badge-amber"`
    - `"emergency": "badge-red"`
  - `GXP_IMPACT_CSS`:
    - `"direct_gxp": "badge-red"`
    - `"indirect_gxp": "badge-amber"`
    - `"non_gxp": "badge-slate"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `system`: `ForeignKey("quality.ComputerSystemValidation", on_delete=models.SET_NULL, null=True, blank=True, related_name="change_controls")`
  - `change_type`: `CharField(max_length=30, choices=CHANGE_TYPE_CHOICES, default="software_patch")`
  - `change_priority`: `CharField(max_length=20, choices=CHANGE_PRIORITY_CHOICES, default="routine", db_index=True)`
  - `gxp_impact`: `CharField(max_length=20, choices=GXP_IMPACT_CHOICES, default="direct_gxp", db_index=True)`
  - `requestor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="requested_change_controls")`
  - `system_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_change_controls")`
  - `qa_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="qa_change_controls")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="system_change_controls")`
  - `description`: `TextField()`
  - `business_justification`: `TextField(blank=True)`
  - `data_integrity_risk`: `TextField(blank=True)`
  - `validation_deliverables`: `TextField(blank=True)`
  - `rollback_plan`: `TextField(blank=True)`
  - `target_date`: `DateField(null=True, blank=True)`
  - `actual_implementation_date`: `DateField(null=True, blank=True)`
  - `post_review_due_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `testing_successful`: `BooleanField(default=False)`
  - `data_backup_verified`: `BooleanField(default=False)`
  - `ccb_approved`: `BooleanField(default=False)`
  - `closure_summary`: `TextField(blank=True)`
- **Properties**:
  - `@property is_closed`: `return self.status == "implemented_closed"`
  - `@property is_emergency`: `return self.change_priority == "emergency"`
  - `@property is_overdue`: `return bool(self.target_date and self.target_date < timezone.now().date() and self.status not in ["implemented_closed", "rejected", "cancelled"])`
- **Constraints & Indexes**:
  - Unique: `UniqueConstraint(fields=["tenant", "number"], name="quality_qccr_ten_num_uniq")`
  - Indexes:
    - `Index(fields=["tenant", "gxp_impact", "status"], name="idx_qccr_ten_gxp_stat")`
    - `Index(fields=["tenant", "change_priority", "status"], name="idx_qccr_ten_prio_stat")`

---

## 2. Forms Contract (`apps/quality/forms/DataIntegrity/`)

All forms subclass `forms.ModelForm`.
Excluded fields on every form:
`"tenant"`, `"number"`, `"created_at"`, `"updated_at"`, and system-managed timestamps (`"qa_approved_at"`, `"completed_at"`, `"actual_implementation_date"`).
All tenant-scoped FK fields are populated in `__init__` with `.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign`.

### 2.1 `ElectronicRecordPolicyForm` (`ElectronicRecordPolicies.py`)
- `Meta.model = ElectronicRecordPolicy`
- `Meta.fields`: `["title", "record_type_name", "record_category", "target_model_name", "system", "governing_sop", "is_part_11_regulated", "is_annex_11_regulated", "signature_requirement", "reauthentication_required", "dual_signature_required", "audit_trail_mandatory", "retention_period_years", "storage_format", "backup_frequency", "legal_hold", "status", "system_owner", "qa_approver", "approval_date", "description"]`

### 2.2 `DataIntegrityAssessmentForm` (`DataIntegrityAssessments.py`)
- `Meta.model = DataIntegrityAssessment`
- `Meta.fields`: `["title", "assessment_scope", "system", "org_unit", "lead_assessor", "qa_reviewer", "assessment_date", "next_review_due", "attributable_rating", "legible_rating", "contemporaneous_rating", "original_rating", "accurate_rating", "complete_rating", "consistent_rating", "enduring_rating", "available_rating", "overall_risk_level", "vulnerabilities_summary", "remediation_plan", "linked_capa", "linked_ncr", "status", "comments"]`

### 2.3 `AuditTrailReviewForm` (`AuditTrailReviews.py`)
- `Meta.model = AuditTrailReview`
- `Meta.fields`: `["title", "system", "review_type", "audit_source", "period_start", "period_end", "reviewer", "qa_approver", "review_date", "records_sampled_count", "anomalies_detected_count", "anomaly_severity", "findings_summary", "disposition", "status", "linked_ncr", "linked_capa", "qa_comments"]`

### 2.4 `SystemChangeControlForm` (`SystemChangeControls.py`)
- `Meta.model = SystemChangeControl`
- `Meta.fields`: `["title", "system", "change_type", "change_priority", "gxp_impact", "requestor", "system_owner", "qa_lead", "org_unit", "description", "business_justification", "data_integrity_risk", "validation_deliverables", "rollback_plan", "target_date", "post_review_due_date", "status", "testing_successful", "data_backup_verified", "ccb_approved", "closure_summary"]`

---

## 3. URLs Contract (`apps/quality/urls/DataIntegrity/`)

Order: literal paths before `<int:pk>` paths.

```python
# Electronic Record Policy
path("policies/", views.electronic_record_policy_list, name="electronic_record_policy_list"),
path("policies/create/", views.electronic_record_policy_create, name="electronic_record_policy_create"),
path("policies/<int:pk>/", views.electronic_record_policy_detail, name="electronic_record_policy_detail"),
path("policies/<int:pk>/edit/", views.electronic_record_policy_edit, name="electronic_record_policy_edit"),
path("policies/<int:pk>/delete/", views.electronic_record_policy_delete, name="electronic_record_policy_delete"),

# Data Integrity Assessment
path("assessments/", views.data_integrity_assessment_list, name="data_integrity_assessment_list"),
path("assessments/create/", views.data_integrity_assessment_create, name="data_integrity_assessment_create"),
path("assessments/<int:pk>/", views.data_integrity_assessment_detail, name="data_integrity_assessment_detail"),
path("assessments/<int:pk>/edit/", views.data_integrity_assessment_edit, name="data_integrity_assessment_edit"),
path("assessments/<int:pk>/delete/", views.data_integrity_assessment_delete, name="data_integrity_assessment_delete"),

# Audit Trail Review
path("audit-reviews/", views.audit_trail_review_list, name="audit_trail_review_list"),
path("audit-reviews/create/", views.audit_trail_review_create, name="audit_trail_review_create"),
path("audit-reviews/<int:pk>/", views.audit_trail_review_detail, name="audit_trail_review_detail"),
path("audit-reviews/<int:pk>/edit/", views.audit_trail_review_edit, name="audit_trail_review_edit"),
path("audit-reviews/<int:pk>/delete/", views.audit_trail_review_delete, name="audit_trail_review_delete"),

# System Change Control
path("change-controls/", views.system_change_control_list, name="system_change_control_list"),
path("change-controls/create/", views.system_change_control_create, name="system_change_control_create"),
path("change-controls/<int:pk>/", views.system_change_control_detail, name="system_change_control_detail"),
path("change-controls/<int:pk>/edit/", views.system_change_control_edit, name="system_change_control_edit"),
path("change-controls/<int:pk>/delete/", views.system_change_control_delete, name="system_change_control_delete"),

# Command Dashboard
path("dashboard/", views.data_integrity_dashboard, name="data_integrity_dashboard"),
```

---

## 4. Views & Context Contract (`apps/quality/views/DataIntegrity/`)

### 4.1 `ElectronicRecordPolicies.py`
- `electronic_record_policy_list`:
  - Query params: `q` (search title/record_type_name), `category`, `status`, `part11`
  - Context keys: `policies`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `category_choices`, `status_choices`, `q`, `category_selected`, `status_selected`, `part11_selected`
- `electronic_record_policy_detail`:
  - Context keys: `policy`
- `electronic_record_policy_create` / `electronic_record_policy_edit`:
  - Context keys: `form`, `policy` (object in edit mode, None in create mode), `is_edit`

### 4.2 `DataIntegrityAssessments.py`
- `data_integrity_assessment_list`:
  - Query params: `q` (search title/scope), `risk_level`, `status`, `system`
  - Context keys: `assessments`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `risk_choices`, `status_choices`, `systems`, `q`, `risk_selected`, `status_selected`, `system_selected`
- `data_integrity_assessment_detail`:
  - Context keys: `assessment`
- `data_integrity_assessment_create` / `data_integrity_assessment_edit`:
  - Context keys: `form`, `assessment`, `is_edit`

### 4.3 `AuditTrailReviews.py`
- `audit_trail_review_list`:
  - Query params: `q` (search title/source), `review_type`, `severity`, `status`
  - Context keys: `reviews`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `type_choices`, `severity_choices`, `status_choices`, `q`, `type_selected`, `severity_selected`, `status_selected`
- `audit_trail_review_detail`:
  - Context keys: `review`
- `audit_trail_review_create` / `audit_trail_review_edit`:
  - Context keys: `form`, `review`, `is_edit`

### 4.4 `SystemChangeControls.py`
- `system_change_control_list`:
  - Query params: `q` (search title/desc), `change_type`, `priority`, `gxp_impact`, `status`
  - Context keys: `changes`, `page_obj`, `paginator`, `is_paginated`, `total_count`, `type_choices`, `priority_choices`, `gxp_choices`, `status_choices`, `q`, `type_selected`, `priority_selected`, `gxp_selected`, `status_selected`
- `system_change_control_detail`:
  - Context keys: `change`
- `system_change_control_create` / `system_change_control_edit`:
  - Context keys: `form`, `change`, `is_edit`

### 4.5 `DataIntegrityDashboard.py`
- `data_integrity_dashboard`:
  - Context keys:
    - `total_policies_count`
    - `part11_policies_count`
    - `active_assessments_count`
    - `critical_risk_assessments_count`
    - `overdue_assessments_count`
    - `total_reviews_count`
    - `anomaly_reviews_count`
    - `open_changes_count`
    - `emergency_changes_count`
    - `recent_policies`
    - `recent_assessments`
    - `recent_reviews`
    - `recent_changes`

---

## 5. Navigation Live Links Contract (`apps/core/navigation.py`)

Sub-module 12.20 maps all 3 NavERP.md feature bullets to live views in `LIVE_LINKS["12.20"]`:
```python
    "12.20": {
        "Electronic Records & Signatures (ER/ES) — 21 CFR Part 11": "quality:electronic_record_policy_list",
        "Data Integrity (ALCOA+)": "quality:data_integrity_assessment_list",
        "System Validation & Change Control (CSV)": "quality:system_change_control_list",
    },
```
