# Research — Sub-module 12.5: Non-Conformance & Deviation Management (Module 12 — Quality Management System, `quality`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 12 so far (`apps/core/navigation.py`):**
  - `"12.1"` (Document Control & Management):
    - `"Document Creation & Authoring": "quality:controlled_document_list"`
    - `"Review & Approval Workflows": "quality:electronic_signature_list"`
    - `"Document Distribution & Obsolescence": "quality:document_acknowledgment_list"`
    - `"Change Request & Revision Control": "quality:document_change_order_list"`
    - `"Archive & Retrieval": "quality:document_archive_vault"`
  - `"12.2"` (Design Controls & Development Quality):
    - `"Design Planning & Inputs": "quality:design_project_list"`
    - `"Design Reviews & Verification": "quality:design_review_list"`
    - `"Design Validation & Transfer": "quality:design_verification_list"`
    - `"Design History File (DHF)": "quality:traceability_matrix"`
    - `"Design Changes & Configuration Management": "quality:design_input_list"`
  - `"12.3"` (Quality Risk Management / ISO 14971):
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
  - **`12.5` is the fifth sub-module of Module 12.**

- **Sibling models available to FK in `apps/quality/models/`:**
  - `ControlledDocument` (`apps/quality/models/DocumentControl/ControlledDocuments.py`, prefix `QDOC`): Standard Operating Procedures, inspection specs, work instructions referenced in NCR containment or rework procedures.
  - `DocumentChangeOrder` (`apps/quality/models/DocumentControl/DocumentChangeOrders.py`, prefix `QDCR`): Formal change orders triggered when an NCR disposition requires drawing or spec revision.
  - `ElectronicSignatureRecord` (`apps/quality/models/DocumentControl/ElectronicSignatures.py`, prefix `QSIG`): 21 CFR Part 11 compliant digital signatures for MRB disposition sign-offs and deviation approvals.
  - `DesignProject` (`apps/quality/models/DesignControls/DesignProjects.py`, prefix `QDPL`): Master medical device/hardware engineering project linked when non-conformance originates in design transfer.
  - `RiskAssessment` (`apps/quality/models/RiskManagement/RiskAssessments.py`, prefix `QRSK`): FMEA failure modes linked to non-conformances to assess critical safety impact.
  - `CapaInvestigation` (`apps/quality/models/CapaManagement/CapaInvestigations.py`, prefix `QCAP`): Enterprise CAPA record spawned from recurring or critical non-conformances.

- **Base classes in `apps/quality/models/_base.py`:**
  - `TenantOwned`: Multi-tenant isolation base (`tenant`, `created_at`, `updated_at`).
  - `TenantNumbered`: Autonumbering base class with `next_number(type(self), self.tenant, self.NUMBER_PREFIX)` and 5-attempt atomic collision retry loop.

### Spine entities verified to EXIST (grep evidence)

| Claim | Evidence | Note |
|---|---|---|
| `core.Tenant` exists | `apps/core/models/Tenant.py:17` -> `class Tenant(models.Model)` | Multi-tenant isolation foundation. |
| `core.OrgUnit` exists | `apps/core/models/OrgUnit.py:5` -> `class OrgUnit(models.Model)` | Department, plant, quality unit, manufacturing work center ownership. |
| `core.Party` & `PartyRole` exist | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Suppliers, customers, external inspectors, and internal personnel. |
| `core.AuditLog` exists | `apps/core/models/AuditLog.py:5` + `write_audit_log` helper | Immutable tenant audit logging for NCR status changes, MRB votes, and quarantine releases. |
| `accounts.User` exists | `apps/accounts/models.py:52` -> `class User(AbstractBaseUser, PermissionsMixin)` | System users for initiator, MRB members, disposition approvers, and deviation authorizers. |
| `quality.CapaInvestigation` exists | `apps/quality/models/CapaManagement/CapaInvestigations.py:8` | Direct bidirectional linkage: high-severity NCRs trigger CAPA investigations. |
| `quality.RiskAssessment` exists | `apps/quality/models/RiskManagement/RiskAssessments.py:8` | Risk severity linkage for safety/criticality assessments. |

