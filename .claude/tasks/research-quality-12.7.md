# Research — Sub-module 12.7: Incoming Quality Control (IQC) (Module 12 — Quality Management System, `quality`)

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
  - **`12.7` is the seventh sub-module of Module 12** (Incoming Quality Control / IQC; connects receiving dock goods receipts with formal sampling, testing, CoA verification, SPC capability analytics, and reject RMA workflows).

- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py`, prefix `QDOC`): Standard operating procedures, inspection instructions, engineering drawings, and reference CoA specifications.
  - `ElectronicSignatureRecord` (`apps/quality/models/DocumentControl/ElectronicSignatures.py`, prefix `QSIG`): 21 CFR Part 11 electronic signatures for formal lot usage decisions, MRB dispositions, and CoA acceptance.
  - `NonConformanceReport` (`apps/quality/models/NonConformance/NonConformanceReports.py`, prefix `QNCR`): Formal quality non-conformance reports triggered when an incoming inspection lot fails AQL or CoA specification comparison.
  - `QuarantineContainment` (`apps/quality/models/NonConformance/QuarantineContainments.py`, prefix `QCNT`): Physical/system segregation records locking defective or pending incoming material in quarantine storage.
  - `ProcessDeviation` (`apps/quality/models/NonConformance/ProcessDeviations.py`, prefix `QDEV`): Engineering deviations referenced when accepting an out-of-spec lot under controlled concession (`accepted_with_deviation`).
  - `SupplierQualificationAudit` (`apps/quality/models/SupplierQuality/SupplierQualificationAudits.py`, prefix `QSQA`): Approved Vendor List (AVL) records defining supplier qualification status (`approved`, `conditional`, `suspended`), dock-to-stock authorization (`dock_to_stock_eligible`), skip-lot eligibility (`skip_lot_approved`), and mandatory CoA requirements (`requires_coa`).
  - `SupplierCorrectiveAction` (`apps/quality/models/SupplierQuality/SupplierCorrectiveActions.py`, prefix `QSCA`): Formal SCARs issued to vendors for critical incoming lot rejections or recurring defects.
  - `SupplierQualityScorecard` (`apps/quality/models/SupplierQuality/SupplierQualityScorecards.py`, prefix `QSSC`): Periodic supplier performance ratings receiving objective incoming lot acceptance rates and defect PPM counts.

- **Cross-module spine models available to FK:**
  - `scm.PurchaseOrder` (`apps/scm/models/ProcurementManagement/PurchaseOrders.py`, prefix `PO`): Procurement purchase orders against which incoming goods were ordered and received.
  - `scm.GoodsReceiptNote` (`apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py`, prefix `GRN`): Warehouse receiving receipts that physically stage inbound shipments and trigger incoming inspection lots.
  - `core.Party` (`apps/core/models/Party.py`): Vendor / supplier party record.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py`): Quality department, receiving dock, inspection station, or quality testing laboratory.
  - `accounts.User` (`apps/accounts/models.py`): Quality inspectors, QC leads, QA engineers, and RMA coordinators.
  - `core.AuditLog` (`apps/core/models/AuditLog.py`): Immutable audit logging for lot usage decisions, CoA approvals, and RMA status transitions.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and atomic collision retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Multi-tenant isolation foundation across all tables. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Unified party spine for suppliers/vendors (`role="supplier"` or `"vendor"`). |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Department, plant, quality control unit, receiving staging area, or test lab. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | System users for QC inspectors, quality leads, and RMA release coordinators. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable tenant audit logging for usage decisions and CoA verifications. |
| `scm.GoodsReceiptNote` exists | `apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py:15` | SCM receipt record [GRN-] triggering incoming lot generation. |
| `scm.PurchaseOrder` exists | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:11` | Procurement purchase order [PO-] referenced in inspection lots and RMAs. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | Linked inspection instructions, part drawings, and test specs. |
| `quality.NonConformanceReport` exists | `apps/quality/models/NonConformance/NonConformanceReports.py:10` | Originating NCR [QNCR-] created when an incoming lot is rejected. |
| `quality.QuarantineContainment` exists | `apps/quality/models/NonConformance/QuarantineContainments.py:10` | Containment record [QCNT-] locking rejected material in quarantine. |
| `quality.SupplierQualificationAudit` exists | `apps/quality/models/SupplierQuality/SupplierQualificationAudits.py:10` | AVL record defining `dock_to_stock_eligible`, `skip_lot_approved`, `requires_coa`. |
| `quality.SupplierCorrectiveAction` exists | `apps/quality/models/SupplierQuality/SupplierCorrectiveActions.py:10` | Vendor SCAR [QSCA-] triggered by severe receiving rejections. |

### Spine entities verified NOT to exist (or unbuilt in Module 12)

- **Module 5 unbuilt masters:** `Item`, `LotSerial`, `UOM`, `StockMove` are not built yet. Quality incoming inspection models use documented tenant-scoped stand-ins (`item_code`, `item_name`, `lot_number`, `uom`) with clean migration hooks to Module 5 Inventory once landed (following lesson L28 and standard NavERP practice).
- **Physical stock move execution:** Inbound inventory movement into inspection staging and putaway into active or quarantine stock is deferred to Module 5 `StockMove`; 12.7 governs the quality gate, inspection execution, pass/fail usage decisions, and return authorizations.

### Candidate prefix collision check (repo-wide automated verification)

Automated ripgrep scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QIIP` (Quality Incoming Inspection Plan) -> **0 collisions** (Completely free)
- `QIIL` (Quality Incoming Inspection Lot) -> **0 collisions** (Completely free)
- `QCOA` (Quality Certificate of Analysis) -> **0 collisions** (Completely free)
- `QRMA` (Quality Return Material Authorization) -> **0 collisions** (Completely free; disambiguated from SCM customer `RMA`)

