# Module 13.9 Pre-Build Contract — Records Management & Compliance (`apps/documents/`)

> Frozen in Phase 3.1 before any entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.9"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0018_...`)
- **Package Directories**:
  - `apps/documents/models/RecordsManagement/`
  - `apps/documents/forms/RecordsManagement/`
  - `apps/documents/views/RecordsManagement/`
  - `apps/documents/urls/RecordsManagement/`
  - `templates/documents/records_management/{retention_schedule,record_declaration,legal_hold,destruction_certificate}/{list,detail,form}.html` + `disposition_review/board.html` + `vital_records/list.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"declare"`, `"lock"`, `"cutoff"`, `"hold"`, `"release"`, `"approve"`, `"execute"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `documents.Document`, `documents.DocumentVersion`, `core.LegalHold`, `documents.RetentionSchedule`, `documents.RecordDeclaration`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/RecordsManagement/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `RetentionSchedule` (`RetentionSchedules.py`)
- **`NUMBER_PREFIX`**: `"DRTN"`
- **`Meta.ordering`**: `["code", "name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Retention Schedule"` / `"Retention Schedules"`
- **Choices & Badge Maps**:
  - `TRIGGER_TYPE_CHOICES` (`max_length=30`):
    - `("creation_date", "Creation Date")`
    - `("last_modified", "Last Modified Date")`
    - `("declaration_date", "Record Declaration Date")`
    - `("event_based", "Event Completion (Superseded/Closed)")`
  - `CUTOFF_RULE_CHOICES` (`max_length=30`):
    - `("immediate", "Immediate Cutoff")`
    - `("calendar_year_end", "End of Calendar Year (Dec 31)")`
    - `("fiscal_year_end", "End of Fiscal Year")`
    - `("event_completion", "Upon Specified Trigger Event")`
  - `DISPOSITION_ACTION_CHOICES` (`max_length=30`):
    - `("destroy", "Secure Destruction")`
    - `("archive", "Permanent Archival / Long-Term Preservation")`
    - `("review", "Disposition Review & Re-evaluation")`
    - `("transfer", "Transfer to National / External Archives")`
  - `FRAMEWORK_CHOICES` (`max_length=30`):
    - `("iso_15489", "ISO 15489 (Information & Documentation)")`
    - `("dod_5015_2", "DoD 5015.2 (Records Management Standard)")`
    - `("sec_17a_4", "SEC Rule 17a-4 (Electronic Records WORM)")`
    - `("gdpr", "GDPR (Article 5(1)(e) Storage Limitation)")`
    - `("hipaa", "HIPAA (45 CFR § 164.316(b)(2)(i))")`
    - `("irs_tax", "IRS Tax & Financial Records (7 Years)")`
    - `("general", "General Corporate Governance")`
  - `RETENTION_MODE_CHOICES` (`max_length=30`):
    - `("modifiable", "Modifiable (Standard Corporate)")`
    - `("regulatory_worm", "Regulatory WORM (Strict Non-Erasable)")`
  - `FRAMEWORK_CSS`:
    - `"iso_15489": "badge-info"`
    - `"dod_5015_2": "badge-slate"`
    - `"sec_17a_4": "badge-red"`
    - `"gdpr": "badge-amber"`
    - `"hipaa": "badge-green"`
    - `"irs_tax": "badge-slate"`
    - `"general": "badge-muted"`
  - `RETENTION_MODE_CSS`:
    - `"modifiable": "badge-info"`
    - `"regulatory_worm": "badge-red"`
  - `DISPOSITION_ACTION_CSS`:
    - `"destroy": "badge-red"`
    - `"archive": "badge-green"`
    - `"review": "badge-amber"`
    - `"transfer": "badge-info"`
  - `STATUS_CSS`:
    - `True: "badge-green"`
    - `False: "badge-muted"`
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=255)`
  - `code`: `CharField(max_length=50, db_index=True)`
  - `description`: `TextField(blank=True)`
  - `retention_period_years`: `PositiveIntegerField(default=7)`
  - `retention_period_months`: `PositiveIntegerField(default=0)`
  - `is_permanent`: `BooleanField(default=False)`
  - `trigger_type`: `CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES, default="creation_date")`
  - `cutoff_rule`: `CharField(max_length=30, choices=CUTOFF_RULE_CHOICES, default="calendar_year_end")`
  - `disposition_action`: `CharField(max_length=30, choices=DISPOSITION_ACTION_CHOICES, default="destroy")`
  - `compliance_framework`: `CharField(max_length=30, choices=FRAMEWORK_CHOICES, default="iso_15489", db_index=True)`
  - `retention_mode`: `CharField(max_length=30, choices=RETENTION_MODE_CHOICES, default="modifiable")`
  - `legal_citation`: `CharField(max_length=255, blank=True)`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="retention_schedules")`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `UniqueConstraint(fields=["tenant", "code"], name="doc_drtn_tnt_code_uniq")`
  - `Index(fields=["tenant", "compliance_framework"], name="doc_drtn_tnt_fmwk_idx")`
  - `Index(fields=["tenant", "is_active"], name="doc_drtn_tnt_act_idx")`

---

### 1.2 `RecordDeclaration` (`RecordDeclarations.py`)
- **`NUMBER_PREFIX`**: `"DRCD"`
- **`Meta.ordering`**: `["-declaration_date"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Record Declaration"` / `"Record Declarations"`
- **Choices & Badge Maps**:
  - `DECLARATION_MODE_CHOICES` (`max_length=30`):
    - `("manual", "Manual User Declaration")`
    - `("automatic_rule", "Automatic Metadata/Rule Trigger")`
    - `("workflow_trigger", "Workflow Approval Finalization")`
  - `RECORD_STATUS_CHOICES` (`max_length=30`):
    - `("active", "Active Record (Pre-Cutoff)")`
    - `("cutoff", "Cutoff Triggered (In Retention)")`
    - `("pending_disposition", "Pending Disposition Review")`
    - `("under_legal_hold", "Frozen Under Legal Hold")`
    - `("disposed", "Disposed / Destroyed")`
  - `DECLARATION_MODE_CSS`:
    - `"manual": "badge-info"`
    - `"automatic_rule": "badge-slate"`
    - `"workflow_trigger": "badge-green"`
  - `RECORD_STATUS_CSS`:
    - `"active": "badge-green"`
    - `"cutoff": "badge-info"`
    - `"pending_disposition": "badge-amber"`
    - `"under_legal_hold": "badge-red"`
    - `"disposed": "badge-muted"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="record_declarations")`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="record_declarations")`
  - `retention_schedule`: `ForeignKey("documents.RetentionSchedule", on_delete=models.PROTECT, related_name="declared_records")`
  - `declared_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="declared_records")`
  - `declaration_date`: `DateTimeField(default=timezone.now, db_index=True)`
  - `declaration_mode`: `CharField(max_length=30, choices=DECLARATION_MODE_CHOICES, default="manual")`
  - `record_status`: `CharField(max_length=30, choices=RECORD_STATUS_CHOICES, default="active", db_index=True)`
  - `is_vital_record`: `BooleanField(default=False, db_index=True)`
  - `vital_review_frequency_months`: `PositiveIntegerField(default=12)`
  - `last_vital_review_date`: `DateField(null=True, blank=True)`
  - `is_locked`: `BooleanField(default=True)`
  - `cutoff_date`: `DateField(null=True, blank=True, db_index=True)`
  - `cutoff_triggered_at`: `DateTimeField(null=True, blank=True)`
  - `disposition_due_date`: `DateField(null=True, blank=True, db_index=True)`
  - `version_hash_snapshot`: `CharField(max_length=64, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `Index(fields=["tenant", "record_status"], name="doc_drcd_tnt_sts_idx")`
  - `Index(fields=["tenant", "is_vital_record"], name="doc_drcd_tnt_vtl_idx")`
  - `Index(fields=["tenant", "disposition_due_date"], name="doc_drcd_tnt_due_idx")`

---

### 1.3 `DocumentLegalHold` (`DocumentLegalHolds.py`)
- **`NUMBER_PREFIX`**: `"DHLD"`
- **`Meta.ordering`**: `["-placed_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Legal Hold"` / `"Document Legal Holds"`
- **Choices & Badge Maps**:
  - `HOLD_REASON_CHOICES` (`max_length=30`):
    - `("litigation", "Pending or Threatened Litigation")`
    - `("regulatory_audit", "Government / Regulatory Audit")`
    - `("tax_investigation", "Tax / Financial Investigation")`
    - `("internal_inquiry", "Internal Compliance Inquiry")`
    - `("ediscovery_matter", "Formal eDiscovery Preservation")`
  - `HOLD_REASON_CSS`:
    - `"litigation": "badge-red"`
    - `"regulatory_audit": "badge-amber"`
    - `"tax_investigation": "badge-slate"`
    - `"internal_inquiry": "badge-info"`
    - `"ediscovery_matter": "badge-red"`
  - `HOLD_STATUS_CSS`:
    - `True: "badge-red"`   # Active hold
    - `False: "badge-muted"` # Released
- **Fields (exact names & types)**:
  - `matter_name`: `CharField(max_length=255)`
  - `matter_number`: `CharField(max_length=100, db_index=True)`
  - `hold_reason`: `CharField(max_length=30, choices=HOLD_REASON_CHOICES, default="litigation")`
  - `description`: `TextField(blank=True)`
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="legal_holds")`
  - `placed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="placed_document_legal_holds")`
  - `placed_at`: `DateTimeField(default=timezone.now, db_index=True)`
  - `custodian`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="custodian_document_legal_holds")`
  - `custodian_notified`: `BooleanField(default=False)`
  - `custodian_acknowledged_at`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `released_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="released_document_legal_holds")`
  - `released_at`: `DateTimeField(null=True, blank=True)`
  - `release_justification`: `TextField(blank=True)`
  - `core_legal_hold`: `ForeignKey("core.LegalHold", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_holds")`
