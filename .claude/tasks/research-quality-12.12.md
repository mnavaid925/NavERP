# Research — Sub-module 12.12: Training & Competency Management (Module 12 — Quality Management System, `quality`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 12 so far (`apps/core/navigation.py`):**
  - `"12.1"` (Document Control & Management):
    - `"Document Creation & Authoring": "quality:controlled_document_list"`
    - `"Review & Approval Workflows": "quality:electronic_signature_list"`
    - `"Document Distribution & Obsolescence": "quality:document_acknowledgment_list"`
    - `"Change Request & Revision Control": "quality:document_change_order_list"`
    - `"Archive & Retrieval": "quality:document_archive_vault"`
  - `"12.2"` (Design Controls & Development):
    - `"Design Planning & Inputs": "quality:design_project_list"`
    - `"Design Reviews & Verification": "quality:design_review_list"`
    - `"Design Validation & Transfer": "quality:design_verification_list"`
    - `"Design History File (DHF)": "quality:traceability_matrix"`
    - `"Design Changes & Configuration Management": "quality:design_input_list"`
  - `"12.3"` (Risk Management / ISO 14971):
    - `"Hazard Identification & Analysis": "quality:risk_assessment_list"`
    - `"Risk Evaluation & Scoring": "quality:fmea_matrix"`
    - `"Risk Control & Mitigation": "quality:risk_control_measure_list"`
    - `"Residual Risk Assessment": "quality:risk_traceability_matrix"`
    - `"Risk Management File & Reporting": "quality:risk_management_plan_list"`
  - `"12.4"` (Corrective & Preventive Action / CAPA):
    - `"Issue Detection & Logging": "quality:capa_investigation_list"`
    - `"Root Cause Analysis (RCA)": "quality:root_cause_analysis_list"`
    - `"Action Plan Development": "quality:capa_action_list"`
    - `"CAPA Tracking & Escalation": "quality:capa_tracking_board"`
    - `"Effectiveness Verification & Closure": "quality:capa_effectiveness_review_list"`
  - `"12.5"` (Non-Conformance & Deviation Management):
    - `"NCR Initiation & Classification": "quality:non_conformance_report_list"`
    - `"Containment & Segregation": "quality:quarantine_containment_list"`
    - `"Disposition & Material Review": "quality:mrb_disposition_list"`
    - `"Impact Assessment & Customer Notification": "quality:process_deviation_list"`
    - `"Trending & Metrics": "quality:ncr_analytics_dashboard"`
  - `"12.6"` (Supplier & Vendor Quality Management):
    - `"Supplier Qualification & Audit": "quality:supplier_qualification_audit_list"`
    - `"Incoming Inspection & Receiving": "quality:avl_directory"`
    - `"Supplier Performance Monitoring": "quality:supplier_quality_scorecard_list"`
    - `"Supplier CAPA & Development": "quality:supplier_corrective_action_list"`
    - `"Supplier Change Notification (SCN)": "quality:supplier_change_notification_list"`
  - `"12.7"` (Incoming Quality Control / IQC):
    - `"Inspection Planning & Sampling": "quality:incoming_inspection_plan_list"`
    - `"Goods Receipt & Inspection Execution": "quality:incoming_inspection_lot_list"`
    - `"Certificate of Analysis (CoA) Management": "quality:certificate_of_analysis_list"`
    - `"Inspection Data Capture & SPC": "quality:iqc_spc_dashboard"`
    - `"Reject & Return Material Authorization (RMA)": "quality:quality_return_authorization_list"`
  - `"12.8"` (In-Process Quality Control / IPQC):
    - `"Process Parameter Monitoring": "quality:process_parameter_log_list"`
    - `"First Article Inspection (FAI)": "quality:first_article_inspection_list"`
    - `"In-Line Inspection & Testing": "quality:in_process_inspection_list"`
    - `"Work Instruction Adherence": "quality:spc_dashboard"`
    - `"Process Audit & Layered Process Audits (LPA)": "quality:layered_process_audit_list"`
  - `"12.9"` (Final Product Quality & Release / OQC):
    - `"Final Inspection Protocols": "quality:final_inspection_lot_list"`
    - `"Lot Sampling & Acceptance Testing": "quality:oqc_hold_board"`
    - `"Packaging & Labeling Verification": "quality:packaging_label_verification_list"`
    - `"Certificate of Conformance (CoC) Issuance": "quality:certificate_of_conformance_list"`
    - `"Finished Goods Release Authorization": "quality:quality_release_authorization_list"`
  - `"12.10"` (Calibration & Measurement System Analysis):
    - `"Calibration Schedule & Planning": "quality:calibration_gage_list"`
    - `"Calibration Execution & Records": "quality:calibration_record_list"`
    - `"Out-of-Tolerance (OOT) Investigation": "quality:out_of_tolerance_investigation_list"`
    - `"Gage R&R and MSA Studies": "quality:measurement_system_analysis_list"`
    - `"Calibration Vendor Management": "quality:calibration_vendor_directory"`
  - `"12.11"` (Audit Management):
    - `"Audit Program Planning": "quality:audit_program_list"`
    - `"Audit Execution & Checklists": "quality:quality_audit_list"`
    - `"Audit Findings & Reporting": "quality:audit_finding_list"`
    - `"Corrective Action Tracking": "quality:audit_action_tracker"`
    - `"Regulatory & Certification Audits": "quality:regulatory_inspection_host_list"`

- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py`, prefix `QDOC`): Standard operating procedures (SOPs), work instructions (WIs), test protocols, and quality manuals that form the curriculum syllabus.
  - `DocumentChangeOrder` (`apps/quality/models/DocumentControl/DocumentChangeOrders.py`, prefix `QDCR`): Document change orders triggering mandatory retraining prior to release or effectivity.
  - `ElectronicSignatureRecord` (`apps/quality/models/DocumentControl/ElectronicSignatures.py`, prefix `QSIG`): 21 CFR Part 11 compliant e-signatures for course completions, supervisor verifications, and qualification sign-offs.
  - `CapaInvestigation` (`apps/quality/models/CapaManagement/CapaInvestigations.py`, prefix `QCAP`) & `CapaAction` (`apps/quality/models/CapaManagement/CapaActions.py`, prefix `QACT`): Corrective and preventive action plans mandating remedial or targeted employee retraining.
  - `NonConformanceReport` (`apps/quality/models/NonConformance/NonConformanceReports.py`, prefix `QNCR`): Non-conformance reports referencing operator competency deficiencies or corrective retraining.
  - `QualityAudit` (`apps/quality/models/AuditManagement/QualityAudits.py`, prefix `QAUD`) & `AuditFinding` (`apps/quality/models/AuditManagement/AuditFindings.py`, prefix `QFND`): Internal/external audit findings citing training record lapses or qualification gaps.

- **Cross-module spine models available to FK:**
  - `core.Tenant` (`apps/core/models/Tenant.py:17`): Multi-tenant isolation foundation across all models.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:5`): Internal departments, plant operations, cleanrooms, and laboratory units mapped to competency matrices.
  - `core.Party` (`apps/core/models/Party.py:5`) & `core.PartyRole` (`apps/core/models/PartyRole.py:5`): External vendor/supplier personnel, contractors, third-party instructors, and training providers.
  - `core.Employment` (`apps/core/models/Employment.py:5`): Employee job title, department assignment (`org_unit`), manager relationship, and employment status.
  - `accounts.User` (`apps/accounts/models.py:52`): Trainees, qualified trainers/instructors, supervisors/practical verifiers, and certification issuing authorities.
  - `core.AuditLog` (`apps/core/models/AuditLog.py:5` + `write_audit_log` helper): Immutable tenant-scoped audit logging for 21 CFR Part 11, EU Annex 11, and ISO 13485/ISO 9001 compliance.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and atomic retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Departments, plants, and operational units scoped in competency matrices. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | External contractors, vendor trainees, and external accredited training providers. |
| `core.Employment` exists | `apps/core/models/Employment.py:5` -> `class Employment(models.Model)` | Employee role, department (`org_unit`), job title, and supervisor hierarchy. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | Trainees, instructors, practical verifiers, and qualification approvers. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable audit trail for FDA 21 CFR Part 11 and ISO 13485 inspection readiness. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | SOPs, work instructions, and specifications bound to training curricula. |
| `quality.DocumentChangeOrder` exists | `apps/quality/models/DocumentControl/DocumentChangeOrders.py:8` | Document revision orders driving automated retraining workflows. |
| `quality.ElectronicSignatureRecord` exists | `apps/quality/models/DocumentControl/ElectronicSignatures.py:10` | Formal 21 CFR Part 11 e-signatures for course completion and certification. |
| `quality.CapaAction` exists | `apps/quality/models/CapaManagement/CapaActions.py:8` | CAPA corrective action plans driving retraining assignments. |
| `quality.NonConformanceReport` exists | `apps/quality/models/NonConformance/NonConformanceReports.py:10` | Non-conformance records citing personnel qualification issues. |
| `quality.AuditFinding` exists | `apps/quality/models/AuditManagement/AuditFindings.py:8` | Audit findings citing training deficiencies or expired qualifications. |

### Spine entities verified NOT to exist (or unbuilt in Module 12 / ERP)

- **Module 5 unbuilt masters:** `Item`, `LotSerial`, `UOM`, `StockMove` are planned for Module 5. Quality models use free-text stand-in fields (`equipment_scope`, `product_line_scope`) when qualification is tied to specific machinery or product lines, ensuring complete loose-coupling without hard FKs to unbuilt tables.
- **SCORM / xAPI LMS Runtime Video Player:** External e-learning standard playback engine (running SCORM packages interactively in-browser) is an integration concern. Sub-module 12.12 provides the complete data model, curriculum definition, document-driven training workflow, practical checklist evaluations, passing scores, certification lifecycle, and regulatory inspection files.
- **Enterprise Calendar Webhooks:** Direct calendar exchange webhooks (Exchange / Google Workspace) are external integrations. 12.12 delivers full scheduling metadata, session timestamps, deadlines, grace periods, and reminder notification logs.

