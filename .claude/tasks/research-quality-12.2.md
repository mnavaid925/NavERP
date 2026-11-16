# Research — Sub-module 12.2: Design Controls & Development (Module 12 — Quality Management System, `quality`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 12 so far:**
  - `"12.1"` is fully built and active:
    - `"Document Creation & Authoring": "quality:controlled_document_list"`
    - `"Review & Approval Workflows": "quality:electronic_signature_list"`
    - `"Document Distribution & Obsolescence": "quality:document_acknowledgment_list"`
    - `"Change Request & Revision Control": "quality:document_change_order_list"`
    - `"Archive & Retrieval": "quality:document_archive_vault"`
  - **`12.2` is the second sub-module of Module 12.**
- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py`, prefix `QDOC`): Controlled quality SOPs, specifications, protocols, drawings, and reports with lifecycle states (`draft`, `in_review`, `pending_approval`, `approved`, `effective`, `superseded`, `obsolete`, `archived`).
  - `DocumentChangeOrder` (`apps/quality/models/DocumentControl/DocumentChangeOrders.py`, prefix `QDCR`): Formal change control authorization for document and specification modifications.
  - `ElectronicSignatureRecord` (`apps/quality/models/DocumentControl/ElectronicSignatures.py`, prefix `QSIG`): FDA 21 CFR Part 11 compliant digital signature manifest with SHA-256 cryptographic binding, printed name, timestamp, and signature meaning.
  - `DocumentAcknowledgment` (`apps/quality/models/DocumentControl/DocumentAcknowledgments.py`, prefix `QACK`): Employee read-and-acknowledge sign-offs for effective procedures.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` → `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` → `class OrgUnit(models.Model)` | R&D / engineering / quality department ownership. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Unified party spine. |
| `core.Document` exists | `apps/core/models/Document.py:5` → `class Document(models.Model)` | General file attachment spine. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable tenant audit logging. |
| `core.NumberingScheme` exists | `apps/core/models/NumberingScheme.py:15` | Scheme prefix allocation registry. |
| `accounts.User` exists | `apps/accounts/models.py:52` → `class User(AbstractBaseUser, PermissionsMixin)` | Project leads, systems engineers, independent reviewers, and test executors. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | Specs, protocols, and reports linked into the DHF. |
| `quality.ElectronicSignatureRecord` exists | `apps/quality/models/DocumentControl/ElectronicSignatures.py:10` | Stage-gate review and verification sign-offs. |

### Spine entities verified NOT to exist

- **No Design Controls or DHF models exist anywhere in the repo:** Grep confirms zero existing classes for Design Projects, User Needs, Design Inputs/Outputs, Stage-Gate Reviews, or Verification Protocols.
- **`Item` in `apps/scm/models/InventoryManagement/Items.py`:** SCM 4.1 item model exists. For medical device design controls, a design project represents a device/system being developed; it identifies the target device name, classification, and intended use as first-class domain fields, with an optional loose link or text reference to catalog items.

### Candidate prefix collision check (repo-wide automated verification)