---

## Leaders surveyed (with source links)

1. **MasterControl (Incoming Quality / Receiving Inspection)** — Enterprise life sciences eQMS market leader for FDA 21 CFR Part 820 / QMSR and ISO 13485:2016 compliance. Features automated inspection lot creation upon goods receipt, ANSI/ASQ Z1.4 normal/tightened/reduced sampling tables, digital Certificate of Analysis (CoA) verification with automated specification comparison, dynamic skip-lot switching rules, closed-loop Non-Conformance (NCR) generation, and vendor return authorization (RMA) workflows.
   - *Source:* https://www.mastercontrol.com/quality-management/incoming-quality/
2. **ETQ Reliance (Receiving & Incoming Inspection)** — Enterprise quality platform connecting receiving docks to enterprise QMS. Features pre-configured inspection checklists, AQL sampling per ANSI/ASQ Z1.4 and ISO 2859-1, real-time lot dispositioning (Accepted, Accepted with Deviation, Rejected, Quarantine), digital CoA intake with automated parameter variance highlighting, integration with Approved Vendor Lists (AVL), and vendor return to vendor (RTV) / RMA tracking.
   - *Source:* https://www.etq.com/receiving-inspection/
3. **Sparta Systems / TrackWise Digital (Incoming Quality Management)** — Honeywell cloud quality solution managing receipt-to-release workflows. Includes configurable sampling plans (ANSI/ASQ Z1.4, c=0 / Squeglia zero-defect plans, 100% inspection), multi-characteristic inspection (dimensional, chemical, functional, packaging), CoA exception management, Statistical Process Control (SPC) data collection for critical-to-quality (CTQ) parameters, and supplier RMA coordination.
   - *Source:* https://www.spartasystems.com/trackwise-digital/
4. **Veeva Vault (Vault QualityDocs & Vault QMS Incoming Inspection)** — Cloud-native enterprise pharma and MedTech platform. Features electronic signature enforcement (21 CFR Part 11) for inspection lot release, digital CoA receipt and parameter boundary validation (min/max/nominal specifications), direct escalation of out-of-spec lots to Quarantine Containment and Supplier Corrective Actions (SCAR), and closed-loop supplier RMA tracking.
   - *Source:* https://www.veeva.com/products/vault-qms/
5. **QT9 QMS (Incoming Inspection & Quality Control Software)** — Regulated discrete manufacturing and MedTech QMS (ISO 9001, ISO 13485, AS9100). Provides embedded ANSI/ASQ Z1.4 sampling tables, skip-lot logic, real-time inspection data entry with immediate pass/fail verdict calculation, digital CoA capture and specification matching, SPC tracking with Cp/Cpk process capability metrics, and complete reject/RMA logging with carrier tracking and credit reconciliation.
   - *Source:* https://www.qt9software.com/incoming-inspection-software.aspx
6. **Greenlight Guru (Medical Device Receiving Inspection)** — Premier medical device quality platform designed for FDA 21 CFR 820.80 and ISO 13485 Clause 7.4.3 receiving verification. Aligns incoming inspection rigor with device risk classification and component criticality, supports ANSI/ASQ Z1.4 and c=0 sampling plans, enforces mandatory CoA verification prior to inventory release, and manages quarantine holds and supplier return authorizations.
   - *Source:* https://www.greenlight.guru/receiving-inspection-software
7. **ComplianceQuest (Receiving Inspection & Quality Control)** — Salesforce-native enterprise EQMS providing automated inspection lot creation from ERP goods receipt notifications, configurable sampling plans with AQL switching rules, digital CoA evaluation with automated parameter boundary checks, Statistical Process Control (SPC) trend charts with out-of-control alerts, and supplier RMA workflows linked to AP credit memos.
   - *Source:* https://www.compliancequest.com/receiving-inspection-software/
8. **Qualio (Receiving & Material Acceptance)** — Life sciences eQMS providing audit-ready incoming inspection checklists, CoA verification checkpoints, supplier qualification gatekeeping, quarantine dispositioning, and vendor return tracking.
   - *Source:* https://www.qualio.com/product/quality-control
9. **Arena QMS / PTC (Incoming Quality & Inspection Management)** — Discrete high-tech and medical electronics PLM/QMS linking incoming inspection plans directly to BOM components, engineering specifications, and revision levels, supporting sample inspection, CoA attachment, and supplier RMA management for defective components.
   - *Source:* https://www.arenasolutions.com/products/quality/

---

## Feature catalog (this sub-module only)

### Bullet 1 — Inspection Planning & Sampling (Sampling plan definition (ANSI/ASQ Z1.4), AQL levels, and inspection frequency)

