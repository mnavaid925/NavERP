# Research — Sub-module 12.15: Process Validation & Verification (Module 12 — Quality Management System, `quality`)

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
  - `"12.14"` (Management Review & Quality Planning):
    - `"Management Review Scheduling & Cadence": "quality:management_review_list"`
    - `"Quality Objectives & KPIs": "quality:quality_objective_list"`
    - `"Review Inputs & Data Compilation": "quality:management_review_input_list"`
    - `"Management Review Outputs & Decisions": "quality:management_review_action_list"`
    - `"Quality Planning & Continuous Improvement": "quality:management_review_board"`

- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py:8`, prefix `QDOC`): Standard operating procedures (SOPs), validation master plans (VMP), and analytical test procedures.
  - `DocumentChangeOrder` (`apps/quality/models/DocumentControl/DocumentChangeOrders.py:8`, prefix `QDCR`): Engineering/process change control orders triggering protocol revalidation.
  - `ElectronicSignatureRecord` (`apps/quality/models/DocumentControl/ElectronicSignatures.py:10`, prefix `QSIG`): 21 CFR Part 11 compliant digital signatures for protocol pre-approval, execution sign-off, and final summary approval.
  - `ProcessDeviation` (`apps/quality/models/NonConformance/ProcessDeviations.py:8`, prefix `QDEV`): Execution deviations, protocol test step anomalies, and process excursions.
  - `NonConformanceReport` (`apps/quality/models/NonConformance/NonConformanceReports.py:10`, prefix `QNCR`): Material and process non-conformances identified during qualification runs.
  - `CapaInvestigation` (`apps/quality/models/CapaManagement/CapaInvestigations.py:8`, prefix `QCAP`): Corrective actions triggered by failed qualifications or incapable processes.
  - `RiskAssessment` (`apps/quality/models/RiskManagement/RiskAssessments.py:6`, prefix `QRSK`): Process FMEA and GAMP 5 software risk assessments justifying validation testing depth.
  - `CalibrationGage` (`apps/quality/models/CalibrationAnalysis/CalibrationGages.py:9`, prefix `QGAG`): Metrology instruments and measuring equipment verified during IQ/OQ.
  - `MeasurementSystemAnalysis` (`apps/quality/models/CalibrationAnalysis/MeasurementSystemAnalyses.py:10`, prefix `QMSA`): Gage R&R studies validating measurement systems prior to capability runs.
  - `InProcessInspection` (`apps/quality/models/InProcessQuality/InProcessInspections.py:8`, prefix `QIPQ`): In-line sampling records providing dimensional and physical test data.
  - `ProcessParameterLog` (`apps/quality/models/InProcessQuality/ProcessParameterLogs.py:10`, prefix `QPAR`): Operating parameters (temperature, pressure, speed) logged during operational qualification and CPV.

- **Cross-module spine models available to FK:**
  - `core.Tenant` (`apps/core/models/Tenant.py:17`): Multi-tenant isolation foundation.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:5`): Manufacturing facilities, operational sites, quality departments, or engineering divisions.
  - `accounts.User` (`apps/accounts/models.py:52`): Validation protocol authors, execution leads, quality reviewers, and system owners.
  - `core.AuditLog` (`apps/core/models/AuditLog.py:5` + `write_audit_log` helper): Immutable audit trail for FDA 21 CFR Part 11, EU Annex 11, and ALCOA+ data integrity.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and atomic collision retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Facility / manufacturing plant site ownership. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | Validation leads, protocol executors, quality approvals. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Tamper-evident audit trail for 21 CFR Part 11 & Annex 11. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | Linked Validation Master Plan (VMP) and SOPs. |
| `quality.DocumentChangeOrder` exists | `apps/quality/models/DocumentControl/DocumentChangeOrders.py:8` | Change control notice triggering revalidation. |
| `quality.ProcessDeviation` exists | `apps/quality/models/NonConformance/ProcessDeviations.py:8` | Execution discrepancies and qualification test failures. |
| `quality.CapaInvestigation` exists | `apps/quality/models/CapaManagement/CapaInvestigations.py:8` | Root cause corrective actions for failed validations. |
| `quality.RiskAssessment` exists | `apps/quality/models/RiskManagement/RiskAssessments.py:6` | FMEA / GxP risk assessments driving validation depth. |
| `quality.ProcessParameterLog` exists | `apps/quality/models/InProcessQuality/ProcessParameterLogs.py:10` | Real-time process parameter runs for capability studies. |
| `quality.CalibrationGage` exists | `apps/quality/models/CalibrationAnalysis/CalibrationGages.py:9` | Metrology tools used during IQ/OQ protocol execution. |

### Spine entities verified NOT to exist (or unbuilt in Module 12 / ERP)

- **Module 5 unbuilt masters (`Item`, `LotSerial`, `UOM`):** Stand-in fields (`item_code`, `lot_number`, `equipment_tag`) are used for equipment, product family, and batch references, avoiding premature foreign keys to unbuilt tables while ensuring clean upgrade pathways.
- **Client-Side Heavy Statistical Toolboxes (e.g., Python RPy2 or proprietary desktop binaries):** All capability metrics ($C_p, C_{pk}, P_p, P_{pk}$) are computed directly using standard Python `math` and `statistics` routines inside the model/service layer, ensuring zero external C-extension binary dependencies.

