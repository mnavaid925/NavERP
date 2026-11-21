# Research — Sub-module 12.18: Traceability & Serialization (Module 12 — Quality Management System, `quality`)

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
- **Sibling models available to FK in `apps/quality/models/` (60 verified models):**
  - `ControlledDocument` (`QDOC-`): Master batch records (MBR), packaging specifications, UDI labeling standards, serialization SOPs, recall plans.
  - `ElectronicSignatureRecord` (`QSIG-`): 21 CFR Part 11 electronic signatures for batch production release, serialization commissioning, and product recall authorization.
  - `NonConformanceReport` (`QNCR-`): Non-conformance records generated during batch review, serialization discrepancies (duplicate serials), barcode grading failures.
  - `ProcessDeviation` (`QDEV-`): Manufacturing deviations during batch synthesis or packaging line aggregation.
  - `CapaInvestigation` (`QCAP-`): Root cause analysis and CAPA for counterfeit detections, recall events, or aggregation failures.
  - `FinalInspectionLot` (`QFQC-`) & `QualityReleaseAuthorization` (`QREL-`): Finished goods QC gate release tied to electronic batch records.
  - `CustomerComplaint` (`QCMP-`) & `FieldAction` (`QFMA-`): Customer complaints and regulatory field safety corrective actions triggering recall executions.
- **Spine entities verified to exist (`apps/core/models/`, `apps/scm/models/`, `accounts`):**
  - `core.Tenant`: Multi-tenant workspace isolation.
  - `core.OrgUnit`: Manufacturing facility, packaging line, cleanroom, warehouse, distribution center.
  - `core.Party` & `core.PartyRole`: Customers, contract packagers (CMO/CDMO), 3PL logistics distributors, health authorities (FDA, EMA, competent authorities).
  - `accounts.User` (`settings.AUTH_USER_MODEL`): Production supervisor, quality release officer, serialization engineer, recall coordinator.
  - `scm.WorkOrder`: Shop-floor production orders executed to manufacture the batch.
  - `scm.Shipment`: Outbound logistics shipments containing aggregated containers/pallets.
- **Cross-module masters / unbuilt masters status (lessons L28, L29):**
  - Unbuilt masters: `Item`, `UOM`, `StockMove`, `LotSerial` (Module 5). Replaced with explicit tenant-scoped text/code fields: `item_code`, `item_name`, `lot_number`, `serial_number`, `unit_of_measure`, `parent_sscc`.
  - Financial ledger: Owned by `apps/accounting`. Recall costs, quarantine write-offs, and reimbursement claims reference standard fields or `accounting.GLAccount` without recreating ledgers.
- **Prefix availability audit (repo-wide verified, 0 collisions across 13 apps & `contract-*.md`):**
  - `QBMR`: **FREE** (Quality Batch Manufacturing Record)
  - `QUDI`: **FREE** (Quality Unique Device Identification)
  - `QSER`: **FREE** (Quality Serialized Item / Unit)
  - `QRCL`: **FREE** (Quality Product Recall & Withdrawal Execution)

---

## Leaders surveyed (with source links)

