# Research — Sub-module 12.11: Audit Management (Module 12 — Quality Management System, `quality`)

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

- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py`, prefix `QDOC`): Standard operating procedures (SOPs), audit protocols, checklists, and regulatory reference documents.
  - `CapaInvestigation` (`apps/quality/models/CapaManagement/CapaInvestigations.py`, prefix `QCAP`): Closed-loop CAPA investigations spawned from critical/major audit findings. Already includes `("internal_audit", "Internal Audit Finding")` and `("external_audit", "External Regulatory Audit")` in `SOURCE_TYPE_CHOICES`.
  - `NonConformanceReport` (`apps/quality/models/NonConformance/NonConformanceReports.py`, prefix `QNCR`): Non-conformance reports triggered directly by audit observations. Already includes `("internal_audit", "Internal Quality Audit")` in `SOURCE_TYPE_CHOICES`.
  - `ProcessDeviation` (`apps/quality/models/NonConformance/ProcessDeviations.py`, prefix `QDEV`): Concessions or process deviations audited for compliance.
  - `SupplierQualificationAudit` (`apps/quality/models/SupplierQuality/SupplierQualificationAudits.py`, prefix `QSQA`): Specialized external vendor onboarding and qualification audits (Module 12.6).
  - `LayeredProcessAudit` (`apps/quality/models/InProcessQuality/LayeredProcessAudits.py`, prefix `QLPA`): High-frequency operator/supervisor manufacturing process walk-through audits (Module 12.8).

- **Cross-module spine models available to FK:**
  - `core.Tenant` (`apps/core/models/Tenant.py:17`): Multi-tenant isolation foundation.
  - `core.OrgUnit` (`apps/core/models/OrgUnit.py:5`): Internal departments, branches, plants, or functional sites audited or hosting regulatory inspections.
  - `core.Party` (`apps/core/models/Party.py:5`) & `core.PartyRole` (`apps/core/models/PartyRole.py:5`): External auditees (vendors/contractors), accredited certification registrars/notified bodies (e.g. TÜV, BSI), and regulatory agencies (e.g. FDA, EMA).
  - `accounts.User` (`apps/accounts/models.py:52`): Lead auditors, audit team members, auditee representatives, front-room hosts, and back-room scribes.
  - `core.AuditLog` (`apps/core/models/AuditLog.py:5` + `write_audit_log` helper): Immutable tenant-scoped audit logging for 21 CFR Part 11 and ISO 19011 compliance.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and atomic retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Audited internal business units, plants, or departments. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Notified bodies, ISO registrars, external agencies, and vendors. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | Auditors, lead auditors, auditee managers, inspection hosts. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable audit trail for FDA 21 CFR Part 11 and ISO 19011 compliance. |
| `quality.ControlledDocument` exists | `apps/quality/models/DocumentControl/ControlledDocuments.py:8` | Audit checklists, protocols, and standard operating procedures. |
| `quality.CapaInvestigation` exists | `apps/quality/models/CapaManagement/CapaInvestigations.py:8` | Closed-loop corrective action tracking for audit non-conformances. |
| `quality.NonConformanceReport` exists | `apps/quality/models/NonConformance/NonConformanceReports.py:10` | Non-conformance records generated from audit findings. |
| `quality.SupplierQualificationAudit` exists | `apps/quality/models/SupplierQuality/SupplierQualificationAudits.py:10` | Sibling sub-module 12.6 vendor audit records. |
| `quality.LayeredProcessAudit` exists | `apps/quality/models/InProcessQuality/LayeredProcessAudits.py:10` | Sibling sub-module 12.8 manufacturing layered process audits. |

### Spine entities verified NOT to exist (or unbuilt in Module 12 / ERP)

- **Module 5 unbuilt masters:** `Item`, `LotSerial`, `UOM`, `StockMove` are planned for Module 5. Quality models use free-text stand-in fields (`product_scope`, `lot_number_sampled`) when audits sample specific physical items, ensuring complete loose-coupling without hard FKs to unbuilt tables.
- **Automated Video Conferencing Bots / Screen Recording:** Live virtual inspection streaming servers or automated AI audio scribes are external services. 12.11 delivers the complete QMS audit lifecycle, checklist evaluation, findings grading, CAPA escalation, and Front Room / Back Room inspection request tracking.

### Auto-number Prefix Collision Check (0 collisions verified)

Automated ripgrep scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QPRG` (Quality Audit Program) -> **0 collisions** (Completely free)
- `QAUD` (Quality Audit Execution) -> **0 collisions** (Completely free)
- `QFND` (Quality Audit Finding) -> **0 collisions** (Completely free)
- `QHST` (Quality Regulatory Inspection Host) -> **0 collisions** (Completely free)

