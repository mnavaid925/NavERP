# Module 12.2 Pre-Build Contract — Design Controls & Development (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.2"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0003_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/DesignControls/`
  - `apps/quality/forms/DesignControls/`
  - `apps/quality/views/DesignControls/`
  - `apps/quality/urls/DesignControls/`
  - `templates/quality/designcontrols/{design_project,design_input,design_review,design_verification}/{list,detail,form}.html` + `templates/quality/designcontrols/traceability_matrix.html` + `templates/quality/designcontrols/dhf_dossier.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, changes=..., tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"advance"`, `"lock_dhf"`, `"verify"`, `"approve"`, `"execute"`, `"sign"` (every verb `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `core.OrgUnit`, `accounts.User`, `quality.ControlledDocument`, `quality.ElectronicSignatureRecord`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.

---

## 1. Models & Choices Contract (`apps/quality/models/DesignControls/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `DesignProject` (`DesignProjects.py`)
- **`NUMBER_PREFIX`**: `"QDPL"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Design Project"` / `"Design Projects"`
- **Choices & Badge Maps**:
  - `DEVICE_CLASS_CHOICES` (`max_length=24`):
    - `("class_i", "Class I (Low Risk)")`
    - `("class_ii", "Class II (Moderate Risk - 510k)")`
    - `("class_iii", "Class III (High Risk - PMA)")`
    - `("class_a", "Class A (IVD Low Risk)")`
    - `("class_b", "Class B (IVD Moderate Risk)")`
    - `("class_c", "Class C (IVD High Risk)")`
    - `("class_d", "Class D (High Public/Individual Risk)")`
    - `("unclassified", "General Regulated / Unclassified")`
  - `REGULATORY_PATHWAY_CHOICES` (`max_length=24`):
    - `("510k", "FDA 510(k) Premarket Notification")`
    - `("pma", "FDA Premarket Approval (PMA)")`
    - `("de_novo", "FDA De Novo Classification")`
    - `("ce_mdr", "EU CE Mark (MDR 2017/745)")`
    - `("ce_ivdr", "EU CE Mark (IVDR 2017/746)")`
    - `("health_canada", "Health Canada MDEL / License")`
    - `("exempt", "Exempt / Self-Declaration")`
    - `("other", "Other Regulatory Pathway")`
  - `CURRENT_PHASE_CHOICES` (`max_length=28`):
    - `("planning", "Phase 1: Design Planning")`
    - `("input", "Phase 2: Design Inputs")`
    - `("output_verification", "Phase 3: Design Output & Verification")`
    - `("validation", "Phase 4: Design Validation & Transfer")`
    - `("commercial_closure", "Phase 5: Commercial DHF Maintenance")`
    - `("closed", "Closed / Transferred")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Draft / Scoping")`
    - `("active", "Active Development")`
    - `("gate_review", "Under Gate Review")`
    - `("on_hold", "On Hold")`
    - `("completed", "Completed / DHF Locked")`
    - `("cancelled", "Cancelled")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"active": "badge-info"`
    - `"gate_review": "badge-amber"`
    - `"on_hold": "badge-muted"`
    - `"completed": "badge-green"`
    - `"cancelled": "badge-red"`
  - `PHASE_CSS`:
    - `"planning": "badge-slate"`
    - `"input": "badge-info"`
    - `"output_verification": "badge-amber"`
    - `"validation": "badge-purple"`
    - `"commercial_closure": "badge-green"`
    - `"closed": "badge-muted"`
  - `DEVICE_CLASS_CSS`:
    - `"class_i": "badge-slate"`
    - `"class_ii": "badge-info"`
    - `"class_iii": "badge-red"`
    - `"class_a": "badge-slate"`
    - `"class_b": "badge-info"`
    - `"class_c": "badge-amber"`
    - `"class_d": "badge-red"`
    - `"unclassified": "badge-muted"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `device_name`: `CharField(max_length=200)`
  - `device_class`: `CharField(max_length=24, choices=DEVICE_CLASS_CHOICES, default="class_ii")`
  - `regulatory_pathway`: `CharField(max_length=24, choices=REGULATORY_PATHWAY_CHOICES, default="510k")`
  - `intended_use`: `TextField(help_text="Clinical intended use and indications for use per 21 CFR § 820.30(c)")`
  - `current_phase`: `CharField(max_length=28, choices=CURRENT_PHASE_CHOICES, default="planning", db_index=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `project_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="led_design_projects")`
  - `quality_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quality_design_projects")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="design_projects")`
  - `target_completion_date`: `DateField(null=True, blank=True)`
  - `actual_completion_date`: `DateField(null=True, blank=True)`
  - `dhf_location`: `CharField(max_length=255, blank=True)`
  - `dhf_locked`: `BooleanField(default=False)`
  - `description`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qdpl_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qdpl_ten_status")` (19)
  - `Index(fields=["tenant", "current_phase"], name="idx_qdpl_ten_phase")` (18)
  - `Index(fields=["tenant", "device_class"], name="idx_qdpl_ten_dclass")` (19)

### 1.2 `DesignInput` (`DesignInputs.py`)
- **`NUMBER_PREFIX`**: `"QINP"`
- **`Meta.ordering`**: `["project", "identifier", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Design Input"` / `"Design Inputs"`
- **Choices & Badge Maps**:
  - `INPUT_TYPE_CHOICES` (`max_length=24`):
    - `("user_need", "User Need / Clinical Need")`
    - `("functional", "Functional Specification")`
    - `("performance", "Performance Requirement")`
    - `("safety", "Safety & Inherent Protection")`
    - `("regulatory", "Regulatory Standard Mandate")`
    - `("human_factors", "Human Factors & Usability")`
    - `("software", "Software Requirement (IEC 62304)")`
    - `("interface", "Interface & Physical Fit")`
    - `("packaging", "Packaging & Sterility Requirement")`
  - `PRIORITY_CHOICES` (`max_length=16`):
    - `("critical", "Critical (Must-Have)")`
    - `("major", "Major (Essential)")`
    - `("minor", "Minor (Desirable)")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft")`
    - `("in_review", "In Review")`
    - `("approved", "Approved / Frozen")`
    - `("verified", "Verified & Satisfied")`
    - `("deferred", "Deferred")`
    - `("obsolete", "Obsolete / Cancelled")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_review": "badge-amber"`
    - `"approved": "badge-info"`
    - `"verified": "badge-green"`
    - `"deferred": "badge-muted"`
    - `"obsolete": "badge-red"`
  - `PRIORITY_CSS`:
    - `"critical": "badge-red"`
    - `"major": "badge-amber"`
    - `"minor": "badge-slate"`
  - `INPUT_TYPE_CSS`:
    - `"user_need": "badge-purple"`
    - `"functional": "badge-info"`
    - `"performance": "badge-green"`
    - `"safety": "badge-red"`
    - `"regulatory": "badge-amber"`
    - `"human_factors": "badge-info"`
    - `"software": "badge-blue"`
    - `"interface": "badge-slate"`
    - `"packaging": "badge-slate"`
- **Fields**:
  - `project`: `ForeignKey("quality.DesignProject", on_delete=models.CASCADE, related_name="inputs")`
  - `identifier`: `CharField(max_length=50, help_text="Engineering item identifier, e.g. UN-001, DI-001")`
  - `title`: `CharField(max_length=255)`
  - `input_type`: `CharField(max_length=24, choices=INPUT_TYPE_CHOICES, default="functional", db_index=True)`
  - `priority`: `CharField(max_length=16, choices=PRIORITY_CHOICES, default="major")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `description`: `TextField(help_text="Unambiguous, objective, testable requirement statement")`
  - `acceptance_criteria`: `TextField(help_text="Quantitative or qualitative criteria for verification")`
  - `rationale`: `TextField(blank=True)`
  - `user_need_parent`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="derived_inputs")`
  - `controlled_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="design_inputs")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_design_inputs")`
  - `version`: `CharField(max_length=20, default="1.0")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qinp_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "project"], name="idx_qinp_ten_project")` (20)
  - `Index(fields=["tenant", "input_type"], name="idx_qinp_ten_type")` (17)
  - `Index(fields=["tenant", "status"], name="idx_qinp_ten_status")` (19)

### 1.3 `DesignReview` (`DesignReviews.py`)
- **`NUMBER_PREFIX`**: `"QREV"`
- **`Meta.ordering`**: `["project", "-review_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Design Review"` / `"Design Reviews"`
- **Choices & Badge Maps**:
  - `REVIEW_STAGE_CHOICES` (`max_length=28`):
    - `("planning", "Design Planning Review")`
    - `("concept", "Concept & Feasibility Review")`
    - `("input_freeze", "Design Input Freeze Gate")`
    - `("detailed_design", "Detailed Architecture / Output Review")`
    - `("verification_gate", "Design Verification Gate")`
    - `("validation_gate", "Design Validation Gate")`
    - `("transfer_gate", "Design Transfer Readiness Gate")`
    - `("post_launch", "Post-Launch / Change Review")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("scheduled", "Scheduled")`
    - `("in_progress", "In Progress")`
    - `("approved", "Approved (Gate Cleared)")`
    - `("conditional", "Conditional Approval")`
    - `("rejected", "Rejected / Gate Hold")`
    - `("cancelled", "Cancelled")`
  - `STATUS_CSS`:
    - `"scheduled": "badge-slate"`
    - `"in_progress": "badge-info"`
    - `"approved": "badge-green"`
    - `"conditional": "badge-amber"`
    - `"rejected": "badge-red"`
    - `"cancelled": "badge-muted"`
  - `STAGE_CSS`:
    - `"planning": "badge-slate"`
    - `"concept": "badge-slate"`
    - `"input_freeze": "badge-info"`
    - `"detailed_design": "badge-amber"`
    - `"verification_gate": "badge-purple"`
    - `"validation_gate": "badge-green"`
    - `"transfer_gate": "badge-green"`
    - `"post_launch": "badge-muted"`
- **Fields**:
  - `project`: `ForeignKey("quality.DesignProject", on_delete=models.CASCADE, related_name="reviews")`
  - `title`: `CharField(max_length=255)`
  - `review_stage`: `CharField(max_length=28, choices=REVIEW_STAGE_CHOICES, default="input_freeze", db_index=True)`
  - `review_date`: `DateField()`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="scheduled", db_index=True)`
  - `lead_reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="led_design_reviews")`
  - `independent_reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="independent_design_reviews", help_text="Independent reviewer with no direct responsibility for the stage per 21 CFR § 820.30(e)")`
  - `agenda`: `TextField(blank=True)`
  - `discussion_summary`: `TextField(blank=True)`
  - `conclusions`: `TextField(blank=True)`
  - `action_items`: `TextField(blank=True, help_text="Assigned action items and required resolutions")`
  - `action_items_resolved`: `BooleanField(default=False)`
  - `electronic_signature`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="design_reviews")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrev_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "project"], name="idx_qrev_ten_project")` (20)
  - `Index(fields=["tenant", "review_stage"], name="idx_qrev_ten_stage")` (18)
  - `Index(fields=["tenant", "status"], name="idx_qrev_ten_status")` (19)

