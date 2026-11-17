# Module 12.4 Pre-Build Contract — Corrective & Preventive Action (CAPA) (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.4"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0007_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/CapaManagement/`
  - `apps/quality/forms/CapaManagement/`
  - `apps/quality/views/CapaManagement/`
  - `apps/quality/urls/CapaManagement/`
  - `templates/quality/capamanagement/{capa_investigation,root_cause_analysis,capa_action,capa_effectiveness_review}/{list,detail,form}.html` + `templates/quality/capamanagement/capa_tracking_board.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"advance"`, `"close"`, `"verify"`, `"complete"`, `"reopen"`, `"export"` (all `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `core.OrgUnit`, `accounts.User`, `quality.ControlledDocument`, `quality.DocumentChangeOrder`, `quality.ElectronicSignatureRecord`, `quality.DesignProject`, `quality.RiskAssessment`, `quality.CapaInvestigation`, `quality.RootCauseAnalysis`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.

---

## 1. Models & Choices Contract (`apps/quality/models/CapaManagement/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `CapaInvestigation` (`CapaInvestigations.py`)
- **`NUMBER_PREFIX`**: `"QCAP"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"CAPA Investigation"` / `"CAPA Investigations"`
- **Choices & Badge Maps**:
  - `ACTION_TYPE_CHOICES` (`max_length=20`):
    - `("corrective", "Corrective Action (Address Recurrence)")`
    - `("preventive", "Preventive Action (Address Potential Occurrence)")`
  - `SOURCE_TYPE_CHOICES` (`max_length=32`):
    - `("ncr", "Non-Conformance Report (NCR)")`
    - `("complaint", "Customer Complaint")`
    - `("internal_audit", "Internal Audit Finding")`
    - `("external_audit", "External Regulatory Audit")`
    - `("deviation", "Process Deviation")`
    - `("risk_assessment", "Risk Assessment / FMEA Trigger")`
    - `("management_review", "Management Review Action")`
    - `("other", "Other Operational Source")`
  - `RISK_PRIORITY_CHOICES` (`max_length=16`):
    - `("low", "Low Priority")`
    - `("medium", "Medium Priority")`
    - `("high", "High Priority")`
    - `("critical", "Critical - Patient/Product Safety")`
  - `STATUS_CHOICES` (`max_length=32`):
    - `("draft", "Draft / Triage")`
    - `("under_investigation", "Under Investigation")`
    - `("rca_in_progress", "RCA in Progress")`
    - `("action_plan_dev", "Action Plan Development")`
    - `("action_implementation", "Action Implementation")`
    - `("effectiveness_review", "Effectiveness Review")`
    - `("closed", "Closed / Verified")`
    - `("voided", "Voided / Cancelled")`
  - `ACTION_TYPE_CSS`:
    - `"corrective": "badge-info"`
    - `"preventive": "badge-purple"`
  - `SOURCE_TYPE_CSS`:
    - `"ncr": "badge-amber"`
    - `"complaint": "badge-red"`
    - `"internal_audit": "badge-info"`
    - `"external_audit": "badge-red"`
    - `"deviation": "badge-amber"`
    - `"risk_assessment": "badge-slate"`
    - `"management_review": "badge-info"`
    - `"other": "badge-slate"`
  - `RISK_PRIORITY_CSS`:
    - `"low": "badge-slate"`
    - `"medium": "badge-info"`
    - `"high": "badge-amber"`
    - `"critical": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"under_investigation": "badge-info"`
    - `"rca_in_progress": "badge-amber"`
    - `"action_plan_dev": "badge-amber"`
    - `"action_implementation": "badge-info"`
    - `"effectiveness_review": "badge-purple"`
    - `"closed": "badge-green"`
    - `"voided": "badge-muted"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `issue_summary`: `TextField(help_text="Detailed problem description, defect observations, and initial conditions")`
  - `action_type`: `CharField(max_length=20, choices=ACTION_TYPE_CHOICES, default="corrective", db_index=True)`
  - `source_type`: `CharField(max_length=32, choices=SOURCE_TYPE_CHOICES, default="ncr", db_index=True)`
  - `source_reference`: `CharField(max_length=100, blank=True, help_text="Originating defect/document reference ID")`
  - `risk_priority`: `CharField(max_length=16, choices=RISK_PRIORITY_CHOICES, default="medium", db_index=True)`
  - `containment_actions`: `TextField(blank=True, help_text="Immediate stop-gap containment or quarantine measures")`
  - `containment_implemented`: `BooleanField(default=False, help_text="Whether immediate containment/quarantine actions have been executed")`
  - `containment_verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_containment_capas")`
  - `containment_date`: `DateField(null=True, blank=True)`
  - `affected_item_code`: `CharField(max_length=100, blank=True, help_text="Part number or SKU affected")`
  - `affected_item_name`: `CharField(max_length=255, blank=True, help_text="Item name or product description")`
  - `affected_lot_numbers`: `CharField(max_length=255, blank=True, help_text="Impacted lot, batch, or serial numbers")`
  - `lead_investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="investigated_capas")`
  - `quality_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_capas")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="capa_investigations")`
  - `design_project`: `ForeignKey("quality.DesignProject", on_delete=models.SET_NULL, null=True, blank=True, related_name="capa_investigations", help_text="Associated product development plan in Design Controls")`
  - `risk_assessment`: `ForeignKey("quality.RiskAssessment", on_delete=models.SET_NULL, null=True, blank=True, related_name="capa_investigations", help_text="Linked ISO 14971 risk/FMEA assessment")`
  - `status`: `CharField(max_length=32, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `target_investigation_date`: `DateField(null=True, blank=True)`
  - `target_closure_date`: `DateField(null=True, blank=True)`
  - `is_escalated`: `BooleanField(default=False, help_text="Escalated to Executive Quality Management Review")`
  - `escalation_reason`: `TextField(blank=True, help_text="Regulatory aging justification or critical patient risk trigger")`
  - `escalated_at`: `DateTimeField(null=True, blank=True)`
  - `closure_summary`: `TextField(blank=True, help_text="Formal justification and summary of completed remediation")`
  - `closed_at`: `DateTimeField(null=True, blank=True)`
  - `closure_approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_closure_capas")`
  - `formal_closure_signature`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="closed_capa_signatures", editable=False, help_text="21 CFR Part 11 e-signature manifest")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcap_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qcap_ten_status")` (19)
  - `Index(fields=["tenant", "source_type"], name="idx_qcap_ten_src_type")` (21)
  - `Index(fields=["tenant", "risk_priority"], name="idx_qcap_ten_risk_pri")` (21)
  - `Index(fields=["tenant", "target_closure_date"], name="idx_qcap_ten_tgt_date")` (21)
  - `Index(fields=["tenant", "-created_at"], name="idx_qcap_ten_created")` (20)
