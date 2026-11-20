# Research — Sub-module 12.14: Management Review & Quality Planning (Module 12 — Quality Management System, `quality`)

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
  - `"12.9"` (Final Quality Control / OQC):
    - `"Final Inspection Protocols": "quality:final_inspection_lot_list"`
    - `"Lot Sampling & Acceptance Testing": "quality:oqc_hold_board"`
    - `"Certificate of Conformance (CoC)": "quality:certificate_of_conformance_list"`
    - `"Packaging & Labeling Verification": "quality:packaging_label_verification_list"`
    - `"Shipment Release & Traceability": "quality:quality_release_authorization_list"`
  - `"12.10"` (Calibration & Measurement System Analysis):
    - `"Calibration Schedule & Planning": "quality:calibration_gage_list"`
    - `"Calibration Execution & Records": "quality:calibration_record_list"`
    - `"Out-of-Tolerance (OOT) Handling": "quality:out_of_tolerance_investigation_list"`
    - `"Measurement System Analysis (MSA / Gage R&R)": "quality:measurement_system_analysis_list"`
    - `"Calibration Vendor Management": "quality:calibration_vendor_directory"`
  - `"12.11"` (Audit Management):
    - `"Audit Program Planning": "quality:audit_program_list"`
    - `"Audit Execution & Checklists": "quality:quality_audit_list"`
    - `"Audit Findings & Reporting": "quality:audit_finding_list"`
    - `"Corrective Action Tracking": "quality:audit_action_tracker"`
    - `"Regulatory & Certification Audits": "quality:regulatory_inspection_host_list"`
  - `"12.12"` (Training & Competency Management):
    - `"Training Needs Analysis": "quality:competency_matrix_list"`
    - `"Course Development & Delivery": "quality:training_course_list"`
    - `"Training Scheduling & Enrollment": "quality:training_enrollment_list"`
    - `"Competency Assessment & Certification": "quality:competency_certification_list"`
    - `"Training Records & Compliance": "quality:training_compliance_dashboard"`
  - `"12.13"` (Customer Complaint Handling):
    - `"Complaint Intake & Triage": "quality:customer_complaint_list"`
    - `"Investigation & Root Cause Analysis": "quality:complaint_investigation_list"`
    - `"Regulatory Reporting & Vigilance": "quality:regulatory_report_list"`
    - `"Field Action & Recall Management": "quality:field_action_list"`
    - `"Complaint Trending & Closure": "quality:complaint_trending_dashboard"`

- **Sibling models available to FK in `apps/quality/models/`:**
  - `QualityAudit` (`apps/quality/models/AuditManagement/QualityAudits.py:9`, prefix `QAUD`): Internal, external, and certification audit records reviewed during management reviews.
  - `AuditFinding` (`apps/quality/models/AuditManagement/AuditFindings.py:10`, prefix `QFND`): Specific non-conformances identified in audits presented as review inputs.
  - `CapaInvestigation` (`apps/quality/models/CapaManagement/CapaInvestigations.py:8`, prefix `QCAP`): Corrective and preventive actions; already includes `("management_review", "Management Review Action")` in `SOURCE_TYPE_CHOICES`.
  - `NonConformanceReport` (`apps/quality/models/NonConformance/NonConformanceReports.py:10`, prefix `QNCR`): Product/process non-conformance metrics and Pareto distributions.
  - `CustomerComplaint` (`apps/quality/models/CustomerComplaints/CustomerComplaints.py:8`, prefix `QCMP`): Customer complaint volume, severity trends, and reportability statistics.
  - `ElectronicSignatureRecord` (`apps/quality/models/DocumentControl/ElectronicSignatures.py:10`, prefix `QSIG`): FDA 21 CFR Part 11 compliant digital signatures; includes `("management_approval", "Management / Executive Authorization")` in `MEANING_CHOICES`.
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py:8`, prefix `QDOC`): Quality manual, quality policy, and SOPs evaluated for continuing adequacy.
  - `DocumentChangeOrder` (`apps/quality/models/DocumentControl/DocumentChangeOrders.py:9`, prefix `QDCR`): QMS documentation modifications triggered by management review outputs.
  - `RiskAssessment` (`apps/quality/models/RiskManagement/RiskAssessments.py:7`, prefix `QRSK`): Product and process risk profile changes and residual risk acceptability.
  - `SupplierQualityScorecard` (`apps/quality/models/SupplierQuality/SupplierQualityScorecards.py:11`, prefix `QSSC`): Approved vendor list (AVL) health and supplier performance ratings.
  - `TrainingEnrollment` (`apps/quality/models/TrainingCompetency/TrainingEnrollments.py:9`, prefix `QENR`): Workforce competency and regulatory training compliance percentages.

- **Cross-module spine models available to FK:**
  - `core.Tenant` (`apps/core/models/Tenant.py:17`): Multi-tenant isolation foundation.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:5`): Internal departments, quality units, manufacturing sites, and business divisions.
  - `core.Party` (`apps/core/models/Party.py:5`) & `core.PartyRole` (`apps/core/models/PartyRole.py:5`): Key stakeholders, external certification bodies, and suppliers.
  - `accounts.User` (`apps/accounts/models.py:52`): Executive management, quality managers, facilitators, and action assignees.
  - `core.AuditLog` (`apps/core/models/AuditLog.py:5` + `write_audit_log` helper): Immutable audit trail for FDA 21 CFR Part 11 and QMSR compliance.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and atomic collision retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Business division, quality department, or site ownership. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | Executive sponsors, meeting facilitators, action assignees. |
