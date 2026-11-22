---
name: documents
description: Work on the Document Management System (DMS) module (Module 13 — Document Management System). As-built = 13.1 Document Creation & Authoring (DocumentTemplate[DTMPL-], TemplateSection[DSEC-], DocumentDraft[DDFT-], DraftCollaboration[DCMT-], interactive canvas, redline diff, promotion) + 13.2 Version Control & Revision Management (Document[DOC-], DocumentVersion[DVER-], DocumentLock[DLOCK-], DocumentBranch[DBRN-], side-by-side diff comparison, check-out/check-in locking, rollback, branching/merging). Use when the user asks to add/change/debug anything under apps/documents or templates/documents, extend the seed_documents seeder, touch documents sidebar wiring (LIVE_LINKS 13.1/13.2), or invokes /documents.
---

# Document Management System (DMS) (Module 13)

App path: `apps/documents`. Templates: `templates/documents/`. URL prefix: `/documents/`, `app_name = "documents"`.
Mirrors `NavERP.md` "## 13. Document Management System (DMS)" (Sub-modules 13.1–13.20).

**As-built: 13.1 Document Creation & Authoring + 13.2 Version Control & Revision Management.**
Build the next sub-module with `/next-module next` — see `apps/quality`/`apps/procurement` for reference package layout and the mandatory Module Creation Sequence.

---

## Overview

Module 13 provides an enterprise document repository, authoring workspace, and revision control engine:
- **13.1 Document Authoring**: Reusable master document blueprints (`DocumentTemplate`), modular clause library (`TemplateSection`), draft lifecycle tracking (`DocumentDraft`), full-screen interactive authoring canvas (`canvas.html`), critique/feedback notes (`DraftCollaboration`), and promotion to official released documents.
- **13.2 Version Control & Revision Management**: Automatic multi-scheme version numbering (`Document`, `DocumentVersion`), exclusive check-in/check-out concurrency locking (`DocumentLock`), side-by-side visual redline diff comparison (`compare.html`), parallel scenario branching and merge-back (`DocumentBranch`), and point-in-time version restoration/rollback.

---

## Models (`apps/documents/models/`)

Shared base in `models/_base.py`:
- `TenantOwned`: multi-tenant foreign key + timestamps.
- `TenantNumbered`: auto-number generator via `core.utils.next_number` with collision retry loop.

### 13.1 DocumentAuthoring (`apps/documents/models/DocumentAuthoring/`)

- **`DocumentTemplates.py`** — `DocumentTemplate` (`NUMBER_PREFIX = "DTMPL"`):
  - `template_type`: sop, contract, policy, report, memo, letter, specification, meeting_minutes, other.
  - `category`: legal, hr, operations, finance, it, quality, sales, executive.
  - `name`, `version`, `description`, `content`, `styling_rules`, `is_active`, `is_locked`.
  - Reuses core spine: `target_org_unit` (FK `core.OrgUnit`), `owner` (FK `settings.AUTH_USER_MODEL`).

- **`TemplateSections.py`** — `TemplateSection` (`NUMBER_PREFIX = "DSEC"`):
  - `template` (FK `DocumentTemplate`, nullable for global boilerplates).
  - `section_type`: header, boilerplate, disclaimer, signature_block, table_of_contents, body_section, appendix, footer.
  - `title`, `content`, `order`, `is_locked`, `is_mandatory`.

- **`DocumentDrafts.py`** — `DocumentDraft` (`NUMBER_PREFIX = "DDFT"`):
  - `template` (FK `DocumentTemplate`, nullable).
  - `title`, `document_type`, `draft_version`, `status`, `sync_status`, `content`, `word_count`.
  - `department` (FK `core.OrgUnit`), `related_party` (FK `core.Party`), `author` (FK `settings.AUTH_USER_MODEL`).
  - `is_collaboration_locked`: gates editing and autosave mutations.
  - `promoted_document` (FK `core.Document`), `promoted_version`, `promoted_at`.

- **`DraftCollaborations.py`** — `DraftCollaboration` (`NUMBER_PREFIX = "DCMT"`):
  - `draft` (FK `DocumentDraft`).
  - `author` (FK `settings.AUTH_USER_MODEL`), `entry_type`, `comment_text`, `selected_text`, `replacement_text`.
  - `status`: open, accepted, rejected, resolved.

