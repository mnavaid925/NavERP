# Module 12.1 Pre-Build Contract — Document Control & Management (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.1"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (BRAND NEW APP — scaffold required; `config/settings.py` and `config/urls.py` wire-up required)
- **Migration**: Initial (`0001_initial.py` in `apps/quality/migrations/`)
- **Package Directories**:
  - `apps/quality/models/DocumentControl/`
  - `apps/quality/forms/DocumentControl/`
  - `apps/quality/views/DocumentControl/`
  - `apps/quality/urls/DocumentControl/`
  - `templates/quality/documentcontrol/{controlled_document,document_change_order,electronic_signature,document_acknowledgment}/{list,detail,form}.html` + `templates/quality/documentcontrol/document_archive_vault.html` (note: `e_signature_modal.html` placeholder was cleanly superseded by dedicated 21 CFR Part 11 page route `electronic_signature/form.html`)
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, changes=..., tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"submit"`, `"approve"`, `"effective"`, `"supersede"`, `"obsolete"`, `"archive"`, `"sign"`, `"ccb_dec"`, `"ack"` (every verb `<= 9` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Global `accounting.Currency` Rule (L39)**:
  - No currency fields are required in Document Control (purely governance/procedural).
  - All foreign keys are tenant-scoped: `core.OrgUnit`, `accounts.User`, `hrm.EmployeeProfile`.

---

## 1. Models & Choices Contract (`apps/quality/models/DocumentControl/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `ControlledDocument` (`ControlledDocuments.py`)
- **`NUMBER_PREFIX`**: `"QDOC"`
- **`Meta.ordering`**: `["-is_latest_revision", "number", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Controlled Document"` / `"Controlled Documents"`
- **Choices & Badge Maps**:
  - `DOCUMENT_TYPE_CHOICES` (`max_length=24`):
    - `("sop", "Standard Operating Procedure (SOP)")`
    - `("wi", "Work Instruction (WI)")`
    - `("policy", "Corporate Policy (POL)")`
    - `("manual", "Quality Manual (QM)")`
    - `("spec", "Product / Material Specification (SPEC)")`
    - `("form", "Form / Template (FORM)")`
    - `("protocol", "Validation Protocol / Plan (PROT)")`
    - `("record", "Quality Record / Report (REC)")`
  - `LIFECYCLE_STATE_CHOICES` (`max_length=28`):
    - `("draft", "Draft")`
    - `("in_review", "In Review")`
    - `("pending_approval", "Pending Approval")`
    - `("approved", "Approved")`
    - `("effective", "Effective")`
    - `("superseded", "Superseded")`
    - `("obsolete", "Obsolete")`
    - `("archived", "Archived")`
  - `CLASSIFICATION_CHOICES` (`max_length=24`):
    - `("public", "Public")`
    - `("internal", "Internal Quality Controlled")`
    - `("confidential", "Confidential")`
    - `("restricted", "Restricted GxP")`
  - `LIFECYCLE_CSS`:
    - `"draft": "badge-slate"`
    - `"in_review": "badge-amber"`
    - `"pending_approval": "badge-info"`
    - `"approved": "badge-info"`
    - `"effective": "badge-green"`
    - `"superseded": "badge-amber"`
    - `"obsolete": "badge-red"`
    - `"archived": "badge-muted"`
  - `CLASSIFICATION_CSS`:
    - `"public": "badge-slate"`
    - `"internal": "badge-info"`
    - `"confidential": "badge-amber"`
    - `"restricted": "badge-red"`
  - `DOCUMENT_TYPE_CSS`:
    - `"sop": "badge-info"`
    - `"wi": "badge-slate"`
    - `"policy": "badge-purple"`
    - `"manual": "badge-blue"`
    - `"spec": "badge-green"`
    - `"form": "badge-slate"`
    - `"protocol": "badge-amber"`
    - `"record": "badge-slate"`
  - `LOCKED_STATES = {"superseded", "obsolete", "archived"}`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `document_type`: `CharField(max_length=24, choices=DOCUMENT_TYPE_CHOICES, default="sop")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="controlled_documents")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="owned_controlled_documents")`
  - `revision`: `CharField(max_length=20, default="1.0")`
  - `is_latest_revision`: `BooleanField(default=True, db_index=True)`
  - `lifecycle_state`: `CharField(max_length=28, choices=LIFECYCLE_STATE_CHOICES, default="draft", db_index=True)`
  - `classification`: `CharField(max_length=24, choices=CLASSIFICATION_CHOICES, default="internal")`
  - `file`: `FileField(upload_to="quality/documents/%Y/%m/", blank=True, null=True)`
  - `description`: `TextField(blank=True)`
  - `change_summary`: `TextField(blank=True)`
  - `effective_date`: `DateField(null=True, blank=True)`
  - `review_interval_months`: `PositiveIntegerField(default=12)`
  - `next_review_date`: `DateField(null=True, blank=True)`
  - `retention_years`: `PositiveIntegerField(default=10)`
  - `supersedes`: `ForeignKey("self", on_delete=SET_NULL, null=True, blank=True, related_name="superseded_by_set")`
  - `superseded_by`: `ForeignKey("self", on_delete=SET_NULL, null=True, blank=True, related_name="supersedes_set")`
  - `is_template`: `BooleanField(default=False)`
  - `archived_at`: `DateTimeField(null=True, blank=True, editable=False)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qdoc_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "lifecycle_state"], name="idx_qdoc_ten_state")` (18)
  - `Index(fields=["tenant", "document_type"], name="idx_qdoc_ten_dtype")` (18)
  - `Index(fields=["tenant", "is_latest_revision"], name="idx_qdoc_ten_latest")` (19)
  - `Index(fields=["tenant", "effective_date"], name="idx_qdoc_ten_effdate")` (20)
  - `Index(fields=["tenant", "next_review_date"], name="idx_qdoc_ten_revdate")` (20)
  - `Index(fields=["tenant", "title"], name="idx_qdoc_ten_title")` (18)