- **Constraints & Indexes**:
  - `Index(fields=["tenant", "is_active"], name="doc_dhld_tnt_act_idx")`
  - `Index(fields=["tenant", "matter_number"], name="doc_dhld_tnt_mat_idx")`
  - `Index(fields=["tenant", "document"], name="doc_dhld_tnt_doc_idx")`

---

### 1.4 `DestructionCertificate` (`DestructionCertificates.py`)
- **`NUMBER_PREFIX`**: `"DDST"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Destruction Certificate"` / `"Destruction Certificates"`
- **Choices & Badge Maps**:
  - `DISPOSITION_TYPE_CHOICES` (`max_length=30`):
    - `("destruction", "Permanent Secure Destruction")`
    - `("archival_transfer", "Transfer to Permanent Archives")`
    - `("deaccession", "Deaccession & Removal")`
  - `DESTRUCTION_METHOD_CHOICES` (`max_length=30`):
    - `("database_purge", "Cryptographic Deletion & DB Purge")`
    - `("dod_5220_22m", "DoD 5220.22-M Electronic Sanitization")`
    - `("nist_800_88", "NIST SP 800-88 Media Sanitization")`
    - `("cryptographic_erase", "Cryptographic Key Erasure (Zeroize)")`
    - `("physical_crosscut", "Physical Cross-Cut Shredding (Paper)")`
    - `("nara_transfer", "NARA / Electronic Records Archives Transfer")`
  - `CERTIFICATE_STATUS_CHOICES` (`max_length=30`):
    - `("pending_approval", "Pending Disposition Approval")`
    - `("authorized", "Authorized for Disposition")`
    - `("executed", "Executed & Certified Complete")`
    - `("rejected", "Rejected / Cancelled")`
  - `DISPOSITION_TYPE_CSS`:
    - `"destruction": "badge-red"`
    - `"archival_transfer": "badge-green"`
    - `"deaccession": "badge-amber"`
  - `DESTRUCTION_METHOD_CSS`:
    - `"database_purge": "badge-slate"`
    - `"dod_5220_22m": "badge-red"`
    - `"nist_800_88": "badge-red"`
    - `"cryptographic_erase": "badge-info"`
    - `"physical_crosscut": "badge-amber"`
    - `"nara_transfer": "badge-green"`
  - `STATUS_CSS`:
    - `"pending_approval": "badge-amber"`
    - `"authorized": "badge-info"`
    - `"executed": "badge-green"`
    - `"rejected": "badge-muted"`