### Spine entities verified NOT to exist (or unbuilt in Module 12)

- **Module 5 unbuilt inventory/catalog masters:** `Item`, `Location`, `StockMove`, `LotSerial`, and `UOM` are not built yet. Non-conformance and deviation models use robust, normalized character and text stand-ins (`item_code`, `item_name`, `lot_serial_number`, `batch_number`, `quarantine_location_name`, `unit_of_measure`) with an explicit future migration path to Module 5 foreign keys.
- **Module 12 later sub-modules (not built yet):**
  - Sub-module 12.6 Supplier Quality Management (`apps/quality` has no SCAR models yet; NCRs record supplier via `core.Party` role).
  - Sub-module 12.7 Incoming Quality Control (`apps/quality` has no IQC inspection models yet; NCRs record incoming inspection findings via source classification).
  - Sub-module 12.13 Customer Complaints (`apps/quality` has no complaint models yet; customer non-conformances capture party and reference).

### Candidate prefix collision check (repo-wide automated verification)

Automated ripgrep scan across all `NUMBER_PREFIX` declarations in `apps/`:
- `QNCR` (Quality Non-Conformance Report) -> **0 collisions** (Completely free)
- `QCNT` (Quality Quarantine & Containment Action) -> **0 collisions** (Completely free)
- `QMRB` (Quality Material Review Board Disposition) -> **0 collisions** (Completely free)
- `QDEV` (Quality Process Deviation & Temporary Concession) -> **0 collisions** (Completely free)

---

## Leaders surveyed (with source links)

1. **MasterControl Quality Excellence (Nonconformance & Deviation)** — Enterprise life sciences eQMS leader (FDA 21 CFR Part 820.90 / 820.100, ISO 13485:2016 §8.3, ISO 9001:2015 §8.7). Provides end-to-end non-conformance event intake from manufacturing, lab, receiving, and packaging. Features automated immediate containment holds (digital stop-ships and physical quarantine flags), guided risk-matrix classification (Critical/Major/Minor), collaborative cross-functional Material Review Board (MRB) voting, disposition tracking (Scrap, Rework, Return to Vendor, Concession/Use-As-Is), and automated escalation to CAPA for recurring or critical events.
   - *Source:* `https://www.mastercontrol.com/quality/nonconformance/`
2. **ETQ Reliance (Ideagen) (Nonconformance Management & MRB)** — Enterprise multi-site manufacturing QMS. Features configurable non-conformance logging, automated electronic quarantine routing, inventory hold reconciliation, multi-member MRB disposition workflows with tiered approval authorities, cost-of-quality tracking (scrap costs, rework labor, vendor chargebacks), and integrated root cause tagging.
   - *Source:* `https://www.etq.com/nonconformance-management-software/`
3. **Veeva Vault QMS (Nonconformance, Deviation & Quality Events)** — Cloud-native pharma and medical device platform. Handles planned deviations (temporary engineering changes or process exemptions) vs. unplanned deviations (spontaneous out-of-spec events). Enforces strict investigation timelines, affected batch impact assessments, field alert / regulatory reportability evaluations, and segregation of suspect materials.
   - *Source:* `https://www.veeva.com/products/vault-qms/`
4. **Qualio (Quality Events, Non-Conformances & Containment)** — Fast-growing life sciences QMS. Streamlined incident logging straight from the manufacturing floor or quality control station. Features immediate suspect lot isolation, digital red-tagging, containment verification checklists, disposition approval trees, and Pareto analytics by product line, defect code, and department.
   - *Source:* `https://www.qualio.com/product/non-conformance`
5. **ComplianceQuest (Salesforce-native QMS: Non-Conformance & MRB)** — Cloud-first manufacturing and life sciences solution. Strong focus on Material Review Board workflows, multi-department electronic sign-offs, quarantine inventory balance tracking, rework routing instructions, supplier debit memo triggers, and comprehensive Cost of Poor Quality (COPQ) analytics.
   - *Source:* `https://www.compliancequest.com/nonconformance-management-software/`
