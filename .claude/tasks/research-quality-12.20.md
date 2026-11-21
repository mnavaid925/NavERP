# Research — Sub-module 12.20: Data Integrity & Electronic Records (Module 12 — Quality Management System, `quality`)

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
  - `"12.15"` (Process Validation & Verification): `ValidationProtocol`, `ProcessCapabilityStudy`, `ComputerSystemValidation`, `CleaningValidation`, Validation Dashboard
  - `"12.16"` (Environmental, Health & Safety / EHS): `HazardousMaterial`, `SafetyIncident`, `EnvironmentalMonitoringLog`, `WasteDisposalManifest`, EHS Dashboard
  - `"12.17"` (Regulatory Compliance & Submissions): `RegulatorySubmission`, `ProductRegistration`, `RegulatoryCommitment`, `PostMarketSurveillanceReport`, Regulatory Dashboard
  - `"12.18"` (Traceability & Serialization): `BatchRecord`, `DeviceIdentifier`, `SerializedItem`, `ProductRecall`, Traceability Dashboard
- **Sibling models available to FK in `apps/quality/models/` (68 verified models across 18 sub-modules):**
  - `ComputerSystemValidation` (`QCSV-`, 12.15): Computerized GxP systems inventory, GAMP 5 categories, qualification lifecycle, and hosting models.
  - `ControlledDocument` (`QDOC-`, 12.1): Governing SOPs, data integrity policies, validation master plans, system user manuals.
  - `DocumentChangeOrder` (`QDCR-`, 12.1): Engineering and procedural change orders linking to system changes.
  - `ElectronicSignatureRecord` (`QSIG-`, 12.1): Document-level signature manifestations.
  - `NonConformanceReport` (`QNCR-`, 12.5) & `ProcessDeviation` (`QDEV-`, 12.5): Data integrity breaches, unauthorized access deviations, aborted batch runs, and audit trail anomalies.
  - `CapaInvestigation` (`QCAP-`, 12.4): Root cause analysis and corrective actions for systemic data integrity deficiencies.
  - `QualityAudit` (`QAUD-`, 12.11) & `AuditFinding` (`QFND-`, 12.11): Data integrity audit findings from internal audits or external regulatory inspections.
- **Spine entities verified to exist (`apps/core/models/`, `accounts`):**
  - `core.Tenant`: Multi-tenant workspace isolation.
  - `core.OrgUnit`: Operating departments, QC laboratories, manufacturing suites, IT/computer system operational units.
  - `core.AuditLog`: Platform-level audit trail logs for data change tracking.
  - `accounts.User` (`settings.AUTH_USER_MODEL`): System owners, QA compliance reviewers, IT administrators, qualified persons, signature authors.
- **Cross-module masters / unbuilt masters status (lessons L28, L29):**
  - All foreign keys are tenant-scoped.
  - Platform audit logs and electronic record policies link to system entities and GxP computerized systems.
- **Prefix availability audit (repo-wide verified, 0 collisions across 13 apps & `contract-*.md`):**
  - `QREC`: **FREE** (Quality Electronic Record Policy & Register)
  - `QDIR`: **FREE** (Quality Data Integrity Risk Assessment)
  - `QATR`: **FREE** (Quality Audit Trail Review Record)
  - `QCCR`: **FREE** (Quality System Change Control)

---

## Leaders surveyed (with source links)

