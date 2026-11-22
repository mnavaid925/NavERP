# Review Findings: Sub-module 13.2 Version Control & Revision Management

Base changeset: `046eecb0bbea97d5200c85f8c7a5b81eae74aa9b...548321965d2527d8ba1d20dda67bc20527b8ad8b`

---

## 1. Code Reviewer Findings

### Critical
- **CR-C1**: `apps/documents/views/VersionControl/DocumentLocks.py:282` — `document_force_unlock` only enforces `@login_required`, allowing any authenticated user to forcibly break active editing reservations held by colleagues without administrative privileges.
  - *Fix*: Add `@tenant_admin_required` (or `request.user.is_superuser or is_tenant_admin(request.user)`) check before allowing force-unlock.

### Important
- **CR-I1**: `apps/documents/views/VersionControl/DocumentLocks.py:100` — `document_checkout` creates a new `DocumentVersion` baseline in the database on HTTP GET requests when no version exists yet, violating HTTP GET idempotency.
  - *Fix*: Move the baseline version instantiation into the POST form processing block inside the atomic transaction, or only initialize on explicit document creation.
- **CR-I2**: `apps/documents/views/VersionControl/DocumentVersions.py:280` — `document_version_rollback` performs multi-model database writes (`DocumentVersion.objects.create` followed by `document.save`) without `transaction.atomic()`, risking orphaned restoration records on failure.
  - *Fix*: Wrap version creation and document version pointer update in `with transaction.atomic():`.
- **CR-I3**: `apps/documents/views/VersionControl/DocumentLocks.py:122` — `document_checkout` checks `document.is_locked` before entering the transaction and lacks row-level locking (`select_for_update()`), allowing concurrent checkout requests to create multiple active locks.
  - *Fix*: Lock the document row with `Document.objects.select_for_update().get(pk=doc_pk, tenant=request.tenant)` inside `transaction.atomic()` and re-verify `is_locked`.
- **CR-I4**: `apps/documents/views/VersionControl/DocumentVersions.py:272` — `document_version_rollback` lacks an active lock guard, allowing historical versions to overwrite document mainline state while an author holds an active check-out lock.
  - *Fix*: Add `if document.is_locked: messages.error(...); return redirect(...)` check before allowing rollback.
- **CR-I5**: `apps/documents/views/VersionControl/DocumentBranches.py:250` — `document_branch_abandon` lacks a status check and creator/admin permission guard, allowing any user to abandon already merged or non-active branches.
  - *Fix*: Enforce `if branch.status != 'active':` guard and require `branch.created_by == request.user or request.user.is_superuser or is_tenant_admin(request.user)`.
- **CR-I6**: `apps/documents/forms/VersionControl/DocumentBranches.py:47` — `DocumentBranchForm` populates `base_version` with all versions in the tenant across all documents, and `clean()` fails to validate that `base_version.document == document`.
  - *Fix*: Restrict `base_version` queryset or add validation in `clean()` asserting `if base_version and base_version.document_id != document.id: self.add_error('base_version', 'Base version must belong to target document')`.
- **CR-I7**: `apps/documents/forms/VersionControl/DocumentVersions.py:63` — `DocumentVersionForm` allows selecting any branch in the tenant without verifying that `branch.document == document`.
  - *Fix*: Add validation in `clean()` asserting `if branch and branch.document_id != document.id: self.add_error('branch', 'Branch must belong to the selected document')`.
- **CR-I8**: `apps/documents/views/VersionControl/DocumentLocks.py:94` — `document.locked_by.username` raises an unhandled `AttributeError` if `document.locked_by` is null (since `locked_by` is nullable on `Document`).
  - *Fix*: Use `getattr(document.locked_by, 'username', 'another user')`.

### Minor
- **CR-M1**: `apps/documents/views/VersionControl/DocumentBranches.py:199` — `change_summary=f"[Merged from {branch.name}] {summary}"` can exceed `DocumentVersion.change_summary` `max_length=500` if user summary is long, raising a `DataError`.
  - *Fix*: Clamp the combined string to `[:500]`.
- **CR-M2**: `templates/documents/version_control/document/detail.html:31` — Detail templates omit Back-to-List navigation buttons and standard POST-only delete actions with confirm dialogs even though delete views and routes exist.
  - *Fix*: Add standard Back button and status/role-conditional POST delete forms to detail headers.
- **CR-M3**: `templates/documents/version_control/document_version/compare.html:217` — When a document with zero versions is selected for comparison, the template leaves an empty space below the selector without an empty-state message.
  - *Fix*: Add `{% else %}` block explaining that the selected document has no versions recorded yet.
- **CR-M4**: `apps/documents/management/commands/seed_documents.py:23` — `seed_documents.py` lacks a `--flush` option.
  - *Fix*: Add `--flush` handling and stdout notice for tenant user credentials.


---

## 2. Explorer Reviewer Findings

### Critical
*None.*

### Important
*None.*

### Minor
- **EX-M1**: `apps/documents/views/VersionControl/Documents.py:68` — View context key alias `department_choices` omitted in `document_list`.
  - *Fix*: Pass `"department_choices": departments` in context alongside `"departments"`.
