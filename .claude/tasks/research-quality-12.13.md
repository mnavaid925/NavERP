# Research — Sub-module 12.13: Customer Complaint Handling (Module 12 — Quality Management System, `quality`)

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

- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py`, prefix `QDOC`): Standard operating procedures (SOPs), customer complaint intake procedures, and Field Safety Notices (FSN).
  - `RiskAssessment` (`apps/quality/models/RiskManagement/RiskAssessments.py`, prefix `QRSK`): Post-market risk reconciliation against product FMEA / ISO 14971 hazard evaluations.
  - `CapaInvestigation` (`apps/quality/models/CapaManagement/CapaInvestigations.py`, prefix `QCAP`): Closed-loop CAPA investigations spawned from recurring, severe, or reportable complaints. Already includes `("complaint", "Customer Complaint")` in `SOURCE_TYPE_CHOICES`.
  - `NonConformanceReport` (`apps/quality/models/NonConformance/NonConformanceReports.py`, prefix `QNCR`): Non-conformance reports triggered directly by defective returned customer samples. Already includes `("customer_return", "Customer Return / RMA")` in `SOURCE_TYPE_CHOICES`.
  - `ProcessDeviation` (`apps/quality/models/NonConformance/ProcessDeviations.py`, prefix `QDEV`): Concessions or deviations associated with suspect lots.
  - `QuarantineContainment` (`apps/quality/models/NonConformance/QuarantineContainments.py`, prefix `QQUR`): Warehouse quarantine holds placed on inventory lots implicated in customer complaints or field recalls.
  - `FinalInspectionLot` (`apps/quality/models/FinalQuality/FinalInspectionLots.py`, prefix `QFQC`): Historical batch release inspection records reviewed during Device History Record (DHR) investigation.

- **Cross-module spine models available to FK:**
  - `core.Tenant` (`apps/core/models/Tenant.py:17`): Multi-tenant isolation foundation.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:5`): Internal quality unit, complaint handling unit, or manufacturing plant responsible for investigation.
  - `core.Party` (`apps/core/models/Party.py:5`) & `core.PartyRole` (`apps/core/models/PartyRole.py:5`): Complainant customers, health care facilities, healthcare professionals, or distributors reporting issues; and regulatory agencies (FDA, Health Canada, EU Competent Authorities).
  - `accounts.User` (`apps/accounts/models.py:52`): Intake coordinators, lead investigators, medical/clinical reviewers, regulatory vigilance specialists, and quality managers.
  - `core.AuditLog` (`apps/core/models/AuditLog.py:5` + `write_audit_log` helper): Immutable tenant-scoped audit logging for FDA 21 CFR Part 11, Part 803, Part 820.198, and ISO 13485:2016 compliance.
  - `scm.SalesOrder` (`apps/scm/models/OrderManagement/SalesOrders.py:20`): Originating sales order against which suspect goods were sold and delivered.
  - `scm.ReturnAuthorization` (`apps/scm/models/ReturnsManagement/ReturnAuthorizations.py:48`): RMA record tracking the physical return of defective product samples to the quality laboratory.
  - `scm.Shipment` (`apps/scm/models/TransportationManagement/Shipments.py`): Outbound delivery and consignment record used during recall traceability and customer consignee identification.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and atomic retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Quality departments, plants, or complaint handling units. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Complainants (customers/patients/distributors) and regulatory authorities. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | Intake specialists, lead investigators, medical reviewers, recall leads. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable audit trail for FDA 21 CFR Part 11 and 820.198 complaint records. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | Complaint SOPs, Field Safety Notices (FSN), customer letters. |
| `quality.RiskAssessment` exists | `apps/quality/models/RiskManagement/RiskAssessments.py:6` | ISO 14971 FMEA failure mode and occurrence frequency verification. |
| `quality.CapaInvestigation` exists | `apps/quality/models/CapaManagement/CapaInvestigations.py:8` | Closed-loop corrective action tracking for complaint trends or critical events. |
| `quality.NonConformanceReport` exists | `apps/quality/models/NonConformance/NonConformanceReports.py:10` | Material/product defect records generated from returned complaint samples. |
| `scm.SalesOrder` exists | `apps/scm/models/OrderManagement/SalesOrders.py:20` | Customer sales orders associated with purchased suspect product. |
| `scm.ReturnAuthorization` exists | `apps/scm/models/ReturnsManagement/ReturnAuthorizations.py:48` | Physical sample return authorization (RMA) for laboratory failure analysis. |

### Spine entities verified NOT to exist (or unbuilt in Module 12 / ERP)

- **Module 5 unbuilt masters:** `Item`, `LotSerial`, `UOM`, `StockMove` are planned for Module 5. Quality models use free-text stand-in fields (`item_code`, `item_name`, `lot_number`, `serial_number`, `udi_di_number`) when complaints and field actions identify specific manufactured units, ensuring complete loose-coupling without hard FKs to unbuilt tables.
- **Direct FDA Electronic Submissions Gateway (ESG) AS2 Connector / EUDAMED Web Service:** Machine-to-machine B2B transmission gateways are external integration layers. Sub-module 12.13 delivers the complete regulatory reportability decision tree, statutory timeline countdown, data capture for MedWatch 3500A / EU MIR, and submission lifecycle tracking.

### Auto-number Prefix Collision Check (0 collisions verified)

