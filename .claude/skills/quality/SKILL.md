---
name: quality
description: Work on the Quality Management System (QMS) module (Module 12 — document control & management, controlled SOPs & work instructions, engineering/document change orders (DCO), 21 CFR Part 11 compliant electronic signatures with HMAC non-repudiation, training/compliance acknowledgments; 12.2 Design Controls & Development including FDA 21 CFR § 820.30 / ISO 13485:2016 design projects, user needs, engineering specs, stage-gate design reviews with independent review sign-off, verification & validation protocols, Requirements Traceability Matrix (RTM), and audit-ready Design History File (DHF) dossiers; and 12.3 Risk Management (ISO 14971 / FMEA) including risk management plans, hazard identification & FMEA risk assessments, risk control measures & mitigations, interactive FMEA risk matrix heatmaps, risk traceability matrices, and risk management reviews/reports). Use when the user asks to add/change/debug anything under apps/quality or templates/quality, extend the quality seeder, touch quality sidebar wiring (LIVE_LINKS 12.1, 12.2, or 12.3), or invokes /quality.
---

# Quality Management System (QMS) Module (Module 12)

Enterprise Quality Management System (QMS) compliant with ISO 9001, ISO 13485:2016, ISO 14971:2019, IEC 60812, GxP, FDA 21 CFR Part 11, and FDA 21 CFR § 820.30 regulatory standards. Provides end-to-end controlled document lifecycle management, Engineering/Document Change Orders (DCO) with Change Control Board (CCB) governance, dual-credential electronic signatures with HMAC-SHA256 non-repudiation digests, employee compliance training acknowledgments, document archive vault workbench, medical device design planning, user needs & engineering specifications, stage-gate design reviews with independent reviewer governance, verification & validation protocols, dynamic Requirements Traceability Matrix (RTM), audit-ready Design History File (DHF) compilation, and ISO 14971 medical device risk management with hazard analysis, FMEA risk assessments, risk mitigation controls, interactive risk matrix heatmaps, risk traceability matrices, and risk management reports.

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

