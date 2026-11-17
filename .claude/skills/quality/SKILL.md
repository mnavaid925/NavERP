---
name: quality
description: Work on the Quality Management System (QMS) module (Module 12 — document control & management, controlled SOPs & work instructions, engineering/document change orders (DCO), 21 CFR Part 11 compliant electronic signatures with HMAC non-repudiation, training/compliance acknowledgments, and 12.2 Design Controls & Development including FDA 21 CFR § 820.30 / ISO 13485:2016 design projects, user needs, engineering specs, stage-gate design reviews with independent review sign-off, verification & validation protocols, Requirements Traceability Matrix (RTM), and audit-ready Design History File (DHF) dossiers). Use when the user asks to add/change/debug anything under apps/quality or templates/quality, extend the quality seeder, touch quality sidebar wiring (LIVE_LINKS 12.1 or 12.2), or invokes /quality.
---

# Quality Management System (QMS) Module (Module 12)

Enterprise Quality Management System (QMS) compliant with ISO 9001, ISO 13485:2016, GxP, FDA 21 CFR Part 11, and FDA 21 CFR § 820.30 regulatory standards. Provides end-to-end controlled document lifecycle management, Engineering/Document Change Orders (DCO) with Change Control Board (CCB) governance, dual-credential electronic signatures with HMAC-SHA256 non-repudiation digests, employee compliance training acknowledgments, document archive vault workbench, medical device design planning, user needs & engineering specifications, stage-gate design reviews with independent reviewer governance, verification & validation protocols, dynamic Requirements Traceability Matrix (RTM), and audit-ready Design History File (DHF) compilation.

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