| `core.Party` exists | `apps/core/models/Party.py:5` -> `class Party(models.Model)` | External entities, registrars, and corporate partners. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable audit trail for FDA 21 CFR Part 11 & QMSR inspections. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | Quality policy and high-level manual reviewed during meetings. |
| `quality.CapaInvestigation` exists | `apps/quality/models/CapaManagement/CapaInvestigations.py:8` | CAPA status input & target for spawned corrective actions. |
| `quality.QualityAudit` exists | `apps/quality/models/AuditManagement/QualityAudits.py:9` | Audit program results and finding counts reviewed by leadership. |
| `quality.NonConformanceReport` exists | `apps/quality/models/NonConformance/NonConformanceReports.py:10` | Scrap, rework, and deviation metrics compiled as review inputs. |
| `quality.CustomerComplaint` exists | `apps/quality/models/CustomerComplaints/CustomerComplaints.py:8` | Complaint rates, adverse events, and customer satisfaction inputs. |
| `quality.ElectronicSignatureRecord` exists | `apps/quality/models/DocumentControl/ElectronicSignatures.py:10` | Executive approval sign-off manifest per 21 CFR Part 11. |

### Spine entities verified NOT to exist (or unbuilt in Module 12 / ERP)

- **Module 5 unbuilt masters (`Item`, `LotSerial`, `UOM`):** When strategic quality objectives relate to specific product lines, free-text identifier fields (`product_family`, `target_metric_label`) are used, maintaining loose coupling without hard FKs to unbuilt inventory tables.
- **Automated Live Presentation Slide Deck Engine (e.g. PPTX generation):** Live meeting decks are supported through audit-ready PDF/HTML minutes packages and HTMX presentation summaries, deferring heavy external presentation generator integrations to later iterations.

### Auto-number Prefix Collision Check (0 collisions verified)