Automated regex scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QDPL` (Quality Design Plan / Project) → **0 collisions** (Completely free)
- `QINP` (Quality Design Input / Requirement) → **0 collisions** (Completely free)
- `QREV` (Quality Design Review / Gate) → **0 collisions** (Completely free)
- `QVER` (Quality Design Verification & Validation) → **0 collisions** (Completely free)
- `QDTR` (Quality Design Transfer Checklist) → **0 collisions** (Completely free)
- `QDHF` (Quality Design History File) → **0 collisions** (Completely free)

---

## Leaders surveyed (with source links)

1. **Greenlight Guru (Design Control Software)** — Purpose-built eQMS platform for the medical device industry aligned with FDA 21 CFR 820.30 and ISO 13485:2016. Its signature capability is the centralized **Automated Design Matrix & Single-Click Traceability** that links User Needs → Design Inputs → Design Outputs → Verification & Validation (V&V). Features real-time compilation of the Design History File (DHF), integrated ISO 14971 risk management linkages, and stage-gate design reviews with 21 CFR Part 11 electronic signatures.
   - *Source:* https://www.greenlight.guru/design-control-software
2. **Qualio (Design Controls & Traceability Management)** — Modern cloud eQMS for medical device and SaMD manufacturers. Delivers an interactive Traceability tab mapping relationships between user needs, product requirements, test cases, and risks. Features visual gap analysis highlighting orphaned requirements or failing tests with amber warning badges, configurable product architectures, and 1-click export of Requirements Traceability Matrices (RTM) and DHFs.
   - *Source:* https://www.qualio.com/product/design-controls
3. **MasterControl (Design Excellence)** — Life sciences market standard. Automates the compilation and indexing of the Design History File (DHF). Manages design and development planning, formal phase-gate design reviews with automated routing and 21 CFR Part 11 compliant sign-offs, and bridges engineering specifications directly downstream to production Device Master Records (DMR) and electronic Device History Records (eDHR).
   - *Source:* https://www.mastercontrol.com/design-excellence/
4. **Arena PLM / QMS by PTC (Design History File & Medical Device PLM)** — Cloud PLM/QMS leader for high-tech medical device manufacturers. Establishes a centralized digital repository for the DHF, linking design inputs, drawings, BOMs, test protocols, and risk files into closed-loop traceability. Distinguishes dynamic engineering changes and DHFs from manufacturing production baselines (DMRs) through rigorous Change Control Board workflows.
   - *Source:* https://www.arenasolutions.com/products/qms/design-history-file/
5. **Jama Connect (Medical Device Development & Design Controls)** — Requirements and engineering lifecycle platform for complex medical devices. Features bi-directional live traceability mapping User Needs → System Requirements → Design Outputs → Verification Test Protocols. Includes built-in coverage gap analysis (identifying unverified inputs), change impact analysis exposing downstream test fallout when requirements change, and pre-configured accelerators for FDA 21 CFR 820.30 and IEC 62304.
   - *Source:* https://www.jamasoftware.com/solutions/medical-device/
6. **Matrix Requirements / Matrix Req (Medical Device Design Controls)** — Item-based requirements, risk, and test management database for MedTech and SaMD. Treats every design element (User Need, Design Input, Design Output, Risk, Test Case) as a discrete database record with a unique identifier. Provides automated impact analysis, live coverage matrices, and audit-ready DHF generation without manual spreadsheet reconciliation.
   - *Source:* https://www.matrixone.health/products/matrix-req/
7. **Veeva Vault Quality / MedTech** — Cloud platform for medical device design controls and regulatory compliance. Unifies the Design and Development File (DDF / DHF) with document control and change management. Features automated traceability between design requirements, clinical evaluations, and verification testing, alongside rigorous multi-disciplinary approval workflows.
   - *Source:* https://www.veeva.com/products/medtech/
8. **Ketryx (Connected Lifecycle Management for MedTech & SaMD)** — Developer-first medical device compliance platform. Automates real-time traceability matrices between requirements, code outputs, risk mitigations, and verification tests. Provides continuous DHF compilation, missing-link detection, and automated audit-trail generation supporting FDA 21 CFR 820.30 and IEC 62304.
   - *Source:* https://www.ketryx.com/

---

## Feature catalog (this sub-module only)

### Bullet 1 — Design Planning & Inputs (Design plans, user needs, regulatory requirements, risk inputs)

- **Design & Development Project / Plan (DDP)** — Master project record establishing scope, project leadership, device risk classification (Class I, II, III / Class A, B, C, D), intended use, regulatory pathway, and target phase milestones per 21 CFR § 820.30(b) and ISO 13485:2016 7.3.2. · seen in: Greenlight Guru, MasterControl, Arena PLM, Veeva Vault · priority: **table-stakes** · spine: new model `DesignProject` (`QDPL-#####`) · **buildable now**
- **Medical Device Classification & Regulatory Pathways** — Explicit capture of device classification (FDA Class I/II/III; EU MDR Class I/IIa/IIb/III) and target submission pathway (510(k), PMA, De Novo, CE Mark MDR, Exempt). · seen in: Greenlight Guru, Qualio, Jama Connect · priority: **table-stakes** · spine: `DesignProject.device_class` & `regulatory_pathway` choices · **buildable now**
- **User Needs & Stakeholder Requirements** — Patient and clinical user needs captured in plain language ("What the device must do for the user"). · seen in: All leaders · priority: **table-stakes** · spine: new model `DesignInput` (`input_type="user_need"`) · **buildable now**
- **Engineering Design Inputs & Specifications** — Unambiguous, testable engineering, functional, and performance requirements derived from user needs per 21 CFR § 820.30(c). · seen in: All leaders · priority: **table-stakes** · spine: `DesignInput` (`input_type="functional"`, `"performance"`, `"safety"`, `"software"`, `"packaging"`) · **buildable now**
- **Input Hierarchy & Parent-Child Derivation** — Direct parent-child linkage connecting technical design inputs back to originating high-level User Needs. · seen in: Qualio, Jama Connect, Matrix Req · priority: **table-stakes** · spine: `DesignInput.user_need_parent` FK to `self` · **buildable now**
- **Regulatory Standards & Risk Input Mapping** — Categorization of design inputs addressing specific regulatory standards (ISO 10993, IEC 60601, IEC 62304) and ISO 14971 risk mitigations. · seen in: Greenlight Guru, Ketryx, Qualio · priority: **common** · spine: `DesignInput` fields (`input_type="regulatory"`, `input_type="safety"`, `rationale`) · **buildable now**
- **Controlled Specification Document Linkage** — Links design inputs to official revision-controlled specifications in Sub-module 12.1. · seen in: MasterControl, Arena PLM · priority: **common** · spine: FK `quality.ControlledDocument` on `DesignInput` · **buildable now**