- **12.2 Design Controls & Development**:
  - **Design Projects & DHF Planning** [`QDPL-`]: Medical device and critical software development project management complying with FDA 21 CFR § 820.30 and ISO 13485:2016 Clause 7.3. Manages device classification (`class_i`, `class_ii`, `class_iii`), regulatory pathways (`510k`, `pma`, `de_novo`, `ce_mark`, `exempt`), sequential phase-gate lifecycle (`planning` -> `input` -> `output_verification` -> `validation` -> `commercial_closure` -> `closed`), project and quality leads, target completion dates, and post-transfer immutable regulatory freeze (`dhf_locked=True`).
  - **Design Inputs & Engineering Specs** [`QINP-`]: Product specifications, user needs, functional, software, hardware, safety, usability, risk control, and packaging requirements. Features parent-child requirement traceability (linking derived design inputs to parent user needs), acceptance criteria, priority triage (`low`, `medium`, `high`, `critical`), and auto-verification status tracking.
  - **Stage-Gate Design Reviews** [`QREV-`]: Formal phase milestone evaluations satisfying 21 CFR § 820.30(e). Governs review stages (`planning_gate`, `inputs_gate`, `outputs_gate`, `verification_gate`, `validation_gate`, `transfer_gate`, `post_market_gate`), lead reviewer assignment, mandatory independent reviewer sign-off (with operational independence from project lead), action item tracking, formal gate approval, and electronic signature linking.
  - **Design Verification & Validation Protocols** [`QVER-`]: V&V test execution records satisfying 21 CFR § 820.30(f)/(g). Features activity types (`design_verification`, `design_validation`), test methods (`lab_testing`, `inspection`, `analysis`, `clinical_eval`, `usability_study`, `simulation`), sample sizes, acceptance criteria, results summaries, pass/fail results (`pending`, `pass`, `fail`, `inconclusive`), executor tracking, and bi-directional status synchronization with primary design inputs.
  - **Requirements Traceability Matrix (RTM)**: Living compliance workbench rendering the multi-tier traceability chain (`User Need` -> `Design Input` -> `Verification Protocol` -> `Test Result` -> `Status`), calculating requirement coverage percentages, flagging uncovered inputs as coverage gaps, and offering streaming CSV export (`RTM_<number>.csv`).
  - **Design History File (DHF) Dossier**: Audit-ready regulatory dossier index compiling the complete design history (DHF plan, requirements specification, design review minutes, V&V execution protocols, and linked controlled documents), evaluating DHF completeness criteria, and providing CSV index export (`DHF_Index_<number>.csv`).

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
    DesignControls/                           <- Sub-module 12.2 models
      DesignProjects.py                       <- DesignProject [QDPL-]
      DesignInputs.py                         <- DesignInput [QINP-]
      DesignReviews.py                        <- DesignReview [QREV-]
      DesignVerifications.py                  <- DesignVerification [QVER-]
    __init__.py                               <- Re-exports all models
  forms/
    _common.py                                <- Base QualityModelForm with tenant injection & clean helpers
    DocumentControl/                          <- Sub-module 12.1 forms
      ControlledDocuments.py                  <- ControlledDocumentForm, ControlledDocumentRevisionForm
      DocumentChangeOrders.py                 <- DocumentChangeOrderForm, DocumentChangeOrderReviewForm, CCBDecisionForm
      ElectronicSignatures.py                 <- ElectronicSignatureForm (21 CFR Part 11 dual-credential check)
      DocumentAcknowledgments.py              <- DocumentAcknowledgmentForm
    DesignControls/                           <- Sub-module 12.2 forms
      DesignProjects.py                       <- DesignProjectForm
      DesignInputs.py                         <- DesignInputForm (with DHF lock check & passing V&V guard)
      DesignReviews.py                        <- DesignReviewForm (with 21 CFR § 820.30(e) independent reviewer check)
      DesignVerifications.py                  <- DesignVerificationForm (with sample size & criteria validation)
    __init__.py                               <- Re-exports all forms
  views/
    _common.py                                <- Base view helpers (quality_object, quality_scope, tenant_admin_required, write_audit_log)
    DocumentControl/                          <- Sub-module 12.1 views
      ControlledDocuments.py                  <- List, Detail, Create, Edit, Delete, Submit, Approve, Make Effective, Obsolete, Revise, Export, Vault
      DocumentChangeOrders.py                 <- List, Detail, Create, Edit, Delete, Submit, CCB Decision, Export
      ElectronicSignatures.py                 <- List, Detail, Verify, Sign Controlled Document, Export
      DocumentAcknowledgments.py              <- List, Detail, Create, Delete, Sign Acknowledgment, Export
    DesignControls/                           <- Sub-module 12.2 views
      DesignProjects.py                       <- List, Detail, Create, Edit, Delete, Advance Phase, Lock DHF, Export
      DesignInputs.py                         <- List, Detail, Create, Edit, Delete, Export
      DesignReviews.py                        <- List, Detail, Create, Edit, Delete, Approve Gate, Export
      DesignVerifications.py                  <- List, Detail, Create, Edit, Delete, Export
      TraceabilityMatrix.py                   <- Traceability Matrix, Matrix Export, DHF Dossier, DHF Export
    __init__.py                               <- Re-exports all views
  urls/
    DocumentControl/                          <- Sub-module 12.1 URLs
      ControlledDocuments.py
      DocumentChangeOrders.py
      ElectronicSignatures.py
      DocumentAcknowledgments.py
    DesignControls/                           <- Sub-module 12.2 URLs
      DesignProjects.py
      DesignInputs.py
      DesignReviews.py
      DesignVerifications.py
      TraceabilityMatrix.py
    __init__.py                               <- Re-exports all URL patterns
  admin.py                                    <- Django admin registrations for all models
  management/commands/
    seed_quality.py                           <- Idempotent QMS seeder (12.1 and 12.2)
  tests/                                      <- Pytest test suite (100% green, 356 passing tests)
    conftest.py                               <- Shared 12.1 and 12.2 fixtures
    test_documentcontrol_models.py
    test_documentcontrol_forms.py
    test_documentcontrol_views.py
    test_documentcontrol_security.py
    test_designcontrols_models.py
    test_designcontrols_forms.py
    test_designcontrols_views.py
    test_designcontrols_security.py