Automated ripgrep scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QOBJ` (Quality Objective) -> **0 collisions** (Completely free)
- `QMRV` (Quality Management Review Meeting) -> **0 collisions** (Completely free)
- `QMRI` (Management Review Input Item) -> **0 collisions** (Completely free)
- `QMRA` (Management Review Action Item) -> **0 collisions** (Completely free)

---

## Leaders surveyed (with source links)

1. **MasterControl Quality Excellence (Management Review & Quality Event Management)** — Leading life sciences eQMS platform designed for FDA 21 CFR Part 820 / QMSR and ISO 13485:2016. Automates the aggregation of quality data required for management review from connected modules (CAPA, nonconformance, audits, customer complaints, supplier scorecards). Features standardized pre-meeting agenda formulation, stakeholder distribution, in-meeting live recording of discussion logs, executive action item assignment, and 21 CFR Part 11 compliant e-signature sign-off.
   - *Source:* https://www.mastercontrol.com/quality/management-review/
2. **Veeva Vault QMS (Management Review & Quality Metrics)** — Cloud-native quality management suite for life sciences and medical devices. Features structured review workflows, real-time quality metrics dashboards that serve as living inputs for periodic reviews, executive sign-off workflows, unified action item tracking across the QMS (direct escalation to CAPA, change control, or SOP revisions), and periodic review cadence scheduling.
   - *Source:* https://www.veeva.com/products/vault-qms/
3. **Sparta Systems TrackWise Digital (Quality Review & Oversight / TrackWise AI)** — Enterprise quality governance platform for global pharmaceutical and medical device manufacturers. Features multi-site data rollup, automated input packaging (aggregating audit findings, open deviations, supplier scorecards, CAPA effectiveness rates), management review cadence management, meeting minutes & attendee logging, review action item management with automated escalation and SLA tracking.
   - *Source:* https://www.spartasystems.com/trackwise-digital/quality-oversight/
4. **ETQ Reliance (Management Review & Quality Objectives / Planning)** — Configurable enterprise quality management platform widely used in aerospace, medical devices, and discrete manufacturing. Provides a configurable agenda builder aligned with ISO 9001:2015 Clause 9.3 and ISO 13485:2016 Clause 5.6. Automates data rollups from inspections, audits, CAPAs, and complaints. Features a dedicated Quality Objectives module tracking SMART goals, target vs actual, and RAG (Red/Amber/Green) status.
   - *Source:* https://www.etq.com/management-review-software/
5. **Greenlight Guru (Medical Device Management Review)** — Purpose-built MedTech QMS aligned strictly with ISO 13485:2016 Clause 5.6, FDA QMSR, and EU MDR/IVDR. Pre-structured review templates cover all mandatory Clause 5.6.2 inputs (complaints, CAPAs, audits, supplier evaluations, post-market surveillance). Directly links review outputs to Design History Files, risk management files, and continuous improvement initiatives, backed by management e-signatures.
   - *Source:* https://www.greenlight.guru/medical-device-management-review-software
6. **Qualio (Management Review & Quality Analytics)** — Agile cloud eQMS for life sciences scaleups. Features automated quality reporting compiling document approvals, training compliance rates, audit findings, and open CAPAs. Collaborative agenda and minutes logging, task delegation with due dates, and executive signature approval.
   - *Source:* https://www.qualio.com/product/management-review
7. **Dot Compliance (eQMS Management Review & Objectives)** — Ready-to-use QMS on Salesforce Life Sciences cloud. Real-time executive dashboards, objective tracking against corporate quality policy, audit trail, 21 CFR Part 11 electronic signatures, and action item tracking with automated task notifications.
   - *Source:* https://www.dotcompliance.com/solutions/management-review/
8. **ComplianceQuest (Executive Management Review & Quality Planning)** — AI-powered enterprise QMS natively built on Salesforce. Automated agenda generation mapping to ISO 9001, ISO 13485, and IATF 16949 standards. Direct connection to CRM, ERP, and QMS data. Quality Objectives & KPI planning with balanced scorecards. Action item parent-child linkage to CAPA or Change Control, executive review package export (audit-ready briefing package).
   - *Source:* https://www.compliancequest.com/management-review-software/

---

## Regulatory Alignment: The QMSR Revolution

Under the FDA's **Quality Management System Regulation (QMSR)** (which harmonized 21 CFR Part 820 with ISO 13485:2016, effective February 2026):
1. **Elimination of the Inspection Shield**: Under legacy 21 CFR § 820.180(c), management review reports and internal audits were exempt from routine FDA inspection. **Under QMSR, that exemption is eliminated.** FDA investigators operating under Compliance Program CP 7382.850 can inspect Management Review records, minutes, action items, executive suitability conclusions, and quality planning records directly.
2. **Mandatory Standardized Inputs (ISO 13485:2016 § 5.6.2 / ISO 9001:2015 § 9.3.2)**: Review agendas must systematically evaluate:
   - Feedback (including customer complaints & post-market surveillance)
   - Complaint handling & reporting to regulatory authorities
   - Audit results (internal, supplier, and regulatory)
   - Process performance and product conformity (scrap, rework, OOT)
   - Status of corrective and preventive actions (CAPA)
   - Follow-up actions from previous management reviews
   - Changes that could affect the QMS (regulatory, organizational, statutory)
   - Recommendations for improvement
3. **Mandatory Standardized Outputs (ISO 13485:2016 § 5.6.3 / ISO 9001:2015 § 9.3.3)**: Management reviews must record decisions and actions regarding:
   - Improvements needed to maintain the suitability, adequacy, and effectiveness of the QMS
   - Improvements to product safety and performance related to customer requirements
   - Resource needs (budget, equipment, staffing, infrastructure)
   - Revisions to quality objectives, policies, and quality plans
4. **Executive Management Responsibility & Part 11 Signatures**: Management with executive responsibility must formally sign off on the review records and suitability conclusions using 21 CFR Part 11 compliant electronic signatures.

---

## Feature catalog (this sub-module only)

### 1. Management Review Scheduling
- **Multi-Cadence Meeting Scheduling** — Schedule reviews across Annual, Semi-Annual, Quarterly, Monthly, or Event-Driven / Urgent cadences with start/end review period bounds · seen in: *All leaders (MasterControl, Veeva, TrackWise, ETQ, Greenlight Guru)* · priority: `table-stakes` · spine: new table `ManagementReview` (`QMRV`) · buildable now.
- **Formal Review Lifecycle Workflow** — Status transition through Scheduled -> In Preparation -> Meeting in Progress -> Minutes Drafting -> Pending Executive Approval -> Approved / Closed -> Cancelled · seen in: *Veeva Vault, MasterControl, TrackWise* · priority: `table-stakes` · spine: status choices in `ManagementReview` · buildable now.
- **Executive Leadership & Facilitator Designation** — Formal assignment of Executive Sponsor (Management with Executive Responsibility) and Lead Quality Facilitator · seen in: *Greenlight Guru, ETQ, MasterControl* · priority: `table-stakes` · spine: FKs to `accounts.User` in `ManagementReview` · buildable now.
- **Attendee Tracking & Quorum Verification** — Logging of required attendees, department representation, attendance status (Present, Excused, Absent), and quorum confirmation · seen in: *TrackWise Digital, MasterControl, ETQ* · priority: `common` · spine: text/JSON attendee roster in `ManagementReview` · buildable now.
- **Calendar & Notice Distribution** — Generation of scheduled meeting invitations, notification logs, and agenda distribution timestamps · seen in: *Qualio, Dot Compliance* · priority: `common` · spine: fields in `ManagementReview` · buildable now.

### 2. Quality Objectives & KPIs
- **SMART Objective Definition & Policy Alignment** — Definition of specific, measurable, achievable, relevant, and time-bound quality goals aligned with corporate Quality Policy per ISO 9001 Clause 6.2 and ISO 13485 Clause 5.4.1 · seen in: *ETQ Reliance, ComplianceQuest, MasterControl* · priority: `table-stakes` · spine: new table `QualityObjective` (`QOBJ`) · buildable now.
- **Objective Categorization & Hierarchy** — Structured classification into Product Quality, Process Performance, Regulatory Compliance, Customer Satisfaction, Supplier Quality, and Safety & Environmental · seen in: *ETQ Reliance, ComplianceQuest* · priority: `table-stakes` · spine: choices in `QualityObjective` · buildable now.
- **Target vs. Actual Metric Tracking** — Tracking of baseline value, target goal value, current actual value, unit of measure, and evaluation frequency (monthly, quarterly, annual) · seen in: *All leaders (ETQ, ComplianceQuest, Qualio, Veeva)* · priority: `table-stakes` · spine: fields in `QualityObjective` · buildable now.
- **Dynamic RAG Status & Performance Badging** — Visual Red/Amber/Green (On Track, At Risk, Behind, Achieved) performance indicator calculating variance between actual and target metrics · seen in: *ETQ Reliance, Dot Compliance, TrackWise* · priority: `table-stakes` · spine: choices and badge styling in `QualityObjective` · buildable now.
- **Departmental / OrgUnit Goal Cascading** — Assignment of objectives to specific business units, production sites, or functional departments (`core.OrgUnit`) with individual user ownership · seen in: *ComplianceQuest, ETQ Reliance* · priority: `common` · spine: FK to `core.OrgUnit` and `accounts.User` in `QualityObjective` · buildable now.

### 3. Review Inputs & Data Compilation (Clause 5.6.2 / 9.3.2)
- **Structured Regulatory Input Categorization** — Hardened classification matching ISO 13485:2016 § 5.6.2 and ISO 9001:2015 § 9.3.2:
  1. Internal & External Audit Results
  2. Customer Feedback & Complaints
  3. Process Performance & Product Conformity
  4. Status of Corrective & Preventive Actions (CAPA)
  5. Follow-Up Actions from Prior Management Reviews
  6. Changes Affecting the QMS & Regulatory Updates
  7. Supplier Performance & AVL Status
  8. Resource Adequacy & Training Competency
  9. Risk Management & Hazard Review
  10. Other Quality Matters
  · seen in: *All leaders (MasterControl, Greenlight Guru, Veeva Vault, ETQ Reliance)* · priority: `table-stakes` · spine: new table `ManagementReviewInput` (`QMRI`) · buildable now.
- **Direct Sibling Module Entity Linkage** — Traceable FK linkages from input agenda items directly to source records:
  - Linked Audit: `quality.QualityAudit`
  - Linked CAPA: `quality.CapaInvestigation`
  - Linked Complaint: `quality.CustomerComplaint`
  - Linked NCR: `quality.NonConformanceReport`
  · seen in: *MasterControl, Veeva Vault, Greenlight Guru, TrackWise* · priority: `differentiator` · spine: FKs in `ManagementReviewInput` · buildable now.
- **Data Trend Summary & Analysis Compilation** — Detailed narrative compilation of performance metrics, failure rates, defect trends, and analysis presented to executive management · seen in: *MasterControl, Qualio, Dot Compliance* · priority: `table-stakes` · spine: fields in `ManagementReviewInput` · buildable now.
- **Presentation Order & Presenter Assignment** — Designation of item presenter (`accounts.User`) and sequence ordering for review meeting agenda · seen in: *ETQ Reliance, TrackWise Digital* · priority: `common` · spine: fields in `ManagementReviewInput` · buildable now.

### 4. Management Review Outputs & Decisions (Clause 5.6.3 / 9.3.3)
- **Structured Action Item Creation** — Action items generated directly from review findings categorized by output type: QMS Continual Improvement, Product Safety / Quality Improvement, Resource Allocation, CAPA Initiation, Process Change, Policy/Objective Revision · seen in: *All leaders (MasterControl, Veeva Vault, TrackWise, Greenlight Guru, ETQ)* · priority: `table-stakes` · spine: new table `ManagementReviewAction` (`QMRA`) · buildable now.
- **Action Accountability & Due Date Tracking** — Assignee ownership (`accounts.User`), priority level (Critical, High, Medium, Low), target due date, and completion date · seen in: *All leaders* · priority: `table-stakes` · spine: fields in `ManagementReviewAction` · buildable now.
- **Closed-Loop Escalation to CAPA & Document Change Control** — Direct one-click spawning or linkage of actions to formal `quality.CapaInvestigation` (with source `management_review`) or `quality.DocumentChangeOrder` · seen in: *MasterControl, Veeva Vault, TrackWise Digital* · priority: `differentiator` · spine: FKs to `quality.CapaInvestigation` and `quality.DocumentChangeOrder` in `ManagementReviewAction` · buildable now.
- **Action Verification & Independent QA Closeout** — Independent verification of action implementation effectiveness by quality authority prior to formal action closure · seen in: *Greenlight Guru, MasterControl, ETQ Reliance* · priority: `table-stakes` · spine: verification fields in `ManagementReviewAction` · buildable now.

### 5. Quality Planning & Continuous Improvement
- **Executive QMS Suitability & Effectiveness Conclusion** — Formal recorded verdict by executive leadership determining whether the QMS is:
  - *Suitable, Adequate, and Effective*
  - *Effective with Minor Improvement Opportunities*
  - *Inadequate / Requiring Systemic Remediation*
  · seen in: *All leaders (Greenlight Guru, MasterControl, Veeva, ETQ)* · priority: `table-stakes` · spine: choices and narrative field in `ManagementReview` · buildable now.
- **Resource Allocation & Budget Decisions** — Documented executive commitments for personnel staffing, manufacturing equipment, laboratory software/hardware, and facility infrastructure investments · seen in: *MasterControl, ETQ Reliance, Greenlight Guru* · priority: `table-stakes` · spine: fields in `ManagementReview` and `ManagementReviewAction` · buildable now.
- **Meeting Minutes Compilation & Distribution** — Complete compilation of review proceedings, executive discussion notes, inputs presented, and decisions rendered, formatted into an audit-ready minutes package · seen in: *All leaders* · priority: `table-stakes` · spine: fields in `ManagementReview` · buildable now.
- **Balanced Quality Scorecard Dashboard** — Rollup analytics view displaying Quality Objective attainment rates, action item closure percentages, review meeting cadence adherence, and open CAPA trends · seen in: *ComplianceQuest, ETQ Reliance, Dot Compliance* · priority: `common` · spine: view & template `quality_planning_dashboard` · buildable now.

### 6. Beyond the Bullets
- **FDA 21 CFR Part 11 Electronic Signature Approval Manifest** — Cryptographic digital sign-off by Management with Executive Responsibility binding signer, legal title, timestamp, and meaning (`management_approval`) using `quality.ElectronicSignatureRecord` · seen in: *MasterControl, Veeva Vault, Sparta TrackWise* · priority: `differentiator` · spine: FK to `quality.ElectronicSignatureRecord` in `ManagementReview` · buildable now.
- **QMSR Audit-Ready Briefing Export Package** — One-click consolidated audit dossier formatting review metadata, attendee logs, input summaries, suitability conclusions, and action items for immediate presentation to FDA investigators or ISO registrars · seen in: *Greenlight Guru, MasterControl, ComplianceQuest* · priority: `differentiator` · spine: export view / printable summary view · buildable now.
- **Action Overdue Visual Urgency Badging** — Dynamic overdue indicators (`badge-red` when past due date, `badge-amber` when within 7 days, `badge-green` when completed) · seen in: *TrackWise Digital, Qualio* · priority: `common` · spine: properties on `ManagementReviewAction` · buildable now.

---

## Recommended build scope (this pass — 4 models)

### Model 1: `QualityObjective` [NUMBER_PREFIX = "QOBJ"]
- **Purpose**: Primary entity capturing strategic quality goals, KPI metrics, target-vs-actual progress, and departmental balanced scorecards per ISO 9001:2015 Clause 6.2 and ISO 13485:2016 Clause 5.4.1.
- **Fields & Choices**:
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QOBJ`)
  - `title` (`CharField(255)`): Concise objective statement (e.g. "Maintain First Pass Inspection Yield >= 98.5%")
  - `description` (`TextField`): Detailed description of objective rationale and calculation methodology
  - `category` (`CharField(32)`):
    - `product_quality` ("Product Quality & Safety")
    - `process_performance` ("Process Performance & Operational Yield")
    - `compliance_regulatory` ("Regulatory Compliance & Audit Performance")
    - `customer_satisfaction` ("Customer Satisfaction & Complaint Reduction")
    - `supplier_quality` ("Supplier Quality & Incoming Acceptance")
    - `safety_environmental` ("Safety & Environmental Compliance")
    - `continuous_improvement` ("Continuous Improvement & Cost of Quality")
  - `period_year` (`PositiveIntegerField`): Operational planning year (e.g. 2026)
  - `cadence` (`CharField(20)`): `monthly` ("Monthly"), `quarterly` ("Quarterly"), `semi_annual` ("Semi-Annual"), `annual` ("Annual")
  - `metric_unit` (`CharField(50)`): Unit of measure (e.g. "%", "PPM", "Days", "Count", "USD")
  - `baseline_value` (`DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`): Historical starting baseline
  - `target_value` (`DecimalField(max_digits=12, decimal_places=3)`): Target goal threshold
  - `current_value` (`DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)`): Latest measured value
  - `target_direction` (`CharField(20)`): `higher_better` ("Higher is Better (>= Target)"), `lower_better` ("Lower is Better (<= Target)"), `exact` ("Exact Target")
  - `status` (`CharField(20)`): `draft` ("Draft"), `active` ("Active"), `on_track` ("On Track"), `at_risk` ("At Risk"), `behind` ("Behind Target"), `achieved` ("Achieved"), `abandoned` ("Abandoned")
  - `rag_status` (`CharField(10)`): `green` ("Green - On Track"), `amber` ("Amber - At Risk"), `red` ("Red - Critical Variance"), `neutral` ("Not Measured")
  - `owner` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quality_objectives")`): Responsible individual
  - `org_unit` (`ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_objectives")`): Owning department/site
  - `target_date` (`DateField(null=True, blank=True)`): Target completion / achievement deadline
  - `last_evaluated_date` (`DateField(null=True, blank=True)`): Date current value was last updated
  - `action_plan_summary` (`TextField(blank=True)`): Operational initiative to achieve objective
  - `notes` (`TextField(blank=True)`)