Automated ripgrep scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QCMP` (Quality Customer Complaint) -> **0 collisions** (Completely free)
- `QCIN` (Quality Complaint Investigation) -> **0 collisions** (Completely free)
- `QRPT` (Quality Regulatory Vigilance Report) -> **0 collisions** (Completely free)
- `QFMA` (Quality Field Action / Recall) -> **0 collisions** (Completely free)

---

## Leaders surveyed (with source links)

1. **MasterControl Customer Complaints** — Industry-standard life sciences eQMS market leader for FDA 21 CFR Part 820.198, ISO 13485:2016 §8.2.2, and cGMP complaint handling. Features multi-channel intake, automated triage and risk evaluation, embedded decision trees for regulatory reportability (FDA MedWatch / EU Vigilance), automated sample return coordination, and one-click launch to CAPA and Field Action / Recall management.
   - *Source:* https://www.mastercontrol.com/quality/complaint-management/
2. **Sparta Systems TrackWise Digital (Complaint Handling & Regulatory Reporting)** — Honeywell enterprise quality platform for global pharmaceutical and medical device manufacturers. Features automated multi-jurisdiction vigilance decision trees, strict statutory reporting deadline countdown timers (e.g. 5-day, 10-day, 15-day, 30-day), comprehensive root cause investigation workflows, and full Field Safety Corrective Action (FSCA) / recall consignee reconciliation.
   - *Source:* https://www.spartasystems.com/trackwise-digital/complaint-handling/
3. **Veeva Vault QMS (Complaints & Safety Vigilance)** — Unified cloud-native quality and post-market safety management suite. Enforces end-to-end complaint intake, rule-based adverse event classification (Death, Serious Injury, Malfunction), integrated medical/clinical evaluation, Health Hazard Assessment (HHA), customer consignee communication tracking, and direct bi-directional traceability to CAPA and FMEA risk files.
   - *Source:* https://www.veeva.com/products/vault-qms/
4. **ETQ Reliance Complaint Management** — Flexible enterprise quality management platform widely used in regulated manufacturing and aerospace. Provides customer portal web forms, risk matrix scoring (severity × occurrence), physical sample return tracking with chain of custody, regulatory reportability determination, and recall management for tracking customer recovery percentages.
   - *Source:* https://www.etq.com/complaint-management-software/
5. **Greenlight Guru Medical Device Complaint Management** — Purpose-built MedTech QMS aligned strictly with FDA 21 CFR 820.198, ISO 13485:2016, and EU MDR 2017/745. Features guided regulatory reportability decision trees, direct Device History File (DHF) and Risk Management File (FMEA) linkage to compare complaint failure rates against design risk estimates, and structured closure verification.
   - *Source:* https://www.greenlight.guru/medical-device-complaint-management-software
6. **Qualio Complaints Management** — Agile eQMS for growing life sciences and medical device enterprises. Features simplified intake, triage categorization (Adverse Event / Malfunction / Customer Satisfaction / Packaging), mandatory justification recording for non-reportable determinations, investigation assignment, and customer closure communication generation.
   - *Source:* https://www.qualio.com/product/complaints-management
7. **AssurX Customer Complaint Handling & Regulatory Reporting** — Comprehensive enterprise complaint resolution system. Features global regulatory reporting wizards (FDA eMDR, Health Canada, EU MDR), standardized IMDRF (International Medical Device Regulators Forum) problem and evaluation coding hierarchies, physical sample inspection logs, and field correction/recall execution workflows.
   - *Source:* https://www.assurx.com/solutions/quality-management/complaint-management/
8. **Arena QMS (PTC) Quality & Complaint Tracking** — Engineering- and product-centric quality solution connecting customer complaints directly to bill of materials (BOM), item revisions, engineering change orders (ECO), and post-market failure rate metrics.
   - *Source:* https://www.arenasolutions.com/products/quality/

---

## Feature catalog (this sub-module only)

### 1. Complaint Intake & Triage
- **Multi-Channel Complaint Capture** — Intake logging across phone, email, customer service portal, sales rep, distributor, or field service technician with intake timestamp and complainant contact details · seen in: *MasterControl, ETQ Reliance, Qualio, TrackWise* · priority: `table-stakes` · spine: new table `CustomerComplaint` (`QCMP`) · buildable now.
- **Product & Lot Traceability Linkage** — Structured capture of product code, product description, manufacturing lot/batch number, serial numbers, customer PO, and sales order reference · seen in: *All leaders (Veeva, MasterControl, Greenlight Guru, Arena)* · priority: `table-stakes` · spine: fields in `CustomerComplaint` and FK to `scm.SalesOrder` · buildable now.
- **Initial Severity & Priority Grading** — Immediate categorization into Critical (Safety/Adverse Event), Major (Functional Failure/Performance Loss), Minor (Cosmetic/Packaging), or Customer Satisfaction/Inconvenience · seen in: *MasterControl, TrackWise, Qualio, ETQ* · priority: `table-stakes` · spine: choices in `CustomerComplaint` · buildable now.
- **Triage & Validity Determination** — Formal initial evaluation determining whether the report is a valid product complaint, an invalid allegation, or a general commercial query; gates whether formal investigation is required · seen in: *MasterControl, Greenlight Guru, TrackWise* · priority: `table-stakes` · spine: fields in `CustomerComplaint` · buildable now.
- **Physical Sample Return (RMA) Coordination** — Tracking whether physical defective samples are requested from the customer, tracking sample receipt status, condition on arrival, and linkage to RMA · seen in: *ETQ Reliance, MasterControl, AssurX* · priority: `common` · spine: fields in `CustomerComplaint` and FK to `scm.ReturnAuthorization` · buildable now.

### 2. Investigation & Root Cause Analysis
- **Dedicated Investigation Lifecycle & Task Delegation** — Dedicated investigation record assigned to a lead investigator with protocol execution, target completion date, and department ownership · seen in: *All leaders (MasterControl, Veeva Vault, TrackWise, Qualio)* · priority: `table-stakes` · spine: new table `ComplaintInvestigation` (`QCIN`) · buildable now.
- **Device History Record (DHR) / Batch Record Review** — Systematic review of manufacturing history, in-process inspection records, final QC release certificates, and environmental logs for the suspect lot · seen in: *Greenlight Guru, MasterControl, Veeva Vault* · priority: `table-stakes` · spine: fields in `ComplaintInvestigation` · buildable now.
- **Defective Sample Failure Analysis & Laboratory Testing** — Detailed recording of visual, electrical, mechanical, chemical, or software failure analysis testing conducted on returned customer units · seen in: *MasterControl, AssurX, ETQ Reliance* · priority: `table-stakes` · spine: fields in `ComplaintInvestigation` · buildable now.
- **Clinical & Medical Health Hazard Evaluation (HHE)** — Specialized clinical assessment evaluating whether the failure caused or could cause death, permanent impairment, serious injury, or medical intervention · seen in: *Veeva Vault, TrackWise, MasterControl, Greenlight Guru* · priority: `table-stakes` · spine: fields in `ComplaintInvestigation` · buildable now.
- **Risk Assessment & FMEA Reconciliation** — Explicit cross-check against the product Risk Management File (`quality.RiskAssessment`) to determine if the failure mode was anticipated and whether observed post-market frequency exceeds acceptable thresholds · seen in: *Greenlight Guru, Veeva Vault, MasterControl* · priority: `differentiator` · spine: FK to `quality.RiskAssessment` in `ComplaintInvestigation` · buildable now.
- **Standardized Root Cause & Defect Coding** — Hierarchical root cause categorization (Component Failure, Manufacturing Defect, Design Limitation, Software Defect, Operator Use Error, Transit Damage, Not Replicated) aligned with IMDRF terminology · seen in: *TrackWise Digital, AssurX, MasterControl* · priority: `table-stakes` · spine: choices in `ComplaintInvestigation` · buildable now.
- **Closed-Loop CAPA & NCR Escalation** — Direct, one-click escalation from confirmed root causes to a formal CAPA Investigation (`quality.CapaInvestigation` [QCAP-]) or Non-Conformance Report (`quality.NonConformanceReport` [QNCR-]) · seen in: *All leaders (MasterControl, Veeva, TrackWise, Qualio, Greenlight Guru)* · priority: `table-stakes` · spine: FKs to `quality.CapaInvestigation` and `quality.NonConformanceReport` · buildable now.

### 3. Regulatory Reporting & Vigilance
- **Regulatory Reportability Decision Tree** — Formal assessment evaluating whether an event meets statutory adverse event criteria across major jurisdictions (FDA 21 CFR 803 MDR, EU MDR 2017/745 Vigilance, Health Canada, PMDA, TGA) · seen in: *MasterControl, TrackWise, Veeva Vault, Greenlight Guru* · priority: `table-stakes` · spine: new table `RegulatoryReport` (`QRPT`) · buildable now.
- **Statutory Countdown Deadlines** — Automatic computation and tracking of strict statutory submission deadlines:
  - 2-Day Report (EU MDR Public Health Threat)
  - 5-Day Report (FDA 21 CFR 803.53 Remedial Action / Substantial Harm)
  - 10-Day Report (EU MDR Unanticipated Serious Deterioration / Death)
  - 15-Day Report (EU MDR Serious Incident)
  - 30-Day Report (FDA 21 CFR 803 MedWatch 3500A Device Malfunction / Serious Injury)
  · seen in: *TrackWise Digital, Veeva Vault, MasterControl, Greenlight Guru* · priority: `table-stakes` · spine: fields in `RegulatoryReport` · buildable now.
- **Multi-Stage Reporting Lifecycle** — Formal workflow tracking Initial Report, Follow-Up / Supplemental Reports, and Final Closure Reports with agency submission timestamps and acknowledgement numbers · seen in: *Veeva Vault, TrackWise Digital, AssurX* · priority: `table-stakes` · spine: status choices and fields in `RegulatoryReport` · buildable now.
- **Mandatory Non-Reportable Justification** — Mandatory documented rationale signed by quality/regulatory management explaining why a complaint was determined to be non-reportable (critical inspection defense record under FDA 21 CFR 820.198(a)(3)) · seen in: *Greenlight Guru, Qualio, MasterControl* · priority: `table-stakes` · spine: fields in `CustomerComplaint` and `RegulatoryReport` · buildable now.
- **Adverse Event Data Fields for Form 3500A / MIR** — Captures patient outcome (Death, Life-Threatening, Hospitalization, Disability, Medical Intervention), device problem code, and date of adverse event · seen in: *TrackWise, MasterControl, Veeva Vault* · priority: `table-stakes` · spine: fields in `RegulatoryReport` · buildable now.

### 4. Field Action & Recall Management
- **Field Action Classification & Initiation** — Initiation of formal field actions categorized by regulatory severity: Class I Recall (life-threatening/fatal risk), Class II Recall (temporary/medically reversible risk), Class III Recall (unlikely to cause adverse health consequences), Field Safety Corrective Action (FSCA), Safety Alert / Advisory Notice, or Voluntary Market Withdrawal · seen in: *MasterControl, TrackWise, Veeva Vault, ETQ Reliance* · priority: `table-stakes` · spine: new table `FieldAction` (`QFMA`) · buildable now.
- **Affected Population & Consignee Scope Identification** — Determination of affected part numbers, lot/batch numbers, serial number ranges, production date spans, and total units distributed to commercial customers · seen in: *TrackWise Digital, Veeva Vault, ETQ Reliance* · priority: `table-stakes` · spine: fields in `FieldAction` · buildable now.
- **Health Hazard Evaluation (HHE / HHA) Summary** — Clinical review documenting the health risk assessment, probability of occurrence, clinical severity, and vulnerable patient populations · seen in: *Veeva Vault, MasterControl, TrackWise* · priority: `table-stakes` · spine: fields in `FieldAction` · buildable now.
- **Consignee Notification & Response Reconciliation** — Real-time tracking of:
  - Total commercial accounts/customers notified
  - Customer acknowledgment responses received
  - Defective units quarantined by customers
  - Defective units returned, reworked in field, or destroyed
  - Recovery / reconciliation percentage against total distributed units
  · seen in: *TrackWise Digital, ETQ Reliance, AssurX, Veeva Vault* · priority: `differentiator` · spine: counter fields and properties in `FieldAction` · buildable now.
- **Field Safety Notice (FSN) / Customer Letter Association** — Direct linkage to approved Field Safety Notice customer communication documents controlled in Document Control · seen in: *Veeva Vault, MasterControl* · priority: `table-stakes` · spine: FK to `quality.ControlledDocument` · buildable now.
- **Regulatory Authority Recall Notification & Closure** — Recording of official agency notification dates, regulatory recall reference numbers, interim progress reports, and formal termination / closure authorization · seen in: *MasterControl, TrackWise Digital* · priority: `table-stakes` · spine: fields in `FieldAction` · buildable now.

### 5. Complaint Trending & Closure
- **Customer Communication & Response Letters** — Formal generation and logging of customer closing response letters detailing investigation findings, containment measures, and resolution · seen in: *MasterControl, Qualio, ETQ Reliance* · priority: `table-stakes` · spine: fields in `CustomerComplaint` · buildable now.
- **Resolution Dispositioning** — Commercial and technical resolution disposition (Replacement Issued, Credit/Refund Authorized, Repaired & Returned, Return-As-Is, Explanation Provided, Unsubstantiated / No Defect Found) · seen in: *All leaders (Qualio, ETQ, MasterControl, TrackWise)* · priority: `table-stakes` · spine: choices in `CustomerComplaint` · buildable now.
- **Complaint Category & Symptom Tagging** — Multi-dimensional categorization by failure symptom, sub-assembly, clinical user error, packaging, or documentation error · seen in: *TrackWise Digital, Arena QMS, ETQ Reliance* · priority: `table-stakes` · spine: choices and fields in `CustomerComplaint` · buildable now.
- **Post-Market Trending & Recurrence Monitoring** — Metrics calculating complaint recurrence rate, complaints per thousand units distributed (PPM), and failure mode Pareto distribution · seen in: *Veeva Vault, MasterControl, Arena QMS* · priority: `common` · spine: properties and queries across `CustomerComplaint` · buildable now.
- **Formal QMS Gatekeeper Closure** — Multi-condition closure verification: investigation complete, regulatory reports submitted, CAPA initiated (if required), customer notified, and quality authority sign-off · seen in: *All leaders (MasterControl, Veeva, TrackWise, Qualio)* · priority: `table-stakes` · spine: status workflow and validation methods in `CustomerComplaint` · buildable now.

### 6. Beyond the Bullets
- **Statutory Countdown Visual Urgency Badging** — Dynamic color-coded deadline badges (`badge-red` for overdue or <= 2 days, `badge-amber` for <= 7 days, `badge-info` for on-track) directly on regulatory vigilance list and detail pages · seen in: *TrackWise Digital, Veeva Vault* · priority: `differentiator` · spine: helper property in `RegulatoryReport` · buildable now.
- **Recall Consignee Reconciliation Progress Bar** — Real-time progress bar computing the exact percentage of distributed units accounted for or recovered during an active recall · seen in: *TrackWise Digital, ETQ Reliance* · priority: `differentiator` · spine: `@property reconciliation_rate` on `FieldAction` · buildable now.

---

## Recommended build scope (this pass — 4 models)

### Model 1: `CustomerComplaint` [NUMBER_PREFIX = "QCMP"]
- **Purpose:** Primary entity capturing incoming customer complaint allegations, customer and item identification, intake triage, severity grading, regulatory reportability screening, and final resolution closure.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QCMP`)
  - `title` (`CharField(255)`): Short headline summary of the customer allegation (e.g. "Catheter balloon rupture during inflation")
  - `intake_channel` (`CharField(30)`): `phone` (Phone Call), `email` (Email Submission), `web_portal` (Customer Portal), `sales_rep` (Sales Representative), `service_tech` (Field Service Engineer), `distributor` (Distributor / Dealer), `regulatory_agency` (Regulatory Authority Notice), `other` (Other Channel)
  - `customer` (`ForeignKey("core.Party", null=True, blank=True, related_name="customer_complaints")`): External customer or hospital account
  - `complainant_name` (`CharField(128)`): Individual reporter or clinician name
  - `complainant_email` (`CharField(128)`, blank=True): Contact email
  - `complainant_phone` (`CharField(64)`, blank=True): Contact telephone
  - `complainant_organization` (`CharField(128)`, blank=True): Hospital, clinic, or facility name
  - `sales_order` (`ForeignKey("scm.SalesOrder", null=True, blank=True, related_name="complaints")`): Originating sales order
  - `item_code` (`CharField(100, db_index=True)`): Finished product catalog number / part number
  - `item_name` (`CharField(255)`): Product commercial name
  - `lot_number` (`CharField(100, db_index=True, blank=True)`): Manufacturing batch / lot number
  - `serial_number` (`CharField(100, db_index=True, blank=True)`): Specific device serial number
  - `udi_di_number` (`CharField(100, blank=True)`): Unique Device Identification (UDI-DI / GTIN)
  - `date_received` (`DateField`): Date complaint was first received by the organization
  - `date_of_occurrence` (`DateField(null=True, blank=True)`): Date incident actually occurred at customer site
  - `problem_description` (`TextField`): Comprehensive narrative of the reported problem and customer observation
  - `severity` (`CharField(30)`): `critical_safety` (Critical - Patient/User Safety Threat), `major_malfunction` (Major - Device Malfunction / Performance Failure), `minor_cosmetic` (Minor - Cosmetic / Packaging Defect), `service_inconvenience` (Inconvenience - Customer Service / Usability), `unspecified` (Unspecified Severity)
  - `is_valid_complaint` (`CharField(20)`): `pending_triage` (Triage Pending), `valid_complaint` (Valid Product Complaint), `invalid_allegation` (Invalid / Customer Misuse), `commercial_inquiry` (Non-Quality / Commercial Issue)
  - `investigation_required` (`BooleanField(default=True)`): Whether a technical failure investigation is mandated
  - `sample_return_required` (`BooleanField(default=False)`): Whether physical return of the suspect unit is needed
  - `sample_received` (`BooleanField(default=False)`): Whether the physical sample has arrived at the QC lab
  - `sample_received_date` (`DateField(null=True, blank=True)`): Date physical sample was received
  - `return_authorization` (`ForeignKey("scm.ReturnAuthorization", null=True, blank=True, related_name="complaints")`): Linked RMA record
  - `is_reportable` (`CharField(25)`): `undetermined` (Evaluation Pending), `reportable_event` (Reportable Adverse Event), `non_reportable` (Confirmed Non-Reportable), `exempt` (Regulatory Exemption)
  - `non_reportable_justification` (`TextField(blank=True)`): Documented justification rationale if evaluated as non-reportable
  - `assigned_investigator` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="investigated_complaints")`)
  - `complaint_category` (`CharField(30)`): `mechanical_failure` (Mechanical / Structural Failure), `electrical_electronic` (Electrical / Electronic Fault), `software_firmware` (Software / Firmware Error), `packaging_seal` (Packaging Integrity / Sterile Seal), `labeling_ifu` (Labeling / Instructions for Use), `biological_contamination` (Contamination / Foreign Particulate), `clinical_adverse_event` (Clinical Complication / Injury), `user_error` (Operator Use Error), `other` (Other Category)
  - `status` (`CharField(35)`): `draft` (Draft Intake), `open_triage` (Open / Triage Assessment), `under_investigation` (Investigation Active), `regulatory_review` (Regulatory Review Active), `capa_initiated` (CAPA Escalated), `resolution_pending` (Customer Resolution Pending), `closed` (Closed / Complete), `cancelled_invalid` (Cancelled / Invalid)
  - `resolution_type` (`CharField(30)`): `pending` (Resolution Pending), `replacement_shipped` (Replacement Unit Shipped), `credit_refund` (Credit Note / Refund Authorized), `repaired_returned` (Product Repaired & Returned), `return_as_is` (Returned As-Is / No Fault Found), `explanation_letter` (Technical Explanation Provided), `unsubstantiated` (Allegation Unsubstantiated)
  - `customer_response_letter` (`TextField(blank=True)`): Formal closing communication text sent to customer
  - `customer_response_date` (`DateField(null=True, blank=True)`): Date resolution was communicated to customer
  - `closed_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="closed_complaints")`)
  - `closed_at` (`DateTimeField(null=True, blank=True)`)
  - `notes` (`TextField(blank=True)`)
- **Properties / Methods:**
  - `days_open`: Total elapsed calendar days from `date_received` to `closed_at` (or today if active).
  - `has_active_regulatory_report`: Boolean indicating whether linked regulatory reports are currently pending submission.
- **Constraints & Indexes (`<= 30` chars):**
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcmp_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qcmp_ten_status")` (18)
  - `Index(fields=["tenant", "severity"], name="idx_qcmp_ten_severity")` (20)
  - `Index(fields=["tenant", "item_code"], name="idx_qcmp_ten_item")` (17)
  - `Index(fields=["tenant", "is_reportable"], name="idx_qcmp_ten_rep_stat")` (21)
