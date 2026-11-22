# Module 13.2 Pre-Build Contract — Version Control & Revision Management (`apps/documents/`)

> Frozen in Phase 3.1 before any Phase 3.2 scaffolding or entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.2"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Scaffolds a brand-new app; creates initial migration `0001_initial.py`; wires `config/settings.py` and `config/urls.py` in Integrate step)
- **Package Directories**:
  - `apps/documents/models/VersionControl/`
  - `apps/documents/forms/VersionControl/`
  - `apps/documents/views/VersionControl/`
  - `apps/documents/urls/VersionControl/`
  - `templates/documents/version_control/{document,document_version,document_lock,document_branch}/{list,detail,form}.html` + `templates/documents/version_control/document_version/compare.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"checkout"`, `"checkin"`, `"discard"`, `"unlock"`, `"fork"`, `"merge"`, `"rollback"`, `"abandon"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `documents.Document`, `documents.DocumentVersion`, `documents.DocumentBranch`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/VersionControl/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `Document` (`Documents.py`)
- **`NUMBER_PREFIX`**: `"DOC"`
- **`Meta.ordering`**: `["-created_at", "title"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document"` / `"Documents"`
- **Choices & Badge Maps**:
  - `DOCUMENT_TYPE_CHOICES` (`max_length=40`):
    - `("general", "General Document")`
    - `("contract", "Legal Contract & Agreement")`
    - `("policy", "Corporate Policy & Governance")`
    - `("sop", "Standard Operating Procedure (SOP)")`
    - `("report", "Business & Operational Report")`
    - `("specification", "Technical Specification")`
    - `("proposal", "Commercial Proposal / Pitch")`
    - `("template", "Document Template")`
    - `("technical", "Technical & Engineering Doc")`
  - `CLASSIFICATION_CHOICES` (`max_length=20`):
    - `("public", "Public")`
    - `("internal", "Internal Use Only")`
    - `("confidential", "Confidential")`
    - `("restricted", "Strictly Restricted")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("draft", "Draft")`
    - `("in_review", "In Review")`
    - `("approved", "Approved")`
    - `("published", "Published / Official")`
    - `("archived", "Archived")`
    - `("superseded", "Superseded")`
    - `("deprecated", "Deprecated")`
  - `VERSIONING_SCHEME_CHOICES` (`max_length=20`):
    - `("major_minor", "Major.Minor (e.g. 1.0, 1.1, 2.0)")`
    - `("semantic", "Semantic (e.g. 1.0.0, 1.1.0)")`
    - `("sequential", "Sequential (e.g. v1, v2, v3)")`
    - `("alphanumeric", "Alphanumeric (e.g. Rev A, Rev B)")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_review": "badge-amber"`
    - `"approved": "badge-info"`
    - `"published": "badge-green"`
    - `"archived": "badge-muted"`
    - `"superseded": "badge-red"`
    - `"deprecated": "badge-red"`
  - `CLASSIFICATION_CSS`:
    - `"public": "badge-green"`
    - `"internal": "badge-info"`
    - `"confidential": "badge-amber"`
    - `"restricted": "badge-red"`
  - `LOCK_CSS`:
    - `True: "badge-red"`
    - `False: "badge-slate"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `slug`: `SlugField(max_length=255, blank=True)`
  - `description`: `TextField(blank=True)`
  - `document_type`: `CharField(max_length=40, choices=DOCUMENT_TYPE_CHOICES, default="general", db_index=True)`
  - `classification`: `CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default="internal", db_index=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `versioning_scheme`: `CharField(max_length=20, choices=VERSIONING_SCHEME_CHOICES, default="major_minor")`
  - `current_version_label`: `CharField(max_length=32, default="1.0")`
  - `current_version_no`: `PositiveIntegerField(default=1)`
  - `is_locked`: `BooleanField(default=False, db_index=True)`
  - `locked_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="locked_documents")`
  - `locked_at`: `DateTimeField(null=True, blank=True)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_documents")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")`
  - `max_versions_retained`: `PositiveIntegerField(default=0, help_text="0 for unlimited, or max versions kept")`
  - `tags`: `CharField(max_length=500, blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dms_ten_num_uniq")` (21)
  - `Index(fields=["tenant", "status"], name="idx_doc_ten_stat")` (16)
  - `Index(fields=["tenant", "document_type"], name="idx_doc_ten_type")` (16)
  - `Index(fields=["tenant", "is_locked"], name="idx_doc_ten_lock")` (16)

### 1.2 `DocumentVersion` (`DocumentVersions.py`)
- **`NUMBER_PREFIX`**: `"DVER"`
- **`Meta.ordering`**: `["-created_at", "-major_number", "-minor_number", "-patch_number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Version"` / `"Document Versions"`
- **Choices & Badge Maps**:
  - `VERSION_TYPE_CHOICES` (`max_length=20`):
    - `("major", "Major Release / Milestone")`
    - `("minor", "Minor Revision / Working Draft")`
    - `("patch", "Patch / Typo Fix")`
    - `("branch_merge", "Branch Merge")`
    - `("rollback", "Historical Rollback Restoration")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft Revision")`
    - `("pending_review", "Pending Review")`
    - `("approved", "Approved")`
    - `("superseded", "Superseded")`
    - `("archived", "Archived")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"pending_review": "badge-amber"`
    - `"approved": "badge-green"`
    - `"superseded": "badge-red"`
    - `"archived": "badge-muted"`
  - `VERSION_TYPE_CSS`:
    - `"major": "badge-green"`
    - `"minor": "badge-info"`
    - `"patch": "badge-slate"`
    - `"branch_merge": "badge-info"`
    - `"rollback": "badge-amber"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="versions")`
  - `version_label`: `CharField(max_length=32)`
  - `major_number`: `PositiveIntegerField(default=1)`
  - `minor_number`: `PositiveIntegerField(default=0)`
  - `patch_number`: `PositiveIntegerField(default=0)`
  - `version_type`: `CharField(max_length=20, choices=VERSION_TYPE_CHOICES, default="minor")`
  - `file`: `FileField(upload_to="documents/versions/%Y/%m/", null=True, blank=True)`
  - `file_name`: `CharField(max_length=255, blank=True)`
  - `file_size`: `BigIntegerField(default=0)`
  - `file_hash`: `CharField(max_length=64, blank=True, help_text="SHA-256 checksum")`
  - `mime_type`: `CharField(max_length=100, blank=True)`
  - `change_summary`: `CharField(max_length=500, blank=True)`
  - `extracted_text`: `TextField(blank=True, help_text="Text content layer for search and redline diffing")`
  - `is_official`: `BooleanField(default=False, db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="approved")`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="authored_document_versions")`
  - `branch`: `ForeignKey("documents.DocumentBranch", on_delete=models.SET_NULL, null=True, blank=True, related_name="versions")`
  - `restored_from_version`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="restorations")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dver_ten_num_uniq")` (22)
  - `UniqueConstraint(fields=["tenant", "document", "version_label"], name="doc_dver_doc_vlabel_uniq")` (25)
  - `Index(fields=["tenant", "document", "is_official"], name="idx_dver_ten_doc_off")` (20)

