# Module 12.12 Pre-Build Contract — Training & Competency Management (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.12"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0020_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/TrainingCompetency/`
  - `apps/quality/forms/TrainingCompetency/`
  - `apps/quality/views/TrainingCompetency/`
  - `apps/quality/urls/TrainingCompetency/`
  - `templates/quality/trainingcompetency/{competency_matrix,training_course,training_enrollment,competency_certification}/{list,detail,form}.html` + `templates/quality/trainingcompetency/training_compliance_dashboard.html` + `templates/quality/trainingcompetency/employee_training_dossier.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"approve"`, `"retire"`, `"activate"`, `"complete"`, `"verify"`, `"waive"`, `"renew"`, `"suspend"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `core.Party`, `quality.ControlledDocument`, `quality.DocumentChangeOrder`, `quality.CapaAction`, `quality.ElectronicSignatureRecord`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)` or explicit tenant equality check.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/TrainingCompetency/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `CompetencyMatrix` (`CompetencyMatrices.py`)
- **`NUMBER_PREFIX`**: `"QMTX"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Competency Matrix"` / `"Competency Matrices"`
- **Choices & Badge Maps**:
  - `QUALIFICATION_TIER_CHOICES` (`max_length=24`):
    - `("trainee", "Trainee (Supervised Only)")`
    - `("independent", "Independent Operator / Qualified")`
    - `("specialist", "Senior Specialist / SME")`
    - `("trainer", "Certified Trainer / Assessor")`
    - `("auditor", "Qualified Internal Auditor")`
  - `CRITICALITY_CHOICES` (`max_length=24`):
    - `("low", "Low / General Admin")`
    - `("medium", "Medium / Standard Operating")`
    - `("high", "High / Direct Product Contact")`
    - `("critical_gxp", "Critical GxP / Sterility Assurance")`
  - `STATUS_CHOICES` (`max_length=16`):
    - `("draft", "Draft")`
    - `("approved", "Approved")`
    - `("active", "Active")`
    - `("retired", "Retired")`
  - `QUALIFICATION_TIER_CSS`:
    - `"trainee": "badge-slate"`
    - `"independent": "badge-info"`
    - `"specialist": "badge-purple"` -> fallback `"badge-info"` or `"badge-green"` (allowed: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`)
    - Let's use strictly allowed:
      - `"trainee": "badge-slate"`
      - `"independent": "badge-info"`
      - `"specialist": "badge-green"`
      - `"trainer": "badge-amber"`
      - `"auditor": "badge-info"`
  - `CRITICALITY_CSS`:
    - `"low": "badge-slate"`
    - `"medium": "badge-info"`
    - `"high": "badge-amber"`
    - `"critical_gxp": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"approved": "badge-info"`
    - `"active": "badge-green"`
    - `"retired": "badge-muted"`

- **Fields**:
  - `title`: `CharField(max_length=255, help_text="e.g. Aseptic Fill Line Operator Competency Matrix")`
  - `role_title`: `CharField(max_length=128, help_text="Target role or job position e.g. Cleanroom Technician")`
  - `qualification_tier`: `CharField(max_length=24, choices=QUALIFICATION_TIER_CHOICES, default="independent", db_index=True)`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="competency_matrices")`
  - `criticality`: `CharField(max_length=24, choices=CRITICALITY_CHOICES, default="medium", db_index=True)`
  - `revision`: `CharField(max_length=16, default="1.0", help_text="Revision/version identifier")`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `minimum_passing_score`: `PositiveSmallIntegerField(default=80, help_text="Passing threshold percentage e.g. 80")`
  - `validity_period_months`: `PositiveSmallIntegerField(default=12, help_text="Re-qualification cycle in months e.g. 12")`
  - `prerequisite_experience_months`: `PositiveSmallIntegerField(default=0, help_text="Required months of domain experience")`
  - `description`: `TextField(blank=True, help_text="Curriculum overview and qualification scope")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_competency_matrices")`
  - `approval_date`: `DateField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qmtx_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qmtx_ten_status")` (19)
  - `Index(fields=["tenant", "qualification_tier"], name="idx_qmtx_ten_tier")` (17)
  - `Index(fields=["tenant", "criticality"], name="idx_qmtx_ten_crit")` (17)
  - `Index(fields=["tenant", "department"], name="idx_qmtx_ten_dept")` (17)
  - `Index(fields=["tenant", "-created_at"], name="idx_qmtx_ten_created")` (20)

- **Helper Properties**:
  - `courses_count`: count of related `courses`
  - `active_courses_count`: count of related `courses` where status="active"
  - `certifications_count`: count of related `certified_holders` where status="active"

---

### 1.2 `QualityTrainingCourse` (`QualityTrainingCourses.py`)
- **`NUMBER_PREFIX`**: `"QCRS"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Quality Training Course"` / `"Quality Training Courses"`
- **Choices & Badge Maps**:
  - `CATEGORY_CHOICES` (`max_length=32`):
    - `("gxp_compliance", "GxP & Regulatory Compliance")`
    - `("safety_ehs", "Safety & Environmental Health (EHS)")`
    - `("technical_sop", "Standard Operating Procedure (SOP)")`
    - `("equipment_operation", "Equipment Operation & Calibration")`
    - `("quality_tools", "Quality Tools & Root Cause Analysis")`
    - `("general", "General Quality Orientation")`
  - `DELIVERY_METHOD_CHOICES` (`max_length=24`):
    - `("read_and_understand", "Read & Understand (Document)")`
    - `("classroom_lecture", "Classroom / Instructor-Led")`
    - `("on_the_job", "On-the-Job Training (OJT)")`
    - `("elearning", "Digital / e-Learning Module")`
    - `("vendor_external", "External Vendor Seminar")`
    - `("blended", "Blended Learning")`
  - `ASSESSMENT_METHOD_CHOICES` (`max_length=24`):
    - `("written_exam", "Written Examination / Quiz")`
    - `("practical_ojt", "Practical OJT Demonstration")`
    - `("attendance_only", "Attendance / Participation Only")`
    - `("both_exam_and_ojt", "Combined Exam & OJT Evaluation")`
    - `("manager_evaluation", "Manager Direct Evaluation")`
  - `STATUS_CHOICES` (`max_length=16`):
    - `("draft", "Draft")`
    - `("active", "Active")`
    - `("under_revision", "Under Revision")`
    - `("retired", "Retired")`
  - `CATEGORY_CSS`:
    - `"gxp_compliance": "badge-red"`
    - `"safety_ehs": "badge-amber"`
    - `"technical_sop": "badge-info"`
    - `"equipment_operation": "badge-slate"`
    - `"quality_tools": "badge-green"`
    - `"general": "badge-muted"`
  - `DELIVERY_METHOD_CSS`:
    - `"read_and_understand": "badge-info"`
    - `"classroom_lecture": "badge-slate"`
    - `"on_the_job": "badge-amber"`
    - `"elearning": "badge-green"`
    - `"vendor_external": "badge-slate"`
    - `"blended": "badge-info"`
  - `ASSESSMENT_METHOD_CSS`:
    - `"written_exam": "badge-info"`
    - `"practical_ojt": "badge-amber"`
    - `"attendance_only": "badge-muted"`
    - `"both_exam_and_ojt": "badge-green"`
    - `"manager_evaluation": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"active": "badge-green"`
    - `"under_revision": "badge-amber"`
    - `"retired": "badge-muted"`

- **Fields**:
  - `title`: `CharField(max_length=255, help_text="e.g. SOP-0042 Aseptic Gowning and Cleanroom Entry Protocol")`
  - `competency_matrix`: `ForeignKey("quality.CompetencyMatrix", on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")`
  - `course_code`: `CharField(max_length=64, blank=True, help_text="Internal course code or catalog ID")`
  - `category`: `CharField(max_length=32, choices=CATEGORY_CHOICES, default="technical_sop", db_index=True)`
  - `delivery_method`: `CharField(max_length=24, choices=DELIVERY_METHOD_CHOICES, default="read_and_understand", db_index=True)`
  - `assessment_method`: `CharField(max_length=24, choices=ASSESSMENT_METHOD_CHOICES, default="written_exam", db_index=True)`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `controlled_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked_training_courses")`
  - `document_revision`: `CharField(max_length=32, blank=True, help_text="Document revision number e.g. Rev C")`
  - `retrain_on_revision`: `BooleanField(default=True, help_text="Trigger automated retraining assignments when bound SOP document is revised")`
  - `duration_hours`: `DecimalField(max_digits=5, decimal_places=2, default=1.00, help_text="Course duration in hours e.g. 2.50")`
  - `passing_score`: `PositiveSmallIntegerField(default=80, help_text="Minimum passing percentage e.g. 80")`
  - `ojt_checklist_criteria`: `TextField(blank=True, help_text="Structured practical evaluation checklist for OJT evaluations")`
  - `syllabus_summary`: `TextField(blank=True, help_text="Learning objectives, syllabus topics, and reference materials")`
  - `external_provider`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="provided_quality_courses")`
  - `instructor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="instructed_quality_courses")`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcrs_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qcrs_ten_status")` (19)
  - `Index(fields=["tenant", "category"], name="idx_qcrs_ten_cat")` (16)
  - `Index(fields=["tenant", "delivery_method"], name="idx_qcrs_ten_delivery")` (21)
  - `Index(fields=["tenant", "assessment_method"], name="idx_qcrs_ten_assess")` (19)
  - `Index(fields=["tenant", "competency_matrix"], name="idx_qcrs_ten_matrix")` (19)
  - `Index(fields=["tenant", "controlled_document"], name="idx_qcrs_ten_cdoc")` (17)
  - `Index(fields=["tenant", "-created_at"], name="idx_qcrs_ten_created")` (20)