### 13.2 VersionControl (`apps/documents/models/VersionControl/`)

- **`Documents.py`** — `Document` (`NUMBER_PREFIX = "DOC"`):
  - `title`, `slug`, `description`, `document_type`, `classification`, `status`, `versioning_scheme`.
  - `current_version_label`, `current_version_no`.
  - `is_locked`, `locked_by` (FK `settings.AUTH_USER_MODEL`), `locked_at`.
  - `owner` (FK `settings.AUTH_USER_MODEL`), `department` (FK `core.OrgUnit`), `max_versions_retained`, `tags`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status)`, `(tenant, document_type)`, `(tenant, is_locked)`.

- **`DocumentVersions.py`** — `DocumentVersion` (`NUMBER_PREFIX = "DVER"`):
  - `document` (FK `Document`, `related_name="versions"`).
  - `version_label`, `major_number`, `minor_number`, `patch_number`, `version_type` (major, minor, patch, branch_merge, rollback).
  - `file`, `file_name`, `file_size`, `file_hash` (SHA-256).
  - `extracted_text` (large text layer for search and redline diffing).
  - `is_official`, `status` (db_index=True), `author` (FK `settings.AUTH_USER_MODEL`), `branch` (FK `DocumentBranch`), `restored_from_version` (FK self).
  - Constraints & Indexes: unique `(tenant, number)`, unique `(tenant, document, version_label)`, indexes on `(tenant, document, is_official)`, `(tenant, status)`.

- **`DocumentLocks.py`** — `DocumentLock` (`NUMBER_PREFIX = "DLOCK"`):
  - `document` (FK `Document`), `base_version` (FK `DocumentVersion`), `locked_by` (FK `settings.AUTH_USER_MODEL`).
  - `checked_out_at`, `expires_at`, `lock_type` (exclusive, reservation), `checkout_note`, `working_copy_file`.
  - `status` (active, checked_in, discarded, force_unlocked).
  - `unlocked_at`, `unlocked_by` (FK `settings.AUTH_USER_MODEL`), `override_reason`.
  - Helper properties: `is_stale_lock`.

- **`DocumentBranches.py`** — `DocumentBranch` (`NUMBER_PREFIX = "DBRN"`):
  - `document` (FK `Document`), `name`, `description`, `base_version` (FK `DocumentVersion`).
  - `branch_type` (what_if, variant, draft_revision), `status` (active, merged, abandoned).
  - `created_by` (FK `settings.AUTH_USER_MODEL`), `merged_at`, `merged_by`, `merged_into_version`, `merge_strategy`, `merge_notes`.

---

## URLs & Routes (`apps/documents/urls/`)

Registered under namespace `documents:`:

### 13.1 Authoring Routes
- `/documents/templates/`: `template_list`, `template_create`, `<pk>/`, `<pk>/edit/`, `<pk>/delete/`, `<pk>/instantiate/`
- `/documents/sections/`: `template_section_list`, `template_section_create`, `<pk>/`, `<pk>/edit/`, `<pk>/delete/`
- `/documents/drafts/`: `draft_list`, `draft_create`, `<pk>/`, `<pk>/edit/`, `<pk>/delete/`, `<pk>/canvas/`, `<pk>/autosave/`, `<pk>/compare/`, `<pk>/conflicts/`, `<pk>/promote/`
- `/documents/collaborations/`: `collaboration_list`, `<pk>/`, `<draft_pk>/collaborate/`, `<pk>/edit/`, `<pk>/delete/`, `<pk>/resolve/`

### 13.2 Version Control Routes
- `/documents/`: `document_list` (main document repository)
- `/documents/create/`: `document_create`
- `/documents/<pk>/`: `document_detail`
- `/documents/<pk>/edit/`: `document_edit`
- `/documents/<pk>/delete/`: `document_delete` (POST-only, `@tenant_admin_required`)
- `/documents/versions/`: `document_version_list`
- `/documents/versions/create/`: `document_version_create`
- `/documents/versions/<pk>/`: `document_version_detail`
- `/documents/versions/<pk>/edit/`: `document_version_edit`
- `/documents/versions/<pk>/delete/`: `document_version_delete` (POST-only, `@tenant_admin_required`)
- `/documents/versions/compare/`: `document_version_compare` (visual redline diff)
- `/documents/versions/<pk>/rollback/`: `document_version_rollback` (POST-only, atomic restoration)
- `/documents/locks/`: `document_lock_list`
- `/documents/locks/<pk>/`: `document_lock_detail`
- `/documents/documents/<doc_pk>/checkout/`: `document_checkout` (row-level lock with `select_for_update`)
- `/documents/documents/<doc_pk>/checkin/`: `document_checkin` (resolves lock, creates next version)
- `/documents/locks/<pk>/force-unlock/`: `document_force_unlock` (POST-only, `@tenant_admin_required`)
- `/documents/branches/`: `document_branch_list`
- `/documents/branches/create/`: `document_branch_create`
- `/documents/branches/<pk>/`: `document_branch_detail`
- `/documents/branches/<pk>/edit/`: `document_branch_edit`
- `/documents/branches/<pk>/delete/`: `document_branch_delete` (POST-only, `@tenant_admin_required`)
- `/documents/branches/<pk>/merge/`: `document_branch_merge` (merges branch revisions into mainline)
- `/documents/branches/<pk>/abandon/`: `document_branch_abandon` (closes active branch)

---

## Templates

Located in:
- `templates/documents/document_authoring/` (13.1 templates: templates, sections, drafts, collaborations)
- `templates/documents/version_control/` (13.2 templates):
  - `document/`: `list.html`, `detail.html`, `form.html`
  - `document_version/`: `list.html`, `detail.html`, `form.html`, `compare.html`
  - `document_lock/`: `list.html`, `detail.html`, `checkout_modal.html`, `checkin_modal.html`, `force_unlock.html`
  - `document_branch/`: `list.html`, `detail.html`, `form.html`, `merge_modal.html`

---

## Seeder (`apps/documents/management/commands/seed_documents.py`)

Run via:
```powershell
venv\Scripts\python.exe manage.py seed_documents
```
Supports `--flush` option to reset module data cleanly. Demo data seeds:
1. Master Document Templates across Acme, Globex, etc. (SOP, NDA, Policy memo).
2. Template Sections (QA clause, cGMP standards, disclaimers).
3. Document Drafts and Collaborations.
4. Core Documents (SOP Master, Mutual NDA, Cloud Infrastructure Spec).
5. Document Versions (Semantic 1.0.0->1.1.0->1.2.0, Major.Minor 1.0->2.0).
6. Active and Resolved Document Locks.
7. Document Branches (What-if scenario spike, merged variants).

---

## Sidebar Wiring (`apps/core/navigation.py`)

```python
LIVE_LINKS["13.2"] = {
    "Automatic Version Numbering": "documents:document_version_list",
    "Check-in / Check-out Mechanism": "documents:document_lock_list",
    "Version Comparison & Diff View": "documents:document_version_compare",
    "Branching & Parallel Versions": "documents:document_branch_list",
    "Version History & Rollback": "documents:document_version_list",
    "Documents": "documents:document_list",
}
```

---

## Conventions & Gotchas

1. **Multi-Tenancy**: All queries MUST use `documents_scope(Model.objects.all(), request)` or `documents_object(request, Model, pk)`. All forms inherit `TenantModelForm` or use `TenantUniqueMixin` with `reject_foreign(...)`.
2. **Concurrency & Row-level Locking**: `document_checkout`, `document_checkin`, `document_version_rollback`, and `document_branch_merge` acquire row-level locks on `Document` using `Document.objects.select_for_update().get(...)` inside `transaction.atomic()` to guarantee exclusive state transitions.
3. **Performance & Text Deferral**: `DocumentVersion.extracted_text` contains massive full-text layers. Always call `.defer("extracted_text")` (or `.defer("base_version__extracted_text")`) on list views to avoid memory exhaustion and query bloat.
4. **XSS Protection in Diff View**: `difflib.HtmlDiff` escapes body lines but interpolates `fromdesc` and `todesc` raw into `<th>` headers. Always escape user version labels using `django.utils.html.escape` before passing to `make_table`.
5. **File Upload Security**: All document and version uploads are validated via `validate_safe_doc_upload(f)` enforcing `ALLOWED_DOC_EXTENSIONS` and `MAX_UPLOAD_BYTES`.
6. **Privileged Operations**: `document_force_unlock`, `document_delete`, `document_version_delete`, and `document_branch_delete` require tenant administrator privileges (`@tenant_admin_required`).