- **Properties & Methods**:
  - `actions_count`: `@property` returning count of linked `CapaAction`s
  - `pending_actions_count`: `@property` returning count of actions where status not in `("implemented", "verified", "cancelled")`
  - `rca_count`: `@property` returning count of linked `RootCauseAnalysis` records
  - `is_overdue`: `@property` returning boolean whether `target_closure_date and target_closure_date < timezone.now().date() and status not in ("closed", "voided")`
  - `days_open`: `@property` returning integer days open

### 1.2 `RootCauseAnalysis` (`RootCauseAnalyses.py`)
- **`NUMBER_PREFIX`**: `"QRCA"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Root Cause Analysis"` / `"Root Cause Analyses"`
- **Choices & Badge Maps**:
  - `RCA_METHOD_CHOICES` (`max_length=32`):
    - `("5_whys", "5 Whys Root Cause Ladder")`
    - `("fishbone_ishikawa", "Ishikawa 6M Fishbone Diagram")`
    - `("8d", "8 Disciplines (8D) Problem Solving")`
    - `("fault_tree", "Fault Tree Analysis (FTA)")`
    - `("barrier_analysis", "Barrier / Escape Point Analysis")`
    - `("other", "Other Systematic Methodology")`
  - `ROOT_CAUSE_CATEGORY_CHOICES` (`max_length=32`):
    - `("design", "Design / Specification Defect")`
    - `("process", "Manufacturing / Operational Process")`
    - `("supplier", "Supplier / Raw Material Variation")`
    - `("equipment", "Equipment / Tooling / Calibration")`
    - `("human_error", "Human Performance / Ergonomics")`
    - `("documentation", "SOP / Work Instruction Inadequacy")`
    - `("training", "Training / Qualification Deficit")`
    - `("environmental", "Cleanroom / Environmental Condition")`
    - `("software", "Software / Firmware Anomaly")`
    - `("other", "Other Root Cause")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Draft Investigation")`
    - `("in_progress", "Analysis In Progress")`
    - `("completed", "Analysis Completed")`
    - `("verified", "Verified by Quality Engineering")`
    - `("rejected", "Rejected / Inconclusive")`
  - `RCA_METHOD_CSS`:
    - `"5_whys": "badge-info"`
    - `"fishbone_ishikawa": "badge-purple"`
    - `"8d": "badge-amber"`
    - `"fault_tree": "badge-slate"`
    - `"barrier_analysis": "badge-info"`
    - `"other": "badge-slate"`
  - `ROOT_CAUSE_CATEGORY_CSS`:
    - `"design": "badge-purple"`
    - `"process": "badge-info"`
    - `"supplier": "badge-amber"`
    - `"equipment": "badge-slate"`
    - `"human_error": "badge-amber"`
    - `"documentation": "badge-slate"`
    - `"training": "badge-info"`
    - `"environmental": "badge-slate"`
    - `"software": "badge-purple"`
    - `"other": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_progress": "badge-info"`
    - `"completed": "badge-amber"`
    - `"verified": "badge-green"`
    - `"rejected": "badge-red"`
