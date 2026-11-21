# Research — Sub-module 12.17: Regulatory Compliance & Submissions (Module 12 — Quality Management System, `quality`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 12 so far (`apps/core/navigation.py`):**
  - `"12.1"` (Document Control & Management): `ControlledDocument`, `ElectronicSignatureRecord`, `DocumentAcknowledgment`, `DocumentChangeOrder`, Archive Vault
  - `"12.2"` (Design Controls & Development): `DesignProject`, `DesignInput`, `DesignReview`, `DesignVerification`, Traceability Matrix
  - `"12.3"` (Risk Management / ISO 14971): `RiskAssessment`, `RiskControlMeasure`, `RiskManagementPlan`, `RiskReviewRecord`, FMEA Matrix
  - `"12.4"` (Corrective & Preventive Action / CAPA): `CapaInvestigation`, `RootCauseAnalysis`, `CapaAction`, `CapaEffectivenessReview`, Tracking Board
  - `"12.5"` (Non-Conformance & Deviation Management): `NonConformanceReport`, `QuarantineContainment`, `MrbDisposition`, `ProcessDeviation`, Analytics Dashboard
  - `"12.6"` (Supplier & Vendor Quality Management): `SupplierQualificationAudit`, `SupplierQualityScorecard`, `SupplierCorrectiveAction`, `SupplierChangeNotification`, AVL Directory
  - `"12.7"` (Incoming Quality Control / IQC): `IncomingInspectionPlan`, `IncomingInspectionLot`, `CertificateOfAnalysis`, `QualityReturnAuthorization`, SPC Dashboard
  - `"12.8"` (In-Process Quality Control / IPQC): `ProcessParameterLog`, `FirstArticleInspection`, `InProcessInspection`, `LayeredProcessAudit`, SPC Dashboard
  - `"12.9"` (Final Quality Control / OQC): `FinalInspectionLot`, `CertificateOfConformance`, `PackagingLabelVerification`, `QualityReleaseAuthorization`, OQC Hold Board
  - `"12.10"` (Calibration & Measurement System Analysis): `CalibrationGage`, `CalibrationRecord`, `OutOfToleranceInvestigation`, `MeasurementSystemAnalysis`, Vendor Directory
  - `"12.11"` (Audit Management): `AuditProgram`, `QualityAudit`, `AuditFinding`, `RegulatoryInspectionHost`, Action Tracker
  - `"12.12"` (Training & Competency Management): `CompetencyMatrix`, `QualityTrainingCourse`, `TrainingEnrollment`, `CompetencyCertification`, Compliance Dashboard
  - `"12.13"` (Customer Complaints & Post-Market Surveillance): `CustomerComplaint`, `ComplaintInvestigation`, `RegulatoryReport`, `FieldAction`, Trending Dashboard
  - `"12.14"` (Management Review & Quality Planning): `QualityObjective`, `ManagementReview`, `ManagementReviewInput`, `ManagementReviewAction`, Planning Dashboard
  - `"12.15"` (Process Validation & Verification): `ValidationProtocol`, `ProcessCapabilityStudy`, `ComputerSystemValidation`, `CleaningValidation`, Validation Summary
  - `"12.16"` (Environmental, Health & Safety / EHS): `HazardousMaterial`, `SafetyIncident`, `EnvironmentalMonitoringLog`, `WasteDisposalManifest`, EHS Dashboard
- **Sibling models available to FK in `apps/quality/models/` (60 verified models):**
  - `ControlledDocument` (`QDOC-`): submission dossiers, 510(k) summary documents, CE technical files, summary of safety and clinical performance (SSCP), labeling files, clinical evaluation reports (CER).
  - `ElectronicSignatureRecord` (`QSIG-`): 21 CFR Part 11 compliant sign-offs for submission package lock, health authority formal responses, and PSUR approval.
  - `CustomerComplaint` (`QCMP-`): field performance data and user feedback feeding directly into Post-Market Surveillance (PMS) trend calculations.
  - `RegulatoryReport` (`QRPT-`): mandatory medical device reporting (FDA MedWatch 3500A, EU vigilance initial/final incident reports) feeding vigilance PMS.
  - `RegulatoryInspectionHost` (`QHST-`): agency audit records (FDA 483 inspections, Notified Body audits) generating formal regulatory commitments.
  - `NonConformanceReport` (`QNCR-`) & `CapaInvestigation` (`QCAP-`): quality escalation items tied to regulatory correspondence and post-market commitments.
  - `RiskAssessment` (`QRSK-`): ISO 14971 risk management files referenced in benefit-risk re-evaluations during PSUR / PMS compilation.
  - `DesignProject` (`QDPL-`): design history files (DHF) providing essential submission inputs for clearance / technical documentation.