- **Standard Sampling Plan Systems (ANSI/ASQ Z1.4 & ISO 2859-1)** — Formal implementation of international attribute sampling systems. Establishes Sample Size Code Letters (A through R) determined by Lot Size (e.g., 2–8, 9–15, 16–25, ... 500,001+) and General Inspection Levels (Level I - reduced discrimination, Level II - normal standard default, Level III - tightened discrimination) or Special Inspection Levels (S-1 through S-4 for high-cost or destructive testing). · seen in: MasterControl, ETQ Reliance, QT9, ComplianceQuest · priority: **table-stakes** · spine: `IncomingInspectionPlan.sampling_standard`, `inspection_level` · **buildable now**
- **Acceptance Quality Limit (AQL) Thresholds by Defect Class** — Defines maximum acceptable percent defective for distinct defect severity classifications:
  - *Critical AQL* (e.g. 0.065%, 0.10%, zero defects allowed $c=0$) — safety hazards, bio-incompatibility, non-compliance with legal/regulatory requirements.
  - *Major AQL* (e.g. 1.0%, 1.5%, 2.5%) — defects likely to cause functional failure, render product unmarketable, or prevent assembly.
  - *Minor AQL* (e.g. 4.0%, 6.5%) — cosmetic imperfections, minor packaging scuffs, or non-functional dimensional deviations.
  · seen in: All leaders · priority: **table-stakes** · spine: `IncomingInspectionPlan.aql_critical`, `aql_major`, `aql_minor` · **buildable now**
- **Zero-Defect ($c=0$ / Squeglia) Sampling Option** — Configurable zero-defect sampling plan option preferred in medical device and aerospace manufacturing (where accepting even one defective unit is prohibited by policy). · seen in: Greenlight Guru, TrackWise Digital, ComplianceQuest · priority: **table-stakes** · spine: `IncomingInspectionPlan.sampling_standard="c_zero"` · **buildable now**
- **Dynamic Inspection Rigor & Switching Rules** — Tracks switching states per ANSI/ASQ Z1.4:
  - `normal` (standard baseline)
  - `tightened` (automatically triggered when 2 out of 5 consecutive lots are rejected; increases sample size or lowers acceptance threshold)
  - `reduced` (triggered when 10 consecutive lots pass under normal inspection, supplier is AVL Grade A, and production is steady; reduces sample size by up to 60%)
  · seen in: MasterControl, ETQ Reliance, ComplianceQuest · priority: **table-stakes** · spine: `IncomingInspectionPlan.inspection_severity`, switching rule methods · **buildable now**
- **Inspection Frequency & Tiered Gating** — Configurable receipt frequency policies:
  - `every_lot` (100% of inbound shipments require inspection lot creation)
  - `skip_lot` (statistically justified sampling of 1 in $N$ lots for certified suppliers with `SupplierQualificationAudit.skip_lot_approved=True`)
  - `dock_to_stock` (direct inventory release with inspection bypass for suppliers with `SupplierQualificationAudit.dock_to_stock_eligible=True`)
  - `first_article` (comprehensive First Article Inspection / FAI per AS9102 for new tooling, suppliers, or design revisions)
  · seen in: ETQ Reliance, MasterControl, Arena QMS · priority: **table-stakes** · spine: `IncomingInspectionPlan.frequency_mode`, `skip_lot_interval` · **buildable now**
- **Inspection Characteristics Specification** — Definition of multi-parameter inspection criteria (dimensions, visual appearance, functional tests, hardness, tensile strength, packaging, label verification) with nominal values, upper/lower specification limits (USL/LSL), units of measure, and test methods. · seen in: All leaders · priority: **table-stakes** · spine: `IncomingInspectionPlan.characteristics` (structured JSON definition) · **buildable now**
- **Document & Revision Control Linkage** — Binds inspection plans to formal engineering drawings and test procedures in `quality.ControlledDocument` [QDOC-] to ensure inspection uses current, authorized revisions. · seen in: MasterControl, Greenlight Guru, Veeva Vault · priority: **common** · spine: `IncomingInspectionPlan.specification_document` (`quality.ControlledDocument`) · **buildable now**

### Bullet 2 — Goods Receipt & Inspection Execution (Physical inspection, dimensional checks, and functional testing protocols)

- **Goods Receipt Trigger & Lot Initialization** — Operational creation of an incoming inspection lot upon physical dock delivery against `scm.GoodsReceiptNote` [GRN-] and `scm.PurchaseOrder` [PO-]. Automatically links supplier (`core.Party`), item code/name, lot number, total received quantity, and selects active `IncomingInspectionPlan`. · seen in: All leaders · priority: **table-stakes** · spine: `IncomingInspectionLot` (new table, `NUMBER_PREFIX = "QIIL"`) · **buildable now**
- **Inspection Lot Lifecycle State Machine** — Closed-loop progression: `pending_receipt` -> `in_inspection` -> `sampling_complete` -> `completed` -> `cancelled`. · seen in: All leaders · priority: **table-stakes** · spine: `IncomingInspectionLot.status` · **buildable now**
- **Sample Size Determination & Quantity Accounting** — Computes required sample size from lot size using the inspection plan's ANSI/ASQ Z1.4 code letter table, and tracks:
  - `lot_quantity` (total quantity received at dock)
  - `sample_size` (statistically mandated sample count)
  - `inspected_quantity` (actual units tested by inspector)
  - `accepted_quantity` (conforming units released to stock)
  - `rejected_quantity` (defective units rejected)
  - `quarantine_quantity` (units placed on quality hold)
  · seen in: MasterControl, QT9, ETQ Reliance · priority: **table-stakes** · spine: `IncomingInspectionLot` quantity fields · **buildable now**