### Bullet 2 — Design Reviews & Verification (Stage-gate reviews, design verification protocols, test execution, traceability)

- **Stage-Gate Design Reviews** — Formal, documented evaluations of design results at planned stages (Planning Freeze, Input Freeze, Detailed Architecture, Verification Gate, Transfer Gate, Commercial Release) per 21 CFR § 820.30(e) and ISO 13485:2016 7.3.5. · seen in: MasterControl, Greenlight Guru, Arena PLM · priority: **table-stakes** · spine: new model `DesignReview` (`QREV-#####`) · **buildable now**
- **Mandatory Independent Reviewer Sign-Off** — Enforces assignment and participation of an independent reviewer who does not have direct responsibility for the design stage being reviewed per 21 CFR § 820.30(e). · seen in: Greenlight Guru, MasterControl, Qualio · priority: **table-stakes (regulated requirement)** · spine: `DesignReview.independent_reviewer` FK `accounts.User` · **buildable now**
- **Review Decision & Action Item Resolution Gate** — Formal gate outcome (`approved`, `conditional_approval`, `rejected`) with tracked action items that must be resolved prior to gate clearance. · seen in: Arena PLM, MasterControl, Jama Connect · priority: **table-stakes** · spine: `DesignReview` fields (`status`, `action_items`, `action_items_resolved`) · **buildable now**
- **Design Verification Protocols & Test Execution** — Planning, execution, and documentation of tests demonstrating that design outputs conform to design inputs per 21 CFR § 820.30(f). Captures test methods (inspection, lab testing, engineering analysis), predetermined acceptance criteria, and pass/fail results. · seen in: Greenlight Guru, Qualio, Jama Connect, Matrix Req · priority: **table-stakes** · spine: new model `DesignVerification` (`QVER-#####`) · **buildable now**
- **Bidirectional Requirements Traceability Matrix (RTM)** — Centralized interactive matrix cross-referencing User Needs → Design Inputs → Verification Protocols → Test Results, highlighting coverage gaps (unverified requirements or orphaned tests). · seen in: All leaders · priority: **table-stakes** · spine: Relational query across `DesignProject` + `DesignInput` + `DesignVerification` · **buildable now**
- **Part 11 Electronic Signature Integration** — Links stage-gate clearances and formal protocol executions to 21 CFR Part 11 compliant cryptographic signature manifests. · seen in: All leaders · priority: **table-stakes** · spine: FK `quality.ElectronicSignatureRecord` · **buildable now**

### Bullet 3 — Design Validation & Transfer (Clinical/process validation, manufacturing transfer documentation)

- **Design Validation Protocols & User Testing** — Testing under defined actual or simulated use conditions with production-equivalent units confirming the device meets user needs and intended uses per 21 CFR § 820.30(g). · seen in: Greenlight Guru, MasterControl, Qualio · priority: **table-stakes** · spine: `DesignVerification` (`activity_type="validation"`, `"usability"`, `"clinical"`) · **buildable now**
- **Manufacturing Design Transfer Readiness Checklist** — Structured verification confirming production specifications, DMR completeness, assembly work instructions, tooling, and inspection procedures are released before commercial manufacturing handoff per 21 CFR § 820.30(h). · seen in: MasterControl, Arena PLM, Greenlight Guru · priority: **table-stakes** · spine: `DesignProject` phase gating + `DesignReview` transfer gate (`review_stage="transfer_gate"`) · **buildable now**
- **DMR Specification Package Compilation** — Links transfer documentation to controlled SOPs, work instructions, and inspection plans in Sub-module 12.1. · seen in: Arena PLM, MasterControl · priority: **common** · spine: Links to `quality.ControlledDocument` · **buildable now**

