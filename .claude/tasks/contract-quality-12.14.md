# Module 12.14 Pre-Build Contract — Management Review & Quality Planning (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.14"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0025_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/ManagementReview/`
  - `apps/quality/forms/ManagementReview/`
  - `apps/quality/views/ManagementReview/`
  - `apps/quality/urls/ManagementReview/`
  - `templates/quality/managementreview/{quality_objective,management_review,management_review_input,management_review_action}/{list,detail,form}.html` + `templates/quality/managementreview/quality_planning_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"approve"`, `"cancel"`, `"start"`, `"complete"`, `"verify"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `quality.QualityAudit`, `quality.CapaInvestigation`, `quality.CustomerComplaint`, `quality.NonConformanceReport`, `quality.ElectronicSignatureRecord`, `quality.DocumentChangeOrder`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/ManagementReview/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `QualityObjective` (`QualityObjectives.py`)
- **`NUMBER_PREFIX`**: `"QOBJ"`
- **`Meta.ordering`**: `["-period_year", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Quality Objective"` / `"Quality Objectives"`
- **Choices & Badge Maps**:
  - `CATEGORY_CHOICES` (`max_length=32`):
    - `("product_quality", "Product Quality & Safety")`
    - `("process_performance", "Process Performance & Operational Yield")`
    - `("compliance_regulatory", "Regulatory Compliance & Audit Performance")`
    - `("customer_satisfaction", "Customer Satisfaction & Complaint Reduction")`
    - `("supplier_quality", "Supplier Quality & Incoming Acceptance")`
    - `("safety_environmental", "Safety & Environmental Compliance")`
    - `("continuous_improvement", "Continuous Improvement & Cost of Quality")`
  - `CADENCE_CHOICES` (`max_length=20`):
    - `("monthly", "Monthly")`
    - `("quarterly", "Quarterly")`
    - `("semi_annual", "Semi-Annual")`
    - `("annual", "Annual")`
  - `DIRECTION_CHOICES` (`max_length=20`):
    - `("higher_better", "Higher is Better (>= Target)")`
    - `("lower_better", "Lower is Better (<= Target)")`
    - `("exact", "Exact Target (= Target)")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft")`
    - `("active", "Active")`
    - `("on_track", "On Track")`
    - `("at_risk", "At Risk")`
    - `("behind", "Behind Target")`
    - `("achieved", "Achieved")`
    - `("abandoned", "Abandoned")`
  - `RAG_STATUS_CHOICES` (`max_length=10`):
    - `("green", "Green — On Track")`
    - `("amber", "Amber — At Risk")`
    - `("red", "Red — Critical Variance")`
    - `("neutral", "Neutral — Not Measured")`
  - `CATEGORY_CSS`:
    - `"product_quality": "badge-info"`
    - `"process_performance": "badge-info"`
    - `"compliance_regulatory": "badge-slate"`
    - `"customer_satisfaction": "badge-green"`
    - `"supplier_quality": "badge-amber"`
    - `"safety_environmental": "badge-slate"`
    - `"continuous_improvement": "badge-green"`
  - `STATUS_CSS`:
    - `"draft": "badge-muted"`
    - `"active": "badge-info"`
    - `"on_track": "badge-green"`
    - `"at_risk": "badge-amber"`
    - `"behind": "badge-red"`
    - `"achieved": "badge-green"`
    - `"abandoned": "badge-slate"`
  - `RAG_CSS`:
    - `"green": "badge-green"`
    - `"amber": "badge-amber"`
    - `"red": "badge-red"`
    - `"neutral": "badge-muted"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField()`
  - `category`: `CharField(max_length=32, choices=CATEGORY_CHOICES, default="product_quality", db_index=True)`
  - `period_year`: `PositiveIntegerField(default=2026, db_index=True)`
  - `cadence`: `CharField(max_length=20, choices=CADENCE_CHOICES, default="quarterly")`
  - `metric_unit`: `CharField(max_length=50, default="%")`
  - `baseline_value`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `target_value`: `DecimalField(max_digits=12, decimal_places=3)`
  - `current_value`: `DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`
  - `target_direction`: `CharField(max_length=20, choices=DIRECTION_CHOICES, default="higher_better")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `rag_status`: `CharField(max_length=10, choices=RAG_STATUS_CHOICES, default="neutral", db_index=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quality_objectives")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_objectives")`
  - `target_date`: `DateField(null=True, blank=True)`
  - `last_evaluated_date`: `DateField(null=True, blank=True)`
  - `action_plan_summary`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `variance`: computed difference between `current_value` and `target_value` (or `None`).
  - `is_achieved`: boolean evaluation based on `target_direction`.
  - `progress_percent`: computed percentage towards target clamped between 0 and 100.
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="qobj_ten_num_uniq")` (17 chars)
  - `Index(fields=["tenant", "status"], name="idx_qobj_ten_status")` (19 chars)
  - `Index(fields=["tenant", "category"], name="idx_qobj_ten_cat")` (16 chars)
  - `Index(fields=["tenant", "period_year"], name="idx_qobj_ten_year")` (17 chars)
  - `Index(fields=["tenant", "rag_status"], name="idx_qobj_ten_rag")` (16 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qobj_ten_created")` (20 chars)

---

### 1.2 `ManagementReview` (`ManagementReviews.py`)
- **`NUMBER_PREFIX`**: `"QMRV"`
- **`Meta.ordering`**: `["-scheduled_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Management Review"` / `"Management Reviews"`
- **Choices & Badge Maps**:
  - `CADENCE_CHOICES` (`max_length=20`):
    - `("annual", "Annual Review")`
    - `("semi_annual", "Semi-Annual Review")`
    - `("quarterly", "Quarterly Review")`
    - `("monthly", "Monthly Quality Review")`
    - `("event_driven", "Event-Driven / Special Review")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("scheduled", "Scheduled")`
    - `("in_preparation", "Input Preparation")`
    - `("meeting_active", "Meeting In Progress")`
    - `("minutes_drafting", "Minutes & Outputs Drafting")`
    - `("pending_approval", "Pending Executive Approval")`
    - `("approved", "Executive Approved / Closed")`
    - `("cancelled", "Cancelled")`
  - `SUITABILITY_CHOICES` (`max_length=32`):
    - `("pending", "Evaluation Pending")`
    - `("suitable_effective", "Suitable, Adequate & Fully Effective")`
    - `("minor_improvements", "Adequate with Minor Opportunities for Improvement")`
    - `("systemic_deficiencies", "Inadequate / Systemic Deficiencies Identified")`
  - `CADENCE_CSS`:
    - `"annual": "badge-info"`
    - `"semi_annual": "badge-info"`
    - `"quarterly": "badge-info"`
    - `"monthly": "badge-slate"`
    - `"event_driven": "badge-amber"`
  - `STATUS_CSS`:
    - `"scheduled": "badge-info"`
    - `"in_preparation": "badge-amber"`
    - `"meeting_active": "badge-amber"`
    - `"minutes_drafting": "badge-info"`
    - `"pending_approval": "badge-amber"`
    - `"approved": "badge-green"`
    - `"cancelled": "badge-slate"`
  - `SUITABILITY_CSS`:
    - `"pending": "badge-muted"`
    - `"suitable_effective": "badge-green"`
    - `"minor_improvements": "badge-amber"`
    - `"systemic_deficiencies": "badge-red"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `cadence`: `CharField(max_length=20, choices=CADENCE_CHOICES, default="quarterly", db_index=True)`
  - `period_start`: `DateField()`
  - `period_end`: `DateField()`
  - `scheduled_date`: `DateField(db_index=True)`
  - `actual_meeting_date`: `DateField(null=True, blank=True)`
  - `location`: `CharField(max_length=255, blank=True)`
  - `executive_sponsor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sponsored_management_reviews")`
  - `lead_facilitator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="facilitated_management_reviews")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="management_reviews")`
  - `attendees_roster`: `TextField(blank=True, help_text="Documented attendee list, titles, and departments")`
  - `quorum_met`: `BooleanField(default=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="scheduled", db_index=True)`
  - `qms_suitability_conclusion`: `CharField(max_length=32, choices=SUITABILITY_CHOICES, default="pending", db_index=True)`
  - `executive_summary`: `TextField(blank=True)`
  - `minutes_discussion`: `TextField(blank=True)`
  - `resource_decisions`: `TextField(blank=True)`
  - `electronic_signature`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="management_reviews")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_management_reviews")`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `total_inputs_count`: `self.inputs.count()`
  - `total_actions_count`: `self.actions.count()`
  - `open_actions_count`: `self.actions.filter(status__in=["open", "in_progress", "pending_verification"]).count()`
  - `is_overdue`: `self.status == "scheduled" and self.scheduled_date < timezone.now().date()`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="qmrv_ten_num_uniq")` (17 chars)
  - `Index(fields=["tenant", "status"], name="idx_qmrv_ten_status")` (19 chars)
  - `Index(fields=["tenant", "cadence"], name="idx_qmrv_ten_cad")` (16 chars)
  - `Index(fields=["tenant", "scheduled_date"], name="idx_qmrv_ten_schdate")` (20 chars)
  - `Index(fields=["tenant", "qms_suitability_conclusion"], name="idx_qmrv_ten_suit")` (17 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qmrv_ten_created")` (20 chars)