6. **Sparta Systems TrackWise / TrackWise Digital (Honeywell)** — Global pharmaceutical and medical device enterprise standard. Deep non-conformance categorization (material defect, procedural failure, environmental out-of-trend, equipment malfunction, packaging/labeling error), lot tracing and disposition tracking, containment hold release audits, and regulatory health authority notification assessments.
   - *Source:* `https://www.spartasystems.com/trackwise-digital/quality-event-management/`
7. **QT9 QMS (Nonconforming Product & Deviation Management)** — Mid-market manufacturing QMS with robust ISO 9001 / ISO 13485 / AS9100 compliance. Integrates quarantine inventory tagging, MRB committee reviews, deviation expiry date controls, rework sign-off inspections, and real-time scrap quantity recording.
   - *Source:* `https://qt9qms.com/modules/nonconforming-product/`
8. **Greenlight Guru (Medical Device Nonconformance & Risk)** — MedTech dedicated platform. Emphasizes risk-based nonconformance triage, tie-ins to ISO 14971 risk files, rapid containment actions to prevent release of suspect medical devices, formal MRB disposition documentation, and direct escalation to CAPA.
   - *Source:* `https://www.greenlight.guru/nonconformance-management-software`

---

## Feature catalog (this sub-module only)

### 1. NCR Initiation & Classification (NavERP.md bullet 1)
- **Multi-Source Non-Conformance Capture** — Log NCRs arising from incoming inspection, in-process manufacturing, final product release, packaging/labeling, customer returns, or facility environmental excursions.
  - *Seen in:* MasterControl, ETQ Reliance, Qualio, Veeva Vault
  - *Priority:* `table-stakes`
  - *Spine:* New model `NonConformanceReport` (`QNCR-`), optional FK to `core.OrgUnit`, `accounts.User` (initiator/owner), `core.Party` (supplier/customer).
  - *Status:* Buildable now.
- **Hierarchical Classification & Defect Coding** — Classify by source category (`material`, `process`, `product`, `supplier`, `facility`, `documentation`), defect type (`dimension_out_of_spec`, `contamination`, `packaging_integrity`, `labeling_error`, `functional_failure`, `procedural_deviation`), and severity level (`minor`, `major`, `critical`).
  - *Seen in:* Sparta TrackWise, QT9, ETQ Reliance
  - *Priority:* `table-stakes`
  - *Spine:* Fields on `NonConformanceReport`.
  - *Status:* Buildable now.
- **Affected Material Identification & Quantity Accounting** — Track affected item code, item description, lot/batch numbers, serial numbers, total quantity inspected, total quantity non-conforming, unit of measure, and estimated financial exposure.
  - *Seen in:* ComplianceQuest, MasterControl, QT9
  - *Priority:* `table-stakes`
  - *Spine:* Fields on `NonConformanceReport`. Stand-in for unbuilt `inventory.Item`.
  - *Status:* Buildable now.

### 2. Containment & Segregation (NavERP.md bullet 2)
- **Quarantine Hold & Physical/Digital Segregation** — Immediately isolate suspect inventory to prevent unintended use, movement, or shipment. Document quarantine location (e.g. "Quarantine Cage A", "Rework Staging 3", "Biohazard Holding").
  - *Seen in:* MasterControl, Qualio, Greenlight Guru, QT9
  - *Priority:* `table-stakes`
  - *Spine:* Dedicated model `QuarantineContainment` (`QCNT-`) FK to `NonConformanceReport`.
  - *Status:* Buildable now.
- **Physical Red-Tagging & Digital Hold Flags** — Record physical red-tag numbers, digital hold flags, stop-ship flags, and stop-production triggers. Record date/time hold applied and hold authorized by user.
  - *Seen in:* ETQ Reliance, Sparta TrackWise, ComplianceQuest
  - *Priority:* `table-stakes`
  - *Spine:* Fields on `QuarantineContainment`.
  - *Status:* Buildable now.
