---
name: documents
description: Work on the Document Management System (DMS) module (Module 13 — Document Management System). As-built = 13.1 Document Creation & Authoring (DocumentTemplate[DTMPL-], TemplateSection[DSEC-], DocumentDraft[DDFT-], DraftCollaboration[DCMT-], interactive canvas, redline diff, promotion) + 13.2 Version Control & Revision Management (Document[DOC-], DocumentVersion[DVER-], DocumentLock[DLOCK-], DocumentBranch[DBRN-], side-by-side diff comparison, check-out/check-in locking, rollback, branching/merging) + 13.3 Document Approval & Review Workflow (DocumentApprovalWorkflow[DWF-], DocumentApprovalRequest[DAPR-], DocumentSignature[DSIG-], DocumentReviewComment[DREV-], visual workflow designer, 21 CFR Part 11 manifest, token verification, approval analytics dashboard). Use when the user asks to add/change/debug anything under apps/documents or templates/documents, extend the seed_documents seeder, touch documents sidebar wiring (LIVE_LINKS 13.1/13.2/13.3), or invokes /documents.
---

# Document Management System (DMS) (Module 13)

App path: `apps/documents`. Templates: `templates/documents/`. URL prefix: `/documents/`, `app_name = "documents"`.
Mirrors `NavERP.md` "## 13. Document Management System (DMS)" (Sub-modules 13.1–13.20).

**As-built: 13.1 Document Creation & Authoring + 13.2 Version Control & Revision Management + 13.3 Document Approval & Review Workflow.**
Build the next sub-module with `/next-module next` — see `apps/quality`/`apps/procurement` for reference package layout and the mandatory Module Creation Sequence.

---

## Overview

Module 13 provides an enterprise document repository, authoring workspace, revision control, and approval orchestration engine:
- **13.1 Document Authoring**: Reusable master document blueprints (`DocumentTemplate`), modular clause library (`TemplateSection`), draft lifecycle tracking (`DocumentDraft`), full-screen interactive authoring canvas (`canvas.html`), critique/feedback notes (`DraftCollaboration`), and promotion to official released documents.
- **13.2 Version Control & Revision Management**: Automatic multi-scheme version numbering (`Document`, `DocumentVersion`), exclusive check-in/check-out concurrency locking (`DocumentLock`), side-by-side visual redline diff comparison (`compare.html`), parallel scenario branching and merge-back (`DocumentBranch`), and point-in-time version restoration/rollback.
- **13.3 Document Approval & Review Workflow**: Multi-stage approval pipelines (`DocumentApprovalWorkflow`), granular participant routing with sequential/parallel/first-responder rules (`DocumentApprovalRequest`), 21 CFR Part 11 cryptographic electronic signatures and certificate manifests (`DocumentSignature`), threaded critique and blocking annotations (`DocumentReviewComment`), visual stage layout designer (`designer.html`), and bottleneck analytics cockpit (`approval_dashboard.html`).

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

### 13.3 ApprovalWorkflow (`apps/documents/models/ApprovalWorkflow/`)

- **`DocumentApprovalWorkflows.py`** — `DocumentApprovalWorkflow` (`NUMBER_PREFIX = "DWF"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `title`, `workflow_type` (sequential, parallel, conditional_rules).
  - `status` (draft, pending, approved, rejected, cancelled, bypassed), `urgency` (low, medium, high, urgent).
  - `target_turnaround_hours`, `initiator` (FK `settings.AUTH_USER_MODEL`), `department` (FK `core.OrgUnit`), `due_date`.
  - `total_stages`, `current_stage`, `requires_all_comments_resolved`, `allow_emergency_bypass`.
  - `bypassed_by` (FK `settings.AUTH_USER_MODEL`), `bypass_reason`, `definition_json`, `completed_at`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status)`, `(tenant, urgency)`, `(tenant, document, status)`.

- **`DocumentApprovalRequests.py`** — `DocumentApprovalRequest` (`NUMBER_PREFIX = "DAPR"`):
  - `workflow` (FK `DocumentApprovalWorkflow`, `related_name="approval_requests"`).
  - `stage_number`, `stage_name`, `stage_type` (sequential, parallel_all, parallel_first).
  - `approver` (FK `settings.AUTH_USER_MODEL`, nullable), `approver_role` (FK `core.Role`, nullable).
  - `status` (pending, approved, rejected, delegated, escalated, bypassed).
  - `order`, `due_date`, `decided_at`, `decision_comments`.
  - `delegated_to`, `delegation_reason`, `delegated_at`.
  - `is_escalated`, `escalated_to`, `escalation_reason`, `escalated_at`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, status)`, `(tenant, approver, status)`, `(tenant, delegated_to, status)`, `(tenant, workflow, stage_number)`.

- **`DocumentSignatures.py`** — `DocumentSignature` (`NUMBER_PREFIX = "DSIG"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `approval_request` (FK `DocumentApprovalRequest`, nullable).
  - `signer` (FK `settings.AUTH_USER_MODEL`, nullable), `signer_name`, `signer_title`, `signer_email`.
  - `signature_type` (biometric, crypto_token, cert_x509, hmac_hash, click_to_sign).
  - `signature_meaning` (authorship, review, approval, verification, witness, receipt).
  - `signature_token` (auto UUID), `document_checksum` (SHA-256), `certificate_serial`, `signature_glyph`, `ip_address`, `user_agent`, `signed_at`, `is_valid`.
  - Constraints & Indexes: unique `(tenant, number)`, unique `signature_token`, indexes on `(tenant, document, is_valid)`, `(tenant, signer, signed_at)`.