- **Physical, Dimensional & Functional Test Logging** — Guided inspection worksheet execution where inspectors record actual test observations across visual, dimensional, electrical, and functional protocols. Tracks tool/gage IDs used, calibration status, and environmental conditions. · seen in: QT9, TrackWise, ComplianceQuest · priority: **table-stakes** · spine: `IncomingInspectionLot.inspection_notes`, test execution summary · **buildable now**
- **Defect Classification & Counting** — Independent defect counters for `critical_defects`, `major_defects`, and `minor_defects`. Automatically evaluates defect counts against plan acceptance thresholds ($Ac$ / $Re$) to provide an instant mathematical recommendation. · seen in: All leaders · priority: **table-stakes** · spine: `IncomingInspectionLot.critical_defects`, `major_defects`, `minor_defects` · **buildable now**
- **Formal Usage Decision & Material Disposition** — Definitive quality authority disposition:
  - `accepted` (conforming lot released to inventory)
  - `accepted_with_deviation` (concession release requiring approved `quality.ProcessDeviation`)
  - `quarantined` (material locked in physical/system quarantine via `quality.QuarantineContainment` [QCNT-])
  - `rejected` (fails specification; triggers `quality.NonConformanceReport` [QNCR-] and `quality.QualityReturnAuthorization` [QRMA-])
  - `skip_lot_passed` (system-approved via skip-lot rules)
  · seen in: All leaders · priority: **table-stakes** · spine: `IncomingInspectionLot.usage_decision`, `usage_decision_by`, `usage_decision_at` · **buildable now**
- **Closed-Loop Quality Escalation** — Direct automatic or one-click creation of `quality.NonConformanceReport` [QNCR-] and `quality.SupplierCorrectiveAction` [QSCA-] when critical defects exceed allowable limits. · seen in: MasterControl, Veeva Vault, Greenlight Guru · priority: **table-stakes** · spine: `IncomingInspectionLot.non_conformance` (`quality.NonConformanceReport`), `scar` (`quality.SupplierCorrectiveAction`) · **buildable now**

### Bullet 3 — Certificate of Analysis (CoA) Management (Digital CoA receipt, specification comparison, and exception handling)

- **Digital CoA Receipt & Intake Logging** — Captures vendor-supplied Certificate of Analysis documentation upon shipment arrival: Certificate Number, Supplier/Manufacturer, Part/Item Number, Lot/Batch Number, Date of Manufacture (DOM), Expiry/Retest Date, Laboratory Accreditation (ISO/IEC 17025), and Authorized Signatory. · seen in: MasterControl, Veeva Vault, ComplianceQuest · priority: **table-stakes** · spine: `CertificateOfAnalysis` (new table, `NUMBER_PREFIX = "QCOA"`) · **buildable now**
- **CoA Lifecycle & Verification Status** — Tracks verification lifecycle: `pending_receipt` -> `received_under_review` -> `compliant` -> `non_compliant_rejected` -> `deviation_accepted`. · seen in: MasterControl, ETQ Reliance, Veeva Vault · priority: **table-stakes** · spine: `CertificateOfAnalysis.status` · **buildable now**
- **Multi-Parameter Specification Comparison Engine** — Captures structured analytical test parameters (e.g. Chemical Assay %, Moisture %, Heavy Metals PPM, Melting Point, Viscosity, Purity, Tensile Yield, Specific Gravity) with:
  - Test parameter name & test standard (e.g. USP <621>, ASTM D638, ISO 1133)
  - Specification lower limit (LSL), target, and upper limit (USL)
  - Supplier reported test result
  - Automated pass/fail verdict (`pass`, `fail`, `borderline`)
  · seen in: MasterControl, Veeva Vault, ComplianceQuest · priority: **table-stakes** · spine: `CertificateOfAnalysis.test_parameters` (structured JSON parameter matrix), `evaluate_parameters()` method · **buildable now**
- **Automated Conformance & Variance Detection** — System evaluates all vendor reported values against engineering limits, automatically computing `variance_count` and setting `is_within_spec` (boolean). Any parameter outside tolerance immediately flags the CoA as non-compliant. · seen in: MasterControl, Veeva Vault · priority: **table-stakes** · spine: `CertificateOfAnalysis.is_within_spec`, `variance_count` · **buildable now**
- **CoA Gating Enforcement** — If a supplier is flagged with `SupplierQualificationAudit.requires_coa = True`, the associated `IncomingInspectionLot` usage decision is strictly blocked from `accepted` disposition until a valid `CertificateOfAnalysis` in `compliant` status is recorded. · seen in: MasterControl, Greenlight Guru, ETQ · priority: **table-stakes** · spine: `IncomingInspectionLot.validate_coa_requirement()` · **buildable now**
- **Document Vault & Attachment Linking** — Links uploaded vendor PDF certificates to `quality.ControlledDocument` or stores digital document references for regulatory inspection readiness (FDA 21 CFR Part 11 / Annex 11). · seen in: Qualio, Veeva Vault, MasterControl · priority: **common** · spine: `CertificateOfAnalysis.attachment_document` (`quality.ControlledDocument`) · **buildable now**

### Bullet 4 — Inspection Data Capture & SPC (Real-time data entry, statistical process control charts, and trend alerts)