### 1.3 `DocumentLock` (`DocumentLocks.py`)
- **`NUMBER_PREFIX`**: `"DLOCK"`
- **`Meta.ordering`**: `["-checked_out_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Lock"` / `"Document Locks"`
- **Choices & Badge Maps**:
  - `LOCK_TYPE_CHOICES` (`max_length=20`):
    - `("exclusive", "Exclusive Editing Lock")`
    - `("reservation", "Intent / Reservation Hold")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("active", "Active Lock")`
    - `("checked_in", "Checked In (Resolved)")`
    - `("discarded", "Discarded / Cancelled")`
    - `("force_unlocked", "Forcibly Broken by Admin")`
  - `STATUS_CSS`:
    - `"active": "badge-red"`
    - `"checked_in": "badge-green"`
    - `"discarded": "badge-slate"`
    - `"force_unlocked": "badge-amber"`
  - `LOCK_TYPE_CSS`:
    - `"exclusive": "badge-red"`
    - `"reservation": "badge-amber"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="locks")`
  - `base_version`: `ForeignKey("documents.DocumentVersion", on_delete=models.PROTECT, related_name="checked_out_locks")`
  - `locked_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="document_locks")`
  - `checked_out_at`: `DateTimeField(auto_now_add=True)`
  - `expires_at`: `DateTimeField(null=True, blank=True)`
  - `lock_type`: `CharField(max_length=20, choices=LOCK_TYPE_CHOICES, default="exclusive")`
  - `checkout_note`: `CharField(max_length=500, blank=True)`
  - `working_copy_file`: `FileField(upload_to="documents/working_copies/%Y/%m/", null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)`
  - `unlocked_at`: `DateTimeField(null=True, blank=True)`
  - `unlocked_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="unlocked_document_locks")`
  - `override_reason`: `TextField(blank=True, help_text="Mandatory justification for administrative override")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dlock_ten_num_uniq")` (23)
  - `Index(fields=["tenant", "document", "status"], name="idx_dlock_ten_doc_stat")` (22)