- **Fields (exact names & types)**:
  - `record_declaration`: `ForeignKey("documents.RecordDeclaration", on_delete=models.SET_NULL, null=True, blank=True, related_name="destruction_certificates")`
  - `document_title_snapshot`: `CharField(max_length=255)`
  - `document_number_snapshot`: `CharField(max_length=50)`
  - `schedule_name_snapshot`: `CharField(max_length=255)`
  - `disposition_type`: `CharField(max_length=30, choices=DISPOSITION_TYPE_CHOICES, default="destruction")`
  - `destruction_method`: `CharField(max_length=30, choices=DESTRUCTION_METHOD_CHOICES, default="database_purge")`
  - `status`: `CharField(max_length=30, choices=CERTIFICATE_STATUS_CHOICES, default="pending_approval", db_index=True)`
  - `content_verification_hash`: `CharField(max_length=64, blank=True)`
  - `legal_hold_verified_clear`: `BooleanField(default=False)`
  - `hold_verification_date`: `DateTimeField(null=True, blank=True)`
  - `authorized_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="authorized_destruction_certificates")`
  - `authorized_at`: `DateTimeField(null=True, blank=True)`
  - `executed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="executed_destruction_certificates")`
  - `executed_at`: `DateTimeField(null=True, blank=True)`
  - `certificate_notes`: `TextField(blank=True)`