---

### 1.3 `ManagementReviewInput` (`ManagementReviewInputs.py`)
- **`NUMBER_PREFIX`**: `"QMRI"`
- **`Meta.ordering`**: `["management_review", "agenda_order", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Management Review Input"` / `"Management Review Inputs"`
- **Choices & Badge Maps**:
  - `CATEGORY_CHOICES` (`max_length=32`):
    - `("audit_results", "1. Audit Results (Internal, Supplier, Regulatory)")`
    - `("customer_feedback", "2. Customer Feedback & Complaint Trends")`
    - `("process_conformity", "3. Process Performance & Product Conformity")`
    - `("capa_status", "4. Status of Corrective & Preventive Actions (CAPA)")`
    - `("prior_review_followup", "5. Follow-Up Actions from Prior Reviews")`
    - `("changes_affecting_qms", "6. Regulatory Changes & QMS Updates")`
    - `("supplier_performance", "7. Supplier Performance & AVL Status")`
    - `("resources_training", "8. Resource Adequacy & Training Competency")`
    - `("risk_management", "9. Risk Management & Hazard Review")`
    - `("other_business", "10. Other Quality Matters")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft")`
    - `("compiled", "Data Compiled")`
    - `("presented", "Presented in Review")`
    - `("accepted", "Accepted by Management")`
  - `CATEGORY_CSS`:
    - `"audit_results": "badge-info"`
    - `"customer_feedback": "badge-amber"`
    - `"process_conformity": "badge-info"`
    - `"capa_status": "badge-red"`
    - `"prior_review_followup": "badge-slate"`
    - `"changes_affecting_qms": "badge-amber"`
    - `"supplier_performance": "badge-info"`
    - `"resources_training": "badge-green"`
    - `"risk_management": "badge-red"`
    - `"other_business": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-muted"`
    - `"compiled": "badge-info"`
    - `"presented": "badge-amber"`
    - `"accepted": "badge-green"`