1. **TraceLink** (Life Sciences Cloud / Opus Platform) — *Global benchmark in multi-enterprise serialization, DSCSA verification router services (VRS), product track and trace, and digital recall management.*
   - Sources: [tracelink.com - Serialization](https://www.tracelink.com/solutions/serialization), [tracelink.com - Track and Trace](https://www.tracelink.com/solutions/traceability), [tracelink.com - Product Recall](https://www.tracelink.com/solutions/digital-recalls)
2. **Antares Vision Group & Systech** (ATS Software Suite / UniSeries / UniSolve) — *Turnkey leader in packaging line serialization (L1-L3), parent-child aggregation, digital supply chain transparency, and tamper/diversion detection.*
   - Sources: [antaresvisiongroup.com - Serialization & Aggregation](https://www.antaresvisiongroup.com/solutions/track-trace/serialization-aggregation/), [systechone.com - Brand Protection](https://www.systechone.com/solutions/brand-protection/)
3. **OPTEL Group** (OPTEL Certa / IntelliTrack) — *Pioneer in pharmaceutical and medical device line-to-cloud serialization, automated parent-child aggregation, and cold chain temperature traceability.*
   - Sources: [optelgroup.com - Traceability](https://www.optelgroup.com/track-and-trace-solutions/), [optelgroup.com - Serialization Solutions](https://www.optelgroup.com/track-and-trace-solutions/serialization-solutions/)
4. **SAP Advanced Track and Trace for Pharmaceuticals (SAP ATTP)** — *Enterprise ERP serialization repository (L4/L5) managing serial number lifecycle, EPCIS event logging, regulatory compliance reporting, and batch genealogy.*
   - Sources: [sap.com - Advanced Track and Trace for Pharmaceuticals](https://www.sap.com/products/scm/track-and-trace-pharmaceuticals.html)
5. **Kezzler** — *Enterprise cloud platform for high-volume serialization-at-source, consumer authentication, supply chain visibility, and rapid recall orchestration.*
   - Sources: [kezzler.com - Serialization & Traceability](https://kezzler.com/solutions/traceability/), [kezzler.com - Brand Protection](https://kezzler.com/solutions/brand-protection/)
6. **Innovit & Rimsys** — *Global market leaders in medical device Unique Device Identification (UDI) management, Master Data governance, and machine-to-machine GUDID / EUDAMED submissions.*
   - Sources: [innovit.com - UDI Solutions](https://innovit.com/solutions/unique-device-identification/), [rimsys.io - UDI Management](https://rimsys.io/platform/udi-management)
7. **Visu UDI (by DDi)** — *Specialized multi-jurisdictional UDI platform with automated SmartRules engines for FDA GUDID, EU EUDAMED, Swissdamed, and AusUDID data compliance.*
   - Sources: [ddismart.com - Visu UDI](https://www.ddismart.com/udi-compliance-software)
8. **MasterControl & Veeva Systems** (MasterControl Manufacturing Excellence / Veeva Vault Quality) — *Standard in electronic Batch Production Records (eBPR), master recipe deviation capture, review-by-exception, and multi-tier quality release disposition.*
   - Sources: [mastercontrol.com - Electronic Batch Records](https://www.mastercontrol.com/manufacturing/electronic-batch-records/), [veeva.com - Vault QualityDocs](https://www.veeva.com/products/vault-qualitydocs/)

---

## Regulatory Alignment & Industry Standards Framework

Sub-module 12.18 must enforce global life sciences, medical device, and food safety regulations:

1. **U.S. FDA Drug Supply Chain Security Act (DSCSA) & EU FMD (2011/62/EU):**
   - Unit-level serialization with 2D DataMatrix (GTIN + Serial Number + Lot Number + Expiration Date).
   - Parent-child aggregation: unit -> bundle -> carton/shipper -> pallet (SSCC - Serial Shipping Container Code).
   - EPCIS (Electronic Product Code Information Services - GS1 standard): ObjectEvent, AggregationEvent, TransformationEvent, TransactionEvent tracking (Commissioning, Aggregation, Disaggregation, Decommissioning).
   - Verification Router Service (VRS) support for suspect and illegitimate product detection and rapid quarantine.
2. **FDA 21 CFR Part 830 & EU MDR 2017/745 / IVDR 2017/746 (Unique Device Identification - UDI):**
   - **Device Identifier (UDI-DI)**: Mandatory fixed numeric or alphanumeric code specific to a model/device (GTIN, HIBC, ICCBBA).
   - **Production Identifier (UDI-PI)**: Dynamic conditional elements including Lot Number, Serial Number, Expiration Date, Manufacturing Date, Distinct Identification Code.
   - **Basic UDI-DI**: European Union EUDAMED core identifier linking device models sharing common intended purpose and risk class.
   - **GUDID & EUDAMED Master Attributes**: Device description, commercial distribution status, MRI safety status, sterile packaging status, single-use flag, storage temperature conditions, FDA listing number.
3. **FDA 21 CFR Part 211 (§211.188 / §211.192) & EU GMP Annex 11 / Annex 16 (Batch Production Records & Release):**
   - Batch Manufacturing Record (BMR) execution, Bill of Materials (BOM) reconciliation, component lot genealogy (backward trace to supplier raw material and forward trace to finished distribution).
   - Review-by-exception: Automated verification that all associated in-process tests (IPQC 12.8), environmental logs (EHS 12.16), and final inspections (FQC 12.9) passed, and all NCRs/Deviations are closed prior to QA batch release.
   - 21 CFR Part 11 compliant electronic signatures for production supervisors and Qualified Persons (QP).
4. **FDA 21 CFR Part 7 (Enforcement Policy - Recalls) & ISO 13485:2016 §8.5.2:**
   - Recall classification: Class I (reasonable probability of serious adverse health consequences or death), Class II (temporary or medically reversible adverse health consequences), Class III (not likely to cause adverse health consequences / market withdrawal).
   - Rapid containment: Automated lot trace to identify all customer shipments within 2-4 hours; quarantine stop-ship flags across inventory.
   - Effectiveness checks: Percentage of recalled units recovered vs. destroyed vs. consumed in market; mock recall drills with timer benchmarks.

---

## Feature catalog (this sub-module only)

### 1. Batch & Lot Record Management
- **Electronic Batch Record (eBR/BMR) Tracking** — Lifecycle management of batch production records from draft through in-process execution, QA technical review, and final disposition · seen in: MasterControl, Veeva, SAP ATTP · priority: `table-stakes` · spine: new table `BatchRecord`, FK `scm.WorkOrder`, FK `quality.ControlledDocument` · buildable now.
- **Component Lot Genealogy & Bill of Materials Reconciliation** — Forward and backward trace linking raw material supplier lots to finished product batches, tracking actual vs theoretical yields · seen in: SAP ATTP, MasterControl, Antares Vision · priority: `table-stakes` · spine: `BatchRecord` fields & JSON component trace · buildable now.
- **Multi-Gate QA Batch Release Protocol** — Review-by-exception checklist verifying closed NCRs (`quality.NonConformanceReport`), approved deviations (`quality.ProcessDeviation`), passed final QC (`quality.FinalInspectionLot`), and release authorization · seen in: MasterControl, Veeva, TraceLink · priority: `table-stakes` · spine: `BatchRecord` disposition fields · buildable now.
- **Electronic Signature Batch Sign-Off** — Multi-tier dual sign-off (Production Supervisor + Quality Assurance Manager) with 21 CFR Part 11 timestamped audit capture · seen in: MasterControl, Veeva, TraceLink · priority: `table-stakes` · spine: `BatchRecord`, FK `quality.ElectronicSignatureRecord` · buildable now.

### 2. Unique Device Identification (UDI)
- **UDI Master Record & Identifier Assignment** — Cataloging Primary Device Identifier (UDI-DI / GTIN), Issuing Agency (GS1, HIBCC, ICCBBA), Device Class (Class I, IIa, IIb, III / A, B, C, D), and Basic UDI-DI (EUDAMED) · seen in: Innovit, Rimsys, Visu UDI · priority: `table-stakes` · spine: new table `DeviceIdentifier` · buildable now.
- **Regulatory Registry Status & Synchronization** — Pre-submission validation and synchronization tracking for FDA AccessGUDID and European Commission EUDAMED · seen in: Visu UDI, Rimsys, Innovit · priority: `table-stakes` · spine: `DeviceIdentifier` fields · buildable now.
- **Packaging & Labeling Specifications** — Definition of DI/PI barcode types (GS1 DataMatrix, GS1-128, HIBC 2D), clinical attributes, single-use, sterile barrier, and storage condition indicators · seen in: Visu UDI, Innovit · priority: `common` · spine: `DeviceIdentifier` fields · buildable now.

### 3. Serialization & Aggregation
- **Serial Number Allocation & Commissioning** — Lifecycle tracking of unit serial numbers (draft, allocated, commissioned, active, disaggregated, decommissioned, recalled) with GS1 SGTIN / SSCC formatting · seen in: TraceLink, Antares Vision, Kezzler, SAP ATTP · priority: `table-stakes` · spine: new table `SerializedItem` · buildable now.
- **Parent-Child Packaging Aggregation Tree** — Multi-tier hierarchy linking serialized units to bundles, cartons/shippers, and master shipping pallets (SSCC) with self-referential parent linking · seen in: Antares Vision, OPTEL, TraceLink, SAP ATTP · priority: `table-stakes` · spine: `SerializedItem.parent_container` (self-referential FK) · buildable now.
- **EPCIS Event Logging** — Tracking of GS1 EPCIS action events: Commissioning, Packing (Aggregation), Unpacking (Disaggregation), Shipping, Receiving, Decommissioning · seen in: TraceLink, SAP ATTP, Kezzler · priority: `table-stakes` · spine: `SerializedItem` status and event history · buildable now.

### 4. Track & Trace / Supply Chain Integrity
- **Real-Time Custody & Location Tracking** — Tracking of current custodian (`core.Party`), facility/line (`core.OrgUnit`), and associated outbound logistics shipment (`scm.Shipment`) · seen in: TraceLink, OPTEL, Kezzler · priority: `table-stakes` · spine: `SerializedItem` FKs · buildable now.
- **Product Authentication & Diversion Verification** — Tamper-evident cryptographic verification code hash (`verification_code`), cold chain flag, and detection of grey-market diversion or illegitimate duplicates · seen in: Systech, Kezzler, TraceLink · priority: `differentiator` · spine: `SerializedItem` fields · buildable now.

### 5. Recall & Withdrawal Execution
- **Recall Case Management & Classification** — Incident documentation specifying FDA/regulatory recall class (Class I, Class II, Class III, Market Withdrawal), hazard summary, and root cause · seen in: TraceLink, MasterControl, Veeva · priority: `table-stakes` · spine: new table `ProductRecall`, FK `quality.CustomerComplaint`, FK `quality.CapaInvestigation` · buildable now.
- **Rapid Trace & Scope Identification** — Immediate querying and containment hold of all distributed batches, affected serial number ranges, and customer delivery destinations · seen in: TraceLink, SAP ATTP, Antares Vision · priority: `table-stakes` · spine: `ProductRecall` batch & customer scope fields · buildable now.
- **Recall Effectiveness & Reconciliation Metrics** — Quantitative tracking of total quantity distributed, quarantined in warehouses, recovered from market, and confirmed destroyed, calculating recovery rate % · seen in: TraceLink, MasterControl · priority: `table-stakes` · spine: `ProductRecall` quantity fields & computed properties · buildable now.
- **Mock Recall Drills & Audit Verification** — Periodic simulated mock recall execution recording drill duration (target < 4 hours per ISO 13485 / BRCGS), effectiveness score, and audit readiness report · seen in: MasterControl, TraceLink · priority: `common` · spine: `ProductRecall` mock drill fields · buildable now.

---

## Recommended build scope (this pass: 4 models + Command Center)

Aim for 4 tenant-scoped models in `apps/quality/models/TraceabilitySerialization/`:

1. **`BatchRecord`** (`QBMR-`) — Electronic Batch Record (eBR/BMR) tracking production order, product code, batch/lot number, yields, component genealogy, review-by-exception checklist, and QA release disposition.
2. **`DeviceIdentifier`** (`QUDI-`) — Unique Device Identification master record for medical devices and life sciences products, handling Primary UDI-DI, Basic UDI-DI (EUDAMED), device classification, GUDID/EUDAMED submission status, and packaging attributes.
3. **`SerializedItem`** (`QSER-`) — Serialized product unit and packaging aggregation item (unit, bundle, carton, pallet), supporting parent-child aggregation hierarchies, EPCIS commissioning status, digital authentication verification hash, and supply chain chain-of-custody.
4. **`ProductRecall`** (`QRCL-`) — Product recall and market withdrawal execution record managing FDA recall classifications, affected lots/serials, regulatory notifications, rapid customer containment, recovery reconciliation rate %, and periodic mock recall drills.
5. **Command Center / Dashboard**: `TraceabilityDashboard` — Visual batch release status, parent-child aggregation & genealogy lookup, UDI regulatory submission readiness, cold chain & integrity telemetry, and active recall reconciliation metrics with CSV export.