- **12.3 Risk Management (ISO 14971 / FMEA)**:
  - **Risk Management Plans (RMP)** [`QRMP-`]: ISO 14971 Clause 4 compliant risk management planning for medical devices and critical products. Manages device classification (`class_i`, `class_ii_a`, `class_ii_b`, `class_iii`), risk evaluation matrix dimensions (`3x3`, `4x4`, `5x5`), scope description, risk acceptability criteria/policy, periodic review intervals, linked `DesignProject`, lead risk manager, and lifecycle statuses (`draft` -> `active` -> `periodic_review` -> `archived`).
  - **Hazard Identification & FMEA Risk Assessments** [`QRSK-`]: ISO 14971 Clause 5/6 hazard analysis and IEC 60812 Failure Modes & Effects Analysis (DFMEA, PFMEA, UFMEA, AFMEA). Tracks sequence of events, hazardous situations, potential harm, initial Risk Priority Number ($RPN = S \times P \times D$), and auto-calculated initial risk levels (`unacceptable`, `alarp`, `broadly_acceptable`). Re-evaluates residual risk scores ($RPN_{res} = S_{res} \times P_{res} \times D_{res}$) upon applying risk controls, enforcing regulatory safety gates.
  - **Risk Control Measures & Mitigations** [`QRCM-`]: ISO 14971 Clause 7 risk reduction controls strictly structured according to the mandatory 3-tier hierarchy: (1) Inherent Safety by Design, (2) Protective Measures in medical device or manufacturing process, and (3) Information for Safety / Training / IFU warnings. Traces directly into the engineering design spine (`DesignInput` requirements, `DesignVerification` test protocols, and `ControlledDocument` procedures) with dual verification tracking (`implementation_verified`, `effectiveness_verified`).
  - **Risk Management Reviews & Reports (RMR)** [`QRMR-`]: ISO 14971 Clause 9 formal risk evaluation reports across project milestones (`initial_rmr`, `periodic_review`, `design_change_review`, `post_market_surveillance`, `complaint_trend_trigger`, `ncr_capa_trigger`). Enforces formal approval workflows, post-approval tampering guards, and 21 CFR Part 11 electronic signature integration.
  - **FMEA Risk Matrix Heatmap Workbench**: Interactive visual matrix mapping Severity vs. Probability distributions for pre-mitigation and residual risks, highlighting risk zone transitions, Pareto RPN distributions, and filtered plan-specific CSV export.
  - **Risk Traceability Matrix (Hazard -> Control -> Verification)**: Comprehensive traceability workbench linking every identified hazard to its control measure, verification protocol, test result, and residual risk acceptance evaluation with coverage metrics and CSV export.

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
    RiskManagement/                           <- Sub-module 12.3 models
      RiskManagementPlans.py                  <- RiskManagementPlan [QRMP-]
      RiskAssessments.py                      <- RiskAssessment [QRSK-]
      RiskControlMeasures.py                  <- RiskControlMeasure [QRCM-]
      RiskReviewRecords.py                    <- RiskReviewRecord [QRMR-]
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
    RiskManagement/                           <- Sub-module 12.3 forms
      RiskManagementPlans.py                  <- RiskManagementPlanForm
      RiskAssessments.py                      <- RiskAssessmentForm (with ISO 14971 safety gate & ALARP checks)
      RiskControlMeasures.py                  <- RiskControlMeasureForm (with objective verification evidence guards)
      RiskReviewRecords.py                    <- RiskReviewRecordForm (with restricted draft/under_review choices)
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
    RiskManagement/                           <- Sub-module 12.3 views
      RiskManagementPlans.py                  <- List, Detail, Create, Edit, Delete, Activate, Archive, Export
      RiskAssessments.py                      <- List, Detail, Create, Edit, Delete, Export
      RiskControlMeasures.py                  <- List, Detail, Create, Edit, Delete, Verify Impl, Verify Eff, Export
      RiskReviewRecords.py                    <- List, Detail, Create, Edit, Delete, Approve, Export
      FmeaMatrix.py                           <- FMEA Matrix, Matrix Export, Risk Traceability Matrix, Traceability Export
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
    RiskManagement/                           <- Sub-module 12.3 URLs
      RiskManagementPlans.py
      RiskAssessments.py
      RiskControlMeasures.py
      RiskReviewRecords.py
      FmeaMatrix.py
    __init__.py                               <- Re-exports all URL patterns
  admin.py                                    <- Django admin registrations for all models
  management/commands/
    seed_quality.py                           <- Idempotent QMS seeder (12.1, 12.2, 12.3)
  tests/                                      <- Pytest test suite (100% green, 604 passing tests)
    conftest.py                               <- Shared 12.1, 12.2, and 12.3 fixtures
    test_documentcontrol_models.py
    test_documentcontrol_forms.py
    test_documentcontrol_views.py
    test_documentcontrol_security.py
    test_designcontrols_models.py
    test_designcontrols_forms.py
    test_designcontrols_views.py
    test_designcontrols_security.py
    test_riskmanagement_models.py
    test_riskmanagement_forms.py
    test_riskmanagement_views.py
    test_riskmanagement_security.py
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

### Sub-module 12.3 Entities

#### 9. `RiskManagementPlan` (Prefix: `QRMP-`)
- **Table:** `quality_risk_management_plan`
- **Key Fields:** `number`, `title`, `device_name`, `device_classification` (`class_i`, `class_ii_a`, `class_ii_b`, `class_iii`), `design_project` (`DesignProject`), `lead_risk_manager` (`accounts.User`), `department` (`core.OrgUnit`), `status` (`draft`, `active`, `periodic_review`, `archived`), `plan_version`, `matrix_dimension` (`3x3`, `4x4`, `5x5`), `periodic_review_frequency_months`, `next_review_due_date`, `scope_description`, `risk_acceptability_policy`, `overall_benefit_risk_summary`, `overall_residual_risk_acceptable`, `approved_signature` (`ElectronicSignatureRecord`), `approval_date`.
- **Properties & Methods:** `status_css`, `device_class_css`, `assessments_count`, `unmitigated_risks_count`, `is_review_overdue`.
- **Indexes:** `idx_qrmp_ten_status` on `(tenant, status)`, `idx_qrmp_ten_created` on `(tenant, -created_at)`.