- **Verified FKs:** `core.Tenant`, `core.Party`, `scm.SalesOrder`, `scm.ReturnAuthorization`, `accounts.User`.

### Model 2: `ComplaintInvestigation` [NUMBER_PREFIX = "QCIN"]
- **Purpose:** Comprehensive technical, metallurgical, clinical, or software failure analysis investigation associated with a customer complaint, establishing root cause, reviewing manufacturing history, and escalating to CAPA or NCR.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QCIN`)
  - `complaint` (`ForeignKey("quality.CustomerComplaint", on_delete=models.CASCADE, related_name="investigations")`)
  - `title` (`CharField(255)`): Investigation title (e.g. "Failure Analysis - Lot B2026-04 Catheter Rupture")
  - `lead_investigator` (`ForeignKey(settings.AUTH_USER_MODEL, related_name="led_complaint_investigations")`)
  - `target_completion_date` (`DateField`)
  - `actual_completion_date` (`DateField(null=True, blank=True)`)
  - `status` (`CharField(30)`): `assigned` (Investigation Assigned), `dhr_review` (Batch History / DHR Review), `sample_testing` (Physical Sample Testing), `root_cause_analysis` (Root Cause Determination), `clinical_review` (Clinical / Medical Evaluation), `completed` (Investigation Completed), `cancelled` (Cancelled)
  - `dhr_review_summary` (`TextField(blank=True)`): Summary of manufacturing batch records, line clearance, in-process testing, and release data
  - `dhr_anomalies_found` (`BooleanField(default=False)`): Whether anomalies, rework, or deviations were identified in batch records
  - `sample_condition_notes` (`TextField(blank=True)`): Physical condition of returned unit upon receipt at quality lab
  - `failure_analysis_method` (`CharField(30)`): `visual_microscopy` (Visual & Optical Microscopy), `dimensional_metrology` (Dimensional Metrology), `mechanical_stress` (Tensile / Burst / Mechanical Testing), `electrical_functional` (Electrical / Functional Bench Test), `chemical_spectroscopy` (Chemical / FTIR / Spectroscopy), `software_code_audit` (Software Log & Code Audit), `historical_data_review` (Historical Batch Review Only), `other` (Other Analytical Method)
  - `test_results_summary` (`TextField(blank=True)`): Detailed observations, lab findings, and quantitative measurements
  - `clinical_evaluation_summary` (`TextField(blank=True)`): Medical expert evaluation of patient injury risk or health consequence
  - `risk_assessment` (`ForeignKey("quality.RiskAssessment", null=True, blank=True, on_delete=models.SET_NULL, related_name="complaint_investigations")`): Linked ISO 14971 FMEA risk item
  - `is_anticipated_risk` (`BooleanField(default=True)`): Whether this failure mode was previously captured in the Risk Management File
  - `occurrence_rate_exceeded` (`BooleanField(default=False)`): Whether observed complaint rate exceeds estimated probability of occurrence
  - `root_cause_category` (`CharField(32)`): `component_defect` (Component / Raw Material Defect), `assembly_workmanship` (Manufacturing / Workmanship Error), `process_deviation` (Process Parameter Excursion), `design_flaw` (Design Limitation / Flaw), `software_bug` (Software Logic Bug), `packaging_barrier` (Packaging Seal Degradation), `transit_damage` (Transportation / Handling Damage), `user_error_misuse` (Operator / Clinical Use Error), `unconfirmed_no_defect` (Unconfirmed / No Defect Detected), `other` (Other Root Cause)
  - `root_cause_narrative` (`TextField(blank=True)`): Comprehensive explanation of the root cause mechanism (e.g. 5 Whys analysis)
  - `capa_required` (`BooleanField(default=False)`): Whether a corrective and preventive action is necessary
  - `linked_capa` (`ForeignKey("quality.CapaInvestigation", null=True, blank=True, on_delete=models.SET_NULL, related_name="source_complaint_investigations")`): Linked CAPA
  - `linked_ncr` (`ForeignKey("quality.NonConformanceReport", null=True, blank=True, on_delete=models.SET_NULL, related_name="source_complaint_investigations")`): Linked NCR
  - `investigation_conclusion` (`TextField(blank=True)`): Final formal conclusion and technical summary
  - `approved_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="approved_complaint_investigations")`)
  - `approved_at` (`DateTimeField(null=True, blank=True)`)
- **Properties / Methods:**
  - `is_overdue`: Boolean indicating whether target completion date has lapsed without completion.
- **Constraints & Indexes (`<= 30` chars):**
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcin_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qcin_ten_status")` (18)
  - `Index(fields=["tenant", "root_cause_category"], name="idx_qcin_ten_root")` (16)