---

## Leaders surveyed (with source links)

1. **MasterControl (Audit Excellence / Audit Management)** — Enterprise life sciences eQMS market leader for FDA 21 CFR Part 11/820, ISO 13485:2016, and cGMP compliance. Provides centralized annual audit scheduling, risk-based frequency assignment, dynamic checklist templates with objective evidence attachments, and automated closed-loop CAPA launching.
   - *Source:* https://www.mastercontrol.com/quality/audit-management/
2. **Veeva Vault QMS (Audit Management & Audit Room)** — Premier cloud-native pharma and medical device quality suite. Features integrated audit program planning with plan-vs-actual tracking, auditor qualification verification, automated checklist-to-finding generation, and an explicit digital "Audit Room" application facilitating Front Room / Back Room coordination during live regulatory inspections.
   - *Source:* https://www.veeva.com/products/vault-qms/
3. **Sparta Systems / TrackWise Digital (Audit Management)** — Honeywell enterprise quality platform built for life sciences and regulated manufacturing. Automates the full audit lifecycle across multi-site global operations, enforces standardized observation grading, bridges findings directly into CAPA, and supports pre-audit document packages and post-audit reporting.
   - *Source:* https://www.spartasystems.com/trackwise-digital/audit-management/
4. **ETQ Reliance (Audit Management Software)** — Flexible enterprise quality management platform. Provides centralized annual audit calendars, no-code checklist builders mapped to ISO and IATF standards, mobile/tablet execution with photo evidence logging, automated finding categorization, and executive compliance dashboards.
   - *Source:* https://www.etq.com/audit-management/
5. **Qualio (Audit Management & Compliance Intelligence)** — Fast-growing MedTech/pharma eQMS. Features continuous audit readiness dashboards, automated standard clause mapping (ISO 13485, FDA QMSR, EU MDR), clause-by-clause gap assessments, and instantaneous finding-to-CAPA escalation.
   - *Source:* https://www.qualio.com/product/audit-management
6. **MetricStream (Internal Audit Management / IAM & Connected Audit Universe)** — Leading enterprise GRC platform. Features an integrated "Audit Universe" connecting entities, risks, and controls; risk-based annual planning; auditor skills and availability allocation; digital workpapers; and executive board reporting.
   - *Source:* https://www.metricstream.com/products/internal-audit-management.html
7. **Intelex (Audit Management Software)** — Global EHS and Quality management software leader. Features automated audit scheduling by risk rating, customizable audit protocols, mobile offline audit execution, non-conformance logging, and cross-facility audit performance rollups.
   - *Source:* https://www.intelex.com/products/quality/audit-management/
8. **Ideagen (Ideagen Quality Management / Internal Audit / ISQM)** — High-reliability compliance and audit software. Employs Plan-Do-Check-Act (PDCA) governance, digital audit checklists, root-cause action tracking, and strict 21 CFR Part 11 electronic signature audit trails.
   - *Source:* https://www.ideagen.com/products/ideagen-internal-audit
9. **SAP S/4HANA QM / PLM (Audit Management)** — Enterprise ERP quality module providing structured 5-phase audit lifecycles (Planning, Preparation, Execution, Reporting, Follow-Up), integration with SAP Quality Notifications (CAPA), questionnaire evaluation scoring, and offline XML/Excel workpaper exchange.
   - *Source:* https://www.sap.com/products/scm/quality-management.html

---

## Feature catalog (this sub-module only)

