# Review Findings: Sub-module 13.2 Version Control & Revision Management

Base changeset: `046eecb0bbea97d5200c85f8c7a5b81eae74aa9b...548321965d2527d8ba1d20dda67bc20527b8ad8b`

---

## Critical Findings

- [x] **C1**: `apps/documents/views/VersionControl/DocumentLocks.py:282` & `templates/documents/version_control/document/detail.html:45`, `document_lock/detail.html:42` — Missing Tenant Administrator Gate on `document_force_unlock` (Privilege Escalation).
  - *Fix*: Decorate `document_force_unlock` with `@tenant_admin_required`, require admin privileges in view logic, and wrap the UI force-unlock button in `{% if request.user.is_superuser or request.user.role == 'admin' %}`. — fixed: `security(documents): require tenant admin for document force unlock`
- [x] **C2**: `apps/documents/views/VersionControl/DocumentVersions.py:20` — Large `extracted_text` TextField loaded on version list view without `.defer()`.
  - *Fix*: Add `.defer("extracted_text")` to `DocumentVersion.objects.select_related(...)` in `document_version_list`. — fixed: `perf(documents): defer extracted_text in document_version_list`

---

## Important Findings

- [x] **I1**: `apps/documents/views/VersionControl/DocumentLocks.py:93-137` — Concurrency race condition and lack of row-level locking (`select_for_update`) in `document_checkout`, plus non-idempotent GET baseline version creation.
  - *Fix*: Move baseline version creation into the POST handling block, wrap in `transaction.atomic()`, acquire `select_for_update()` on Document, and re-verify `doc.is_locked`. — fixed: `fix(documents): add row-level locking with select_for_update and null check in document_checkout`
- [x] **I2**: `apps/documents/views/VersionControl/DocumentVersions.py:270-285` — Missing transaction, active lock guard, and owner/admin authorization in `document_version_rollback`.
  - *Fix*: Wrap in `with transaction.atomic():`, check `if document.is_locked: messages.error(...); return redirect(...)`, and require `document.owner == request.user or request.user.is_superuser or is_tenant_admin(request.user)`. — fixed: `fix(documents): add transaction, lock guard, and owner authorization to document_version_rollback`
- [x] **I3**: `apps/documents/views/VersionControl/DocumentBranches.py:158-255` — Missing active status check, lock guard, and creator/admin authorization in `document_branch_abandon` and `document_branch_merge`.
  - *Fix*: Check status is active, check `not document.is_locked`, and verify `branch.created_by == request.user or document.owner == request.user or request.user.is_superuser or is_tenant_admin(request.user)`. — fixed: `fix(documents): add active status check, lock guard, and owner authorization to branch merge and abandon`
- [x] **I4**: `apps/documents/views/VersionControl/DocumentVersions.py:218-219` & `templates/documents/version_control/document_version/compare.html:207` — Stored XSS vulnerability in `difflib.HtmlDiff` table headers (`fromdesc`, `todesc`) rendered via `|safe`.
  - *Fix*: Escape `version_label` with `django.utils.html.escape` before building `fromdesc`/`todesc`. — fixed: `security(documents): escape version labels in difflib html table headers to prevent stored XSS`
- [x] **I5**: `apps/documents/forms/VersionControl/DocumentBranches.py:47` & `apps/documents/forms/VersionControl/DocumentVersions.py:63` — Foreign key cross-document selection: `DocumentBranchForm` allows selecting `base_version` from another document, and `DocumentVersionForm` allows selecting `branch` from another document.
  - *Fix*: Validate in `clean()` that `base_version.document == document` and `branch.document == document`. — fixed: `fix(documents): validate base_version belongs to document in DocumentBranchForm` & `fix(documents): validate branch belongs to document in DocumentVersionForm`
- [x] **I6**: `apps/documents/forms/VersionControl/DocumentVersions.py:45`, `DocumentLocks.py:40, 102`, `DocumentBranches.py:74` — Missing file upload extension and size validation.
  - *Fix*: Validate file extension against `ALLOWED_DOC_EXTENSIONS` and size against `MAX_UPLOAD_BYTES` from `apps.core.forms._common`. — fixed: `fix(documents): add validate_safe_doc_upload helper using ALLOWED_DOC_EXTENSIONS and MAX_UPLOAD_BYTES` & forms validation
- [x] **I7**: `apps/documents/views/VersionControl/Documents.py:86` & `templates/documents/version_control/document/detail.html:214` — N+1 queries on `restored_from_version` in document detail revision history.
  - *Fix*: Add `"restored_from_version"` to `select_related` and defer `extracted_text` on the versions queryset in `document_detail`. — fixed: `perf(documents): select_related restored_from_version and defer extracted_text in document_detail`
- [x] **I8**: `apps/documents/views/VersionControl/Documents.py:82` & `apps/documents/views/VersionControl/DocumentBranches.py:73` — Redundant and discarded `prefetch_related` queries in detail views.
  - *Fix*: Remove discarded `prefetch_related=("versions", "locks", "branches")` from `document_detail` and `prefetch_related=("versions",)` from `document_branch_detail`. — fixed: `perf(documents): remove unused prefetch_related from document_detail` & `perf(documents): remove unused prefetch_related from document_branch_detail`