- **Verified FKs:** `core.Tenant`, `quality.CustomerComplaint`, `accounts.User`, `quality.RiskAssessment`, `quality.CapaInvestigation`, `quality.NonConformanceReport`.

### Model 3: `RegulatoryReport` [NUMBER_PREFIX = "QRPT"]
- **Purpose:** Post-market regulatory vigilance and mandatory adverse event submission entity tracking jurisdiction requirements, statutory filing deadlines, reporting stages, and official authority acknowledgements.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QRPT`)
  - `complaint` (`ForeignKey("quality.CustomerComplaint", on_delete=models.CASCADE, related_name="regulatory_reports")`)
  - `agency` (`CharField(30)`): `fda_cdrh` (US FDA - CDRH Devices), `fda_cder` (US FDA - CDER Drugs), `eu_competent_auth` (EU Competent Authority - MDR), `health_canada` (Health Canada - Medical Devices), `pmda_japan` (PMDA Japan - MHLW), `tga_australia` (TGA Australia), `mhra_uk` (MHRA United Kingdom), `other_authority` (Other National Competent Authority)
  - `report_type` (`CharField(30)`): `initial_report` (Initial Mandatory Report), `follow_up_supplemental` (Follow-up / Supplemental Report), `final_closure_report` (Final Incident Closure Report), `non_reportable_justification` (Formal Non-Reportable Memo)
  - `adverse_event_classification` (`CharField(32)`): `death` (Patient / User Death), `serious_injury` (Serious Deterioration of Health / Permanent Injury), `malfunction_recurrent` (Device Malfunction Likely to Cause Harm), `public_health_threat` (Serious Public Health Threat), `remedial_action_trigger` (Report of Correction or Removal)
  - `statutory_timeline` (`CharField(35)`): `2_day_public_health` (2-Day Emergency Report - EU MDR), `5_day_remedial` (5-Day Remedial Action - FDA 21 CFR 803.53), `10_day_death_deterioration` (10-Day Serious Deterioration - EU MDR), `15_day_serious_incident` (15-Day Serious Incident - EU MDR), `30_day_standard_mdr` (30-Day Standard Medical Device Report - FDA)
  - `due_date` (`DateField`): Computed statutory deadline date for filing
  - `submission_date` (`DateField(null=True, blank=True)`): Actual date filed with regulatory agency
  - `submission_format` (`CharField(25)`): `medwatch_3500a` (FDA Form MedWatch 3500A), `emdr_electronic` (FDA Electronic eMDR XML), `eu_mir_xml` (EU Manufacturer Incident Report - MIR), `health_canada_form` (Health Canada Mandatory Incident Form), `agency_online_portal` (National Online Portal Submission), `formal_letter_memo` (Formal Letter / Paper Filing)
  - `agency_report_identifier` (`CharField(64, blank=True)`): Manufacturer Report Number (e.g. FDA MDR 7-digit FEI + Year + Sequence: 1234567-2026-00001)
  - `agency_acknowledgement_number` (`CharField(64, blank=True)`): Confirmation number / transmission ID issued by agency
  - `patient_outcome` (`CharField(25)`): `death` (Death), `life_threatening` (Life-Threatening), `hospitalization` (Hospitalization / Prolonged), `disability_impairment` (Permanent Disability), `medical_intervention` (Medical Intervention Required), `no_adverse_effect` (No Adverse Effect Observed)
  - `status` (`CharField(30)`): `draft` (Drafting Report), `under_medical_review` (Medical & Regulatory Review), `ready_for_submission` (Approved - Ready to Submit), `submitted` (Submitted to Agency), `agency_accepted` (Agency Accepted / Acknowledged), `additional_info_requested` (Additional Information Requested), `closed` (Report Closed)
  - `event_narrative` (`TextField`): Mandatory technical narrative describing the event, patient involvement, device performance, and remedial actions
  - `device_problem_code` (`CharField(64, blank=True)`): Standardized IMDRF / FDA device problem code (e.g. "A0401 - Break")
  - `submitted_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="submitted_regulatory_reports")`)
  - `closure_date` (`DateField(null=True, blank=True)`)
  - `notes` (`TextField(blank=True)`)
- **Properties / Methods:**
  - `is_overdue`: True if submission is past `due_date` and `status` is not `submitted`, `agency_accepted`, or `closed`.
  - `days_until_due`: Calculated calendar days remaining until statutory deadline.
  - `urgency_badge_css`: CSS badge color (`badge-red` for overdue / <= 2 days, `badge-amber` for <= 7 days, `badge-info` otherwise).
- **Constraints & Indexes (`<= 30` chars):**
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrpt_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "agency"], name="idx_qrpt_ten_agency")` (18)
  - `Index(fields=["tenant", "status"], name="idx_qrpt_ten_status")` (18)
  - `Index(fields=["tenant", "due_date"], name="idx_qrpt_ten_due")` (15)