### 1.4 `DesignVerification` (`DesignVerifications.py`)
- **`NUMBER_PREFIX`**: `"QVER"`
- **`Meta.ordering`**: `["project", "primary_input", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Design Verification"` / `"Design Verifications"`
- **Choices & Badge Maps**:
  - `ACTIVITY_TYPE_CHOICES` (`max_length=28`):
    - `("verification", "Design Verification (Outputs meet Inputs)")`
    - `("validation", "Design Validation (Conforms to User Needs)")`
    - `("usability", "Usability & Human Factors Validation")`
    - `("process_validation", "Process / Transfer Validation")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Protocol Draft")`
    - `("approved_protocol", "Protocol Approved")`
    - `("testing", "Testing In Progress")`
    - `("passed", "Passed / Criteria Met")`
    - `("failed", "Failed / Non-Conformance")`
    - `("waived", "Waived / Justified")`
  - `TEST_METHOD_CHOICES` (`max_length=24`):
    - `("inspection", "Visual / Dimensional Inspection")`
    - `("lab_test", "Laboratory / Bench Testing")`
    - `("analysis", "Engineering Analysis / Simulation")`
    - `("clinical_trial", "Clinical Study / User Trial")`
    - `("demonstration", "Operational Demonstration")`
  - `RESULT_CHOICES` (`max_length=12`):
    - `("pending", "Pending Execution")`
    - `("pass", "Pass")`
    - `("fail", "Fail")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"approved_protocol": "badge-info"`
    - `"testing": "badge-amber"`
    - `"passed": "badge-green"`
    - `"failed": "badge-red"`
    - `"waived": "badge-muted"`
  - `RESULT_CSS`:
    - `"pending": "badge-slate"`
    - `"pass": "badge-green"`
    - `"fail": "badge-red"`
  - `ACTIVITY_TYPE_CSS`:
    - `"verification": "badge-info"`
    - `"validation": "badge-green"`
    - `"usability": "badge-purple"`
    - `"process_validation": "badge-amber"`
