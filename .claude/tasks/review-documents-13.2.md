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