- **Properties & Methods**:
  - `variance`: Difference between `current_value` and `target_value`.
  - `is_achieved`: Boolean evaluating achievement based on `target_direction`.
- **Constraints & Indexes (<= 30 chars)**:
  - `models.UniqueConstraint(fields=["tenant", "number"], name="quality_qobj_ten_num_uniq")`
  - `models.Index(fields=["tenant", "status"], name="idx_qobj_ten_status")`
  - `models.Index(fields=["tenant", "category"], name="idx_qobj_ten_cat")`
  - `models.Index(fields=["tenant", "period_year"], name="idx_qobj_ten_year")`
  - `models.Index(fields=["tenant", "rag_status"], name="idx_qobj_ten_rag")`
  - `models.Index(fields=["tenant", "-created_at"], name="idx_qobj_ten_created")`

### Model 2: `ManagementReview` [NUMBER_PREFIX = "QMRV"]
- **Purpose**: Formal review cycle and executive meeting record capturing agenda planning, attendance, proceedings, suitability evaluations, and Part 11 executive authorization.
- **Fields & Choices**:
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QMRV`)
  - `title` (`CharField(255)`): Review cycle title (e.g. "Q1 2026 Executive Management Review")
  - `cadence` (`CharField(20)`): `annual` ("Annual Review"), `semi_annual` ("Semi-Annual Review"), `quarterly` ("Quarterly Review"), `monthly` ("Monthly Quality Review"), `event_driven` ("Event-Driven / Special Review")
  - `period_start` (`DateField`): Start of performance period under review
  - `period_end` (`DateField`): End of performance period under review
  - `scheduled_date` (`DateField`): Planned meeting date
  - `actual_meeting_date` (`DateField(null=True, blank=True)`): Actual meeting date
  - `location` (`CharField(255, blank=True)`): Conference room or virtual meeting link
  - `executive_sponsor` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sponsored_management_reviews")`): Management with Executive Responsibility
  - `lead_facilitator` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="facilitated_management_reviews")`): Quality manager / facilitator
  - `org_unit` (`ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="management_reviews")`): Facility or enterprise scope
  - `attendees_roster` (`TextField(blank=True)`): Documented attendee list, titles, and departments
  - `quorum_met` (`BooleanField(default=True)`): Whether quorum requirements were satisfied
  - `status` (`CharField(25)`): `scheduled` ("Scheduled"), `in_preparation` ("Input Preparation"), `meeting_active` ("Meeting In Progress"), `minutes_drafting` ("Minutes & Outputs Drafting"), `pending_approval` ("Pending Executive Approval"), `approved` ("Executive Approved / Closed"), `cancelled` ("Cancelled")
  - `qms_suitability_conclusion` (`CharField(32)`):
    - `pending` ("Evaluation Pending")
    - `suitable_effective` ("Suitable, Adequate & Fully Effective")
    - `minor_improvements` ("Adequate with Minor Opportunities for Improvement")
    - `systemic_deficiencies` ("Inadequate / Systemic Deficiencies Identified")
  - `executive_summary` (`TextField(blank=True)`): High-level executive narrative and evaluation
  - `minutes_discussion` (`TextField(blank=True)`): Detailed meeting discussion notes and findings
  - `resource_decisions` (`TextField(blank=True)`): Decisions regarding budget, personnel, and infrastructure
  - `electronic_signature` (`ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="management_reviews")`): Part 11 sign-off record
  - `approved_by` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_management_reviews")`)
  - `approved_at` (`DateTimeField(null=True, blank=True)`)
  - `notes` (`TextField(blank=True)`)