### Auto-number Prefix Collision Check (0 collisions verified)

Automated ripgrep scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QMTX` (Quality Competency Matrix) -> **0 collisions** (Completely free)
- `QCRS` (Quality Training Course) -> **0 collisions** (Completely free)
- `QENR` (Quality Training Enrollment / Assignment) -> **0 collisions** (Completely free)
- `QCERT` (Quality Competency Certification) -> **0 collisions** (Completely free)

---

## Leaders surveyed (with source links)

1. **MasterControl (Training Excellence / Quality Excellence)** — Industry-standard life sciences eQMS platform for FDA 21 CFR Part 11/820, EU GMP Annex 11, and ISO 13485:2016 compliance. Features automated training assignment triggered by SOP revisions and CAPA actions, "training-dictated document effectivity" (SOPs cannot go effective until mandatory staff complete training), randomized comprehension exams, 2-step On-the-Job Training (OJT) checklist verifications with Group Verify capabilities, and audit-ready individual training dossiers.
   - *Source:* https://www.mastercontrol.com/quality/training-management/
2. **Veeva Vault Training (Veeva Systems)** — Cloud-native market leader for pharmaceutical and medical device life sciences. Built around a role-based qualification matrix connecting Learner Roles, Curricula, and Training Requirements; provides interactive training matrix visualization, direct integration with Veeva QualityDocs SOPs, automated assignment routing on job role changes or document revisions, prerequisite course sequencing, and auditable learner exemption governance.
   - *Source:* https://www.veeva.com/products/vault-training/
3. **Honeywell Sparta TrackWise Digital (Training Management)** — Salesforce-based enterprise quality platform for regulated manufacturing and life sciences. Directly ties training workflows to document management (DMS) lifecycles and quality events (CAPAs, deviations, change controls); supports SCORM e-learning, electronic document acknowledgments, role-based curricula, 21 CFR Part 11 electronic signatures, and executive compliance dashboards.
   - *Source:* https://www.spartasystems.com/trackwise-digital/training-management/
4. **ETQ Reliance (Training Management Software)** — Flexible enterprise quality and EHS management suite (Hexagon). Connects training courses directly to controlled documents with an "Automate with the next revision" feature; triggers training from CAPA and New Product Introduction (NPI); enforces role-based user profiles; delivers automated deadline notifications and overdue escalations; optimized for frontline shop-floor workers without corporate email.
   - *Source:* https://www.etq.com/training-management/
5. **ComplianceQuest (Training Management Software)** — Native Salesforce EQMS for medical devices, aerospace, automotive, and manufacturing. Offers role-based curriculum mapping, classroom / instructor-led training (ILT) scheduling, attendance tracking, SCORM player integration, custom quizzes with passing thresholds, manager practical evaluation sign-offs, and contractor/supplier training portals.
   - *Source:* https://www.compliancequest.com/training-management-system/
6. **Qualio (Training Management eQMS)** — Modern life sciences eQMS for emerging biotech, pharma, and medical devices. Features document-driven inline training assigned directly from approved SOPs; automatic retraining triggers upon document revisions; role-based learning paths; comprehension quizzes with configurable passing scores; 21 CFR Part 11 electronic signatures; and real-time gap analysis dashboards.
   - *Source:* https://www.qualio.com/product/training
7. **Ideagen Quality Management / Q-Pulse (People & Training Module)** — High-reliability compliance platform for aviation, healthcare, and life sciences. Replaces subjective evaluations with standardized competency frameworks and measurable matrices; tracks certification and qualification expiration dates; issues automated pre-lapse alerts; and maintains complete employee training histories for regulatory inspections.
   - *Source:* https://www.ideagen.com/products/ideagen-quality-management
8. **UL Solutions ComplianceWire (ULTRUS)** — Leading GxP compliance LMS used by the U.S. FDA to train its own field investigators under a formal CRADA. Provides role-based qualification matrices, digital qualification form workflows, supplier/contractor qualification, strict 21 CFR Part 11 / EU Annex 11 compliance, interactive team qualification charts, and extensive regulatory inspection readiness reporting.
   - *Source:* https://www.ul.com/services/compliancewire-learning-management-system
9. **SAP SuccessFactors / SAP S/4HANA QM Training** — Enterprise ERP quality and workforce qualification integration. Bridges HR job catalogs and production work centers with quality qualification profiles; enforces prerequisite skills before allowing shop-floor machine operation or batch release in SAP PP/QM; logs recurrent qualification validity intervals.
   - *Source:* https://www.sap.com/products/hcm/learning-management-lms.html

---

## Feature catalog (this sub-module only)

### 1. Training Needs Analysis & Role-Based Competency Matrices
- **Role-Based Competency & Qualification Matrix** — Central matrix mapping organizational roles (`role_title`), job codes, and departments (`core.OrgUnit`) to mandatory qualification requirements, required SOPs, and proficiency levels · seen in: *Veeva Vault, MasterControl, UL ComplianceWire, ComplianceQuest* · priority: `table-stakes` · spine: new table `CompetencyMatrix` (`QMTX`) · buildable now.
- **Skills Gap Analysis & Readiness Assessment** — Real-time comparison between an employee's completed qualifications and the target role's matrix requirements, identifying missing courses, upcoming expirations, or unfulfilled prerequisites · seen in: *Veeva Vault, Ideagen Q-Pulse, Qualio* · priority: `table-stakes` · spine: calculation properties & gap analysis view · buildable now.
- **Annual & Multi-Year Training Planning** — Enterprise quality training plans defining annual training themes, target completion dates, allocated training hours, and budget allocations for compliance programs · seen in: *Ideagen, ETQ Reliance, SAP QM* · priority: `common` · spine: fields in `CompetencyMatrix` & `QualityTrainingCourse` · buildable now.
- **Competency Level & Proficiency Hierarchy** — Structured qualification tiers (e.g. Level 1: Trainee / Under Supervision, Level 2: Qualified Operator / Independent, Level 3: Advanced Subject Matter Expert, Level 4: Qualified Trainer / Evaluator) · seen in: *UL ComplianceWire, MasterControl, Ideagen* · priority: `table-stakes` · spine: choices in `CompetencyMatrix` and `CompetencyCertification` · buildable now.
- **Department & Facility Scoping** — Scoping matrix requirements by specific manufacturing lines, cleanrooms, laboratories, or organizational units ensuring site-specific safety and GxP compliance · seen in: *ETQ Reliance, Veeva Vault* · priority: `common` · spine: FK to `core.OrgUnit` · buildable now.

### 2. Course Development & Delivery
- **Multi-Modal Course Delivery Methods** — Support for diverse delivery channels: Read & Understand (Self-Paced Document Review), Classroom / Instructor-Led Training (ILT), Interactive E-Learning, On-the-Job Training (OJT), and External Vendor/Third-Party Training · seen in: *All leaders (MasterControl, Veeva, TrackWise, ComplianceQuest, ETQ)* · priority: `table-stakes` · spine: choices on `QualityTrainingCourse` (`QCRS`) · buildable now.
- **Controlled Document & SOP Direct Binding** — Direct linkage between a training course and an active SOP or work instruction in Document Control (`quality.ControlledDocument`), establishing standard operating procedures as the definitive syllabus · seen in: *MasterControl, Veeva Vault (QualityDocs), Qualio, ETQ Reliance* · priority: `table-stakes` · spine: FK from `QualityTrainingCourse` to `quality.ControlledDocument` · buildable now.
- **On-the-Job Training (OJT) Checklist & Practical Criteria** — Detailed practical performance checklist items (e.g. step-by-step equipment setup, aseptic technique verification, batch record entry) evaluated during hands-on mentoring · seen in: *MasterControl, ComplianceQuest, UL ComplianceWire* · priority: `table-stakes` · spine: text/JSON checklist fields on `QualityTrainingCourse` and `TrainingEnrollment` · buildable now.
- **Course Versioning & Revision Management** — Structured revision numbering (e.g. Rev 1, Rev 2) tracking syllabus changes, updated learning objectives, and changes in passing criteria aligned with document revisions · seen in: *TrackWise Digital, MasterControl, Qualio* · priority: `table-stakes` · spine: fields on `QualityTrainingCourse` · buildable now.
- **Course Duration, Credit Hours & CEU Tracking** — Recording planned duration hours, practical demonstration hours, and Continuing Education Units (CEUs) for professional accreditation · seen in: *ComplianceQuest, UL ComplianceWire* · priority: `common` · spine: numeric fields on `QualityTrainingCourse` · buildable now.
- **External Vendor & Third-Party Training Management** — Logging external certified training courses delivered by equipment manufacturers, calibration houses, or accredited registrars · seen in: *ComplianceQuest, Ideagen, UL ComplianceWire* · priority: `common` · spine: vendor fields and FK to `core.Party` · buildable now.

### 3. Training Scheduling & Enrollment
- **Automated Role-Based Enrollment** — Automatic creation of training assignments when a user is assigned a job role or department, instantly populating mandatory onboarding curricula · seen in: *Veeva Vault, MasterControl, TrackWise Digital, UL ComplianceWire* · priority: `table-stakes` · spine: new table `TrainingEnrollment` (`QENR`) · buildable now.
- **Event-Driven Retraining Triggers (Document Change & CAPA)** — Automatic generation of retraining assignments when a linked `ControlledDocument` is revised via `DocumentChangeOrder`, or when a `CapaAction` mandates procedural retraining · seen in: *MasterControl, Veeva Vault, ETQ Reliance, Qualio* · priority: `table-stakes` · spine: FKs to `DocumentChangeOrder` and `CapaAction` on `TrainingEnrollment` · buildable now.
- **Training Calendar & Classroom Session Scheduling** — Scheduling training session dates, start/end times, training rooms/virtual links, and instructor assignments · seen in: *ComplianceQuest, TrackWise Digital, ETQ Reliance* · priority: `table-stakes` · spine: fields in `TrainingEnrollment` and `QualityTrainingCourse` · buildable now.
- **Due Date Enforcement, Grace Periods & Auto-Escalation** — Time-bound completion targets (e.g. 14, 30, or 60 days from assignment), defined grace periods, and overdue flagging to prevent compliance gaps · seen in: *All leaders (MasterControl, Veeva, ETQ, ComplianceQuest, Ideagen)* · priority: `table-stakes` · spine: date fields and status logic in `TrainingEnrollment` · buildable now.
- **Formal Learner Exemption & Waiver Governance** — Controlled request and approval workflow to formally waive or exempt an employee from a training assignment (e.g. equivalent prior experience, extended medical leave), maintaining a documented audit justification · seen in: *Veeva Vault, MasterControl* · priority: `differentiator` · spine: waiver fields and approver FK on `TrainingEnrollment` · buildable now.

### 4. Competency Assessment & Certification
- **Formal Comprehension Assessment & Exam Scoring** — Post-training comprehension quizzes or written exams with recorded numerical scores (e.g. 85%), passing score thresholds (e.g. 80%), and pass/fail determination · seen in: *MasterControl, Qualio, ComplianceQuest, UL ComplianceWire* · priority: `table-stakes` · spine: score fields in `TrainingEnrollment` · buildable now.
- **2-Step Practical OJT Verification Workflow** — Formal two-tier sign-off workflow where the trainee first submits their practical demonstration, followed by independent evaluation and sign-off by a qualified supervisor or mentor (`accounts.User`) · seen in: *MasterControl, ComplianceQuest, UL ComplianceWire* · priority: `table-stakes` · spine: workflow states and verifier FKs in `TrainingEnrollment` · buildable now.
- **Competency Certification Issuance** — Automatic issuance of an official, numbered competency certificate (`QCERT-XXXXX`) upon satisfying all course and practical requirements · seen in: *All leaders (Ideagen, UL ComplianceWire, ComplianceQuest, MasterControl)* · priority: `table-stakes` · spine: new table `CompetencyCertification` (`QCERT`) · buildable now.
- **Qualification Expiration & Validity Tracking** — Calculation of certificate validity intervals (e.g. 12, 24, or 36 months) and explicit expiration dates (`valid_until`), driving proactive recertification workflows · seen in: *Ideagen Q-Pulse, MasterControl, Veeva Vault, UL ComplianceWire* · priority: `table-stakes` · spine: date fields on `CompetencyCertification` · buildable now.
- **Periodic Re-qualification & Renewal Cycles** — Tracking recertification frequency (annual, biennial, triennial) and renewing certifications upon refresher course completion · seen in: *Veeva Vault, MasterControl, Ideagen* · priority: `table-stakes` · spine: renewal fields on `CompetencyCertification` · buildable now.

### 5. Training Records & Regulatory Compliance
- **Individual Employee Training Dossier & Transcript** — Consolidated, chronological training history file for every employee, displaying completed courses, assessment scores, certifications held, and current compliance status · seen in: *All leaders (MasterControl, Veeva Vault, UL ComplianceWire, Qualio)* · priority: `table-stakes` · spine: employee transcript view & PDF export · buildable now.
- **Regulatory Inspection Readiness & Audit Export** — Instant compilation of training proof for FDA (21 CFR Part 820/211), ISO 13485:2016 §6.2, and ISO 9001:2015 §7.2 audits, demonstrating that personnel operating a line or releasing a batch were fully qualified at that specific date · seen in: *Veeva Vault, MasterControl, UL ComplianceWire* · priority: `table-stakes` · spine: dedicated inspection summary view & filtering · buildable now.
- **Real-Time Compliance & Overdue Analytics Dashboard** — Executive metrics displaying organizational training compliance percentage (e.g. 96.5%), overdue assignment count, upcoming expirations within 30/60 days, and department-by-department compliance ranking · seen in: *ETQ Reliance, Qualio, ComplianceQuest, TrackWise Digital* · priority: `table-stakes` · spine: dashboard analytics view · buildable now.
- **Electronic Signatures & Immutable Audit Trail** — 21 CFR Part 11 compliant sign-offs (user ID, timestamp, intent/meaning: "Trainee Completion", "Trainer Verification", "Certification Issuance") backed by immutable logging · seen in: *MasterControl, Veeva Vault, Qualio, TrackWise Digital* · priority: `table-stakes` · spine: FK to `quality.ElectronicSignatureRecord` & `core.AuditLog` · buildable now.

### 6. Beyond the Bullets
- **Training-Dictated Document Effectivity Gating** — Integration logic indicating whether a pending revision of a `ControlledDocument` has met its required training threshold before being authorized for final `effective` release · seen in: *MasterControl, Veeva Vault* · priority: `differentiator` · spine: verification helper method linking `ControlledDocument` and `TrainingEnrollment` · buildable now.
- **Shop-Floor Cleanroom & Equipment Qualification Gating** — Qualification lookup method allowing manufacturing work centers or laboratory equipment to verify an operator's active certification status before initiating operations · seen in: *SAP QM, MasterControl* · priority: `differentiator` · spine: model helper `is_user_qualified(user, course/qualification)` · buildable now.

---

## Recommended build scope (this pass — 4 models)

### Model 1: `CompetencyMatrix` [NUMBER_PREFIX = "QMTX"]
- **Package:** `apps/quality/models/TrainingCompetency/CompetencyMatrices.py`
- **Purpose:** Role-based competency & training curriculum matrix defining mandatory qualification requirements, required SOPs, proficiency thresholds, and recertification intervals for specific organizational roles and departments.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QMTX`)
  - `title` (`CharField(255)`): Matrix title (e.g. "Cleanroom Aseptic Operator Competency Matrix", "Quality Control Analytical Chemist Curriculum")
  - `target_role` (`CharField(128)`): Job title / functional role (e.g. "Aseptic Cleanroom Operator", "QC Lab Analyst", "Quality Assurance Specialist", "Calibration Technician")
  - `department` (`ForeignKey("core.OrgUnit", null=True, blank=True, related_name="competency_matrices")`): Governing organizational unit, laboratory, or plant facility
  - `qualification_tier` (`CharField(32)`): `entry_trainee` (Tier 1: Trainee / Under Direct Supervision), `qualified_independent` (Tier 2: Qualified Independent Operator), `senior_specialist` (Tier 3: Senior Specialist / Lead), `master_trainer` (Tier 4: Certified Trainer & Practical Evaluator)
  - `criticality` (`CharField(24)`): `gxp_mandatory` (Mandatory GxP / Regulatory Critical), `quality_critical` (Quality Critical), `operational_standard` (Standard Operational), `continuous_improvement` (Recommended / Development)
  - `validity_period_months` (`PositiveIntegerField(default=12)`): Recertification cycle interval (e.g. 12 months for annual refresher, 24 for biennial, 0 for perpetual)
  - `passing_score_required` (`DecimalField(max_digits=5, decimal_places=2, default=80.00)`): Minimum examination passing percentage required
  - `status` (`CharField(24)`): `draft`, `active`, `under_revision`, `retired`
  - `description` (`TextField(blank=True)`): Detailed description of role competencies, regulatory expectations, and prerequisite qualifications
  - `revision` (`PositiveSmallIntegerField(default=1)`): Matrix revision number
  - `approved_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="approved_competency_matrices")`)
  - `approved_date` (`DateField(null=True, blank=True)`)
  - `effective_date` (`DateField(null=True, blank=True)`)