### Auto-number Prefix Collision Check (0 collisions verified)

Automated regex scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QVAL` (Validation Protocol) -> **0 collisions** (Completely unique repo-wide)
- `QCPK` (Process Capability Study) -> **0 collisions** (Completely unique repo-wide)
- `QCSV` (Computer System Validation) -> **0 collisions** (Completely unique repo-wide)
- `QCLN` (Cleaning Validation) -> **0 collisions** (Completely unique repo-wide)

---

## Leaders surveyed (with source links)

1. **Kneat Gx (Kneat Solutions)** — Enterprise paperless validation lifecycle management software for biopharma, medical devices, and high-tech manufacturing. Standardizes the authoring, review, digital execution, and approval of qualification protocols (IQ/OQ/PQ) and Stage 1-3 process validation. Eliminates physical paper binders through online/offline test script execution, dynamic requirements traceability matrices (RTM), built-in deviation handling at the test-step level, and 21 CFR Part 11 / EU Annex 11 compliant digital signatures. Provides dedicated cleaning validation and Computer Software Assurance (CSA) workflows.
   - *Source:* https://kneat.com/product/
2. **ValGenesis VLMS (Validation Lifecycle Management System)** — Market standard paperless validation suite adopted by 30+ top tier global pharmaceutical enterprises. Covers equipment and facility qualification (DQ/IQ/OQ/PQ), cleaning validation life cycle (matrix worst-case calculations, swab/rinse limit management, dirty/clean hold time tracking), and computer system validation / CSA (GAMP 5 category alignment, URS-to-test traceability, regression change impact analysis). Includes automated revalidation scheduling and change-triggered reassessment.
   - *Source:* https://www.valgenesis.com/valgenesis-vlms
3. **MasterControl VxT (Validation Excellence Tool)** — Cloud-native risk-based validation system for regulated life science manufacturers. Implements modern GAMP 5 and FDA Computer Software Assurance (CSA) methodologies. Automates IQ/OQ/PQ protocol generation tailored to system configuration, dramatically shortening software validation and revalidation cycles during upgrades from months to hours. Features inspection-ready documentation, real-time audit logs, and integrated deviation escalation.
   - *Source:* https://www.mastercontrol.com/quality/vxt/
4. **Matrix Validate (Matrix One)** — Modern web-based CSV and equipment qualification platform designed for pharmaceutical, biotechnology, and MedTech companies. Enforces vertical traceability from User Requirements Specifications (URS) and Functional Specifications (FS) to test scripts and execution runs. Aligned strictly with EU GMP Annex 11, Annex 15, and 21 CFR Part 11. Features real-time trace matrices, discrepancy resolution, and cryptographically signed PDF validation summary packages.
   - *Source:* https://matrixone.health/matrix-validate/
5. **GoVal (GoValidation)** — Cloud-hosted paperless validation lifecycle management software. Provides end-to-end management of equipment qualification (IQ/OQ/PQ), utility validation, and computer systems validation (GAMP 5 Categories 1-5). Offers automated Requirements Traceability Matrix (RTM) generation, digital test execution, integrated deviation tracking, periodic review cadences, and vendor assessment records.
   - *Source:* https://govalidation.com/
6. **AmpleLogic Cleaning Validation Software** — Specialized pharmaceutical cleaning validation solution automating Maximum Allowable Carryover (MAC / MACO) calculations. Dynamically evaluates multiple limits (10 ppm general limit, 1/1000th minimum daily dose therapeutic limit, and toxicological Permitted Daily Exposure / PDE) to determine the most stringent worst-case threshold. Converts MACO into actionable swab limits ($\mu\text{g/cm}^2$) and rinse limits ($\text{mg/L}$ or $\text{ppm}$) across equipment trains, incorporating analytical method recovery factors and Dirty/Clean Hold Times (DHT/CHT).
   - *Source:* https://www.amplelogic.com/cleaning-validation-software/
7. **Veeva Vault Validation Management** — Part of the unified Veeva Vault Quality platform for life sciences. Unifies validation across computer systems, facilities, utilities, equipment, and cleaning processes. Features paperless protocol authoring, collaborative execution by multiple technicians, real-time evidence capture (screenshots, attachments), integrated discrepancy handling, and continuous change control integration with Vault QMS.
   - *Source:* https://www.veeva.com/products/vault-validation-management/
8. **Minitab Statistical Software (Quality Tools & Capability Analysis)** — The global benchmark for process capability analysis and statistical quality engineering. Computes potential within-subgroup capability ($C_p, C_{pk}$) and overall performance ($P_p, P_{pk}$) using rational subgrouping ($n > 1$) and individual moving range methods. Evaluates data against customer Upper/Lower Specification Limits (USL/LSL), computes expected defect rates in Parts Per Million (PPM), and determines capability adequacy against standard benchmarks ($C_{pk} \ge 1.33$ or $1.67$).
   - *Source:* https://www.minitab.com/en-us/products/minitab/
9. **InfinityQS ProFicient** — Enterprise Statistical Process Control (SPC) and real-time capability analytics engine. Evaluates process capability indices ($C_p, C_{pk}, P_p, P_{pk}, C_{pm}$) in real time from shop-floor and laboratory measurements. Provides automated out-of-control rule violation alerts, Assignable Cause and Corrective Action (ACCA) logging, and Continued Process Verification (CPV) dashboards aligned with FDA Stage 3 validation guidelines.
   - *Source:* https://www.infinityqs.com/solutions/quality-management

---

## Feature catalog (this sub-module only)

### 1. Process Validation Planning (IQ/OQ/PQ)
- **Validation Protocol Authoring & Stage Categorization** — Structured protocol setup defining validation scope, stage (DQ, IQ, OQ, PQ, PPQ, CPV, Revalidation), and acceptance criteria · seen in: Kneat Gx, ValGenesis, Veeva Vault · priority: `table-stakes` · spine: new table `ValidationProtocol` (`QVAL-`) · buildable now.
- **Equipment & Process Scope Identification** — Captures target equipment tag, line identifier, process name, and facility area with foreign key to `core.OrgUnit` · seen in: ValGenesis, MasterControl · priority: `table-stakes` · spine: `core.OrgUnit` + stand-in `equipment_tag` · buildable now.
- **Protocol Pre-Execution Approval Workflow** — Multi-tier approval routing requiring formal quality and technical sign-offs before physical execution starts · seen in: Kneat Gx, Matrix Validate, Veeva Vault · priority: `table-stakes` · spine: `ValidationProtocol` + `quality.ElectronicSignatureRecord` · buildable now.
- **Execution Run Logging & Summary** — Records execution start/completion timestamps, lead executor, protocol pass/fail determination, and objective evidence summary · seen in: Kneat Gx, GoVal, ValGenesis · priority: `table-stakes` · spine: `ValidationProtocol` · buildable now.
- **Qualification Discrepancy & Deviation Linking** — Immediate linkage of test-step discrepancies or parameter excursions to formal deviation records · seen in: Kneat Gx, MasterControl, ValGenesis · priority: `table-stakes` · spine: FK to `quality.ProcessDeviation` · buildable now.
- **Requirements Traceability Matrix (RTM)** — Bidirectional traceability linking user requirements and functional specs to protocol test scripts and execution results · seen in: Matrix Validate, GoVal, Kneat Gx · priority: `common` · spine: `ValidationProtocol` structured field / detail view · buildable now.
- **Post-Execution Quality Approval & Release** — Final sign-off by Quality Assurance authorizing commercial production release of the equipment or process · seen in: ValGenesis, Veeva Vault, MasterControl · priority: `table-stakes` · spine: `ValidationProtocol` + `quality.ElectronicSignatureRecord` · buildable now.
- **Tablet / Mobile Digital Script Execution Mode** — Touch-screen step-by-step checklist execution with real-time photo/attachment upload from the shop floor · seen in: Kneat Gx, ValGenesis · priority: `differentiator` · spine: HTMX execution view · buildable now.

### 2. Process Capability Studies (Cp/Cpk)
- **Specification Limit Configuration (USL / LSL / Nominal)** — Definition of customer or engineering tolerance limits (Upper Specification Limit, Lower Specification Limit, Target Nominal) · seen in: Minitab, InfinityQS ProFicient · priority: `table-stakes` · spine: new table `ProcessCapabilityStudy` (`QCPK-`) · buildable now.
- **Subgroup Configuration & Sampling Scheme** — Rational subgrouping setup capturing subgroup size ($n$, e.g. 5 parts per hour) vs. individual observations ($n=1$), total subgroup count, and total sample size ($N$) · seen in: Minitab, InfinityQS ProFicient · priority: `table-stakes` · spine: `ProcessCapabilityStudy` · buildable now.
- **Automated Capability Index Computation ($C_p, C_{pk}$)** — Potential within-subgroup capability calculation evaluating process spread against tolerance width and process centering:
  $$C_p = \frac{\text{USL} - \text{LSL}}{6 \cdot \sigma_{\text{within}}}, \quad C_{pk} = \min\left(\frac{\text{USL} - \bar{X}}{3 \cdot \sigma_{\text{within}}}, \frac{\bar{X} - \text{LSL}}{3 \cdot \sigma_{\text{within}}}\right)$$
  · seen in: Minitab, InfinityQS ProFicient · priority: `table-stakes` · spine: `ProcessCapabilityStudy` mathematical service · buildable now.
- **Automated Overall Performance Index Computation ($P_p, P_{pk}$)** — Overall process capability calculation based on total standard deviation across all combined observations, capturing long-term drift · seen in: Minitab, InfinityQS ProFicient · priority: `table-stakes` · spine: `ProcessCapabilityStudy` · buildable now.
- **Capability Benchmark Determination & RAG Status** — Automatic categorization of process capability against industry benchmarks:
  - Highly Capable ($C_{pk} \ge 1.67$, Six Sigma process)
  - Capable ($1.33 \le C_{pk} < 1.67$, 4-to-5 Sigma process)
  - Marginally Capable ($1.00 \le C_{pk} < 1.33$, prone to drift, requires 100% inspection/tight SPC)
  - Incapable ($C_{pk} < 1.00$, out of spec parts actively generated)
  · seen in: Minitab, InfinityQS ProFicient · priority: `table-stakes` · spine: `ProcessCapabilityStudy` choice field + UI badges · buildable now.
- **Expected Defect Rate Estimation (PPM / DPMO)** — Calculation of expected parts per million out of specification based on normal distribution Z-scores · seen in: Minitab · priority: `common` · spine: `ProcessCapabilityStudy` calculation service · buildable now.
- **Normality Check & Anderson-Darling Assessment** — Verification that continuous data meets the normality assumption prior to interpreting standard capability indices · seen in: Minitab · priority: `common` · spine: `ProcessCapabilityStudy` boolean & p-value field · buildable now.
- **Live SPC Control Chart & Histogram Rendering** — Interactive visualization showing histogram with overlaid normal curve and USL/LSL vertical limit markers · seen in: InfinityQS, Minitab · priority: `differentiator` · spine: SVG/HTML5 interactive canvas · buildable now.
- **Integration with In-Process Parameters** — Sourcing raw measurement data directly from shop-floor logs · seen in: InfinityQS ProFicient · priority: `common` · spine: FK to `quality.ProcessParameterLog` / `quality.InProcessInspection` · buildable now.

### 3. Computer System Validation (CSV & CSA)
- **GAMP 5 Software Categorization** — Formal categorization of computerized systems per ISPE GAMP 5 Second Edition:
  - Category 1: Infrastructure Software (OS, DB engine, virtualization)
  - Category 3: Non-Configurable Software (commercial off-the-shelf COTS)
  - Category 4: Configured Software (configurable applications, ERP/QMS/MES workflows)
  - Category 5: Custom Software (bespoke scripts, macros, custom code integrations)
  · seen in: MasterControl VxT, GoVal, Matrix Validate · priority: `table-stakes` · spine: new table `ComputerSystemValidation` (`QCSV-`) · buildable now.
- **GxP Criticality & Intended Use Assessment** — Rigorous determination of whether the software impacts patient safety, product quality, or data integrity · seen in: MasterControl VxT, Kneat Gx, GoVal · priority: `table-stakes` · spine: `ComputerSystemValidation` · buildable now.
- **FDA 21 CFR Part 11 & EU Annex 11 Applicability Checklist** — Structured evaluation of electronic records creation, electronic signature use, and audit trail retention requirements · seen in: Matrix Validate, Veeva Vault, ValGenesis · priority: `table-stakes` · spine: `ComputerSystemValidation` · buildable now.
- **Validation Strategy: Traditional CSV vs. Computer Software Assurance (CSA)** — Selection of validation framework: traditional documentation-heavy CSV vs. risk-based CSA focusing on unscripted/exploratory testing and critical thinking · seen in: MasterControl VxT, Kneat Gx, ValGenesis · priority: `common` · spine: `ComputerSystemValidation` · buildable now.
- **Validation Deliverables & Traceability Tracking** — Tracking completion status of core lifecycle artifacts: User Requirements Specification (URS), Functional Specification (FS), Validation Plan (VP), Test Scripts (IQ/OQ/PQ), and Validation Summary Report (VSR) · seen in: Matrix Validate, GoVal, Veeva Vault · priority: `table-stakes` · spine: `ComputerSystemValidation` + FKs to `quality.ControlledDocument` · buildable now.
- **System Inventory & Version Configuration Registry** — Centralized catalog of validated computerized systems, software version numbers, hosting environments (Cloud/SaaS vs. On-Premises), and vendor details · seen in: GoVal, Veeva Vault · priority: `table-stakes` · spine: `ComputerSystemValidation` · buildable now.

### 4. Cleaning Validation
- **Maximum Allowable Carryover (MAC / MACO) Multi-Criteria Calculation Engine** — Automated computation of carryover limits evaluating the most stringent of three industry criteria:
  1. *Therapeutic Daily Dose Criterion:* $\text{MACO} = \frac{\text{Min Daily Dose (Product A)} \times \text{Smallest Batch Size (Product B)}}{\text{Safety Factor (e.g. 1000)} \times \text{Max Daily Dose (Product B)}}$
  2. *10 ppm General Limit Criterion:* $\text{MACO} = 10 \times 10^{-6} \times \text{Smallest Batch Size (Product B)}$
  3. *Health-Based Exposure Limit (HBEL / Toxicological PDE):* $\text{MACO} = \frac{\text{PDE} \times \text{Smallest Batch Size (Product B)}}{\text{Max Daily Dose (Product B)}}$
  · seen in: AmpleLogic, ValGenesis · priority: `table-stakes` · spine: new table `CleaningValidation` (`QCLN-`) · buildable now.
- **Equipment Surface Area & Swab Limit Translation** — Converting total allowable carryover (MACO) into swab sample acceptance criteria ($\mu\text{g/cm}^2$ or $\mu\text{g/swab}$) based on total equipment contact surface area ($A_{\text{total}}$) and individual swab sampling template area ($A_{\text{swab}}$, e.g. $25\text{ cm}^2$ or $100\text{ cm}^2$):
  $$\text{Swab Limit} = \frac{\text{MACO} \times A_{\text{swab}}}{A_{\text{total}}}$$
  · seen in: AmpleLogic, ValGenesis, Kneat Gx · priority: `table-stakes` · spine: `CleaningValidation` · buildable now.
- **Rinse Limit Translation** — Converting total allowable carryover into maximum allowable concentration in the final rinse solvent volume ($\text{mg/L}$ or $\text{ppm}$):
  $$\text{Rinse Limit} = \frac{\text{MACO}}{\text{Total Rinse Volume}}$$
  · seen in: AmpleLogic, ValGenesis · priority: `table-stakes` · spine: `CleaningValidation` · buildable now.
- **Dirty Hold Time (DHT) & Clean Hold Time (CHT) Qualification** — Tracking validated maximum permissible hold duration before cleaning starts (DHT) and storage duration after cleaning before re-use (CHT) · seen in: ValGenesis, AmpleLogic, Kneat Gx · priority: `table-stakes` · spine: `CleaningValidation` · buildable now.
- **Analytical Method & Recovery Factor Integration** — Specifying analytical technique (HPLC, TOC, UV-Vis, Conductivity, Visual) and factoring analytical method recovery percentage (e.g. 80%) into swab results · seen in: AmpleLogic, Kneat Gx · priority: `common` · spine: `CleaningValidation` · buildable now.
- **Consecutive Successful Cleaning Runs Tracker** — Verification of the regulatory "3 consecutive successful full-scale runs" requirement to achieve validated status · seen in: ValGenesis, Kneat Gx · priority: `table-stakes` · spine: `CleaningValidation` · buildable now.
- **Visual Cleanliness Acceptance (Visually Clean Criterion)** — Primary physical inspection gate ("free from visible residues, particulate matter, and odor") before chemical sampling · seen in: AmpleLogic, ValGenesis · priority: `table-stakes` · spine: `CleaningValidation` · buildable now.

### 5. Revalidation & Periodic Review
- **Change-Triggered Revalidation Impact Assessment** — Evaluation of equipment alterations, process modifications, raw material source changes, or software patches to establish revalidation scope · seen in: ValGenesis, MasterControl VxT, GoVal · priority: `table-stakes` · spine: FK to `quality.DocumentChangeOrder` / `quality.ProcessDeviation` · buildable now.
- **Periodic Review Cadence & Due Date Monitoring** — Configurable review frequency (annual, biennial, triennial) with automated overdue alerts for validated equipment and systems · seen in: Veeva Vault, ValGenesis, GoVal · priority: `table-stakes` · spine: `ValidationProtocol`, `ComputerSystemValidation`, `CleaningValidation` · buildable now.
- **Continued Process Verification (CPV) / Ongoing Verification** — Periodic aggregation of commercial lot parameters and Cpk trends to verify the validated state remains in statistical control over time · seen in: Kneat Gx, ValGenesis, InfinityQS · priority: `common` · spine: `ProcessCapabilityStudy` + `ValidationProtocol` · buildable now.
- **Revalidation History & Audit Log** — Historical log tracking all previous validation protocol versions, execution outcomes, and re-qualification dates · seen in: Kneat Gx, MasterControl · priority: `table-stakes` · spine: `core.AuditLog` + `ValidationProtocol.parent_protocol` · buildable now.

---

## Recommended build scope (this pass — 4 models)

To cover all 5 NavERP.md feature bullets completely without bloat or gaps, we recommend a tightly integrated 4-model architecture in package `apps/quality/models/ProcessValidation/`:

### 1. `ValidationProtocol` (`NUMBER_PREFIX = "QVAL"`)
- **Justified by features:** Process Validation Planning (IQ/OQ/PQ), Equipment Qualification, Protocol Approval, Digital Execution, Revalidation & Periodic Review.
- **Key Fields:**
  - `protocol_number`: Auto-generated alphanumeric key (`QVAL-YYYY-NNNNN`).
  - `title`: Concise title of the validation protocol.
  - `protocol_stage`: Choices: `dq` (Design Qualification), `iq` (Installation Qualification), `oq` (Operational Qualification), `pq` (Performance Qualification), `ppq` (Process Performance Qualification), `cpv` (Continued Process Verification), `revalidation` (Change / Periodic Revalidation).
  - `status`: Choices: `draft` (Drafting), `in_review` (Technical / Quality Review), `approved_for_execution` (Approved - Ready for Run), `in_execution` (Testing in Progress), `deviation_hold` (Paused on Deviation), `execution_completed` (Run Completed), `final_approved` (QA Approved & Released), `rejected` (Disapproved), `superseded` (Superseded by New Study).
  - `revalidation_trigger`: Choices: `initial` (Initial Commissioning / New System), `periodic_review` (Routine Periodic Review), `change_control` (Process / Equipment Change Order), `deviation` (Corrective Action from NCR/Deviation), `regulatory` (Regulatory / Audit Requirement).
  - `target_type`: Choices: `equipment` (Production / Lab Equipment), `process` (Manufacturing Process), `facility_utility` (Cleanroom / HVAC / WFI Utility), `cleaning_procedure` (Cleaning Protocol), `computerized_system` (GAMP System).
  - `equipment_tag`: Free-text equipment identification / asset tag.
  - `process_name`: Free-text process or production step name.
  - `facility_area`: Facility room, cleanroom classification, or plant location.
  - `item_code`: Product code / component catalog reference (unbuilt Item stand-in).
  - `target_completion_date`: Target qualification target date.
  - `execution_start_date` / `execution_end_date`: Actual execution period timestamps.
  - `acceptance_criteria_summary`: Text summary of physical/functional acceptance criteria.
  - `execution_summary`: Technical summary of execution findings and test data.
  - `is_acceptance_criteria_met`: Boolean indicating overall pass/fail status.
  - `periodic_review_frequency_months`: Integer review interval (default 12 months).
  - `last_review_date` / `next_review_due`: Periodic review cadence tracker.
- **Foreign Keys:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE)`.
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True)` (Plant or department).
  - `lead_author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_validation_protocols")`.
  - `lead_executor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="executed_validation_protocols")`.
  - `qa_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_validation_protocols")`.
  - `vmp_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="validation_protocols")` (Linked Validation Master Plan).
  - `change_order`: `ForeignKey("quality.DocumentChangeOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_validation_protocols")` (Triggering DCO).
  - `linked_deviation`: `ForeignKey("quality.ProcessDeviation", on_delete=models.SET_NULL, null=True, blank=True, related_name="validation_protocols")` (Execution discrepancy).
  - `linked_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="validation_protocols")`.
  - `parent_protocol`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="revalidation_cycles")` (Previous qualification version).

### 2. `ProcessCapabilityStudy` (`NUMBER_PREFIX = "QCPK"`)
- **Justified by features:** Process Capability Studies (Cp/Cpk, Pp/Ppk), Rational Subgrouping, Specification Limits, Acceptance Criteria, Capability RAG Determination.
- **Key Fields:**
  - `study_number`: Auto-generated alphanumeric key (`QCPK-YYYY-NNNNN`).
  - `title`: Title of the capability study.
  - `parameter_name`: Critical Quality Attribute (CQA) or Critical Process Parameter (CPP) measured (e.g. "Fill Volume", "Tensile Strength", "Seal Temperature").
  - `parameter_category`: Choices matching `ProcessParameterLog.PARAMETER_CATEGORY_CHOICES` (`dimensional_thickness`, `temperature`, `pressure`, `speed_feed`, `torque`, `ph_chemical`, `humidity`, `voltage_current`, `cycle_time`, `other`).
  - `unit_of_measure`: Engineering unit label (e.g., "mm", "°C", "bar", "g", "mL").
  - `upper_spec_limit` (`usl`): Decimal engineering upper tolerance limit.
  - `lower_spec_limit` (`lsl`): Decimal engineering lower tolerance limit.
  - `target_nominal`: Decimal target process aim point.
  - `subgroup_size`: Integer rational subgroup size ($n \ge 1$; e.g., 5).
  - `number_of_subgroups`: Integer count of subgroups evaluated ($k$).
  - `total_samples`: Integer total parts sampled ($N = n \times k$).
  - `mean_value`: Calculated sample average ($\bar{X}$).
  - `within_subgroup_stdev`: Short-term within-subgroup variation ($\sigma_{\text{within}}$ using $\bar{R}/d_2$ or pooled $S$).
  - `overall_stdev`: Total overall sample standard deviation ($s_{\text{overall}}$).
  - `cp_index`: Potential capability index ($C_p$).
  - `cpk_index`: Potential capability index adjusted for centering ($C_{pk} = \min(C_{pl}, C_{pu})$).
  - `pp_index`: Overall performance index ($P_p$).
  - `ppk_index`: Overall performance index adjusted for centering ($P_{pk}$).
  - `expected_ppm`: Estimated non-conforming parts per million based on normal cumulative distribution.
  - `is_normally_distributed`: Boolean flag confirming normality assumption.
  - `capability_determination`: Choices: `highly_capable` ($C_{pk} \ge 1.67$), `capable` ($1.33 \le C_{pk} < 1.67$), `marginally_capable` ($1.00 \le C_{pk} < 1.33$), `incapable` ($C_{pk} < 1.00$).
  - `status`: Choices: `draft`, `data_collection`, `analyzed`, `approved`, `action_required`.
  - `process_name`: Free-text process stage identifier.
  - `equipment_tag`: Free-text machine or work center asset tag.
  - `item_code`: Product identifier stand-in.
  - `lot_number`: Production lot number stand-in.
- **Foreign Keys:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE)`.
  - `validation_protocol`: `ForeignKey("quality.ValidationProtocol", on_delete=models.SET_NULL, null=True, blank=True, related_name="capability_studies")` (Linked PQ/PPQ protocol).
  - `investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="capability_studies")`.
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_capability_studies")`.
  - `linked_parameter_log`: `ForeignKey("quality.ProcessParameterLog", on_delete=models.SET_NULL, null=True, blank=True, related_name="capability_studies")`.
  - `linked_calibration_gage`: `ForeignKey("quality.CalibrationGage", on_delete=models.SET_NULL, null=True, blank=True, related_name="capability_studies")`.
  - `linked_capa`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="capability_studies")` (Triggered if incapable).

### 3. `ComputerSystemValidation` (`NUMBER_PREFIX = "QCSV"`)
- **Justified by features:** Computer System Validation (CSV & CSA), GAMP 5 Categorization, 21 CFR Part 11 Evaluation, URS Traceability, System Inventory.
- **Key Fields:**
  - `csv_number`: Auto-generated alphanumeric key (`QCSV-YYYY-NNNNN`).
  - `system_name`: Commercial or internal software application name.
  - `version_release`: System release/build identifier (e.g., "v3.4.1").
  - `vendor_name`: Software supplier / commercial software vendor.
  - `hosting_model`: Choices: `cloud_saas` (Multi-tenant SaaS Cloud), `cloud_dedicated` (Dedicated Cloud IaaS/PaaS), `on_premises` (On-Premises Data Center), `hybrid` (Hybrid Environment), `embedded_firmware` (Embedded Instrument Controller).
  - `gamp_category`: Choices: `cat_1_infrastructure` (Category 1: Infrastructure Software), `cat_3_non_configured` (Category 3: Non-Configurable / COTS), `cat_4_configured` (Category 4: Configured Applications), `cat_5_custom` (Category 5: Custom Bespoke Code).
  - `gxp_impact`: Choices: `direct_gxp` (Direct GxP Impact - Patient Safety / Release), `indirect_gxp` (Indirect GxP Impact - Supporting Infrastructure), `non_gxp` (Non-GxP - Administrative Only).
  - `validation_approach`: Choices: `traditional_csv` (Traditional Scripted CSV per GAMP 5), `csa_risk_based` (FDA Computer Software Assurance / Critical Thinking).
  - `is_part_11_compliant`: Boolean indicating electronic records and signature controls are evaluated.
  - `requires_audit_trail`: Boolean confirming 21 CFR § 11.10(e) audit trail requirement.
  - `traceability_status`: Choices: `not_started`, `drafting`, `matrix_verified`, `gaps_identified`.
  - `urs_requirements_count`: Integer count of User Requirements Specifications evaluated.
  - `test_scripts_count`: Integer count of test scripts executed.
  - `deviations_found_count`: Integer count of open software anomalies during validation.
  - `status`: Choices: `inventory_only`, `planning`, `in_qualification`, `validated_live`, `periodic_review_due`, `decommissioned`.
  - `periodic_review_frequency_months`: Integer review cycle (default 24 months).
  - `last_review_date` / `next_review_due`: Periodic review tracking.
- **Foreign Keys:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE)`.
  - `system_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_computer_systems")`.
  - `quality_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="qa_computer_systems")`.
  - `validation_protocol`: `ForeignKey("quality.ValidationProtocol", on_delete=models.SET_NULL, null=True, blank=True, related_name="computer_system_validations")`.
  - `urs_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="csv_urs_docs")` (Linked URS).
  - `vsr_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="csv_vsr_docs")` (Linked Validation Summary Report).
  - `risk_assessment`: `ForeignKey("quality.RiskAssessment", on_delete=models.SET_NULL, null=True, blank=True, related_name="computer_system_validations")` (GxP Risk Assessment).