- **Controlled Quarantine Release Workflow** — Support partial or full release from quarantine following authorized disposition approval, with verification of release criteria, release authorization signatures, and reconciliation of released vs. scrapped quantities.
  - *Seen in:* Veeva Vault, MasterControl, ComplianceQuest
  - *Priority:* `common`
  - *Spine:* Fields and state machine on `QuarantineContainment`.
  - *Status:* Buildable now.

### 3. Disposition & Material Review (NavERP.md bullet 3)
- **Material Review Board (MRB) Convening & Committee Review** — Formal convening of cross-functional MRB committee (Quality Engineering, Operations, Manufacturing Engineering, Regulatory Affairs) to review complex or high-value defects.
  - *Seen in:* ComplianceQuest, ETQ Reliance, MasterControl
  - *Priority:* `table-stakes`
  - *Spine:* Dedicated model `MrbDisposition` (`QMRB-`) FK to `NonConformanceReport`.
  - *Status:* Buildable now.
- **Standard Disposition Decisions & Technical Justification** — Disposition choices: `scrap` (unusable/destroy), `rework` (return to original specification via approved instructions), `repair` (non-standard repair bringing to usable condition), `use_as_is` (concession requiring engineering safety rationale), `return_to_vendor` (RTV to supplier), or `regrade` (downgrade to secondary application).
  - *Seen in:* All 8 leaders
  - *Priority:* `table-stakes`
  - *Spine:* Fields on `MrbDisposition`.
  - *Status:* Buildable now.
- **Rework Instructions & Re-Inspection Verification** — Document step-by-step rework/repair procedures, assign rework technicians, specify post-rework quality re-inspection criteria, and capture reinspection pass/fail outcomes.
  - *Seen in:* QT9, ETQ Reliance, ComplianceQuest
  - *Priority:* `common`
  - *Spine:* Fields on `MrbDisposition`.
  - *Status:* Buildable now.
- **Cost of Poor Quality (COPQ) Tracking** — Track total scrap material cost, rework labor hours and labor cost, vendor return restocking fees, and total non-conformance financial impact.
  - *Seen in:* ComplianceQuest, ETQ Reliance, Sparta TrackWise
  - *Priority:* `common`
  - *Spine:* Fields on `MrbDisposition` (`scrap_cost`, `rework_labor_cost`, `vendor_chargeback_cost`, `total_financial_impact`).
  - *Status:* Buildable now.

### 4. Impact Assessment & Process Deviation Management (NavERP.md bullet 4)
- **Planned vs. Unplanned Process Deviations** — Handle planned temporary deviations (pre-approved temporary departures from standard SOPs or manufacturing recipes) and unplanned deviations (unexpected operational excursions).
  - *Seen in:* Veeva Vault, MasterControl, Sparta TrackWise
  - *Priority:* `table-stakes`
  - *Spine:* Dedicated model `ProcessDeviation` (`QDEV-`), optional FK to `NonConformanceReport` and `quality.ControlledDocument`.
  - *Status:* Buildable now.
- **Risk & Product Quality Impact Evaluation** — Structured impact assessment evaluating product safety, efficacy, validation status, shelf life/stability, and regulatory compliance.
  - *Seen in:* Veeva Vault, Greenlight Guru, MasterControl
  - *Priority:* `table-stakes`
  - *Spine:* Fields on `ProcessDeviation`.
  - *Status:* Buildable now.
- **Affected Batch Tracing & Customer / Regulatory Notification** — Trace all impacted lots/batches across manufacturing runs; document customer notification requirements (concession approval required by customer contract) and regulatory reporting evaluations (e.g. FDA 21 CFR 806 / Medical Device Reportability).
  - *Seen in:* Veeva Vault, MasterControl, Sparta TrackWise
  - *Priority:* `common`
  - *Spine:* Fields on `ProcessDeviation` (`affected_lots_summary`, `customer_notification_required`, `regulatory_reporting_required`, `regulatory_authority_notified`).
  - *Status:* Buildable now.
- **Temporary Deviation Expiry & Controls** — Time-limited and batch-limited deviation approvals with mandatory expiration dates and maximum permitted production run limits to prevent temporary concessions from becoming permanent unvalidated practices.
  - *Seen in:* Veeva Vault, QT9, MasterControl
  - *Priority:* `common`
  - *Spine:* Fields on `ProcessDeviation` (`valid_from`, `valid_until`, `max_batch_limit`, `batches_produced_count`).
  - *Status:* Buildable now.