- **Properties & Methods**:
  - `total_inputs_count`: Number of compiled input topics.
  - `total_actions_count`: Number of spawned action items.
  - `open_actions_count`: Number of unresolved action items.
  - `is_overdue`: Boolean indicating whether scheduled meeting date is past and meeting has not occurred.
- **Constraints & Indexes (<= 30 chars)**:
  - `models.UniqueConstraint(fields=["tenant", "number"], name="quality_qmrv_ten_num_uniq")`
  - `models.Index(fields=["tenant", "status"], name="idx_qmrv_ten_status")`
  - `models.Index(fields=["tenant", "cadence"], name="idx_qmrv_ten_cad")`
  - `models.Index(fields=["tenant", "scheduled_date"], name="idx_qmrv_ten_schdate")`
  - `models.Index(fields=["tenant", "suitability"], name="idx_qmrv_ten_suit")`
  - `models.Index(fields=["tenant", "-created_at"], name="idx_qmrv_ten_created")`

### Model 3: `ManagementReviewInput` [NUMBER_PREFIX = "QMRI"]
- **Purpose**: Structured input data compilation, agenda topics, and performance summaries per ISO 13485:2016 § 5.6.2 and ISO 9001:2015 § 9.3.2.
- **Fields & Choices**:
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QMRI`)
  - `management_review` (`ForeignKey("quality.ManagementReview", on_delete=models.CASCADE, related_name="inputs")`): Parent review cycle
  - `agenda_order` (`PositiveIntegerField(default=1)`): Presentation sequence number
  - `title` (`CharField(255)`): Agenda topic title (e.g. "Q1 Internal & Supplier Audit Summary")
  - `category` (`CharField(32)`):
    - `audit_results` ("1. Audit Results (Internal, Supplier, Regulatory)")
    - `customer_feedback` ("2. Customer Feedback & Complaint Trends")
    - `process_conformity` ("3. Process Performance & Product Conformity")
    - `capa_status` ("4. Status of Corrective & Preventive Actions (CAPA)")
    - `prior_review_followup` ("5. Follow-Up Actions from Prior Reviews")
    - `changes_affecting_qms` ("6. Regulatory Changes & QMS System Updates")
    - `supplier_performance` ("7. Supplier Performance & AVL Status")
    - `resources_training` ("8. Resource Adequacy & Training Competency")
    - `risk_management` ("9. Risk Management & Hazard Review")
    - `other_business` ("10. Other Quality Matters")
  - `summary_findings` (`TextField`): Comprehensive synthesis of data, trends, and compliance metrics
  - `metrics_data` (`TextField(blank=True)`): Tabular or structured numerical metrics summary
  - `status` (`CharField(20)`): `draft` ("Draft"), `compiled` ("Data Compiled"), `presented` ("Presented in Review"), `accepted` ("Accepted by Management")
  - `presenter` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="presented_review_inputs")`): Presenting specialist
  - `linked_audit` (`ForeignKey("quality.QualityAudit", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_inputs")`)
  - `linked_capa` (`ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_inputs")`)
  - `linked_complaint` (`ForeignKey("quality.CustomerComplaint", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_inputs")`)
  - `linked_ncr` (`ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="review_inputs")`)
  - `attachments_summary` (`CharField(255, blank=True)`): Reference to external slide deck or data package
  - `notes` (`TextField(blank=True)`)