- **Constraints & Indexes**:
  - `Index(fields=["tenant", "status"], name="doc_ddst_tnt_sts_idx")`
  - `Index(fields=["tenant", "created_at"], name="doc_ddst_tnt_crt_idx")`

---

## 2. Forms Contract (`apps/documents/forms/RecordsManagement/`)

All forms inherit `apps.core.forms.TenantModelForm` and use `TenantUniqueMixin` / `reject_foreign`.

### 2.1 `RetentionScheduleForm` (`RetentionSchedules.py`)
- **`Meta.model`**: `RetentionSchedule`
- **`Meta.fields`**: `["name", "code", "description", "retention_period_years", "retention_period_months", "is_permanent", "trigger_type", "cutoff_rule", "disposition_action", "compliance_framework", "retention_mode", "legal_citation", "department", "is_active", "notes"]`
- **Form exclusions**: `tenant`, `number`
- **Tenant scoping**: `department` queryset filtered by `tenant=self.tenant`.
- **Validation**:
  - `reject_foreign(self, cleaned_data, ["department"])`
  - If `retention_mode == "regulatory_worm"`, warn or enforce that `retention_period_years > 0` or `is_permanent=True`.
  - Case-insensitive uniqueness check for `code` within tenant.

### 2.2 `RecordDeclarationForm` (`RecordDeclarations.py`)
- **`Meta.model`**: `RecordDeclaration`
- **`Meta.fields`**: `["document", "version", "retention_schedule", "declaration_mode", "is_vital_record", "vital_review_frequency_months", "notes"]`
- **Form exclusions**: `tenant`, `number`, `declared_by`, `declaration_date`, `record_status`, `is_locked`, `cutoff_date`, `cutoff_triggered_at`, `disposition_due_date`, `version_hash_snapshot`, `last_vital_review_date`
- **Tenant scoping**: `document`, `version`, `retention_schedule` querysets filtered by `tenant=self.tenant`.
- **Validation**:
  - `reject_foreign(self, cleaned_data, ["document", "version", "retention_schedule"])`
  - If `version` is provided, assert `version.document_id == document.id`.