### 1. Audit Program Planning
- **Annual Audit Program Definition** — Multi-year and annual quality audit programs defining high-level quality governance objectives, strategic focus areas, and scheduled fiscal year timeframes · seen in: *Veeva Vault, MetricStream, MasterControl, SAP QM* · priority: `table-stakes` · spine: new table `AuditProgram` (`QPRG`) · buildable now.
- **Audit Universe & Scope Hierarchy** — Catalog of auditable entities, business units, departments, plant sites, and processes ensuring comprehensive coverage without organizational blind spots · seen in: *MetricStream, SAP QM, Ideagen* · priority: `common` · spine: reuses `core.OrgUnit` · buildable now.
- **Risk-Based Audit Frequency & Prioritization** — Frequency assignment driven by process risk classification, historical non-conformance density, past audit results, and regulatory criticality (e.g. high-risk semi-annual vs. low-risk biennial) · seen in: *MasterControl, ETQ Reliance, Qualio, MetricStream* · priority: `table-stakes` · spine: fields in `AuditProgram` & `QualityAudit` · buildable now.
- **Auditor Resource Allocation & Capacity Budgeting** — Budgeted auditor person-hours, scheduling feasibility tracking, and auditor qualification/lead auditor assignment · seen in: *MetricStream, Intelex, Veeva Vault* · priority: `common` · spine: fields in `AuditProgram` and FKs to `accounts.User` · buildable now.
- **Plan vs. Actual Schedule Tracking** — Real-time comparison of planned audit schedule milestones against actual fieldwork initiation, completion, and report publishing · seen in: *Veeva Vault, SAP QM* · priority: `common` · spine: properties and date fields on `QualityAudit` · buildable now.

### 2. Audit Execution & Checklists
- **Multi-Type Audit Execution Protocols** — Configurable execution workflows supporting Internal System Audits, Process Audits, Product Audits, External Regulatory Inspections, Notified Body/Registrar Audits, and Customer Quality Audits · seen in: *MasterControl, TrackWise Digital, ETQ Reliance, Veeva Vault* · priority: `table-stakes` · spine: choices on `QualityAudit` (`QAUD`) · buildable now.
- **Standard Operating Procedure & Checklist Linking** — Direct association of governing SOPs, audit guidelines, and standard checklists from Document Control · seen in: *Veeva Vault (QualityDocs), MasterControl, Ideagen* · priority: `table-stakes` · spine: FK to `quality.ControlledDocument` · buildable now.
- **Audit Execution Methodologies** — Formal designation of On-Site, Remote/Virtual, Hybrid, or Desktop audit methodologies with specific protocols and communication channels · seen in: *ETQ Reliance, Intelex, MetricStream* · priority: `common` · spine: choices on `QualityAudit` · buildable now.
- **Objective Evidence Documentation** — Structured recording of sampling notes, interview records, document references, batch numbers inspected, and physical evidence descriptions · seen in: *MasterControl, TrackWise Digital, SAP QM* · priority: `table-stakes` · spine: text fields in `QualityAudit` and `AuditFinding` · buildable now.
- **Auditor Independence Validation** — Verification that lead auditors and audit team members do not audit their own functional reporting lines or direct work processes (ISO 19011 independence requirement) · seen in: *MasterControl, Ideagen, Veeva Vault* · priority: `common` · spine: clean validation comparing `lead_auditor` vs. `target_org_unit` · buildable now.

### 3. Audit Findings & Reporting
- **Standardized Observation Severity Grading** — Multi-tier finding classification (Critical / Major / Minor / Observation & OFI / Commendation) aligned with ISO 19011, ISO 13485, and FDA inspection standards · seen in: *All leaders (Veeva, MasterControl, TrackWise, ETQ, Qualio, SAP)* · priority: `table-stakes` · spine: new table `AuditFinding` (`QFND`) · buildable now.
- **Regulatory Standard & Clause Mapping** — Explicit tagging of findings to governing clauses (e.g., ISO 9001:2015 §9.2, ISO 13485:2016 §8.2.4, 21 CFR Part 820.22, IATF 16949 §9.2.2) · seen in: *Qualio, MasterControl, ETQ Reliance* · priority: `table-stakes` · spine: fields in `AuditFinding` · buildable now.
- **Executive Audit Summary & Overall Verdict** — Overall audit verdict (Conforming, Minor Findings, Major Findings, Critical Failure, Passed, Failed) with lead auditor executive summary for leadership presentation · seen in: *TrackWise Digital, MasterControl, SAP QM* · priority: `table-stakes` · spine: fields in `QualityAudit` · buildable now.
- **Automated Findings Counting & Metrics Rollup** — Real-time calculation of total findings, open findings, and findings broken down by severity for immediate reporting · seen in: *ETQ Reliance, MetricStream, Intelex* · priority: `table-stakes` · spine: cached fields and model properties on `QualityAudit` · buildable now.