- **Constraints & Indexes (<= 30 chars)**:
  - `models.UniqueConstraint(fields=["tenant", "number"], name="quality_qmri_ten_num_uniq")`
  - `models.Index(fields=["tenant", "management_review"], name="idx_qmri_ten_mrv")`
  - `models.Index(fields=["tenant", "category"], name="idx_qmri_ten_cat")`
  - `models.Index(fields=["tenant", "status"], name="idx_qmri_ten_status")`
  - `models.Index(fields=["tenant", "-created_at"], name="idx_qmri_ten_created")`

### Model 4: `ManagementReviewAction` [NUMBER_PREFIX = "QMRA"]
- **Purpose**: Concrete output decisions, resource commitments, continual improvement initiatives, and assigned tasks per ISO 13485:2016 § 5.6.3 and ISO 9001:2015 § 9.3.3.
- **Fields & Choices**:
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QMRA`)
  - `management_review` (`ForeignKey("quality.ManagementReview", on_delete=models.CASCADE, related_name="actions")`): Originating review cycle
  - `title` (`CharField(255)`): Action headline (e.g. "Procure automated vision inspection system for Line 3")
  - `action_type` (`CharField(32)`):
    - `qms_improvement` ("QMS Continual Improvement")
    - `product_improvement` ("Product Quality / Safety Enhancement")
    - `resource_allocation` ("Resource & Infrastructure Allocation")
    - `capa_initiation` ("Formal CAPA Initiation")
    - `procedure_revision` ("SOP / Quality Plan Revision")
    - `training_competency` ("Training & Education Initiative")
    - `regulatory_filing` ("Regulatory Notification / Filing")
  - `priority` (`CharField(20)`): `critical` ("Critical"), `high` ("High"), `medium` ("Medium"), `low` ("Low")
  - `description` (`TextField`): Action requirements and implementation scope
  - `assignee` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_management_actions")`): Task owner
  - `due_date` (`DateField`): Target completion deadline
  - `status` (`CharField(25)`): `open` ("Open"), `in_progress` ("In Progress"), `pending_verification` ("Pending QA Verification"), `completed` ("Verified & Closed"), `cancelled` ("Cancelled / Superseded")
  - `budget_allocated` (`DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`): Authorized capital or operational expense
  - `spawned_capa` (`ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="spawned_management_actions")`)
  - `spawned_change_order` (`ForeignKey("quality.DocumentChangeOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="spawned_management_actions")`)
  - `completion_date` (`DateField(null=True, blank=True)`): Actual completion date
  - `resolution_summary` (`TextField(blank=True)`): Narrative explaining how action was implemented
  - `verified_by` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_management_actions")`)
  - `verification_notes` (`TextField(blank=True)`): Independent evidence that action was effective
  - `notes` (`TextField(blank=True)`)