- **`DocumentReviewComments.py`** — `DocumentReviewComment` (`NUMBER_PREFIX = "DREV"`):
  - `document` (FK `Document`), `version` (FK `DocumentVersion`, nullable), `workflow` (FK `DocumentApprovalWorkflow`, nullable).
  - `author` (FK `settings.AUTH_USER_MODEL`), `annotation_type` (inline_comment, highlight, redline, sticky_note, drawing_callout).
  - `page_number`, `coordinate_ref`, `selected_text`, `content`.
  - `parent` (FK self, nullable, `related_name="replies"`).
  - `is_blocking` (gates workflow approval), `status` (open, addressed, resolved, dismissed).
  - `resolved_by` (FK `settings.AUTH_USER_MODEL`), `resolved_at`, `resolution_notes`.
  - Constraints & Indexes: unique `(tenant, number)`, indexes on `(tenant, document, status)`, `(tenant, workflow, is_blocking)`, `(tenant, is_blocking, status)`.

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

### 13.3 Approval & Review Workflow Routes
- `/documents/workflows/`: `workflow_list`
- `/documents/workflows/create/`: `workflow_create`
- `/documents/workflows/<pk>/`: `workflow_detail`
- `/documents/workflows/<pk>/edit/`: `workflow_edit`
- `/documents/workflows/<pk>/delete/`: `workflow_delete` (POST-only, draft-only)
- `/documents/workflows/<pk>/designer/`: `workflow_designer` (interactive stage sequence builder)
- `/documents/workflows/<pk>/submit/`: `workflow_submit` (POST-only, initiates pending stage 1)
- `/documents/workflows/<pk>/bypass/`: `workflow_bypass` (POST-only, requires admin or initiator)
- `/documents/workflows/<pk>/cancel/`: `workflow_cancel` (POST-only)
- `/documents/approval-requests/`: `approval_request_list`
- `/documents/approval-requests/create/`: `approval_request_create`
- `/documents/approval-requests/<pk>/`: `approval_request_detail`
- `/documents/approval-requests/<pk>/edit/`: `approval_request_edit`
- `/documents/approval-requests/<pk>/delete/`: `approval_request_delete` (POST-only, pending in draft)
- `/documents/approval-requests/<pk>/decide/`: `approval_request_decide` (POST-only, atomic, checks blocking comments)
- `/documents/approval-requests/<pk>/delegate/`: `approval_request_delegate` (POST-only)
- `/documents/approval-requests/<pk>/escalate/`: `approval_request_escalate` (POST-only)
- `/documents/signatures/`: `signature_list`
- `/documents/signatures/create/`: `signature_create`
- `/documents/signatures/verify/`: `signature_verify` (lookup form)
- `/documents/signatures/verify/<str:token>/`: `signature_verify` (token verification view)
- `/documents/signatures/<int:pk>/`: `signature_detail`
- `/documents/signatures/<int:pk>/edit/`: `signature_edit` (locks immutable fields)
- `/documents/signatures/<int:pk>/delete/`: `signature_delete` (POST-only)
- `/documents/signatures/<int:pk>/manifest/`: `signature_manifest` (21 CFR Part 11 printable manifest)
- `/documents/review-comments/`: `review_comment_list`
- `/documents/review-comments/create/`: `review_comment_create`
- `/documents/review-comments/<int:pk>/`: `review_comment_detail`
- `/documents/review-comments/<int:pk>/edit/`: `review_comment_edit` (author or admin)
- `/documents/review-comments/<int:pk>/delete/`: `review_comment_delete` (POST-only, author or admin)
- `/documents/review-comments/<int:pk>/resolve/`: `review_comment_resolve` (POST-only)
- `/documents/review-comments/<int:pk>/reply/`: `review_comment_reply` (POST-only)
- `/documents/dashboard/`: `approval_dashboard` (analytics command center & bottleneck KPIs)