### 1.4 `DocumentBranch` (`DocumentBranches.py`)
- **`NUMBER_PREFIX`**: `"DBRN"`
- **`Meta.ordering`**: `["-created_at", "name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Branch"` / `"Document Branches"`
- **Choices & Badge Maps**:
  - `BRANCH_TYPE_CHOICES` (`max_length=20`):
    - `("what_if", "What-If Scenario Draft")`
    - `("variant", "Regional / Market Variant")`
    - `("draft_revision", "Alternative Revision Draft")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("active", "Active Branch")`
    - `("merged", "Merged into Mainline")`
    - `("abandoned", "Abandoned / Closed")`
  - `MERGE_STRATEGY_CHOICES` (`max_length=30`):
    - `("new_major_version", "Merge as New Major Version")`
    - `("new_minor_version", "Merge as New Minor Version")`
    - `("replace_content", "Direct Content Overwrite")`
  - `STATUS_CSS`:
    - `"active": "badge-amber"`
    - `"merged": "badge-green"`
    - `"abandoned": "badge-muted"`
  - `BRANCH_TYPE_CSS`:
    - `"what_if": "badge-info"`
    - `"variant": "badge-slate"`
    - `"draft_revision": "badge-amber"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="branches")`
  - `name`: `CharField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `base_version`: `ForeignKey("documents.DocumentVersion", on_delete=models.PROTECT, related_name="branched_children")`
  - `branch_type`: `CharField(max_length=20, choices=BRANCH_TYPE_CHOICES, default="what_if")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_document_branches")`
  - `merged_at`: `DateTimeField(null=True, blank=True)`
  - `merged_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="merged_document_branches")`
  - `merged_into_version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="originating_branch")`
  - `merge_strategy`: `CharField(max_length=30, choices=MERGE_STRATEGY_CHOICES, default="new_major_version")`
  - `merge_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dbrn_ten_num_uniq")` (22)
  - `Index(fields=["tenant", "document", "status"], name="idx_dbrn_ten_doc_stat")` (21)

---

## 2. Forms Contract (`apps/documents/forms/VersionControl/`)

All forms inherit `forms.ModelForm` (or `forms.Form`) and accept `tenant` in `__init__`, scoping all FK querysets via `Model.objects.filter(tenant=self.tenant)` and defending against IDOR with `reject_foreign(...)`.

### 2.1 `DocumentForm` (`Documents.py`)
- **`model`**: `Document`
- **`Meta.fields`**: `["title", "slug", "description", "document_type", "classification", "status", "versioning_scheme", "owner", "department", "max_versions_retained", "tags"]`
- **`Meta.exclude`**: `["tenant", "number", "current_version_label", "current_version_no", "is_locked", "locked_by", "locked_at", "created_at", "updated_at"]`

### 2.2 `DocumentVersionForm` (`DocumentVersions.py`)
- **`model`**: `DocumentVersion`
- **`Meta.fields`**: `["document", "version_label", "major_number", "minor_number", "patch_number", "version_type", "file", "file_name", "change_summary", "extracted_text", "is_official", "status", "author", "branch"]`
- **`Meta.exclude`**: `["tenant", "number", "file_size", "file_hash", "mime_type", "restored_from_version", "created_at", "updated_at"]`

