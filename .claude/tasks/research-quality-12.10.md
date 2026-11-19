# Research — Sub-module 12.10: Calibration & Measurement System Analysis (Module 12 — Quality Management System, `quality`)

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

- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py`, prefix `QDOC`): Standard operating procedures (SOPs), calibration protocols, metrology work instructions, and MSA sampling plans.
  - `NonConformanceReport` (`apps/quality/models/NonConformance/NonConformanceReports.py`, prefix `QNCR`): Internal non-conformance reports automatically spawned when calibration encounters Out-of-Tolerance (OOT) conditions or when MSA fails acceptability thresholds.
  - `QuarantineContainment` (`apps/quality/models/NonConformance/QuarantineContainments.py`, prefix `QCNT`): Physical or tool-crib quarantine records for failed gages or suspect production lots produced with out-of-tolerance instruments.
  - `ProcessDeviation` (`apps/quality/models/NonConformance/ProcessDeviations.py`, prefix `QDEV`): Concessions or deviations logged when instruments are used under de-rated conditions or temporarily operating within expanded guard bands.
  - `CapaInvestigation` (`apps/quality/models/CapaManagement/CapaInvestigations.py`, prefix `QCAP`): Enterprise CAPA records triggered by chronic gage drift, recurring OOT events, or unacceptable measurement system variation.
  - `RiskAssessment` (`apps/quality/models/RiskManagement/RiskAssessments.py`, prefix `QRSK`): Process and Design FMEA records identifying Critical-to-Quality (CTQ) dimensions requiring calibrated gages and Gage R&R validation.
  - `SupplierQualificationAudit` (`apps/quality/models/SupplierQuality/SupplierQualificationAudits.py`, prefix `QSQA`): Audits assessing external commercial calibration laboratories for ISO/IEC 17025 accreditation compliance.
  - `SupplierQualityScorecard` (`apps/quality/models/SupplierQuality/SupplierQualityScorecards.py`, prefix `QSSC`): Vendor scorecards tracking calibration vendor turnaround time, certificate accuracy, and calibration test uncertainty ratios (TUR).

- **Cross-module spine models available to FK:**
  - `scm.Asset` (`apps/scm/models/AssetManagement/Assets.py:50`, prefix `AST`): Physical plant equipment, machines, and tools. Calibrated gages can be maintainable assets or associated with physical production machinery.
  - `scm.WorkCenter` (`apps/scm/models/Manufacturing/WorkCenters.py:23`, prefix `WC`): Machine cells, metrology inspection stations, quality labs, or assembly lines where gages are deployed.
  - `scm.WorkOrder` (`apps/scm/models/Manufacturing/WorkOrders.py:26`, prefix `WO`): Production orders executed using gages during the suspect window of an Out-of-Tolerance event.
  - `core.Tenant` (`apps/core/models/Tenant.py:17`): Multi-tenant isolation foundation.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:5`): Plant, department, metrology laboratory, or quality control unit ownership.
  - `core.Party` (`apps/core/models/Party.py:5`) & `core.PartyRole` (`apps/core/models/PartyRole.py:5`): External ISO/IEC 17025 accredited calibration laboratories, gage manufacturers, and internal employees (`role="vendor"` or `role="employee"`).
  - `accounts.User` (`apps/accounts/models.py:52`): Quality engineers, metrology technicians, tool crib custodians, and calibration approval supervisors.
  - `core.AuditLog` (`apps/core/models/AuditLog.py:5` + `write_audit_log` helper): Immutable tenant-scoped audit logging for calibration adjustments, interval overrides, and OOT disposition approvals.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and atomic retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Metrology lab, quality department, or plant location. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Calibration service vendors (`role="vendor"`), gage OEMs. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | Calibration technicians, custodians, and approving metrologists. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable audit trail for FDA 21 CFR Part 11 and ISO 17025 compliance. |