### 5. Trending, Metrics & Quality Closed-Loop (NavERP.md bullet 5)
- **NCR Lifecycle State Machine & Closed-Loop Resolution** — Structured progression: `draft` -> `containment_active` -> `under_investigation` -> `mrb_review` -> `disposition_approved` -> `rework_in_progress` -> `closed` -> `voided`.
  - *Seen in:* All 8 leaders
  - *Priority:* `table-stakes`
  - *Spine:* `status` choice on `NonConformanceReport`.
  - *Status:* Buildable now.
- **CAPA Escalation Trigger** — One-click or automated escalation for recurring, high-severity, or critical non-conformances directly linking into `quality.CapaInvestigation` (`apps.quality.models.CapaManagement`).
  - *Seen in:* All 8 leaders
  - *Priority:* `table-stakes`
  - *Spine:* `capa_investigation` FK on `NonConformanceReport`.
  - *Status:* Buildable now.
- **Non-Conformance Analytics & Pareto Review Dashboard** — Visual summary cards: open NCRs count, quarantine hold count, pending MRB count, scrap cost YTD, Pareto defect breakdown, and severity distribution.
  - *Seen in:* ETQ Reliance, Qualio, ComplianceQuest
  - *Priority:* `differentiator`
  - *Spine:* Custom aggregated view `ncr_analytics_dashboard`.
  - *Status:* Buildable now.

---

## Recommended build scope (this pass — 4 models)

To completely cover all 5 feature bullets of `NavERP.md 12.5` while staying strictly within the 1–4 model build unit, we recommend the following four tenant-scoped models:

1. **`NonConformanceReport`** [prefix `QNCR`]
   - **Purpose:** Primary quality event record capturing the non-conformance report, classification, defect coding, affected item/lot quantities, initial severity, and lifecycle status.
   - **Key fields:** `tenant`, `number` (`QNCR-#####`), `title`, `source_type` (`incoming`, `in_process`, `final_inspection`, `customer_return`, `internal_audit`, `supplier`), `category` (`material`, `process`, `product`, `supplier`, `facility`, `documentation`), `severity` (`minor`, `major`, `critical`), `status` (`draft`, `containment_active`, `under_investigation`, `mrb_review`, `disposition_approved`, `rework_in_progress`, `closed`, `voided`), `defect_code`, `defect_description`, `department` (FK `core.OrgUnit`), `initiator` (FK `accounts.User`), `owner` (FK `accounts.User`), `supplier_party` (FK `core.Party`, null=True), `affected_item_code`, `affected_item_name`, `lot_serial_numbers`, `quantity_inspected`, `quantity_nonconforming`, `unit_of_measure`, `estimated_financial_loss`, `immediate_containment_required` (bool), `capa_required` (bool), `capa_investigation` (FK `quality.CapaInvestigation`, null=True), `closed_at`, `closed_by` (FK `accounts.User`, null=True).
   - **Justified by:** Researched feature 1 (NCR Initiation, Defect Coding, Quantity Accounting, CAPA Linkage).

2. **`QuarantineContainment`** [prefix `QCNT`]
   - **Purpose:** Immediate physical and digital containment action to quarantine suspect material, assign red tags, trigger stop-ship/production holds, and manage controlled release.
   - **Key fields:** `tenant`, `number` (`QCNT-#####`), `ncr` (FK `NonConformanceReport`), `hold_type` (`physical_quarantine`, `digital_hold`, `stop_shipment`, `stop_production`), `quarantine_location` (e.g. "Quarantine Cage B", "Receiving Hold Area"), `red_tag_number`, `quantity_on_hold`, `unit_of_measure`, `hold_date`, `hold_applied_by` (FK `accounts.User`), `status` (`active`, `partially_released`, `released`, `disposed`), `release_criteria`, `released_quantity`, `release_date`, `released_by` (FK `accounts.User`, null=True), `disposition_notes`.
   - **Justified by:** Researched feature 2 (Quarantine & Containment, Red-Tagging, Controlled Release).