- **Fields**:
  - `capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.CASCADE, related_name="root_cause_analyses")`
  - `rca_method`: `CharField(max_length=32, choices=RCA_METHOD_CHOICES, default="5_whys", db_index=True)`
  - `problem_statement`: `TextField(help_text="Concise description of the specific failure mode or defect to investigate")`
  - `why_1`: `CharField(max_length=500, blank=True)`
  - `why_2`: `CharField(max_length=500, blank=True)`
  - `why_3`: `CharField(max_length=500, blank=True)`
  - `why_4`: `CharField(max_length=500, blank=True)`
  - `why_5`: `CharField(max_length=500, blank=True)`
  - `fishbone_manpower`: `TextField(blank=True, help_text="Personnel, training, operator ergonomics, human factor contributors")`
  - `fishbone_machine`: `TextField(blank=True, help_text="Equipment, tooling, calibration, maintenance, hardware factors")`
  - `fishbone_material`: `TextField(blank=True, help_text="Raw material, component defect, supplier variation")`
  - `fishbone_method`: `TextField(blank=True, help_text="Procedures, work instructions, process parameters, test methods")`
  - `fishbone_measurement`: `TextField(blank=True, help_text="Gauge error, inspection accuracy, measurement resolution")`
  - `fishbone_environment`: `TextField(blank=True, help_text="Cleanroom conditions, temperature, humidity, ESD, contamination")`
  - `root_cause_category`: `CharField(max_length=32, choices=ROOT_CAUSE_CATEGORY_CHOICES, default="process", db_index=True)`
  - `root_cause_summary`: `TextField(help_text="Defensible synthesis of the primary root cause supported by physical/data evidence")`
  - `escape_point_gap`: `TextField(blank=True, help_text="Analysis of why existing inspection/containment barriers failed to detect the defect")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `lead_investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conducted_rcas")`
  - `verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_rcas")`
  - `verified_date`: `DateField(null=True, blank=True)`
  - `verification_notes`: `TextField(blank=True, help_text="Quality engineering verification of investigation adequacy")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrca_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "capa"], name="idx_qrca_ten_capa")` (17)
  - `Index(fields=["tenant", "rca_method"], name="idx_qrca_ten_method")` (19)
  - `Index(fields=["tenant", "root_cause_category"], name="idx_qrca_ten_rc_cat")` (19)
  - `Index(fields=["tenant", "status"], name="idx_qrca_ten_status")` (19)
  - `Index(fields=["tenant", "-created_at"], name="idx_qrca_ten_created")` (20)