- **Helper Properties**:
  - `enrollments_count`: count of related `enrollments`
  - `active_enrollments_count`: count of enrollments where status in ("assigned", "in_progress")
  - `completed_enrollments_count`: count of enrollments where status in ("completed", "verified")

---

### 1.3 `TrainingEnrollment` (`TrainingEnrollments.py`)
- **`NUMBER_PREFIX`**: `"QENR"`
- **`Meta.ordering`**: `["-assigned_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Training Enrollment"` / `"Training Enrollments"`
- **Choices & Badge Maps**:
  - `ASSIGNMENT_REASON_CHOICES` (`max_length=32`):
    - `("onboarding_new_hire", "New Hire / Onboarding Qualification")`
    - `("annual_refresher", "Annual / Periodic Refresher Training")`
    - `("dco_revision_retrain", "Document Revision (DCO) Retraining")`
    - `("capa_corrective_action", "CAPA Corrective Action Retraining")`
    - `("role_transfer", "Role Change / Promotion Transfer")`
    - `("manager_assignment", "Manager / Supervisor Assignment")`
    - `("remediation_retrain", "Remediation / Failed Attempt Retrain")`
  - `STATUS_CHOICES` (`max_length=16`):
    - `("assigned", "Assigned / Pending")`
    - `("in_progress", "In Progress")`
    - `("completed", "Completed (Pending Verification)")`
    - `("verified", "Verified / Qualified")`
    - `("overdue", "Overdue")`
    - `("waived", "Waived / Exempt")`
    - `("failed", "Failed Assessment")`
  - `PRACTICAL_RATING_CHOICES` (`max_length=24`):
    - `("exceeds_standard", "Exceeds Standard")`
    - `("meets_standard", "Meets Standard (Proficient)")`
    - `("needs_improvement", "Needs Improvement")`
    - `("unsatisfactory", "Unsatisfactory / Not Qualified")`
  - `ASSIGNMENT_REASON_CSS`:
    - `"onboarding_new_hire": "badge-info"`
    - `"annual_refresher": "badge-slate"`
    - `"dco_revision_retrain": "badge-amber"`
    - `"capa_corrective_action": "badge-red"`
    - `"role_transfer": "badge-info"`
    - `"manager_assignment": "badge-slate"`
    - `"remediation_retrain": "badge-amber"`
  - `STATUS_CSS`:
    - `"assigned": "badge-info"`
    - `"in_progress": "badge-amber"`
    - `"completed": "badge-info"`
    - `"verified": "badge-green"`
    - `"overdue": "badge-red"`
    - `"waived": "badge-muted"`
    - `"failed": "badge-red"`
  - `PRACTICAL_RATING_CSS`:
    - `"exceeds_standard": "badge-green"`
    - `"meets_standard": "badge-info"`
    - `"needs_improvement": "badge-amber"`
    - `"unsatisfactory": "badge-red"`