### 2.3 `DocumentLockForm` (`DocumentLocks.py`)
- **`model`**: `DocumentLock`
- **`Meta.fields`**: `["document", "base_version", "locked_by", "expires_at", "lock_type", "checkout_note", "working_copy_file", "status"]`
- **`Meta.exclude`**: `["tenant", "number", "checked_out_at", "unlocked_at", "unlocked_by", "override_reason", "created_at", "updated_at"]`

### 2.4 `DocumentBranchForm` (`DocumentBranches.py`)
- **`model`**: `DocumentBranch`
- **`Meta.fields`**: `["document", "name", "description", "base_version", "branch_type", "created_by"]`
- **`Meta.exclude`**: `["tenant", "number", "status", "merged_at", "merged_by", "merged_into_version", "merge_strategy", "merge_notes", "created_at", "updated_at"]`

### 2.5 Action & Utility Forms
- **`CheckoutForm`**: `lock_type`, `checkout_note`, `expires_at`
- **`CheckinForm`**: `increment_intent` (`minor`, `major`, `patch`), `change_summary`, `file`, `extracted_text`, `is_official`
- **`ForceUnlockForm`**: `override_reason` (required)
- **`BranchMergeForm`**: `merge_strategy` (`new_major_version`, `new_minor_version`, `replace_content`), `change_summary`, `merge_notes`, `file`, `extracted_text`
- **`VersionCompareForm`**: `version_a_id`, `version_b_id`

---

## 3. URLs Contract (`apps/documents/urls/VersionControl/`)

All URL routes are grouped in `apps/documents/urls/VersionControl/<Entity>.py` and re-exported / concatenated in `apps/documents/urls/__init__.py` with `app_name = "documents"`. Literal routes strictly precede `<int:pk>` patterns.

### 3.1 Document URLs (`Documents.py`)
- `path("", views.document_list, name="document_list")`
- `path("create/", views.document_create, name="document_create")`
- `path("<int:pk>/", views.document_detail, name="document_detail")`
- `path("<int:pk>/edit/", views.document_edit, name="document_edit")`
- `path("<int:pk>/delete/", views.document_delete, name="document_delete")`

### 3.2 DocumentVersion URLs (`DocumentVersions.py`)
- `path("versions/", views.document_version_list, name="document_version_list")`
- `path("versions/create/", views.document_version_create, name="document_version_create")`
- `path("versions/compare/", views.document_version_compare, name="document_version_compare")`
- `path("versions/<int:pk>/", views.document_version_detail, name="document_version_detail")`
- `path("versions/<int:pk>/edit/", views.document_version_edit, name="document_version_edit")`
- `path("versions/<int:pk>/delete/", views.document_version_delete, name="document_version_delete")`
- `path("versions/<int:pk>/rollback/", views.document_version_rollback, name="document_version_rollback")`

### 3.3 DocumentLock URLs (`DocumentLocks.py`)
- `path("locks/", views.document_lock_list, name="document_lock_list")`
- `path("locks/<int:pk>/", views.document_lock_detail, name="document_lock_detail")`
- `path("documents/<int:doc_pk>/checkout/", views.document_checkout, name="document_checkout")`
- `path("documents/<int:doc_pk>/checkin/", views.document_checkin, name="document_checkin")`
- `path("documents/<int:doc_pk>/discard-checkout/", views.document_discard_checkout, name="document_discard_checkout")`
- `path("locks/<int:pk>/force-unlock/", views.document_force_unlock, name="document_force_unlock")`

### 3.4 DocumentBranch URLs (`DocumentBranches.py`)
- `path("branches/", views.document_branch_list, name="document_branch_list")`
- `path("branches/create/", views.document_branch_create, name="document_branch_create")`
- `path("branches/<int:pk>/", views.document_branch_detail, name="document_branch_detail")`
- `path("branches/<int:pk>/edit/", views.document_branch_edit, name="document_branch_edit")`
- `path("branches/<int:pk>/delete/", views.document_branch_delete, name="document_branch_delete")`
- `path("branches/<int:pk>/merge/", views.document_branch_merge, name="document_branch_merge")`
- `path("branches/<int:pk>/abandon/", views.document_branch_abandon, name="document_branch_abandon")`