- **Verified FKs:** `core.Tenant`, `quality.CustomerComplaint`, `accounts.User`.

### Model 4: `FieldAction` [NUMBER_PREFIX = "QFMA"]
- **Purpose:** Enterprise orchestrator for product recalls, Field Safety Corrective Actions (FSCA), safety notices, and market withdrawals, handling health hazard assessments, customer consignee notification, unit recovery reconciliation, and regulatory termination.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QFMA`)
  - `title` (`CharField(255)`): Official title of field action (e.g. "Urgent Medical Device Recall - Disposable Syringes Lot B2026")
  - `action_type` (`CharField(32)`): `recall_removal` (Product Recall - Removal from Market), `fsca_safety_notice` (Field Safety Corrective Action - FSCA), `field_correction_rework` (Field Correction / On-Site Modification), `safety_advisory_alert` (Safety Alert / Customer Advisory Notice), `market_withdrawal` (Market Withdrawal - Minor/Non-Violative)
  - `recall_classification` (`CharField(25)`): `class_i_critical` (Class I - High Probability of Death/Serious Harm), `class_ii_moderate` (Class II - Temporary/Reversible Harm), `class_iii_minor` (Class III - Unlikely to Cause Adverse Health Consequences), `fsca_safety_alert` (FSCA - Safety Correction / Advisory), `not_classified` (Not Classified / Non-Violative)
  - `initiating_complaint` (`ForeignKey("quality.CustomerComplaint", null=True, blank=True, on_delete=models.SET_NULL, related_name="field_actions")`): Primary originating customer complaint
  - `lead_coordinator` (`ForeignKey(settings.AUTH_USER_MODEL, related_name="coordinated_field_actions")`)
  - `field_safety_notice_doc` (`ForeignKey("quality.ControlledDocument", null=True, blank=True, on_delete=models.SET_NULL, related_name="field_actions")`): Approved Field Safety Notice (FSN) document
  - `affected_item_code` (`CharField(100, db_index=True)`): Product SKU / Catalog Number
  - `affected_item_name` (`CharField(255)`): Product commercial name
  - `affected_lot_numbers` (`CharField(255)`): Impacted manufacturing lot/batch numbers
  - `affected_serial_numbers` (`CharField(255, blank=True)`): Impacted serial number ranges
  - `distribution_date_start` (`DateField(null=True, blank=True)`): Beginning of commercial distribution span
  - `distribution_date_end` (`DateField(null=True, blank=True)`): End of commercial distribution span
  - `health_hazard_evaluation` (`TextField`): Clinical assessment of health hazard, clinical probability, and vulnerable patient populations
  - `total_units_distributed` (`PositiveIntegerField(default=0)`): Total number of units shipped to commercial customers
  - `consignees_targeted_count` (`PositiveIntegerField(default=0)`): Total number of customer/distributor accounts to notify
  - `consignees_notified_count` (`PositiveIntegerField(default=0)`): Number of consignee accounts verified notified
  - `consignees_responded_count` (`PositiveIntegerField(default=0)`): Number of consignee acknowledgment forms returned
  - `units_quarantined_by_customers` (`PositiveIntegerField(default=0)`): Units confirmed isolated/quarantined in field
  - `units_recovered_or_destroyed` (`PositiveIntegerField(default=0)`): Units returned to warehouse, corrected, or destroyed
  - `status` (`CharField(30)`): `draft_strategy` (Draft Recall Strategy), `management_approved` (Recall Strategy Approved), `agency_notified` (Regulatory Agencies Notified), `active_notification` (Customer Notification in Progress), `reconciliation_active` (Reconciliation & Recovery Active), `termination_requested` (Recall Termination Requested), `closed_terminated` (Closed / Formally Terminated), `cancelled` (Cancelled)
  - `initiation_date` (`DateField`): Date field action was formally declared
  - `agency_notification_date` (`DateField(null=True, blank=True)`): Date regulatory agencies were informed
  - `regulatory_reference_number` (`CharField(64, blank=True)`): Official agency recall number (e.g. FDA Recall Z-Number: "Z-1234-2026")
  - `termination_date` (`DateField(null=True, blank=True)`): Date regulatory agency agreed to formal termination
  - `closure_justification` (`TextField(blank=True)`): Final reconciliation report, recovery analysis, and termination rationale
- **Properties / Methods:**
  - `reconciliation_rate`: Percentage of distributed units accounted for (`(units_quarantined_by_customers + units_recovered_or_destroyed) / total_units_distributed * 100` if total > 0).
  - `consignee_response_rate`: Percentage of notified customers responding (`consignees_responded_count / consignees_targeted_count * 100` if targeted > 0).
- **Constraints & Indexes (`<= 30` chars):**
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qfma_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "status"], name="idx_qfma_ten_status")` (18)
  - `Index(fields=["tenant", "recall_classification"], name="idx_qfma_ten_class")` (17)
  - `Index(fields=["tenant", "action_type"], name="idx_qfma_ten_type")` (16)
  - `Index(fields=["tenant", "affected_item_code"], name="idx_qfma_ten_item")` (17)