- **Properties & Methods**:
  - `is_overdue`: True if active and past `due_date`.
  - `days_open`: Total elapsed days from creation to completion.
- **Constraints & Indexes (<= 30 chars)**:
  - `models.UniqueConstraint(fields=["tenant", "number"], name="quality_qmra_ten_num_uniq")`
  - `models.Index(fields=["tenant", "management_review"], name="idx_qmra_ten_mrv")`
  - `models.Index(fields=["tenant", "status"], name="idx_qmra_ten_status")`
  - `models.Index(fields=["tenant", "priority"], name="idx_qmra_ten_pri")`
  - `models.Index(fields=["tenant", "due_date"], name="idx_qmra_ten_duedate")`
  - `models.Index(fields=["tenant", "-created_at"], name="idx_qmra_ten_created")`

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Detailed Failure Root Cause & 5-Why / Ishikawa Analysis** -> Belongs to 12.4 (`CapaManagement`). Management review actions escalate directly into `quality.CapaInvestigation` when systemic root-cause investigation is required.
- **Audit Scheduling & Finding Resolution** -> Belongs to 12.11 (`AuditManagement`). Audits feed into management reviews as input items; internal audit workflows remain in 12.11.
- **Engineering Change Orders & Drawing Redlines** -> Belongs to 12.1 (`DocumentControl`) & 12.2 (`DesignControls`). Management review outputs trigger `DocumentChangeOrder` records.
- **Process Validation IQ/OQ/PQ Protocols** -> Belongs to 12.15 (`ProcessValidation`). High-level validation planning decisions take place in 12.14, but validation execution and statistical capability studies reside in 12.15.

---

## Deferred (later passes / integrations)

- **Direct Live PowerPoint (PPTX) Deck Exporter**: While management review packages can be exported to audit-ready HTML/PDF dossiers and printed reports, direct dynamic generation of PowerPoint decks is deferred to external reporting integrations.
- **Automated Webhook Meeting Integration (Zoom / Microsoft Teams / Google Meet)**: Direct API integration to schedule conference room calls or synchronize calendars is an external service integration; meetings currently record web URLs and calendar details directly.
- **Statistical SPC Metric Live Sync**: Real-time automated querying of IPQC/IQC SPC databases for chart rendering inside management reviews is deferred; manual/semi-automated data entry and narrative summary fields are supported out-of-the-box in `ManagementReviewInput`.