- **Fields**:
  - `course`: `ForeignKey("quality.QualityTrainingCourse", on_delete=models.PROTECT, related_name="enrollments")`
  - `trainee`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quality_training_enrollments")`
  - `assignment_reason`: `CharField(max_length=32, choices=ASSIGNMENT_REASON_CHOICES, default="manager_assignment", db_index=True)`
  - `document_change_order`: `ForeignKey("quality.DocumentChangeOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_enrollments")`
  - `capa_action`: `ForeignKey("quality.CapaAction", on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_training_enrollments")`
  - `assigned_date`: `DateField(db_index=True)`
  - `due_date`: `DateField(db_index=True)`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default="assigned", db_index=True)`
  - `completion_date`: `DateField(null=True, blank=True)`
  - `score`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Exam score percentage e.g. 95.00")`
  - `is_passed`: `BooleanField(default=False)`
  - `self_certified`: `BooleanField(default=False, help_text="Trainee confirmation of reading/understanding or course completion")`
  - `self_certified_at`: `DateTimeField(null=True, blank=True)`
  - `practical_evaluation_notes`: `TextField(blank=True, help_text="Supervisor practical OJT evaluation observations")`
  - `practical_verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_practical_trainings")`
  - `practical_verified_at`: `DateTimeField(null=True, blank=True)`
  - `practical_rating`: `CharField(max_length=24, choices=PRACTICAL_RATING_CHOICES, null=True, blank=True)`
  - `waiver_reason`: `TextField(blank=True, help_text="Formal regulatory justification for waiver or exemption")`
  - `waived_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="waived_training_enrollments")`
  - `waived_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qenr_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qenr_ten_status")` (19)
  - `Index(fields=["tenant", "trainee"], name="idx_qenr_ten_trainee")` (20)
  - `Index(fields=["tenant", "course"], name="idx_qenr_ten_course")` (19)
  - `Index(fields=["tenant", "due_date"], name="idx_qenr_ten_due")` (16)
  - `Index(fields=["tenant", "assignment_reason"], name="idx_qenr_ten_reason")` (19)
  - `Index(fields=["tenant", "-created_at"], name="idx_qenr_ten_created")` (20)