- **Critical-to-Quality (CTQ) Variable Data Logging** — Direct digital capture of quantitative inspection measurements across sample units (e.g., sample readings $x_1, x_2, \dots, x_n$ for critical shaft diameter, thickness, or resistance). · seen in: QT9, TrackWise Digital, ComplianceQuest · priority: **table-stakes** · spine: `IncomingInspectionLot.sample_readings` (list of float measurements) · **buildable now**
- **Automated Summary Statistics Calculation** — Computes sample descriptive statistics on the fly:
  - Sample Size ($n$)
  - Sample Mean ($\bar{X} = \frac{1}{n} \sum x_i$)
  - Standard Deviation ($s = \sqrt{\frac{1}{n-1} \sum (x_i - \bar{X})^2}$)
  - Range ($R = \max(x) - \min(x)$)
  - Min and Max observed values
  · seen in: QT9, ComplianceQuest, Sparta Systems · priority: **table-stakes** · spine: `IncomingInspectionLot.sample_mean`, `sample_std_dev`, `sample_min`, `sample_max` · **buildable now**
- **Process Capability Indices ($C_p$ and $C_{pk}$)** — Calculates process capability metrics against inspection plan engineering tolerance limits ($USL$, $LSL$):
  $$C_p = \frac{USL - LSL}{6s}$$
  $$C_{pk} = \min\left(\frac{USL - \bar{X}}{3s}, \frac{\bar{X} - LSL}{3s}\right)$$
  Classifies capability into industry standards:
  - $C_{pk} \ge 1.67$: World-class / Six Sigma quality
  - $1.33 \le C_{pk} < 1.67$: Capable / acceptable production
  - $1.00 \le C_{pk} < 1.33$: Marginally capable / requires close monitoring
  - $C_{pk} < 1.00$: Incapable / high defect risk, triggers quality investigation
  · seen in: QT9, ComplianceQuest, Arena QMS · priority: **table-stakes** · spine: `IncomingInspectionLot.cp_index`, `cpk_index`, capability evaluation methods · **buildable now**
- **Statistical Trend & Out-of-Control Alerts** — Detects statistical anomalies (Western Electric / Nelson rules): points beyond 3-sigma limits, significant mean drift toward specification limits, or high variance excursion. Sets `spc_alert_triggered = True` and records `spc_alert_reason`. · seen in: ComplianceQuest, Sparta Systems · priority: **table-stakes** · spine: `IncomingInspectionLot.spc_alert_triggered`, `spc_alert_reason` · **buildable now**
- **IQC SPC Analytics Dashboard** — Consolidated quality engineering view tracking historical $C_{pk}$ trends by supplier, lot acceptance rate trends, defect distribution pareto, and active out-of-control statistical alerts. · seen in: QT9, ComplianceQuest · priority: **table-stakes** · spine: Dedicated analytics view `quality:iqc_spc_dashboard` · **buildable now**

### Bullet 5 — Reject & Return Material Authorization (RMA) (Rejection documentation, supplier notification, and RMA workflow)

- **Rejection Documentation & Material Isolation** — Automatic initialization of return records from rejected `IncomingInspectionLot` [QIIL-] or `quality.NonConformanceReport` [QNCR-]. Locks affected lot numbers, quantities, supplier details, purchase order, and receiving receipt reference. · seen in: All leaders · priority: **table-stakes** · spine: `QualityReturnAuthorization` (new table, `NUMBER_PREFIX = "QRMA"`) · **buildable now**
- **Vendor RMA Lifecycle State Machine** — Governs closed-loop return progression:
  `draft` -> `rma_requested` -> `rma_approved_by_vendor` -> `shipped_to_vendor` -> `received_by_vendor` -> `settled_closed` (or `cancelled`).
  · seen in: All leaders · priority: **table-stakes** · spine: `QualityReturnAuthorization.status` · **buildable now**
- **Structured Return Reason Categorization** — Standard quality taxonomy for supplier returns:
  `dimensional_out_of_spec`, `functional_failure`, `coa_non_compliance`, `cosmetic_visual_defect`, `wrong_material_supplied`, `packaging_damage`, `contamination`, `expired_shelf_life`.
  · seen in: MasterControl, ETQ, QT9 · priority: **table-stakes** · spine: `QualityReturnAuthorization.return_reason` · **buildable now**
- **Commercial & Financial Disposition Types** — Defines commercial resolution agreement with vendor:
  - `return_for_credit` (supplier issues full credit memo against AP invoice)
  - `return_for_replacement` (supplier ships replacement lot under new or original PO)
  - `return_for_rework` (supplier recalibrates, re-machines, or repacks and returns)
  - `scrap_on_site` (supplier authorizes on-site scrapping with credit allowance)
  · seen in: ETQ Reliance, QT9, Veeva Vault · priority: **table-stakes** · spine: `QualityReturnAuthorization.disposition_type` · **buildable now**