- **Properties & Helper Methods**:
  - `@property def watermark_text(self)`: returns `"DRAFT"`, `"IN REVIEW"`, `"PENDING APPROVAL"`, `"APPROVED"`, `"EFFECTIVE - CONTROLLED COPY"`, `"SUPERSEDED - UNCONTROLLED"`, `"OBSOLETE - DO NOT USE"`, or `"ARCHIVED"` based on `lifecycle_state`.
  - `@property def is_effective(self)`: returns `self.lifecycle_state == "effective"`
  - `@property def is_locked(self)`: returns `self.lifecycle_state in self.LOCKED_STATES`
  - `@property def is_overdue_review(self)`: returns `bool(self.next_review_date and self.next_review_date < timezone.now().date())`

---

### 1.2 `DocumentChangeOrder` (`DocumentChangeOrders.py`)
- **`NUMBER_PREFIX`**: `"QDCR"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Change Order"` / `"Document Change Orders"`
- **Choices & Badge Maps**:
  - `CHANGE_TYPE_CHOICES` (`max_length=28`):
    - `("new_document", "New Document Creation")`
    - `("major_revision", "Major Revision")`
    - `("minor_revision", "Minor Revision")`
    - `("obsoletion", "Document Obsoletion")`
    - `("emergency_change", "Emergency Urgent Change")`
  - `PRIORITY_CHOICES` (`max_length=20`):
    - `("low", "Low")`
    - `("standard", "Standard")`
    - `("high", "High")`
    - `("critical_urgent", "Critical / Urgent")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("draft", "Draft")`
    - `("submitted", "Submitted for Review")`
    - `("in_assessment", "Impact Assessment")`
    - `("ccb_review", "CCB Review")`
    - `("approved", "Approved")`
    - `("rejected", "Rejected")`
    - `("implemented", "Implemented & Closed")`
    - `("cancelled", "Cancelled")`
  - `CCB_DECISION_CHOICES` (`max_length=20`):
    - `("pending", "Pending CCB Review")`
    - `("approved", "CCB Approved")`
    - `("rejected", "CCB Rejected")`
    - `("waived", "CCB Review Waived")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`, `"submitted": "badge-info"`, `"in_assessment": "badge-amber"`, `"ccb_review": "badge-info"`, `"approved": "badge-green"`, `"rejected": "badge-red"`, `"implemented": "badge-green"`, `"cancelled": "badge-muted"`
  - `PRIORITY_CSS`:
    - `"low": "badge-slate"`, `"standard": "badge-info"`, `"high": "badge-amber"`, `"critical_urgent": "badge-red"`
  - `CCB_DECISION_CSS`:
    - `"pending": "badge-amber"`, `"approved": "badge-green"`, `"rejected": "badge-red"`, `"waived": "badge-slate"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `change_type`: `CharField(max_length=28, choices=CHANGE_TYPE_CHOICES, default="major_revision")`
  - `priority`: `CharField(max_length=20, choices=PRIORITY_CHOICES, default="standard")`
  - `document`: `ForeignKey("quality.ControlledDocument", on_delete=CASCADE, related_name="change_orders")`
  - `target_revision`: `CharField(max_length=20, default="1.1")`
  - `reason_for_change`: `TextField(help_text="Regulatory / operational justification for this change.")`
  - `change_description`: `TextField(help_text="Detailed summary of additions, modifications, or deletions.")`
  - `regulatory_impact`: `BooleanField(default=False, help_text="Does this change require regulatory notification or filings (e.g. FDA 510(k), CE mark)?")`
  - `training_required`: `BooleanField(default=True, help_text="Does this change trigger mandatory read-and-acknowledge retraining?")`
  - `impact_assessment`: `TextField(blank=True, help_text="Scope analysis of affected processes, equipment, and validation.")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `requested_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="requested_change_orders")`
  - `target_effective_date`: `DateField(null=True, blank=True)`
  - `ccb_decision`: `CharField(max_length=20, choices=CCB_DECISION_CHOICES, default="pending")`
  - `ccb_decision_date`: `DateField(null=True, blank=True)`
  - `ccb_decision_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="ccb_decisions")`
  - `closure_notes`: `TextField(blank=True)`
  - `closed_at`: `DateTimeField(null=True, blank=True, editable=False)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qdcr_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qdcr_ten_status")` (19)
  - `Index(fields=["tenant", "document", "status"], name="idx_qdcr_ten_doc_stat")` (21)
  - `Index(fields=["tenant", "requested_by"], name="idx_qdcr_ten_reqby")` (18)