### Bullet 4 — Design History File (DHF) (Centralized compilation of design records, decisions, iterations)

- **Digital DHF Index & Dossier** — Centralized compilation indexing all design plans, approved inputs, review records, verification reports, and change approvals demonstrating the device was developed per the approved design plan per 21 CFR § 820.30(j) and ISO 13485:2016 7.3.10. · seen in: All leaders · priority: **table-stakes** · spine: Consolidated detail view aggregating `DesignProject` + `DesignInput` + `DesignReview` + `DesignVerification` · **buildable now**
- **DHF Freeze & Version Baselines** — Locks the DHF upon design transfer / commercial release to prevent unapproved tampering (`dhf_locked=True`). · seen in: Jama Connect, Greenlight Guru, Arena PLM · priority: **common** · spine: `DesignProject.dhf_locked` boolean flag · **buildable now**
- **Audit-Ready DHF Summary Report** — Formats the complete design history, traceability matrix, and signature manifest into an inspection-ready dossier for FDA investigators or notified body auditors. · seen in: Greenlight Guru, MasterControl, Qualio · priority: **differentiator** · spine: DHF summary view / export endpoint · **buildable now**

### Bullet 5 — Design Changes & Configuration Management (Post-launch changes, impact analysis, regulatory notification triggers)

- **Design Change Request & Authorization** — Formal change control governing modifications to approved design inputs, outputs, or device configurations per 21 CFR § 820.30(i). · seen in: All leaders · priority: **table-stakes** · spine: Links to Sub-module 12.1 `DocumentChangeOrder` (`QDCR`) and post-launch `DesignReview` (`review_stage="post_launch"`) · **buildable now**
- **Change Impact & Regulatory Notification Analysis** — Assessment of whether design modifications impact safety, intended use, biocompatibility, or performance, triggering mandatory regulatory notifications (e.g. FDA 510(k) Special/Traditional or CE MDR notice). · seen in: Veeva Vault, Greenlight Guru, MasterControl · priority: **common** · spine: `DocumentChangeOrder.regulatory_impact` / `DesignReview.conclusions` · **buildable now**
- **Verification Retesting & Traceability Update** — Updating traceability links and executing targeted verification re-tests following an approved design change. · seen in: Jama Connect, Matrix Req, Ketryx · priority: **common** · spine: Re-running `DesignVerification` with status updates · **buildable now**

---

## Recommended build scope (this pass — 1–4 models)

Following NavERP's strict Module Creation Sequence guidelines, Sub-module 12.2 is scoped to **4 tenant-scoped models** that form the complete, end-to-end Design Controls & Development spine:

### 1. `DesignProject` [NUMBER_PREFIX = "QDPL"]
- **Role:** Master record for a medical device or regulated engineering design and development project / Design History File (DHF) root. Governs project scope, device classification, intended use, regulatory pathway, stage-gate progression, and DHF lifecycle locking.
- **Fields:**
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `number` (CharField, max_length=32, auto-numbered e.g. `QDPL-00001`)
  - `title` (CharField, max_length=255)
  - `device_name` (CharField, max_length=200, help_text="Commercial or code name of the medical device / product")
  - `device_class` (CharField, max_length=24, choices: `class_i`="Class I (Low Risk)", `class_ii`="Class II (Moderate Risk - 510k)", `class_iii`="Class III (High Risk - PMA)", `class_a`="Class A (IVD Low Risk)", `class_b`="Class B (IVD Moderate Risk)", `class_c`="Class C (IVD High Individual Risk)", `class_d`="Class D (High Public/Individual Risk)", `unclassified`="Non-Medical / General Regulated", default="class_ii")
  - `regulatory_pathway` (CharField, max_length=24, choices: `510k`="FDA 510(k) Premarket Notification", `pma`="FDA Premarket Approval (PMA)", `de_novo`="FDA De Novo Classification", `ce_mdr`="EU CE Mark (MDR 2017/745)", `ce_ivdr`="EU CE Mark (IVDR 2017/746)", `health_canada`="Health Canada Medical Device License", `exempt`="Exempt / Self-Declaration", `other`="Other Regulatory Submission", default="510k")
  - `intended_use` (TextField, help_text="Clinical intended use and indications for use per 21 CFR § 820.30(c)")
  - `current_phase` (CharField, max_length=28, choices: `planning`="Design Planning", `input`="Design Inputs & Requirements", `output_verification`="Design Output & Verification", `validation`="Design Validation & Human Factors", `transfer`="Design Transfer to Manufacturing", `commercial_closure`="Commercial Launch & DHF Maintenance", `closed`="Project Closed", default="planning", db_index=True)
  - `status` (CharField, max_length=24, choices: `draft`="Draft / Scoping", `active`="Active Development", `gate_review`="Under Stage-Gate Review", `on_hold`="On Hold", `completed`="Completed / DHF Locked", `cancelled`="Cancelled", default="draft", db_index=True)
  - `project_lead` (FK `accounts.User`, on_delete=PROTECT, related_name="led_design_projects")
  - `quality_lead` (FK `accounts.User`, on_delete=PROTECT, related_name="quality_design_projects")
  - `department` (FK `core.OrgUnit`, on_delete=SET_NULL, null=True, blank=True, related_name="design_projects")
  - `target_completion_date` (DateField, null=True, blank=True)
  - `actual_completion_date` (DateField, null=True, blank=True)
  - `dhf_location` (CharField, max_length=255, blank=True, help_text="Physical or digital DHF repository reference identifier")
  - `dhf_locked` (BooleanField, default=False, help_text="DHF frozen upon design transfer / commercial release")
  - `description` (TextField, blank=True)
  - `created_at`, `updated_at` (from `TenantNumbered`)
- **Key Methods / Properties:**
  - `is_dhf_ready`: Returns True if all design inputs are verified, validation is passed, and transfer gate review is approved.
  - `open_reviews_count`: Count of pending or in-progress design reviews.
  - `unverified_inputs_count`: Count of active design inputs without a passing verification.

### 2. `DesignInput` [NUMBER_PREFIX = "QINP"]
- **Role:** Discrete design requirement, user need, functional specification, or regulatory input within a design project. Forms the foundational element of the Requirements Traceability Matrix (RTM).
- **Fields:**
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `project` (FK `DesignProject`, on_delete=CASCADE, related_name="inputs")
  - `number` (CharField, max_length=32, auto-numbered e.g. `QINP-00001`)
  - `identifier` (CharField, max_length=50, help_text="Engineering item identifier, e.g. UN-001, DI-ENG-004, PR-SAFETY-002")
  - `title` (CharField, max_length=255)
  - `input_type` (CharField, max_length=24, choices: `user_need`="User Need / Customer Requirement", `functional`="Functional Requirement", `performance`="Performance Requirement", `safety`="Safety & Inherent Protection", `regulatory`="Regulatory / Standard Mandate", `human_factors`="Human Factors & Usability", `software`="Software / Cybersecurity Requirement", `interface`="Interface & Physical Fit", `packaging`="Packaging, Labelling & Sterility", default="functional", db_index=True)
  - `priority` (CharField, max_length=16, choices: `critical`="Critical / Must-Have", `major`="Major / Essential", `minor`="Minor / Desirable", default="major")
  - `status` (CharField, max_length=20, choices: `draft`="Draft", `in_review`="In Review", `approved`="Approved / Frozen", `verified`="Verified & Satisfied", `deferred`="Deferred", `obsolete`="Obsolete / Superseded", default="draft", db_index=True)
  - `description` (TextField, help_text="Unambiguous, objective, and testable requirement statement")
  - `acceptance_criteria` (TextField, help_text="Quantitative or qualitative threshold required for verification pass")
  - `rationale` (TextField, blank=True, help_text="Clinical, regulatory, or engineering rationale")
  - `user_need_parent` (FK `self`, on_delete=SET_NULL, null=True, blank=True, related_name="derived_inputs", help_text="Links functional design input back to originating high-level User Need")
  - `controlled_document` (FK `quality.ControlledDocument`, on_delete=SET_NULL, null=True, blank=True, related_name="design_inputs", help_text="Links to source specification or SOP in Document Control")
  - `owner` (FK `accounts.User`, on_delete=PROTECT, related_name="owned_design_inputs")
  - `version` (CharField, max_length=20, default="1.0")
  - `created_at`, `updated_at` (from `TenantNumbered`)