- **Helper Properties**:
  - `is_overdue`: returns True if `status in ("assigned", "in_progress")` and `due_date < timezone.now().date()`
  - `days_remaining`: integer days until due_date (negative if overdue)
  - `requires_practical_verification`: True if course assessment_method in ("practical_ojt", "both_exam_and_ojt") and practical_verified_at is None

---

### 1.4 `CompetencyCertification` (`CompetencyCertifications.py`)
- **`NUMBER_PREFIX`**: `"QCERT"`
- **`Meta.ordering`**: `["-issue_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Competency Certification"` / `"Competency Certifications"`
- **Choices & Badge Maps**:
  - `QUALIFICATION_LEVEL_CHOICES` (`max_length=32`):
    - `("level_1_novice", "Level 1: Novice / Supervised Operator")`
    - `("level_2_qualified", "Level 2: Fully Qualified / Independent")`
    - `("level_3_senior_specialist", "Level 3: Senior Specialist / SME")`
    - `("level_4_trainer_assessor", "Level 4: Certified Trainer / Assessor")`
  - `STATUS_CHOICES` (`max_length=16`):
    - `("active", "Active / Valid")`
    - `("expiring_soon", "Expiring Soon (<30 Days)")`
    - `("expired", "Expired")`
    - `("suspended", "Suspended")`
    - `("revoked", "Revoked")`
    - `("superseded", "Superseded / Renewed")`
  - `QUALIFICATION_LEVEL_CSS`:
    - `"level_1_novice": "badge-slate"`
    - `"level_2_qualified": "badge-info"`
    - `"level_3_senior_specialist": "badge-green"`
    - `"level_4_trainer_assessor": "badge-amber"`
  - `STATUS_CSS`:
    - `"active": "badge-green"`
    - `"expiring_soon": "badge-amber"`
    - `"expired": "badge-red"`
    - `"suspended": "badge-red"`
    - `"revoked": "badge-red"`
    - `"superseded": "badge-muted"`