---

## 4. View Context Keys Contract (`apps/documents/views/VersionControl/`)

### 4.1 `Document` Views
- **`document_list`**:
  - `page_obj`: paginated `Document` queryset
  - `documents`: `page_obj.object_list`
  - `document_type_choices`: `Document.DOCUMENT_TYPE_CHOICES`
  - `classification_choices`: `Document.CLASSIFICATION_CHOICES`
  - `status_choices`: `Document.STATUS_CHOICES`
  - `department_choices` / `departments`: `OrgUnit.objects.filter(tenant=request.tenant)`
  - `active_locks_count`: count of active locks
  - `total_documents_count`: total count
- **`document_detail`**:
  - `document` / `obj`: `Document` instance
  - `versions`: `document.versions.all()`
  - `active_lock`: `document.locks.filter(status="active").first()`
  - `branches`: `document.branches.all()`
  - `lock_history`: `document.locks.all()[:10]`
- **`document_create` / `document_edit`**:
  - `form`: `DocumentForm`
  - `document` / `obj`: `Document` instance (None on create)
  - `is_edit`: boolean

### 4.2 `DocumentVersion` Views
- **`document_version_list`**:
  - `page_obj`: paginated `DocumentVersion` queryset
  - `versions`: `page_obj.object_list`
  - `documents`: `Document.objects.filter(tenant=request.tenant)`
  - `version_type_choices`: `DocumentVersion.VERSION_TYPE_CHOICES`
  - `status_choices`: `DocumentVersion.STATUS_CHOICES`
- **`document_version_detail`**:
  - `version` / `obj`: `DocumentVersion` instance
  - `document`: `version.document`
  - `predecessor`: previous version
- **`document_version_compare`**:
  - `document`: `Document` instance
  - `version_a`: first `DocumentVersion`
  - `version_b`: second `DocumentVersion`
  - `versions`: all versions for selection dropdown
  - `diff_html`: generated side-by-side or inline HTML diff
  - `metadata_diff`: dict of metadata property differences
  - `diff_stats`: dict (`lines_added`, `lines_removed`, `metadata_changes_count`)

### 4.3 `DocumentLock` Views
- **`document_lock_list`**:
  - `page_obj`: paginated `DocumentLock` queryset
  - `locks`: `page_obj.object_list`
  - `status_choices`: `DocumentLock.STATUS_CHOICES`
  - `lock_type_choices`: `DocumentLock.LOCK_TYPE_CHOICES`
  - `documents`: `Document.objects.filter(tenant=request.tenant)`
- **`document_lock_detail`**:
  - `lock` / `obj`: `DocumentLock` instance
  - `document`: `lock.document`

### 4.4 `DocumentBranch` Views
- **`document_branch_list`**:
  - `page_obj`: paginated `DocumentBranch` queryset
  - `branches`: `page_obj.object_list`
  - `status_choices`: `DocumentBranch.STATUS_CHOICES`
  - `branch_type_choices`: `DocumentBranch.BRANCH_TYPE_CHOICES`
  - `documents`: `Document.objects.filter(tenant=request.tenant)`
- **`document_branch_detail`**:
  - `branch` / `obj`: `DocumentBranch` instance
  - `document`: `branch.document`
  - `branch_versions`: `branch.versions.all()`

---

## 5. Navigation & Sidebar Contract (`apps/core/navigation.py`)

The `LIVE_LINKS["13.2"]` dictionary maps the 5 NavERP.md feature bullets to live staff management routes:

```python
    "13.2": {
        "Automatic Version Numbering": "documents:document_version_list",
        "Check-in / Check-out Mechanism": "documents:document_lock_list",
        "Version Comparison & Diff View": "documents:document_version_compare",
        "Branching & Parallel Versions": "documents:document_branch_list",
        "Version History & Rollback": "documents:document_version_list",
    },
```