- **Vendor Authorization & Tracking Coordination** — Tracks supplier authorization details: `vendor_rma_number` (vendor's return authorization code), `rma_request_date`, `rma_approved_date`, `rma_expiry_date`. · seen in: All leaders · priority: **table-stakes** · spine: `QualityReturnAuthorization.vendor_rma_number`, authorization date fields · **buildable now**
- **Logistics, Shipping & Chain of Custody** — Captures physical outbound return logistics: `carrier_name`, `tracking_number`, `bill_of_lading_number`, `shipment_date`, `vendor_received_date`. · seen in: QT9, MasterControl · priority: **table-stakes** · spine: `QualityReturnAuthorization` logistics fields · **buildable now**
- **Financial Settlement & Credit Reconciliation** — Tracks financial closure: `debit_memo_number`, `settlement_status` (`pending`, `credit_note_received`, `replacement_received`, `settled`), `settlement_date`, `settlement_amount`. · seen in: QT9, ETQ Reliance, ComplianceQuest · priority: **table-stakes** · spine: `QualityReturnAuthorization.debit_memo_number`, `settlement_status`, `settlement_amount` · **buildable now**
- **Upstream Feedback Loop to Supplier Scorecard (12.6)** — Material returns automatically feed into `SupplierQualityScorecard` [QSSC-] calculations, directly impacting the vendor's Defect PPM score and lot acceptance rate, and triggering AVL status reviews if rejection thresholds are breached. · seen in: MasterControl, ETQ Reliance, Greenlight Guru · priority: **table-stakes** · spine: Integration with Module 12.6 `SupplierQualityScorecard` · **buildable now**

---

## Recommended 4-model scope for Sub-module 12.7

To deliver comprehensive coverage across all 5 bullets in NavERP.md without unnecessary schema bloat, we recommend a cohesive **4-model architecture**:

```
+---------------------------------------------------------------------------------------------------+
|                                  INCOMING QUALITY CONTROL (IQC)                                   |
|                                                                                                   |
|  +------------------------------+                +---------------------------------------------+  |
|  | IncomingInspectionPlan       |                | CertificateOfAnalysis                       |  |
|  | Prefix: [QIIP-]              |                | Prefix: [QCOA-]                             |  |
|  | - Sampling: ANSI Z1.4, AQL   |                | - Manufacturer CoA Data & DOM/Expiry        |  |
|  | - Inspection Level / Severity|                | - Multi-Parameter Spec Comparison Engine    |  |
|  | - Frequency Mode & Skip-Lot  |                | - Automated Variance / Out-of-Spec Flags    |  |
|  | - CTQ Specs & Limits         |                | - Gated Verification for Lot Acceptance     |  |
|  +--------------+---------------+                +----------------------+----------------------+  |
|                 | 1:N                                                   | 1:1 or 1:N              |
|                 v                                                       v                         |
|  +----------------------------------------------------------------------+----------------------+  |
|  | IncomingInspectionLot [QIIL-]                                                               |  |
|  | - Goods Receipt Linkage (scm.GoodsReceiptNote, scm.PurchaseOrder, core.Party supplier)      |  |
|  | - Sampling Math: ANSI Code Letter -> Sample Size -> Defect Counts (Critical/Major/Minor)   |  |
|  | - SPC Variable Measurements: Mean, StdDev, Range, Cp, Cpk Index & Out-of-Control Alerts    |  |
|  | - Usage Decision: Accepted, Accepted with Deviation, Quarantined, Rejected, Skip-Lot       |  |
|  | - Direct Linkages to quality.NonConformanceReport [QNCR-] and Quarantine [QCNT-]           |  |
|  +----------------------------------------------------------------------+----------------------+  |
|                                                                         | 1:1                     |
|                                                                         v                         |
|  +---------------------------------------------------------------------------------------------+  |
|  | QualityReturnAuthorization [QRMA-]                                                          |  |
|  | - Rejection Isolation & Return Reason (Dimensional OOS, Functional, CoA Fail, Contam.)     |  |
|  | - Vendor RMA Tracking (vendor_rma_number, request/approval dates, validity period)          |  |
|  | - Commercial Disposition: Return for Credit, Replacement, Rework, Scrap On-Site             |  |
|  | - Logistics: Carrier, Tracking #, BOL, Shipment Dates, Vendor Receipt Confirmation         |  |
|  | - Financial Settlement: Debit Memo #, Credit Reconciliation, Closed-Loop Settlement        |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

### Model 1: `IncomingInspectionPlan` (`QIIP`)
- **Bullet realization:** Realizes Bullet 1 (*Inspection Planning & Sampling*) and provides tolerance definitions for Bullet 4 (*SPC*).
- **Core fields:**
  - `number`: Autonumbered `[QIIP-00001]` via `TenantNumbered`.
  - `title`: Plan name / description (e.g., "Precision CNC Machined Shafts - Receiving Plan").
  - `item_code`: Target item part number (Module 5 unbuilt stand-in).
  - `item_name`: Part description.
  - `supplier`: Optional specific supplier (`core.Party`), or null for generic commodity plan.
  - `revision`: Document revision string (e.g., "Rev C").
  - `sampling_standard`: Choices `ansi_z1_4` (ANSI/ASQ Z1.4 / ISO 2859-1), `c_zero` (Zero Defect $c=0$), `fixed_sample`, `percent_sample`, `100_percent`.
  - `inspection_level`: Choices `level_I`, `level_II` (default), `level_III`, `special_S1`, `special_S2`, `special_S3`, `special_S4`.
  - `inspection_severity`: Choices `normal` (default), `tightened`, `reduced`.
  - `frequency_mode`: Choices `every_lot` (default), `skip_lot`, `dock_to_stock`, `first_article`.
  - `skip_lot_interval`: Positive integer (e.g. inspect 1 in every 5 lots).
  - `aql_critical`: Decimal AQL threshold (e.g. 0.065, 0.10, default 0.00).
  - `aql_major`: Decimal AQL threshold (e.g. 1.0, 1.5, default 1.00).
  - `aql_minor`: Decimal AQL threshold (e.g. 4.0, 6.5, default 4.00).
  - `characteristics`: JSONField defining test characteristics (name, type [dimensional/visual/functional/chemical], nominal, LSL, USL, uom, is_ctq, is_coa_required).
  - `specification_document`: Optional FK to `quality.ControlledDocument`.
  - `status`: Choices `draft`, `active`, `under_revision`, `obsolete`.
  - `owner`: FK to `accounts.User`.
  - `notes`: Markdown text.

### Model 2: `IncomingInspectionLot` (`QIIL`)
- **Bullet realization:** Realizes Bullet 2 (*Goods Receipt & Inspection Execution*) and Bullet 4 (*Inspection Data Capture & SPC*).
- **Core fields:**
  - `number`: Autonumbered `[QIIL-00001]` via `TenantNumbered`.
  - `inspection_plan`: FK to `IncomingInspectionPlan` (protect).
  - `supplier`: FK to `core.Party` (supplier/vendor).
  - `purchase_order`: Optional FK to `scm.PurchaseOrder` [PO-].
  - `goods_receipt`: Optional FK to `scm.GoodsReceiptNote` [GRN-].
  - `item_code` & `item_name`: Part identifiers snapshotted from receipt/plan.
  - `lot_number`: Vendor batch / lot number string.
  - `receipt_date`: Date goods landed at receiving dock.
  - `lot_quantity`: Decimal total received shipment quantity.
  - `sample_size`: Integer sample count required by ANSI/ASQ Z1.4.
  - `inspected_quantity`: Integer actual units inspected.
  - `accepted_quantity`: Decimal quantity approved for release to inventory.
  - `rejected_quantity`: Decimal quantity rejected.
  - `quarantine_quantity`: Decimal quantity placed in quarantine hold.
  - `critical_defects`: Integer count of critical defects found.
  - `major_defects`: Integer count of major defects found.
  - `minor_defects`: Integer count of minor defects found.
  - `status`: Choices `pending_receipt`, `in_inspection`, `sampling_complete`, `completed`, `cancelled`.
  - `usage_decision`: Choices `pending`, `accepted`, `accepted_with_deviation`, `quarantined`, `rejected`, `skip_lot_passed`.
  - `usage_decision_by`: FK to `accounts.User`.
  - `usage_decision_at`: DateTime of decision sign-off.
  - `inspector`: FK to `accounts.User`.
  - `inspection_started_at` & `inspection_completed_at`: Timestamps.
  - **SPC & CTQ Metrics:**
    - `sample_readings`: JSONField list of measured float/decimal readings for CTQ characteristic.
    - `sample_mean`: Decimal average reading $\bar{X}$.
    - `sample_std_dev`: Decimal standard deviation $s$.
    - `sample_range`: Decimal range $R$.
    - `sample_min` & `sample_max`: Extremes.
    - `cp_index`: Decimal process capability $C_p$.
    - `cpk_index`: Decimal process capability $C_{pk}$.
    - `spc_alert_triggered`: Boolean flag for out-of-control conditions.
    - `spc_alert_reason`: Text summary of alert cause (e.g. "$C_{pk} < 1.33$ or point beyond 3-sigma limit").
  - **Downstream Quality Links:**
    - `non_conformance`: Optional FK to `quality.NonConformanceReport` [QNCR-].
    - `quarantine`: Optional FK to `quality.QuarantineContainment` [QCNT-].
    - `scar`: Optional FK to `quality.SupplierCorrectiveAction` [QSCA-].

### Model 3: `CertificateOfAnalysis` (`QCOA`)
- **Bullet realization:** Realizes Bullet 3 (*Certificate of Analysis (CoA) Management*).
- **Core fields:**
  - `number`: Autonumbered `[QCOA-00001]` via `TenantNumbered`.
  - `inspection_lot`: Optional OneToOne/ForeignKey to `IncomingInspectionLot` [QIIL-].
  - `supplier`: FK to `core.Party`.
  - `certificate_reference`: Supplier's CoA certificate/document identifier string.
  - `manufacturer_name`: Name of actual manufacturing facility / laboratory.
  - `item_code` & `item_name`: Material identification.
  - `lot_number`: Lot / batch number on certificate.
  - `date_of_manufacture`: Date lot was manufactured.
  - `expiration_date`: Date product expires / requires re-testing.
  - `accredited_lab`: Boolean (tested by ISO/IEC 17025 accredited laboratory).
  - `status`: Choices `pending_receipt`, `received_under_review`, `compliant`, `non_compliant_rejected`, `deviation_accepted`.
  - `test_parameters`: JSONField list of test parameters (characteristic, specification limits [LSL, target, USL], test method, reported result, conformance [pass/fail]).
  - `is_within_spec`: Boolean overall specification compliance flag.
  - `variance_count`: Integer count of parameters failing engineering limits.
  - `exception_notes`: Markdown details on out-of-specification or borderline values.
  - `verified_by`: FK to `accounts.User`.
  - `verified_at`: DateTime of verification sign-off.
  - `attachment_document`: Optional FK to `quality.ControlledDocument` or document link.

### Model 4: `QualityReturnAuthorization` (`QRMA`)
- **Bullet realization:** Realizes Bullet 5 (*Reject & Return Material Authorization (RMA)*).
- **Core fields:**
  - `number`: Autonumbered `[QRMA-00001]` via `TenantNumbered`.
  - `inspection_lot`: FK to `IncomingInspectionLot` [QIIL-].
  - `supplier`: FK to `core.Party` (supplier/vendor).
  - `purchase_order`: Optional FK to `scm.PurchaseOrder` [PO-].
  - `goods_receipt`: Optional FK to `scm.GoodsReceiptNote` [GRN-].
  - `non_conformance`: Optional FK to `quality.NonConformanceReport` [QNCR-].
  - `vendor_rma_number`: Supplier-issued return authorization number.
  - `status`: Choices `draft`, `rma_requested`, `rma_approved_by_vendor`, `shipped_to_vendor`, `received_by_vendor`, `settled_closed`, `cancelled`.
  - `return_reason`: Choices `dimensional_out_of_spec`, `functional_failure`, `coa_non_compliance`, `cosmetic_visual_defect`, `wrong_material_supplied`, `packaging_damage`, `contamination`, `expired_shelf_life`.
  - `disposition_type`: Choices `return_for_credit`, `return_for_replacement`, `return_for_rework`, `scrap_on_site`.
  - `return_quantity`: Decimal quantity of material being returned.
  - `uom`: String unit of measure (e.g., "EA", "KG", "L").
  - `rma_request_date`: Date RMA requested from supplier.
  - `rma_approved_date`: Date vendor authorized the RMA.
  - `rma_expiry_date`: Expiry date of vendor's return authorization.
  - `carrier_name`: Shipping carrier (e.g. FedEx, UPS, Freight).
  - `tracking_number`: Outbound return shipment tracking number.
  - `bill_of_lading`: BOL number for freight shipments.
  - `shipped_date`: Date returned material left dock.
  - `vendor_received_date`: Date vendor confirmed delivery.
  - `debit_memo_number`: Accounts Payable debit memo reference.
  - `settlement_status`: Choices `pending`, `credit_note_received`, `replacement_received`, `settled`.
  - `settlement_amount`: Decimal financial credit amount.
  - `settlement_date`: Date financial or replacement settlement completed.
  - `coordinator`: FK to `accounts.User` (RMA coordinator).
  - `notes`: Markdown text.

---

## UI / View routing & Navigation mapping

Matching the 5 bullets in `NavERP.md` 12.7 and integrating cleanly into `apps/core/navigation.py`:

```python
"12.7": {
    "Inspection Planning & Sampling": "quality:incoming_inspection_plan_list",
    "Goods Receipt & Inspection Execution": "quality:incoming_inspection_lot_list",
    "Certificate of Analysis (CoA) Management": "quality:certificate_of_analysis_list",
    "Inspection Data Capture & SPC": "quality:iqc_spc_dashboard",
    "Reject & Return Material Authorization (RMA)": "quality:quality_return_authorization_list",
}
```

### URL patterns planned under `apps/quality/urls/`:
1. **Inspection Plans (`IncomingInspectionPlan`):**
   - `iqc/plans/` -> `incoming_inspection_plan_list`
   - `iqc/plans/new/` -> `incoming_inspection_plan_create`
   - `iqc/plans/<int:pk>/` -> `incoming_inspection_plan_detail`
   - `iqc/plans/<int:pk>/edit/` -> `incoming_inspection_plan_edit`
2. **Inspection Lots (`IncomingInspectionLot`):**
   - `iqc/lots/` -> `incoming_inspection_lot_list`
   - `iqc/lots/new/` -> `incoming_inspection_lot_create`
   - `iqc/lots/<int:pk>/` -> `incoming_inspection_lot_detail`
   - `iqc/lots/<int:pk>/edit/` -> `incoming_inspection_lot_edit`
   - `iqc/lots/<int:pk>/decision/` -> `incoming_inspection_lot_decision`
3. **Certificates of Analysis (`CertificateOfAnalysis`):**
   - `iqc/coas/` -> `certificate_of_analysis_list`
   - `iqc/coas/new/` -> `certificate_of_analysis_create`
   - `iqc/coas/<int:pk>/` -> `certificate_of_analysis_detail`
   - `iqc/coas/<int:pk>/edit/` -> `certificate_of_analysis_edit`
   - `iqc/coas/<int:pk>/verify/` -> `certificate_of_analysis_verify`
4. **SPC Analytics Dashboard (`IqcSpcDashboard`):**
   - `iqc/spc-dashboard/` -> `iqc_spc_dashboard`
5. **Quality Return Material Authorizations (`QualityReturnAuthorization`):**
   - `iqc/rmas/` -> `quality_return_authorization_list`
   - `iqc/rmas/new/` -> `quality_return_authorization_create`
   - `iqc/rmas/<int:pk>/` -> `quality_return_authorization_detail`
   - `iqc/rmas/<int:pk>/edit/` -> `quality_return_authorization_edit`
   - `iqc/rmas/<int:pk>/status/` -> `quality_return_authorization_status_update`

---

## Verification & testing strategy

- **Multi-Tenant Isolation:** Full tenant boundary tests asserting that `tenant_a` records cannot be accessed, modified, or listed by `tenant_b` across all 4 models.
- **Autonumbering & Sequence Integrity:** Verifies atomic sequence generation for `QIIP-`, `QIIL-`, `QCOA-`, and `QRMA-`.
- **ANSI/ASQ Z1.4 Sampling Size Derivation:** Mathematical tests verifying correct sample size calculation across various lot sizes (e.g. lot size 50 -> sample size 8; lot size 1,000 -> sample size 80 under Level II).
- **SPC Calculation Engine:** Verifies that sample mean, sample standard deviation, $C_p$, and $C_{pk}$ match textbook formulas and correctly flag out-of-control conditions when $C_{pk} < 1.33$ or when points drift past 3-sigma.
- **CoA Specification Evaluation:** Tests automated range checking (min, target, max) across structured parameters and verifies that `is_within_spec` is correctly computed.
- **CoA Gating Enforcement:** Verifies that when a supplier requires CoA (`requires_coa=True`), an inspection lot cannot be accepted without a compliant CoA.
- **RMA Lifecycle Progression:** Verifies status transitions, logistics field validation, and settlement tracking.