- **Fields**:
  - `enrollment`: `ForeignKey("quality.TrainingEnrollment", on_delete=models.SET_NULL, null=True, blank=True, related_name="certifications")`
  - `trainee`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="competency_certifications")`
  - `course`: `ForeignKey("quality.QualityTrainingCourse", on_delete=models.PROTECT, related_name="issued_certifications")`
  - `competency_matrix`: `ForeignKey("quality.CompetencyMatrix", on_delete=models.SET_NULL, null=True, blank=True, related_name="certified_holders")`
  - `qualification_title`: `CharField(max_length=255, help_text="e.g. Certified Aseptic Fill Suite Level 2 Independent Operator")`
  - `qualification_level`: `CharField(max_length=32, choices=QUALIFICATION_LEVEL_CHOICES, default="level_2_qualified", db_index=True)`
  - `certificate_hash`: `CharField(max_length=64, editable=False, db_index=True, help_text="SHA-256 tamper-evident verification fingerprint")`
  - `issue_date`: `DateField(db_index=True)`
  - `valid_until`: `DateField(null=True, blank=True, db_index=True, help_text="Certification expiration date (null if permanent)")`
  - `renewal_interval_months`: `PositiveSmallIntegerField(default=12, help_text="Renewal frequency in months e.g. 12 or 24")`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default="active", db_index=True)`
  - `authorized_work_centers`: `TextField(blank=True, help_text="Specific cleanroom suites, production lines, or equipment models authorized")`
  - `certified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authorized_competency_certifications")`
  - `electronic_signature`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="authorized_certifications")`
  - `suspension_reason`: `TextField(blank=True, help_text="Documented rationale for certification suspension or revocation")`
  - `notes`: `TextField(blank=True)`

- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcert_ten_num_uniq")` (26)
  - `Index(fields=["tenant", "status"], name="idx_qcert_ten_status")` (20)
  - `Index(fields=["tenant", "trainee"], name="idx_qcert_ten_trainee")` (21)
  - `Index(fields=["tenant", "course"], name="idx_qcert_ten_course")` (20)
  - `Index(fields=["tenant", "valid_until"], name="idx_qcert_ten_valid")` (19)
  - `Index(fields=["tenant", "qualification_level"], name="idx_qcert_ten_level")` (19)
  - `Index(fields=["tenant", "certificate_hash"], name="idx_qcert_ten_hash")` (18)
  - `Index(fields=["tenant", "-created_at"], name="idx_qcert_ten_created")` (21)

- **Helper Properties & Methods**:
  - `is_valid`: returns True if `status == "active"` and (`valid_until is None` or `valid_until >= timezone.now().date()`)
  - `days_until_expiration`: integer days until `valid_until` (None if permanent, negative if expired)
  - `generate_certificate_hash()`: SHA-256 of `f"{self.tenant_id}:{self.number}:{self.trainee_id}:{self.course_id}:{self.issue_date}:{settings.SECRET_KEY}"`

---

## 2. Forms Contract (`apps/quality/forms/TrainingCompetency/`)

All forms inherit `forms.ModelForm` with styling applied in `__init__` via standard `form-input`, `form-select`, `form-textarea` classes from `theme.css`.

### 2.1 `CompetencyMatrixForm` (`CompetencyMatrices.py`)
- **`model`**: `CompetencyMatrix`
- **`fields`**: `["title", "role_title", "qualification_tier", "department", "criticality", "revision", "minimum_passing_score", "validity_period_months", "prerequisite_experience_months", "description", "approved_by", "approval_date", "notes"]`
- **`exclude`**: `["tenant", "number", "status", "created_at", "updated_at"]`
- **Queryset Scoping**:
  - `department`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - `approved_by`: `User.objects.filter(tenant=self.tenant, is_active=True)`