- **Spine entities verified to exist (`apps/core/models/`, `accounts`):**
  - `core.Tenant`: multi-tenant workspace isolation across all regulatory operations.
  - `core.OrgUnit`: legal manufacturer entity, authorized facility, clinical trial division, or global regulatory affairs department.
  - `core.Party` & `core.PartyRole`: health authorities (US FDA, EMA, Health Canada, PMDA, NMPA, MHRA), notified bodies (BSI, TÜV SÜD, DEKRA), European Authorized Representatives (EU AR), UK Responsible Persons, US Agents, local sponsors/distributors.
  - `accounts.User` (`settings.AUTH_USER_MODEL`): regulatory affairs manager, submission lead author, medical safety director, executive sponsor, qualified person (QP / PRRC).
- **Cross-module masters / unbuilt masters status (lessons L28, L29):**
  - Unbuilt masters: `Item`, `UOM`, `StockMove`, `LotSerial` (Module 5). Replaced with explicit tenant-scoped text/code fields: `product_code`, `product_name`, `device_model`, `intended_purpose`, `udi_di_code`.
  - Financial ledger: Owned by `apps/accounting`. Registration fees, user fees (e.g. FDA MDUFA fees, Notified Body assessment fees), and renewals reference standard decimal fields without duplicating accounting ledgers.
- **Prefix availability audit (repo-wide verified, 0 collisions across 13 apps & `contract-*.md`):**
  - `QSUB`: **FREE** (Quality Regulatory Submission Dossier)
  - `QREG`: **FREE** (Quality Product & Establishment Registration / License)
  - `QCOM`: **FREE** (Quality Regulatory Commitment & Agency Correspondence)
  - `QPMS`: **FREE** (Quality Post-Market Surveillance & PSUR Report)

---

## Leaders surveyed (with source links)