- **Properties / Methods:**
  - `is_effective`: Boolean indicating whether the matrix is active and within effective dates.
  - `active_courses_count`: Count of linked active courses in this curriculum.
- **Verified FKs:** `core.Tenant`, `core.OrgUnit`, `accounts.User`.

### Model 2: `QualityTrainingCourse` [NUMBER_PREFIX = "QCRS"]
- **Package:** `apps/quality/models/TrainingCompetency/QualityTrainingCourses.py`
- **Purpose:** GxP training course and syllabus definition, binding controlled document SOPs, classroom sessions, e-learning modules, and On-the-Job Training (OJT) practical checklists.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QCRS`)
  - `code` (`CharField(64)`): Unique course code (e.g. "TRN-SOP-042", "TRN-ASEPTIC-101", "TRN-GMP-ANNUAL")
  - `title` (`CharField(255)`): Course title (e.g. "Aseptic Gowning & Cleanroom Protocol Qualification")
  - `delivery_method` (`CharField(32)`): `read_and_understand` (Read & Understand Document Review), `classroom_ilt` (Classroom / Instructor-Led Training), `elearning` (Interactive E-Learning / Multimedia), `on_the_job_ojt` (On-the-Job Training & Practical Checklist), `external_vendor` (External Vendor / Certified Third-Party Training)
  - `category` (`CharField(32)`): `sop_procedure` (SOP / Work Instruction Training), `gxp_compliance` (cGMP / Regulatory Compliance), `safety_ehs` (Environmental Health & Safety), `technical_skills` (Technical / Operational Skills), `equipment_qualification` (Equipment & Instrument Qualification), `audit_capa_remedial` (Remedial / CAPA Follow-up)
  - `competency_matrix` (`ForeignKey("quality.CompetencyMatrix", null=True, blank=True, related_name="courses")`): Associated role matrix / curriculum
  - `controlled_document` (`ForeignKey("quality.ControlledDocument", null=True, blank=True, related_name="training_courses")`): Bound SOP or quality document
  - `retrain_on_revision` (`BooleanField(default=True)`): Automatically triggers employee retraining when bound document is revised
  - `duration_hours` (`DecimalField(max_digits=5, decimal_places=2, default=1.00)`): Estimated course completion or lecture hours
  - `passing_score` (`DecimalField(max_digits=5, decimal_places=2, default=80.00)`): Required score to pass examination (percentage)
  - `assessment_method` (`CharField(32)`): `written_exam` (Written / Electronic Examination), `ojt_checklist` (Practical OJT Checklist Sign-off), `trainer_observation` (Instructor Observation & Demonstration), `acknowledgment_only` (Read & Understood Electronic Acknowledgment), `none` (Attendance Only)
  - `ojt_checklist_criteria` (`TextField(blank=True)`): Practical demonstration checklist steps and criteria for OJT evaluations
  - `syllabus_content` (`TextField(blank=True)`): Detailed learning objectives, course syllabus, and reference materials
  - `external_provider` (`ForeignKey("core.Party", null=True, blank=True, related_name="provided_quality_courses")`): Vendor or external certification body
  - `instructor` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="instructed_quality_courses")`): Primary qualified instructor
  - `revision` (`PositiveSmallIntegerField(default=1)`): Course version number
  - `status` (`CharField(24)`): `draft`, `active`, `under_revision`, `retired`
