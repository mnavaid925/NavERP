# Review Findings: Module 13.9 — Records Management & Compliance (`apps/documents/`)

**Target Changeset**: `36b7962ee269904d6d3affe02ef40ed5080fd945...HEAD`  
**Review Passes Completed (6/6)**:
1. `code-reviewer` — Architecture, error handling, transaction safety, and coding standards.
2. `explorer` — Structural file alignment, imports, naming, and theme consistency.
3. `frontend-reviewer` — UX design, responsive layouts, theme badge standards, and accessibility.
4. `performance-reviewer` — N+1 queries, query indexing, caching, and memory/pagination efficiency.
5. `qa-smoke-tester` — Route contract verification, edge cases, IDOR multi-tenancy isolation.
6. `security-reviewer` — Permissions, WORM compliance, dual-control integrity, and injection safety.

---

## Summary of Findings

| Category | Total | Open | Fixed | Skipped |
|---|---|---|---|---|
| **Critical** | 5 | 0 | 5 | 0 |
| **Important** | 9 | 3 | 6 | 0 |
| **Minor** | 4 | 4 | 0 | 0 |
| **Total** | 18 | 7 | 11 | 0 |

---

## Critical Findings (C1 – C5)

### [x] `C1`: Destruction Execution Without Prior Authorization & Non-Atomic Execution
- **Found by**: `code-reviewer`, `qa-smoke-tester`, `security-reviewer`
- **Location**:
  - `apps/documents/models/RecordsManagement/DestructionCertificates.py:132` (`execute_destruction`)
  - `apps/documents/views/RecordsManagement/DestructionCertificates.py:120` (`destruction_certificate_execute`)
- **Issue**: Neither the model method nor the view verifies `self.status == "authorized"` before executing destruction. A draft certificate in `pending_approval` or `rejected` can be executed directly, marking the record as `disposed`. Furthermore, already-executed certificates can be re-executed, and multiple model mutations occur without `transaction.atomic()`.
- **Fix**:
  1. In `DestructionCertificate.execute_destruction()`, verify:
     ```python
     if self.status != "authorized":
         raise ValueError("Cannot execute destruction: Certificate must be authorized first.")
     ```
  2. Prevent re-execution if `self.status == "executed"`.
  3. Wrap the view execution logic in `transaction.atomic()`.

### [x] `C2`: Missing `@tenant_admin_required` on Destructive & Compliance Mutating Views
- **Found by**: `code-reviewer`, `security-reviewer`
- **Location**:
  - `apps/documents/views/RecordsManagement/DestructionCertificates.py` (`destruction_certificate_authorize`, `destruction_certificate_execute`)
  - `apps/documents/views/RecordsManagement/DocumentLegalHolds.py` (`legal_hold_release`)
  - `apps/documents/views/RecordsManagement/RetentionSchedules.py` (`retention_schedule_delete`)
  - `apps/documents/views/RecordsManagement/RecordDeclarations.py` (`record_declaration_delete`)
- **Issue**: Standard authenticated users can unilaterally authorize or execute record destructions, lift litigation holds, or delete retention schedules and modifiable records.
- **Fix**: Apply `@tenant_admin_required` decorator to these 5 views.

### [x] `C3`: N+1 Query Cascade via `RecordDeclaration.is_under_legal_hold` in List Rendering
- **Found by**: `performance-reviewer`
- **Location**:
  - `apps/documents/models/RecordsManagement/RecordDeclarations.py:101` (`is_under_legal_hold`)
  - `apps/documents/views/RecordsManagement/RecordDeclarations.py` (`record_declaration_list`)
  - `apps/documents/views/RecordsManagement/VitalRecords.py` (`vital_records_list`)
- **Issue**: For every record declaration rendered in list or vital records views, `self.document.legal_holds.filter(is_active=True).exists()` executes a separate SQL query ($O(N)$ database roundtrips).
- **Fix**:
  1. In `record_declaration_list` and `vital_records_list`, annotate the queryset using `Exists`:
     ```python
     from django.db.models import Exists, OuterRef
     from apps.documents.models.RecordsManagement.DocumentLegalHolds import DocumentLegalHold
     
     hold_subquery = DocumentLegalHold.objects.filter(
         tenant=request.tenant,
         document=OuterRef("document_id"),
         is_active=True,
     )
     declarations = declarations.annotate(has_active_hold=Exists(hold_subquery))
     ```
  2. In `RecordDeclaration.is_under_legal_hold`, check `if hasattr(self, "has_active_hold"): return bool(self.has_active_hold)`.