### 2.3 `DocumentLegalHoldForm` (`DocumentLegalHolds.py`)
- **`Meta.model`**: `DocumentLegalHold`
- **`Meta.fields`**: `["matter_name", "matter_number", "hold_reason", "description", "document", "custodian", "core_legal_hold"]`
- **Form exclusions**: `tenant`, `number`, `placed_by`, `placed_at`, `is_active`, `released_by`, `released_at`, `release_justification`, `custodian_notified`, `custodian_acknowledged_at`
- **Tenant scoping**: `document`, `custodian`, `core_legal_hold` filtered by `tenant=self.tenant`.
- **Validation**:
  - `reject_foreign(self, cleaned_data, ["document", "custodian", "core_legal_hold"])`

### 2.4 `LegalHoldReleaseForm` (`DocumentLegalHolds.py`)
- Non-model or simple Form:
  - `release_justification`: `forms.CharField(widget=forms.Textarea, required=True)`

### 2.5 `DestructionCertificateForm` (`DestructionCertificates.py`)
- **`Meta.model`**: `DestructionCertificate`
- **`Meta.fields`**: `["record_declaration", "disposition_type", "destruction_method", "certificate_notes"]`
- **Form exclusions**: `tenant`, `number`, `document_title_snapshot`, `document_number_snapshot`, `schedule_name_snapshot`, `status`, `content_verification_hash`, `legal_hold_verified_clear`, `hold_verification_date`, `authorized_by`, `authorized_at`, `executed_by`, `executed_at`
- **Tenant scoping**: `record_declaration` filtered by `tenant=self.tenant` and `record_status__in=["cutoff", "pending_disposition"]`.
- **Validation**:
  - `reject_foreign(self, cleaned_data, ["record_declaration"])`
  - Assert target document has NO active `DocumentLegalHold` (`is_active=True`).

---

## 3. URLs Contract (`apps/documents/urls/RecordsManagement/`)

All routes belong to `app_name = "documents"` and concatenate into `apps/documents/urls/__init__.py`.

### 3.1 Retention Schedules (`RetentionSchedules.py`)
- `path("records/schedules/", views.retention_schedule_list, name="retention_schedule_list")`
- `path("records/schedules/create/", views.retention_schedule_create, name="retention_schedule_create")`
- `path("records/schedules/<int:pk>/", views.retention_schedule_detail, name="retention_schedule_detail")`
- `path("records/schedules/<int:pk>/edit/", views.retention_schedule_edit, name="retention_schedule_edit")`
- `path("records/schedules/<int:pk>/delete/", views.retention_schedule_delete, name="retention_schedule_delete")`

### 3.2 Record Declarations (`RecordDeclarations.py`)
- `path("records/declarations/", views.record_declaration_list, name="record_declaration_list")`
- `path("records/declarations/create/", views.record_declaration_create, name="record_declaration_create")`
- `path("records/declarations/<int:pk>/", views.record_declaration_detail, name="record_declaration_detail")`
- `path("records/declarations/<int:pk>/edit/", views.record_declaration_edit, name="record_declaration_edit")`
- `path("records/declarations/<int:pk>/delete/", views.record_declaration_delete, name="record_declaration_delete")`
- `path("records/declarations/<int:pk>/trigger-cutoff/", views.record_declaration_trigger_cutoff, name="record_declaration_trigger_cutoff")`

### 3.3 Document Legal Holds (`DocumentLegalHolds.py`)
- `path("records/holds/", views.legal_hold_list, name="legal_hold_list")`
- `path("records/holds/create/", views.legal_hold_create, name="legal_hold_create")`
- `path("records/holds/<int:pk>/", views.legal_hold_detail, name="legal_hold_detail")`
- `path("records/holds/<int:pk>/release/", views.legal_hold_release, name="legal_hold_release")`
- `path("records/holds/<int:pk>/acknowledge/", views.legal_hold_acknowledge, name="legal_hold_acknowledge")`