---

### 1.3 `ElectronicSignatureRecord` (`ElectronicSignatures.py`)
- **`NUMBER_PREFIX`**: `"QSIG"`
- **`Meta.ordering`**: `["-signature_timestamp"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Electronic Signature Record"` / `"Electronic Signature Records"`
- **Choices & Badge Maps**:
  - `MEANING_CHOICES` (`max_length=32`):
    - `("authored", "Author / Originator Sign-Off")`
    - `("reviewed", "Technical Verification / Peer Review")`
    - `("quality_approval", "Quality Assurance Approval")`
    - `("management_approval", "Management / Executive Authorization")`
    - `("ccb_approval", "Change Control Board Approval")`
    - `("acknowledgment", "Read, Understood & Compliance Agreement")`
  - `MEANING_CSS`:
    - `"authored": "badge-slate"`
    - `"reviewed": "badge-info"`
    - `"quality_approval": "badge-green"`
    - `"management_approval": "badge-amber"`
    - `"ccb_approval": "badge-info"`
    - `"acknowledgment": "badge-green"`
- **Fields**:
  - `document`: `ForeignKey("quality.ControlledDocument", on_delete=CASCADE, related_name="signature_manifests")`
  - `change_order`: `ForeignKey("quality.DocumentChangeOrder", on_delete=SET_NULL, null=True, blank=True, related_name="signatures")`
  - `signer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="quality_signatures")`
  - `signer_name`: `CharField(max_length=150, help_text="Printed legal name of the signer per 21 CFR § 11.50(a)(1).")`
  - `signer_title`: `CharField(max_length=100, blank=True)`
  - `signature_meaning`: `CharField(max_length=32, choices=MEANING_CHOICES)`
  - `signature_timestamp`: `DateTimeField(auto_now_add=True, editable=False)`
  - `document_revision`: `CharField(max_length=20)`
  - `signature_hash`: `CharField(max_length=64, editable=False, help_text="SHA-256 HMAC digest binding signer, document, revision, timestamp, and meaning.")`
  - `comments`: `TextField(blank=True)`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qsig_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "document", "-signature_timestamp"], name="idx_qsig_ten_doc_time")` (21)
  - `Index(fields=["tenant", "signer", "-signature_timestamp"], name="idx_qsig_ten_sig_time")` (21)
  - `Index(fields=["tenant", "signature_hash"], name="idx_qsig_ten_hash")` (17)

---

### 1.4 `DocumentAcknowledgment` (`DocumentAcknowledgments.py`)
- **`NUMBER_PREFIX`**: `"QACK"`
- **`Meta.ordering`**: `["-due_date", "-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Acknowledgment"` / `"Document Acknowledgments"`
- **Choices & Badge Maps**:
  - `STATUS_CHOICES` (`max_length=20`):
    - `("pending", "Pending Sign-Off")`
    - `("acknowledged", "Acknowledged")`
    - `("overdue", "Overdue")`
    - `("waived", "Waived")`
  - `STATUS_CSS`:
    - `"pending": "badge-amber"`
    - `"acknowledged": "badge-green"`
    - `"overdue": "badge-red"`
    - `"waived": "badge-slate"`
- **Fields**:
  - `document`: `ForeignKey("quality.ControlledDocument", on_delete=CASCADE, related_name="acknowledgments")`
  - `document_revision`: `CharField(max_length=20)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="document_acknowledgments")`
  - `employee`: `ForeignKey("hrm.EmployeeProfile", on_delete=SET_NULL, null=True, blank=True, related_name="quality_acknowledgments")`
  - `due_date`: `DateField()`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)`
  - `acknowledged_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `signature_record`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=SET_NULL, null=True, blank=True, related_name="linked_acknowledgment")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qack_ten_num_uniq")` (25)
  - `UniqueConstraint(fields=["tenant", "document", "document_revision", "user"], name="idx_qack_ten_doc_rev_usr")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qack_ten_status")` (19)
  - `Index(fields=["tenant", "user", "status"], name="idx_qack_ten_user_stat")` (22)
  - `Index(fields=["tenant", "due_date"], name="idx_qack_ten_duedate")` (20)