- **Key Methods / Properties:**
  - `is_verified`: Returns True if associated with at least one `DesignVerification` record with `pass_fail_result="pass"`.

### 3. `DesignReview` [NUMBER_PREFIX = "QREV"]
- **Role:** Formal, documented stage-gate design review meeting and decision record per FDA 21 CFR § 820.30(e) and ISO 13485:2016 7.3.5. Enforces multidisciplinary attendance, independent reviewer sign-off, action item tracking, and 21 CFR Part 11 gate clearance.
- **Fields:**
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `project` (FK `DesignProject`, on_delete=CASCADE, related_name="reviews")
  - `number` (CharField, max_length=32, auto-numbered e.g. `QREV-00001`)
  - `title` (CharField, max_length=255)
  - `review_stage` (CharField, max_length=28, choices: `planning`="Design Planning Review", `concept`="Concept & Feasibility Review", `input_freeze`="Design Input Freeze Gate", `detailed_design`="Detailed Architecture / Output Review", `verification_gate`="Design Verification Gate", `validation_gate`="Design Validation Gate", `transfer_gate`="Design Transfer Readiness Gate", `post_launch`="Post-Launch / Change Review", default="input_freeze", db_index=True)
  - `review_date` (DateField)
  - `status` (CharField, max_length=24, choices: `scheduled`="Scheduled", `in_progress`="In Progress", `approved`="Approved (Gate Cleared)", `conditional`="Conditional Approval (Action Items Pending)", `rejected`="Rejected / Gate Hold", `cancelled`="Cancelled", default="scheduled", db_index=True)
  - `lead_reviewer` (FK `accounts.User`, on_delete=PROTECT, related_name="led_design_reviews")
  - `independent_reviewer` (FK `accounts.User`, on_delete=PROTECT, related_name="independent_design_reviews", help_text="Independent reviewer with no direct responsibility for the design stage being reviewed per 21 CFR § 820.30(e)")
  - `agenda` (TextField, blank=True)
  - `discussion_summary` (TextField, blank=True)
  - `conclusions` (TextField, blank=True)
  - `action_items` (TextField, blank=True, help_text="Assigned action items and due dates required before full gate closure")
  - `action_items_resolved` (BooleanField, default=False)
  - `electronic_signature` (FK `quality.ElectronicSignatureRecord`, on_delete=SET_NULL, null=True, blank=True, related_name="design_reviews", help_text="21 CFR Part 11 signature manifest authorizing gate closure")
  - `created_at`, `updated_at` (from `TenantNumbered`)
- **Key Methods / Properties:**
  - `is_cleared`: Returns True if `status == "approved"` and (`action_items_resolved` or not `action_items`).

### 4. `DesignVerification` [NUMBER_PREFIX = "QVER"]
- **Role:** Design Verification & Validation protocol and execution record confirming that design outputs meet design inputs (Verification - 820.30(f)) or device satisfies user needs and clinical intended use (Validation - 820.30(g)).
- **Fields:**
  - `tenant` (FK `core.Tenant`, on_delete=CASCADE)
  - `project` (FK `DesignProject`, on_delete=CASCADE, related_name="verifications")
  - `primary_input` (FK `DesignInput`, on_delete=CASCADE, related_name="verifications", help_text="Target design input or user need being verified or validated")
  - `number` (CharField, max_length=32, auto-numbered e.g. `QVER-00001`)
  - `title` (CharField, max_length=255)
  - `activity_type` (CharField, max_length=28, choices: `verification`="Design Verification (Outputs meet Inputs)", `validation`="Design Validation (Conforms to User Needs)", `usability`="Usability & Human Factors Validation (IEC 62366)", `process_validation`="Process / Transfer Validation (IQ/OQ/PQ)", default="verification", db_index=True)
  - `status` (CharField, max_length=24, choices: `draft`="Protocol Draft", `approved_protocol`="Protocol Approved", `testing`="Testing In Progress", `passed`="Passed / Criteria Met", `failed`="Failed / Non-Conformance", `waived`="Waived / Justified", default="draft", db_index=True)
  - `test_method` (CharField, max_length=24, choices: `inspection`="Visual / Dimensional Inspection", `lab_test`="Laboratory / Bench Testing", `analysis`="Engineering Analysis / Simulation", `clinical_trial`="Clinical Study / User Trial", `demonstration`="Operational Demonstration", default="lab_test")
  - `acceptance_criteria` (TextField, help_text="Predetermined objective acceptance criteria")
  - `sample_size` (PositiveIntegerField, default=1, help_text="Number of test units with statistical rationale")
  - `results_summary` (TextField, blank=True, help_text="Observed testing data and statistical summary")
  - `pass_fail_result` (CharField, max_length=12, choices: `pending`="Pending", `pass`="Pass", `fail`="Fail", default="pending", db_index=True)
  - `deviation_notes` (TextField, blank=True, help_text="Test anomalies, protocol deviations, or unexpected results")
  - `executed_by` (FK `accounts.User`, on_delete=SET_NULL, null=True, blank=True, related_name="executed_design_tests")
  - `execution_date` (DateField, null=True, blank=True)
  - `protocol_document` (FK `quality.ControlledDocument`, on_delete=SET_NULL, null=True, blank=True, related_name="verification_protocols", help_text="Formal controlled protocol document in Document Control")
  - `report_document` (FK `quality.ControlledDocument`, on_delete=SET_NULL, null=True, blank=True, related_name="verification_reports", help_text="Formal controlled test report in Document Control")
  - `created_at`, `updated_at` (from `TenantNumbered`)