#### 10. `RiskAssessment` (Prefix: `QRSK-`)
- **Table:** `quality_risk_assessment`
- **Key Fields:** `number`, `plan` (`RiskManagementPlan`), `hazard_category` (`biological`, `chemical`, `electrical`, `mechanical`, `thermal`, `radiation`, `software`, `usability`, `operational`, `information_security`), `hazard_description`, `sequence_of_events`, `hazardous_situation`, `potential_harm`, `affected_user` (`patient`, `operator`, `service_personnel`, `third_party`), `analysis_type` (`dfmea`, `pfmea`, `ufmea`, `afmea`), `failure_mode`, `cause_of_failure`, `effect_of_failure`, `initial_severity` (1-5), `initial_probability` (1-5), `initial_detectability` (1-5), `initial_rpn`, `initial_risk_level` (`broadly_acceptable`, `alarp`, `unacceptable`), `residual_severity`, `residual_probability`, `residual_detectability`, `residual_rpn`, `residual_risk_level`, `residual_risk_acceptable`, `benefit_risk_justification`, `bra_required`, `lifecycle_status` (`identified`, `analyzed`, `mitigated`, `verified`, `accepted`, `closed`), `design_input` (`DesignInput`), `created_by` (`accounts.User`).
- **Properties & Methods:** `calculate_level(severity, probability)`, `initial_risk_level_badge`, `residual_risk_level_badge`, `lifecycle_status_badge`, `analysis_type_badge`.
- **Safety Gate Invariant:** `save()` auto-enforces `residual_risk_acceptable = False` if `residual_risk_level == "unacceptable"`, and sets `bra_required = True` when in ALARP zone.
- **Indexes:** `idx_qrsk_ten_plan_type`, `idx_qrsk_ten_init_level`, `idx_qrsk_ten_res_level`, `idx_qrsk_ten_status`, `idx_qrsk_ten_hazard_cat`, `idx_qrsk_ten_created`.

#### 11. `RiskControlMeasure` (Prefix: `QRCM-`)
- **Table:** `quality_risk_control_measure`
- **Key Fields:** `number`, `risk_assessment` (`RiskAssessment`), `title`, `description`, `control_hierarchy` (`inherent_safety`, `protective_measure`, `information_for_safety`), `assigned_to` (`accounts.User`), `target_completion_date`, `implementation_verified`, `implementation_date`, `effectiveness_verified`, `effectiveness_date`, `status` (`proposed`, `in_progress`, `implemented`, `verified`, `rejected`), `verification_notes`, `design_input` (`DesignInput`), `design_verification` (`DesignVerification`), `controlled_document` (`ControlledDocument`), `introduces_new_hazard`, `new_hazard_details`, `created_by` (`accounts.User`).
- **Properties & Methods:** `is_fully_verified` (both impl and eff verified), `control_hierarchy_badge`, `status_badge`.
- **Indexes:** `idx_qrcm_ten_asmt`, `idx_qrcm_ten_hier`, `idx_qrcm_ten_status`, `idx_qrcm_ten_created`.

#### 12. `RiskReviewRecord` (Prefix: `QRMR-`)
- **Table:** `quality_risk_review_record`
- **Key Fields:** `number`, `plan` (`RiskManagementPlan`), `review_title`, `review_type` (`initial_rmr`, `periodic_review`, `design_change_review`, `post_market_surveillance`, `complaint_trend_trigger`, `ncr_capa_trigger`), `review_date`, `period_start_date`, `period_end_date`, `lead_reviewer` (`accounts.User`), `status` (`draft`, `under_review`, `approved`, `rejected`), `findings_summary`, `post_market_data_reviewed`, `risk_benefit_conclusion`, `overall_residual_risk_acceptable`, `approved_signature` (`ElectronicSignatureRecord`), `approval_date`.
- **Properties & Methods:** `status_badge`, `review_type_badge`.
- **Indexes:** `idx_qrmr_ten_plan_type`, `idx_qrmr_ten_status`, `idx_qrmr_ten_created`.


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