### 2.2 `QualityTrainingCourseForm` (`QualityTrainingCourses.py`)
- **`model`**: `QualityTrainingCourse`
- **`fields`**: `["title", "competency_matrix", "course_code", "category", "delivery_method", "assessment_method", "controlled_document", "document_revision", "retrain_on_revision", "duration_hours", "passing_score", "ojt_checklist_criteria", "syllabus_summary", "external_provider", "instructor", "notes"]`
- **`exclude`**: `["tenant", "number", "status", "created_at", "updated_at"]`
- **Queryset Scoping**:
  - `competency_matrix`: `CompetencyMatrix.objects.filter(tenant=self.tenant)`
  - `controlled_document`: `ControlledDocument.objects.filter(tenant=self.tenant)`
  - `external_provider`: `Party.objects.filter(tenant=self.tenant)`
  - `instructor`: `User.objects.filter(tenant=self.tenant, is_active=True)`

### 2.3 `TrainingEnrollmentForm` (`TrainingEnrollments.py`)
- **`model`**: `TrainingEnrollment`
- **`fields`**: `["course", "trainee", "assignment_reason", "document_change_order", "capa_action", "assigned_date", "due_date", "notes"]`
- **`exclude`**: `["tenant", "number", "status", "completion_date", "score", "is_passed", "self_certified", "self_certified_at", "practical_evaluation_notes", "practical_verified_by", "practical_verified_at", "practical_rating", "waiver_reason", "waived_by", "waived_at", "created_at", "updated_at"]`
- **Queryset Scoping**:
  - `course`: `QualityTrainingCourse.objects.filter(tenant=self.tenant)`
  - `trainee`: `User.objects.filter(tenant=self.tenant, is_active=True)`
  - `document_change_order`: `DocumentChangeOrder.objects.filter(tenant=self.tenant)`
  - `capa_action`: `CapaAction.objects.filter(tenant=self.tenant)`

### 2.4 `TrainingCompletionForm` (`TrainingEnrollments.py`)
- **Fields**: `["score", "notes"]`
- For exam submission and trainee self-certification.

### 2.5 `PracticalVerificationForm` (`TrainingEnrollments.py`)
- **Fields**: `["practical_rating", "practical_evaluation_notes"]`
- For supervisor evaluation of OJT practical execution.

### 2.6 `TrainingWaiverForm` (`TrainingEnrollments.py`)
- **Fields**: `["waiver_reason"]`
- For formal compliance waiver/exemption.

### 2.7 `CompetencyCertificationForm` (`CompetencyCertifications.py`)
- **`model`**: `CompetencyCertification`
- **`fields`**: `["enrollment", "trainee", "course", "competency_matrix", "qualification_title", "qualification_level", "issue_date", "valid_until", "renewal_interval_months", "authorized_work_centers", "certified_by", "notes"]`
- **`exclude`**: `["tenant", "number", "status", "certificate_hash", "electronic_signature", "suspension_reason", "created_at", "updated_at"]`
- **Queryset Scoping**:
  - `enrollment`: `TrainingEnrollment.objects.filter(tenant=self.tenant)`
  - `trainee`: `User.objects.filter(tenant=self.tenant, is_active=True)`
  - `course`: `QualityTrainingCourse.objects.filter(tenant=self.tenant)`
  - `competency_matrix`: `CompetencyMatrix.objects.filter(tenant=self.tenant)`
  - `certified_by`: `User.objects.filter(tenant=self.tenant, is_active=True)`

### 2.8 `CertificationSuspensionForm` (`CompetencyCertifications.py`)
- **Fields**: `["suspension_reason"]`

---

## 3. URLs Contract (`apps/quality/urls/TrainingCompetency/`)

Mounted under `apps/quality/urls/__init__.py`. Literal URLs defined BEFORE `<int:pk>`:

```python
# Training & Competency Management
path("training/dashboard/", views.training_compliance_dashboard, name="training_compliance_dashboard"),
path("training/dossier/", views.employee_training_dossier, name="employee_training_dossier"),

# Competency Matrix
path("training/matrices/", views.competency_matrix_list, name="competency_matrix_list"),
path("training/matrices/create/", views.competency_matrix_create, name="competency_matrix_create"),
path("training/matrices/export/", views.competency_matrix_export, name="competency_matrix_export"),
path("training/matrices/<int:pk>/", views.competency_matrix_detail, name="competency_matrix_detail"),
path("training/matrices/<int:pk>/edit/", views.competency_matrix_edit, name="competency_matrix_edit"),
path("training/matrices/<int:pk>/delete/", views.competency_matrix_delete, name="competency_matrix_delete"),
path("training/matrices/<int:pk>/approve/", views.competency_matrix_approve, name="competency_matrix_approve"),
path("training/matrices/<int:pk>/retire/", views.competency_matrix_retire, name="competency_matrix_retire"),

# Training Course
path("training/courses/", views.training_course_list, name="training_course_list"),
path("training/courses/create/", views.training_course_create, name="training_course_create"),
path("training/courses/export/", views.training_course_export, name="training_course_export"),
path("training/courses/<int:pk>/", views.training_course_detail, name="training_course_detail"),
path("training/courses/<int:pk>/edit/", views.training_course_edit, name="training_course_edit"),
path("training/courses/<int:pk>/delete/", views.training_course_delete, name="training_course_delete"),
path("training/courses/<int:pk>/activate/", views.training_course_activate, name="training_course_activate"),
path("training/courses/<int:pk>/retire/", views.training_course_retire, name="training_course_retire"),

# Training Enrollment
path("training/enrollments/", views.training_enrollment_list, name="training_enrollment_list"),
path("training/enrollments/create/", views.training_enrollment_create, name="training_enrollment_create"),
path("training/enrollments/export/", views.training_enrollment_export, name="training_enrollment_export"),
path("training/enrollments/<int:pk>/", views.training_enrollment_detail, name="training_enrollment_detail"),
path("training/enrollments/<int:pk>/edit/", views.training_enrollment_edit, name="training_enrollment_edit"),
path("training/enrollments/<int:pk>/delete/", views.training_enrollment_delete, name="training_enrollment_delete"),
path("training/enrollments/<int:pk>/complete/", views.training_enrollment_complete, name="training_enrollment_complete"),
path("training/enrollments/<int:pk>/verify/", views.training_enrollment_verify, name="training_enrollment_verify"),
path("training/enrollments/<int:pk>/waive/", views.training_enrollment_waive, name="training_enrollment_waive"),

# Competency Certification
path("training/certifications/", views.competency_certification_list, name="competency_certification_list"),
path("training/certifications/create/", views.competency_certification_create, name="competency_certification_create"),
path("training/certifications/export/", views.competency_certification_export, name="competency_certification_export"),
path("training/certifications/<int:pk>/", views.competency_certification_detail, name="competency_certification_detail"),
path("training/certifications/<int:pk>/edit/", views.competency_certification_edit, name="competency_certification_edit"),
path("training/certifications/<int:pk>/delete/", views.competency_certification_delete, name="competency_certification_delete"),
path("training/certifications/<int:pk>/renew/", views.competency_certification_renew, name="competency_certification_renew"),
path("training/certifications/<int:pk>/suspend/", views.competency_certification_suspend, name="competency_certification_suspend"),
```

---

## 4. Views & Context Variables Contract (`apps/quality/views/TrainingCompetency/`)

All views are function-based, decorated with `@login_required` (mutations `@require_POST`, admin deletions `@tenant_admin_required`), tenant-scoped via `request.tenant`, and call `write_audit_log(request.user, obj, verb, tenant=request.tenant)`.

### 4.1 `CompetencyMatrices.py`
- `competency_matrix_list`:
  - List variable: `matrices` (Page object or queryset)
  - Pagination: `page_obj`, `paginator`, `is_paginated`
  - Total count: `total_count`
  - Choices passed: `tier_choices`, `criticality_choices`, `status_choices`
  - FK dropdowns: `departments` (`OrgUnit.objects.filter(tenant=request.tenant)`)
  - Selected filter values: `selected_status`, `selected_tier`, `selected_criticality`, `selected_department`, `q`
- `competency_matrix_detail`:
  - Detail object variable: `matrix`
  - Sub-collections: `courses` (`matrix.courses.all()`)
- `competency_matrix_create` / `competency_matrix_edit`:
  - Form variable: `form`
  - Edit-mode object variable: `matrix` (`None` in create)

### 4.2 `QualityTrainingCourses.py`
- `training_course_list`:
  - List variable: `courses`
  - Pagination: `page_obj`, `paginator`, `is_paginated`
  - Total count: `total_count`
  - Choices passed: `category_choices`, `delivery_choices`, `assessment_choices`, `status_choices`
  - FK dropdowns: `matrices` (`CompetencyMatrix.objects.filter(tenant=request.tenant)`), `documents` (`ControlledDocument.objects.filter(tenant=request.tenant)`)
  - Selected filter values: `selected_category`, `selected_delivery`, `selected_assessment`, `selected_status`, `selected_matrix`, `selected_doc`, `q`