1. **Veeva Vault RIM / Veeva MedTech RIM** — *Global life sciences benchmark for end-to-end regulatory information management, submissions publishing, health authority interaction tracking, and multi-country registrations.*
   - Sources: [veeva.com - MedTech RIM](https://www.veeva.com/products/medtech/rim/), [veeva.com - Vault Submissions](https://www.veeva.com/products/vault-submissions/), [veeva.com - Vault Registrations](https://www.veeva.com/products/vault-registrations/)
2. **Rimsys (Regulatory Management System)** — *The premier purpose-built medical device and IVD regulatory platform managing 510(k), PMA, CE Technical Files, GSPR checklists, global registration lifecycles, and health authority intelligence.*
   - Sources: [rimsys.io - Product Platform](https://www.rimsys.io/), [rimsys.io - Submissions Management](https://www.rimsys.io/platform/submissions), [rimsys.io - Registrations Management](https://www.rimsys.io/platform/registrations)
3. **MasterControl Regulatory Excellence** — *QMS-integrated regulatory suite connecting document control, design history files (DHF), and engineering changes directly into technical dossiers and submission tracking.*
   - Sources: [mastercontrol.com - Regulatory Excellence](https://www.mastercontrol.com/regulatory/), [mastercontrol.com - Submissions Document Management](https://www.mastercontrol.com/solutions/regulatory/submissions/)
4. **RegDesk** — *AI-driven regulatory intelligence and global medical device registration platform tracking international approvals, guidance documents, and distributor licenses across 120+ countries.*
   - Sources: [regdesk.co - Regulatory Information Management](https://www.regdesk.co/rims/), [regdesk.co - Regulatory Intelligence](https://www.regdesk.co/regulatory-intelligence/)
5. **Amplexor / Acolad Life Sciences RIM** — *Enterprise regulatory lifecycle management supporting global drug/device submissions, eCTD / eSTAR structures, health authority correspondence, and license maintenance.*
   - Sources: [acolad.com - Life Sciences RIM](https://www.acolad.com/life-sciences/regulatory-information-management)
6. **Ennov Regulatory Suite (Ennov RIM / Submissions)** — *Unified European and global regulatory platform handling eCTD compilation, medical device technical documentation, agency correspondence tracking, and post-marketing commitments.*
   - Sources: [ennov.com - Regulatory Suite](https://www.ennov.com/software/regulatory/), [ennov.com - Submissions Management](https://www.ennov.com/software/regulatory/submissions/)
7. **IQVIA Regulatory Suite (SmartSolve / RIM)** — *Global compliance platform integrating regulatory affairs with clinical development, post-market surveillance, and health authority tracking.*
   - Sources: [iqvia.com - Regulatory Solutions](https://www.iqvia.com/solutions/regulatory-compliance)
8. **ArisGlobal LifeSphere RIM** — *Next-generation cloud platform for global regulatory registration management, health authority interactions, commitments, and eCTD publishing.*
   - Sources: [arisglobal.com - LifeSphere Regulatory](https://www.arisglobal.com/lifesphere-regulatory/)

---

## Regulatory Alignment & Industry Standards Framework

Sub-module 12.17 must align with the primary regulatory pathways and statutory mandates governing life sciences, pharma, and medical devices:
1. **US FDA Regulations (21 CFR)**:
   - **21 CFR Part 807**: Establishment Registration and Device Listing for Manufacturers and Initial Importers; 510(k) Premarket Notification requirements.
   - **21 CFR Part 814**: Premarket Approval (PMA) applications, PMA supplements, humanitarian device exemptions (HDE).
   - **21 CFR Part 820 / QMSR (Quality Management System Regulation)**: Requirements for design controls, technical documentation, device master records (DMR), and compliance correspondence.
   - **FDA eSTAR (electronic Submission Template And Resource)**: Structured 510(k), De Novo, and PMA submission packaging.
2. **European Union Regulations**:
   - **EU MDR 2017/745 (Medical Device Regulation)**:
     - *Annex II & III*: Technical Documentation and Post-Market Surveillance Technical Documentation (CE Technical Files).
     - *Article 83-86*: Post-Market Surveillance (PMS) Plan, PMS Report (Class I), and Periodic Safety Update Report (PSUR for Class IIa, IIb, III).
     - *Article 61 & Annex XIV Part B*: Post-Market Clinical Follow-up (PMCF).
     - *Article 31 & 32*: Registration of devices and economic operators (EUDAMED Actor registration and UDI-DI linkage).
   - **EU IVDR 2017/746 (In Vitro Diagnostic Medical Device Regulation)**: Corresponding technical documentation, performance evaluation reports (PER), and post-market performance follow-up (PMPF).
3. **ISO 13485:2016 (Medical Devices — Quality Management Systems)**:
   - *Clause 4.2.3*: Medical Device File (MDF).
   - *Clause 7.2.3*: Customer and Regulatory Authority communication.
   - *Clause 8.2.1*: Feedback and Post-Market Monitoring.
4. **Health Authority Interactions & Commitments**:
   - Tracking agency requests for additional information (AI requests / deficiency letters), formal response countdowns, pre-submission meeting minutes, and post-approval commitments (post-market clinical studies, stability testing updates, annual reports).

---

## Feature Catalog (Sub-module 12.17 only)

### 1. Submission Document Management
- **Dossier & Submission Package Structuring** — Authoring, tracking, and compilation of regulatory submission dossiers for 510(k), PMA, De Novo, CE Technical File / Design Dossier (EU MDR/IVDR), Health Canada MDL, PMDA, and NMPA.
  - *Seen in:* Veeva Vault Submissions, Rimsys, MasterControl, Ennov.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* New model `RegulatorySubmission` (`QSUB-`), linking to `ControlledDocument` and `core.OrgUnit`.
- **Submission Lifecycle & Gate Milestones** — Tracking status through Authoring, Internal QA Review, Ready for Submission, Submitted to Agency, Under Review, AI/Deficiency Phase, Cleared / Approved, Rejected, or Withdrawn.
  - *Seen in:* Veeva, Rimsys, RegDesk, Amplexor.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* `RegulatorySubmission.status` lifecycle and milestone date fields.
- **Dossier Component Table of Contents (TOC)** — Categorization of technical sections: Device Description, Essential Principles / GSPR Checklist, Biocompatibility, Software Verification (IEC 62304), Bench Testing, Clinical Evaluation Report (CER), Labeling & IFU.
  - *Seen in:* Rimsys, MasterControl.
  - *Priority:* `common`.
  - *Spine mapping:* Field `technical_sections_summary` on `RegulatorySubmission`.

### 2. Registration & Listing Management
- **Global Market Registration & License Directory** — Multi-jurisdiction catalog of active, pending, expired, and under-renewal market authorizations across target countries and health authorities.
  - *Seen in:* Veeva Vault Registrations, Rimsys, RegDesk, ArisGlobal.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* New model `ProductRegistration` (`QREG-`), linking to `core.Party` (agency/notified body).
- **Establishment Registration & Economic Operator Records** — Tracking legal manufacturer, FDA Establishment Identifier (FEI), Registration Number, EUDAMED Actor ID (SRN), and Authorized Representative appointments (EU AR, UKRP, US Agent).
  - *Seen in:* Rimsys, RegDesk, Veeva.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* `ProductRegistration` fields for establishment ID, local representative (`core.Party`), and licensing attributes.
- **License Expiration & Renewal Schedule** — Automated countdown of license validity periods, annual listing verification dates, and fee due dates with visual urgency alerts.
  - *Seen in:* RegDesk, Rimsys, MasterControl.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* Date fields `expiration_date`, `renewal_due_date` with helper properties and filter support.

### 3. Regulatory Correspondence & Commitments
- **Agency Communication & Deficiency Logging** — Systematic logging of inbound and outbound official communications with regulatory agencies and notified bodies (deficiency letters, formal inquiry notices, meeting minutes, clearance letters).
  - *Seen in:* Veeva, MasterControl, Rimsys, IQVIA.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* New model `RegulatoryCommitment` (`QCOM-`), linking to `RegulatorySubmission` and `core.Party`.
- **Regulatory Commitment Tracking & Response Deadlines** — Formal commitments made to health authorities (post-market study delivery, annual reports, analytical batch validation, labeling changes) with strict due dates, assigned owners, and agency acceptance verification.
  - *Seen in:* Veeva MedTech RIM, Ennov, ArisGlobal, MasterControl.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* `RegulatoryCommitment` category, milestone due date, response status, verification sign-off.
- **Overdue Commitment & Escalation Warnings** — Identifying pending commitments within 30/60/90-day response windows or past agency deadlines to prevent regulatory sanctions.
  - *Seen in:* Veeva, Rimsys, RegDesk.
  - *Priority:* `common`.
  - *Spine mapping:* View queries, badge styling (`badge-red` / `badge-amber`), and dashboard metrics.

### 4. Post-Market Surveillance (PMS) & Periodic Reporting
- **PSUR / PMS Periodic Safety Assessment** — Compilation and tracking of Periodic Safety Update Reports (PSUR for EU MDR Class IIa/IIb/III, FDA 522 postmarket studies, annual post-approval reports).
  - *Seen in:* Veeva MedTech, Rimsys, MasterControl, IQVIA.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* New model `PostMarketSurveillanceReport` (`QPMS-`), linking to `ProductRegistration` and `accounts.User`.
- **Safety Data Synthesis & Incident Aggregation** — Aggregation of post-market sales volumes, complaint frequency, vigilance reportable events, and field safety corrective actions (FSCA) over the evaluation timeframe.
  - *Seen in:* Rimsys, Veeva, Cority.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* Metric fields on `PostMarketSurveillanceReport` (units sold/distributed, total complaints, reportable incidents, serious injuries, recalls/field actions).
- **Benefit-Risk Profile Conclusion & PMCF Actions** — Formal determination whether the clinical benefit-risk ratio remains favorable, identifying newly emerged residual risks or requiring Post-Market Clinical Follow-up updates.
  - *Seen in:* Rimsys, MasterControl, OpenRegulatory.
  - *Priority:* `table-stakes`.
  - *Spine mapping:* `benefit_risk_conclusion` choices, `pmcf_action_required` boolean, and next reporting schedule.

### 5. Regulatory Intelligence & Dashboard (Beyond the bullets)
- **Executive Regulatory Overview & Metric Dashboard** — High-level KPI visualization: Active Global Registrations, Submissions by Status, Commitments by Due Window, and PSUR Reporting Schedule.
  - *Seen in:* Veeva, Rimsys, RegDesk.
  - *Priority:* `common`.
  - *Spine mapping:* Dedicated overview/dashboard view in `RegulatorySubmissions` providing real-time compliance metrics.

---

## Recommended build scope (this pass — 4 models)

Following NavERP's strict 1–4 model build scope, Sub-module 12.17 will be implemented in `apps/quality/` under the PascalCase sub-module package `RegulatorySubmissions` with 4 tenant-scoped models:

1. **`RegulatorySubmission`** [`QSUB-`]
   - **Purpose:** Manages pre-market and post-market submission packages and dossiers (510(k), PMA, CE Technical Files, De Novo, IND, NDA, Health Canada MDL).
   - **Key Fields:** `tenant`, `number` (`QSUB-#####`), `title`, `submission_type` (510K, PMA, DE_NOVO, CE_TECH_FILE, HDE, IND, NDA, HEALTH_CANADA, PMDA, NMPA, OTHER), `target_authority` (`ForeignKey('core.Party')`), `org_unit` (`ForeignKey('core.OrgUnit')`), `product_name`, `product_code`, `device_class` (CLASS_I, CLASS_IIA, CLASS_IIB, CLASS_III, UNCLASSIFIED), `application_number`, `status` (DRAFT, AUTHORING, INTERNAL_REVIEW, SUBMITTED, UNDER_REVIEW, DEFICIENCY_RESPONSE, APPROVED_CLEARED, REJECTED, WITHDRAWN), `planned_submission_date`, `actual_submission_date`, `decision_date`, `lead_author` (`ForeignKey(settings.AUTH_USER_MODEL)`), `qa_approver` (`ForeignKey(settings.AUTH_USER_MODEL)`), `technical_dossier` (`ForeignKey('quality.ControlledDocument')`), `technical_sections_summary`, `notes`.
   - **Properties & Utilities:** `is_submitted`, `is_approved`, `days_under_review`.

2. **`ProductRegistration`** [`QREG-`]
   - **Purpose:** Tracks global market authorizations, establishment registrations, national device listings, and license renewal lifecycles across jurisdictions.
   - **Key Fields:** `tenant`, `number` (`QREG-#####`), `registration_title`, `registration_type` (PRODUCT_LICENSE, ESTABLISHMENT_REGISTRATION, NATIONAL_LISTING, CE_CERTIFICATE, IMPORT_PERMIT), `jurisdiction_country`, `regulatory_authority` (`ForeignKey('core.Party')`), `authorized_representative` (`ForeignKey('core.Party')`), `product_name`, `product_code`, `intended_purpose`, `license_certificate_number`, `establishment_id` (FEI / SRN / DUNS), `status` (ACTIVE, PENDING_RENEWAL, IN_APPLICATION, SUSPENDED, EXPIRED, WITHDRAWN), `initial_approval_date`, `effective_date`, `expiration_date`, `renewal_due_date`, `renewal_lead_days` (default 90), `regulatory_lead` (`ForeignKey(settings.AUTH_USER_MODEL)`), `linked_submission` (`ForeignKey('quality.RegulatorySubmission')`), `notes`.
   - **Properties & Utilities:** `is_active`, `days_to_expiration`, `is_overdue_renewal`, `urgency_status`.

3. **`RegulatoryCommitment`** [`QCOM-`]
   - **Purpose:** Records official health authority communications, deficiency requests, meeting minutes, and tracks post-clearance regulatory commitments and deadlines.
   - **Key Fields:** `tenant`, `number` (`QCOM-#####`), `title`, `commitment_type` (AGENCY_DEFICIENCY, POST_APPROVAL_STUDY, ANNUAL_REPORT, LABELING_UPDATE, STABILITY_MONITORING, INSPECTION_483_RESPONSE, PMCF_COMMITMENT, OTHER), `regulatory_agency` (`ForeignKey('core.Party')`), `linked_submission` (`ForeignKey('quality.RegulatorySubmission')`), `linked_registration` (`ForeignKey('quality.ProductRegistration')`), `linked_inspection` (`ForeignKey('quality.RegulatoryInspectionHost')`), `agency_reference_number`, `correspondence_date`, `commitment_description`, `responsible_owner` (`ForeignKey(settings.AUTH_USER_MODEL)`), `due_date`, `completion_date`, `status` (OPEN, IN_PROGRESS, SUBMITTED_TO_AGENCY, AGENCY_ACCEPTED, OVERDUE, WAIVED), `verification_method`, `agency_feedback`, `notes`.
   - **Properties & Utilities:** `is_overdue`, `days_remaining`.

4. **`PostMarketSurveillanceReport`** [`QPMS-`]
   - **Purpose:** Compiles periodic safety update reports (PSUR), Post-Market Clinical Follow-up (PMCF) evaluations, and post-market vigilance trend assessments.
   - **Key Fields:** `tenant`, `number` (`QPMS-#####`), `report_title`, `report_type` (PSUR, PMS_REPORT, PMCF_EVALUATION, VIGILANCE_TREND, ANNUAL_SAFETY_REPORT), `product_registration` (`ForeignKey('quality.ProductRegistration')`), `device_model_family`, `reporting_period_start`, `reporting_period_end`, `units_distributed`, `total_complaints_count`, `serious_incidents_count`, `field_actions_count`, `benefit_risk_conclusion` (FAVORABLE, ACCEPTABLE_WITH_MONITORING, UNFAVORABLE_ACTION_REQUIRED), `benefit_risk_rationale`, `pmcf_action_required` (boolean), `pmcf_action_summary`, `status` (DRAFT, IN_REVIEW, APPROVED, SUBMITTED_TO_AUTHORITY, ARCHIVED), `prepared_by` (`ForeignKey(settings.AUTH_USER_MODEL)`), `approved_by` (`ForeignKey(settings.AUTH_USER_MODEL)`), `approval_date`, `next_report_due_date`, `notes`.
   - **Properties & Utilities:** `complaint_rate_pct`, `serious_incident_rate_pct`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Electronic Signature Manifest & Multi-factor Signatures** → Sub-module 12.1 (`apps/quality/models/DocumentControl/ElectronicSignatures.py`). Sibling model `ElectronicSignatureRecord` provides 21 CFR Part 11 signatures for locking submissions and PSURs.
- **Design History File (DHF) & Verification Matrices** → Sub-module 12.2 (`apps/quality/models/DesignControls/`).
- **Product Risk Management & Hazard Analysis** → Sub-module 12.3 (`apps/quality/models/RiskManagement/RiskAssessments.py`).
- **Post-Market Complaints Intake & Root Cause** → Sub-module 12.13 (`apps/quality/models/CustomerComplaints/CustomerComplaints.py`).
- **Individual Medical Device Reports (MDR) & Vigilance Reporting** → Sub-module 12.13 (`apps/quality/models/CustomerComplaints/RegulatoryReports.py`).
- **Facility & Regulatory Inspection Hosting (FDA 483 / Notified Body Audits)** → Sub-module 12.11 (`apps/quality/models/AuditManagement/RegulatoryInspectionHosts.py`).

---

## Deferred (later passes / integrations)

- **Direct Gateway Integration (FDA ESG / eSubmitter / AS2 connector)**: Automated direct electronic file transfer protocol integration with FDA Electronic Submissions Gateway or EUDAMED M2M REST APIs.
- **Regulatory Intelligence Crawlers / Horizon Scanning Webhooks**: Automated scraping and subscription feeds for daily Federal Register notices, EU MDR MDCG guidance updates, or Health Canada notices.
- **eCTD XML Dossier Compiler Engine**: Specialized XML backbone builder for pharmaceutical eCTD Module 1-5 schemas (deferred to enterprise integration or specialized CLI tool).