### 4. `CleaningValidation` (`NUMBER_PREFIX = "QCLN"`)
- **Justified by features:** Cleaning Validation, Maximum Allowable Carryover (MACO), Surface Area Swab/Rinse Limits, Analytical Method Recovery, Dirty/Clean Hold Times (DHT/CHT).
- **Key Fields:**
  - `cleaning_study_number`: Auto-generated alphanumeric key (`QCLN-YYYY-NNNNN`).
  - `title`: Title of the cleaning validation study.
  - `equipment_train_tag`: Free-text identifier for the target equipment train or machine.
  - `target_residue`: Name of active ingredient (API), detergent, or contaminant of interest.
  - `cleaning_agent_used`: Name of chemical cleaning agent / detergent used.
  - `worst_case_rationale`: Choices: `lowest_solubility` (Lowest Aqueous Solubility), `highest_toxicity_pde` (Lowest PDE / Highest Toxicity), `highest_potency` (Lowest Minimum Therapeutic Dose), `hardest_to_clean` (Viscous / Difficult Cleanability Matrix).
  - `calculation_basis`: Choices: `therapeutic_dose` (1/1000th Daily Therapeutic Dose), `ten_ppm_limit` (10 ppm General Limit Criterion), `toxicological_pde` (Permitted Daily Exposure / HBEL), `most_stringent` (Auto-Selected Most Stringent).
  - `min_daily_dose_active_mg`: Decimal minimum single daily dose of preceding active drug ($mg$).
  - `max_daily_dose_subsequent_mg`: Decimal maximum daily dose of next product ($mg$).
  - `smallest_batch_size_kg`: Decimal smallest batch size of next product ($kg$).
  - `safety_factor`: Decimal safety factor denominator (e.g., 1000 for oral, 10000 for parenteral).
  - `toxicological_pde_mg_day`: Decimal Permitted Daily Exposure limit ($mg/\text{day}$).
  - `calculated_maco_mg`: Decimal computed Maximum Allowable Carryover value in the shared equipment train ($mg$).
  - `total_surface_area_sqcm`: Decimal total product-contact surface area of the equipment ($cm^2$).
  - `swab_sampling_area_sqcm`: Decimal area sampled per swab coupon ($cm^2$, default 25.0).
  - `calculated_swab_limit_ug`: Decimal calculated maximum allowable residue per swab ($\mu g/\text{swab}$).
  - `rinse_volume_liters`: Decimal total rinse solvent volume used ($L$).
  - `calculated_rinse_limit_ppm`: Decimal calculated maximum allowable rinse solvent concentration ($ppm$ or $mg/L$).
  - `analytical_method`: Choices: `hplc` (High Performance Liquid Chromatography), `toc` (Total Organic Carbon), `uv_vis` (UV-Visible Spectrophotometry), `conductivity` (Conductivity Measurement), `visual_clean` (Visual Inspection Criterion).
  - `method_recovery_percentage`: Decimal analytical swab recovery factor (e.g., 85.0%).
  - `dirty_hold_time_hours`: Decimal maximum validated Dirty Hold Time (DHT) in hours.
  - `clean_hold_time_hours`: Decimal maximum validated Clean Hold Time (CHT) in hours.
  - `consecutive_successful_runs`: Integer count of successful qualification runs executed (target $\ge 3$).
  - `is_visually_clean`: Boolean verifying physical inspection acceptance criterion.
  - `worst_swab_result_ug`: Decimal highest residue quantity recovered across all swab sites ($\mu g$).
  - `worst_rinse_result_ppm`: Decimal highest concentration detected in rinse samples ($ppm$).
  - `cleaning_status`: Choices: `draft`, `protocol_approved`, `sampling_in_progress`, `analytical_testing`, `validated_pass`, `failed_recleaning_required`, `expired`.
  - `next_revalidation_date`: Date for routine periodic revalidation.