- **Properties / Methods:**
  - `enrollments_count`: Total number of enrollments.
  - `completed_enrollments_count`: Total successfully completed enrollments.
  - `has_document_link`: Boolean whether course is bound to a `ControlledDocument`.
- **Verified FKs:** `core.Tenant`, `quality.CompetencyMatrix`, `quality.ControlledDocument`, `core.Party`, `accounts.User`.

### Model 3: `TrainingEnrollment` [NUMBER_PREFIX = "QENR"]
- **Package:** `apps/quality/models/TrainingCompetency/TrainingEnrollments.py`
- **Purpose:** Granular employee training assignment and execution record, tracking lifecycle status from assignment to study, examination, practical OJT supervisor verification, waiver, or completion.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QENR`)
  - `course` (`ForeignKey("quality.QualityTrainingCourse", on_delete=models.CASCADE, related_name="enrollments")`)
  - `trainee` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quality_training_enrollments")`): Enrolled employee
  - `assignment_reason` (`CharField(32)`): `role_onboarding` (Role Curriculum / New Hire Onboarding), `periodic_refresher` (Periodic Recertification Refresher), `document_revision` (SOP Revision Triggered Retraining), `capa_corrective` (CAPA / Non-Conformance Remedial Action), `management_directed` (Management Directed / Development), `for_cause` (For-Cause Re-qualification)
  - `document_change_order` (`ForeignKey("quality.DocumentChangeOrder", null=True, blank=True, related_name="triggered_training_enrollments")`): DCO that triggered retraining
  - `capa_action` (`ForeignKey("quality.CapaAction", null=True, blank=True, related_name="triggered_training_enrollments")`): CAPA action driving retraining
  - `assigned_date` (`DateField`): Date training was assigned
  - `due_date` (`DateField`): Mandatory completion deadline
  - `completion_date` (`DateField(null=True, blank=True)`): Date training was successfully finished
  - `status` (`CharField(24)`): `assigned`, `in_progress`, `pending_verification`, `completed`, `failed`, `waived`, `overdue`
  - `score_achieved` (`DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`): Examination score percentage achieved
  - `attempts_count` (`PositiveSmallIntegerField(default=0)`): Number of assessment attempts taken
  - `trainee_signed_at` (`DateTimeField(null=True, blank=True)`): Timestamp when trainee completed self-study or practical exam
  - `practical_verifier` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="verified_training_enrollments")`): Supervisor or qualified trainer who evaluated practical OJT
  - `verified_at` (`DateTimeField(null=True, blank=True)`): Timestamp of supervisor verification sign-off
  - `verifier_remarks` (`TextField(blank=True)`): Evaluator's observations, strengths, and areas for improvement
  - `electronic_signature` (`ForeignKey("quality.ElectronicSignatureRecord", null=True, blank=True, related_name="training_enrollments")`): Part 11 electronic signature link
  - `is_waived` (`BooleanField(default=False)`): Whether assignment was exempted / waived
  - `waiver_reason` (`TextField(blank=True)`): Formal justification for exemption
  - `waived_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="waived_training_enrollments")`): Approver of exemption
  - `notes` (`TextField(blank=True)`)
- **Properties / Methods:**
  - `is_overdue`: Boolean indicating whether due date has passed without completion or waiver.
  - `is_passed`: Boolean indicating whether achieved score meets or exceeds course passing threshold.
  - `days_remaining`: Days until due date (negative if overdue).
- **Verified FKs:** `core.Tenant`, `quality.QualityTrainingCourse`, `accounts.User`, `quality.DocumentChangeOrder`, `quality.CapaAction`, `quality.ElectronicSignatureRecord`.

### Model 4: `CompetencyCertification` [NUMBER_PREFIX = "QCERT"]
- **Package:** `apps/quality/models/TrainingCompetency/CompetencyCertifications.py`
- **Purpose:** Formal qualification and competency certificate issued upon successful course completion and practical evaluation, tracking validity intervals, recertification deadlines, and inspection readiness.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QCERT`)
  - `enrollment` (`ForeignKey("quality.TrainingEnrollment", on_delete=models.CASCADE, related_name="certifications")`): Source enrollment record
  - `trainee` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quality_competency_certifications")`): Certified employee
  - `course` (`ForeignKey("quality.QualityTrainingCourse", on_delete=models.CASCADE, related_name="certifications")`): Completed training course
  - `competency_matrix` (`ForeignKey("quality.CompetencyMatrix", null=True, blank=True, related_name="certifications")`): Governing competency matrix
  - `certification_name` (`CharField(255)`): Official qualification title (e.g. "Certified Cleanroom Aseptic Operator", "Qualified HPLC Analyst - Level 2")
  - `qualification_level` (`CharField(32)`): `level_1_provisional` (Level 1: Provisional / Supervised Operator), `level_2_independent` (Level 2: Qualified Independent Operator), `level_3_senior` (Level 3: Senior Specialist / Lead), `level_4_trainer` (Level 4: Certified Trainer / Evaluator)
  - `issue_date` (`DateField`): Date certification was issued
  - `valid_until` (`DateField(null=True, blank=True)`): Expiration date (null if perpetual)
  - `renewal_interval_months` (`PositiveIntegerField(default=12)`): Recertification cycle interval in months
  - `status` (`CharField(24)`): `active`, `expiring_soon`, `expired`, `suspended`, `revoked`, `superseded`
  - `certified_by` (`ForeignKey(settings.AUTH_USER_MODEL, related_name="issued_competency_certifications")`): Authorizing quality authority or department manager
  - `electronic_signature` (`ForeignKey("quality.ElectronicSignatureRecord", null=True, blank=True, related_name="issued_certifications")`): 21 CFR Part 11 approval signature
  - `suspension_reason` (`TextField(blank=True)`): Reason if certification is suspended or revoked (e.g. quality deviation, process change)
  - `certificate_hash` (`CharField(64, blank=True)`): Tamper-evident cryptographic verification digest for audit inspection
  - `remarks` (`TextField(blank=True)`): Certification scope boundaries, authorized work centers, or cleanroom suites