```

---

## Models & Entities

### Sub-module 12.1 Entities

#### 1. `ControlledDocument` (Prefix: `QDOC-`)
- **Table:** `quality_controlled_document`
- **Key Fields:** `number`, `title`, `document_type` (`sop`, `work_instruction`, `policy`, `specification`, `protocol`, `manual`, `form`, `other`), `department` (`core.OrgUnit`), `owner` (`accounts.User`), `revision` (e.g. `"1.0"`), `is_latest_revision`, `lifecycle_state` (`draft`, `in_review`, `approved`, `effective`, `superseded`, `obsolete`, `archived`), `effective_date`, `next_review_date`, `review_interval_months`, `supersedes`, `superseded_by`, `classification` (`public`, `internal`, `confidential`, `restricted`), `file`, `is_template`.
- **Properties & Methods:** `is_locked`, `is_effective`, `is_under_review`, `is_overdue_review`, `watermark_text`, `make_effective()`, `supersede()`, `mark_obsolete()`.

#### 2. `DocumentChangeOrder` (Prefix: `QDCR-`)
- **Table:** `quality_change_order`
- **Key Fields:** `number`, `title`, `document` (`ControlledDocument`), `change_type` (`new_document`, `revision`, `obsoletion`, `emergency`, `administrative`), `priority` (`low`, `medium`, `high`, `critical`, `emergency`), `status` (`draft`, `submitted`, `in_assessment`, `ccb_review`, `approved`, `rejected`, `implemented`, `cancelled`), `requested_by` (`accounts.User`), `reason_for_change`, `change_description`, `regulatory_impact`, `ccb_decision` (`approved`, `rejected`, `more_info_required`, `waived`), `ccb_decision_date`, `ccb_decision_by` (`accounts.User`), `closure_notes`.

#### 3. `ElectronicSignatureRecord` (Prefix: `QSIG-`)
- **Table:** `quality_e_signature`
- **Key Fields:** `number`, `document` (`ControlledDocument`), `change_order` (`DocumentChangeOrder`), `signer` (`accounts.User`), `signer_name`, `signer_title`, `signature_meaning` (`authored`, `reviewed`, `quality_approval`, `management_approval`, `ccb_approval`, `acknowledgment`), `signed_at`, `verification_hash` (HMAC-SHA256), `ip_address`, `document_revision`, `comments`.

#### 4. `DocumentAcknowledgment` (Prefix: `QACK-`)
- **Table:** `quality_doc_acknowledgment`
- **Key Fields:** `number`, `document` (`ControlledDocument`), `document_revision`, `user` (`accounts.User`), `employee` (`hrm.EmployeeProfile`), `status` (`pending`, `acknowledged`, `waived`), `due_date`, `acknowledged_at`, `signature_record` (`ElectronicSignatureRecord`), `notes`.

---

### Sub-module 12.2 Entities

#### 5. `DesignProject` (Prefix: `QDPL-`)
- **Table:** `quality_design_project`
- **Key Fields:** `number`, `title`, `device_name`, `device_class` (`class_i`, `class_ii`, `class_iii`), `regulatory_pathway` (`510k`, `pma`, `de_novo`, `ce_mark`, `exempt`), `intended_use`, `current_phase` (`planning`, `input`, `output_verification`, `validation`, `commercial_closure`, `closed`), `status` (`draft`, `active`, `on_hold`, `completed`, `cancelled`), `project_lead` (`accounts.User`), `quality_lead` (`accounts.User`), `department` (`core.OrgUnit`), `target_completion_date`, `actual_completion_date`, `dhf_location`, `dhf_locked`, `description`.
- **Properties & Methods:** `is_locked`, `is_active`, `phase_progress_pct`, `status_css`, `phase_css`, `device_class_css`.
- **Compound Index:** `idx_qdpl_ten_created` on `(tenant, -created_at)`.

#### 6. `DesignInput` (Prefix: `QINP-`)
- **Table:** `quality_design_input`
- **Key Fields:** `number`, `project` (`DesignProject`), `identifier` (e.g. `"UN-001"`, `"SRS-102"`), `title`, `input_type` (`user_need`, `functional`, `performance`, `interface`, `safety`, `regulatory`, `software`, `hardware`, `usability`, `risk_control`, `packaging`), `priority` (`low`, `medium`, `high`, `critical`), `status` (`draft`, `approved`, `verified`, `deprecated`), `owner` (`accounts.User`), `user_need_parent` (`self`, self-referential FK), `controlled_document` (`ControlledDocument`), `acceptance_criteria`, `description`, `rationales`.
- **Properties & Methods:** `is_verified` (optimized with prefetch cache inspection), `status_css`, `priority_css`, `input_type_css`.

#### 7. `DesignReview` (Prefix: `QREV-`)
- **Table:** `quality_design_review`
- **Key Fields:** `number`, `project` (`DesignProject`), `title`, `review_stage` (`planning_gate`, `inputs_gate`, `outputs_gate`, `verification_gate`, `validation_gate`, `transfer_gate`, `post_market_gate`), `review_date`, `status` (`scheduled`, `in_progress`, `approved`, `conditional`, `rejected`), `lead_reviewer` (`accounts.User`), `independent_reviewer` (`accounts.User`, 21 CFR § 820.30(e)), `electronic_signature` (`ElectronicSignatureRecord`), `conclusions`, `action_items`, `action_items_resolved`, `recommendations`.
- **Properties & Methods:** `is_cleared`, `stage_css`, `status_css`.

#### 8. `DesignVerification` (Prefix: `QVER-`)
- **Table:** `quality_design_verification`
- **Key Fields:** `number`, `project` (`DesignProject`), `primary_input` (`DesignInput`), `title`, `activity_type` (`design_verification`, `design_validation`), `status` (`draft`, `in_progress`, `passed`, `failed`, `cancelled`), `test_method` (`lab_testing`, `inspection`, `analysis`, `clinical_eval`, `usability_study`, `simulation`), `sample_size`, `acceptance_criteria`, `results_summary`, `pass_fail_result` (`pending`, `pass`, `fail`, `inconclusive`), `executed_by` (`accounts.User`), `execution_date`, `protocol_document` (`ControlledDocument`), `report_document` (`ControlledDocument`), `notes`.
- **Properties & Methods:** `is_passed`, `status_css`, `result_css`, `activity_type_css`.

---

## Routes & URLs

All routes use the `quality:` namespace:

### Sub-module 12.1 Routes
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

### Sub-module 12.2 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/design-controls/projects/` | `design_project_list` | Design projects list with filters, stats, and search |
| `/quality/design-controls/projects/create/` | `design_project_create` | Initialize new design project and DHF plan |
| `/quality/design-controls/projects/<pk>/` | `design_project_detail` | Project detail, phase timeline, linked inputs, reviews & tests |
| `/quality/design-controls/projects/<pk>/edit/` | `design_project_edit` | Edit project metadata (guarded by DHF lock) |
| `/quality/design-controls/projects/<pk>/delete/` | `design_project_delete` | POST-only delete (guarded by DHF lock) |
| `/quality/design-controls/projects/<pk>/advance-phase/` | `design_project_advance_phase` | POST-only phase progression through stage gates |
| `/quality/design-controls/projects/<pk>/lock-dhf/` | `design_project_lock_dhf` | Formal 21 CFR § 820.30(j) immutable DHF freeze |
| `/quality/design-controls/projects/export/` | `design_project_export` | CSV export of design projects |
| `/quality/design-controls/inputs/` | `design_input_list` | Design inputs & user needs list |
| `/quality/design-controls/inputs/create/` | `design_input_create` | Add design input / specification |
| `/quality/design-controls/inputs/<pk>/` | `design_input_detail` | Design input detail with child specs and linked V&V protocols |
| `/quality/design-controls/inputs/<pk>/edit/` | `design_input_edit` | Edit specification (guarded by DHF lock) |
| `/quality/design-controls/inputs/<pk>/delete/` | `design_input_delete` | POST-only delete (guarded by DHF lock) |
| `/quality/design-controls/inputs/export/` | `design_input_export` | CSV export of design inputs |
| `/quality/design-controls/reviews/` | `design_review_list` | Stage-gate design reviews list |
| `/quality/design-controls/reviews/create/` | `design_review_create` | Schedule stage-gate design review |
| `/quality/design-controls/reviews/<pk>/` | `design_review_detail` | Design review detail with actions & approval gate |
| `/quality/design-controls/reviews/<pk>/edit/` | `design_review_edit` | Edit review notes & action items (guarded by DHF lock) |
| `/quality/design-controls/reviews/<pk>/delete/` | `design_review_delete` | POST-only delete (guarded by DHF lock) |
| `/quality/design-controls/reviews/<pk>/approve-gate/` | `design_review_approve_gate` | Formally clear and approve stage gate milestone |
| `/quality/design-controls/reviews/export/` | `design_review_export` | CSV export of design reviews |
| `/quality/design-controls/verifications/` | `design_verification_list` | V&V test protocols list |
| `/quality/design-controls/verifications/create/` | `design_verification_create` | Author V&V test protocol (auto-verifies primary input) |
| `/quality/design-controls/verifications/<pk>/` | `design_verification_detail` | Verification protocol execution detail & results |
| `/quality/design-controls/verifications/<pk>/edit/` | `design_verification_edit` | Update test results (auto-syncs primary input status) |
| `/quality/design-controls/verifications/<pk>/delete/` | `design_verification_delete` | POST-only delete (recalculates input status) |
| `/quality/design-controls/verifications/export/` | `design_verification_export` | CSV export of verification protocols |
| `/quality/design-controls/matrix/` | `traceability_matrix` | Requirements Traceability Matrix (RTM) workbench |
| `/quality/design-controls/matrix/export/` | `traceability_matrix_export` | Stream RTM CSV (`RTM_<number>.csv`) |
| `/quality/design-controls/projects/<pk>/dhf/` | `design_project_dhf` | Audit-ready Design History File (DHF) dossier |
| `/quality/design-controls/projects/<pk>/dhf/export/` | `design_project_dhf_export` | Stream DHF Index CSV (`DHF_Index_<number>.csv`) |