- **Fields**:
  - `project`: `ForeignKey("quality.DesignProject", on_delete=models.CASCADE, related_name="verifications")`
  - `primary_input`: `ForeignKey("quality.DesignInput", on_delete=models.CASCADE, related_name="verifications")`
  - `title`: `CharField(max_length=255)`
  - `activity_type`: `CharField(max_length=28, choices=ACTIVITY_TYPE_CHOICES, default="verification", db_index=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `test_method`: `CharField(max_length=24, choices=TEST_METHOD_CHOICES, default="lab_test")`
  - `acceptance_criteria`: `TextField(help_text="Predetermined objective acceptance criteria")`
  - `sample_size`: `PositiveIntegerField(default=1)`
  - `results_summary`: `TextField(blank=True)`
  - `pass_fail_result`: `CharField(max_length=12, choices=RESULT_CHOICES, default="pending", db_index=True)`
  - `deviation_notes`: `TextField(blank=True)`
  - `executed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="executed_design_tests")`
  - `execution_date`: `DateField(null=True, blank=True)`
  - `protocol_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="verification_protocols")`
  - `report_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="verification_reports")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qver_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "project"], name="idx_qver_ten_project")` (20)
  - `Index(fields=["tenant", "primary_input"], name="idx_qver_ten_input")` (18)
  - `Index(fields=["tenant", "activity_type"], name="idx_qver_ten_acttype")` (20)
  - `Index(fields=["tenant", "status"], name="idx_qver_ten_status")` (19)
  - `Index(fields=["tenant", "pass_fail_result"], name="idx_qver_ten_result")` (19)

---

## 2. Forms Contract (`apps/quality/forms/DesignControls/`)

All forms subclass `apps.quality.forms._common.QualityModelForm` with strict tenant scoping in `__init__`, excluded system fields, and `reject_foreign(...)` validation in `clean()`.

### 2.1 `DesignProjectForm` (`DesignProjects.py`)
- **`Meta.model`**: `DesignProject`
- **`Meta.fields`**: `["title", "device_name", "device_class", "regulatory_pathway", "intended_use", "current_phase", "status", "project_lead", "quality_lead", "department", "target_completion_date", "actual_completion_date", "dhf_location", "description"]`
- **Excluded**: `["tenant", "number", "dhf_locked", "created_at", "updated_at"]`

### 2.2 `DesignInputForm` (`DesignInputs.py`)
- **`Meta.model`**: `DesignInput`
- **`Meta.fields`**: `["project", "identifier", "title", "input_type", "priority", "status", "description", "acceptance_criteria", "rationale", "user_need_parent", "controlled_document", "owner", "version"]`
- **Excluded**: `["tenant", "number", "created_at", "updated_at"]`

### 2.3 `DesignReviewForm` (`DesignReviews.py`)
- **`Meta.model`**: `DesignReview`
- **`Meta.fields`**: `["project", "title", "review_stage", "review_date", "status", "lead_reviewer", "independent_reviewer", "agenda", "discussion_summary", "conclusions", "action_items", "action_items_resolved"]`
- **Excluded**: `["tenant", "number", "electronic_signature", "created_at", "updated_at"]`
- **Validation in `clean()`**: `independent_reviewer` must NOT be identical to `lead_reviewer` (FDA 21 CFR § 820.30(e) independence gate).

### 2.4 `DesignVerificationForm` (`DesignVerifications.py`)
- **`Meta.model`**: `DesignVerification`
- **`Meta.fields`**: `["project", "primary_input", "title", "activity_type", "status", "test_method", "acceptance_criteria", "sample_size", "results_summary", "pass_fail_result", "deviation_notes", "executed_by", "execution_date", "protocol_document", "report_document"]`
- **Excluded**: `["tenant", "number", "created_at", "updated_at"]`

---

## 3. Views & URLs Contract (`apps/quality/views/` & `apps/quality/urls/`)

All views are function-based, `@login_required`, tenant-isolated (`tenant=request.tenant`), write audit logs via `write_audit_log`, and return exact context contracts.

### 3.1 `DesignProject` Routes & Views
- `GET design-controls/projects/` -> `quality:design_project_list`
  - Context keys: `projects` (page_obj), `device_class_choices`, `phase_choices`, `status_choices`, `total_count`, `active_count`, `locked_count`
- `GET design-controls/projects/export/` -> `quality:design_project_export`
- `GET/POST design-controls/projects/create/` -> `quality:design_project_create`
- `GET design-controls/projects/<int:pk>/` -> `quality:design_project_detail`
  - Context keys: `project`, `inputs`, `reviews`, `verifications`, `input_stats`, `review_stats`, `verification_stats`
- `GET/POST design-controls/projects/<int:pk>/edit/` -> `quality:design_project_edit`
- `POST design-controls/projects/<int:pk>/delete/` -> `quality:design_project_delete`
- `POST design-controls/projects/<int:pk>/advance-phase/` -> `quality:design_project_advance_phase`
- `POST design-controls/projects/<int:pk>/lock-dhf/` -> `quality:design_project_lock_dhf`

### 3.2 `DesignInput` Routes & Views
- `GET design-controls/inputs/` -> `quality:design_input_list`
  - Context keys: `inputs` (page_obj), `projects`, `input_type_choices`, `priority_choices`, `status_choices`, `total_count`, `verified_count`, `unverified_count`
- `GET design-controls/inputs/export/` -> `quality:design_input_export`
- `GET/POST design-controls/inputs/create/` -> `quality:design_input_create`
- `GET design-controls/inputs/<int:pk>/` -> `quality:design_input_detail`
  - Context keys: `input_obj`, `verifications`, `derived_inputs`
- `GET/POST design-controls/inputs/<int:pk>/edit/` -> `quality:design_input_edit`
- `POST design-controls/inputs/<int:pk>/delete/` -> `quality:design_input_delete`

### 3.3 `DesignReview` Routes & Views
- `GET design-controls/reviews/` -> `quality:design_review_list`
  - Context keys: `reviews` (page_obj), `projects`, `stage_choices`, `status_choices`, `total_count`, `approved_count`, `pending_count`
- `GET design-controls/reviews/export/` -> `quality:design_review_export`
- `GET/POST design-controls/reviews/create/` -> `quality:design_review_create`
- `GET design-controls/reviews/<int:pk>/` -> `quality:design_review_detail`
  - Context keys: `review`
- `GET/POST design-controls/reviews/<int:pk>/edit/` -> `quality:design_review_edit`
- `POST design-controls/reviews/<int:pk>/delete/` -> `quality:design_review_delete`
- `POST design-controls/reviews/<int:pk>/approve-gate/` -> `quality:design_review_approve_gate`

### 3.4 `DesignVerification` Routes & Views
- `GET design-controls/verifications/` -> `quality:design_verification_list`
  - Context keys: `verifications` (page_obj), `projects`, `activity_choices`, `status_choices`, `result_choices`, `total_count`, `passed_count`, `failed_count`
- `GET design-controls/verifications/export/` -> `quality:design_verification_export`
- `GET/POST design-controls/verifications/create/` -> `quality:design_verification_create`
- `GET design-controls/verifications/<int:pk>/` -> `quality:design_verification_detail`
  - Context keys: `verification`
- `GET/POST design-controls/verifications/<int:pk>/edit/` -> `quality:design_verification_edit`
- `POST design-controls/verifications/<int:pk>/delete/` -> `quality:design_verification_delete`

### 3.5 Traceability Matrix & DHF Dossier Workbenches (`TraceabilityMatrix.py`)
- `GET design-controls/matrix/` -> `quality:traceability_matrix`
  - Context keys: `projects`, `selected_project`, `matrix_rows`, `total_inputs`, `verified_inputs`, `coverage_percentage`, `gap_count`
- `GET design-controls/matrix/export/` -> `quality:traceability_matrix_export`
- `GET design-controls/projects/<int:pk>/dhf/` -> `quality:design_project_dhf`
  - Context keys: `project`, `inputs`, `reviews`, `verifications`, `specifications`, `is_dhf_complete`

---

## 4. Navigation Wiring Contract (`apps/core/navigation.py`)

`LIVE_LINKS["12.2"]` must map the 5 exact NavERP.md feature bullets to active management views:

```python
    "12.2": {
        "Design Planning & Inputs": "quality:design_project_list",
        "Design Reviews & Verification": "quality:design_review_list",
        "Design Validation & Transfer": "quality:design_verification_list",
        "Design History File (DHF)": "quality:traceability_matrix",
        "Design Changes & Configuration Management": "quality:design_input_list",
    },
```

---

## 5. Templates Contract (`templates/quality/designcontrols/`)

1. `design_project/list.html`
2. `design_project/detail.html`
3. `design_project/form.html`
4. `design_input/list.html`
5. `design_input/detail.html`
6. `design_input/form.html`
7. `design_review/list.html`
8. `design_review/detail.html`
9. `design_review/form.html`
10. `design_verification/list.html`
11. `design_verification/detail.html`
12. `design_verification/form.html`
13. `traceability_matrix.html`
14. `dhf_dossier.html`