### 4. Corrective Action Tracking
- **Closed-Loop Finding-to-CAPA Integration** — One-click or direct linkage from critical/major audit findings into formal CAPA investigations with full bi-directional traceability · seen in: *All leaders (MasterControl, Veeva, TrackWise, ETQ, Qualio, Ideagen)* · priority: `table-stakes` · spine: FK from `AuditFinding` to `quality.CapaInvestigation` · buildable now.
- **Immediate Non-Conformance Report (NCR) Logging** — Direct linkage to an internal Non-Conformance Report for isolated material/process defects identified during audit execution · seen in: *MasterControl, TrackWise Digital, Qualio* · priority: `common` · spine: FK from `AuditFinding` to `quality.NonConformanceReport` · buildable now.
- **Auditee Response Deadlines & Remediation Workflows** — Enforced turnaround timelines (e.g. 15-day or 30-day response window) for auditee owners to submit containment, root cause, and proposed corrective action plans · seen in: *MasterControl, TrackWise Digital, MetricStream* · priority: `table-stakes` · spine: fields and status choices in `AuditFinding` · buildable now.
- **Closure Verification & Effectiveness Check** — Formal verification by the lead auditor that implemented corrective actions have been verified and confirmed effective prior to finding closure · seen in: *Veeva Vault, TrackWise Digital, ETQ Reliance* · priority: `table-stakes` · spine: verification fields in `AuditFinding` · buildable now.

### 5. Regulatory & Certification Audits
- **External Regulatory & Registrar Inspection Hosting** — Dedicated management of high-stakes inspections by FDA (QSIT), ISO Notified Bodies (MDR, ISO 13485), ISO Registrars, and Customer Corporate Quality teams · seen in: *Veeva Vault (Audit Room), MasterControl, QMSdesk* · priority: `table-stakes` · spine: new table `RegulatoryInspectionHost` (`QHST`) · buildable now.
- **Front Room / Back Room Command Center Coordination** — Formal designation of Front Room host/spokesperson, Back Room coordination lead, official scribe, and war room location to manage inspector interactions seamlessly · seen in: *Veeva Vault, MasterControl, Jama Software* · priority: `differentiator` · spine: FKs and fields in `RegulatoryInspectionHost` · buildable now.
- **Inspector Request & Fulfillment Tracking** — High-speed logging and fulfillment tracking for documents, procedures, batch records, and personnel interview requests made by inspectors during active audits · seen in: *Veeva Vault (Inspection Management), MasterControl* · priority: `common` · spine: request counter fields and tracking in `RegulatoryInspectionHost` · buildable now.
- **Inspection Outcome & Notice Logging (FDA 483 / Warning Letter / NAI / VAI / OAI)** — Formal recording of official regulatory inspection outcomes, including FDA Form 483 issuance, observation count, and agency classifications · seen in: *MasterControl, Veeva Vault, TrackWise Digital* · priority: `table-stakes` · spine: outcome choices in `RegulatoryInspectionHost` · buildable now.

### 6. Beyond the Bullets
- **Standard Framework Multi-Mapping** — Pre-configured framework selectors encompassing ISO 9001, ISO 13485, IATF 16949, FDA 21 CFR 820 / QMSR, EU MDR 2017/745, and cGMP 21 CFR 211, enabling cross-standard compliance auditing · seen in: *Qualio, ETQ Reliance, Ideagen* · priority: `differentiator` · spine: choices in `QualityAudit` · buildable now.
- **Daily Wrap-Up & Closing Conference Memo** — Structured capture of daily debriefs between lead auditors/inspectors and company executive management · seen in: *Veeva Vault, MasterControl* · priority: `common` · spine: text fields in `RegulatoryInspectionHost` · buildable now.