---

## 2. Forms Contract (`apps/quality/forms/DocumentControl/`)

All forms inherit `apps.core.forms.TenantModelForm` + `TenantUniqueMixin`.

### 2.1 `ControlledDocumentForm`
- **Fields included in `Meta.fields`**:
  `["title", "document_type", "department", "owner", "revision", "classification", "file", "description", "change_summary", "effective_date", "review_interval_months", "retention_years", "is_template"]`
- **Excluded**:
  `["tenant", "number", "is_latest_revision", "lifecycle_state", "next_review_date", "supersedes", "superseded_by", "archived_at", "created_at", "updated_at"]`
- **Scoping & `clean()`**:
  - Populate `department`: `OrgUnit.objects.filter(tenant=self.tenant)`
  - Populate `owner`: `User.objects.filter(tenant=self.tenant)`
  - `reject_foreign(self, cleaned_data, ["department", "owner"])`
  - Validate `review_interval_months >= 1` and `retention_years >= 1`.

### 2.2 `ControlledDocumentRevisionForm`
- Specialized form to branch a new draft revision from an effective document.
- **Fields**:
  `["revision", "change_summary", "file", "description"]`
- **Excluded**:
  All others. Automatically wires `supersedes` to the source document on save.

### 2.3 `DocumentChangeOrderForm`
- **Fields included in `Meta.fields`**:
  `["title", "change_type", "priority", "document", "target_revision", "reason_for_change", "change_description", "regulatory_impact", "training_required", "impact_assessment", "requested_by", "target_effective_date"]`
- **Excluded**:
  `["tenant", "number", "status", "ccb_decision", "ccb_decision_date", "ccb_decision_by", "closure_notes", "closed_at", "created_at", "updated_at"]`
- **Scoping & `clean()`**:
  - Populate `document`: `ControlledDocument.objects.filter(tenant=self.tenant, is_latest_revision=True)`
  - Populate `requested_by`: `User.objects.filter(tenant=self.tenant)`
  - `reject_foreign(self, cleaned_data, ["document", "requested_by"])`

### 2.4 `ElectronicSignatureForm` (21 CFR Part 11 Non-Repudiation)
- Custom ModelForm for executing an electronic signature with mandatory password re-authentication.
- **Fields**:
  `["signature_meaning", "comments"]`
- **Extra field**:
  `password = forms.CharField(widget=forms.PasswordInput, required=True, label="Re-enter Password for Electronic Signature")`
- **Validation**:
  - In `clean()`: checks `request.user.check_password(cleaned_data.get("password"))`. If invalid, raises `ValidationError("Invalid credentials. Electronic signature aborted per 21 CFR § 11.200.")`.

### 2.5 `DocumentAcknowledgmentForm`
- **Fields included in `Meta.fields`**:
  `["document", "document_revision", "user", "employee", "due_date", "notes"]`
- **Excluded**:
  `["tenant", "number", "status", "acknowledged_at", "signature_record", "created_at", "updated_at"]`