| `scm.Asset` exists | `apps/scm/models/AssetManagement/Assets.py:50` -> `class Asset(TenantNumbered)` | Physical plant assets and tools linked to calibration gage records. |
| `scm.WorkCenter` exists | `apps/scm/models/Manufacturing/WorkCenters.py:23` -> `class WorkCenter(TenantNumbered)` | Production cells, inspection rooms, or test benches. |
| `scm.WorkOrder` exists | `apps/scm/models/Manufacturing/WorkOrders.py:26` -> `class WorkOrder(TenantNumbered)` | Production jobs linked to reverse-tracing during OOT investigations. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | Calibration procedures, work instructions, and MSA protocols. |
| `quality.NonConformanceReport` exists | `apps/quality/models/NonConformance/NonConformanceReports.py:10` | Non-conformance records generated automatically on OOT findings. |
| `quality.QuarantineContainment` exists | `apps/quality/models/NonConformance/QuarantineContainments.py:8` | Quarantine tagging for OOT gages and suspect production material. |
| `quality.CapaInvestigation` exists | `apps/quality/models/CapaManagement/CapaInvestigations.py:8` | Enterprise CAPAs escalated from chronic gage drift or severe OOT recalls. |

### Spine entities verified NOT to exist (or unbuilt in Module 12 / ERP)

- **Module 5 unbuilt masters:** `Item`, `LotSerial`, `UOM`, `StockMove` are planned for Module 5. Quality models use free-text stand-in fields (`item_code`, `item_name`, `lot_number`, `unit_of_measure`, `part_number`) with optional nullable FKs to `scm.WorkOrder` / `scm.WorkCenter` / `scm.Asset`, ensuring complete loose-coupling and a documented future migration path.
- **Hardware Bus Drivers:** Hardware communication protocols (IEEE 488 / GPIB, RS-232, USB-TMC, VISA, LXI) for live automated calibrator control (e.g. Fluke MET/CAL automated execution) are external hardware protocols. 12.10 delivers the complete QMS and metrology data architecture, scheduling engine, calibration data records, uncertainty/guardband evaluations, OOT risk containment, and MSA statistical calculations.

### Candidate prefix collision check (repo-wide automated verification)