- **Properties & Methods**:
  - `why_levels_count`: `@property` returning integer count of non-empty `why_*` fields
  - `is_verified`: `@property` returning `status == "verified" and verified_by is not None`

### 1.3 `CapaAction` (`CapaActions.py`)
- **`NUMBER_PREFIX`**: `"QACT"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"CAPA Action"` / `"CAPA Actions"`
- **Choices & Badge Maps**:
  - `ACTION_TYPE_CHOICES` (`max_length=24`):
    - `("containment", "Containment Action (Immediate)")`
    - `("corrective", "Corrective Action (Root Cause Removal)")`
    - `("preventive", "Preventive Action (Systemic Prevention)")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("pending", "Pending Assignment")`
    - `("in_progress", "In Progress")`
    - `("implemented", "Implemented / Executed")`
    - `("verified", "Verified by Quality")`
    - `("cancelled", "Cancelled / Superseded")`
  - `ACTION_TYPE_CSS`:
    - `"containment": "badge-amber"`
    - `"corrective": "badge-info"`
    - `"preventive": "badge-purple"`
  - `STATUS_CSS`:
    - `"pending": "badge-slate"`
    - `"in_progress": "badge-info"`
    - `"implemented": "badge-amber"`
    - `"verified": "badge-green"`
    - `"cancelled": "badge-muted"`
- **Fields**:
  - `capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.CASCADE, related_name="actions")`
  - `root_cause`: `ForeignKey("quality.RootCauseAnalysis", on_delete=models.SET_NULL, null=True, blank=True, related_name="actions")`
  - `action_type`: `CharField(max_length=24, choices=ACTION_TYPE_CHOICES, default="corrective", db_index=True)`
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField(help_text="Detailed action instructions, scope, and expected outcome")`
  - `assigned_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_capa_actions")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="capa_actions")`
  - `due_date`: `DateField(db_index=True)`
  - `completion_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="pending", db_index=True)`
  - `implementation_notes`: `TextField(blank=True, help_text="Summary of actions taken and physical evidence of completion")`
  - `controlled_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="capa_actions")`
  - `change_order`: `ForeignKey("quality.DocumentChangeOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="capa_actions")`
  - `design_project`: `ForeignKey("quality.DesignProject", on_delete=models.SET_NULL, null=True, blank=True, related_name="capa_actions")`
  - `verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_capa_actions")`
  - `verified_on`: `DateField(null=True, blank=True)`
  - `verification_evidence`: `TextField(blank=True, help_text="Independent quality verification notes confirming physical execution")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qact_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "capa"], name="idx_qact_ten_capa")` (17)
  - `Index(fields=["tenant", "action_type"], name="idx_qact_ten_act_type")` (21)
  - `Index(fields=["tenant", "status"], name="idx_qact_ten_status")` (19)
  - `Index(fields=["tenant", "due_date"], name="idx_qact_ten_due_date")` (21)
  - `Index(fields=["tenant", "-created_at"], name="idx_qact_ten_created")` (20)
- **Properties & Methods**:
  - `is_overdue`: `@property` returning `due_date and due_date < timezone.now().date() and status not in ("implemented", "verified", "cancelled")`
  - `is_verified`: `@property` returning `status == "verified" and verified_by is not None`