### [x] `C4`: WORM Immutability Bypass via In-Place Record Declaration Editing
- **Found by**: `security-reviewer`
- **Location**:
  - `apps/documents/views/RecordsManagement/RecordDeclarations.py:130` (`record_declaration_edit`)
  - `apps/documents/forms/RecordsManagement/RecordDeclarations.py:11` (`RecordDeclarationForm`)
- **Issue**: `record_declaration_edit` allows updating a declaration without checking if `declaration.is_locked` or `declaration.retention_schedule.retention_mode == "regulatory_worm"` or `declaration.is_under_legal_hold`. Furthermore, the form permits changing the document, version, and schedule on existing instances.
- **Fix**:
  1. In `record_declaration_edit`, reject editing with error message if `declaration.is_locked` or `declaration.retention_schedule.retention_mode == "regulatory_worm"` or `declaration.is_under_legal_hold`.
  2. In `RecordDeclarationForm.clean()`, forbid changing `document`, `version`, or `retention_schedule` on existing instances (`if self.instance.pk`).

### [x] `C5`: Evidence Spoliation Prevention on Parent Document Deletion
- **Found by**: `security-reviewer`
- **Location**:
  - `apps/documents/views/VersionControl/Documents.py:156` (`document_delete`)
- **Issue**: If a document has an active legal hold or is declared as a locked official record, deleting the document cascades and deletes the hold and declaration, spoliating evidence and breaking WORM retention.
- **Fix**:
  In `document_delete`, check:
  ```python
  if document.legal_holds.filter(is_active=True).exists():
      messages.error(request, "Cannot delete document: An active legal hold is in place.")
      return redirect("documents:document_detail", pk=document.pk)
  if document.record_declarations.filter(is_locked=True).exists():
      messages.error(request, "Cannot delete document: It is an immutable official record.")
      return redirect("documents:document_detail", pk=document.pk)
  ```

---

## Important Findings (I1 – I9)

### [x] `I1`: Duplicate Active Record Declarations Permitted on Same Document
- **Found by**: `qa-smoke-tester`, `security-reviewer`
- **Location**: `apps/documents/forms/RecordsManagement/RecordDeclarations.py:53`
- **Issue**: A document already declared as an active record can be declared again under conflicting schedules.
- **Fix**: In `RecordDeclarationForm.clean()`, reject declaration if an existing declaration for that document exists in the tenant that is not `disposed`.

### [x] `I2`: Missing Authorization & State Validation on Record Cutoff and Retention Schedule Config
- **Found by**: `code-reviewer`, `security-reviewer`
- **Location**:
  - `apps/documents/views/RecordsManagement/RetentionSchedules.py` (`retention_schedule_create`, `retention_schedule_edit`)
  - `apps/documents/views/RecordsManagement/RecordDeclarations.py` (`record_declaration_trigger_cutoff`)
- **Issue**: Any authenticated user can create/edit organizational file plans or prematurely trigger cutoff. Also, `record_declaration_trigger_cutoff` does not check if the record is already cutoff or disposed.
- **Fix**:
  1. Add `@tenant_admin_required` to `retention_schedule_create`, `retention_schedule_edit`, and `record_declaration_trigger_cutoff`.
  2. In `record_declaration_trigger_cutoff`, verify `if declaration.record_status not in ["active"]:` return error message.

### [x] `I3`: N+1 Query in `RecordDeclarationForm` Version Dropdown Initialization
- **Found by**: `code-reviewer`, `performance-reviewer`
- **Location**: `apps/documents/forms/RecordsManagement/RecordDeclarations.py:46`
- **Issue**: `self.fields["version"].queryset` lacks `.select_related("document")`, causing individual document fetches per version choice when rendering the dropdown.
- **Fix**: Add `.select_related("document")` to `self.fields["version"].queryset`.

### [x] `I4`: `verify_legal_holds()` False Negative When Certificate Lacks Declaration
- **Found by**: `qa-smoke-tester`
- **Location**: `apps/documents/models/RecordsManagement/DestructionCertificates.py:115`
- **Issue**: If `self.record_declaration` is None, `verify_legal_holds()` unconditionally returns `False`, blocking certificate operations even when no legal hold exists.
- **Fix**: If `self.record_declaration` is None, return `True` (or check `self.document` if available).