### Sub-module 12.3 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/risk-management/plans/` | `risk_management_plan_list` | Risk management plans list with filters, KPI cards, and search |
| `/quality/risk-management/plans/create/` | `risk_management_plan_create` | Create new ISO 14971 risk management plan |
| `/quality/risk-management/plans/<pk>/` | `risk_management_plan_detail` | Plan detail, batched stats, linked hazards, reviews, and e-signatures |
| `/quality/risk-management/plans/<pk>/edit/` | `risk_management_plan_edit` | Edit plan metadata (guarded against active/signed plans) |
| `/quality/risk-management/plans/<pk>/delete/` | `risk_management_plan_delete` | POST-only delete (requires tenant admin, preserves audit object_id) |
| `/quality/risk-management/plans/<pk>/activate/` | `risk_management_plan_activate` | POST-only milestone transition to active (requires tenant admin) |
| `/quality/risk-management/plans/<pk>/archive/` | `risk_management_plan_archive` | POST-only milestone transition to archived (requires tenant admin) |
| `/quality/risk-management/plans/export/` | `risk_management_plan_export` | CSV export with csv_safe sanitization |
| `/quality/risk-management/assessments/` | `risk_assessment_list` | FMEA hazard assessments list with category, level, and plan filters |
| `/quality/risk-management/assessments/create/` | `risk_assessment_create` | Add hazard analysis / FMEA failure mode with pre-mitigation scores |
| `/quality/risk-management/assessments/<pk>/` | `risk_assessment_detail` | Assessment detail with linked controls, residual evaluation, and BRA |
| `/quality/risk-management/assessments/<pk>/edit/` | `risk_assessment_edit` | Edit hazard assessment and recompute residual metrics |
| `/quality/risk-management/assessments/<pk>/delete/` | `risk_assessment_delete` | POST-only delete (requires tenant admin) |
| `/quality/risk-management/assessments/export/` | `risk_assessment_export` | CSV export of risk assessments |
| `/quality/risk-management/controls/` | `risk_control_measure_list` | Risk control measures list with hierarchy and status filters |
| `/quality/risk-management/controls/create/` | `risk_control_measure_create` | Add mitigation measure linked to design input/verification |
| `/quality/risk-management/controls/<pk>/` | `risk_control_measure_detail` | Control measure detail with verification protocol status |
| `/quality/risk-management/controls/<pk>/edit/` | `risk_control_measure_edit` | Edit control measure (with objective evidence validation) |
| `/quality/risk-management/controls/<pk>/delete/` | `risk_control_measure_delete` | POST-only delete (requires tenant admin) |
| `/quality/risk-management/controls/<pk>/verify-implementation/` | `risk_control_measure_verify_impl` | POST-only action marking implementation verified with audit log |
| `/quality/risk-management/controls/<pk>/verify-effectiveness/` | `risk_control_measure_verify_eff` | POST-only action marking effectiveness verified with audit log |
| `/quality/risk-management/controls/export/` | `risk_control_measure_export` | CSV export of control measures |
| `/quality/risk-management/reviews/` | `risk_review_record_list` | Risk management reviews list |
| `/quality/risk-management/reviews/create/` | `risk_review_record_create` | Schedule risk management review |
| `/quality/risk-management/reviews/<pk>/` | `risk_review_record_detail` | Review detail with findings, conclusions, and approval status |
| `/quality/risk-management/reviews/<pk>/edit/` | `risk_review_record_edit` | Edit review notes (guarded against approved reviews) |
| `/quality/risk-management/reviews/<pk>/delete/` | `risk_review_record_delete` | POST-only delete (requires tenant admin) |
| `/quality/risk-management/reviews/<pk>/approve/` | `risk_review_record_approve` | POST-only formal review approval (requires tenant admin) |
| `/quality/risk-management/reviews/export/` | `risk_review_record_export` | CSV export of review records |
| `/quality/risk-management/fmea-matrix/` | `fmea_matrix` | Interactive 5x5 / NxN FMEA risk matrix heatmap workbench |
| `/quality/risk-management/fmea-matrix/export/` | `fmea_matrix_export` | CSV export of matrix distribution for selected plan |
| `/quality/risk-management/traceability-matrix/` | `risk_traceability_matrix` | Comprehensive Hazard -> Control -> Verification Traceability Matrix |
| `/quality/risk-management/traceability-matrix/export/` | `risk_traceability_matrix_export` | CSV export of Risk Traceability Matrix |

---

## Seeder (`seed_quality`)

Run command:
```powershell
venv\Scripts\python.exe manage.py seed_quality
```