- **EX-M2**: `templates/documents/version_control/document/list.html:74` — Filter dropdown for `is_locked` and pagination persistence `&is_locked={{ request.GET.is_locked }}` missing from document list.
  - *Fix*: Add "Availability / Lock" filter dropdown and preserve `is_locked` in pagination links.
- **EX-M3**: `templates/documents/version_control/document_version/list.html:31` — Filter dropdown for `is_official` and pagination persistence `&is_official={{ request.GET.is_official }}` missing from version list.
  - *Fix*: Add "Official Release" filter dropdown and preserve `is_official` in pagination links.
- **EX-M4**: `apps/documents/views/VersionControl/DocumentBranches.py:253` — AuditLog action verb `"abandon"` in `document_branch_abandon` was not in the initial contract list (though valid under schema `<= 10` chars).
  - *Fix*: Keep or standardize to `"abandon"` in contract documentation.


---

## 3. Frontend Reviewer Findings

### Critical
*None.*

### Important
- **FE-I1**: `templates/documents/version_control/document_version/list.html:142` and `detail.html:29` — Missing CRUD Delete Action in version list actions column and detail header.
  - *Fix*: Add POST-only delete form with CSRF and confirm prompt targeting `documents:document_version_delete`.
- **FE-I2**: `templates/documents/version_control/document_branch/list.html:123` and `detail.html:26` — Missing CRUD Delete Action in branch list actions column and detail header.
  - *Fix*: Add POST-only delete form with CSRF and confirm prompt targeting `documents:document_branch_delete`.
- **FE-I3**: `templates/documents/version_control/document_version/detail.html:29` and `document_branch/detail.html:26` — Missing "Back to List" navigation action in detail headers.
  - *Fix*: Add `<a href="{% url 'documents:document_version_list' %}" class="btn btn-outline"><i data-lucide="arrow-left"></i> Version Register</a>` and `<a href="{% url 'documents:document_branch_list' %}" class="btn btn-outline"><i data-lucide="arrow-left"></i> Branch Register</a>`.

### Minor
- **FE-M1**: `templates/documents/version_control/document/detail.html:21` — `Locked by {{ document.locked_by.username }}` inside header badge if `locked_by` is null.
  - *Fix*: Use `{% if document.locked_by %}{{ document.locked_by.get_full_name|default:document.locked_by.username }}{% else %}Unknown{% endif %}`.
- **FE-M2**: Icon-only action buttons across list tables lack `aria-label` attribute matching `title`.
  - *Fix*: Add `aria-label` matching `title` on all icon-only action buttons.


---

## 4. Performance Reviewer Findings

### Critical
- **PR-C1**: `apps/documents/views/VersionControl/DocumentVersions.py:20` — Large `extracted_text` TextField loaded on version list view without `.defer()`.
  - *Fix*: Add `.defer("extracted_text")` to `DocumentVersion.objects.select_related(...)` in `document_version_list`.

### Important
- **PR-I1**: `apps/documents/views/VersionControl/Documents.py:86` & `templates/documents/version_control/document/detail.html:214` — N+1 queries on `restored_from_version` in document detail revision history.
  - *Fix*: Add `"restored_from_version"` to `select_related` on the `versions` queryset in `document_detail`.
- **PR-I2**: `apps/documents/views/VersionControl/Documents.py:82` & `apps/documents/views/VersionControl/DocumentBranches.py:73` — Redundant and discarded `prefetch_related` queries in detail views.
  - *Fix*: Remove `prefetch_related` calls that are immediately superseded by custom filtered/ordered queries.
- **PR-I3**: `apps/documents/views/VersionControl/DocumentLocks.py:28` & `apps/documents/views/VersionControl/DocumentBranches.py:25` — `select_related("base_version")` pulls unneeded `extracted_text` on lock and branch lists.
  - *Fix*: Add `.defer("base_version__extracted_text")` in both list views.
- **PR-I4**: `apps/documents/views/VersionControl/DocumentVersions.py:193` — Multiple redundant queries and full text loading in `document_version_compare`.
  - *Fix*: Defer `extracted_text` on dropdown versions queryset and evaluate list in memory once for default selection.
- **PR-I5**: `apps/documents/models/VersionControl/DocumentVersions.py:80` — Missing database index on `DocumentVersion.status` for tenant-scoped filtering.
  - *Fix*: Add `db_index=True` to `status` and add `models.Index(fields=["tenant", "status"], name="idx_dver_ten_stat")` to `DocumentVersion.Meta.indexes`.

### Minor
- **PR-M1**: `templates/documents/version_control/document/detail.html:168` — Template `.count` executes redundant `COUNT(*)` queries right before iteration.
  - *Fix*: Use `{{ versions|length }}` and `{{ branches|length }}`.
- **PR-M2**: `apps/documents/views/VersionControl/Documents.py:59` — Uncombined stat card count queries in `document_list`.
  - *Fix*: Combine into single aggregated query via `.aggregate()`.
- **PR-M3**: `apps/documents/views/VersionControl/DocumentVersions.py:57` — Filter dropdown queries fetch unneeded columns on `Document`.
  - *Fix*: Restrict dropdown queries with `.only("id", "title", "number")`.
- **PR-M4**: `apps/documents/models/VersionControl/DocumentVersions.py:118` — Chained N+1 vulnerability through `DocumentVersion.__str__`.
  - *Fix*: Ensure `base_version__document` is included where string representation is rendered.