- **Scoping & `clean()`**:
  - Populate `document`: `ControlledDocument.objects.filter(tenant=self.tenant)`
  - Populate `user`: `User.objects.filter(tenant=self.tenant)`
  - Populate `employee`: `EmployeeProfile.objects.filter(tenant=self.tenant)`
  - `reject_foreign(self, cleaned_data, ["document", "user", "employee"])`

---

## 3. URLs & Routes Contract (`apps/quality/urls/`)

`app_name = "quality"`. Literal routes listed strictly before `<int:pk>` patterns.

| Route Pattern | Name | View Function |
|---|---|---|
| `documents/` | `controlled_document_list` | `controlled_document_list` |
| `documents/create/` | `controlled_document_create` | `controlled_document_create` |
| `documents/export/` | `controlled_document_export` | `controlled_document_export` |
| `documents/vault/` | `document_archive_vault` | `document_archive_vault` |
| `documents/<int:pk>/` | `controlled_document_detail` | `controlled_document_detail` |
| `documents/<int:pk>/edit/` | `controlled_document_edit` | `controlled_document_edit` |
| `documents/<int:pk>/delete/` | `controlled_document_delete` | `controlled_document_delete` |
| `documents/<int:pk>/submit/` | `controlled_document_submit` | `controlled_document_submit` |
| `documents/<int:pk>/approve/` | `controlled_document_approve` | `controlled_document_approve` |
| `documents/<int:pk>/make-effective/` | `controlled_document_make_effective` | `controlled_document_make_effective` |
| `documents/<int:pk>/obsolete/` | `controlled_document_obsolete` | `controlled_document_obsolete` |
| `documents/<int:pk>/revise/` | `controlled_document_new_revision` | `controlled_document_new_revision` |
| `documents/<int:pk>/sign/` | `controlled_document_sign` | `controlled_document_sign` |
| `change-orders/` | `document_change_order_list` | `document_change_order_list` |
| `change-orders/create/` | `document_change_order_create` | `document_change_order_create` |
| `change-orders/export/` | `document_change_order_export` | `document_change_order_export` |
| `change-orders/<int:pk>/` | `document_change_order_detail` | `document_change_order_detail` |
| `change-orders/<int:pk>/edit/` | `document_change_order_edit` | `document_change_order_edit` |
| `change-orders/<int:pk>/delete/` | `document_change_order_delete` | `document_change_order_delete` |
| `change-orders/<int:pk>/submit/` | `document_change_order_submit` | `document_change_order_submit` |
| `change-orders/<int:pk>/ccb-decision/` | `document_change_order_ccb_decision` | `document_change_order_ccb_decision` |
| `signatures/` | `electronic_signature_list` | `electronic_signature_list` |
| `signatures/export/` | `electronic_signature_export` | `electronic_signature_export` |
| `signatures/<int:pk>/` | `electronic_signature_detail` | `electronic_signature_detail` |
| `signatures/<int:pk>/verify/` | `electronic_signature_verify` | `electronic_signature_verify` |
| `acknowledgments/` | `document_acknowledgment_list` | `document_acknowledgment_list` |
| `acknowledgments/create/` | `document_acknowledgment_create` | `document_acknowledgment_create` |
| `acknowledgments/export/` | `document_acknowledgment_export` | `document_acknowledgment_export` |
| `acknowledgments/<int:pk>/` | `document_acknowledgment_detail` | `document_acknowledgment_detail` |
| `acknowledgments/<int:pk>/edit/` | `document_acknowledgment_edit` | `document_acknowledgment_edit` |
| `acknowledgments/<int:pk>/delete/` | `document_acknowledgment_delete` | `document_acknowledgment_delete` |
| `acknowledgments/<int:pk>/sign/` | `document_acknowledgment_sign` | `document_acknowledgment_sign` |

---

## 4. View Context Keys Contract

### 4.1 `controlled_document_list`
- `documents`: Paginated queryset of `ControlledDocument`
- `page_obj`: Django Paginator `page_obj`
- `paginator`: Paginator instance
- `is_paginated`: Boolean
- `total_count`: Integer
- `q`: Search query string
- `status_choices`: `ControlledDocument.LIFECYCLE_STATE_CHOICES`
- `type_choices`: `ControlledDocument.DOCUMENT_TYPE_CHOICES`
- `department_choices`: `OrgUnit.objects.filter(tenant=request.tenant)`
- `stats`: dict with keys `total`, `effective`, `in_review`, `draft`, `overdue_reviews`