- `training_course_detail`:
  - Detail object variable: `course`
  - Sub-collections: `recent_enrollments` (`course.enrollments.all()[:10]`)
- `training_course_create` / `training_course_edit`:
  - Form variable: `form`
  - Edit-mode object variable: `course` (`None` in create)

### 4.3 `TrainingEnrollments.py`
- `training_enrollment_list`:
  - List variable: `enrollments`
  - Pagination: `page_obj`, `paginator`, `is_paginated`
  - Total count: `total_count`
  - Choices passed: `reason_choices`, `status_choices`
  - FK dropdowns: `courses` (`QualityTrainingCourse.objects.filter(tenant=request.tenant)`), `trainees` (`User.objects.filter(tenant=request.tenant, is_active=True)`)
  - Selected filter values: `selected_status`, `selected_reason`, `selected_course`, `selected_trainee`, `selected_overdue`, `q`
- `training_enrollment_detail`:
  - Detail object variable: `enrollment`
  - Related actions: `completion_form`, `verification_form`, `waiver_form`
- `training_enrollment_create` / `training_enrollment_edit`:
  - Form variable: `form`
  - Edit-mode object variable: `enrollment` (`None` in create)

### 4.4 `CompetencyCertifications.py`
- `competency_certification_list`:
  - List variable: `certifications`
  - Pagination: `page_obj`, `paginator`, `is_paginated`
  - Total count: `total_count`
  - Choices passed: `level_choices`, `status_choices`
  - FK dropdowns: `trainees` (`User.objects.filter(tenant=request.tenant, is_active=True)`), `courses` (`QualityTrainingCourse.objects.filter(tenant=request.tenant)`)
  - Selected filter values: `selected_status`, `selected_level`, `selected_trainee`, `selected_course`, `selected_expiring`, `q`
- `competency_certification_detail`:
  - Detail object variable: `certification`
- `competency_certification_create` / `competency_certification_edit`:
  - Form variable: `form`
  - Edit-mode object variable: `certification` (`None` in create)

### 4.5 `training_compliance_dashboard`
- Context keys:
  - `kpis`: dict with `compliance_rate`, `active_certifications`, `overdue_enrollments`, `expiring_certifications`, `total_courses`
  - `recent_enrollments`: queryset
  - `expiring_certifications`: queryset
  - `department_metrics`: list of dicts with department names and completed vs overdue stats

### 4.6 `employee_training_dossier`
- Context keys:
  - `trainee`: User instance
  - `users`: queryset of active tenant users
  - `active_certifications`: queryset
  - `completed_enrollments`: queryset
  - `pending_enrollments`: queryset
  - `compliance_summary`: dict with total, completed, pending, overdue counts

---

## 5. Navigation `LIVE_LINKS["12.12"]` Contract

In `apps/core/navigation.py`:

```python
    "12.12": {
        "Training Needs Analysis": "quality:competency_matrix_list",
        "Course Development & Delivery": "quality:training_course_list",
        "Training Scheduling & Enrollment": "quality:training_enrollment_list",
        "Competency Assessment & Certification": "quality:competency_certification_list",
        "Training Records & Compliance": "quality:training_compliance_dashboard",
    },
```

---

## 6. Seeder Contract (`apps/quality/management/commands/seed_quality.py`)

The seeder command will be extended idempotently (`seed_training_competency(tenant, users, depts, docs, dcos, capas)`):
- Creates at least 3 `CompetencyMatrix` records (`QMTX`)
- Creates at least 4 `QualityTrainingCourse` records (`QCRS`) bound to SOP documents and matrices
- Creates at least 6 `TrainingEnrollment` records (`QENR`) in different states (`assigned`, `in_progress`, `completed`, `verified`, `overdue`)
- Creates at least 4 `CompetencyCertification` records (`QCERT`) with valid hashes and expiration dates
- Running `python manage.py seed_quality` twice yields zero duplicates.
