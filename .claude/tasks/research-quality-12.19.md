# Research — Sub-module 12.19: Laboratory Information Management (LIMS) (Module 12 — Quality Management System, `quality`)

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
- **Sibling models available to FK in `apps/quality/models/` (64 verified models):**
  - `ControlledDocument` (`QDOC-`): Standard operating procedures (SOP), analytical methods, validated testing specifications.
  - `ElectronicSignatureRecord` (`QSIG-`): 21 CFR Part 11 electronic signatures for test worksheet authorization, result approval, and OOS investigation closure.
  - `CalibrationGage` (`QGAG-`) & `CalibrationRecord` (`QCAL-`): Laboratory instruments, HPLC/GC chromatography systems, spectrophotometers, analytical balances, and calibration compliance status.
  - `NonConformanceReport` (`QNCR-`): Non-conformance records generated when samples or batches fail testing or require MRB quarantine.
  - `ProcessDeviation` (`QDEV-`): Lab testing deviations, temperature excursions in sample storage, or instrument run aborts.
  - `CapaInvestigation` (`QCAP-`): Root cause analysis and CAPA for confirmed out-of-specification (OOS) manufacturing defects or recurrent analytical errors.
  - `BatchRecord` (`QBMR-`): Electronic batch production records linked directly to sample testing results and QA release.
  - `IncomingInspectionLot` (`QIIL-`) & `FinalInspectionLot` (`QFQC-`): Incoming raw material and finished goods lots undergoing lab analysis.
- **Spine entities verified to exist (`apps/core/models/`, `apps/scm/models/`, `accounts`):**
  - `core.Tenant`: Multi-tenant workspace isolation.
  - `core.OrgUnit`: Quality control laboratories, analytical testing suites, sampling booths, stability chambers.
  - `core.Party` & `core.PartyRole`: External contract testing laboratories (CRO), analytical reagent vendors, instrument manufacturers.
  - `accounts.User` (`settings.AUTH_USER_MODEL`): Sample collection technicians, analytical chemists/analysts, QC lab supervisors, quality assurance reviewers.
  - `scm.WorkOrder`: Shop-floor production orders generating in-process or release samples.
- **Cross-module masters / unbuilt masters status (lessons L28, L29):**
  - Unbuilt masters: `Item`, `UOM`, `StockMove`, `LotSerial` (Module 5). Replaced with explicit tenant-scoped text/code fields: `item_code`, `item_name`, `lot_number`, `source_batch_number`, `unit_of_measure`.
  - Financial ledger: Owned by `apps/accounting`. Reagent costs and external testing lab fees reference standard fields or `accounting.GLAccount` without recreating ledgers.
- **Prefix availability audit (repo-wide verified, 0 collisions across 13 apps & `contract-*.md`):**
  - `QSMP`: **FREE** (Quality Lab Sample)
  - `QSPC`: **FREE** (Quality Lab Specification & Analytical Method)
  - `QWKS`: **FREE** (Quality Lab Test Worksheet & Execution)
  - `QOOS`: **FREE** (Quality Out-of-Specification Investigation)

---

## Leaders surveyed (with source links)