- **Key Methods / Properties:**
  - `is_passed`: Returns True if `pass_fail_result == "pass"` and `status == "passed"`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

The following capabilities belong to sibling sub-modules in Module 12 or related modules and are intentionally parked:

- **12.1 Document Control & Management:** Controlled SOPs, policies, specifications, 21 CFR Part 11 e-signatures, read & acknowledge, document change orders (already built in 12.1).
- **12.3 Risk Management (ISO 14971 / FMEA):** Failure Mode and Effects Analysis (dFMEA, pFMEA, uFMEA), preliminary hazard lists, Risk Priority Numbers (RPN), pre- and post-mitigation risk evaluation matrices, and residual risk acceptance (belongs to 12.3).
- **12.4 Corrective & Preventive Action (CAPA):** CAPA issue detection, 5 Whys / Fishbone Root Cause Analysis (RCA), corrective action plans, effectiveness verification checks (belongs to 12.4).
- **12.5 Non-Conformance & Deviation Management (NCR):** Material, process, and supplier non-conformance logging, quarantine holds, Material Review Board (MRB) dispositions (rework, scrap, return-to-vendor) (belongs to 12.5).
- **12.7–12.9 Inspection Controls (IQC, IPQC, FQC):** Routine incoming receiving inspection, in-process routing checks, and finished good lot release testing (belongs to 12.7–12.9; distinct from R&D design verification).
- **12.20 Data Integrity & Electronic Records:** Computerized System Validation (CSV), ALCOA+ compliance rules, Part 11 electronic audit trail analytics (belongs to 12.20).
- **Module 9 Manufacturing Execution & Engineering BOMs:** Production BOMs, routing operations, work center capacities, and shop floor job orders (belongs to Module 9).

---

## Deferred (later passes / integrations)

The following advanced capabilities identified during market research are deferred from this initial 12.2 pass to maintain a clean, robust, and reliable core build:

- **Automated Jira / GitHub / GitLab Webhook Synchronization:** Real-time bi-directional synchronization of software issues and commits into design inputs for SaMD (Ketryx, Qualio, Greenlight Guru feature; deferred to future external API integrations).
- **Interactive 2D Node-Link Traceability Graph Visualization:** D3.js or Canvas-based visual graph rendering of the V-model hierarchy (deferred to frontend enhancement; standard tabular and hierarchical matrix view provided in core UI).
- **Native 3D CAD File Embedding (STEP / SolidWorks WebGL Viewer):** In-browser 3D interactive model inspection (deferred; technical drawings and CAD packages are linked via controlled document attachments).
- **Direct Regulatory Gateway Electronic Submissions (FDA eSTAR / Health Canada XML Export):** Automatic compilation of electronic regulatory submission packages (deferred; audit-ready DHF summary view and export provided).
- **Automated Statistical Test Protocol Sample Size Calculators:** Built-in confidence level / reliability formulas (e.g. 95%/95% sampling calculators) (deferred to quality analytics pass).