- [x] **I9**: `apps/documents/views/VersionControl/DocumentLocks.py:28` & `apps/documents/views/VersionControl/DocumentBranches.py:25` — `select_related("base_version")` pulls unneeded large `extracted_text` on lock and branch lists.
  - *Fix*: Add `.defer("base_version__extracted_text")` to both list querysets. — fixed: `perf(documents): defer base_version__extracted_text in document_lock_list` & `perf(documents): defer base_version__extracted_text in document_branch_list`
- [x] **I10**: `apps/documents/views/VersionControl/DocumentVersions.py:193-209` — Multiple redundant queries and full text loading in `document_version_compare`.
  - *Fix*: Defer `extracted_text` on dropdown versions queryset and evaluate `versions_list = list(versions)` once to resolve default selections in memory without repeated DB queries. — fixed: `perf(documents): defer extracted_text and resolve compare defaults in memory`
- [ ] **I11**: `apps/documents/models/VersionControl/DocumentVersions.py:80` — Missing database index on `DocumentVersion.status`.
  - *Fix*: Add `db_index=True` to `status` and `models.Index(fields=["tenant", "status"], name="idx_dver_ten_stat")` to Meta.indexes.
- [ ] **I12**: `templates/documents/version_control/document_version/list.html:142`, `detail.html:29`, `document_branch/list.html:123`, `detail.html:26` — Missing CRUD Delete Actions in version and branch lists and detail pages.
  - *Fix*: Add POST-only delete forms with CSRF and confirm prompt targeting `documents:document_version_delete` and `documents:document_branch_delete`.
- [ ] **I13**: `templates/documents/version_control/document_version/detail.html:29` & `document_branch/detail.html:26` — Missing "Back to List" navigation action in detail headers.
  - *Fix*: Add Back button navigating to `documents:document_version_list` and `documents:document_branch_list`.
- [x] **I14**: `apps/documents/views/VersionControl/DocumentLocks.py:94` — `document.locked_by.username` raises `AttributeError` if `document.locked_by` is null.
  - *Fix*: Use `getattr(document.locked_by, 'username', 'another user')`. — fixed: `fix(documents): add row-level locking with select_for_update and null check in document_checkout`

---

## Minor Findings

- [ ] **M1**: `apps/documents/views/VersionControl/DocumentBranches.py:199` — `change_summary=f"[Merged from {branch.name}] {summary}"` can exceed `max_length=500` if summary is long.
  - *Fix*: Clamp combined string to `[:500]`.
- [ ] **M2**: `templates/documents/version_control/document_version/compare.html:217` — Empty state missing when a document has zero versions recorded.
  - *Fix*: Add empty state card in template explaining that the selected document has no versions recorded yet.
- [ ] **M3**: `apps/documents/management/commands/seed_documents.py:23` — Lacks `--flush` option and tenant user credential notice.
  - *Fix*: Add `--flush` handling and stdout notice for tenant user credentials.
- [ ] **M4**: `apps/documents/views/VersionControl/Documents.py:68` — Pass `"department_choices": departments` in `document_list` context for full contract symmetry.
  - *Fix*: Add `"department_choices": departments` to context dict.
- [ ] **M5**: `templates/documents/version_control/document/list.html:74` & `document_version/list.html:31` — Filter dropdowns and pagination persistence for `is_locked` and `is_official`.
  - *Fix*: Add filter dropdowns and preserve in pagination query strings.
- [ ] **M6**: `templates/documents/version_control/document/detail.html:21` — `Locked by {{ document.locked_by.username }}` inside header badge when `locked_by` is null.
  - *Fix*: Guard with `{% if document.locked_by %}{{ document.locked_by.get_full_name|default:document.locked_by.username }}{% else %}Unknown{% endif %}`.
- [ ] **M7**: Icon-only action buttons across list tables lack `aria-label` attribute matching `title`.
  - *Fix*: Add `aria-label` matching `title` on all icon-only action buttons.
- [ ] **M8**: `templates/documents/version_control/document/detail.html:168, 268` & `document_branch/detail.html:151` — Template `.count` triggers redundant SQL `COUNT(*)` right before iteration.
  - *Fix*: Use `{{ versions|length }}` and `{{ branches|length }}`.
- [ ] **M9**: `apps/documents/views/VersionControl/Documents.py:59` — Uncombined stat card count queries in `document_list`.
  - *Fix*: Combine via `.aggregate()`.
- [ ] **M10**: `apps/documents/views/VersionControl/DocumentVersions.py:57` & `DocumentLocks.py:60` — Filter dropdown queries fetch unneeded large text columns on `Document`.
  - *Fix*: Restrict with `.only("id", "title", "number")`.
- [ ] **M11**: `apps/documents/views/VersionControl/DocumentBranches.py:253` — AuditLog action verb `"abandon"` documentation standardization.
  - *Fix*: Document `"abandon"` in contract documentation.