### 3.4 Destruction Certificates (`DestructionCertificates.py`)
- `path("records/certificates/", views.destruction_certificate_list, name="destruction_certificate_list")`
- `path("records/certificates/create/", views.destruction_certificate_create, name="destruction_certificate_create")`
- `path("records/certificates/<int:pk>/", views.destruction_certificate_detail, name="destruction_certificate_detail")`
- `path("records/certificates/<int:pk>/authorize/", views.destruction_certificate_authorize, name="destruction_certificate_authorize")`
- `path("records/certificates/<int:pk>/execute/", views.destruction_certificate_execute, name="destruction_certificate_execute")`

### 3.5 Specialized Registers (`DispositionReview.py` & `VitalRecords.py`)
- `path("records/disposition-board/", views.disposition_review_board, name="disposition_review_board")`
- `path("records/vital-register/", views.vital_records_list, name="vital_records_list")`

---

## 4. Views & Context Variables Contract (`apps/documents/views/RecordsManagement/`)

### 4.1 `RetentionSchedule` Views
- **`retention_schedule_list`**:
  - URL name: `"documents:retention_schedule_list"`
  - Template: `"documents/records_management/retention_schedule/list.html"`
  - Context keys:
    - `"schedules"` (Page object)
    - `"page_obj"` (same as schedules)
    - `"paginator"`
    - `"framework_choices"` (`RetentionSchedule.FRAMEWORK_CHOICES`)
    - `"retention_mode_choices"` (`RetentionSchedule.RETENTION_MODE_CHOICES`)
    - `"departments"` (`OrgUnit.objects.filter(tenant=request.tenant)`)
    - `"current_framework"` (`request.GET.get("compliance_framework", "")`)
    - `"current_mode"` (`request.GET.get("retention_mode", "")`)
    - `"current_status"` (`request.GET.get("status", "")`)
    - `"query"` (`request.GET.get("q", "")`)
- **`retention_schedule_detail`**:
  - URL name: `"documents:retention_schedule_detail"`
  - Template: `"documents/records_management/retention_schedule/detail.html"`
  - Context keys:
    - `"schedule"` (`RetentionSchedule` instance)
    - `"declared_records"` (`schedule.declared_records.select_related("document", "declared_by")[:10]`)
    - `"declared_records_count"`
- **`retention_schedule_create` / `retention_schedule_edit`**:
  - Template: `"documents/records_management/retention_schedule/form.html"`
  - Context keys:
    - `"form"`
    - `"schedule"` (None on create, instance on edit)
    - `"is_edit"` (`bool`)

### 4.2 `RecordDeclaration` Views
- **`record_declaration_list`**:
  - URL name: `"documents:record_declaration_list"`
  - Template: `"documents/records_management/record_declaration/list.html"`
  - Context keys:
    - `"declarations"` (Page object)
    - `"page_obj"`
    - `"paginator"`
    - `"status_choices"` (`RecordDeclaration.RECORD_STATUS_CHOICES`)
    - `"schedules"` (`RetentionSchedule.objects.filter(tenant=request.tenant)`)
    - `"current_status"` (`request.GET.get("status", "")`)
    - `"current_schedule"` (`request.GET.get("schedule", "")`)
    - `"current_vital"` (`request.GET.get("vital", "")`)
    - `"query"` (`request.GET.get("q", "")`)
- **`record_declaration_detail`**:
  - URL name: `"documents:record_declaration_detail"`
  - Template: `"documents/records_management/record_declaration/detail.html"`
  - Context keys:
    - `"declaration"` (`RecordDeclaration` instance)
    - `"active_holds"` (`declaration.document.legal_holds.filter(is_active=True)`)
    - `"certificates"` (`declaration.destruction_certificates.all()`)