---

## Recommended build scope (this pass — 4 models)

### Model 1: `AuditProgram` [NUMBER_PREFIX = "QPRG"]
- **Purpose:** Central entity for managing annual and strategic multi-year audit programs, scoping the audit universe, risk-based frequency scheduling, and allocating auditor capacity.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QPRG`)
  - `title` (`CharField(255)`): Program title (e.g. "FY2026 Enterprise Quality & Regulatory Audit Program")
  - `program_year` (`PositiveIntegerField`): Operating year (e.g. 2026)
  - `program_type` (`CharField(32)`): `internal_qms` (Internal QMS Audits), `supplier_external` (Supplier/Vendor Audits), `regulatory_certification` (Regulatory & Notified Body Audits), `integrated_enterprise` (Integrated Global Quality Program)
  - `risk_basis` (`CharField(32)`): `low_risk_annual` (Annual - Low Risk), `medium_risk_biennial` (Biennial - Moderate Risk), `high_risk_semi_annual` (Semi-Annual - High Risk / CTQ), `for_cause_triggered` (Event / CAPA Driven)
  - `scope_description` (`TextField`): Program coverage, objectives, and audit universe definition
  - `start_date` (`DateField`), `end_date` (`DateField`): Operational validity timeframe
  - `allocated_budget_hours` (`PositiveIntegerField(default=0)`): Budgeted auditor person-hours
  - `status` (`CharField(24)`): `draft`, `submitted`, `approved`, `active`, `completed`, `cancelled`
  - `program_manager` (`ForeignKey(settings.AUTH_USER_MODEL, related_name="managed_audit_programs")`)
  - `approved_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="approved_audit_programs")`)
  - `approval_date` (`DateField(null=True, blank=True)`)
  - `notes` (`TextField(blank=True)`)
- **Properties / Methods:**
  - `progress_percentage`: Percentage of scheduled audits completed.
  - `total_audits_count`, `completed_audits_count`, `open_audits_count`.
- **Verified FKs:** `core.Tenant`, `accounts.User`.

### Model 2: `QualityAudit` [NUMBER_PREFIX = "QAUD"]
- **Purpose:** Primary execution entity representing an individual audit instance—internal system, process, product, supplier, certification body, or regulatory agency audit.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QAUD`)
  - `program` (`ForeignKey("quality.AuditProgram", null=True, blank=True, related_name="audits")`): Parent audit program (nullable for ad-hoc or unannounced for-cause audits)
  - `title` (`CharField(255)`): Specific audit scope (e.g. "ISO 13485 Internal Audit - Design & Document Control")
  - `audit_type` (`CharField(32)`): `internal_system` (Internal Quality System Audit), `internal_process` (Manufacturing / Process Audit), `internal_product` (Product Quality Audit), `supplier_qualification` (Supplier Quality Audit), `regulatory_fda` (FDA Regulatory Inspection), `certification_notified_body` (ISO / Notified Body Audit), `customer_audit` (Customer / Client Quality Audit), `special_for_cause` (Special / For-Cause Investigation Audit)
  - `audit_method` (`CharField(24)`): `on_site` (On-Site Audit), `remote_virtual` (Remote / Virtual Audit), `hybrid` (Hybrid Audit), `desk_audit` (Desk / Off-Site Document Review)
  - `standard_framework` (`CharField(32)`): `iso_9001_2015`, `iso_13485_2016`, `iatf_16949`, `fda_21cfr820_qmsr`, `eu_mdr_2017_745`, `gmp_21cfr211`, `as9100d`, `multiple_frameworks`, `internal_sop`
  - `target_org_unit` (`ForeignKey("core.OrgUnit", null=True, blank=True, related_name="audited_units")`): Audited department, plant, or facility
  - `external_entity` (`ForeignKey("core.Party", null=True, blank=True, related_name="external_audits")`): Audited supplier, inspecting agency, or registrar
  - `lead_auditor` (`ForeignKey(settings.AUTH_USER_MODEL, related_name="led_quality_audits")`): Lead auditor or primary host
  - `auditee_lead` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="received_quality_audits")`): Auditee department lead or key contact
  - `audit_checklist_sop` (`ForeignKey("quality.ControlledDocument", null=True, blank=True, related_name="referenced_in_audits")`): Governing audit checklist or procedure SOP
  - `planned_start_date` (`DateField`), `planned_end_date` (`DateField`)
  - `actual_start_date` (`DateField(null=True, blank=True)`), `actual_end_date` (`DateField(null=True, blank=True)`)
  - `scope_objectives` (`TextField`): Scope boundaries, criteria, and audit objectives
  - `status` (`CharField(24)`): `scheduled`, `in_preparation`, `in_progress`, `reporting`, `capa_pending`, `closed`, `cancelled`
  - `outcome` (`CharField(32)`): `pending` (Assessment Pending), `conforming` (Conforming / No Deficiencies), `minor_findings` (Minor Deficiencies Only), `major_findings` (Major Deficiencies Identified), `critical_non_conformance` (Critical Non-Conformance), `passed` (Passed / Satisfactory), `conditional_pass` (Conditional Approval), `failed` (Failed / Unsatisfactory)
  - `executive_summary` (`TextField(blank=True)`): Management summary, positive observations, and conclusion
  - `report_published_date` (`DateField(null=True, blank=True)`)
  - `total_findings_count` (`PositiveIntegerField(default=0)`)
  - `critical_findings_count` (`PositiveIntegerField(default=0)`)
  - `major_findings_count` (`PositiveIntegerField(default=0)`)
  - `minor_findings_count` (`PositiveIntegerField(default=0)`)
  - `ofi_findings_count` (`PositiveIntegerField(default=0)`)
- **Properties / Methods:**
  - `is_overdue`: Boolean indicating whether scheduled dates have passed without closure.
  - `days_open`: Working age of audit from actual start to closure.
- **Verified FKs:** `core.Tenant`, `quality.AuditProgram`, `core.OrgUnit`, `core.Party`, `accounts.User`, `quality.ControlledDocument`.

### Model 3: `AuditFinding` [NUMBER_PREFIX = "QFND"]
- **Purpose:** Granular non-conformance and observation record logged during audit execution, with severity grading, requirement citation, objective evidence, and closed-loop linkage to CAPA and NCR.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QFND`)
  - `audit` (`ForeignKey("quality.QualityAudit", on_delete=models.CASCADE, related_name="findings")`)
  - `finding_number_in_audit` (`PositiveSmallIntegerField(default=1)`): Sequential number within audit (e.g. 1, 2, 3...)
  - `title` (`CharField(255)`): Finding summary headline
  - `severity` (`CharField(24)`): `critical` (Critical Non-Conformance - Regulatory / Patient Safety Risk), `major` (Major Non-Conformance - Systemic Process Breakdown), `minor` (Minor Non-Conformance - Isolated Procedural Lapse), `observation_ofi` (Opportunity for Improvement / OFI), `commendation` (Commendation / Best Practice)
  - `standard_clause` (`CharField(128)`): Standard & clause cited (e.g. "ISO 13485:2016 §8.2.4", "21 CFR 820.22", "SOP-QMS-012 Rev 4")
  - `requirement_statement` (`TextField`): Specified requirement or procedure text
  - `condition_evidence` (`TextField`): Objective evidence observed during audit proving non-conformance
  - `audited_org_unit` (`ForeignKey("core.OrgUnit", null=True, blank=True, related_name="unit_audit_findings")`)
  - `assignee` (`ForeignKey(settings.AUTH_USER_MODEL, related_name="assigned_audit_findings")`): Responsible auditee owner
  - `response_due_date` (`DateField`): Target deadline for auditee response (e.g. 15 or 30 days)
  - `response_received_date` (`DateField(null=True, blank=True)`)
  - `containment_action` (`TextField(blank=True)`): Immediate correction taken to contain finding
  - `root_cause_summary` (`TextField(blank=True)`): Root cause analysis summary submitted by auditee
  - `corrective_action_plan` (`TextField(blank=True)`): Proposed corrective & preventive action plan
  - `linked_capa` (`ForeignKey("quality.CapaInvestigation", null=True, blank=True, on_delete=models.SET_NULL, related_name="source_audit_findings")`): Formal closed-loop CAPA record
  - `linked_ncr` (`ForeignKey("quality.NonConformanceReport", null=True, blank=True, on_delete=models.SET_NULL, related_name="source_audit_findings")`): Immediate non-conformance report
  - `status` (`CharField(28)`): `draft`, `issued`, `response_submitted`, `response_accepted`, `capa_in_progress`, `verification_pending`, `closed`, `escalated`
  - `closure_verified_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="verified_audit_findings")`)
  - `closed_date` (`DateField(null=True, blank=True)`)
  - `closure_notes` (`TextField(blank=True)`): Auditor verification rationale and closure evidence