3. **`MrbDisposition`** [prefix `QMRB`]
   - **Purpose:** Cross-functional Material Review Board disposition decision, technical justification, rework protocol, reinspection sign-off, and cost-of-quality tracking.
   - **Key fields:** `tenant`, `number` (`QMRB-#####`), `ncr` (FK `NonConformanceReport`), `disposition_decision` (`scrap`, `rework`, `repair`, `use_as_is`, `return_to_vendor`, `regrade`), `technical_justification`, `concession_rationale`, `rework_instructions`, `rework_assignee` (FK `accounts.User`, null=True), `rework_completed_date`, `reinspection_required` (bool), `reinspection_criteria`, `reinspection_passed` (null=True, bool), `reinspection_by` (FK `accounts.User`, null=True), `scrap_cost` (Decimal), `rework_labor_cost` (Decimal), `vendor_chargeback_cost` (Decimal), `total_cost_impact` (Decimal), `mrb_chair` (FK `accounts.User`), `quality_approved_by` (FK `accounts.User`, null=True), `engineering_approved_by` (FK `accounts.User`, null=True), `operations_approved_by` (FK `accounts.User`, null=True), `status` (`draft`, `under_review`, `approved`, `rejected`, `executed`).
   - **Justified by:** Researched feature 3 (MRB Convening, Disposition Workflows, Cost of Poor Quality, Multi-signature sign-off).

4. **`ProcessDeviation`** [prefix `QDEV`]
   - **Purpose:** Planned temporary concessions and unplanned process deviations, risk/product impact assessments, customer/regulatory notifications, and expiration controls.
   - **Key fields:** `tenant`, `number` (`QDEV-#####`), `title`, `deviation_type` (`planned`, `unplanned`), `category` (`process_parameter`, `equipment_substitution`, `material_substitution`, `procedural_exemption`, `environmental`), `ncr` (FK `NonConformanceReport`, null=True), `controlled_document` (FK `quality.ControlledDocument`, null=True), `department` (FK `core.OrgUnit`), `requested_by` (FK `accounts.User`), `approved_by` (FK `accounts.User`, null=True), `risk_impact_level` (`negligible`, `minor`, `moderate`, `critical`), `quality_impact_assessment`, `affected_lots_summary`, `customer_notification_required` (bool), `customer_concession_obtained` (bool), `regulatory_reporting_required` (bool), `regulatory_authority_notified` (bool), `valid_from`, `valid_until`, `max_batches_permitted`, `batches_produced_count`, `status` (`draft`, `under_assessment`, `approved`, `active`, `expired`, `closed`, `cancelled`).
   - **Justified by:** Researched feature 4 (Process Deviations, Risk & Lot Impact Assessment, Customer/Regulatory Notifications, Time/Batch Expiry).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **12.6 Supplier Quality Management:** Supplier audits, Approved Vendor List (AVL), and Supplier Corrective Action Requests (SCAR) → parked for Sub-module 12.6.
- **12.7 Incoming Quality Control (IQC):** Receiving inspection plans, ANSI/ASQ Z1.4 sampling, AQL inspection checklists → parked for Sub-module 12.7.
- **12.11 Quality Audits:** Internal audit schedules, audit checklists, auditor qualifications, and audit finding reports → parked for Sub-module 12.11.
- **12.13 Customer Complaints:** Complaint intake, MDR/Vigilance customer triage, complaint investigation records → parked for Sub-module 12.13.

---

## Deferred (later passes / integrations)

- **Automated ERP inventory stock holds:** Direct SQL triggers or API hooks into Module 5 WMS `StockMove` and warehouse bin quarantine locks (deferred until Module 5 Inventory/WMS lands).
- **Electronic regulatory submission gateways:** Direct FDA eMDR AS2 gateway XML submission or EU EUDAMED integration (deferred to enterprise regulatory connector plugin).
- **Automated barcode / RFID quarantine scanner integration:** Mobile scanner hardware integration for physical red tags (deferred to mobile field quality pass).