- **Fields**:
  - `management_review`: `ForeignKey("quality.ManagementReview", on_delete=models.CASCADE, related_name="inputs")`
  - `agenda_order`: `PositiveIntegerField(default=1)`
  - `title`: `CharField(max_length=255)`
  - `category`: `CharField(max_length=32, choices=CATEGORY_CHOICES, default="audit_results", db_index=True)`
  - `summary_findings`: `TextField()`
  - `metrics_data`: `TextField(blank=True, help_text="Tabular or key metric figures presented")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `presenter`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="presented_review_inputs")`
  - `linked_audit`: `ForeignKey("quality.QualityAudit", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_inputs")`
  - `linked_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_inputs")`
  - `linked_complaint`: `ForeignKey("quality.CustomerComplaint", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_inputs")`
  - `linked_ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_inputs")`
  - `attachments_summary`: `CharField(max_length=255, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="qmri_ten_num_uniq")` (17 chars)
  - `Index(fields=["tenant", "management_review"], name="idx_qmri_ten_mrv")` (16 chars)
  - `Index(fields=["tenant", "category"], name="idx_qmri_ten_cat")` (16 chars)
  - `Index(fields=["tenant", "status"], name="idx_qmri_ten_status")` (19 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qmri_ten_created")` (20 chars)

---

### 1.4 `ManagementReviewAction` (`ManagementReviewActions.py`)
- **`NUMBER_PREFIX`**: `"QMRA"`
- **`Meta.ordering`**: `["due_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Management Review Action"` / `"Management Review Actions"`
- **Choices & Badge Maps**:
  - `ACTION_TYPE_CHOICES` (`max_length=32`):
    - `("qms_improvement", "QMS Continual Improvement")`
    - `("product_improvement", "Product Quality / Safety Enhancement")`
    - `("resource_allocation", "Resource & Infrastructure Allocation")`
    - `("capa_initiation", "Formal CAPA Initiation")`
    - `("procedure_revision", "SOP / Quality Plan Revision")`
    - `("training_competency", "Training & Education Initiative")`
    - `("regulatory_filing", "Regulatory Notification / Filing")`
  - `PRIORITY_CHOICES` (`max_length=20`):
    - `("critical", "Critical")`
    - `("high", "High")`
    - `("medium", "Medium")`
    - `("low", "Low")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("open", "Open")`
    - `("in_progress", "In Progress")`
    - `("pending_verification", "Pending QA Verification")`
    - `("completed", "Verified & Closed")`
    - `("cancelled", "Cancelled / Superseded")`
  - `ACTION_TYPE_CSS`:
    - `"qms_improvement": "badge-green"`
    - `"product_improvement": "badge-info"`
    - `"resource_allocation": "badge-amber"`
    - `"capa_initiation": "badge-red"`
    - `"procedure_revision": "badge-slate"`
    - `"training_competency": "badge-info"`
    - `"regulatory_filing": "badge-amber"`
  - `PRIORITY_CSS`:
    - `"critical": "badge-red"`
    - `"high": "badge-amber"`
    - `"medium": "badge-info"`
    - `"low": "badge-slate"`
  - `STATUS_CSS`:
    - `"open": "badge-info"`
    - `"in_progress": "badge-amber"`
    - `"pending_verification": "badge-amber"`
    - `"completed": "badge-green"`
    - `"cancelled": "badge-slate"`
- **Fields**:
  - `management_review`: `ForeignKey("quality.ManagementReview", on_delete=models.CASCADE, related_name="actions")`
  - `title`: `CharField(max_length=255)`
  - `action_type`: `CharField(max_length=32, choices=ACTION_TYPE_CHOICES, default="qms_improvement", db_index=True)`
  - `priority`: `CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium", db_index=True)`
  - `description`: `TextField()`
  - `assignee`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_management_actions")`
  - `due_date`: `DateField(db_index=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="open", db_index=True)`
  - `budget_allocated`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
  - `spawned_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="spawned_management_actions")`
  - `spawned_change_order`: `ForeignKey("quality.DocumentChangeOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="spawned_management_actions")`
  - `completion_date`: `DateField(null=True, blank=True)`
  - `resolution_summary`: `TextField(blank=True)`
  - `verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_management_actions")`
  - `verification_notes`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `is_overdue`: `self.status in ["open", "in_progress", "pending_verification"] and self.due_date < timezone.now().date()`
  - `days_open`: computed elapsed days from `created_at.date()` to `completion_date` (or `now().date()`).
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="qmra_ten_num_uniq")` (17 chars)
  - `Index(fields=["tenant", "management_review"], name="idx_qmra_ten_mrv")` (16 chars)
  - `Index(fields=["tenant", "status"], name="idx_qmra_ten_status")` (19 chars)
  - `Index(fields=["tenant", "priority"], name="idx_qmra_ten_pri")` (16 chars)
  - `Index(fields=["tenant", "due_date"], name="idx_qmra_ten_duedate")` (20 chars)
  - `Index(fields=["tenant", "-created_at"], name="idx_qmra_ten_created")` (20 chars)

---

## 2. Forms Contract (`apps/quality/forms/ManagementReview/`)

All forms inherit `django.forms.ModelForm` and enforce:
- Exclusions: `tenant`, `number`, `created_at`, `updated_at`.
- Strict exclusions on workflow state and approval timestamps:
  - `QualityObjectiveForm`: excludes `rag_status` (calculated), `last_evaluated_date` (updated on evaluation).
  - `ManagementReviewForm`: excludes `qms_suitability_conclusion`, `electronic_signature`, `approved_by`, `approved_at`, `status` (lifecycle controlled).
  - `ManagementReviewInputForm`: excludes `management_review` (pinned in view or hidden), `status` (lifecycle controlled).
  - `ManagementReviewActionForm`: excludes `management_review` (pinned in view or hidden), `status`, `completion_date`, `verified_by`, `verification_notes` (handled via dedicated action transitions).
- Explicit `__init__(self, *args, tenant=None, **kwargs)` accepting `tenant`, filtering all FK querysets:
  - `accounts.User`: `User.objects.filter(tenant=self.tenant, is_active=True)`
  - `core.OrgUnit`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - `quality.ManagementReview`: `ManagementReview.objects.filter(tenant=self.tenant)`
  - `quality.QualityAudit`: `QualityAudit.objects.filter(tenant=self.tenant)`
  - `quality.CapaInvestigation`: `CapaInvestigation.objects.filter(tenant=self.tenant)`
  - `quality.CustomerComplaint`: `CustomerComplaint.objects.filter(tenant=self.tenant)`
  - `quality.NonConformanceReport`: `NonConformanceReport.objects.filter(tenant=self.tenant)`
  - `quality.DocumentChangeOrder`: `DocumentChangeOrder.objects.filter(tenant=self.tenant)`
- Form validation in `clean()` verifying that any selected FK belongs to `self.tenant` using `reject_foreign(...)`.

---

## 3. URLs & Views Contract (`apps/quality/views/ManagementReview/` & `urls/ManagementReview/`)

### 3.1 Route Declarations (`apps/quality/urls/ManagementReview/`)

All literal routes appear before `<int:pk>` routes.

#### Quality Objectives:
- `objectives/` -> `name="quality_objective_list"`
- `objectives/create/` -> `name="quality_objective_create"`
- `objectives/export/csv/` -> `name="quality_objective_export_csv"`
- `objectives/<int:pk>/` -> `name="quality_objective_detail"`
- `objectives/<int:pk>/edit/` -> `name="quality_objective_edit"`
- `objectives/<int:pk>/delete/` -> `name="quality_objective_delete"`
- `objectives/<int:pk>/evaluate/` -> `name="quality_objective_evaluate"` (POST)

#### Management Reviews:
- `reviews/` -> `name="management_review_list"`
- `reviews/create/` -> `name="management_review_create"`
- `reviews/export/csv/` -> `name="management_review_export_csv"`
- `reviews/<int:pk>/` -> `name="management_review_detail"`
- `reviews/<int:pk>/edit/` -> `name="management_review_edit"`
- `reviews/<int:pk>/delete/` -> `name="management_review_delete"`
- `reviews/<int:pk>/start/` -> `name="management_review_start"` (POST)
- `reviews/<int:pk>/draft-minutes/` -> `name="management_review_draft_minutes"` (GET/POST)
- `reviews/<int:pk>/approve/` -> `name="management_review_approve"` (POST)
- `reviews/<int:pk>/cancel/` -> `name="management_review_cancel"` (POST)
- `reviews/<int:pk>/export/pdf/` -> `name="management_review_export_pdf"` (GET dossier/printable)

#### Review Inputs:
- `inputs/` -> `name="management_review_input_list"`
- `inputs/create/` -> `name="management_review_input_create"`
- `inputs/export/csv/` -> `name="management_review_input_export_csv"`
- `inputs/<int:pk>/` -> `name="management_review_input_detail"`
- `inputs/<int:pk>/edit/` -> `name="management_review_input_edit"`
- `inputs/<int:pk>/delete/` -> `name="management_review_input_delete"`
- `inputs/<int:pk>/present/` -> `name="management_review_input_present"` (POST)
- `inputs/<int:pk>/accept/` -> `name="management_review_input_accept"` (POST)

#### Review Actions:
- `actions/` -> `name="management_review_action_list"`
- `actions/create/` -> `name="management_review_action_create"`
- `actions/export/csv/` -> `name="management_review_action_export_csv"`
- `actions/<int:pk>/` -> `name="management_review_action_detail"`
- `actions/<int:pk>/edit/` -> `name="management_review_action_edit"`
- `actions/<int:pk>/delete/` -> `name="management_review_action_delete"`
- `actions/<int:pk>/start/` -> `name="management_review_action_start"` (POST)
- `actions/<int:pk>/complete/` -> `name="management_review_action_complete"` (POST)
- `actions/<int:pk>/verify/` -> `name="management_review_action_verify"` (POST)
- `actions/<int:pk>/escalate-capa/` -> `name="management_review_action_escalate_capa"` (POST)

#### Command Center / Quality Planning:
- `quality-planning/` -> `name="quality_planning_dashboard"`

---

### 3.2 View Context Keys & Filters Contract

#### `quality_objective_list`
- **Context Keys**:
  - `page_obj`: paginated `QualityObjective` records (15 per page)
  - `category_choices`: `QualityObjective.CATEGORY_CHOICES`
  - `status_choices`: `QualityObjective.STATUS_CHOICES`
  - `rag_choices`: `QualityObjective.RAG_STATUS_CHOICES`
  - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
  - `owners`: `User.objects.filter(tenant=request.tenant, is_active=True)`
  - `q`: search query string
  - `selected_category`: `request.GET.get("category", "")`
  - `selected_status`: `request.GET.get("status", "")`
  - `selected_rag`: `request.GET.get("rag_status", "")`
  - `selected_org_unit`: `request.GET.get("org_unit", "")`
  - `total_count`: total records matching filters
  - `on_track_count`: count with status `on_track` or `achieved`
  - `at_risk_count`: count with `rag_status="amber"`
  - `behind_count`: count with `rag_status="red"`
- **Filter Query Params**:
  - `q`: search in `title`, `description`, `number`
  - `category`: exact string match
  - `status`: exact string match
  - `rag_status`: exact string match
  - `org_unit`: `.isdigit()` check before filtering `org_unit_id`

#### `quality_objective_detail`
- **Context Keys**:
  - `objective`: the `QualityObjective` instance
  - `variance`: computed variance
  - `is_achieved`: boolean
  - `can_evaluate`: boolean indicating whether user has permission

#### `quality_objective_form` (create & edit)
- **Context Keys**:
  - `form`: `QualityObjectiveForm`
  - `objective`: instance or `None`
  - `is_edit`: boolean

---

#### `management_review_list`
- **Context Keys**:
  - `page_obj`: paginated `ManagementReview` records
  - `cadence_choices`: `ManagementReview.CADENCE_CHOICES`
  - `status_choices`: `ManagementReview.STATUS_CHOICES`
  - `suitability_choices`: `ManagementReview.SUITABILITY_CHOICES`
  - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
  - `sponsors`: `User.objects.filter(tenant=request.tenant, is_active=True)`
  - `q`: search query string
  - `selected_cadence`: `request.GET.get("cadence", "")`
  - `selected_status`: `request.GET.get("status", "")`
  - `selected_suitability`: `request.GET.get("suitability", "")`
  - `total_count`: total count
  - `scheduled_count`: count with status `scheduled`
  - `active_count`: count with status in `in_preparation`, `meeting_active`, `minutes_drafting`
  - `approved_count`: count with status `approved`

#### `management_review_detail`
- **Context Keys**:
  - `review`: the `ManagementReview` instance
  - `inputs`: review's `ManagementReviewInput` queryset ordered by `agenda_order`
  - `actions`: review's `ManagementReviewAction` queryset
  - `open_actions`: actions with status not `completed` and not `cancelled`
  - `can_start`: boolean
  - `can_draft_minutes`: boolean
  - `can_approve`: boolean
  - `can_cancel`: boolean

#### `management_review_form` (create & edit)
- **Context Keys**:
  - `form`: `ManagementReviewForm`
  - `review`: instance or `None`
  - `is_edit`: boolean

---

#### `management_review_input_list`
- **Context Keys**:
  - `page_obj`: paginated `ManagementReviewInput` records
  - `category_choices`: `ManagementReviewInput.CATEGORY_CHOICES`
  - `status_choices`: `ManagementReviewInput.STATUS_CHOICES`
  - `reviews`: `ManagementReview.objects.filter(tenant=request.tenant)`
  - `presenters`: `User.objects.filter(tenant=request.tenant, is_active=True)`
  - `q`: search query string
  - `selected_category`: `request.GET.get("category", "")`
  - `selected_status`: `request.GET.get("status", "")`
  - `selected_review`: `request.GET.get("review", "")`
  - `total_count`: total records
  - `compiled_count`: count with status `compiled`
  - `presented_count`: count with status `presented`
  - `accepted_count`: count with status `accepted`

#### `management_review_input_detail`
- **Context Keys**:
  - `review_input`: the `ManagementReviewInput` instance
  - `can_present`: boolean
  - `can_accept`: boolean

#### `management_review_input_form` (create & edit)
- **Context Keys**:
  - `form`: `ManagementReviewInputForm`
  - `review_input`: instance or `None`
  - `is_edit`: boolean
  - `review`: parent `ManagementReview` if passed in query param `review_id`

---

#### `management_review_action_list`
- **Context Keys**:
  - `page_obj`: paginated `ManagementReviewAction` records
  - `action_type_choices`: `ManagementReviewAction.ACTION_TYPE_CHOICES`
  - `priority_choices`: `ManagementReviewAction.PRIORITY_CHOICES`
  - `status_choices`: `ManagementReviewAction.STATUS_CHOICES`
  - `reviews`: `ManagementReview.objects.filter(tenant=request.tenant)`
  - `assignees`: `User.objects.filter(tenant=request.tenant, is_active=True)`
  - `q`: search query string
  - `selected_type`: `request.GET.get("action_type", "")`
  - `selected_priority`: `request.GET.get("priority", "")`
  - `selected_status`: `request.GET.get("status", "")`
  - `selected_review`: `request.GET.get("review", "")`
  - `total_count`: total count
  - `open_count`: count with status `open` or `in_progress`
  - `overdue_count`: count open and past due date
  - `completed_count`: count with status `completed`

#### `management_review_action_detail`
- **Context Keys**:
  - `action_item`: the `ManagementReviewAction` instance
  - `is_overdue`: boolean
  - `days_open`: integer
  - `can_start`: boolean
  - `can_complete`: boolean
  - `can_verify`: boolean
  - `can_escalate_capa`: boolean

#### `management_review_action_form` (create & edit)
- **Context Keys**:
  - `form`: `ManagementReviewActionForm`
  - `action_item`: instance or `None`
  - `is_edit`: boolean
  - `review`: parent `ManagementReview` if passed in query param `review_id`

---

#### `quality_planning_dashboard`
- **Context Keys**:
  - `total_objectives`: total active objectives
  - `objectives_on_track`: count on track or achieved
  - `objectives_at_risk`: count with amber/red rag status
  - `objectives_achieved`: count achieved
  - `objective_achievement_rate`: percentage
  - `total_reviews`: total management reviews
  - `scheduled_reviews`: upcoming scheduled reviews
  - `reviews_approved_this_year`: reviews approved in current year
  - `total_actions`: total review actions
  - `open_actions`: actions currently open or in progress
  - `overdue_actions`: actions past due date
  - `action_closure_rate`: percentage
  - `recent_reviews`: latest 5 reviews
  - `upcoming_reviews`: upcoming reviews
  - `urgent_actions`: top 5 open actions ordered by due date
  - `objectives_by_category`: counts grouped by category
  - `rag_distribution`: dict with `green`, `amber`, `red`, `neutral` counts

---

## 4. Navigation Contract (`apps/core/navigation.py`)

The entry for `"12.14"` in `apps/core/navigation.py` MUST match the exact NavERP.md feature-bullet text:

```python
    "12.14": {
        "Management Review Scheduling": "quality:management_review_list",
        "Quality Objectives & KPIs": "quality:quality_objective_list",
        "Review Inputs & Data Compilation": "quality:management_review_input_list",
        "Management Review Outputs & Decisions": "quality:management_review_action_list",
        "Quality Planning & Continuous Improvement": "quality:quality_planning_dashboard",
    },
```

---

## 5. Seeder Contract (`apps/quality/management/commands/seed_quality.py`)

- Function: `_seed_submodule_12_14(self, tenant, admin_user, staff_user)`
- Idempotency guard: `if QualityObjective.objects.filter(tenant=tenant).exists(): return`
- Minimum seeded records:
  - 4 `QualityObjective` records (spanning product quality, process yield, compliance, customer satisfaction)
  - 2 `ManagementReview` records (one `approved` closed review from prior quarter with attendees, minutes, suitability conclusion; one `scheduled` review for upcoming cadence)
  - 4 `ManagementReviewInput` records (linked to real `QualityAudit`, `CapaInvestigation`, `CustomerComplaint`, `NonConformanceReport`)
  - 4 `ManagementReviewAction` records (one `completed` with verification notes; one `in_progress`; one `open`; one escalated with `spawned_capa`)
- Second run must create 0 new records.