- **Properties / Methods:**
  - `is_valid`: Boolean indicating whether status is active and certificate has not passed `valid_until`.
  - `days_to_expiration`: Days remaining before expiration (negative if expired).
  - `is_expiring_soon`: Boolean indicating whether expiration is within next 30 days.
- **Verified FKs:** `core.Tenant`, `quality.TrainingEnrollment`, `accounts.User`, `quality.QualityTrainingCourse`, `quality.CompetencyMatrix`, `quality.ElectronicSignatureRecord`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Document Authoring, Approval & DCO Change Control** (`ControlledDocument`, `DocumentChangeOrder`, `ElectronicSignatureRecord`) → Sub-module 12.1 (Document Control & Management).
- **Design Verification & Design Transfer Reviews** (`DesignProject`, `DesignVerification`) → Sub-module 12.2 (Design Controls & Development).
- **CAPA Investigations & Root Cause Analyses** (`CapaInvestigation`, `RootCauseAnalysis`, `CapaAction`) → Sub-module 12.4 (Corrective & Preventive Action).
- **Material Non-Conformance & Quarantine Containment** (`NonConformanceReport`, `QuarantineContainment`, `MrbDisposition`) → Sub-module 12.5 (Non-Conformance & Deviation Management).
- **Supplier Qualification & Vendor Audits** (`SupplierQualificationAudit`, `SupplierQualityScorecard`) → Sub-module 12.6 (Supplier & Vendor Quality Management).
- **Inspection Protocols IQC/IPQC/FQC** (`IncomingInspectionLot`, `InProcessInspection`, `FinalInspectionLot`) → Sub-modules 12.7, 12.8, 12.9.
- **Equipment Calibration & Gage R&R MSA** (`CalibrationGage`, `CalibrationRecord`, `MeasurementSystemAnalysis`) → Sub-module 12.10 (Calibration & MSA).
- **Internal Quality Audits & Inspection Room Hosting** (`AuditProgram`, `QualityAudit`, `AuditFinding`, `RegulatoryInspectionHost`) → Sub-module 12.11 (Audit Management).
- **Customer Complaint Handling & Medical Device Vigilance** (`Complaint`, `MDR`) → Sub-module 12.13 (Customer Complaint Handling).
- **General HR Corporate Onboarding, Benefits, Payroll, & Non-GxP Training** → Module 3 (Human Resource Management / HRM 3.19 & 3.20).

---

## Deferred (later passes / integrations)

- **Interactive SCORM / xAPI / cmi5 In-Browser Video Player Engine:** Interactive multimedia course playback engine; course records and completion scoring are fully modeled in 12.12 now.
- **Direct Exchange / Google Calendar Webhooks:** Real-time push syncing to corporate calendars; session dates, times, and deadlines are tracked directly in NavERP.
- **Automated AI Quiz Question Generator (CQ.AI style):** Generative AI prompt pipeline to extract multiple-choice quizzes from uploaded PDF SOPs; syllabus and question criteria fields are modeled now.
- **Physical Cleanroom RFID Badge Access Gate Integration:** Hardware turnstile integration blocking door access if operator training is expired; the `is_user_qualified` helper method is implemented in 12.12 now to provide the backend authorization decision.