- **`record_declaration_create` / `record_declaration_edit`**:
  - Template: `"documents/records_management/record_declaration/form.html"`
  - Context keys:
    - `"form"`
    - `"declaration"`
    - `"is_edit"`

### 4.3 `DocumentLegalHold` Views
- **`legal_hold_list`**:
  - URL name: `"documents:legal_hold_list"`
  - Template: `"documents/records_management/legal_hold/list.html"`
  - Context keys:
    - `"holds"` (Page object)
    - `"page_obj"`
    - `"paginator"`
    - `"reason_choices"` (`DocumentLegalHold.HOLD_REASON_CHOICES`)
    - `"current_reason"` (`request.GET.get("hold_reason", "")`)
    - `"current_status"` (`request.GET.get("status", "")`)
    - `"query"` (`request.GET.get("q", "")`)
- **`legal_hold_detail`**:
  - URL name: `"documents:legal_hold_detail"`
  - Template: `"documents/records_management/legal_hold/detail.html"`
  - Context keys:
    - `"hold"` (`DocumentLegalHold` instance)
    - `"release_form"` (`LegalHoldReleaseForm`)
- **`legal_hold_create`**:
  - Template: `"documents/records_management/legal_hold/form.html"`
  - Context keys:
    - `"form"`

### 4.4 `DestructionCertificate` Views
- **`destruction_certificate_list`**:
  - URL name: `"documents:destruction_certificate_list"`
  - Template: `"documents/records_management/destruction_certificate/list.html"`
  - Context keys:
    - `"certificates"` (Page object)
    - `"page_obj"`
    - `"paginator"`
    - `"status_choices"` (`DestructionCertificate.CERTIFICATE_STATUS_CHOICES`)
    - `"type_choices"` (`DestructionCertificate.DISPOSITION_TYPE_CHOICES`)
    - `"method_choices"` (`DestructionCertificate.DESTRUCTION_METHOD_CHOICES`)
    - `"current_status"` (`request.GET.get("status", "")`)
    - `"current_type"` (`request.GET.get("disposition_type", "")`)
    - `"query"` (`request.GET.get("q", "")`)
- **`destruction_certificate_detail`**:
  - URL name: `"documents:destruction_certificate_detail"`
  - Template: `"documents/records_management/destruction_certificate/detail.html"`
  - Context keys:
    - `"certificate"` (`DestructionCertificate` instance)
- **`destruction_certificate_create`**:
  - Template: `"documents/records_management/destruction_certificate/form.html"`
  - Context keys:
    - `"form"`

### 4.5 Specialized Views
- **`disposition_review_board`**:
  - URL name: `"documents:disposition_review_board"`
  - Template: `"documents/records_management/disposition_review/board.html"`
  - Context keys:
    - `"due_records"` (Records reaching cutoff/due date without hold)
    - `"held_records"` (Records reaching due date but blocked by active hold)
    - `"pending_certificates"` (Certificates awaiting authorization)
- **`vital_records_list`**:
  - URL name: `"documents:vital_records_list"`
  - Template: `"documents/records_management/vital_records/list.html"`
  - Context keys:
    - `"vital_records"` (Page object of records with `is_vital_record=True`)
    - `"page_obj"`
    - `"paginator"`
    - `"departments"`
    - `"query"`

---

## 5. Navigation Contract (`LIVE_LINKS["13.9"]` in `apps/core/navigation.py`)

Exact mapping from `NavERP.md` 13.9 feature bullets:
```python
    # 13.9 Records Management & Compliance
    "13.9": {
        "Records Classification & Retention": "documents:retention_schedule_list",
        "Records Declaration & Filing": "documents:record_declaration_list",
        "Legal Hold & eDiscovery": "documents:legal_hold_list",
        "Disposition & Destruction": "documents:destruction_certificate_list",
        "Compliance Framework Mapping": "documents:retention_schedule_list",
        # Extra live leaves:
        "Disposition Review Board": "documents:disposition_review_board",
        "Vital Records Register": "documents:vital_records_list",
    },
```