---

## Seeder (`seed_quality`)

Run command:
```powershell
venv\Scripts\python.exe manage.py seed_quality
```

Creates realistic GxP compliance data for `acme` and `globex` tenants:
- **12.1 Data**: 5 Controlled Documents, 3 Change Orders, 4 Electronic Signatures, 4 Acknowledgments per tenant.
- **12.2 Data**:
  - 2 Design Projects per tenant:
    - Smart Infusion Pump System (`InfuseFlow Pro 3000`, Class II, 510(k), active in `output_verification` phase)
    - Sterile Disposable Syringe Set (`AccuInject 5mL Safety Syringe`, Class II, 510(k), completed with `dhf_locked=True`)
  - 4 Design Inputs per active project:
    - User Needs (`UN-001`, `UN-002`)
    - Functional Engineering Specs (`DI-001`, `DI-002`) linked to parent User Needs
  - 2 Stage-Gate Design Reviews:
    - Planning Gate Review (Approved with independent reviewer sign-off)
    - Design Input & Verification Gate Review (Scheduled)
  - 2 Design Verification & Validation Protocols:
    - Occlusion Pressure Detection Test (Passed, verifying `DI-001`)
    - Battery Transit Life Test (Passed, verifying `DI-002`)

Seeder is 100% idempotent: subsequent runs check `.exists()` and skip existing records.

