---
name: quality
description: Work on the Quality Management System (QMS) module (Module 12 — document control & management, controlled SOPs & work instructions, engineering/document change orders (DCO), 21 CFR Part 11 compliant electronic signatures with HMAC non-repudiation, and training/compliance acknowledgments). Use when the user asks to add/change/debug anything under apps/quality or templates/quality, extend the quality seeder, touch quality sidebar wiring (LIVE_LINKS 12.1), or invokes /quality.
---

# Quality Management System (QMS) Module (Module 12)

Enterprise Quality Management System (QMS) compliant with ISO 9001, ISO 13485, GxP, and FDA 21 CFR Part 11 regulatory standards. Provides end-to-end controlled document lifecycle management, Engineering/Document Change Orders (DCO) with Change Control Board (CCB) governance, dual-credential electronic signatures with HMAC-SHA256 non-repudiation digests, employee compliance training acknowledgments, and an archive vault workbench.

- **App path:** `apps/quality/`
- **Templates:** `templates/quality/`
- **URL prefix:** `/quality/` (`app_name="quality"`)
- Mounted in `config/urls.py`; registered in `config/settings.py` `INSTALLED_APPS` as `apps.quality`.

---

## Sub-modules Overview

- **12.1 Document Control & Management**:
  - **Controlled Documents** [`QDOC-`]: SOPs, Work Instructions, Policies, Specifications, Protocols, Manuals, and Forms with version control (`1.0` -> `2.0`), review interval tracking, lifecycle state machine (`draft` -> `in_review` -> `approved` -> `effective` -> `superseded` / `obsolete` / `archived`), and predecessor/successor lineage tracking.
  - **Document Change Orders (DCO)** [`QDCR-`]: Formal engineering change control tickets with priority triage (`low`, `medium`, `high`, `critical`, `emergency`), review assessments, regulatory impact determinations, and Change Control Board (CCB) approval workflows.
  - **21 CFR Part 11 Electronic Signatures** [`QSIG-`]: Dual-credential re-authentication (`password` check), signature meaning binding (`authored`, `reviewed`, `quality_approval`, `management_approval`, `ccb_approval`, `acknowledgment`), remote IP address capture, and RFC 2104 HMAC-SHA256 cryptographic verification digests.
  - **Document Acknowledgments** [`QACK-`]: SOP/policy distribution and compliance sign-off tracking for employees with due dates, overdue escalations, and binding electronic signatures.
  - **Document Archive Vault**: Specialized compliance workbench for exploring, filtering, and exporting superseded, obsolete, and archived historical documentation.

---

## App Layout & Architecture

Backend layers follow the mandatory NavERP package structure (`models/`, `forms/`, `views/`, `urls/`):

```
apps/quality/
  models/
    _base.py                                  <- TenantOwned, TenantNumbered abstract base models
    DocumentControl/                          <- Sub-module 12.1 models
      ControlledDocuments.py                  <- ControlledDocument [QDOC-]
      DocumentChangeOrders.py                 <- DocumentChangeOrder [QDCR-]
      ElectronicSignatures.py                 <- ElectronicSignatureRecord [QSIG-]
      DocumentAcknowledgments.py              <- DocumentAcknowledgment [QACK-]
    __init__.py                               <- Re-exports all models
  forms/
    _common.py                                <- Base QualityModelForm with tenant injection & clean helpers
    DocumentControl/                          <- Sub-module 12.1 forms
      ControlledDocuments.py                  <- ControlledDocumentForm, ControlledDocumentRevisionForm
      DocumentChangeOrders.py                 <- DocumentChangeOrderForm, DocumentChangeOrderReviewForm, CCBDecisionForm
      ElectronicSignatures.py                 <- ElectronicSignatureForm (21 CFR Part 11 dual-credential check)
      DocumentAcknowledgments.py              <- DocumentAcknowledgmentForm
    __init__.py                               <- Re-exports all forms
  views/
    _common.py                                <- Base view helpers (quality_object, tenant_admin_required, write_audit_log)
    DocumentControl/                          <- Sub-module 12.1 views
      ControlledDocuments.py                  <- List, Detail, Create, Edit, Delete, Submit, Approve, Make Effective, Obsolete, Revise, Export, Vault
      DocumentChangeOrders.py                 <- List, Detail, Create, Edit, Delete, Submit, CCB Decision, Export
      ElectronicSignatures.py                 <- List, Detail, Verify, Sign Controlled Document, Export
      DocumentAcknowledgments.py              <- List, Detail, Create, Delete, Sign Acknowledgment, Export
    __init__.py                               <- Re-exports all views
  urls/
    DocumentControl/                          <- Sub-module 12.1 URLs
      ControlledDocuments.py
      DocumentChangeOrders.py
      ElectronicSignatures.py
      DocumentAcknowledgments.py
    __init__.py                               <- Re-exports all URL patterns
  admin.py                                    <- Django admin registrations
  management/commands/
    seed_quality.py                           <- Idempotent QMS seeder with realistic demo data
  tests/                                      <- Pytest test suite
    conftest.py                               <- Shared fixtures
    test_documentcontrol_models.py            <- Model invariants & transitions
    test_documentcontrol_forms.py             <- Mass-assignment, upload validation & scoping
    test_documentcontrol_views.py             <- View CRUD, actions & KPI stats
    test_documentcontrol_security.py          <- Multi-tenancy IDOR, Part 11 auth & audit logs
```