### [x] `I5`: Disallowed CSS Class `stat-icon red` and Duplicate Query Count on Disposition Review Board
- **Found by**: `frontend-reviewer`, `performance-reviewer`
- **Location**:
  - `templates/documents/records_management/disposition_review/board.html:36`
  - `apps/documents/views/RecordsManagement/DispositionReview.py`
- **Issue**: Theme only permits `blue|green|orange|purple|slate` for `.stat-icon` (L33 prohibits `red`). Also, evaluating `.count` inside the template triggers multiple redundant SQL queries.
- **Fix**: Replace `stat-icon red` with `stat-icon orange`, and calculate counts in view context (`due_count`, `held_count`, `pending_count`).

### [x] `I6`: Missing Filter Dropdowns and Pagination Preservation in Templates
- **Found by**: `qa-smoke-tester`
- **Location**:
  - `templates/documents/records_management/retention_schedule/list.html`
  - `templates/documents/records_management/destruction_certificate/list.html`
- **Issue**:
  - Retention schedule list lacks a Status dropdown and pagination omits `&status={{ current_status }}`.
  - Destruction certificate list lacks a Sanitization Method dropdown and pagination omits `&destruction_method={{ current_method }}`.
- **Fix**: Add the missing filter dropdowns and ensure pagination preserves all query parameters.

### [ ] `I7`: Add Status-Conditional Delete Forms to Detail Templates
- **Found by**: `frontend-reviewer`
- **Location**:
  - `templates/documents/records_management/retention_schedule/detail.html`
  - `templates/documents/records_management/record_declaration/detail.html`
- **Issue**: Detail views have no action button or modal form to delete schedules (when no records attached) or delete modifiable records.
- **Fix**: Add clean, confirmation-gated POST delete action forms in detail header/card actions when eligible.

### [ ] `I8`: Missing Composite Database Indexes for Performance
- **Found by**: `performance-reviewer`
- **Location**: `apps/documents/models/RecordsManagement/*.py`
- **Issue**: Frequent list filtering and legal hold lookups perform table scans without composite indexes.
- **Fix**: Add composite indexes:
  - `RecordDeclaration`: `(tenant, -declaration_date)`, `(tenant, record_status)`, `(tenant, is_vital_record)`.
  - `DocumentLegalHold`: `(tenant, document, is_active)`.
  - `DestructionCertificate`: `(tenant, status)`.
  Create and apply migration.

### [ ] `I9`: Admin Tenant-Consistency and Read-Only Compliance Fields
- **Found by**: `security-reviewer`
- **Location**: `apps/documents/admin.py`
- **Issue**: `DestructionCertificateAdmin` allows manual editing of audit timestamps and approval statuses.
- **Fix**: Make `status`, `authorized_by`, `executed_by`, `authorized_at`, `executed_at`, and `legal_hold_verified_clear` read-only in `DestructionCertificateAdmin`.

---

## Minor Findings (M1 – M4)

### [ ] `M1`: Duplicate Word Typo in Destruction Certificate Detail
- **Found by**: `code-reviewer`, `explorer`, `qa-smoke-tester`
- **Location**: `templates/documents/records_management/destruction_certificate/detail.html:163`
- **Issue**: Renders `<span>Authorization Authorization</span>`.
- **Fix**: Change to `<span>Disposition Authorization</span>`.

### [ ] `M2`: Seeder Sub-module 13.10 Indentation Bug
- **Found by**: `code-reviewer`, `explorer`
- **Location**: `apps/documents/management/commands/seed_documents.py:642`
- **Issue**: Sub-module 13.10 block was indented under 13.9's Acme tenant loop instead of running for all tenants.
- **Fix**: Un-indent the 13.10 block to the correct tenant loop level.

### [ ] `M3`: Calendar Month Clamping in Disposition Due Date Calculation
- **Found by**: `qa-smoke-tester`
- **Location**: `apps/documents/models/RecordsManagement/RecordDeclarations.py:116`
- **Issue**: Clamping to day 28 shortens end-of-month dates (e.g. Dec 31 becomes Dec 28).
- **Fix**: Use month-end preservation calculation so month-end dates land on the actual last day of the target month.

### [ ] `M4`: Update Document Status to "archived" on Destruction Execution
- **Found by**: `security-reviewer`
- **Location**: `apps/documents/models/RecordsManagement/DestructionCertificates.py:132`
- **Issue**: When a destruction certificate is executed, `record_declaration.record_status` becomes `"disposed"`, but the parent `Document.status` remains `"active"`.
- **Fix**: In `execute_destruction()`, also set `self.document.status = "archived"` and save the document.