---

## Conventions & Gotchas

1. **Multi-Tenancy Isolation:**
   - Always filter querysets by `tenant=request.tenant`.
   - Use `quality_object(request, Model, pk, select_related=[...])` in views for consistent tenant checks and HTTP 404 responses.
   - Forms inherit from `QualityModelForm` which injects `tenant` and filters foreign key querysets. Cross-tenant foreign keys submitted in POST data are rejected with validation errors via `reject_foreign`.
2. **21 CFR § 820.30(j) Regulatory DHF Freeze:**
   - Projects with `dhf_locked=True` represent frozen design history files.
   - Any attempt to modify, delete, advance phase, add/edit/delete inputs, reviews, or verification protocols under a locked project is strictly rejected at the view and form validation layers.
3. **21 CFR § 820.30(e) Independent Reviewer Governance:**
   - Every formal design review requires an independent reviewer who does not have direct operational responsibility for the design under evaluation.
   - Form validation strictly prohibits `independent_reviewer == lead_reviewer` and `independent_reviewer == project.project_lead`.
4. **Auto-Synchronization of Verification Status:**
   - When a `DesignVerification` protocol achieves `pass_fail_result == "pass"` and `status == "passed"`, the `primary_input.status` automatically updates to `"verified"` and an `AuditLog` entry (`action="verify"`) is emitted.
   - Modifying a test from pass to fail or deleting a passing protocol automatically re-evaluates `primary_input.status` and reverts it to `"approved"` if no other passing tests exist.
5. **Requirements Traceability Matrix (RTM) Query Optimization:**
   - `DesignInput.is_verified` checks `_prefetched_objects_cache` before querying. In RTM and DHF views, inputs are queried with `.prefetch_related("verifications")` to prevent N+1 query storms.
6. **Theme CSS Badges:**
   - Strictly use colour-named classes from `static/css/theme.css`: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`. Never use semantic names like `badge-success`, `badge-danger`, `badge-purple`, or `badge-blue`.

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
    "12.2": [
        "quality:design_project_list",
        "quality:design_input_list",
        "quality:design_review_list",
        "quality:design_verification_list",
        "quality:traceability_matrix",
    ],
}
```