Automated scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QGAG` (Quality Calibration Gage) -> **0 collisions** (Completely free)
- `QCAL` (Quality Calibration Record) -> **0 collisions** (Completely free)
- `QOOT` (Quality Out-of-Tolerance Investigation) -> **0 collisions** (Completely free)
- `QMSA` (Quality Measurement System Analysis) -> **0 collisions** (Completely free)

---

## Leaders surveyed (with source links)

1. **Fluke MET/TEAM & MET/CAL** — Industry gold standard for commercial and enterprise metrology calibration management, asset tracking, and automated calibration execution. Features cradle-to-grave instrument lifecycle tracking, calibration work orders, test point management, measurement uncertainty budgets, guardbanding per ILAC-G8 / ANSI/NCSL Z540.3, automated calibration alerts, reverse traceability / recall escalation, and compliance with ISO/IEC 17025 and 10 CFR 21/50.
   - *Source:* https://www.fluke.com/en-us/products/calibration-software/fluke-calibration-software/met-team
2. **Beamex CMX** — Enterprise calibration management software widely deployed in regulated process industries (pharmaceuticals, energy, life sciences, chemicals). Features plant hierarchy location tracking, standardized calibration procedures, reference standard traceability management, as-found/as-left result logging, combined expanded uncertainty calculation, interval optimization analysis (drift trend analysis), automated calibration certificate generation, and FDA 21 CFR Part 11 electronic signatures.
   - *Source:* https://www.beamex.com/software/calibration-management-software/
3. **CyberMetrics GAGEtrak** — Comprehensive calibration management and Measurement and Test Equipment (M&TE) software. Features gage inventory tracking, tool crib issue/return check-in/out, time- and usage-based calibration interval scheduling, calibration history logs, variable and attribute measurement capture, Out-of-Tolerance containment workflows, and built-in AIAG MSA 4th Edition Gage R&R analysis (%GRR, NDC, ANOVA/Xbar-R).
   - *Source:* https://gagetrak.com/
4. **ETQ Reliance (Calibration & OOT Management)** — Enterprise life sciences QMS platform featuring closed-loop calibration management. Specializes in automated Out-of-Tolerance (OOT) detection from failed As-Found calibration data, instant Nonconformance (NCMR) generation, automated escalation into CAPA/SCAR, reverse-traceability impact assessment (querying affected production lots between the last passing calibration and the failure), and risk evaluation.
   - *Source:* https://www.etq.com/quality-management-system/ & https://www.etq.com/blog/layered-process-audits/
5. **MasterControl Asset Excellence (Ax) / Qualer** — Life sciences CMMS and calibration software tailored for FDA 21 CFR Part 820/211 and ISO 13485 environments. Features automated usage- and time-based calibration event triggering, as-found and as-left metrology logging, external accredited service provider portal, reference standard hierarchy tracking, and seamless linkage into electronic batch records (EBR) to prevent uncalibrated tool utilization.
   - *Source:* https://www.mastercontrol.com/solutions/asset-management/
6. **Minitab (Measurement System Analysis / Gage R&R)** — The global statistical benchmark for quality engineering and Six Sigma. Delivers complete Measurement System Analysis (MSA) capabilities including Crossed Gage R&R (balanced ANOVA & Xbar-R methods), Nested Gage R&R (destructive testing), Gage Linearity and Bias studies, Gage Stability studies (longitudinal control charting), Type 1 Gage capability analysis ($C_g, C_{gk}$), and Attribute Agreement Analysis.
   - *Source:* https://www.minitab.com/en-us/products/minitab/
7. **PQ Systems GAGEpack** — Specialized gage calibration and measurement management software for ISO 9001 and IATF 16949 manufacturers. Provides complete gage lifecycle tracking, custom calibration procedures with environmental logging, automated due-date notifications, calibration certificates, and integrated Gage R&R studies to assess appraiser variation and equipment variation.
   - *Source:* https://www.pqsystems.com/gagepack/
8. **IndySoft Calibration Management** — Scalable metrology and asset tracking solution used by commercial calibration laboratories, aerospace/defense, and research institutions. Features event-driven calibration workflows, automated pass/fail calculations, measurement uncertainty budgets, equipment template cloning, NIST/ISO 17025 certificate management, and tool crib barcode/RFID tracking.
   - *Source:* https://www.indysoft.com/
9. **SimplerQMS (Equipment & Calibration Management)** — Cloud eQMS for medical device and biotech industries. Features centralized equipment metadata registers, calibration work instruction linkage, automated calibration task assignments with supervisor escalation, certificate drag-and-drop archiving, and automatic failure-to-CAPA incident workflows.
   - *Source:* https://www.simplerqms.com/equipment-calibration-and-maintenance-software/

---

## Feature catalog (this sub-module only)

### 1. Calibration Schedule & Planning
- **Comprehensive Gage & Instrument Registry** — Centralized repository tracking all measurement and test equipment (M&TE), reference standards, and gages, recording gage tag, description, serial number, model, manufacturer, physical location, assigned work center, custodian, measurement range, resolution, and tolerance limits. · seen in: Fluke MET/TEAM, CyberMetrics GAGEtrak, Beamex CMX, PQ Systems GAGEpack, SimplerQMS · priority: table-stakes · spine: new table `CalibrationGage` (`QGAG-`), reuses `core.Tenant`, FKs `scm.Asset`, `scm.WorkCenter`, `core.OrgUnit`, `accounts.User`, `core.Party` · buildable now.
- **Dynamic Calibration Intervals & Due-Date Forecasting** — Automated scheduling engine calculating calibration due dates based on defined cadences: time-based (e.g. 30, 90, 180, 365 days), usage cycle thresholds, or on-demand/before-use triggers, with automated status shifts (`active_in_service`, `calibration_due`, `out_of_service`, `in_calibration`). · seen in: Fluke MET/TEAM, Beamex CMX, MasterControl Ax, IndySoft · priority: table-stakes · spine: fields on `CalibrationGage` · buildable now.
- **Gage Classification & Criticality Hierarchy** — Categorization of measurement assets by criticality level (e.g., `critical_ctq` for product safety/key characteristics, `standard_inspection` for routine inspection, `reference_standard` for master calibration tools, `indication_only` for non-critical process monitors), determining inspection rigor and tolerance guardbanding. · seen in: SimplerQMS, Beamex CMX, ETQ Reliance · priority: common · spine: `classification` choice on `CalibrationGage` · buildable now.
- **Reference Standard & Traceability Chain** — Identification of master reference standards with NIST (or national metrology institute) test report numbers, certificate expiration dates, and traceability hierarchy to satisfy ISO/IEC 17025 requirements. · seen in: Fluke MET/TEAM, Beamex CMX, IndySoft · priority: common · spine: `is_reference_standard`, `nist_traceability_number` fields on `CalibrationGage` · buildable now.
- **Tool Crib Custody & Gage Status Tracking** — Tracking physical custody, storage location (bin/shelf/room), and operational readiness state, preventing checkout or shop-floor deployment of uncalibrated, overdue, or quarantined gages. · seen in: CyberMetrics GAGEtrak, PQ Systems GAGEpack, IndySoft · priority: table-stakes · spine: `status`, `location_storage`, `custodian` on `CalibrationGage` · buildable now.

### 2. Calibration Execution & Records
- **Dual "As-Found" and "As-Left" Metrology Data Recording** — Logging condition and numerical readings both prior to any adjustment/cleaning (`as_found`: in-tolerance vs. out-of-tolerance) and following adjustment/cleaning (`as_left`: returned to nominal, adjusted, or limited calibration), establishing drift history and triggering OOT investigations. · seen in: Fluke MET/TEAM, Beamex CMX, MasterControl Ax, ETQ Reliance · priority: table-stakes · spine: new table `CalibrationRecord` (`QCAL-`), FK `CalibrationGage`, choice fields `as_found_condition`, `as_left_condition`, `result_status` · buildable now.
- **Multilevel Calibration Execution Routing** — Support for internal calibration lab execution, external ISO 17025 accredited laboratory servicing, on-site third-party technician calibration, or quick field zero/span verification checks. · seen in: Fluke MET/TEAM, IndySoft, MasterControl Ax · priority: table-stakes · spine: `calibration_type` on `CalibrationRecord`, FK to `core.Party` (`calibration_vendor`) · buildable now.
- **Environmental Condition Logging** — Recording ambient temperature ($^\circ\text{C}$) and relative humidity ($\%$) at the time of calibration, ensuring compliance with standard metrology reference conditions (e.g., $20^\circ\text{C} \pm 1^\circ\text{C}$ for precision dimensional gages). · seen in: Fluke MET/TEAM, Beamex CMX, PQ Systems GAGEpack · priority: common · spine: `environmental_temperature_c`, `environmental_humidity_pct` on `CalibrationRecord` · buildable now.
- **Measurement Uncertainty & Test Uncertainty Ratio (TUR)** — Storing expanded measurement uncertainty ($U$) with coverage factor $k=2$ (95% confidence interval) and calculating the Test Uncertainty Ratio (TUR $\ge 4:1$ rule of thumb per ANSI/NCSL Z540.3) between gage tolerance and standard uncertainty. · seen in: Fluke MET/TEAM, Beamex CMX, IndySoft · priority: common · spine: `expanded_uncertainty`, `test_uncertainty_ratio` on `CalibrationRecord` · buildable now.
- **Guardbanding & Decision Rule Formulation** — Formal documentation of the conformity decision rule applied to calibration readings (Simple Acceptance, ILAC-G8 Binary Guardbanding, Non-Binary Guardbanding with safety margins), preventing false acceptance of borderline readings near tolerance limits. · seen in: Fluke MET/TEAM, Beamex CMX, ISO 17025 guidelines · priority: differentiator · spine: `decision_rule` choice field on `CalibrationRecord` · buildable now.
- **Calibration Certificate Ingestion & Archiving** — Capturing vendor certificate numbers, issue dates, accreditation symbols, and digital certificate file attachments, creating permanent, tamper-resistant digital calibration records. · seen in: Fluke MET/TEAM, SimplerQMS, MasterControl Ax · priority: table-stakes · spine: `certificate_number`, `certificate_issue_date`, `certificate_file` reference on `CalibrationRecord` · buildable now.
- **Electronic Review & Verification Sign-Off** — Formal multi-tier sign-off by the executing technician and the approving quality/metrology engineer, satisfying FDA 21 CFR Part 11 and ISO 9001 revision control. · seen in: ETQ Reliance, MasterControl Ax, SimplerQMS · priority: table-stakes · spine: `performed_by`, `approved_by`, `approved_at` on `CalibrationRecord` · buildable now.

### 3. Out-of-Tolerance (OOT) Handling
- **Automated OOT Triggering & Immediate Quarantine** — Automatic generation of an Out-of-Tolerance Investigation when a calibration record logs an `as_found_condition="out_of_tolerance"`, immediately shifting gage status to `quarantined_oot` and logging a containment action. · seen in: ETQ Reliance, MasterControl Ax, SimplerQMS, Beamex CMX · priority: table-stakes · spine: new table `OutOfToleranceInvestigation` (`QOOT-`), FK to `CalibrationRecord`, FK to `CalibrationGage`, updates `CalibrationGage.status` · buildable now.
- **Suspect Window & Reverse-Tracing Impact Assessment** — Defining the suspect operational window (from the date of the last known passing calibration to the date of the OOT discovery) and identifying all production work orders, batches, inspection lots, or finished products measured by the instrument during that window. · seen in: ETQ Reliance, MasterControl Ax, Fluke MET/TEAM · priority: table-stakes · spine: `suspect_usage_window_start`, `suspect_usage_window_end`, `suspect_work_orders_count`, `suspect_lots_inspected` on `OutOfToleranceInvestigation` · buildable now.
- **Consumer vs. Producer Risk Evaluation** — Quantitative evaluation of the magnitude of error: whether the gage was reading high or low, whether parts accepted may have been non-conforming (Consumer's Risk / False Acceptance), or whether conforming parts were falsely rejected (Producer's Risk), factoring in product tolerance safety margins. · seen in: ETQ Reliance, ANSI/NCSL Z540.3, ISO 17025 · priority: differentiator · spine: `consumer_risk_level`, `producer_risk_level`, `magnitude_of_oot`, `impact_assessment_summary` on `OutOfToleranceInvestigation` · buildable now.
- **Closed-Loop NCR & CAPA Linkage** — Direct one-click or automated bridge from an OOT investigation into an enterprise Non-Conformance Report (`quality.NonConformanceReport` `QNCR-`) for lot disposition, and escalation into a formal CAPA (`quality.CapaInvestigation` `QCAP-`) for recurring or severe measurement drift. · seen in: ETQ Reliance, SimplerQMS, MasterControl Ax · priority: common · spine: FK `non_conformance_report`, FK `capa_investigation` on `OutOfToleranceInvestigation` · buildable now.
- **Product Disposition & Recall Evaluation** — Formal multi-disciplinary review (Material Review Board / Quality Management) determining product disposition: no impact (tolerance wide enough to absorb error), re-inspect quarantined stock, issue customer notification, or initiate product recall. · seen in: ETQ Reliance, MasterControl Ax, FDA 21 CFR Part 820 · priority: table-stakes · spine: `product_disposition`, `mrb_review_notes`, `quality_manager_signoff` on `OutOfToleranceInvestigation` · buildable now.
- **Root Cause & Drift Analysis** — Investigation of root cause categories (normal wear, mechanical shock/drop, thermal expansion, improper handling, electronic sensor drift) to prevent recurrence. · seen in: ETQ Reliance, Beamex CMX, GAGEtrak · priority: common · spine: `root_cause_category`, `corrective_preventive_actions` on `OutOfToleranceInvestigation` · buildable now.

### 4. Measurement System Analysis (MSA / Gage R&R)
- **Crossed Gage R&R Study (ANOVA and Xbar-R Methods)** — Statistical study where multiple appraisers/operators measure multiple parts in multiple randomized trials, calculating Repeatability (Equipment Variation - EV), Reproducibility (Appraiser Variation - AV), and Total Gage R&R (GRR) according to AIAG MSA 4th Edition guidelines. · seen in: Minitab, CyberMetrics GAGEtrak, PQ Systems GAGEpack · priority: table-stakes · spine: new table `MeasurementSystemAnalysis` (`QMSA-`), FK `CalibrationGage`, fields for ANOVA/Xbar-R statistics · buildable now.
- **Nested Gage R&R Study for Destructive Testing** — MSA study structure for destructive testing (e.g. tensile pull, burst pressure, chemical assay) where parts cannot be measured repeatedly by different operators, nesting parts within operators. · seen in: Minitab, AIAG MSA · priority: common · spine: `study_type="gage_rr_nested"` on `MeasurementSystemAnalysis` · buildable now.
- **Gage Linearity and Bias Studies** — Accuracy studies evaluating: (a) Bias: difference between observed average reading and a certified master reference standard value; (b) Linearity: change in bias across the gage's entire operating range (calculating slope, intercept, and $R^2$). · seen in: Minitab, AIAG MSA, GAGEtrak · priority: common · spine: `study_type="linearity_and_bias"`, `bias_value`, `bias_percentage`, `linearity_slope`, `linearity_r_squared` on `MeasurementSystemAnalysis` · buildable now.
- **Gage Stability Studies & Longitudinal Drift** — Evaluating total measurement variation over time on a single reference master, plotting measurements on an Xbar-R or I-MR control chart to verify absence of special causes and long-term calibration stability. · seen in: Minitab, Beamex CMX, AIAG MSA · priority: common · spine: `study_type="stability_study"` on `MeasurementSystemAnalysis` · buildable now.
- **Standardized MSA Acceptability Thresholds & Metrics** — Automatic calculation and classification of key AIAG metrics:
  - $\%GRR$ (Total Gage R&R as percentage of Study Variation or Tolerance): $<10\%$ = Acceptable, $10\%-30\%$ = Marginal / Conditional, $>30\%$ = Unacceptable.
  - $P/T$ Ratio (Precision-to-Tolerance ratio): $6 \times \sigma_{GRR} / \text{Tolerance}$.
  - $NDC$ (Number of Distinct Categories): $1.41 \times (PV / GRR)$; must be $\ge 5$ for an acceptable measurement system. · seen in: Minitab, CyberMetrics GAGEtrak, PQ Systems GAGEpack · priority: table-stakes · spine: `percent_gage_rr_study_variation`, `percent_tolerance_pt_ratio`, `number_of_distinct_categories_ndc`, `study_result` on `MeasurementSystemAnalysis` · buildable now.
- **Attribute Agreement Analysis (Attribute Gage R&R)** — Fleiss' kappa, Kendall's concordance, and percent agreement calculation for qualitative go/no-go plug gages or visual inspection systems. · seen in: Minitab, PQ Systems GAGEpack · priority: common · spine: `study_type="attribute_agreement"` on `MeasurementSystemAnalysis` · buildable now.

### 5. Calibration Vendor Management
- **Accredited Laboratory Qualification & Scope Directory** — Directory of third-party commercial calibration laboratories linked to unified `core.Party` records (`role="vendor"`), recording accreditation bodies (e.g., A2LA, ANAB, NVLAP, UKAS), ISO/IEC 17025 certificate numbers, expiration dates, and approved Calibration and Measurement Capabilities (CMC). · seen in: Fluke MET/TEAM, MasterControl Ax, SimplerQMS · priority: table-stakes · spine: reuses `core.Party`, `core.PartyRole`, links to `SupplierQualificationAudit` · buildable now.
- **Vendor Certificate Receipt & Audit Trail Maintenance** — Standardized intake process for external calibration certificates, verifying stated decision rules, test points, environmental parameters, and accredited laboratory signatures, with full change audit logging. · seen in: Fluke MET/TEAM, IndySoft, SimplerQMS · priority: table-stakes · spine: `CalibrationRecord` external lab fields, `core.AuditLog` · buildable now.
- **Calibration Vendor Performance & Turnaround Tracking** — Tracking vendor service lead times (days out of plant), certificate discrepancy rates, and calibration quality to feed supplier quality scorecards. · seen in: MasterControl Ax, CyberMetrics GAGEtrak, ETQ Reliance · priority: common · spine: links `CalibrationRecord` to `quality.SupplierQualityScorecard` · buildable now.

### Beyond the Bullets (High-value commercial differentiators)
- **Visual Calibration Due-Date Dashboard & Aging Bins** — Metrology dashboard categorizing active gage inventory into status buckets: *Overdue / Expired*, *Due within 7 Days*, *Due within 30 Days*, *In Calibration*, and *Active / In Service*, preventing surprise expirations. · seen in: Beamex CMX, GAGEtrak, PQ Systems GAGEpack · priority: differentiator · spine: view aggregation on `CalibrationGage` · buildable now.
- **Interval Optimization Analysis** — Historical drift tracking to recommend calibration interval extensions (for highly stable gages) or interval reductions (for frequently drifting gages), optimizing lab operating expenses while maintaining compliance. · seen in: Beamex CMX, Fluke MET/TEAM · priority: differentiator · spine: `calibrated_interval_override_months` on `CalibrationRecord` · buildable now.
- **Gage Clones & Procedural Equipment Templates** — Rapid creation of identical gages (e.g. duplicating caliper models across 20 machining stations) inheriting measurement ranges, default calibration intervals, tolerances, and calibration SOP references. · seen in: CyberMetrics GAGEtrak, IndySoft · priority: common · spine: form helper / clone action · buildable now.

---

## Recommended build scope (this pass — 4 models)

Following the standard NavERP sub-module unit (1–4 tenant-scoped models), Sub-module 12.10 builds **four core metrology and quality models** in `apps/quality/models/Calibration/`:

1. **`CalibrationGage`** [`QGAG-`] — Master equipment and gage registry for physical measurement instruments, tools, and reference standards.
   - **Fields/Choices justified by:** Centralized gage registry, equipment classification (`critical_ctq`, `standard_inspection`, `reference_standard`, `indication_only`), gage types (`caliper`, `micrometer`, `dial_indicator`, `pressure_gage`, `temperature_probe`, `torque_wrench`, `multimeter`, `scale_balance`, `cmm`, `optical_comparator`, `height_gage`, `plug_ring_gage`, `reference_standard`, `other`), measurement range (min/max/resolution/unit), tolerance limits (upper/lower), status (`active_in_service`, `calibration_due`, `out_of_service`, `quarantined_oot`, `in_calibration`, `retired`), interval tracking (interval months/days, last calibration date, next calibration due date), tool crib storage location, and NIST traceability number.
   - **FKs:** `core.Tenant` (TenantNumbered), `scm.Asset` (optional nullable link to physical plant asset), `scm.WorkCenter` (optional assigned cell/station), `core.OrgUnit` (owning department/lab), `accounts.User` (`custodian`), `core.Party` (`manufacturer`, optional `preferred_vendor`), `quality.ControlledDocument` (`calibration_procedure_doc`).

2. **`CalibrationRecord`** [`QCAL-`] — Individual calibration execution events (internal or external accredited lab).
   - **Fields/Choices justified by:** Dual As-Found and As-Left data tracking (`as_found_condition`, `as_left_condition`), calibration types (`internal_lab`, `external_accredited_lab`, `on_site_vendor`, `field_verification`), calibration dates, overall result status (`passed`, `passed_with_adjustments`, `conditional_pass_guardband`, `failed_out_of_tolerance`, `canceled`), metrology environmental conditions (temperature $^\circ\text{C}$, relative humidity $\%$), measurement uncertainty ($U$) and coverage factor ($k=2$), Test Uncertainty Ratio (TUR), decision rules (`simple_acceptance`, `binary_guardbanding_ilac_g8`, `non_binary_guardbanding`), certificate number, certificate issue date, external lab accreditation (`iso_17025_accredited`, `nist_traceable`, `ansi_z540`, `manufacturer_cert`), and interval adjustment overrides.
   - **FKs:** `core.Tenant` (TenantNumbered), `quality.CalibrationGage` (`gage`), `quality.CalibrationGage` (`reference_standard_used`), `accounts.User` (`performed_by`), `accounts.User` (`approved_by`), `core.Party` (`calibration_vendor`), `quality.ControlledDocument` (`procedure_followed`).

3. **`OutOfToleranceInvestigation`** [`QOOT-`] — Formal investigation and impact assessment initiated when a gage fails calibration or displays out-of-tolerance As-Found readings.
   - **Fields/Choices justified by:** Automated OOT containment, investigation lifecycle status (`open_containment`, `impact_analysis_in_progress`, `mrb_review`, `capa_pending`, `closed_no_impact`, `closed_product_recalled`), risk severity (`critical_high_risk`, `moderate_risk`, `low_negligible_risk`), numerical magnitude of OOT deviation, suspect operational window (`suspect_usage_window_start`, `suspect_usage_window_end`), counts of suspect work orders and lots evaluated, Consumer's Risk level (false acceptance probability), Producer's Risk level (false rejection probability), engineering impact assessment rationale, product disposition decisions (`no_action_tolerances_adequate`, `re_inspect_inventory`, `customer_quarantine_alert`, `formal_recall`, `scrap_wip`), root cause category (`normal_wear`, `handling_drop_impact`, `environmental_exposure`, `operator_misuse`, `component_drift`, `unknown`), and immediate containment actions.
   - **FKs:** `core.Tenant` (TenantNumbered), `quality.CalibrationRecord` (`calibration_record`), `quality.CalibrationGage` (`gage`), `quality.NonConformanceReport` (`non_conformance_report`, optional), `quality.CapaInvestigation` (`capa_investigation`, optional), `accounts.User` (`investigator`), `accounts.User` (`quality_manager_signoff`), `scm.WorkCenter` (`suspect_work_center`).

4. **`MeasurementSystemAnalysis`** [`QMSA-`] — Formal statistical Gage R&R and measurement system study per AIAG MSA 4th Edition.
   - **Fields/Choices justified by:** Study types (`gage_rr_crossed`, `gage_rr_nested`, `linearity_and_bias`, `stability_study`, `attribute_agreement`, `type_1_gage_study`), analysis methods (`anova`, `average_and_range_xbar_r`), study setup parameters (number of operators, parts, trials, total tolerance, master reference value), calculated variance components (Repeatability Equipment Variation EV, Reproducibility Appraiser Variation AV, Total Gage R&R GRR, Part Variation PV, Total Variation TV), AIAG standardized acceptability metrics ($\%GRR$ study variation percentage, $P/T$ precision-to-tolerance ratio, Number of Distinct Categories NDC), Linearity/Bias parameters (bias value, bias percentage, linearity slope, $R^2$), study result verdict (`acceptable`, `marginal_conditional`, `unacceptable`), and JSON storage of raw trial measurement matrices (`raw_study_data`).
   - **FKs:** `core.Tenant` (TenantNumbered), `quality.CalibrationGage` (`gage`), `accounts.User` (`study_lead`), `quality.ControlledDocument` (`study_protocol_doc`).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Finished Good Inspection Checklists & Final AQL Release** → Belongs to **Sub-module 12.9 (Final Quality Control / FQC / OQC)**. Calibrated gages built in 12.10 are selected by FQC inspectors during release testing.
- **Certificate of Conformance (CoC) Customer Generation** → Belongs to **Sub-module 12.9 (FQC/OQC)**.
- **Enterprise Quality Audit Programs & Annual Audit Schedules** → Belongs to **Sub-module 12.11 (Audit Management)**. Calibration vendor on-site facility audits and ISO 17025 surveillance audits are scheduled under 12.11, while 12.10 stores gage-specific calibration certificates.
- **Calibration Technician Qualification & Training Matrices** → Belongs to **Sub-module 12.12 (Training & Competency Management)**. Certifies metrologists to execute specific calibration protocols.
- **Chemical / Biological Reagent and Wet Laboratory Sample Management** → Belongs to **Sub-module 12.19 (Laboratory Information Management / LIMS)**.
- **Heavy Plant Asset Preventive Maintenance & Machine Work Orders** → Belongs to **Sub-module 4.10 (Enterprise Asset Management / CMMS)**. 12.10 links via optional FK to `scm.Asset` for metrological calibration, leaving mechanical lubrication and PM schedules to CMMS.
- **Inventory Lot Scrap Ledger Posting** → Belongs to **Module 5 (Inventory Management)**. OOT disposition flags scrap recommendations, but financial/stock movements wait for Module 5.

---

## Deferred (later passes / integrations)

- **Direct Calibrator Hardware Bi-Directional Drivers (GPIB / USB / VISA)** — Automated test script execution communicating with Fluke 5500A/5520A multi-product calibrators or Beamex MC6 documenting calibrators via IEEE 488 / VISA. Deferred to external lab automation connector service.
- **Continuous Environmental Chamber Telemetry (OPC-UA / MQTT)** — Real-time sensor streaming for temperature and humidity logging in metrology cleanrooms. `CalibrationRecord` provides manual entry fields now; IoT automated ingestion is registered as an external interface enhancement.
- **OCR Parsing of Vendor PDF Calibration Certificates** — Automated text/table extraction from third-party lab PDF certificates into `CalibrationRecord` test point JSON.
- **3D CMM Point-Cloud Mesh Alignment (CAD-to-Part)** — Direct coordinate measuring machine (CMM) DMIS/STEP CAD file inspection data ingestion.

---

## Verification & Architecture Checklist

- [x] Multi-tenancy: All 4 models extend `TenantNumbered` and `TenantOwned`, strictly filtered by `tenant=request.tenant`.
- [x] Autonumber prefixes: `QGAG-`, `QCAL-`, `QOOT-`, `QMSA-` verified **0 collisions** across the entire repository.
- [x] Core spine reuse: Reuses `core.Tenant`, `scm.Asset`, `scm.WorkCenter`, `core.OrgUnit`, `accounts.User`, `core.Party`, `core.PartyRole`, `core.AuditLog`, `quality.ControlledDocument`, `quality.NonConformanceReport`, `quality.CapaInvestigation`.
- [x] NavERP.md compliance: Fully covers all 5 bolded feature bullets in section `### 12.10 Calibration & Measurement System Analysis`.
- [x] Commercial leaders coverage: Synthesizes core capabilities from 9 market leaders (Fluke MET/TEAM, Beamex CMX, GAGEtrak, ETQ Reliance, MasterControl, Minitab, PQ Systems GAGEpack, IndySoft, SimplerQMS).