- **Foreign Keys:**
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE)`.
  - `validation_protocol`: `ForeignKey("quality.ValidationProtocol", on_delete=models.SET_NULL, null=True, blank=True, related_name="cleaning_studies")`.
  - `cleaning_sop`: `ForeignKey("quality.ControlledDocument", on_delete=models.PROTECT, related_name="cleaning_validation_studies")` (SOP governing cleaning).
  - `analytical_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cleaning_studies")`.
  - `qa_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_cleaning_studies")`.
  - `linked_deviation`: `ForeignKey("quality.ProcessDeviation", on_delete=models.SET_NULL, null=True, blank=True, related_name="cleaning_studies")`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **12.1 Document Control & Management** — Master template authoring, document vaulting, and general electronic signature infrastructure (e-signatures in 12.15 FK to `quality.ElectronicSignatureRecord`).
- **12.2 Design Controls & Development** — Design Verification, Design Validation, and Design History File (DHF) compilation for medical device development (12.15 covers manufacturing process and system validation).
- **12.3 Risk Management (ISO 14971 / FMEA)** — Risk evaluation matrices, preliminary hazard analysis, and product risk management plans (12.15 links to `quality.RiskAssessment` for GAMP 5 and process risk).
- **12.4 Corrective & Preventive Action (CAPA)** — Full root-cause 5-Whys and fishbone investigations for systemic process failures (12.15 logs failures and links to `quality.CapaInvestigation`).
- **12.5 Non-Conformance & Deviation Management** — Material quarantine holds, MRB disposition, and general non-conformance trending (12.15 links to `quality.ProcessDeviation`).
- **12.8 In-Process Quality Control (IPQC)** — Routine daily production run-charts, operator first-piece inspections, and Layered Process Audits (12.15 provides statistical capability studies that analyze logs from 12.8).
- **12.10 Calibration & Measurement System Analysis (MSA)** — Physical gage calibration schedules, out-of-tolerance investigations, and Gage R&R ANOVA evaluations (12.15 links to verified gages to confirm measurement accuracy before capability analysis).
- **12.14 Management Review & Quality Planning** — Quality objective scorecards and periodic executive leadership meetings (12.15 provides process capability and validation status inputs to 12.14).
- **12.16 Environmental, Health & Safety (EHS)** — Cleanroom particle counting, viable microbial monitoring, and HVAC classification (12.15 qualifies the utility/HVAC systems; routine monitoring belongs to 12.16).
- **12.19 Laboratory Information Management (LIMS)** — Sample chain of custody, instrument raw data capture, and Out-Of-Specification (OOS) investigations (12.15 records analytical method limits and final swab/rinse values).
- **12.20 Data Integrity & Electronic Records** — Enterprise-wide 21 CFR Part 11 policy configurations and system-wide ALCOA+ audit logging frameworks (12.15 applies GAMP 5 and Part 11 assessments to individual systems).

---

## Deferred (later passes / integrations)

- **Direct Automated Laboratory Instrument Data Acquisition (Chromatography / TOC Integration):** Automated ingestion of swab peak areas directly from Waters Empower or Thermo Chromeleon CDS via IoT/LIMS APIs. Deferred until Module 12.19 LIMS lands.
- **Shop-Floor PLC / OPC-UA Automated Data Collector:** Continuous automated ingestion of thousands of machine sensor data points per second for real-time capability tracking. Handled via standard CSV/manual import and FK to `ProcessParameterLog` in this build pass.
- **Dynamic Equipment 3D Heat-Map for Swab Sampling:** Graphical 3D visualization showing equipment hot-spots and sampling coupon locations. Deferred to future UI enhancements.
- **Automated Regression Test Runner for CSV / CSA:** Direct integration with automated software testing tools (Selenium, Playwright, Cypress) for live test execution against web applications. Handled via structured test script outcome records in this build unit.