---

## Models & Entities

### 1. `ControlledDocument` (Prefix: `QDOC-`)
- **Table:** `quality_controlled_document`
- **Key Fields:** `number`, `title`, `document_type` (`sop`, `work_instruction`, `policy`, `specification`, `protocol`, `manual`, `form`, `other`), `department` (`core.OrgUnit`), `owner` (`accounts.User`), `revision` (e.g. `"1.0"`), `is_latest_revision`, `lifecycle_state` (`draft`, `in_review`, `approved`, `effective`, `superseded`, `obsolete`, `archived`), `effective_date`, `next_review_date`, `review_interval_months`, `supersedes`, `superseded_by`, `classification` (`public`, `internal`, `confidential`, `restricted`), `file` (upload with strict extension and size validation), `is_template`.
- **Properties & Methods:** `is_locked`, `is_effective`, `is_under_review`, `is_overdue_review`, `watermark_text`, `make_effective()`, `supersede()`, `mark_obsolete()`.

### 2. `DocumentChangeOrder` (Prefix: `QDCR-`)
- **Table:** `quality_change_order`
- **Key Fields:** `number`, `title`, `document` (`ControlledDocument`), `change_type` (`new_document`, `revision`, `obsoletion`, `emergency`, `administrative`), `priority` (`low`, `medium`, `high`, `critical`, `emergency`), `status` (`draft`, `submitted`, `in_assessment`, `ccb_review`, `approved`, `rejected`, `implemented`, `cancelled`), `requested_by` (`accounts.User`), `reason_for_change`, `change_description`, `regulatory_impact`, `ccb_decision` (`approved`, `rejected`, `more_info_required`, `waived`), `ccb_decision_date`, `ccb_decision_by` (`accounts.User`), `closure_notes`.

### 3. `ElectronicSignatureRecord` (Prefix: `QSIG-`)
- **Table:** `quality_e_signature`
- **Key Fields:** `number`, `document` (`ControlledDocument`), `change_order` (`DocumentChangeOrder`), `signer` (`accounts.User`), `signer_name`, `signer_title`, `signature_meaning` (`authored`, `reviewed`, `quality_approval`, `management_approval`, `ccb_approval`, `acknowledgment`), `signed_at`, `verification_hash` (HMAC-SHA256), `ip_address`, `document_revision`, `comments`.
- **Compliance:** Enforces FDA 21 CFR § 11.50 and § 11.200. Verification method `is_valid_hash()` detects any tampering of signature attributes.

### 4. `DocumentAcknowledgment` (Prefix: `QACK-`)
- **Table:** `quality_doc_acknowledgment`
- **Key Fields:** `number`, `document` (`ControlledDocument`), `document_revision`, `user` (`accounts.User`), `employee` (`hrm.EmployeeProfile`), `status` (`pending`, `acknowledged`, `waived`), `due_date`, `acknowledged_at`, `signature_record` (`ElectronicSignatureRecord`), `notes`.
- **Properties:** `is_overdue`, `days_until_due`.

---

## Routes & URLs

All routes use the `quality:` namespace:

| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/documents/` | `controlled_document_list` | Controlled documents list with filters and KPI stats |
| `/quality/documents/create/` | `controlled_document_create` | Create new controlled document |
| `/quality/documents/<pk>/` | `controlled_document_detail` | Document detail view with revision history & action buttons |
| `/quality/documents/<pk>/edit/` | `controlled_document_edit` | Edit metadata/file of draft or unapproved document |
| `/quality/documents/<pk>/delete/` | `controlled_document_delete` | POST-only delete for draft documents |
| `/quality/documents/<pk>/submit/` | `controlled_document_submit` | Submit draft document for review |
| `/quality/documents/<pk>/approve/` | `controlled_document_approve` | Admin approval for reviewed document |
| `/quality/documents/<pk>/make-effective/` | `controlled_document_make_effective` | Admin action: mark approved document effective |
| `/quality/documents/<pk>/obsolete/` | `controlled_document_obsolete` | Admin action: retire effective document |
| `/quality/documents/<pk>/new-revision/` | `controlled_document_new_revision` | Branch new revision from effective document |
| `/quality/documents/<pk>/sign/` | `controlled_document_sign` | 21 CFR Part 11 electronic signature execution |
| `/quality/documents/export/` | `controlled_document_export` | CSV export of controlled documents |
| `/quality/documents/vault/` | `document_archive_vault` | Compliance vault workbench for historical documents |
| `/quality/change-orders/` | `document_change_order_list` | DCO tickets list with filters and KPI stats |
| `/quality/change-orders/create/` | `document_change_order_create` | Create new document change order |
| `/quality/change-orders/<pk>/` | `document_change_order_detail` | DCO detail with signature manifest & actions |
| `/quality/change-orders/<pk>/edit/` | `document_change_order_edit` | Edit draft DCO |
| `/quality/change-orders/<pk>/delete/` | `document_change_order_delete` | POST-only delete for draft DCO |
| `/quality/change-orders/<pk>/submit/` | `document_change_order_submit` | Submit draft DCO for CCB review |
| `/quality/change-orders/<pk>/ccb-decision/` | `document_change_order_ccb_decision` | Record CCB determination |
| `/quality/change-orders/export/` | `document_change_order_export` | CSV export of change orders |
| `/quality/signatures/` | `electronic_signature_list` | Audit log of all 21 CFR Part 11 electronic signatures |
| `/quality/signatures/<pk>/` | `electronic_signature_detail` | Signature manifest verification detail |
| `/quality/signatures/<pk>/verify/` | `electronic_signature_verify` | Dynamic HMAC integrity check |
| `/quality/signatures/export/` | `electronic_signature_export` | CSV export of electronic signatures |
| `/quality/acknowledgments/` | `document_acknowledgment_list` | Employee compliance acknowledgments list |
| `/quality/acknowledgments/create/` | `document_acknowledgment_create` | Assign new acknowledgment requirement |
| `/quality/acknowledgments/<pk>/` | `document_acknowledgment_detail` | Acknowledgment detail view |
| `/quality/acknowledgments/<pk>/sign/` | `document_acknowledgment_sign` | Dual-credential sign-off for assigned employee |
| `/quality/acknowledgments/<pk>/delete/` | `document_acknowledgment_delete` | Admin delete of pending acknowledgment |
| `/quality/acknowledgments/export/` | `document_acknowledgment_export` | CSV export of acknowledgments |

---

## Seeder (`seed_quality`)

Run command:
```powershell
venv\Scripts\python.exe manage.py seed_quality
```

Creates realistic GxP compliance data for `acme` and `globex` tenants:
- 5 Controlled Documents per tenant:
  - SOP on Cleanroom Garbing (Effective v2.0)
  - Work Instruction on Environmental Monitoring (Effective v1.0)
  - Quality Manual (Approved v3.0)
  - Batch Record Protocol (In Review v1.0)
  - Calibration Policy (Draft v0.1)
- 3 Document Change Orders (CCB reviewed, approved, and emergency revisions)
- 4 Electronic Signature Records (Author, Quality Approval, CCB Approval)
- 4 Document Acknowledgments (Acknowledged with linked signatures and pending sign-offs)

Seeder is 100% idempotent: subsequent runs check `.exists()` and skip existing records.

---

## Conventions & Gotchas

1. **Multi-Tenancy Isolation:**
   - Always filter querysets by `tenant=request.tenant`.
   - Use `quality_object(request, Model, pk, select_related=[...])` in views for consistent tenant checks and HTTP 404 responses.
2. **21 CFR Part 11 Re-Authentication:**
   - `ElectronicSignatureForm` requires re-entering the user's password.
   - Dual-credential authentication is validated via `user.check_password(password)`.
   - Never skip credential check even if user is logged in.
3. **HMAC Signature Integrity:**
   - Hashes are calculated using `hmac.new(secret, payload, hashlib.sha256).hexdigest()`.
   - Binds `tenant_id`, `document_id`, `document_revision`, `signer_id`, and `signature_meaning`.
4. **Lifecycle State Machine:**
   - Documents in `superseded`, `obsolete`, or `archived` states are **locked** (`is_locked=True`).
   - Locked documents cannot be edited, deleted, or signed.
   - New revisions branch via `controlled_document_new_revision`, which links `supersedes=doc`.
5. **Theme CSS Badges:**
   - Strictly use colour-named classes from `static/css/theme.css`: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`. Never use semantic names like `badge-success` or `badge-danger`.
6. **File Upload Hardening:**
   - Controlled documents disallow `.svg` (to prevent Stored XSS) and executable files.
   - Files are validated against `ALLOWED_DOC_EXTENSIONS` (`.pdf`, `.docx`, etc.) and `MAX_UPLOAD_BYTES` (20MB).

---

## Sidebar Wiring (`LIVE_LINKS`)

Wired in `apps/core/navigation.py`:

```python
LIVE_LINKS = {
    # ...
    "12.1": [
        "quality:controlled_document_list",
        "quality:document_archive_vault",
        "quality:document_change_order_list",
        "quality:electronic_signature_list",
        "quality:document_acknowledgment_list",
    ],
}
```