1. **Veeva Systems (Veeva Vault Quality / Vault QMS / Vault Validation Management)** — *Industry benchmark in cloud-based Life Sciences GxP compliance, 21 CFR Part 11 electronic records, audit trail verification, computerized system assurance (CSA), and automated change control.*
   - Sources: [veeva.com - Vault QMS](https://www.veeva.com/products/vault-qms/), [veeva.com - Vault Validation Management](https://www.veeva.com/products/vault-validation-management/)
2. **MasterControl (MasterControl Quality Excellence & Data Integrity Solutions)** — *Market leader in automated electronic batch records (eBR), GxP data integrity governance, audit trail analytics, and review-by-exception workflows.*
   - Sources: [mastercontrol.com - Data Integrity](https://www.mastercontrol.com/data-integrity/), [mastercontrol.com - Change Control](https://www.mastercontrol.com/change-control/)
3. **Scilife (Scilife Life Sciences QMS)** — *Pioneer in native ALCOA+ data integrity compliance, automated audit trail reviews (ATR), periodic system reviews (PSR), and 21 CFR Part 11 / EU Annex 11 electronic signatures.*
   - Sources: [scilife.io - Data Integrity in Life Sciences](https://www.scilife.io/blog/data-integrity-pharma), [scilife.io - Audit Trail Review](https://www.scilife.io/solutions/audit-trail-review)
4. **SimplerQMS** — *Turnkey medical device and pharma eQMS with pre-validated GAMP 5 packages, immutable 21 CFR Part 11 audit trails, electronic signature manifests, and integrated change controls.*
   - Sources: [simplerqms.com - 21 CFR Part 11 Software](https://www.simplerqms.com/21-cfr-part-11-software/), [simplerqms.com - Computer Software Assurance](https://www.simplerqms.com/computer-software-assurance-csa/)
5. **DocuSign Life Sciences Module & Validator** — *Global standard for 21 CFR Part 11 signature manifestations, dual-factor signer authentication, cryptographic tamper seals, and automated qualification reporting.*
   - Sources: [docusign.com - Life Sciences Solutions](https://www.docusign.com/solutions/industries/life-sciences), [docusign.com - 21 CFR Part 11 Compliance](https://www.docusign.com/trust/compliance/21-cfr-part-11)
6. **Sparta Systems / Honeywell (TrackWise Digital Change Control)** — *Enterprise standard for computerized system change management, GxP risk assessment, re-validation tracking, and Change Control Board (CCB) multi-disciplinary governance.*
   - Sources: [spartasystems.com - TrackWise Digital Change Control](https://www.spartasystems.com/trackwise-digital/change-control/)
7. **Qualio** — *Cloud-first quality management system enforcing ALCOA+ data integrity, secure time-stamped audit trails, and strict role-based access for fast-growing life sciences firms.*
   - Sources: [qualio.com - 21 CFR Part 11 Compliance](https://www.qualio.com/21-cfr-part-11)
8. **Körber (Werum PAS-X Data Integrity Suite)** — *Global pharmaceutical manufacturing benchmark for real-time audit trail monitoring, parameter exception detection, and ALCOA+ compliance on computerized shop floor systems.*
   - Sources: [koerber.com - Pharma Software PAS-X](https://www.koerber.com/en/pharma/software/pas-x)

---

## Regulatory Alignment & Industry Standards Framework

Sub-module 12.20 enforces key global standards for electronic records, electronic signatures, data integrity, and computerized system validation:

1. **U.S. FDA 21 CFR Part 11 (Electronic Records; Electronic Signatures):**
   - **§ 11.10 (Controls for closed systems):** Validation of systems, generation of accurate and complete copies of records, protection of records to enable accurate retrieval throughout the retention period, limiting system access to authorized individuals, secure computer-generated time-stamped audit trails recording the date and time of operator entries and actions, operational system checks, and authority checks.
   - **§ 11.50 (Signature manifestations):** Printed name of the signer, date and time when the signature was executed, and the meaning associated with the signature (such as authorship, review, approval, or verification).
   - **§ 11.70 (Signature linking):** Electronic signatures and handwritten signatures executed to electronic records shall be linked to their respective electronic records to ensure that the signatures cannot be excised, copied, or transferred to falsify an electronic record by ordinary means.
   - **§ 11.100 - § 11.300 (Electronic signature controls & dual authentication):** Unique user identification, two distinct identification components (e.g. username and password/token), and periodic testing of signature credentials.
2. **EU GMP Annex 11 (Computerised Systems):**
   - Principle of risk management throughout the lifecycle of the system.
   - Validation throughout lifecycle (qualification, testing, traceability).
   - Data storage: Protection against damage, regular backups, integrity testing, audit trails regularly reviewed.
   - Electronic signatures: Same legal impact as handwritten signatures, permanent linking to respective records.
   - Change and configuration management: Formal change control procedure for any change to a computerized system.
   - Periodic review: Computerized systems should be periodically reviewed to confirm they remain in a valid state.
3. **Data Integrity (ALCOA+) Principles (WHO TRS 996 Annex 5, FDA Data Integrity Guidance, MHRA Data Integrity GxP Guidance, PIC/S PI 041-1):**
   - **A**ttributable: Traceable to the individual who created/modified the record, including system ID and device ID.
   - **L**egible: Human-readable throughout the entire record retention period.
   - **C**ontemporaneous: Recorded at the exact time the event occurred, using synchronized network time protocol (NTP) clocks.
   - **O**riginal: First recording of data, or a verified true copy (with metadata preserved).
   - **A**ccurate: Free from errors, unapproved modifications, or undocumented edits.
   - **Complete:** All raw data, processed data, metadata, audit trails, and repeated runs preserved without selective deletion.
   - **Consistent:** Logical chronological sequence of actions and events without conflicting timestamps or out-of-order logs.
   - **Enduring:** Stored on durable, tamper-evident media resistant to degradation, loss, or unauthorized tampering.
   - **Available:** Readily accessible for review, audits, and health authority inspections throughout the required retention period.
4. **ISPE GAMP 5 (Second Edition) & FDA Computer Software Assurance (CSA):**
   - Risk-based validation and change control of computerized systems.
   - GxP impact assessment (direct GxP, indirect GxP, non-GxP).
   - Change classification (critical, major, minor, standard/emergency).
   - Change Control Board (CCB) multidisciplinary review and sign-off.
   - Pre-implementation testing (qualification, unit, regression, UAT) and post-implementation verification.
   - Rollback / contingency backout plan.
   - Periodic review intervals based on system risk criticality (e.g., annual or bi-annual).

---

## Feature catalog (this sub-module only)

### 1. Electronic Records & Signatures (ER/ES) — 21 CFR Part 11
- **Electronic Record Register & Governance Policy** — Register of regulated GxP electronic record types, target database models, retention schedules, backup frequency, legal hold status, and Part 11 / Annex 11 compliance certification · seen in: Veeva, SimplerQMS, Scilife · priority: `table-stakes` · spine: new table `ElectronicRecordPolicy`, FK `quality.ComputerSystemValidation` · buildable now.
- **Electronic Signature Profile & Manifestation Rules** — Definition of signature levels (author, peer reviewer, technical verifier, QA approver), dual-authentication requirements, re-entry of credentials, allowed meaning codes, and 21 CFR § 11.50 compliant visual signature manifestation stamping · seen in: DocuSign Life Sciences, Veeva, MasterControl · priority: `table-stakes` · spine: `ElectronicRecordPolicy` fields · buildable now.
- **Record Retention & Archival Protocol** — Retention period calculation (years post-manufacture, years post-expiry, permanent), archival format (PDF/A, immutable digital blob), cryptographic checksum hashing (SHA-256), and destruction authorization workflows · seen in: SimplerQMS, Qualio, DocuSign · priority: `common` · spine: `ElectronicRecordPolicy` retention fields · buildable now.

### 2. Data Integrity (ALCOA+)
- **ALCOA+ Data Integrity Risk Assessment (DIRA)** — Structured evaluation of a computerized system, lab instrument, or manufacturing workflow across all 9 ALCOA+ dimensions (Attributable, Legible, Contemporaneous, Original, Accurate, Complete, Consistent, Enduring, Available) · seen in: Scilife, MasterControl, Körber · priority: `table-stakes` · spine: new table `DataIntegrityAssessment`, FK `quality.ComputerSystemValidation`, FK `core.OrgUnit` · buildable now.
- **Data Integrity Risk Scoring & Gap Scoring** — Quantitative risk scoring (Likelihood of occurrence x Detectability x Impact on patient safety / product quality) generating a Data Integrity Risk Priority Number (DI-RPN) and criticality classification (Low, Medium, High, Critical) · seen in: Scilife, Veeva, Körber · priority: `table-stakes` · spine: `DataIntegrityAssessment` scoring fields · buildable now.
- **Remediation & Vulnerability Mitigation Tracking** — Gap identification, technical and procedural control assignment, target remediation deadlines, and link to CAPA investigations (`quality.CapaInvestigation`) or Non-Conformances (`quality.NonConformanceReport`) · seen in: Scilife, MasterControl · priority: `table-stakes` · spine: `DataIntegrityAssessment` mitigation fields · buildable now.
- **GxP Audit Trail Review (ATR) Protocol** — Scheduled periodic and event-driven (batch release, deviation closeout) review of electronic system and database audit trails, verifying absence of unapproved edits, timestamp anomalies, deleted records, or unauthorized administrative actions · seen in: Scilife, MasterControl, Körber, Veeva · priority: `table-stakes` · spine: new table `AuditTrailReview`, FK `quality.ComputerSystemValidation`, FK `accounts.User` · buildable now.
- **Audit Trail Anomaly Flagging & Exception Investigation** — Categorization of audit trail observations (clean, minor discrepancy, critical anomaly, data integrity violation), incident logging, and QA disposition sign-off · seen in: MasterControl, Körber, Scilife · priority: `table-stakes` · spine: `AuditTrailReview` exception fields · buildable now.

### 3. System Validation & Change Control (CSV)
- **Computerized System Change Control Request (CCR)** — Formal lifecycle management of changes to GxP software, infrastructure, cloud configurations, instrument firmware, and database schemas · seen in: TrackWise Digital, Veeva, MasterControl, SimplerQMS · priority: `table-stakes` · spine: new table `SystemChangeControl`, FK `quality.ComputerSystemValidation`, FK `core.OrgUnit` · buildable now.
- **GxP Impact & Validation Strategy Assessment** — Automated determination of GxP impact (Direct, Indirect, None), software category impact (GAMP Category 1-5), validation deliverables required (Validation Plan, FRS, Traceability Matrix update, IQ/OQ/PQ execution, User Training), and risk classification · seen in: TrackWise Digital, Veeva, SimplerQMS · priority: `table-stakes` · spine: `SystemChangeControl` impact fields · buildable now.
- **Change Control Board (CCB) Multi-Discipline Review** — Cross-functional review and approval matrix (System Owner, IT Security Officer, QA Validation Lead, Operations Lead) with electronic signature sign-off · seen in: TrackWise Digital, Veeva · priority: `table-stakes` · spine: `SystemChangeControl` approval fields · buildable now.
- **Implementation, Post-Execution Verification & Rollback Assurance** — Detailed deployment plan, regression testing summary, data backup confirmation, documented rollback / backout procedure, and final change release to live GxP production · seen in: TrackWise Digital, SimplerQMS · priority: `table-stakes` · spine: `SystemChangeControl` implementation fields · buildable now.
- **Periodic System Review (PSR) / Post-Implementation Verification** — Scheduled post-go-live evaluation confirming the change remained in control, user access lists remained valid, and system operated without unhandled deviations · seen in: Scilife, TrackWise Digital · priority: `common` · spine: `SystemChangeControl` & `AuditTrailReview` review fields · buildable now.

### 4. Beyond the Bullets: Executive Overview & Control Center
- **Data Integrity & Compliance Command Dashboard** — Live KPIs aggregating active 21 CFR Part 11 electronic record policies, ALCOA+ assessment risk distribution, pending audit trail reviews, open system change controls, overdue periodic evaluations, and data integrity health index · priority: `differentiator` · view/template: `DataIntegrityDashboard` · buildable now.

---

## Recommended Build Scope for This Pass (1–4 tenant-scoped models)

To achieve 100% compliance with NavERP.md and commercial leaders, Sub-module 12.20 implements **4 tenant-scoped models** plus a dedicated **Executive Dashboard**:

1. **`ElectronicRecordPolicy`** (Prefix: `QREC-`):
   - 21 CFR Part 11 & EU Annex 11 Electronic Record Register & Signature Profile.
   - Key fields: `system` (FK `quality.ComputerSystemValidation`), `record_type_name`, `record_category`, `is_part_11_regulated`, `is_annex_11_regulated`, `signature_requirement`, `reauthentication_required`, `dual_signature_required`, `retention_period_years`, `storage_format`, `backup_frequency`, `legal_hold`, `status`, `owner` (FK `accounts.User`), `qa_approver` (FK `accounts.User`), `policy_document` (FK `quality.ControlledDocument`).
   - Tenant-scoped, auto-numbered with collision retry, multi-tenancy isolated.

2. **`DataIntegrityAssessment`** (Prefix: `QDIR-`):
   - ALCOA+ Data Integrity Risk Assessment (DIRA).
   - Key fields: `system` (FK `quality.ComputerSystemValidation`), `assessment_title`, `org_unit` (FK `core.OrgUnit`), `lead_assessor` (FK `accounts.User`), `assessment_date`, `attributable_rating`, `legible_rating`, `contemporaneous_rating`, `original_rating`, `accurate_rating`, `complete_rating`, `consistent_rating`, `enduring_rating`, `available_rating`, `data_integrity_risk_level`, `identified_vulnerabilities`, `remediation_plan`, `capa` (FK `quality.CapaInvestigation`), `target_remediation_date`, `status`, `qa_approval_date`.
   - Evaluates compliance across all 9 ALCOA+ criteria, calculates overall DI risk level, and tracks remediation.

3. **`AuditTrailReview`** (Prefix: `QATR-`):
   - GxP Audit Trail Review & Anomaly Record.
   - Key fields: `system` (FK `quality.ComputerSystemValidation`), `review_title`, `review_type` (Routine Batch/Release, Scheduled Periodic, Event-Driven/Deviation, Authority Inspection Prep), `review_period_start`, `review_period_end`, `reviewer` (FK `accounts.User`), `review_date`, `audit_trail_source`, `records_reviewed_count`, `anomalies_identified`, `anomaly_severity`, `data_integrity_impact`, `investigation_details`, `linked_ncr` (FK `quality.NonConformanceReport`), `review_disposition` (Approved Clean, Approved with Remediations, Rejected - Investigation Required), `qa_lead` (FK `accounts.User`), `status`.
   - Records structured evidence of audit trail examination and captures integrity deviations.

4. **`SystemChangeControl`** (Prefix: `QCCR-`):
   - Computerized System Validation (CSV) Change Control Request.
   - Key fields: `system` (FK `quality.ComputerSystemValidation`), `change_title`, `change_type` (Software Upgrade, Infrastructure/Network, Cloud/SaaS Patch, Configuration Change, Security Patch, Database Schema, Decommissioning), `change_priority`, `gxp_impact`, `change_description`, `justification`, `data_integrity_impact`, `validation_deliverables_required`, `rollback_plan`, `requestor` (FK `accounts.User`), `system_owner` (FK `accounts.User`), `qa_lead` (FK `accounts.User`), `target_implementation_date`, `actual_implementation_date`, `post_implementation_review_date`, `status`, `closure_notes`.
   - Manages the full GxP change lifecycle from request, impact assessment, CCB review, implementation, verification to closure.

5. **Dedicated Executive Dashboard (`DataIntegrityDashboard`)**:
   - URL: `/quality/data-integrity/dashboard/`
   - Real-time statistics: Total Regulated Electronic Records, Active ALCOA+ Assessments, Overdue Audit Trail Reviews, Open System Change Controls, High-Risk Vulnerabilities, and GxP Compliance Health Index.

---

## What is deferred to later modules

- Biometric signature hardware device integrations (FIDO2 / fingerprint / PKI token smartcards) -> deferred to native hardware plugin / enterprise SSO integration.
- Automated real-time log ingestion agent directly streaming server syslog / database WAL logs -> handled by infrastructure monitoring tools (SIEM/Splunk/Datadog), with review records synthesized in NavERP.
- Automated machine-learning anomaly detection on raw database audit trails -> Module 23 (AI & Intelligent Automation).