Creates realistic GxP compliance data for `acme` and `globex` tenants:
- **12.1 Data**: 5 Controlled Documents, 3 Change Orders, 4 Electronic Signatures, 4 Acknowledgments per tenant.
- **12.2 Data**:
  - 2 Design Projects per tenant (`InfuseFlow Pro 3000` active, `AccuInject 5mL Safety Syringe` locked)
  - 4 Design Inputs per active project (`UN-001`, `UN-002`, `DI-001`, `DI-002`)
  - 2 Stage-Gate Design Reviews (Planning Gate approved, Input/Verification Gate scheduled)
  - 2 Design Verification & Validation Protocols (Occlusion pressure, Battery transit)
- **12.3 Data**:
  - 2 Risk Management Plans per tenant:
    - Smart Infusion Pump System (`InfuseFlow Pro 3000`, Class II, 5x5 matrix, active)
    - Sterile Syringe Device (`AccuInject 5mL Safety Syringe`, Class II, 5x5 matrix, active)
  - 4 Hazard Identification & FMEA Risk Assessments:
    - Electrical hazard: Chassis voltage leakage during line power surge ($S=4, P=3 \rightarrow \text{ALARP}$)
    - Software/Operational: Free-flow bolus delivery due to motor encoder desync ($S=5, P=3 \rightarrow \text{Unacceptable}$)
    - Mechanical: Syringe plunger clamp disengagement during infusion ($S=3, P=3 \rightarrow \text{ALARP}$)
    - Usability: Confusion between primary infusion and secondary piggyback ($S=3, P=2 \rightarrow \text{ALARP}$)
  - 4 Risk Control Measures across the 3-tier ISO 14971 hierarchy:
    - Inherent Safety: Dual-channel independent optical encoder with hardware watchdog (verified)
    - Inherent Safety: Galvanic 4kV dielectric isolation transformer (verified)
    - Protective Measure: Redundant mechanical anti-free-flow clamp (verified)
    - Information for Safety: Clear dual-color graphical UI on touchscreen and IFU warning label (verified)
  - Residual Risk Evaluations:
    - Post-mitigation motor desync reduced from $RPN=15$ (Unacceptable) to $RPN=2$ (Broadly Acceptable)
    - Electrical surge reduced to $RPN=2$ (Broadly Acceptable)
  - 2 Risk Management Reviews:
    - Interim Design Risk Assessment Review (Approved with e-signature)
    - Pre-Verification Risk Assessment Review (Under Review)

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
5. **ISO 14971 Regulatory Safety Gates:**
   - `RiskAssessment.calculate_level(severity, probability)` enforces:
     - Unacceptable (Red): $S \times P \ge 15$
     - ALARP (Amber): $6 \le S \times P < 15$
     - Broadly Acceptable (Green): $S \times P < 6$
   - Safety Gate Invariant: Under ISO 14971 Clause 7.4/8, residual risks calculating to `unacceptable` CANNOT be marked `residual_risk_acceptable=True`. `save()` automatically sets `residual_risk_acceptable=False` when residual risk level is unacceptable.
   - Clinical Benefit-Risk Analysis (BRA): In the ALARP zone, marking `residual_risk_acceptable=True` requires documented `benefit_risk_justification`.
6. **21 CFR Part 11 Electronic Signature Integrity & Tampering Guards:**
   - Plans with `approved_signature` or `status in ("active", "archived")` and review records with `status == "approved"` cannot be modified directly via edit views. A new revision or milestone review must be created.
   - Deletion views record `write_audit_log` BEFORE calling `.delete()` to preserve the entity's `object_id` in audit records.
7. **Query Optimization in FMEA & Traceability Matrices:**
   - Plan detail view aggregates KPI counts into single `.aggregate(Count("id", filter=Q(...)))` calls.
   - Matrix views avoid standalone COUNT queries on already iterated querysets by using `len(assessments)`.
   - In exports, prefetch caches are preserved using `list(a.control_measures.all())` rather than `.exists()`.
8. **Theme CSS Badges:**
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
    "12.3": [
        "quality:risk_management_plan_list",
        "quality:risk_assessment_list",
        "quality:risk_control_measure_list",
        "quality:fmea_matrix",
        "quality:risk_traceability_matrix",
    ],
}
```