1. **LabWare LIMS** (LabWare 8 / LabWare Mobile) — *The global gold standard in laboratory informatics across pharmaceutical, clinical, and environmental testing laboratories.*
   - Strengths: Complete sample lifecycle management from accessioning to disposal, dynamic chain of custody (CoC) audit trail, automated specification comparison with multi-tier limits, integrated FDA/MHRA OOS Phase I/Phase II investigations, instrument calibration interlocks, and reagent inventory tracking.
   - Reference: [labware.com/solutions/lims](https://www.labware.com/solutions/lims)
2. **Thermo Scientific SampleManager LIMS & LES** (Thermo Fisher Scientific) — *Enterprise laboratory information management system and laboratory execution system (LES).*
   - Strengths: Unified sample management, electronic laboratory notebook (ELN) worksheets, automated instrument interfacing (Chromeleon CDS integration), rigid specification rules with automated OOS flagging, reagent and consumable lot expiration enforcement, and ALCOA+ compliance.
   - Reference: [thermofisher.com/samplemanager](https://www.thermofisher.com/us/en/home/industrial/informatics/laboratory-information-management-systems-lims/samplemanager-lims-software.html)
3. **LabVantage LIMS** (LabVantage Solutions) — *Pure web-native enterprise LIMS for life sciences, biotechnology, and regulated quality control.*
   - Strengths: Hierarchical storage location management (room -> freezer -> shelf -> rack -> box -> well), barcode labeling, structured test methods with versioning, test worksheet execution, built-in OOS and out-of-trend (OOT) workflows, and reagent lot tracking.
   - Reference: [labvantage.com/our-platform/lims](https://www.labvantage.com/our-platform/lims/)
4. **STARLIMS** (Abbott Informatics / Francisco Partners) — *Comprehensive LIMS with integrated ELN and Scientific Data Management System (SDMS).*
   - Strengths: Electronic chain of custody, analytical methods management, raw instrument data capture, analyst competency gating before test assignment, automated OOS root cause investigation trees, and lab reagent inventory management.
   - Reference: [starlims.com/solutions/lims](https://www.starlims.com/solutions/lims/)
5. **Veeva Vault LIMS** (Veeva Systems) — *Cloud-native LIMS designed specifically for pharmaceutical quality control.*
   - Strengths: Seamless connection between lab test execution, analytical specifications, sample tracking, and QMS deviations, CAPAs, and batch records within the unified Veeva Quality platform.
   - Reference: [veeva.com/products/vault-lims](https://www.veeva.com/products/vault-lims/)
6. **Autoscribe Informatics (Matrix Gemini LIMS)** — *Highly configurable LIMS platform for manufacturing QC, biobanking, and contract analytical testing.*
   - Strengths: Dual sample registration and batch logging, flexible specification limit profiles (warning limits vs action limits), automated testing worksheets, chain of custody logs, and multi-step OOS escalation.
   - Reference: [autoscribeinformatics.com/lims](https://www.autoscribeinformatics.com/lims)
7. **QBench LIMS** — *Modern cloud LIMS tailored for analytical, environmental, and clinical testing laboratories.*
   - Strengths: Sample accessioning, barcode scanning, test worksheets with automated calculations, instrument connectivity, reagent expiration tracking, and OOS incident management.
   - Reference: [qbench.com](https://www.qbench.com/)
8. **Labforward (Laboperator & Labregister)** — *Modular laboratory execution and reagent inventory system.*
   - Strengths: Smart reagent and reference standard lot tracking with automated expiration warnings, laboratory equipment status and calibration integration, and digital test protocols.
   - Reference: [labforward.io](https://www.labforward.io/)

---

## Regulatory Alignment & Industry Standards Framework

Sub-module 12.19 enforces international regulatory requirements for laboratory operations and data integrity:

1. **FDA Guidance for Industry: Investigating Out-of-Specification (OOS) Test Results for Pharmaceutical Production (May 2006 / Oct 2022 Revision):**
   - **Phase I: Laboratory Investigation**: Immediate assessment by analyst and supervisor examining sample integrity, analytical instrument suitability, reference standards, reagent lot validity, calculation accuracy, and raw test data. Must determine whether lab error occurred before invalidating results.
   - **Phase II: Full Investigation**: Multi-disciplinary review including production and QA to evaluate manufacturing operations, process deviations, and sampling procedures; authorized re-testing protocols with predefined sample sizes; and final batch disposition.
2. **ISO/IEC 17025:2017 (General requirements for the competence of testing and calibration laboratories):**
   - Clause 7.2 (Selection, verification and validation of methods): Management of analytical method specifications, validation records, and measurement uncertainty.
   - Clause 7.3 & 7.4 (Sampling and handling of test items): Systematic sample registration, identification labeling, storage conditions, and chain of custody tracking to preserve sample integrity.
   - Clause 6.4 & 6.5 (Equipment and Metrological Traceability): Qualification of analytical instruments, calibration status verification before use, and traceable reference standards.
3. **FDA 21 CFR Part 211 (§211.160 / §211.165 / §211.167) & EU GMP Chapter 6 (Quality Control):**
   - Scientifically sound specifications, standards, and test procedures.
   - Complete raw data records, test worksheets, calculation formulas, and supervisory review before batch release.
   - Reagent and standard solution labeling, expiration dates, and preparation logs.
4. **Data Integrity & ALCOA+ Principles (FDA 21 CFR Part 11, EU Annex 11, WHO Technical Report Series No. 996):**
   - **Attributable**: Every sample receipt, test entry, calculation, and approval tied to a specific user.
   - **Legible & Contemporaneous**: Real-time test result capture and immutable audit logs.
   - **Original & Accurate**: Direct capture of raw instrument data, automated limit comparisons, and tamper-evident records.

---

## Feature catalog (this sub-module only)

### 1. Sample Management & Chain of Custody
- **Sample Registration & Accessioning** — Rapid logging of raw material, in-process, finished product, environmental, stability, and retained samples with unique barcode identification · seen in: LabWare, SampleManager, LabVantage, QBench · priority: `table-stakes` · spine: new table `LabSample` [`QSMP-`] · buildable now.
- **Dynamic Chain of Custody (CoC) Audit Log** — Continuous timestamped tracking of sample possession, custody handoffs, transfers between analysts, and external shipping · seen in: LabWare, STARLIMS, Autoscribe · priority: `table-stakes` · spine: `LabSample.chain_of_custody_log` & custodian user link · buildable now.
- **Storage Location & Environmental Condition Tracking** — Multi-tier physical storage location mapping (facility, room, freezer, rack, shelf) with temperature condition enforcement (ambient, 2-8°C, -20°C, -80°C, desiccated) · seen in: LabVantage, LabWare, SampleManager · priority: `table-stakes` · spine: `LabSample` storage fields · buildable now.
- **Sample Lifecycle & Retention Management** — Lifecycle state machine (registered, received, in_testing, testing_completed, approved, rejected, disposed, retained) with retest and expiry date tracking · seen in: LabWare, SampleManager, Autoscribe · priority: `table-stakes` · spine: `LabSample` status & date fields · buildable now.

### 2. Test Method & Specification Management
- **Analytical Method & Specification Repository** — Centralized catalog of testing specifications across chemical, physical, microbiological, and chromatographic categories · seen in: SampleManager, LabWare, Veeva Vault LIMS · priority: `table-stakes` · spine: new table `LabSpecification` [`QSPC-`], FK `quality.ControlledDocument` · buildable now.
- **Multi-Tier Specification Limits** — Quantitative numeric acceptance limits (lower limit, upper limit, nominal target value, unit of measure) and qualitative text criteria · seen in: SampleManager, LabWare, Matrix Gemini · priority: `table-stakes` · spine: `LabSpecification` limits fields · buildable now.
- **Method Validation & Regulatory Reference Tracking** — Documentation of analytical method validation report references, validation dates, and scheduled periodic review cycles · seen in: LabWare, STARLIMS, Veeva · priority: `common` · spine: `LabSpecification` validation fields · buildable now.

### 3. Test Execution & Result Capture
- **Electronic Test Worksheet Assignment** — Digital worksheets assigned to qualified analysts, linking specific samples to required analytical specifications · seen in: SampleManager LES, LabWare, QBench · priority: `table-stakes` · spine: new table `LabTestWorksheet` [`QWKS-`], FK `LabSample`, FK `LabSpecification` · buildable now.
- **Raw Data Capture & Calculation Evaluation** — Structured capture of replicate raw data, instrument readings, final calculated results, and automated pass/fail limit verification · seen in: SampleManager, LabWare, STARLIMS · priority: `table-stakes` · spine: `LabTestWorksheet` results fields & property `is_within_specification` · buildable now.
- **Analytical Replicate Precision (% RSD)** — Automatic calculation and validation of relative standard deviation (% RSD) across analytical replicate readings · seen in: LabWare, SampleManager · priority: `common` · spine: `LabTestWorksheet.relative_standard_deviation` · buildable now.
- **Supervisory Review & Disposition Sign-off** — Two-tier analyst completion and supervisory quality review with disposition status (conforms, oos_flagged, inconclusive, invalid_run) · seen in: LabWare, Veeva, STARLIMS · priority: `table-stakes` · spine: `LabTestWorksheet` review fields · buildable now.

### 4. Out-of-Specification (OOS) Investigation
- **Phase I Laboratory Investigation Protocol** — Immediate structured checklist verifying sample integrity, instrument calibration, reagent validity, analyst technique, and calculation accuracy · seen in: LabWare, SampleManager, Veeva Vault LIMS · priority: `table-stakes` · spine: new table `OosInvestigation` [`QOOS-`], FK `LabTestWorksheet` · buildable now.
- **Lab Error Identification & Documented Cause** — Formal classification of confirmed laboratory errors (dilution error, instrument malfunction, contaminated standard) preventing false product rejections · seen in: LabWare, STARLIMS · priority: `table-stakes` · spine: `OosInvestigation` lab error fields · buildable now.
- **Phase II Manufacturing & Cross-Functional Investigation** — Expanded root cause investigation examining manufacturing equipment, batch records, raw material lots, and environmental parameters · seen in: LabWare, Veeva, MasterControl · priority: `table-stakes` · spine: `OosInvestigation` Phase II fields · buildable now.
- **Authorized Retesting Protocol & Final Disposition** — Controlled retest plan authorization, retest summary capture, final batch disposition, and closed-loop escalation to CAPA or NCR · seen in: LabWare, SampleManager, Veeva · priority: `table-stakes` · spine: `OosInvestigation` retest fields, FK `quality.CapaInvestigation`, FK `quality.NonConformanceReport` · buildable now.

### 5. Laboratory Equipment & Reagent Management
- **Instrument Verification & Calibration Interlocking** — Linking test worksheets to specific analytical gages/instruments, checking calibration validity and operational status · seen in: SampleManager, LabWare, Labforward · priority: `table-stakes` · spine: `LabTestWorksheet.instrument` FK `quality.CalibrationGage` · buildable now.
- **Reagent & Reference Standard Lot Traceability** — Recording specific analytical reagent lots, reference standards, and mobile phases used during testing, with lot numbers and expiration dates · seen in: SampleManager, LabWare, Labregister · priority: `table-stakes` · spine: `LabTestWorksheet` reagent and standard fields · buildable now.
- **Reagent Expiration Warning Interlock** — Automated identification and alert when reagents or standards are expired or nearing expiry · seen in: SampleManager, Labforward · priority: `common` · spine: `LabTestWorksheet` expiration verification & dashboard alert · buildable now.

---

## Recommended 4-Model Build Scope (Sub-module 12.19)

To deliver all 5 feature bullets of `### 12.19 Laboratory Information Management (LIMS)` while maintaining strict tenant isolation and consistency with Module 12 architecture, the recommended scope comprises **4 tenant-scoped models** subclassing `TenantNumbered`, plus a centralized **LIMS Command Center Dashboard**:

1. **`LabSample` [`QSMP-`]** (Sample Management & Chain of Custody):
   - Sample registration, unique barcode identifier, sample type/matrix, lot/batch links, sampling point, sampler/receipt metadata, storage location & conditions, custodian tracking, and chain of custody audit log.
2. **`LabSpecification` [`QSPC-`]** (Test Method & Specification Management):
   - Analytical specifications and methods, product/material code, category, approved SOP link (`quality.ControlledDocument`), lower/upper/nominal limits, unit of measure, qualitative criteria, and method validation records.
3. **`LabTestWorksheet` [`QWKS-`]** (Test Execution, Result Capture & Reagent/Instrument Verification):
   - Execution worksheet linking sample and specification, assigned analyst, instrument used (`quality.CalibrationGage`), reagent lot/expiry, standard lot/expiry, raw data capture, quantitative/qualitative results, automated limit evaluation, % RSD, and supervisory review.
4. **`OosInvestigation` [`QOOS-`]** (Out-of-Specification Investigation):
   - Two-phase OOS workflow (Phase I Lab Error Check + Phase II Manufacturing Investigation), assignable cause, hypothesis testing, authorized retest protocol, final disposition, and escalation links to `quality.CapaInvestigation` and `quality.NonConformanceReport`.
5. **`LimsDashboard` (`lims_dashboard`)**:
   - Executive command center displaying sample pipeline status, pending worksheets, OOS investigations by phase, expiring reagent warnings, and analytical turnaround time metrics.