---

## Templates

Located in:
- `templates/documents/document_authoring/` (13.1 templates: templates, sections, drafts, collaborations)
- `templates/documents/version_control/` (13.2 templates):
  - `document/`: `list.html`, `detail.html`, `form.html`
  - `document_version/`: `list.html`, `detail.html`, `form.html`, `compare.html`
  - `document_lock/`: `list.html`, `detail.html`, `checkout_modal.html`, `checkin_modal.html`, `force_unlock.html`
  - `document_branch/`: `list.html`, `detail.html`, `form.html`, `merge_modal.html`
- `templates/documents/approval_workflow/` (13.3 templates):
  - `document_approval_workflow/`: `list.html`, `detail.html`, `form.html`, `designer.html`
  - `document_approval_request/`: `list.html`, `detail.html`, `form.html`
  - `document_signature/`: `list.html`, `detail.html`, `form.html`, `manifest.html`, `verify.html`
  - `document_review_comment/`: `list.html`, `detail.html`, `form.html`
  - `approval_dashboard.html`: Command center & bottleneck analytics cockpit

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
8. Multi-Stage Document Approval Workflows (Draft, Pending Stage 1/2, Approved, Emergency Bypassed).
9. Granular Approval Requests (Sequential, Parallel All, Parallel First Responder, Delegated, Escalated).
10. Electronic Signatures (Biometric seal, X.509 cryptographic thumbprint, SHA-256 checksum, UUID verification token).
11. Collaborative Review Comments (Page annotations, highlighted passages, blocking critique, threaded replies).

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
LIVE_LINKS["13.3"] = {
    "Approval Command Center": "documents:approval_dashboard",
    "Approval Workflows": "documents:workflow_list",
    "Approval Requests": "documents:approval_request_list",
    "Electronic Signatures": "documents:signature_list",
    "Review Comments": "documents:review_comment_list",
}
```

---

## Conventions & Gotchas

1. **Multi-Tenancy**: All queries MUST use `documents_scope(Model.objects.all(), request)` or `documents_object(request, Model, pk)`. All forms inherit `TenantModelForm` or use `TenantUniqueMixin` with `reject_foreign(...)`.
2. **Concurrency & Row-level Locking**: `document_checkout`, `document_checkin`, `document_version_rollback`, and `document_branch_merge` acquire row-level locks on `Document` using `Document.objects.select_for_update().get(...)` inside `transaction.atomic()` to guarantee exclusive state transitions.
3. **Approval Decision Atomicity & Gate**: `approval_request_decide` multi-model updates must be wrapped in `transaction.atomic()`. If `workflow.requires_all_comments_resolved=True`, approvals are strictly blocked while any `is_blocking=True` comments remain in `status='open'`.
4. **Stage Progression Rules**: When `parallel_first` stage requests are approved, remaining sibling requests in that stage are automatically marked `status='bypassed'`. In `parallel_all`, stages advance only when no pending, delegated, or escalated requests remain.
5. **Electronic Signature Integrity**: `DocumentSignature` automatically generates a 32-character UUID token and records the document version's SHA-256 checksum. On edit, core identity and document fields are disabled. Raw SVG or signature glyphs MUST be rendered without `|safe` or sanitized to prevent stored XSS.
6. **Privilege & Emergency Bypass**: Emergency bypass on workflows requires superuser, tenant admin, or workflow initiator privileges. Deletion of workflows is restricted to `draft` status, and deletion of approval requests is restricted to pending requests in draft workflows.
7. **Performance & Text Deferral**: `DocumentVersion.extracted_text` contains massive full-text layers. Always call `.defer("extracted_text")` (or `.defer("base_version__extracted_text")`) on list views to avoid memory exhaustion and query bloat. Form dropdowns must include `.select_related("document")` on versions and `.select_related("workflow", "approver")` on approval requests.
8. **XSS Protection in Diff View**: `difflib.HtmlDiff` escapes body lines but interpolates `fromdesc` and `todesc` raw into `<th>` headers. Always escape user version labels using `django.utils.html.escape` before passing to `make_table`.
9. **File Upload Security**: All document and version uploads are validated via `validate_safe_doc_upload(f)` enforcing `ALLOWED_DOC_EXTENSIONS` and `MAX_UPLOAD_BYTES`.
10. **Privileged Operations**: `document_force_unlock`, `document_delete`, `document_version_delete`, and `document_branch_delete` require tenant administrator privileges (`@tenant_admin_required`).