- **Properties / Methods:**
  - `is_overdue`: Response past `response_due_date` without response submission.
- **Verified FKs:** `core.Tenant`, `quality.QualityAudit`, `core.OrgUnit`, `accounts.User`, `quality.CapaInvestigation`, `quality.NonConformanceReport`.

### Model 4: `RegulatoryInspectionHost` [NUMBER_PREFIX = "QHST"]
- **Purpose:** Specialized inspection readiness and hosting entity designed for external audits by FDA, ISO Notified Bodies, and Customers, orchestrating the Front Room / Back Room command center logistics, request tracking, and formal inspection outcomes.
- **Fields & Choices Justified by Research:**
  - `tenant` (`ForeignKey("core.Tenant")`)
  - `number` (`CharField(32)`, prefix `QHST`)
  - `audit` (`ForeignKey("quality.QualityAudit", null=True, blank=True, on_delete=models.SET_NULL, related_name="regulatory_hosts")`): Linked QualityAudit record
  - `inspection_title` (`CharField(255)`): Inspection title (e.g. "FDA cGMP / QSIT Inspection - Medical Device Facility")
  - `agency_or_body` (`CharField(32)`): `fda_cdrh` (US FDA - CDRH Devices), `fda_cder` (US FDA - CDER Drugs), `iso_notified_body` (EU Notified Body / MDR), `ema_eu` (European Medicines Agency), `health_canada` (Health Canada), `pmda_japan` (PMDA Japan), `customer_corporate` (Customer Corporate Quality), `iso_registrar` (ISO Accredited Registrar), `other_authority` (Other Regulatory Authority)
  - `agency_name` (`CharField(128)`): Official organization name (e.g. "TÜV SÜD Product Service GmbH", "US FDA - District Office")
  - `lead_inspector_name` (`CharField(128)`): Lead inspector / investigator name
  - `inspector_credentials` (`CharField(128)`, blank=True): Badge number, division, or contact identifier
  - `inspection_purpose` (`CharField(32)`): `routine_surveillance` (Routine Surveillance Inspection), `pre_approval_pma_nda` (Pre-Approval Inspection / PAI), `for_cause_directed` (For-Cause / Directed Inspection), `unannounced_inspection` (Unannounced Inspection), `mdsap_audit` (MDSAP Comprehensive Audit), `recertification_audit` (Triennial Recertification Audit)
  - `announcement_status` (`CharField(20)`): `announced`, `unannounced`, `short_notice`
  - `scheduled_start_date` (`DateField`), `scheduled_end_date` (`DateField`)
  - `actual_start_date` (`DateField(null=True, blank=True)`), `actual_end_date` (`DateField(null=True, blank=True)`)
  - `front_room_lead` (`ForeignKey(settings.AUTH_USER_MODEL, related_name="hosted_front_rooms")`): Primary company spokesperson / Front Room facilitator
  - `back_room_lead` (`ForeignKey(settings.AUTH_USER_MODEL, related_name="managed_back_rooms")`): Back Room staging and document coordination manager
  - `scribe_user` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="scribed_inspections")`): Official inspection scribe and request logger
  - `war_room_location` (`CharField(255)`): Staging conference room or secure virtual bridge room
  - `status` (`CharField(28)`): `preparation`, `active_inspection`, `daily_wrapup`, `inspection_closed`, `post_inspection_followup`
  - `requests_logged_count` (`PositiveIntegerField(default=0)`): Number of records/documents requested by inspectors
  - `requests_fulfilled_count` (`PositiveIntegerField(default=0)`): Number of requests successfully fulfilled
  - `form_483_issued` (`BooleanField(default=False)`): Whether FDA Form 483 / Inspectional Observations notice was issued
  - `observations_count` (`PositiveIntegerField(default=0)`): Number of formal inspection observations / Form 483 citations
  - `formal_outcome` (`CharField(32)`): `pending` (Pending Final Agency Determination), `nai_no_action_indicated` (NAI - No Action Indicated / Clear), `vai_voluntary_action_indicated` (VAI - Voluntary Action Indicated), `oai_official_action_indicated` (OAI - Official Action Indicated), `certified_unconditional` (Full Unconditional Certification), `conditional_clearance` (Conditional Clearance), `refusal_warning_letter` (Warning Letter / Certificate Suspension)
  - `daily_summary_notes` (`TextField(blank=True)`): Daily wrap-up log, inspector queries, and focus areas
  - `closeout_memo` (`TextField(blank=True)`): Final inspection exit conference debrief and executive response commitments
- **Properties / Methods:**
  - `fulfillment_rate`: Percentage of inspector document requests fulfilled.
  - `is_active`: Inspection currently in session.
- **Verified FKs:** `core.Tenant`, `quality.QualityAudit`, `accounts.User`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Master Document Authoring, Approval & Checklists (`ControlledDocument`)** -> Belongs to **Sub-module 12.1 Document Control & Management**. 12.11 links to `ControlledDocument` for SOPs and protocols, but authoring stays in 12.1.
- **CAPA Investigations, 8D Root Cause Analysis & Action Plans (`CapaInvestigation`)** -> Belongs to **Sub-module 12.4 CAPA Management**. 12.11 findings link directly to `CapaInvestigation` via foreign key, but the 8D investigation and effectiveness review remain in 12.4.
- **Non-Conformance Reports & Material Review Board Disposition (`NonConformanceReport`)** -> Belongs to **Sub-module 12.5 Non-Conformance & Deviation Management**. 12.11 findings link to `NonConformanceReport`, but MRB dispositioning remains in 12.5.
- **Supplier Qualification & Onboarding Audits (`SupplierQualificationAudit`)** -> Built in **Sub-module 12.6 Supplier & Vendor Quality Management**. 12.6 owns vendor qualification audits and AVL status; 12.11 handles corporate quality audits, internal audits, and regulatory inspections.
- **Layered Process Audits (`LayeredProcessAudit`)** -> Built in **Sub-module 12.8 In-Process Quality Control**. 12.8 owns high-frequency shift/daily supervisory production walk-throughs; 12.11 owns periodic and annual comprehensive QMS system/process audits.
- **Internal Auditor Training Records & Competency Matrices** -> Belongs to **Sub-module 12.12 Training & Competency Management**. 12.11 designates qualified auditors via `accounts.User`, while curriculum completion and qualification certificates belong to 12.12.
- **Regulatory Vigilance & Adverse Event Reporting (MDR / MAUDE / Recalls)** -> Belongs to **Sub-module 12.13 Customer Complaint Handling**. 12.11 logs external inspections and Form 483 responses, while post-market adverse event reporting belongs to 12.13.

---

## Deferred (later passes / integrations)

- **Offline Mobile Field Audit Execution & Local SQLite Sync** — Dedicated offline tablet PWA caching with background bi-directional sync for remote auditors in cleanrooms or signal-blocked factory floors. (Planned for mobile field-suite pass).
- **Automated AI Evidence Extraction & Voice Scribing** — Computer vision OCR of physical machine calibration labels and real-time voice-to-text dictation for auditors during walk-throughs.
- **Direct FDA ESG / EUDAMED Regulatory Portal Gateway** — Automated machine-to-machine transmission of Form 483 response submissions and inspection packets to FDA Electronic Submissions Gateway (ESG).
- **Live Real-Time WebSocket Channel for War Room Request Push** — Sub-second push notification bridge between Front Room and Back Room. (Standard Django/HTMX polling implemented now; WebSockets deferred).