### 4.2 `controlled_document_detail`
- `document`: The `ControlledDocument` instance
- `change_orders`: Related `DocumentChangeOrder` records
- `signatures`: Related `ElectronicSignatureRecord` records
- `acknowledgments`: Related `DocumentAcknowledgment` records
- `revision_history`: Sibling and predecessor versions of this document family
- `can_sign`: Boolean
- `can_edit`: Boolean (`not document.is_locked`)
- `can_submit`: Boolean (`document.lifecycle_state == 'draft'`)
- `can_approve`: Boolean (`document.lifecycle_state in {'in_review', 'pending_approval'}`)
- `can_make_effective`: Boolean (`document.lifecycle_state == 'approved'`)
- `can_obsolete`: Boolean (`document.lifecycle_state == 'effective'`)
- `can_revise`: Boolean (`document.lifecycle_state == 'effective'`)

### 4.3 `document_change_order_list`
- `change_orders`: Paginated queryset
- `page_obj`: Paginator `page_obj`
- `paginator`: Paginator instance
- `is_paginated`: Boolean
- `total_count`: Integer
- `q`: Search query string
- `status_choices`: `DocumentChangeOrder.STATUS_CHOICES`
- `priority_choices`: `DocumentChangeOrder.PRIORITY_CHOICES`
- `change_type_choices`: `DocumentChangeOrder.CHANGE_TYPE_CHOICES`
- `stats`: dict with keys `total`, `active`, `ccb_pending`, `approved`, `implemented`

### 4.4 `document_change_order_detail`
- `change_order`: The `DocumentChangeOrder` instance
- `document`: The linked `ControlledDocument`
- `signatures`: Linked signature records
- `can_edit`: Boolean (`change_order.status in {'draft', 'submitted'}`)
- `can_submit`: Boolean (`change_order.status == 'draft'`)
- `can_ccb_approve`: Boolean (`change_order.status == 'ccb_review'`)

### 4.5 `electronic_signature_list`
- `signatures`: Paginated queryset
- `page_obj`: Paginator `page_obj`
- `paginator`: Paginator instance
- `is_paginated`: Boolean
- `total_count`: Integer
- `q`: Search query string
- `meaning_choices`: `ElectronicSignatureRecord.MEANING_CHOICES`
- `stats`: dict with keys `total`, `approvals`, `reviews`, `acknowledgments`

### 4.6 `electronic_signature_detail`
- `signature`: The `ElectronicSignatureRecord` instance
- `document`: The linked `ControlledDocument`
- `change_order`: The linked `DocumentChangeOrder` (or None)
- `is_valid_hash`: Boolean (cryptographic verification)

### 4.7 `document_acknowledgment_list`
- `acknowledgments`: Paginated queryset
- `page_obj`: Paginator `page_obj`
- `paginator`: Paginator instance
- `is_paginated`: Boolean
- `total_count`: Integer
- `q`: Search query string
- `status_choices`: `DocumentAcknowledgment.STATUS_CHOICES`
- `stats`: dict with keys `total`, `pending`, `acknowledged`, `overdue`

### 4.8 `document_acknowledgment_detail`
- `acknowledgment`: The `DocumentAcknowledgment` instance
- `document`: Linked `ControlledDocument`
- `signature`: Linked `ElectronicSignatureRecord` (if signed)

### 4.9 `document_archive_vault`
- `vault_documents`: Paginated queryset of `lifecycle_state in {'superseded', 'obsolete', 'archived'}`
- `page_obj`: Paginator `page_obj`
- `paginator`: Paginator instance
- `is_paginated`: Boolean
- `total_count`: Integer
- `q`: Search query string
- `stats`: dict with keys `total_vault`, `superseded`, `obsolete`, `archived`

---

## 5. Navigation & Sidebar Contract (`apps/core/navigation.py`)

`LIVE_LINKS["12.1"]` maps the 5 NavERP.md feature bullets to live routes:

```python
    "12.1": {
        "Document Creation & Authoring": "quality:controlled_document_list",
        "Review & Approval Workflows": "quality:electronic_signature_list",
        "Document Distribution & Obsolescence": "quality:document_acknowledgment_list",
        "Change Request & Revision Control": "quality:document_change_order_list",
        "Archive & Retrieval": "quality:document_archive_vault",
    },
```