### 1.4 `CapaEffectivenessReview` (`CapaEffectivenessReviews.py`)
- **`NUMBER_PREFIX`**: `"QEFF"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"CAPA Effectiveness Review"` / `"CAPA Effectiveness Reviews"`
- **Choices & Badge Maps**:
  - `METHOD_CHOICES` (`max_length=32`):
    - `("statistical_sample", "Statistical Sampling & Quality Inspection")`
    - `("trend_analysis", "Trend Analysis (NCR / Complaint Volume)")`
    - `("audit_recheck", "Audit Re-check / Follow-up Audit")`
    - `("process_capability", "Process Capability Study (Cpk / Ppk)")`
    - `("zero_recurrence_window", "Zero Recurrence Window (30/60/90 Days)")`
  - `OUTCOME_CHOICES` (`max_length=24`):
    - `("pending", "Pending Evaluation")`
    - `("effective", "Effective — Actions Successful")`
    - `("ineffective", "Ineffective — Recurrence / Defect Persists")`
    - `("inconclusive", "Inconclusive — Extended Window Required")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("scheduled", "Scheduled")`
    - `("in_progress", "Evaluation In Progress")`
    - `("completed", "Review Completed")`
    - `("cancelled", "Cancelled")`
  - `METHOD_CSS`:
    - `"statistical_sample": "badge-info"`
    - `"trend_analysis": "badge-purple"`
    - `"audit_recheck": "badge-amber"`
    - `"process_capability": "badge-info"`
    - `"zero_recurrence_window": "badge-slate"`
  - `OUTCOME_CSS`:
    - `"pending": "badge-slate"`
    - `"effective": "badge-green"`
    - `"ineffective": "badge-red"`
    - `"inconclusive": "badge-amber"`
  - `STATUS_CSS`:
    - `"scheduled": "badge-slate"`
    - `"in_progress": "badge-info"`
    - `"completed": "badge-green"`
    - `"cancelled": "badge-muted"`