- **Verified FKs:** `core.Tenant`, `quality.CustomerComplaint`, `quality.ControlledDocument`, `accounts.User`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Master Document Authoring, Approval & FSN Templates (`ControlledDocument`)** -> Belongs to **Sub-module 12.1 Document Control & Management**. 12.13 links to `ControlledDocument` for Field Safety Notice customer templates and SOPs, but document creation and revision workflows stay in 12.1.
- **Risk Management File, FMEA & Hazard Analysis (`RiskAssessment`)** -> Belongs to **Sub-module 12.3 Risk Management**. 12.13 reconciles complaint occurrence against the Risk Management File via foreign key, but hazard scoring and mitigation design remain in 12.3.
- **CAPA Investigations, 8D Root Cause Analysis & Effectiveness Reviews (`CapaInvestigation`)** -> Belongs to **Sub-module 12.4 CAPA Management**. 12.13 complaints and investigations escalate directly into `CapaInvestigation` via foreign key, but the multi-stage CAPA action plan and effectiveness verification stay in 12.4.
- **Defective Material Quarantine Containment & MRB Disposition (`NonConformanceReport`, `QuarantineContainment`)** -> Belongs to **Sub-module 12.5 Non-Conformance & Deviation Management**. 12.13 investigations link defective returned samples to `NonConformanceReport` and quarantine lots in `QuarantineContainment`, but scrap/rework disposition stays in 12.5.
- **Physical Customer Returns, Return Authorizations (RMA) & Credit Notes (`ReturnAuthorization`)** -> Belongs to **SCM Sub-module 4.10 Returns Management**. 12.13 links to `ReturnAuthorization` for defective sample tracking, but warehouse physical receipt and credit note drafting remain in SCM 4.10.
- **Periodic Safety Update Reports (PSUR) & Post-Market Clinical Follow-Up (PMCF)** -> Belongs to **Sub-module 12.17 Regulatory Compliance & Submissions**. 12.13 manages individual complaint vigilance reports (MDR / MedWatch / MIR) and field actions; annual aggregate surveillance reporting belongs to 12.17.
- **Customer Consignee Shipping & Distribution Lot Tracing (`Shipment`)** -> Belongs to **SCM Sub-module 4.18 Transportation Management** and **12.18 Traceability & Serialization**. 12.13 aggregates customer counts and recovery numbers during recalls; low-level shipping carton tracing belongs to SCM 4.18.

---

## Deferred (later passes / integrations)

- **Direct FDA Electronic Submissions Gateway (ESG) AS2 Connector** — Automated electronic B2B transmission of XML eMDR files directly to CDRH gateway via AS2 protocol. (Handled in this pass via data capture, MedWatch 3500A tracking, and exportable records).
- **Direct EUDAMED Machine-to-Machine Service** — Direct REST/EDI integration with European Commission EUDAMED vigilance portal for electronic MIR XML submission.
- **Customer Self-Service Interactive Complaint Intake Portal** — External public/patient web form with reCAPTCHA for direct unauthenticated complaint filing. (Complaints logged in this pass by internal CSRs, quality coordinators, or via CRM/SCM portal handoff).
- **Automated Computer Vision Defect OCR on Returned Sample Photos** — AI-assisted image analysis to detect fracture lines, scorch marks, or packaging punctures from photos uploaded to complaint investigations.