- **Fields**:
  - `capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.CASCADE, related_name="effectiveness_reviews")`
  - `review_criteria`: `TextField(help_text="Pre-established acceptance criteria")`
  - `verification_method`: `CharField(max_length=32, choices=METHOD_CHOICES, default="zero_recurrence_window")`
  - `planned_review_date`: `DateField(help_text="Scheduled post-implementation review date")`
  - `actual_review_date`: `DateField(null=True, blank=True)`
  - `evaluator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="evaluated_capa_reviews")`
  - `metrics_evaluated`: `TextField(blank=True, help_text="Observed defect counts, statistical sample results, or process capability figures")`
  - `recurrence_observed`: `BooleanField(default=False, help_text="Whether the failure mode or root cause recurred during evaluation window")`
  - `recurrence_details`: `TextField(blank=True, help_text="Details of any recurrences observed")`
  - `outcome`: `CharField(max_length=24, choices=OUTCOME_CHOICES, default="pending", db_index=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="scheduled", db_index=True)`
  - `review_notes`: `TextField(blank=True, help_text="Executive summary of effectiveness review finding and recommendations")`
  - `formal_signature`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="effective_review_signatures", editable=False)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qeff_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "capa"], name="idx_qeff_ten_capa")` (17)
  - `Index(fields=["tenant", "outcome"], name="idx_qeff_ten_outcome")` (20)
  - `Index(fields=["tenant", "planned_review_date"], name="idx_qeff_ten_plan_dt")` (20)
  - `Index(fields=["tenant", "status"], name="idx_qeff_ten_status")` (19)
  - `Index(fields=["tenant", "-created_at"], name="idx_qeff_ten_created")` (20)
- **Properties & Methods**:
  - `is_review_overdue`: `@property` returning `planned_review_date and planned_review_date < timezone.now().date() and status == "scheduled"`
  - `is_effective`: `@property` returning `outcome == "effective"`

---

## 2. Forms Contract (`apps/quality/forms/CapaManagement/`)

All forms inherit `apps.quality.forms._common.QualityModelForm` (`self.tenant` injected, tenant foreign keys scoped in `__init__`, `reject_foreign(...)` called in `clean()`).

### 2.1 `CapaInvestigationForm` (`CapaInvestigations.py`)
- **`Meta.model`**: `CapaInvestigation`
- **`Meta.fields`**:
  `["title", "issue_summary", "action_type", "source_type", "source_reference", "risk_priority", "containment_actions", "containment_implemented", "containment_verified_by", "containment_date", "affected_item_code", "affected_item_name", "affected_lot_numbers", "lead_investigator", "quality_owner", "department", "design_project", "risk_assessment", "status", "target_investigation_date", "target_closure_date", "is_escalated", "escalation_reason", "closure_summary"]`
- **Exclusions**: `["tenant", "number", "closed_at", "closure_approved_by", "formal_closure_signature", "escalated_at", "created_at", "updated_at"]`

### 2.2 `RootCauseAnalysisForm` (`RootCauseAnalyses.py`)
- **`Meta.model`**: `RootCauseAnalysis`
- **`Meta.fields`**:
  `["capa", "rca_method", "problem_statement", "why_1", "why_2", "why_3", "why_4", "why_5", "fishbone_manpower", "fishbone_machine", "fishbone_material", "fishbone_method", "fishbone_measurement", "fishbone_environment", "root_cause_category", "root_cause_summary", "escape_point_gap", "status", "lead_investigator"]`
- **Exclusions**: `["tenant", "number", "verified_by", "verified_date", "verification_notes", "created_at", "updated_at"]`

### 2.3 `CapaActionForm` (`CapaActions.py`)
- **`Meta.model`**: `CapaAction`
- **`Meta.fields`**:
  `["capa", "root_cause", "action_type", "title", "description", "assigned_to", "department", "due_date", "status", "implementation_notes", "controlled_document", "change_order", "design_project"]`
- **Exclusions**: `["tenant", "number", "completion_date", "verified_by", "verified_on", "verification_evidence", "created_at", "updated_at"]`

### 2.4 `CapaEffectivenessReviewForm` (`CapaEffectivenessReviews.py`)
- **`Meta.model`**: `CapaEffectivenessReview`
- **`Meta.fields`**:
  `["capa", "review_criteria", "verification_method", "planned_review_date", "evaluator", "metrics_evaluated", "recurrence_observed", "recurrence_details", "outcome", "status", "review_notes"]`
- **Exclusions**: `["tenant", "number", "actual_review_date", "formal_signature", "created_at", "updated_at"]`

---

## 3. URLs Contract (`apps/quality/urls/CapaManagement/`)

All URL routes mounted under `apps/quality/urls/__init__.py` with `app_name = "quality"`.
Literal routes MUST precede `<int:pk>` routes (first-match-wins, L23).

### 3.1 `CapaInvestigations.py`
| Pattern | View Function | URL Name |
|---|---|---|
| `capa/` | `capa_investigation_list` | `capa_investigation_list` |
| `capa/create/` | `capa_investigation_create` | `capa_investigation_create` |
| `capa/export/` | `capa_investigation_export` | `capa_investigation_export` |
| `capa/<int:pk>/` | `capa_investigation_detail` | `capa_investigation_detail` |
| `capa/<int:pk>/edit/` | `capa_investigation_edit` | `capa_investigation_edit` |
| `capa/<int:pk>/delete/` | `capa_investigation_delete` | `capa_investigation_delete` |
| `capa/<int:pk>/advance/` | `capa_investigation_advance_status` | `capa_investigation_advance_status` |
| `capa/<int:pk>/close/` | `capa_investigation_close` | `capa_investigation_close` |

### 3.2 `RootCauseAnalyses.py`
| Pattern | View Function | URL Name |
|---|---|---|
| `capa/rca/` | `root_cause_analysis_list` | `root_cause_analysis_list` |
| `capa/rca/create/` | `root_cause_analysis_create` | `root_cause_analysis_create` |
| `capa/rca/export/` | `root_cause_analysis_export` | `root_cause_analysis_export` |
| `capa/rca/<int:pk>/` | `root_cause_analysis_detail` | `root_cause_analysis_detail` |
| `capa/rca/<int:pk>/edit/` | `root_cause_analysis_edit` | `root_cause_analysis_edit` |
| `capa/rca/<int:pk>/delete/` | `root_cause_analysis_delete` | `root_cause_analysis_delete` |
| `capa/rca/<int:pk>/verify/` | `root_cause_analysis_verify` | `root_cause_analysis_verify` |

### 3.3 `CapaActions.py`
| Pattern | View Function | URL Name |
|---|---|---|
| `capa/actions/` | `capa_action_list` | `capa_action_list` |
| `capa/actions/create/` | `capa_action_create` | `capa_action_create` |
| `capa/actions/export/` | `capa_action_export` | `capa_action_export` |
| `capa/actions/<int:pk>/` | `capa_action_detail` | `capa_action_detail` |
| `capa/actions/<int:pk>/edit/` | `capa_action_edit` | `capa_action_edit` |
| `capa/actions/<int:pk>/delete/` | `capa_action_delete` | `capa_action_delete` |
| `capa/actions/<int:pk>/complete/` | `capa_action_mark_completed` | `capa_action_mark_completed` |
| `capa/actions/<int:pk>/verify/` | `capa_action_verify` | `capa_action_verify` |

### 3.4 `CapaEffectivenessReviews.py`
| Pattern | View Function | URL Name |
|---|---|---|
| `capa/effectiveness/` | `capa_effectiveness_review_list` | `capa_effectiveness_review_list` |
| `capa/effectiveness/create/` | `capa_effectiveness_review_create` | `capa_effectiveness_review_create` |
| `capa/effectiveness/export/` | `capa_effectiveness_review_export` | `capa_effectiveness_review_export` |
| `capa/effectiveness/<int:pk>/` | `capa_effectiveness_review_detail` | `capa_effectiveness_review_detail` |
| `capa/effectiveness/<int:pk>/edit/` | `capa_effectiveness_review_edit` | `capa_effectiveness_review_edit` |
| `capa/effectiveness/<int:pk>/delete/` | `capa_effectiveness_review_delete` | `capa_effectiveness_review_delete` |
| `capa/effectiveness/<int:pk>/sign-off/` | `capa_effectiveness_review_sign_off` | `capa_effectiveness_review_sign_off` |

### 3.5 `CapaTrackingBoard.py`
| Pattern | View Function | URL Name |
|---|---|---|
| `capa/tracking-board/` | `capa_tracking_board` | `capa_tracking_board` |
| `capa/tracking-board/export/` | `capa_tracking_board_export` | `capa_tracking_board_export` |

---

## 4. Views & Context Contract (`apps/quality/views/CapaManagement/`)

All views enforce `@login_required`, tenant isolation via `tenant=request.tenant`, and use `quality_object(request, Model, pk)` for detail/edit/delete/actions.

### 4.1 `capa_investigation_list`
- **Template**: `templates/quality/capamanagement/capa_investigation/list.html`
- **Context Keys**:
  - `capas`: Paginator Page object of `CapaInvestigation`
  - `total_count`: Integer total count for tenant
  - `active_count`: Integer count where status not in `("closed", "voided")`
  - `overdue_count`: Integer count overdue
  - `critical_count`: Integer count with `risk_priority="critical"`
  - `q`: Search query string
  - `status_filter`: Selected status filter
  - `source_filter`: Selected source_type filter
  - `priority_filter`: Selected risk_priority filter
  - `status_choices`: `CapaInvestigation.STATUS_CHOICES`
  - `source_type_choices`: `CapaInvestigation.SOURCE_TYPE_CHOICES`
  - `risk_priority_choices`: `CapaInvestigation.RISK_PRIORITY_CHOICES`

### 4.2 `capa_investigation_detail`
- **Template**: `templates/quality/capamanagement/capa_investigation/detail.html`
- **Context Keys**:
  - `capa`: Single `CapaInvestigation` object
  - `rcas`: Queryset of linked `RootCauseAnalysis`
  - `actions`: Queryset of linked `CapaAction`
  - `reviews`: Queryset of linked `CapaEffectivenessReview`

### 4.3 `capa_investigation_create` & `capa_investigation_edit`
- **Template**: `templates/quality/capamanagement/capa_investigation/form.html`
- **Context Keys**:
  - `form`: `CapaInvestigationForm` instance
  - `is_edit`: Boolean (`False` for create, `True` for edit)
  - `capa`: `CapaInvestigation` object (when editing)

### 4.4 `root_cause_analysis_list`
- **Template**: `templates/quality/capamanagement/root_cause_analysis/list.html`
- **Context Keys**:
  - `rcas`: Paginator Page object of `RootCauseAnalysis`
  - `total_count`: Integer count
  - `verified_count`: Integer verified count
  - `q`: Search query
  - `method_filter`: Selected method filter
  - `category_filter`: Selected root cause category filter
  - `rca_method_choices`: `RootCauseAnalysis.RCA_METHOD_CHOICES`
  - `root_cause_category_choices`: `RootCauseAnalysis.ROOT_CAUSE_CATEGORY_CHOICES`

### 4.5 `root_cause_analysis_detail`
- **Template**: `templates/quality/capamanagement/root_cause_analysis/detail.html`
- **Context Keys**:
  - `rca`: Single `RootCauseAnalysis` object
  - `linked_actions`: Queryset of `CapaAction` linked to this RCA

### 4.6 `root_cause_analysis_create` & `root_cause_analysis_edit`
- **Template**: `templates/quality/capamanagement/root_cause_analysis/form.html`
- **Context Keys**:
  - `form`: `RootCauseAnalysisForm` instance
  - `is_edit`: Boolean
  - `rca`: `RootCauseAnalysis` object (when editing)

### 4.7 `capa_action_list`
- **Template**: `templates/quality/capamanagement/capa_action/list.html`
- **Context Keys**:
  - `actions`: Paginator Page object of `CapaAction`
  - `total_count`: Integer count
  - `pending_count`: Integer pending count
  - `overdue_count`: Integer overdue count
  - `q`: Search query
  - `action_type_filter`: Selected action_type filter
  - `status_filter`: Selected status filter
  - `action_type_choices`: `CapaAction.ACTION_TYPE_CHOICES`
  - `status_choices`: `CapaAction.STATUS_CHOICES`

### 4.8 `capa_action_detail`
- **Template**: `templates/quality/capamanagement/capa_action/detail.html`
- **Context Keys**:
  - `action`: Single `CapaAction` object

### 4.9 `capa_action_create` & `capa_action_edit`
- **Template**: `templates/quality/capamanagement/capa_action/form.html`
- **Context Keys**:
  - `form`: `CapaActionForm` instance
  - `is_edit`: Boolean
  - `action`: `CapaAction` object (when editing)

### 4.10 `capa_effectiveness_review_list`
- **Template**: `templates/quality/capamanagement/capa_effectiveness_review/list.html`
- **Context Keys**:
  - `reviews`: Paginator Page object of `CapaEffectivenessReview`
  - `total_count`: Integer count
  - `effective_count`: Integer effective count
  - `ineffective_count`: Integer ineffective count
  - `q`: Search query
  - `outcome_filter`: Selected outcome filter
  - `status_filter`: Selected status filter
  - `outcome_choices`: `CapaEffectivenessReview.OUTCOME_CHOICES`
  - `status_choices`: `CapaEffectivenessReview.STATUS_CHOICES`

### 4.11 `capa_effectiveness_review_detail`
- **Template**: `templates/quality/capamanagement/capa_effectiveness_review/detail.html`
- **Context Keys**:
  - `review`: Single `CapaEffectivenessReview` object

### 4.12 `capa_effectiveness_review_create` & `capa_effectiveness_review_edit`
- **Template**: `templates/quality/capamanagement/capa_effectiveness_review/form.html`
- **Context Keys**:
  - `form`: `CapaEffectivenessReviewForm` instance
  - `is_edit`: Boolean
  - `review`: `CapaEffectivenessReview` object (when editing)

### 4.13 `capa_tracking_board`
- **Template**: `templates/quality/capamanagement/capa_tracking_board.html`
- **Context Keys**:
  - `tier_0_30`: Queryset of active CAPAs aged 0 to 30 days
  - `tier_31_60`: Queryset of active CAPAs aged 31 to 60 days
  - `tier_61_90`: Queryset of active CAPAs aged 61 to 90 days
  - `tier_90_plus`: Queryset of active CAPAs aged > 90 days
  - `escalated_capas`: Queryset of CAPAs with `is_escalated=True`
  - `overdue_capas`: List or queryset of overdue CAPAs
  - `stats`: Dict with `total_active`, `overdue_count`, `escalated_count`, `avg_cycle_days`

---

## 5. Navigation LIVE_LINKS Contract

In `apps/core/navigation.py`:

```python
"12.4": {
    "Issue Detection & Logging": "quality:capa_investigation_list",
    "Root Cause Analysis (RCA)": "quality:root_cause_analysis_list",
    "Action Plan Development": "quality:capa_action_list",
    "CAPA Tracking & Escalation": "quality:capa_tracking_board",
    "Effectiveness Verification & Closure": "quality:capa_effectiveness_review_list",
},
```
